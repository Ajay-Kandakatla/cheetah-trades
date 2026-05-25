"""Real-time money flow snapshot for the dependency graph.

For each ticker in the supply/demand graph, fetch:
  - last price
  - previous close
  - day's change %
  - day's volume
  - day's $ volume (proxy for "money flowing into the name")

We hit Massive's bulk snapshot endpoint (one HTTP call covers all tickers)
for efficiency, then fall back to per-ticker quotes for any names the bulk
endpoint missed.

Cache 60s during market hours; 5min after-hours; 24h on weekends.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests

log = logging.getLogger("supply_demand.flow")

_CACHE_KEY = "_flow_snapshot"
_CACHE_TTL_LIVE = 60          # 60s during market hours
_CACHE_TTL_AFTER = 5 * 60     # 5min after hours
_CACHE_TTL_WEEKEND = 24 * 60 * 60  # 24h on weekends

# Module-level in-memory cache (per-process). Restarts wipe it; that's fine —
# the data is rebuilt in <2s.
_cache: dict = {"data": None, "ts": 0.0, "ttl": _CACHE_TTL_LIVE}


def _now_et() -> datetime:
    """Return current time in America/New_York."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        # zoneinfo missing on older Pythons — naive ET fallback (UTC-5)
        return datetime.now(timezone.utc).astimezone()


def market_status() -> dict:
    """Compute current market status — open/pre/after/closed/weekend.

    Returns a dict with `state`, `next_event`, `is_live`, and human label.
    """
    n = _now_et()
    weekday = n.weekday()  # 0=Mon, 6=Sun

    if weekday >= 5:
        return {
            "state": "weekend",
            "is_live": False,
            "label": "Markets closed (weekend)",
            "next_event": "Monday 9:30 ET",
        }

    cur_min = n.hour * 60 + n.minute
    pre_open = 4 * 60          # 4am ET — pre-market start
    open_min = 9 * 60 + 30     # 9:30 ET — regular session
    close_min = 16 * 60        # 4:00 ET — close
    after_close = 20 * 60      # 8pm ET — after-hours end

    if open_min <= cur_min < close_min:
        return {
            "state": "open",
            "is_live": True,
            "label": "Markets open",
            "next_event": "4:00 PM ET close",
        }
    if pre_open <= cur_min < open_min:
        return {
            "state": "pre",
            "is_live": False,
            "label": "Pre-market",
            "next_event": "9:30 AM ET open",
        }
    if close_min <= cur_min < after_close:
        return {
            "state": "after",
            "is_live": False,
            "label": "After-hours",
            "next_event": "Tomorrow 9:30 ET",
        }
    return {
        "state": "closed",
        "is_live": False,
        "label": "Markets closed",
        "next_event": "Tomorrow 9:30 ET",
    }


def _ttl_for_status(status: dict) -> int:
    if status["state"] == "open":
        return _CACHE_TTL_LIVE
    if status["state"] == "weekend":
        return _CACHE_TTL_WEEKEND
    return _CACHE_TTL_AFTER


# --- Massive bulk snapshot (preferred — one call for all tickers) -------

def _fetch_massive_bulk(tickers: list[str]) -> dict[str, dict]:
    """Bulk fetch via Massive snapshot endpoint. Returns {ticker: snapshot}.

    Massive snapshot includes:
      - lastTrade.p (last price)
      - day.{o,h,l,c,v} (day OHLC + volume)
      - prevDay.c (previous close)
      - todaysChange / todaysChangePerc
    """
    key = os.getenv("MASSIVE_API_KEY")
    if not key:
        return {}

    out: dict[str, dict] = {}

    # Massive caps tickers per call ~250; we have ~56 so one call works.
    url = "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers"
    try:
        r = requests.get(
            url,
            params={"tickers": ",".join(tickers), "apiKey": key},
            timeout=8,
        )
        if r.status_code != 200:
            log.warning("massive bulk snapshot HTTP %s: %s", r.status_code, r.text[:160])
            return {}
        body = r.json() or {}
        for snap in body.get("tickers", []):
            t = snap.get("ticker")
            if not t:
                continue
            day = snap.get("day", {}) or {}
            prev = snap.get("prevDay", {}) or {}
            last_trade = snap.get("lastTrade", {}) or {}

            price = last_trade.get("p") or day.get("c") or prev.get("c")
            prev_close = prev.get("c")
            volume = day.get("v") or 0
            change_pct = snap.get("todaysChangePerc")
            if change_pct is None and price and prev_close:
                change_pct = (price - prev_close) / prev_close * 100

            if not price or not prev_close:
                continue

            out[t.upper()] = {
                "ticker": t.upper(),
                "price": float(price),
                "prev_close": float(prev_close),
                "change_pct": round(float(change_pct or 0), 2),
                "volume": int(volume or 0),
                "dollar_volume": int((volume or 0) * (price or 0)),
                "day_high": float(day.get("h") or 0),
                "day_low": float(day.get("l") or 0),
                "day_open": float(day.get("o") or 0),
                "ts_unix_ns": last_trade.get("t"),
            }
    except Exception as exc:
        log.warning("massive bulk snapshot failed: %s", exc)
    return out


# --- yfinance fallback (per-ticker, for any Massive misses) -------------

