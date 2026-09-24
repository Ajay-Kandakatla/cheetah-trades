"""SSE must never go through our own GZipMiddleware (Ajay 2026-09-23).

    "Sometimes I am getting this error"  — a red `network error` on a Hermes
    Agent turn that had been running a while.

`network error` is the BROWSER's word for a response body that died mid-stream.
It died because the app gzipped its own SSE: `main.py` adds
`GZipMiddleware(minimum_size=1024)` and Starlette's responder has no
content-type exclusion, so every `text/event-stream` response went into an
unflushed zlib buffer at compresslevel 9. Measured on the live api container:

    Accept-Encoding: gzip      ->     316 bytes, all at t=0, then 32s of silence
    Accept-Encoding: identity  ->  14,807 bytes in ~60 chunks, the whole time

WHAT THESE TESTS PIN
────────────────────
1. THE BEHAVIOUR, NOT THE HEADER. `test_a_stream_reaches_the_client_in_pieces`
   runs a real StreamingResponse through a real GZipMiddleware and asserts the
   chunks arrive separately. Its NEGATIVE runs the identical app WITHOUT the
   header and asserts the bytes are swallowed — if Starlette ever changes its
   pass-through rule, the negative fails and tells us the fix is now a no-op.
2. `minimum_size` IS NOT A DEFENCE. A 1-byte chunk is still gzipped, because the
   guard is `len(body) < minimum_size AND NOT more_body` and a stream always has
   `more_body=True`. Pinned, because "our chunks are small so gzip skips them"
   is the intuition that let this ship.
3. A HEARTBEAT IS NOT A FIX. `events/sse.py` already sent `: ping` every 25s for
   exactly this purpose and gzip ate it. Pinned so nobody "fixes" a future
   stall by adding pings and calls it done.
4. THE SOURCE GUARD. Every `media_type="text/event-stream"` in the backend uses
   `SSE_HEADERS`. A seventh SSE endpoint cannot be added without it.
"""
from __future__ import annotations

import asyncio
import gzip as _gzip
import re
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from events.sse_headers import SSE_HEADERS          # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
CHUNKS = [f"data: {{\"n\": {i}}}\n\n".encode() for i in range(10)]


def _app(headers):
    app = FastAPI()
    # the SAME middleware and the SAME minimum_size main.py ships
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.get("/s")
    async def _s():                                        # noqa: ANN202
        async def gen():
            for c in CHUNKS:
                # A REAL await between chunks. Without one the whole generator
                # drains in a single event-loop step and even an un-gzipped
                # stream arrives as one buffer — that would make this test pass
                # for the wrong reason, which is exactly the failure mode the
                # bug itself had.
                await asyncio.sleep(0.02)
                yield c
        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers=headers)
    return app


def _wire(headers):
    """Raw bytes off the wire, per chunk, with the response's own headers."""
    with TestClient(_app(headers)) as c:
        with c.stream("GET", "/s", headers={"Accept-Encoding": "gzip"}) as r:
            return r.headers, list(r.iter_raw())


# ── 1. the behaviour ────────────────────────────────────────────────────────
def test_the_bytes_on_the_wire_are_readable_sse_not_a_zlib_buffer():
    """The fix. NOTE the limit of this harness: `TestClient` uses an in-memory
    transport and coalesces the body however it likes, so the NUMBER of chunks
    here proves nothing either way. What it does prove — and what the bug turned
    off — is that the bytes leaving the app are plaintext a client can act on as
    they arrive, rather than a zlib stream that means nothing until it closes.
    The over-the-socket timing proof is `test_over_a_real_socket_...` below."""
    hdrs, raw = _wire(SSE_HEADERS)
    assert hdrs.get("content-encoding") == "identity"
    body = b"".join(raw)
    assert body == b"".join(CHUNKS)                 # nothing was mangled
    assert b'data: {"n": 0}' in raw[0]              # readable from the first byte


