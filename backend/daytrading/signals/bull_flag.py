"""Bull Flag continuation — strong impulse + tight consolidation + breakout.

Pattern (classical chart-pattern lit; refined by Stockbee + IBD):
  1. Pole: a strong move ≥2% in 5-15 minutes during RTH.
  2. Flag: 5-15 bar tight consolidation where high-low range stays within
     40% of the pole height, drift is sideways or gentle pullback.
  3. Volume drops during the flag (smart-money holding, not selling).
  4. Entry: break above the flag-high on volume > flag-avg-volume × 1.3.
  5. Stop: bottom of the flag. Target: pole-height projected up from breakout.

Bear flag is the mirror image — short signal.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import atr


def detect(df: pd.DataFrame,
           min_pole_pct: float = 2.0,
           pole_max_bars: int = 15,
           flag_min_bars: int = 5,
           flag_max_bars: int = 15,
           flag_max_range_ratio: float = 0.4,    # flag range ≤ 40% of pole
           breakout_vol_multiplier: float = 1.3,
           target_pole_multiple: float = 1.0,    # measured-move target
           ) -> list[dict]:
    if df is None or df.empty:
        return []
    rth = df[df["session"] == "rth"]
    if rth.empty:
        return []
    et_idx = rth.index.tz_localize("UTC").tz_convert("America/New_York")
    today = pd.Series(et_idx.date, index=rth.index).max()
    today_rth = rth[pd.Series(et_idx.date, index=rth.index) == today]
    if len(today_rth) < pole_max_bars + flag_min_bars + 1:
        return []

    closes = today_rth["close"].values
    highs = today_rth["high"].values
    lows = today_rth["low"].values
    vols = today_rth["volume"].values
    atr_series = atr(rth, period=14)

    signals: list[dict] = []
    fired_long = False
    fired_short = False

    # Walk the day looking for: pole ending at bar i → flag of length k starting at i+1
    for pole_end in range(pole_max_bars, len(today_rth) - flag_min_bars - 1):
        if fired_long and fired_short:
            break
        # Try long pole: rising
        for pole_len in range(3, pole_max_bars + 1):
            pole_start = pole_end - pole_len + 1
            if pole_start < 0:
                continue
            pole_low = float(lows[pole_start:pole_end + 1].min())
            pole_high = float(highs[pole_start:pole_end + 1].max())
            pole_pct_long = (closes[pole_end] / closes[pole_start] - 1) * 100

            if not fired_long and pole_pct_long >= min_pole_pct:
                pole_height = pole_high - pole_low
                # Search flag of varying length
                for flag_len in range(flag_min_bars, flag_max_bars + 1):
                    flag_end = pole_end + flag_len
                    if flag_end >= len(today_rth) - 1:
                        break
                    flag_high = float(highs[pole_end + 1:flag_end + 1].max())
                    flag_low = float(lows[pole_end + 1:flag_end + 1].min())
                    flag_range = flag_high - flag_low
                    if flag_range > flag_max_range_ratio * pole_height:
                        continue
                    # Avg vol in flag for breakout comparison
                    flag_avg_vol = float(vols[pole_end + 1:flag_end + 1].mean())
                    if flag_avg_vol <= 0:
                        continue
                    # Breakout bar
                    breakout_idx = flag_end + 1
                    if breakout_idx >= len(today_rth):
                        break
                    if closes[breakout_idx] <= flag_high:
                        continue
                    if vols[breakout_idx] < breakout_vol_multiplier * flag_avg_vol:
                        continue
                    # Fire signal
                    entry = float(closes[breakout_idx])
                    stop = float(flag_low)
                    if entry - stop <= 0:
                        continue
                    target = entry + target_pole_multiple * pole_height
                    ts = today_rth.index[breakout_idx]
                    atr_val = float(atr_series.loc[ts]) if ts in atr_series.index and atr_series.loc[ts] == atr_series.loc[ts] else None
                    signals.append({
                        "strategy": "bull_flag",
                        "side": "long",
                        "entry_ts": ts.isoformat(),
                        "entry_price": round(entry, 4),
                        "stop": round(stop, 4),
                        "target": round(target, 4),
                        "risk_pct": round((entry - stop) / entry * 100, 3),
                        "reward_pct": round((target - entry) / entry * 100, 3),
                        "r_multiple_potential": round((target - entry) / (entry - stop), 2),
                        "pole_pct": round(pole_pct_long, 2),
                        "pole_bars": pole_len,
                        "flag_bars": flag_len,
                        "flag_high": round(flag_high, 4),
                        "flag_low": round(flag_low, 4),
                        "atr14": round(atr_val, 4) if atr_val else None,
                        "reasons": [
                            f"Pole: +{pole_pct_long:.2f}% over {pole_len} bars (impulse)",
                            f"Flag: {flag_len} bars, range {flag_range:.2f} = {flag_range/pole_height*100:.0f}% of pole — tight",
                            f"Breakout volume {vols[breakout_idx]/flag_avg_vol:.1f}× flag avg",
                        ],
                    })
                    fired_long = True
                    break
                if fired_long:
                    break

            # Short pole (bear flag)
            pole_pct_short = (closes[pole_start] / closes[pole_end] - 1) * 100
            if not fired_short and pole_pct_short >= min_pole_pct:
                pole_height = pole_high - pole_low
                for flag_len in range(flag_min_bars, flag_max_bars + 1):
                    flag_end = pole_end + flag_len
                    if flag_end >= len(today_rth) - 1:
                        break
                    flag_high = float(highs[pole_end + 1:flag_end + 1].max())
                    flag_low = float(lows[pole_end + 1:flag_end + 1].min())
                    flag_range = flag_high - flag_low
                    if flag_range > flag_max_range_ratio * pole_height:
                        continue
                    flag_avg_vol = float(vols[pole_end + 1:flag_end + 1].mean())
                    if flag_avg_vol <= 0:
                        continue
                    breakout_idx = flag_end + 1
                    if breakout_idx >= len(today_rth):
                        break
                    if closes[breakout_idx] >= flag_low:
                        continue
                    if vols[breakout_idx] < breakout_vol_multiplier * flag_avg_vol:
                        continue
                    entry = float(closes[breakout_idx])
                    stop = float(flag_high)
                    if stop - entry <= 0:
                        continue
                    target = entry - target_pole_multiple * pole_height
                    ts = today_rth.index[breakout_idx]
                    atr_val = float(atr_series.loc[ts]) if ts in atr_series.index and atr_series.loc[ts] == atr_series.loc[ts] else None
                    signals.append({
                        "strategy": "bull_flag",
                        "side": "short",
                        "entry_ts": ts.isoformat(),
                        "entry_price": round(entry, 4),
                        "stop": round(stop, 4),
                        "target": round(target, 4),
                        "risk_pct": round((stop - entry) / entry * 100, 3),
                        "reward_pct": round((entry - target) / entry * 100, 3),
                        "r_multiple_potential": round((entry - target) / (stop - entry), 2),
                        "pole_pct": round(-pole_pct_short, 2),
                        "pole_bars": pole_len,
                        "flag_bars": flag_len,
                        "flag_high": round(flag_high, 4),
                        "flag_low": round(flag_low, 4),
                        "atr14": round(atr_val, 4) if atr_val else None,
                        "reasons": [
                            f"Bear pole: -{pole_pct_short:.2f}% over {pole_len} bars",
                            f"Bear flag: {flag_len} bars tight consolidation",
                            f"Breakdown volume {vols[breakout_idx]/flag_avg_vol:.1f}× flag avg",
                        ],
                    })
                    fired_short = True
                    break
                if fired_short:
                    break

    return signals


def simulate_outcome(df: pd.DataFrame, signal: dict) -> dict:
    """Standard stop/target/EOD-flat simulation."""
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
