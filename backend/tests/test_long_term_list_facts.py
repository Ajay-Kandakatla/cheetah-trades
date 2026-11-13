"""📅 Long Term — `long_term_list.facts` (spec §3.4, WP-DATA, 2026-11-12). PURE.

Ajay 2026-11-12: "Yeah I wanna find out the ones that are actually great in
fundamentals and growth and sales and no debt but not growing in price action
yet.."

Pins the facts shape criteria/notices consume, the values mappers (the SAME
functions the baseline script maps the 11-12 dumps through) and the NEGATIVES:
a failing source -> its categories `ok: False` + reason with NO population
(never an empty pass); no scan doc -> 🚀 💎 📈 🏷️ not read; no long-term doc ->
🌱 not read; a saved name missing everywhere -> `in: []`; a missing quarter end
is None, never invented; NaN never leaves facts.
"""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from long_term_list import constants as C
from long_term_list import criteria as CR
from long_term_list import facts as F
from long_term_list import seed as SEED
from long_term_list import sources as SRC

ET = ZoneInfo("America/New_York")
CACHED_AT = datetime(2026, 11, 8, 23, 30, tzinfo=ET).timestamp()     # an ET date of 11-08


def _scan_row(sym, *, sector="Technology", stage=2, tier="strong", acc=True, c=True, a=True,
              rs=95, score=80.0, roe=25.0, fcf=5.0, nde=0.5, moat=60, bonde="strong", bscore=88,
              turnover=9e7):
    return {"symbol": sym, "name": f"{sym} Inc", "sector": sector, "score": score, "rs_rank": rs,
            "qualifier": True, "is_candidate": True, "stage": {"stage": stage},
            "liquidity": {"avg_dollar_vol": turnover},
            "fundamentals": {"sales": {"tier": tier, "accelerating": acc},
                             "checks": {"c_strong_q_eps": c, "a_strong_y_eps": a}},
            "moat": {"score": moat, "components": {"profitability": {"roe_pct": roe},
                                                   "fcf": {"fcf_margin_pct": fcf},
                                                   "capital": {"net_debt_ebitda": nde}}},
            "buy_verdict": {"bonde": {"tier": bonde, "score": bscore}}}


def _bar(stage=1, close=100.0, below=20.0, above=30.0, dv=5e7, date="2026-11-12"):
    return {"close": close, "close_date": date, "stage": stage, "stage_label": "Basing",
            "stage_bar_date": date, "pct_below_high": below, "pct_above_low": above,
            "dollar_vol_50": dv, "n_bars": 300}


def _lt(score=80.0, np_=1e8, ocf=2e8, cagr=20.0, de=0.5, sector="Technology"):
    return {"m": {"net_profit": np_, "ocf": ocf, "opm": 20.0, "sales_cagr": cagr,
                  "profit_cagr": 15.0, "de": de}, "sector": sector,
            "score": {"score": score, "ranked": True}}


def _ok(**kw):
    return {"ok": True, "reason": None, "as_of": "2026-11-12", "n": 1, **kw}


