"""🧱 Zone-pad study PIN (2026-09-30): the study's arm-B emulation == the branch engine.

The study runs on origin/main inside the container, where `level_pad` does not exist, so
arm B (the pad) is EMULATED there from `sd_liquidity.STOP_SHELF_PCT`. This file runs on the
branch, with the real `level_pad` at its default, and pins every emulated piece to the engine
the phone will run: the floor, proximity, the approach read, room with the entry band removed,
the stop, and the A_held floor-held gate (on the DRAWN floor, HIS CALL #1 = off). If any
engine changes, this fails and the study must be re-pinned before its number is quoted.
Hermetic: no network, no Mongo, no price cache.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from scripts import zone_pad_study_2026_09_30 as ZP     # noqa: E402
from supply_demand import alert_gates as AG             # noqa: E402
from supply_demand import level_pad as LP               # noqa: E402


@pytest.fixture(autouse=True)
def _branch_defaults(monkeypatch):
    """The pad ON at the one number, the floor-held gate on the drawn floor."""
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", ZP.PAD_PCT)
    monkeypatch.setattr(LP, "PAD_FLOOR_HELD", False)


def _band(lo, width=0.015, kind="demand"):
    return {"kind": kind, "lo": lo, "hi": round(lo * (1 + width), 2), "touches": 3, "strength": 60.0}


BANDS = [_band(133.0), _band(95.04), _band(12.37), _band(1.99), _band(250.0, 0.04)]


def _grid(band, k=41):
    return np.round(np.linspace(band["lo"] * 0.975, band["hi"] * 1.02, k), 2).tolist()


def test_the_emulated_pad_is_the_engine_pad():
    assert ZP.PAD_PCT == LP.DEMAND_PAD_PCT == LP.pad_pct()


@pytest.mark.parametrize("band", BANDS, ids=lambda b: str(b["lo"]))
def test_floor_b_is_the_engine_support_floor(band):
    assert ZP._floor_b(band) == LP.support_floor(band)
    assert ZP._floor_b(band) < band["lo"]


@pytest.mark.parametrize("band", BANDS, ids=lambda b: str(b["lo"]))
def test_prox_b_is_the_engine_proximity_gate(band):
    for px in _grid(band):
        assert ZP.prox_b(px, band) == AG.demand_proximity_gate(px, band), px


def _approach_cases(band):
    lo, hi = band["lo"], band["hi"]
    prevs = [None, hi * 1.03, hi * 1.001, lo * 0.995, lo * 0.97]
    lows = [None, lo * 0.992, lo * 0.98, hi * 1.005]
    return [(px, prev, dl) for px in _grid(band, 17) for prev in prevs for dl in lows]


@pytest.mark.parametrize("band", BANDS, ids=lambda b: str(b["lo"]))
def test_approach_b_is_the_engine_approach_read(band, monkeypatch):
    """approach_b feeds a floor-moved band to MAIN's approach_read (drawn floor). On the
    branch that is AG.approach_read with the pad OFF; the engine it must equal is the
    branch's approach_read with the pad ON."""
    cases = _approach_cases(band)
    engine = [AG.approach_read(px, band, prev, dl) for px, prev, dl in cases]
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)                 # AG.* == main's gates
    emulated = [ZP.approach_b(px, band, prev, dl, pad=ZP.PAD_PCT) for px, prev, dl in cases]
    for c, e, m in zip(cases, engine, emulated):
        assert m == e, c


def test_NEGATIVE_approach_b_on_the_branch_engine_would_pad_twice(monkeypatch):
    """Why the pin turns the branch pad off for the emulation: fed to the PADDED engine the
    emulation pads twice and admits a print under the one-pad floor. The study never runs
    on the branch engine with arm B (arm_a_pad_off)."""
    band = BANDS[-1]
    px = round(LP.support_floor(band) * 0.999, 2)          # under the one-pad floor
    assert AG.approach_read(px, band, None, None) is None
    assert ZP.approach_b(px, band, None, None) is not None


def test_room_b_is_the_engine_room_gate_with_the_entry_band():
    entry = _band(133.0)
    lid = {"kind": "supply", "lo": 136.0, "hi": 137.0, "touches": 3, "strength": 50.0}
    far = {"kind": "supply", "lo": 150.0, "hi": 152.0, "touches": 3, "strength": 50.0}
    under = _band(120.0)
    for bands in ([entry, far], [entry, lid, far], [under, entry], [entry]):
        for px in (132.2, 133.0, 134.0, 135.5, 139.0):
            for prev in (None, 131.0, 136.5):
                assert ZP.room_b(px, bands, prev, entry) == \
                    AG.room_gate(px, bands, prev, entry_band=entry), (px, prev, len(bands))


def test_NEGATIVE_room_b_and_the_engine_both_keep_every_other_band():
    """The entry band is the only one removed: a real ceiling above still fails both."""
    entry = _band(133.0)
    lid = {"kind": "supply", "lo": 134.5, "hi": 135.5, "touches": 3, "strength": 50.0}
    ok_b, room_b = ZP.room_b(134.0, [entry, lid], None, entry)
    assert (ok_b, room_b) == AG.room_gate(134.0, [entry, lid], None, entry_band=entry)
    assert ok_b is False and room_b["target"] == 134.5


_STOP = re.compile(r"stop \$([0-9.]+)")


@pytest.mark.parametrize("band", BANDS, ids=lambda b: str(b["lo"]))
def test_stop_b_is_the_phone_plan_stop(band):
    txt = AG.plan_txt(band["hi"], band, None)
    m = _STOP.search(txt)
    assert m, txt
    assert "%.2f" % ZP.stops(band)[1] == m.group(1)
    assert "%.2f" % ZP.stops(band)[0] != m.group(1)          # arm A is NOT the padded stop


