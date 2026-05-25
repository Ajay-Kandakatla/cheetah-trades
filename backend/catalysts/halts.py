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
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests

log = logging.getLogger("catalysts.halts")

_CACHE_TTL_SEC = 60
_cache: dict = {"data": None, "ts": 0.0}

_HALT_FEED_URL = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"

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


def get_today_halts(force: bool = False) -> dict:
    """Return today's halts, grouped by ticker."""
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
            headers={"User-Agent": "Mozilla/5.0 cheetah-frenzy-radar"},
            timeout=8,
        )
        if r.status_code == 200:
            raw_halts = _parse_halts_xml(r.text)
    except Exception as exc:
        log.warning("halts feed fetch failed: %s", exc)

    # Group by ticker, count halts per ticker today
    today_iso = datetime.now(timezone.utc).date().isoformat()
    today_short = datetime.now(timezone.utc).strftime("%m/%d/%Y")

    by_ticker: dict[str, dict] = {}
    for h in raw_halts:
        # NASDAQ uses MM/DD/YYYY format
        if h.get("halt_date") != today_short:
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

    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "session_date": today_iso,
        "by_ticker": by_ticker,
        "n_total": len(by_ticker),
        "n_with_parabolic": sum(1 for v in by_ticker.values() if v["n_parabolic_halts"] > 0),
        "cached": False,
        "cache_age_sec": 0,
    }
    _cache["data"] = payload
    _cache["ts"] = now
    return payload


def get_ticker_halts(ticker: str) -> Optional[dict]:
    """Get halt summary for one ticker today."""
    h = get_today_halts()
    return h["by_ticker"].get(ticker.upper())


__all__ = ["get_today_halts", "get_ticker_halts", "PARABOLIC_REASONS"]
