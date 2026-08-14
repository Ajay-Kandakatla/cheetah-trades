"""Liquidity sweeps, the falling-knife guard, and the backtest harness.

Ajay 2026-08-13 asked for a supply/demand strategy independent of Minervini,
built on demand zones + prints + dark pools, and then asked for it to be
backtested. It was, and it FAILED — see docs/supply_demand/
liquidity_sweep_methodology.md for the numbers. These tests exist so that:

  * the sweep detector stays honest (a pierce that never reclaims is `broken`,
    not a setup),
  * the trade plan can never again quote a target below its own entry,
  * the backtest can never quietly acquire lookahead, which is the one bug that
    would turn a losing strategy into a winning-looking one.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import sd_backtest as BT
from supply_demand import sd_liquidity as liq
from supply_demand import sd_sweep as sweep


def _bars(rows, start="2026-08-03 09:30", freq="1min"):
    """rows = [(low, high, close, volume)]"""
    df = pd.DataFrame(rows, columns=["low", "high", "close", "volume"])
    df["open"] = df["close"]
    df.index = pd.date_range(start, periods=len(df), freq=freq, tz="UTC")
    return df


# ── find_sweep: the three states ─────────────────────────────────────────────
def test_pierce_then_reclaim_is_a_sweep():
    b = _bars([(101, 106, 104, 1000), (102, 106, 105, 1000),
               (100.5, 105, 101, 1100), (98.5, 103, 99.5, 3000),
               (101, 104, 103, 1200), (102, 105, 104, 1000)])
    s = liq.find_sweep(b, 100.0, 106.0)
    assert s["state"] == "swept"
    assert s["sweep_low"] == 98.5
    assert s["pierce_pct"] == pytest.approx(1.5, abs=0.05)
    assert s["reclaim_bars"] == 1
    assert s["sweep_volume_x"] and s["sweep_volume_x"] > 1


def test_pierce_without_reclaim_is_broken_not_swept():
    """The distinction the whole idea rests on: a level that breaks and stays
    broken is the OPPOSITE signal and must never read as a buy setup."""
    b = _bars([(101, 106, 104, 1000), (102, 106, 105, 1000),
               (100.5, 105, 101, 1100), (98.5, 103, 99.5, 3000),
               (97, 99, 97.5, 1200), (96, 98, 96.5, 1300)])
    assert liq.find_sweep(b, 100.0, 106.0)["state"] == "broken"


def test_never_pierced_is_intact():
    b = _bars([(101, 106, 104, 1000), (100.5, 105, 103, 1100),
               (100.2, 104, 103, 900), (101, 105, 104, 950),
               (100.8, 105, 104, 900), (101, 106, 105, 1000)])
    assert liq.find_sweep(b, 100.0, 106.0)["state"] == "intact"


def test_a_quiet_dip_without_volume_is_not_a_sweep():
    """No absorption = nobody was filling. Just a drift through the level."""
    b = _bars([(101, 106, 104, 1000), (102, 106, 105, 1000),
               (101, 105, 104, 1000), (98.5, 103, 99.5, 100),
               (101, 104, 103, 1000), (102, 105, 104, 1000)])
    assert liq.find_sweep(b, 100.0, 106.0, min_vol_x=1.3)["state"] != "swept"


def test_a_collapse_is_not_a_stop_run():
    """Beyond max_pierce_pct it is a breakdown, whatever it does afterwards."""
    b = _bars([(101, 106, 104, 1000), (102, 106, 105, 1000),
               (101, 105, 104, 1000), (80, 103, 82, 5000),
               (101, 104, 103, 1200), (102, 105, 104, 1000)])
    assert liq.find_sweep(b, 100.0, 106.0, max_pierce_pct=4.0)["state"] != "swept"


def test_find_sweep_handles_degenerate_input():
    assert liq.find_sweep(None, 100, 106)["state"] == "intact"
    assert liq.find_sweep(_bars([(1, 2, 1.5, 10)] * 3), 100, 106)["state"] == "intact"
    assert liq.find_sweep(_bars([(1, 2, 1.5, 10)] * 10), 106, 100)["state"] == "intact"


def test_stop_shelf_sits_under_the_floor():
    shelf = liq.stop_shelf(100.0, pct=1.0)
    assert shelf["top"] == 100.0 and shelf["bottom"] == 99.0
    assert liq.stop_shelf(0) is None


# ── the falling-knife guard (neutral — no Minervini) ─────────────────────────
def test_knife_needs_both_falling_lows_and_a_falling_average():
    falling = {"trend": "falling"}
    rising = {"trend": "rising"}
    assert liq.is_falling_knife(falling, 100, ma50=90, ma50_prior=110) is True
    # one shakeout low inside an uptrend must not disqualify
    assert liq.is_falling_knife(falling, 100, ma50=110, ma50_prior=90) is False
    assert liq.is_falling_knife(rising, 100, ma50=90, ma50_prior=110) is False


def test_structure_read_detects_lower_lows():
    """The CIEN shape: 424 -> 404 -> 359 -> 323."""
    lows, closes = [], []
    for base in (424, 404, 359, 323):
        lows += [base + 20] * 6 + [base] + [base + 20] * 6
        closes += [base + 25] * 13
    st = liq.structure_read(closes, lows, swing_window=5)
    assert st["trend"] == "falling"
    assert st["last_two"][1] < st["last_two"][0]


def test_structure_read_is_unclear_without_enough_bars():
    assert liq.structure_read([1, 2], [1, 2])["trend"] == "unclear"


# ── the trade plan ───────────────────────────────────────────────────────────
def test_plan_targets_the_first_supply_ABOVE_the_band():
    """REGRESSION 2026-08-13: the target used to come from the nearest
    resistance above SPOT, which handed KLAC a 209.72 target under a
    211.94-212.77 entry band — a target below the entry."""
    p = sweep.plan_from_sweep(sweep_low=207.69, band_lo=208.63, band_hi=210.93,
                              last_price=209.39,
                              supply_zones=[{"lo": 209.72, "hi": 210.0},
                                            {"lo": 212.64, "hi": 213.5}])
    assert p["valid"] is True
    assert p["target"] == 212.64                 # NOT 209.72
    assert p["target"] > p["entry_high"]
    assert p["rr"] and p["rr"] > 0


def test_plan_is_invalid_once_price_is_back_below_the_swept_low():
    """REGRESSION: this used to emit a plan with risk_pct None because the
    'stop' sat above the current price — a failed setup shown as a trade."""
    p = sweep.plan_from_sweep(210.29, 211.94, 212.77, last_price=209.39,
                              supply_zones=[{"lo": 220.0, "hi": 221.0}])
    assert p["valid"] is False
    assert "already failed" in p["reason"]
    assert p["rr"] is None


def test_plan_entry_ref_is_clamped_into_the_band():
    p = sweep.plan_from_sweep(99.0, 100.0, 106.0, last_price=130.0,
                              supply_zones=[{"lo": 140.0, "hi": 141.0}])
    assert p["entry_ref"] == 106.0               # not 130
    p2 = sweep.plan_from_sweep(99.0, 100.0, 106.0, last_price=103.0,
                               supply_zones=[{"lo": 140.0, "hi": 141.0}])
    assert p2["entry_ref"] == 103.0


def test_plan_stop_is_under_the_defended_low():
    p = sweep.plan_from_sweep(99.0, 100.0, 106.0, 103.0, [{"lo": 120.0}])
    assert p["stop"] < 99.0


def test_plan_without_overhead_supply_has_no_target():
    p = sweep.plan_from_sweep(99.0, 100.0, 106.0, 103.0, [])
    assert p["valid"] is True and p["target"] is None and p["rr"] is None


# ── backtest integrity ───────────────────────────────────────────────────────
def test_window_upto_cannot_see_the_future():
    """THE test. If this breaks, every backtest number becomes fiction."""
    idx = pd.date_range("2026-08-01", periods=60 * 24 * 12, freq="1min", tz="UTC")
    df = pd.DataFrame({"low": 1.0, "high": 2.0, "close": 1.5, "open": 1.5,
                       "volume": 10}, index=idx)
    from datetime import date
    w = BT._window_upto(df, date(2026, 8, 6), sessions=10)
    assert w is not None
    assert w.index.max() < pd.Timestamp("2026-08-07", tz="UTC")


def test_walk_forward_refuses_an_entry_that_gaps_past_the_target():
    """REGRESSION: a gap above the target was scored a 'target hit' that
    settled BELOW the fill — recording winners as losses and producing a
    contradictory 140 target hits at an 11% win rate."""
    daily = pd.DataFrame({"open": [130.0], "high": [131.0], "low": [129.0],
                          "close": [130.0]})
    r = BT.walk_forward(daily, 0, stop=99.0, target=110.0)
    assert r["outcome"] == "gap_past_target"
    assert r["ret_pct"] is None


def test_walk_forward_refuses_an_entry_that_gaps_below_the_stop():
    daily = pd.DataFrame({"open": [95.0], "high": [96.0], "low": [94.0],
                          "close": [95.0]})
    r = BT.walk_forward(daily, 0, stop=99.0, target=110.0)
    assert r["outcome"] == "gap_below_stop"


def test_ambiguous_day_defaults_to_a_loss_without_intraday_bars():
    """Daily OHLC cannot say which level came first. Assuming the win would
    inflate every result, so the conservative default is a loss."""
    daily = pd.DataFrame({"open": [100.0], "high": [115.0], "low": [95.0],
                          "close": [105.0]})
    r = BT.walk_forward(daily, 0, stop=98.0, target=110.0)
    assert r["outcome"] == "stop"
    assert r["resolved"] == "assumed_loss"


def test_ambiguous_day_is_resolved_by_intraday_bars_when_available():
    daily = pd.DataFrame({"open": [100.0], "high": [115.0], "low": [95.0],
                          "close": [105.0]}, index=[pd.Timestamp("2026-08-03")])
    # target touched first
    intra = _bars([(100, 112, 111, 10), (96, 100, 97, 10)], start="2026-08-03 09:30")
    intra.index = intra.index.tz_localize(None)
    r = BT.walk_forward(daily, 0, stop=98.0, target=110.0, intraday=intra)
    assert r["outcome"] == "target" and r["resolved"] == "intraday"


def test_summarize_reports_expectancy_not_just_win_rate():
    """A high win rate with a bad payoff still loses — expectancy is the
    number that decides, and the backtest's whole conclusion rests on it."""
    trades = [{"ret_pct": 0.5, "outcome": "target", "days": 1}] * 7 + \
             [{"ret_pct": -2.0, "outcome": "stop", "days": 1}] * 3
    s = BT.summarize(trades, "x")
    assert s["win_rate_pct"] == 70.0
    assert s["expectancy_pct"] < 0            # 70% wins, still a loser


def test_summarize_handles_an_empty_cohort():
    assert BT.summarize([], "empty")["n"] == 0
