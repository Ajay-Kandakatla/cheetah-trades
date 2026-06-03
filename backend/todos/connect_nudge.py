"""Gentle weekly 'connect' nudge — ONE intimacy suggestion at a time.

Replaces the old aggressive setup (2026-06-03: "too much noise", 30 todos dumped
at once, reminders firing twice a day). This posts a SINGLE rotating suggestion
per week to each owner as a tappable todo — the suggestion's resource link opens
on tap. Deliberately low-frequency and one-at-a-time.

Curated from the earlier vetted research. Direct links only where the handle /
subreddit is known; otherwise a Google-search link so nothing is ever dead.

Run weekly from cron (Sun 10:00 ET):  python -m todos.connect_nudge
"""
from __future__ import annotations

import datetime
import logging
import time

from . import store as ts

log = logging.getLogger("todos.connect_nudge")

OWNERS = ["ajaykandakatla@gmail.com", "gandurivineetha@gmail.com"]

# One gentle idea at a time. `url` is an optional tappable resource.
SUGGESTIONS: list[dict] = [
    {"text": "💞 This week: a 15-min screen-free check-in — eye contact and one thing you each appreciate.", "url": None},
    {"text": "💞 Plan one date out of the house this week (book the sitter if you need one).", "url": None},
    {"text": "💞 Talk about your 'accelerators & brakes' — what turns desire on, and off, for each of you.", "url": None},
    {"text": "💞 Follow a couples-intimacy therapist for ideas — Vanessa Marin.", "url": "https://www.instagram.com/vanessamarintherapy"},
    {"text": "💞 Relationship tools from the Gottman Institute.", "url": "https://www.instagram.com/gottmaninstitute"},
    {"text": "💞 Read or listen together: 'Sex Talks' by Vanessa & Xander Marin.", "url": "https://www.google.com/search?q=Sex+Talks+book+Vanessa+Xander+Marin"},
    {"text": "💞 Take the Erotic Blueprint quiz separately, then compare notes.", "url": "https://www.google.com/search?q=Erotic+Blueprint+quiz"},
    {"text": "💞 Outercourse night — kissing, touching, a sensual massage, zero pressure to go further.", "url": None},
    {"text": "💞 Send one playful, flirty text in the middle of a day this week.", "url": None},
    {"text": "💞 Pillow talk after closeness — stay a few minutes, say what you loved.", "url": None},
    {"text": "💞 Protect ~6 hours of just-us time this week, phones away.", "url": None},
    {"text": "💞 Browse a couples community for ideas and others' experiences.", "url": "https://www.reddit.com/r/sexover30"},
]


def pick_for_week(week: int) -> dict:
    """Pure: the suggestion for a given (ISO) week — rotates through the list."""
    return SUGGESTIONS[week % len(SUGGESTIONS)]


def _already_posted_recently(email: str) -> bool:
    """Idempotency: skip if a connect nudge was added in the last 6 days
    (so a cron double-fire doesn't double-post)."""
    cutoff = int(time.time()) - 6 * 86400
    try:
        todos = ts.list_todos(user_email=email)
    except Exception:
        return False
    return any(t.get("source") == "connect" and (t.get("created_at") or 0) >= cutoff
               for t in todos)


def run() -> None:
    week = datetime.date.today().isocalendar()[1]      # 1..53 — deterministic rotation
    pick = pick_for_week(week)
    for em in OWNERS:
        if _already_posted_recently(em):
            log.info("connect_nudge: already posted this week for %s — skip", em)
            continue
        res = ts.add_todo(pick["text"], user_email=em, url=pick.get("url"),
                          workspace="personal", source="connect", important=False)
        log.info("connect_nudge: posted to %s ok=%s", em, res.get("ok"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
