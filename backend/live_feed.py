"""Massive (Polygon-shape) real-time stock WebSocket feed.

Phase 1 of the real-time stack. Replaces the Finnhub WS + REST poller as the
live-quote SOURCE when a Massive Stocks Advanced key is present. It feeds the
SAME ``QuoteCache.update()`` the Finnhub path used, so the SSE bridge
(``events.publish_throttled('quote.update', …)``) and the entire frontend are
unchanged — only the upstream feed swaps from 15-min-capable Finnhub to
real-time Massive.

Two coroutines, started together from ``main.lifespan``:

  massive_ws_consumer(cache, tracked, queue)
      Holds one authenticated WebSocket to ``wss://socket.massive.com/stocks``.
      Subscribes ``T.<sym>`` (trades) for every tracked symbol and drains the
      shared subscribe queue for new ones. Each trade → ``cache.update(price)``.
      Auto-reconnects with exponential backoff; re-subscribes the full tracked
      set on every (re)connect.

  massive_snapshot_poller(cache, tracked, bulk_snapshot)
      The trade stream carries price but NOT the day frame (open/high/low/
      prev-close/volume). This poller backfills those from the Massive bulk
      snapshot every MASSIVE_SNAPSHOT_INTERVAL_SEC. Crucially it never writes a
      ``price`` key, so it can't clobber the live WS tick — and because the SSE
      payload ships both ``price`` (live) and ``prev_close`` (snapshot), the
      browser derives a LIVE percent move off every tick.

Env knobs
---------
  MASSIVE_WS_ENABLED            auto (default) | true | false. ``auto`` = on iff
                                a stocks key is configured.
  MASSIVE_WS_URL                wss://socket.massive.com/stocks (override for the
                                delayed cluster or the legacy polygon host).
  MASSIVE_WS_CHANNELS           "T" (default). Comma list; "T,A" also streams
                                per-second aggregates.
  MASSIVE_SNAPSHOT_INTERVAL_SEC 15.0
  MASSIVE_WS_RECONNECT_COOLDOWN 30 — the wait after an authed drop that is NOT a kick (today's value).
  MASSIVE_WS_KICK_COOLDOWN_SEC  default = MASSIVE_WS_RECONNECT_COOLDOWN — the wait after a KICK (status
                                ``max_connections`` or close code 1008). HIS CALL #10 (GG LIVE spec §7).
  MASSIVE_WS_KICK_YIELD_AFTER_N / _WINDOW_SEC / _SEC — the "never fight" guard: after N kicks inside the window,
                                stop reclaiming for YIELD seconds and say so. Unset = OFF (today's behaviour).

2026-11-09 (GG LIVE spec §3.1, WP-A) — feed honesty + one ordered control queue:
  * kick timeline (in memory, ``EVENTS_MAX``; best-effort Mongo ``live_feed_events``, TTL, written off the read loop),
    kicks / blind seconds / resume / lag / message-rate keys on ``feed_state`` and one served ``word`` per state;
  * ``enabled()`` is False on ``CHEETAH_ENV == "dev"`` in ``auto`` (a dev stack never opens a second socket on the
    prod key); an explicit ``MASSIVE_WS_ENABLED=true`` still wins;
  * the hub (``live_hub``) owns a small WATCH set on THIS socket: ``watch`` / ``unwatch`` enqueue ``("sub"|"unsub",
    sym)`` on the SAME queue the UI subscribes through (a ``str`` item = today's subscribe); ONE pump drains it in
    order, and an unsubscribe is sent only if, at SEND time, the symbol is neither UI-tracked nor hub-watched;
  * routing: a hub symbol's print goes to the hub listener FIRST (sync, no I/O), then a tracked symbol's print to
    ``await cache.update`` (unchanged payload). ``_handle(raw, cache)`` with no ``tracked`` = today's behaviour.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import websockets

from massive_keys import stocks_key
import accumulation

log = logging.getLogger("market_stream")

MASSIVE_WS_URL = os.getenv("MASSIVE_WS_URL", "wss://socket.massive.com/stocks")
MASSIVE_WS_CHANNELS = [
    c.strip().upper() for c in os.getenv("MASSIVE_WS_CHANNELS", "T").split(",") if c.strip()
]
SNAPSHOT_INTERVAL_SEC = float(os.getenv("MASSIVE_SNAPSHOT_INTERVAL_SEC", "15"))
# Symbols per subscribe frame. Massive accepts long param strings; we chunk to
# stay well under any frame-size limit on a broad-universe subscribe.
_SUBSCRIBE_BATCH = int(os.getenv("MASSIVE_WS_SUBSCRIBE_BATCH", "250"))
# The account allows only ONE concurrent stocks WS connection (per cluster, shared by every key on the account).
# Corrected 2026-11-09: the old comment here said the server "takes ~20-60s to release a dropped one" — that is NOT
# what Massive documents. On Stocks the OLDER connection is closed and the NEW one keeps streaming, so after our own
# unclean drop a reconnect only kicks our own ghost; after a KICK, reconnecting kicks the other client. The 30 s wait
# is kept (value and behaviour unchanged) for authed drops; its measured need is HIS CALL #11 (the canary).
_RECONNECT_COOLDOWN = float(os.getenv("MASSIVE_WS_RECONNECT_COOLDOWN", "30"))


def _env_float(name: str) -> Optional[float]:
    v = (os.getenv(name) or "").strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


# ── knobs (GG LIVE spec §3.1) — every default = today's behaviour ───────────────────────────────────────────────
KICK_COOLDOWN_SEC = float(os.getenv("MASSIVE_WS_KICK_COOLDOWN_SEC", str(_RECONNECT_COOLDOWN)))  # HIS CALL #10 — = today's 30 s
KICK_YIELD_AFTER_N: Optional[int] = (int(_env_float("MASSIVE_WS_KICK_YIELD_AFTER_N"))           # HIS CALL #10 — None = OFF
                                     if _env_float("MASSIVE_WS_KICK_YIELD_AFTER_N") is not None else None)
KICK_YIELD_WINDOW_SEC: Optional[float] = _env_float("MASSIVE_WS_KICK_YIELD_WINDOW_SEC")          # HIS CALL #10 — None = OFF
KICK_YIELD_SEC: Optional[float] = _env_float("MASSIVE_WS_KICK_YIELD_SEC")                        # HIS CALL #10 — None = OFF
KICK_STATUS = "max_connections"          # the Massive status that means "another connection took the stream"
KICK_CLOSE_CODE = 1008                   # the close code Massive sends with it (policy violation)
TIMELINE_STATUSES = (KICK_STATUS, "auth_failed", "auth_timeout", "error")   # the statuses the timeline records
EVENTS_MAX = 500                         # MINE — in-memory kick-timeline rows
EVENTS_SERVED = 50                       # MINE — rows `/live/feed-status?events=1` serves (admins only)
LAG_SAMPLES = 1000                       # MINE — recv − SIP `t` samples behind lag_ms_p50 / p99
MSG_RATE_WINDOW_SEC = 60                 # the "1m" in msgs_per_s_1m
KICKS_HOUR_SEC = 3600                    # the "1h" in kicks_1h
WHY_MAX = 80                             # MINE — characters of the error shown in the "down" word
LIVE_FEED_EVENTS_COLL = "live_feed_events"


def _events_ttl_days() -> int:
    from chart_maps.gajjala import constants as GC
    return int(GC.READS_TTL_DAYS)


LIVE_FEED_EVENTS_TTL_DAYS = _events_ttl_days()     # MINE, = chart_maps.gajjala.constants.READS_TTL_DAYS (14)

# Served words (GG LIVE spec §3.1, verbatim). `yielding` is the "say so" of the yield guard (OFF by default).
FEED_WORDS = {
    "live": "📡 Live prices — last print {age} s ago",
    "kicked": "📡 Reconnecting — another connection on this Massive key took the stream ({n} times today). "
              "The 1-minute check keeps running.",
    "yielding": "📡 Paused — another connection on this Massive key keeps taking the stream ({n} times today); "
                "not reclaiming it for {wait} s. The 1-minute check keeps running.",
    "down": "📡 Live stream down ({why}) — the 1-minute check keeps running.",
    "quiet": "📡 Connected — no prints (market closed).",
    "off": "📡 Live stream off on this server.",
}
ADMIN_WORD = "lag {p50} ms · {kicks} kicks today · {blind} s blind"
FEED_STATES = ("live", "kicked", "down", "quiet", "off")
_ET = ZoneInfo("America/New_York")

# Observable state for the /live/feed-status endpoint. Single process, single
# WS — a plain dict is enough (no cross-process sharing needed).
feed_state: dict = {
    "source": "massive_ws",
    "url": MASSIVE_WS_URL,
    "channels": MASSIVE_WS_CHANNELS,
    "connected": False,
    "authed": False,
    "tracked": 0,
    "focus": 0,
    "trades": 0,
    "last_msg_ts": 0.0,
    "last_trade_ts": 0.0,
    "reconnects": 0,
    "error": None,
}

# ── run-time state behind the new keys (single process, single socket) ──────────────────────────────────────────
_events: deque = deque(maxlen=EVENTS_MAX)
_lag: deque = deque(maxlen=LAG_SAMPLES)
_msg_buckets: deque = deque(maxlen=MSG_RATE_WINDOW_SEC + 1)      # [epoch second, n]
_kick_times: deque = deque(maxlen=EVENTS_MAX)
_today: dict = {"day": None, "kicks": 0, "blind_s": 0.0}
_link: dict = {"conn_ts": None, "trades": 0, "kicked": False, "auth_ts": None, "drop_ts": None,
               "kick_pending": False, "yielding_wait": None, "last_kick_ts": None, "resume_s_last": None}
_listeners: list = []
_views: dict = {"tracked": None, "hub": None}
_queue: Optional["asyncio.Queue"] = None
_subscribed_t: set = set()
_bg: set = set()                                 # fire-and-forget persist tasks (kept referenced until done)
_EVENTS_COLL = None
_EVENTS_DISABLED = False


def enabled() -> bool:
    """Whether the Massive WS feed should be the live-quote source."""
    v = os.getenv("MASSIVE_WS_ENABLED", "auto").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("1", "true", "yes", "on"):
        return True
    # auto: never on a dev stack (it would open a SECOND socket on the prod key and kick prod — spec §1.1/§3.1)
    if (os.getenv("CHEETAH_ENV") or "").strip().lower() == "dev":
        return False
    return bool(stocks_key())  # auto: on when a stocks key exists


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _scrub(text) -> Optional[str]:
    """Any text that leaves this module: the stocks key never appears in it."""
    if text is None:
        return None
    t = str(text)
    k = stocks_key()
    if k and k in t:
        t = t.replace(k, "•••")
    return t


def _scrub_obj(obj):
    if isinstance(obj, str):
        return _scrub(obj)
    if isinstance(obj, dict):
        return {k: _scrub_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_scrub_obj(v) for v in obj]
    return obj


def _et_iso(ts: Optional[float]) -> Optional[str]:
    if not ts:
        return None
    return datetime.fromtimestamp(float(ts), tz=_ET).isoformat(timespec="seconds")


def _roll_day(now: float) -> None:
    day = datetime.fromtimestamp(now, tz=_ET).strftime("%Y-%m-%d")
    if _today["day"] != day:
        _today.update(day=day, kicks=0, blind_s=0.0)


def _pctl(sorted_vals: list, q: float) -> Optional[float]:
    """Linear-interpolation percentile (numpy's default method) of an already-sorted list."""
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return float(sorted_vals[0])
    pos = (n - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    return float(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo))


def _count_msg(now: float) -> None:
    sec = int(now)
    if _msg_buckets and _msg_buckets[-1][0] == sec:
        _msg_buckets[-1][1] += 1
    else:
        _msg_buckets.append([sec, 1])


def _msgs_per_s(now: float) -> float:
    lo = now - MSG_RATE_WINDOW_SEC
    n = sum(c for s, c in _msg_buckets if s > lo)
    return round(n / float(MSG_RATE_WINDOW_SEC), 2)


def _events_coll():
    """Mongo `live_feed_events` (TTL on `at`) or None — called only from a worker thread, never the read loop."""
    global _EVENTS_COLL, _EVENTS_DISABLED
    if _EVENTS_DISABLED:
        return None
    if _EVENTS_COLL is not None:
        return _EVENTS_COLL
    try:
        from pymongo import MongoClient
        client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"), serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        coll = client[os.getenv("MONGO_DB", "cheetah")][LIVE_FEED_EVENTS_COLL]
        coll.create_index("at", expireAfterSeconds=LIVE_FEED_EVENTS_TTL_DAYS * 86400)
        _EVENTS_COLL = coll
        return coll
    except Exception as exc:                                    # noqa: BLE001
        log.warning("live_feed: events timeline not persisted (%s)", type(exc).__name__)
        _EVENTS_DISABLED = True
        return None


def _persist_event(row: dict) -> None:
    coll = _events_coll()
    if coll is None:
        return
    try:
        coll.insert_one(dict(row, at=datetime.fromtimestamp(row["ts"], tz=timezone.utc)))
    except Exception as exc:                                    # noqa: BLE001
        log.debug("live_feed: event persist failed: %s", exc)


def _timeline(kind: str, now: Optional[float] = None, *, status=None, message=None, close_code=None,
              wait_s=None) -> dict:
    """One kick-timeline row: in memory always; Mongo best-effort in a fire-and-forget worker task."""
    now = time.time() if now is None else now
    conn_ts = _link.get("conn_ts")
    row = {"ts": round(now, 3), "ts_et": _et_iso(now), "kind": kind, "status": status,
           "message": _scrub(message)[:200] if message is not None else None, "close_code": close_code,
           "conn_age_s": round(now - conn_ts, 1) if conn_ts else None,
           "trades_in_conn": int(_link.get("trades") or 0),
           "wait_s": wait_s}
    _events.append(row)
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(asyncio.to_thread(_persist_event, dict(row)))
        _bg.add(task)
        task.add_done_callback(_bg.discard)
    except RuntimeError:
        pass                                                    # no loop (a sync caller) — memory only
    return row


def _note_status(st, message, now: float) -> None:
    """Timeline only what explains a drop: auth_success ("auth") and the kick / failure statuses ("status").
    Per-symbol subscribe acks ("success"), "connected" and every other status are NOT recorded (one ack per
    symbol per reconnect would bury the kicks and blow the ~500 rows/day budget)."""
    if st == "auth_success":
        _timeline("auth", now, status=st, message=message)
        return
    if st not in TIMELINE_STATUSES:
        return
    _timeline("status", now, status=st, message=message)
    if st == KICK_STATUS:
        _link["kicked"] = True


def _on_auth(now: float) -> None:
    """auth_success on a fresh connection: close the blind window opened by the last drop."""
    _roll_day(now)
    drop = _link.get("drop_ts")
    if drop:
        gap = max(0.0, now - drop)
        _today["blind_s"] += gap
        _link["resume_s_last"] = round(gap, 1)
    _link.update(auth_ts=now, drop_ts=None, kick_pending=False, yielding_wait=None)


def _is_kick(exc_text: str, close_code) -> bool:
    return bool(_link.get("kicked")) or close_code == KICK_CLOSE_CODE or KICK_STATUS in (exc_text or "").lower()


def _yield_due(now: float) -> bool:
    if KICK_YIELD_AFTER_N is None or KICK_YIELD_WINDOW_SEC is None or KICK_YIELD_SEC is None:
        return False
    lo = now - KICK_YIELD_WINDOW_SEC
    return sum(1 for t in _kick_times if t >= lo) >= KICK_YIELD_AFTER_N


def _on_drop(*, was_authed: bool, exc_text: str, close_code, backoff: float, clean: bool,
             now: Optional[float] = None) -> float:
    """Classify one drop, update the counters, return the wait before the next connect.

    Today's wait first: a clean close → 0 (reconnect at once); an authed drop or a max_connections text →
    _RECONNECT_COOLDOWN; anything else → `backoff`. A kick (status max_connections | close 1008) is COUNTED in every
    case; where today cools, the wait becomes KICK_COOLDOWN_SEC (default = _RECONNECT_COOLDOWN); with the yield guard
    ON and due, KICK_YIELD_SEC. Defaults reproduce today's waits exactly."""
    now = time.time() if now is None else now
    _roll_day(now)
    kicked = _is_kick(exc_text, close_code)
    if (was_authed or kicked) and not _link.get("drop_ts"):
        _link["drop_ts"] = now
    _timeline("close", now, message=exc_text or None, close_code=close_code)
    # Today's wait, exactly: a clean close → at once; an authed drop or a max_connections text → the cooldown;
    # anything else → the exponential backoff.
    cooling = (not clean) and (was_authed or KICK_STATUS in (exc_text or "").lower())
    wait = 0.0 if clean else (_RECONNECT_COOLDOWN if cooling else backoff)
    _link["yielding_wait"] = None
    if kicked:
        _today["kicks"] += 1
        _kick_times.append(now)
        _link.update(last_kick_ts=now, kick_pending=True)
        if _yield_due(now):                      # the yield guard (OFF by default) — the only added wait
            wait = float(KICK_YIELD_SEC)
            _link["yielding_wait"] = wait
        elif cooling:                            # the kick knob replaces today's cooldown VALUE, never adds a wait
            wait = KICK_COOLDOWN_SEC
    _link["kicked"] = False
    _timeline("reconnect_wait", now, wait_s=wait)
    return wait


def _close_code_of(exc) -> Optional[int]:
    rcvd = getattr(exc, "rcvd", None)
    code = getattr(rcvd, "code", None)
    if code is None:
        code = getattr(exc, "code", None)
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


# ── the hub's view of this socket (live_hub) ────────────────────────────────────────────────────────────────────
def add_listener(fn: Callable[[dict], None]) -> None:
    """Register a print listener (the hub's `on_print`): called synchronously, FIRST, for every T print of a
    hub-watched symbol with {"sym", "p", "s", "c", "t_ms", "recv", "trfi"}. It must never block or raise."""
    if fn not in _listeners:
        _listeners.append(fn)


def set_views(tracked: set, hub: Callable[[], set], queue: Optional["asyncio.Queue"] = None) -> None:
    """Tell `_handle` and the pump which symbols the UI tracks and which the hub watches (`hub()` returns the
    hub's live set). `queue` (optional) = the ONE control queue, when the consumer has not started yet."""
    global _queue
    _views["tracked"] = tracked
    _views["hub"] = hub
    if queue is not None:
        _queue = queue


def _hub_set() -> set:
    fn = _views.get("hub")
    if fn is None:
        return set()
    try:
        return fn() or set()
    except Exception:                                           # noqa: BLE001
        return set()


def _norm(symbols) -> list:
    out = []
    for s in symbols or []:
        if isinstance(s, str) and s.strip():
            u = s.strip().upper()
            if u not in out:
                out.append(u)
    return out


def watch(symbols: list) -> int:
    """Hub only: enqueue ("sub", sym) per symbol on the ONE control queue. Returns how many were queued."""
    q = _queue
    if q is None:
        return 0
    n = 0
    for s in _norm(symbols):
        q.put_nowait(("sub", s))
        n += 1
    return n


def unwatch(symbols: list) -> int:
    """Hub only: enqueue ("unsub", sym); the pump re-checks UI-tracked ∪ hub-watched at SEND time."""
    q = _queue
    if q is None:
        return 0
    n = 0
    for s in _norm(symbols):
        q.put_nowait(("unsub", s))
        n += 1
    return n


async def _unsubscribe(ws, symbols: list, channels: Optional[list] = None) -> None:
    chans = channels or MASSIVE_WS_CHANNELS
    syms = [s for s in symbols if s]
    if not syms:
        return
    params = ",".join(f"{ch}.{s}" for s in syms for ch in chans)
    await ws.send(json.dumps({"action": "unsubscribe", "params": params}))


async def _send_control(ws, item, tracked) -> Optional[str]:
    """ONE control item onto the socket, in queue order. Returns what was sent ("subscribe" | "unsubscribe") or
    None when the item was dropped.

    str            → subscribe T (today's protocol, always sent)
    ("sub", s)     → subscribe T unless already subscribed on this connection
    ("unsub", s)   → unsubscribe only if, NOW, s is neither UI-tracked nor hub-watched"""
    if isinstance(item, str):
        await _subscribe(ws, [item])
        _subscribed_t.add(item)
        return "subscribe"
    if not isinstance(item, tuple) or len(item) != 2:
        return None
    op, sym = item
    if op == "sub":
        if sym in _subscribed_t:
            return None
        await _subscribe(ws, [sym])
        _subscribed_t.add(sym)
        return "subscribe"
    if op == "unsub":
        if sym in (tracked or set()) or sym in _hub_set():
            return None
        if sym not in _subscribed_t:
            return None
        await _unsubscribe(ws, [sym])
        _subscribed_t.discard(sym)
        return "unsubscribe"
    return None


# ── the served view ─────────────────────────────────────────────────────────────────────────────────────────────
def _quiet(now: float) -> bool:
    from daytrading.data import ET_PREMARKET_OPEN, ET_AFTERHOURS_CLOSE
    from market_hours.gate import closed_reason
    n = datetime.fromtimestamp(now, tz=_ET)
    try:
        if closed_reason(n):
            return True
    except Exception:                                           # noqa: BLE001
        pass
    return not (ET_PREMARKET_OPEN <= n.time() < ET_AFTERHOURS_CLOSE)


def state_word(now: Optional[float] = None, *, is_enabled: Optional[bool] = None) -> tuple:
    """(state, word) — the ONE served feed word (GG LIVE spec §3.1)."""
    now = time.time() if now is None else now
    _roll_day(now)
    on = enabled() if is_enabled is None else is_enabled
    if not on:
        return "off", FEED_WORDS["off"]
    if _link.get("kick_pending"):
        y = _link.get("yielding_wait")
        if y is not None:
            return "kicked", FEED_WORDS["yielding"].format(n=_today["kicks"], wait=int(round(y)))
        return "kicked", FEED_WORDS["kicked"].format(n=_today["kicks"])
    if not feed_state.get("authed"):
        why = _scrub(feed_state.get("error")) or "not connected"
        return "down", FEED_WORDS["down"].format(why=why[:WHY_MAX])
    if _quiet(now):
        return "quiet", FEED_WORDS["quiet"]
    last = feed_state.get("last_trade_ts") or 0.0
    age = str(int(round(now - last))) if last else "—"
    return "live", FEED_WORDS["live"].format(age=age)


def authed_since() -> Optional[float]:
    """⚡ 2026-11-11 (entry spec §3.1): the epoch of the CURRENT authentication while the socket is authed, else None.
    chart_maps.gajjala.break_watch keys its coverage on it — a changed value (a re-auth after a kick / drop) means the
    socket may have missed prints, so every symbol's coverage restarts at its next print. Reads state only."""
    return _link.get("auth_ts") if feed_state.get("authed") else None


def status_payload(*, tracked_n: int, admin: bool, events: bool = False, active_source: str = "massive_ws",
                   is_enabled: Optional[bool] = None, now: Optional[float] = None) -> dict:
    """The `/live/feed-status` body. `admin_word` and `events` only for admins; the key never appears."""
    now = time.time() if now is None else now
    _roll_day(now)
    st = dict(feed_state)
    st["tracked"] = int(tracked_n)
    st["active_source"] = active_source
    if st.get("last_trade_ts"):
        st["last_trade_age_s"] = round(now - st["last_trade_ts"], 1)
    if st.get("last_msg_ts"):
        st["last_msg_age_s"] = round(now - st["last_msg_ts"], 1)
    lo = now - KICKS_HOUR_SEC
    lags = sorted(_lag)
    p50 = _pctl(lags, 50)
    p99 = _pctl(lags, 99)
    last_kick = _link.get("last_kick_ts")
    st.update(
        kicks_1h=sum(1 for t in _kick_times if t >= lo),
        kicks_today=int(_today["kicks"]),
        last_kick_et=_et_iso(last_kick),
        last_kick_age_s=round(now - last_kick, 1) if last_kick else None,
        blind_s_today=round(float(_today["blind_s"]), 1),
        resume_s_last=_link.get("resume_s_last"),
        connected_since_et=_et_iso(_link.get("auth_ts")) if feed_state.get("authed") else None,
        lag_ms_p50=round(p50, 1) if p50 is not None else None,
        lag_ms_p99=round(p99, 1) if p99 is not None else None,
        msgs_per_s_1m=_msgs_per_s(now),
        hub_symbols=len(_hub_set()),
        subscribed_t=len(_subscribed_t),
    )
    state, word = state_word(now, is_enabled=is_enabled)
    st["state"] = state
    st["word"] = word
    if admin:
        st["admin_word"] = ADMIN_WORD.format(
            p50=("—" if p50 is None else int(round(p50))), kicks=int(_today["kicks"]),
            blind=int(round(float(_today["blind_s"]))))
        if events:
            st["events"] = list(_events)[-EVENTS_SERVED:]
    return _scrub_obj(st)


async def _await_auth(ws, timeout: float = 8.0) -> bool:
    """Block until Massive returns ``auth_success`` before we subscribe.

    Subscribing in the same instant as auth races the server's auth handler and
    silently drops part of the subscription (observed: 2 of 4 symbols never
    streamed). Polygon's protocol is auth → wait for auth_success → subscribe.
    """
    end = time.time() + timeout
    while time.time() < end:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, end - time.time()))
        except asyncio.TimeoutError:
            return False
        try:
            events = json.loads(raw)
        except Exception:
            continue
        for e in events if isinstance(events, list) else [events]:
            if e.get("ev") != "status":
                continue
            st = e.get("status")
            _note_status(st, e.get("message"), time.time())
            if st == "auth_success":
                feed_state["authed"] = True
                return True
            if st in ("auth_failed", "auth_timeout", "error", "max_connections"):
                feed_state["error"] = _scrub(f"{st}: {e.get('message')}")
                return False
    return False


