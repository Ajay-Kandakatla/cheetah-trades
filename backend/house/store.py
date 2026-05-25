"""Mongo persistence for the house dashboard.

Two collections:
  - house_config:    one doc per owner, holds address + listing URLs + price
  - house_snapshots: one row per (owner, captured_at_iso_date) with metrics
                     scraped or manually entered that day
  - house_comps:     comparable sales the owner adds manually or that we
                     pull from public county records
  - house_events:    open-house schedules, showings, offers — a manual log
                     the owner adds events to from the dashboard
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("house.store")

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
        _db.house_config.create_index([("owner_email", ASCENDING)], unique=True)
        _db.house_snapshots.create_index(
            [("owner_email", ASCENDING), ("date_et", ASCENDING)], unique=True,
        )
        _db.house_snapshots.create_index([("captured_at", DESCENDING)])
        _db.house_comps.create_index([("owner_email", ASCENDING), ("address", ASCENDING)])
        _db.house_events.create_index([("owner_email", ASCENDING), ("ts", DESCENDING)])
        return _db
    except Exception as exc:
        log.warning("house.store: mongo unavailable: %s", exc)
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _today_et() -> str:
    """ISO date string in America/New_York. Matches scan/cron timezone."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


# ---------------------------------------------------------------------------
# Config — address + listing URLs + asking price
# ---------------------------------------------------------------------------
def get_config(owner_email: str) -> Optional[dict]:
    db = _get_db()
    if db is None:
        return None
    doc = db.house_config.find_one({"owner_email": owner_email.lower()})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


