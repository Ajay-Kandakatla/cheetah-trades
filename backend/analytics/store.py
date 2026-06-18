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
        # Web-vitals / page-load RUM samples (one doc per metric reading).
        _db.perf_events.create_index([("ts", DESCENDING)])
        _db.perf_events.create_index([("module", ASCENDING), ("metric", ASCENDING)])
        try:
            _db.perf_events.create_index("ts_dt", expireAfterSeconds=_TTL_DAYS * 86400)
        except Exception:
            pass
        # "What's new" — per-user record of which shipped features they've seen.
        # feature_views is the durable seen-set (no TTL); feature_events is the
        # analytics log (impressions + first views, TTL'd like the rest).
        _db.feature_views.create_index(
            [("user_email", ASCENDING), ("feature", ASCENDING)], unique=True)
        _db.feature_events.create_index([("ts", DESCENDING)])
        try:
            _db.feature_events.create_index("ts_dt", expireAfterSeconds=_TTL_DAYS * 86400)
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


# ---------------------------------------------------------------------------
# Web-vitals / page-load performance (RUM) — Ajay 2026-06-17: capture real page
# load + paint timings (to OUR backend, no third party) so we can see which
# pages are slow and how they fare on low-bandwidth connections, then optimize.
# ---------------------------------------------------------------------------

# Rating thresholds straight from the web-vitals spec (web.dev/articles/vitals).
# Values are in ms except CLS (unitless). 'route_load' is our own SPA route→
# data-ready timing. (good_max, needs_improvement_max).
PERF_THRESHOLDS = {
    "LCP":        (2500.0, 4000.0),
    "FCP":        (1800.0, 3000.0),
    "INP":        (200.0, 500.0),
    "TTFB":       (800.0, 1800.0),
    "CLS":        (0.1, 0.25),
    "route_load": (1000.0, 3000.0),
}
SLOW_CONNS = {"slow-2g", "2g", "3g"}        # the "low internet" buckets


def _rating(metric: str, value: float) -> str:
    t = PERF_THRESHOLDS.get(metric)
    if not t:
        return "unknown"
    good, poor = t
    if value <= good:
        return "good"
    if value <= poor:
        return "needs-improvement"
    return "poor"


def _module_of(route: str) -> str:
    seg = (route or "").strip("/").split("/")[0]
    return (seg or "home").lower()[:40]


def record_perf(events: list) -> int:
    """Persist a batch of web-vitals / page-load samples. Returns the count
    stored. Best-effort: skips malformed entries, never raises."""
    db = _get_db()
    if db is None or not events:
        return 0
    now = _now()
    now_dt = datetime.now(tz=timezone.utc)
    day = _today_et()
    docs = []
    for e in events:
        if not isinstance(e, dict):
            continue
        metric = str(e.get("metric") or "")[:24]
        if metric not in PERF_THRESHOLDS:
            continue
        try:
            value = float(e.get("value"))
        except (TypeError, ValueError):
            continue
        if value != value or value < 0 or value > 1e7:        # NaN / nonsense guard
            continue
        route = str(e.get("route") or "/")[:200]
        docs.append({
            "metric":     metric,
            "value":      value,
            "rating":     _rating(metric, value),
            "route":      route,
            "module":     _module_of(route),
            "conn":       str(e.get("conn") or "unknown")[:12],
            "downlink":   _safe_float(e.get("downlink")),
            "save_data":  bool(e.get("save_data")),
            "session_id": str(e.get("session_id") or "")[:64],
            "ts":         now,
            "ts_dt":      now_dt,
            "day_et":     day,
        })
    if not docs:
        return 0
    try:
        db.perf_events.insert_many(docs, ordered=False)
        return len(docs)
    except Exception as exc:
        log.debug("record_perf: %s", exc)
        return 0


