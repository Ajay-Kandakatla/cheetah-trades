"""🏁 🩳 SI follow-up (2026-11-26, SPEC sishares rev 2 §3.5 / §4.3, WP be-track) — negatives first.

Ajay 2026-11-26: "lets track them in our list of SI. and maintain a track record of our stocks".
Hermetic: the si_track test world (a fake gajjala store, injected seams). Not advice.
"""
from __future__ import annotations

import ast
import copy
import json
import re
from datetime import date
from pathlib import Path

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import si_follow as SF
from chart_maps.gajjala import si_track as SIT
from chart_maps.gajjala import store as ST
from daytrading import data as dt_data
from short_interest import basis_math as BM
from tests.test_gajjala_si_track_2026_11_26 import (HALF, NIGHT, N, P, S, SEAMS, _minutes, fake_store, flat, rdoc,
                                                    utc, world)

SF_SRC = Path(SF.__file__).read_text(encoding="utf-8")
D23, D24, D25, D30 = date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 30)
LATE = utc(date(2026, 12, 15), "20:30")                        # every horizon of S has ended


def rec(st, si, d=S, now=NIGHT, **kw):
    seams = dict(SEAMS, si_read=si)
    seams.update(kw)
    return SIT.record_session(st, d, now, **seams)


def ctx_of(st, now=NIGHT, *, stub=None, cap=None, split=lambda s, lo, hi: False):
    status = {}
    ctx = SIT.Ctx(st, now, load_1m=SF.loader(stub or (lambda s, d: None), status), split_lookup=split,
                  budget=SIT.Budget(SIT.MAX_LOADS if cap is None else cap))
    return ctx, status


def fact(state="ok", *, retry=False, high=None, low=None, close=None, winner=None, base=None, prev_close=1.0):
    f = dict.fromkeys(SF.FACT_KEYS)
    f.update(state=state, retry=retry, high=high, low=low, close=close, winner=winner, base=base,
             prev_close=prev_close, load="reads")
    return f


def after(*facts_, ended=True, start=S):
    days = SF._next_n(start, SF.FOLLOW_SESSIONS)
    out = []
    for i, x in enumerate(days):
        f = facts_[i] if i < len(facts_) else None
        e = ended if isinstance(ended, bool) else i < ended
        out.append((x.isoformat(), f, e))
    return out


# ── constants [C15] ───────────────────────────────────────────────────────────────────────────────────────────────
def test_horizons_are_the_two_constants_by_name_and_no_typed_five_or_ten():
    assert SF.HORIZONS == (1, GC.LEDGER_SPAN_SESSIONS, GC.LEDGER_SPAN_SESSIONS_LONG)
    assert SF.DAY_HORIZON is GC.LEDGER_SPAN_SESSIONS and SF.FOLLOW_SESSIONS == GC.LEDGER_SPAN_SESSIONS_LONG
    ints = {n.value for n in ast.walk(ast.parse(SF_SRC)) if isinstance(n, ast.Constant) and type(n.value) is int}
    assert GC.LEDGER_SPAN_SESSIONS not in ints and GC.LEDGER_SPAN_SESSIONS_LONG not in ints
    assert re.search(r"HORIZONS = \(1, GC\.LEDGER_SPAN_SESSIONS, GC\.LEDGER_SPAN_SESSIONS_LONG\)", SF_SRC)
    assert SF.FACT_STATES == SIT.OUTCOME_STATES + ("no_trade",)


def test_the_day_table_gains_exactly_one_head_and_no_f1_or_f10():
    heads = SIT.day_heads()
    assert heads[:-1] == SIT.DAY_HEADS and len(heads) == len(SIT.DAY_HEADS) + 1
    assert heads[-1] == ["f%d" % SF.DAY_HORIZON, "+%d sessions" % SF.DAY_HORIZON] == SIT.FOLLOW_HEAD
    keys = {h[0] for h in heads}
    assert "f%d" % SF.HORIZONS[0] not in keys and "f%d" % SF.HORIZONS[-1] not in keys
    assert set(SF.cells({}, None)) == {"f%d" % SF.DAY_HORIZON}


def test_si_track_pins_moved_block_and_night_keys_gain_follow():
    assert SIT.BLOCK_KEYS[-1] == "follow" and SIT.NIGHT_KEYS[-1] == "follow"
    assert len(set(SIT.BLOCK_KEYS)) == len(SIT.BLOCK_KEYS) and len(set(SIT.NIGHT_KEYS)) == len(SIT.NIGHT_KEYS)


# ── [C9] the 6-K stays out of the 🏁 pattern ──────────────────────────────────────────────────────────────────────
def _basis(filings, flags=(), sec="ok"):
    return {"basis": {"filings": list(filings), "splits": [], "sources": {"sec": sec, "splits": "ok"},
                      "flags": list(flags)}}


def test_kinds_not_in_pattern_is_the_basis_math_kind():
    assert SIT.FILING_KINDS_NOT_IN_PATTERN == (BM.KIND_FOREIGN_ISSUANCE,)


def test_NEGATIVE_a_foreign_issuance_6k_before_the_session_never_sets_dilution_before():
    flag = {"key": BM.FLAG_FILING, "short": "📄 6-K 11/18"}
    six = {"form": "6-K", "filed": P.isoformat(), "kind": BM.KIND_FOREIGN_ISSUANCE}
    f = SIT.filing_facts(_basis([six], flags=[flag]), S)
    assert f["dilution_before"] is False and f["dilution"] is True and f["flag_shorts"] == ["📄 6-K 11/18"]
    f1 = {"form": "F-1", "filed": P.isoformat(), "kind": BM.KIND_REGISTRATION}
    assert SIT.filing_facts(_basis([six, f1], flags=[flag]), S)["dilution_before"] is True
    assert SIT.filing_facts(_basis([six], sec="failed"), S)["dilution_before"] is None


