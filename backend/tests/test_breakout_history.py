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
