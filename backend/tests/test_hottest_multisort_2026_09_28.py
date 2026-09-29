"""🔥 Hottest — multi-column sort (Ajay 2026-09-28).

  "Can you fix the horizontal columns hiding and also can you help me with
   multi column sort also can you help with info icon on the quality?"

This file owns the BACKEND half of the multi-column sort and the served
`quality_info` block's wiring:

  * `then_by=key:dir,key:dir` — up to `MAX_SORT_KEYS - 1` tie-breaks after the
    primary `sort` / `dir`, which behave EXACTLY as before.
  * one comparator for all four levels (names, industries, sectors, themes);
    a missing value sorts LAST per key; exact ties: NAME rows fall to the
    symbol A→Z, GROUP rows keep their input (stored) order — today's rule.
  * single-key output is order-identical to the pre-change module, pinned by a
    golden captured from the UNMODIFIED module
    (`fixtures/hottest_single_sort_order_golden_2026_09_28.json`).

Regenerate the golden ONLY from a module you trust to be the old behaviour:
    .venv/bin/python tests/test_hottest_multisort_2026_09_28.py --write-golden
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path:                    # direct-run support
    sys.path.insert(0, os.path.dirname(HERE))

from rotation import hottest as H                              # noqa: E402
from rotation import tracker as T                              # noqa: E402

GOLDEN = os.path.join(HERE, "fixtures",
                      "hottest_single_sort_order_golden_2026_09_28.json")

# ─────────────────────────────────────────────────────────────────────────────
# The golden fixture. NAME input is alphabetical (prod: tracker.py sorts the
# priced members before serving `symbols`); GROUP input is deliberately NOT
# alphabetical (prod: the members table's own insertion order), with real ties
# at group level and — like prod — no next_earnings / traction / ret_* on any
# group row.
# ─────────────────────────────────────────────────────────────────────────────
_STATS = {
    #        sector              industry     r1     r5     r21
    "ALFA": ("Technology",      "Software",  1.0,   2.0,   5.0),
    "BETA": ("Technology",      "Hardware",  1.0,   4.0,   3.0),
    "CHAR": ("Technology",      "Software",  -0.5,  2.0,   None),
    "DELT": ("Technology",      "Semis",     2.5,   -1.0,  8.0),
    "ECHO": ("Energy",          "Oil",       0.3,   1.5,   2.0),
    "FOXT": ("Energy",          "Coal",      0.3,   3.5,   -4.0),
    "GOLF": ("Energy",          "Oil",       None,  1.5,   6.0),
    "HOTL": ("Basic Materials", "Steel",     -1.2,  0.0,   1.0),
    "INDI": ("Basic Materials", "Chemicals", 0.8,   -2.0,  1.0),
    "JULI": ("Basic Materials", "Steel",     0.8,   5.0,   -1.0),
}

# sym -> (sales_yoy, sales_tier, q_eps_yoy, net_margin, eq_score, eq_tier, cached_at)
_FUND = {
    "ALFA": (20.0, "steady", 30.0, 12.0, 90.0, "steady", 1790000000),
    "BETA": (18.0, "steady", 45.0, 12.0, 90.0, "accelerating", 1790100000),
    "CHAR": (10.0, "steady", 30.0, 8.0, 70.0, "weak", 1790200000),
    "DELT": (6.0, "steady", None, 20.0, 60.0, "weak", 1790300000),
    "ECHO": (8.0, "steady", 12.0, 5.0, 80.0, "steady", 1790400000),
    "FOXT": (12.0, "steady", 12.0, None, 90.0, "code33", 1790500000),
    "GOLF": (9.0, "steady", -5.0, 15.0, 70.0, "weak", 1790600000),
    "HOTL": (30.0, "strong", 60.0, 9.0, 50.0, "red_flag", 1790700000),
    # INDI: no research row at all — every fundamental blank
    "JULI": (40.0, "strong", 10.0, 9.0, 40.0, "weak", 1790800000),
}
_EARN = {"ALFA": "2026-10-20", "CHAR": "2026-10-02", "ECHO": "2026-11-05",
         "HOTL": "2026-10-02", "JULI": "2026-10-15"}

_SECTOR_ORDER = ("Technology", "Energy", "Basic Materials")
_SHIPPED_SECTORS = [
    {"group": "Technology", "n": 40, "dropped": 0, "rel_1d": 0.5, "rel_5d": 1.0,
     "rel_21d": 2.0, "pct_positive_1d": 50.0},
    {"group": "Energy", "n": 30, "dropped": 0, "rel_1d": 0.5, "rel_5d": 3.0,
     "rel_21d": 1.0, "pct_positive_1d": 60.0},
    {"group": "Basic Materials", "n": 20, "dropped": 0, "rel_1d": -0.2, "rel_5d": 1.0,
     "rel_21d": 4.0, "pct_positive_1d": 40.0},
]
_THEMES = {"space": ["ALFA", "ECHO", "HOTL"],
           "quantum": ["BETA", "DELT"],
           "crypto": ["CHAR", "FOXT", "JULI"]}


def _decision(sym: str):
    f = _FUND.get(sym)
    if f is None:
        return None
    sales_yoy, tier, q, m, score, eq_tier, cached = f
    return {
        "sales": {"growth_yoy_pct": sales_yoy, "tier": tier},
        "q_eps_growth_pct": q,
        "earnings_quality": {"score": score, "tier": eq_tier,
                             "code_33": eq_tier == "code33",
                             "components": {"npm_latest_pct": m},
                             "red_flags": {"inventory_vs_sales": False}},
        "_source": "massive",
        "cached_at": cached,
    }


def _golden_inputs():
    """(payload, decisions, earnings) — the fixture every golden key runs on."""
    by_symbol = {}
    for s in sorted(_STATS):
        sec, ind, r1, r5, r21 = _STATS[s]
        st = {"sector": sec, "industry": ind, "name": s.title(), "last_close": 10.0}
        for k, v in (("ret_1d", r1), ("ret_5d", r5), ("ret_21d", r21)):
            if v is not None:
                st[k] = v
        by_symbol[s] = st
    sector_groups = {}
    for sec in _SECTOR_ORDER:
        sector_groups[sec] = {"symbols": sorted(s for s in _STATS if _STATS[s][0] == sec),
                              "median_21d": 1.0}
    groups = {
        "sector": sector_groups,
        "industry": {"Software": {"symbols": ["ALFA", "CHAR"], "median_21d": 5.0},
                     "Oil": {"symbols": ["ECHO", "GOLF"], "median_21d": 4.0}},
        "cohort": {},
        "theme": {k: {"symbols": sorted(v), "median_21d": 0.5} for k, v in _THEMES.items()},
    }
    payload = {
        "as_of": "2026-09-25", "benchmark": "RSP",
        "sectors": [dict(r) for r in _SHIPPED_SECTORS],
        "industries": [{"group": "Software", "n": 12, "rel_1d": 0.4, "rel_5d": 1.1,
                        "rel_21d": 2.2, "pct_positive_1d": 55.0}],
        "themes": [{"group": "space", "n": 3, "rel_1d": 0.2, "rel_5d": 0.9,
                    "rel_21d": 1.3, "pct_positive_1d": 66.0}],
        "sampled": {"Technology": {"of": 300, "used": 40}},
        T.MEMBERS_KEY: {"by_symbol": by_symbol, "groups": groups,
                        "benchmark": {"symbol": "RSP", "ret_1d": 0.1, "ret_5d": 0.2,
                                      "ret_21d": 0.3}},
    }
    decisions = {s: _decision(s) for s in _FUND}
    earnings = {s: {"next_date": d, "when": "bmo"} for s, d in _EARN.items()}
    return payload, decisions, earnings


def _run(sort, direction, then_by="__absent__", names_per_group=25, inputs=None):
    payload, decisions, earnings = inputs or _golden_inputs()
    kw = dict(sort=sort, direction=direction, names_per_group=names_per_group,
              decisions=decisions, earnings=earnings, live=None)
    if then_by != "__absent__":
        kw["then_by"] = then_by
    return H._build(payload, **kw)


def _syms(rows):
    return [r["symbol"] for r in rows]


def _projection(board: dict) -> dict:
    """ONLY the order at every level + what the board says it ranked on."""
    return {
        "sorted_by": board["sorted_by"],
        "sorted_dir": board["sorted_dir"],
        "themes": [t["group"] for t in board["themes"]],
        "theme_names": {t["group"]: _syms(t["names"]) for t in board["themes"]},
        "sectors": [s["group"] for s in board["sectors"]],
        "sector_names": {s["group"]: _syms(s["names"]) for s in board["sectors"]},
        "industries": {s["group"]: [i["group"] for i in s["industries"]]
                       for s in board["sectors"]},
        "industry_names": {s["group"] + " / " + i["group"]: _syms(i["names"])
                           for s in board["sectors"] for i in s["industries"]},
    }


def _golden_now() -> dict:
    return {f"{k}:{d}": _projection(_run(k, d))
            for k in H.SORT_KEYS for d in H.SORT_DIRS}



# ─────────────────────────────────────────────────────────────────────────────
# A one-sector fixture for NAME ordering, inserted Z..A on purpose so an A→Z
# result can only come from the tie rule, never from insertion order.
# ─────────────────────────────────────────────────────────────────────────────
def _mini(rows: dict, *, sector="Technology"):
    """rows: sym -> dict(eq, q, m, sales, tier, r5). Inserted in the dict's
    order (tests pass Z..A)."""
    by_symbol, decisions = {}, {}
    for s, v in rows.items():
        st = {"sector": sector, "industry": "Only", "name": s, "last_close": 10.0,
              "ret_1d": v.get("r1", 0.0), "ret_21d": 1.0}
        if v.get("r5", "x") is not None:
            st["ret_5d"] = v.get("r5", 1.0)
        by_symbol[s] = st
        if v.get("nofund"):
            continue
        decisions[s] = {
            "sales": {"growth_yoy_pct": v.get("sales"), "tier": v.get("tier")},
            "q_eps_growth_pct": v.get("q"),
            "earnings_quality": {"score": v.get("eq"), "tier": "weak",
                                 "components": {"npm_latest_pct": v.get("m")},
                                 "red_flags": {}},
            "cached_at": 1790000000,
        }
    syms = list(rows)                                   # NOT sorted: Z..A
    payload = {
        "as_of": "2026-09-25",
        "sectors": [{"group": sector, "n": 10, "rel_1d": 0.1, "rel_5d": 0.2,
                     "rel_21d": 0.3}],
        T.MEMBERS_KEY: {"by_symbol": by_symbol,
                        "groups": {"sector": {sector: {"symbols": syms, "median_21d": 1.0}},
                                   "industry": {}, "cohort": {}, "theme": {}},
                        "benchmark": {"symbol": "RSP", "ret_1d": 0.0, "ret_5d": 0.0,
                                      "ret_21d": 0.0}},
    }
    return payload, decisions, {}


def _names_of(board, sector="Technology"):
    return _syms(next(s for s in board["sectors"] if s["group"] == sector)["names"])


# ── parse_then_by (syntax only) ─────────────────────────────────────────────
def test_parse_then_by_basic():
    assert H.parse_then_by("net_margin:asc,eq_score") == [("net_margin", "asc"),
                                                          ("eq_score", "desc")]
    assert H.parse_then_by(" net_margin : asc ,, ") == [("net_margin", "asc")]


def test_NEGATIVE_parse_then_by_empty_and_non_string():
    assert H.parse_then_by("") == []
    assert H.parse_then_by(None) == []
    assert H.parse_then_by(object()) == []          # a FastAPI Query object
    assert H.parse_then_by(":asc") == []
    assert H.parse_then_by(",") == []


# ── _sort_plan — THE one validator ──────────────────────────────────────────
def test_NEGATIVE_plan_drops_unknown_key():
    assert H._sort_plan("rel_5d", "desc", [("; DROP TABLE", "asc")], False) == [("rel_5d", "desc")]


def test_NEGATIVE_plan_drops_amd_it_stays_unsortable():
    assert "amd" not in H.SORT_KEYS
    assert H._sort_plan("rel_5d", "desc", [("amd", "desc")], True) == [("rel_5d", "desc")]


def test_NEGATIVE_plan_bad_dir_becomes_default():
    assert H._sort_plan("rel_5d", "desc", [("eq_score", "sideways")], False) == [
        ("rel_5d", "desc"), ("eq_score", H.DEFAULT_DIR)]


def test_NEGATIVE_plan_duplicate_of_primary_dropped():
    assert H._sort_plan("eq_score", "asc", [("eq_score", "desc")], False) == [("eq_score", "asc")]


def test_NEGATIVE_plan_duplicate_inside_then_by_first_wins():
    assert H._sort_plan("rel_5d", "desc", [("eq_score", "asc"), ("eq_score", "desc")],
                        False) == [("rel_5d", "desc"), ("eq_score", "asc")]


def test_NEGATIVE_plan_never_exceeds_max_keys():
    req = [("eq_score", "desc"), ("q_eps_yoy", "desc"), ("net_margin", "asc"),
           ("sales_yoy", "desc"), ("rel_1d", "asc")]
    plan = H._sort_plan("rel_5d", "desc", req, False)
    assert len(plan) == H.MAX_SORT_KEYS == 3
    b = _run("rel_5d", "desc", then_by=req)
    assert len(b["sorted_then_by"]) == 2
    assert b["sorted_then_by"] == [{"key": "eq_score", "dir": "desc"},
                                   {"key": "q_eps_yoy", "dir": "desc"}]


def test_NEGATIVE_invalid_entries_never_consume_a_slot():
    req = [("bogus", "asc"), ("sales_tier", "asc"), ("rel_5d", "sideways"),
           ("amd", "desc"), ("q_eps_yoy", "desc")]
    b = _run("sales_tier", "desc", then_by=req)
    assert b["sorted_then_by"] == [{"key": "rel_5d", "dir": "desc"},
                                   {"key": "q_eps_yoy", "dir": "desc"}]
    # the wire example, end to end through the parser
    b2 = _run("sales_tier", "desc", then_by=H.parse_then_by(
        "bogus:asc,sales_tier:asc,rel_5d:sideways,amd:desc,q_eps_yoy"))
    assert b2["sorted_then_by"] == b["sorted_then_by"]


def test_NEGATIVE_pre_1d_tie_break_dropped_when_pre_leg_is_idle():
    b = _run("rel_5d", "desc", then_by=[("pre_1d", "desc"), ("eq_score", "desc")])
    assert b["sorted_then_by"] == [{"key": "eq_score", "dir": "desc"}]
    assert H._sort_plan("rel_5d", "desc", [("pre_1d", "asc")], True) == [
        ("rel_5d", "desc"), ("pre_1d", "asc")]


def test_NEGATIVE_demoted_pre_primary_drops_a_rel_5d_tie_break_as_a_dup():
    b = _run("pre_1d", "desc", then_by=[("rel_5d", "asc")])
    assert b["sorted_by"] == "rel_5d"
    assert b["sorted_then_by"] == []


def test_NEGATIVE_plan_never_raises_on_junk():
    for junk in (None, 5, [None], [("a",)], [(1, "desc")], "rel_1d"):
        assert H._sort_plan("rel_5d", "desc", junk, False)[0] == ("rel_5d", "desc")


# ── NAME ordering ───────────────────────────────────────────────────────────
_TIE3 = {  # inserted Z..A; three names tie on eq 90
    "ZED": {"eq": 90.0, "q": 10.0, "m": 5.0},
    "YAK": {"eq": 90.0, "q": 40.0, "m": 5.0},
    "XRAY": {"eq": 90.0, "q": 25.0, "m": 5.0},
    "WOLF": {"eq": 50.0, "q": 99.0, "m": 5.0},
}


def test_primary_tie_is_decided_by_the_secondary():
    b = _run("eq_score", "desc", then_by=[("q_eps_yoy", "desc")], inputs=_mini(_TIE3))
    assert _names_of(b) == ["YAK", "XRAY", "ZED", "WOLF"]


def test_flipping_only_the_secondary_flips_only_inside_the_tie():
    b = _run("eq_score", "desc", then_by=[("q_eps_yoy", "asc")], inputs=_mini(_TIE3))
    assert _names_of(b) == ["ZED", "XRAY", "YAK", "WOLF"]      # WOLF still last


def test_a_tie_on_two_keys_falls_to_the_third():
    rows = {"ZED": {"eq": 90.0, "q": 30.0, "m": 2.0},
            "YAK": {"eq": 90.0, "q": 30.0, "m": 9.0},
            "XRAY": {"eq": 90.0, "q": 30.0, "m": 5.0}}
    b = _run("eq_score", "desc", then_by=[("q_eps_yoy", "desc"), ("net_margin", "asc")],
             inputs=_mini(rows))
    assert _names_of(b) == ["ZED", "XRAY", "YAK"]


def test_NEGATIVE_a_full_tie_is_symbol_A_to_Z_in_both_primary_dirs():
    rows = {"ZED": {"eq": 90.0, "q": 30.0, "m": 5.0},
            "YAK": {"eq": 90.0, "q": 30.0, "m": 5.0},
            "XRAY": {"eq": 90.0, "q": 30.0, "m": 5.0}}
    for d in ("desc", "asc"):
        for tb in ([], [("q_eps_yoy", "desc")], [("q_eps_yoy", "asc"), ("net_margin", "asc")]):
            b = _run("eq_score", d, then_by=tb, inputs=_mini(rows))
            # never insertion order (Z..A), never flipped by the direction
            assert _names_of(b) == ["XRAY", "YAK", "ZED"], (d, tb)


def test_missing_secondary_is_last_of_its_tie_in_both_secondary_dirs():
    rows = {"ZED": {"eq": 90.0, "q": None, "m": 5.0},
            "YAK": {"eq": 90.0, "q": 40.0, "m": 5.0},
            "XRAY": {"eq": 90.0, "q": 25.0, "m": 5.0},
            "WOLF": {"eq": 50.0, "q": 99.0, "m": 5.0}}
    b = _run("eq_score", "desc", then_by=[("q_eps_yoy", "desc")], inputs=_mini(rows))
    assert _names_of(b) == ["YAK", "XRAY", "ZED", "WOLF"]
    b = _run("eq_score", "desc", then_by=[("q_eps_yoy", "asc")], inputs=_mini(rows))
    assert _names_of(b) == ["XRAY", "YAK", "ZED", "WOLF"]


def test_NEGATIVE_missing_primary_is_after_every_present_primary():
    rows = {"ZED": {"eq": None, "q": 999.0, "m": 5.0},
            "YAK": {"eq": 90.0, "q": 1.0, "m": 5.0},
            "XRAY": {"eq": 10.0, "q": 2.0, "m": 5.0},
            "VOLT": {"nofund": True}}
    for d in ("desc", "asc"):
        for sd in ("desc", "asc"):
            b = _run("eq_score", d, then_by=[("q_eps_yoy", sd)], inputs=_mini(rows))
            got = _names_of(b)
            assert set(got[:2]) == {"YAK", "XRAY"}, (d, sd, got)
            assert set(got[2:]) == {"ZED", "VOLT"}, (d, sd, got)


def test_categorical_sales_tier_then_q_eps_orders_inside_each_tier():
    rows = {"ZED": {"tier": "steady", "q": 10.0},
            "YAK": {"tier": "strong", "q": 5.0},
            "XRAY": {"tier": "steady", "q": 50.0},
            "WOLF": {"tier": "strong", "q": 80.0},
            "VOLT": {"tier": "steady", "q": 30.0}}
    b = _run("sales_tier", "desc", then_by=[("q_eps_yoy", "desc")], inputs=_mini(rows))
    assert _names_of(b) == ["WOLF", "YAK", "XRAY", "VOLT", "ZED"]
    # single key: the tier ties fall to A→Z
    b1 = _run("sales_tier", "desc", inputs=_mini(rows))
    assert _names_of(b1) == ["WOLF", "YAK", "VOLT", "XRAY", "ZED"]


def test_integer_quality_ties_then_sales_yoy():
    rows = {"ZED": {"eq": 90.0, "sales": 5.0},
            "YAK": {"eq": 90.0, "sales": 50.0},
            "XRAY": {"eq": 70.0, "sales": 99.0},
            "WOLF": {"eq": 90.0, "sales": 20.0}}
    b = _run("eq_score", "desc", then_by=[("sales_yoy", "desc")], inputs=_mini(rows))
    assert _names_of(b) == ["YAK", "WOLF", "ZED", "XRAY"]


def test_truncation_happens_after_the_multi_sort():
    b = _run("eq_score", "desc", then_by=[("q_eps_yoy", "desc")], names_per_group=1,
             inputs=_mini(_TIE3))
    assert _names_of(b) == ["YAK"]
    b = _run("eq_score", "desc", then_by=[("q_eps_yoy", "asc")], names_per_group=1,
             inputs=_mini(_TIE3))
    assert _names_of(b) == ["ZED"]


# ── GROUP ordering (critic #2): ties keep their INPUT order ─────────────────
_INPUT_SECTORS = ["Technology", "Energy", "Basic Materials"]
_INPUT_THEMES = ["space", "quantum", "crypto"]


def test_NEGATIVE_keys_no_group_carries_leave_groups_in_input_order():
    for key, d in (("next_earnings", "asc"), ("next_earnings", "desc"),
                   ("traction", "desc"), ("ret_5d", "desc"), ("ret_5d", "asc")):
        for tb in (None, [("next_earnings", "asc")]):
            b = _run(key, d, then_by=tb)
            assert [s["group"] for s in b["sectors"]] == _INPUT_SECTORS, (key, d, tb)
            assert [t["group"] for t in b["themes"]] == _INPUT_THEMES, (key, d, tb)
            tech = next(s for s in b["sectors"] if s["group"] == "Technology")
            assert [i["group"] for i in tech["industries"]] == ["Software", "Hardware", "Semis"]


def test_group_ties_on_sales_tier_are_broken_by_the_secondary():
    # Technology and Energy both median `steady`; Basic Materials `strong`
    b = _run("sales_tier", "desc")
    assert [s["group"] for s in b["sectors"]] == ["Basic Materials", "Technology", "Energy"]
    b = _run("sales_tier", "desc", then_by=[("rel_5d", "desc")])
    assert [s["group"] for s in b["sectors"]] == ["Basic Materials", "Energy", "Technology"]
    b = _run("sales_tier", "desc", then_by=[("rel_5d", "asc")])
    assert [s["group"] for s in b["sectors"]] == ["Basic Materials", "Technology", "Energy"]


def test_group_ties_on_two_keys_fall_to_input_order():
    # sales_tier ties Technology/Energy; rel_1d ties them again (0.5 / 0.5)
    for d in ("desc", "asc"):
        b = _run("sales_tier", "desc", then_by=[("rel_1d", d)])
        order = [s["group"] for s in b["sectors"]]
        assert order.index("Technology") < order.index("Energy"), (d, order)


def test_NEGATIVE_a_secondary_no_group_carries_leaves_tied_groups_in_input_order():
    b = _run("sales_tier", "desc", then_by=[("next_earnings", "asc")])
    assert [s["group"] for s in b["sectors"]] == ["Basic Materials", "Technology", "Energy"]
    b = _run("eq_score", "desc", then_by=[("next_earnings", "asc")])
    assert [s["group"] for s in b["sectors"]][:2] == ["Technology", "Energy"]


def test_group_eq_score_tie_broken_by_rel_5d():
    b = _run("eq_score", "desc", then_by=[("rel_5d", "desc")])
    assert [s["group"] for s in b["sectors"]] == ["Energy", "Technology", "Basic Materials"]


# ── served ──────────────────────────────────────────────────────────────────
def test_served_plan_is_what_was_applied_not_what_was_asked():
    b = _run("eq_score", "desc", then_by=[("q_eps_yoy", "desc"), ("net_margin", "asc")])
    assert b["sorted_by"] == "eq_score" and b["sorted_dir"] == "desc"
    assert b["sorted_then_by"] == [{"key": "q_eps_yoy", "dir": "desc"},
                                   {"key": "net_margin", "dir": "asc"}]
    assert b["sort_max_keys"] == H.MAX_SORT_KEYS
    assert _run("rel_5d", "desc")["sorted_then_by"] == []


def test_build_and_build_live_accept_then_by():
    payload, _, _ = _golden_inputs()
    b = H.build(payload, sort="eq_score", then_by=[("q_eps_yoy", "asc")])
    assert b["sorted_then_by"] == [{"key": "q_eps_yoy", "dir": "asc"}]
    assert "then_by" in inspect.signature(H.build_live).parameters


def test_quality_info_rides_the_payload():
    b = _run("rel_5d", "desc")
    qi = b["quality_info"]
    assert qi and qi["points"] and qi["ceiling_today"] == 90
    assert qi["fundamentals_as_of"]["n"] == len(_FUND)


# ── single-key order identity vs the UNMODIFIED module ──────────────────────
def _golden():
    with open(GOLDEN) as fh:
        return json.load(fh)


def test_single_key_order_is_identical_to_the_old_module_for_every_key_and_dir():
    g = _golden()
    assert set(g) == {f"{k}:{d}" for k in H.SORT_KEYS for d in H.SORT_DIRS}
    for k in H.SORT_KEYS:
        for d in H.SORT_DIRS:
            assert _projection(_run(k, d)) == g[f"{k}:{d}"], (k, d)


def test_NEGATIVE_empty_then_by_forms_are_identical_to_none():
    g = _golden()
    for k in H.SORT_KEYS:
        for d in H.SORT_DIRS:
            for tb in ([], None, H.parse_then_by(""), H.parse_then_by("bogus:asc")):
                assert _projection(_run(k, d, then_by=tb)) == g[f"{k}:{d}"], (k, d, tb)


def test_single_key_multi_sorter_is_the_old_sorter():
    b = _run("rel_5d", "desc")
    rows = [r for s in b["sectors"] for r in s["names"]]
    rows += b["sectors"] + [i for s in b["sectors"] for i in s["industries"]] + b["themes"]
    for k in H.SORT_KEYS:
        for d in H.SORT_DIRS:
            m, o = H._multi_sorter([(k, d)]), H._sorter(k, d)
            assert all(m(r) == o(r) for r in rows), (k, d)


# ── API ─────────────────────────────────────────────────────────────────────
def _call_endpoint(monkeypatch, seen: dict, **kw):
    from rotation import api as A
    monkeypatch.setattr(A, "_members_table",
                        lambda: (_golden_inputs()[0][T.MEMBERS_KEY], {"source": "scan"}))
    monkeypatch.setattr(A, "_members_payload", lambda: _golden_inputs()[0])

    def _fake_live(payload, **k):
        seen.update(k)
        return H.build(payload, sort=k.get("sort", H.DEFAULT_SORT),
                       direction=k.get("direction", H.DEFAULT_DIR),
                       names_per_group=k.get("names_per_group", H.NAMES_PER_GROUP),
                       then_by=k.get("then_by"))
    monkeypatch.setattr(A.H, "build_live", _fake_live)
    monkeypatch.setattr(A, "HA", None)

    import rotation as _pkg

    class _NoTags:
        @staticmethod
        def latest_within(*a, **k):
            return {}

        @staticmethod
        def attach(payload, tags=None):
            return payload

    monkeypatch.setattr(_pkg, "sector_news_tags", _NoTags, raising=False)
    loop = asyncio.new_event_loop()
    try:
        resp = loop.run_until_complete(A.rotation_hottest(**kw))
    finally:
        loop.close()
    return resp, json.loads(bytes(resp.body).decode())


def test_api_without_then_by_is_the_query_object_and_serves_an_empty_plan(monkeypatch):
    seen = {}
    resp, body = _call_endpoint(monkeypatch, seen, sort="eq_score", dir="desc",
                                names=25, basis="close")
    assert resp.status_code == 200
    assert seen["then_by"] == []
    assert body["sorted_then_by"] == [] and body["sort_max_keys"] == H.MAX_SORT_KEYS


def test_api_forwards_then_by(monkeypatch):
    seen = {}
    resp, body = _call_endpoint(monkeypatch, seen, sort="eq_score", dir="desc",
                                then_by="q_eps_yoy:desc", names=25, basis="close")
    assert resp.status_code == 200
    assert seen["then_by"] == [("q_eps_yoy", "desc")]
    assert body["sorted_then_by"] == [{"key": "q_eps_yoy", "dir": "desc"}]


def test_NEGATIVE_api_bad_then_by_is_200_never_4xx(monkeypatch):
    seen = {}
    resp, body = _call_endpoint(monkeypatch, seen, sort="eq_score", dir="desc",
                                then_by="zzz", names=25, basis="close")
    assert resp.status_code == 200
    assert body["sorted_then_by"] == []


def test_NEGATIVE_api_early_return_carries_an_empty_plan(monkeypatch):
    from rotation import api as A
    monkeypatch.setattr(A, "_members_table", lambda: (None, {"reason": "no table"}))
    loop = asyncio.new_event_loop()
    try:
        resp = loop.run_until_complete(A.rotation_hottest(
            sort="rel_5d", dir="desc", then_by="eq_score:asc", names=25, basis="close"))
    finally:
        loop.close()
    body = json.loads(bytes(resp.body).decode())
    assert resp.status_code == 200 and body["sorted_then_by"] == []


def test_api_declares_then_by_as_a_query():
    from rotation import api as A
    src = inspect.getsource(A.rotation_hottest)
    assert 'then_by: str = Query(' in src


# ── freshness source guard (critic #5) ──────────────────────────────────────
def test_the_served_ttl_is_the_one_decision_map_applies():
    from sepa import research
    sig = inspect.signature(research.decision_snapshot)
    assert sig.parameters["max_age_sec"].default == research.CACHE_TTL_SEC
    tree = ast.parse(inspect.getsource(H._decision_map).lstrip())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "decision_snapshot"]
    assert len(calls) == 1
    assert len(calls[0].args) == 1
    assert not any(k.arg == "max_age_sec" for k in calls[0].keywords)
    assert H._research_ttl_sec() == research.CACHE_TTL_SEC


def test_NEGATIVE_stubbed_research_without_the_ttl_gives_None(monkeypatch):
    import sepa
    stub = types.ModuleType("sepa.research")
    monkeypatch.setitem(sys.modules, "sepa.research", stub)
    monkeypatch.setattr(sepa, "research", stub, raising=False)
    assert H._research_ttl_sec() is None
    b = _run("rel_5d", "desc")                       # never raises
    blank = " ".join(b["quality_info"]["blank"])
    assert "too old for the board to use" in blank


if __name__ == "__main__" and "--write-golden" in sys.argv:    # pragma: no cover
    with open(GOLDEN, "w") as fh:
        json.dump(_golden_now(), fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("wrote", GOLDEN)


def test_next_er_primary_then_a_group_key_still_ranks_group_rows():
    # critic 2026-09-28 (#3): the api.py docstring says Next ER leaves the
    # sectors in stored order ONLY when it is the sole key. Every group row ties
    # on Next ER, so a tie-break after it ranks them.
    for d in ("asc", "desc"):
        b = _run("next_earnings", d, then_by=[("sales_tier", "desc")])
        assert [s["group"] for s in b["sectors"]] == ["Basic Materials", "Technology", "Energy"], d
        # NEGATIVE: sole key → stored order, unchanged
        b = _run("next_earnings", d)
        assert [s["group"] for s in b["sectors"]] == _INPUT_SECTORS, d
