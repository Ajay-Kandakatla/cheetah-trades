"""LLM client — supports both local OpenAI-compatible servers
(LM Studio / Ollama / vLLM / llama.cpp's server) AND the native
Anthropic Messages API.

Two provider configurations in backend/.env:

    # ── Local (LM Studio etc.) ───────────────────────────────────────
    LLM_BASE_URL=http://host.docker.internal:1234/v1
    LLM_MODEL=gemma-4-26b-a4b-it-mlx
    LLM_API_KEY=lm-studio                # optional; LM Studio ignores

    # ── Anthropic Claude ─────────────────────────────────────────────
    ANTHROPIC_LLM_BASE_URL=https://api.anthropic.com/v1
    ANTHROPIC_LLM_MODEL=claude-sonnet-4-5
    ANTHROPIC_LLM_API_KEY=sk-ant-...      # canonical
    # ANTHROPIC_API_KEY=sk-ant-...        # also accepted (Anthropic's
                                          # standard env name)

Callers pick a provider per call:

    llm.chat(prompt)                          # default — uses LOCAL
                                              # (no behavior change for
                                              #  existing callers)
    llm.chat(prompt, provider="anthropic")    # forces Claude
    llm.chat(prompt, provider="auto")         # Anthropic if configured,
                                              # else local

Cost note: the catalysts.gemma_review path fires the LLM for many
tickers per scan — running that on Claude Sonnet 4.5 would cost
real money. The default stays "local" intentionally so existing
high-volume callers keep paying $0. Only the todos llm_runner
(research-quality tasks the user asked for explicitly) flips to
``provider="anthropic"`` when configured.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional

log = logging.getLogger("llm")


# ============================================================================
# Provider configuration helpers
# ============================================================================
def _local_configured() -> bool:
    return bool(os.getenv("LLM_BASE_URL") and os.getenv("LLM_MODEL"))


def _anthropic_configured() -> bool:
    """True when we have both an API key (either prefixed name) and a
    model id. The base URL has a sensible default so we don't require
    the user to set it."""
    has_key = bool(os.getenv("ANTHROPIC_LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
    has_model = bool(os.getenv("ANTHROPIC_LLM_MODEL"))
    return has_key and has_model


def _anthropic_api_key() -> Optional[str]:
    """Read in priority order: the explicit ANTHROPIC_LLM_API_KEY (our
    namespaced naming) first, then the canonical ANTHROPIC_API_KEY that
    Anthropic's own SDK reads from. Both work."""
    return os.getenv("ANTHROPIC_LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY")


def is_enabled() -> bool:
    return _local_configured() or _anthropic_configured()


# ============================================================================
# Health
# ============================================================================
def _health_local() -> dict:
    base = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")
    if not base:
        return {"enabled": False, "reason": "LLM_BASE_URL not set"}
    import requests
    try:
        r = requests.get(f"{base}/models", timeout=5)
        if r.status_code != 200:
            return {"enabled": True, "ok": False, "base_url": base, "model": model,
                    "status": r.status_code, "error": r.text[:200]}
        body = r.json()
        ids = [x.get("id") for x in (body.get("data") or [])]
        return {"enabled": True, "ok": True, "base_url": base, "model": model,
                "models_available": ids, "model_loaded": model in ids if model else None}
    except Exception as exc:
        return {"enabled": True, "ok": False, "base_url": base, "model": model, "error": str(exc)}


def _health_anthropic() -> dict:
    """Lightweight probe — Anthropic doesn't have a free `/models` GET
    we can call without spending tokens. We just verify the key + model
    are configured and the base URL is reachable (HEAD on root)."""
    if not _anthropic_configured():
        return {"enabled": False, "reason": "ANTHROPIC_LLM_API_KEY / ANTHROPIC_LLM_MODEL not set"}
    base = os.getenv("ANTHROPIC_LLM_BASE_URL", "https://api.anthropic.com/v1")
    model = os.getenv("ANTHROPIC_LLM_MODEL")
    # Anthropic's /v1/models endpoint actually exists and is free to
    # GET with a valid key — use it for a real probe.
    import requests
    try:
        r = requests.get(
            f"{base}/models",
            headers={
                "x-api-key": _anthropic_api_key() or "",
                "anthropic-version": "2023-06-01",
            },
            timeout=5,
        )
        if r.status_code != 200:
            return {"enabled": True, "ok": False, "base_url": base, "model": model,
                    "status": r.status_code, "error": r.text[:200]}
        body = r.json()
        ids = [m.get("id") for m in (body.get("data") or [])]
        return {"enabled": True, "ok": True, "base_url": base, "model": model,
                "models_available": ids, "model_loaded": model in ids if model else None}
    except Exception as exc:
        return {"enabled": True, "ok": False, "base_url": base, "model": model, "error": str(exc)}