def _fetch_yfinance_fallback(tickers: list[str]) -> dict[str, dict]:
    """Per-ticker yfinance fallback. Slower (~0.3s/ticker) so only used for
    names Massive didn't return (e.g. foreign tickers like ASML, TSM, NVO)."""
    out: dict[str, dict] = {}
    try:
        import yfinance as yf
        # Multi-ticker download is much faster than per-ticker
        tk_str = " ".join(tickers)
        from concurrent.futures import ThreadPoolExecutor

        def _one(t):
            try:
                tk = yf.Ticker(t)
                fi = tk.fast_info
                last = fi.last_price
                prev = fi.previous_close
                vol = fi.last_volume or 0
                if not last or not prev:
                    return None
                return {
                    "ticker": t.upper(),
                    "price": float(last),
                    "prev_close": float(prev),
                    "change_pct": round((last - prev) / prev * 100, 2),
                    "volume": int(vol),
                    "dollar_volume": int(vol * last),
                    "day_high": float(getattr(fi, "day_high", 0) or 0),
                    "day_low": float(getattr(fi, "day_low", 0) or 0),
                    "day_open": float(getattr(fi, "open", 0) or 0),
                    "ts_unix_ns": None,
                }
            except Exception as exc:
                log.warning("yfinance flow fallback failed for %s: %s", t, exc)
                return None

        with ThreadPoolExecutor(max_workers=10) as ex:
            for r in ex.map(_one, tickers):
                if r:
                    out[r["ticker"]] = r
    except Exception as exc:
        log.warning("yfinance bulk fallback failed: %s", exc)
    return out


# --- Public API ---------------------------------------------------------

def get_flow_snapshot(force: bool = False) -> dict:
    """Return per-ticker flow snapshot for every node in the dependency graph.

    Output shape:
      {
        as_of: ISO timestamp,
        market: {state, is_live, label, next_event},
        tickers: [{ticker, price, prev_close, change_pct, volume,
                   dollar_volume, day_high, day_low, day_open}, ...],
        leaders: {top_inflow: [...], top_outflow: [...]},  // sorted by change_pct
        totals: {n_up, n_down, n_flat, total_dollar_volume},
        cached: bool,
      }
    """
    status = market_status()
    ttl = _ttl_for_status(status)
    age = time.time() - _cache["ts"]
    if not force and _cache["data"] is not None and age < ttl:
        out = dict(_cache["data"])
        out["cached"] = True
        out["cache_age_sec"] = round(age)
        return out

    # Build ticker list from the graph
    from .dependencies import NODES
    tickers = [n["ticker"] for n in NODES]

    # 1) Bulk via Massive
    snapshots = _fetch_massive_bulk(tickers)

    # 2) Fall back to yfinance for any missing
    missing = [t for t in tickers if t not in snapshots]
    if missing:
        log.info("flow: %d tickers missing from Massive, falling back to yfinance: %s",
                 len(missing), missing[:10])
        snapshots.update(_fetch_yfinance_fallback(missing))

    # 2.5) Multi-day accumulation/distribution scores (Chaikin Money Flow
    #      over 10 sessions). 1h cached, so cheap to call every flow refresh.
    try:
        from .accumulation import get_accumulation_scores
        accum_scores = get_accumulation_scores(tickers)
    except Exception as exc:
        log.warning("accumulation fetch failed (continuing without): %s", exc)
        accum_scores = {}

    # Augment each snapshot with its accumulation signal
    for t, snap in snapshots.items():
        a = accum_scores.get(t)
        if a:
            snap["accumulation_score"] = a.get("score")
            snap["accumulation_label"] = a.get("label")
        else:
            snap["accumulation_score"] = None
            snap["accumulation_label"] = None

    # 3) Sort + leaders
    flow_list = list(snapshots.values())
    flow_list.sort(key=lambda x: x.get("change_pct") or 0, reverse=True)

    n_up = sum(1 for f in flow_list if (f.get("change_pct") or 0) > 0.1)
    n_down = sum(1 for f in flow_list if (f.get("change_pct") or 0) < -0.1)
    n_flat = len(flow_list) - n_up - n_down
    total_dv = sum(f.get("dollar_volume", 0) for f in flow_list)

    # Multi-day accumulation/distribution counts (independent of today's move)
    n_accum = sum(1 for f in flow_list if (f.get("accumulation_score") or 0) >= 30)
    n_strong_accum = sum(1 for f in flow_list if (f.get("accumulation_score") or 0) >= 60)
    n_dist = sum(1 for f in flow_list if (f.get("accumulation_score") or 0) <= -30)
    n_strong_dist = sum(1 for f in flow_list if (f.get("accumulation_score") or 0) <= -60)

    top_inflow = flow_list[:5]
    top_outflow = flow_list[-5:][::-1]  # worst first

    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "market": status,
        "tickers": flow_list,
        "leaders": {
            "top_inflow": top_inflow,
            "top_outflow": top_outflow,
        },
        "totals": {
            "n_total": len(flow_list),
            "n_up": n_up,
            "n_down": n_down,
            "n_flat": n_flat,
            "total_dollar_volume": total_dv,
            "n_accumulating": n_accum,
            "n_strong_accumulation": n_strong_accum,
            "n_distributing": n_dist,
            "n_strong_distribution": n_strong_dist,
        },
        "cached": False,
        "cache_age_sec": 0,
    }

    _cache["data"] = payload
    _cache["ts"] = time.time()
    _cache["ttl"] = ttl
    return payload


__all__ = ["get_flow_snapshot", "market_status"]


if __name__ == "__main__":
    # Smoke test: python -m supply_demand.flow
    import json
    print(json.dumps(get_flow_snapshot(force=True), indent=2, default=str))
