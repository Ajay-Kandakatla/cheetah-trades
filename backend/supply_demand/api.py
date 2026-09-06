"""FastAPI handlers for the supply/demand module."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import dependencies as deps
from . import sectors as sec
from . import news as news_mod
from . import tracker as tr
from . import whales as whales_mod
from . import whales_13d as whales_13d_mod
from . import flow as flow_mod
from . import equity_premium as equity_premium_mod
from . import stock_supply_demand as stocks_mod
from . import demand_zones as zones_mod
from . import price_zones as price_zones_mod
from . import timeframes as tf_mod
from . import demand_reentry as reentry_mod
from . import session_board as session_mod
from . import zone_edge as zone_edge_mod
from . import bounce_room as bounce_room_mod
from . import alert_status as alert_status_mod

log = logging.getLogger("supply_demand.api")
router = APIRouter(tags=["supply-demand"])


@router.get("/supply-demand/session-board")
async def get_session_board(
    tf: str = Query("15m", description="analysis timeframe: 15m (default) | 60m"),
    universe: str = Query("full", description="same universe key the demand boards use"),
    orb_minutes: int = Query(15, ge=1, le=120,
                             description="opening-range window in 1-minute bars"),
    limit: int = Query(session_mod.MAX_SYMBOLS, ge=1, le=300),
    force: bool = Query(False, description="bypass the 3-minute cache and re-read"),
):
    """ORB / fair-value gaps / SMC / market mood for every name already on the
    Back in Demand and Deep Demand boards.

    Ajay 2026-08-31: *"a tab for ORB/ FVG/ Bullish sentiment or bearish for all
    the onces in demand zone. and deep demand zones ... I will use this tab
    after market open to figure out market sentiment."*

    The daily boards answer WHICH NAMES. This answers whether the session is
    confirming the daily band that listed them: mood on intraday bars, where
    price sits against the opening range, unfilled imbalances (with the ones
    left by THIS session called out separately), and the complete
    sweep -> BOS -> order-block -> FVG sequence where one exists.

    Never blocks (Cloudflare 524, 2026-08-14): a cold pass warms in a thread
    and this returns `warming: true`. Poll `/session-board/progress`.

    Out of session it shows the LAST session and says so via `live: false` —
    the read is still the honest one, it is just not today's.
    """
    if force:
        import asyncio
        return await asyncio.to_thread(session_mod.scan, universe, tf,
                                       limit=limit, orb_minutes=orb_minutes)
    return session_mod.cached_or_warm(universe, tf, limit=limit,
                                      orb_minutes=orb_minutes)


@router.get("/supply-demand/session-board/progress")
async def get_session_board_progress(
    tf: str = Query("15m"),
    universe: str = Query("full"),
):
    """Live counter for a warming session pass. `phase: idle` when nothing runs."""
    return session_mod.progress_for(universe, tf)


@router.get("/supply-demand/session-board/{symbol}")
async def get_session_board_symbol(
    symbol: str,
    tf: str = Query("15m"),
    orb_minutes: int = Query(15, ge=1, le=120),
):
    """One name's session read — the same row the board renders.

    Exists so the drill-in and the board can never disagree: both call
    `session_board.read_symbol`.
    """
    import asyncio
    return await asyncio.to_thread(session_mod.read_symbol,
                                   symbol.upper(), None, tf=tf,
                                   orb_minutes=orb_minutes)


@router.get("/supply-demand/demand-reentry")
async def get_demand_reentry(
    limit: int = Query(60, ge=1, le=500),
    force: bool = Query(False, description="bypass the 3h cache and rescan"),
    universe: str = Query("sp1500", description="sp1500 (default) | sp500 | sp400 | sp600"),
    min_rr: Optional[float] = Query(None, ge=0, le=10,
                                    description="reward:risk floor; 0 = off, "
                                                "omit for the house default (1.0)"),
    min_room: float = Query(reentry_mod.MIN_ROOM_DEFAULT, ge=0, le=50,
                            description="room floor: % from the LIVE print to the "
                                        "first unbroken band overhead; rows under "
                                        "it are dropped (dropped_low_room). 0 = off "
                                        "(every row still carries `room`). Default "
                                        "= alert_gates.ALERT_MIN_ROOM_PCT (5.0)."),
):
    """Names that have pulled back DOWN into a tested demand band while the
    structure still holds ("entering back into demand").

    A *transition* read, not a snapshot: the name must have traded at least
    `min_rise_above_pct` ABOVE the band top inside the lookback window and be
    back inside it now, on a band tested >= `min_touches` times, and must pass
    the falling-knife guard (swing lows stepping down AND a falling 50-day
    disqualifies it). Each row carries a trade plan — entry band, stop under
    the floor, target at the nearest overhead supply — plus the reasons it
    qualified, so the list is auditable.

    `universe`: sp500 (default) | sp1500 | sp400 | sp600. sp1500 adds the
    ~1,000 S&P MidCap + SmallCap names beyond the S&P 500 (2026-08-13).

    `min_room` (2026-09-05): every row (and deep row) carries `room` — the %
    from the live print (basis "live"; the scan price, basis "scan", when the
    tape has nothing) to the first unbroken band overhead, the entry band
    excluded — and rows under the floor are dropped like the R:R floor drops.
    Ajay, TRU: "It already gapped up very close to the resistance. Why is it
    still in in Demand page? There is only 0.5% room". Owner setting, S&D
    scope; the number is the phone gate's ALERT_MIN_ROOM_PCT.

    Independent of the Minervini/SEPA stack. Configured price-structure method
    (NOT a book method) — decision-support only, not a buy signal, not advice.
    See backend/supply_demand/demand_reentry.py.
    """
    import asyncio
    # Never block the request on a cold pass — a full sp1500 scan is minutes
    # and Cloudflare cuts at ~100s (the 524 of 2026-08-14). `force` still runs
    # inline for the Scan button, which the UI shows a spinner for.
    room = min_room if isinstance(min_room, (int, float)) else reentry_mod.MIN_ROOM_DEFAULT
    if force is True:
        data = await asyncio.to_thread(reentry_mod.scan, True, None, universe)
        return await asyncio.to_thread(reentry_mod.read_view, data, min_rr, room, limit)
    return await asyncio.to_thread(reentry_mod.cached_or_warm, universe, limit, min_rr, room)


@router.get("/supply-demand/demand-reentry/progress")
async def get_demand_reentry_progress(
    universe: str = Query("sp1500", description="sp1500 (default) | sp500 | sp400 | sp600"),
):
    """What the Back in Demand scan for `universe` is doing RIGHT NOW.

    Ajay 2026-08-17: *"I am looking at this and its hard to tell if its scanning
    or now"*. The board's own counters (`n`, `scanned`) only exist in the final
    payload, so for the ~2-3 minutes of a cold sp1500 pass the page could only
    show a static sentence — indistinguishable from a hang.

    Deliberately NOT the SEPA scan stream: that watches `/sepa/scan/stream`, a
    different scan over a different universe. This board runs its own pass.

    Cheap enough to poll every second or two — it reads one dict and takes no
    lock, so a progress poll can never slow the scan it is watching. Phases:
    idle → universe → scanning → enriching → done (or failed).
    """
    return reentry_mod.progress_for(universe)


@router.post("/supply-demand/demand-reentry/scan")
async def post_demand_reentry_scan(
    limit: int = Query(60, ge=1, le=500),
    universe: str = Query("sp1500", description="sp1500 (default) | sp500 | sp400 | sp600"),
    min_rr: Optional[float] = Query(None, ge=0, le=10,
                                    description="reward:risk floor; 0 = off"),
    min_room: float = Query(reentry_mod.MIN_ROOM_DEFAULT, ge=0, le=50,
                            description="room floor (% to the first unbroken band "
                                        "overhead, live print); 0 = off"),
):
    """Force a fresh demand-zone re-entry scan (the page's Scan button).
    Bypasses the 3h cache. sp1500 covers ~1,500 names."""
    import asyncio
    # The floors are applied AFTER the scan, never inside it: `limit` must cut
    # the list that already cleared them, or a strict floor returns a short page
    # while qualifying rows sit just past the limit (read_view keeps the order).
    room = min_room if isinstance(min_room, (int, float)) else reentry_mod.MIN_ROOM_DEFAULT
    data = await asyncio.to_thread(reentry_mod.scan, True, None, universe)
    return await asyncio.to_thread(reentry_mod.read_view, data, min_rr, room, limit)


@router.get("/supply-demand/zone-edge")
async def get_zone_edge():
    """The zone-edge board: $1B+ names within 1% of BREAKING their last supply
    band toward new highs, and names inside / within 1% above a demand level —
    as of the last one-minute pass, with the day's minute-by-minute distance
    track per name.

    Ajay 2026-09-03: *"stocks that are <1% away from breaking supply zones
    which are going for new highs ... and stocks that are just <1% away from
    Demand zones. I need you to give me an alert and also to track these min
    on min."*

    Read-only: the cron (`supply_demand.zone_edge`, every minute in RTH)
    writes `zone_edge_latest` + `zone_edge_track`; this route joins them.
    `in_session` is evaluated at request time; `as_of` null = no pass yet.
    Rows: `breaking` (tier near | broke; broke first, new_highs first, then
    distance) and `near_demand` (tier in | near; arrivals first, then
    distance). `track["supply:SYM"]` / `track["demand:SYM"]` = up to the last
    30 `[HH:MM, dist_pct]` points today.

    Configured price-structure heuristic (zone_store bands), NOT a book method
    — decision-support only, not a buy signal, not advice. See
    backend/supply_demand/zone_edge.py and docs/supply_demand/zone_edge.md.
    """
    import asyncio
    return await asyncio.to_thread(zone_edge_mod.api_payload)


@router.get("/alerts/status")
async def get_alerts_status():
    """What each Supply & Demand push pass did last, so the /alerts page can
    say WHY the phone was quiet.

    Ajay 2026-09-05: *"Do we have the same logic in back end demand for the
    ones that I get alerts. Would it be the same list of stocks.. Also can I
    go to a dedicated page to see the list of alerts?"* — no: the Demand board
    is a closed-bar scan with an R:R floor; the phone gets a live, $1B+, gated
    subset (alert_gates). This route returns the gate numbers and the last
    pass's counters per kind (`zone_edge` from `zone_edge_latest`,
    `zone_bounce_alert` / `demand_alert` from `alert_pass_latest`): candidates,
    priced, skipped_room / skipped_cap / unknown_cap / skipped_proximity,
    pushed. `as_of` null + counts {} = no pass recorded. `in_session` is
    evaluated at request time; times are ET.

    Read-only. Configured heuristic, NOT a book method — decision-support
    only, not a buy signal, not advice. See
    backend/supply_demand/alert_status.py and docs/supply_demand/alerts_page.md.
    """
    import asyncio
    return await asyncio.to_thread(alert_status_mod.status_payload)


class BounceRoomBody(BaseModel):
    """POST body for /supply-demand/bounce-room — {"symbols": ["AVGO", ...]}."""
    symbols: list[str]


async def _bounce_room(raw_symbols: list) -> dict:
    """Shared by POST and GET: upper-case + dedupe, cap MAX_SYMBOLS, 422 on
    empty, then the read off the event loop (one store read + one chunked
    snapshot; misses go to the background worker as `pending`)."""
    import asyncio
    syms = bounce_room_mod.normalize_symbols(raw_symbols, cap=bounce_room_mod.MAX_SYMBOLS)
    if not syms:
        raise HTTPException(status_code=422, detail="symbols: at least one ticker is required")
    return await asyncio.to_thread(bounce_room_mod.api_payload, syms)


@router.post("/supply-demand/bounce-room")
async def post_bounce_room(body: BounceRoomBody):
    """Bounce-off-demand + room-to-supply read for a list of symbols — the
    one read behind the SEPA "bouncing off demand" filter, the Back in
    Demand sort and the Catalysts sort.

    Ajay 2026-09-05: *"The Filter need to check. #1 for Sepa stocks that is
    bouncing off of Demand zone. #2 for in demand Make sure you sort stocks
    by bouncing off of demand zone and have big gap in to supply. #3 for
    catalyst same deal make sure you sort stocks by bigger gaps in to supply
    like EOSE stock and CLYM as an example they have bigger gap and room to
    grow."*

    Body `{"symbols": [...]}` (<= 2500, upper-cased, de-duplicated; 422 when
    empty). Rows keyed by symbol: `coverage` store | ondemand | pending |
    unavailable; `bounce` (null = not bouncing) with the touched band, its
    role (demand | broken_supply), touch_low/date, sessions_ago, bounce_pct,
    strong; `room` with state CLEAR | IN_BAND | NEAR | ROOM, room_pct (null
    only for CLEAR), atr_days, the first overhead band, at_highs. `fresh`
    false = the print is older than 3 min (still shown, never dropped).
    Bands are the zone_store's for the LATEST stored day <= today
    (`store_date`), so weekends answer with Friday's bands. Whole response
    cached 30 s per symbol set; a pending row is a queued on-demand doc,
    never a CLEAR.

    Configured price-structure heuristic, S/D scope, NOT a book method, no
    Minervini cites — decision support, not a buy signal, not advice. See
    backend/supply_demand/bounce_room.py and docs/supply_demand/bounce_room.md.
    """
    return await _bounce_room(list(body.symbols or []))


@router.get("/supply-demand/bounce-room")
async def get_bounce_room(
    symbols: str = Query(..., description="comma-separated tickers (short lists; POST for many)"),
):
    """GET twin of POST /supply-demand/bounce-room for short lists
    (`?symbols=EOSE,CLYM`). Same function, same payload, same 422 on empty.
    Not advice — see the POST route's docstring."""
    return await _bounce_room([s for s in (symbols or "").split(",")])


