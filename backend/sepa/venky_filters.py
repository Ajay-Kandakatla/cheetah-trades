"""Venky's filter stack — weekly 21-SMA + ATR + ADX.

Why this exists (2026-05-29): Ajay's WhatsApp trading group debated a
"weekly 9/21 SMA cross + hold-till-21-breakdown" strategy claimed by
Venky to win 90% over 12 years. The reductive truth (per Raghu in the
same thread): no single indicator works alone, but the 21-week SMA
is a clean medium-term trend filter when combined with proper risk
management. ATR sizes the stop; ADX confirms there's actually a trend
worth riding (not chop).

This module computes three small numeric gates per ticker and returns
them as nested dicts on the candidate row. The frontend renders them
as toggle chips so the user can stack them on top of SEPA's existing
qualifier gate.

The three gates:
  - weekly_21sma: price > 21-week SMA AND SMA[now] > SMA[4 weeks ago]
                  (Venky's "trend confirmation, sloping up not flat")
  - atr:          14-day ATR%; chip filter is "ATR% < cap" (default 8%)
                  — names too volatile to swing-trade get culled
  - adx:          14-day ADX; chip filter is "ADX >= threshold" (default 25)
                  — confirms there IS a trend, not chop

The gates are independent: the user can enable any subset of chips.
Returned as `row.venky = { weekly_21sma: {...}, atr: {...}, adx: {...} }`
so the frontend can render them cleanly without prefix collisions.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("sepa.venky_filters")


def _safe_float(x) -> Optional[float]:
    try:
        f = float(x)
        if f != f or f == float("inf") or f == float("-inf"):
            return None
        return f
    except Exception:
        return None


def compute_weekly_21sma(df) -> dict:
    """Weekly 21-period SMA gate (Venky's primary signal).

    Resamples daily bars to weekly closes (Fri close), computes the
    21-week SMA, and checks two things Venky explicitly named in the
    WhatsApp thread:
      1. "Weekly candle must close above 21 SMA"
      2. "21 SMA must be inclined way, not flat way"

    Slope check uses the last 4-week trailing slope (~1 month): the
    21-SMA today vs the 21-SMA 4 weeks ago must be increasing by
    at least 0.5% (filters out true flatness without demanding a
    parabolic slope).

    Returns an always-non-null dict so consumers can rely on the shape:
        {
          "pass":          bool,
          "value":         float | None,  # latest 21w SMA price
          "weekly_close":  float | None,
          "slope_up":      bool,
          "slope_pct_4w":  float | None,  # % change in SMA over last 4 weeks
          "distance_pct":  float | None,  # (close-SMA)/SMA * 100
          "weeks_above":   int | None,    # consecutive weeks close > SMA
          "error":         str | None,
        }
    """
    try:
        if df is None or len(df) < 110:
            return _empty("insufficient bars (<110 trading days = ~22 weeks)")

        # Resample to weekly (week-ending Friday). We want the LAST close
        # of each calendar week. Using "W-FRI" anchors weeks to Friday
        # close, which matches how chart packages render weekly bars.
        weekly = df["close"].resample("W-FRI").last().dropna()
        if len(weekly) < 25:
            return _empty(f"insufficient weekly bars ({len(weekly)} < 25)")

        sma_21 = weekly.rolling(window=21).mean()
        latest_close = _safe_float(weekly.iloc[-1])
        latest_sma   = _safe_float(sma_21.iloc[-1])
        if latest_close is None or latest_sma is None:
            return _empty("SMA computation produced NaN")

        # Slope check: SMA[now] vs SMA[-4]. We need at least 25 weekly
        # bars (21 for the SMA window + 4 for the slope lookback).
        sma_4w_ago = _safe_float(sma_21.iloc[-5])  # index -5 = 4 weeks back
        slope_pct_4w = None
        slope_up = False
        if sma_4w_ago is not None and sma_4w_ago > 0:
            slope_pct_4w = (latest_sma - sma_4w_ago) / sma_4w_ago * 100.0
            # 0.5% over 4 weeks ≈ 6.5% annualized — clears "true flat"
            # without requiring a parabolic move.
            slope_up = slope_pct_4w >= 0.5

        # Distance — how stretched the price is above the SMA. Useful in
        # tooltip ("close is +12% over its 21w SMA — late entry").
        distance_pct = (latest_close - latest_sma) / latest_sma * 100.0

        # Consecutive weeks the close was at-or-above the SMA. Walks
        # backwards until it finds a week below. Capped at the available
        # history; mostly a "is this a fresh cross or a long-standing
        # uptrend?" hint.
        weeks_above = 0
        for i in range(len(weekly) - 1, -1, -1):
            sm = _safe_float(sma_21.iloc[i])
            cl = _safe_float(weekly.iloc[i])
            if sm is None or cl is None:
                break
            if cl >= sm:
                weeks_above += 1
            else:
                break

        passes = bool(latest_close > latest_sma and slope_up)

        return {
            "pass":          passes,
            "value":         round(latest_sma, 4),
            "weekly_close":  round(latest_close, 4),
            "slope_up":      slope_up,
            "slope_pct_4w":  round(slope_pct_4w, 3) if slope_pct_4w is not None else None,
            "distance_pct":  round(distance_pct, 2),
            "weeks_above":   weeks_above,
            "error":         None,
        }
    except Exception as exc:
        log.debug("weekly_21sma failed: %s", exc)
        return _empty(f"computation error: {exc}")


def compute_atr(df, period: int = 14) -> dict:
    """14-day Average True Range — volatility, no direction.

    True Range = max(high-low, |high-prev_close|, |low-prev_close|)
    Smoothed with Wilder's method (EMA equivalent at alpha = 1/period).

    Returns ATR$ and ATR% (ATR / close). The chip filter uses ATR%
    against a threshold — too volatile names get culled.
    """
    try:
        if df is None or len(df) < period + 1:
            return {"atr": None, "atr_pct": None, "period": period, "error": "insufficient bars"}

        high = df["high"]
        low = df["low"]
        close = df["close"]
        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        # Element-wise max across the three TR definitions.
        tr = tr1.combine(tr2, max).combine(tr3, max)
        # Wilder's smoothing — equivalent to EMA with alpha = 1/period.
        atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()

        latest_atr = _safe_float(atr.iloc[-1])
        latest_close = _safe_float(close.iloc[-1])
        if latest_atr is None or latest_close is None or latest_close <= 0:
            return {"atr": None, "atr_pct": None, "period": period, "error": "NaN in tail"}
        atr_pct = (latest_atr / latest_close) * 100.0

        return {
            "atr":     round(latest_atr, 4),
            "atr_pct": round(atr_pct, 3),
            "period":  period,
            "error":   None,
        }
    except Exception as exc:
        log.debug("atr failed: %s", exc)
        return {"atr": None, "atr_pct": None, "period": period, "error": f"error: {exc}"}


def compute_adx(df, period: int = 14) -> dict:
    """14-day Average Directional Index — Wilder's trend strength (0-100).

    Returns ADX, +DI, -DI. ADX measures STRENGTH only (no direction);
    +DI > -DI indicates uptrend, -DI > +DI indicates downtrend.
    Conventional thresholds:
      < 20  no trend / chop
      25-50 strong trend
      > 50  very strong (often near-exhaustion)

    The chip filter uses `adx >= threshold` (default 25) so the user
    can require a meaningful trend, not chop.
    """
    try:
        if df is None or len(df) < period * 2 + 1:
            return {"adx": None, "plus_di": None, "minus_di": None,
                    "trend": None, "period": period, "error": "insufficient bars"}

        high = df["high"]
        low = df["low"]
        close = df["close"]

        up_move = high.diff()
        down_move = -low.diff()

        # +DM = up_move if up_move > down_move AND up_move > 0 else 0
        plus_dm = ((up_move > down_move) & (up_move > 0)).astype(float) * up_move.fillna(0.0)
        minus_dm = ((down_move > up_move) & (down_move > 0)).astype(float) * down_move.fillna(0.0)

        prev_close = close.shift(1)
        tr = (high - low).combine((high - prev_close).abs(), max).combine((low - prev_close).abs(), max)

        # Wilder smoothing on TR, +DM, -DM
        atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
        plus_di = 100.0 * (plus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr.replace(0, float("nan")))
        minus_di = 100.0 * (minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr.replace(0, float("nan")))

        dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, float("nan"))) * 100.0
        adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()

        latest_adx = _safe_float(adx.iloc[-1])
        latest_plus_di = _safe_float(plus_di.iloc[-1])
        latest_minus_di = _safe_float(minus_di.iloc[-1])
        if latest_adx is None:
            return {"adx": None, "plus_di": None, "minus_di": None,
                    "trend": None, "period": period, "error": "NaN in tail"}

        if latest_plus_di is None or latest_minus_di is None:
            trend = None
        elif latest_plus_di > latest_minus_di:
            trend = "up"
        elif latest_minus_di > latest_plus_di:
            trend = "down"
        else:
            trend = "flat"

        return {
            "adx":      round(latest_adx, 2),
            "plus_di":  round(latest_plus_di, 2) if latest_plus_di is not None else None,
            "minus_di": round(latest_minus_di, 2) if latest_minus_di is not None else None,
            "trend":    trend,
            "period":   period,
            "error":    None,
        }
    except Exception as exc:
        log.debug("adx failed: %s", exc)
        return {"adx": None, "plus_di": None, "minus_di": None,
                "trend": None, "period": period, "error": f"error: {exc}"}


def compute_all(df) -> dict:
    """Compute the full Venky stack as one nested dict.

    Always returns the shape `{weekly_21sma, atr, adx}` with sub-dicts
    that are themselves always-present (with `error` set on failure).
    Frontend can rely on `row.venky.weekly_21sma.pass` etc. without
    optional chaining beyond the top-level.
    """
    return {
        "weekly_21sma": compute_weekly_21sma(df),
        "atr":          compute_atr(df),
        "adx":          compute_adx(df),
    }


def _empty(error_msg: str) -> dict:
    return {
        "pass":          False,
        "value":         None,
        "weekly_close":  None,
        "slope_up":      False,
        "slope_pct_4w":  None,
        "distance_pct":  None,
        "weeks_above":   None,
        "error":         error_msg,
    }


__all__ = ["compute_weekly_21sma", "compute_atr", "compute_adx", "compute_all"]
