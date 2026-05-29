"""FastAPI handlers for the supply/demand module."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query

from . import dependencies as deps
from . import sectors as sec
from . import news as news_mod
from . import tracker as tr
from . import whales as whales_mod
from . import whales_13d as whales_13d_mod
from . import flow as flow_mod
from . import equity_premium as equity_premium_mod

log = logging.getLogger("supply_demand.api")
router = APIRouter(tags=["supply-demand"])


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
    """Bulk read of recent 13D/G filings across all cached tickers.

    Used by SEPA cards to render a "📜 13D" chip when a ticker has had
    recent filings. Returns a compact per-ticker summary (n_filings,
    latest filing's date + form) — full filing list requires the
    per-ticker /whales/{t}/13d endpoint.
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
        latest = recent[0]  # already sorted newest-first by get_13d()
        rows.append({
            "ticker":       (d.get("ticker") or "").upper(),
            "n_filings":    len(recent),
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
