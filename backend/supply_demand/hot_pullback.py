"""🔥 Hot Pullback — a HOT name takes one hard flush into a demand band and
reverses the same day.

Ajay 2026-09-09: *"Can you create a new tab for hot pull back like 21 day moving
average drops but have a reversal from demand zones? The drop should be someting
like DYN today which bounced back quick. I wanna see such names whcih dropped
huge but have been hot in the market. Are having reversals"*

THE ARCHETYPE — DYN, 2026-09-08 (measured, closed bars):
    prev close 24.28 -> opened 17.08 -> low 17.00 -> closed 20.31
    the low landed INSIDE a 4-touch demand band at 16.56-17.02 (strength 92)
    the close finished +19.5% off that low, 85% of the way up the day's range,
    20.6% under the 21-day line, on 11x average volume.

OWNER RULES. Price-structure heuristics, this app's own. No book, no cites —
this is Supply & Demand / day-trade scope, never Minervini (see the SEPA-scope
rule). Not advice, and nothing here places an order.

── WHAT THE STUDY FOUND — CORRECTED 2026-09-09 ─────────────────────────────

**THIS RULE HAS NO MEASURED EDGE.** The numbers first shipped here were wrong.

The corrected measurement (2,594 usable names, bands rebuilt at every historical
date from PRIOR bars only, no lookahead; the trade is: buy the next open, stop
0.5% under the signal-day low, out at the 21-day line or after 3 sessions,
intrabar stops honoured):

    83 trades on 50 dates across 71 names, 2025-09-11 -> 2026-09-08
    51.8% win, mean +0.75%, median +0.21%, expectancy +0.10R
    median risk 8.8%, average win +7.82% against an average loss of -6.85%
    worst -14.61%, best +31.64%, exits 54 clock / 21 stop / 8 target
    95% CI (date-block bootstrap) -0.18R to +0.40R — IT INCLUDES ZERO,
    P(R <= 0) = 0.26

and +0.10R is the most favourable defensible figure. It does not survive:

    one trade per date (these are correlated market-wide flush days)  +0.094R
    dropping the single best date, 2025-11-24, alone                  +0.015R

The honest number for a sizing decision is **0.0R +/- 0.2**. A separate
survivorship check (the price cache holds delisted names the survivors-only
universe does not) put it at ~0.00R; that one is NOT reproduced by the shipped
script, so it is not quoted on the board.

WHY IT WAS WRONG, kept here because the failure is reusable. The original
feature pass computed rolling columns, ran `dropna()`, and only THEN applied
`rolling(252)` — so the event window began at bar 301, not 252. That off-by-49
silently deleted the first 49 eligible sessions: 17 trades running 23.5% win
and -0.418R, twelve of them on the 2025-11-06/07/11 market-wide flush days. The
backtest started one week after the sample's worst cluster. Moving the floor
back to bar 300 reproduces the old 65-event run exactly, stop count, target
count and worst case to the decimal.

Four independent re-derivations — one inline, three by separate agents that did
not share code — agree on 83 / 51.8% / +0.75% / +0.10R, and all four reproduce
the original by that one change. The measurement is now re-runnable in the repo
at `studies/hot_pullback_study.py`, which is the process failure that let this
reach a live board: the module, docs and tests shipped, the backtest did not.

WHAT ELSE THE CORRECTION OVERTURNED

 1. NO GATE IN THIS RULE SEPARATES, and the demand band least of all. This
    module used to call it "the one that matters". Measured: the same reversal
    with NO band (n=467) gives +0.007R against +0.100R here — a separation of
    0.093R at p=0.198. The snapback pair looks like the stronger of the two
    (+0.126R against the 3,906 it excludes) and still lands at p=0.234. Both
    are reproduced by `studies/hot_pullback_study.py`, which measures each gate
    against the cohort it removes.
 3. FLUSH DEPTH CARRIES NO INFORMATION. The -10%-under-the-21-day-line gate
    already implies a deep flush, so the flush gate is effectively inert:
    cutting at 10%, 12% or 15% selects the SAME 83 events. Ajay asked on
    2026-09-09 to loosen it to 10% — measured, that adds zero names. The only
    stable read is that deeper than 30% is worse (-0.059R, n=39).
 4. The forward medians were shifted a session. From the next open the real
    numbers are +0.79% by that close (52% up), +2.39% by day two (59%), +0.61%
    by day three (57%). The old "+2.40% by the next close" was the day-two
    figure and the old "+2.85%" existed nowhere.
 5. "2 years" was never reachable. The price cache holds ~501 bars per name and
    the 252-day hot gate eats half of them, so the window is ~12 months and the
    original run only ever saw ~9.5 of them.
 6. Worst simulated trade is -14.61%, not -13.3%.

WHAT IT IS STILL GOOD FOR. A watchlist. "A hot name took one hard flush into
structure and turned the same day" is a real, rare, legible thing to look at —
about 83 of them in a year. It is not a trade signal, the board says so on
every row, and the paper lane exists to keep measuring it forward.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("supply_demand.hot_pullback")

ET = ZoneInfo("America/New_York")

# ── the rule (owner constants; every one is a MEASURED cut, see the study) ──
HOT_ABOVE_52W_LOW_PCT = 30.0    # yesterday's close this far above its own 52w low
MIN_DOLLAR_VOL_USD = 5e6        # median 50-day dollar volume
FALL_FROM_10D_HIGH_PCT = -12.0  # today's LOW this far under the prior 10-day high
UNDER_MA21_PCT = -10.0          # today's close this far under the 21-day line
OFF_LOW_PCT = 8.0               # the close this far off today's low
RANGE_POS_MIN = 0.70            # and in the top 30% of today's range
MA_LEN = 21                     # "21 day moving average drops" — his words
HIGH_LOOKBACK = 10              # the prior 10-day high the flush is measured from

# What the study measured, carried on the payload so the board can print it and
# nobody has to trust a number typed into a component.
# CORRECTED 2026-09-09. The numbers first shipped here were wrong, and the cause
# is worth keeping in the file: the study's feature pass computed rolling columns,
# dropped NaNs, and only THEN applied rolling(252), so the event window began at
# bar 301 instead of 252. That off-by-49 silently deleted the first 49 eligible
# sessions — 17 events that ran 23.5% win / -0.418R, twelve of them on the
# 2025-11-06/07/11 market-wide flush days. Starting the backtest one week after
# the sample's worst cluster turned +0.10R into +0.27R.
#
# Four independent re-derivations (one inline, three by separate agents that did
# not share code) all land on the same corrected figures below, and all four
# reproduce the 65-event original exactly by moving the floor back to bar 300.
# The re-runnable measurement now lives at `studies/hot_pullback_study.py`.
STUDY = {
    "events": 83, "names": 71, "dates": 50,
    # NOT "2 years". The price cache holds ~501 bars and the 252-day HOT gate
    # eats half of them, so the reachable window is about twelve months.
    "window": "2025-10-21 to 2026-08-25",
    "window_note": "the price cache holds ~501 bars per name and the 52-week hot "
                   "gate consumes 252 of them, so two years is not reachable",
    # THE TRADE, simulated: buy the next open, stop 0.5% under the signal-day
    # low, out at the 21-day line or after 3 sessions, intrabar stops honoured.
    "sim_n": 83, "sim_win_pct": 51.8,
    "sim_mean_pct": 0.75, "sim_median_pct": 0.21,
    "sim_avg_win_pct": 7.82, "sim_avg_loss_pct": -6.85,
    "sim_worst_pct": -14.61, "sim_best_pct": 19.94,
    "sim_median_risk_pct": 8.8, "sim_expectancy_r": 0.10,
    "sim_exit_clock": 54, "sim_exit_stop": 21, "sim_exit_target": 8,
    "sim_distinct_dates": 50,
    # The interval, which is the point: it includes zero.
    "ci_lo_r": -0.188, "ci_hi_r": 0.405, "p_r_le_zero": 0.264,
    # …and three ways the +0.10R does not survive contact.
    "one_per_date_r": 0.094, "one_per_date_n": 50, "one_per_date_win_pct": 54,
    "drop_top_date_r": 0.015, "top_date": "2025-11-24",
    # Forward medians from the next open, corrected — the old +2.40% "by the
    # next close" was the day-2 number, and the old +2.85% existed nowhere.
    "next_open_fwd1_pct": 0.79, "next_open_up1_pct": 52,
    "next_open_fwd2_pct": 2.39, "next_open_up2_pct": 59,
    "next_open_fwd3_pct": 0.61, "next_open_up3_pct": 57,
    "placebo_fwd1_pct": 0.02, "placebo_fwd3_pct": 0.08, "placebo_up_pct": 50,
    # The band is NOT load-bearing. The original said it was "the one that
    # matters"; measured, it is the WEAKEST gate in the rule.
    "no_band_n": 467, "no_band_r": 0.007, "no_band_p": 0.198,
    "band_separation_r": 0.093,
    # NEITHER gate separates. The snapback looks like the stronger of the two
    # and still does not clear p<0.05 against the cohort it excludes.
    "snapback_excluded_n": 3906, "snapback_excluded_r": -0.026,
    "snapback_separation_r": 0.126, "snapback_p": 0.234,
    "flush_gate_is_inert": True,
    "deep_flush_30_r": -0.059, "deep_flush_30_n": 39,
}

CACHE_TTL_SEC = 180
MAX_ROWS = 60


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


# ── the pure rule ──────────────────────────────────────────────────────────
def is_hot(prev_close, low_252) -> bool:
    """Was it hot BEFORE the flush? Yesterday's close well above its own
    52-week low. Deliberately NOT 'near the 52-week high': the archetype was
    24% off its high when it broke."""
    pc, lo = _f(prev_close), _f(low_252)
    if pc is None or lo is None or lo <= 0:
        return False
    return (pc / lo - 1.0) * 100.0 >= HOT_ABOVE_52W_LOW_PCT


def flush_pct(day_low, high_10d) -> Optional[float]:
    """How far today's low fell below the prior 10-day high, negative."""
    lo, hi = _f(day_low), _f(high_10d)
    if lo is None or hi is None or hi <= 0:
        return None
    return (lo / hi - 1.0) * 100.0


