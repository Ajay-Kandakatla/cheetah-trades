"""Deep Demand — every number says which print it is on (2026-09-17).

Ajay, on APLD: "Some of these are not accurate. APLD is showing wrong in Deep
demand" — then, once the numbers were in front of him, "Ok it should be ok to
be there. but I know its not 5% band thats ok.."

THE BUG, verified live that morning: demand band 24.03-24.41, scan close 24.39
(INSIDE it), pre-market print 25.76 (+5.24% over the band top). The tile said,
adjacently and unlabelled, that the same band was "0.8% under" (a closed-print
number, and in fact the GAP between two OTHER bands) and "5.24% above" (a live
print), and badged the name "🩹 Reclaiming 2nd band" while the tape had
already left it. 8 of the 10 deep tiles carrying a pre-market print that
morning were above their band.

HIS DECISION: the name STAYS. `BOUNCE_DONE_PCT` (7.0) is untouched, nothing
about who qualifies moves — ONLY the words change. These tests hold that line
in both directions: the sentences must be honest, and the cohort must not move.

  W1  the three position cases — in band / a hair above / well above
  W2  APLD and STX reproduce sentences that do not contradict themselves
  W3  NEGATIVE — no arrival verb anywhere above the band
  W4  NEGATIVE — missing inputs render shorter, never raise, never "0%"
  W5  NEGATIVE — no live print says "on the close", and never says "live"
  W6  NEGATIVE — "2nd band" cannot mean two things on one tile
  W7  NEGATIVE — reversal, never bounce; the module is pure; no thresholds
  W8  the board says which print its position numbers came from
  W9  REGRESSION PIN — the 7% tolerance and the qualifying set are untouched
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chart_maps import board as B  # noqa: E402
from supply_demand import band_structure as BS  # noqa: E402
from supply_demand import deep_demand_wording as DW  # noqa: E402

# The board fixtures the chart-maps suite already owns — imported, never
# re-typed, so a fixture change there reaches here.
from test_chart_maps import (  # noqa: E402,F401
    _deep_row, _frame, _sales,
    prices, reentry_stub, sales_stub,
)

# The verbs that must never describe a print the tape has already carried out
# of the band. `reclaim` covers "reclaiming" and "reclaimed".
ARRIVAL_VERBS = re.compile(r"entering|arriv|reclaim", re.I)


def _one(rows, prices, reentry_stub, sales_stub, live=None, monkeypatch=None,
         **kw):
    reentry_stub["deep_rows"] = rows
    for r in rows:
        prices[r["symbol"]] = _frame(200)
        sales_stub[r["symbol"]] = _sales("steady", 9.0)
    if monkeypatch is not None:
        monkeypatch.setattr(B, "_live_last",
                            lambda syms, rows=None, _l=dict(live or {}): _l)
        # No bulk rows -> no `_approach_badge`, so the position badge is the
        # tile's own and `reclaiming` can only come from the scan flag.
        monkeypatch.setattr(B, "_live_rows", lambda syms: {})
    kw.setdefault("limit", 5)
    kw.setdefault("min_tier", "any")
    kw.setdefault("min_room", 0)
    return B.board("deep_demand", **kw)


def _code_of(obj) -> str:
    """The CODE, with every docstring and comment stripped.

    A source guard must test what a module DOES, not what it explains: this
    file's own subject is a wording bug, so the docstrings quote every phrase
    the code must not contain.
    """
    import ast
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(obj)))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(body, list) and body
                and isinstance(body[0], ast.Expr)
                and isinstance(getattr(body[0], "value", None), ast.Constant)
                and isinstance(body[0].value.value, str)):
            body.pop(0)
    return ast.unparse(tree)


def _strings_in(obj) -> list:
    """Every string literal the object's code can actually emit."""
    import ast
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(obj)))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _tile_strings(tile) -> str:
    """Every string on the tile a human reads, in one blob."""
    return " ".join([tile.get("why") or ""]
                    + [b.get("text") or "" for b in tile.get("badges") or []]
                    + [b.get("label") or "" for b in tile.get("bands") or []]
                    + [str(s.get("k")) + " " + str(s.get("v"))
                       for s in tile.get("stats") or []])


