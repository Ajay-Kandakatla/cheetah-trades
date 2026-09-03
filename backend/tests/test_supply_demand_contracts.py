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


# ── ordering: closest to the level first, flow breaks ties (2026-09-03) ───────
# Ajay 2026-09-03: "make sure in our other demand and deep demand keep the
# closest one to demand zones on the top. Of course CMF inflow too considered."
def test_ordering_constants_locked():
    from supply_demand import demand_order as O
    from supply_demand import deep_demand as DD
    assert O.PROXIMITY_BUCKET_PCT == 0.5          # one tick of noise on a $96 stock
    assert O.FLOW_RANK == {"inflow": 0, "neutral": 1, "distribution": 2}
    assert O.FLOW_RANK_MISSING == 3               # missing never outranks a real read
    assert DD.MAX_IN == 60 and DD.MAX_NEAR == 40  # per-state, measured 2026-09-03
    assert DD.MAX_ROWS == DD.MAX_IN + DD.MAX_NEAR
    assert dr.OB_INFLOW_BUDGET_SEC == 30.0


def test_demand_order_stays_pure():
    """Both the scan and Chart Maps call it; the moment it reaches for a scan,
    a price or the clock the two surfaces stop being one definition."""
    from supply_demand import demand_order as O
    src = inspect.getsource(O)
    for forbidden in ("load_prices", "cached_or_warm", "import time", "datetime",
                      "requests", "httpx", "from . import", "from supply_demand"):
        assert forbidden not in src, f"demand_order reaches for {forbidden}"


def test_every_non_reached_demand_list_sorts_with_the_shared_key():
    from supply_demand import deep_demand as DD
    src = inspect.getsource(dr.scan)
    assert "approaching_rows.sort(key=_order.approaching_key)" in src
    assert "approaching_ob_rows.sort(key=_order.approaching_ob_key)" in src
    assert "in_ob_rows.sort(key=_order.in_ob_key)" in src
    assert "deep_rows.sort(key=_deep.sort_key)" in src
    assert "deep_key(row, px=px)" in inspect.getsource(DD.sort_key)
    assert "_deep.cap(deep_rows)" in src, "deep cap must be per state, not one slice"
    assert "deep_rows[:_deep.MAX_ROWS]" not in src


def test_no_distance_default_can_send_a_true_zero_to_the_back():
    """`dist_pct or 99.0` ranked a name sitting exactly on its band LAST.
    None-safety lives inside proximity_key (state 3 = unknown, sorts last)."""
    for mod in (dr, __import__("supply_demand.demand_order", fromlist=["x"]),
                __import__("supply_demand.deep_demand", fromlist=["x"])):
        src = inspect.getsource(mod)
        assert '("dist_pct") or 99.0' not in src, mod.__name__
        assert '("bars_ago") or 999' not in src, mod.__name__


def test_the_reached_board_keeps_its_measured_rr_order():
    """Every reached row is INSIDE its band — proximity is a constant there.
    rows.sort stays R:R-led (docs/supply_demand/rr_floor.md); the limit and
    signal_watch truncate by that order."""
    src = inspect.getsource(dr.scan)
    assert 'rows.sort(key=lambda r: (-((r.get("plan") or {}).get("rr") or 0.0), _rank_key(r)))' in src
    assert "\n    rows.sort(key=_order" not in src
    assert "BY ORDER" in inspect.getsource(dr._apply_limit)


def test_order_block_collectors_attach_the_flow_read_under_a_budget():
    src = inspect.getsource(dr.scan)
    assert src.count('["inflow"] = _ob_inflow(sym)') == 2, "in_ob AND approaching_ob"
    assert "OB_INFLOW_BUDGET_SEC" in src
    assert 'r3["inflow"] = d3.get("inflow")' in src, "deep rows expose top-level inflow"


def test_chart_maps_reranks_on_the_live_print_with_a_position_score():
    """Approaching / in-the-block / deep tiles: `_score` is the POSITION in
    the shared key's order (supply_tiles pattern) — never a second weighted
    number; the reached zone board keeps R:R + the cheetah composite."""
    from chart_maps import board
    z = inspect.getsource(board.zone_tiles)
    assert "rerank_live(rows, rank_key, live)" in z
    assert '"_score": (float(len(rows) - rank) if rank_key is not None' in z
    assert "f * 10000.0 + vlead * 1000.0" in z, "reached composite must stay"
    assert '-appr["dist_pct"]' not in z and "bars_ago\"))\n" not in z
    d = inspect.getsource(board.deep_demand_tiles)
    assert "rerank_live(rows, _order.deep_key, live)" in d
    assert '"_score": float(len(rows) - rank)' in d
    for gone in ("flow_lead", "cmf_lead", "in_band_lead", "sales_tb", "inflow names sort"):
        assert gone not in d, f"deep board still carries the 2026-08-26 weighted score: {gone}"
    # flow badge reads through inflow_of so OB and deep tiles show it too
    assert "_flow_badge(_order.inflow_of(r))" in z
    assert "_order.inflow_of(r) or {}" in d
    # the live dict is fetched ONCE per board and shared with the bounce gate
    assert z.count("_live_last(") == 1 and d.count("_live_last(") == 1
