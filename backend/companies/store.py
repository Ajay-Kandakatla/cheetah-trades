"""Mongo-cached company info snapshot. yfinance once, reuse for 30 days."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional
from sepa import symbols

log = logging.getLogger("companies.store")

_db = None
TTL_SECONDS = 30 * 86400        # 30 days


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient
        client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                              serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        _db.companies.create_index("symbol", unique=True)
        return _db
    except Exception as exc:
        log.warning("companies.store: Mongo unavailable: %s", exc)
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _fetch_from_yfinance(symbol: str) -> Optional[dict]:
    try:
        import yfinance as yf
        t = symbols.yf_ticker(symbol)
        info = t.info or {}
        if not info:
            return None
        return {
            "name": info.get("longName") or info.get("shortName"),
            "summary": info.get("longBusinessSummary"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "website": info.get("website"),
            "employees": info.get("fullTimeEmployees"),
            "country": info.get("country"),
            "city": info.get("city"),
            "state": info.get("state"),
            "ceo": (
                # yfinance returns companyOfficers list; CEO usually first or
                # tagged with title. Try to extract.
                next(
                    (o.get("name") for o in (info.get("companyOfficers") or [])
                     if "CEO" in (o.get("title") or "").upper() or
                        "Chief Executive" in (o.get("title") or "")),
                    None,
                )
            ),
            "exchange": info.get("exchange"),
            "currency": info.get("currency"),
            "ipo_year": (info.get("firstTradeDateEpochUtc") or 0) and (
                datetime.fromtimestamp(info["firstTradeDateEpochUtc"], tz=timezone.utc).year
                if info.get("firstTradeDateEpochUtc") else None
            ),
        }
    except Exception as exc:
        log.warning("yfinance fetch failed for %s: %s", symbol, exc)
        return None


def get(symbol: str, force: bool = False) -> dict:
    """Return cached company info, refreshing from yfinance if stale or absent.
    Always returns a dict — never None. May be sparse if yfinance unavailable."""
    db = _get_db()
    symbol = symbol.upper().strip()
    if not symbol:
        return {"symbol": symbol, "summary": None}

    cached = db.companies.find_one({"symbol": symbol}) if db is not None else None
    fresh_needed = (
        force
        or cached is None
        or (_now() - (cached.get("refreshed_at") or 0)) > TTL_SECONDS
    )

    if fresh_needed:
        info = _fetch_from_yfinance(symbol)
        if info:
            doc = {
                "symbol": symbol,
                **info,
                "refreshed_at": _now(),
            }
            if db is not None:
                db.companies.update_one(
                    {"symbol": symbol},
                    {"$set": doc, "$setOnInsert": {"created_at": _now()}},
                    upsert=True,
                )
            return doc

    if cached:
        cached["_id"] = str(cached["_id"])
        return cached

    # Last resort — return a stub
    return {"symbol": symbol, "summary": None, "refreshed_at": None}


def get_many_cached(symbols: list[str]) -> dict:
    """Batch CACHE-ONLY lookup — one Mongo read, never touches yfinance.

    Safe to call on the scan hot path (the daily money-path scan): it does NOT
    fetch, refresh, or write, so it can never slow the scan or trip a yfinance
    rate-limit. Returns ``{SYMBOL: company_info_dict}`` for the symbols that have
    a cached doc; missing symbols are simply absent from the result (callers
    degrade gracefully, never fake). Returns ``{}`` when Mongo is unavailable.

    Used by ``sepa.group_leadership`` to attach industry/sector labels for the
    group-leadership annotation. Coverage grows over time via ``get()`` /
    ``backfill_descriptions``; uncached names just go ungrouped.
    """
    syms = sorted({(s or "").upper().strip() for s in symbols if (s or "").strip()})
    if not syms:
        return {}
    db = _get_db()
    if db is None:
        return {}
    out: dict = {}
    try:
        for doc in db.companies.find({"symbol": {"$in": syms}}):
            doc["_id"] = str(doc.get("_id"))
            out[doc["symbol"]] = doc
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("companies.store.get_many_cached failed: %s", exc)
        return {}
    return out


def backfill_descriptions(
    symbols: list[str],
    delay_sec: float = 1.5,
    max_fetch: Optional[int] = None,
) -> dict:
    """Throttled backfill of company info for symbols missing a summary.

    The broad universe (3,600+ names) floods yfinance and Yahoo rate-limits it,
    so per-page fetches fail and descriptions stay blank. This walks the list
    SLOWLY (delay_sec between calls) and only fetches symbols that don't already
    have a good cached summary — so it's resumable and won't re-hammer names
    that already filled in. On a rate-limit hit it backs off and keeps going.

    Returns {checked, fetched, still_missing, rate_limited}.
    """
    import time
    db = _get_db()
    checked = fetched = still_missing = rate_limited = 0
    for raw in symbols:
        if max_fetch and fetched >= max_fetch:
            break
        sym = (raw or "").upper().strip()
        if not sym:
            continue
        cached = db.companies.find_one({"symbol": sym}) if db is not None else None
        if cached and (cached.get("summary") or "").strip():
            continue                      # already good — skip
        checked += 1
        info = _fetch_from_yfinance(sym)
        if info and (info.get("summary") or "").strip():
            doc = {"symbol": sym, **info, "refreshed_at": _now()}
            if db is not None:
                db.companies.update_one(
                    {"symbol": sym},
                    {"$set": doc, "$setOnInsert": {"created_at": _now()}},
                    upsert=True,
                )
            fetched += 1
        else:
            still_missing += 1
            if info is None:
                rate_limited += 1
                time.sleep(delay_sec * 4)   # extra cool-down after a likely 429
        time.sleep(delay_sec)
    out = {
        "checked": checked, "fetched": fetched,
        "still_missing": still_missing, "rate_limited": rate_limited,
    }
    log.info("backfill_descriptions: %s", out)
    return out