def health() -> dict:
    """Combined health for both providers. Shape backward-compatible
    with the previous single-provider response — the top-level fields
    describe the local provider so /llm/health UI keeps working — and
    new fields describe Anthropic alongside."""
    local = _health_local()
    out: dict = dict(local)                          # keep old top-level shape
    if _anthropic_configured():
        out["anthropic"] = _health_anthropic()
    out["providers"] = {
        "local":     _local_configured(),
        "anthropic": _anthropic_configured(),
    }
    return out


# ============================================================================
# Provider implementations
# ============================================================================
def _chat_local(prompt: str, *, system: Optional[str], max_tokens: int,
                temperature: float, timeout: int) -> dict:
    base = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL")
    if not base or not model:
        return {"ok": False, "error": "local LLM not configured (LLM_BASE_URL / LLM_MODEL)"}

    import requests
    messages: list = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    api_key = os.getenv("LLM_API_KEY", "lm-studio")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    t0 = time.time()
    try:
        r = requests.post(f"{base}/chat/completions", json=body, headers=headers, timeout=timeout)
    except Exception as exc:
        return {"ok": False, "provider": "local", "error": f"request failed: {exc}",
                "latency_sec": time.time() - t0}
    latency = time.time() - t0
    if r.status_code != 200:
        return {"ok": False, "provider": "local", "error": f"HTTP {r.status_code}: {r.text[:200]}",
                "latency_sec": latency}
    try:
        body = r.json()
    except Exception as exc:
        return {"ok": False, "provider": "local", "error": f"non-JSON response: {exc}",
                "latency_sec": latency}

    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return {"ok": False, "provider": "local", "error": "malformed response",
                "raw": body, "latency_sec": latency}

    return {
        "ok": True,
        "provider": "local",
        "text": text,
        "model": body.get("model"),
        "latency_sec": round(latency, 2),
        "input_tokens":  (body.get("usage") or {}).get("prompt_tokens"),
        "output_tokens": (body.get("usage") or {}).get("completion_tokens"),
    }


def _chat_anthropic(prompt: str, *, system: Optional[str], max_tokens: int,
                    temperature: float, timeout: int) -> dict:
    """Call Anthropic's native Messages API. Differences vs OpenAI-compat:

      - Endpoint:        POST /v1/messages   (not /chat/completions)
      - Auth header:     x-api-key + anthropic-version  (not Authorization)
      - Body:            system is a TOP-LEVEL field, not a message;
                         messages array uses {role, content} pairs
                         where role is 'user' or 'assistant' (no 'system')
      - Response shape:  body.content[] is a list of content blocks of
                         type 'text' (we concatenate their text fields)
      - Token usage:     usage.input_tokens / usage.output_tokens

    We deliberately don't pull in the official anthropic SDK — the
    direct HTTP path is ~30 lines and avoids a heavy dependency for
    this single use site.
    """
    api_key = _anthropic_api_key()
    base = os.getenv("ANTHROPIC_LLM_BASE_URL", "https://api.anthropic.com/v1")
    model = os.getenv("ANTHROPIC_LLM_MODEL")
    if not api_key or not model:
        return {"ok": False, "provider": "anthropic",
                "error": "Anthropic not configured (ANTHROPIC_LLM_API_KEY / ANTHROPIC_LLM_MODEL)"}

    import requests
    headers = {
        "Content-Type":      "application/json",
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
    }
    payload: dict = {
        "model":       model,
        "max_tokens":  max_tokens,
        "temperature": temperature,
        "messages":    [{"role": "user", "content": prompt}],
    }
    if system:
        # system goes top-level for Anthropic, not inline as a message.
        payload["system"] = system

    t0 = time.time()
    try:
        r = requests.post(f"{base}/messages", json=payload, headers=headers, timeout=timeout)
    except Exception as exc:
        return {"ok": False, "provider": "anthropic", "error": f"request failed: {exc}",
                "latency_sec": time.time() - t0}
    latency = time.time() - t0
    if r.status_code != 200:
        return {"ok": False, "provider": "anthropic",
                "error": f"HTTP {r.status_code}: {r.text[:200]}", "latency_sec": latency}
    try:
        body = r.json()
    except Exception as exc:
        return {"ok": False, "provider": "anthropic", "error": f"non-JSON response: {exc}",
                "latency_sec": latency}

    # Anthropic returns content as a list of blocks; we want the
    # concatenated text of all `type: "text"` blocks. Other block
    # types (tool_use etc.) aren't expected from a plain user-message
    # request but we skip them defensively.
    text = ""
    for block in body.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text += block.get("text") or ""

    if not text:
        return {"ok": False, "provider": "anthropic", "error": "no text content in response",
                "raw": body, "latency_sec": latency}

    usage = body.get("usage") or {}
    return {
        "ok":             True,
        "provider":       "anthropic",
        "text":           text,
        "model":          body.get("model"),
        "latency_sec":    round(latency, 2),
        "input_tokens":   usage.get("input_tokens"),
        "output_tokens":  usage.get("output_tokens"),
        # Stop reason is useful for debugging hit length limits
        "stop_reason":    body.get("stop_reason"),
    }


