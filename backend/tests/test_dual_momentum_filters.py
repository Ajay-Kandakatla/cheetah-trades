"""🏎️ Dual Momentum tab — 🌀 AMD raided · 📍 near demand · 🔑 near a lower key
level filters (2026-09-29) — spec WP-BE tests T1-T18.

Ajay 2026-09-29: "Can you add AMD raided and near demand zone and near lower
Key level filters to dual momentum please".

Pins the pure filter reads in `chart_maps/dual_momentum_tab.py`, the builder
wiring in `chart_maps/board.py` (every read over the WHOLE pool, BEFORE the
order and the cut; per-box counts; the served line; the empty note), the
`dm` param in `chart_maps/api.py`, and that nothing outside the tab reads the
filter. Positive AND negative cases. Stubs only — the conftest refuses Mongo;
the `dm_board` fixture stubs the three new reads by default.
"""
from __future__ import annotations

import asyncio
import inspect
import itertools
import json
import os
import re
from pathlib import Path

import pytest

from chart_maps import board as B
from chart_maps import dual_momentum_tab as DMT
from chart_maps import key_levels_tab as KLT
from rotation import hottest_amd as HA
from supply_demand import alert_gates as AG
from supply_demand import turning_bullish as TB
from tests.test_dual_momentum_tab import (NOW, _clean_memo, _doc, _pick, _snap,  # noqa: F401
                                          _std, _strings, dm_board, scan_file)
from tests.test_hottest_amd import _doc as _amd_doc
from tests.test_hottest_amd import _verdict
from tests.test_key_levels_tab import _frame, _rth

BACKEND = Path(__file__).resolve().parents[1]
ALL = ("amd", "zone", "level")


def _near(d, label="PWL"):
    return {"label": label, "price": 100.0, "distance_pct": d, "text": f"{label} {d}"}


def _known(grade):
    return HA.read_one("X", _verdict(grade))


def _syms(out):
    return [t["symbol"] for t in out["tiles"]]


def _items(out):
    return {i["key"]: i for i in out["dual_momentum_board"]["filters"]["items"]}


# --------------------------------------------------------------------------
# T1 — parse_filters
# --------------------------------------------------------------------------
def test_T1_parse_filters_canonical_order_case_space_plus_dedupe():
    assert DMT.parse_filters("level,AMD, foo") == ("amd", "level")
    assert DMT.parse_filters(" Zone + amd ") == ("amd", "zone")
    assert DMT.parse_filters("level,level,zone,amd,amd") == ALL
    assert DMT.parse_filters("amd,foo") == ("amd",)
    assert DMT.FILTER_KEYS == ALL


@pytest.mark.parametrize("bad", [None, "", "   ", 123, ["amd"], "foo", "foo,bar", ",,+"])
def test_T1_NEG_junk_parses_to_nothing(bad):
    assert DMT.parse_filters(bad) == ()


# --------------------------------------------------------------------------
# T2 — the 🌀 cell -> pass / fail / not read
# --------------------------------------------------------------------------
def test_T2_amd_raided_passes_every_other_grade_fails():
    tf = DMT.tile_filter(_known(TB.AMD_TURNING), None, None)
    assert tf["amd"] is True and tf["amd_grade"] == TB.AMD_TURNING and tf["amd_reason"] is None
    assert DMT.passes(tf, ("amd",)) is True
    assert DMT.AMD_RAIDED == TB.AMD_TURNING
    others = [g for g in TB.AMD_GRADES if g != TB.AMD_TURNING]
    assert others
    for g in others:
        cell = _known(g)
        assert cell["known"] is True, g
        tf = DMT.tile_filter(cell, None, None)
        assert tf["amd"] is False and tf["amd_grade"] == g, g
        assert DMT.passes(tf, ("amd",)) is False, g


@pytest.mark.parametrize("cell", [HA.blank("not_in_store"), HA.blank("no_verdict"),
                                  HA.blank("store_unavailable"), None, "junk"])
