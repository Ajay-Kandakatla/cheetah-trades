"""Market open / close reminder pushes.

Two pings per weekday:
  - 09:15 ET — "Market opens in 15 min" (regular session opens 09:30)
  - 15:45 ET — "Market closes in 15 min" (regular session closes 16:00)

Holiday-aware: full-closure days (NYSE holiday calendar) are skipped.
Early-close days (e.g. day before Thanksgiving) still get the open
ping but NOT the close ping — we'd need a per-day early-close lookup
which isn't worth the complexity yet. The user will get the open
reminder, glance at /sepa, and notice the early close themselves.

See reminder.py for the dispatcher; cron entries live in
backend/crontab. Push kind: ``market_hours_reminder`` — separately
toggleable on /notifications.
"""
from .reminder import fire_open_reminder, fire_close_reminder, is_market_day

__all__ = ["fire_open_reminder", "fire_close_reminder", "is_market_day"]
