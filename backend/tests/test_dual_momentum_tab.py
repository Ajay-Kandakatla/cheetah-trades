"""🏎️ Dual Momentum tab on Chart Maps (2026-09-29) — spec WP-BE tests 1-15.

Ajay 2026-09-29: "Can you pull these in to chart maps and add the demand zones
logic to these? https://pounce.ajaykandakatla.dev/dual-momentum" + "I want a
toggle and also the check boxes we have like AMD and supple and demand zones
computing and also key levels".

Pins the memo + pure reads in `chart_maps/dual_momentum_tab.py`, the builder
and the board wiring in `chart_maps/board.py` (one engine call per scan
generation, one snapshot, ONE zone-store read shared with the 🎯 read, the
page's rank, the 📍 order, the tab-scoped sort, every checkbox's wiring), the
`KIND_BY_TAB` entry and the gate that is never loosened. Positive AND
negative cases. Stubs only — the conftest refuses Mongo; no thread is ever
started (`_spawn` is patched) and nothing reaches the network.
"""
from __future__ import annotations

import copy
import inspect
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps import board as B
from chart_maps import dual_momentum_tab as DMT
from sepa import dual_momentum as DM
from sepa import scanner
from supply_demand import alert_gates as AG
from supply_demand import bounce_room, room_floor, zone_store
from supply_demand import enterable as EN

ET = ZoneInfo("America/New_York")
# the REAL attachers, captured before the board fixture stubs them (test 16)
_REAL_ATTACH_BS = B.attach_band_structure
_REAL_BS_COVERAGE = B.band_structure_coverage
BACKEND = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 29, 11, 0, tzinfo=ET)

# the 6d3ad93 tuple, before this tab
TABS_BEFORE = ("vcp", "topping", "zones", "supply", "ict", "deep_demand", "quick_bounce",
               "breaking", "gabbar", "undervalue", "zero_dte", "winners", "earnings",
               "keltner", "amd", "ipo", "key_levels")


