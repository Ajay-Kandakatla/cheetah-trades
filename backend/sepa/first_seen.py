"""When a symbol FIRST appeared on a board — the ✨ NEW badge, generically.

Ajay 2026-09-13, asking for the Bonde tab: *"I wanna see explicitly new ones
getting added in this tab"*. That is the same question the Explosive Growth
board already answers, and the answer has one subtle part worth getting right
exactly once.

THE SUBTLE PART, and why `__meta__` exists
──────────────────────────────────────────
A latest-only board doc (`_id: "latest"`) cannot tell a name that arrived today
from one that has sat there for months. So arrivals get their own collection,
one doc per symbol with a `first_seen` stamp.

But on the FIRST build every name has a first_seen of now, so a naive read
badges the entire board as new — and "we have only just started looking" must
never render as "these are fresh finds". A `__meta__` row records when tracking
itself began, written with the SAME timestamp as that first cohort, and
`newly_found` uses a STRICT `>` against it. The first board therefore reports
zero arrivals, which is the honest answer.

One stamp for the meta row and every symbol, deliberately: two clock reads would
leave microseconds of drift and let the strict `>` badge the whole first board.

RELATIONSHIP TO `growth/tracker.py`
───────────────────────────────────
That module has its own copy of this logic, written first (2026-09-12) and in
production on the Explosive Growth board. It is NOT refactored to call this one:
that board is live, tested, and there is no user-facing gain from moving it.
`tests/test_first_seen.py` asserts the two behave IDENTICALLY on the same
inputs, so the duplication cannot silently drift.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

log = logging.getLogger("sepa.first_seen")

META_ID = "__meta__"


def _db(db=None):
    if db is not None:
        return db
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL") or "mongodb://mongo:27017"
        name = os.getenv("MONGO_DB") or "cheetah"
        return MongoClient(url, serverSelectionTimeoutMS=3000)[name]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("first_seen: mongo unavailable: %s", exc)
        return None


def record(collection: str, symbols, db=None) -> int:
    """Stamp `first_seen` for any symbol not seen before; refresh `last_seen`.

    Returns how many symbols were written. Never raises: a board must still
    render when the arrival ledger is unavailable — it simply badges nothing.
    """
    d = _db(db)
    if d is None:
        return 0
    syms = [str(s).upper() for s in (symbols or []) if s]
    if not syms:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    try:
        coll = d[collection]
        coll.update_one({"_id": META_ID},
                        {"$setOnInsert": {"tracking_since": now}}, upsert=True)
        for sym in syms:
            coll.update_one({"_id": sym},
                            {"$set": {"last_seen": now},
                             "$setOnInsert": {"first_seen": now}}, upsert=True)
        return len(syms)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("first_seen: write to %s failed: %s", collection, exc)
        return 0


def newly_found(collection: str, days: int = 30, db=None) -> set:
    """Symbols that ARRIVED within `days`. Empty until an arrival is observed.

    A name present at the very first build is NOT new — it is merely the first
    thing we ever saw, which is a different statement.
    """
    d = _db(db)
    if d is None:
        return set()
    try:
        coll = d[collection]
        meta = coll.find_one({"_id": META_ID}) or {}
        since = meta.get("tracking_since")
        if not since:
            return set()
        cut = (datetime.now(timezone.utc) - timedelta(days=int(days))).isoformat()
        # The LATER of the two floors: inside the window AND strictly after
        # tracking began, so the first cohort can never qualify.
        floor = max(str(since), cut)
        return {str(x["_id"]).upper()
                for x in coll.find({"_id": {"$ne": META_ID},
                                    "first_seen": {"$gt": floor}}, {"_id": 1})}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("first_seen: read of %s failed: %s", collection, exc)
        return set()


def first_seen_map(collection: str, symbols, db=None) -> dict:
    """{SYM: first_seen ISO} for the given symbols — what the tooltip prints.

    A badge that says "new" without saying WHEN is a claim the reader cannot
    check, and this board's whole point is watching arrivals.
    """
    d = _db(db)
    syms = [str(s).upper() for s in (symbols or []) if s]
    if d is None or not syms:
        return {}
    try:
        return {str(x["_id"]).upper(): x.get("first_seen")
                for x in d[collection].find(
                    {"_id": {"$in": syms}}, {"_id": 1, "first_seen": 1})}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("first_seen: map read of %s failed: %s", collection, exc)
        return {}
