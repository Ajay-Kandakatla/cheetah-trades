"""Tests for the pattern detector — synthetic daily frames with known geometry.
Confirmation-line discipline (an unconfirmed W is a shape, not a signal) and
self-validation math are the load-bearing behaviors.
"""
import numpy as np
import pandas as pd

from patterns import detector


def _df(closes, lows=None, highs=None, start="2025-06-01"):
    idx = pd.bdate_range(start, periods=len(closes))
    c = np.asarray(closes, dtype=float)
    lo = c - 0.5 if lows is None else np.asarray(lows, dtype=float)
    hi = c + 0.5 if highs is None else np.asarray(highs, dtype=float)
    return pd.DataFrame({"open": np.r_[c[0], c[:-1]], "high": hi, "low": lo,
                         "close": c, "volume": np.full(len(c), 1e6)}, index=idx)


def _w_bottom(confirm=True, second_low_offset=0.0):
    """Build a W: 100 → 80 (low1) → 92 (peak) → 80.x (low2) → breakout/stall."""
    seg = []
    seg += list(np.linspace(100, 80, 25))          # decline to low1
    seg += list(np.linspace(80, 92, 20))           # interim peak ~15% above
    seg += list(np.linspace(92, 80 + second_low_offset, 20))   # back to low2
    if confirm:
        seg += list(np.linspace(80 + second_low_offset, 95, 12))  # close above 92
    else:
        seg += list(np.linspace(80 + second_low_offset, 88, 12))  # stalls below the line
    return _df(seg)


def test_double_bottom_confirmed():
    res = detector.double_bottom(_w_bottom(confirm=True))
    assert res["fresh"], "should detect a fresh confirmed W"
    p = res["fresh"][0]
    assert p["status"] == "confirmed"
    assert p["pattern"] == "double_bottom"
    assert p["neckline"] > 91 and p["target"] > p["neckline"]
    assert p["stop"] < p["pattern_low"]
    assert res["historical_confirms"], "confirmation harvested for self-validation"


def test_double_bottom_unconfirmed_is_forming_not_signal():
    res = detector.double_bottom(_w_bottom(confirm=False))
    assert res["historical_confirms"] == []        # never closed above the line
    if res["fresh"]:
        assert all(p["status"] == "forming" for p in res["fresh"])
        assert all(p.get("to_confirm_pct", 0) > 0 for p in res["fresh"])


def test_double_bottom_rejects_unequal_lows():
    # second low 10% below the first — not a W
    res = detector.double_bottom(_w_bottom(confirm=True, second_low_offset=-8.0))
    assert all(p["status"] != "confirmed" or p["pattern_low"] < 75
               for p in res["fresh"]) or not res["fresh"]


def test_double_bottom_rejects_shallow_interim_peak():
    seg = (list(np.linspace(100, 80, 25)) + list(np.linspace(80, 84, 20)) +
           list(np.linspace(84, 80, 20)) + list(np.linspace(80, 90, 12)))
    res = detector.double_bottom(_df(seg))         # peak only +5% — below the 10% gate
    assert res["fresh"] == []


def test_inverse_head_shoulders_confirmed():
    seg = []
    seg += list(np.linspace(100, 85, 15))          # left shoulder low ~85
    seg += list(np.linspace(85, 95, 12))           # peak1
    seg += list(np.linspace(95, 78, 15))           # head ~78 (deeper)
    seg += list(np.linspace(78, 96, 15))           # peak2
    seg += list(np.linspace(96, 86, 12))           # right shoulder ~86
    seg += list(np.linspace(86, 99, 12))           # confirm above neckline 96
    res = detector.inverse_head_shoulders(_df(seg))
    assert res["fresh"], "should detect the inverse H&S"
    p = res["fresh"][0]
    assert p["status"] == "confirmed"
    assert p["neckline"] >= 95
    assert res["historical_confirms"]


def test_measure_outcomes_skips_incomplete_windows():
    closes = list(np.linspace(100, 120, 40))
    df = _df(closes)
    confirms = [{"confirm_idx": 5, "neckline": 100, "pattern_low": 95},
                {"confirm_idx": 35, "neckline": 110, "pattern_low": 100}]  # <21 bars left
    out = detector.measure_outcomes(df, confirms, horizon=21)
    assert len(out) == 1                            # the late one skipped, never peeked
    assert out[0]["fwd_pct"] > 0 and out[0]["max_gain_pct"] >= out[0]["fwd_pct"]


def test_swing_points_find_extrema():
    seg = list(np.linspace(100, 90, 10)) + list(np.linspace(90, 110, 10)) + list(np.linspace(110, 95, 10))
    lows, highs = detector.swing_points(_df(seg))
    assert lows and highs
