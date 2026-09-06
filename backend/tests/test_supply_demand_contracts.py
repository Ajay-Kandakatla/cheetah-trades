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
        # 2026-09-05 (TRU): the target is the first UNBROKEN band above the
        # PRINT; these say which band it is (supply | demand), whether the
        # print is under it (ROOM) or already inside it (IN_BAND), and the
        # free-text basis the card prints. See rr_floor.md section 6.
        "target_kind", "target_state", "target_basis",
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


# ── engine fixes 2026-09-05 (Ajay: "yes please fix the bugs") ─────────────────
# Source guards for the six engine fixes. Behaviour lives in test_price_zones.py,
# test_prices_today_bar.py and test_timeframes_patterns.py; these make sure the
# next refactor cannot drop a rule silently.
def test_engine_fixes_2026_09_05_at_demand_carries_the_true_support_distance():
    """AT_DEMAND no longer forces support_pct to 0.0 next to the band BELOW."""
    src = inspect.getsource(pz._verdict)
    assert '"support_pct": 0.0' not in src
    assert 'base = {"resistance_pct": res_pct, "support_pct": sup_pct}' in src


def test_engine_fixes_2026_09_05_structure_reads_the_closed_frame_only():
    """Swings, gaps, ATR and trade levels come off `closed`; the live bar / the
    partial intraday bucket only prices the read."""
    src = inspect.getsource(pz.for_symbol)
    assert "out = compute(closed, last_price=last_price, **geom)" in src
    assert "atr_value = pat_mod.atr(closed)" in src
    assert "gaps = pat_mod.fair_value_gaps(closed, lp)" in src
    assert '.get("partial") and len(df) > 1:' in src and "closed = df.iloc[:-1]" in src
    assert "compute(df," not in src and "pat_mod.atr(df)" not in src


def test_engine_fixes_2026_09_05_hairline_bands_get_width_but_real_spans_do_not():
    assert pz._TICK_2DP == 0.01, "the 2dp rounding grain, not a threshold"
    src = inspect.getsource(pz._make_zone)
    assert "if hi <= lo or (round(hi, 2) - round(lo, 2)) < _TICK_2DP - 1e-9:" in src


def test_engine_fixes_2026_09_05_with_today_bar_reuses_the_cache_guards():
    from sepa import prices as P
    src = inspect.getsource(P.with_today_bar)
    assert "weekday() >= 5" in src, "weekend-dated snapshot rejected"
    assert "healed = _drop_phantom_tail(out)" in src, "phantom echo rejected by the read-path test"
    assert '"reason": None' in src


def test_engine_fixes_2026_09_05_atr_is_labelled_simple_mean_and_the_math_is_untouched():
    from supply_demand import patterns as P
    assert "Wilder" not in (P.atr.__doc__ or "")
    assert "tr.rolling(period).mean()" in inspect.getsource(P.atr), "changing the math moves every stop"


def test_engine_fixes_2026_09_05_no_long_plan_inside_a_supply_band():
    from supply_demand import patterns as P
    src = inspect.getsource(P.trade_levels)
    assert 'if kind == "supply" and lo <= last <= hi:\n        return None' in src
    assert '"trade_reason"' in inspect.getsource(P.attach_levels)


def test_engine_fixes_2026_09_05_intraday_as_of_is_the_last_minute_and_the_bucket_is_flagged():
    from supply_demand import timeframes as TF
    src = inspect.getsource(TF.frame_for)
    assert "as_of = str(raw.index[-1])" in src
    assert '"partial": partial' in src
    assert "partial = bool((label - last_minute) > pd.Timedelta(minutes=1))" in src
    assert "the last one is a half hour" not in (TF.__doc__ or "")


# ═════════════════════════════════════════════════════════════════════════════
# reentry fixes 2026-09-05  (Ajay 2026-09-05: "yes please fix the bugs")
# Source / constant guards for the four demand_reentry.py findings of the S/D
# zone review. Behaviour lives in test_demand_reentry.py + test_deep_demand.py.
# ═════════════════════════════════════════════════════════════════════════════
def test_reentry_fix_a_break_is_answered_only_by_a_MIN_RISE_close_above_the_top():
    """The whipsaw guard: one close a hair over the band top must NOT re-arm a
    band that closed under its floor. The scan answers a break only with a
    close >= min_rise_pct above the top — the same bar the re-entry clears."""
    src = inspect.getsource(dr._break_scan)
    assert "(c / zone_hi - 1.0) * 100.0 >= min_rise_pct" in src
    assert "above_idx[-1] + 1" not in src, "the old 'after the last close above' scoping is back"
    whipsaw = [112.0] * 10 + [106.0] * 19 + [101.0] + [97.0] * 4 + [104.2] + [102.0] * 5
    assert dr.reentry_read(whipsaw, 104.0, 100.0, 102.0)["is_reentry"] is False


