"""Bounce quality — does anything on top of "bouncing" make a demand PUSH better?

    docker cp studies/bounce_quality_study.py cheetah-market-app-api-1:/tmp/bq.py
    docker exec cheetah-market-app-api-1 sh -c \
        'cd /app && PYTHONPATH=/app python -u /tmp/bq.py'

WHY THIS FILE EXISTS. Ajay 2026-09-09, after CASY: "I need only bullish reversal
stocks that touched demand zone and bouncing back.. Those are the only alerts I
need and mood has to be bullish too with reversal. After a stationary bottommed
stocks as I caught a fallig knife today with Casy". Four conditions. One of them
shipped that morning (`alert_gates.direction_gate` = bouncing only); two exist in
the codebase and are not wired to the phone (`sd_liquidity.is_falling_knife`,
`alert_gates.mood_read`); the fourth ("stationary bottomed") did not exist, and
three parallel agents each proposed a definition of it. Rule "ship the backtest
with the claim" says none of them may reach the phone on an anecdote.

This script measures all four, separately and stacked, on the SAME cohort, with a
placebo beside every rate and a permutation p-value beside every separation.
Nothing here is wired to anything: it is a measurement, not a change.

THE COHORT (the baseline, i.e. the alert as it fires TODAY)
-----------------------------------------------------------
A replay over daily CLOSED bars of the `full` universe. At every bar j with at
least `--floor` (252) prior bars:

  * bands = `price_zones.compute(bars[:j], last_price=close[j], max_zones=None,
    **demand_reentry.zone_geom())` — the geometry `zone_store` itself passes.
    Bars STRICTLY BEFORE j. `max_zones=None` or the band list is trimmed and
    events silently vanish.
  * for every demand band: `alert_gates.approach_read(close[j], band,
    close[j-1], low[j])`, then `room_gate` (>= 5% to the first PROVEN band
    overhead) and `demand_proximity_gate` (<= 1% above the band top).
  * the event's band, when more than one qualifies, is the one with the HIGHEST
    floor — the nearest support under the print, and the stop the push's
    plan_txt would name. `n_bands` records how many qualified.

Every direction is collected, so the cohort the shipped direction gate ALREADY
removes (falling / settling / reclaiming / resting / lifting) is available as a
control. BASELINE = the `bouncing` rows.

THE TRADE (how he trades it, from the push's own plan text)
-----------------------------------------------------------
entry = close[j] (the print proxy — see LIMITATIONS), stop = band floor less
`alert_gates.STOP_BUFFER_PCT` (0.5%), target = the first proven band overhead
(`room_read.target`; CLEAR = no target, the trade can only stop or time out).
Bars j+1..j+hold: stop checked BEFORE target inside a bar (the pessimistic side
of the intrabar ambiguity), else exit at close[j+hold]. Default clock 20
sessions; `--hold 60` is `zone_backtest.MAX_HOLD_BARS`, the house episode clock.

THE FOUR GATES
--------------
  knife     not `sd_liquidity.is_falling_knife(structure_read(bars[:j]), ...)`
            with the live windows (swing 5, ma50 vs ma50 10 bars prior).
  mood      `mood.mood(bars[:j])["score"] >= T`, T swept {0,10,25,40,60}.
  vc        DEFINITION 1, range/drift contraction at the low (agent A).
  shelf     DEFINITION 2, a touched, time-tested shelf (agent B).
  rp        DEFINITION 3, close-position in the trailing range (agent C).
All three "stationary bottom" definitions are implemented here verbatim from the
three proposals and are independently switchable. No favourite is picked.

EVERY GATE IS A TIGHTENING. Each is an AND-term appended to the existing chain;
none can add a push. Loosening a gate to raise a hit rate is not on the table.

PLACEBOS, stated exactly
------------------------
  1. size-matched random keep — `--placebo-draws` random subsets of the baseline
     of the SAME size as the gate's kept set. The 5th-95th percentile band of
     their expectancy is what "keeping n_kept of these events at random" pays. A
     kept expectancy inside that band is a gate that did nothing.
  2. the excluded cohort — kept vs dropped, with a one-sided permutation p for
     the null that the gate is a random relabelling of the same events.
  3. the direction control — the same measurement on the non-bouncing rows the
     shipped gate already drops.

WHAT IT MEASURED (run 2026-09-09, `full` universe, clock 20)
------------------------------------------------------------
31,861 bouncing events, 2,462 names, 2025-09-09 -> 2026-06-12, 192 dates.
BASELINE +0.226R, 24.1% win, exits 19% target / 75% stop / 6% clock.

  not falling knife        keep 59.4%   +0.220R   Δ -0.006R  CI[-0.049,+0.037]  inert
  mood >= 25 (MOOD_BUY)    keep 15.7%   +0.132R   Δ -0.094R  CI[-0.190,+0.005]  HARMFUL
  DEF1 vc range_settled    keep  0.5%   +0.150R   Δ -0.076R  CI[-0.482,+0.355]  n too small
  DEF2 shelf stationary    keep 38.1%   +0.247R   Δ +0.020R  CI[-0.038,+0.075]  inert
  DEF3 range_position      keep 39.8%   +0.167R   Δ -0.059R  CI[-0.134,+0.013]  HARMFUL
  THE FULL STACK
  nk + mood>=25 + any def  keep 12.3%   +0.052R   Δ -0.174R  CI[-0.272,-0.075]  HARMFUL, CI excludes 0

NOT ONE OF THE FOUR GATES PAID. Three are inside the size-matched random-keep
placebo band; the stack Ajay asked for is measurably WORSE than the alert as it
fires today, at every clock from 5 to 60 sessions and with one event per date.

The MECHANISM section says why, and it is the useful part: the win rate is FLAT
at ~24% across every mood bucket, every knife verdict and every definition. What
the gates change is the SIZE of the trade they leave. Room to the first proven
lid falls from 14.7% (bearish) to 9.5% (mood >= 40) while the stop distance
rises, so the reward the setup can even pay drops from 5.9x risk to 3.3x. These
gates do not select better bounces; they select SMALLER ones. Only DEF2 moved
the hit rate at all (26.1% vs 24.1%, stops 73% vs 75%) and it paid for that with
payoff, netting a wash.

The direction gate that shipped this morning gets the same treatment and the
same answer: bouncing +0.226R vs the +0.296R of every direction it drops
(perm p=0.993). It was asked for after a loss, not measured, and this window
does not support it either. That is not a recommendation to remove it — Ajay's
reason for it was "I am late by the time it reaches me", which is about which
alerts he can act on, not about expectancy — but the expectancy claim should
never be made for it.

AND YET CASY FAILS ALL FIVE. `--casy` shows every gate blocking it for the right
structural reasons. That is the trap this file exists to expose: a gate that
rejects the one trade that hurt is not thereby a gate that pays. CASY is n=1;
these gates reject ~85% of the events that worked too.

NO LOOKAHEAD, and the four traps that have produced wrong numbers in this repo:
  * bands at bar j from bars[:j] only, `max_zones=None`.
  * the three definitions read a TAIL SLICE of closed bars strictly before j; no
    `dropna()` runs before any rolling window (the hot_pullback off-by-49).
  * `price_zones.compute` returns "demand_zones"/"supply_zones".
  * `sepa.prices.load_prices` ignores `period` and returns ~501 bars, so with a
    252-bar floor only ~1 year of bars per name is reachable. Frames here are
    read straight from the Mongo bars cache for speed; same data, same limit.

LIMITATIONS (read before quoting any number from this file)
-----------------------------------------------------------
  * ~2 years of cached bars per name, minus a 252-bar floor and the clock, is
    ONE regime. Nothing here is a multi-cycle result.
  * The print is the daily CLOSE. A live push fires intraday at some price >=
    0.5% off the day's low; the close is the only price a daily replay can
    honestly stand behind, and it is neither the best nor the worst fill. Every
    event's approach is therefore an end-of-day read of an intraday condition.
  * The live demand_alert also needs market cap >= $1B (`demand_alerts
    .MIN_CAP_USD`). Historical caps are not available here, so `--min-dvol`
    (median 50-day dollar volume) is offered as a liquidity stand-in and
    defaults to OFF. The cohort is therefore WIDER than what actually pushes.
  * Mood mirrors the live read on a strictly-prior frame (`closed_only=False` on
    bars[:j], i.e. through j-1). The live `mood_read` passes an already-closed
    frame with `closed_only=True` and so drops one MORE bar; that is a live
    quirk, not a rule, and reproducing it would only add lag.
  * One event per (symbol, date). Live can ring the same name on two bands.
  * No slippage, no commissions, no gaps modelled at the stop: a stop exit is
    booked AT the stop even when the bar gapped through it. Stop-side results
    are therefore optimistic — which flatters, not hurts, the gates that keep
    stop-heavy names.
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

import numpy as np
import pandas as pd

from sepa import prices, universe
from supply_demand import alert_gates as AG
from supply_demand import demand_reentry
from supply_demand import mood as MD
from supply_demand import price_zones
from supply_demand import sd_liquidity as SL

MIN_HISTORY_BARS = 252        # bars of history before an event counts
HOLD_SESSIONS = 20            # the reported clock
# Every event is simulated at ALL of these clocks in one pass, and the event
# window is bounded by the LONGEST of them, so a clock comparison is the same
# events read at different horizons rather than four different cohorts.
# 60 = zone_backtest.MAX_HOLD_BARS, the house episode clock.
CLOCKS = (5, 10, 20, 60)
DEF_TAIL_BARS = 150           # closed bars handed to the three definitions
STRUCTURE_SWING_WINDOW = 5    # demand_reentry.STRUCTURE_SWING_WINDOW
MA_SLOPE_LOOKBACK = 10        # demand_reentry.MA_SLOPE_LOOKBACK
PERM_DRAWS = 2_000
BOOT_DRAWS = 5_000
PLACEBO_DRAWS = 2_000
MOOD_SWEEP = (0.0, 10.0, 25.0, 40.0, 60.0)      # 10 = MOOD_CONSTRUCTIVE, 25 = MOOD_BUY


# ─────────────────────────────────────────────────────────────────────────────
# DEFINITION 1 — "range_settled" (volatility contraction at the low).
# Transcribed from studies/stationary_bottom_vc_study.py so this script stays
# self-contained and deterministic. UNKNOWN FAILS CLOSED.
# ─────────────────────────────────────────────────────────────────────────────
VC_BASE_LEN = 10          # sweep 5..20
VC_DECLINE_LEN = 20       # sweep 10..40
VC_CONTRACTION_MAX = 0.75
VC_DRIFT_MAX_ATR = 1.0
VC_EXPANSION_MAX_X = 1.0
VC_LOW_PROX_ATR = 1.0
VC_HALF_STEP_MAX = 1.10


def tr_pct(df: pd.DataFrame) -> np.ndarray:
    """Per-bar true range as % of the PRIOR close. Percent, not dollars: a name
    that fell 40% shows a shrinking dollar range from the price level alone,
    which would fake a contraction."""
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    pc = np.empty_like(c)
    pc[0] = c[0]
    pc[1:] = c[:-1]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return np.where(pc > 0, tr / pc * 100.0, np.nan)


def vc_settled(df, base_len: int = VC_BASE_LEN, dec_len: int = VC_DECLINE_LEN) -> dict:
    """DEFINITION 1. Range and drift ran out, at the low, before anything bounced."""
    need = int(base_len) + int(dec_len) + 1
    if df is None or len(df) < need:
        return {"ok": False, "reason": "history"}
    n = len(df)
    b0 = n - int(base_len)
    d0 = n - int(base_len) - int(dec_len)
    t = tr_pct(df)
    c = df["close"].to_numpy(dtype=float)
    lo = df["low"].to_numpy(dtype=float)
    atrp_base = float(np.nanmean(t[b0:n]))
    atrp_dec = float(np.nanmean(t[d0:b0]))
    if not (atrp_base > 0 and atrp_dec > 0):
        return {"ok": False, "reason": "flat"}
    contraction = atrp_base / atrp_dec
    anchor = c[b0 - 1]                                   # close of the bar BEFORE the base
    drift_pct = (c[n - 1] / anchor - 1.0) * 100.0 if anchor > 0 else np.nan
    drift_atr = abs(drift_pct) / atrp_base
    expansion = float(np.nanmax(t[b0:n])) / atrp_dec     # the direct anti-knife term
    win_low = float(np.nanmin(lo[d0:n]))
    base_low = float(np.nanmin(lo[b0:n]))
    low_prox_atr = ((base_low / win_low) - 1.0) * 100.0 / atrp_base if win_low > 0 else np.nan
    h = int(base_len) // 2
    first_half = float(np.nanmean(t[b0:b0 + h]))
    half_step = float(np.nanmean(t[n - h:n])) / first_half if first_half > 0 else np.nan
    checks = {"contraction": contraction <= VC_CONTRACTION_MAX,
              "drift": drift_atr <= VC_DRIFT_MAX_ATR,
              "expansion": expansion <= VC_EXPANSION_MAX_X,
              "low_prox": low_prox_atr <= VC_LOW_PROX_ATR,
              "half_step": half_step <= VC_HALF_STEP_MAX}
    return {"ok": bool(all(checks.values())), "checks": checks,
            "reason": "settled" if all(checks.values())
                      else ",".join(k for k, v in checks.items() if not v),
            "contraction": contraction, "drift_pct": drift_pct, "drift_atr": drift_atr,
            "expansion": expansion, "low_prox_atr": low_prox_atr, "half_step": half_step,
            "atrp_base": atrp_base, "atrp_dec": atrp_dec}


# ─────────────────────────────────────────────────────────────────────────────
# DEFINITION 2 — "stationary_bottom" (a touched, time-tested shelf).
# Transcribed from studies/stationary_bottom_swing_study.py. UNKNOWN FAILS CLOSED.
# ─────────────────────────────────────────────────────────────────────────────
SHELF_WINDOW_BARS = 20        # K   sweep 10..40
SHELF_TOL_PCT = 3.0           # TOL sweep 1..5
MIN_LOWS_AT_SHELF = 4         # C   sweep 2..8
MIN_SHELF_SPAN_BARS = 8       # S   sweep 3..12
MIN_BARS_SINCE_NEW_LOW = 5    # B   sweep 2..13
MIN_BARS_SINCE_BREAK = 5      # F   sweep 0..10
MAX_ABOVE_SHELF_PCT = 8.0     # E   sweep 4..15
SHELF_ANCHOR = "band"         # "band" | "window_min" | "lower"


def shelf_based(df, band=None, window: int = SHELF_WINDOW_BARS,
                tol_pct: float = SHELF_TOL_PCT, anchor: str = SHELF_ANCHOR) -> dict:
    """DEFINITION 2. Stopped printing new lows AND spent real time flat at one
    level. Only the WINDOW/TOL/ANCHOR shape the metrics — B/C/S/F/E are applied
    by the caller so they can be swept without recomputing."""
    K = int(window)
    if df is None or len(df) < K or K < 3:
        return {"ok": False, "reason": "history"}
    w = df["low"].to_numpy(dtype=float)[-K:]
    last_close = float(df["close"].iloc[-1])
    if not np.isfinite(w).all() or not np.isfinite(last_close):
        return {"ok": False, "reason": "nan"}
    wmin = float(w.min())
    if wmin <= 0:
        return {"ok": False, "reason": "bad_price"}
    # B is ALWAYS measured on the window minimum, whatever the anchor: "it
    # stopped going down" is a statement about price, not about the band. LAST
    # occurrence of the min, so an equal re-test resets the clock.
    i_min = int(np.flatnonzero(w == wmin)[-1])
    bars_since_new_low = (K - 1) - i_min

    lo_b = hi_b = None
    if isinstance(band, dict):
        try:
            lo_b, hi_b = float(band["lo"]), float(band["hi"])
        except (TypeError, ValueError, KeyError):
            lo_b = hi_b = None
        if lo_b is None or hi_b is None or not (0 < lo_b <= hi_b):
            lo_b = hi_b = None
    if anchor == "band" and lo_b is not None:
        shelf_lo, shelf_hi, used = lo_b, hi_b, "band"
    elif anchor == "lower" and lo_b is not None:
        lvl = min(lo_b, wmin)
        shelf_lo = shelf_hi = lvl
        used = "lower"
    else:
        shelf_lo = shelf_hi = wmin
        used = "window_min"
    floor_ = shelf_lo * (1.0 - tol_pct / 100.0)
    top_ = shelf_hi * (1.0 + tol_pct / 100.0)
    at = np.flatnonzero((w >= floor_) & (w <= top_))
    lows_at_shelf = int(at.size)
    shelf_span = int(at[-1] - at[0] + 1) if at.size else 0
    broke = np.flatnonzero(w < floor_)
    bars_since_break = ((K - 1) - int(broke[-1])) if broke.size else K
    above_shelf_pct = (last_close / shelf_hi - 1.0) * 100.0
    fails = []
    if bars_since_new_low < MIN_BARS_SINCE_NEW_LOW:
        fails.append("new_low_%dd" % bars_since_new_low)
    if lows_at_shelf < MIN_LOWS_AT_SHELF:
        fails.append("touches_%d" % lows_at_shelf)
    if shelf_span < MIN_SHELF_SPAN_BARS:
        fails.append("span_%d" % shelf_span)
    if bars_since_break < MIN_BARS_SINCE_BREAK:
        fails.append("cut_under_%dd" % bars_since_break)
    if above_shelf_pct > MAX_ABOVE_SHELF_PCT:
        fails.append("above_%.1f%%" % above_shelf_pct)
    return {"ok": not fails, "reason": "based" if not fails else " + ".join(fails),
            "anchor": used, "shelf_lo": shelf_lo, "shelf_hi": shelf_hi, "window_min": wmin,
            "bars_since_new_low": bars_since_new_low, "lows_at_shelf": lows_at_shelf,
            "shelf_span": shelf_span, "bars_since_break": bars_since_break,
            "above_shelf_pct": above_shelf_pct}


# ─────────────────────────────────────────────────────────────────────────────
# DEFINITION 3 — "range_position" (closes stopped finishing on the floor, and
# the floor stopped migrating down). From
# studies/stationary_bottom_range_position_study.py. UNKNOWN FAILS CLOSED.
# ─────────────────────────────────────────────────────────────────────────────
RANGE_N = 10               # sweep 5,8,10,15,20
PERCH_K = 10               # sweep 5,10,15,20
ATR_LEN = 14               # sweep 10,14,20
RP_MEAN_MIN = 0.40
FLOOR_DRIFT_MAX_ATR = 1.5
LAST_BAR_MIN_RP = 0.20
MIN_BARS_SINCE_LOW = 1
BASE_MAX_WIDTH_ATR = 6.0


def rp_based(df, N: int = RANGE_N, K: int = PERCH_K, atr_len: int = ATR_LEN) -> dict:
    """DEFINITION 3. Rolling FIRST, dropna never (the hot_pullback off-by-49
    came from the other order). Only N/K/ATR_LEN shape the metrics; the five
    thresholds are applied by the caller so they can be swept."""
    need = max(2 * int(N) + 5, int(atr_len) + 1, int(K) + int(N))
    if df is None or len(df) < need:
        return {"ok": False, "reason": "history"}
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    c = df["close"].astype(float)
    RH = h.rolling(int(N), min_periods=int(N)).max()
    RL = l.rolling(int(N), min_periods=int(N)).min()
    rng = RH - RL
    rp = (c - RL) / rng.where(rng > 0)
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    atr = tr.rolling(int(atr_len), min_periods=int(atr_len)).mean()
    tail = rp.iloc[-int(K):]
    if tail.isna().any() or not np.isfinite(atr.iloc[-1]) or float(atr.iloc[-1]) <= 0:
        return {"ok": False, "reason": "history"}
    a = float(atr.iloc[-1])
    rp_mean = float(tail.mean())
    rl_now = float(RL.iloc[-1])
    rl_prior = float(RL.iloc[-1 - int(N)])              # adjacent, disjoint prior window
    if not np.isfinite(rl_prior):
        return {"ok": False, "reason": "history"}
    drift_atr = (rl_now - rl_prior) / a
    width_atr = (float(RH.iloc[-1]) - rl_now) / a
    last_rp = float(rp.iloc[-1])
    w2 = l.iloc[-2 * int(N):].to_numpy(dtype=float)
    since_low = (len(w2) - 1) - int(np.argmin(w2))
    fails = []
    if rp_mean < RP_MEAN_MIN:
        fails.append("perch")
    if drift_atr < -FLOOR_DRIFT_MAX_ATR:
        fails.append("floor")
    if last_rp < LAST_BAR_MIN_RP:
        fails.append("last")
    if since_low < MIN_BARS_SINCE_LOW:
        fails.append("newlow")
    if width_atr > BASE_MAX_WIDTH_ATR:
        fails.append("width")
    return {"ok": not fails, "reason": "PASS" if not fails else ",".join(fails),
            "rp_mean": rp_mean, "last_rp": last_rp, "floor_drift_atr": drift_atr,
            "bars_since_low": since_low, "width_atr": width_atr}


# window-length variants recomputed per event (thresholds stay at default)
VC_WIN_GRID = ([("vc_base%d" % b, {"base_len": b}) for b in (5, 8, 12, 15, 20)]
               + [("vc_dec%d" % d, {"dec_len": d}) for d in (10, 15, 30, 40)])
SHELF_WIN_GRID = ([("shelf_K%d" % k, {"window": k}) for k in (10, 15, 25, 30, 40)]
                  + [("shelf_tol%g" % t, {"tol_pct": t}) for t in (1.0, 1.5, 2.0, 4.0, 5.0)]
                  + [("shelf_anchor_%s" % a, {"anchor": a}) for a in ("window_min", "lower")])
RP_WIN_GRID = ([("rp_N%d" % n, {"N": n}) for n in (5, 8, 15, 20)]
               + [("rp_K%d" % k, {"K": k}) for k in (5, 15, 20)]
               + [("rp_atr%d" % a, {"atr_len": a}) for a in (10, 20)])


# ─────────────────────────────────────────────────────────────────────────────
# the replay
# ─────────────────────────────────────────────────────────────────────────────
def _frame(coll, sym) -> Optional[pd.DataFrame]:
    doc = coll.find_one({"symbol": sym}, {"bars": 1, "_id": 0})
    f = pd.DataFrame((doc or {}).get("bars") or [])
    if f.empty or "close" not in f or "date" not in f:
        return None
    for c in ("open", "high", "low", "close", "volume"):
        if c not in f:
            f[c] = np.nan
        f[c] = pd.to_numeric(f[c], errors="coerce")
    f["d"] = f["date"].astype(str).str[:10]
    f = f.dropna(subset=["open", "high", "low", "close"]).sort_values("d")
    return f.drop_duplicates(subset=["d"], keep="last").reset_index(drop=True)


def _knife(sub: pd.DataFrame) -> Optional[bool]:
    """The live guard on the SAME closed bars: swing lows stepping down AND a
    falling 50-bar mean (demand_reentry windows: swing 5, ma50 vs 10 bars prior)."""
    if sub is None or len(sub) < 60:
        return None
    closes, lows = sub["close"], sub["low"]
    st = SL.structure_read(closes.tolist(), lows.tolist(),
                           swing_window=STRUCTURE_SWING_WINDOW)
    ma = closes.rolling(50).mean()
    now = float(ma.iloc[-1]) if pd.notna(ma.iloc[-1]) else None
    prior = (float(ma.iloc[-(MA_SLOPE_LOOKBACK + 1)])
             if len(ma) > MA_SLOPE_LOOKBACK and pd.notna(ma.iloc[-(MA_SLOPE_LOOKBACK + 1)])
             else None)
    return bool(SL.is_falling_knife(st, float(closes.iloc[-1]), now, prior))


def _mood(sub: pd.DataFrame) -> float:
    """Mood on bars strictly before the event bar. `closed_only=False` because
    every bar in `sub` has already closed — see LIMITATIONS."""
    try:
        m = MD.mood(sub, closed_only=False)
        if m.get("label") == "unavailable":
            return np.nan
        return float(m.get("score"))
    except Exception:                                   # noqa: BLE001
        return np.nan


def events(hold: int = HOLD_SESSIONS, floor: int = MIN_HISTORY_BARS,
           limit_names: int = 0, min_dvol: float = 0.0,
           uni: str = "full") -> pd.DataFrame:
    """Every (symbol, bar) where price reached a demand band and the two
    STANDING gates passed, with its simulated trade and every gate's reading."""
    coll = prices._get_mongo()
    geom = demand_reentry.zone_geom()
    syms = universe.load_universe(uni)
    if limit_names:
        syms = syms[:limit_names]
    rows = []
    for i, sym in enumerate(syms):
        if i % 200 == 0:
            print("  %d/%d  events=%d" % (i, len(syms), len(rows)), file=sys.stderr, flush=True)
        f = _frame(coll, sym)
        if f is None or len(f) < floor + hold + 2:
            continue
        c = f["close"].to_numpy(dtype=float)
        hi = f["high"].to_numpy(dtype=float)
        lo = f["low"].to_numpy(dtype=float)
        vol = f["volume"].to_numpy(dtype=float)
        dvol = pd.Series(c * vol).rolling(50, min_periods=50).median().to_numpy()
        max_clock = max(max(CLOCKS), hold)
        last = len(f) - max_clock - 1
        for j in range(floor, last + 1):
            if min_dvol and not (dvol[j - 1] >= min_dvol):
                continue
            px, prev, day_low = float(c[j]), float(c[j - 1]), float(lo[j])
            z = price_zones.compute(f.iloc[max(0, j - 252):j], last_price=px,
                                    max_zones=None, **geom)
            if not z:
                continue
            bands = (z.get("supply_zones") or []) + (z.get("demand_zones") or [])
            hits = []
            for b in (z.get("demand_zones") or []):
                if not AG.demand_proximity_gate(px, b):
                    continue
                ap = AG.approach_read(px, b, prev, day_low)
                if not isinstance(ap, dict):
                    continue
                hits.append((float(b["lo"]), b, ap))
            if not hits:
                continue
            # the band a human would call "the one it bounced at": the nearest
            # support UNDER the print, which is also the stop plan_txt names.
            band_lo, band, ap = max(hits, key=lambda t: t[0])
            ok_room, room = AG.room_gate(px, bands, prev)
            if not ok_room:
                continue
            stop = float(band["lo"]) * (1.0 - AG.STOP_BUFFER_PCT / 100.0)
            if px <= stop:
                continue
            target = float(room["target"]) if room else None
            # ONE forward pass to the longest clock; each clock then reads the
            # same first-touch. Stop is checked BEFORE target inside a bar.
            hit_k = hit_px = hit_why = None
            for k in range(1, max_clock + 1):
                t = j + k
                if lo[t] <= stop:
                    hit_k, hit_px, hit_why = k, stop, "stop"
                    break
                if target is not None and hi[t] >= target:
                    hit_k, hit_px, hit_why = k, target, "target"
                    break
            clocks = {}
            for cl in sorted(set(CLOCKS) | {hold}):
                if hit_k is not None and hit_k <= cl:
                    ex, wy = hit_px, hit_why
                else:
                    ex, wy = float(c[j + cl]), "clock"
                clocks["R%d" % cl] = (ex - px) / (px - stop)
                clocks["pct%d" % cl] = (ex / px - 1.0) * 100.0
                clocks["why%d" % cl] = wy
            exit_px, why = (clocks["pct%d" % hold] / 100.0 + 1.0) * px, clocks["why%d" % hold]

            sub_all = f.iloc[:j]                        # CLOSED bars, strictly before j
            tail = f.iloc[max(0, j - DEF_TAIL_BARS):j]
            v = vc_settled(tail)
            s = shelf_based(tail, band)
            r = rp_based(tail)
            row = {
                "symbol": sym, "date": f["d"].iloc[j], "dir": ap.get("dir"),
                "n_bands": len(hits), "entry": px, "stop": stop,
                "target": target, "room_pct": (room or {}).get("room_pct_raw"),
                "clear": room is None,
                "risk_pct": (px - stop) / px * 100.0,
                "trade_pct": (exit_px / px - 1.0) * 100.0,
                "R": (exit_px - px) / (px - stop),
                "why": why, **clocks,
                "knife": _knife(sub_all), "mood": _mood(sub_all),
                "vc_ok": bool(v.get("ok")), "shelf_ok": bool(s.get("ok")),
                "rp_ok": bool(r.get("ok")),
            }
            # A metric the definition could not compute stays NaN, and _pass()
            # fails closed on NaN — never 0, which would read as a pass.
            for k in ("contraction", "drift_atr", "expansion", "low_prox_atr", "half_step"):
                row["vc_" + k] = float(v[k]) if v.get(k) is not None else np.nan
            for k in ("bars_since_new_low", "lows_at_shelf", "shelf_span",
                      "bars_since_break", "above_shelf_pct"):
                row["sh_" + k] = float(s[k]) if s.get(k) is not None else np.nan
            for k in ("rp_mean", "last_rp", "floor_drift_atr", "bars_since_low", "width_atr"):
                row["rp_" + k] = float(r[k]) if r.get(k) is not None else np.nan
            # window-length variants (thresholds at default), so the sweep needs
            # no second replay pass
            for lab, kw in VC_WIN_GRID:
                row[lab] = bool(vc_settled(tail, **kw).get("ok"))
            for lab, kw in SHELF_WIN_GRID:
                row[lab] = bool(shelf_based(tail, band, **kw).get("ok"))
            for lab, kw in RP_WIN_GRID:
                row[lab] = bool(rp_based(tail, **kw).get("ok"))
            rows.append(row)
    E = pd.DataFrame(rows)
    if not E.empty:
        E = E.drop_duplicates(subset=["symbol", "date"]).reset_index(drop=True)
    return E


