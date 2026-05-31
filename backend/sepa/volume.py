"""Volume analysis — accumulation / distribution signals.

Minervini Ch 10: "stocks under accumulation will almost always show tightness
in price with volume contracting." We measure multiple complementary signals:

  * up_down_vol_ratio      — 50-day sum(up-day vol) / sum(down-day vol).
                             >1.3 = real accumulation. Median of US Russell
                             1000 hovers ~1.0; threshold of 1.0 used to
                             trip ~50% of universe → useless. Raised to
                             1.3 on 2026-05-21 to make the signal mean
                             something (now trips ~10-15%).
  * pocket_pivot           — TODAY'S up-day volume > MAX down-day volume of
                             the prior 10 sessions. Minervini's go-to
                             sub-base buy signal — institutional
                             footprint BEFORE the textbook breakout.
  * cmf_20                 — Chaikin Money Flow over 20 sessions. Combines
                             close-position-within-bar-range with volume.
                             Pure accumulation indicator that doesn't depend
                             on the day's direction. >+0.10 = institutional
                             accumulation; <-0.10 = distribution.
  * accumulation_days_25   — count of "real" accumulation days in last 25:
                             close UP + close in upper half of range +
                             volume > 50-day avg. Tighter than the bare
                             up_down_vol_ratio.
  * distribution_days_25   — Minervini's per-stock distribution count.
                             Close DOWN >0.2% on heavier-than-yesterday
                             volume. ≥4 in 25 = institutional selling.
  * vol_dryup              — 10-day avg vol / 50-day avg vol. <0.7 = drying
                             up (constructive late-base signal).
  * high_vol_breakout      — latest bar vol > 1.5× 50-day avg AND close
                             above 21-day high. Strict breakout flag.

The signals stack — a name with pocket_pivot=True AND cmf_20>0.15 AND
up_down_vol_ratio>1.5 AND distribution_days_25=0 is in a different
league than one with just up_down_vol_ratio=1.05.

Score impact: the SEPA score uses 'accumulation' + 'high_vol_breakout' as
binary inputs (sepa/scanner.py). With the threshold tightening, fewer
names get the accumulation point — but the names that DO get it have a
much higher signal-to-noise ratio.
"""
from __future__ import annotations

from typing import Optional
import pandas as pd


# ---------------------------------------------------------------------------
# Thresholds — tuned 2026-05-21 against a 977-name Russell 1000 sample.
# ---------------------------------------------------------------------------
# up_down_vol_ratio threshold for the binary `accumulation` flag.
# Old value (1.0) tripped 49% of universe — meaningless.
# 1.3 trips ~12% (median 0.99, p75 1.21, p90 1.45).
ACCUM_RATIO_THRESHOLD       = 1.30
ACCUM_STRONG_THRESHOLD      = 1.50
DIST_RATIO_THRESHOLD        = 0.70   # ratio <= 0.7 = distribution
# Chaikin Money Flow zones — academic literature commonly uses ±0.05;
# we use ±0.10 to bias toward higher-signal events.
CMF_INFLOW_THRESHOLD        = 0.10
CMF_OUTFLOW_THRESHOLD       = -0.10
# Accumulation day = up close + close in upper half + volume > 50-day avg.
# Distribution day = down close ≤ -0.2% + volume > 50-day avg (book p.76,
#   "down days on ABOVE-AVERAGE volume"). Symmetric with accumulation.
DIST_DAY_DOWN_PCT           = -0.002
DIST_DAY_LOOKBACK           = 25
# Day-count BACKSTOP (2026-05-31): volume is the primary distribution signal;
# the day count only acts as a safety net for a slow persistent bleed, and
# only when down-volume isn't being out-traded (ratio < 1). Raised from the
# old trigger-happy 4 so it catches persistence, not normal pullbacks.
DIST_DAYS_BACKSTOP          = 8


def _safe_float(x) -> Optional[float]:
    try:
        f = float(x)
        if f != f:           # NaN
            return None
        return f
    except Exception:
        return None


