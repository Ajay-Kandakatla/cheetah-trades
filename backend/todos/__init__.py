"""Personal todo list with optional push reminders.

Each todo can have:
  - text       (required)
  - due_at     (optional epoch — for filtering/sorting)
  - notify_at  (optional epoch — when the reminder cron fires push)
  - ticker     (optional — links the todo to a ticker; reminder routes to /sepa/{ticker})
  - status     ("active" | "completed")

The reminder cron runs every minute and fires push for items whose
``notify_at`` has passed and ``notified_at`` is null.

Module layout
-------------
store.py     Mongo CRUD
reminder.py  Cron-driven reminder dispatcher
"""
from todos import store, reminder  # noqa: F401
