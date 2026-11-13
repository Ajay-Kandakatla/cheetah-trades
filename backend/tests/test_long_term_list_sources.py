"""📅 Long Term — `long_term_list.sources` (spec §3.8, WP-DATA, 2026-11-12).

Ajay 2026-11-12: "keep updating it from all the other tabs info.. Weekly and if
something gets dropped let me know".

Every source is read in-process from the source tab's own engine, cache only,
and FENCED: a failure is `ok: False` + a reason — never an empty pass, never a
zero. Hermetic: the conftest refuses Mongo; every engine is monkeypatched.
NEGATIVES: each source failing; no HTTP (socket refused); `load_prices` never
called by the request-time 🧭 read; caps read with `cap=0`; < 220 bars -> no
stage; a today bar before 16:30 ET dropped.
"""
from __future__ import annotations

import inspect
import socket
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from long_term_list import constants as C
from long_term_list import sources as SRC

ET = ZoneInfo("America/New_York")
THU = "2026-11-12"


def _frame(n=300, end=THU, start_px=50.0, step=0.2, vol=1_000_000.0):
    idx = pd.bdate_range(end=end, periods=n)
    close = start_px + step * np.arange(n)
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                         "close": close, "volume": vol}, index=idx)


def _at(h, m, day=THU):
    y, mo, d = (int(x) for x in day.split("-"))
    return datetime(y, mo, d, h, m, tzinfo=ET)


# --------------------------------------------------------------------------
# closed bars + the bar read
# --------------------------------------------------------------------------
def test_closed_frame_drops_a_today_bar_before_the_rerate_and_keeps_it_at_1630():
    df = _frame()
    assert str(SRC.closed_frame(df, _at(16, 29)).index[-1])[:10] == "2026-11-11"
    assert str(SRC.closed_frame(df, _at(10, 0)).index[-1])[:10] == "2026-11-11"
    assert str(SRC.closed_frame(df, _at(16, 30)).index[-1])[:10] == THU
    assert str(SRC.closed_frame(df, _at(9, 0, "2026-11-13")).index[-1])[:10] == THU


def test_bar_read_uses_the_stage_engine_on_closed_bars(monkeypatch):
    from sepa import stage
    seen = []
    real = stage.classify

    def spy(d, vol=None):
        seen.append(str(d.index[-1])[:10])
        return real(d, vol=vol)
    monkeypatch.setattr(stage, "classify", spy)
    r = SRC.bar_read(_frame(), _at(16, 29))
    assert seen == ["2026-11-11"] and r["close_date"] == "2026-11-11"
    from sepa import volume
    d = SRC.closed_frame(_frame(), _at(16, 29))
    assert r["stage"] == real(d, vol=volume.analyze(d))["stage"]
    assert r["stage_label"] == real(d, vol=volume.analyze(d))["label"]
    assert r["stage_bar_date"] == "2026-11-11" and r["n_bars"] == 299
    r2 = SRC.bar_read(_frame(), _at(16, 30))
    assert seen[-1] == THU and r2["close_date"] == THU


def test_bar_read_52w_and_dollar_volume_come_from_the_app_engines():
    from sepa import adr, trend_template
    df = _frame()
    r = SRC.bar_read(df, _at(17, 0))
    tt = trend_template.evaluate("", df)
    assert r["pct_below_high"] == tt.pct_below_high and r["pct_above_low"] == tt.pct_above_low
    assert r["dollar_vol_50"] == adr.liquidity_check(df)["avg_dollar_vol"]


def test_NEG_under_220_bars_no_stage_no_52w_and_under_50_no_dollar_volume():
    r = SRC.bar_read(_frame(n=219), _at(17, 0))
    assert r["stage"] is None and r["stage_label"] is None and r["pct_below_high"] is None
    assert r["close"] is not None and r["dollar_vol_50"] is not None
    r = SRC.bar_read(_frame(n=30), _at(17, 0))
    assert r["dollar_vol_50"] is None                    # never adr's 0 for "insufficient"
    assert SRC.bar_read(None, _at(17, 0))["close"] is None