@router.get("/supply-demand/demand-reentry/history")
async def get_demand_reentry_history(
    universe: Optional[str] = Query(None, description="sp1500 | sp500 | … ; omit for all"),
    symbol: Optional[str] = Query(None, description="one name's episodes instead of the board"),
    runs: int = Query(30, ge=1, le=200, description="how many past boards to return"),
    min_rr: Optional[float] = Query(None, ge=0, le=10,
                                    description="re-slice the aggregate by R:R floor"),
):
    """The live track record of the Back in Demand board.

    Ajay 2026-08-17: *"Can you maintain history of our In deman page please… I
    saw CIEN you recommended is bouncing out of the zone now… Want you to track
    it"*.

    Three views in one payload: `accuracy` (did it work), `runs` (what the
    board said each day, with entered/dropped churn), and — when `symbol` is
    given — that name's own episodes.

    Distinct from `zone_backtest`, which re-derives the past from today's
    universe and is re-run whenever the rule changes. This is what the page
    ACTUALLY published, graded at the next session's open against a plan frozen
    at first sight, so it starts at the day recording began and cannot be
    rewritten by a later tweak to the rule.

    Read `excess_vs_spy_pct`, not `win_pct`: a dip-buying board in a rising
    tape shows profits with or without skill. Small n early.
    """
    import asyncio
    from . import demand_history as dh
    out = await asyncio.to_thread(dh.accuracy, universe, min_rr)
    out["runs"] = (await asyncio.to_thread(dh.runs, universe, runs)).get("runs", [])
    if symbol:
        out["symbol_history"] = await asyncio.to_thread(dh.for_symbol, symbol, universe)
    return out


