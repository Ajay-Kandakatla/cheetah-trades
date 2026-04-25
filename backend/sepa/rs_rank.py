"""IBD-style Relative Strength rank.

Per IBD's formula: weight 3-, 6-, 9-, 12-month price returns 40/20/20/20 and
percentile-rank across the full universe. Output is 1-99 where higher = leader.
"""
from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

from .prices import load_prices


def _return(df: pd.DataFrame, lookback_days: int) -> Optional[float]:
    if df is None or len(df) < lookback_days + 1:
        return None
    start = df["close"].iloc[-lookback_days - 1]
    end = df["close"].iloc[-1]
    if start == 0:
        return None
    return float(end / start - 1)


def rs_score(df: pd.DataFrame) -> Optional[float]:
    r63 = _return(df, 63)    # ~3 months
    r126 = _return(df, 126)  # ~6 months
    r189 = _return(df, 189)  # ~9 months
    r252 = _return(df, 252)  # ~12 months
    parts = [r63, r126, r189, r252]
    if any(p is None for p in parts):
        return None
    return 0.4 * r63 + 0.2 * r126 + 0.2 * r189 + 0.2 * r252


def rs_ranks(symbols: list[str]) -> Dict[str, int]:
    """Return {symbol: rank 1-99}. Symbols with insufficient data are omitted."""
    scores: Dict[str, float] = {}
    for s in symbols:
        df = load_prices(s)
        val = rs_score(df)
        if val is not None:
            scores[s] = val
    if not scores:
        return {}

    series = pd.Series(scores)
    # percentile rank: 0-1 → 1-99
    pct = series.rank(pct=True)
    return {sym: max(1, min(99, int(round(pct[sym] * 99)))) for sym in scores}
