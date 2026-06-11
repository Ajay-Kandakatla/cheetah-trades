"""Intraday OHLCV loader — 1-minute bars from Massive.

Cache layers:
  1. Mongo `intraday_cache` — keyed by (symbol, date). Bars for completed
     trading days never change, so once fetched they're cached forever.
     Today's bars are always re-fetched.
  2. In-memory dict for the duration of one request.

Bar timestamps are stored UTC. The bar's `session` field tags each bar as:
  'premarket' (04:00-09:30 ET) | 'rth' (09:30-16:00 ET) | 'afterhours' (16:00-20:00 ET)
"""
from __future__ import annotations

import logging
import os
from massive_keys import stocks_key
import time
from datetime import datetime, date, timedelta, time as dtime
from typing import Optional

import pandas as pd

log = logging.getLogger("daytrading.data")

BASE_URL = "https://api.massive.com"

# Eastern-time session boundaries — converted to UTC at call time to handle DST.
ET_PREMARKET_OPEN = dtime(4, 0)
ET_RTH_OPEN = dtime(9, 30)
ET_RTH_CLOSE = dtime(16, 0)
ET_AFTERHOURS_CLOSE = dtime(20, 0)

# ── Massive REST circuit-breaker ──────────────────────────────────────────
# Massive's REST data API can go fully unresponsive (read-timeouts) while the
# host still accepts connections, so each blocking fetch hangs for the whole
# timeout and a watchlist poll multiplies that. The breaker trips after a few
# consecutive failures and short-circuits subsequent fetches for a cooldown, so
# a dead provider returns instantly (None) instead of stalling every caller.
# 2026-06-03 — after a Massive REST outage froze the API event loop.
_CB = {"fails": 0, "open_until": 0.0}
_CB_TRIP_AFTER = 3
_CB_COOLDOWN_SEC = 60.0
_FETCH_TIMEOUT_SEC = 6          # was 20 — fail fast; Massive answers in <1s when healthy


def _cb_is_open(now: float) -> bool:
    """True while the breaker is tripped — skip the network call entirely."""
    return now < _CB["open_until"]


def _cb_record(ok: bool, now: float) -> None:
    """Reset on success; trip after `_CB_TRIP_AFTER` consecutive failures."""
    if ok:
        _CB["fails"] = 0
        _CB["open_until"] = 0.0
    else:
        _CB["fails"] += 1
        if _CB["fails"] >= _CB_TRIP_AFTER:
            _CB["open_until"] = now + _CB_COOLDOWN_SEC


def _get_mongo_coll():
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        coll = client[db]["intraday_cache"]
        coll.create_index([("symbol", ASCENDING), ("date", ASCENDING)], unique=True)
        return coll
    except Exception as exc:
        log.warning("mongo unavailable: %s", exc)
        return None


def _classify_session(ts_utc: pd.Timestamp) -> str:
    """Tag a bar as premarket/rth/afterhours based on its ET clock time."""
    et = ts_utc.tz_localize("UTC").tz_convert("America/New_York") if ts_utc.tzinfo is None else ts_utc.tz_convert("America/New_York")
    t = et.time()
    if ET_RTH_OPEN <= t < ET_RTH_CLOSE:
        return "rth"
    if ET_PREMARKET_OPEN <= t < ET_RTH_OPEN:
        return "premarket"
    if ET_RTH_CLOSE <= t < ET_AFTERHOURS_CLOSE:
        return "afterhours"
    return "closed"


def _fetch_massive_minute(symbol: str, from_date: date, to_date: date) -> Optional[pd.DataFrame]:
    """Fetch 1-minute bars from Massive for a date range, inclusive."""
    import requests
    key = stocks_key()
    if not key:
        log.error("MASSIVE_API_KEY missing — cannot fetch intraday bars")
        return None
    if _cb_is_open(time.time()):
        log.debug("massive intraday: circuit open, skipping fetch for %s", symbol)
        return None
    url = f"{BASE_URL}/v2/aggs/ticker/{symbol.upper()}/range/1/minute/{from_date}/{to_date}"
    rows = []
    next_url = url
    next_params = {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": key}
    page = 0
    while next_url:
        try:
            r = requests.get(next_url, params=next_params, timeout=_FETCH_TIMEOUT_SEC)
        except Exception as exc:
            from sepa.prices import _scrub_key
            log.warning("massive intraday fetch failed for %s: %s", symbol, _scrub_key(exc))
            _cb_record(False, time.time())
            return None
        if r.status_code == 429:
            time.sleep(2)
            continue
        if r.status_code != 200:
            log.warning("massive intraday %s -> HTTP %s: %s", symbol, r.status_code, r.text[:200])
            _cb_record(False, time.time())
            return None
        body = r.json() or {}
        rows.extend(body.get("results") or [])
        next_url_field = body.get("next_url")
        # Polygon's next_url already encodes its own params — just append the apiKey.
        if next_url_field:
            next_url = next_url_field
            next_params = {"apiKey": key}
            page += 1
            if page > 20:
                log.warning("intraday paging cutoff at 20 pages for %s", symbol)
                break
        else:
            next_url = None

    _cb_record(True, time.time())     # provider responded 200 — reset the breaker

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df["ts_utc"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_convert(None)
    df = df.set_index("ts_utc")
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "vw": "vwap_bar", "n": "trade_count"})
    keep = [c for c in ["open", "high", "low", "close", "volume", "vwap_bar", "trade_count"] if c in df.columns]
    df = df[keep].sort_index()
    df["session"] = [_classify_session(ts) for ts in df.index]
    return df