def _sources(**over):
    rows = {"AAA": _scan_row("AAA"), "BBB": _scan_row("BBB", stage=3)}
    src = {
        "session": "2026-11-13",
        "scan": _ok(rows=rows, candidates=["AAA", "BBB"]),
        "undervalue": _ok(passed=[{"symbol": "AAA", "sector": "Technology", "ratio": 0.2,
                                   "ttm_revenue": 5e8, "q_yoy_pct": 30.0, "ttm_growth_pct": 25.0,
                                   "floor_ok": True}], snaps={}),
        "fallen": _ok(rows={"FAL": {"symbol": "FAL", "pct_below": 55.0, "pct_above_low": 15.0,
                                    "sector": "Healthcare", "in_served_pool": True,
                                    "floor_ok": True,
                                    "sales": {"yoy_pct": 40.0, "pair_blanked": False}}},
                      pool=["FAL"]),
        "hottest": _ok(rows={"HOT": {"symbol": "HOT", "group": "Energy", "sales_tier": "strong",
                                     "q_eps_yoy": 5.0, "ret_21d": 3.0, "served": True},
                             "COLD": {"symbol": "COLD", "group": "Energy", "sales_tier": "strong",
                                      "q_eps_yoy": 5.0, "ret_21d": 9.0, "served": False}}),
        "longterm": _ok(rows={"QQQ1": _lt(), "LOW": _lt(score=50.0)}, sector_map={"ACC": "Industrials"}),
        "research": _ok(rows={
            "AAA": {"sales": {"tier": "strong", "growth_yoy_pct": 44.7, "prior_yoy_pct": 30.0,
                              "accelerating": True},
                    "q_end_series": ["2026-09-27", "2026-06-28"], "cached_at": CACHED_AT},
            "QQQ1": {"sales": {"tier": "steady", "growth_yoy_pct": 12.0}},
            "ACC": {"sales": {"tier": "explosive", "growth_yoy_pct": 150.0, "prior_yoy_pct": 40.0,
                              "accelerating": True}, "cached_at": CACHED_AT}}),
        "frames": _ok(reads={"AAA": _bar(stage=2), "QQQ1": _bar(stage=1),
                             "ACC": _bar(stage=1, below=45.0, above=25.0),
                             "TSM": _bar(stage=3, close=405.49)}),
        "caps": _ok(caps={"ACC": 2e9}),
        "growth_board": _ok(grades={"AAA": "all"}),
    }
    src.update(over)
    return src


SAVED = ["AAA", "BBB", "FAL", "HOT", "QQQ1", "ACC", "TSM", "GONE"]


def _seed_tsm():
    return {"categories": [{"key": "pankaj", "names": [
        {"sym": "TSM", "tier": "A", "zt": "8.8", "action": "Buy Zone AAG1",
         "zones": {"Agg": [400.0, 410.0], "C1": [360.0, 375.0], "C2": [None, None],
                   "C3": [None, None]}}]}]}


# --------------------------------------------------------------------------
# shape
# --------------------------------------------------------------------------
def test_facts_shape_and_every_category_present():
    f = F.build(_sources(), SAVED, _seed_tsm())
    assert set(f) == {"session", "sources", "names", "categories"}
    assert f["session"] == "2026-11-13"
    assert set(f["sources"]) == set(SRC.SOURCE_KEYS)
    for k, m in f["sources"].items():
        assert set(m) == {"ok", "reason", "as_of", "n"}, k
    assert set(f["categories"]) == set(C.CATEGORY_KEYS)
    for cat, c in f["categories"].items():
        assert set(c) == {"ok", "reason", "population", "lookup"}
        if cat != C.PANKAJ_KEY:
            assert set(c["lookup"]) == set(SAVED)
    assert set(f["names"]) == set(SAVED)
    want = {"symbol", "name", "sector", "stage", "stage_label", "stage_bar_date", "close",
            "close_date", "sales_tier", "sales_yoy_pct", "sales_prior_yoy_pct", "sales_q_end",
            "sales_read_on", "in"}
    assert set(f["names"]["AAA"]) == want


def test_sales_quarter_end_and_read_date():
    f = F.build(_sources(), SAVED, None)
    a = f["names"]["AAA"]
    assert a["sales_q_end"] == "2026-09-27" and a["sales_read_on"] == "2026-11-08"
    assert a["sales_tier"] == "strong" and a["sales_yoy_pct"] == 44.7
    q = f["names"]["QQQ1"]
    assert q["sales_q_end"] is None and q["sales_read_on"] is None      # never invented


def test_NEG_a_saved_name_missing_everywhere_reads_in_empty():
    f = F.build(_sources(), SAVED, None)
    g = f["names"]["GONE"]
    assert g["in"] == [] and g["stage"] is None and g["close"] is None and g["sales_tier"] is None
    for cat in C.SCREENED_KEYS:
        assert f["categories"][cat]["lookup"]["GONE"]["values"]
        assert CR.qualifies(cat, f["categories"][cat]["lookup"]["GONE"]["values"]) is not True
    assert sorted(f["names"]["AAA"]["in"]) == sorted(
        ["scan", "undervalue", "research", "frames", "growth_board"])


