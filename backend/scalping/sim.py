"""Backtest-mode detection + outcome simulation for the scalping detectors.

The live detectors (detectors.py) answer "is there a signal RIGHT NOW". For a
walk-forward backtest / paper-trade we need the complementary view: given a full
day's bars, WHERE would each strategy have triggered (entry_ts), and what
happened next (stop / target / time-stop / EOD). Thresholds are imported from
detectors.py so the backtest can't silently drift from the live gates.
"""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from daytrading.indicators import opening_range
from . import detectors as D


def _et_col(day_rth: pd.DataFrame) -> pd.Series:
    et = day_rth.index.tz_localize("UTC").tz_convert("America/New_York")
    return pd.Series([t.hour * 60 + t.minute for t in et], index=day_rth.index)


# ── ORB (Zarattini Stocks-in-Play) — one entry/day in the opening direction ──
def orb_entries(day_rth: pd.DataFrame, *, rel_vol: Optional[float], atr14: Optional[float]) -> list:
    if day_rth is None or len(day_rth) < D.ORB_MINUTES + 2:
        return []
    if rel_vol is None or rel_vol < D.RELVOL_MIN or not atr14 or atr14 <= 0:
        return []
    orb = opening_range(day_rth, minutes=D.ORB_MINUTES)
    if not orb or not orb.get("complete"):
        return []
    oh, ol = orb["high"], orb["low"]
    if oh <= ol:
        return []
    window = day_rth.iloc[:D.ORB_MINUTES]
    net_pct = (float(window.iloc[-1]["close"]) / float(window.iloc[0]["open"]) - 1.0) * 100.0
    if abs(net_pct) < D.DOJI_PCT:
        return []
    side = "long" if net_pct > 0 else "short"
    trigger = oh if side == "long" else ol
    stop = (trigger - D.ORB_ATR_MULT * atr14) if side == "long" else (trigger + D.ORB_ATR_MULT * atr14)

    after = day_rth.iloc[D.ORB_MINUTES:]
    for ts, row in after.iterrows():
        crossed = (side == "long" and float(row["high"]) >= trigger) or \
                  (side == "short" and float(row["low"]) <= trigger)
        if crossed:
            risk = abs(trigger - stop)
            return [{
                "strategy": "stocks_in_play_orb", "side": side,
                "entry_ts": ts.isoformat(), "entry_price": round(trigger, 4),
                "stop": round(stop, 4), "target": None,          # primary exit = EOD/stop
                "rel_vol": round(rel_vol, 2), "atr14": round(atr14, 4),
                "risk": round(risk, 4),
                "check_entry_bar_stop": True,    # stop-order fill — entry bar can also stop out
            }]
    return []


# ── shock fade (Zawadowski) — non-overlapping fades through the day ──────────
def shock_fade_entries(day_rth: pd.DataFrame, *, atr14: Optional[float] = None,
                       lookback_min: int = D.SHOCK_LOOKBACK_MIN) -> list:
    if day_rth is None or len(day_rth) < lookback_min + 12:
        return []
    closes = day_rth["close"].astype(float).reset_index(drop=True)
    idx = list(day_rth.index)
    et_min = _et_col(day_rth).reset_index(drop=True)
    entries = []
    cooldown_until = -1
    for i in range(lookback_min + 6, len(closes)):
        if i <= cooldown_until:
            continue
        m = et_min.iloc[i]
        if m < (9 * 60 + 30 + D.EXCLUDE_OPEN_MIN) or m > (16 * 60 - D.EXCLUDE_CLOSE_MIN):
            continue
        px = closes.iloc[i]
        ref = closes.iloc[i - lookback_min]
        move_pct = (px / ref - 1.0) * 100.0
        baseline = closes.iloc[max(0, i - lookback_min - 30):i - lookback_min]
        rets = baseline.pct_change().dropna() * 100.0
        sigma1 = float(rets.std()) if len(rets) > 5 else None
        if not sigma1 or sigma1 <= 0:
            continue
        sigma_w = sigma1 * math.sqrt(lookback_min)
        if abs(move_pct) < D.SHOCK_MIN_MOVE_PCT or abs(move_pct) < D.SHOCK_SIGMA_MULT * sigma_w:
            continue
        side = "long" if move_pct < 0 else "short"
        stop_frac = abs(move_pct) * 0.30
        revert_frac = abs(move_pct) * 0.40
        stop = px * (1 - stop_frac / 100.0) if side == "long" else px * (1 + stop_frac / 100.0)
        target = px * (1 + revert_frac / 100.0) if side == "long" else px * (1 - revert_frac / 100.0)
        entries.append({
            "strategy": "shock_fade", "side": side,
            "entry_ts": idx[i].isoformat(), "entry_price": round(px, 4),
            "stop": round(stop, 4), "target": round(target, 4),
            "move_pct": round(move_pct, 2), "sigma_multiple": round(abs(move_pct) / sigma_w, 1),
            "atr14": round(atr14, 4) if atr14 else None,
            "time_stop_min": D.SHOCK_TIME_STOP_MIN, "risk": round(abs(px - stop), 4),
        })
        cooldown_until = i + D.SHOCK_TIME_STOP_MIN     # no overlapping fades
    return entries


