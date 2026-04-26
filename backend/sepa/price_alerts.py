"""Per-stock on-demand price alerts.

Two collections:
  price_alerts          {_id, symbol, kind, level, created_price, created_at,
                         last_fired_at, channels[], note}
  price_alert_fires     {_id, alert_id, symbol, kind, level, price, fired_at,
                         channels[], message}

`kind` is one of:
  - "below"     → fire when last <= level
  - "above"     → fire when last >= level
  - "drop_pct"  → fire when last <= created_price * (1 - level/100)
  - "rise_pct"  → fire when last >= created_price * (1 + level/100)

The cron worker calls `check_alerts()` every 5 minutes during market hours.
A fire is rate-limited per alert by ALERT_COOLDOWN_SEC so we don't spam.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from . import notify, prices

log = logging.getLogger("sepa.price_alerts")

ALERT_COOLDOWN_SEC = 6 * 3600
KINDS = {"below", "above", "drop_pct", "rise_pct"}


def _db():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[os.getenv("MONGO_DB", "cheetah")]
    except Exception as exc:
        log.warning("price_alerts: Mongo unavailable: %s", exc)
        return None


def _strip_id(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if doc and "alert_id" in doc:
        doc["alert_id"] = str(doc["alert_id"])
    return doc


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def create(symbol: str, kind: str, level: float,
           channels: Optional[list[str]] = None,
           note: Optional[str] = None) -> Optional[dict]:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    db = _db()
    if db is None:
        return None
    last = prices.last_trade_price(symbol)
    doc = {
        "symbol": symbol.upper(),
        "kind": kind,
        "level": float(level),
        "created_price": float(last) if last else None,
        "created_at": int(time.time()),
        "last_fired_at": 0,
        "channels": channels or ["whatsapp", "browser"],
        "note": note,
    }
    res = db.price_alerts.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _strip_id(doc)


def list_active() -> list[dict]:
    db = _db()
    if db is None:
        return []
    return [_strip_id(d) for d in db.price_alerts.find().sort("created_at", -1)]


def delete(alert_id: str) -> bool:
    db = _db()
    if db is None:
        return False
    from bson import ObjectId
    try:
        oid = ObjectId(alert_id)
    except Exception:
        return False
    res = db.price_alerts.delete_one({"_id": oid})
    return res.deleted_count > 0


def recent_fires(since: int = 0, limit: int = 50) -> list[dict]:
    db = _db()
    if db is None:
        return []
    cur = db.price_alert_fires.find({"fired_at": {"$gt": int(since)}}).sort("fired_at", -1).limit(limit)
    return [_strip_id(d) for d in cur]


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------
def _hit(alert: dict, last: float) -> bool:
    kind = alert["kind"]
    level = alert["level"]
    created = alert.get("created_price") or last
    if kind == "below":      return last <= level
    if kind == "above":      return last >= level
    if kind == "drop_pct":   return last <= created * (1 - level / 100)
    if kind == "rise_pct":   return last >= created * (1 + level / 100)
    return False


def _format(alert: dict, last: float) -> str:
    sym = alert["symbol"]
    kind = alert["kind"]
    level = alert["level"]
    created = alert.get("created_price")
    if kind == "below":
        head = f"{sym} ↓ hit {last} (alert ≤ {level})"
    elif kind == "above":
        head = f"{sym} ↑ hit {last} (alert ≥ {level})"
    elif kind == "drop_pct":
        pct = (last / created - 1) * 100 if created else 0
        head = f"{sym} dropped {pct:+.1f}% to {last} (from {created})"
    else:
        pct = (last / created - 1) * 100 if created else 0
        head = f"{sym} up {pct:+.1f}% to {last} (from {created})"
    note = alert.get("note")
    return head + (f"\nNote: {note}" if note else "")


def check_alerts() -> dict:
    """Evaluate every active alert against the live last-trade price.
    Fires once per cooldown window per alert. Returns counts."""
    db = _db()
    if db is None:
        return {"fired": 0, "checked": 0}

    fired: list[dict] = []
    checked = 0
    now = int(time.time())

    # Group alerts by symbol so we only fetch each price once.
    alerts = list(db.price_alerts.find())
    by_sym: dict[str, list[dict]] = {}
    for a in alerts:
        by_sym.setdefault(a["symbol"], []).append(a)

    for sym, group in by_sym.items():
        last = prices.last_trade_price(sym)
        if last is None:
            continue
        for a in group:
            checked += 1
            if not _hit(a, last):
                continue
            if now - int(a.get("last_fired_at") or 0) < ALERT_COOLDOWN_SEC:
                continue
            msg = _format(a, last)
            channels = a.get("channels") or []
            sent_via: list[str] = []
            if "whatsapp" in channels:
                if notify.send_whatsapp(msg):
                    sent_via.append("whatsapp")
            # "browser" is a passive channel — we record the fire and the UI
            # picks it up on its next /sepa/alerts/recent poll.
            if "browser" in channels:
                sent_via.append("browser")

            db.price_alerts.update_one({"_id": a["_id"]},
                                       {"$set": {"last_fired_at": now}})
            fire_doc = {
                "alert_id": a["_id"],
                "symbol": sym,
                "kind": a["kind"],
                "level": a["level"],
                "price": float(last),
                "fired_at": now,
                "channels": sent_via,
                "message": msg,
            }
            db.price_alert_fires.insert_one(fire_doc)
            fired.append(_strip_id(fire_doc))

    log.info("price alerts: checked=%d fired=%d", checked, len(fired))
    return {"checked": checked, "fired": len(fired), "details": fired}
