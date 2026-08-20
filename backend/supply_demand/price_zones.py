"""Price-structure supply/demand zones — per-ticker, on-demand.

WHAT: for a single ticker, find the price BANDS where supply and demand have
shown up — swing-high clusters = SUPPLY (overhead resistance), swing-low clusters
= DEMAND (support) — weighted by how many times the band was tested and the volume
that traded there. Then, relative to the current price, report the nearest
overhead resistance, the nearest support below, and a plain entry read
("in a demand zone / clear runway / into overhead supply / mid-range").

METHOD NOTE (Ajay 2026-06-09): this is a PRAGMATIC price-structure read, **not** a
named book methodology — every threshold below is a CONFIGURED house value, not a
Minervini (or any book) number. Decision-support only — it is **not** a buy signal
and **not** financial advice.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

log = logging.getLogger("supply_demand.price_zones")

# ── Configured thresholds (NOT a book method — pragmatic price structure) ──────
LOOKBACK_BARS        = 252    # ~1 trading year of structure
SWING_WINDOW         = 4      # bars each side for a local swing high / low
ZONE_MERGE_PCT       = 1.75   # swings within this % of each other merge into one band
ZONE_HALF_WIDTH_PCT  = 0.6    # a single-swing band gets this half-width
NEAR_PCT             = 3.0    # a zone within this % of price = "at" it
CLEAR_RUNWAY_PCT     = 8.0    # nearest overhead supply beyond this % = clear runway
NO_SUPPORT_PCT       = 6.0    # nearest support farther than this below = "no support to lean on"
MAX_ZONES_PER_SIDE   = 4      # surface the strongest N supply + N demand bands

# Frame floors. MIN_BARS is the historical gate and stays exactly where it was
# for every caller that does not ask for a custom window — moving it would
# silently change the /zones page, orderflow.signals and the two backtests.
#
# A caller that DOES pass `lookback_bars` is explicitly asking for a shorter
# zoom (the Support Levels tab offers 1 month = 21 bars), so the floor becomes
# the only one that means anything at that size: enough bars for a swing to
# exist at all. `_local_extrema` scans range(w, n - w) and each candidate is
# compared against w bars either side, so 2w + 3 is the smallest frame that can
# produce a swing with a bar to spare on each end.
MIN_BARS             = 60     # default-window floor — unchanged since 2026-06-09
MIN_BARS_ABS         = 12     # hard floor for a custom window, at any resolution

DISCLAIMER = ("Price-structure zones — a configured, pragmatic read of where "
              "supply/demand showed up (NOT a book method). Decision-support only "
              "— not a buy signal and not advice.")


def _local_extrema(df: pd.DataFrame, swing_window: Optional[int] = None):
    """Raw swing highs (on `high`) + lows (on `low`). NOT collapsed — every touch
    counts toward a band's strength."""
    h = df["high"].values
    l = df["low"].values
    n = len(df)
    w = SWING_WINDOW if swing_window is None else int(swing_window)
    highs, lows = [], []
    for i in range(w, n - w):
        if h[i] >= h[i - w:i].max() and h[i] >= h[i + 1:i + 1 + w].max():
            highs.append(i)
        if l[i] <= l[i - w:i].min() and l[i] <= l[i + 1:i + 1 + w].min():
            lows.append(i)
    return highs, lows


def _make_zone(df: pd.DataFrame, cluster, kind: str,
               half_width_pct: Optional[float] = None) -> dict:
    prices = [p for p, _ in cluster]
    idxs = [i for _, i in cluster]
    lo, hi = min(prices), max(prices)
    mid = sum(prices) / len(prices)
    hwp = ZONE_HALF_WIDTH_PCT if half_width_pct is None else float(half_width_pct)
    if hi <= lo:                                   # single-swing band → give it width
        hw = mid * hwp / 100.0
        lo, hi = mid - hw, mid + hw
    vol = float(df["volume"].iloc[idxs].sum()) if "volume" in df else 0.0
    bars_since = int(len(df) - 1 - max(idxs))
    # Age of the OLDEST swing in the cluster, i.e. how far back a chart must
    # reach to show the structure that makes this a band at all. Added
    # 2026-08-16: zones are computed over 252 bars but the study board charted
    # 130, so a band could be drawn with every one of its defining touches
    # off-screen — Ajay studies these to learn the pattern, and a band with no
    # visible reason is worse than none. Purely additive; nothing reads it as a
    # gate. See docs/sepa/chart_timeframes.md.
    oldest = int(len(df) - 1 - min(idxs))
    return {
        "kind": kind,                              # "supply" | "demand"
        "lo": round(float(lo), 2),
        "hi": round(float(hi), 2),
        "mid": round(float(mid), 2),
        "touches": len(idxs),
        "volume": int(vol),
        "bars_since_test": bars_since,
        "oldest_touch_bars": oldest,
    }


