"""FRED (Federal Reserve Economic Data) reader — the Market Gauge's Economic source.

Wires the free St. Louis Fed FRED API (https://fred.stlouisfed.org/docs/api/fred/)
so the Market Gauge's Economic category reads REAL macro series instead of
flagging them unwired:

    CPIAUCSL  — CPI, All Urban Consumers, All Items (monthly index) → YoY inflation
    UNRATE    — Civilian Unemployment Rate (monthly, %)
    FEDFUNDS  — Federal Funds Effective Rate (monthly avg, %)
    T10Y3M    — 10-Year minus 3-Month Treasury, constant maturity (daily, %)
                FRED publishes the SPREAD directly (the recession curve)

SOURCE CITATION (Rule #1/#4): every series is cited by its FRED series id in the
pillar `basis`. The numbers that turn a series into a 0–1 health score
(`market_gauge`'s CPI/UNEMP/FF/CURVE constants) are CONFIGURED / standard-macro —
the Fed's ~2% inflation target, the Sahm-rule rising-unemployment recession
signal, policy tightening-vs-easing, curve inversion. They are NOT from any book
we hold (Minervini's book covers index price action, not a weighted macro gauge),
so they are labelled CONFIGURED and locked by the source-guard test, exactly like
the gauge's O'Neil-style distribution-day / follow-through numbers.

KEY: read from the `FRED_API_KEY` env var — NEVER hardcoded. Get a free key at
https://fredaccount.stlouisfed.org/apikeys and put it in `backend/.env`. With no
key the helpers return None and the Economic pillars degrade to neutral (honest,
not faked) — they never invent a number.

CACHE: FRED series update slowly (monthly releases / once-daily curve), so each
series is cached in-process for 24h — at most one HTTP call per series per day.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

log = logging.getLogger("sepa.fred")

# FRED series/observations endpoint (returns a series' data points).
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

_DEFAULT_LIMIT = 24          # 2 years of a monthly series / ~5 weeks of a daily one
_TTL_SEC = 86_400           # 24h — FRED series update daily at most
_TIMEOUT = 10

# series-id -> (fetched_at_epoch, [(date_str, value_float), ...] newest-first)
_CACHE: dict = {}

# Process-level lazy-disable on auth failure (absent/bad key) — mirrors the
# short_interest Massive client so a dead key doesn't spam the log every call.
_disabled = False


def api_key() -> str:
    return os.getenv("FRED_API_KEY", "").strip()


def available() -> bool:
    """True when a FRED key is configured and we haven't hit an auth failure."""
    return bool(api_key()) and not _disabled


def _parse_observations(payload: dict) -> list:
    """PURE: FRED observations JSON → [(date, value)] newest-first, with missing
    values ('.') dropped. Sorted by date desc so callers index by age."""
    obs = (payload or {}).get("observations") or []
    out = []
    for o in obs:
        v = o.get("value")
        d = o.get("date")
        if v in (None, ".", "") or d is None:        # FRED encodes "missing" as "."
            continue
        try:
            out.append((d, float(v)))
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda x: x[0], reverse=True)
    return out


def _fetch(series_id: str, limit: int = _DEFAULT_LIMIT) -> list:
    """Cached (24h) [(date, value)] newest-first for `series_id`. Returns an
    empty list on ANY failure (no key, network, bad series) — callers treat an
    empty list as "no data" and degrade to neutral."""
    global _disabled
    now = time.time()
    hit = _CACHE.get(series_id)
    if hit and (now - hit[0]) < _TTL_SEC:
        return hit[1]
    key = api_key()
    if not key or _disabled:
        return []
    try:
        import requests
    except ImportError:
        log.warning("fred: requests not installed")
        return []
    try:
        r = requests.get(
            FRED_BASE,
            params={"series_id": series_id, "api_key": key, "file_type": "json",
                    "sort_order": "desc", "limit": limit},
            timeout=_TIMEOUT,
        )
        if r.status_code in (400, 401, 403):
            # FRED returns 400 (not 401) for a bad/absent key. Disable for the
            # rest of this run so we don't hammer it on every pillar.
            log.warning("fred: HTTP %s for %s — check FRED_API_KEY. "
                        "Disabling FRED for this run.", r.status_code, series_id)
            _disabled = True
            return []
        if r.status_code == 429:
            log.warning("fred: rate-limited on %s", series_id)
            return []
        if r.status_code != 200:
            log.debug("fred: %s returned HTTP %s", series_id, r.status_code)
            return []
        data = _parse_observations(r.json() or {})
        if data:
            _CACHE[series_id] = (now, data)
        return data
    except Exception as exc:
        log.warning("fred: fetch failed for %s: %s", series_id, exc)
        return []


# ── derived reads used by the gauge's Economic pillars ───────────────────────
def latest(series_id: str) -> Optional[float]:
    """Most recent numeric observation, or None."""
    data = _fetch(series_id)
    return data[0][1] if data else None


def latest_with_date(series_id: str) -> Optional[tuple]:
    """(date, value) of the most recent observation, or None."""
    data = _fetch(series_id)
    return data[0] if data else None


def value_periods_ago(series_id: str, periods: int) -> Optional[float]:
    """Value `periods` observations before the latest (for a MONTHLY series,
    periods == months). None if the history is too short."""
    data = _fetch(series_id)
    if not data or len(data) <= periods:
        return None
    return data[periods][1]


def yoy(series_id: str) -> Optional[float]:
    """Year-over-year % change of a MONTHLY index/level series (12 obs back)."""
    data = _fetch(series_id)
    if not data or len(data) <= 12:
        return None
    now, prior = data[0][1], data[12][1]
    if not prior:
        return None
    return round((now / prior - 1.0) * 100.0, 2)


def change(series_id: str, periods: int) -> Optional[float]:
    """Latest minus value `periods` observations ago (a level change — e.g. pp
    for a rate). None if the history is too short."""
    now = latest(series_id)
    prior = value_periods_ago(series_id, periods)
    if now is None or prior is None:
        return None
    return round(now - prior, 2)
