"""🧘 GG-like on 👀 Gajjala's Watch (spec gglike §3.8 / §4 WP be-serve-watch, 2026-11-27).

Ajay 2026-11-27, verbatim: "find calmer and better setups.. Continue to track the runners we might evolve and find
patterns in the current runners too but I want to make sure we are finding similar setups to Gajjala".

The Watch PRINTS what the 🚩 pass stored on the read doc (`gajjala_reads[...].gg_like`) — it never computes a block:
  * `tags.blocks` → every `setups` item carries `gg_like` = `gg_like.served(from_stamp(stored[setup]))` or None
    (no `keep` handed in: nothing is hidden on the Watch);
  * `payload._roster_gg_like` → a 📅 roster row of a carded name gains `gg_like` = {setup, label, **row_chip} from ONE
    projected find (🎾 first, else the first carded setup).

NEGATIVES: no stored block → None (never computed, never invented); a malformed / other-setup block → None; an uncarded
name → `tags` None as today; no projection holds a tile key; an uncarded runner has no key; a raising read leaves every
roster row byte-equal; the `only` poll runs no roster read.
"""
from __future__ import annotations

import copy
import json

import pytest

from chart_maps.gajjala import gg_like as GL
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import runseat as RS
from chart_maps.gajjala_watch import sections as SEC
from chart_maps.gajjala_watch import tags as TG
from tests.test_gajjala_watch_tags_2026_11_18 import (FRI, SESSION, World, _omh_world, _r, _read, _rows, _set,
                                                     stubs)  # noqa: F401 — autouse fixture

RS_K, KF_K = "reversal_squeeze", "kiss_fly"
assert RS_K == SEC.RS_SETUP

# §3.3 — the stored / frozen block shape (the real DKI read of 11-25)
DKI = {"v": 1, "setup": RS_K, "frame": "5m", "as_of": "2026-11-25 20:00", "entry_bar_t": "2026-11-25 16:50",
       "verdict": "not", "failed": ["near_high", "tennis_drop", "ema_hold"], "unknown": [],
       "checks": [{"key": "base_bars", "ok": True, "value": 9, "need": 4},
                  {"key": "near_high", "ok": False, "value": 22.7, "need": 15.0, "high": 1.6699, "tight": False},
                  {"key": "tennis_drop", "ok": False, "value": [6.6, 8.4], "need": 15.0},
                  {"key": "ema_hold", "ok": False, "value": 6, "need": "slow", "bars": 9},
                  {"key": "lower_highs", "ok": None, "info": True, "value": None, "why": "few_swings"}]}
KF_OK = {"v": 1, "setup": KF_K, "frame": "5m", "as_of": "2026-11-13 10:30", "entry_bar_t": "2026-11-13 10:25",
         "verdict": "gg_like", "failed": [], "unknown": [],
         "checks": [{"key": "base_bars", "ok": True, "value": 5, "need": 3},
                    {"key": "near_high", "ok": True, "value": 2.0, "need": 15.0, "high": 2.6, "tight": True},
                    {"key": "ema_hold", "ok": True, "value": 0, "need": "fast", "bars": 5}]}


def _blk(b, **kw):
    return dict(copy.deepcopy(b), **kw)


def _gl_read(sym, setups, gg_like=None, **kw):
    d = _read(sym, setups, **kw)
    if gg_like is not None:
        d["gg_like"] = gg_like
    return d


def _want(stored):
    return GL.served(GL.from_stamp(stored))


def _never_compute(monkeypatch):
    """Every computing entry point of the engine raises — the Watch must not reach any of them."""
    def boom(*a, **k):
        raise AssertionError("the Watch computed a block")
    for name in ("block", "doc_blocks", "block_of", "tag"):
        if hasattr(GL, name):
            monkeypatch.setattr(GL, name, boom)


def test_the_fixture_blocks_pass_the_engines_own_shape_guard():
    assert GL.from_stamp(copy.deepcopy(DKI)) is not None and GL.from_stamp(copy.deepcopy(KF_OK)) is not None
    assert _want(DKI)["verdict"] == "not" and _want(KF_OK)["verdict"] == "gg_like"


# ── 🏷️ tags: the setups items ────────────────────────────────────────────────────────────────────────────────────
def test_a_carded_name_serves_the_stored_block_per_setup(monkeypatch):
    _never_compute(monkeypatch)
    stored = {RS_K: _blk(DKI), KF_K: _blk(KF_OK)}
    w = _set(monkeypatch, _omh_world(reads=[_gl_read("OMH", {RS_K: _r("forming", at=None), KF_K: _r("forming")},
                                                     stored)]))
    t = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]
    by = {s["setup"]: s for s in t["setups"]}
    assert set(by) == {RS_K, KF_K}
    assert by[RS_K]["gg_like"] == _want(DKI) and by[KF_K]["gg_like"] == _want(KF_OK)
    assert by[RS_K]["gg_like"]["verdict"] == "not" and by[KF_K]["gg_like"]["verdict"] == "gg_like"
    assert by[RS_K]["gg_like"]["keep"] is False and by[KF_K]["gg_like"]["keep"] is False   # no keep on the Watch
    rows, out = _rows()
    assert {s["setup"]: s["gg_like"] for s in rows["OMH"]["tags"]["setups"]} == {RS_K: _want(DKI), KF_K: _want(KF_OK)}
    json.dumps(out, ensure_ascii=False, allow_nan=False)


