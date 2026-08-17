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

from . import symbols

log = logging.getLogger("sepa.prices")


_APIKEY_RE = None


def _scrub_key(exc) -> str:
    """Exception text with any apiKey=... query param redacted — requests
    embeds the full URL in connection errors, which would otherwise print
    the Massive API key into the logs (leaked once, 2026-06-11; rotated)."""
    global _APIKEY_RE
    import re as _re
    if _APIKEY_RE is None:
        _APIKEY_RE = _re.compile(r"(apiKey=)[A-Za-z0-9_-]+")
    return _APIKEY_RE.sub(r"\1<redacted>", str(exc))

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
    # Yahoo spells class shares BRK-B. See sepa/symbols.py — a wrong spelling
    # returns "no data", which downstream is indistinguishable from "delisted".
    tick = symbols.for_yahoo(symbol)
    try:
        df = yf.Ticker(tick).history(period=period, auto_adjust=False)
    except Exception as exc:
        log.warning("yfinance fetch failed for %s: %s", tick, exc)
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
    # Massive spells class shares BRK.B and returns NOTHING for BRK-B, which
    # silently pushed every class share onto the yfinance fallback. See
    # sepa/symbols.py for the measured evidence.
    tick = symbols.for_massive(symbol)
    url = (
        f"https://api.massive.com/v2/aggs/ticker/{tick}"
        f"/range/1/day/{from_date.date()}/{to_date.date()}"
    )
    try:
        r = requests.get(
            url,
            params={"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": key},
            timeout=15,
        )
        if r.status_code == 429:
            log.warning("massive rate-limited on %s", tick)
            time.sleep(2)
            r = requests.get(
                url,
                params={"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": key},
                timeout=15,
            )
        if r.status_code != 200:
            log.warning("massive %s -> HTTP %s: %s", tick, r.status_code, r.text[:200])
            return None
        results = (r.json() or {}).get("results") or []
    except Exception as exc:
        log.warning("massive fetch failed for %s: %s", symbol, _scrub_key(exc))
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
        # Resolve first: asking for the pre-rename symbol returns the last trade
        # from before the rename, which is a real price from a real session and
        # therefore passes every sanity check while being weeks out of date.
        tick = symbols.for_massive(symbols.resolve(symbol))
        try:
            r = requests.get(
                f"https://api.massive.com/v2/last/trade/{tick}",
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


def _fetch_one(symbol: str, period: str) -> Optional[pd.DataFrame]:
    provider = os.getenv("PRICE_PROVIDER", "massive").lower()
    if provider == "massive":
        df = _fetch_massive(symbol, period)
        if df is not None:
            return df
        log.info("massive returned nothing for %s — falling back to yfinance", symbol)
        return _fetch_yfinance(symbol, period)
    return _fetch_yfinance(symbol, period)


# A rename splice is REFUSED when the boundary price jumps by more than this
# ratio. A rename is a relabelling — the price does not move because of it. A
# large jump means something else happened on that date (a reverse split, a
# spin-off, or a wrong entry in RENAMES), and inventing a continuous series
# across it would fabricate a chart Ajay sizes positions against. Refusing costs
# a short history; splicing wrongly costs a fake one.
SPLICE_MAX_JUMP_RATIO = 1.35
# Boundary sessions must be adjacent. More than this many calendar days between
# the last old bar and the first new one means the symbol was dark in between,
# which is not a clean relabelling.
SPLICE_MAX_GAP_DAYS = 10


def splice_history(old_df: Optional[pd.DataFrame], new_df: Optional[pd.DataFrame],
                   label: str = "") -> Optional[pd.DataFrame]:
    """Old bars before the rename + new bars after it, as one series. PURE.

    Massive only carries ~37 bars under ECHO, which is far too short for a
    200-day average — the continuity is the whole point, not a nicety. Returns
    ``new_df`` unchanged whenever the join would not be honest.
    """
    if new_df is None or len(new_df) == 0:
        return old_df
    if old_df is None or len(old_df) == 0:
        return new_df

    first_new = new_df.index[0]
    head = old_df[old_df.index < first_new]
    if len(head) == 0:
        return new_df

    gap_days = (pd.Timestamp(first_new) - pd.Timestamp(head.index[-1])).days
    if gap_days > SPLICE_MAX_GAP_DAYS:
        log.warning("splice %s: %d-day hole at the boundary — not splicing",
                    label, gap_days)
        return new_df

    prev_close = float(head["close"].iloc[-1])
    next_open = float(new_df["open"].iloc[0])
    if prev_close > 0 and next_open > 0:
        ratio = max(next_open / prev_close, prev_close / next_open)
        if ratio > SPLICE_MAX_JUMP_RATIO:
            log.warning("splice %s: %.2fx price jump at the boundary "
                        "(%.2f -> %.2f) — not splicing", label, ratio,
                        prev_close, next_open)
            return new_df

    out = pd.concat([head, new_df])
    return out[~out.index.duplicated(keep="last")].sort_index()


def _fetch(symbol: str, period: str) -> Optional[pd.DataFrame]:
    """Fetch under the symbol that trades today, splicing in any former name.

    EchoStar renamed SATS -> ECHO on 2026-06-24. Asking either provider for
    SATS returns a series that simply stops that day, which ``is_stale`` reads —
    correctly, on the data it was given — as "this stopped trading", and the UI
    then tells Ajay the company was acquired. It was trading at $91.89.
    """
    live = symbols.resolve(symbol)
    df = _fetch_one(live, period)

    olds = symbols.former_names(live)
    if not olds:
        return df

    for old in olds:
        prior = _fetch_one(old, period)
        df = splice_history(prior, df, label=f"{old}->{live}")
    return df


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


# Scale-discontinuity threshold for the decimal-shift guard (2026-06-15).
# A real, already-cached, already-liquid name never moves anywhere near this
# in a single session — even a limit move is <2x. The only things that produce
# a >=5x close ratio between two adjacent sessions are (a) a stored history left
# at the wrong decimal scale by an earlier bad full-history fetch, or (b) a
# split Massive hasn't reflected yet. For BOTH the correct response is a full,
# clean refetch (adjusted=true), never blindly stacking a correct-scale snapshot
# bar on top of a wrong-scale series. 5x sits well clear of the most violent
# real microcap squeeze, and — critically — even a false positive is harmless:
# the only consequence is one extra full refetch, which returns the real series.
_SCALE_GLITCH_RATIO = 5.0


def _is_scale_glitch(new_close, prev_close) -> bool:
    """True when ``new_close`` is discontinuous from ``prev_close`` by a factor
    no real daily session can produce (>= _SCALE_GLITCH_RATIO either direction).

    This is the signature of a decimal-shift / split-adjustment artifact. It is
    exactly what corrupted KLAC's served scan on 2026-06-12: a correct 254.54
    snapshot bar got appended onto a stored prior-session bar sitting at ~2413
    (~10x scale), so day_change_pct = 254.54 / 2413 - 1 collapsed to -89.45%
    (and the 200-day MA inflated, flipping dist_200_pct to -81.83%). Pure
    function — no Mongo, no network — so it unit-tests like ``_drop_phantom_tail``.
    Returns False (i.e. "not a glitch") on any non-positive or unparseable input,
    so a data hiccup never trips the guard on a legitimate bar.
    """
    try:
        a, b = float(new_close), float(prev_close)
    except (TypeError, ValueError):
        return False
    if a <= 0 or b <= 0:
        return False
    r = a / b
    return r >= _SCALE_GLITCH_RATIO or r <= 1.0 / _SCALE_GLITCH_RATIO


# Staleness is judged primarily in TRADING days (market sessions missed), not
# calendar days. A delisted/halted name that stopped ~12 calendar days ago is
# ~8 market sessions stale — but 12 < 14, so the old calendar-only guard let it
# leak onto the scan / Breakouts board with a frozen, weeks-old "breakout" (KALV,
# Chiesi M&A 2026-06; CFLT before it). The trading-day gate catches it while
# staying clear of normal weekend / holiday gaps (a name is at most 1-2 sessions
# behind even after the longest holiday stretch). The calendar value is kept as
# an outer ceiling.
STALE_MAX_TRADING_DAYS = 6        # > 6 missed market sessions = stale
STALE_MAX_CALENDAR_DAYS = 14      # outer ceiling (kept for the sane-bounds lock)


def is_stale(
    df: Optional[pd.DataFrame],
    asof: Optional[pd.Timestamp] = None,
    max_days: int = STALE_MAX_CALENDAR_DAYS,
    max_trading_days: int = STALE_MAX_TRADING_DAYS,
) -> bool:
    """True when the newest bar is more than ``max_trading_days`` MARKET SESSIONS
    old (or past the ``max_days`` calendar ceiling) — the symbol has stopped
    printing daily bars (delisted, halted, renamed, or a persistent data gap).
    Such a name has no live price and no chart, and must not surface in the scan
    or the buyable tier: a frozen last bar reads as a pocket pivot / breakout and
    leaks into is_buyable and the Breakouts board (KALV, last real bar ~12
    calendar / ~8 trading days back after the Chiesi acquisition — fresh under
    the old 14-calendar guard, stale under the 6-trading-day one; CFLT before
    it). ``asof`` defaults to today (ET). Conservative: returns False on any
    error so a parsing hiccup never silently empties the scan."""
    if df is None or len(df) == 0:
        return True
    try:
        last_ts = pd.Timestamp(df.index[-1]).normalize()
        if asof is None:
            asof = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
        else:
            asof = pd.Timestamp(asof).normalize()
        cal_gap = (asof - last_ts).days
        if cal_gap <= 0:
            return False                       # current / future bar — fresh
        # Market sessions between the last bar and asof (Mon-Fri; holidays
        # over-count harmlessly, well within the 6-session margin).
        trading_gap = max(0, len(pd.bdate_range(last_ts, asof)) - 1)
        return trading_gap > max_trading_days or cal_gap > max_days
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


def bulk_snapshot(syms: list[str]) -> dict[str, dict]:
    """Fetch today's OHLCV snapshot for up to N tickers in one Massive call.

    Massive endpoint: GET /v2/snapshot/locale/us/markets/stocks/tickers
    Returns {SYMBOL: {open, high, low, close, volume, vwap, date, change_pct}}
    Missing or errored symbols are simply absent from the dict.

    Keys come back in OUR spelling, not Massive's. The request goes out as
    BRK.B / ECHO and the response is mapped back to BRK-B / SATS, so a caller
    that asked for a symbol always finds that symbol in the result — a live
    quote silently filed under a name nobody asked for is the same as no quote.
    """
    key = stocks_key()
    if not key:
        return {}
    try:
        import requests as _req
    except ImportError:
        return {}

    # {massive spelling -> what the caller asked for}
    asked: dict[str, str] = {}
    for s in syms:
        canon = (s or "").strip().upper()
        if canon:
            asked.setdefault(symbols.for_massive(symbols.resolve(canon)), canon)
    wire = list(asked)

    result: dict[str, dict] = {}
    chunks = [wire[i : i + _SNAP_CHUNK] for i in range(0, len(wire), _SNAP_CHUNK)]
    for chunk in chunks:
        try:
            r = _req.get(
                "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers",
                params={"tickers": ",".join(chunk), "apiKey": key},
                timeout=15,
            )
            if r.status_code != 200:
                log.warning("bulk_snapshot: HTTP %s for chunk of %d", r.status_code, len(chunk))
                continue
            for item in (r.json() or {}).get("tickers") or []:
                sym = (item.get("ticker") or "").upper()
                sym = asked.get(sym, sym)
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
            log.warning("bulk_snapshot: chunk failed: %s", _scrub_key(exc))

    log.info("bulk_snapshot: fetched %d/%d symbols", len(result), len(wire))
    return result


def patch_latest_closes(syms: list[str]) -> dict:
    """Append today's close to every already-cached symbol using bulk snapshot.

    Instead of re-downloading 2 years of history when the 20h TTL expires,
    we grab just the latest bar for every ticker in one bulk API call and
    append it to the existing Mongo-cached series. The TTL is also reset so
    the scan workers see a fresh cache hit and skip the full re-fetch.

    Symbols not yet cached are left alone — the scan worker will do a full
    history fetch for them as usual.

    Returns stats dict: {patched, already_current, no_cache, total_snapshot}
    """
    snaps = bulk_snapshot(syms)
    if not snaps:
        return {"patched": 0, "already_current": 0, "no_cache": 0, "total_snapshot": 0}

    coll = _get_mongo()
    patched = already_current = no_cache = phantom_skipped = scale_glitch_healed = 0

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

        # Decimal-shift / scale-glitch guard (2026-06-15). Compare today's
        # snapshot close against the most recent stored bar from a PRIOR session
        # (strictly before bar_iso). If they differ by a factor no real session
        # can produce, the stored history is at the wrong decimal scale (left by
        # an earlier bad full-history fetch) — appending or overwriting a
        # correct-scale bar on top yields the KLAC 2026-06-12 signature:
        # day_change_pct = correct / wrong-scale-prev - 1 ~= -89% plus an
        # inflated 200-day MA (dist_200_pct -81.83%). Don't stack a mismatched
        # bar onto a corrupt series; expire cached_at so the next load_prices()
        # does a full clean _fetch -> _mongo_put (rewrites the WHOLE array,
        # healing dist_200 / stage / RS too), and skip this symbol for now.
        prior_session = next(
            (b for b in reversed(doc["bars"]) if _bar_iso(b) and _bar_iso(b) < bar_iso),
            None,
        )
        if prior_session is not None and _is_scale_glitch(
            bar["close"], prior_session.get("close")
        ):
            log.warning(
                "patch_latest_closes: scale glitch for %s (snapshot %s close=%.4f vs "
                "stored prior session %s close=%.4f) — stored history is wrong-scale; "
                "expiring cache to force a clean full refetch",
                sym, bar_iso, float(bar["close"]),
                _bar_iso(prior_session), float(prior_session.get("close") or 0.0),
            )
            if coll is not None:
                try:
                    coll.update_one({"symbol": sym}, {"$set": {"cached_at": 0}})
                except Exception as exc:
                    log.warning("patch_latest_closes: %s cache-expire failed: %s", sym, exc)
            scale_glitch_healed += 1
            continue

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
        "patch_latest_closes: patched=%d already_current=%d no_cache=%d "
        "phantom_skipped=%d scale_glitch_healed=%d",
        patched, already_current, no_cache, phantom_skipped, scale_glitch_healed,
    )
    return {
        "patched":        patched,
        "already_current": already_current,
        "no_cache":       no_cache,
        "phantom_skipped": phantom_skipped,
        "scale_glitch_healed": scale_glitch_healed,
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


def bulk_live_prices(syms: list[str]) -> dict[str, dict]:
    """Real-time last prices for the given symbols.

    Returns {SYMBOL: {price, change_pct, volume, last_trade_price,
    last_trade_ts_ms, prev_day_close}} — suitable for fast intraday card
    refreshes without re-running the full SEPA scan.

    Extended-hours fields (last_trade_price / last_trade_ts_ms /
    prev_day_close) are surfaced so the frontend can render pre-market
    and after-hours prints with a session badge. Display-only — SEPA
    scoring still uses the regular-session close.
    """
    snaps = bulk_snapshot(syms)
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
