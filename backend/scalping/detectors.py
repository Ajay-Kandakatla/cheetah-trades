"""Scalping detectors — Phase 1. Each is a pure function over today's 1-minute
RTH frame; each cites its source. Returns a signal dict (or None) in the shared
DaySignal shape so the existing IntradayChart can render it.

  • stocks_in_play_orb — Zarattini, Barbon & Aziz (2024), 'A Profitable Day
      Trading Strategy For The U.S. Equity Market', SSRN 4729284. The edge lives
      in the relative-volume 'stock in play' filter; 5-min opening range; ATR
      stop; EOD flat. Honest demerits in docs/scalping_methodology.md.
  • shock_fade — Zawadowski, Andor & Kertesz (2004), 'Short-term market reaction
      after extreme price changes of liquid stocks', arXiv cond-mat/0406696. Fade
      a PURE-intraday shock that clears BOTH an absolute (|move|>=4%) and a
      relative (>=8x own intraday sigma) filter; spread is the kill-switch; hard
      60-min time-stop. A 2000-2002 event study — gross opportunity, not a proven
      modern net edge.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from daytrading.indicators import opening_range

# Don't chase a breakout more than this far past the trigger (Minervini-style
# no-chase discipline; also keeps ORB entries honest vs a gap).
MAX_EXT_PAST_TRIGGER_PCT = 3.0
# Stocks-in-Play ORB
ORB_MINUTES = 5
ORB_ATR_MULT = 1.0                 # paper-aligned (QuantConnect used up to 1.4)
DOJI_PCT = 0.05                    # |5-min net| below this % = no clear direction
RELVOL_MIN = 1.0                   # 'stock in play' gate (paper: RelVol > 1.0)
# Shock fade
SHOCK_LOOKBACK_MIN = 20            # rolling window for the intraday move
SHOCK_MIN_MOVE_PCT = 4.0          # absolute filter
SHOCK_SIGMA_MULT = 8.0            # relative filter (x own intraday sigma)
SHOCK_TIME_STOP_MIN = 60          # edge is gone after ~60 min
EXCLUDE_OPEN_MIN = 5              # skip the first 5 min (opening effects)
EXCLUDE_CLOSE_MIN = 60           # skip the last 60 min (auction-dominated)


def _today_rth(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Most-recent ET trading day's RTH bars, with an `et` column attached."""
    if df is None or df.empty or "session" not in df.columns:
        return None
    rth = df[df["session"] == "rth"].copy()
    if rth.empty:
        return None
    et = rth.index.tz_localize("UTC").tz_convert("America/New_York")
    rth["_et"] = et
    most_recent = pd.Series(et.date, index=rth.index).max()
    today = rth[pd.Series(et.date, index=rth.index) == most_recent]
    return today if not today.empty else None


def _et_minute(ts_et) -> int:
    return ts_et.hour * 60 + ts_et.minute


