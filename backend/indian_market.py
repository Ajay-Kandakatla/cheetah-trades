"""Real-time Indian market data from Yahoo Finance (free, no API key).

Uses Yahoo's public chart endpoint which accepts `.NS` (NSE) and `.BO` (BSE)
suffixes. Quotes + indices are fetched in parallel via httpx.AsyncClient and
cached briefly so refresh clicks don't hammer Yahoo.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

log = logging.getLogger("indian_market")

QUOTE_TTL_SEC = 30       # stocks + indices cache (Yahoo updates ~every 15s)
NEWS_TTL_SEC = 180       # news cache (same as US news)

# Indian tier-1 names with sectors. Symbol uses Yahoo's NSE suffix `.NS`.
INDIAN_STOCKS: list[dict] = [
    {"symbol": "RELIANCE.NS",   "name": "Reliance Industries",      "sector": "Energy / Digital"},
    {"symbol": "TCS.NS",        "name": "Tata Consultancy Services", "sector": "IT Services"},
    {"symbol": "INFY.NS",       "name": "Infosys",                  "sector": "IT Services"},
    {"symbol": "HDFCBANK.NS",   "name": "HDFC Bank",                "sector": "Banking"},
    {"symbol": "ICICIBANK.NS",  "name": "ICICI Bank",               "sector": "Banking"},
    {"symbol": "SBIN.NS",       "name": "State Bank of India",      "sector": "Banking"},
    {"symbol": "AXISBANK.NS",   "name": "Axis Bank",                "sector": "Banking"},
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel",            "sector": "Telecom"},
    {"symbol": "WIPRO.NS",      "name": "Wipro",                    "sector": "IT Services"},
    {"symbol": "LT.NS",         "name": "Larsen & Toubro",          "sector": "Engineering"},
    {"symbol": "ITC.NS",        "name": "ITC",                      "sector": "FMCG"},
    {"symbol": "HINDUNILVR.NS", "name": "Hindustan Unilever",       "sector": "FMCG"},
    {"symbol": "MARUTI.NS",     "name": "Maruti Suzuki",            "sector": "Auto"},
    {"symbol": "TATAMOTORS.NS", "name": "Tata Motors",              "sector": "Auto"},
    {"symbol": "ADANIENT.NS",   "name": "Adani Enterprises",        "sector": "Conglomerate"},
]

INDIAN_INDICES: list[dict] = [
    {"symbol": "^NSEI",    "name": "Nifty 50"},
    {"symbol": "^BSESN",   "name": "BSE Sensex"},
    {"symbol": "^NSEBANK", "name": "Nifty Bank"},
    {"symbol": "^CNXIT",   "name": "Nifty IT"},
]

_quote_cache: dict[str, tuple[float, dict]] = {}
_lock = asyncio.Lock()

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


async def _fetch_yahoo_chart(
    client: httpx.AsyncClient, symbol: str
) -> dict | None:
    """Hit Yahoo's free chart endpoint. Returns the `meta` object or None."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        r = await client.get(url, params={"interval": "1d", "range": "5d"}, headers=_HEADERS)
        if r.status_code != 200:
            log.warning("yahoo chart %s: HTTP %s", symbol, r.status_code)
            return None
        data = r.json()
        result = (data.get("chart") or {}).get("result") or []
        if not result:
            return None
        return result[0].get("meta") or None
    except Exception as e:
        log.warning("yahoo chart %s: %s", symbol, e)
        return None


def _build_stock(meta: dict, base: dict) -> dict:
    price = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose") or price or 0
    change = (price or 0) - prev
    pct = (change / prev * 100) if prev else 0
    return {
        "symbol": base["symbol"].replace(".NS", "").replace(".BO", ""),
        "name": base["name"],
        "sector": base["sector"],
        "price": round(price or 0, 2),
        "change": round(change, 2),
        "changePercent": round(pct, 2),
        "volume": int(meta.get("regularMarketVolume") or 0),
        "high52": round(meta.get("fiftyTwoWeekHigh") or 0, 2) or None,
        "low52": round(meta.get("fiftyTwoWeekLow") or 0, 2) or None,
        # Yahoo chart endpoint doesn't reliably return P/E or market cap,
        # but we keep the keys so the frontend type is satisfied.
        "marketCap": None,
        "peRatio": None,
        "currency": meta.get("currency") or "INR",
    }


def _build_index(meta: dict, base: dict) -> dict:
    price = meta.get("regularMarketPrice") or 0
    prev = meta.get("chartPreviousClose") or meta.get("previousClose") or price
    change = price - prev
    pct = (change / prev * 100) if prev else 0
    return {
        "symbol": base["symbol"],
        "name": base["name"],
        "value": round(price, 2),
        "change": round(change, 2),
        "changePercent": round(pct, 2),
        "lastUpdated": int(time.time()),
    }


async def fetch_indian_market() -> dict:
    """Fetch all stocks + indices in parallel with a short-lived cache."""
    now = time.time()
    async with _lock:
        cached = _quote_cache.get("__all__")
        if cached and now - cached[0] < QUOTE_TTL_SEC:
            return cached[1]

    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        stock_tasks = [_fetch_yahoo_chart(client, s["symbol"]) for s in INDIAN_STOCKS]
        index_tasks = [_fetch_yahoo_chart(client, i["symbol"]) for i in INDIAN_INDICES]
        stock_metas, index_metas = await asyncio.gather(
            asyncio.gather(*stock_tasks),
            asyncio.gather(*index_tasks),
        )

    stocks = [
        _build_stock(meta, base)
        for meta, base in zip(stock_metas, INDIAN_STOCKS)
        if meta
    ]
    indices = [
        _build_index(meta, base)
        for meta, base in zip(index_metas, INDIAN_INDICES)
        if meta
    ]

    payload = {
        "stocks": stocks,
        "indices": indices,
        "fetchedAt": int(now),
    }
    async with _lock:
        _quote_cache["__all__"] = (now, payload)
    return payload