def _chaikin_money_flow(df: pd.DataFrame, period: int = 20) -> dict:
    """Chaikin Money Flow over `period` sessions.

    Formula:
        money_flow_multiplier = ((close - low) - (high - close)) / (high - low)
        money_flow_volume     = mfm * volume                  (in SHARES)
        cmf = sum(mfv, period) / sum(volume, period)          (ratio -1..+1)

    Range of cmf: -1.0 to +1.0. Positive = buying pressure on close near
    highs; negative = selling pressure on close near lows.

    Also returns the DOLLAR money flow over the same window:
        money_flow_dollar = mfm * volume * close              (in DOLLARS)
        net_dollar_flow   = sum(money_flow_dollar, period)
    so drill modals can show "Net $-flow last 20d: +$1.2B" instead of just
    the abstract CMF ratio.
    """
    if len(df) < period:
        return {"cmf": None, "net_dollar_flow": None}
    sub = df.iloc[-period:].copy()
    rng = (sub["high"] - sub["low"]).replace(0, pd.NA)
    mfm = ((sub["close"] - sub["low"]) - (sub["high"] - sub["close"])) / rng
    mfv_shares = mfm * sub["volume"]
    total_vol = float(sub["volume"].sum())
    if total_vol <= 0:
        return {"cmf": None, "net_dollar_flow": None}
    cmf = float(mfv_shares.sum() / total_vol)
    if cmf != cmf:           # NaN guard
        return {"cmf": None, "net_dollar_flow": None}
    # Dollar money flow — weight each day's MFV by its close price so the
    # output is in dollars not shares. Positive = net $ inflow over 20d,
    # negative = net $ outflow. Surfaced in drill modals.
    try:
        mfv_dollars = mfv_shares * sub["close"]
        net_dollar_flow = float(mfv_dollars.sum())
        if net_dollar_flow != net_dollar_flow:
            net_dollar_flow = None
    except Exception:
        net_dollar_flow = None
    return {"cmf": cmf, "net_dollar_flow": net_dollar_flow}


def _pocket_pivot(df: pd.DataFrame, lookback: int = 10) -> dict:
    """Minervini's pocket pivot detector.

    True iff:
      * TODAY closed up (close > prior_close)
      * TODAY's volume > MAX volume of any down-day in the last `lookback` sessions

    Returns the trigger detail so the UI can show "today vol 1.8M vs prior-10d
    max down-day 1.5M" — concrete confirmation, not just a boolean.
    """
    if len(df) < lookback + 2:
        return {"is_pocket_pivot": False}
    today = df.iloc[-1]
    prev = df.iloc[-2]
    if not (today["close"] > prev["close"]):
        return {"is_pocket_pivot": False}
    window = df.iloc[-(lookback + 1):-1]   # the `lookback` prior bars
    closes = window["close"].values
    vols = window["volume"].values
    # Identify down-days within the window.
    down_vols = [v for c_today, c_yesterday, v in
                 zip(closes[1:], closes[:-1], vols[1:])
                 if c_today < c_yesterday]
    if not down_vols:
        # No down-days in the window — bullish enough that the pocket
        # pivot test is trivially satisfied. Flag it.
        return {
            "is_pocket_pivot": True,
            "today_vol": int(today["volume"]),
            "max_down_vol_lookback": 0,
            "strength_x": None,
            "reason": "no down-days in lookback",
        }
    max_down_vol = max(down_vols)
    is_pp = float(today["volume"]) > float(max_down_vol)
    return {
        "is_pocket_pivot": bool(is_pp),
        "today_vol": int(today["volume"]),
        "max_down_vol_lookback": int(max_down_vol),
        "strength_x": round(today["volume"] / max_down_vol, 2) if max_down_vol > 0 else None,
    }