def _cluster(df: pd.DataFrame, idxs, price_col: str, kind: str,
             merge_pct: Optional[float] = None,
             half_width_pct: Optional[float] = None):
    """Greedy price-clustering of swing points into bands."""
    mp = ZONE_MERGE_PCT if merge_pct is None else float(merge_pct)
    pts = sorted((float(df[price_col].iloc[i]), i) for i in idxs)
    zones, cur = [], []
    for price, i in pts:
        if cur and (price - cur[0][0]) / cur[0][0] * 100.0 > mp:
            zones.append(_make_zone(df, cur, kind, half_width_pct))
            cur = []
        cur.append((price, i))
    if cur:
        zones.append(_make_zone(df, cur, kind, half_width_pct))
    return zones


def _strength(z: dict, max_vol: float, max_touch: int) -> float:
    """0–100: half from test count, half from volume traded at the band."""
    t = z["touches"] / max_touch if max_touch else 0.0
    v = z["volume"] / max_vol if max_vol else 0.0
    return round(100.0 * (0.5 * t + 0.5 * v), 0)


def _verdict(px, res, sup, in_zone):
    res_pct = round((res["lo"] - px) / px * 100, 1) if res else None
    sup_pct = round((px - sup["hi"]) / px * 100, 1) if sup else None
    base = {"resistance_pct": res_pct, "support_pct": sup_pct}

    if in_zone and in_zone["kind"] == "supply":
        return {**base, "state": "AT_SUPPLY", "entry_read": "caution",
                "label": f"In an overhead-supply band (${in_zone['lo']}–${in_zone['hi']}) — "
                         f"resistance right here; it needs to clear this before it runs."}
    if in_zone and in_zone["kind"] == "demand":
        return {**base, "state": "AT_DEMAND", "entry_read": "favorable", "support_pct": 0.0,
                "label": f"In a demand zone (${in_zone['lo']}–${in_zone['hi']}, "
                         f"{in_zone['touches']}× tested) — support is right here."}
    if res is not None and res_pct is not None and res_pct <= NEAR_PCT:
        return {**base, "state": "INTO_SUPPLY", "entry_read": "caution",
                "label": f"Overhead supply just above at ${res['lo']}–${res['hi']} (+{res_pct}%) — "
                         f"risk of stalling. Better to buy nearer support or wait for a clean break."}

    support_near = sup_pct is not None and sup_pct <= NO_SUPPORT_PCT
    clear_above = res is None or (res_pct is not None and res_pct >= CLEAR_RUNWAY_PCT)

    if res is None and not support_near:
        far = f"{sup_pct}% below" if sup_pct is not None else "none in range"
        return {**base, "state": "EXTENDED_NO_SUPPORT", "entry_read": "caution",
                "label": f"At/near highs — no overhead supply, but no nearby support either "
                         f"(nearest {far}). Extended; no defined risk level for an entry here."}
    if clear_above and support_near:
        runway = (f"nearest overhead supply is {res_pct}% up" if res
                  else "no overhead supply in the last year")
        return {**base, "state": "CLEAR_RUNWAY", "entry_read": "favorable",
                "label": f"Clear runway — {runway}; support ~{sup_pct}% below for a stop."}
    return {**base, "state": "MID_RANGE", "entry_read": "neutral",
            "label": (f"Mid-range — support ~{sup_pct}% below, resistance ~{res_pct}% above."
                      if (sup_pct is not None and res_pct is not None)
                      else "Mid-range — no clearly defined band directly above/below right now.")}