def under_ma_pct(close, ma) -> Optional[float]:
    c, m = _f(close), _f(ma)
    if c is None or m is None or m <= 0:
        return None
    return (c / m - 1.0) * 100.0


def reversal(close, day_low, day_high) -> Optional[dict]:
    """The snapback: how far off the low the close finished, and where in the
    day's range it sits. None when the bar has no range."""
    c, lo, hi = _f(close), _f(day_low), _f(day_high)
    if c is None or lo is None or hi is None or lo <= 0 or hi <= lo:
        return None
    return {
        "off_low_pct": round((c / lo - 1.0) * 100.0, 2),
        "range_pos": round((c - lo) / (hi - lo), 3),
    }


def band_for_low(day_low, bands) -> Optional[dict]:
    """The demand band today's LOW landed inside, or None.

    Any TESTED demand band counts. `alert_gates.is_proven_band` is deliberately
    NOT applied: requiring 2+ touches measured WORSE (52% up vs 53%), and 3+
    touches worse again (50%). Tightening here would cost, not help.
    """
    lo = _f(day_low)
    if lo is None or lo <= 0:
        return None
    best = None
    for b in bands or []:
        if "demand" not in str(b.get("kind") or "").lower():
            continue
        blo, bhi = _f(b.get("lo")), _f(b.get("hi"))
        if blo is None or bhi is None or blo <= 0 or bhi < blo:
            continue
        if blo <= lo <= bhi:
            if best is None or (_f(b.get("strength")) or 0) > (_f(best.get("strength")) or 0):
                best = b
    return best


