"""Mongo-backed user profile cache. Fetched once from Google, then served local."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests

log = logging.getLogger("users.store")

_db = None
GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"
PROFILE_TTL_SECONDS = 7 * 86400   # refresh from Google at most once a week


# ============================================================================
# Display-name overrides — server-side only.
#
# Why this exists: the frontend used to hardcode {"ajaykandakatla": "Ajay",
# "gandurivineetha": "Vineetha"} inside the JS bundle. Anyone who curl-ed
# the static asset could grep two personal Gmail addresses. The user
# (Ajay) flagged this on 2026-05-18 — "they are personal emails" — and
# asked to keep them out of the bundle.
#
# The fix: ship the override map as an env var that lives ONLY on the
# Mac book pro M5 (this machine) (in .env). Source code committed to git stays clean. The
# /auth/me + /admin/access/users endpoints resolve display_name on the
# server, so the frontend just renders whatever the API returned.
#
# Env format (JSON object, lowercased emails as keys):
#   DISPLAY_NAME_OVERRIDES_JSON='{"ajaykandakatla@gmail.com":"Ajay",
#                                 "gandurivineetha@gmail.com":"Vineetha"}'
#
# If unset or malformed, behavior degrades to title-cased email handle.
# Admin detection still works via HOUSE_OWNER_EMAILS — orthogonal.
# ============================================================================
_OVERRIDES_CACHE: Optional[dict] = None


def _display_name_overrides() -> dict:
    """Load + memoize override map from DISPLAY_NAME_OVERRIDES_JSON env var.

    Memoized at module level — env doesn't change between requests so we
    avoid the JSON parse on every /auth/me call. To pick up changes,
    restart the container (same as any other env var).
    """
    global _OVERRIDES_CACHE
    if _OVERRIDES_CACHE is not None:
        return _OVERRIDES_CACHE
    raw = (os.getenv("DISPLAY_NAME_OVERRIDES_JSON") or "").strip()
    if not raw:
        _OVERRIDES_CACHE = {}
        return _OVERRIDES_CACHE
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            log.warning("DISPLAY_NAME_OVERRIDES_JSON must be a JSON object — ignoring")
            _OVERRIDES_CACHE = {}
            return _OVERRIDES_CACHE
        # Normalize: lowercase email keys for case-insensitive lookup,
        # drop empty values so a half-configured entry doesn't override
        # a real Google profile name with "".
        _OVERRIDES_CACHE = {
            str(k).strip().lower(): str(v).strip()
            for k, v in parsed.items()
            if v and str(v).strip()
        }
        if _OVERRIDES_CACHE:
            log.info("display-name overrides loaded for %d emails", len(_OVERRIDES_CACHE))
        return _OVERRIDES_CACHE
    except (json.JSONDecodeError, TypeError) as exc:
        log.warning("DISPLAY_NAME_OVERRIDES_JSON parse failed (%s); using no overrides", exc)
        _OVERRIDES_CACHE = {}
        return _OVERRIDES_CACHE


def resolve_display_name(email: str, profile_display_name: Optional[str] = None) -> str:
    """Resolve a user's display name with this precedence:

      1. DISPLAY_NAME_OVERRIDES_JSON env-driven override (highest — wins
         even over a Google-fetched name, because the user may explicitly
         prefer a nickname like "Ajay" over their full Google name).
      2. ``profile_display_name`` — typically Google's userinfo.name. We
         treat it as "no real name set" if it equals what _derived() would
         have returned anyway — that means the cached Mongo doc was filled
         with the fallback handle (e.g. "Ajaykandakatla"), not an actual
         Google profile name, so the override map should still get a shot
         at fixing it.
      3. ``_derived(email)`` — title-cased local part as last resort.

    Called by the /auth/me endpoint for the current user AND by
    /admin/access/users when injecting display_name onto every row, so
    the frontend never needs to know about the override map.
    """
    overrides = _display_name_overrides()
    key = (email or "").strip().lower()
    if key in overrides:
        return overrides[key]
    pdn = (profile_display_name or "").strip()
    # Auto-heal: if the cached profile name is just _derived(email), it
    # means the Google fetch never populated a real name — treat as empty
    # so the email handle takes effect through the fallback path.
    if pdn and pdn != _derived(email):
        return pdn
    return _derived(email)


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient
        client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                              serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        _db.users.create_index("email", unique=True)
        return _db
    except Exception as exc:
        log.warning("users.store: Mongo unavailable: %s", exc)
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _fetch_from_google(access_token: str) -> Optional[dict]:
    """Call Google's userinfo endpoint with the OAuth access token.
    Returns dict with email, name, given_name, family_name, picture, sub."""
    if not access_token:
        return None
    try:
        r = requests.get(GOOGLE_USERINFO, headers={
            "Authorization": f"Bearer {access_token}",
        }, timeout=4)
        if r.status_code != 200:
            log.warning("google userinfo HTTP %s: %s", r.status_code, r.text[:200])
            return None
        return r.json()
    except Exception as exc:
        log.warning("google userinfo failed: %s", exc)
        return None


def get_or_fetch(email: str, access_token: Optional[str] = None) -> dict:
    """Return the user's cached profile, refreshing from Google if stale or absent.

    Always returns a dict — never None. Falls back to a derived display_name
    from the email handle when Google can't be reached.
    """
    db = _get_db()
    email = (email or "").strip().lower()
    if not email:
        return {"email": email, "display_name": "", "picture": None}

    cached = None
    if db is not None:
        cached = db.users.find_one({"email": email})

    fresh_needed = (
        cached is None
        or not cached.get("display_name")
        or (_now() - (cached.get("refreshed_at") or 0)) > PROFILE_TTL_SECONDS
    )

    if fresh_needed and access_token:
        info = _fetch_from_google(access_token)
        if info and info.get("email", "").lower() == email:
            doc = {
                "email": email,
                "display_name": info.get("name") or _derived(email),
                "given_name": info.get("given_name"),
                "family_name": info.get("family_name"),
                "picture": info.get("picture"),
                "google_sub": info.get("sub"),
                "refreshed_at": _now(),
            }
            if db is not None:
                db.users.update_one(
                    {"email": email}, {"$set": doc,
                                          "$setOnInsert": {"created_at": _now()}},
                    upsert=True,
                )
            return doc

    if cached:
        return {**cached, "_id": str(cached["_id"])}

    # No cache + no Google access token (or Google call failed) → derive
    derived = {
        "email": email,
        "display_name": _derived(email),
        "given_name": None, "family_name": None, "picture": None,
        "google_sub": None,
        "refreshed_at": None,
    }
    if db is not None:
        db.users.update_one(
            {"email": email},
            {"$set": derived, "$setOnInsert": {"created_at": _now()}},
            upsert=True,
        )
    return derived


def record_signin(email: str) -> dict:
    """Lightweight per-visit upsert — touches `last_seen_at` + counts
    sessions. Returns a status dict including `is_first_seen=True` exactly
    once per user. Callers use that to fire a one-time admin notification
    ("Karthik just signed in for the first time").

    Detection works by checking whether `notified_admin` was unset on the
    doc BEFORE this update — pymongo's `update_one` with `$setOnInsert`
    + a follow-up read covers both inserts and existing-but-never-notified
    users (e.g., users created before this feature shipped).
    """
    db = _get_db()
    email = (email or "").strip().lower()
    if not email or db is None:
        return {"is_first_seen": False, "email": email}

    now = _now()
    existing = db.users.find_one({"email": email}, {"notified_admin": 1, "created_at": 1})
    is_first_seen = not existing or not existing.get("notified_admin")

    # Touch last_seen + increment session counter on every call.
    update: dict = {
        "$set":  {"last_seen_at": now, "notified_admin": True},
        "$setOnInsert": {
            "email": email,
            "display_name": _derived(email),
            "created_at": now,
        },
        "$inc":  {"session_count": 1},
    }
    db.users.update_one({"email": email}, update, upsert=True)
    return {
        "is_first_seen":  is_first_seen,
        "email":          email,
        "created_at":     (existing or {}).get("created_at") or now,
    }


def list_all(limit: int = 200) -> list[dict]:
    """Used by the admin dashboard to list every user the app has seen."""
    db = _get_db()
    if db is None:
        return []
    rows = list(db.users.find({}, {
        "email": 1, "display_name": 1, "created_at": 1, "last_seen_at": 1,
        "session_count": 1, "notified_admin": 1,
    }).sort("last_seen_at", -1).limit(limit))
    for r in rows:
        r["_id"] = str(r["_id"])
    return rows


# ============================================================================
# Per-user alert thresholds.
#
# Stored on the same `users` doc to avoid an extra collection. Defaults
# apply when the user has never set a value. All thresholds are POSITIVE
# percentages — direction is encoded in the field name.
# ============================================================================
DEFAULT_ALERT_SETTINGS = {
    "intraday_emergency_pct":  12.0,   # Minervini structural break
    "intraday_warning_pct":     8.0,   # earlier warning before the emergency
    "stop_close_buffer_pct":    1.0,   # how close to stop before warning
}


def get_alert_settings(email: str) -> dict:
    """Read the user's alert thresholds. Fills in defaults for missing keys."""
    db = _get_db()
    email = (email or "").strip().lower()
    if not email or db is None:
        return dict(DEFAULT_ALERT_SETTINGS)
    doc = db.users.find_one({"email": email}, {"alert_settings": 1}) or {}
    merged = {**DEFAULT_ALERT_SETTINGS, **(doc.get("alert_settings") or {})}
    return merged


