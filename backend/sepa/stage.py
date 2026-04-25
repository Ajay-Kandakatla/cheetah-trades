"""Minervini 4-Stage classifier.

Stage 1 = Neglect / basing (sideways after Stage 4)
Stage 2 = Advancing — what we want to own
Stage 3 = Topping — exit signal
Stage 4 = Decline — short candidate (or at minimum, avoid)

Heuristic matches Ch 4 of the book: classify by MA geometry + slope of 200-MA
+ price position vs MA200.
"""
from __future__ import annotations

from typing import Optional
import pandas as pd


def classify(df: pd.DataFrame) -> Optional[dict]:
    if df is None or len(df) < 220:
        return None
    c = df["close"]
    ma50 = c.rolling(50).mean()
    ma150 = c.rolling(150).mean()
    ma200 = c.rolling(200).mean()
    p = float(c.iloc[-1])
    s50, s150, s200 = float(ma50.iloc[-1]), float(ma150.iloc[-1]), float(ma200.iloc[-1])

    # 200-DMA slope: up if > value 22 bars ago
    s200_prev = float(ma200.iloc[-22])
    slope_up = s200 > s200_prev
    slope_down = s200 < s200_prev

    # Price distance from 200-MA (%)
    dist_200 = (p / s200 - 1) * 100 if s200 else 0

    # Stage 2: price > MA50 > MA150 > MA200, slope up
    if slope_up and p > s50 > s150 > s200:
        return {"stage": 2, "label": "Advancing", "slope_up": True, "dist_200_pct": round(dist_200, 2)}

    # Stage 4: price < MA50 < MA150 < MA200, slope down
    if slope_down and p < s50 < s150 < s200:
        return {"stage": 4, "label": "Decline", "slope_up": False, "dist_200_pct": round(dist_200, 2)}

    # Stage 3: price still above 200 but 50-MA rolled over + price lost 50-MA
    if p < s50 and s200 > s200_prev and p > s200 * 0.9:
        return {"stage": 3, "label": "Topping", "slope_up": slope_up, "dist_200_pct": round(dist_200, 2)}

    # Default: Stage 1 (basing / neglect)
    return {"stage": 1, "label": "Basing", "slope_up": slope_up, "dist_200_pct": round(dist_200, 2)}
