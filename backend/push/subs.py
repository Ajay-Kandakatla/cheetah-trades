"""Push subscription CRUD."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("push.subs")

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
        _db.push_subscriptions.create_index("endpoint", unique=True)
        _db.push_subscriptions.create_index("created_at")
        return _db
    except Exception as exc:
        log.warning("push.subs: Mongo unavailable: %s", exc)
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def add_subscription(subscription: dict, label: Optional[str] = None,
                     prefs: Optional[dict] = None,
                     user_email: Optional[str] = None) -> dict:
    """Insert or update a push subscription tied to a specific user.

    A single device endpoint can only belong to one user — if the same browser
    re-subscribes under a different email, it overwrites the user_email field
    so notifications follow the most-recent login.
    """
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}

    endpoint = subscription.get("endpoint")
    if not endpoint or not subscription.get("keys"):
        return {"ok": False, "reason": "invalid subscription"}

    import os
    if not user_email:
        user_email = os.getenv("DEFAULT_USER_EMAIL", "ajay@example.com")

    doc = {
        "endpoint": endpoint,
        "keys": subscription.get("keys"),
        "label": label or "device",
        "prefs": prefs or default_prefs(),
        "user_email": user_email.lower(),
        "updated_at": _now(),
    }
    db.push_subscriptions.update_one(
        {"endpoint": endpoint},
        {"$set": doc, "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )
    return {"ok": True, "endpoint": endpoint}


def remove_subscription(endpoint: str) -> dict:
    db = _get_db()
    if db is None:
        return {"ok": False}
    res = db.push_subscriptions.delete_one({"endpoint": endpoint})
    return {"ok": True, "removed": res.deleted_count}


def update_prefs(endpoint: str, prefs: dict) -> dict:
    db = _get_db()
    if db is None:
        return {"ok": False}
    db.push_subscriptions.update_one(
        {"endpoint": endpoint},
        {"$set": {"prefs": prefs, "updated_at": _now()}},
    )
    return {"ok": True}


def list_subscriptions(filter_kind: Optional[str] = None,
                       user_email: Optional[str] = None) -> list[dict]:
    """List active subscriptions, optionally filtered by alert kind and user.

    Excludes ``kind=mac`` rows — those are pure-prefs records for the native
    macOS app and have no real Web Push endpoint, so passing them to
    pywebpush would crash. Mac delivery is handled separately via SSE in
    push.mac_stream.

    Auto-backfills missing pref keys + user_email onto every subscription so
    future schema additions don't silently drop notifications for existing
    devices.
    """
    db = _get_db()
    if db is None:
        return []
    _backfill(db)
    # $ne: "mac" matches both rows where kind is something-else AND rows
    # where the kind field is absent (existing pre-migration data).
    q: dict = {"kind": {"$ne": "mac"}}
    if filter_kind:
        q[f"prefs.{filter_kind}"] = True
    if user_email:
        q["user_email"] = user_email.lower()
    return list(db.push_subscriptions.find(q))


# ---------------------------------------------------------------------------
# Mac-app subscriptions (kind=mac)
# ---------------------------------------------------------------------------
# These rows store per-device prefs only — no Web Push endpoint or keys. The
# native Pounce.app self-identifies via a stable ``device_id`` (a uuid kept
# in ~/Library/Application Support/Pounce/device_id), opens an SSE connection
# to /push/mac-stream, and the api container's drain task fans alerts out
# from the mac_outbox collection. See push/mac_stream.py.

def add_mac_subscription(device_id: str,
                         user_email: str,
                         label: Optional[str] = None,
                         prefs: Optional[dict] = None) -> dict:
    """Insert/upsert a kind=mac subscription. Idempotent — safe to call on
    every Pounce.app launch."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    if not device_id:
        return {"ok": False, "reason": "device_id required"}
    # Synthetic endpoint preserves the unique-endpoint index without
    # colliding with real Web Push URLs (which start with https://).
    synthetic_endpoint = f"mac:{device_id}"
    db.push_subscriptions.update_one(
        {"endpoint": synthetic_endpoint},
        {
            "$set": {
                "kind": "mac",
                "device_id": device_id,
                "label": label or "Mac",
                "user_email": (user_email or "").lower(),
                "updated_at": _now(),
            },
            "$setOnInsert": {
                "endpoint": synthetic_endpoint,
                "prefs": prefs or default_prefs(),
                "created_at": _now(),
            },
        },
        upsert=True,
    )
    return {"ok": True, "device_id": device_id, "endpoint": synthetic_endpoint}