def stocks_in_play_orb(
    df: pd.DataFrame,
    *,
    rel_vol: Optional[float],
    atr14: Optional[float],
    atr_mult: float = ORB_ATR_MULT,
    regime_bias: Optional[str] = None,
) -> Optional[dict]:
    """Zarattini Stocks-in-Play 5-min ORB for ONE name's today frame.

    Requires the RelVol 'stock in play' gate (>1.0). Direction = sign of the
    first 5-min bar's net (skip dojis). Buy-stop entry at the OR boundary, ATR
    stop, primary exit = EOD/stop. Returns a signal with `status` ∈
    {armed, triggered, too_extended} or None when it doesn't qualify."""
    today = _today_rth(df)
    if today is None or len(today) < ORB_MINUTES + 1:
        return None
    if rel_vol is None or rel_vol < RELVOL_MIN:
        return None                                    # not a 'stock in play'
    if not atr14 or atr14 <= 0:
        return None

    orb = opening_range(today, minutes=ORB_MINUTES)
    if not orb or not orb.get("complete"):
        return None
    oh, ol = orb["high"], orb["low"]
    if oh <= ol:
        return None

    window = today.iloc[:ORB_MINUTES]
    net_pct = (float(window.iloc[-1]["close"]) / float(window.iloc[0]["open"]) - 1.0) * 100.0
    if abs(net_pct) < DOJI_PCT:
        return None                                    # no clear opening direction

    last = today.iloc[-1]
    px = float(last["close"])
    side = "long" if net_pct > 0 else "short"
    trigger = oh if side == "long" else ol
    stop = (trigger - atr_mult * atr14) if side == "long" else (trigger + atr_mult * atr14)
    # Reference 1R target; the paper's primary exit is EOD/stop, surfaced in reasons.
    risk = abs(trigger - stop)
    target = (trigger + risk) if side == "long" else (trigger - risk)

    ext_past = ((px / trigger - 1.0) * 100.0) if side == "long" else ((trigger / px - 1.0) * 100.0)
    if side == "long":
        status = "armed" if px < trigger else ("triggered" if ext_past <= MAX_EXT_PAST_TRIGGER_PCT else "too_extended")
    else:
        status = "armed" if px > trigger else ("triggered" if ext_past <= MAX_EXT_PAST_TRIGGER_PCT else "too_extended")
    if status == "too_extended":
        return None                                    # already ran — don't chase

    risk_pct = abs(trigger - stop) / trigger * 100.0
    reward_pct = abs(target - trigger) / trigger * 100.0
    aligned = regime_bias in (None, "pending", "stand_aside") or \
        (regime_bias == "long_bias" and side == "long") or \
        (regime_bias == "short_bias" and side == "short")

    return {
        "strategy": "stocks_in_play_orb",
        "strategy_label": "Stocks-in-Play 5-min ORB",
        "side": side,
        "status": status,
        "entry": round(trigger, 4), "entry_price": round(trigger, 4),
        "stop": round(stop, 4), "target": round(target, 4),
        "last_price": round(px, 4),
        "risk_pct": round(risk_pct, 3), "reward_pct": round(reward_pct, 3),
        "rel_vol": round(rel_vol, 2), "atr14": round(atr14, 4),
        "orb_high": round(oh, 4), "orb_low": round(ol, 4),
        "regime_aligned": bool(aligned),
        "target_move_pct": round(reward_pct, 3),
        "source": "Zarattini, Barbon & Aziz (2024), SSRN 4729284",
        "reasons": [
            f"RelVol {rel_vol:.1f}× — a 'stock in play' (the paper's core filter)",
            f"5-min OR {ol:.2f}–{oh:.2f}; opening bar {net_pct:+.2f}% → {side} bias",
            f"Buy-stop at {trigger:.2f}, ATR stop {stop:.2f} ({atr_mult:g}×ATR)",
            "Primary exit is end-of-day flat or stop (paper has no fixed target)",
        ] + ([] if aligned else ["⚠ Against the intraday-momentum regime — lower confidence"]),
    }