# ── the loader [C3] ───────────────────────────────────────────────────────────────────────────────────────────────
def test_loader_tells_failed_from_no_bars_from_loaded_and_a_raise_is_failed():
    status = {}

    def stub(sym, d):
        if sym == "FAIL":
            return dt_data._provider_failed()
        if sym == "BOOM":
            raise RuntimeError("x")
        return _minutes(d) if sym == "OK" else None
    load = SF.loader(stub, status)
    assert load("FAIL", S) is None and status[("FAIL", S.isoformat())] == "failed"
    assert load("NONE", S) is None and status[("NONE", S.isoformat())] == "no_bars"   # the flag is cleared first
    assert load("BOOM", S) is None and status[("BOOM", S.isoformat())] == "failed"
    assert load("OK", S) is not None and status[("OK", S.isoformat())] == "loaded"
    assert SF.loader(SF.stored_only, status)("ANY", S) is None and status[("ANY", S.isoformat())] == "deferred"


# ── day_fact [C2] ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_an_off_scanner_name_is_graded_from_the_stand_in_tail():
    st = fake_store()
    calls = []
    ctx, status = ctx_of(st, stub=lambda s, d: calls.append(d) or _minutes(d))
    f = SF.day_fact(ctx, "OFF", S, status)
    assert f["state"] == "ok" and f["prev_close"] == pytest.approx(1.0) and f["retry"] is False
    assert f["high_pct"] == pytest.approx(50.0) and f["winner"] is True and f["load"] == "loaded"
    assert ctx.budget.loads == 2 and ctx.budget.split_calls == 1 and sorted(calls) == [P, S]
    assert f["low"] == pytest.approx(1.0) and f["close"] == pytest.approx(1.0)
    assert set(f) == set(SF.FACT_KEYS[:-3])                         # not listed → no base keys


def test_NEGATIVE_the_same_name_handed_straight_to_outcome_is_no_prev_close_with_no_load():
    ctx, _status = ctx_of(fake_store(), stub=lambda s, d: _minutes(d))
    o = SIT.outcome(ctx, "OFF", S, read_doc=None, prev_read_doc=None, scan_doc=None, avg_vol_50=None)
    assert o["outcome_state"] == "no_prev_close" and ctx.budget.loads == 0      # the bug the pre-build fixes


def test_NEGATIVE_budget_spent_before_the_prior_day_load_is_retry():
    ctx, status = ctx_of(fake_store(), stub=lambda s, d: _minutes(d), cap=1)
    f = SF.day_fact(ctx, "OFF", S, status)
    assert f["state"] == "no_prev_close" and f["retry"] is True and ctx.budget.deferred >= 1


def test_NEGATIVE_the_provider_failing_the_prior_day_is_retry():
    def stub(s, d):
        return _minutes(d) if d == S else dt_data._provider_failed()
    ctx, status = ctx_of(fake_store(), stub=stub)
    f = SF.day_fact(ctx, "OFF", S, status)
    assert f["state"] == "no_prev_close" and f["retry"] is True


def test_NEGATIVE_the_provider_answering_the_prior_day_empty_is_terminal_no_prev_close():
    ctx, status = ctx_of(fake_store(), stub=lambda s, d: _minutes(d) if d == S else None)
    f = SF.day_fact(ctx, "OFF", S, status)
    assert f["state"] == "no_prev_close" and f["retry"] is False and f["winner"] is None
    assert SF._terminal(f)


def test_an_answered_empty_day_is_no_trade_terminal_and_a_failed_one_is_retried():
    ctx, status = ctx_of(fake_store(), stub=lambda s, d: None)
    f = SF.day_fact(ctx, "HALT", S, status)
    assert f["state"] == "no_trade" and f["retry"] is False and f["load"] == "no_bars"
    ctx, status = ctx_of(fake_store(), stub=lambda s, d: dt_data._provider_failed())
    f = SF.day_fact(ctx, "HALT", S, status)
    assert f["state"] == "no_bars" and f["retry"] is True and f["load"] == "failed"
    ctx, status = ctx_of(fake_store(), stub=lambda s, d: None, cap=0)
    f = SF.day_fact(ctx, "HALT", S, status)
    assert f["state"] == "no_bars" and f["retry"] is True and f["load"] == "deferred"     # never a no_trade


def test_a_copied_listing_row_equals_the_computed_fact_and_costs_no_unit():
    st, si = world()
    row = next(r for r in rec(st, si)["doc"]["rows"] if r["symbol"] == "AAA")
    assert row["outcome_state"] == "ok"
    ctx, status = ctx_of(st)
    copied = SF.day_fact(ctx, "AAA", S, status, row=row)
    assert ctx.budget.loads == 0 and ctx.budget.split_calls == 0
    ctx2, status2 = ctx_of(st)
    computed = SF.day_fact(ctx2, "AAA", S, status2)
    keys = [k for k in SF.FACT_KEYS if k not in SF.BASE_KEYS]
    assert {k: copied[k] for k in keys} == {k: computed[k] for k in keys}
    assert ctx2.budget.split_calls == 1                             # computed: the split check is asked
    assert copied["base_kind"] == "regular_close" and copied["base"] == pytest.approx(1.0)


# ── base_of [C5] ──────────────────────────────────────────────────────────────────────────────────────────────────
def _ah_doc(d=S, reg_end="16:00"):
    bars = flat(d, "04:00", "09:30", 0.5, s="pre") + flat(d, "09:30", reg_end, 1.0)
    bars[-1] = dict(bars[-1], c=1.1)                                # the last regular close
    ah = flat(d, reg_end, "20:00", 2.0, s="ah")
    for i, b in enumerate(ah):
        b["c"] = round(2.0 + i * 0.01, 2)
        b["h"] = max(b["h"], b["c"])
    return rdoc("X", d, bars + ah)


def _close_at(doc, d, start):
    return next(b["c"] for b in SIT.day_bars(doc, d) if SIT.bar_start(b) == start)


def test_base_listed_before_or_during_the_day_is_the_last_regular_close():
    doc = _ah_doc()
    assert SF.base_of(doc, {"listed_before": True, "listed_at": None}, S) == (1.1, "regular_close", None)
    assert SF.base_of(doc, {"listed_before": False, "listed_at": "10:15"}, S) == (1.1, "regular_close", None)


