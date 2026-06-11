"""Earnings-date watch — never buy into a report blind again.

Built 2026-06-11 after ATEX: it passed every technical gate, Ajay entered,
and it reported THAT EVENING (2026-06-10 AMC, EPS $0.98 vs $1.37 est,
-28% surprise). The chart can't show a scheduled binary event — this
module does.

Source: yfinance get_earnings_dates / Ticker.calendar (per-symbol, exact
timestamps → BMO/AMC derivable). EarningsWhispers (the user's preferred
site) has no stable public API — every UI chip deep-links to
earningswhispers.com/stocks/{sym} instead, so the whisper numbers are one
click away while OUR dates come from a source that can't silently break.

Coverage: the decision universe — latest scan candidates + portfolio
holdings + watchlist. Cached in Mongo `earnings_calendar`; a date is
re-fetched when missing, older than 3 days, or already in the past.
Nightly cron (`python -m sepa.earnings_watch`) + read-through on the
bulk endpoint.
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional

log = logging.getLogger("sepa.earnings_watch")

_REFETCH_AFTER_SEC = 3 * 24 * 3600
_MAP_HORIZON_DAYS = 30          # bulk map only carries dates within this window
WARN_WINDOW_DAYS = 7            # the UI/filters treat <= this as "earnings soon"


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].earnings_calendar
    except Exception:
        return None


def _today_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now().astimezone()


def _f(x) -> Optional[float]:
    """float or None — NaN-safe (yfinance hands back NaN for missing cells)."""
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _fetch_next(symbol: str) -> Optional[dict]:
    """Next earnings event for one symbol via yfinance — AND the most recent
    PAST report from the same frame (date, actual vs estimate, surprise %),
    at zero extra API cost. The past report powers the "good earnings →
    potential bull" picks (Ajay 2026-06-11, after being shaken out of ATEX
    right before its post-earnings rip)."""
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        today = _today_et().date()
        # Preferred: get_earnings_dates — exact timestamps, estimates included.
        try:
            df = t.get_earnings_dates(limit=8)
        except Exception:
            df = None
        out: dict = {}
        if df is not None and len(df):
            def when_of(ts):
                return "BMO" if ts.hour < 9 else ("AMC" if ts.hour >= 15 else None)
            future = [(ts, row) for ts, row in df.iterrows() if ts.date() >= today]
            past = [(ts, row) for ts, row in df.iterrows()
                    if ts.date() < today and _f(row.get("Reported EPS")) is not None]
            if future:
                ts, row = min(future, key=lambda x: x[0])
                out.update(next_date=ts.date().isoformat(), when=when_of(ts),
                           eps_estimate=_f(row.get("EPS Estimate")))
            if past:
                ts, row = max(past, key=lambda x: x[0])
                out.update(last_report={
                    "date": ts.date().isoformat(),
                    "when": when_of(ts),
                    "eps_actual": _f(row.get("Reported EPS")),
                    "eps_estimate": _f(row.get("EPS Estimate")),
                    "surprise_pct": _f(row.get("Surprise(%)")),
                })
            if out:
                out.setdefault("next_date", None)
                out.setdefault("when", None)
                out.setdefault("eps_estimate", None)
                out.setdefault("last_report", None)
                return out
        # Fallback: Ticker.calendar (sometimes an estimate/range, no time).
        cal = t.calendar
        dates = (cal or {}).get("Earnings Date") if isinstance(cal, dict) else None
        if dates:
            future = [d for d in dates if d >= today]
            if future:
                return {"next_date": min(future).isoformat(), "when": None,
                        "eps_estimate": None, "last_report": None}
    except Exception as exc:
        log.debug("earnings fetch failed %s: %s", symbol, exc)
    return None


def _universe() -> List[str]:
    syms: set = set()
    try:
        from . import scanner
        for r in (scanner.load_latest() or {}).get("all_results") or []:
            if r.get("symbol"):
                syms.add(r["symbol"].upper())
    except Exception as exc:
        log.debug("universe: scan rows unavailable: %s", exc)
    try:
        from pymongo import MongoClient
        db = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                         serverSelectionTimeoutMS=2000)[os.getenv("MONGO_DB", "cheetah")]
        for d in db.portfolio_holdings.find({}, {"ticker": 1, "symbol": 1}):
            s = (d.get("ticker") or d.get("symbol") or "").upper()
            if s:
                syms.add(s)
        for d in db.watchlist.find({}, {"ticker": 1}):
            if d.get("ticker"):
                syms.add(d["ticker"].upper())
    except Exception as exc:
        log.debug("universe: holdings/watchlist unavailable: %s", exc)
    return sorted(syms)


def refresh(symbols: Optional[List[str]] = None, max_workers: int = 4,
            force: bool = False) -> dict:
    """Fetch/update earnings dates for the decision universe. A doc is
    re-fetched when missing, stale (>3d), its date already passed, or it
    predates the last_report schema (2026-06-11). force=True refetches all."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "no mongo"}
    syms = [s.upper() for s in (symbols or _universe())]
    today = _today_et().date().isoformat()
    now = int(time.time())

    existing = {d["_id"]: d for d in coll.find({"_id": {"$in": syms}})}
    todo = []
    for s in syms:
        doc = existing.get(s)
        if (force
                or doc is None
                or now - (doc.get("fetched_at") or 0) > _REFETCH_AFTER_SEC
                or (doc.get("next_date") and doc["next_date"] < today)
                or "last_report" not in doc):
            todo.append(s)

    fetched = 0
    def work(sym: str):
        nonlocal fetched
        res = _fetch_next(sym)
        doc = {"_id": sym, "fetched_at": int(time.time()),
               **(res or {"next_date": None, "when": None,
                          "eps_estimate": None, "last_report": None})}
        try:
            coll.replace_one({"_id": sym}, doc, upsert=True)
            fetched += 1
        except Exception as exc:
            log.debug("earnings upsert failed %s: %s", sym, exc)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        list(ex.map(work, todo))
    log.info("earnings_watch: universe=%d refreshed=%d", len(syms), fetched)
    return {"ok": True, "universe": len(syms), "refreshed": fetched}


