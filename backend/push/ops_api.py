"""🩺 POST /admin/ops/alert — the Mac's Docker watchdog reports here (2026-10-06).

Why: on 2026-10-05 Docker's backend died and its network forwarder had leaked
~14,750 flows; nothing told Ajay. ``ops/docker_watchdog.py`` runs on the host
every 2 minutes under launchd and POSTs one alert per condition to
``http://127.0.0.1:8000/admin/ops/alert``. This route turns it into ONE web
push (kind ``ops_alert``) to the primary admin's devices.

Contract (pinned by tests/test_ops_alert.py; the watchdog side by
tests/test_docker_watchdog.py):

    body  {"condition": one of push.hooks.OPS_CONDITIONS,
           "title": 1..80 chars, "body": 1..280 chars}        (no other keys)
    200   {"ok": true, "delivered": bool, "sent", "failed", "total_targets",
           "skipped": null | "no_target" | "quiet_hours" | <closed-day reason>}
    401 no auth · 404 not the primary admin · 422 bad body
    429   {"ok": false, "error": "rate_limited", "retry_after_sec": int}
    500   {"ok": false, "error": "send_failed"}

Safety: the caller cannot choose the kind or the recipient (extra keys are
refused); only ``push.hooks.ADMIN_EMAIL`` is gated in (404 to everyone else,
the /ollama stealth gate); at most ``OPS_RATE_MAX_PER_HOUR`` accepted requests
per condition per hour. Nothing here trades or touches an alert gate.
"""
from __future__ import annotations

import asyncio
import collections
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from auth import current_user_email
from push import hooks

log = logging.getLogger("push.ops_api")

router = APIRouter(tags=["ops"])

OPS_RATE_MAX_PER_HOUR = 6          # per condition; the watchdog retries every 15 min (4/h)
_RATE_WINDOW_SEC = 3600.0
_now = time.monotonic              # tests monkeypatch
_SENT: dict = {}                   # condition -> deque[monotonic]; single uvicorn worker


def require_ops_admin(email: str = Depends(current_user_email)) -> str:
    """Strict primary admin (push.hooks.ADMIN_EMAIL), 404 to everyone else — the
    /ollama stealth gate. A dependency, so a stranger posting garbage gets 404, not 422."""
    if (email or "").strip().lower() != hooks.ADMIN_EMAIL:
        raise HTTPException(status_code=404, detail="Not Found")
    return email


class OpsAlertIn(BaseModel):
    model_config = ConfigDict(extra="forbid")   # no recipient, no kind, nothing else
    condition: str
    title: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=280)

    @field_validator("title", "body", mode="before")
    @classmethod
    def _strip(cls, v):
        # strip BEFORE min_length (critic 2026-10-06: an all-spaces title passed)
        return v.strip() if isinstance(v, str) else v

    @field_validator("condition")
    @classmethod
    def _known_condition(cls, v: str) -> str:
        if v not in hooks.OPS_CONDITIONS:
            raise ValueError("unknown ops condition")
        return v


@router.post("/admin/ops/alert")
async def ops_alert(req: OpsAlertIn, _admin: str = Depends(require_ops_admin)):
    now = _now()
    sent_at = _SENT.setdefault(req.condition, collections.deque())
    while sent_at and now - sent_at[0] >= _RATE_WINDOW_SEC:
        sent_at.popleft()
    if len(sent_at) >= OPS_RATE_MAX_PER_HOUR:
        retry = max(1, int(_RATE_WINDOW_SEC - (now - sent_at[0])) + 1)
        return JSONResponse(status_code=429, content={
            "ok": False, "error": "rate_limited", "retry_after_sec": retry})
    sent_at.append(now)
    try:
        r = await asyncio.to_thread(hooks.notify_ops, req.condition,
                                    req.title.strip(), req.body.strip())
    except Exception as exc:
        log.warning("ops_alert: send failed for %s (%s)", req.condition, type(exc).__name__)
        return JSONResponse(status_code=500, content={"ok": False, "error": "send_failed"})
    r = r or {}
    return {"ok": True, "delivered": r.get("sent", 0) > 0,
            "sent": r.get("sent", 0), "failed": r.get("failed", 0),
            "total_targets": r.get("total_targets", 0), "skipped": r.get("skipped")}
