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
# How far back to look for a high-volume breakout when reporting recency.
# `high_vol_breakout` is the SAME-DAY (last bar) flag the strict is_buyable
# gate uses (book p.203). `days_since_breakout` additionally reports how many
# bars ago the most recent volume-confirmed breakout fired within this window
# (0 = today, None = none in window) so the FE 'Breakout: ≤1wk / Any' toggle
# can admit a name that broke out earlier in the week. The 15-bar cap is a
# pragmatic recency horizon, NOT a verbatim book number — the canonical buy
# point remains the breakout day itself.
BREAKOUT_RECENCY_LOOKBACK   = 15
# Window for COUNTING distinct breakouts a name has printed (≈ one trading year).
# Display-only — "how often does this stock actually break out?"
BREAKOUT_COUNT_LOOKBACK     = 252
# Volume-trend sparkline window — last N daily bars surfaced to the FE as a
# signed-volume series (≈ one month of trading). Display-only, see detect().
VOL_SPARK_BARS              = 20
# Day-count BACKSTOP (2026-05-31): volume is the primary distribution signal;
# the day count only acts as a safety net for a slow persistent bleed, and
# only when down-volume isn't being out-traded (ratio < 1). Raised from the
# old trigger-happy 4 so it catches persistence, not normal pullbacks.
DIST_DAYS_BACKSTOP          = 8

# ── "Whose hands fired this breakout?" footprint (TTLAC Ch.9 p.186) ───────────
# Minervini: a genuine breakout is institutions ACCUMULATING — "strong
# professional hands" absorbing supply on heavy volume with the close held near
# the high; a breakout that closes WEAK on heavy volume is suspect "churn"
# (p.188, "elevated volume without much price progress"). We read the breakout
# bar + its run-up to classify the hands behind it. Display-only; never scores.
BREAKOUT_RUNUP              = 10     # run-up window — "6 to 10 days of accelerated advance" (p.187)
BREAKOUT_CHURN_LOC         = 0.0    # close in the LOWER half of the bar's range on heavy vol = churn/suspect (p.188)
BREAKOUT_HEAVY_STRENGTH    = 70     # footprint strength ≥ this (and a big block) = heavy institutional
BREAKOUT_INST_STRENGTH     = 45     # footprint strength ≥ this = institutional
# Forward read — a breakout SETTING UP: a name coiling within this % BELOW its
# prior 21-bar high with accumulation building (VCP/pivot, TLSW Ch.7 + p.203).
EMERGING_NEAR_HIGH_PCT     = 3.0


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


def _date_str(idx) -> str:
    """Format a price-frame index label (Timestamp or string) as YYYY-MM-DD."""
    try:
        return idx.strftime("%Y-%m-%d")
    except Exception:
        return str(idx)[:10]


