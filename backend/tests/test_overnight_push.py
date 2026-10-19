"""🌙 overnight/push.py — the one morning push off the overnight session read (BUILD_SPEC16 §3.6, WP-B, 2026-10-19).

Ajay 2026-10-19 (verbatim): "Can you do an over night scan for all the stocks they are all growing over night".

Ships OFF (AMENDMENTS16 A2). The pass still runs at 06:45 ET on trading days: the gate (up overnight, >= the $2
house floor, >= PUSH_MIN_ON_DOLLAR traded overnight, not leveraged / inverse, unknown leverage fail-closed), one claim
per trade date, the read of the session that ended 04:00 ET. WP-A's overnight.scan is stubbed (`load=` injection;
a stub module only when the real one is not importable yet) — these tests never touch Mongo or the network.
"""
from __future__ import annotations

import json
import re
import sys
import types
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pymongo.errors import DuplicateKeyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_hours import gate                    # noqa: E402
from overnight import push as OP                 # noqa: E402
from push import sender, subs                    # noqa: E402

ET = ZoneInfo("America/New_York")
TD = "2026-10-19"                                # Monday; the session Sun 10-18 20:00 → Mon 04:00
SLOT = datetime(2026, 10, 19, 6, 45, tzinfo=ET)


@pytest.fixture(autouse=True)
def no_override(monkeypatch):
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)


@pytest.fixture(autouse=True)
def scan_mod(monkeypatch):
    """The real overnight.scan when WP-A has landed; else a stub carrying only the §3.2 REF_SYMBOLS, and a
    load_latest that refuses (every test injects `load=`)."""
    try:
        from overnight import scan as S
        return S
    except Exception:
        stub = types.ModuleType("overnight.scan")
        stub.REF_SYMBOLS = ("SPY", "QQQ", "IWM", "DIA")

        def _refuse(*a, **k):
            raise AssertionError("load_latest must be injected in these tests")
        stub.load_latest = _refuse
        monkeypatch.setitem(sys.modules, "overnight.scan", stub)
        import overnight
        monkeypatch.setattr(overnight, "scan", stub, raising=False)
        return stub


def row(sym, pct, *, price=10.0, on_dollar=1_000_000.0, lev=False, src="t", prior=-1.25):
    return {"symbol": sym, "name": f"{sym} Inc", "type": "CS", "pct": pct, "price": price, "src": src,
            "on_dollar": on_dollar, "prior_pct": prior, "leveraged": lev, "lev_label": None}


def read_doc(rows, *, td=TD, refs=None):
    if refs is None:
        refs = [{"symbol": "SPY", "pct": 0.12}, {"symbol": "QQQ", "pct": 0.25}, {"symbol": "IWM", "pct": -0.1}]
    return {"_id": f"{td}T0350", "trade_date": td, "base_date": "2026-10-16", "as_of": f"{td}T03:50:00-04:00",
            "as_of_et": "Mon 3:50 ET", "refs": refs, "rows": rows}


EIGHT = [row(f"A{c}", 10.0 - i) for i, c in enumerate("ABCDEFGH")]     # AA +10 … AH +3


class ClaimColl:
    def __init__(self):
        self.docs = {}
        self.updates = []

    def insert_one(self, doc):
        if doc["_id"] in self.docs:
            raise DuplicateKeyError("E11000 duplicate key")
        self.docs[doc["_id"]] = dict(doc)

    def update_one(self, q, upd):
        self.updates.append((q, upd))
        self.docs[q["_id"]].update(upd["$set"])


class PassColl:
    def __init__(self):
        self.docs = {}

    def find_one(self, q):
        return self.docs.get(q["_id"])

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)


class Spy:
    def __init__(self, res=None):
        self.calls = []
        self.res = res if res is not None else {"sent": 0, "failed": 0, "total_targets": 0}

    def __call__(self, *, owner, payload):
        self.calls.append((owner, payload))
        return self.res


def run(read, now=SLOT, **kw):
    kw.setdefault("claim_coll", ClaimColl())
    kw.setdefault("pass_coll", PassColl())
    kw.setdefault("send", Spy())
    return OP.run_pass(now, load=(lambda td: read), **kw), kw


# ── gate ─────────────────────────────────────────────────────────────────────
def test_gate_top_by_pct_desc_tie_by_symbol():
    rows = [row("ZZZ", 4.0), row("AAA", 4.0), row("MMM", 9.5), row("BBB", 1.0)]
    passed, counts = OP.gate_rows(rows)
    assert [r["symbol"] for r in passed] == ["MMM", "AAA", "ZZZ", "BBB"]
    assert counts["candidates"] == 4 and counts["passed"] == 4


