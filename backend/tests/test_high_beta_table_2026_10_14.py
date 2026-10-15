"""🎢 High Beta table — header sorts, 5 / 21 days, the Sales view
(chart_maps/high_beta_tab.py, "2026-10-14 b").

Ajay 2026-10-14, verbatim: "Can you add sort function on the headers and also 5
day and 21 days columns to show how they were reacting in price like hot sectors
and also add sales tab make it like hot sector with some important metrics like
EPS, QUAlity and other colums that show the strength of the stock".

Every expected number is derived here from the frames / the decision rows built
in this file, through the SAME engines the module must reuse (🔥 Hottest's
`_fundamentals_row` / `_sort_value`, the tracker's `trailing_return` /
`member_stats`). Hermetic: the research-cache read is monkeypatched
(`HB._fund_source`); un-patched it answers ({}, {}) under tests/conftest.py.

`DEC` / `EARN` / `FUND_SOURCE` are imported by the FE fixture capture (M1) —
keep their names.
"""
from __future__ import annotations

import copy
import inspect
import json
import math
import time
from datetime import datetime
from pathlib import Path

import pytest

from chart_maps import high_beta_tab as HB
from rotation import hottest as HOT
from rotation import tracker as RT

from tests.test_data_spine_2026_09_20 import ADJACENT, IOVA            # noqa: E402
from tests.test_high_beta_tab import (ET, FRI, NOW_AFTER, NOW_NIGHT, NOW_RTH, UNIVERSE,  # noqa: E402
                                      _entry, _frame, _frames, _prev, _r, _snap, _strings)

BACKEND = Path(__file__).resolve().parents[1]
SRC = (BACKEND / "chart_maps" / "high_beta_tab.py").read_text(encoding="utf-8")

# research-cache rows shaped like `sepa.research.decision_snapshot` (the fields
# `HOT._fundamentals_row` reads). AAA / CCC / DDD carry a four-quarters-apart pair;
# BBB carries IOVA's real mismatched keys (the YoY pair guard blanks its YoY legs).
_T1 = datetime(2026, 10, 1, 12, 0, tzinfo=ET).timestamp()
_T0 = datetime(2026, 9, 28, 12, 0, tzinfo=ET).timestamp()
DEC = {
    "AAA": {"_source": "massive", "cached_at": _T1, "q_period_series": list(ADJACENT),
            "sales": {"growth_yoy_pct": 85.0, "prior_yoy_pct": 40.0, "accelerating": True,
                      "tier": "explosive"},
            "q_eps_growth_pct": 120.0, "y_eps_growth_pct": 60.0,
            "earnings_quality": {"score": 78.0, "tier": "accelerating", "code_33": True,
                                 "components": {"npm_latest_pct": 18.5, "npm_expanding": True,
                                                "sales_backed": True},
                                 "red_flags": {"inventory_vs_sales": False}}},
    "BBB": {"_source": "massive", "cached_at": _T1, "q_period_series": list(IOVA),
            "sales": {"growth_yoy_pct": 300.0, "prior_yoy_pct": 120.0, "accelerating": True,
                      "tier": "strong"},
            "q_eps_growth_pct": 200.0,
            "earnings_quality": {"score": 55.0, "tier": "steady", "code_33": False,
                                 "components": {"npm_latest_pct": 5.0, "npm_expanding": False},
                                 "red_flags": {"inventory_vs_sales": True}}},
    "CCC": {"_source": "massive", "cached_at": _T0, "q_period_series": list(ADJACENT),
            "sales": {"growth_yoy_pct": 12.25, "prior_yoy_pct": 14.0, "accelerating": False,
                      "tier": "steady"},
            "q_eps_growth_pct": -10.0,
            "earnings_quality": {"score": 40.0, "tier": "weak",
                                 "components": {"npm_latest_pct": -3.0}}},
    "DDD": {"_source": "massive", "cached_at": _T1,
            "sales": {"growth_yoy_pct": 2.0, "tier": "weak"}},
}
# keyed by `_id` in the real collection (the `_earnings_map` trap); the map Hottest serves
EARN = {"AAA": {"_id": "AAA", "next_date": "2026-10-20", "when": "amc"},
        "BBB": {"_id": "BBB", "next_date": "2026-11-05", "when": "bmo"},
        "DDD": {"_id": "DDD", "next_date": "2026-10-08"}}


def FUND_SOURCE(symbols):                                   # noqa: N802  (imported by the M1 capture)
    syms = [str(s).upper() for s in symbols]
    return ({s: DEC[s] for s in syms if s in DEC}, {s: EARN[s] for s in syms if s in EARN})


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for m in (HB._memo, HB._base_memo, HB._failures, HB._fund_memo):
        m.clear()
    HB._warming.clear()
    spawned = []
    monkeypatch.setattr(HB, "_spawn", lambda target, name: spawned.append((target, name)))
    yield spawned
    for m in (HB._memo, HB._base_memo, HB._failures, HB._fund_memo):
        m.clear()


def _build(frames, now, *, universe=None, snaps=None, fund_fn=None, qqq=("AAA",)):
    return HB.build("full", now, universe_fn=lambda u: list(universe or UNIVERSE),
                    frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                    qqq_fn=lambda: list(qqq), etf_fn=lambda: {"XLV", "SPY", "RSP", "QQQ"},
                    is_delisted=lambda s: False,
                    snap_fn=lambda syms: {s: v for s, v in (snaps or {}).items() if s in syms},
                    levered_fn=lambda **k: {"state": "missing"}, fund_fn=fund_fn)


def _closes(df) -> list:
    return [float(c) for c in df["close"].tolist()]


def _pct(a, b) -> float:
    return round((a / b - 1.0) * 100.0, 2)