# --------------------------------------------------------------------------
# each source fenced
# --------------------------------------------------------------------------
def test_NEG_no_scan_doc_is_not_read(monkeypatch):
    from sepa import scanner
    monkeypatch.setattr(scanner, "load_latest", lambda: None)
    got = SRC._fenced("scan", SRC.read_scan)
    assert got["ok"] is False and got["reason"] == "no scan doc" and got["n"] == 0
    monkeypatch.setattr(scanner, "load_latest", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    got = SRC._fenced("scan", SRC.read_scan)
    assert got["ok"] is False and "RuntimeError" in got["reason"]


def test_scan_rows_and_candidates(monkeypatch):
    from sepa import scanner
    rows = [{"symbol": "aaa", "sector": "Tech", "score": 9, "is_candidate": True,
             "fundamentals": {"sales": {"tier": "strong"}, "checks": {}, "huge": [1] * 9}},
            {"symbol": "BBB", "sector": "Tech", "is_candidate": False}]
    monkeypatch.setattr(scanner, "load_latest", lambda: {
        "generated_at": 1794519071, "all_results": rows, "candidates": [rows[0], rows[1]]})
    got = SRC.read_scan()
    assert got["ok"] is True and got["candidates"] == ["AAA"] and set(got["rows"]) == {"AAA", "BBB"}
    assert got["as_of"].startswith("2026-11-12T16:31") and "huge" not in got["rows"]["AAA"]["fundamentals"]


def test_undervalue_passed_rows_and_floor(monkeypatch):
    from chart_maps import undervalue_peers as UVP
    inputs = {"rows": [], "snaps": {"AVT": {"x": 1}, "ZZZ": {}}, "caps": {}, "cap_meta": {},
              "generation": 1, "scan_generated_at": 1794519071}
    monkeypatch.setattr(UVP, "_load_inputs", lambda: inputs)
    monkeypatch.setattr(UVP, "build", lambda **kw: {"counts": {}, "passed": [
        {"symbol": "AVT", "sector": "Technology", "ratio": 0.06, "discount_pct": 94.0,
         "ttm_revenue": 2.7e10, "q_yoy_pct": 48.0, "ttm_growth_pct": 24.0,
         "scan_row": {"liquidity": {"avg_dollar_vol": 9e7}}},
        {"symbol": "THN", "sector": "Technology", "ratio": 0.2, "scan_row": {}}]})
    monkeypatch.setattr(UVP, "build_failure", lambda counts: None)
    got = SRC.read_undervalue({"AVT", "NOPE"})
    assert got["ok"] is True and [p["symbol"] for p in got["passed"]] == ["AVT", "THN"]
    assert got["passed"][0]["floor_ok"] is True
    assert got["passed"][1]["floor_ok"] is False         # unknown turnover fails a real floor
    assert set(got["snaps"]) == {"AVT"} and got["as_of"] == THU
    monkeypatch.setattr(UVP, "build_failure", lambda counts: UVP.ERR_NO_SCAN)
    bad = SRC._fenced("undervalue", SRC.read_undervalue, {"AVT"})
    assert bad["ok"] is False and bad["reason"] == UVP.ERR_NO_SCAN


def _fallen_entry():
    def r(sym, pct, turn, g):
        return {"symbol": sym, "pick": {"n_pass": 3}, "pct_below": pct, "pct_above_low": 20.0,
                "close": 5.0, "close_date": THU, "sector": "Tech", "growth_yoy_pct": g,
                "metrics": {"avg_turnover": turn}, "market_cap": 1e9}
    rows = [r("AAA", 60.0, 9e7, 50.0), r("BBB", 45.0, 1.0, 80.0), r("CCC", 41.0, 9e7, 30.0),
            r("SAV", 20.0, 9e7, 30.0)]
    return {"rows": {x["symbol"]: x for x in rows}, "counts": {}, "session": "2026-11-13",
            "as_of": THU}


def test_fallen_pool_is_the_served_pool_in_page_order(monkeypatch):
    from chart_maps import board as B
    from chart_maps import fallen_tab as FAL
    e = _fallen_entry()
    seen = {}
    monkeypatch.setattr(FAL, "cached_or_warm",
                        lambda u, now=None, sync=False: seen.update(u=u, sync=sync)
                        or {"state": "ready", "entry": e})
    got = SRC.read_fallen(_at(21, 0), {"SAV"})
    kept, *_ = B.fallen_pool(e, sort=C.FALLEN_SORT, depth=int(C.FALLEN_MIN_PCT_BELOW),
                             min_tier=C.FLOOR_TIER)
    assert got["pool"] == [r["symbol"] for r, _m in kept][:C.FALLEN_PAGE]
    assert "BBB" not in got["pool"] and "BBB" not in got["rows"]      # thin, not saved
    assert got["rows"]["SAV"]["in_served_pool"] is False          # saved, read, not in the pool
    assert got["rows"]["AAA"]["sales"] == FAL.sales_block(e["rows"]["AAA"])
    assert seen == {"u": "full", "sync": True} and got["session"] == "2026-11-13"


def test_NEG_fallen_not_ready_is_not_read(monkeypatch):
    from chart_maps import fallen_tab as FAL
    monkeypatch.setattr(FAL, "cached_or_warm",
                        lambda u, now=None, sync=False: {"state": "error", "reason": "boom"})
    got = SRC._fenced("fallen", SRC.read_fallen, _at(21, 0), set())
    assert got["ok"] is False and "boom" in got["reason"]


def test_hottest_served_is_the_first_hot_page_per_group(monkeypatch):
    from rotation import api as RA
    from rotation import hottest as H
    names = [{"symbol": f"S{i:02d}", "sales_tier": "strong", "q_eps_yoy": 1.0,
              "ret_21d": 30.0 - i} for i in range(C.HOT_PAGE + 3)]
    table = {"by_symbol": {n["symbol"]: {} for n in names}}
    seen = {}
    monkeypatch.setattr(RA, "_members_table", lambda: (table, {}))
    monkeypatch.setattr(RA, "_members_payload", lambda: {"sectors": []})
    monkeypatch.setattr(H, "_decision_map", lambda syms: {})
    monkeypatch.setattr(H, "_earnings_map", lambda syms: {})

    real_sig = inspect.signature(H._build)

    def fake_build(payload, **kw):
        real_sig.bind(payload, **kw)
        seen.update(kw, members=payload.get("members"))
        return {"as_of": THU, "sectors": [{"group": "Technology", "names": names}]}
    monkeypatch.setattr(H, "_build", fake_build)
    got = SRC.read_hottest()
    assert seen["live"] is None and seen["names_per_group"] == len(names)
    assert seen["members"] is table and seen["sort"] == C.HOT_SORT
    served = [s for s, r in got["rows"].items() if r["served"]]
    assert len(served) == C.HOT_PAGE and got["n"] == C.HOT_PAGE
    assert got["rows"][f"S{C.HOT_PAGE:02d}"]["served"] is False
    assert got["rows"]["S00"]["group"] == "Technology"


HOT_BUILD_KWARGS = ("sort", "direction", "names_per_group", "decisions", "earnings",
                    "live", "pre")


def test_hottest_build_keyword_names_are_pinned_to_the_real_signature():
    from rotation import hottest as H
    params = inspect.signature(H._build).parameters
    for k in HOT_BUILD_KWARGS:
        assert k in params, k
        assert params[k].kind is inspect.Parameter.KEYWORD_ONLY, k
    required = {k for k, p in params.items()
                if p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is p.empty}
    assert required <= set(HOT_BUILD_KWARGS)
    inspect.signature(H._build).bind({}, **{k: None for k in HOT_BUILD_KWARGS})


def test_NEG_a_renamed_hottest_build_keyword_fails_the_bind():
    from rotation import hottest as H
    sig = inspect.signature(H._build)
    kw = {k: None for k in HOT_BUILD_KWARGS}
    kw["names_per_grp"] = kw.pop("names_per_group")
    with pytest.raises(TypeError):
        sig.bind({}, **kw)
    kw = {k: None for k in HOT_BUILD_KWARGS if k != "decisions"}
    with pytest.raises(TypeError):
        sig.bind({}, **kw)


def test_NEG_hottest_without_a_member_table_is_not_read(monkeypatch):
    from rotation import api as RA
    monkeypatch.setattr(RA, "_members_table", lambda: (None, {"reason": "no doc"}))
    got = SRC._fenced("hottest", SRC.read_hottest)
    assert got["ok"] is False and got["reason"] == "no doc"


def test_NEG_no_long_term_doc_is_not_read(monkeypatch):
    from sepa import longterm as LT
    monkeypatch.setattr(LT, "stored", lambda db=None: {})
    got = SRC._fenced("longterm", SRC.read_longterm)
    assert got["ok"] is False and got["reason"] == "no long-term doc"


def test_NEG_research_unreachable_or_empty_is_not_read(monkeypatch):
    from sepa import research
    monkeypatch.setattr(research, "_get_cache", lambda: None)
    assert SRC._fenced("research", SRC.read_research, {"AMD"}, ["AMD"])["ok"] is False
    monkeypatch.setattr(research, "_get_cache", lambda: object())
    monkeypatch.setattr(research, "decision_snapshot", lambda syms, **k: {})
    monkeypatch.setattr(research, "sales_snapshot", lambda syms, **k: {})
    got = SRC._fenced("research", SRC.read_research, {"AMD"}, ["AMD"])
    assert got["ok"] is False and got["n"] == 0


def test_research_decision_snapshot_wins_for_saved_names(monkeypatch):
    from sepa import research
    monkeypatch.setattr(research, "_get_cache", lambda: object())
    monkeypatch.setattr(research, "decision_snapshot", lambda syms, **k: {
        "AMD": {"sales": {"tier": "strong"}, "q_end_series": ["2026-09-27"], "cached_at": 1.0}})
    monkeypatch.setattr(research, "sales_snapshot", lambda syms, **k: {
        "AMD": {"sales": {"tier": "weak"}}, "XYZ": {"sales": {"tier": "steady"}}})
    got = SRC.read_research({"AMD"}, ["XYZ"])
    assert got["rows"]["AMD"]["q_end_series"] == ["2026-09-27"]
    assert got["rows"]["AMD"]["sales"]["tier"] == "strong" and got["rows"]["XYZ"]["sales"]


def test_NEG_frames_empty_cache_is_not_read(monkeypatch):
    from sepa import prices
    monkeypatch.setattr(prices, "bulk_cached_frames", lambda syms: {})
    got = SRC._fenced("frames", SRC.read_frames, {"AMD"}, _at(17, 0))
    assert got["ok"] is False and got["n"] == 0


def test_NEG_caps_are_read_with_cap_zero_and_empty_is_not_read(monkeypatch):
    from catalysts import promo_circuit as PC
    seen = []

    def fake(syms, closes, fetch=None, coll=None, cap=None, budget_sec=None):
        seen.append(cap)
        return {}
    monkeypatch.setattr(PC, "market_caps_for", fake)
    got = SRC._fenced("caps", SRC.read_caps, {"AAA"}, {"AAA": 5.0})
    assert seen == [0] and got["ok"] is False
    monkeypatch.setattr(PC, "market_caps_for", lambda syms, closes, cap=None, **k:
                        seen.append(cap) or {"AAA": 1e9})
    assert SRC.read_caps({"AAA"}, {"AAA": 5.0})["caps"] == {"AAA": 1e9} and seen[-1] == 0


def test_NEG_every_source_failing_never_raises_and_never_reaches_the_network(monkeypatch):
    """No Mongo (conftest) AND no socket: every source reads not-ok with a reason."""
    from sepa import scanner
    from sepa import universe

    def refuse(*a, **k):
        raise AssertionError("network reached")
    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(scanner, "load_latest", lambda: None)
    monkeypatch.setattr(universe, "load_universe", lambda mode=None: ["AAA", "BBB"])
    from chart_maps import fallen_tab as FAL
    monkeypatch.setattr(FAL, "cached_or_warm",
                        lambda u, now=None, sync=False: {"state": "error", "reason": "no data"})
    from chart_maps import undervalue_peers as UVP
    monkeypatch.setattr(UVP, "_load_inputs", lambda: {"rows": [], "snaps": {}, "caps": {},
                                                      "cap_meta": {}, "generation": None,
                                                      "scan_generated_at": None})
    from growth import api as GA
    monkeypatch.setattr(GA, "_board_payload", lambda: {})
    from rotation import api as RA
    monkeypatch.setattr(RA, "_members_table", lambda: (None, {"reason": "no member table"}))
    out = SRC.load_all(_at(17, 0), saved={"AMD", "TSM"})
    for k in SRC.SOURCE_KEYS:
        assert out[k]["ok"] is False and out[k]["reason"], k
        assert out[k]["n"] == 0, k
    assert out["session"] is None


def test_NEG_sources_never_use_a_fetching_reader():
    src = (SRC.__file__ and open(SRC.__file__, encoding="utf-8").read())
    for bad in ("load_prices(", "requests.", "httpx", "urlopen", "build_live(",
                "_shares_outstanding", "send_to_all"):
        assert bad not in src, bad


# --------------------------------------------------------------------------
# the ONE request-time read
# --------------------------------------------------------------------------
def test_pankaj_closes_closed_bars_only_and_never_load_prices(monkeypatch):
    from sepa import prices
    monkeypatch.setattr(prices, "load_prices",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("fetch")))
    calls = []
    monkeypatch.setattr(prices, "bulk_cached_frames",
                        lambda syms: calls.append(list(syms)) or {"TSM": _frame(), "META": _frame()})
    am = SRC.pankaj_closes(["TSM", "meta", "NVDA"], _at(10, 0))
    assert set(am) == {"TSM", "META"}                     # NVDA not cached -> absent, never 0
    assert am["TSM"]["date"] == "2026-11-11"              # 10:00 ET today bar dropped
    pm = SRC.pankaj_closes(["TSM"], _at(16, 30))
    assert pm["TSM"]["date"] == THU and pm["TSM"]["close"] == float(_frame()["close"].iloc[-1])
    assert calls[0] == ["TSM", "META", "NVDA"] and len(calls) == 2


