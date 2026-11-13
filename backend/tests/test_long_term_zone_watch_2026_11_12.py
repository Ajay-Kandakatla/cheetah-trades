"""📅 Long Term — 🔔 the zone pass (pkzone spec §3.3, tests 1–22, 2026-11-12).

Ajay 2026-11-12, verbatim: "add an alert list when stocks reach Pankaj's zones and also tell me if you finish the long
term tabs in general". The 09-08 purge found 6,378 push_history rows for 1 delivered — the latch must make a repeat
impossible. Fakes record every collection method AND every update operator; the latch fake refuses anything but
insert_one. Prefs and the hook are monkeypatched explicitly (registered AND not) so these pass before and after the
kind lands in push/subs.py. NEGATIVES throughout.
"""
from __future__ import annotations

import ast
import importlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from long_term_list import constants as C
from long_term_list import payload as P
from long_term_list import push as PUSH
from long_term_list import seed as SD
from long_term_list import sources as SRC
from long_term_list import words as W
from long_term_list import zone_watch as ZW

ET = ZoneInfo("America/New_York")
SEED = SD.load()
ENTRIES = SD.pankaj_entries(SEED)
SYMS = list(ENTRIES)
OWNER = "owner@example.com"
TUE = "2026-11-17"                                   # session; previous market day = Mon 2026-11-16
MON_PREV = "2026-11-16"
FAR = 1.0e6                                          # a close outside every zone of every name


def at(hh, mm, day=TUE):
    y, m, d = (int(x) for x in day.split("-"))
    return datetime(y, m, d, hh, mm, tzinfo=ET)


class DuplicateKeyError(Exception):
    pass


class _Res:
    def __init__(self, n):
        self.modified_count = n


class FakeLatch:
    """INSERT ONLY — any other write raises (test 18)."""

    def __init__(self, fail=0):
        self.docs, self.calls, self.fail = {}, [], fail

    def insert_one(self, doc):
        self.calls.append("insert_one")
        if self.fail:
            self.fail -= 1
            raise RuntimeError("mongo timeout")
        if doc["_id"] in self.docs:
            raise DuplicateKeyError(doc["_id"])
        self.docs[doc["_id"]] = dict(doc)

    def __getattr__(self, name):
        if name in ("update_one", "update_many", "replace_one", "delete_one", "delete_many", "find_one_and_update",
                    "find_one_and_replace", "find_one_and_delete", "bulk_write"):
            def _refuse(*a, **k):
                raise AssertionError(f"latch collection saw {name}")
            return _refuse
        raise AttributeError(name)


def _set_path(doc, path, value):
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def _has_path(doc, path):
    cur = doc
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return False
        cur = cur[p]
    return True


class FakeState:
    def __init__(self):
        self.docs, self.calls, self.ops, self.writes = {}, [], [], []

    def update_one(self, flt, upd, upsert=False):
        self.calls.append("update_one")
        self.ops.extend(upd.keys())
        if set(upd) - {"$set"}:
            raise AssertionError(f"state coll saw {set(upd) - {'$set'}}")
        d = self.docs.get(flt["_id"])
        for k, v in flt.items():
            if k == "_id":
                continue
            if isinstance(v, dict) and v.get("$exists") is False:
                if d is not None and _has_path(d, k):
                    return _Res(0)
        if d is None:
            if not upsert:
                return _Res(0)
            d = self.docs[flt["_id"]] = {"_id": flt["_id"]}
        for path, val in upd["$set"].items():
            _set_path(d, path, val)
            self.writes.append(path)
        return _Res(1)

    def find_one(self, flt):
        self.calls.append("find_one")
        d = self.docs.get(flt["_id"])
        return None if d is None else dict(d)


def mkdb():
    return {C.ZONE_LATCH_COLL: FakeLatch(), C.ZONE_STATE_COLL: FakeState()}


def snap(price, when):
    return {"last_trade_price": price, "last_trade_ts_ms": int(when.timestamp() * 1000)}


class Snaps:
    """Counting bulk_snapshot fake: exactly the 40 names per call."""

    def __init__(self, prices=None):
        self.prices, self.calls = dict(prices or {}), []

    def __call__(self, syms):
        self.calls.append(list(syms))
        return dict(self.prices)


