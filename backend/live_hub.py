"""🛰 The live hub (GG LIVE spec §3.2, WP-A, 2026-11-09) — ONE in-api owner of a small WATCH set on THE Massive socket.

Ajay 2026-11-09: "I would like the autopilot to be continously monitored or live tracked … make it more live with
websockets or something else where there is a low latency monitoring on the prices action changes please? same for
reuglar Gajjlas tab as well need it to be more live". Live features are for the OWNER only (his word for this build:
"I only need this setup for myself the owner of the app").

What it does (nothing here changes a rule, a gate, a push or a detector):
  * every HUB_POLL_SEC (only on a trading day inside GC.PASS_OPEN_ET–GC.PASS_CLOSE_ET; else idle, NO Mongo):
      1. today's pushed live 🚩 A+ (`gajjala_alerts`, `GG:{day}|…`, state "pushed") → new ids →
         `trading.gajjala_stream.on_new_aplus(rows, now)` on the worker. The rows already on file when the hub first
         reads a day are SEEDED silently — a restart never fabricates a late "seen".
      2. today's lane docs → `doc_view` (states LANE_WATCH_STATES); any change → `live_events.on_lane_change(day, now)`.
      3. the "latest" pass pointers (GG5's `gajjala_passes` serves 🚩 AND 🧪 — GGA borrows it; GG1's own) → a changed
         {pass_id, finished_at} → `live_events.on_pass(variant, pass_id, finished_at_epoch)` per variant.
      4. the gate snapshot: `exit_engine.get_config()` (one find_one), `trading.broker.mode()` (env), market open from
         the LOCAL calendar (`market_hours.gate.closed_reason` + the RTH clock) — NO Alpaca call, ever. `on_print`
         reads one bool.
      3b. ⚡ (2026-11-11, entry spec §3.1): the GG5 pass pointer change, or the first poll of a day →
          `break_watch.request_refresh(day, now)` — NON-BLOCKING, it runs on break_watch's OWN "gg-brk" worker (never
          queued behind a lane order on this hub's worker).
      5. watch set = lane symbols ∪ today's A+ symbols ∪ every variant's live interest ∪ break_watch's symbols
         → `live_feed.watch/unwatch`.
      6. the bar clock: once per 5-minute boundary at boundary + BAR_CLOSE_OFFSET_SEC → `gajjala_stream.on_bar_close`
         on the worker; a boundary missed by more than BAR_CLOCK_LATE_MAX_SEC (host sleep) is skipped and logged.
      7. `live_events.flush(now)` (the quote batches).
  * `on_print(pr)` — the `live_feed` listener, sync, O(1), no I/O, never raises: ONE print filter (PRINT_KINDS through
    `orderflow.tape.print_kind`) BEFORE every consumer, so the lane, the ⚡ break watch and the screen read the same
    tape (order: lane → break → screen).
  * `register_interest(variant, symbols, levels)` — the on-screen cards, keyed (variant, symbol), TTL
    INTEREST_TTL_SEC, at most INTEREST_MAX symbols per variant (the excess is refused, never silently cut).

Variants are named by their TAB string ("gajjala", "gajjala_1m", "gajjala_audited"); `register_interest` also accepts a
variant key ("gga") and normalizes it to the tab. Every `now` handed to a consumer is a tz-aware ET datetime.
Consumers (`trading.gajjala_stream`, `chart_maps.gajjala.live_events`) are lazy imports; a missing module or a raising
consumer logs one line (rate-limited) and never stops the loop or the socket's read loop. Everything assumes ONE
uvicorn worker (one socket, one hub, one listener).
"""
from __future__ import annotations

import asyncio
import importlib
import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import live_feed
from chart_maps import live_card
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import variant as V
from orderflow import tape as OT
from trading import gajjala_entry as GE

log = logging.getLogger("live_hub")

ET = ZoneInfo("America/New_York")
UTC = timezone.utc

