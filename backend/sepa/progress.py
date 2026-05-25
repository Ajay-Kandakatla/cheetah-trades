"""Progress emitter — bridges sync scan code to async SSE stream.

Pattern: caller (FastAPI endpoint) creates an emitter on the request's event
loop. The emitter is passed to scan_universe / scan_universe_fast / etc. as a
keyword arg. Worker threads call `emitter.emit()` from inside the scanner;
emit() uses `loop.call_soon_threadsafe` to put events onto an asyncio.Queue.
The endpoint drains the queue via async iteration and yields SSE-formatted
strings to the client.

Event shape:
    {"type": str, "ts": float, ...payload}

Standard event types emitted by scanner.py:
    "phase"        — {phase: "rs"|"warming_names"|"scanning"|"enriching"|"writing"}
    "ticker"       — {current, total, symbol, analyzed, candidate_count}
    "candidate"    — {symbol, score, rating, rank}  fired when a hit is found
    "enrich"       — {current, total, symbol}      catalyst/insider pass
    "log"          — {level, message}              freeform info/warn
    "done"         — {result: <full scan payload>} terminal success
    "error"        — {message}                     terminal failure
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Optional

log = logging.getLogger("sepa.progress")


class ProgressEmitter:
    """Thread-safe progress emitter rooted on a single asyncio loop.

    A no-op variant exists for code paths that don't want to instrument:
    pass `emitter=None` and the scanner skips emit calls entirely.
    """

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self.loop = loop or asyncio.get_event_loop()
        self.queue: asyncio.Queue = asyncio.Queue()
        self._closed = False

    def emit(self, event_type: str, **payload: Any) -> None:
        """Called from any thread. Coalesces into the queue on the main loop."""
        if self._closed:
            return
        ev = {"type": event_type, "ts": time.time(), **payload}
        try:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, ev)
        except RuntimeError:
            # Loop is closed — caller already disconnected. Safe to drop.
            pass

    def close(self) -> None:
        """Sentinel to terminate the async stream cleanly."""
        if self._closed:
            return
        self._closed = True
        try:
            self.loop.call_soon_threadsafe(self.queue.put_nowait, None)
        except RuntimeError:
            pass

    async def stream(self, *, heartbeat_sec: float = 15.0) -> AsyncIterator[dict]:
        """Async iterator over events. Yields dict events; ends on close().

        Inserts heartbeat events every `heartbeat_sec` seconds when idle, so
        proxies / browsers don't drop the connection during long quiet phases
        (e.g. mid-scan when one ticker is taking 30s).
        """
        while True:
            try:
                ev = await asyncio.wait_for(self.queue.get(), timeout=heartbeat_sec)
            except asyncio.TimeoutError:
                yield {"type": "heartbeat", "ts": time.time()}
                continue
            if ev is None:
                return
            yield ev
