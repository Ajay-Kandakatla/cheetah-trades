"""Liquidity sweeps — the stop-run into a demand zone, and what printed there.

Ajay 2026-08-13: "I think the main indicator for S/D are Demand zones and Prints
and darkpools which will help me do more deterministic trading like Intraday to
find exact reasonable entries to track smart money and how they use stop losses
to entry and lower price."

THE IDEA (Wyckoff's spring / the modern "liquidity grab" — NOT Minervini, and
deliberately independent of the SEPA stack)
------------------------------------------
Retail parks protective stops just BELOW an obvious support band. Those stops
are resting sell orders — the only pool of guaranteed supply on the book. A
size buyer who needs fills cannot get them at the zone without moving price, so
the cheaper path is to push price *through* the zone floor, trigger the stops,
absorb that forced selling at a lower price, and let price return.

The signature is mechanical and therefore testable:

  1. price pierces BELOW the zone floor by >= SWEEP_MIN_PIERCE_PCT   (stops hit)
  2. it closes back ABOVE the floor within RECLAIM_MAX_BARS          (reclaim)
  3. the sweep bar(s) trade on elevated volume                       (absorption)

What you get out of it that a plain "price is in the zone" read cannot give:
the **sweep low** — the actual price at which the forced sellers were filled.
That is the level the buyer defended, so it is a far better stop reference than
a guessed buffer under the band.

WHAT THIS IS NOT
----------------
Not proof of manipulation, and not proof of who bought. A sweep-and-reclaim is
a price pattern; the tape can show that size printed there, not whose it was.
A pierce that does NOT reclaim is simply a broken zone — the module reports
that as `broken`, never as a sweep.

All thresholds are CONFIGURED HOUSE VALUES. Not a book method, not advice.
Spec: docs/supply_demand/liquidity_sweep_methodology.md
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

log = logging.getLogger("supply_demand.sd_liquidity")

# ── Sweep geometry (house values) ────────────────────────────────────────────
SWEEP_MIN_PIERCE_PCT = 0.15    # must break the floor by this much to hit stops
SWEEP_MAX_PIERCE_PCT = 4.0     # deeper than this is a breakdown, not a stop-run
RECLAIM_MAX_BARS     = 12      # bars allowed to close back above the floor
SWEEP_MIN_VOL_X      = 1.3     # sweep-bar volume vs the local average
VOL_LOOKBACK_BARS    = 30      # local average window

# Where the stops actually sit, as a band under the zone floor. Used to report
# the "stop shelf" the sweep was hunting.
STOP_SHELF_PCT = 1.0

DISCLAIMER = (
    "A sweep-and-reclaim is a price pattern plus what printed there — evidence "
    "that resting stops were taken and the level was bought back, NOT proof of "
    "manipulation or of whose orders they were. Configured house thresholds, "
    "not a book method. Not advice."
)


def stop_shelf(zone_lo: float, pct: float = STOP_SHELF_PCT) -> Optional[dict]:
    """The price band just under a zone floor where protective stops cluster.
    PURE. This is the liquidity a sweep goes after."""
    if not zone_lo or zone_lo <= 0:
        return None
    return {"top": round(zone_lo, 2),
            "bottom": round(zone_lo * (1 - pct / 100.0), 2)}


def find_sweep(bars: pd.DataFrame, zone_lo: float, zone_hi: float,
               min_pierce_pct: float = SWEEP_MIN_PIERCE_PCT,
               max_pierce_pct: float = SWEEP_MAX_PIERCE_PCT,
               reclaim_bars: int = RECLAIM_MAX_BARS,
               min_vol_x: float = SWEEP_MIN_VOL_X) -> dict:
    """Find the most recent stop-run below `zone_lo` that reclaimed.

    `bars` needs low/high/close/volume, ascending, any timeframe (daily bars
    give the swing-level read; 1-/5-min bars give the intraday entry).

    Returns the richest sweep found (deepest pierce that reclaimed), or a
    not-found record. `state` is one of:
        swept    — pierced and reclaimed (the setup)
        broken   — pierced and never reclaimed (zone failed; do NOT buy)
        intact   — never pierced in this window
    """
    out = {"found": False, "state": "intact", "sweep_low": None,
           "pierce_pct": None, "reclaim_bars": None, "sweep_volume_x": None,
           "sweep_index": None, "reclaimed_at": None,
           "stop_shelf": stop_shelf(zone_lo)}
    if bars is None or len(bars) < 5 or not zone_lo or not zone_hi or zone_hi <= zone_lo:
        return out
    need = {"low", "close"}
    if not need.issubset(set(bars.columns)):
        return out

    lows = bars["low"].values
    closes = bars["close"].values
    vols = bars["volume"].values if "volume" in bars.columns else None
    n = len(bars)

    floor_ = float(zone_lo)
    min_px = floor_ * (1 - min_pierce_pct / 100.0)
    max_px = floor_ * (1 - max_pierce_pct / 100.0)

    best = None
    for i in range(n):
        low_i = float(lows[i])
        if low_i > min_px:
            continue                       # didn't reach the stop shelf
        if low_i < max_px:
            # Too deep to be a stop-run. If nothing ever reclaims, this is a
            # genuine breakdown — recorded below via the `broken` pass.
            continue
        # look forward for a close back above the floor
        stop = min(n, i + 1 + reclaim_bars)
        rec = None
        for j in range(i, stop):
            if float(closes[j]) > floor_:
                rec = j
                break
        if rec is None:
            continue
        pierce = (floor_ - low_i) / floor_ * 100.0
        vol_x = None
        if vols is not None:
            lo_b = max(0, i - VOL_LOOKBACK_BARS)
            base = float(pd.Series(vols[lo_b:i]).mean()) if i > lo_b else 0.0
            vol_x = round(float(vols[i]) / base, 2) if base > 0 else None
        if vol_x is not None and vol_x < min_vol_x:
            continue                       # no absorption — just a quiet dip
        cand = {"i": i, "low": low_i, "pierce": pierce, "rec": rec, "vol_x": vol_x}
        # Prefer the most RECENT qualifying sweep; ties break on depth.
        if best is None or cand["i"] > best["i"]:
            best = cand

    if best is not None:
        idx = bars.index
        out.update({
            "found": True, "state": "swept",
            "sweep_low": round(best["low"], 2),
            "pierce_pct": round(best["pierce"], 2),
            "reclaim_bars": int(best["rec"] - best["i"]),
            "sweep_volume_x": best["vol_x"],
            "sweep_index": str(idx[best["i"]]),
            "reclaimed_at": str(idx[best["rec"]]),
        })
        return out

    # Nothing reclaimed. Did price pierce at all? Then the zone is broken.
    pierced = [i for i in range(n) if float(lows[i]) <= min_px]
    if pierced:
        last = pierced[-1]
        if float(closes[-1]) <= floor_:
            out.update({"state": "broken",
                        "sweep_low": round(float(lows[last]), 2),
                        "pierce_pct": round((floor_ - float(lows[last])) / floor_ * 100.0, 2),
                        "sweep_index": str(bars.index[last])})
    return out


def structure_read(closes, lows, swing_window: int = 5) -> dict:
    """Are the swing lows stepping UP or DOWN? PURE.

    The falling-knife guard, stated WITHOUT any Minervini machinery: buying
    support while each swing low prints below the last is buying a downtrend.
    Ajay 2026-08-13, on CIEN (424 -> 404 -> 359 -> 323): "need to avoid falling
    knife".

    Returns {trend: rising|falling|unclear, swing_lows, last_two}.
    """
    out = {"trend": "unclear", "swing_lows": [], "last_two": None}
    lows = list(lows)
    n = len(lows)
    w = swing_window
    if n < 2 * w + 2:
        return out
    sw = []
    for i in range(w, n - w):
        if lows[i] <= min(lows[i - w:i]) and lows[i] <= min(lows[i + 1:i + 1 + w]):
            sw.append(round(float(lows[i]), 2))
    out["swing_lows"] = sw[-4:]
    if len(sw) >= 2:
        out["last_two"] = [sw[-2], sw[-1]]
        out["trend"] = "rising" if sw[-1] > sw[-2] else "falling"
    return out


def is_falling_knife(structure: dict, last_close: float,
                     ma50: Optional[float], ma50_prior: Optional[float]) -> bool:
    """Neutral downtrend guard — NOT the Minervini trend template.

    True when the swing lows are stepping down AND the 50-period average is
    also falling. Both must agree, so a single shakeout low inside an uptrend
    does not disqualify a zone."""
    lows_falling = structure.get("trend") == "falling"
    ma_falling = (ma50 is not None and ma50_prior is not None and ma50 < ma50_prior)
    return bool(lows_falling and ma_falling)
