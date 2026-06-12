"""Auto-Pilot risk-rule behavior — synthetic inputs, stdlib only, no network.

Locks backend/trading/risk_rules.py to Minervini, *Trade Like a Stock Market
Wizard* (2013), Ch.13 pp.291-315 — the contract in
docs/sepa/risk_management_methodology.md. Every test cites the printed page
it encodes. risk_rules.py is the single owner of this math (the exit engine
and the entry path call into it); any change here is a Rule #4 methodology
change.

Host-runnable (py3.9, no pandas/numpy):
    cd backend && python3 -m pytest tests/test_risk_rules.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trading.risk_rules import (
    ABS_MAX_STOP_PCT,
    BREAKEVEN_AT_RISK_MULTIPLE,
    DEFAULT_STOP_PCT,
    DIFFICULT_STOP_BAND,
    HALF_AVG_GAIN_MIN_TRADES,
    MAX_POSITION_FRACTION,
    MAX_POSITIONS,
    MIN_REWARD_RISK,
    NORMAL_STOP_BAND,
    STREAK_HALVE_AFTER,
    breakeven_trigger,
    equity_risk_pct,
    initial_stop,
    may_add_to_position,
    position_size,
    profit_target,
    size_multiplier,
)


# ── p.308 worked example — the book's own numbers, EXACT ────────────────────

def test_p308_worked_example_exact():
    """p.308 verbatim: buy $50, stop $47.50 (risk $2.50) -> at $57.50 move
    the stop to $50 (breakeven). The engine must reproduce the book's own
    example to the penny."""
    plan = initial_stop(50.0, requested_pct=5)
    assert plan.stop_pct == 5.0
    assert plan.stop_price == 47.50
    assert plan.basis == "requested"
    assert breakeven_trigger(50.0, 47.50) == 57.50


def test_breakeven_multiple_is_3x_risk():
    """p.308 — trigger = entry + 3 x initial per-share risk, any scale."""
    assert BREAKEVEN_AT_RISK_MULTIPLE == 3.0
    assert breakeven_trigger(100.0, 93.0) == 121.0      # 7% stop -> +21%
    assert breakeven_trigger(20.0, 18.80) == 23.60      # 6% stop on a $20 name


def test_breakeven_trigger_rejects_stop_at_or_above_entry():
    """A stop at/above entry means zero/negative risk — data error, not a plan."""
    with pytest.raises(ValueError):
        breakeven_trigger(50.0, 50.0)
    with pytest.raises(ValueError):
        breakeven_trigger(50.0, 51.0)


# ── 10% absolute cap (p.299 + p.301) ────────────────────────────────────────

def test_half_avg_gain_is_capped_at_10pct():
    """p.299: '...not allow any stock to fall more than 10 percent before
    selling', no matter how large the average gain. avg gain 30% with a real
    sample wants 15% — the cap holds it at 10%."""
    plan = initial_stop(100.0, avg_gain_pct=30.0, closed_trades=50)
    assert plan.stop_pct == 10.0
    assert plan.stop_price == 90.0
    assert plan.basis == "half_avg_gain_p299"


def test_requested_stop_is_capped_at_10pct():
    """p.301: 'an absolute maximum stop loss of no more than 10 percent' —
    a 12% user request is clamped, never honored."""
    plan = initial_stop(100.0, requested_pct=12)
    assert plan.stop_pct == 10.0
    assert plan.stop_price == 90.0


def test_grid_sweep_stop_never_exceeds_10pct():
    """Sweep entry prices x regimes x every basis (requested / half-avg-gain /
    band default): stop_pct <= 10.0 ALWAYS, and the stop price is always
    strictly below entry (p.299/p.301 hard cap)."""
    entries = (2.5, 18.66, 50.0, 100.0, 333.0, 1234.56)
    for entry in entries:
        for regime in ("normal", "difficult"):
            plans = [initial_stop(entry, regime)]
            for req in (1, 2.5, 5, 7, 7.9, 9.9, 10, 12, 25, 99):
                plans.append(initial_stop(entry, regime, requested_pct=req))
            for avg_gain in (4.0, 8.0, 15.0, 30.0, 64.0):
                for n in (0, 19, 20, 500):
                    plans.append(initial_stop(entry, regime,
                                              avg_gain_pct=avg_gain,
                                              closed_trades=n))
            for plan in plans:
                assert plan.stop_pct <= ABS_MAX_STOP_PCT, (
                    f"stop {plan.stop_pct}% breached the p.299/p.301 10% cap "
                    f"(entry={entry}, regime={regime}, basis={plan.basis})"
                )
                assert plan.stop_pct >= 1.0          # data-error floor
                assert plan.stop_price < entry


def test_stop_rejects_nonpositive_entry():
    with pytest.raises(ValueError):
        initial_stop(0.0)
    with pytest.raises(ValueError):
        initial_stop(-5.0)


# ── Half-average-gain rule (p.299) ──────────────────────────────────────────

def test_half_avg_gain_with_real_sample():
    """p.299 verbatim: winners average 15% -> sell decliners at no more than
    7.5%. Needs a real sample (>= 20 closed trades)."""
    assert HALF_AVG_GAIN_MIN_TRADES == 20
    plan = initial_stop(100.0, avg_gain_pct=15.0, closed_trades=20)
    assert plan.stop_pct == 7.5
    assert plan.stop_price == 92.5
    assert plan.basis == "half_avg_gain_p299"


def test_thin_sample_falls_back_to_band_default():
    """19 closed trades is noise, not a sample — stay on the p.311 normal-band
    default of 7% (Rule #1: never invent a statistic from thin data)."""
    plan = initial_stop(100.0, avg_gain_pct=15.0, closed_trades=19)
    assert plan.stop_pct == DEFAULT_STOP_PCT == 7.0
    assert plan.basis == "band_default_normal_p311"


# ── Difficult regime can only tighten (p.311 + p.308-309) ───────────────────

def test_difficult_default_within_5_to_6_band():
    """p.311: 'If you normally cut losses at 7 to 8 percent, cut them at
    5 to 6 percent.'"""
    plan = initial_stop(100.0, "difficult")
    assert plan.stop_pct <= DIFFICULT_STOP_BAND[1] == 6.0
    assert plan.stop_pct >= DIFFICULT_STOP_BAND[0] == 5.0


def test_difficult_clamps_wide_request_to_6():
    """p.308-309: never widen stops. A 9% request in a difficult tape is
    clamped to the band's loose end (6%), not honored."""
    plan = initial_stop(100.0, "difficult", requested_pct=9)
    assert plan.stop_pct == 6.0
    assert plan.stop_price == 94.0


def test_difficult_clamps_half_avg_gain_too():
    """The p.299 half-average-gain stop is also bound by the difficult band —
    no basis may widen risk in a bad tape."""
    plan = initial_stop(100.0, "difficult", avg_gain_pct=30.0, closed_trades=40)
    assert plan.stop_pct == 6.0


def test_difficult_honors_tighter_request():
    """Tightening is always allowed (p.308-309 goes one direction only)."""
    plan = initial_stop(100.0, "difficult", requested_pct=4)
    assert plan.stop_pct == 4.0


# ── Profit targets (p.301 2:1 floor + p.311 bands) ──────────────────────────

def test_profit_target_normal_7pct_stop():
    """Normal regime, 7% stop: 2:1 says 14%, but the p.311 normal profit band
    floor (15%) lifts it — and reward:risk stays >= 2."""
    t = profit_target(100.0, 7.0, "normal")
    assert t["target_pct"] == 15.0
    assert t["target_price"] == 115.0
    assert t["reward_risk"] >= MIN_REWARD_RISK


def test_profit_target_difficult_5p5_stop():
    """Difficult regime, 5.5% stop: 2:1 -> 11%, inside the p.311 difficult
    band (10-12) -> taken as-is at exactly 2:1."""
    t = profit_target(100.0, 5.5, "difficult")
    assert t["target_pct"] == 11.0
    assert t["target_price"] == 111.0
    assert t["reward_risk"] == 2.0


def test_reward_risk_never_below_2_full_sweep():
    """p.301: 'at least a 2:1 win/loss ratio' — for EVERY band/stop combination
    the target keeps reward:risk >= 2.0. The band cap may only apply when it
    does not break 2:1."""
    for regime in ("normal", "difficult"):
        for i in range(10, 101):                      # stops 1.00% .. 10.00%
            stop = i / 10.0
            t = profit_target(100.0, stop, regime)
            assert t["reward_risk"] >= MIN_REWARD_RISK, (
                f"regime={regime} stop={stop}%: reward_risk "
                f"{t['reward_risk']} < 2.0 violates p.301"
            )
            assert t["target_price"] > 100.0


# ── Position sizing (p.312) + losing-streak governor (p.304) ────────────────

def test_position_size_25pct_of_equity():
    """p.312: 'your optimal position size should be 25 percent' —
    $20,000 equity at $50 -> 100 shares = $5,000 = exactly 25%."""
    s = position_size(20000.0, 50.0)
    assert s["shares"] == 100
    assert s["allocation"] == 5000.0
    assert s["allocation"] / 20000.0 == MAX_POSITION_FRACTION == 0.25
    assert s["multiplier"] == 1.0


def test_position_size_whole_shares_only():
    """Alpaca bracket orders take whole shares — floor, never round up."""
    s = position_size(20000.0, 333.0)
    assert s["shares"] == 15                      # floor(5000 / 333) = 15
    assert s["allocation"] == 4995.0
    assert s["allocation"] <= 20000.0 * MAX_POSITION_FRACTION


def test_streak_multiplier_ladder():
    """p.304: cut size after a losing streak (5,000 -> 2,000 -> 1,000 shares
    in the book's example): 0-2 losses full size, 3-5 half, 6+ quarter."""
    assert STREAK_HALVE_AFTER == 3
    for n in (0, 1, 2):
        assert size_multiplier(n) == 1.0
    for n in (3, 4, 5):
        assert size_multiplier(n) == 0.5
    for n in (6, 7, 9, 30):
        assert size_multiplier(n) == 0.25         # floor of the ladder


def test_streak_scales_position_size():
    assert position_size(20000.0, 50.0, consecutive_losses=3)["shares"] == 50
    assert position_size(20000.0, 50.0, consecutive_losses=6)["shares"] == 25


def test_position_size_degenerate_inputs():
    assert position_size(0.0, 50.0)["shares"] == 0
    assert position_size(20000.0, 0.0)["shares"] == 0


def test_max_positions_is_5():
    """p.312: 'between 4 and 6 stocks' — engine cap locked at 5."""
    assert MAX_POSITIONS == 5


# ── Never average down (pp.304-305 + p.308) ─────────────────────────────────

def test_may_add_to_position():
    """pp.304-305: 'only losers average losers'; p.308: 'never trust the
    first price unless the position shows you a profit'. Below avg cost:
    never add. At avg cost: no profit shown — still no. Above: allowed."""
    assert may_add_to_position(100.0, 99.0) is False
    assert may_add_to_position(100.0, 100.0) is False
    assert may_add_to_position(100.0, 101.0) is True


# ── Regression: sub-dollar cent-rounding degeneracy ─────────────────────────
# initial_stop() used to round stop_price to 2 decimals unconditionally, so
# for sub-dollar entries the cent grid could collapse the stop ONTO the entry
# (zero risk) and breakeven_trigger then raised, which would have crashed a
# reconciler tick. Fixed 2026-06-11: sub-dollar stops round to 4 decimals
# (Alpaca's sub-$1 grid). The 10% cap contract was never affected.

def test_subdollar_stop_rounding_keeps_stop_below_entry():
    """A stop plan must always carry positive per-share risk."""
    plan = initial_stop(0.37, requested_pct=1)
    assert plan.stop_price < 0.37
    breakeven_trigger(0.37, plan.stop_price)      # must not raise


# ── Account-level risk ──────────────────────────────────────────────────────

def test_equity_risk_pct_default_is_1_75():
    """25% position x 7% stop = 1.75% of equity at risk per trade —
    the number /trading/preview surfaces."""
    assert equity_risk_pct(DEFAULT_STOP_PCT) == 1.75
    assert equity_risk_pct(10.0) == 2.5           # worst-case at the hard cap
    assert NORMAL_STOP_BAND == (7.0, 8.0)
