"""Momentum Failure (short) — fade exhausted parabolic moves.

Pattern (Bo Yoder / Steenbarger):
  1. Stock has had a parabolic move ≥5% within the last 30 minutes on
     relative volume ≥2× the same-time average.
  2. Topping/exhaustion candle: long upper wick ≥2× body, OR an outside
     bar (high > prior, low < prior, close < prior close).
  3. Next bar closes BELOW the topping candle's body midpoint.
  4. Short entry on that confirmation. Stop = top of the topping candle.
  5. Target = 50% retrace of the parabolic move OR 1.5×R, whichever closer.

This is short-only — failure-to-continue is a high-conviction setup but
asymmetric (longs are easier than shorts in equity markets generally).
"""
from __future__ import annotations

import pandas as pd

from ..indicators import atr


def detect(df: pd.DataFrame,
           min_parabolic_pct: float = 3.0,
           parabolic_lookback_bars: int = 45,
           min_rel_vol: float = 1.2,           # vs same-time prior-day avg
           wick_ratio: float = 1.5,
           target_r_multiple: float = 1.5,
           ) -> list[dict]:
    if df is None or df.empty:
        return []
    rth = df[df["session"] == "rth"]
    if rth.empty:
        return []
    et_idx = rth.index.tz_localize("UTC").tz_convert("America/New_York")
    et_dates = pd.Series(et_idx.date, index=rth.index)
    today = et_dates.max()
    today_rth = rth[et_dates == today]
    if len(today_rth) < parabolic_lookback_bars + 5:
        return []

    closes = today_rth["close"].values
    highs = today_rth["high"].values
    lows = today_rth["low"].values
    opens = today_rth["open"].values
    vols = today_rth["volume"].values
    indices = today_rth.index
    atr_series = atr(rth, period=14)

    # Same-time-of-day volume baseline from prior days
    prior_dates = sorted([d for d in et_dates.unique() if d != today])[-10:]

    fired = False
    signals: list[dict] = []
    for i in range(parabolic_lookback_bars, len(today_rth) - 1):
        if fired:
            break
        # Parabolic check: max gain in the last `parabolic_lookback_bars`
        window_low_idx = max(0, i - parabolic_lookback_bars)
        window_low = float(lows[window_low_idx:i + 1].min())
        if window_low <= 0:
            continue
        gain = (highs[i] / window_low - 1) * 100
        if gain < min_parabolic_pct:
            continue

        # Relative volume — sum vol over the parabolic window vs prior day same window
        window_vol = float(vols[window_low_idx:i + 1].sum())
        prior_vols = []
        for d in prior_dates:
            day_bars = rth[et_dates == d]
            if len(day_bars) >= i + 1:
                prior_vols.append(float(day_bars["volume"].iloc[window_low_idx:i + 1].sum()))
        if prior_vols:
            avg_prior = sum(prior_vols) / len(prior_vols)
            if avg_prior > 0 and window_vol < min_rel_vol * avg_prior:
                continue

        # Topping candle at bar i
        body = abs(closes[i] - opens[i])
        upper_wick = highs[i] - max(closes[i], opens[i])
        is_outside = (i > 0 and highs[i] > highs[i - 1] and lows[i] < lows[i - 1] and closes[i] < closes[i - 1])
        is_wick = (upper_wick >= wick_ratio * max(body, 0.001))
        if not (is_outside or is_wick):
            continue

        # Confirmation: next bar closes below topping body midpoint
        if i + 1 >= len(today_rth):
            break
        body_mid = (opens[i] + closes[i]) / 2
        confirm_close = float(closes[i + 1])
        if confirm_close >= body_mid:
            continue

        # Build short signal
        entry = confirm_close
        stop = float(highs[i]) + 0.02
        if stop - entry <= 0:
            continue
        risk = stop - entry
        # Target: lesser of (1.5×R below entry, 50% retracement of parabolic)
        target_r = entry - target_r_multiple * risk
        target_retrace = highs[i] - 0.5 * (highs[i] - window_low)
        target = max(target_r, target_retrace)  # closer of the two = higher price for shorts
        if target >= entry:
            continue

        ts = indices[i + 1]
        atr_val = float(atr_series.loc[ts]) if ts in atr_series.index and atr_series.loc[ts] == atr_series.loc[ts] else None
        signals.append({
            "strategy": "momentum_failure",
            "side": "short",
            "entry_ts": ts.isoformat(),
            "entry_price": round(entry, 4),
            "stop": round(stop, 4),
            "target": round(target, 4),
            "risk_pct": round(risk / entry * 100, 3),
            "reward_pct": round((entry - target) / entry * 100, 3),
            "r_multiple_potential": round((entry - target) / risk, 2),
            "parabolic_gain_pct": round(gain, 2),
            "parabolic_window_low": round(window_low, 4),
            "topping_high": round(float(highs[i]), 4),
            "atr14": round(atr_val, 4) if atr_val else None,
            "reasons": [
                f"Parabolic +{gain:.1f}% in {parabolic_lookback_bars} bars — exhausted move",
                f"Topping candle: {'outside bar reversal' if is_outside else f'upper wick {upper_wick:.2f} = {upper_wick/max(body,0.01):.1f}× body'}",
                f"Confirmation: next bar closed {confirm_close:.2f} < body mid {body_mid:.2f}",
            ],
        })
        fired = True
    return signals


def simulate_outcome(df: pd.DataFrame, signal: dict) -> dict:
    rth = df[df["session"] == "rth"]
    if rth.empty:
        return {"outcome": "no_data"}
    entry_ts = pd.Timestamp(signal["entry_ts"])
    if entry_ts.tzinfo is not None:
        entry_ts = entry_ts.tz_convert(None)
    after = rth[rth.index > entry_ts]
    entry, stop, target = signal["entry_price"], signal["stop"], signal["target"]
    risk = abs(entry - stop)
    if risk == 0:
        return {"outcome": "invalid_risk"}
    r_pot = signal.get("r_multiple_potential") or 1.5

    for ts, row in after.iterrows():
        h, l = float(row["high"]), float(row["low"])
        # Short side
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
    pl = (1 - exit_price / entry) * 100
    r_mult = (entry - exit_price) / risk
    return {"outcome": "eod_flat", "exit_ts": last.name.isoformat(), "exit_price": round(exit_price, 4),
            "pnl_pct": round(pl, 3), "r_multiple": round(r_mult, 2)}
