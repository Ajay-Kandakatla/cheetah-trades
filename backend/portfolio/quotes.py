"""Live quote fetch for portfolio holdings.

Single batched call to yfinance per refresh, in-process cache so the
morning brief doesn't re-fetch 8 tickers on every page load. Brief is
hit dozens of times a day per user; the cache TTL of 60s keeps yfinance
load trivial while still feeling live.

Returns one row per ticker:
  {
    "ticker":          "MU",
    "last":            746.50,        # last trade price
    "prev_close":      731.20,        # for day delta
    "day_change":      15.30,
    "day_change_pct":  2.09,
    "as_of":           1700000000,
  }
"""
from __future__ import annotations

import logging
import time
from threading import Lock

log = logging.getLogger("portfolio.quotes")

_CACHE_TTL = 60  # seconds
_cache: dict[str, dict] = {}   # ticker -> quote
_cache_set_at: dict[str, float] = {}
_lock = Lock()


def _fresh(t: str) -> bool:
    return (time.time() - _cache_set_at.get(t, 0)) < _CACHE_TTL


def fetch_quotes(tickers: list[str]) -> dict[str, dict]:
    """Return ``{ticker: quote}`` for every input. Cached entries fresh
    within 60s are served from memory; the rest are fetched in one
    yfinance call."""
    tickers = [t.upper().strip() for t in tickers if t]
    out: dict[str, dict] = {}

    with _lock:
        stale = [t for t in tickers if not _fresh(t)]

    if stale:
        # Primary: Massive bulk snapshot — real-time, unlimited, no Yahoo
        # "Too Many Requests" rate limit. yfinance only fills what Massive
        # couldn't price (delistings, thin foreign listings).
        priced: set[str] = set()
        try:
            from sepa import prices as sepa_prices
            live = sepa_prices.bulk_live_prices(stale)
            for t, bar in (live or {}).items():
                last = bar.get("price")
                if not last:                       # pre-open day.c is 0, not a price
                    last = bar.get("last_trade_price")
                if not last:
                    continue
                prev = bar.get("prev_day_close")
                last = float(last)
                prev = float(prev) if prev is not None else None
                quote = {
                    "ticker":         t,
                    "last":           round(last, 4),
                    "prev_close":     None if prev is None else round(prev, 4),
                    "day_change":     None if prev is None else round(last - prev, 4),
                    "day_change_pct": None if (prev is None or prev == 0) else round((last / prev - 1) * 100, 3),
                    "as_of":          int(time.time()),
                }
                with _lock:
                    _cache[t] = quote
                    _cache_set_at[t] = time.time()
                priced.add(t)
        except Exception as exc:
            log.debug("massive portfolio quotes failed: %s", exc)

        remaining = [t for t in stale if t not in priced]
        if remaining:
            try:
                import yfinance as yf
                data = yf.Tickers(" ".join(remaining))
                for t in remaining:
                    try:
                        tk = data.tickers.get(t)
                        if tk is None:
                            continue
                        fi = tk.fast_info
                        last = float(fi.get("last_price") or fi.get("lastPrice") or 0) or None
                        prev = float(fi.get("previous_close") or fi.get("previousClose") or 0) or None
                        quote = {
                            "ticker":         t,
                            "last":           last,
                            "prev_close":     prev,
                            "day_change":     None if (last is None or prev is None) else round(last - prev, 4),
                            "day_change_pct": None if (last is None or prev is None or prev == 0) else round((last / prev - 1) * 100, 3),
                            "as_of":          int(time.time()),
                        }
                        with _lock:
                            _cache[t] = quote
                            _cache_set_at[t] = time.time()
                    except Exception as exc:
                        log.debug("yfinance fast_info failed for %s: %s", t, exc)
            except Exception as exc:
                log.warning("yfinance batch fetch failed: %s", exc)

    with _lock:
        for t in tickers:
            if t in _cache:
                out[t] = _cache[t]
    return out
