"""Mongo persistence for usage events.

Schema (collection ``usage_events``):
  {
    "user_email":   "ajaykandakatla@gmail.com",
    "module":       "sepa" | "morning" | "food" | "house" | ... ,
    "route":        "/sepa" | "/sepa/MU" | "/morning",
    "started_at":   1700000000,         # epoch seconds
    "ended_at":     1700000050,         # set on second beacon (leaving)
    "duration_sec": 50,                  # ended_at - started_at
    "day_et":       "2026-05-14",
    "session_id":   "abc123…",          # rolling per-tab id, expires 30min
  }

A "visit" is one row. When a user navigates to /sepa, the frontend POSTs
to log a fresh row (server returns its _id). Periodic heartbeats and the
final "leaving" beacon update `ended_at` + `duration_sec` on that row.

Indexes:
  - (user_email, started_at desc) — recent activity per user
  - (module, day_et)               — dailies per module
  - (day_et)                       — total daily activity
  - TTL on started_at: 180 days    — drops old data automatically
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("analytics.store")

_db = None
_TTL_DAYS = 180


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
        _db.usage_events.create_index([("user_email", ASCENDING), ("started_at", DESCENDING)])
        _db.usage_events.create_index([("module", ASCENDING), ("day_et", ASCENDING)])
        _db.usage_events.create_index([("day_et", ASCENDING)])
        # TTL: 180-day retention on started_at (stored as datetime for TTL to work)
        try:
            _db.usage_events.create_index(
                "started_at_dt",
                expireAfterSeconds=_TTL_DAYS * 86400,
            )
        except Exception:
            pass
        return _db
    except Exception as exc:
        log.warning("analytics.store: mongo unavailable: %s", exc)
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _today_et() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


def start_event(*, user_email: str, module: str, route: str,
                session_id: Optional[str] = None) -> Optional[str]:
    """Insert a fresh visit row. Returns the row id so the client can
    later send a `end_event` beacon with the duration.

    Side effect: also records the visit in the user directory and fires
    a one-time admin notification on first-ever signin. Both calls are
    best-effort — analytics never blocks on a failed notification.
    """
    db = _get_db()
    if db is None:
        return None
    # Record visit + fire admin push if this is the user's first time.
    # Done first so we don't lose the "first event" signal even if the
    # insert below races.
    try:
        from users import store as user_store
        from push import hooks as push_hooks
        signin = user_store.record_signin(user_email)
        if signin.get("is_first_seen"):
            try:
                push_hooks.notify_new_user(user_email)
            except Exception as exc:
                log.debug("notify_new_user failed: %s", exc)
    except Exception as exc:
        log.debug("user record_signin failed: %s", exc)

    try:
        doc = {
            "user_email":     user_email.lower(),
            "module":         module,
            "route":          route,
            "started_at":     _now(),
            "started_at_dt":  datetime.now(tz=timezone.utc),
            "ended_at":       None,
            "duration_sec":   0,
            "day_et":         _today_et(),
            "session_id":     session_id or "",
        }
        res = db.usage_events.insert_one(doc)
        return str(res.inserted_id)
    except Exception as exc:
        log.debug("analytics.start_event: %s", exc)
        return None


def end_event(event_id: str, *, duration_sec: Optional[int] = None) -> bool:
    """Close out a visit. If duration_sec is omitted, computes it from
    started_at to now (use this when the client sends only an id)."""
    db = _get_db()
    if db is None or not event_id:
        return False
    try:
        from bson import ObjectId
        oid = ObjectId(event_id)
        doc = db.usage_events.find_one({"_id": oid})
        if not doc:
            return False
        end_ts = _now()
        dur = duration_sec if duration_sec is not None else max(0, end_ts - int(doc.get("started_at") or end_ts))
        # Cap absurd durations — if the user left the tab open overnight,
        # don't count 8 hours as engaged time. Practical max: 2 hours/visit.
        dur = min(dur, 7200)
        db.usage_events.update_one(
            {"_id": oid},
            {"$set": {"ended_at": end_ts, "duration_sec": int(dur)}},
        )
        return True
    except Exception as exc:
        log.debug("analytics.end_event: %s", exc)
        return False


def aggregate_dashboard(days: int = 14) -> dict:
    """Roll-up for the admin dashboard. Returns:
      {
        users: [
          {email, total_sec, modules: {sepa: 1234, morning: 567, ...},
           last_seen_iso, sessions: int},
          ...
        ],
        modules: [{module, total_sec, users: int, sessions: int}, ...],
        daily: [{day_et, total_sec, users: int, sessions: int}, ...],
        total_users: int,
        total_sessions: int,
        total_sec: int,
        window_days: int,
      }
    """
    db = _get_db()
    if db is None:
        return {"users": [], "modules": [], "daily": [], "total_users": 0,
                "total_sessions": 0, "total_sec": 0, "window_days": days}
    from datetime import timedelta
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp()

    # Pipeline: filter, group by user + module, then aggregate further in Python.
    pipe = [
        {"$match": {"started_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": {"user": "$user_email", "module": "$module"},
            "total_sec": {"$sum": "$duration_sec"},
            "sessions":  {"$sum": 1},
            "last_seen": {"$max": "$started_at"},
        }},
    ]
    rows = list(db.usage_events.aggregate(pipe))

    # Build user-level aggregation
    users_map: dict[str, dict] = {}
    modules_map: dict[str, dict] = {}
    for r in rows:
        u = r["_id"]["user"]
        m = r["_id"]["module"]
        sec = int(r.get("total_sec") or 0)
        sess = int(r.get("sessions") or 0)
        last = int(r.get("last_seen") or 0)

        if u not in users_map:
            users_map[u] = {"email": u, "total_sec": 0, "sessions": 0, "modules": {}, "last_seen": 0}
        users_map[u]["total_sec"] += sec
        users_map[u]["sessions"]  += sess
        users_map[u]["modules"][m] = sec
        if last > users_map[u]["last_seen"]:
            users_map[u]["last_seen"] = last

        if m not in modules_map:
            modules_map[m] = {"module": m, "total_sec": 0, "users_set": set(), "sessions": 0}
        modules_map[m]["total_sec"] += sec
        modules_map[m]["users_set"].add(u)
        modules_map[m]["sessions"]  += sess

    # Format users
    users = sorted(users_map.values(), key=lambda x: -x["total_sec"])
    for u in users:
        u["last_seen_iso"] = (
            datetime.fromtimestamp(u["last_seen"], tz=timezone.utc).isoformat()
            if u["last_seen"] else None
        )
        u.pop("last_seen", None)

    modules = []
    for m in modules_map.values():
        modules.append({
            "module":   m["module"],
            "total_sec": m["total_sec"],
            "users":    len(m["users_set"]),
            "sessions": m["sessions"],
        })
    modules.sort(key=lambda x: -x["total_sec"])

    # Daily aggregate
    daily_pipe = [
        {"$match": {"started_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$day_et",
            "total_sec":  {"$sum": "$duration_sec"},
            "users_set":  {"$addToSet": "$user_email"},
            "sessions":   {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    daily = []
    for r in db.usage_events.aggregate(daily_pipe):
        daily.append({
            "day_et":    r["_id"],
            "total_sec": int(r.get("total_sec") or 0),
            "users":     len(r.get("users_set") or []),
            "sessions":  int(r.get("sessions") or 0),
        })

    return {
        "users":           users,
        "modules":         modules,
        "daily":           daily,
        "total_users":     len(users),
        "total_sessions":  sum(u["sessions"] for u in users),
        "total_sec":       sum(u["total_sec"] for u in users),
        "window_days":     days,
    }


def personal_heatmap(email: str, days: int = 30) -> dict:
    """Per-user usage rollup for the /usage page: top modules/routes by visits +
    dwell, and a weekday(Sun=0)×hour(ET) heatmap of when the app is used.
    Reads the same usage_events the page-view tracker already writes."""
    from collections import defaultdict
    db = _get_db()
    empty = {"available": False, "modules": [], "routes": [], "heatmap": {},
             "total_visits": 0, "total_sec": 0, "window_days": days}
    if db is None or not email:
        return empty
    try:
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
    except Exception:
        et = None
    cutoff = _now() - days * 86400
    mods: dict = defaultdict(lambda: {"visits": 0, "total_sec": 0})
    routes: dict = defaultdict(lambda: {"visits": 0, "total_sec": 0})
    heat: dict = defaultdict(int)
    total_visits = total_sec = 0
    try:
        cur = db.usage_events.find(
            {"user_email": email, "started_at": {"$gte": cutoff}},
            {"module": 1, "route": 1, "started_at_dt": 1, "duration_sec": 1},
        )
        for d in cur:
            m, r = (d.get("module") or "other"), (d.get("route") or "/")
            dur = int(d.get("duration_sec") or 0)
            mods[m]["visits"] += 1; mods[m]["total_sec"] += dur
            routes[r]["visits"] += 1; routes[r]["total_sec"] += dur
            total_visits += 1; total_sec += dur
            dt = d.get("started_at_dt")
            if dt is not None and et is not None:
                try:
                    e = dt.astimezone(et)
                    heat[f"{(e.weekday() + 1) % 7}_{e.hour}"] += 1   # Mon=0 -> Sun=0
                except Exception:
                    pass
    except Exception:
        return empty

    def _top(dd):
        return sorted(({"key": k, **v} for k, v in dd.items()),
                      key=lambda x: -x["visits"])[:30]

    return {"available": True, "total_visits": total_visits, "total_sec": total_sec,
            "modules": _top(mods), "routes": _top(routes),
            "heatmap": dict(heat), "window_days": days}
