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


# ── the lookback knob (2026-08-19, Support Levels tab) ────────────────────────
def test_the_default_lookback_is_unchanged_and_still_gated_at_60_bars():
    """Every pre-existing caller passes no window. If this floor moves, the
    /zones page, orderflow.signals and both backtests change silently."""
    assert pz.LOOKBACK_BARS == 252
    assert pz.MIN_BARS == 60
    assert pz.compute(SAW.iloc[:59]) is None
    assert pz.compute(SAW.iloc[:60]) is not None


def test_a_short_window_is_reachable_only_when_it_is_ASKED_for():
    """21 bars cannot clear the 60-bar default gate — that is the point of the
    gate. Passing `lookback_bars` is the explicit request that relaxes it."""
    frame = SAW.iloc[:40]
    assert pz.compute(frame.iloc[:21]) is None                   # default floor
    out = pz.compute(SAW, lookback_bars=21, swing_window=2)      # asked for
    assert out is not None
    assert out["params"]["lookback"] == 21


def test_a_frame_below_the_absolute_floor_returns_None_at_any_window():
    assert pz.compute(SAW.iloc[:8], lookback_bars=21, swing_window=2) is None


def _vees(low, high, leg, cycles):
    """A V-repeating series whose local minima land at `low`. Unlike SAW this is
    built per-test so the exact bar count is known, which is what the floor
    tests need."""
    seq = []
    for _ in range(cycles):
        seq += list(np.linspace(high, low, leg, endpoint=False))
        seq += list(np.linspace(low, high, leg, endpoint=False))
    c = pd.Series(seq, dtype=float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c,
                         "volume": pd.Series(np.ones(len(c)) * 1_000_000)})


def test_the_floor_scales_with_the_swing_window():
    """`_local_extrema` scans range(w, n-w) and compares w bars either side, so
    a frame of 2w+2 has nowhere to put a swing at all. A fixed floor would let a
    wide swing window through to return an empty band list instead of None."""
    frame = _vees(100.0, 110.0, 4, 20)                 # a swing every 4 bars
    assert pz.compute(frame, lookback_bars=12, swing_window=5) is None   # 2*5+3=13
    assert pz.compute(frame, lookback_bars=13, swing_window=5) is not None


def test_the_window_actually_narrows_what_is_seen():
    """The whole feature: a short read must not report structure that only
    exists further back than it looked."""
    old = list(np.linspace(90.0, 80.0, 10)) + list(np.linspace(80.0, 90.0, 10))
    recent = ([100.0, 104.0] * 5) + list(np.linspace(104.0, 100.0, 5)) \
        + list(np.linspace(100.0, 106.0, 10))
    c = pd.Series(([95.0] * 40) + (old * 4) + recent, dtype=float)
    df = pd.DataFrame({"open": c, "high": c, "low": c, "close": c,
                       "volume": pd.Series(np.ones(len(c)) * 1_000_000)})

    wide = pz.compute(df, lookback_bars=252, swing_window=2)
    narrow = pz.compute(df, lookback_bars=21, swing_window=2)
    assert wide["params"]["lookback"] == 252
    assert narrow["params"]["lookback"] == 21

    # The 80 floor is 80+ bars back. The wide read must find it; the narrow one
    # must not be able to see it at all.
    assert any(z["mid"] < 85 for z in wide["demand_zones"]), wide["demand_zones"]
    assert not any(z["mid"] < 85 for z in narrow["demand_zones"]), \
        f"a 21-bar read reported a band from 80+ bars back: {narrow['demand_zones']}"


def test_the_lookback_is_a_per_call_argument_and_never_a_global_mutation():
    before = (pz.LOOKBACK_BARS, pz.SWING_WINDOW, pz.MIN_BARS, pz.MIN_BARS_ABS)
    pz.compute(SAW, lookback_bars=21, swing_window=2)
    assert (pz.LOOKBACK_BARS, pz.SWING_WINDOW, pz.MIN_BARS,
            pz.MIN_BARS_ABS) == before


def test_params_report_the_EFFECTIVE_window_not_the_module_default():
    """The payload is what the Support tab labels its chart with. Reporting 252
    while reading 63 would put the wrong zoom on screen."""
    for lb in (21, 63, 126, 252):
        out = pz.compute(SAW, lookback_bars=lb, swing_window=2)
        assert out["params"]["lookback"] == lb
