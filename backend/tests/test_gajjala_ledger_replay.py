"""chart_maps/gajjala/ledger.py + store.py — the ⏪ REPLAYED line (2026-10-16 night, DECISIONS11 D4 / D5, BUILD_SPEC11
§3.11 / §3.12, AMENDMENTS11 F15).

Ajay 2026-10-16 ~22:30 ET: "Would you be able to back test for the past week from his alerts any way to do so? build a
pre historic timeline or so?" — a replay doc (today's detectors re-run on a session with no record, written ONLY by
scripts/gajjala_replay.py --write) is its OWN line: never rang, never in a sent count, never a %. WP-C STEP 1's tests
(1: alert_of, 7: the store) and STEP 2's (2: the served block, 3: a replay read fault, 4: grade_step / today_read never
see a replay doc, 5: the source filter, 6: the spans, 8: the tape) — BUILD_SPEC11 §4 WP-C.

Every store is the in-memory FakeColl set (tests/conftest.py refuses a real MongoClient). Every doc is SYNTHETIC (the
§3.12 shape) and named so. NEGATIVES are mandatory and marked.
"""
from __future__ import annotations

import copy
import json
from datetime import date, datetime

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from tests.test_gajjala_ledger import ET, aplus_doc, et
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import run_route
from tests.test_gajjala_track_record_tab import (D16, NOW, _et, _rows, board, graded_replay_doc, ledger_store,
                                                 no_split, tape_loader)

D12 = date(2026, 10, 12)                      # Columbus Day — the market was open (DECISIONS11 facts)
D13 = date(2026, 10, 13)


def replay_doc(sym="SYM", setup="bull_flag", d=D12, *, at=None, trigger=1.23, stop=1.11, **over) -> dict:
    """SYNTHETIC — the BUILD_SPEC11 §3.12 replay doc (same / next left null: STEP 1 tests the row, not the grades)."""
    at = at or et(d, 10, 35).isoformat()
    doc = {"_id": LG.replay_id(d.isoformat(), sym, setup), "date": d.isoformat(), "symbol": sym, "setup": setup,
           "kind": "aplus", "state": "replayed",
           "alert": {"date": d.isoformat(), "symbol": sym, "setup": setup, "entry_bar_t": f"{d.isoformat()} 10:30",
                     "frame": "5m", "trigger": trigger, "stop": stop, "risk_pct": 9.76,
                     "pass_t": f"{d.isoformat()} 10:35", "q_t": f"{d.isoformat()} 09:52", "at": at},
           "same": None, "next": None, "bars5": [], "universe": "study same-day q", "float_gate": False,
           "detectors_sha": "abc1234", "detectors_sha256": "0" * 64, "replayed_at": "2026-10-17T03:00:00+00:00",
           "caveats": list(LG.REPLAY_CAVEATS)}
    doc.update(over)
    return doc


# ── 1. alert_of reads the replayed line (D5, C6, F15) ────────────────────────────────────────────────────────────────
def test_replay_id_and_the_frozen_names():
    assert LG.replay_id("2026-10-12T00:00:00", "sym", "bull_flag") == "REPLAY:2026-10-12|SYM|bull_flag"
    assert LG.REPLAY_ID_PREFIX == "REPLAY:" and LG.REPLAY_STATE == "replayed"
    assert LG.LINES == ("live", "shadow", "replayed") and LG.COUNT_LINES == ("live", "shadow", "entry", "replayed")
    assert LG.KIND_TEXT[("aplus", LG.LINES[2])] == "⏪ A+ replayed"
    assert LG.FLOAT_GATED_SETUPS == ("reversal_squeeze",)
    assert LG.REPLAY_CHIP == "⏪ replayed" and LG.REPLAY_CHIP_UNGATED == "⏪ replayed · 🎾 ungated"
    assert LG.REPLAY_NOT_GRADED_TEXT == "not graded (bars not cached)" and LG.REPLAY_FAULT_TEXT == "⏪ replay not read"
    assert LG.REPLAYED_HEAD == "⏪ Replayed with today's detectors (never rang, not in any %)"
    assert LG.REPLAY_NOTE == ("Replayed on the study's same-day universe (a subset of what the live scanner lists), no "
                              "float gate, as-printed bars; these never rang. Not a measurement — the 2026-10-14 study "
                              "read NULL.")
    # AMENDMENTS11 F10: the one-break-per-setup caveat sits right before the last line
    assert len(LG.REPLAY_CAVEATS) == 7 and LG.REPLAY_CAVEATS[-1] == ("These never rang. Not a measurement — the "
                                                                     "2026-10-14 study read NULL.")
    assert LG.REPLAY_CAVEATS[-2].startswith("One break per setup per day: the study keeps the first break of any class")
    assert "5-minute pass label" in LG.REPLAY_CAVEATS[3]                    # built from GC.PASS_CADENCE_SEC


