"""Company name resolver — symbol → human-readable company name.

Used by the SEPA scanner to attach a `name` field to each candidate so the UI
can show "MU · Micron Technology" instead of just the ticker.

Strategy:
  1. Mongo collection `company_names_cache` is the source of truth (30-day TTL).
  2. On miss, fetch via yfinance `.info["longName"]` (or `shortName` fallback).
  3. `bulk_warm(symbols)` parallel-fills missing names in a thread pool so a scan
     pays the lookup cost once, then reads from cache thereafter.

Graceful degradation: if Mongo or yfinance is down, returns `None` and the
caller should fall back to the symbol.
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Iterable

log = logging.getLogger("sepa.company_names")

# 30-day TTL — company names rarely change
CACHE_TTL_SEC = 30 * 24 * 3600

_mongo_coll = None
_mongo_disabled = False
# In-process LRU so each scan pass doesn't hit Mongo for the same ticker
_memo: dict[str, Optional[str]] = {}


def _get_mongo():
    """Return the company_names_cache collection or None if Mongo is unavailable."""
    global _mongo_coll, _mongo_disabled
    if _mongo_disabled:
        return None
    if _mongo_coll is not None:
        return _mongo_coll
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        coll = client[db_name].company_names_cache
        coll.create_index([("symbol", ASCENDING)], unique=True)
        _mongo_coll = coll
        return _mongo_coll
    except Exception as exc:
        log.warning("company_names: Mongo unavailable (%s)", exc)
        _mongo_disabled = True
        return None


def _mongo_get(symbol: str) -> Optional[str]:
    coll = _get_mongo()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"symbol": symbol.upper()})
        if not doc:
            return None
        if (time.time() - (doc.get("cached_at") or 0)) >= CACHE_TTL_SEC:
            return None
        return doc.get("name")
    except Exception as exc:
        log.warning("company_names mongo read failed for %s: %s", symbol, exc)
        return None


def _mongo_put(symbol: str, name: Optional[str]) -> None:
    coll = _get_mongo()
    if coll is None:
        return
    try:
        coll.update_one(
            {"symbol": symbol.upper()},
            {"$set": {"symbol": symbol.upper(), "name": name, "cached_at": int(time.time())}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("company_names mongo write failed for %s: %s", symbol, exc)


def _fetch_yfinance(symbol: str) -> Optional[str]:
    """Best-effort fetch of the long company name via yfinance."""
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).info or {}
        # longName is the official 'Apple Inc.', shortName is 'Apple Inc'
        name = info.get("longName") or info.get("shortName") or info.get("displayName")
        if name and isinstance(name, str):
            return name.strip()
    except Exception as exc:
        log.warning("yfinance name fetch failed for %s: %s", symbol, exc)
    return None


def name_for(symbol: str) -> Optional[str]:
    """Return the cached company name for a symbol, or None if unknown.

    Does NOT trigger a remote fetch — call `bulk_warm` first to fill the cache."""
    sym = symbol.upper()
    if sym in _memo:
        return _memo[sym]
    name = _mongo_get(sym)
    _memo[sym] = name
    return name


def bulk_warm(symbols: Iterable[str], max_workers: int = 8) -> dict[str, Optional[str]]:
    """Ensure the name cache contains entries for every symbol in `symbols`.

    Names already cached are skipped. Missing names are fetched via yfinance in
    a thread pool and persisted to Mongo. Returns a dict {symbol: name} with
    the full resolved set."""
    syms = [s.upper() for s in symbols]
    out: dict[str, Optional[str]] = {}
    missing: list[str] = []

    for s in syms:
        cached = _memo.get(s) if s in _memo else _mongo_get(s)
        if cached is not None:
            _memo[s] = cached
            out[s] = cached
        else:
            missing.append(s)

    if not missing:
        return out

    log.info("company_names: warming %d missing name(s)", len(missing))

    def _one(sym: str) -> tuple[str, Optional[str]]:
        return sym, _fetch_yfinance(sym)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for sym, name in ex.map(_one, missing):
            _memo[sym] = name
            _mongo_put(sym, name)
            out[sym] = name

    return out
