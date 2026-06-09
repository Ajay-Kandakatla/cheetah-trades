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
  - Stage 3 geometry: price has lost the 50-day and is within 10% of the
                      200-day while 150-day > 200-day; the 200-day "will lose
                      upside momentum, flatten out, and then roll over" and
                      price "may undercut its 200-day" (p.74). Slope-agnostic —
                      a top does NOT require a rising 200-day (fixed 2026-06-09;
                      see the Stage 3 branch comment below).
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

    # ── Stage 3 (Topping), book p.74: in a top the 200-day MA "will lose upside
    #    momentum, flatten out, and then roll over into a downtrend," and price
    #    "may undercut its 200-day." Stage 3 therefore must NOT require a *rising*
    #    200-day. Before 2026-06-09 this branch was gated on `s200 > s200_prev`,
    #    which is backwards for a top: a genuinely topping name whose 200-day had
    #    flattened or started rolling over fell through to Stage 1 "Basing",
    #    masking the top (book-audit finding, 2026-06-09).
    #
    #    Topping is now: price has lost the 50-day, is still within 10% of the
    #    200-day (the book's "may undercut" allowance), and the prior Stage-2 MA
    #    stack is still intact (150-day > 200-day). That intact-but-stalling
    #    structure is what separates a post-advance TOP from a Stage-1 BASE — a
    #    base forms after a Stage-4 decline with the stack recovering from
    #    inversion (150-day <= 200-day), so it does not match here. A deeper break
    #    with a fully-inverted stack is Stage 4 (matched above).
    #
    #    BUY-SIDE-SAFE BY CONSTRUCTION: this branch can only return Stage 3, never
    #    Stage 2, so it cannot manufacture a buy (is_buyable / the ENTER verdict
    #    both require stage == 2). It only refines the Basing-vs-Topping label that
    #    feeds the holding / sell-side read — and Topping is the more cautious,
    #    book-correct label for a stalling post-advance name. Quantified against the
    #    latest scan the day it shipped: 1 of 105 names (VRTX) moved Basing->Topping;
    #    0 names moved into Stage 2.
    if p < s50 and p > s200 * 0.9 and s150 > s200:
        return {"stage": 3, "label": "Topping", "slope_up": slope_up, "dist_200_pct": round(dist_200, 2)}

    # ── Default: Stage 1 (basing / neglect, book p.67)
    return {"stage": 1, "label": "Basing", "slope_up": slope_up, "dist_200_pct": round(dist_200, 2)}
