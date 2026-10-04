"""Short volume debug + drill API.

Endpoints:

  GET /short/{symbol}
      Latest cached snapshot for `symbol`. ~5ms on cache hit, ~300ms on miss.
      Used by the frontend chip + drill modal.

  GET /short/{symbol}/history?days=30
      Last `days` records (default 30). Used by sparkline trend rendering.

  GET /short-interest/map?symbols=A,B,C   (2026-10-03)
      🩳 Short INTEREST (bi-monthly FINRA settlement) for up to
      `read.MAP_MAX_SYMBOLS` names — the ONE bulk read behind the chip on
      every Chart Maps tab and the ticker page. ONE `$in` read of the
      `short_interest_latest` cache via `short_interest.read.si_map`, off the
      event loop; never a provider call. A name with no cached doc is absent.

The short-VOLUME paths go through `short_interest.client`, which manages the
1-day Mongo cache. `/short/{symbol}/interest` is the older live per-name read
(two provider calls per hit); the chip and the ticker page never use it.
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


@router.get("/short-interest/map")
async def short_interest_read_map(
    symbols: str = Query("", description="comma-separated tickers; first 200 read"),
):
    """🩳 Served short-interest blocks for a batch of names (display only).

    Every word and number is built by `short_interest.read`; the front end
    prints `chip` / `title` / `rows` verbatim. Never fetches from the provider.
    """
    from short_interest import read as SR
    syms = [s.strip().upper() for s in (symbols or "").split(",") if s.strip()]
    items = await asyncio.to_thread(SR.si_map, syms)
    return {"items": items, "n": len(items), "max_symbols": SR.MAP_MAX_SYMBOLS}


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