@pytest.mark.parametrize("bad, key", [
    (row("LOW", 5.0, price=1.99), "skipped_price"),
    (row("THN", 5.0, on_dollar=249_999.0), "skipped_thin"),
    (row("LEV", 5.0, lev=True), "skipped_leveraged"),
    (row("UNK", 5.0, lev=None), "skipped_lev_unknown"),
    (row("FLT", 0.0), "skipped_not_up"),
    (row("DWN", -3.0), "skipped_not_up"),
    (row("NAN", float("nan")), "skipped_not_up"),
    (row("NOP", 5.0, price=None), "skipped_price"),
])
def test_NEGATIVE_each_gate_drops_and_counts(bad, key):
    passed, counts = OP.gate_rows([bad, row("OKK", 2.0)])
    assert [r["symbol"] for r in passed] == ["OKK"]
    assert counts[key] == 1
    assert sum(v for k, v in counts.items() if k.startswith("skipped_")) == 1


def test_the_floors_are_inclusive_at_the_constant():
    passed, _ = OP.gate_rows([row("EDG", 1.0, price=OP.PUSH_MIN_PRICE, on_dollar=OP.PUSH_MIN_ON_DOLLAR)])
    assert [r["symbol"] for r in passed] == ["EDG"]


def test_NEGATIVE_a_leveraged_string_is_never_read_as_false():
    passed, counts = OP.gate_rows([row("STR", 5.0, lev="false"), row("ZER", 5.0, lev=0)])
    assert passed == [] and counts["skipped_lev_unknown"] == 2


# ── window ───────────────────────────────────────────────────────────────────
def test_window_open_at_the_slot():
    assert OP.window_reason(SLOT) is None
    assert OP.window_reason(datetime(2026, 10, 19, 9, 29, tzinfo=ET)) is None


@pytest.mark.parametrize("now, why", [
    (datetime(2026, 10, 19, 6, 44, tzinfo=ET), "before 06:45 ET"),
    (datetime(2026, 10, 19, 9, 30, tzinfo=ET), "the regular session opened at 9:30 ET"),
    (datetime(2026, 10, 19, 20, 0, tzinfo=ET), "the regular session opened at 9:30 ET"),
    (datetime(2026, 10, 19, 23, 59, tzinfo=ET), "the regular session opened at 9:30 ET"),
    (datetime(2026, 10, 20, 2, 0, tzinfo=ET), "before 06:45 ET"),
    (datetime(2026, 10, 17, 6, 45, tzinfo=ET), "weekend"),
    (datetime(2026, 9, 7, 6, 45, tzinfo=ET), "holiday 2026-09-07"),
])
def test_NEGATIVE_outside_the_window(now, why):
    assert OP.window_reason(now) == why
    res, kw = run(read_doc(EIGHT), now=now)
    assert res["ran"] is False and res["reason"] == why
    assert kw["send"].calls == [] and kw["claim_coll"].docs == {} and kw["pass_coll"].docs == {}


def test_the_open_cut_is_daytrading_data_ET_RTH_OPEN_by_name(monkeypatch):
    """MUTATION GUARD: the 9:30 cut is read from the constant, never retyped."""
    from datetime import time as dtime
    from daytrading import data as DD
    assert DD.ET_RTH_OPEN == dtime(9, 30)
    monkeypatch.setattr(DD, "ET_RTH_OPEN", dtime(8, 0))
    assert OP.window_reason(datetime(2026, 10, 19, 8, 0, tzinfo=ET)) == "the regular session opened at 8:00 ET"
    src = (Path(__file__).resolve().parents[1] / "overnight" / "push.py").read_text()
    assert not re.search(r"boun", src, re.I), "NEGATIVE: the contracts ban the b-word in the new backend files"


def test_a_naive_clock_is_the_et_wall_clock():
    assert OP.window_reason(datetime(2026, 10, 19, 6, 45)) is None
    assert OP.window_reason(datetime(2026, 10, 19, 6, 44)) == "before 06:45 ET"


def test_moving_the_slot_moves_the_window(monkeypatch):
    monkeypatch.setattr(OP, "SLOT_ET", "07:00")
    assert OP.window_reason(SLOT) == "before 07:00 ET"


