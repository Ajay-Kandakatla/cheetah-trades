"""Mongo CRUD for the personal todo list."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("todos.store")

_db = None


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING
        client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                              serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        _db.todos.create_index("created_at")
        _db.todos.create_index([("user_email", ASCENDING), ("status", ASCENDING),
                                  ("notify_at", ASCENDING)])
        # Backfill: stamp pre-multiuser todos with the default user so they
        # remain reachable post-migration.
        from os import getenv as _g
        default_user = _g("DEFAULT_USER_EMAIL", "ajay@example.com")
        _db.todos.update_many(
            {"user_email": {"$exists": False}},
            {"$set": {"user_email": default_user}},
        )
        return _db
    except Exception as exc:
        log.warning("todos.store: Mongo unavailable: %s", exc)
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def add_todo(text: str, *, user_email: str,
             due_at: Optional[int] = None,
             notify_at: Optional[int] = None,
             ticker: Optional[str] = None,
             important: bool = False,
             workspace: str = "personal",
             ai_task: bool = False,
             source: str = "manual") -> dict:
    """Insert a new todo. New fields (2026-05-17):

      - workspace: 'personal' | 'work' — UI tab + dashboard grouping.
        Any other string is accepted but won't get a visual treatment.
      - ai_task: when True, the LLM runner cron picks it up, does
        research via the local LM Studio model, and stuffs the
        markdown result back into ai_result. ai_status tracks the
        lifecycle.
      - source: free-form provenance tag ('manual', 'admin', 'claude',
        'cron', 'recurring'). Used by the dashboard + the UI badge so
        AI-generated rows look different from hand-typed ones.
    """
    db = _get_db()
    if db is None:
        return {"ok": False}
    text = (text or "").strip()
    if not text:
        return {"ok": False, "reason": "empty text"}
    workspace = (workspace or "personal").lower().strip() or "personal"
    if workspace not in ("personal", "work"):
        workspace = "personal"
    doc = {
        "user_email": user_email.lower(),
        "text": text[:300],
        "created_at": _now(),
        "due_at": due_at,
        "notify_at": notify_at,
        "notified_at": None,
        "status": "active",
        "completed_at": None,
        "ticker": ticker.upper() if ticker else None,
        "important": bool(important),
        # New axes — workspace + source for grouping, ai_* for the
        # research-by-LLM pipeline (see todos/llm_runner.py).
        "workspace": workspace,
        "source":    source or "manual",
        "ai_task":   bool(ai_task),
        "ai_status": "pending" if ai_task else None,
        # ai_summary is the brief TL;DR extracted from ai_result —
        # what we show inline on the (now-completed) row so the user
        # doesn't have to expand to know if it's worth reading. Full
        # markdown stays in ai_result.
        "ai_summary": None,
        "ai_result":  None,
        "ai_processed_at": None,
    }
    res = db.todos.insert_one(doc)
    doc["_id"] = str(res.inserted_id)
    return {"ok": True, "todo": doc}


def list_todos(*, user_email: str,
               status: Optional[str] = None,
               important_only: bool = False,
               workspace: Optional[str] = None) -> list[dict]:
    """List a user's todos.

    ``workspace`` filter behavior:
      - None or 'all'  → both personal + work
      - 'personal'     → only the personal bucket (legacy todos with no
                         workspace field are treated as personal too —
                         see the {"$in": [...], None: matched-by-$or}
                         clause below).
      - 'work'         → only work-tagged todos.
    """
    db = _get_db()
    if db is None:
        return []
    q: dict = {"user_email": user_email.lower()}
    if status and status != "all":
        q["status"] = status
    if important_only:
        q["important"] = True
    if workspace == "personal":
        # Treat absent / null workspace as personal so legacy rows still
        # show up under the default tab. Same trick the multi-user
        # migration used for user_email.
        q["$or"] = [{"workspace": "personal"}, {"workspace": None}, {"workspace": {"$exists": False}}]
    elif workspace == "work":
        q["workspace"] = "work"
    rows = list(db.todos.find(q).sort([
        ("status", 1),
        ("important", -1),
        ("notify_at", 1),
        ("due_at", 1),
        ("created_at", -1),
    ]))
    for r in rows:
        r["_id"] = str(r["_id"])
    return rows


# ----------------------------------------------------------------------
# AI / LLM helpers
# ----------------------------------------------------------------------
def list_pending_ai_tasks(limit: int = 5) -> list[dict]:
    """Find AI tasks that haven't been processed yet. Used by the LLM
    runner cron. Caps at `limit` so a backlog of 50 doesn't blow up
    LM Studio's queue in one tick."""
    db = _get_db()
    if db is None:
        return []
    rows = list(db.todos.find({
        "ai_task":   True,
        "ai_status": "pending",
        "status":    "active",
    }).sort([("created_at", 1)]).limit(limit))
    for r in rows:
        r["_id"] = str(r["_id"])
    return rows


