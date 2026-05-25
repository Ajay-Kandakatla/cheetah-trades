"""Opening Range Breakout (ORB) — the workhorse intraday strategy.

Pattern:
  1. Mark high/low of first N minutes of RTH (default 15min).
  2. Long entry: close above ORB high on volume > avg, AFTER the ORB window.
  3. Short entry: close below ORB low on volume > avg, AFTER the ORB window.
  4. Stop: opposite end of ORB (or 1×ATR(14), whichever is tighter).
  5. Target: 1.5×ORB-range above entry (long) or below (short). Or end-of-day.

References:
  - Toby Crabel, *Day Trading with Short Term Price Patterns* (1990) — the
    original ORB framework.
  - Linda Raschke, *Street Smarts* (1995) — refined volume-confirmation rules.

Each signal dict shape:
  {
    'strategy': 'orb',
    'side': 'long' | 'short',
    'entry_ts': UTC ISO,
    'entry_price': float,
    'stop': float,
    'target': float,
    'risk_pct': float,
    'reward_pct': float,
    'r_multiple_potential': float,
    'orb_high': float, 'orb_low': float, 'orb_range_pct': float,
    'volume_ratio_at_entry': float,    # entry-bar volume / avg bar volume so far
    'reasons': [str],
  }
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ..indicators import opening_range, atr


def detect(df: pd.DataFrame,
           orb_minutes: int = 15,
           min_orb_range_pct: float = 0.15,    # ORB must span at least 0.15% of price
           max_orb_range_pct: float = 3.0,     # too-wide ORB = chop
           vol_multiplier: float = 1.2,        # entry bar volume vs avg
           target_r_multiple: float = 1.5,
           ) -> list[dict]:
    """Detect ORB entries on a single trading day's 1m bars.

    Returns list of triggered signal dicts (usually 0-2 per day per symbol).
    """
    if df is None or df.empty:
        return []
    rth = df[df["session"] == "rth"].copy()
    if rth.empty:
        return []

    # Most recent ET date in the frame
    et_idx = rth.index.tz_localize("UTC").tz_convert("America/New_York")
    et_date_series = pd.Series(et_idx.date, index=rth.index)
    most_recent = et_date_series.max()
    today_rth = rth[et_date_series == most_recent]
    if len(today_rth) < orb_minutes + 1:
        return []  # ORB window not complete

    orb = opening_range(today_rth, minutes=orb_minutes)
    if not orb or not orb["complete"]:
        return []

    orb_high = orb["high"]
    orb_low = orb["low"]
    orb_range = orb_high - orb_low
    if orb_range <= 0:
        return []
    mid_price = (orb_high + orb_low) / 2
    orb_range_pct = orb_range / mid_price * 100
    if orb_range_pct < min_orb_range_pct or orb_range_pct > max_orb_range_pct:
        return []

    # Average bar volume over the ORB window for confirmation comparison.
    orb_avg_vol = today_rth.iloc[:orb_minutes]["volume"].mean()
    if orb_avg_vol <= 0:
        return []

    # ATR for stop calculation
    atr_series = atr(rth, period=14)

    # Walk bars after the ORB window, fire on the first qualifying breakout
    after_orb = today_rth.iloc[orb_minutes:]
    signals: list[dict] = []
    long_fired = False
    short_fired = False
    for ts, row in after_orb.iterrows():
        if not long_fired and row["close"] > orb_high and row["volume"] >= vol_multiplier * orb_avg_vol:
            atr_val = float(atr_series.loc[ts]) if ts in atr_series.index and not pd.isna(atr_series.loc[ts]) else None
            entry = float(row["close"])
            stop_orb = orb_low
            stop_atr = entry - atr_val if atr_val else None
            stop = max(stop_orb, stop_atr) if stop_atr else stop_orb
            target = entry + target_r_multiple * (entry - stop)
            signals.append({
                "strategy": "orb",
                "side": "long",
                "entry_ts": ts.isoformat(),
                "entry_price": round(entry, 4),
                "stop": round(stop, 4),
                "target": round(target, 4),
                "risk_pct": round((entry - stop) / entry * 100, 3),
                "reward_pct": round((target - entry) / entry * 100, 3),
                "r_multiple_potential": target_r_multiple,
                "orb_high": round(orb_high, 4),
                "orb_low": round(orb_low, 4),
                "orb_range_pct": round(orb_range_pct, 3),
                "volume_ratio_at_entry": round(row["volume"] / orb_avg_vol, 2),
                "atr14": round(atr_val, 4) if atr_val else None,
                "reasons": [
                    f"Close {entry:.2f} broke ORB high {orb_high:.2f}",
                    f"Volume {row['volume']:.0f} = {row['volume']/orb_avg_vol:.1f}× avg ORB-window bar",
                    f"ORB range {orb_range_pct:.2f}% within healthy band",
                ],
            })
            long_fired = True
        elif not short_fired and row["close"] < orb_low and row["volume"] >= vol_multiplier * orb_avg_vol:
            atr_val = float(atr_series.loc[ts]) if ts in atr_series.index and not pd.isna(atr_series.loc[ts]) else None
            entry = float(row["close"])
            stop_orb = orb_high
            stop_atr = entry + atr_val if atr_val else None
            stop = min(stop_orb, stop_atr) if stop_atr else stop_orb
            target = entry - target_r_multiple * (stop - entry)
            signals.append({
                "strategy": "orb",
                "side": "short",
                "entry_ts": ts.isoformat(),
                "entry_price": round(entry, 4),
                "stop": round(stop, 4),
                "target": round(target, 4),
                "risk_pct": round((stop - entry) / entry * 100, 3),
                "reward_pct": round((entry - target) / entry * 100, 3),
                "r_multiple_potential": target_r_multiple,
                "orb_high": round(orb_high, 4),
                "orb_low": round(orb_low, 4),
                "orb_range_pct": round(orb_range_pct, 3),
                "volume_ratio_at_entry": round(row["volume"] / orb_avg_vol, 2),
                "atr14": round(atr_val, 4) if atr_val else None,
                "reasons": [
                    f"Close {entry:.2f} broke ORB low {orb_low:.2f}",
                    f"Volume {row['volume']:.0f} = {row['volume']/orb_avg_vol:.1f}× avg ORB-window bar",
                    f"ORB range {orb_range_pct:.2f}% within healthy band",
                ],
            })
            short_fired = True
        if long_fired and short_fired:
            break
    return signals


def simulate_outcome(df: pd.DataFrame, signal: dict) -> dict:
    """Simulate the trade from entry: did we hit stop or target first? Or close
    at end of RTH? Returns realized P&L in % and R-multiple."""
    rth = df[df["session"] == "rth"]
    if rth.empty:
        return {"outcome": "no_data"}
    entry_ts = pd.Timestamp(signal["entry_ts"])
    if entry_ts.tzinfo is not None:
        entry_ts = entry_ts.tz_convert(None)
    after = rth[rth.index > entry_ts]
    entry = signal["entry_price"]
    stop = signal["stop"]
    target = signal["target"]
    side = signal["side"]
    risk = abs(entry - stop)
    if risk == 0:
        return {"outcome": "invalid_risk"}

    for ts, row in after.iterrows():
        high, low = float(row["high"]), float(row["low"])
        if side == "long":
            if low <= stop:
                pl_pct = (stop / entry - 1) * 100
                return {"outcome": "stop", "exit_ts": ts.isoformat(), "exit_price": round(stop, 4),
                        "pnl_pct": round(pl_pct, 3), "r_multiple": -1.0}
            if high >= target:
                pl_pct = (target / entry - 1) * 100
                return {"outcome": "target", "exit_ts": ts.isoformat(), "exit_price": round(target, 4),
                        "pnl_pct": round(pl_pct, 3), "r_multiple": float(signal["r_multiple_potential"])}
        else:  # short
            if high >= stop:
                pl_pct = (1 - stop / entry) * 100
                return {"outcome": "stop", "exit_ts": ts.isoformat(), "exit_price": round(stop, 4),
                        "pnl_pct": round(pl_pct, 3), "r_multiple": -1.0}
            if low <= target:
                pl_pct = (1 - target / entry) * 100
                return {"outcome": "target", "exit_ts": ts.isoformat(), "exit_price": round(target, 4),
                        "pnl_pct": round(pl_pct, 3), "r_multiple": float(signal["r_multiple_potential"])}

    # Neither hit — exit at last RTH bar (end-of-day flat)
    last = after.iloc[-1] if not after.empty else None
    if last is None:
        return {"outcome": "no_exit"}
    exit_price = float(last["close"])
    if side == "long":
        pl_pct = (exit_price / entry - 1) * 100
    else:
        pl_pct = (1 - exit_price / entry) * 100
    r_mult = (exit_price - entry) / risk * (1 if side == "long" else -1)
    return {"outcome": "eod_flat", "exit_ts": last.name.isoformat(), "exit_price": round(exit_price, 4),
            "pnl_pct": round(pl_pct, 3), "r_multiple": round(r_mult, 2)}