@router.get("/supply-demand/trade-flash")
async def trade_flash_today():
    """Today's zone-tied tape bursts (Ajay 2026-08-24: Trade Flash "with in the
    Demand Zone tabs"). Read-only view over what the cron watch recorded —
    serving it never triggers a scan or a tape fetch."""
    from orderflow import trade_flash
    return trade_flash.today_events()


@router.get("/supply-demand/accumulation-changes")
async def accumulation_changes(limit: int = Query(50, ge=1, le=200)):
    """Quarter-over-quarter institutional flow changes already detected.

    Ajay 2026-08-16: "give me updated and notification as Accumulations change
    as money moving I need a comparison." Written by the Sunday sweep; this
    only reads. 13F lags up to 45 days — context for a setup, never a trigger."""
    import asyncio
    from . import accumulation_changes as acc
    n = limit if isinstance(limit, int) else 50
    rows = await asyncio.to_thread(acc.recent, n)
    return JSONResponse({"n": len(rows), "changes": rows,
                         "min_usd": acc.MIN_NET_CHANGE_USD,
                         "min_pct": acc.MIN_NET_CHANGE_PCT})


@router.get("/supply-demand/accumulation-changes/{symbol}")
async def accumulation_change_for(symbol: str):
    """The live quarter-over-quarter comparison for one ticker — money in/out,
    new buyers, exits, each scoped to a single filing quarter."""
    import asyncio
    from . import accumulation_changes as acc
    return JSONResponse(await asyncio.to_thread(acc.for_symbol, symbol))


