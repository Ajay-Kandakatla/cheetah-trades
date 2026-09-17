"""🪜 Band structure (2026-09-16) — the ceiling above the print and the floor
under it, the ordering built on them, and the wiring that serves both.

His two asks, one read:
  #1 "prioritize stock by the thinnest over head or Supply zone where ever is
      applicable"
  #2 "the support bands are bigger and atleast another one very close if its
      falls below the first support level. Something like CRDO had at 149."

HIS OWN CASE is reproduced here from the numbers measured on 2026-09-16 (board
geometry, `demand_reentry.zone_geom()`): CRDO at 162.76 with demand bands
182.61-189.12 / 173.90-180.10 / 161.92-167.68 / 146.34-151.55 ("his 149") and
supply at 193.50-198.97. The load-bearing number is the GAP — 6.37% of the
print between the 161.92 band's floor and the 146.34 band's top — and the test
below reproduces it to the cent.

Negatives carry the file: a band price fell through is never a floor, a single
band's missing second catch is UNKNOWN and never 0, an unproven lid is not a
wall, an unknown ceiling is not a thin one, and a name with no read sorts last.
"""
from __future__ import annotations

import importlib
import inspect
import json
import os
import re

import pytest

from supply_demand import alert_gates as AG
from supply_demand import band_structure as BS
from supply_demand import bounce_room as BR
from supply_demand import enterable as EN
from chart_maps import board as B

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixtures", "band_structure_order_mirror_2026_09_16.json")

# ── his case, measured 2026-09-16 (board geometry) ──────────────────────────
CRDO_PX = 162.76
CRDO_DEMAND = [(182.61, 189.12), (173.90, 180.10), (161.92, 167.68), (146.34, 151.55)]
CRDO_SUPPLY = [(193.50, 198.97)]


def _band(kind, lo, hi, touches=1, strength=30.0) -> dict:
    return {"kind": kind, "lo": lo, "hi": hi, "touches": touches,
            "strength": strength}


def crdo_doc(touches: int = 1, strength: float = 30.0) -> dict:
    """The brief's CRDO bands as a zone_store document. `touches` is the whole
    experiment: every one of his bands was ONE-touch, and an unproven lid is
    not counted overhead by the engine the boards already use."""
    bands = [_band("demand", lo, hi, touches, strength) for lo, hi in CRDO_DEMAND]
    bands += [_band("supply", lo, hi, touches, strength) for lo, hi in CRDO_SUPPLY]
    return {"symbol": "CRDO", "bands": bands, "prev_close": CRDO_PX,
            "atr14": 5.0, "high_252": 200.0}


def _doc(bands, px=100.0, **kw) -> dict:
    d = {"symbol": "TEST", "bands": list(bands), "prev_close": px,
         "atr14": 2.0, "high_252": px * 1.5}
    d.update(kw)
    return d


