"""ADR — Average Daily Range (20-period).

A liquidity/volatility quality filter Minervini implicitly requires:
SEPA setups need enough intraday range to produce 20-25% pivot moves
without taking weeks. ADR < 3% = sluggish; ADR ≥ 4% = tradeable; ADR ≥ 6%
= momentum-ready.

Formula (industry standard):
    ADR% = 100 * (mean(high/low) - 1) over last N bars
"""
from __future__ import annotations

from typing import Optional
import pandas as pd


def adr_pct(df: pd.DataFrame, period: int = 20) -> Optional[float]:
    """Return ADR% over `period` bars, or None if insufficient data."""
    if df is None or len(df) < period:
        return None
    sl = df.iloc[-period:]
    if (sl["low"] <= 0).any():
        return None
    ratio = (sl["high"] / sl["low"]).mean()
    return round((ratio - 1) * 100, 2)


def liquidity_check(df: pd.DataFrame,
                    min_dollar_vol: float = 20_000_000,
                    min_shares: int = 200_000,
                    period: int = 50) -> dict:
    """Institutional-grade liquidity check.

    Minervini: avoid thin stocks — institutions cannot accumulate them, so
    you have no smart money tailwind. Standard floors:
      - 50-day avg $-volume ≥ $20M (preferred)
      - OR 50-day avg shares ≥ 200,000 (acceptable for smaller names)
    """
    if df is None or len(df) < period:
        return {"liquid": False, "reason": "insufficient history",
                "avg_dollar_vol": 0, "avg_shares": 0}
    sl = df.iloc[-period:]
    avg_shares = float(sl["volume"].mean())
    avg_dollar_vol = float((sl["close"] * sl["volume"]).mean())
    liquid = avg_dollar_vol >= min_dollar_vol or avg_shares >= min_shares
    return {
        "liquid": liquid,
        "avg_dollar_vol": round(avg_dollar_vol, 0),
        "avg_shares": int(avg_shares),
        "reason": None if liquid else "below institutional floor",
    }