def test_T2_NEG_an_unread_cell_is_none_and_never_passes(cell):
    tf = DMT.tile_filter(cell, None, None)
    assert tf["amd"] is None and tf["amd_grade"] is None
    if isinstance(cell, dict):
        assert tf["amd_reason"] == cell["reason"]
    assert DMT.passes(tf, ("amd",)) is False


def test_T2_NEG_passes_needs_True_never_truthiness():
    assert DMT.passes({"amd": 1}, ("amd",)) is False
    assert DMT.passes({"amd": "raided"}, ("amd",)) is False
    assert DMT.passes({"amd": True, "zone": None}, ("amd", "zone")) is False
    assert DMT.passes({"amd": True, "zone": False}, ("amd",)) is True     # unticked box ignored
    assert DMT.passes({}, ()) is True and DMT.passes(None, ()) is True
    assert DMT.passes(None, ("amd",)) is False


# --------------------------------------------------------------------------
# T3 — amd_reads is hottest_amd.attach
# --------------------------------------------------------------------------
def test_T3_amd_reads_are_the_attach_cells_rename_aware():
    from sepa import symbols as SY
    old, (new, _eff, _why) = next(iter(SY.RENAMES.items()))
    rows = {old: _verdict("raided"), "BBB": _verdict("basing"), "CCC": _verdict("raided")}
    doc = _amd_doc(rows)
    syms = [new, "BBB", "CCC", "ZZZ"]
    cells, summary = DMT.amd_reads(syms, doc=doc, now=NOW)
    body = {"themes": [{"names": [{"symbol": s} for s in syms]}]}
    HA.attach(body, doc=doc, now=NOW)
    assert cells == {r["symbol"]: r[HA.ROW_KEY] for r in body["themes"][0]["names"]}
    assert summary["available"] is True
    assert cells[new]["known"] is True and cells[new]["grade"] == TB.AMD_TURNING
    assert DMT.tile_filter(cells[new], None, None)["amd"] is True
    assert DMT.tile_filter(cells["BBB"], None, None)["amd"] is False
    # NEGATIVE: a symbol absent from the sweep -> not_in_store, never raided
    assert cells["ZZZ"]["known"] is False and cells["ZZZ"]["reason"] == "not_in_store"
    assert DMT.tile_filter(cells["ZZZ"], None, None)["amd"] is None


def test_T3_NEG_an_unreadable_sweep_blanks_every_cell():
    cells, summary = DMT.amd_reads(["AAA", "BBB"], doc={}, now=NOW)
    assert summary["available"] is False
    assert {c["reason"] for c in cells.values()} == {"store_unavailable"}
    assert all(DMT.tile_filter(c, None, None)["amd"] is None for c in cells.values())
    assert "could not be read" in DMT.amd_note(summary)


# --------------------------------------------------------------------------
# T4 — 📍 boundary through the REAL builder
# --------------------------------------------------------------------------
def test_T4_zone_boundary_is_the_gate_proximity(dm_board):
    picks = [_pick("EDG", 1), _pick("OUT", 2), _pick("INB", 3), _pick("NOD", 4)]
    docs = {s: _doc([(98.0, 99.0)], [(130.0, 131.0)], floor="intact")
            for s in ("EDG", "OUT", "INB")}
    snaps = {"EDG": _snap(99.99), "OUT": _snap(99.9999), "INB": _snap(98.5), "NOD": _snap(99.5)}
    dm_board["seed"](picks, docs, snaps)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any", dm="zone")
    by = {t["symbol"]: t for t in out["tiles"]}
    assert set(by) == {"EDG", "INB"}                        # 1.00% above + in band
    assert by["EDG"]["dm_filter"]["zone"] is True
    assert by["INB"]["dm_filter"]["zone"] is True
    full = {t["symbol"]: t for t in B.board(tab="dual_momentum", limit=80,
                                             min_tier="any")["tiles"]}
    # NEGATIVE: 1.01% above -> False, hidden, counted as a fail
    assert full["OUT"]["dm_filter"]["zone"] is False
    assert full["OUT"]["dm_zone"]["gate"]["prox_ok"] is False
    # NEGATIVE: no stored bands -> not read, hidden, counted no_read
    assert full["NOD"]["dm_filter"]["zone"] is None
    it = _items(out)["zone"]
    assert (it["pass"], it["fail"], it["no_read"], it["hidden"]) == (2, 1, 1, 2)
    f = out["dual_momentum_board"]["filters"]
    assert f["near_demand_pct"] == AG.ALERT_MAX_ABOVE_DEMAND_PCT == DMT.near_demand_pct()
    # the read is the tile's own gate copy, zero new calls
    for t in full.values():
        g = (t["dm_zone"].get("gate") or {}).get("prox_ok")
        assert t["dm_filter"]["zone"] is (g if isinstance(g, bool) else None)


