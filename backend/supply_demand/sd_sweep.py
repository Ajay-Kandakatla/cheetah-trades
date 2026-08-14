"""Liquidity-sweep entries — a supply/demand strategy, independent of SEPA.

Ajay 2026-08-13:
  · "The autopilot and SEPA scanners can be [used]. The Supply demand are
     outside of this strategy."
  · "the main indicator for S/D are Demand zones and Prints and darkpools …
     to track smart money and how they use stop losses to entry and lower price"
  · "Doesn't have to be exactly intraday I can hold for a day or two sometimes
     a week if we got a clean entry."
  · "need to avoid falling knife lol."

This module imports NOTHING from the Minervini stack — no trend template, no
stage, no VCP, no scanner score. (`sepa.prices` is used purely as the OHLCV
loader; that is data plumbing, not methodology.)

WHAT IT LOOKS FOR
-----------------
1. **A demand band** built from the last `LOOKBACK_SESSIONS` sessions of
   intraday bars — the level where buyers repeatedly showed up.
2. **A stop-run** through that band's floor: price pierces it (taking the
   resting stops, which are the only guaranteed pool of supply), then closes
   back above it on elevated volume. The **sweep low** is where the forced
   sellers were filled — the level someone defended, and a far better stop
   reference than a guessed buffer.
3. **What printed there** — how much of the volume in that price range went
   off-exchange, and whether there were blocks.
4. **A falling-knife guard** on DAILY swing lows. Neutral, not Minervini:
   if each swing low is lower than the last AND the 50-day average is falling,
   the zone is not tradeable no matter how clean the sweep.

WHY THIS WINDOW
---------------
Measured 2026-08-13 across three horizons:

  · DAILY bands sit too far from price to ever be swept (VRT's daily demand
    band was 158-162 against a 288 price) — every symbol reads `intact`.
  · ONE session of 1-min bars gives bands ~0.3% wide and sweeps of ~0.24%.
    Real, but noise for a multi-day hold.
  · TEN sessions of intraday bars, geometry below: CAT band 852.11-861.58
    (1.11% wide, 8x tested) swept to 842.11 (-1.17%) and reclaimed in 1 bar on
    11.9x volume. That is a level worth holding days against.

HONEST LIMIT ON THE EDGE
------------------------
Osler (2003, NY Fed Staff Report 150; JIMF 2005) documented that stop-loss
clusters do produce genuine price cascades — but found the effect statistically
significant **for hours, not for days** (and in FX, not equities). So a sweep is
ENTRY TIMING, not a multi-day thesis. What is meant to carry a multi-day hold
here is the zone holding plus accumulation evidence — never the sweep alone.

All thresholds are CONFIGURED HOUSE VALUES. Not a book method. Not advice.
Spec: docs/supply_demand/liquidity_sweep_methodology.md
"""
from __future__ import annotations

import logging
from datetime import date as _date, timedelta
from typing import Optional

import pandas as pd

from . import price_zones, sd_liquidity as liq

log = logging.getLogger("supply_demand.sd_sweep")

# ── Window + zone geometry (house values; calibrated 2026-08-13, see docstring)
LOOKBACK_SESSIONS   = 10
LOOKBACK_CAL_DAYS   = 14        # calendar span that covers ~10 sessions
SWING_WINDOW        = 12
MERGE_PCT           = 1.2
HALF_WIDTH_PCT      = 0.45

# ── Sweep qualification ──────────────────────────────────────────────────────
MIN_PIERCE_PCT      = 0.4       # below this it is noise, not a stop-run
MAX_PIERCE_PCT      = 6.0       # beyond this it is a breakdown, not a sweep
RECLAIM_MAX_BARS    = 60        # bars allowed to close back above the floor
MIN_SWEEP_VOL_X     = 1.3       # absorption on the sweep bar

# A sweep older than this many bars is history, not a live entry (~1.5 sessions).
FRESH_WITHIN_BARS   = 600
# The band must be within this % of the last price to be actionable.
MAX_DISTANCE_PCT    = 8.0
MIN_TOUCHES         = 2
MAX_BANDS_CHECKED   = 4
MIN_BARS            = 300

DISCLAIMER = (
    "Liquidity-sweep entries: demand bands from recent intraday structure, "
    "stop-runs detected as pierce-then-reclaim, plus the venue mix of what "
    "printed there. Evidence, not proof of intent. No part of the "
    "Minervini/SEPA stack. Configured house thresholds — not advice."
)


def sweep_geom() -> dict:
    return {"swing_window": SWING_WINDOW, "merge_pct": MERGE_PCT,
            "half_width_pct": HALF_WIDTH_PCT}


def _norm(bars: pd.DataFrame) -> pd.DataFrame:
    return bars.rename(columns={c: str(c).lower() for c in bars.columns})