def test_NEG_pankaj_closes_cache_failure_is_empty_not_zero(monkeypatch):
    from sepa import prices
    monkeypatch.setattr(prices, "bulk_cached_frames",
                        lambda syms: (_ for _ in ()).throw(RuntimeError("down")))
    assert SRC.pankaj_closes(["TSM"], _at(17, 0)) == {}
    monkeypatch.setattr(prices, "bulk_cached_frames", lambda syms: {})
    assert SRC.pankaj_closes(["TSM"], _at(17, 0)) == {}


# --------------------------------------------------------------------------
# 📉 a saved name back above the line (refix 2026-11-12): fallen_tab stores only
# "fallen" rows, so the name's 📉 values come from its own closed-bar read.
# --------------------------------------------------------------------------
SAVE_ALL_PASS = {"stage": 2, "sales_tier": "strong",
                 "legs": {"fallen_growers": {"pct_below_high": "pass", "pct_above_low": "pass",
                                             "sales_yoy": "pass", "floor": "pass"}}}


def _recovered_frame(end=THU):
    """150 bars at 100, down to 50, back up to 70: 30% under the 52-week high,
    40% over the low — above the 📉 line."""
    idx = pd.bdate_range(end=end, periods=300)
    close = np.r_[np.full(150, 100.0), np.linspace(100, 50, 100), np.linspace(50, 70, 50)]
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                         "volume": 1e6}, index=idx)


