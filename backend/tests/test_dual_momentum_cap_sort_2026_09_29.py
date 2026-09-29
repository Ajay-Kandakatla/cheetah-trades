"""🏎️ Dual Momentum tab — the MAIN package + two critic fixes + the 💰 sort
(2026-09-29).

Ajay 2026-09-29: "Also a sort by market cap please" (on the Dual Momentum tab,
next to the 🏎️ rank ↔ 📍 nearest-demand toggle).

Pins:
  * critic fix 3 — a leader with a stored doc but NO demand band under the
    print (`dm_zone.reason == "no_band"`) is a plain FAIL of 📍, never "not
    read"; no doc / no print stay "not read".
  * critic fix 2 — the 🔑 pool build is memoised keyed by (session, scan
    generation, pool) with the Key Levels tab's own `MEMO_TTL_SEC`; the live
    `rank` still runs per request; a raising build is never memoised; the
    memo is never mutated or aliased by a tile.
  * 💰 — `market_cap` (largest first) / `market_cap_asc` (smallest first),
    tab-scoped like 📍, over the WHOLE pool after the filters and BEFORE the
    cut; no cap LAST in both directions; ties by the page's rank; an unknown
    key falls back to the rank; ONE cached cap read (the weekly shares cache,
    `market_caps_for(..., cap=0)`) and only when the order is asked for; the
    served line says how many had no cap. Display only.
Positive AND negative cases. Stubs only (the conftest refuses Mongo).
"""
from __future__ import annotations

import json
import re
import time
from datetime import timedelta
from pathlib import Path

import pytest

from chart_maps import board as B
from chart_maps import dual_momentum_tab as DMT
from chart_maps import key_levels_tab as KLT
from rotation import hottest_amd as HA
from supply_demand import enterable as EN
from tests.test_dual_momentum_tab import (NOW, _clean_memo, _doc, _pick, _snap,  # noqa: F401
                                          _std, _strings, dm_board, scan_file)
from tests.test_hottest_amd import _verdict
from tests.test_key_levels_tab import _frame, _rth

BACKEND = Path(__file__).resolve().parents[1]


def _syms(out):
    return [t["symbol"] for t in out["tiles"]]


def _board(**kw):
    kw.setdefault("limit", 80)
    kw.setdefault("min_tier", "any")
    return B.board(tab="dual_momentum", **kw)


# --------------------------------------------------------------------------
# critic fix 3 — no band under the print is a FAIL of 📍, not "not read"
# --------------------------------------------------------------------------
def test_F3_no_band_zone_is_a_plain_fail_pure():
    zone = {"reason": "no_band", "demand": None, "gate": {"verdict": "BLOCKED",
                                                          "room_ok": None, "prox_ok": None}}
    tf = DMT.tile_filter(None, zone, None)
    assert tf["zone"] is False
    assert DMT.passes(tf, ("zone",)) is False
    # NEGATIVE: even an inconsistent gate copy never makes "no band" pass
    zone_bad = {**zone, "gate": {"prox_ok": True}}
    assert DMT.tile_filter(None, zone_bad, None)["zone"] is False
    # NEGATIVE: no doc / no print / no zone at all stay "not read"
    for reason in ("no_doc", "no_print"):
        assert DMT.tile_filter(None, {"reason": reason, "gate": {"prox_ok": None}},
                               None)["zone"] is None, reason
    assert DMT.tile_filter(None, None, None)["zone"] is None
    # a real band keeps the gate's own proximity read
    ok = {"reason": "ok", "gate": {"prox_ok": True}}
    assert DMT.tile_filter(None, ok, None)["zone"] is True


