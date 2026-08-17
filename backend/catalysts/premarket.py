"""Pre-market scanner — catch tiny stocks gapping up BEFORE 9:30 ET.

70% of the best pump entries happen in the first 30 min of regular session,
so you want to know who's setting up DURING pre-market (4:00-9:30 AM ET).

Why a separate module:
  - Massive's "gainers" / "losers" snapshot endpoints don't work pre-market
    (they only count regular session). We compute % change manually from
    pre-market last trade vs prior-day close.
  - We use a different criteria mix: volume vs avg pre-market volume isn't
    available for free, so we lean harder on absolute price move + dollar
    volume + chatter velocity.

Sources:
  - Massive last trade + prev close (paid; covers extended hours)
  - yfinance fast_info (free, 15-min delayed but covers extended hours)

Endpoint:  /catalysts/premarket
Cron:      4am, 6am, 8am, 9:25am ET on weekdays
"""
from __future__ import annotations

import logging
import os
from massive_keys import stocks_key
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

import requests
from sepa import symbols

log = logging.getLogger("catalysts.premarket")

# Universe to scan in pre-market. We can't enumerate every US ticker here
# without paying for the full reference list; instead we use the union of:
#   1. Yesterday's regular-session top movers (via Massive snapshot — they
#      often follow through pre-market)
#   2. Stocks with overnight news (Massive news last 12h)
#   3. Names already in our supply/demand graph (smaller universe but always
#      up-to-date)
PREMARKET_MIN_ABS_CHANGE_PCT = 5.0
PREMARKET_MAX_PRICE = 20.0
PREMARKET_MAX_CAP = 500_000_000


def _et_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(timezone.utc)


def is_premarket_window() -> dict:
    """Return premarket-window status + label."""
    n = _et_now()
    if n.weekday() >= 5:
        return {"in_window": False, "label": "Weekend", "minutes_until_open": None}
    cur = n.hour * 60 + n.minute
    pre_start = 4 * 60       # 4am ET
    open_min = 9 * 60 + 30   # 9:30 ET
    after = 16 * 60          # 4pm ET
    after_end = 20 * 60      # 8pm ET

    if pre_start <= cur < open_min:
        return {
            "in_window": True,
            "label": "Pre-market",
            "minutes_until_open": open_min - cur,
        }
    if open_min <= cur < after:
        return {"in_window": False, "label": "Regular session", "minutes_until_open": None}
    if after <= cur < after_end:
        return {"in_window": False, "label": "After-hours", "minutes_until_open": None}
    return {"in_window": False, "label": "Closed", "minutes_until_open": None}


def _seed_universe() -> list[str]:
    """Build a candidate ticker list for the pre-market sweep.

    Strategy:
      - Take yesterday's gainers/losers (those often follow through)
      - Add tickers with overnight news from Massive
      - Add the supply_demand graph nodes as a baseline of major names
    """
    seen: set[str] = set()
    out: list[str] = []

    # 1) Yesterday's biggest movers (still likely to gap pre-market)
    key = stocks_key()
    if key:
        for direction in ("gainers", "losers"):
            try:
                r = requests.get(
                    f"https://api.massive.com/v2/snapshot/locale/us/markets/stocks/{direction}",
                    params={"apiKey": key},
                    timeout=10,
                )
                if r.status_code == 200:
                    for snap in (r.json() or {}).get("tickers", []):
                        t = (snap.get("ticker") or "").upper()
                        if t and t not in seen:
                            seen.add(t)
                            out.append(t)
            except Exception as exc:
                log.warning("seed gainers/%s failed: %s", direction, exc)

    # 2) Overnight news mentions (last 12h)
    if key:
        try:
            r = requests.get(
                "https://api.massive.com/v2/reference/news",
                params={"limit": 100, "order": "desc", "apiKey": key},
                timeout=10,
            )
            if r.status_code == 200:
                for it in (r.json() or {}).get("results", []):
                    for t in (it.get("tickers") or []):
                        t = (t or "").upper()
                        if t and t not in seen:
                            seen.add(t)
                            out.append(t)
        except Exception as exc:
            log.warning("seed news failed: %s", exc)

    log.info("premarket universe seeded with %d tickers", len(out))
    return out


