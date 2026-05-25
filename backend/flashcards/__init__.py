"""Minervini flash-card push notifications.

Bite-sized lessons that fire as push notifications throughout the
trading day — entry rules in the morning, risk reminders at midday,
mindset/mistakes at close. Pairs with the in-app MinerviniLesson card
on the SEPA + MorningBrief pages (deep version of the same topics).

Schedule (backend/crontab):
  - 09:00 ET (pre-market):  MORNING — entry / setup / regime
  - 12:30 ET (midday):      MIDDAY  — risk / sizing / stops / sell rules
  - 16:00 ET (close):       CLOSE   — mindset / mistakes / stage analysis

User can mute via the ``minervini_flashcards`` pref on /notifications.
Default ON for new subscriptions — these are core to Ajay's stated
learning goal ("act as flash cards throughout the day").

NOTE: this module is intentionally separate from ``learning/`` (which
hosts the signal-calibration loop) because the two solve unrelated
problems and share zero code paths. Keeping them apart avoids
confusing the calibration code with notification dispatch.
"""
from .flashcards import fire_flashcard, ALL_CARDS, pick_for_slot
from .api import router

__all__ = ["fire_flashcard", "ALL_CARDS", "pick_for_slot", "router"]
