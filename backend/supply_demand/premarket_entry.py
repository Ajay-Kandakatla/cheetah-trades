"""Premarket + session ENTRY lane — the ready-to-enter cut of the two demand
boards, graded by what we actually measured.

Ajay 2026-09-09: *"I would like to see you ready to enter premarket category
for me from In demand and Deep demands with crons firing in the morning to scan
at 7 CT and another one regular market session but I need an entry signal with
mood considered and demand zone and other criterate we discussed I wanna see
this category in the signals page with a section for it."*

WHAT THIS IS. The Back in Demand and Deep Demand boards answer *which names sit
at a level*. `session_board` asks *is the tape confirming that level*. This
board asks the third question, the one he actually trades: **of those names,
which are ready to ENTER right now, and which are not — and why.**

It adds NO new zone maths. The level, the band and the room all come from the
same `demand_reentry` cache the two tabs read, through
`session_board.board_symbols`, so this board can never disagree with the tabs
it is cut from.

WHAT DECIDES A ROW. Two standing gates plus two measured drags.

GATES (the standing rule, unchanged — `feedback_alert_gate_room_proximity`):
  * `alert_gates.room_gate`        — at least 5% to the first proven band
                                     overhead; CLEAR passes; IN_BAND fails.
  * `alert_gates.demand_proximity_gate` — the print is at the band or within
                                     1% above its top, and never under the floor.
A row that fails either is graded BLOCKED and still listed with its reason.
Boards list everything; gates decide what is tradable. Nothing here loosens a
gate — the 2026-09-08 standing instruction was to improve accuracy by muting
and measuring, never by widening a threshold.

DRAGS (measured 2026-09-08 on 286 graded demand pushes — `sd_autopsy_2026_09_08`):
  * RECLAIM FROM BELOW. Yesterday closed under the band and price ran up into
    it: 115/286 = 40% of pushes, and 66% hit the floor stop, against 11% for
    arrivals from above. This is the single strongest separator we have found.
  * THE −3%..−8% DAY. Names down that much on the day closed above the alert
    print only 22% of the time (n=51), against 57% on −3..0 days and 59% on up
    days. Gaps at or beyond −8% are a different animal (67% up, n=6) and are
    already handled by `alert_gates.gap_day`, so they are NOT dragged here.
A row that passes both gates but carries a drag is graded WATCH, not READY, and
the row says which drag and what the measured rate was. The drag never silently
removes a name — he asked to see the distinction in writing.

MOOD IS CONTEXT, NEVER A GATE. Ajay 2026-09-08: *"I do want signals to sell
based on Supply demand but not on mood. But do include mood in the overall
criteria of the stocks for alerts becuz mood determins if stock grows faster
from demand or not."* So `mood_rank` orders READY rows among themselves and the
text rides along on every row — and `grade_row` never reads it. That separation
is pinned by a test; the mood watcher was deleted on 2026-09-08 and this must
not become it again.

THE TWO PASSES.
  * `premarket` — the 08:00 ET cron (07:00 CT, his ask). The regular-session
    aggregate is still empty, so the print is the snapshot's extended-hours last
    trade (`prices.extended_print`) and the reference is the previous regular
    close. There is no follow-through to read yet, so a premarket row is a plan
    for the open, not a fill.
  * `session` — the RTH crons. Same gates, plus the follow-through read: what
    price has done in the `CONFIRM_WINDOW_MIN` minutes since the level was
    reached. Measured on the same 286: ≤ −1% → 28% up (stop hit 89%);
    0..+1% → 61% up; > +1% → 77% up BUT entering after that lift won only 23%.
    So `confirm_read` reports `chase` above +1% — the move already happened.

NOT ADVICE, and nothing here places an order. The paper lanes have their own
switches; this board is a read.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from supply_demand import alert_gates as AG

log = logging.getLogger("supply_demand.premarket_entry")

ET = ZoneInfo("America/New_York")

# ── passes ─────────────────────────────────────────────────────────────────
PASS_PREMARKET = "premarket"
PASS_SESSION = "session"
PASSES = (PASS_PREMARKET, PASS_SESSION)

# ── grades ─────────────────────────────────────────────────────────────────
GRADE_READY = "READY"
GRADE_WATCH = "WATCH"
GRADE_BLOCKED = "BLOCKED"
GRADE_ORDER = {GRADE_READY: 0, GRADE_WATCH: 1, GRADE_BLOCKED: 2}

# ── measured drags (sd_autopsy_2026_09_08, n=286 graded pushes) ────────────
# Every number below is a MEASURED rate, not a chosen threshold. If the study
# is re-run these move with it — and the wording on the row moves with them,
# because the row text is built from these constants.
RECLAIM_STOP_PCT = 66.0        # reclaims from below that hit the floor stop
ARRIVAL_STOP_PCT = 11.0        # same stop, for arrivals from above
WEAK_DAY_LO_PCT = -8.0         # the −3..−8% bucket: 22% closed above the print
WEAK_DAY_HI_PCT = -3.0
WEAK_DAY_UP_PCT = 22.0
NORMAL_DAY_UP_PCT = 57.0

# ── the follow-through read (session pass only) ────────────────────────────
CONFIRM_WINDOW_MIN = 10        # minutes after the level is reached
CONFIRM_FADE_PCT = -1.0        # ≤ this: 28% up, stop hit 89%
CONFIRM_MAX_LIFT_PCT = 1.0     # > this: 77% up, but entering here won only 23%

CACHE_TTL_SEC = 120
MAX_SYMBOLS = 140


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


# ── pure reads ─────────────────────────────────────────────────────────────
def day_change_drag(change_pct) -> Optional[dict]:
    """The −3%..−8% drag, or None.

    Measured: that bucket closed above the alert print 22% of the time (n=51)
    against 57% on −3..0 days. Beyond −8% is a gap day, which measured 67% up
    (n=6) and is handled by `alert_gates.gap_day` — so it is explicitly NOT a
    drag here. Garbage returns None: a missing day change is not evidence.
    """
    pct = _f(change_pct)
    if pct is None:
        return None
    if WEAK_DAY_LO_PCT <= pct <= WEAK_DAY_HI_PCT:
        return {
            "key": "weak_day",
            "text": (f"down {abs(pct):.1f}% today — the {abs(WEAK_DAY_HI_PCT):g}"
                     f"-{abs(WEAK_DAY_LO_PCT):g}% bucket closed above the alert "
                     f"print only {WEAK_DAY_UP_PCT:g}% of the time "
                     f"(vs {NORMAL_DAY_UP_PCT:g}% otherwise)"),
            "measured_up_pct": WEAK_DAY_UP_PCT,
        }
    return None


def approach_drag(approach: Optional[dict]) -> Optional[dict]:
    """The reclaim-from-below drag, or None.

    `alert_gates.approach_read` tags a run UP into the band from underneath as
    `reclaiming` (shipped 6bfb7fc). Measured: those hit the floor stop 66% of
    the time against 11% for arrivals from above — the strongest separator in
    the study. Any other direction (bouncing, falling, settling, resting,
    lifting) carries no measured drag.

    Reads `dir`, the machine key — NOT `tag`, which is the display string
    ("↑ reclaiming", arrow and all). Matching on `tag` silently never fired and
    graded every reclaim READY (found in the first live run, 2026-09-09: WLDN
    and WLFC both printed "↑ reclaiming the band from below" under a READY
    grade). `test_reclaim_is_dragged_by_dir_not_tag` pins it.
    """
    direction = ((approach or {}).get("dir") or "").strip().lower()
    if direction != "reclaiming":
        return None
    return {
        "key": "reclaim",
        "text": (f"reclaiming the band from below — these hit the floor stop "
                 f"{RECLAIM_STOP_PCT:g}% of the time, against "
                 f"{ARRIVAL_STOP_PCT:g}% for arrivals from above"),
        "measured_stop_pct": RECLAIM_STOP_PCT,
    }


def confirm_read(print_px, ref_px, minutes_since=None) -> Optional[dict]:
    """The follow-through read for the session pass, or None premarket.

    `ref_px` is the print when the level was first reached. Measured on the
    same 286 pushes: ≤ −1% → 28% closed up and the floor stop was hit 89% of
    the time; 0..+1% → 61%; > +1% → 77% up, but ENTERING after that lift won
    only 23% — the lift was the gain. So above +1% the state is `chase`, which
    is information, not an invitation.
    """
    px, ref = _f(print_px), _f(ref_px)
    if px is None or ref is None or ref <= 0:
        return None
    # Round BEFORE bucketing: 101.0/100.0-1 is 1.0000000000000009 in binary
    # floating point, which pushed an exact +1.0% into `chase`. The buckets are
    # quoted to one decimal everywhere, so compare at that precision.
    move = round((px / ref - 1.0) * 100.0, 4)
    if move <= CONFIRM_FADE_PCT:
        state, text = "fading", f"{move:+.1f}% since the level — fades stopped out 89% of the time"
    elif move > CONFIRM_MAX_LIFT_PCT:
        state, text = "chase", f"{move:+.1f}% since the level — already ran; entering after the lift won 23%"
    else:
        state, text = "holding", f"{move:+.1f}% since the level — the 0..+1% bucket closed up 61%"
    out = {"state": state, "move_pct": round(move, 2), "text": text}
    if minutes_since is not None:
        out["minutes_since"] = int(minutes_since)
        out["window_met"] = bool(minutes_since >= CONFIRM_WINDOW_MIN)
    return out


def grade_row(room_ok: bool, prox_ok: bool, drags: list) -> str:
    """READY / WATCH / BLOCKED. Never reads mood — that is deliberate.

    A gate failure is BLOCKED (the row is still listed, with the reason). A row
    that clears both gates but carries a measured drag is WATCH. Only a clean
    row on both gates with no drag is READY.
    """
    if not room_ok or not prox_ok:
        return GRADE_BLOCKED
    return GRADE_WATCH if drags else GRADE_READY


def blockers(room_ok: bool, prox_ok: bool, room: Optional[dict]) -> list:
    """Why a row is BLOCKED, in his words, so the board is auditable."""
    out = []
    if not prox_ok:
        out.append(f"not at the band — the print must sit between the floor and "
                   f"{AG.ALERT_MAX_ABOVE_DEMAND_PCT:g}% above its top")
    if not room_ok:
        state = (room or {}).get("state")
        if state == "IN_BAND":
            out.append("already inside overhead supply — no room to run")
        else:
            pct = (room or {}).get("room_pct")
            have = f"{pct:g}%" if pct is not None else "unknown"
            out.append(f"only {have} to the first proven band overhead — "
                       f"the rule wants {AG.ALERT_MIN_ROOM_PCT:g}%")
    return out


def sort_key(row: dict) -> tuple:
    """READY first, then the measured drags, then MOOD as the tiebreak, then
    proximity to the band. Mood only ever moves a row against another row of
    the same grade — it can never promote one."""
    return (
        GRADE_ORDER.get(row.get("grade"), 9),
        len(row.get("drags") or []),
        AG.mood_rank(row.get("mood")),
        _f(row.get("above_band_pct")) if _f(row.get("above_band_pct")) is not None else 99.0,
    )


# ── the scan ───────────────────────────────────────────────────────────────
def _now_et() -> datetime:
    return datetime.now(tz=ET)


def current_pass(now: Optional[datetime] = None) -> str:
    """Which pass the clock is in. 04:00–09:30 ET is the premarket read;
    everything else uses the session read (after-hours included — the gates are
    the same and the follow-through is simply measured from the last level)."""
    now = now or _now_et()
    mins = now.hour * 60 + now.minute
    return PASS_PREMARKET if 4 * 60 <= mins < 9 * 60 + 30 else PASS_SESSION


def _row(rec: dict, live: dict, pass_name: str) -> Optional[dict]:
    """One board row. Pure given its inputs."""
    sym = rec.get("symbol")
    band = rec.get("band")
    if not sym or not AG._valid_band(band):
        return None

    prev_close = _f(live.get("prev_day_close"))
    close = _f(live.get("price"))
    ext = _f(live.get("last_trade_price"))
    # Premarket: the day aggregate is empty, so the extended print IS the price.
    print_px = (ext or close) if pass_name == PASS_PREMARKET else (close or ext)
    if print_px is None or print_px <= 0:
        return None

    bands = rec.get("bands") or []
    room_ok, room = AG.room_gate(print_px, bands, prev_close)
    prox_ok = AG.demand_proximity_gate(print_px, band)

    approach = AG.approach_read(print_px, band, prev_close, _f(live.get("low")))
    change_pct = _f(live.get("change_pct"))
    if change_pct is None and prev_close and prev_close > 0:
        change_pct = (print_px / prev_close - 1.0) * 100.0

    drags = [d for d in (approach_drag(approach), day_change_drag(change_pct)) if d]
    grade = grade_row(room_ok, prox_ok, drags)

    hi = float(band["hi"])
    return {
        "symbol": sym,
        "name": rec.get("name") or sym,
        "sources": rec.get("sources") or [],
        "theme": rec.get("theme"),
        "pass": pass_name,
        "grade": grade,
        "price": round(print_px, 4),
        "session": (live.get("tape_session")
                    or ("premarket" if pass_name == PASS_PREMARKET else "rth")),
        "prev_close": prev_close,
        "change_pct": round(change_pct, 2) if change_pct is not None else None,
        "band": band,
        "above_band_pct": round((print_px / hi - 1.0) * 100.0, 2) if hi > 0 else None,
        "room": room,
        "room_txt": AG.room_txt(room),
        "approach": approach,
        "approach_txt": (approach or {}).get("text"),
        "mood": rec.get("mood"),
        "mood_txt": AG.mood_txt(rec.get("mood")),
        "drags": drags,
        "blockers": blockers(room_ok, prox_ok, room),
        "plan": AG.plan_txt(print_px, band, room),
        "confirm": None,   # filled by the session pass when a level time exists
    }


def scan(universe: str = "full", pass_name: Optional[str] = None,
         limit: int = MAX_SYMBOLS) -> dict:
    """Build the board. Returns {} shaped payload; never raises for one symbol."""
    from sepa import prices
    from supply_demand import session_board as SB

    pass_name = pass_name if pass_name in PASSES else current_pass()
    recs = SB.board_symbols(universe=universe, limit=limit)
    if not recs:
        return {"warming": True, "pass": pass_name, "universe": universe, "rows": []}

    syms = [r["symbol"] for r in recs]
    try:
        live = prices.bulk_live_prices(syms)
    except Exception as exc:
        log.warning("premarket_entry: live prices failed: %s", exc)
        live = {}

    # The bands the room gate needs come from the zone store, same source the
    # boards use. `load_latest`, not `load`: on a Saturday or before the 04:05
    # warm has run, TODAY has no doc and the room gate would fail every row
    # closed for want of bands. A missing entry means no proven overhead →
    # `room_gate` returns CLEAR, which passes.
    store_day = None
    try:
        from supply_demand import zone_store as ZS
        store_day, stored = ZS.load_latest(syms)
    except Exception as exc:
        log.warning("premarket_entry: zone_store read failed: %s", exc)
        stored = {}

    rows = []
    for rec in recs:
        sym = rec["symbol"]
        rec = dict(rec)
        rec["bands"] = (stored.get(sym) or {}).get("bands") or []
        row = _row(rec, live.get(sym) or {}, pass_name)
        if not row:
            continue
        # Mood is read ONLY for rows that clear both gates — it is context on a
        # tradable row, never a reason to look at an untradable one, and the
        # read costs a frame per symbol.
        if row["grade"] != GRADE_BLOCKED:
            try:
                row["mood"] = AG.mood_read(sym)
                row["mood_txt"] = AG.mood_txt(row["mood"])
            except Exception:
                pass
        rows.append(row)

    rows.sort(key=sort_key)
    counts = {g: sum(1 for r in rows if r["grade"] == g)
              for g in (GRADE_READY, GRADE_WATCH, GRADE_BLOCKED)}
    return {
        "warming": False,
        "pass": pass_name,
        "universe": universe,
        "as_of": _now_et().isoformat(timespec="seconds"),
        "counts": counts,
        "n": len(rows),
        "rows": rows,
        "zone_store_day": store_day.isoformat() if store_day else None,
        "market_closed": market_closed_reason(),
        "rules": rules_lines(),
    }


def rules_lines() -> list:
    """Every line built from the enforcing constant, never retyped — the
    `rules_info` contract (2026-09-06)."""
    return [
        f"Gate 1 — room: at least {AG.ALERT_MIN_ROOM_PCT:g}% to the first PROVEN band "
        f"overhead ({AG.LID_MIN_TOUCHES}+ touches). A clear runway passes.",
        f"Gate 2 — proximity: the print sits at the demand band or within "
        f"{AG.ALERT_MAX_ABOVE_DEMAND_PCT:g}% above its top, never under the floor.",
        f"Drag — reclaiming from below: measured {RECLAIM_STOP_PCT:g}% floor-stop rate "
        f"vs {ARRIVAL_STOP_PCT:g}% for arrivals from above (286 pushes, 2026-09-08). "
        f"Graded WATCH, never hidden.",
        f"Drag — a {abs(WEAK_DAY_HI_PCT):g}-{abs(WEAK_DAY_LO_PCT):g}% down day: closed above "
        f"the print {WEAK_DAY_UP_PCT:g}% of the time vs {NORMAL_DAY_UP_PCT:g}% otherwise. "
        f"Gaps beyond {abs(WEAK_DAY_LO_PCT):g}% are excluded — they measured 67% up.",
        f"Session pass only — follow-through: {CONFIRM_FADE_PCT:g}% or worse reads 'fading' "
        f"(stopped out 89%); above +{CONFIRM_MAX_LIFT_PCT:g}% reads 'chase' (entering after "
        f"the lift won 23%).",
        "Mood is CONTEXT: it orders rows of the same grade and prints on every row. "
        "It can never promote, demote or block one.",
        f"Stop on every plan = the band floor less {AG.STOP_BUFFER_PCT:g}%.",
    ]


# ── cache + cron ───────────────────────────────────────────────────────────
_CACHE: dict = {}
_LOCK = threading.Lock()
_SCAN_LOCKS: dict = {}


def _scan_lock(key: str) -> threading.Lock:
    """One lock per cache key, so two forced passes coalesce onto one scan."""
    with _LOCK:
        lk = _SCAN_LOCKS.get(key)
        if lk is None:
            lk = _SCAN_LOCKS[key] = threading.Lock()
        return lk


def _key(universe: str, pass_name: str, limit: int) -> str:
    return f"{universe}:{pass_name}:{limit}"


def cached_or_warm(universe: str = "full", pass_name: Optional[str] = None,
                   limit: int = MAX_SYMBOLS, force: bool = False) -> dict:
    """Serve what we have and warm in a thread — never block the request.

    Same rule as `demand_reentry.cached_or_warm` and for the same reason:
    Cloudflare cuts the connection at ~100s (the 524 of 2026-08-14).

    EXCEPT under `force`, which blocks and re-scans. `force` used to fall
    through to the background-warm path and return the STALE pass flagged
    `warming: True`, and `record()` refuses a warming payload — so every
    `force=true&record=true` cron would have written nothing to
    `premarket_entry_runs`. This scan reads the demand boards' own caches and
    takes well under a second, so blocking is safe.
    """
    pass_name = pass_name if pass_name in PASSES else current_pass()
    limit = max(1, int(limit or MAX_SYMBOLS))
    key = _key(universe, pass_name, limit)
    if force:
        with _LOCK:
            before = float((_CACHE.get(key) or {}).get("ts") or 0.0)
        with _scan_lock(key):
            with _LOCK:
                hit = _CACHE.get(key)
                if hit and float(hit.get("ts") or 0.0) > before and not hit.get("warming"):
                    return {**hit["data"], "cached": True}   # another pass just ran
            data = scan(universe=universe, pass_name=pass_name, limit=limit)
            with _LOCK:
                _CACHE[key] = {"ts": time.time(), "data": data, "warming": False}
            return data
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(key)
        fresh = hit and (now - hit["ts"]) < CACHE_TTL_SEC
        if fresh:
            return {**hit["data"], "cached": True}
        warming = bool(hit and hit.get("warming"))

    if hit and not warming:
        with _LOCK:
            _CACHE[key] = {**hit, "warming": True}

        def _work():
            try:
                data = scan(universe=universe, pass_name=pass_name, limit=limit)
                with _LOCK:
                    _CACHE[key] = {"ts": time.time(), "data": data, "warming": False}
            except Exception as exc:
                log.warning("premarket_entry warm failed: %s", exc)
                with _LOCK:
                    _CACHE[key] = {**_CACHE.get(key, {}), "warming": False}

        threading.Thread(target=_work, daemon=True).start()
        return {**hit["data"], "cached": True, "warming": True}

    data = scan(universe=universe, pass_name=pass_name, limit=limit)
    with _LOCK:
        _CACHE[key] = {"ts": time.time(), "data": data, "warming": False}
    return data


def market_closed_reason(now: Optional[datetime] = None) -> Optional[str]:
    """'weekend' / 'holiday YYYY-MM-DD' / None — the one calendar
    (`market_hours.gate`). The BOARD still renders on a closed day, on purpose:
    he asked on 2026-09-05 for the bounce/room reads to answer on a Saturday
    evening off the last session. Only `record` is gated, so a holiday cron
    cannot write a history row computed from stale prices."""
    try:
        from market_hours import gate
        return gate.closed_reason(now or _now_et())
    except Exception:
        return None


def record(data: dict) -> bool:
    """Persist one completed pass to Mongo `premarket_entry_runs`.

    Called from the endpoint when the cron asks for `record=true`, so the ONE
    scan that warms the API's own cache is also the one that lands in history.
    A cron that runs `python -m supply_demand.premarket_entry` in the cron
    container would warm a different process's memory and leave the page cold —
    the same trap the 09:25 demand-reentry curl exists to avoid.
    """
    if not data or data.get("warming"):
        return False
    closed = market_closed_reason()
    if closed:
        log.info("premarket_entry: not recording — market closed (%s)", closed)
        return False
    db = None
    try:
        from sepa import prices as _p
        coll = _p._get_mongo()
        db = coll.database if coll is not None else None
    except Exception as exc:
        log.warning("premarket_entry: mongo unavailable: %s", exc)
    if db is None:
        return False
    try:
        db.premarket_entry_runs.insert_one({
            "pass": data["pass"], "universe": data["universe"],
            "as_of": data.get("as_of"), "counts": data.get("counts"),
            "n": data.get("n"),
            "rows": [{k: r.get(k) for k in
                      ("symbol", "grade", "price", "change_pct", "above_band_pct",
                       "band", "approach_txt", "mood_txt", "plan", "drags", "blockers")}
                     for r in data.get("rows") or []],
        })
    except Exception as exc:
        log.warning("premarket_entry: persist failed: %s", exc)
        return False
    log.info("premarket_entry %s recorded: %s", data.get("pass"), data.get("counts"))
    return True


def run(universe: str = "full", pass_name: Optional[str] = None,
        limit: int = MAX_SYMBOLS) -> dict:
    """Manual / module entry point: scan, persist, seed this process's cache."""
    data = scan(universe=universe, pass_name=pass_name, limit=limit)
    record(data)
    if not data.get("warming"):
        with _LOCK:
            _CACHE[_key(data["universe"], data["pass"], limit)] = {
                "ts": time.time(), "data": data, "warming": False}
    return data


if __name__ == "__main__":  # pragma: no cover - cron entry
    logging.basicConfig(level=logging.INFO)
    import sys
    run(pass_name=sys.argv[1] if len(sys.argv) > 1 else None)
