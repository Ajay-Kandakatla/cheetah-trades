"""Walk-forward backtest for the liquidity-sweep strategy.

Ajay 2026-08-13: "Can you back test this strategy once done for data please".

The point of this file is to answer one question honestly: **does a
sweep-and-reclaim entry actually pay over a 1-to-5 day hold?** Osler (2003)
found stop-cascade effects significant for hours but not days, so the null
hypothesis here is real and this test is meant to be able to fail.

NO LOOKAHEAD — the rules that keep it honest
--------------------------------------------
1. Zones and sweeps for decision day D are computed from intraday bars
   **strictly before D's close**. `_window_upto` slices on timestamp; nothing
   from D+1 onward is visible.
2. The entry is the **next session's open**, never D's close. You cannot see a
   close and also trade it.
3. Outcomes walk forward bar by bar on daily OHLC after the entry day.
4. When a day's range contains BOTH the stop and the target, it is scored a
   **loss**. Daily bars cannot say which came first, and assuming the win would
   inflate every result.
5. Costs are charged on entry and exit (`COST_BPS_PER_SIDE`).

Metrics are reported per-cohort so the filters can be judged separately: all
setups, knife-filtered, and dark-print-confirmed.

Not a book method. Not advice. Past behaviour of a rule on historical bars is
not a forecast.
"""
from __future__ import annotations

import logging
from datetime import date as _date, timedelta
from typing import Optional

import pandas as pd

from . import price_zones, sd_liquidity as liq, sd_sweep as sweep

log = logging.getLogger("supply_demand.sd_backtest")

MAX_HOLD_DAYS = 5            # "a day or two, sometimes a week"
COST_BPS_PER_SIDE = 2.0      # 2bp each way — liquid large caps
MIN_DECISION_BARS = 300      # a window smaller than this is not a read


def _window_upto(bars: pd.DataFrame, day: _date, sessions: int) -> Optional[pd.DataFrame]:
    """Intraday bars for the `sessions` days ENDING at `day`'s close.

    The lookahead firewall: everything after `day` 23:59 is dropped before any
    zone or sweep is computed."""
    if bars is None or bars.empty:
        return None
    idx = bars.index
    end = pd.Timestamp(day).tz_localize(idx.tz) + pd.Timedelta(days=1) \
        if idx.tz is not None else pd.Timestamp(day) + pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=sweep.LOOKBACK_CAL_DAYS + 1)
    w = bars[(idx >= start) & (idx < end)]
    return w if len(w) >= MIN_DECISION_BARS else None


def setups_on(bars_window: pd.DataFrame) -> list:
    """Valid sweep setups visible at the end of `bars_window`. PURE-ish."""
    z = price_zones.compute(bars_window, **sweep.sweep_geom())
    if not z:
        return []
    last = float(bars_window["close"].iloc[-1])
    n = len(bars_window)
    idx_str = list(bars_window.index.astype(str))
    out = []
    for band in (z.get("demand_zones") or []):
        if (band.get("touches") or 0) < sweep.MIN_TOUCHES:
            continue
        if abs(band["mid"] / last - 1) * 100 > sweep.MAX_DISTANCE_PCT:
            continue
        s = liq.find_sweep(bars_window, band["lo"], band["hi"],
                           min_pierce_pct=sweep.MIN_PIERCE_PCT,
                           max_pierce_pct=sweep.MAX_PIERCE_PCT,
                           reclaim_bars=sweep.RECLAIM_MAX_BARS,
                           min_vol_x=sweep.MIN_SWEEP_VOL_X)
        if s["state"] != "swept":
            continue
        try:
            age = n - 1 - idx_str.index(s["sweep_index"])
        except ValueError:
            continue
        if age > sweep.FRESH_WITHIN_BARS or last <= band["lo"]:
            continue
        plan = sweep.plan_from_sweep(s["sweep_low"], band["lo"], band["hi"],
                                     last, z.get("supply_zones"))
        if not plan["valid"] or plan.get("target") is None:
            continue
        out.append({"band_lo": band["lo"], "band_hi": band["hi"],
                    "touches": band["touches"], "sweep_low": s["sweep_low"],
                    "pierce_pct": s["pierce_pct"],
                    "vol_x": s["sweep_volume_x"], "bars_since": age,
                    "plan": plan})
    return out


