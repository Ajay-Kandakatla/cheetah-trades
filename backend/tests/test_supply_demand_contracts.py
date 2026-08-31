"""Regression tests for the /supply-demand page contracts.

See `docs/supply_demand/broken_band_guard.md` and
`docs/supply_demand/demand_reentry_methodology.md` for the spec these enforce.
Run before AND after any supply/demand change to prove nothing drifted:

    docker compose exec api python -m pytest /app/tests/test_supply_demand_contracts.py -v

Tests are intentionally cheap — no Massive calls, no Mongo, no price cache.
Constants are asserted by re-importing the module; behaviour lives in
`test_demand_reentry.py`.

WHY THIS FILE EXISTS SEPARATELY FROM test_sepa_contracts.py
-----------------------------------------------------------
This surface is deliberately NOT Minervini. Ajay 2026-08-13: *"The Supply
demand are outside of this strategy… Oh ignore the minervini for this please"*.
Every threshold here is a CONFIGURED house value with no page cite, and mixing
them into the SEPA contracts file would blur the one boundary the module
docstring works hardest to keep.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import demand_reentry as dr
from supply_demand import price_zones as pz


# ── the qualification rule ────────────────────────────────────────────────────
def test_reentry_requires_a_rise_a_prior_visit_above_AND_an_unbroken_band():
    """The whole gate, in one place. Adding a fourth condition or dropping the
    break check should fail here loudly rather than quietly change the board."""
    src = inspect.getsource(dr.reentry_read)
    assert 'out["is_reentry"] = bool(rise >= min_rise_pct and above_idx' in src
    assert 'and not out["broke_below"]' in src


def test_the_board_row_still_ANDs_in_the_trend_and_quality_gates():
    src = inspect.getsource(dr.decide_from_frame)
    assert '"is_reentry": bool(band["is_reentry"] and trend_ok and quality_ok)' in src


def test_reentry_geometry_constants_locked():
    """House values, measured on the 2026-08-13 S&P 500 walk-forward. Changing
    one changes the board — it needs a re-measure, not a nudge."""
    assert dr.SWING_WINDOW == 5
    assert dr.MERGE_PCT == 4.0
    assert dr.HALF_WIDTH_PCT == 1.75
    assert dr.REENTRY_LOOKBACK_BARS == 40
    assert dr.MIN_RISE_ABOVE_PCT == 5.0
    assert dr.MIN_TOUCHES == 2
    assert dr.MIN_ZONE_STRENGTH == 40.0
    assert dr.MIN_BARS == 220


def test_zones_page_defaults_are_not_this_modules_defaults():
    """`demand_reentry` passes wider geometry per-call. If it ever mutated the
    shared defaults, the /zones page silently changes with it."""
    assert pz.ZONE_MERGE_PCT != dr.MERGE_PCT
    assert pz.ZONE_HALF_WIDTH_PCT != dr.HALF_WIDTH_PCT


# ── the plan ──────────────────────────────────────────────────────────────────
def test_stop_and_stop_hit_constants_locked():
    assert dr.STOP_BUFFER_PCT == 1.5
    assert dr.STOP_HIT_LOOKBACK_BARS == 10


def test_the_stop_cap_is_IMPORTED_from_risk_rules_never_redeclared():
    """The p.299/p.301 hard cap has exactly one home. A local copy here is how
    two surfaces start disagreeing about the same trade."""
    src = inspect.getsource(dr.trade_plan)
    assert "from trading.risk_rules import ABS_MAX_STOP_PCT" in src
    assert "ABS_MAX_STOP_PCT =" not in inspect.getsource(dr)


def test_the_plan_payload_shape_is_stable():
    """The FE destructures these. A rename is a broken page, not a type error —
    there is no shared schema between the two sides."""
    p = dr.trade_plan(103.0, {"lo": 100.0, "hi": 106.0}, {"lo": 120.0},
                      recent_lows=[102.0, 97.0])
    assert set(p) == {
        "entry_low", "entry_high", "entry_ref", "stop", "risk_pct",
        "target", "reward_pct", "rr", "risk_exceeds_max", "max_stop_pct",
        "stop_recently_hit", "bars_since_stop_hit", "lowest_low_pct_below_stop",
        "stop_hit_lookback_bars",
        # 2026-08-31: `rr` is measured at spot but the card instructs a BAND.
        # These report R:R at the worst fill the plan permits. See
        # docs/supply_demand/demand_reentry_methodology.md.
        "rr_at_entry_high", "thin_across_band", "thin_band_rr",
    }


def test_the_reentry_read_payload_shape_is_stable():
    out = dr.reentry_read([100, 110, 120, 103], 106, 100, 103)
    assert set(out) == {"is_reentry", "fell_from_pct", "bars_since_above",
                        "in_band", "broke_below", "bars_since_break",
                        "lowest_close_pct_below"}


def test_the_already_run_stop_WARNS_and_never_gates():
    """Deliberate asymmetry (Ajay 2026-08-17). A broken band invalidates the
    ZONE, so it is a gate. An already-run stop is a fact about the PLAN — he
    may still want the name on the board with the caveat attached."""
    src = inspect.getsource(dr.decide_from_frame)
    assert "stop_recently_hit" not in src, \
        "the stop-hit flag must not feed is_reentry or any board filter"


def test_the_stop_check_is_fed_LOWS_and_the_band_check_is_fed_CLOSES():
    """The two rules read different evidence on purpose: a stop is an intraday
    order (a wick fills it), a broken band is a closing-basis judgement (a wick
    is how support gets tested). Swapping them inverts both."""
    src = inspect.getsource(dr.decide_from_frame)
    assert "recent_lows=[float(x) for x in lows_s.tolist()]" in src
    assert "reentry_read(closes," in src


# ── the snapshot/transition boundary ──────────────────────────────────────────
def test_price_zones_stays_a_pure_SNAPSHOT_with_no_break_history():
    """`price_zones` answers 'where is price relative to the bands today'. Give
    it history and every /zones read, every chart-maps tile and the stocks
    screen start depending on the re-entry rules."""
    src = inspect.getsource(pz)
    for forbidden in ("broke_below", "DEMAND_BROKEN", "is_reentry"):
        assert forbidden not in src, f"price_zones reaches for {forbidden}"


def test_the_downgrade_only_ever_touches_AT_DEMAND():
    src = inspect.getsource(dr._verdict_after_break)
    assert 'verdict.get("state") != "AT_DEMAND"' in src


def test_decide_from_frame_stays_pure_so_the_backtest_scores_the_same_rule():
    """Duplicated from test_zone_backtest.py on purpose — this is the property
    that lets the walk-forward measure the live rule, and it is easy to break
    from the demand_reentry side without ever opening the backtest tests."""
    src = inspect.getsource(dr.decide_from_frame)
    for forbidden in ("load_prices", "datetime.now", "time.time", "_cache",
                      "cached_or_warm", "fetch_trades"):
        assert forbidden not in src, f"decide_from_frame reaches for {forbidden}"


# ── liquidity: one scale, shared with /chart-maps ─────────────────────────────
def test_liquidity_tier_thresholds_locked():
    assert dr.LIQ_DEEP_USD == 50_000_000.0
    assert dr.LIQ_OK_USD == 10_000_000.0
    assert dr.LIQ_THIN_USD == 2_000_000.0


def test_chart_maps_imports_the_tier_scale_rather_than_redeclaring_it():
    from chart_maps import board
    assert board.LIQ_DEEP_USD is dr.LIQ_DEEP_USD
    assert board.LIQ_OK_USD is dr.LIQ_OK_USD
    assert board.LIQ_THIN_USD is dr.LIQ_THIN_USD


# ── the reward:risk floor (2026-08-17) ────────────────────────────────────────
def test_rr_floor_constant_locked():
    assert dr.MIN_RR_DEFAULT == 1.0


def test_the_floor_filters_the_BOARD_and_never_the_structural_read():
    """Two different questions, two different fields. `is_reentry` = did price
    come back into a band it had left with the trend intact. The R:R floor = is
    the resulting PLAN worth taking. Folding the second into the first would
    also blind the walk-forward to the unfiltered cohort — which is where the
    measurement that justifies the floor came from."""
    src = inspect.getsource(dr.decide_from_frame)
    assert "meets_rr_floor" not in src and "min_rr" not in src


def test_the_floor_runs_at_read_time_not_inside_the_scan():
    """Otherwise the 3-hour cache holds one row set PER FLOOR VALUE, and moving
    the dropdown costs a fresh 3-minute universe pass."""
    assert "_apply_rr_floor" not in inspect.getsource(dr.scan)
    assert "_apply_rr_floor" in inspect.getsource(dr.cached_or_warm)


def test_an_unknown_reward_risk_FAILS_a_real_floor():
    """Consistent with the chart-maps liquidity tier: the one we could not
    measure must not be the one that shows up unfiltered."""
    assert dr.meets_rr_floor({"rr": None}, 1.0) is False
    assert dr.meets_rr_floor(None, 1.0) is False


def test_the_documented_default_is_not_the_backtests_best_cell():
    """A guard against a future 'optimisation'. 1.25 measured better on the
    737-observation sample; it is not the default because excess-vs-SPY is NOT
    monotone across the sweep, making the peak a fitted number rather than a
    measured one. If someone changes this to 1.25 they must also change this
    test, and this docstring is the reason they should not."""
    assert dr.MIN_RR_DEFAULT != 1.25