# ---------------------------------------------------------------------------
# W1 — the three position cases the board actually served that morning
# ---------------------------------------------------------------------------
def test_w1_still_inside_the_band_keeps_its_arrival_language():
    """WERN was the one name still in its band. Nothing about the in-band
    sentence needed fixing, and it must not drift."""
    why = DW.why_sentence(levels_broken=1, level=2, below_top_pct=7.0,
                          dist_pct=-0.5, reclaiming=False,
                          prev_close_known=False, dist_basis=DW.LIVE_BASIS,
                          sales_growth_pct=24.0)
    assert "now in its 2nd demand level on the live print" in why
    assert DW.badge_text(2, -0.5, False) == "🩹 In its 2nd demand level"
    assert DW.band_label(2, -0.5, False, "reached") == "2nd demand level · price inside"
    assert DW.verb_phrase(-0.5, False, DW.LIVE_BASIS) == "standing in it"
    # Still inside AND reclaimed: the arrival language stays, said as a prior-close
    # fact, because the print really is in the band.
    assert DW.badge_text(2, 0.0, True) == "🩹 Back in its 2nd demand level from below"
    assert DW.band_label(2, 0.0, True, "reached") == "2nd demand level · back in from below"


def test_w1_a_hair_above_the_band_reads_the_same_as_far_above_the_number_carries_it():
    """HGV was +0.03% out. The wording must not change shape at some invented
    distance — the number says how far, the words say which side."""
    hair = DW.why_sentence(levels_broken=3, level=4, below_top_pct=16.0,
                           dist_pct=0.03, reclaiming=False,
                           prev_close_known=False, dist_basis=DW.LIVE_BASIS,
                           sales_growth_pct=7.0)
    far = DW.why_sentence(levels_broken=3, level=4, below_top_pct=16.0,
                          dist_pct=5.24, reclaiming=False,
                          prev_close_known=False, dist_basis=DW.LIVE_BASIS,
                          sales_growth_pct=7.0)
    assert "now 0.03% above its 4th demand level on the live print" in hair
    assert "now 5.24% above its 4th demand level on the live print" in far
    assert hair.replace("0.03", "X") == far.replace("5.24", "X")
    assert DW.badge_text(4, 0.03, False) == "🩹 Above its 4th demand level"


def test_w1_the_board_renders_all_three_cases_off_real_rows(
        prices, reentry_stub, sales_stub, monkeypatch):
    """In band (no live), a hair above and well above — on the tile, through
    the real builder. Band top is 85.0 on the shared fixture."""
    rows = [_deep_row("INB"), _deep_row("HAIR"), _deep_row("FAR")]
    out = _one(rows, prices, reentry_stub, sales_stub,
               live={"HAIR": 85.03, "FAR": 89.5}, monkeypatch=monkeypatch)
    by = {t["symbol"]: t for t in out["tiles"]}
    assert "now in its 2nd demand level on the close" in by["INB"]["why"]
    assert by["INB"]["left_band"] is False and by["INB"]["print_basis"] == "scan"
    for sym in ("HAIR", "FAR"):
        t = by[sym]
        assert t["print_basis"] == "live" and t["left_band"] is True
        assert "above its 2nd demand level on the live print" in t["why"]
        assert any(b["text"] == "🩹 Above its 2nd demand level"
                   for b in t["badges"])
        assert "2nd demand level · price above it" in [b.get("label")
                                                       for b in t["bands"]]
    assert by["HAIR"]["dist_pct"] == 0.04 and by["FAR"]["dist_pct"] == 5.03


