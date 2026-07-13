"""Minervini risk-management rules — Trade Like a Stock Market Wizard (2013),
Chapter 13 "Risk Management Part 2: How to Deal with and Control Risk"
(pp.291-315). Every constant and formula here traces to a printed page of the
book on this machine (backend/sepa/minervini.pdf, printed page = PDF page - 15).

This module is PURE: no I/O, no broker, no Mongo. The exit engine and the
entry path call into it so the math lives in exactly one place.

Source map (printed pages):
  p.295  Initial stop-loss is set BEFORE buying; sell the moment it's hit.
         Once a stock advances, raise the sell point (trailing/back stop).
  p.296  Once gain is a multiple of the stop, never let the position turn
         into a loss — move stop to breakeven or trail.
  p.298  Reward/risk must exceed 1:1; keep risk below your average gain.
  p.299  Rule of thumb: cut losses at one-half your average gain ("if your
         winning trades produce a gain of 15 percent on average, you should
         sell any declining stock at no more than 7.5 percent"). And: "not
         allow any stock to fall more than 10 percent before selling",
         no matter how large the average gain.
  p.301  "maintain at least a 2:1 win/loss ratio with an absolute maximum
         stop loss of no more than 10 percent. I shoot for 3:1."
  p.302  The stop is an absolute maximum: sell immediately, no exception.
  p.304  Losing streak: cut position size (5,000 -> 2,000 -> 1,000 shares);
         pyramid back up when the plan works again.
  p.304-305  Never average down ("only losers average losers").
  p.307  Scale in only in the direction of the trade.
  p.308  "When the price of a stock I own rises by three times my risk, I
         almost always move my stop up to at least breakeven." Example:
         buy $50, stop $47.50 (risk $2.50) -> at $57.50 move stop to $50.
         "never trust the first price unless the position shows you a profit."
  p.308-309  Do NOT widen stops for volatility — the opposite.
  p.311  Difficult market: "If you normally cut losses at 7 to 8 percent,
         cut them at 5 to 6 percent. ... If you normally take profits of 15
         to 20 percent on average, take profits at 10 to 12 percent." Get
         off margin, reduce position sizes and overall exposure.
  p.312  "between 4 and 6 stocks, and for large portfolios maybe as many as
         10 or 12". "If you're a true 2:1 trader, mathematically your
         optimal position size should be 25 percent (four stocks divided
         equally)."
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# ── Stops ────────────────────────────────────────────────────────────────
# p.299 + p.301: never, under any rule or override, risk more than 10%.
ABS_MAX_STOP_PCT = 10.0
# p.311: the normal-market stop band ("7 to 8 percent") and the
# difficult-market band ("5 to 6 percent").
NORMAL_STOP_BAND = (7.0, 8.0)
DIFFICULT_STOP_BAND = (5.0, 6.0)
# Default initial stop: low end of the normal band (Ajay's stated 7%,
# which sits exactly on the book's p.311 normal band).
DEFAULT_STOP_PCT = 7.0
# p.299: with a real trade history, the stop is one-half the average gain
# (still capped at ABS_MAX_STOP_PCT). Below this many closed trades the
# sample is noise and we stay on the band default.
HALF_AVG_GAIN_MIN_TRADES = 20

# ── Profit taking ────────────────────────────────────────────────────────
# p.301: "at least a 2:1 win/loss ratio ... I shoot for 3:1."
MIN_REWARD_RISK = 2.0
STRETCH_REWARD_RISK = 3.0
# p.311: profit bands — normal "15 to 20 percent", difficult "10 to 12".
NORMAL_PROFIT_BAND = (15.0, 20.0)
DIFFICULT_PROFIT_BAND = (10.0, 12.0)

# ── Ratchet ──────────────────────────────────────────────────────────────
# p.308: at 3x the initial risk, move the stop to at least breakeven.
BREAKEVEN_AT_RISK_MULTIPLE = 3.0

# ── Sizing ───────────────────────────────────────────────────────────────
# p.312: 4-6 stocks for a portfolio this size; optimal position for a true
# 2:1 trader is 25% of equity.
MAX_POSITIONS = 5
MAX_POSITION_FRACTION = 0.25
# p.304: losing streak -> cut size roughly in half, then again; pyramid
# back up one level per winner when the plan works again.
STREAK_HALVE_AFTER = 3            # consecutive full-stop losses
STREAK_MULTIPLIERS = (1.0, 0.5, 0.25)


@dataclass
class StopPlan:
    stop_pct: float          # distance below entry, percent
    stop_price: float
    basis: str               # which book rule produced it


def regime_bands(regime: str) -> tuple:
    """p.311 — band selection. regime is 'normal' or 'difficult'."""
    if regime == "difficult":
        return DIFFICULT_STOP_BAND, DIFFICULT_PROFIT_BAND
    return NORMAL_STOP_BAND, NORMAL_PROFIT_BAND


def initial_stop(entry_price: float, regime: str = "normal",
                 avg_gain_pct: float | None = None,
                 closed_trades: int = 0,
                 requested_pct: float | None = None) -> StopPlan:
    """Initial stop per pp.299/301/311.

    Precedence: an explicit request (clamped), else half-average-gain once
    there's a real sample (p.299), else the regime band default. Everything
    is clamped to ABS_MAX_STOP_PCT — the p.299/p.301 hard cap — and to the
    regime band's loose end so a 'difficult' tape can only tighten, never
    widen (p.308-309).
    """
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    stop_band, _ = regime_bands(regime)

    if requested_pct is not None:
        pct = float(requested_pct)
        basis = "requested"
    elif avg_gain_pct is not None and closed_trades >= HALF_AVG_GAIN_MIN_TRADES:
        pct = avg_gain_pct / 2.0                      # p.299 rule of thumb
        basis = "half_avg_gain_p299"
    else:
        pct = DEFAULT_STOP_PCT if regime == "normal" else stop_band[1]
        basis = f"band_default_{regime}_p311"

    # p.308-309: stops never widen past the regime band's loose end...
    pct = min(pct, stop_band[1] if regime == "difficult" else ABS_MAX_STOP_PCT)
    # ...and p.299/p.301: the 10% line is absolute.
    pct = min(pct, ABS_MAX_STOP_PCT)
    # Floor: a stop tighter than 1% is a data error, not a plan.
    pct = max(pct, 1.0)
    stop_price = round(entry_price * (1 - pct / 100.0), 2)
    if stop_price >= entry_price:
        # Sub-dollar entries: the cent grid can collapse the stop onto the
        # entry (zero risk). Alpaca accepts 4 decimals below $1.
        stop_price = round(entry_price * (1 - pct / 100.0), 4)
    return StopPlan(stop_pct=round(pct, 2), stop_price=stop_price, basis=basis)


def profit_target(entry_price: float, stop_pct: float,
                  regime: str = "normal") -> dict:
    """Sell-into-strength limit per p.301 (>=2:1) and p.311 (bands).

    Target percent = at least MIN_REWARD_RISK x the stop distance, lifted to
    the regime profit band's floor if 2:1 lands below it. The 2:1 minimum is
    never violated (p.301); the band cap is only applied when it doesn't
    break 2:1.
    """
    _, profit_band = regime_bands(regime)
    pct = max(MIN_REWARD_RISK * stop_pct, profit_band[0])
    if pct > profit_band[1] and profit_band[1] >= MIN_REWARD_RISK * stop_pct:
        pct = profit_band[1]
    return {"target_pct": round(pct, 2),
            "target_price": round(entry_price * (1 + pct / 100.0), 2),
            "reward_risk": round(pct / stop_pct, 2)}


def breakeven_trigger(entry_price: float, stop_price: float) -> float:
    """p.308 — the price at which the stop moves to breakeven: entry plus
    BREAKEVEN_AT_RISK_MULTIPLE x the initial per-share risk. Book example:
    buy $50, stop $47.50 -> trigger $57.50."""
    risk = entry_price - stop_price
    if risk <= 0:
        raise ValueError("stop must be below entry")
    return round(entry_price + BREAKEVEN_AT_RISK_MULTIPLE * risk, 2)


def size_multiplier(consecutive_losses: int) -> float:
    """p.304 — halve after STREAK_HALVE_AFTER consecutive losses, halve
    again after another streak of the same length. A win steps back up one
    level (handled by the caller resetting/decrementing the counter)."""
    level = min(consecutive_losses // STREAK_HALVE_AFTER,
                len(STREAK_MULTIPLIERS) - 1)
    return STREAK_MULTIPLIERS[level]


def position_size(equity: float, entry_price: float,
                  consecutive_losses: int = 0,
                  extra_multiplier: float = 1.0) -> dict:
    """p.312 — 25% of equity per position (optimal for a 2:1 trader),
    scaled down by the p.304 losing-streak multiplier. Whole shares only
    (Alpaca bracket orders don't take fractional qty).

    `extra_multiplier` is the progressive-exposure governor
    (trading/progressive.py, TLSW pp.307-308 pilot buys — added 2026-07-12).
    It composes via min(): the MOST CONSERVATIVE governor wins, the two
    never multiply into a number neither rule owns. Out-of-range values
    degrade to 1.0 (no effect) — this function's book math is unchanged
    when the param is omitted."""
    if equity <= 0 or entry_price <= 0:
        return {"shares": 0, "allocation": 0.0, "multiplier": 1.0}
    mult = size_multiplier(consecutive_losses)
    try:
        extra = float(extra_multiplier)
    except (TypeError, ValueError):
        extra = 1.0
    if 0.0 < extra <= 1.0:
        mult = min(mult, extra)
    alloc = equity * MAX_POSITION_FRACTION * mult
    shares = int(math.floor(alloc / entry_price))
    return {"shares": shares,
            "allocation": round(shares * entry_price, 2),
            "multiplier": mult}


def may_add_to_position(avg_cost: float, current_price: float) -> bool:
    """pp.304-305 + p.308 — never average down; add only in the direction
    of the trade, only when the position shows a profit."""
    return current_price > avg_cost


def equity_risk_pct(stop_pct: float,
                    position_fraction: float = MAX_POSITION_FRACTION) -> float:
    """Account-level risk of one full-size trade: position fraction x stop
    distance. At the defaults (25% x 7%) that's 1.75% of equity per trade."""
    return round(position_fraction * stop_pct, 4)