def _mixed_entry():
    """Rows with ties, gaps and NaN in every header column (the generic path)."""
    vals = [None, 1.0, 2.0, -3.0, 2.0, float("nan"), 1.0, None, 4.5, -3.0]
    tiers = [None, "explosive", "steady", "weak", "steady", "declining", None, "strong", "junk", "weak"]
    dates = [None, "2026-10-20", "2026-11-01", "junk", "2026-10-20", "2026-10-09", None, "2026-12-01",
             "2026-10-20", None]
    rows = []
    for i, sym in enumerate(["KK", "AB", "ZZ", "MM", "AC", "QQ", "BA", "XY", "CD", "NN"]):
        move = [-4.0, -7.0, 1.0, None, -4.0, 0.0, -2.0, None, -9.0, 3.0][i]
        r = _r(sym, [2.0, 2.5, 1.6, 2.0, 2.0, 3.1, 1.5, 2.2, 2.5, 1.9][i], move,
               state="read" if move is not None else "no_print", sigma=vals[(i + 3) % 10])
        r["cats"] = ["b15", "b20", "top20"][: 1 + i % 3]
        r["qqq"] = bool(i % 2)
        r["levered"] = [{"etf": f"{sym}L", "factor": 2.0, "direction": "long"}] * (i % 3)
        for j, k in enumerate(("ret_5d", "rel_5d", "ret_21d", "rel_21d", "rs_spy_63d")):
            r[k] = vals[(i + j) % 10]
        r["fund"] = None if i == 6 else {
            **{k: None for k in HB.FUND_ROW_KEYS},
            "sales_yoy": vals[(i + 5) % 10], "q_eps_yoy": vals[(i + 6) % 10],
            "net_margin": vals[(i + 7) % 10], "eq_score": vals[(i + 8) % 10],
            "sales_tier": tiers[i], "next_earnings": dates[i]}
        rows.append(r)
    return _entry(*rows)


# --------------------------------------------------------------------------
# 1 — GOLDEN: the three presets in their first direction are the old sort_key, verbatim
# --------------------------------------------------------------------------
def _test09_entry():
    return _entry(_r("A", 3.0, -4.0, sigma=2.0), _r("B", 1.5, -7.0, sigma=5.0),
                  _r("C", 2.0, -6.0, sigma=None), _r("D", 2.0, 1.0, sigma=9.0),
                  _r("E", 2.0, None, state="no_print", sigma=1.0), _r("F", 2.0, 0.0, sigma=3.0),
                  _r("G", 2.0, -6.0, sigma=4.0))


@pytest.mark.parametrize("green", [True, False])
def test_01_golden_presets_equal_the_legacy_sort_key(green):
    entries = [_test09_entry(), _build(_frames(), NOW_NIGHT)]
    for e in entries:
        every = list(e["rows"].values())
        for k in ("default", "volume", "junk", HB.SORT_SWING, HB.SORT_DROP, HB.SORT_VOL):
            srt = HB.resolve_sort(k)
            want = [r["symbol"] for r in sorted(every, key=HB.sort_key(srt))
                    if green or HB.is_red(r)]
            for d in (None, HB.PRESET_DIRS[srt]):
                got = [r["symbol"] for r in HB.rank(e, sort=k, direction=d, include_green=green)[0]]
                assert got == want, (k, d)
    # test_09's pinned lists, unchanged
    e = _test09_entry()
    assert [r["symbol"] for r in HB.rank(e, sort="default", include_green=True)[0]] == \
        ["C", "G", "A", "B", "F", "D", "E"]
    assert [r["symbol"] for r in HB.rank(e, sort=HB.SORT_DROP, direction="asc", include_green=True)[0]] == \
        ["B", "C", "G", "A", "F", "D", "E"]
    assert [r["symbol"] for r in HB.rank(e, sort=HB.SORT_VOL, direction="desc", include_green=True)[0]] == \
        ["D", "B", "G", "F", "A", "E", "C"]


def test_01b_the_constants_hold_the_contract():
    assert HB.TAB_SORTS[:3] == (HB.SORT_SWING, HB.SORT_DROP, HB.SORT_VOL)
    assert set(HB.TAB_SORTS) == set(HB.HEADER_SORTS) and len(HB.TAB_SORTS) == 19
    assert HB.HEADER_SORTS[HB.SORT_DROP] == ("today", "asc")
    assert HB.HEADER_SORTS[HB.SORT_SYMBOL] == ("symbol", "asc")
    assert HB.HEADER_SORTS[HB.SORT_NEXT_ER] == ("next_earnings", "asc")
    assert HB.HEADER_SORTS[HB.SORT_LEVERED] == ("levered", "desc")              # B3
    assert {d for k, (_c, d) in HB.HEADER_SORTS.items()
            if k not in (HB.SORT_DROP, HB.SORT_SYMBOL, HB.SORT_NEXT_ER)} == {"desc"}
    assert [k for k, _l in HB.TABLE_COLUMNS] == ["symbol", "levered", "today", "ret_5d", "rel_5d",
                                                 "ret_21d", "rel_21d", "beta", "swing", "sigma",
                                                 "cats", "qqq"]
    assert [k for k, _l in HB.SALES_COLUMNS] == ["symbol", "levered", "today", "sales_yoy",
                                                 "sales_tier", "q_eps_yoy", "net_margin", "eq_score",
                                                 "next_earnings", "rs_spy_63d"]
    cols = {k for k, _l in HB.TABLE_COLUMNS} | {k for k, _l in HB.SALES_COLUMNS}
    assert cols == set(HB.COLUMN_SORT)                                         # every column sorts (K4)
    assert (HB.LEG_FAST, HB.LEG_SHORT, HB.RS_WINDOW) == (RT.WINDOW_FAST, RT.WINDOW_SHORT,
                                                         RT.WINDOW_MED) == (5, 21, 63)
    assert HB.TAIL_BARS == 64 and HB.RS_BENCH == "SPY" and HB.REL_FALLBACK == "SPY"
    assert set(HOT.FUND_SORTS) | {"sales_tier", "next_earnings"} == \
        {k for k, _l in HB.SALES_COLUMNS[3:9]}