def breakout_footprint(df: pd.DataFrame, pos: int,
                       runup: int = BREAKOUT_RUNUP) -> Optional[dict]:
    """Whose hands fired the breakout at integer bar ``pos``?

    Minervini (TTLAC p.186): a real breakout is institutions ACCUMULATING —
    strong hands absorbing supply on heavy volume with the close pinned near the
    high. A breakout that closes WEAK (lower half of the range) on heavy volume
    is suspect "churn" — supply meeting the demand (p.188). We read three book
    tells at/around the breakout bar:

      * close LOCATION in the bar's range  -> buyers vs sellers in control at the
        close (the accumulation-day "upper half" test, p.76 / Ch.10);
      * VOLUME vs the 50-day average       -> how heavy the institutional block;
      * UP vs DOWN volume over the run-up  -> sustained accumulation, plus a
        pocket-pivot "big block" check (today's vol > any down-day vol).

    Returns ``{close_location, vol_ratio, up_days, down_days, up_down_vol_ratio,
    big_block, strength (0-100), hands}`` where ``hands`` ∈ {heavy_institutional,
    institutional, light, suspect}. Display-only; never feeds the score. ``None``
    on any problem."""
    try:
        n = len(df)
        if df is None or pos < 1 or pos >= n:
            return None
        h = float(df["high"].iloc[pos]); l = float(df["low"].iloc[pos])
        c = float(df["close"].iloc[pos]); vol = float(df["volume"].iloc[pos])
        rng = h - l
        close_loc = (((c - l) - (h - c)) / rng) if rng > 0 else 0.0   # -1..+1
        lo50 = max(0, pos - 49)
        avg50 = float(df["volume"].iloc[lo50:pos + 1].mean())
        vol_ratio = (vol / avg50) if avg50 and avg50 > 0 else None
        # Run-up: up vs down days + the volume that traded on each.
        wstart = max(1, pos - runup + 1)
        closes = df["close"].values
        vols = df["volume"].values
        up_days = down_days = 0
        up_vol = down_vol = 0.0
        max_down_vol = 0.0
        for p in range(wstart, pos + 1):
            v = float(vols[p])
            if closes[p] > closes[p - 1]:
                up_days += 1; up_vol += v
            elif closes[p] < closes[p - 1]:
                down_days += 1; down_vol += v
                if v > max_down_vol:
                    max_down_vol = v
        up_down_ratio = (up_vol / down_vol) if down_vol > 0 else None
        big_block = bool(vol > max_down_vol) if max_down_vol > 0 else True
        # Strength 0-100 — weight volume heaviest, then close location, then the
        # up/down balance. None-as-strong for the no-down-volume run-up.
        v_comp = min(1.0, max(0.0, (vol_ratio - 1.0) / 2.0)) if vol_ratio else 0.0
        loc_comp = min(1.0, max(0.0, (close_loc + 1.0) / 2.0))
        ud = up_down_ratio if up_down_ratio is not None else 2.0
        ud_comp = min(1.0, max(0.0, ud / 2.0))
        strength = int(round(100 * (0.40 * v_comp + 0.35 * loc_comp + 0.25 * ud_comp)))
        if vol_ratio and vol_ratio >= 1.5 and close_loc < BREAKOUT_CHURN_LOC:
            hands = "suspect"                          # heavy vol, weak close = churn (p.188)
        elif strength >= BREAKOUT_HEAVY_STRENGTH and big_block:
            hands = "heavy_institutional"
        elif strength >= BREAKOUT_INST_STRENGTH:
            hands = "institutional"
        else:
            hands = "light"
        return {
            "close_location":    round(close_loc, 2),
            "vol_ratio":         round(vol_ratio, 2) if vol_ratio else None,
            "up_days":           up_days,
            "down_days":         down_days,
            "up_down_vol_ratio": round(up_down_ratio, 2) if up_down_ratio is not None else None,
            "big_block":         big_block,
            "strength":          strength,
            "hands":             hands,
        }
    except Exception:
        return None


def emerging_breakout(df: pd.DataFrame,
                      near_pct: float = EMERGING_NEAR_HIGH_PCT,
                      runup: int = BREAKOUT_RUNUP) -> dict:
    """Forward read — is a breakout SETTING UP right now, and whose hands are
    building it?

    Not a breakout yet: a name coiling within ``near_pct`` BELOW its prior 21-bar
    high (the pivot, book p.203) with accumulation building underneath — the VCP
    /pivot setup (TLSW Ch.7) where volume dries in the base and a pocket pivot
    signals institutions stepping in just before the breakout. We require the
    price to be close to the pivot AND at least one accumulation tell (CMF > 0,
    up/down volume ≥ the accumulation threshold, or a pocket pivot).

    Returns ``{emerging, distance_to_high_pct, pivot_price, cmf,
    up_down_vol_ratio, pocket_pivot, hands, strength}``; ``{emerging: False}``
    when nothing is setting up. Display-only; a prediction, never a score."""
    try:
        if df is None or len(df) < 60:
            return {"emerging": False}
        c = df["close"].astype(float)
        last = float(c.iloc[-1])
        prior_high_21 = float(c.iloc[-22:-1].max())          # prior 21 bars, excl. today
        if prior_high_21 <= 0 or last >= prior_high_21:      # already broke out → not "emerging"
            return {"emerging": False}
        dist_pct = (prior_high_21 - last) / prior_high_21 * 100.0
        if dist_pct > near_pct:
            return {"emerging": False}
        cmf = _chaikin_money_flow(df, 20).get("cmf")
        pp = bool(_pocket_pivot(df).get("is_pocket_pivot"))
        n = len(df)
        wstart = max(1, n - runup)
        closes = c.values
        vols = df["volume"].values
        up_vol = sum(float(vols[p]) for p in range(wstart, n) if closes[p] > closes[p - 1])
        down_vol = sum(float(vols[p]) for p in range(wstart, n) if closes[p] < closes[p - 1])
        udr = (up_vol / down_vol) if down_vol > 0 else None
        accumulating = ((cmf is not None and cmf > 0)
                        or (udr is not None and udr >= ACCUM_RATIO_THRESHOLD)
                        or pp)
        if not accumulating:
            return {"emerging": False}
        loc_comp = min(1.0, max(0.0, ((cmf or 0.0) + 0.30) / 0.60))
        ud = udr if udr is not None else 2.0
        ud_comp = min(1.0, max(0.0, ud / 2.0))
        strength = int(round(100 * (0.45 * loc_comp + 0.35 * ud_comp + 0.20 * (1.0 if pp else 0.0))))
        hands = "institutional" if (strength >= BREAKOUT_INST_STRENGTH or pp) else "light"
        return {
            "emerging":             True,
            "distance_to_high_pct": round(dist_pct, 2),
            "pivot_price":          round(prior_high_21, 4),
            "cmf":                  round(cmf, 3) if cmf is not None else None,
            "up_down_vol_ratio":    round(udr, 2) if udr is not None else None,
            "pocket_pivot":         pp,
            "hands":                hands,
            "strength":             strength,
        }
    except Exception:
        return {"emerging": False}


