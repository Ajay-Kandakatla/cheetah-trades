"""Walk-forward backtest for day-trading strategies.

For each historical trading day in the lookback window:
  1. Load 1m bars (premarket + RTH).
  2. Run signal detector — get entry signals.
  3. Simulate each trade using only intraday bars (no look-ahead).
  4. Record outcome: stop / target / eod-flat, P&L %, R-multiple.

Aggregate stats:
  - Win rate
  - Average P&L per trade
  - R-expectancy (avg R-multiple = win_rate*avg_win_R - loss_rate*1.0)
  - Profit factor (sum wins / sum losses)
  - Max drawdown across consecutive trades
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd

from .data import load_intraday, trading_days_back
from .signals import orb, gap_and_go, bull_flag, vwap_reversion, momentum_failure


SIGNAL_REGISTRY = {
    "orb": orb,
    "gap_and_go": gap_and_go,
    "bull_flag": bull_flag,
    "vwap_reversion": vwap_reversion,
    "momentum_failure": momentum_failure,
}


def backtest_symbol(symbol: str, days: int = 30, strategy: str = "orb",
                    detect_kwargs: Optional[dict] = None) -> dict:
    """Walk-forward backtest a single symbol over the last `days` trading days."""
    mod = SIGNAL_REGISTRY.get(strategy)
    if mod is None:
        return {"error": f"unknown strategy: {strategy}"}
    detect_kwargs = detect_kwargs or {}

    sessions = trading_days_back(days)
    trades = []
    days_with_signal = 0
    days_evaluated = 0

    for d in sessions:
        df = load_intraday(symbol, d, include_premarket=True, include_afterhours=False)
        if df is None or df.empty:
            continue
        days_evaluated += 1
        signals = mod.detect(df, **detect_kwargs)
        if signals:
            days_with_signal += 1
        for sig in signals:
            outcome = mod.simulate_outcome(df, sig)
            trades.append({**sig, **outcome, "et_date": str(d)})

    if not trades:
        return {
            "symbol": symbol,
            "strategy": strategy,
            "days_evaluated": days_evaluated,
            "days_with_signal": 0,
            "n_trades": 0,
            "trades": [],
            "stats": {"note": "no trades fired in this window"},
        }

    # Aggregate
    df_t = pd.DataFrame(trades)
    n = len(df_t)
    wins = df_t[df_t["r_multiple"] > 0]
    losses = df_t[df_t["r_multiple"] < 0]
    win_rate = len(wins) / n * 100
    avg_pnl = float(df_t["pnl_pct"].mean())
    avg_win_pnl = float(wins["pnl_pct"].mean()) if len(wins) else 0.0
    avg_loss_pnl = float(losses["pnl_pct"].mean()) if len(losses) else 0.0
    avg_r = float(df_t["r_multiple"].mean())
    expectancy = avg_r  # R-expectancy
    sum_wins = float(wins["pnl_pct"].sum()) if len(wins) else 0.0
    sum_losses = abs(float(losses["pnl_pct"].sum())) if len(losses) else 0.0
    profit_factor = sum_wins / sum_losses if sum_losses > 0 else (float("inf") if sum_wins > 0 else 0.0)

    # Sequential max drawdown (in % equity if 1% risked per trade)
    pnl_seq = df_t["pnl_pct"].cumsum()
    rolling_max = pnl_seq.cummax()
    drawdown = (pnl_seq - rolling_max).min()

    # Outcome breakdown
    outcome_counts = df_t["outcome"].value_counts().to_dict()

    # Side breakdown
    side_stats = {}
    for side in df_t["side"].unique():
        sub = df_t[df_t["side"] == side]
        side_stats[side] = {
            "n": len(sub),
            "win_rate_pct": round(float((sub["r_multiple"] > 0).mean() * 100), 1),
            "avg_r": round(float(sub["r_multiple"].mean()), 3),
        }

    return {
        "symbol": symbol,
        "strategy": strategy,
        "days_evaluated": days_evaluated,
        "days_with_signal": days_with_signal,
        "trigger_rate_pct": round(days_with_signal / days_evaluated * 100, 1) if days_evaluated else 0.0,
        "n_trades": n,
        "stats": {
            "win_rate_pct": round(win_rate, 1),
            "avg_pnl_pct": round(avg_pnl, 3),
            "avg_win_pnl_pct": round(avg_win_pnl, 3),
            "avg_loss_pnl_pct": round(avg_loss_pnl, 3),
            "avg_r_multiple": round(avg_r, 3),
            "r_expectancy": round(expectancy, 3),
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else None,
            "max_consecutive_drawdown_pct": round(float(drawdown), 3),
            "outcome_counts": outcome_counts,
            "by_side": side_stats,
        },
        "trades": df_t.to_dict(orient="records"),
    }


def backtest_universe(symbols: list[str], days: int = 30, strategy: str = "orb") -> dict:
    """Run backtest across a universe of symbols, aggregate."""
    per_symbol = {}
    all_trades = []
    for s in symbols:
        r = backtest_symbol(s, days=days, strategy=strategy)
        per_symbol[s] = {k: v for k, v in r.items() if k != "trades"}
        all_trades.extend(r.get("trades", []))

    if not all_trades:
        return {
            "strategy": strategy,
            "days": days,
            "symbols": symbols,
            "per_symbol": per_symbol,
            "aggregate": {"n_trades": 0},
        }

    import pandas as pd
    df = pd.DataFrame(all_trades)
    n = len(df)
    wins = df[df["r_multiple"] > 0]
    losses = df[df["r_multiple"] < 0]

    return {
        "strategy": strategy,
        "days": days,
        "symbols": symbols,
        "per_symbol": per_symbol,
        "aggregate": {
            "n_trades": n,
            "win_rate_pct": round(float((df["r_multiple"] > 0).mean() * 100), 1),
            "avg_pnl_pct": round(float(df["pnl_pct"].mean()), 3),
            "avg_r_multiple": round(float(df["r_multiple"].mean()), 3),
            "profit_factor": round(float(wins["pnl_pct"].sum() / abs(losses["pnl_pct"].sum())), 2) if len(losses) else None,
        },
    }


if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="SPY")
    ap.add_argument("--symbols", default="", help="comma-separated symbols (overrides --symbol)")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--strategy", default="orb")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.symbols:
        syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
        result = backtest_universe(syms, days=args.days, strategy=args.strategy)
    else:
        result = backtest_symbol(args.symbol, days=args.days, strategy=args.strategy)

    if args.out:
        with open(args.out, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"Wrote {args.out}")

    if "stats" in result:
        s = result["stats"]
        print(f"\n{result['symbol']} · {result['strategy']} · {result['days_evaluated']} days")
        print(f"  Trades: {result['n_trades']}  ({result['days_with_signal']} signal-days, trigger rate {result.get('trigger_rate_pct')}%)")
        print(f"  Win rate: {s.get('win_rate_pct')}%")
        print(f"  Avg P&L: {s.get('avg_pnl_pct')}%   Avg R: {s.get('avg_r_multiple')}")
        print(f"  Profit factor: {s.get('profit_factor')}")
        print(f"  Max drawdown: {s.get('max_consecutive_drawdown_pct')}% (cumulative %, not capital)")
        print(f"  Outcomes: {s.get('outcome_counts')}")
        print(f"  By side: {s.get('by_side')}")
    elif "aggregate" in result:
        a = result["aggregate"]
        print(f"\nUniverse: {len(result['symbols'])} symbols · {result['days']} days · {result['strategy']}")
        print(f"  Trades: {a.get('n_trades')}  Win rate: {a.get('win_rate_pct')}%")
        print(f"  Avg P&L: {a.get('avg_pnl_pct')}%   Avg R: {a.get('avg_r_multiple')}")
        print(f"  Profit factor: {a.get('profit_factor')}")
        for sym, ps in result["per_symbol"].items():
            stats = ps.get("stats", {})
            print(f"    {sym:>6}  trades={ps.get('n_trades'):>3}  win={stats.get('win_rate_pct')}%  avgR={stats.get('avg_r_multiple')}")
