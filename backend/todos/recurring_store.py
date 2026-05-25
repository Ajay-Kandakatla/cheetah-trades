"""User-managed recurring todo rules with day-of-week scheduling.

A "rule" is a template that fires a todo on specific weekdays at a
specific time. The 6 AM ET cron (todos.daily_recurring) reads all rules
matching today's weekday and materializes them as actual rows in the
`todos` collection — the existing reminder.fire_due cron then pushes
them at the configured notify time.

Schema (`recurring_todos` collection)
-------------------------------------
    {
      _id:         ObjectId,
      user_email:  "ajaykandakatla@gmail.com",
      text:        "Take out trash",
      days_of_week: [1],                # 0=Mon … 6=Sun (Python isoweekday-1)
      hour:        9,                   # 0..23, ET wall-clock
      minute:      0,                   # 0..59
      important:   false,
      ticker:      null,                # optional ticker tag (rare for recurring)
      active:      true,                # soft-disable without deleting
      created_at:  epoch,
      updated_at:  epoch,
    }

Day-of-week numbering follows ``datetime.weekday()`` — Monday is 0,
Sunday is 6. Mirrors the JS convention shifted by one (JS uses 0=Sun).
The frontend translates between the two.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Iterable, Optional

log = logging.getLogger("todos.recurring_store")

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
        # Lookups always start "rules for THIS user" — index keeps
        # list_rules() cheap regardless of how many other users exist.
        _db.recurring_todos.create_index(
            [("user_email", ASCENDING), ("active", ASCENDING)]
        )
        return _db
    except Exception as exc:
        log.warning("recurring_store: Mongo unavailable (%s) — disabling", exc)
        _disabled = True
        return None


def _now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


# ----------------------------------------------------------------------
# Validation helpers
# ----------------------------------------------------------------------
def _clean_days(raw: Iterable) -> list[int]:
    """Sanitize day_of_week input. Returns sorted unique list of valid
    [0..6] ints; drops anything else. Empty result means "never fires"
    (probably a UI mistake — caller should reject)."""
    out: set[int] = set()
    for v in raw or ():
        try:
            i = int(v)
            if 0 <= i <= 6:
                out.add(i)
        except (TypeError, ValueError):
            continue
    return sorted(out)


def _clean_hour_minute(hour, minute) -> tuple[int, int]:
    """Clamp to valid wall-clock ranges. Anything wonky → 09:00."""
    try:
        h = int(hour)
    except (TypeError, ValueError):
        h = 9
    try:
        m = int(minute)
    except (TypeError, ValueError):
        m = 0
    h = max(0, min(23, h))
    m = max(0, min(59, m))
    return h, m


# ----------------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------------
def list_rules(user_email: str, *, active_only: bool = False) -> list[dict]:
    db = _get_db()
    if db is None:
        return []
    q: dict = {"user_email": user_email.lower()}
    if active_only:
        q["active"] = True
    rows = []
    for r in db.recurring_todos.find(q).sort([("hour", 1), ("minute", 1)]):
        r["_id"] = str(r["_id"])
        rows.append(r)
    return rows


def create_rule(
    user_email: str,
    *,
    text: str,
    days_of_week: Iterable,
    hour: int,
    minute: int,
    important: bool = False,
    ticker: Optional[str] = None,
) -> dict:
    """Insert a new rule. Validates inputs; returns
    ``{"ok": True, "rule": {...}}`` or ``{"ok": False, "reason": …}``."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    text = (text or "").strip()
    if not text:
        return {"ok": False, "reason": "text required"}
    days = _clean_days(days_of_week)
    if not days:
        return {"ok": False, "reason": "at least one day required"}
    h, m = _clean_hour_minute(hour, minute)

    doc = {
        "user_email":   user_email.lower(),
        "text":         text[:300],
        "days_of_week": days,
        "hour":         h,
        "minute":       m,
        "important":    bool(important),
        "ticker":       ticker.upper() if ticker else None,
        "active":       True,
        "created_at":   _now(),
        "updated_at":   _now(),
    }
    res = db.recurring_todos.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return {"ok": True, "rule": doc}


def update_rule(rule_id: str, user_email: str, patch: dict) -> dict:
    """Modify selected fields on a rule the caller owns. Anything not
    in the allowlist is silently dropped — prevents the caller from
    changing user_email, created_at, etc."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    from bson import ObjectId
    try:
        oid = ObjectId(rule_id)
    except Exception:
        return {"ok": False, "reason": "bad id"}

    allowed = {"text", "days_of_week", "hour", "minute", "important", "ticker", "active"}
    update: dict = {"updated_at": _now()}
    for k, v in (patch or {}).items():
        if k not in allowed:
            continue
        if k == "text":
            v = (v or "").strip()[:300]
            if not v:
                return {"ok": False, "reason": "text cannot be empty"}
        elif k == "days_of_week":
            v = _clean_days(v)
            if not v:
                return {"ok": False, "reason": "at least one day required"}
        elif k == "hour":
            v, _m_unused = _clean_hour_minute(v, 0)
        elif k == "minute":
            _h_unused, v = _clean_hour_minute(0, v)
        elif k == "important":
            v = bool(v)
        elif k == "active":
            v = bool(v)
        elif k == "ticker":
            v = v.upper() if v else None
        update[k] = v

    if len(update) == 1:                 # only the timestamp — nothing to do
        return {"ok": True, "no_changes": True}

    res = db.recurring_todos.update_one(
        {"_id": oid, "user_email": user_email.lower()},
        {"$set": update},
    )
    if res.matched_count == 0:
        return {"ok": False, "reason": "not found"}
    return {"ok": True}


def delete_rule(rule_id: str, user_email: str) -> dict:
    db = _get_db()
    if db is None:
        return {"ok": False}
    from bson import ObjectId
    try:
        oid = ObjectId(rule_id)
    except Exception:
        return {"ok": False, "reason": "bad id"}
    res = db.recurring_todos.delete_one(
        {"_id": oid, "user_email": user_email.lower()},
    )
    return {"ok": True, "deleted": res.deleted_count}


# ----------------------------------------------------------------------
# Read for materializer
# ----------------------------------------------------------------------
def rules_for_weekday(weekday: int) -> list[dict]:
    """Every active rule whose ``days_of_week`` includes ``weekday``
    (Monday=0). Used by the morning materializer cron — not filtered
    by user_email here because the cron iterates across all users."""
    db = _get_db()
    if db is None:
        return []
    rows = []
    for r in db.recurring_todos.find({
        "active":       True,
        "days_of_week": weekday,         # Mongo matches scalar against array element
    }):
        r["_id"] = str(r["_id"])
        rows.append(r)
    return rows