# ─────────────────────────────────────────────────────────────────────────────
# statistics
# ─────────────────────────────────────────────────────────────────────────────
def _subset_sums(pool: np.ndarray, n: int, draws: int, seed: int) -> np.ndarray:
    """Sums of `draws` random size-n subsets drawn WITHOUT replacement. Chunked
    so a 40k-event pool does not need a draws x N matrix. Same construction as
    hot_pullback_study._perm_p (shuffle the pool, take the first n), only
    vectorised — that loop is O(draws*N) in Python and this cohort is 100x its."""
    rng = np.random.default_rng(seed)
    N = len(pool)
    out = np.empty(draws)
    chunk = max(1, int(4_000_000 // max(N, 1)))
    done = 0
    while done < draws:
        m = min(chunk, draws - done)
        mat = np.tile(pool, (m, 1))
        rng.permuted(mat, axis=1, out=mat)
        out[done:done + m] = mat[:, :n].sum(axis=1)
        done += m
    return out


def _perm_p(a: np.ndarray, b: np.ndarray, draws: int = PERM_DRAWS) -> float:
    """One-sided permutation p for mean(a) - mean(b), labels shuffled."""
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    obs = a.mean() - b.mean()
    pool = np.concatenate([a, b])
    N, n = len(pool), len(a)
    total = pool.sum()
    sa = _subset_sums(pool, n, draws, 11)
    diff = sa / n - (total - sa) / (N - n)
    return float((diff >= obs).mean())


def _by_date(D: pd.DataFrame, dates: np.ndarray, col: str = "R"):
    """(sums, counts) per date — lets a date-clustered bootstrap be vectorised."""
    g = D.groupby("date")[col].agg(["sum", "count"])
    g = g.reindex(dates).fillna(0.0)
    return g["sum"].to_numpy(dtype=float), g["count"].to_numpy(dtype=float)


def _boot_delta(base: pd.DataFrame, kept: pd.DataFrame, draws: int = BOOT_DRAWS) -> tuple:
    """95% CI on mean R(kept) - mean R(baseline), resampling DATES (the events
    cluster on market-wide flush days) and using the SAME resample for both
    cohorts, because kept is a subset of baseline."""
    dates = np.array(sorted(base["date"].unique()))
    if len(dates) < 3 or kept.empty:
        return (float("nan"), float("nan"), float("nan"))
    bs, bc = _by_date(base, dates)
    ks, kc = _by_date(kept, dates)
    rng = np.random.default_rng(7)
    idx = rng.integers(0, len(dates), size=(draws, len(dates)))
    bn, bd = bs[idx].sum(1), bc[idx].sum(1)
    kn, kd = ks[idx].sum(1), kc[idx].sum(1)
    ok = (bd > 0) & (kd > 0)
    d = kn[ok] / kd[ok] - bn[ok] / bd[ok]
    if d.size < 100:
        return (float("nan"), float("nan"), float("nan"))
    return (float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5)),
            float((d <= 0).mean()))