def test_alert_of_reads_a_replay_doc_as_the_replayed_line():
    doc = replay_doc(trigger=1.23, stop=1.11)
    doc.update(trigger=9.0, stop=8.0, at=et(D12, 15, 0).isoformat(), price=7.0)   # top-level keys are NOT the alert's
    r = LG.alert_of(doc, "aplus")
    assert r is not None
    assert (r["id"], r["line"], r["kind"], r["date"], r["symbol"], r["setup"]) == \
        ("REPLAY:2026-10-12|SYM|bull_flag", "replayed", "aplus", "2026-10-12", "SYM", "bull_flag")
    assert r["id"] == doc["_id"] and r["id"] != LG.ledger_id("2026-10-12", "SYM", "bull_flag", "aplus")
    assert r["at_utc"] == et(D12, 10, 35) and r["at_et"] == "10:35" and r["rang"] == "rth"
    assert (r["trigger"], r["stop"], r["plan"], r["plan_source"]) == (1.23, 1.11, "ok", "aplus")
    assert r["r"] == pytest.approx(0.12) and r["price_at_alert"] is None
    assert r["url"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=SYM"
    assert LG.KIND_TEXT[(r["kind"], r["line"])] == "⏪ A+ replayed"


def test_the_existing_lines_are_unchanged_by_the_replay_branch():
    sh = LG.alert_of(aplus_doc("PMI", "bull_flag", D13, et(D13, 10, 36), 2.0, 1.9, price=1.95), "aplus")
    live = LG.alert_of(aplus_doc("PMI", "bull_flag", D13, et(D13, 10, 36), 2.0, 1.9, state="pushed"), "aplus")
    assert (sh["line"], sh["id"], live["line"], live["id"]) == \
        ("shadow", "2026-10-13|PMI|bull_flag|aplus", "live", "2026-10-13|PMI|bull_flag|aplus")


def _mut(kind: str) -> dict:
    """SYNTHETIC mutations of the §3.12 doc that must NEVER read as a replayed (or live) row."""
    d = replay_doc()
    if kind == "hash_suffix":                                   # REPLAY:…#x
        d["_id"] += "#x"
    elif kind == "hash_in_setup":                               # F15: the id equals replay_id yet carries a "#"
        d = replay_doc(setup="bull_flag#x")
    elif kind == "state_other":
        d["state"] = "shadow"
    elif kind == "state_missing":
        d.pop("state")
    elif kind == "state_pushed":                                # C6: a REPLAY: id in state pushed never reads live
        d["state"] = "pushed"
    elif kind == "kind_other":
        d["kind"] = "potential"
    elif kind == "kind_missing":
        d.pop("kind")
    elif kind == "other_symbol":
        d["_id"] = LG.replay_id("2026-10-12", "OTHER", "bull_flag")
    elif kind == "other_date":
        d["_id"] = LG.replay_id("2026-10-09", "SYM", "bull_flag")
    elif kind == "other_setup":
        d["_id"] = LG.replay_id("2026-10-12", "SYM", "kiss_fly")
    elif kind == "no_alert":
        d.pop("alert")
    elif kind == "empty_alert":
        d["alert"] = {}
    elif kind == "alert_not_a_dict":
        d["alert"] = "x"
    elif kind == "shadow_prefixed":                             # SHADOW:REPLAY:… is no replay id
        d["_id"] = "SHADOW:" + d["_id"]
    elif kind == "ledger_id":                                   # a ledger_id in state replayed is not a replay doc
        d["_id"] = LG.ledger_id("2026-10-12", "SYM", "bull_flag", "aplus")
    elif kind == "gg_claim":                                    # a live claim key in state replayed
        d["_id"] = "GG:2026-10-12|SYM|bull_flag"
    else:
        raise AssertionError(kind)
    return d


NEG_KINDS = ("hash_suffix", "hash_in_setup", "state_other", "state_missing", "state_pushed", "kind_other",
             "kind_missing", "other_symbol", "other_date", "other_setup", "no_alert", "empty_alert", "alert_not_a_dict",
             "shadow_prefixed", "ledger_id", "gg_claim")


@pytest.mark.parametrize("kind", NEG_KINDS)
def test_NEGATIVE_a_mutated_replay_doc_is_never_a_replayed_or_live_row(kind):
    doc = _mut(kind)
    assert LG.alert_of(doc, "aplus") is None, kind
    assert LG.alert_of(doc, "potential") is None, kind                    # never a 🧠 row either


def test_NEGATIVE_c6_bites_without_the_prefix_rule():
    """The C6 clause is what keeps a pushed REPLAY: id off the live line: the same doc with the prefix renamed reads
    live (so the NEGATIVE above is not vacuous)."""
    d = _mut("state_pushed")
    d["_id"] = d["_id"].replace(LG.REPLAY_ID_PREFIX, "XREPLAY:", 1)
    assert LG.alert_of(d, "aplus")["line"] == "live"


def test_NEGATIVE_the_replayed_branch_reads_only_the_alert_block():
    """No `alert.at` → a no-time row (the top-level `at` is never read for a replay doc)."""
    doc = replay_doc()
    doc["alert"].pop("at")
    doc["at"] = et(D12, 11, 0).isoformat()
    r = LG.alert_of(doc, "aplus")
    assert r["line"] == "replayed" and r["at_utc"] is None and r["at_et"] is None and r["rang"] is None


# ── 7. the store: gajjala_replay (D4) ───────────────────────────────────────────────────────────────────────────────
def test_replay_is_a_kept_indexed_collection_in_all():
    assert ST.REPLAY == "gajjala_replay" and ST.REPLAY in ST.ALL and ST.ALL[-1] == ST.REPLAY
    assert ST.REPLAY not in ST.TTL_DAYS
    st = fake_store()
    st.ensure_indexes()
    idx = st.coll(ST.REPLAY).indexes
    assert (("date", 1), ("symbol", 1)) in [s for s, _kw in idx] and (("symbol", 1), ("date", -1)) in [s for s, _kw in idx]
    assert not [kw for _s, kw in idx if kw.get("expireAfterSeconds")]                        # kept — no TTL
    assert ST.REPLAY_KEYS == frozenset({"date", "symbol", "setup", "kind", "state", "alert", "same", "next", "bars5",
                                        "universe", "float_gate", "detectors_sha", "detectors_sha256", "replayed_at",
                                        "caveats"})
    assert set(replay_doc()) - {"_id"} == ST.REPLAY_KEYS                                     # the §3.12 doc fits
    for n in ("replay_rows", "replay_dates", "records_on", "upsert_replay"):
        assert callable(getattr(ST.GajjalaStore, n)) and callable(getattr(ST, n)), n


def test_upsert_replay_writes_only_the_replay_collection_and_replaces():
    st = fake_store()
    doc = replay_doc()
    assert st.upsert_replay(doc) is True
    assert st.upsert_replay(dict(doc, universe="study same-day q (re-run)")) is True       # a re-run replaces
    assert set(st.coll(ST.REPLAY).docs) == {doc["_id"]}
    assert st.coll(ST.REPLAY).docs[doc["_id"]]["universe"] == "study same-day q (re-run)"
    assert all(st.coll(n).writes == 0 for n in ST.ALL if n != ST.REPLAY)                    # never another collection
    assert st.replay_rows([D12]) == [st.coll(ST.REPLAY).docs[doc["_id"]]]
    assert st.replay_dates() == ["2026-10-12"]


@pytest.mark.parametrize("bad", ["extra_key", "ledger_id", "gg_id", "shadow_id", "no_id", "int_id", "not_a_dict"])
def test_NEGATIVE_upsert_replay_refuses_a_bad_key_or_a_non_replay_id(bad):
    st = fake_store()
    doc = replay_doc()
    if bad == "extra_key":
        doc["push"] = {"state": "pushed"}
    elif bad == "ledger_id":
        doc["_id"] = LG.ledger_id("2026-10-12", "SYM", "bull_flag", "aplus")
    elif bad == "gg_id":
        doc["_id"] = "GG:2026-10-12|SYM|bull_flag"
    elif bad == "shadow_id":
        doc["_id"] = "SHADOW:" + doc["_id"]
    elif bad == "no_id":
        doc.pop("_id")
    elif bad == "int_id":
        doc["_id"] = 7
    else:
        doc = [doc]
    assert st.upsert_replay(doc) is False
    assert all(st.coll(n).writes == 0 for n in ST.ALL)


def test_replay_rows_filter_on_the_sessions_and_the_state():
    keep = replay_doc("AAA")
    other_day = replay_doc("BBB", d=D13)
    not_replayed = replay_doc("CCC", state="draft")
    st = fake_store(**{ST.REPLAY: FakeColl([keep, other_day, not_replayed])})
    assert [d["_id"] for d in st.replay_rows([D12])] == [keep["_id"]]
    assert sorted(d["_id"] for d in st.replay_rows([D12, D13])) == sorted([keep["_id"], other_day["_id"]])
    assert st.replay_rows([]) == []
    assert st.replay_dates() == ["2026-10-12", "2026-10-13"]


def test_records_on_sums_alerts_and_scan_docs_of_the_session():
    alerts = [copy.deepcopy(aplus_doc("PMI", "bull_flag", D13, et(D13, 10, 36), 2.0, 1.9)),
              dict(aplus_doc("TGL", "bull_flag", D13, et(D13, 10, 40), 2.0, 1.9, state="pushed"),
                   _id="GG:2026-10-13|TGL|bull_flag#late", state="late")]
    scan = [{"_id": ST.key(D13, "PMI"), "date": "2026-10-13", "symbol": "PMI"},
            {"_id": ST.key(D12, "OLD"), "date": "2026-10-12", "symbol": "OLD"}]
    st = fake_store(**{ST.ALERTS: FakeColl(alerts), ST.SCAN: FakeColl(scan)})
    assert st.records_on(D13) == 3                                  # every alert doc (any state) + every scan doc
    assert st.records_on(D12) == 1
    assert st.records_on(date(2026, 10, 9)) == 0
    assert st.records_on("2026-10-13") == 3


@pytest.mark.parametrize("which", [ST.ALERTS, ST.SCAN])
def test_NEGATIVE_records_on_is_none_when_either_read_faults(which):
    st = fake_store(**{which: FakeColl(fail=True)})
    assert st.records_on(D13) is None                               # unreadable is never "no record"


def test_NEGATIVE_a_failing_or_missing_replay_coll_reads_none_and_writes_false():
    st = fake_store(**{ST.REPLAY: FakeColl(fail=True)})
    assert (st.replay_rows([D12]), st.replay_dates()) == (None, None)
    assert st.upsert_replay(replay_doc()) is False
    none = ST.GajjalaStore(colls={n: None for n in ST.ALL})
    assert (none.replay_rows([D12]), none.replay_dates(), none.records_on(D12)) == (None, None, None)
    assert none.upsert_replay(replay_doc()) is False


def test_the_module_delegates_reach_the_default_store(monkeypatch):
    fake = fake_store()
    monkeypatch.setattr(ST, "_DEFAULT", fake)
    assert ST.upsert_replay(replay_doc()) is True
    assert [d["_id"] for d in ST.replay_rows([D12])] == ["REPLAY:2026-10-12|SYM|bull_flag"]
    assert ST.replay_dates() == ["2026-10-12"] and ST.records_on(D12) == 0


def test_the_ledger_reads_what_the_store_holds():
    """One shape end to end: a doc the store accepts is a replayed row for the ledger."""
    st = fake_store()
    assert st.upsert_replay(replay_doc("RPL"))
    (doc,) = st.replay_rows([D12])
    r = LG.alert_of(doc, "aplus")
    assert r["line"] == LG.LINES[2] and r["id"] == "REPLAY:2026-10-12|RPL|bull_flag"
    assert r["at_utc"].astimezone(ET).strftime("%H:%M") == "10:35"



# ══ STEP 2 — the served block, the nightly, the spans, the tape ═══════════════════════════════════════════════════
class Rec:
    """A call recorder: returns `ret` (or `ret(*a, **k)` when callable), raises `exc` when given."""

    def __init__(self, ret=None, exc=None):
        self.calls, self.ret, self.exc = [], ret, exc

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        if self.exc is not None:
            raise self.exc
        return self.ret(*a, **k) if callable(self.ret) else self.ret


@pytest.fixture(autouse=True)
def _clean_memos(monkeypatch):
    from chart_maps.gajjala import tape as TP
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    for m in (LG._TODAY_MEMO, LG._TODAY_SPLIT, TP._MEMO):
        m.clear()
    yield
    for m in (LG._TODAY_MEMO, LG._TODAY_SPLIT, TP._MEMO):
        m.clear()


def two_replays():
    """SYNTHETIC: a 🚩 bull_flag WIN graded through the next session, and a 🎾 reversal_squeeze LOSS whose next session
    was never cached (next null)."""
    a = graded_replay_doc("RPL", "bull_flag", D12)
    b = graded_replay_doc("RSQ", "reversal_squeeze", D12, outcome="loss", next_graded=False)
    return a, b


def with_replays(*docs, st=None):
    st = st or ledger_store()
    for d in docs:
        st.coll(ST.REPLAY).docs[d["_id"]] = copy.deepcopy(d)
    return st


SENT_TEXTS = ("counts_text", "shadow_text", "entries_text", "today_text", "empty_text")


# ── 2. the served block: its own line, its own counts, never a % ───────────────────────────────────────────────────
def test_served_block_serves_the_replayed_line_apart_from_every_sent_count():
    a, b = two_replays()
    base = board(ledger_store(), "5d")["track_record"]
    tr = board(with_replays(a, b), "5d")["track_record"]
    for k in ("live", "shadow", "entry"):                                          # NEGATIVE: byte-equal
        assert json.dumps(tr["counts"][k], sort_keys=True) == json.dumps(base["counts"][k], sort_keys=True), k
    for k in SENT_TEXTS:
        assert tr[k] == base[k], k
    c = tr["counts"]["replayed"]
    assert (c["same"]["win"], c["same"]["loss"], c["next"]["win"], c["next"]["pending"]) == (1, 1, 1, 1)
    assert all(c[h]["pct"] is None for h in GC.LEDGER_HORIZONS)                   # never a %
    assert all(base["counts"]["replayed"][h]["pct"] is None and base["counts"]["replayed"][h]["win"] == 0
               for h in GC.LEDGER_HORIZONS)
    rt = tr["replayed_text"]
    assert rt == ("⏪ Replayed with today's detectors (never rang, not in any %): same session 1 win · 1 loss · 0 no "
                  "entry · 0 open; through next session 1 win · 0 losses · 0 flat · 1 not graded (bars not cached)")
    assert rt.startswith(LG.REPLAYED_HEAD) and "% won" not in rt and "no graded entry" not in rt
    assert "not graded yet" not in rt and LG.REPLAY_NOT_GRADED_TEXT in rt    # NEGATIVE: the nightly never grades it
    assert tr["replayed_note"] == LG.REPLAY_NOTE
    assert (base["replayed_text"], base["replayed_note"]) == (None, None)        # NEGATIVE: no replay on file
    rows = _rows(tr)
    ra, rb = rows[a["_id"]], rows[b["_id"]]
    assert (ra["kind_text"], ra["line"], ra["kind"], ra["replay_text"]) == ("⏪ A+ replayed", "replayed", "aplus",
                                                                            LG.REPLAY_CHIP)
    assert rb["replay_text"] == LG.REPLAY_CHIP_UNGATED and "reversal_squeeze" in LG.FLOAT_GATED_SETUPS
    assert ra["same"]["state"] == "win" and ra["same"]["text"].startswith("WIN · best +")
    assert "fill 1.23 at 10:40" in ra["plan_text"] and ra["at_text"] == "10:35 ET" and ra["date"] == "2026-10-12"
    assert rb["same"]["state"] == "loss"
    assert rb["next"] == {"state": "pending", "text": LG.REPLAY_NOT_GRADED_TEXT, "sub_text": None,
                          "provisional": False}
    assert (ra["bucket"], rb["bucket"]) == ("win", "loss")
    assert rb["loss_text"] == LG.loss_text(LG.alert_of(b, "aplus"), b["same"]) and ra["loss_text"] is None
    others = [r for r in rows.values() if r["line"] != "replayed"]
    assert others and all(r["replay_text"] is None for r in others)
    assert [d["date"] for d in tr["days"]] == ["2026-10-16", "2026-10-15", "2026-10-12"]


def test_NEGATIVE_a_replayed_row_never_reads_the_ledger_nor_todays_grades():
    """A replayed row reads ONLY its own pre-graded columns: a gajjala_ledger doc planted under its id (a LOSS) and a
    today_read grade handed in for it are both ignored; a 10-16 replayed row with no grade never enters `needs`."""
    a = graded_replay_doc("RPL", "bull_flag", D12)
    t = graded_replay_doc("RPT", "bull_flag", D16, next_graded=False)
    t["same"] = None
    st = with_replays(a, t)
    plant = {"_id": a["_id"], "date": a["date"], "same": dict(a["same"], outcome="loss", reason="stop")}
    st.coll(ST.LEDGER).docs[plant["_id"]] = plant
    today = {"grades": {t["_id"]: dict(a["same"]), a["_id"]: dict(a["same"], outcome="loss")}, "through_et": "11:11",
             "not_read": []}
    b = LG.served_block(st, D16, NOW, span="5d", is_today=True, today=today)
    base = LG.served_block(ledger_store(), D16, NOW, span="5d", is_today=True, today=today)
    rows = {r["id"]: r for d in b["days"] for r in d["rows"]}
    assert rows[a["_id"]]["same"]["state"] == "win"
    assert rows[t["_id"]]["same"] == {"state": "pending", "text": LG.REPLAY_NOT_GRADED_TEXT, "sub_text": None,
                                      "provisional": False}
    assert b["today_text"] == base["today_text"]
    assert b["counts"]["live"] == base["counts"]["live"] and b["counts_text"] == base["counts_text"]


def test_NEGATIVE_a_lone_ungraded_replayed_row_today_never_raises_the_today_text():
    """Critic fix round 2: a store holding ONLY a 10-16 replayed row with no same grade — the `needs` exclusion is
    the only thing keeping "Today · not read on this open — graded tonight" off the block (no live row needs it)."""
    t = graded_replay_doc("RPT", "bull_flag", D16, next_graded=False)
    t["same"] = None
    st = with_replays(t, st=fake_store())
    for today in (None, {"grades": {}, "through_et": "11:11", "not_read": []}):
        b = LG.served_block(st, D16, NOW, span="today", is_today=True, today=today)
        rows = [r for d in b["days"] for r in d["rows"]]
        assert [r["id"] for r in rows] == [t["_id"]] and rows[0]["line"] == "replayed"
        assert b["today_text"] is None


def _replay_row(**over):
    return LG.alert_of(replay_doc(d=D16, at=et(D16, 10, 35).isoformat(), **over), "aplus")


def test_NEGATIVE_replay_cell_says_bars_not_cached_only_for_a_plan_with_an_alert_time():
    """Critic fix round 2: "not graded (bars not cached)" is said only of a row bars could have graded (plan ok + an
    alert time); a no-risk / no-plan / no-time replayed row reads the live _cell's word."""
    ok = _replay_row()
    assert LG.replay_cell(ok, "same", None, NOW, D16, True) == {"state": "pending", "text": LG.REPLAY_NOT_GRADED_TEXT,
                                                                "sub_text": None, "provisional": False}
    nr = _replay_row(trigger=1.11, stop=1.11)
    assert nr["plan"] == "no_risk"
    for h in GC.LEDGER_HORIZONS:
        c = LG.replay_cell(nr, h, None, NOW, D16, True)
        assert c == LG._cell(nr, h, None, False, NOW, D16, True)
        assert (c["state"], c["text"], c["sub_text"]) == ("no_risk", "no risk", LG.NO_RISK_TEXT)
    np_ = dict(ok, plan="no_plan")
    assert LG.replay_cell(np_, "same", None, NOW, D16, True)["state"] == "no_plan"
    nt = dict(ok, at_utc=None)
    assert LG.replay_cell(nt, "same", None, NOW, D16, True) == {"state": "no_time", "text": LG.NO_TIME_TEXT,
                                                                "sub_text": None, "provisional": False}
    for c in (LG.replay_cell(x, "next", None, NOW, D16, True) for x in (nr, np_, nt)):
        assert c["text"] != LG.REPLAY_NOT_GRADED_TEXT and not c["provisional"]


def test_NEGATIVE_a_served_no_risk_replayed_row_reads_no_risk_never_bars_not_cached():
    doc = replay_doc("RNR", d=D12, at=et(D12, 10, 35).isoformat(), trigger=1.11, stop=1.11)
    b = LG.served_block(with_replays(doc, st=fake_store()), D16, NOW, span="5d", is_today=True, today=None)
    r = {x["symbol"]: x for d in b["days"] for x in d["rows"]}["RNR"]
    assert r["plan_text"] == LG.NO_RISK_TEXT
    assert (r["same"]["state"], r["next"]["state"]) == ("no_risk", "no_risk") and r["bucket"] == "out"
    assert LG.REPLAY_NOT_GRADED_TEXT not in json.dumps(r, ensure_ascii=False)


# ── 3. a replay read fault: the block serves without the line, and says so ─────────────────────────────────────────
@pytest.mark.parametrize("how", ["none", "raises"])
def test_NEGATIVE_a_replay_read_fault_serves_the_block_without_the_line(monkeypatch, how):
    a, b = two_replays()
    st = with_replays(a, b)
    base = LG.served_block(ledger_store(), D16, NOW, span="5d", is_today=True, today=None)
    monkeypatch.setattr(st, "replay_rows", Rec(ret=None) if how == "none" else Rec(exc=RuntimeError("mongo down")))
    out = LG.served_block(st, D16, NOW, span="5d", is_today=True, today=None)
    assert not [r for d in out["days"] for r in d["rows"] if r["line"] == "replayed"]
    assert out["replayed_note"] == LG.REPLAY_FAULT_TEXT and out["replayed_text"] is None
    assert out["counts"] == base["counts"] and out["counts_text"] == base["counts_text"]


def test_NEGATIVE_a_failing_replay_collection_is_the_fault_note():
    good = with_replays(*two_replays())
    st = fake_store(**{n: (FakeColl(fail=True) if n == ST.REPLAY else good.coll(n)) for n in ST.ALL})
    out = LG.served_block(st, D16, NOW, span="all", is_today=True, today=None)
    assert out["replayed_note"] == LG.REPLAY_FAULT_TEXT and out["days"]


class NoReplayStore:
    """A store without the replay methods (an older store): no replayed line, no fault note."""

    def __init__(self, st):
        self._st = st

    def __getattr__(self, name):
        if name in ("replay_rows", "replay_dates"):
            raise AttributeError(name)
        return getattr(self._st, name)


def test_NEGATIVE_a_store_without_the_replay_read_serves_no_line_and_no_note():
    st = NoReplayStore(with_replays(*two_replays()))
    for span in ("5d", "all"):
        out = LG.served_block(st, D16, NOW, span=span, is_today=True, today=None)
        assert out["replayed_note"] is None and out["replayed_text"] is None, span
        assert not [r for d in out["days"] for r in d["rows"] if r["line"] == "replayed"], span


def test_rows_for_default_never_reads_the_replay_source():
    st = with_replays(*two_replays())
    rec = Rec(ret=st.replay_rows)
    st.replay_rows = rec
    rows = LG.rows_for([D12, D16], st)
    assert rec.calls == [] and not [r for r in rows if r["line"] == "replayed"]
    faults = []
    rows = LG.rows_for([D12, D16], st, with_replay=True, faults=faults)
    assert len(rec.calls) == 1 and faults == []
    rep = [r for r in rows if r["line"] == "replayed"]
    assert {r["id"] for r in rep} == {"REPLAY:2026-10-12|RPL|bull_flag", "REPLAY:2026-10-12|RSQ|reversal_squeeze"}
    assert all(set(r["graded"]) == set(GC.LEDGER_HORIZONS) for r in rep)
    assert [r for r in rep if r["symbol"] == "RSQ"][0]["graded"]["next"] is None


# ── 4. the nightly and the on-open read never see a replay doc ─────────────────────────────────────────────────────
def test_NEGATIVE_grade_step_never_reads_loads_or_writes_a_replay_doc(monkeypatch):
    st = ledger_store()
    a = graded_replay_doc("RPL", "bull_flag", D12)
    c = graded_replay_doc("RPX", "bull_flag", date(2026, 10, 15))
    for d in (a, c):
        d["same"] = d["next"] = None                    # ungraded — a grader that saw them would want them
    with_replays(a, c, st=st)
    rows_rec, dates_rec = Rec(ret=st.replay_rows), Rec(ret=st.replay_dates)
    monkeypatch.setattr(st, "replay_rows", rows_rec)
    monkeypatch.setattr(st, "replay_dates", dates_rec)
    seen = []
    out = LG.grade_step(st, _et(D16, 20, 15, 30), load_day=tape_loader(seen), split_lookup=lambda *x: False)
    assert out["read_fault"] is False and out["written"] >= 1
    assert rows_rec.calls == [] and dates_rec.calls == []
    assert not [s for s, _d in seen if s in ("RPL", "RPX")]
    ids = set(st.coll(ST.LEDGER).docs)
    assert not [i for i in ids if str(i).startswith(LG.REPLAY_ID_PREFIX)]
    assert not [d for d in st.coll(ST.LEDGER).docs.values() if d.get("symbol") in ("RPL", "RPX")]
    assert st.coll(ST.REPLAY).docs[a["_id"]]["same"] is None                      # never graded by the nightly
    assert out["rows"] == len(LG.rows_for(out["sessions"], st))


def test_NEGATIVE_today_read_never_reads_nor_loads_a_replay_doc(monkeypatch):
    st = ledger_store()
    t = graded_replay_doc("RPT", "bull_flag", D16, next_graded=False)
    t["same"] = None
    with_replays(t, st=st)
    rec = Rec(ret=st.replay_rows)
    monkeypatch.setattr(st, "replay_rows", rec)
    seen = []
    tr = LG.today_read(NOW, span="5d", store=st, load_frames=tape_loader(seen), split_lookup=no_split)
    assert tr is not None and rec.calls == []
    assert "RPT" not in {s for s, _d in seen} and "RPT" not in tr["not_read"]
    assert not [k for k in tr["grades"] if k.startswith(LG.REPLAY_ID_PREFIX)]


# ── 5. the source filter: each source keeps only its own lines ─────────────────────────────────────────────────────
def test_NEGATIVE_a_replay_doc_planted_in_gajjala_alerts_is_never_a_row(monkeypatch):
    rep = replay_doc("PLT", d=D16, at=et(D16, 10, 35).isoformat())
    assert LG.alert_of(rep, "aplus")["line"] == "replayed"            # the filter is what keeps it out (not vacuous)
    sh = aplus_doc("PMI", "bull_flag", D16, et(D16, 10, 36), 2.40, 2.20, price=2.35)
    st = fake_store(**{ST.ALERTS: FakeColl([rep, sh])})
    ids = [r["id"] for r in LG.rows_for([D16], st, with_replay=True)]
    assert ids == ["2026-10-16|PMI|bull_flag|aplus"]
    monkeypatch.setattr(st, "alert_rows", lambda s: [copy.deepcopy(rep), copy.deepcopy(sh)])
    ids = [r["id"] for r in LG.rows_for([D16], st, with_replay=True)]
    assert ids == ["2026-10-16|PMI|bull_flag|aplus"]                   # even when the alerts read hands it back
    out = LG.served_block(st, D16, NOW, span="today", is_today=True, today=None)
    assert [r["id"] for d in out["days"] for r in d["rows"]] == ["2026-10-16|PMI|bull_flag|aplus"]
    assert out["replayed_text"] is None and out["replayed_note"] is None
    assert all(out["counts"]["replayed"][h]["win"] == 0 for h in GC.LEDGER_HORIZONS)


def test_NEGATIVE_the_replay_source_keeps_only_the_replayed_line(monkeypatch):
    """A shadow / live claim handed back by the replay read is never a row through it."""
    sh = aplus_doc("PMI", "bull_flag", D16, et(D16, 10, 36), 2.40, 2.20, price=2.35)
    live = aplus_doc("TGL", "kiss_fly", D16, et(D16, 10, 46), 5.60, 5.30, state="pushed")
    st = fake_store()
    monkeypatch.setattr(st, "replay_rows", lambda s: [copy.deepcopy(sh), copy.deepcopy(live)])
    assert LG.rows_for([D16], st, with_replay=True) == []
    assert LG.alert_of(sh, "aplus")["line"] == "shadow" and LG.alert_of(live, "aplus")["line"] == "live"


# ── 6. the spans: 10d and all include the replayed sessions, today / yesterday never ───────────────────────────────
def test_the_10d_and_all_spans_include_the_replay_dates_today_and_yesterday_never():
    st = with_replays(graded_replay_doc("RPL", "bull_flag", D12),
                      graded_replay_doc("RPN", "bull_flag", date(2026, 10, 9)),
                      graded_replay_doc("RPO", "bull_flag", date(2026, 10, 2)))
    days = {k: [d["date"] for d in board(st, k)["track_record"]["days"]] for k in GC.LEDGER_SPANS}
    assert days["today"] == ["2026-10-16"] and days["yesterday"] == ["2026-10-15"]      # NEGATIVE
    assert days["5d"] == ["2026-10-16", "2026-10-15", "2026-10-12"]
    assert days["10d"] == ["2026-10-16", "2026-10-15", "2026-10-12", "2026-10-09"]
    assert days["all"] == ["2026-10-16", "2026-10-15", "2026-10-12", "2026-10-09", "2026-10-02"]
    assert date(2026, 10, 2) in LG._sessions_for("all", D16, st)
    for k in ("today", "yesterday"):
        assert board(st, k)["track_record"]["replayed_note"] is None, k


@pytest.mark.parametrize("how", ["raises", "none"])
def test_NEGATIVE_an_unreadable_replay_dates_read_never_breaks_the_all_span(monkeypatch, how):
    st = with_replays(graded_replay_doc("RPO", "bull_flag", date(2026, 10, 2)))
    rec = Rec(exc=RuntimeError("mongo down")) if how == "raises" else Rec(ret=None)
    monkeypatch.setattr(st, "replay_dates", rec)
    out = LG.served_block(st, D16, NOW, span="all", is_today=True, today=None)
    assert "2026-10-02" not in [d["date"] for d in out["days"]] and out["days"]
    assert out["replayed_note"] == LG.REPLAY_FAULT_TEXT and out["replayed_text"] is None   # never folded silently
    assert rec.calls
    faults: list = []
    LG._sessions_for("all", D16, st, faults)
    assert faults == ["replay"]


def test_NEGATIVE_an_empty_replay_dates_answer_is_no_fault(monkeypatch):
    st = ledger_store()
    monkeypatch.setattr(st, "replay_dates", Rec(ret=[]))
    faults: list = []
    LG._sessions_for("all", D16, st, faults)
    assert faults == []
    assert LG.served_block(st, D16, NOW, span="all", is_today=True, today=None)["replayed_note"] is None


# ── 8. the tape: the stored bars5, the doc's grades, the replay note — never a loader ────────────────────────────────
@pytest.fixture
def no_loader(monkeypatch):
    """Every bar path RAISES and is counted: a replayed tape must never call one."""
    from chart_maps.gajjala import tape as TP
    from daytrading import data as dt_data
    recs = {}
    for mod, name in ((dt_data, "load_intraday"), (dt_data, "_mongo_get_day"), (dt_data, "_fetch_massive_minute"),
                      (LG, "_today_load"), (LG, "today_bars"), (LG, "_default_load_day"), (TP, "_completed_day"),
                      (TP, "_cached_day")):
        recs[name] = Rec(exc=AssertionError(f"a replayed tape called {name}"))
        monkeypatch.setattr(mod, name, recs[name])
    return recs


def test_the_tape_serves_a_replayed_rows_stored_bars5_and_never_loads(no_loader):
    from catalysts import promo_tape as PROMO
    from chart_maps.gajjala import tab as GT
    from chart_maps.gajjala import tape as TP
    a = graded_replay_doc("RPL", "bull_flag", D12)
    st = with_replays(a)
    load_day, today_bars = Rec(exc=AssertionError("load_day")), Rec(exc=AssertionError("today_bars"))
    full = TP.entry_tape(a["_id"], now=NOW, store=st, load_day=load_day, today_bars=today_bars)
    assert set(full) == set(TP.PAYLOAD_KEYS) and full["note"] == LG.REPLAY_NOTE and full["lite"] is False
    assert full["bars"] == a["bars5"] and full["n_bars"] == len(a["bars5"]) > 0 and full["ticker"] == "RPL"
    assert [h["label"] for h in full["hlines"]] == [TP.ENTRY_TAPE_WORDS["trigger"].format(px=LG._px(1.23)),
                                                    TP.ENTRY_TAPE_WORDS["stop"].format(px=LG._px(1.11)),
                                                    TP.ENTRY_TAPE_WORDS["target"].format(m=LG._m(), px=LG._px(1.35))]
    assert [(r["key"], r["style"], r["label"]) for r in full["rules"]] == [("alert", "solid", "alert 10:35 ET"),
                                                                           ("fill", "dashed", "fill 10:40")]
    assert [(x["key"], x["tone"], x["label"]) for x in full["dots"]] == [
        ("fill", "fill", f"fill {LG._px(1.23)} at 10:40"), ("exit", "target", f"+{LG._m()}R 10:41")]
    assert full["tone"] == "up"
    session, is_today, _ = GT.session_for(NOW)
    row = {r["id"]: r for d in LG.served_block(st, session, NOW, span="5d", is_today=is_today)["days"]
           for r in d["rows"]}[a["_id"]]
    heads = dict(LG.HEADS)
    txt = lambda c: c["text"] + (" · " + c["sub_text"] if c.get("sub_text") else "")      # noqa: E731
    assert full["read"] == TP.ENTRY_TAPE_WORDS["read"].format(same_head=heads["same"], same=txt(row["same"]),
                                                              next_head=heads["next"], next=txt(row["next"]))
    lite = TP.entry_tape(a["_id"], lite=True, now=NOW, store=st, load_day=load_day, today_bars=today_bars)
    assert set(lite) == set(TP.LITE_KEYS) and lite["note"] == LG.REPLAY_NOTE
    assert lite["bars"] == PROMO.lite_payload({"bars": full["bars"]}, stride=PROMO.LITE_STRIDE)["bars"]
    assert load_day.calls == [] and today_bars.calls == []                       # NEGATIVE: never called
    assert all(r.calls == [] for r in no_loader.values())


def test_NEGATIVE_a_replayed_tape_with_a_null_next_column_says_not_graded(no_loader):
    from chart_maps.gajjala import tape as TP
    _a, b = two_replays()
    p = TP.entry_tape(b["_id"], now=NOW, store=with_replays(b))
    assert p["note"] == LG.REPLAY_NOTE and p["read"].endswith(LG.REPLAY_NOT_GRADED_TEXT)
    assert [x["tone"] for x in p["dots"]] == ["fill", "stop"]
    assert [d["label"] for d in p["dots"]][1] == TP.ENTRY_TAPE_WORDS["exit_stop"].format(hhmm="10:41")
    assert all(r.calls == [] for r in no_loader.values())


def _split_replay(col: str) -> dict:
    """SYNTHETIC: the RPL replay with a split cell on file in `col`; the 10-13 bars print x10 (a post-split tape)."""
    a = graded_replay_doc("RPL", "bull_flag", D12)
    a[col] = dict(LG._blank(col), reason="split", split_on="2026-10-13")
    a["bars5"] = [dict(b, **{k: (b[k] * 10 if b.get(k) is not None else None) for k in "ohlc"})
                  if _et_day(b["t"]) == D13 else b for b in a["bars5"]]
    return a


def _et_day(ms: int) -> date:
    from datetime import timezone
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).astimezone(ET).date()


