"""chart_maps/gajjala/context.py — the context reads around the five detectors (spec §3.1.5; WP2, 2026-10-13).

Float chain (C7, HIS CALL 28) · rotation · ⏸ halts · 🧱 psych levels · red closes · 🎾 squeeze history ·
☀️ K9 premarket list · 🌙 K10 post-market confirm. Every fetcher is injected (tests/conftest.py refuses network and
Mongo); the store is the in-memory `fake_store`. Edge fixtures are built with the module's own expressions.
"""
from __future__ import annotations

import ast
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import context as CX
from chart_maps.gajjala import detectors as DT
from tests.test_gajjala_store import fake_store

ET = ZoneInfo("America/New_York")
S = date(2026, 10, 13)
NOW = datetime(2026, 10, 13, 14, 1, tzinfo=timezone.utc)


# ── fakes ─────────────────────────────────────────────────────────────────────────────────────────────────────────
class Yahoo:
    """`volume_movers.shares_status` stand-in: `cache` answers fetch=False, `answers` answer fetch=True."""

    def __init__(self, cache=None, answers=None):
        self.cache = dict(cache or {})
        self.answers = dict(answers or {})
        self.fetched: list = []

    def __call__(self, sym, *, fetch=True):
        if not fetch:
            return self.cache.get(sym, (None, "missing"))
        self.fetched.append(sym)
        return self.answers.get(sym, ({"float_shares": 5_000_000, "shares_outstanding": 6_000_000}, "fetched"))


class Massive:
    def __init__(self, shares=None):
        self.shares = dict(shares or {})
        self.calls: list = []

    def __call__(self, sym):
        self.calls.append(sym)
        return self.shares.get(sym)


def _floats(syms, yahoo, massive=None, **kw):
    kw.setdefault("now", NOW)
    kw.setdefault("sleep", lambda s: None)
    return CX.floats_for(syms, status_lookup=yahoo, massive_lookup=massive or Massive(), **kw)


# ── float chain ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_fresh_yfinance_float_reads_float():
    y = Yahoo(cache={"AAA": ({"float_shares": 3_100_000, "shares_outstanding": 8_100_000}, "cached")})
    r = _floats(["AAA"], y, refine=False)["AAA"]
    assert (r["shares"], r["src"], r["text"]) == (3_100_000, "float", "Float 3.1M")
    assert r["suspect"] is None


def test_yfinance_shares_out_only_reads_shares_out():
    y = Yahoo(cache={"AAA": ({"float_shares": None, "shares_outstanding": 8_100_000}, "cached")})
    r = _floats(["AAA"], y, refine=False)["AAA"]
    assert (r["src"], r["text"]) == ("shares_out_yf", "shares out 8.1M")


def test_NEGATIVE_yahoo_row_missing_uses_massive_without_any_yahoo_call():
    y, m = Yahoo(), Massive({"AAA": 8_100_000})
    r = _floats(["AAA"], y, m, refine=False)["AAA"]
    assert (r["shares"], r["src"], r["text"]) == (8_100_000, "shares_out_massive", "shares out 8.1M (Massive)")
    assert y.fetched == [] and m.calls == ["AAA"]


def test_NEGATIVE_all_three_none_is_float_unknown():
    y = Yahoo(answers={"AAA": (None, "no_data")})
    r = _floats(["AAA"], y, Massive())["AAA"]
    assert r["shares"] is None and r["src"] is None and r["text"] == "float unknown"
    assert y.fetched == ["AAA"]


def test_massive_called_once_per_session_and_symbol_across_passes():
    st, m = fake_store(), Massive({"AAA": 8_100_000})
    for k in range(3):
        _floats(["AAA"], Yahoo(), m, refine=False, store=st, session=S, now=NOW + timedelta(minutes=5 * k))
    assert m.calls == ["AAA"]
    _floats(["AAA"], Yahoo(), m, refine=False, store=st, session=S + timedelta(days=1))
    assert m.calls == ["AAA", "AAA"], "a new session asks again"


def test_massive_none_is_remembered_too():
    st, m = fake_store(), Massive()
    _floats(["AAA"], Yahoo(), m, refine=False, store=st, session=S)
    r = _floats(["AAA"], Yahoo(), m, refine=False, store=st, session=S)["AAA"]
    assert m.calls == ["AAA"] and r["text"] == "float unknown"


def test_priority_squeeze_alive_name_is_fetched_before_a_300pct_name_without_structure():
    y = Yahoo()
    prio = {"BIG": {"structure_alive": False, "change_pct": 300.0}, "TB": {"structure_alive": True, "change_pct": 40.0}}
    _floats(["BIG", "TB"], y, priority=prio, max_new=1)
    assert y.fetched == ["TB"]