def _fallen_ok_without(sym_rows=None):
    return {"ok": True, "reason": None, "as_of": THU, "n": 0,
            "rows": dict(sym_rows or {}), "pool": [], "session": "2026-11-13"}


RES_ROWS = {"LUNR": {"sales": {"tier": "strong", "growth_yoy_pct": 35.0, "prior_yoy_pct": 20.0}}}


def _legs(facts, sym="LUNR"):
    from long_term_list import criteria as CR
    vals = facts["categories"]["fallen_growers"]["lookup"][sym]["values"]
    return vals, {lg.key: lg.verdict for lg in CR.legs("fallen_growers", vals)}


def test_fallen_fill_a_recovered_saved_name_reads_its_bars_and_research_sales():
    from chart_maps import fallen_tab as FAL
    reads = {"LUNR": SRC.bar_read(_recovered_frame(), _at(21, 0))}
    assert reads["LUNR"]["pct_below_high"] == pytest.approx(30.0)
    got = SRC.fill_fallen_from_bars(_fallen_ok_without(), {"LUNR"}, reads, RES_ROWS)
    r = got["rows"]["LUNR"]
    assert r["pct_below"] == pytest.approx(30.0) and r["pct_above_low"] == pytest.approx(40.0)
    assert r["in_served_pool"] is False and r["floor_ok"] is None
    assert r["sales"] == FAL.sales_block(RES_ROWS["LUNR"]["sales"])
    assert got["filled_from_frames"] == ["LUNR"] and got["pool"] == [] and got["n"] == 0


