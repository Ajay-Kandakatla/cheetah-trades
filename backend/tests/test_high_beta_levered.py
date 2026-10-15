"""🔗 Leveraged-ETF tags on the 🎢 High Beta rows and cards
(chart_maps/high_beta_tab.py ⟵ sepa/levered_etf.py, 2026-10-14).

Ajay 2026-10-14, verbatim: "Can you add a short tag on these stocks for their
Leverage equivalents like IRE for IREN, VSTL for VST".

The map is the REAL 10-14 reference fixture (tests/fixtures/
levered_etf_reference_2026_10_14.json) read through LE.load over a Mongo
double; the board is the High Beta test board (tests/test_high_beta_tab.py
stubs). The FE fixture frontend/src/components/__fixtures__/
high_beta_levered_2026_10_14.json is dumped from these REAL functions and
pinned equal here (rebuild: LEVERED_FE_FIXTURE_WRITE=1).
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from chart_maps import board as BOARD
from chart_maps import high_beta_tab as HB
from chart_maps import membership as MEM
from sepa import levered_etf as LE

from tests.test_high_beta_tab import (NOW_NIGHT, _FakeDB, _bench, _frame, _patch_build,  # noqa: E402
                                _stub_board)
from tests.test_levered_etf import _Coll, _DB, _built, _doc  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
FE_FIXTURE = (BACKEND.parent / "frontend" / "src" / "components" / "__fixtures__"
              / "high_beta_levered_2026_10_14.json")
UNIVERSE = ["IREN", "NBIS", "VST", "AAA"]


def _frames():
    """IREN β3.8 −7%, NBIS β3.5 −6%, VST β1.52 −2% (his VSTL example), AAA β2.0
    −5% (no leveraged fund on file)."""
    f = {"IREN": _frame(3.8, move=-7.0), "NBIS": _frame(3.5, move=-6.0),
         "VST": _frame(1.52, move=-2.0), "AAA": _frame(2.0, move=-5.0)}
    f.update(_bench())
    return f


def _lev_state():
    """The map as LE.load serves it: the fixture doc, as of the board's own
    night (age 0)."""
    db = _DB(_Coll(_doc(as_of="2026-10-05", grouped_day="2026-10-02")))
    return LE.load(now=NOW_NIGHT, db=db, ensure=False)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for m in (HB._memo, HB._base_memo, HB._failures):
        m.clear()
    HB._warming.clear()
    LE._reset_for_tests()
    spawned = []
    monkeypatch.setattr(HB, "_spawn", lambda target, name: spawned.append((target, name)))
    monkeypatch.setattr(LE, "_spawn", lambda target, name: spawned.append((target, name)))
    yield spawned
    LE._reset_for_tests()


def _entry(levered_fn):
    fr = _frames()
    return HB.build("full", NOW_NIGHT, universe_fn=lambda u: list(UNIVERSE),
                    frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr},
                    qqq_fn=lambda: ["NBIS"], etf_fn=lambda: {"SPY", "RSP", "QQQ"},
                    is_delisted=lambda s: False, snap_fn=lambda syms: {}, levered_fn=levered_fn)


@pytest.fixture
def lev_board(monkeypatch):
    state = {"snap_calls": [], "db": _FakeDB()}
    lev = _lev_state()
    calls = []
    monkeypatch.setattr(LE, "load", lambda **k: calls.append(k) or lev)
    _patch_build(monkeypatch, _frames(), universe=UNIVERSE, qqq=("NBIS",))
    _stub_board(monkeypatch, state)
    monkeypatch.setattr(MEM, "_db", lambda db=None: state["db"])
    HB.cached_or_warm("full", now=NOW_NIGHT, sync=True)
    state["load_calls"] = calls
    state["lev"] = lev
    return state


# --------------------------------------------------------------------------
# 1 — the rows, the tiles, the table, the board line
# --------------------------------------------------------------------------
def test_01_build_live_tags_iren_vst_nbis_and_not_the_name_with_no_fund():
    lev = _lev_state()
    e = _entry(lambda **k: lev)
    r = e["rows"]["IREN"]
    assert [x["etf"] for x in r["levered"]] == ["IRE", "IREX", "IREG", "IREZ"]
    assert r["levered"][0] == {"etf": "IRE", "factor": 2.0, "direction": "long"}
    assert r["levered_chip"]["text"] == "\U0001F517 2× IRE · IREX · IREG +1"
    assert e["rows"]["VST"]["levered_chip"]["text"] == "\U0001F517 2× VSTL"
    assert e["rows"]["NBIS"]["levered_chip"]["text"] == "\U0001F517 2× NBIL · NBIG · NEBX +1"
    assert e["rows"]["AAA"]["levered"] == [] and e["rows"]["AAA"]["levered_chip"] is None
    blk = e["levered"]
    assert blk["state"] == "ready" and blk["n_on"] == 3 and blk["n_etfs"] == 31
    assert blk["line"].startswith("\U0001F517 Leveraged-ETF tags: 3 of these 4 names")
    assert HB.TABLE_COLUMNS[1] == ("levered", LE.STAT_KEY)


def test_02_the_card_badge_stat_and_the_table_reach_the_payload(lev_board):
    out = BOARD.board(tab="high_beta", limit=24, hb_all=True, min_tier="any")
    tiles = {t["symbol"]: t for t in out["tiles"]}
    t = tiles["IREN"]
    assert t["badges"][0]["text"].startswith("\U0001F3A2 β 3.80")
    assert t["badges"][1] == {"text": "\U0001F517 2× IRE · IREX · IREG +1", "tone": "muted", "levered": True}
    assert t["badges"][2]["text"].startswith("\U0001F4C5 last session")                # the today pill follows
    stats = {s["k"]: s["v"] for s in t["stats"]}
    assert stats[LE.STAT_KEY] == "IRE 2× · IREX 2× · IREG 2× · IREZ −2×"
    assert t["high_beta"]["levered_chip"]["text"] == t["badges"][1]["text"]
    assert [x["etf"] for x in t["high_beta"]["levered"]] == ["IRE", "IREX", "IREG", "IREZ"]
    rows = {r["symbol"]: r for r in out["rows"]}
    assert rows["VST"]["levered_chip"]["text"] == "\U0001F517 2× VSTL"
    b = out["high_beta_board"]
    assert b["table"]["columns"][1] == {"key": "levered", "label": LE.STAT_KEY}
    assert b["levered"]["state"] == "ready" and b["levered"]["n_on"] == 3 and b["levered"]["legend"]
    # compact_row.text reads the stats BY KEY: the appended stat changes no cell
    assert set(rows["IREN"]["text"]) == {"beta", "today", "swing", "sigma"}


def test_03_NEG_a_name_with_no_fund_has_no_badge_no_stat_no_chip(lev_board):
    out = BOARD.board(tab="high_beta", limit=24, hb_all=True, min_tier="any")
    t = next(t for t in out["tiles"] if t["symbol"] == "AAA")
    assert not any(b.get("levered") for b in t["badges"])
    assert LE.STAT_KEY not in {s["k"] for s in t["stats"]}
    assert t["high_beta"]["levered"] == [] and t["high_beta"]["levered_chip"] is None
    r = next(r for r in out["rows"] if r["symbol"] == "AAA")
    assert r["levered"] == [] and r["levered_chip"] is None


# --------------------------------------------------------------------------
# 2 — negatives: a broken or stale map never breaks the board
# --------------------------------------------------------------------------
def test_04_NEG_a_raising_map_builds_the_board_with_no_tag():
    def boom(**k):
        raise RuntimeError("mongo down")
    e = _entry(boom)
    assert all(r["levered"] == [] and r["levered_chip"] is None for r in e["rows"].values())
    assert e["levered"]["state"] == "error" and "mongo down" in e["levered"]["line"]
    assert e["levered"]["n_on"] == 0 and e["levered"]["legend"] is None
    e = _entry(lambda **k: "junk")
    assert e["levered"]["state"] == "error"


def test_05_NEG_a_stale_map_hides_every_tag_and_says_so():
    db = _DB(_Coll(_doc(as_of="2026-09-20")))
    stale = LE.load(now=NOW_NIGHT, db=db, ensure=False)
    assert stale["state"] == "stale"
    e = _entry(lambda **k: stale)
    for r in e["rows"].values():
        assert r["levered"] == [] and r["levered_chip"] is None
        assert not any(b.get("levered") for b in HB.tile_badges(r))
        assert LE.STAT_KEY not in {s["k"] for s in HB.tile_stats(r)}
    assert "hidden" in e["levered"]["line"]


def test_06_NEG_the_tag_never_changes_the_order_the_filters_or_the_watch_list(monkeypatch, _clean):
    lev = _lev_state()
    with_map = _entry(lambda **k: lev)
    HB._base_memo.clear()
    without = _entry(lambda **k: {"state": "missing", "reason": "not read yet"})
    for sort in HB.TAB_SORTS:
        for act in ((), ("b20",), ("qqq", "d5")):
            a, ca, fa = HB.rank(with_map, sort=sort, active=act, include_green=True)
            b, cb, fb = HB.rank(without, sort=sort, active=act, include_green=True)
            assert [r["symbol"] for r in a] == [r["symbol"] for r in b]
            assert ca == cb and fa == fb
    assert with_map["counts"] == without["counts"]


def test_07_NEG_the_memo_rows_are_never_mutated_and_the_map_is_read_once_per_build(lev_board):
    key = (HB.MODE_CLOSED, "2026-10-02", "full")
    before = copy.deepcopy(HB._memo[key]["rows"])
    out = BOARD.board(tab="high_beta", limit=24, hb_all=True, min_tier="any")
    for t in out["tiles"]:
        if t["high_beta"]["levered_chip"]:
            t["high_beta"]["levered_chip"]["parts"].clear()
            t["high_beta"]["levered"].clear()
    for r in out["rows"]:
        if r["levered_chip"]:
            r["levered_chip"]["text"] = "x"
    assert HB._memo[key]["rows"] == before
    assert len(lev_board["load_calls"]) == 1                     # the build read it; the request did not
    assert all(set(c) == {"now"} for c in lev_board["load_calls"])  # read-only call: no db, no write path


def test_08_NEG_the_request_path_never_reaches_massive(lev_board, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the request path called Massive")
    for name in ("fetch_reference", "fetch_grouped", "refresh", "ensure_async"):
        monkeypatch.setattr(LE, name, boom)
    out = BOARD.board(tab="high_beta", limit=24, hb_all=True, min_tier="any")
    assert out["high_beta_board"]["levered"]["state"] == "ready"
    w = BOARD.high_beta_watch()
    assert w["state"] == "ready"


def test_09_NEG_the_hermetic_default_map_is_missing_and_starts_no_refresh(_clean):
    e = _entry(None)                                             # the real LE.load under the conftest stub
    assert e["levered"]["state"] == "missing"
    assert all(r["levered"] == [] for r in e["rows"].values())
    assert not any(n.startswith("levered-etf") for _t, n in _clean)


# --------------------------------------------------------------------------
# 3 — the FE fixture is a REAL payload
# --------------------------------------------------------------------------
def _fe_payload(out: dict) -> dict:
    b = out["high_beta_board"]
    keep = {k: v for k, v in b.items() if k not in ("built_at", "base_built_at")}
    tiles = [{"symbol": t["symbol"], "badges": t["badges"], "stats": t["stats"],
              "high_beta": {"levered": t["high_beta"]["levered"],
                            "levered_chip": t["high_beta"]["levered_chip"]}} for t in out["tiles"]]
    return json.loads(json.dumps({"source": "tests/test_high_beta_levered.py::_fe_payload (real functions over "
                                            "tests/fixtures/levered_etf_reference_2026_10_14.json)",
                                  "high_beta_board": keep, "rows": out["rows"], "tiles": tiles},
                                 ensure_ascii=False, default=str))


def test_10_the_fe_fixture_equals_the_rebuilt_payload(lev_board):
    got = _fe_payload(BOARD.board(tab="high_beta", limit=24, hb_all=True, min_tier="any"))
    if os.environ.get("LEVERED_FE_FIXTURE_WRITE") == "1":
        FE_FIXTURE.write_text(json.dumps(got, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                              encoding="utf-8")
    want = json.loads(FE_FIXTURE.read_text(encoding="utf-8"))
    assert got == want
    assert {r["symbol"] for r in got["rows"]} == set(UNIVERSE)
    assert "IR" + "NX" not in FE_FIXTURE.read_text(encoding="utf-8")