# --------------------------------------------------------------------------
# fenced sources -> categories not read
# --------------------------------------------------------------------------
@pytest.mark.parametrize("key", list(SRC.SOURCE_KEYS))
def test_NEG_each_failing_source_marks_its_categories_not_read(key):
    f = F.build(_sources(**{key: SRC.fail("boom")}), SAVED, _seed_tsm())
    assert f["sources"][key] == {"ok": False, "reason": "boom", "as_of": None, "n": 0}
    hit = [c for c, need in F.CATEGORY_SOURCES.items() if key in need]
    for cat in C.CATEGORY_KEYS:
        c = f["categories"][cat]
        if cat in hit:
            assert c["ok"] is False and key in c["reason"] and "boom" in c["reason"]
            assert c["population"] == []                  # never an empty pass
        else:
            assert c["ok"] is True and c["reason"] is None


def test_NEG_no_scan_doc_scan_categories_not_read():
    f = F.build(_sources(scan=SRC.fail("no scan doc")), SAVED, None)
    for cat in ("s2_growth", "capital_quality", "bonde", "undervalue"):
        assert f["categories"][cat]["ok"] is False and "no scan doc" in f["categories"][cat]["reason"]
    assert f["categories"]["fallen_growers"]["ok"] is True


def test_NEG_no_long_term_doc_quiet_strong_not_read():
    f = F.build(_sources(longterm=SRC.fail("no long-term doc")), SAVED, None)
    c = f["categories"]["quiet_strong"]
    assert c["ok"] is False and "no long-term doc" in c["reason"] and c["population"] == []
    v = c["lookup"]["QQQ1"]["values"]
    assert v["score"] is None and CR.qualifies("quiet_strong", v) is None


def test_NEG_a_missing_source_key_is_not_read_never_ok():
    src = _sources()
    del src["caps"]
    f = F.build(src, SAVED, None)
    assert f["sources"]["caps"]["ok"] is False
    assert f["categories"]["accel_after_fall"]["ok"] is False


# --------------------------------------------------------------------------
# the mappers
# --------------------------------------------------------------------------
def test_scan_mappers_and_the_bar_stage_wins():
    f = F.build(_sources(), SAVED, None)
    s2 = f["categories"]["s2_growth"]["lookup"]["AAA"]
    assert s2["sector"] == "Technology"
    assert s2["values"] == {"qualifier": True, "stage": 2, "sales_tier": "strong",
                            "sales_accelerating": True, "c_strong_q_eps": True,
                            "a_strong_y_eps": True, "rs_rank": 95.0, "scan_score": 80.0}
    assert CR.qualifies("s2_growth", s2["values"]) is True
    bbb = f["categories"]["s2_growth"]["lookup"]["BBB"]["values"]
    assert bbb["stage"] == 3                              # no bar read -> the scan's own stage
    assert F.values_s2(_scan_row("X", stage=2), stage=4)["stage"] == 4
    cq = f["categories"]["capital_quality"]["lookup"]["AAA"]["values"]
    assert cq["roe_pct"] == 25.0 and cq["net_debt_ebitda"] == 0.5 and cq["cq_grade"] == "all"
    bd = f["categories"]["bonde"]["lookup"]["AAA"]["values"]
    assert bd["bonde_tier"] == "strong" and bd["bonde_score"] == 88.0
    assert [c["symbol"] for c in f["categories"]["s2_growth"]["population"]] == ["AAA", "BBB"]


def test_undervalue_on_list_and_off_list_through_the_vs_peers_helpers(monkeypatch):
    from chart_maps import undervalue_peers as UVP
    f = F.build(_sources(), SAVED, None)
    on = f["categories"]["undervalue"]["lookup"]["AAA"]["values"]
    assert on["on_list"] is True and on["ratio"] == 0.2 and on["floor_ok"] is True
    seen = []
    monkeypatch.setattr(UVP, "ttm_revenue", lambda rev, per=None, off=0: seen.append(off) or 7e8)
    monkeypatch.setattr(UVP, "q_yoy_pct", lambda snap: 33.0)
    monkeypatch.setattr(UVP, "ttm_growth_pct", lambda rev, per=None: 21.0)
    off = F.values_uv(None, {"rev_q_series": [1] * 8, "q_period_series": [], "_source": "massive"},
                      _scan_row("BBB"))
    assert off == {"ttm_revenue": 7e8, "q_yoy_pct": 33.0, "ttm_growth_pct": 21.0,
                   "on_list": False, "floor_ok": True, "ratio": None}
    assert seen == [0]
    assert CR.qualifies("undervalue", off) is None        # off-list, F legs pass -> unknown


