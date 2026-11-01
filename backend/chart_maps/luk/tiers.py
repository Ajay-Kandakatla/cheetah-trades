"""🥇 Luk's watchlist tiers — his guest post, his words (BUILD SPEC luk-tab §3.5, 2026-11-01).

"Lead: 9 EMA > 21 EMA > 50 EMA." "Mediocre: 9 EMA > 21 EMA < 50 EMA or 9 EMA < 21 EMA > 50 EMA." "Lag: 9 EMA < 21 EMA
< 50 EMA." "One for small caps (<$5B market cap)" — https://tradingresourcehub.substack.com/p/martin-luk-283-usic-2024-key-lessons
(2025-02-01). Lead and Lag are STRICT orders; anything else — equal EMAs included — is Mediocre (MINE, HIS CALL #17).
A tier is a label on a row, never a gate.
"""
from __future__ import annotations

from typing import Optional

from chart_maps.luk import constants as LC

LEAD, MEDIOCRE, LAG = "lead", "mediocre", "lag"
TIERS = (LEAD, MEDIOCRE, LAG)
TIER_TEXT = {
    LEAD: "Lead — 9 EMA > 21 EMA > 50 EMA",
    LAG: "Lag — 9 EMA < 21 EMA < 50 EMA",
    MEDIOCRE: "Mediocre — in between",
}
SMALL_CAP_TEXT = "small cap (<${b:g}B) — his second list"
_BILLION = 1_000_000_000                    # a unit, not a rule


def _num(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None            # NaN → None


def tier_of(e9, e21, e50) -> Optional[str]:
    """"lead" when 9 > 21 > 50, "lag" when 9 < 21 < 50 (both strict), else "mediocre"; None when any EMA is missing."""
    a, b, c = _num(e9), _num(e21), _num(e50)
    if a is None or b is None or c is None:
        return None
    if a > b > c:
        return LEAD
    if a < b < c:
        return LAG
    return MEDIOCRE


def tier_text(tier) -> Optional[str]:
    return TIER_TEXT.get(tier) if isinstance(tier, str) else None


def small_cap_text(cap) -> Optional[str]:
    """His second list's chip when the cap is known and under LUK_SMALL_CAP_USD; None otherwise (unknown is not small)."""
    v = _num(cap)
    if v is None or v <= 0 or v >= LC.LUK_SMALL_CAP_USD:
        return None
    return SMALL_CAP_TEXT.format(b=LC.LUK_SMALL_CAP_USD / _BILLION)
