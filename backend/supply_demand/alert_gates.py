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

``is_proven_band(band) -> bool``  (Ajay 2026-09-06, the KLAC lesson)
  A band counts as OVERHEAD only when it meets the board's own bar for a real
  band: touches >= LID_MIN_TOUCHES (2) AND strength >= LID_MIN_STRENGTH (40),
  the same numbers demand_reentry.MIN_TOUCHES / MIN_ZONE_STRENGTH use to list
  a demand band (pinned equal in tests/test_supply_demand_contracts.py). KLAC
  2026-09-02..03: price 169.50 sat inside the 164.60-169.81 demand band with a
  1-touch / strength-32 supply band 166.37-172.30 on top of it; the room read
  measured to THAT lid = IN_BAND = no push, no paper buy for two days, then the
  +7% gap. Unproven lids are noise, not ceilings: skip them and measure to the
  next PROVEN band (191.11 -> 12.7% room). Unknown touches keep the lid
  (conservative); unknown strength is judged on touches alone. Every overhead
  reader applies it: overhead_bands here, bounce_room.overhead_bands,
  portfolio.supply_watch.overhead_bands, trading.zone_edge_entry.room_ok and
  room_floor.plan_bands (the board plan's target). Boards still LIST every band.

``plan_txt(print, band, room) -> str``  (Ajay 2026-09-06, "ok please all 3")
  The plan inside the push text: "buy $lo-hi · stop $x (0.5% under the floor,
  y% risk) · target $t (nR)". The stop is the SAME one the paper lane places
  (STOP_BUFFER_PCT under the band floor = trading.zone_edge_entry.STOP_BUFFER_PCT,
  pinned equal in tests/test_trading_contracts.py).

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
# A lid must be PROVEN to count as overhead (Ajay 2026-09-06, KLAC): the
# board's own bar for a real band — demand_reentry.MIN_TOUCHES /
# MIN_ZONE_STRENGTH. Pinned equal in tests/test_supply_demand_contracts.py.
LID_MIN_TOUCHES = 2
LID_MIN_STRENGTH = 40.0
# The plan text's stop: this far under the band floor — the stop the paper
# lane places (trading.zone_edge_entry.STOP_BUFFER_PCT, pinned equal).
STOP_BUFFER_PCT = 0.5


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and not math.isinf(v) else None      # NaN / inf guard


def _kind(band: dict) -> str:
    return str((band or {}).get("kind") or "demand").lower()


def is_proven_band(band) -> bool:
    """True when the band meets the board's bar for real structure: touches
    >= LID_MIN_TOUCHES and strength >= LID_MIN_STRENGTH. Touches unknown
    (missing / non-positive) keeps the band — a lid nobody counted is not
    dismissed; strength unknown is judged on touches alone."""
    if not isinstance(band, dict):
        return False
    touches = _f(band.get("touches"))
    if touches is None or touches <= 0:
        return True
    if touches < LID_MIN_TOUCHES:
        return False
    strength = _f(band.get("strength"))
    if strength is None:
        return True
    return bool(strength >= LID_MIN_STRENGTH)


def _valid_band(band) -> bool:
    if not isinstance(band, dict):
        return False
    lo, hi = _f(band.get("lo")), _f(band.get("hi"))
    return lo is not None and hi is not None and 0 < lo <= hi


def _slim(band: dict) -> dict:
    return {"kind": _kind(band), "lo": float(band["lo"]), "hi": float(band["hi"]),
            "touches": int(_f(band.get("touches")) or 0)}


def overhead_bands(bands, print_px, prev_close=None) -> list:
    """Everything price meets going UP: unbroken PROVEN supply bands with
    hi >= print, plus proven demand bands strictly above the print. A demand
    band that CONTAINS the print is support, never overhead; a band that fails
    is_proven_band is skipped (KLAC 2026-09-06). Same shape as
    bounce_room.overhead_bands with ONE addition — the broken-supply rule when
    prev_close is known."""
    px = _f(print_px)
    if px is None or px <= 0:
        return []
    pc = _f(prev_close)
    if pc is not None and pc <= 0:
        pc = None
    out = []
    for b in bands or []:
        if not _valid_band(b) or not is_proven_band(b):
            continue                                      # unproven lid = noise, not a ceiling
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


def plan_txt(print_px, band, room: Optional[dict],
             stop_buffer_pct: float = STOP_BUFFER_PCT) -> str:
    """The plan inside the push (Ajay 2026-09-06): 'buy $164.6-169.81 · stop
    $163.78 (0.5% under the floor, 3.4% risk) · target $191.11 (3.6R)'. Risk is
    measured from the PRINT (what a fill here risks), the stop from the band
    floor (what the paper lane places). No overhead band: 'target: clear
    runway'. Garbage in -> '' (the body simply omits the plan)."""
    px = _f(print_px)
    if px is None or px <= 0 or not _valid_band(band):
        return ""
    lo, hi = float(band["lo"]), float(band["hi"])
    stop = lo * (1.0 - stop_buffer_pct / 100.0)
    risk_pct = (px - stop) / px * 100.0
    out = (f"buy ${lo:g}-{hi:g} · stop ${stop:.2f} ({stop_buffer_pct:g}% under the floor, "
           f"{risk_pct:.1f}% risk)")
    target = _f((room or {}).get("target")) if room else None
    if target is None:
        return out + " · target: clear runway"
    rr = (target - px) / (px - stop) if px > stop else None
    rr_txt = f" ({rr:.1f}R)" if rr is not None and rr > 0 else ""
    return out + f" · target ${target:g}{rr_txt}"
