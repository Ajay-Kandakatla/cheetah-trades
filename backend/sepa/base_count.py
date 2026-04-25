"""Base count — which base # is the stock in (1=primary, 2, 3, ...).

Book Ch 11: early bases (1st/2nd) = best risk/reward. 4th/5th = late-stage,
failure-prone. A "base" is loosely defined as a consolidation of ≥3 weeks
where price moves sideways after a multi-month advance.

Pragmatic detection:
  - Compute rolling 50-day high.
  - Count the number of times the stock broke out to a new 50-day high after
    being in a consolidation (≥15 bars without a new high) in the past ~2 yrs.
"""
from __future__ import annotations

from typing import Optional
import pandas as pd


def count_bases(df: pd.DataFrame, lookback: int = 504) -> Optional[dict]:
    if df is None or len(df) < 60:
        return None
    c = df["close"].iloc[-lookback:].reset_index(drop=True)
    rolling_high = c.cummax()
    bases = 0
    last_break = -999
    consolidation_bars = 0
    for i in range(1, len(c)):
        if c[i] >= rolling_high[i - 1]:
            # New all-time (in-lookback) high
            if consolidation_bars >= 15 and (i - last_break) > 30:
                bases += 1
                last_break = i
            consolidation_bars = 0
        else:
            consolidation_bars += 1

    # Ensure at least 1 base if stock is in uptrend (primary base)
    if bases == 0 and c.iloc[-1] > c.iloc[0]:
        bases = 1

    return {
        "base_count": bases,
        "is_early_base": bases <= 2,
        "is_late_stage": bases >= 4,
    }