def test_F3_no_band_through_the_builder_counts_as_fail_and_is_hidden(dm_board):
    picks = [_pick("NEAR", 1), _pick("SUP", 2), _pick("NOD", 3), _pick("NOP", 4)]
    docs = {"NEAR": _doc([(98.0, 99.0)], [(130.0, 131.0)], floor="intact"),
            "SUP": _doc(None, [(110.0, 112.0)]),                  # stored, supply only
            "NOP": _doc([(97.0, 99.5)], [(110.0, 112.0)])}
    snaps = {"NEAR": _snap(98.5), "SUP": _snap(100.0), "NOD": _snap(100.0)}
    scan = [{"symbol": "NEAR", "last_close": 98.5, "liquidity": {"avg_dollar_vol": 50e6}},
            {"symbol": "SUP", "last_close": 100.0, "liquidity": {"avg_dollar_vol": 50e6}},
            {"symbol": "NOD", "last_close": 100.0, "liquidity": {"avg_dollar_vol": 50e6}},
            {"symbol": "NOP", "last_close": None, "liquidity": {"avg_dollar_vol": 50e6}}]
    dm_board["seed"](picks, docs, snaps, scan)
    full = {t["symbol"]: t for t in _board()["tiles"]}
    assert full["SUP"]["dm_zone"]["reason"] == "no_band"
    assert full["SUP"]["dm_filter"]["zone"] is False
    # NEGATIVE: no stored doc / no print remain "not read"
    assert full["NOD"]["dm_zone"]["reason"] == "no_doc" and full["NOD"]["dm_filter"]["zone"] is None
    assert full["NOP"]["dm_zone"]["reason"] == "no_print" and full["NOP"]["dm_filter"]["zone"] is None
    out = _board(dm="zone")
    assert _syms(out) == ["NEAR"]
    it = {i["key"]: i for i in out["dual_momentum_board"]["filters"]["items"]}["zone"]
    assert (it["pass"], it["fail"], it["no_read"], it["hidden"]) == (1, 1, 2, 3)
    assert "(2 not read)" in out["dual_momentum_board"]["filters"]["line"]


# --------------------------------------------------------------------------
# critic fix 2 — the 🔑 pool build is memoised
# --------------------------------------------------------------------------
def _kl(frames):
    calls = []

    def build_fn(universe, session, *, universe_fn):
        calls.append((universe, session, tuple(universe_fn(universe))))
        return KLT.build(universe, session, universe_fn=universe_fn,
                         frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames})
    return build_fn, calls


def test_M1_same_session_generation_pool_builds_once_rank_runs_each_time(monkeypatch):
    monkeypatch.setattr(DMT, "scan_generation", lambda: 111)
    frames = {"NER": _frame(), "FAR": _frame()}
    build_fn, calls = _kl(frames)
    syms = ["NER", "FAR"]
    a, err_a = DMT.key_level_reads(syms, {"NER": _rth(100.9), "FAR": _rth(101.2)},
                                   now=NOW, first_seen={}, build_fn=build_fn)
    # a NEW print against the SAME memoised build: the live read moves
    b, err_b = DMT.key_level_reads(syms, {"NER": _rth(101.5), "FAR": _rth(100.5)},
                                   now=NOW + timedelta(minutes=5), first_seen={},
                                   build_fn=build_fn)
    assert err_a is None and err_b is None
    assert len(calls) == 1                                   # ONE build, two reads
    assert DMT.tile_filter(None, None, a["NER"])["level"] is True
    assert DMT.tile_filter(None, None, a["FAR"])["level"] is False
    # the rank is NOT memoised — the flipped prints flip the reads
    assert DMT.tile_filter(None, None, b["NER"])["level"] is False
    assert DMT.tile_filter(None, None, b["FAR"])["level"] is True


def test_M2_NEG_each_key_part_and_the_ttl_force_a_rebuild(monkeypatch):
    gen = {"v": 111}
    monkeypatch.setattr(DMT, "scan_generation", lambda: gen["v"])
    frames = {"NER": _frame(), "FAR": _frame()}
    build_fn, calls = _kl(frames)
    snaps = {"NER": _rth(100.9), "FAR": _rth(101.2)}
    DMT.key_level_reads(["NER", "FAR"], snaps, now=NOW, first_seen={}, build_fn=build_fn)
    assert len(calls) == 1
    DMT.key_level_reads(["NER"], snaps, now=NOW, first_seen={}, build_fn=build_fn)
    assert len(calls) == 2                                   # another pool
    gen["v"] = 222
    DMT.key_level_reads(["NER"], snaps, now=NOW, first_seen={}, build_fn=build_fn)
    assert len(calls) == 3                                   # a new scan generation
    DMT.key_level_reads(["NER"], snaps, now=NOW + timedelta(days=1), first_seen={},
                        build_fn=build_fn)
    assert len(calls) == 4                                   # another session
    DMT._kl_memo["ts"] = time.time() - KLT.MEMO_TTL_SEC - 1
    DMT.key_level_reads(["NER"], snaps, now=NOW + timedelta(days=1), first_seen={},
                        build_fn=build_fn)
    assert len(calls) == 5                                   # older than the TTL
    DMT.key_level_reads(["NER"], snaps, now=NOW + timedelta(days=1), first_seen={},
                        build_fn=build_fn)
    assert len(calls) == 5                                   # fresh again -> hit


