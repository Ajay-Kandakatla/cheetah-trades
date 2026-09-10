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

``is_proven_band(band) -> bool``  (Ajay 2026-09-06, the KLAC lesson; 2026-09-08 touches only)
  A band counts as OVERHEAD only when it is tested: touches >= LID_MIN_TOUCHES
  (2). The strength half of the bar (>= 40, the board's MIN_ZONE_STRENGTH) was
  dropped on 2026-09-08 — FSLR: 2-touch shelves at 233 and 241 of strength 27 /
  35 were skipped and the push read "room +17.3% -> $250.99" while the chart
  drew them; Ajay: "ok push please" to "room bar = touches only". KLAC
  2026-09-02..03: price 169.50 sat inside the 164.60-169.81 demand band with a
  1-touch / strength-32 supply band 166.37-172.30 on top of it; the room read
  measured to THAT lid = IN_BAND = no push, no paper buy for two days, then the
  +7% gap. Unproven lids are noise, not ceilings: skip them and measure to the
  next PROVEN band (191.11 -> 12.7% room). Unknown touches keep the lid
  (conservative). Every overhead reader applies it: overhead_bands here,
  bounce_room.overhead_bands, portfolio.supply_watch.overhead_bands,
  trading.zone_edge_entry.room_ok and room_floor.plan_bands (the board plan's
  target). Boards still LIST every band.

``gap_day(print, prev_close) -> bool``  (Ajay 2026-09-08, DYN −29%)
  A print GAP_DOWN_PCT (8%) or more under yesterday's close resets the
  structure for the day: every shelf between the print and that close is
  trapped supply, whatever the closed bars called it. DYN 2026-09-08 pushed
  "above demand" four times on the way back up from 17.2 because the house
  rule "a supply band yesterday CLOSED above is broken = support" was judged
  against a 24.28 close the gap had just invalidated, and the room read ran
  to 23.96 over the same shelves. On a gap day: supply bands are NEVER
  support (zone_edge.read_near_demand, zone_bounce_alerts.is_eligible) and
  the broken-supply skip is OFF in every overhead reader (overhead_bands
  here, bounce_room, portfolio.supply_watch) — the shelves count for the 5%
  room gate. Same-day replay: DYN pushes once, at 09:09 (16.56–17.02).

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
# A lid must be PROVEN to count as overhead (Ajay 2026-09-06, KLAC): tested
# at least twice — demand_reentry.MIN_TOUCHES, pinned equal in
# tests/test_supply_demand_contracts.py. Strength no longer counts
# (Ajay 2026-09-08, FSLR: "room bar = touches only").
LID_MIN_TOUCHES = 2
# A gap DOWN of this much from yesterday's close resets the structure for the
# day (Ajay 2026-09-08, DYN): shelves between the print and that close are
# trapped supply — never support, always overhead.
GAP_DOWN_PCT = 8.0
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
    """True when the band is tested: touches >= LID_MIN_TOUCHES. Touches
    unknown (missing / non-positive) keeps the band — a lid nobody counted is
    not dismissed. Strength is not consulted (Ajay 2026-09-08)."""
    if not isinstance(band, dict):
        return False
    touches = _f(band.get("touches"))
    if touches is None or touches <= 0:
        return True
    return bool(touches >= LID_MIN_TOUCHES)


def gap_day(print_px, prev_close, gap_pct: float = GAP_DOWN_PCT) -> bool:
    """True when the print sits `gap_pct` or more UNDER yesterday's close —
    the day the closed-bar roles no longer apply (DYN 2026-09-08). Unknown
    or garbage inputs: False (the ordinary rules stand)."""
    px, pc = _f(print_px), _f(prev_close)
    if px is None or pc is None or px <= 0 or pc <= 0:
        return False
    return px <= pc * (1.0 - float(gap_pct) / 100.0)


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
    gap = gap_day(px, pc)                                 # DYN 2026-09-08: the gap resets the roles
    out = []
    for b in bands or []:
        if not _valid_band(b) or not is_proven_band(b):
            continue                                      # unproven lid = noise, not a ceiling
        lo, hi = float(b["lo"]), float(b["hi"])
        if _kind(b) == "supply":
            if hi < px:
                continue                                  # below the print
            if pc is not None and hi < pc and not gap:
                continue                                  # yesterday closed above it: broken = support
            out.append(_slim(b))
        elif lo > px:
            out.append(_slim(b))                          # demand above the print: broken support
    return out


# Mood as CONTEXT on a demand alert (Ajay 2026-09-08: "I do want signals to
# sell based on Supply demand but not on mood. But do include mood in the
# overall criteria of the stocks for alerts becuz mood determins if stock grows
# faster from demand or not"). Mood NEVER fires or suppresses an alert — the
# S/D gates alone decide that, and the mood watcher was deleted the same day
# for a measured 8-hits/25-misses record as a signal. Here it only:
#   * rides in the push body and on the board tile ("mood +18 bullish"), and
#   * breaks the tie for the MAX_SINGLES_PER_PASS names that ring individually
#     (constructive first) — nothing is dropped, the rest ride the digest.
# Whether it actually separates the fast bounces is being measured; a gate
# needs those numbers and Ajay's sign-off (Rule #10).
MOOD_CONSTRUCTIVE = 10.0     # score >= this = "leaning bullish" or better
MOOD_HEAVY = -25.0           # score <= this = bearish, the tile says so


def mood_read(symbol, frame=None) -> Optional[dict]:
    """{"score", "label", "constructive"} on the name's CLOSED daily bars, or
    None when it cannot be computed. Best-effort: a mood failure never blocks
    an alert."""
    try:
        from . import mood as mood_mod
        df = frame
        if df is None:
            from sepa import prices
            df = prices.load_prices(symbol, period="1y")
        if df is None or len(df) < 6:
            return None
        m = mood_mod.mood(df)
        score = _f(m.get("score"))
        if score is None or m.get("label") == "unavailable":
            return None
        return {"score": round(score, 1), "label": m.get("label"),
                "constructive": score >= MOOD_CONSTRUCTIVE,
                "heavy": score <= MOOD_HEAVY}
    except Exception:                                # noqa: BLE001
        return None


def mood_txt(mood: Optional[dict]) -> str:
    """"mood +18 bullish" — the body/tile fragment, "" when unknown."""
    if not isinstance(mood, dict) or mood.get("score") is None:
        return ""
    return "mood %+g %s" % (mood["score"], mood.get("label") or "")


def mood_rank(mood: Optional[dict]) -> int:
    """Sort key fragment: constructive names ring first (0), unknown next (1),
    heavy last (2). A tie-break, never a filter."""
    if not isinstance(mood, dict) or mood.get("score") is None:
        return 1
    if mood.get("constructive"):
        return 0
    return 2 if mood.get("heavy") else 1


# Direction into a demand band (Ajay 2026-09-08: "I would like to somehow know
# if we are nearing demand zone from the top like falling or Bouncing back from
# Demand zone.. I need the distinction in writing"). Owner constants, no book.
APPROACH_TOUCH_TOL_PCT = 1.0     # the day's low within 1% above the band top = touched it today
APPROACH_LIFT_PCT = 0.5          # the print this far off the day's low = lifting / bouncing
APPROACH_AT_LOW_PCT = 0.2        # the print within this of the day's low = still falling


def approach_read(print_px, band, prev_close=None, day_low=None) -> Optional[dict]:
    """How price reached a demand band, in words. {"dir", "tag", "text"} or
    None when nothing can be said (no prev close and no day low, or the print
    is simply above the band with no lift).

      bouncing  the day's low touched the band (≤ 1% above its top) and the
                print is ≥ 0.5% off that low        → "↑ reversal off"
      falling   yesterday closed ABOVE the band and the print sits at the
                day's low (≤ 0.2% off it, or no low known) → "↓ falling into"
      settling  yesterday closed above the band, the print is between the
                low and the close                    → "↓ settling into"
      resting   inside the band, came from inside/below, no lift → "resting in"
      lifting   above the band from below, ≥ 0.5% off the low  → "↑ lifting off"
      reclaiming yesterday closed UNDER the band and the print is back in or
                above it — a run UP into the band, not a bounce (SMR 2026-09-08:
                +12% on the day when the alert fired)  → "↑ reclaiming"
    """
    px = _f(print_px)
    if px is None or px <= 0 or not _valid_band(band):
        return None
    lo, hi = float(band["lo"]), float(band["hi"])
    pc, dl = _f(prev_close), _f(day_low)
    pc = pc if pc is not None and pc > 0 else None
    dl = dl if dl is not None and dl > 0 else None
    off_low = (px / dl - 1.0) * 100.0 if dl is not None else None
    touched = dl is not None and dl <= hi * (1.0 + APPROACH_TOUCH_TOL_PCT / 100.0)
    from_above = pc is not None and pc > hi
    from_below = pc is not None and pc < lo
    chg = (px / pc - 1.0) * 100.0 if pc is not None else None
    if from_below:
        if px < lo:
            return None                      # still under the floor: nothing reached yet
        return {"dir": "reclaiming", "tag": "↑ reclaiming",
                "text": "↑ reclaiming the band from below (%+.1f%% today)" % chg}
    if touched and off_low is not None and off_low >= APPROACH_LIFT_PCT:
        # Ajay 2026-09-09: "Instead of bounce use the word reversal from Demand
        # zone or something I have trauma with that word now cuz I caught
        # falliing knives with it". WORDING ONLY. The dir key stays "bouncing":
        # it is the value PUSH_DIRECTIONS, direction_gate, the stored dedupe
        # keys and the board tones all match on. Two names for one state is how
        # a gate drifts; the phrase he reads is the only thing that moved.
        return {"dir": "bouncing", "tag": "↑ reversal off",
                "text": "↑ reversal off the band, +%.1f%% off the %g low" % (off_low, dl)}
    if from_above and (off_low is None or off_low <= APPROACH_AT_LOW_PCT):
        return {"dir": "falling", "tag": "↓ falling into",
                "text": "↓ falling into the band from %g (%+.1f%% today)" % (pc, chg)}
    if from_above:
        return {"dir": "settling", "tag": "↓ settling into",
                "text": "↓ came down from %g (%+.1f%% today), holding %.1f%% off the %g low" % (pc, chg, off_low, dl)}
    if lo <= px <= hi:
        return {"dir": "resting", "tag": None, "text": "resting in the band"}
    if px > hi and off_low is not None and off_low >= APPROACH_LIFT_PCT:
        return {"dir": "lifting", "tag": "↑ lifting off",
                "text": "↑ lifting away from the band, +%.1f%% off the %g low" % (off_low, dl)}
    return None


def first_weak_lid(bands, print_px, target=None) -> Optional[dict]:
    """The first band above the print that the room rule does NOT count — a
    lid that fails is_proven_band (a 1-touch shelf, since 2026-09-08) —
    and that sits under `target` (the proven lid the room is measured to).
    FSLR 2026-09-08: the push read "room +17.3% -> $250.99" while the chart
    showed shelves at 233 and 241 first; both were 2-touch bands of strength
    27 / 35, dropped by the KLAC bar. The gate is unchanged — this only puts
    the dropped lid back into the wording so the room is never read as empty
    sky. {"lo","hi","touches","strength","pct"} or None."""
    px = _f(print_px)
    if px is None or px <= 0:
        return None
    tgt = _f(target)
    weak = []
    for b in bands or []:
        if not _valid_band(b) or is_proven_band(b):
            continue
        lo, hi = float(b["lo"]), float(b["hi"])
        if lo <= px:
            continue
        if tgt is not None and lo >= tgt:
            continue
        weak.append((lo, hi, b))
    if not weak:
        return None
    lo, hi, b = min(weak, key=lambda t: t[0])
    return {"lo": round(lo, 2), "hi": round(hi, 2), "touches": int(_f(b.get("touches")) or 0),
            "strength": _f(b.get("strength")), "pct": round((lo - px) / px * 100.0, 1)}


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
            "target": round(target, 2), "touches": first.get("touches"), "band": dict(first),
            # the first lid the rule dropped on the way to the target (2026-09-08)
            "weak": first_weak_lid(bands, px, target)}


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