def simulate_outcome(day_rth: pd.DataFrame, sig: dict) -> dict:
    """From entry_ts forward: stop / target / time-stop / EOD-flat, whichever
    first. Returns {outcome, exit_ts, exit_price, pnl_pct, r_multiple}."""
    entry_ts = pd.Timestamp(sig["entry_ts"])
    if entry_ts.tzinfo is not None:
        entry_ts = entry_ts.tz_convert(None)
    after = day_rth[day_rth.index > entry_ts]
    entry = sig["entry_price"]; stop = sig["stop"]; target = sig.get("target")
    side = sig["side"]; risk = abs(entry - stop)
    if risk == 0:
        return {"outcome": "invalid_risk", "pnl_pct": 0.0, "r_multiple": 0.0}

    # Entry-bar edge case (review fix 2026-06-09): a stop-order fill (ORB) happens
    # INSIDE the entry bar; if that same bar's range also spans the protective
    # stop, assume the WORST (stopped) rather than silently skipping the bar.
    if sig.get("check_entry_bar_stop"):
        eb = day_rth[day_rth.index == entry_ts]
        if not eb.empty:
            lo, hi = float(eb.iloc[0]["low"]), float(eb.iloc[0]["high"])
            if (side == "long" and lo <= stop) or (side == "short" and hi >= stop):
                return _exit("stop", entry_ts, stop, entry, risk, side)
    if after.empty:
        return {"outcome": "no_data", "pnl_pct": 0.0, "r_multiple": 0.0}
    time_stop = None
    if sig.get("time_stop_min"):
        time_stop = entry_ts + pd.Timedelta(minutes=int(sig["time_stop_min"]))

    for ts, row in after.iterrows():
        hi, lo = float(row["high"]), float(row["low"])
        if side == "long":
            if lo <= stop:
                return _exit("stop", ts, stop, entry, risk, side)
            if target and hi >= target:
                return _exit("target", ts, target, entry, risk, side)
        else:
            if hi >= stop:
                return _exit("stop", ts, stop, entry, risk, side)
            if target and lo <= target:
                return _exit("target", ts, target, entry, risk, side)
        if time_stop is not None and ts >= time_stop:
            return _exit("time_stop", ts, float(row["close"]), entry, risk, side)

    last = after.iloc[-1]
    return _exit("eod_flat", after.index[-1], float(last["close"]), entry, risk, side)


def _exit(outcome, ts, exit_price, entry, risk, side) -> dict:
    if side == "long":
        pnl_pct = (exit_price / entry - 1.0) * 100.0
        r = (exit_price - entry) / risk
    else:
        pnl_pct = (1.0 - exit_price / entry) * 100.0
        r = (entry - exit_price) / risk
    return {"outcome": outcome, "exit_ts": ts.isoformat(),
            "exit_price": round(exit_price, 4), "pnl_pct": round(pnl_pct, 3),
            "r_multiple": round(r, 3)}