def _placebo(base_R: np.ndarray, n_keep: int, draws: int = PLACEBO_DRAWS) -> tuple:
    """Size-matched random keep: what dropping to n_keep events AT RANDOM pays.
    Returns the 5th and 95th percentile expectancy of those random subsets."""
    if n_keep <= 0 or n_keep >= len(base_R):
        return (float("nan"), float("nan"))
    out = _subset_sums(base_R, n_keep, draws, 3) / n_keep
    return float(np.percentile(out, 5)), float(np.percentile(out, 95))


def _stats(D: pd.DataFrame) -> dict:
    R, T = D["R"].to_numpy(dtype=float), D["trade_pct"].to_numpy(dtype=float)
    mix = D["why"].value_counts().to_dict()
    return {"n": len(D), "exp": R.mean(), "win": (R > 0).mean() * 100.0,
            "mean": T.mean(), "med": float(np.median(T)),
            "tgt": 100.0 * mix.get("target", 0) / max(1, len(D)),
            "stp": 100.0 * mix.get("stop", 0) / max(1, len(D)),
            "clk": 100.0 * mix.get("clock", 0) / max(1, len(D))}


def _line(tag: str, s: dict) -> str:
    return ("  %-30s n=%-5d  %+0.3fR  win %4.1f%%  mean %+5.2f%%  med %+5.2f%%  "
            "tgt/stop/clock %2.0f/%2.0f/%2.0f" %
            (tag, s["n"], s["exp"], s["win"], s["mean"], s["med"], s["tgt"], s["stp"], s["clk"]))


