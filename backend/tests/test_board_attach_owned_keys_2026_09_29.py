"""Attacher-owned keys never ride a flat `tile_metrics` spread (2026-09-29).

Found live 2026-09-29: `key_level_tiles` (🔑 Key Levels) and
`turning_bullish_tiles` (🌀 AMD, Keltner) spread `tile_metrics` FLAT onto each
tile, which carried its always-None `explosive` and `band_structure` columns
onto the tile. `attach_explosive` / `attach_band_structure` are idempotent by
KEY PRESENCE, so they skipped every tile: the three tabs served no 🧨 and no
🪜 read, and both sorts fell to an all-None column (the payload said "No
demand-band read for these names" and ordered A, AA, AAL…).

The fix: `board.ATTACH_OWNED_KEYS` + `board.published_metrics`, the ONE filter
every flat spread goes through. `_m` keeps every column for the sorts.

Positive AND negative cases. Stubs only — no Mongo, no network.
"""
from __future__ import annotations

import ast
import inspect
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps import board as B
from chart_maps import key_levels_tab as KLT
from supply_demand import band_structure as BS
from supply_demand import enterable as EN
from supply_demand import explosive as EX
from supply_demand import key_levels as KL
from supply_demand import turning_bullish as TBm
from supply_demand import zone_store

ET = ZoneInfo("America/New_York")
BOARD_SRC = Path(B.__file__).read_text()
NOW = datetime(2026, 9, 29, 11, 0, tzinfo=ET)
SYMS = ("AAA", "BBB", "ZZZ")           # ZZZ is LAST in every default order below
TABS = ("key_levels", "amd", "keltner")

EXPL_READ = {"score": None, "grade": None, "intact": True,
             "room": {"state": "CLEAR"}, "components": []}
BS_READ = {"applicable": True, "score": None, "stat": "stub",
           "ceiling": {"state": "CLEAR"}, "floor": {}}


# --------------------------------------------------------------------------
# 1. the tuple and the filter
# --------------------------------------------------------------------------
def test_owned_keys_are_tile_metrics_columns_that_are_always_None():
    m = B.tile_metrics({})
    assert B.ATTACH_OWNED_KEYS == ("explosive", "band_structure")
    for k in B.ATTACH_OWNED_KEYS:
        assert k in m and m[k] is None
    # the richest row still leaves them None — the attachers own the value
    rich = B.tile_metrics({"liquidity": {"avg_dollar_vol": 5e7, "rvol": 2.0},
                           "rs_rank": 90, "last_close": 10.0})
    assert all(rich[k] is None for k in B.ATTACH_OWNED_KEYS)


def test_owned_keys_are_exactly_the_attachers_idempotence_keys():
    """Each key is the one its attacher checks by presence — the reason a flat
    None on the tile silences it."""
    assert '"explosive" not in t' in inspect.getsource(B.attach_explosive)
    assert '"band_structure" not in t' in inspect.getsource(B.attach_band_structure)


def test_published_metrics_drops_only_the_owned_keys_and_never_mutates():
    m = B.tile_metrics({"liquidity": {"avg_dollar_vol": 5e7}, "rs_rank": 80})
    before = json.dumps(m, sort_keys=True)
    pub = B.published_metrics(m)
    assert json.dumps(m, sort_keys=True) == before          # untouched: `_m` needs it
    assert not set(pub) & set(B.ATTACH_OWNED_KEYS)
    assert pub == {k: v for k, v in m.items() if k not in B.ATTACH_OWNED_KEYS}
    assert set(pub) | set(B.ATTACH_OWNED_KEYS) == set(m)


def test_NEGATIVE_published_metrics_on_None_empty_and_a_non_None_owned_value():
    assert B.published_metrics(None) == {}
    assert B.published_metrics({}) == {}
    # even a populated value is dropped — the attacher, not the builder, owns it
    assert B.published_metrics({"explosive": {"x": 1}, "band_structure": 1,
                                "rvol": 2.0}) == {"rvol": 2.0}


# --------------------------------------------------------------------------
# 2. source guard: no flat tile_metrics spread anywhere in board.py
# --------------------------------------------------------------------------
def _call_name(v) -> str:
    """`f` for `f(...)` and `B.f(...)`; "" for anything else."""
    if isinstance(v, ast.Call):
        if isinstance(v.func, ast.Name):
            return v.func.id
        if isinstance(v.func, ast.Attribute):
            return v.func.attr
    return ""


