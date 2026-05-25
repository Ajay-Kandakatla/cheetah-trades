"""FastAPI router for the in-app chat with Claude.

Endpoint
--------
POST /chat
    Body:
      {
        messages:     [{role: "user"|"assistant", content: str}, ...],
        page_context: { ... whatever the page wants to share ... }
      }
    Response:
      {
        ok:           bool,
        text:         str,            // Claude's reply
        model:        str,
        latency_sec:  float,
        input_tokens: int | null,
        output_tokens: int | null,
      }

Auth: requires authenticated user (any). The auth middleware handles
this — anonymous requests get 401 before reaching the handler.

Rate limit: 20 calls / minute / IP. Token-bucket in-memory; resets on
container restart. Chat is interactive — a higher rate than the
batched scanners is fine, but we still cap so a runaway loop doesn't
ring up a $50 Claude bill.

Provider: Anthropic Messages API (claude-sonnet-4-5 per the user's
ANTHROPIC_LLM_MODEL env). The macro module already uses this same
provider via llm.chat() — but llm.chat() is single-prompt. Chat needs
multi-turn so we call the Anthropic endpoint directly here with the
full messages array.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import requests
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from auth import current_user_email

from .prompt import build_system_prompt

log = logging.getLogger("chat.api")

router = APIRouter(tags=["chat"])


# In-memory per-IP token bucket. Same pattern as local_auth/api.py
# — survives the request lifecycle, resets on restart, no DB needed.
_RATE_BUCKET: dict[str, list[float]] = {}
_RATE_WINDOW_SEC = 60
_RATE_LIMIT = 20


def _rate_check(ip: str) -> bool:
    """Return True if the IP is within budget; False if rate-limited.

    Trims old entries on every check so the map doesn't grow unbounded.
    """
    now = time.time()
    bucket = _RATE_BUCKET.setdefault(ip, [])
    # Drop timestamps older than the window.
    cutoff = now - _RATE_WINDOW_SEC
    bucket[:] = [t for t in bucket if t >= cutoff]
    if len(bucket) >= _RATE_LIMIT:
        return False
    bucket.append(now)
    return True


def _client_ip(request: Request) -> str:
    """Best-effort client IP. oauth2-proxy forwards X-Forwarded-For; in
    dev we fall back to client.host."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.client.host if request.client else "unknown")


@router.post("/chat")
async def chat_send(
    request: Request,
    payload: dict = Body(...),
    email: str = Depends(current_user_email),
):
    """Multi-turn chat with Claude, grounded in current page context."""
    if not _rate_check(_client_ip(request)):
        raise HTTPException(
            429,
            "Too many chat messages. Wait a minute and retry. (Limit: 20/min.)",
        )

    messages = payload.get("messages") or []
    page_context = payload.get("page_context") or None

    # Basic validation — keep cheap before we hit the network.
    if not isinstance(messages, list) or not messages:
        raise HTTPException(400, "messages must be a non-empty list")
    if len(messages) > 30:
        # Reset every so often — long chats run up costs fast and
        # Claude's context window isn't free either.
        raise HTTPException(
            400,
            "Chat exceeded 30 turns. Start a new conversation (clear chat) to continue.",
        )
    clean: list[dict] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = (m.get("role") or "").lower()
        content = m.get("content") or ""
        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        # Truncate individual messages to keep one runaway paste from
        # blowing the input-token budget.
        clean.append({"role": role, "content": content[:8000]})
    if not clean or clean[-1]["role"] != "user":
        raise HTTPException(
            400,
            "Last message must be from the user. (Are you replaying state?)",
        )

    system_prompt = build_system_prompt(page_context)

    # Anthropic Messages API direct call — bypasses llm.chat() because
    # that helper takes a single-prompt string. Multi-turn chat needs
    # the full messages array passed through.
    api_key = (
        os.getenv("ANTHROPIC_LLM_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
    )
    model = os.getenv("ANTHROPIC_LLM_MODEL")
    base = os.getenv("ANTHROPIC_LLM_BASE_URL", "https://api.anthropic.com/v1")
    if not api_key or not model:
        raise HTTPException(
            503,
            "Anthropic not configured — set ANTHROPIC_LLM_API_KEY and "
            "ANTHROPIC_LLM_MODEL in backend/.env.",
        )

    headers = {
        "Content-Type":      "application/json",
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
    }
    body = {
        "model":      model,
        "max_tokens": 1400,
        "temperature": 0.3,
        "system":     system_prompt,
        "messages":   clean,
    }

    t0 = time.time()
    try:
        r = requests.post(f"{base}/messages", json=body, headers=headers, timeout=60)
    except Exception as exc:
        log.warning("chat: anthropic request failed for %s: %s", email, exc)
        raise HTTPException(503, f"Anthropic request failed: {exc}")
    latency = time.time() - t0
    if r.status_code != 200:
        log.warning("chat: anthropic HTTP %s for %s: %s",
                    r.status_code, email, r.text[:200])
        raise HTTPException(r.status_code if r.status_code < 600 else 502,
                            f"Anthropic error: {r.text[:200]}")
    try:
        resp_body = r.json()
    except Exception as exc:
        raise HTTPException(502, f"Anthropic returned non-JSON: {exc}")

    # Anthropic returns content as a list of blocks; we want the
    # concatenated text of all text blocks.
    text = ""
    for block in resp_body.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text += block.get("text") or ""
    if not text:
        raise HTTPException(502, "Anthropic returned no text content")

    usage = resp_body.get("usage") or {}
    log.info("chat: user=%s in=%s out=%s latency=%.2fs",
             email, usage.get("input_tokens"), usage.get("output_tokens"), latency)

    return JSONResponse({
        "ok":             True,
        "text":           text,
        "model":          resp_body.get("model"),
        "latency_sec":    round(latency, 2),
        "input_tokens":   usage.get("input_tokens"),
        "output_tokens":  usage.get("output_tokens"),
    })