def test_base_listed_after_the_close_is_the_first_bar_at_or_after_the_listing():
    doc = _ah_doc()
    b = SF.base_of(doc, {"listed_before": False, "listed_at": "16:06"}, S)
    assert b == (_close_at(doc, S, "16:10"), "after_listing", "16:10")
    assert SF.base_of(doc, {"listed_before": False, "listed_at": "16:05"}, S)[2] == "16:05"


def test_NEGATIVE_listed_17_26_never_takes_the_16_00_close():
    doc = _ah_doc()
    b = SF.base_of(doc, {"listed_before": False, "listed_at": "17:26"}, S)
    assert b[1] == "after_listing" and b[2] == "17:30" and b[0] == _close_at(doc, S, "17:30") and b[0] != 1.1


def test_base_on_a_half_day_cuts_at_its_own_close():
    doc = _ah_doc(HALF, reg_end="13:00")
    assert SF.base_of(doc, {"listed_before": False, "listed_at": "12:30"}, HALF) == (1.1, "regular_close", None)
    b = SF.base_of(doc, {"listed_before": False, "listed_at": "13:02"}, HALF)
    assert b[1] == "after_listing" and b[2] == "13:05"


def test_NEGATIVE_no_bar_after_the_listing_or_no_listing_time_is_no_base():
    doc = _ah_doc()
    assert SF.base_of(doc, {"listed_before": False, "listed_at": "19:58"}, S) == (None, None, None)
    assert SF.base_of(doc, {"listed_before": False, "listed_at": None}, S) == (None, None, None)
    assert SF.base_of(doc, {"listed_before": None}, S) == (None, None, None)
    assert SF.base_of(None, {"listed_before": True}, S) == (None, None, None)
    assert SF.base_of(doc, None, S) == (None, None, None)


def test_NEGATIVE_the_premarket_low_is_ignored():
    doc = _ah_doc()
    assert SF._low(doc, S) == pytest.approx(1.0)                    # the 0.5 premarket bars never count


# ── forward ───────────────────────────────────────────────────────────────────────────────────────────────────────
ROW = {"date": S.isoformat(), "symbol": "A", "high": 1.5}
BASE = dict(fact(high=1.5, close=1.0), base=1.0, base_kind="regular_close", base_at=None)


def test_sessions_after_are_market_days_skipping_the_weekend_and_the_holiday():
    assert SF._next_n(S, 6) == [N, D23, D24, D25, HALF, D30]       # 11-21/22 weekend, 11-26 Thanksgiving


def test_forward_ok_counts_wins_new_high_close_run_and_low():
    fs = [fact(high=1.2, low=0.9, close=1.1), fact(high=1.6, low=0.8, close=1.3, winner=True),
          fact(high=1.4, low=0.95, close=1.25), fact(high=1.3, low=1.0, close=1.2), fact(high=1.3, low=1.0, close=1.15)]
    f = SF.forward(ROW, BASE, after(*fs))
    one, five = f[1], f[SF.DAY_HORIZON]
    assert one["state"] == "ok" and one["wins"] == 0 and one["new_high"] is False
    assert one["close_pct"] == pytest.approx(10.0) and one["run_pct"] == pytest.approx(20.0)
    assert five["state"] == "ok" and five["n_read"] == 5 and five["wins"] == 1 and five["new_high"] is True
    assert five["close_pct"] == pytest.approx(15.0) and five["run_pct"] == pytest.approx(60.0)
    assert five["low_pct"] == pytest.approx(-20.0)
    assert f[SF.FOLLOW_SESSIONS]["state"] == "unread"               # sessions 6–10 have no fact


def test_NEGATIVE_new_high_is_strictly_above_and_none_without_a_listing_high():
    f = SF.forward(ROW, BASE, after(fact(high=1.5, low=1.0, close=1.0)))
    assert f[1]["new_high"] is False
    f = SF.forward({"date": S.isoformat(), "symbol": "A"}, dict(BASE, high=None), after(fact(high=9.0)))
    assert f[1]["new_high"] is None and f[1]["state"] == "ok"


def test_NEGATIVE_pending_until_the_kth_session_ends_and_close_is_none_until_read():
    f = SF.forward(ROW, BASE, after(fact(high=1.2, close=1.1), ended=1))
    assert f[1]["state"] == "ok" and f[SF.DAY_HORIZON]["state"] == "pending"
    assert f[SF.DAY_HORIZON]["close_pct"] is None


def test_NEGATIVE_a_retry_or_missing_fact_is_unread_never_a_zero():
    f = SF.forward(ROW, BASE, after(fact(), fact("no_bars", retry=True)))
    assert f[1]["state"] == "ok"
    five = f[SF.DAY_HORIZON]
    assert five["state"] == "unread" and five["n_read"] == 1 and five["close_pct"] is None
    f = SF.forward(ROW, None, after(fact(high=1.2)))
    assert f[1]["state"] == "unread"                                # the listing day's own fact is missing
    f = SF.forward(ROW, dict(BASE, retry=True), after(fact(high=1.2)))
    assert f[1]["state"] == "unread"


def test_NEGATIVE_a_split_stops_the_numbers():
    f = SF.forward(ROW, BASE, after(fact(high=1.2, low=0.9, close=1.1), fact("split"), fact(high=9.0, low=0.1)))
    five = f[SF.DAY_HORIZON]
    assert five["state"] == "split" and five["n_read"] == 1 and five["run_pct"] == pytest.approx(20.0)
    assert five["low_pct"] == pytest.approx(-10.0) and five["close_pct"] is None
    assert SF.cells(ROW, f)["f%d" % SF.DAY_HORIZON] == "split after 1"


def test_NEGATIVE_nan_none_and_bool_highs_are_ignored():
    fs = [fact(high=float("nan"), low=True, close=1.0), fact(high=None, low=1.0, close=1.0), fact(high=True)]
    f = SF.forward(ROW, BASE, after(*fs), (3,))[3]
    assert f["state"] == "ok" and f["run_pct"] is None and f["new_high"] is False
    assert f["low_pct"] == pytest.approx(0.0)


def test_no_trade_and_ungraded_sessions_are_counted_apart():
    fs = [fact("no_trade", high=None, close=None), fact("no_prev_close", high=None, low=0.9, close=1.0)]
    f = SF.forward(ROW, BASE, after(*fs), (2,))[2]
    assert f["state"] == "ok" and f["no_trade"] == 1 and f["ungraded"] == 1 and f["wins"] == 0


