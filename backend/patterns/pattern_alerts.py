"""📐 Chart-pattern alerts — Ajay 2026-09-09:

    "Can you give me hot pull back alerts and chart pattern Alerts and also
     Sameday deman alerts please... Kill all other.. I just wanna these alerts."

WHAT FIRES. One push per (symbol, pattern, confirmation day) on a pattern that
CONFIRMED on the daily frame — the scan's own `status == "confirmed"` with
`bars_since_confirm` inside FRESH_BARS. `patterns_scan` is written by the
existing scan; this module never rescans, it only reads and pushes.

WHAT THE PUSH SAYS, AND WHY. His own ledger, 669 resolved observations graded 21
sessions forward:

    cup_with_handle          n=434   45% up
    double_bottom            n=248   43% up
    triple_bottom            n= 68   37% up
    inverse_head_shoulders   n= 10   10% up
    PLACEBO (all resolved)   n=659   50% up

NOT ONE BEATS CHANCE. He was shown that and asked for the alerts anyway. So the
pattern's own record and the placebo ride in the body of every single push. This
is a watchlist ping and the phone says so; it is not a signal this app can stand
behind, and nothing in here is allowed to imply otherwise.

flat_top is excluded outright — it fired on 120 of 120 random names.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("patterns.pattern_alerts")

KIND = "pattern_alert"
STATE_COLL = "pattern_alerts"
FRESH_BARS = 2           # confirmed within this many sessions
MAX_SINGLES = 4
ET = ZoneInfo("America/New_York")


def _db():
    try:
        from pymongo import MongoClient
        cli = MongoClient(os.getenv("MONGO_URL", "mongodb://mongo:27017"),
                          serverSelectionTimeoutMS=2500)
        return cli[os.getenv("MONGO_DB", "cheetah")]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("pattern_alerts: no db: %s", exc)
        return None


def _day_et(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(tz=ET)).astimezone(ET).date().isoformat()


def record_line(pattern: str) -> str:
    """The pattern's measured record beside the placebo. Standing rule: never a
    per-name rate without its placebo. Read from the one table."""
    from supply_demand import bullish_context as BC
    rec = BC.PATTERN_RECORD.get(pattern)
    n_p, up_p, _ = BC.PATTERN_PLACEBO
    if not rec:
        return "no measured record · placebo %d%% up (n=%d)" % (up_p, n_p)
    n, up, mean = rec
    return ("your ledger: %d%% up over %d · placebo %d%% — it does NOT beat chance"
            % (up, n, up_p))


def is_fresh(row: dict, fresh_bars: int = FRESH_BARS) -> bool:
    """Confirmed, named, and recent. Anything unreadable is NOT fresh."""
    from supply_demand import bullish_context as BC
    if not isinstance(row, dict):
        return False
    name = row.get("pattern")
    if not name or name in BC.NOISE_PATTERNS:
        return False
    if str(row.get("status") or "").lower() != "confirmed":
        return False
    b = row.get("bars_since_confirm")
    try:
        b = int(b)
    except (TypeError, ValueError):
        return False
    return 0 <= b <= fresh_bars


def message(row: dict) -> dict:
    sym, pat = row.get("symbol"), row.get("pattern")
    parts = []
    if row.get("last_close") is not None:
        parts.append("$%g" % float(row["last_close"]))
    if row.get("neckline") is not None:
        parts.append("neckline $%g" % float(row["neckline"]))
    if row.get("stop") is not None:
        parts.append("stop $%g" % float(row["stop"]))
    if row.get("target") is not None:
        parts.append("target $%g" % float(row["target"]))
    parts.append(record_line(pat))
    return {"title": "\U0001F4D0 %s %s confirmed" % (sym, str(pat).replace("_", " ")),
            "body": " · ".join(parts), "icon": "/icon.svg",
            "tag": "pat-%s" % str(sym).lower(),
            "url": "/patterns", "kind": KIND, "ticker": sym,
            "data": {"url": "/patterns", "symbol": sym, "source": "patterns"}}


def digest_message(rows: list, day: str) -> Optional[dict]:
    if not rows:
        return None
    from supply_demand import bullish_context as BC
    names = ", ".join("%s (%s)" % (r.get("symbol"), str(r.get("pattern")).replace("_", " "))
                      for r in rows[:10])
    return {"title": "\U0001F4D0 %d more patterns confirmed" % len(rows),
            "body": names + " · placebo %d%% up — none of these beats chance"
                    % BC.PATTERN_PLACEBO[1],
            "icon": "/icon.svg", "tag": "pat-digest-%s" % day,
            "url": "/patterns", "kind": KIND, "ticker": None,
            "data": {"url": "/patterns", "source": "patterns"}}


def check_once(owner: Optional[str] = None, now: Optional[datetime] = None,
               rows: Optional[list] = None, coll=None, force: bool = False) -> dict:
    from push import sender
    from portfolio.alerts import _resolve_owner

    owner = (owner or _resolve_owner()).lower()
    day = _day_et(now)
    if rows is None:
        db = _db()
        doc = None
        if db is not None:
            try:
                doc = db.patterns_scan.find_one(sort=[("generated_at", -1)])
            except Exception as exc:                            # pragma: no cover
                log.warning("pattern_alerts: scan read failed: %s", exc)
        rows = list((doc or {}).get("results") or [])
    rows = list(rows or [])
    if coll is None:
        db = _db()
        coll = getattr(db, STATE_COLL) if db is not None else None

    fresh, seen, stale = [], 0, 0
    for r in rows:
        if not is_fresh(r):
            stale += 1
            continue
        key = "%s:%s:%s" % (r.get("symbol"), r.get("pattern"),
                            str(r.get("confirmed_date") or day)[:10])
        if coll is not None and not force:
            try:
                if coll.find_one({"_id": key}):
                    seen += 1
                    continue
            except Exception as exc:                            # pragma: no cover
                log.warning("pattern_alerts dedupe read failed: %s", exc)
        fresh.append((key, r))

    pushed = 0
    singles, rest = fresh[:MAX_SINGLES], fresh[MAX_SINGLES:]
    to_send = [(k, message(r)) for k, r in singles]
    dig = digest_message([r for _k, r in rest], day)
    if dig is not None:
        to_send.append(("digest:%s" % day, dig))
    for key, msg in to_send:
        res = sender.send_to_user(owner, msg, kind=KIND) or {}
        sent, targets = res.get("sent", 0), res.get("total_targets", 0)
        if sent > 0:
            pushed += 1
        if (sent > 0 or targets == 0) and coll is not None:
            try:
                coll.update_one({"_id": key}, {"$set": {
                    "at": datetime.now(timezone.utc), "day": day,
                    "sent": sent, "targets": targets}}, upsert=True)
            except Exception as exc:                            # pragma: no cover
                log.warning("pattern_alerts dedupe write failed: %s", exc)
    out = {"ran": True, "day": day, "candidates": len(rows), "fresh": len(fresh),
           "skipped_stale": stale, "skipped_seen": seen, "pushed": pushed,
           "singles": len(singles), "digest": bool(dig)}
    log.info("PATTERN-ALERTS: %s", out)
    return out


if __name__ == "__main__":                                     # pragma: no cover
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    check_once()