@pytest.mark.parametrize("col", ["next", "same"])
def test_NEGATIVE_a_replayed_tape_with_a_split_on_file_draws_no_levels(no_loader, col):
    """AMENDMENTS11 F9 on the ⏪ tape: the stored bars5 spans the split, so the as-printed levels are never drawn — and
    the note SAYS why in the replay's own word (A7), never the live word "the bars are adjusted" (NEGATIVE)."""
    from chart_maps.gajjala import tape as TP
    a = _split_replay(col)
    assert any(_et_day(b["t"]) == D13 for b in a["bars5"]) and a["bars5"][-1]["c"] > 10
    p = TP.entry_tape(a["_id"], now=NOW, store=with_replays(a))
    assert p["hlines"] == [] and p["dots"] == [] and p["tone"] is None
    assert p["note"] == TP.ENTRY_TAPE_WORDS["split_replayed"] + " " + LG.REPLAY_NOTE and p["bars"] == a["bars5"]
    assert "adjusted" not in p["note"] and p["note"] != TP.ENTRY_TAPE_WORDS["split"]
    assert "levels are not drawn" in p["note"] and p["note"].endswith(LG.REPLAY_NOTE)
    assert all(r.calls == [] for r in no_loader.values())
    TP._MEMO.clear()                                                             # the control reads afresh
    ctl = TP.entry_tape(a["_id"], now=NOW, store=with_replays(graded_replay_doc("RPL", "bull_flag", D12)))
    assert ctl["hlines"] and ctl["dots"] and ctl["tone"] == "up"                # the control: no split → drawn