async def _subscribe(ws, symbols: list[str], channels: list[str] | None = None) -> None:
    """Send subscribe frames for ``symbols`` across ``channels`` (default: the
    price channels in MASSIVE_WS_CHANNELS). Pass ``["Q"]`` for focus quotes."""
    chans = channels or MASSIVE_WS_CHANNELS
    syms = [s for s in symbols if s]
    if not syms:
        return
    for i in range(0, len(syms), _SUBSCRIBE_BATCH):
        chunk = syms[i : i + _SUBSCRIBE_BATCH]
        params = ",".join(f"{ch}.{s}" for s in chunk for ch in chans)
        await ws.send(json.dumps({"action": "subscribe", "params": params}))


async def _handle(raw, cache, tracked=None) -> None:
    """Route one raw WS frame (a JSON array of events).

    `tracked is None` → today's behaviour: every T → `cache.update`. Otherwise (the consumer always passes the UI's
    tracked set): a hub-watched symbol's print goes to the hub listener(s) FIRST (sync, no I/O), then a tracked
    symbol's print to `await cache.update` (unchanged payload); a print that is neither is dropped."""
    try:
        events = json.loads(raw)
    except Exception:
        return
    if not isinstance(events, list):
        return
    now = time.time()
    for e in events:
        if not isinstance(e, dict):
            continue
        ev = e.get("ev")
        _count_msg(now)
        if ev == "T":  # real-time trade
            sym = e.get("sym")
            if not sym or e.get("p") is None:
                continue
            feed_state["last_msg_ts"] = now
            feed_state["last_trade_ts"] = now
            feed_state["trades"] += 1
            _link["trades"] = int(_link.get("trades") or 0) + 1
            t_ms = e.get("t")
            if isinstance(t_ms, (int, float)) and not isinstance(t_ms, bool) and t_ms > 0:
                _lag.append(now * 1000.0 - float(t_ms))
            else:
                t_ms = None
            payload = {
                "price": e.get("p"),
                "volume": e.get("s"),
                "source": "massive_ws",
                "trade_ts": e.get("t"),
            }
            if tracked is None:
                await cache.update(sym, payload)
            else:
                if _listeners and sym in _hub_set():
                    conds = e.get("c")
                    pr = {"sym": sym, "p": e.get("p"), "s": e.get("s"),
                          "c": list(conds) if isinstance(conds, (list, tuple)) else [],
                          "t_ms": int(t_ms) if t_ms is not None else None, "recv": now, "trfi": "trfi" in e}
                    for fn in list(_listeners):
                        try:
                            fn(pr)
                        except Exception as exc:                # noqa: BLE001 — a listener never stops the read loop
                            log.warning("live_feed: listener failed on %s: %s", sym, type(exc).__name__)
                if sym in tracked:
                    await cache.update(sym, payload)
            # Phase 2: feed the accumulation tracker (focus symbols only). The
            # trade's `trfi` field (FINRA TRF id) marks an off-exchange/dark print.
            if accumulation.tracker.in_focus(sym):
                await accumulation.tracker.on_trade(
                    sym, e.get("p"), e.get("s"), is_dark=("trfi" in e), ts=now
                )
        elif ev == "Q":  # NBBO quote (focus symbols) — for buy/sell classification
            sym = e.get("sym")
            if sym:
                feed_state["last_msg_ts"] = now
                accumulation.tracker.on_quote(sym, e.get("bp"), e.get("ap"), now)
        elif ev == "A":  # per-second aggregate (only if "A" in MASSIVE_WS_CHANNELS)
            sym = e.get("sym")
            if not sym:
                continue
            feed_state["last_msg_ts"] = now
            payload = {"source": "massive_ws"}
            if e.get("c") is not None:
                payload["price"] = e.get("c")
            if e.get("op") is not None:
                payload["open"] = e.get("op")
            if e.get("v") is not None:
                payload["volume"] = e.get("v")
            if tracked is None or sym in tracked:
                await cache.update(sym, payload)
        elif ev == "status":
            st = e.get("status")
            _note_status(st, e.get("message"), now)
            if st == "auth_success":
                feed_state["authed"] = True
                log.info("Massive WS authenticated.")
            elif st in ("auth_failed", "error", "max_connections"):
                feed_state["error"] = _scrub(f"{st}: {e.get('message')}")
                log.error("Massive WS status %s — %s", st, _scrub(e.get("message")))