def test_NEG_undervalue_off_list_without_a_readable_snapshot_is_unknown():
    for snap in (None, {"_source": "yfinance", "rev_q_series": [1e9] * 8}):
        v = F.values_uv(None, snap, None)
        assert v["ttm_revenue"] is None and v["floor_ok"] is None and v["on_list"] is False
        assert all(lg.verdict != CR.PASS for lg in CR.legs("undervalue", v))


def test_fallen_hot_quiet_accel_mappers_and_populations():
    f = F.build(_sources(), SAVED, None)
    fv = f["categories"]["fallen_growers"]["lookup"]["FAL"]
    assert fv["sector"] == "Healthcare" and fv["values"]["pct_below_high"] == 55.0
    assert fv["values"]["sales_yoy_pct"] == 40.0 and fv["values"]["in_served_pool"] is True
    assert [c["symbol"] for c in f["categories"]["fallen_growers"]["population"]] == ["FAL"]
    assert [c["symbol"] for c in f["categories"]["hot"]["population"]] == ["HOT"]   # served only
    hv = f["categories"]["hot"]["lookup"]["HOT"]
    assert hv["sector"] == "Energy" and CR.qualifies("hot", hv["values"]) is True
    q = f["categories"]["quiet_strong"]["lookup"]["QQQ1"]["values"]
    assert q["liab_to_equity"] == 0.5 and q["stage"] == 1 and q["sales_tier"] == "steady"
    assert q["dollar_vol_50"] == 5e7 and q["pct_below_high"] == 20.0
    assert [c["symbol"] for c in f["categories"]["quiet_strong"]["population"]] == ["QQQ1"]
    a = f["categories"]["accel_after_fall"]["lookup"]["ACC"]
    assert a["sector"] == "Industrials"                    # no scan row -> the companies map
    assert a["values"]["market_cap"] == 2e9 and a["values"]["growth_yoy_pct"] == 150.0
    assert CR.qualifies("accel_after_fall", a["values"]) is True
    assert [c["symbol"] for c in f["categories"]["accel_after_fall"]["population"]] == ["AAA", "ACC"]


def test_quiet_net_debt_is_info_from_the_scan_row():
    v = F.values_quiet(_lt(), _bar(), {"sales": {"tier": "strong"}}, _scan_row("Z", nde=5.07))
    assert v["net_debt_ebitda"] == 5.07
    assert CR.qualifies("quiet_strong", v) is True        # info never gates
    assert F.values_quiet(_lt(), _bar(), None, None)["net_debt_ebitda"] is None


def test_pankaj_lookup_from_the_seed_entry_and_the_closed_close():
    f = F.build(_sources(), SAVED, _seed_tsm())
    c = f["categories"]["pankaj"]
    assert c["population"] == [] and set(c["lookup"]) == {"TSM"}
    v = c["lookup"]["TSM"]["values"]
    assert v["close"] == 405.49 and v["tier"] == "A" and v["zt"] == "8.8"
    assert "action" not in v and v["zones"]["Agg"] == (400.0, 410.0)
    zr = CR.zone_read(v["zones"], v["close"], v["close_date"], SEED.zone_order(_full_seed()))
    assert zr["in"] == ["Agg"]


def _full_seed():
    return SEED.load()


def test_NEG_nan_never_leaves_facts():
    src = _sources()
    src["frames"]["reads"]["AAA"] = _bar(stage=2, close=float("nan"), dv=float("inf"))
    src["research"]["rows"]["AAA"]["sales"]["growth_yoy_pct"] = float("nan")
    f = F.build(src, SAVED, _seed_tsm())
    json.dumps(f, allow_nan=False, default=list)
    assert f["names"]["AAA"]["close"] is None and f["names"]["AAA"]["sales_yoy_pct"] is None


def test_NEG_facts_is_pure_no_io_imports():
    src = open(F.__file__, encoding="utf-8").read()
    for bad in ("bulk_cached_frames", "load_latest", "_get_mongo", "decision_snapshot(",
                "requests", "load_prices", "market_caps_for("):
        assert bad not in src, bad
