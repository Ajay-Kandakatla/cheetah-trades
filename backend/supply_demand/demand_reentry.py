"""Demand-zone RE-ENTRY scan — S&P 500 names that have pulled back DOWN into a
tested demand band while the uptrend is still intact.

Ajay 2026-08-13: "update my Supply and demand page with stocks that entering
back in to demand zones … scan only S&P 500 stocks for this."

WHAT MAKES THIS DIFFERENT FROM `price_zones`
--------------------------------------------
`price_zones.py` answers "where are this ticker's bands right now?" — a
snapshot. This module answers a *transition* question: **did price come back
down INTO a demand band it had already left?** A name that has simply been
sitting inside a band for months is not "entering back in"; a name that ran
+18% above the band and has now returned to it is.

METHOD NOTE — this is a PRAGMATIC price-structure read, **not** a named book
methodology. Every threshold below is a CONFIGURED house value. The one
exception is the trend gate, which reuses the contract-locked Minervini trend
template (`sepa.trend_template`) rather than inventing a trend rule, and the
stop sanity cap, which reuses `trading.risk_rules.ABS_MAX_STOP_PCT`.
Decision-support only — NOT a buy signal and NOT financial advice.

WHY THE BANDS ARE WIDER HERE
----------------------------
The /zones page defaults (`ZONE_MERGE_PCT` 1.75, `ZONE_HALF_WIDTH_PCT` 0.6)
produce ~1%-wide lines. Measured 2026-08-13 across the S&P 500, those thin
bands made "re-entry" meaningless — 21 hits, almost all utilities, most of them
1 bar after price crossed a band 0.5% wide. That is noise, not demand. A
tradeable zone is a band you can put a stop underneath, so this module passes
wider geometry (merge 4.0%, half-width 1.75%, swing window 5) via the optional
knobs on `price_zones.compute`. Defaults elsewhere are untouched.

WHY THE TREND GATE
------------------
A pullback into support inside a DOWNtrend is a falling knife, not a demand
zone. Gating on the Minervini trend template (>= MIN_TREND_CHECKS of 8) cut the
measured candidate pool roughly in half and removed the utility-drift names.

Spec + measured tuning notes: docs/supply_demand/demand_reentry_methodology.md
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from sepa import prices, trend_template, universe as universe_mod, company_names
from . import price_zones

log = logging.getLogger("supply_demand.demand_reentry")

# ── Zone geometry (house values — see module docstring for the measurement) ────
SWING_WINDOW    = 5
MERGE_PCT       = 4.0
HALF_WIDTH_PCT  = 1.75

# ── Re-entry qualification (all CONFIGURED house values) ──────────────────────
REENTRY_LOOKBACK_BARS = 40    # window in which price must have been above the band
MIN_RISE_ABOVE_PCT    = 5.0   # it must have traded >= this % above the band top
MIN_TOUCHES           = 2     # the band must have been tested at least twice
MIN_ZONE_STRENGTH     = 40.0  # 0-100 price_zones strength (tests + volume)
MIN_TREND_CHECKS      = 6     # of trend_template's 8 Stage-2 criteria

# Stop sits this far under the band floor (room for a wick through support).
STOP_BUFFER_PCT = 1.5

MIN_BARS = 220                # trend_template needs ~1y; 220 is its own floor

_CACHE_TTL_SEC = 3 * 60 * 60
_cache: dict = {}

DISCLAIMER = (
    "Demand-zone re-entry is a configured, pragmatic price-structure read (NOT a "
    "book method) of names that pulled back into a tested support band while the "
    "trend held. Decision-support only — not a buy signal and not advice."
)


def zone_geom() -> dict:
    """The wider geometry this module hands to `price_zones.compute`."""
    return {"swing_window": SWING_WINDOW, "merge_pct": MERGE_PCT,
            "half_width_pct": HALF_WIDTH_PCT}


# ── Pure helpers (unit-tested directly) ───────────────────────────────────────
def reentry_read(closes: list[float], zone_hi: float, zone_lo: float,
                 last_price: float,
                 lookback: int = REENTRY_LOOKBACK_BARS,
                 min_rise_pct: float = MIN_RISE_ABOVE_PCT) -> dict:
    """Did price leave this band above and come back into it? PURE.

    Returns is_reentry plus the supporting evidence: how far above the band top
    it got (`fell_from_pct`) and how many bars ago it was last above
    (`bars_since_above`). Requires price to be INSIDE the band now — a name
    below the floor has broken support, which is the opposite of this signal.
    """
    out = {"is_reentry": False, "fell_from_pct": None,
           "bars_since_above": None, "in_band": False}
    if not closes or not zone_hi or not zone_lo or zone_hi <= zone_lo:
        return out
    out["in_band"] = bool(zone_lo <= last_price <= zone_hi)
    if not out["in_band"]:
        return out

    window = closes[-int(lookback):] if lookback else closes
    if not window:
        return out
    peak = max(window)
    rise = (peak / zone_hi - 1.0) * 100.0
    out["fell_from_pct"] = round(rise, 1)

    above_idx = [i for i, c in enumerate(window) if c > zone_hi]
    if above_idx:
        out["bars_since_above"] = int(len(window) - 1 - above_idx[-1])
    out["is_reentry"] = bool(rise >= min_rise_pct and above_idx)
    return out


def trade_plan(last_price: float, entry_zone: Optional[dict],
               resistance: Optional[dict],
               stop_buffer_pct: float = STOP_BUFFER_PCT) -> Optional[dict]:
    """Entry / stop / target for a demand-zone play. PURE.

    entry area = the demand band itself (buy into support, not through it)
    stop       = `stop_buffer_pct` under the band floor — the level that says
                 "demand failed", so the reason for the trade is gone
    target     = the LOW of the nearest overhead supply band: the first place
                 sellers are known to be waiting, not a hoped-for extension

    `risk_exceeds_max` flags a stop wider than the house/book hard cap
    (`trading.risk_rules.ABS_MAX_STOP_PCT`, the p.299/p.301 cap) — such a plan
    is not sized down here, it is flagged so the UI can say "too wide".
    """
    if not last_price or not entry_zone:
        return None
    lo = entry_zone.get("lo")
    hi = entry_zone.get("hi")
    if not lo or not hi or hi <= lo:
        return None

    stop = round(lo * (1.0 - stop_buffer_pct / 100.0), 2)
    risk_pct = round((last_price - stop) / last_price * 100.0, 1) if last_price else None

    target = None
    reward_pct = None
    if resistance and resistance.get("lo") and resistance["lo"] > last_price:
        target = round(float(resistance["lo"]), 2)
        reward_pct = round((target - last_price) / last_price * 100.0, 1)

    rr = None
    if target is not None and last_price > stop:
        rr = round((target - last_price) / (last_price - stop), 2)

    try:
        from trading.risk_rules import ABS_MAX_STOP_PCT as _MAX
    except Exception:
        _MAX = 10.0

    return {
        "entry_low": round(float(lo), 2),
        "entry_high": round(float(hi), 2),
        "entry_ref": round(float(last_price), 2),
        "stop": stop,
        "risk_pct": risk_pct,
        "target": target,
        "reward_pct": reward_pct,
        "rr": rr,
        "risk_exceeds_max": bool(risk_pct is not None and risk_pct > _MAX),
        "max_stop_pct": _MAX,
    }


def _pick_entry_zone(last_price: float, demand_zones: list[dict]) -> Optional[dict]:
    """The band price is INSIDE, else the nearest band below (where you'd want
    to buy). None when there is no demand structure under price."""
    inside = [z for z in demand_zones if z.get("lo", 0) <= last_price <= z.get("hi", 0)]
    if inside:
        return max(inside, key=lambda z: z.get("strength") or 0)
    below = [z for z in demand_zones if z.get("hi", 0) < last_price]
    return max(below, key=lambda z: z["hi"]) if below else None


def _series_for_chart(df: pd.DataFrame, bars: int = 180) -> list[dict]:
    """Compact close series the FE draws the bands against."""
    tail = df.iloc[-bars:]
    out = []
    for idx, row in tail.iterrows():
        d = row.get("date") if "date" in tail.columns else idx
        try:
            ds = pd.Timestamp(d).strftime("%Y-%m-%d")
        except Exception:
            ds = str(d)[:10]
        out.append({"date": ds, "close": round(float(row["close"]), 2)})
    return out


def analyze_symbol(symbol: str, with_series: bool = False) -> Optional[dict]:
    """Full zone + re-entry + trade-plan record for one ticker.

    Works for ANY symbol, not only re-entry hits — the individual-stock view
    uses it to draw the bands and label entry/exit even when price sits in
    overhead supply.
    """
    sym = (symbol or "").upper().strip()
    if not sym:
        return None
    df = prices.load_prices(sym, period="2y")
    if df is None or len(df) < MIN_BARS:
        return None

    zones = price_zones.compute(df, **zone_geom())
    if not zones:
        return None

    last_price = zones["last_price"]
    demand = zones.get("demand_zones") or []
    supply = zones.get("supply_zones") or []

    tr = trend_template.evaluate(sym, df)
    trend_passed = tr.passed if tr else None
    trend_ok = bool(tr and tr.passed >= MIN_TREND_CHECKS)

    entry_zone = _pick_entry_zone(last_price, demand)
    closes = [float(c) for c in df["close"].tolist()]

    band = None
    if entry_zone and entry_zone.get("lo", 0) <= last_price <= entry_zone.get("hi", 0):
        band = reentry_read(closes, entry_zone["hi"], entry_zone["lo"], last_price)
    else:
        band = {"is_reentry": False, "fell_from_pct": None,
                "bars_since_above": None, "in_band": False}

    quality_ok = bool(entry_zone
                      and (entry_zone.get("touches") or 0) >= MIN_TOUCHES
                      and (entry_zone.get("strength") or 0) >= MIN_ZONE_STRENGTH)

    plan = trade_plan(last_price, entry_zone, zones.get("nearest_resistance"))

    rec = {
        "symbol": sym,
        "name": company_names.name_for(sym) or sym,
        "last_price": last_price,
        "supply_zones": supply,
        "demand_zones": demand,
        "nearest_resistance": zones.get("nearest_resistance"),
        "nearest_support": zones.get("nearest_support"),
        "verdict": zones.get("verdict"),
        # The re-entry read.
        "in_demand_band": band["in_band"],
        "is_reentry": bool(band["is_reentry"] and trend_ok and quality_ok),
        "fell_from_pct": band["fell_from_pct"],
        "bars_since_above": band["bars_since_above"],
        # Why it did / didn't qualify — surfaced so the list is auditable.
        "trend_passed": trend_passed,
        "trend_ok": trend_ok,
        "zone_quality_ok": quality_ok,
        "entry_zone": entry_zone,
        "plan": plan,
        "params": zones.get("params"),
        "disclaimer": DISCLAIMER,
    }
    if with_series:
        rec["series"] = _series_for_chart(df)
    return rec


def _rank_key(r: dict):
    """Freshest, strongest re-entries first: most recently back in the band,
    then the strongest band, then the deepest pullback."""
    bars = r.get("bars_since_above")
    z = r.get("entry_zone") or {}
    return (bars if bars is not None else 9_999,
            -(z.get("strength") or 0),
            -(r.get("fell_from_pct") or 0))


def scan(force: bool = False, limit: Optional[int] = None) -> dict:
    """Scan the S&P 500 for demand-zone re-entries. Cached `_CACHE_TTL_SEC`.

    Universe is `sepa.universe.fetch_sp500()` — which as of 2026-08-13 falls
    back to a STALE-but-real cached constituent list when Wikipedia 403s,
    rather than to the 158-name curated list (a different universe entirely).
    `universe_note` reports which list was actually used so the page can't
    quietly claim "S&P 500" over the wrong names.
    """
    if not force:
        c = _cache.get("data")
        if c and (time.time() - c["ts"]) < _CACHE_TTL_SEC:
            return {**c["data"], "cached": True}

    t0 = time.time()
    syms = universe_mod.fetch_sp500()
    curated_n = len(getattr(universe_mod, "UNIVERSE", []) or [])
    looks_curated = len(syms) == curated_n
    universe_note = ("S&P 500 unavailable — scanned the curated list instead"
                     if looks_curated else f"S&P 500 constituents ({len(syms)} names)")

    rows, scanned, errors = [], 0, 0
    for sym in syms:
        try:
            rec = analyze_symbol(sym)
        except Exception as exc:
            errors += 1
            log.debug("demand-reentry: %s failed: %s", sym, exc)
            continue
        if not rec:
            continue
        scanned += 1
        if rec["is_reentry"]:
            rec.pop("series", None)
            rows.append(rec)

    rows.sort(key=_rank_key)
    if limit:
        rows = rows[:int(limit)]

    data = {
        "rows": rows,
        "n": len(rows),
        "scanned": scanned,
        "universe": len(syms),
        "universe_note": universe_note,
        "universe_is_sp500": not looks_curated,
        "errors": errors,
        "took_sec": round(time.time() - t0, 1),
        "as_of": datetime.now(timezone.utc).isoformat(),
        "params": {
            "swing_window": SWING_WINDOW, "merge_pct": MERGE_PCT,
            "half_width_pct": HALF_WIDTH_PCT,
            "reentry_lookback_bars": REENTRY_LOOKBACK_BARS,
            "min_rise_above_pct": MIN_RISE_ABOVE_PCT,
            "min_touches": MIN_TOUCHES, "min_zone_strength": MIN_ZONE_STRENGTH,
            "min_trend_checks": MIN_TREND_CHECKS,
            "stop_buffer_pct": STOP_BUFFER_PCT,
        },
        "disclaimer": DISCLAIMER,
        "cached": False,
    }
    _cache["data"] = {"ts": time.time(), "data": data}
    log.info("demand-reentry: %d hits from %d scanned (%s) in %.1fs",
             len(rows), scanned, universe_note, data["took_sec"])
    return data