def test_NEGATIVE_a_rang_read_still_serves_keep_false_nothing_is_hidden_on_the_watch(monkeypatch):
    w = _set(monkeypatch, _omh_world(reads=[_gl_read("OMH", {RS_K: _r("aplus")}, {RS_K: _blk(DKI)})]))
    item = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]["setups"][0]
    assert item["gg_like"] == GL.served(GL.from_stamp(DKI), keep=False) and item["gg_like"]["keep"] is False


def test_NEGATIVE_no_stored_block_serves_none_never_computed(monkeypatch):
    _never_compute(monkeypatch)
    w = _set(monkeypatch, _omh_world(reads=[_read("OMH", {RS_K: _r("forming", at=None), KF_K: _r("forming")})]))
    t = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]
    assert [s["gg_like"] for s in t["setups"]] == [None, None]
    # one setup stored, the other not → None for the other only (never borrowed, never invented)
    w = _set(monkeypatch, _omh_world(reads=[_gl_read("OMH", {RS_K: _r("forming", at=None), KF_K: _r("forming")},
                                                     {KF_K: _blk(KF_OK)})]))
    by = {s["setup"]: s["gg_like"] for s in TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]["setups"]}
    assert by == {RS_K: None, KF_K: _want(KF_OK)}


@pytest.mark.parametrize("bad", [
    "not a dict", ["a", "list"], 7, {},
    _blk(DKI, verdict="maybe"),                                                  # a foreign verdict
    _blk(DKI, v=True),                                                           # a bool `v`
    _blk(DKI, checks=[{"key": "base_bars", "ok": "yes", "value": 9, "need": 4}]),  # ok = "yes"
    _blk(DKI, checks="nope"),
    _blk(DKI, setup=KF_K),                                                       # a block of ANOTHER setup
])
def test_NEGATIVE_a_malformed_stored_block_serves_none(monkeypatch, bad):
    w = _set(monkeypatch, _omh_world(reads=[_gl_read("OMH", {RS_K: _r("forming", at=None)}, {RS_K: bad})]))
    t = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]
    assert t["on_board"] is True and t["setups"][0]["gg_like"] is None


@pytest.mark.parametrize("stored", ["a string", ["list"], 3])
def test_NEGATIVE_a_malformed_gg_like_key_serves_none(monkeypatch, stored):
    w = _set(monkeypatch, _omh_world(reads=[_gl_read("OMH", {RS_K: _r("forming", at=None)}, stored)]))
    assert TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]["setups"][0]["gg_like"] is None


def test_NEGATIVE_a_raising_engine_costs_that_item_only(monkeypatch):
    w = _set(monkeypatch, _omh_world(reads=[_gl_read("OMH", {RS_K: _r("forming", at=None)}, {RS_K: _blk(DKI)})]))
    monkeypatch.setattr(GL, "served", lambda *a, **k: 1 / 0)
    t = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]
    assert t["on_board"] is True and t["setups"][0]["gg_like"] is None and t["setups"][0]["state"] == "forming"
    assert set(t) == set(TG.TAGS_KEYS)


def test_NEGATIVE_an_uncarded_name_with_a_stored_block_still_serves_tags_none(monkeypatch):
    _set(monkeypatch, _omh_world(reads=[_gl_read("OMH", {RS_K: _r("none")}, {RS_K: _blk(DKI)})]))
    rows, _ = _rows()
    assert rows["OMH"]["tags"] is None and rows["NVDA"]["tags"] is None


def test_the_projection_reads_the_stored_block_and_never_the_tile(monkeypatch):
    w = _set(monkeypatch, _omh_world())
    _rows()
    ids = [ST.key(SESSION, "OMH"), ST.key(SESSION, "NVDA")]
    assert w.c[ST.READS].finds == [({"_id": {"$in": ids}}, TG.TAGS_READ_FIELDS)]
    for fields in (TG.TAGS_READ_FIELDS, PL.ROSTER_GG_LIKE_FIELDS):
        assert fields.get("gg_like") == 1
        assert not [k for k in fields if k == "tile" or k.startswith("tile.")]
    assert set(PL.ROSTER_GG_LIKE_FIELDS) == {"symbol", "setups", "gg_like"}


# ── 📅 roster row chip ───────────────────────────────────────────────────────────────────────────────────────────
def _roster(*syms):
    return {"state": "ok", "rows": [{"symbol": s, "day_text": "📅 day", "seat_text": "+1% day"} for s in syms]}