def _mongo_get_day(symbol: str, day: date) -> Optional[pd.DataFrame]:
    coll = _get_mongo_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"symbol": symbol.upper(), "date": str(day)})
        if not doc or not doc.get("bars"):
            return None
        df = pd.DataFrame(doc["bars"])
        if "ts_utc" not in df.columns:
            return None
        df["ts_utc"] = pd.to_datetime(df["ts_utc"])
        df = df.set_index("ts_utc")
        return df
    except Exception as exc:
        log.warning("mongo intraday read failed: %s", exc)
        return None


def _mongo_put_day(symbol: str, day: date, df: pd.DataFrame) -> None:
    coll = _get_mongo_coll()
    if coll is None:
        return
    try:
        bars = df.reset_index().to_dict(orient="records")
        # Stringify timestamps for portability
        for b in bars:
            if "ts_utc" in b:
                b["ts_utc"] = b["ts_utc"].isoformat() if hasattr(b["ts_utc"], "isoformat") else str(b["ts_utc"])
        coll.update_one(
            {"symbol": symbol.upper(), "date": str(day)},
            {"$set": {"symbol": symbol.upper(), "date": str(day), "bars": bars,
                      "cached_at": datetime.utcnow()}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("mongo intraday write failed: %s", exc)


def load_intraday(symbol: str, day: date, force: bool = False,
                  include_premarket: bool = True,
                  include_afterhours: bool = False) -> Optional[pd.DataFrame]:
    """Load 1-min bars for a single trading day. Returns None if no bars.

    Cache rule: completed days are cached forever. Today's bars are always
    re-fetched (force=True is implied for `day == today`).
    """
    today = datetime.utcnow().date()
    is_today = day == today

    if not force and not is_today:
        cached = _mongo_get_day(symbol, day)
        if cached is not None and not cached.empty:
            return _filter_sessions(cached, include_premarket, include_afterhours)

    df = _fetch_massive_minute(symbol, day, day)
    if df is None or df.empty:
        return None

    if not is_today:
        _mongo_put_day(symbol, day, df)
    return _filter_sessions(df, include_premarket, include_afterhours)


def _filter_sessions(df: pd.DataFrame, include_premarket: bool, include_afterhours: bool) -> pd.DataFrame:
    keep_sessions = ["rth"]
    if include_premarket:
        keep_sessions.append("premarket")
    if include_afterhours:
        keep_sessions.append("afterhours")
    if "session" not in df.columns:
        return df
    return df[df["session"].isin(keep_sessions)]


def load_intraday_range(symbol: str, from_day: date, to_day: date,
                        include_premarket: bool = True,
                        include_afterhours: bool = False) -> Optional[pd.DataFrame]:
    """Load 1-min bars over a range of trading days (inclusive)."""
    parts = []
    cur = from_day
    while cur <= to_day:
        # Skip weekends
        if cur.weekday() < 5:
            df = load_intraday(symbol, cur,
                               include_premarket=include_premarket,
                               include_afterhours=include_afterhours)
            if df is not None and not df.empty:
                parts.append(df)
        cur += timedelta(days=1)
    if not parts:
        return None
    return pd.concat(parts).sort_index()


def trading_days_back(n: int, end: Optional[date] = None) -> list[date]:
    """Last n weekday dates ending on `end` (default = yesterday)."""
    if end is None:
        end = (datetime.utcnow() - timedelta(days=1)).date()
    out = []
    cur = end
    while len(out) < n:
        if cur.weekday() < 5:
            out.append(cur)
        cur -= timedelta(days=1)
    return list(reversed(out))