def test_forward_with_no_base_still_counts_wins_and_new_high():
    fs = [fact(high=2.0, low=0.5, close=1.5, winner=True)]
    f = SF.forward(ROW, dict(BASE, base=None, base_kind=None), after(*fs))[1]
    assert f["close_pct"] is None and f["run_pct"] is None and f["low_pct"] is None
    assert f["wins"] == 1 and f["new_high"] is True
    assert SF.cells(ROW, {SF.DAY_HORIZON: dict(f, state="ok")})["f%d" % SF.DAY_HORIZON] == "1✅ · new high"


def test_cells_words():
    key = "f%d" % SF.DAY_HORIZON
    ok = {"state": "ok", "wins": 1, "new_high": True, "close_pct": 12.34, "run_pct": 88.1, "low_pct": -14.2,
          "no_trade": 1, "n_read": 5}
    assert SF.cells(ROW, {SF.DAY_HORIZON: ok})[key] == "1✅ · new high · close +12.3% · run +88.1% · low −14.2% · 1 no trade"
    assert SF.cells(ROW, {SF.DAY_HORIZON: {"state": "unread", "n_read": 3}})[key] == "3 of %d read" % SF.DAY_HORIZON
    assert SF.cells(ROW, {SF.DAY_HORIZON: {"state": "pending"}})[key] == "pending"
    for junk in (None, [], 7, {SF.DAY_HORIZON: {"state": "weird"}}, {SF.DAY_HORIZON: None}):
        assert SF.cells(ROW, junk)[key] == SIT.DASH


# ── follow_stats [C3] ─────────────────────────────────────────────────────────────────────────────────────────────
def _row(sym, d=S, high=1.5, winner=False):
    return {"date": d.isoformat(), "symbol": sym, "high": high, "winner": winner, "listed_before": True}


def _facts(by: dict) -> dict:
    """{(iso, sym): fact} → {iso: {sym: fact}}"""
    out = {}
    for (iso, sym), f in by.items():
        out.setdefault(iso, {})[sym] = dict(f, symbol=sym)
    return out


def _full(sym, d=S, *, k=SF.FOLLOW_SESSIONS, winner_on=None, state="ok"):
    by = {(d.isoformat(), sym): BASE}
    for i, x in enumerate(SF._next_n(d, k)):
        by[(x.isoformat(), sym)] = fact(state if i == 0 else "ok", high=1.2, low=0.9, close=1.1,
                                        winner=(winner_on == i))
    return by


def test_a_day_with_one_unread_name_is_not_counted_and_its_rows_are_printed():
    rows = [_row("A"), _row("B")]
    by = _full("A", winner_on=0)
    by[(S.isoformat(), "B")] = BASE                                  # B's later sessions never read
    s = SF.follow_stats(rows, _facts(by), LATE)["by"]["1"]
    assert s["days_due"] == 1 and s["days_complete"] == 0 and s["n"] == 0
    assert s["unread_days"] == 1 and s["unread_rows"] == 1
    lines = SF.base_lines(SF.follow_stats(rows, _facts(by), LATE))
    assert lines[0] == ("Within 1 session after a listing day — no listing day is read in full yet (1 name-days not "
                        "read); nothing is counted.")


def test_a_no_trade_name_is_counted_in_n():
    rows = [_row("A"), _row("B")]
    by = {**_full("A", winner_on=0), **_full("B", state="no_trade")}
    s = SF.follow_stats(rows, _facts(by), LATE)["by"]["1"]
    assert s["days_complete"] == 1 and s["n"] == 2 and s["names"] == 2
    assert s["again"] == 1 and s["no_trade"] == 1 and s["unread_rows"] == 0
    line = SF.base_lines(SF.follow_stats(rows, _facts(by), LATE))[0]
    assert line.startswith("Within 1 session after a listing day — counted on 1 of 1 listing days read in full · "
                           "2 name-days · 2 names: another +40% day 1 of 2")
    assert "1 did not trade a session" in line


def test_NEGATIVE_the_outcome_selected_sample_yields_no_count_line():
    rows, by = [], {}
    for i, d in enumerate((P, S, N)):
        rows += [_row("W%d" % i, d, winner=True), _row("L%d" % i, d), _row("M%d" % i, d)]
        by.update(_full("W%d" % i, d, winner_on=0))
        by[(d.isoformat(), "L%d" % i)] = BASE                       # the rest: listed, never read after
        by[(d.isoformat(), "M%d" % i)] = BASE
    fs = SF.follow_stats(rows, _facts(by), LATE)
    for k in SF.HORIZONS:
        assert fs["by"][str(k)]["days_complete"] == 0 and fs["by"][str(k)]["n"] == 0
    assert not any(" · counted on " in ln for ln in SF.base_lines(fs))
    assert all("nothing is counted" in ln for ln in SF.base_lines(fs))


def test_NEGATIVE_pins_never_enter_a_count():
    rows = [_row("A")]
    by = _full("A", winner_on=0)
    base = SF.follow_stats(rows, _facts(by), LATE)
    pinned = {**by, **{(x.isoformat(), "PIN"): fact(high=9.0, winner=True) for x in SF._next_n(S, 3)}}
    assert SF.follow_stats(rows, _facts(pinned), LATE) == base


def test_first_listing_only_counts_and_too_few_names_for_an_interval():
    rows = [_row("A"), _row("A", N)]
    by = {**_full("A", N), **_full("A", winner_on=0)}
    fs = SF.follow_stats(rows, _facts(by), LATE)
    assert fs["by"]["1"]["first"]["n"] == 1 and fs["by"]["1"]["first"]["again"] == 1
    assert fs["by"]["1"]["first"]["ci"] is None
    assert "too few names for an interval" in SF.base_lines(fs)[1]


def test_NEGATIVE_a_day_whose_horizon_has_not_ended_is_not_due():
    rows = [_row("A")]
    fs = SF.follow_stats(rows, _facts(_full("A")), utc(N, "19:00"))
    assert all(fs["by"][str(k)]["days_due"] == 0 for k in SF.HORIZONS)
    assert SF.base_lines(fs)[0].endswith("no listing day has had 1 session yet; nothing is counted.")


