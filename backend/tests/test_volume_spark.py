"""Volume-trend sparkline (vol_spark) — behavioral + display-only guards.

The sparkline is the last ``VOL_SPARK_BARS`` daily bars as a SIGNED-volume
series: magnitude = the bar's real volume, sign = up-day (close ≥ prior close)
vs down-day. It powers the FE volume-trend mini-histogram on the SEPA card +
detail page. It is DISPLAY-ONLY and must never reach the scanner score.
"""
from __future__ import annotations

import pandas as pd

from sepa import volume as V


def _ohlcv(n: int = 70) -> pd.DataFrame:
    """Deterministic OHLCV: a mostly-rising path with a down day every 4th bar
    (so the last 20 bars carry both up and down days), and strictly-distinct
    volumes so magnitude→volume mapping is verifiable bar-for-bar."""
    closes, px = [], 100.0
    for i in range(n):
        px += 1.0 if (i % 4 != 3) else -0.5     # up,up,up,down,...
        closes.append(round(px, 2))
    vols = [1_000_000 + i * 1_000 for i in range(n)]
    return pd.DataFrame({
        "open":   closes,
        "high":   [c + 1.0 for c in closes],
        "low":    [c - 1.0 for c in closes],
        "close":  closes,
        "volume": vols,
    })


def test_vol_spark_shape_and_signs():
    df = _ohlcv(70)
    out = V.analyze(df)
    assert out is not None
    spark = out["vol_spark"]
    assert isinstance(spark, list)
    assert len(spark) == V.VOL_SPARK_BARS == 20

    closes = df["close"].tolist()
    vols = df["volume"].tolist()
    for k in range(20):
        idx = len(df) - 20 + k
        up = closes[idx] >= closes[idx - 1]
        expected = vols[idx] if up else -vols[idx]
        assert spark[k] == expected, f"bar {k}: got {spark[k]} expected {expected}"

    # Magnitude is ALWAYS the real volume regardless of the up/down sign.
    assert [abs(x) for x in spark] == vols[-20:]
    # The deterministic path has down days, so the series must contain negatives.
    assert any(x < 0 for x in spark) and any(x > 0 for x in spark)


def test_vol_spark_short_history_safe():
    # Fewer than VOL_SPARK_BARS bars (but enough for analyze's 60-bar floor):
    # the series simply shortens, never raises.
    out = V.analyze(_ohlcv(63))
    assert out is not None
    assert isinstance(out["vol_spark"], list)
    assert len(out["vol_spark"]) == 20  # 63 ≥ 20, so still a full window


def test_breakout_count_counts_distinct_events():
    # Flat volume with four separated 3× spikes on a rising (new-high) close →
    # four distinct breakouts. Spikes placed past bar 50 so the 50-day average is
    # defined. A multi-day push would still count once (rising edges).
    n = 130
    close = [100 + 0.1 * i for i in range(n)]
    vol = [1_000_000] * n
    for b in (60, 80, 100, 120):
        vol[b] = 3_000_000
    df = pd.DataFrame({
        "open": close, "high": [c + 1 for c in close],
        "low": [c - 1 for c in close], "close": close, "volume": vol,
    })
    out = V.analyze(df)
    assert out["breakout_count"] == 4
    assert out["breakout_window_bars"] == min(V.BREAKOUT_COUNT_LOOKBACK, n)


def test_breakout_count_zero_without_volume_spikes():
    # The deterministic rising path with slowly-rising flat volume never clears
    # the 1.5× threshold → zero breakouts.
    out = V.analyze(_ohlcv(70))
    assert out["breakout_count"] == 0


def test_breakout_count_is_display_only_not_scored():
    import inspect
    from sepa import scanner
    assert "breakout_count" not in inspect.getsource(scanner), (
        "scanner.py references breakout_count — it must stay display-only."
    )


def test_vol_spark_is_display_only_not_scored():
    # Hard contract: the scanner score must never read the sparkline — it's a
    # display series, not a signal. Mirrors the analyst-pulse isolation guard.
    import inspect
    from sepa import scanner
    assert "vol_spark" not in inspect.getsource(scanner), (
        "scanner.py references vol_spark — the volume-trend sparkline must "
        "stay display-only and out of scoring."
    )
