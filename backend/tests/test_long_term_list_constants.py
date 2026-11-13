"""📅 Long Term (2026-11-12) — constants.py is the ONLY number source; APP numbers are imported, never retyped."""
from __future__ import annotations

import json

from chart_maps import board as B, fallen_tab as FAL, undervalue_peers as UVP
from long_term_list import constants as C
from rotation import backtest as RB, hottest as H
from sepa import pankaj_picks as PK, sales as S, scanner as SC


def _seed():
    return json.loads(C.SEED_FILE.read_text(encoding="utf-8"))


def test_app_numbers_are_imported_not_retyped():
    assert C.FALLEN_MIN_PCT_BELOW is FAL.THRESHOLD_PCT
    assert C.UV_PS_MAX_FRACTION is UVP.PEER_PS_MAX_FRACTION
    assert C.UV_MIN_Q_YOY_PCT is UVP.MIN_SALES_YOY_Q_PCT
    assert C.UV_MIN_TTM_GROWTH_PCT is UVP.MIN_SALES_TTM_GROWTH_PCT
    assert C.UV_MIN_TTM_REVENUE_USD is UVP.MIN_TTM_REVENUE_USD
    assert C.QUIET_SALES_TIERS is S.BONDE_PASS_TIERS
    assert C.PANKAJ_ZONE_PAD_PCT == PK.ZONE_PAD_PCT
    assert C.HOT_PAGE == H.NAMES_PER_GROUP
    assert C.HOT_SORT == H.DEFAULT_SORT
    assert C.FALLEN_PAGE == B.LIMIT_MAX
    assert C.FALLEN_SORT == FAL.DEFAULT_SORT
    assert C.FLOOR_TIER == B.DEFAULT_MIN_TIER
    assert C.RUN_AFTER_ET == SC.SEPA_RERATE_ET
    assert C.FORWARD_MIN_SESSIONS == RB.REBALANCE
    assert C.BENCHMARK == RB.BENCHMARK and C.BENCHMARK_ALT == RB.BENCHMARK_ALT
    assert C.STAGE_DROP_PAIRS == ((2, 3), (2, 4))
    assert C.STAGE_DROP_TO == (3, 4)


def test_held_switches_default_off():
    # RE-PINNED 2026-11-12 (pkzone spec §3.1): both phone pushes are LIVE by his calls — Ajay 2026-11-12: "add an
    # alert list when stocks reach Pankaj's zones …" / "Weekly and if something gets dropped let me know …".
    # The tab stays owner only and UNMEASURED.
    assert C.DIGEST_PUSH_MODE == "live" and C.ZONE_PUSH_MODE == "live"
    assert C.CONSTANT_SOURCES["DIGEST_PUSH_MODE"] == "HIS" and C.CONSTANT_SOURCES["ZONE_PUSH_MODE"] == "HIS"
    assert C.KIND == C.DIGEST_KIND == "long_term"                       # ONE kind for both pushes
    assert C.OWNER_ONLY is True
    assert C.MEASURED is False


def test_NEGATIVE_no_second_long_term_kind_2026_11_12():
    kinds = {v for k, v in vars(C).items() if k.isupper() and isinstance(v, str) and v.startswith("long_term")
             and not v.startswith("long_term_list") and not v.startswith("long_term_zone")}
    assert kinds == {"long_term"}                                       # no long_term_digest / long_term_zone kind
    assert C.ZONE_LATCH_COLL != C.ZONE_STATE_COLL
    assert C.ZONE_URL == C.DIGEST_URL == "/chart-maps?tab=long_term"


def test_negative_no_3_to_4_in_stage_drop_pairs():
    assert (3, 4) not in C.STAGE_DROP_PAIRS
    assert 1 not in C.STAGE_DROP_TO and 2 not in C.STAGE_DROP_TO


def test_list_shape_equals_the_seed_rules():
    rules = _seed()["rules"]
    assert C.PER_CATEGORY == rules["per_category"]
    assert C.MAX_PER_SECTOR == rules["max_per_sector"]
    assert C.HOT_MAX_PER_SECTOR == rules["hot_max_per_sector"]


