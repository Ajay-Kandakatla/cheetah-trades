"""Has a 🚀 Explosive Growth name JUST REPORTED — a calendar fact, nothing else.

Ajay 2026-09-17, verbatim: *"make a remindder ro scan explosive growth of new
earnings stocks and high light them to me in explosive growth tab"*.

WHAT THIS IS. A read-time JOIN between the board rows (`growth/tracker.py`) and
the earnings calendar (`sepa/earnings_watch.py`, collection `earnings_calendar`,
where **`_id` IS the symbol** — there is no `symbol` field). It adds one key per
row and one summary to the payload. It changes no order, no filter, no gate and
no number, and it sends nothing anywhere.

WHAT THIS IS NOT. There is no measurement in this repo that a just-reported
grower outperforms; the nearest prior — the 8-K event study, 2026-09-01 — read
NO chase edge after a fresh print. So the badge claims nothing and the wording
on the surface says so out loud.

EVERY NUMBER IS IMPORTED. The recency window is the repo's own
`sepa.earnings_picks.REPORT_WINDOW_DAYS` ("calendar days back a report still
counts") — the same window the Earnings report picks list he already reads uses,
so "just reported" means one thing across the app. The have-the-numbers-been-seen
rule is `chart_maps.earnings.phase_for`. Nothing here defines a window of its own.

THE ONE SUBTLETY, and it is the trap this module exists to avoid: `phase_for`
answers a BAR question, not a REPORT question — it returns REACTED for ANY
`next_date` in the past, so a frozen estimate that merely aged would manufacture
a report that may never have happened (live example: IPI carries
`next_date 2026-11-04` and no `last_report` at all). A `next_date` STRICTLY IN
THE PAST is therefore a stale estimate here, never a report. `next_date` can
only ever contribute a report dated TODAY.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sepa.earnings_picks import REPORT_WINDOW_DAYS as WINDOW_DAYS  # the ONE recency window
from chart_maps.earnings import REACTED, phase_for                 # the ONE BMO/AMC rule
from sepa import earnings_watch as EW                              # the ONE calendar

log = logging.getLogger("growth.earnings_fresh")

SOURCE = ("yfinance (Yahoo Finance) via sepa.earnings_watch — "
          "verify on EarningsWhispers; dates can shift")


def today_et() -> str:
    """The ET calendar date, from the calendar module's own clock. No second
    clock in this app — a date read here must agree with the one the cache was
    written against."""
    return EW._today_et().date().isoformat()


def _unknown() -> dict:
    """Unknown is NOT "did not report". 16 of the 21 names on the live board
    carry `last_report: None` (measured 2026-09-18), and reading that as a
    negative would be a lie told 16 times a page."""
    return {"known": False, "reported_on": None, "when": None,
            "days_ago": None, "fresh": False, "surprise_pct": None,
            "window_days": WINDOW_DAYS}


def _iso(v) -> Optional[str]:
    """A real YYYY-MM-DD, or None. Never raises."""
    s = str(v or "")[:10]
    try:
        date.fromisoformat(s)
    except (TypeError, ValueError):
        return None
    return s


def _when(v) -> Optional[str]:
    s = str(v or "").upper().strip()
    return s if s in ("BMO", "AMC") else None


def _num(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def read_one(cal: Optional[dict], today: str) -> dict:
    """PURE. Never raises. `cal` is one `earnings_calendar` doc (or None)."""
    if not isinstance(cal, dict) or not today:
        return _unknown()
    today = _iso(today)
    if not today:
        return _unknown()

    cands = []                      # (reported_on, when, surprise_pct)

    # 1. the PAST report the calendar recorded — the only source of EPS numbers
    lr = cal.get("last_report")
    if isinstance(lr, dict):
        last = _iso(lr.get("date"))
        if last and last <= today:
            cands.append((last, _when(lr.get("when")), _num(lr.get("surprise_pct"))))

    # 2. a report dated TODAY whose numbers `_fetch_next` cannot have written
    #    into last_report yet (it builds `past` from ts.date() < today, strictly).
    #    TODAY ONLY — see the module docstring for why a past next_date is not
    #    a report.
    nxt = _iso(cal.get("next_date"))
    if nxt and nxt == today:
        try:
            phase = phase_for({"next_date": nxt, "when": cal.get("when")},
                              today, today)
        except Exception as exc:                                # noqa: BLE001
            log.debug("earnings_fresh: phase_for failed: %s", exc)
            phase = None
        if phase == REACTED:
            cands.append((nxt, _when(cal.get("when")), None))

    if not cands:
        return _unknown()

    reported_on, when, surprise = max(cands, key=lambda c: c[0])
    try:
        days_ago = (date.fromisoformat(today) - date.fromisoformat(reported_on)).days
    except (TypeError, ValueError):                             # unreachable via _iso
        return _unknown()
    return {"known": True, "reported_on": reported_on, "when": when,
            "days_ago": days_ago,
            "fresh": 0 <= days_ago <= WINDOW_DAYS,
            "surprise_pct": surprise,
            "window_days": WINDOW_DAYS}


def _calendar_coll(db=None):
    """The `earnings_calendar` collection. `db` may be a database handle or the
    collection itself (tests hand a fake collection straight in)."""
    if db is None:
        return EW._coll()
    return getattr(db, "earnings_calendar", db)


def attach(rows: list, db=None, today: Optional[str] = None) -> dict:
    """Give every row `r["earnings_fresh"]`, return the payload-level summary.

    Mutates in place and NEVER adds, drops, reorders or re-sorts a row, and
    never touches any other row key. On ANY failure every row still gets the
    unknown shape and a summary still comes back — a dead calendar must not
    blank his growth board."""
    rows = rows if isinstance(rows, list) else []
    try:
        day = _iso(today) or today_et()
    except Exception as exc:                                    # noqa: BLE001
        log.debug("earnings_fresh: clock read failed: %s", exc)
        day = None

    cals: dict = {}
    try:
        syms = [str(r["symbol"]).upper() for r in rows
                if isinstance(r, dict) and r.get("symbol")]
        if syms:
            coll = _calendar_coll(db)
            if coll is not None:
                # `_id` IS the symbol. Querying {"symbol": ...} returns zero
                # docs with no error, which is how this join fails silently.
                for d in coll.find({"_id": {"$in": syms}}):
                    if isinstance(d, dict) and d.get("_id"):
                        cals[str(d["_id"]).upper()] = d
    except Exception as exc:                                    # noqa: BLE001
        log.debug("earnings_fresh: calendar read failed: %s", exc)
        cals = {}

    n = n_fresh = n_known = 0
    most_recent = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        n += 1
        sym = str(r.get("symbol") or "").upper()
        try:
            read = read_one(cals.get(sym), day) if day else _unknown()
        except Exception as exc:                                # noqa: BLE001
            log.debug("earnings_fresh: read failed %s: %s", sym, exc)
            read = _unknown()
        r["earnings_fresh"] = read
        if read.get("fresh"):
            n_fresh += 1
        if read.get("known"):
            n_known += 1
            cand = {"symbol": sym, "reported_on": read["reported_on"],
                    "days_ago": read["days_ago"]}
            # largest reported_on wins; a tie goes to the alphabetically first
            # symbol so the value is stable between page loads.
            if (most_recent is None
                    or cand["reported_on"] > most_recent["reported_on"]
                    or (cand["reported_on"] == most_recent["reported_on"]
                        and cand["symbol"] < most_recent["symbol"])):
                most_recent = cand

    return {"window_days": WINDOW_DAYS, "n": n, "n_fresh": n_fresh,
            "n_known": n_known, "n_unknown": n - n_known,
            "as_of": day, "most_recent": most_recent, "source": SOURCE}


def refresh_board_calendar(max_workers: int = 4) -> dict:
    """Re-fetch the earnings calendar for THIS BOARD's own symbols. Sends
    nothing, writes only `earnings_calendar`, touches no board document.

    `force=True` AND `merge=True` are both REQUIRED, and neither is optional:

    * `force=True` — the `todo` filter in `earnings_watch.refresh` skips any doc
      whose `last_report` KEY exists with value None, which is exactly the 16
      blank docs on this board. Measured 2026-09-17: the nightly sweep refreshed
      2 of 2,078 in one second. Without force they never heal.
    * `merge=True` — the write is a full `replace_one`, so one missed fetch
      would null the only good `last_report` on the board. See
      `earnings_watch.refresh`'s docstring.

    Budget: at most `tracker.MAX_ROWS` symbols (300); 21 today.

    SIDE EFFECT, named rather than buried: `sepa.earnings_picks` reads the same
    collection five minutes later. Healing a blank `last_report` can ADD a name
    to the Earnings report picks list on Portfolio / SEPA / Leaderboard /
    Scalping — the same gates, more complete input."""
    from growth import tracker as T
    syms = [r["symbol"] for r in ((T.board() or {}).get("rows") or [])
            if isinstance(r, dict) and r.get("symbol")]
    if not syms:
        return {"ok": True, "symbols": 0, "refreshed": 0, "reason": "empty board"}
    out = EW.refresh(symbols=syms, max_workers=max_workers,
                     force=True, merge=True) or {}
    return {**out, "symbols": len(syms)}
