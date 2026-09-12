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
    you have no smart money tailwind. ONE floor:
      - 50-day avg $-volume >= $20M

    2026-09-11 — the share-count leg is GONE. It used to read
    `avg_dollar_vol >= min_dollar_vol OR avg_shares >= min_shares`, and the
    OR made the $-volume floor decorative: 848 of 2,945 scanned rows passed
    on the share leg ALONE, 328 of them under $5, and ARAI read liquid=True
    on $148,074 of daily turnover. Shares are not liquidity — 200k shares of
    a $0.74 stock is $148k, which one order moves.

    Ajay first asked for OR -> AND. Measured before shipping: AND removes
    901 names (30.6%) but 53 of them are high-PRICED institutional names
    that trade few shares because each share is expensive — NVR ($6,160/sh
    on ~32k shares/day), SEB ($4,296), MTD ($1,293), FCNCA, MKL. Those are
    the opposite of the manipulation risk he asked to be protected from.
    Deleting the share leg removes the SAME 848 penny names and keeps all
    53. min_shares is kept in the signature (unused, reported) so callers
    and stored rows do not break; test_adr.py pins that it cannot rescue a
    thin name.
    """
    if df is None or len(df) < period:
        return {"liquid": False, "reason": "insufficient history",
                "avg_dollar_vol": 0, "avg_shares": 0}
    sl = df.iloc[-period:]
    avg_shares = float(sl["volume"].mean())
    avg_dollar_vol = float((sl["close"] * sl["volume"]).mean())
    liquid = avg_dollar_vol >= min_dollar_vol
    return {
        "liquid": liquid,
        "avg_dollar_vol": round(avg_dollar_vol, 0),
        "avg_shares": int(avg_shares),
        "reason": None if liquid else "below institutional floor",
    }
