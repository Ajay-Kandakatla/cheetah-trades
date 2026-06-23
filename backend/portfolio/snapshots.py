"""Daily position-value snapshots → an HONEST "today's change".

The portfolio's per-position "today" used to be `shares × (last − prev_close)`
— the market's close-to-close move applied to the position. That's wrong for
anything opened TODAY: a position bought this morning, after a drop, never
experienced yesterday's close, so the market move overstates its loss. Real
case (Ajay 2026-06-23): MUU showed −20% (the security's close-to-close) when the
actual position, bought today near the low, was only −1.5%.

Fix: measure today's change from the position's value at YESTERDAY'S close
(a stored snapshot). A position with no prior-day snapshot was opened today, so
its baseline is the COST basis (what you paid), not a market close. A cron records
a snapshot just after the close each session; from the next day, held positions
get an exact close-to-close read while same-day buys read from cost.

`day_change_from_baseline` is PURE — unit-tested without Mongo.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Tuple

log = logging.getLogger("portfolio.snapshots")


def day_change_from_baseline(
    cur_value: Optional[float],
    cost_basis: Optional[float],
    prior_value: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    """Today's ($ change, % change) for one position.

    Baseline = ``prior_value`` (the position's value at yesterday's close) when
    we have it; otherwise ``cost_basis`` — a position with no prior-day snapshot
    was opened today, so its "today" is measured from what you paid, never the
    market's close-to-close (which would count a drop that happened before you
    bought). Returns (None, None) when not computable. Pure."""
    if cur_value is None:
        return None, None
    baseline = prior_value if prior_value is not None else cost_basis
    if not baseline:
        return None, None
    return cur_value - baseline, (cur_value / baseline - 1.0) * 100.0


# ── Mongo: record + read prior-day snapshots ────────────────────────────────

def _et_date(now: Optional[datetime] = None) -> str:
    try:
        from zoneinfo import ZoneInfo
        from datetime import timezone
        now = now or datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))
    except Exception:
        now = now or datetime.now()
    return now.strftime("%Y-%m-%d")


def _coll():
    try:
        from . import store
        db = store._get_db()
        return None if db is None else db.portfolio_snapshots
    except Exception as exc:                       # noqa: BLE001
        log.warning("portfolio_snapshots unavailable: %s", exc)
        return None


def record_snapshot(user_email: str, value_map: dict) -> dict:
    """Persist today's CLOSE value for each held position (idempotent per
    (email, ticker, account, date)). ``value_map`` maps (ticker, account) ->
    current value. Run by cron just after the close. Derived data — safe to
    rebuild."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "db unavailable"}
    date = _et_date()
    n = 0
    for (ticker, account), value in (value_map or {}).items():
        if value is None:
            continue
        coll.update_one(
            {"user_email": user_email.lower(), "ticker": ticker,
             "account": account or "default", "date": date},
            {"$set": {"value": float(value), "recorded_at": datetime.utcnow().isoformat()}},
            upsert=True,
        )
        n += 1
    return {"ok": True, "date": date, "positions": n}


def record_all() -> dict:
    """Cron entry (just after the close): snapshot every portfolio user's
    position values for today, so tomorrow's "today's change" is an exact
    close-to-close read. Idempotent — re-running the same session is harmless."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "db unavailable"}
    from . import store, quotes
    try:
        emails = store._get_db().portfolio_holdings.distinct("user_email")
    except Exception as exc:                        # noqa: BLE001
        return {"ok": False, "reason": "users query failed: %s" % exc}
    users = 0
    positions = 0
    for email in emails:
        holdings = store.list_holdings(email)
        if not holdings:
            continue
        qm = quotes.fetch_quotes([h["ticker"] for h in holdings]) or {}
        value_map = {}
        for h in holdings:
            last = (qm.get(h["ticker"]) or {}).get("last")
            if last is None:
                continue
            value_map[(h["ticker"], h.get("account") or "default")] = float(h.get("shares") or 0) * last
        r = record_snapshot(email, value_map)
        if r.get("ok"):
            users += 1
            positions += r.get("positions", 0)
    return {"ok": True, "users": users, "positions": positions, "date": _et_date()}


def prior_values(user_email: str, asof: Optional[str] = None) -> dict:
    """{(ticker, account): value} from the most recent snapshot date STRICTLY
    BEFORE ``asof`` (default today, ET) — i.e. each position's value at the
    previous session's close. Empty when no prior snapshots (then the rollup
    falls back to cost basis)."""
    coll = _coll()
    if coll is None:
        return {}
    today = asof or _et_date()
    out: dict = {}
    try:
        cur = coll.find({"user_email": user_email.lower(), "date": {"$lt": today}})
        # keep the latest date seen per (ticker, account)
        best_date: dict = {}
        for d in cur:
            key = (d.get("ticker"), d.get("account") or "default")
            dt = d.get("date") or ""
            if dt > best_date.get(key, ""):
                best_date[key] = dt
                out[key] = d.get("value")
    except Exception as exc:                        # noqa: BLE001
        log.warning("prior_values read failed: %s", exc)
        return {}
    return out
