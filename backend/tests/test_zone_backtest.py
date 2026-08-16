"""Walk-forward backtest of the demand-zone re-entry rule.

Ajay 2026-08-16: "I want you to look at data historically and tell me if buy
zones worked.. Record further if you want but I want you to back test and record
and load them up there."

A backtest that is wrong is worse than none — it launders a bad rule into a
number he will size positions on. These pin the five no-lookahead rules and the
three ways the result could be flattered:

  * counting the same multi-day episode as several trades
  * scoring an ambiguous bar (stop AND target in range) as a win
  * counting unresolved trades as anything other than unresolved

All synthetic. No network, no ledger, no scan on disk.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")

from supply_demand import zone_backtest as ZB  # noqa: E402


def frame(rows):
    """[(date, open, high, low, close)] -> the OHLC frame the rule consumes."""
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame(
        {"open": [r[1] for r in rows], "high": [r[2] for r in rows],
         "low": [r[3] for r in rows], "close": [r[4] for r in rows],
         "volume": [1_000_000] * len(rows)},
        index=idx)


def flat(n, px=100.0, start="2020-01-01"):
    days = pd.bdate_range(start, periods=n)
    return [(d.strftime("%Y-%m-%d"), px, px, px, px) for d in days]


# --------------------------------------------------------------------------
# Rule 1 — the lookahead firewall
# --------------------------------------------------------------------------
def test_upto_is_inclusive_and_sees_nothing_after():
    df = frame(flat(10))
    got = ZB._upto(df, 4)
    assert len(got) == 5
    assert str(got.index[-1])[:10] == str(df.index[4])[:10]


def test_the_decision_function_reads_only_its_frame():
    """decide_from_frame must not fetch prices, read a clock, or hit a cache —
    otherwise every historical decision is contaminated by today."""
    import inspect
    from supply_demand import demand_reentry as DR
    src = inspect.getsource(DR.decide_from_frame)
    for forbidden in ("load_prices", "datetime.now", "time.time", "_cache",
                      "cached_or_warm", "fetch_trades"):
        assert forbidden not in src, f"decide_from_frame reaches for {forbidden}"


# --------------------------------------------------------------------------
# Rule 2 — entry is the NEXT bar's open
# --------------------------------------------------------------------------
def test_entry_is_the_next_bars_open_not_the_decision_close():
    rows = flat(5)
    # Decision bar closes at 100; next bar OPENS at 110 (a gap up).
    rows[3] = ("2020-01-06", 110.0, 115.0, 109.0, 112.0)
    df = frame(rows)
    res = ZB.walk_forward(df, entry_idx=3, stop=90.0, target=115.0)
    # Target 115 is the entry bar's high -> filled from the 110 open.
    assert res["outcome"] == ZB.OUTCOME_WIN
    assert res["net_pct"] == pytest.approx(ZB._net(110.0, 115.0))


# --------------------------------------------------------------------------
# Rules 3 + 4 — walking forward, and the ambiguous bar
# --------------------------------------------------------------------------
def test_target_before_stop_is_a_win():
    rows = flat(6)
    rows[2] = ("2020-01-03", 100.0, 112.0, 99.0, 111.0)     # target
    df = frame(rows)
    res = ZB.walk_forward(df, entry_idx=1, stop=90.0, target=110.0)
    assert res["outcome"] == ZB.OUTCOME_WIN and res["bars"] == 1


def test_stop_before_target_is_a_loss():
    rows = flat(6)
    rows[2] = ("2020-01-03", 100.0, 101.0, 88.0, 89.0)      # stop
    df = frame(rows)
    res = ZB.walk_forward(df, entry_idx=1, stop=90.0, target=110.0)
    assert res["outcome"] == ZB.OUTCOME_LOSS and res["bars"] == 1


def test_a_bar_containing_both_levels_is_scored_a_loss():
    """RULE 4. A daily bar cannot say which came first, and assuming the win
    inflates every result. This single line is worth several points of win rate."""
    rows = flat(6)
    rows[2] = ("2020-01-03", 100.0, 112.0, 88.0, 100.0)     # both
    df = frame(rows)
    res = ZB.walk_forward(df, entry_idx=1, stop=90.0, target=110.0)
    assert res["outcome"] == ZB.OUTCOME_LOSS
    assert res["ambiguous_bar"] is True


def test_max_gain_is_tracked_even_on_a_loss():
    rows = flat(8)
    rows[2] = ("2020-01-03", 100.0, 108.0, 99.0, 107.0)     # ran up first
    rows[4] = ("2020-01-07", 100.0, 101.0, 88.0, 89.0)      # then stopped
    df = frame(rows)
    res = ZB.walk_forward(df, entry_idx=1, stop=90.0, target=120.0)
    assert res["outcome"] == ZB.OUTCOME_LOSS
    assert res["max_gain_pct"] == pytest.approx(8.0, abs=0.1)


# --------------------------------------------------------------------------
# Unresolved trades
# --------------------------------------------------------------------------
def test_running_out_of_data_is_open_not_a_win():
    df = frame(flat(6))
    res = ZB.walk_forward(df, entry_idx=1, stop=90.0, target=110.0, max_hold=100)
    assert res["outcome"] == ZB.OUTCOME_OPEN


def test_hitting_the_hold_cap_is_expired_not_a_win():
    df = frame(flat(40))
    res = ZB.walk_forward(df, entry_idx=1, stop=90.0, target=110.0, max_hold=5)
    assert res["outcome"] == ZB.OUTCOME_TIMEOUT


def test_open_and_expired_are_excluded_from_the_win_rate():
    obs = [{"outcome": ZB.OUTCOME_WIN, "net_pct": 3.0, "bars_to_outcome": 4},
           {"outcome": ZB.OUTCOME_LOSS, "net_pct": -2.0, "bars_to_outcome": 2},
           {"outcome": ZB.OUTCOME_OPEN, "net_pct": 1.0, "bars_to_outcome": 60},
           {"outcome": ZB.OUTCOME_TIMEOUT, "net_pct": 0.5, "bars_to_outcome": 60}]
    s = ZB.summarize(obs)
    assert s["n"] == 4 and s["raced"] == 2
    assert s["win_pct"] == pytest.approx(50.0)
    assert s["open"] == 1 and s["expired"] == 1


def test_expectancy_is_probability_weighted_not_an_average_of_returns():
    obs = ([{"outcome": ZB.OUTCOME_WIN, "net_pct": 10.0, "bars_to_outcome": 3}]
           + [{"outcome": ZB.OUTCOME_LOSS, "net_pct": -2.0, "bars_to_outcome": 1}] * 3)
    s = ZB.summarize(obs)
    assert s["win_pct"] == pytest.approx(25.0)
    # 0.25*10 + 0.75*(-2) = 1.0
    assert s["expectancy_pct"] == pytest.approx(1.0)


def test_summarize_on_nothing_reports_nothing_rather_than_zero():
    s = ZB.summarize([])
    assert s["n"] == 0 and s["raced"] == 0
    assert s["win_pct"] is None and s["expectancy_pct"] is None


# --------------------------------------------------------------------------
# Same-bar wins — the trivially close target
# --------------------------------------------------------------------------
def test_same_bar_wins_are_counted_and_reported():
    """135 of 694 real backtested wins hit target on the ENTRY bar, because the
    first supply band sat a fraction above entry. They are wins, but they must
    be visible or the win rate reads as skill."""
    obs = [{"outcome": ZB.OUTCOME_WIN, "net_pct": 0.15, "bars_to_outcome": 0},
           {"outcome": ZB.OUTCOME_WIN, "net_pct": 6.0, "bars_to_outcome": 7},
           {"outcome": ZB.OUTCOME_LOSS, "net_pct": -2.0, "bars_to_outcome": 3}]
    s = ZB.summarize(obs)
    assert s["same_bar_wins"] == 1
    assert s["same_bar_win_pct"] == pytest.approx(50.0)


def test_the_summary_points_at_expectancy_not_win_rate():
    """A guard on the wording, because this is the number that misleads."""
    s = ZB.summarize([{"outcome": ZB.OUTCOME_WIN, "net_pct": 1.0, "bars_to_outcome": 1}])
    assert "expectancy_pct" in s["note"]


# --------------------------------------------------------------------------
# Costs
# --------------------------------------------------------------------------
def test_costs_are_charged_on_both_sides():
    gross = (110.0 / 100.0 - 1.0) * 100.0
    assert ZB._net(100.0, 110.0) < gross
    assert ZB._net(100.0, 110.0) == pytest.approx(
        gross - 2 * ZB.COST_BPS_PER_SIDE / 100.0, abs=1e-6)


def test_a_flat_round_trip_loses_the_costs():
    assert ZB._net(100.0, 100.0) < 0


# --------------------------------------------------------------------------
# Episode de-duplication
# --------------------------------------------------------------------------
def test_a_multi_day_stay_inside_a_band_is_one_trade_not_many(monkeypatch):
    """Without the cooldown, price sitting in a band for a fortnight records as
    a dozen trades and one good week dominates the sample."""
    df = frame(flat(ZB.MIN_BARS + 60))

    plan = {"stop": 90.0, "target": 110.0, "entry_ref": 100.0, "rr": 2.0}
    monkeypatch.setattr(
        "supply_demand.demand_reentry.decide_from_frame",
        lambda d, s: {"is_reentry": True, "plan": plan,
                      "entry_zone": {"lo": 95.0, "hi": 99.0, "touches": 3,
                                     "strength": 70},
                      "fell_from_pct": 12.0})
    obs = ZB.observations_for("TEST", df, stride=1)
    dates = [o["et_date"] for o in obs]
    assert len(obs) == len(set(dates))
    # Every recorded episode is at least the cooldown apart.
    idxs = [list(df.index.strftime("%Y-%m-%d")).index(d) for d in dates]
    assert all(b - a >= ZB.EPISODE_COOLDOWN_BARS for a, b in zip(idxs, idxs[1:]))


def test_a_plan_with_no_target_is_skipped_not_scored_as_flat(monkeypatch):
    df = frame(flat(ZB.MIN_BARS + 30))
    monkeypatch.setattr(
        "supply_demand.demand_reentry.decide_from_frame",
        lambda d, s: {"is_reentry": True,
                      "plan": {"stop": 90.0, "target": None, "rr": None},
                      "entry_zone": {"lo": 95.0, "hi": 99.0}})
    assert ZB.observations_for("TEST", df) == []


def test_an_inverted_plan_is_skipped(monkeypatch):
    """target below stop is not a trade — it is a bad plan, and scoring it
    would manufacture a guaranteed outcome."""
    df = frame(flat(ZB.MIN_BARS + 30))
    monkeypatch.setattr(
        "supply_demand.demand_reentry.decide_from_frame",
        lambda d, s: {"is_reentry": True,
                      "plan": {"stop": 110.0, "target": 90.0, "rr": -1.0},
                      "entry_zone": {"lo": 95.0, "hi": 99.0}})
    assert ZB.observations_for("TEST", df) == []


def test_a_frame_too_short_to_decide_produces_nothing():
    assert ZB.observations_for("TEST", frame(flat(50))) == []
    assert ZB.observations_for("TEST", None) == []


def test_non_reentry_days_are_not_recorded(monkeypatch):
    df = frame(flat(ZB.MIN_BARS + 30))
    monkeypatch.setattr("supply_demand.demand_reentry.decide_from_frame",
                        lambda d, s: {"is_reentry": False, "plan": {}})
    assert ZB.observations_for("TEST", df) == []


# --------------------------------------------------------------------------
# One rule, not two
# --------------------------------------------------------------------------
def test_the_backtest_calls_the_live_decision_function():
    """The whole point of extracting decide_from_frame. If the backtest ever
    grows its own copy of the rule, it stops testing what Ajay trades."""
    import inspect
    src = inspect.getsource(ZB.observations_for)
    assert "decide_from_frame" in src
    for reimplemented in ("price_zones.compute", "is_falling_knife", "reentry_read"):
        assert reimplemented not in src, (
            f"observations_for reimplements {reimplemented} instead of calling "
            "the live decision")


def test_recorded_rows_are_marked_backtested():
    """A backtested row must never be mistaken for a live observation."""
    df = frame(flat(ZB.MIN_BARS + 40))
    import supply_demand.demand_reentry as DR
    orig = DR.decide_from_frame
    DR.decide_from_frame = lambda d, s: {
        "is_reentry": True, "plan": {"stop": 90.0, "target": 110.0, "rr": 2.0},
        "entry_zone": {"lo": 95.0, "hi": 99.0, "touches": 3, "strength": 70},
        "fell_from_pct": 12.0}
    try:
        obs = ZB.observations_for("TEST", df)
    finally:
        DR.decide_from_frame = orig
    assert obs and all(o["backtested"] is True for o in obs)
    assert all(o["kind"] == ZB.LEDGER_KIND for o in obs)
