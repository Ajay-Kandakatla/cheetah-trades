"""🪜 THE NO-READ SENTENCE MAY NOT PROMISE A REFRESH THAT CANNOT COME
(critique 5, BLOCKING, 2026-09-16).

The first wording ended "Names the store is still warming arrive on the next
refresh." — served on 📁 My holdings, about BTBT, a position Ajay owns. BTBT's
market cap is 562,588,224 against `zone_store.MIN_CAP_USD` = 700,000,000. It is
not warming: it is permanently outside the store's eligible set at the floor he
set on 2026-09-10, so that refresh never arrives. A served sentence that is
untrue about his own name, on the page he owns it on.

`bounce_room.band_structure_no_read_note` now BUILDS the line from what the
render can actually see:

    every shown name UNDER the floor  -> "...at or above a $700M market cap and
                                          these are under it, so no refresh
                                          brings a read"
    every shown name AT/ABOVE it      -> "...still warming arrive on the next
                                          refresh"
    anything else (unknown / mixed)   -> the base sentence ALONE, promising
                                          nothing

ONE WORDING, BOTH PATHS: the row boards (`build_payload`) and the tile path
(`chart_maps/board.band_structure_coverage`, which Support Levels and 📁 My
holdings read) call the same function. The figure is `cap_floor_txt` over
`zone_store.MIN_CAP_USD` — never typed (the "$0B" precedent: a hard-coded
"$1B+" survived four days past his 2026-09-10 move, and the 2026-09-14 sweep
had to fix it on the Alerts page).

NEGATIVES pinned here: a below-floor name is NEVER told to wait; a genuinely
warming name still is; an unknown or mixed cap gets the neutral truth; a name
WITH a read gets no note at all; a zero / NaN / junk cap is UNKNOWN, never
"under the floor"; the cap read never touches the provider and never raises.
"""
from __future__ import annotations

import inspect
import json

import pytest

from supply_demand import bounce_room as BR
from supply_demand import enterable as EN
from supply_demand import zone_store as ZS
from supply_demand.alert_status import cap_floor_txt
from chart_maps import board as B

from tests.test_band_structure_tile_coverage_2026_09_16 import (  # reuse ONE fixture set
    CRDO_PX, crdo_doc, _patch_store, _tile,
)
from tests.test_band_structure_rows_2026_09_16 import (            # and the row path's
    CRDO_BANDS, NOW, STORE_DAY, _doc, _snap,
)

BTBT_CAP = 562_588_224.0        # his position, probed in the container 2026-09-16
CRDO_CAP = 25_000_000_000.0     # comfortably over the floor


def _caps(monkeypatch, caps: dict):
    """The shares-cache read, stubbed. It lives on the TILE path (see
    `_caps_for_band_note`'s docstring: the S/D scope contract keeps the cache
    out of `bounce_room`), so the row path never sees one."""
    monkeypatch.setattr(B, "_caps_for_band_note", lambda syms: dict(caps))


def _row_note(monkeypatch, symbols, caps, *, docs=None):
    _caps(monkeypatch, caps)          # the row path ignores it, by contract
    p = BR.build_payload(list(symbols), docs=dict(docs or {}), snapshot={},
                         now=NOW, store_date=STORE_DAY, pending=[])
    return p["band_structure_coverage"]["note"]


def _tile_note(monkeypatch, symbols, caps, *, docs=None):
    _caps(monkeypatch, caps)
    _patch_store(monkeypatch, docs or {})
    tiles = [_tile(s) for s in symbols]
    B.attach_band_structure(tiles, kind=EN.KIND_DEMAND, live={})
    return B.band_structure_coverage(tiles, kind=EN.KIND_DEMAND)["note"]


