"""Behavioral tests for the on-demand price-structure zones (price_zones.py).

Configured price-structure method (NOT a book method) — these lock the geometry
+ the entry-read decision logic on a deterministic synthetic series. A clean
sawtooth between a support level (~100) and a resistance level (~120) gives a
known demand band ~100 and supply band ~120; we then probe the verdict at several
price positions via the `last_price` override.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from supply_demand import price_zones as pz


def _sawtooth(low=100.0, high=120.0, leg=12, cycles=7):
    """Repeating low→high→low ramp so swing highs cluster at `high`, lows at `low`."""
    seq = []
    for _ in range(cycles):
        seq += list(np.linspace(low, high, leg, endpoint=False))
        seq += list(np.linspace(high, low, leg, endpoint=False))
    c = pd.Series(seq, dtype=float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c,
                         "volume": pd.Series(np.ones(len(c)) * 1_000_000)})


SAW = _sawtooth()


def test_zones_are_found_at_the_swing_levels():
    out = pz.compute(SAW, last_price=110.0)
    assert out is not None
    # A supply band near 120 and a demand band near 100 must exist.
    assert any(abs(z["mid"] - 120) <= 2 for z in out["supply_zones"]), out["supply_zones"]
    assert any(abs(z["mid"] - 100) <= 2 for z in out["demand_zones"]), out["demand_zones"]


def test_into_supply_when_resistance_just_above():
    out = pz.compute(SAW, last_price=118.0)          # ~1.7% below the 120 band
    assert out["verdict"]["state"] == "INTO_SUPPLY"
    assert out["verdict"]["entry_read"] == "caution"


def test_clear_runway_with_support_below():
    out = pz.compute(SAW, last_price=101.0)          # just above the 100 support, runway up
    assert out["verdict"]["state"] in ("CLEAR_RUNWAY", "AT_DEMAND")
    assert out["verdict"]["entry_read"] == "favorable"


def test_mid_range_between_bands():
    out = pz.compute(SAW, last_price=110.0)          # dead center, ~9% from each band
    assert out["verdict"]["state"] == "MID_RANGE"
    assert out["verdict"]["entry_read"] == "neutral"


def test_extended_no_support_above_all_bands():
    # Price well above every band → no overhead, no nearby support → extended.
    out = pz.compute(SAW, last_price=140.0)
    assert out["verdict"]["state"] == "EXTENDED_NO_SUPPORT"
    assert out["verdict"]["entry_read"] == "caution"
    assert out["nearest_resistance"] is None


def test_disclaimer_and_params_present():
    out = pz.compute(SAW, last_price=110.0)
    assert "not advice" in out["disclaimer"].lower()
    assert out["params"]["near_pct"] == pz.NEAR_PCT


def test_too_little_history_returns_none():
    short = _sawtooth(cycles=1).iloc[:30]
    assert pz.compute(short) is None


def test_resolution_is_reported_so_two_surfaces_cannot_look_contradictory():
    """Ajay 2026-08-14 spotted DTE showing different demand bands on the Tape
    tab (fine geometry) and Back in Demand (coarse). They are the same
    structure at two zoom levels, but nothing on screen said so."""
    import pandas as pd
    n = 260
    base = [100 + (i % 7) for i in range(n)]
    df = pd.DataFrame({
        "open": base, "close": base,
        "high": [b + 1.5 for b in base], "low": [b - 1.5 for b in base],
        "volume": [10_000] * n,
    })
    fine = pz.compute(df)
    coarse = pz.compute(df, merge_pct=4.0, half_width_pct=1.75, swing_window=5)
    assert fine["resolution"] == "fine"
    assert coarse["resolution"] == "swing"
    assert fine["params"]["merge_pct"] < coarse["params"]["merge_pct"]
