"""Minervini Trend Template — the 8 Stage-2 criteria.

A stock must satisfy ALL eight to be a SEPA candidate. We also return the
individual pass/fail dict so the UI can render checkmarks.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import pandas as pd


@dataclass
class TrendResult:
    symbol: str
    pass_all: bool
    passed: int
    checks: dict
    preferred: dict
    price: Optional[float]
    ma50: Optional[float]
    ma150: Optional[float]
    ma200: Optional[float]
    week52_high: Optional[float]
    week52_low: Optional[float]
    pct_above_low: Optional[float]
    pct_below_high: Optional[float]

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate(symbol: str, df: pd.DataFrame) -> Optional[TrendResult]:
    """Run all 8 checks against a daily OHLCV frame. Needs ~252 trading days."""
    if df is None or len(df) < 220:
        return None

    close = df["close"]
    ma50 = close.rolling(50).mean()
    ma150 = close.rolling(150).mean()
    ma200 = close.rolling(200).mean()

    price = float(close.iloc[-1])
    v_ma50 = float(ma50.iloc[-1])
    v_ma150 = float(ma150.iloc[-1])
    v_ma200 = float(ma200.iloc[-1])
    ma200_22_ago = float(ma200.iloc[-22]) if len(ma200) >= 22 else float("nan")
    # Minervini: 200-DMA up ≥1 month = pass, ≥5 months (≈110 bars) = preferred.
    ma200_110_ago = float(ma200.iloc[-110]) if len(ma200) >= 110 else float("nan")

    window = close.iloc[-252:] if len(close) >= 252 else close
    hi52 = float(window.max())
    lo52 = float(window.min())
    pct_above_low = (price / lo52 - 1) * 100 if lo52 else None
    pct_below_high = (1 - price / hi52) * 100 if hi52 else None

    checks = {
        "price_above_ma150_and_ma200": price > v_ma150 and price > v_ma200,
        "ma150_above_ma200": v_ma150 > v_ma200,
        "ma200_trending_up": v_ma200 > ma200_22_ago,
        "ma50_above_ma150_above_ma200": v_ma50 > v_ma150 > v_ma200,
        "price_above_ma50": price > v_ma50,
        "at_least_30pct_above_52w_low": pct_above_low is not None and pct_above_low >= 30,
        "within_25pct_of_52w_high": pct_below_high is not None and pct_below_high <= 25,
        # Gate stays True here — scanner re-sets after rs_ranks() is computed
        # so this function still runs standalone against a single DataFrame.
        "rs_rank_at_least_70": True,
    }
    preferred = {
        "ma200_trending_up_5mo": (
            ma200_110_ago == ma200_110_ago  # NaN guard
            and v_ma200 > ma200_110_ago
        ),
    }

    passed = sum(1 for v in checks.values() if v)
    return TrendResult(
        symbol=symbol,
        pass_all=all(checks.values()),
        passed=passed,
        checks=checks,
        preferred=preferred,
        price=round(price, 4),
        ma50=round(v_ma50, 4),
        ma150=round(v_ma150, 4),
        ma200=round(v_ma200, 4),
        week52_high=round(hi52, 4),
        week52_low=round(lo52, 4),
        pct_above_low=round(pct_above_low, 2) if pct_above_low is not None else None,
        pct_below_high=round(pct_below_high, 2) if pct_below_high is not None else None,
    )
