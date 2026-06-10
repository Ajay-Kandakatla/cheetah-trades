"""Daily-bar candle reads for the qualifier verdicts (Ajay 2026-06-09: "if its
double bottom or triple bottom or candle sticks patterns or cup handle —
whatever it matches, [or] if it does not match").

HONESTY CONTRACT (same as the 5-min tape layer in scalping/candles.py): the
academic record on candlesticks as STANDALONE predictors is null — Marshall,
Young & Rose (2006) on US dailies, Horton (2009), Fock et al. (2005). So a
named formation here is CONTEXT for a decision, never a signal: each carries
Bulkowski's measured reversal frequency in the only permitted framing (daily
bars, hindsight-measured, no costs) right next to that academic caveat, and the
last-bar read stays descriptive supply/demand arithmetic — who won the bar.

Formation DEFINITIONS are structural conventions (what makes a hammer a
hammer); the trend gate exists because every reversal formation is defined
relative to a trend to reverse. Pure functions over daily OHLCV — no I/O.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from scalping.candles import anatomy, DOJI_BODY_PCT, WICK_DOMINANCE

# ── CONFIGURED conventions (definitional, not book formulas) ─────────────────
TREND_LOOKBACK = 10          # bars used to decide "after a decline / rise"
TREND_MIN_PCT = 3.0          # ±3% over the lookback = a trend worth reversing
SMALL_WICK_PCT = 0.15        # "little or no shadow" operationalized
TALL_BODY_PCT = 0.60         # "tall" candle = body ≥60% of its range (shared w/ tape layer)
SMALL_BODY_PCT = 0.30        # the morning-star "star" = body ≤30% of its range
RECENT_BARS = 1              # formations only count on the MOST RECENT bar (Ajay 2026-06-09:
                             # in-the-moment reads, ≤24h — a hammer from 3 days ago is history)
VOL_AVG_BARS = 50            # last-bar volume vs this average = participation read

# Bulkowski's measured reversal frequencies — VERIFIED VERBATIM against
# thepatternsite.com (adversarial pass 2026-06-09; see scalping_methodology.md).
# Quoted as "acts as a reversal X% of the time" — a frequency of direction in
# his hindsight sample, NEVER a win rate or an expected return. His own
# deflating verdicts ("near random", "dreadful") are quoted on purpose.
BULKOWSKI_CANDLE = {
    "hammer": ("Bulkowski: bullish reversal 60% of the time "
               "(reversal rank 26/103; overall performance rank 65/103)"),
    "shooting_star": ("Bulkowski: bearish reversal 59% of the time — he calls that "
                      "“near random” (overall performance rank 55/103)"),
    "doji": ("Bulkowski (southern doji): bullish reversal just 52% of the time — "
             "a coin flip (overall performance rank 78/103)"),
    "bullish_engulfing": ("Bulkowski: bullish reversal 63% of the time, BUT overall "
                          "performance rank 84/103 — “the post breakout performance "
                          "can be dreadful”"),
    "bearish_engulfing": ("Bulkowski: bearish reversal 79% of the time (rank 5/103) yet "
                          "“does not imply a lasting reversal” — overall rank 91/103"),
    "morning_star": ("Bulkowski: bullish reversal 78% of the time (rank 6/103) and the "
                     "rare candle with a strong post-breakout trend — overall rank 12/103"),
}

CAVEAT = ("Bulkowski daily-bar frequencies, hindsight-measured, no costs; "
          "academic tests find NO standalone trading value in candle patterns "
          "(Marshall 2006; Horton 2009). Context, not a signal.")


def _trend(closes: np.ndarray, end: int) -> str:
    """'down' / 'up' / 'flat' over the TREND_LOOKBACK bars ending at `end`-1."""
    if end - TREND_LOOKBACK < 0:
        return "flat"
    base = closes[end - TREND_LOOKBACK]
    if base <= 0:
        return "flat"
    chg = (closes[end - 1] / base - 1) * 100
    if chg <= -TREND_MIN_PCT:
        return "down"
    if chg >= TREND_MIN_PCT:
        return "up"
    return "flat"


def _bar(df: pd.DataFrame, i: int) -> Optional[dict]:
    row = df.iloc[i]
    a = anatomy(float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]))
    return a


def _formations_at(df: pd.DataFrame, i: int, closes: np.ndarray) -> list:
    """Named formations completed at bar i (definitional checks + trend gate)."""
    out = []
    a = _bar(df, i)
    if a is None:
        return out
    trend = _trend(closes, i)
    date = df.index[i].strftime("%Y-%m-%d")

    # Hammer — lower wick ≥2× body, little upper shadow, after a decline.
    if (trend == "down" and a["lower_wick_dominant"]
            and a["upper_wick_pct"] <= SMALL_WICK_PCT and not a["is_doji"]):
        out.append({"name": "hammer", "date": date, "read": "bullish_reversal_setup",
                    "note": (f"Lower wick {a['lower_wick_pct']:.0%} of the bar vs body "
                             f"{a['body_pct']:.0%} after a decline — sellers pushed it down "
                             "intraday and lost the bar")})

    # Shooting star — upper wick ≥2× body, little lower shadow, after a rise.
    if (trend == "up" and a["upper_wick_dominant"]
            and a["lower_wick_pct"] <= SMALL_WICK_PCT and not a["is_doji"]):
        out.append({"name": "shooting_star", "date": date, "read": "bearish_warning",
                    "note": (f"Upper wick {a['upper_wick_pct']:.0%} of the bar vs body "
                             f"{a['body_pct']:.0%} after a rise — buyers pushed it up "
                             "intraday and lost the bar")})

    # Doji — open ≈ close. Indecision, NOT a reversal call (Horton 2009).
    if a["is_doji"]:
        out.append({"name": "doji", "date": date, "read": "indecision",
                    "note": f"Body {a['body_pct']:.1%} of the range — neither side won the day"})

    # Engulfings — two-bar, body strictly engulfs the prior body, against trend.
    if i >= 1:
        prev = df.iloc[i - 1]
        last = df.iloc[i]
        po, pc = float(prev["open"]), float(prev["close"])
        lo_, lc = float(last["open"]), float(last["close"])
        if trend == "down" and pc < po and lc > lo_ and lo_ <= pc and lc >= po \
                and abs(lc - lo_) > abs(pc - po):
            out.append({"name": "bullish_engulfing", "date": date, "read": "bullish_reversal_setup",
                        "note": "Up body swallowed the prior down body after a decline — "
                                "demand absorbed yesterday's selling and then some"})
        if trend == "up" and pc > po and lc < lo_ and lo_ >= pc and lc <= po \
                and abs(lc - lo_) > abs(pc - po):
            out.append({"name": "bearish_engulfing", "date": date, "read": "bearish_warning",
                        "note": "Down body swallowed the prior up body after a rise — "
                                "supply absorbed yesterday's buying and then some"})

    # Morning star — three bars: tall black in a downtrend, a small body whose
    # body GAPS below it, then a tall white gapping above the star's body and
    # closing at least midway into the first body (Bulkowski's exact ID rules).
    if i >= 2 and trend == "down":
        b1, b2, b3 = df.iloc[i - 2], df.iloc[i - 1], df.iloc[i]
        a1, a2, a3 = (_bar(df, i - 2), _bar(df, i - 1), a)
        if a1 and a2 and a3:
            o1, c1 = float(b1["open"]), float(b1["close"])
            o2, c2 = float(b2["open"]), float(b2["close"])
            o3, c3 = float(b3["open"]), float(b3["close"])
            tall1 = c1 < o1 and a1["body_pct"] >= TALL_BODY_PCT
            star_gap_dn = max(o2, c2) < min(o1, c1) and a2["body_pct"] <= SMALL_BODY_PCT
            tall3 = (c3 > o3 and a3["body_pct"] >= TALL_BODY_PCT
                     and min(o3, c3) > max(o2, c2) and c3 >= (o1 + c1) / 2)
            if tall1 and star_gap_dn and tall3:
                out.append({"name": "morning_star", "date": date,
                            "read": "bullish_reversal_setup",
                            "note": "Panic bar, a gapped-down stall, then a strong white bar "
                                    "closing back into the decline — demand retook control "
                                    "across three sessions"})
    for f in out:
        f["stat"] = BULKOWSKI_CANDLE.get(f["name"], "")
        f["caveat"] = CAVEAT
    return out


def read_daily(df: pd.DataFrame) -> Optional[dict]:
    """Candle context for one symbol's daily frame.

    Returns {"formations": [...recent named formations...],
             "last_bar": descriptive anatomy of the most recent bar,
             "trend": trend into the last bar} or None on a too-short frame.
    """
    if df is None or len(df) < TREND_LOOKBACK + RECENT_BARS + 1:
        return None
    closes = df["close"].to_numpy(dtype=float)
    n = len(df)

    formations: list = []
    for i in range(n - RECENT_BARS, n):
        formations.extend(_formations_at(df, i, closes))
    # newest first; one entry per name (keep the most recent)
    seen = set()
    formations = [f for f in reversed(formations)
                  if not (f["name"] in seen or seen.add(f["name"]))]

    a = _bar(df, n - 1)
    last_bar = None
    if a is not None:
        vols = df["volume"].to_numpy(dtype=float)
        avg = float(vols[-(VOL_AVG_BARS + 1):-1].mean()) if n > VOL_AVG_BARS else None
        vol_ratio = round(float(vols[-1]) / avg, 2) if avg and avg > 0 else None
        who = ("buyers" if a["dir"] == "up" and a["is_strong"]
               else "sellers" if a["dir"] == "down" and a["is_strong"]
               else "neither side decisively")
        last_bar = {**a, "date": df.index[-1].strftime("%Y-%m-%d"),
                    "vol_ratio": vol_ratio,
                    "read": (f"{who.capitalize()} controlled the last bar "
                             f"({a['body_pct']:.0%} body, CLV {a['clv']:+.2f}"
                             + (f", {vol_ratio}× avg volume)" if vol_ratio is not None else ")"))}
    return {"formations": formations, "last_bar": last_bar,
            "trend": _trend(closes, n)}
