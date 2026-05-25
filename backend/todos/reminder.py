"""Reminder cron — fires push notifications for due todos every minute,
plus a 7am daily digest summarizing important + today's todos."""
from __future__ import annotations

import logging
from todos import store

log = logging.getLogger("todos.reminder")


def fire_due() -> dict:
    """Find todos whose notify_at has passed and fire push for each.

    Per-user — uses each todo's stored user_email to scope the push so
    Aj's reminders go to Aj's devices, not the friend's.

    **Bug history (2026-05-17):** the previous version called
    ``notify.send_alert`` without ``user_email``, which fell through
    to ``sender.send_to_all`` and broadcast every todo reminder to
    every subscribed device on the system. Vineetha's vitamin push at
    9pm was hitting Ajay's phone too. The fix is the explicit
    ``user_email=t.get("user_email")`` below — ``send_alert`` now
    forwards that to ``sender.send_to_user`` which filters
    ``push_subscriptions`` by the email field.
    """
    due = store.find_due_reminders(limit=50)
    if not due:
        return {"checked": 0, "fired": 0}

    from sepa import notify
    fired = 0
    skipped_no_owner = 0
    for t in due:
        owner = (t.get("user_email") or "").strip().lower()
        if not owner:
            # Cross-user safety: a todo without an owner means we can't
            # scope the push, and broadcasting a private reminder to
            # every device is the failure mode we fixed earlier today.
            # Mark notified so we don't keep retrying this same row,
            # but log it loudly so the orphan can be investigated.
            log.error("todos.reminder: SKIP todo %s — missing user_email; "
                      "marking notified to avoid retry storm", t.get("_id"))
            try:
                store.mark_notified(t["_id"])
            except Exception:
                pass
            skipped_no_owner += 1
            continue

        text = t.get("text") or "Reminder"
        ticker = t.get("ticker")
        url = f"/sepa/{ticker}" if ticker else "/todos"
        title = f"📌 {ticker} · {text[:60]}" if ticker else f"📌 {text[:80]}"
        body = "Reminder from your todo list"
        ok = notify.send_alert(
            title=title, body=body, url=url, kind="todo_reminder",
            ticker=ticker,
            user_email=owner,
        )
        if ok:
            store.mark_notified(t["_id"])
            fired += 1
    log.info("todos.reminder: checked=%d fired=%d skipped_no_owner=%d",
             len(due), fired, skipped_no_owner)
    return {"checked": len(due), "fired": fired, "skipped_no_owner": skipped_no_owner}


def fire_daily_digest() -> dict:
    """Once-a-day push at 7 AM ET — fans out per registered user.

    Pulls each user's important + today's items via store.list_for_brief()
    and sends them their own personal digest. Tap routes to /todos.
    """
    from sepa import notify
    db = store._get_db()
    if db is None:
        return {"sent": 0}
    user_emails = db.todos.distinct("user_email") or []
    if not user_emails:
        # Fall back to default user (legacy single-user mode)
        import os
        user_emails = [os.getenv("DEFAULT_USER_EMAIL", "ajay@example.com")]

    sent_total = 0
    for ue in user_emails:
        slice_ = store.list_for_brief(user_email=ue)
        important = slice_.get("important") or []
        today = slice_.get("today") or []
        upcoming = slice_.get("upcoming_count") or 0
        total = len(important) + len(today)
        if total == 0 and upcoming == 0:
            continue  # don't ping users with nothing to do

        # ... reuse the body-building logic below in a closure
        result = _send_one_digest(ue, important, today, upcoming)
        if result:
            sent_total += 1

    log.info("todos.daily_digest: per-user fan-out sent=%d", sent_total)
    return {"sent": sent_total, "users": len(user_emails)}


def _send_one_digest(user_email: str, important: list, today: list,
                     upcoming: int) -> bool:
    """Build + send the digest payload for one user."""
    from sepa import notify
    total = len(important) + len(today)
    if total == 0 and upcoming == 0:
        log.info("todos.daily_digest: nothing to surface, skipping")
        return False

    # Build a scannable preview body — show up to 3 items, prioritizing
    # important > today.
    preview_items: list[str] = []
    for t in important[:3]:
        preview_items.append(f"⭐ {t['text']}")
    remaining = 3 - len(preview_items)
    if remaining > 0:
        for t in today[:remaining]:
            preview_items.append(t["text"])
    body = " · ".join(preview_items)
    if total > 3:
        body += f" · +{total - 3} more"
    if upcoming and total <= 3:
        body += f" · {upcoming} upcoming"

    title_parts = []
    if len(important) > 0:
        title_parts.append(f"⭐ {len(important)}")
    if len(today) > 0:
        title_parts.append(f"📅 {len(today)} today")
    title = "📋 Daily todos · " + " · ".join(title_parts) if title_parts \
        else "📋 Daily todos"

    # Send only to push subscriptions registered to this specific user
    from push import sender, subs as psubs
    pdb = psubs._get_db()
    if pdb is None:
        return False
    targets = list(pdb.push_subscriptions.find({
        "user_email": user_email,
        "prefs.todo_daily_digest": True,
    }))
    sent = 0
    payload = {
        "title": title, "body": body, "tag": "todo_daily_digest",
        "url": "/todos", "kind": "todo_daily_digest",
    }
    for t in targets:
        if sender._send_one(t, payload):
            sent += 1
    log.info("todos.daily_digest: user=%s sent=%d important=%d today=%d upcoming=%d",
             user_email, sent, len(important), len(today), upcoming)
    return sent > 0
