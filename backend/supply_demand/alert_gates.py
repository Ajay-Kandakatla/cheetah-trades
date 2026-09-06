"""One phone gate for every Supply & Demand push — zone_edge (🚀 + 🧲),
zone_bounce_alerts (🪃) and demand_alerts (🧲). Boards keep listing everything;
only the PHONE tightens. The modules already draw that line ("pushes only; the
board lists every band").

Ajay 2026-09-05 (verbatim, mid-fix): "When alert I need the same logic. Need
only alerts on stocks that have atleast 5% to Supply and also <1% bounce from
demand zone".

Two owner settings, both straight from that sentence:

  ALERT_MIN_ROOM_PCT          5.0   "atleast 5% to Supply"
  ALERT_MAX_ABOVE_DEMAND_PCT  1.0   "<1% bounce from demand zone"

``room_gate(print, bands, prev_close) -> (ok, room)``
  The band price meets FIRST going up, the SAME rule as bounce_room.first_overhead
  and zone_bounce_alerts.room_for (fixed 2026-09-05): supply bands with
  ``hi >= print`` that are NOT already broken — a supply band with ``hi <
  prev_close`` (yesterday CLOSED above it) is support, the house rule zone_edge's
  Side B and zone_bounce_alerts.is_eligible use; unknown prev close = every supply
  band counts — plus demand bands with ``lo > print`` (broken support =
  resistance). The band CONTAINING the print wins (lowest lo when nested), else
  the lowest lo above it. target = lo when lo > print, else hi (the print is
  inside the band). CLEAR (nothing overhead) passes with room None; IN_BAND fails;
  room_pct < ALERT_MIN_ROOM_PCT fails. A garbage print fails closed.

``demand_proximity_gate(print, band) -> bool``
  ``band.lo <= print <= band.hi * (1 + ALERT_MAX_ABOVE_DEMAND_PCT/100)`` — at the
  level or within 1% above it. Under the floor = fell through = no push ("I am
  late by the time it reaches me" is the complaint; a bounce that already ran 4%
  above the top lists, it does not ring). Garbage fails closed.

Pure, no I/O, and NO imports from the sibling modules: bounce_room imports both
zone_edge and zone_bounce_alerts, so this module must stay a leaf. "At least 5% to
supply" applies to every phone kind, including ``supply_break_alert`` (measured to
the NEXT band above the one being broken).

Configured house heuristic, S/D scope, NOT a book method, no Minervini cites.
Decision support, not a buy signal, not advice.
"""
from __future__ import annotations

import math
from typing import Optional

ALERT_MIN_ROOM_PCT = 5.0            # Ajay 2026-09-05: "atleast 5% to Supply"
ALERT_MAX_ABOVE_DEMAND_PCT = 1.0    # Ajay 2026-09-05: "<1% bounce from demand zone"


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and not math.isinf(v) else None      # NaN / inf guard


def _kind(band: dict) -> str:
    return str((band or {}).get("kind") or "demand").lower()


def _valid_band(band) -> bool:
    if not isinstance(band, dict):
        return False
    lo, hi = _f(band.get("lo")), _f(band.get("hi"))
    return lo is not None and hi is not None and 0 < lo <= hi


def _slim(band: dict) -> dict:
    return {"kind": _kind(band), "lo": float(band["lo"]), "hi": float(band["hi"]),
            "touches": int(_f(band.get("touches")) or 0)}


def overhead_bands(bands, print_px, prev_close=None) -> list:
    """Everything price meets going UP: unbroken supply bands with hi >= print,
    plus demand bands strictly above the print. A demand band that CONTAINS the
    print is support, never overhead. Same shape as bounce_room.overhead_bands
    with ONE addition — the broken-supply rule when prev_close is known."""
    px = _f(print_px)
    if px is None or px <= 0:
        return []
    pc = _f(prev_close)
    if pc is not None and pc <= 0:
        pc = None
    out = []
    for b in bands or []:
        if not _valid_band(b):
            continue
        lo, hi = float(b["lo"]), float(b["hi"])
        if _kind(b) == "supply":
            if hi < px:
                continue                                  # below the print
            if pc is not None and hi < pc:
                continue                                  # yesterday closed above it: broken = support
            out.append(_slim(b))
        elif lo > px:
            out.append(_slim(b))                          # demand above the print: broken support
    return out


