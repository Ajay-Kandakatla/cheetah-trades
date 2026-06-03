"""Ravi volume-rank — locks the ThinkScript formula (user-provided 2026-06-02).

rawScore = volZ*30 + volRatio*10 ; rank = clamp(rawScore, 0, 100).
volZ = (volume-avgVol)/stdVol ; volRatio = volume/avgVol ; avgVol = SMA(volume,20)
; stdVol = sqrt(SMA((volume-avgVol)^2, 20)).
"""
import pandas as pd

from sepa.ravi import volume_rank


def _df(volumes, closes=None, opens=None):
    n = len(volumes)
    closes = closes or [50.0] * n
    opens = opens or [50.0] * n
    return pd.DataFrame({
        "open": opens, "high": [c + 1 for c in closes], "low": [c - 1 for c in closes],
        "close": closes, "volume": volumes,
    })


def test_constant_volume_scores_ten():
    # No surge: stdVol=0 -> volZ=0 ; volume==avgVol -> volRatio=1 -> rawScore=10.
    r = volume_rank(_df([100.0] * 41))
    assert r["vol_z"] == 0.0
    assert r["vol_ratio"] == 1.0
    assert r["rank"] == 10.0


def test_volume_spike_components_and_clamp():
    # Last bar doubles vs a flat 100-history: avgVol=105, stdVol≈21.24,
    # volZ≈4.47, volRatio≈1.90, rawScore≈153 -> clamps to 100.
    vols = [100.0] * 40 + [200.0]
    closes = [50.0] * 40 + [51.0]            # bullish last bar
    r = volume_rank(_df(vols, closes=closes, opens=[50.0] * 41))
    assert abs(r["vol_z"] - 4.47) < 0.05
    assert abs(r["vol_ratio"] - 1.90) < 0.02
    assert r["rank"] == 100.0                # rawScore ~153 -> clamp
    assert r["is_bullish"] is True
    assert r["is_flat"] is False
    assert r["avg_vol"] == 105


def test_flat_bar_flag():
    r = volume_rank(_df([100.0] * 41, closes=[50.0] * 41, opens=[50.0] * 41))
    assert r["is_flat"] is True
    assert r["is_bullish"] is False


def test_breakout_flag_on_volz():
    spike = volume_rank(_df([100.0] * 40 + [200.0]), breakout_thresh=2.0)
    assert spike["is_breakout"] is True       # volZ ≈ 4.47 ≥ 2.0
    flat = volume_rank(_df([100.0] * 41), breakout_thresh=2.0)
    assert flat["is_breakout"] is False       # volZ 0 < 2.0


def test_insufficient_history_returns_none():
    assert volume_rank(_df([100.0] * 30)) is None     # need ≥ 2*lookback (40)
