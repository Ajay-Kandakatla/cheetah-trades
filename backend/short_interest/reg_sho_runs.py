"""🔒 Reg SHO close-out day — the pure run math behind the dated 🔒 tag (2026-11-24).

THE ASK (Ajay 2026-11-23, verbatim)
  "I need to know when it would like to Potentially squeeze.."
  "Add a tag with date in it.."

What this module is: the settlement-day calendar and the count of a name's current run of consecutive SETTLEMENT days
on its exchange's threshold list, with the dates the SEC rule hangs on that run. No Mongo, no HTTP, no display words:
`short_interest.reg_sho` reads the per-date list docs, calls `run_for`, and builds every served word.

What the date is (and is not):
  * 17 CFR 242.203(b)(3): a clearing-agency participant with a fail to deliver in a threshold security for thirteen
    consecutive settlement days must close it out by purchasing. The count runs PER FIRM, from its own fail (SEC staff
    FAQ 6.3, 6.8); the app sees the list, never the fails. Day 13 of the list run is a BACKSTOP date: Rule 204 already
    requires most fails to be closed out 1 to 3 settlement days after settlement, and the SEC staff say fails generally
    do not remain for 13 consecutive settlement days. A Rule 144 sale gets 35.
  * Settlement day (Rule 203(c)(5)) = a business day on which deliveries of securities AND payments of money can be
    made. Columbus Day and Veterans Day: the exchanges trade, banks are closed → not settlement days (measured: NYSE
    published no list, Nasdaq's file repeats the prior day's names).
  * Day 1 is a convention: the list dated D counts as day D. By FAQ 6.1 that list takes effect at the next open, so the
    same day can fall one settlement day later — `day13_late`.

The Rule 204 / Rule 144 numbers are DESCRIBED in served sentences, never compared. Only
REG_SHO_CLOSEOUT_SETTLEMENT_DAYS and REG_SHO_CLOSEOUT_BUY_WINDOW_DAYS feed the date math, read from the module globals at
call time. DISPLAY ONLY. UNMEASURED.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from short_interest import read as SR

REG_SHO_NAME = "SEC Regulation SHO"
# 17 CFR 242.203(b)(3): a fail "in a threshold security for thirteen consecutive settlement days" → close out by purchasing
REG_SHO_CLOSEOUT_RULE = "Rule 203(b)(3)"
REG_SHO_CLOSEOUT_SETTLEMENT_DAYS = 13
# SEC staff FAQ 6.7: a purchase "executed on settlement day 11, 12 or 13" counts → the LAST 3 days of the count
REG_SHO_CLOSEOUT_BUY_WINDOW_DAYS = 3
REG_SHO_STAFF_FAQ = "SEC staff FAQ 6.5, 6.7"
# 17 CFR 242.203(c)(5): settlement day = a business day on which deliveries of securities AND payments of money can be made
REG_SHO_SETTLEMENT_DAY_RULE = "Rule 203(c)(5)"
# 17 CFR 242.204(a): a fail in ANY equity security — by the open of "the settlement day following the settlement date";
# (a)(1) a long sale and (a)(3) market making: "the third consecutive settlement day following the settlement date"
REG_SHO_204_RULE = "Rule 204"
REG_SHO_204_SETTLEMENT_DAYS = 1
REG_SHO_204_LONG_MM_SETTLEMENT_DAYS = 3
# 17 CFR 242.203(b)(3)(ii): a threshold-security fail "sold pursuant to § 230.144 … for thirty-five consecutive
# settlement days"
REG_SHO_144_RULE = "Rule 144"
REG_SHO_144_SETTLEMENT_DAYS = 35
# the two bank holidays on which the exchanges trade and nothing settles (measured: NYSE no list, Nasdaq repeats the
# prior day)
BANK_HOLIDAYS_OPEN_MARKET = ("Columbus Day", "Veterans Day")

_DATE_KEYS = ("day11", "day13", "day13_late", "start_by")


def first_buy_day() -> int:
    """The first settlement day of the count on which a purchase counts (FAQ 6.7) — DERIVED, so one constant moves both."""
    return REG_SHO_CLOSEOUT_SETTLEMENT_DAYS - REG_SHO_CLOSEOUT_BUY_WINDOW_DAYS + 1


# ───────────────────────────────────────────── calendar
def columbus_day(year: int) -> date:
    """The second Monday of October."""
    d = date(year, 10, 1)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d + timedelta(days=7)


def veterans_day_observed(year: int) -> Optional[date]:
    """November 11; Monday the 12th when the 11th is a Sunday; None when it is a Saturday (the market is shut anyway)."""
    d = date(year, 11, 11)
    if d.weekday() == 5:
        return None
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def is_bank_holiday(d: date) -> bool:
    return d == columbus_day(d.year) or d == veterans_day_observed(d.year)


def is_settlement_day(d: date) -> bool:
    return SR.is_business_day(d) and not is_bank_holiday(d)


def prev_settlement_day(d: date) -> date:
    """`d` itself when it is a settlement day, else the nearest earlier one."""
    while not is_settlement_day(d):
        d -= timedelta(days=1)
    return d


def add_settlement_days(d: date, n: int) -> date:
    """The n-th settlement day AFTER `d` (n == 0 → d)."""
    out = d
    left = int(n)
    while left > 0:
        out += timedelta(days=1)
        if is_settlement_day(out):
            left -= 1
    return out


def settlement_days_back(anchor: date, n: int) -> list:
    """n settlement days, NEWEST FIRST, starting at prev_settlement_day(anchor)."""
    out = []
    d = prev_settlement_day(anchor)
    while len(out) < int(n):
        out.append(d)
        d = prev_settlement_day(d - timedelta(days=1))
    return out


def next_trading_day(d: date) -> date:
    """FAQ 6.5 says TRADING day: the close-out starts by the open of the trading day after the last count day."""
    return SR.add_business_days(d, 1)


def closeout_dates(start: date) -> dict:
    """{"day11", "day13", "day13_late", "start_by"} — dates, for a run whose day 1 is `start`."""
    rule = REG_SHO_CLOSEOUT_SETTLEMENT_DAYS
    d13 = add_settlement_days(start, rule - 1)
    return {"day11": add_settlement_days(start, first_buy_day() - 1),
            "day13": d13,
            "day13_late": add_settlement_days(d13, 1),
            "start_by": next_trading_day(d13)}


def _iso(d) -> Optional[str]:
    return d.isoformat() if d else None


def unknown_block() -> dict:
    """The run block of state "unknown": days 0, every date None."""
    return {"state": "unknown", "days": 0, "start": None, "through": None, "window_from": None,
            "day11": None, "day13": None, "day13_late": None, "start_by": None, "missing": None,
            "rule_days": REG_SHO_CLOSEOUT_SETTLEMENT_DAYS, "first_buy_day": first_buy_day()}


def run_for(sym: str, days_desc: list, members: dict) -> dict:
    """The name's current run on ONE market's lists.

    days_desc: settlement days, newest first (days_desc[0] = the list the tag is read from).
    members: {iso: frozenset of normalised symbols | None}; None (or an absent key) = that day's list was NOT READ —
    counted neither as on nor as off. A READ list without the name ends the run.
    """
    if not days_desc:
        return unknown_block()
    rule = REG_SHO_CLOSEOUT_SETTLEMENT_DAYS
    n = 0
    start = None
    missing = None
    ended = False
    for d in days_desc:
        s = members.get(d.isoformat())
        if s is None:
            missing = d
            break
        if sym in s:
            n += 1
            start = d
            continue
        ended = True
        break
    dates = dict.fromkeys(_DATE_KEYS)
    if ended and n > 0:
        state = "counting" if n < rule else ("reached" if n == rule else "passed")
        dates = closeout_dates(start)
    elif n >= rule:
        state = "passed_open"                    # at least `rule` for sure, the first day not known
        start = None
    else:
        state = "unknown"                        # incl. n == 0
        start = None
    out = {"state": state, "days": n, "start": _iso(start), "through": _iso(days_desc[0]),
           "window_from": _iso(days_desc[-1])}
    for k in _DATE_KEYS:
        out[k] = _iso(dates[k])
    out.update({"missing": _iso(missing), "rule_days": rule, "first_buy_day": first_buy_day()})
    return out