def test_priority_alive_with_massive_above_10m_still_comes_first():
    y, m = Yahoo(), Massive({"TB": GC.K8_MAX_FLOAT + 1, "LOW": GC.K8_MAX_FLOAT})
    prio = {"BIG": {"change_pct": 300.0}, "LOW": {"structure_alive": True, "change_pct": 90.0},
            "TB": {"structure_alive": True, "change_pct": 40.0}}
    _floats(["BIG", "LOW", "TB"], y, m, priority=prio)
    assert y.fetched == ["TB", "BIG", "LOW"], "alive + could-admit first; the rest by change desc"


def test_NEGATIVE_the_ninth_uncached_name_is_not_fetched_this_pass():
    syms = [f"S{i}" for i in range(GC.FLOAT_MAX_NEW_PER_PASS + 1)]
    prio = {s: {"change_pct": 100.0 - i} for i, s in enumerate(syms)}
    y = Yahoo()
    reads = _floats(syms, y, priority=prio)
    assert y.fetched == syms[:GC.FLOAT_MAX_NEW_PER_PASS]
    assert reads[syms[-1]]["refined"] is False and reads[syms[0]]["refined"] is True


def test_NEGATIVE_cached_and_tombstoned_names_are_never_refetched():
    y = Yahoo(cache={"OK": ({"float_shares": 1_000_000}, "cached"), "ETF": (None, "tombstone"),
                     "RL": (None, "rl_marker")})
    _floats(["OK", "ETF", "RL"], y)
    assert y.fetched == []


def test_yahoo_paced_at_the_house_interval():
    sleeps: list = []
    _floats(["A", "B", "C"], Yahoo(), sleep=sleeps.append)
    assert sleeps == [CX.FLOAT_FETCH_INTERVAL_SEC] * 2
    assert CX.FLOAT_FETCH_INTERVAL_SEC == 1.0 and CX.FLOAT_BACKOFF_MAX_SEC == 900.0
    assert CX.FLOAT_BACKOFF_START_SEC == GC.PASS_CADENCE_SEC == 300


def test_429_backoff_300_then_600_then_900_cap_and_a_success_resets():
    st = fake_store()
    limited = Yahoo(answers={"AAA": (None, "rate_limited")})
    t0 = NOW
    _floats(["AAA"], limited, store=st, session=S, now=t0)
    s1 = st.get_state(CX.FLOAT_STATE_ID)
    assert s1["n"] == 1 and s1["until"] == t0.timestamp() + 300
    # next pass (inside the back-off): Yahoo skipped entirely
    skip = Yahoo(answers={"AAA": (None, "rate_limited")})
    state: dict = {}
    state.update({k: st.get_state(CX.FLOAT_STATE_ID)[k] for k in ("until", "n")})
    _floats(["AAA"], skip, store=st, session=S, now=t0 + timedelta(seconds=299), state=state)
    assert skip.fetched == [] and state["yahoo"]["skipped_backoff"] is True
    t2 = t0 + timedelta(seconds=301)
    _floats(["AAA"], limited, store=st, session=S, now=t2)
    s2 = st.get_state(CX.FLOAT_STATE_ID)
    assert s2["n"] == 2 and s2["until"] == t2.timestamp() + 600
    t3 = t2 + timedelta(seconds=601)
    _floats(["AAA"], limited, store=st, session=S, now=t3)
    s3 = st.get_state(CX.FLOAT_STATE_ID)
    assert s3["n"] == 3 and s3["until"] == t3.timestamp() + 900
    t4 = t3 + timedelta(seconds=901)
    _floats(["AAA"], limited, store=st, session=S, now=t4)
    assert st.get_state(CX.FLOAT_STATE_ID)["until"] == t4.timestamp() + 900, "capped at BACKOFF_MAX_SEC"
    t5 = t4 + timedelta(seconds=901)
    _floats(["AAA"], Yahoo(), store=st, session=S, now=t5)
    assert st.get_state(CX.FLOAT_STATE_ID)["n"] == 0


def test_a_429_stops_the_yahoo_step_at_once():
    y = Yahoo(answers={"A": (None, "rate_limited")})
    _floats(["A", "B", "C"], y, priority={"A": {"change_pct": 9}, "B": {"change_pct": 5}, "C": {"change_pct": 1}})
    assert y.fetched == ["A"]


def test_NEGATIVE_massive_still_runs_during_a_yahoo_backoff():
    y, m = Yahoo(), Massive({"AAA": 4_000_000})
    state = {"until": NOW.timestamp() + 120, "n": 1}
    r = _floats(["AAA"], y, m, state=state)["AAA"]
    assert y.fetched == [] and m.calls == ["AAA"] and r["src"] == "shares_out_massive"


# FCHL 2026-10-13 (trap T10): float on file 1,314,047 > shares out 1,299,391
FCHL = {"float_shares": 1_314_047, "shares_outstanding": 1_299_391}


