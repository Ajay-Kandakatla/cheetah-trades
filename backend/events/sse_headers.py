"""The ONE header set every Server-Sent-Events response in this app must carry.

WHY THIS MODULE EXISTS (2026-09-23)
───────────────────────────────────
Ajay, on the /ollama page in Hermes Agent mode: *"Sometimes I am getting this
error"* — a red `network error` on a turn that had been running a while.

`network error` is not a string this app owns. It is the browser's own
`TypeError` for a response body that died mid-stream, printed verbatim by
`OllamaChat.tsx`. The stream died because **the app was gzipping its own SSE**.

`main.py` adds `GZipMiddleware(minimum_size=1024)` (2026-08-16, for the ~295 KB
/chart-maps JSON). Starlette's `GZipResponder` has no content-type exclusion, and
its small-response guard is `len(body) < minimum_size and not more_body` — a
STREAMING response always has `more_body=True`, so it falls straight through to
the streaming branch no matter how small each chunk is. That branch writes every
chunk into a `GzipFile` at `compresslevel=9` **and never flushes**. zlib holds
~250 KB before it emits anything, and no SSE turn on this app reaches that.

Measured on the live api container, 2026-09-23, `GET /events`:

    Accept-Encoding: gzip      ->     316 bytes, all at t=0.0s, then 32s of silence
    Accept-Encoding: identity  ->  14,807 bytes in ~60 chunks, flowing the whole time

So the browser got the gzip header and nothing else for the entire turn. Any idle
timeout anywhere in the Cloudflare → tunnel → nginx → oauth2-proxy path then cut
the connection, and the page printed the browser's word for it.

THE TRAP THAT MAKES THIS WORTH A MODULE: **a heartbeat does not fix it.**
`events/sse.py` already emits a `: ping` comment every 25 s for exactly this
purpose — and gzip swallowed it whole. Every one of the six SSE endpoints also
already sets `X-Accel-Buffering: no` and `Cache-Control: no-cache`, because their
authors knew about proxy buffering. None of that helps when the buffering happens
*inside our own middleware stack*, before the bytes ever reach a proxy.

THE FIX: declare `Content-Encoding: identity` on the response. Starlette 0.41.3's
`GZipResponder.__call__` reads the outgoing headers once
(`self.content_encoding_set = "content-encoding" in headers`) and, when one is
already set, passes every body chunk straight through untouched. So this turns
gzip off for SSE **only**, and the /chart-maps JSON win is untouched.

`identity` is the RFC 9110 token for "no transformation applied". It is a
truthful declaration, not a trick.
"""
from __future__ import annotations

# `Content-Encoding` is the one that fixes the bug; the other three were already
# on all six endpoints and are kept so this dict is a drop-in for what they had.
SSE_HEADERS = {
    # Opt OUT of our own GZipMiddleware. Without this the whole stream is one
    # unflushed zlib buffer and the client sees nothing until the response ends.
    # See the module docstring for the measurement.
    "Content-Encoding": "identity",
    # nginx honours this; it does not cover the gzip above.
    "X-Accel-Buffering": "no",
    # Cloudflare and the browser's own cache. `no-transform` is the RFC 9111
    # directive that forbids an intermediary re-compressing or otherwise
    # rewriting the body — the same class of damage as the gzip above, one hop
    # further out. `events/sse.py` already carried it and the other five did
    # not; taking the stronger of the two is the whole point of one constant.
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
}

__all__ = ["SSE_HEADERS"]
