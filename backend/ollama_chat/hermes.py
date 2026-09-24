"""Hermes Agent bridge — the /ollama page's **Agent** mode. Ajay only.

Ajay 2026-09-14: *"Can you let me connect it via the hermes setup so I can
chat with it and make it do things for me via the chat?"*

WHAT HERMES IS ON HIS MAC (measured, not assumed)
─────────────────────────────────────────────────
Hermes Agent v0.21.1 at ``~/.hermes/hermes-agent``, model
``huihui_ai/Qwen3.8-abliterated:27b`` through Ollama's OpenAI-compatible
endpoint, toolsets ``hermes-cli`` + ``web``, terminal backend ``local`` — so
"do things" means Hermes runs shell commands on this machine, browses, edits
files, remembers across sessions. That is exactly what he asked for and
exactly why the gate on this router is the strict primary-admin address.

``hermes serve`` is the JSON-RPC/WebSocket backend the Hermes desktop app
uses. I installed it as a LaunchAgent (``~/Library/LaunchAgents/
ai.hermes.serve.plist``, RunAtLoad + KeepAlive, 127.0.0.1:9119) so it is up
after every login, like Ollama.

THE WIRE (probed from inside the api container, 2026-09-14)
───────────────────────────────────────────────────────────
* ``ws://…:9119/api/ws?token=<HERMES_DASHBOARD_SESSION_TOKEN>``. Newline-
  delimited JSON-RPC 2.0 both ways; the server sends ``gateway.ready`` right
  after accept. Events arrive as ``{"method":"event","params":{"type",
  "session_id","payload"}}``.
* TWO GUARDS a container must satisfy. The DNS-rebinding check wants a
  loopback ``Host`` header, and the peer check wants a loopback peer. Docker
  Desktop presents the container's connection to the host from 127.0.0.1, so
  the peer passes; the Host header is our job — the URI stays
  ``ws://127.0.0.1:<port>`` while the socket dials ``host.docker.internal``
  (websockets' ``host=``/``port=`` override). A plain
  ``ws://host.docker.internal:9119`` is refused with HTTP 403. Measured.
* ``session.create`` → ``{session_id (runtime), stored_session_id, …}``.
  ``session.resume {session_id: <stored>}`` returns the SAME runtime id while
  the server still holds it, a fresh one after a restart — so the browser
  keeps the stored id and every turn resumes it. A NEW connection may submit
  to a runtime id another connection created and receives its events, so one
  socket per turn is enough; nothing has to stay open between turns.
* ``image.attach_bytes {session_id, content_base64, filename}`` queues an
  image for the next ``prompt.submit``; the model answered "Blue" to a blue
  PNG through this path, so vision survives Hermes's OpenAI-shaped call.
* ``prompt.submit {session_id, text}`` → ``{"status":"streaming"}`` then
  ``thinking.delta`` / ``reasoning.delta`` / ``message.delta`` /
  ``tool.generating`` / ``tool.start`` / ``tool.complete`` /
  ``approval.request`` / ``status.update`` … / ``message.complete`` (final
  ``text`` + ``usage``) or ``turn.error``.
* ``session.interrupt {session_id}`` → ``{"status":"interrupted"}`` and a
  ``message.complete`` with empty text. Used when the browser disconnects.
* ``approval.respond {session_id, request_id, choice, all}`` — his config is
  not in approval mode today (the terminal ran without asking), so this path
  is wired and unit-tested but NOT exercised against a live Hermes.

WHAT THE PAGE GETS (SSE, one JSON object per ``data:`` line)
────────────────────────────────────────────────────────────
    {"session": {"session_id", "stored_session_id"}}   first, always
    {"thinking": text}   {"delta": text}
    {"tool_generating": name}
    {"tool_start": {"tool_id","name","context","args"}}
    {"tool_done":  {"tool_id","name","duration_s","result"}}   result capped
    {"approval": {...request_id, command, choices...}}
    {"status": {"kind","text"}}
    {"done": {"text","usage","status"}}      final text is authoritative
    {"error": message}

The token never leaves the server (it is a query parameter on a loopback
socket the container opens) and is never logged.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncIterator, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from websockets.legacy.client import connect as ws_connect

from .api import (MAX_IMAGE_B64_BYTES, MAX_IMAGES_PER_MESSAGE, _DATA_URL,
                  require_primary_admin)
from events.sse_headers import SSE_HEADERS

log = logging.getLogger("ollama_chat.hermes")
router = APIRouter()

DEFAULT_BASE_URL = "http://host.docker.internal:9119"
TOKEN_ENV = "HERMES_WS_TOKEN"

READY_TIMEOUT_SEC = 10.0
RPC_TIMEOUT_SEC = 60.0
# A tool-heavy turn (build something, browse, run tests) can legitimately run
# for many minutes. nginx's /api/ read timeout is 1800 s; stay under it.
TURN_TIMEOUT_SEC = float(os.getenv("HERMES_TURN_TIMEOUT", "1700"))
TOOL_RESULT_MAX = 4000
TOOL_ARGS_MAX = 2000
APPROVAL_CHOICES = ("once", "session", "always", "deny")

THINKING_EVENTS = frozenset({"thinking.delta", "reasoning.delta"})
TERMINAL_EVENTS = frozenset({"message.complete", "turn.error"})


def base_url() -> str:
    return (os.getenv("HERMES_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def token() -> str:
    return (os.getenv(TOKEN_ENV) or "").strip()


def ws_target() -> tuple[str, str, int]:
    """``(uri, dial_host, dial_port)``.

    The URI carries a LOOPBACK host on purpose — Hermes rejects any other
    ``Host`` header (DNS-rebinding guard) — while the TCP dial goes to the
    real host from HERMES_BASE_URL. See the module docstring."""
    u = urlparse(base_url())
    host = u.hostname or "127.0.0.1"
    port = u.port or 9119
    return f"ws://127.0.0.1:{port}/api/ws?token={token()}", host, port


class HermesError(RuntimeError):
    pass


def _truncate(v: Any, n: int) -> Any:
    if isinstance(v, str):
        return v if len(v) <= n else v[:n] + f"… [{len(v) - n} more chars]"
    try:
        s = json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        s = str(v)
    return v if len(s) <= n else s[:n] + "…"


# ---------------------------------------------------------------------------
# Connection: one reader task, request/response by id, events on a queue
# ---------------------------------------------------------------------------
class Conn:
    def __init__(self, ws):
        self.ws = ws
        self._rid = 0
        self._futs: dict[int, asyncio.Future] = {}
        self.events: asyncio.Queue = asyncio.Queue()
        self.error: Optional[BaseException] = None
        self._reader = asyncio.create_task(self._read())

    async def _read(self) -> None:
        try:
            async for raw in self.ws:
                try:
                    m = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(m, dict):
                    continue
                if "method" not in m and "id" in m:
                    fut = self._futs.pop(m["id"], None)
                    if fut is not None and not fut.done():
                        fut.set_result(m)
                elif m.get("method") == "event":
                    await self.events.put(m.get("params") or {})
        except Exception as exc:                                   # noqa: BLE001
            self.error = exc
        finally:
            await self.events.put(None)                            # sentinel: socket gone
            for fut in self._futs.values():
                if not fut.done():
                    fut.set_exception(HermesError("connection closed"))

    async def call(self, method: str, params: dict, timeout: float = RPC_TIMEOUT_SEC) -> dict:
        self._rid += 1
        rid = self._rid
        fut = asyncio.get_running_loop().create_future()
        self._futs[rid] = fut
        await self.ws.send(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}))
        try:
            m = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            self._futs.pop(rid, None)
            raise HermesError(f"{method}: no reply from Hermes in {int(timeout)}s")
        if m.get("error"):
            err = m["error"]
            raise HermesError(f"{method}: {err.get('message') if isinstance(err, dict) else err}")
        return m.get("result") or {}

    async def wait_ready(self, timeout: float = READY_TIMEOUT_SEC) -> dict:
        end = time.monotonic() + timeout
        while True:
            left = end - time.monotonic()
            if left <= 0:
                raise HermesError(f"no gateway.ready from Hermes in {int(timeout)}s")
            try:
                ev = await asyncio.wait_for(self.events.get(), left)
            except asyncio.TimeoutError:
                raise HermesError(f"no gateway.ready from Hermes in {int(timeout)}s")
            if ev is None:
                raise HermesError("connection closed before gateway.ready")
            if ev.get("type") == "gateway.ready":
                return ev.get("payload") or {}

    async def close(self) -> None:
        self._reader.cancel()
        try:
            await self.ws.close()
        except Exception:                                          # noqa: BLE001
            pass


async def open_conn() -> Conn:
    if not token():
        raise HermesError(f"{TOKEN_ENV} is not set — copy HERMES_DASHBOARD_SESSION_TOKEN from ~/.hermes/.env into backend/.env")
    uri, host, port = ws_target()
    try:
        ws = await ws_connect(uri, host=host, port=port, max_size=32 * 1024 * 1024,
                              open_timeout=10, ping_interval=20, ping_timeout=20)
    except OSError as exc:
        raise HermesError(f"Hermes backend not reachable at {host}:{port} — "
                          f"launchctl kickstart gui/$(id -u)/ai.hermes.serve ({type(exc).__name__})") from exc
    except Exception as exc:                                       # noqa: BLE001
        code = getattr(exc, "status_code", None)
        if code in (401, 403):
            raise HermesError(f"Hermes refused the socket (HTTP {code}) — "
                              "token mismatch or a non-loopback Host/peer") from exc
        raise HermesError(f"{type(exc).__name__}: {exc}"[:200]) from exc
    return Conn(ws)


# ---------------------------------------------------------------------------
# Request shapes
# ---------------------------------------------------------------------------
class AgentTurn(BaseModel):
    text: str = ""
    session_id: Optional[str] = None          # the STORED id the browser keeps
    images: Optional[list[str]] = None
    cwd: Optional[str] = None


class Approve(BaseModel):
    session_id: str                            # runtime id from the session event
    request_id: str
    choice: str = "once"


class Interrupt(BaseModel):
    session_id: str


def _clean_images(images: Optional[list[str]]) -> list[str]:
    out = []
    for raw in images or []:
        s = (raw or "").strip()
        if not s:
            continue
        if _DATA_URL.match(s):
            raise HTTPException(400, "images must be raw base64, not a data: URL")
        if len(s) > MAX_IMAGE_B64_BYTES:
            raise HTTPException(413, "image too large")
        out.append(s)
    if len(out) > MAX_IMAGES_PER_MESSAGE:
        raise HTTPException(400, f"more than {MAX_IMAGES_PER_MESSAGE} images on one message")
    return out


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/hermes/me")
async def hermes_me(email: str = Depends(require_primary_admin)):
    """Reachability probe for the page header. Never raises — the page shows
    the reason instead of a broken state."""
    status = {"ok": True, "base_url": base_url(), "reachable": False,
              "token_set": bool(token()), "reason": None, "heartbeat": None}
    conn = None
    try:
        conn = await open_conn()
        ready = await conn.wait_ready()
        status["reachable"] = True
        status["heartbeat"] = ready.get("heartbeat")
    except HermesError as exc:
        status["reason"] = str(exc)
    except Exception as exc:                                       # noqa: BLE001
        status["reason"] = f"{type(exc).__name__}: {exc}"[:200]
    finally:
        if conn is not None:
            await conn.close()
    return JSONResponse(status)


async def _turn(body: AgentTurn, images: list[str], request: Request) -> AsyncIterator[bytes]:
    def ev(obj: dict) -> bytes:
        return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")

    conn: Optional[Conn] = None
    sid: Optional[str] = None
    try:
        conn = await open_conn()
        await conn.wait_ready()

        # Resume the stored session when the browser has one; fall back to a
        # fresh session if Hermes no longer knows it (deleted, pruned).
        res: dict = {}
        if body.session_id:
            try:
                res = await conn.call("session.resume", {"session_id": body.session_id})
            except HermesError as exc:
                log.info("hermes resume failed (%s) — creating a new session", exc)
                res = {}
        if not res.get("session_id"):
            params: dict = {"cols": 120}
            if body.cwd:
                params["cwd"] = body.cwd
            res = await conn.call("session.create", params)
        sid = str(res.get("session_id") or "")
        stored = str(res.get("stored_session_id") or (res.get("info") or {}).get("stored_session_id")
                     or body.session_id or "")
        info = res.get("info") or {}
        yield ev({"session": {"session_id": sid, "stored_session_id": stored,
                              "model": info.get("model"), "cwd": info.get("cwd"),
                              "tools": info.get("tools"), "approval_mode": info.get("approval_mode")}})

        for i, b64 in enumerate(images, 1):
            await conn.call("image.attach_bytes",
                            {"session_id": sid, "content_base64": b64, "filename": f"cheetah_{i}.png"})

        await conn.call("prompt.submit", {"session_id": sid, "text": body.text})

        deadline = time.monotonic() + TURN_TIMEOUT_SEC
        while True:
            if await request.is_disconnected():
                # The browser hit Stop or closed the tab: free the GPU.
                try:
                    await conn.call("session.interrupt", {"session_id": sid}, timeout=10)
                except Exception:                                  # noqa: BLE001
                    pass
                return
            left = deadline - time.monotonic()
            if left <= 0:
                yield ev({"error": f"turn exceeded {int(TURN_TIMEOUT_SEC)}s — interrupted"})
                try:
                    await conn.call("session.interrupt", {"session_id": sid}, timeout=10)
                except Exception:                                  # noqa: BLE001
                    pass
                return
            try:
                e = await asyncio.wait_for(conn.events.get(), min(1.0, left))
            except asyncio.TimeoutError:
                continue
            if e is None:
                yield ev({"error": "Hermes closed the connection mid-turn"
                          + (f" ({type(conn.error).__name__})" if conn.error else "")})
                return
            ty = e.get("type") or ""
            esid = e.get("session_id")
            if esid and sid and esid != sid:
                continue                                           # another session's chatter
            pl = e.get("payload")
            pd = pl if isinstance(pl, dict) else {}
            if ty == "message.delta":
                if pd.get("text"):
                    yield ev({"delta": pd["text"]})
            elif ty in THINKING_EVENTS:
                if pd.get("text"):
                    yield ev({"thinking": pd["text"]})
            elif ty == "message.interim":
                if pd.get("text"):
                    yield ev({"interim": pd["text"]})
            elif ty == "tool.generating":
                yield ev({"tool_generating": pd.get("name")})
            elif ty == "tool.start":
                yield ev({"tool_start": {"tool_id": pd.get("tool_id"), "name": pd.get("name"),
                                         "context": _truncate(pd.get("context") or "", 300),
                                         "args": _truncate(pd.get("args"), TOOL_ARGS_MAX)}})
            elif ty == "tool.complete":
                yield ev({"tool_done": {"tool_id": pd.get("tool_id"), "name": pd.get("name"),
                                        "duration_s": pd.get("duration_s"),
                                        "result": _truncate(pd.get("result"), TOOL_RESULT_MAX)}})
            elif ty == "approval.request":
                yield ev({"approval": {**pd, "session_id": sid}})
            elif ty == "clarify.request":
                yield ev({"status": {"kind": "clarify", "text": _truncate(pd.get("text") or pd, 500)}})
            elif ty == "status.update":
                yield ev({"status": {"kind": pd.get("kind"), "text": pd.get("text")}})
            elif ty == "turn.error":
                yield ev({"error": str(pd.get("text") or pd.get("message") or pl or "turn error")[:500]})
                return
            elif ty == "message.complete":
                yield ev({"done": {"text": pd.get("text") or "", "usage": pd.get("usage"),
                                   "status": pd.get("status")}})
                return
            # everything else (sessions.changed, session.info, session.usage,
            # reasoning.available, todo.updated …) is chrome for other clients
    except HermesError as exc:
        yield ev({"error": str(exc)})
    except HTTPException:
        raise
    except Exception as exc:                                       # noqa: BLE001
        log.warning("hermes turn failed: %s", exc)
        yield ev({"error": f"{type(exc).__name__}: {exc}"[:300]})
    finally:
        if conn is not None:
            await conn.close()


@router.post("/hermes/chat")
async def hermes_chat(body: AgentTurn, request: Request,
                      email: str = Depends(require_primary_admin)):
    images = _clean_images(body.images)
    if not (body.text or "").strip() and not images:
        raise HTTPException(400, "text is empty")
    return StreamingResponse(
        _turn(body, images, request),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/hermes/approve")
async def hermes_approve(body: Approve, email: str = Depends(require_primary_admin)):
    if body.choice not in APPROVAL_CHOICES:
        raise HTTPException(400, f"choice must be one of {', '.join(APPROVAL_CHOICES)}")
    conn = None
    try:
        conn = await open_conn()
        await conn.wait_ready()
        res = await conn.call("approval.respond", {
            "session_id": body.session_id, "request_id": body.request_id,
            "choice": body.choice, "all": False})
        return JSONResponse({"ok": True, "result": res})
    except HermesError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=502)
    finally:
        if conn is not None:
            await conn.close()


@router.post("/hermes/interrupt")
async def hermes_interrupt(body: Interrupt, email: str = Depends(require_primary_admin)):
    conn = None
    try:
        conn = await open_conn()
        await conn.wait_ready()
        res = await conn.call("session.interrupt", {"session_id": body.session_id}, timeout=15)
        return JSONResponse({"ok": True, "result": res})
    except HermesError as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=502)
    finally:
        if conn is not None:
            await conn.close()