def test_M3_NEG_a_raising_build_is_never_memoised(monkeypatch):
    monkeypatch.setattr(DMT, "scan_generation", lambda: 111)
    n = {"calls": 0}

    def boom(*a, **k):
        n["calls"] += 1
        raise RuntimeError("price cache down")
    for _ in range(3):
        reads, err = DMT.key_level_reads(["AAA"], {}, now=NOW, first_seen={}, build_fn=boom)
        assert err == "price cache down" and reads["AAA"]["status"] == DMT.LEVEL_UNREAD
    assert n["calls"] == 3 and DMT._kl_memo == {}
    # a success after the failures is served and memoised
    build_fn, calls = _kl({"AAA": _frame()})
    reads, err = DMT.key_level_reads(["AAA"], {"AAA": _rth(100.9)}, now=NOW, first_seen={},
                                     build_fn=build_fn)
    assert err is None and reads["AAA"]["status"] == "ranked" and len(calls) == 1


def test_M4_NEG_the_memo_is_never_mutated_or_aliased_by_a_read(monkeypatch):
    monkeypatch.setattr(DMT, "scan_generation", lambda: 111)
    build_fn, _ = _kl({"NER": _frame()})
    reads, _ = DMT.key_level_reads(["NER"], {"NER": _rth(100.9)}, now=NOW, first_seen={},
                                   build_fn=build_fn)
    before = json.dumps(DMT._kl_memo["entry"], sort_keys=True, default=str)
    reads["NER"]["near"]["label"] = "tampered"
    for k in list(reads["NER"]["near"]):
        if isinstance(reads["NER"]["near"][k], dict):
            reads["NER"]["near"][k]["x"] = "tampered"
    DMT.key_level_reads(["NER"], {"NER": _rth(100.9)}, now=NOW, first_seen={},
                        build_fn=build_fn)
    assert json.dumps(DMT._kl_memo["entry"], sort_keys=True, default=str) == before
    # the engine's `near_block` embeds the entry's own `last_bar` dict — a
    # tile block that aliased it would write into the memo
    DMT._kl_memo.clear()
    shared = {"state": "held"}
    entry = {"syms": ["NER"], "levels": {"NER": {"last_bar": {"m1": shared}}},
             "session": "2026-09-29"}
    monkeypatch.setattr(KLT, "rank", lambda e, raw, **k: (
        [{"symbol": "NER", "near": {"distance_pct": 0.5,
                                    "last_bar": e["levels"]["NER"]["last_bar"]["m1"]}}],
        {"ranked": 1}))
    reads, _ = DMT.key_level_reads(["NER"], {}, now=NOW, first_seen={},
                                   build_fn=lambda *a, **k: entry)
    reads["NER"]["near"]["last_bar"]["state"] = "tampered"
    assert DMT._kl_memo["entry"]["levels"]["NER"]["last_bar"]["m1"] == {"state": "held"}


def test_M5_SOURCE_the_ttl_is_the_key_levels_tabs_own_by_name():
    src = (BACKEND / "chart_maps" / "dual_momentum_tab.py").read_text(encoding="utf-8")
    body = src[src.index("def _kl_pool_entry"):src.index("def key_level_reads")]
    assert "KLT.MEMO_TTL_SEC" in body and "scan_generation()" in body
    assert "session.isoformat()" in body and "tuple(syms)" in body
    assert not re.search(r"<\s*\d", body)                 # no retyped number


# --------------------------------------------------------------------------
# 💰 market-cap order
# --------------------------------------------------------------------------
CAPS = {"AAA": 5e9, "BBB": None, "CCC": 2e9, "DDD": 2e9, "EEE": 10e9}