# ---------------------------------------------------------------------------
# W2 — his two names, with the numbers off the wire
# ---------------------------------------------------------------------------
def test_w2_apld_reproduces_a_sentence_that_does_not_contradict_itself():
    """APLD, 2026-09-17: band 24.03-24.41, close 24.39, live 25.76, crossed 1
    level 10% under its floor, reclaimed on yesterday's close."""
    why = DW.why_sentence(levels_broken=1, level=2, below_top_pct=10.0,
                          dist_pct=5.24, reclaiming=True,
                          prev_close_known=True, dist_basis=DW.LIVE_BASIS,
                          sales_growth_pct=877.0)
    assert why == (
        "broke its 1st demand level (10% under that level's floor on the "
        "close), now 5.24% above its 2nd demand level on the live print "
        "(yesterday closed under it) — sales +877% YoY say the business "
        "didn't break with the price")
    # Both numbers carry their basis, so neither can be read against the other
    assert why.count("on the close") == 1 and why.count("on the live print") == 1
    # and the tile no longer claims an arrival it has left
    assert not ARRIVAL_VERBS.search(why)
    assert DW.badge_text(2, 5.24, True) == "🩹 Above its 2nd demand level"
    assert DW.band_label(2, 5.24, True, "reached") == "2nd demand level · price above it"


def test_w2_stx_the_worst_pairing_on_the_wire_is_readable():
    """STX served "broke its 1st demand band (1% below it), now 3.8% above the
    2nd band" — two numbers that are impossible together until each says which
    print it is on."""
    why = DW.why_sentence(levels_broken=1, level=2, below_top_pct=1.0,
                          dist_pct=3.8, reclaiming=False,
                          prev_close_known=False, dist_basis=DW.LIVE_BASIS,
                          sales_growth_pct=12.0)
    assert "1% under that level's floor on the close" in why
    assert "now 3.8% above its 2nd demand level on the live print" in why
    assert "below it" not in why, "the old unanchored phrase is gone"


# ---------------------------------------------------------------------------
# W3 — NEGATIVE: no arrival verb above the band
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("dist", [0.01, 0.5, 3.8, 5.45, 6.99])
def test_w3_negative_nothing_above_the_band_is_described_as_arriving(dist):
    """Every distance under the 7% drop tolerance — the whole range a tile can
    legitimately sit at while still on the board."""
    for phase in ("reached", "approaching"):
        for reclaiming in (True, False):
            strings = [
                DW.why_sentence(levels_broken=1, level=2, below_top_pct=9.0,
                                dist_pct=dist, reclaiming=reclaiming,
                                prev_close_known=True,
                                dist_basis=DW.LIVE_BASIS, sales_growth_pct=9.0),
                DW.badge_text(2, dist, reclaiming),
                DW.band_label(2, dist, reclaiming, phase),
                DW.verb_phrase(dist, reclaiming, DW.LIVE_BASIS),
            ]
            for s in strings:
                assert not ARRIVAL_VERBS.search(s), s


def test_w3_negative_the_reclaim_clause_is_dropped_once_the_print_is_out():
    """`reclaiming` is yesterday's close. Above the band it may be SAID as
    that, but it may never dress the badge or the band label."""
    assert DW.badge_text(2, 5.24, True) == DW.badge_text(2, 5.24, False)
    assert DW.band_label(2, 5.24, True, "reached") == DW.band_label(2, 5.24, False, "reached")
    why = DW.why_sentence(levels_broken=1, level=2, below_top_pct=9.0,
                          dist_pct=5.24, reclaiming=True, prev_close_known=True,
                          dist_basis=DW.LIVE_BASIS, sales_growth_pct=9.0)
    assert "(yesterday closed under it)" in why, "the fact is kept, labelled"


def test_w3_negative_the_board_never_badges_a_reclaim_it_has_left(
        prices, reentry_stub, sales_stub, monkeypatch):
    row = _deep_row("RECL")
    row["deep_demand"]["reclaiming"] = True
    out = _one([row], prices, reentry_stub, sales_stub, live={"RECL": 89.5},
               monkeypatch=monkeypatch)
    t = out["tiles"][0]
    assert not ARRIVAL_VERBS.search(_tile_strings(t)), _tile_strings(t)
    assert "yesterday closed under it" in t["why"]