def gate_report(base: pd.DataFrame, name: str, keep: pd.Series, perm: int) -> None:
    """n kept / dropped, expectancy before and after, the delta, a date-clustered
    95% CI on it, a permutation p vs the excluded cohort, and the size-matched
    random-keep placebo band."""
    keep = keep.fillna(False).astype(bool)
    K, X = base[keep], base[~keep]
    b = _stats(base)
    if len(K) < 10:
        print("  %-30s kept n=%-5d  TOO SMALL TO MEASURE" % (name, len(K)))
        return
    k = _stats(K)
    delta = k["exp"] - b["exp"]
    lo_ci, hi_ci, p_le0 = _boot_delta(base, K)
    p_perm = (_perm_p(K["R"].to_numpy(dtype=float), X["R"].to_numpy(dtype=float), perm)
              if len(X) >= 10 else float("nan"))
    p5, p95 = _placebo(base["R"].to_numpy(dtype=float), len(K))
    print("  %-30s keep %5d (%4.1f%%)  drop %5d   %+0.3fR -> %+0.3fR   Δ %+0.3fR   "
          "CI[%+0.3f,%+0.3f] P(Δ<=0)=%.3f  perm p=%s  placebo[%+0.3f,%+0.3f]%s"
          % (name, len(K), 100.0 * len(K) / len(base), len(X), b["exp"], k["exp"], delta,
             lo_ci, hi_ci, p_le0,
             ("%.3f" % p_perm) if p_perm == p_perm else " n/a",
             p5, p95,
             "  *outside placebo*" if (p5 == p5 and (k["exp"] > p95 or k["exp"] < p5)) else ""))