# Ajay 2026-09-09, after CASY: "Turn off falling in to deman alerts all
# together. only bouncing off alerts".
#
# WHY HE ASKED. On 2026-09-09 at 08:13 ET the phone said "🧲 CASY ↓ falling into
# demand $627.49-651 · buy $627.49-651 · stop $624.35". Two minutes later the
# promo tape said "do not chase" on the same name. He bought at $646.50; CASY
# had reported earnings after the close and printed $604.51 that morning — the
# stop was gone through by 3%.
#
# It also matches the 2026-09-08 autopsy of his own 286 pushes: reclaims from
# below were 40% of pushes and 66% of them hit the floor stop, and same-day
# arrivals on a -3..-8% day closed above the print only 22% of the time. A
# bounce is the only approach that has price already turning.
#
# This is a TIGHTENING. Every other direction still appears on the boards — only
# the PHONE is gated. `None` fails closed: if the approach cannot be read there
# is no evidence of a bounce, and silence is the safe side.
PUSH_DIRECTIONS = ("bouncing",)


# What each internal `dir` is CALLED on his phone and on the boards. The keys
# are the engine's states and never change; the values are the only words he
# reads (Ajay 2026-09-09: "Instead of bounce use the word reversal from Demand
# zone or something I have trauma with that word now cuz I caught falliing
# knives with it"). rules_info renders the phone rule through this map, so the
# panel can never drift from PUSH_DIRECTIONS or re-type the old word.
DIRECTION_LABELS = {
    "bouncing": "a reversal off demand",
    "falling": "falling into",
    "settling": "settling into",
    "resting": "resting inside",
    "lifting": "lifting off",
    "reclaiming": "reclaiming from below",
}


