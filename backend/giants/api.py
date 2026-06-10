"""Giants API — aggregated 13F flow leaderboard + per-symbol rotation.

GET  /giants/flows            the persisted aggregate doc (self-heals if stale)
GET  /giants/rotation/{sym}   where the money moved for one symbol (cache-only)
GET  /giants/refresh/status   background refresh progress
POST /giants/refresh          force a refresh (admin)
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from auth import current_user_email, is_admin_email

router = APIRouter(tags=["giants"])


@router.get("/giants/flows")
async def giants_flows():
    from giants import flows
    return JSONResponse(await asyncio.to_thread(flows.latest))


@router.get("/giants/rotation/{symbol}")
async def giants_rotation(symbol: str):
    from giants import flows
    return JSONResponse(await asyncio.to_thread(flows.symbol_rotation, symbol))


@router.get("/giants/refresh/status")
async def giants_refresh_status():
    from giants import flows
    return JSONResponse(flows.refresh_status())


@router.post("/giants/refresh")
async def giants_refresh(email: str = Depends(current_user_email)):
    if not is_admin_email(email):
        raise HTTPException(403, "admin only")
    from giants import flows
    return JSONResponse(await asyncio.to_thread(flows.start_refresh))
