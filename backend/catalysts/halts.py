"""NASDAQ trading-halts feed.

NASDAQ publishes intraday halts as an RSS feed at:
  https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts

Halt reason codes are highly correlated with frenzy moves:
  T1   = News pending — material news incoming, often big move on resume
  LUDP = Limit Up-Down Pause — stock crossed circuit-breaker bands (parabolic move)
  H10  = SEC suspension (very bad — usually fraud)
  T2   = News released, awaiting full distribution
  T5   = Single-stock circuit breaker triggered
  T6   = Halt for extraordinary market activity
  T8   = ETP halt
  T12  = Trading halted for additional information requested

The single most actionable for our purposes: stocks with ≥2 halts today,
especially LUDP. A LUDP halt means the stock moved >5% in <5 minutes — that's
the parabolic phase signature.

Cached 60 seconds during market hours.

"Today" is the ET date (2026-10-13). It was the UTC date, so from 20:00 EDT /
19:00 EST every one of the session's halts vanished (the feed stamps HaltDate
on the ET clock). `get_halts_for_date(d)` reads one PAST session from the same
feed (`&haltdate=MMDDYYYY`, measured 2026-10-13: 10/09 → 72 items, every one
dated 10/09) — the Gajjala's tab backfills its 30-session halt history with it. A dated read
whose items are not ALL dated that session (or that has none) is a failed read ({}), never "no halts".
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import requests

log = logging.getLogger("catalysts.halts")

_CACHE_TTL_SEC = 60
_cache: dict = {"data": None, "ts": 0.0}

_HALT_FEED_URL = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
_HEADERS = {"User-Agent": "Mozilla/5.0 cheetah-frenzy-radar"}
_ET = ZoneInfo("America/New_York")

# Reasons that signal a parabolic move in progress (vs e.g. corporate action)
PARABOLIC_REASONS = {"LUDP", "T1", "T6"}


def _parse_halts_xml(xml: str) -> list[dict]:
    """Parse the RSS feed body into halt records. Hand-parsed to avoid
    pulling a heavy XML lib for what's a simple flat structure."""
    halts = []
    items = re.findall(r"<item>(.*?)</item>", xml, re.S)
    for item in items:
        # Each item has fields like <ndaq:IssueSymbol>RYOJ</ndaq:IssueSymbol>,
        # <ndaq:HaltDate>...</ndaq:HaltDate>, <ndaq:ReasonCode>...
        sym = re.search(r"<ndaq:IssueSymbol>([^<]+)</ndaq:IssueSymbol>", item)
        date = re.search(r"<ndaq:HaltDate>([^<]+)</ndaq:HaltDate>", item)
        time_m = re.search(r"<ndaq:HaltTime>([^<]+)</ndaq:HaltTime>", item)
        reason = re.search(r"<ndaq:ReasonCode>([^<]+)</ndaq:ReasonCode>", item)
        resume_date = re.search(r"<ndaq:ResumptionDate>([^<]*)</ndaq:ResumptionDate>", item)
        resume_time = re.search(r"<ndaq:ResumptionTradeTime>([^<]*)</ndaq:ResumptionTradeTime>", item)
        name = re.search(r"<ndaq:IssueName>([^<]+)</ndaq:IssueName>", item)

        if not sym:
            continue

        halts.append({
            "ticker": sym.group(1).strip().upper(),
            "name": name.group(1).strip() if name else None,
            "halt_date": date.group(1).strip() if date else None,
            "halt_time": time_m.group(1).strip() if time_m else None,
            "reason_code": reason.group(1).strip() if reason else None,
            "resume_date": (resume_date.group(1).strip() if resume_date and resume_date.group(1).strip() else None),
            "resume_time": (resume_time.group(1).strip() if resume_time and resume_time.group(1).strip() else None),
        })
    return halts


def _now_et() -> datetime:
    """The ET wall clock — the clock NASDAQ stamps HaltDate with."""
    return datetime.now(_ET)


