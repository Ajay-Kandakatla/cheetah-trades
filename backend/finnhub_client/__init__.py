"""finnhub_client — rate-limited, cache-first, JIT Finnhub access.

What this is
------------
A wrapper around Finnhub's REST API designed for the "just-in-time"
fetching pattern: callers ask for data WHEN the UI needs it (card scrolls
into viewport, user clicks detail, etc.), the wrapper hits cache first,
falls back to a token-bucket-throttled Finnhub call on miss.

Why not eager warming
---------------------
Eager pre-warm (e.g. cron loops through 150 candidates' news + profile +
earnings) bursts Finnhub's free tier and hits 429. JIT only fetches what
a user is actually about to see, so the request rate matches genuine
attention — orders of magnitude below the rate limit.

Why this module instead of direct httpx
---------------------------------------
- Token-bucket rate limiter (shared across all callers in the process)
- Mongo cache with per-endpoint TTL (quote 60s, profile 24h, news 30min)
- Graceful degradation: on 429 or timeout, returns stale cache rather
  than failing the caller
- Single source of truth for Finnhub auth, retries, error handling

Public API
----------
.. code-block:: python

    from finnhub_client import client as fh

    quote = await fh.quote("AAPL")               # 60s cache
    profile = await fh.profile("AAPL")           # 24h cache
    news = await fh.company_news("AAPL")         # 30min cache
    earnings = await fh.earnings_for("AAPL")     # 6h cache
    recs = await fh.recommendation("AAPL")       # 24h cache

All methods return a plain dict (the Finnhub JSON response), or the cached
fallback on transient failure, or ``None`` on hard failure (e.g. bad key).
"""
from . import client
from . import cache
from .api import router

__all__ = ["client", "cache", "router"]