def _pass(col: pd.Series, thr: float, op: str) -> pd.Series:
    """NaN (the metric could not be computed) FAILS CLOSED — the same side
    direction_gate fails on."""
    v = pd.to_numeric(col, errors="coerce")
    m = (v <= thr) if op == "le" else (v >= thr)
    return m.fillna(False)


def vc_mask(E, contraction=VC_CONTRACTION_MAX, drift=VC_DRIFT_MAX_ATR,
            expansion=VC_EXPANSION_MAX_X, low_prox=VC_LOW_PROX_ATR,
            half=VC_HALF_STEP_MAX) -> pd.Series:
    return (_pass(E.vc_contraction, contraction, "le") & _pass(E.vc_drift_atr, drift, "le")
            & _pass(E.vc_expansion, expansion, "le") & _pass(E.vc_low_prox_atr, low_prox, "le")
            & (_pass(E.vc_half_step, half, "le") if np.isfinite(half)
               else E.vc_half_step.notna()))


def shelf_mask(E, C=MIN_LOWS_AT_SHELF, S=MIN_SHELF_SPAN_BARS, B=MIN_BARS_SINCE_NEW_LOW,
               F=MIN_BARS_SINCE_BREAK, Ec=MAX_ABOVE_SHELF_PCT) -> pd.Series:
    return (_pass(E.sh_bars_since_new_low, B, "ge") & _pass(E.sh_lows_at_shelf, C, "ge")
            & _pass(E.sh_shelf_span, S, "ge") & _pass(E.sh_bars_since_break, F, "ge")
            & _pass(E.sh_above_shelf_pct, Ec, "le"))