# ── names / pinned ────────────────────────────────────────────────────────────────────────────────────────────────
def test_names_first_last_days_wins_and_since_counts_read_sessions_only():
    rows = [_row("A", P, winner=True), _row("A", S), _row("B", S)]
    facts = _facts({(S.isoformat(), "A"): fact(winner=True), (N.isoformat(), "A"): fact("no_bars", retry=True),
                    (D23.isoformat(), "A"): fact(winner=False), (P.isoformat(), "A"): fact(winner=True)})
    nm = SF.names(rows, facts)
    assert [x["symbol"] for x in nm] == ["A", "B"]                  # last listed DESC, then ticker
    a = nm[0]
    assert (a["first"], a["last"], a["days"], a["wins_listed"]) == (P.isoformat(), S.isoformat(), 2, 1)
    assert a["since_n"] == 2 and a["since_wins"] == 1               # S + 11-23 read; 11-20 retry; P is the first day
    rows2 = rows + [_row("C", N)]
    assert [x["symbol"] for x in SF.names(rows2, facts)] == ["C", "A", "B"]


# ── pins [C10] ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_pins_round_trip_and_tracked_from_since():
    st = fake_store()
    assert SF.pins(st) == []
    assert SF.pin(st, "pom", "2026-11-19", NIGHT)["ok"] is True
    assert SF.pin(st, "BRK.B", S, NIGHT)["ok"] is True
    assert [p["symbol"] for p in SF.pins(st)] == ["BRK.B", "POM"]
    assert SF.tracked(st, S, index=[]) == ["BRK.B", "POM"]
    assert SF.tracked(st, P, index=[]) == []                         # a pin before its since is not tracked
    assert SF.unpin(st, "POM")["ok"] is True and [p["symbol"] for p in SF.pins(st)] == ["BRK.B"]
    assert SF.unpin(st, "POM")["ok"] is False


@pytest.mark.parametrize("junk", ["", None, "1ABC", "AB C", "A1", "AB$", "X" * 40, 7, "../x"])
def test_NEGATIVE_a_junk_symbol_is_refused_and_nothing_written(junk):
    st = fake_store()
    res = SF.pin(st, junk, S, NIGHT)
    assert res["ok"] is False and res["error"] == "symbol" and st.get_state(SF.PINS_ID) == {}


def test_NEGATIVE_a_junk_since_or_a_faulted_pins_read_is_refused():
    st = fake_store()
    assert SF.pin(st, "POM", "11/19", NIGHT)["error"] == "since"
    st.coll(ST.STATE).fail_ids[SF.PINS_ID] = 5
    assert SF.pin(st, "POM", S, NIGHT)["error"] == "read_fault"
    st.coll(ST.STATE).fail_ids[SF.PINS_ID] = 0
    assert st.get_state(SF.PINS_ID) == {}


def test_tracked_holds_the_listed_names_of_the_last_follow_sessions():
    st, si = world()
    rec(st, si)
    have = SIT.index_dates(st)
    assert SF.tracked(st, S, index=have) == ["AAA", "BBB", "CCC"]
    tenth = SF._next_n(S, SF.FOLLOW_SESSIONS)[-1]
    assert SF.tracked(st, tenth, index=have) == ["AAA", "BBB", "CCC"]
    assert SF.tracked(st, SIT._next_day(tenth), index=have) == []
    assert SF.tracked(st, P, index=have) == []


# ── fill_night [C4] ───────────────────────────────────────────────────────────────────────────────────────────────
def _recorded():
    st, si = world()
    rec(st, si)
    return st


def test_fill_night_takes_its_own_budget_and_never_touches_the_ledgers(monkeypatch):
    st = _recorded()
    caps = []

    class Spy(SIT.Budget):
        def __init__(self, cap=SIT.MAX_LOADS):
            caps.append(cap)
            super().__init__(cap)
    ledger = SIT.Ctx(st, utc(N, "20:30"), budget=SIT.Budget(7))
    ledger.budget.loads, ledger.budget.split_calls = 3, 2
    budget_id = id(ledger.budget)
    monkeypatch.setattr(SIT, "Budget", Spy)
    out = SF.fill_night(st, utc(N, "20:30"), load_1m=lambda s, d: _minutes(d), split_lookup=lambda s, lo, hi: False,
                        share=ledger)
    assert caps == [SIT.MAX_LOADS]
    assert id(ledger.budget) == budget_id and (ledger.budget.loads, ledger.budget.split_calls) == (3, 2)
    assert ledger.budget.cap == 7 and ledger.budget.deferred == 0
    assert out["faults"] == [] and out["sessions"] == [S.isoformat(), N.isoformat()]
    assert set(out) == set(SF.NIGHT_KEYS)


def test_fill_night_oldest_first_and_one_write_per_changed_session():
    st = _recorded()
    SF.fill_night(st, utc(N, "20:30"), load_1m=lambda s, d: _minutes(d), split_lookup=lambda s, lo, hi: False)
    ops = [i for i, _u in st.coll(ST.STATE).ops if isinstance(i, str) and i.startswith("si_follow|")]
    assert ops == ["si_follow|%s" % S.isoformat(), "si_follow|%s" % N.isoformat()]
    facts = SF.read_facts(st, [S.isoformat(), N.isoformat()])
    assert sorted(facts[S.isoformat()]) == ["AAA", "BBB", "CCC"]
    a = facts[S.isoformat()]["AAA"]
    assert a["base_kind"] == "regular_close" and a["state"] == "ok"
    assert "base_kind" not in facts[N.isoformat()]["AAA"]             # N is not a listing day of AAA
    again = SF.fill_night(st, utc(N, "20:40"), load_1m=lambda s, d: pytest.fail("terminal facts re-asked"))
    assert again["facts"] == 0 and again["sessions"] == []