@router.get("/supply-demand/zone-map/{symbol}")
async def get_zone_map(
    symbol: str,
    tf: str = Query("daily", description="bar timeframe the bands are read "
                                         "on: daily | 60m | 15m"),
):
    """One ticker's supply/demand bands + close series + entry/stop/target plan
    — everything the individual-stock zone chart draws. Works for any symbol,
    including names that are NOT re-entry candidates (price sitting in overhead
    supply still gets its bands and a plan drawn)."""
    import asyncio
    out = await asyncio.to_thread(reentry_mod.analyze_symbol, symbol, True)
    if not out:
        return {"symbol": (symbol or "").upper(), "error": "no / insufficient price data"}
    # Timeframe overlay (Ajay 2026-08-29: "also the supply demand tab in
    # individual ticker"). The daily re-entry read is unchanged underneath;
    # the chosen timeframe's bands, gaps, opening range and computed
    # entry/stop ride alongside it.
    out["timeframes"] = tf_mod.tf_options()
    key = tf_mod.parse_tf(tf if isinstance(tf, str) else "daily")
    out["timeframe"] = key
    out["timeframe_label"] = tf_mod.tf_spec(key)["label"]
    try:
        zoned = await asyncio.to_thread(
            price_zones_mod.for_symbol, symbol, None, key)
        if not zoned.get("error"):
            out["tf_bands"] = [
                {"kind": z.get("kind"), "lo": z.get("lo"), "hi": z.get("hi")}
                for z in (list(zoned.get("demand_zones") or [])
                          + list(zoned.get("supply_zones") or []))]
            for k in ("trade_levels", "fair_value_gaps", "opening_range", "atr"):
                out[k] = zoned.get(k)
        else:
            out["tf_error"] = zoned["error"]
    except Exception as exc:                                # pragma: no cover
        log.warning("zone-map: timeframe overlay for %s failed: %s", symbol, exc)
    return out


