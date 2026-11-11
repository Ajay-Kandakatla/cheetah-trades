"""⚡ break_watch — the ONE engine of "the armed 🧠 plan broke on the live bar" (entry spec §3.1, WP-BRK, 2026-11-11).

Ajay 2026-11-11: "Here is how he enters please tell me to enter based on this" — GG buys "right as the next candle
breaks above the high of the pullback bar … without waiting for the candle to close". The A+ push (alerts.py) rings
only after that bar CLOSES; this module watches today's ARMED 🧠 plans on THE existing Massive socket (prints handed in
by live_hub) and rings ⚡ ONCE per (symbol, setup, ET day) the first time a ROUND-LOT regular print trades STRICTLY OVER
an armed plan's trigger inside the live bar that follows the armed bar — only when the socket saw that bar from its
open and no print traded under the stop first. Same window and 1M floor as the A+. The A+ pass stays the backstop and
is not changed; the paper lane is not touched.

HOW IT DECIDES (`decide`, pure — the strict compares of detectors.entry_event):
  1. the live bar already closed → "expired" (nothing recorded; the pass decides A+ or a new plan);
  2. the feed's coverage of the symbol starts after the bar's open → "blind";
  3. the first round-lot print over the trigger and the first print (any lot) under the stop inside the bar;
  4. a stop print at or before the break print → "stopped_first" (one timestamp doing both = stopped);
  5. a break print → "break"; else "wait".
THE RING (its own single worker "gg-brk"; every refusal written ONCE per (plan id, bar) to `brk_held`, never the claim):
  mode off → nothing · closed day · the A+ window on the LIVE bar's start · the two OFF-by-default suppressions (only
  while a switch is ON; a doc without their ctx → suppressed_unknown) · GG's session-volume floor · blind /
  stopped_first · the claim (`brk`, once a day) · shadow → recorded, never sent; live → the sender of KIND.

Mode = GC.GAJJALA_BREAK_PUSH_MODE ("shadow" — HIS CALL #1); KIND = GC.GAJJALA_BREAK_PUSH_KIND (rides the 🧠 kind —
HIS CALL #2). No number is typed here except ODD_LOT_CONDITION (37, pinned equal to the lane's and orderflow.tape's).
UNMEASURED — an intrabar break of the armed plan, not a buy signal.
"""
from __future__ import annotations

import logging
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import live_feed

from . import alerts as GA
from . import constants as GC
from . import ledger as LG

log = logging.getLogger("chart_maps.gajjala.break_watch")

ET = ZoneInfo("America/New_York")
KIND = GC.GAJJALA_BREAK_PUSH_KIND
MODES = GC.GAJJALA_BREAK_PUSH_MODES
REFUSALS = ("closed_day", "suppressed_premarket", "suppressed_first15", "suppressed_window",
            "suppressed_halt", "suppressed_exhausted", "suppressed_unknown",
            "floor_unknown", "under_floor", "blind", "stopped_first", "claimed_before")
CAP_KEY = "refused_cap"
# = trading.gajjala_stream.ODD_LOT_CONDITION = orderflow.tape KEPT_DESPITE_FLAGS "37 Odd Lot Trade" — pinned equal in the
# tests (this module imports no trading.* module). An odd lot never makes the bar high the detector reads.
ODD_LOT_CONDITION = 37
WATCH_MAX = GC.TILE_LIMIT_MAX                            # = live_hub.INTEREST_MAX (derived the same way; pinned equal)
BASE_FRAME = "5m"                                        # alerts.FRAME_MINUTES' default frame (GG5's primary)
BUCKET_SEC = 60 * GA.FRAME_MINUTES[BASE_FRAME]           # derived 300 — one 5-minute bar per bucket
BUCKETS_KEEP = GA.FRAME_MINUTES["15m"] // GA.FRAME_MINUTES[BASE_FRAME] + 1   # derived 4 — a 15-minute Fade + the open one
HALT_KEYS = ("halt_resume_et", "reg_gain_pct")           # the `last` keys WP-POT writes while a suppression switch is ON
TAIL = "UNMEASURED — an intrabar break of the armed plan, not a buy signal"
TAG_PREFIX = "gg-brk"                                    # never the 🧠 "gg-pot-" tag: the break must not replace the armed ring
TERMINAL = ("break", "stopped_first", "blind")
TEXTS = {
    "off": "⚡ Break pushes: off.",
    "shadow": ("⚡ Break pushes: SHADOW — when an armed 🧠 plan trades over its trigger on the live bar it is recorded, "
               "not sent; today's are listed on /alerts. The A+ push still waits for the bar close."),
    "live": ("⚡ Break pushes: LIVE — the first trade over an armed 🧠 plan's trigger on the live bar rings once per name, "
             "setup and day, from {mute_end} ET; never when the feed missed the bar or the stop traded first. The A+ "
             "push still waits for the bar close. UNMEASURED."),
}
TRACK_TEXTS = {"pushed": "⚡ break rang {at} ET", "shadow": "⚡ break seen {at} ET (shadow)"}
SUMMARY_HEAD = "⚡ break pushes today: "
SUMMARY_PARTS = (("pushed", "{n} sent"), ("shadow", "{n} recorded in shadow"))
SUMMARY_RIDES = " — they ride the 🧠 toggle, so your phone's 🧠 count = the 🧠 pushes + these"
_HMS = re.compile(r"\d\d:\d\d:\d\d")

