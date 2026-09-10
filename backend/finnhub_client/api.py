"""HTTP routes for the JIT Finnhub layer.

Mounted at ``/finnhub-v2/...`` so it sits beside the legacy direct
Finnhub calls without conflicting. Existing code paths are untouched —
the frontend opts in by calling these routes from card components when
they enter the viewport.

Routes
------
- ``GET /finnhub-v2/health`` — diagnostics (configured? cache size? recent errors?)
- ``GET /finnhub-v2/quote/{symbol}`` — live snapshot, 60s cache
- ``GET /finnhub-v2/profile/{symbol}`` — company profile, 24h cache
- ``GET /finnhub-v2/news/{symbol}`` — company news (last 7 days), 30min cache
- ``GET /finnhub-v2/earnings/{symbol}`` — next earnings, 6h cache
- ``GET /finnhub-v2/recommendation/{symbol}`` — analyst recs, 24h cache
- ``GET /finnhub-v2/price-target/{symbol}`` — analyst targets, 24h cache
- ``POST /finnhub-v2/cache/clear`` — admin: drop a cached endpoint
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from . import cache as _cache
from . import client as _client

log = logging.getLogger("finnhub_client.api")
router = APIRouter()


@router.get("/finnhub-v2/health")
async def finnhub_v2_health():
    """Quick check: is the layer configured + reachable?"""
    return JSONResponse({
        "configured":  _client.is_configured(),
        "cache":       _cache.stats(),
        "ttl_by_endpoint_sec": {
            ep: _cache.ttl_for(ep)
            for ep in ("quote", "profile", "news", "earnings", "recommendation", "price_target", "search")
        },
    })


def _norm(symbol: str) -> str:
    s = (symbol or "").upper().strip()
    if not s or len(s) > 12:
        raise HTTPException(400, "invalid symbol")
    return s


@router.get("/finnhub-v2/quote/{symbol}")
async def finnhub_v2_quote(symbol: str):
    """Live quote snapshot. JIT-friendly: cache TTL is 60s so rapid UI
    re-renders share one upstream call."""
    sym = _norm(symbol)
    data = await _client.quote(sym)
    if data is None:
        raise HTTPException(503, f"could not fetch quote for {sym}")
    return JSONResponse({"symbol": sym, "data": data, "source": "finnhub-v2"})


@router.get("/finnhub-v2/profile/{symbol}")
async def finnhub_v2_profile(symbol: str):
    """Company profile (name, country, sector, marketCap, etc). 24h cache."""
    sym = _norm(symbol)
    data = await _client.profile(sym)
    if data is None:
        raise HTTPException(503, f"could not fetch profile for {sym}")
    return JSONResponse({"symbol": sym, "data": data, "source": "finnhub-v2"})


@router.get("/finnhub-v2/news/{symbol}")
async def finnhub_v2_news(
    symbol: str,
    days_back: int = Query(7, ge=1, le=30),
):
    """Company news headlines from the last N days (default 7). 30min cache.
    Cap of 30 days because Finnhub's company-news endpoint returns 400 on
    longer windows."""
    sym = _norm(symbol)
    data = await _client.company_news(sym, days_back=days_back)
    if data is None:
        raise HTTPException(503, f"could not fetch news for {sym}")
    return JSONResponse({"symbol": sym, "count": len(data), "rows": data, "source": "finnhub-v2"})


@router.get("/finnhub-v2/earnings/{symbol}")
async def finnhub_v2_earnings(symbol: str):
    """Next earnings event. 6h cache."""
    sym = _norm(symbol)
    data = await _client.earnings_for(sym)
    if data is None:
        raise HTTPException(503, f"could not fetch earnings for {sym}")
    return JSONResponse({"symbol": sym, "data": data, "source": "finnhub-v2"})


@router.get("/finnhub-v2/recommendation/{symbol}")
async def finnhub_v2_recommendation(symbol: str):
    """Analyst recommendation trends. 24h cache."""
    sym = _norm(symbol)
    data = await _client.recommendation(sym)
    if data is None:
        raise HTTPException(503, f"could not fetch recommendation for {sym}")
    return JSONResponse({"symbol": sym, "rows": data, "source": "finnhub-v2"})


@router.get("/finnhub-v2/price-target/{symbol}")
async def finnhub_v2_price_target(symbol: str):
    """Analyst price targets. 24h cache."""
    sym = _norm(symbol)
    data = await _client.price_target(sym)
    if data is None:
        raise HTTPException(503, f"could not fetch price target for {sym}")
    return JSONResponse({"symbol": sym, "data": data, "source": "finnhub-v2"})


@router.post("/finnhub-v2/cache/clear")
async def finnhub_v2_cache_clear(endpoint: str = Query(..., min_length=1)):
    """Drop every cached row for one endpoint. Use after a Finnhub
    schema change or a known cache poisoning."""
    removed = _cache.clear_endpoint(endpoint)
    return JSONResponse({"endpoint": endpoint, "removed": removed})