def direction_label(direction) -> str:
    """The words for an internal direction state. Unknown states print as-is."""
    d = str(direction or "").strip().lower()
    return DIRECTION_LABELS.get(d, d)


def direction_gate(approach, allowed=PUSH_DIRECTIONS) -> bool:
    """True only when price is REVERSING off the band (internal dir
    "bouncing"). Fails closed on None."""
    if not isinstance(approach, dict):
        return False
    d = approach.get("dir")
    if not isinstance(d, str):          # a non-string dir is not a reversal
        return False
    return d.strip().lower() in allowed


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
    txt = f"room +{room['room_pct']:g}% -> ${room['target']:g}{rr}"
    weak = room.get("weak")
    if isinstance(weak, dict) and weak.get("lo") is not None:
        # Ajay 2026-09-08 (FSLR): "Do we really have that much room?" — name the
        # weaker shelf the chart draws before the proven target.
        txt += f" · weak lid ${weak['lo']:g} first (+{weak['pct']:g}%, {weak.get('touches') or 0}×)"
    return txt


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


# ─────────────────────────────────────────────────────────────────────────────
# BULLISH REVERSAL, NOT A FALLING KNIFE — Ajay 2026-09-09, after CASY:
#
#   "I think we got alerts wrong.. I need only bullish reversal stocks that
#    touched demand zone and bouncing back.. Those are the only alerts I need
#    and mood has to be bullish too with reversal. After a stationary bottommed
#    stocks as I caught a fallig knife today with Casy"
#
# and, on the mood question, "#1 but I need them to be looking at GEX and other
# bullish patterns to see and also most recent sentiment and they have to be
# <1% of reversal from demand with a minimum of 5% room to Supply" — the last
# two being ALERT_MAX_ABOVE_DEMAND_PCT and ALERT_MIN_ROOM_PCT, unchanged.
#
# WHY. The morning's direction gate (PUSH_DIRECTIONS) was necessary and not
# sufficient: "bouncing" is an INTRADAY read — the day's low touched the band
# and the print is 0.5% off it. CASY satisfied that at 08:13 ET while it was in
# free-fall on a post-earnings repricing. Both of the things that would have
# stopped it were already computed in this repo and neither was wired to the
# phone:
#
#   is_falling_knife(CASY, 2026-09-09) = True
#       swing lows 811.19 -> 740.00 stepping down, 50-day 825.82 -> 822.61 falling
#   mood(CASY) = -24.3 "leaning bearish"      (the floor for a long is +25.0)
#
# COUNTED on the live universe (1,355 names with a demand band, last closed
# session, walking zone_store through these same gates):
#       402 bouncing -> 151 with >=5% room -> 108 within 1% of the band
#           -> 69 not a falling knife          (-36%)
#           -> 15 also mood-bullish on the turn (-78% more)
#
# THAT IS A COUNT, NOT AN EDGE, and the difference matters. Measured afterwards
# on 31,861 replayed bouncing events over 192 dates, date-clustered bootstrap:
#       not a falling knife   win 24.1% vs 24.2%   Δ -0.08pp  CI[-1.62,+1.47]
#       mood >= 25            win 24.3% vs 24.1%   Δ +0.30pp  CI[-1.82,+2.31]
# Both are INDISTINGUISHABLE FROM ZERO. They are here because Ajay asked for
# them after CASY and because a demand band under a post-earnings repricing is
# a line on a chart — a tightening on principle, NOT a measured edge. Do not
# describe them as one. (Lead on win/stop rate: mean R is tail-dominated here,
# the top 1% of events carry 86.6% of total R and the median R is -1.000.)
#
# THE MOOD FRAME IS THE SUBTLE PART. mood() is a TREND read: 25 of its points
# are price vs EMA20/EMA50, 10 are position in the frame's range and 10 are
# higher-highs/higher-lows. A stock that has genuinely BOTTOMED scores -45 on
# those three before momentum and pressure are counted, so it can never reach
# +25 on a 2-year frame — the literal reading of "mood has to be bullish" would
# have silently deleted the exact setup he described and left only strong names
# pulling back. Measured across 1,172 names: 22.6% are mood-bullish, 37.5% sit
# within 8% of their 60-day low, and 1.19% are both.
#
# So the mood is read on a SHORT frame: the same six components, scored over the
# last REVERSAL_MOOD_BARS sessions, which asks "is the TURN bullish" instead of
# "is the TREND bullish". Ajay picked this reading over the literal one.
#
# Both gates FAIL CLOSED. If the structure or the mood cannot be read there is
# no evidence of a bullish reversal, and silence is the safe side — the same
# side direction_gate fails on.