def load_window(symbol: str, end_day: _date,
                sessions: int = LOOKBACK_SESSIONS) -> Optional[pd.DataFrame]:
    """Intraday bars across the recent `sessions` trading days."""
    from daytrading import data as dt_data
    start = end_day - timedelta(days=LOOKBACK_CAL_DAYS)
    try:
        bars = dt_data.load_intraday_range(symbol, start, end_day,
                                           include_premarket=False,
                                           include_afterhours=False)
    except Exception as exc:
        log.debug("sd-sweep: range bars failed for %s: %s", symbol, exc)
        return None
    if bars is None or len(bars) < MIN_BARS:
        return None
    return _norm(bars)


def daily_structure(symbol: str) -> dict:
    """Falling-knife guard on DAILY swing lows. Neutral — no trend template.

    Returns the structure read plus `is_knife`. Ajay 2026-08-13, after CIEN
    printed 424 -> 404 -> 359 -> 323 while Minervini's template still read 7/8:
    "need to avoid falling knife lol."
    """
    from sepa import prices                       # OHLCV loader only
    out = {"trend": "unclear", "swing_lows": [], "last_two": None,
           "is_knife": False, "ma50_rising": None}
    df = prices.load_prices(symbol, period="1y")
    if df is None or len(df) < 60:
        return out
    closes, lows = df["close"], df["low"]
    st = liq.structure_read(closes.tolist(), lows.tolist(), swing_window=5)
    ma50 = closes.rolling(50).mean()
    ma_now = float(ma50.iloc[-1]) if pd.notna(ma50.iloc[-1]) else None
    ma_prior = float(ma50.iloc[-11]) if len(ma50) > 11 and pd.notna(ma50.iloc[-11]) else None
    return {**st,
            "ma50_rising": (None if ma_now is None or ma_prior is None
                            else bool(ma_now > ma_prior)),
            "is_knife": liq.is_falling_knife(st, float(closes.iloc[-1]), ma_now, ma_prior)}


def plan_from_sweep(sweep_low: float, band_lo: float, band_hi: float,
                    last_price: float, supply_zones: Optional[list]) -> dict:
    """Entry / stop / target anchored on the SWEEP, not on a guess. PURE.

    Entry  = the band itself (buy back inside it, above the swept floor)
    Stop   = just under the sweep low — the level real money defended. Break it
             and the absorption thesis is simply wrong.
    Target = the first supply band ABOVE THE BAND TOP.

    Three corrections forced by live data 2026-08-13, each of which had produced
    a misleading number:

    * `valid` — once price closes back BELOW the sweep low the setup has already
      failed. It used to still print a plan (with `risk_pct: None`, because the
      "stop" was above the current price). Now it is explicitly invalid.
    * the target is measured from the BAND, not from the last price. Taking the
      nearest resistance above *spot* gave KLAC a target of 209.72 under an
      entry band of 211.94-212.77 — a target below the entry.
    * `entry_ref` is clamped into the band. Quoting R:R off a spot price that
      sits outside the band you intend to buy is not the trade being described.
    """
    out = {"valid": False, "reason": None,
           "entry_low": round(band_lo, 2), "entry_high": round(band_hi, 2),
           "entry_ref": None, "stop": None, "risk_pct": None,
           "target": None, "reward_pct": None, "rr": None}
    if not sweep_low or not last_price or band_hi <= band_lo:
        out["reason"] = "no band or sweep"
        return out

    stop = round(sweep_low * 0.998, 2)
    out["stop"] = stop
    if last_price <= stop:
        out["reason"] = "price is back below the swept low — setup already failed"
        return out

    entry_ref = min(max(last_price, band_lo), band_hi)
    out["entry_ref"] = round(entry_ref, 2)
    out["risk_pct"] = round((entry_ref - stop) / entry_ref * 100, 1)

    above = [z for z in (supply_zones or [])
             if z.get("lo") and float(z["lo"]) > band_hi]
    if above:
        tgt = round(float(min(above, key=lambda z: z["lo"])["lo"]), 2)
        out["target"] = tgt
        out["reward_pct"] = round((tgt - entry_ref) / entry_ref * 100, 1)
        out["rr"] = round((tgt - entry_ref) / (entry_ref - stop), 2)
    out["valid"] = True
    return out


