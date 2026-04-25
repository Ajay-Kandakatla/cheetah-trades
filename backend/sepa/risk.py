"""Position sizing + stop placement — Minervini risk rules (Ch 12-13).

Key numbers from the book:
  - Max stop: 10% (absolute line in the sand).
  - Avg loss target: 6-7%.
  - Min reward/risk: 2:1. Aim for 3:1.
  - Account risk per trade: 0.5%-2% (we default to 1%).
  - 4-6 positions ideal; max 10-20.
  - Move stop to breakeven when gain = 3x risk.
  - Pyramid up on winners; never average down.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PositionPlan:
    entry: float
    stop: float
    risk_per_share: float
    risk_pct: float                # stop distance as % of entry
    shares: int
    dollar_risk: float
    dollar_position: float
    position_pct_of_account: float
    reward_target_2r: float
    reward_target_3r: float
    move_stop_to_breakeven_at: float
    warnings: list[str]

    def to_dict(self) -> dict:
        return {**self.__dict__}


def plan_position(
    entry: float,
    stop: float,
    account_size: float,
    risk_per_trade_pct: float = 1.0,
    max_stop_pct: float = 10.0,
    max_position_pct: float = 25.0,
) -> Optional[PositionPlan]:
    if entry <= 0 or stop <= 0 or stop >= entry or account_size <= 0:
        return None
    risk_per_share = entry - stop
    risk_pct = risk_per_share / entry * 100
    warnings: list[str] = []
    if risk_pct > max_stop_pct:
        warnings.append(
            f"Stop distance {risk_pct:.1f}% exceeds max {max_stop_pct}% — "
            "tighten stop or pass the trade."
        )
    if risk_pct > 7:
        warnings.append("Stop wider than 7% — book targets avg loss 6-7% (p.276).")

    dollar_risk = account_size * (risk_per_trade_pct / 100.0)
    shares = int(dollar_risk // risk_per_share) if risk_per_share > 0 else 0
    dollar_position = shares * entry
    position_pct = dollar_position / account_size * 100 if account_size else 0

    # Cap position by max_position_pct
    if position_pct > max_position_pct:
        capped_dollar = account_size * (max_position_pct / 100)
        shares = int(capped_dollar // entry)
        dollar_position = shares * entry
        position_pct = dollar_position / account_size * 100
        dollar_risk = shares * risk_per_share
        warnings.append(f"Position size capped at {max_position_pct}% of account.")

    return PositionPlan(
        entry=round(entry, 4),
        stop=round(stop, 4),
        risk_per_share=round(risk_per_share, 4),
        risk_pct=round(risk_pct, 2),
        shares=shares,
        dollar_risk=round(dollar_risk, 2),
        dollar_position=round(dollar_position, 2),
        position_pct_of_account=round(position_pct, 2),
        reward_target_2r=round(entry + 2 * risk_per_share, 4),
        reward_target_3r=round(entry + 3 * risk_per_share, 4),
        move_stop_to_breakeven_at=round(entry + 3 * risk_per_share, 4),
        warnings=warnings,
    )