# The reconnect wait goes through this seam so the fake-socket tests can record it.
_sleep = asyncio.sleep


async def massive_ws_consumer(cache, tracked_symbols: set, subscribe_queue: "asyncio.Queue",
                              q_subscribe_queue: "asyncio.Queue | None" = None) -> None:
    """Maintain THE one authenticated Massive WS (account allows a single
    socket). Streams T trades into ``cache`` for every tracked symbol and Q
    quotes into the accumulation tracker for the bounded focus set. The hub's
    watch set rides the SAME socket (``watch`` / ``unwatch`` → this queue)."""
    global _queue
    _queue = subscribe_queue
    if _views.get("tracked") is None:
        _views["tracked"] = tracked_symbols
    key = stocks_key()
    if not key:
        log.warning("Massive WS: no stocks key configured — feed not started.")
        return
    backoff = 2
    while True:
        clean = False
        close_code = None
        exc_text = ""
        was_authed = False
        _link.update(conn_ts=None, trades=0)
        try:
            async with websockets.connect(MASSIVE_WS_URL, ping_interval=20, ping_timeout=20) as ws:
                now = time.time()
                _link.update(conn_ts=now, trades=0, kicked=False)
                _timeline("connect", now)
                feed_state.update(connected=True, authed=False, error=None)
                await ws.send(json.dumps({"action": "auth", "params": key}))
                if not await _await_auth(ws):
                    raise RuntimeError(f"Massive WS auth failed: {feed_state.get('error')}")
                _on_auth(time.time())
                # Subscribe ONLY after auth_success (covers first connect + reconnects): UI-tracked ∪ hub-watched,
                # each exactly once.
                syms = sorted(set(tracked_symbols) | set(_hub_set()))
                _subscribed_t.clear()
                await _subscribe(ws, syms)
                _subscribed_t.update(syms)
                feed_state["tracked"] = len(tracked_symbols)
                # Phase 2: Q (NBBO) for the bounded focus set on the SAME socket.
                focus = list(accumulation.tracker.focus)
                if focus:
                    await _subscribe(ws, focus, channels=["Q"])
                feed_state["focus"] = len(focus)
                log.info(
                    "Massive WS authenticated — %d symbols (T) + %d focus (Q).",
                    len(syms), len(focus),
                )
                backoff = 2

                async def pump_subs() -> None:
                    # ONE ordered control queue: str = today's subscribe; ("sub"|"unsub", sym) = the hub.
                    while True:
                        item = await subscribe_queue.get()
                        try:
                            await _send_control(ws, item, tracked_symbols)
                            feed_state["tracked"] = len(tracked_symbols)
                        except Exception:
                            await subscribe_queue.put(item)  # retry on next reconnect
                            raise

                async def pump_q() -> None:
                    while True:
                        sym = await q_subscribe_queue.get()
                        try:
                            await _subscribe(ws, [sym], channels=["Q"])
                            feed_state["focus"] = len(accumulation.tracker.focus)
                        except Exception:
                            await q_subscribe_queue.put(sym)
                            raise

                pumps = [asyncio.create_task(pump_subs())]
                if q_subscribe_queue is not None:
                    pumps.append(asyncio.create_task(pump_q()))
                try:
                    async for raw in ws:
                        await _handle(raw, cache, tracked_symbols)
                finally:
                    for p in pumps:
                        p.cancel()
                clean = True
                close_code = getattr(ws, "close_code", None)
                was_authed = bool(feed_state.get("authed"))
                feed_state.update(connected=False, authed=False)
        except Exception as exc:
            was_authed = bool(feed_state.get("authed"))
            exc_text = _scrub(str(exc)) or ""
            close_code = _close_code_of(exc)
            feed_state.update(connected=False, authed=False, error=exc_text[:140])
            feed_state["reconnects"] += 1
        # Wait before the next connect. Defaults reproduce today's waits: an authed drop or a kick → 30 s; a
        # failed connect → exponential backoff; a clean close that was not a kick → at once.
        wait = _on_drop(was_authed=was_authed, exc_text=exc_text, close_code=close_code,
                        backoff=backoff, clean=clean)
        if not clean:
            log.error("Massive WS error: %s — reconnecting in %ss", exc_text, wait)
            backoff = min(backoff * 2, 60)
        if wait > 0:
            await _sleep(wait)


async def massive_snapshot_poller(cache, tracked_symbols: set, bulk_snapshot) -> None:
    """Backfill day frame (open/high/low/prev_close/volume) from the bulk snapshot.

    ``bulk_snapshot`` is injected (``sepa.prices.bulk_snapshot``) to avoid a
    circular import. Never writes ``price`` — the live WS tick owns that.
    """
    # Maps a snapshot bar field → the QuoteCache field. prev_day_close →
    # prev_close is the one the SSE payload needs for a live percent move.
    field_map = (
        ("open", "open"),
        ("high", "high"),
        ("low", "low"),
        ("volume", "day_volume"),
        ("change_pct", "pct_change"),
        ("prev_day_close", "prev_close"),
        ("vwap", "vwap"),
    )
    while True:
        try:
            syms = list(tracked_symbols)
            if syms:
                snaps = await asyncio.to_thread(bulk_snapshot, syms)
                for sym, bar in (snaps or {}).items():
                    payload = {dst: bar.get(src) for src, dst in field_map if bar.get(src) is not None}
                    if payload:
                        await cache.update(sym, payload)
        except Exception as exc:
            log.warning("Massive snapshot poll error: %s", exc)
        await asyncio.sleep(SNAPSHOT_INTERVAL_SEC)