@router.get("/supply-demand/price-zones/{symbol}")
async def get_price_zones(
    symbol: str,
    tf: str = Query("daily", description="bar timeframe the structure is "
                                         "read on: daily | 60m | 15m"),
):
    """On-demand per-ticker supply/demand price zones + an entry read. Swing-high
    clusters = overhead supply (resistance), swing-low clusters = demand (support),
    weighted by tests + volume; reports nearest resistance/support vs the live
    close and a plain 'favorable / caution / neutral' entry read. Configured
    price-structure method (NOT a book method); decision-support only, not advice.
    See backend/supply_demand/price_zones.py."""
    import asyncio
    return await asyncio.to_thread(
        price_zones_mod.for_symbol, symbol, None,
        tf if isinstance(tf, str) else "daily")


@router.get("/supply-demand/stocks")
async def get_stock_supply_demand(
    mode: str = Query("broad", description="universe: broad | russell1000 | curated | sp500 …"),
    min_dollar_vol: float = Query(3_000_000.0, ge=0, description="drop tape thinner than this avg $/day"),
    state: Optional[str] = Query(None, description="filter: demand | supply | churning"),
    limit: int = Query(300, ge=1, le=4000),
    force: bool = Query(False, description="bypass the cache and recompute"),
):
    """Per-stock supply/demand screen — Minervini Ch.10 (pp.204-210).

    Scores every name in `mode`'s universe on overhead supply, supply
    absorption (volume dry-up), demand (accumulation), and distance from the
    52-week high. Cached ~3h + warmed by cron (the broad pass is ~3.7k frames),
    so the first cold call can take a while; subsequent calls are instant.
    """
    import asyncio
    data = await asyncio.to_thread(stocks_mod.screen, mode, min_dollar_vol, None, force)
    rows = data["rows"]
    if state in ("demand", "supply", "churning"):
        rows = [r for r in rows if r["state"] == state]
    return {**data, "rows": rows[:limit], "n_shown": min(len(rows), limit)}


@router.get("/supply-demand/demand-zones")
async def get_demand_zones(force: bool = Query(False, description="bypass the 3h cache and recompute")):
    """Minervini-basing demand-zone bands for the leaderboard + day-trading
    universe (Ch.10 pp.197-213).

    Each name's most-recent VCP consolidation base becomes a price band —
    `zone_low` (the base floor where strong hands accumulate, Fig 10.8 p.205) up
    to `zone_high` (the pivot/breakout line, p.203) — classified by correction
    depth (constructive 8-35% · deep · failure-prone ≥60%, p.210-211), with
    where the current price sits relative to the band (in / above / below) and
    its signed distance to it. Sorted in-zone (pullbacks) then nearest first.

    Educational — a structural read of where demand showed up, NOT a buy signal
    and NOT advice. Derived from the contract-locked `sepa.vcp.detect`.
    """
    import asyncio
    return await asyncio.to_thread(zones_mod.compute_zones, force)


