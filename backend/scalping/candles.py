"""Candle anatomy + level-context tape read — the wick/body layer of the SEPA
watch (Ajay 2026-06-09: "tell me they are going to grow or not based on price
action and candle wicks and body").

HONESTY CONTRACT (per the verified research, see docs/scalping_methodology.md):
the academic record on candlestick patterns as STANDALONE predictors is weak to
null (Marshall, Young & Rose 2006 found no value on US stocks). What this module
does instead is DESCRIPTIVE supply/demand arithmetic about each completed 5-min
bar — who won the bar (body %, close-location), where rejection happened (wick
dominance), and on what participation (volume ratio) — evaluated AT a level that
matters (the SEPA pivot, VWAP, opening-range high, day high). Verdicts say
"constructive" / "deteriorating", never "will go up". All thresholds CONFIGURED.

Pure functions over OHLCV — no I/O. sepa_watch.py owns state + alerts.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

# ── CONFIGURED thresholds (descriptive cutoffs, not book formulas) ────────────
STRONG_BODY_PCT = 0.60       # body ≥60% of range = one side controlled the bar
DOJI_BODY_PCT = 0.15         # body <15% of range = indecision
WICK_DOMINANCE = 2.0         # wick ≥2× body = rejection tail
CLV_STRONG = 0.50            # close-location-value (Chaikin): +1 close at high
VOL_RATIO_MIN = 1.5          # bar volume ≥1.5× today's avg 5-min bar = real participation
LEVEL_TOL_PCT = 0.30         # "at the level" band, % of price
BARS_5M = "5min"


def aggregate_5min(df_1min: pd.DataFrame) -> pd.DataFrame:
    """1-min OHLCV → completed 5-min bars (drops a trailing partial bar)."""
    if df_1min is None or df_1min.empty:
        return pd.DataFrame()
    agg = df_1min.resample(BARS_5M).agg(
        open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last"), volume=("volume", "sum"),
    ).dropna(subset=["open", "close"])
    if agg.empty:
        return agg
    # Drop the in-progress bar: the last 5-min bucket is complete only when the
    # 1-min frame extends to its final minute.
    last_bucket_end = agg.index[-1] + pd.Timedelta(minutes=4)
    if df_1min.index[-1] < last_bucket_end:
        agg = agg.iloc[:-1]
    return agg


def anatomy(o: float, h: float, l: float, c: float) -> Optional[dict]:
    """Descriptive arithmetic for one bar. Returns None on a degenerate bar."""
    rng = h - l
    if rng <= 0 or not all(np.isfinite([o, h, l, c])):
        return None
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - l
    clv = ((c - l) - (h - c)) / rng                       # -1 close at low … +1 at high
    body_pct = body / rng
    return {
        "body_pct": round(body_pct, 3),
        "upper_wick_pct": round(upper / rng, 3),
        "lower_wick_pct": round(lower / rng, 3),
        "clv": round(clv, 3),
        "dir": "up" if c > o else "down" if c < o else "flat",
        "is_doji": body_pct < DOJI_BODY_PCT,
        "is_strong": body_pct >= STRONG_BODY_PCT,
        "upper_wick_dominant": body > 0 and (upper / body) >= WICK_DOMINANCE or (body == 0 and upper > 0),
        "lower_wick_dominant": body > 0 and (lower / body) >= WICK_DOMINANCE or (body == 0 and lower > 0),
    }


def _near(px: float, level: Optional[float]) -> bool:
    return bool(level and px and abs(px / level - 1.0) * 100.0 <= LEVEL_TOL_PCT)


def classify(df5: pd.DataFrame, levels: dict, avg_vol_5m: Optional[float]) -> Optional[dict]:
    """Read the LAST COMPLETED 5-min bar against the levels.

    levels: {pivot, vwap, or_high, day_high} (any may be None).
    Returns {state, verdict, severity, reasons, metrics} or None (no read).

    States (alertable ones marked ⚡):
      ⚡ BREAKOUT_STRONG — closed above pivot/OR-high/day-high with a strong body,
          close near highs, on volume. Constructive.
      BREAKOUT_WEAK     — above the level but small body / wick-heavy / no volume.
      ⚡ REJECTION       — tested the level from below, upper-wick-dominant, closed
          back under. Supply hit the breakout. Deteriorating.
      ⚡ BREAKDOWN       — lost VWAP (or fell back under the pivot) on a strong red
          bar. Deteriorating.
      ⚡ RECLAIM         — took VWAP back on a strong body. Constructive.
      STALL             — doji(s) sitting at the level on fading volume. Neutral.
    """
    if df5 is None or len(df5) < 2:
        return None
    last, prev = df5.iloc[-1], df5.iloc[-2]
    a = anatomy(float(last["open"]), float(last["high"]), float(last["low"]), float(last["close"]))
    if a is None:
        return None
    c, h = float(last["close"]), float(last["high"])
    pc = float(prev["close"])
    vol_ratio = (float(last["volume"]) / avg_vol_5m) if avg_vol_5m else None
    vol_ok = vol_ratio is not None and vol_ratio >= VOL_RATIO_MIN

    pivot, vwap = levels.get("pivot"), levels.get("vwap")
    or_high, day_high = levels.get("or_high"), levels.get("day_high")
    # The breakout reference: pivot beats OR-high beats day-high.
    ref_name, ref = next(((n, v) for n, v in
                          (("pivot", pivot), ("OR high", or_high), ("day high", day_high))
                          if v), (None, None))

    metrics = {**a, "vol_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
               "close": round(c, 4), "ref_level": ref, "ref_name": ref_name}

    def out(state, verdict, severity, reasons):
        return {"state": state, "verdict": verdict, "severity": severity,
                "reasons": reasons, "metrics": metrics}

    # REJECTION — poked the reference level, wick rejected it, closed back under.
    if ref and h >= ref and c < ref and a["upper_wick_dominant"]:
        return out("REJECTION", "deteriorating", "alert", [
            f"Tested {ref_name} {ref:.2f} and got rejected — upper wick "
            f"{a['upper_wick_pct']:.0%} of the bar vs body {a['body_pct']:.0%}",
            f"Closed back under at {c:.2f}" + (f" on {vol_ratio:.1f}× volume" if vol_ratio else ""),
            "Supply showed up at the breakout level",
        ])

    # BREAKOUT — crossed or holding above the reference this bar.
    crossed = ref and pc <= ref < c
    holding_above = ref and c > ref and pc > ref and _near(float(last["low"]), ref)
    if crossed or holding_above:
        if a["is_strong"] and a["clv"] >= CLV_STRONG and vol_ok:
            return out("BREAKOUT_STRONG", "constructive", "alert", [
                f"{'Broke' if crossed else 'Holding'} {ref_name} {ref:.2f} with a "
                f"{a['body_pct']:.0%}-body bar closing near its high (CLV {a['clv']:+.2f})",
                f"{vol_ratio:.1f}× average 5-min volume — real participation",
                "Demand controlled the bar at the level",
            ])
        return out("BREAKOUT_WEAK", "neutral", "info", [
            f"Above {ref_name} {ref:.2f} but the bar is "
            + ("wick-heavy" if a["upper_wick_dominant"] else f"only {a['body_pct']:.0%} body")
            + (f" on {vol_ratio:.1f}× volume" if vol_ratio is not None else ", volume unknown"),
            "Breakout without conviction — wait for a strong-bodied confirmation bar",
        ])

    # BREAKDOWN — lost VWAP, or fell back under the pivot after being above.
    lost_vwap = vwap and pc >= vwap and c < vwap
    failed_pivot = pivot and pc >= pivot and c < pivot
    if (lost_vwap or failed_pivot) and a["dir"] == "down" and a["is_strong"]:
        lvl_name, lvl = ("VWAP", vwap) if lost_vwap else ("pivot", pivot)
        return out("BREAKDOWN", "deteriorating", "alert", [
            f"Lost {lvl_name} {lvl:.2f} on a {a['body_pct']:.0%}-body red bar"
            + (f" at {vol_ratio:.1f}× volume" if vol_ratio else ""),
            "Sellers controlled the bar through the level",
        ])

    # RECLAIM — took VWAP back with a strong body.
    if vwap and pc < vwap and c > vwap and a["is_strong"] and a["dir"] == "up":
        return out("RECLAIM", "constructive", "alert", [
            f"Reclaimed VWAP {vwap:.2f} with a {a['body_pct']:.0%}-body bar"
            + (f" on {vol_ratio:.1f}× volume" if vol_ratio else ""),
            "Buyers took the session's reference price back",
        ])

    # STALL — indecision at a level.
    at_level = any(_near(c, lv) for lv in (pivot, or_high, day_high) if lv)
    if at_level and a["is_doji"]:
        return out("STALL", "neutral", "info", [
            f"Doji ({a['body_pct']:.0%} body) sitting at the level — neither side in control",
        ])

    return None
