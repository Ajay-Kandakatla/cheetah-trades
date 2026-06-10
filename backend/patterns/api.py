"""Patterns API — on-demand bullish-pattern scan (owner-triggered, like the SEPA
full scan), polled progress, and the persisted latest results."""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse

from auth import current_user_email, is_admin_email

router = APIRouter(tags=["patterns"])


@router.post("/patterns/scan")
async def patterns_scan_start(email: str = Depends(current_user_email),
                              payload: Optional[dict] = Body(default=None)):
    """Owner: kick off a pattern scan (background thread; poll
    /patterns/scan/status). Reads cached daily frames — no provider calls.
    Body {"scope": "qualifiers"} answers EVERY SEPA qualifier (match or
    no-match); default scope "universe" is the hits-only sweep."""
    if not is_admin_email(email):
        raise HTTPException(403, "admin only")
    scope = (payload or {}).get("scope") or "universe"
    from . import scan
    return JSONResponse(await asyncio.to_thread(scan.start_scan, scope))


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


@router.get("/patterns/symbol/{symbol}")
async def patterns_symbol(symbol: str):
    """On-demand single-ticker pattern read: which pattern this chart matches
    right now (or explicitly none), recent candle reads, and THIS chart's own
    historical record per pattern. Fresh compute on cached daily bars (~10ms)."""
    from . import scan
    return JSONResponse(await asyncio.to_thread(scan.symbol_verdict, symbol))


@router.get("/patterns/accuracy")
async def patterns_accuracy():
    """The live forward record: every pattern/candle the verdict scan flagged,
    graded later against the real tape (target-before-stop within 21 bars,
    forming→confirm rate, candle direction hits). Measured frequencies — the
    honest answer to "what's our patterns' success rate?"."""
    from . import history
    return JSONResponse(await asyncio.to_thread(history.accuracy))


@router.get("/patterns/qualifiers")
async def patterns_qualifiers():
    """The last qualifier verdict scan: every SEPA qualifier with the pattern(s)
    it matches (confirmed/forming), recent candle reads, or an explicit
    no-match. The chart-analysis column beside SEPA, VCP and volume."""
    from . import scan
    return JSONResponse(await asyncio.to_thread(scan.latest_qualifiers))
