"""🪜 THE SILENT BLANK on the tile path (critique J2, 2026-09-16).

`chart_maps/board.attach_band_structure` sources its bands from
`zone_store.load_latest` and nothing else. A name the $1B store has not warmed
therefore gets `band_structure: None`, the chip renders nothing — and the two
ONE-CHART surfaces (Support Levels, 📁 My holdings) printed NO REASON at all,
because the served coverage note existed only on the row-board payload.

Demonstrated on BTBT, one of his own positions: 7 holdings, 6 with a store doc,
BTBT with none. The ten row boards served him the read for it (`bounce_room`
builds the doc on demand) while his own holdings tab showed the same name, the
same day, with nothing and no reason.

What is pinned here:
  * the tile path serves `band_structure_coverage`, counts and all;
  * its note IS `bounce_room.BAND_STRUCTURE_NO_READ` — the row boards' own
    sentence, imported, never a second wording for one fact;
  * the note fires ONLY when not one shown tile came back with a read;
  * NEGATIVES: one tile that DID read silences it, an n/a tab never prints it
    (it has its own n/a sentence), an empty board prints no note, a raising
    verdict serves no coverage block at all (the chip may never outlive its
    banner, and neither may its absence notice), and nothing here can raise.

The ON-DEMAND BUILD was NOT taken (critique option a): every tile that missed
the store would cost its own price load on a board that draws up to `limit`
tiles at once. The absence is made VISIBLE instead; the richer fix stays open.
"""
from __future__ import annotations

import inspect
import json

import pytest

from supply_demand import bounce_room as BR
from supply_demand import enterable as EN
from chart_maps import board as B

CRDO_PX = 162.76
CRDO_DEMAND = [(182.61, 189.12), (173.90, 180.10), (161.92, 167.68), (146.34, 151.55)]
CRDO_SUPPLY = [(193.50, 198.97)]


def _band(kind, lo, hi, touches=1, strength=30.0) -> dict:
    return {"kind": kind, "lo": lo, "hi": hi, "touches": touches,
            "strength": strength}


def crdo_doc() -> dict:
    bands = [_band("demand", lo, hi) for lo, hi in CRDO_DEMAND]
    bands += [_band("supply", lo, hi) for lo, hi in CRDO_SUPPLY]
    return {"symbol": "CRDO", "bands": bands, "prev_close": CRDO_PX,
            "atr14": 5.0, "high_252": 200.0}


def _tile(sym, px=CRDO_PX):
    return {"symbol": sym, "last_price": px, "stats": []}


def _patch_store(monkeypatch, docs):
    from supply_demand import zone_store
    monkeypatch.setattr(zone_store, "load_latest",
                        lambda syms=None, coll=None, today=None: (None, dict(docs)),
                        raising=False)


# ═══════════════════════════════════════════════════════════════════════════
# 1 — the helper
# ═══════════════════════════════════════════════════════════════════════════
def test_a_tile_with_NO_READ_says_so_in_the_ROW_BOARDS_OWN_WORDS(monkeypatch):
    """BTBT: a position of his the store has not warmed. It used to draw a
    tile with no Bands line and no reason."""
    _patch_store(monkeypatch, {})
    tiles = [_tile("BTBT")]
    assert B.attach_band_structure(tiles, kind=EN.KIND_DEMAND, live={}) == 0
    cov = B.band_structure_coverage(tiles, kind=EN.KIND_DEMAND)
    assert cov["note"] == BR.BAND_STRUCTURE_NO_READ_ONE
    assert cov["tiles_with_read"] == 0 and cov["tiles_without_read"] == 1


def test_the_sentence_is_IMPORTED_not_a_SECOND_WORDING_for_one_fact():
    """Two wordings for one fact is how the two surfaces drifted apart. The
    source may name the constant; it may not retype the sentence."""
    src = inspect.getsource(B.band_structure_coverage)
    assert "band_structure_no_read_note" in src
    assert "No band read" not in src, "the sentence must be imported, not typed"
    body = src[src.index("shown = "):]          # past the docstring
    for txt in (BR.BAND_STRUCTURE_NO_READ, BR.BAND_STRUCTURE_STILL_WARMING,
                BR.BAND_STRUCTURE_BELOW_CAP_FMT):
        assert " ".join(txt.split()[:4]) not in body, \
            "the tile path may not word the NO-READ / WARMING / BELOW-CAP branch itself"
    for txt in (BR.BAND_STRUCTURE_NO_READ, BR.BAND_STRUCTURE_STILL_WARMING,
                BR.BAND_STRUCTURE_BELOW_CAP_FMT):
        assert "bounc" not in txt.lower(), \
            "reversal, never bounce, on a served string"


