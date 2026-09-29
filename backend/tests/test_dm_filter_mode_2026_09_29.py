"""🏎️ Dual Momentum filter boxes — ANY (default) vs "must match all" (2026-09-29).

Ajay 2026-09-29, after 🌀 AMD raided 5 · 📍 near demand 12 · 🔑 near a lower
key level 2 showed 0 names ticked together: "How can I see all of these? at
the same time? is there a check box selection?"

Pins: ticking several boxes shows leaders passing ANY ticked box (the
default); `dm_mode=all` restores AND; absent / unknown mode = any; a not-read
box never passes in either mode; each shown leader carries a served badge for
each TICKED box it passes (off its `dm_filter`, never a fail or a not-read);
the served counts / line / hidden number / empty note per mode; the union keeps
the chosen order and runs before the cut. Positive AND negative cases, stubs
only (the `dm_board` fixture refuses Mongo).
"""
from __future__ import annotations

import asyncio
import json
import re

import pytest

from chart_maps import board as B
from chart_maps import dual_momentum_tab as DMT
from rotation import hottest_amd as HA
from tests.test_dual_momentum_filters import _items, _known, _near, _six, _syms  # noqa: F401
from tests.test_dual_momentum_tab import (_clean_memo, _pick, _snap, _strings,  # noqa: F401
                                          dm_board, scan_file)

ALL3 = ("amd", "zone", "level")
LAB = DMT.FILTER_LABELS


def _board(**k):
    return B.board(tab="dual_momentum", limit=80, min_tier="any", **k)


def _f(out):
    return out["dual_momentum_board"]["filters"]


def _dm_badges(t):
    return [b for b in t.get("badges") or [] if isinstance(b, dict) and b.get("dm_filter")]


# ---------------------------------------------------------------------------
# M1 — the mode param
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("v", ["all", "ALL", " All "])
def test_M1_parse_mode_all(v):
    assert DMT.parse_mode(v) == DMT.MODE_ALL == "all"


@pytest.mark.parametrize("v", [None, "", "   ", "any", "foo", "and", "or", 1, ["all"], True])
def test_M1_NEG_absent_or_unknown_mode_is_any(v):
    assert DMT.parse_mode(v) == DMT.MODE_ANY == DMT.FILTER_MODE_DEFAULT == "any"


def test_M1_constants():
    assert DMT.FILTER_MODE_PARAM == "dm_mode"
    assert DMT.FILTER_MODES == ("any", "all")
    assert DMT.MODE_ALL_LABEL == "must match all"


# ---------------------------------------------------------------------------
# M2 — passes(): ANY vs ALL, not-read never passes
# ---------------------------------------------------------------------------
def test_M2_passes_any_and_all():
    tf = {"amd": True, "zone": False, "level": None}
    assert DMT.passes(tf, ("amd", "zone")) is True                     # default ANY
    assert DMT.passes(tf, ("amd", "zone"), "any") is True
    assert DMT.passes(tf, ("amd", "zone"), "all") is False              # 1 of 2 -> hidden in ALL
    assert DMT.passes(tf, ("amd",), "all") is True
    assert DMT.passes(tf, ("amd", "zone"), "foo") is True               # unknown -> ANY


def test_M2_NEG_not_read_or_fail_never_passes_in_either_mode():
    for mode in ("any", "all", None):
        assert DMT.passes({"amd": None, "zone": None, "level": None}, ALL3, mode) is False
        assert DMT.passes({"amd": False, "zone": None}, ("amd", "zone"), mode) is False
        assert DMT.passes({"amd": 1, "zone": "yes"}, ("amd", "zone"), mode) is False   # truthy != True
        assert DMT.passes(None, ("amd",), mode) is False
        assert DMT.passes({}, (), mode) is True                          # nothing ticked
    # an UNTICKED box's True never lets a leader in
    assert DMT.passes({"amd": False, "zone": True}, ("amd",)) is False


# ---------------------------------------------------------------------------
# M3 — the six-leader fixture through the REAL builder, ANY (default)
#   amd True A,B,C · False D · None E,F
#   zone True A,C,D · False B · None E,F
#   level True A,B · False C,D · None E,F
# ---------------------------------------------------------------------------
ANY_WANT = {"amd": ["AAA", "BBB", "CCC"], "zone": ["AAA", "CCC", "DDD"],
            "level": ["AAA", "BBB"], "amd,zone": ["AAA", "BBB", "CCC", "DDD"],
            "amd,level": ["AAA", "BBB", "CCC"], "zone,level": ["AAA", "BBB", "CCC", "DDD"],
            "amd,zone,level": ["AAA", "BBB", "CCC", "DDD"]}
