"""📚 Playbook learning — the two routes (spec playbook videos §3.3, WP-be, 2026-11-27).

Ajay 2026-11-27 ~02:15 ET, verbatim: "I loved the video can you move them under our replay tab with a PLaybook learning
and also add it to the playbook tab too with videos".

  * `GET /chart-maps/replays/playbook` — the listing (`playbook.payload`), read off the event loop, `no-store`.
  * `GET|HEAD /chart-maps/replays/playbook/video/{film}/{name}` — the bytes of a LISTED film file only, through
    Starlette's own `FileResponse` (the ONE Range engine) with `C.VIDEO_HEADERS` (identity + private, no-transform).

Included from `api.py` by `router.include_router(...)` so `api.py` keeps its four own routes. PRIMARY OWNER ONLY through
the ONE gate `require_primary_admin` (a dependency, resolved before the path is looked at): anyone else gets the stealth
404, no header → 401. The admin email is never typed here. Read-only; UNMEASURED.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from ollama_chat.api import require_primary_admin

from . import constants as C
from . import playbook as PB

router = APIRouter(tags=["chart-maps"])


@router.get(C.PLAYBOOK_API_PATH)
async def replay_playbook(email: str = Depends(require_primary_admin)):
    body = await asyncio.to_thread(PB.payload)
    return JSONResponse(body, headers=C.LISTING_HEADERS)


@router.api_route(C.PLAYBOOK_VIDEO_PATH, methods=["GET", "HEAD"])
async def replay_playbook_video(film: str, name: str, email: str = Depends(require_primary_admin)):
    path = await asyncio.to_thread(PB.resolve_video, film, name)
    if path is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(str(path), media_type="video/mp4", headers=C.VIDEO_HEADERS)
