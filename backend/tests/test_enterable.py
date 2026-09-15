"""🎯 ENTERABLE read — the verdict, the words, the fixture mirror, the guards.

Nothing here talks to Mongo. The fixture
`tests/fixtures/enterable_mirror_2026_09_15.json` is the ONE contract the
frontend's `lib/enterable.test.ts` partitions as well, so a verdict can never
mean two things on two surfaces.
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import re

import pytest

from supply_demand import alert_gates as AG
from supply_demand import enterable as EN
from supply_demand import explosive as EX
from supply_demand import premarket_entry as PE
from supply_demand import zone_edge as ZE

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(BACKEND, "tests", "fixtures", "enterable_mirror_2026_09_15.json")
MEASURED_JSON = os.path.join(BACKEND, "scripts", "entry_trigger_measured.json")
SRC = open(os.path.join(BACKEND, "supply_demand", "enterable.py")).read()
TREE = ast.parse(SRC)


def _code_of(name: str) -> str:
    """A function's BODY as code, docstring stripped — so a guard reads what the
    function does, never what its prose says about it."""
    fn = next(n for n in ast.walk(TREE)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    body = fn.body[1:] if ast.get_docstring(fn) else fn.body
    return "\n".join(ast.unparse(stmt) for stmt in body)


def _imports(module_level_only: bool) -> set:
    nodes = TREE.body if module_level_only else list(ast.walk(TREE))
    out = set()
    for n in nodes:
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            out |= {"%s.%s" % (n.module or "", a.name) for a in n.names}
    return out

with open(FIXTURE) as _fh:
    FIX = json.load(_fh)


# ── helpers ────────────────────────────────────────────────────────────────
def demand_band(lo=98.0, hi=100.0, touches=3):
    return {"kind": "demand", "lo": lo, "hi": hi, "touches": touches}


def supply_band(lo=130.0, hi=132.0, touches=3):
    return {"kind": "supply", "lo": lo, "hi": hi, "touches": touches}


def bands_with_room():
    return [demand_band(), supply_band()]


def doc_with_tail(bars, bands=None, prev_close=None):
    return {"bands": bands if bands is not None else bands_with_room(),
            "prev_close": prev_close,
            "feat": {"tail": bars}}


def bar(d, o, h, l, c, v=1_000_000.0):
    return {"date": d, "open": o, "high": h, "low": l, "close": c, "volume": v}


# ═══════════════════════════════════════════════════════════════════════════
# 1 — the constants are IMPORTED, the state words are not written down
# ═══════════════════════════════════════════════════════════════════════════
def test_every_constant_is_imported_and_no_threshold_is_typed():
    assert EN.READY is PE.GRADE_READY
    assert EN.WATCH is PE.GRADE_WATCH
    assert EN.BLOCKED is PE.GRADE_BLOCKED
    assert EN.VERDICT_RANK is PE.GRADE_ORDER
    assert EN.BLOCK_CODES == ("no_band", "no_break", "break_extended",
                              "proximity", "room", "floor")
    assert EN.WATCH_CODES == ("reclaim", "weak_day", "floor_unknown")
    for banned in ("ALERT_MIN_ROOM_PCT =", "ALERT_MAX_ABOVE_DEMAND_PCT =",
                   "= 5.0", "= 1.0", "RECLAIM_STOP_PCT =", "WEAK_DAY_LO_PCT ="):
        assert banned not in SRC, "enterable.py retypes %r" % banned
    # the room refusal quotes the ENFORCING constant, whatever it is set to
    assert ("%g%%" % AG.ALERT_MIN_ROOM_PCT) in EN.REASON_SHORT["room"]({})


def test_M4_the_floor_state_words_are_never_written_into_this_module():
    """A new sweep state must BLOCK by falling outside AG.FLOOR_HELD_STATES —
    which can only work if this file never hard-codes a state name."""
    for word in ("swept", "broken"):
        assert word not in SRC, "enterable.py types the floor state %r" % word
    assert "AG.FLOOR_HELD_STATES" in SRC


def test_grade_takes_no_mood_and_never_reads_one():
    params = list(inspect.signature(EN.grade).parameters)
    assert params == ["kind", "room_ok", "prox_ok", "floor_state", "drags", "survivor"]
    assert "mood" not in _code_of("grade")
    assert "mood" not in _code_of("assess")


# ═══════════════════════════════════════════════════════════════════════════
# 2 — the shared fixture: the partition, the counts, every grade case
# ═══════════════════════════════════════════════════════════════════════════
def test_KIND_BY_TAB_equals_the_fixture_the_frontend_mirrors():
    assert EN.KIND_BY_TAB == FIX["kind_by_tab"]
    assert set(FIX["kind_by_tab"].values()) == {EN.KIND_DEMAND, EN.KIND_SUPPLY_BREAK, EN.KIND_NA}


def test_the_fixture_partitions_into_the_served_order_with_unread_last():
    rows = FIX["rows"]
    shown = [r["symbol"] for r in rows
             if isinstance(r["read"], dict) and EN.is_shown(r["read"])]
    unread = [r["symbol"] for r in rows if not isinstance(r["read"], dict)]
    assert shown + unread == FIX["expected_shown_enterable"]

    hidden = [r for r in rows
              if isinstance(r["read"], dict) and not EN.is_shown(r["read"])]
    assert len(hidden) == FIX["expected_hidden"]
    assert len(unread) == FIX["expected_unread"]

    by_reason: dict = {}
    for r in hidden:
        key = r["read"]["reason_short"][0]
        by_reason[key] = by_reason.get(key, 0) + 1
    assert by_reason == FIX["expected_hidden_by_reason"]


def test_every_fixture_grade_case_is_reproduced_input_for_input():
    assert len(FIX["grade_cases"]) >= 15
    for case in FIX["grade_cases"]:
        i = case["in"]
        verdict, reasons = EN.grade(i["kind"], i["room_ok"], i["prox_ok"],
                                    i["floor_state"], i["drags"], i["survivor"])
        assert verdict == case["out"]["verdict"], case
        assert reasons == case["out"]["reasons"], case


def test_a_floor_state_nobody_has_shipped_yet_BLOCKS_and_names_the_gate():
    verdict, reasons = EN.grade(EN.KIND_DEMAND, True, True, "a_new_state", [], None)
    assert (verdict, reasons) == (EN.BLOCKED, ["floor_a_new_state"])
    text = EN.REASON_TEXT["floor"]({"floor_state": "a_new_state", "sweep": None})
    for state in AG.FLOOR_HELD_STATES:
        assert state in text
    assert "a_new_state" in text


# ═══════════════════════════════════════════════════════════════════════════
# 3 — assess: the demand read
# ═══════════════════════════════════════════════════════════════════════════
def test_no_demand_band_is_BLOCKED_with_every_gate_unknown():
    r = EN.assess(px=100.0, band=None, bands=bands_with_room())
    assert r["verdict"] == EN.BLOCKED and r["reasons"] == ["no_band"]
    assert r["gates"] == {"room_ok": None, "prox_ok": None, "floor_state": None,
                          "session_low": False}
    assert r["band"] is None and r["room"] is None
    assert r["reason_text"] == ["no demand band at or below the print"]


def test_a_failed_proximity_gate_BLOCKS_even_when_a_drag_is_present():
    """A gate failure is not softened by a drag — the drag would only ever make
    it WATCH, and a blocked row is blocked."""
    r = EN.assess(px=140.0, band=demand_band(), bands=bands_with_room(),
                  prev_close=150.0, day_low=139.0, floor_state="intact")
    assert r["verdict"] == EN.BLOCKED
    assert "proximity" in r["reasons"]
    assert r["gates"]["prox_ok"] is False


def test_a_print_inside_overhead_supply_is_BLOCKED_on_room():
    bands = [demand_band(lo=130.0, hi=131.0), supply_band(lo=130.0, hi=132.0)]
    r = EN.assess(px=131.0, band=demand_band(lo=130.0, hi=131.0), bands=bands,
                  prev_close=130.5, floor_state="intact")
    assert r["verdict"] == EN.BLOCKED and "room" in r["reasons"]
    assert r["room"]["state"] == "IN_BAND"
    assert ("%g%%" % AG.ALERT_MIN_ROOM_PCT) in r["reason_short"][r["reasons"].index("room")]


def test_the_reclaim_drag_is_read_from_dir_never_from_the_display_tag():
    tagged = {"tag": "↑ reclaiming the band from below", "dir": "bouncing"}
    machine = {"tag": "↑ reversal off", "dir": "reclaiming"}
    common = dict(px=100.0, band=demand_band(), bands=bands_with_room(),
                  prev_close=100.0, floor_state="intact")
    assert EN.assess(approach=tagged, **common)["reasons"] == []
    assert EN.assess(approach=machine, **common)["reasons"] == ["reclaim"]


def test_the_weak_day_edges_are_the_imported_measured_ones():
    common = dict(band=demand_band(), bands=bands_with_room(), floor_state="intact",
                  approach={"dir": "bouncing"}, px=100.0, room_ok=True, prox_ok=True)
    for pct in (PE.WEAK_DAY_LO_PCT, PE.WEAK_DAY_HI_PCT, -5.0):
        assert EN.assess(change_pct=pct, **common)["reasons"] == ["weak_day"]
    for pct in (PE.WEAK_DAY_LO_PCT - 0.01, PE.WEAK_DAY_HI_PCT + 0.01, 0.0):
        assert EN.assess(change_pct=pct, **common)["reasons"] == []


def test_the_day_change_is_derived_from_prev_close_when_it_is_not_handed_over():
    r = EN.assess(px=95.0, band=demand_band(lo=93.0, hi=95.5), bands=[supply_band()],
                  prev_close=100.0, floor_state="intact", approach={"dir": "bouncing"})
    assert r["reasons"] == ["weak_day"]          # −5.0% derived
    assert "weak day" in r["reason_short"]


def test_a_failed_floor_BLOCKS_even_when_both_standing_gates_pass():
    r = EN.assess(px=100.0, band=demand_band(), bands=bands_with_room(),
                  prev_close=100.0, floor_state=AG.FLOOR_HELD_STATES[0] + "_not",
                  room_ok=True, prox_ok=True)
    assert r["verdict"] == EN.BLOCKED
    assert r["reasons"][0].startswith("floor_")


def test_an_unreadable_floor_with_no_doc_is_WATCH_not_BLOCKED():
    r = EN.assess(px=100.0, band=demand_band(), bands=bands_with_room(),
                  prev_close=100.0, approach={"dir": "bouncing"})
    assert r["verdict"] == EN.WATCH and r["reasons"] == ["floor_unknown"]
    assert r["gates"]["floor_state"] is None
    assert EN.is_shown(r) is True


def test_the_floor_is_read_through_the_one_adapter_and_an_exception_reads_unknown(monkeypatch):
    seen = {}

    def spy(doc, band, px, day_low=None, day=None):
        seen["called"] = (band["lo"], band["hi"], px, day_low)
        return {"state": AG.FLOOR_HELD_STATES[0]}

    monkeypatch.setattr(EX, "intact_read", spy)
    doc = doc_with_tail([bar("2026-09-14", 99, 101, 98, 100)])
    r = EN.assess(px=100.0, band=demand_band(), bands=bands_with_room(),
                  prev_close=100.0, day_low=98.5, doc=doc, approach={"dir": "bouncing"})
    assert seen["called"] == (98.0, 100.0, 100.0, 98.5)
    assert r["gates"]["floor_state"] == AG.FLOOR_HELD_STATES[0]
    assert r["verdict"] == EN.READY

    def boom(*a, **k):
        raise RuntimeError("no frame")

    monkeypatch.setattr(EX, "intact_read", boom)
    r2 = EN.assess(px=100.0, band=demand_band(), bands=bands_with_room(),
                   prev_close=100.0, day_low=98.5, doc=doc, approach={"dir": "bouncing"})
    assert r2["gates"]["floor_state"] is None
    assert r2["verdict"] == EN.WATCH and r2["reasons"] == ["floor_unknown"]


def test_precomputed_gates_are_honoured_and_only_a_missing_one_is_computed():
    """The push paths gated the SAME line before this runs; recomputing would
    let the recorded verdict disagree with the gate that actually fired."""
    handed = EN.assess(px=100.0, band=demand_band(lo=10.0, hi=11.0), bands=[],
                       prev_close=100.0, floor_state="intact",
                       room_ok=True, prox_ok=True)
    assert handed["verdict"] == EN.READY and handed["gates"]["prox_ok"] is True

    computed = EN.assess(px=100.0, band=demand_band(lo=10.0, hi=11.0), bands=[],
                         prev_close=100.0, floor_state="intact",
                         room_ok=None, prox_ok=None)
    assert computed["verdict"] == EN.BLOCKED and computed["reasons"] == ["proximity"]


def test_B2_CLEAR_is_a_state_and_an_unusable_print_is_no_room_block_at_all():
    clear = EN.assess(px=100.0, band=demand_band(), bands=[demand_band()],
                      prev_close=100.0, floor_state="intact")
    assert clear["gates"]["room_ok"] is True
    assert clear["room"] == {"state": "CLEAR", "room_pct": None, "target": None}
    assert clear["verdict"] == EN.READY

    dead = EN.assess(px=0.0, band=demand_band(), bands=bands_with_room(),
                     prev_close=100.0, floor_state="intact")
    assert dead["room"] is None
    assert dead["gates"]["room_ok"] is False
    assert dead["verdict"] == EN.BLOCKED and "room" in dead["reasons"]


def test_m7_the_session_DATE_reaches_the_floor_adapter_and_defaults_to_nothing(monkeypatch):
    """The floor read is dated by the caller (the boards' session day, the push
    paths' pass date). Without it `with_session_bar` falls back to the calendar
    today and appends a bar on a day that never traded (critique m7)."""
    seen = {}

    def spy(doc, band, px, day_low=None, day=None):
        seen["day"] = day
        return {"state": "intact", "pierce_pct": None, "reclaim_bars": None, "vol_x": None}

    monkeypatch.setattr(EX, "intact_read", spy)
    doc = doc_with_tail([], bands=bands_with_room(), prev_close=99.0)
    EN.read(doc=doc, px=99.0, day_low=98.5, prev_close=99.0, day="2026-09-18")
    assert seen["day"] == "2026-09-18"

    seen.clear()
    EN.read(doc=doc, px=99.0, day_low=98.5, prev_close=99.0)
    assert seen["day"] is None, "no date given, no date invented"

    # a caller that already knows the state never triggers the adapter at all
    seen.clear()
    EN.assess(px=99.0, band=demand_band(), bands=bands_with_room(), prev_close=99.0,
              doc=doc, floor_state="intact", day="2026-09-18")
    assert seen == {}


def test_the_print_source_is_served_exactly_as_the_caller_read_it():
    live = EN.assess(px=100.0, band=demand_band(), bands=bands_with_room(),
                     prev_close=100.0, floor_state="intact")
    assert live["print"] == {"px": 100.0, "source": "live"}
    scan = EN.assess(px=100.0, band=demand_band(), bands=bands_with_room(),
                     prev_close=100.0, floor_state="intact", print_source="scan")
    assert scan["print"]["source"] == "scan"


# ═══════════════════════════════════════════════════════════════════════════
# 4 — the other two kinds
# ═══════════════════════════════════════════════════════════════════════════
def test_supply_break_is_room_to_the_next_lid_and_nothing_else():
    band = supply_band(lo=100.0, hi=101.0)
    lids = [supply_band(lo=130.0, hi=132.0)]
    ok = EN.assess(kind=EN.KIND_SUPPLY_BREAK, px=101.5, band=band, bands=lids,
                   prev_close=99.0, change_pct=-5.0)
    assert ok["verdict"] == EN.READY and ok["reasons"] == []
    assert ok["gates"]["prox_ok"] is None          # proximity is a demand rule

    tight = EN.assess(kind=EN.KIND_SUPPLY_BREAK, px=101.5, band=band,
                      bands=[supply_band(lo=103.0, hi=104.0)], prev_close=99.0)
    assert tight["verdict"] == EN.BLOCKED and tight["reasons"] == ["room"]

    none = EN.assess(kind=EN.KIND_SUPPLY_BREAK, px=101.5, band=None, bands=lids)
    assert none["verdict"] == EN.BLOCKED and none["reasons"] == ["no_break"]
    assert none["reason_text"] == ["not breaking a lid at this print"]


def _break_doc(bands=None, prev_close=97.0):
    """The critique's own demo geometry (M1): a lid 98-100, the next lid
    130-132, yesterday's close under the lid."""
    return {"bands": bands or [supply_band(lo=98.0, hi=100.0),
                               supply_band(lo=130.0, hi=132.0)],
            "prev_close": prev_close, "high_252": 140.0}


def test_M1_a_print_PAST_the_break_window_says_the_break_is_extended():
    """The demo the critique ran (scratchpad/enterable/probe/breaking_probe.py):
    100.5 and 102.9 are the lane's break; 104 and 108 are past
    `zone_edge.BROKE_MAX_PCT` through the lid. They stay BLOCKED (his call
    §7.6 — the supply read is the existing gate), but the reason a blocked row
    carries must be what HAPPENED, and "no lid break" is its opposite."""
    doc = _break_doc()
    seen = {}
    for px in (100.5, 102.9, 104.0, 108.0):
        r = EN.read(doc=doc, px=px, prev_close=97.0, kind=EN.KIND_SUPPLY_BREAK, symbol="X")
        seen[px] = (r["verdict"], tuple(r["reasons"]), tuple(r["reason_short"]))
    assert seen[100.5] == (EN.READY, (), ())
    assert seen[102.9] == (EN.READY, (), ())
    for px in (104.0, 108.0):
        verdict, reasons, short = seen[px]
        assert (verdict, reasons) == (EN.BLOCKED, ("break_extended",)), px
        assert "no lid break" not in short, px

    text = EN.read(doc=doc, px=108.0, prev_close=97.0,
                   kind=EN.KIND_SUPPLY_BREAK)["reason_text"][0]
    assert ("%g%%" % ZE.BROKE_MAX_PCT) in text, text
    assert "not breaking a lid" not in text


def test_M1_the_break_window_in_the_words_and_in_the_verdict_is_the_ENFORCING_one(monkeypatch):
    """Mutation: move `zone_edge.BROKE_MAX_PCT` and BOTH the sentence and the
    line between READY and `break_extended` must move with it. Nothing about
    that number is written in this module."""
    assert "BROKE_MAX_PCT =" not in SRC, "enterable.py assigns its own break window"
    assert "ZE.BROKE_MAX_PCT" in SRC or "zone_edge.BROKE_MAX_PCT" in SRC
    assert EN.REASON_SHORT["break_extended"]({}) == "break > %g%%" % ZE.BROKE_MAX_PCT
    doc = _break_doc()
    assert EN.read(doc=doc, px=104.0, prev_close=97.0,
                   kind=EN.KIND_SUPPLY_BREAK)["reasons"] == ["break_extended"]

    # `read_breaking` binds its own default at definition, so this moves the
    # line THIS module draws: how far past a cleared lid it still stays silent.
    monkeypatch.setattr(ZE, "BROKE_MAX_PCT", 10.0)
    assert EN.REASON_SHORT["break_extended"]({}) == "break > 10%"
    near = EN.read(doc=doc, px=108.0, prev_close=97.0, kind=EN.KIND_SUPPLY_BREAK)
    assert near["reasons"] == ["no_break"], "inside a 10% window this is not extended"
    past = EN.read(doc=doc, px=112.0, prev_close=97.0, kind=EN.KIND_SUPPLY_BREAK)
    assert past["reasons"] == ["break_extended"]
    assert "10%" in past["reason_text"][0]


def test_M1_every_fixture_break_case_is_reproduced_price_for_price():
    """The fixture pins the NEGATIVES too: nothing cleared, an unknown previous
    close and a lid yesterday already closed above all keep the old
    `no_break` — the new code is served ONLY for a break that ran."""
    cases = FIX["break_cases"]
    assert len(cases) >= 8
    assert any(c["out"]["reasons"] == ["no_break"] for c in cases)
    for case in cases:
        i = case["in"]
        doc = _break_doc(bands=i.get("bands"), prev_close=i["prev_close"])
        r = EN.read(doc=doc, px=i["px"], prev_close=i["prev_close"],
                    kind=EN.KIND_SUPPLY_BREAK, symbol="X")
        assert r["verdict"] == case["out"]["verdict"], case
        assert r["reasons"] == case["out"]["reasons"], case


def test_NEGATIVE_the_extended_read_never_touches_the_demand_kind():
    """A demand row far above its band is `proximity` / `no_band` as it always
    was — the lid code exists on one kind only."""
    doc = {"bands": [demand_band(lo=98.0, hi=100.0), supply_band()], "prev_close": 97.0}
    r = EN.read(doc=doc, px=108.0, prev_close=97.0, kind=EN.KIND_DEMAND)
    assert r["reasons"] == ["proximity"] and "break_extended" not in str(r)
    assert EN._extended_break(108.0, doc["bands"], 97.0) is None, \
        "a DEMAND band is not a lid: nothing to be through"


def test_the_supply_break_read_takes_its_lids_from_the_one_next_lid_rule(monkeypatch):
    calls = []
    real = ZE.next_lids

    def spy(bands, band):
        calls.append((len(bands or []), band["hi"]))
        return real(bands, band)

    monkeypatch.setattr(ZE, "next_lids", spy)
    bands = [supply_band(lo=100.0, hi=101.0), supply_band(lo=130.0, hi=132.0)]
    doc = {"bands": bands, "prev_close": 99.0, "high_252": 200.0}
    r = EN.read(doc=doc, px=101.5, prev_close=99.0, kind=EN.KIND_SUPPLY_BREAK)
    assert calls and calls[0][1] == 101.0
    assert r["kind"] == EN.KIND_SUPPLY_BREAK


def test_a_tab_with_no_demand_read_carries_no_verdict_and_is_still_shown():
    r = EN.read(doc={"bands": []}, px=100.0, kind=EN.KIND_NA)
    assert r["kind"] == EN.KIND_NA and r["verdict"] is None
    assert r["reasons"] == ["na"] and r["reason_text"] == [EN.NA_TEXT]
    assert r["reason_short"] == ["n/a"]
    assert EN.is_shown(r) is True
    assert EN.KIND_BY_TAB["vcp"] == EN.KIND_NA


# ═══════════════════════════════════════════════════════════════════════════
# 5 — read(), is_shown(), slim()
# ═══════════════════════════════════════════════════════════════════════════
def test_read_takes_the_band_the_boards_take_and_refuses_only_a_dead_print():
    doc = {"bands": [demand_band(lo=90.0, hi=95.0), demand_band(lo=97.0, hi=100.0),
                     supply_band()],
           "prev_close": 99.0}
    r = EN.read(doc=doc, px=100.5, day_low=98.0)
    assert r["band"] == {"lo": 97.0, "hi": 100.0}      # highest hi at/below the print
    assert EN.read(doc=doc, px=0.0) is None
    assert EN.read(doc=doc, px=None) is None
    assert EN.read(doc=doc, px=float("nan")) is None


def test_is_shown_hides_BLOCKED_only_and_never_hides_what_it_cannot_read():
    blocked = {"verdict": EN.BLOCKED}
    assert EN.is_shown(blocked) is False
    assert EN.is_shown(blocked, "all") is True
    for read in ({"verdict": EN.READY}, {"verdict": EN.WATCH}, {"verdict": None},
                 None, "junk", {}):
        assert EN.is_shown(read) is True


def test_slim_is_the_verdict_and_its_words_and_nothing_stale():
    r = EN.assess(px=100.0, band=demand_band(), bands=bands_with_room(),
                  prev_close=100.0, approach={"dir": "reclaiming"}, floor_state="intact")
    s = EN.slim(r)
    assert set(s) == {"kind", "verdict", "reasons", "reason_text", "reason_short"}
    assert s["verdict"] == EN.WATCH and s["reasons"] == ["reclaim"]
    assert s["reason_short"] == ["reclaim from below"]
    assert EN.slim(None) is None and EN.slim("x") is None


# ═══════════════════════════════════════════════════════════════════════════
# 6 — the study slot
# ═══════════════════════════════════════════════════════════════════════════
def test_status_fails_closed_on_a_half_written_survivor(monkeypatch):
    # pin updated by the 2026-09-15 paste: the study ran and came back no_signal
    # with no survivor, so the shipped dict reads `no_signal`, not `pending`.
    assert EN.status() == EN.STATUS_NO_SIGNAL
    monkeypatch.setitem(EN.MEASURED, "status", EN.STATUS_PENDING)
    assert EN.status() == EN.STATUS_PENDING
    full = {"key": "C1", "definition": "first close above the touch high within 3 bars",
            "ci_cond": [1.0, 4.0], "window_bars": 3}
    monkeypatch.setitem(EN.MEASURED, "status", EN.STATUS_SEPARATES)
    monkeypatch.setattr(EN, "SURVIVOR", full)
    assert EN.status() == EN.STATUS_SEPARATES
    for missing in ("key", "definition", "ci_cond", "window_bars"):
        part = dict(full)
        part[missing] = None
        monkeypatch.setattr(EN, "SURVIVOR", part)
        assert EN.status() == EN.STATUS_NO_SIGNAL, missing
    monkeypatch.setattr(EN, "SURVIVOR", None)
    assert EN.status() == EN.STATUS_NO_SIGNAL


def test_an_unknown_survivor_key_warns_and_reads_unknown(monkeypatch, caplog):
    monkeypatch.setattr(EN, "SURVIVOR", {"key": "ZZ", "window_bars": 3})
    with caplog.at_level("WARNING"):
        assert EN.survivor_read(EN.KIND_DEMAND, doc={}, band=demand_band(), px=100.0) is None
    assert "no live reader" in caplog.text
    # and it is never read on a kind the study never measured
    monkeypatch.setattr(EN, "SURVIVOR", {"key": "C1", "window_bars": 3})
    assert EN.survivor_read(EN.KIND_SUPPLY_BREAK, doc={}, band=demand_band(), px=100.0) is None


def test_a_missing_study_module_reads_unknown_never_fired(monkeypatch, caplog):
    monkeypatch.setattr(EN, "_study", lambda: None)
    out = EN._sv_c1(doc=doc_with_tail([]), band=demand_band(), px=100.0,
                    survivor={"key": "C1", "window_bars": 3})
    assert out is None


def _mirror_tail():
    """17 closed bars: the touch is the third from last (close 100.5 sits inside
    the proximity window of the 98-100 band), the next bar closes above its
    high, and the two later bars are far above the band so only ONE bar in the
    window is an event."""
    bars = [bar("2026-08-%02d" % (d + 1), 104, 106, 103, 105) for d in range(14)]
    bars.append(bar("2026-09-10", 100.2, 101.0, 99.0, 100.5))     # the touch, j
    bars.append(bar("2026-09-11", 100.6, 102.5, 100.4, 102.0))    # closes above h[j]
    bars.append(bar("2026-09-14", 102.2, 103.5, 102.0, 103.0))
    return bars


def _ets():
    try:
        from scripts import entry_trigger_study as ETS
    except Exception as exc:                                   # noqa: BLE001
        pytest.skip("scripts/entry_trigger_study.py is not importable yet (%s) — "
                    "WP0 writes it; this mirror arms itself the moment it lands" % exc)
    for attr in ("event_at", "trigger_c1"):
        if not hasattr(ETS, attr):
            pytest.skip("scripts/entry_trigger_study.py has no %s yet — the mirror "
                        "arms itself when the study exposes it" % attr)
    return ETS


def test_MIRROR_the_survivor_reader_runs_the_STUDYS_OWN_event_and_trigger():
    """M2: no third definition of the touch. The live reader must agree with the
    study function for function on the same closed bars."""
    ETS = _ets()
    bars = _mirror_tail()
    bands = bands_with_room()
    doc = doc_with_tail(bars, bands=bands)
    survivor = {"key": "C1", "window_bars": 3,
                "definition": "first close above the touch high within 3 bars",
                "ci_cond": [1.0, 4.0]}

    o = [b["open"] for b in bars]
    h = [b["high"] for b in bars]
    lo_ = [b["low"] for b in bars]
    c = [b["close"] for b in bars]
    j = len(bars) - 3
    ev = ETS.event_at(o, h, lo_, c, j, bands)
    assert isinstance(ev, dict), "the study does not see a touch on the mirror tail"
    k, _why = ETS.trigger_c1(o, h, lo_, c, j, ev["stop"], ev["band"]["hi"], 3)

    out = EN._sv_c1(doc=doc, band=demand_band(), px=102.5, survivor=survivor)
    assert out is not None
    assert out["ok"] == (k is not None)
    assert out["key"] == "C1"
    assert "bounc" not in out["text"].lower()


def test_MIRROR_a_live_print_above_the_touch_high_is_NEVER_the_trigger():
    """The trigger is a CLOSE. A print that is above the bar's high right now,
    with no closed bar above it, has not confirmed anything."""
    _ets()
    bars = [bar("2026-08-%02d" % (d + 1), 104, 106, 103, 105) for d in range(14)]
    bars.append(bar("2026-09-10", 100.2, 101.0, 99.0, 100.5))     # the touch
    bars.append(bar("2026-09-11", 97.5, 98.0, 96.0, 97.0))        # floor gone, no confirm
    doc = doc_with_tail(bars, bands=bands_with_room())
    out = EN._sv_c1(doc=doc, band=demand_band(), px=150.0,
                    survivor={"key": "C1", "window_bars": 3})
    assert out is not None and out["ok"] is False
    assert "not confirmed" in out["text"]


def test_MIRROR_a_trigger_measured_on_a_different_band_is_refused():
    _ets()
    doc = doc_with_tail(_mirror_tail(), bands=bands_with_room())
    out = EN._sv_c1(doc=doc, band=demand_band(lo=50.0, hi=52.0), px=102.5,
                    survivor={"key": "C1", "window_bars": 3})
    assert out is not None and out["ok"] is None
    assert "different band" in out["text"]


def test_the_survivor_readers_cover_every_convention_the_study_can_ship():
    assert set(EN._SURVIVOR_READERS) == {"C1", "C2", "L1", "HL"}
    for key, fn in EN._SURVIVOR_READERS.items():
        assert list(inspect.signature(fn).parameters) == ["doc", "band", "px", "survivor"]


# ═══════════════════════════════════════════════════════════════════════════
# 7 — the prose and the pinned measurement
# ═══════════════════════════════════════════════════════════════════════════
def test_the_measured_verdict_names_the_run_and_says_the_read_is_unchanged(monkeypatch):
    # pin updated by the 2026-09-15 paste: status flipped pending -> no_signal.
    v = EN.measured_verdict()
    assert set(v) == {"headline", "body", "fallback_note", "limits"}
    assert "NO ENTRY TRIGGER SEPARATES" in v["headline"]
    assert str(EN.MEASURED["run_date"]) in v["headline"]
    assert "unchanged" in v["fallback_note"]          # the READY read does not move
    assert "buys nothing" in v["limits"]
    blk = EN.measured_block()
    assert set(blk) == {"status", "run_date", "n_episodes", "survivor_key", "mdl", "script"}
    assert blk["status"] == EN.STATUS_NO_SIGNAL and blk["survivor_key"] is None
    # the pending branch is still reachable and still names the script
    monkeypatch.setitem(EN.MEASURED, "status", EN.STATUS_PENDING)
    pv = EN.measured_verdict()
    assert "pending" in pv["headline"]
    assert EN.MEASURED["script"] in pv["body"]
    assert "unchanged" in pv["fallback_note"]


def test_not_one_served_string_says_bounce():
    strings = list(EN.measured_verdict().values()) + [EN.NA_TEXT]
    for fn in list(EN.REASON_TEXT.values()) + list(EN.REASON_SHORT.values()):
        strings.append(fn({"floor_state": "x", "sweep": None, "room": None,
                           "drags": [], "survivor": {"key": "C1"}}))
    reads = [r["read"] for r in FIX["rows"] if isinstance(r["read"], dict)]
    for r in reads:
        strings += list(r.get("reason_text") or []) + list(r.get("reason_short") or [])
    for s in strings:
        assert "bounc" not in str(s).lower(), s
    assert EN._prose("bouncing off the band") == "reversal off the band"


def test_measured_dict_equals_the_shipped_json():
    with open(MEASURED_JSON) as fh:
        js = json.load(fh)
    assert EN.MEASURED == js
    assert EN.MEASURED["status"] in (EN.STATUS_PENDING, EN.STATUS_NO_SIGNAL,
                                     EN.STATUS_SEPARATES)
    assert str(EN.MEASURED["script"]).startswith("backend/scripts/")


def test_SOURCE_GUARD_the_read_borrows_exactly_one_thing_from_explosive():
    """One floor adapter, nothing else: the ENTERABLE read must never inherit
    the explosive score, its MEASURED dict or its ordering key."""
    from_explosive = {n.split(".")[-1] for n in _imports(False)
                      if n.startswith("supply_demand.explosive.")}
    assert from_explosive == {"intact_read"}, from_explosive
    attrs = {n.attr for n in ast.walk(TREE)
             if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
             and n.value.id == "explosive"}
    assert attrs == set(), attrs
    for banned in ("explosive_key", "_score", "SELECTED"):
        assert banned not in _code_of("assess") + _code_of("read")

    # every heavy neighbour is imported INSIDE a function (circularity)
    top = _imports(True)
    for banned in ("trading", "supply_demand.zone_edge", "supply_demand.bounce_room",
                   "supply_demand.explosive", "supply_demand.demand_alerts",
                   "supply_demand.zone_bounce_alerts", "scripts.entry_trigger_study"):
        assert not any(t == banned or t.startswith(banned + ".") for t in top), \
            "enterable imports %s at module level" % banned
    assert top == {"__future__.annotations", "logging", "math", "typing.Optional",
                   "supply_demand.alert_gates", "supply_demand.premarket_entry"}
    assert "from supply_demand import bounce_room" in inspect.getsource(EN.read)


# ═══════════════════════════════════════════════════════════════════════════
# 8 — zone_edge.next_lids: the ONE overhead list (WP2 step 0)
# ═══════════════════════════════════════════════════════════════════════════
def test_next_lids_is_the_supply_lane_room_list():
    """The extracted function must return exactly what the lane built inline:
    every band whose top clears the one being broken, an overlapping lid
    included (review 2026-09-05)."""
    band = supply_band(lo=100.0, hi=101.0)
    bands = [demand_band(lo=90.0, hi=95.0),
             supply_band(lo=100.0, hi=101.0),          # the band itself: not overhead
             supply_band(lo=100.5, hi=101.5),          # overlapping lid: IS overhead
             supply_band(lo=130.0, hi=132.0),
             {"kind": "supply", "lo": None, "hi": 200.0}]   # unusable: dropped
    inline = [b for b in bands if ZE._valid_band(b) and float(b["hi"]) > band["hi"]]
    out = ZE.next_lids(bands, band)
    assert out == inline
    assert [b["hi"] for b in out] == [101.5, 132.0]


def test_next_lids_has_nothing_overhead_of_a_band_it_cannot_read():
    bands = [supply_band(lo=130.0, hi=132.0)]
    assert ZE.next_lids(bands, None) == []
    assert ZE.next_lids(bands, {"lo": None, "hi": None}) == []
    assert ZE.next_lids(bands, {"lo": 10.0, "hi": 5.0}) == []      # lo > hi
    assert ZE.next_lids(None, supply_band(lo=100.0, hi=101.0)) == []
    assert ZE.next_lids([], supply_band(lo=100.0, hi=101.0)) == []
