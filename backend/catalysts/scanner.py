"""Catalyst scanner — find tiny stocks moving big TODAY.

Pipeline:
  1. Fetch top US gainers + losers from Massive snapshot endpoints.
  2. Filter for "tiny" — share price < $20 OR market cap < $500M.
  3. Compute volume surge ratio (today's volume / 30d avg).
  4. Return ranked candidates (chatter + evidence enrichment lives in
     `chatter.py` and `evidence.py` — kept separate so we can swap signals
     in/out without touching the price-driven core).

Free / paid mix:
  - Massive Developer ($79/mo) gives bulk snapshot + gainers/losers.
  - yfinance fallback for share-count / float when Massive lacks it.

The scan is intentionally permissive — we want to catch RYOJ-style names
that aren't on hot-stock screeners but are moving on chatter alone.
"""
from __future__ import annotations

import logging
import os
from massive_keys import stocks_key
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import requests
from sepa import symbols

log = logging.getLogger("catalysts.scanner")

# --- Tiny-stock criteria ------------------------------------------------
# Permissive on purpose: catch <$20 names AND microcaps that happen to
# trade higher. The combined "tiny_score" then weighs how tiny the name is.
DEFAULT_MAX_SHARE_PRICE = 20.0
DEFAULT_MAX_MARKET_CAP_USD = 500_000_000
DEFAULT_MIN_ABS_CHANGE_PCT = 8.0   # only show movers ≥ ±8%
DEFAULT_MIN_PRICE = 0.10           # filter out the most degenerate sub-pennies


def _massive_key() -> Optional[str]:
    return stocks_key()


def _fetch_movers(direction: str, limit: int = 50) -> list[dict]:
    """Hit Massive snapshot gainers / losers endpoint.

    Massive returns up to 50 per direction. We always fetch both then
    merge so the user sees both up- and down-catalyst plays.
    """
    key = _massive_key()
    if not key:
        log.warning("MASSIVE_API_KEY not set — scanner cannot run")
        return []

    url = f"https://api.massive.com/v2/snapshot/locale/us/markets/stocks/{direction}"
    try:
        r = requests.get(url, params={"apiKey": key}, timeout=10)
        if r.status_code != 200:
            log.warning("massive %s HTTP %s: %s", direction, r.status_code, r.text[:200])
            return []
        body = r.json() or {}
        return body.get("tickers") or []
    except Exception as exc:
        log.warning("massive %s failed: %s", direction, exc)
        return []


def _normalize_snapshot(snap: dict) -> Optional[dict]:
    """Turn a Massive snapshot row into our canonical format. Returns None
    if essential fields are missing."""
    t = snap.get("ticker")
    if not t:
        return None
    day = snap.get("day", {}) or {}
    prev = snap.get("prevDay", {}) or {}
    last_trade = snap.get("lastTrade", {}) or {}
    last_quote = snap.get("lastQuote", {}) or {}

    price = last_trade.get("p") or day.get("c") or prev.get("c")
    prev_close = prev.get("c")
    volume = day.get("v") or 0
    change_pct = snap.get("todaysChangePerc")
    if change_pct is None and price and prev_close:
        change_pct = (price - prev_close) / prev_close * 100

    if not price or price < DEFAULT_MIN_PRICE:
        return None
    if change_pct is None:
        return None

    return {
        "ticker": t.upper(),
        "price": float(price),
        "prev_close": float(prev_close or 0),
        "change_pct": round(float(change_pct), 2),
        "volume": int(volume or 0),
        "dollar_volume": int((volume or 0) * (price or 0)),
        "day_high": float(day.get("h") or 0),
        "day_low": float(day.get("l") or 0),
        "day_open": float(day.get("o") or 0),
        "spread_pct": (
            (last_quote.get("a", 0) - last_quote.get("b", 0)) / price * 100
            if last_quote.get("a") and last_quote.get("b") and price else None
        ),
    }