class Closes:
    def __init__(self, closes=None, date=MON_PREV, default=FAR):
        self.calls = []
        self.closes = {s: {"close": default, "date": date} for s in SYMS}
        for s, v in (closes or {}).items():
            if v is None:
                self.closes.pop(s, None)
            else:
                self.closes[s] = v

    def __call__(self, symbols, now=None, *, before=None):
        self.calls.append({"symbols": list(symbols), "now": now, "before": before})
        return {k: dict(v) for k, v in self.closes.items()}


class Sender:
    def __init__(self, res=None):
        self.calls, self.res = [], res or {"sent": 1, "failed": 0, "total_targets": 1}

    def __call__(self, *, owner, payload):
        self.calls.append((owner, payload))
        return dict(self.res)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    from push import sender as SENDER, subs
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setattr(subs, "_owner_email", lambda: OWNER)
    real = subs.default_prefs
    monkeypatch.setattr(subs, "default_prefs", lambda: {**real(), C.KIND: False})        # registered

    def _never(*a, **k):
        raise AssertionError("send_to_all reached")
    monkeypatch.setattr(SENDER, "send_to_all", _never)
    monkeypatch.setattr(PUSH, "_hook", lambda: None)            # the real sender is never reached in this file


def run(now, *, db, snaps, closes=None, send=None, **kw):
    return ZW.run_pass(now, seed=SEED, snap_fn=snaps, closes_fn=closes or Closes(), db=db, send=send, **kw)


def tsm(price, when):
    return Snaps({"TSM": snap(price, when)})


def tsm_closes(close=430.0, date=MON_PREV):
    return Closes({"TSM": {"close": close, "date": date}})


def payload_for(db, now, session=TUE):
    day = db[C.ZONE_STATE_COLL].docs.get(session)
    return P.build_payload(SEED, {}, [], [], {}, now=now, owner=True, zone_live=ZW.serve_state(day, now),
                           zone_day=day, log_session=session)["zones"]["alert"]


# ── 1 / 1b — same zone twice in a session ───────────────────────────────────────────────────────────────────────
def test_01_same_zone_twice_in_a_session_rings_once():
    db, s = mkdb(), Sender()
    a = run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    b = run(at(10, 5), db=db, snaps=tsm(406.5, at(10, 4)), closes=tsm_closes(), send=s)
    assert a["reached"] == [f"{TUE}|TSM|Agg"] and a["pushed"] == 1
    assert len(s.calls) == 1                                               # NEG: never a second send
    assert b["dup"] == 1 and b["results"] == [{"id": f"{TUE}|TSM|Agg", "state": "dup", "sent": 0}]
    assert list(db[C.ZONE_LATCH_COLL].docs) == [f"{TUE}|TSM|Agg"]


def test_01b_a_duplicate_writes_nothing_and_the_log_keeps_the_first_reach():
    db, s = mkdb(), Sender()
    run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    st = db[C.ZONE_STATE_COLL]
    n_before = len(st.writes)
    run(at(10, 5), db=db, snaps=tsm(406.5, at(10, 4)), closes=tsm_closes(), send=s)
    later = st.writes[n_before:]
    assert not [w for w in later if w.startswith("results.")]              # NEG [C1]: no result on a dup
    assert set(st.ops) == {"$set"} and "$push" not in st.ops               # NEG: never an array append
    doc = st.docs[TUE]
    rec = doc["reaches"]["TSM|Agg"]
    assert rec["at_hhmm"] == "10:00" and rec["price"] == 405.0             # first write wins
    assert doc["results"]["TSM|Agg"]["state"] == "pushed"
    alert = payload_for(db, at(10, 6))
    assert [r["push_text"] for r in alert["log"]] == ["rang your phone"]
    assert alert["log"][0]["push_text"] != W.ZONE_RESULT_MISSING