def test_fallen_fill_facts_path_a_name_above_the_line_is_a_moved_line_not_not_read():
    """The facts path end to end (the repro of the refix): build -> legs -> detect."""
    from long_term_list import facts as F
    from long_term_list import notices as N
    reads = {"LUNR": SRC.bar_read(_recovered_frame(), _at(21, 0))}
    src = {"fallen": SRC.fill_fallen_from_bars(_fallen_ok_without(), {"LUNR"}, reads, RES_ROWS)}
    fb = F.build(src, ["LUNR"], None)
    vals, legs = _legs(fb)
    assert legs == {"pct_below_high": "fail", "pct_above_low": "pass", "sales_yoy": "pass",
                    "floor": "unknown"}
    assert vals["in_served_pool"] is False
    assert "fallen" in fb["names"]["LUNR"]["in"]                   # read -> no "absent" next week
    assert fb["categories"]["fallen_growers"]["population"] == []
    from long_term_list import criteria as CR
    now = {"stage": 2, "absent": [], "zone_read": None,
           "legs": {"fallen_growers": [lg.to_dict() for lg in CR.legs("fallen_growers", vals)]}}
    evs, fl = N.detect("LUNR", ["fallen_growers"], None, None, now, SAVE_ALL_PASS, "2026-11-20")
    assert [e["kind"] for e in evs] == ["moved"]
    assert evs[0]["rings"] is False and "LUNR" in evs[0]["text"]
    assert N.section_for(fl, now, "2026-11-20") == "holding"


