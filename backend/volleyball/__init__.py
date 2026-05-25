"""Volleyball — personal fitness module tuned to Ajay's profile.

What this module owns
---------------------
  * 7-day workout plan rotating power / pull / skills / strength /
    push / match / recovery — modified for his right-shoulder rehab
    (band work, no overhead pressing today) and right index finger
    plantar-plate issue (taping protocols, no full-extension wrist
    pushups).
  * Education card bank — ~30 cards on shoulder durability, finger
    plantar plate science, jump training (Verkhoshansky), supplement
    rationale (Magnesium Glycinate, Moringa, D3/K2 synergy), recovery,
    technique.
  * Daily push reminders:
      - 07:00 ET morning workout brief + D3/K2 + Moringa supplement ping
      - 21:30 ET Magnesium Glycinate before-bed ping
      - 18:00 ET one volleyball-education card per day
  * API endpoints powering /volleyball page:
      - /vb/today              today's workout + supplements + rehab
      - /vb/weekly             full 7-day rotation
      - /vb/education          card bank
      - /vb/education/{topic}  one topic's cards

What this module does NOT do
----------------------------
  * It's not medical advice. The exercises are sourced from common
    NSCA / USA Volleyball / sports-PT references. Personal injury
    decisions remain Ajay's call — coordinate with his PT.
  * It's not workout tracking — no set/rep logging. v2 if useful.

See plan.py for the workout data, education.py for the card bank,
reminders.py for the cron-fired pushes.
"""
from .api import router

__all__ = ["router"]