# ═══════════════════════════════════════════════════════════════════════════
# 1 — the three branches
# ═══════════════════════════════════════════════════════════════════════════
def test_NEGATIVE_a_name_UNDER_the_cap_floor_is_NEVER_told_to_wait(monkeypatch):
    """THE BUG. BTBT at $562.6M against a $700M floor: the store will never
    carry it, so the refresh clause is a promise nobody can keep."""
    note = BR.band_structure_no_read_note(["BTBT"], caps={"BTBT": BTBT_CAP})
    assert BR.BAND_STRUCTURE_STILL_WARMING_ONE not in note
    assert "still warming" not in note
    assert note == "%s %s" % (
        BR.BAND_STRUCTURE_NO_READ_ONE,
        BR.BAND_STRUCTURE_BELOW_CAP_ONE_FMT % cap_floor_txt(ZS.MIN_CAP_USD))
    assert "$700M" in note, "the floor he set on 2026-09-10"


def test_a_name_the_store_is_STILL_WARMING_is_still_told_to_wait(monkeypatch):
    """The positive control: over the floor, no doc yet — the refresh really
    does bring it, and dropping that clause would lose a true statement."""
    note = BR.band_structure_no_read_note(["CRDO"], caps={"CRDO": CRDO_CAP})
    assert note == "%s %s" % (BR.BAND_STRUCTURE_NO_READ_ONE,
                              BR.BAND_STRUCTURE_STILL_WARMING_ONE)
    assert "$700M" not in note, "no cap figure when the cap is not the reason"


def test_NEGATIVE_an_UNKNOWN_cap_gets_the_NEUTRAL_sentence(monkeypatch):
    """The cache never saw this name. Neither clause is knowable, so neither
    is served: "this name has no band read", full stop."""
    note = BR.band_structure_no_read_note(["NEWCO"], caps={})
    assert note == BR.BAND_STRUCTURE_NO_READ_ONE
    assert "refresh" not in note and "cap" not in note


@pytest.mark.parametrize("junk", [None, 0, 0.0, -1.0, float("nan"), "n/a", {}])
def test_NEGATIVE_a_ZERO_or_GARBAGE_cap_is_UNKNOWN_not_under_the_floor(junk):
    """NEGATIVE, and the nastiest one: a cap of 0 or NaN compares "< floor"
    and would tell him his name is too small when the truth is nobody
    knows."""
    note = BR.band_structure_no_read_note(["X"], caps={"X": junk})
    assert note == BR.BAND_STRUCTURE_NO_READ_ONE


def test_NEGATIVE_a_MIXED_list_promises_NOTHING(monkeypatch):
    """One below, one above. Either clause would be false about one of the two
    names, so the board says the part that is true of both."""
    note = BR.band_structure_no_read_note(
        ["BTBT", "CRDO"], caps={"BTBT": BTBT_CAP, "CRDO": CRDO_CAP})
    assert note == BR.BAND_STRUCTURE_NO_READ


def test_NEGATIVE_ONE_unknown_name_keeps_the_whole_note_neutral():
    """A known-under name beside an unknown one is not "all under"."""
    note = BR.band_structure_no_read_note(["BTBT", "NEWCO"],
                                          caps={"BTBT": BTBT_CAP})
    assert note == BR.BAND_STRUCTURE_NO_READ


def test_NEGATIVE_no_symbols_is_the_base_sentence_not_a_cap_claim():
    assert BR.band_structure_no_read_note([], caps={}) == BR.BAND_STRUCTURE_NO_READ
    assert BR.band_structure_no_read_note(None, caps={}) == BR.BAND_STRUCTURE_NO_READ


# ═══════════════════════════════════════════════════════════════════════════
# 2 — the figure is the CONSTANT, not a number in a string
# ═══════════════════════════════════════════════════════════════════════════
def test_the_cap_figure_is_READ_from_zone_store_MIN_CAP_USD(monkeypatch):
    """MUTATION. Move the constant and the sentence moves with it — and the
    SAME name flips branch, because the floor is the only thing deciding."""
    monkeypatch.setattr(ZS, "MIN_CAP_USD", 1_000_000_000.0)
    note = BR.band_structure_no_read_note(["BTBT"], caps={"BTBT": BTBT_CAP})
    assert "$1B" in note and "$700M" not in note

    monkeypatch.setattr(ZS, "MIN_CAP_USD", 400_000_000.0)
    note = BR.band_structure_no_read_note(["BTBT"], caps={"BTBT": BTBT_CAP})
    assert note.endswith(BR.BAND_STRUCTURE_STILL_WARMING_ONE), \
        "over the floor, the store really is still warming it"