def test_NEG_fallen_fill_without_it_the_same_name_reads_unknown_and_absent():
    """Pins what the fill fixes: the bare 📉 source gives every leg unknown."""
    from long_term_list import facts as F
    fb = F.build({"fallen": _fallen_ok_without()}, ["LUNR"], None)
    _vals, legs = _legs(fb)
    assert set(legs.values()) == {"unknown"}
    assert "fallen" not in fb["names"]["LUNR"]["in"]


def test_NEG_fallen_fill_never_overwrites_a_real_fallen_row():
    real = {"symbol": "LUNR", "pct_below": 55.0, "pct_above_low": 12.0, "in_served_pool": True,
            "floor_ok": True, "sales": {}}
    reads = {"LUNR": SRC.bar_read(_recovered_frame(), _at(21, 0))}
    got = SRC.fill_fallen_from_bars(_fallen_ok_without({"LUNR": real}), {"LUNR"}, reads, RES_ROWS)
    assert got["rows"]["LUNR"] == real and got["filled_from_frames"] == []


def test_NEG_fallen_fill_no_frame_or_short_frame_stays_not_read_never_zero():
    short = SRC.bar_read(_recovered_frame().iloc[-100:], _at(21, 0))
    assert short["pct_below_high"] is None
    got = SRC.fill_fallen_from_bars(_fallen_ok_without(), {"LUNR", "GONE"},
                                    {"LUNR": short}, RES_ROWS)
    assert got["rows"] == {} and got["filled_from_frames"] == []


def test_NEG_fallen_fill_a_failed_fallen_source_comes_back_unchanged():
    bad = SRC.fail("📉 list not ready: error boom")
    reads = {"LUNR": SRC.bar_read(_recovered_frame(), _at(21, 0))}
    assert SRC.fill_fallen_from_bars(bad, {"LUNR"}, reads, RES_ROWS) is bad
    from long_term_list import facts as F
    fb = F.build({"fallen": bad}, ["LUNR"], None)
    assert fb["categories"]["fallen_growers"]["ok"] is False


def test_NEG_fallen_fill_a_research_miss_leaves_sales_unknown_not_a_pass():
    from long_term_list import facts as F
    reads = {"LUNR": SRC.bar_read(_recovered_frame(), _at(21, 0))}
    src = {"fallen": SRC.fill_fallen_from_bars(_fallen_ok_without(), {"LUNR"}, reads, {})}
    _vals, legs = _legs(F.build(src, ["LUNR"], None))
    assert legs["sales_yoy"] == "unknown" and legs["pct_below_high"] == "fail"


def test_load_all_fills_a_recovered_saved_fallen_name_from_its_frame(monkeypatch):
    from sepa import prices
    from sepa import universe
    monkeypatch.setattr(universe, "load_universe", lambda mode=None: [])
    for name in ("read_scan", "read_hottest", "read_longterm", "read_growth_board"):
        monkeypatch.setattr(SRC, name, lambda *a, **k: SRC.fail("stub"))
    monkeypatch.setattr(SRC, "read_undervalue", lambda saved: SRC.fail("stub"))
    monkeypatch.setattr(SRC, "read_fallen", lambda now, saved: _fallen_ok_without())
    monkeypatch.setattr(SRC, "read_research",
                        lambda saved, universe: SRC._ok(None, 1, rows=dict(RES_ROWS)))
    monkeypatch.setattr(SRC, "read_caps", lambda syms, closes: SRC.fail("stub"))
    monkeypatch.setattr(prices, "bulk_cached_frames",
                        lambda syms: {"LUNR": _recovered_frame()})
    out = SRC.load_all(_at(21, 0), saved={"LUNR"})
    r = out["fallen"]["rows"]["LUNR"]
    assert out["fallen"]["ok"] is True and r["in_served_pool"] is False
    assert r["pct_below"] == pytest.approx(30.0)
    assert r["sales"]["yoy_pct"] == pytest.approx(35.0)
