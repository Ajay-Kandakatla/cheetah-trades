"""ETF detection + fund-specific metrics.

Why this exists: yfinance returns null for `marketCap`, `totalRevenue`, and
`enterpriseValue` on ETFs because those are equity-only concepts. ETFs have
their own metrics (Assets Under Management, expense ratio, distribution
yield, holdings) that the SEPA page should surface instead of empty cells.

Public API:
  - is_etf(symbol) -> bool                : cheap classifier
  - etf_data_for(symbol) -> dict | None   : full ETF payload, None for equities

Cached 30 days in Mongo `etf_info_cache`. ETFs change category / expense ratio
rarely, so a long TTL keeps yfinance traffic low.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional
from . import symbols

log = logging.getLogger("sepa.etf_info")

CACHE_TTL_SEC = 30 * 86400  # 30 days
_memo: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Mongo cache (optional — degrades to in-memory if Mongo isn't reachable)
# ---------------------------------------------------------------------------
_mongo_coll = None
_mongo_disabled = False


def _coll():
    global _mongo_coll, _mongo_disabled
    if _mongo_disabled:
        return None
    if _mongo_coll is not None:
        return _mongo_coll
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _mongo_coll = client[db_name].etf_info_cache
        return _mongo_coll
    except Exception as exc:
        log.warning("etf_info: mongo unavailable (%s)", exc)
        _mongo_disabled = True
        return None


def _cached_get(symbol: str) -> Optional[dict]:
    if symbol in _memo:
        return _memo[symbol]
    coll = _coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"_id": symbol})
        if doc and time.time() - int(doc.get("cached_at", 0)) < CACHE_TTL_SEC:
            payload = doc.get("payload")
            _memo[symbol] = payload
            return payload
    except Exception:
        pass
    return None


def _cached_put(symbol: str, payload: dict) -> None:
    _memo[symbol] = payload
    coll = _coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"_id": symbol},
            {"$set": {"cached_at": int(time.time()), "payload": payload}},
            upsert=True,
        )
    except Exception as exc:
        log.debug("etf_info: cache write failed for %s: %s", symbol, exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def etf_data_for(symbol: str) -> Optional[dict]:
    """Return ETF metadata for `symbol`, or None if it isn't an ETF.

    Payload keys (all may be None except is_etf + symbol):
        is_etf, symbol, name, category, fund_family,
        aum (Assets Under Management, $),
        expense_ratio (decimal, e.g. 0.0095 for 0.95%),
        dividend_yield (trailing 12m, decimal),
        ytd_return (decimal),
        nav,                 # most recent NAV
        holdings_count,      # number of holdings in basket
        top_holdings: list of {symbol, weight} (top 5)
    """
    sym = symbol.upper().strip()

    cached = _cached_get(sym)
    if cached is not None:
        return cached if cached.get("is_etf") else None

    try:
        import yfinance as yf
    except ImportError:
        return None

    try:
        t = symbols.yf_ticker(sym)
        info = t.info or {}
    except Exception as exc:
        log.debug("etf_info: yfinance lookup failed for %s: %s", sym, exc)
        return None

    quote_type = (info.get("quoteType") or "").upper()
    if quote_type != "ETF":
        # Cache the negative result too — saves a yfinance call on the next ask.
        _cached_put(sym, {"is_etf": False, "symbol": sym})
        return None

    # Try to extract top holdings (yfinance Ticker.funds_data may not exist on
    # older versions; falls back to None silently).
    top_holdings: list[dict] = []
    holdings_count: Optional[int] = None
    try:
        fd = getattr(t, "funds_data", None)
        if fd is not None:
            tho = getattr(fd, "top_holdings", None)
            if tho is not None and not tho.empty:
                top_holdings = [
                    {"symbol": str(idx),
                     "name":   str(row.get("Name", "")),
                     "weight": float(row.get("Holding Percent", 0) or 0)}
                    for idx, row in tho.head(5).iterrows()
                ]
            equity_holdings = getattr(fd, "equity_holdings", None)
            if equity_holdings is not None and not equity_holdings.empty:
                # Newer yfinance exposes a holding-count via fund_overview
                pass
    except Exception as exc:
        log.debug("etf_info: holdings fetch failed for %s: %s", sym, exc)

    # yfinance is annoyingly inconsistent with how it returns rate fields:
    #   - annualReportExpenseRatio / netExpenseRatio: returned as percent
    #     points (0.95 means "0.95%"). Need to divide by 100 to get a decimal.
    #   - yield / trailingAnnualDividendYield: usually decimal (0.005 = 0.5%)
    #     but occasionally percent for some funds.
    # Real-world ETF rates: expense 0.03%-1.50%, yield 0%-12%. So in DECIMAL
    # form they sit in 0.0003-0.12 range. Anything > 0.10 in the raw is almost
    # certainly already-percent and needs dividing by 100.
    def _to_decimal(v):
        if v is None:
            return None
        return v / 100 if v > 0.10 else v

    expense_ratio = _to_decimal(
        info.get("annualReportExpenseRatio") or info.get("netExpenseRatio")
    )
    dividend_yield = _to_decimal(
        info.get("yield") or info.get("trailingAnnualDividendYield")
    )

    payload = {
        "is_etf":         True,
        "symbol":         sym,
        "name":           info.get("longName") or info.get("shortName"),
        "category":       info.get("category"),
        "fund_family":    info.get("fundFamily"),
        "aum":            info.get("totalAssets"),
        "expense_ratio":  expense_ratio,
        "dividend_yield": dividend_yield,
        "ytd_return":     info.get("ytdReturn"),
        "nav":            info.get("navPrice"),
        "holdings_count": (info.get("equityHoldings") or {}).get("count")
                          if isinstance(info.get("equityHoldings"), dict) else None,
        "top_holdings":   top_holdings,
    }
    _cached_put(sym, payload)
    return payload


def is_etf(symbol: str) -> bool:
    """Cheap classifier — uses cache when available."""
    data = etf_data_for(symbol)
    return bool(data and data.get("is_etf"))