class _Fixed(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


def _pick(sym, rank, *, r12=100.0, score=None, rs=90, name=None):
    return {"symbol": sym, "name": name if name is not None else f"{sym} Corp",
            "return_1m": 5.0, "return_3m": 20.0, "return_6m": 50.0, "return_12m": r12,
            "return_gate": r12, "abs_mom_pass": True, "beats_spy": True, "rs_rank": rs,
            "stage": 2, "score": score if score is not None else 100.0 - rank,
            "is_sepa_candidate": False, "entry_setup": None, "rank": rank}


def _result(picks, *, regime=None, error=None, rows=None):
    res = {"generated_at": 1759150000, "generated_at_iso": "2026-09-29T15:00:00Z",
           "regime": regime if regime is not None else
           {"spy_return_12m": 18.5, "risk_on": True,
            "label": "RISK-ON — SPY 12m return positive, take leaders"},
           "gate_lookback_days": 252,
           "rows": rows if rows is not None else [dict(p) for p in picks],
           "picks": [dict(p) for p in picks], "universe_size": 500,
           "scan_generated_at": 1759140000}
    if error:
        res["error"] = error
    return res


def _doc(demand=None, supply=None, *, floor=None, prev_close=100.0):
    bands = []
    for lo, hi in (demand or []):
        bands.append({"kind": "demand", "lo": lo, "hi": hi, "touches": 3, "strength": 50})
    for lo, hi in (supply or []):
        bands.append({"kind": "supply", "lo": lo, "hi": hi, "touches": 3, "strength": 50})
    d = {"bands": bands, "prev_close": prev_close}
    if floor is not None:
        d["_floor"] = floor
    return d


def _snap(px, prev=None):
    return {"last_trade_price": px, "price": px, "prev_day_close": prev if prev is not None else px,
            "low": px, "change_pct": 0.0}


@pytest.fixture(autouse=True)
def _clean_memo(monkeypatch):
    DMT._memo.clear()
    DMT._warming.clear()
    DMT._failed.clear()
    spawns = []
    monkeypatch.setattr(DMT, "_spawn", lambda target, name: spawns.append((target, name)))
    yield spawns
    DMT._memo.clear()
    DMT._warming.clear()
    DMT._failed.clear()


@pytest.fixture
def scan_file(tmp_path, monkeypatch):
    p = tmp_path / "latest.json"
    p.write_text("{}")
    monkeypatch.setattr(scanner, "LATEST_PATH", p)
    return p


# --------------------------------------------------------------------------
# 1 — TABS
# --------------------------------------------------------------------------
def test_01_tab_sits_right_after_key_levels_and_nothing_else_moved():
    assert B.TABS.index("dual_momentum") == B.TABS.index("key_levels") + 1
    assert B.TABS[-1] == "dual_momentum"
    # NEGATIVE: the tuple minus the insertion is the 6d3ad93 tuple
    assert tuple(t for t in B.TABS if t != "dual_momentum") == TABS_BEFORE


# --------------------------------------------------------------------------
# 2 — build
# --------------------------------------------------------------------------
def test_02_build_calls_the_engine_once_with_top_n_only():
    calls = []

    def compute(**kw):
        calls.append(kw)
        return _result([_pick("AAA", 1), _pick("BBB", 2)])

    scan = {"all_results": [{"symbol": "AAA", "last_close": 10.0}, {"symbol": "ZZZ"}]}
    entry = DMT.build(80, compute_fn=compute, scan_fn=lambda: scan)
    assert calls == [{"top_n": 80}]
    assert [p["symbol"] for p in entry["picks"]] == ["AAA", "BBB"]
    assert set(entry["scan_rows"]) == {"AAA"}             # the pool only
    assert entry["eligible"] == 2 and entry["universe_size"] == 500
    assert isinstance(entry["built_at"], str) and entry["regime"]["risk_on"] is True


def test_02_NEG_an_engine_error_raises_and_is_never_memoised(scan_file, monkeypatch):
    monkeypatch.setattr(DM, "compute", lambda **kw: _result([], error="no_scan", rows=[]))
    with pytest.raises(RuntimeError):
        DMT.build(80, scan_fn=lambda: {})
    with pytest.raises(RuntimeError):
        DMT.cached_or_warm(now=NOW, pool_n=80, sync=True)
    assert DMT._memo == {}
    # an empty engine answer (no rows) is an error too
    with pytest.raises(RuntimeError):
        DMT.build(80, compute_fn=lambda **kw: {"rows": [], "picks": []}, scan_fn=lambda: {})
    # but rows with no pick is a real answer, not an error
    e = DMT.build(80, compute_fn=lambda **kw: _result([], rows=[{"symbol": "X"}]),
                  scan_fn=lambda: {})
    assert e["picks"] == [] and e["eligible"] == 0


def test_02_eligible_uses_the_engines_own_rs_default():
    rows = [{"abs_mom_pass": True, "rs_rank": None}, {"abs_mom_pass": True, "rs_rank": 5},
            {"abs_mom_pass": False, "rs_rank": 99}]

    def compute(top_n=15, gate_lookback_days=252, min_rs_rank=10):
        return _result([], rows=rows)

    assert DMT.build(80, compute_fn=compute, scan_fn=lambda: {})["eligible"] == 0
    assert inspect.signature(DM.compute).parameters["min_rs_rank"].default == 0


# --------------------------------------------------------------------------
# 3 — the memo
# --------------------------------------------------------------------------
def _patch_build(monkeypatch, fn=None):
    calls = []

    def build(pool_n, **kw):
        calls.append(pool_n)
        if fn is not None:
            return fn(pool_n)
        return {"key": None, "built_ts": __import__("time").time(), "built_at": "x",
                "picks": [], "n": len(calls)}
    monkeypatch.setattr(DMT, "build", build)
    return calls


def test_03_memo_cold_warms_once_then_serves(scan_file, monkeypatch, _clean_memo):
    spawns = _clean_memo
    calls = _patch_build(monkeypatch)
    got = DMT.cached_or_warm(now=NOW, pool_n=80)
    assert got == {"state": "warming", "entry": None} and len(spawns) == 1
    # a concurrent second call adds no second spawn
    assert DMT.cached_or_warm(now=NOW, pool_n=80)["state"] == "warming"
    assert len(spawns) == 1 and calls == []
    spawns[0][0]()                                          # the thread body
    assert calls == [80] and DMT._warming == set()
    got = DMT.cached_or_warm(now=NOW, pool_n=80)
    assert got["state"] == "ready" and got["entry"]["n"] == 1
    # same key and fresh -> no rebuild
    assert len(spawns) == 1 and calls == [80]


def test_03_memo_new_generation_serves_old_and_rebuilds_once(scan_file, monkeypatch,
                                                             _clean_memo):
    import os
    spawns = _clean_memo
    calls = _patch_build(monkeypatch)
    DMT.cached_or_warm(now=NOW, pool_n=80, sync=True)
    old = DMT._memo["entry"]
    st = scan_file.stat()
    os.utime(scan_file, (st.st_atime, st.st_mtime + 100))
    got = DMT.cached_or_warm(now=NOW, pool_n=80)
    assert got["state"] == "ready" and got["entry"] is old and len(spawns) == 1
    DMT.cached_or_warm(now=NOW, pool_n=80)
    assert len(spawns) == 1                                 # still one rebuild
    spawns[0][0]()
    assert DMT._memo["entry"] is not old and DMT._memo["key"][0] == int(st.st_mtime + 100)
    assert len(calls) == 2


def test_03_memo_ttl_expiry_rebuilds_once(scan_file, monkeypatch, _clean_memo):
    spawns = _clean_memo
    _patch_build(monkeypatch)
    DMT.cached_or_warm(now=NOW, pool_n=80, sync=True)
    DMT._memo["entry"]["built_ts"] -= DMT.MEMO_TTL_SEC + 1
    got = DMT.cached_or_warm(now=NOW, pool_n=80)
    assert got["state"] == "ready" and len(spawns) == 1


def test_03_NEG_a_late_build_for_an_older_key_never_overwrites_a_newer(scan_file, monkeypatch):
    _patch_build(monkeypatch)
    with DMT._lock:
        assert DMT._store((200, "2026-09-29", 80), {"n": "new"})
        assert not DMT._store((100, "2026-09-29", 80), {"n": "old"})
    assert DMT._memo["entry"]["n"] == "new"


def test_03_NEG_a_raising_build_leaves_the_memo_empty_and_retries(scan_file, monkeypatch,
                                                                 _clean_memo):
    spawns = _clean_memo

    def boom(pool_n):
        raise RuntimeError("engine down")
    _patch_build(monkeypatch, boom)
    DMT.cached_or_warm(now=NOW, pool_n=80)
    spawns[0][0]()
    assert DMT._memo == {} and DMT._warming == set()
    # critic 2026-09-29 #1: a failed build is served as "error", never
    # "warming" forever, and is NOT rebuilt on every poll.
    for _ in range(3):
        got = DMT.cached_or_warm(now=NOW, pool_n=80)
        assert got["state"] == "error" and got["entry"] is None
        assert "engine down" in got["reason"]
    assert len(spawns) == 1                                 # no rebuild inside the backoff
    # after FAIL_RETRY_SEC: exactly ONE retry, still served as the error
    DMT._failed["ts"] -= DMT.FAIL_RETRY_SEC + 1
    assert DMT.cached_or_warm(now=NOW, pool_n=80)["state"] == "error"
    assert DMT.cached_or_warm(now=NOW, pool_n=80)["state"] == "error"
    assert len(spawns) == 2


def test_03_NEG_a_build_that_raises_three_times_runs_the_engine_once(scan_file, monkeypatch,
                                                                    _clean_memo):
    """The critic's demo: a raising build polled 3 times ran 3 builds."""
    spawns = _clean_memo
    calls = _patch_build(monkeypatch, lambda n: (_ for _ in ()).throw(RuntimeError("x")))
    for _ in range(3):
        DMT.cached_or_warm(now=NOW, pool_n=80)
        for target, _name in list(spawns):
            spawns.remove((target, _name))
            target()
    assert calls == [80]


def test_03_a_success_after_a_failure_clears_it_and_serves_ready(scan_file, monkeypatch,
                                                                 _clean_memo):
    spawns = _clean_memo
    state = {"fail": True}

    def maybe(pool_n):
        if state["fail"]:
            raise RuntimeError("engine down")
        return {"key": None, "built_ts": __import__("time").time(), "built_at": "x",
                "picks": [], "n": "ok"}
    _patch_build(monkeypatch, maybe)
    DMT.cached_or_warm(now=NOW, pool_n=80)
    spawns[0][0]()
    assert DMT.cached_or_warm(now=NOW, pool_n=80)["state"] == "error"
    state["fail"] = False
    DMT._failed["ts"] -= DMT.FAIL_RETRY_SEC + 1
    DMT.cached_or_warm(now=NOW, pool_n=80)
    spawns[-1][0]()
    got = DMT.cached_or_warm(now=NOW, pool_n=80)
    assert got["state"] == "ready" and got["entry"]["n"] == "ok"
    assert DMT._failed == {}


def test_03_NEG_a_failure_for_another_key_does_not_block_this_key(scan_file, monkeypatch,
                                                                  _clean_memo):
    import os
    spawns = _clean_memo
    _patch_build(monkeypatch, lambda n: (_ for _ in ()).throw(RuntimeError("x")))
    DMT.cached_or_warm(now=NOW, pool_n=80)
    spawns[0][0]()
    st = scan_file.stat()
    os.utime(scan_file, (st.st_atime, st.st_mtime + 100))   # a new scan generation
    got = DMT.cached_or_warm(now=NOW, pool_n=80)
    assert got["state"] == "warming" and len(spawns) == 2   # the new scan is tried at once


def test_03_NEG_a_held_entry_is_served_through_a_failed_rebuild_without_hammering(
        scan_file, monkeypatch, _clean_memo):
    spawns = _clean_memo
    state = {"fail": False}

    def maybe(pool_n):
        if state["fail"]:
            raise RuntimeError("engine down")
        return {"key": None, "built_ts": __import__("time").time(), "built_at": "x",
                "picks": [], "n": "held"}
    _patch_build(monkeypatch, maybe)
    DMT.cached_or_warm(now=NOW, pool_n=80, sync=True)
    DMT._memo["entry"]["built_ts"] -= DMT.MEMO_TTL_SEC + 1
    state["fail"] = True
    got = DMT.cached_or_warm(now=NOW, pool_n=80)
    assert got["state"] == "ready" and got["entry"]["n"] == "held" and len(spawns) == 1
    spawns[0][0]()
    for _ in range(3):
        got = DMT.cached_or_warm(now=NOW, pool_n=80)
        assert got["state"] == "ready" and got["entry"]["n"] == "held"
    assert len(spawns) == 1


def test_03_NEG_an_engine_no_scan_answer_is_served_as_no_scan_not_warming(
        scan_file, monkeypatch, _clean_memo):
    """A scan file with empty all_results: the engine answers error=no_scan."""
    spawns = _clean_memo
    monkeypatch.setattr(DM, "compute", lambda **kw: {"rows": [], "picks": [], "error": "no_scan"})
    with pytest.raises(DMT.EngineNoScan):
        DMT.build(80, scan_fn=lambda: {})
    DMT.cached_or_warm(now=NOW, pool_n=80)
    spawns[0][0]()
    assert DMT.cached_or_warm(now=NOW, pool_n=80) == {"state": "no_scan", "entry": None}
    assert DMT._memo == {} and len(spawns) == 1


def test_03_error_block_is_served_and_never_warming():
    blk = DMT.error_block("engine down")
    assert blk["state"] == "error" and blk["counts"] is None
    assert "engine down" in blk["header"] and str(DMT.FAIL_RETRY_SEC // 60) in blk["header"]
    assert "bounc" not in blk["header"].lower()


def test_03_NEG_no_scan_file_never_calls_the_engine(tmp_path, monkeypatch, _clean_memo):
    monkeypatch.setattr(scanner, "LATEST_PATH", tmp_path / "missing.json")
    calls = []
    monkeypatch.setattr(DM, "compute", lambda **kw: calls.append(kw))
    got = DMT.cached_or_warm(now=NOW, pool_n=80)
    assert got == {"state": "no_scan", "entry": None}
    assert calls == [] and _clean_memo == []


# --------------------------------------------------------------------------
# the board fixture
# --------------------------------------------------------------------------
@pytest.fixture
def dm_board(monkeypatch, scan_file):
    state = {"picks": [], "scan": [], "docs_seq": [{}], "store_calls": [], "snaps": {},
             "snap_calls": [], "compute_calls": [], "kl": [], "burst": [], "gex": [],
             "studies": [], "themes": {}, "regime": None}

    def compute(**kw):
        state["compute_calls"].append(kw)
        return _result(state["picks"], regime=state["regime"], rows=state.get("rows"))

    def load_latest(syms):
        i = len(state["store_calls"])
        state["store_calls"].append(sorted(syms))
        docs = state["docs_seq"][min(i, len(state["docs_seq"]) - 1)]
        return None, {s: copy.deepcopy(docs[s]) for s in syms if s in docs}

    def floor_read(doc, band, px, day_low=None, day=None):
        st = (doc or {}).get("_floor")
        return {"state": st} if st is not None else None

    def bulk(syms):
        state["snap_calls"].append(sorted(syms))
        return {s: state["snaps"][s] for s in syms if s in state["snaps"]}

    def live_from(tiles, raw):
        return {t["symbol"]: raw[t["symbol"]] for t in tiles if t["symbol"] in (raw or {})}

    def bars(tiles, days, **k):
        for t in tiles:
            t["bars"] = [{"t": "2026-09-28", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]

    def kl_spy(tiles, out=None, **kw):
        state["kl"].append(len(tiles))
        return {}

    def burst_spy(tiles, out=None, **kw):
        state["burst"].append(len(tiles))
        return {}

    def gex_spy(tiles, wall_kind):
        state["gex"].append((len(tiles), wall_kind))
        return "2026-09-28"

    monkeypatch.setattr(B, "datetime", _Fixed)
    monkeypatch.setattr(DM, "compute", compute)
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": state["scan"]})
    monkeypatch.setattr(zone_store, "load_latest", load_latest)
    monkeypatch.setattr(EN, "_floor_read", floor_read)
    monkeypatch.setattr(B, "_bulk_snaps", bulk)
    monkeypatch.setattr(B, "_live_from_snaps", live_from)
    monkeypatch.setattr(B, "_attach_bars", bars)
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)
    monkeypatch.setattr(B, "_name_for", lambda s: f"{s} Inc")
    monkeypatch.setattr(B, "_theme", lambda s: state["themes"].get(s))
    monkeypatch.setattr(B, "attach_live_now", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(B, "attach_band_structure", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "band_structure_coverage", lambda tiles, kind="demand": {})
    monkeypatch.setattr(B, "attach_burst", burst_spy)
    monkeypatch.setattr(B, "_burst_frames", lambda syms: {})
    monkeypatch.setattr(B, "attach_key_levels", kl_spy)
    monkeypatch.setattr(B, "_gex_decor", gex_spy)
    monkeypatch.setattr(B, "_attach_studies",
                        lambda out, days: state["studies"].append(len(out.get("tiles") or [])))

    def seed(picks, docs, snaps, scan=None, rows=None):
        state["picks"] = picks
        state["rows"] = rows
        state["docs_seq"] = docs if isinstance(docs, list) else [docs]
        state["snaps"] = snaps
        state["scan"] = scan if scan is not None else [
            {"symbol": p["symbol"], "last_close": (snaps.get(p["symbol"]) or {}).get("price"),
             "liquidity": {"avg_dollar_vol": 50e6}} for p in picks]
        DMT._memo.clear()
        DMT.cached_or_warm(now=NOW, pool_n=B.LIMIT_MAX, sync=True)
        state["compute_calls"].clear()
        state["store_calls"].clear()
    state["seed"] = seed
    return state


def _std(dm_board):
    """Five leaders: READY-ish, extended (proximity), room short, supply only, no doc."""
    picks = [_pick("AAA", 1, r12=300.0), _pick("BBB", 2, r12=900.0), _pick("CCC", 3),
             _pick("DDD", 4), _pick("EEE", 5)]
    docs = {"AAA": _doc([(97.0, 99.5)], [(110.0, 112.0)], floor="intact"),
            "BBB": _doc([(80.0, 85.0)], [(120.0, 125.0)], floor="broken"),
            "CCC": _doc([(98.0, 99.8)], [(104.0, 106.0)], floor="swept"),
            "DDD": _doc(None, [(110.0, 112.0)])}
    snaps = {s: _snap(100.0) for s in ("AAA", "BBB", "CCC", "DDD", "EEE")}
    dm_board["seed"](picks, docs, snaps)
    return picks, docs, snaps


# --------------------------------------------------------------------------
# 4 — the page's rank
# --------------------------------------------------------------------------
def test_04_rank_fidelity_default_order_is_the_page_rank(dm_board):
    picks, _, _ = _std(dm_board)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    assert [t["symbol"] for t in out["tiles"]] == ["AAA", "BBB", "CCC", "DDD", "EEE"]
    for t, p in zip(out["tiles"], picks):
        assert t["dual_momentum"]["rank"] == p["rank"]
        assert t["badges"][0]["text"] == DMT.RANK_CHIP_FMT.format(rank=p["rank"])
        assert [s["k"] for s in t["stats"]][:5] == ["12m", "6m", "3m", "1m", "RS"]
    # NEGATIVE: BBB has the larger 12m but the lower score -> keeps rank 2
    assert out["tiles"][1]["dual_momentum"]["return_12m"] > out["tiles"][0]["dual_momentum"]["return_12m"]
    assert out["tiles"][1]["symbol"] == "BBB"
    assert dm_board["compute_calls"] == []                  # served from the memo


# --------------------------------------------------------------------------
# 5 — ONE engine, ONE store read
# --------------------------------------------------------------------------
def test_05_zone_read_is_the_engine_and_matches_the_gate_read(dm_board):
    _, docs, snaps = _std(dm_board)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    by = {t["symbol"]: t for t in out["tiles"]}
    for sym in ("AAA", "BBB", "CCC"):
        t = by[sym]
        z = t["dm_zone"]
        assert z["reason"] == "ok"
        assert z["demand"] == bounce_room.demand_read(100.0, docs[sym])
        assert round(z["demand"]["lo"], 2) == round(t["enterable"]["band"]["lo"], 2)
        assert round(z["demand"]["hi"], 2) == round(t["enterable"]["band"]["hi"], 2)
        room = room_floor.room_block(100.0, docs[sym]["bands"], z["demand"], 100.0, "live")
        stats = {s["k"]: s["v"] for s in t["stats"]}
        assert stats["Room"] == room_floor.room_stat(room) == z["room_stat"]
        assert z["gate"] == {"verdict": t["enterable"]["verdict"],
                             "room_ok": t["enterable"]["gates"]["room_ok"],
                             "prox_ok": t["enterable"]["gates"]["prox_ok"]}
        assert z["print"] == t["enterable"]["print"]
        kinds = [b["kind"] for b in t["bands"]]
        assert kinds[0] == "demand" and "supply" in kinds


def test_05_NEG_race_one_store_read_feeds_both_reads(dm_board):
    picks = [_pick("AAA", 1), _pick("BBB", 2)]
    docs_a = {"AAA": _doc([(97.0, 99.5)], [(110.0, 112.0)], floor="intact"),
              "BBB": _doc([(90.0, 92.0)], [(120.0, 125.0)], floor="intact")}
    docs_b = {"AAA": _doc([(60.0, 61.0)], [(150.0, 160.0)], floor="intact"),
              "BBB": _doc([(50.0, 51.0)], [(150.0, 160.0)], floor="intact")}
    dm_board["seed"](picks, [docs_a, docs_b], {s: _snap(100.0) for s in ("AAA", "BBB")})
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    assert len(dm_board["store_calls"]) == 1               # the DM path reads it ONCE
    for t in out["tiles"]:
        a = docs_a[t["symbol"]]["bands"][0]
        assert (t["dm_zone"]["demand"]["lo"], t["dm_zone"]["demand"]["hi"]) == (a["lo"], a["hi"])
        assert (t["enterable"]["band"]["lo"], t["enterable"]["band"]["hi"]) == (a["lo"], a["hi"])


def test_05_attach_enterable_docs_kwarg_skips_the_store_and_default_reads_once(monkeypatch):
    calls = []
    monkeypatch.setattr(zone_store, "load_latest",
                        lambda syms: calls.append(list(syms)) or (None, {}))
    monkeypatch.setattr(EN, "_floor_read", lambda *a, **k: None)
    tiles = [{"symbol": "AAA", "last_close": 100.0, "_m": {}}]
    doc = _doc([(97.0, 99.5)], [(110.0, 112.0)])
    B.attach_enterable(tiles, kind="demand", live={}, docs={"AAA": doc})
    assert calls == [] and tiles[0]["enterable"]["band"] == {"lo": 97.0, "hi": 99.5}
    # NEGATIVE: every other caller (no docs) still makes exactly ONE store read
    tiles = [{"symbol": "AAA", "last_close": 100.0, "_m": {}},
             {"symbol": "BBB", "last_close": 50.0, "_m": {}}]
    B.attach_enterable(tiles, kind="demand", live={})
    assert len(calls) == 1 and sorted(calls[0]) == ["AAA", "BBB"]


# --------------------------------------------------------------------------
# 6 — the gate is never loosened
# --------------------------------------------------------------------------
def test_06_room_gate_is_called_with_the_house_default(dm_board, monkeypatch):
    seen = []
    real = AG.room_gate

    def spy(*a, **k):
        bound = inspect.signature(real).bind(*a, **k)
        bound.apply_defaults()
        seen.append(bound.arguments["min_room_pct"])
        return real(*a, **k)
    monkeypatch.setattr(AG, "room_gate", spy)
    _std(dm_board)
    B.board(tab="dual_momentum", limit=80, min_tier="any")
    assert seen and set(seen) == {AG.ALERT_MIN_ROOM_PCT}


def test_06_room_under_the_floor_blocks_and_proximity_boundary(dm_board):
    picks = [_pick("RRR", 1), _pick("PPA", 2), _pick("PPB", 3)]
    docs = {"RRR": _doc([(98.0, 99.5)], [(104.99, 106.0)], floor="intact"),   # room 4.99%
            "PPA": _doc([(99.0, 100.0)], [(130.0, 131.0)], floor="intact"),
            "PPB": _doc([(99.0, 100.0)], [(130.0, 131.0)], floor="intact")}
    snaps = {"RRR": _snap(100.0), "PPA": _snap(101.0), "PPB": _snap(101.01)}
    dm_board["seed"](picks, docs, snaps)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    by = {t["symbol"]: t for t in out["tiles"]}
    assert by["RRR"]["dm_zone"]["gate"]["room_ok"] is False
    assert by["RRR"]["enterable"]["verdict"] == EN.BLOCKED and "room" in by["RRR"]["enterable"]["reasons"]
    assert by["PPA"]["dm_zone"]["gate"]["prox_ok"] is True           # exactly 1.00%
    assert by["PPB"]["dm_zone"]["gate"]["prox_ok"] is False          # 1.01%
    assert by["PPB"]["enterable"]["verdict"] == EN.BLOCKED


def test_06_SOURCE_GUARD_no_gate_arithmetic_in_the_tab_module():
    src = (BACKEND / "chart_maps" / "dual_momentum_tab.py").read_text(encoding="utf-8")
    assert "def room_gate" not in src and "def demand_proximity_gate" not in src
    assert "ALERT_MIN_ROOM_PCT =" not in src and "ALERT_MAX_ABOVE_DEMAND_PCT" not in src
    # no numeric literal compared against a room or a distance
    assert not re.search(r"(room|distance|dist)[\w\"'\]\)]*\s*[<>]=?\s*\d", src)
    assert not re.search(r"\d\s*[<>]=?\s*[\w\[\"'.(]*(room|distance|dist)", src)
    assert "sepa.dual_momentum" in src or "from sepa import dual_momentum" in src


# --------------------------------------------------------------------------
# 7 — no fake band
# --------------------------------------------------------------------------
def test_07_no_fake_band_supply_only_no_doc_no_print(dm_board):
    picks = [_pick("SUP", 1), _pick("NOD", 2), _pick("NOP", 3)]
    docs = {"SUP": _doc(None, [(110.0, 112.0)]),
            "NOP": _doc([(97.0, 99.5)], [(110.0, 112.0)])}
    snaps = {"SUP": _snap(100.0), "NOD": _snap(100.0)}
    scan = [{"symbol": "SUP", "last_close": 100.0}, {"symbol": "NOD", "last_close": 100.0},
            {"symbol": "NOP", "last_close": None}]
    dm_board["seed"](picks, docs, snaps, scan)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    by = {t["symbol"]: t for t in out["tiles"]}
    sup = by["SUP"]
    assert sup["dm_zone"]["reason"] == "no_band" and sup["dm_zone"]["demand"] is None
    assert not any(b["kind"] == "demand" for b in sup["bands"])
    assert DMT.NO_BAND_TEXT in [b["text"] for b in sup["badges"]]
    st = {s["k"]: s["v"] for s in sup["stats"]}
    assert st["Room"] == "—" and "To band" not in st
    assert sup["enterable"]["reasons"] == ["no_band"]
    nod = by["NOD"]
    assert nod["dm_zone"]["reason"] == "no_doc" and nod["bands"] == []
    assert DMT.NO_DOC_TEXT in [b["text"] for b in nod["badges"]]
    nop = by["NOP"]
    assert nop["dm_zone"]["reason"] == "no_print" and nop["bands"] == []
    assert DMT.NO_PRINT_TEXT in [b["text"] for b in nop["badges"]]
    c = out["dual_momentum_board"]["counts"]
    assert (c["no_band"], c["no_doc"], c["no_print"], c["with_band"]) == (1, 1, 1, 0)


def test_07_no_to_band_stat_anywhere(dm_board):
    _std(dm_board)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    for t in out["tiles"]:
        assert "To band" not in {s["k"] for s in t["stats"]}


# --------------------------------------------------------------------------
# 8 — floor words and the 📍 key
# --------------------------------------------------------------------------
def test_08_floor_words_pass_through_and_never_collapse():
    assert DMT.floor_state_word("intact") == "intact"
    assert DMT.floor_state_word("swept") == "swept"
    assert DMT.floor_state_word("broken") == "broken"
    assert DMT.floor_state_word(None) == DMT.FLOOR_UNKNOWN == "unknown"
    assert DMT.floor_state_word("") == "unknown" and DMT.floor_state_word("  ") == "unknown"
    assert DMT.floor_state_word(" Broken ") == "broken"
    # NEGATIVE: broken never becomes swept; a future state passes through, ranks 3
    assert DMT.floor_state_word("broken") != "swept"
    assert DMT.floor_state_word("foo") == "foo" and DMT.floor_rank("foo") == 3
    assert [DMT.floor_rank(w) for w in ("intact", "unknown", "swept", "broken")] == [0, 1, 2, 3]


def test_08_floor_vocabulary_is_the_engines():
    sdl = (BACKEND / "supply_demand" / "sd_liquidity.py").read_text(encoding="utf-8")
    ag = (BACKEND / "supply_demand" / "alert_gates.py").read_text(encoding="utf-8")
    for w in ("intact", "swept", "broken"):
        assert f'"state": "{w}"' in sdl or f'state = "{w}"' in ag or f'"{w}"' in ag
    assert '"state": "intact"' in sdl and '"state": "swept"' in sdl and '"state": "broken"' in sdl
    assert 'state = "broken"' in ag
    assert "intact" in AG.FLOOR_HELD_STATES


def test_08_broken_counts_as_broken_and_the_buckets_sum(dm_board):
    _std(dm_board)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    c = out["dual_momentum_board"]["counts"]
    assert c["broken"] == 1 and c["swept"] == 1 and c["held"] == 1
    assert c["held"] + c["swept"] + c["broken"] + c["floor_unknown"] == c["with_band"] == 3
    by = {t["symbol"]: t for t in out["tiles"]}
    assert {s["k"]: s["v"] for s in by["BBB"]["stats"]}["Band"] == "floor broken"
    assert by["BBB"]["dm_zone"]["floor"] == "broken" and by["BBB"]["dm_zone"]["floor_held"] is False
    assert "floor broken" in by["BBB"]["why"]


def test_08_nearest_order_groups_distance_rank_symbol_and_is_stable(dm_board):
    picks = [_pick("NOB", 1), _pick("BRK", 2), _pick("SWP", 3), _pick("UNK", 4),
             _pick("INF", 5), _pick("INN", 6), _pick("INT", 7), _pick("TIE", 8)]
    docs = {"BRK": _doc([(99.0, 99.9)], [(130.0, 131.0)], floor="broken"),
            "SWP": _doc([(99.0, 99.9)], [(130.0, 131.0)], floor="swept"),
            "UNK": _doc([(99.0, 99.9)], [(130.0, 131.0)]),
            "INF": _doc([(90.0, 92.0)], [(130.0, 131.0)], floor="intact"),     # far
            "INN": _doc([(98.0, 99.0)], [(130.0, 131.0)], floor="intact"),     # near
            "INT": _doc([(95.0, 97.0)], [(130.0, 131.0)], floor="intact"),
            "TIE": _doc([(95.0, 97.0)], [(130.0, 131.0)], floor="intact"),
            "NOB": _doc(None, [(130.0, 131.0)])}
    dm_board["seed"](picks, docs, {p["symbol"]: _snap(100.0) for p in picks})
    out = B.board(tab="dual_momentum", limit=80, min_tier="any", sort="nearest_demand")
    order = [t["symbol"] for t in out["tiles"]]
    assert order == ["INN", "INT", "TIE", "INF", "UNK", "SWP", "BRK", "NOB"]
    keys = [DMT.nearest_demand_key(t["dm_zone"], t["dual_momentum"]["rank"], t["symbol"])
            for t in out["tiles"]]
    assert keys == sorted(keys)
    assert out["sort"] == "nearest_demand" and not out.get("sort_unavailable")
    again = B.board(tab="dual_momentum", limit=80, min_tier="any", sort="nearest_demand")
    assert [t["symbol"] for t in again["tiles"]] == order          # stable
    # the order decides which tiles reach the page (pre-cut)
    cut = B.board(tab="dual_momentum", limit=2, min_tier="any", sort="nearest_demand")
    assert [t["symbol"] for t in cut["tiles"]] == ["INN", "INT"]
    assert "nearest demand first" in cut["dual_momentum_board"]["header"]


def test_08_NEG_no_band_anywhere_keeps_rank_and_says_so(dm_board):
    picks = [_pick("AAA", 1), _pick("BBB", 2), _pick("CCC", 3)]
    docs = {s: _doc(None, [(130.0, 131.0)]) for s in ("AAA", "BBB", "CCC")}
    dm_board["seed"](picks, docs, {p["symbol"]: _snap(100.0) for p in picks})
    out = B.board(tab="dual_momentum", limit=80, min_tier="any", sort="nearest_demand")
    assert [t["symbol"] for t in out["tiles"]] == ["AAA", "BBB", "CCC"]
    assert out["sort_unavailable"] == DMT.NEAREST_SORT_UNAVAILABLE


def test_08_nearest_key_pure_shape():
    assert DMT.nearest_demand_key({"demand": None}, 3, "X") == (4, 0.0, 3, "X")
    z = {"demand": {"distance_pct": 1.5}, "floor": "swept"}
    assert DMT.nearest_demand_key(z, 3, "X") == (2, 1.5, 3, "X")
    assert DMT.rank_key(2, "B") < DMT.rank_key(2, "C") < DMT.rank_key(3, "A")


# --------------------------------------------------------------------------
# 9 — the sort is tab-scoped
# --------------------------------------------------------------------------
def test_09_sorts_on_the_tab(dm_board):
    _std(dm_board)
    out = B.board(tab="dual_momentum", limit=80, sort="nearest_demand", min_tier="any")
    assert out["sort"] == "nearest_demand"
    assert out["sorts"][0] == {"key": "default", "label": DMT.DEFAULT_SORT_LABEL}
    assert out["sorts"][1] == {"key": "nearest_demand", "label": DMT.NEAREST_SORT_LABEL}
    keys = [s["key"] for s in out["sorts"]]
    assert "band_structure" in keys and keys.count("nearest_demand") == 1
    assert out["dual_momentum_board"]["sort"] == "nearest_demand"
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    assert out["sort"] == "default"


def test_09_NEG_no_other_tab_offers_or_honours_nearest_demand(monkeypatch):
    assert "nearest_demand" not in B.SORTS
    stub = lambda *a, **k: {"tiles": []}                   # noqa: E731
    for name in ("zone_tiles", "vcp_tiles", "supply_tiles", "key_level_tiles"):
        monkeypatch.setattr(B, name, stub)
    for tab in ("zones", "vcp", "supply", "key_levels"):
        out = B.board(tab=tab, sort="nearest_demand")
        assert out["sort"] == B.DEFAULT_SORT, tab
        assert "nearest_demand" not in [s["key"] for s in out["sorts"]], tab


# --------------------------------------------------------------------------
# 10 / 11 — every checkbox's wiring, ONE snapshot
# --------------------------------------------------------------------------
def test_10_checkbox_wiring_in_the_payload(dm_board):
    _std(dm_board)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    assert out["enterable_kind"] == "demand" == EN.KIND_BY_TAB["dual_momentum"]
    assert out["band_structure_kind"] == "demand"
    assert dm_board["kl"] and dm_board["burst"]                        # 🔑 + ⚡
    assert dm_board["gex"] == [(5, "demand")] and out["gex_as_of"] == "2026-09-28"
    assert out["tiers"] and out["disclaimer"] == DMT.DISCLAIMER
    assert dm_board["studies"] == []
    B.board(tab="dual_momentum", limit=80, min_tier="any", studies=True)
    assert dm_board["studies"] == [5]                                  # AMD / fib / …
    # themes_first is forwarded: the theme name leads
    dm_board["themes"]["EEE"] = "space"
    out = B.board(tab="dual_momentum", limit=80, min_tier="any", themes_first=True)
    assert out["tiles"][0]["symbol"] == "EEE"
    assert "theme names lead" in out["dual_momentum_board"]["header"]
    out = B.board(tab="dual_momentum", limit=80, min_tier="any", themes_first=False)
    assert out["tiles"][0]["symbol"] == "AAA"


def test_10_liquidity_floor_applies_and_is_counted(dm_board):
    picks = [_pick("AAA", 1), _pick("THN", 2)]
    scan = [{"symbol": "AAA", "last_close": 100.0, "liquidity": {"avg_dollar_vol": 50e6}},
            {"symbol": "THN", "last_close": 100.0, "liquidity": {"avg_dollar_vol": 1e5}}]
    dm_board["seed"](picks, {}, {p["symbol"]: _snap(100.0) for p in picks}, scan)
    out = B.board(tab="dual_momentum", limit=80, min_tier="ok")
    assert [t["symbol"] for t in out["tiles"]] == ["AAA"]
    c = out["dual_momentum_board"]["counts"]
    assert c["dropped_thin"] == 1 and c["shown"] == 1 and c["pool"] == 2 and out["matched"] == 1


def test_11_one_snapshot_per_request(dm_board):
    _std(dm_board)
    B.board(tab="dual_momentum", limit=80, min_tier="any")
    assert dm_board["snap_calls"] == [["AAA", "BBB", "CCC", "DDD", "EEE"]]


def test_11_warming_and_no_scan_payloads(dm_board, monkeypatch, tmp_path):
    DMT._memo.clear()
    out = B.board(tab="dual_momentum", limit=80)
    assert out["warming"] is True and out["tiles"] == []
    assert out["dual_momentum_board"]["state"] == "warming"
    assert out["dual_momentum_board"]["header"] == DMT.WARMING_NOTE
    assert dm_board["snap_calls"] == []
    monkeypatch.setattr(scanner, "LATEST_PATH", tmp_path / "nope.json")
    out = B.board(tab="dual_momentum", limit=80)
    assert out["dual_momentum_board"]["state"] == "no_scan" and out["note"] == DMT.NO_SCAN_NOTE


def test_11_NEG_a_failed_build_payload_is_error_and_never_polls(dm_board, monkeypatch):
    monkeypatch.setattr(DMT, "cached_or_warm",
                        lambda **kw: {"state": "error", "entry": None, "reason": "engine down"})
    out = B.board(tab="dual_momentum", limit=80)
    assert out["tiles"] == [] and not out.get("warming")    # the FE stops polling
    blk = out["dual_momentum_board"]
    assert blk["state"] == "error" and "engine down" in blk["header"]
    assert out["note"] == DMT.error_note("engine down")
    assert DMT.WARMING_NOTE not in (blk["header"], out["note"])
    assert dm_board["snap_calls"] == []


# --------------------------------------------------------------------------
# 12 — the regime never hides a pick
# --------------------------------------------------------------------------
def test_12_regime_label_verbatim_and_never_hides(dm_board):
    label = "DEFENSIVE — SPY 12m return ≤ 0, classic Antonacci says cash/bonds"
    dm_board["regime"] = {"spy_return_12m": -3.25, "risk_on": False, "label": label}
    _std(dm_board)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    blk = out["dual_momentum_board"]
    assert label in blk["regime_line"] and "SPY 12m -3.25%" in blk["regime_line"]
    assert len(out["tiles"]) == 5                           # NEGATIVE: nothing hidden


def test_12_NEG_spy_missing_and_regime_missing_never_raise(dm_board):
    dm_board["regime"] = {"spy_return_12m": None, "risk_on": False, "label": "DEFENSIVE"}
    _std(dm_board)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    assert "SPY 12m —" in out["dual_momentum_board"]["regime_line"]
    assert len(out["tiles"]) == 5
    assert DMT.regime_line(None) == f"{DMT.MARK} regime unavailable"
    assert DMT.regime_line("junk") == f"{DMT.MARK} regime unavailable"
    assert "SPY 12m —" in DMT.regime_line({"spy_return_12m": float("nan"), "label": "x"})


# --------------------------------------------------------------------------
# 13 — hygiene
# --------------------------------------------------------------------------
def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _strings(v)


def test_13_json_clean_no_forbidden_word_unmeasured(dm_board):
    _std(dm_board)
    for srt in ("default", "nearest_demand"):
        out = B.board(tab="dual_momentum", limit=80, min_tier="any", sort=srt)
        json.dumps(out, allow_nan=False)
        for s in _strings(out):
            assert not re.search("bounc", s, re.I), s
            assert "nan" != s.lower() and "[object" not in s
        assert "UNMEASURED" in out["note"] and out["dual_momentum_board"]["measured"] is False
        assert "UNMEASURED" in out["dual_momentum_board"]["note"]
    for s in (DMT.NOTE, DMT.WARMING_NOTE, DMT.NO_SCAN_NOTE, DMT.EMPTY_NOTE, DMT.DISCLAIMER,
              DMT.NEAREST_SORT_UNAVAILABLE, DMT.NO_BAND_TEXT, DMT.NO_DOC_TEXT, DMT.NO_PRINT_TEXT,
              DMT.DEFAULT_SORT_LABEL, DMT.NEAREST_SORT_LABEL):
        assert not re.search("bounc", s, re.I)
    assert DMT.MEASURED is False


def test_13_SOURCE_GUARD_writes_nothing_and_never_says_it():
    src = (BACKEND / "chart_maps" / "dual_momentum_tab.py").read_text(encoding="utf-8")
    code = src.replace("bounce_room", "")
    assert not re.search("bounc", code, re.I)
    assert not re.search(r"insert_|update_one|update_many|replace_|delete_|bulk_write|"
                         r"create_index|open\(|write_text", src)
    assert "UNMEASURED" in src
    assert "from chart_maps import board" not in src and "import board" not in src
    assert DMT.MARK == "\U0001F3CE️"


def test_13_empty_pool_says_so(dm_board):
    dm_board["seed"]([], {}, {}, rows=[{"symbol": "LOSER", "abs_mom_pass": False}])
    out = B.board(tab="dual_momentum", limit=80)
    assert out["tiles"] == [] and out["note"] == DMT.EMPTY_NOTE
    assert out["dual_momentum_board"]["counts"]["pool"] == 0


# --------------------------------------------------------------------------
# 14 — the parity fixture
# --------------------------------------------------------------------------
def test_14_kind_by_tab_and_the_fixture_carry_the_tab():
    fix = json.loads((BACKEND / "tests" / "fixtures" / "enterable_mirror_2026_09_15.json")
                     .read_text(encoding="utf-8"))
    assert EN.KIND_BY_TAB["dual_momentum"] == EN.KIND_DEMAND
    assert fix["kind_by_tab"]["dual_momentum"] == "demand"
    assert fix["kind_by_tab"] == EN.KIND_BY_TAB


# --------------------------------------------------------------------------
# 15 — the memo is never mutated
# --------------------------------------------------------------------------
def test_15_memo_entry_is_never_mutated(dm_board):
    _std(dm_board)
    snap = json.dumps(DMT._memo["entry"], sort_keys=True, default=str)
    out1 = B.board(tab="dual_momentum", limit=80, min_tier="any", studies=True)
    B.board(tab="dual_momentum", limit=80, min_tier="any", sort="nearest_demand", studies=True)
    assert json.dumps(DMT._memo["entry"], sort_keys=True, default=str) == snap
    # NEGATIVE: mutating a served tile never reaches the memo
    out1["tiles"][0]["dual_momentum"]["rank"] = 999
    out1["tiles"][0]["stats"][0]["v"] = "tampered"
    out1["tiles"][0]["name"] = "tampered"
    # the served regime block is the one nested dict the entry hands through
    out1["dual_momentum_board"]["regime"]["label"] = "tampered"
    out1["dual_momentum_board"]["regime"]["spy_return_12m"] = -99.0
    assert json.dumps(DMT._memo["entry"], sort_keys=True, default=str) == snap
    assert DMT._memo["entry"]["picks"][0]["rank"] == 1


# --------------------------------------------------------------------------
# 16 — the board attachers reach every leader (LIVE step 2026-09-29)
# --------------------------------------------------------------------------
# Found on the branch API: the tile skeleton spread tile_metrics' own
# `explosive: None` / `band_structure: None` onto every tile, and both
# attachers skip by KEY PRESENCE, so 80/80 leaders served no 🪜 read and no 🧨
# read and the 🪜 / 🧨 sorts were silently inert.
def test_16_band_structure_and_explosive_attachers_reach_every_leader(dm_board, monkeypatch):
    _std(dm_board)
    seen = {}

    def explosive_spy(tiles):
        # the real attacher's own presence rule, recorded on the FIRST call
        # (board() calls it again post-cut as a no-op for the ledger tabs)
        seen.setdefault("explosive", []).extend(t["symbol"] for t in tiles if "explosive" not in t)
        for t in tiles:
            t.setdefault("explosive", None)
        return 0

    monkeypatch.setattr(B, "attach_explosive", explosive_spy)
    monkeypatch.setattr(B, "attach_band_structure", _REAL_ATTACH_BS)
    monkeypatch.setattr(B, "band_structure_coverage", _REAL_BS_COVERAGE)
    out = B.board(tab="dual_momentum", limit=80, min_tier="any")
    assert sorted(seen["explosive"]) == ["AAA", "BBB", "CCC", "DDD", "EEE"]
    bs = {t["symbol"]: t.get("band_structure") for t in out["tiles"]}
    assert bs["AAA"] and bs["AAA"]["applicable"] is True and bs["AAA"]["stat"]
    assert out["band_structure_coverage"]["tiles_with_read"] >= 1
    # NEGATIVE: a leader with no stored doc gets NO invented read
    assert bs["EEE"] is None


def test_16_NEG_only_the_two_attacher_keys_are_withheld_from_the_tile(dm_board):
    _std(dm_board)
    captured = []
    real_finish = B._finish

    def finish_spy(tiles, *a, **k):
        captured.extend(copy.deepcopy(t) for t in tiles)
        return real_finish(tiles, *a, **k)

    import pytest as _pt
    mp = _pt.MonkeyPatch()
    try:
        mp.setattr(B, "_finish", finish_spy)
        B.board(tab="dual_momentum", limit=80, min_tier="any")
    finally:
        mp.undo()
    assert captured
    metric_keys = set(B.tile_metrics({}))
    assert set(B._DM_ATTACH_OWNED) == {"explosive", "band_structure"}
    assert set(B._DM_ATTACH_OWNED) <= metric_keys           # they ARE tile_metrics keys
    for t in captured:
        for k in B._DM_ATTACH_OWNED:
            assert k not in t                               # never pre-set on the tile
            assert k in t["_m"]                             # still a sort column
        # every other metric still rides on the tile, unchanged
        assert metric_keys - set(B._DM_ATTACH_OWNED) <= set(t)