# --------------------------------------------------------------------------
# 2 — every key × both directions: monotone, missing last (NEGATIVE), ties A→Z
# --------------------------------------------------------------------------
@pytest.mark.parametrize("key", [k for k in HB.HEADER_SORTS if k != HB.SORT_SYMBOL])
@pytest.mark.parametrize("d", ["desc", "asc"])
def test_02_every_header_sort_is_monotone_missing_last_ties_a_to_z(key, d):
    e = _mixed_entry()
    if key in HB.PRESET_DIRS and d == HB.PRESET_DIRS[key]:
        pytest.skip("the legacy path — test_01")
    col = HB.HEADER_SORTS[key][0]
    rows = HB.rank(e, sort=key, direction=d, include_green=True)[0]
    pairs = [(HOT._sort_value(HB.sort_fields(r, qqq_available=True), col), r["symbol"]) for r in rows]
    present = [p for p in pairs if p[0][0] == 1]
    missing = [p for p in pairs if p[0][0] == 0]
    assert pairs == present + missing, "a missing value floated above a present one"      # NEGATIVE
    assert present, "the fixture must carry values for every column"
    assert [s for _v, s in missing] == sorted(s for _v, s in missing)                        # A→Z
    for (a, sa), (b, sb) in zip(present, present[1:]):
        if d == "desc":
            assert a[1] >= b[1], (key, a, b)
        else:
            assert a[1] <= b[1], (key, a, b)
        if a[1] == b[1]:
            assert sa < sb, ("ties A→Z", key, sa, sb)


def test_02b_symbol_sorts_both_ways_and_nothing_is_missing():
    e = _mixed_entry()
    up = [r["symbol"] for r in HB.rank(e, sort=HB.SORT_SYMBOL, include_green=True)[0]]
    assert up == sorted(up)
    down = [r["symbol"] for r in HB.rank(e, sort=HB.SORT_SYMBOL, direction="desc", include_green=True)[0]]
    assert down == sorted(up, reverse=True)
    _rows, c, _f = HB.rank(e, sort=HB.SORT_SYMBOL, include_green=True)
    assert c["sort_present"] == len(up) and c["sort_missing"] == 0


def test_02c_NEG_asc_never_floats_a_none_to_the_top():
    e = _entry(_r("A", 2.0, -1.0), _r("B", 2.0, -2.0), _r("C", 2.0, -3.0))
    e["rows"]["A"]["ret_5d"], e["rows"]["B"]["ret_5d"], e["rows"]["C"]["ret_5d"] = None, 5.0, -5.0
    for d, want in (("asc", ["C", "B", "A"]), ("desc", ["B", "C", "A"])):
        got = [r["symbol"] for r in HB.rank(e, sort=HB.SORT_RET_5D, direction=d, include_green=True)[0]]
        assert got == want, d
    _rows, c, _f = HB.rank(e, sort=HB.SORT_RET_5D, direction="asc", include_green=True)
    assert (c["sort_present"], c["sort_missing"]) == (2, 1)


def test_02d_levered_sorts_on_the_tag_count_and_no_tag_is_missing_B3():
    e = _entry(_r("A", 2.0, -1.0), _r("B", 2.0, -2.0), _r("C", 2.0, -3.0), _r("D", 2.0, -4.0))
    tag = {"etf": "X", "factor": 2.0, "direction": "long"}
    e["rows"]["A"]["levered"] = [tag]
    e["rows"]["B"]["levered"] = [tag, tag, tag]
    e["rows"]["C"]["levered"] = []
    for d, want in (("desc", ["B", "A", "C", "D"]), ("asc", ["A", "B", "C", "D"])):
        got = [r["symbol"] for r in HB.rank(e, sort=HB.SORT_LEVERED, direction=d, include_green=True)[0]]
        assert got == want, d                                  # [] and absent sit last both ways
    assert HB.sort_fields(e["rows"]["C"], qqq_available=True)["levered"] is None


def test_02e_NEG_qqq_unread_is_missing_never_not_a_member():
    e = _entry(_r("A", 2.0, -1.0), _r("B", 2.0, -2.0))
    e["rows"]["A"]["qqq"] = True
    assert HB.sort_fields(e["rows"]["A"], qqq_available=True)["qqq"] == 1.0
    assert HB.sort_fields(e["rows"]["B"], qqq_available=True)["qqq"] == 0.0
    assert HB.sort_fields(e["rows"]["A"], qqq_available=False)["qqq"] is None
    e["qqq"] = {"available": False}
    _rows, c, _f = HB.rank(e, sort=HB.SORT_QQQ, include_green=True)
    assert c["sort_present"] == 0 and c["sort_missing"] == 2
    assert [r["symbol"] for r in _rows] == ["A", "B"]                 # nothing read -> A→Z


# --------------------------------------------------------------------------
# 3 — NEGATIVE: junk directions, the preset table
# --------------------------------------------------------------------------
@pytest.mark.parametrize("junk", ["sideways", "", None, 5, "  ", ["asc"]])
def test_03_NEG_junk_direction_is_the_keys_first_direction(junk):
    for k, (_c, first) in HB.HEADER_SORTS.items():
        assert HB.resolve_dir(k, junk) == first
    assert HB.resolve_dir("junk-key", junk) == "desc"                    # -> hb_swing's first


def test_03b_direction_is_case_and_space_tolerant_and_preset_for_table():
    assert HB.resolve_dir(HB.SORT_RET_5D, " ASC ") == "asc"
    assert HB.resolve_dir(HB.SORT_DROP, "Desc") == "desc"
    assert HB.preset_for(HB.SORT_DROP, None) == HB.SORT_DROP
    assert HB.preset_for(HB.SORT_DROP, "asc") == HB.SORT_DROP
    assert HB.preset_for(HB.SORT_DROP, "desc") is None                   # a flipped preset is no preset
    assert HB.preset_for(HB.SORT_RET_5D, None) is None
    assert HB.preset_for("default", None) == HB.SORT_SWING
    assert HB.preset_for(HB.SORT_VOL, "asc") is None and HB.preset_for(HB.SORT_VOL, "x") == HB.SORT_VOL
    assert HB.resolve_sort(HB.SORT_RS) == HB.SORT_RS and HB.resolve_sort(None) == HB.SORT_SWING


