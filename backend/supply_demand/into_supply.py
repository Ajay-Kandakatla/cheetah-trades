"""Into Supply — the inverse of Back in Demand.

Ajay 2026-08-20:

> *"Now in inversely give me a tab that are in or about to be in supply zones
> please..."*

WHAT THIS IS FOR
----------------
Back in Demand finds names that pulled back into a floor. This finds names that
have rallied up into a CEILING: a tested band of overhead supply that price is
either sitting inside or is about to reach.

It is not a short list. Ajay trades long. The three questions it answers are:

  * about to buy this?      — you are buying directly under a lid
  * already hold it?        — this is where the advance is most likely to stall
  * watching for an entry?  — the clean entry is AFTER it clears, not here

The DHI read on 2026-08-19 is the case that motivated it: overhead supply
$151.87–$152.74 sitting **at price**, three times tested, while the nearest
support was 2% below and the only real floor was 4.4% below. Everything needed
to see that was already being computed and thrown away.

IT RIDES THE DEMAND PASS — IT DOES NOT SCAN
-------------------------------------------
`demand_reentry.scan()` already calls `analyze_symbol` on every name in the
universe (~1,600 price frames, ~3 minutes) and then keeps ONLY the rows where
`is_reentry` is true. Every discarded record already held `supply_zones`,
`nearest_resistance`, `nearest_support` and the structure read.

So this module never loads a price. It is a second PREDICATE over the same
record, evaluated in the same loop. That is not just cheaper — it means the two
boards physically cannot disagree about a name's zones, because they are reading
one computation from one moment.

ONE SCALE, NOT A SECOND ONE
---------------------------
Every threshold is imported from `demand_reentry`, never re-declared. A ceiling
that needs 2 touches and 40 strength to count is the same bar a floor has to
clear, and `test_the_two_boards_share_one_scale` fails if someone forks them.

NOT A BOOK METHOD. `price_zones` says so in its own header and nothing here
changes that. Decision support, not a signal, not advice.
"""
from __future__ import annotations

import logging
from typing import Optional

from . import price_zones
from .demand_reentry import (
    MIN_TOUCHES,
    MIN_ZONE_STRENGTH,
    REENTRY_LOOKBACK_BARS,
    MIN_RISE_ABOVE_PCT,
)

log = logging.getLogger("supply_demand.into_supply")

# ── thresholds — all borrowed, none invented ─────────────────────────────────
# How close below a band counts as "about to be in it". `price_zones.NEAR_PCT`
# is the same 3% its own verdict uses for INTO_SUPPLY, so the tab and the
# per-ticker read on /chart-maps?tab=support cannot disagree about the word.
NEAR_CEILING_PCT = price_zones.NEAR_PCT

# The mirror of MIN_RISE_ABOVE_PCT: a floor only counts as re-entered if price
# had risen 5% clear of it first. A ceiling only counts as approached if price
# had been 5% under it. Same number, opposite direction — a band price has
# merely hovered around is a level it is chopping in, not one it is arriving at.
MIN_RUN_UP_PCT = MIN_RISE_ABOVE_PCT

LOOKBACK_BARS = REENTRY_LOOKBACK_BARS

STATE_AT = "AT_CEILING"        # price is inside the supply band right now
STATE_NEAR = "NEAR_CEILING"    # price is under it, within NEAR_CEILING_PCT

DISCLAIMER = (
    "Into-supply is a configured, pragmatic price-structure read (NOT a book "
    "method) of names that have rallied into a tested band of overhead supply. "
    "It is a caution flag, not a short signal and not advice."
)


def _pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """(a - b) / b as a percent, or None. Guards the zero-price case that a
    halted or bad frame can produce."""
    try:
        a = float(a)
        b = float(b)
    except (TypeError, ValueError):
        return None
    if not b or b <= 0:
        return None
    return round((a - b) / b * 100.0, 2)