def _flat_metric_spreads(src: str) -> list:
    """Line numbers of flat spreads that can carry `tile_metrics` columns onto a
    tile without going through `published_metrics`:
      * `**tile_metrics(...)` / `**X.tile_metrics(...)` in any dict literal
        (except as the value of the `_m` key);
      * `**m` in any dict literal (the builders' local name for the metrics);
      * ANY flat `**` spread in a dict literal that also has an `_m` key — a
        tile — whatever the spread expression is called;
      * `.update(tile_metrics(...))` / `.update(m)`."""
    tree = ast.parse(src)
    allowed = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "_m" and isinstance(v, ast.Dict):
                    allowed.add(id(v))
    bad = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "update" and node.args):
            a = node.args[0]
            if _call_name(a) == "tile_metrics" or (isinstance(a, ast.Name) and a.id == "m"):
                bad.append(a.lineno)
            continue
        if not isinstance(node, ast.Dict) or id(node) in allowed:
            continue
        is_tile = any(isinstance(k, ast.Constant) and k.value == "_m" for k in node.keys)
        for k, v in zip(node.keys, node.values):
            if k is not None or _call_name(v) == "published_metrics":
                continue
            if (is_tile or _call_name(v) == "tile_metrics"
                    or (isinstance(v, ast.Name) and v.id == "m")):
                bad.append(v.lineno)
    return bad


def test_SOURCE_GUARD_every_flat_spread_goes_through_published_metrics():
    assert _flat_metric_spreads(BOARD_SRC) == []
    assert BOARD_SRC.count("**published_metrics(") >= 2


def test_NEGATIVE_the_guard_catches_both_spread_shapes_and_allows_the_m_column():
    assert _flat_metric_spreads('x = {"a": 1, **tile_metrics(r)}') == [1]
    assert _flat_metric_spreads('x = {"a": 1,\n **m}') == [2]
    assert _flat_metric_spreads('x = {"_m": {**tile_metrics(r)}}') == []
    assert _flat_metric_spreads('x = {**published_metrics(m), "_m": dict(m)}') == []


def test_NEGATIVE_the_guard_catches_the_renamed_and_indirect_spreads():
    """The four shapes the critic showed slipping past the first guard."""
    assert _flat_metric_spreads('x = {"a": 1, **metrics, "_m": metrics}') == [1]
    assert _flat_metric_spreads('x = {**dict(m), "_m": dict(m)}') == [1]
    assert _flat_metric_spreads('x = {"a": 1, **B.tile_metrics(r)}') == [1]
    assert _flat_metric_spreads('x.update(tile_metrics(r))') == [1]
    assert _flat_metric_spreads('x.update(m)') == [1]
    # still allowed: a non-tile dict spreading something unrelated, and an
    # attribute-qualified published_metrics on a tile
    assert _flat_metric_spreads('x = {**defaults, "a": 1}') == []
    assert _flat_metric_spreads('x = {**B.published_metrics(m), "_m": dict(m)}') == []
    assert _flat_metric_spreads('x.update(other)') == []


# --------------------------------------------------------------------------
# 3. the three affected builders, end to end with the real attachers
# --------------------------------------------------------------------------
def _theme(sym):
    return None


@pytest.fixture
def stores(monkeypatch):
    """The two read stores behind the real attachers. `has` = which symbols
    come back with a read (both reads)."""
    state = {"has": {"ZZZ"}, "expl_calls": [], "bs_calls": []}
    real_bs_read = BS.read

    def _load_latest(syms):
        return "2026-09-29", {s: {"symbol": s} for s in syms}

    def _expl(**kw):
        state["expl_calls"].append(kw["symbol"])
        return dict(EXPL_READ) if kw["symbol"] in state["has"] else None

    def _bs(**kw):
        state["bs_calls"].append((kw["symbol"], kw.get("kind")))
        if kw.get("kind") == EN.KIND_NA:
            return real_bs_read(**kw)                   # the honest n/a read, unstubbed
        return dict(BS_READ) if kw["symbol"] in state["has"] else None

    monkeypatch.setattr(zone_store, "load_latest", _load_latest)
    monkeypatch.setattr(EX, "read", _expl)
    monkeypatch.setattr(EX, "SELECTED", ())
    monkeypatch.setattr(BS, "read", _bs)
    return state


