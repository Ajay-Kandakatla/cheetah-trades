"""Push subscription CRUD."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("push.subs")

# Retired alert kinds (Ajay 2026-06-13: "clean up all the alerts besides
# Minervini learning, buyable/Enter-zone, portfolio, market open/close, and
# household"). Delivery is hard-stopped here for these kinds regardless of any
# per-device pref still set to True, so the retired market-scan pushes can't
# fire for anyone — even a device that hasn't re-toggled. This is the single
# chokepoint: both the Web Push path (sender.send_to_user/all) and the Mac SSE
# path (mac_stream) filter through list_subscriptions / list_mac_device_ids.
# NOTE: ``price_alert`` is PAUSED, not gone — remove it from this set when the
# user re-adds custom price alerts.
DISABLED_ALERT_KINDS: frozenset[str] = frozenset({
    "sepa_new_candidate", "volume_breakout", "rising_momentum",
    "watchlist_breakout", "juggernaut_watchlist", "stage_breakdown",
    "watchlist_stage_breakdown", "morning_brief", "product_launch",
    "scalp_tape", "price_alert",
})

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


def _is_in_quiet_hours(prefs: dict, now: Optional[datetime] = None) -> bool:
    """True if ``now`` (server-local time — America/New_York in compose)
    falls within this subscription's quiet-hours window.

    The window is per-subscription so a user can mute their phone overnight
    but keep desktop alerts active. Stored as 24h strings (``"22:00"``,
    ``"08:00"``). Overnight ranges (start > end) are handled by treating
    "after start OR before end" as in-window.

    Added 2026-05-21 alongside extending the flashcards schedule to
    24h — without this, the every-hour cron would ping users at 3 AM
    regardless of their pref. Quiet hours had been in the schema but
    never enforced anywhere in the delivery path.
    """
    from datetime import datetime as _dt
    if not prefs.get("quiet_hours_enabled"):
        return False
    start = prefs.get("quiet_hours_start", "22:00")
    end = prefs.get("quiet_hours_end", "08:00")
    try:
        sh, sm = [int(x) for x in str(start).split(":")[:2]]
        eh, em = [int(x) for x in str(end).split(":")[:2]]
    except Exception:
        # Malformed pref — fail-open (deliver the notification) rather
        # than silently drop it. Logging would be noisy in this hot path.
        return False
    n = now if now is not None else _dt.now()
    cur = n.hour * 60 + n.minute
    s = sh * 60 + sm
    e = eh * 60 + em
    if s == e:
        return False              # zero-length window — pref-makes-no-sense, ignore
    if s < e:
        return s <= cur < e       # same-day window (e.g. 12:00 → 14:00)
    return cur >= s or cur < e    # overnight window (e.g. 22:00 → 08:00)


def list_subscriptions(filter_kind: Optional[str] = None,
                       user_email: Optional[str] = None,
                       *,
                       honor_quiet_hours: bool = True) -> list[dict]:
    """List active subscriptions, optionally filtered by alert kind and user.

    Excludes ``kind=mac`` rows — those are pure-prefs records for the native
    macOS app and have no real Web Push endpoint, so passing them to
    pywebpush would crash. Mac delivery is handled separately via SSE in
    push.mac_stream.

    Auto-backfills missing pref keys + user_email onto every subscription so
    future schema additions don't silently drop notifications for existing
    devices.

    Quiet hours: when ``honor_quiet_hours=True`` (default), drops any
    subscription whose user has quiet_hours_enabled AND the current
    server-local time falls within their window. Caller can pass False
    for critical alerts that should bypass quiet hours (none today —
    but kept as a hatch for future "trade stopped out" style pings).
    """
    # Hard kill-switch for retired alert kinds — no device receives them,
    # whatever its stored prefs say. See DISABLED_ALERT_KINDS.
    if filter_kind and filter_kind in DISABLED_ALERT_KINDS:
        return []
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
    rows = list(db.push_subscriptions.find(q))
    if honor_quiet_hours:
        from datetime import datetime as _dt
        now = _dt.now()   # server local TZ (America/New_York set in compose)
        rows = [r for r in rows if not _is_in_quiet_hours(r.get("prefs") or {}, now)]
    return rows


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
    # Hard kill-switch for retired alert kinds (mirror of list_subscriptions).
    if filter_kind and filter_kind in DISABLED_ALERT_KINDS:
        return set()
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
        "leaderboard_breakout": True, # consolidated: a name ON the rank leaderboard
                                      # breaks out today (fired by
                                      # sepa.leaderboard_breakout_watch cron, 2026-06-03)
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
        # macbook_deal removed 2026-05-15 along with the lifeboard module.
        # Existing user docs may still have the key on them — pymongo
        # tolerates unknown keys in default_prefs intersection, so leaving
        # them be is harmless. If we ever want to clean up, run a one-shot
        # $unset migration over `notification_devices.prefs`.
        "product_launch": True,       # new hardware/software launches detected by
                                      # catalysts.product_launches (Gemma-classified)
        # ── Real-estate listing notifications (HOUSE_OWNER_EMAIL only;
        # non-owners would never receive these because house pushes are
        # scoped via send_to_user(owner_email, ...) in
        # backend/house/daily_scrape.py). Default ON so the owner gets
        # the morning summary out of the box; they can mute any of the
        # three from /notifications.
        "house_daily":          True, # daily 8am summary: views, saves, tours, offers
        "house_scrape_failed":  True, # ⚠ scraper couldn't pull any numbers today
        "house_stagnant":       True, # 📉 N+ days with no view movement — consider price drop
        "user_signin": True,          # admin-only: ping when a NEW user signs in
                                      # for the first time (fires once per email)
        # ── Minervini flash cards — 3 bite-sized lessons/day (9 ET morning,
        # 12:30 ET midday, 16:00 ET close). Education, not signals.
        # Broadcast (everyone gets the same card). User toggles off here
        # if they find the cadence noisy. See backend/flashcards/.
        "minervini_flashcards": True,
        # ── Market open / close reminders — pings 15 min before each bell
        # (9:15 ET + 3:45 ET Mon-Fri, skips US holidays). Broadcast.
        # Mute via this toggle if the user finds it noisy. See
        # backend/market_hours/reminder.py.
        "market_hours_reminder": True,
        # ── Volleyball fitness module — three daily kinds, separate
        # toggles so non-VB users can mute each independently. See
        # backend/volleyball/reminders.py.
        "vb_workout":     True,    # 7 AM morning workout brief
        "vb_supplement":  True,    # 9 PM magnesium reminder
        "vb_education":   True,    # 6 PM daily volleyball/health card
        # ── Pivot / entry alerts (sepa.pivot_alerts cron). BUG FIX 2026-06-09:
        # this kind was never added here, and list_subscriptions(filter_kind=k)
        # only matches devices whose prefs.<k>==True — so pivot pushes were
        # silently targeting ZERO devices (the in-app feed still showed them via
        # push_history). The _backfill merge stamps it onto existing devices.
        "pivot_alert": True,
        # ── SEPA-cross tape watch (scalping.sepa_watch cron) — 5-min candle
        # reads at pivot/VWAP/levels on holdings + buyable + at-pivot +
        # leaderboard names. One alert per (symbol, state, day), self-graded.
        "scalp_tape": True,
        "quiet_hours_enabled": False,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    }