def supply_read(closes: list, band_lo: float, band_hi: float,
                last_price: float,
                lookback: int = LOOKBACK_BARS,
                min_run_up_pct: float = MIN_RUN_UP_PCT) -> dict:
    """Did price come UP into this band from below? PURE.

    Line-for-line the mirror of `demand_reentry.reentry_read`, including its
    two subtle rules, because the failures they were written for are symmetric:

    * **Only CLOSES count.** An intraday wick into overhead supply is how a
      ceiling gets tested; failing on a wick would reject the ordinary case.

    * **The broken-band guard, inverted.** `reentry_read` refuses a floor that
      price has CLOSED beneath — the market rejected that support. Here, a band
      price has CLOSED above is no longer a ceiling: that is a breakout, and the
      band has become support. Scoped to bars after the last close below the
      band, for the same reason: a close above from before the approach is old
      structure, already accounted for by price then falling 5% back under it.
    """
    out = {
        "into_supply": False, "state": None, "in_band": False,
        "near_band": False, "distance_pct": None, "to_clear_pct": None,
        "run_up_pct": None, "bars_since_below": None,
        "broke_above": False, "bars_since_break": None,
        "highest_close_pct_above": None,
    }
    try:
        band_lo = float(band_lo)
        band_hi = float(band_hi)
        last_price = float(last_price)
    except (TypeError, ValueError):
        return out
    if not closes or not band_lo or not band_hi or band_hi <= band_lo:
        return out
    if last_price <= 0:
        return out

    out["in_band"] = bool(band_lo <= last_price <= band_hi)
    # Distance to the band's LOW — the first price that touches it on the way
    # up, and 0 once inside. Measuring to the midpoint would understate how
    # close the lid already is.
    out["distance_pct"] = 0.0 if out["in_band"] else _pct(band_lo, last_price)
    # What it would take to be CLEAR of this supply, i.e. above the band top.
    # Meaningful in both states, unlike distance, which is 0 once inside.
    out["to_clear_pct"] = _pct(band_hi, last_price)

    if not out["in_band"]:
        d = out["distance_pct"]
        out["near_band"] = bool(d is not None and 0 < d <= NEAR_CEILING_PCT)
    if not (out["in_band"] or out["near_band"]):
        return out
    out["state"] = STATE_AT if out["in_band"] else STATE_NEAR

    window = closes[-int(lookback):] if lookback else list(closes)
    if not window:
        return out
    try:
        window = [float(c) for c in window]
    except (TypeError, ValueError):
        return out

    trough = min(window)
    # How far UNDER the band this approach started, mirroring `fell_from_pct`.
    run = (1.0 - trough / band_lo) * 100.0
    out["run_up_pct"] = round(run, 1)

    below_idx = [i for i, c in enumerate(window) if c < band_lo]
    if below_idx:
        out["bars_since_below"] = int(len(window) - 1 - below_idx[-1])

    start = (below_idx[-1] + 1) if below_idx else 0
    above = [(i, c) for i, c in enumerate(window[start:], start) if c > band_hi]
    if above:
        out["broke_above"] = True
        out["bars_since_break"] = int(len(window) - 1 - above[-1][0])
        best = max(c for _i, c in above)
        out["highest_close_pct_above"] = round((best / band_hi - 1.0) * 100.0, 2)

    out["into_supply"] = bool(run >= min_run_up_pct and below_idx
                              and not out["broke_above"])
    return out


def pick_ceiling(last_price: float, rec: dict) -> Optional[dict]:
    """The band acting as the lid: the one price is inside, else the nearest above.

    `nearest_resistance` leads because `price_zones` computes it over EVERY band
    while `supply_zones` is truncated to the strongest four — the same reason
    `trade_plan` reaches for it first, and the same bug (KLAC's real objective
    missing from the truncated list) it was written to avoid.

    Band ORIGIN is not the test. `price_zones` keeps supply/demand for colour;
    broken support trades as resistance, and a lid is a lid.
    """
    if not rec:
        return None
    try:
        last_price = float(last_price)
    except (TypeError, ValueError):
        return None

    pool = [rec.get("nearest_resistance")] + list(rec.get("supply_zones") or []) \
        + list(rec.get("demand_zones") or [])
    inside, above = [], []
    for z in pool:
        if not z:
            continue
        try:
            lo, hi = float(z["lo"]), float(z["hi"])
        except (TypeError, ValueError, KeyError):
            continue
        if lo <= last_price <= hi:
            inside.append((lo, z))
        elif lo > last_price:
            above.append((lo, z))
    if inside:
        # The lowest band containing price — the edge it has to clear first.
        return min(inside, key=lambda t: t[0])[1]
    if above:
        return min(above, key=lambda t: t[0])[1]
    return None


def _quality_ok(band: Optional[dict]) -> bool:
    """Same bar a demand band has to clear. Borrowed, never re-declared."""
    if not band:
        return False
    return bool((band.get("touches") or 0) >= MIN_TOUCHES
                and (band.get("strength") or 0) >= MIN_ZONE_STRENGTH)