def set_alert_settings(email: str, updates: dict) -> dict:
    """Patch a user's alert thresholds. Only known keys + sane numeric
    ranges are accepted. Returns the merged final settings."""
    db = _get_db()
    email = (email or "").strip().lower()
    if not email or db is None:
        return dict(DEFAULT_ALERT_SETTINGS)

    current = get_alert_settings(email)
    safe: dict = {}
    for k, default in DEFAULT_ALERT_SETTINGS.items():
        if k not in updates:
            continue
        try:
            v = float(updates[k])
        except Exception:
            continue
        # All current settings are percentages in [0, 50] — clamp.
        v = max(0.0, min(50.0, v))
        safe[k] = round(v, 2)
    if not safe:
        return current
    merged = {**current, **safe}
    db.users.update_one(
        {"email": email},
        {"$set": {"alert_settings": merged}, "$setOnInsert": {"email": email, "created_at": _now()}},
        upsert=True,
    )
    return merged


def _derived(email: str) -> str:
    """Last-resort display name from the email handle.
    'ajaykandakatla@gmail.com' → 'Ajaykandakatla'
    'jane.doe@gmail.com'      → 'Jane Doe'
    """
    handle = email.split("@", 1)[0]
    if not handle:
        return email
    parts = [p for p in handle.replace(".", " ").replace("_", " ").replace("-", " ").split() if p]
    if not parts:
        return handle.capitalize()
    return " ".join(p.capitalize() for p in parts)
