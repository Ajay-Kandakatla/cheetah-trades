"""Historical walk-forward backtest for the scalping detectors over real Massive
1-min bars. Reports GROSS beside NET-of-cost — because, per the research, gross
is the lie and net is the truth.

Honesty caveats travel in the payload and are non-negotiable:
  • NO historical NBBO — the spread is an ASSUMPTION (`assumed_spread_pct`), and
    the research says the spread is exactly what kills these trades. Treat net
    numbers as an OPTIMISTIC upper bound.
  • slippage / commission / borrow are modeled, not real fills.
  • ~1 month is a single regime, not a robustness test.
  • the universe is today's liquid movers (mild look-ahead in name selection).

RelVol and ATR are computed as-of each day with NO intraday look-ahead (opening-
window RelVol vs prior days; daily ATR from days strictly before).
"""
from __future__ import annotations

import logging
import os
import time
from datetime import timedelta
from typing import Optional

import numpy as np
import pandas as pd

from . import costs, engine, sim

log = logging.getLogger("scalping.backtest")

DEFAULT_ASSUMED_SPREAD_PCT = 0.05      # liquid large-cap assumption; clearly flagged
UNIVERSE_CAP = 12                      # bound the run
_TTL_SEC = 6 * 3600


def _attach_et_date(rth: pd.DataFrame) -> pd.Series:
    et = rth.index.tz_localize("UTC").tz_convert("America/New_York")
    return pd.Series([t.date() for t in et], index=rth.index)


def _open_relvol(rth: pd.DataFrame, et_date_ser: pd.Series, day, window_min=5, lookback=14):
    """First-`window_min`-min volume on `day` ÷ mean of the same opening window on
    the prior `lookback` days. The Zarattini 'stock in play' gate — no look-ahead."""
    today = rth[et_date_ser == day]
    if today.empty:
        return None
    today_open_vol = float(today.iloc[:window_min]["volume"].sum())
    prior = sorted([d for d in et_date_ser.unique() if d < day])[-lookback:]
    vols = []
    for d in prior:
        sub = rth[et_date_ser == d].iloc[:window_min]
        if not sub.empty:
            vols.append(float(sub["volume"].sum()))
    if not vols:
        return None
    avg = np.mean(vols)
    return round(today_open_vol / avg, 2) if avg > 0 else None