def set_ai_status(
    todo_id: str,
    *,
    status: str,
    result: Optional[str] = None,
    summary: Optional[str] = None,
    mark_completed: bool = False,
) -> dict:
    """Update the AI lifecycle fields on one todo. Status transitions:
    pending → running → done / failed.

    Extra knobs (2026-05-17):
      - summary: short TL;DR string surfaced inline in the row UI so
        the user doesn't have to expand the full ai_result to know
        what the AI found.
      - mark_completed: when True (typically on ``status='done'``),
        also flips the todo's main ``status`` to 'completed' and sets
        ``completed_at``. This is how an AI task moves itself into the
        Done section once the research is finished.
    """
    db = _get_db()
    if db is None:
        return {"ok": False}
    from bson import ObjectId
    try:
        oid = ObjectId(todo_id)
    except Exception:
        return {"ok": False, "reason": "bad id"}
    update: dict = {"ai_status": status}
    if result is not None:
        update["ai_result"] = result
    if summary is not None:
        update["ai_summary"] = summary
    if status in ("done", "failed"):
        update["ai_processed_at"] = _now()
    if mark_completed:
        update["status"]       = "completed"
        update["completed_at"] = _now()
    res = db.todos.update_one({"_id": oid}, {"$set": update})
    return {"ok": True, "matched": res.matched_count}


def get_todo(todo_id: str) -> Optional[dict]:
    """Read one todo by id. Used by callers that need the
    ``user_email`` field after an LLM run completes (so they can scope
    the push notification to that user only)."""
    db = _get_db()
    if db is None:
        return None
    from bson import ObjectId
    try:
        oid = ObjectId(todo_id)
    except Exception:
        return None
    doc = db.todos.find_one({"_id": oid})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


def dashboard_stats(user_email: str) -> dict:
    """Aggregated counts the /todos dashboard widget renders. Cheap —
    just a handful of count_documents calls. Acceptable to run in
    threadpool from the request handler since it's bounded I/O.
    """
    db = _get_db()
    if db is None:
        return {}
    u = user_email.lower()
    now = _now()
    # End-of-day in ET — same approximation list_for_brief uses.
    from datetime import datetime, timezone, timedelta
    et = datetime.now(tz=timezone(timedelta(hours=-5)))
    eod_local = et.replace(hour=23, minute=59, second=59, microsecond=0)
    eod_ts = int(eod_local.timestamp())

    def _personal_filter() -> dict:
        return {"$or": [{"workspace": "personal"}, {"workspace": None}, {"workspace": {"$exists": False}}]}

    def _count(extra: dict) -> int:
        q = {"user_email": u, **extra}
        return db.todos.count_documents(q)

    out: dict = {
        "open": {
            "total":    _count({"status": "active"}),
            "personal": _count({"status": "active", **_personal_filter()}),
            "work":     _count({"status": "active", "workspace": "work"}),
        },
        "today": _count({
            "status": "active",
            "$or": [
                {"notify_at": {"$gte": now - 3600, "$lte": eod_ts}},
                {"due_at":    {"$gte": now - 86400, "$lte": eod_ts}},
            ],
        }),
        "overdue": _count({
            "status": "active",
            "$or": [
                {"notify_at": {"$lt": now - 3600}, "notified_at": None},
                {"due_at":    {"$lt": now}},
            ],
        }),
        "important_open": _count({"status": "active", "important": True}),
        "ai": {
            "pending":  _count({"ai_task": True, "ai_status": "pending"}),
            "running":  _count({"ai_task": True, "ai_status": "running"}),
            "done":     _count({"ai_task": True, "ai_status": "done"}),
            "failed":   _count({"ai_task": True, "ai_status": "failed"}),
        },
        # Completed-in-last-7-days — proxy for productivity. Cheap because
        # completed_at is filtered.
        "completed_7d": _count({
            "status": "completed",
            "completed_at": {"$gte": now - 7 * 86400},
        }),
    }
    return out


