"""Tests for the scalping backtest/paper logic — sim entries, outcome
simulation, and net-of-cost aggregation. Synthetic frames, no network.
"""
import numpy as np
import pandas as pd

from scalping import sim, backtest


def _frame(closes, start="2026-06-09 13:30", highs=None, lows=None):
    """Single-day RTH 1-min frame, UTC tz-naive index."""
    idx = pd.date_range(start, periods=len(closes), freq="1min")
    c = np.asarray(closes, dtype=float)
    h = c + 0.05 if highs is None else np.asarray(highs, float)
    lo = c - 0.05 if lows is None else np.asarray(lows, float)
    return pd.DataFrame({"open": np.r_[c[0], c[:-1]], "high": h, "low": lo,
                         "close": c, "volume": np.full(len(c), 5e4), "session": "rth"}, index=idx)


# ── ORB entries ──────────────────────────────────────────────────────────────
def test_orb_entries_long_on_open_drive_breakout():
    rng = np.random.RandomState(0)
    closes = np.r_[np.linspace(100.0, 100.6, 5), 100.7 + np.cumsum(rng.normal(0.02, 0.03, 40))]
    e = sim.orb_entries(_frame(closes), rel_vol=2.0, atr14=1.0)
    assert len(e) == 1
    assert e[0]["side"] == "long" and e[0]["strategy"] == "stocks_in_play_orb"
    assert "entry_ts" in e[0] and e[0]["stop"] < e[0]["entry_price"]


def test_orb_entries_empty_when_relvol_low():
    closes = np.r_[np.linspace(100.0, 100.6, 5), np.full(40, 101.0)]
    assert sim.orb_entries(_frame(closes), rel_vol=0.4, atr14=1.0) == []


# ── shock-fade entries ───────────────────────────────────────────────────────
def test_shock_fade_entries_on_sharp_drop():
    rng = np.random.RandomState(2)
    base = 100.0 + rng.normal(0, 0.03, 40)
    drop = np.linspace(100.0, 94.0, 22)               # ~6% drop in the window
    e = sim.shock_fade_entries(_frame(np.r_[base, drop], start="2026-06-09 14:01"), atr14=1.5)
    assert len(e) >= 1
    assert e[0]["side"] == "long" and e[0]["time_stop_min"] == sim.D.SHOCK_TIME_STOP_MIN


# ── outcome simulation ───────────────────────────────────────────────────────
def test_simulate_outcome_target_then_stop_then_eod():
    # long entry at bar 0 (100), stop 99, target 101
    sig = {"side": "long", "entry_ts": "2026-06-09 13:30:00", "entry_price": 100.0,
           "stop": 99.0, "target": 101.0}
    # path rises to 101.2 → target
    f = _frame([100.0, 100.5, 101.2, 101.0], highs=[100.1, 100.6, 101.3, 101.1])
    out = sim.simulate_outcome(f, sig)
    assert out["outcome"] == "target" and out["r_multiple"] > 0

    # path drops to 98.5 → stop
    f2 = _frame([100.0, 99.5, 98.5, 99.0], lows=[99.9, 99.0, 98.4, 98.9])
    out2 = sim.simulate_outcome(f2, sig)
    assert out2["outcome"] == "stop" and out2["r_multiple"] == -1.0


def test_simulate_outcome_time_stop():
    sig = {"side": "long", "entry_ts": "2026-06-09 13:30:00", "entry_price": 100.0,
           "stop": 95.0, "target": 110.0, "time_stop_min": 3}
    # never hits stop/target; time-stop closes at the 3-min bar
    f = _frame([100.0, 100.1, 100.2, 100.3, 100.4], highs=[100.2]*5, lows=[99.9]*5)
    out = sim.simulate_outcome(f, sig)
    assert out["outcome"] == "time_stop"


# ── net-of-cost aggregation ──────────────────────────────────────────────────
def test_net_applies_cost_to_gross():
    trade = {"entry_price": 100.0, "side": "long", "pnl_pct": 1.0, "risk": 1.0}
    n = backtest._net(trade, assumed_spread_pct=0.05)
    assert n["cost_pct"] > 0.05                        # spread + slippage + commission
    assert n["net_pnl_pct"] < 1.0                      # net < gross


def test_agg_reports_gross_and_net_separately():
    trades = [
        {"strategy": "x", "side": "long", "pnl_pct": 1.0, "r_multiple": 1.0, "net_pnl_pct": 0.8, "net_r_multiple": 0.8, "outcome": "target"},
        {"strategy": "x", "side": "long", "pnl_pct": -1.0, "r_multiple": -1.0, "net_pnl_pct": -1.2, "net_r_multiple": -1.2, "outcome": "stop"},
        {"strategy": "x", "side": "short", "pnl_pct": 0.5, "r_multiple": 0.5, "net_pnl_pct": 0.3, "net_r_multiple": 0.3, "outcome": "eod_flat"},
    ]
    a = backtest._agg(trades)
    assert a["n_trades"] == 3
    assert a["gross_win_rate_pct"] == round(2 / 3 * 100, 1)
    assert a["net_expectancy_r"] is not None
    assert "by_side" in a and "verdict" in a