def _money_forms(v):
    out = {f"{v:g}"}
    for div, unit in ((1e9, "B"), (1e6, "M")):
        if v >= div:
            out.add(f"${v / div:g}{unit}")
    return out


MINE_IN_CRITERIA = {
    "CQ_MIN_ROE_PCT": "capital_quality", "CQ_MIN_FCF_MARGIN_PCT": "capital_quality",
    "CQ_MAX_NET_DEBT_EBITDA": "capital_quality",
    "FALLEN_MIN_PCT_ABOVE_LOW": "fallen_growers", "FALLEN_MIN_SALES_YOY_PCT": "fallen_growers",
    "HOT_MIN_Q_EPS_YOY": "hot", "HOT_MIN_RET_21D": "hot",
    "QUIET_MIN_SCORE": "quiet_strong", "QUIET_MIN_NET_PROFIT": "quiet_strong", "QUIET_MIN_OCF": "quiet_strong",
    "QUIET_MIN_SALES_CAGR_PCT": "quiet_strong", "QUIET_MAX_LIAB_TO_EQUITY": "quiet_strong",
    "QUIET_MIN_DOLLAR_VOL": "quiet_strong", "QUIET_MIN_PCT_BELOW_HIGH": "quiet_strong",
    "ACCEL_MIN_CAP_USD": "accel_after_fall", "ACCEL_MAX_CAP_USD": "accel_after_fall",
    "ACCEL_MIN_PRIOR_YOY_PCT": "accel_after_fall", "ACCEL_MIN_PCT_BELOW_HIGH": "accel_after_fall",
    "ACCEL_MIN_PCT_ABOVE_LOW": "accel_after_fall", "ACCEL_MIN_DOLLAR_VOL": "accel_after_fall",
}


def test_every_mine_number_appears_in_its_category_seed_criteria():
    crit = {c["key"]: c["criteria"] for c in _seed()["categories"]}
    for name, cat in MINE_IN_CRITERIA.items():
        assert C.CONSTANT_SOURCES[name] == "MINE", name
        v = getattr(C, name)
        assert any(form in crit[cat] for form in _money_forms(v)), (name, v, cat)
    for tiers, cat in ((C.S2_SALES_TIERS, "s2_growth"), (C.HOT_SALES_TIERS, "hot"),
                       (C.ACCEL_SALES_TIERS, "accel_after_fall"), (C.BONDE_TIERS, "bonde"),
                       (C.QUIET_SALES_TIERS, "quiet_strong")):
        for t in tiers:
            assert t in crit[cat], (t, cat)


def test_negative_every_mine_numeric_constant_is_listed():
    assert set(MINE_IN_CRITERIA) <= set(C.CONSTANT_SOURCES)


def test_constant_sources_cover_every_numeric_constant():
    numeric = [k for k, v in vars(C).items()
               if k.isupper() and isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert numeric
    missing = [k for k in numeric if k not in C.CONSTANT_SOURCES]
    assert not missing, missing
    assert set(C.CONSTANT_SOURCES.values()) <= {"HIS", "APP", "MINE"}
    for k in C.CONSTANT_SOURCES:
        assert hasattr(C, k), k


def test_sales_tier_ladder_follows_the_sales_engine():
    def tier(g):
        series = [100.0 * (1 + g / 100.0)] + [100.0] * 7
        return S.compute(series)["tier"]
    assert tuple(tier(g) for g in (-10, 2, 10, 50, 150)) == C.SALES_TIER_LADDER


def test_ring_kinds_are_exactly_three():
    assert C.RING_KINDS == ("stage_drop", "sales_drop", "started_moving")
    assert "fundamental" not in C.RING_KINDS and "moved" not in C.RING_KINDS and "zone" not in C.RING_KINDS


def test_category_keys_match_the_seed_file_order():
    assert tuple(c["key"] for c in _seed()["categories"]) == C.CATEGORY_KEYS
