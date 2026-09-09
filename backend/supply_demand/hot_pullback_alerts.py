"""🔥 Hot Pullback alerts — Ajay 2026-09-09:

    "Can you give me hot pull back alerts and chart pattern Alerts and also
     Sameday deman alerts please... Kill all other.. I just wanna these alerts..
     Default turn these on from tomorrow."

WHAT FIRES. One push per name per day, off the board's RECORDED CLOSED session
(`hot_pullback.last_closed_signals`), never a live re-scan. The board is computed
from the latest bar; during RTH that bar is today's unfinished session, so a
signal read live would repaint. The signal day is a closed session by definition.

WHAT THE PUSH SAYS, AND WHY IT SAYS IT. The board measures 51.8% win over 83
trades on 50 dates, expectancy +0.10R with a 95% interval of -0.188R to +0.405R
that INCLUDES ZERO, and P(R<=0) = 0.264. No gate inside the rule separates: the
demand band itself measures p=0.198 and flush depth is completely inert (10%,
12% and 15% select the identical 83 events). He was shown all of that and asked
for the alerts anyway, as a watchlist ping. So every push carries the win rate
and the words "interval includes zero" — the phone must never imply more than
the measurement supports.

THE EDGE, SUCH AS IT IS, IS GONE BY DAY FIVE. The board says so on every row and
so does the push: this is a 1-3 session read.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("supply_demand.hot_pullback_alerts")

KIND = "hot_pullback_alert"
STATE_COLL = "hot_pullback_alerts"
MAX_SINGLES = 4          # the rest ride one digest, like every other board
ET = ZoneInfo("America/New_York")


def _db():
    try:
        from pymongo import MongoClient
        cli = MongoClient(os.getenv("MONGO_URL", "mongodb://mongo:27017"),
                          serverSelectionTimeoutMS=2500)
        return cli[os.getenv("MONGO_DB", "cheetah")]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("hot_pullback_alerts: no db: %s", exc)
        return None


def _day_et(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(tz=ET)).astimezone(ET).date().isoformat()


def study_line() -> str:
    """The honest one-liner that rides on every push. Built from the STUDY dict
    so a corrected number can never go stale here."""
    from . import hot_pullback as HP
    s = HP.STUDY
    return ("%.1f%% win over %d trades · expectancy %+gR, 95%% interval %+gR to %+gR "
            "— INCLUDES ZERO. Watchlist, not an edge. Gone by day 5."
            % (s["sim_win_pct"], s["sim_n"], s["sim_expectancy_r"],
               s["ci_lo_r"], s["ci_hi_r"]))


def _num(x):
    """Float or None. Recorded rows carry dicts, strings and NaN in places a
    number is expected — never let one raise inside a push builder."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


def message(row: dict) -> dict:
    sym = row.get("symbol")
    band = row.get("band") or {}
    close = row.get("close")
    parts = []
    close = _num(close)
    if close is not None:
        parts.append("$%g" % close)
    fl = _num(row.get("flush_pct"))
    if fl is not None:
        parts.append("flushed %.0f%%" % abs(fl))
    # `reversal` is a DICT on a recorded row — {"off_low_pct", "range_pos"} —
    # not a number. A dry run of this module caught float(dict) before the cron
    # ever ran it.
    rv = row.get("reversal")
    if isinstance(rv, dict):
        off = _num(rv.get("off_low_pct"))
        if off is not None:
            parts.append("closed +%.1f%% off the low" % off)
        pos = _num(rv.get("range_pos"))
        if pos is not None:
            parts.append("%.0f%% up the day's range" % (pos * 100.0))
    elif rv is not None:
        off = _num(rv)
        if off is not None:
            parts.append("closed +%.1f%% off the low" % off)
    b_lo, b_hi = _num(band.get("lo")), _num(band.get("hi"))
    if b_lo is not None and b_hi is not None:
        parts.append("band $%g-%g" % (b_lo, b_hi))
    vx = _num(row.get("vol_x"))
    if vx is not None:
        parts.append("%.1fx vol" % vx)
    plan = row.get("plan") or {}
    stop = _num(plan.get("stop"))
    if stop is not None:
        parts.append("stop $%.2f" % stop)
    body = " · ".join(parts) + " · " + study_line()
    return {"title": "\U0001F525 %s hot pullback" % sym,
            "body": body, "icon": "/icon.svg",
            "tag": "hotpb-%s" % str(sym).lower(),
            "url": "/chart-maps?tab=hot_pullback", "kind": KIND, "ticker": sym,
            "data": {"url": "/chart-maps?tab=hot_pullback", "symbol": sym,
                     "source": "hot_pullback"}}