# --------------------------------------------------------------------------
# T5 — 🔑 with the REAL key-level engine
# --------------------------------------------------------------------------
def _kl_setup():
    frames = {"NER": _frame(), "FAR": _frame(), "BUF": _frame(), "BRK": _frame(),
              "NOP": _frame(), "OLD": _frame(end="2026-09-22")}
    snaps = {"NER": _rth(100.9), "FAR": _rth(101.2), "BUF": _rth(99.9), "BRK": _rth(96.0),
             "OLD": _rth(100.5)}

    def build_fn(universe, session, *, universe_fn):
        return KLT.build(universe, session, universe_fn=universe_fn,
                         frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames})
    return frames, snaps, build_fn


def test_T5_key_level_reads_real_engine_and_parity_with_the_tab():
    frames, snaps, build_fn = _kl_setup()
    syms = list(frames)
    reads, err = DMT.key_level_reads(syms, snaps, now=NOW, first_seen={}, build_fn=build_fn)
    assert err is None
    tfs = {s: DMT.tile_filter(None, None, reads[s]) for s in syms}
    assert reads["NER"]["status"] == "ranked"
    assert round(reads["NER"]["near"]["distance_pct"], 2) == 0.89 and tfs["NER"]["level"] is True
    # NEGATIVE: 1.19% away -> False
    assert round(reads["FAR"]["near"]["distance_pct"], 2) == 1.19 and tfs["FAR"]["level"] is False
    # inside the break buffer, not through -> ranked, negative distance, passes
    assert reads["BUF"]["status"] == "ranked" and reads["BUF"]["near"]["distance_pct"] < 0
    assert tfs["BUF"]["level"] is True
    # NEGATIVE: through every lower level -> broken (the tab's own count) -> False
    entry = build_fn("full", KLT.session_for(NOW), universe_fn=lambda _u: syms)
    _, c = KLT.rank({**entry, "syms": ["BRK"]}, snaps, now=NOW, first_seen={})
    assert c["broken"] == 1
    assert reads["BRK"]["status"] == "broken" and tfs["BRK"]["level"] is False
    assert DMT.passes(tfs["BRK"], ("level",)) is False
    # NEGATIVE: no snapshot row -> no_print -> None; bars behind -> stale -> None
    assert reads["NOP"]["status"] == "no_print" and tfs["NOP"]["level"] is None
    assert reads["OLD"]["status"] == "stale" and tfs["OLD"]["level"] is None
    assert tfs["NOP"]["level_near"] is None
    # parity: the Key Levels tab's own key_level_near for the SAME name
    ranked, _ = KLT.rank(entry, snaps, now=NOW, first_seen={})
    tab = {r["symbol"]: r["near"] for r in ranked}
    assert set(tab) == {"NER", "FAR", "BUF"}
    for s in tab:
        assert tfs[s]["level_near"] == tab[s] == reads[s]["near"]
    # never mutates the entry it ranks against
    assert entry["syms"] == syms