# ── 2 / 3 / 4 ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_02_leaves_and_reenters_the_same_session_rings_once():
    db, s = mkdb(), Sender()
    run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    out = run(at(10, 10), db=db, snaps=tsm(430.0, at(10, 9)), closes=tsm_closes(), send=s)
    assert out["reached"] == []
    again = run(at(10, 15), db=db, snaps=tsm(404.0, at(10, 14)), closes=tsm_closes(), send=s)
    assert again["dup"] == 1 and len(s.calls) == 1                         # NEG
    assert list(db[C.ZONE_STATE_COLL].docs[TUE]["reaches"]) == ["TSM|Agg"]


def test_03_a_different_zone_the_same_session_rings_once_more():
    db, s = mkdb(), Sender()
    run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    run(at(10, 5), db=db, snaps=tsm(370.0, at(10, 4)), closes=tsm_closes(), send=s)
    assert len(s.calls) == 2
    assert [p["tag"] for _, p in s.calls] == [f"long_term:zone:{TUE}:TSM:Agg", f"long_term:zone:{TUE}:TSM:C1"]
    assert sorted(db[C.ZONE_STATE_COLL].docs[TUE]["reaches"]) == ["TSM|Agg", "TSM|C1"]
    run(at(10, 10), db=db, snaps=tsm(371.0, at(10, 9)), closes=tsm_closes(), send=s)
    assert len(s.calls) == 2                                               # NEG


def test_04_next_session_may_ring_again_unless_its_prior_close_sat_inside():
    db, s = mkdb(), Sender()
    run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    wed = "2026-11-18"
    run(at(10, 0, wed), db=db, snaps=tsm(405.0, at(9, 59, wed)), closes=tsm_closes(430.0, TUE), send=s)
    assert len(s.calls) == 2 and f"{wed}|TSM|Agg" in db[C.ZONE_LATCH_COLL].docs
    thu = "2026-11-19"
    out = run(at(10, 0, thu), db=db, snaps=tsm(405.0, at(9, 59, thu)), closes=tsm_closes(404.0, wed), send=s)
    assert out["reached"] == [] and len(s.calls) == 2                      # NEG: closed inside → no reach
    assert "reaches" not in db[C.ZONE_STATE_COLL].docs[thu]                # NEG: no log row


# ── 5 restart-safe / race ───────────────────────────────────────────────────────────────────────────────────────
def test_05_restart_safe_and_a_raced_insert_sends_once():
    db, s = mkdb(), Sender()
    run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    zw2 = importlib.reload(ZW)                                             # a fresh process / module state
    zw2.run_pass(at(10, 5), seed=SEED, snap_fn=tsm(405.0, at(10, 4)), closes_fn=tsm_closes(), db=db, send=s)
    assert len(s.calls) == 1                                               # NEG
    db2, s2 = mkdb(), Sender()
    a = run(at(10, 0), db=db2, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s2)
    b = run(at(10, 0), db=db2, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s2)
    assert a["pushed"] + b["pushed"] == 1 and len(s2.calls) == 1 and b["dup"] == 1


# ── 6 / 7 closed day, override ──────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("now,why", [(at(10, 0, "2026-11-21"), "weekend"),
                                     (at(10, 0, "2026-11-26"), "holiday 2026-11-26")])
def test_06_closed_day_reads_nothing_writes_nothing_sends_nothing(now, why):
    db, s, sn, cl = mkdb(), Sender(), tsm(405.0, now), tsm_closes()
    out = run(now, db=db, snaps=sn, closes=cl, send=s)
    assert out == {"ran": False, "reason": why}
    assert sn.calls == [] and cl.calls == [] and s.calls == []
    assert db[C.ZONE_LATCH_COLL].calls == [] and db[C.ZONE_STATE_COLL].calls == []


def test_07_override_env_never_reads_or_sends(monkeypatch):
    monkeypatch.setenv("CHEETAH_IGNORE_HOLIDAY", "1")
    db, s, sn = mkdb(), Sender(), tsm(405.0, at(9, 59))
    out = run(at(10, 0), db=db, snaps=sn, closes=tsm_closes(), send=s)
    assert out["reason"] == ZW.R_OVERRIDE and sn.calls == [] and s.calls == []
    assert db[C.ZONE_STATE_COLL].calls == []


