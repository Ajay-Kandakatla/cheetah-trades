"""Background research worker for watchlist entries.

Called as a FastAPI BackgroundTask after a ticker is added. Fetches:
  - yfinance info (sector, industry, last_price, market_cap, long_name)
  - Most recent SEPA score from candidate_snapshots (if analyzed)
  - 3-5 industry peers from candidate_snapshots (auto-add as competitors)

Hooks into supply_demand by tagging the ticker for inclusion in the next
sector graph build (the supply_demand tracker will pick it up on next refresh).
"""
from __future__ import annotations

import logging
from typing import Optional

from watchlist import store
from sepa import symbols

log = logging.getLogger("watchlist.research")

PEER_LIMIT = 5  # how many competitors to auto-add per primary ticker


def _yfinance_info(ticker: str) -> dict:
    try:
        import yfinance as yf
        t = symbols.yf_ticker(ticker)
        info = t.info or {}
        # Pull the most recent close as a fallback if regularMarketPrice missing
        try:
            hist = t.history(period="5d", auto_adjust=False)
            last_close = float(hist["Close"].iloc[-1]) if not hist.empty else None
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else None
            day_pct = ((last_close - prev_close) / prev_close * 100.0
                       if last_close and prev_close else None)
        except Exception:
            last_close = None
            day_pct = None
        return {
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "last_price": (info.get("regularMarketPrice") or last_close),
            "day_change_pct": day_pct,
            "exchange": info.get("exchange"),
            "currency": info.get("currency"),
        }
    except Exception as exc:
        log.warning("yfinance lookup failed for %s: %s", ticker, exc)
        return {}


def _latest_sepa(db, ticker: str) -> dict:
    """Most recent candidate_snapshot for this ticker, if any."""
    snap = db.candidate_snapshots.find_one(
        {"symbol": ticker.upper()},
        sort=[("generated_at", -1)],
        projection={"score": 1, "rating": 1, "rs_rank": 1, "stage_label": 1,
                     "date_et": 1, "generated_at": 1, "entry_setup": 1,
                     "pioneer_themes": 1},
    )
    if not snap:
        return {}
    return {
        "score": snap.get("score"),
        "rating": snap.get("rating"),
        "rs_rank": snap.get("rs_rank"),
        "stage_label": snap.get("stage_label"),
        "date_et": snap.get("date_et"),
        "entry_setup": snap.get("entry_setup"),
        "pioneer_themes": snap.get("pioneer_themes") or [],
    }


def _theme_peers(db, ticker: str, themes: list[str], limit: int) -> list[str]:
    """Find tickers that share pioneer_themes with the input. This catches
    theme relationships that pure industry classification misses — e.g.
    TWLO (cloud comms) and SOUN (voice AI) both tagged 'AI / voice'.
    """
    if not themes:
        return []
    # Most recent candidate_snapshot per symbol that shares any theme
    pipeline = [
        {"$match": {
            "pioneer_themes": {"$in": themes},
            "symbol": {"$ne": ticker.upper()},
        }},
        {"$sort": {"generated_at": -1, "score": -1}},
        {"$group": {"_id": "$symbol",
                    "score": {"$first": "$score"},
                    "themes": {"$first": "$pioneer_themes"}}},
        {"$sort": {"score": -1}},
        {"$limit": limit},
    ]
    rows = list(db.candidate_snapshots.aggregate(pipeline))
    return [r["_id"] for r in rows if r["_id"]]


def _industry_peers(db, ticker: str, industry: Optional[str], limit: int) -> list[str]:
    """Find peers from the existing analyzed universe in the same industry.

    Industry isn't stored on candidate_snapshots, so we resolve it via
    yfinance for each candidate symbol — too expensive. Instead we query
    by sector inferred from supply_demand if available, OR fall back to a
    simple 'most-recent BUY/STRONG_BUY in same industry from yfinance lookups'.

    For now: return top-scoring SEPA candidates that share the industry,
    looking up industries on-the-fly only for top N candidates.
    """
    if not industry:
        return []
    # Pull top SEPA candidates and check their yfinance industry.
    # Capped at 30 lookups to stay under a few seconds.
    pipeline = [
        {"$match": {"rating": {"$in": ["STRONG_BUY", "BUY", "WATCH"]}}},
        {"$sort": {"generated_at": -1, "score": -1}},
        {"$group": {"_id": "$symbol", "score": {"$first": "$score"}}},
        {"$sort": {"score": -1}},
        {"$limit": 30},
    ]
    candidates = [r["_id"] for r in db.candidate_snapshots.aggregate(pipeline)
                  if r["_id"] and r["_id"] != ticker.upper()]
    peers: list[str] = []
    try:
        import yfinance as yf
        for sym in candidates:
            if len(peers) >= limit:
                break
            try:
                t = symbols.yf_ticker(sym)
                info = t.info or {}
                if info.get("industry") == industry:
                    peers.append(sym)
            except Exception:
                continue
    except ImportError:
        pass
    return peers


def _hook_supply_demand(ticker: str, sector: Optional[str]):
    """Mark the ticker for inclusion in the next supply_demand graph build.

    Writes to a ``watchlist_sd_pending`` collection that supply_demand.tracker
    can drain on its next run.
    """
    if not sector:
        return
    try:
        db = store._get_db()
        if db is None:
            return
        db.watchlist_sd_pending.update_one(
            {"ticker": ticker.upper()},
            {"$set": {"ticker": ticker.upper(), "sector": sector,
                       "queued_at": store._now()}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("supply_demand hook failed for %s: %s", ticker, exc)


def research_ticker(ticker: str, *, expand_competitors: bool = True):
    """Background task entry point. Updates the watchlist record in place
    and adds competitors as derived entries when applicable."""
    db = store._get_db()
    if db is None:
        return

    store.set_status(ticker, "researching")

    info = _yfinance_info(ticker)
    sepa = _latest_sepa(db, ticker)
    peers: list[str] = []

    if expand_competitors:
        # Try theme-based peers first — these surface non-obvious relationships
        # (e.g. TWLO + SOUN both tagged 'AI Voice' even though different industry).
        # Fall back to industry-peer scan if no themes are tagged.
        theme_peers = _theme_peers(db, ticker, sepa.get("pioneer_themes") or [], PEER_LIMIT)
        peers.extend(theme_peers)
        if len(peers) < PEER_LIMIT:
            ind_peers = _industry_peers(db, ticker, info.get("industry"),
                                         PEER_LIMIT - len(peers))
            peers.extend([p for p in ind_peers if p not in peers])

        for peer in peers:
            via = "theme_of" if peer in theme_peers else "competitor_of"
            store.add_entry(peer, primary_ticker=ticker.upper(),
                            added_via=f"{via}:{ticker.upper()}")
            # Recurse with no further competitor expansion
            try:
                research_ticker(peer, expand_competitors=False)
            except Exception as exc:
                log.warning("peer research failed for %s: %s", peer, exc)

    _hook_supply_demand(ticker, info.get("sector"))

    research_blob = {
        **info,
        **sepa,
        "competitors": peers,
        "researched_at": store._now(),
    }
    status = "ready" if (info or sepa) else "failed"
    store.set_status(ticker, status, research=research_blob)
    log.info("watchlist: researched %s status=%s peers=%d",
             ticker, status, len(peers))