def qualifies(row: dict) -> tuple:
    """(ok, reasons). `row` carries the computed features. Every failure is
    named so the board can show near-misses instead of a silent empty list."""
    miss = []
    if not row.get("hot"):
        miss.append(f"not hot — the prior close is under {HOT_ABOVE_52W_LOW_PCT:g}% above its 52-week low")
    fall = _f(row.get("flush_pct"))
    if fall is None or fall > FALL_FROM_10D_HIGH_PCT:
        have = f"{fall:.1f}%" if fall is not None else "unknown"
        miss.append(f"the flush is only {have} off the 10-day high (rule {FALL_FROM_10D_HIGH_PCT:g}%)")
    ma = _f(row.get("under_ma21_pct"))
    if ma is None or ma > UNDER_MA21_PCT:
        have = f"{ma:.1f}%" if ma is not None else "unknown"
        miss.append(f"only {have} under the {MA_LEN}-day line (rule {UNDER_MA21_PCT:g}%)")
    rev = row.get("reversal") or {}
    if (_f(rev.get("off_low_pct")) or -99) < OFF_LOW_PCT:
        miss.append(f"the close is under {OFF_LOW_PCT:g}% off the low — no real snapback")
    if (_f(rev.get("range_pos")) or -1) < RANGE_POS_MIN:
        miss.append(f"the close is not in the top {(1-RANGE_POS_MIN)*100:.0f}% of the day's range")
    if not row.get("band"):
        # NOT "the one that matters" any more. That was the pre-correction claim
        # and the 2026-09-09 re-measurement disproved it: the same reversal with
        # NO band gives +0.007R against +0.100R, p=0.198.
        miss.append("the low never reached a tested demand band (a required part of the "
                    "rule, though measured it separates least — p=0.198)")
    return (not miss), miss