@pytest.mark.parametrize("rid", ["REPLAY:2026-10-12|ZZZ|bull_flag", "REPLAY:2026-10-12|RPL|kiss_fly",
                                 "REPLAY:2026-10-09|RPL|bull_flag", "REPLAY:2026-10-12|RPL|bull_flag#x",
                                 "REPLAY:2026-10-12|rpl|bull_flag", "REPLAY:2026-10-12|RPL", "REPLAY:2026-13-01|RPL|x",
                                 "SHADOW:REPLAY:2026-10-12|RPL|bull_flag", "REPLAY:"])
def test_NEGATIVE_an_unknown_or_malformed_replay_id_is_404(no_loader, monkeypatch, rid):
    from chart_maps import api as API
    from chart_maps.gajjala import tape as TP
    st = with_replays(graded_replay_doc("RPL", "bull_flag", D12))
    assert TP.entry_tape(rid, now=NOW, store=st) is None, rid
    monkeypatch.setattr(ST, "default", lambda: st)
    resp = run_route(API.chart_maps_gajjala_entry_tape(id=rid, lite=0))
    assert resp.status_code == 404 and json.loads(resp.body) == {"detail": TP.ENTRY_TAPE_WORDS["not_found"]}, rid
    assert all(r.calls == [] for r in no_loader.values())