def _five(dm_board, monkeypatch, caps=None):
    picks = [_pick(s, i + 1) for i, s in enumerate(("AAA", "BBB", "CCC", "DDD", "EEE"))]
    snaps = {p["symbol"]: _snap(100.0) for p in picks}
    dm_board["seed"](picks, {}, snaps)
    reads = []
    c = CAPS if caps is None else caps

    def caps_stub(syms, **k):
        reads.append(list(syms))
        return {s: c.get(s) for s in syms}
    monkeypatch.setattr(DMT, "market_caps", caps_stub)
    return reads


def test_C1_largest_first_then_smallest_first_none_last_both_ties_by_rank(dm_board,
                                                                         monkeypatch):
    _five(dm_board, monkeypatch)
    out = _board(sort="market_cap")
    assert _syms(out) == ["EEE", "AAA", "CCC", "DDD", "BBB"]
    assert out["sort"] == "market_cap" and out["dual_momentum_board"]["sort"] == "market_cap"
    out = _board(sort="market_cap_asc")
    assert _syms(out) == ["CCC", "DDD", "AAA", "EEE", "BBB"]
    assert out["sort"] == "market_cap_asc"
    # NEGATIVE: the no-cap name is LAST in both directions, never first
    for srt in ("market_cap", "market_cap_asc"):
        assert _syms(_board(sort=srt))[-1] == "BBB", srt


def test_C1_NEG_ties_stay_in_rank_order_even_against_the_symbol(dm_board, monkeypatch):
    picks = [_pick("ZZZ", 1), _pick("AAA", 2), _pick("MMM", 3), _pick("BBB", 4)]
    dm_board["seed"](picks, {}, {p["symbol"]: _snap(100.0) for p in picks})
    caps = {"ZZZ": 3e9, "AAA": 3e9, "MMM": None, "BBB": None}
    monkeypatch.setattr(DMT, "market_caps", lambda syms, **k: {s: caps.get(s) for s in syms})
    assert _syms(_board(sort="market_cap")) == ["ZZZ", "AAA", "MMM", "BBB"]
    assert _syms(_board(sort="market_cap_asc")) == ["ZZZ", "AAA", "MMM", "BBB"]


@pytest.mark.parametrize("bad", ["cap", "market_cap_desc", "MARKET_CAP", "marketcap", " "])
def test_C2_NEG_an_unknown_sort_falls_back_to_the_rank(dm_board, monkeypatch, bad):
    reads = _five(dm_board, monkeypatch)
    out = _board(sort=bad)
    assert out["sort"] == "default" and _syms(out) == ["AAA", "BBB", "CCC", "DDD", "EEE"]
    assert out["dual_momentum_board"]["cap_sort"] is None
    assert reads == []                                       # no cap read at all


def test_C3_sorts_served_on_the_tab_and_only_there(dm_board, monkeypatch):
    _five(dm_board, monkeypatch)
    out = _board()
    assert out["sorts"][:4] == [
        {"key": "default", "label": DMT.DEFAULT_SORT_LABEL},
        {"key": "nearest_demand", "label": DMT.NEAREST_SORT_LABEL},
        {"key": "market_cap", "label": DMT.MARKET_CAP_LABEL},
        {"key": "market_cap_asc", "label": DMT.MARKET_CAP_ASC_LABEL}]
    assert DMT.MARKET_CAP_LABEL.startswith("\U0001F4B0") and "largest" in DMT.MARKET_CAP_LABEL
    assert "smallest" in DMT.MARKET_CAP_ASC_LABEL
    keys = [s["key"] for s in out["sorts"]]
    assert keys.count("market_cap") == 1 and keys.count("market_cap_asc") == 1
    assert set(DMT.TAB_SORTS) == {"nearest_demand", "market_cap", "market_cap_asc"}
    assert not set(DMT.TAB_SORTS) & set(B.SORTS)