# --------------------------------------------------------------------------
# 4 / 5 / 6 — the legs in the three modes
# --------------------------------------------------------------------------
def test_04_closed_legs_are_the_tracker_engine_through_the_session_close():
    fr = _frames()
    e = _build(fr, NOW_NIGHT)
    assert e["mode"] == HB.MODE_CLOSED
    r = e["rows"]["AAA"]
    c = _closes(fr["AAA"].iloc[:-1])                                   # closes before Friday
    p = r["today"]["print"]
    assert p == round(float(fr["AAA"]["close"].iloc[-1]), 4)            # the Friday close (Today's print)
    assert r["ret_5d"] == _pct(p, c[-5]) and r["ret_21d"] == _pct(p, c[-21])
    days = [d.strftime("%Y-%m-%d") for d in fr["AAA"].index[-(HB.TAIL_BARS + 1):]]
    bars = [{"t": t, "c": x} for t, x in zip(days, c[-HB.TAIL_BARS:] + [p])]
    ms = RT.member_stats(bars, bars[-1]["t"])
    assert (r["ret_5d"], r["ret_21d"]) == (ms["ret_5d"], ms["ret_21d"])
    legs = e["legs"]
    rsp_c, spy_c = _closes(fr["RSP"].iloc[:-1]), _closes(fr["SPY"].iloc[:-1])
    rsp_p, spy_p = round(float(fr["RSP"]["close"].iloc[-1]), 4), round(float(fr["SPY"]["close"].iloc[-1]), 4)
    assert legs["RSP"]["ret_5d"] == _pct(rsp_p, rsp_c[-5]) and legs["SPY"]["ret_63d"] == _pct(spy_p, spy_c[-63])
    assert legs["rel"] == "RSP" and legs["rs"] == "SPY" and legs["end"] == FRI.isoformat()
    assert legs["through"] == "session_close"
    assert r["rel_5d"] == round(r["ret_5d"] - legs["RSP"]["ret_5d"], 2)
    assert r["rel_21d"] == round(r["ret_21d"] - legs["RSP"]["ret_21d"], 2)
    assert r["rs_spy_63d"] == round(ms["ret_63d"] - legs["SPY"]["ret_63d"], 2)
    line = HB.returns_line(legs)
    assert "through the Fri 10-02 close, the Today column's session included" in line
    assert "“vs RSP”" in line and "SPY " in line


def test_04b_the_tail_rides_on_the_base_only_and_never_reaches_a_live_row():
    _build(_frames(), NOW_NIGHT)
    base = next(iter(HB._base_memo.values()))["base"]
    assert len(base["rows"]["AAA"]["tail"]) == HB.TAIL_BARS
    assert len(base["bench_tail"]["SPY"]) == HB.TAIL_BARS and base["bench_tail"]["RSP"]
    e = _build(_frames(), NOW_NIGHT)
    assert all("tail" not in r and "bar" not in r for r in e["rows"].values())
    assert HB.close_tail({"2026-01-03": 3.0, "2026-01-01": 1.0, "2026-01-02": 2.0}) == [1.0, 2.0, 3.0]
    assert HB.close_tail({}) == [] and HB.close_tail(None) == []


def _thu_frames():
    return {k: v.iloc[:-1] for k, v in _frames().items()}


def test_05_live_windows_end_at_the_prior_close_and_a_live_crash_moves_none_of_them():
    fr, thu = _frames(), _thu_frames()
    prev = _prev(fr["AAA"])
    snaps = {s: _snap(_prev(fr[s]) * 0.99, _prev(fr[s])) for s in ("SPY", "RSP", "QQQ")}
    e1 = _build(thu, NOW_RTH, snaps={**snaps, "AAA": _snap(prev * 0.98, prev)})
    assert e1["mode"] == HB.MODE_LIVE
    c = _closes(thu["AAA"])
    r1 = e1["rows"]["AAA"]
    assert r1["ret_5d"] == _pct(c[-1], c[-6]) and r1["ret_21d"] == _pct(c[-1], c[-22])
    assert e1["legs"]["through"] == "prior_close" and e1["legs"]["end"] == "2026-10-01"
    HB._memo.clear()
    e2 = _build(thu, NOW_RTH, snaps={**snaps, "AAA": _snap(prev * 0.5, prev)})       # −50% live
    r2 = e2["rows"]["AAA"]
    assert r2["today"]["move_pct"] != r1["today"]["move_pct"]
    for k in ("ret_5d", "ret_21d", "rel_5d", "rel_21d", "rs_spy_63d"):
        assert r2[k] == r1[k] is not None, k                            # NEGATIVE: today is not inside
    # a live name with no print still has its closed legs
    assert e1["rows"]["BBB"]["today"]["state"] != "read" and e1["rows"]["BBB"]["ret_5d"] is not None
    assert "today's live move is the Today column, not inside them" in HB.returns_line(e1["legs"])
    assert "Thu 10-01" in HB.returns_line(e1["legs"])


def test_06_after_the_close_the_windows_end_at_the_today_print_and_no_print_is_no_leg():
    fr, thu = _frames(), _thu_frames()
    at = datetime(2026, 10, 2, 15, 59, tzinfo=ET)
    snaps = {s: _snap(_prev(fr[s]) * 0.99, _prev(fr[s]), at=at) for s in ("SPY", "RSP", "QQQ")}
    prev = _prev(fr["AAA"])
    snaps["AAA"] = _snap(prev * 0.97, prev, at=at)
    e = _build(thu, NOW_AFTER, snaps=snaps)
    assert e["mode"] == HB.MODE_AFTER and e["legs"]["end"] == FRI.isoformat()
    r = e["rows"]["AAA"]
    c = _closes(thu["AAA"])
    assert r["ret_5d"] == _pct(r["today"]["print"], c[-5])
    # NEGATIVE: BBB has no print after the close -> no leg (never a stale window passed off as today's)
    b = e["rows"]["BBB"]
    assert b["today"]["state"] != "read"
    assert all(b[k] is None for k in ("ret_5d", "ret_21d", "rel_5d", "rel_21d", "rs_spy_63d"))
    assert HB.compact_row(b, qqq_available=True)["text"]["ret_5d"] == "—"
    # … and in live mode the same name keeps its closed legs
    assert HB.leg_bars([1.0, 2.0], {"state": "no_print"}, HB.MODE_LIVE) == [{"c": 1.0}, {"c": 2.0}]
    assert HB.leg_bars([1.0, 2.0], {"state": "no_print"}, HB.MODE_AFTER) is None
    assert HB.leg_bars([1.0, 2.0], {"state": "read", "print": 0.0}, HB.MODE_CLOSED) is None
    assert HB.leg_bars([1.0], {"state": "read", "print": 3.0}, HB.MODE_CLOSED) == [{"c": 1.0}, {"c": 3.0}]
    assert HB.leg_bars(None, {"state": "read", "print": 3.0}, HB.MODE_LIVE) is None
    assert HB.window_moves(None) == {"ret_5d": None, "ret_21d": None, "ret_63d": None}


