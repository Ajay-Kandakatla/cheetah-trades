"""🌙 Overnight session clock (BUILD_SPEC16 §3.1, 2026-10-19) — PURE.

Alpaca's 24/5 doc: the overnight (Blue Ocean) session runs 20:00–04:00 ET
"the evening before the trade date", Sunday evening → Friday morning, and
follows the NYSE holiday calendar (no session the evening before a full
closure). The trade date is the date the session closes on.

The ONE market calendar decides whether a trade date trades:
`market_hours.gate.closed_reason`, passed an AWARE ET noon of the trade date
so its fixed −4 h `_ET` offset never matters; the next / previous market day
come from `catalysts.medical.reaction` (both read `reminder.is_market_day`).
Stdlib at import; the calendar modules are imported lazily.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from datetime import time as dtime
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")          # pinned equal to supply_demand.zone_edge.ET by test
SESSION_OPEN_ET = dtime(20, 0)             # Alpaca 24/5 doc — the evening before the trade date
SESSION_CLOSE_ET = dtime(4, 0)


def et_now(now: Optional[datetime] = None) -> datetime:
    """The injected instant in ET, or the real clock. A naive `now` is an ET
    wall clock by contract (the `rotation.hottest._now_et` rule)."""
    if now is None:
        return datetime.now(ET)
    if now.tzinfo is None:
        return now.replace(tzinfo=ET)
    return now.astimezone(ET)


def _at(d: date, t: dtime) -> datetime:
    return datetime.combine(d, t, ET)


def session_for(now: Optional[datetime] = None) -> dict:
    """`{open, trade_date, base_date, opens_at, closes_at, next_open, reason}`.

    open → the session's trade date, the base date (the previous market day:
    the regular close the overnight % is read against), its aware ET open /
    close, the NEXT session's open and reason None. closed → trade_date /
    base_date / opens_at / closes_at None, `next_open` the next session's open
    (always later than `now`) and the reason in words."""
    from market_hours import gate
    from catalysts.medical.reaction import next_market_day, prev_market_day

    t = et_now(now)
    d = t.date()
    if t.time() >= SESSION_OPEN_ET:
        td: Optional[date] = d + timedelta(days=1)
    elif t.time() < SESSION_CLOSE_ET:
        td = d
    else:
        td = None

    closed = None
    if td is not None:
        closed = gate.closed_reason(_at(td, dtime(12, 0)))
        if closed is None:
            return {
                "open": True,
                "trade_date": td,
                "base_date": prev_market_day(td),
                "opens_at": _at(td - timedelta(days=1), SESSION_OPEN_ET),
                "closes_at": _at(td, SESSION_CLOSE_ET),
                "next_open": _at(next_market_day(td) - timedelta(days=1), SESSION_OPEN_ET),
                "reason": None,
            }

    if td is None:
        reason = "between sessions"
    elif td.isoformat() in str(closed):
        # CHANGED 2026-10-19 (coordinator): the date once — closed_reason already
        # says "holiday YYYY-MM-DD". market_hours exposes no holiday names (they
        # live only in reminder.py comments), so the generic word stays.
        reason = f"no session — {closed}"
    else:
        reason = f"no session — {closed} {td.isoformat()}"
    return {
        "open": False,
        "trade_date": None,
        "base_date": None,
        "opens_at": None,
        "closes_at": None,
        "next_open": _at(next_market_day(d) - timedelta(days=1), SESSION_OPEN_ET),
        "reason": reason,
    }
