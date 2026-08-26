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
from . import support as support_mod

log = logging.getLogger("chart_maps.api")
router = APIRouter(tags=["chart-maps"])


@router.get("/chart-maps")
async def chart_maps(
    tab: str = Query("vcp", description="vcp | topping | zones | supply | deep_demand | gabbar | zero_dte | earnings | winners"),
    limit: int = Query(board_mod.LIMIT_DEFAULT, ge=1, le=board_mod.LIMIT_MAX),
    days: int = Query(board_mod.BARS_DEFAULT, ge=20, le=board_mod.BARS_MAX),
    universe: str = Query("full",
                          description="zones + supply tabs — one universe since "
                                      "2026-08-25: the SEPA `full` alias. Legacy "
                                      "keys (sp1500_plus, sp500, qqq, ...) fold "
                                      "into it server-side."),
    level: str = Query("all",
                       description="gabbar tab only — measure against one band "
                                   "type: all (default) | aggressive | "
                                   "conservative 1 | conservative 2"),
    touching_only: bool = Query(True,
                                description="gabbar tab only — hide names more "
                                            "than NEAR_PCT from every measured "
                                            "band (default). false = the full "
                                            "distance ladder."),
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
            level=level if isinstance(level, str) else "all",
            touching_only=touching_only if isinstance(touching_only, bool) else True,
        )

    return JSONResponse(await asyncio.to_thread(_run))


@router.get("/chart-maps/support")
async def chart_maps_support(
    symbol: str = Query("", description="any US ticker — the tab searches "
                                        "/symbol-search for it"),
    window: str = Query(support_mod.DEFAULT_WINDOW,
                        description="zoom the structure is read at: "
                                    "1m | 3m | 6m | 1y"),
):
    """Support + overhead levels for ONE ticker at one zoom.

    Unlike the board tabs this computes on request — there is no universe pass
    behind it, just `price_zones` over a 2y frame, so it answers in the time of
    one price load.

    Both arguments are coerced inside the module for the same reason `board()`
    coerces its own: these handlers get called directly in the container for
    smoke tests, and a direct call receives the `Query` OBJECT, which is truthy
    and has no `.lower()`.
    """
    def _run():
        return support_mod.for_symbol(
            symbol if isinstance(symbol, str) else "",
            window if isinstance(window, str) else support_mod.DEFAULT_WINDOW,
        )

    return JSONResponse(await asyncio.to_thread(_run))