# ── constants (MINE unless derived) ─────────────────────────────────────────────────────────────────────────────
HUB_POLL_SEC = 1.0                                       # MINE — the hub's Mongo poll (≤ 6 indexed reads / s)
HUB_IDLE_SEC = 60.0                                      # MINE — the sleep on a closed day / outside the pass window
INTEREST_TTL_SEC = 2 * live_card.CARD_LIVE_SEC           # derived 60 — two card polls without a renewal = gone
INTEREST_MAX = GC.TILE_LIMIT_MAX                         # derived 80 — per variant (one board's tile cap)
BAR_CLOSE_OFFSET_SEC = GC.BAR_SETTLE_SEC                 # derived 30 — "a bucket counts as closed 30 s after its label"
BAR_CLOCK_MISS_POLLS = 5                                 # MINE (spec §3.2) — a boundary later than 5 polls = missed
BAR_CLOCK_LATE_MAX_SEC = BAR_CLOCK_MISS_POLLS * HUB_POLL_SEC   # derived 5 s
LANE_WATCH_STATES = ("waiting",) + GE._LIVE_STATES       # derived — the docs whose symbol the hub streams
PRINT_KINDS = ("regular",)                               # HIS CALL #2 — names from orderflow.tape.PRINT_KINDS;
                                                         # "regular" includes odd lots (37) and Form T (12)
ERR_LOG_EVERY_SEC = 60.0                                 # MINE — one log line per failing consumer per minute
STREAM_MOD = "trading.gajjala_stream"
EVENTS_MOD = "chart_maps.gajjala.live_events"
BREAK_MOD = "chart_maps.gajjala.break_watch"            # ⚡ 2026-11-11 (entry spec §3.1) — fenced like the others
assert all(k in OT.PRINT_KINDS for k in PRINT_KINDS)

# ── state (single process) ──────────────────────────────────────────────────────────────────────────────────────
_watch: set = set()                                      # the hub's live watch set (live_feed.set_views reads it)
_interest: dict = {}                                     # (variant_tab, SYM) → {"level": dict|None, "expires": epoch}
_interest_syms: dict = {}                                # SYM → {variant_tab, …}
_view: dict = {}
_running = False
_missing: set = set()
_err_at: dict = {}
_executor: Optional[ThreadPoolExecutor] = None
_MISSING = object()


def _fresh_view() -> dict:
    return {"day": None, "doc_view": {}, "lane_syms": frozenset(), "aplus_syms": frozenset(), "gate_ok": False,
            "cfg": {}, "seen": set(), "seeded_day": None, "lane_sig": _MISSING, "pass_sig": {},
            "next_fire": None, "brk_syms": frozenset(), "brk_day": None}


_view.update(_fresh_view())


def reset() -> None:
    """Tests only: forget every set, the interest and the clocks."""
    global _running
    _watch.clear()
    _interest.clear()
    _interest_syms.clear()
    _view.clear()
    _view.update(_fresh_view())
    _missing.clear()
    _err_at.clear()
    _running = False


# ── seams (patched in tests) ────────────────────────────────────────────────────────────────────────────────────
def _now_et() -> datetime:
    return datetime.now(tz=ET)


def _coll(name: str):
    """The collection or None — the lane's own IO seam (one Mongo handle for the lane and the hub)."""
    return GE._coll(name)


def _get_config() -> Optional[dict]:
    from trading import exit_engine as EE
    return EE.get_config()


def _broker_mode() -> str:
    from trading import broker
    return broker.mode()


def _pass_groups() -> list:
    """[(physical passes collection, (variant tabs…))] in VARIANTS order — GGA borrows GG5's `gajjala_passes`."""
    from chart_maps.gajjala import store as ST
    groups: dict = {}
    for v in V.VARIANTS:
        phys = ST.for_variant(v).physical(ST.PASSES)
        groups.setdefault(phys, [])
        groups[phys].append(v.tab)
    return [(k, tuple(tabs)) for k, tabs in groups.items()]


# ── fenced consumer calls ───────────────────────────────────────────────────────────────────────────────────────
def _err(where: str, exc: BaseException) -> None:
    now = time.time()
    if now - _err_at.get(where, 0.0) >= ERR_LOG_EVERY_SEC:
        _err_at[where] = now
        log.warning("live_hub: %s failed: %s: %s", where, type(exc).__name__, exc)


