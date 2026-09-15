"""ℹ️ Rules panel — the 🧨 Explosive read section (2026-09-15).

The panel exists so the served rules can not drift from the code. This file
pins that for the new section three ways:

* it is BUILT from `explosive.MEASURED` (through `explosive.measured_verdict()`)
  and from the constants that enforce each gate — change either and the text
  changes;
* NEGATIVE: not one digit in the rendered section is a literal that is absent
  from those constants and from MEASURED, so nobody can paste a study number
  into the prose;
* NEGATIVE: the section never says "bounc…" on a surface Ajay reads.

The `"bounc"` scrub in `test_supply_demand_contracts.py` covers the whole
payload already; the local one here fails closer to the change.
"""
from __future__ import annotations

import json
import re

from supply_demand import alert_gates as AG
from supply_demand import amd as AMD
from supply_demand import mood as MD
from supply_demand import rules_info as RI
from supply_demand import explosive as EX
from sepa.breakout_audit import VOL_AVG_BARS

NUM = re.compile(r"\d+(?:\.\d+)?")

CONSTS = (
    AG.ALERT_MIN_ROOM_PCT,
    AG.STOP_BUFFER_PCT,
    AG.SWEEP_WINDOW_BARS,
    MD.RSI_PERIOD,
    AMD.VOL_REF_BARS,
    VOL_AVG_BARS,
)


def _section() -> dict:
    secs = RI.payload()["sections"]
    assert "explosive" in secs, (
        "the 🧨 section fell out of the payload — sections() swallowed an "
        "exception from _explosive_section(); keys: %s" % sorted(secs)
    )
    return secs["explosive"]


def _blob(sec: dict) -> str:
    return " ".join([sec["title"]] + list(sec["picks"]) + list(sec["stops"])
                    + list(sec["alerts"]) + [sec["note"]])


def _allowed_numbers() -> set:
    """Every numeric token a reader could legitimately meet in the section:
    the enforcing constants (raw and as the panel formats them) and anything
    the measurement itself carries."""
    parts = []
    for c in CONSTS:
        parts.append(str(c))
        parts.append(RI._pct(c))
        if float(c) == int(c):
            parts.append(str(int(c)))
    # ensure_ascii=False: a JSON-escaped unicode minus ("\\u2212") glued to the
    # digits that follow it would turn "−1.47pp" into the token "22121.47" and
    # hide the very number the prose prints (found 2026-09-15).
    parts.append(json.dumps(EX.MEASURED, default=str, ensure_ascii=False))
    try:
        parts.append(json.dumps(EX.measured_verdict(), default=str, ensure_ascii=False))
    except Exception:                                          # noqa: BLE001
        pass
    return set(NUM.findall(" ".join(parts)))


# ── built from MEASURED + the constants ────────────────────────────────────

def test_explosive_section_is_built_from_MEASURED_and_constants(monkeypatch):
    assert "explosive" in RI.SECTION_KEYS
    sec = _section()
    blob = _blob(sec)

    # every imported constant reaches the prose in the panel's own format
    assert RI._pct(AG.ALERT_MIN_ROOM_PCT) in blob
    assert RI._pct(AG.STOP_BUFFER_PCT) in blob
    for c in (AG.SWEEP_WINDOW_BARS, MD.RSI_PERIOD, AMD.VOL_REF_BARS,
              VOL_AVG_BARS):
        assert str(int(c)) in blob, c

    # pending / no_signal → the order line says what it really is
    if EX.MEASURED.get("status") != EX.STATUS_SEPARATES:
        assert "floor-held + room" in blob
        assert "NOT an explosiveness ranking" in blob

    # MEASURED drives the branch: flip the status and the order line changes
    patched = dict(EX.MEASURED)
    patched["status"] = EX.STATUS_SEPARATES
    monkeypatch.setattr(EX, "MEASURED", patched, raising=False)
    monkeypatch.setattr(EX, "measured_verdict",
                        lambda: {"headline": "MEASURED 2099-01-02: stub",
                                 "body": "", "fallback_note": "",
                                 "limits": ""})
    flipped = _blob(_section())
    assert flipped != blob
    assert "floor-held + room" not in flipped
    assert "measured score" in flipped

    # and the verdict is RENDERED, never retyped: its run date reaches the page
    assert "2099-01-02" in flipped

    # the constants survive the flip — they are not part of the branch
    assert RI._pct(AG.ALERT_MIN_ROOM_PCT) in flipped
    assert str(int(AG.SWEEP_WINDOW_BARS)) in flipped


def test_the_section_is_regenerated_on_every_call_not_cached(monkeypatch):
    """A cached section would show yesterday's verdict after a re-run."""
    before = _blob(_section())
    monkeypatch.setattr(EX, "measured_verdict",
                        lambda: {"headline": "MEASURED 2098-12-31: other stub"})
    after = _blob(_section())
    assert "2098-12-31" in after
    assert after != before


# ── NEGATIVE cases ─────────────────────────────────────────────────────────