@pytest.fixture
def builders(monkeypatch, stores):
    """Every I/O leg of `key_level_tiles` / `turning_bullish_tiles` replaced by
    a double; `_finish` and both attachers run for real. `seen` holds the
    tiles as the builder handed them to `_finish`."""
    from sepa import prices, scanner
    seen = {"tiles": []}
    real_finish = B._finish

    def _finish_spy(tiles, *a, **k):
        seen["tiles"] = [dict(t, _m=dict(t.get("_m") or {})) for t in tiles]
        return real_finish(tiles, *a, **k)

    def _bars(tiles, days, **k):
        for t in tiles:
            t["bars"] = [{"t": "2026-09-28", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]

    def _tb(kind, limit=120, db=None, grades=None):
        rows = [{"symbol": s, "last_close": 10.0 + i,
                 kind: {"base_lo": 9.0, "base_hi": 11.0, "grade": "raided"}}
                for i, s in enumerate(SYMS)]
        return {"kind": kind, "rows": rows, "n": 3, "n_all": 3, "n_rows": 3,
                "n_scanned": 3, "counts": {}, "grades": [], "grades_all": [],
                "grade_counts": {}, "params": {}, "built_at": None}

    near = {s: {"text": f"{s} near", "distance_pct": d, "period": "PWL"}
            for s, d in zip(SYMS, (0.5, 1.0, 4.0))}      # ZZZ farthest -> last
    ranked = [{"symbol": s, "ref_close": 10.0, "avg_dollar_vol_50": 5e7, "near": near[s]}
              for s in SYMS]
    counts = {k: 0 for k in KLT.COUNT_KEYS}
    counts.update(scanned=3, ranked=3)

    monkeypatch.setattr(KLT, "cached_or_warm", lambda u, now=None, sync=False: {
        "state": "ready", "entry": {"syms": list(SYMS), "session": "2026-09-29",
                                    "built_at": None}})
    monkeypatch.setattr(KLT, "rank", lambda entry, raw, now, first_seen: (
        [dict(r) for r in ranked], dict(counts)))
    monkeypatch.setattr(KL, "read_first_seen", lambda s, coll=None: {})
    monkeypatch.setattr(TBm, "board", _tb)
    monkeypatch.setattr(B, "_bulk_snaps", lambda syms: {})
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": [
        {"symbol": s, "liquidity": {"avg_dollar_vol": 5e7}} for s in SYMS]})
    monkeypatch.setattr(B, "bars_for", lambda sym, days=130, **k: [
        {"t": "2026-09-28", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}])
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: None)
    monkeypatch.setattr(B, "_keltner_curves", lambda tile, df: None)
    monkeypatch.setattr(B, "_session_day", lambda *a, **k: date(2026, 9, 29))
    monkeypatch.setattr(B, "_attach_bars", _bars)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)
    monkeypatch.setattr(B, "_name_for", lambda s: f"{s} Inc")
    monkeypatch.setattr(B, "_theme", _theme)
    monkeypatch.setattr(B, "_finish", _finish_spy)
    return seen


def _build(tab, sort=B.DEFAULT_SORT):
    if tab == "key_levels":
        return B.key_level_tiles(24, 130, "full", sort=sort, min_tier="any", now=NOW)
    return B.turning_bullish_tiles(tab, limit=24, sort=sort)


@pytest.mark.parametrize("tab", TABS)
def test_the_builder_hands_finish_no_flat_owned_key_but_keeps_them_in_m(builders, tab):
    _build(tab)
    assert len(builders["tiles"]) == 3
    for t in builders["tiles"]:
        assert not set(t) & set(B.ATTACH_OWNED_KEYS)
        for k in B.ATTACH_OWNED_KEYS:
            assert k in t["_m"]                          # the sort columns survive
        # every OTHER metric is still published flat, value for value
        for k, v in B.published_metrics(t["_m"]).items():
            assert t[k] == v