def _safe_float(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def _percentile(sorted_vals: list, q: float):
    """Linear-interpolation percentile (q in [0,1]) over a pre-sorted list."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    frac = pos - lo
    if lo + 1 < len(sorted_vals):
        return sorted_vals[lo] + frac * (sorted_vals[lo + 1] - sorted_vals[lo])
    return sorted_vals[lo]


def _stat(vals: list) -> dict:
    s = sorted(vals)
    def r(q):
        p = _percentile(s, q)
        return round(p, 3) if p is not None else None
    return {"n": len(s), "p50": r(0.5), "p75": r(0.75), "p95": r(0.95)}


def _summarize(docs: list, days: int) -> dict:
    """Pure roll-up of perf docs → p50/p75/p95 per (module, metric) and per
    metric overall, PLUS a slow-vs-fast-connection split per metric (so we can
    see how much worse the app is on low-bandwidth links). No Mongo here — unit
    tested directly."""
    from collections import defaultdict
    by_mod_metric: dict = defaultdict(list)
    by_metric: dict = defaultdict(list)
    slow: dict = defaultdict(list)
    fast: dict = defaultdict(list)
    for d in docs:
        metric = d.get("metric")
        if metric not in PERF_THRESHOLDS:
            continue
        try:
            v = float(d.get("value"))
        except (TypeError, ValueError):
            continue
        mod = d.get("module") or "home"
        by_mod_metric[(mod, metric)].append(v)
        by_metric[metric].append(v)
        (slow if d.get("conn") in SLOW_CONNS else fast)[metric].append(v)

    routes = [{"module": mod, "metric": metric, **_stat(vals)}
              for (mod, metric), vals in sorted(by_mod_metric.items())]
    metrics = []
    for m in sorted(by_metric):
        vals = by_metric[m]
        poor = sum(1 for v in vals if _rating(m, v) == "poor")
        metrics.append({
            "metric":    m,
            **_stat(vals),
            "poor_rate": round(poor / len(vals), 3) if vals else 0.0,
            "slow_conn": _stat(slow.get(m, [])),
            "fast_conn": _stat(fast.get(m, [])),
        })
    return {"routes": routes, "metrics": metrics, "n": len(docs),
            "window_days": days, "available": True}


def aggregate_perf(days: int = 14) -> dict:
    db = _get_db()
    if db is None:
        return {"routes": [], "metrics": [], "n": 0, "window_days": days, "available": False}
    cutoff = _now() - days * 86400
    try:
        docs = list(db.perf_events.find(
            {"ts": {"$gte": cutoff}},
            {"metric": 1, "value": 1, "module": 1, "conn": 1},
        ))
    except Exception as exc:
        log.debug("aggregate_perf: %s", exc)
        return {"routes": [], "metrics": [], "n": 0, "window_days": days, "available": False}
    return _summarize(docs, days)


# ---------------------------------------------------------------------------
# "What's new" feature highlights (Ajay 2026-06-18: highlight each shipped
# feature until I've viewed it, and log the unviewed ones to analytics).
# ---------------------------------------------------------------------------

def feature_seen_set(email: str) -> list:
    """Feature ids this user has already viewed (the highlight is cleared)."""
    db = _get_db()
    if db is None or not email:
        return []
    try:
        return [d["feature"] for d in
                db.feature_views.find({"user_email": email.lower()}, {"feature": 1})]
    except Exception as exc:                       # noqa: BLE001
        log.debug("feature_seen_set: %s", exc)
        return []


def mark_feature_seen(email: str, feature: str) -> bool:
    """Record that the user has viewed a feature (clears its highlight) + log a
    'viewed' analytics event. Returns True if this was the FIRST view."""
    db = _get_db()
    feature = (feature or "").strip()[:60]
    if db is None or not email or not feature:
        return False
    now = _now()
    now_dt = datetime.now(tz=timezone.utc)
    try:
        res = db.feature_views.update_one(
            {"user_email": email.lower(), "feature": feature},
            {"$setOnInsert": {"user_email": email.lower(), "feature": feature,
                              "seen_at": now, "seen_at_dt": now_dt}},
            upsert=True,
        )
        newly = res.upserted_id is not None
        db.feature_events.insert_one({
            "user_email": email.lower(), "feature": feature, "kind": "viewed",
            "newly": newly, "ts": now, "ts_dt": now_dt,
        })
        return newly
    except Exception as exc:                       # noqa: BLE001
        log.debug("mark_feature_seen: %s", exc)
        return False


def log_feature_impressions(email: str, features: list) -> int:
    """Log that the user was SHOWN new-feature highlights they haven't opened
    yet (the 'until I view it, log it' signal). Returns count logged."""
    db = _get_db()
    if db is None or not email or not features:
        return 0
    now = _now()
    now_dt = datetime.now(tz=timezone.utc)
    docs = [{"user_email": email.lower(), "feature": str(f).strip()[:60],
             "kind": "impression", "ts": now, "ts_dt": now_dt}
            for f in features[:50] if str(f or "").strip()]
    if not docs:
        return 0
    try:
        db.feature_events.insert_many(docs, ordered=False)
        return len(docs)
    except Exception as exc:                       # noqa: BLE001
        log.debug("log_feature_impressions: %s", exc)
        return 0


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