def test_float_above_shares_out_ineligible_policy_flags_and_the_squeeze_gate_reads_unknown(monkeypatch):
    monkeypatch.setattr(GC, "FLOAT_SUSPECT_POLICY", "ineligible")
    r = _floats(["FCHL"], Yahoo(cache={"FCHL": (FCHL, "cached")}), refine=False)["FCHL"]
    assert r["suspect"] == CX.FLOAT_EXCEEDS_SHARES
    assert r["suspect_text"] == "float on file 1.31M exceeds shares out 1.30M — treated as unknown"
    gated = DT._float_gate({"setup": "reversal_squeeze", "meta": {"structure_alive": True}, "as_of_bar_t": None}, r)
    assert gated["state"] == "none" and gated["reason"] == "float unknown"
    assert CX.rotation(5_000_000, r) is None


def test_float_above_shares_out_shares_out_policy_uses_shares_out(monkeypatch):
    monkeypatch.setattr(GC, "FLOAT_SUSPECT_POLICY", "shares_out")
    r = _floats(["FCHL"], Yahoo(cache={"FCHL": (FCHL, "cached")}), refine=False)["FCHL"]
    assert r["shares"] == 1_299_391 and r["src"] == "shares_out_yf"
    assert r["text"] == "shares out 1.3M (float on file exceeds it)"
    assert r["suspect_text"].endswith("— using shares out")


def test_NEGATIVE_float_equal_to_shares_out_is_not_suspect():
    vals = {"float_shares": 1_299_391, "shares_outstanding": 1_299_391}
    r = _floats(["X"], Yahoo(cache={"X": (vals, "cached")}), refine=False)["X"]
    assert r["suspect"] is None and r["src"] == "float"


@pytest.mark.parametrize("policy", GC.FLOAT_SUSPECT_POLICIES)
def test_NEGATIVE_no_float_no_shares_anywhere_is_unknown_under_both_policies(monkeypatch, policy):
    monkeypatch.setattr(GC, "FLOAT_SUSPECT_POLICY", policy)
    y = Yahoo(cache={"X": ({"float_shares": None, "shares_outstanding": None}, "cached")})
    assert _floats(["X"], y, refine=False)["X"]["text"] == "float unknown"


def test_stale_values_served_under_a_429_marker_are_used():
    y = Yahoo(cache={"X": ({"float_shares": 2_000_000}, "stale_served")})
    assert _floats(["X"], y, refine=False)["X"]["shares"] == 2_000_000


# ── rotation ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_rotation_float_and_shares_out_labels():
    assert CX.rotation(13_020_000, {"shares": 3_100_000, "src": "float"}) == {"x": 4.2, "text": "🔄 float ×4.2"}
    assert CX.rotation(8_100_000, {"shares": 8_100_000, "src": "shares_out_massive"})["text"] == "🔄 shares out ×1.0"


def test_NEGATIVE_rotation_float_zero_or_unknown_is_none():
    assert CX.rotation(1_000_000, {"shares": 0, "src": "float"}) is None
    assert CX.rotation(1_000_000, {"shares": None}) is None
    assert CX.rotation(1_000_000, None) is None
    assert CX.rotation(None, {"shares": 1_000_000, "src": "float"}) is None


# ── psychological levels ──────────────────────────────────────────────────────────────────────────────────────────
def test_psych_480_gives_5_dollars_4_2_pct():
    chips = CX.psych_chips(4.80)
    assert [c["level"] for c in chips] == [5.0]
    assert chips[0]["text"] == "🧱 $5 · 4.2% above" and chips[0]["why"] == CX.PSY_WHY


def test_psych_97_cents_and_9_60():
    assert [c["text"] for c in CX.psych_chips(0.97)] == ["🧱 $1 · 3.1% above"]
    assert [c["text"] for c in CX.psych_chips(9.60)] == ["🧱 $10 · 4.2% above"]


def test_NEGATIVE_psych_too_far_at_or_above_the_level():
    assert CX.psych_chips(4.70) == []           # 6.4% under $5
    assert CX.psych_chips(5.00) == []           # AT the level — not above
    assert CX.psych_chips(5.10) == []           # $5 is under the price; $10 is 96% away
    assert CX.psych_chips(0) == [] and CX.psych_chips(None) == []


# ── red closes chip ───────────────────────────────────────────────────────────────────────────────────────────────
def test_red_closes_chip_above_his_three():
    c = CX.red_closes_chip(GC.RED_CLOSES_WAIT + 1)
    assert c["n"] == 4 and c["text"] == "4 red closes in a row — he waits (“more than 3 red closes is red flag to me”)"


def test_NEGATIVE_red_closes_three_or_off_is_no_chip(monkeypatch):
    assert CX.red_closes_chip(GC.RED_CLOSES_WAIT) is None
    assert CX.red_closes_chip(0) is None
    monkeypatch.setattr(GC, "RED_CLOSES_MODE", "off")
    assert CX.red_closes_chip(9) is None


