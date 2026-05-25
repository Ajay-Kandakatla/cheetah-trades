"""Push notification history — persist every push for later review.

Why this exists (user feedback 2026-05-21): some push notifications get
truncated mid-sentence on iOS / Android (~180 char body cap on lock
screen) so the lesson or the breakout reason cuts off. By persisting
the FULL untruncated payload server-side and exposing a "recent
notifications" panel, the user can re-read whatever was clipped from
any device.

Schema (push_history collection)
--------------------------------
    {
      ts:         epoch_sec,
      ts_iso:     UTC datetime,
      title:      str,
      body:       str,             # full untruncated body
      kind:       str | None,      # 'volume_breakout', 'minervini_flashcards', etc.
      ticker:     str | None,
      url:        str | None,      # tap-route
      user_email: str | None,      # None = broadcast
      sent:       int,             # devices reached
      failed:     int,             # delivery failures
      total:      int,             # devices targeted
    }

Indexes
  * (user_email, ts desc) — fast per-user history query
  * (ts_iso) TTL 90 days  — collection self-prunes; nobody needs a
                            year-old "volume breakout" notification

Visibility model: each user sees their OWN pushes (user_email matches)
PLUS all broadcasts (user_email is null). The frontend already filters
through this lens via the /push/history endpoint passing the caller's
email.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("push.history")

_coll = None
_disabled = False
_TTL_DAYS = 90


def _get_coll():
    """Lazy-init the push_history collection with required indexes.

    Failures are remembered (``_disabled``) so we don't pay the
    connect-retry cost on every push — if Mongo is down at startup,
    the rest of the push pipeline still works; history just becomes
    a no-op until restart."""
    global _coll, _disabled
    if _disabled:
        return None
    if _coll is not None:
        return _coll
    try:
        from pymongo import MongoClient, ASCENDING, DESCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        c = client[db_name].push_history
        c.create_index([("user_email", ASCENDING), ("ts", DESCENDING)])
        try:
            # Mongo TTL is on a datetime field — use ts_iso.
            c.create_index("ts_iso", expireAfterSeconds=_TTL_DAYS * 86400)
        except Exception:
            # Index may already exist with different TTL — leave it.
            pass
        _coll = c
        log.info("push.history: connected to %s/%s.push_history", url, db_name)
        return _coll
    except Exception as exc:
        log.warning("push.history mongo unavailable: %s", exc)
        _disabled = True
        return None


def record(payload: dict, *, user_email: Optional[str] = None,
           result: Optional[dict] = None) -> None:
    """Insert one history row. Best-effort — failures are swallowed.

    Called from push.sender after every send_to_all / send_to_user.
    The history write is in the same execution path as the live push,
    so it MUST be cheap + must never raise (delivery is what matters).
    """
    coll = _get_coll()
    if coll is None:
        return
    try:
        now = int(time.time())
        coll.insert_one({
            "ts":         now,
            "ts_iso":     datetime.fromtimestamp(now, tz=timezone.utc),
            "title":      payload.get("title"),
            "body":       payload.get("body"),
            "kind":       payload.get("kind"),
            "ticker":     payload.get("ticker"),
            "url":        payload.get("url"),
            "user_email": user_email,   # None for broadcasts
            "sent":       int((result or {}).get("sent", 0)),
            "failed":     int((result or {}).get("failed", 0)),
            "total":      int((result or {}).get("total_targets", 0)),
        })
    except Exception as exc:
        log.debug("push.history record failed: %s", exc)


def list_recent(user_email: Optional[str] = None, limit: int = 25,
                kind: Optional[str] = None) -> list[dict]:
    """Return the last N pushes visible to the given user.

    Visibility rules:
      * ``user_email`` set: returns broadcasts (user_email=None) PLUS
        pushes scoped to this user. That's what a normal user sees.
      * ``user_email`` None: returns everything (admin-only path).

    Caller is responsible for the admin gate; this function doesn't
    enforce it. The /push/history endpoint passes the caller's email
    by default.
    """
    coll = _get_coll()
    if coll is None:
        return []
    try:
        clauses: list[dict] = []
        if user_email:
            clauses.append({"$or": [
                {"user_email": user_email.lower()},
                {"user_email": None},
            ]})
        if kind:
            clauses.append({"kind": kind})
        q = {"$and": clauses} if clauses else {}
        cur = coll.find(q).sort("ts", -1).limit(limit)
        out: list[dict] = []
        for doc in cur:
            doc["_id"] = str(doc["_id"])
            if isinstance(doc.get("ts_iso"), datetime):
                doc["ts_iso"] = doc["ts_iso"].isoformat()
            out.append(doc)
        return out
    except Exception as exc:
        log.warning("push.history list failed: %s", exc)
        return []


__all__ = ["record", "list_recent"]