REVERSAL_MOOD_BARS = 60      # sessions the turn is scored over (~3 months)
REVERSAL_MOOD_FLOOR = 25.0   # mood.LABELS: >= +25 is "bullish". His word.
KNIFE_MA_LEN = 50            # the average sd_liquidity.is_falling_knife reads


def daily_frame(symbol, frame=None):
    """The name's daily bars, loaded once and shared by every read below.
    None when they cannot be had."""
    if frame is not None:
        return frame
    try:
        from sepa import prices
        return prices.load_prices(symbol)
    except Exception:                                # noqa: BLE001
        return None


def knife_read(symbol, frame=None) -> Optional[dict]:
    """{"knife", "trend", "swing_lows", "ma", "ma_prior"} on CLOSED daily bars,
    or None when it cannot be computed.

    Neutral price-structure only — NOT the Minervini trend template. See
    sd_liquidity.structure_read / is_falling_knife, which this only wires up:
    swing lows stepping DOWN *and* the 50-day falling, both required, so a
    single shakeout low inside an uptrend does not disqualify a name."""
    df = daily_frame(symbol, frame)
    if df is None or len(df) < KNIFE_MA_LEN + 12:
        return None
    try:
        from . import sd_liquidity as liq
        closed = df.iloc[:-1]                        # never the forming bar
        if len(closed) < KNIFE_MA_LEN + 2:
            return None
        closes, lows = closed["close"], closed["low"]
        ma = closes.rolling(KNIFE_MA_LEN).mean()
        ma_now, ma_prior = _f(ma.iloc[-1]), _f(ma.iloc[-2])
        st = liq.structure_read(closes, lows)
        knife = liq.is_falling_knife(st, float(closes.iloc[-1]), ma_now, ma_prior)
        return {"knife": bool(knife), "trend": st.get("trend"),
                "swing_lows": st.get("swing_lows"),
                "ma": round(ma_now, 2) if ma_now is not None else None,
                "ma_prior": round(ma_prior, 2) if ma_prior is not None else None}
    except Exception:                                # noqa: BLE001
        return None