# ── state (one api process, one socket) ────────────────────────────────────────────────────────────────────────
_lock = threading.Lock()
_executor: Optional[ThreadPoolExecutor] = None
_day: Optional[str] = None
_syms: frozenset = frozenset()                           # break_watch's OWN watch list
_plans: dict = {}                                        # SYM → [plan, …] (armed only)
_mem: dict = {}                                          # SYM → {"buckets": {start: {...}}, "covered_from", "last"}
_done: set = set()                                       # (plan id, bar_t) already decided (terminal or expired)
_auth_seen: object = None
_counts: dict = {}


def _fresh_counts() -> dict:
    return {"rang": 0, "shadow": 0, "refused": {k: 0 for k in REFUSALS + (CAP_KEY,)}}


_counts.update(_fresh_counts())


def reset() -> None:
    """Tests only: forget every view, memo and count (the executor is kept)."""
    global _day, _syms, _auth_seen
    with _lock:
        _day, _syms, _auth_seen = None, frozenset(), None
        _plans.clear()
        _mem.clear()
        _done.clear()
        _counts.clear()
        _counts.update(_fresh_counts())


# ── seams (patched in tests) ──────────────────────────────────────────────────────────────────────────────────────
def _now_et() -> datetime:
    return datetime.now(tz=ET)


def _store():
    from . import store as ST
    return ST.default()


def _hooks():
    from push import hooks
    return hooks


