"""Daily-recurring todo seeder.

Runs once a day at 6am ET (via cron) and materializes the day's
recurring reminders for users who've subscribed to them. Each entry
turns into a regular row in the `todos` collection with `notify_at`
set to today's HH:MM in US/Eastern — the existing
``todos.reminder.fire_due`` minute-cron then pushes the actual
notification at the scheduled time.

This module just decides WHAT gets created each day. The push delivery
machinery is unchanged.

Idempotency
-----------
Re-running mid-day is safe. We skip any entry that already has a row
in `todos` with the same `user_email` + `text` created since today's
midnight. So:
    docker compose exec cron python -m todos.daily_recurring
can be invoked manually to backfill a fresh deploy without spamming.

Recipients today
----------------
Only Vineetha. Ajay handles his own todos through the regular UI.
If more household members ever need recurring reminders, append to
``RECURRING`` below — no schema change needed.
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # python <3.9 fallback — should never trigger in our container
    ZoneInfo = None  # type: ignore

from todos import store

log = logging.getLogger("todos.daily_recurring")

VINEETHA = "gandurivineetha@gmail.com"


# Recurring schedule. Each tuple: (user_email, hour, minute, text, important)
# Hour/minute are in US/Eastern. Keep entries grouped by recipient for
# easy editing; the comments explain the WHY of each block so future-me
# (or another contributor) doesn't accidentally yank them.
RECURRING: list[tuple[str, int, int, str, bool]] = [
    # ─── Vineetha · daily love note from Ajay ───────────────────────────
    # First push of the morning — lands when she checks her phone after
    # waking up. Marked `important` so it pins to the top of her list
    # alongside any time-sensitive items.
    (VINEETHA, 8, 30,  "💕 From Ajay: He loves you so much and thinks you are sexy", True),

    # ─── Vineetha · hydration through the day ───────────────────────────
    # Four pings spaced through her waking hours. Not so many that they
    # become noise; enough to actually move the needle on water intake.
    # She can dismiss/complete each as it fires.
    (VINEETHA, 10, 0,  "💧 Drink a glass of water", False),
    (VINEETHA, 13, 0,  "💧 Time for water — afternoon", False),
    (VINEETHA, 16, 0,  "💧 Hydrate again", False),
    (VINEETHA, 19, 0,  "💧 Last water reminder of the day", False),

    # ─── Vineetha · nightly vitamins ────────────────────────────────────
    (VINEETHA, 21, 0,  "💊 Take your vitamins", True),
]


def _et_now() -> datetime:
    if ZoneInfo is None:
        return datetime.now()
    return datetime.now(ZoneInfo("America/New_York"))


def _today_midnight_epoch() -> int:
    """Epoch seconds for 00:00 in US/Eastern today.
    Used as the "since" cutoff for the idempotency check."""
    now = _et_now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp())


def _epoch_today(hour: int, minute: int) -> int:
    """Epoch seconds for HH:MM in US/Eastern today."""
    target = _et_now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    return int(target.timestamp())


def _exists_today(user_email: str, text: str) -> bool:
    """Has this exact (user_email, text) todo been created already today?

    Note: we don't filter by `status` — even a completed copy counts as
    "exists" so re-running the cron doesn't pile up a 5th water reminder
    if she's already drunk water and ticked off four. The next day's
    fresh materialization gives her a clean slate."""
    db = store._get_db()  # underscore is internal, but we're in the same package
    if db is None:
        return False
    return db.todos.find_one({
        "user_email": user_email.lower(),
        "text":       text[:300],  # match store.add_todo's truncation
        "created_at": {"$gte": _today_midnight_epoch()},
    }) is not None


def _iter_all_entries() -> list[tuple[str, int, int, str, bool]]:
    """Yield (user_email, hour, minute, text, important) for every entry
    that should fire TODAY. Combines two sources:

      1. The hardcoded RECURRING list above — legacy seed for
         Vineetha's health pings. Fires every day (no day-of-week
         filter).
      2. User-managed rules from the ``recurring_todos`` Mongo
         collection — fires only on weekdays matching the rule's
         ``days_of_week`` field. Built by the /todos page UI.
    """
    today_weekday = _et_now().weekday()           # 0=Monday … 6=Sunday
    entries: list[tuple[str, int, int, str, bool]] = []

    # 1. Legacy hardcoded rules — daily, no weekday filter.
    for user_email, hour, minute, text, important in RECURRING:
        entries.append((user_email, hour, minute, text, important))

    # 2. User-managed rules from Mongo — filtered to today's weekday.
    try:
        from todos import recurring_store
        for r in recurring_store.rules_for_weekday(today_weekday):
            entries.append((
                r["user_email"],
                int(r.get("hour") or 9),
                int(r.get("minute") or 0),
                r.get("text") or "",
                bool(r.get("important")),
            ))
    except Exception as exc:
        log.warning("recurring: failed to load Mongo rules: %s", exc)

    return entries


def materialize_for_today(*, dry_run: bool = False) -> dict:
    """Create todos for every recurring entry whose time is still in
    the future today. Idempotent.

    Returns a summary dict for logging / cron output.
    """
    now_ts = int(time.time())
    inserted: list[str] = []
    skipped_exists: list[str] = []
    skipped_past:   list[str] = []
    failed:         list[str] = []

    for user_email, hour, minute, text, important in _iter_all_entries():
        notify_at = _epoch_today(hour, minute)

        # Don't backfire entries that are already past — would create
        # noise (e.g. running at noon would instantly fire 10am water).
        # Vitamins at 9pm being skipped at 11pm is fine; tomorrow's run
        # will pick them up.
        if notify_at <= now_ts:
            skipped_past.append(f"{user_email}: {text}")
            continue

        if _exists_today(user_email, text):
            skipped_exists.append(f"{user_email}: {text}")
            continue

        if dry_run:
            inserted.append(f"[dry] {user_email}: {text} @ {notify_at}")
            continue

        result = store.add_todo(
            text=text,
            user_email=user_email,
            notify_at=notify_at,
            important=important,
        )
        if result.get("ok"):
            inserted.append(f"{user_email}: {text} @ {notify_at}")
            log.info("recurring: created '%s' for %s, notify_at=%s",
                     text, user_email, notify_at)
        else:
            failed.append(f"{user_email}: {text} ({result.get('reason')})")
            log.warning("recurring: failed for %s: %s", user_email, result)

    summary = {
        "inserted":       len(inserted),
        "skipped_exists": len(skipped_exists),
        "skipped_past":   len(skipped_past),
        "failed":         len(failed),
        "details": {
            "inserted":       inserted,
            "skipped_exists": skipped_exists,
            "skipped_past":   skipped_past,
            "failed":         failed,
        },
    }
    return summary


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    dry_run = "--dry-run" in (argv or sys.argv[1:])
    summary = materialize_for_today(dry_run=dry_run)
    # One-line stdout summary so the cron log is grep-able.
    print(
        f"daily_recurring: inserted={summary['inserted']} "
        f"skipped_exists={summary['skipped_exists']} "
        f"skipped_past={summary['skipped_past']} "
        f"failed={summary['failed']}"
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