def knife_gate(symbol, frame=None, read=None) -> bool:
    """True when the name is NOT a falling knife. Unreadable = False (closed)."""
    r = read if isinstance(read, dict) else knife_read(symbol, frame)
    if not isinstance(r, dict) or r.get("knife") is None:
        return False
    return not bool(r["knife"])


def reversal_mood_read(symbol, frame=None, bars: int = REVERSAL_MOOD_BARS) -> Optional[dict]:
    """Mood scored on the last `bars` sessions — the TURN, not the trend.

    Same six components as mood_read; only the window differs, so a name that
    based and turned is judged on the base and the turn instead of on the
    decline that came before them."""
    df = daily_frame(symbol, frame)
    if df is None or len(df) < 6:
        return None
    try:
        from . import mood as mood_mod
        m = mood_mod.mood(df.tail(bars))             # closed_only drops the forming bar
        score = _f(m.get("score"))
        if score is None or m.get("label") == "unavailable":
            return None
        return {"score": round(score, 1), "label": m.get("label"), "bars": bars,
                "bullish": score >= REVERSAL_MOOD_FLOOR,
                "components": m.get("components")}
    except Exception:                                # noqa: BLE001
        return None


def reversal_mood_gate(symbol, frame=None, read=None,
                       floor: float = REVERSAL_MOOD_FLOOR) -> bool:
    """True when the TURN is bullish. Unreadable = False (fails closed)."""
    r = read if isinstance(read, dict) else reversal_mood_read(symbol, frame)
    if not isinstance(r, dict) or r.get("score") is None:
        return False
    return bool(float(r["score"]) >= floor)