def read_from_frame(df, rec: dict) -> Optional[dict]:
    """The supply-side read for one already-decided record. PURE.

    Takes the frame only for its closes — every zone, band and structure number
    is read off `rec`, which `demand_reentry.decide_from_frame` has just
    computed from that same frame. Nothing is recomputed, so the two boards
    cannot drift.

    Returns None when there is no ceiling in range, which is the ordinary case
    for a name in clear air.
    """
    if df is None or rec is None:
        return None
    try:
        last_price = float(rec.get("last_price"))
    except (TypeError, ValueError):
        return None

    ceiling = pick_ceiling(last_price, rec)
    if not ceiling:
        return None

    try:
        closes = [float(c) for c in df["close"].tolist()]
    except Exception:                                        # pragma: no cover
        return None

    read = supply_read(closes, ceiling.get("lo"), ceiling.get("hi"), last_price)
    if not read.get("state"):
        return None                                  # not at or near a ceiling

    quality_ok = _quality_ok(ceiling)
    support = rec.get("nearest_support")
    down = None
    if support:
        try:
            down = _pct(last_price, float(support["hi"]))
        except (TypeError, ValueError, KeyError):
            down = None

    # Room UP to the lid vs room DOWN to the next floor.
    #
    # NOT a trade reward:risk — there is no stop here and this module never
    # proposes one. It is the asymmetry of the two nearest structural levels,
    # which is the thing that was invisible on DHI: 0.01% of room above and
    # 2.05% below is a 0.005 ratio, and no amount of a good-looking base
    # changes that arithmetic.
    up = read.get("distance_pct")
    room_ratio = None
    if (up is not None and down is not None and down > 0):
        room_ratio = round(up / down, 2)

    return {
        **read,
        "ceiling": ceiling,
        "ceiling_touches": ceiling.get("touches"),
        "ceiling_strength": ceiling.get("strength"),
        "ceiling_bars_since_test": ceiling.get("bars_since_test"),
        "quality_ok": quality_ok,
        "support_below": support,
        "downside_pct": down,
        "room_ratio": room_ratio,
        # The published verdict. Quality is folded in HERE and not inside
        # `supply_read`, so the raw geometry stays reusable and testable on its
        # own — the same split `is_reentry` uses.
        "is_into_supply": bool(read.get("into_supply") and quality_ok),
    }


def qualifies(rec: dict) -> bool:
    """Does this record belong on the Into Supply board? PURE.

    Reads the attached `supply` block only — the scan attaches it once and this
    never recomputes, so a row on the board always carries the numbers that put
    it there.
    """
    s = (rec or {}).get("supply") or {}
    return bool(s.get("is_into_supply"))


def _n(v, fallback: float) -> float:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) \
        else fallback


def sort_key(rec: dict):
    """Most urgent first. A lexicographic TUPLE, deliberately not a weighted score.

    THE FIRST VERSION SORTED THE BOARD ALPHABETICALLY AND I ONLY SAW IT ON REAL
    DATA. It led on `distance_pct` then `room_ratio` — but both are 0.0 for
    *every* name already inside its ceiling, which on the S&P 500 was all of the
    top 24. Both keys degenerated, the tie-break fell through to the symbol, and
    the board opened ABBV / ACN / AJG / AON. An alphabetical caution list is
    worse than none: it looks ranked.

    So the order is:

      1. **inside the band before approaching it** — a lid you are already in
         matters more today than one 3% away
      2. **most air beneath first** — this is the one that separates the rows
         the first version could not. If it fails here, how far to the next
         floor? BKNG at 6.1% is a worse place to buy than BKR at 0.4%
      3. **hardest lid first** — a 6x-tested band is more of a ceiling than a 2x
      4. symbol, only so the order is stable

    No invented weights: `supply_tiles` turns this ranking into `_score` by
    POSITION, so there is exactly one definition of the ordering.
    """
    s = (rec or {}).get("supply") or {}
    return (
        0 if s.get("state") == STATE_AT else 1,
        _n(s.get("distance_pct"), 9e9),          # only separates the NEAR rows
        -_n(s.get("downside_pct"), -9e9),        # most air beneath first
        -_n(s.get("ceiling_touches"), 0.0),      # hardest lid first
        rec.get("symbol") or "",
    )
