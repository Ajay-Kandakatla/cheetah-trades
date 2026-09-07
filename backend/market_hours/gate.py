"""Closed-day gate for market alerts and scans — ONE calendar, THREE chokepoints.

Ajay 2026-09-07, Labor Day, 11:35 ET: "TOday is holiday so turn of alerts scans."

What had happened: the crontab filters Mon–Fri only, so on a weekday holiday
every intraday job ran against Friday's closing prices. Sixteen ``pivot_alert``
pushes landed on his phone at 09:00 ET on a closed market (OGN, LNG, HLX "at the
pivot" at Friday's close; C, OXY, IBKR, VRTX "approaching"). The zone-edge loop
already carried a holiday check (``zone_edge.in_session``, fix 2026-09-05);
nothing else did — not the alerts CLI, not the demand / Gabbar watchers, not
the 16:30 fast-scan, not the paper-lane warms.

Calendar: ``market_hours.reminder.ALL_HOLIDAYS`` (NYSE full-closure days,
2026 + 2027) plus weekends. Extend that set when the exchange publishes the
next year — every consumer below reads it.

Chokepoints:

* ``closed_reason(now)`` — ``"weekend"``, ``"holiday YYYY-MM-DD"`` or ``None``.
  ``CHEETAH_IGNORE_HOLIDAY=1`` lifts it for a deliberate manual run (a measured
  scan on a holiday afternoon, a backfill). Never set it in the crontab.
* push — ``push.sender.send_to_all`` / ``send_to_user`` drop every kind
  outside ``PERSONAL_KINDS`` on a closed day BEFORE touching a device or
  ``push_history`` (the row would only be noise). Personal kinds — todos,
  flashcards, household, sign-ins, health — still deliver.
* jobs — ``sepa.cli`` skips ``MARKET_DAY_CMDS``; the standalone crontab
  modules run through ``python -m market_hours.gate <module> [args]`` (or
  ``--call pkg.mod:func``), which exits 0 without importing the target when
  the market is closed.
"""
from __future__ import annotations

import importlib
import logging
import os
import runpy
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger(__name__)

OVERRIDE_ENV = "CHEETAH_IGNORE_HOLIDAY"

# Kinds that still deliver on a closed day: nothing in this set is computed
# from prices. Everything else (pivot / position / demand / promo / breakout /
# setup_* / stop_loss …, 70+ literals across the backend) is ticker-driven and
# on a closed day would be computed from STALE prices — so the default is DROP
# and this is the pass-list. Add a new personal kind HERE, never a market kind.
PERSONAL_KINDS: frozenset[str] = frozenset({
    "todo_reminder", "todo_daily_digest", "minervini_flashcards",
    "market_hours_reminder",          # self-gated on the same calendar
    "vb_workout", "vb_supplement", "vb_education",
    "user_signin", "product_launch", "health", "macbook",
    "house_daily", "house_stagnant", "house_scrape_failed",
    "generic",                        # notify.send_alert default
})

# The market kinds his phone actually carries (push/subs.default_prefs keep-set
# + the zone kinds). Pinned by the test so a rename never lets one slip into
# PERSONAL_KINDS by accident.
MARKET_ALERT_KINDS: frozenset[str] = frozenset({
    "pivot_alert", "position_alert", "price_alert", "demand_alert",
    "zone_bounce_alert", "supply_break_alert", "promo_alert", "pankaj_alert",
    "stage_out_alert", "sepa_new_candidate", "volume_breakout", "rising_momentum",
    "watchlist_breakout", "juggernaut_watchlist", "leaderboard_breakout",
    "stage_breakdown", "watchlist_stage_breakdown", "accumulation_change",
    "trade_flash", "scalp_tape", "morning_brief",
})

_ET = timezone(timedelta(hours=-4))


def _now_et() -> datetime:
    return datetime.now(timezone.utc).astimezone(_ET)


def override_active() -> bool:
    return os.environ.get(OVERRIDE_ENV, "").strip().lower() in ("1", "true", "yes")


def closed_reason(now: Optional[datetime] = None) -> Optional[str]:
    """Why the market is closed today, or None on a trading day.

    Weekends → "weekend"; a date in ``ALL_HOLIDAYS`` → "holiday YYYY-MM-DD".
    The override env lifts both (manual runs only)."""
    if override_active():
        return None
    from .reminder import ALL_HOLIDAYS   # lazy: reminder pulls the push stack
    n = now if now is not None else _now_et()
    if n.weekday() >= 5:
        return "weekend"
    day = n.strftime("%Y-%m-%d")
    if day in ALL_HOLIDAYS:
        return f"holiday {day}"
    return None


def should_drop_kind(kind: Optional[str], now: Optional[datetime] = None) -> Optional[str]:
    """The closed-day reason when ``kind`` is NOT a personal kind and the
    market is closed; None when the push should go out. ``kind=None`` is the
    untyped broadcast path — personal by construction (never price-driven)."""
    if kind is None or kind in PERSONAL_KINDS:
        return None
    return closed_reason(now)


def _run_call(spec: str) -> int:
    mod_name, _, func_name = spec.partition(":")
    if not mod_name or not func_name:
        log.error("gate --call expects pkg.mod:func, got %r", spec)
        return 2
    fn = getattr(importlib.import_module(mod_name), func_name)
    fn()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """``python -m market_hours.gate <module> [args…]`` or ``--call pkg.mod:func``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m market_hours.gate <module> [args…] | --call pkg.mod:func",
              file=sys.stderr)
        return 2
    target = argv[1] if argv[0] == "--call" and len(argv) > 1 else argv[0]
    reason = closed_reason()
    if reason:
        log.info("GATE closed (%s) — %s skipped; %s=1 forces a run", reason, target, OVERRIDE_ENV)
        return 0
    if argv[0] == "--call":
        return _run_call(target)
    sys.argv = [target] + argv[1:]
    runpy.run_module(target, run_name="__main__", alter_sys=True)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    sys.exit(main())