def test_NEGATIVE_pad_off_the_plan_stop_is_arm_a(monkeypatch):
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)
    band = BANDS[0]
    m = _STOP.search(AG.plan_txt(band["hi"], band, None))
    assert "%.2f" % ZP.stops(band)[0] == m.group(1)


# ── A_held: the phone's floor-held gate on the DRAWN floor ───────────────────
def _fh_frame(low_hit=None, close_hit=None, n=40):
    c = np.full(n, 136.0)
    lo_ = c - 0.5
    if low_hit is not None:
        lo_[-5] = low_hit
    if close_hit is not None:
        c[-5] = close_hit
    d = pd.bdate_range("2026-08-03", periods=n)
    return pd.DataFrame({"date": d, "open": c, "high": c + 0.5, "low": lo_, "close": c,
                         "volume": np.full(n, 1e6), "d": d.strftime("%Y-%m-%d")})


FH_CASES = [(None, None), (132.5, None), (132.5, 132.8), (131.0, None), (131.0, 131.2)]


@pytest.mark.parametrize("low_hit,close_hit", FH_CASES)
def test_floor_held_a_is_the_engine_gate_on_the_drawn_floor(low_hit, close_hit, monkeypatch):
    band = BANDS[0]
    f = _fh_frame(low_hit, close_hit)
    j = len(f) - 1
    win = f.iloc[max(0, j - ZP.SWEEP_WINDOW - 2):j + 1]
    got = ZP.floor_held_a(band, f, j)
    assert got == AG.floor_held_gate(band, frame=win)
    monkeypatch.setattr(LP, "DEMAND_PAD_PCT", 0.0)            # the drawn floor, pad off
    assert got == AG.floor_held_gate(band, frame=win)


def test_floor_held_a_intact_passes_and_a_pierce_inside_the_pad_fails():
    band = BANDS[0]
    f = _fh_frame()
    assert ZP.floor_held_a(band, f, len(f) - 1) is True
    f = _fh_frame(132.5)                                       # under 133, above the 131.67 pad
    assert ZP.floor_held_a(band, f, len(f) - 1) is False


def test_NEGATIVE_his_call_1_flipped_breaks_the_pin(monkeypatch):
    """If PAD_FLOOR_HELD flips, a pierce inside the pad reads held on the engine while
    A_held's definition (drawn floor) must be revisited: this pin says so."""
    monkeypatch.setattr(LP, "PAD_FLOOR_HELD", True)
    band = BANDS[0]
    f = _fh_frame(132.5)
    j = len(f) - 1
    win = f.iloc[max(0, j - ZP.SWEEP_WINDOW - 2):j + 1]
    drawn = AG.floor_held_gate(band, frame=win)
    monkeypatch.setattr(LP, "PAD_FLOOR_HELD", False)
    assert AG.floor_held_gate(band, frame=win) is False
    assert drawn is True


# ── q2_tables carries A_held ─────────────────────────────────────────────────
def _events(n_dates=30, per=3, held_every=2):
    rows = []
    dates = pd.bdate_range("2025-01-02", periods=n_dates).strftime("%Y-%m-%d")
    k = 0
    for d in dates:
        for i in range(per):
            k += 1
            r = {"q": "q2", "cohort": "A", "symbol": "S%d" % i, "date": d, "j": k,
                 "lo": 100.0, "hi": 101.0, "entry": 101.0,
                 "floor_held_a": (k % held_every == 0)}
            for cl in ZP.CLOCKS:
                r["a_pct%d" % cl], r["b_pct%d" % cl] = 1.0, 1.5
                r["a_R%d" % cl], r["b_R%d" % cl] = 0.5, 0.4
                r["a_why%d" % cl], r["b_why%d" % cl] = "clock", "clock"
            rows.append(r)
    return pd.DataFrame(rows)


def test_q2_tables_reports_A_held_as_the_held_subset():
    E = _events()
    out = ZP.q2_tables(E, pd.DataFrame(), draws=200, perm=50)
    n_held = int(E["floor_held_a"].sum())
    assert out["n_A"] == len(E) and out["A_held"]["n"] == n_held and 0 < n_held < len(E)
    assert out["A_held"]["paired"]["d_pct20"]["mean"] == pytest.approx(0.5)


def test_NEGATIVE_q2_tables_says_A_held_is_missing_on_old_rows():
    E = _events().drop(columns=["floor_held_a"])
    out = ZP.q2_tables(E, pd.DataFrame(), draws=200, perm=50)
    assert out["A_held"]["n"] == 0 and "missing" in out["A_held"]


def test_NEGATIVE_csv_string_bools_never_count_as_held():
    E = _events()
    E["floor_held_a"] = E["floor_held_a"].map(lambda v: "True" if v else "False")
    out = ZP.q2_tables(E, pd.DataFrame(), draws=200, perm=50)
    assert out["A_held"]["n"] == int((E["floor_held_a"] == "True").sum())


def test_replay_rows_carry_floor_held_a_on_cohort_a_only():
    from tests.test_zone_pad_study import _frame
    rows = []
    for seed in (11, 23, 37, 41):
        rows += ZP.replay_symbol("S%d" % seed, _frame(seed=seed))
    q2 = [r for r in rows if r["q"] == "q2"]
    assert any(r["cohort"] == "A" for r in q2)
    for r in q2:
        assert ("floor_held_a" in r) == (r["cohort"] == "A")
        if r["cohort"] == "A":
            assert isinstance(r["floor_held_a"], bool)