def _roster_world(monkeypatch, fail=False):
    reads = [
        _gl_read("OMH", {KF_K: _r("forming"), RS_K: _r("forming", at=None)}, {RS_K: _blk(DKI), KF_K: _blk(KF_OK)}),
        _gl_read("POM", {KF_K: _r("forming")}, {KF_K: _blk(KF_OK)}),
        _gl_read("NVDA", {RS_K: _r("none")}, {RS_K: _blk(DKI)}),              # not carded today
        _gl_read("GP", {RS_K: _r("forming", at=None)}),                     # carded, no stored block
    ]
    return _set(monkeypatch, World(reads=reads, fail=((ST.READS,) if fail else ())))


def _chip(stored, k):
    return {"setup": k, "label": tab._setup_label(k), **GL.row_chip(GL.from_stamp(stored), source="read")}


def test_roster_a_carded_runner_gains_the_chip_of_its_reversal_squeeze_read_first(monkeypatch):
    _never_compute(monkeypatch)
    w = _roster_world(monkeypatch)
    ro = _roster("OMH", "POM", "NVDA", "GP", "ZZZ")
    PL._roster_gg_like(ro, SESSION)
    by = {r["symbol"]: r for r in ro["rows"]}
    assert by["OMH"]["gg_like"] == _chip(DKI, RS_K)                 # 🎾 first although kiss & fly is carded too
    assert by["POM"]["gg_like"] == _chip(KF_OK, KF_K)               # else the first carded setup
    assert by["OMH"]["gg_like"]["source"] == "read"
    ids = [ST.key(SESSION, s) for s in ("OMH", "POM", "NVDA", "GP", "ZZZ")]
    assert w.c[ST.READS].finds == [({"_id": {"$in": ids}}, PL.ROSTER_GG_LIKE_FIELDS)]     # ONE projected find
    json.dumps(ro, ensure_ascii=False, allow_nan=False)


def test_NEGATIVE_roster_uncarded_unread_and_blockless_runners_have_no_key(monkeypatch):
    _roster_world(monkeypatch)
    ro = _roster("NVDA", "GP", "ZZZ")
    before = copy.deepcopy(ro)
    PL._roster_gg_like(ro, SESSION)
    assert ro == before and all("gg_like" not in r for r in ro["rows"])


def test_NEGATIVE_roster_a_raising_read_leaves_every_row_byte_equal(monkeypatch):
    _roster_world(monkeypatch, fail=True)
    ro = _roster("OMH", "POM", "NVDA")
    before = json.dumps(ro, ensure_ascii=False, sort_keys=True)
    PL._roster_gg_like(ro, SESSION)
    assert json.dumps(ro, ensure_ascii=False, sort_keys=True) == before


def test_NEGATIVE_roster_a_fault_mid_rows_adds_no_key_on_any_row(monkeypatch):
    _roster_world(monkeypatch)
    calls = {"n": 0}
    real = GL.row_chip

    def flaky(blk, **kw):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("mid-roster fault")
        return real(blk, **kw)
    monkeypatch.setattr(GL, "row_chip", flaky)
    ro = _roster("OMH", "POM")
    before = copy.deepcopy(ro)
    PL._roster_gg_like(ro, SESSION)
    assert calls["n"] == 2 and ro == before                         # the first chip was computed, never assigned


@pytest.mark.parametrize("roster", [None, {"state": "unreadable", "text": "x", "rows": []}, {"state": "ok", "rows": []},
                                    "junk"])
def test_NEGATIVE_roster_with_no_rows_reads_nothing(monkeypatch, roster):
    w = _roster_world(monkeypatch)
    before = copy.deepcopy(roster)
    PL._roster_gg_like(roster, SESSION)
    assert w.c[ST.READS].finds == [] and roster == before


def test_roster_through_build_and_the_only_poll_reads_nothing_new(monkeypatch):
    seen = []
    monkeypatch.setattr(PL, "_roster_gg_like", lambda ro, siso: seen.append((ro, siso)))
    monkeypatch.setattr(RS, "roster", lambda *a, **k: _roster("OMH"))
    monkeypatch.setattr(RS, "tags_for", lambda *a, **k: {})
    _set(monkeypatch, _omh_world())
    _rows(only=["OMH"])
    assert seen == []                                                # the pending poll: no roster, no roster read
    _, out = _rows()
    assert len(seen) == 1 and seen[0][1] == SESSION and seen[0][0] is out["runners"]


def test_roster_through_build_serves_the_chip_on_the_board(monkeypatch):
    monkeypatch.setattr(RS, "roster", lambda *a, **k: _roster("OMH", "NVDA"))
    monkeypatch.setattr(RS, "tags_for", lambda *a, **k: {})
    _set(monkeypatch, _omh_world(reads=[_gl_read("OMH", {RS_K: _r("forming", at=None)}, {RS_K: _blk(DKI)})]))
    _, out = _rows()
    by = {r["symbol"]: r for r in out["runners"]["rows"]}
    assert by["OMH"]["gg_like"] == _chip(DKI, RS_K) and "gg_like" not in by["NVDA"]
    json.dumps(out, ensure_ascii=False, allow_nan=False)