def breakout_points(df: pd.DataFrame,
                    lookback: int = BREAKOUT_COUNT_LOOKBACK) -> list:
    """The distinct volume-confirmed breakout START bars over the trailing
    ``lookback`` bars — the rising edges of the SAME bo_series ``analyze()``
    counts as ``breakout_count`` (book p.203: a close above the prior 21-bar
    high on volume > 1.5× the 50-day average). Each point:

        {"date", "close", "volume", "vol_ratio"}

    Kept here, right next to the count, so the chart markers can NEVER drift
    from the number on the chip. Display-only; never feeds the score. Returns
    ``[]`` on any problem (too-short history, bad data).
    """
    out: list = []
    try:
        if df is None or len(df) < 60:
            return out
        c = df["close"].astype(float)
        v = df["volume"].astype(float)
        vol_avg50 = v.rolling(50).mean()
        prior_high_21 = c.rolling(21).max().shift(1)
        bo = ((vol_avg50 > 0) & (v > 1.5 * vol_avg50) & (c > prior_high_21)).fillna(False).values
        n = len(df)
        start = max(0, n - lookback)
        prev = False
        for p in range(start, n):
            f = bool(bo[p])
            if f and not prev:                 # rising edge = one breakout START
                av = float(vol_avg50.iloc[p])
                vi = float(v.iloc[p])
                ratio = (vi / av) if av > 0 else None
                out.append({
                    "date":      _date_str(df.index[p]),
                    "close":     round(float(c.iloc[p]), 4),
                    "volume":    int(vi),
                    "vol_ratio": round(ratio, 2) if ratio else None,
                    # WHO fired it — institutional accumulation vs churn (p.186).
                    "footprint": breakout_footprint(df, p),
                })
            prev = f
    except Exception:
        return []
    return out


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
    # FIXED 2026-05-29 per formula audit. Book p.71-72 (Stage 2 verbatim):
    #   "There are more up DAYS and up WEEKS on above-average volume than
    #    down DAYS and down WEEKS on above-average volume."
    # And p.75 (Stage 4 verbatim):
    #   "There are more down days and weeks on above-average volume than
    #    up days and up weeks on above-average volume."
    # The book is asking for a COUNT of qualifying days, NOT a sum of volume.
    # Previous formula:
    #   ratio = sum(up_day_volume) / sum(down_day_volume)
    # was a different thing — one big up day on huge volume could inflate
    # the ratio without there actually being "more up days" the way Minervini
    # defines it. A name with 5 up days totaling 100M volume vs 15 down days
    # totaling 60M volume would emit ratio=1.67 (accumulation) when the
    # book's count-of-days rule says it's distributing (3× more down days).
    # New formula counts above-average-volume days on each side, matching
    # the book's wording. The "above-average" qualifier (>= 50-day avg
    # volume) is also from p.71-72: "on above-average volume."
    avg_vol_50_for_ratio = float(vol50.mean()) if len(vol50) else 0.0
    if avg_vol_50_for_ratio > 0:
        above_avg_mask = vol50 >= avg_vol_50_for_ratio
        # ret > 0 on above-avg volume = "up day on above-average volume"
        n_up_days = int(((last50 > 0) & above_avg_mask).sum())
        n_dn_days = int(((last50 < 0) & above_avg_mask).sum())
        ratio = (n_up_days / n_dn_days) if n_dn_days > 0 else None
    else:
        n_up_days = n_dn_days = 0
        ratio = None
    # Dollar volume on up / down days (close × volume). Surfaces in the
    # accum_strong / accumulating / distributing drill modals as "actual $
    # accumulated last 50d" instead of just the abstract ratio.
    # Added 2026-05-29 per user request. Kept alongside the count-of-days
    # ratio above — the counts answer the book's question, the dollars
    # answer "how much money".
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

    # Breakout RECENCY (2026-06-02): the same `breakout` test, vectorized across
    # the trailing window, so the FE can admit a name whose volume-confirmed
    # breakout fired earlier in the week (not just on the last bar). A bar is a
    # breakout if its volume > 1.5× the trailing 50-day average AND its close
    # exceeds the highest close of the prior 21 bars. days_since_breakout = bars
    # since the most recent such bar within BREAKOUT_RECENCY_LOOKBACK (0 = today,
    # None = none in window). At the last bar this matches `breakout` exactly.
    days_since_breakout = None
    breakout_count = None
    breakout_window_bars = 0
    try:
        vol_avg50 = v.rolling(50).mean()
        prior_high_21 = c.rolling(21).max().shift(1)
        bo_series = ((vol_avg50 > 0) & (v > 1.5 * vol_avg50) & (c > prior_high_21)).fillna(False)
        window = bo_series.iloc[-BREAKOUT_RECENCY_LOOKBACK:]
        for k, fired in enumerate(reversed(list(window.values))):
            if bool(fired):
                days_since_breakout = k          # 0 = today, 1 = yesterday, ...
                break
        # COUNT of distinct breakouts over the trailing year — rising edges of
        # bo_series, so a multi-day push above the prior high counts as ONE.
        bo_win = bo_series.iloc[-BREAKOUT_COUNT_LOOKBACK:]
        breakout_window_bars = int(len(bo_win))
        prev = False
        cnt = 0
        for fired in bo_win.values:
            f = bool(fired)
            if f and not prev:
                cnt += 1
            prev = f
        breakout_count = cnt
    except Exception:
        days_since_breakout = None
        breakout_count = None

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

    # --- volume-TREND sparkline (2026-06-12) -------------------------------
    # Last 20 daily bars as a SIGNED-volume series so the FE can draw a mini
    # histogram: bar HEIGHT = |volume|, bar COLOR = up-day (close ≥ prior
    # close → positive) vs down-day (close < prior close → negative). Pairs
    # with the single-day relative-volume gauge to show whether volume is
    # BUILDING on up days / DRYING on pullbacks — the accumulation footprint
    # Minervini reads off the tape ("more up days on above-average volume",
    # Trade Like a Stock Market Wizard p.71-72).
    # DISPLAY-ONLY: never feeds the score or any gate (locked in contracts).
    vol_spark: list = []
    try:
        n = min(VOL_SPARK_BARS, len(v))
        recent_v = v.iloc[-n:]
        recent_d = c.diff().iloc[-n:]          # close − prior close; NaN only at the very first bar
        for i in range(n):
            vol_i = int(recent_v.iloc[i])
            d = recent_d.iloc[i]
            up = (d != d) or (d >= 0)          # NaN (no prior bar) → treat as up
            vol_spark.append(vol_i if up else -vol_i)
    except Exception:
        vol_spark = []

    return {
        # Legacy fields — DO NOT remove (frontend chips + scoring depend
        # on these). 2026-05-29: ratio formula now book-aligned —
        # COUNT of above-average-volume days, not sum of volumes.
        "up_down_vol_ratio":     round(ratio, 2) if ratio is not None else None,
        # New (2026-05-29): expose the raw day counts the ratio is built
        # from so the FE drill modal can show "8 up days vs 4 down days
        # on above-avg volume" instead of just the abstract ratio.
        "up_days_on_avg_vol":    n_up_days,
        "dn_days_on_avg_vol":    n_dn_days,
        "accumulation":          bool(ratio is not None and ratio >= ACCUM_RATIO_THRESHOLD),
        "vol_dryup":             round(dryup, 2) if dryup is not None else None,
        "is_drying_up":          bool(dryup is not None and dryup < 0.7),
        "high_vol_breakout":     bool(breakout),
        "days_since_breakout":   days_since_breakout,   # 0=today, None=no breakout in last 15 bars
        # How many DISTINCT volume-confirmed breakouts over the trailing year +
        # the window it was counted over. Display-only ("how often does this
        # name break out?"). Pairs with last_vol/avg_vol_50 (the ACTUAL volume,
        # not just the ratio).
        "breakout_count":        breakout_count,
        "breakout_window_bars":  breakout_window_bars,
        # The 21-bar high the breakout cleared = the breakout reference price.
        # Used as the "not extended" reference for bare-breakout setups (which
        # have no stable VCP/Power-Play pivot). Additive; book p.224 buy-zone gate.
        "recent_high":           round(recent_high, 4) if recent_high == recent_high else None,
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
        # Volume-trend sparkline — last 20 bars, signed by up/down day.
        # DISPLAY-ONLY (not scored). See the computation comment above.
        "vol_spark":             vol_spark,
    }