def test_the_sentences_carry_NO_TYPED_cap_figure():
    """Source guard, the 2026-09-14 Alerts-page lesson: the stale "$1B" lived
    in prose. No served constant here may name a dollar figure at all."""
    for txt in (BR.BAND_STRUCTURE_NO_READ, BR.BAND_STRUCTURE_STILL_WARMING,
                BR.BAND_STRUCTURE_BELOW_CAP_FMT):
        assert "$1B" not in txt and "$700M" not in txt
    src = inspect.getsource(BR.band_structure_no_read_note)
    assert "MIN_CAP_USD" in src and "cap_floor_txt" in src
    assert "700" not in src and "1e9" not in src


def test_NEGATIVE_no_served_string_here_says_bounce():
    """Reversal, never bounce, on anything he reads (2026-09-09)."""
    for txt in (BR.BAND_STRUCTURE_NO_READ, BR.BAND_STRUCTURE_STILL_WARMING,
                BR.BAND_STRUCTURE_BELOW_CAP_FMT):
        assert "bounc" not in txt.lower()


# ═══════════════════════════════════════════════════════════════════════════
# 3 — ONE wording, both paths
# ═══════════════════════════════════════════════════════════════════════════
def test_the_ROW_path_and_the_TILE_path_serve_the_SAME_sentence(monkeypatch):
    """The whole reason the note is served and not typed in TSX: his holdings
    tab and the ten row boards must not be able to say different things about
    the same name on the same day."""
    caps = {"BTBT": BTBT_CAP}
    row = _row_note(monkeypatch, ["BTBT"], caps)
    tile = _tile_note(monkeypatch, ["BTBT"], caps)
    # Same wording engine, so neither can say something the other cannot: the
    # row path (cap-blind) serves the BASE of the tile path's sentence, never a
    # different one, and NEITHER tells a $562.6M name to wait for a refresh.
    assert tile.startswith(row) and row == BR.BAND_STRUCTURE_NO_READ_ONE
    assert BR.BAND_STRUCTURE_STILL_WARMING not in row
    assert BR.BAND_STRUCTURE_STILL_WARMING not in tile


def test_the_ROW_path_says_the_NEUTRAL_truth_it_cannot_see_the_cap(monkeypatch):
    """NOT a lesser sentence — the honest one. `bounce_room` may not read the
    shares cache (S/D scope), so on that path neither clause is knowable and
    the board promises nothing. The row boards build their docs on demand
    anyway; the tile path is where his positions are named."""
    for caps in ({"CRDO": CRDO_CAP}, {"BTBT": BTBT_CAP}):
        # one symbol per call here, so the singular base sentence is the
        # neutral truth (the plural reads wrong on a one-name response)
        assert _row_note(monkeypatch, list(caps), caps) == BR.BAND_STRUCTURE_NO_READ_ONE


def test_NEGATIVE_a_name_WITH_a_read_is_UNCHANGED_on_both_paths(monkeypatch):
    """NEGATIVE — nothing about this change may put a sentence on a board that
    has its read. The note is a ZERO-coverage statement and stays one."""
    caps = {"CRDO": CRDO_CAP}
    tile = _tile_note(monkeypatch, ["CRDO"], caps, docs={"CRDO": crdo_doc()})
    assert tile is None

    _caps(monkeypatch, caps)
    p = BR.build_payload(["CRDO"], docs={"CRDO": _doc(CRDO_BANDS)},
                         snapshot={"CRDO": _snap(CRDO_PX)},
                         now=NOW, store_date=STORE_DAY, pending=[])
    assert p["rows"]["CRDO"]["band_structure"]["applicable"] is True
    assert p["band_structure_coverage"]["note"] is None
    assert json.dumps(p)


