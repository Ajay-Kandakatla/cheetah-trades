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


# ── bounce + room: one read for the SEPA filter, Back-in-Demand and Catalysts (2026-09-05) ─
# Ajay 2026-09-05: "#1 for Sepa stocks that is bouncing off of Demand zone. #2 for
# in demand Make sure you sort stocks by bouncing off of demand zone and have big
# gap in to supply. #3 for catalyst same deal make sure you sort stocks by bigger
# gaps in to supply". Spec: docs/supply_demand/bounce_room.md.
def test_bounce_room_imports_the_alerts_touch_and_bounce_constants_never_redefines_them():
    """Three surfaces, one meaning of 'touched' and 'bounced'. A local copy of
    any of these is how the filter and the phone alert start disagreeing."""
    from supply_demand import bounce_room as BR
    from supply_demand import zone_bounce_alerts as ZB
    from supply_demand import zone_edge as ZE
    assert BR.TOUCH_TOL_PCT is ZB.TOUCH_TOL_PCT and BR.WICK_PCT is ZB.WICK_PCT
    assert BR.BOUNCE_MIN_PCT is ZB.BOUNCE_MIN_PCT and BR.STRONG_PCT is ZB.STRONG_PCT
    assert BR.NEW_HIGH_TOL is ZE.NEW_HIGH_TOL
    assert BR.is_eligible is ZB.is_eligible and BR.print_from_snapshot is ZB.print_from_snapshot
    src = inspect.getsource(BR)
    for name in ("TOUCH_TOL_PCT", "WICK_PCT", "BOUNCE_MIN_PCT", "STRONG_PCT", "NEW_HIGH_TOL",
                 "ARRIVAL_PCT"):
        assert f"\n{name} =" not in src, f"bounce_room redefines {name}"
    assert "from .zone_bounce_alerts import" in src and "from .zone_edge import NEW_HIGH_TOL" in src


def test_bounce_room_owner_settings_locked():
    from supply_demand import bounce_room as BR
    from supply_demand import zone_store as ZS
    assert ZS.RECENT_SESSIONS == 5
    assert BR.LOOKBACK_SESSIONS == 5 and BR.LOOKBACK_SESSIONS is ZS.RECENT_SESSIONS, \
        "a touch older than the doc's recent list cannot be seen — the two must be one number"
    assert BR.NEAR_PCT == 2.0
    assert BR.STALE_PRINT_SEC == 180
    assert BR.RESPONSE_TTL_SEC == 30
    assert BR.ONDEMAND_MAX_QUEUE == 400 and BR.ONDEMAND_BUDGET_SEC == 240
    assert BR.MAX_SYMBOLS == 2500
    assert BR.ONDEMAND_COLL == "bounce_room_zones"
    assert BR.PARAMS == {"touch_tol_pct": 1.0, "wick_pct": 1.5, "bounce_min_pct": 3.0,
                         "strong_pct": 5.0, "lookback_sessions": 5, "near_pct": 2.0,
                         "stale_print_sec": 180, "new_high_tol": 0.98}


def test_bounce_room_ordering_puts_CLEAR_first_and_bouncing_before_room():
    """CLEAR = no supply overhead in the 1y frame = unbounded room, not zero.
    Ajay treats names clearing their last supply as the ones 'likely to go
    much higher' (EOSE / CLYM in the ask). The frontend mirrors this key."""
    from supply_demand import bounce_room as BR
    src = inspect.getsource(BR.room_rank)
    assert 'if state == "CLEAR":\n        return (0, 0.0)' in src
    assert 'if state in ("ROOM", "NEAR", "IN_BAND"):' in src and "return (1, -pct)" in src
    assert "return (2, 0.0)" in src, "no room read sorts last"
    key = inspect.getsource(BR.bounce_room_key)
    assert "bouncing = 0 if bounce else 1" in key
    assert "return (bouncing,) + tuple(room_rank(row)) + (-bounce_pct" in key