def digest_message(rows: list, day: str) -> Optional[dict]:
    if not rows:
        return None
    names = ", ".join(str(r.get("symbol")) for r in rows[:12])
    return {"title": "\U0001F525 %d more hot pullbacks" % len(rows),
            "body": names + " · " + study_line(), "icon": "/icon.svg",
            "tag": "hotpb-digest-%s" % day,
            "url": "/chart-maps?tab=hot_pullback", "kind": KIND, "ticker": None,
            "data": {"url": "/chart-maps?tab=hot_pullback", "source": "hot_pullback"}}


def check_once(owner: Optional[str] = None, now: Optional[datetime] = None,
               rows: Optional[list] = None, day: Optional[str] = None,
               coll=None, force: bool = False) -> dict:
    """One pass. Reads the newest RECORDED closed session and pushes what has
    not already been pushed for that signal day."""
    from push import sender
    from portfolio.alerts import _resolve_owner
    from . import hot_pullback as HP

    owner = (owner or _resolve_owner()).lower()
    today = _day_et(now)
    if rows is None:
        day, rows = HP.last_closed_signals()
    rows = list(rows or [])
    if not day:
        return {"ran": True, "reason": "nothing recorded", "pushed": 0,
                "candidates": 0, "skipped_seen": 0}
    if coll is None:
        db = _db()
        coll = getattr(db, STATE_COLL) if db is not None else None

    fresh, seen = [], 0
    for r in rows:
        sym = r.get("symbol")
        if not sym:
            continue
        key = "%s:%s" % (sym, day)
        if coll is not None and not force:
            try:
                if coll.find_one({"_id": key}):
                    seen += 1
                    continue
            except Exception as exc:                            # pragma: no cover
                log.warning("hot_pullback_alerts dedupe read failed: %s", exc)
        fresh.append((key, r))

    pushed = 0
    singles, rest = fresh[:MAX_SINGLES], fresh[MAX_SINGLES:]
    to_send = [(k, message(r)) for k, r in singles]
    dig = digest_message([r for _k, r in rest], day)
    if dig is not None:
        to_send.append(("%s:digest:%s" % (day, today), dig))
    for key, msg in to_send:
        res = sender.send_to_user(owner, msg, kind=KIND) or {}
        sent, targets = res.get("sent", 0), res.get("total_targets", 0)
        if sent > 0:
            pushed += 1
        if (sent > 0 or targets == 0) and coll is not None:
            try:
                coll.update_one({"_id": key}, {"$set": {
                    "at": datetime.now(timezone.utc), "signal_day": day,
                    "sent": sent, "targets": targets}}, upsert=True)
            except Exception as exc:                            # pragma: no cover
                log.warning("hot_pullback_alerts dedupe write failed: %s", exc)
    out = {"ran": True, "signal_day": day, "candidates": len(rows),
           "fresh": len(fresh), "skipped_seen": seen, "pushed": pushed,
           "singles": len(singles), "digest": bool(dig)}
    log.info("HOT-PULLBACK-ALERTS: %s", out)
    return out


if __name__ == "__main__":                                     # pragma: no cover
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    check_once()