def _submit(fn, *args) -> None:
    """Run `fn` on break_watch's OWN single worker "gg-brk" (refreshes and rings never overlap; never queued behind
    a lane order on the hub's worker). Fenced: an exception is logged, never raised."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gg-brk")

    def job():
        try:
            fn(*args)
        except Exception as exc:                                # noqa: BLE001
            log.warning("break_watch: job %s failed: %s: %s", getattr(fn, "__name__", fn), type(exc).__name__, exc)

    try:
        _executor.submit(job)
    except Exception as exc:                                    # noqa: BLE001 — a shut-down pool
        log.warning("break_watch: submit failed: %s", exc)


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def mode() -> str:
    """GC.GAJJALA_BREAK_PUSH_MODE when it is one of the MODES, else "off" (fail closed). Read at CALL time."""
    m = GC.GAJJALA_BREAK_PUSH_MODE
    return m if isinstance(m, str) and m in GC.GAJJALA_BREAK_PUSH_MODES else GC.GAJJALA_BREAK_PUSH_MODES[0]


def _num(x) -> Optional[float]:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def _frame(doc: dict) -> Optional[str]:
    f = doc.get("frame") or BASE_FRAME
    return f if f in GA.FRAME_MINUTES else None


def _hms(t: float) -> str:
    return datetime.fromtimestamp(t, ET).strftime("%H:%M:%S")


def _stamp(t: float) -> str:
    """An epoch → the house bar stamp "YYYY-MM-DD HH:MM" (ET; bars.py — the label alerts.bar_close_et reads)."""
    return datetime.fromtimestamp(t, ET).strftime("%Y-%m-%d %H:%M")


def _mute_end() -> str:
    """ET_RTH_OPEN + NO_TRADE_AFTER_OPEN_MIN as "HH:MM" (09:45 today — built, never typed)."""
    return (datetime.combine(date.min, GA.ET_RTH_OPEN) + timedelta(minutes=GC.NO_TRADE_AFTER_OPEN_MIN)).strftime("%H:%M")


def _switches_on() -> bool:
    return GC.HALT_CALM_BARS is not None or GC.AH_EXHAUSTION_MAX_PCT is not None


def _day_bounds(day: str) -> tuple:
    d = date.fromisoformat(day)
    start = datetime.combine(d, datetime.min.time(), tzinfo=ET)
    return start.timestamp(), (start + timedelta(days=1)).timestamp()


def _roll(day: str) -> None:
    """Caller holds the lock: a new ET day forgets every view, memo, decision and count."""
    global _day, _syms
    if _day == day:
        return
    _day, _syms = day, frozenset()
    _plans.clear()
    _mem.clear()
    _done.clear()
    _counts.clear()
    _counts.update(_fresh_counts())


def _count(reason: str) -> None:
    with _lock:
        _counts["refused"][reason] = _counts["refused"].get(reason, 0) + 1


# ── the plan ──────────────────────────────────────────────────────────────────────────────────────────────────────
def plan_of_doc(doc: dict) -> Optional[dict]:
    """An ARMED tracker doc → its plan, else None. Armed = `last.kind` armed AND `last.state` forming; the trigger is
    over the stop (ledger.plan_of "ok"); `last.bar_t` parses (the armed bar's CLOSE = the live bar's open)."""
    if not isinstance(doc, dict):
        return None
    last = doc.get("last")
    if not isinstance(last, dict):
        return None
    if last.get("kind") != GC.POTENTIAL_KINDS[0] or last.get("state") != GC.POTENTIAL_STATE:
        return None
    if LG.plan_of(last.get("trigger"), last.get("stop"))[0] != LG.PLANS[0]:
        return None
    close = GA.bar_close_et(last.get("bar_t"))
    frame = _frame(doc)
    sym = str(doc.get("symbol") or "").strip().upper()
    setup = doc.get("setup")
    if close is None or frame is None or not sym or not isinstance(setup, str) or not setup:
        return None
    trigger, stop = float(last["trigger"]), float(last["stop"])
    open_t = close.timestamp()
    day = close.date().isoformat()
    return {"id": doc.get("_id") or f"{day}|{sym}|{setup}", "symbol": sym, "setup": setup, "frame": frame,
            "trigger": trigger, "stop": stop, "risk_pct": (trigger - stop) / trigger * 100,   # = detectors._levels
            "bar_t": last.get("bar_t"), "open_t": open_t, "close_t": open_t + 60 * GA.FRAME_MINUTES[frame],
            "session_volume": _num(last.get("session_volume")), "day": day,
            "halt_ctx": {k: last[k] for k in HALT_KEYS if k in last}}


def _fresh(doc: dict, now: float) -> bool:
    """The doc was read forming at a pass whose live bar is still open: epoch(last.bar_t) + its frame > now."""
    last = doc.get("last") if isinstance(doc, dict) else None
    close = GA.bar_close_et(last.get("bar_t")) if isinstance(last, dict) else None
    frame = _frame(doc) if isinstance(doc, dict) else None
    return close is not None and frame is not None and close.timestamp() + 60 * GA.FRAME_MINUTES[frame] > now


# ── the decision (pure) ───────────────────────────────────────────────────────────────────────────────────────────
def decide(plan: dict, ups, downs, covered_from, t: float) -> tuple:
    """("expired",) | ("blind",) | ("stopped_first", t, px) | ("break", t, px) | ("wait",). `ups` / `downs` = [(t, px)]
    (the prints that set a new bucket high — round lots — / low — every print). Strict compares (detectors.entry_event)."""
    open_t, close_t = plan["open_t"], plan["close_t"]
    if t >= close_t:                                     # left-closed [open_t, close_t) like the buckets (2026-11-11 fix)
        return ("expired",)
    if covered_from is None or covered_from > open_t:
        return ("blind",)
    trig, stop = plan["trigger"], plan["stop"]
    over = next(((pt, px) for pt, px in sorted(ups or []) if open_t <= pt < close_t and px > trig), None)
    under = next(((pt, px) for pt, px in sorted(downs or []) if open_t <= pt < close_t and px < stop), None)
    if under is not None and (over is None or under[0] <= over[0]):
        return ("stopped_first",) + tuple(under)
    if over is not None:
        return ("break",) + tuple(over)
    return ("wait",)


# ── the words ─────────────────────────────────────────────────────────────────────────────────────────────────────
def compose(plan: dict, brk: dict, *, broker_text=None, session=None) -> dict:
    """The device payload of one ⚡ break — numbers first. `brk` = {"t": the print's epoch, "px": its price,
    "last_px": the latest print}. Every number is the plan's or a print's."""
    from .potential import deep_link
    sym, setup, frame = plan["symbol"], plan["setup"], plan["frame"]
    emoji, label = GA.SETUP_META.get(setup, ("🚩", setup))
    trig = plan["trigger"]
    first, last = _num(brk.get("px")), _num(brk.get("last_px"))
    bt = broker_text if isinstance(broker_text, str) and broker_text else ""
    title = f"⚡ {sym} · {emoji} {label} — traded over the armed trigger {GA._px(trig)}"
    if bt:
        from .tab import BROKER_FLAG_ICON
        title = f"{title} · {BROKER_FLAG_ICON}"
    last_bit = ""
    if last is not None and first is not None and last != first:
        last_bit = f"last {GA._px(last)} ({(last - trig) / trig * 100:+.1f}% vs the trigger)"
    label_t = _stamp(plan["close_t"])
    ah = GA.AH_TAG if GA.is_after_hours_bar(label_t, session or plan["day"], frame) else ""
    bits = [f"traded {GA._px(first)} at {_hms(brk['t'])} ET, over the trigger {GA._px(trig)}", last_bit,
            f"stop {GA._px(plan['stop'])} (−{plan['risk_pct']:.1f}%)", GA.entry_words(setup),
            f"the {frame} bar has not closed — the A+ push still waits for the close", ah, bt, TAIL]
    return {"title": title, "body": " · ".join(b for b in bits if b), "tag": f"{TAG_PREFIX}-{setup}-{sym}",
            "url": deep_link(sym, setup), "kind": KIND, "ticker": sym,
            "items": [{"symbol": sym, "text": title[len("⚡ "):]}]}


def status() -> dict:
    """The served ⚡ status (tab.py prints `text` verbatim). The counts are this process's (they reset on an api
    restart) — the words never carry them; the docs are the record."""
    m = mode()
    text = TEXTS[m].format(mute_end=_mute_end()) if m in TEXTS else TEXTS["off"]
    try:
        state, word = live_feed.state_word()
        if state != "live" and isinstance(word, str) and word:
            text = f"{text} {word}"
    except Exception as exc:                                    # noqa: BLE001
        log.warning("break_watch: feed word unavailable: %s", exc)
    with _lock:
        return {"mode": m, "text": text, "watching": len(_syms) if m != "off" else 0,
                "plans": sum(len(v) for v in _plans.values()) if m != "off" else 0,
                "rang": _counts["rang"], "shadow": _counts["shadow"], "refused": dict(_counts["refused"])}


def track_text(doc: dict) -> Optional[str]:
    """The 🧠 Track row / the /alerts row word of a doc's ⚡ claim: pushed → rang, shadow → seen (shadow); else None."""
    brk = doc.get("brk") if isinstance(doc, dict) else None
    if not isinstance(brk, dict):
        return None
    t = TRACK_TEXTS.get(brk.get("state")) if isinstance(brk.get("state"), str) else None
    at = brk.get("at_et")
    if t is None or not isinstance(at, str) or not _HMS.fullmatch(at):
        return None
    return t.format(at=at)