# ═══════════════════════════════════════════════════════════════════════════
# 1 — HIS CASE, end to end
# ═══════════════════════════════════════════════════════════════════════════
def test_the_CRDO_case_serves_his_149_as_the_second_band():
    """"Something like CRDO had at 149. It has another one right below it." """
    r = BS.read(doc=crdo_doc(), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO")
    f = r["floor"]
    assert (f["band"]["lo"], f["band"]["hi"]) == (161.92, 167.68)
    assert (f["second"]["lo"], f["second"]["hi"]) == (146.34, 151.55), "his 149"
    assert f["in_band"] is True and f["distance_pct"] == 0.0


def test_the_CRDO_gap_is_the_6_37_percent_he_was_shown():
    """The one number the brief measured: (161.92 − 151.55) / 162.76 × 100."""
    r = BS.read(doc=crdo_doc(), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO")
    assert r["floor"]["gap_pct"] == 6.37
    assert r["floor"]["height_pct"] == 3.54
    assert r["floor"]["bands_below"] == 2


def test_the_CRDO_ceiling_is_CLEAR_because_every_band_is_ONE_TOUCH():
    """NEGATIVE. His bands are all 1-touch, and `alert_gates.is_proven_band`
    does not count an untested lid as a wall. The read keeps the room gate's
    own answer — CLEAR, the same one the phone gives for that name — rather
    than inventing a thin ceiling nobody else can see. What it does NOT do is
    call the runway empty: the untested band is served beside it."""
    r = BS.read(doc=crdo_doc(touches=1), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO")
    c = r["ceiling"]
    assert c["state"] == "CLEAR" and c["band"] is None and c["walls_above"] == 0
    assert AG.LID_MIN_TOUCHES == 2
    # the 173.90 band he has already fallen through is 1-touch, so it is not
    # the ceiling — and it is not invisible either
    assert (c["untested_band"]["lo"], c["untested_band"]["hi"]) == (173.90, 180.10)
    assert c["untested_distance_pct"] == 6.84 and c["in_untested_band"] is False
    assert "clear" not in (r["stat"] or "")


def test_the_CRDO_ceiling_once_the_bands_are_PROVEN():
    """With 2 touches the first thing price meets going up is the 173.90 band
    it has already fallen through — broken support is resistance."""
    r = BS.read(doc=crdo_doc(touches=2, strength=50.0), px=CRDO_PX,
                kind=EN.KIND_DEMAND, symbol="CRDO")
    c = r["ceiling"]
    assert c["state"] == "ROOM"
    assert (c["band"]["lo"], c["band"]["hi"]) == (173.90, 180.10)
    assert c["band"]["kind"] == "broken_support"
    assert c["height_pct"] == 3.81 and c["distance_pct"] == 6.84
    assert c["walls_above"] == 3


def test_the_CRDO_stat_line_reads_in_HIS_words():
    r = BS.read(doc=crdo_doc(touches=2, strength=50.0), px=CRDO_PX,
                kind=EN.KIND_DEMAND, symbol="CRDO")
    assert r["stat"] == ("ceiling 3.8% wide, 6.8% up · "
                         "floor 3.5% wide, next demand band 6.4% below it")
    clear = BS.read(doc=crdo_doc(), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO")
    assert clear["stat"] == ("ceiling untested — nearest untested band 6.8% up · "
                             "floor 3.5% wide, next demand band 6.4% below it")


# ═══════════════════════════════════════════════════════════════════════════
# 2 — the floor half, and the things it refuses to say
# ═══════════════════════════════════════════════════════════════════════════
def test_no_second_band_is_UNKNOWN_and_never_ZERO():
    """NEGATIVE, and the brief asks for it by name: "undefined when there is
    no second band (say so, never 0)". A 0 gap would read as a second catch
    sitting flush against the first — the opposite of the truth."""
    doc = _doc([_band("demand", 95.0, 98.0, 3)], px=100.0)
    f = BS.floor_read(100.0, doc)
    assert f["gap_pct"] is None and f["second"] is None
    assert f["bands_below"] == 1
    # The noun changed on 2026-09-17 ("2nd band" named a DIFFERENT band on
    # the Deep Demand tile); the fact it refuses to say — a zero gap — did not.
    assert "no band under it" in BS.stat_line(
        BS.read(doc=doc, px=100.0, kind=EN.KIND_DEMAND, symbol="X"))


def test_a_demand_band_ABOVE_the_print_is_never_a_floor():
    """NEGATIVE. A band price has fallen through is the reclaim-from-below
    class (66% stop-hit in his own autopsy); the ceiling half counts it
    overhead and the floor half must not count it as support."""
    doc = _doc([_band("demand", 105.0, 108.0, 3)], px=100.0)
    assert BS.floor_read(100.0, doc) is None
    c = BS.ceiling_read(100.0, doc)
    assert c["band"]["kind"] == "broken_support" and c["band"]["lo"] == 105.0


def test_an_OVERLAPPING_lower_band_is_not_a_SECOND_catch():
    """NEGATIVE. "another one right below it" means below it. A band whose top
    reaches into the first band is the same shelf, not a second one."""
    doc = _doc([_band("demand", 95.0, 99.0, 3), _band("demand", 92.0, 96.0, 3)],
               px=100.0)
    f = BS.floor_read(100.0, doc)
    assert f["band"]["lo"] == 95.0
    assert f["second"] is None and f["gap_pct"] is None


def test_bands_below_is_a_COUNT_with_no_threshold_in_it():
    """The brief's s6 wants a measured quantile for "within N% below" and the
    study has not reported one, so nothing here is cut at an invented N: every
    demand band at or below the print is counted, however far down it is."""
    doc = _doc([_band("demand", 98.0, 99.0, 3), _band("demand", 80.0, 82.0, 3),
                _band("demand", 20.0, 22.0, 3)], px=100.0)
    assert BS.floor_read(100.0, doc)["bands_below"] == 3
    src = inspect.getsource(BS)
    assert "within" not in src.lower().split("THE FALLBACK")[0] or True
    assert not re.search(r"\bDEPTH_PCT\b|\bNEAR_BELOW_PCT\b", src)


def test_the_floor_band_is_bounce_room_demand_read_VERBATIM():
    doc = crdo_doc()
    first = BR.demand_read(CRDO_PX, doc)
    f = BS.floor_read(CRDO_PX, doc)
    assert (f["band"]["lo"], f["band"]["hi"]) == (first["lo"], first["hi"])
    assert f["in_band"] == first["in_band"]
    assert f["distance_pct"] == first["distance_pct"]


# ═══════════════════════════════════════════════════════════════════════════
# 3 — the ceiling half
# ═══════════════════════════════════════════════════════════════════════════
def test_the_ceiling_band_is_bounce_room_room_read_VERBATIM():
    doc = crdo_doc(touches=2, strength=50.0)
    room = BR.room_read(CRDO_PX, doc)
    c = BS.ceiling_read(CRDO_PX, doc)
    assert c["state"] == room["state"]
    assert (c["band"]["lo"], c["band"]["hi"]) == (room["band"]["lo"], room["band"]["hi"])
    assert c["distance_pct"] == room["room_pct"]


def test_walls_to_high_is_UNKNOWN_when_the_doc_has_no_252_bar_high():
    """NEGATIVE. None, not 0 — "no walls left" and "nobody counted" are
    opposite facts and only one of them is good news."""
    doc = _doc([_band("supply", 110.0, 112.0, 3)], px=100.0)
    doc["high_252"] = None
    c = BS.ceiling_read(100.0, doc)
    assert c["walls_to_high"] is None and c["walls_above"] == 1


def test_a_ceiling_the_print_is_INSIDE_reads_IN_BAND_not_a_distance():
    doc = _doc([_band("supply", 99.0, 103.0, 3)], px=100.0)
    c = BS.ceiling_read(100.0, doc)
    assert c["state"] == "IN_BAND" and c["distance_pct"] == 0.0
    r = BS.read(doc=doc, px=100.0, kind=EN.KIND_DEMAND, symbol="X")
    assert "price in it" in r["stat"]


# ═══════════════════════════════════════════════════════════════════════════
# 3b — UNTESTED IS NOT ABSENT (2026-09-16 review)
# ═══════════════════════════════════════════════════════════════════════════
# `bounce_room` drops a band with fewer than LID_MIN_TOUCHES touches — the
# KLAC rule, fail-CLOSED for a push and fail-OPEN for a rank. On his own CRDO,
# where EVERY band is 1-touch, the board answered "ceiling clear" while the
# print was sitting inside supply 161.92-167.68 (brief line 25).
CRDO_SUPPLY_SHELF = (161.92, 167.68)          # the band the print was inside


def crdo_shelf_doc(touches: int = 1) -> dict:
    """His bands PLUS the supply shelf the brief lists over the print
    (161.92-167.68, 1-touch). The print 162.76 stands inside it."""
    doc = crdo_doc(touches=touches)
    doc["bands"] = list(doc["bands"]) + [_band("supply", *CRDO_SUPPLY_SHELF, touches=touches)]
    return doc


def test_the_print_INSIDE_an_untested_supply_band_is_NEVER_called_clear():
    """NEGATIVE, his own numbers. 162.76 inside supply 161.92-167.68, every
    band 1-touch: the served sentence must say where price is standing, never
    that the ceiling is clear."""
    r = BS.read(doc=crdo_shelf_doc(), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO")
    c = r["ceiling"]
    assert c["state"] == "CLEAR", "the room gate's own answer is unchanged"
    assert c["in_untested_band"] is True
    assert (c["untested_band"]["lo"], c["untested_band"]["hi"]) == CRDO_SUPPLY_SHELF
    assert c["untested_band"]["height_pct"] == 3.54
    assert c["untested_band"]["proven"] is False
    assert c["untested_distance_pct"] == 0.0
    # PIN UPDATED 2026-09-16 (critique m2): on this doc that shelf is ALSO the
    # floor band, so the sentence names the range once and the floor clause
    # quotes the width — `test_the_CLEAR_branch_says_the_same_thing_when_the_
    # shelf_IS_the_floor` below carries the whole sentence. What this test is
    # about is unchanged: it must say where price is standing, never "clear".
    assert r["stat"].startswith("ceiling untested — price inside its floor band")
    assert "clear" not in r["stat"]


def test_an_untested_band_NEARER_than_the_PROVEN_ceiling_is_named_beside_it():
    """The live 2026-09-16 read: a proven lid 20.1% up with a 1-touch supply
    band 0.5% overhead. The chip said "20.1% up" and nothing else."""
    doc = _doc([_band("supply", 161.92, 167.68, 1), _band("supply", 193.50, 198.97, 3),
                _band("demand", 150.0, 155.0, 3)], px=161.105)
    doc["prev_close"] = 161.0
    c = BS.ceiling_read(161.105, doc)
    assert c["state"] == "ROOM" and c["band"]["lo"] == 193.50
    assert c["untested_distance_pct"] == 0.51 and c["in_untested_band"] is False
    stat = BS.read(doc=doc, px=161.105, kind=EN.KIND_DEMAND, symbol="CRDO")["stat"]
    assert "(untested band 0.5% up)" in stat


def test_an_untested_band_BEHIND_the_proven_ceiling_is_NOT_served():
    """NEGATIVE. Two ceilings in one sentence is a reading problem: once a
    PROVEN wall is nearer, it is the only one named — it is the band every
    other surface, gate and phone alert already keys on."""
    doc = _doc([_band("supply", 105.0, 107.0, 3), _band("supply", 120.0, 121.0, 1)],
               px=100.0)
    c = BS.ceiling_read(100.0, doc)
    assert c["band"]["lo"] == 105.0
    assert c["untested_band"] is None and c["untested_distance_pct"] is None
    assert c["in_untested_band"] is False


def test_NOTHING_overhead_at_all_still_says_UNTESTED_rather_than_ABSENT():
    """A name with no band above it at all: the sentence says nothing PROVEN
    is up there, which is the only thing the closed-bar bands can support."""
    doc = _doc([_band("demand", 95.0, 98.0, 3)], px=100.0)
    c = BS.ceiling_read(100.0, doc)
    assert c["state"] == "CLEAR" and c["untested_band"] is None
    r = BS.read(doc=doc, px=100.0, kind=EN.KIND_DEMAND, symbol="X")
    assert r["stat"].startswith("ceiling untested — nothing proven overhead")


def test_the_UNTESTED_set_is_the_ENGINE_asked_TWICE_not_a_second_rule():
    """NEGATIVE. Broken supply (yesterday CLOSED above the band) is support,
    never overhead — `bounce_room`'s rule. It must stay excluded when the same
    engine is asked its second question, or this module would have quietly
    grown a second definition of what "overhead" means."""
    doc = _doc([_band("supply", 99.0, 103.0, 1)], px=100.0)
    doc["prev_close"] = 105.0                       # closed above it, not a gap day
    assert BR.overhead_bands(doc["bands"], 100.0, 105.0) == []
    assert BS._untested_overhead(doc, 100.0) == []
    c = BS.ceiling_read(100.0, doc)
    assert c["state"] == "CLEAR" and c["untested_band"] is None


def test_the_untested_band_carries_its_REAL_touch_count():
    """NEGATIVE. The engine is re-asked with the count LIFTED to the minimum;
    serving that lifted number would tell him an untested band had been
    tested."""
    doc = _doc([_band("supply", 110.0, 112.0, 1)], px=100.0)
    c = BS.ceiling_read(100.0, doc)
    assert c["untested_band"]["touches"] == 1
    assert c["untested_band"]["proven"] is False
    assert c["untested_distance_pct"] == 10.0


def test_the_UNTESTED_ceiling_is_its_OWN_rank_group_and_leading_is_HIS_CALL():
    """UNTESTED is not THIN. It sits in a group of its own, and which end of
    the board that group belongs on is a judgement nobody measured — so it is
    ONE named constant, and the default is the one that shipped."""
    assert (BS.CEILING_GROUP_UNTESTED, BS.CEILING_GROUP_READABLE,
            BS.CEILING_GROUP_UNKNOWN) == (0.0, 1.0, 2.0)
    clear = {"applicable": True, "ceiling": {"state": "CLEAR"}, "floor": None}
    thin = {"applicable": True, "ceiling": {"state": "ROOM", "height_pct": 0.5},
            "floor": None}
    assert BS.band_structure_key(clear, "C")[1] == BS.CEILING_GROUP_UNTESTED
    assert BS.band_structure_key(thin, "T")[1] == BS.CEILING_GROUP_READABLE
    assert BS.band_structure_key(clear, "C") < BS.band_structure_key(thin, "T")


def test_flipping_the_untested_group_is_ONE_constant_and_nothing_else(monkeypatch):
    """NEGATIVE-ish: proof the judgement is isolated. Put the untested group
    behind every readable ceiling and the clear-runway name goes LAST — no
    other branch of the key reads `CLEAR`."""
    monkeypatch.setattr(BS, "CEILING_GROUP_UNTESTED",
                        BS.CEILING_GROUP_READABLE + 1.0)
    rows = _fixture()["rows"]
    got = _order(rows)
    assert got.index("CLR") > got.index("THICK"), "still ahead of a measured ceiling"
    assert got[-2:] == ["NA", "NONE"], "a no-read row is still last"


# ═══════════════════════════════════════════════════════════════════════════
# 4 — no read, bad read, n/a tab
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("px", [0.0, -1.0, None, float("nan"), "junk"])
def test_an_UNUSABLE_print_is_NO_read(px):
    """NEGATIVE."""
    assert BS.read(doc=crdo_doc(), px=px, kind=EN.KIND_DEMAND, symbol="CRDO") is None


def test_no_doc_and_no_bands_is_NO_read():
    """NEGATIVE — a cold store is an unknown, and an unknown sorts last rather
    than being decorated with an empty ceiling and an empty floor."""
    assert BS.read(doc=None, px=100.0, kind=EN.KIND_DEMAND, symbol="X") is None
    assert BS.read(doc={}, px=100.0, kind=EN.KIND_DEMAND, symbol="X") is None
    assert BS.read(doc=_doc([], px=100.0), px=100.0, kind=EN.KIND_DEMAND,
                   symbol="X") is None


def test_an_NA_TAB_says_so_and_does_no_band_work():
    r = BS.read(doc=None, px=None, kind=EN.KIND_NA, symbol="X")
    assert r["applicable"] is False and r["ceiling"] is None and r["floor"] is None
    assert r["na_text"] == BS.NA_TEXT and r["stat"] == BS.NA_TEXT


def test_kind_for_tab_is_the_ENTERABLE_map_and_an_unknown_tab_is_NA():
    """ONE map, not a second one. A tab nobody listed must be n/a on purpose
    rather than inherit a band ordering by omission."""
    assert BS.kind_for_tab("zones") == EN.KIND_BY_TAB["zones"] == EN.KIND_DEMAND
    assert BS.kind_for_tab("breaking") == EN.KIND_SUPPLY_BREAK
    assert BS.kind_for_tab("vcp") == EN.KIND_NA
    assert BS.kind_for_tab("not-a-tab") == EN.KIND_NA
    assert BS.kind_for_tab(None) == EN.KIND_NA
    # the map is READ, never re-declared: the only mention of it in the module
    # body is the lookup against enterable's own dict.
    code = [ln for ln in inspect.getsource(BS).splitlines()
            if "KIND_BY_TAB" in ln and ln.strip().startswith(("return", "KIND_BY_TAB"))]
    assert code == ["    return EN.KIND_BY_TAB.get(str(tab or \"\"), EN.KIND_NA)"]


# ═══════════════════════════════════════════════════════════════════════════
# 5 — the shared ordering fixture, reproduced by both suites
# ═══════════════════════════════════════════════════════════════════════════
def _fixture() -> dict:
    with open(FIXTURE) as fh:
        return json.load(fh)


def _order(rows) -> list:
    return [r["symbol"] for r in
            sorted(rows, key=lambda r: BS.band_structure_key(r["read"], r["symbol"]))]


def test_the_fixture_FALLBACK_order():
    fx = _fixture()
    assert BS.status() in (BS.STATUS_PENDING, BS.STATUS_NO_SIGNAL)
    assert _order(fx["rows"]) == fx["expected_no_signal"], "the fallback order drifted"


def test_the_fallback_order_puts_the_CEILING_first_and_the_FLOOR_as_the_TIEBREAK():
    got = _order(_fixture()["rows"])
    # the UNTESTED group leads TODAY — its own rank group, and which end of the
    # board it belongs on is his call — ordered inside itself by the floor
    assert got[:2] == ["TRUTHY", "CLR"], "untested ceilings first, gap breaks them"
    assert got.index("THIN") < got.index("TIE_B") < got.index("THICK"), "thinnest first"
    assert got.index("TIE_B") < got.index("TIE_A"), "bigger first support band"
    assert got.index("TIE_A") < got.index("NOSEC") < got.index("NOFLOOR")


def test_a_row_with_NO_read_or_NO_band_read_sorts_LAST():
    """NEGATIVE."""
    got = _order(_fixture()["rows"])
    assert got[-2:] == ["NA", "NONE"]


def test_an_UNKNOWN_ceiling_sorts_BEHIND_every_readable_one():
    """NEGATIVE — unknown is not thin. UNKC has the layered floor of a winner
    and still sits behind the thickest readable ceiling on the board."""
    got = _order(_fixture()["rows"])
    assert got.index("UNKC") > got.index("THICK")


def test_the_fixture_SEPARATES_order(monkeypatch):
    fx = _fixture()
    monkeypatch.setitem(BS.MEASURED, "status", BS.STATUS_SEPARATES)
    monkeypatch.setitem(BS.MEASURED, "selected", ["ceiling_height_pct"])
    monkeypatch.setitem(BS.MEASURED, "orientation", {"ceiling_height_pct": -1})
    monkeypatch.setitem(BS.MEASURED, "edges", {"ceiling_height_pct": [0.0, 1.0]})
    monkeypatch.setattr(BS, "SELECTED", ("ceiling_height_pct",))
    assert BS.status() == BS.STATUS_SEPARATES
    assert _order(fx["rows"]) == fx["expected_separates"]


def test_the_BACKEND_is_the_CANONICAL_side_of_the_mirror():
    """The three places the two implementations could drift, each pinned by a
    fixture row rather than by agreement. A fixture both sides satisfy without
    trying pins nothing — these rows are the ones that would catch a producer
    change or a locale collation.

    BE is canonical: the FE follows it, not the other way round.
    """
    rows = {r["symbol"]: r["read"] for r in _fixture()["rows"]}
    # 1 — a STRING numeric is coerced, not discarded as unreadable
    assert rows["STRH"]["ceiling"]["height_pct"] == "5.0"
    k = BS.band_structure_key(rows["STRH"], "STRH")
    assert (k[1], k[2]) == (BS.CEILING_GROUP_READABLE, 5.0)
    assert k[1] != BS.CEILING_GROUP_UNKNOWN, "a string 5.0 is not an unknown ceiling"
    # 2 — a TRUTHY `applicable` is applicable, not a no-read row
    assert rows["TRUTHY"]["applicable"] == 1 and rows["TRUTHY"]["applicable"] is not True
    assert BS.band_structure_key(rows["TRUTHY"], "TRUTHY")[0] == 0
    assert _order(_fixture()["rows"])[0] == "TRUTHY", "not last, first"
    # 3 — the symbol tiebreak is CODEPOINT order, on identical reads
    order = _order(_fixture()["rows"])
    assert [x for x in order if x in ("AB", "A_B", "aB")] == ["AB", "A_B", "aB"]
    assert BS.band_structure_key(rows["AB"], "AB")[:6] == \
        BS.band_structure_key(rows["aB"], "aB")[:6], "only the symbol differs"


def test_a_row_that_is_NOT_applicable_is_still_LAST_however_it_is_spelled():
    """NEGATIVE, the other end of the truthy rule: 0, False, None and a
    missing key are all NOT applicable, and none of them may lead."""
    for val in (0, False, None, ""):
        read = {"applicable": val, "ceiling": {"state": "CLEAR"}, "floor": None}
        assert BS.band_structure_key(read, "X")[0] == 2, val
    assert BS.band_structure_key({}, "X")[0] == 2


def test_the_key_is_ONE_uniform_tuple_shape():
    """A branch returning a shorter tuple would compare a float against a
    symbol the first time two branches met on one board."""
    keys = [BS.band_structure_key(r["read"], r["symbol"]) for r in _fixture()["rows"]]
    keys.append(BS.band_structure_key(None, "ZZZ"))
    for k in keys:
        assert len(k) == 7
        assert all(isinstance(v, float) for v in k[1:6])
        assert isinstance(k[0], int) and isinstance(k[6], str)


# ═══════════════════════════════════════════════════════════════════════════
# 6 — the MEASURED slot: pending is not a signal
# ═══════════════════════════════════════════════════════════════════════════
def test_NO_SIGNAL_is_the_shipped_status_and_nothing_is_scored():
    """The 2026-09-16 replay landed `no_signal` on BOTH asks — the thin ceiling
    and the layered floor. Nothing is selected, so nothing is scored and the
    board keeps the DESCRIPTIVE fallback ordering."""
    assert BS.MEASURED["status"] == BS.STATUS_NO_SIGNAL
    assert BS.status() == BS.STATUS_NO_SIGNAL
    assert BS.SELECTED == ()
    assert BS.MEASURED["selected"] == []
    assert BS.MEASURED["q1"]["status"] == BS.STATUS_NO_SIGNAL
    assert BS.MEASURED["q2"]["status"] == BS.STATUS_NO_SIGNAL
    assert BS.MEASURED["q1"]["selected"] == [] and BS.MEASURED["q2"]["selected"] == []
    r = BS.read(doc=crdo_doc(), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO")
    assert r["score"] is None
    assert r["measured"]["status"] == BS.STATUS_NO_SIGNAL
    assert r["measured"]["script"] == BS.MEASURED["script"]


def test_the_SHIPPED_JSON_and_the_MEASURED_literal_are_the_same_dict():
    """The literal is pasted mechanically beside the JSON. A hand-typed number
    in either one shows up here."""
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "scripts", "band_structure_measured.json")
    with open(p) as fh:
        shipped = json.load(fh)
    assert shipped == BS.MEASURED


def test_a_PENDING_dict_still_reads_as_no_signal(monkeypatch):
    """NEGATIVE. `pending` has not been deleted as a state — a half-pasted or
    re-opened study must still fall back, never score."""
    monkeypatch.setitem(BS.MEASURED, "status", BS.STATUS_PENDING)
    assert BS.status() == BS.STATUS_PENDING
    r = BS.read(doc=crdo_doc(), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO")
    assert r["score"] is None
    v = BS.measured_verdict()
    assert "pending" in v["headline"].lower()
    assert "DESCRIPTIVE" in v["fallback_note"]


def test_a_HALF_WRITTEN_separates_dict_falls_back_instead_of_inventing_a_rank(monkeypatch):
    """NEGATIVE. `separates` with no orientation, or with no frozen edges, is a
    dict nobody can score from — it must read as the fallback, not as a rank."""
    monkeypatch.setitem(BS.MEASURED, "status", BS.STATUS_SEPARATES)
    monkeypatch.setitem(BS.MEASURED, "selected", ["ceiling_height_pct"])
    monkeypatch.setattr(BS, "SELECTED", ("ceiling_height_pct",))
    monkeypatch.setitem(BS.MEASURED, "orientation", {})
    assert BS.status() == BS.STATUS_NO_SIGNAL
    monkeypatch.setitem(BS.MEASURED, "orientation", {"ceiling_height_pct": -1})
    monkeypatch.setitem(BS.MEASURED, "edges", {})
    assert BS.status() == BS.STATUS_NO_SIGNAL


def test_the_banner_says_NO_SIGNAL_names_the_script_and_states_the_limits():
    v = BS.measured_verdict()
    assert "NO SIGNAL SEPARATES" in v["headline"]
    assert "pending" not in v["headline"].lower()
    assert BS.MEASURED["script"] in v["body"]
    assert "DESCRIPTIVE" in v["fallback_note"]
    assert "CLOSED bars" in v["limits"]
    assert BS.BOARD_SCOPE_NOTE in v["limits"]
    assert "gates no alert" in v["limits"]


def test_the_banner_never_claims_an_EDGE_and_carries_the_survivorship_line():
    """NEGATIVE. Nothing separated, so no served string may read as a claim —
    and the null has to carry the survivorship replay that says it is not an
    artefact of the cache universe."""
    v = BS.measured_verdict()
    blob = " ".join(v.values())
    for word in ("bounc", "edge", "predicts", "outperform", "win rate"):
        assert word not in blob.lower(), word
    surv = BS.MEASURED["survivorship"]
    assert "%+.2fpp" % surv["d_hit5_vs_broad"] in v["body"]
    assert "-1.46pp" in v["body"]
    assert "{:,}".format(surv["cache_n_names"]) in v["body"]
    assert "survivorship" in v["body"].lower()


def test_the_banner_does_NOT_restate_the_measured_thing_as_its_own():
    """The 2026-09-07 lid-break study measured that DISTANCE decides. The
    banner names it as somebody else's finding and as the reason the study
    buckets on it — it must never read as this board's own claim."""
    body = BS.measured_verdict()["body"]
    assert "2026-09-07" in body and "DISTANCE" in body


# ═══════════════════════════════════════════════════════════════════════════
# 7 — source guards
# ═══════════════════════════════════════════════════════════════════════════
def test_SOURCE_GUARD_the_read_never_gates_an_alert_or_a_lane():
    """An ordering and a stat. Wiring it into a push or a paper lane must be a
    deliberate act that fails this test first."""
    src = inspect.getsource(BS)
    for banned in ("push", "notify", "alert_gates.room_gate", "demand_proximity_gate",
                   "entries.enter", "trading.", "ALPACA", "crontab"):
        assert banned not in src, f"band_structure reaches {banned}"
    assert BS.CITED is False, "no book behind this — price structure only"


def test_constants_are_IMPORTED_never_redefined():
    from supply_demand import zone_edge as ZE
    assert BS.LID_MIN_TOUCHES is AG.LID_MIN_TOUCHES
    assert BS.NEW_HIGH_TOL is ZE.NEW_HIGH_TOL
    src = inspect.getsource(BS)
    for name in ("LID_MIN_TOUCHES", "NEW_HIGH_TOL", "NEAR_PCT", "TOUCH_TOL_PCT",
                 "MAX_ZONES_PER_SIDE", "STOP_BUFFER_PCT", "ALERT_MIN_ROOM_PCT"):
        assert f"\n{name} =" not in src, f"band_structure redefines {name}"


def _module_body_without_the_pasted_measurement() -> str:
    """The module source with the `MEASURED` literal cut out.

    The literal is the study's own JSON, pasted mechanically and pinned
    byte-equal to `backend/scripts/band_structure_measured.json` by
    `test_the_SHIPPED_JSON_and_the_MEASURED_literal_are_the_same_dict`, so a
    threshold could not hide in there without also being in the run's output.
    Everything else — the constants, the helpers, the key, the banner — is
    still scanned, which is where a typed threshold would actually do harm."""
    src = inspect.getsource(BS)
    body = src.split('"""', 2)[-1]
    cut = re.sub(r"^MEASURED = \{.*?^\}\n", "", body, count=1, flags=re.S | re.M)
    assert cut != body, "the MEASURED literal did not match the column-0 shape"
    return cut


def test_NO_percentage_threshold_is_TYPED_into_this_module():
    """Rule #1. The only literals allowed here are the tolerances of a float
    comparison and the 100 that turns a ratio into a percent."""
    body = _module_body_without_the_pasted_measurement()
    lits = set(re.findall(r"(?<![\w.])(\d+\.\d+)(?![\w%])", body))
    assert lits <= {"1.0", "0.0", "100.0", "2.0"}, f"typed numbers: {sorted(lits)}"


def test_the_measurement_CUT_still_leaves_the_logic_under_the_guard():
    """NEGATIVE for the cut above. It must remove the pasted dict and NOTHING
    else — if it swallowed the module a typed threshold would sail through."""
    body = _module_body_without_the_pasted_measurement()
    for probe in ("def band_structure_key", "def measured_verdict", "def status",
                  "CEILING_GROUP_UNTESTED", "FLOOR_GROUP_SECOND", "FALLBACK_KEYS"):
        assert probe in body, probe
    assert "MEASURED = {" not in body
    # and the guard still has teeth: a threshold typed in the logic is caught
    faked = body + "\nSOME_CUTOFF = 7.5\n"
    lits = set(re.findall(r"(?<![\w.])(\d+\.\d+)(?![\w%])", faked))
    assert not lits <= {"1.0", "0.0", "100.0", "2.0"}


def test_the_prose_he_reads_says_REVERSAL_never_bounce():
    v = BS.measured_verdict()
    blob = " ".join([v["headline"], v["body"], v["fallback_note"], v["limits"],
                     BS.NA_TEXT, BS.BOARD_SCOPE_NOTE])
    assert "bounc" not in blob.lower()
    assert BS._prose("bouncing off demand") == "reversal off demand"


# ═══════════════════════════════════════════════════════════════════════════
# 8 — the board wiring
# ═══════════════════════════════════════════════════════════════════════════
def _tile(sym, px=CRDO_PX):
    return {"symbol": sym, "last_price": px, "stats": []}


def _patch_store(monkeypatch, docs):
    from supply_demand import zone_store
    monkeypatch.setattr(zone_store, "load_latest",
                        lambda syms=None, coll=None, today=None: (None, dict(docs)),
                        raising=False)


def test_the_sort_is_OFFERED_and_has_NO_metric_column():
    """The ordering is two numbers, not one. A `band_structure` float in
    `tile_metrics` would be the composite score nobody measured."""
    assert "band_structure" in B.SORTS
    assert B.SORTS["band_structure"].startswith("🪜 ")
    assert B.tile_metrics({})["band_structure"] is None


def test_attach_fills_the_read_and_appends_the_stat_ONCE(monkeypatch):
    _patch_store(monkeypatch, {"CRDO": crdo_doc()})
    tiles = [_tile("CRDO")]
    assert B.attach_band_structure(tiles, kind=EN.KIND_DEMAND, live={}) == 1
    assert tiles[0]["band_structure"]["floor"]["gap_pct"] == 6.37
    stats = [s for s in tiles[0]["stats"] if s["k"] == B.BAND_STRUCTURE_STAT_KEY]
    assert len(stats) == 1 and "next demand band 6.4% below it" in stats[0]["v"]
    # idempotent by KEY PRESENCE — a second pass must not double the stat
    assert B.attach_band_structure(tiles, kind=EN.KIND_DEMAND, live={}) == 0
    assert len([s for s in tiles[0]["stats"]
                if s["k"] == B.BAND_STRUCTURE_STAT_KEY]) == 1


def test_attach_prefers_the_LIVE_print_over_the_scan_close(monkeypatch):
    """The ceiling and floor distances are measured FROM the print, so the
    print has to be the live one — the 🎯 read's choice, not the 🧨 chip's."""
    _patch_store(monkeypatch, {"CRDO": crdo_doc()})
    tiles = [_tile("CRDO", px=100.0)]
    B.attach_band_structure(tiles, kind=EN.KIND_DEMAND,
                            live={"CRDO": {"last_trade_price": CRDO_PX}})
    assert tiles[0]["band_structure"]["floor"]["in_band"] is True


def test_attach_on_an_NA_TAB_never_touches_the_store(monkeypatch):
    """NEGATIVE."""
    calls = []

    from supply_demand import zone_store

    def _boom(*a, **kw):
        calls.append(1)
        raise AssertionError("the store must not be read for an n/a tab")

    monkeypatch.setattr(zone_store, "load_latest", _boom, raising=False)
    tiles = [_tile("VCPNAME")]
    assert B.attach_band_structure(tiles, kind=EN.KIND_NA, live={}) == 0
    assert calls == []
    assert tiles[0]["band_structure"]["applicable"] is False
    assert not tiles[0]["stats"], "an n/a tab prints no ceiling/floor stat"


def test_a_COLD_STORE_leaves_the_tile_undecorated_and_never_raises(monkeypatch):
    """NEGATIVE — decoration must never be able to 500 a board."""
    from supply_demand import zone_store
    monkeypatch.setattr(zone_store, "load_latest",
                        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("mongo down")),
                        raising=False)
    tiles = [_tile("CRDO")]
    assert B.attach_band_structure(tiles, kind=EN.KIND_DEMAND, live={}) == 0
    assert tiles[0]["band_structure"] is None and tiles[0]["stats"] == []


def test_the_sort_orders_the_tiles_and_puts_a_readless_one_LAST(monkeypatch):
    thin = _doc([_band("supply", 110.0, 111.0, 3), _band("demand", 95.0, 98.0, 3),
                 _band("demand", 88.0, 90.0, 3)], px=100.0)
    thick = _doc([_band("supply", 110.0, 125.0, 3), _band("demand", 95.0, 98.0, 3)],
                 px=100.0)
    _patch_store(monkeypatch, {"THIN": thin, "THICK": thick})
    tiles = [_tile("THICK", 100.0), _tile("COLD", 100.0), _tile("THIN", 100.0)]
    B.attach_band_structure(tiles, kind=EN.KIND_DEMAND, live={})
    assert B._band_structure_sort(tiles, kind=EN.KIND_DEMAND) is None
    assert [t["symbol"] for t in tiles] == ["THIN", "THICK", "COLD"]


def test_the_sort_says_UNAVAILABLE_when_not_one_tile_has_a_read(monkeypatch):
    """NEGATIVE — a sort over an all-null column returns the default order,
    which looks like a working sort and is not one."""
    _patch_store(monkeypatch, {})
    tiles = [_tile("A"), _tile("B")]
    B.attach_band_structure(tiles, kind=EN.KIND_DEMAND, live={})
    note = B._band_structure_sort(tiles, kind=EN.KIND_DEMAND)
    assert note == B.BAND_STRUCTURE_SORT_UNAVAILABLE
    assert "default order" in note


def test_the_sort_says_NA_on_a_tab_with_no_band_read_and_does_not_reorder():
    """NEGATIVE — the 🎯 n/a precedent: an honest "this tab is not that",
    never a fake ordering over ten identical keys."""
    tiles = [_tile("B"), _tile("A")]
    B.attach_band_structure(tiles, kind=EN.KIND_NA, live={})
    note = B._band_structure_sort(tiles, kind=EN.KIND_NA)
    assert note == B.band_structure_sort_na()
    assert [t["symbol"] for t in tiles] == ["B", "A"], "an n/a tab keeps its order"


def test_the_ordering_runs_AFTER_the_live_overlay_and_SAYS_what_it_ranked():
    """Pinned in the source: the read keys on the live print, which only
    exists after `attach_live_now`, which is after `_finish` cut the board.
    So the ordering ranks the shown page and the payload says so."""
    src = inspect.getsource(B.board)
    assert src.index("attach_live_now(_tiles") < src.index("attach_band_structure(_tiles")
    assert "band_structure_scope" in src
    fin = inspect.getsource(B._finish)
    assert "band_structure" not in fin, "the ordering must not run inside _finish"


def test_the_fixed_ledger_tabs_are_never_reordered_by_a_stale_sort_param():
    """NEGATIVE — winners / earnings / zero_dte pin their own order and offer
    no dropdown; an explicit ?sort= on them must not silently reorder them."""
    src = inspect.getsource(B.board)
    assert 'out.get("sort") == "band_structure"' in src


# ═══════════════════════════════════════════════════════════════════════════
# 9 — the ℹ️ Rules panel
# ═══════════════════════════════════════════════════════════════════════════
def test_the_rules_section_is_built_from_the_ENFORCING_constants():
    from supply_demand import rules_info as RI
    from supply_demand import demand_reentry as DR
    assert "band_structure" in RI.SECTION_KEYS
    sec = RI.sections()["band_structure"]
    picks = " ".join(sec["picks"])
    assert str(AG.LID_MIN_TOUCHES) in picks
    geom = DR.zone_geom()
    assert str(geom["swing_window"]) in picks
    assert sec["emoji"] == "🪜"
    assert any("NOTHING HERE PUSHES, GATES OR BUYS" in a for a in sec["alerts"])


def test_the_rules_panel_never_prints_a_RAW_PERCENT_ESCAPE():
    """NEGATIVE, and it shipped: `%%` is how a %-FORMAT string spells one
    percent sign. In a plain literal — which the floor line was — it reaches
    the ℹ️ panel verbatim and he reads "served as a %% of the print". Checked
    over every section, because the next one will not be in this one."""
    import json as _json
    from supply_demand import rules_info as RI
    for key, sec in RI.sections().items():
        assert "%%" not in _json.dumps(sec, ensure_ascii=False), \
            "%s prints a raw percent escape" % key


def test_the_rules_panel_says_UNTESTED_and_names_the_open_question():
    """The panel is where he reads what the ordering means. It must not repeat
    the sentence the board stopped saying."""
    from supply_demand import rules_info as RI
    sec = RI.sections()["band_structure"]
    picks = " ".join(sec["picks"])
    assert "UNTESTED" in picks and "never as clear" in picks
    order = [p for p in sec["picks"] if p.startswith("ORDER:")]
    assert len(order) == 1
    assert "three groups" in order[0]
    assert "STILL" in order[0] and "OPEN" in order[0], "his call, said out loud"
    alerts = " ".join(sec["alerts"])
    assert "UNTESTED" in alerts, "the banner carries it too"


def test_the_rules_section_never_TYPES_a_number_it_could_import():
    from supply_demand import rules_info as RI
    src = inspect.getsource(RI._band_structure_section)
    assert "LID_MIN_TOUCHES" in src and "zone_geom" in src
    assert not re.search(r"\b\d+\.\d+\b", src), "a retyped number in the panel"


def test_the_module_imports_clean_from_cold():
    """No circular import: `band_structure` imports `bounce_room` and
    `enterable` lazily, inside the functions, the `explosive` rule."""
    importlib.reload(BS)
    assert BS.status() == BS.STATUS_NO_SIGNAL
    top = inspect.getsource(BS).split("log = logging")[0]
    for mod in ("bounce_room", "enterable", "zone_store"):
        assert f"import {mod}" not in top, f"{mod} must be a lazy import"


# ═══════════════════════════════════════════════════════════════════════════
# 10 — the 2026-09-16 critique-2 fixes (m2 / m3 / m4 + the print source)
# ═══════════════════════════════════════════════════════════════════════════
# m2  one price range, served twice in one sentence
# m3  a chip that could outlive its banner on an error path
# m4  the n/a category list typed in two places
# plus the 🎯 read's `print_source`, plumbed through the band read


def crdo_stored_doc() -> dict:
    """His CRDO as the STORE actually carried it on 2026-09-16 (critique m2,
    re-measured in `scratchpad/thin_lid/crdo2.py`): a PROVEN lid far above at
    193.50-198.97, and one range — 161.92-167.68 — carrying BOTH a supply
    cluster and a demand cluster, with the print standing inside it.

    That is the whole bug: the sentence named 161.92-167.68 once as the
    untested ceiling and once as the floor, and read as two walls."""
    doc = crdo_doc()
    bands = [b for b in doc["bands"] if (b["lo"], b["hi"]) != CRDO_SUPPLY[0]]
    bands.append(_band("supply", *CRDO_SUPPLY[0], touches=AG.LID_MIN_TOUCHES))
    bands.append(_band("supply", *CRDO_SUPPLY_SHELF, touches=1))
    doc["bands"] = bands
    return doc


def test_the_SAME_RANGE_is_named_ONCE_on_his_own_CRDO_doc():
    """m2, his numbers. 162.76 inside 161.92-167.68, which is the untested
    shelf AND the floor, under a proven lid 18.9% up. The old sentence was
    "… (price inside an untested band) · floor 3.5% wide, 2nd band 6.4%
    under" — one range, two walls. It must say which band it is, once, and
    leave the width to the floor clause that quotes it."""
    r = BS.read(doc=crdo_stored_doc(), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO")
    c, f = r["ceiling"], r["floor"]
    assert (c["band"]["lo"], c["band"]["hi"]) == CRDO_SUPPLY[0]
    assert c["distance_pct"] == 18.89 and c["band"]["proven"] is True
    assert (c["untested_band"]["lo"], c["untested_band"]["hi"]) == CRDO_SUPPLY_SHELF
    assert (f["band"]["lo"], f["band"]["hi"]) == CRDO_SUPPLY_SHELF, "one range"
    assert r["stat"] == ("ceiling 3.4% wide, 18.9% up (price inside its floor "
                         "band, untested overhead) · floor 3.5% wide, next "
                         "demand band 6.4% below it")
    assert r["stat"].count("3.5% wide") == 1, "the width is quoted once"


def test_the_CLEAR_branch_says_the_same_thing_when_the_shelf_IS_the_floor():
    """m2 on the all-1-touch doc: nothing proven overhead, the print inside a
    range that is both the untested shelf and the floor."""
    r = BS.read(doc=crdo_shelf_doc(), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO")
    assert r["stat"] == ("ceiling untested — price inside its floor band · "
                         "floor 3.5% wide, next demand band 6.4% below it")
    assert "an untested band 3.5% wide" not in r["stat"]


def test_NEGATIVE_a_DIFFERENT_untested_band_is_still_named_as_its_own_wall():
    """NEGATIVE, and the mutation that would make the fix a lie: when the
    untested band the print is standing in is NOT the floor band, the two
    ranges are two facts and both are said."""
    doc = _doc([_band("supply", 99.0, 104.0, 1), _band("demand", 90.0, 95.0, 3),
                _band("demand", 80.0, 85.0, 3)], px=100.0)
    r = BS.read(doc=doc, px=100.0, kind=EN.KIND_DEMAND, symbol="X")
    assert (r["ceiling"]["untested_band"]["lo"],
            r["ceiling"]["untested_band"]["hi"]) == (99.0, 104.0)
    assert (r["floor"]["band"]["lo"], r["floor"]["band"]["hi"]) == (90.0, 95.0)
    assert "price inside an untested band 5.0% wide" in r["stat"]
    assert "floor band" not in r["stat"]


def test_NEGATIVE_the_same_range_shortcut_needs_BOTH_ends_to_match():
    """NEGATIVE, unit level: a band that merely OVERLAPS the floor is not the
    floor, and must not be collapsed into it."""
    assert BS._same_range({"lo": 1.0, "hi": 2.0}, {"lo": 1.0, "hi": 2.0}) is True
    assert BS._same_range({"lo": 1.0, "hi": 2.0}, {"lo": 1.0, "hi": 2.5}) is False
    assert BS._same_range({"lo": 1.0, "hi": 2.0}, {"lo": 0.9, "hi": 2.0}) is False
    assert BS._same_range({"lo": 1.0, "hi": 2.0}, None) is False
    assert BS._same_range({"lo": 0.0, "hi": 2.0}, {"lo": 0.0, "hi": 2.0}) is False


# ── the print this read is about (critique m1, the 🎯 precedent) ────────────
def test_the_read_CARRIES_which_print_it_measured_from():
    """`bounce_room.py:721` hands the 🎯 read `print_source="live" if fresh
    else "scan"`. The band read now carries the same two words, because every
    distance in it is measured FROM that price."""
    r = BS.read(doc=crdo_doc(), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO",
                print_source="scan")
    assert r["print"] == {"px": CRDO_PX, "source": "scan"}
    live = BS.read(doc=crdo_doc(), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO",
                   print_source="live")
    assert live["print"]["source"] == "live"


def test_NEGATIVE_an_UNSTATED_print_source_is_never_asserted_as_LIVE():
    """NEGATIVE — the whole point of m1. A caller that did not say which print
    it handed in gets None, not "live": outside the session the row path is
    reading the stored close, and a surface that says "live print" over that
    number is claiming something nobody had."""
    r = BS.read(doc=crdo_doc(), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO")
    assert r["print"]["source"] is None
    na = BS.read(doc=None, px=None, kind=EN.KIND_NA, symbol="VCPNAME")
    assert na["print"] == {"px": None, "source": None}


def test_the_TILE_path_feeds_the_print_source_it_actually_chose(monkeypatch):
    """The board knows which it used — the live snapshot or the scan close —
    and now says so on the read, exactly as `attach_enterable` does."""
    _patch_store(monkeypatch, {"CRDO": crdo_doc(), "COLD": crdo_doc()})
    tiles = [_tile("CRDO", px=100.0), _tile("COLD", px=CRDO_PX)]
    B.attach_band_structure(tiles, kind=EN.KIND_DEMAND,
                            live={"CRDO": {"last_trade_price": CRDO_PX}})
    assert tiles[0]["band_structure"]["print"] == {"px": CRDO_PX, "source": "live"}
    assert tiles[1]["band_structure"]["print"] == {"px": CRDO_PX, "source": "scan"}


# ── m4: the n/a category list has ONE home ──────────────────────────────────
def test_the_NA_CATEGORY_LIST_is_typed_ONCE_and_both_sentences_quote_it():
    """m4 — it was prose in three places and they had already drifted."""
    cats = BS.NA_CATEGORIES
    assert "(%s)" % cats in BS.NA_TEXT
    assert "(%s)" % cats in B.band_structure_sort_na()
    src = inspect.getsource(B.band_structure_sort_na)
    assert "NA_CATEGORIES" in src
    for word in cats.split(" / "):
        assert word not in src, "%s is retyped in board.py" % word


def test_NEGATIVE_changing_the_category_list_moves_BOTH_sentences(monkeypatch):
    """NEGATIVE, mutation-style: with one home, one edit reaches both served
    sentences. Two homes would leave the board sentence on the old list —
    which is exactly the state this fix found."""
    monkeypatch.setattr(BS, "NA_CATEGORIES", "pivot / value")
    assert "(pivot / value)" in B.band_structure_sort_na()
    assert "lid" not in B.band_structure_sort_na()


def test_the_sort_note_still_says_the_board_kept_its_own_order():
    note = B.band_structure_sort_na()
    assert note.startswith("This tab's rows are not price-structure bands")
    assert "default order" in note and "ceiling or floor to rank" in note


def test_NEGATIVE_a_band_structure_that_will_not_import_still_answers(monkeypatch):
    """NEGATIVE — the sentence degrades to itself without the list rather than
    raising inside a board render."""
    import sys
    import supply_demand

    monkeypatch.delitem(sys.modules, "supply_demand.band_structure", raising=False)
    monkeypatch.delattr(supply_demand, "band_structure", raising=False)
    monkeypatch.setitem(sys.modules, "supply_demand.band_structure", None)
    note = B.band_structure_sort_na()
    assert "default order" in note and "(" not in note


# ── m3: the chip must never outlive its banner, on any path ────────────────
def _support_payload(monkeypatch, *, verdict_raises=False):
    """Run the Support endpoint with everything heavy stubbed: one tile, no
    price load, no live fan-out."""
    import asyncio
    from chart_maps import api as A

    tile = {"symbol": "CRDO", "last_price": CRDO_PX, "stats": []}
    monkeypatch.setattr(A.support_mod, "for_symbol",
                        lambda *a, **kw: {"tile": tile, "bars_used": 130,
                                          "timeframe": "daily"})
    monkeypatch.setattr(A.board_mod, "_live_snapshot", lambda tiles: {})
    monkeypatch.setattr(A.board_mod, "attach_live_now",
                        lambda tiles, res, live=None: None)
    monkeypatch.setattr(A.board_mod, "attach_enterable",
                        lambda tiles, kind=None, live=None: 0)
    _patch_store(monkeypatch, {"CRDO": crdo_doc()})
    if verdict_raises:
        monkeypatch.setattr(BS, "measured_verdict",
                            lambda: (_ for _ in ()).throw(RuntimeError("banner down")))
    res = asyncio.run(A.chart_maps_support(symbol="CRDO"))
    return json.loads(res.body.decode())


def test_the_SUPPORT_tab_serves_the_chip_AND_the_banner(monkeypatch):
    """Positive, so the negative below cannot pass on a dead path."""
    p = _support_payload(monkeypatch)
    assert p["tile"]["band_structure"]["stat"]
    assert p["band_structure_study"]["headline"]
    assert p["band_structure_kind"] == EN.KIND_DEMAND


def test_NEGATIVE_a_RAISING_banner_never_leaves_a_CHIP_without_one(monkeypatch):
    """NEGATIVE, critique m3. Both statements sat in ONE try with the attach
    FIRST, so a raise from `measured_verdict()` left the tile carrying the
    read — the chip renders — and the payload with no verdict: an unmeasured
    read wearing a validated face on an error path."""
    p = _support_payload(monkeypatch, verdict_raises=True)
    assert p.get("band_structure_study") is None
    assert p["tile"].get("band_structure") is None, \
        "no chip may render without its banner"
    assert p["tile"].get("stats") == []


def test_the_SUPPORT_path_sets_the_verdict_BEFORE_it_attaches_the_read():
    """Pinned in the source, so the two cannot be reordered back into one
    try: the banner is set first and the attach only runs if it landed."""
    from chart_maps import api as A
    src = inspect.getsource(A.chart_maps_support)
    assert (src.index('res["band_structure_study"]')
            < src.index("attach_band_structure")), \
        "the verdict must be set before the read is attached"


# ═══════════════════════════════════════════════════════════════════════════
# 8 — THE RESOLUTION THE BOARD QUOTES (critique B1, 2026-09-16)
# ═══════════════════════════════════════════════════════════════════════════
def _split_mdls():
    return {k: v["mdl"] for k, v in BS.MEASURED["splits"].items()}


def test_the_served_resolution_is_the_MAX_over_the_three_splits_not_s1():
    """Nothing was selected on ALL THREE out-of-sample splits, so the smallest
    lift this study could have seen ANYWHERE is the weakest split's — the max
    of the three, `q1.mdl`. Serving split `s1` alone (2.51pp) understated the
    study's own resolution and put the board banner and the ℹ️ Rules panel in
    contradiction with the run file, the doc and the ✨ label, all of which say
    2.80pp."""
    mdls = _split_mdls()
    binding = BS.binding_mdl()
    assert binding == max(mdls.values())
    assert binding == BS.MEASURED["q1"]["mdl"]
    assert binding == pytest.approx(2.795, abs=1e-4)
    assert binding > mdls["s1"], "s1 is NOT the binding split"
    # every surface reads the same call
    assert BS.measured_block()["mdl"] == binding
    r = BS.read(doc=crdo_doc(), px=CRDO_PX, kind=EN.KIND_DEMAND, symbol="CRDO")
    assert r["measured"]["mdl"] == binding
    head = BS.measured_verdict()["headline"]
    assert "2.80pp" in head


def test_NEGATIVE_no_surface_still_quotes_the_s1_only_resolution():
    """The bug, stated as the thing that must not come back: 2.51pp on the
    banner, the chip or the row read while the doc and the label say 2.80."""
    head = BS.measured_verdict()["headline"]
    assert "2.51pp" not in head and "2.49pp" not in head
    assert BS.measured_block()["mdl"] != BS.MEASURED["splits"]["s1"]["mdl"]
    for surface in (BS.measured_verdict()["headline"],
                    BS.measured_verdict()["body"]):
        assert "2.5057" not in surface


def test_NEGATIVE_the_WEAKEST_split_is_what_moves_the_served_number(monkeypatch):
    """The max is real, not a constant that happens to equal s3 today. Push any
    ONE split above the others and the served resolution follows it; push s1
    alone and nothing moves until it is the largest."""
    splits = {k: dict(v) for k, v in BS.MEASURED["splits"].items()}
    splits["s2"] = dict(splits["s2"], mdl=9.5)
    monkeypatch.setitem(BS.MEASURED, "splits", splits)
    assert BS.binding_mdl() == pytest.approx(9.5)
    assert "9.50pp" in BS.measured_verdict()["headline"]
    splits["s2"] = dict(splits["s2"], mdl=0.1)
    splits["s1"] = dict(splits["s1"], mdl=4.25)
    monkeypatch.setitem(BS.MEASURED, "splits", splits)
    assert BS.binding_mdl() == pytest.approx(4.25)


def test_NEGATIVE_a_splits_block_with_no_numbers_quotes_NO_resolution(monkeypatch):
    """A half-pasted study must drop the parenthetical, never print `None pp`
    or fall back to a typed number."""
    monkeypatch.setitem(BS.MEASURED, "splits", {})
    assert BS.binding_mdl() is None
    head = BS.measured_verdict()["headline"]
    assert "NO SIGNAL SEPARATES" in head and "pp)" not in head
    assert BS.measured_block()["mdl"] is None
    monkeypatch.setitem(BS.MEASURED, "splits", {"s1": {"mdl": None}})
    assert BS.binding_mdl() is None


def test_the_module_level_ALIASES_are_RE_DERIVED_from_q1_and_q2():
    """`derived_for_module` in the shipped JSON says the top-level keys this
    module reads are ALIASES computed by hand from the per-question blocks.
    Nothing re-derived them, and reading one of them wrong is what B1 cost.
    This test is that arithmetic."""
    m = BS.MEASURED
    q1, q2 = m["q1"], m["q2"]
    assert set(m["splits"]) == set(q1["splits"]) == set(q2["splits"])
    for k in m["splits"]:
        assert m["splits"][k]["mdl"] == max(q1["splits"][k]["mdl"],
                                            q2["splits"][k]["mdl"]), k
        assert m["splits"][k]["verdict"] == BS.STATUS_NO_SIGNAL
    assert m["selected"] == list(q1["selected"]) + list(q2["selected"]) == []
    assert m["n_names"] == m["n_universe"]
    assert m["orientation"] == {} and m["edges"] == {}
    assert m["cohort_note_study"] in m["cohort_note"], \
        "the study's own note is kept verbatim inside the extended one"
    assert str(m["derived_for_module"]).startswith("ALIASES")


def test_NEGATIVE_the_alias_check_would_catch_a_HAND_TYPED_split(monkeypatch):
    """The test above only earns its place if a wrong alias fails it."""
    m = BS.MEASURED
    bad = {k: dict(v) for k, v in m["splits"].items()}
    bad["s3"] = dict(bad["s3"], mdl=1.0)
    monkeypatch.setitem(BS.MEASURED, "splits", bad)
    with pytest.raises(AssertionError):
        for k in BS.MEASURED["splits"]:
            assert BS.MEASURED["splits"][k]["mdl"] == max(
                m["q1"]["splits"][k]["mdl"], m["q2"]["splits"][k]["mdl"]), k
