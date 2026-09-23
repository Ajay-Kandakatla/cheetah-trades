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
# ``price_alert`` LEFT this set 2026-09-21 — Ajay, asked "Price alerts are
# retired in the push switch and off in your Notifications, so even a real
# crossing will not reach your phone. Turn them back on?": "Yes to all..".
# It now sits in the owner keep-set at the bottom of this file.
_RETIRED_2026_06_13: frozenset[str] = frozenset({
    "sepa_new_candidate", "volume_breakout", "rising_momentum",
    "watchlist_breakout", "juggernaut_watchlist", "stage_breakdown",
    "watchlist_stage_breakdown", "morning_brief", "product_launch",
    "scalp_tape",
})

# Ajay 2026-09-20: "Remove volleyball and learning of stocks I do dont wanna
# see them they are spamming too much". Crons deleted, toggles gone,
# PERSONAL_KINDS entry gone, stored prefs flipped False by
# scripts/owner_prefs_apply.py. Labels stay in frontend/src/lib/alertKinds.ts
# so the 1,712 flashcard + 215 volleyball rows still in push_history (90-day
# TTL) render a name.
# `minervini_flashcards` KEEPS its seat here even though `backend/flashcards/`
# was DELETED later the same day ("Delete Flashcards please"): nothing can fire
# the kind any more, but ~1,712 rows carrying it are still in push_history and
# push.recent's serve-time filter keys on THIS set to hide them.
RETIRED_2026_09_20: frozenset = frozenset({
    "minervini_flashcards", "vb_workout", "vb_supplement", "vb_education",
})

DISABLED_ALERT_KINDS: frozenset[str] = _RETIRED_2026_06_13 | RETIRED_2026_09_20

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
        "prefs": prefs or prefs_for(user_email),
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

    Added 2026-05-21 alongside extending the (since-deleted) flashcards
    schedule to
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
                "prefs": prefs or prefs_for(user_email),
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


# ── The owner's keep-set (Ajay 2026-09-08) ──────────────────────────────────
# "Also kill the tape burst and pankaj and also few others miscellaneous
# notifications... I need just supply demand and also Sell signals and buy
# signals accurately."
#
# A NEW device registration used to get default_prefs() — every kind ON — which
# is exactly how his second phone ended up carrying 335 promo movers, 183 pivot
# alerts and 105 flash cards in a week. For the OWNER only, a registering device
# starts with these five and nothing else; everyone else keeps default_prefs().
# Muting a kind is a data write; this is the floor a re-subscribe falls back to.
# REPLACED 2026-09-09. Ajay: "Can you give me hot pull back alerts and chart
# pattern Alerts and also Sameday deman alerts please... Kill all other.. I just
# wanna these alerts.. Default turn these on from tomorrow." Asked whether the
# stop alerts on stocks he OWNS counted as "other", he chose to keep them and
# drop the todo reminders.
#
# WHAT LEFT: zone_bounce_alert, supply_break_alert, todo_reminder.
#
# SAID OUT LOUD, BECAUSE THE CODE SHOULD NOT PRETEND OTHERWISE: the three
# scanning kinds he chose are the three this app has measured at or below a coin
# flip — hot pullback 51.8% (interval includes zero), chart patterns 49.3%
# against a 50% placebo, same-day demand arrivals 52%. He was shown those
# numbers and asked for them anyway, as a watchlist. Each push carries its own
# record so the screen never implies more than the measurement supports.
#
# WIDENED 2026-09-20. Ajay: "Default on for any change of todays features
# Bondes or Potus or explosive growth or Earnings I wanna see all of them."
# → 🏛️ potus_investment (his #1 Yes), 🚀 growth_demand_alert (already
# delivering: 6 pushes / 18 device deliveries since 2026-09-11 — listed here so
# a re-registration cannot mute it), 📣 earnings_reaction
# (chart_maps/earnings_alerts.py), ✨ board_arrival (sepa/board_arrival.py).
# The four 2026-09-09 kinds stay. "Never loosen a GATE" still stands: this
# widens which KINDS reach him, not what any kind requires to fire.
#
# WIDENED 2026-09-21. Ajay, asked whether to turn price alerts back on now that
# they fire once per crossing (the latch, 37cd469): "Yes to all..".
# `price_alert` was PAUSED 2026-06-13 (`_RETIRED_2026_06_13`) and his stored
# prefs carry it False; both chokepoints open here — this set for the code,
# scripts/owner_prefs_apply.py for the data. "Never loosen a GATE" still
# stands: this widens which KINDS reach him, not what any kind requires to
# fire — the latch, ALERT_COOLDOWN_SEC and _threshold are untouched.
OWNER_KEEP_SET: frozenset = frozenset({
    "hot_pullback_alert",  # 🔥 the flush-and-turn board
    "pattern_alert",       # 📐 named bullish reversal patterns
    "demand_alert",        # 🧲 SAME-DAY arrivals at a tested demand band only
    "position_alert",      # 🔴 stop / supply reached on stocks he actually owns
    "potus_investment",    # 🏛️ federal stake reported (2026-09-20, his #1 Yes)
    "growth_demand_alert", # 🚀 explosive-growth board name at demand
    "earnings_reaction",   # 📣 earnings beat + institutional buying
    "board_arrival",       # ✨ a new name on 📈 Bonde / 🚀 Explosive Growth
    "price_alert",         # 🔔 a line HE drew on a ticker page (2026-09-21, "Yes to all..")
})