def test_a_load_the_shared_memo_holds_costs_no_unit():
    st = _recorded()
    calls = []
    load = lambda s, d: calls.append((s, d)) or _minutes(d)          # noqa: E731
    ledger = SIT.Ctx(st, utc(N, "20:30"))
    ledger.raw[("AAA", N.isoformat())] = _minutes(N)
    ledger.raw[("AAA", S.isoformat())] = _minutes(S)
    ledger.raw[("BBB", N.isoformat())] = None                        # a failed ledger load is asked again
    out = SF.fill_night(st, utc(N, "20:30"), load_1m=load, split_lookup=lambda s, lo, hi: False, share=ledger)
    assert ("AAA", N) not in calls and ("AAA", S) not in calls and ("BBB", N) in calls
    assert out["loads"] == 4


def test_NEGATIVE_budget_spent_leaves_the_fact_retry_and_the_next_night_asks_it():
    st = _recorded()
    out = SF.fill_night(st, utc(N, "20:30"), load_1m=lambda s, d: _minutes(d), split_lookup=lambda s, lo, hi: False,
                        max_loads=2)
    assert out["deferred_cap"] > 0 and out["pending"] > 0
    pend = [s for s, f in SF.read_facts(st, [N.isoformat()])[N.isoformat()].items() if f["retry"]]
    assert pend
    SF.fill_night(st, utc(N, "21:00"), load_1m=lambda s, d: _minutes(d), split_lookup=lambda s, lo, hi: False)
    assert all(not f["retry"] for f in SF.read_facts(st, [N.isoformat()])[N.isoformat()].values())


def test_NEGATIVE_fill_night_never_raises(monkeypatch):
    st = _recorded()
    monkeypatch.setattr(SF, "tracked", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    out = SF.fill_night(st, utc(N, "20:30"), load_1m=lambda s, d: None)
    assert out["sessions"] == [] and any(f.startswith("session:") for f in out["faults"])
    monkeypatch.setattr(SF, "_ctx", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("y")))
    assert SF.fill_night(st, utc(N, "20:30"))["faults"] == ["night:RuntimeError"]


def test_NEGATIVE_a_faulted_facts_read_never_overwrites():
    st = _recorded()
    st.set_state("si_follow|%s" % S.isoformat(), {"date": S.isoformat(), "facts": [dict(BASE, symbol="AAA")]})
    st.coll(ST.STATE).fail_ids["si_follow|%s" % S.isoformat()] = 1
    out = SF.fill_night(st, utc(N, "20:30"), load_1m=lambda s, d: _minutes(d), split_lookup=lambda s, lo, hi: False)
    assert "read:%s" % S.isoformat() in out["faults"]
    assert [f["symbol"] for f in st.get_state("si_follow|%s" % S.isoformat())["facts"]] == ["AAA"]