def test_T5_level_cut_is_inclusive_at_exactly_the_constant():
    k = DMT.KEY_LEVEL_NEAR_PCT
    ok = DMT.tile_filter(None, None, {"status": "ranked", "near": _near(k)})
    neg = DMT.tile_filter(None, None, {"status": "ranked", "near": _near(-k)})
    over = DMT.tile_filter(None, None, {"status": "ranked", "near": _near(k + 1e-9)})
    assert ok["level"] is True and neg["level"] is True
    assert over["level"] is False                                       # NEGATIVE
    # NEGATIVE: garbage distance / unknown status / no read -> None, never True
    assert DMT.tile_filter(None, None, {"status": "ranked",
                                        "near": _near(float("nan"))})["level"] is None
    assert DMT.tile_filter(None, None, {"status": "weird", "near": _near(0.1)})["level"] is None
    assert DMT.tile_filter(None, None, None)["level_status"] == DMT.LEVEL_UNREAD
    assert DMT.tile_filter(None, None, {"status": "no_level"})["level"] is False


def test_T5_NEG_a_raising_build_leaves_every_name_unread():
    def boom(*a, **k):
        raise RuntimeError("price cache down")
    reads, err = DMT.key_level_reads(["AAA", "BBB"], {}, now=NOW, first_seen={}, build_fn=boom)
    assert err == "price cache down"
    assert {r["status"] for r in reads.values()} == {DMT.LEVEL_UNREAD}
    assert all(DMT.tile_filter(None, None, r)["level"] is None for r in reads.values())
    note = DMT.level_note(err)
    assert "failed" in note and "price cache down" in note and "hides every leader" in note
    assert "failed" not in DMT.level_note(None)


# --------------------------------------------------------------------------
# the six-leader AND fixture
# --------------------------------------------------------------------------
def _six(dm_board):
    """amd True A,B,C · False D · None E,F
       zone True A,C,D · False B · None E,F
       level True A,B · False C,D · None E,F"""
    picks = [_pick(s, i + 1) for i, s in enumerate(("AAA", "BBB", "CCC", "DDD", "EEE", "FFF"))]
    near = _doc([(98.0, 99.0)], [(130.0, 131.0)], floor="intact")
    far = _doc([(90.0, 92.0)], [(130.0, 131.0)], floor="intact")
    docs = {"AAA": near, "BBB": far, "CCC": near, "DDD": near}
    snaps = {p["symbol"]: _snap(98.5) for p in picks}
    dm_board["seed"](picks, docs, snaps)
    dm_board["amd_cells"] = {"AAA": _known("raided"), "BBB": _known("raided"),
                             "CCC": _known("raided"), "DDD": _known("basing"),
                             "EEE": HA.blank("not_in_store")}
    dm_board["amd_summary"] = {"available": True, "built_at_et": "2026-09-28T17:32:00-04:00",
                               "stale": False}
    dm_board["level_reads"] = {
        "AAA": {"status": "ranked", "near": _near(0.5)},
        "BBB": {"status": "ranked", "near": _near(-0.1)},
        "CCC": {"status": "ranked", "near": _near(2.0)},
        "DDD": {"status": "broken", "near": None},
        "EEE": {"status": "no_print", "near": None}}
    return picks


def test_T6_AND_every_box_alone_and_together(dm_board):
    _six(dm_board)
    want = {"": ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"],
            "amd": ["AAA", "BBB", "CCC"], "zone": ["AAA", "CCC", "DDD"],
            "level": ["AAA", "BBB"], "amd,level": ["AAA", "BBB"],
            "amd,zone": ["AAA", "CCC"], "zone,level": ["AAA"], "amd,zone,level": ["AAA"]}
    counts = None
    for spec, syms in want.items():
        out = B.board(tab="dual_momentum", limit=80, min_tier="any", dm=spec)
        assert _syms(out) == syms, spec
        f = out["dual_momentum_board"]["filters"]
        got = {k: (i["pass"], i["fail"], i["no_read"]) for k, i in _items(out).items()}
        # the per-box counts are over the WHOLE pool and do not move with the ticks
        assert got == {"amd": (3, 1, 2), "zone": (3, 1, 2), "level": (2, 2, 2)}, spec
        counts = counts or out["dual_momentum_board"]["counts"]
        assert out["dual_momentum_board"]["counts"]["pool"] == 6
        assert f["pool"] == 6
        if spec:
            assert f["passed_all"] == len(syms) and f["active"] == list(DMT.parse_filters(spec))
            for k, i in _items(out).items():
                assert i["on"] is (k in f["active"])
                assert i["hidden"] == ((i["fail"] + i["no_read"]) if i["on"] else 0)
            assert out["matched"] == len(syms)
        for t in out["tiles"]:
            for k in DMT.parse_filters(spec):
                assert t["dm_filter"][k] is True