def rp_mask(E, perch=RP_MEAN_MIN, drift=FLOOR_DRIFT_MAX_ATR, last=LAST_BAR_MIN_RP,
            since=MIN_BARS_SINCE_LOW, width=BASE_MAX_WIDTH_ATR) -> pd.Series:
    return (_pass(E.rp_rp_mean, perch, "ge") & _pass(E.rp_floor_drift_atr, -drift, "ge")
            & _pass(E.rp_last_rp, last, "ge") & _pass(E.rp_bars_since_low, since, "ge")
            & _pass(E.rp_width_atr, width, "le"))


def mech_line(tag: str, s: pd.DataFrame) -> None:
    """WHY a gate moves expectancy: it can only do it by changing how OFTEN the
    trade works, or by changing how BIG it is when it does. Room is the distance
    to the target the push names, risk the distance to the stop it names, so
    room/risk is the R the setup is even capable of paying."""
    if len(s) < 50:
        return
    w = s["R"] > 0
    room, risk = s["room_pct"].mean(skipna=True), s["risk_pct"].mean()
    print("    %-18s n=%-6d %+0.3fR  win %4.1f%%   room %5.2f%%  risk %4.2f%%  room/risk %4.2f  "
          "avg win %+0.2fR  avg loss %+0.2fR  clear %4.1f%%  tgt/stop/clk %2.0f/%2.0f/%2.0f"
          % (tag, len(s), s["R"].mean(), 100.0 * w.mean(), room, risk, room / risk,
             s["R"][w].mean(), s["R"][~w].mean(), 100.0 * s["clear"].mean(),
             100.0 * (s["why"] == "target").mean(), 100.0 * (s["why"] == "stop").mean(),
             100.0 * (s["why"] == "clock").mean()))


def _dedupe(D: pd.DataFrame, tag: str) -> None:
    """Clustering check: the same expectancy with one event per date, and with
    one per symbol. A headline that only survives the raw table is one name or
    one flush day wearing a sample size."""
    if D.empty:
        return
    d1 = D.sort_values(["date", "symbol"]).groupby("date").first()
    s1 = D.sort_values(["date", "symbol"]).groupby("symbol").first()
    print("    %-16s raw %+0.3fR n=%d | one per DATE %+0.3fR n=%d | one per SYMBOL %+0.3fR n=%d"
          " | busiest name %d events, busiest day %d"
          % (tag, D.R.mean(), len(D), d1.R.mean(), len(d1), s1.R.mean(), len(s1),
             D.symbol.value_counts().max(), D.date.value_counts().max()))


def sweep_line(base: pd.DataFrame, tag: str, keep: pd.Series) -> None:
    keep = keep.fillna(False).astype(bool)
    K = base[keep]
    if len(K) < 10:
        print("    %-22s n=%-5d  (too small)" % (tag, len(K)))
        return
    s = _stats(K)
    print("    %-22s n=%-5d keep %4.1f%%   %+0.3fR  win %4.1f%%   Δ %+0.3fR"
          % (tag, s["n"], 100.0 * len(K) / len(base), s["exp"], s["win"],
             s["exp"] - base["R"].mean()))