# ── halts ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _halts(by, session="2026-10-13"):
    return {"session_date": session, "by_ticker": by}


AAA_HALTS = {"ticker": "AAA", "n_halts": 2, "reasons": ["LUDP", "T1"], "halts": [
    {"halt_time": "10:31:22                      .756", "reason_code": "LUDP", "resume_date": "10/13/2026",
     "resume_time": "10:36:22"},
    {"halt_time": "09:45:01", "reason_code": "T1", "resume_date": "10/13/2026", "resume_time": "09:50:01"}]}


def test_halts_chip_two_halts_with_reasons_and_last_resume_in_et():
    c = CX.halts_chip("AAA", _halts({"AAA": AAA_HALTS}))
    assert c["text"] == "⏸ halted ×2 (LUDP, T1)" and c["n"] == 2
    assert c["first_halt_time"] == "09:45:01"
    assert c["last_resume_et"] == "2026-10-13T10:36:22-04:00"


def test_NEGATIVE_halts_chip_none_when_not_halted():
    assert CX.halts_chip("ZZZ", _halts({"AAA": AAA_HALTS})) is None
    assert CX.halts_chip("AAA", {}) is None and CX.halts_chip("AAA", None) is None


def test_NEGATIVE_missing_resume_time_is_none_still_halted():
    rec = {"ticker": "AAA", "n_halts": 1, "reasons": ["LUDP"],
           "halts": [{"halt_time": "15:58:00", "resume_date": None, "resume_time": None}]}
    assert CX.halts_chip("AAA", _halts({"AAA": rec}))["last_resume_et"] is None


def test_class_share_feed_spelling_maps_to_the_dash():
    rec = dict(AAA_HALTS, ticker="BRK.B")
    assert CX.halts_chip("BRK-B", _halts({"BRK.B": rec}))["n"] == 2
    st = fake_store()
    assert CX.record_halts(st, S, _halts({"BRK.B": rec}), source="history") == 1
    assert st.halt_dates("BRK-B") == {"2026-10-13"}


def test_record_live_halts_writes_today_only():
    st = fake_store()
    assert CX.record_live_halts(st, S, _halts({"AAA": AAA_HALTS})) == 1
    row = st.halts(S)[0]
    assert row["source"] == "live" and row["n_halts"] == 2 and row["reasons"] == ["LUDP", "T1"]
    assert CX.record_live_halts(st, S + timedelta(days=1), _halts({"AAA": AAA_HALTS})) == 0, \
        "a feed dated another session never lands under this one"
    assert CX.record_live_halts(st, S, {}) == 0


# ── 🎾 squeeze history ────────────────────────────────────────────────────────────────────────────────────────────
def _daily(ranges: dict, session=S, base=(1.0, 1.2)):
    """Daily frame over the chip's window: {ISO: (low, high)} overrides; every other day low 1.0 / high 1.2."""
    days = CX.history_window(session) + [session]
    rows = []
    for d in days:
        lo, hi = ranges.get(d.isoformat(), base)
        rows.append({"open": lo, "high": hi, "low": lo, "close": lo, "volume": 1e6})
    return pd.DataFrame(rows, index=pd.DatetimeIndex([pd.Timestamp(d) for d in days]))


def test_window_is_thirty_market_days_before_the_session():
    w = CX.history_window(S)
    assert len(w) == GC.K8_HISTORY_SESSIONS == 30 and w[-1] == date(2026, 10, 12) and S not in w
    assert date(2026, 9, 7) not in w, "Labor Day is not a session"


def test_squeeze_history_counts_range_days_and_halt_days():
    w = CX.history_window(S)
    edge = 1.0 * (1 + GC.K8_HISTORY_RANGE_PCT / 100)           # the module's own expression → 50% exactly
    df = _daily({w[0].isoformat(): (1.0, edge), w[5].isoformat(): (0.5, 2.0)})
    h = CX.squeeze_history(df, {w[10].isoformat(), w[5].isoformat()}, session=S)
    assert h["n"] == 3 and h["of"] == 30
    assert h["range_days"] == [w[0].isoformat(), w[5].isoformat()]
    assert h["halt_days"] == [w[5].isoformat(), w[10].isoformat()]
    assert h["text"] == "🎾 squeeze history: 3 of last 30 sessions (≥50% range or a halt)"


def test_NEGATIVE_49_9_pct_range_does_not_count():
    w = CX.history_window(S)
    assert CX.squeeze_history(_daily({w[0].isoformat(): (1.0, 1.499)}), set(), session=S)["n"] == 0


def test_NEGATIVE_todays_row_never_counts():
    h = CX.squeeze_history(_daily({S.isoformat(): (1.0, 9.0)}), {S.isoformat()}, session=S)
    assert h["n"] == 0


