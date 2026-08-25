"""Deep Demand — price entering the SECOND demand band from the top.

Ajay 2026-08-25: "some stocks are entering second level of demand zone from
the top but sales are intact. this is for penalized stocks that actually have
good revenue but market does not realize it."

Two halves, deliberately split:

* THIS module answers the price half — the geometry of "fell through the
  highest demand band, now arriving at the second one" — inside the demand
  scan, because the names doing this are usually falling knives that fail
  `trend_ok` and therefore never reach the cached `rows` a board could read.
* The revenue half ("sales intact") is joined at BOARD time from the weekly
  `sepa_research_cache` blob (sepa/research.revenue_snapshot), never here:
  fundamentals change on filings, zones change daily, and coupling the two
  would put a Mongo read inside a 1,500-symbol price loop.

Same lazy-import relationship with demand_reentry as into_supply: this module
top-imports demand_reentry's constants; demand_reentry imports THIS module
only inside scan(). Thresholds are IMPORTED, not re-declared — one scale for
"a real band" across the app.
"""
from __future__ import annotations

import logging
from typing import Optional

from .price_zones import NEAR_PCT
from .demand_reentry import MIN_TOUCHES, MIN_ZONE_STRENGTH

log = logging.getLogger("supply_demand.deep_demand")

# Payload cap. The scan keeps every qualifying record's small dict; without a
# cap a bad-breadth day (everything breaking down) could balloon the cached
# payload. 80 >> the 24-tile board will ever show; the count of qualifiers is
# still reported so a capped day says so instead of looking complete.
MAX_ROWS = 80


def read(rec: dict) -> Optional[dict]:
    """The deep-demand read for one scan record, or None.

    Qualifies when ALL of:
      * at least two demand bands are surfaced (demand_zones is high→low)
      * price is BELOW the floor of the highest band — the first level is
        broken or abandoned, which is what "penalized" looks like on a chart
      * price is INSIDE the second band, or approaching it from above within
        price_zones.NEAR_PCT — "entering from the top", not already through it
      * the second band is real by the scan's own bar: MIN_TOUCHES touches
        and MIN_ZONE_STRENGTH strength (imported, one scale)

    Deliberately does NOT require trend_ok / is_reentry — failing the trend
    gate is the point of this screen. The board says so on every tile.
    """
    dz = rec.get("demand_zones") or []
    last = rec.get("last_price")
    if last is None or len(dz) < 2:
        return None
    top, second = dz[0], dz[1]
    t_lo = top.get("lo")
    s_lo, s_hi = second.get("lo"), second.get("hi")
    if t_lo is None or s_lo is None or s_hi is None:
        return None
    if last >= t_lo:
        return None                      # first level still holding — not this screen
    if last < s_lo:
        return None                      # through the second band too — broken, not entering

    if s_lo <= last <= s_hi:
        state = "in"
        dist_pct = 0.0
    else:                                # between the bands, coming down
        dist_pct = (last - s_hi) / last * 100.0
        if dist_pct > NEAR_PCT:
            return None
        state = "near"

    if (second.get("touches") or 0) < MIN_TOUCHES:
        return None
    if (second.get("strength") or 0) < MIN_ZONE_STRENGTH:
        return None

    tb = rec.get("top_band_read") or {}
    return {
        "state": state,                          # "in" | "near"
        "dist_pct": round(dist_pct, 2),
        "top_band": {"lo": top.get("lo"), "hi": top.get("hi")},
        "second_band": {"lo": s_lo, "hi": s_hi,
                        "touches": second.get("touches"),
                        "strength": second.get("strength")},
        # How far below the broken first level price sits.
        "below_top_pct": round((t_lo - last) / t_lo * 100.0, 2),
        # Break evidence for the FIRST band, computed in decide_from_frame
        # where the closes series still exists. None on older cached rows.
        "bars_since_top_break": tb.get("bars_since_break"),
        "fell_from_pct": tb.get("fell_from_pct"),
    }


def sort_key(row: dict):
    """IN-band first, then closest to arriving, then the stronger second band."""
    d = row.get("deep_demand") or {}
    in_band = 0 if d.get("state") == "in" else 1
    return (in_band, d.get("dist_pct") or 0.0,
            -((d.get("second_band") or {}).get("strength") or 0.0))