# ---------------------------------------------------------------------------
# W4 — NEGATIVE: a missing field renders shorter, never raises
# ---------------------------------------------------------------------------
def test_w4_negative_no_below_top_pct_drops_the_clause_it_cannot_measure():
    why = DW.why_sentence(levels_broken=1, level=2, below_top_pct=None,
                          dist_pct=-1.0, reclaiming=False,
                          prev_close_known=False, dist_basis=DW.SCAN_BASIS,
                          sales_growth_pct=9.0)
    assert why.startswith("broke its 1st demand level, now in its 2nd demand level")
    assert "0%" not in why and "(" not in why.split("—")[0]


def test_w4_negative_no_dist_says_position_unknown_never_zero_never_in_band():
    why = DW.why_sentence(levels_broken=2, level=3, below_top_pct=12.0,
                          dist_pct=None, reclaiming=False,
                          prev_close_known=False, dist_basis=DW.LIVE_BASIS,
                          sales_growth_pct=9.0)
    assert "position unknown" in why
    assert "0%" not in why and "in its 3rd demand level" not in why
    assert DW.position_phrase(None, 3, DW.LIVE_BASIS) == "position unknown"
    assert DW.verb_phrase(None, True, DW.LIVE_BASIS) == ""
    assert DW.band_label(3, None, True, "reached") == "3rd demand level"


@pytest.mark.parametrize("bad", [None, "", "n/a", float("nan"), {}])
def test_w4_negative_junk_inputs_render_a_shorter_sentence_and_never_raise(bad):
    """The 2026-09-16 outage was an f-string evaluated outside its guard: in a
    board-wide loop that takes every OTHER tile down too."""
    why = DW.why_sentence(levels_broken=1, level=2, below_top_pct=bad,
                          dist_pct=bad, reclaiming=True, prev_close_known=True,
                          dist_basis=bad if isinstance(bad, str) else "",
                          sales_growth_pct=bad)
    assert isinstance(why, str) and why
    assert "None" not in why and "nan" not in why
    assert DW.badge_text(2, bad, True) and DW.band_label(2, bad, True, "reached")


def test_w4_negative_a_row_with_no_price_and_no_band_still_renders(
        prices, reentry_stub, sales_stub, monkeypatch):
    """No `second_band`, no `below_top_pct`, `last_price` None — the tile must
    come back, shorter and honest, rather than taking the board with it."""
    row = _deep_row("THIN")
    row["last_price"] = None
    row["deep_demand"].pop("below_top_pct")
    row["deep_demand"]["second_band"] = {"lo": None, "hi": None}
    out = _one([row], prices, reentry_stub, sales_stub, live={},
               monkeypatch=monkeypatch)
    assert out["tiles"], "a thin row must not empty the board"
    t = out["tiles"][0]
    assert "None" not in _tile_strings(t)


def test_w4_negative_a_reclaim_with_no_prior_close_is_never_asserted():
    assert DW.prior_close_note(True, False) == ""
    why = DW.why_sentence(levels_broken=1, level=2, below_top_pct=9.0,
                          dist_pct=-1.0, reclaiming=True,
                          prev_close_known=False, dist_basis=DW.SCAN_BASIS,
                          sales_growth_pct=9.0)
    assert "yesterday" not in why


# ---------------------------------------------------------------------------
# W5 — NEGATIVE: no live print falls back to the close, and says so
# ---------------------------------------------------------------------------
def test_w5_negative_without_a_live_print_every_sentence_says_on_the_close():
    why = DW.why_sentence(levels_broken=1, level=2, below_top_pct=9.0,
                          dist_pct=1.96, reclaiming=False,
                          prev_close_known=False, dist_basis=DW.SCAN_BASIS,
                          sales_growth_pct=9.0)
    assert "now 1.96% above its 2nd demand level on the close" in why
    assert "live" not in why


def test_w5_negative_the_board_calls_a_scan_fallback_scan_not_live(
        prices, reentry_stub, sales_stub, monkeypatch):
    """`_live_px` falls back to the scan's `last_price`, so asking IT whether
    the tape is up would call every tile "live" on a dead feed."""
    out = _one([_deep_row("NOLIVE")], prices, reentry_stub, sales_stub,
               live={}, monkeypatch=monkeypatch)
    t = out["tiles"][0]
    assert t["print_basis"] == "scan"
    assert "on the live print" not in _tile_strings(t)
    assert out["position_basis"] == {
        "live": 0, "scan": 1,
        "note": DW.basis_note(DW.SCAN_BASIS, 0, 1)}


