"""GET /events — server-sent events stream.

One persistent connection per browser tab. The browser's built-in
EventSource handles reconnect automatically (default 3s delay), so this
handler only has to:

  1. Allocate a subscriber queue.
  2. Yield SSE frames as events arrive.
  3. Emit a heartbeat every HEARTBEAT_S seconds so nginx / Cloudflare
     don't kill the stream as idle.
  4. Cleanly unsubscribe on disconnect.

Frame format follows the SSE spec — `event:` line for type, `data:` line
for the JSON envelope. EventSource on the frontend dispatches to handlers
by the `event:` field, so the bus event type and the SSE event name are
the same string.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .bus import subscribe, unsubscribe

log = logging.getLogger("events.sse")

router = APIRouter()

# Pluggable callback that knows how to start streaming a symbol upstream
# (Finnhub WS subscribe + REST warm). Set from main.py at startup —
# keeps events/ from importing main and creating a circular dependency.
SymbolRegistrar = Callable[[list[str]], Awaitable[Any]]
_symbol_registrar: Optional[SymbolRegistrar] = None


def set_symbol_registrar(fn: SymbolRegistrar) -> None:
    """Called once at startup. Whatever async function handles symbol
    subscription on the main app is plugged in here, so /events/subscribe
    can route requests through it without a hard import."""
    global _symbol_registrar
    _symbol_registrar = fn

# Idle keepalive. Cloudflare's free tier closes idle streams at 100s and
# nginx's default proxy_read_timeout is 60s — 25s gives us a comfortable
# safety margin while staying off the wire 99% of the time.
HEARTBEAT_S = 25.0


def _frame(event_type: str, data: dict) -> bytes:
    """Encode one SSE event. Newlines in the data are escaped by
    json.dumps so the frame stays single-line, which is what
    EventSource expects."""
    body = json.dumps(data, separators=(",", ":"), default=str)
    return f"event: {event_type}\ndata: {body}\n\n".encode("utf-8")


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    """Stream bus events to the caller.

    Returns a chunked text/event-stream. Lifetime = the TCP connection;
    EventSource will reconnect on its own if the stream drops.
    """

    async def stream():
        q = subscribe()
        # Tell the client the stream is live — also flushes proxy
        # buffers so the first real event isn't delayed.
        yield b": connected\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    # asyncio.wait_for gives us heartbeat-on-timeout
                    # without a separate timer task.
                    evt = await asyncio.wait_for(q.get(), timeout=HEARTBEAT_S)
                except asyncio.TimeoutError:
                    # Comment line — ignored by EventSource but keeps
                    # the TCP connection warm.
                    yield b": ping\n\n"
                    continue
                yield _frame(evt["type"], evt)
        except asyncio.CancelledError:
            # Client disconnected mid-await. Normal shutdown path.
            pass
        except Exception as e:
            log.exception("events: stream error: %s", e)
        finally:
            unsubscribe(q)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            # Disable buffering on intermediate proxies. The
            # X-Accel-Buffering header is honored by nginx; the
            # Cache-Control directive covers Cloudflare and the
            # browser's own cache.
            "Cache-Control":      "no-cache, no-transform",
            "X-Accel-Buffering":  "no",
            "Connection":         "keep-alive",
        },
    )


@router.post("/events/subscribe")
async def events_subscribe(payload: dict) -> dict:
    """Register interest in a set of symbols.

    The frontend posts the symbols visible on the current page (e.g. the
    SEPA card list or the open ticker page). The backend pushes those
    into the Finnhub WS subscription, so every cache.update for them
    fans out as a `quote.update` SSE frame.

    Idempotent — re-posting the same symbols is a no-op. We deliberately
    do NOT track per-client interest in v2: with one user and a bounded
    universe (watchlist + visible SEPA cards), the cost of broadcasting
    every symbol to every tab is negligible, and skipping the per-client
    registry keeps the connection stateless.

    Request:  {"symbols": ["NVDA","MU",...]}
    Response: {"ok": true, "registered": 47}
    """
    raw = payload.get("symbols") or []
    if not isinstance(raw, list):
        return {"ok": False, "reason": "symbols must be a list"}
    symbols = [str(s).upper().strip() for s in raw if s and isinstance(s, str)]
    # Hard cap — defends against a runaway client (or malicious request)
    # adding thousands of symbols to the Finnhub feed.
    symbols = list(dict.fromkeys(symbols))[:300]
    if not symbols:
        return {"ok": True, "registered": 0}

    if _symbol_registrar is None:
        # Bus is up but main hasn't wired the registrar yet — happens
        # only during the brief window between FastAPI startup and
        # lifespan completion. Symbols still flow if they're in
        # DEFAULT_SYMBOLS; the rest get picked up on the next post.
        log.warning("events: /subscribe called before registrar set")
        return {"ok": False, "reason": "not ready"}

    try:
        await _symbol_registrar(symbols)
    except Exception as e:
        log.exception("events: symbol registrar failed: %s", e)
        return {"ok": False, "reason": str(e)}

    return {"ok": True, "registered": len(symbols)}
