"""Mongo-backed cache for Finnhub responses with per-endpoint TTL.

Collection: ``finnhub_cache_v2`` (deliberately distinct from any older
finnhub_cache to avoid stepping on existing caches; safe to drop at any
time without affecting other modules).

Schema
------
.. code-block:: python

    {
      "key":        "quote:AAPL",          # endpoint + symbol
      "endpoint":   "quote",
      "symbol":     "AAPL",
      "data":       <raw Finnhub JSON dict>,
      "cached_at":  1779999999,            # unix seconds
      "ttl_sec":    60,                     # for diagnostics + cache audit
    }

TTL policy
----------
Per-endpoint defaults baked in here so callers don't have to know the
volatility profile of each Finnhub endpoint. Override via the
``ttl_sec_override`` arg on ``put()`` when you genuinely need fresher
data (e.g. during a manual refresh from the UI).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

log = logging.getLogger("finnhub_client.cache")

# Per-endpoint TTL in seconds. Picked to match how often each endpoint's
# data actually changes:
#   quote        — refreshes every trade tick → 60s is plenty for JIT UI
#   profile      — company name/sector/cap rarely changes → 24h
#   news         — new stories trickle in → 30min keeps the feed lively
#   earnings     — next earnings date moves ~quarterly → 6h
#   recommendation — analyst recs shift weekly at most → 24h
#   price-target — same cadence as recs → 24h
#   search       — ticker search index is stable → 24h
_TTL_BY_ENDPOINT: dict[str, int] = {
    "quote":          60,
    "profile":        24 * 3600,
    "news":           30 * 60,
    "earnings":       6 * 3600,
    "recommendation": 24 * 3600,
    "price_target":   24 * 3600,
    "search":         24 * 3600,
}

_coll = None
_disabled = False


def _get_coll():
    """Lazy Mongo handle. Returns None when Mongo is unreachable so
    callers fall through to direct Finnhub fetches (degraded but
    functional). The error is logged once, then silenced."""
    global _coll, _disabled
    if _disabled:
        return None
    if _coll is not None:
        return _coll
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        cli = MongoClient(url, serverSelectionTimeoutMS=2000)
        cli.admin.command("ping")
        coll = cli[db_name].finnhub_cache_v2
        coll.create_index([("key", ASCENDING)], unique=True)
        coll.create_index([("cached_at", ASCENDING)])  # for stale sweeps
        _coll = coll
        log.info("finnhub_client.cache: connected to %s.finnhub_cache_v2", db_name)
        return _coll
    except Exception as exc:
        log.warning("finnhub_client.cache: Mongo unavailable (%s)", exc)
        _disabled = True
        return None


def ttl_for(endpoint: str) -> int:
    """Public lookup of the TTL we'd apply for a given endpoint. Used by
    the rate limiter to decide how long to wait before re-trying a failed
    fetch (no point retrying if cache is fresh)."""
    return _TTL_BY_ENDPOINT.get(endpoint, 600)


def _key(endpoint: str, symbol: str) -> str:
    return f"{endpoint}:{symbol.upper().strip()}"


def get(endpoint: str, symbol: str, *, allow_stale: bool = False) -> Optional[dict]:
    """Return cached data for (endpoint, symbol) or None.

    Normally returns None when the entry is past its TTL. Pass
    ``allow_stale=True`` to return any cached row regardless of age —
    useful as a fallback when Finnhub is rate-limiting and a stale
    response is better than nothing.
    """
    coll = _get_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"key": _key(endpoint, symbol)})
        if not doc:
            return None
        if allow_stale:
            return doc.get("data")
        age = time.time() - (doc.get("cached_at") or 0)
        if age >= ttl_for(endpoint):
            return None
        return doc.get("data")
    except Exception as exc:
        log.warning("finnhub_client.cache.get failed for %s/%s: %s",
                    endpoint, symbol, exc)
        return None


def put(endpoint: str, symbol: str, data: dict, *,
        ttl_sec_override: Optional[int] = None) -> None:
    """Upsert a cached response. Silently no-ops if Mongo is down."""
    coll = _get_coll()
    if coll is None:
        return
    if data is None:
        return
    ttl = ttl_sec_override if ttl_sec_override is not None else ttl_for(endpoint)
    try:
        coll.update_one(
            {"key": _key(endpoint, symbol)},
            {"$set": {
                "key":       _key(endpoint, symbol),
                "endpoint":  endpoint,
                "symbol":    symbol.upper().strip(),
                "data":      data,
                "cached_at": int(time.time()),
                "ttl_sec":   ttl,
            }},
            upsert=True,
        )
    except Exception as exc:
        log.warning("finnhub_client.cache.put failed for %s/%s: %s",
                    endpoint, symbol, exc)


def clear_endpoint(endpoint: str) -> int:
    """Drop every cached row for one endpoint. Useful when a Finnhub
    schema changes and the cached payload shape is stale. Returns the
    delete count for diagnostics."""
    coll = _get_coll()
    if coll is None:
        return 0
    try:
        return coll.delete_many({"endpoint": endpoint}).deleted_count
    except Exception as exc:
        log.warning("finnhub_client.cache.clear_endpoint(%s) failed: %s",
                    endpoint, exc)
        return 0


def stats() -> dict:
    """Cache-health summary for the /finnhub-v2/health route."""
    coll = _get_coll()
    if coll is None:
        return {"available": False}
    try:
        from pymongo import DESCENDING
        total = coll.estimated_document_count()
        by_endpoint = list(coll.aggregate([
            {"$group": {"_id": "$endpoint", "count": {"$sum": 1}}},
            {"$sort": {"count": DESCENDING}},
        ]))
        return {
            "available":   True,
            "total":       total,
            "by_endpoint": {row["_id"]: row["count"] for row in by_endpoint},
        }
    except Exception as exc:
        log.warning("finnhub_client.cache.stats failed: %s", exc)
        return {"available": False, "error": str(exc)}