def _count_accum_dist_days(df: pd.DataFrame,
                            lookback: int = DIST_DAY_LOOKBACK) -> dict:
    """Count accumulation + distribution days in last `lookback` sessions.

    Accumulation day:
      * close up vs prior
      * close in upper half of today's range
      * volume > 50-day avg (heavier-than-typical institutional footprint)

    Distribution day (book p.76 — "down days … on ABOVE-AVERAGE volume"):
      * close down ≥ 0.2%
      * volume > 50-day average (institutional selling footprint)

    NOTE (2026-05-30 fix): previously this required only `volume > yesterday`
    (the O'Neil/IBD intraday-relative definition). That was ASYMMETRIC with
    the accumulation-day test above, which requires above-AVERAGE volume —
    so a down day on volume merely higher than the prior session but still
    below average was over-counted as distribution. Minervini's literal
    language (p.76, Stage 4 / topping signature) is "above-average volume,"
    so we now use the 50-day average for BOTH counters. This stops the
    "N distribution days → distributing → AVOID" flag from over-firing on
    ordinary pullbacks (the CVGI-class false-avoid).

    These two counters are complementary: a stock with 8 accum days + 1
    dist day is in a very different state than 2 accum + 6 dist, even
    if their up_down_vol_ratio looks similar.
    """
    if len(df) < lookback + 5:
        return {"accumulation_days_25": 0, "distribution_days_25": 0}
    window = df.iloc[-(lookback + 1):]
    closes = window["close"].values
    highs  = window["high"].values
    lows   = window["low"].values
    vols   = window["volume"].values
    # 50-day vol avg up to (but not including) the lookback window.
    avg_window = df.iloc[-(lookback + 51):-lookback]
    if len(avg_window) < 30:
        # Not enough history — degrade to whole-series avg.
        avg_vol = float(df["volume"].mean())
    else:
        avg_vol = float(avg_window["volume"].mean())
    if avg_vol <= 0:
        avg_vol = 1.0
    accum = 0
    dist = 0
    for i in range(1, len(window)):
        c_today = closes[i]
        c_yest  = closes[i - 1]
        h_today = highs[i]
        l_today = lows[i]
        v_today = vols[i]
        v_yest  = vols[i - 1]
        if h_today == l_today:
            continue
        upper_half = (c_today - l_today) / (h_today - l_today) >= 0.5
        # Accumulation day
        if c_today > c_yest and upper_half and v_today > avg_vol:
            accum += 1
        # Distribution day (book p.76: down ≥ 0.2% on ABOVE-AVERAGE volume).
        # Symmetric with the accumulation test above (both use avg_vol).
        if c_yest > 0 and ((c_today - c_yest) / c_yest) <= DIST_DAY_DOWN_PCT \
                and v_today > avg_vol:
            dist += 1
    return {"accumulation_days_25": accum, "distribution_days_25": dist}


def _strength_label(ratio: Optional[float], cmf: Optional[float],
                     dist_days: int) -> str:
    """Human-readable summary that combines the three primary signals.

    Strong is rare — ALL three need to align. Distributing is also rare
    and serious. Most names land in 'accumulating' or 'neutral'.
    """
    if ratio is None:
        return "unknown"
    # PRIMARY signal is VOLUME-weighted, not a day count (2026-05-31). Research
    # note: O'Neil's distribution-DAY count (4-5 in ~4-5 weeks) is a MARKET /
    # index timing tool, not a per-stock read; the per-stock convention (incl.
    # Minervini-style platforms) is the up/down volume ratio + money flow,
    # which captures the MAGNITUDE of selling. The old `dist_days >= 4` hard
    # gate flagged names like ARM as distributing even while up/down vol was
    # 1.92 and CMF was +0.32 (clear accumulation) — a false topping call.
    if ratio <= DIST_RATIO_THRESHOLD or (cmf is not None and cmf <= CMF_OUTFLOW_THRESHOLD):
        return "distributing"
    # BACKSTOP for a slow persistent bleed the volume balance might miss —
    # but GATED on the volume balance so it can't fire on pullbacks inside an
    # advance: many down-on-volume days AND down-volume isn't being out-traded
    # (ratio < 1). ARM (8 dist days but ratio 1.92) is correctly excluded.
    if dist_days >= DIST_DAYS_BACKSTOP and ratio < 1.0:
        return "distributing"
    # Strong accumulation requires alignment.
    if (ratio >= ACCUM_STRONG_THRESHOLD
            and (cmf is None or cmf >= CMF_INFLOW_THRESHOLD)
            and dist_days <= 1):
        return "strong"
    if ratio >= ACCUM_RATIO_THRESHOLD:
        return "accumulating"
    return "neutral"