def _daily_atr_asof(rth: pd.DataFrame, et_date_ser: pd.Series, day, period=14):
    """Daily ATR(period) from days STRICTLY BEFORE `day` (no look-ahead)."""
    prior = sorted([d for d in et_date_ser.unique() if d < day])[-(period + 1):]
    if len(prior) < 3:
        return None
    rows = []
    for d in prior:
        sub = rth[et_date_ser == d]
        rows.append((float(sub["high"].max()), float(sub["low"].min()), float(sub["close"].iloc[-1])))
    daily = pd.DataFrame(rows, columns=["high", "low", "close"])
    prev_close = daily["close"].shift(1)
    tr = pd.concat([(daily["high"] - daily["low"]).abs(),
                    (daily["high"] - prev_close).abs(),
                    (daily["low"] - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(min(period, len(daily))).mean().iloc[-1]
    return float(atr) if atr == atr else None


def _net(trade: dict, assumed_spread_pct: float) -> dict:
    entry = trade["entry_price"]
    cost = costs.round_trip_cost_pct(entry, spread_pct=assumed_spread_pct,
                                     is_short=trade["side"] == "short").get("total_pct") or 0.0
    risk_pct = (trade["risk"] / entry * 100.0) if entry and entry > 0 else None
    net_pnl = trade["pnl_pct"] - cost
    net_r = round(net_pnl / risk_pct, 3) if risk_pct else None
    return {"cost_pct": round(cost, 4), "net_pnl_pct": round(net_pnl, 3), "net_r_multiple": net_r}


def _agg(trades: list) -> dict:
    if not trades:
        return {"n_trades": 0, "note": "no trades fired"}
    df = pd.DataFrame(trades)
    n = len(df)
    gross_wr = float((df["pnl_pct"] > 0).mean() * 100)
    net_wr = float((df["net_pnl_pct"] > 0).mean() * 100)
    gross_exp = float(df["r_multiple"].mean())
    net_exp = float(df["net_r_multiple"].dropna().mean()) if df["net_r_multiple"].notna().any() else None
    net_sum = float(df["net_pnl_pct"].sum())
    gross_sum = float(df["pnl_pct"].sum())
    wins = df[df["net_pnl_pct"] > 0]["net_pnl_pct"].sum()
    losses = abs(df[df["net_pnl_pct"] < 0]["net_pnl_pct"].sum())
    pf = round(wins / losses, 2) if losses > 0 else None
    by_side = {}
    for side in df["side"].unique():
        sub = df[df["side"] == side]
        by_side[side] = {"n": int(len(sub)),
                         "net_win_rate_pct": round(float((sub["net_pnl_pct"] > 0).mean() * 100), 1)}
    return {
        "n_trades": n,
        "gross_win_rate_pct": round(gross_wr, 1),
        "net_win_rate_pct": round(net_wr, 1),
        "gross_expectancy_r": round(gross_exp, 3),
        "net_expectancy_r": round(net_exp, 3) if net_exp is not None else None,
        "gross_total_pnl_pct": round(gross_sum, 2),
        "net_total_pnl_pct": round(net_sum, 2),
        "net_profit_factor": pf,
        "outcome_counts": df["outcome"].value_counts().to_dict(),
        "by_side": by_side,
        "verdict": _verdict(net_exp, n),
    }


def _verdict(net_exp: Optional[float], n: int) -> str:
    if n < 20:
        return f"Only {n} trades — too few to conclude anything. Directional at best."
    if net_exp is None:
        return "Net expectancy undefined."
    if net_exp <= 0:
        return f"Net expectancy {net_exp:+.2f}R after costs — NOT profitable on this window."
    if net_exp < 0.1:
        return f"Net expectancy {net_exp:+.2f}R — barely positive; inside the cost/assumption noise."
    return f"Net expectancy {net_exp:+.2f}R after the ASSUMED spread — promising but spread-assumption-dependent."


def run_backtest(symbols: Optional[list] = None, days: int = 20, profile: str = "aggressive",
                 assumed_spread_pct: float = DEFAULT_ASSUMED_SPREAD_PCT) -> dict:
    from daytrading.data import load_intraday_range, trading_days_back
    universe = (symbols or engine._universe(profile, UNIVERSE_CAP))[:UNIVERSE_CAP]
    sessions = trading_days_back(days)
    if not sessions:
        return {"error": "no trading days"}
    from_day = min(sessions) - timedelta(days=28)     # RelVol/ATR context
    to_day = max(sessions)

    trades: list = []
    syms_used = 0
    for sym in universe:
        try:
            df = load_intraday_range(sym, from_day, to_day, include_premarket=False)
        except Exception as exc:
            log.debug("backtest load %s failed: %s", sym, exc)
            continue
        if df is None or df.empty:
            continue
        rth = df[df["session"] == "rth"]
        if rth.empty:
            continue
        et_date = _attach_et_date(rth)
        syms_used += 1
        for d in sessions:
            day_rth = rth[et_date == d]
            if len(day_rth) < sim.D.ORB_MINUTES + 12:
                continue
            rel_vol = _open_relvol(rth, et_date, d)
            atr14 = _daily_atr_asof(rth, et_date, d)
            sigs = sim.orb_entries(day_rth, rel_vol=rel_vol, atr14=atr14) + \
                sim.shock_fade_entries(day_rth, atr14=atr14)
            for s in sigs:
                out = sim.simulate_outcome(day_rth, s)
                if out["outcome"] in ("no_data", "invalid_risk"):
                    continue
                row = {**s, **out, **_net({**s, **out}, assumed_spread_pct),
                       "symbol": sym, "et_date": str(d)}
                trades.append(row)

    by_strategy = {}
    for strat in ("stocks_in_play_orb", "shock_fade"):
        by_strategy[strat] = _agg([t for t in trades if t["strategy"] == strat])
    overall = _agg(trades)

    return {
        "generated_at": int(time.time()),
        "days": days, "profile": profile, "symbols_used": syms_used,
        "assumed_spread_pct": assumed_spread_pct,
        "by_strategy": by_strategy,
        "overall": overall,
        "n_trades": len(trades),
        "sample_trades": sorted(trades, key=lambda t: t["et_date"], reverse=True)[:40],
        "caveats": [
            f"Spread is ASSUMED at {assumed_spread_pct}% (no historical NBBO) — the research says "
            "the spread is what kills these trades, so net numbers are an OPTIMISTIC upper bound.",
            "Slippage / commission / borrow are modeled defaults, not real fills.",
            f"~{days} trading days is a single market regime, not a robustness test.",
            "Universe = today's liquid movers (mild look-ahead in name selection).",
            "Educational, not advice — and most retail day-trading is net-losing.",
        ],
    }


_CACHE: dict = {"at": 0.0, "key": None, "data": None}


def get_backtest(days: int = 20, profile: str = "aggressive", force: bool = False) -> dict:
    now = time.time()
    key = (days, profile)
    if not force and _CACHE["data"] is not None and _CACHE["key"] == key and (now - _CACHE["at"]) < _TTL_SEC:
        return _CACHE["data"]
    data = run_backtest(days=days, profile=profile)
    _CACHE.update(at=now, key=key, data=data)
    return data