# --------------------------------------------------------------------------
# 7 — NEGATIVE: the bench rule (RSP, else SPY, else blank — never the raw move)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("how", ["missing", "stale"])
def test_07_rsp_missing_or_stale_falls_back_to_spy_and_says_so(how):
    fr = _frames()
    if how == "missing":
        fr.pop("RSP")
    else:
        fr["RSP"] = fr["RSP"].iloc[:-2]                       # last bar Wed: not the prior session
    e = _build(fr, NOW_NIGHT)
    legs = e["legs"]
    assert legs["rel"] == "SPY" and legs["RSP"]["ret_5d"] is None
    r = e["rows"]["AAA"]
    assert r["rel_5d"] == round(r["ret_5d"] - legs["SPY"]["ret_5d"], 2)
    tb = HB.table_block(legs)
    by = {c["key"]: c for c in tb["columns"]}
    assert by["rel_5d"]["label"] == "5 days vs SPY" and by["rel_21d"]["label"] == "21 days vs SPY"
    assert "SPY's" in by["rel_5d"]["title"] and "RSP" not in by["rel_5d"]["title"]
    line = HB.returns_line(legs)
    assert HB.REL_FALLBACK_NOTE in line and "RSP not read / not read" in line
    assert "“vs SPY”" in line


def test_07b_NEG_neither_bench_read_blanks_every_vs_column_and_never_prints_the_raw_move():
    fr = _frames()
    fr.pop("RSP")
    fr["SPY"] = fr["SPY"].iloc[:-1]            # closed mode: SPY has no session bar -> not read
    e = _build(fr, NOW_NIGHT)
    legs = e["legs"]
    assert legs["rel"] is None and legs["rs"] is None
    for r in e["rows"].values():
        if r["ret_5d"] is not None:
            assert r["rel_5d"] is None and r["rel_21d"] is None and r["rs_spy_63d"] is None
            t = HB.compact_row(r, qqq_available=True)["text"]
            assert t["rel_5d"] == t["rel_21d"] == t["rs_spy_63d"] == "—"
            assert t["ret_5d"] != "—"
    assert any(r["ret_5d"] is not None for r in e["rows"].values())
    assert HB.REL_NONE_NOTE in HB.returns_line(legs)
    assert HB.row_legs("X", [1.0] * 70, None, HB.MODE_LIVE, {"rel": None, "rs": None})["rel_5d"] is None


# --------------------------------------------------------------------------
# 8 / 9 / 10 — fundamentals: Hottest's numbers, never a zero, the memo
# --------------------------------------------------------------------------
def test_08_fund_rows_are_hottests_fundamentals_row_verbatim(monkeypatch):
    monkeypatch.setattr(HB, "_fund_source", FUND_SOURCE)
    e = _build(_frames(), NOW_NIGHT)
    listed = sorted(e["rows"])
    assert listed == ["AAA", "BBB", "CCC", "DDD"]
    for s in listed:
        full = HOT._fundamentals_row(s, DEC.get(s), EARN.get(s))
        assert e["rows"][s]["fund"] == {k: full[k] for k in HB.FUND_ROW_KEYS}, s
        assert HB.compact_row(e["rows"][s], qqq_available=True)["fund"] == e["rows"][s]["fund"]
    b = e["rows"]["BBB"]["fund"]                                   # IOVA's pair
    assert b["sales_yoy"] is None and b["q_eps_yoy"] is None and b["period_ok"] is False
    assert b["sales_tier"] == "strong" and b["eq_score"] == 55.0 and b["net_margin"] == 5.0
    a = e["rows"]["AAA"]["fund"]
    assert a["sales_yoy"] == 85.0 and a["next_earnings"] == "2026-10-20" and a["earnings_when"] == "amc"
    f = e["fundamentals"]
    dec = FUND_SOURCE(listed)[0]
    assert f["state"] == HB.FUND_READY and (f["n"], f["of"], f["n_earnings"]) == (4, 4, 3)
    assert f["quality_info"] == HOT._quality_info(dec) and f["as_of"] == HOT._as_of_range(dec)
    blk = HB.fundamentals_block(e)
    assert blk["state"] == "ready" and blk["line"].startswith("Sales view — the \U0001F525 Hottest numbers")
    assert "(figures cached 2026-09-28 to 2026-10-01)" in blk["line"] and "for 4 of 4 names" in blk["line"]
    assert "UNMEASURED" in blk["note"] and blk["reason"] is None
    # sorting on a fundamentals column orders by Hottest's own value
    rows = [r["symbol"] for r in HB.rank(e, sort=HB.SORT_SALES_TIER, include_green=True)[0]]
    assert rows == ["AAA", "BBB", "CCC", "DDD"]                    # explosive › strong › steady › weak
    rows = [r["symbol"] for r in HB.rank(e, sort=HB.SORT_NEXT_ER, include_green=True)[0]]
    assert rows == ["DDD", "AAA", "BBB", "CCC"]                    # soonest first, no date last


def test_08b_quality_info_is_served_as_a_copy_without_group_rows_B7(monkeypatch):
    monkeypatch.setattr(HB, "_fund_source", FUND_SOURCE)
    e = _build(_frames(), NOW_NIGHT)
    want = HOT._quality_info(FUND_SOURCE(sorted(e["rows"]))[0])
    blk = HB.fundamentals_block(e)
    qi = blk["quality_info"]
    assert qi["group_rows"] is None
    assert want["group_rows"] and want["group_rows"] not in json.dumps(blk, ensure_ascii=False)
    assert e["fundamentals"]["quality_info"]["group_rows"] == want["group_rows"]      # memo untouched
    assert {k: v for k, v in qi.items() if k != "group_rows"} == \
        {k: v for k, v in want.items() if k != "group_rows"}
    qi["points"].clear()
    assert e["fundamentals"]["quality_info"]["points"]                                 # a deep copy