def test_T6_NEG_filters_sort_nothing_survivors_keep_the_chosen_order(dm_board):
    _six(dm_board)
    for srt in ("default", "nearest_demand"):
        base = _syms(B.board(tab="dual_momentum", limit=80, min_tier="any", sort=srt))
        for spec in ("amd", "zone", "level", "amd,level"):
            got = _syms(B.board(tab="dual_momentum", limit=80, min_tier="any", sort=srt,
                                dm=spec))
            assert got == [s for s in base if s in set(got)], (srt, spec)
            assert got and len(got) < len(base)


# --------------------------------------------------------------------------
# T7 — the filter runs BEFORE the cut
# --------------------------------------------------------------------------
def test_T7_filter_is_pre_cut(dm_board):
    picks = [_pick(f"R{i}", i) for i in range(1, 7)]
    dm_board["seed"](picks, {}, {p["symbol"]: _snap(100.0) for p in picks})
    dm_board["amd_cells"] = {p["symbol"]: _known("raided" if p["rank"] >= 5 else "basing")
                             for p in picks}
    out = B.board(tab="dual_momentum", limit=2, min_tier="any", dm="amd")
    assert _syms(out) == ["R5", "R6"]
    # NEGATIVE: not empty, not ranks 1-2
    plain = B.board(tab="dual_momentum", limit=2, min_tier="any")
    assert _syms(plain) == ["R1", "R2"]


# --------------------------------------------------------------------------
# T8 — the zero result is said, never silent
# --------------------------------------------------------------------------
def test_T8_zero_result_serves_the_empty_note(dm_board):
    _six(dm_board)
    dm_board["amd_cells"]["AAA"] = _known("basing")
    out = B.board(tab="dual_momentum", limit=80, min_tier="any", dm="amd,zone,level")
    assert out["tiles"] == []
    assert out["note"] == DMT.filter_empty_note(ALL, 6)
    assert "untick" in out["note"] and "1–6" in out["note"]
    for k in ALL:
        assert DMT.FILTER_LABELS[k] in out["note"]
    blk = out["dual_momentum_board"]
    assert blk["state"] == "ready" and blk["header"].startswith(DMT.MARK)
    assert blk["counts"]["pool"] == 6 and blk["filters"]["passed_all"] == 0
    assert isinstance(blk["filters"]["line"], str)
    # NEGATIVE: an unticked view of the same pool keeps the ordinary note
    assert B.board(tab="dual_momentum", limit=80, min_tier="any")["note"] == DMT.NOTE


def test_T8_NEG_empty_pool_with_a_box_ticked_keeps_the_empty_pool_note(dm_board):
    dm_board["seed"]([], {}, {}, rows=[{"symbol": "LOSER", "abs_mom_pass": False}])
    out = B.board(tab="dual_momentum", limit=80, dm="amd")
    assert out["tiles"] == [] and out["note"] == DMT.EMPTY_NOTE


# --------------------------------------------------------------------------
# T9 — unknown / absent never narrows
# --------------------------------------------------------------------------
def test_T9_unknown_or_absent_param_is_no_filter(dm_board):
    _six(dm_board)
    base = B.board(tab="dual_momentum", limit=80, min_tier="any")
    for dm in (None, "", "foo", "foo,bar", 7):
        out = B.board(tab="dual_momentum", limit=80, min_tier="any", dm=dm)
        assert _syms(out) == _syms(base), dm
        f = out["dual_momentum_board"]["filters"]
        assert f["active"] == [] and f["line"] is None and f["passed_all"] is None
        assert all(i["hidden"] == 0 and i["on"] is False for i in f["items"])
        # NEGATIVE: the counts are still served so each box shows its number
        assert [i["pass"] for i in f["items"]] == [3, 3, 2]
        assert out["note"] == DMT.NOTE


