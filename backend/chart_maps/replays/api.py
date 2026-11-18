"""🎬 Replays — the routes (replays spec §3.1, WP-BE, 2026-11-17).

Ajay 2026-11-17, verbatim: "Can you store the videos in to the app please".

  * `GET /chart-maps/replays[?date=YYYY-MM-DD]` — the listing (`store.payload`), read off the event loop,
    `Cache-Control: no-store`. A malformed `date` → 404; a well-formed day with no folder → `state: "empty"` with
    that day kept (the URL stays truthful).
  * `GET|HEAD /chart-maps/replays/video/{day}/{name}` — the bytes of a LISTED mp4 only, through Starlette's own
    `FileResponse` (the ONE Range engine: 206 / 416 / multipart / HEAD). `VIDEO_HEADERS` carries
    `Content-Encoding: identity` (our GZipMiddleware would otherwise gzip a ≥ 1024-byte partial into a corrupt 206)
    and `Cache-Control: private, no-transform` (Cloudflare never caches `private` — a cached 200 would bypass the gate).
    FastAPI does not answer HEAD on `@router.get` (measured 405) → `api_route(methods=["GET", "HEAD"])`.

PRIMARY OWNER ONLY on both routes through `require_primary_admin` — a DEPENDENCY, so it resolves before the path is
looked at: anyone else gets the same stealth 404 for a real file, a traversal attempt or a bad date; no header → 401
(`auth.current_user_email`). The admin email is never typed here. Read-only; UNMEASURED.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from ollama_chat.api import require_primary_admin

from . import constants as C
from . import store as ST

router = APIRouter(tags=["chart-maps"])


@router.get(C.API_PATH)
async def replays(date: Optional[str] = Query(None), email: str = Depends(require_primary_admin)):
    if date is not None and not ST.is_date(date):
        raise HTTPException(status_code=404, detail="Not Found")
    body = await asyncio.to_thread(ST.payload, date)
    return JSONResponse(body, headers=C.LISTING_HEADERS)


@router.api_route(C.API_VIDEO_PATH, methods=["GET", "HEAD"])
async def replay_video(day: str, name: str, email: str = Depends(require_primary_admin)):
    path = await asyncio.to_thread(ST.resolve_video, day, name)
    if path is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(str(path), media_type="video/mp4", headers=C.VIDEO_HEADERS)
