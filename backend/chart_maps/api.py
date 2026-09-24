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
from . import ema_frames as ema_frames_mod
from . import support as support_mod

log = logging.getLogger("chart_maps.api")
router = APIRouter(tags=["chart-maps"])


@router.get("/chart-maps")
async def chart_maps(
    tab: str = Query("vcp", description="vcp | topping | zones | supply | ict | "
                                        "deep_demand | gabbar | zero_dte | "
                                        "earnings | winners | keltner | amd"),
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
    levels: str = Query("all",
                        description="deep_demand tab only — which ARRIVAL "
                                    "levels to show: all (default) or a "
                                    "comma list of levels, e.g. '3,4' or '4'. "
                                    "Ajay 2026-09-16: 'can you do level 4 and "
                                    "give me filters for that'. Parsed by "
                                    "supply_demand.deep_demand.parse_levels, "
                                    "which FAILS OPEN — an unknown or "
                                    "out-of-range spec serves the full board, "
                                    "never an empty one. Distinct from "
                                    "`level` (singular) above, which is the "
                                    "gabbar tab's band TYPE."),
    phase: str = Query("",
                       description="zones + deep_demand tabs — reached "
                                   "(default: price back inside the band) | "
                                   "approaching (price still above it, close, "
                                   "and falling toward it). Ajay 2026-08-31: "
                                   "'I need the ones that are about to reach "
                                   "and catch them'."),
    target: str = Query("zone",
                        description="zones tab, approaching phase only — which "
                                    "level the approach is measured to: zone "
                                    "(default, the tested demand band) | "
                                    "order_block (a fresh SMC order block; "
                                    "uncited convention)."),
    touching_only: bool = Query(False,
                                description="gabbar tab only — true hides names "
                                            "more than NEAR_PCT from every "
                                            "measured band; default false shows "
                                            "the full distance ladder, in-band "
                                            "first (flipped 2026-08-27)."),
    themes_first: bool = Query(board_mod.THEMES_FIRST_DEFAULT,
                               description="lead with quantum/nuclear/robotics/AI-semis "
                                           "names — OFF by default since 2026-08-17"),
    pattern: Optional[str] = Query(None, description="winners tab only — filter to one pattern"),
    source: str = Query("pattern", description="winners tab only — pattern | zone"),
    minervini_only: bool = Query(False,
                                 description="winners tab only — SEPA qualifiers at the time"),
    flight: str = Query("", description="amd tab — live state filter: "
                                       "sweeping | reclaimed | holding, comma "
                                       "list. Empty = every state."),
    grades: str = Query("", description="amd / keltner tabs — comma list of "
                                       "grades to show, or 'all'. Empty = the "
                                       "turning grade only, as before."),
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
    bias: str = Query("all", description="all | bullish | bearish (ict)"),
    micro: str = Query("60m", description="60m | 15m (ict micro timeframe)"),
    min_room: Optional[float] = Query(None, ge=0, le=50,
                                      description="zones + deep_demand tabs only — hide "
                                                  "tiles with less than this % of room "
                                                  "from the LIVE print to the first "
                                                  "unbroken band overhead; 0 = off; omit "
                                                  "for the house default (alert_gates."
                                                  "ALERT_MIN_ROOM_PCT, 5.0). Ajay "
                                                  "2026-09-05: 'stocks that have more "
                                                  "room atleast >5%'. Other tabs ignore it."),
    studies: bool = Query(False,
                          description="append the AMD / Fibonacci / mean-reversion "
                                      "overlays (Ajay 2026-09-12). Default FALSE: "
                                      "they are uncited, unmeasured, gate nothing, "
                                      "and are off in the UI by default — the "
                                      "frontend asks for them only when one of the "
                                      "three checkboxes is on."),
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
            levels=levels if isinstance(levels, str) else "all",
            touching_only=touching_only if isinstance(touching_only, bool) else False,
            phase=phase if isinstance(phase, str) else "",
            target=target if isinstance(target, str) else "zone",
            bias=bias if isinstance(bias, str) else "all",
            micro=micro if isinstance(micro, str) else "60m",
            grades=(grades if isinstance(grades, str) and grades.strip() else None),
            flight=(flight if isinstance(flight, str) and flight.strip() else None),
            studies=studies is True,
            min_room=(float(min_room) if isinstance(min_room, (int, float))
                      and not isinstance(min_room, bool) else None),
        )

    return JSONResponse(await asyncio.to_thread(_run))


