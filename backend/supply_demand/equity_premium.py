"""External-equity-driven company screener.

Some companies (MSTR, COIN's MSTR-ish trades, certain growth names) trade
mostly on the value EXTERNAL shareholders assign to a thesis or treasury
position — not on operating cash flows. The classic example is MSTR:
  - $58B market cap
  - $5–6B in book equity (mostly Bitcoin holdings + a tiny software op)
  - Operating revenue only $477M trailing
  - Trades at ~10x book, 120x sales — pure premium to fundamentals

These names are interesting because:
  - Premium expansion can drive huge upside (MSTR mNAV cycle)
  - Premium contraction can crush them (-70% drawdowns are routine)
  - Tracking the PREMIUM itself is a leading indicator — when smart money
    sells the premium narrative collapses

This module computes per-ticker:
  - equity_premium_pct = (market_cap - tangible_book_value) / market_cap
  - price_to_book (P/B)
  - price_to_sales (P/S TTM)
  - market_cap_to_revenue
  - shares_growth_yoy   (proxy for "do they fund themselves via equity?")
  - tag                 (TREASURY / GROWTH_PREMIUM / NARRATIVE / NORMAL)

Source: yfinance .info (free, ~0.3s/ticker), parallel.
Cache: 12h in Mongo (fundamentals don't change intraday).
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("supply_demand.equity_premium")

_CACHE_TTL_SEC = 12 * 60 * 60  # 12 hours


# --- Mongo cache --------------------------------------------------------

def _cache_coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        return client[db]["equity_premium_cache"]
    except Exception as exc:
        log.warning("equity_premium cache mongo unavailable: %s", exc)
        return None


def _cache_get_all() -> Optional[dict]:
    coll = _cache_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"_id": "all"})
        if not doc:
            return None
        ts = doc.get("cached_at")
        if not isinstance(ts, datetime):
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - ts).total_seconds() > _CACHE_TTL_SEC:
            return None
        return doc.get("payload")
    except Exception:
        return None


def _cache_put_all(payload: dict):
    coll = _cache_coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"_id": "all"},
            {"$set": {"cached_at": datetime.now(timezone.utc), "payload": payload}},
            upsert=True,
        )
    except Exception:
        pass


# --- Per-ticker fetch ---------------------------------------------------

def _classify_tag(*, equity_share_pct: float, ps: float, pb: float,
                  shares_growth: float, ticker: str) -> tuple[str, str]:
    """Return (tag, rationale).

    `equity_share_pct` = stockholders' equity / market cap × 100 — the
    fraction of market cap that is backed by tangible book equity.
    HIGH values (>40%) mean value is mostly external shareholders' equity
    (e.g. MSTR's BTC NAV + premium). LOW values mean almost all value is
    operating multiple / goodwill (e.g. AAPL).

    Tags:
      TREASURY        — known crypto-treasury vehicles (MSTR, COIN, MARA, RIOT, ...)
      EQUITY_HEAVY    — equity_share_pct ≥ 50 (value largely tangible book equity)
      NARRATIVE       — heavy share issuance + low equity backing (pure premium)
      GROWTH_PREMIUM  — high P/S + high P/B (hot growth name pricing in future)
      NORMAL          — typical operating multiple
    """
    # Hardcoded BTC-treasury / coin-adjacent vehicles
    treasury_set = {"MSTR", "COIN", "MARA", "RIOT", "CLSK", "HUT", "BITF",
                    "GBTC", "IBIT", "FBTC", "SMLR", "TSLA"}  # TSLA has BTC on BS
    if ticker.upper() in treasury_set and equity_share_pct >= 30:
        return ("TREASURY",
                f"{int(equity_share_pct)}% of market cap = book equity. "
                f"Value driven by treasury holdings (typically BTC) + premium to NAV.")

    if equity_share_pct >= 50:
        return ("EQUITY_HEAVY",
                f"{int(equity_share_pct)}% of market cap is backed by tangible "
                f"shareholders' equity. External investors valuing the assets, "
                f"not future earnings.")

    if shares_growth >= 8 and equity_share_pct >= 25:
        return ("NARRATIVE",
                f"Heavy stock issuance ({shares_growth:.0f}% YoY) plus "
                f"~{int(equity_share_pct)}% equity backing — funded by external "
                f"capital rather than retained earnings.")

    if ps >= 15 and pb is not None and pb >= 5 and pb < 100:
        return ("GROWTH_PREMIUM",
                f"P/S {ps:.1f} · P/B {pb:.1f} — market pricing in significant "
                f"future growth not yet in earnings.")

    return ("NORMAL", "Most of value backed by operating fundamentals.")


def _fetch_one(ticker: str) -> Optional[dict]:
    """Pull yfinance fundamentals + compute equity premium signals."""
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        info = tk.info or {}
    except Exception as exc:
        log.debug("equity_premium fetch failed for %s: %s", ticker, exc)
        return None

    mcap = info.get("marketCap")
    pb = info.get("priceToBook")
    ps = info.get("priceToSalesTrailing12Months")
    book_value_per_share = info.get("bookValue")
    shares_out = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
    revenue_ttm = info.get("totalRevenue")
    enterprise_value = info.get("enterpriseValue")
    cash = info.get("totalCash")
    debt = info.get("totalDebt")
    name = info.get("shortName") or info.get("longName")
    sector = info.get("sector")

    if not mcap:
        return None

    # Get total stockholders' equity. Prefer .balance_sheet (most reliable),
    # fall back to bookValue × shares if needed.
    book_value_total = None
    try:
        bs = tk.balance_sheet
        if bs is not None and not bs.empty:
            for key in ("Stockholders Equity", "Common Stock Equity",
                         "Total Stockholder Equity"):
                if key in bs.index:
                    val = bs.loc[key].iloc[0]
                    if val and val > 0:
                        book_value_total = float(val)
                        break
    except Exception:
        pass

    # Fallback: bookValue (per share) × shares_outstanding
    if book_value_total is None and book_value_per_share and shares_out:
        try:
            book_value_total = float(book_value_per_share) * float(shares_out)
        except Exception:
            pass

    # equity_share_pct = book_equity / market_cap × 100
    # HIGH (>50%) = value mostly backed by tangible equity (treasury, value).
    # LOW (<10%)  = value mostly operating multiple / intangibles (growth, narrative).
    equity_share_pct = None
    if book_value_total and mcap and mcap > 0:
        equity_share_pct = book_value_total / mcap * 100
        # Sanity-clip — extreme values usually mean stale yfinance data
        equity_share_pct = max(-50.0, min(150.0, equity_share_pct))

    # Filter out broken P/B values (yfinance occasionally returns 1000+ on
    # tickers post-buyback or with negative book equity)
    if pb is not None:
        try:
            pb = float(pb)
            if pb > 200 or pb < -200:
                pb = None
        except Exception:
            pb = None

    # Mcap / revenue (better than P/S for some structures)
    mcap_to_rev = None
    if mcap and revenue_ttm:
        mcap_to_rev = mcap / max(revenue_ttm, 1)

    # Share-count growth: needs historical. Use floatShares + sharesShort
    # diff as rough proxy. Better: use yfinance's quarterly_balance_sheet to
    # get shares-outstanding history. For now we approximate via
    # info.netIncomeToCommon vs sharesOutstanding (proxy).
    # TODO: properly compute YoY share growth via balance sheet.
    shares_growth = 0.0
    try:
        bs = tk.quarterly_balance_sheet
        if bs is not None and not bs.empty:
            so_row = None
            for key in ("Share Issued", "Ordinary Shares Number", "Common Stock", "Total Capitalization"):
                if key in bs.index:
                    so_row = bs.loc[key]
                    break
            if so_row is not None and len(so_row) >= 4:
                # latest 1Q vs 4Q ago = YoY growth in share count
                latest = float(so_row.iloc[0])
                year_ago = float(so_row.iloc[3]) if len(so_row) > 3 else float(so_row.iloc[-1])
                if year_ago > 0:
                    shares_growth = (latest / year_ago - 1) * 100
    except Exception:
        pass

    tag, rationale = _classify_tag(
        equity_share_pct=equity_share_pct or 0,
        ps=ps or 0,
        pb=pb,
        shares_growth=shares_growth or 0,
        ticker=ticker,
    )

    # Cash + investments as % of mcap — separate signal for treasury vehicles
    cash_pct = None
    if cash and mcap and mcap > 0:
        cash_pct = round(cash / mcap * 100, 1)

    return {
        "ticker": ticker.upper(),
        "name": name,
        "sector": sector,
        "market_cap": mcap,
        "book_value_total": book_value_total,
        "revenue_ttm": revenue_ttm,
        "enterprise_value": enterprise_value,
        "cash": cash,
        "cash_pct_of_mcap": cash_pct,
        "debt": debt,
        "pb_ratio": pb,
        "ps_ratio": ps,
        "mcap_to_revenue": round(mcap_to_rev, 1) if mcap_to_rev else None,
        "equity_share_pct": round(equity_share_pct, 1) if equity_share_pct is not None else None,
        "shares_growth_yoy_pct": round(shares_growth, 1) if shares_growth else 0,
        "tag": tag,
        "rationale": rationale,
    }


# --- Public API ---------------------------------------------------------

def get_equity_premium_screen(force: bool = False, tickers: Optional[list[str]] = None) -> dict:
    """Return premium-to-fundamentals screen across the supply/demand graph.

    Sorted by equity_premium_pct descending — names where the most of
    market cap is "above book" come first.
    """
    if not force:
        cached = _cache_get_all()
        if cached:
            return cached

    if not tickers:
        try:
            from .dependencies import NODES
            tickers = [n["ticker"] for n in NODES]
        except Exception:
            tickers = []

    t0 = time.time()
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for r in ex.map(_fetch_one, tickers):
            if r:
                rows.append(r)

    # Sort by equity_share_pct DESC (treasury/equity-heavy names first)
    rows.sort(
        key=lambda r: r.get("equity_share_pct") if r.get("equity_share_pct") is not None else -999,
        reverse=True,
    )

    by_tag = {"TREASURY": 0, "EQUITY_HEAVY": 0, "NARRATIVE": 0, "GROWTH_PREMIUM": 0, "NORMAL": 0}
    for r in rows:
        tag = r.get("tag") or "NORMAL"
        by_tag[tag] = by_tag.get(tag, 0) + 1

    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
        "n_total": len(rows),
        "by_tag": by_tag,
        "elapsed_sec": round(time.time() - t0, 1),
    }
    _cache_put_all(payload)
    return payload


__all__ = ["get_equity_premium_screen"]


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    p = get_equity_premium_screen(tickers=["MSTR", "COIN", "PLTR", "AAPL", "F"], force=True)
    for r in p["rows"]:
        print(f"{r['ticker']:7s} {r['tag']:18s} prem={r.get('equity_premium_pct')}%  P/B={r.get('pb_ratio')}  P/S={r.get('ps_ratio')}")
