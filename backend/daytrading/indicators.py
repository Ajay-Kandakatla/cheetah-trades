"""Intraday indicators — VWAP, ATR, opening range, premarket H/L, relative volume.

All functions take a 1-minute OHLCV DataFrame indexed by UTC timestamp, with
a `session` column (rth/premarket/afterhours), and return either a Series
aligned to the input or a scalar/dict.
"""
from __future__ import annotations

from datetime import time as dtime
from typing import Optional

import numpy as np
import pandas as pd


def vwap_session(df: pd.DataFrame, session: str = "rth") -> pd.Series:
    """Cumulative VWAP for the bars matching `session`. Resets per day.

    Returns a Series with NaN for non-session bars."""
    if df is None or df.empty:
        return pd.Series(dtype=float)
    mask = df["session"] == session
    out = pd.Series(np.nan, index=df.index)
    if not mask.any():
        return out
    typical = (df["high"] + df["low"] + df["close"]) / 3
    pv = typical * df["volume"]
    # Reset cumulative at the start of each session (per ET date)
    et_date = df.index.tz_localize("UTC").tz_convert("America/New_York").date if df.index.tz is not None else \
              df.index.tz_localize("UTC").tz_convert("America/New_York").date
    # Simpler — just group by ET calendar date among masked rows:
    et_idx = df.index.tz_localize("UTC", nonexistent="shift_forward", ambiguous="NaT").tz_convert("America/New_York")
    day_keys = pd.Series(et_idx.date, index=df.index)

    cum_pv = 0.0
    cum_vol = 0.0
    last_day = None
    for ts in df.index:
        if not mask.loc[ts]:
            continue
        d = day_keys.loc[ts]
        if d != last_day:
            cum_pv = 0.0
            cum_vol = 0.0
            last_day = d
        cum_pv += pv.loc[ts]
        cum_vol += df.loc[ts, "volume"]
        if cum_vol > 0:
            out.loc[ts] = cum_pv / cum_vol
    return out


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range over `period` bars (Wilder)."""
    if df is None or len(df) < period + 1:
        return pd.Series(dtype=float, index=df.index if df is not None else None)
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat([(high - low).abs(),
                    (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def opening_range(df: pd.DataFrame, minutes: int = 5) -> Optional[dict]:
    """High/low/volume of the first `minutes` of the RTH session for the most
    recent ET trading day in `df`. Returns None if RTH hasn't opened.
    """
    if df is None or df.empty:
        return None
    rth = df[df["session"] == "rth"]
    if rth.empty:
        return None
    et_idx = rth.index.tz_localize("UTC").tz_convert("America/New_York")
    # Pick the most recent ET date
    most_recent_date = et_idx.date.max()
    day_mask = pd.Series(et_idx.date, index=rth.index) == most_recent_date
    today_rth = rth[day_mask]
    if today_rth.empty:
        return None
    open_bar_count = min(minutes, len(today_rth))
    window = today_rth.iloc[:open_bar_count]
    return {
        "high": float(window["high"].max()),
        "low": float(window["low"].min()),
        "volume": float(window["volume"].sum()),
        "from": str(window.index[0]),
        "to": str(window.index[-1]),
        "minutes": minutes,
        "complete": len(window) >= minutes,
        "et_date": str(most_recent_date),
    }


def premarket_levels(df: pd.DataFrame) -> Optional[dict]:
    """High/low/volume of premarket session for the most recent ET date."""
    if df is None or df.empty or "session" not in df.columns:
        return None
    pre = df[df["session"] == "premarket"]
    if pre.empty:
        return None
    et_idx = pre.index.tz_localize("UTC").tz_convert("America/New_York")
    most_recent = et_idx.date.max()
    day_mask = pd.Series(et_idx.date, index=pre.index) == most_recent
    today_pre = pre[day_mask]
    if today_pre.empty:
        return None
    return {
        "high": float(today_pre["high"].max()),
        "low": float(today_pre["low"].min()),
        "volume": float(today_pre["volume"].sum()),
        "et_date": str(most_recent),
        "bars": len(today_pre),
    }


def relative_volume(df: pd.DataFrame, lookback_days: int = 10) -> Optional[float]:
    """Today's RTH volume so far / average RTH volume at the same time-of-day
    over the prior `lookback_days`. >1.5 = elevated, >2.0 = unusual.
    """
    if df is None or df.empty:
        return None
    rth = df[df["session"] == "rth"]
    if rth.empty:
        return None
    et_idx = rth.index.tz_localize("UTC").tz_convert("America/New_York")
    et_date = pd.Series(et_idx.date, index=rth.index)
    most_recent = et_date.max()
    today = rth[et_date == most_recent]
    if today.empty:
        return None
    today_vol = float(today["volume"].sum())
    bars_today = len(today)
    # Compare to same number of opening bars on prior days
    prior_dates = sorted([d for d in et_date.unique() if d != most_recent])[-lookback_days:]
    if not prior_dates:
        return None
    prior_avg_vol = []
    for d in prior_dates:
        day_bars = rth[et_date == d].iloc[:bars_today]
        if not day_bars.empty:
            prior_avg_vol.append(float(day_bars["volume"].sum()))
    if not prior_avg_vol:
        return None
    avg = np.mean(prior_avg_vol)
    if avg == 0:
        return None
    return round(today_vol / avg, 2)


def gap_pct(today_rth_open: float, prev_rth_close: float) -> Optional[float]:
    """Percent gap from prior day's RTH close to today's first RTH bar open."""
    if not prev_rth_close:
        return None
    return round((today_rth_open / prev_rth_close - 1) * 100, 2)


def session_high_low(df: pd.DataFrame, session: str = "rth") -> Optional[dict]:
    """High/low of the named session for the most recent ET date."""
    if df is None or df.empty:
        return None
    sub = df[df["session"] == session]
    if sub.empty:
        return None
    return {"high": float(sub["high"].max()), "low": float(sub["low"].min())}
