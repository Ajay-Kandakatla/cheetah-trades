"""Demand-board ordering — closest to the level first, money flow breaks ties.

Ajay 2026-09-03: "make sure in our other demand and deep demand keep the
closest one to demand zones on the top. Of course CMF inflow too considered."

One definition of "closest first" for every demand list that is NOT the
reached Back-in-Demand board: Approaching (zone and order block), In the
order block, and Deep Demand (in + near). The reached board keeps its
measured R:R-first order (docs/supply_demand/rr_floor.md) — every row there is
already inside its band, so proximity is a constant and cannot rank anything.

Why this module exists (measured on the 2026-09-03 17:22 UTC scan):

* deep_demand.sort_key was CMF-FIRST, so NOG — 2.53% ABOVE its second band
  with CMF +0.36 — ranked over 52 names already inside theirs.
* approaching_rows sorted by raw distance with an `or 99.0` guard and no
  flow tie-break, so LECO at 0.01% sat above ITRI at 0.07% on a difference
  that is one tick of noise, while the money-flow read was ignored.
* in_ob_rows sorted by block age alone: the top 41 of 82 all had bars_ago
  = 2 and their order was whatever the universe list happened to be.

The key, in order:

  1. state       0 inside the band · 1 above it · 2 below it · 3 unknown
  2. bucket      floor(prox_pct / PROXIMITY_BUCKET_PCT) — distance in 0.5%
                 steps. 0.03% vs 0.08% out is one tick of noise on a $96
                 stock; CMF −0.04 vs −0.28 is not. Inside a bucket the flow
                 read decides, not the third decimal of the distance.
  3. flow rank   inflow 0 < neutral 1 < distribution 2 < missing 3
  4. −CMF-20     stronger inflow (or milder selling) first; None → +inf so a
                 missing reading sorts LAST within its state, never first
  5. prox_pct    the exact distance, for a stable order inside a tie
  6. *tail       the caller's own tie-breaks (drift, band strength, symbol)

prox_pct = (px − hi) / px × 100 above the band, 0 inside,
           (lo − px) / px × 100 below it. Below-band sorts AFTER above-band
           because "fell through the level" is a different event from
           "arriving at it" and must not sit at the top of an arrival list.

Worked example (live rows, 2026-09-03):

  Deep Demand   COTY  inside the band, CMF +0.248          → state 0
                APPF  0.81% above,     CMF +0.282          → state 1, bucket 1
                NOG   2.53% above,     CMF +0.364          → state 1, bucket 5
                ⇒ COTY, APPF, NOG (the old key gave NOG, APPF, COTY)

  Approaching, all in bucket 0 (< 0.5% above the band):
                MP    0.26%  inflow        CMF +0.159
                HIMS  0.18%  neutral       CMF −0.031
                ITRI  0.03%  neutral       CMF −0.044
                VLTO  0.11%  distribution  CMF −0.144
                EXR   0.08%  distribution  CMF −0.275
                ⇒ MP, HIMS, ITRI, VLTO, EXR (raw distance gave ITRI, EXR,
                  VLTO, HIMS, MP — the accumulated name LAST)

Pure: no imports from the package, no I/O, no scan state. Both the scan
(demand_reentry.py, on the scan's last_price) and Chart Maps (board.py, on
the LIVE print, since the scan cache is hours old) call the same function so
the two surfaces can never disagree about who is closest.

Decision-support only. Configured house ordering, not a book method.
"""
from __future__ import annotations

import math
from typing import Optional

# Distance step that counts as "the same distance". Ajay's ask is proximity
# first with CMF "considered"; a raw-distance sort never lets CMF speak
# because two floats are almost never equal. 0.5% (2026-09-03): on a $96
# stock that is ~$0.48 — inside one session's noise — while the CMF spread it
# yields to (e.g. −0.04 vs −0.28) is a real difference in who is buying.
PROXIMITY_BUCKET_PCT = 0.5

# Money-flow rank. Missing is 3, not neutral's 1: a row with no read must
# never outrank a row with a real one (into_supply's "missing data must not
# masquerade as the most urgent" rule, applied to flow).
FLOW_RANK = {"inflow": 0, "neutral": 1, "distribution": 2}
FLOW_RANK_MISSING = 3

STATE_IN, STATE_ABOVE, STATE_BELOW, STATE_UNKNOWN = 0, 1, 2, 3