def analyze(df: pd.DataFrame) -> Optional[dict]:
    """Full per-ticker volume read.

    Returns the full set of signals. All numeric fields are pre-rounded
    so the JSON payload stays compact for the SEPA list (977 candidates ×
    payload size adds up). Booleans are normalized to bool() so pymongo
    doesn't store numpy.bool_ which then trips JSON serializers downstream.
    """
    if df is None or len(df) < 60:
        return None
    c = df["close"]
    v = df["volume"]
    rets = c.pct_change()
    last50 = rets.iloc[-50:]
    vol50 = v.iloc[-50:]

    # --- legacy fields (kept for backward compat with existing UI / score) ---
    up_vol = float(vol50[last50 > 0].sum())
    dn_vol = float(vol50[last50 < 0].sum())
    ratio = up_vol / dn_vol if dn_vol > 0 else None
    # Dollar volume on up / down days (close × volume). Surfaces in the
    # accum_strong / accumulating / distributing drill modals as "actual $
    # accumulated last 50d" instead of just the abstract ratio.
    # Added 2026-05-29 per user request.
    close50 = c.iloc[-50:]
    dv50 = (close50 * vol50)
    up_dollar_vol = float(dv50[last50 > 0].sum())
    dn_dollar_vol = float(dv50[last50 < 0].sum())
    net_dollar_vol = up_dollar_vol - dn_dollar_vol

    avg50 = float(vol50.mean()) if len(vol50) else 0
    avg10 = float(v.iloc[-10:].mean())
    dryup = (avg10 / avg50) if avg50 > 0 else None

    recent_high = float(c.iloc[-22:-1].max()) if len(c) >= 22 else float("nan")
    last_vol = float(v.iloc[-1])
    last_close = float(c.iloc[-1])
    breakout = (
        avg50 > 0
        and last_vol > 1.5 * avg50
        and recent_high == recent_high
        and last_close > recent_high
    )

    # --- new signals (2026-05-21 upgrade) ---
    cmf_info = _chaikin_money_flow(df, period=20)
    cmf = cmf_info.get("cmf")
    cmf_dollar_flow_20 = cmf_info.get("net_dollar_flow")  # dollars
    cmf_signal = (
        "inflow"  if cmf is not None and cmf >= CMF_INFLOW_THRESHOLD  else
        "outflow" if cmf is not None and cmf <= CMF_OUTFLOW_THRESHOLD else
        "neutral"
    )
    pp_info = _pocket_pivot(df, lookback=10)
    counts = _count_accum_dist_days(df, lookback=DIST_DAY_LOOKBACK)
    strength = _strength_label(ratio, cmf, counts["distribution_days_25"])

    return {
        # Legacy fields — DO NOT remove (frontend chips + scoring depend
        # on these). Threshold-tightening for `accumulation` flag is
        # the one behavior change.
        "up_down_vol_ratio":     round(ratio, 2) if ratio is not None else None,
        "accumulation":          bool(ratio is not None and ratio >= ACCUM_RATIO_THRESHOLD),
        "vol_dryup":             round(dryup, 2) if dryup is not None else None,
        "is_drying_up":          bool(dryup is not None and dryup < 0.7),
        "high_vol_breakout":     bool(breakout),
        "last_vol":              int(last_vol),
        "avg_vol_50":            int(avg50),
        # New fields — additive, no rename of existing keys.
        "accumulation_strength": strength,           # strong/accumulating/neutral/distributing
        "pocket_pivot":          bool(pp_info.get("is_pocket_pivot")),
        "pocket_pivot_detail":   pp_info,             # full breakdown for UI
        "accumulation_days_25":  counts["accumulation_days_25"],
        "distribution_days_25":  counts["distribution_days_25"],
        "cmf_20":                round(cmf, 3) if cmf is not None else None,
        "cmf_signal":            cmf_signal,
        # Dollar flows — added 2026-05-29 so drill modals can show actual
        # $ accumulation instead of just ratios. Up/dn dollar volume over
        # 50d for the accum_strong/accumulating/distributing drills; CMF
        # net $ flow over 20d for the cmf_inflow/cmf_outflow drills.
        "up_dollar_vol_50":      int(up_dollar_vol),
        "dn_dollar_vol_50":      int(dn_dollar_vol),
        "net_dollar_vol_50":     int(net_dollar_vol),
        "cmf_dollar_flow_20":    int(cmf_dollar_flow_20) if cmf_dollar_flow_20 is not None else None,
    }
