"""Per-stock supply / demand screen — Minervini *Trade Like a Stock Market
Wizard*, Chapter 10 "A Picture Is Worth a Million Dollars" (pp. 204-210).

This is the book-faithful, per-stock supply/demand read that the curated
dependency-graph / sector tabs never measured. It scores EVERY name in the
broad universe on the four forces the book describes:

  1. OVERHEAD SUPPLY  — volume that traded ABOVE the current price over the
     last year: "trapped buyers who bought around the stock's previous high
     point and are now sitting with a loss … look for a rally to sell"
     (p.204-205). A stock at a new high "has no overhead supply to contend
     with" (p.206); a deep correction (down 50-60%) is "failure-prone" because
     it is burdened with trapped buyers (p.210).

  2. SUPPLY ABSORPTION — volume drying up / price tightening: "A significant
     contraction in volume associated with tightness in price signals supply
     has stopped coming to market and the line of least resistance has been
     established" (p.205, Fig 10.8; p.206).

  3. DEMAND — accumulation, money-flow inflow, breakout/pocket-pivot volume
     (volume.py; book p.194 accumulation, p.203 breakout on expanding volume).

  4. DISTANCE FROM 52-WEEK HIGH — proximity to new-high ground (p.206-207).

Self-contained: reuses the pure functions sepa.volume.analyze /
sepa.vcp.detect and the cached daily bars. It does NOT touch the
contract-locked SEPA scanner. Cached + cron-warmed (the broad pass loads
~3.7k cached price frames).

Spec + page cites: docs/supply_demand/per_stock_methodology.md
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from sepa import prices, volume as volume_mod, vcp as vcp_mod, universe as universe_mod
from sepa import company_names

log = logging.getLogger("supply_demand.stocks")

# ── Thresholds (our codification — book gives the concepts, not the numbers) ──
LOOKBACK_DAYS        = 252     # ~1 trading year for the overhead-supply window
MIN_BARS             = 60      # need enough history to be meaningful
OVERHEAD_LOW_PCT     = 15.0    # ≤15% of last-year volume traded above → clear runway
OVERHEAD_HEAVY_PCT   = 40.0    # ≥40% trapped above → supply-burdened
DEEP_CORRECTION_PCT  = 50.0    # ≥50% below 52w high → deep correction, failure-prone (p.210)
NEAR_HIGH_PCT        = 15.0    # within 15% of the 52w high → near new-high ground
DIST_DAYS_HEAVY      = 8       # persistent distribution (matches volume.py backstop)

# Two-level cache, keyed by (mode, min_dollar_vol). L1 = in-process dict; L2 =
# Mongo (so a cron warm in a SEPARATE process populates the cache the API
# reads, and it survives API restarts). The screen is analytical, not a live
# quote feed, so a multi-hour TTL + a daily cron warm is plenty.
_CACHE_TTL_SEC = 3 * 60 * 60
_cache: dict = {}


def _cache_key(mode: str, min_dollar_vol: float) -> str:
    return f"{mode}:{int(min_dollar_vol)}"


def _cache_coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        return client[db]["stock_supply_demand_cache"]
    except Exception as exc:
        log.warning("supply/demand cache mongo unavailable: %s", exc)
        return None


def _mongo_get(key: str) -> Optional[dict]:
    coll = _cache_coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({"_id": key})
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


def _mongo_put(key: str, payload: dict):
    coll = _cache_coll()
    if coll is None:
        return
    try:
        coll.update_one(
            {"_id": key},
            {"$set": {"cached_at": datetime.now(timezone.utc), "payload": payload}},
            upsert=True,
        )
    except Exception:
        pass


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _overhead_supply_pct(df: pd.DataFrame) -> Optional[float]:
    """Fraction (0-100) of the last LOOKBACK_DAYS of volume that traded ABOVE
    the current close — i.e. the share of recent trading now sitting underwater
    (trapped buyers / overhead supply, book p.204-205).

    0 → at/above the period high (no overhead supply, p.206).
    High → most of the past year traded higher (heavy resistance).
    """
    if df is None or len(df) < MIN_BARS:
        return None
    w = df.iloc[-LOOKBACK_DAYS:]
    close = w["close"].astype(float)
    vol = w["volume"].astype(float)
    cur = float(close.iloc[-1])
    total = float(vol.sum())
    if total <= 0 or cur != cur:        # NaN guard
        return None
    above = float(vol[close > cur].sum())
    return round(100.0 * above / total, 1)


def _pct_below_52w_high(df: pd.DataFrame) -> Optional[float]:
    """How far below the trailing-252d high the current close sits (%). 0 = at
    a new high (no overhead supply, p.206)."""
    if df is None or len(df) < MIN_BARS:
        return None
    w = df["close"].iloc[-LOOKBACK_DAYS:].astype(float)
    hi = float(w.max())
    cur = float(w.iloc[-1])
    if hi <= 0:
        return None
    return round((1 - cur / hi) * 100, 1)


def _classify(overhead: Optional[float], pct_below_high: Optional[float],
              vol: dict) -> str:
    """The headline supply/demand state, book-faithful precedence."""
    strength = (vol or {}).get("accumulation_strength")
    drying   = bool((vol or {}).get("is_drying_up"))
    breakout = bool((vol or {}).get("high_vol_breakout") or (vol or {}).get("pocket_pivot"))
    distributing = (strength == "distributing")

    heavy_overhead = (
        (overhead is not None and overhead >= OVERHEAD_HEAVY_PCT)
        or (pct_below_high is not None and pct_below_high >= DEEP_CORRECTION_PCT)
    )
    low_overhead = (
        (overhead is not None and overhead <= OVERHEAD_LOW_PCT)
        or (pct_below_high is not None and pct_below_high <= NEAR_HIGH_PCT)
    )

    # Supply in control — active distribution, or trapped buyers above / deep
    # correction. "If the stock's price and volume don't quiet down … supply is
    # still coming to market and the stock is too risky." (p.206)
    if distributing or heavy_overhead:
        return "supply"
    # Demand in control — clear runway above the price (low overhead) AND a
    # positive demand read: accumulation (buying pressure), a volume-backed
    # breakout, or volume drying up (supply absorbed, p.205-206). Accumulation
    # IS demand, so it qualifies on its own — drying/breakout are not required.
    demand_confirmed = (strength in ("strong", "accumulating")) or breakout or drying
    if low_overhead and demand_confirmed:
        return "demand"
    return "churning"


def _demand_score(overhead: Optional[float], pct_below_high: Optional[float],
                  vol: dict) -> float:
    """0-100 ranking score, additive so it spreads across the universe instead
    of saturating. Components (max): overhead supply 30 · distance-from-high 20
    · demand/accumulation 25 · money flow 10 · absorption+breakout 15."""
    s = 0.0
    # Overhead supply — the primary SUPPLY force. Less trapped above = better.
    if overhead is not None:
        s += 30.0 * _clamp(1 - overhead / OVERHEAD_HEAVY_PCT, 0.0, 1.0)
    else:
        s += 15.0                                  # unknown → neutral half-credit
    # Distance from the 52w high — nearer new-high ground = better (p.206).
    if pct_below_high is not None:
        s += 20.0 * _clamp(1 - pct_below_high / 40.0, 0.0, 1.0)
    else:
        s += 10.0
    # Demand — accumulation is the core demand read.
    strength = (vol or {}).get("accumulation_strength")
    s += {"strong": 25.0, "accumulating": 15.0, "neutral": 5.0,
          "distributing": 0.0}.get(strength, 5.0)
    # Money flow (CMF) — independent confirmation.
    cmf = (vol or {}).get("cmf_signal")
    s += {"inflow": 10.0, "outflow": 0.0}.get(cmf, 5.0)
    # Supply absorption + demand events.
    if (vol or {}).get("is_drying_up"):            # supply stopped coming (p.205-206)
        s += 8.0
    if (vol or {}).get("high_vol_breakout") or (vol or {}).get("pocket_pivot"):
        s += 7.0
    return round(_clamp(s, 0.0, 100.0), 1)


def analyze_symbol(symbol: str) -> Optional[dict]:
    """Full per-stock supply/demand record, or None if insufficient data."""
    df = prices.load_prices(symbol)
    if df is None or len(df) < MIN_BARS:
        return None
    try:
        overhead = _overhead_supply_pct(df)
        pct_below_high = _pct_below_52w_high(df)
        vol = volume_mod.analyze(df) or {}
        vcp_info = vcp_mod.detect(df) or {}
    except Exception as exc:
        log.debug("supply/demand analyze failed for %s: %s", symbol, exc)
        return None

    last_close = float(df["close"].iloc[-1])
    last_vol = float(df["volume"].iloc[-1]) if "volume" in df else 0.0
    dollar_vol = vol.get("avg_vol_50")
    dollar_vol = float(dollar_vol) * last_close if dollar_vol else last_close * last_vol

    state = _classify(overhead, pct_below_high, vol)
    score = _demand_score(overhead, pct_below_high, vol)

    return {
        "symbol": symbol,
        "name": company_names.name_for(symbol) or symbol,
        "last_close": round(last_close, 2),
        "state": state,                                  # demand | supply | churning
        "demand_score": score,
        # Supply
        "overhead_supply_pct": overhead,                 # NEW (p.204-205)
        "pct_below_52w_high": pct_below_high,            # p.206-207
        "distribution_days_25": vol.get("distribution_days_25"),
        # Absorption (p.205-206)
        "is_drying_up": vol.get("is_drying_up"),
        "vol_dryup": vol.get("vol_dryup"),
        "n_contractions": vcp_info.get("n_contractions"),
        "has_base": vcp_info.get("has_base"),
        "volume_drying": vcp_info.get("volume_drying"),
        # Demand (p.194, 203)
        "accumulation_strength": vol.get("accumulation_strength"),
        "up_down_vol_ratio": vol.get("up_down_vol_ratio"),
        "cmf_signal": vol.get("cmf_signal"),
        "high_vol_breakout": vol.get("high_vol_breakout"),
        "pocket_pivot": vol.get("pocket_pivot"),
        # Liquidity (so the FE can demote thin tape, consistent w/ scanner p.195)
        "dollar_vol": round(dollar_vol) if dollar_vol else None,
    }


def screen(mode: str = "broad", min_dollar_vol: float = 3_000_000.0,
           limit: Optional[int] = None, force: bool = False) -> dict:
    """Run the per-stock supply/demand screen across `mode`'s universe.

    Returns {"rows": [...], "counts": {...}, "n": int, "mode": str} sorted by
    demand_score desc. Cached `_CACHE_TTL_SEC`; pass force=True to recompute.
    """
    key = (mode, min_dollar_vol)
    if not force:
        # L1 — in-process.
        cached = _cache.get(key)
        if cached and (time.time() - cached["ts"]) < _CACHE_TTL_SEC:
            out = dict(cached["data"]); out["cached"] = True
            return _apply_limit(out, limit)
        # L2 — Mongo (populated by the cron warm / another worker).
        mdoc = _mongo_get(_cache_key(mode, min_dollar_vol))
        if mdoc:
            _cache[key] = {"data": mdoc, "ts": time.time()}
            out = dict(mdoc); out["cached"] = True
            return _apply_limit(out, limit)

    syms = universe_mod.load_universe(mode)
    rows: list[dict] = []
    for sym in syms:
        rec = analyze_symbol(sym)
        if rec is None:
            continue
        if min_dollar_vol and (rec["dollar_vol"] or 0) < min_dollar_vol:
            continue
        rows.append(rec)

    rows.sort(key=lambda r: -r["demand_score"])
    counts = {
        "demand":   sum(1 for r in rows if r["state"] == "demand"),
        "supply":   sum(1 for r in rows if r["state"] == "supply"),
        "churning": sum(1 for r in rows if r["state"] == "churning"),
    }
    data = {"rows": rows, "counts": counts, "n": len(rows), "mode": mode, "cached": False}
    _cache[key] = {"data": data, "ts": time.time()}
    _mongo_put(_cache_key(mode, min_dollar_vol), data)
    log.info("supply/demand screen: %d names (mode=%s) demand=%d supply=%d churning=%d",
             len(rows), mode, counts["demand"], counts["supply"], counts["churning"])
    return _apply_limit(dict(data), limit)


def _apply_limit(out: dict, limit: Optional[int]) -> dict:
    if limit and out.get("rows"):
        out = {**out, "rows": out["rows"][:limit]}
    return out


if __name__ == "__main__":
    # Cron warm: recompute + persist to Mongo so the API serves it instantly.
    #   python -m supply_demand.stock_supply_demand --mode broad
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Warm the per-stock supply/demand screen cache.")
    ap.add_argument("--mode", default="broad")
    ap.add_argument("--min-dollar-vol", type=float, default=3_000_000.0)
    args = ap.parse_args()
    t0 = time.time()
    out = screen(mode=args.mode, min_dollar_vol=args.min_dollar_vol, force=True)
    print(f"warmed supply/demand [{args.mode}]: {out['n']} names, counts={out['counts']} "
          f"in {time.time() - t0:.1f}s")
