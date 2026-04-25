"""Sell-signal detector — "material change in character".

Book Ch 12-13 distills the exits:
  1. Largest 1-day %-decline since the Stage 2 advance began.
  2. Largest 1-week %-decline since the Stage 2 advance began.
  3. Close below 50-MA on above-average volume.
  4. Climax run: +25% in 1-3 weeks (parabolic blow-off).
  5. Close below 200-MA (trend break — full exit).
  6. Stop-loss breached (caller supplies entry + stop).
"""
from __future__ import annotations

from typing import Optional
import pandas as pd


def evaluate(df: pd.DataFrame, stage2_start_idx: Optional[int] = None,
             entry_price: Optional[float] = None,
             stop_price: Optional[float] = None) -> Optional[dict]:
    if df is None or len(df) < 60:
        return None
    c = df["close"]
    v = df["volume"]
    price = float(c.iloc[-1])
    ma50 = c.rolling(50).mean()
    ma200 = c.rolling(200).mean()
    vol_avg50 = float(v.iloc[-50:].mean())

    # Daily + weekly returns
    daily = c.pct_change()
    weekly = c.pct_change(5)

    # Stage 2 window defaults to last 252 bars if not provided
    start = stage2_start_idx if stage2_start_idx is not None else max(0, len(c) - 252)
    daily_in = daily.iloc[start:]
    weekly_in = weekly.iloc[start:]
    today_daily = float(daily.iloc[-1]) if not pd.isna(daily.iloc[-1]) else 0.0
    today_weekly = float(weekly.iloc[-1]) if not pd.isna(weekly.iloc[-1]) else 0.0

    largest_down_1d = float(daily_in.min()) if len(daily_in) else 0
    largest_down_1w = float(weekly_in.min()) if len(weekly_in) else 0
    new_biggest_1d = today_daily <= largest_down_1d + 1e-9 and today_daily < 0
    new_biggest_1w = today_weekly <= largest_down_1w + 1e-9 and today_weekly < 0

    last_vol = float(v.iloc[-1])
    below_50 = price < float(ma50.iloc[-1]) if not pd.isna(ma50.iloc[-1]) else False
    below_50_on_vol = below_50 and vol_avg50 > 0 and last_vol > 1.3 * vol_avg50
    below_200 = price < float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else False

    # Climax run: +25% in last 15 bars
    climax_window = c.iloc[-15:]
    climax_gain = (float(climax_window.iloc[-1]) / float(climax_window.iloc[0]) - 1) * 100 if len(climax_window) else 0
    climax = climax_gain >= 25

    stop_hit = bool(stop_price and price <= stop_price)
    entry_protection = bool(entry_price and price < entry_price and (entry_price - price) / entry_price > 0.1)

    signals = {
        "largest_1d_decline_since_stage2": new_biggest_1d,
        "largest_1w_decline_since_stage2": new_biggest_1w,
        "close_below_50ma_on_high_vol": below_50_on_vol,
        "close_below_200ma": below_200,
        "climax_run_25pct_in_3w": climax,
        "stop_loss_breached": stop_hit,
        "down_10pct_from_entry": entry_protection,
    }
    severity = sum(1 for v in signals.values() if v)
    action = "HOLD"
    if signals["close_below_200ma"] or signals["stop_loss_breached"]:
        action = "FULL_EXIT"
    elif severity >= 2 or signals["close_below_50ma_on_high_vol"] or signals["climax_run_25pct_in_3w"]:
        action = "REDUCE"
    elif severity >= 1:
        action = "TIGHTEN_STOP"

    return {
        "signals": signals,
        "severity": severity,
        "action": action,
        "today_1d_return_pct": round(today_daily * 100, 2),
        "today_1w_return_pct": round(today_weekly * 100, 2),
        "largest_1d_down_pct_stage2": round(largest_down_1d * 100, 2),
        "largest_1w_down_pct_stage2": round(largest_down_1w * 100, 2),
        "climax_15d_gain_pct": round(climax_gain, 2),
    }