ALL_WANT = {"amd": ["AAA", "BBB", "CCC"], "zone": ["AAA", "CCC", "DDD"],
            "level": ["AAA", "BBB"], "amd,zone": ["AAA", "CCC"], "amd,level": ["AAA", "BBB"],
            "zone,level": ["AAA"], "amd,zone,level": ["AAA"]}


def test_M3_any_is_the_default_union(dm_board):
    _six(dm_board)
    for spec, want in ANY_WANT.items():
        for kw in ({}, {"dm_mode": None}, {"dm_mode": ""}, {"dm_mode": "any"},
                   {"dm_mode": "foo"}):
            out = _board(dm=spec, **kw)
            assert _syms(out) == want, (spec, kw)
            f = _f(out)
            assert f["mode"] == "any" and f["active"] == list(DMT.parse_filters(spec))
            assert f["shown"] == f["passed_any"] == len(want)
            assert f["passed_all"] == len(ALL_WANT[spec])
            assert f["hidden"] == 6 - len(want) and f["pool"] == 6
            assert out["matched"] == len(want)
            # the per-box counts are over the WHOLE pool, in either mode
            got = {k: (i["pass"], i["fail"], i["no_read"]) for k, i in _items(out).items()}
            assert got == {"amd": (3, 1, 2), "zone": (3, 1, 2), "level": (2, 2, 2)}


def test_M3_all_switch_restores_and(dm_board):
    _six(dm_board)
    for spec, want in ALL_WANT.items():
        out = _board(dm=spec, dm_mode="all")
        assert _syms(out) == want, spec
        f = _f(out)
        assert f["mode"] == "all" and f["shown"] == f["passed_all"] == len(want)
        assert f["hidden"] == 6 - len(want)
        assert f["note"] == DMT.FILTERS_NOTE


def test_M3_NEG_one_of_two_hidden_in_all_shown_in_any(dm_board):
    _six(dm_board)
    # BBB: 🌀 True, 📍 False · DDD: 🌀 False, 📍 True
    anyv = _syms(_board(dm="amd,zone"))
    allv = _syms(_board(dm="amd,zone", dm_mode="all"))
    for s in ("BBB", "DDD"):
        assert s in anyv and s not in allv


def test_M3_NEG_passing_none_is_hidden_and_not_read_never_passes(dm_board):
    _six(dm_board)
    for mode in (None, "all"):
        out = _board(dm="amd,zone,level", dm_mode=mode)
        # EEE (every box not read: not_in_store / no stored bands / no_print)
        # and FFF (no read at all) pass NOTHING -> hidden in ANY too
        assert "EEE" not in _syms(out) and "FFF" not in _syms(out)
    full = {t["symbol"]: t for t in _board()["tiles"]}
    assert full["EEE"]["dm_filter"]["amd"] is None
    assert full["EEE"]["dm_filter"]["zone"] is None
    assert full["EEE"]["dm_filter"]["level"] is None


def test_M3_NEG_unticked_true_never_lets_a_leader_in(dm_board):
    _six(dm_board)
    # DDD passes 📍 only — ticking 🌀 + 🔑 (ANY) must not show it
    assert "DDD" not in _syms(_board(dm="amd,level"))


def test_M3_NEG_mode_without_a_box_filters_nothing(dm_board):
    _six(dm_board)
    base = _syms(_board())
    for mode in ("all", "any", "foo"):
        out = _board(dm_mode=mode)
        assert _syms(out) == base
        f = _f(out)
        assert f["active"] == [] and f["shown"] is None and f["hidden"] == 0 and f["line"] is None
        assert all(not _dm_badges(t) for t in out["tiles"])


# ---------------------------------------------------------------------------
# M4 — served badges: one per TICKED box the leader passes
# ---------------------------------------------------------------------------
def test_M4_badges_per_passed_ticked_box(dm_board):
    _six(dm_board)
    for mode in (None, "all"):
        for spec in ANY_WANT:
            out = _board(dm=spec, dm_mode=mode)
            act = DMT.parse_filters(spec)
            for t in out["tiles"]:
                bs = _dm_badges(t)
                want = [k for k in DMT.FILTER_KEYS if k in act and t["dm_filter"][k] is True]
                assert [b["dm_filter"] for b in bs] == want, (spec, mode, t["symbol"])
                assert [b["text"] for b in bs] == [LAB[k] for k in want]
                assert all(b["tone"] == "good" for b in bs)
                assert bs, (spec, t["symbol"])          # a shown leader passed at least one


def test_M4_the_union_list_reads_which_box_let_each_in(dm_board):
    _six(dm_board)
    out = _board(dm="amd,zone,level")
    got = {t["symbol"]: [b["text"] for b in _dm_badges(t)] for t in out["tiles"]}
    assert got == {"AAA": [LAB["amd"], LAB["zone"], LAB["level"]],
                   "BBB": [LAB["amd"], LAB["level"]],
                   "CCC": [LAB["amd"], LAB["zone"]],
                   "DDD": [LAB["zone"]]}