def test_NEGATIVE_a_halt_outside_the_window_never_counts():
    w = CX.history_window(S)
    assert CX.squeeze_history(_daily({}), {(w[0] - timedelta(days=1)).isoformat()}, session=S)["n"] == 0


def test_squeeze_history_incomplete_ledger_says_where_the_halt_list_starts():
    w = CX.history_window(S)
    h = CX.squeeze_history(_daily({}), set(), session=S, ledger_dates={w[-1].isoformat(), w[-2].isoformat()})
    assert h["ledger_complete"] is False and h["ledger_from"] == w[-2].isoformat()
    assert h["text"].endswith(f" · halt list from {w[-2].isoformat()}")
    full = CX.squeeze_history(_daily({}), set(), session=S, ledger_dates={d.isoformat() for d in w})
    assert full["ledger_complete"] is True and "halt list from" not in full["text"]


def test_NEGATIVE_no_daily_bars_counts_halts_only_and_says_so():
    w = CX.history_window(S)
    h = CX.squeeze_history(None, {w[3].isoformat()}, session=S)
    assert h["n"] == 1 and h["daily_ok"] is False and h["text"].endswith("no daily bars — halts only")


def test_warm_squeeze_history_counts_backfilled_halts_caps_new_computes_and_serves_stored():
    st = fake_store()
    w = CX.history_window(S)
    st.upsert_halt(w[2], "AAA", {"n_halts": 1, "source": "history"})
    calls: list = []

    def loader(sym, *, now=None):
        calls.append((sym, now))
        return _daily({})
    res = CX.warm_squeeze_history(["AAA", "BBB", "CCC"], S, st, cap=2, loader=loader)
    assert res["computed"] == 2 and res["deferred"] == 1
    assert res["chips"]["AAA"]["n"] == 1 and res["chips"]["AAA"]["halt_days"] == [w[2].isoformat()]
    assert calls[0][1] == datetime(2026, 10, 13, 0, 0), "the daily read is cut at the session's ET midnight"
    again = CX.warm_squeeze_history(["AAA", "BBB", "CCC"], S, st, cap=2, loader=loader)
    assert again["cached"] == 2 and again["computed"] == 1 and len(calls) == 3


# ── ☀️ K9 premarket ───────────────────────────────────────────────────────────────────────────────────────────────
def _scan_doc(sym, *, pm=True, vol=2e6, tape="premarket", price=2.2, prev=1.5, change=None):
    last = {"symbol": sym, "price": price, "prev_close": prev, "volume": vol, "vol_src": "min_av",
            "change_pct": change if change is not None else round((price / prev - 1) * 100, 4),
            "tape_session": tape}
    return {"_id": f"2026-10-13|{sym}", "date": "2026-10-13", "symbol": sym,
            "sessions": {"premarket": pm, "rth": not pm}, "last": last, "first_qualified_at": NOW}


def test_k9_list_volume_sorted_then_carry_names_after():
    docs = [_scan_doc("LOW", vol=1.5e6), _scan_doc("HIGH", vol=9e6), _scan_doc("MID", vol=3e6)]
    carry = {"_id": "2026-10-12", "pass_at": datetime(2026, 10, 13, 0, 1, tzinfo=timezone.utc),
             "names": {"CAR1": {"ah_move_pct": 12.34, "ah_last": 3.0, "reg_close": 2.67},
                       "CAR2": {"ah_move_pct": 30.0, "ah_last": 1.3, "reg_close": 1.0}}}
    rows = CX.premarket_list(docs, carry)
    assert [r["symbol"] for r in rows] == ["HIGH", "MID", "LOW", "CAR2", "CAR1"]
    car1 = rows[-1]
    assert car1["carry"] is True
    assert car1["text"] == "🌙 carried from yesterday's after-hours +12.3% (last after-hours pass 20:01)"


def test_NEGATIVE_a_premarket_name_under_1m_is_not_listed():
    edge = GC.K9_PM_MIN_VOLUME
    rows = CX.premarket_list([_scan_doc("ON", vol=edge), _scan_doc("OFF", vol=edge - 1)], None)
    assert [r["symbol"] for r in rows] == ["ON"]


def test_NEGATIVE_a_name_first_seen_after_the_open_is_not_premarket():
    assert CX.premarket_list([_scan_doc("RTH", pm=False, tape="rth")], None) == []


def test_k9_after_the_open_uses_the_1min_premarket_sum_and_off_pm_high():
    doc = _scan_doc("AAA", tape="rth", vol=30e6, price=2.20, prev=1.5)
    lv = {"high": 2.50, "low": 1.9, "volume": 4_000_000.0, "last": 2.4, "et_date": "2026-10-13"}
    rows = CX.premarket_list([doc], None, pm_levels={"AAA": lv})
    r = rows[0]
    assert r["pm_volume"] == 4_000_000.0 and r["pm_volume_src"] == "1min"
    assert r["off_pm_high_pct"] == -12.0
    assert r["pm_change_pct"] == 60.0


