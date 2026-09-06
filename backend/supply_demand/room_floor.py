"""Room to the first unbroken band overhead — the one read every demand board
row carries, and the floor that hides the ones without it.

Ajay 2026-09-05, TRU on the Back-in-Demand board (verbatim): "It already
gapped up very close to the resistance. Why is it still in in Demand page?
There is only 0.5% room". Measured: the scan's demand band 78.34-81.08
CONTAINED a supply band 80.12-82.10; the plan targeted 83.87 (the first band
above the ENTRY BAND TOP) so R:R read 1.47, while from the print (79.88) the
first band overhead was 80.12 — 0.3% of room, 0.09R.

Same day: "I need the same logic in Demand and deep demand zone. So that there
are stocks that have more room atleast >5%".

Two owner settings, both his, both IMPORTED from alert_gates so the phone and
the boards agree on one number:

  MIN_ROOM_DEFAULT  = alert_gates.ALERT_MIN_ROOM_PCT  (5.0, "atleast >5%")
  the overhead rule = alert_gates.first_overhead: supply bands with hi >= print
                      that are NOT broken (hi < prev_close = yesterday closed
                      above it = support), plus demand bands with lo > print
                      (broken support is resistance). Kind-agnostic.

``room_block(px, bands, entry_band, prev_close, basis)``
  {"room_pct", "target_lo", "target_hi", "target_kind", "state", "basis", "px"}
  state: CLEAR (nothing overhead) | ROOM (>= the house floor) | NEAR (under it)
  | IN_BAND (the print is inside the first overhead band). The row's own
  ENTRY band is excluded — from below, a name's own band is not its ceiling
  (the VRT case of 2026-08-13). None for a garbage print.

``meets_room_floor(room, min_room)``
  CLEAR passes, IN_BAND fails, room_pct >= min_room passes, an uncomputable
  room fails a real floor (the R:R floor's rule), min_room <= 0 is OFF.

``row_entry_band(row)`` / ``row_bands(row)``
  The band a scan row is trading (a deep row's SECOND band, else entry_zone)
  and every band it can measure room against (nearest_resistance + both zone
  lists + a deep row's broken top band), deduped.

Pure, no I/O. A LEAF: imports alert_gates only — chart_maps reads it while
tests stub demand_reentry, and demand_reentry re-exports it. Owner settings
for the Supply & Demand strategy, NOT a book method, no Minervini cites.
Decision support, not a buy signal, not advice.
"""
from __future__ import annotations

import math
from typing import Optional

from . import alert_gates as _gates

MIN_ROOM_DEFAULT = _gates.ALERT_MIN_ROOM_PCT   # Ajay 2026-09-05: "more room atleast >5%"


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and not math.isinf(v) else None


def _same_band(a: dict, b: Optional[dict]) -> bool:
    if not b:
        return False
    alo, ahi, blo, bhi = _f(a.get("lo")), _f(a.get("hi")), _f(b.get("lo")), _f(b.get("hi"))
    if alo is None or blo is None:
        return False
    # a legacy single-level band has no hi: compare what exists
    return round(alo, 2) == round(blo, 2) and (
        ahi is None or bhi is None or round(ahi, 2) == round(bhi, 2))


def plan_bands(cands, entry_band: Optional[dict] = None) -> list:
    """Normalise the bands a plan / room read may target: drop Nones and
    garbage, drop the entry band itself, dedupe, and give every band the
    shape alert_gates reads. A band without `kind` is a resistance candidate
    (trade_plan's legacy `{"lo": ...}` call) — supply; one without `hi` is a
    level, hi = lo. A band that fails alert_gates.is_proven_band (touches < 2
    or strength < 40) is dropped — the KLAC lesson (2026-09-06): a 1-touch
    lid is not a target. `strength` rides along (None when unknown)."""
    out, seen = [], set()
    for z in cands or []:
        if not isinstance(z, dict):
            continue
        lo = _f(z.get("lo"))
        if lo is None or lo <= 0:
            continue
        hi = _f(z.get("hi"))
        hi = lo if hi is None else hi
        if hi < lo:
            continue
        if entry_band and _same_band(z, entry_band):
            continue
        if not _gates.is_proven_band(z):
            continue                          # unproven lid = noise (KLAC 2026-09-06)
        kind = str(z.get("kind") or "supply").lower()
        key = (kind, round(lo, 2), round(hi, 2))
        if key in seen:
            continue
        seen.add(key)
        out.append({"kind": kind, "lo": lo, "hi": hi,
                    "touches": int(_f(z.get("touches")) or 0),
                    "strength": _f(z.get("strength"))})
    return out