def test_M4_NEG_no_badge_for_a_fail_a_not_read_or_an_unticked_box():
    tf = {"amd": True, "zone": False, "level": None}
    assert DMT.filter_badges(tf, ALL3) == [{"text": LAB["amd"], "tone": "good", "dm_filter": "amd"}]
    assert DMT.filter_badges({"amd": False, "zone": True}, ("amd",)) == []      # unticked 📍
    assert DMT.filter_badges(tf, ()) == []
    assert DMT.filter_badges(None, ALL3) == []
    assert DMT.filter_badges({"amd": 1, "zone": "x"}, ALL3) == []                 # truthy != True


def test_M4_NEG_badges_never_leak_to_the_rank_chip_or_the_memo(dm_board):
    _six(dm_board)
    out = _board(dm="amd,zone,level")
    for t in out["tiles"]:
        assert t["badges"][0]["text"].startswith(DMT.MARK + " #")               # rank chip first
    # a second, unfiltered request carries no filter badge (no memo aliasing)
    assert all(not _dm_badges(t) for t in _board()["tiles"])


# ---------------------------------------------------------------------------
# M5 — order + cut
# ---------------------------------------------------------------------------
def test_M5_union_keeps_the_chosen_order(dm_board):
    _six(dm_board)
    for srt in ("default", "nearest_demand"):
        base = _syms(_board(sort=srt))
        for spec in ANY_WANT:
            got = _syms(_board(sort=srt, dm=spec))
            assert got == [s for s in base if s in set(got)], (srt, spec)


def test_M5_union_is_pre_cut(dm_board):
    picks = [_pick(f"R{i}", i) for i in range(1, 7)]
    dm_board["seed"](picks, {}, {p["symbol"]: _snap(100.0) for p in picks})
    dm_board["amd_cells"] = {p["symbol"]: _known("raided" if p["rank"] == 5 else "basing")
                             for p in picks}
    dm_board["level_reads"] = {p["symbol"]: ({"status": "ranked", "near": _near(0.2)}
                                             if p["rank"] == 6 else {"status": "broken"})
                               for p in picks}
    out = B.board(tab="dual_momentum", limit=2, min_tier="any", dm="amd,level")
    assert _syms(out) == ["R5", "R6"]
    # NEGATIVE: ALL -> nobody passes both
    out = B.board(tab="dual_momentum", limit=2, min_tier="any", dm="amd,level", dm_mode="all")
    assert _syms(out) == []


# ---------------------------------------------------------------------------
# M6 — the served line, the note and the empty state per mode
# ---------------------------------------------------------------------------
def test_M6_any_line_names_each_box_pass_and_the_union(dm_board):
    _six(dm_board)
    out = _board(dm="amd,zone,level")
    line = _f(out)["line"]
    assert line.startswith("Filters on (any ticked box) — ")
    for k in ALL3:
        i = _items(out)[k]
        assert f"{i['label']}: {i['pass']} pass (2 not read)" in line
        assert f"{i['label']}: {i['pass']} pass, " not in line          # no per-box "hidden" in ANY
    assert "4 of 6 pass at least one ticked box, 2 hidden" in line
    assert _f(out)["note"] == DMT.FILTERS_NOTE_ANY
    # NEGATIVE: an unticked box is not named
    line1 = _f(_board(dm="amd"))["line"]
    assert LAB["amd"] in line1 and LAB["zone"] not in line1 and LAB["level"] not in line1


def test_M6_all_line_keeps_per_box_hidden(dm_board):
    _six(dm_board)
    out = _board(dm="amd,zone,level", dm_mode="all")
    line = _f(out)["line"]
    assert line.startswith("Filters on (must match all) — ")
    assert "1 of 6 pass every ticked box" in line
    for k in ALL3:
        i = _items(out)[k]
        assert f"{i['label']}: {i['pass']} pass, {i['hidden']} hidden" in line


def test_M6_empty_note_differs_per_mode(dm_board):
    _six(dm_board)
    dm_board["amd_cells"] = {s: _known("basing") for s in ("AAA", "BBB", "CCC", "DDD")}
    dm_board["level_reads"] = {s: {"status": "broken", "near": None}
                               for s in ("AAA", "BBB", "CCC", "DDD")}
    anyo = _board(dm="amd,level")
    allo = _board(dm="amd,level", dm_mode="all")
    assert anyo["tiles"] == [] and allo["tiles"] == []
    assert anyo["note"] == DMT.filter_empty_note(("amd", "level"), 6)
    assert allo["note"] == DMT.filter_empty_note(("amd", "level"), 6, "all")
    assert anyo["note"] != allo["note"]
    assert "passes any ticked box" in anyo["note"]
    assert f"{LAB['amd']} or {LAB['level']}" in anyo["note"]
    assert "passes every ticked box" in allo["note"]
    assert f"{LAB['amd']} + {LAB['level']}" in allo["note"]
    assert _f(anyo)["shown"] == 0 and _f(anyo)["hidden"] == 6