def plan_for(row: dict) -> Optional[dict]:
    """The measured plan. Entry is the NEXT OPEN (it measured better than the
    close, because the signal day gaps down into it 60% of the time), with the
    trigger variant carried alongside. Stop under the signal day's LOW, which is
    the low that tagged the band. Target is the 21-day line the flush fell
    from — the thing that has to be reclaimed for the pullback to be over."""
    close = _f(row.get("close"))
    low = _f(row.get("low"))
    high = _f(row.get("high"))
    ma21 = _f(row.get("ma21"))
    if close is None or low is None or high is None or low <= 0:
        return None
    stop = round(low * 0.995, 2)
    risk = (close - stop) / close * 100.0 if close > stop else None
    out = {
        # The next open is what the corrected study measures (+0.79% by that
        # close, +2.39% by day two) and what the paper lane trades. The old
        # "60% of the time" gap claim came from the invalidated run.
        "entry_note": "next open — the entry the corrected study measures and the paper lane trades",
        "trigger": round(high * 1.001, 2),
        # No fire-rate claim here any more. The old one (83%) came from the
        # backtest the 2026-09-09 correction invalidated, and the corrected run
        # did not re-measure the trigger variant.
        "trigger_note": "or wait for a trade over the signal-day high (unmeasured variant)",
        "stop": stop,
        "stop_note": "0.5% under the signal-day low, the low that tagged the band",
        "risk_from_close_pct": round(risk, 1) if risk is not None else None,
        "target": round(ma21, 2) if ma21 else None,
        "target_note": f"the {MA_LEN}-day line the flush fell away from",
        # The clock is the LANE's rule, not a measured edge boundary: the
        # corrected study found no edge at any horizon, so holding longer would
        # simply be trading something unmeasured for longer.
        "horizon": "1-3 sessions — the lane's clock. No measured edge at any horizon.",
    }
    if ma21 and close > 0:
        out["target_pct"] = round((ma21 / close - 1.0) * 100.0, 1)
        if risk:
            out["rr"] = round((ma21 - close) / (close - stop), 1) if close > stop else None
    return out


def sort_key(row: dict) -> tuple:
    """Deepest flush first, then the strongest snapback. Nothing about mood
    or band 'quality' — both measured neutral-to-negative here."""
    return (_f(row.get("flush_pct")) or 0.0,
            -(_f((row.get("reversal") or {}).get("off_low_pct")) or 0.0))