def analyze_symbol(symbol: str, end_day: _date,
                   trades: Optional[pd.DataFrame] = None,
                   check_structure: bool = True) -> Optional[dict]:
    """Zones + stop-runs + prints + the knife guard, for one ticker."""
    from orderflow import darkpool

    sym = (symbol or "").upper().strip()
    if not sym:
        return None
    bars = load_window(sym, end_day)
    if bars is None:
        return None
    z = price_zones.compute(bars, **sweep_geom())
    if not z:
        return None

    last_price = float(bars["close"].iloc[-1])
    n = len(bars)
    structure = daily_structure(sym) if check_structure else {"is_knife": False}

    idx_str = list(bars.index.astype(str))
    hits = []
    for band in (z.get("demand_zones") or []):
        if (band.get("touches") or 0) < MIN_TOUCHES:
            continue
        dist = abs(band["mid"] / last_price - 1) * 100
        if dist > MAX_DISTANCE_PCT:
            continue
        s = liq.find_sweep(bars, band["lo"], band["hi"],
                           min_pierce_pct=MIN_PIERCE_PCT,
                           max_pierce_pct=MAX_PIERCE_PCT,
                           reclaim_bars=RECLAIM_MAX_BARS,
                           min_vol_x=MIN_SWEEP_VOL_X)
        if s["state"] != "swept":
            continue
        try:
            age = n - 1 - idx_str.index(s["sweep_index"])
        except ValueError:
            age = None

        prints = {"available": False}
        if trades is not None and not trades.empty:
            prints = darkpool.dark_in_band(trades, s["sweep_low"], band["hi"])
            if prints.get("available") and prints.get("total_shares"):
                sub = trades[(trades["price"] >= s["sweep_low"])
                             & (trades["price"] <= band["hi"])]
                prints["blocks_detail"] = darkpool.dark_blocks(sub, top=5)

        hits.append({
            "band_lo": band["lo"], "band_hi": band["hi"],
            "touches": band["touches"], "strength": band["strength"],
            "distance_pct": round((band["mid"] / last_price - 1) * 100, 1),
            "sweep_low": s["sweep_low"], "pierce_pct": s["pierce_pct"],
            "reclaim_bars": s["reclaim_bars"], "sweep_volume_x": s["sweep_volume_x"],
            "sweep_at": s["sweep_index"], "reclaimed_at": s["reclaimed_at"],
            "stop_shelf": s["stop_shelf"],
            "bars_since": age,
            "fresh": bool(age is not None and age <= FRESH_WITHIN_BARS),
            "held": bool(last_price > band["lo"]),
            "prints": prints,
            "plan": plan_from_sweep(s["sweep_low"], band["lo"], band["hi"],
                                    last_price, z.get("supply_zones")),
        })

    hits.sort(key=lambda r: (r["bars_since"] if r["bars_since"] is not None else 10**9))
    return {
        "symbol": sym, "end_day": str(end_day),
        "last_price": round(last_price, 2), "bars": n,
        "sessions": LOOKBACK_SESSIONS,
        "demand_zones": z.get("demand_zones") or [],
        "supply_zones": z.get("supply_zones") or [],
        "nearest_resistance": z.get("nearest_resistance"),
        "sweeps": hits, "n_sweeps": len(hits),
        "structure": structure,
        "is_knife": bool(structure.get("is_knife")),
        "disclaimer": DISCLAIMER,
    }


def scan(symbols: list, end_day: _date, with_prints: bool = True,
         limit: Optional[int] = None, allow_knives: bool = False) -> dict:
    """Scan a list for fresh, held stop-runs. Falling knives are dropped."""
    from orderflow import tape as tape_mod

    rows, scanned, knives, errors = [], 0, 0, 0
    for sym in symbols:
        trades = None
        if with_prints:
            try:
                trades = tape_mod.fetch_trades(sym, end_day)
            except Exception:
                trades = None
        try:
            rec = analyze_symbol(sym, end_day, trades=trades)
        except Exception as exc:
            errors += 1
            log.debug("sd-sweep: %s failed: %s", sym, exc)
            continue
        if not rec:
            continue
        scanned += 1
        if rec["is_knife"] and not allow_knives:
            knives += 1
            continue
        live = [s for s in rec["sweeps"] if s["fresh"] and s["held"]]
        if live:
            rows.append({**rec, "sweeps": live, "n_sweeps": len(live)})

    rows.sort(key=lambda r: (r["sweeps"][0]["bars_since"] or 10**9,
                             -(r["sweeps"][0]["sweep_volume_x"] or 0)))
    if limit:
        rows = rows[:int(limit)]
    return {
        "rows": rows, "n": len(rows), "scanned": scanned,
        "knives_dropped": knives, "errors": errors,
        "end_day": str(end_day), "disclaimer": DISCLAIMER,
        "params": {
            "sessions": LOOKBACK_SESSIONS, "swing_window": SWING_WINDOW,
            "merge_pct": MERGE_PCT, "half_width_pct": HALF_WIDTH_PCT,
            "min_pierce_pct": MIN_PIERCE_PCT, "max_pierce_pct": MAX_PIERCE_PCT,
            "reclaim_max_bars": RECLAIM_MAX_BARS,
            "min_sweep_vol_x": MIN_SWEEP_VOL_X,
            "max_distance_pct": MAX_DISTANCE_PCT, "min_touches": MIN_TOUCHES,
        },
    }
