"""Demand-zone bands — Minervini basing (Ch.10 "A Picture Is Worth a Million
Dollars", pp. 197-213).

A *demand zone* is the price band of a stock's most-recent consolidation base:
the floor where strong hands accumulate, up to the pivot/breakout line. The book
describes the forces; the band itself is read straight off the contract-locked
`sepa.vcp.detect` so this module introduces NO new base-detection thresholds —
it is a thin, faithful derivation on top of the locked VCP detector.

  • zone_low  = `base_low`  — the deepest trough of the base. Fig 10.8 (p.205)
    marks this floor as where "bottom fishers achieve healthy gains" — i.e.
    where supply is absorbed and strong holders accumulate. You want the weak
    holders out before you buy (p.206).
  • zone_high = `pivot_buy_price` — the top of the final contraction, the pivot
    where "the line of least resistance has been established" (p.205-206) and a
    volume-backed move begins the advance (p.203).
  • depth class — how far the base corrected, the book's validity gate:
    "Most constructive set-ups correct between 10 percent and 35 percent" and
    "I rarely buy a stock that has corrected 60 percent or more" (p.211); deep
    corrections are explicitly failure-prone (p.210).

Where price sits vs. the band:
  • in_zone  — price is INSIDE [zone_low, zone_high]: it has pulled back into /
    is consolidating in the demand area (the actionable "pullback" case that
    cross-links to the leaderboard).
  • above    — price broke out / is extended above the pivot; the zone now sits
    BELOW as support (the common case for a leader mid-advance).
  • below    — price is under the base floor (base broke down).

Universe = the leaderboard + the day-trading watchlist (the two lists the user
asked for). Small (~40 names), so it recomputes in seconds and is cached 3h.

Educational — a structural read of where demand showed up. NOT a buy signal and
NOT advice.

Spec + page cites: docs/supply_demand/demand_zones_methodology.md
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from sepa import prices, vcp as vcp_mod, company_names
from . import stock_supply_demand as sd

log = logging.getLogger("supply_demand.demand_zones")

# ── Depth-class bands — our codification of the book's correction limits ──────
# Book p.211: "Most constructive set-ups correct between 10 percent and 35
# percent"; ">= 60 percent" is failure-prone (p.210-211). The 8% shallow floor
# mirrors sepa.vcp's existing `good_depth` lower bound (a sub-8% "base" is a
# flat low-vol drift, not a real correction to accumulate from).
DEPTH_SHALLOW_MAX      = 8.0     # < this → shallow (barely a base)
DEPTH_CONSTRUCTIVE_MAX = 35.0    # 8-35 → constructive (p.211)
DEPTH_FAILURE_PRONE    = 60.0    # >= this → failure-prone (p.211); 35-60 → deep

# "Near" the zone = within this % of the band edge (for the summary count).
NEAR_PCT = 8.0

# How many leaderboard names to pull. The leaderboard surfaces ~12 by default;
# 30 covers the page + honourable mentions so "all in leaderboard" is honoured.
LEADERBOARD_N = 30

_CACHE_TTL_SEC = 3 * 60 * 60
_cache: dict = {}

DISCLAIMER = (
    "Demand zones are a structural read of the most-recent consolidation base "
    "(Minervini Ch.10) — where demand previously absorbed supply. Educational, "
    "not a buy signal and not advice."
)


def _depth_class(depth_pct: Optional[float]) -> Optional[str]:
    """Classify a base's correction depth per the book's validity limits
    (p.210-211). Pure + locked by the contract test."""
    if depth_pct is None:
        return None
    if depth_pct < DEPTH_SHALLOW_MAX:
        return "shallow"
    if depth_pct <= DEPTH_CONSTRUCTIVE_MAX:
        return "constructive"
    if depth_pct < DEPTH_FAILURE_PRONE:
        return "deep"
    return "failure_prone"


def _zone_geometry(last_close: Optional[float], zone_low: Optional[float],
                   zone_high: Optional[float]) -> dict:
    """Where the current price sits relative to the [low, high] band. Pure.

    Returns in_zone / zone_status (in|above|below) / signed distance_to_zone_pct
    (0 inside; +above the pivot; -below the floor) / zone_position_pct (0 at the
    floor → 100 at the pivot, only when inside)."""
    out = {"in_zone": False, "zone_status": None,
           "distance_to_zone_pct": None, "zone_position_pct": None}
    if not last_close or not zone_low or not zone_high or zone_high <= zone_low:
        return out
    if last_close < zone_low:
        out["zone_status"] = "below"
        out["distance_to_zone_pct"] = round((last_close / zone_low - 1) * 100, 1)
    elif last_close > zone_high:
        out["zone_status"] = "above"
        out["distance_to_zone_pct"] = round((last_close / zone_high - 1) * 100, 1)
    else:
        out["in_zone"] = True
        out["zone_status"] = "in"
        out["distance_to_zone_pct"] = 0.0
        span = zone_high - zone_low
        out["zone_position_pct"] = round(100.0 * (last_close - zone_low) / span, 1)
    return out


def zone_for_symbol(symbol: str, source: str = "leaderboard") -> Optional[dict]:
    """Compute one name's demand-zone record, or None if there isn't enough
    history. `source` tags which list the name came from (leaderboard|day|both)."""
    sym = (symbol or "").upper()
    if not sym:
        return None
    df = prices.load_prices(sym)
    if df is None or len(df) < sd.MIN_BARS:
        return None
    last_close = round(float(df["close"].iloc[-1]), 2)

    try:
        vcp = vcp_mod.detect(df) or {}
    except Exception as exc:
        log.debug("demand-zones: vcp.detect failed for %s: %s", sym, exc)
        vcp = {}

    # Supply/demand context (state + score) — canonical read, best-effort.
    try:
        ctx = sd.analyze_symbol(sym) or {}
    except Exception:
        ctx = {}

    zone_low = vcp.get("base_low")
    zone_high = vcp.get("pivot_buy_price")
    base_high = vcp.get("base_high")
    depth = vcp.get("base_depth_pct")
    has_zone = (zone_low is not None and zone_high is not None and zone_high > zone_low)

    geo = _zone_geometry(last_close, zone_low, zone_high)
    depth_class = _depth_class(depth) if has_zone else None

    return {
        "symbol": sym,
        "name": (ctx.get("name") if ctx else None) or company_names.name_for(sym) or sym,
        "source": source,
        "last_close": last_close,
        "has_zone": has_zone,
        # The band (Minervini basing).
        "zone_low": zone_low,                          # base floor (p.205 Fig 10.8)
        "zone_high": zone_high,                        # pivot / breakout line (p.203)
        "base_high": base_high,                        # left-side high of the base
        "base_depth_pct": depth,
        "depth_class": depth_class,                    # shallow|constructive|deep|failure_prone (p.211)
        # VCP quality context (already book-cited in vcp.py).
        "n_contractions": vcp.get("n_contractions"),
        "final_contraction_pct": vcp.get("final_contraction_pct"),
        "tightness": vcp.get("tightness"),
        "tightness_band": vcp.get("tightness_band"),
        "volume_drying": vcp.get("volume_drying"),
        "has_base": vcp.get("has_base"),
        "pivot_buy_price": vcp.get("pivot_buy_price"),
        "suggested_stop": vcp.get("suggested_stop"),
        # Where price sits vs the band.
        "in_zone": geo["in_zone"],
        "zone_status": geo["zone_status"],             # in|above|below
        "zone_position_pct": geo["zone_position_pct"],
        "distance_to_zone_pct": geo["distance_to_zone_pct"],
        # A pullback INTO a still-constructive base — the actionable cross-link.
        "pulled_back": bool(geo["in_zone"] and depth_class in ("shallow", "constructive")),
        # Supply/demand context.
        "state": (ctx.get("state") if ctx else None),
        "demand_score": (ctx.get("demand_score") if ctx else None),
        "dollar_vol": (ctx.get("dollar_vol") if ctx else None),
    }


def _universe() -> list[tuple[str, str]]:
    """The two lists the user asked for: leaderboard + day-trading watchlist.
    Returns [(symbol, source)] deduped; source = leaderboard|day|both."""
    src: dict[str, set] = {}
    try:
        from sepa.leaderboard import leaderboard
        lb = leaderboard(n=LEADERBOARD_N) or {}
        for r in (lb.get("leaders") or []):
            s = (r.get("symbol") or "").upper()
            if s:
                src.setdefault(s, set()).add("leaderboard")
    except Exception as exc:
        log.warning("demand-zones: leaderboard universe unavailable: %s", exc)
    try:
        from daytrading.api import DEFAULT_WATCHLIST
        for s in DEFAULT_WATCHLIST:
            su = (s or "").upper()
            if su:
                src.setdefault(su, set()).add("day")
    except Exception as exc:
        log.warning("demand-zones: day watchlist unavailable: %s", exc)

    out: list[tuple[str, str]] = []
    for s, kinds in src.items():
        source = "both" if len(kinds) > 1 else next(iter(kinds))
        out.append((s, source))
    return out


def _sort_key(r: dict):
    # Names with a real zone first; among those, in-zone (pullbacks) first;
    # then nearest to the band by absolute distance.
    has = 0 if r.get("has_zone") else 1
    inz = 0 if r.get("in_zone") else 1
    d = r.get("distance_to_zone_pct")
    dist = abs(d) if d is not None else 9.0e9
    return (has, inz, dist)


def compute_zones(force: bool = False) -> dict:
    """Demand-zone records for the leaderboard + day-trading universe, sorted
    in-zone/nearest first. Cached `_CACHE_TTL_SEC`; pass force=True to recompute."""
    if not force:
        c = _cache.get("data")
        if c and (time.time() - c["ts"]) < _CACHE_TTL_SEC:
            return {**c["data"], "cached": True}

    rows: list[dict] = []
    for sym, source in _universe():
        try:
            rec = zone_for_symbol(sym, source)
        except Exception as exc:
            log.debug("demand-zones: %s failed: %s", sym, exc)
            rec = None
        if rec:
            rows.append(rec)

    rows.sort(key=_sort_key)
    counts = {
        "in_zone": sum(1 for r in rows if r["in_zone"]),
        "near": sum(1 for r in rows
                    if (not r["in_zone"] and r.get("distance_to_zone_pct") is not None
                        and abs(r["distance_to_zone_pct"]) <= NEAR_PCT)),
        "no_base": sum(1 for r in rows if not r["has_zone"]),
    }
    data = {
        "rows": rows,
        "counts": counts,
        "n": len(rows),
        "as_of": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
        "cached": False,
    }
    _cache["data"] = {"ts": time.time(), "data": data}
    log.info("demand-zones: %d names, in_zone=%d near=%d no_base=%d",
             len(rows), counts["in_zone"], counts["near"], counts["no_base"])
    return data