def rules_lines() -> list:
    """Every line built from the enforcing constant."""
    s = STUDY
    return [
        f"Hot first: the prior close sits at least {HOT_ABOVE_52W_LOW_PCT:g}% above its own 52-week low, "
        f"median 50-day dollar volume at least ${MIN_DOLLAR_VOL_USD/1e6:.0f}M.",
        f"The flush: today's LOW is at least {abs(FALL_FROM_10D_HIGH_PCT):g}% under the prior "
        f"{HIGH_LOOKBACK}-day high AND the close is at least {abs(UNDER_MA21_PCT):g}% under the "
        f"{MA_LEN}-day line.",
        f"Into demand: that low landed inside a TESTED demand band.",
        f"The snapback: the close finished at least {OFF_LOW_PCT:g}% off the low and in the top "
        f"{(1-RANGE_POS_MIN)*100:.0f}% of the day's range.",
        f"NO MEASURED EDGE. {s['sim_n']} trades on {s['sim_distinct_dates']} dates across "
        f"{s['names']} names ({s['window']}): {s['sim_win_pct']:g}% win, mean {s['sim_mean_pct']:+g}%, "
        f"expectancy {s['sim_expectancy_r']:+g}R on a median {s['sim_median_risk_pct']:g}% risk. "
        f"The 95% interval is {s['ci_lo_r']:+g}R to {s['ci_hi_r']:+g}R — it INCLUDES ZERO "
        f"(P(R<=0) = {s['p_r_le_zero']:g}). Treat this board as a watchlist, not an edge.",
        f"AND IT IS FRAGILE: these are correlated market-wide flush days — {s['sim_n']} trades sit on "
        f"only {s['sim_distinct_dates']} dates. Dropping {s['top_date']} alone takes it to "
        f"{s['drop_top_date_r']:+g}R. One trade per date leaves {s['one_per_date_r']:+g}R on "
        f"{s['one_per_date_n']} trades — still inside the noise.",
        f"CORRECTED 2026-09-09. This board previously claimed 58% win and +0.27R. That came from a "
        f"backtest whose event window started at bar 300 instead of 252, "
        f"deleting 17 trades that ran -0.418R — twelve of them on the 2025-11-06/07/11 flush days. "
        f"Expectancy was overstated about 2.3x and the mean trade about 3x.",
        f"NO GATE IN THIS RULE SEPARATES. Demand band: {s['sim_expectancy_r']:+g}R kept against "
        f"{s['no_band_r']:+g}R for the same reversal with NO band (n={s['no_band_n']}), "
        f"p={s['no_band_p']:g}. Snapback pair: against {s['snapback_excluded_r']:+g}R "
        f"(n={s['snapback_excluded_n']}), p={s['snapback_p']:g}. Neither clears p<0.05. This board "
        f"used to call the demand band 'the one that matters' — measured, it does not.",
        f"FLUSH DEPTH CARRIES NO INFORMATION: the {abs(UNDER_MA21_PCT):g}%-under-the-21-day gate "
        f"already implies a deep flush, so moving the flush cut from "
        f"{abs(FALL_FROM_10D_HIGH_PCT):g}% to 10% adds ZERO names. The only stable read across the "
        f"range is that deeper than 30% is worse ({s['deep_flush_30_r']:+g}R, "
        f"n={s['deep_flush_30_n']}).",
        f"Exits: {s['sim_exit_clock']} on the clock, {s['sim_exit_stop']} stopped, "
        f"{s['sim_exit_target']} at target. Worst simulated trade {s['sim_worst_pct']:g}%.",
        f"The rule is price-only — it cannot tell a liquidation flush from a permanent repricing. "
        f"DYN itself fell because ANOTHER company missed the endpoint Dyne's own study uses.",
    ]


# ── the scan ───────────────────────────────────────────────────────────────
def _frames(symbols):
    """{sym: DataFrame} of CLOSED daily bars from the shared price cache.

    Closed bars only, straight from `price_cache`. Today's bar is NEVER taken
    from here — a cached doc written during the session holds a partial bar
    (the PHVS trap, 2026-09-08), so the live day comes from `bulk_snapshot`
    below, which is the tape rather than a frozen fragment.
    """
    import pandas as pd
    from sepa import prices
    coll = prices._get_mongo()
    if coll is None:
        return {}
    out = {}
    cur = coll.find({"symbol": {"$in": list(symbols)}}, {"symbol": 1, "bars": 1, "_id": 0})
    for d in cur:
        bars = d.get("bars") or []
        if len(bars) < 260:
            continue
        f = pd.DataFrame(bars).dropna(subset=["close"]).sort_values("date").reset_index(drop=True)
        if len(f) >= 260:
            out[d["symbol"]] = f
    return out


