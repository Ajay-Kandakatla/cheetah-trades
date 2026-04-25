"""Real-time news scraping for Cheetah tickers.

Uses three free sources, merged and deduped:
  1. Finnhub /company-news (requires API key, rich metadata)
  2. Yahoo Finance RSS (no key, public feed)
  3. Google News RSS (no key, broad coverage)

Results are cached in memory with a short TTL so refresh-clicks don't hammer
the sources. Cache key is the uppercased ticker.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

log = logging.getLogger("news")

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
CACHE_TTL_SEC = int(os.getenv("NEWS_CACHE_TTL_SEC", "180"))  # 3 minutes
MAX_ITEMS = 12

_cache: dict[str, tuple[float, list[dict]]] = {}
_lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Individual source scrapers
# ---------------------------------------------------------------------------
async def _finnhub_news(client: httpx.AsyncClient, symbol: str) -> list[dict]:
    if not FINNHUB_API_KEY:
        return []
    today = datetime.now(timezone.utc).date()
    frm = (today - timedelta(days=7)).isoformat()
    to = today.isoformat()
    try:
        r = await client.get(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": symbol, "from": frm, "to": to, "token": FINNHUB_API_KEY},
        )
        if r.status_code != 200:
            return []
        out = []
        for n in r.json()[:20]:
            out.append(
                {
                    "source": n.get("source") or "Finnhub",
                    "title": n.get("headline") or "",
                    "url": n.get("url") or "",
                    "summary": (n.get("summary") or "")[:320],
                    "published": n.get("datetime"),  # unix seconds
                    "provider": "finnhub",
                }
            )
        return out
    except Exception as e:
        log.warning("finnhub news %s: %s", symbol, e)
        return []


_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL | re.IGNORECASE)
_TITLE_RE = re.compile(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL | re.IGNORECASE)
_LINK_RE = re.compile(r"<link>(.*?)</link>", re.DOTALL | re.IGNORECASE)
_DATE_RE = re.compile(r"<pubDate>(.*?)</pubDate>", re.DOTALL | re.IGNORECASE)
_DESC_RE = re.compile(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", re.DOTALL | re.IGNORECASE)
_SRC_RE = re.compile(r"<source[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</source>", re.DOTALL | re.IGNORECASE)


def _parse_rss(xml_text: str, provider: str) -> list[dict]:
    out = []
    for item in _ITEM_RE.findall(xml_text):
        title = _TITLE_RE.search(item)
        link = _LINK_RE.search(item)
        date = _DATE_RE.search(item)
        desc = _DESC_RE.search(item)
        src = _SRC_RE.search(item)
        if not (title and link):
            continue
        try:
            ts = int(datetime.strptime(
                (date.group(1) if date else "").strip(),
                "%a, %d %b %Y %H:%M:%S %z",
            ).timestamp())
        except Exception:
            ts = int(time.time())
        raw_desc = html.unescape(desc.group(1)).strip() if desc else ""
        clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)[:320].strip()
        out.append(
            {
                "source": (src.group(1).strip() if src else provider.title()),
                "title": html.unescape(title.group(1)).strip(),
                "url": link.group(1).strip(),
                "summary": clean_desc,
                "published": ts,
                "provider": provider,
            }
        )
    return out


async def _yahoo_news(client: httpx.AsyncClient, symbol: str) -> list[dict]:
    url = (
        f"https://feeds.finance.yahoo.com/rss/2.0/headline"
        f"?s={symbol}&region=US&lang=en-US"
    )
    try:
        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Cheetah-app)"})
        if r.status_code != 200:
            return []
        return _parse_rss(r.text, "yahoo")[:10]
    except Exception as e:
        log.warning("yahoo news %s: %s", symbol, e)
        return []


async def _google_news(client: httpx.AsyncClient, symbol: str) -> list[dict]:
    q = f"{symbol}+stock+OR+earnings+OR+analyst"
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    try:
        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (Cheetah-app)"})
        if r.status_code != 200:
            return []
        return _parse_rss(r.text, "google")[:10]
    except Exception as e:
        log.warning("google news %s: %s", symbol, e)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def fetch_news(symbol: str) -> list[dict]:
    """Return merged, deduped, time-sorted news for a ticker (cached)."""
    symbol = symbol.upper()
    now = time.time()

    async with _lock:
        cached = _cache.get(symbol)
        if cached and now - cached[0] < CACHE_TTL_SEC:
            return cached[1]

    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        fin, yh, gg = await asyncio.gather(
            _finnhub_news(client, symbol),
            _yahoo_news(client, symbol),
            _google_news(client, symbol),
        )

    merged: list[dict] = []
    seen_titles: set[str] = set()
    for item in fin + yh + gg:
        key = re.sub(r"\W+", "", (item.get("title") or "").lower())[:80]
        if not key or key in seen_titles:
            continue
        seen_titles.add(key)
        merged.append(item)

    merged.sort(key=lambda x: x.get("published") or 0, reverse=True)
    merged = merged[:MAX_ITEMS]

    async with _lock:
        _cache[symbol] = (now, merged)

    return merged


async def market_news() -> list[dict]:
    """General-market headlines (Finnhub general + Google 'market')."""
    now = time.time()
    key = "__MARKET__"
    async with _lock:
        cached = _cache.get(key)
        if cached and now - cached[0] < CACHE_TTL_SEC:
            return cached[1]

    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        finnhub_items: list[dict] = []
        if FINNHUB_API_KEY:
            try:
                r = await client.get(
                    "https://finnhub.io/api/v1/news",
                    params={"category": "general", "token": FINNHUB_API_KEY},
                )
                if r.status_code == 200:
                    for n in r.json()[:15]:
                        finnhub_items.append({
                            "source": n.get("source") or "Finnhub",
                            "title": n.get("headline") or "",
                            "url": n.get("url") or "",
                            "summary": (n.get("summary") or "")[:320],
                            "published": n.get("datetime"),
                            "provider": "finnhub",
                        })
            except Exception as e:
                log.warning("finnhub market news: %s", e)

        try:
            g = await client.get(
                "https://news.google.com/rss/search"
                "?q=stock+market+OR+Nasdaq+OR+S%26P+500&hl=en-US&gl=US&ceid=US:en",
                headers={"User-Agent": "Mozilla/5.0 (Cheetah-app)"},
            )
            google_items = _parse_rss(g.text, "google") if g.status_code == 200 else []
        except Exception as e:
            log.warning("google market news: %s", e)
            google_items = []

    items = finnhub_items + google_items
    items.sort(key=lambda x: x.get("published") or 0, reverse=True)
    items = items[:MAX_ITEMS]

    async with _lock:
        _cache[key] = (now, items)
    return items