def shock_fade(
    df: pd.DataFrame,
    *,
    atr14: Optional[float] = None,
    lookback_min: int = SHOCK_LOOKBACK_MIN,
    min_move_pct: float = SHOCK_MIN_MOVE_PCT,
    sigma_mult: float = SHOCK_SIGMA_MULT,
) -> Optional[dict]:
    """Zawadowski volatility-normalized shock fade for ONE name's today frame.

    A shock = a PURE-intraday move over the last `lookback_min` that clears BOTH
    |move| >= min_move_pct AND |move| >= sigma_mult × the name's own intraday
    1-min return sigma scaled to the window. Excludes the first 5 / last 60 min.
    Fades the move; hard 60-min time-stop. Returns a signal or None.

    NOTE: the paper's sigma is a same-clock-window stdev over 60 prior days; here
    we approximate it from today's own 1-min returns (documented limitation)."""
    today = _today_rth(df)
    if today is None or len(today) < lookback_min + 10:
        return None

    last_ts_et = today.iloc[-1]["_et"]
    minute_of_day = _et_minute(last_ts_et)
    # Time-of-day exclusions (open effects + the hostile closing auction window).
    if minute_of_day < (9 * 60 + 30 + EXCLUDE_OPEN_MIN):
        return None
    if minute_of_day > (16 * 60 - EXCLUDE_CLOSE_MIN):
        return None

    closes = today["close"].astype(float)
    px = float(closes.iloc[-1])
    ref = float(closes.iloc[-(lookback_min + 1)])
    move_pct = (px / ref - 1.0) * 100.0

    # Baseline intraday sigma from BEFORE the shock window. The paper's sigma is a
    # NORMAL-vol baseline; computing it over today's full series would include the
    # shock bars, inflate sigma, and the 8x relative filter would never fire.
    baseline = closes.iloc[:-lookback_min]
    rets = baseline.pct_change().dropna() * 100.0
    sigma_1min = float(rets.std()) if len(rets) > 5 else None
    if not sigma_1min or sigma_1min <= 0:
        return None
    sigma_window = sigma_1min * math.sqrt(lookback_min)

    if abs(move_pct) < min_move_pct:
        return None                                    # absolute filter
    if abs(move_pct) < sigma_mult * sigma_window:
        return None                                    # relative filter

    # Fade the move. Entry ≈ current price (near the shock extreme), so the stop
    # is placed a FRACTION of the shock BEYOND entry (a new-extreme continuation),
    # not at the extreme itself — otherwise risk collapses to ~0 and R:R lies.
    side = "long" if move_pct < 0 else "short"
    shock_extreme = float(today["low"].iloc[-lookback_min:].min()) if side == "long" \
        else float(today["high"].iloc[-lookback_min:].max())
    stop_frac = abs(move_pct) * 0.30                    # 30% of the shock further against us
    revert_frac = abs(move_pct) * 0.40                  # target ~40% of the shock back
    if side == "long":
        stop = px * (1 - stop_frac / 100.0)
        target = px * (1 + revert_frac / 100.0)
    else:
        stop = px * (1 + stop_frac / 100.0)
        target = px * (1 - revert_frac / 100.0)
    risk_pct = abs(px - stop) / px * 100.0
    reward_pct = abs(target - px) / px * 100.0
    if risk_pct <= 0:
        return None

    return {
        "strategy": "shock_fade",
        "strategy_label": "Volatility-normalized shock fade",
        "side": side,
        "status": "triggered",
        "entry": round(px, 4), "entry_price": round(px, 4),
        "stop": round(stop, 4), "target": round(target, 4),
        "last_price": round(px, 4),
        "risk_pct": round(risk_pct, 3), "reward_pct": round(reward_pct, 3),
        "move_pct": round(move_pct, 2),
        "sigma_window_pct": round(sigma_window, 3),
        "sigma_multiple": round(abs(move_pct) / sigma_window, 1) if sigma_window else None,
        "atr14": round(atr14, 4) if atr14 else None,
        "time_stop_min": SHOCK_TIME_STOP_MIN,
        "target_move_pct": round(reward_pct, 3),
        "source": "Zawadowski, Andor & Kertesz (2004), arXiv cond-mat/0406696",
        "reasons": [
            f"{abs(move_pct):.1f}% {lookback_min}-min move = {abs(move_pct)/sigma_window:.1f}× own intraday σ",
            f"Pure-intraday shock (excl. first {EXCLUDE_OPEN_MIN} / last {EXCLUDE_CLOSE_MIN} min)",
            f"Fade {side}; hard {SHOCK_TIME_STOP_MIN}-min time-stop — edge decays fast",
            "⚠ 2000-2002 event study; the spread can eat the whole reversal — see the spread gate",
        ],
    }