@router.get("/chart-maps/support")
async def chart_maps_support(
    symbol: str = Query("", description="any US ticker — the tab searches "
                                        "/symbol-search for it"),
    window: str = Query(support_mod.DEFAULT_WINDOW,
                        description="zoom the structure is read at: "
                                    "1w | 2w | 1m | 3m | 6m | 1y | 2y | 3y "
                                    "| 5y | all"),
    tf: str = Query(support_mod.TF_DEFAULT,
                    description="bar timeframe the structure is read on: "
                                "daily | 60m | 15m"),
    studies: bool = Query(False,
                          description="append the AMD / Fibonacci / "
                                      "mean-reversion / Keltner study overlays"),
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
        res = support_mod.for_symbol(
            symbol if isinstance(symbol, str) else "",
            window if isinstance(window, str) else support_mod.DEFAULT_WINDOW,
            tf if isinstance(tf, str) else support_mod.TF_DEFAULT,
        )
        # Extended hours (Ajay 2026-09-08, ORCL): the tile's `now` line moves
        # to the live print and says which tape — the same overlay every
        # board tab gets at the end of board().
        tile = res.get("tile") if isinstance(res, dict) else None
        if isinstance(tile, dict):
            # ONE live fan-out for the one tile, shared by the now-line and
            # the 🎯 read (2026-09-15) exactly as board() shares it.
            try:
                live = board_mod._live_snapshot([tile])
            except Exception as exc:                        # pragma: no cover
                log.debug("chart-maps/support: live snapshot failed: %s", exc)
                live = {}
            try:
                board_mod.attach_live_now([tile], res, live=live)
            except Exception as exc:                        # pragma: no cover
                log.debug("chart-maps/support: live now-line failed: %s", exc)
            # 🎯 ENTERABLE on the Support tab: one symbol, so the page shows the
            # chip and never hides the row (the filter is a Chart Maps grid
            # control). Same read, same live print, after the now-line.
            try:
                from supply_demand import enterable as EN
                board_mod.attach_enterable([tile], kind=EN.KIND_DEMAND, live=live)
                res["enterable_kind"] = EN.KIND_DEMAND
            except Exception as exc:                        # pragma: no cover
                log.debug("chart-maps/support: enterable failed: %s", exc)
            # 🪜 BAND STRUCTURE on the Support tab (2026-09-16): one symbol, so
            # there is nothing to order — the page gets the ceiling/floor stat
            # and the banner only. Same read, same live print, after the
            # now-line, exactly as the 🎯 read above.
            #
            # THE BANNER IS SET FIRST, and the attach only runs if it landed
            # (critique m3). Both statements used to sit in ONE try in the
            # other order, so a raise from `measured_verdict()` left the tile
            # carrying the read — the chip renders — and the payload with no
            # verdict, i.e. an UNMEASURED read wearing a validated face on an
            # error path. The chip may never outlive its banner; the banner
            # without a chip is only a tile with no bands, which is a state
            # this page already has.
            try:
                from supply_demand import band_structure as BS
                _bs_kind = BS.kind_for_tab("support")
                res["band_structure_study"] = BS.measured_verdict()
                res["band_structure_kind"] = _bs_kind
            except Exception as exc:                        # pragma: no cover
                log.debug("chart-maps/support: band structure verdict failed: %s", exc)
            else:
                try:
                    board_mod.attach_band_structure([tile], kind=_bs_kind, live=live)
                    # 🪜 COVERAGE (critique J2, 2026-09-16). ONE tile here, so
                    # the note fires exactly when THIS name has no read — the
                    # BTBT case: a position of his the zone store does not
                    # carry drew a tile with no Bands line and no reason, while
                    # the ten row boards served him the read for the same name
                    # on the same day. The sentence is the row boards' own
                    # (`bounce_room.band_structure_no_read_note`, served, never
                    # typed in the TSX) and it distinguishes a name that is
                    # still warming from one under the store's cap floor
                    # (`zone_store.MIN_CAP_USD` — BTBT is under it, so no
                    # refresh can bring it a read). 📁 My holdings reads the
                    # note off this same response, one per position.
                    res["band_structure_coverage"] = board_mod.band_structure_coverage(
                        [tile], kind=_bs_kind)
                except Exception as exc:                    # pragma: no cover
                    log.debug("chart-maps/support: band structure failed: %s", exc)
            # THE BUG AJAY HIT THREE TIMES (2026-09-12): "Still not seeing, AMD
            # or keltners indicators. Whts going on?"
            #
            # The overlay ledger renders the four study groups on EVERY surface
            # that mounts it, because they are declared `always: true` in
            # chartOverlays.ts — so on this tab he saw four checkboxes, ticked
            # them, and nothing drew. It was never a stale tab: this endpoint
            # had no `studies` parameter at all, so the payload could not carry
            # an AMD band or a fib line no matter what the checkbox said. Proven
            # on DBRG: the tile came back with tones {neutral, now, target} and
            # bands {demand, order_block} and nothing else.
            #
            # Same helper the board tabs use, so the two surfaces cannot draw a
            # different Fibonacci for one name. Soft-fails per tile.
            # DAILY ONLY (2026-09-14). The studies are computed from the daily
            # frame; on tf=60m/15m they were painted across an hourly chart
            # at daily prices (CRDO: KC upper 223.51 daily vs 165.0 hourly),
            # and the curves silently vanished because intraday bars carry a
            # time in `t`. Until they are computed on the analysed frame, an
            # intraday tile says so instead of drawing the wrong numbers.
            if studies is True and res.get("timeframe") not in (None, "daily"):
                # The BAR SIZE, not the job name: "not drawn on the The last
                # two weeks chart" is not a sentence (2026-09-23).
                res["studies_note"] = ("AMD / Fibonacci / mean reversion / Keltner "
                                       "are daily-frame studies — not drawn on the "
                                       f"{res.get('timeframe_bar_label') or res.get('timeframe')} chart.")
            elif studies is True:
                try:
                    # `bars_used` is the key the support payload actually
                    # carries. This read `bars`/`days`, which do not exist, so
                    # the zoom cut never ran: the "mean of the visible window"
                    # was a 2-year regression drawn over a 1-month chart, and
                    # every study line was identical at 1m/6m/1y (CRDO,
                    # 2026-09-14). The verdict still reads the full frame.
                    board_mod._attach_studies(
                        {"tiles": [tile]},
                        int((res.get("bars_used") or res.get("bars")
                             or res.get("days") or 0) or 0),
                        raids=True)
                except Exception as exc:                    # pragma: no cover
                    log.debug("chart-maps/support: studies failed: %s", exc)
        return res

    return JSONResponse(await asyncio.to_thread(_run))


@router.get("/chart-maps/ema-frames")
async def chart_maps_ema_frames(
    symbol: str = Query("", description="one US ticker"),
    frame: str = Query(ema_frames_mod.DEFAULT_FRAME,
                       description="weekly (default) | monthly — the bar "
                                   "size the 9 EMA is computed on. Ajay "
                                   "2026-09-23: 'a new tab for 9EMA lines on "
                                   "our charts for weekly charts and monthly "
                                   "charts'."),
):
    """〰️ The 9 EMA on WEEKLY or MONTHLY bars, for ONE ticker.

    One cached daily frame, resampled — there is no universe pass behind this
    and no scan is ever started by it. The tab calls it once per name on his
    ⚡ Signals watchlist, exactly as \U0001F4C1 My holdings calls
    /chart-maps/support once per position.

    Both arguments are coerced inside the module, the house rule: these
    handlers get called directly in the container for smoke tests and a direct
    call receives the `Query` OBJECT, which is truthy and has no `.lower()`.
    """
    def _run():
        return ema_frames_mod.build(
            symbol if isinstance(symbol, str) else "",
            frame if isinstance(frame, str) else ema_frames_mod.DEFAULT_FRAME)

    return JSONResponse(await asyncio.to_thread(_run))


@router.get("/chart-maps/news")
async def chart_maps_news():
    """📰 News tab (Ajay 2026-09-24). Four served reads, one payload. The market word is the
    Market Gauge's own state mapped once in news_tab.MARKET_WORD — nothing invented. The macro
    rows are the calendar at its ONE cache key (macro_calendar.DEFAULT_DAYS): this route takes
    NO window parameter so it can never evict the gauge's 14-day doc or reach the padding
    defect at 21+ days. Gates nothing, pushes nothing, ranks nothing."""
    from rotation.api import _scrub
    from . import news_tab
    return JSONResponse(_scrub(await news_tab.build()))


@router.get("/chart-maps/ipo/upcoming/{symbol}")
async def chart_maps_ipo_upcoming(symbol: str):
    """🗓️ "Coming up" drill-in — the fact sheet for ONE expected listing.

    Ajay 2026-09-20: *"Can you gather similar info about these please like the
    ticket and make them clicable the onesin IPO tab that are future"*.

    Fetched on a CLICK and nowhere else: `board()` never calls this, because a
    cold open costs three to four rate-paced EDGAR GETs and a multi-megabyte
    download, which is not something a board load may pay per row.

    Nothing here is measured, nothing here is an LLM summary, and no number
    ever leaves the registration filing — the revenue and net-loss lines are
    sentences the prospectus printed, with their own units and period headers
    beside them.

    503 — Finnhub's calendar could not be read, so the symbol cannot be looked
    up at all. 404 — the calendar was read and this symbol is not an expected
    listing inside the forward window; a deal Finnhub flips to `priced` leaves
    the strip and answers 404 here.
    """
    from . import ipo as IPO
    from . import ipo_upcoming as IU

    sym = (symbol if isinstance(symbol, str) else "").strip().upper()
    row, cal_ok, reason = await asyncio.to_thread(IU.calendar_row, sym)
    if row is None:
        if not cal_ok:
            return JSONResponse(
                status_code=503,
                content={"detail": f"Finnhub's IPO calendar could not be read "
                                   f"({reason}), so {sym} cannot be looked up "
                                   f"right now."})
        return JSONResponse(
            status_code=404,
            content={"detail": f"{sym} is not an expected listing in the next "
                               f"{IPO.FORWARD_DAYS} days on Finnhub's IPO "
                               f"calendar."})
    return JSONResponse(await IU.lookup(sym, row))