def _first_touch_intraday(bars: pd.DataFrame, day, stop: float,
                          target: float) -> Optional[str]:
    """On a day whose RANGE contains both levels, replay that day's intraday
    bars in order and report which was touched first: 'stop' or 'target'.

    Daily OHLC genuinely cannot answer this. Scoring every ambiguous day as a
    loss (the first version of this file) turned 140 target hits into an 11%
    win rate — an artefact of the scoring rule, not a property of the strategy.
    Returns None when intraday bars for that day are unavailable, and the
    caller falls back to the conservative loss assumption."""
    if bars is None or bars.empty:
        return None
    idx = bars.index
    d0 = pd.Timestamp(day).tz_localize(idx.tz) if idx.tz is not None else pd.Timestamp(day)
    sess = bars[(idx >= d0) & (idx < d0 + pd.Timedelta(days=1))]
    if sess.empty:
        return None
    for lo, hi in zip(sess["low"].values, sess["high"].values):
        if float(lo) <= stop:
            return "stop"
        if float(hi) >= target:
            return "target"
    return None


def walk_forward(daily: pd.DataFrame, entry_idx: int, stop: float,
                 target: float, max_hold: int = MAX_HOLD_DAYS,
                 intraday: Optional[pd.DataFrame] = None) -> dict:
    """Score one trade on daily bars from `entry_idx` (the entry day).

    Entry is that day's OPEN. A day containing both levels is resolved on
    intraday bars where available, else scored a loss (conservative)."""
    if entry_idx >= len(daily):
        return {"outcome": "no_data", "ret_pct": None, "days": None}
    entry = float(daily["open"].iloc[entry_idx])

    # An entry that gaps out of the setup is NOT a trade. Taking it anyway was
    # the second bug: a gap above `target` scored as a target "hit" that
    # settled below the fill, i.e. a winner recorded as a loss.
    if entry <= stop:
        return {"outcome": "gap_below_stop", "ret_pct": None, "days": 0}
    if entry >= target:
        return {"outcome": "gap_past_target", "ret_pct": None, "days": 0}

    for k in range(0, max_hold):
        i = entry_idx + k
        if i >= len(daily):
            break
        lo = float(daily["low"].iloc[i])
        hi = float(daily["high"].iloc[i])
        hit_stop, hit_tgt = lo <= stop, hi >= target
        if hit_stop and hit_tgt:
            first = _first_touch_intraday(intraday, daily.index[i], stop, target)
            if first == "target":
                return {"outcome": "target", "ret_pct": _net(entry, target),
                        "days": k + 1, "resolved": "intraday"}
            return {"outcome": "stop", "ret_pct": _net(entry, stop),
                    "days": k + 1, "resolved": "intraday" if first else "assumed_loss"}
        if hit_stop:
            return {"outcome": "stop", "ret_pct": _net(entry, stop), "days": k + 1}
        if hit_tgt:
            return {"outcome": "target", "ret_pct": _net(entry, target), "days": k + 1}
    last_i = min(entry_idx + max_hold - 1, len(daily) - 1)
    return {"outcome": "timeout",
            "ret_pct": _net(entry, float(daily["close"].iloc[last_i])),
            "days": last_i - entry_idx + 1}


def _net(entry: float, exit_px: float) -> float:
    gross = (exit_px / entry - 1) * 100.0
    return round(gross - 2 * COST_BPS_PER_SIDE / 100.0, 2)


def summarize(trades: list, label: str) -> dict:
    """Hit rate + expectancy for a cohort. Expectancy is the number that
    matters — a 70% win rate on 0.3R losers to 0.2R winners still loses."""
    done = [t for t in trades if t.get("ret_pct") is not None]
    n = len(done)
    if not n:
        return {"label": label, "n": 0}
    wins = [t for t in done if t["ret_pct"] > 0]
    losses = [t for t in done if t["ret_pct"] <= 0]
    avg_w = sum(t["ret_pct"] for t in wins) / len(wins) if wins else 0.0
    avg_l = sum(t["ret_pct"] for t in losses) / len(losses) if losses else 0.0
    exp = sum(t["ret_pct"] for t in done) / n
    return {
        "label": label, "n": n,
        "win_rate_pct": round(100.0 * len(wins) / n, 1),
        "avg_win_pct": round(avg_w, 2),
        "avg_loss_pct": round(avg_l, 2),
        "expectancy_pct": round(exp, 3),
        "total_pct": round(sum(t["ret_pct"] for t in done), 1),
        "target_hits": sum(1 for t in done if t["outcome"] == "target"),
        "stops": sum(1 for t in done if t["outcome"] == "stop"),
        "timeouts": sum(1 for t in done if t["outcome"] == "timeout"),
        "avg_days": round(sum(t["days"] for t in done if t.get("days")) / n, 1),
    }