def test_NEGATIVE_a_replay_doc_only_in_gajjala_alerts_has_no_tape(no_loader):
    from chart_maps.gajjala import tape as TP
    rep = graded_replay_doc("RPL", "bull_flag", D12)
    st = fake_store(**{ST.ALERTS: FakeColl([rep])})
    assert TP.entry_tape(rep["_id"], now=NOW, store=st) is None


def test_NEGATIVE_an_unreadable_replay_read_is_the_fault_note_never_memoised(no_loader, monkeypatch):
    from chart_maps.gajjala import tape as TP
    a = graded_replay_doc("RPL", "bull_flag", D12)
    st = with_replays(a)
    monkeypatch.setattr(st, "replay_rows", Rec(ret=None))
    p = TP.entry_tape(a["_id"], now=NOW, store=st)
    assert p["note"] == TP.ENTRY_TAPE_WORDS["fault"] and p["bars"] == [] and p["ticker"] == "RPL"
    assert not TP._MEMO
    monkeypatch.setattr(st, "replay_rows", Rec(exc=RuntimeError("mongo down")))
    assert TP.entry_tape(a["_id"], now=NOW, store=st)["note"] == TP.ENTRY_TAPE_WORDS["fault"]


def test_the_route_serves_a_replayed_tape(no_loader, monkeypatch):
    from chart_maps import api as API
    from chart_maps.gajjala import tape as TP
    a = graded_replay_doc("RPL", "bull_flag", D12)
    st = with_replays(a)
    monkeypatch.setattr(ST, "default", lambda: st)
    body = json.loads(run_route(API.chart_maps_gajjala_entry_tape(id=a["_id"], lite=1)).body)
    assert set(body) == set(TP.LITE_KEYS) and body["note"] == LG.REPLAY_NOTE and body["n_bars"] > 0
    assert all(r.calls == [] for r in no_loader.values())