def test_M6_NEG_a_non_empty_union_keeps_the_ordinary_note(dm_board):
    _six(dm_board)
    # ALL would be empty for zone,level with AAA's 🔑 failing; ANY is not
    dm_board["level_reads"]["AAA"] = {"status": "broken", "near": None}
    assert _board(dm="zone,level", dm_mode="all")["tiles"] == []
    out = _board(dm="zone,level")
    assert _syms(out) and out["note"] == DMT.NOTE


def test_M6_NEG_empty_pool_keeps_the_empty_pool_note(dm_board):
    dm_board["seed"]([], {}, {}, rows=[{"symbol": "LOSER", "abs_mom_pass": False}])
    for mode in (None, "all"):
        out = B.board(tab="dual_momentum", limit=80, dm="amd,zone", dm_mode=mode)
        assert out["tiles"] == [] and out["note"] == DMT.EMPTY_NOTE


def test_M6_words_are_honest_and_json_clean(dm_board):
    _six(dm_board)
    for mode in (None, "all"):
        for spec in ("", "amd", "amd,zone,level"):
            out = _board(dm=spec, dm_mode=mode)
            json.dumps(out, allow_nan=False)
            for s in _strings(out):
                assert not re.search("bounc|fake", s, re.I), s
    for s in (DMT.FILTERS_NOTE_ANY, DMT.FILTER_EMPTY_ANY_FMT, DMT.MODE_ALL_LABEL):
        assert not re.search("bounc|fake", s, re.I)
    assert "gate nothing" in DMT.FILTERS_NOTE_ANY and DMT.MODE_ALL_LABEL in DMT.FILTERS_NOTE_ANY


# ---------------------------------------------------------------------------
# M7 — the API forwards dm_mode; other tabs never see it
# ---------------------------------------------------------------------------
def test_M7_api_forwards_dm_mode(monkeypatch):
    from chart_maps import api
    got = []
    monkeypatch.setattr(api.board_mod, "board", lambda **k: got.append(k) or {"tiles": []})
    asyncio.run(api.chart_maps(tab="dual_momentum", dm="amd,level", dm_mode="all"))
    assert got[-1]["dm_mode"] == "all" and got[-1]["dm"] == "amd,level"
    # NEGATIVE: absent / blank -> None (never a Query object)
    asyncio.run(api.chart_maps(tab="dual_momentum"))
    assert got[-1]["dm_mode"] is None
    asyncio.run(api.chart_maps(tab="dual_momentum", dm_mode="  "))
    assert got[-1]["dm_mode"] is None


def test_M7_NEG_other_tabs_never_get_dm_mode(monkeypatch):
    import inspect
    seen = []
    monkeypatch.setattr(B, "key_level_tiles", lambda *a, **k: seen.append(k) or {"tiles": []})
    monkeypatch.setattr(B, "dual_momentum_tiles",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("DM ran")))
    B.board(tab="key_levels", dm="amd", dm_mode="all")
    assert seen and all("dm_mode" not in k for k in seen)
    src = inspect.getsource(B.board)
    assert src.count("dm_mode=") == 1
    i = src.index("dm_mode=")
    assert 'elif t == "dual_momentum":' in src[max(0, i - 300):i]


def test_M7_the_filter_read_is_the_badge_source_not_a_second_read(dm_board, monkeypatch):
    _six(dm_board)
    calls = []
    real = DMT.filter_badges
    monkeypatch.setattr(DMT, "filter_badges", lambda tf, act: calls.append(tf) or real(tf, act))
    out = _board(dm="amd,zone,level")
    assert len(calls) == len(out["tiles"]) == 4
    for tf, t in zip(calls, out["tiles"]):
        assert tf is t["dm_filter"]
    # an unticked request builds no badges at all
    calls.clear()
    _board()
    assert calls == []


def test_M7_amd_store_down_any_mode_still_shows_the_other_boxes(dm_board, monkeypatch):
    _six(dm_board)
    dm_board["amd_cells"] = {s: HA.blank("store_unavailable")
                             for s in ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF")}
    out = _board(dm="amd,zone")
    assert _syms(out) == ["AAA", "CCC", "DDD"]                  # 📍 alone carries them
    assert _items(out)["amd"]["no_read"] == 6
    assert all(_dm_badges(t) == [{"text": LAB["zone"], "tone": "good", "dm_filter": "zone"}]
               for t in out["tiles"])