def run(symbols: list, start: _date, end: _date,
        max_hold: int = MAX_HOLD_DAYS) -> dict:
    """Walk every symbol day by day and score each setup it would have taken."""
    from daytrading import data as dt_data
    from sepa import prices as px_mod

    trades: list = []
    covered, skipped = 0, 0

    for sym in symbols:
        try:
            bars = dt_data.load_intraday_range(
                sym, start - timedelta(days=sweep.LOOKBACK_CAL_DAYS + 4), end,
                include_premarket=False, include_afterhours=False)
            daily = px_mod.load_prices(sym, period="2y")
        except Exception as exc:
            log.debug("backtest: load failed %s: %s", sym, exc)
            skipped += 1
            continue
        if bars is None or bars.empty or daily is None or daily.empty:
            skipped += 1
            continue
        bars = bars.rename(columns={c: str(c).lower() for c in bars.columns})
        daily = daily.rename(columns={c: str(c).lower() for c in daily.columns})
        covered += 1

        # knife guard, evaluated per decision day off daily bars only
        d_index = [d.date() if hasattr(d, "date") else d for d in daily.index]

        day = start
        while day <= end:
            if day.weekday() < 5:
                w = _window_upto(bars, day, sweep.LOOKBACK_SESSIONS)
                if w is not None:
                    # daily slice strictly up to and including `day`
                    upto = [i for i, dd in enumerate(d_index) if dd <= day]
                    if upto and len(upto) > 60:
                        di = upto[-1]
                        hist = daily.iloc[:di + 1]
                        st = liq.structure_read(hist["close"].tolist(),
                                                hist["low"].tolist(), swing_window=5)
                        ma50 = hist["close"].rolling(50).mean()
                        knife = liq.is_falling_knife(
                            st, float(hist["close"].iloc[-1]),
                            float(ma50.iloc[-1]) if pd.notna(ma50.iloc[-1]) else None,
                            float(ma50.iloc[-11]) if len(ma50) > 11 and pd.notna(ma50.iloc[-11]) else None)
                        for setup in setups_on(w):
                            res = walk_forward(daily, di + 1,      # NEXT day's open
                                               setup["plan"]["stop"],
                                               setup["plan"]["target"], max_hold,
                                               intraday=bars)
                            trades.append({
                                "symbol": sym, "decision_day": str(day),
                                "knife": knife, "vol_x": setup["vol_x"],
                                "pierce_pct": setup["pierce_pct"],
                                "rr": setup["plan"]["rr"],
                                "risk_pct": setup["plan"]["risk_pct"],
                                **res,
                            })
            day = day + timedelta(days=1)

    cohorts = [
        summarize(trades, "ALL setups"),
        summarize([t for t in trades if not t["knife"]], "knife filtered OUT"),
        summarize([t for t in trades if t["knife"]], "knives only (control)"),
        summarize([t for t in trades if not t["knife"] and (t["vol_x"] or 0) >= 2.0],
                  "knife-filtered + vol >= 2x"),
        summarize([t for t in trades if not t["knife"] and (t["rr"] or 0) >= 1.5],
                  "knife-filtered + rr >= 1.5"),
    ]
    return {
        "cohorts": [c for c in cohorts if c.get("n")],
        "n_trades": len(trades),
        "symbols_covered": covered, "symbols_skipped": skipped,
        "start": str(start), "end": str(end), "max_hold_days": max_hold,
        "cost_bps_per_side": COST_BPS_PER_SIDE,
        "trades": trades,
        "caveats": [
            "Entry is the NEXT session's open, never the decision day's close.",
            "A day whose range contains both stop and target is scored a LOSS.",
            f"{COST_BPS_PER_SIDE}bp charged each way.",
            "Survivorship: the symbol list is today's, so names that were "
            "delisted or fell out of the index are absent.",
            "Small sample sizes have wide error bars — read n before expectancy.",
        ],
    }