def remove_mac_subscription(device_id: str) -> dict:
    db = _get_db()
    if db is None:
        return {"ok": False}
    res = db.push_subscriptions.delete_one(
        {"endpoint": f"mac:{device_id}", "kind": "mac"}
    )
    return {"ok": True, "removed": res.deleted_count}


def list_mac_device_ids(user_email: str,
                        filter_kind: Optional[str] = None) -> set[str]:
    """Return the set of mac device_ids for ``user_email`` whose prefs allow
    ``filter_kind``. Used by the SSE drain task to decide which clients to
    deliver each outbox doc to."""
    db = _get_db()
    if db is None:
        return set()
    q: dict = {"kind": "mac", "user_email": (user_email or "").lower()}
    if filter_kind:
        q[f"prefs.{filter_kind}"] = True
    return {r["device_id"] for r in db.push_subscriptions.find(q, {"device_id": 1})
            if r.get("device_id")}


def list_mac_subscriptions(user_email: str) -> list[dict]:
    """List all kind=mac subscriptions for one user. Used by /push/subscriptions
    so the /notifications page can render Mac devices alongside web/iPhone
    devices."""
    db = _get_db()
    if db is None:
        return []
    return list(db.push_subscriptions.find({
        "kind": "mac",
        "user_email": (user_email or "").lower(),
    }))


_backfilled = False


def _backfill(db):
    """Stamp missing pref keys + user_email on existing subscriptions so the
    multi-user migration doesn't lose any data."""
    global _backfilled
    if _backfilled:
        return
    import os
    default_user = os.getenv("DEFAULT_USER_EMAIL", "ajay@example.com")
    defaults = default_prefs()
    for sub in db.push_subscriptions.find({}):
        cur_prefs = sub.get("prefs") or {}
        merged_prefs = {**defaults, **cur_prefs}
        update: dict = {}
        if merged_prefs != cur_prefs:
            update["prefs"] = merged_prefs
        if "user_email" not in sub:
            update["user_email"] = default_user
        if update:
            db.push_subscriptions.update_one(
                {"_id": sub["_id"]}, {"$set": update},
            )
    _backfilled = True


def default_prefs() -> dict:
    """Default notification preferences when a new subscription registers."""
    return {
        "volume_breakout": True,      # SEPA volume breakout
        "rising_momentum": True,      # TWLO-style pre-breakout (routes to /track)
        "sepa_new_candidate": True,   # new VCP / Power Play setup
        "watchlist_breakout": True,   # any watchlist ticker fires a breakout
        "juggernaut_watchlist": True, # consolidated daily: watchlist names where
                                      # accumulation + rising momentum align
                                      # (fired by sepa.juggernaut cron)
        # SELL-side signals — Weinstein stage transitions. Default on
        # because these are the highest-value alerts for an active book
        # (catching a topping name 1-2 days early vs the morning brief
        # is the entire reason this exists).
        "stage_breakdown": True,           # any ticker rolls 2→3, 2→4, 3→4
        "watchlist_stage_breakdown": True, # same but only for watchlist names
        "price_alert": True,          # user-set price alerts
        "position_alert": True,       # stop / target hit on Lifeboard positions
        "morning_brief": True,        # 8:30am post-fast-scan summary
        "todo_reminder": True,        # personal todo list reminders (specific times)
        "todo_daily_digest": True,    # 7 AM ET daily summary push
        "macbook_deal": True,         # MacBook deal scraper — strict-verified URLs only
        "quiet_hours_enabled": False,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    }