def room_block(px, bands, entry_band: Optional[dict] = None, prev_close=None,
               basis: str = "scan", near_pct: float = MIN_ROOM_DEFAULT) -> Optional[dict]:
    """The room from `px` to the first unbroken band overhead. None for a
    garbage print. See the module docstring for the states."""
    p = _f(px)
    if p is None or p <= 0:
        return None
    first = _gates.first_overhead(plan_bands(bands, entry_band), p, prev_close)
    base = {"px": round(p, 2), "basis": basis if basis in ("live", "scan") else "scan",
            "prev_close": _f(prev_close)}
    if first is None:
        return {**base, "state": "CLEAR", "room_pct": None,
                "target_lo": None, "target_hi": None, "target_kind": None}
    lo, hi = float(first["lo"]), float(first["hi"])
    if lo <= p <= hi:
        state, raw = "IN_BAND", 0.0
    else:
        # The state split compares the RAW pct, exactly as alert_gates.room_gate
        # does (review 2026-09-05: 4.995% rounds to 5.0 on the card but fails
        # the phone; the boards must not list it as room-ok). room_pct stays
        # the 1-dp display number; room_pct_raw is the one to compare.
        raw = (lo - p) / p * 100.0
        state = "ROOM" if raw >= float(near_pct) else "NEAR"
    return {**base, "state": state, "room_pct": round(raw, 1), "room_pct_raw": raw,
            "target_lo": round(lo, 2), "target_hi": round(hi, 2),
            "target_kind": first.get("kind")}


def meets_room_floor(room: Optional[dict], min_room: Optional[float]) -> bool:
    """Does this row have the room the floor asks for? PURE. A floor <= 0 is
    OFF. CLEAR passes; IN_BAND fails; an uncomputable room fails a real floor
    — same rule as demand_reentry.meets_rr_floor, for the same reason: the
    one we could not measure must not be the one that shows up unfiltered."""
    floor = _f(min_room)
    if floor is None or floor <= 0:
        return True
    if not isinstance(room, dict):
        return False
    state = room.get("state")
    if state == "CLEAR":
        return True
    if state == "IN_BAND":
        return False
    # Compare RAW when the block carries it (room_pct is rounded for display);
    # a legacy block without it falls back to room_pct — but a server that
    # already said NEAR at the house floor has compared raw, and that wins.
    pct = _f(room.get("room_pct_raw"))
    if pct is None:
        pct = _f(room.get("room_pct"))
        if pct is not None and state == "NEAR" and floor == MIN_ROOM_DEFAULT:
            return False
    return pct is not None and pct >= floor


def room_stat(room: Optional[dict]) -> str:
    """'+12.4% -> 84.10' | 'open sky' | 'in band' | '—' — the one wording the
    board tiles and the cards print."""
    if not isinstance(room, dict):
        return "—"
    if room.get("state") == "CLEAR":
        return "open sky"
    if room.get("state") == "IN_BAND":
        return "in band"
    pct, tgt = _f(room.get("room_pct")), _f(room.get("target_lo"))
    if pct is None or tgt is None:
        return "—"
    return f"+{pct:.1f}% -> {tgt:.2f}"


def row_entry_band(row: dict) -> Optional[dict]:
    """The band this row is trading: a deep row's SECOND band (the one it is
    entering), else the scan's entry_zone."""
    row = row or {}
    second = ((row.get("deep_demand") or {}).get("second_band"))
    if isinstance(second, dict) and _f(second.get("lo")) is not None:
        return second
    ez = row.get("entry_zone")
    return ez if isinstance(ez, dict) else None


def row_bands(row: dict) -> list:
    """Every band a scan row can measure room against. `nearest_resistance`
    FIRST (price_zones computes it over every band while the zone lists keep
    the strongest four per side — the KLAC lesson in decide_from_frame), then
    both lists, then a deep row's broken top band as demand-kind (it IS in
    demand_zones for a live row; a cached row may carry only the deep dict).
    Deduped; the entry band is NOT removed here (room_block does that)."""
    row = row or {}
    deep = row.get("deep_demand") or {}
    top = deep.get("top_band")
    extra = ([{**top, "kind": "demand"}] if isinstance(top, dict) else [])
    return plan_bands([row.get("nearest_resistance")]
                      + list(row.get("supply_zones") or [])
                      + list(row.get("demand_zones") or [])
                      + extra)