def summary_text(states) -> Optional[str]:
    """The /alerts 🧠 strip's ⚡ line from the rows' `brk_state` — parts with 0 dropped; nothing to say → None."""
    states = [s for s in (states or []) if isinstance(s, str)]
    parts = [w.format(n=states.count(k)) for k, w in SUMMARY_PARTS if states.count(k)]
    if not parts:
        return None
    # 2026-11-11 fix: a shadow record never reaches the phone — the 🧠-count clause is said only when one was sent
    rides = SUMMARY_RIDES if KIND == GC.POTENTIAL_PUSH_KIND and "pushed" in states else ""
    return SUMMARY_HEAD + " · ".join(parts) + rides


def rules_line() -> str:
    """The ℹ️ panel line — every number from the constants at CALL time."""
    return (f"⚡ {KIND} (break of an armed 🧠 plan): the first round-lot trade over the trigger inside the "
            f"{GC.PASS_CADENCE_SEC // 60}-minute bar after the armed bar, judged on the live feed; refused when the feed "
            f"did not see that bar from its open, when a trade under the stop came first, before {_mute_end()} ET, "
            f"outside the push hours or under GG's {GC.K11_MIN_SESSION_VOLUME:,}-share session floor; once per name, "
            f"setup and day; mode {mode()}. UNMEASURED.")


