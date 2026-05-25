"""Mongo CRUD for the watchlist collection."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("watchlist.store")

_db = None
_disabled = False


def _get_db():
    global _db, _disabled
    if _disabled:
        return None
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        _db.watchlist.create_index("ticker", unique=True)
        _db.watchlist.create_index("primary_ticker")
        _db.watchlist.create_index("added_at")
        return _db
    except Exception as exc:
        log.warning("watchlist: Mongo unavailable (%s) — disabling", exc)
        _disabled = True
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def add_entry(ticker: str, primary_ticker: Optional[str] = None,
              added_via: str = "manual") -> dict:
    """Insert a watchlist entry. If it already exists, returns the existing one
    untouched (so adding NVDA twice is idempotent)."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 10:
        return {"ok": False, "reason": "invalid ticker"}

    existing = db.watchlist.find_one({"ticker": ticker})
    if existing:
        existing["_id"] = str(existing["_id"])
        return {"ok": True, "existing": True, "entry": existing}

    doc = {
        "ticker": ticker,
        "added_at": _now(),
        "added_via": added_via,
        "primary_ticker": primary_ticker,
        "status": "queued",
        "research": {},
        "last_refreshed_at": None,
    }
    result = db.watchlist.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    log.info("watchlist: added %s (via=%s primary=%s)", ticker, added_via, primary_ticker)
    return {"ok": True, "existing": False, "entry": doc}


def remove_entry(ticker: str) -> dict:
    """Remove a ticker. If it was a user-added primary, also removes its
    auto-added competitors so the watchlist doesn't accumulate stale peers."""
    db = _get_db()
    if db is None:
        return {"ok": False}
    ticker = ticker.upper().strip()
    main = db.watchlist.delete_one({"ticker": ticker})
    cleared = 0
    if main.deleted_count:
        peers = db.watchlist.delete_many({"primary_ticker": ticker})
        cleared = peers.deleted_count
    return {"ok": True, "removed": main.deleted_count, "competitors_cleared": cleared}


def list_entries() -> list[dict]:
    db = _get_db()
    if db is None:
        return []
    rows = list(db.watchlist.find().sort("added_at", -1))
    for r in rows:
        r["_id"] = str(r["_id"])
    return rows


def get_entry(ticker: str) -> Optional[dict]:
    db = _get_db()
    if db is None:
        return None
    row = db.watchlist.find_one({"ticker": ticker.upper()})
    if row:
        row["_id"] = str(row["_id"])
    return row


def set_status(ticker: str, status: str, research: Optional[dict] = None):
    db = _get_db()
    if db is None:
        return
    update = {"status": status}
    if research is not None:
        update["research"] = research
        update["last_refreshed_at"] = _now()
    db.watchlist.update_one({"ticker": ticker.upper()}, {"$set": update})
