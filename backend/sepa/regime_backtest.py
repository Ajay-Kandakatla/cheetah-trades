"""Backtest the market regime classifier.

For each trading day in the lookback window, recompute the regime label
using only data available *as of that day* (no look-ahead). Then measure
forward 1-week / 1-month / 3-month SPY returns conditional on the label.

Honest accuracy metrics:
  - Hit rate: when label was 'confirmed_uptrend', what % of forward
    20-trading-day SPY returns were positive?
  - Mean / median forward return per label
  - Worst forward drawdown experienced while in each regime
  - Comparison vs buy-and-hold

Run as a script:
    python -m sepa.regime_backtest --years 10
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from .market_regime import regime_for_date
from .prices import load_prices
from . import symbols

log = logging.getLogger("sepa.regime_backtest")


def _load_vix() -> Optional[pd.DataFrame]:
    """yfinance fallback for VIX history (massive doesn't carry indices)."""
    try:
        import yfinance as yf
        t = symbols.yf_ticker("^VIX")
        df = t.history(period="max")
        if df.empty:
            return None
        df = df.rename(columns={"Open": "open", "High": "high", "Low": "low",
                                 "Close": "close", "Volume": "volume"})
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df[["open", "high", "low", "close", "volume"]]
    except Exception as exc:
        log.warning("VIX load failed: %s", exc)
        return None


def _load_index(symbol: str) -> Optional[pd.DataFrame]:
    """Try the project's load_prices first, then fall back to yfinance for
    long history. The 2y default in load_prices isn't enough for backtest."""
    try:
        import yfinance as yf
        t = symbols.yf_ticker(symbol)
        df = t.history(period="max")
        if df.empty:
            df = load_prices(symbol, period="10y")
            return df
        df = df.rename(columns={"Open": "open", "High": "high", "Low": "low",
                                 "Close": "close", "Volume": "volume"})
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df[["open", "high", "low", "close", "volume"]]
    except Exception as exc:
        log.warning("%s yfinance load failed: %s — falling back to load_prices", symbol, exc)
        return load_prices(symbol, period="10y")


def run_backtest(years: int = 10, sample_every: int = 1) -> dict:
    """Backtest over the last `years`. Sampled every `sample_every` trading days
    (set to 5 for weekly samples — much faster, similar accuracy)."""
    df_spy = _load_index("SPY")
    df_qqq = _load_index("QQQ")
    df_vix = _load_vix()

    if df_spy is None:
        return {"error": "could not load SPY history"}

    cutoff = df_spy.index[-1] - pd.DateOffset(years=years)
    eligible = df_spy.index[(df_spy.index >= cutoff) & (df_spy.index <= df_spy.index[-1])]
    eligible = eligible[::sample_every]

    rows = []
    for i, dt in enumerate(eligible):
        r = regime_for_date(dt, df_spy, df_qqq, df_vix)
        if r is None:
            continue
        # Forward returns
        try:
            today_close = float(df_spy.loc[dt, "close"])
        except (KeyError, ValueError):
            continue
        idx_pos = df_spy.index.get_loc(dt)
        for horizon, days in [("fwd_5d", 5), ("fwd_20d", 20), ("fwd_60d", 60)]:
            future_pos = idx_pos + days
            if future_pos < len(df_spy):
                future_close = float(df_spy["close"].iloc[future_pos])
                r[horizon] = round((future_close / today_close - 1) * 100, 3)
            else:
                r[horizon] = None
        # Forward drawdown over the next 20 days (peak-to-trough from today)
        future_slice = df_spy["close"].iloc[idx_pos:idx_pos + 21]
        if len(future_slice) > 1:
            run_max = future_slice.cummax()
            dd = (future_slice / run_max - 1) * 100
            r["fwd_20d_max_drawdown"] = round(float(dd.min()), 3)
        else:
            r["fwd_20d_max_drawdown"] = None
        rows.append(r)

    df = pd.DataFrame(rows)
    if df.empty:
        return {"error": "no usable rows"}

    # Aggregate per label
    aggregates = {}
    for label in ["confirmed_uptrend", "uptrend_under_pressure", "market_in_correction"]:
        sub = df[df["label"] == label]
        if len(sub) == 0:
            continue
        aggregates[label] = {
            "n_days": int(len(sub)),
            "share_of_time": round(len(sub) / len(df) * 100, 1),
            "fwd_5d_mean":  round(float(sub["fwd_5d"].mean(skipna=True)), 3) if "fwd_5d" in sub else None,
            "fwd_5d_median": round(float(sub["fwd_5d"].median(skipna=True)), 3) if "fwd_5d" in sub else None,
            "fwd_5d_hit_rate":  round(float((sub["fwd_5d"] > 0).mean() * 100), 1) if "fwd_5d" in sub else None,
            "fwd_20d_mean":  round(float(sub["fwd_20d"].mean(skipna=True)), 3) if "fwd_20d" in sub else None,
            "fwd_20d_median": round(float(sub["fwd_20d"].median(skipna=True)), 3) if "fwd_20d" in sub else None,
            "fwd_20d_hit_rate":  round(float((sub["fwd_20d"] > 0).mean() * 100), 1) if "fwd_20d" in sub else None,
            "fwd_60d_mean":  round(float(sub["fwd_60d"].mean(skipna=True)), 3) if "fwd_60d" in sub else None,
            "fwd_60d_hit_rate":  round(float((sub["fwd_60d"] > 0).mean() * 100), 1) if "fwd_60d" in sub else None,
            "worst_20d_drawdown": round(float(sub["fwd_20d_max_drawdown"].min(skipna=True)), 3) if "fwd_20d_max_drawdown" in sub else None,
            "median_20d_drawdown": round(float(sub["fwd_20d_max_drawdown"].median(skipna=True)), 3) if "fwd_20d_max_drawdown" in sub else None,
        }

    # Buy-and-hold baseline over the same window
    bh_start = float(df_spy.loc[eligible[0], "close"])
    bh_end = float(df_spy.loc[eligible[-1], "close"])
    bh_total = (bh_end / bh_start - 1) * 100

    # Naive long-only strategy: buy when label != market_in_correction, exit otherwise.
    # 20-day forward return as the realized P&L per signal day (overlapping, indicative).
    long_mask = df["label"] != "market_in_correction"
    if long_mask.sum() > 0:
        avg_long_fwd = float(df.loc[long_mask, "fwd_20d"].mean(skipna=True))
    else:
        avg_long_fwd = 0.0
    avg_correction_fwd = float(df.loc[~long_mask, "fwd_20d"].mean(skipna=True)) if (~long_mask).sum() > 0 else 0.0

    summary = {
        "window_years": years,
        "sample_every_n_days": sample_every,
        "total_observations": len(df),
        "from": str(df["date"].iloc[0]),
        "to": str(df["date"].iloc[-1]),
        "buy_and_hold_total_return_pct": round(bh_total, 2),
        "by_label": aggregates,
        "long_when_not_correction": {
            "avg_fwd_20d_return_pct": round(avg_long_fwd, 3),
            "n_signals": int(long_mask.sum()),
        },
        "correction_window_avg_fwd_20d": {
            "avg_fwd_20d_return_pct": round(avg_correction_fwd, 3),
            "n_signals": int((~long_mask).sum()),
        },
    }
    return {"summary": summary, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--sample-every", type=int, default=5,
                    help="sample every N trading days (5 = weekly; faster, similar accuracy)")
    ap.add_argument("--out", default="regime_backtest.json")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
    print(f"Running backtest: {args.years}y, sample every {args.sample_every}d ...")
    result = run_backtest(years=args.years, sample_every=args.sample_every)

    out = Path(args.out)
    out.write_text(json.dumps(result, indent=2, default=str))

    s = result.get("summary", {})
    if not s:
        print("ERROR:", result.get("error"))
        return

    print()
    print(f"Window: {s['from']} → {s['to']}  ({s['total_observations']} samples)")
    print(f"Buy-and-hold SPY return: {s['buy_and_hold_total_return_pct']}%")
    print()
    print(f"{'Label':<28} {'%time':>7} {'fwd5d_hit':>10} {'fwd20d_hit':>11} {'fwd20d_mean':>12} {'worst_dd':>10}")
    print("-" * 82)
    for label, agg in s.get("by_label", {}).items():
        print(f"{label:<28} {agg['share_of_time']:>6}% {agg['fwd_5d_hit_rate']:>9}% {agg['fwd_20d_hit_rate']:>10}% {agg['fwd_20d_mean']:>11}% {agg['worst_20d_drawdown']:>9}%")
    print()
    print(f"Long when label != correction: avg fwd 20d = {s['long_when_not_correction']['avg_fwd_20d_return_pct']}% ({s['long_when_not_correction']['n_signals']} signals)")
    print(f"Sit-out (correction): avg fwd 20d = {s['correction_window_avg_fwd_20d']['avg_fwd_20d_return_pct']}% ({s['correction_window_avg_fwd_20d']['n_signals']} signals)")
    print()
    print(f"Full output: {out}")


if __name__ == "__main__":
    main()