def reversal_mood_txt(read: Optional[dict]) -> str:
    """"turn +41 bullish (60d)" — the body fragment, "" when unknown."""
    if not isinstance(read, dict) or read.get("score") is None:
        return ""
    return "turn %+g %s (%dd)" % (read["score"], read.get("label") or "",
                                 read.get("bars") or REVERSAL_MOOD_BARS)


# ─────────────────────────────────────────────────────────────────────────────
# STOP HUNT vs FALLING KNIFE — Ajay 2026-09-09:
#
#   "I am trying to find bullish stocks that got in to demand zone for some
#    reason in the short while where Institutions hunt for stop losses in the
#    journey I been catching some falling knives do what ever is best"
#
# THE SETUP HE IS DESCRIBING IS NOT A BOTTOM. It is a strong name whose demand
# band gets sliced through to take the stops resting under it, and then bought
# back. The difference between that and the knife he keeps catching is ONE
# thing: whether price CLOSED back above the floor.
#
# sd_liquidity.find_sweep has named those three states since 2026-08 and nothing
# but a backtest has ever called it:
#
#     swept    pierced the floor and closed back above it   <- the setup
#     broken   pierced and never reclaimed                  <- the knife
#     intact   never pierced
#
# Its own house geometry already says what he said: pierce >= 0.15% ("must break
# the floor to hit stops"), <= 4.0% ("deeper than this is a breakdown, not a
# stop-run"), reclaim within 12 bars, and sweep-bar volume >= 1.3x local average
# — absorption, not a quiet dip.
#
# This is a READ, not a gate. It rides on the push and the tiles so he can see
# which dip was a stop run and which was a break.

SWEEP_WINDOW_BARS = 15       # how far back a sweep may live and still be "now"


def sweep_read(band, symbol=None, frame=None, window: int = SWEEP_WINDOW_BARS) -> Optional[dict]:
    """{"state","pierce_pct","reclaim_bars","vol_x","sweep_low","stop_shelf"} or
    None when it cannot be computed.

    CLOSED BARS PLUS THE EVENT BAR: the day's low and close are both known at
    the moment a push is decided, so the forming bar is legitimate HERE (unlike
    the structure reads) — a stop run that happened this morning is the whole
    point. Nothing after the decision bar is ever touched."""
    if not _valid_band(band):
        return None
    df = daily_frame(symbol, frame)
    if df is None or len(df) < window + 2:
        return None
    try:
        from . import sd_liquidity as liq
        lo, hi = float(band["lo"]), float(band["hi"])
        w = df.iloc[-window:]
        sw = liq.find_sweep(w, lo, hi)
        state = sw.get("state") or "intact"
        if not sw.get("found") and float(w["low"].min()) < lo:
            state = "broken"          # pierced somewhere in the window, never reclaimed
        return {"state": state,
                "pierce_pct": sw.get("pierce_pct"),
                "reclaim_bars": sw.get("reclaim_bars"),
                "vol_x": sw.get("sweep_volume_x"),
                "sweep_low": sw.get("sweep_low"),
                "stop_shelf": sw.get("stop_shelf")}
    except Exception:                                # noqa: BLE001
        return None