def upsert_config(owner_email: str, payload: dict) -> dict:
    """Upsert the owner's house config.

    Expected payload shape (every field optional except address):
      {
        "address":             "1234 Maple Ln, McKinney, TX 75070",
        "city":                "McKinney",
        "state":               "TX",
        "zip":                 "75070",
        "list_price":          550000,
        "listed_on":           "2026-04-22",   # ISO date (start of DOM)
        "redfin_url":          "https://www.redfin.com/TX/McKinney/...",
        "zillow_url":          "https://www.zillow.com/homedetails/...",
        "realtor_url":         "https://www.realtor.com/realestateandhomes-detail/...",
        "mls_id":              "20123456",
        "agent_name":           "Agent name",
        "agent_phone":          "555-...",
        "beds": 4, "baths": 3, "sqft": 2400, "lot_sqft": 7200, "year_built": 2014,
        "zestimate":           560000,        # zillow estimate (manual entry, optional)
        "redfin_estimate":     545000,
        "notes":               "...",
      }
    """
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    payload = {**payload, "owner_email": owner_email.lower(), "updated_at": _now()}
    db.house_config.update_one(
        {"owner_email": owner_email.lower()},
        {"$set": payload, "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Daily snapshot — one per (owner, date_et). Captures the day's metrics.
# ---------------------------------------------------------------------------
def upsert_snapshot(owner_email: str, metrics: dict, date_et: Optional[str] = None) -> dict:
    """Save (or merge into) today's snapshot.

    Metrics shape — every field optional, all nullable:
      {
        "redfin_views":   1234,
        "redfin_saves":     27,
        "redfin_tours":      3,
        "zillow_views":   2200,
        "zillow_saves":     41,
        "realtor_saves":     8,
        "current_list_price": 549000,   # any price drop today
        "open_houses_scheduled": 1,
        "showings_today":        2,
        "offers_received":       0,
        "source":  "manual" | "scraper" | "merged",
      }

    Multiple writes the same day MERGE — so the daily cron + manual edits
    can both touch a snapshot without overwriting.
    """
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    date_et = date_et or _today_et()
    db.house_snapshots.update_one(
        {"owner_email": owner_email.lower(), "date_et": date_et},
        {
            "$set": {**metrics, "captured_at": _now()},
            "$setOnInsert": {
                "owner_email": owner_email.lower(),
                "date_et": date_et,
                "created_at": _now(),
            },
        },
        upsert=True,
    )
    return {"ok": True, "date_et": date_et}


def list_snapshots(owner_email: str, days: int = 30) -> list[dict]:
    """Return last N daily snapshots, oldest → newest."""
    db = _get_db()
    if db is None:
        return []
    cur = db.house_snapshots.find(
        {"owner_email": owner_email.lower()},
        sort=[("date_et", 1)],
    ).limit(max(1, days))
    rows = []
    for r in cur:
        r["_id"] = str(r["_id"])
        rows.append(r)
    return rows


def latest_snapshot(owner_email: str) -> Optional[dict]:
    db = _get_db()
    if db is None:
        return None
    r = db.house_snapshots.find_one(
        {"owner_email": owner_email.lower()},
        sort=[("date_et", -1)],
    )
    if r:
        r["_id"] = str(r["_id"])
    return r


# ---------------------------------------------------------------------------
# Comps — comparable solds, manual entry first, scraper later
# ---------------------------------------------------------------------------
def list_comps(owner_email: str) -> list[dict]:
    db = _get_db()
    if db is None:
        return []
    rows = list(db.house_comps.find(
        {"owner_email": owner_email.lower()},
        sort=[("sold_date", -1)],
    ))
    for r in rows:
        r["_id"] = str(r["_id"])
    return rows


def add_comp(owner_email: str, comp: dict) -> dict:
    """Add or update a comp. Comp shape:
      {
        "address": "...",
        "sold_price": 545000,
        "sold_date":  "2026-03-15",
        "beds": 4, "baths": 3, "sqft": 2400,
        "ppsf": 227,                        # auto-computed if omitted
        "distance_mi": 0.4,
        "notes": "...",
      }
    """
    db = _get_db()
    if db is None:
        return {"ok": False}
    if comp.get("ppsf") is None and comp.get("sold_price") and comp.get("sqft"):
        try:
            comp["ppsf"] = round(float(comp["sold_price"]) / float(comp["sqft"]))
        except Exception:
            pass
    db.house_comps.update_one(
        {"owner_email": owner_email.lower(), "address": comp.get("address")},
        {"$set": {**comp, "updated_at": _now()},
         "$setOnInsert": {"owner_email": owner_email.lower(), "created_at": _now()}},
        upsert=True,
    )
    return {"ok": True}


def remove_comp(owner_email: str, address: str) -> dict:
    db = _get_db()
    if db is None:
        return {"ok": False}
    db.house_comps.delete_one({"owner_email": owner_email.lower(), "address": address})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Events — open houses, showings, offers, price drops. Manual log.
# ---------------------------------------------------------------------------
def list_events(owner_email: str, limit: int = 50) -> list[dict]:
    db = _get_db()
    if db is None:
        return []
    rows = list(db.house_events.find(
        {"owner_email": owner_email.lower()},
        sort=[("ts", -1)],
    ).limit(limit))
    for r in rows:
        r["_id"] = str(r["_id"])
    return rows


def add_event(owner_email: str, event: dict) -> dict:
    """Event shape:
      {
        "kind":   "open_house" | "showing" | "offer" | "price_drop" | "feedback" | "note",
        "label":  "Sat 1-3pm open house",
        "value":  null,                      # offer price, new list price, etc.
        "ts":     1715200000,                # epoch — defaults to now
        "notes":  "...",
      }
    """
    db = _get_db()
    if db is None:
        return {"ok": False}
    payload = {
        "kind":  event.get("kind", "note"),
        "label": event.get("label", ""),
        "value": event.get("value"),
        "notes": event.get("notes", ""),
        "ts":    event.get("ts") or _now(),
        "owner_email": owner_email.lower(),
        "created_at": _now(),
    }
    res = db.house_events.insert_one(payload)
    return {"ok": True, "id": str(res.inserted_id)}


def remove_event(owner_email: str, event_id: str) -> dict:
    db = _get_db()
    if db is None:
        return {"ok": False}
    from bson import ObjectId
    try:
        db.house_events.delete_one(
            {"_id": ObjectId(event_id), "owner_email": owner_email.lower()},
        )
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)}
