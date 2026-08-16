"""Chart Maps API — one read-only board endpoint per tab.

Read-only by construction: nothing here starts a scan. The demand tab warms in
the background and answers `warming: true` immediately, so a page load cannot
sit behind a multi-minute universe pass.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from . import board as board_mod

log = logging.getLogger("chart_maps.api")
router = APIRouter(tags=["chart-maps"])


@router.get("/chart-maps")
async def chart_maps(
    tab: str = Query("vcp", description="vcp | zones | winners"),
    limit: int = Query(board_mod.LIMIT_DEFAULT, ge=1, le=board_mod.LIMIT_MAX),
    days: int = Query(board_mod.BARS_DEFAULT, ge=20, le=board_mod.BARS_MAX),
    universe: str = Query("sp1500_plus",
                          description="zones tab only — sp1500_plus (default) | "
                                      "sp1500 | sp500 | themes"),
    themes_first: bool = Query(True,
                               description="lead with quantum/nuclear/robotics/AI-semis names"),
    pattern: Optional[str] = Query(None, description="winners tab only — filter to one pattern"),
):
    """Chart-ready tiles for one tab.

    Every argument is coerced inside `board()` rather than trusted here: these
    handlers get called directly in the container for smoke tests, and FastAPI
    resolves `Query(...)` defaults at REQUEST time, so a direct call receives
    the Query OBJECT — which is truthy and has no `.lower()`. That bug shipped
    twice on the demand board (2026-08-14); the coercion lives in one place now.
    """
    def _run():
        return board_mod.board(
            tab=tab if isinstance(tab, str) else "vcp",
            limit=limit if isinstance(limit, int) else board_mod.LIMIT_DEFAULT,
            days=days if isinstance(days, int) else board_mod.BARS_DEFAULT,
            universe=universe if isinstance(universe, str) else "sp1500_plus",
            themes_first=themes_first if isinstance(themes_first, bool) else True,
            pattern=pattern if isinstance(pattern, str) else None,
        )

    return JSONResponse(await asyncio.to_thread(_run))