def test_C3_NEG_no_other_tab_offers_or_honours_the_cap_keys(monkeypatch):
    stub = lambda *a, **k: {"tiles": []}                   # noqa: E731
    for name in ("zone_tiles", "vcp_tiles", "supply_tiles", "key_level_tiles"):
        monkeypatch.setattr(B, name, stub)
    for tab in ("zones", "vcp", "supply", "key_levels"):
        for srt in ("market_cap", "market_cap_asc"):
            out = B.board(tab=tab, sort=srt)
            assert out["sort"] == B.DEFAULT_SORT, (tab, srt)
            assert srt not in [s["key"] for s in out["sorts"]], (tab, srt)


def test_C4_the_order_is_pre_cut_over_the_whole_pool(dm_board, monkeypatch):
    _five(dm_board, monkeypatch)
    assert _syms(_board(sort="market_cap", limit=2)) == ["EEE", "AAA"]
    assert _syms(_board(sort="market_cap_asc", limit=2)) == ["CCC", "DDD"]
    # NEGATIVE: not ranks 1-2 re-ordered after the cut
    assert _syms(_board(limit=2)) == ["AAA", "BBB"]


def test_C5_filters_first_then_the_cap_order_over_the_survivors(dm_board, monkeypatch):
    reads = _five(dm_board, monkeypatch)
    dm_board["amd_cells"] = {s: HA.read_one(s, _verdict("raided" if s != "EEE" else "basing"))
                             for s in CAPS}
    dm_board["amd_summary"] = {"available": True, "built_at_et": "2026-09-28T17:32:00-04:00"}
    out = _board(sort="market_cap", dm="amd")
    assert _syms(out) == ["AAA", "CCC", "DDD", "BBB"]          # EEE filtered out first
    cs = out["dual_momentum_board"]["cap_sort"]
    assert cs["ordered"] == 4 and cs["no_cap"] == 1 and cs["with_cap"] == 3
    assert reads == [["AAA", "BBB", "CCC", "DDD"]]              # read over the survivors


def test_C6_the_served_line_says_how_many_had_no_cap(dm_board, monkeypatch):
    _five(dm_board, monkeypatch)
    for srt, word in (("market_cap", "largest"), ("market_cap_asc", "smallest")):
        blk = _board(sort=srt)["dual_momentum_board"]
        cs = blk["cap_sort"]
        assert cs["sort"] == srt and cs["largest_first"] is (srt == "market_cap")
        assert (cs["ordered"], cs["with_cap"], cs["no_cap"]) == (5, 4, 1)
        assert cs["line"].startswith("\U0001F4B0") and f"{word} first" in cs["line"]
        assert "1 of 5 leaders have no cached market cap" in cs["line"]
        assert "sit last" in cs["line"] and "gates nothing" in cs["line"]
        assert f"{word} first" in blk["header"] and "\U0001F4B0" in blk["header"]
    # NEGATIVE: the rank and 📍 orders serve no cap line and no cap read
    for srt in ("default", "nearest_demand"):
        blk = _board(sort=srt)["dual_momentum_board"]
        assert blk["cap_sort"] is None and "\U0001F4B0" not in blk["header"]


def test_C7_one_cap_read_only_when_asked_and_the_tile_shows_it(dm_board, monkeypatch):
    reads = _five(dm_board, monkeypatch)
    out = _board()
    assert reads == []
    assert all("dm_market_cap" not in t for t in out["tiles"])
    assert all("Cap" not in {s["k"] for s in t["stats"]} for t in out["tiles"])
    out = _board(sort="market_cap")
    assert len(reads) == 1 and sorted(reads[0]) == sorted(CAPS)
    by = {t["symbol"]: t for t in out["tiles"]}
    assert by["EEE"]["dm_market_cap"] == 10e9 and by["BBB"]["dm_market_cap"] is None
    st = {t["symbol"]: {s["k"]: s["v"] for s in t["stats"]} for t in out["tiles"]}
    assert st["EEE"]["Cap"] == "$10.0B" and st["BBB"]["Cap"] == "—"


def test_C8_NEG_a_failed_cap_read_keeps_the_rank_and_says_every_name(dm_board, monkeypatch):
    _five(dm_board, monkeypatch, caps={})

    def boom(names):
        raise RuntimeError("shares cache down")
    real = DMT.market_caps
    monkeypatch.setattr(DMT, "market_caps", lambda syms, **k: real(syms, caps_fn=boom))
    for srt in ("market_cap", "market_cap_asc"):
        out = _board(sort=srt)
        assert _syms(out) == ["AAA", "BBB", "CCC", "DDD", "EEE"], srt
        cs = out["dual_momentum_board"]["cap_sort"]
        assert cs["no_cap"] == 5 and "5 of 5 leaders have no cached market cap" in cs["line"]