def test_bounce_room_has_no_arrival_gate_the_filter_counts_residence_bounces():
    """The phone kind's ARRIVAL_PCT is an anti-noise rule for pushes. A FILTER
    must also list a name that lived near the band and lifted off it."""
    from supply_demand import bounce_room as BR
    src = inspect.getsource(BR.bounce_read)
    assert "arrival" not in src.lower().replace("no arrival gate", "")
    assert "ARRIVAL_PCT" not in inspect.getsource(BR).replace("ARRIVAL_PCT)", "").replace(
        "zone_bounce_alerts ARRIVAL_PCT", "").replace('"ARRIVAL_PCT"', "")


def test_bounce_room_stays_in_S_D_scope_no_book_cites_no_scanner_imports():
    from supply_demand import bounce_room as BR
    src = inspect.getsource(BR)
    # The house disclaimer sentence is REQUIRED ("... no Minervini cites"); anything
    # else naming the books or a page is a cite that does not belong here.
    assert "NOT a book method, no\nMinervini cites" in src or "no Minervini cites" in src
    src = src.replace("no\nMinervini cites", "").replace("no Minervini cites", "")
    for forbidden in ("Minervini", "TLSW", "TTLAC", "trend_template", "sepa.scanner",
                      "from sepa import scanner", "from catalysts", "import catalysts",
                      "from .demand_reentry", "is_candidate", "is_buyable"):
        assert forbidden not in src, f"bounce_room reaches for {forbidden}"
    import re
    assert not re.search(r"\bpp?\.\s?\d", src), "page cites do not belong on an S/D surface"
    # the only import from outside supply_demand is the price cache, lazily, on the worker path
    outside = [l for l in src.splitlines()
               if l.strip().startswith(("from ", "import ")) and "supply_demand" not in l
               and not l.strip().startswith("from .")]
    stdlib = {"__future__", "logging", "threading", "time", "datetime", "typing", "zoneinfo",
              "json", "sys"}
    allowed = {"from sepa import prices",                    # the worker's price cache, lazily
               "from portfolio.store import _get_db"}       # the house Mongo accessor, lazily
    for l in outside:
        mod = l.strip().split()[1].split(".")[0]
        assert mod in stdlib or l.strip() in allowed, l
    assert "not advice" in BR.DISCLAIMER and "not a book method" in BR.DISCLAIMER


def test_bounce_room_request_path_never_calls_the_provider_per_symbol():
    from supply_demand import bounce_room as BR
    for fn in (BR.api_payload, BR.load_docs, BR.build_payload, BR.read_symbol):
        src = inspect.getsource(fn)
        for forbidden in ("load_prices", "for_symbol", "with_today_bar", "requests.", "httpx",
                          "_fetch_massive_minute", "find_one("):
            assert forbidden not in src, f"{fn.__name__} reaches for {forbidden}"
    assert "prices.bulk_snapshot(names)" in inspect.getsource(BR.api_payload)
    assert "load_prices" in inspect.getsource(BR.default_builder), "the worker is the only price path"
    assert "threading.Thread(target=run, daemon=True" in inspect.getsource(BR.queue_ondemand)


def test_zone_store_recent_is_additive_and_the_intraday_crons_still_read_today_only():
    """`recent` rides on the doc; zone_edge / zone_bounce_alerts never read it
    and keep `load(None, day)` (today) — `load_latest` is bounce_room's."""
    from supply_demand import zone_bounce_alerts as ZB
    from supply_demand import zone_edge as ZE
    from supply_demand import zone_store as ZS
    for mod in (ZB, ZE):
        src = inspect.getsource(mod)
        assert '"recent"' not in src and "load_latest" not in src and "latest_store_day" not in src
        assert "zone_store.load(None, day)" in src
    assert '"recent": recent_sessions(frame)' in inspect.getsource(ZS.build_doc)
    assert "coll.distinct(\"date\")" in inspect.getsource(ZS.latest_store_day)
    assert "day = day or _today_et()" in inspect.getsource(ZS.load), "load(day=None) still means TODAY"
