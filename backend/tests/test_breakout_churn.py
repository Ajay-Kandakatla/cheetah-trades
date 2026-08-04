"""Churned spike-and-dump days must NOT count as breakouts (2026-08-03).

Regression: GSAT 2026-03-25 (+10.3% close but 7 points off the high, 4x
volume — an institution selling into the spike) and 2026-04-01 (closed in
the bottom fifth on 2.2x) were counted/boarded as breakouts. TTLAC p.188:
heavy volume without the close holding = churn. breakout_series now requires
the close to HOLD the upper half of the day's range (close_loc >=
BREAKOUT_CHURN_LOC on the -1..+1 scale); counting, recency, and the chart
markers all share the one series so they can never disagree.

Pure pandas — no network, no Mongo.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import volume


def _frame(rows):
    idx = pd.date_range("2025-01-01", periods=len(rows), freq="B")
    return pd.DataFrame(rows, index=idx)


def _flat(n, close=100.0, vol=1000.0):
    return [{"open": close, "high": close, "low": close,
             "close": close, "volume": vol} for _ in range(n)]


def test_spike_and_dump_is_not_a_breakout():
    """Close above the prior 21-bar high on 4x volume BUT dumped to the
    bottom of the range -> churn, not a breakout (the GSAT case)."""
    rows = _flat(67) + [{"open": 100.0, "high": 115.0, "low": 99.0,
                         "close": 101.0, "volume": 4000.0}]
    out = volume.analyze(_frame(rows))
    assert out["days_since_breakout"] is None
    assert out["breakout_count"] == 0
    assert volume.breakout_points(_frame(rows)) == []


def test_strong_close_breakout_still_counts():
    rows = _flat(67) + [{"open": 100.0, "high": 115.0, "low": 99.0,
                         "close": 114.0, "volume": 4000.0}]
    out = volume.analyze(_frame(rows))
    assert out["days_since_breakout"] == 0
    assert out["breakout_count"] == 1
    pts = volume.breakout_points(_frame(rows))
    assert len(pts) == 1 and pts[0]["close"] == 114.0


def test_exact_midpoint_close_counts_as_held():
    """close_loc == BREAKOUT_CHURN_LOC (0.0, dead middle) is NOT below the
    lower-half threshold -> still a breakout (boundary pinned)."""
    rows = _flat(67) + [{"open": 100.0, "high": 118.0, "low": 100.0,
                         "close": 109.0, "volume": 4000.0}]
    out = volume.analyze(_frame(rows))
    assert out["breakout_count"] == 1


def test_flat_bar_breakout_still_counts():
    """high == low (no range) reads as held — keeps the long-standing
    synthetic-frame behavior and never divides by zero."""
    rows = _flat(67) + [{"open": 110.0, "high": 110.0, "low": 110.0,
                         "close": 110.0, "volume": 4000.0}]
    out = volume.analyze(_frame(rows))
    assert out["high_vol_breakout"] is True
    assert out["breakout_count"] == 1


def test_count_and_points_share_one_series():
    """A mixed year: one clean breakout, one churned spike -> count 1 and
    exactly one chart marker, always in agreement."""
    rows = (_flat(67)
            + [{"open": 100.0, "high": 112.0, "low": 100.0,
                "close": 111.0, "volume": 4000.0}]           # clean
            + _flat(30, close=111.0, vol=1000.0)
            + [{"open": 111.0, "high": 130.0, "low": 110.0,
                "close": 112.0, "volume": 5000.0}])          # churned dump
    df = _frame(rows)
    out = volume.analyze(df)
    assert out["breakout_count"] == 1
    assert len(volume.breakout_points(df)) == 1


def test_gate_view_still_sees_churned_candidates():
    """The scanner's distribution gate calls breakout_points with
    include_churned=True — the churned bar must stay VISIBLE there so its
    suspect footprint can veto the buy tier (hiding it would let a churn
    breakout sail through is_buyable)."""
    rows = _flat(67) + [{"open": 100.0, "high": 115.0, "low": 99.0,
                         "close": 101.0, "volume": 4000.0}]
    df = _frame(rows)
    assert volume.breakout_points(df) == []
    gate_view = volume.breakout_points(df, include_churned=True)
    assert len(gate_view) == 1 and gate_view[0]["close"] == 101.0