def test_NEGATIVE_after_the_open_with_no_premarket_volume_known_not_listed():
    assert CX.premarket_list([_scan_doc("AAA", tape="rth")], None) == []


def test_k9_change_toggle_and_a_carried_name_that_also_qualifies_is_listed_once():
    docs = [_scan_doc("A", vol=9e6, price=1.6, prev=1.0), _scan_doc("B", vol=2e6, price=2.0, prev=1.0)]
    carry = {"pass_at": NOW, "names": {"B": {"ah_move_pct": 15.0}}}
    rows = CX.premarket_list(docs, carry, sort="change")
    assert [r["symbol"] for r in rows] == ["B", "A"]
    assert rows[0]["carried"]["ah_move_pct"] == 15.0 and rows[0]["carry"] is False


def _pm_frame(session=S, with_pm=True):
    idx, rows = [], []
    if with_pm:
        for k, (hi, lo, c, v) in enumerate([(2.0, 1.8, 1.9, 1e6), (2.5, 1.9, 2.4, 2e6)]):
            idx.append(pd.Timestamp(datetime(2026, 10, 13, 12, k)))           # 08:0k ET (EDT)
            rows.append({"open": lo, "high": hi, "low": lo, "close": c, "volume": v, "session": "premarket"})
    idx.append(pd.Timestamp(datetime(2026, 10, 13, 13, 30)))
    rows.append({"open": 2.4, "high": 2.6, "low": 2.3, "close": 2.5, "volume": 5e6, "session": "rth"})
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


def test_pm_levels_for_today():
    lv = CX.pm_levels_for(_pm_frame(), S)
    assert lv["high"] == 2.5 and lv["volume"] == 3e6 and lv["last"] == 2.4


def test_NEGATIVE_pm_levels_for_no_premarket_bars_or_another_day_is_none():
    assert CX.pm_levels_for(_pm_frame(with_pm=False), S) is None
    assert CX.pm_levels_for(_pm_frame(), S + timedelta(days=1)) is None


# ── 🌙 K10 post-market ────────────────────────────────────────────────────────────────────────────────────────────
def _post_minutes(lo, hi, *, c1559=None, ah=(300_000,), cross=5_000_000, session=S):
    """1-min bars, naive UTC (bar START): an RTH bar at 09:30 ET carrying hi/lo, the 15:59 bar, the 16:00 cross minute,
    then after-hours minutes from 16:01."""
    base = datetime(session.year, session.month, session.day, 13, 30)            # 09:30 EDT
    idx = [base, base + timedelta(minutes=389), base + timedelta(minutes=390)]   # 09:30, 15:59, 16:00
    rows = [{"open": lo, "high": hi, "low": lo, "close": lo, "volume": 1e6},
            {"open": lo, "high": lo, "low": lo, "close": c1559 if c1559 is not None else lo, "volume": 1e5},
            {"open": lo, "high": lo, "low": lo, "close": lo, "volume": cross}]
    for k, v in enumerate(ah):
        idx.append(base + timedelta(minutes=391 + k))
        rows.append({"open": lo, "high": lo, "low": lo, "close": lo, "volume": v})
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


def _cand(sym, reg, price, prev=None):
    return {"symbol": sym, "price": price, "day_c": reg, "prev_close": prev, "ah_move_pct": (price / reg - 1) * 100 if reg else None}


def _confirm(cands, minutes, checked=None, **kw):
    kw.setdefault("session", S)
    kw.setdefault("now", datetime(2026, 10, 13, 21, 1, tzinfo=timezone.utc))
    return CX.postmarket_confirm(cands, checked or {}, lambda s: minutes[s], **kw)


def test_k10_close_pos_edge_binary_exact():
    close = 1 - GC.K10_CLOSE_TOP_FRAC
    price = close * (1 + GC.K10_AH_MIN_GAIN_PCT / 100)
    rows, unchecked = _confirm([_cand("ON", close, price)], {"ON": _post_minutes(0.0, 1.0)})
    assert [r["symbol"] for r in rows] == ["ON"] and unchecked == 0
    assert rows[0]["checked_text"] == "checked 17:01 ET"


def test_NEGATIVE_k10_close_pos_just_under_the_edge():
    close = 1 - GC.K10_CLOSE_TOP_FRAC - 1e-9
    price = close * (1 + GC.K10_AH_MIN_GAIN_PCT / 100)
    rows, _ = _confirm([_cand("OFF", close, price)], {"OFF": _post_minutes(0.0, 1.0)})
    assert rows == []


def test_k10_ah_volume_250k_edge():
    rows, _ = _confirm([_cand("ON", 2.00, 2.30)], {"ON": _post_minutes(1.0, 2.05, ah=(150_000, 100_000))})
    assert rows and rows[0]["ah_volume"] == GC.K10_AH_MIN_VOLUME


