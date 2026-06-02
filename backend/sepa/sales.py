"""Sales Confidence Score — sales/revenue-driven stock conviction.

Inspired by Pradeep Bonde ("Stockbee"), who emphasises company SALES growth and
ACCELERATION as a driver of explosive moves: his Episodic-Pivot catalyst list
names "Sales Acceleration", and he writes (Stockbee, Sept 2025) "...it is
revenue growth that investors focus on", with a standalone "Sales 100% plus but
no earnings" EP category (2010).

This is a PRINCIPLED score anchored to the only sales numbers Bonde documents in
HIS OWN writing — it is NOT a verbatim Bonde formula (he never publishes a 0-100
score), and it deliberately does NOT use the tighter third-party figures
(30% / 39% two-quarter / "MAGNA 53+") that are widely attributed to him but
FAILED source verification (they come from Deepvue / TradeZella / TraderLion, not
Stockbee). Full sourcing + the QoQ-vs-YoY caveat live in
docs/sepa/sales_confidence_methodology.md.

Bonde-documented sales thresholds (Stockbee 2007 "How to trade earnings"; 2010
EP taxonomy):
    >= 5%   — his floor          ("I take 5%")
    25%+    — his preferred/ideal ("you can use 25% plus")
    100%+   — his "Sales 100% plus" Episodic-Pivot category
Acceleration (growth rate rising) and consistency (consecutive growth quarters)
are his NAMED qualitative catalysts; the numeric weighting of them here is ours.

Growth is YoY (latest quarter vs the same quarter a year earlier) to match the
app's existing canslim metrics and the more common reading of Bonde's ambiguous
"quarter over quarter" phrasing (see the methodology doc).
"""
from __future__ import annotations

from typing import List, Optional

# Bonde-documented sales thresholds — LOCKED (see test_sepa_contracts.py).
SALES_FLOOR_PCT = 5.0       # his floor
SALES_PREFERRED_PCT = 25.0  # his preferred
SALES_EXPLOSIVE_PCT = 100.0  # his "Sales 100% plus" category


def _yoy(series: List[Optional[float]], i: int) -> Optional[float]:
    """YoY revenue growth % for quarter index ``i``: series[i] vs series[i+4]
    (the same quarter a year earlier). ``series`` is newest-first quarterly
    revenue. None when either quarter is missing or the base is zero."""
    if len(series) <= i + 4:
        return None
    a, b = series[i], series[i + 4]
    if a is None or b is None or b == 0:
        return None
    return (a - b) / abs(b) * 100.0


def compute(rev_q_series: List[Optional[float]],
            eps_growth_q: Optional[float] = None) -> dict:
    """Sales confidence from a newest-first quarterly revenue series.

    Returns growth_yoy_pct, prior_yoy_pct, accelerating, consecutive_growth_q,
    sales_led, tier, and a 0-100 ``score`` — or score=None when there isn't
    enough revenue history (need >= 5 quarters for one YoY comparison)."""
    series = list(rev_q_series or [])
    g = _yoy(series, 0)
    if g is None:
        return {
            "score": None, "tier": "unknown", "growth_yoy_pct": None,
            "prior_yoy_pct": None, "accelerating": None,
            "consecutive_growth_q": 0, "sales_led": None,
            "reason": "insufficient revenue history (need >= 5 quarters)",
        }

    prior = _yoy(series, 1)
    accelerating = bool(prior is not None and g > prior and g > 0)

    # Consistency — consecutive most-recent quarters with positive YoY growth.
    consec = 0
    for i in range(4):
        gi = _yoy(series, i)
        if gi is not None and gi > 0:
            consec += 1
        else:
            break

    # Sales-led — top line outpacing the bottom line (organic growth, not
    # buybacks/financial engineering); Bonde's "revenue growth investors focus on".
    sales_led = bool(eps_growth_q is not None and g > eps_growth_q)

    # Growth-level base, anchored to Bonde's 5 / 25 / 100 tiers.
    if g < 0:
        base = max(0.0, 20.0 + g * 0.5)                                   # declining
    elif g < SALES_FLOOR_PCT:
        base = 20.0 + (g / SALES_FLOOR_PCT) * 15.0                        # 20-35 (below floor)
    elif g < SALES_PREFERRED_PCT:
        base = 35.0 + ((g - SALES_FLOOR_PCT)
                       / (SALES_PREFERRED_PCT - SALES_FLOOR_PCT)) * 20.0  # 35-55 (confirming)
    elif g < SALES_EXPLOSIVE_PCT:
        base = 55.0 + ((g - SALES_PREFERRED_PCT)
                       / (SALES_EXPLOSIVE_PCT - SALES_PREFERRED_PCT)) * 30.0  # 55-85 (strong)
    else:
        base = min(100.0, 85.0 + (g - SALES_EXPLOSIVE_PCT) / 100.0 * 15.0)    # 85-100 (explosive)

    # Acceleration / consistency / sales-led bonuses apply only ABOVE Bonde's
    # 5% floor — a barely-growing or declining name stays weak no matter how
    # "consistent" its tiny growth is.
    bonus = 0.0
    if g >= SALES_FLOOR_PCT:
        bonus = ((10.0 if accelerating else 0.0)
                 + min(10.0, consec * 2.5)
                 + (5.0 if sales_led else 0.0))
    score = int(max(0.0, min(100.0, round(base + bonus))))

    tier = ("explosive" if g >= SALES_EXPLOSIVE_PCT else
            "strong" if g >= SALES_PREFERRED_PCT else
            "steady" if g >= SALES_FLOOR_PCT else
            "weak" if g >= 0 else
            "declining")

    return {
        "score": score,
        "tier": tier,
        "growth_yoy_pct": round(g, 1),
        "prior_yoy_pct": round(prior, 1) if prior is not None else None,
        "accelerating": accelerating,
        "consecutive_growth_q": consec,
        "sales_led": sales_led,
    }
