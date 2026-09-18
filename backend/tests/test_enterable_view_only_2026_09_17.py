"""🎯 UN-HIDE BY REASON — the BACKEND did not move (2026-09-17).

Ajay: "Can you give me a toggle for the room too? I am not seeing all stocks on
the selected filter due to this now."

Every reason the hidden-count line prints is now a button on the frontend. The
feature is a VIEW filter over a verdict the backend already serves on every row:
no gate, no threshold, no constant and no default changed, and the only backend
work this spec carries is the proof of that.

Three of these tests carry the weight — they pin the SERVED contract the
frontend's un-hide rule rests on:

  * a BLOCKED read carries ONLY block codes, so "every code on a BLOCKED row is
    a blocking code" is true and the FE needs no block/advisory split;
  * `reasons` / `reason_text` / `reason_short` stay index-parallel, so the chip's
    label really is the label of the code it toggles;
  * no module under `supply_demand/` has ever heard of an un-hide, so a view
    preference cannot reach a gate.

The last three are REGRESSION PINS, not new coverage: they restate what
`test_enterable_wiring.py` already proves, in the words of this change, so that
"he un-hid room on a board" can never be read as "room stopped blocking". A
reason un-hidden on a board is still blocked on the phone and still refused by
every lane.

Nothing here loosens a gate. Nothing here is a measurement.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import alert_gates as AG          # noqa: E402
from supply_demand import enterable as EN            # noqa: E402

# The shipped wiring harness, reused rather than re-declared: a second copy of
# `_da` / `_ze` / `_zb` would be a second definition of what "pushed" means.
from tests.test_enterable_wiring import (            # noqa: E402
    DEM, RES, Coll, _capture, _clean_structure, _da, _doc, _snap, _zb, _zb_case, _ze,
)

# `_clean_structure` is an AUTOUSE fixture in its own module; importing the name
# is what re-arms it here (the daily-bar reads the push paths make are stubbed
# exactly as the sibling suite stubs them).
__all__ = ["_clean_structure"]

BACKEND = Path(__file__).resolve().parents[1]


# ═════════════════════════════════════════ 1. the SERVED contract the FE rests on
def _grade_matrix():
    """Every (kind, gates, floor, drags, survivor) combination `grade()` can be
    handed — the same shape the shipped grader is exercised with."""
    drag_sets = ([], [{"key": "reclaim"}], [{"key": "weak_day"}],
                 [{"key": "reclaim"}, {"key": "weak_day"}])
    survivors = (None, {"key": "t1", "ok": True}, {"key": "t1", "ok": False},
                 {"key": "t1", "ok": None})
    floors = (None, "intact", "swept", "broken", "GREMLIN") + tuple(AG.FLOOR_HELD_STATES)
    for kind in (EN.KIND_DEMAND, EN.KIND_SUPPLY_BREAK, EN.KIND_NA):
        for room_ok in (True, False, None):
            for prox_ok in (True, False, None):
                for floor in floors:
                    for drags in drag_sets:
                        for surv in survivors:
                            yield kind, room_ok, prox_ok, floor, drags, surv


def test_a_BLOCKED_read_carries_only_BLOCK_CODES():
    """THE contract the frontend's un-hide rule rests on.

    Every code on a BLOCKED row is a BLOCKING code, so "show this row once every
    one of its reasons is un-hidden" needs no block/advisory split on the FE. If
    an advisory code (a drag, `floor_unknown`, a survivor) could ride on a
    BLOCKED read, un-hiding it would show a row that is still blocked for
    something the line never named.
    """
    seen = set()
    for kind, room_ok, prox_ok, floor, drags, surv in _grade_matrix():
        verdict, reasons = EN.grade(kind, room_ok, prox_ok, floor, drags, surv)
        if verdict != EN.BLOCKED:
            continue
        assert reasons, "a BLOCKED read always names at least one reason"
        for code in reasons:
            base = EN._base_code(code)
            seen.add(base)
            assert base in EN.BLOCK_CODES, f"{code!r} is not a block code"
            # NEGATIVE: not one WATCH code, and no survivor, ever appears.
            assert base not in EN.WATCH_CODES
            assert not str(code).startswith("survivor_")
    assert {"room", "proximity", "floor"} <= seen, "the matrix reached the real blockers"


def test_reasons_reason_text_reason_short_are_index_parallel():
    """`reasons[i]` ↔ `reason_short[i]`, on every `assess()` path.

    The frontend zips the two by index to build one chip per reason. The FE also
    fails CLOSED on a short array (a row with an unlabelled block reason is
    never un-hideable), but a truncation would be caught HERE first.
    """
    bands = [DEM, RES]
    cases = [
        dict(kind=EN.KIND_NA, px=91.0, band=None, bands=[]),                     # n/a
        dict(kind=EN.KIND_DEMAND, px=91.0, band=None, bands=[]),                 # no band
        dict(kind=EN.KIND_SUPPLY_BREAK, px=99.0, band=None, bands=bands),        # no lid break
        dict(kind=EN.KIND_DEMAND, px=91.0, band=DEM, bands=bands, prev_close=95.0),
        dict(kind=EN.KIND_DEMAND, px=91.0, band=DEM, bands=bands, prev_close=95.0,
             room_ok=False, prox_ok=False),                                      # room + proximity
        dict(kind=EN.KIND_DEMAND, px=91.0, band=DEM, bands=bands, prev_close=95.0,
             room_ok=True, prox_ok=True, floor_state="swept"),                   # floor_<state>
        dict(kind=EN.KIND_DEMAND, px=91.0, band=DEM, bands=bands, prev_close=95.0,
             room_ok=True, prox_ok=True, floor_state=None),                      # floor_unknown
        dict(kind=EN.KIND_SUPPLY_BREAK, px=103.0, band=RES, bands=bands, prev_close=95.0),
    ]
    for kw in cases:
        read = EN.assess(**kw)
        n = len(read["reasons"])
        assert len(read["reason_text"]) == n, kw
        assert len(read["reason_short"]) == n, kw
        for short in read["reason_short"]:
            assert isinstance(short, str) and short, (kw, read["reasons"])


def test_SOURCE_GUARD_the_backend_has_no_un_hide_concept():
    """A view preference must be UNABLE to reach a gate.

    The ignore set lives in the browser's URL and nowhere else. If any of these
    tokens ever appears under `backend/supply_demand/`, somebody has taught a
    module the push path calls what a board is currently drawing.
    """
    tokens = ("unhide", "un_hide", "ignore_reasons", "ignoreReasons", "ignore_set")
    offenders = []
    for path in sorted((BACKEND / "supply_demand").rglob("*.py")):
        src = path.read_text(encoding="utf-8", errors="replace").lower()
        for token in tokens:
            if token.lower() in src:
                offenders.append(f"{path.name}: {token}")
    assert offenders == [], offenders


def test_is_shown_still_hides_BLOCKED_and_nothing_else():
    """The backend's own copy of the filter rule is untouched: it takes a read
    and a mode, and it has no third argument. The ignore set is the FRONTEND's.
    """
    import inspect
    assert list(inspect.signature(EN.is_shown).parameters) == ["read", "mode"]
    assert EN.is_shown({"verdict": EN.BLOCKED}) is False
    assert EN.is_shown({"verdict": EN.BLOCKED}, "all") is True
    for read in ({"verdict": EN.READY}, {"verdict": EN.WATCH}, {"verdict": None}, None, {}):
        assert EN.is_shown(read) is True


# ═════════════════════════════════════════ 2. regression pins — the phone and the lanes
def test_PIN_a_room_blocked_row_is_still_not_pushed(monkeypatch):
    """REGRESSION PIN — a reason un-hidden on a board is still blocked on the
    phone. Restates `test_enterable_wiring.py`'s counter test in this change's
    words; nothing in this diff may move it.
    """
    sent = _capture(monkeypatch)
    from supply_demand import demand_alerts as DA
    blocked = dict(EN.assess(kind=EN.KIND_DEMAND, px=91.0, band=DEM, bands=[DEM, RES],
                             prev_close=95.0, room_ok=True, prox_ok=True),
                   verdict=EN.BLOCKED, reasons=["room"], reason_short=["room < 5%"])
    monkeypatch.setattr(DA.EN, "assess", lambda **kw: blocked)
    out = _da({"AAA": _doc("AAA", [DEM, RES], 95.0)}, {"AAA": _snap(91.0, 95.0, low=90.5)},
              {"AAA": 5e9}, coll=Coll())
    assert sent == [] and out["pushed"] == 0
    assert out["skipped_not_enterable"] == 1


def test_PIN_the_entry_lane_still_refuses_it(monkeypatch):
    """REGRESSION PIN — the zone-edge lane refuses the same forced BLOCKED read.
    A row he brought back onto a board is never entered."""
    from supply_demand import zone_edge as ZE
    sent = _capture(monkeypatch)
    out, _ = _ze({"AAA": _doc("AAA", [DEM, RES], 95.0)},
                 {"AAA": _snap(91.0, 95.0, low=90.5)}, {"AAA": 5e9})
    assert out["pushed"] == 1 and out["skipped_not_enterable"] == 0
    blocked = dict(sent[0]["enterable"], verdict=EN.BLOCKED,
                   reasons=["room"], reason_short=["room < 5%"])
    monkeypatch.setattr(ZE.EN, "assess", lambda **kw: blocked)
    sent2 = _capture(monkeypatch)
    out2, _ = _ze({"AAA": _doc("AAA", [DEM, RES], 95.0)},
                  {"AAA": _snap(91.0, 95.0, low=90.5)}, {"AAA": 5e9})
    assert sent2 == [] and out2["pushed"] == 0
    assert out2["skipped_not_enterable"] == 1


def test_PIN_zone_bounce_alerts_unchanged(monkeypatch):
    """REGRESSION PIN — the 🪃 reversal kind, same forced BLOCKED read, same
    silence."""
    from supply_demand import zone_bounce_alerts as ZB
    doc, snapshot = _zb_case()
    sent = _capture(monkeypatch)
    out = _zb({"AAA": doc}, snapshot, {"AAA": 5e9})
    assert out["pushed"] == 1 and out["skipped_not_enterable"] == 0
    blocked = dict(sent[0]["enterable"], verdict=EN.BLOCKED,
                   reasons=["room"], reason_short=["room < 5%"])
    monkeypatch.setattr(ZB.EN, "assess", lambda **kw: blocked)
    sent2 = _capture(monkeypatch)
    out2 = _zb({"AAA": doc}, snapshot, {"AAA": 5e9})
    assert sent2 == [] and out2["pushed"] == 0
    assert out2["skipped_not_enterable"] == 1


# ═════════════════════════════════════════ 3. no constant moved
@pytest.mark.parametrize("name,value", [
    ("BLOCK_CODES", ("no_band", "no_break", "break_extended", "proximity", "room", "floor")),
    ("WATCH_CODES", ("reclaim", "weak_day", "floor_unknown")),
    ("FLOOR_CODE", "floor_{state}"),
])
def test_PIN_the_reason_vocabulary_did_not_move(name, value):
    """REGRESSION PIN — the chip KEYS are these codes. A silent rename here
    would turn every bookmarked `?unhide=` into an inert token."""
    assert getattr(EN, name) == value


def test_PIN_the_room_label_is_still_built_from_the_enforcing_constant():
    """The chip prints this string verbatim. It is built from
    `alert_gates.ALERT_MIN_ROOM_PCT` — never typed, here or on the frontend."""
    assert EN.REASON_SHORT["room"]({}) == "room < %g%%" % AG.ALERT_MIN_ROOM_PCT
    assert EN.REASON_SHORT["proximity"]({}) == "not at band"
    assert EN.REASON_SHORT["no_band"]({}) == "no band"
