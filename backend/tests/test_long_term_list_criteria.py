"""📅 Long Term (2026-11-12) — list rules as legs with kinds; pick_top; the 🧭 zone read."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from long_term_list import constants as C
from long_term_list import criteria as CR
from sepa import pankaj_picks as PK

FIX = Path(__file__).parent / "fixtures" / "long_term_list"

F, M, S, I = "fundamental", "market", "stage", "info"

TABLE_K = {
    "s2_growth": {"qualifier": M, "stage": S, "sales_tier": F, "c_strong_q_eps": F, "a_strong_y_eps": F},
    "capital_quality": {"qualifier": M, "roe": F, "fcf_margin": F, "net_debt_ebitda": F, "cq_grade": I},
    "undervalue": {"ttm_revenue": F, "q_yoy": F, "ttm_growth": F, "on_list": M, "floor": M},
    "bonde": {"qualifier": M, "bonde_tier": F},
    "fallen_growers": {"pct_below_high": M, "pct_above_low": M, "sales_yoy": F, "floor": M},
    "hot": {"sales_tier": F, "q_eps_yoy": F, "ret_21d": M, "served": M},
    "quiet_strong": {"stage": S, "score": F, "net_profit": F, "ocf": F, "sales_cagr": F, "liab_to_equity": F,
                     "sales_tier": F, "dollar_vol_50": M, "pct_below_high": M, "net_debt_ebitda": I},
    "accel_after_fall": {"market_cap": M, "sales_tier": F, "accelerating": F, "prior_yoy": F,
                         "pct_below_high": M, "pct_above_low": M, "stage": S, "dollar_vol_50": M, "net_profit": I},
    "pankaj": {"pankaj_tier": I, "pankaj_zones": I, "zone_read": I},
}

GOOD = {
    "s2_growth": {"qualifier": True, "stage": 2, "sales_tier": "strong", "sales_accelerating": False,
                  "c_strong_q_eps": True, "a_strong_y_eps": True, "rs_rank": 95, "scan_score": 80},
    "capital_quality": {"qualifier": True, "roe_pct": 25.0, "fcf_margin_pct": 12.0, "net_debt_ebitda": 0.4,
                        "cq_grade": "A", "moat_score": 70, "scan_score": 60},
    "undervalue": {"ttm_revenue": 5e8, "q_yoy_pct": 30.0, "ttm_growth_pct": 25.0, "on_list": True,
                   "floor_ok": True, "ratio": 0.3},
    "bonde": {"qualifier": True, "bonde_tier": "strong", "bonde_score": 7, "scan_score": 50},
    "fallen_growers": {"pct_below_high": 55.0, "pct_above_low": 20.0, "sales_yoy_pct": 40.0, "pair_blanked": False,
                       "floor_ok": True, "in_served_pool": True},
    "hot": {"sales_tier": "explosive", "q_eps_yoy": 30.0, "ret_21d": 12.0, "served": True},
    "quiet_strong": {"stage": 1, "score": 80.0, "score_ranked": True, "net_profit": 1e8, "ocf": 2e8,
                     "sales_cagr": 20.0, "liab_to_equity": 0.5, "sales_tier": "strong", "dollar_vol_50": 9e6,
                     "pct_below_high": 25.0, "net_debt_ebitda": -0.3},
    "accel_after_fall": {"market_cap": 2e9, "sales_tier": "strong", "sales_accelerating": True,
                         "growth_yoy_pct": 60.0, "prior_yoy_pct": 20.0, "pct_below_high": 45.0,
                         "pct_above_low": 30.0, "stage": 1, "dollar_vol_50": 4e6, "net_profit": -1e7},
}

# (category, value key, failing value, leg key)
FAILS = [
    ("s2_growth", "qualifier", False, "qualifier"), ("s2_growth", "stage", 3, "stage"),
    ("s2_growth", "sales_tier", "weak", "sales_tier"), ("s2_growth", "c_strong_q_eps", False, "c_strong_q_eps"),
    ("s2_growth", "a_strong_y_eps", False, "a_strong_y_eps"),
    ("capital_quality", "roe_pct", 19.9, "roe"), ("capital_quality", "fcf_margin_pct", 0.0, "fcf_margin"),
    ("capital_quality", "net_debt_ebitda", 1.01, "net_debt_ebitda"),
    ("undervalue", "ttm_revenue", 9e7, "ttm_revenue"), ("undervalue", "q_yoy_pct", 19.0, "q_yoy"),
    ("undervalue", "ttm_growth_pct", 10.0, "ttm_growth"), ("undervalue", "floor_ok", False, "floor"),
    ("bonde", "bonde_tier", "steady", "bonde_tier"), ("bonde", "qualifier", False, "qualifier"),
    ("fallen_growers", "pct_below_high", 39.9, "pct_below_high"),
    ("fallen_growers", "pct_above_low", 9.0, "pct_above_low"),
    ("fallen_growers", "sales_yoy_pct", 19.9, "sales_yoy"), ("fallen_growers", "floor_ok", False, "floor"),
    ("hot", "sales_tier", "steady", "sales_tier"), ("hot", "q_eps_yoy", 0.0, "q_eps_yoy"),
    ("hot", "ret_21d", 0.0, "ret_21d"), ("hot", "served", False, "served"),
    ("quiet_strong", "stage", 2, "stage"), ("quiet_strong", "score", 69.9, "score"),
    ("quiet_strong", "net_profit", -1.0, "net_profit"), ("quiet_strong", "ocf", 0.0, "ocf"),
    ("quiet_strong", "sales_cagr", 14.9, "sales_cagr"), ("quiet_strong", "liab_to_equity", 1.2, "liab_to_equity"),
    ("quiet_strong", "sales_tier", "declining", "sales_tier"), ("quiet_strong", "dollar_vol_50", 4.9e6, "dollar_vol_50"),
    ("quiet_strong", "pct_below_high", 8.2, "pct_below_high"),
    ("accel_after_fall", "market_cap", 2e8, "market_cap"), ("accel_after_fall", "market_cap", 1.1e10, "market_cap"),
    ("accel_after_fall", "sales_tier", "steady", "sales_tier"),
    ("accel_after_fall", "sales_accelerating", False, "accelerating"),
    ("accel_after_fall", "prior_yoy_pct", 0.0, "prior_yoy"),
    ("accel_after_fall", "pct_below_high", 29.0, "pct_below_high"),
    ("accel_after_fall", "pct_above_low", 9.9, "pct_above_low"), ("accel_after_fall", "stage", 3, "stage"),
    ("accel_after_fall", "dollar_vol_50", 2.9e6, "dollar_vol_50"),
]


def _verdict(cat, values, key):
    return next(lg.verdict for lg in CR.legs(cat, values) if lg.key == key)


def test_leg_kinds_equal_the_table():
    assert CR.LEG_KINDS == TABLE_K


@pytest.mark.parametrize("cat", sorted(GOOD))
def test_good_values_qualify(cat):
    assert CR.qualifies(cat, GOOD[cat]) is True
    assert all(lg.verdict in ("pass", "info") for lg in CR.legs(cat, GOOD[cat]))


@pytest.mark.parametrize("cat,vkey,bad,leg", FAILS)
def test_each_leg_fails(cat, vkey, bad, leg):
    vals = {**GOOD[cat], vkey: bad}
    assert _verdict(cat, vals, leg) == "fail"
    assert CR.qualifies(cat, vals) is False


@pytest.mark.parametrize("cat,vkey,bad,leg", FAILS)
def test_negative_none_is_unknown_never_pass(cat, vkey, bad, leg):
    vals = {**GOOD[cat], vkey: None}
    assert _verdict(cat, vals, leg) == "unknown"
    assert CR.qualifies(cat, vals) is None


@pytest.mark.parametrize("cat", ["hot", "quiet_strong", "accel_after_fall", "s2_growth"])
def test_negative_unknown_tier_string_is_unknown(cat):
    vals = {**GOOD[cat], "sales_tier": "unknown"}
    assert _verdict(cat, vals, "sales_tier") == "unknown"
    assert CR.qualifies(cat, vals) is not True


def test_negative_bonde_unknown_tier():
    assert _verdict("bonde", {**GOOD["bonde"], "bonde_tier": "unknown"}, "bonde_tier") == "unknown"


def test_negative_info_legs_never_change_qualifies():
    for cat, key, vals in (("capital_quality", "cq_grade", [None, "F", "A+"]),
                           ("quiet_strong", "net_debt_ebitda", [None, 5.07, -1.3]),
                           ("accel_after_fall", "net_profit", [None, -5e8, 5e8])):
        for v in vals:
            assert CR.qualifies(cat, {**GOOD[cat], key: v}) is True
            assert _verdict(cat, {**GOOD[cat], key: v}, key) == "info"


def test_s2_steady_needs_acceleration():
    assert CR.qualifies("s2_growth", {**GOOD["s2_growth"], "sales_tier": "steady", "sales_accelerating": True})
    assert CR.qualifies("s2_growth", {**GOOD["s2_growth"], "sales_tier": "steady",
                                      "sales_accelerating": False}) is False
    assert _verdict("s2_growth", {**GOOD["s2_growth"], "sales_tier": "steady", "sales_accelerating": None},
                    "sales_tier") == "unknown"


def test_capital_quality_net_debt_null_is_unknown():
    assert _verdict("capital_quality", {**GOOD["capital_quality"], "net_debt_ebitda": None},
                    "net_debt_ebitda") == "unknown"


def test_fallen_blanked_pair_is_unknown():
    assert _verdict("fallen_growers", {**GOOD["fallen_growers"], "pair_blanked": True}, "sales_yoy") == "unknown"


def test_hot_ret_21d_zero_fails():
    assert _verdict("hot", {**GOOD["hot"], "ret_21d": 0.0}, "ret_21d") == "fail"


def test_undervalue_off_list_unknown_when_fundamentals_pass_else_fail():
    assert _verdict("undervalue", {**GOOD["undervalue"], "on_list": False}, "on_list") == "unknown"
    assert _verdict("undervalue", {**GOOD["undervalue"], "on_list": False, "q_yoy_pct": 5.0}, "on_list") == "fail"


def test_quiet_unranked_score_is_unknown():
    assert _verdict("quiet_strong", {**GOOD["quiet_strong"], "score_ranked": False}, "score") == "unknown"


def test_quiet_net_debt_text_and_liabilities_label():
    lg = {x.key: x for x in CR.legs("quiet_strong", {**GOOD["quiet_strong"], "net_debt_ebitda": -0.62})}
    assert lg["net_debt_ebitda"].text == "Net debt / EBITDA -0.62 (net cash)"
    assert lg["liab_to_equity"].label == "Liabilities / equity"
    assert "debt" not in lg["liab_to_equity"].text.lower()
    assert {x.key: x for x in CR.legs("quiet_strong", {**GOOD["quiet_strong"], "net_debt_ebitda": None})
            }["net_debt_ebitda"].text == "—"


def test_quiet_reproduction_on_the_11_12_pass_set():
    doc = json.loads((FIX / "quiet_pass_2026_11_12.json").read_text(encoding="utf-8"))
    pop = doc["population"]
    assert len(pop) == 29
    saved = {"HLNE", "NVDA", "META", "GOOGL", "NXT", "MPWR", "XPEL", "EPRT", "MGY", "CTRE"}
    top = CR.pick_top("quiet_strong", pop, saved=saved)
    assert top == ["HLNE", "NVDA", "META", "GOOGL", "NXT", "MPWR", "XPEL", "EPRT", "MGY", "CTRE"]
    by = {c["symbol"]: c["values"] for c in pop}
    assert CR.qualifies("quiet_strong", by["AEM"]) is None          # tier unknown
    assert CR.qualifies("quiet_strong", by["LULU"]) is False        # declining
    assert CR.qualifies("quiet_strong", by["ZM"]) is False          # weak
    assert "GOOG" not in top


def test_share_class_without_saved_keeps_the_first_ranked():
    doc = json.loads((FIX / "quiet_pass_2026_11_12.json").read_text(encoding="utf-8"))
    top = CR.pick_top("quiet_strong", doc["population"])
    assert "GOOG" in top and "GOOGL" not in top


def _cands(cat, n, sector="Technology", **over):
    out = []
    for i in range(n):
        vals = {**GOOD[cat], **over}
        if cat == "s2_growth":
            vals["rs_rank"] = 99 - i
        if cat == "hot":
            vals["ret_21d"] = 50.0 - i
        out.append({"symbol": f"S{i:02d}", "sector": sector, "values": vals})
    return out


def test_negative_sector_cap_three_hot_two():
    assert CR.pick_top("s2_growth", _cands("s2_growth", 11)) == ["S00", "S01", "S02"]
    assert CR.pick_top("hot", _cands("hot", 11)) == ["S00", "S01"]


def test_ten_cap_and_deterministic():
    pop = []
    for i in range(14):
        pop.append({"symbol": f"N{i:02d}", "sector": f"Sec{i}", "values": {**GOOD["s2_growth"], "rs_rank": 90}})
    a = CR.pick_top("s2_growth", pop)
    b = CR.pick_top("s2_growth", list(reversed(pop)))
    assert len(a) == C.PER_CATEGORY and a == b == sorted(a)


def test_negative_non_population_never_picked():
    pop = [{"symbol": "AAA", "sector": "X", "values": {**GOOD["hot"], "served": False}},
           {"symbol": "BBB", "sector": "X", "values": {**GOOD["fallen_growers"], "in_served_pool": False}}]
    assert CR.pick_top("hot", pop[:1]) == []
    assert CR.pick_top("fallen_growers", pop[1:]) == []
    assert CR.pick_top("s2_growth", [{"symbol": "CCC", "sector": "X",
                                      "values": {**GOOD["s2_growth"], "qualifier": None}}]) == []


def test_negative_pankaj_never_screened():
    assert CR.pick_top("pankaj", [{"symbol": "TSM", "sector": "X", "values": {}}]) == []
    assert CR.qualifies("pankaj", {"close": 405.49, "zones": {"Agg": (400, 410)}}) is None
    assert CR.in_population("pankaj", {}) is False


ORDER = ("Agg", "C1", "C2", "C3")
TSM = {"Agg": (400.0, 410.0), "C1": (360.0, 375.0), "C2": (310.0, 320.0), "C3": (260.0, 280.0)}
META = {"Agg": (680.0, 700.0), "C1": (620.0, 630.0), "C2": (560.0, 580.0), "C3": (None, None)}
INTU = {"Agg": (255.0, 275.0), "C1": (180.0, 210.0), "C2": (130.0, 145.0), "C3": (None, None)}


def test_zone_read_reproduces_the_11_12_close():
    assert CR.zone_read(TSM, 405.49, "2026-11-12", ORDER)["in"] == ["Agg"]
    assert CR.zone_read(META, 623.61, "2026-11-12", ORDER)["in"] == ["C1"]
    r = CR.zone_read(INTU, 340.17, "2026-11-12", ORDER)
    assert r["in"] == []
    assert r["nearest"] == {"zone": "Agg", "side": "over", "pct": pytest.approx(23.7), "edge": 275.0}


def test_zone_read_below_every_zone_is_under():
    r = CR.zone_read(INTU, 100.0, "2026-11-12", ORDER)
    assert r["nearest"]["side"] == "under" and r["nearest"]["zone"] == "C2" and r["nearest"]["edge"] == 130.0


def test_negative_blank_zones_skipped():
    r = CR.zone_read(INTU, 340.17, "2026-11-12", ORDER)
    assert r["n_zones"] == 3 and "C3" not in r["zones"]
    assert CR.zone_read({"Agg": (None, None)}, 10.0, "d", ("Agg",))["n_zones"] == 0


def test_negative_close_none_is_unknown():
    r = CR.zone_read(TSM, None, None, ORDER)
    assert r["unknown"] is True and r["in"] == [] and r["nearest"] is None


def test_zone_read_reuses_pankaj_setup_status(monkeypatch):
    calls = []

    def fake(setup, price):
        calls.append((setup, price))
        return {"state": "in_zone", "dist_pct": 0.0, "detail": "x"}
    monkeypatch.setattr(PK, "setup_status", fake)
    r = CR.zone_read(INTU, 340.17, "2026-11-12", ORDER)
    assert r["in"] == ["Agg", "C1", "C2"]
    assert calls[0] == ({"kind": "pullback", "zone": {"lo": 255.0, "hi": 275.0}}, 340.17)


def test_zone_pad_is_the_pankaj_pad():
    # 410 * (1 + 0.5%) = 412.05 — inside by the /pankaj page's pad.
    assert CR.zone_read(TSM, 412.0, "d", ORDER)["in"] == ["Agg"]
    assert CR.zone_read(TSM, 412.2, "d", ORDER)["in"] == []


def test_rank_keys():
    assert CR.rank_key("undervalue", {"ratio": 0.2}, "A") < CR.rank_key("undervalue", {"ratio": 0.3}, "A")
    assert CR.rank_key("accel_after_fall", {"growth_yoy_pct": 60, "prior_yoy_pct": 10}, "A") < \
        CR.rank_key("accel_after_fall", {"growth_yoy_pct": 60, "prior_yoy_pct": 30}, "A")
    assert CR.rank_key("s2_growth", {"rs_rank": 90, "scan_score": 80}, "A") < \
        CR.rank_key("s2_growth", {"rs_rank": 90, "scan_score": 70}, "A")
    assert CR.sector_cap("hot") == C.HOT_MAX_PER_SECTOR and CR.sector_cap("bonde") == C.MAX_PER_SECTOR
