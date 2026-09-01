"""Signal Lab — the 1-minute BUY/SELL event engine.

The load-bearing test is prefix stability: a signal computed live at bar i
must be exactly the signal a full-frame recompute shows at bar i. That is
the difference between an indicator and a backfitted story — smc's own
full-frame lists fail this (they match bars against swings confirmed
later), which is why the engine runs its own walk.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from daytrading.signal_lab import (  # noqa: E402
    COMPOSITE_WITHIN, ORB_MINUTES, events_from_frame,
)


def _frame(closes, spread=0.05, start="2026-09-01 09:30",
           highs=None, lows=None):
    idx = pd.date_range(start, periods=len(closes), freq="1min", tz="America/New_York")
    c = np.asarray(closes, dtype=float)
    h = np.asarray(highs, dtype=float) if highs is not None else c + spread
    l = np.asarray(lows, dtype=float) if lows is not None else c - spread
    return pd.DataFrame({"open": c, "high": h, "low": l, "close": c,
                         "volume": 10_000}, index=idx)


def _flat(n, px=100.0):
    return [px + (0.01 if i % 2 else -0.01) for i in range(n)]


# ── the non-repaint contract ────────────────────────────────────────────────
def test_prefix_stability():
    # A jagged session with sweeps, breaks and an ORB: every prefix's events
    # must equal the full-frame events truncated to that prefix.
    rng = np.random.RandomState(7)
    closes = 100 + np.cumsum(rng.normal(0, 0.3, size=120))
    lows = closes - np.abs(rng.normal(0.15, 0.1, size=120))
    highs = closes + np.abs(rng.normal(0.15, 0.1, size=120))
    df = _frame(closes, highs=highs, lows=lows)
    full = events_from_frame(df)
    for k in (20, 40, 60, 90, 110):
        prefix = events_from_frame(df.iloc[:k])
        want = [e for e in full if e["i"] < k]
        assert prefix == want, f"prefix {k} diverged — the engine repaints"


# ── ORB events ──────────────────────────────────────────────────────────────
def test_orb_break_fires_once_and_only_after_the_range_is_complete():
    closes = _flat(ORB_MINUTES) + [100.5, 100.6, 100.7]
    df = _frame(closes)
    ups = [e for e in events_from_frame(df) if e["kind"] == "orb_up"]
    assert len(ups) == 1
    assert ups[0]["i"] == ORB_MINUTES          # the FIRST close beyond, once
    assert ups[0]["level"] > 100               # the range top, not the close


def test_no_orb_events_on_an_incomplete_range():
    df = _frame(_flat(8))                      # session died after 8 minutes
    assert [e for e in events_from_frame(df) if e["kind"].startswith("orb")] == []


def test_orb_down_break():
    closes = _flat(ORB_MINUTES) + [99.4, 99.3]
    evs = [e for e in events_from_frame(_frame(closes)) if e["kind"] == "orb_dn"]
    assert len(evs) == 1


# ── sweep + structure -> composite ─────────────────────────────────────────
def _sweep_then_break():
    """Rally, dip forming a swing low at ~99, sweep under it with a close
    back above, then break the prior swing high -> composite BUY."""
    closes = [100, 100.2, 100.4, 100.2, 100.0,       # swing high at i=2 (100.4)
              99.6, 99.2, 99.0, 99.2, 99.6,          # swing low  at i=7 (99.0)
              99.8, 99.9, 99.7, 99.8, 99.9,
              99.5,                                  # i=15: the sweep bar
              99.9, 100.1, 100.6, 100.8, 101.0]      # i=18 closes over 100.4+
    lows = [c - 0.05 for c in closes]
    lows[15] = 98.7                                  # wick THROUGH the 98.95 low
    highs = [c + 0.05 for c in closes]
    return _frame(closes, highs=highs, lows=lows)


def test_five_step_composite_buy():
    evs = events_from_frame(_sweep_then_break())
    sweeps = [e for e in evs if e["kind"] == "sweep" and e["side"] == "sell_side"]
    buys = [e for e in evs if e["kind"] == "buy"]
    assert sweeps, "the trap bar must register as a sweep"
    assert len(buys) == 1
    b = buys[0]
    assert b["stop"] == 98.7                   # the trap wick, not a percent
    assert b["target"] > b["price"] > b["stop"]
    # 2R geometry
    assert abs((b["target"] - b["price"]) - 2 * (b["price"] - b["stop"])) < 1e-6
    # structure bar comes AFTER the sweep bar
    assert b["i"] > sweeps[0]["i"]


def test_sweep_alone_is_not_a_buy():
    # Same trap but price never breaks structure afterwards.
    closes = [100, 100.2, 100.4, 100.2, 100.0,
              99.6, 99.2, 99.0, 99.2, 99.6,
              99.8, 99.9, 99.7, 99.8, 99.9,
              99.5, 99.6, 99.5, 99.6, 99.5, 99.6]
    lows = [c - 0.05 for c in closes]
    lows[15] = 98.7
    evs = events_from_frame(_frame(closes, lows=lows))
    assert [e for e in evs if e["kind"] == "buy"] == []


def test_stale_sweep_does_not_arm_a_late_break():
    # Structure break more than COMPOSITE_WITHIN bars after the sweep.
    base = _sweep_then_break()
    filler_close = [99.8, 99.7] * (COMPOSITE_WITHIN // 2 + 2)
    filler = _frame(filler_close, start="2026-09-01 09:50")
    # rebuild: sweep segment, long chop, then the breakout closes
    closes = list(base["close"].values[:16]) + filler_close + [100.6, 100.8, 101.0]
    lows = [c - 0.05 for c in closes]
    lows[15] = 98.7
    df = _frame(closes, lows=lows)
    buys = [e for e in events_from_frame(df) if e["kind"] == "buy"]
    assert buys == []


def test_one_trap_per_level_per_session():
    # The first live smoke printed ~100 sweeps in 2 hours — the same swing
    # low re-swept every bar. One level arms once.
    closes = [100, 100.2, 100.4, 100.2, 100.0,
              99.6, 99.2, 99.0, 99.2, 99.6, 99.8, 99.9,
              99.5, 99.6, 99.5, 99.6, 99.5, 99.6]
    lows = [c - 0.05 for c in closes]
    lows[12] = 98.7
    lows[14] = 98.6
    lows[16] = 98.5                              # three pierces of the same low
    evs = events_from_frame(_frame(closes, lows=lows))
    assert len([e for e in evs if e["kind"] == "sweep"]) == 1


def test_stale_swing_is_not_liquidity():
    # A swing far older than SWEEP_LOOKBACK must not fire a sweep.
    from daytrading.signal_lab import SWEEP_LOOKBACK
    closes = ([100, 100.3, 100.6, 100.3, 100.0, 99.6, 99.2, 99.0, 99.2, 99.6]
              + [99.8 + (0.01 if i % 2 else -0.01) for i in range(SWEEP_LOOKBACK + 10)]
              + [99.5])
    lows = [c - 0.05 for c in closes]
    lows[-1] = 98.7                              # pierces the ancient 98.95 low
    evs = events_from_frame(_frame(closes, lows=lows))
    sweep_bars = [e["i"] for e in evs if e["kind"] == "sweep"]
    assert len(closes) - 1 not in sweep_bars


def test_flat_tape_is_silent():
    evs = events_from_frame(_frame(_flat(60)))
    assert [e for e in evs if e["kind"] in ("buy", "sell")] == []


def test_empty_and_tiny_frames_refuse_quietly():
    assert events_from_frame(None) == []
    assert events_from_frame(_frame([100.0])) == []