def sweep_txt(read: Optional[dict]) -> str:
    """"🎯 swept the stops -0.8% and reclaimed in 1 bar (2.1x vol)" / "🔪 broke
    the band and stayed under". "" when nothing can be said."""
    if not isinstance(read, dict):
        return ""
    st = read.get("state")
    if st == "swept":
        bits = []
        p = _f(read.get("pierce_pct"))
        if p is not None:
            bits.append("-%.1f%%" % p)
        rb = read.get("reclaim_bars")
        if rb is not None:
            bits.append("reclaimed in %d bar%s" % (int(rb), "" if int(rb) == 1 else "s"))
        v = _f(read.get("vol_x"))
        if v is not None:
            bits.append("%.1fx vol" % v)
        return "\U0001F3AF swept the stops" + (" " + " · ".join(bits) if bits else "")
    if st == "broken":
        p = _f(read.get("pierce_pct"))
        return ("\U0001F52A broke the band%s and stayed under"
                % (" by %.1f%%" % p if p is not None else ""))
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# THE BAND FLOOR MUST HAVE HELD — the one gate measured all day that separates.
#
# Ajay asked for the stop hunt: "bullish stocks that got in to demand zone ..
# where Institutions hunt for stop losses .. I been catching some falling
# knives". The measurement says the stop hunt is the LOSING side.
#
# 31,861 replayed bouncing events, 2,364 names, 192 dates (2025-09-09 ->
# 2026-06-12), win rate with a bootstrap that resamples WHOLE DATES:
#
#     state     n        win     stop-out
#     swept     12,290   22.7%   76.9%     <- the stop hunt he asked for
#     broken    11,990   21.5%   78.2%     <- the knife he keeps catching
#     intact     7,581   30.7%   67.9%     <- the band nobody touched
#     baseline  31,861   24.1%   75.3%
#
#     intact as a gate   keeps 23.8%   Δwin +8.60pp CI[+6.39,+11.06]
#                                      Δstop -9.58pp CI[-12.05,-7.40]
#     swept  as a gate   keeps 38.6%   Δwin -2.37pp CI[-3.76,-1.01]   WORSE
#     broken as a gate   keeps 37.6%   Δwin -4.23pp CI[-5.50,-3.02]   WORSE
#
# THE RECLAIM DOES NOT SAVE IT. A floor that was pierced and bought back still
# underperforms one that was never tested — and the deeper the pierce the worse
# it gets (2-4% sweeps: Δwin -2.80pp CI[-4.49,-1.07]). Whatever a stop run
# signals, it is not that the level will hold the next time.
#
# CONFIRMED TWICE, independently. A separate definition on a different window
# (the shelf study's "no low cut under the band floor in the last N sessions",
# K=20) measured +5.34pp CI[+3.26,+7.43] at N=3 and stayed positive at N=5 and
# N=8. Two implementations, two windows, same answer.
#
# WHY WIN RATE. On this cohort the top 1% of events carry 86.6% of total R and
# the median R is -1.000 in EVERY arm including the baseline. Mean R is a tail
# statistic here; win and stop rates are binomials.
#
# HONEST LIMITS. One 9-month window. ~83% of the replayed cohort sits on bands
# the live push never sees (it takes board-qualified bands only), so the size of
# the effect on his own population is not yet confirmed — the DIRECTION is what
# two independent measurements agree on. Fails closed.

FLOOR_HELD_STATES = ("intact",)


def floor_held_gate(band, symbol=None, frame=None, read=None,
                    allowed=FLOOR_HELD_STATES) -> bool:
    """True when the demand band's floor has NOT been pierced in the sweep
    window. Unreadable = False (fails closed), same side every other phone gate
    fails on."""
    r = read if isinstance(read, dict) else sweep_read(band, symbol, frame)
    if not isinstance(r, dict):
        return False
    st = r.get("state")
    if not isinstance(st, str):
        return False
    return st.strip().lower() in allowed