@pytest.mark.parametrize("bad", ["raise", "empty", "junk"])
def test_09_NEG_a_failed_or_empty_read_is_not_read_blank_and_not_memoised(monkeypatch, bad):
    calls = []

    def src(syms):
        calls.append(list(syms))
        if bad == "raise":
            raise RuntimeError("research cache down")
        return ({}, {}) if bad == "empty" else ("junk", None)
    monkeypatch.setattr(HB, "_fund_source", src)
    e = _build(_frames(), NOW_NIGHT)
    assert e["fundamentals"]["state"] == HB.FUND_NOT_READ
    assert all(r["fund"] is None for r in e["rows"].values())
    assert HB._fund_memo == {}
    _build(_frames(), NOW_NIGHT)
    assert len(calls) == 2                                          # the next build asks again
    blk = HB.fundamentals_block(e)
    assert blk["state"] == "not_read" and blk["quality_info"] is None and blk["as_of"] is None
    assert "the Sales columns stay blank, never zero" in blk["line"]
    assert ("research cache down" if bad == "raise" else HB.FUND_EMPTY_REASON) in blk["line"]
    for r in e["rows"].values():
        c = HB.compact_row(r, qqq_available=True)
        assert c["fund"] is None
        assert HB.sort_fields(r, qqq_available=True)["sales_yoy"] is None
    _rows, cnt, _f = HB.rank(e, sort=HB.SORT_QUALITY, include_green=True)
    assert cnt["sort_present"] == 0
    assert HB.ORDER_NONE in HB.order_line(HB.SORT_QUALITY, None, cnt)


def test_09b_NEG_a_missing_fundamental_is_none_never_zero(monkeypatch):
    dec = {"AAA": DEC["AAA"]}                                       # BBB / CCC / DDD unanswered
    monkeypatch.setattr(HB, "_fund_source", lambda syms: (dict(dec), {}))
    e = _build(_frames(), NOW_NIGHT)
    assert e["fundamentals"]["state"] == "ready" and e["fundamentals"]["n"] == 1
    for s in ("BBB", "CCC", "DDD"):
        f = e["rows"][s]["fund"]
        assert set(f) == set(HB.FUND_ROW_KEYS)
        assert all(v is None for v in f.values()), (s, f)          # never a 0, never False
    assert e["rows"]["AAA"]["fund"]["next_earnings"] is None        # no earnings row -> blank


def test_09c_the_hermetic_default_source_is_not_read():
    e = _build(_frames(), NOW_NIGHT)                                # the un-patched Hottest readers
    assert e["fundamentals"]["state"] == HB.FUND_NOT_READ
    assert all(r["fund"] is None for r in e["rows"].values())


def test_10_the_fund_memo_reads_once_per_ttl_and_again_for_a_new_name(monkeypatch):
    calls = []
    monkeypatch.setattr(HB, "_fund_source", lambda syms: calls.append(list(syms)) or FUND_SOURCE(syms))
    _build(_frames(), NOW_NIGHT)
    _build(_frames(), NOW_NIGHT)
    _build(_frames(), NOW_NIGHT)
    assert len(calls) == 1 and calls[0] == ["AAA", "BBB", "CCC", "DDD"]
    key = next(iter(HB._fund_memo))
    HB._fund_memo[key]["ts"] -= HB.FUND_TTL_SEC + 1
    _build(_frames(), NOW_NIGHT)
    assert len(calls) == 2                                          # stale -> re-read
    fr = _frames()
    fr["NEWX"] = _frame(2.7, move=-3.0)
    HB._base_memo.clear()
    e = _build(fr, NOW_NIGHT, universe=UNIVERSE + ["NEWX"])
    assert len(calls) == 3 and "NEWX" in calls[-1]                   # a newly listed name -> re-read
    assert e["rows"]["NEWX"]["fund"] == {k: None for k in HB.FUND_ROW_KEYS}
    # an older session's read is evicted when a newer one is stored
    HB._fund_memo[("2026-09-01", "full")] = {"ts": time.time(), "fund": {"rows": {}}}
    HB._fund_memo[key]["ts"] -= HB.FUND_TTL_SEC + 1
    _build(fr, NOW_NIGHT, universe=UNIVERSE + ["NEWX"])
    assert list(HB._fund_memo) == [key]


def test_10b_the_base_build_never_reads_fundamentals(monkeypatch):
    assert "fund" not in inspect.getsource(HB.build_base)
    assert "fund" not in inspect.getsource(HB.rate_one)

    def boom(syms):
        raise AssertionError("the base build reached the research cache")
    monkeypatch.setattr(HB, "_fund_source", boom)
    fr = _frames()
    base = HB._base_for(("2026-10-02", "full"), "full", FRI, universe_fn=lambda u: list(UNIVERSE),
                        frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr},
                        qqq_fn=lambda: ["AAA"], etf_fn=lambda: {"XLV"}, is_delisted=lambda s: False)
    assert "AAA" in base["rows"] and "fund" not in base["rows"]["AAA"]
    e = _build(fr, NOW_NIGHT)                                      # a raising source never breaks the build
    assert e["fundamentals"]["state"] == "not_read" and "AAA" in e["rows"]


# --------------------------------------------------------------------------
# 11 — source guards: Hottest's and the tracker's engines, no parallel formula
# --------------------------------------------------------------------------
def test_11_NEG_one_engine_per_number():
    for need in ("HOT._fundamentals_row", "HOT._decision_map", "HOT._earnings_map", "HOT._quality_info",
                 "HOT._sorter", "HOT._rank_names", "HOT._sort_value", "HOT._as_of_range",
                 "RT.trailing_return", "RT.traction_row", "RES.sigma_pct", "RES.closes_by_day"):
        assert need in SRC, need
    for banned in ("growth_yoy_pct", "npm_latest_pct", "q_eps_growth_pct", "TIER_RANK =", "MongoClient",
                   "decision_snapshot(", "pymongo"):
        assert banned not in SRC, banned
    import re
    assert not re.search(r"insert_|update_one|update_many|replace_one|delete_|bulk_write|"
                         r"create_index|\.drop\(|open\(", SRC)


