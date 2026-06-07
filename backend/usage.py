"""Usage tracking — what Ajay actually uses, captured for future context.

Records page-views and key feature interactions into Mongo `usage_stats`: one
doc per (kind, key) with a running count, last-seen, and weekday×hour buckets.
Powers the /usage heatmap so a glance (and future sessions) can tell what's used
heavily vs. ignored. Owner-only; stores route/feature NAMES only — no PII, no
payloads, no query strings.
"""
from __future__ import annotations

import logging
import os
import time

log = logging.getLogger("usage")

MAX_EVENTS_PER_CALL = 200     # cap a single batch (defensive)
MAX_KEY_LEN = 80


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[os.getenv("MONGO_DB", "cheetah")].usage_stats
    except Exception:
        return None


def _clean_key(k):
    if not isinstance(k, str):
        return None
    # route/feature names only — strip any query string defensively
    k = k.split("?")[0].strip()[:MAX_KEY_LEN]
    return k or None


def record_events(events) -> dict:
    """Persist a batch of usage events.

    events: list of {kind: 'page'|'feature', key: str, weekday?: 0-6, hour?: 0-23}
    """
    coll = _coll()
    if coll is None or not isinstance(events, list):
        return {"recorded": 0}
    n = 0
    for e in events[:MAX_EVENTS_PER_CALL]:
        if not isinstance(e, dict):
            continue
        kind = e.get("kind")
        if kind not in ("page", "feature"):
            continue
        key = _clean_key(e.get("key"))
        if not key:
            continue
        wd, hr = e.get("weekday"), e.get("hour")
        wd = wd if isinstance(wd, int) and 0 <= wd <= 6 else None
        hr = hr if isinstance(hr, int) and 0 <= hr <= 23 else None
        inc = {"count": 1}
        if wd is not None and hr is not None:
            inc[f"buckets.{wd}_{hr}"] = 1
        try:
            coll.update_one(
                {"_id": f"{kind}:{key}"},
                {"$inc": inc,
                 "$set": {"kind": kind, "key": key, "last_seen": int(time.time())}},
                upsert=True,
            )
            n += 1
        except Exception as exc:
            log.debug("usage record failed for %s: %s", key, exc)
    return {"recorded": n}


def feature_counts(top: int = 50) -> list:
    """Top in-page feature interactions (chips/filters/modals) from usage_stats —
    the signal the page-view analytics never captured."""
    coll = _coll()
    if coll is None:
        return []
    out = []
    try:
        for d in coll.find({"kind": "feature"}):
            out.append({"key": d.get("key"), "count": int(d.get("count") or 0),
                        "last_seen": d.get("last_seen")})
    except Exception as exc:
        log.debug("usage feature_counts failed: %s", exc)
        return []
    out.sort(key=lambda r: -r["count"])
    return out[:top]


def summary(email: str = "", days: int = 30, top: int = 50) -> dict:
    """The /usage heatmap payload: page usage + weekday×hour heatmap come from the
    existing page-view analytics (per user); in-page feature clicks come from our
    own usage_stats. One combined read."""
    try:
        from analytics import store as analytics_store
        page = analytics_store.personal_heatmap(email, days=days)
    except Exception as exc:
        log.debug("usage summary page rollup failed: %s", exc)
        page = {"available": False, "modules": [], "routes": [], "heatmap": {},
                "total_visits": 0, "total_sec": 0, "window_days": days}
    return {
        "available": page.get("available", False),
        "generated_at": int(time.time()),
        "window_days": days,
        "total_visits": page.get("total_visits", 0),
        "total_sec": page.get("total_sec", 0),
        "modules": page.get("modules", []),
        "routes": page.get("routes", []),
        "heatmap": page.get("heatmap", {}),
        "features": feature_counts(top),
    }