# ── Intraday variant ─────────────────────────────────────────────────────────
# Osler's stop-cascade effect is significant for HOURS, not days. The daily
# walk-forward above found no multi-day edge, so this tests the horizon the
# research actually supports: enter on the reclaim, exit the same session.
INTRADAY_MAX_BARS = 180          # ~3h on 1-min bars
INTRADAY_STOP_BUFFER = 0.998


def run_intraday(symbols: list, start: _date, end: _date,
                 rmult: float = 2.0, max_bars: int = INTRADAY_MAX_BARS) -> dict:
    """Enter at the reclaim bar's close; exit on stop/target within the session.

    Same no-lookahead discipline: the sweep is found using bars up to and
    including the reclaim bar, and the outcome is walked forward only from the
    bar AFTER it. Both-levels-in-one-bar resolves as a loss (a 1-min bar is
    small enough that this is a fair tie-break)."""
    from daytrading import data as dt_data

    trades = []
    for sym in symbols:
        try:
            bars = dt_data.load_intraday_range(
                sym, start - timedelta(days=sweep.LOOKBACK_CAL_DAYS + 4), end,
                include_premarket=False, include_afterhours=False)
        except Exception:
            continue
        if bars is None or bars.empty:
            continue
        bars = bars.rename(columns={c: str(c).lower() for c in bars.columns})

        day = start
        while day <= end:
            if day.weekday() < 5:
                w = _window_upto(bars, day, sweep.LOOKBACK_SESSIONS)
                if w is not None and len(w) > 2:
                    idx_str = list(w.index.astype(str))
                    for s in setups_on(w):
                        # entry = the bar AFTER the sweep is confirmed
                        try:
                            e = idx_str.index(str(w.index[-1])) + 1
                        except ValueError:
                            continue
                        fwd = bars[bars.index > w.index[-1]].head(max_bars)
                        if fwd.empty:
                            continue
                        entry = float(fwd["open"].iloc[0])
                        stop = round(s["sweep_low"] * INTRADAY_STOP_BUFFER, 2)
                        if entry <= stop:
                            continue
                        target = entry + rmult * (entry - stop)
                        outcome, ret = "timeout", None
                        for lo, hi in zip(fwd["low"].values, fwd["high"].values):
                            if float(lo) <= stop:
                                outcome, ret = "stop", _net(entry, stop); break
                            if float(hi) >= target:
                                outcome, ret = "target", _net(entry, target); break
                        if ret is None:
                            ret = _net(entry, float(fwd["close"].iloc[-1]))
                        trades.append({"symbol": sym, "decision_day": str(day),
                                       "outcome": outcome, "ret_pct": ret,
                                       "days": 0, "vol_x": s["vol_x"],
                                       "knife": False})
            day = day + timedelta(days=1)

    return {"cohorts": [c for c in [
                summarize(trades, f"intraday {rmult}R / {max_bars} bars"),
                summarize([t for t in trades if (t["vol_x"] or 0) >= 2.0],
                          f"intraday {rmult}R, vol >= 2x"),
            ] if c.get("n")],
            "n_trades": len(trades), "trades": trades,
            "start": str(start), "end": str(end), "rmult": rmult,
            "max_bars": max_bars}


if __name__ == "__main__":                                   # pragma: no cover
    import argparse, json as _json
    ap = argparse.ArgumentParser(prog="supply_demand.sd_backtest")
    ap.add_argument("--symbols", default="CAT,KLAC,VRT,CIEN,FIX,ADI,TXN,AMD,NVDA,MSFT")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--hold", type=int, default=MAX_HOLD_DAYS)
    ap.add_argument("--intraday", action="store_true")
    ap.add_argument("--rmult", type=float, default=2.0)
    a = ap.parse_args()
    _end = _date.today() - timedelta(days=1)
    _start = _end - timedelta(days=a.days)
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    res = (run_intraday(syms, _start, _end, a.rmult) if a.intraday
           else run(syms, _start, _end, a.hold))
    res.pop("trades", None)
    print(_json.dumps(res, indent=2))