# --------------------------------------------------------------------------
# T10 — never silent
# --------------------------------------------------------------------------
def test_T10_every_ticked_combination_serves_a_line_naming_what_it_hid(dm_board):
    _six(dm_board)
    for n in (1, 2, 3):
        for combo in itertools.combinations(ALL, n):
            out = B.board(tab="dual_momentum", limit=80, min_tier="any", dm=",".join(combo))
            f = out["dual_momentum_board"]["filters"]
            line = f["line"]
            assert isinstance(line, str) and line.startswith("Filters on"), combo
            for i in f["items"]:
                if i["on"]:
                    assert f"{i['label']}: {i['pass']} pass, {i['hidden']} hidden" in line
                    assert "(2 not read)" in line
                else:
                    assert i["label"] not in line
            assert f"{f['passed_all']} of 6 pass every ticked box" in line


# --------------------------------------------------------------------------
# T11 — cost: one engine per read, no per-name AMD frame
# --------------------------------------------------------------------------
def test_T11_one_read_each_and_no_per_name_amd(dm_board, monkeypatch):
    _six(dm_board)
    calls = {"amd": 0, "level": 0}
    real_amd, real_lv = DMT.amd_reads, DMT.key_level_reads

    def amd_spy(*a, **k):
        calls["amd"] += 1
        return real_amd(*a, **k)

    def lv_spy(*a, **k):
        calls["level"] += 1
        return real_lv(*a, **k)

    def boom(*a, **k):
        raise AssertionError("a per-name AMD frame read on the DM tab")

    from supply_demand import amd as AMD
    monkeypatch.setattr(DMT, "amd_reads", amd_spy)
    monkeypatch.setattr(DMT, "key_level_reads", lv_spy)
    monkeypatch.setattr(TB, "amd_verdict", boom)
    monkeypatch.setattr(AMD, "find_cycle", boom)
    monkeypatch.setattr(AMD, "find_raids", boom)
    monkeypatch.setattr(B, "_attach_amd_raids", boom)
    dm_board["snap_calls"].clear()
    dm_board["fs_calls"].clear()
    out = B.board(tab="dual_momentum", limit=80, min_tier="any", dm="amd,zone,level")
    assert _syms(out) == ["AAA"]
    assert len(dm_board["snap_calls"]) == 1
    assert calls == {"amd": 1, "level": 1}
    assert dm_board["fs_calls"] == [("2026-09-29",)]


def test_T11_the_real_reads_are_handed_the_pool_the_snapshot_and_the_clock(dm_board,
                                                                         monkeypatch):
    _six(dm_board)
    seen = {}
    monkeypatch.setattr(DMT, "amd_reads",
                        lambda syms, **k: seen.setdefault("amd", (list(syms), k)) and ({}, {}))
    monkeypatch.setattr(DMT, "key_level_reads",
                        lambda syms, raw, **k: seen.setdefault("lv", (list(syms), raw, k))
                        and ({}, None))
    B.board(tab="dual_momentum", limit=2, min_tier="any")
    pool = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
    assert seen["amd"][0] == pool and seen["amd"][1]["now"].tzinfo is not None
    assert seen["lv"][0] == pool and set(seen["lv"][1]) == set(pool)
    assert seen["lv"][2]["first_seen"] == {} and seen["lv"][2]["now"] == seen["amd"][1]["now"]


