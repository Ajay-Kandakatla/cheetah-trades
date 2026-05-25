"""HTTP routes for the macro-context module.

Two endpoints:

  GET /macro/{symbol}                  → cached macro brief
  GET /macro/{symbol}?force=true       → bypass cache + regenerate

Both responses share the shape documented in store.get_macro_context.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from . import store

log = logging.getLogger("macro.api")

router = APIRouter()


@router.get("/macro/{symbol}")
async def macro_for_symbol(
    symbol: str,
    force: bool = Query(False, description="Bypass cache and regenerate"),
):
    """Return the cached/freshly-generated macro brief for one ticker.

    Threaded — store.get_macro_context does sync Mongo + a sync requests
    call to Claude (~5-10s) + a sync helper that pulls recent news. We
    don't want any of that on the event loop, especially the Claude
    HTTP call.
    """
    payload = await asyncio.to_thread(store.get_macro_context, symbol, force=force)
    return JSONResponse(payload)
