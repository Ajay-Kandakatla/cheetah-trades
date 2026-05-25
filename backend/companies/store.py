"""Mongo-cached company info snapshot. yfinance once, reuse for 30 days."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

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
        t = yf.Ticker(symbol)
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