def test_NEGATIVE_no_digit_in_the_section_is_a_typed_literal():
    """Not one number in the prose may be a literal that is absent from the
    enforcing constants and from MEASURED — the whole point of the panel."""
    sec = _section()
    allowed = _allowed_numbers()
    found = set(NUM.findall(_blob(sec)))
    stray = sorted(found - allowed)
    assert not stray, (
        "typed numbers in the 🧨 section: %s — every number must come from a "
        "constant or from explosive.MEASURED" % stray
    )


def test_NEGATIVE_the_section_never_says_bounce():
    sec = _section()
    prose = re.sub(r'"[^"]*"', "", _blob(sec))
    assert "bounc" not in prose.lower(), prose


def test_NEGATIVE_a_broken_verdict_never_takes_the_section_off_the_page(monkeypatch):
    """A half-written MEASURED must not cost the reader the rules that are
    built from constants and have nothing to do with the study."""
    def _boom():
        raise KeyError("d_hit5")

    monkeypatch.setattr(EX, "measured_verdict", _boom)
    sec = _section()
    blob = _blob(sec)
    assert RI._pct(AG.ALERT_MIN_ROOM_PCT) in blob
    assert str(int(AG.SWEEP_WINDOW_BARS)) in blob
    assert sec["alerts"], "the section must still say the study has not reported"
    assert "NOTHING HERE PUSHES, GATES OR BUYS." in blob


def test_NEGATIVE_the_section_promises_no_alert_no_lane_and_no_trade():
    sec = _section()
    blob = _blob(sec)
    assert "NOTHING HERE PUSHES, GATES OR BUYS." in blob
    assert "No stop, no target and no size" in blob


def test_NEGATIVE_the_section_has_the_shape_the_panel_scrubs():
    """The contracts scrub indexes these five keys; a section missing one
    would slip past every "bounc"/number check in the suite."""
    sec = _section()
    for key in ("title", "emoji", "picks", "stops", "alerts", "note"):
        assert key in sec, key
    assert isinstance(sec["picks"], list) and sec["picks"]
    assert isinstance(sec["stops"], list) and sec["stops"]
    assert isinstance(sec["alerts"], list) and sec["alerts"]
    assert sec["note"] == RI._DISCLAIMER


# ── the panel's "who gets a read" line vs what `explosive.read` actually does ──

def _flat_doc() -> dict:
    """A doc shaped like `zone_store.build_doc`'s, whose 99–101 demand band is
    at/below the print (`bounce_room.demand_read` agrees) and whose floor has
    BROKEN on the closed tail — the row the phone would never be shown."""
    import numpy as np                                         # noqa: F401
    import pandas as pd

    n = 400
    f = pd.DataFrame({"open": 100.0, "high": 100.5, "low": 99.5,
                      "close": 100.0, "volume": 1_000_000.0},
                     index=pd.bdate_range("2024-01-02", periods=n))
    cols = [f.columns.get_loc(c) for c in ("open", "high", "low", "close")]
    f.iloc[-3:, cols] = [[97.0, 97.5, 96.5, 97.0]] * 3
    return {"symbol": "TEST", "date": "2026-09-15",
            "bands": [{"kind": "demand", "lo": 99.0, "hi": 101.0,
                       "touches": 3}],
            "atr14": 2.0, "prev_close": 100.0, "high_252": 140.0,
            "feat": EX.feat_block(f)}


def test_the_who_gets_a_read_line_is_what_explosive_read_really_does():
    """MEDIUM refix 2026-09-15: the panel claimed the read carried the phone's
    room and stop gates. It does not — `explosive.read` reads any row with a
    demand band at/below the print. The prose now says that, and this pins the
    prose to the behaviour rather than to itself."""
    from supply_demand import bounce_room as BR

    doc = _flat_doc()
    px = 99.5
    band = {"lo": 99.0, "hi": 101.0}
    assert BR.demand_read(px, doc) is not None, "the band must be a real pick"

    # zero headroom (IN_BAND — the room gate's own failure case) AND a floor
    # that has already broken (the stop gate's) → the chip is drawn anyway
    got = EX.read({"symbol": "TEST", "print": px, "demand": band,
                   "room": {"state": "IN_BAND", "room_pct": 0.0}}, doc=doc)
    assert got is not None, (
        "read() dropped a row both phone gates reject — if that ever becomes "
        "true, the panel line has to go back to claiming the two gates")
    assert got["floor_state"] == "broken"
    assert got["intact"] is False

    who = _section()["picks"][0]
    assert "at or below the print" in who
    assert "not gated on headroom" in who and "not gated on the stop" in who


def test_NEGATIVE_the_two_gate_constants_are_not_claimed_on_the_who_line():
    """The room and stop numbers belong to the STUDY's cohort, not to who gets
    a chip; a paste back into picks[0] re-opens the contradiction."""
    picks = _section()["picks"]
    who = picks[0]
    for token in (RI._pct(AG.ALERT_MIN_ROOM_PCT), RI._pct(AG.STOP_BUFFER_PCT)):
        assert token not in who, who

    study_line = [p for p in picks if "STUDY measured" in p]
    assert len(study_line) == 1, picks
    assert RI._pct(AG.ALERT_MIN_ROOM_PCT) in study_line[0]
    assert RI._pct(AG.STOP_BUFFER_PCT) in study_line[0]
    assert "cohort" in study_line[0]