def _mod(name: str):
    if name in _missing:
        return None
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        _missing.add(name)
        log.warning("live_hub: consumer %s not importable (%s) — skipped", name, exc)
        return None


def _fn(mod: str, fn: str) -> Optional[Callable]:
    m = _mod(mod)
    return None if m is None else getattr(m, fn, None)


def _call(mod: str, fn: str, *args):
    f = _fn(mod, fn)
    if f is None:
        return None
    try:
        return f(*args)
    except Exception as exc:                                    # noqa: BLE001 — a consumer never stops the hub
        _err(f"{mod}.{fn}", exc)
        return None


def submit(fn: Callable, *args, **kw) -> Optional[Future]:
    """Run `fn` on the hub's ONE worker thread (hub lane jobs never overlap each other). Fenced: an exception is
    logged, never raised. Used by the hub and by `trading.gajjala_stream` (its memo decides what is submitted)."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="live_hub")
    name = getattr(fn, "__qualname__", repr(fn))

    def job():
        try:
            return fn(*args, **kw)
        except Exception as exc:                                # noqa: BLE001
            _err(f"worker {name}", exc)
            return None

    try:
        return _executor.submit(job)
    except Exception as exc:                                    # noqa: BLE001 — a shut-down pool
        _err("submit", exc)
        return None


def _submit_consumer(mod: str, fn: str, *args) -> None:
    f = _fn(mod, fn)
    if f is not None:
        submit(f, *args)


# ── the window ──────────────────────────────────────────────────────────────────────────────────────────────────
def _hhmm(s: str):
    h, m = s.split(":")
    return datetime(2000, 1, 3, int(h), int(m)).time()


def active(now_et: datetime) -> bool:
    """A trading day (the LOCAL calendar) and inside GC.PASS_OPEN_ET–GC.PASS_CLOSE_ET."""
    from market_hours.gate import closed_reason
    if closed_reason(now_et):
        return False
    return _hhmm(GC.PASS_OPEN_ET) <= now_et.time() < _hhmm(GC.PASS_CLOSE_ET)


def _market_open_local(now_et: datetime) -> bool:
    """Regular hours from the house calendar — never an Alpaca call (C1)."""
    from daytrading.data import ET_RTH_OPEN
    from market_hours.gate import closed_reason
    if closed_reason(now_et):
        return False
    return ET_RTH_OPEN <= now_et.time() < GE._close_t(now_et.date())


# ── one poll ────────────────────────────────────────────────────────────────────────────────────────────────────
def _alerts_query(day: str) -> dict:
    p = V.GG5.claim_prefix
    return {"_id": {"$gte": f"{p}:{day}|", "$lt": f"{p}:{day}}}"}, "state": "pushed"}


def read_world(now_et: datetime) -> dict:
    """Every Mongo read of one poll (runs in a thread). A failed read = None for that block (the block is skipped)."""
    from chart_maps.gajjala import store as ST
    day = now_et.date().isoformat()
    out: dict = {"day": day, "aplus": None, "lane": None, "passes": {}, "cfg": None, "mode": None}
    try:
        c = _coll(ST.ALERTS)
        if c is not None:
            rows = list(c.find(_alerts_query(day),
                               {"symbol": 1, "trigger": 1, "stop": 1, "setup": 1, "claimed_at": 1, "state": 1}))
            p = f"{V.GG5.claim_prefix}:{day}|"
            out["aplus"] = [r for r in rows
                            if str(r.get("_id") or "").startswith(p) and "#" not in str(r.get("_id"))
                            and r.get("state") == "pushed"]
    except Exception as exc:                                    # noqa: BLE001
        _err("read alerts", exc)
    try:
        c = _coll(GE.LANE_COLL)
        if c is not None:
            out["lane"] = list(c.find({"date": day}, {"symbol": 1, "trigger": 1, "stop": 1, "state": 1,
                                                      "updated_at": 1, "alert_at": 1, "setup": 1}))
    except Exception as exc:                                    # noqa: BLE001
        _err("read lane", exc)
    for phys, _tabs in _pass_groups():
        try:
            c = _coll(phys)
            if c is not None:
                out["passes"][phys] = c.find_one({"_id": ST.LATEST_ID}, {"pass_id": 1, "finished_at": 1, "at": 1})
        except Exception as exc:                                # noqa: BLE001
            _err(f"read {phys}", exc)
    try:
        out["cfg"] = _get_config()
        out["mode"] = _broker_mode()
    except Exception as exc:                                    # noqa: BLE001
        _err("read gate", exc)
        out["cfg"] = None
    return out


def _epoch(x) -> Optional[float]:
    if isinstance(x, datetime):
        return (x if x.tzinfo else x.replace(tzinfo=UTC)).timestamp()
    d = GE._parse(x)
    return d.timestamp() if d else None


def _next_fire(now_et: datetime) -> datetime:
    """The first 5-minute boundary + BAR_CLOSE_OFFSET_SEC strictly after `now_et` (ET grid, GC.PASS_CADENCE_SEC)."""
    mid = now_et.replace(hour=0, minute=0, second=0, microsecond=0)
    secs = (now_et - mid).total_seconds()
    c = int(GC.PASS_CADENCE_SEC)
    k = int((secs - BAR_CLOSE_OFFSET_SEC) // c) + 1
    return mid + timedelta(seconds=k * c + BAR_CLOSE_OFFSET_SEC)


def _bar_clock(now_et: datetime) -> bool:
    """True once per boundary, at boundary + BAR_CLOSE_OFFSET_SEC. A boundary found later than BAR_CLOCK_LATE_MAX_SEC
    (host sleep) is skipped with one log line. The next boundary is always the first one after `now_et`."""
    nf = _view.get("next_fire")
    if nf is None:
        _view["next_fire"] = _next_fire(now_et)
        return False
    if now_et < nf:
        return False
    late = (now_et - nf).total_seconds()
    _view["next_fire"] = _next_fire(now_et)
    if late > BAR_CLOCK_LATE_MAX_SEC:
        log.info("live_hub: bar clock skipped the %s boundary (%.1f s late)", nf.strftime("%H:%M:%S"), late)
        return False
    return True


def _gate_ok(cfg, mode, now_et: datetime) -> bool:
    if cfg is None:
        return False
    try:
        return bool(GE.gate(cfg, mode, _market_open_local(now_et))["ok"] and GE.in_entry_window(now_et))
    except Exception as exc:                                    # noqa: BLE001
        _err("gate", exc)
        return False


def _live_interest(now: float) -> set:
    dead = [k for k, r in _interest.items() if r["expires"] <= now]
    for k in dead:
        _drop_interest(k)
    return {k[1] for k in _interest}


def _drop_interest(key) -> None:
    _interest.pop(key, None)
    tabs = _interest_syms.get(key[1])
    if tabs is not None:
        tabs.discard(key[0])
        if not tabs:
            _interest_syms.pop(key[1], None)


def apply(world: dict, now_et: datetime) -> None:
    """The on-loop half of one poll: consumers, the watch diff, the bar clock, the quote flush."""
    v = _view
    day = world.get("day")
    if v.get("day") != day:
        v.update(day=day, seen=set(), seeded_day=None, lane_sig=_MISSING)
    # 1. today's pushed live A+
    rows = world.get("aplus")
    if rows is not None:
        ids = {r.get("_id") for r in rows}
        if v.get("seeded_day") != day:
            v["seen"] = set(ids)
            v["seeded_day"] = day
            if ids:
                log.info("live_hub: %d A+ already on file for %s — seeded, not replayed", len(ids), day)
        else:
            new = [r for r in rows if r.get("_id") not in v["seen"]]
            if new:
                new.sort(key=lambda r: (str(r.get("claimed_at") or ""), str(r.get("_id"))))
                v["seen"] |= {r.get("_id") for r in new}
                _submit_consumer(STREAM_MOD, "on_new_aplus", new, now_et)
        v["aplus_syms"] = frozenset(str(r.get("symbol") or "").upper() for r in rows if r.get("symbol"))
    # 2. lane docs
    docs = world.get("lane")
    if docs is not None:
        dv = {}
        for d in docs:
            if d.get("state") in LANE_WATCH_STATES and d.get("symbol"):
                dv[d.get("_id")] = {"symbol": str(d.get("symbol")).upper(), "trigger": d.get("trigger"),
                                    "stop": d.get("stop"), "state": d.get("state"), "updated_at": d.get("updated_at"),
                                    "alert_at": d.get("alert_at"), "setup": d.get("setup")}
        v["doc_view"] = dv
        v["lane_syms"] = frozenset(x["symbol"] for x in dv.values())
        sig = tuple(sorted((str(d.get("_id")), str(d.get("state")), str(d.get("updated_at"))) for d in docs))
        if v["lane_sig"] is not _MISSING and sig != v["lane_sig"]:
            _call(EVENTS_MOD, "on_lane_change", day, now_et)
        v["lane_sig"] = sig
    # 3. pass pointers
    brk_refresh = v.get("brk_day") != day
    for phys, tabs in _pass_groups():
        if phys not in world.get("passes", {}):
            continue
        ptr = world["passes"].get(phys) or {}
        fin = _epoch(ptr.get("finished_at")) or _epoch(ptr.get("at"))
        sig = (ptr.get("pass_id"), fin)
        prev = v["pass_sig"].get(phys, _MISSING)
        if prev is not _MISSING and sig != prev and ptr.get("pass_id"):
            for tab in tabs:
                _call(EVENTS_MOD, "on_pass", tab, ptr.get("pass_id"), fin)
            if V.GG5.tab in tabs:
                brk_refresh = True
        v["pass_sig"][phys] = sig
    # 3b. ⚡ the break watch's plans — NON-BLOCKING (its own "gg-brk" worker) [entry spec C5]
    if brk_refresh:
        v["brk_day"] = day
        _call(BREAK_MOD, "request_refresh", day, now_et)
    # 4. the gate snapshot (no Alpaca call)
    if "cfg" in world:
        v["cfg"] = world.get("cfg") or {}
        v["gate_ok"] = _gate_ok(world.get("cfg"), world.get("mode"), now_et)
    # 5. the watch set
    brk = _call(BREAK_MOD, "symbols")
    v["brk_syms"] = frozenset(brk) if isinstance(brk, (set, frozenset)) else frozenset()
    desired = set(v["lane_syms"]) | set(v["aplus_syms"]) | _live_interest(time.time()) | set(v["brk_syms"])
    added = sorted(desired - _watch)
    removed = sorted(_watch - desired)
    _watch.difference_update(removed)
    _watch.update(added)
    try:
        if added:
            live_feed.watch(added)
        if removed:
            live_feed.unwatch(removed)
    except Exception as exc:                                    # noqa: BLE001
        _err("watch", exc)
    # 6. the bar clock
    if _bar_clock(now_et):
        _submit_consumer(STREAM_MOD, "on_bar_close", now_et)
    # 7. the quote batches
    _call(EVENTS_MOD, "flush", now_et)


def _go_idle() -> None:
    _view["next_fire"] = None


def tick(now_et: Optional[datetime] = None) -> bool:
    """One synchronous poll (tests and the loop's logic): False = idle (closed day / outside the window, no Mongo)."""
    now_et = now_et or _now_et()
    if not active(now_et):
        _go_idle()
        return False
    apply(read_world(now_et), now_et)
    return True


async def run(*, sleep: Optional[Callable] = None) -> None:
    """The hub loop (started in the api lifespan only when `live_feed.enabled()`)."""
    global _running
    sleep = sleep or asyncio.sleep
    _running = True
    live_feed.add_listener(on_print)
    log.info("live_hub: started (poll %.1f s)", HUB_POLL_SEC)
    try:
        while True:
            now_et = _now_et()
            try:
                if not active(now_et):
                    _go_idle()
                    await sleep(HUB_IDLE_SEC)
                    continue
                world = await asyncio.to_thread(read_world, now_et)
                apply(world, now_et)
            except asyncio.CancelledError:
                raise
            except Exception as exc:                            # noqa: BLE001 — the loop never dies
                _err("poll", exc)
            await sleep(HUB_POLL_SEC)
    finally:
        _running = False


# ── the print path (sync, O(1), no I/O) ─────────────────────────────────────────────────────────────────────────
def on_print(pr: dict) -> None:
    """The `live_feed` listener. ONE filter (PRINT_KINDS) before EVERY consumer (C7). Never raises. Order: the lane,
    then the ⚡ break watch (2026-11-11), then the screen — each fenced."""
    try:
        kind = OT.print_kind(pr.get("c"))
        if kind not in PRINT_KINDS:
            return
        pr["kind"] = kind
        sym = pr.get("sym")
        v = _view
        if sym in v["lane_syms"] or sym in v["aplus_syms"]:
            _call(STREAM_MOD, "on_print", pr, v["doc_view"], v["gate_ok"])
        if sym in v.get("brk_syms", ()):
            _call(BREAK_MOD, "on_print", pr)
        tabs = _interest_syms.get(sym)
        if tabs:
            now = pr.get("recv") or time.time()
            for tab in sorted(tabs):
                rec = _interest.get((tab, sym))
                if rec is not None and rec["expires"] > now:
                    _call(EVENTS_MOD, "on_print", tab, pr, rec.get("level"))
    except Exception as exc:                                    # noqa: BLE001
        _err("on_print", exc)


# ── the cards on screen ─────────────────────────────────────────────────────────────────────────────────────────
def register_interest(variant: str, symbols: list, levels: Optional[dict] = None) -> dict:
    """The cards of one board (C6: keyed (variant, symbol), each with ITS level). Returns {"on", "word", "state"}
    (+ "refused" when the per-variant cap refused symbols — never silently cut). `word`/`state` = the served feed
    word. Unknown variant, a hub that is not running or a feed that is off (state "off") → on False. A degraded
    feed (kicked / down / quiet) still registers → on True with that state, so the board prints the served word."""
    state, word = live_feed.state_word()
    v = V.by_key(variant) or V.by_tab(variant)
    if v is None or not _running or state == "off":
        return {"on": False, "word": word, "state": state}
    tab = v.tab
    now = time.time()
    syms = live_card.normalize(symbols)
    lv: dict = {}
    if isinstance(levels, dict):
        for k, val in levels.items():
            if isinstance(k, str) and k.strip():
                lv[k.strip().upper()] = val
    for key in [k for k, r in _interest.items() if k[0] == tab and r["expires"] <= now]:
        _drop_interest(key)
    live = {k[1] for k in _interest if k[0] == tab}
    refused = []
    for s in syms:
        if s not in live and len(live) >= INTEREST_MAX:
            refused.append(s)
            continue
        _interest[(tab, s)] = {"level": lv.get(s), "expires": now + INTEREST_TTL_SEC}
        _interest_syms.setdefault(s, set()).add(tab)
        live.add(s)
    out = {"on": not refused, "word": word, "state": state}
    if refused:
        out["refused"] = refused
    return out


def interest_of(variant: str, symbol: str) -> Optional[dict]:
    """The live interest record of (variant tab, SYM) or None — read side for tests and the events module."""
    rec = _interest.get((variant, str(symbol or "").upper()))
    if rec is None or rec["expires"] <= time.time():
        return None
    return dict(rec)


def watched() -> set:
    """The hub's live watch set (the SAME object every call — `live_feed` reads it per print)."""
    return _watch


def doc_view() -> dict:
    return _view.get("doc_view") or {}


def gate_ok() -> bool:
    return bool(_view.get("gate_ok"))


__all__ = ["HUB_POLL_SEC", "HUB_IDLE_SEC", "INTEREST_TTL_SEC", "INTEREST_MAX", "BAR_CLOSE_OFFSET_SEC",
           "BAR_CLOCK_LATE_MAX_SEC", "LANE_WATCH_STATES", "PRINT_KINDS", "run", "tick", "apply", "read_world",
           "on_print", "register_interest", "interest_of", "watched", "doc_view", "gate_ok", "submit", "active"]