def test_w5_negative_an_unknown_basis_says_nothing_rather_than_guessing():
    assert DW.basis_word("") == "" and DW.basis_word("whatever") == ""
    assert DW.position_phrase(2.0, 2, "whatever") == "2% above its 2nd demand level"


# ---------------------------------------------------------------------------
# W6 — NEGATIVE: one noun, one band
# ---------------------------------------------------------------------------
def test_w6_negative_the_phrase_2nd_band_never_names_two_bands_on_one_tile(
        prices, reentry_stub, sales_stub, monkeypatch):
    out = _one([_deep_row("NOUN")], prices, reentry_stub, sales_stub,
               live={"NOUN": 86.7}, monkeypatch=monkeypatch)
    blob = _tile_strings(out["tiles"][0])
    assert blob.count("2nd band") == 0, blob
    assert "its 2nd demand level" in blob


def test_w6_negative_the_bands_stat_names_the_band_it_actually_measures():
    """`gap_pct` is band1.lo -> band2.hi: the fall THROUGH the first band, not
    a distance from price. The number is unchanged; the noun is not."""
    read = {"applicable": True,
            "ceiling": {"state": "PROVEN", "height_pct": 3.5, "distance_pct": 0.5},
            "floor": {"height_pct": 3.2, "gap_pct": 6.4}}
    line = BS.stat_line(read)
    assert line == ("ceiling 3.5% wide, 0.5% up · floor 3.2% wide, "
                    "next demand band 6.4% below it")
    assert "2nd band" not in line
    read["floor"] = {"height_pct": 3.2, "gap_pct": None}
    assert BS.stat_line(read).endswith("floor 3.2% wide, no band under it")
    assert not [t for t in _strings_in(BS.stat_line) if "2nd band" in t], \
        "the phrase cannot come back through another branch"


# ---------------------------------------------------------------------------
# W7 — NEGATIVE: the standing rules
# ---------------------------------------------------------------------------
def test_w7_negative_reversal_never_bounce_on_anything_he_reads(
        prices, reentry_stub, sales_stub, monkeypatch):
    src = inspect.getsource(DW)
    rendered = [ln for ln in src.splitlines() if '"' in ln or "'" in ln]
    out = _one([_deep_row("REV")], prices, reentry_stub, sales_stub,
               live={"REV": 86.7}, monkeypatch=monkeypatch)
    assert not re.search(r"bounc", _tile_strings(out["tiles"][0]), re.I)
    for fn in (DW.why_sentence(levels_broken=1, level=2, below_top_pct=9.0,
                               dist_pct=1.0, reclaiming=True,
                               prev_close_known=True,
                               dist_basis=DW.LIVE_BASIS, sales_growth_pct=9.0),
               DW.badge_text(2, 1.0, True), DW.band_label(2, 1.0, True, "reached"),
               DW.basis_note(DW.LIVE_BASIS, 1, 2)):
        assert not re.search(r"bounc", fn, re.I)
    assert rendered, "the module does carry strings"


def test_w7_negative_the_wording_module_is_pure():
    """Strings in, strings out. A module that can read a store or a clock can
    disagree with the board that called it."""
    code = _code_of(DW)
    for banned in ("zone_store", "prices", "datetime", "requests", "chart_maps",
                   "pymongo", "time.", "open(", "load_latest"):
        assert banned not in code, banned
    assert "from supply_demand.deep_demand import ordinal" in code


def test_w7_negative_the_module_writes_no_distance_threshold():
    """It decides nothing about who is on the board, so it carries no number
    that could quietly become one. Parsed, not grepped: the only numeric
    literals allowed are the 0/1 of its own guards and slices."""
    import ast
    tree = ast.parse(_code_of(DW))
    nums = [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool)]
    assert nums, "the guards do use 0 and 1"
    for v in nums:
        assert v in (0, 1) and isinstance(v, int), f"a number reached the wording module: {v!r}"


