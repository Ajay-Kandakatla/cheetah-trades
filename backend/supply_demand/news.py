"""Per-edge news enrichment.

For each curated edge in the dependency graph, we fetch recent news
mentioning BOTH endpoints. This proves the relationship is currently
relevant — if no news has co-mentioned NVDA + TSM in 30 days, that's
either a gap in the news API or the relationship is dormant.

Cached per (source, target) pair for 6h.
"""
from __future__ import annotations

import logging
import os
from massive_keys import stocks_key
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger("supply_demand.news")

_CACHE_TTL_SEC = 6 * 60 * 60


def _cache_coll():
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        c = client[db]["supply_demand_edge_news"]
        c.create_index([("edge_key", ASCENDING)], unique=True)
        return c
    except Exception as exc:
        log.warning("edge news mongo unavailable: %s", exc)
        return None


def _edge_key(source: str, target: str) -> str:
    return f"{source.upper()}|{target.upper()}"


def _cache_get(source: str, target: str) -> Optional[list[dict]]:
    coll = _cache_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"edge_key": _edge_key(source, target)})
        if not doc:
            return None
        ts = doc.get("cached_at")
        if not isinstance(ts, datetime):
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - ts).total_seconds() > _CACHE_TTL_SEC:
            return None
        return doc.get("headlines") or []
    except Exception as exc:
        log.warning("edge news cache get failed: %s", exc)
    return None


def _cache_put(source: str, target: str, headlines: list[dict]) -> None:
    coll = _cache_coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"edge_key": _edge_key(source, target)},
            {"$set": {"edge_key": _edge_key(source, target),
                      "cached_at": datetime.now(timezone.utc),
                      "headlines": headlines}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("edge news cache put failed: %s", exc)


def fetch_edge_news(source: str, target: str, limit: int = 5,
                    force: bool = False) -> list[dict]:
    """Find news headlines mentioning both source and target.

    Strategy: pull recent articles for the source ticker, filter to those
    whose body or tickers list also mentions the target.
    """
    if not force:
        cached = _cache_get(source, target)
        if cached is not None:
            return cached

    import requests
    key = stocks_key()
    if not key:
        return []

    src = source.upper()
    tgt = target.upper()
    matches: list[dict] = []
    seen_titles = set()

    try:
        # Massive supports tickers param — articles tagged with both
        r = requests.get(
            "https://api.massive.com/v2/reference/news",
            params={"tickers": src, "limit": 30, "order": "desc", "apiKey": key},
            timeout=10,
        )
        if r.status_code != 200:
            log.warning("massive edge news HTTP %s for %s", r.status_code, src)
            _cache_put(source, target, [])
            return []
        for item in (r.json() or {}).get("results") or []:
            tickers = [t.upper() for t in (item.get("tickers") or [])]
            title = item.get("title") or ""
            if tgt in tickers or tgt in title.upper():
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                matches.append({
                    "title": title[:200],
                    "url": item.get("article_url"),
                    "publisher": (item.get("publisher") or {}).get("name"),
                    "published_utc": item.get("published_utc"),
                    "tickers": tickers,
                })
                if len(matches) >= limit:
                    break
    except Exception as exc:
        log.warning("edge news fetch failed for %s/%s: %s", source, target, exc)

    _cache_put(source, target, matches)
    return matches


def enrich_edges(edges: list[dict], max_edges: int = 30,
                 force: bool = False) -> list[dict]:
    """Add news_links to each edge. Limits to max_edges (parallelized)."""
    import concurrent.futures
    enriched = list(edges)
    todo = enriched[:max_edges]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futures = {
            ex.submit(fetch_edge_news, e["source"], e["target"], 5, force): i
            for i, e in enumerate(todo)
        }
        for fut in concurrent.futures.as_completed(futures):
            i = futures[fut]
            try:
                todo[i]["news_links"] = fut.result()
            except Exception as exc:
                log.warning("enrich edge %s failed: %s", i, exc)
                todo[i]["news_links"] = []
    # For edges beyond max_edges, leave news_links empty
    for i in range(max_edges, len(enriched)):
        enriched[i]["news_links"] = []
    return enriched