# ── the watch list ────────────────────────────────────────────────────────────────────────────────────────────────
def symbols() -> frozenset:
    """break_watch's watch list ("off" → empty)."""
    if mode() == GC.GAJJALA_BREAK_PUSH_MODES[0]:
        return frozenset()
    return _syms


def request_refresh(day: str, now_et: Optional[datetime] = None) -> None:
    """The hub's poll thread: NON-BLOCKING — the refresh runs on break_watch's own "gg-brk" worker."""
    _submit(_refresh_job, day, now_et)


def _refresh_job(day: str, now_et: Optional[datetime]) -> None:
    refresh(day, now_et)


def _sv(doc: dict) -> float:
    v = _num((doc.get("last") or {}).get("session_volume"))
    return v if v is not None else -math.inf


def refresh(day: str, now_et: Optional[datetime] = None) -> int:
    """The "gg-brk" worker ONLY: ONE store read, then the watch list and the plans from FRESH docs; a symbol that left
    the list loses its coverage, buckets and last print; each NEW plan is judged once on the bucket seen so far.
    -> plans held (0 on "off" / a read fault — a fault keeps the previous view)."""
    global _syms
    now_et = now_et or _now_et()
    now = now_et.timestamp()
    if mode() == GC.GAJJALA_BREAK_PUSH_MODES[0]:
        with _lock:
            _roll(day)
            _syms = frozenset()
            _plans.clear()
            _mem.clear()
        return 0
    docs = _store().break_watch_docs(day)
    if docs is None:
        log.warning("break_watch: tracker read failed for %s — the previous watch is kept", day)
        return sum(len(v) for v in _plans.values())
    fresh = [d for d in docs if isinstance(d, dict) and d.get("symbol") and _fresh(d, now)]
    by_sym: dict = {}
    for d in fresh:
        by_sym.setdefault(str(d["symbol"]).strip().upper(), []).append(d)
    ranked = sorted(by_sym, key=lambda s: (0 if any((d.get("last") or {}).get("kind") == GC.POTENTIAL_KINDS[0]
                                                    for d in by_sym[s]) else 1,
                                           -max(_sv(d) for d in by_sym[s]), s))
    keep, cut = ranked[:WATCH_MAX], ranked[WATCH_MAX:]
    plans: dict = {}
    for s in keep:
        for d in by_sym[s]:
            p = plan_of_doc(d)
            if p is not None:
                plans.setdefault(s, []).append(p)
    jobs = []
    with _lock:
        _roll(day)
        left = set(_syms) - set(keep)
        for s in left:
            _mem.pop(s, None)                                   # coverage, buckets and last print go with it [C1]
        _syms = frozenset(keep)
        _plans.clear()
        _plans.update(plans)
        _counts["refused"][CAP_KEY] = len(cut)
        for s, ps in plans.items():
            m = _mem.get(s) or {}
            for p in ps:
                j = _judge(p, m, now)
                if j is not None:
                    jobs.append(j)
    if cut:
        log.info("break_watch: %d symbols over the %d cap — not watched", len(cut), WATCH_MAX)
    for plan, d, last_px in jobs:
        _ring(plan, d, last_px)
    return sum(len(v) for v in plans.values())


def _ups_downs(m: dict) -> tuple:
    ups, downs = [], []
    for b in (m.get("buckets") or {}).values():
        ups.extend(b["ups"])
        downs.extend(b["downs"])
    return ups, downs


