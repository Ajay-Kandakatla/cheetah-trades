"""One-shot repair for price_cache corruption left by the pre-2026-05-27
patch_latest_closes bug (future-dated bars + frozen pre-market partials).

PREREQUISITE: deploy the prices.py fix FIRST. Otherwise the next call to
patch_latest_closes() will recreate the future-dated rows.

What this script does (in order):
  1. Removes every bar from every symbol whose `date` is later than today
     (US/Eastern) — these were the UTC-rollover ghosts.
  2. Resets `cached_at = 0` on every symbol so the 20-hour TTL miss path
     triggers on next read, forcing _mongo_put() to overwrite the entire
     bars array with a fresh _fetch() — which cleans up any remaining
     partial-volume bars in one stroke.

Both operations are idempotent and reversible (the bars array is *shrunk*,
not destroyed; the next scan refetches the full 2-year history).

Run from the api container AFTER `docker compose build api && up -d`:

    docker compose exec api python -m sepa.repair_cache_corruption

Or pipe via stdin if the module isn't baked in yet:

    cat backend/sepa/repair_cache_corruption.py | docker compose exec -T api python -

Expect ~3-5 minutes of Massive API bursts on the next scan as 2,000+
symbols re-fetch their 2-year histories. Run off-hours.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime


def _et_today_midnight() -> datetime:
    """Midnight in US/Eastern, returned as a NAIVE datetime so it matches
    how `bar_date` is stored in price_cache (.normalize().tz_localize(None))."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        now = datetime.now()
    return datetime(now.year, now.month, now.day)


def main() -> int:
    try:
        from pymongo import MongoClient
    except ImportError:
        print("pymongo not installed in this environment", file=sys.stderr)
        return 2

    url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB", "cheetah")
    try:
        client = MongoClient(url, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
    except Exception as exc:
        print(f"Mongo connection failed: {exc}", file=sys.stderr)
        return 2

    coll = client[db_name].price_cache
    today_midnight = _et_today_midnight()

    print(f"ET today (midnight): {today_midnight.isoformat()}")
    print()

    # ── Step 1: remove future-dated bars ──────────────────────────────
    # $pull every bar from the array whose `date` is strictly after midnight
    # ET today. Pre-fix bug stamped bars with UTC midnight, which rolls to
    # tomorrow's calendar date any time after 8 PM ET.
    print("Step 1: pulling future-dated bars …")
    r1 = coll.update_many(
        {},
        {"$pull": {"bars": {"date": {"$gt": today_midnight}}}},
    )
    print(f"  matched={r1.matched_count}, modified={r1.modified_count}")

    # ── Step 2: expire every cached_at so next read triggers _fetch ──
    # _mongo_put() does an update_one with $set: {bars: ...}, which REPLACES
    # the entire bars array. So the next read of each symbol (TTL miss →
    # full _fetch → _mongo_put) cleans up any partial-volume bars too,
    # without us having to surgically identify and remove each one.
    print()
    print("Step 2: expiring cached_at on all rows …")
    r2 = coll.update_many({}, {"$set": {"cached_at": 0}})
    print(f"  matched={r2.matched_count}, modified={r2.modified_count}")

    print()
    print("Repair complete. Next scan will re-fetch full 2-year history for")
    print("every symbol via _fetch() → _mongo_put(). This takes ~3-5 min on")
    print("Russell 1000 and bursts the Massive API. Run a scan now:")
    print("  curl -X POST http://localhost:8000/sepa/scan")
    print("…or wait for the next cron-triggered scan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