def test_reentry_fix_reentry_read_and_band_break_read_share_ONE_scan():
    """Two callers, one walk. If either grows its own loop they will disagree
    about the same band on the same day."""
    for fn in (dr.reentry_read, dr.band_break_read):
        src = inspect.getsource(fn)
        assert "_break_scan(window, zone_hi, zone_lo, min_rise_pct)" in src, fn.__name__
        assert "_break_fields(scan, zone_hi, zone_lo)" in src, fn.__name__
        assert "for i, c in enumerate" not in src, f"{fn.__name__} grew its own scan"


def test_reentry_fix_band_break_read_payload_shape_is_stable():
    out = dr.band_break_read([110.0] * 32 + [95.0] * 8, 104.0, 100.0)
    assert set(out) == {"fell_from_pct", "bars_since_above", "broke_below",
                        "bars_since_break", "bars_since_first_break",
                        "lowest_close_pct_below"}
    # reentry_read's shape did NOT grow — the FE destructures it.
    assert "bars_since_first_break" not in dr.reentry_read([100, 110, 120, 103], 106, 100, 103)


def test_reentry_fix_decide_from_frame_reads_closes_on_the_2dp_quote_basis():
    """`zones["last_price"]` and the band edges are 2dp. The closes fed to the
    reads must be too, or a sub-cent close above the band top is INSIDE for
    membership and ABOVE for reentry_read at the same time."""
    src = inspect.getsource(dr.decide_from_frame)
    assert 'closes = [round(float(c), 2) for c in df["close"].tolist()]' in src


def test_reentry_fix_top_band_read_uses_the_no_in_band_read():
    """reentry_read is the empty shape whenever price is outside the band, and
    top_band_read is only ever asked when price is BELOW it. It must be
    band_break_read, and deep_demand must read the FIRST-break age from it."""
    from supply_demand import deep_demand as DD
    src = inspect.getsource(dr.decide_from_frame)
    assert '"top_band_read": (band_break_read(closes, demand[0]["hi"], demand[0]["lo"])' in src
    assert 'top_band_read": (reentry_read(' not in src
    assert '"bars_since_top_break": tb.get("bars_since_first_break")' in inspect.getsource(DD.read)


def test_reentry_fix_ob_reads_label_the_target_by_the_bands_origin():
    """Both OB reads hand trade_levels `nearest_resistance` (either origin);
    the label must go through _label_target_kind or a demand band overhead is
    printed as 'next supply band'."""
    for fn in (dr.approaching_ob_read, dr.in_ob_read):
        src = inspect.getsource(fn)
        assert "trade = _label_target_kind(" in src, fn.__name__
    assert dr._label_target_kind({"target_basis": "next supply band"},
                                 {"kind": "demand"})["target_basis"] == "broken demand band overhead"
    assert dr._label_target_kind({"target_basis": "2R measured"},
                                 {"kind": "demand"})["target_basis"] == "2R measured"
    assert "either origin" in dr.trade_plan.__doc__.lower()