# --------------------------------------------------------------------------
# 12 — wording + number tags
# --------------------------------------------------------------------------
def _clean_words(text: str) -> None:
    low = str(text).lower()
    for w in HB.FORBIDDEN_WORDS:
        assert w not in low, (w, text)


def test_12_every_served_line_carries_no_forbidden_word():
    counts = [None, {"sort_present": 3, "sort_missing": 2}, {"sort_present": 0, "sort_missing": 4},
              {"sort_present": 5, "sort_missing": 0}]
    for k in HB.HEADER_SORTS:
        for d in (None, "asc", "desc"):
            for c in counts:
                for rel in (None, "RSP", "SPY"):
                    line = HB.order_line(k, d, c, rel)
                    _clean_words(line)
                    assert line.startswith("Order: ")
    for through in ("prior_close", "session_close"):
        for mode in (HB.MODE_LIVE, HB.MODE_AFTER, HB.MODE_CLOSED):
            for rel in ("RSP", "SPY", None):
                legs = {"end": "2026-10-02", "mode": mode, "through": through, "rel": rel,
                        "rs": "SPY" if rel else None,
                        "SPY": {"ret_5d": -1.234, "ret_21d": 2.0, "ret_63d": 5.0},
                        "RSP": {"ret_5d": None if rel != "RSP" else 0.5, "ret_21d": 1.0, "ret_63d": 3.0}}
                _clean_words(HB.returns_line(legs))
    assert HB.returns_line(None) is None and HB.returns_line({}) is None
    for e in ({"fundamentals": {"state": "ready", "n": 3, "of": 5, "n_earnings": 2,
                                "as_of": {"oldest": "2026-10-01", "newest": "2026-10-02", "n": 3}}},
              {"fundamentals": {"state": "not_read", "reason": "x"}}, {}):
        blk = HB.fundamentals_block(e)
        _clean_words(blk["line"])
        _clean_words(blk["note"])
    for cols in (HB.table_block()["columns"], HB.table_block()["sales_columns"]):
        for c in cols:
            _clean_words(c["label"])
            _clean_words(c["title"] or "")
    assert "UNMEASURED" in HB.FUND_NOTE and "Not advice" in HB.FUND_NOTE
    assert "UNMEASURED" in HB.COLUMN_TITLES["rs_spy_63d"]


def test_12b_the_presets_keep_their_old_lines_verbatim():
    assert HB.order_line(HB.SORT_DROP) == HB.order_line(HB.SORT_DROP, "asc", {"sort_missing": 9}) == (
        "Order: today's drop, deepest first; names up or flat follow (smallest move first); names with "
        "no read last.")
    assert HB.order_line("default") == HB.order_line(HB.SORT_SWING, "desc") == (
        "Order: β × today's drop, largest first, over the red names; names up or flat today follow "
        "(smallest move first); names with no read last.")
    assert HB.order_line(HB.SORT_VOL, None).startswith("Order: most volatile first — σ")
    assert HB.order_line(HB.SORT_DROP, "desc") == "Order: today's move, highest first."
    assert HB.order_line(HB.SORT_VOL, "asc") == "Order: σ (50d), least volatile first."
    assert HB.order_line(HB.SORT_NEXT_ER, None, {"sort_present": 3, "sort_missing": 2}) == \
        "Order: the next earnings date, soonest first. 2 with no value sit last."
    assert HB.order_line(HB.SORT_REL_5D, "asc", None, "SPY") == "Order: the 5-day move vs SPY, lowest first."
    assert HB.order_line(HB.SORT_SYMBOL, "desc") == "Order: the ticker, Z→A."
    assert HB.order_line(HB.SORT_SWING, "asc") == "Order: β × today's drop, smallest first over the red names."


def test_12c_his_numbers_and_mine_are_tagged():
    lines = SRC.splitlines()

    def line_of(prefix):
        return next(l for l in lines if l.startswith(prefix))
    for name in ("LEG_FAST = ", "LEG_SHORT = ", "RS_WINDOW = ", "RS_BENCH = "):
        assert "# Ajay 2026-10-14" in line_of(name), name
    for name in ("FUND_TTL_SEC = ", "LEG_TEXT_DP = "):
        assert "# MINE" in line_of(name), name
    assert HB.LEG_TEXT_DP == 1 and HB.FUND_TTL_SEC == HB.BASE_TTL_SEC
    doc = " ".join(HB.__doc__.split())
    assert "2026-10-14 b" in doc and "Can you add sort function on the headers and also 5 day" in doc


# --------------------------------------------------------------------------
# 13 — the memo is read-only, NaN is missing, the served table, cell text precision
# --------------------------------------------------------------------------
def test_13_NEG_rank_and_compact_row_never_mutate_the_memo_rows(monkeypatch):
    monkeypatch.setattr(HB, "_fund_source", FUND_SOURCE)
    e = _build(_frames(), NOW_NIGHT)
    before = repr(e["rows"])
    snap = copy.deepcopy(e["rows"])
    for k in HB.HEADER_SORTS:
        for d in ("asc", "desc", None):
            rows, _c, _f = HB.rank(e, sort=k, direction=d, include_green=True)
            for r in rows:
                c = HB.compact_row(r, qqq_available=True)
                if c["fund"]:
                    c["fund"]["sales_yoy"] = -999.0
                c["text"]["ret_5d"] = "x"
    assert repr(e["rows"]) == before and e["rows"] == snap
    assert isinstance(e["rows"], dict)


def test_13b_NEG_a_planted_nan_sorts_as_missing():
    e = _entry(_r("A", 2.0, -1.0), _r("B", 2.0, -2.0), _r("C", 2.0, -3.0))
    e["rows"]["A"]["ret_5d"], e["rows"]["B"]["ret_5d"], e["rows"]["C"]["ret_5d"] = float("nan"), 1.0, 2.0
    e["rows"]["A"]["today"]["prev_close"] = 50.0
    for d, want in (("desc", ["C", "B", "A"]), ("asc", ["B", "C", "A"])):
        assert [r["symbol"] for r in HB.rank(e, sort=HB.SORT_RET_5D, direction=d,
                                             include_green=True)[0]] == want
    assert HB.compact_row(e["rows"]["A"], qqq_available=True)["text"]["ret_5d"] == "—"


