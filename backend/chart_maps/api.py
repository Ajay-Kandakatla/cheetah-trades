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
    themes_first: bool = Query(board_mod.THEMES_FIRST_DEFAULT,
                               description="lead with quantum/nuclear/robotics/AI-semis "
                                           "names — OFF by default since 2026-08-17"),
    pattern: Optional[str] = Query(None, description="winners tab only — filter to one pattern"),
    source: str = Query("pattern", description="winners tab only — pattern | zone"),
    minervini_only: bool = Query(False,
                                 description="winners tab only — SEPA qualifiers at the time"),
    min_tier: str = Query(board_mod.DEFAULT_MIN_TIER,
                          description="liquidity floor by 50-day avg $ volume: "
                                      "deep (>=$50M) | ok (>=$10M, default) | "
                                      "thin (>=$2M) | any. Same scale as the "
                                      "Back in Demand tiers."),
    sort: str = Query(board_mod.DEFAULT_SORT,
                      description="theme (default) | volume | rvol | turnover | "
                                  "avg_turnover | conviction | rs | change. Applied "
                                  "BEFORE the per-theme cap and the bar fetch, so it "
                                  "ranks every match rather than reordering the page."),
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
            source=source if isinstance(source, str) else "pattern",
        minervini_only=minervini_only if isinstance(minervini_only, bool) else False,
        universe=universe if isinstance(universe, str) else "sp1500_plus",
            themes_first=themes_first if isinstance(themes_first, bool) else board_mod.THEMES_FIRST_DEFAULT,
            pattern=pattern if isinstance(pattern, str) else None,
            sort=sort if isinstance(sort, str) else board_mod.DEFAULT_SORT,
            min_tier=min_tier if isinstance(min_tier, str) else board_mod.DEFAULT_MIN_TIER,
        )

    return JSONResponse(await asyncio.to_thread(_run))
