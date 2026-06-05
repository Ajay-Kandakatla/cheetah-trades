"""TradingView Charting Library — UDF-compatible datafeed.

Ajay 2026-06-04 (for Ravi): the licensed TradingView Charting Library is the only
way to embed a TradingView-grade chart that can carry CUSTOM indicators (the
embed widget can't — it's anonymous and blocks custom Pine). The library's bundled
`UDFCompatibleDatafeed` reads from a REST API that follows TradingView's UDF
protocol; this module serves that protocol from our OWN price cache (sepa.prices),
so the chart is backed by the same daily OHLCV the scanner uses.

Endpoints (wired in main.py under /tv/udf/*):
  GET /tv/udf/config            datafeed capabilities
  GET /tv/udf/time              server time (unix seconds)
  GET /tv/udf/symbols?symbol=   resolve one symbol
  GET /tv/udf/search?query=     symbol search (our universe)
  GET /tv/udf/history?symbol=&resolution=&from=&to=&countback=   OHLCV bars

Daily is the native resolution; weekly/monthly are resampled from it. Intraday is
not served here (the native lightweight-charts view already does live intraday).

Docs: docs/tradingview_charting_library.md.
"""
from __future__ import annotations

import time
from typing import Optional

SUPPORTED_RESOLUTIONS = ["1D", "1W", "1M"]
EXCHANGE = "Pounce"          # shown as the data source in the chart's legend


def udf_config() -> dict:
    """Datafeed capabilities (the library calls this first, via onReady)."""
    return {
        "supports_search": True,
        "supports_group_request": False,
        "supports_marks": False,
        "supports_timescale_marks": False,
        "supports_time": True,
        "supported_resolutions": SUPPORTED_RESOLUTIONS,
        "exchanges": [
            {"value": "", "name": "All Exchanges", "desc": ""},
            {"value": EXCHANGE, "name": EXCHANGE, "desc": "Pounce price cache"},
        ],
        "symbols_types": [{"name": "Stock", "value": "stock"}],
    }


def server_time() -> int:
    return int(time.time())


def resolve_symbol(symbol: str, *, description: str = "", exchange: str = "") -> dict:
    """Per-symbol metadata. pricescale 100 = two decimals; US equity session."""
    sym = (symbol or "").upper().strip()
    return {
        "name": sym,
        "ticker": sym,
        "full_name": f"{EXCHANGE}:{sym}",
        "description": description or sym,
        "type": "stock",
        "session": "0930-1600",
        "timezone": "America/New_York",
        "exchange": exchange or EXCHANGE,
        "listed_exchange": exchange or EXCHANGE,
        "format": "price",
        "minmov": 1,
        "pricescale": 100,
        "has_intraday": False,
        "has_daily": True,
        "has_weekly_and_monthly": True,
        "supported_resolutions": SUPPORTED_RESOLUTIONS,
        "volume_precision": 0,
        "data_status": "endofday",
    }


def search_symbols(query: str, universe: list[str], *, limit: int = 30) -> list[dict]:
    """Prefix/substring match over a provided symbol universe (kept pure for tests;
    the endpoint passes the latest-scan universe)."""
    q = (query or "").upper().strip()
    out = []
    for sym in universe:
        s = (sym or "").upper()
        if not q or q in s:
            out.append({
                "symbol": s, "full_name": f"{EXCHANGE}:{s}",
                "description": s, "exchange": EXCHANGE, "type": "stock",
            })
        if len(out) >= limit:
            break
    # exact / prefix matches first
    out.sort(key=lambda r: (r["symbol"] != q, not r["symbol"].startswith(q), r["symbol"]))
    return out[:limit]


# ── History (the core: OHLCV → UDF columns) ──────────────────────────────────
def _epoch_utc_midnight(ts) -> int:
    """Daily bars are keyed to 00:00:00 UTC of the session date (UDF convention)."""
    import pandas as pd
    t = pd.Timestamp(ts)
    t = t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC")
    return int(t.normalize().timestamp())


def _resample(df, rule: str):
    import pandas as pd  # noqa: F401
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample(rule, label="left", closed="left").agg(agg).dropna(how="any")


def format_history(df, resolution: str, from_ts: Optional[int], to_ts: Optional[int],
                   countback: Optional[int] = None) -> dict:
    """Pure: daily OHLCV DataFrame → UDF history JSON. Resamples for 1W / 1M,
    windows by [from_ts, to_ts] (or the last `countback` bars up to to_ts)."""
    if df is None or getattr(df, "empty", True):
        return {"s": "no_data"}
    res = (resolution or "1D").upper()
    d = df
    if res in ("1W", "W", "W-FRI"):
        d = _resample(d, "W-FRI")
    elif res in ("1M", "M", "1MONTH"):
        d = _resample(d, "M")

    rows = []
    for ts, row in d.iterrows():
        try:
            t = _epoch_utc_midnight(ts)
        except Exception:
            continue
        if to_ts is not None and t > to_ts:
            continue
        if countback is None and from_ts is not None and t < from_ts:
            continue
        rows.append((t, float(row["open"]), float(row["high"]),
                     float(row["low"]), float(row["close"]), float(row["volume"])))
    rows.sort(key=lambda r: r[0])
    if countback is not None and countback > 0:
        rows = rows[-countback:]

    if not rows:
        # UDF: tell the library there's nothing in this window, and where to look next.
        nxt = None
        try:
            nxt = _epoch_utc_midnight(d.index[0])
        except Exception:
            pass
        return {"s": "no_data", "nextTime": nxt} if nxt else {"s": "no_data"}

    return {
        "s": "ok",
        "t": [r[0] for r in rows],
        "o": [round(r[1], 4) for r in rows],
        "h": [round(r[2], 4) for r in rows],
        "l": [round(r[3], 4) for r in rows],
        "c": [round(r[4], 4) for r in rows],
        "v": [r[5] for r in rows],
    }


def history(symbol: str, resolution: str, from_ts: Optional[int], to_ts: Optional[int],
            countback: Optional[int] = None) -> dict:
    """Load this symbol's daily bars and format them. Thin wrapper over
    format_history so the pure formatter stays unit-testable."""
    from sepa import prices as _prices
    df = _prices.load_prices((symbol or "").upper())
    return format_history(df, resolution, from_ts, to_ts, countback)