# ── live alert fixes 2026-09-05 (review of the S/D zone logic; Ajay: "yes please fix the bugs") ──
def test_live_alert_fixes_2026_09_05_phone_gate_constants_and_every_push_path_calls_it():
    """Ajay 2026-09-05: "When alert I need the same logic. Need only alerts on
    stocks that have atleast 5% to Supply and also <1% bounce from demand zone".
    One gate module, three callers, counters in every pass result."""
    from supply_demand import alert_gates as AG
    from supply_demand import demand_alerts as DA
    from supply_demand import zone_bounce_alerts as ZB
    from supply_demand import zone_edge as ZE
    assert AG.ALERT_MIN_ROOM_PCT == 5.0 and AG.ALERT_MAX_ABOVE_DEMAND_PCT == 1.0
    assert ZE.EDGE_PCT == AG.ALERT_MAX_ABOVE_DEMAND_PCT, "zone_edge's in/near tier IS the <1% rule — reused"
    assert DA.AT_PCT == AG.ALERT_MAX_ABOVE_DEMAND_PCT, "AT already pushed at <=1%; only NEAR pushes stopped"
    ze = inspect.getsource(ZE.check_once)
    assert ze.count("AG.room_gate(") == 2, "breaking AND near-demand candidacy"
    # integrator 2026-09-05: `lo > band.hi` missed an OVERLAPPING lid; the set is every band whose top clears this one's
    assert 'float(b["hi"]) > rb["band"]["hi"]' in ze, "🚀 room is measured to the NEXT band above the one breaking"
    # /alerts page 2026-09-05: check_once became a thin wrapper (session gate +
    # alert_pass_latest record) around _check_once, the pass proper — the gate
    # calls live in the inner function, and the wrapper must reach it
    for mod in (ZB, DA):
        wrap = inspect.getsource(mod.check_once)
        assert "out = _check_once(" in wrap and "AS.record_result(KIND, out, now, coll=pass_coll)" in wrap, mod.__name__
        assert 'return {"ran": False, "reason": "outside RTH"}' in wrap, f"{mod.__name__}: outside RTH records nothing"
    zb = inspect.getsource(ZB._check_once)
    assert 'AG.demand_proximity_gate(px, item["band"])' in zb and "AG.room_gate(px, bands, prev)" in zb
    da = inspect.getsource(DA._check_once)
    assert 'AG.demand_proximity_gate(it["last"], it["band"])' in da and "AG.room_gate(" in da
    assert "unknown_room += 1" in da, "no zone_store doc = unknown room = silent, counted"
    for src, names in ((ze, ("skipped_room",)),
                       (zb, ("skipped_room", "skipped_proximity")),
                       (da, ("skipped_room", "skipped_proximity", "unknown_room"))):
        for n in names:
            assert f'"{n}": {n}' in src, n
    # alert_gates stays a LEAF: bounce_room imports zone_edge + zone_bounce_alerts, which import it
    imports = [l for l in inspect.getsource(AG).splitlines() if l.startswith(("from ", "import "))]
    assert imports == ["from __future__ import annotations", "import math", "from typing import Optional"]
    ag = inspect.getsource(AG)
    assert "no Minervini cites" in ag and "not advice" in ag
    for forbidden in ("TLSW", "TTLAC", "trend_template", "sepa.", "from catalysts"):
        assert forbidden not in ag, forbidden