# --------------------------------------------------------------------------
# T12 — the memo is never mutated
# --------------------------------------------------------------------------
def test_T12_memo_never_mutated_with_filters_on(dm_board):
    _six(dm_board)
    snap = json.dumps(DMT._memo["entry"], sort_keys=True, default=str)
    for spec in ("amd", "zone,level", "amd,zone,level"):
        out = B.board(tab="dual_momentum", limit=80, min_tier="any", dm=spec,
                      sort="nearest_demand")
        for t in out["tiles"]:
            t["dm_filter"]["amd"] = "tampered"
    assert json.dumps(DMT._memo["entry"], sort_keys=True, default=str) == snap


# --------------------------------------------------------------------------
# T13 — wording
# --------------------------------------------------------------------------
def test_T13_json_clean_and_honest_words(dm_board):
    _six(dm_board)
    for spec in ("", "amd", "amd,zone,level"):
        out = B.board(tab="dual_momentum", limit=80, min_tier="any", dm=spec)
        json.dumps(out, allow_nan=False)
        for s in _strings(out):
            assert not re.search("bounc|fake", s, re.I), s
            assert "filters nothing" not in s, s             # HA.HONESTY never leaks here
    it = {k: DMT.filters_block([], (), pool=0, amd_summary=s, level_error=None)["items"]
          for k, s in (("up", {"available": True, "built_at_et": "2026-09-28T17:32:00-04:00",
                               "stale": True, "stale_note": "STALE-NOTE"}),
                       ("down", {"available": False}))}
    for key in ("up", "down"):
        amd = it[key][0]["note"]
        assert HA.AMD_MEASURED["claim"] in amd and "INVERTED" in amd
        assert "51.9" in amd                                    # served, from HA — never typed
    assert "2026-09-28 17:32 ET" in it["up"][0]["note"] and "STALE-NOTE" in it["up"][0]["note"]
    assert "could not be read" in it["down"][0]["note"]
    zone, level = DMT.zone_note(), DMT.level_note()
    assert "UNMEASURED" in zone and "UNMEASURED" in level
    assert f"{AG.ALERT_MAX_ABOVE_DEMAND_PCT:g}%" in zone
    assert f"{DMT.KEY_LEVEL_NEAR_PCT:g}%" in level and KLT.LOWS in level
    for s in (DMT.FILTERS_NOTE, DMT.FILTER_EMPTY_FMT, zone, level,
              *DMT.FILTER_LABELS.values(), it["up"][0]["note"], it["down"][0]["note"]):
        assert not re.search("bounc|fake", s, re.I)
        assert "filters nothing" not in s
    assert "gate nothing" in DMT.FILTERS_NOTE


# --------------------------------------------------------------------------
# T14 — source guard
# --------------------------------------------------------------------------
def test_T14_SOURCE_GUARD_constants_by_name_never_retyped():
    src = (BACKEND / "chart_maps" / "dual_momentum_tab.py").read_text(encoding="utf-8")
    assert not re.search(r"""==\s*["']raided["']|["']raided["']\s*==""", src)
    assert "TB.AMD_TURNING" in src and "AMD_MEASURED" in src and "KLT.rank" in src
    assert "51.9" not in src and "ALERT_MAX_ABOVE_DEMAND_PCT =" not in src
    assert not re.search(r"amd_verdict|find_cycle|find_raids", src)
    assert "from chart_maps import board" not in src and "import board" not in src
    assert len(re.findall(r"^KEY_LEVEL_NEAR_PCT\s*=\s*1\.0\s*$", src, re.M)) == 1
    assert len(re.findall(r"KEY_LEVEL_NEAR_PCT\s*=", src)) == 1
    assert "HIS CALL" in src
    assert set(DMT.LEVEL_STATUSES) <= set(KLT.COUNT_KEYS)
    assert DMT.KEY_LEVEL_NEAR_PCT == 1.0
    # the 📍 bound is the gate's OWN default — the one the 🎯 read binds
    assert DMT.near_demand_pct() == AG.ALERT_MAX_ABOVE_DEMAND_PCT
    assert "HONESTY" not in src and '"title"' not in src


