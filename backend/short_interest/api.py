"""Short volume debug + drill API.

Endpoints:

  GET /short/{symbol}
      Latest cached snapshot for `symbol`. ~5ms on cache hit, ~300ms on miss.
      Used by the frontend chip + drill modal.

  GET /short/{symbol}/history?days=30
      Last `days` records (default 30). Used by sparkline trend rendering.

The data path goes through `short_interest.client` which manages the
1-day Mongo cache. No bulk endpoint exposed here — bulk loading happens
in the SEPA scanner's parallel worker pool.
"""
from __future__ import annotations

import asyncio
import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from short_interest import client as si_client

log = logging.getLogger("short_interest.api")

router = APIRouter(tags=["short_interest"])


@router.get("/short/{symbol}")
async def get_short_volume(symbol: str, refresh: bool = Query(False)):
    """Latest single-day short-volume snapshot for `symbol`."""
    sym = symbol.upper()
    snap = si_client.short_volume_for(sym, force_refresh=refresh)
    if not snap:
        return JSONResponse(
            {"symbol": sym, "found": False,
             "message": "No short-volume data — FINRA doesn't publish "
                        "for this ticker, or it's an ADR/foreign listing."},
        )
    return {"symbol": sym, "found": True, "snapshot": snap}


@router.get("/short/{symbol}/interest")
async def get_short_interest(symbol: str):
    """Bi-monthly FINRA short interest + squeeze gauges (short % of shares
    outstanding, days-to-cover, settlement-over-settlement trend).

    Complements ``/short/{symbol}`` (daily short-sale VOLUME). Returns
    ``{available: False}`` when Massive has no short-interest record (ADRs,
    foreign listings, very thin names).
    """
    sym = symbol.upper()
    data = await asyncio.to_thread(si_client.short_interest_for, sym)
    if not data:
        return JSONResponse({"symbol": sym, "available": False})
    return {**data, "available": True}


@router.get("/short/{symbol}/history")
async def get_short_volume_history(
    symbol: str,
    days: int = Query(30, ge=5, le=180),
):
    """Last `days` daily short-volume records for trend analysis."""
    sym = symbol.upper()
    records = si_client.short_volume_history(sym, days=days)
    return {
        "symbol":  sym,
        "n":       len(records),
        "records": records,
    }