def test_NEGATIVE_k10_ah_volume_249_999():
    rows, _ = _confirm([_cand("OFF", 2.00, 2.30)], {"OFF": _post_minutes(1.0, 2.05, ah=(150_000, 99_999))})
    assert rows == []


def test_NEGATIVE_the_16_00_closing_cross_minute_is_excluded():
    rows, _ = _confirm([_cand("OFF", 2.00, 2.30)], {"OFF": _post_minutes(1.0, 2.05, ah=(1,), cross=50_000_000)})
    assert rows == []


def test_k10_gain_edge_and_negative():
    m = {"ON": _post_minutes(1.0, 2.05), "OFF": _post_minutes(1.0, 2.05)}
    rows, _ = _confirm([_cand("ON", 2.00, 2.00 * 1.05), _cand("OFF", 2.00, 2.00 * 1.0499)], m)
    assert [r["symbol"] for r in rows] == ["ON"]


def test_k10_reg_close_falls_back_to_the_1559_minute_flagged():
    c = _cand("ON", None, 2.30)
    rows, _ = _confirm([c], {"ON": _post_minutes(1.0, 2.05, c1559=2.0)})
    assert rows[0]["reg_close"] == 2.0 and rows[0]["reg_close_src"] == "minute_1559"


def test_k10_reg_gain_pct_and_NEGATIVE_prev_close_zero():
    m = {"A": _post_minutes(1.0, 2.05), "B": _post_minutes(1.0, 2.05)}
    rows, _ = _confirm([_cand("A", 2.0, 2.3, prev=1.0), _cand("B", 2.0, 2.3, prev=0)], m)
    by = {r["symbol"]: r for r in rows}
    assert by["A"]["reg_gain_pct"] == 100.0 and by["B"]["reg_gain_pct"] is None


def test_k10_rotation_cap_unchecked_count_and_the_next_pass_checks_them_first():
    st = fake_store()
    cands = [_cand(f"N{i:03d}", 2.0, 2.0 * (1.10 + i / 1000)) for i in range(200)]
    minutes = {c["symbol"]: _post_minutes(1.0, 2.05) for c in cands}
    loaded: list = []

    def loader(s):
        loaded.append(s)
        return minutes[s]
    t1 = datetime(2026, 10, 13, 21, 1, tzinfo=timezone.utc)
    rows, unchecked = CX.postmarket_confirm(cands, {}, loader, cap=150, session=S, now=t1, store=st)
    assert len(loaded) == 150 and unchecked == 50 and len(rows) == 150
    assert CX.unchecked_text(unchecked) == "50 after-hours gainers not checked yet — next pass"
    first = set(loaded)
    loaded.clear()
    checked = {d["symbol"]: d for d in st.post_docs(S)}
    t2 = t1 + timedelta(minutes=5)
    rows2, unchecked2 = CX.postmarket_confirm(cands, checked, loader, cap=150, session=S, now=t2, store=st)
    assert set(loaded[:50]) == {c["symbol"] for c in cands} - first, "the never-checked 50 go first"
    assert unchecked2 == 0 and len(rows2) == 200


def test_k10_close_pos_is_fixed_once_computed():
    prior = {"close_pos": 0.9, "reg_close": 2.0, "rth_high": 2.05, "rth_low": 1.5, "reg_close_src": "snapshot_day_c",
             "checked_at": datetime(2026, 10, 13, 20, 6, tzinfo=timezone.utc), "ah_volume": 1.0, "passes": 1}
    rows, _ = _confirm([_cand("A", 2.0, 2.3)], {"A": _post_minutes(1.0, 9.0)}, checked={"A": prior})
    assert rows[0]["close_pos"] == 0.9 and rows[0]["rth_high"] == 2.05


def test_NEGATIVE_minutes_failure_counts_as_unchecked_never_silent():
    def loader(s):
        raise RuntimeError("massive down")
    rows, unchecked = CX.postmarket_confirm([_cand("A", 2.0, 2.3)], {}, loader, session=S, now=NOW)
    assert rows == [] and unchecked == 1


# ── source guards ─────────────────────────────────────────────────────────────────────────────────────────────────
ALLOWED_SEPA = {"sepa.moat_backfill", "sepa.volume_movers", "sepa.prices"}   # infra only: pacing, float, daily bars


@pytest.mark.parametrize("mod", ["context.py", "nightly.py"])
def test_NEGATIVE_source_guard_no_sepa_method_or_bonde_import_or_word(mod):
    path = os.path.join(os.path.dirname(CX.__file__), mod)
    src = open(path, encoding="utf-8").read()
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    bad = [n for n in names if (n.startswith("sepa") and n not in ALLOWED_SEPA) or "bonde" in n.lower()]
    assert bad == [], bad
    low = src.lower()
    for word in ("minervini", "bonde", "is_candidate", "bounce"):
        assert word not in low, word


