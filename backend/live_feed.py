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
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time

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
# The account allows only ONE concurrent WS connection and the server takes
# ~20-60s to release a dropped one. Reconnecting sooner just trips
# "max_connections" (1008), so after an authenticated drop we wait this cooldown.
_RECONNECT_COOLDOWN = float(os.getenv("MASSIVE_WS_RECONNECT_COOLDOWN", "30"))

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


def enabled() -> bool:
    """Whether the Massive WS feed should be the live-quote source."""
    v = os.getenv("MASSIVE_WS_ENABLED", "auto").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("1", "true", "yes", "on"):
        return True
    return bool(stocks_key())  # auto: on when a stocks key exists


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
            if st == "auth_success":
                feed_state["authed"] = True
                return True
            if st in ("auth_failed", "auth_timeout", "error", "max_connections"):
                feed_state["error"] = f"{st}: {e.get('message')}"
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


async def _handle(raw, cache) -> None:
    """Route one raw WS frame (a JSON array of events) into the QuoteCache."""
    try:
        events = json.loads(raw)
    except Exception:
        return
    if not isinstance(events, list):
        return
    now = time.time()
    for e in events:
        ev = e.get("ev")
        if ev == "T":  # real-time trade
            sym = e.get("sym")
            if not sym or e.get("p") is None:
                continue
            feed_state["last_msg_ts"] = now
            feed_state["last_trade_ts"] = now
            feed_state["trades"] += 1
            await cache.update(
                sym,
                {
                    "price": e.get("p"),
                    "volume": e.get("s"),
                    "source": "massive_ws",
                    "trade_ts": e.get("t"),
                },
            )
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
            await cache.update(sym, payload)
        elif ev == "status":
            st = e.get("status")
            if st == "auth_success":
                feed_state["authed"] = True
                log.info("Massive WS authenticated.")
            elif st in ("auth_failed", "error", "max_connections"):
                feed_state["error"] = f"{st}: {e.get('message')}"
                log.error("Massive WS status %s — %s", st, e.get("message"))


async def massive_ws_consumer(cache, tracked_symbols: set, subscribe_queue: "asyncio.Queue",
                              q_subscribe_queue: "asyncio.Queue | None" = None) -> None:
    """Maintain THE one authenticated Massive WS (account allows a single
    socket). Streams T trades into ``cache`` for every tracked symbol and Q
    quotes into the accumulation tracker for the bounded focus set."""
    key = stocks_key()
    if not key:
        log.warning("Massive WS: no stocks key configured — feed not started.")
        return
    backoff = 2
    while True:
        try:
            async with websockets.connect(MASSIVE_WS_URL, ping_interval=20, ping_timeout=20) as ws:
                feed_state.update(connected=True, authed=False, error=None)
                await ws.send(json.dumps({"action": "auth", "params": key}))
                if not await _await_auth(ws):
                    raise RuntimeError(f"Massive WS auth failed: {feed_state.get('error')}")
                # Subscribe ONLY after auth_success (covers first connect + reconnects).
                await _subscribe(ws, list(tracked_symbols))
                feed_state["tracked"] = len(tracked_symbols)
                # Phase 2: Q (NBBO) for the bounded focus set on the SAME socket.
                focus = list(accumulation.tracker.focus)
                if focus:
                    await _subscribe(ws, focus, channels=["Q"])
                feed_state["focus"] = len(focus)
                log.info(
                    "Massive WS authenticated — %d symbols (T) + %d focus (Q).",
                    len(tracked_symbols), len(focus),
                )
                backoff = 2

                async def pump_subs() -> None:
                    while True:
                        sym = await subscribe_queue.get()
                        try:
                            await _subscribe(ws, [sym])
                            feed_state["tracked"] = len(tracked_symbols)
                        except Exception:
                            await subscribe_queue.put(sym)  # retry on next reconnect
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
                        await _handle(raw, cache)
                finally:
                    for p in pumps:
                        p.cancel()
        except Exception as exc:
            was_authed = feed_state.get("authed")
            feed_state.update(connected=False, authed=False, error=str(exc)[:140])
            feed_state["reconnects"] += 1
            # One-connection limit: the server holds a dropped socket ~20-60s, so
            # after an authed drop (or an explicit max_connections) wait the
            # cooldown before retrying — reconnecting sooner just 1008s again.
            cooling = was_authed or "max_connections" in str(exc).lower()
            wait = _RECONNECT_COOLDOWN if cooling else backoff
            log.error("Massive WS error: %s — reconnecting in %ss", exc, wait)
            await asyncio.sleep(wait)
            backoff = min(backoff * 2, 60)


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
