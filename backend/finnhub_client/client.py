"""Rate-limited Finnhub HTTP client.

Token-bucket
------------
Shared across the whole process. Configured for Finnhub's free tier
(30 req/min) with a small safety margin: 25 req/min sustained, 5/sec
burst. If the caller submits faster than that, the request blocks until
a token is available (no dropping, no 429).

Failure handling
----------------
- ``429 Too Many Requests``: pause the bucket for 30s, return stale
  cache to the caller if available, else None
- ``5xx`` from Finnhub: 1 retry with exponential backoff, then stale cache
- Network timeout: 1 retry, then stale cache
- ``403``: bad key, no point retrying — return None

All non-cache-hit paths log at INFO level so production can see the real
Finnhub request volume.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

import httpx

from . import cache as _cache

log = logging.getLogger("finnhub_client.client")

_BASE_URL = "https://finnhub.io/api/v1"
_FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# Token-bucket configuration. ``rate`` tokens added per second up to
# ``capacity``. The defaults give Finnhub's free tier ~25 sustained
# requests/min with short bursts of 5 — comfortably under the 30/min
# cutoff that triggers 429s on the actual server.
_BUCKET_CAPACITY = 5         # max burst
_BUCKET_RATE_PER_SEC = 25 / 60.0   # ≈ 0.417 tokens/sec → 25/min

# After a 429, freeze the bucket for this long before retrying. Finnhub's
# rate-limit window is ~60s so 30s pauses long enough for the window to
# slide without leaving the user waiting forever.
_BACKOFF_AFTER_429_SEC = 30


class _TokenBucket:
    """Standard token-bucket throttle. Async-aware: ``acquire()`` awaits
    when no tokens are available, then debits one."""

    def __init__(self, capacity: float, refill_per_sec: float) -> None:
        self._capacity = capacity
        self._tokens = capacity
        self._rate = refill_per_sec
        self._last = time.monotonic()
        self._lock = asyncio.Lock()
        self._pause_until: float = 0.0   # 0 = bucket not paused

    def pause(self, seconds: float) -> None:
        """Pause the bucket for ``seconds`` (e.g. after a 429). New
        acquires will block until the pause expires."""
        self._pause_until = max(self._pause_until, time.monotonic() + seconds)
        log.warning("finnhub_client: bucket paused %.0fs after rate-limit hit", seconds)

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                # Honor any active pause from a recent 429.
                if now < self._pause_until:
                    wait = self._pause_until - now
                else:
                    # Refill tokens based on elapsed time.
                    elapsed = now - self._last
                    self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                    self._last = now
                    if self._tokens >= 1:
                        self._tokens -= 1
                        return
                    # Not enough — compute how long to wait for one token.
                    wait = (1 - self._tokens) / self._rate
            # Release the lock before sleeping so other waiters can also
            # observe the bucket state. After sleep, loop to re-check.
            await asyncio.sleep(max(wait, 0.05))


_bucket = _TokenBucket(_BUCKET_CAPACITY, _BUCKET_RATE_PER_SEC)
_http: Optional[httpx.AsyncClient] = None


async def _get_http() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=10)
    return _http


def is_configured() -> bool:
    """Tells callers whether the Finnhub key is set. ``/finnhub-v2/health``
    uses this to surface a friendly setup error instead of 500-ing."""
    return bool(_FINNHUB_API_KEY)


async def _fetch_raw(path: str, params: dict) -> Optional[dict]:
    """Low-level Finnhub call. Handles rate-limit + retry. Returns the
    JSON dict on success, None on any failure (caller falls back to
    stale cache)."""
    if not _FINNHUB_API_KEY:
        log.warning("finnhub_client: FINNHUB_API_KEY not set")
        return None

    params = {**params, "token": _FINNHUB_API_KEY}
    url = f"{_BASE_URL}{path}"

    for attempt in (1, 2):
        await _bucket.acquire()
        try:
            client = await _get_http()
            r = await client.get(url, params=params)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                _bucket.pause(_BACKOFF_AFTER_429_SEC)
                return None    # caller serves stale
            if r.status_code == 403:
                log.error("finnhub_client: 403 from %s — bad key?", path)
                return None
            if 500 <= r.status_code < 600 and attempt == 1:
                log.warning("finnhub_client: %s -> HTTP %s; retrying",
                            path, r.status_code)
                await asyncio.sleep(1.5)
                continue
            log.warning("finnhub_client: %s -> HTTP %s", path, r.status_code)
            return None
        except httpx.TimeoutException:
            if attempt == 1:
                log.warning("finnhub_client: timeout on %s; retrying", path)
                await asyncio.sleep(1.0)
                continue
            log.warning("finnhub_client: timeout on %s (final)", path)
            return None
        except Exception as exc:
            log.warning("finnhub_client: error on %s: %s", path, exc)
            return None
    return None


# ============================================================================
# Public endpoint wrappers
# ============================================================================
# Each method follows the same shape:
#   1. Probe cache for a fresh hit → return immediately
#   2. Otherwise hit Finnhub through the throttled bucket
#   3. On success, cache + return
#   4. On failure, return stale cache if any (graceful degradation)
# ============================================================================
async def quote(symbol: str) -> Optional[dict]:
    """Current price snapshot. Returns {c, o, h, l, pc, dp, ...} or None."""
    return await _cached_call("quote", "/quote", {"symbol": symbol.upper()}, symbol)


async def profile(symbol: str) -> Optional[dict]:
    """Company profile: name, country, exchange, sector, marketCap, etc."""
    return await _cached_call("profile", "/stock/profile2", {"symbol": symbol.upper()}, symbol)


async def company_news(symbol: str, days_back: int = 7) -> Optional[list]:
    """Company-specific news headlines for the last ``days_back`` days."""
    from datetime import datetime, timedelta
    today = datetime.utcnow().date()
    frm = (today - timedelta(days=days_back)).isoformat()
    to  = today.isoformat()
    data = await _cached_call(
        "news",
        "/company-news",
        {"symbol": symbol.upper(), "from": frm, "to": to},
        symbol,
    )
    # Finnhub returns a JSON array; the cache layer expects dict so we
    # wrap. Unwrap on read.
    if isinstance(data, dict) and "rows" in data:
        return data["rows"]
    if isinstance(data, list):
        return data
    return None


async def earnings_for(symbol: str) -> Optional[dict]:
    """Next earnings event for the symbol (date, EPS estimate, etc.)."""
    from datetime import datetime, timedelta
    today = datetime.utcnow().date()
    to = (today + timedelta(days=120)).isoformat()
    return await _cached_call(
        "earnings",
        "/calendar/earnings",
        {"symbol": symbol.upper(), "from": today.isoformat(), "to": to},
        symbol,
    )


async def recommendation(symbol: str) -> Optional[list]:
    """Analyst recommendation trends (latest 4 quarters)."""
    data = await _cached_call(
        "recommendation",
        "/stock/recommendation",
        {"symbol": symbol.upper()},
        symbol,
    )
    if isinstance(data, dict) and "rows" in data:
        return data["rows"]
    if isinstance(data, list):
        return data
    return None


async def price_target(symbol: str) -> Optional[dict]:
    """Analyst price targets — mean, high, low, last update."""
    return await _cached_call(
        "price_target",
        "/stock/price-target",
        {"symbol": symbol.upper()},
        symbol,
    )


# ----------------------------------------------------------------------------
# Internal: the cache-then-fetch flow shared by every endpoint above.
# ----------------------------------------------------------------------------
async def _cached_call(endpoint: str, path: str, params: dict, symbol: str) -> Optional[dict]:
    hit = _cache.get(endpoint, symbol)
    if hit is not None:
        return hit
    data = await _fetch_raw(path, params)
    if data is not None:
        # Finnhub returns lists for news/recommendation — wrap to dict so
        # the cache layer (which stores dict) round-trips cleanly.
        cache_payload = data if isinstance(data, dict) else {"rows": data}
        _cache.put(endpoint, symbol, cache_payload)
        return data
    # Fetch failed (429, timeout, etc.). Serve stale cache rather than
    # leaving the user empty-handed — the data is at most a few hours
    # old and the UI shows a "cached" indicator.
    return _cache.get(endpoint, symbol, allow_stale=True)
