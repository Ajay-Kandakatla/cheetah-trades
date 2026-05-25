"""Trade plan builder — entries, stops, targets, support/resistance.

Given a daily-bar price history (pandas DataFrame with columns
high/low/close/open/volume) plus optional setup metadata (VCP pivot,
power-play info), returns a structured trade plan that a swing trader
can act on without opening a chart elsewhere.

The plan answers four questions:
  1. Where to buy?          (entry levels — aggressive vs standard)
  2. Where to stop out?     (multiple stop strategies with a recommended pick)
  3. Where to take profit?  (R-multiples + nearest resistance)
  4. What's the risk?       (% to stop, R-distance to nearest resistance)

All numbers are honest about their methodology — every field carries a
short label so the UI can show "stop $114.20 (Minervini 7%)" rather than
just a raw number.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("analysis.trade_plan")


# Minervini's published rule: never hold a swing trade more than 7-8%
# below entry. We default to 7% as the stricter side. Override via
# build_plan(hard_stop_pct=0.08) when configurable.
MINERVINI_HARD_STOP_PCT = 0.07

# ATR multiplier for volatility-adjusted stop. 2.0× is the O'Neil /
# Minervini convention for swing trades on stage-2 names.
ATR_STOP_MULTIPLIER = 2.0


# ---------------------------------------------------------------------------
# Indicators (kept here to avoid a circular import with daytrading.indicators)
# ---------------------------------------------------------------------------
def _atr(df, period: int = 14) -> Optional[float]:
    """Average True Range, Wilder-smoothed. Returns the most recent value
    in the same units as the price (i.e. ATR=$3.20 means the typical day
    has a $3.20 high-low range after smoothing).
    """
    try:
        if df is None or len(df) < period + 1:
            return None
        import pandas as pd  # local import keeps top-level imports clean
        h, l, c = df["high"], df["low"], df["close"]
        prev_c = c.shift(1)
        tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
        # Wilder smoothing (RMA) — first value = simple mean of first `period`
        atr = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
        last = atr.iloc[-1]
        if last is None or last != last:  # NaN
            return None
        return float(last)
    except Exception as exc:
        log.debug("ATR computation failed: %s", exc)
        return None


def _swing_highs_lows(df, lookback: int = 5, n_max: int = 5) -> tuple[list[float], list[float]]:
    """Find recent swing highs + lows using a rolling N-bar window.

    A bar is a swing high if it's the local max over [-lookback, +lookback].
    We can only confirm swings up to `lookback` bars from the current bar
    (no future data), so the most recent swings end ~5 bars before today.

    Returns (highs, lows) — most recent first, capped at n_max each.
    Useful for plotting "horizontal levels" (where price has previously
    reversed) on a chart-aware UI.
    """
    try:
        if df is None or len(df) < lookback * 2 + 1:
            return [], []
        h, l = df["high"].values, df["low"].values
        n = len(h)
        highs: list[tuple[int, float]] = []
        lows:  list[tuple[int, float]] = []
        for i in range(lookback, n - lookback):
            window_h = h[i - lookback: i + lookback + 1]
            window_l = l[i - lookback: i + lookback + 1]
            if h[i] == max(window_h):
                highs.append((i, float(h[i])))
            if l[i] == min(window_l):
                lows.append((i, float(l[i])))
        # Most recent first, dedupe by ~0.5% price proximity to avoid
        # cluster-pollution (a 3-day pivot at $99 / $99.20 / $99.10 is one level)
        def _dedupe(seq: list[tuple[int, float]]) -> list[float]:
            out: list[float] = []
            for _, px in reversed(seq):
                if all(abs(px - x) / max(x, 1e-6) > 0.005 for x in out):
                    out.append(px)
                if len(out) >= n_max:
                    break
            return out
        return _dedupe(highs), _dedupe(lows)
    except Exception as exc:
        log.debug("swing detection failed: %s", exc)
        return [], []


def _moving_average(df, period: int) -> Optional[float]:
    try:
        if df is None or len(df) < period:
            return None
        return float(df["close"].rolling(period).mean().iloc[-1])
    except Exception:
        return None


def _high_low(df, period: int) -> tuple[Optional[float], Optional[float]]:
    """High/low of last `period` bars. (week52 ≈ period=252.)"""
    try:
        if df is None or len(df) < period:
            return None, None
        recent = df.iloc[-period:]
        return float(recent["high"].max()), float(recent["low"].min())
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Plan builders
# ---------------------------------------------------------------------------
def _stops(entry: float, base_low: Optional[float], atr: Optional[float],
           hard_pct: float = MINERVINI_HARD_STOP_PCT) -> dict:
    """Build the three-stop set + recommend one.

    Per Minervini:
      • Base low = ideal (technical) — derived from VCP last contraction
      • ATR×2  = volatility-adjusted (works when no clean base)
      • Hard 7% = absolute cap — never let a position go past this

    The RECOMMENDED stop is the HIGHEST of {base_low, atr_stop, hard_stop}
    that's still BELOW the entry — i.e. the least-painful one that's
    also a real technical level. This minimizes false stops on noise
    while honoring the hard cap.
    """
    candidates: list[tuple[str, float]] = []
    hard_stop = round(entry * (1 - hard_pct), 2)
    candidates.append(("hard_pct", hard_stop))

    if atr is not None and atr > 0:
        atr_stop = round(entry - ATR_STOP_MULTIPLIER * atr, 2)
        candidates.append(("atr_2x", atr_stop))

    if base_low is not None and base_low > 0 and base_low < entry:
        candidates.append(("base_low", float(base_low)))

    # Filter to stops strictly below entry (defensive)
    valid = [(name, px) for name, px in candidates if px < entry]
    if not valid:
        # Degenerate case — fall back to hard stop only
        return {
            "recommended_label": "hard_pct",
            "recommended": hard_stop,
            "candidates": dict(candidates),
            "reason": "Only hard 7% stop applies (base/ATR unavailable)",
        }

    # Pick the highest (least painful) — but never above the hard cap
    valid.sort(key=lambda x: -x[1])
    rec_label, rec_px = valid[0]
    if rec_px > hard_stop:
        # If the technical stop is tighter than the hard cap, use that
        # (means the base is closer than 7% — that's MORE conservative)
        pass
    else:
        # Technical stop deeper than 7% — clamp to hard cap (Minervini rule)
        # We pick whichever is HIGHER (less painful) within the valid set,
        # which is what the sort already did. But verify against hard_stop
        # one more time — if hard_stop is the highest, use it.
        if hard_stop >= rec_px:
            rec_label, rec_px = "hard_pct", hard_stop

    risk_pct = round((entry - rec_px) / entry * 100, 2) if entry else None
    return {
        "recommended_label": rec_label,
        "recommended": round(rec_px, 2),
        "candidates": {name: round(px, 2) for name, px in candidates},
        "risk_pct": risk_pct,
        "reason": _stop_reason(rec_label),
    }


def _stop_reason(label: str) -> str:
    return {
        "base_low": "VCP base low — last contraction's swing low. Tightest technical stop.",
        "atr_2x":   "Entry − 2×ATR(14) — volatility-adjusted stop, O'Neil/Minervini convention.",
        "hard_pct": f"Entry − {int(MINERVINI_HARD_STOP_PCT * 100)}% — Minervini's hard cap. Never hold a swing past this.",
    }.get(label, "")


def _targets(entry: float, stop: float,
             nearest_resistance: Optional[float] = None) -> dict:
    """R-multiples + nearest resistance. R = entry − stop (always positive).

    Minervini's published profit-taking guidance:
      • 1R quick scale (cover risk + 1× reward)
      • 2-3R sweet spot for stage-2 swings
      • Trail stop above 2R if name keeps running
    """
    r = entry - stop
    if r <= 0:
        return {"r": 0, "r1": None, "r2": None, "r3": None, "nearest_resistance": nearest_resistance}
    return {
        "r": round(r, 2),
        "r1": round(entry + 1 * r, 2),
        "r2": round(entry + 2 * r, 2),
        "r3": round(entry + 3 * r, 2),
        "nearest_resistance": round(nearest_resistance, 2) if nearest_resistance else None,
        "reward_to_risk": round((nearest_resistance - entry) / r, 2) if nearest_resistance else None,
    }


def build_plan(
    *,
    last_close: float,
    df=None,                                    # pandas DataFrame: open/high/low/close/volume
    vcp_setup: Optional[dict] = None,           # {pivot, stop, ...} from sepa.vcp
    powerplay_setup: Optional[dict] = None,     # {pivot, stop, ...} from sepa.power_play
    direction: str = "long",                    # "long" or "short"
    hard_stop_pct: float = MINERVINI_HARD_STOP_PCT,
) -> dict:
    """Top-level builder. Combines all sub-helpers into a single plan dict.

    Returns shape (long example):
      {
        "direction": "long",
        "entries": {
          "aggressive": 145.20,    # pivot or current
          "standard":   146.65,    # +1% above pivot (confirmed breakout)
          "pullback":   141.50,    # 50d MA, only if currently above
        },
        "entry_recommended_label": "aggressive",
        "entry_recommended": 145.20,
        "stop": {
          "recommended_label": "atr_2x",
          "recommended":       138.50,
          "candidates":        {hard_pct: 135.04, atr_2x: 138.50, base_low: 137.20},
          "risk_pct":          4.6,
          "reason":            "Entry − 2×ATR(14) — ...",
        },
        "targets": {
          "r": 6.70, "r1": 151.90, "r2": 158.60, "r3": 165.30,
          "nearest_resistance": 152.40,
          "reward_to_risk":     1.07,
        },
        "levels": {
          "ma20": 142.10, "ma50": 138.20, "ma200": 124.50,
          "week52_high": 149.99, "week52_low": 98.40,
          "swing_highs": [149.99, 147.20, 144.10],
          "swing_lows":  [137.20, 134.80, 130.10],
        },
        "atr": 3.32,
      }
    """
    # ── Choose entry source ────────────────────────────────────────────────
    setup = vcp_setup if (vcp_setup and vcp_setup.get("has_base")) else (
        powerplay_setup if (powerplay_setup and powerplay_setup.get("is_power_play")) else None
    )
    base_pivot = setup.get("pivot_buy_price") if setup else None
    base_stop  = setup.get("suggested_stop")  if setup else None

    # Aggressive entry: pivot if we have a base, else current close
    aggressive = float(base_pivot) if base_pivot else float(last_close)
    # Standard entry: pivot + 1% buffer (don't chase, wait for confirmed BO)
    standard = round(aggressive * 1.01, 2)
    # Pullback entry: 50d MA, only useful if we're currently above it
    ma20  = _moving_average(df, 20)
    ma50  = _moving_average(df, 50)
    ma200 = _moving_average(df, 200)
    pullback = float(ma50) if (ma50 and last_close > ma50) else None

    # ── Stop ───────────────────────────────────────────────────────────────
    atr = _atr(df, period=14)
    stop = _stops(aggressive, base_low=base_stop, atr=atr, hard_pct=hard_stop_pct)

    # ── Resistance / support / targets ─────────────────────────────────────
    week52_high, week52_low = _high_low(df, 252)
    swing_highs, swing_lows = _swing_highs_lows(df, lookback=5, n_max=5)
    # Nearest resistance ABOVE current price for target reasoning
    above = [px for px in (swing_highs + ([week52_high] if week52_high else []))
             if px and px > aggressive]
    nearest_resistance = min(above) if above else None
    targets = _targets(aggressive, stop["recommended"], nearest_resistance)

    # ── Pretty-print "buy zone" + "no-touch zone" for the UI ──────────────
    buy_zone = {
        "lo": round(aggressive, 2),
        "hi": round(aggressive * 1.025, 2),  # Minervini's 2.5% breakout range
    }
    return {
        "direction": direction,
        "entries": {
            "aggressive": round(aggressive, 2),
            "standard":   standard,
            "pullback":   round(pullback, 2) if pullback else None,
        },
        "entry_recommended_label": "aggressive",
        "entry_recommended":       round(aggressive, 2),
        "buy_zone":   buy_zone,
        "stop":       stop,
        "targets":    targets,
        "levels": {
            "ma20":          round(ma20, 2)  if ma20  else None,
            "ma50":          round(ma50, 2)  if ma50  else None,
            "ma200":         round(ma200, 2) if ma200 else None,
            "week52_high":   round(week52_high, 2) if week52_high else None,
            "week52_low":    round(week52_low, 2)  if week52_low  else None,
            "swing_highs":   [round(p, 2) for p in swing_highs],
            "swing_lows":    [round(p, 2) for p in swing_lows],
        },
        "atr":        round(atr, 2) if atr else None,
        "setup_source": setup.get("type") if setup else ("VCP" if base_pivot else "current_price"),
    }


def position_size(*, account_size: float, risk_pct: float,
                  entry: float, stop: float) -> dict:
    """Compute share count + dollar exposure for a given account-risk %.

    Risk-per-trade convention: pros use 0.5-1% of account per swing trade.
    With 1% risk on a $100k account, a 5% stop = $1,000 risked = $20,000
    notional position = ~140 shares of a $145 stock.
    """
    if entry <= 0 or stop >= entry:
        return {"shares": 0, "notional": 0, "dollars_risked": 0}
    dollars_risked = round(account_size * (risk_pct / 100.0), 2)
    per_share_risk = entry - stop
    shares = int(dollars_risked / per_share_risk) if per_share_risk > 0 else 0
    notional = round(shares * entry, 2)
    return {
        "shares":         shares,
        "notional":       notional,
        "dollars_risked": dollars_risked,
        "per_share_risk": round(per_share_risk, 2),
    }


__all__ = ["build_plan", "position_size", "MINERVINI_HARD_STOP_PCT", "ATR_STOP_MULTIPLIER"]
