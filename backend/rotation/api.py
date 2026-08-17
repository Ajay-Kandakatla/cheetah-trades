"""Sector rotation API — one read-only endpoint.

Read-only by construction: nothing here starts a scan. The tracker reads the
latest SEPA scan for its sector membership and pulls cached price frames, so a
cold call is seconds, not minutes.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from . import backtest as B
from . import tracker as T

log = logging.getLogger("rotation.api")
router = APIRouter(tags=["rotation"])

# Default window start. Ajay 2026-08-16: "From June this happened."
DEFAULT_START = "2026-06-01"

_CACHE_TTL_SEC = 30 * 60
_cache: dict = {}


def _coerce_str(v, fallback: str) -> str:
    """FastAPI resolves Query(...) defaults at REQUEST time, so a direct call
    from a container smoke test receives the Query OBJECT — truthy, with no
    string methods. That bug shipped twice on the demand board; coerce here."""
    return v if isinstance(v, str) and v.strip() else fallback


def _coerce_float(v, fallback: float) -> float:
    return float(v) if isinstance(v, (int, float)) else fallback


@router.get("/rotation")
async def rotation(
    start: str = Query(DEFAULT_START, description="ISO date the window opens on"),
    min_dollar_vol: float = Query(20_000_000.0, ge=0,
                                  description="liquidity floor for sector members"),
    min_price: float = Query(10.0, ge=0, description="price floor for sector members"),
    refresh: bool = Query(False, description="bypass the 30-minute cache"),
):
    """Where money left and where it went, relative to equal-weight.

    Returns sectors, Ajay's build-out themes, and safe-haven proxies, each with
    the window return, 21-day and 63-day, all restated relative to RSP.
    """
    s = _coerce_str(start, DEFAULT_START)
    dv = _coerce_float(min_dollar_vol, 20_000_000.0)
    px = _coerce_float(min_price, 10.0)
    key = (s, dv, px)

    if not (refresh is True):
        hit = _cache.get(key)
        if hit and (time.time() - hit["ts"]) < _CACHE_TTL_SEC:
            return JSONResponse({**hit["data"], "cached": True})

    try:
        data = T.build(start=s, min_dollar_vol=dv, min_price=px)
    except Exception as exc:
        log.warning("rotation: build failed: %s", exc)
        return JSONResponse(
            {"error": f"{type(exc).__name__}: {exc}"[:200], "sectors": [],
             "themes": [], "havens": [], "start": s},
            status_code=503)

    _cache[key] = {"ts": time.time(), "data": data}
    return JSONResponse({**data, "cached": False})


# The backtest is a ~5s full-history refetch, so it is cached hard. The answer
# moves on the scale of months, not minutes.
_BT_TTL_SEC = 12 * 60 * 60
_bt_cache: dict = {}


@router.get("/rotation/backtest")
async def rotation_backtest(refresh: bool = Query(False)):
    """Does rotating into the leading sectors actually pay?

    Measured 2026-08-16 over 116 monthly rebalances back to 2016: top-3 rotation
    158.22%, RSP 155.42%, holding all 11 sectors 163.23%. Mean excess -0.013%
    per period with a 95% interval of [-0.549, +0.522].

    Served next to the tracker on purpose. The tracker describes what already
    moved; this is the evidence that acting on that description does not beat
    owning the market, so the page can say so rather than implying a signal it
    does not have.
    """
    hit = _bt_cache.get("v")
    if hit and not (refresh is True) and (time.time() - hit["ts"]) < _BT_TTL_SEC:
        return JSONResponse({**hit["data"], "cached": True})
    try:
        data = B.run()
        # Per-period rows are debugging detail and dominate the payload; the
        # page reads the summary and the year table.
        data.pop("periods", None)
    except Exception as exc:
        log.warning("rotation: backtest failed: %s", exc)
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}"[:200]},
                            status_code=503)
    _bt_cache["v"] = {"ts": time.time(), "data": data}
    return JSONResponse({**data, "cached": False})
