"""Mongo CRUD for personal portfolio holdings.

Schema (collection ``portfolio_holdings``):
  {
    "user_email":  "ajaykandakatla@gmail.com",
    "ticker":      "MU",
    "shares":      42.26,        # fractional shares allowed (Fidelity)
    "cost_basis":  24999.61,     # total $ in, not per-share
    "account":     "Individual - TOD X90778361",   # optional, for grouping
    "tags":        ["semis"],    # optional, used by brief to cluster
    "notes":       "...",        # optional
    "added_at":    1700000000,
    "updated_at":  1700000000,
  }

Unique key: (user_email, ticker, account). Two accounts can hold the
same ticker — they aggregate in the brief but stay separate rows so
edits don't collide.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("portfolio.store")

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
        # Composite unique — same ticker can sit in multiple accounts.
        _db.portfolio_holdings.create_index(
            [("user_email", ASCENDING), ("ticker", ASCENDING), ("account", ASCENDING)],
            unique=True,
        )
        return _db
    except Exception as exc:
        log.warning("portfolio.store: Mongo unavailable (%s) — disabling", exc)
        _disabled = True
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def upsert_holding(user_email: str, ticker: str, shares: float,
                   cost_basis: float, *,
                   account: Optional[str] = None,
                   tags: Optional[list[str]] = None,
                   notes: Optional[str] = None) -> dict:
    """Upsert a single (user, ticker, account) row. Updating shares/cost_basis
    is the normal case after a buy/sell — re-call with the new totals."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    ticker = ticker.upper().strip()
    if not ticker or len(ticker) > 10:
        return {"ok": False, "reason": "invalid ticker"}
    if shares is None or shares < 0:
        return {"ok": False, "reason": "shares must be >= 0"}

    account = (account or "default").strip()
    doc = {
        "user_email": user_email.lower(),
        "ticker":     ticker,
        "account":    account,
        "shares":     float(shares),
        "cost_basis": float(cost_basis or 0),
        "tags":       tags or [],
        "notes":      notes or "",
        "updated_at": _now(),
    }
    db.portfolio_holdings.update_one(
        {"user_email": user_email.lower(), "ticker": ticker, "account": account},
        {"$set": doc, "$setOnInsert": {"added_at": _now()}},
        upsert=True,
    )
    return {"ok": True, "ticker": ticker, "shares": shares}


def remove_holding(user_email: str, ticker: str,
                   account: Optional[str] = None) -> dict:
    db = _get_db()
    if db is None:
        return {"ok": False}
    q: dict = {"user_email": user_email.lower(), "ticker": ticker.upper()}
    if account:
        q["account"] = account
    res = db.portfolio_holdings.delete_many(q)
    return {"ok": True, "removed": res.deleted_count}


def list_holdings(user_email: str) -> list[dict]:
    db = _get_db()
    if db is None:
        return []
    rows = list(db.portfolio_holdings.find({"user_email": user_email.lower()}))
    for r in rows:
        r["_id"] = str(r["_id"])
    # Sort by cost_basis desc — biggest positions first.
    rows.sort(key=lambda r: -float(r.get("cost_basis") or 0))
    return rows