@router.get("/supply-demand/graph")
async def get_graph(enrich_news: bool = Query(False, description="attach news headlines per edge"),
                    max_edges_enriched: int = Query(20, ge=0, le=100)):
    """Return the full curated dependency graph (nodes + edges).

    Pass `enrich_news=true` to fetch news headlines per edge (slower, cached 6h).
    """
    g = deps.full_graph()
    if enrich_news:
        g = {**g, "edges": news_mod.enrich_edges(g["edges"], max_edges=max_edges_enriched)}
    return {**g, "n_nodes": len(g["nodes"]), "n_edges": len(g["edges"])}


@router.get("/supply-demand/graph/{ticker}")
async def get_subgraph(ticker: str, depth: int = Query(1, ge=1, le=2),
                        enrich_news: bool = Query(True)):
    """Return the subgraph centered on `ticker`. Edges enriched with news by default."""
    sub = deps.subgraph_for_ticker(ticker, depth=depth)
    if enrich_news:
        sub = {**sub, "edges": news_mod.enrich_edges(sub["edges"], max_edges=20)}
    return sub


@router.get("/supply-demand/sectors")
async def get_sectors(force: bool = Query(False, description="bypass 6h cache")):
    """Classify all 15 sectors. Cached 6h."""
    return tr.classify_all_sectors(force=force)


@router.get("/supply-demand/sectors/{sector_id}")
async def get_sector(sector_id: str, force: bool = Query(False)):
    """Single sector classification."""
    r = tr.classify_sector(sector_id, force=force)
    if r is None:
        return {"error": "unknown sector_id"}
    return r


@router.get("/supply-demand/thesis/{ticker}")
async def get_thesis(ticker: str):
    """Curated company thesis (role, moat, what to watch, bull/bear) +
    plain-English explanation of every relationship the node has.

    Used by the node click-popup on the dependency graph.
    """
    t = ticker.upper()
    # lookup_node consults curated roster + dynamic watchlist/SEPA extras
    # so dynamic nodes (e.g. TWLO from the watchlist) don't 404 here.
    node = deps.lookup_node(t)
    if not node:
        return {"error": f"unknown ticker {t}"}

    thesis = deps.thesis_for_ticker(t) or {}
    edges = deps.edges_for_ticker(t)

    # Explain each edge in plain English from this ticker's POV
    relationships = []
    for e in edges:
        relationships.append({
            "source": e["source"],
            "target": e["target"],
            "relation": e["relation"],
            "strength": e.get("strength"),
            "evidence": e.get("evidence"),
            "explanation": deps.explain_edge_plain_english(e, t),
            "is_outbound": e["source"] == t,
        })

    # Sort by strength descending so most important relationships first
    relationships.sort(key=lambda r: -(r.get("strength") or 0))

    # Sectors this ticker is exposed to (with current state)
    ticker_sectors = sec.sectors_for_ticker(t)
    sector_states = []
    for s in ticker_sectors:
        full = tr.classify_sector(s["id"])
        if full:
            sector_states.append({
                "sector_id": s["id"],
                "label": s["label"],
                "thesis": s.get("thesis"),
                "state": full["classification"]["state"],
                "gap_index": full["classification"]["gap_index"],
                "trend_direction": full["classification"]["trend_direction"],
            })

    return {
        "ticker": t,
        "name": node.get("name"),
        "sector": node.get("sector"),
        "sub_sector": node.get("sub_sector"),
        "thesis": thesis,
        "relationships": relationships,
        "n_relationships": len(relationships),
        "sector_exposures": sector_states,
    }


@router.get("/supply-demand/flow")
async def get_flow(force: bool = Query(False, description="bypass 60s cache")):
    """Real-time money flow snapshot for every ticker in the dependency graph.

    Returns:
      - per-ticker price + change% + volume + $ volume
      - market state (open/pre/after/closed/weekend)
      - top 5 inflow + outflow leaders
      - aggregate up/down/flat counts

    Cached 60s when market is open, 5min after-hours, 24h on weekends.
    Frontend polls this every 30-60s during market hours to animate flow.
    """
    return flow_mod.get_flow_snapshot(force=force)


@router.get("/supply-demand/equity-premium")
async def get_equity_premium(force: bool = Query(False, description="bypass 12h cache")):
    """Companies whose market cap is largely premium to book value.

    Surfaces "external-equity-driven" names — MSTR-style treasuries,
    high-multiple growth names, and narrative trades that depend on
    external capital rather than retained earnings. Useful as a leading
    indicator: premium expansion drives upside, premium contraction
    drives crashes.

    Returns tickers sorted by `equity_premium_pct` descending.
    Cached 12h (fundamentals don't change intraday).
    """
    return equity_premium_mod.get_equity_premium_screen(force=force)