def _enrich_with_yfinance(c: dict) -> dict:
    """Pull market cap, float, avg volume, sector via yfinance.

    yfinance.fast_info gives us a fast path for cap/avg-vol; full info
    only on miss because it's slower.
    """
    try:
        import yfinance as yf
        tk = symbols.yf_ticker(c["ticker"])
        fi = tk.fast_info

        cap = None
        try: cap = float(getattr(fi, "market_cap", None) or 0) or None
        except Exception: pass

        avg_vol = None
        try: avg_vol = float(getattr(fi, "ten_day_average_volume", None) or 0) or None
        except Exception: pass
        if not avg_vol:
            try: avg_vol = float(getattr(fi, "three_month_average_volume", None) or 0) or None
            except Exception: pass

        # Surge ratio: today's volume vs 10d avg. Capped at 50× to keep UI sane.
        surge = None
        if avg_vol and avg_vol > 0 and c.get("volume"):
            surge = min(50.0, c["volume"] / avg_vol)

        # Sector / float — use full info ONLY for promising candidates
        sector = None
        company_name = None
        share_float = None
        try:
            info = tk.info or {}
            sector = info.get("sector")
            company_name = info.get("shortName") or info.get("longName")
            share_float = info.get("floatShares") or info.get("sharesOutstanding")
        except Exception:
            pass

        return {
            **c,
            "market_cap": cap,
            "avg_volume_10d": avg_vol,
            "volume_surge_ratio": round(surge, 1) if surge else None,
            "sector": sector,
            "company_name": company_name,
            "float": share_float,
        }
    except Exception as exc:
        log.debug("yfinance enrich failed for %s: %s", c.get("ticker"), exc)
        return c


def _is_tiny(c: dict, max_price: float, max_cap: float) -> bool:
    """A stock is 'tiny' if EITHER price < max_price OR market cap < max_cap.
    We use OR (not AND) so a $25 stock with a $200M cap still qualifies."""
    price_ok = c.get("price", 0) <= max_price
    cap = c.get("market_cap")
    cap_ok = cap is not None and cap <= max_cap
    # If we have neither cap nor cheap price, exclude conservatively
    if cap is None:
        return price_ok
    return price_ok or cap_ok


def scan(
    *,
    max_share_price: float = DEFAULT_MAX_SHARE_PRICE,
    max_market_cap: float = DEFAULT_MAX_MARKET_CAP_USD,
    min_abs_change_pct: float = DEFAULT_MIN_ABS_CHANGE_PCT,
    max_results: int = 30,
) -> list[dict]:
    """Run the full scan and return a list of candidate dicts.

    Each candidate has price/volume/change% from Massive plus market_cap +
    avg_volume + sector + company_name from yfinance. Chatter & evidence
    enrichment is layered on top by the caller.
    """
    # 1) Pull both directions in parallel
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_gain = ex.submit(_fetch_movers, "gainers")
        f_lose = ex.submit(_fetch_movers, "losers")
        raw = (f_gain.result() or []) + (f_lose.result() or [])

    log.info("massive returned %d raw movers", len(raw))

    # 2) Normalize + filter by change magnitude + price floor
    normalized = []
    for snap in raw:
        n = _normalize_snapshot(snap)
        if n is None:
            continue
        # Massive's movers snapshot can serve a ghost — a ticker its own
        # reference API no longer knows (GFRR: reference NOT_FOUND, zero
        # aggs, Yahoo 404). Each ghost re-enters every 5-min cron run and
        # ERRORs the yfinance enrich, forever. Verified fates only — the
        # curated list lives in sepa.symbols.DELISTED with evidence.
        if symbols.is_delisted(n["ticker"]):
            log.debug("dropping delisted ghost from movers: %s", n["ticker"])
            continue
        if abs(n["change_pct"]) < min_abs_change_pct:
            continue
        normalized.append(n)

    log.info("after normalize+price filter: %d candidates", len(normalized))

    # 3) Enrich with yfinance (parallel — ~0.3s/ticker, but we cap to top 60)
    normalized.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    top_for_enrich = normalized[: max(max_results * 2, 60)]
    with ThreadPoolExecutor(max_workers=15) as ex:
        enriched = list(ex.map(_enrich_with_yfinance, top_for_enrich))

    # 4) Apply tiny filter
    tiny = [c for c in enriched if _is_tiny(c, max_share_price, max_market_cap)]
    log.info("after tiny filter (price<%s or cap<$%dM): %d candidates",
             max_share_price, int(max_market_cap // 1e6), len(tiny))

    # 5) Sort by combined heuristic: |change%| weighted by volume surge
    def heuristic(c):
        change = abs(c.get("change_pct") or 0)
        surge = c.get("volume_surge_ratio") or 1
        return change * (1 + min(surge, 10) * 0.2)
    tiny.sort(key=heuristic, reverse=True)

    return tiny[:max_results]


__all__ = ["scan"]


if __name__ == "__main__":
    import json
    print(json.dumps(scan(), indent=2, default=str))