def test_NEGATIVE_no_literal_threshold_numbers_in_the_rule_expressions():
    """Every rule number comes from constants by name — the edges read `GC.<NAME>`."""
    src = open(CX.__file__, encoding="utf-8").read()
    for name in ("K10_CLOSE_TOP_FRAC", "K10_AH_MIN_VOLUME", "K10_AH_MIN_GAIN_PCT", "K9_PM_MIN_VOLUME",
                 "K8_HISTORY_RANGE_PCT", "PSY_NEAR_PCT", "PSY_LEVELS", "RED_CLOSES_WAIT", "K8_MAX_FLOAT",
                 "FLOAT_MAX_NEW_PER_PASS", "AH_CONFIRM_MAX_PER_PASS"):
        assert f"GC.{name}" in src, name
    for literal in ("250_000", "250000", "1_000_000", "0.30", "0.7 ", "10_000_000"):
        assert literal not in src, literal


# ── 2026-10-13 review: the float's as_of is the DATA's age; a raising Massive is asked once a pass ───────────────
def test_float_as_of_is_the_rows_stamp_not_the_pass_time():
    row = int((NOW - timedelta(days=2)).timestamp())
    y = Yahoo(cache={"AAA": ({"float_shares": 3_100_000, "shares_outstanding": 8_100_000, "as_of": row}, "cached")})
    r = _floats(["AAA"], y, refine=False)["AAA"]
    assert r["as_of"] == (NOW - timedelta(days=2)).isoformat() and r["text"] == "Float 3.1M"


def test_NEGATIVE_stale_served_float_says_stale_with_its_date():
    old = NOW - timedelta(days=9)
    y = Yahoo(cache={"AAA": ({"float_shares": 3_100_000, "shares_outstanding": 8_100_000,
                              "as_of": int(old.timestamp())}, "stale_served")})
    r = _floats(["AAA"], y, refine=False)["AAA"]
    assert r["as_of"] == old.isoformat()
    assert r["text"] == f"Float 3.1M (stale, as of {old.date().isoformat()})"
    assert r["shares"] == 3_100_000, "still served — floats move rarely and Yahoo cannot be asked"


def test_NEGATIVE_row_without_a_stamp_falls_back_to_now():
    y = Yahoo(cache={"AAA": ({"float_shares": 3_100_000, "shares_outstanding": 8_100_000}, "cached")})
    assert _floats(["AAA"], y, refine=False)["AAA"]["as_of"] == NOW.isoformat()


def test_fetched_float_stored_with_the_fetch_stamp():
    st = fake_store()
    stamp = int(NOW.timestamp())
    y = Yahoo(answers={"AAA": ({"float_shares": 3_100_000, "shares_outstanding": 8_100_000, "as_of": stamp},
                               "fetched")})
    _floats(["AAA"], y, store=st, session=S)
    assert st.get_daily(S, "AAA")["float"]["as_of"] == NOW.isoformat()


class _Down:
    def __init__(self):
        self.calls: list = []

    def __call__(self, sym):
        self.calls.append(sym)
        raise RuntimeError("massive down")


def test_NEGATIVE_raising_massive_is_called_once_per_pass_across_both_float_calls():
    """run.py calls floats_for twice a pass (refine=False, then refine=True) with the same `now`."""
    st, m = fake_store(), _Down()
    a = _floats(["AAA"], Yahoo(), m, refine=False, store=st, session=S)["AAA"]
    b = _floats(["AAA"], Yahoo(answers={"AAA": (None, "no_data")}), m, store=st, session=S)["AAA"]
    assert m.calls == ["AAA"]
    assert a["text"] == b["text"] == "float unknown"


def test_NEGATIVE_raising_massive_is_tried_again_next_pass():
    st, m = fake_store(), _Down()
    _floats(["AAA"], Yahoo(), m, refine=False, store=st, session=S)
    _floats(["AAA"], Yahoo(), m, refine=False, store=st, session=S,
            now=NOW + timedelta(seconds=GC.PASS_CADENCE_SEC - 1))
    assert m.calls == ["AAA"], "still the same pass window"
    good = Massive({"AAA": 8_100_000})
    r = _floats(["AAA"], Yahoo(), good, refine=False, store=st, session=S,
                now=NOW + timedelta(seconds=GC.PASS_CADENCE_SEC))["AAA"]
    assert good.calls == ["AAA"] and r["text"] == "shares out 8.1M (Massive)"
    _floats(["AAA"], Yahoo(), good, refine=False, store=st, session=S,
            now=NOW + timedelta(seconds=2 * GC.PASS_CADENCE_SEC))
    assert good.calls == ["AAA"], "the answer, once it lands, is kept for the session"