def _today_bar(sym: str, snap: dict, frame) -> Optional[dict]:
    """Today's o/h/l/c/v for `sym`, and whether it is the live session or the
    last completed one. Returns None when there is nothing usable."""
    row = (snap or {}).get(sym) or {}
    o, h, l = _f(row.get("open")), _f(row.get("high")), _f(row.get("low"))
    c = _f(row.get("close"))
    v = _f(row.get("volume"))
    last_cached = str(frame["date"].iloc[-1])[:10]
    snap_date = str(row.get("date") or "")[:10]
    fresh = bool(snap_date and snap_date > last_cached)
    if fresh and c and h and l and l > 0 and h >= l:
        # RESTAMP GUARD (2026-09-09). Before the open, Massive rolls the
        # snapshot's `date` forward to today while the aggregate still holds
        # YESTERDAY's session. Taken at face value that dates the last closed
        # bar as today and prints a 0.0% day change on it (caught on DYN, whose
        # 09-08 flush came back stamped 09-09). A snapshot whose OHLC matches
        # the last cached bar to the cent is that restamp, not a live session.
        try:
            prev = frame.iloc[-1]
            same = all(
                abs(float(a) - float(b)) < 0.005
                for a, b in ((o, prev["open"]), (h, prev["high"]),
                             (l, prev["low"]), (c, prev["close"]))
                if a is not None and b == b
            )
        except Exception:
            same = False
        if not same:
            return {"open": o, "high": h, "low": l, "close": c, "volume": v,
                    "date": snap_date, "live": True}
    # fall back to the last CLOSED bar (evenings, weekends, a cold snapshot)
    r = frame.iloc[-1]
    try:
        return {"open": _f(r["open"]), "high": _f(r["high"]), "low": _f(r["low"]),
                "close": _f(r["close"]), "volume": _f(r.get("volume")),
                "date": last_cached, "live": False}
    except Exception:
        return None


def scan(universe_key: str = "full", limit: int = MAX_ROWS,
         include_near_miss: bool = True) -> dict:
    """Today's hot-pullback rows. Reads caches; never mutates the price cache."""
    import numpy as np
    from sepa import prices, universe as U
    from supply_demand import zone_store as ZS

    try:
        syms = sorted(set(U.load_universe(universe_key)))
    except Exception as exc:
        log.warning("hot_pullback: universe failed: %s", exc)
        return {"rows": [], "near_miss": [], "error": "universe unavailable"}

    frames = _frames(syms)
    if not frames:
        return {"warming": True, "rows": [], "near_miss": []}

    # one snapshot for the live day, one zone-store read for the bands
    try:
        snap = prices.bulk_snapshot(list(frames))
    except Exception as exc:
        log.warning("hot_pullback: snapshot failed: %s", exc)
        snap = {}
    try:
        store_day, store = ZS.load_latest(list(frames))
    except Exception as exc:
        log.warning("hot_pullback: zone_store failed: %s", exc)
        store_day, store = None, {}

    hits, near = [], []
    for sym, f in frames.items():
        try:
            c = f["close"].astype(float)
            h = f["high"].astype(float)
            v = f["volume"].astype(float)
            today = _today_bar(sym, snap, f)
            if not today or not today.get("close"):
                continue
            live = bool(today["live"])
            # history = every bar BEFORE today's
            hist_c = c if not live else c
            prior_c = hist_c.iloc[-1] if live else hist_c.iloc[-2]
            prior_hi10 = (h.iloc[-HIGH_LOOKBACK:] if live else h.iloc[-HIGH_LOOKBACK-1:-1]).max()
            lo252 = (hist_c.iloc[-252:] if live else hist_c.iloc[-253:-1]).min()
            ma_src = list(hist_c.iloc[-(MA_LEN-1):]) + [today["close"]] if live else list(hist_c.iloc[-MA_LEN:])
            ma21 = float(np.mean(ma_src))
            dvol = float((c * v).iloc[-50:].median())
            v50 = float(v.iloc[-50:].mean())

            row = {
                "symbol": sym, "date": today["date"], "live": live,
                "close": round(float(today["close"]), 4),
                "open": today["open"], "high": today["high"], "low": today["low"],
                "prev_close": round(float(prior_c), 4),
                "change_pct": round((today["close"] / float(prior_c) - 1) * 100, 2) if prior_c else None,
                "ma21": round(ma21, 4),
                "high_10d": round(float(prior_hi10), 4),
                "low_252": round(float(lo252), 4),
                "dollar_vol_musd": round(dvol / 1e6, 1),
                "vol_x": round(float(today["volume"]) / v50, 1) if (today.get("volume") and v50) else None,
                "hot": is_hot(prior_c, lo252),
                "above_52w_low_pct": round((float(prior_c) / float(lo252) - 1) * 100, 1) if lo252 else None,
                "flush_pct": round(flush_pct(today["low"], prior_hi10) or 0.0, 2),
                "under_ma21_pct": round(under_ma_pct(today["close"], ma21) or 0.0, 2),
                "reversal": reversal(today["close"], today["low"], today["high"]),
                "band": None,
            }
            if dvol < MIN_DOLLAR_VOL_USD:
                continue
            row["band"] = band_for_low(today["low"], (store.get(sym) or {}).get("bands") or [])
            ok, miss = qualifies(row)
            row["misses"] = miss
            row["plan"] = plan_for(row) if ok else None
            if ok:
                hits.append(row)
            elif include_near_miss and len(miss) == 1 and row["hot"]:
                near.append(row)
        except Exception as exc:                                # pragma: no cover
            log.debug("hot_pullback: %s failed: %s", sym, exc)

    hits.sort(key=sort_key)
    near.sort(key=sort_key)
    return {
        "warming": False,
        "universe": universe_key,
        "as_of": datetime.now(tz=ET).isoformat(timespec="seconds"),
        "zone_store_day": store_day.isoformat() if store_day else None,
        "scanned": len(frames),
        "n": len(hits),
        "rows": hits[:max(1, int(limit))],
        "near_miss": near[:12],
        "study": STUDY,
        "rules": rules_lines(),
    }


