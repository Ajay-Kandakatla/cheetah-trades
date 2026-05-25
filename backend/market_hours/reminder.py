"""Open + close reminder push dispatcher.

Each function is a single entry point the cron calls — see
backend/crontab. Both early-out cleanly on US market holidays so the
user doesn't get pinged on Memorial Day or Thanksgiving.

Why a tiny hardcoded holiday list instead of pandas-market-calendars?
The app already ships pandas via yfinance dependencies, but pulling in
pandas-market-calendars adds another transitive surface for marginal
gain. The NYSE adds/changes maybe one holiday per year — a 30-second
yearly maintenance task is cheaper than the dependency.

When this module is wrong, the worst case is one accidental ping on
a closed day — the body still reads correctly. Update HOLIDAYS_2026
+ HOLIDAYS_2027 as new dates publish.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger("market_hours.reminder")

# ============================================================================
# US market holidays — full closures only (NYSE + NASDAQ).
# Update yearly. See https://www.nyse.com/markets/hours-calendars for
# the canonical list. Includes weekends-observed dates (e.g. Jul 4 2026
# is Saturday → observed Friday Jul 3).
# ============================================================================
HOLIDAYS_2026: set[str] = {
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # MLK Jr Day
    "2026-02-16",  # Presidents Day
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-06-19",  # Juneteenth
    "2026-07-03",  # Independence Day (observed; Jul 4 is Sat)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving
    "2026-12-25",  # Christmas
}
HOLIDAYS_2027: set[str] = {
    "2027-01-01",
    "2027-01-18",
    "2027-02-15",
    "2027-03-26",  # Good Friday
    "2027-05-31",
    "2027-06-18",  # Juneteenth (observed; Jun 19 is Sat)
    "2027-07-05",  # Independence Day (observed; Jul 4 is Sun)
    "2027-09-06",
    "2027-11-25",
    "2027-12-24",  # Christmas (observed; Dec 25 is Sat)
}

ALL_HOLIDAYS: set[str] = HOLIDAYS_2026 | HOLIDAYS_2027


def _now_et() -> datetime:
    """Current time in US Eastern. All schedule decisions use this — the
    container's TZ is America/New_York per docker-compose, but using ET
    explicitly here keeps the function portable + testable."""
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=-5)))


def is_market_day(now: datetime | None = None) -> bool:
    """True if the NYSE/NASDAQ is open today.

    Weekends auto-fail. Cron already filters Mon-Fri so this mainly
    catches federal holidays that land on a weekday.
    """
    n = now if now is not None else _now_et()
    if n.weekday() >= 5:        # Sat=5, Sun=6
        return False
    return n.strftime("%Y-%m-%d") not in ALL_HOLIDAYS


def fire_open_reminder() -> dict:
    """09:15 ET — fires 15 min before regular session opens.

    No-op on weekends + US holidays. Routes to /morning so the user
    lands on the Morning Brief + top SEPA candidates.
    """
    n = _now_et()
    if not is_market_day(n):
        log.info("market_hours: skipping open reminder (non-market day %s)",
                 n.strftime("%Y-%m-%d"))
        return {"ok": False, "reason": "non-market day", "date": n.strftime("%Y-%m-%d")}
    payload = {
        "title": "🔔 Market opens in 15 min",
        "body":  (
            "Regular session starts 9:30 ET. Quick checklist: scan "
            "/morning brief, confirm watchlist stops, set today's PEG / "
            "Inside-Day buy-stops at Fidelity, and stand by for the "
            "9:46 ET ORB capture."
        ),
        "tag":   f"market-open-{n.strftime('%Y-%m-%d')}",  # one slot per day; replaces on device
        "url":   "/morning",
        "kind":  "market_hours_reminder",
    }
    try:
        from push import sender
        result = sender.send_to_all(payload, kind="market_hours_reminder")
    except Exception as exc:
        log.warning("open reminder send failed: %s", exc)
        return {"ok": False, "reason": str(exc)}
    log.info("market_hours: open reminder fired sent=%d failed=%d",
             result.get("sent", 0), result.get("failed", 0))
    return {"ok": True, "kind": "open", **result}


def fire_close_reminder() -> dict:
    """15:45 ET — fires 15 min before regular session closes.

    No-op on weekends + US holidays. Routes to /sepa so the user can
    review open positions, manage stops, flatten any ORB positions
    per the same-day discipline.
    """
    n = _now_et()
    if not is_market_day(n):
        log.info("market_hours: skipping close reminder (non-market day %s)",
                 n.strftime("%Y-%m-%d"))
        return {"ok": False, "reason": "non-market day", "date": n.strftime("%Y-%m-%d")}
    payload = {
        "title": "🔔 Market closes in 15 min",
        "body":  (
            "Final 15 minutes. Review open positions, manage stops at "
            "today's close, flatten any ORB intraday positions per the "
            "no-overnight discipline, set tomorrow's PEG / Inside-Day "
            "buy-stops at Fidelity before bed."
        ),
        "tag":   f"market-close-{n.strftime('%Y-%m-%d')}",
        "url":   "/sepa",
        "kind":  "market_hours_reminder",
    }
    try:
        from push import sender
        result = sender.send_to_all(payload, kind="market_hours_reminder")
    except Exception as exc:
        log.warning("close reminder send failed: %s", exc)
        return {"ok": False, "reason": str(exc)}
    log.info("market_hours: close reminder fired sent=%d failed=%d",
             result.get("sent", 0), result.get("failed", 0))
    return {"ok": True, "kind": "close", **result}


if __name__ == "__main__":
    # CLI for cron + manual testing:
    #   python -m market_hours.reminder open
    #   python -m market_hours.reminder close
    import sys
    arg = sys.argv[1] if len(sys.argv) > 1 else "open"
    if arg == "open":
        print(fire_open_reminder())
    elif arg == "close":
        print(fire_close_reminder())
    else:
        print(f"unknown arg: {arg} (expected 'open' or 'close')")
        sys.exit(2)
