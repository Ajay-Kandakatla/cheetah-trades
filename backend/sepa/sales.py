"""Sales Confidence Score — sales/revenue-driven stock conviction.

Inspired by Pradeep Bonde ("Stockbee"). What he DOCUMENTS about sales, verbatim:
  2007 'How to trade earnings' — "Sales/revenue should be up 5% or more."
       https://stockbee.blogspot.com/2007/03/how-to-trade-earnings.html
  2010 EP catalogue — a catalyst CATEGORY named "Sales 100% plus but no earnings"
       https://stockbee.blogspot.com/2010/02/what-are-episodic-pivots-and-how-to.html
  2025 — "Their real moves start when they start growing revenue aggressively."
       and a scan for "two quarters of revenue growth of 39% plus"
       https://stockbee.blogspot.com/2025/09/find-young-episodic-pivots.html

This is a PRINCIPLED score this app built — NOT a Bonde formula (he publishes
no 0-100 score). Tiers:
  >= 5%   HIS floor (2007).
  >= 25%  THIS APP'S mid-tier, chosen 2026-06-02. Until 2026-09-20 it was
          mis-attributed to him through a fabricated first-person quote;
          no such sentence exists in any of his posts.
  >= 100% the boundary of his 2010 "Sales 100% plus" catalyst category,
          used here as a tier by this app.
His two-quarter revenue figure from 2025-09-01 is HIS and is shown on the
📈 Bonde tab as its own pick leg; whether it joins or replaces a tier is
Ajay's call.
Figures that FAILED source verification and are not used: 30% and
"MAGNA 53+" (Deepvue / TradeZella / TraderLion, not Stockbee).
The app's acceleration / consistency / sales-led flags are this app's
reads: his 'acceleration' is EARNINGS acceleration (2007, 2010) and his
only two-quarter rule is the 2025 revenue scan above. Growth is YoY here
(canslim parity); for EARNINGS he names BOTH legs — "compared to last year
same quarter as well as quarter over quarter" (2010). Full sourcing:
docs/sepa/sales_confidence_methodology.md.
"""
from __future__ import annotations

from typing import List, Optional

# Sales tiers — LOCKED (see test_sepa_contracts.py). Whose number is whose:
# see the module docstring above.
SALES_FLOOR_PCT = 5.0       # his floor (2007)
SALES_PREFERRED_PCT = 25.0  # THIS APP'S mid-tier (not his; see docstring)
SALES_EXPLOSIVE_PCT = 100.0  # boundary of his 2010 "Sales 100% plus" category


# The falling-knife gate's pass set (Deep Demand / Gabbar boards, and the
# portfolio knife watch): only tiers with a growing top line pass. The
# 5 / 25 / 100 percent tier anchors are computed below in `compute`.
BONDE_PASS_TIERS = ("steady", "strong", "explosive")


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

    # Sales-led — top line outpacing the bottom line. THIS APP'S read; Bonde's
    # 2007 gate is earnings-first and he names no such concept.
    sales_led = bool(eps_growth_q is not None and g > eps_growth_q)

    # Growth-level base, anchored to the 5 / 25 / 100 tiers above.
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
