"""Deep Demand — price arriving at the 2nd or 3rd demand level from the top.

Ajay 2026-08-25: "some stocks are entering second level of demand zone from
the top but sales are intact. this is for penalized stocks that actually have
good revenue but market does not realize it."

Ajay 2026-09-16, widening it: "For the deep demand stocks I need the logic to
be, the stocks that crosses the first level of support and lying in second or
third level of support. Like CRDO dropped after the earning it crossed
multiple support level." Until then `read()` looked at the fixed pair
`demand_zones[0]` / `demand_zones[1]`; it now WALKS the same served window and
counts every level already crossed, capped by MAX_LEVELS_BROKEN.

Two halves, deliberately split:

* THIS module answers the price half — the geometry of "fell through one or
  more demand bands, now arriving at the next level down" — inside the demand
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

# How deep the screen goes (2026-09-16). Ajay's sentence read literally —
# "lying in second or third level of support" — is levels_broken ∈ {1, 2},
# i.e. an arrival at the 2nd or the 3rd level. ONE named constant so widening
# to 3 (the deepest a four-band served window can even express) is a one-line
# edit after the study, and so the board note and the ℹ️ Rules prose can be
# built from it instead of retyping "2nd or 3rd" in three places.
#
# Depth is NOT a measured edge: the 2026-09-16 band-structure study measured
# `no_signal` on the adjacent claim (docs/supply_demand/band_structure.md).
# Nothing here orders or gates on the level count.
MAX_LEVELS_BROKEN = 2


def ordinal(n: int) -> str:
    """1 -> '1st', 2 -> '2nd', 3 -> '3rd', 4 -> '4th', 11/12/13 -> 'th'.

    PURE, no I/O. ONE wording source for the tile labels, the badges and the
    ℹ️ Rules prose — chart_maps/board.py imports this rather than carrying its
    own "2nd"/"3rd" strings, which is how the old copy went stale."""
    n = int(n)
    rem = abs(n) % 100
    if 11 <= rem <= 13:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(abs(n) % 10, "th")
    return "%d%s" % (n, suf)


def _f(x) -> Optional[float]:
    """A finite float or None — a scan record can carry a string or a NaN."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _lo_hi(z):
    """(lo, hi) as finite floats, or (None, None) for a malformed band."""
    if not isinstance(z, dict):
        return None, None
    lo, hi = _f(z.get("lo")), _f(z.get("hi"))
    if lo is None or hi is None or hi < lo:
        return None, None
    return lo, hi


