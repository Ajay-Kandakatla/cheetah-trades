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
from massive_keys import stocks_key
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
    key = stocks_key()
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
    df = df[["open", "high", "low", "close", "volume"]]
    # Defensive: drop any rows where close/open/volume is zero. Massive's
    # daily aggs endpoint occasionally emits placeholder bars on the
    # current day during holidays (e.g. Memorial Day) with all zeros.
    # These corrupt RS rank and Stage classification downstream — drop them
    # at the source so they never reach the price cache.
    pre_n = len(df)
    df = df[(df["close"] > 0) & (df["open"] > 0) & (df["volume"] > 0)]
    if len(df) < pre_n:
        log.info("massive %s: dropped %d zero-priced bars", symbol, pre_n - len(df))
    return df


def last_trade_price(symbol: str) -> Optional[float]:
    """Real-time last trade price from Massive (Developer tier).

    Falls back to the most recent daily close if the live endpoint fails.
    Used by the alerts checker so stop-loss decisions use live prices."""
    import requests
    key = stocks_key()
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
def _drop_phantom_tail(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Drop a trailing phantom bar that exactly duplicates the prior session.

    A pre-session bulk snapshot can echo the previous day's completed aggregate
    into a bar stamped with *today's* date, leaving two adjacent bars with
    byte-identical close AND volume. Two real daily sessions never share volume
    to the exact share, so an identical (close, volume) tail is a placeholder,
    not a session. Left in place it makes the breakout test
    ``last_close > recent_high`` impossible (the duplicate close already sits
    inside ``recent_high``), which zeros ``high_vol_breakout`` for the entire
    universe and collapses ``is_buyable`` (book pp.198-203). Read-time guard so
    the existing cache self-heals on the next scan without a repair pass — and
    so the stored bar survives to be overwritten in place when the real session
    prints. Conservative: drops at most one trailing bar, only on an exact match.
    """
    if df is None or len(df) < 2:
        return df
    try:
        last, prev = df.iloc[-1], df.iloc[-2]
        if (
            float(last["close"]) == float(prev["close"])
            and float(last["volume"]) == float(prev["volume"])
        ):
            return df.iloc[:-1]
    except (KeyError, ValueError, TypeError):
        pass
    return df


# A symbol whose newest daily bar is older than this many CALENDAR days is
# treated as delisted / halted / renamed (no live data) and excluded from the
# scan. ~10 trading days; the gap between an active name (last bar 0-3 days old)
# and a delisted one (months) is huge, so this sits comfortably clear of
# weekend / holiday / transient-patch-gap noise.
STALE_MAX_CALENDAR_DAYS = 14


def is_stale(
    df: Optional[pd.DataFrame],
    asof: Optional[pd.Timestamp] = None,
    max_days: int = STALE_MAX_CALENDAR_DAYS,
) -> bool:
    """True when the newest bar is older than ``max_days`` calendar days — the
    symbol has stopped printing daily bars (delisted, halted, renamed, or a
    persistent data gap). Such a name has no live price and no chart, and must
    not surface in the scan or the buyable tier: a frozen last bar can read as a
    pocket pivot / breakout and leak into is_buyable (see CFLT, last bar
    2026-03-16 — an M&A volume spike that scored buyable months after delisting).
    ``asof`` defaults to today (ET). Conservative: returns False on any error so
    a parsing hiccup never silently empties the scan."""
    if df is None or len(df) == 0:
        return True
    try:
        last_ts = pd.Timestamp(df.index[-1])
        if asof is None:
            asof = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
        else:
            asof = pd.Timestamp(asof)
        return (asof - last_ts).days > max_days
    except Exception:
        return False


def load_prices(symbol: str, period: str = "2y", force: bool = False) -> Optional[pd.DataFrame]:
    """Return a DataFrame indexed by date with [open, high, low, close, volume].

    Cache order: Mongo → parquet → fetch. None on failure (delisted, no data).
    A trailing phantom-duplicate bar is stripped at read time (see
    ``_drop_phantom_tail``) so detectors never see a placeholder last session."""
    if not force:
        df = _mongo_get(symbol)
        if df is not None:
            return _drop_phantom_tail(df)
        df = _parquet_get(symbol)
        if df is not None:
            # Backfill Mongo so subsequent reads stay there
            _mongo_put(symbol, df)
            return _drop_phantom_tail(df)

    df = _fetch(symbol, period)
    if df is None or df.empty:
        return None

    _mongo_put(symbol, df)
    _parquet_put(symbol, df)
    return _drop_phantom_tail(df)


# ---------------------------------------------------------------------------
# Real-time upgrades — bulk snapshot (2026-05-25)
# ---------------------------------------------------------------------------

_SNAP_CHUNK = 250  # Massive allows up to 250 tickers per snapshot call


def bulk_snapshot(symbols: list[str]) -> dict[str, dict]:
    """Fetch today's OHLCV snapshot for up to N tickers in one Massive call.

    Massive endpoint: GET /v2/snapshot/locale/us/markets/stocks/tickers
    Returns {SYMBOL: {open, high, low, close, volume, vwap, date, change_pct}}
    Missing or errored symbols are simply absent from the dict.
    """
    key = stocks_key()
    if not key:
        return {}
    try:
        import requests as _req
    except ImportError:
        return {}

    result: dict[str, dict] = {}
    chunks = [symbols[i : i + _SNAP_CHUNK] for i in range(0, len(symbols), _SNAP_CHUNK)]
    for chunk in chunks:
        try:
            r = _req.get(
                "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers",
                params={"tickers": ",".join(s.upper() for s in chunk), "apiKey": key},
                timeout=15,
            )
            if r.status_code != 200:
                log.warning("bulk_snapshot: HTTP %s for chunk of %d", r.status_code, len(chunk))
                continue
            for item in (r.json() or {}).get("tickers") or []:
                sym = (item.get("ticker") or "").upper()
                if not sym:
                    continue
                day = item.get("day") or {}
                # Use the start-of-day timestamp from `day.t`; fall back to today-ET.
                # IMPORTANT (2026-05-27): normalize in US/Eastern, not UTC.
                # Calling .normalize() directly on a UTC Timestamp truncates to
                # midnight UTC, which rolls over to "tomorrow" any time after
                # 8 PM ET (= midnight UTC). That bug appended future-dated bars
                # every evening and silently broke VCP / Kell detectors that
                # read the tail of the series. Convert to America/New_York
                # before normalizing so a bar timestamped at any point during
                # the May 27 ET session always stores as 2026-05-27.
                day_t = day.get("t")
                if day_t:
                    bar_date = (
                        pd.Timestamp(day_t, unit="ms", tz="UTC")
                        .tz_convert("America/New_York")
                        .normalize()
                        .tz_localize(None)
                    )
                else:
                    bar_date = (
                        pd.Timestamp.now(tz="America/New_York")
                        .normalize()
                        .tz_localize(None)
                    )
                # Extended-hours surface (2026-05-26): expose lastTrade +
                # prevDay so the frontend can render pre-market / after-hours
                # prints with a session badge. Display-only — SEPA scoring
                # still uses `close` (the regular-session close).
                last_trade = item.get("lastTrade") or {}
                prev_day = item.get("prevDay") or {}
                result[sym] = {
                    "open":             day.get("o"),
                    "high":             day.get("h"),
                    "low":              day.get("l"),
                    "close":            day.get("c"),
                    "volume":           day.get("v"),
                    "vwap":             day.get("vw"),
                    "date":             bar_date,
                    "change_pct":       item.get("todaysChangePerc"),
                    # Extended-hours fields (additive — never read by SEPA scorer)
                    "last_trade_price": last_trade.get("p"),
                    "last_trade_ts_ms": last_trade.get("t"),
                    "prev_day_close":   prev_day.get("c"),
                    "todays_change":    item.get("todaysChange"),
                }
        except Exception as exc:
            log.warning("bulk_snapshot: chunk failed: %s", exc)

    log.info("bulk_snapshot: fetched %d/%d symbols", len(result), len(symbols))
    return result


def patch_latest_closes(symbols: list[str]) -> dict:
    """Append today's close to every already-cached symbol using bulk snapshot.

    Instead of re-downloading 2 years of history when the 20h TTL expires,
    we grab just the latest bar for every ticker in one bulk API call and
    append it to the existing Mongo-cached series. The TTL is also reset so
    the scan workers see a fresh cache hit and skip the full re-fetch.

    Symbols not yet cached are left alone — the scan worker will do a full
    history fetch for them as usual.

    Returns stats dict: {patched, already_current, no_cache, total_snapshot}
    """
    snaps = bulk_snapshot(symbols)
    if not snaps:
        return {"patched": 0, "already_current": 0, "no_cache": 0, "total_snapshot": 0}

    coll = _get_mongo()
    patched = already_current = no_cache = phantom_skipped = 0

    for sym, bar in snaps.items():
        # Skip bars with any missing or zero price field (0 = no session today,
        # i.e. weekend/holiday response from Massive).
        if any(not bar.get(k) for k in ("open", "high", "low", "close", "volume")):
            continue
        bar_date: pd.Timestamp = bar["date"]
        if bar_date is None:
            continue
        bar_iso = bar_date.date().isoformat()

        # Safety net (2026-05-27): refuse to store bars dated in the future.
        # With the TZ fix in bulk_snapshot() above this should be impossible,
        # but the guard makes a regression in date handling fail loud instead
        # of silently corrupting the cache.
        et_today_iso = (
            pd.Timestamp.now(tz="America/New_York").normalize().date().isoformat()
        )
        if bar_iso > et_today_iso:
            log.warning(
                "patch_latest_closes: refusing future-dated bar for %s (%s > %s)",
                sym, bar_iso, et_today_iso,
            )
            continue

        # Reject WEEKEND-dated bars (2026-05-31). On a Saturday/Sunday run,
        # Massive returns the last (Friday) session's OHLCV, but when `day.t`
        # is absent the date falls back to "today" — so it appends a phantom
        # weekend bar: a near-duplicate of Friday with a drifted volume. The
        # future-date guard above misses it (Sat bar dated today-is-Sat is not
        # "future"). That phantom bar shifts every symbol's 25-bar volume
        # window by one and flips borderline distribution calls (e.g. BB
        # sitting on the 3/4 distribution-day threshold → wrong S2/S3). Real
        # daily bars only ever fall Mon–Fri.
        if bar_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            log.warning(
                "patch_latest_closes: skipping weekend-dated bar for %s (%s, weekday %d)",
                sym, bar_iso, bar_date.weekday(),
            )
            continue

        # Load just the tail of the stored series (last 5 rows is enough to
        # check whether today is already present).
        doc = None
        if coll is not None:
            try:
                doc = coll.find_one({"symbol": sym}, {"bars": {"$slice": -5}, "cached_at": 1})
            except Exception:
                pass

        if not doc or not doc.get("bars"):
            no_cache += 1
            continue

        # Check if today is already in the tail
        def _bar_iso(b: dict) -> str:
            d = b.get("date")
            if d is None:
                return ""
            if hasattr(d, "date"):
                return d.date().isoformat()
            return str(d)[:10]

        if any(_bar_iso(b) == bar_iso for b in doc["bars"]):
            # Today's bar already exists — OVERWRITE its OHLCV with the
            # latest snapshot (2026-05-27 fix). Pre-fix behavior was to
            # bump the TTL and skip the update, which meant a 9 AM
            # partial / pre-market snapshot got frozen as the "daily"
            # bar and was never updated to end-of-day values. That
            # corrupted volume + range for the trailing bar, breaking
            # VCP's tight_right_side check + vol_drying ratio. Now we
            # rewrite the bar in place so subsequent calls (cron at 16:30
            # ET, on-demand scans, etc.) always settle to the latest
            # Massive snapshot.
            if coll is not None:
                try:
                    updated_bar = {
                        "date":   bar_date.to_pydatetime(),
                        "open":   float(bar["open"]),
                        "high":   float(bar["high"]),
                        "low":    float(bar["low"]),
                        "close":  float(bar["close"]),
                        "volume": float(bar["volume"]),
                    }
                    coll.update_one(
                        {"symbol": sym, "bars.date": bar_date.to_pydatetime()},
                        {"$set": {
                            "bars.$":    updated_bar,
                            "cached_at": int(time.time()),
                        }},
                    )
                except Exception as exc:
                    log.warning("patch_latest_closes: %s overwrite failed: %s", sym, exc)
            already_current += 1
            continue

        # Phantom-rollover guard (2026-06-02): before the regular session
        # prints, the bulk snapshot can echo the PREVIOUS day's completed
        # aggregate but stamp it with today's date (day.t missing -> falls
        # back to now-ET). Appending it creates two adjacent bars with
        # byte-identical close AND volume. Two real sessions never share
        # volume to the exact share, and the duplicate close makes the
        # breakout test `last_close > recent_high` impossible (the dup close
        # already sits inside recent_high), which zeros high_vol_breakout
        # across the WHOLE universe and collapses is_buyable to ~0. Skip the
        # phantom; the real bar lands via the overwrite-in-place branch above
        # once the session actually trades.
        prev_stored = doc["bars"][-1]
        if (
            float(bar["close"]) == float(prev_stored.get("close", -1.0))
            and float(bar["volume"]) == float(prev_stored.get("volume", -1.0))
        ):
            log.info(
                "patch_latest_closes: skip phantom dup bar for %s "
                "(close=%.4f vol=%.0f duplicates prior session)",
                sym, float(bar["close"]), float(bar["volume"]),
            )
            phantom_skipped += 1
            continue

        # Append the new bar and reset TTL
        new_bar = {
            "date":   bar_date.to_pydatetime(),
            "open":   float(bar["open"]),
            "high":   float(bar["high"]),
            "low":    float(bar["low"]),
            "close":  float(bar["close"]),
            "volume": float(bar["volume"]),
        }
        if coll is not None:
            try:
                coll.update_one(
                    {"symbol": sym},
                    {"$push": {"bars": new_bar}, "$set": {"cached_at": int(time.time())}},
                )
                patched += 1
            except Exception as exc:
                log.warning("patch_latest_closes: %s failed: %s", sym, exc)

    log.info(
        "patch_latest_closes: patched=%d already_current=%d no_cache=%d phantom_skipped=%d",
        patched, already_current, no_cache, phantom_skipped,
    )
    return {
        "patched":        patched,
        "already_current": already_current,
        "no_cache":       no_cache,
        "phantom_skipped": phantom_skipped,
        "total_snapshot": len(snaps),
    }


def purge_weekend_bars() -> dict:
    """One-off repair: drop any Saturday/Sunday-dated bar from every cached
    symbol. These are phantom bars a weekend run of patch_latest_closes wrote
    before the weekday guard existed (2026-05-31) — a near-dup of Friday with
    a drifted volume that corrupts the trailing 25-bar volume window.

    Idempotent and safe to re-run. Returns
    {symbols_scanned, symbols_fixed, bars_removed}.
    """
    coll = _get_mongo()
    if coll is None:
        return {"symbols_scanned": 0, "symbols_fixed": 0, "bars_removed": 0}
    scanned = fixed = removed = 0
    for doc in coll.find({}, {"symbol": 1, "bars": 1}):
        scanned += 1
        bars = doc.get("bars") or []
        kept = [
            b for b in bars
            if not (hasattr(b.get("date"), "weekday") and b["date"].weekday() >= 5)
        ]
        drop = len(bars) - len(kept)
        if drop:
            try:
                coll.update_one({"_id": doc["_id"]}, {"$set": {"bars": kept}})
                fixed += 1
                removed += drop
            except Exception as exc:
                log.warning("purge_weekend_bars: %s failed: %s", doc.get("symbol"), exc)
    log.info("purge_weekend_bars: fixed %d/%d symbols, removed %d bars",
             fixed, scanned, removed)
    return {"symbols_scanned": scanned, "symbols_fixed": fixed, "bars_removed": removed}


def bulk_live_prices(symbols: list[str]) -> dict[str, dict]:
    """Real-time last prices for the given symbols.

    Returns {SYMBOL: {price, change_pct, volume, last_trade_price,
    last_trade_ts_ms, prev_day_close}} — suitable for fast intraday card
    refreshes without re-running the full SEPA scan.

    Extended-hours fields (last_trade_price / last_trade_ts_ms /
    prev_day_close) are surfaced so the frontend can render pre-market
    and after-hours prints with a session badge. Display-only — SEPA
    scoring still uses the regular-session close.
    """
    snaps = bulk_snapshot(symbols)
    return {
        sym: {
            "price":            bar.get("close"),
            "change_pct":       bar.get("change_pct"),
            "volume":           bar.get("volume"),
            # NEW: extended-hours data
            "last_trade_price": bar.get("last_trade_price"),
            "last_trade_ts_ms": bar.get("last_trade_ts_ms"),
            "prev_day_close":   bar.get("prev_day_close"),
        }
        for sym, bar in snaps.items()
        # Surface a ticker if it has ANY usable price:
        #   - close (regular session)
        #   - last_trade_price (extended-hours pre/after print)
        #   - prev_day_close (so the "closed" / weekend / holiday UI can
        #     still display the previous regular close, which is what
        #     the user explicitly asked for in the closed-market UX rules)
        if bar.get("close") or bar.get("last_trade_price") or bar.get("prev_day_close")
    }
