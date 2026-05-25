"""Mongo store for PEG / ORB / Inside-Day setups.

Single collection ``setups`` with a discriminator field ``kind``. One
schema covers all three because the structural fields are identical:

    {
      _id,
      kind: "peg" | "orb" | "inside_day",
      symbol: "NVDA",
      generated_at: epoch_seconds,
      date_et:    "2026-05-19",       # the scan date
      trigger:    149.40,             # buy at/above this
      stop:       144.10,             # protective stop
      target:     153.00,             # first take-profit
      risk_pct:   3.55,               # (trigger-stop)/trigger * 100
      reward_pct: 2.41,               # (target-trigger)/trigger * 100
      rr:         0.68,               # reward / risk
      meta:       {...},              # setup-specific (e.g. gap_pct, vol_mult)
      status:     "pending" | "triggered" | "expired" | "stopped",
      triggered_at: epoch | null,
      expires_at:   epoch,            # when to mark this stale
    }

Indexes:
  - (symbol, kind, generated_at desc) — fast "latest for this ticker"
  - (kind, date_et, generated_at desc) — fast "tab view"
  - (expires_at) — for the sweeper that flips stale ones to expired

Why one collection, not three:
  - The API surface is uniform: /setups?kind=peg, ?kind=orb, ?kind=inside_day
  - The frontend renders them with the same row component
  - Cron sweeps run a single $set on `expires_at < now` instead of three
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("setups.store")

_COLL_NAME = "setups"
_db = None
_disabled = False


def _coll():
    """Return the setups collection, or None if Mongo is unavailable.

    Mirrors the lazy-init pattern in sepa/history.py — survives missing
    Mongo (returns None so callers degrade gracefully) but creates the
    indexes on first successful connection.
    """
    global _db, _disabled
    if _disabled:
        return None
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING, DESCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        coll = client[db_name][_COLL_NAME]
        coll.create_index(
            [("symbol", ASCENDING), ("kind", ASCENDING), ("generated_at", DESCENDING)]
        )
        coll.create_index(
            [("kind", ASCENDING), ("date_et", ASCENDING), ("generated_at", DESCENDING)]
        )
        coll.create_index([("expires_at", ASCENDING)])
        coll.create_index([("status", ASCENDING)])
        _db = coll
        log.info("setups store: connected to %s/%s.%s", url, db_name, _COLL_NAME)
        return _db
    except Exception as exc:
        log.warning("setups store: Mongo unavailable (%s); operating in no-op mode", exc)
        _disabled = True
        return None


def _eastern_date(epoch: int) -> str:
    """Return YYYY-MM-DD in US Eastern. Hardcoded -05:00 (good enough for
    file-naming; DST drift doesn't matter for the date key)."""
    et = datetime.fromtimestamp(epoch, tz=timezone(timedelta(hours=-5)))
    return et.strftime("%Y-%m-%d")


def make_setup(
    *,
    kind: str,
    symbol: str,
    trigger: float,
    stop: float,
    target: float,
    expires_in_hours: int,
    meta: Optional[dict] = None,
) -> dict:
    """Build a uniform setup dict ready for insertion.

    `expires_in_hours` defines the validity window. After this, the
    sweeper flips status to ``expired`` even if the trigger never hit.
    Defaults differ by kind (caller decides):
      - PEG:        72h (3 trading days — gap can be ripe for a few days)
      - ORB:         7h (same session only — useless overnight)
      - Inside-Day: 48h (one extra day grace if no fill day-1)
    """
    now = int(time.time())
    risk = max(trigger - stop, 0.01)
    reward = max(target - trigger, 0.01)
    return {
        "kind": kind,
        "symbol": symbol.upper(),
        "generated_at": now,
        "date_et": _eastern_date(now),
        "trigger": round(float(trigger), 4),
        "stop": round(float(stop), 4),
        "target": round(float(target), 4),
        "risk_pct": round(risk / trigger * 100, 2),
        "reward_pct": round(reward / trigger * 100, 2),
        "rr": round(reward / risk, 2),
        "meta": meta or {},
        "status": "pending",
        "triggered_at": None,
        "expires_at": now + expires_in_hours * 3600,
    }


def upsert_setups(kind: str, setups: list[dict]) -> int:
    """Replace today's setups for this kind in one shot.

    Strategy: delete today's pending rows for this kind, insert the new
    batch. Triggered/stopped rows from today are kept (they reflect real
    intraday state we don't want to lose). Older rows untouched — they
    age out via the expires_at sweep.
    """
    coll = _coll()
    if coll is None:
        return 0
    if not setups:
        return 0
    try:
        today = _eastern_date(int(time.time()))
        coll.delete_many({
            "kind": kind,
            "date_et": today,
            "status": "pending",
        })
        coll.insert_many(setups, ordered=False)
        return len(setups)
    except Exception as exc:
        log.warning("upsert_setups(%s) failed: %s", kind, exc)
        return 0


def get_setups(
    kind: Optional[str] = None,
    *,
    limit: int = 50,
    only_pending: bool = False,
) -> list[dict]:
    """Read setups for the API. Defaults to the most recent 50 across
    all kinds; pass ``kind`` to scope to one tab and ``only_pending``
    to filter out triggered/expired."""
    coll = _coll()
    if coll is None:
        return []
    q: dict = {}
    if kind:
        q["kind"] = kind
    if only_pending:
        q["status"] = "pending"
    try:
        cur = coll.find(q).sort("generated_at", -1).limit(limit)
        rows = []
        for d in cur:
            d["_id"] = str(d["_id"])
            rows.append(d)
        return rows
    except Exception as exc:
        log.warning("get_setups failed: %s", exc)
        return []


def mark_triggered(setup_id: str, triggered_price: float) -> bool:
    """Flip a setup from pending → triggered. Idempotent on already-triggered
    rows (returns True without re-update). Called by the ORB price watcher."""
    coll = _coll()
    if coll is None:
        return False
    try:
        from bson import ObjectId
        res = coll.update_one(
            {"_id": ObjectId(setup_id), "status": "pending"},
            {"$set": {
                "status": "triggered",
                "triggered_at": int(time.time()),
                "triggered_price": round(float(triggered_price), 4),
            }},
        )
        return res.modified_count > 0
    except Exception as exc:
        log.warning("mark_triggered(%s) failed: %s", setup_id, exc)
        return False


def expire_stale() -> int:
    """Flip pending → expired for any setup past its expires_at.

    Called from cron post-close. Cheap (single $set on an indexed field)
    so safe to run hourly if we want, but daily is enough."""
    coll = _coll()
    if coll is None:
        return 0
    try:
        now = int(time.time())
        res = coll.update_many(
            {"status": "pending", "expires_at": {"$lt": now}},
            {"$set": {"status": "expired"}},
        )
        return res.modified_count
    except Exception as exc:
        log.warning("expire_stale failed: %s", exc)
        return 0


__all__ = [
    "make_setup",
    "upsert_setups",
    "get_setups",
    "mark_triggered",
    "expire_stale",
]