def arrival(dz: list, last) -> Optional[tuple]:
    """Which demand level the print is standing at, and what it crossed to get
    there. PURE — no I/O, no quality judgement.

    `dz` is the SERVED demand window, high→low: `rec["demand_zones"]`, which
    price_zones caps at MAX_ZONES_PER_SIDE bands NEAREST THE PRINT
    (price_zones.nearest_first(...)[:cap]). It is a SLIDING WINDOW, not the
    whole stack — a name that fell a long way may have older bands above the
    window that are not counted here. Stated on the board and in
    docs/supply_demand/deep_levels.md; reading the uncapped stack instead is
    Ajay's call, not made.

    Returns `(levels_broken, arrival_band, broken_bands)` or None:

      * the ARRIVAL band is the first band (high→low) the print is INSIDE;
        failing that, the first band whose top is under the print and within
        price_zones.NEAR_PCT of it — approaching from above.
      * a BROKEN level is a band above the arrival band with `last < lo`,
        strictly below only: a band that still straddles the print was not
        crossed, and must never be counted as a level.
      * `levels_broken == 0` (the first level still holds) → None;
        `levels_broken > MAX_LEVELS_BROKEN` → None (too deep for this screen).

    THE WALK NEVER SKIPS A BAND FOR QUALITY. Touches/strength are read by
    `read()` only after the band is chosen: a flimsy arrival band refuses the
    row, it never promotes the next level down. Promoting would make the
    reported `level` lie and would silently relax the band gate.
    """
    last = _f(last)
    if last is None or last <= 0:
        return None
    if not isinstance(dz, (list, tuple)) or len(dz) < 2:
        return None

    idx = None
    for i, z in enumerate(dz):                       # pass 1 — INSIDE wins
        lo, hi = _lo_hi(z)
        if lo is None:
            continue
        if lo <= last <= hi:
            idx = i
            break
    if idx is None:                                  # pass 2 — NEAR from above
        for i, z in enumerate(dz):
            lo, hi = _lo_hi(z)
            if lo is None:
                continue
            if hi < last:
                if (last - hi) / last * 100.0 <= NEAR_PCT:
                    idx = i
                break        # lower bands are farther — never keep searching
    if idx is None:
        return None                                  # in the air, or under everything

    arr = dz[idx]
    a_lo, a_hi = _lo_hi(arr)
    if a_lo is None:
        return None

    broken = []
    for j in range(idx):
        lo, hi = _lo_hi(dz[j])
        if lo is None:
            return None      # a malformed band overhead — fail closed, never guess
        if last < lo:        # strictly below: a straddling band was not crossed
            broken.append(dz[j])
    levels_broken = len(broken)
    if levels_broken == 0:
        return None                                  # first level still holding
    if levels_broken > MAX_LEVELS_BROKEN:
        return None                                  # deeper than this screen goes
    return levels_broken, arr, broken


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
      * price crossed 1..MAX_LEVELS_BROKEN of them — each one strictly above
        the print — which is what "penalized" looks like on a chart
      * price is INSIDE the next level down, or approaching it from above
        within price_zones.NEAR_PCT — not already through it
      * that ARRIVAL band is real by the scan's own bar: MIN_TOUCHES touches
        and MIN_ZONE_STRENGTH strength (imported, one scale)

    The geometry is `arrival()`; this function adds the state, the quality
    gate and the payload. `second_band` KEEPS ITS NAME — demand_order.deep_key,
    room_floor.row_entry_band, chart_maps/board.py and the FE all key on the
    literal — but its meaning widened from "demand_zones[1]" to "the band it
    arrived at" (2026-09-16). `top_band` is likewise the HIGHEST band it
    crossed, and `broken_bands` carries all of them so the tile can draw every
    level the price went through.

    "Entering from the top" is NOT enforced (review 2026-09-14, D5): a name
    whose prior close was UNDER the second band and is back inside it today
    still qualifies — it reached the band from below, a reclaim, not an
    arrival from above. The read says so instead (`reclaiming`, off the
    scan's `prev_close`; None/absent prev_close = unknown = False) and the
    board labels the band '2nd demand · reclaiming'. Requiring
    prev_close >= s_lo here would change who qualifies — Ajay's call, not
    made.

    Deliberately does NOT require trend_ok / is_reentry — failing the trend
    gate is the point of this screen. The board says so on every tile.
    """
    dz = rec.get("demand_zones") or []
    last = _f(rec.get("last_price"))
    got = arrival(dz, last)
    if got is None:
        return None
    levels_broken, second, broken = got
    s_lo, s_hi = _lo_hi(second)
    top = broken[0]                      # the HIGHEST level it crossed
    t_lo, t_hi = _lo_hi(top)

    if s_lo <= last <= s_hi:
        state = "in"
        dist_pct = 0.0
    else:                                # between the levels, coming down
        dist_pct = (last - s_hi) / last * 100.0     # ≤ NEAR_PCT by construction
        state = "near"

    # The band bar, on the ARRIVAL band only — unchanged thresholds, imported.
    if (second.get("touches") or 0) < MIN_TOUCHES:
        return None
    if (second.get("strength") or 0) < MIN_ZONE_STRENGTH:
        return None

    tb = rec.get("top_band_read") or {}
    # `top_band_read` is computed for demand_zones[0] ONLY (demand_reentry
    # decide_from_frame). When the highest level CROSSED is not that band —
    # dz[0] still straddles the print — carrying its break history would
    # attach another band's dates to this one.
    d0_lo, d0_hi = _lo_hi(dz[0]) if dz else (None, None)
    _same = (d0_lo is not None and abs(d0_lo - t_lo) < 1e-9
             and abs(d0_hi - t_hi) < 1e-9)
    pc = _f(rec.get("prev_close"))
    return {
        "state": state,                          # "in" | "near"
        "dist_pct": round(dist_pct, 2),
        # How many demand levels the print crossed, counted off the SURFACED
        # window (see arrival()), and which level it is standing at.
        "levels_broken": levels_broken,          # 1..MAX_LEVELS_BROKEN
        "level": levels_broken + 1,              # 2 or 3 — never ordered on
        # Yesterday closed UNDER the ARRIVAL band: today's position in it is
        # a reclaim from below, not an arrival from the top (D5, wording).
        "reclaiming": bool(pc is not None and pc > 0 and pc < s_lo),
        # Every band carries its touch count and its AGE fields (2026-09-14):
        # the tile sizes its window to `oldest_touch_bars`, and without it every
        # deep tile was 130 bars with the band's swings off-screen (56/100).
        # `top_band` = the HIGHEST level crossed (shape unchanged).
        "top_band": {"lo": top.get("lo"), "hi": top.get("hi"),
                     "touches": top.get("touches"),
                     "bars_since_test": top.get("bars_since_test"),
                     "oldest_touch_bars": top.get("oldest_touch_bars")},
        # `second_band` = the ARRIVAL band (shape unchanged, name unchanged —
        # four modules and the FE key on the literal).
        "second_band": {"lo": s_lo, "hi": s_hi,
                        "touches": second.get("touches"),
                        "strength": second.get("strength"),
                        "bars_since_test": second.get("bars_since_test"),
                        "oldest_touch_bars": second.get("oldest_touch_bars")},
        # EVERY crossed level, high→low, so the tile can draw them all and
        # room_floor can measure past all of them. len == levels_broken.
        "broken_bands": [{"lo": b.get("lo"), "hi": b.get("hi"),
                          "touches": b.get("touches"),
                          "strength": b.get("strength"),
                          "bars_since_test": b.get("bars_since_test"),
                          "oldest_touch_bars": b.get("oldest_touch_bars")}
                         for b in broken],
        # How far below the FIRST (highest) crossed level price sits.
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
        # `_same` (2026-09-16): only when the highest CROSSED level IS dz[0].
        "bars_since_top_break": tb.get("bars_since_first_break") if _same else None,
        "fell_from_pct": tb.get("fell_from_pct") if _same else None,
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
