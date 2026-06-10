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
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def all_names() -> dict:
    """The ENTIRE cached {SYMBOL: name} map in one read — powers the app-wide
    ticker labels (Ajay 2026-06-10: company name in tiny font everywhere a
    ticker shows). Cache-only, never fetches; ~one small Mongo scan."""
    coll = _get_mongo()
    if coll is None:
        return {}
    out = {}
    try:
        for doc in coll.find({}, {"symbol": 1, "name": 1}):
            if doc.get("symbol") and doc.get("name"):
                out[doc["symbol"]] = doc["name"]
    except Exception as exc:
        log.warning("company_names.all_names failed: %s", exc)
    return out


def bulk_warm(symbols: Iterable[str], max_workers: int = 8,
              emitter=None, fetch: bool = True,
              throttle_sec: float = 0.0) -> dict[str, Optional[str]]:
    """Ensure the name cache contains entries for every symbol in `symbols`.

    Names already cached are skipped. Missing names are fetched via yfinance in
    a thread pool and persisted to Mongo. Returns a dict {symbol: name} with
    the full resolved set.

    fetch=False makes this CACHE-ONLY — it never touches yfinance, so the hot
    scan path doesn't flood Yahoo (the broad universe has thousands of
    un-cached names → 429 storm). The daily warmer (sepa.warm_names) fills the
    misses instead. throttle_sec>0 fetches sequentially with that delay between
    calls (rate-limit-safe) — used by the daily warmer.

    Optional `emitter` (sepa.progress.ProgressEmitter) fires `name_progress`
    events every 25 completions so the SSE stream can show progress during
    cold-start fetches (~25-60s on a 1000-name universe with empty cache).
    """
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

    if emitter:
        emitter.emit("phase", phase="warming_names",
                     total=len(syms), missing=len(missing),
                     message=(f"Company-name cache: {len(syms) - len(missing)} hits, "
                              f"fetching {len(missing)} missing"))

    if not missing or not fetch:
        # All cached, or cache-only mode — emit a final tick + return what we
        # have. Missing names simply stay absent; the caller falls back to the
        # ticker and the daily warmer fills them later.
        if emitter:
            emitter.emit("name_progress",
                         current=len(syms), total=len(syms), fetched=0)
        return out

    log.info("company_names: warming %d missing name(s)", len(missing))
    completed = 0

    def _one(sym: str) -> tuple[str, Optional[str]]:
        return sym, _fetch_yfinance(sym)

    # Throttled sequential path — rate-limit-safe for the daily warmer.
    if throttle_sec > 0:
        for sym in missing:
            name = _fetch_yfinance(sym)
            _memo[sym] = name
            _mongo_put(sym, name)
            out[sym] = name
            completed += 1
            if emitter and (completed % 25 == 0 or completed == len(missing)):
                emitter.emit("name_progress",
                             current=completed, total=len(missing), fetched=completed)
            time.sleep(throttle_sec)
        return out

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_one, s): s for s in missing}
        for fut in as_completed(futures):
            sym, name = fut.result()
            _memo[sym] = name
            _mongo_put(sym, name)
            out[sym] = name
            completed += 1
            if emitter and (completed % 25 == 0 or completed == len(missing)):
                emitter.emit("name_progress",
                             current=completed, total=len(missing), fetched=completed)

    return out