def first_overhead(bands, print_px, prev_close=None) -> Optional[dict]:
    """The band price meets FIRST going up: the one containing the print
    (lowest lo when nested), else the lowest lo above it. None = clear."""
    px = _f(print_px)
    over = overhead_bands(bands, px, prev_close)
    if not over or px is None:
        return None
    inside = [b for b in over if b["lo"] <= px <= b["hi"]]
    if inside:
        return min(inside, key=lambda b: b["lo"])
    return min(over, key=lambda b: b["lo"])


def room_read(print_px, bands, prev_close=None) -> Optional[dict]:
    """{"state": "IN_BAND"|"ROOM", "room_pct", "target", "touches", "band"} for the
    first overhead band; None = CLEAR (or an unusable print — callers check the
    print first when the difference matters)."""
    px = _f(print_px)
    if px is None or px <= 0:
        return None
    first = first_overhead(bands, px, prev_close)
    if first is None:
        return None
    in_band = first["lo"] <= px <= first["hi"]
    target = first["hi"] if in_band else first["lo"]
    room_pct = (target - px) / px * 100.0
    # room_pct is the 1-dp DISPLAY number; room_pct_raw is what the gate
    # compares and what callers format in a refusal (review 2026-09-05: a
    # 4.995% room printed "5.0% < 5%" — the rounded value must never be the
    # one compared or quoted).
    return {"state": "IN_BAND" if in_band else "ROOM", "room_pct": round(room_pct, 1),
            "room_pct_raw": room_pct,
            "target": round(target, 2), "touches": first.get("touches"), "band": dict(first)}


def room_gate(print_px, bands, prev_close=None,
              min_room_pct: float = ALERT_MIN_ROOM_PCT) -> tuple:
    """(ok, room). CLEAR passes with room None; IN_BAND fails; room under
    `min_room_pct` fails. A garbage print fails closed: (False, None)."""
    px = _f(print_px)
    if px is None or px <= 0:
        return False, None
    room = room_read(px, bands, prev_close)
    if room is None:
        return True, None
    if room["state"] == "IN_BAND":
        return False, room
    # Compare the UNROUNDED room. Until 2026-09-05 this rebuilt the pct from
    # room["target"], which is rounded to cents — a band floor at 104.995 read
    # 105.00 and a 4.995% room passed the 5% line (found by the boundary test).
    raw = room.get("room_pct_raw")
    if raw is None:
        raw = (room["target"] - px) / px * 100.0
    return bool(raw >= min_room_pct), room


def demand_proximity_gate(print_px, band,
                          max_above_pct: float = ALERT_MAX_ABOVE_DEMAND_PCT) -> bool:
    """At the demand level or within `max_above_pct` above its top. Under the
    floor (fell through) and garbage both fail."""
    px = _f(print_px)
    if px is None or px <= 0 or not _valid_band(band):
        return False
    lo, hi = float(band["lo"]), float(band["hi"])
    return bool(lo <= px <= hi * (1.0 + max_above_pct / 100.0))


def room_txt(room: Optional[dict]) -> str:
    """'room +12% -> $112 (3.6R)' / 'room: clear runway' — the one wording every
    push body uses (moved here from zone_bounce_alerts._room_txt)."""
    if not room:
        return "room: clear runway"
    rr = f" ({room['rr']:g}R)" if room.get("rr") is not None else ""
    return f"room +{room['room_pct']:g}% -> ${room['target']:g}{rr}"