def _judge(plan: dict, m: dict, t: float) -> Optional[tuple]:
    """Caller holds the lock. A terminal decision (or expiry) marks (plan id, bar_t) done; terminal → a ring job."""
    key = (plan["id"], plan["bar_t"])
    if key in _done:
        return None
    ups, downs = _ups_downs(m)
    d = decide(plan, ups, downs, m.get("covered_from"), t)
    if d[0] == "expired":
        _done.add(key)
        return None
    if d[0] not in TERMINAL:
        return None
    _done.add(key)
    last = m.get("last")
    return plan, d, (last[0] if last else None)


# ── the print path (socket read loop: no I/O, never raises) ───────────────────────────────────────────────────────
def on_print(pr: dict) -> None:
    """One regular print (the hub applied PRINT_KINDS). O(plans of the symbol); a terminal decision → a ring job on the
    "gg-brk" worker. A print of a symbol not on break_watch's OWN list is ignored (the hub's copy can lag) [C1]."""
    global _auth_seen
    try:
        if mode() == GC.GAJJALA_BREAK_PUSH_MODES[0]:
            return
        sym = str(pr.get("sym") or "").upper()
        px = _num(pr.get("p"))
        t_ms = pr.get("t_ms")
        t = (t_ms / 1000.0) if isinstance(t_ms, (int, float)) and not isinstance(t_ms, bool) and t_ms > 0 \
            else _num(pr.get("recv"))
        if not sym or px is None or t is None:
            return
        conds = pr.get("c") or []
        round_lot = ODD_LOT_CONDITION not in conds
        jobs = []
        with _lock:
            if sym not in _syms:
                return
            if _day is not None:
                lo, hi = _day_bounds(_day)
                if not (lo <= t < hi):
                    if t >= hi:
                        _roll(datetime.fromtimestamp(t, ET).date().isoformat())
                    return
            auth = live_feed.authed_since()
            if auth != _auth_seen:
                for mm in _mem.values():
                    mm["covered_from"] = None                   # a re-auth: every symbol's coverage restarts
                _auth_seen = auth
            m = _mem.setdefault(sym, {"buckets": {}, "covered_from": None, "last": None})
            if m["covered_from"] is None:
                m["covered_from"] = t
            start = int(t // BUCKET_SEC) * BUCKET_SEC
            b = m["buckets"].get(start)
            if b is None:
                b = m["buckets"][start] = {"hi": None, "lo": None, "ups": [], "downs": []}
                for old in sorted(m["buckets"])[:-BUCKETS_KEEP]:
                    m["buckets"].pop(old, None)
            if round_lot and (b["hi"] is None or px > b["hi"]):
                b["hi"] = px
                b["ups"].append((t, px))
            if b["lo"] is None or px < b["lo"]:
                b["lo"] = px
                b["downs"].append((t, px))
            m["last"] = (px, t)
            for plan in _plans.get(sym, ()):
                j = _judge(plan, m, t)
                if j is not None:
                    jobs.append(j)
        for plan, d, last_px in jobs:
            _submit(_ring, plan, d, last_px)
    except Exception as exc:                                    # noqa: BLE001 — never stops the read loop
        log.warning("break_watch: on_print failed: %s: %s", type(exc).__name__, exc)


# ── the ring ("gg-brk" worker) ────────────────────────────────────────────────────────────────────────────────────
def _refusal(plan: dict, now_et: datetime) -> Optional[str]:
    """Steps 2–4 of the ring: the A+'s own clock, window, suppressions and GG's floor."""
    if GA._closed_reason(now_et):
        return "closed_day"
    label = _stamp(plan["close_t"])                             # the LIVE bar, judged by its START (the A+ rule)
    w = GA.window_reason(label, plan["day"], plan["frame"])
    if w:
        return w
    if _switches_on():
        hc = plan.get("halt_ctx") or {}
        if any(k not in hc for k in HALT_KEYS):
            return "suppressed_unknown"
        x = GA.extra_suppression({"entry_bar_t": label, "frame": plan["frame"]},
                                 {"last_halt_resume_et": hc.get("halt_resume_et"),
                                  "reg_gain_pct": hc.get("reg_gain_pct")}, plan["day"])
        if x:
            return x
    sv = plan.get("session_volume")
    if sv is None:
        return "floor_unknown"
    if sv < GC.K11_MIN_SESSION_VOLUME:
        return "under_floor"
    return None


def _hold(store, plan: dict, reason: str, now_et: datetime, decision: tuple) -> None:
    """`brk_held` += {reason, bar_t, at, at_et[, print_t, print_px]} — once per (plan id, bar_t); never the claim."""
    doc = store.get_potential(plan["day"], plan["symbol"], plan["setup"])
    if not isinstance(doc, dict) or "brk" in doc:
        return
    held = [h for h in (doc.get("brk_held") or []) if isinstance(h, dict)]
    if any(h.get("bar_t") == plan["bar_t"] for h in held):
        return
    e = {"reason": reason, "bar_t": plan["bar_t"], "at": now_et.astimezone(timezone.utc),
         "at_et": now_et.astimezone(ET).strftime("%H:%M:%S")}
    if len(decision) == 3:
        e["print_t"] = datetime.fromtimestamp(decision[1], ET).isoformat(timespec="milliseconds")
        e["print_px"] = decision[2]
    held.append(e)
    store.hold_potential_break(plan["id"], held)


def _send(owner: str, payload: dict) -> dict:
    """The sender of KIND — fail closed: a kind without a sender raises before push.hooks is touched."""
    if KIND == GC.POTENTIAL_PUSH_KIND:
        return _hooks().notify_gajjala_potential(owner=owner, payload=payload)
    if KIND == GC.PUSH_KIND:
        return _hooks().notify_gajjala_setup(owner=owner, payload=payload)
    raise RuntimeError(f"no sender for the ⚡ kind {KIND!r}")


def _ring(plan: dict, decision: tuple, last_px) -> None:
    m = mode()
    if m == GC.GAJJALA_BREAK_PUSH_MODES[0]:
        return
    now_et = _now_et()
    store = _store()
    reason = _refusal(plan, now_et)
    if reason is None and decision[0] in ("blind", "stopped_first"):
        reason = decision[0]
    if reason is None and decision[0] != "break":
        return
    if reason is not None:
        _count(reason)
        try:
            _hold(store, plan, reason, now_et, decision)
        except Exception as exc:                                # noqa: BLE001
            log.warning("break_watch: hold write failed for %s: %s", plan["id"], exc)
        return
    t, px = decision[1], decision[2]
    at_et = now_et.astimezone(ET).strftime("%H:%M:%S")
    fields = {"state": "claimed", "at": now_et.astimezone(timezone.utc), "at_et": at_et,
              "print_t": datetime.fromtimestamp(t, ET).isoformat(timespec="milliseconds"), "print_px": px,
              "last_px": last_px, "trigger": plan["trigger"], "stop": plan["stop"], "bar_t": plan["bar_t"],
              "frame": plan["frame"], "kind": KIND, "mode": m}
    res = store.claim_potential_break(plan["id"], fields)
    if res == "taken":
        _count("claimed_before")
        return
    if res != "claimed":
        log.warning("break_watch: claim failed for %s (%s)", plan["id"], res)
        return
    from . import store as ST
    from .tab import broker_text_for
    flags = frozenset(ST.broker_flags(store)[0])
    payload = compose(plan, {"t": t, "px": px, "last_px": last_px}, broker_text=broker_text_for(plan["symbol"], flags),
                      session=plan["day"])
    if m == "shadow":
        store.settle_potential_break(plan["id"], {"state": "shadow", "result": {"would_push": payload}, "at_et": at_et})
        with _lock:
            _counts["shadow"] += 1
        return
    try:
        res = _send(GA._owner(), payload) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("break_watch: send failed for %s: %s", plan["id"], type(exc).__name__)
        store.settle_potential_break(plan["id"], {"state": "failed", "result": {"error": type(exc).__name__},
                                                  "at_et": at_et})
        return
    sent, targets = int(res.get("sent") or 0), int(res.get("total_targets") or 0)
    st = "pushed" if sent > 0 else ("no_target" if targets == 0 else "failed")   # the A+ settle rule (alerts.run_pass)
    store.settle_potential_break(plan["id"], {"state": st, "result": {k: res.get(k) for k in
                                                                     ("sent", "failed", "total_targets", "skipped")},
                                              "at_et": at_et})
    if st == "pushed":
        with _lock:
            _counts["rang"] += 1


__all__ = ["KIND", "MODES", "REFUSALS", "TAIL", "ODD_LOT_CONDITION", "mode", "plan_of_doc", "request_refresh",
           "refresh", "symbols", "on_print", "decide", "compose", "status", "track_text", "summary_text",
           "rules_line"]
