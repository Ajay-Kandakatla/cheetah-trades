"""Breakout history — the markers behind the BreakoutHistoryModal chart.

Ajay 2026-06-15: "add a modal of the breakouts ... to see where the breakout
occurred." These lock:
  - breakout_points returns the rising-edge breakout bars (date/close/volume),
  - and CANNOT drift from analyze()'s breakout_count (same bo_series),
  - history_for_symbol assembles series + markers, soft-fails on no data.

Run in the backend venv (needs pandas):
  cd backend && .venv/bin/python -m pytest tests/test_breakout_history.py -q
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import breakout, volume


def _make_df(breakout_idxs, n=130):
    """Flat 100/1M baseline with clean volume-confirmed breakouts injected at
    the given indices (each close steps above the prior 21-day high on 3× vol)."""
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    close = np.full(n, 100.0)
    vol = np.full(n, 1_000_000.0)
    hi = 100.0
    for j in breakout_idxs:
        hi += 5.0
        close[j] = hi
        vol[j] = 3_000_000.0
    return pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close, "volume": vol},
        index=idx,
    )


def test_breakout_points_finds_each_injected_breakout():
    df = _make_df([70, 95, 120])
    pts = volume.breakout_points(df)
    assert len(pts) == 3
    # Dates line up with the injected bars; price + ratio are real.
    assert pts[0]["date"] == df.index[70].strftime("%Y-%m-%d")
    assert pts[0]["close"] == 105.0
    assert pts[-1]["close"] == 115.0
    assert pts[0]["vol_ratio"] and pts[0]["vol_ratio"] >= 2.5


def test_markers_cannot_drift_from_count():
    """The chart markers and the chip number come from the SAME bo_series."""
    for idxs in ([70, 95, 120], [65], [80, 110]):
        df = _make_df(idxs)
        assert len(volume.breakout_points(df)) == volume.analyze(df)["breakout_count"]


def test_breakout_points_empty_on_short_history():
    df = _make_df([], n=40)            # < 60 bars
    assert volume.breakout_points(df) == []


def test_history_for_symbol_shape(monkeypatch):
    df = _make_df([70, 95, 120])
    monkeypatch.setattr("sepa.prices.load_prices", lambda s: df)
    out = breakout.history_for_symbol("TEST")
    assert out["ok"] is True
    assert out["symbol"] == "TEST"
    assert len(out["series"]) == 130
    assert {"date", "close", "volume"} <= set(out["series"][0].keys())
    assert len(out["breakouts"]) == 3
    assert out["breakout_count"] == 3          # marker count == chip count


def test_history_for_symbol_soft_fails_without_prices(monkeypatch):
    monkeypatch.setattr("sepa.prices.load_prices", lambda s: None)
    out = breakout.history_for_symbol("NODATA")
    assert out["ok"] is False
    assert out["symbol"] == "NODATA"
    assert "series" not in out                 # nothing fabricated


# ── "Whose hands fired the breakout?" footprint (TTLAC p.186) ─────────────────
# Real OHLCV (the flat _make_df has no intrabar range, so close-location can't
# be read). We build a 6-day up run-up into a volume-confirmed breakout and vary
# only the close LOCATION in the breakout bar — institutional (close near high)
# vs suspect churn (close near low on heavy volume, p.188).

def _df_from(close, high, low, vol):
    n = len(close)
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"open": np.asarray(close, float), "high": np.asarray(high, float),
         "low": np.asarray(low, float), "close": np.asarray(close, float),
         "volume": np.asarray(vol, float)}, index=idx)


def _breakout_df(close_loc="high", n=130, bo=120):
    close = np.full(n, 100.0); high = np.full(n, 100.5)
    low = np.full(n, 99.5); vol = np.full(n, 1_000_000.0)
    for k, p in enumerate(range(bo - 6, bo)):          # 6 up days into the break
        close[p] = 100.0 + (k + 1) * 0.4
        high[p] = close[p] + 0.3; low[p] = close[p] - 0.3
        vol[p] = 1_300_000.0
    close[bo] = 112.0; vol[bo] = 3_000_000.0           # clears prior high on 3× vol
    if close_loc == "high":
        high[bo] = 112.5; low[bo] = 105.0              # close pinned near the high
    else:
        high[bo] = 118.0; low[bo] = 111.5              # close near the low (churn)
    return _df_from(close, high, low, vol)


def test_marker_carries_footprint_with_expected_keys():
    pts = volume.breakout_points(_breakout_df("high"))
    assert pts and pts[-1]["footprint"] is not None
    fp = pts[-1]["footprint"]
    assert {"close_location", "vol_ratio", "up_days", "down_days",
            "up_down_vol_ratio", "big_block", "strength", "hands"} <= set(fp)


def test_footprint_reads_institutional_on_strong_close_heavy_volume():
    fp = volume.breakout_points(_breakout_df("high"))[-1]["footprint"]
    assert fp["hands"] in ("institutional", "heavy_institutional")
    assert fp["close_location"] > 0.5          # close held near the high
    assert fp["strength"] >= volume.BREAKOUT_INST_STRENGTH
    assert fp["up_days"] >= 5                   # the accumulation run-up


def test_churned_weak_close_is_no_longer_a_breakout_point():
    """CONTRACT FLIP (2026-08-03, GSAT regression — Ajay: "heavy sell off is
    being tracked as breakout"): heavy volume with the close given back into
    the LOWER half of the range is churn (p.188) and now produces NO breakout
    point at all — previously it was boarded with a 'suspect' footprint,
    which still read as a breakout on the page. Exclusion is the fix; the
    suspect-hands footprint read remains for upper-half closes."""
    assert volume.breakout_points(_breakout_df("low")) == []


def test_footprint_none_on_out_of_range_position():
    df = _breakout_df("high")
    assert volume.breakout_footprint(df, 0) is None       # no prior bar
    assert volume.breakout_footprint(df, len(df)) is None  # past the end


# ── Emerging breakout — the forward "setting up + whose hands" read ───────────

def _coil_df(last_close, near_low=False, n=130, pivot=105.0, pivot_pos=109):
    close = np.full(n, 100.0); high = np.full(n, 100.5)
    low = np.full(n, 99.5); vol = np.full(n, 1_000_000.0)
    close[pivot_pos] = pivot; high[pivot_pos] = pivot + 0.5
    low[pivot_pos] = pivot - 0.5; vol[pivot_pos] = 1_500_000.0
    for p in range(n - 20, n):                 # coil the last 20 bars
        close[p] = last_close
        if near_low:                            # close near the low → CMF < 0
            high[p] = last_close + 0.8; low[p] = last_close - 0.2
        else:                                   # close near the high → CMF > 0
            high[p] = last_close + 0.2; low[p] = last_close - 0.8
        vol[p] = 1_400_000.0
    return _df_from(close, high, low, vol)


def test_emerging_true_when_coiling_under_high_with_accumulation():
    em = volume.emerging_breakout(_coil_df(103.5))         # 1.4% under the 105 pivot
    assert em["emerging"] is True
    assert em["distance_to_high_pct"] <= volume.EMERGING_NEAR_HIGH_PCT
    assert em["pivot_price"] == 105.0
    assert em["hands"] in ("institutional", "light")
    assert em["cmf"] is not None and em["cmf"] > 0


def test_emerging_false_when_already_extended_above_high():
    assert volume.emerging_breakout(_coil_df(106.0))["emerging"] is False


def test_emerging_false_when_far_below_the_pivot():
    assert volume.emerging_breakout(_coil_df(100.0))["emerging"] is False   # ~4.8% under


def test_emerging_false_without_accumulation():
    """Near the pivot but closing weak (no buying pressure) → not setting up."""
    assert volume.emerging_breakout(_coil_df(103.5, near_low=True))["emerging"] is False


def test_emerging_false_on_short_history():
    n = 40                                      # < 60 bars → no read, never a crash
    df = _df_from(np.full(n, 100.0), np.full(n, 100.5),
                  np.full(n, 99.5), np.full(n, 1_000_000.0))
    assert volume.emerging_breakout(df)["emerging"] is False


def test_history_for_symbol_includes_emerging(monkeypatch):
    monkeypatch.setattr("sepa.prices.load_prices", lambda s: _coil_df(103.5))
    out = breakout.history_for_symbol("COIL")
    assert out["ok"] is True
    assert out["emerging"]["emerging"] is True
