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
    """Build a W: 100 → 80 (low1) → 92 (peak) → 80.x (low2) → breakout/stall.
    Bottom separation ~26 bars — inside the cited 23–35 band (LMW >22 days;
    Bulkowski 2–7 weeks)."""
    seg = []
    seg += list(np.linspace(100, 80, 25))          # decline to low1
    seg += list(np.linspace(80, 92, 13))           # interim peak ~15% above
    seg += list(np.linspace(92, 80 + second_low_offset, 13))   # back to low2
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
    seg = (list(np.linspace(100, 80, 25)) + list(np.linspace(80, 84, 13)) +
           list(np.linspace(84, 80, 13)) + list(np.linspace(80, 90, 12)))
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


# ── Triple bottom (Bulkowski tb.html, verified verbatim 2026-06-09) ──────────

def _triple(confirm=True, third_low_offset=0.0):
    """Three ~equal valleys at 80 with ~91 peaks between, then breakout/stall.
    Adjacent valleys ~16 bars apart (≥ TB_MIN_ADJ_SEP), span ~32 (≤ TB_MAX_SPAN)."""
    seg = list(np.linspace(100, 80, 25))           # decline to valley 1
    seg += list(np.linspace(80, 90, 8))
    seg += list(np.linspace(90, 80, 8))            # valley 2
    seg += list(np.linspace(80, 91, 8))
    seg += list(np.linspace(91, 80 + third_low_offset, 8))   # valley 3
    if confirm:
        seg += list(np.linspace(80 + third_low_offset, 97, 10))  # close above 91
    else:
        seg += list(np.linspace(80 + third_low_offset, 88, 10))  # stalls below the line
    return _df(seg)


def test_triple_bottom_confirmed():
    res = detector.triple_bottom(_triple(confirm=True))
    assert res["fresh"], "should detect a fresh confirmed triple bottom"
    p = res["fresh"][0]
    assert p["status"] == "confirmed"
    assert p["pattern"] == "triple_bottom"
    assert len(p["lows"]) == 3
    assert p["neckline"] > 90                      # the HIGHEST peak between valleys
    # Bulkowski's measure rule on the page: height × 74% added to the breakout.
    expect = p["neckline"] + detector.TB_TARGET_FACTOR * (p["neckline"] - p["pattern_low"])
    assert abs(p["target"] - round(expect, 2)) < 0.02
    assert res["historical_confirms"]


def test_triple_bottom_unconfirmed_is_not_a_signal():
    res = detector.triple_bottom(_triple(confirm=False))
    assert res["historical_confirms"] == []
    assert all(p["status"] == "forming" for p in res["fresh"])


def test_triple_bottom_rejects_unequal_valleys():
    res = detector.triple_bottom(_triple(confirm=True, third_low_offset=-8.0))
    assert not any(p["status"] == "confirmed" and p["pattern_low"] > 75
                   for p in res["fresh"])


# ── Cup with handle (Bulkowski cup.html, verified verbatim 2026-06-09) ───────

def _cup(confirm=True, handle_break_pct=0.0, v_shaped=False):
    """Left rim ~100 → U cup to ~70 → right rim ~99 → 7-bar handle to ~92 →
    breakout (or stall). Cup span ≥ CUP_MIN_BARS, handle in the upper half."""
    seg = list(np.linspace(90, 100, 10))           # rise into the left rim
    if v_shaped:
        seg += list(np.linspace(100, 95, 22))      # drift
        seg += list(np.linspace(95, 70, 3))        # plunge — one-bar V bottom
        seg += list(np.linspace(70, 95, 3))
        seg += list(np.linspace(95, 99, 26))       # right side back to the rim
    else:
        seg += list(np.linspace(100, 70, 25))      # rounded left side
        seg += [70.2, 70.0, 69.9, 70.0, 70.1, 70.3]  # time spent AT the low (the U)
        seg += list(np.linspace(70.5, 99, 23))     # rounded right side
    handle_low = 92 - handle_break_pct
    seg += list(np.linspace(99, handle_low, 7))    # the handle (≥ 1 week, upper half)
    if confirm:
        seg += list(np.linspace(handle_low, 104, 8))   # close above the right rim
    else:
        seg += list(np.linspace(handle_low, 96, 8))    # never takes out the rim
    return _df(seg)


def test_cup_with_handle_confirmed():
    res = detector.cup_with_handle(_cup(confirm=True))
    assert res["fresh"], "should detect a fresh confirmed cup with handle"
    p = res["fresh"][0]
    assert p["status"] == "confirmed"
    assert p["pattern"] == "cup_with_handle"
    assert p["neckline"] > 95                      # the right cup lip
    # Bulkowski's measure rule on the page: height × 61% added to the breakout.
    expect = p["neckline"] + detector.CWH_TARGET_FACTOR * (p["neckline"] - p["pattern_low"])
    assert abs(p["target"] - round(expect, 2)) < 0.02
    assert p["stop"] > p["pattern_low"]            # stop under the HANDLE low, not the cup low
    assert res["historical_confirms"]


def test_cup_rejects_v_shaped_bottom():
    res = detector.cup_with_handle(_cup(confirm=True, v_shaped=True))
    assert res["fresh"] == [] and res["historical_confirms"] == []


def test_cup_rejects_handle_below_upper_half():
    # Handle crashing to ~78 violates "forming in the upper half of the cup".
    res = detector.cup_with_handle(_cup(confirm=True, handle_break_pct=14.0))
    assert res["fresh"] == [] and res["historical_confirms"] == []


def test_cited_constants_locked():
    """Source-guard: page-cited values must not drift without a doc update."""
    assert detector.MIN_SEPARATION == 23           # LMW ">22 trading days"
    assert detector.MIN_INTERIM_RISE_PCT == 10.0   # Bulkowski ≥10% interim rise
    assert detector.TB_TARGET_FACTOR == 0.74       # tb.html measure rule
    assert detector.CWH_TARGET_FACTOR == 0.61      # cup.html measure rule
    assert detector.CUP_MIN_BARS == 35             # "7 to 65 weeks"
    assert detector.CUP_MAX_BARS == 325
    assert detector.HANDLE_MIN_BARS == 5           # handle "1 week minimum"
    assert set(detector.DETECTORS) == {"double_bottom", "inverse_head_shoulders",
                                       "triple_bottom", "cup_with_handle"}