def list_for_brief(*, user_email: str) -> dict:
    """Pull a small slice of todos for inclusion in the morning brief.

    Returns:
        important   — all active items flagged important
        today       — active items with notify_at OR due_at falling today (Eastern)
                      that aren't already in `important`
        upcoming_n  — count of remaining future-dated items
    """
    db = _get_db()
    if db is None:
        return {"important": [], "today": [], "upcoming_count": 0}

    from datetime import datetime, timezone, timedelta
    et = datetime.now(tz=timezone(timedelta(hours=-5)))
    eod_local = et.replace(hour=23, minute=59, second=59, microsecond=0)
    eod_ts = int(eod_local.timestamp())
    now_ts = _now()

    user_q = {"user_email": user_email.lower()}
    important = list(db.todos.find({
        **user_q, "status": "active", "important": True,
    }).sort([("notify_at", 1), ("due_at", 1), ("created_at", -1)]).limit(20))

    important_ids = {r["_id"] for r in important}
    today = list(db.todos.find({
        **user_q, "status": "active",
        "_id": {"$nin": list(important_ids)},
        "$or": [
            {"notify_at": {"$gte": now_ts - 3600, "$lte": eod_ts}},
            {"due_at": {"$gte": now_ts - 86400, "$lte": eod_ts}},
        ],
    }).sort([("notify_at", 1), ("due_at", 1)]).limit(20))

    upcoming_count = db.todos.count_documents({
        **user_q, "status": "active",
        "_id": {"$nin": list(important_ids) + [r["_id"] for r in today]},
        "$or": [
            {"notify_at": {"$gt": eod_ts}},
            {"due_at": {"$gt": eod_ts}},
        ],
    })

    def _strip(rows):
        return [{**r, "_id": str(r["_id"])} for r in rows]

    return {
        "important": _strip(important),
        "today": _strip(today),
        "upcoming_count": upcoming_count,
    }


def update_todo(todo_id: str, patch: dict, *, user_email: str) -> dict:
    db = _get_db()
    if db is None:
        return {"ok": False}
    from bson import ObjectId
    allowed = {"text", "due_at", "notify_at", "ticker", "status", "important"}
    update = {k: v for k, v in patch.items() if k in allowed}
    if "ticker" in update and update["ticker"]:
        update["ticker"] = update["ticker"].upper()
    if not update:
        return {"ok": False, "reason": "no valid fields"}
    if update.get("status") == "completed":
        update["completed_at"] = _now()
    # Scoped update — won't touch another user's todo even if the id is right.
    res = db.todos.update_one(
        {"_id": ObjectId(todo_id), "user_email": user_email.lower()},
        {"$set": update},
    )
    return {"ok": res.matched_count > 0}


def delete_todo(todo_id: str, *, user_email: str) -> dict:
    db = _get_db()
    if db is None:
        return {"ok": False}
    from bson import ObjectId
    res = db.todos.delete_one(
        {"_id": ObjectId(todo_id), "user_email": user_email.lower()},
    )
    return {"ok": True, "removed": res.deleted_count}


def find_due_reminders(limit: int = 50) -> list[dict]:
    """Active todos whose notify_at has passed and that haven't been notified yet."""
    db = _get_db()
    if db is None:
        return []
    now_ts = _now()
    rows = list(db.todos.find({
        "status": "active",
        "notified_at": None,
        "notify_at": {"$ne": None, "$lte": now_ts},
    }).sort("notify_at", 1).limit(limit))
    for r in rows:
        r["_id"] = str(r["_id"])
    return rows


def mark_notified(todo_id: str) -> None:
    db = _get_db()
    if db is None:
        return
    from bson import ObjectId
    db.todos.update_one({"_id": ObjectId(todo_id)},
                        {"$set": {"notified_at": _now()}})