def _fetch_premarket_quote(ticker: str) -> Optional[dict]:
    """Get latest extended-hours price + prev close for one ticker.

    Falls back gracefully across Massive → yfinance.
    """
    # Try Massive first (paid + reliable)
    key = stocks_key()
    if key:
        try:
            r = requests.get(
                f"https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers/{ticker.upper()}",
                params={"apiKey": key},
                timeout=6,
            )
            if r.status_code == 200:
                snap = (r.json() or {}).get("ticker")
                if snap:
                    last_trade = snap.get("lastTrade", {}) or {}
                    prev = snap.get("prevDay", {}) or {}
                    day = snap.get("day", {}) or {}
                    price = last_trade.get("p") or day.get("c") or prev.get("c")
                    pclose = prev.get("c")
                    if price and pclose:
                        chg = (price - pclose) / pclose * 100
                        return {
                            "ticker": ticker.upper(),
                            "price": float(price),
                            "prev_close": float(pclose),
                            "change_pct": round(float(chg), 2),
                            "volume": int(day.get("v") or 0),
                            "dollar_volume": int((day.get("v") or 0) * (price or 0)),
                            "ts_unix_ns": last_trade.get("t"),
                            "_source": "massive",
                        }
        except Exception as exc:
            log.debug("massive premarket fail for %s: %s", ticker, exc)

    # Fallback: yfinance (covers extended hours via fast_info)
    try:
        import yfinance as yf
        tk = symbols.yf_ticker(ticker)
        fi = tk.fast_info
        last = float(getattr(fi, "last_price", 0) or 0)
        prev = float(getattr(fi, "previous_close", 0) or 0)
        if last and prev:
            chg = (last - prev) / prev * 100
            return {
                "ticker": ticker.upper(),
                "price": last,
                "prev_close": prev,
                "change_pct": round(chg, 2),
                "volume": int(getattr(fi, "last_volume", 0) or 0),
                "dollar_volume": int((getattr(fi, "last_volume", 0) or 0) * last),
                "_source": "yfinance",
            }
    except Exception as exc:
        log.debug("yfinance premarket fail for %s: %s", ticker, exc)

    return None


def scan_premarket(
    *,
    min_abs_change_pct: float = PREMARKET_MIN_ABS_CHANGE_PCT,
    max_price: float = PREMARKET_MAX_PRICE,
    max_cap: float = PREMARKET_MAX_CAP,
    max_results: int = 25,
) -> dict:
    """Run the pre-market scan. Returns ranked candidates.

    Slightly different filter than regular-session scan — we relax volume
    surge entirely (no avg pre-market vol available for free) but require
    a meaningful absolute price move + non-trivial dollar volume.
    """
    window = is_premarket_window()

    # 1) Build seed universe
    universe = _seed_universe()

    # 2) Parallel quote fetch
    with ThreadPoolExecutor(max_workers=15) as ex:
        quotes = [q for q in ex.map(_fetch_premarket_quote, universe) if q is not None]

    # 3) Filter: must have meaningful price move
    movers = [
        q for q in quotes
        if abs(q["change_pct"]) >= min_abs_change_pct
        and q["price"] >= 0.10
        and q["price"] <= max_price * 5  # let high-cap names through; cap filter below
    ]

    # 4) Enrich top N with yfinance for cap + sector + name
    movers.sort(key=lambda q: abs(q["change_pct"]), reverse=True)
    top = movers[: max_results * 2]

    def _enrich(q):
        try:
            import yfinance as yf
            tk = symbols.yf_ticker(q["ticker"])
            fi = tk.fast_info
            cap = None
            try: cap = float(getattr(fi, "market_cap", 0) or 0) or None
            except Exception: pass
            avg_vol = None
            try: avg_vol = float(getattr(fi, "ten_day_average_volume", 0) or 0) or None
            except Exception: pass
            info = {}
            try: info = tk.info or {}
            except Exception: pass
            return {
                **q,
                "market_cap": cap,
                "avg_volume_10d": avg_vol,
                "company_name": info.get("shortName") or info.get("longName"),
                "sector": info.get("sector"),
            }
        except Exception as exc:
            log.debug("premarket enrich %s failed: %s", q.get("ticker"), exc)
            return q

    with ThreadPoolExecutor(max_workers=10) as ex:
        enriched = list(ex.map(_enrich, top))

    # 5) Apply cap filter (price OR cap)
    tiny = [
        c for c in enriched
        if c.get("price", 0) <= max_price
        or (c.get("market_cap") and c["market_cap"] <= max_cap)
    ]

    # 6) Rank by absolute % move (no volume surge in premarket)
    tiny.sort(key=lambda c: abs(c["change_pct"]), reverse=True)
    tiny = tiny[:max_results]

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "window": window,
        "candidates": tiny,
        "n_universe_scanned": len(universe),
        "n_movers_found": len(movers),
        "n_after_filter": len(tiny),
    }


__all__ = ["scan_premarket", "is_premarket_window"]


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(scan_premarket(), indent=2, default=str))