def test_live_alert_fixes_2026_09_05_side_a_room_for_keys_holidays_stale_day():
    from supply_demand import alert_gates as AG
    from supply_demand import bounce_room as BR
    from supply_demand import demand_alerts as DA
    from supply_demand import zone_bounce_alerts as ZB
    from supply_demand import zone_edge as ZE
    # Side A: a supply band yesterday CLOSED above is Side B's support, never resistance
    rb = inspect.getsource(ZE.read_breaking)
    assert 'resistance = supply if pc0 is None else [b for b in supply if float(b["hi"]) >= pc0]' in rb
    assert 'above = [b for b in resistance if float(b["hi"]) >= px]' in rb
    # room_for shares the gate's overhead rule and knows prev_close; the caller passes it
    assert "AG.room_read(px, bands or [], prev_close)" in inspect.getsource(ZB.room_for)
    assert "prev_close=None" in str(inspect.signature(ZB.room_for))
    assert 'room_for(px, bands, item["band"], prev)' in inspect.getsource(ZB._check_once)
    # the gate's first-overhead read == bounce_room.first_overhead whenever no band is broken
    bands = [{"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 2},
             {"kind": "supply", "lo": 99.0, "hi": 101.0, "touches": 2},
             {"kind": "supply", "lo": 104.0, "hi": 105.0, "touches": 1},
             {"kind": "demand", "lo": 105.0, "hi": 107.0, "touches": 2},
             {"kind": "supply", "lo": 120.0, "hi": 125.0, "touches": 3}]
    for px in (50.0, 99.0, 100.0, 104.5, 106.0, 110.0, 130.0):
        theirs = BR.first_overhead(BR.overhead_bands(bands, px), px)
        ours = AG.first_overhead(bands, px, None)
        assert (theirs is None) == (ours is None), px
        assert theirs is None or (theirs["lo"], theirs["hi"]) == (ours["lo"], ours["hi"]), px
    # and the ONE addition: a broken band (hi < prev_close) is not a ceiling for the phone
    assert AG.first_overhead(bands[:3], 100.0, 106.0) is None and AG.first_overhead(bands[:3], 100.0, 104.5)["lo"] == 104.0
    # state / first_seen / dedupe keys are fixed 2 dp (':g' collided above $10,000)
    for fn in (ZE.break_state_key, ZE.first_seen_key, ZB.state_key, DA.state_key):
        src = inspect.getsource(fn)
        assert ":.2f}" in src and ":g}" not in src, fn.__name__
    # holiday-aware session gates through the ONE house calendar
    for mod in (ZE, ZB, DA):
        assert "is_market_day(et)" in inspect.getsource(mod.in_session), mod.__name__
        assert "from market_hours.reminder import is_market_day" in inspect.getsource(mod), mod.__name__
    # a doc from another day is never live; a cold store writes the reason so the board self-heals
    ap = inspect.getsource(ZE.api_payload)
    assert 'if str(payload.get("date") or "") != today:' in ap and 'payload["in_session"] = False' in ap
    assert "no pass yet today" in ap
    ze = inspect.getsource(ZE.check_once)
    assert "_write_latest(latest_coll, ep)" in ze and 'reason = "zone store empty for today"' in ze


# ── integrator fixes 2026-09-05 (review of the 22-bug sweep; Ajay: "yes please fix the bugs") ──
def test_integrator_fixes_2026_09_05_overlapping_lid_and_transient_store_read():
    from supply_demand import zone_edge as ZE
    # overhead = every OTHER supply band whose TOP clears the band's top (an overlapping lid counts)
    rb = inspect.getsource(ZE.read_breaking)
    assert 'overhead = sum(1 for b in supply if float(b["hi"]) > hi)' in rb
    assert 'float(b["lo"]) > hi' not in rb
    ze = inspect.getsource(ZE.check_once)
    assert 'float(b["hi"]) > rb["band"]["hi"]' in ze, "the 🚀 room read uses the same set"
    # a transient {} from zone_store.load never blanks a board a live pass wrote today
    assert "_latest_is_todays_pass(latest_coll, day_iso)" in ze
    assert '"latest_written": written' in ze
    lp = inspect.getsource(ZE._latest_is_todays_pass)
    assert 'str(doc.get("date") or "") == day_iso and doc.get("as_of")' in lp


def test_integrator_fixes_2026_09_05_broken_supply_rule_reaches_bounce_room_and_supply_watch():
    import importlib.util
    from supply_demand import bounce_room as BR
    assert "prev_close=None" in str(inspect.signature(BR.overhead_bands))
    ob = inspect.getsource(BR.overhead_bands)
    assert "if pc is not None and hi < pc:" in ob and "continue" in ob
    assert 'overhead_bands(doc.get("bands") or [], px, doc.get("prev_close"))' in inspect.getsource(BR.room_read)
    spec = importlib.util.spec_from_file_location(
        "sw_contract", Path(__file__).resolve().parents[2] / "backend/portfolio/supply_watch.py")
    sw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sw)
    assert "prev_close=None" in str(inspect.signature(sw.overhead_bands))
    assert 'overhead_bands(supply, demand, live, quote.get("prev_close"))' in inspect.getsource(sw.derive)
    assert '"prev_close": float(prev) if prev else None' in inspect.getsource(sw)


def test_integrator_fixes_2026_09_05_structure_reads_closed_bars_in_every_caller():
    """price_zones.for_symbol adopted the closed-frame rule; the three callers
    that still computed on the live bar / partial bucket follow it."""
    from catalysts import signal_watch as SW
    from chart_maps import support as S
    from supply_demand import session_board as SB
    fs = inspect.getsource(S.for_symbol)
    assert "zones = pz.compute(closed, last_price=live_last" in fs
    assert "atr_value = pat_mod.atr(closed)" in fs and "fair_value_gaps(closed, last_price)" in fs
    assert 'df, _have, as_of, closed = _frame_for(sym, spec["bars"], with_closed=True)' in fs
    assert "with_closed: bool = False" in str(inspect.signature(S._frame_for)) or \
        "with_closed" in str(inspect.signature(S._frame_for))
    sb = inspect.getsource(SB.read_symbol)
    assert 'closed = df.iloc[:-1] if (meta.get("partial") and len(df) > 1) else df' in sb
    assert "gaps = pat.fair_value_gaps(closed, last)" in sb
    sw = inspect.getsource(SW.check_once)
    assert "df.iloc[:-1] if ((meta or {}).get(\"partial\") and len(df) > 1)" in sw
    assert "atr_value = pat_mod.atr(closed)" in sw and "fair_value_gaps(closed, last)" in sw
    assert "lookback_bars=len(closed)" in sw
    # the zone_bounce_alerts phone-gate geometry note: STRONG off a band needs hi/lo >= 1.05/1.01
    assert round(1.05 / 1.01 - 1.0, 4) == 0.0396


