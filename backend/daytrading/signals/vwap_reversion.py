"""VWAP Reversion — fade extended moves back to volume-weighted average.

Pattern (Brett Steenbarger / Mike Bellafiore):
  1. Price extended ≥1.5×ATR(14) away from session VWAP.
  2. Reversal candle at the extreme (long bottom wick for long entry,
     long top wick for short entry).
  3. Next bar confirms direction (close back toward VWAP).
  4. Stop just past the extreme (low for long, high for short).
  5. Target = session VWAP.

Mean-reversion edge — works best in choppy regimes (low ATR percentile)
and on liquid names where intraday flow drives temporary dislocations.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import atr, vwap_session


def detect(df: pd.DataFrame,
           min_atr_distance: float = 1.5,
           wick_ratio: float = 1.5,        # wick/body ratio for reversal candle
           target_r_multiple: float = 1.0, # default; overridden by VWAP target
           ) -> list[dict]:
    if df is None or df.empty:
        return []
    rth = df[df["session"] == "rth"]
    if rth.empty:
        return []
    et_idx = rth.index.tz_localize("UTC").tz_convert("America/New_York")
    today = pd.Series(et_idx.date, index=rth.index).max()
    today_rth = rth[pd.Series(et_idx.date, index=rth.index) == today]
    if len(today_rth) < 30:
        return []

    vw = vwap_session(rth, session="rth")
    atr_series = atr(rth, period=14)

    signals: list[dict] = []
    fired_long = False
    fired_short = False

    # Walk bars, look for extreme + reversal candle + next-bar confirmation
    closes = today_rth["close"]
    highs = today_rth["high"]
    lows = today_rth["low"]
    opens = today_rth["open"]
    indices = today_rth.index

    for i in range(2, len(today_rth) - 1):
        if fired_long and fired_short:
            break
        ts = indices[i]
        if ts not in vw.index or ts not in atr_series.index:
            continue
        v = vw.loc[ts]
        a = atr_series.loc[ts]
        if pd.isna(v) or pd.isna(a) or a == 0:
            continue
        c = float(closes.iloc[i])
        h = float(highs.iloc[i])
        l = float(lows.iloc[i])
        o = float(opens.iloc[i])
        body = abs(c - o)
        upper_wick = h - max(c, o)
        lower_wick = min(c, o) - l
        distance = (c - v) / a  # ATR-units away from VWAP

        # Long setup: price below VWAP by >= min_atr_distance, bullish reversal
        if not fired_long and distance <= -min_atr_distance:
            # Bullish reversal: long lower wick, body bullish
            if (lower_wick >= wick_ratio * body and c >= o):
                # Confirm: next bar closes higher
                next_close = float(closes.iloc[i + 1])
                if next_close > c:
                    entry = next_close
                    stop = float(l) - 0.01
                    if entry - stop <= 0:
                        continue
                    target = float(v)  # VWAP target
                    if target <= entry:
                        continue
                    next_ts = indices[i + 1]
                    signals.append({
                        "strategy": "vwap_reversion",
                        "side": "long",
                        "entry_ts": next_ts.isoformat(),
                        "entry_price": round(entry, 4),
                        "stop": round(stop, 4),
                        "target": round(target, 4),
                        "risk_pct": round((entry - stop) / entry * 100, 3),
                        "reward_pct": round((target - entry) / entry * 100, 3),
                        "r_multiple_potential": round((target - entry) / (entry - stop), 2),
                        "atr_distance_to_vwap": round(distance, 2),
                        "vwap_at_entry": round(float(v), 4),
                        "atr14": round(float(a), 4),
                        "reasons": [
                            f"Price was {abs(distance):.1f} ATR below VWAP — extended",
                            f"Reversal candle: lower wick {lower_wick:.2f} = {lower_wick/max(body,0.01):.1f}× body",
                            f"Next bar confirmed: close {next_close:.2f} > prior close {c:.2f}",
                        ],
                    })
                    fired_long = True

        # Short setup: price above VWAP by >= min_atr_distance, bearish reversal
        if not fired_short and distance >= min_atr_distance:
            if (upper_wick >= wick_ratio * body and c <= o):
                next_close = float(closes.iloc[i + 1])
                if next_close < c:
                    entry = next_close
                    stop = float(h) + 0.01
                    if stop - entry <= 0:
                        continue
                    target = float(v)
                    if target >= entry:
                        continue
                    next_ts = indices[i + 1]
                    signals.append({
                        "strategy": "vwap_reversion",
                        "side": "short",
                        "entry_ts": next_ts.isoformat(),
                        "entry_price": round(entry, 4),
                        "stop": round(stop, 4),
                        "target": round(target, 4),
                        "risk_pct": round((stop - entry) / entry * 100, 3),
                        "reward_pct": round((entry - target) / entry * 100, 3),
                        "r_multiple_potential": round((entry - target) / (stop - entry), 2),
                        "atr_distance_to_vwap": round(distance, 2),
                        "vwap_at_entry": round(float(v), 4),
                        "atr14": round(float(a), 4),
                        "reasons": [
                            f"Price was {distance:.1f} ATR above VWAP — extended",
                            f"Reversal candle: upper wick {upper_wick:.2f} = {upper_wick/max(body,0.01):.1f}× body",
                            f"Next bar confirmed: close {next_close:.2f} < prior close {c:.2f}",
                        ],
                    })
                    fired_short = True

    return signals


def simulate_outcome(df: pd.DataFrame, signal: dict) -> dict:
    rth = df[df["session"] == "rth"]
    if rth.empty:
        return {"outcome": "no_data"}
    entry_ts = pd.Timestamp(signal["entry_ts"])
    if entry_ts.tzinfo is not None:
        entry_ts = entry_ts.tz_convert(None)
    after = rth[rth.index > entry_ts]
    entry, stop, target, side = signal["entry_price"], signal["stop"], signal["target"], signal["side"]
    risk = abs(entry - stop)
    if risk == 0:
        return {"outcome": "invalid_risk"}
    r_pot = signal.get("r_multiple_potential") or 1.0

    for ts, row in after.iterrows():
        h, l = float(row["high"]), float(row["low"])
        if side == "long":
            if l <= stop:
                return {"outcome": "stop", "exit_ts": ts.isoformat(), "exit_price": round(stop, 4),
                        "pnl_pct": round((stop / entry - 1) * 100, 3), "r_multiple": -1.0}
            if h >= target:
                return {"outcome": "target", "exit_ts": ts.isoformat(), "exit_price": round(target, 4),
                        "pnl_pct": round((target / entry - 1) * 100, 3), "r_multiple": float(r_pot)}
        else:
            if h >= stop:
                return {"outcome": "stop", "exit_ts": ts.isoformat(), "exit_price": round(stop, 4),
                        "pnl_pct": round((1 - stop / entry) * 100, 3), "r_multiple": -1.0}
            if l <= target:
                return {"outcome": "target", "exit_ts": ts.isoformat(), "exit_price": round(target, 4),
                        "pnl_pct": round((1 - target / entry) * 100, 3), "r_multiple": float(r_pot)}

    last = after.iloc[-1] if not after.empty else None
    if last is None:
        return {"outcome": "no_exit"}
    exit_price = float(last["close"])
    pl = (exit_price / entry - 1) * 100 if side == "long" else (1 - exit_price / entry) * 100
    r_mult = (exit_price - entry) / risk * (1 if side == "long" else -1)
    return {"outcome": "eod_flat", "exit_ts": last.name.isoformat(), "exit_price": round(exit_price, 4),
            "pnl_pct": round(pl, 3), "r_multiple": round(r_mult, 2)}