def test_stored_bars5_are_validated_and_capped(no_loader, monkeypatch):
    from chart_maps.gajjala import tape as TP
    a = graded_replay_doc("RPL", "bull_flag", D12)
    good = a["bars5"][:4]
    a["bars5"] = [good[2], {"t": True, "c": 1.0}, {"t": 5, "c": None}, {"t": "x", "c": 1.0}, "junk", None,
                  dict(good[0], c=float("nan")), good[1], dict(good[3], s=7, v="x")]
    st = with_replays(a)
    p = TP.entry_tape(a["_id"], now=NOW, store=st)
    assert [b["t"] for b in p["bars"]] == [good[1]["t"], good[2]["t"], good[3]["t"]]       # ascending, junk dropped
    assert p["bars"][-1]["s"] is None and p["bars"][-1]["v"] is None
    TP._MEMO.clear()
    monkeypatch.setattr(GC, "LEDGER_TAPE_BARS_MAX", 2)
    assert TP.entry_tape(a["_id"], now=NOW, store=st)["n_bars"] == 2


def test_replay_ref_reads_only_the_replay_id_shape():
    from chart_maps.gajjala import tape as TP
    assert TP.replay_ref("REPLAY:2026-10-12|RPL|bull_flag") == (D12, "RPL", "bull_flag")
    for bad in ("REPLAY:2026-10-12|RPL|bull_flag#x", "REPLAY:2026-10-12|rpl|bull_flag", "REPLAY:2026-10-12|RPL",
                "REPLAY:2026-10-12|RPL|bull_flag|aplus", "2026-10-12|RPL|bull_flag|aplus", "SHADOW:REPLAY:x", None, 5,
                "REPLAY:2026-10-12| |bull_flag", "REPLAY:2026-10-12|RPL| "):
        assert TP.replay_ref(bad) is None, bad
    assert TP.parse_id("REPLAY:2026-10-12|RPL|bull_flag") is None                 # the ledger-id reader is unchanged
