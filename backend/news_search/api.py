"""News-search API — the per-ticker ⚖️ bull / bear read.

Two endpoints on one path, and the split is the whole point:

    POST /news/two-sided/{symbol}   may call the model (once per session date,
                                    or every time with ?force=true)
    GET  /news/two-sided/{symbol}   NEVER calls the model — it serves today's
                                    stored doc or says there is not one

A GET that could trigger a model call is a GET that a page-load, a prefetch or
a bot can run up a bill on; the ticker page mounts the button cold and nothing
happens until Ajay clicks it.
"""
from __future__ import annotations

import asyncio
import logging
import math

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from . import two_sided as TS

log = logging.getLogger("news_search.api")

router = APIRouter(tags=["news"])


def _scrub(o):
    """NaN / inf -> None, recursively. A NaN survives `json.dumps` in Python
    and breaks the frontend's `JSON.parse` — the bug that once stuck the SEPA
    scan button on 'Scanning…'."""
    if isinstance(o, dict):
        return {k: _scrub(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_scrub(v) for v in o]
    if isinstance(o, float):
        return None if (o != o or math.isinf(o)) else o
    return o


@router.post("/news/two-sided/{symbol}")
async def post_two_sided(symbol: str, force: bool = Query(False)):
    """Read (or re-read) one ticker's bull case and bear case.

    Off the event loop: the model leg blocks for up to `MODEL_TIMEOUT_SEC` and
    would hold every other request on this worker.
    """
    try:
        out = await asyncio.to_thread(TS.read, symbol, force=force)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("two-sided: read %s failed: %s", symbol, exc)
        out = {"ok": False, "symbol": (symbol or "").upper(),
               "reason": f"read failed: {exc}", "headlines": [],
               "measured": False}
    return JSONResponse(_scrub(out))


@router.get("/news/two-sided/{symbol}")
async def get_two_sided(symbol: str):
    """Today's stored read, or a plain "not read today". No model call."""
    sym = (symbol or "").upper()
    doc = await asyncio.to_thread(TS.cached, sym)
    if doc is None:
        return JSONResponse({"ok": False, "symbol": sym, "date": TS.today_et(),
                             "reason": "not read today", "headlines": [],
                             "measured": False, "cached": False})
    return JSONResponse(_scrub(doc))