# ── 8 owner only ────────────────────────────────────────────────────────────────────────────────────────────────
def test_08_owner_only_and_no_broadcast_named():
    db, s = mkdb(), Sender()
    run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    assert [o for o, _ in s.calls] == [OWNER]
    root = Path(__file__).resolve().parents[1] / "long_term_list"
    for f in ("zone_watch.py", "push.py"):
        tree = ast.parse((root / f).read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
        assert "send_to_all" not in names, f


# ── 9 no snapshot ───────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raising", [False, True])
def test_09_no_snapshot_no_latch_no_send_and_a_served_reason(raising):
    def _raise(syms):
        raise RuntimeError("massive down")
    db, s = mkdb(), Sender()
    out = run(at(10, 35), db=db, snaps=_raise if raising else Snaps({}), closes=tsm_closes(), send=s)
    assert out["reason"] == ZW.R_NO_SNAPSHOT and s.calls == []
    assert db[C.ZONE_LATCH_COLL].calls == []
    assert db[C.ZONE_STATE_COLL].docs[TUE]["reason"] == "no_snapshot"
    alert = payload_for(db, at(10, 36))
    assert alert["live"] is True
    assert alert["reason"] == "No live prices at the 10:35 ET pass — nothing could ring."


# ── 10 / 11 / 12 price and baseline guards ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0, -5.0, "abc"])
def test_10_bad_last_trade_price_is_not_live(bad):
    db, s = mkdb(), Sender()
    out = run(at(10, 0), db=db, snaps=tsm(bad, at(9, 59)), closes=tsm_closes(), send=s)
    assert out["reads"]["TSM"]["basis"] != "live" and out["reached"] == [] and s.calls == []


def test_11_a_trade_stamped_yesterday_is_not_live():
    db, s = mkdb(), Sender()
    out = run(at(9, 5), db=db, snaps=tsm(405.0, at(19, 30, MON_PREV)), closes=tsm_closes(), send=s)
    assert out["reads"]["TSM"]["basis"] == "close" and out["reached"] == [] and s.calls == []


def test_12_no_prior_close_cannot_reach():
    db, s = mkdb(), Sender()
    out = run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=Closes({"TSM": None}), send=s)
    assert out["reads"]["TSM"]["prior_basis"] == ZW.P_NONE and out["reached"] == [] and s.calls == []


# ── 13 store error on the latch ─────────────────────────────────────────────────────────────────────────────────
def test_13_a_non_dup_latch_error_is_no_store_then_a_later_pass_sends_once():
    db, s = mkdb(), Sender()
    db[C.ZONE_LATCH_COLL].fail = 1
    a = run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    assert s.calls == [] and a["results"][0]["state"] == "no_store"
    assert db[C.ZONE_STATE_COLL].docs[TUE]["results"]["TSM|Agg"]["state"] == "no_store"
    run(at(10, 5), db=db, snaps=tsm(405.0, at(10, 4)), closes=tsm_closes(), send=s)
    run(at(10, 10), db=db, snaps=tsm(405.0, at(10, 9)), closes=tsm_closes(), send=s)
    assert len(s.calls) == 1
    assert [r["push_text"] for r in payload_for(db, at(10, 11))["log"]] == ["rang your phone"]


# ── 14 / 14b the log is not the latch ───────────────────────────────────────────────────────────────────────────
def test_14_blocked_pushes_still_log_the_reach_and_never_touch_the_latch(monkeypatch):
    from push import subs
    cases = []
    monkeypatch.setattr(C, "ZONE_PUSH_MODE", "off")
    db, s = mkdb(), Sender()
    run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    cases.append((db, s, "off", "not sent — phone push is off"))
    monkeypatch.setattr(C, "ZONE_PUSH_MODE", "live")
    real = subs.default_prefs
    monkeypatch.setattr(subs, "default_prefs", lambda: {k: v for k, v in real().items() if k != C.KIND})
    db, s = mkdb(), Sender()
    run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    cases.append((db, s, "kind", "not sent — the phone alert kind is not registered"))
    monkeypatch.setattr(subs, "default_prefs", lambda: {**real(), C.KIND: False})
    db = mkdb()
    run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=None)   # _hook → None
    cases.append((db, Sender(), "no_hook", "not sent — no phone sender"))
    for db, s, reason, text in cases:
        assert s.calls == [] and db[C.ZONE_LATCH_COLL].calls == []         # NEG: latch untouched
        doc = db[C.ZONE_STATE_COLL].docs[TUE]
        assert doc["reason"] == reason and doc["reaches"]["TSM|Agg"]["push_reason"] == reason
        assert "results" not in doc
        assert [r["push_text"] for r in payload_for(db, at(10, 1))["log"]] == [text]


