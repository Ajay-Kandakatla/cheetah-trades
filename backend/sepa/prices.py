"""Daily OHLCV loader with Mongo-backed cache (parquet fallback).

Cache layers, in order of preference:
  1. MongoDB collection `price_cache` — one document per symbol with the full
     bar series. Survives container restarts and is shared across the api +
     cron services. Refreshed when older than 20 hours.
  2. Local parquet under ~/.cheetah/prices/<SYMBOL>.parquet — fallback when
     Mongo is unreachable.

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


# ---------------------------------------------------------------------------
# Mongo cache (primary)
# ---------------------------------------------------------------------------
_mongo_coll = None
_mongo_disabled = False


def _get_mongo():
    """Return the price_cache collection or None if Mongo is unavailable."""
    global _mongo_coll, _mongo_disabled
    if _mongo_disabled:
        return None
    if _mongo_coll is not None:
        return _mongo_coll
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        coll = client[db_name].price_cache
        coll.create_index([("symbol", ASCENDING)], unique=True)
        _mongo_coll = coll
        log.info("price cache: connected to %s/%s.price_cache", url, db_name)
        return _mongo_coll
    except Exception as exc:
        log.warning("price cache: Mongo unavailable (%s) — falling back to parquet", exc)
        _mongo_disabled = True
        return None


def _mongo_get(symbol: str) -> Optional[pd.DataFrame]:
    coll = _get_mongo()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"symbol": symbol.upper()})
        if not doc:
            return None
        if (time.time() - (doc.get("cached_at") or 0)) >= CACHE_TTL_SEC:
            return None
        bars = doc.get("bars") or []
        if not bars:
            return None
        df = pd.DataFrame(bars)
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date")[["open", "high", "low", "close", "volume"]]
    except Exception as exc:
        log.warning("mongo cache read failed for %s: %s", symbol, exc)
        return None


def _mongo_put(symbol: str, df: pd.DataFrame) -> None:
    coll = _get_mongo()
    if coll is None:
        return
    try:
        bars = [
            {
                "date": idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            for idx, row in df.iterrows()
        ]
        coll.update_one(
            {"symbol": symbol.upper()},
            {"$set": {"symbol": symbol.upper(), "bars": bars, "cached_at": int(time.time())}},
            upsert=True,
        )
    except Exception as exc:
        log.warning("mongo cache write failed for %s: %s", symbol, exc)


# ---------------------------------------------------------------------------
# Parquet cache (fallback)
# ---------------------------------------------------------------------------
def _cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol.upper()}.parquet"


def _parquet_get(symbol: str) -> Optional[pd.DataFrame]:
    path = _cache_path(symbol)
    if not path.exists():
        return None
    if (time.time() - path.stat().st_mtime) >= CACHE_TTL_SEC:
        return None
    try:
        return pd.read_parquet(path)
    except Exception as exc:
        log.warning("parquet cache read failed for %s: %s", symbol, exc)
        return None


def _parquet_put(symbol: str, df: pd.DataFrame) -> None:
    try:
        df.to_parquet(_cache_path(symbol))
    except Exception as exc:
        log.warning("parquet cache write failed for %s: %s", symbol, exc)


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------
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


def last_trade_price(symbol: str) -> Optional[float]:
    """Real-time last trade price from Massive (Developer tier).

    Falls back to the most recent daily close if the live endpoint fails.
    Used by the alerts checker so stop-loss decisions use live prices."""
    import requests
    key = os.getenv("MASSIVE_API_KEY")
    if key:
        try:
            r = requests.get(
                f"https://api.massive.com/v2/last/trade/{symbol.upper()}",
                params={"apiKey": key},
                timeout=5,
            )
            if r.status_code == 200:
                results = (r.json() or {}).get("results") or {}
                price = results.get("p") or results.get("price")
                if price:
                    return float(price)
            else:
                log.warning("massive last-trade %s -> HTTP %s", symbol, r.status_code)
        except Exception as exc:
            log.warning("massive last-trade fetch failed for %s: %s", symbol, exc)
    df = load_prices(symbol)
    if df is not None and not df.empty:
        return float(df["close"].iloc[-1])
    return None


def _fetch(symbol: str, period: str) -> Optional[pd.DataFrame]:
    provider = os.getenv("PRICE_PROVIDER", "massive").lower()
    if provider == "massive":
        df = _fetch_massive(symbol, period)
        if df is not None:
            return df
        log.info("massive returned nothing for %s — falling back to yfinance", symbol)
        return _fetch_yfinance(symbol, period)
    return _fetch_yfinance(symbol, period)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def load_prices(symbol: str, period: str = "2y", force: bool = False) -> Optional[pd.DataFrame]:
    """Return a DataFrame indexed by date with [open, high, low, close, volume].

    Cache order: Mongo → parquet → fetch. None on failure (delisted, no data)."""
    if not force:
        df = _mongo_get(symbol)
        if df is not None:
            return df
        df = _parquet_get(symbol)
        if df is not None:
            # Backfill Mongo so subsequent reads stay there
            _mongo_put(symbol, df)
            return df

    df = _fetch(symbol, period)
    if df is None or df.empty:
        return None

    _mongo_put(symbol, df)
    _parquet_put(symbol, df)
    return df
