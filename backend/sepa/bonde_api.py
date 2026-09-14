"""Bonde board endpoint — read-only, never scans on the request path.

Ajay 2026-09-13: *"create me a Bonde tab … I wanna see explicitly new ones
getting added in this tab."*
"""
from __future__ import annotations

import asyncio
import logging
import math

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from . import bonde as B

log = logging.getLogger("sepa.bonde_api")
router = APIRouter(tags=["bonde"])


def _scrub(obj):
    """NaN/Inf → None, everywhere, before it reaches the browser.

    The same scrub every board in this app runs. A NaN serialises as the bare
    token `NaN`, which is not legal JSON, and the frontend's JSON.parse throws —
    that failure mode has shipped here before (the SSE 'done' event, 2026-05-29)
    and it looks like a hung page, not a data error.
    """
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


@router.get("/bonde/board")
async def bonde_board(
    new_days: int = Query(B.NEW_DAYS, ge=1, le=365,
                          description="how many days an arrival counts as ✨ NEW"),
):
    """Pradeep Bonde's screen: ⚡ Episodic Pivots first, then his sales tiers.

    `new_days` is coerced inside the handler for the reason every board in this
    repo coerces: these functions get called directly in the container for smoke
    tests, and FastAPI resolves `Query(...)` defaults at REQUEST time, so a
    direct call receives the Query OBJECT — which is not an int.
    """
    def _run():
        return B.board(new_days=new_days if isinstance(new_days, int) else B.NEW_DAYS)

    return JSONResponse(_scrub(await asyncio.to_thread(_run)))