def test_w7_negative_the_ordinals_are_never_retyped():
    code = _code_of(DW)
    for lit in ("1st", "2nd", "3rd", "4th"):
        assert lit not in code, f"ordinal retyped: {lit}"
    assert "ordinal(" in code
    assert DW.band_noun(4) == "its 4th demand level"


# ---------------------------------------------------------------------------
# W8 — the board says which print its numbers came from
# ---------------------------------------------------------------------------
def test_w8_the_payload_counts_both_bases_and_the_note_says_it(
        prices, reentry_stub, sales_stub, monkeypatch):
    rows = [_deep_row(s) for s in ("L1", "L2", "L3", "S1", "S2")]
    out = _one(rows, prices, reentry_stub, sales_stub,
               live={"L1": 86.7, "L2": 86.0, "L3": 85.5}, monkeypatch=monkeypatch)
    assert len(out["tiles"]) == 5
    assert out["position_basis"]["live"] == 3
    assert out["position_basis"]["scan"] == 2
    assert out["position_basis"]["note"] in out["note"]
    assert "3 of 5 tiles" in out["note"] and "on the other 2" in out["note"]
    assert ("The level, the break and the reclaim are always read on the close."
            in out["note"])


def test_w8_negative_an_empty_board_says_nothing_rather_than_zero_of_zero(
        prices, reentry_stub, sales_stub, monkeypatch):
    assert DW.basis_note(DW.LIVE_BASIS, 0, 0) == ""
    out = _one([], prices, reentry_stub, sales_stub, live={},
               monkeypatch=monkeypatch)
    assert out["position_basis"] == {"live": 0, "scan": 0, "note": ""}
    assert "tiles here" not in out["note"]


def test_w8_negative_the_counts_can_never_exceed_the_page():
    assert "of 2 tiles" in DW.basis_note(DW.LIVE_BASIS, 9, 2)
    assert DW.basis_note(DW.LIVE_BASIS, "x", 2) == ""


# ---------------------------------------------------------------------------
# W9 — REGRESSION PIN: only the words changed
# ---------------------------------------------------------------------------
def test_w9_the_seven_percent_tolerance_is_untouched():
    """Ajay 2026-09-17: "Ok it should be ok to be there. but I know its not 5%
    band thats ok.." — the name stays, so the gate does not move."""
    assert B.BOUNCE_DONE_PCT == 7.0
    assert B.already_bounced(85.0 * 1.0701, 85.0) is True
    assert B.already_bounced(85.0 * 1.0699, 85.0) is False


def test_w9_the_qualifying_set_is_decided_by_the_gate_not_by_the_new_words(
        prices, reentry_stub, sales_stub, monkeypatch):
    """A name 6.99% off the band is ON the board and described as above it; a
    name 7.01% off is dropped by `drop_bounced`, exactly as before."""
    rows = [_deep_row("STAY"), _deep_row("GONE")]
    out = _one(rows, prices, reentry_stub, sales_stub,
               live={"STAY": 85.0 * 1.0699, "GONE": 85.0 * 1.0701},
               monkeypatch=monkeypatch)
    served = {t["symbol"] for t in out["tiles"]}
    assert served == {"STAY"}
    assert out["dropped_bounced"] == 1
    assert out["bounce_done_pct"] == B.BOUNCE_DONE_PCT
    t = out["tiles"][0]
    assert t["left_band"] is True, "on the board AND above its band — both true"
    assert "above its 2nd demand level on the live print" in t["why"]


def test_w9_negative_left_band_gates_nothing_and_orders_nothing():
    """`left_band` is descriptive. If it ever reaches a filter or a sort key,
    the board's membership starts moving with the wording."""
    src = inspect.getsource(B.deep_demand_tiles)
    assert '"left_band"' in src
    for banned in ("if left_band", "left_band and", "not left_band",
                   'sort(key=lambda t: t.get("left_band")'):
        assert banned not in src, banned
