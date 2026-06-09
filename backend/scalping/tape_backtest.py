"""Backtest of the tape READ itself — over real Massive 1-min history, classify
every completed 5-min candle at its levels and measure what actually happened
over the next 30 minutes. Answers the only question that matters before trusting
the alerts: does BREAKOUT_STRONG actually precede strength, and REJECTION/
BREAKDOWN precede weakness — or is the read noise?

Honest limits (travel in the payload): the historical run can't use the SEPA
pivot (it changes scan-to-scan), so level contexts are OR-high / day-high / VWAP
only; outcomes are GROSS price moves (no costs — this validates the READ, not a
trading P&L); one ~3-week regime.
"""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Optional

import pandas as pd

from . import candles

log = logging.getLogger("scalping.tape_backtest")

FWD_MIN = 30
UNIVERSE_CAP = 12
_TTL_SEC = 6 * 3600
_CACHE: dict = {"at": 0.0, "key": None, "data": None}


def _classify_day(day_rth: pd.DataFrame) -> list:
    """Walk a day's completed 5-min bars; classify each against levels AS OF that
    bar (no look-ahead); attach the +30min forward return."""
    from daytrading.indicators import vwap_session
    if day_rth is None or len(day_rth) < 40:
        return []
    df5 = candles.aggregate_5min(day_rth)
    if len(df5) < 4:
        return []
    vw = vwap_session(day_rth, session="rth")
    closes_1m = day_rth["close"]
    out = []
    # i = index of the bar being read (needs ≥1 prior bar and a +30m future bar)
    for i in range(2, len(df5)):
        bar_end = df5.index[i] + pd.Timedelta(minutes=5)
        hist_1m = day_rth[day_rth.index < bar_end]
        if len(hist_1m) < 11:
            continue
        # Levels as of this bar: OR high (first 5 bars of 1-min), running day high
        # BEFORE this 5-min bar, VWAP at bar end.
        or_high = float(hist_1m.iloc[:5]["high"].max())
        prior_1m = day_rth[day_rth.index < df5.index[i]]
        day_high = float(prior_1m["high"].max()) if len(prior_1m) else None
        vw_hist = vw[vw.index < bar_end].dropna()
        vwap_now = float(vw_hist.iloc[-1]) if len(vw_hist) else None
        levels = {"pivot": None, "vwap": vwap_now, "or_high": or_high, "day_high": day_high}
        sub5 = df5.iloc[: i + 1]
        avg_vol = float(sub5["volume"].iloc[:-1].mean()) if len(sub5) > 1 else None
        read = candles.classify(sub5, levels, avg_vol)
        if not read:
            continue
        base = float(df5.iloc[i]["close"])
        fwd = closes_1m[closes_1m.index >= bar_end + pd.Timedelta(minutes=FWD_MIN)]
        if fwd.empty:
            continue
        fwd_pct = (float(fwd.iloc[0]) / base - 1.0) * 100.0
        out.append({"state": read["state"], "verdict": read["verdict"],
                    "fwd_pct": round(fwd_pct, 3)})
    return out


def _agg(events: list) -> dict:
    by_state: dict = {}
    for e in events:
        s = by_state.setdefault(e["state"], {"n": 0, "fwd": [], "verdict": e["verdict"]})
        s["n"] += 1
        s["fwd"].append(e["fwd_pct"])
    out = {}
    for state, s in by_state.items():
        fwd = sorted(s["fwd"])
        n = s["n"]
        med = fwd[n // 2]
        pos = sum(1 for x in fwd if x > 0) / n * 100
        # "follow-through" = moved the direction the verdict implied
        follow = pos if s["verdict"] == "constructive" else (100 - pos) if s["verdict"] == "deteriorating" else None
        out[state] = {
            "n": n, "verdict": s["verdict"],
            "median_fwd_30m_pct": round(med, 3),
            "mean_fwd_30m_pct": round(sum(fwd) / n, 3),
            "pct_positive_30m": round(pos, 1),
            "follow_through_pct": round(follow, 1) if follow is not None else None,
        }
    return out


def _verdict(by_state: dict) -> str:
    strong = by_state.get("BREAKOUT_STRONG") or {}
    rej = by_state.get("REJECTION") or {}
    bits = []
    if strong.get("n", 0) >= 15:
        bits.append(f"BREAKOUT_STRONG: median +30m {strong['median_fwd_30m_pct']:+.2f}%, "
                    f"follow-through {strong['follow_through_pct']}% (n={strong['n']})")
    if rej.get("n", 0) >= 15:
        bits.append(f"REJECTION: median +30m {rej['median_fwd_30m_pct']:+.2f}%, "
                    f"follow-through {rej['follow_through_pct']}% (n={rej['n']})")
    if not bits:
        return "Too few classified events in this window to grade the read — directional at best."
    return " · ".join(bits) + ". A follow-through near 50% means the read adds nothing — judge it honestly."


def run(symbols: Optional[list] = None, days: int = 15, profile: str = "aggressive") -> dict:
    from daytrading.data import load_intraday_range, trading_days_back
    from . import engine, sepa_watch
    if symbols is None:
        # Prefer the actual watch names; fall back to the liquid universe.
        symbols = [e["symbol"] for e in sepa_watch.watch_universe()] or engine._universe(profile, UNIVERSE_CAP)
    symbols = symbols[:UNIVERSE_CAP]
    sessions = trading_days_back(days)
    if not sessions:
        return {"error": "no trading days"}

    events: list = []
    syms_used = 0
    for sym in symbols:
        try:
            df = load_intraday_range(sym, min(sessions), max(sessions), include_premarket=False)
        except Exception as exc:
            log.debug("tape backtest load %s failed: %s", sym, exc)
            continue
        if df is None or df.empty:
            continue
        rth = df[df["session"] == "rth"]
        if rth.empty:
            continue
        syms_used += 1
        et = rth.index.tz_localize("UTC").tz_convert("America/New_York")
        day_ser = pd.Series([t.date() for t in et], index=rth.index)
        for d in sorted(day_ser.unique()):
            events.extend(_classify_day(rth[day_ser == d]))

    by_state = _agg(events)
    return {
        "generated_at": int(time.time()),
        "days": days, "symbols_used": syms_used, "n_events": len(events),
        "by_state": by_state,
        "verdict": _verdict(by_state),
        "caveats": [
            "Validates the READ, not a P&L — forward moves are GROSS, no costs.",
            "Historical run can't use the SEPA pivot (changes scan-to-scan): contexts are OR-high / day-high / VWAP.",
            f"~{days} trading days = one regime. Follow-through ≈50% means the read is noise — say so.",
            "Educational, not advice.",
        ],
    }


def get(days: int = 15, force: bool = False) -> dict:
    now = time.time()
    if not force and _CACHE["data"] is not None and _CACHE["key"] == days and (now - _CACHE["at"]) < _TTL_SEC:
        return _CACHE["data"]
    data = run(days=days)
    _CACHE.update(at=now, key=days, data=data)
    return data