# --------------------------------------------------------------------------
# T15 — gates nothing: only the tab reads the filter
# --------------------------------------------------------------------------
def test_T15_nothing_outside_chart_maps_reads_the_filter():
    hits = []
    for root, dirs, files in os.walk(BACKEND):
        dirs[:] = [d for d in dirs if d not in (".venv", "node_modules", "__pycache__", ".git")]
        rel = Path(root).relative_to(BACKEND)
        top = rel.parts[0] if rel.parts else ""
        if top in ("chart_maps", "tests"):
            continue
        for f in files:
            if f.endswith(".py"):
                txt = (Path(root) / f).read_text(encoding="utf-8", errors="ignore")
                if "dm_filter" in txt or "DMT.passes" in txt:
                    hits.append(str(rel / f))
    assert hits == []


# --------------------------------------------------------------------------
# T16 — other tabs never see it
# --------------------------------------------------------------------------
def test_T16_other_tabs_ignore_dm(monkeypatch):
    seen = []

    def kl_stub(*a, **k):
        seen.append(k)
        return {"tiles": []}

    def dm_boom(*a, **k):
        raise AssertionError("the DM builder ran for another tab")

    monkeypatch.setattr(B, "key_level_tiles", kl_stub)
    monkeypatch.setattr(B, "dual_momentum_tiles", dm_boom)
    out = B.board(tab="key_levels", dm="amd,zone")
    assert seen and all("dm_filters" not in k and "dm" not in k for k in seen)
    assert all("dm_filter" not in t for t in out.get("tiles") or [])
    assert "dual_momentum_board" not in out
    src = inspect.getsource(B.board)
    assert src.count("dm_filters=") == 1
    i = src.index("dm_filters=")
    assert 'elif t == "dual_momentum":' in src[max(0, i - 200):i]


# --------------------------------------------------------------------------
# T17 — the API forwards `dm`
# --------------------------------------------------------------------------
def test_T17_api_forwards_dm(monkeypatch):
    from chart_maps import api
    got = []
    monkeypatch.setattr(api.board_mod, "board", lambda **k: got.append(k) or {"tiles": []})
    asyncio.run(api.chart_maps(tab="dual_momentum", dm="amd,level"))
    assert got[-1]["dm"] == "amd,level" and got[-1]["tab"] == "dual_momentum"
    # NEGATIVE: a direct call without it hands board() None, never a Query object
    asyncio.run(api.chart_maps(tab="dual_momentum"))
    assert got[-1]["dm"] is None
    asyncio.run(api.chart_maps(tab="dual_momentum", dm="   "))
    assert got[-1]["dm"] is None


# --------------------------------------------------------------------------
# T18 — failure paths never raise
# --------------------------------------------------------------------------
def test_T18_a_raising_read_is_not_read_never_a_500(dm_board, monkeypatch):
    _six(dm_board)

    def boom(*a, **k):
        raise RuntimeError("sweep store down")

    monkeypatch.setattr(DMT, "amd_reads", boom)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any", dm="amd")
    blk = out["dual_momentum_board"]
    assert blk["state"] == "ready" and out["tiles"] == []
    assert _items(out)["amd"]["no_read"] == 6 and _items(out)["amd"]["hidden"] == 6
    assert out["note"] == DMT.filter_empty_note(("amd",), 6)
    assert "could not be read" in _items(out)["amd"]["note"]
    # the other boxes still read
    assert _items(out)["zone"]["pass"] == 3

    def boom_lv(*a, **k):
        raise RuntimeError("frames down")

    monkeypatch.setattr(DMT, "key_level_reads", boom_lv)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any", dm="level")
    assert out["tiles"] == [] and _items(out)["level"]["no_read"] == 6
    assert "failed" in _items(out)["level"]["note"] and "frames down" in _items(out)["level"]["note"]
    json.dumps(out, allow_nan=False)
    # NEGATIVE: unticked, the same failure hides nothing
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    assert len(out["tiles"]) == 6


def test_T18_blocks_other_than_ready_carry_no_filters():
    assert DMT.warming_block()["filters"] is None
    assert DMT.no_scan_block()["filters"] is None
    assert DMT.error_block("x")["filters"] is None