# ─────────────────────────────────────────────────────────────────────────────
# report
# ─────────────────────────────────────────────────────────────────────────────
def report(E: pd.DataFrame, hold: int, floor: int, perm: int, do_sweep: bool) -> None:
    if E.empty:
        print("no events")
        return
    B = E[E["dir"] == "bouncing"].reset_index(drop=True)
    print()
    print("=" * 118)
    print("COHORT  demand band reached, room >= %g%% to the first proven lid, print <= %g%% "
          "above the band top" % (AG.ALERT_MIN_ROOM_PCT, AG.ALERT_MAX_ABOVE_DEMAND_PCT))
    print("        floor=bar %d   clock=%d sessions (event window bounded by the longest clock, "
          "%d)   entry=close of the event bar   stop=band floor -%g%%"
          % (floor, hold, max(max(CLOCKS), hold), AG.STOP_BUFFER_PCT))
    print("        all events n=%d   names=%d   %s -> %s"
          % (len(E), E.symbol.nunique(), E.date.min(), E.date.max()))
    print("=" * 118)
    print()
    print("DIRECTION SPLIT (the shipped gate keeps `bouncing` only) — the control cohort:")
    for d, g in sorted(E.groupby("dir"), key=lambda kv: -len(kv[1])):
        print(_line("%s%s" % (d, "  <= BASELINE" if d == "bouncing" else ""), _stats(g)))
    if len(B) < 30:
        print("\nbouncing cohort too small (n=%d) to gate. Widen --names or lower --floor." % len(B))
        return
    nb = E[E["dir"] != "bouncing"]
    if len(nb) >= 10:
        print("  direction gate itself: bouncing %+0.3fR vs everything else %+0.3fR  "
              "(Δ %+0.3fR, perm p=%.3f)"
              % (B.R.mean(), nb.R.mean(), B.R.mean() - nb.R.mean(),
                 _perm_p(B.R.to_numpy(dtype=float), nb.R.to_numpy(dtype=float), perm)))
    print()
    print("BASELINE (what the phone sends TODAY):")
    print(_line("bouncing", _stats(B)))
    print("    median risk %.1f%%   clear-runway (no target) %.1f%%   mood known %.1f%%   "
          "knife known %.1f%%"
          % (B.risk_pct.median(), 100.0 * B.clear.mean(),
             100.0 * B.mood.notna().mean(), 100.0 * B.knife.notna().mean()))
    # Events repeat: one name can ring on many sessions and one flush day can
    # ring many names. Neither dedupe is the headline — both are the check that
    # the headline is not one name or one day.
    _dedupe(B, "baseline")
    print("    PLACEBO for every line below = the same cohort with n_kept events dropped at "
          "RANDOM (5-95th pct band).")
    print()
    print("GATES, one at a time (each is a TIGHTENING of the baseline):")
    gate_report(B, "not falling knife", B.knife.eq(False), perm)
    for t in MOOD_SWEEP:
        gate_report(B, "mood >= %g" % t, _pass(B.mood, t, "ge"), perm)
    gate_report(B, "DEF1 vc range_settled", vc_mask(B), perm)
    gate_report(B, "DEF2 shelf stationary", shelf_mask(B), perm)
    gate_report(B, "DEF3 range_position", rp_mask(B), perm)
    print()
    print("STACKS (Ajay's ask = bouncing + not-knife + bullish mood + stationary bottom):")
    nk = B.knife.eq(False)
    for t in (10.0, 25.0):
        gate_report(B, "not-knife + mood>=%g" % t, nk & _pass(B.mood, t, "ge"), perm)
    for lab, m in (("DEF1", vc_mask(B)), ("DEF2", shelf_mask(B)), ("DEF3", rp_mask(B))):
        gate_report(B, "not-knife + mood>=25 + %s" % lab,
                    nk & _pass(B.mood, 25.0, "ge") & m, perm)
    gate_report(B, "not-knife + mood>=25 + ANY def",
                nk & _pass(B.mood, 25.0, "ge") & (vc_mask(B) | shelf_mask(B) | rp_mask(B)), perm)
    gate_report(B, "not-knife + mood>=25 + ALL defs",
                nk & _pass(B.mood, 25.0, "ge") & vc_mask(B) & shelf_mask(B) & rp_mask(B), perm)

    print()
    print("CLUSTERING CHECK (same cohorts, one event per date and one per symbol):")
    for tag, m in (("not-knife", nk),
                   ("mood>=25", _pass(B.mood, 25.0, "ge")),
                   ("nk+mood>=10", nk & _pass(B.mood, 10.0, "ge")),
                   ("nk+mood>=25", nk & _pass(B.mood, 25.0, "ge")),
                   ("nk+mood25+DEF1", nk & _pass(B.mood, 25.0, "ge") & vc_mask(B)),
                   ("nk+mood25+DEF2", nk & _pass(B.mood, 25.0, "ge") & shelf_mask(B)),
                   ("nk+mood25+DEF3", nk & _pass(B.mood, 25.0, "ge") & rp_mask(B))):
        sub = B[m.fillna(False).astype(bool)]
        if len(sub) >= 10:
            _dedupe(sub, tag)

    print()
    print("MECHANISM — a gate can only pay by raising the HIT RATE or the SIZE of the hit:")
    mech_line("all bouncing", B)
    for lo_m, hi_m in ((-100, -25), (-25, -10), (-10, 10), (10, 25), (25, 40), (40, 101)):
        mech_line("mood %d..%d" % (lo_m, hi_m),
                  B[(B.mood >= lo_m) & (B.mood < hi_m)])
    mech_line("falling knife", B[B.knife.eq(True)])
    mech_line("not falling knife", B[nk])
    mech_line("DEF1 vc settled", B[vc_mask(B)])
    mech_line("DEF2 shelf based", B[shelf_mask(B)])
    mech_line("DEF3 rp based", B[rp_mask(B)])

    cols = [c for c in ("R%d" % cl for cl in sorted(set(CLOCKS) | {hold})) if c in B]
    if cols:
        print()
        print("CLOCK ROBUSTNESS (the SAME events, read at each horizon — mean R):")
        stacks = [("baseline", pd.Series(True, index=B.index)),
                  ("not-knife", nk),
                  ("nk+mood>=25", nk & _pass(B.mood, 25.0, "ge")),
                  ("nk+mood25+DEF1", nk & _pass(B.mood, 25.0, "ge") & vc_mask(B)),
                  ("nk+mood25+DEF2", nk & _pass(B.mood, 25.0, "ge") & shelf_mask(B)),
                  ("nk+mood25+DEF3", nk & _pass(B.mood, 25.0, "ge") & rp_mask(B))]
        print("    %-18s %6s  %s" % ("cohort", "n", "  ".join("%8s" % c for c in cols)))
        for tag, m in stacks:
            sub = B[m.fillna(False).astype(bool)]
            if len(sub) < 10:
                continue
            print("    %-18s %6d  %s" % (tag, len(sub),
                                         "  ".join("%+8.3f" % sub[c].mean() for c in cols)))

    print()
    print("MARGINAL KEEP RATE of each single check (how selective each clause is alone):")
    singles = [
        ("vc contraction<=%g" % VC_CONTRACTION_MAX, _pass(B.vc_contraction, VC_CONTRACTION_MAX, "le")),
        ("vc drift<=%g ATR" % VC_DRIFT_MAX_ATR, _pass(B.vc_drift_atr, VC_DRIFT_MAX_ATR, "le")),
        ("vc expansion<=%g" % VC_EXPANSION_MAX_X, _pass(B.vc_expansion, VC_EXPANSION_MAX_X, "le")),
        ("vc low_prox<=%g" % VC_LOW_PROX_ATR, _pass(B.vc_low_prox_atr, VC_LOW_PROX_ATR, "le")),
        ("vc half_step<=%g" % VC_HALF_STEP_MAX, _pass(B.vc_half_step, VC_HALF_STEP_MAX, "le")),
        ("sh new-low>=%dd" % MIN_BARS_SINCE_NEW_LOW, _pass(B.sh_bars_since_new_low, MIN_BARS_SINCE_NEW_LOW, "ge")),
        ("sh touches>=%d" % MIN_LOWS_AT_SHELF, _pass(B.sh_lows_at_shelf, MIN_LOWS_AT_SHELF, "ge")),
        ("sh span>=%d" % MIN_SHELF_SPAN_BARS, _pass(B.sh_shelf_span, MIN_SHELF_SPAN_BARS, "ge")),
        ("sh no-cut>=%dd" % MIN_BARS_SINCE_BREAK, _pass(B.sh_bars_since_break, MIN_BARS_SINCE_BREAK, "ge")),
        ("sh above<=%g%%" % MAX_ABOVE_SHELF_PCT, _pass(B.sh_above_shelf_pct, MAX_ABOVE_SHELF_PCT, "le")),
        ("rp perch>=%g" % RP_MEAN_MIN, _pass(B.rp_rp_mean, RP_MEAN_MIN, "ge")),
        ("rp floor>=-%g ATR" % FLOOR_DRIFT_MAX_ATR, _pass(B.rp_floor_drift_atr, -FLOOR_DRIFT_MAX_ATR, "ge")),
        ("rp last>=%g" % LAST_BAR_MIN_RP, _pass(B.rp_last_rp, LAST_BAR_MIN_RP, "ge")),
        ("rp since_low>=%d" % MIN_BARS_SINCE_LOW, _pass(B.rp_bars_since_low, MIN_BARS_SINCE_LOW, "ge")),
        ("rp width<=%g ATR" % BASE_MAX_WIDTH_ATR, _pass(B.rp_width_atr, BASE_MAX_WIDTH_ATR, "le")),
    ]
    for tag, m in singles:
        sweep_line(B, tag, m)

    if do_sweep:
        print()
        print("CONSTANT SWEEPS — one constant moved, the rest at default. Δ is vs the baseline.")
        print("  DEF1 vc:")
        for x in np.arange(0.50, 1.001, 0.05):
            sweep_line(B, "contraction<=%.2f" % x, vc_mask(B, contraction=x))
        for x in np.arange(0.5, 2.001, 0.25):
            sweep_line(B, "drift<=%.2f ATR" % x, vc_mask(B, drift=x))
        for x in np.arange(0.8, 1.501, 0.1):
            sweep_line(B, "expansion<=%.1f" % x, vc_mask(B, expansion=x))
        for x in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
            sweep_line(B, "low_prox<=%.1f" % x, vc_mask(B, low_prox=x))
        for x in (1.00, 1.10, 1.25, 1.50, float("inf")):
            sweep_line(B, "half_step<=%g" % x, vc_mask(B, half=x))
        print("  DEF2 shelf:")
        for x in (2, 3, 4, 5, 6, 8):
            sweep_line(B, "touches>=%d" % x, shelf_mask(B, C=x))
        for x in (3, 5, 8, 10, 12):
            sweep_line(B, "span>=%d" % x, shelf_mask(B, S=x))
        for x in (2, 3, 5, 8, 10, 13):
            sweep_line(B, "new_low>=%dd" % x, shelf_mask(B, B=x))
        for x in (0, 3, 5, 8, 10):
            sweep_line(B, "no_cut>=%dd" % x, shelf_mask(B, F=x))
        for x in (4.0, 6.0, 8.0, 10.0, 15.0):
            sweep_line(B, "above<=%g%%" % x, shelf_mask(B, Ec=x))
        print("  DEF3 rp:")
        for x in (0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55):
            sweep_line(B, "perch>=%.2f" % x, rp_mask(B, perch=x))
        for x in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
            sweep_line(B, "floor>=-%.1f ATR" % x, rp_mask(B, drift=x))
        for x in (0.0, 0.10, 0.20, 0.30, 0.40, 0.50):
            sweep_line(B, "last_rp>=%.2f" % x, rp_mask(B, last=x))
        for x in (0, 1, 2, 3, 5):
            sweep_line(B, "since_low>=%d" % x, rp_mask(B, since=x))
        for x in (4.0, 5.0, 6.0, 8.0, 99.0):
            sweep_line(B, "width<=%g ATR" % x, rp_mask(B, width=x))
        print("  WINDOW LENGTHS (recomputed at replay time; thresholds at default):")
        for lab, _ in VC_WIN_GRID + SHELF_WIN_GRID + RP_WIN_GRID:
            if lab in B:
                sweep_line(B, lab, B[lab])