@router.get("/supply-demand/whales/{ticker}")
async def get_whales(ticker: str, force: bool = Query(False, description="bypass 24h cache")):
    """Top institutional holders + recent buys/sells (from 13F filings).

    Cached 24h (13F data is quarterly so this is plenty).
    Source: yfinance/Yahoo Finance (free).
    """
    return whales_mod.get_whales(ticker, force=force)


@router.get("/supply-demand/whales-flow")
async def get_whales_flow_bulk():
    """Bulk read of the institutional-flow signal for every ticker that
    has a cached whales record. Used by the SEPA list to render the
    🐋 Accumulating / 🐋 Distributing chip on each card without firing
    a per-card request.

    Returns only the summary fields — no full holders list, no mutual
    funds — so the response stays small.
    """
    import os
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        coll = client[db_name].whales_cache
    except Exception:
        return {"rows": []}

    rows = []
    for d in coll.find({}, {
        "ticker": 1,
        "payload.moves.net_signal": 1,
        "payload.moves.n_buying": 1,
        "payload.moves.n_selling": 1,
        "payload.moves.n_unchanged": 1,
        "payload.moves.notable_buys": 1,
        "payload.moves.notable_sells": 1,
        "cached_at": 1,
    }):
        moves = ((d.get("payload") or {}).get("moves") or {})
        if not moves.get("net_signal"):
            continue
        rows.append({
            "ticker":    (d.get("ticker") or "").upper(),
            "signal":    moves.get("net_signal"),
            "n_buying":  moves.get("n_buying", 0),
            "n_selling": moves.get("n_selling", 0),
            "n_unchanged": moves.get("n_unchanged", 0),
            "top_buy":   (moves.get("notable_buys") or [{}])[0].get("holder")
                          if moves.get("notable_buys") else None,
            "top_sell":  (moves.get("notable_sells") or [{}])[0].get("holder")
                          if moves.get("notable_sells") else None,
        })
    return {"rows": rows, "n": len(rows)}


# --- 13D / 13G filings (real-time-ish institutional accumulation) ---

@router.get("/supply-demand/whales/{ticker}/13d")
async def get_whales_13d(
    ticker: str,
    days: int = Query(120, ge=1, le=730,
                      description="Lookback window in days (default: 120)"),
    force: bool = Query(False, description="Bypass 24h cache"),
):
    """SC 13D / 13D-A / 13G / 13G-A filings for a ticker.

    Closest free "real-time" institutional signal — filed within 10 days
    of crossing 5% ownership. Source: SEC EDGAR submissions API.

    v1: surfaces filing dates + deep links to cover pages. Filer name
    and exact % owned require parsing the cover page — deferred to v2.
    """
    return whales_13d_mod.get_13d(ticker, days=days, force=force)


@router.get("/supply-demand/13d-flow")
async def get_13d_flow_bulk(
    days: int = Query(90, ge=1, le=365,
                      description="Lookback window in days (default: 90)"),
):
    """Bulk read of recent SEC filings of interest across all cached tickers.

    Tracks Form 4 (insider trades) + Form 144 (insider pre-sale notice) +
    SC 13D/G (5% ownership threshold). Used by SEPA cards to render the
    📋 SEC activity chip — compact per-ticker counts. Full filing list
    requires the per-ticker /whales/{t}/13d endpoint.

    Endpoint name kept as /13d-flow for backwards-compat with the
    frontend hook; semantically it now covers a wider form set.
    """
    import os
    from datetime import datetime, timezone, timedelta
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        coll = client[db_name].whales13d_cache
    except Exception:
        return {"rows": [], "n": 0}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    rows = []
    for d in coll.find({}, {
        "ticker": 1,
        "payload.filings.form": 1,
        "payload.filings.filing_date": 1,
        "payload.filings.bucket": 1,
        "payload.n_filings": 1,
        "payload.latest": 1,
        "cached_at": 1,
    }):
        payload = d.get("payload") or {}
        all_filings = payload.get("filings") or []
        # Apply caller's window even if the cached doc used a longer one.
        recent = [f for f in all_filings if (f.get("filing_date") or "") >= cutoff]
        if not recent:
            continue
        # Bucket counts within the caller's window — can't trust cached
        # totals which may have used a longer window.
        n_form4 = sum(1 for f in recent if f.get("bucket") == "form4")
        n_form144 = sum(1 for f in recent if f.get("bucket") == "form144")
        n_form13 = sum(1 for f in recent if f.get("bucket") == "form13")
        latest = recent[0]  # already sorted newest-first by get_13d()
        rows.append({
            "ticker":       (d.get("ticker") or "").upper(),
            "n_filings":    len(recent),
            "n_form4":      n_form4,
            "n_form144":    n_form144,
            "n_form13":     n_form13,
            "latest_form":  latest.get("form"),
            "latest_date":  latest.get("filing_date"),
            "latest_url":   latest.get("primary_doc_url"),
        })
    rows.sort(key=lambda r: r.get("latest_date") or "", reverse=True)
    return {"rows": rows, "n": len(rows), "window_days": days}