def compute(df: pd.DataFrame, last_price: Optional[float] = None, *,
            swing_window: Optional[int] = None,
            merge_pct: Optional[float] = None,
            half_width_pct: Optional[float] = None,
            lookback_bars: Optional[int] = None) -> Optional[dict]:
    """Supply/demand bands for one frame.

    The four knobs default to this module's constants, so every existing caller
    (the /zones page, orderflow.signals) is byte-for-byte unaffected.
    `demand_reentry` passes WIDER geometry because a tradeable zone is a band
    you can place a stop under, not a 1%-wide line — see
    docs/supply_demand/demand_reentry_methodology.md.

    `lookback_bars` is the ZOOM: how far back the structure is read from.
    `chart_maps.support` drives it from a dropdown so the same rule can answer
    "where is support on a 1-month chart" and "…on a 1-year chart" — two
    genuinely different questions for a swing entry vs a position stop. It is a
    per-call argument, never a module mutation: see
    `test_price_zones_defaults_are_untouched_by_this_module`.

    NOTE the floor moves with it (MIN_BARS / MIN_BARS_ABS above). A 21-bar frame
    cannot clear the 60-bar default gate, and silently returning None for the
    shortest dropdown option would have looked like "no structure found".
    """
    if df is None or "high" not in df or "low" not in df:
        return None
    w = SWING_WINDOW if swing_window is None else int(swing_window)
    lb = LOOKBACK_BARS if lookback_bars is None else max(1, int(lookback_bars))
    need = MIN_BARS if lookback_bars is None else max(MIN_BARS_ABS, 2 * w + 3)
    df = df.iloc[-lb:].reset_index(drop=True)
    if len(df) < need:
        return None
    if last_price is None:
        last_price = float(df["close"].iloc[-1])

    highs, lows = _local_extrema(df, swing_window)
    supply = _cluster(df, highs, "high", "supply", merge_pct, half_width_pct)
    demand = _cluster(df, lows, "low", "demand", merge_pct, half_width_pct)
    allz = supply + demand
    if not allz:
        return None

    max_vol = max((z["volume"] for z in allz), default=1) or 1
    max_touch = max((z["touches"] for z in allz), default=1) or 1
    for z in allz:
        z["strength"] = _strength(z, max_vol, max_touch)
        z["in_price"] = z["lo"] <= last_price <= z["hi"]

    # Nearest overhead (any band above) + nearest support (any band below). A
    # band's origin (supply/demand) is kept for coloring; what matters for entry
    # is what sits directly above/below the price now (broken support = resistance).
    overhead = sorted((z for z in allz if z["lo"] > last_price), key=lambda z: z["lo"])
    below = sorted((z for z in allz if z["hi"] < last_price), key=lambda z: -z["hi"])
    nearest_res = overhead[0] if overhead else None
    nearest_sup = below[0] if below else None
    in_zone = next((z for z in allz if z["in_price"]), None)

    supply_top = sorted(supply, key=lambda z: -z["strength"])[:MAX_ZONES_PER_SIDE]
    demand_top = sorted(demand, key=lambda z: -z["strength"])[:MAX_ZONES_PER_SIDE]
    return {
        "last_price": round(float(last_price), 2),
        "supply_zones": sorted(supply_top, key=lambda z: -z["mid"]),   # high → low
        "demand_zones": sorted(demand_top, key=lambda z: -z["mid"]),
        "nearest_resistance": nearest_res,
        "nearest_support": nearest_sup,
        "verdict": _verdict(last_price, nearest_res, nearest_sup, in_zone),
        # Which RESOLUTION produced these bands. Two surfaces legitimately use
        # different geometry — the Tape tab wants fine bands for an intraday
        # read, demand_reentry wants coarse ones for a multi-day hold — and
        # without saying so they look like they disagree about the same stock.
        # DTE 2026-08-14: fine gave 141.42-143.87 + 138.49-140.37; coarse
        # merged them into 139.61-143.87. Same structure, different zoom.
        "resolution": ("fine" if (merge_pct or ZONE_MERGE_PCT) <= 2.0 else "swing"),
        "params": {"lookback": lb,
                   "swing_window": w,
                   "merge_pct": ZONE_MERGE_PCT if merge_pct is None else float(merge_pct),
                   "half_width_pct": (ZONE_HALF_WIDTH_PCT if half_width_pct is None
                                      else float(half_width_pct)),
                   "near_pct": NEAR_PCT,
                   "clear_runway_pct": CLEAR_RUNWAY_PCT},
        "disclaimer": DISCLAIMER,
    }


def for_symbol(symbol: str, last_price: Optional[float] = None, **geom) -> dict:
    """Load 2y of bars and compute the zones for one ticker (on-demand).

    `**geom` forwards the optional swing_window / merge_pct / half_width_pct
    knobs of `compute`; omitting them keeps the historical defaults."""
    sym = (symbol or "").upper().strip()
    if not sym:
        return {"symbol": sym, "error": "missing symbol"}
    from sepa import prices
    df = prices.load_prices(sym, period="2y")
    if df is None or len(df) < 60:
        return {"symbol": sym, "error": "no / insufficient price data"}
    out = compute(df, last_price=last_price, **geom)
    if out is None:
        return {"symbol": sym, "error": "no swing structure found"}
    out["symbol"] = sym
    return out
