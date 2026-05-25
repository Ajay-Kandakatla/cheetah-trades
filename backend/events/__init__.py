"""In-process SSE event bus.

Anything in the backend can `publish(type, payload)` and every connected
browser tab on `GET /events` receives it. Replaces poll-every-30s loops.

See bus.py for the pub/sub primitive and sse.py for the HTTP endpoint.
"""
from .bus import publish, publish_throttled, subscribe, unsubscribe  # noqa: F401
from .sse import router, set_symbol_registrar  # noqa: F401