# ─────────────────────────────────────────────────────────────────────────────
# the acceptance test
# ─────────────────────────────────────────────────────────────────────────────
CASY_BAND = {"lo": 627.49, "hi": 651.00, "kind": "demand", "touches": 2}   # the 08:13 ET push
CASY_DATE = "2026-09-09"


def upto(df, date_str: str):
    """Bars STRICTLY BEFORE `date_str` — what the phone could legally see."""
    if df is None:
        return None
    return df[df.index.astype(str).str[:10] < date_str]


def named_check(symbol: str = "CASY", date_str: str = CASY_DATE,
                band: Optional[dict] = None) -> bool:
    """What every gate says about one name on one date. Executed, not asserted."""
    band = band or (CASY_BAND if symbol == "CASY" else None)
    df = prices.load_prices(symbol)
    sub = upto(df, date_str)
    print()
    print("=" * 118)
    print("ACCEPTANCE TEST — %s on %s   (bars strictly before the date; the alert fired "
          "pre-open)" % (symbol, date_str))
    if sub is None or sub.empty:
        print("  no bars")
        return False
    print("  last CLOSED bar %s  close %.2f   band %s" % (str(sub.index[-1])[:10],
                                                          float(sub.close.iloc[-1]), band))
    try:
        row = df.loc[df.index.astype(str).str[:10] == date_str]
        px = float(row["open"].iloc[0])
        prev = float(sub["close"].iloc[-1])
        # day_low at alert time is the print itself: at 08:13 ET no lower price
        # had traded. Using the eventual session low would be lookahead.
        ap = AG.approach_read(px, band, prev, px)
        print("  print (the day's open, the pre-open alert's best proxy) %.2f   prev close %.2f"
              % (px, prev))
        print("  GATE direction   %-8s %s" % (
            "BLOCK" if not AG.direction_gate(ap) else "pass",
            (ap or {}).get("text") or "unreadable"))
    except Exception as exc:                            # noqa: BLE001
        print("  GATE direction   n/a (%s)" % exc)
    kn = _knife(sub)
    print("  GATE knife       %-8s is_falling_knife=%s  (%s)" % (
        "BLOCK" if kn else "pass", kn,
        SL.structure_read(sub["close"].tolist(), sub["low"].tolist(),
                          swing_window=STRUCTURE_SWING_WINDOW).get("trend")))
    md = _mood(sub)
    print("  GATE mood>=25    %-8s score %.1f" % ("BLOCK" if not (md >= 25.0) else "pass", md))
    tail = sub.iloc[-DEF_TAIL_BARS:]
    v = vc_settled(tail)
    print("  GATE DEF1 vc     %-8s settled=%s  contraction %.3f  drift %.3f ATR  expansion %.3f  "
          "low_prox %.3f  half %.3f  [%s]"
          % ("BLOCK" if not v.get("ok") else "pass", v.get("ok"),
             v.get("contraction", float("nan")), v.get("drift_atr", float("nan")),
             v.get("expansion", float("nan")), v.get("low_prox_atr", float("nan")),
             v.get("half_step", float("nan")), v.get("reason")))
    for a in ("band", "window_min", "lower"):
        s = shelf_based(tail, band, anchor=a)
        print("  GATE DEF2 shelf  %-8s ok=%-5s anchor=%-10s B=%s C=%s S=%s F=%s E=%+.2f%%  [%s]"
              % ("BLOCK" if not s.get("ok") else "pass", s.get("ok"), a,
                 s.get("bars_since_new_low"), s.get("lows_at_shelf"), s.get("shelf_span"),
                 s.get("bars_since_break"), s.get("above_shelf_pct", float("nan")),
                 s.get("reason")))
    r = rp_based(tail)
    print("  GATE DEF3 rp     %-8s ok=%-5s perch %.3f  last %.3f  floor_drift %+.2f ATR  "
          "since_low %s  width %.2f ATR  [%s]"
          % ("BLOCK" if not r.get("ok") else "pass", r.get("ok"),
             r.get("rp_mean", float("nan")), r.get("last_rp", float("nan")),
             r.get("floor_drift_atr", float("nan")), r.get("bars_since_low"),
             r.get("width_atr", float("nan")), r.get("reason")))
    blocked = bool(kn) or not (md >= 25.0) or not v.get("ok") or not r.get("ok") \
        or not shelf_based(tail, band).get("ok")
    print("  VERDICT: %s" % ("BLOCKED — the push would not have been sent." if blocked
                             else "PASSES every gate (the acceptance test FAILS)."))
    print("=" * 118)
    return blocked


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hold", type=int, default=HOLD_SESSIONS,
                    help="clock in sessions (60 = zone_backtest.MAX_HOLD_BARS)")
    ap.add_argument("--floor", type=int, default=MIN_HISTORY_BARS,
                    help="bars of history required before an event counts")
    ap.add_argument("--names", type=int, default=0, help="cap the universe (smoke runs)")
    ap.add_argument("--universe", default="full")
    ap.add_argument("--min-dvol", type=float, default=0.0,
                    help="median 50d dollar-volume floor (stand-in for the live $1B cap gate)")
    ap.add_argument("--perm-draws", type=int, default=PERM_DRAWS)
    ap.add_argument("--no-sweep", action="store_true", help="skip the constant sweeps")
    ap.add_argument("--casy", action="store_true", help="run ONLY the acceptance test")
    ap.add_argument("--symbol", default=None, help="acceptance test on another name")
    ap.add_argument("--date", default=CASY_DATE)
    ap.add_argument("--out", default=None, help="write the event table to this CSV")
    ap.add_argument("--from-csv", default=None,
                    help="re-report an earlier --out table instead of replaying "
                         "(the replay is the slow half; the statistics are not)")
    a = ap.parse_args()

    named_check(a.symbol or "CASY", a.date)
    if a.casy:
        sys.exit(0)
    E = (pd.read_csv(a.from_csv) if a.from_csv
         else events(a.hold, a.floor, a.names, a.min_dvol, a.universe))
    if a.out and not E.empty:
        E.to_csv(a.out, index=False)
        print("wrote %s (%d rows)" % (a.out, len(E)))
    report(E, a.hold, a.floor, a.perm_draws, not a.no_sweep)