# ============================================================================
# Public chat() — dispatches by provider
# ============================================================================
def chat(prompt: str, *,
         system: Optional[str] = None,
         max_tokens: int = 600,
         temperature: float = 0.2,
         json_only: bool = False,
         timeout: int = 60,
         provider: str = "local") -> dict:
    """Single-turn chat completion.

    provider:
      - "local"     (default) — OpenAI-compatible server. Existing
                                callers keep their existing behavior;
                                no Claude bills get rung up by accident.
      - "anthropic"           — Anthropic Messages API. Falls back to
                                local if Anthropic isn't configured —
                                so an opt-in caller doesn't hard-fail
                                on a fresh deploy that hasn't added
                                ANTHROPIC_LLM_API_KEY yet.
      - "auto"                — Anthropic if configured, else local.

    Returns:
        {ok: bool, text: str, model: str, provider: str, latency_sec: float, ...}
    or  {ok: False, error: str, ...}

    json_only=True post-processes the response to strip markdown fences
    and tries to parse as JSON, returning the parsed dict in `parsed`.
    Works for both providers.
    """
    # Provider resolution. "auto" expands to anthropic if available,
    # else local. "anthropic" with no config silently falls back to
    # local — preserves the older callers' ability to opt in without
    # blocking the path during incremental rollout.
    if provider == "auto":
        provider = "anthropic" if _anthropic_configured() else "local"
    elif provider == "anthropic" and not _anthropic_configured():
        log.info("llm.chat: anthropic requested but not configured — falling back to local")
        provider = "local"

    if provider == "anthropic":
        out = _chat_anthropic(prompt, system=system, max_tokens=max_tokens,
                              temperature=temperature, timeout=timeout)
    else:
        out = _chat_local(prompt, system=system, max_tokens=max_tokens,
                          temperature=temperature, timeout=timeout)

    if json_only and out.get("ok"):
        parsed, parse_err = _extract_json(out.get("text") or "")
        out["parsed"] = parsed
        if parse_err:
            out["parse_error"] = parse_err
    return out


# ============================================================================
# JSON extraction (unchanged)
# ============================================================================
def _extract_json(text: str) -> tuple[Optional[dict], Optional[str]]:
    """Robust JSON extraction — handles markdown fences (Gemma's habit),
    surrounding prose, and trailing commas."""
    if not text:
        return None, "empty"
    s = text.strip()
    # Strip ```json ... ``` fences
    if s.startswith("```"):
        # remove first fence line
        s = re.sub(r"^```(?:json)?\s*\n", "", s)
        s = re.sub(r"\n```\s*$", "", s)
    # Find first { ... } block (greedy)
    m = re.search(r"\{.*\}", s, re.S)
    if not m:
        return None, "no JSON object found"
    candidate = m.group(0)
    # Remove trailing commas before } or ]
    candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
    try:
        return json.loads(candidate), None
    except Exception as exc:
        return None, f"json decode: {exc}"
