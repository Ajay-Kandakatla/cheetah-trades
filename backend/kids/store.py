"""Mongo persistence for kids activity history.

One collection — `kids_activity_log` — stores every activity the parent
marks "✓ did this today" so the planner avoids same-day repeats and can
chart variety over time.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("kids.store")

_db = None


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING, DESCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        _db.kids_activity_log.create_index(
            [("owner_email", ASCENDING), ("date_et", ASCENDING), ("activity_id", ASCENDING)],
            unique=True,
        )
        _db.kids_activity_log.create_index([("date_et", DESCENDING)])
        return _db
    except Exception as exc:
        log.warning("kids.store: mongo unavailable: %s", exc)
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _today_et() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


def log_done(owner_email: str, activity_id: str,
             rating: Optional[int] = None,
             notes: str = "",
             date_et: Optional[str] = None) -> dict:
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    date_et = date_et or _today_et()
    db.kids_activity_log.update_one(
        {"owner_email": owner_email.lower(), "date_et": date_et, "activity_id": activity_id},
        {"$set": {"rating": rating, "notes": notes, "logged_at": _now()},
         "$setOnInsert": {
             "owner_email": owner_email.lower(),
             "date_et": date_et,
             "activity_id": activity_id,
             "created_at": _now(),
         }},
        upsert=True,
    )
    return {"ok": True}


def history(owner_email: str, days: int = 21) -> list[dict]:
    db = _get_db()
    if db is None:
        return []
    rows = list(db.kids_activity_log.find(
        {"owner_email": owner_email.lower()},
        sort=[("date_et", -1)],
    ).limit(days * 5))
    rows.reverse()
    for r in rows:
        r["_id"] = str(r["_id"])
    return rows


def recent_ids(owner_email: str, days: int = 7) -> set[str]:
    """IDs done in last N days — planner uses this to avoid same-week repeats."""
    db = _get_db()
    if db is None:
        return set()
    from datetime import date, timedelta
    today = date.fromisoformat(_today_et())
    cutoff = (today - timedelta(days=days)).isoformat()
    return {r["activity_id"] for r in db.kids_activity_log.find(
        {"owner_email": owner_email.lower(), "date_et": {"$gte": cutoff}},
        {"activity_id": 1},
    )}
