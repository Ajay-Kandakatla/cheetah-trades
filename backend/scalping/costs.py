"""Net-of-cost model — the honesty layer the research said is non-negotiable.

The realism survey was blunt: for a few-cents target, the bid-ask SPREAD plus
slippage is what kills the edge, and ~80-99% of retail day-traders net lose
after costs. So every scalping signal is shown GROSS beside NET, and we surface
the win rate it would need just to break even after a conservative cost stack.

Cost components (round-trip, as % of entry price), all configurable:
  • spread      — you cross the bid-ask. Taking liquidity both sides ≈ pay the
                  full quoted spread round-trip (we use the live NBBO spread when
                  available; otherwise it's flagged unknown, never assumed zero).
  • slippage    — adverse fill beyond the quote, each side (default 5 bps/side).
  • commission  — per-share; the Zarattini paper modeled $0.0035/share.
  • fees        — SEC Section 31 + FINRA TAF on the sell side (tiny but real).
  • borrow      — short-locate cost for shorts (small for a same-day hold).

These are CONFIGURED conservative defaults (cited to the realism survey + the
Zarattini commission), NOT a book formula. Pure + unit-tested.
"""
from __future__ import annotations

from typing import Optional

# Per-share commission — Zarattini, Barbon & Aziz (2024) modeled this exactly.
COMMISSION_PER_SHARE = 0.0035
# Adverse fill beyond the quote, EACH side. Conservative retail assumption.
DEFAULT_SLIPPAGE_BPS_PER_SIDE = 5.0
# SEC Section 31 fee (sell side, % of notional) — periodically reset; ~2024-26 level.
SEC_FEE_PCT_SELL = 0.0000278 * 100        # as a percent of sell notional
# FINRA Trading Activity Fee (sell side, per share, capped).
FINRA_TAF_PER_SHARE_SELL = 0.000166
# Short-borrow assumption for an intraday short (% of notional for the hold).
DEFAULT_SHORT_BORROW_PCT = 0.02


def round_trip_cost_pct(
    entry_price: float,
    *,
    spread_pct: Optional[float] = None,
    slippage_bps_per_side: float = DEFAULT_SLIPPAGE_BPS_PER_SIDE,
    commission_per_share: float = COMMISSION_PER_SHARE,
    is_short: bool = False,
    short_borrow_pct: float = DEFAULT_SHORT_BORROW_PCT,
) -> dict:
    """Round-trip cost as a % of entry price, with a per-component breakdown.

    `spread_pct` is the live quoted spread as a % of price; when None the spread
    cost is reported as None (UNKNOWN — never silently treated as zero) and the
    total carries a `spread_known=False` flag so the UI can warn.
    """
    if not entry_price or entry_price <= 0:
        return {"total_pct": None, "spread_known": False, "breakdown": {}}

    slip = 2.0 * (slippage_bps_per_side / 100.0)            # both sides, % of price
    commission = 2.0 * (commission_per_share / entry_price) * 100.0   # buy + sell
    sec = SEC_FEE_PCT_SELL                                  # sell side only
    taf = (FINRA_TAF_PER_SHARE_SELL / entry_price) * 100.0  # sell side only
    borrow = short_borrow_pct if is_short else 0.0

    breakdown = {
        "spread_pct": round(spread_pct, 4) if spread_pct is not None else None,
        "slippage_pct": round(slip, 4),
        "commission_pct": round(commission, 4),
        "fees_pct": round(sec + taf, 5),
        "borrow_pct": round(borrow, 4) if is_short else 0.0,
    }
    known = spread_pct if spread_pct is not None else 0.0
    total = known + slip + commission + sec + taf + borrow
    return {
        "total_pct": round(total, 4),
        "spread_known": spread_pct is not None,
        "breakdown": breakdown,
    }


def breakeven_win_rate(reward_pct: float, risk_pct: float, cost_pct: Optional[float]) -> Optional[float]:
    """The win rate a fixed reward/risk trade needs just to break even AFTER the
    round-trip cost is paid on every trade.

    E[net] = p*(reward) + (1-p)*(-risk) - cost = 0
        => p* = (risk + cost) / (reward + risk)

    Returns p* as a percent (0-100), or None if undefined. p* > 100 means the
    setup can't break even at this reward/risk no matter the hit-rate.
    """
    if reward_pct is None or risk_pct is None or cost_pct is None:
        return None
    denom = reward_pct + risk_pct
    if denom <= 0:
        return None
    p = (risk_pct + cost_pct) / denom
    return round(p * 100.0, 1)


def annotate_net_of_cost(signal: dict, spread_pct: Optional[float]) -> dict:
    """Attach a `net_of_cost` block to a signal dict (gross beside net).

    Adds: round-trip cost %, the breakeven win rate after costs, and a candid
    one-line verdict. Mutates and returns `signal`.
    """
    entry = signal.get("entry_price") or signal.get("entry")
    reward = signal.get("reward_pct")
    risk = signal.get("risk_pct")
    is_short = signal.get("side") == "short"
    cost = round_trip_cost_pct(entry, spread_pct=spread_pct, is_short=is_short)
    be = breakeven_win_rate(reward, risk, cost.get("total_pct"))

    note = "Spread unknown — assume you pay it; treat any edge as unproven."
    if cost.get("spread_known"):
        if be is None:
            note = "Reward/risk undefined — can't price the edge."
        elif be >= 100:
            note = f"Can't break even at this R:R after costs (needs {be}% wins)."
        elif be >= 60:
            note = f"Needs ≥{be}% wins just to break even after costs — steep."
        else:
            note = f"Breaks even at {be}% wins after costs; gross R:R flatters this."

    signal["net_of_cost"] = {
        "round_trip_cost_pct": cost.get("total_pct"),
        "spread_known": cost.get("spread_known"),
        "cost_breakdown": cost.get("breakdown"),
        "breakeven_win_rate_pct": be,
        "verdict": note,
    }
    return signal