def test_NEGATIVE_ONE_tile_that_DID_read_silences_the_note(monkeypatch):
    """NEGATIVE — the row path's own rule: the note is a ZERO-coverage
    statement, not a per-name one. A board where six of seven names read is
    not a board with no band read."""
    _patch_store(monkeypatch, {"CRDO": crdo_doc()})
    tiles = [_tile("CRDO"), _tile("BTBT")]
    assert B.attach_band_structure(tiles, kind=EN.KIND_DEMAND, live={}) == 1
    cov = B.band_structure_coverage(tiles, kind=EN.KIND_DEMAND)
    assert cov["note"] is None
    assert cov["tiles_with_read"] == 1 and cov["tiles_without_read"] == 1


def test_NEGATIVE_an_NA_TAB_never_prints_the_no_read_sentence(monkeypatch):
    """NEGATIVE. An n/a tab carries `band_structure.NA_TEXT` — "no band read
    for this tab, its rows are not price-structure bands". Adding "names the
    store is still warming arrive on the next refresh" beside it would be two
    contradicting sentences about one tab."""
    _patch_store(monkeypatch, {})
    tiles = [_tile("VCPNAME")]
    B.attach_band_structure(tiles, kind=EN.KIND_NA, live={})
    assert tiles[0]["band_structure"]["applicable"] is False
    cov = B.band_structure_coverage(tiles, kind=EN.KIND_NA)
    assert cov["note"] is None
    assert cov["tiles_with_read"] == 0 and cov["tiles_without_read"] == 1


def test_NEGATIVE_an_EMPTY_board_prints_no_note():
    """NEGATIVE — 0DTE outside the session. "No band read for these names" over
    a board with no names on it is a sentence about nothing; the payload-level
    n/a text is that board's line."""
    cov = B.band_structure_coverage([], kind=EN.KIND_DEMAND)
    assert cov == {"tiles_with_read": 0, "tiles_without_read": 0, "note": None}


def test_NEGATIVE_the_coverage_read_can_NEVER_raise(monkeypatch):
    """NEGATIVE — it decorates, so it fails open and silent like every other
    decoration on this path. A board that 500s because a note module moved
    would be the far worse trade."""
    import sys
    import supply_demand
    monkeypatch.delitem(sys.modules, "supply_demand.bounce_room", raising=False)
    monkeypatch.delattr(supply_demand, "bounce_room", raising=False)
    monkeypatch.setitem(sys.modules, "supply_demand.bounce_room", None)
    cov = B.band_structure_coverage([{"symbol": "BTBT"}], kind=EN.KIND_DEMAND)
    assert cov["note"] is None and cov["tiles_without_read"] == 1
    cov = B.band_structure_coverage([None, "junk", {"symbol": "X"}],  # type: ignore[list-item]
                                    kind=EN.KIND_DEMAND)
    assert cov["tiles_without_read"] == 1, "non-dict rows are not tiles"


# ═══════════════════════════════════════════════════════════════════════════
# 2 — the Support endpoint (the payload 📁 My holdings reads, one per position)
# ═══════════════════════════════════════════════════════════════════════════
def _support_payload(monkeypatch, *, docs, verdict_raises=False, symbol="CRDO"):
    import asyncio
    from chart_maps import api as A
    from supply_demand import band_structure as BS

    tile = {"symbol": symbol, "last_price": CRDO_PX, "stats": []}
    monkeypatch.setattr(A.support_mod, "for_symbol",
                        lambda *a, **kw: {"tile": tile, "bars_used": 130,
                                          "timeframe": "daily"})
    monkeypatch.setattr(A.board_mod, "_live_snapshot", lambda tiles: {})
    monkeypatch.setattr(A.board_mod, "attach_live_now",
                        lambda tiles, res, live=None: None)
    monkeypatch.setattr(A.board_mod, "attach_enterable",
                        lambda tiles, kind=None, live=None: 0)
    _patch_store(monkeypatch, docs)
    if verdict_raises:
        monkeypatch.setattr(BS, "measured_verdict",
                            lambda: (_ for _ in ()).throw(RuntimeError("banner down")))
    res = asyncio.run(A.chart_maps_support(symbol=symbol))
    return json.loads(res.body.decode())


def test_the_SUPPORT_payload_SAYS_IT_when_this_name_has_no_read(monkeypatch):
    """The BTBT case end to end. One tile on this endpoint, so the zero-
    coverage rule fires exactly when THIS name came back with nothing."""
    p = _support_payload(monkeypatch, docs={}, symbol="BTBT")
    assert p["tile"].get("band_structure") is None
    assert p["band_structure_coverage"]["note"] == BR.BAND_STRUCTURE_NO_READ_ONE
    assert p["band_structure_coverage"]["tiles_with_read"] == 0