# ── the pass ─────────────────────────────────────────────────────────────────
def test_the_pass_claims_sends_and_records(monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", "owner@example.com")
    res, kw = run(read_doc(EIGHT))
    assert res["ran"] is True and "reason" not in res and res["state"] == "no_target"
    (owner, payload), = kw["send"].calls
    assert owner == "owner@example.com" and payload["kind"] == OP.KIND
    claim = kw["claim_coll"].docs[TD]
    assert claim["state"] == "no_target" and claim["read_id"] == f"{TD}T0350"
    assert claim["names"] == [f"A{c}" for c in "ABCDEFGH"]
    assert claim["result"] == {"sent": 0, "failed": 0, "total_targets": 0}
    assert res["candidates"] == 8 and res["passed"] == 8 and res["pushed"] == 0 and res["no_target"] == 1


@pytest.mark.parametrize("sres, state, pushed, no_target", [
    ({"sent": 1, "failed": 0, "total_targets": 1}, "pushed", 1, 0),
    ({"sent": 0, "failed": 0, "total_targets": 0}, "no_target", 0, 1),
    ({"sent": 0, "failed": 2, "total_targets": 2}, "failed", 0, 0),
])
def test_claim_state_follows_the_send_result(sres, state, pushed, no_target):
    res, kw = run(read_doc(EIGHT), send=Spy(sres))
    assert kw["claim_coll"].docs[TD]["state"] == state
    assert (res["pushed"], res["no_target"]) == (pushed, no_target)
    assert (res.get("reason") == "send failed") is (state == "failed")


def test_NEGATIVE_a_raising_send_is_a_failed_claim_never_a_crash():
    def boom(*, owner, payload):
        raise RuntimeError("webpush down")
    res, kw = run(read_doc(EIGHT), send=boom)
    assert res["state"] == "failed" and kw["claim_coll"].docs[TD]["state"] == "failed"


def test_NEGATIVE_second_run_same_session_is_already_pushed_no_send():
    cc, pc = ClaimColl(), PassColl()
    run(read_doc(EIGHT), claim_coll=cc, pass_coll=pc)
    first = dict(pc.docs[OP.KIND])
    spy = Spy()
    res, _ = run(read_doc(EIGHT), claim_coll=cc, pass_coll=pc, send=spy)
    assert res["reason"] == f"already pushed for the {TD} session"
    assert spy.calls == []
    assert pc.docs[OP.KIND] == first, "the dedupe never overwrites the morning's recorded pass"


def test_NEGATIVE_no_read_for_today_no_send_reason_recorded():
    res, kw = run(None)
    assert res["reason"] == f"no overnight read stored for the {TD} session"
    assert kw["send"].calls == [] and kw["claim_coll"].docs == {}
    assert kw["pass_coll"].docs[OP.KIND]["reason"] == res["reason"]


def test_NEGATIVE_yesterdays_read_is_never_pushed_as_today():
    res, kw = run(read_doc(EIGHT, td="2026-10-16"))
    assert res["reason"] == f"the latest overnight read is for the 2026-10-16 session, not {TD}"
    assert kw["send"].calls == [] and kw["claim_coll"].docs == {}


def test_NEGATIVE_the_loader_is_asked_for_todays_trade_date():
    asked = []
    OP.run_pass(SLOT, load=lambda td: asked.append(td) or None, claim_coll=ClaimColl(), pass_coll=PassColl(),
                send=Spy())
    assert asked == [TD]


def test_NEGATIVE_zero_passed_no_send_reason_and_counts_recorded():
    rows = [row("LEV", 9.0, lev=True), row("THN", 8.0, on_dollar=10_000.0), row("DWN", -2.0)]
    pc = PassColl()
    res, kw = run(read_doc(rows), pass_coll=pc)
    assert res["reason"] == "no name passed the gate"
    assert kw["send"].calls == [] and kw["claim_coll"].docs == {}
    doc = pc.docs[OP.KIND]
    assert doc["reason"] == "no name passed the gate" and doc["date"] == TD
    assert doc["counts"] == {"candidates": 3, "passed": 0, "pushed": 0, "skipped_price": 0, "skipped_thin": 1,
                             "skipped_leveraged": 1, "skipped_lev_unknown": 0, "skipped_not_up": 1, "no_target": 0}


def test_record_result_writes_the_counts_and_nothing_else():
    pc = PassColl()
    run(read_doc(EIGHT + [row("LEV", 20.0, lev=True)]), pass_coll=pc)
    doc = pc.docs[OP.KIND]
    assert set(doc["counts"]) == set(OP.COUNT_KEYS)
    assert doc["counts"]["skipped_leveraged"] == 1 and doc["counts"]["no_target"] == 1
    assert "reason" not in doc
    json.dumps(doc, allow_nan=False)


def test_NEGATIVE_no_claim_store_never_sends():
    res, kw = run(read_doc(EIGHT), claim_coll=None)       # tests: _get_db() is None
    assert res["reason"] == "claim store unreachable — not sent" and kw["send"].calls == []


def test_dry_run_composes_sends_claims_and_records_nothing():
    res, kw = run(read_doc(EIGHT), dry_run=True)
    assert res["dry_run"] is True and res["payload"]["kind"] == OP.KIND
    assert kw["send"].calls == [] and kw["claim_coll"].docs == {} and kw["pass_coll"].docs == {}


def test_the_default_send_is_the_hook_to_the_owner_under_the_kind(monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", "owner@example.com")
    calls = []
    monkeypatch.setattr(sender, "send_to_user",
                        lambda email, payload, kind=None: calls.append((email, kind)) or
                        {"sent": 0, "failed": 0, "total_targets": 0})
    OP.run_pass(SLOT, load=lambda td: read_doc(EIGHT), claim_coll=ClaimColl(), pass_coll=PassColl())
    assert calls == [("owner@example.com", OP.KIND)]
    assert subs._owner_email() == "owner@example.com"


# ── payload ──────────────────────────────────────────────────────────────────
def _payload(rows=EIGHT, **kw):
    passed, _ = OP.gate_rows(rows)
    return OP.compose(read_doc(rows, **kw), passed)


def test_payload_title_index_line_five_names_more_and_the_tail(scan_mod):
    p = _payload()
    assert p["kind"] == OP.KIND and p["url"] == OP.URL and p["tag"] == f"overnight_movers:{TD}"
    assert p["ticker"] is None
    assert p["title"] == "🌙 Overnight movers — AA +10.0%, AB +9.0%, AC +8.0% +5 more"
    lines = p["body"].split("\n")
    assert lines[0] == "SPY +0.12% · QQQ +0.25% · IWM -0.10% · DIA — · vs Fri 10-16 close · read Mon 3:50 ET"
    assert [ln.split(" ")[0] for ln in lines[0].split(" · ")[:len(scan_mod.REF_SYMBOLS)]] == list(scan_mod.REF_SYMBOLS)
    assert lines[1] == "AA +10.0% · $10.00 · $1.0M overnight · prior session -1.2% · delayed indicative trade"
    assert len(lines) == 1 + OP.PUSH_TOP_N + 2
    assert lines[6] == "+3 more on the board"
    assert lines[-1] == "UNMEASURED — what moved overnight, not what to buy. Not advice."
    assert p["tickers"] == ["AA", "AB", "AC", "AD", "AE"]
    assert [i["symbol"] for i in p["items"]] == [f"A{c}" for c in "ABCDEFGH"]
    assert p["items"][0]["text"] == lines[1]


def test_a_quote_priced_name_is_marked_q_and_prior_unknown_is_a_dash():
    p = _payload([row("QQQX", 3.0, src="q", prior=None, on_dollar=2_500_000.0, price=1234.5)])
    lines = p["body"].split("\n")
    assert lines[1] == "QQQX +3.0% · $1,234.50 · $2.5M overnight · prior session — · q"
    assert p["title"] == "🌙 Overnight movers — QQQX +3.0%"
    assert "more on the board" not in p["body"]


def test_NEGATIVE_three_or_fewer_never_say_more():
    p = _payload(EIGHT[:3])
    assert "more" not in p["title"] and "more on the board" not in p["body"]
    assert len(p["body"].split("\n")) == 1 + 3 + 1


def test_items_capped_at_items_max():
    rows = [row(f"N{i:02d}", 50.0 - i) for i in range(OP.ITEMS_MAX + 6)]
    p = _payload(rows)
    assert len(p["items"]) == OP.ITEMS_MAX and len(p["tickers"]) == OP.PUSH_TOP_N
    assert f"+{len(rows) - OP.PUSH_TOP_N} more on the board" in p["body"]


def test_NEGATIVE_missing_refs_print_a_dash_never_a_zero():
    p = _payload(refs=[])
    assert p["body"].split("\n")[0].startswith("SPY — · QQQ — · IWM — · DIA —")


def test_NEGATIVE_no_banned_words_and_the_payload_is_strict_json():
    p = _payload()
    txt = " ".join([p["title"], p["body"]] + [i["text"] for i in p["items"]])
    assert not re.search(r"boun|fak", txt, re.I)
    json.dumps(p, allow_nan=False)


def test_NEGATIVE_items_are_log_only_never_sent_to_a_device():
    p = _payload()
    assert "items" not in sender.device_payload(p) and "items" in p


@pytest.mark.skipif(not (Path(__file__).resolve().parents[1] / "overnight" / "scan.py").exists(),
                    reason="WP-A overnight/scan.py not landed yet")
def test_ref_symbols_are_the_scans_own():
    from overnight import scan as S
    assert OP._ref_symbols() == tuple(S.REF_SYMBOLS)


def test_main_dry_run_prints_json_and_exits_0(monkeypatch, capsys):
    monkeypatch.setattr(OP, "run_pass", lambda now=None, **kw: {"kind": OP.KIND, "ran": False,
                                                                 "reason": "weekend", "dry_run": kw["dry_run"]})
    assert OP.main(["--dry-run", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True and out["reason"] == "weekend"
