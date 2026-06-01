"""Short volume Massive client + Mongo cache.

Public API:
    short_volume_for(symbol)        → latest single-day snapshot dict | None
    short_volume_history(symbol, n) → list of last `n` daily records
    latest_short_pct(symbol)        → float | None  (just the % for quick chip lookup)

Cache strategy:
    * Mongo collection `short_volume_cache` keyed on (symbol, date).
    * Each upsert keeps the full FINRA record (all 15 fields per the
      Massive /stocks/v1/short-volume schema). We never delete rows so
      we accumulate a time-series usable for trend analysis.
    * A summary record per symbol caches the latest snapshot for fast
      "single chip lookup" reads (collection `short_volume_latest`).

The fetch loop pulls the last 30 days of data per request — enough for
the 20-day moving average we use to spot short-spike vs steady-state
short positioning. If a symbol is queried on a market day and we already
have today's record cached, we skip the HTTP call.
"""
from __future__ import annotations

import logging
import os
from massive_keys import stocks_key
from datetime import date, datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("short_interest.client")


# ---------- Mongo cache helpers ------------------------------------------------

# Module-level connection handle. Mirrors the pattern used by options/soir.py
# and other backend modules — each owns its own MongoClient + creates the
# indexes it cares about on first call.
_db = None


def _get_db():
    """Lazy Mongo handle. Returns None if Mongo is unreachable (dev mode)."""
    global _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING, DESCENDING
        client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                              serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        # Time-series of daily short volume — one row per (symbol, date).
        _db.short_volume_cache.create_index(
            [("symbol", ASCENDING), ("date", DESCENDING)], unique=True,
        )
        # Latest snapshot per symbol — fast read path for chip rendering.
        _db.short_volume_latest.create_index("symbol", unique=True)
        return _db
    except Exception as exc:
        log.warning("short_interest: Mongo unavailable: %s", exc)
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _today_iso() -> str:
    return _now_utc().date().isoformat()


def _cached_latest(symbol: str) -> Optional[dict]:
    """Read the latest cached snapshot for `symbol`. Returns None if the
    cache is empty OR the cached value is older than 24h."""
    db = _get_db()
    if db is None:
        return None
    try:
        rec = db.short_volume_latest.find_one({"symbol": symbol.upper()}, {"_id": 0})
        if not rec:
            return None
        cached_at = rec.get("cached_at")
        if not cached_at:
            return None
        # The FINRA feed updates daily. A cached snapshot is fresh enough
        # if it was fetched within the last 24h.
        if isinstance(cached_at, str):
            cached_at = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
        if (_now_utc() - cached_at).total_seconds() > 86_400:
            return None
        return rec.get("snapshot")
    except Exception as exc:
        log.warning("short_interest: cache read failed for %s: %s", symbol, exc)
        return None


def _persist_records(symbol: str, records: list[dict]) -> None:
    """Upsert each record into short_volume_cache. Update short_volume_latest
    with the newest record so single-chip lookups are O(1)."""
    db = _get_db()
    if db is None or not records:
        return
    try:
        # Upsert per (symbol, date) so we accumulate a time-series.
        for r in records:
            db.short_volume_cache.update_one(
                {"symbol": symbol.upper(), "date": r["date"]},
                {"$set": {**r, "symbol": symbol.upper()}},
                upsert=True,
            )
        # Latest pointer for fast reads
        newest = max(records, key=lambda x: x["date"])
        db.short_volume_latest.update_one(
            {"symbol": symbol.upper()},
            {"$set": {
                "symbol": symbol.upper(),
                "snapshot": newest,
                "cached_at": _now_utc().isoformat(),
            }},
            upsert=True,
        )
    except Exception as exc:
        log.warning("short_interest: persist failed for %s: %s", symbol, exc)


# ---------- Massive fetcher ----------------------------------------------------

# Process-level lazy-disable. If the endpoint returns 401/403 (plan
# downgrade, key rotation), skip subsequent calls in this run.
_short_volume_disabled = False


