"""Power Play setup detector — Minervini Ch 10 p.254-255.

Criteria:
  1. Explosive move: +100% in ≤8 weeks (~40 trading days) on huge volume.
  2. Sideways digest: 3-6 weeks, correcting ≤20-25%.
  3. Tight final action: ≤10% (or VCP characteristics).

Does NOT require fundamentals — the price/volume action IS the signal.
"""
from __future__ import annotations

from typing import Optional
import pandas as pd


def detect(df: pd.DataFrame) -> Optional[dict]:
    if df is None or len(df) < 80:
        return None
    c = df["close"]
    # Find max 40-bar gain ending before the last 15 bars (give room for consolidation)
    recent = c.iloc[-80:]
    best_gain_pct = 0.0
    gain_end_idx = -1
    for i in range(40, len(recent) - 15):
        start = float(recent.iloc[i - 40])
        end = float(recent.iloc[i])
        if start <= 0:
            continue
        g = (end / start - 1) * 100
        if g > best_gain_pct:
            best_gain_pct = g
            gain_end_idx = i

    if best_gain_pct < 100 or gain_end_idx < 0:
        return {"is_power_play": False, "best_40d_gain_pct": round(best_gain_pct, 2)}

    # Consolidation window = gain_end_idx → end
    consol = recent.iloc[gain_end_idx:]
    hi = float(consol.max())
    lo = float(consol.min())
    consol_depth = (1 - lo / hi) * 100 if hi else 0
    tight = consol_depth <= 25
    final = recent.iloc[-10:]
    final_depth = (1 - float(final.min()) / float(final.max())) * 100 if float(final.max()) else 0
    very_tight = final_depth <= 10
    bars = len(consol)

    return {
        "is_power_play": bool(tight and very_tight and bars >= 12),
        "best_40d_gain_pct": round(best_gain_pct, 2),
        "consolidation_bars": bars,
        "consolidation_depth_pct": round(consol_depth, 2),
        "final_10d_range_pct": round(final_depth, 2),
        "pivot_buy_price": round(hi, 2),
        "suggested_stop": round(lo, 2),
    }