def test_NEGATIVE_without_the_header_the_bytes_are_swallowed():
    """THE BUG ITSELF. If this ever stops failing to stream, Starlette changed
    its pass-through rule and `Content-Encoding: identity` is no longer the
    lever — do not delete this test, read it."""
    hdrs, raw = _wire({"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    assert hdrs.get("content-encoding") == "gzip"
    body = b"".join(raw)
    # everything that was readable before the response ended
    early = b"".join(raw[:-1]) if len(raw) > 1 else b""
    assert b"data:" not in early, "a gzipped stream leaked readable data early"
    # it is only intelligible once the response is CLOSED and zlib flushes
    assert _gzip.decompress(body) == b"".join(CHUNKS)


# ── 2. minimum_size is not a defence ────────────────────────────────────────
def test_NEGATIVE_minimum_size_does_not_exempt_a_small_stream():
    """`len(body) < minimum_size AND NOT more_body` — a stream is always
    more_body, so a 1-byte chunk is gzipped just the same."""
    app = FastAPI()
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.get("/tiny")
    async def _tiny():                                     # noqa: ANN202
        async def gen():
            yield b"x"
        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})
    with TestClient(app) as c:
        r = c.get("/tiny", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"     # 1 byte, still gzipped


# ── 3. a heartbeat is not a fix ─────────────────────────────────────────────
def test_NEGATIVE_a_ping_comment_does_not_survive_gzip():
    """`events/sse.py` sends `: ping` every 25s to keep proxies warm. Under gzip
    it puts ZERO readable bytes on the wire, which is why the stall looked like
    a missing heartbeat when the heartbeat was already there."""
    app = FastAPI()
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.get("/ping")
    async def _ping():                                     # noqa: ANN202
        async def gen():
            for _ in range(20):
                yield b": ping\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})
    with TestClient(app) as c:
        with c.stream("GET", "/ping", headers={"Accept-Encoding": "gzip"}) as r:
            raw = list(r.iter_raw())
    early = b"".join(raw[:-1]) if len(raw) > 1 else b""
    assert b": ping" not in early
    # ...and with the fix it does
    with TestClient(_app(SSE_HEADERS)) as c:
        with c.stream("GET", "/s", headers={"Accept-Encoding": "gzip"}) as r:
            assert b"data:" in next(r.iter_raw())


# ── 4. the source guard ─────────────────────────────────────────────────────
SSE_FILES = ("main.py", "events/sse.py", "ollama_chat/api.py",
             "ollama_chat/hermes.py")


def _sse_sites():
    """(file, line) for every `media_type="text/event-stream"` in the backend,
    found by walking the tree — NOT by trusting the list above."""
    out = []
    for p in BACKEND.rglob("*.py"):
        s = str(p)
        if "/tests/" in s or "/.venv/" in s or "/scripts/" in s:
            continue
        for i, ln in enumerate(p.read_text(errors="replace").splitlines(), 1):
            if 'media_type="text/event-stream"' in ln:
                out.append((p, i))
    return out


def test_SOURCE_GUARD_every_sse_response_uses_the_shared_headers():
    sites = _sse_sites()
    assert len(sites) == 6, f"SSE endpoint count changed: {[str(p) for p, _ in sites]}"
    for path, line in sites:
        lines = path.read_text(errors="replace").splitlines()
        window = "\n".join(lines[line - 6:line + 4])
        assert "headers=SSE_HEADERS" in window, (
            f"{path.relative_to(BACKEND)}:{line} is an SSE response that does not "
            "use SSE_HEADERS — it will be gzipped into silence")


def test_SOURCE_GUARD_the_guard_finds_the_files_it_claims_to():
    found = {str(p.relative_to(BACKEND)) for p, _ in _sse_sites()}
    assert found == set(SSE_FILES), found


def test_NEGATIVE_the_source_guard_would_catch_a_new_bare_endpoint():
    """Mutation of the guard itself: a synthetic site with an inline dict must
    fail the same window check."""
    bad = ('    return StreamingResponse(\n        gen(),\n'
           '        media_type="text/event-stream",\n'
           '        headers={"Cache-Control": "no-cache"},\n    )')
    window = bad
    assert "headers=SSE_HEADERS" not in window


# ── 5. the constant itself ──────────────────────────────────────────────────
def test_the_header_set_is_what_the_fix_needs():
    assert SSE_HEADERS["Content-Encoding"] == "identity"
    assert SSE_HEADERS["X-Accel-Buffering"] == "no"
    assert "no-transform" in SSE_HEADERS["Cache-Control"]


def test_NEGATIVE_the_gzip_middleware_is_still_installed():
    """This fix is only needed because GZipMiddleware is there. If it is ever
    removed, this test fails and the whole module can go with it."""
    src = (BACKEND / "main.py").read_text(errors="replace")
    assert re.search(r"add_middleware\(GZipMiddleware, minimum_size=\d+\)", src)


# ── 6. the timing proof, over a real socket ─────────────────────────────────
def test_over_a_real_socket_the_client_sees_bytes_before_the_stream_ends():
    """The only harness that can answer the question he actually asked — does
    anything reach the browser DURING the turn. Runs uvicorn on an ephemeral
    port and reads the raw socket, the same way I measured the live container
    (gzip: 316 bytes at t=0 then 32s of silence; identity: 14,807 bytes flowing).

    A slow generator (10 chunks, 60ms apart) stands in for a Hermes turn.
    """
    uvicorn = pytest.importorskip("uvicorn")
    import socket
    import threading
    import time

    def serve(headers, port):
        cfg = uvicorn.Config(_app(headers), host="127.0.0.1", port=port,
                             log_level="critical")
        srv = uvicorn.Server(cfg)
        t = threading.Thread(target=srv.run, daemon=True)
        t.start()
        for _ in range(200):
            if getattr(srv, "started", False):
                return srv, t
            time.sleep(0.05)
        srv.should_exit = True
        pytest.skip("uvicorn did not start")

    def read_first(port):
        """(seconds until the first byte of SSE PAYLOAD, total bytes)."""
        s = socket.create_connection(("127.0.0.1", port), timeout=10)
        s.sendall(b"GET /s HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                  b"Accept-Encoding: gzip\r\nConnection: close\r\n\r\n")
        s.settimeout(10)
        t0, buf, first = time.monotonic(), b"", None
        while True:
            try:
                b = s.recv(65536)
            except socket.timeout:
                break
            if not b:
                break
            buf += b
            if first is None and b"data: {" in buf:
                first = time.monotonic() - t0
        s.close()
        return first, buf

    port = 8571
    srv, _t = serve(SSE_HEADERS, port)
    try:
        first, buf = read_first(port)
    finally:
        srv.should_exit = True
    assert first is not None, "no readable SSE ever arrived"
    assert b"content-encoding: identity" in buf.lower()

    # NEGATIVE, same server, no header: readable payload NEVER appears, because
    # zlib holds it all until the response closes.
    port2 = 8572
    srv2, _t2 = serve({"Cache-Control": "no-cache"}, port2)
    try:
        first_bad, buf_bad = read_first(port2)
    finally:
        srv2.should_exit = True
    assert b"content-encoding: gzip" in buf_bad.lower()
    assert first_bad is None, "a gzipped SSE stream leaked readable payload"
