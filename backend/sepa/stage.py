"""Minervini 4-Stage classifier.

Stage 1 = Neglect / basing (sideways after Stage 4)
Stage 2 = Advancing — what we want to own
Stage 3 = Topping — exit signal
Stage 4 = Decline — short candidate (or at minimum, avoid)

Source of truth: Mark Minervini, *Trade Like a Stock Market Wizard*,
Chapter 5 "Trading with the Trend," pp. 65-77. Both the MA-geometry
half AND the volume half of each stage are explicit on those pages.

Implementation notes:
  - Stage 2 geometry: price > MA50 > MA150 > MA200, 200DMA slope up (p.71-72)
  - Stage 2 volume:   accumulation — vol spikes on up days/weeks, vol
                      contractions on pullbacks (p.71-72 verbatim)
  - Stage 3 volume:   distribution — major price break on volume since
                      stage 2 began; vol expansion on down days (p.74-76)
  - Stage 4 volume:   more down days/weeks on above-avg volume than up
                      days/weeks on above-avg volume (p.75)

The geometry half was the only thing checked before 2026-05-28. A name
with perfect MA stack but actively-distributing volume would still come
back as `stage: 2` — directly contradicting book p.71-72. This module
now accepts an optional ``vol`` dict from sepa.volume.analyze() and
downgrades Stage-2-by-geometry to Stage 3 (topping) when volume signals
disagree with the stage 2 thesis.
"""
from __future__ import annotations

from typing import Optional
import pandas as pd


def classify(df: pd.DataFrame, *, vol: Optional[dict] = None) -> Optional[dict]:
    """Classify a daily OHLCV series into Weinstein/Minervini stages 1-4.

    Parameters
    ----------
    df : pd.DataFrame
        Daily OHLCV. Requires >= 220 rows for MA200.
    vol : dict, optional
        Output of sepa.volume.analyze(df). When provided, Stage 2
        candidates are confirmed against the volume half of the book
        definition (book p.71-72). Names with distributing accumulation
        or CMF outflow get downgraded to Stage 3 (topping, book p.74-76).
        When omitted, behaviour matches the pre-2026-05-28 classifier
        (geometry only).

    Returns
    -------
    dict with keys: stage (1-4), label (one of {Basing, Advancing,
    Topping, Decline}), slope_up (bool), dist_200_pct (float).
    Stage-2-downgrade-to-Stage-3 cases additionally include
    ``volume_disagreement`` (True) and ``volume_reason`` (str) keys.
    """
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

    # ── Stage 2 GEOMETRY: price > MA50 > MA150 > MA200, 200DMA slope up
    if slope_up and p > s50 > s150 > s200:
        # Book p.71-72 verbatim Stage 2 characteristics:
        #   "Volume spikes on big up days and big up weeks are contrasted
        #    by volume contractions during normal price pullbacks. There
        #    are more up days and up weeks on above-average volume than
        #    down days and down weeks on above-average volume."
        #
        # Distributing accumulation or CMF outflow directly contradicts
        # this. Per book p.74-76, distribution is a Stage 3 (topping)
        # characteristic. So even with perfect MA stack, downgrade if
        # the volume tape is in disagreement. Pre-2026-05-28 behaviour
        # (geometry only) is preserved when vol is None — keeps old
        # callers, including the contracts regression test, working.
        if vol is not None:
            accum = vol.get("accumulation_strength")
            cmf = vol.get("cmf_signal")
            if accum == "distributing" or cmf == "outflow":
                return {
                    "stage":  3,
                    "label":  "Topping",
                    "slope_up": True,
                    "dist_200_pct": round(dist_200, 2),
                    "volume_disagreement": True,
                    "volume_reason": (
                        f"MA geometry is Stage 2 (price > MA50 > MA150 > MA200, "
                        f"200DMA slope up) but volume tape disagrees: "
                        f"accumulation_strength='{accum}', cmf_signal='{cmf}'. "
                        f"Per Minervini p.71-72 Stage 2 requires accumulation; "
                        f"distribution is a Stage 3 (topping) characteristic "
                        f"(p.74-76). Downgraded from 2 -> 3."
                    ),
                }
        return {"stage": 2, "label": "Advancing", "slope_up": True, "dist_200_pct": round(dist_200, 2)}

    # ── Stage 4: price < MA50 < MA150 < MA200, slope down (book p.75)
    if slope_down and p < s50 < s150 < s200:
        return {"stage": 4, "label": "Decline", "slope_up": False, "dist_200_pct": round(dist_200, 2)}

    # ── Stage 3: price still above 200 but 50-MA rolled over + price lost 50-MA
    if p < s50 and s200 > s200_prev and p > s200 * 0.9:
        return {"stage": 3, "label": "Topping", "slope_up": slope_up, "dist_200_pct": round(dist_200, 2)}

    # ── Default: Stage 1 (basing / neglect, book p.67)
    return {"stage": 1, "label": "Basing", "slope_up": slope_up, "dist_200_pct": round(dist_200, 2)}
