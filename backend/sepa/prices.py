"""Daily OHLCV loader with parquet cache.

Caches under ~/.cheetah/prices/<SYMBOL>.parquet. A fresh fetch is triggered if
the cache is older than 20 hours or missing entirely.

Provider is selected by PRICE_PROVIDER env var:
  - "massive"  (default) — Massive.com REST API. Requires MASSIVE_API_KEY.
  - "yfinance"           — yfinance fallback. No key required.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger("sepa.prices")

CACHE_DIR = Path.home() / ".cheetah" / "prices"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SEC = 20 * 3600

PERIOD_DAYS = {"1y": 365, "2y": 730, "3y": 1095, "5y": 1825, "max": 3650}


def _cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol.upper()}.parquet"


def _fetch_yfinance(symbol: str, period: str) -> Optional[pd.DataFrame]:
    import yfinance as yf
    try:
        df = yf.Ticker(symbol).history(period=period, auto_adjust=False)
    except Exception as exc:
        log.warning("yfinance fetch failed for %s: %s", symbol, exc)
        return None
    if df is None or df.empty:
        return None
    return df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]


def _fetch_massive(symbol: str, period: str) -> Optional[pd.DataFrame]:
    import requests
    key = os.getenv("MASSIVE_API_KEY")
    if not key:
        log.warning("MASSIVE_API_KEY not set — cannot fetch %s from Massive", symbol)
        return None

    days = PERIOD_DAYS.get(period, 730)
    to_date = pd.Timestamp.utcnow().normalize()
    from_date = to_date - pd.Timedelta(days=days)
    url = (
        f"https://api.massive.com/v2/aggs/ticker/{symbol.upper()}"
        f"/range/1/day/{from_date.date()}/{to_date.date()}"
    )
    try:
        r = requests.get(
            url,
            params={"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": key},
            timeout=15,
        )
        if r.status_code == 429:
            log.warning("massive rate-limited on %s", symbol)
            time.sleep(2)
            r = requests.get(
                url,
                params={"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": key},
                timeout=15,
            )
        if r.status_code != 200:
            log.warning("massive %s -> HTTP %s: %s", symbol, r.status_code, r.text[:200])
            return None
        results = (r.json() or {}).get("results") or []
    except Exception as exc:
        log.warning("massive fetch failed for %s: %s", symbol, exc)
        return None

    if not results:
        return None

    df = pd.DataFrame(results)
    df["date"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_convert(None)
    df = df.set_index("date")
    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    return df[["open", "high", "low", "close", "volume"]]


def _fetch(symbol: str, period: str) -> Optional[pd.DataFrame]:
    provider = os.getenv("PRICE_PROVIDER", "massive").lower()
    if provider == "massive":
        df = _fetch_massive(symbol, period)
        if df is not None:
            return df
        log.info("massive returned nothing for %s — falling back to yfinance", symbol)
        return _fetch_yfinance(symbol, period)
    return _fetch_yfinance(symbol, period)


def load_prices(symbol: str, period: str = "2y", force: bool = False) -> Optional[pd.DataFrame]:
    """Return a DataFrame indexed by date with columns [open, high, low, close, volume].

    Returns None on failure (delisted ticker, no data, etc.)."""
    path = _cache_path(symbol)
    fresh = path.exists() and (time.time() - path.stat().st_mtime) < CACHE_TTL_SEC
    if fresh and not force:
        try:
            return pd.read_parquet(path)
        except Exception as exc:
            log.warning("parquet cache read failed for %s: %s", symbol, exc)

    df = _fetch(symbol, period)
    if df is None or df.empty:
        return None

    try:
        df.to_parquet(path)
    except Exception as exc:
        log.warning("parquet cache write failed for %s: %s", symbol, exc)
    return df