def test_14b_logged_under_off_then_live_rings_once_and_keeps_the_first_time(monkeypatch):
    monkeypatch.setattr(C, "ZONE_PUSH_MODE", "off")
    db, s = mkdb(), Sender()
    run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    monkeypatch.setattr(C, "ZONE_PUSH_MODE", "live")
    run(at(10, 5), db=db, snaps=tsm(406.0, at(10, 4)), closes=tsm_closes(), send=s)
    assert len(s.calls) == 1 and len(db[C.ZONE_LATCH_COLL].docs) == 1
    rec = db[C.ZONE_STATE_COLL].docs[TUE]["reaches"]["TSM|Agg"]
    assert rec["at_hhmm"] == "10:00" and rec["push_reason"] == "off"
    assert [r["push_text"] for r in payload_for(db, at(10, 6))["log"]] == ["rang your phone"]   # result wins


# ── 15 outside the push window ──────────────────────────────────────────────────────────────────────────────────
def test_15_outside_push_hours_logs_not_sent():
    db, s = mkdb(), Sender()
    out = run(at(20, 30), db=db, snaps=tsm(405.0, at(19, 55)), closes=tsm_closes(), send=s)
    assert out["reason"] == ZW.R_WINDOW and s.calls == [] and db[C.ZONE_LATCH_COLL].calls == []
    rec = db[C.ZONE_STATE_COLL].docs[TUE]["reaches"]["TSM|Agg"]
    assert W.zone_log_push_text(None, rec["push_reason"]) == "not sent — outside the app's push hours"


# ── 16 the body ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_16_body_words():
    import re
    db, s = mkdb(), Sender()
    run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    _, p = s.calls[0]
    text = p["title"] + "\n" + p["body"]
    for part in ("TSM", "Agg", "400–410", "405.00", "Tier", "Pankaj's"):
        assert part in text, part
    assert p["kind"] == C.KIND == "long_term" and p["url"] == C.ZONE_URL
    assert not re.search(r"buy", text, re.I) and not re.search(r"\bentry\b", text, re.I)    # NEG
    assert W.NOT_A_SIGNAL not in text and " · pre-mkt" not in text
    assert SD.category(SEED, "pankaj")["names"][0]["action"].lower().startswith("buy")     # the sheet has it …
    ent = dict(ENTRIES["TSM"], action="Buy CL1")
    body = ZW.compose("TSM", ent, "Agg", 405.0, TUE, "rth")["body"]
    assert "Buy" not in body and "CL1" not in body                         # … it never reaches a body
    db2, s2 = mkdb(), Sender()
    run(at(9, 5), db=db2, snaps=tsm(405.0, at(9, 4)), closes=tsm_closes(), send=s2)
    assert " · pre-mkt" in s2.calls[0][1]["body"]


# ── 17 / 18 / 19 ────────────────────────────────────────────────────────────────────────────────────────────────
def test_17_exactly_one_snapshot_call_carrying_all_40():
    db, sn = mkdb(), tsm(405.0, at(9, 59))
    run(at(10, 0), db=db, snaps=sn, closes=tsm_closes(), send=Sender())
    assert len(sn.calls) == 1 and sorted(sn.calls[0]) == sorted(SYMS) and len(SYMS) == 40


def test_NEGATIVE_17_a_per_symbol_loop_fails_the_counter():
    sn = Snaps({})
    for sym in SYMS[:2]:
        sn([sym])
    assert not (len(sn.calls) == 1 and sorted(sn.calls[0]) == sorted(SYMS))