# ── cache ──────────────────────────────────────────────────────────────────
_CACHE: dict = {}
_LOCK = threading.Lock()
_SCAN_LOCKS: dict = {}


def _scan_lock(key: str) -> threading.Lock:
    """One lock per cache key, so two forced passes coalesce onto one scan."""
    with _LOCK:
        lk = _SCAN_LOCKS.get(key)
        if lk is None:
            lk = _SCAN_LOCKS[key] = threading.Lock()
        return lk


def cached_or_warm(universe_key: str = "full", limit: int = MAX_ROWS,
                   force: bool = False) -> dict:
    """Serve what we have, warm in a thread. Never blocks (the 2026-08-14 524)
    — EXCEPT under `force`, which blocks and re-scans.

    `force` used to fall through to the background-warm path and hand back the
    STALE board flagged `warming: True`. Two things read that as a failure: the
    Scan button, which showed the same rows and looked like nothing happened,
    and `record()`, which refuses a warming payload — so the 17:05 cron, the one
    the paper lane depends on, wrote nothing. The 2026-08-14 524 was a ~100s
    Cloudflare cut; this scan is ~6s, so blocking here is safe.
    """
    key = f"{universe_key}:{limit}"
    if force:
        with _LOCK:
            before = float((_CACHE.get(key) or {}).get("ts") or 0.0)
        with _scan_lock(key):
            with _LOCK:
                hit = _CACHE.get(key)
                if hit and float(hit.get("ts") or 0.0) > before and not hit.get("warming"):
                    return {**hit["data"], "cached": True}   # another Scan just ran
            data = scan(universe_key, limit)
            with _LOCK:
                _CACHE[key] = {"ts": time.time(), "data": data, "warming": False}
            return data
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and (now - hit["ts"]) < CACHE_TTL_SEC:
            return {**hit["data"], "cached": True}
        warming = bool(hit and hit.get("warming"))
    if hit and not warming:
        with _LOCK:
            _CACHE[key] = {**hit, "warming": True}

        def _work():
            try:
                data = scan(universe_key, limit)
                with _LOCK:
                    _CACHE[key] = {"ts": time.time(), "data": data, "warming": False}
            except Exception as exc:
                log.warning("hot_pullback warm failed: %s", exc)
                with _LOCK:
                    _CACHE[key] = {**_CACHE.get(key, {}), "warming": False}

        threading.Thread(target=_work, daemon=True).start()
        return {**hit["data"], "cached": True, "warming": True}
    data = scan(universe_key, limit)
    with _LOCK:
        _CACHE[key] = {"ts": time.time(), "data": data, "warming": False}
    return data


# ── history ────────────────────────────────────────────────────────────────
# The board is computed off the LATEST bar. During RTH that bar is today's
# live partial session, so a lane that re-scans at 09:35 sees rows dated TODAY
# and `hot_pullback_entry.signal_is_fresh` rejects every one of them — the lane
# could never fire. The signal day is a CLOSED session, so it has to be written
# down when it closes and read back the next morning. That is what this is for.
RUNS_COLL = "hot_pullback_runs"
_KEEP = ("symbol", "date", "live", "close", "open", "high", "low", "prev_close",
         "change_pct", "ma21", "high_10d", "low_252", "dollar_vol_musd", "vol_x",
         "above_52w_low_pct", "flush_pct", "under_ma21_pct", "reversal", "band",
         "plan", "misses")


