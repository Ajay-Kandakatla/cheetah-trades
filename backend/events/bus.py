"""In-process pub/sub for SSE fan-out.

Every connected SSE client gets its own bounded asyncio.Queue. Publishers
call `publish(type, payload)` from anywhere (sync or async); the bus
fan-outs to every queue without blocking the caller.

Why bounded? A slow/stuck client must not balloon memory or back-pressure
publishers. If a queue is full we drop the OLDEST event for that client
(it'll resync next time the page reloads). The publish path is therefore
O(num_subscribers) and never awaits — safe to call from any thread via
`call_soon_threadsafe`.

Single-process scope. If we ever fork uvicorn workers or split out a
second container, swap this for Redis pub/sub — the publish/subscribe
surface stays the same.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

log = logging.getLogger("events.bus")

# Per-subscriber queue. Bounded so one slow tab can't OOM the API.
_QUEUE_MAX = 256

# Set of live subscriber queues. We use a set (not list) so unsubscribe
# is O(1) and double-unsubscribe is harmless.
_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

# We snapshot the event loop on first publish so threadpool callers
# (e.g. a sync route running scan_symbol) can hand events back to the
# loop safely. FastAPI creates one loop per worker, captured at startup.
_loop: asyncio.AbstractEventLoop | None = None


def _bind_loop() -> asyncio.AbstractEventLoop | None:
    """Best-effort grab of the running loop. Cached after first hit."""
    global _loop
    if _loop is not None:
        return _loop
    try:
        _loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop in this thread — caller is sync code outside an async
        # context. publish() will no-op rather than crash.
        return None
    return _loop


def subscribe() -> asyncio.Queue[dict[str, Any]]:
    """Allocate a new subscriber queue and register it. The SSE handler
    awaits on this queue and writes each event out to the wire."""
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_QUEUE_MAX)
    _subscribers.add(q)
    _bind_loop()
    log.info("events: subscribe — %d total", len(_subscribers))
    return q


def unsubscribe(q: asyncio.Queue[dict[str, Any]]) -> None:
    """Called from the SSE handler's finally block when the client
    disconnects. Idempotent."""
    _subscribers.discard(q)
    log.info("events: unsubscribe — %d total", len(_subscribers))


def _enqueue(envelope: dict[str, Any]) -> None:
    """Loop-thread side of publish. Drops oldest on full queue so a
    stuck consumer cannot stall the bus."""
    for q in list(_subscribers):
        try:
            q.put_nowait(envelope)
        except asyncio.QueueFull:
            try:
                _ = q.get_nowait()           # drop oldest
                q.put_nowait(envelope)
                log.warning("events: dropped oldest event for slow subscriber")
            except Exception:
                pass


# Per-(type, key) timestamp of the last successful publish. Used by
# publish_throttled to dampen high-frequency streams (Finnhub WS can
# fire dozens of trades/second per symbol — we don't want to flood
# every SSE client with redundant frames).
_last_publish_ts: dict[tuple[str, str], float] = {}


def publish_throttled(
    type_: str,
    key: str,
    payload: dict[str, Any] | None = None,
    *,
    min_interval_s: float = 0.5,
) -> None:
    """publish() but coalesces calls with the same (type_, key) inside
    a `min_interval_s` window. Quote streams use this so we send at most
    ~2 updates/second per symbol regardless of WS tick rate.

    Trade-off: callers lose intra-window updates. That's fine for
    quotes (last-write-wins is what the UI shows anyway), and not
    appropriate for event-style messages where every payload matters
    (use plain publish() for those).
    """
    if not _subscribers:
        return
    import time as _t
    now = _t.time()
    last = _last_publish_ts.get((type_, key), 0.0)
    if now - last < min_interval_s:
        return
    _last_publish_ts[(type_, key)] = now
    publish(type_, payload)


def publish(type_: str, payload: dict[str, Any] | None = None) -> None:
    """Fan-out a single event to every subscriber.

    Safe to call from:
      - async handlers (direct path)
      - threadpool callers (via call_soon_threadsafe)
      - sync code in the loop thread (also direct path)

    If there's no event loop yet (e.g. import-time call), we drop the
    event silently — the bus isn't ready.
    """
    if not _subscribers:
        return                               # nobody listening; cheap exit
    envelope = {
        "type":    type_,
        "ts":      time.time(),
        "payload": payload or {},
    }
    loop = _bind_loop()
    if loop is None:
        return
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:
        _enqueue(envelope)                   # already on loop thread
    else:
        loop.call_soon_threadsafe(_enqueue, envelope)