def test_18_the_latch_collection_sees_only_insert_one():
    db, s = mkdb(), Sender()
    for mm in (0, 5, 10):
        run(at(10, mm), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)
    assert set(db[C.ZONE_LATCH_COLL].calls) == {"insert_one"}
    with pytest.raises(AssertionError):
        db[C.ZONE_LATCH_COLL].update_one({}, {})                           # the fake would catch a retake


def test_19_dry_run_reads_but_never_writes_or_sends():
    db, s = mkdb(), Sender()
    out = run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s, dry=True)
    assert out["reason"] == ZW.R_DRY and out["reads"]["TSM"]["reached"] == ["Agg"]
    assert s.calls == [] and db[C.ZONE_LATCH_COLL].calls == [] and db[C.ZONE_STATE_COLL].calls == []


# ── 20 / 21 the dated baseline [C4] ─────────────────────────────────────────────────────────────────────────────
def test_20_stale_baseline_blocks_every_name_and_the_tab_says_so():
    db, s = mkdb(), Sender()
    stale = Closes({"TSM": {"close": 430.0, "date": "2026-11-13"}}, date="2026-11-13")
    out = run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=stale, send=s)
    assert out["n_stale"] == 40 and out["prev_session"] == MON_PREV
    assert all(r["prior_basis"] == ZW.P_STALE for r in out["reads"].values())
    assert out["reached"] == [] and s.calls == [] and db[C.ZONE_LATCH_COLL].calls == []
    assert "reaches" not in db[C.ZONE_STATE_COLL].docs[TUE]
    alert = payload_for(db, at(10, 1))
    assert alert["stale_text"] == "40 of 40 names have no cached close from 11-16 — they cannot ring this session."


def test_NEGATIVE_20_dated_baselines_ring_and_only_the_stale_name_is_blocked():
    db, s = mkdb(), Sender()
    assert run(at(10, 0), db=db, snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=s)["pushed"] == 1
    mon, fri = "2026-11-16", "2026-11-13"
    out = run(at(10, 0, mon), db=mkdb(), snaps=tsm(405.0, at(9, 59, mon)), closes=tsm_closes(430.0, fri),
              send=Sender())
    assert out["reads"]["TSM"]["prior_basis"] == ZW.P_OK and out["pushed"] == 1          # Monday ← Friday
    after, before_hol = "2026-11-27", "2026-11-25"
    out = run(at(10, 0, after), db=mkdb(), snaps=tsm(405.0, at(9, 59, after)),
              closes=tsm_closes(430.0, before_hol), send=Sender())
    assert out["prev_session"] == before_hol and out["reads"]["TSM"]["prior_basis"] == ZW.P_OK
    one = Closes({"TSM": {"close": 430.0, "date": MON_PREV}, "META": {"close": FAR, "date": "2026-11-13"}})
    db3 = mkdb()
    out = run(at(10, 0), db=db3, snaps=tsm(405.0, at(9, 59)), closes=one, send=Sender())
    assert out["n_stale"] == 1 and out["pushed"] == 1 and out["reads"]["META"]["prior_basis"] == ZW.P_STALE
    assert payload_for(db3, at(10, 1))["stale_text"].startswith("1 of 40 ")


def test_21_the_pass_asks_for_closes_before_the_session():
    cl = tsm_closes()
    run(at(16, 30), db=mkdb(), snaps=tsm(405.0, at(16, 29)), closes=cl, send=Sender())
    assert cl.calls[0]["before"] == TUE and sorted(cl.calls[0]["symbols"]) == sorted(SYMS)


def test_21_real_pankaj_closes_cuts_at_before(monkeypatch):
    from sepa import prices
    idx = pd.to_datetime(["2026-11-13", MON_PREV, TUE])
    df = pd.DataFrame({"open": [1, 1, 1], "high": [1, 1, 1], "low": [1, 1, 1], "close": [430.0, 431.0, 405.0],
                       "volume": [1, 1, 1]}, index=idx)
    monkeypatch.setattr(prices, "bulk_cached_frames", lambda syms: {"TSM": df.copy()})
    now = at(16, 30)
    assert SRC.pankaj_closes(["TSM"], now, before=TUE) == {"TSM": {"close": 431.0, "date": MON_PREV}}
    assert SRC.pankaj_closes(["TSM"], now) == {"TSM": {"close": 405.0, "date": TUE}}       # NEG: default unchanged