def test_NEGATIVE_a_name_that_DID_read_serves_no_no_read_note(monkeypatch):
    """NEGATIVE, and the positive control for the test above: the same
    endpoint, the same code path, a warmed name — the stat renders and the
    sentence must NOT."""
    p = _support_payload(monkeypatch, docs={"CRDO": crdo_doc()})
    assert p["tile"]["band_structure"]["stat"]
    assert p["band_structure_coverage"]["note"] is None
    assert p["band_structure_coverage"]["tiles_with_read"] == 1


def test_NEGATIVE_a_RAISING_banner_serves_NO_coverage_block_either(monkeypatch):
    """NEGATIVE. The chip may never outlive its banner (critique m3) — and
    neither may its absence notice: with the verdict down the read never runs,
    so "no band read for these names" would be a statement about a path that
    was switched off, not about the store."""
    p = _support_payload(monkeypatch, docs={}, verdict_raises=True, symbol="BTBT")
    assert p.get("band_structure_study") is None
    assert p.get("band_structure_coverage") is None
    assert p["tile"].get("band_structure") is None


# ═══════════════════════════════════════════════════════════════════════════
# 3 — the tile grid keeps the same answer
# ═══════════════════════════════════════════════════════════════════════════
def test_the_BOARD_serves_the_coverage_block_beside_the_read():
    """Pinned in the source: the coverage is computed from the SHOWN tiles,
    after the attach and inside the same guard, so it can never describe a
    different set of tiles than the one the page draws."""
    src = inspect.getsource(B.board)
    assert "band_structure_coverage" in src
    assert (src.index("attach_band_structure(_tiles")
            < src.index('out["band_structure_coverage"]')), \
        "the coverage must be read AFTER the tiles were decorated"


@pytest.mark.parametrize("kind", [EN.KIND_DEMAND, EN.KIND_NA])
def test_the_counts_are_HONEST_for_every_kind(monkeypatch, kind):
    """Counts are `applicable is True`, never "the key is present" — an n/a
    read is a served answer and still not a band read."""
    _patch_store(monkeypatch, {"CRDO": crdo_doc()})
    tiles = [_tile("CRDO"), _tile("BTBT")]
    B.attach_band_structure(tiles, kind=kind, live={})
    cov = B.band_structure_coverage(tiles, kind=kind)
    expect = 1 if kind == EN.KIND_DEMAND else 0
    assert cov["tiles_with_read"] == expect
    assert cov["tiles_without_read"] == 2 - expect


# ═══════════════════════════════════════════════════════════════════════════
# 4 — j5: the FLOOR bullet says the floor applies no proven-lid filter
# ═══════════════════════════════════════════════════════════════════════════
def test_the_RULES_panel_says_the_FLOOR_applies_NO_PROVEN_LID_FILTER():
    """`floor_read` is `bounce_room.demand_read` verbatim — no
    `LID_MIN_TOUCHES` filter — while `ceiling_read` skips sub-threshold bands.
    On CRDO the one served sentence therefore calls the SAME range "untested
    overhead" and "floor 3.5% wide". The panel's CEILING bullet said the rule;
    the FLOOR bullet was silent."""
    from supply_demand import alert_gates as AG
    from supply_demand import band_structure as BS
    from supply_demand import rules_info as RI

    sec = RI.sections()["band_structure"]
    floor = [p for p in sec["picks"] if "THE FLOOR APPLIES NO PROVEN-LID FILTER" in p]
    assert len(floor) == 1
    assert str(AG.LID_MIN_TOUCHES) in floor[0]
    assert "UNTESTED" in floor[0]
    # built from the constant, not retyped
    src = inspect.getsource(RI._band_structure_section)
    assert "LID_MIN_TOUCHES" in src
    # and the asymmetry it describes is REAL: the floor half imports the room
    # gate's demand read and applies no touch filter of its own.
    fsrc = inspect.getsource(BS.floor_read)
    assert "demand_read" in fsrc and "LID_MIN_TOUCHES" not in fsrc


def test_NEGATIVE_the_new_bullet_prints_no_RAW_PERCENT_ESCAPE():
    """NEGATIVE, and it has shipped before: `%%` is how a %-FORMAT string
    spells one percent sign; in a plain literal it reaches the ℹ️ panel
    verbatim and he reads "a floor N%% wide"."""
    from supply_demand import rules_info as RI
    sec = RI.sections()["band_structure"]
    assert "%%" not in json.dumps(sec, ensure_ascii=False)
    floor = [p for p in sec["picks"] if "NO PROVEN-LID FILTER" in p][0]
    assert "N% wide" in floor