# ── room floor 2026-09-05 ────────────────────────────────────────────────────
# Ajay 2026-09-05 (TRU, Back in Demand): "It already gapped up very close to
# the resistance. Why is it still in in Demand page? There is only 0.5% room";
# and "I need the same logic in Demand and deep demand zone. So that there are
# stocks that have more room atleast >5%". Owner settings for the S&D strategy,
# no book cite. Spec: docs/supply_demand/rr_floor.md (section 6),
# docs/supply_demand/demand_reentry_methodology.md, docs/sepa/chart_maps_sort.md.
def test_room_floor_default_IS_the_alert_gate_number_imported_not_retyped():
    from supply_demand import alert_gates as G
    from supply_demand import room_floor as RF
    assert RF.MIN_ROOM_DEFAULT == G.ALERT_MIN_ROOM_PCT == dr.MIN_ROOM_DEFAULT
    src = inspect.getsource(RF)
    line = next(l for l in src.splitlines() if l.startswith("MIN_ROOM_DEFAULT"))
    assert "_gates.ALERT_MIN_ROOM_PCT" in line and "5" not in line.split("=")[1].split("#")[0]
    # room_floor is a LEAF: alert_gates is its only sibling import — never the
    # boards or demand_reentry (chart_maps reads it while tests stub the latter)
    imports = [l for l in src.splitlines() if l.startswith(("from ", "import "))]
    assert "from . import alert_gates as _gates" in imports
    assert not any("demand_reentry" in l or "chart_maps" in l or "board" in l for l in imports)


def test_trade_plan_target_is_alert_gates_first_overhead_above_the_PRINT():
    src = inspect.getsource(dr.trade_plan)
    assert "_gates.first_overhead(" in src
    assert 'float(z["lo"]) > max(hi, last_price)' not in src, \
        "the old 'above the entry band top' rule is gone"
    assert "prev_close" in str(inspect.signature(dr.trade_plan))
    assert "prev_close=prev_close" in inspect.getsource(dr.decide_from_frame)


def test_room_floor_is_read_time_like_the_rr_floor_and_the_routes_take_min_room():
    assert "_apply_room_floor" not in inspect.getsource(dr.scan)
    cw = inspect.getsource(dr.cached_or_warm)
    assert "_apply_room_floor" in cw and "attach_room" in cw
    assert "min_room" in str(inspect.signature(dr.cached_or_warm))
    from supply_demand import api as sd_api
    for fn in (sd_api.get_demand_reentry, sd_api.post_demand_reentry_scan):
        assert "min_room" in str(inspect.signature(fn))
    from chart_maps import api as cm_api
    assert "min_room" in str(inspect.signature(cm_api.chart_maps))
    from chart_maps import board as B
    for fn in (B.zone_tiles, B.deep_demand_tiles):
        assert "min_room" in str(inspect.signature(fn))
    assert "min_room" not in str(inspect.signature(B.supply_tiles))


def test_room_block_shape_is_the_shared_contract():
    from supply_demand import room_floor as RF
    room = RF.room_block(79.88, [{"kind": "supply", "lo": 80.12, "hi": 82.10}])
    assert set(room) >= {"room_pct", "room_pct_raw", "target_lo", "target_hi", "target_kind",
                         "state", "basis", "px"}
    assert room["state"] in ("CLEAR", "ROOM", "NEAR", "IN_BAND")
    # the state split and the floor compare RAW; room_pct is display-only (1 dp)
    src = inspect.getsource(RF.room_block)
    assert "room_pct_raw" in src
    assert "room_pct_raw" in inspect.getsource(RF.meets_room_floor)
    assert RF.room_stat(room) == "+0.3% -> 80.12"
    assert RF.room_stat(RF.room_block(10.0, [])) == "open sky"
    assert RF.room_stat(None) == "—"
