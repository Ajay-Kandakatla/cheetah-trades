"""Patterns API — on-demand bullish-pattern scan (owner-triggered, like the SEPA
full scan), polled progress, and the persisted latest results."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from auth import current_user_email, is_admin_email

router = APIRouter(tags=["patterns"])


@router.post("/patterns/scan")
async def patterns_scan_start(email: str = Depends(current_user_email)):
    """Owner: kick off a full-universe pattern scan (background thread; poll
    /patterns/scan/status). Reads cached daily frames — no provider calls."""
    if not is_admin_email(email):
        raise HTTPException(403, "admin only")
    from . import scan
    return JSONResponse(await asyncio.to_thread(scan.start_scan))


@router.get("/patterns/scan/status")
async def patterns_scan_status():
    from . import scan
    return JSONResponse(scan.status())


@router.get("/patterns/latest")
async def patterns_latest():
    """The last scan's results: fresh confirmed/forming patterns with their SEPA
    context, plus OUR universe's measured +21-bar outcomes per pattern."""
    from . import scan
    return JSONResponse(await asyncio.to_thread(scan.latest))
