"""Behavioral contract for breakout RECENCY (backend/sepa/volume.py).

`high_vol_breakout` is the SAME-DAY (last bar) volume-confirmed breakout the
strict is_buyable gate uses (book p.203). `days_since_breakout` additionally
reports how many bars ago the most recent such breakout fired within
BREAKOUT_RECENCY_LOOKBACK (0 = today, None = none in window) so the FE
'Breakout: ≤1wk / Any' toggle can admit a name that broke out earlier in the
week. A bar is a breakout when its volume > 1.5× the trailing 50-day average
AND its close exceeds the highest close of the prior 21 bars.

Pure pandas — no network, no Mongo.
"""
from __future__ import annotations

import pandas as pd

from sepa import volume


def _series(closes, vols):
    idx = pd.date_range("2025-01-01", periods=len(closes), freq="B")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": vols},
        index=idx,
    )


def test_breakout_today_is_zero_days():
    df = _series([100.0] * 67 + [110.0], [1000.0] * 67 + [2000.0])
    out = volume.analyze(df)
    assert out["high_vol_breakout"] is True
    assert out["days_since_breakout"] == 0          # today


def test_breakout_three_days_ago():
    # Breakout bar, then 3 quiet pullback bars below the pivot high.
    closes = [100.0] * 64 + [110.0, 108.0, 108.0, 108.0]
    vols = [1000.0] * 64 + [2000.0, 1000.0, 1000.0, 1000.0]
    out = volume.analyze(_series(closes, vols))
    assert out["high_vol_breakout"] is False        # last bar is NOT a breakout
    assert out["days_since_breakout"] == 3          # ...but one fired 3 bars ago


def test_old_breakout_outside_window_is_none():
    # Breakout ~20 bars back — beyond BREAKOUT_RECENCY_LOOKBACK (15).
    closes = [100.0] * 47 + [110.0] + [108.0] * 20
    vols = [1000.0] * 47 + [2000.0] + [1000.0] * 20
    out = volume.analyze(_series(closes, vols))
    assert out["high_vol_breakout"] is False
    assert out["days_since_breakout"] is None


def test_never_broke_out_is_none():
    closes = [100.0 + (i % 3) * 0.1 for i in range(68)]
    out = volume.analyze(_series(closes, [1000.0] * 68))
    assert out["days_since_breakout"] is None


def test_lookback_constant_locked():
    # FE '≤1wk' threshold (<=5) must stay inside the computed window.
    assert volume.BREAKOUT_RECENCY_LOOKBACK >= 5