# In-process per-ticker cache for /supply-demand/ticker/{ticker}.
# This endpoint is expensive (Massive snapshot + yfinance accumulation +
# news enrichment + sector classify). When the user clicks back/forth
# between graph nodes a fresh fetch every time is wasteful — prices
# move slowly enough that 60s is safe.
_TICKER_CACHE: dict = {}
_TICKER_CACHE_TTL = 60  # seconds


@router.get("/supply-demand/ticker/{ticker}")
async def get_for_ticker(ticker: str, depth: int = Query(1, ge=1, le=2)):
    """All supply/demand context for a ticker:
      - Flow: today's price + change% + volume + market state
      - Accumulation/Distribution: 10-day Chaikin Money Flow score
      - Subgraph (this company's suppliers/customers/competitors)
      - Sectors this company is exposed to (with current state)
      - News for top edges

    60-second in-process cache: rapid back-and-forth between graph nodes
    or fast page-revisits don't re-trigger the (slow) yfinance + Massive
    + news fan-out.
    """
    import time as _time
    t = ticker.upper()
    cache_key = f"{t}:{depth}"
    now = _time.time()
    cached = _TICKER_CACHE.get(cache_key)
    if cached and (now - cached["ts"]) < _TICKER_CACHE_TTL:
        return {**cached["data"], "_cached": True, "_cache_age_sec": round(now - cached["ts"])}

    subgraph = deps.subgraph_for_ticker(t, depth=depth)
    subgraph = {**subgraph, "edges": news_mod.enrich_edges(subgraph["edges"], max_edges=15)}

    # Sectors that include this ticker
    ticker_sectors_static = sec.sectors_for_ticker(t)
    enriched_sectors = []
    for s in ticker_sectors_static:
        full = tr.classify_sector(s["id"])
        if full:
            enriched_sectors.append(full)

    # Live flow snapshot for this ticker — covers pre-market / regular /
    # after-hours via Massive's lastTrade (extended-hours-aware). Falls
    # back to yfinance for foreign ADRs not in Massive's feed.
    flow_data = None
    try:
        snap = flow_mod._fetch_massive_bulk([t]).get(t)
        if not snap:
            snap = flow_mod._fetch_yfinance_fallback([t]).get(t)
        if snap:
            flow_data = snap
            flow_data["market"] = flow_mod.market_status()
    except Exception as exc:
        log.warning("flow fetch failed for %s: %s", t, exc)

    # Multi-day Chaikin Money Flow score (1h cached)
    accumulation = None
    try:
        from . import accumulation as accum_mod
        scores = accum_mod.get_accumulation_scores([t])
        accumulation = scores.get(t)
    except Exception as exc:
        log.warning("accumulation fetch failed for %s: %s", t, exc)

    payload = {
        "ticker": t,
        "flow": flow_data,
        "accumulation": accumulation,
        "subgraph": subgraph,
        "sectors": enriched_sectors,
        "n_dependencies": len(subgraph.get("edges", [])),
        "n_sector_exposures": len(enriched_sectors),
    }

    # Update cache + cap entry count to avoid unbounded growth
    if len(_TICKER_CACHE) > 200:
        # Evict oldest half — simple, no LRU library dep
        sorted_keys = sorted(_TICKER_CACHE.keys(), key=lambda k: _TICKER_CACHE[k]["ts"])
        for k in sorted_keys[:100]:
            _TICKER_CACHE.pop(k, None)
    _TICKER_CACHE[cache_key] = {"ts": now, "data": payload}

    return {**payload, "_cached": False, "_cache_age_sec": 0}