def market_closed_reason(now: Optional[datetime] = None) -> Optional[str]:
    """'weekend' / 'holiday YYYY-MM-DD' / None — the one calendar
    (`market_hours.gate`). The BOARD still renders on a closed day, on purpose;
    only `record` is gated, so a holiday cron cannot write a history row built
    from stale prices."""
    try:
        from market_hours import gate
        return gate.closed_reason(now or datetime.now(ET))
    except Exception:
        return None


def _db():
    try:
        from sepa import prices as _p
        coll = _p._get_mongo()
        return coll.database if coll is not None else None
    except Exception as exc:                                   # pragma: no cover
        log.warning("hot_pullback: mongo unavailable: %s", exc)
        return None


def closed_session_rows(data: dict) -> tuple:
    """(day, rows) for the CLOSED session in a board payload, or (None, []).

    A row carrying `live: True` is today's unfinished bar. It is a fine thing to
    look at and a terrible thing to trade off tomorrow, so it never gets
    written. All recorded rows share one session date.
    """
    rows = [r for r in (data or {}).get("rows") or []
            if not r.get("live") and r.get("date")]
    if not rows:
        return None, []
    day = max(str(r["date"])[:10] for r in rows)
    return day, [r for r in rows if str(r["date"])[:10] == day]


def record(data: dict) -> bool:
    """Persist one completed pass to Mongo `hot_pullback_runs`, keyed by the
    CLOSED session it describes.

    Called from the endpoint when the cron asks for `record=true`, so the ONE
    scan that warms the API's own cache is also the one that lands in history.
    A cron running `python -m supply_demand.hot_pullback` in the cron container
    would warm a different process's memory and leave the page cold — the same
    trap the 09:25 demand-reentry curl exists to avoid.

    Idempotent: re-running the same session's cron replaces that day's doc
    rather than stacking duplicates.
    """
    if not data or data.get("warming"):
        return False
    closed = market_closed_reason()
    if closed:
        log.info("hot_pullback: not recording — market closed (%s)", closed)
        return False
    day, rows = closed_session_rows(data)
    if not day:
        log.info("hot_pullback: not recording — no closed-session row to write")
        return False
    db = _db()
    if db is None:
        return False
    try:
        getattr(db, RUNS_COLL).replace_one(
            {"day": day},
            {"day": day, "as_of": data.get("as_of"),
             "universe": data.get("universe"), "scanned": data.get("scanned"),
             "n": len(rows),
             "rows": [{k: r.get(k) for k in _KEEP} for r in rows],
             "near_miss": [{k: r.get(k) for k in _KEEP}
                           for r in (data.get("near_miss") or [])[:12]]},
            upsert=True)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("hot_pullback: persist failed: %s", exc)
        return False
    log.info("hot_pullback recorded %s: %d row(s)", day, len(rows))
    return True


def last_closed_signals(before: Optional[str] = None) -> tuple:
    """(day, rows) — the newest RECORDED closed session, for the paper lane.

    `before` (an ET date string) excludes that day and everything after it, so
    a lane running today reads yesterday's board and never its own morning.
    Returns (None, []) when nothing is recorded — the lane then buys nothing,
    which is the correct behaviour for a board that never scanned.
    """
    db = _db()
    if db is None:
        return None, []
    q = {"day": {"$lt": str(before)[:10]}} if before else {}
    try:
        doc = getattr(db, RUNS_COLL).find_one(q, sort=[("day", -1)])
    except Exception as exc:                                   # noqa: BLE001
        log.warning("hot_pullback: history read failed: %s", exc)
        return None, []
    if not doc:
        return None, []
    return doc.get("day"), list(doc.get("rows") or [])


def run(universe_key: str = "full", limit: int = MAX_ROWS) -> dict:
    """Manual / module entry point: scan, persist, seed this process's cache."""
    data = scan(universe_key, limit)
    record(data)
    with _LOCK:
        _CACHE[f"{universe_key}:{limit}"] = {
            "ts": time.time(), "data": data, "warming": False}
    return data


if __name__ == "__main__":  # pragma: no cover - manual entry
    logging.basicConfig(level=logging.INFO)
    d = run()
    print(f"{d.get('n')} row(s) of {d.get('scanned')} scanned")