def _fetch_from_massive(symbol: str, days_back: int = 30) -> list[dict]:
    """Hit /stocks/v1/short-volume for the last N days.

    Returns list of records (may be empty if no FINRA data for this symbol
    or if the plan doesn't include short-volume). Each record matches the
    Massive schema exactly — caller pulls the fields it needs.
    """
    global _short_volume_disabled
    if _short_volume_disabled:
        return []
    api_key = stocks_key()
    if not api_key:
        return []

    try:
        import requests
    except ImportError:
        log.warning("short_interest: requests not installed")
        return []

    since = (_now_utc().date() - timedelta(days=days_back)).isoformat()
    url = "https://api.massive.com/stocks/v1/short-volume"
    params = {
        "ticker":  symbol.upper(),
        "date.gte": since,
        "limit":   max(days_back, 30),
        "order":   "desc",
        "sort":    "date",
        "apiKey":  api_key,
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code in (401, 403):
            if not _short_volume_disabled:
                log.warning(
                    "short_interest: Massive returned %s for %s — plan doesn't "
                    "include short-volume. Disabling for this run.",
                    r.status_code, symbol,
                )
                _short_volume_disabled = True
            return []
        if r.status_code == 429:
            log.warning("short_interest: rate-limited on %s", symbol)
            return []
        if r.status_code != 200:
            log.debug("short_interest: %s returned HTTP %s", symbol, r.status_code)
            return []
        body = r.json() or {}
        return body.get("results") or []
    except Exception as exc:
        log.warning("short_interest: fetch failed for %s: %s", symbol, exc)
        return []


# ---------- Public API ---------------------------------------------------------

def short_volume_for(symbol: str, *, force_refresh: bool = False) -> Optional[dict]:
    """Latest single-day short volume snapshot for `symbol`.

    Returns dict with keys:
        date              (str ISO)
        ticker            (str)
        short_volume      (float)
        total_volume      (float)
        short_volume_ratio (float, 0-100)
        exempt_volume     (float)  — market-maker hedge shorts
        non_exempt_volume (float)  — directional short bets
        ... plus venue-level breakdown

    Returns None when:
        - Massive plan doesn't include short volume (silently disabled)
        - No FINRA data for this symbol (ADRs, foreign listings)
        - Network failure (caller should treat None as "no signal")
    """
    if not force_refresh:
        cached = _cached_latest(symbol)
        if cached:
            return cached

    records = _fetch_from_massive(symbol)
    if not records:
        return None

    _persist_records(symbol, records)
    return max(records, key=lambda x: x["date"])


def short_volume_history(symbol: str, days: int = 30) -> list[dict]:
    """Last `days` days of short volume records, newest first.

    Hits Mongo cache first; only fetches from Massive if the cache is
    older than 24h. Useful for trend analysis (rising short% on
    advancing stock = squeeze setup).
    """
    db = _get_db()
    if db is not None:
        try:
            cursor = (db.short_volume_cache
                        .find({"symbol": symbol.upper()}, {"_id": 0})
                        .sort("date", -1)
                        .limit(days))
            cached = list(cursor)
            # If we have at least `days * 0.5` records AND the newest is
            # less than 24h old, return cache without a fresh fetch.
            if cached and len(cached) >= max(days // 2, 5):
                newest_date = max(c["date"] for c in cached)
                age_days = (date.today() - date.fromisoformat(newest_date)).days
                if age_days <= 2:  # weekend tolerance
                    return cached
        except Exception as exc:
            log.warning("short_interest: history cache read failed: %s", exc)

    records = _fetch_from_massive(symbol, days_back=days)
    if records:
        _persist_records(symbol, records)
    return sorted(records, key=lambda x: x["date"], reverse=True)[:days]


def latest_short_pct(symbol: str) -> Optional[float]:
    """Just the latest short_volume_ratio (0-100). Fast path for chip rendering."""
    snap = short_volume_for(symbol)
    if not snap:
        return None
    return snap.get("short_volume_ratio")