def test_NEGATIVE_an_NA_TAB_still_prints_no_sentence_of_any_branch(monkeypatch):
    """NEGATIVE — an n/a tab has its own n/a text; a cap clause beside it is
    two contradicting sentences about one tab."""
    _caps(monkeypatch, {"VCPNAME": BTBT_CAP})
    _patch_store(monkeypatch, {})
    tiles = [_tile("VCPNAME")]
    B.attach_band_structure(tiles, kind=EN.KIND_NA, live={})
    assert B.band_structure_coverage(tiles, kind=EN.KIND_NA)["note"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 4 — the cap read itself: cache only, fail open
# ═══════════════════════════════════════════════════════════════════════════
def test_the_cap_read_NEVER_calls_the_provider(monkeypatch):
    """A render path may not turn into one network call per symbol
    (`bounce_room`'s own contract). `cap=0` cuts off `market_caps_for`'s
    provider tail, and no price map is passed — the cached figure is it."""
    seen = {}

    def fake(tickers, last_prices, fetch=None, coll=None, cap=None, **kw):
        seen["tickers"] = list(tickers)
        seen["cap"] = cap
        seen["prices"] = last_prices
        return {"BTBT": BTBT_CAP}

    import catalysts.promo_circuit as PC
    monkeypatch.setattr(PC, "market_caps_for", fake)
    assert B._caps_for_band_note(["btbt"]) == {"BTBT": BTBT_CAP}
    assert seen["tickers"] == ["BTBT"] and seen["cap"] == 0
    assert seen["prices"] == {}, "no price map on this path — the cached cap is it"
    assert B._caps_for_band_note([]) == {}


def test_the_CAP_READER_is_the_SHARED_engine_not_a_second_one():
    """One engine: the same `market_caps_for` the demand / zone-edge cap gates
    read. And it may not sit in `bounce_room` — the S/D scope contract forbids
    that module from reaching `catalysts` at all, which is the whole reason the
    wording takes `caps` from its caller."""
    assert "market_caps_for" in inspect.getsource(B._caps_for_band_note)
    src = inspect.getsource(BR)
    for forbidden in ("from catalysts", "import catalysts", "volume_movers"):
        assert forbidden not in src, \
            "bounce_room stays in S/D scope (test_supply_demand_contracts)"


def test_NEGATIVE_a_RAISING_cap_read_falls_back_to_the_NEUTRAL_sentence(monkeypatch):
    """NEGATIVE — fail open like every other decoration: no cap, no claim, and
    never a 500 on a board because a cache moved."""
    import catalysts.promo_circuit as PC
    monkeypatch.setattr(PC, "market_caps_for",
                        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no mongo")))
    assert B._caps_for_band_note(["BTBT"]) == {}
    assert BR.band_structure_no_read_note(["BTBT"]) == BR.BAND_STRUCTURE_NO_READ_ONE


def test_NEGATIVE_an_unreadable_cap_FLOOR_also_falls_back(monkeypatch):
    """NEGATIVE — if the constant itself cannot be read, the neutral truth is
    the only honest answer; inventing a floor here is the Rule #1 violation."""
    monkeypatch.setattr(ZS, "MIN_CAP_USD", float("nan"))
    assert BR.band_structure_no_read_note(["BTBT"], caps={"BTBT": BTBT_CAP}) \
        == BR.BAND_STRUCTURE_NO_READ_ONE


# ═══════════════════════════════════════════════════════════════════════════
# 5 — end to end on the payload 📁 My holdings reads, one per position
# ═══════════════════════════════════════════════════════════════════════════
def _support_payload(monkeypatch, *, symbol, caps, docs=None):
    import asyncio
    from chart_maps import api as A

    tile = {"symbol": symbol, "last_price": CRDO_PX, "stats": []}
    monkeypatch.setattr(A.support_mod, "for_symbol",
                        lambda *a, **kw: {"tile": tile, "bars_used": 130,
                                          "timeframe": "daily"})
    monkeypatch.setattr(A.board_mod, "_live_snapshot", lambda tiles: {})
    monkeypatch.setattr(A.board_mod, "attach_live_now",
                        lambda tiles, res, live=None: None)
    monkeypatch.setattr(A.board_mod, "attach_enterable",
                        lambda tiles, kind=None, live=None: 0)
    _caps(monkeypatch, caps)
    _patch_store(monkeypatch, docs or {})
    res = asyncio.run(A.chart_maps_support(symbol=symbol))
    return json.loads(res.body.decode())


def test_the_SUPPORT_payload_tells_BTBT_THE_TRUTH(monkeypatch):
    """His own position, his own tab. Before: "Names the store is still
    warming arrive on the next refresh." Now: it says why no read is coming."""
    p = _support_payload(monkeypatch, symbol="BTBT", caps={"BTBT": BTBT_CAP})
    note = p["band_structure_coverage"]["note"]
    assert "still warming" not in note and "next refresh" not in note
    assert cap_floor_txt(ZS.MIN_CAP_USD) in note
    assert p["tile"].get("band_structure") is None


def test_the_SUPPORT_payload_still_says_WARMING_for_a_big_name(monkeypatch):
    """NEGATIVE control on the same endpoint: over the floor and simply not
    warmed yet — the refresh clause is true and must survive."""
    p = _support_payload(monkeypatch, symbol="CRDO", caps={"CRDO": CRDO_CAP})
    assert p["band_structure_coverage"]["note"].endswith(
        BR.BAND_STRUCTURE_STILL_WARMING_ONE)


# ── One name reads as one name (2026-09-16, final review minor) ──────────────
# Support Levels and 📁 My holdings send ONE symbol per response, so the plural
# sentence was grammatically wrong on exactly the tab where the false refresh
# promise bit him. The branch is chosen by len(symbols), never by the caller.

def test_ONE_name_below_the_floor_reads_as_one_name():
    from supply_demand import bounce_room as BR
    note = BR.band_structure_no_read_note(["BTBT"], {"BTBT": 562_588_224.0})
    assert "this name" in note and "this one is under it" in note
    assert "these names" not in note and "these are under it" not in note
    assert "no refresh brings a read" in note


def test_ONE_name_still_warming_reads_as_one_name():
    from supply_demand import bounce_room as BR
    note = BR.band_structure_no_read_note(["NVDA"], {"NVDA": 3.2e12})
    assert "this name" in note and "next refresh" in note
    assert "Names the store is still warming" not in note


def test_NEGATIVE_two_names_keep_the_plural_sentence():
    from supply_demand import bounce_room as BR
    note = BR.band_structure_no_read_note(
        ["BTBT", "SLS"], {"BTBT": 5.6e8, "SLS": 4.0e8})
    assert "these names" in note and "these are under it" in note
    assert "this name" not in note


def test_NEGATIVE_one_name_with_an_UNKNOWN_cap_still_promises_nothing():
    from supply_demand import bounce_room as BR
    note = BR.band_structure_no_read_note(["XYZ"], {})
    assert "this name" in note
    assert "refresh" not in note and "market cap" not in note


def test_NEGATIVE_the_singular_forms_TYPE_no_cap_figure():
    import inspect
    from supply_demand import bounce_room as BR
    for name in ("BAND_STRUCTURE_NO_READ_ONE",
                 "BAND_STRUCTURE_STILL_WARMING_ONE",
                 "BAND_STRUCTURE_BELOW_CAP_ONE_FMT"):
        txt = getattr(BR, name)
        assert "$" not in txt.replace("%s", ""), name
        assert "700" not in txt and "billion" not in txt.lower(), name
    # (the served-string scrub is pinned in the shared contract test; the
    # docstring here legitimately names test_bounce_room_stays_in_S_D_scope)