@pytest.mark.parametrize("tab", TABS)
def test_a_built_tile_gets_a_real_explosive_and_band_structure_read(builders, stores, tab):
    out = _build(tab)
    tiles = out["tiles"]
    kind = BS.kind_for_tab(tab)
    B.attach_band_structure(tiles, kind=kind, live=None)
    by = {t["symbol"]: t for t in tiles}
    assert set(by) == set(SYMS)
    assert sorted(stores["expl_calls"]) == sorted(SYMS)  # the attacher READ every tile
    assert by["ZZZ"]["explosive"] == EXPL_READ
    assert by["AAA"]["explosive"] is None                # store had nothing: honest None
    if kind == EN.KIND_NA:
        # 🔑 Key Levels is not in enterable.KIND_BY_TAB, so its 🪜 read is the
        # honest n/a read — before the fix it was a bare None (no sentence).
        for t in tiles:
            assert t["band_structure"] is not None
            assert t["band_structure"].get("applicable") is not True
    else:
        assert by["ZZZ"]["band_structure"] == BS_READ
        assert by["AAA"]["band_structure"] is None
        assert {"k": B.BAND_STRUCTURE_STAT_KEY, "v": "stub"} in by["ZZZ"]["stats"]


@pytest.mark.parametrize("tab", TABS)
def test_the_explosive_sort_now_reorders(builders, tab):
    default = [t["symbol"] for t in _build(tab)["tiles"]]
    assert default[0] != "ZZZ"                           # else the test proves nothing
    out = _build(tab, sort="explosive")
    assert [t["symbol"] for t in out["tiles"]][0] == "ZZZ"
    assert out["sort_unavailable"] is None


@pytest.mark.parametrize("tab", ("amd", "keltner"))
def test_the_band_structure_sort_now_reorders(builders, tab):
    tiles = _build(tab)["tiles"]
    assert tiles[0]["symbol"] != "ZZZ"
    kind = BS.kind_for_tab(tab)
    B.attach_band_structure(tiles, kind=kind, live=None)
    assert B._band_structure_sort(tiles, kind=kind) is None
    assert tiles[0]["symbol"] == "ZZZ"


def test_NEGATIVE_key_levels_band_structure_sort_stays_the_honest_na_note(builders):
    tiles = _build("key_levels")["tiles"]
    kind = BS.kind_for_tab("key_levels")
    assert kind == EN.KIND_NA
    B.attach_band_structure(tiles, kind=kind, live=None)
    assert B._band_structure_sort(tiles, kind=kind) == B.band_structure_sort_na()


@pytest.mark.parametrize("tab", TABS)
def test_NEGATIVE_no_read_anywhere_still_says_so(builders, stores, tab):
    stores["has"] = set()
    out = _build(tab, sort="explosive")
    assert all(t["explosive"] is None for t in out["tiles"])
    assert out["sort_unavailable"] == B.EXPLOSIVE_SORT_UNAVAILABLE


# --------------------------------------------------------------------------
# 4. the attachers themselves are unchanged
# --------------------------------------------------------------------------
def test_NEGATIVE_key_presence_idempotence_is_kept(stores):
    """The bug's mechanism, pinned so the fix stays at the SPREAD: a tile that
    already carries the key (None is a real answer) is still skipped."""
    pre = {"symbol": "ZZZ", "last_close": 10.0, "explosive": None, "band_structure": None}
    fresh = {"symbol": "ZZZ", "last_close": 10.0}
    B.attach_explosive([pre, fresh])
    B.attach_band_structure([pre, fresh], kind=EN.KIND_DEMAND, live=None)
    assert pre["explosive"] is None and pre["band_structure"] is None
    assert fresh["explosive"] == EXPL_READ and fresh["band_structure"] == BS_READ
    assert stores["expl_calls"] == ["ZZZ"]               # one read, the fresh tile


def test_a_tab_that_was_correct_is_unchanged_an_m_only_tile(stores):
    """Tabs that build `_m` only (zones, vcp, deep_demand, …) never had the
    flat keys; their attach path is byte-identical before and after."""
    tile = {"symbol": "ZZZ", "last_close": 10.0, "_m": B.tile_metrics({})}
    B.attach_explosive([tile])
    assert tile["explosive"] == EXPL_READ and tile["_m"]["explosive"] is None
    assert json.dumps(tile, sort_keys=True) == json.dumps(
        {"symbol": "ZZZ", "last_close": 10.0, "_m": B.tile_metrics({}),
         "explosive": EXPL_READ}, sort_keys=True)
