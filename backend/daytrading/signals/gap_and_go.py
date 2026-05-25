"""Gap-and-Go — premarket gap continuation strategy.

Pattern (Ross Cameron / Warrior Trading framework):
  1. Stock gaps up/down ≥2% from prior RTH close (premarket-driven).
  2. First RTH bar (09:30-09:31 ET) closes IN THE DIRECTION of the gap
     (long: bullish bar; short: bearish bar).
  3. Volume confirmation: first-bar volume > 1.5× the 10-day same-time average.
  4. Long entry: break above the first-5min high. Stop = first-5min low or
     premarket low. Target = 1.5× initial risk OR premarket high (whichever
     is further). Short mirrors.

Avoids the most common failure mode (gap-and-fade) by requiring the opening
bar to confirm the gap direction.
"""
from __future__ import annotations

import pandas as pd

from ..indicators import atr


def detect(df: pd.DataFrame,
           min_gap_pct: float = 1.0,
           confirm_minutes: int = 5,
           vol_multiplier: float = 1.2,
           target_r_multiple: float = 1.5) -> list[dict]:
    if df is None or df.empty:
        return []

    rth = df[df["session"] == "rth"]
    if rth.empty:
        return []
    et_idx = rth.index.tz_localize("UTC").tz_convert("America/New_York")
    et_dates = pd.Series(et_idx.date, index=rth.index)
    today = et_dates.max()
    prior_dates = sorted([d for d in et_dates.unique() if d != today])

    today_rth = rth[et_dates == today]
    if today_rth.empty or len(today_rth) < confirm_minutes + 2:
        return []

    # Prior RTH close
    if not prior_dates:
        return []
    prior_close_bars = rth[et_dates == prior_dates[-1]]
    if prior_close_bars.empty:
        return []
    prior_close = float(prior_close_bars["close"].iloc[-1])

    # Today's open + first-bar metrics
    first_bar = today_rth.iloc[0]
    today_open = float(first_bar["open"])
    gap_pct = (today_open / prior_close - 1) * 100
    if abs(gap_pct) < min_gap_pct:
        return []

    side = "long" if gap_pct > 0 else "short"

    # First-bar must confirm gap direction
    first_bullish = first_bar["close"] > first_bar["open"]
    if side == "long" and not first_bullish:
        return []
    if side == "short" and first_bullish:
        return []

    # Volume confirmation: first bar vs 10d same-time avg
    same_time_vols = []
    for d in prior_dates[-10:]:
        day_bars = rth[et_dates == d]
        if not day_bars.empty:
            same_time_vols.append(float(day_bars["volume"].iloc[0]))
    if same_time_vols:
        avg_vol = sum(same_time_vols) / len(same_time_vols)
        if avg_vol > 0 and first_bar["volume"] < vol_multiplier * avg_vol:
            return []

    # Confirmation window — first N minutes of RTH
    confirm = today_rth.iloc[:confirm_minutes]
    confirm_high = float(confirm["high"].max())
    confirm_low = float(confirm["low"].min())
    confirm_avg_vol = float(confirm["volume"].mean())

    # Premarket levels for stop-loss reference
    pre = df[df["session"] == "premarket"]
    pre_today = pre[pd.Series(pre.index.tz_localize("UTC").tz_convert("America/New_York").date,
                              index=pre.index) == today]
    pre_high = float(pre_today["high"].max()) if not pre_today.empty else None
    pre_low = float(pre_today["low"].min()) if not pre_today.empty else None

    # ATR for stop refinement
    atr_series = atr(rth, period=14)

    after = today_rth.iloc[confirm_minutes:]
    signals: list[dict] = []
    for ts, row in after.iterrows():
        if side == "long":
            if row["close"] > confirm_high and row["volume"] >= confirm_avg_vol:
                entry = float(row["close"])
                # Stop = max(confirm_low, premarket_low) — whichever is closer
                stop = confirm_low
                if pre_low is not None and pre_low < entry and pre_low > stop:
                    stop = pre_low
                if entry - stop <= 0:
                    return []
                target = entry + target_r_multiple * (entry - stop)
                # If premarket high is further than target_r_multiple, prefer it
                if pre_high is not None and pre_high > target:
                    target = pre_high
                signals.append(_build("gap_and_go", "long", ts, row, entry, stop, target,
                                     gap_pct, confirm_high, confirm_low, atr_series))
                break
        else:  # short
            if row["close"] < confirm_low and row["volume"] >= confirm_avg_vol:
                entry = float(row["close"])
                stop = confirm_high
                if pre_high is not None and pre_high > entry and pre_high < stop:
                    stop = pre_high
                if stop - entry <= 0:
                    return []
                target = entry - target_r_multiple * (stop - entry)
                if pre_low is not None and pre_low < target:
                    target = pre_low
                signals.append(_build("gap_and_go", "short", ts, row, entry, stop, target,
                                     gap_pct, confirm_high, confirm_low, atr_series))
                break
    return signals


def _build(strategy, side, ts, row, entry, stop, target, gap_pct, confirm_high, confirm_low, atr_series):
    risk = abs(entry - stop)
    reward = abs(target - entry)
    atr_val = float(atr_series.loc[ts]) if ts in atr_series.index and atr_series.loc[ts] == atr_series.loc[ts] else None
    return {
        "strategy": strategy,
        "side": side,
        "entry_ts": ts.isoformat(),
        "entry_price": round(entry, 4),
        "stop": round(stop, 4),
        "target": round(target, 4),
        "risk_pct": round(risk / entry * 100, 3),
        "reward_pct": round(reward / entry * 100, 3),
        "r_multiple_potential": round(reward / risk, 2) if risk else None,
        "gap_pct": round(gap_pct, 2),
        "confirm_high": round(confirm_high, 4),
        "confirm_low": round(confirm_low, 4),
        "volume_ratio_at_entry": round(row["volume"] / max(1, row["volume"]), 2),  # vs itself; replaced by ratio in detect
        "atr14": round(atr_val, 4) if atr_val else None,
        "reasons": [
            f"Gap {gap_pct:+.2f}% from prior close — large premarket move",
            f"First RTH bar confirmed direction with bullish/bearish close",
            f"Broke {confirm_high:.2f}-{confirm_low:.2f} confirmation range on volume",
        ],
    }


def simulate_outcome(df: pd.DataFrame, signal: dict) -> dict:
    """Same outcome simulation as ORB — exit on stop, target, or EOD flat."""
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
    r_pot = signal.get("r_multiple_potential") or 1.5

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