def test_C9_market_cap_key_pure_junk_is_last():
    keys = {s: DMT.market_cap_key(c, r, s) for s, c, r in (
        ("A", 1e9, 1), ("B", None, 2), ("C", float("nan"), 3), ("D", 0, 4), ("E", -5e9, 5),
        ("F", "junk", 6), ("G", "3e9", 7))}
    order = sorted(keys, key=keys.get)
    assert order == ["G", "A", "B", "C", "D", "E", "F"]
    asc = {s: DMT.market_cap_key(c, r, s, largest_first=False) for s, c, r in (
        ("A", 1e9, 1), ("B", None, 2), ("G", 3e9, 7))}
    assert sorted(asc, key=asc.get) == ["A", "G", "B"]
    # NEGATIVE: an unparseable rank never outranks a real one on a tie
    assert DMT.market_cap_key(1e9, None, "Z") > DMT.market_cap_key(1e9, 50, "A")


def test_C10_market_caps_reuses_the_cached_reader_with_no_provider_tail(monkeypatch):
    from catalysts import promo_circuit as PC
    seen = []

    def spy(tickers, last_prices, fetch=None, coll=None, cap=None, **k):
        seen.append((list(tickers), dict(last_prices), cap, fetch))
        return {"AAA": 5e9, "BBB": None, "CCC": float("nan")}
    monkeypatch.setattr(PC, "market_caps_for", spy)
    got = DMT.market_caps(["AAA", "BBB", "CCC", "DDD"])
    assert got == {"AAA": 5e9, "BBB": None, "CCC": None, "DDD": None}
    assert seen == [(["AAA", "BBB", "CCC", "DDD"], {}, 0, None)]   # cap=0: never a fetch
    # NEGATIVE: a junk answer fails open to every name None
    monkeypatch.setattr(PC, "market_caps_for", lambda *a, **k: ["junk"])
    assert DMT.market_caps(["AAA"]) == {"AAA": None}
    assert DMT.market_caps([]) == {}


def test_C11_display_only_the_gate_reads_do_not_move_and_json_is_clean(dm_board,
                                                                      monkeypatch):
    _std(dm_board)
    caps = {"AAA": 1e9, "BBB": 9e9, "CCC": None, "DDD": 4e9, "EEE": 2e9}
    monkeypatch.setattr(DMT, "market_caps", lambda syms, **k: {s: caps.get(s) for s in syms})
    base = {t["symbol"]: t for t in _board()["tiles"]}
    snap = json.dumps(DMT._memo["entry"], sort_keys=True, default=str)
    for srt in ("market_cap", "market_cap_asc"):
        out = _board(sort=srt)
        json.dumps(out, allow_nan=False)
        for t in out["tiles"]:
            b = base[t["symbol"]]
            assert t["enterable"] == b["enterable"] and t["dm_zone"] == b["dm_zone"]
            assert t["dm_filter"] == b["dm_filter"]
        for s in _strings(out):
            assert not re.search(r"bounc|fake", s, re.I), s
        assert out["dual_momentum_board"]["counts"]["pool"] == 5
    assert json.dumps(DMT._memo["entry"], sort_keys=True, default=str) == snap
    assert EN.KIND_BY_TAB["dual_momentum"] == "demand"


def test_C12_SOURCE_the_cap_is_read_nowhere_as_a_gate():
    src = (BACKEND / "chart_maps" / "dual_momentum_tab.py").read_text(encoding="utf-8")
    assert "market_caps_for" in src and "cap=0" in src
    assert not re.search(r"MIN_CAP_USD\s*=|700_?000_?000|7e8", src)
    board = (BACKEND / "chart_maps" / "board.py").read_text(encoding="utf-8")
    body = board[board.index("def dual_momentum_tiles"):board.index("def _usd_short")]
    assert body.count("DMT.market_caps(") == 1
    assert body.index("DMT.passes(") < body.index("DMT.market_caps(") < body.index("_finish(tiles")
