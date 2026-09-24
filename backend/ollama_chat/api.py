"""Private chat with the local Ollama model — Ajay only.

Ajay 2026-09-14: *"Can you build me a chat interface to talk to my Ollamma LLM
the abliterated model. I wanna chat with it from this app but only available
for me. Make sure the LLM is setup to start on computer start. Turn on the
LLM. I can upload images and talk to it."*

WHAT WAS ALREADY TRUE WHEN I LOOKED (so nothing here re-does it)
────────────────────────────────────────────────────────────────
* Ollama 0.33.3 is a Homebrew service: ``~/Library/LaunchAgents/
  sh.brew.ollama.plist`` with ``RunAtLoad`` + ``KeepAlive`` and the
  ``LoginWindow`` session type. It starts at login and restarts if it dies.
  "Start on computer start" was already done; I did not touch the plist —
  brew rewrites it on upgrade and any hand edit would be lost.
* The model he chats with in Hermes is ``huihui_ai/Qwen3.8-abliterated:27b``
  (his terminal paste showed it). ``ollama show`` reports capabilities
  completion / **vision** / tools / thinking with a 460M CLIP projector, so
  images work natively — no second model, no OCR sidecar.
* The api container reaches the host's Ollama at
  ``http://host.docker.internal:11434`` (verified with a request from inside
  the container; ``172.17.0.1`` does not work on Docker Desktop for Mac).
* "Turn on the LLM": a warm request with ``keep_alive: -1`` loaded it —
  ``ollama ps`` reads 20 GB, 100% GPU, ``UNTIL Forever``. Every request this
  module sends repeats ``keep_alive: -1`` so an idle hour never unloads it.

WHY THE GATE IS THE STRICT ADMIN EMAIL AND NOT ``is_admin_email``
─────────────────────────────────────────────────────────────────
``auth.is_admin_email`` is TRUE FOR EVERY HOUSE OWNER — Vineetha included,
by design ("a household sale or budget should be jointly managed"). He said
*only available for me*. So this router gates on the single primary-admin
address, the same way ``access/api.py`` gates the user-access screens, and
answers **404** (not 403) to anyone else so the page's existence stays
opaque. Kept as a local constant rather than imported, matching the note in
``access/api.py``: a refactor of one gate must not quietly relax the other.
``tests/test_ollama_chat.py`` pins the two constants equal.

The address never reaches the JS bundle. The frontend learns whether to show
the page from ``is_primary_admin`` on ``/auth/me`` — a boolean, the same
pattern that replaced six leaked ``ADMIN_EMAIL`` constants in 2026.

STREAMING
─────────
A 27B model at Q4 streams at tens of tokens a second; a full answer can take
a minute. Waiting on a blank pane for that is the one thing that would make
him go back to the terminal, so ``/ollama/chat`` is server-sent events, the
house shape from ``main.py``'s tape streams (``text/event-stream`` +
``X-Accel-Buffering: no``). The ``/api/`` proxy already has
``proxy_buffering off`` and 1800 s timeouts, so tokens pass straight through.

Events, one JSON object per ``data:`` line::

    {"delta": "text"}         a slice of the answer
    {"thinking": "text"}      a slice of the model's reasoning (Qwen3.8 emits
                              this separately; the UI shows it folded)
    {"done": true, "eval_count": n, "total_duration": ns, "model": ...}
    {"error": "message"}      then the stream ends

IMAGES
──────
Ollama's chat API takes ``messages[].images`` as a list of raw base64 strings
(no ``data:image/...;base64,`` prefix). The browser produces data URLs, so
the frontend strips the prefix before sending and this module refuses
anything that still carries one rather than passing garbage to the model.
``client_max_body_size`` on the ``/api/`` proxy is raised to 40 MB for this
route's sake — nginx's 1 MB default rejected a single phone photo.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import AsyncIterator, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from auth import current_user_email
from events.sse_headers import SSE_HEADERS

log = logging.getLogger("ollama_chat")
router = APIRouter()

# Mirrors ADMIN_EMAIL in access/api.py. Deliberately NOT imported — see the
# module docstring. tests/test_ollama_chat.py asserts the two stay equal.
PRIMARY_ADMIN_EMAIL = "ajaykandakatla@gmail.com"

DEFAULT_BASE_URL = "http://host.docker.internal:11434"
DEFAULT_MODEL = "huihui_ai/Qwen3.8-abliterated:27b"

# Ollama unloads an idle model after 5 minutes by default. -1 pins it in
# memory — that is what "turn on the LLM" means for a 20 GB model he wants
# to talk to on impulse, and the M5 has 128 GB.
KEEP_ALIVE = -1

MAX_IMAGES_PER_MESSAGE = 6
MAX_IMAGE_B64_BYTES = 12 * 1024 * 1024        # ~9 MB decoded — a large phone photo
MAX_MESSAGES = 200

_DATA_URL = re.compile(r"^data:[^;]+;base64,", re.I)


def base_url() -> str:
    return (os.getenv("OLLAMA_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def model_name() -> str:
    return os.getenv("OLLAMA_CHAT_MODEL") or DEFAULT_MODEL


def is_primary_admin(email: Optional[str]) -> bool:
    return (email or "").strip().lower() == PRIMARY_ADMIN_EMAIL


def _require_primary_admin(email: str) -> None:
    """404 stealth gate — the page does not exist for anyone else."""
    if not is_primary_admin(email):
        raise HTTPException(status_code=404, detail="Not Found")


def require_primary_admin(email: str = Depends(current_user_email)) -> str:
    """The gate as a DEPENDENCY, not a first line in the handler.

    FastAPI resolves dependencies before it validates the body, and an
    exception raised here short-circuits. Gating inside the handler would
    let a stranger learn the route exists by posting garbage — they would
    get a 422 with our field names instead of the 404 everyone else sees."""
    _require_primary_admin(email)
    return email


# ---------------------------------------------------------------------------
# Request shapes
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str = Field(pattern="^(system|user|assistant)$")
    content: str = ""
    images: Optional[list[str]] = None


class ChatBody(BaseModel):
    messages: list[ChatMessage]
    model: Optional[str] = None
    think: Optional[bool] = None
    options: Optional[dict] = None


def _clean_messages(msgs: list[ChatMessage]) -> list[dict]:
    """Validate and normalise for Ollama. Raises 400 on anything that would
    otherwise fail inside the model call with a far less useful error."""
    if not msgs:
        raise HTTPException(400, "messages is empty")
    if len(msgs) > MAX_MESSAGES:
        raise HTTPException(400, f"more than {MAX_MESSAGES} messages")
    out = []
    for m in msgs:
        d: dict = {"role": m.role, "content": m.content or ""}
        if m.images:
            if len(m.images) > MAX_IMAGES_PER_MESSAGE:
                raise HTTPException(400, f"more than {MAX_IMAGES_PER_MESSAGE} images on one message")
            imgs = []
            for raw in m.images:
                s = (raw or "").strip()
                if not s:
                    continue
                if _DATA_URL.match(s):
                    # The frontend strips this; refuse rather than pass a
                    # prefixed blob the model will silently fail to decode.
                    raise HTTPException(400, "images must be raw base64, not a data: URL")
                if len(s) > MAX_IMAGE_B64_BYTES:
                    raise HTTPException(413, "image too large")
                imgs.append(s)
            if imgs:
                d["images"] = imgs
        out.append(d)
    if not any(m["role"] == "user" for m in out):
        raise HTTPException(400, "no user message")
    return out


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/ollama/me")
async def ollama_me(email: str = Depends(require_primary_admin)):
    """Gate probe + status for the page header. 404 for anyone but him."""
    status = {"ok": True, "model": model_name(), "base_url": base_url(),
              "reachable": False, "resident": False, "version": None,
              "capabilities": [], "context_length": None}
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            v = await c.get(f"{base_url()}/api/version")
            status["reachable"] = v.status_code == 200
            status["version"] = (v.json() or {}).get("version") if status["reachable"] else None
            ps = await c.get(f"{base_url()}/api/ps")
            if ps.status_code == 200:
                names = {m.get("name") for m in (ps.json() or {}).get("models", [])}
                status["resident"] = model_name() in names
            show = await c.post(f"{base_url()}/api/show", json={"model": model_name()})
            if show.status_code == 200:
                j = show.json() or {}
                status["capabilities"] = j.get("capabilities") or []
                info = j.get("model_info") or {}
                cl = next((v for k, v in info.items() if k.endswith(".context_length")), None)
                status["context_length"] = cl
    except Exception as exc:                                   # noqa: BLE001
        log.debug("ollama status: %s", exc)
    return JSONResponse(status)


@router.post("/ollama/warm")
async def ollama_warm(email: str = Depends(require_primary_admin)):
    """Load the model and pin it (keep_alive -1). The page calls this on
    open so the first real message never pays the 20 GB load."""
    try:
        async with httpx.AsyncClient(timeout=600.0) as c:
            r = await c.post(f"{base_url()}/api/generate",
                             json={"model": model_name(), "prompt": "", "keep_alive": KEEP_ALIVE})
            return JSONResponse({"ok": r.status_code == 200, "model": model_name()})
    except Exception as exc:                                   # noqa: BLE001
        return JSONResponse({"ok": False, "error": type(exc).__name__}, status_code=200)


async def _stream(payload: dict, request: Request) -> AsyncIterator[bytes]:
    """Relay Ollama's NDJSON stream as SSE. Stops the upstream generation
    when the browser disconnects — otherwise a closed tab keeps the GPU
    busy for the rest of a long answer."""
    def ev(obj: dict) -> bytes:
        return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode("utf-8")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=10.0)) as c:
            async with c.stream("POST", f"{base_url()}/api/chat", json=payload) as r:
                if r.status_code != 200:
                    body = (await r.aread()).decode("utf-8", "replace")[:300]
                    yield ev({"error": f"ollama {r.status_code}: {body}"})
                    return
                async for line in r.aiter_lines():
                    if await request.is_disconnected():
                        return
                    if not line:
                        continue
                    try:
                        j = json.loads(line)
                    except ValueError:
                        continue
                    if j.get("error"):
                        yield ev({"error": str(j["error"])})
                        return
                    msg = j.get("message") or {}
                    if msg.get("thinking"):
                        yield ev({"thinking": msg["thinking"]})
                    if msg.get("content"):
                        yield ev({"delta": msg["content"]})
                    if j.get("done"):
                        yield ev({"done": True, "model": j.get("model"),
                                  "eval_count": j.get("eval_count"),
                                  "prompt_eval_count": j.get("prompt_eval_count"),
                                  "total_duration": j.get("total_duration")})
                        return
    except httpx.ConnectError:
        yield ev({"error": f"cannot reach Ollama at {base_url()} — is `brew services start ollama` running?"})
    except Exception as exc:                                   # noqa: BLE001
        log.warning("ollama stream failed: %s", exc)
        yield ev({"error": f"{type(exc).__name__}: {exc}"[:300]})


@router.post("/ollama/chat")
async def ollama_chat(body: ChatBody, request: Request,
                      email: str = Depends(require_primary_admin)):
    payload: dict = {
        "model": body.model or model_name(),
        "messages": _clean_messages(body.messages),
        "stream": True,
        "keep_alive": KEEP_ALIVE,
    }
    if body.think is not None:
        payload["think"] = bool(body.think)
    if body.options:
        payload["options"] = body.options
    return StreamingResponse(
        _stream(payload, request),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
