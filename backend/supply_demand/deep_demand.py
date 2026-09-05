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

# Payload caps, PER STATE (2026-09-03). The scan keeps every qualifying
# record's small dict; without a cap a bad-breadth day (everything breaking
# down) could balloon the cached payload. Until 2026-09-03 this was one
# MAX_ROWS = 80 trim applied after a CMF-first sort, which happened to keep a
# 49 in / 31 near mix. The sort is now closest-first (in-band before near —
# demand_order.proximity_key), so a single cap would fill with in-band rows
# and the Chart Maps "approaching" toggle (state "near") could go EMPTY on a
# day with 80+ in-band arrivals. Measured 2026-09-03 17:22 UTC: deep_n = 242,
# ~61/39 in/near in the kept sample → ~148 in / ~94 near — both caps fill.
# 60 + 40 = 100 > the 24-tile board will ever show; deep_n still reports the
# uncapped total so a capped day says so instead of looking complete.
MAX_IN = 60
MAX_NEAR = 40
MAX_ROWS = MAX_IN + MAX_NEAR          # the payload ceiling, derived


def cap(rows: list) -> list:
    """Trim an already-sorted deep list to MAX_IN in-band + MAX_NEAR near rows,
    preserving order. Rows with any other state are kept (there are none by
    construction; if one appears it should be seen, not silently dropped)."""
    kept, n_in, n_near = [], 0, 0
    for r in rows:
        st = (r.get("deep_demand") or {}).get("state")
        if st == "in":
            if n_in >= MAX_IN:
                continue
            n_in += 1
        elif st == "near":
            if n_near >= MAX_NEAR:
                continue
            n_near += 1
        kept.append(r)
    return kept


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
        # Break evidence for the FIRST band — demand_reentry.band_break_read,
        # computed in decide_from_frame where the closes series still exists.
        # `bars_since_top_break` is the age of the FIRST close under the top
        # band in the current leg (when it fell through); the most recent one
        # is always today for a name still under its floor. `fell_from_pct` is
        # how far above the top band the run-up before that break reached.
        # None only on cached rows older than 2026-09-05 (before that date the
        # scan fed reentry_read, which is empty whenever price is outside the
        # band — i.e. always here — so the field was dead on every row).
        "bars_since_top_break": tb.get("bars_since_first_break"),
        "fell_from_pct": tb.get("fell_from_pct"),
    }


def inflow_read(vol: Optional[dict]) -> Optional[dict]:
    """Distill sepa/volume.analyze() into the deep-demand inflow verdict.

    Ajay 2026-08-25: "they are very bearish from institutions and retailer —
    we are looking for bullish momentum stocks and inflow signals for these."
    A name that broke its first band IS under distribution almost by
    definition; the question this answers is whether money has STARTED
    flowing back in while price sits at the second band.

    Every threshold is sepa/volume.py's own (CMF ±0.10 zones tuned 2026-05-21
    against a 977-name sample; accumulation/distribution day counts per
    Minervini p.71-76, count-of-days not sum-of-volume). This function only
    CLASSIFIES — it must never re-derive a number.

      inflow        — CMF-20 at/above the module's inflow zone, or positive
                      CMF with more accumulation than distribution days
      distribution  — the mirror image
      neutral       — everything else, including a missing CMF (thin data
                      must never read as either signal)
    """
    if not vol:
        return None
    from sepa.volume import CMF_INFLOW_THRESHOLD, CMF_OUTFLOW_THRESHOLD
    cmf = vol.get("cmf_20")
    acc = vol.get("accumulation_days_25") or 0
    dist = vol.get("distribution_days_25") or 0
    if cmf is None:
        state = "neutral"
    elif cmf >= CMF_INFLOW_THRESHOLD or (cmf > 0 and acc > dist):
        state = "inflow"
    elif cmf <= CMF_OUTFLOW_THRESHOLD or (cmf < 0 and dist > acc):
        state = "distribution"
    else:
        state = "neutral"
    return {
        "state": state,
        "cmf_20": cmf,
        "accum_days_25": acc,
        "dist_days_25": dist,
        "net_dollar_vol_50": vol.get("net_dollar_vol_50"),
        # TLSW-cited momentum footprint at lows — the strongest single
        # "buyers are back" bar there is (volume.py _pocket_pivot).
        "pocket_pivot": bool(vol.get("pocket_pivot")),
    }


def sort_key(row: dict, px=None):
    """Closest to the second band first; money flow breaks ties.

    Ajay 2026-09-03: "make sure in our other demand and deep demand keep the
    closest one to demand zones on the top. Of course CMF inflow too
    considered." SUPERSEDES the 2026-08-26 "rank these by highest CMF on the
    top" order, under which NOG — 2.53% ABOVE its second band — ranked over
    52 names already inside theirs because its CMF was the largest.

    The order is demand_order.proximity_key (one definition for every demand
    board): inside the band, then nearest approaching in 0.5% buckets; inside
    a bucket inflow > neutral > distribution > missing, then the stronger
    CMF; then the exact distance; then the stronger second band, then symbol.
    `px` lets Chart Maps rank on the LIVE print instead of the scan price.
    """
    from .demand_order import deep_key
    return deep_key(row, px=px)