def _days_between(today_iso: str, date_iso: str) -> int:
    from datetime import date
    return (date.fromisoformat(date_iso) - date.fromisoformat(today_iso)).days


def bulk_map() -> dict:
    """{SYM: {date, days_to, when}} for every cached symbol whose next
    earnings is today..+30d. Small payload; FE fetches once per session."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "map": {}}
    today = _today_et().date().isoformat()
    out: Dict[str, dict] = {}
    try:
        for d in coll.find({"next_date": {"$ne": None}}):
            nd = d.get("next_date")
            if not nd or nd < today:
                continue
            days = _days_between(today, nd)
            if days > _MAP_HORIZON_DAYS:
                continue
            out[d["_id"]] = {"date": nd, "days_to": days, "when": d.get("when")}
    except Exception as exc:
        log.warning("earnings bulk map failed: %s", exc)
    return {"ok": True, "map": out, "as_of": today,
            "warn_window_days": WARN_WINDOW_DAYS,
            "source": "yfinance (Yahoo Finance); verify on "
                      "earningswhispers.com — dates can shift",
            "n": len(out)}


def _date_label(today_iso: str, date_iso: str) -> str:
    d = _days_between(today_iso, date_iso)
    if d == 0:
        return "Today"
    if d == 1:
        return "Tomorrow"
    from datetime import date
    dt = date.fromisoformat(date_iso)
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    mons = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return "%s %s %d" % (names[dt.weekday()], mons[dt.month - 1], dt.day)


def upcoming(days: int = 14) -> dict:
    """Names reporting in the next `days`, grouped by date, with SEPA context
    so the user can spot interesting upcoming reporters (Ajay 2026-06-11:
    "add upcoming post-earnings tabs by dates"). Cache-only — no network."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "groups": [], "n": 0}
    today = _today_et().date().isoformat()
    days = max(1, min(int(days), _MAP_HORIZON_DAYS))

    ctx: dict = {}
    try:
        from . import scanner
        for r in (scanner.load_latest() or {}).get("all_results") or []:
            ctx[r.get("symbol")] = {
                "rs_rank": r.get("rs_rank"),
                "stage": (r.get("stage") or {}).get("stage"),
                "is_buyable": bool(r.get("is_buyable")),
                "is_candidate": bool(r.get("qualifier") or r.get("is_candidate")),
            }
    except Exception as exc:
        log.debug("upcoming earnings: scan ctx unavailable: %s", exc)

    by_date: Dict[str, list] = {}
    try:
        for d in coll.find({"next_date": {"$ne": None}}):
            nd = d.get("next_date")
            if not nd or nd < today:
                continue
            dt = _days_between(today, nd)
            if dt > days:
                continue
            c = ctx.get(d["_id"]) or {}
            by_date.setdefault(nd, []).append({
                "symbol": d["_id"], "when": d.get("when"), "days_to": dt,
                "rs_rank": c.get("rs_rank"), "stage": c.get("stage"),
                "is_buyable": c.get("is_buyable"), "is_candidate": c.get("is_candidate"),
            })
    except Exception as exc:
        log.warning("upcoming earnings read failed: %s", exc)

    groups = []
    for nd in sorted(by_date):
        names = by_date[nd]
        # interesting (in the SEPA scan) first, then BMO before AMC, then A-Z
        names.sort(key=lambda x: (not (x["is_candidate"] or x["is_buyable"]),
                                  {"BMO": 0, None: 1, "AMC": 2}.get(x["when"], 1),
                                  x["symbol"]))
        groups.append({
            "date": nd, "label": _date_label(today, nd),
            "days_to": _days_between(today, nd), "n": len(names),
            "n_in_scan": sum(1 for x in names if x["is_candidate"] or x["is_buyable"]),
            "names": names,
        })
    return {"ok": True, "as_of": today, "horizon_days": days,
            "groups": groups, "n": sum(g["n"] for g in groups),
            "source": "yfinance (Yahoo Finance); verify on earningswhispers.com",
            "note": ("Scheduled report dates — dates can shift; confirm on "
                     "EarningsWhispers. 'in scan' = currently a SEPA "
                     "qualifier/buyable, i.e. worth watching into the print.")}


def days_to(symbol: str) -> Optional[int]:
    """Days until the cached next earnings for one symbol (None = unknown
    or none scheduled in cache). Backend consumers (alerts, AI analysis)."""
    coll = _coll()
    if coll is None:
        return None
    try:
        d = coll.find_one({"_id": (symbol or "").upper()})
        nd = (d or {}).get("next_date")
        if not nd:
            return None
        today = _today_et().date().isoformat()
        if nd < today:
            return None
        return _days_between(today, nd)
    except Exception:
        return None


def next_event(symbol: str) -> Optional[dict]:
    """{date, days_to, when} or None — used by the AI chart analysis."""
    coll = _coll()
    if coll is None:
        return None
    try:
        d = coll.find_one({"_id": (symbol or "").upper()})
        nd = (d or {}).get("next_date")
        if not nd:
            return None
        today = _today_et().date().isoformat()
        if nd < today:
            return None
        return {"date": nd, "days_to": _days_between(today, nd),
                "when": d.get("when")}
    except Exception:
        return None


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    r = refresh()
    log.info("EARNINGS-WATCH: %s", r)
    sys.exit(0 if r.get("ok") else 1)
