"""👀 Gajjala's Watch — frames, tiles and the tile writes (spec 2026-11-15 §3.5.2, WP-B).

Ajay, verbatim (2026-11-15): "When I add a ticker I need 1 min 3 min and 5 min charts... Not the SEPA and I need clear
distinction or may be a brighter and thicker 21 EMA and 9 EMA" · "Any chart I view make sure you are showing me from 4 AM
for historical behaviour and also the right side with gaps to see where it might go".

The house engine only: the closed 1/5/15-minute frames (1/3/5 until 2026-11-23 — Ajay: "Can you remove 3 mins just add 15
mins instead.. So 1 min, 5 and 15 accross board") are `chart_maps.gajjala.bars.frames_for(rules=C.FRAMES)` (the
house resampler, the settle rule, the masked 9 / 21 EMA), the tile is `bars.tile_payload`, the crosses are the card's
`tab.ema_cross_block` over the ONE engine (`ema_cross`), K5 is `detectors.uptrend`. Nothing here is a gate or a
threshold; the axis is display only (04:00 ET → the regular close, or the extended close once a 1-minute bar printed
after the regular close). UNMEASURED — a cross is information, not an entry.

Tile doc (`gajjala_watch_tiles`, `_id` = the symbol) — [C1.2] a read that is not `loaded` `$set`s only
`{symbol, at, status}`: the last good `frames`, `session`, `loaded_at` and `seen_bar_t` stay, served stale.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time as dtime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd

from chart_maps import board
from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as DT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import run_bases as RB
from chart_maps.gajjala import tab as GT
from daytrading.data import ET_PREMARKET_OPEN, ET_RTH_OPEN
from orderflow import signals as EMA

from . import constants as C
from . import vwap as VW

log = logging.getLogger("chart_maps.gajjala_watch.build")

ET = ZoneInfo("America/New_York")
STATUSES = ("loaded", "no_prints", "no_bars", "failed", "over_budget")
UPTREND_SHORT = {True: "K5 ✓", False: "K5 ✗", None: "K5 —"}
SHADE_PRE, SHADE_AH = "pre", "ah"                     # = chart_maps.support._SESSION_FLAG's served words


def uptrend_rule() -> str:
    """The K5 criterion in words (detectors.kiss_fly's `k5_uptrend` need text), the numbers read at CALL time."""
    return (f"K5 uptrend: {GC.EMA_FAST} EMA above the {GC.EMA_SLOW} EMA and both higher than {GC.K5_SLOPE_BARS} "
            f"bars ago")


# ── the session and the frames ────────────────────────────────────────────────────────────────────────────────────
def session_of(now) -> tuple:
    """(session date, is_today, in_window) — tab.session_for (closed day / before 04:00 → the LAST market session)."""
    return GT.session_for(now)


def frames(symbols, session, now, *, load_day=None, budget_sec=GC.GG1M_MINUTE_BUDGET_SEC, stats=None,
           per_name=None) -> dict:
    """{SYM: bars.Frames} with the watch's three frames (C.FRAMES: 1m primary, 5m slow) — bars.frames_for."""
    return B.frames_for(symbols, session, now, load_day=load_day, workers=board.BAR_WORKERS, budget_sec=budget_sec,
                        stats=stats, rules=C.FRAMES, per_name=per_name)


def status_of(entry) -> str:
    """[C1.6] frames_for's per-name entry → the tile status: loaded · no_prints (no bar today, the prior session
    loaded) · no_bars (neither) · failed · over_budget. Anything unreadable → failed."""
    e = entry if isinstance(entry, dict) else {}
    st = e.get("status")
    if st == "loaded":
        return "loaded"
    if st == "no_bars":
        return "no_prints" if e.get("prev") else "no_bars"
    if st == "over_budget":
        return "over_budget"
    return "failed"


# ── the axis (display only) ───────────────────────────────────────────────────────────────────────────────────────
def _day(session) -> date:
    return session if isinstance(session, date) and not isinstance(session, datetime) else \
        date.fromisoformat(str(session)[:10])


def _at(session, t: dtime) -> datetime:
    return datetime.combine(_day(session), t, tzinfo=ET)


def axis_end(session, bars_1m) -> dtime:
    """[C1.7] The tile's ONE axis end: the session's regular close (16:00; 13:00 on a half day — alerts._closes) unless
    a served 1-minute bar closes after it → the extended close (20:00; 17:00 on a half day)."""
    rth, ext = AL._closes(_day(session))
    cut = _at(session, rth)
    for b in bars_1m or []:
        t = AL.bar_close_et(b.get("t") if isinstance(b, dict) else b)
        if t is not None and t > cut:
            return ext
    return rth


def _frame_min(tf: str) -> int:
    rule = dict(C.FRAMES)[tf]
    return int(pd.Timedelta(rule).total_seconds() // 60)


def axis(session, frame_min: int, bars, end: dtime) -> dict:
    """The 04:00 ET axis of one chart: `slots` = (end − 04:00) / frame_min; a bar's slot = (its close − frame_min −
    04:00) / frame_min (a bar is stamped at its close, bars.py); pre-market shaded [04:00, 09:30); after-hours shaded
    [regular close, end) when `end` is the extended close; hourly ticks from 04:00 "HH:MM". Empty slots right of the
    last bar stay empty (the replay's look). 👀 LIVE (2026-11-16): + `start_epoch` (the float epoch of THIS `start`,
    the session's 04:00 ET the slots are measured from) and `frame_min` (`fm`), so the board buckets a live print on
    the server's own grid — `floor((t − start_epoch) / (fm·60))`, closed=left — with no clock arithmetic of its own."""
    fm = max(1, int(frame_min))
    start = _at(session, ET_PREMARKET_OPEN)
    stop = _at(session, end)

    def slot(t: datetime) -> int:
        return int((t - start).total_seconds() // 60) // fm

    slots = slot(stop)
    xs = []
    for b in bars or []:
        close = AL.bar_close_et(b.get("t") if isinstance(b, dict) else None)
        xs.append(slot(close - timedelta(minutes=fm)) if close is not None else None)
    rth, ext = AL._closes(_day(session))
    shade = [{"from_slot": 0, "to_slot": slot(_at(session, ET_RTH_OPEN)), "kind": SHADE_PRE}]
    if end == ext and ext != rth:
        shade.append({"from_slot": slot(_at(session, rth)), "to_slot": slots, "kind": SHADE_AH})
    ticks = []
    h = start
    while h <= stop:
        ticks.append({"slot": slot(h), "label": h.strftime("%H:%M")})
        h += timedelta(hours=1)
    return {"from_et": start.strftime("%H:%M"), "to_et": stop.strftime("%H:%M"), "slots": slots, "x": xs,
            "shade": shade, "ticks": ticks, "start_epoch": start.timestamp(), "frame_min": fm}


# 🎾 2026-11-23 (spec rswatch §3.3; Ajay: "In the reversal squeeze can you make the charts same as in watch list please")
# — the reason words `lead_axis` answers with; the card view (gajjala.card_frames) logs them. The Watch never calls it.
LEAD_DROP_NO_AXIS = "no axis"
LEAD_DROP_NO_PRIOR = "no prior bar"
LEAD_DROP_JUNK_BAR = "junk prior bar"
LEAD_DROP_TWO_DATES = "prior bars span two dates"
LEAD_DROP_NOT_BEFORE = "prior day not before today"
LEAD_DROP_EMPTY = "empty lead"
LEAD_DROP_SLOT = "prior slot outside the lead"
LEAD_DROP_ORDER = "prior slots not increasing"
LEAD_DROP_JUNK_X = "junk today slot"


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _axis_ok(ax) -> bool:
    """`ax` reads as an `axis(...)` answer: int `slots`, numeric `start_epoch`, a list `x`, shade spans and ticks with
    int slots. Anything else is no axis to lead."""
    if not isinstance(ax, dict) or not _is_int(ax.get("slots")) or not isinstance(ax.get("x"), list):
        return False
    se = ax.get("start_epoch")
    if not isinstance(se, (int, float)) or isinstance(se, bool):
        return False
    shade, ticks = ax.get("shade"), ax.get("ticks")
    if not isinstance(shade, list) or not isinstance(ticks, list):
        return False
    if not all(isinstance(s, dict) and _is_int(s.get("from_slot")) and _is_int(s.get("to_slot")) for s in shade):
        return False
    return all(isinstance(t, dict) and _is_int(t.get("slot")) for t in ticks)


def lead_axis(ax: dict, prior_bars, frame_min: int, *, from_et: dtime, to_et: dtime) -> tuple:
    """🎾 2026-11-23 — (axis, None) or (None, reason): `ax` (this module's `axis(...)` of TODAY's bars) with the prior
    session's tail laid in `lead` slots AHEAD of today's 04:00. `lead` = the prior day's [from_et, min(its extended
    close, to_et)) in `frame_min` slots (alerts._closes — half days shorter); a prior bar's slot = (its close −
    frame_min − from_et) / frame_min, the rule `axis` uses; `slots` + lead, today's `x` / `shade` / `ticks` shifted by
    lead; the prior day after its regular close shaded SHADE_AH; ONE tick at slot 0 = the prior day ("Nov 20").
    `start_epoch`, `frame_min`, `from_et`, `to_et` stay today's 04:00 grid (a live print buckets as before). The
    checks run in the LEAD_DROP_* order and the first that fails names the reason; never raises on junk input, never
    a partial axis. Display only."""
    try:
        if not _axis_ok(ax):
            return None, LEAD_DROP_NO_AXIS
        fm = max(1, int(frame_min))
        if not isinstance(prior_bars, list) or not prior_bars:
            return None, LEAD_DROP_NO_PRIOR
        closes = []
        for b in prior_bars:
            c = AL.bar_close_et(b.get("t")) if isinstance(b, dict) else None
            if c is None:
                return None, LEAD_DROP_JUNK_BAR
            closes.append(c)
        days = {c.date() for c in closes}
        if len(days) != 1:
            return None, LEAD_DROP_TWO_DATES
        day = days.pop()
        rth, ext = AL._closes(day)
        start, stop = _at(day, from_et), _at(day, min(ext, to_et))
        if stop.timestamp() > float(ax["start_epoch"]):
            return None, LEAD_DROP_NOT_BEFORE

        def slot(t: datetime) -> int:
            return int((t - start).total_seconds() // 60) // fm

        lead = slot(stop)
        if lead <= 0:
            return None, LEAD_DROP_EMPTY
        px = [slot(c - timedelta(minutes=fm)) for c in closes]
        if any(s < 0 or s >= lead for s in px):
            return None, LEAD_DROP_SLOT
        if any(b <= a for a, b in zip(px, px[1:])):
            return None, LEAD_DROP_ORDER
        if not all(_is_int(x) for x in ax["x"]):
            return None, LEAD_DROP_JUNK_X
        shade = []
        close_at = _at(day, rth)
        if close_at < stop:
            shade.append({"from_slot": max(0, slot(close_at)), "to_slot": lead, "kind": SHADE_AH})
        shade += [{**s, "from_slot": s["from_slot"] + lead, "to_slot": s["to_slot"] + lead} for s in ax["shade"]]
        ticks = [{"slot": 0, "label": f"{day:%b} {day.day}"}] + [{**t, "slot": t["slot"] + lead} for t in ax["ticks"]]
        out = dict(ax)
        out.update({"slots": ax["slots"] + lead, "x": px + [x + lead for x in ax["x"]], "shade": shade,
                    "ticks": ticks, "lead": lead})
        return out, None
    except Exception:                                           # noqa: BLE001 — junk never raises, never a partial axis
        return None, LEAD_DROP_NO_AXIS


# ── one chart, one tile ───────────────────────────────────────────────────────────────────────────────────────────
def k5(F, k) -> Optional[bool]:
    """detectors.uptrend (K5) at bar k of a Frame; None when there is no such bar."""
    if F is None or k is None or not isinstance(k, int) or k < 0 or k >= len(F):
        return None
    return DT.uptrend(F, k)


def tile(frames_obj, tf: str, end: dtime, *, vw=None) -> dict:
    """One chart of a tile: today's closed bars of `tf` from 04:00 (bars.tile_payload, every bar), the 9 / 21 EMA
    curves, the served volume average, the cross markers + block (tab.ema_cross_block — the ➖ card's two lines), K5 at
    the latest bar and the 04:00 axis with the tile's shared `end`. 📈 2026-11-23: `vw` (the name's minute VWAP,
    `vwap.minute_vwap`) adds ONE optional key `vwap` LAST — the stored `curves` stay the two EMAs; without `vw` the
    tile is byte-identical to before."""
    p = B.tile_payload(frames_obj, tf, max_bars=None)
    blk = GT.ema_cross_block({"tf": tf, "bars": p["bars"], "curves": p["curves"]})
    markers = []
    if blk:
        markers = GT._on_bars([{"date": m["t"], "kind": GT.EMA_CROSS_MARK[m["dir"]], "label": m["text"],
                                "price": m["ema"]} for m in blk.pop("_marks")], p["bars"])
    F = frames_obj.frame(tf)
    ok = k5(F, len(F) - 1)
    out = {"tf": tf, "label": C.FRAME_WORDS[tf], "bars": p["bars"], "curves": p["curves"], "vol_avg": p["vol_avg"],
           "markers": markers, "ema_cross": blk or None, "uptrend": {"ok": ok, "short": UPTREND_SHORT[ok]},
           "axis": axis(frames_obj.session, _frame_min(tf), p["bars"], end),
           "as_of_bar_t": F.t[-1] if F.t else None}
    out.update(run_bases_keys(F, tf, p["bars"]))
    out.update(ema_tail_keys(F))
    if vw is not None:
        out.update(vwap_keys(F, tf, vw))
    return out


def vwap_keys(F, tf: str, vw) -> dict:
    """📈 2026-11-23 (spec vwapzones §3.3): {"vwap": {"values": [float | None × today's bars]}} — the minute VWAP after
    the last 1-minute bar inside each of today's buckets (`vwap.frame_values`, rounded to C.VWAP_DP), aligned to the
    served bars; only when at least one value is finite, else {}. Fenced: any fault → {} + one debug line."""
    try:
        if F is None or vw is None or not len(F.today):
            return {}
        labels = F.df.index[F.today.start:F.today.stop]
        vals = VW.frame_values(vw, labels, dict(C.FRAMES)[tf], dp=C.VWAP_DP)
        if not any(v is not None for v in vals):
            return {}
        return {"vwap": {"values": vals}}
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gajjala watch: vwap %s failed: %s", tf, exc)
        return {}


def name_vwap(fr, session):
    """📈 2026-11-23: the name's minute VWAP ONCE per build (`vwap.minute_vwap` over today's raw rows of the sessions
    `vwap.sessions()` names) with the session's REGULAR close as the half-day cut — `alerts._closes`, the function
    `axis_end` / `axis` already read [C2]. None when VWAP is off, C.VWAP_SESSIONS is junk, or anything faults."""
    try:
        sets = VW.sessions() if C.VWAP_ON else None
        if not sets or fr is None:
            return None
        rth = AL._closes(_day(session))[0]
        cut = pd.Timestamp(_at(session, rth)).tz_convert("UTC").tz_localize(None)
        return VW.minute_vwap(getattr(fr, "raw", None), _iso(session), sessions=sets, rth_close=cut)
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gajjala watch: minute vwap failed: %s", exc)
        return None


def ema_tail_keys(F) -> dict:
    """👀 LIVE (2026-11-16): {"ema_tail": {"ema9", "ema21"}} = the LAST value of each EMA over the FULL 2-session frame,
    UNROUNDED, from the ONE engine (`orderflow.signals.ema`, the same kernel `bars._masked_ema` rounds to 6 dp for the
    curves) — the seed a forming bar's tip would chain from (drawn only on HIS CALL #1). {} for an empty frame."""
    if F is None or not len(F):
        return {}
    close = F.df["close"].astype(float)
    return {"ema_tail": {"ema9": float(EMA.ema(close, GC.EMA_FAST).iloc[-1]),
                         "ema21": float(EMA.ema(close, GC.EMA_SLOW).iloc[-1])}}


def run_bases_keys(F, tf: str, bars: list) -> dict:
    """📶 2026-11-15 (Ajay: "There is a concept of 3 bases and climax run can you bake that in to the app please" · "I need
    that tracked in to Gajjala's"; spec ggbase WP-E): on the counting frame ONLY (GC.RUN_BASE_FRAME — the 5-min chart),
    the card's base-count line and marks from the ONE engine (`run_bases.count` → `card_block` / `ellipses`) — the same
    📶 line Gajjala's cards print. {"run_bases": …} / {"ellipses": […]}, each key only when non-empty; every other frame
    → {}. Information only — nothing gates, sorts, filters or pushes on it (the cross push never reads it). UNMEASURED."""
    if tf != GC.RUN_BASE_FRAME or F is None:
        return {}
    rb = RB.count(F)
    out: dict = {}
    card = RB.card_block(rb)
    if card:
        out["run_bases"] = card
    marks = RB.ellipses(rb, bars, tf)
    if marks:
        out["ellipses"] = marks
    return out


def _iso(session) -> str:
    return _day(session).isoformat()


def tile_update(sym: str, fr, session, now, status: str, held: Optional[dict] = None) -> tuple:
    """(filter, update) of one name's tile doc. `loaded` → $set {symbol, session, at, loaded_at, status, frames:
    {tf: tile} in C.FRAMES order, seen_bar_t = the latest closed 1-minute stamp}; any other status → $set
    {symbol, at, status} ONLY (the last good frames stay — [C1.2]). Each held[tf] adds $set "held.<tf>"."""
    at = RUN._utc(now)
    sets: dict = {"symbol": sym, "at": at, "status": status}
    if status == "loaded" and fr is not None:
        F1 = fr.frame(C.AXIS_FRAME)
        end = axis_end(session, [F1.t[i] for i in F1.today])
        vw = name_vwap(fr, session)                             # 📈 2026-11-23 — once per name, every frame reads it
        sets.update({"session": _iso(session), "loaded_at": at,
                     "frames": {tf: tile(fr, tf, end, vw=vw) for tf, _rule in C.FRAMES},
                     "seen_bar_t": F1.t[-1] if F1.t else None})
    elif status == "loaded":
        sets["status"] = "failed"
    for tf, h in (held or {}).items():
        if isinstance(h, dict):
            sets[f"held.{tf}"] = {"bar_t": h.get("bar_t"), "reason": h.get("reason")}
    return {"_id": sym}, {"$set": sets}


def write(tiles_coll, updates) -> int:
    """update_one(filter, update, upsert=True) per name → the number written. A raising write logs once, never raises."""
    if tiles_coll is None:
        return 0
    n, logged = 0, False
    for flt, upd in updates or []:
        try:
            tiles_coll.update_one(flt, upd, upsert=True)
            n += 1
        except Exception as exc:                                # noqa: BLE001
            if not logged:
                log.warning("gajjala watch: tile write failed: %s", type(exc).__name__)
                logged = True
    return n


def seen(tiles_coll, syms) -> dict:
    """{SYM: seen_bar_t} of the listed names' tile docs — ONE find; any failure → {}."""
    if tiles_coll is None or not syms:
        return {}
    try:
        docs = tiles_coll.find({"_id": {"$in": list(syms)}}, {"seen_bar_t": 1})
        return {d["_id"]: d["seen_bar_t"] for d in docs
                if isinstance(d, dict) and isinstance(d.get("seen_bar_t"), str)}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch: tile read failed: %s", type(exc).__name__)
        return {}


__all__ = ["session_of", "frames", "status_of", "axis_end", "axis", "tile", "tile_update", "write", "seen", "k5",
           "run_bases_keys", "vwap_keys", "name_vwap", "uptrend_rule", "UPTREND_SHORT", "STATUSES",
           "lead_axis", "LEAD_DROP_NO_AXIS", "LEAD_DROP_NO_PRIOR", "LEAD_DROP_JUNK_BAR",
           "LEAD_DROP_TWO_DATES", "LEAD_DROP_NOT_BEFORE", "LEAD_DROP_EMPTY", "LEAD_DROP_SLOT", "LEAD_DROP_ORDER",
           "LEAD_DROP_JUNK_X"]
