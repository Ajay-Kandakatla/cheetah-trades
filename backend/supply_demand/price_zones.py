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
MAX_ZONES_PER_SIDE   = 4      # surface the N NEAREST supply + N demand bands (was strongest until 2026-09-02)

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

# One tick at the 2dp every band edge is rounded to. NOT a threshold — the
# rounding grain `_make_zone` already applies; a cluster whose natural span is
# thinner than this has no width after rounding (see the degenerate-band fix).
_TICK_2DP            = 0.01

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
    # A single swing has no span, and (2026-09-05, Ajay: "yes please fix the
    # bugs") so does a multi-touch cluster whose swings sit a fraction of a cent
    # apart: 1.2001/1.2004 rounded to a 1.20–1.20 band with two touches and no
    # width, which killed its trade_levels and made in_price a one-cent target.
    # Both degenerate cases get the symmetric single-swing half-width. ONLY the
    # degenerate case is widened — a real span (100.0–101.5, or even one tick,
    # 110.00–110.01) is left exactly as the swings drew it. Widening every
    # multi-touch band would reshape every board and needs a re-measure first.
    if hi <= lo or (round(hi, 2) - round(lo, 2)) < _TICK_2DP - 1e-9:
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
    # AT_DEMAND used to force support_pct to 0.0 ("support is right here").
    # `nearest_support` is the band BELOW price, never the one it stands in, and
    # the /zones page prints the two as one statement — so 0.0 annotated the
    # NEXT band down as "−0.0%" when it was 12% away. Both sides now carry the
    # true distance to the band the payload names; the containing band is in
    # the label (2026-09-05, Ajay: "yes please fix the bugs").
    if in_zone and in_zone["kind"] == "demand":
        return {**base, "state": "AT_DEMAND", "entry_read": "favorable",
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


def band_distance(z: dict, last_price: float) -> float:
    """0 when price is inside the band, else the gap to its nearest edge."""
    if z["lo"] <= last_price <= z["hi"]:
        return 0.0
    return z["lo"] - last_price if z["lo"] > last_price else last_price - z["hi"]


def nearest_first(bands: list, last_price: float) -> list:
    """Bands ordered by distance from price (inside first); ties by strength."""
    return sorted(bands, key=lambda z: (band_distance(z, last_price), -z.get("strength", 0)))


def compute(df: pd.DataFrame, last_price: Optional[float] = None, *,
            max_zones: Optional[int] = MAX_ZONES_PER_SIDE,
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

    # Which N bands per side are SURFACED. Until 2026-09-02 this kept the N
    # STRONGEST, which routinely dropped the band price meets FIRST (CRWD 6m:
    # the 216-219 and 227 swing highs the SMC ledger was sweeping; UBER: the
    # band price was standing in). Every consumer of these lists asks "what is
    # nearest / what am I in", so the cut is now by DISTANCE from price, the
    # band price is standing in always kept. `strength` stays on each band for
    # ranking and display; max_zones=None returns every cluster.
    _cap = len(allz) if max_zones is None else max_zones
    supply_top = nearest_first(supply, last_price)[:_cap]
    demand_top = nearest_first(demand, last_price)[:_cap]
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


def _overlay_today(prices_mod, df, sym: str):
    """prices.with_today_bar, tolerant of stubs that lack it (tests) and of any
    failure — the closed frame is always an acceptable answer.

    Since 2026-09-05 `for_symbol` uses only the INFO half of the answer (the
    live price + the block the chart draws); structure is read off the closed
    frame it was given. The overlaid frame is still returned for any caller
    that wants it."""
    fn = getattr(prices_mod, "with_today_bar", None)
    if fn is None:
        return df, None
    try:
        return fn(df, sym)
    except Exception as exc:                                    # pragma: no cover
        log.debug("price_zones: today-bar overlay failed for %s: %s", sym, exc)
        return df, None


def for_symbol(symbol: str, last_price: Optional[float] = None,
               tf: Optional[str] = None, **geom) -> dict:
    """Load bars and compute the zones for one ticker (on-demand).

    `**geom` forwards the optional swing_window / merge_pct / half_width_pct
    knobs of `compute`; omitting them keeps the historical defaults.

    `tf` (Ajay 2026-08-29) reads the structure off hourly or 15-minute bars
    instead of daily. Omitted or "daily" is the historical path, byte for
    byte — the intraday branch is additive and cannot change what the
    existing callers see. Every intraday answer also carries its Fair Value
    Gaps, the session opening range, and the entry/stop each band implies.

    STRUCTURE IS READ OFF CLOSED BARS ONLY (2026-09-05, Ajay: "yes please fix
    the bugs"). Swings/bands, fair value gaps, ATR and trade levels are
    computed on the frame BEFORE today's live bar (daily) or without the
    in-progress last bucket (intraday). The partial bar supplies only the
    price the verdict is read at, and the `live_bar` block the chart draws.
    A "three-bar imbalance" whose third bar has not closed is not a gap yet —
    its edge was the intraday low-so-far and repainted all session; the same
    bar was leaking a partial-day true range into the ATR the stop buffer is
    scaled by. This deliberately NARROWS the 2026-09-03 CHPT decision: the
    verdict and the chart still see the live bar; the structure does not.
    """
    sym = (symbol or "").upper().strip()
    if not sym:
        return {"symbol": sym, "error": "missing symbol"}
    from supply_demand import timeframes as tf_mod
    tf_key = tf_mod.parse_tf(tf) if tf else tf_mod.DAILY
    tf_meta = None
    live_bar = None

    if tf_key == tf_mod.DAILY:
        from sepa import prices
        df = prices.load_prices(sym, period="2y")
        if df is None or len(df) < 60:
            return {"symbol": sym, "error": "no / insufficient price data",
                    "timeframe": tf_key, "timeframes": tf_mod.tf_options()}
        # Today's live bar (Ajay 2026-09-03, CHPT read "1.4% below support"
        # off yesterday's close while the tape was +76%) supplies the PRICE
        # the verdict is read at; the structure stays on the closed frame
        # (docstring). Nothing is written back — see prices.with_today_bar.
        closed = df
        _live_df, live_bar = _overlay_today(prices, closed, sym)
        if last_price is None and live_bar and live_bar.get("appended"):
            try:
                last_price = float(live_bar.get("last_price"))
            except (TypeError, ValueError):
                last_price = None
    else:
        df, tf_meta = tf_mod.frame_for(sym, tf_key)
        if df is None or len(df) < 30:
            return {"symbol": sym, "timeframe": tf_key,
                    "timeframes": tf_mod.tf_options(),
                    "timeframe_meta": tf_meta,
                    "error": ((tf_meta or {}).get("reason")
                              or "no / insufficient intraday data")}
        # The in-progress last bucket (frame_for flags it `partial`) is the
        # intraday twin of today's live bar: it prices the read, it is not
        # structure.
        closed = df
        if (tf_meta or {}).get("partial") and len(df) > 1:
            closed = df.iloc[:-1]
            if last_price is None:
                last_price = float(df["close"].iloc[-1])
        geom.setdefault("swing_window", tf_mod.tf_spec(tf_key)["swing_window"])
        geom.setdefault("lookback_bars", len(closed))

    out = compute(closed, last_price=last_price, **geom)
    if out is None:
        return {"symbol": sym, "error": "no swing structure found",
                "timeframe": tf_key, "timeframes": tf_mod.tf_options()}
    out["symbol"] = sym
    out["timeframe"] = tf_key
    out["timeframe_label"] = tf_mod.tf_spec(tf_key)["label"]
    out["live_bar"] = live_bar if tf_key == tf_mod.DAILY else None
    out["timeframes"] = tf_mod.tf_options()
    if tf_meta:
        out["timeframe_meta"] = tf_meta

    # ORB / FVG / dynamic entry-stop ride along on every answer.
    try:
        from supply_demand import patterns as pat_mod
        lp = float(out.get("last_price") or closed["close"].iloc[-1])
        atr_value = pat_mod.atr(closed)
        gaps = pat_mod.fair_value_gaps(closed, lp)
        bands = [{"kind": z.get("kind"), "lo": z.get("lo"), "hi": z.get("hi"),
                  "source": "swing", "touches": z.get("touches")}
                 for z in (list(out.get("demand_zones") or [])
                           + list(out.get("supply_zones") or []))
                 if z.get("lo") and z.get("hi")]
        out["atr"] = round(atr_value, 4) if atr_value else None
        out["fair_value_gaps"] = gaps
        out["opening_range"] = pat_mod.opening_range(
            sym, tf_mod.tf_spec(tf_key)["orb_minutes"])
        out["trade_levels"] = pat_mod.attach_levels(bands + gaps, lp, atr_value)
    except Exception as exc:                                # pragma: no cover
        log.warning("price_zones: pattern overlay for %s failed: %s", sym, exc)
    return out
