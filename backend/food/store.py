"""Mongo persistence for the food planner.

Collections:
  - food_menus: one doc per (user_email, date_et, slot)
        slot ∈ {adult_breakfast, kid_breakfast, dinner}
        stores: list of recipe_ids cooked that day
  - food_preferences: per-user knobs (iron focus, telangana-bias, etc.)
  - food_pantry: bulk staples on-hand (rice, dal, etc.)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("food.store")

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
        _db.food_menus.create_index(
            [("user_email", ASCENDING), ("date_et", ASCENDING), ("slot", ASCENDING)],
            unique=True,
        )
        _db.food_menus.create_index([("date_et", DESCENDING)])
        _db.food_preferences.create_index([("user_email", ASCENDING)], unique=True)
        _db.food_pantry.create_index([("user_email", ASCENDING)], unique=True)
        return _db
    except Exception as exc:
        log.warning("food.store: mongo unavailable: %s", exc)
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _today_et() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


# ---------------------------------------------------------------------------
# Menu history
# ---------------------------------------------------------------------------
def log_cooked(user_email: str, slot: str, recipe_ids: list[str],
               date_et: Optional[str] = None) -> dict:
    """Record what was cooked for a slot. Overwrites if same (user, date,
    slot) already exists — supports edits."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    date_et = date_et or _today_et()
    db.food_menus.update_one(
        {"user_email": user_email.lower(), "date_et": date_et, "slot": slot},
        {
            "$set": {
                "recipe_ids": list(recipe_ids),
                "logged_at": _now(),
            },
            "$setOnInsert": {
                "user_email": user_email.lower(),
                "date_et": date_et,
                "slot": slot,
                "created_at": _now(),
            },
        },
        upsert=True,
    )
    return {"ok": True, "date_et": date_et, "slot": slot}


def history(user_email: str, days: int = 21) -> list[dict]:
    """Return last `days` of cooked entries (oldest → newest)."""
    db = _get_db()
    if db is None:
        return []
    rows = list(db.food_menus.find(
        {"user_email": user_email.lower()},
        sort=[("date_et", -1), ("slot", 1)],
    ).limit(days * 4))
    rows.reverse()
    for r in rows:
        r["_id"] = str(r["_id"])
    return rows


def recent_recipe_ids(user_email: str, days: int = 7) -> set[str]:
    """Return the set of recipe_ids cooked in the last `days` — used by
    the planner to avoid repeating within the cooldown window."""
    db = _get_db()
    if db is None:
        return set()
    from datetime import date, timedelta
    today = date.fromisoformat(_today_et())
    cutoff = (today - timedelta(days=days)).isoformat()
    out: set[str] = set()
    for r in db.food_menus.find(
        {"user_email": user_email.lower(), "date_et": {"$gte": cutoff}},
        {"recipe_ids": 1},
    ):
        out.update(r.get("recipe_ids") or [])
    return out


def days_since_last(user_email: str, recipe_id: str,
                    max_lookback: int = 30) -> Optional[int]:
    """How many days since this recipe was last cooked, or None if never
    in the lookback window."""
    db = _get_db()
    if db is None:
        return None
    from datetime import date, timedelta
    today = date.fromisoformat(_today_et())
    cutoff = (today - timedelta(days=max_lookback)).isoformat()
    last = db.food_menus.find_one(
        {
            "user_email": user_email.lower(),
            "date_et": {"$gte": cutoff},
            "recipe_ids": recipe_id,
        },
        sort=[("date_et", -1)],
    )
    if not last:
        return None
    return (today - date.fromisoformat(last["date_et"])).days


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------
def get_preferences(user_email: str) -> dict:
    db = _get_db()
    if db is None:
        return _default_preferences()
    p = db.food_preferences.find_one({"user_email": user_email.lower()})
    if not p:
        return _default_preferences()
    p.pop("_id", None)
    # Merge with defaults so newly-added keys are populated for old users
    return {**_default_preferences(), **p}


def set_preferences(user_email: str, prefs: dict) -> dict:
    db = _get_db()
    if db is None:
        return {"ok": False}
    db.food_preferences.update_one(
        {"user_email": user_email.lower()},
        {"$set": {**prefs, "updated_at": _now()}},
        upsert=True,
    )
    return {"ok": True}


def _default_preferences() -> dict:
    """Default preferences match the family brief Ajay gave verbatim."""
    return {
        "telangana_bias":   0.7,    # 0-1 — share of mains drawn from Telangana
        "andhra_bias":      0.2,    # less, but in rotation
        "iron_focus_days":  3,      # at least N iron-rich items per week (wife)
        "weekend_meat":     True,   # paya/biryani saved for weekend
        "shrimp_freq_days": 14,     # shrimp at most every N days
        "fish_freq_days":   7,      # fish at most every N days
        "every_meal_charu": True,   # always pair a charu with dinner
        "kid_probiotic_priority": True,
    }


# ---------------------------------------------------------------------------
# Pantry — bulk staples on hand. Used by the grocery planner to subtract
# what we already have from what we need to buy.
# ---------------------------------------------------------------------------
def get_pantry(user_email: str) -> dict:
    db = _get_db()
    if db is None:
        return _default_pantry()
    p = db.food_pantry.find_one({"user_email": user_email.lower()})
    if not p:
        return _default_pantry()
    p.pop("_id", None)
    return {**_default_pantry(), **p}


def set_pantry(user_email: str, pantry: dict) -> dict:
    db = _get_db()
    if db is None:
        return {"ok": False}
    db.food_pantry.update_one(
        {"user_email": user_email.lower()},
        {"$set": {**pantry, "updated_at": _now()}},
        upsert=True,
    )
    return {"ok": True}


def _default_pantry() -> dict:
    """Defaults reflect Ajay's brief: rice in bulk every 2 months, weekly
    veg/meat/batter. The grocery roller subtracts these from the planned
    week's needs."""
    return {
        "rice_kg":         20,    # bulk every 2 months
        "toor_dal_kg":     2,
        "moong_dal_kg":    1,
        "tamarind":        True,
        "spices_stocked":  True,
        "jaggery":         True,
        "ghee":            True,
    }
