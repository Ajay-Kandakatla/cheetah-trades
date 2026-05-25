"""Cron-fired push notifications for the volleyball module.

Schedule (server local TZ = America/New_York, all weekdays + weekend):

  07:00 ET  morning_brief    — today's workout + D3/K2 + Moringa reminder
  18:00 ET  daily_education  — one volleyball/health card
  21:30 ET  magnesium        — 30-60 min before bed reminder

Quiet-hours pref (per-user) still gates delivery — same plumbing as
flashcards. Match-day Saturdays might want a different timing for the
morning brief; for now we send the same 7am ping every day. The body
adapts by reading the day's session type.

Push kinds (each separately toggleable on /notifications):
  - vb_workout        morning brief + workout-related pings
  - vb_supplement     supplement reminders
  - vb_education      daily education card
"""
from __future__ import annotations

import logging

log = logging.getLogger("volleyball.reminders")


def fire_morning_brief() -> dict:
    """07:00 ET. Today's workout focus + AM supplement reminder."""
    from . import plan
    today = plan.get_today_plan()
    session = today["session"]
    name = session["name"]
    focus = session["focus"]
    body = (
        f"Today: {focus}\n\n"
        f"Duration: ~{session['duration_min']} min\n"
        f"💊 D3/K2 + Moringa with breakfast"
    )
    payload = {
        "title": f"🏐 {name}",
        "body":  body[:300],
        "tag":   f"vb-morning-{today['date_et']}",
        "url":   "/volleyball?from=alert",
        "kind":  "vb_workout",
    }
    try:
        from push import sender
        result = sender.send_to_all(payload, kind="vb_workout")
        log.info("vb morning brief fired sent=%d failed=%d",
                 result.get("sent", 0), result.get("failed", 0))
        return {"ok": True, **result}
    except Exception as exc:
        log.warning("vb morning brief failed: %s", exc)
        return {"ok": False, "reason": str(exc)}


def fire_magnesium() -> dict:
    """21:30 ET. Pre-sleep magnesium glycinate ping."""
    payload = {
        "title": "💊 Magnesium Glycinate · before bed",
        "body":  ("200-400 mg with water, 30-60 min before lights-out. "
                  "Crosses BBB; muscle relaxation + GABA-pathway sleep depth. "
                  "Sleep is your recovery."),
        "tag":   "vb-magnesium",  # daily slot; replaces previous evening's ping
        "url":   "/volleyball?from=alert&topic=supplements",
        "kind":  "vb_supplement",
    }
    try:
        from push import sender
        result = sender.send_to_all(payload, kind="vb_supplement")
        log.info("vb magnesium fired sent=%d failed=%d",
                 result.get("sent", 0), result.get("failed", 0))
        return {"ok": True, **result}
    except Exception as exc:
        log.warning("vb magnesium failed: %s", exc)
        return {"ok": False, "reason": str(exc)}


def fire_education_card() -> dict:
    """18:00 ET. One volleyball/health education card per day."""
    from . import education
    card = education.pick_today()
    body = card["body"]
    if card.get("source"):
        body = f"{body}\n— {card['source']}"
    payload = {
        "title": card["title"],
        "body":  body[:300],
        "tag":   f"vb-edu-{card.get('topic', 'general')}",
        "url":   f"/volleyball?from=alert&topic={card.get('topic', 'shoulder')}",
        "kind":  "vb_education",
    }
    try:
        from push import sender
        result = sender.send_to_all(payload, kind="vb_education")
        log.info("vb education fired sent=%d failed=%d topic=%s",
                 result.get("sent", 0), result.get("failed", 0),
                 card.get("topic"))
        return {"ok": True, **result}
    except Exception as exc:
        log.warning("vb education failed: %s", exc)
        return {"ok": False, "reason": str(exc)}


if __name__ == "__main__":
    # CLI for cron + manual testing:
    #   python -m volleyball.reminders morning
    #   python -m volleyball.reminders magnesium
    #   python -m volleyball.reminders education
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "morning"
    if cmd == "morning":
        print(fire_morning_brief())
    elif cmd == "magnesium":
        print(fire_magnesium())
    elif cmd == "education":
        print(fire_education_card())
    else:
        print(f"unknown: {cmd}")
        sys.exit(2)