# ── 22 no items on the zone push [C5] ───────────────────────────────────────────────────────────────────────────
def test_22_no_items_and_the_feed_renders_the_body_as_is():
    from push import recent
    p = ZW.compose("TSM", ENTRIES["TSM"], "Agg", 405.0, TUE, "rth")
    assert "items" not in p
    row = {"kind": "long_term", "ticker": "TSM", "title": p["title"], "body": p["body"]}
    assert recent.served_items(row, frozenset()) is None
    with_items = dict(row, items=[{"symbol": "TSM", "text": p["body"].split("\n")[0]}])
    got = recent.served_items(with_items, frozenset())
    assert got is not None                                                  # NEG: why items stay out
    urls = [i.get("url") for i in got[0]]
    assert urls and all(u != C.ZONE_URL for u in urls)


# ── pure helpers ────────────────────────────────────────────────────────────────────────────────────────────────
def test_helpers():
    assert ZW.latch_id(TUE, "TSM", "Agg") == "2026-11-17|TSM|Agg"
    assert ZW.reach_key("BRK.B", "C$1") == "BRK_B|C_1"
    assert ZW.prev_session("2026-11-16") == "2026-11-13"
    assert ZW.session_of(datetime(2026, 11, 17, 23, 0)) == TUE
    assert ZW.log_session(at(10, 0, "2026-11-21")) == "2026-11-20"
    assert ZW.serve_state({"session": TUE}, at(10, 0)) == {"session": TUE}
    assert ZW.serve_state({"session": TUE}, at(20, 30)) is None             # NEG: house clock closed
    assert ZW.serve_state({"session": MON_PREV}, at(10, 0)) is None         # NEG: yesterday's pass
    line = ZW.summary(run(at(10, 0), db=mkdb(), snaps=tsm(405.0, at(9, 59)), closes=tsm_closes(), send=Sender()))
    assert line.startswith("ran=True session=2026-11-17") and "pushed=1" in line
    assert ZW.summary({"ran": False, "reason": "weekend"}) == "ran=False reason=weekend"


# ── key_levels reach is ONE helper, lazily (refix 2026-11-12: test_key_levels.py ALLOWED widened for this file) ──
def _kl_uses(src: str):
    tree = ast.parse(src)
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    attrs = {n.attr for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "KL"}
    return top, attrs


def test_zone_watch_reaches_key_levels_only_for_prev_market_day_and_only_lazily():
    src = (Path(ZW.__file__)).read_text(encoding="utf-8")
    top, attrs = _kl_uses(src)
    top_mods = {getattr(n, "module", None) or "" for n in top} | {a.name for n in top for a in n.names}
    assert not any("key_level" in m for m in top_mods)
    assert attrs == {"prev_market_day"}
    every = {(getattr(n, "module", None) or "") + ":" + ",".join(a.name for a in n.names)
             for n in ast.walk(ast.parse(src)) if isinstance(n, (ast.Import, ast.ImportFrom))}
    assert not [m for m in every if "key_level_alerts" in m]
    assert [m for m in every if "key_levels" in m] == ["supply_demand:key_levels"]
    from supply_demand import key_levels as KL
    from datetime import date
    for s in ("2026-11-16", "2026-11-27", "2026-11-17"):
        assert ZW.prev_session(s) == KL.prev_market_day(date.fromisoformat(s)).isoformat()


def test_NEGATIVE_the_scope_pin_catches_a_top_level_import_or_a_second_helper():
    top, attrs = _kl_uses("from supply_demand import key_levels as KL\nx = KL.tile_block\n")
    assert top and attrs == {"tile_block"}
    top, attrs = _kl_uses("def f():\n    from supply_demand import key_levels as KL\n    return KL.prev_market_day\n")
    assert not top and attrs == {"prev_market_day"}
