"""Trailing-twelve-month revenue dollars, Mongo-cached.

Built for the Under Value board (Ajay 2026-08-28: "undervalued stocks
whose sales are incredible but their comparitive stock value is less ...
huge backlog or contracts and exponential revenue"). The weekly research
cache stores sales GROWTH (%, tiers) but discards the dollar level, and a
price-to-sales read needs dollars.

One Mongo doc per symbol, TTL 7 days — revenue changes quarterly, so a
week-old figure is current. Reads are one `$in` query; fills happen in a
time-boxed pool at board build (the attach_velocity discipline: degrade
to None, never block a request path) and via the Sunday cron warm that
follows the research refresh.

Source: yfinance `Ticker.info["totalRevenue"]` — the same library the
research builder already leans on, throttle-friendly at warm cadence.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

log = logging.getLogger("sepa.rev_ttm")

TTL_SEC = 7 * 24 * 3600
_FILL_BOX_SEC = 8.0
_FILL_WORKERS = 8


def _coll():
    from portfolio.store import _get_db
    try:
        return _get_db().rev_ttm_cache
    except Exception:                                          # pragma: no cover
        return None


def _fetch_one(symbol: str) -> Optional[float]:
    """One TTM-revenue fetch. None on any failure — never raises."""
    try:
        from sepa.symbols import yf_ticker
        v = (yf_ticker(symbol).info or {}).get("totalRevenue")
        return float(v) if v and v > 0 else None
    except Exception:
        return None


def bulk(symbols: list, *, fill_missing: bool = True) -> dict:
    """{symbol: ttm_revenue_dollars} for every symbol with a fresh cached
    value; optionally fills misses in a time-boxed pool (partial fills are
    fine — the next 5-minute board refresh picks up the rest)."""
    syms = sorted({str(s).upper() for s in (symbols or []) if s})
    coll = _coll()
    out: dict = {}
    if coll is None or not syms:
        return out
    now = time.time()
    try:
        for doc in coll.find({"symbol": {"$in": syms}},
                             {"_id": 0, "symbol": 1, "rev_ttm": 1, "cached_at": 1}):
            if (now - (doc.get("cached_at") or 0)) < TTL_SEC and doc.get("rev_ttm"):
                out[doc["symbol"]] = float(doc["rev_ttm"])
    except Exception as exc:                                   # pragma: no cover
        log.warning("rev_ttm: bulk read failed: %s", exc)
        return out

    missing = [s for s in syms if s not in out]
    if not fill_missing or not missing:
        return out
    deadline = now + _FILL_BOX_SEC
    with ThreadPoolExecutor(max_workers=_FILL_WORKERS) as pool:
        futs = {pool.submit(_fetch_one, s): s for s in missing}
        for fut, sym in futs.items():
            budget = deadline - time.time()
            if budget <= 0:
                break
            try:
                v = fut.result(timeout=budget)
            except Exception:
                continue
            if v:
                out[sym] = v
                try:
                    coll.update_one({"symbol": sym},
                                    {"$set": {"rev_ttm": v, "cached_at": time.time()}},
                                    upsert=True)
                except Exception:                              # pragma: no cover
                    pass
        for fut in futs:
            fut.cancel()
    return out


def warm(symbols: list) -> dict:
    """Cron entrypoint — no time box, throttled walk for the Sunday warm."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "no mongo"}
    now = time.time()
    fresh = 0
    try:
        fresh_syms = {d["symbol"] for d in coll.find(
            {"symbol": {"$in": [s.upper() for s in symbols]},
             "cached_at": {"$gte": now - TTL_SEC}}, {"symbol": 1})}
    except Exception:
        fresh_syms = set()
    filled = 0
    for s in symbols:
        s = str(s).upper()
        if s in fresh_syms:
            fresh += 1
            continue
        v = _fetch_one(s)
        if v:
            try:
                coll.update_one({"symbol": s},
                                {"$set": {"rev_ttm": v, "cached_at": time.time()}},
                                upsert=True)
                filled += 1
            except Exception:                                  # pragma: no cover
                pass
        time.sleep(1.0)                       # yfinance throttle etiquette
    return {"ok": True, "already_fresh": fresh, "filled": filled}