def owner_prefs() -> dict:
    """default_prefs() with everything OFF except OWNER_KEEP_SET."""
    return {k: (v if not isinstance(v, bool) else k in OWNER_KEEP_SET)
            for k, v in default_prefs().items()}


def _owner_email() -> str:
    import os
    return (os.getenv("OWNER_EMAIL")
            or os.getenv("DEFAULT_USER_EMAIL", "ajay@example.com")).lower()


def prefs_for(user_email: Optional[str]) -> dict:
    """Starting prefs for a NEWLY registered device."""
    return (owner_prefs() if (user_email or "").lower() == _owner_email()
            else default_prefs())


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
        "price_alert": True,          # user-set price alerts (paused 2026-06-13, back 2026-09-21)
        "position_alert": True,       # stop / target hit on Lifeboard positions
        # Promo-circuit mover (catalysts/promo_live.py): a roster-tagged
        # name moves >= 8% vs the prior close, pre/regular/after hours.
        # Ajay 2026-09-02: "just give me alerts from the topstock alerts
        # only.. I need the pre market alerts as well. After hours alerts."
        "promo_alert": True,
        # Demand-zone approach (supply_demand/demand_alerts.py): a $1B+ name
        # from the demand board is inside / within 1% of a tested demand band
        # (one push per band per day) or 1-3% above and falling (one digest
        # per 5-min pass). Ajay 2026-09-03: "big companies ... coming close
        # to Demand zones."
        "demand_alert": True,
        # 🔥 Hot Pullback (supply_demand/hot_pullback_alerts.py): a name that was
        # HOT, took one hard flush into a tested demand band and turned the same
        # day. Ajay 2026-09-09: "Can you give me hot pull back alerts and chart
        # pattern Alerts and also Sameday deman alerts please... Kill all other."
        # HONEST: this board measures 51.8% win over 83 trades with a 95%
        # interval of -0.19R to +0.41R that INCLUDES ZERO. He asked for it as a
        # watchlist ping, not as an edge, and the push says so.
        # MUST be here — a kind missing from default_prefs silently drops for
        # every device (total_targets = 0).
        "hot_pullback_alert": True,
        # 📐 Chart pattern (patterns/pattern_alerts.py): a named bullish reversal
        # pattern confirms on the daily frame. Same ask, same day.
        # HONEST: his own ledger has cup_with_handle at 45% up, double_bottom
        # 43%, triple_bottom 37% against a 50% placebo over 669 resolved
        # observations — NOT ONE beats chance. Every push carries the pattern's
        # own record beside the placebo so the number is never hidden.
        "pattern_alert": True,
        # Zone bounce (supply_demand/zone_bounce_alerts.py): a $1B+ name
        # touched a demand level — or a BROKEN supply shelf now acting as
        # support — intraday and is already bouncing off it (above the band,
        # >= max(3%, 1 ATR) off the low, arrivals only). Ajay 2026-09-03:
        # "NTAP did hit the demand zone in the morning and bounced back
        # immediately 20 point I am looking for those." Digest-first (one per
        # 5-min pass; only STRONG bounces, max 3, get their own push) so it
        # stays tolerable; mutable at /notifications. MUST be here — a kind
        # missing from default_prefs silently drops for every device.
        "zone_bounce_alert": True,
        # Breaking resistance → new highs (supply_demand/zone_edge.py, every
        # minute in RTH): a $1B+ name within 1% UNDER the ceiling of its LAST
        # supply band — nothing overhead, or the band sits at the 52-week
        # high — or that broke it TODAY (at most 3% through); band tested 2+
        # times; once per (symbol, band, day, tier); 3 singles per pass, the
        # rest one digest. Ajay 2026-09-03: "stocks that are <1% away from
        # breaking supply zones which are going for new highs". (The
        # near-demand side of the same module reuses demand_alert above.)
        # MUST be here — a kind missing from default_prefs silently drops
        # for every device.
        "supply_break_alert": True,
        # 🚀 Explosive Growth at demand (growth/alerts.py, Ajay 2026-09-11: "I
        # wanna know when ever these are in demand, separately just trackers").
        # Its own kind on purpose: the board it comes from has NO cap floor,
        # so these pushes cover names the other zone kinds skip entirely, and
        # he must be able to silence one without silencing the other. The push
        # still carries the standing room + proximity gates and the measured
        # `intact` gate. MUST be here — a kind missing from default_prefs
        # silently drops for every device.
        "growth_demand_alert": True,
        # 🏛️ Federal stake reported (political/watch.py, Ajay 2026-09-20:
        # "Anytime POTUS does new investments show me those").
        #
        # FLIPPED ON 2026-09-20, same day, on his follow-up: "Default on for
        # any change of todays features Bondes or Potus or explosive growth or
        # Earnings I wanna see all of them" — and "Yes for #1", the his-call
        # item that asked exactly this. It is in OWNER_KEEP_SET too, so a
        # re-registered device cannot quietly mute it again.
        #
        # STILL A HEURISTIC, and the push says so: a regex over headlines with
        # no measured record. The gate is unchanged and stays the tightest
        # class — an equity stake + a NAMED agency + a STATED size + a
        # resolved ticker in one headline. Turning the kind on does not loosen
        # what it takes to fire.
        "potus_investment": True,
        # 📣 Earnings beat with institutional buying (chart_maps/earnings_alerts.py,
        # Ajay 2026-09-20: "Also don't forget to alert me on earnings surprises
        # I think stock witz also has it. I wanna make sure we are catching
        # those in alerts as well.").
        # Fires on the REACTED half of the Earnings Flow tab: a beat whose
        # reaction bar carries institutional-sized volume.
        # A MARKET kind (market_hours.gate) — it reads a closed reaction bar.
        # NOT MEASURED: no forward study stands behind it; the push says so.
        "earnings_reaction": True,
        # ✨ New name on 📈 Bonde / 🚀 Explosive Growth (sepa/board_arrival.py,
        # Ajay 2026-09-20: "Default on for any change of todays features
        # Bondes or Potus or explosive growth or Earnings I wanna see all of
        # them.").
        # Fires once per (board, symbol) when a name ARRIVES on a board.
        # A MARKET kind — both boards are built from closed bars.
        # NOT MEASURED as an entry: Bonde's rule measured INVERTED (−3.11pp)
        # and the 100/100 growth screen has never been measured forward.
        "board_arrival": True,
        # 💎 A balance sheet IMPROVED on a fresh quarter (growth/quality_alerts.py,
        # Ajay 2026-09-22: "Filter and have alerts and new look out for such
        # companies where whcih have very high quality.").
        #
        # SHIPS OFF — the only kind in this dict that does. It is deliberate and
        # it was CHECKED rather than assumed: OWNER_KEEP_SET below is an explicit
        # nine-kind list and this is not on it, so `owner_prefs()` returns False
        # for his devices either way. His 2026-09-20 "default on for any change
        # of todays features" named the features that existed THAT DAY; a kind he
        # has not seen yet does not inherit that sentence. He turns it on at
        # /notifications, where the toggle says what it does.
        #
        # It MUST still be here: a kind missing from default_prefs silently
        # targets ZERO devices (the 2026-06-24 chokepoint) AND renders no toggle,
        # so he could never turn it on at all.
        #
        # Fires on a DEFINITIONAL component of growth/capital_quality.py crossing
        # FAIL -> PASS on a NEW fiscal quarter — net cash, FCF positive, dilution
        # stopped, return on capital positive. Never on "is high quality" (a
        # state), never on unknown -> pass (the app learning, not the company
        # improving), never twice for one quarter. A MARKET kind.
        # NOT MEASURED: capital_quality.MEASURED is False and the body says so.
        "capital_quality_upgrade": False,
        "morning_brief": True,        # 8:30am post-fast-scan summary
        "todo_reminder": True,        # personal todo list reminders (specific times)
        # Institutional 13F flow changed quarter-over-quarter on a name Ajay
        # holds or watches (Ajay 2026-08-16: "give me updated and notification
        # as Accumulations change as money moving I need a comparison"). This
        # is a 4th kind on a deliberately-small keep-set; it stays tolerable
        # because 13F rolls quarterly and the scope is holdings + watchlist —
        # a handful per quarter, batched into ONE consolidated push.
        "accumulation_change": True,
        # ── Trade Flash — a >= $250k, >=75% one-sided 10s burst printing IN or
        # NEAR a zone on the demand/supply boards (orderflow/trade_flash.py).
        # 5th phone kind, added on Ajay's explicit ask 2026-08-24 ("push
        # notification I can also get it on my phone"). Owner-scoped at the
        # SENDER (send_to_user) — this pref existing for everyone is harmless
        # because nobody else is ever targeted. MUST be in this dict: a kind
        # missing from default_prefs silently drops for every device (the
        # 2026-06-24 chokepoint), which would make the cron look healthy while
        # his phone stays dark.
        "trade_flash": True,
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
        # ── `minervini_flashcards` removed 2026-09-20 — see RETIRED_2026_09_20
        # at the top of this file ("they are spamming too much"). The module
        # behind it (`backend/flashcards/`) was deleted the same day.
        # ── Market open / close reminders — pings 15 min before each bell
        # (9:15 ET + 3:45 ET Mon-Fri, skips US holidays). Broadcast.
        # Mute via this toggle if the user finds it noisy. See
        # backend/market_hours/reminder.py.
        "market_hours_reminder": True,
        # ── `vb_workout` / `vb_supplement` / `vb_education` removed
        # 2026-09-20 — see RETIRED_2026_09_20 at the top of this file.
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