def test_13c_table_block_columns_follow_header_sorts_and_carry_the_views():
    tb = HB.table_block()
    for cols, spec in ((tb["columns"], HB.TABLE_COLUMNS), (tb["sales_columns"], HB.SALES_COLUMNS)):
        assert [c["key"] for c in cols] == [k for k, _l in spec]
        for c in cols:
            assert set(c) == {"key", "label", "title", "sort", "first"}
            assert c["sort"] == HB.COLUMN_SORT[c["key"]]
            assert c["first"] == HB.HEADER_SORTS[c["sort"]][1]
    by = {c["key"]: c for c in tb["columns"] + tb["sales_columns"]}
    assert by["levered"]["sort"] == HB.SORT_LEVERED and by["levered"]["first"] == "desc"       # B3
    assert by["today"]["sort"] == HB.SORT_DROP and by["today"]["first"] == "asc"
    assert by["swing"]["sort"] == HB.SORT_SWING and by["sigma"]["sort"] == HB.SORT_VOL
    assert [by[k]["label"] for k in ("ret_5d", "rel_5d", "ret_21d", "rel_21d")] == \
        ["5 days", "5 days vs RSP", "21 days", "21 days vs RSP"]
    assert [c["label"] for c in tb["sales_columns"][3:]] == \
        ["Sales YoY", "Sales trend", "Q EPS", "Margin", "Quality", "Next ER", "RS vs SPY (63d)"]
    assert by["sales_tier"]["title"] == "ranks explosive › strong › steady › weak › declining"
    assert by["eq_score"]["title"] == "Minervini Ch.8 earnings quality · 🎯 Code 33 · ⚠️ inventory vs sales"
    assert by["next_earnings"]["title"] == "ascending = who reports soonest"
    assert tb["views"] == [{"key": "price", "label": "Price"}, {"key": "sales", "label": "Sales"}]
    assert tb["view_param"] == "hb_view" and tb["cat_labels"] == HB.CAT_SHORT
    assert HB.table_block({"rel": None})["columns"][4]["label"] == "5 days vs RSP"


def test_13d_cell_text_is_one_dp_and_the_numbers_stay_two_dp_B8():
    r = _r("A", 2.0, -3.0)
    r["today"]["prev_close"] = 50.0
    r.update(ret_5d=12.34, ret_21d=-0.06, rel_5d=4.15, rel_21d=None, rs_spy_63d=-7.25)
    c = HB.compact_row(r, qqq_available=True)
    assert c["ret_5d"] == 12.34 and c["rs_spy_63d"] == -7.25                  # the sort numbers, unchanged
    assert c["text"]["ret_5d"] == "+12.3%" and c["text"]["ret_21d"] == "−0.1%"
    assert c["text"]["rel_5d"] == "+4.2 pp"                                    # 4.15 sits above the binary tie
    assert c["text"]["rel_21d"] == "—" and c["text"]["rs_spy_63d"] == "−7.3 pp"   # −7.25: HALF_UP like JS toFixed (not Python's −7.2)
    assert c["fund"] is None
    assert math.isclose(float(c["text"]["ret_5d"][1:-1]), 12.3)


def test_13e_envelopes_serve_dir_preset_returns_and_fundamentals(monkeypatch):
    monkeypatch.setattr(HB, "_fund_source", FUND_SOURCE)
    e = _build(_frames(), NOW_NIGHT)
    rows, counts, filters = HB.rank(e, sort=HB.SORT_RET_5D, direction="asc", include_green=True)
    b = HB.ready_block(counts, entry=e, sort=HB.SORT_RET_5D, min_tier_label="no floor", filters=filters,
                       include_green=True, direction="asc")
    assert b["sort"] == HB.SORT_RET_5D and b["sort_dir"] == "asc" and b["sort_preset"] is None
    assert b["order_line"] == "Order: the 5-day move, lowest first."
    assert b["returns_line"] == HB.returns_line(e["legs"]) and b["fundamentals"]["state"] == "ready"
    assert b["table"]["columns"][4]["label"] == "5 days vs RSP"
    vals = [r["ret_5d"] for r in rows]
    assert vals == sorted(vals)
    b = HB.ready_block(counts, entry=e, sort="default", min_tier_label="no floor", filters=filters)
    assert b["sort_dir"] == "desc" and b["sort_preset"] == HB.SORT_SWING
    for blk in (HB.warming_block(now=NOW_NIGHT, sort=HB.SORT_DROP, direction="DESC"),
                HB.error_block("boom", now=NOW_NIGHT, sort=HB.SORT_DROP, direction="desc")):
        assert blk["sort_dir"] == "desc" and blk["sort_preset"] is None
        assert blk["returns_line"] is None and blk["fundamentals"] is None and blk["table"] is None
        assert blk["order_line"] == "Order: today's move, highest first."
    w = HB.warming_block(now=NOW_NIGHT, sort="junk", direction="junk")
    assert w["sort"] == HB.SORT_SWING and w["sort_dir"] == "desc" and w["sort_preset"] == HB.SORT_SWING


def test_13f_the_wording_guard_still_covers_the_module():
    words = _strings(BACKEND / "chart_maps" / "high_beta_tab.py", skip_assign="FORBIDDEN_WORDS")
    for w in HB.FORBIDDEN_WORDS:
        assert w not in words, w


def test_99_leg_text_rounds_like_hottest_toFixed():
    """JS (1.25).toFixed(1) == "1.3", (-0.25).toFixed(1) == "-0.3", (1.15).toFixed(1) == "1.1"
    (binary 1.15 sits below the tie). Python's f-format gives "1.2" / "-0.2" / "1.1"."""
    assert HB.leg_text(1.25) == "+1.3%" and HB.leg_text(-0.25) == "\u22120.3%"    # the house typographic minus
    assert HB.leg_text(1.15) == "+1.1%" and HB.leg_text(0.0) == "+0.0%"
    assert HB.pp_text(2.75) == "+2.8 pp" and HB.pp_text(-0.04) == "+0.0 pp"      # never "−0.0"
    assert HB.leg_text(None) == "—" and HB.pp_text(float("nan")) == "—"            # NEGATIVE: unread stays a dash
