"""Tests for the daily candle-read layer (patterns/candles_daily) — formation
definitions are structural conventions; these pin the definitions, the trend
gate (a reversal needs a trend to reverse), and the honest framing fields.
"""
import numpy as np
import pandas as pd

from patterns import candles_daily as cd


def _frame(bars):
    """bars: list of (o, h, l, c). Volume constant."""
    idx = pd.bdate_range("2025-06-01", periods=len(bars))
    o, h, l, c = zip(*bars)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c,
                         "volume": np.full(len(bars), 1e6)}, index=idx)


def _downtrend(n=12, start=100.0, step=1.0):
    """Plain red bars drifting down — no wicks worth naming."""
    bars = []
    px = start
    for _ in range(n):
        o = px
        cl = px - step
        bars.append((o, o + 0.05, cl - 0.05, cl))
        px = cl
    return bars


def _uptrend(n=12, start=100.0, step=1.0):
    bars = []
    px = start
    for _ in range(n):
        o = px
        cl = px + step
        bars.append((o, o + 0.05 + step, o - 0.05, cl))
        px = cl
    return bars


def test_hammer_after_decline():
    bars = _downtrend(15)
    last = bars[-1][3]
    # long lower shadow (≥2× body), little upper shadow, body up top
    bars.append((last, last + 0.1, last - 3.0, last + 0.6))
    res = cd.read_daily(_frame(bars))
    names = [f["name"] for f in res["formations"]]
    assert "hammer" in names
    h = next(f for f in res["formations"] if f["name"] == "hammer")
    assert h["read"] == "bullish_reversal_setup"
    assert "60%" in h["stat"]                      # verified Bulkowski frequency
    assert "no standalone" in h["caveat"].lower() or "NO standalone" in h["caveat"]


def test_hammer_shape_without_downtrend_is_silent():
    bars = _uptrend(15)
    last = bars[-1][3]
    bars.append((last, last + 0.1, last - 3.0, last + 0.6))
    res = cd.read_daily(_frame(bars))
    assert "hammer" not in [f["name"] for f in res["formations"]]


def test_bullish_engulfing_after_decline():
    bars = _downtrend(15)
    o_prev, c_prev = bars[-1][0], bars[-1][3]      # last red body
    # white body strictly engulfing it: opens below prior close, closes above prior open
    bars.append((c_prev - 0.4, o_prev + 0.6, c_prev - 0.5, o_prev + 0.5))
    res = cd.read_daily(_frame(bars))
    names = [f["name"] for f in res["formations"]]
    assert "bullish_engulfing" in names
    f = next(x for x in res["formations"] if x["name"] == "bullish_engulfing")
    assert "63%" in f["stat"] and "dreadful" in f["stat"]   # his own deflating verdict travels with it


def test_doji_is_indecision_not_reversal():
    bars = _downtrend(15)
    last = bars[-1][3]
    bars.append((last, last + 1.0, last - 1.0, last + 0.01))   # open ≈ close
    res = cd.read_daily(_frame(bars))
    d = next(f for f in res["formations"] if f["name"] == "doji")
    assert d["read"] == "indecision"
    assert "52%" in d["stat"]                      # coin flip, said out loud


def test_morning_star_three_bars():
    bars = _downtrend(12, step=1.5)
    o1, c1 = bars[-1][0], bars[-1][3]              # tall red bar (body 1.5 of ~1.6 range)
    star_hi = c1 - 0.5                             # star body gaps BELOW the red body
    bars.append((star_hi, star_hi + 0.3, star_hi - 0.8, star_hi - 0.2))
    o3 = star_hi + 0.4                             # white bar gaps above the star body...
    c3 = (o1 + c1) / 2 + 0.8                       # ...and closes well into the red body
    bars.append((o3, c3 + 0.1, o3 - 0.1, c3))
    res = cd.read_daily(_frame(bars))
    names = [f["name"] for f in res["formations"]]
    assert "morning_star" in names


def test_no_formations_on_plain_trend():
    res = cd.read_daily(_frame(_uptrend(15)))
    assert res["formations"] == []
    assert res["last_bar"] is not None
    assert "controlled the last bar" in res["last_bar"]["read"]
    assert res["trend"] == "up"


def test_stats_only_from_verified_set():
    """Source-guard: every named formation carries a verified Bulkowski framing,
    and no formation exists without one (no folklore additions)."""
    for name in ("hammer", "shooting_star", "doji", "bullish_engulfing",
                 "bearish_engulfing", "morning_star"):
        assert name in cd.BULKOWSKI_CANDLE
        assert "%" in cd.BULKOWSKI_CANDLE[name]
    assert "near random" in cd.BULKOWSKI_CANDLE["shooting_star"]
    assert "lasting reversal" in cd.BULKOWSKI_CANDLE["bearish_engulfing"]