def _group_by_ticker(raw_halts: list[dict], day: date) -> dict:
    """{ticker: {ticker, name, halts[], n_halts, n_parabolic_halts, reasons[]}} for the halts dated `day`."""
    day_short = day.strftime("%m/%d/%Y")                # NASDAQ uses MM/DD/YYYY format
    by_ticker: dict[str, dict] = {}
    for h in raw_halts:
        if h.get("halt_date") != day_short:
            continue
        t = h["ticker"]
        if t not in by_ticker:
            by_ticker[t] = {
                "ticker": t,
                "name": h.get("name"),
                "halts": [],
                "n_halts": 0,
                "n_parabolic_halts": 0,
                "reasons": set(),
            }
        rec = by_ticker[t]
        rec["halts"].append({
            "halt_time": h.get("halt_time"),
            "reason_code": h.get("reason_code"),
            "resume_date": h.get("resume_date"),
            "resume_time": h.get("resume_time"),
        })
        rec["n_halts"] += 1
        rec["reasons"].add(h.get("reason_code") or "?")
        if (h.get("reason_code") or "") in PARABOLIC_REASONS:
            rec["n_parabolic_halts"] += 1

    # Convert sets to lists for JSON
    for v in by_ticker.values():
        v["reasons"] = sorted(v["reasons"])
    return by_ticker


def get_today_halts(force: bool = False) -> dict:
    """Return today's (ET) halts, grouped by ticker."""
    now = time.time()
    if not force and _cache["data"] is not None and (now - _cache["ts"]) < _CACHE_TTL_SEC:
        out = dict(_cache["data"])
        out["cached"] = True
        out["cache_age_sec"] = round(now - _cache["ts"])
        return out

    raw_halts: list[dict] = []
    try:
        r = requests.get(
            _HALT_FEED_URL,
            headers=_HEADERS,
            timeout=8,
        )
        if r.status_code == 200:
            raw_halts = _parse_halts_xml(r.text)
    except Exception as exc:
        log.warning("halts feed fetch failed: %s", exc)

    # Group by ticker, count halts per ticker today — the ET date (was UTC: empty after 20:00 EDT / 19:00 EST)
    today = _now_et().date()
    by_ticker = _group_by_ticker(raw_halts, today)

    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "session_date": today.isoformat(),
        "by_ticker": by_ticker,
        "n_total": len(by_ticker),
        "n_halts": sum(v["n_halts"] for v in by_ticker.values()),
        "n_with_parabolic": sum(1 for v in by_ticker.values() if v["n_parabolic_halts"] > 0),
        "cached": False,
        "cache_age_sec": 0,
    }
    _cache["data"] = payload
    _cache["ts"] = now
    return payload


def get_halts_for_date(d: date) -> dict:
    """One past session's halts, grouped by ticker — the same feed with `&haltdate=MMDDYYYY`, the same parser,
    filtered to `d`. NOT cached (a nightly backfill reads each date once). {} (never a raise) = the read FAILED:
    a non-200, a transport error, an empty body, or ANY item dated another day (2026-10-13 review: a 200 carrying
    only 10/09's items, asked as 10/08, used to come back as "no halts on 10/08" and was marked read for good — a
    feed that ignores `&haltdate` or a truncated body must never pass for a halt-free session)."""
    url = _HALT_FEED_URL + "&haltdate=" + d.strftime("%m%d%Y")
    try:
        r = requests.get(url, headers=_HEADERS, timeout=8)
    except Exception as exc:
        log.warning("halts feed fetch failed for %s: %s", d, exc)
        return {}
    if r.status_code != 200:
        log.warning("halts feed for %s -> HTTP %s", d, r.status_code)
        return {}
    raw = _parse_halts_xml(r.text)
    day_short = d.strftime("%m/%d/%Y")
    if not raw or any(h.get("halt_date") != day_short for h in raw):
        log.warning("halts feed for %s: %d items, not all dated %s — treated as a failed read",
                    d, len(raw), day_short)
        return {}
    by_ticker = _group_by_ticker(raw, d)
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "session_date": d.isoformat(),
        "by_ticker": by_ticker,
        "n_total": len(by_ticker),
        "n_halts": sum(v["n_halts"] for v in by_ticker.values()),
        "n_with_parabolic": sum(1 for v in by_ticker.values() if v["n_parabolic_halts"] > 0),
    }


def get_ticker_halts(ticker: str) -> Optional[dict]:
    """Get halt summary for one ticker today."""
    h = get_today_halts()
    return h["by_ticker"].get(ticker.upper())


__all__ = ["get_today_halts", "get_ticker_halts", "get_halts_for_date", "PARABOLIC_REASONS"]