def test_NEGATIVE_a_raise_inside_the_follow_keeps_record_night_whole(monkeypatch):
    st, si = world()
    monkeypatch.setattr(SF, "fill_night", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    out = SIT.record_night(NIGHT, store=st, **dict(SEAMS, si_read=si))
    assert set(out) == set(SIT.NIGHT_KEYS) and out["rows"] == 3 and out["stats"] is True
    assert out["follow"] is None and "follow:RuntimeError" in out["faults"]


def test_record_night_runs_the_follow_after_the_ledger_with_its_own_budget():
    st, si = world()
    out = SIT.record_night(NIGHT, store=st, **dict(SEAMS, si_read=si))
    assert isinstance(out["follow"], dict) and out["follow"]["sessions"] == [S.isoformat()]
    s = st.get_state(SIT.STATS_ID)
    assert set(s["follow"]["by"]) == {str(k) for k in SF.HORIZONS} and [x["symbol"] for x in s["names"]] == [
        "AAA", "BBB", "CCC"]


def test_plan_makes_no_outside_call_and_its_units_match_a_real_run():
    st = _recorded()
    boom = lambda *a, **k: pytest.fail("plan made an outside call")  # noqa: E731
    before = copy.deepcopy(st.coll(ST.STATE).docs)
    p = SF.plan(st, utc(N, "20:30"))
    assert st.coll(ST.STATE).docs == before
    units = {x["session"]: x["units"] for x in p["sessions"]}
    assert units[S.isoformat()] == 0 and units[N.isoformat()] == 9 and p["units"] == 9 and p["cap"] == SIT.MAX_LOADS
    assert all(v == 0 for k, v in units.items() if k not in (S.isoformat(), N.isoformat()))
    out = SF.fill_night(st, utc(N, "20:30"), load_1m=lambda s, d: _minutes(d), split_lookup=lambda s, lo, hi: False)
    assert out["loads"] + out["split_calls"] == p["units"]
    del boom


# ── served [C11] ──────────────────────────────────────────────────────────────────────────────────────────────────
def _served_world():
    st, si = world()
    SIT.record_night(NIGHT, store=st, **dict(SEAMS, si_read=si))
    SIT.record_night(utc(N, "20:15"), store=st, **dict(SEAMS, si_read=si, load_1m=lambda s, d: _minutes(d)))
    return st


def test_served_follow_block_caveat_verbatim_and_keys():
    st = _served_world()
    b = SIT.served_block(st, N, utc(N, "20:30"))
    f = b["follow"]
    assert set(f) == set(SF.SERVED_KEYS)
    assert f["caveat"] == ("These are the names we listed — winners and losers both count. It is a record of what "
                           "happened next, not a test. Names that were not on the 🩳 list on the same days are not "
                           "followed, so this cannot say whether short interest made the difference. UNMEASURED.")
    assert [x["symbol"] for x in f["names"]] == ["AAA", "BBB", "CCC"]
    assert f["pinned"] == [] and f["pinned_empty_text"] == SF.PINNED_EMPTY_TEXT
    assert b["heads"][-1] == SIT.FOLLOW_HEAD
    key = SIT.FOLLOW_HEAD[0]
    assert all(key in r["cells"] for d in b["days"] for r in d["rows"])


def test_NEGATIVE_no_served_string_says_signal_edge_bounce_or_carried():
    st = _served_world()
    SF.pin(st, "POM", S, NIGHT)
    text = json.dumps(SIT.served_block(st, N, utc(N, "20:30"))["follow"], ensure_ascii=False)
    for bad in (r"\bsignals?\b", r"\bedges?\b", r"bounc", r"\bcarried\b"):
        assert re.search(bad, text, re.I) is None, bad
    assert re.search(r"bounc|\bsignal|\bedge\b|carried", SF.rule_text(), re.I) is None


def test_NEGATIVE_a_follow_fault_serves_follow_none_and_the_ledger_block_otherwise_identical(monkeypatch):
    st = _served_world()
    good = SIT.served_block(st, N, utc(N, "20:30"))
    monkeypatch.setattr(SF, "served", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    bad = SIT.served_block(st, N, utc(N, "20:30"))
    assert bad["follow"] is None and isinstance(good["follow"], dict)
    key = SIT.FOLLOW_HEAD[0]

    def strip(b):
        b = copy.deepcopy(b)
        b.pop("follow")
        for d in b["days"]:
            for r in d["rows"]:
                r["cells"].pop(key)
        return b
    assert strip(bad) == strip(good)
    assert all(r["cells"][key] == SIT.DASH for d in bad["days"] for r in d["rows"])


def test_the_pinned_table_is_apart_and_never_in_the_names():
    st = _served_world()
    SF.pin(st, "POM", S, NIGHT)
    f = SIT.served_block(st, N, utc(N, "20:30"))["follow"]
    assert [p["symbol"] for p in f["pinned"]] == ["POM"] and f["pinned_empty_text"] is None
    assert "POM" not in [x["symbol"] for x in f["names"]]
    assert f["pinned"][0]["cells"]["days"].startswith("fills at the next")      # pinned after the night's counts
    SIT.record_night(utc(D23, "20:15"), store=st, **dict(SEAMS, si_read=lambda syms: {}, load_1m=lambda s, d: None))
    f = SIT.served_block(st, D23, utc(D23, "20:30"))["follow"]
    assert f["pinned"][0]["cells"]["since"] == S.isoformat() and f["pinned"][0]["cells"]["days"] == "0"


def test_NEGATIVE_no_recorded_day_is_the_empty_ledger_block_with_no_follow():
    b = SIT.served_block(fake_store(), S, NIGHT)
    assert b["follow"] is None and b["heads"] == SIT.day_heads()


# ── one read of the follow facts per 🩳 block build (2026-11-26 refix) ──────────────────────────────────────────────
def _count_fact_reads(monkeypatch):
    seen = []
    real = SIT.state_read

    def spy(st, sid):
        if sid.startswith(SF.STATE_FMT.split("{")[0]):
            seen.append(sid)
        return real(st, sid)
    monkeypatch.setattr(SIT, "state_read", spy)
    return seen


@pytest.mark.parametrize("drop_stats", [False, True])
def test_served_block_reads_each_follow_fact_doc_once(monkeypatch, drop_stats):
    st = _served_world()
    if drop_stats:                                              # the live-count fallback path reads fact_days too
        st.set_state(SIT.STATS_ID, {"follow": None, "names": None})
    if drop_stats:
        assert not isinstance((st.get_state(SIT.STATS_ID) or {}).get("follow"), dict)
    seen = _count_fact_reads(monkeypatch)
    b = SIT.served_block(st, N, utc(N, "20:30"))
    assert isinstance(b["follow"], dict)
    assert seen and len(seen) == len(set(seen)), seen


def test_NEGATIVE_without_handed_facts_forwards_and_served_read_the_same_docs_twice(monkeypatch):
    st = _served_world()
    dates = SIT.index_dates(st)
    by_day = SIT._rows_for_days(st, sorted(dates)[-SIT.SPAN_SESSIONS:][::-1])
    seen = _count_fact_reads(monkeypatch)
    SF.forwards(st, by_day, utc(N, "20:30"))
    SF.served(st, dates, by_day, utc(N, "20:30"))
    assert len(seen) > len(set(seen))                           # the cost the refix removes, pinned load-bearing


def test_handed_facts_give_the_same_forwards_and_served_as_reading_them():
    st = _served_world()
    now = utc(N, "20:30")
    dates = [S.isoformat(), N.isoformat()]
    by_day = SIT._rows_for_days(st, dates[::-1])
    cf = SF.cell_facts(st, by_day, now)
    assert SF.forwards(st, by_day, now, facts=cf) == SF.forwards(st, by_day, now)
    assert SF.served(st, dates, by_day, now, facts=cf) == SF.served(st, dates, by_day, now)


def test_NEGATIVE_read_facts_with_have_never_rereads_a_held_session_and_still_raises_on_an_unheld_fault(monkeypatch):
    st = _served_world()
    held = {S.isoformat(): {"AAA": fact()}}
    faults = lambda st_, sid: None                              # noqa: E731 — every read is a fault
    monkeypatch.setattr(SIT, "state_read", faults)
    assert SF.read_facts(st, [S.isoformat()], have=held) == held
    with pytest.raises(SIT.ReadFault):
        SF.read_facts(st, [S.isoformat(), N.isoformat()], have=held)
    with pytest.raises(SIT.ReadFault):
        SF.read_facts(st, [S.isoformat()], have={})


def test_NEGATIVE_a_cell_facts_fault_serves_follow_none_and_dash_cells(monkeypatch):
    st = _served_world()
    monkeypatch.setattr(SF, "cell_facts", lambda *a, **k: (_ for _ in ()).throw(SIT.ReadFault("x")))
    b = SIT.served_block(st, N, utc(N, "20:30"))
    key = SIT.FOLLOW_HEAD[0]
    assert b["follow"] is None and all(r["cells"][key] == SIT.DASH for d in b["days"] for r in d["rows"])


# ── the script ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_script_plan_and_dry_write_nothing_and_never_call_the_1_minute_seam(capsys):
    from scripts import gajjala_si_follow_backfill as BF
    st = _recorded()
    before = copy.deepcopy(st.coll(ST.STATE).docs)
    assert BF.main(["--plan"], store=st, now=utc(N, "20:30")) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["units"] == 9
    boom = lambda s, d: pytest.fail("the 1-minute seam was asked")    # noqa: E731
    out = BF.run(st, utc(N, "20:30"), dry=True, load_1m=boom, split_lookup=lambda s, lo, hi: False)
    assert st.coll(ST.STATE).docs == before and [x["session"] for x in out] == [S.isoformat(), N.isoformat()]
    out = BF.run(st, utc(N, "20:30"), load_1m=boom, split_lookup=lambda s, lo, hi: False)
    facts = SF.read_facts(st, [S.isoformat(), N.isoformat()])
    assert all(not f["retry"] for f in facts[S.isoformat()].values())        # stored reads: free and terminal
    assert all(f["retry"] and f["load"] == "deferred" for f in facts[N.isoformat()].values())


def test_NEGATIVE_script_load_without_max_loads_exits_non_zero_and_refuses_in_regular_hours(capsys):
    from scripts import gajjala_si_follow_backfill as BF
    st = _recorded()
    assert BF.main(["--load"], store=st, now=utc(N, "20:30")) != 0
    assert json.loads(capsys.readouterr().out)["error"] == "max_loads_required"
    assert BF.main(["--load", "--max-loads", "0"], store=st, now=utc(N, "20:30")) != 0
    capsys.readouterr()
    assert BF.main(["--load", "--max-loads", "5"], store=st, now=utc(N, "10:00")) != 0
    assert json.loads(capsys.readouterr().out)["error"] == "regular_hours"
    assert BF.in_rth(utc(N, "09:30")) and BF.in_rth(utc(N, "15:59")) and not BF.in_rth(utc(N, "16:00"))
    assert not BF.in_rth(utc(N, "09:29"))


def test_script_load_uses_one_budget_of_max_loads():
    from scripts import gajjala_si_follow_backfill as BF
    st = _recorded()
    out = BF.run(st, utc(N, "20:30"), load=True, max_loads=3, load_1m=lambda s, d: _minutes(d),
                 split_lookup=lambda s, lo, hi: False)
    assert out[-1]["loads"] + out[-1]["split_calls"] == 3 and out[-1]["deferred_cap"] > 0


def test_script_pins(capsys):
    from scripts import gajjala_si_follow_backfill as BF
    st = fake_store()
    assert BF.main(["--pin", "POM,NCPL", "--since", "2026-11-19"], store=st, now=NIGHT) == 0
    capsys.readouterr()
    assert BF.main(["--pins"], store=st, now=NIGHT) == 0
    assert [p["symbol"] for p in json.loads(capsys.readouterr().out)["pins"]] == ["NCPL", "POM"]
    assert BF.main(["--pin", "POM"], store=st, now=NIGHT) == 2                      # no --since
    assert BF.main(["--pin", "1BAD", "--since", "2026-11-19"], store=st, now=NIGHT) == 2
    assert BF.main(["--unpin", "NCPL"], store=st, now=NIGHT) == 0
    assert [p["symbol"] for p in SF.pins(st)] == ["POM"]


# ── the script: --night (refix 2026-11-26 — ship gate §5.2c asks for ONE night, not the summed range) ──────────────
def test_script_night_prints_the_look_back_plan_not_the_range(capsys):
    from scripts import gajjala_si_follow_backfill as BF
    st = _recorded()
    before = copy.deepcopy(st.coll(ST.STATE).docs)
    assert BF.main(["--night"], store=st, now=LATE) == 0
    night = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert night == json.loads(json.dumps(SF.plan(st, LATE), default=str))
    assert [x["session"] for x in night["sessions"]] == [d.isoformat() for d in SF._sessions(LATE)]
    assert night["cap"] == SIT.MAX_LOADS and night["over_cap"] == (night["units"] > SIT.MAX_LOADS)
    assert BF.main(["--plan"], store=st, now=LATE) == 0
    rng = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert [x["session"] for x in rng["sessions"]] == BF.sessions(st, LATE)
    assert [x["session"] for x in rng["sessions"]] != [x["session"] for x in night["sessions"]]
    assert S.isoformat() in [x["session"] for x in rng["sessions"]]
    assert S.isoformat() not in [x["session"] for x in night["sessions"]]
    assert st.coll(ST.STATE).docs == before


def test_script_night_on_tonight_matches_the_real_night_units(capsys):
    from scripts import gajjala_si_follow_backfill as BF
    st = _recorded()
    assert BF.main(["--night"], store=st, now=utc(N, "20:30")) == 0
    night = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    out = SF.fill_night(st, utc(N, "20:30"), load_1m=lambda s, d: _minutes(d), split_lookup=lambda s, lo, hi: False)
    assert night["units"] == out["loads"] + out["split_calls"] == 9


def test_NEGATIVE_script_night_over_the_cap_says_so(capsys, monkeypatch):
    from scripts import gajjala_si_follow_backfill as BF
    st = _recorded()
    monkeypatch.setattr(SIT, "MAX_LOADS", 8)
    assert BF.main(["--night"], store=st, now=utc(N, "20:30")) == 0
    night = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert night["units"] == 9 and night["cap"] == 8 and night["over_cap"] is True


def test_NEGATIVE_script_night_refuses_a_range_writes_nothing_and_asks_no_provider(capsys, monkeypatch):
    from scripts import gajjala_si_follow_backfill as BF
    st = _recorded()
    before = copy.deepcopy(st.coll(ST.STATE).docs)
    boom = lambda *a, **k: pytest.fail("--night made an outside call")  # noqa: E731
    monkeypatch.setattr(SIT, "default_load_1m", boom)
    assert BF.main(["--night", "--from", "2026-11-19"], store=st, now=utc(N, "20:30")) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "night_takes_no_range"
    assert BF.main(["--night", "--to", "2026-11-20"], store=st, now=utc(N, "20:30")) == 2
    capsys.readouterr()
    assert BF.main(["--night"], store=st, now=utc(N, "20:30")) == 0
    assert st.coll(ST.STATE).docs == before


def test_NEGATIVE_script_night_on_an_index_read_fault_exits_non_zero(capsys, monkeypatch):
    from scripts import gajjala_si_follow_backfill as BF
    st = _recorded()
    monkeypatch.setattr(SIT, "index_dates", lambda *a, **k: (_ for _ in ()).throw(SIT.ReadFault("x")))
    assert BF.main(["--night"], store=st, now=utc(N, "20:30")) == 1
    assert "index_read" in json.loads(capsys.readouterr().out)["faults"]