def _num(v) -> Optional[float]:
    """float or None — None, NaN, inf and junk all read as None."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def geometry(px, band_lo, band_hi) -> tuple[int, Optional[float]]:
    """(state, prox_pct) of `px` against the band. prox_pct is None only when
    the state is unknown (missing price or band)."""
    p, lo, hi = _num(px), _num(band_lo), _num(band_hi)
    if p is None or p <= 0 or lo is None or hi is None:
        return STATE_UNKNOWN, None
    if lo > hi:                       # defensive — a reversed band is still a band
        lo, hi = hi, lo
    if lo <= p <= hi:
        return STATE_IN, 0.0
    if p > hi:
        return STATE_ABOVE, (p - hi) / p * 100.0
    return STATE_BELOW, (lo - p) / p * 100.0


def flow_rank(inflow: Optional[dict]) -> int:
    if not inflow:
        return FLOW_RANK_MISSING
    return FLOW_RANK.get(inflow.get("state"), FLOW_RANK_MISSING)


def cmf_rank(inflow: Optional[dict]) -> float:
    """−CMF-20, so a stronger inflow (or milder selling) sorts first. A
    missing CMF is +inf: LAST within its flow state, never first."""
    cmf = _num((inflow or {}).get("cmf_20"))
    return math.inf if cmf is None else -cmf


def _safe_tail(tail) -> tuple:
    """Caller tie-breaks with None pushed last instead of raising TypeError."""
    return tuple((1, 0.0) if t is None else (0, t) for t in (tail or ()))


def proximity_key_from(state: int, prox_pct: Optional[float],
                       inflow: Optional[dict], tail=()) -> tuple:
    """The key from an already-measured geometry (the scan's own read, when
    the price it was read against is not on the row)."""
    p = _num(prox_pct)
    if state == STATE_UNKNOWN or p is None:
        state, p = STATE_UNKNOWN, math.inf
    bucket = math.floor(p / PROXIMITY_BUCKET_PCT) if math.isfinite(p) else math.inf
    return (state, bucket, flow_rank(inflow), cmf_rank(inflow), p, *_safe_tail(tail))


def proximity_key(px, band_lo, band_hi, inflow: Optional[dict], tail=()) -> tuple:
    """Sort key: closest to the band first, money flow inside a 0.5% bucket.
    See the module docstring for the full order and the worked example.
    None-safe: a missing price or band ranks LAST (state 3), never first."""
    state, prox = geometry(px, band_lo, band_hi)
    return proximity_key_from(state, prox, inflow, tail)


def inflow_of(row: Optional[dict]) -> Optional[dict]:
    """The flow read wherever a row carries it: top-level `inflow` (Back in
    Demand, Approaching, order-block rows), else nested `deep_demand.inflow`
    (deep rows before 2026-09-03 only carried it there)."""
    if not row:
        return None
    return row.get("inflow") or (row.get("deep_demand") or {}).get("inflow") or None


def _px(row: dict, px=None):
    return px if px is not None else row.get("last_price")


# ── per-board keys — ONE definition each, shared by the scan and Chart Maps ──
def approaching_key(row: dict, px=None) -> tuple:
    """Approaching a demand band: proximity_key over `approaching.band`,
    ties on drift (harder fall first — the 2026-08-31 tie-break, kept) then
    symbol. `px` overrides the scan price (Chart Maps passes the live print)."""
    a = row.get("approaching") or {}
    band = a.get("band") or row.get("entry_zone") or {}
    return proximity_key(_px(row, px), band.get("lo"), band.get("hi"),
                         inflow_of(row),
                         tail=(a.get("drift_pct"), row.get("symbol") or ""))


def approaching_ob_key(row: dict, px=None) -> tuple:
    """Approaching a fresh order block: same key over `approaching_ob.block`."""
    a = row.get("approaching_ob") or {}
    blk = a.get("block") or {}
    return proximity_key(_px(row, px), blk.get("lo"), blk.get("hi"),
                         inflow_of(row),
                         tail=(a.get("drift_pct"), row.get("symbol") or ""))


def in_ob_key(row: dict, px=None) -> tuple:
    """Inside a fresh order block: the block's AGE leads (youngest first —
    Ajay 2026-08-31, the freshest footprint's first test is the informative
    one), then the proximity key over the block so that among same-age
    blocks (41 of 82 live rows were 2 bars old) the flow read decides
    instead of universe order. Missing age sorts last, never first."""
    blk = (row.get("in_ob") or {}).get("block") or {}
    age = _num(blk.get("bars_ago"))
    return (math.inf if age is None else age,
            *proximity_key(_px(row, px), blk.get("lo"), blk.get("hi"),
                           inflow_of(row), tail=(row.get("symbol") or "",)))


def deep_key(row: dict, px=None) -> tuple:
    """Deep Demand: proximity_key over the SECOND band, ties on band strength
    (stronger first) then symbol. Uses the row's price (or the live `px`);
    when a row carries only the read (no last_price) the read's own
    state/dist_pct — the same formula — stands in, so ranking never crashes
    or silently degrades to "unknown"."""
    d = row.get("deep_demand") or {}
    sb = d.get("second_band") or {}
    tail = (-(_num(sb.get("strength")) or 0.0), row.get("symbol") or "")
    p = _px(row, px)
    if p is None:
        state = {"in": STATE_IN, "near": STATE_ABOVE}.get(d.get("state"), STATE_UNKNOWN)
        return proximity_key_from(state, d.get("dist_pct"), inflow_of(row), tail)
    return proximity_key(p, sb.get("lo"), sb.get("hi"), inflow_of(row), tail)
