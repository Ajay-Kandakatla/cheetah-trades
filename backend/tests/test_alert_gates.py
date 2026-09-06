"""supply_demand/alert_gates — the ONE phone gate the three S/D push paths share.

Ajay 2026-09-05 (verbatim): "When alert I need the same logic. Need only
alerts on stocks that have atleast 5% to Supply and also <1% bounce from
demand zone". Boards keep listing everything; only the phone tightens.

Pure tests on synthetic bands (NEGATIVES throughout). S/D scope: configured
house numbers, not a book method, no cites.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import alert_gates as AG   # noqa: E402

DEM = {"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 2, "strength": 30.0}


def _sup(lo, hi, touches=2):
    return {"kind": "supply", "lo": lo, "hi": hi, "touches": touches, "strength": 50.0}


# ── the two owner numbers come straight from his sentence ─────────────────────
def test_owner_constants_are_his_sentence():
    assert AG.ALERT_MIN_ROOM_PCT == 5.0             # "atleast 5% to Supply"
    assert AG.ALERT_MAX_ABOVE_DEMAND_PCT == 1.0     # "<1% bounce from demand zone"


# ── room_gate ─────────────────────────────────────────────────────────────────
def test_clear_runway_passes_with_no_room_dict():
    ok, room = AG.room_gate(100.0, [DEM], None)
    assert ok is True and room is None
    ok, room = AG.room_gate(100.0, [], 99.0)
    assert ok is True and room is None


def test_four_point_nine_percent_fails_five_passes():
    ok, room = AG.room_gate(100.0, [DEM, _sup(104.9, 106.0)], None)
    assert ok is False and room["state"] == "ROOM" and room["room_pct"] == 4.9 and room["target"] == 104.9
    ok, room = AG.room_gate(100.0, [DEM, _sup(105.0, 106.0)], None)
    assert ok is True and room["room_pct"] == 5.0 and room["target"] == 105.0 and room["touches"] == 2


def test_inside_a_supply_band_fails_and_measures_to_its_top():
    ok, room = AG.room_gate(100.0, [_sup(99.0, 101.0), _sup(120.0, 125.0)], None)
    assert ok is False and room["state"] == "IN_BAND"
    assert room["target"] == 101.0 and room["room_pct"] == 1.0, "the top of the band we are IN, not the next floor"
    ok_top, room_top = AG.room_gate(101.0, [_sup(99.0, 101.0)], None)
    assert ok_top is False and room_top["state"] == "IN_BAND", "sitting on the top is still in the band"


def test_a_supply_band_yesterday_closed_above_is_broken_and_not_a_ceiling():
    bands = [_sup(104.0, 105.0)]
    assert AG.room_gate(100.0, bands, 106.0) == (True, None), "hi 105 < prev 106: broken = support, ignored"
    ok, room = AG.room_gate(100.0, bands, 104.5)
    assert ok is False and room["room_pct"] == 4.0, "hi 105 >= prev 104.5: still resistance"
    ok, room = AG.room_gate(100.0, bands, 105.0)
    assert ok is False, "prev close ON the top: not broken (same edge as read_breaking's broke rule)"
    ok, room = AG.room_gate(100.0, bands, None)
    assert ok is False and room["room_pct"] == 4.0, "unknown prev close: every supply band counts"
    # the ceiling is the first UNBROKEN band: broken 104-105 skipped, 108-110 (8%) is the target
    ok, room = AG.room_gate(100.0, [_sup(104.0, 105.0), _sup(108.0, 110.0)], 106.0)
    assert ok is True and room["target"] == 108.0 and room["room_pct"] == 8.0


def test_a_demand_band_above_the_print_is_broken_support_and_counts_as_overhead():
    ok, room = AG.room_gate(100.0, [{"kind": "demand", "lo": 103.0, "hi": 104.0, "touches": 3}], None)
    assert ok is False and room["room_pct"] == 3.0 and room["band"]["kind"] == "demand"
    # a demand band that CONTAINS the print is support, never overhead
    assert AG.room_gate(100.0, [{"kind": "demand", "lo": 99.0, "hi": 101.0}], None) == (True, None)
    # a supply band BELOW the print is not overhead either
    assert AG.room_gate(100.0, [_sup(95.0, 98.0)], None) == (True, None)


def test_room_gate_garbage_never_crashes_and_never_passes_silently():
    assert AG.room_gate(None, [_sup(104.0, 105.0)], None) == (False, None)
    assert AG.room_gate(0, [_sup(104.0, 105.0)], None) == (False, None)
    assert AG.room_gate("x", [], None) == (False, None)
    assert AG.room_gate(100.0, [{"kind": "supply", "lo": None, "hi": 105.0}], None) == (True, None)
    assert AG.room_gate(100.0, [{"kind": "supply", "lo": 106.0, "hi": 105.0}], None) == (True, None)  # inverted
    assert AG.room_gate(100.0, None, None) == (True, None)


# ── demand_proximity_gate ─────────────────────────────────────────────────────
def test_print_within_one_percent_above_the_band_passes_further_fails():
    assert AG.demand_proximity_gate(92.92, DEM) is True             # 1.0% above the top
    assert AG.demand_proximity_gate(92.0 * 1.012, DEM) is False     # 1.2% above: late
    assert AG.demand_proximity_gate(92.0 * 1.010 + 0.001, DEM) is False
    assert AG.demand_proximity_gate(95.7, DEM) is False             # the +4% bounce that already ran


def test_print_inside_the_band_passes_under_the_floor_fails():
    assert AG.demand_proximity_gate(91.0, DEM) is True
    assert AG.demand_proximity_gate(90.0, DEM) is True              # on the floor
    assert AG.demand_proximity_gate(92.0, DEM) is True              # on the top
    assert AG.demand_proximity_gate(89.99, DEM) is False, "fell through = no push"
    assert AG.demand_proximity_gate(80.0, DEM) is False


def test_proximity_garbage_never_crashes_and_fails_closed():
    assert AG.demand_proximity_gate(None, DEM) is False
    assert AG.demand_proximity_gate(0, DEM) is False
    assert AG.demand_proximity_gate(91.0, {}) is False
    assert AG.demand_proximity_gate(91.0, {"lo": None, "hi": 92.0}) is False
    assert AG.demand_proximity_gate(91.0, {"lo": 93.0, "hi": 92.0}) is False   # inverted


# ── the one wording every push body uses ──────────────────────────────────────
def test_room_txt_is_the_wording_zone_bounce_pushes_already_use():
    assert AG.room_txt(None) == "room: clear runway"
    assert AG.room_txt({"room_pct": 12.0, "target": 112.0}) == "room +12% -> $112"
    assert AG.room_txt({"room_pct": 20.0, "target": 205.4, "rr": 3.6}) == "room +20% -> $205.4 (3.6R)"
    assert AG.room_txt({"room_pct": 2.9, "target": 180.07, "rr": None}) == "room +2.9% -> $180.07"


def test_room_read_rounds_like_room_for_and_reports_the_first_overhead():
    room = AG.room_read(171.2, [_sup(161.78, 167.54, 1), _sup(205.4, 212.72, 2)], 180.77)
    assert room == {"state": "ROOM", "room_pct": 20.0, "target": 205.4, "touches": 2,
                    "room_pct_raw": pytest.approx((205.4 - 171.2) / 171.2 * 100.0, abs=1e-4),
                    "band": {"kind": "supply", "lo": 205.4, "hi": 212.72, "touches": 2}}
    assert AG.room_read(171.2, [_sup(161.78, 167.54, 1)], 180.77) is None


@pytest.mark.parametrize("px", [50.0, 99.0, 100.0, 104.5, 106.0, 110.0, 130.0])
def test_first_overhead_agrees_with_bounce_room_when_no_band_is_broken(px):
    """Same fixture, same answer as the filter twin (bounce_room.first_overhead)
    whenever prev_close is unknown — the gate adds ONLY the broken-band rule."""
    from supply_demand import bounce_room as BR
    bands = [DEM, _sup(99.0, 101.0), _sup(104.0, 105.0), _sup(120.0, 125.0),
             {"kind": "demand", "lo": 105.0, "hi": 107.0, "touches": 2, "strength": 50.0}]
    theirs = BR.first_overhead(BR.overhead_bands(bands, px), px)
    ours = AG.first_overhead(bands, px, None)
    if theirs is None:
        assert ours is None
    else:
        assert (ours["lo"], ours["hi"]) == (theirs["lo"], theirs["hi"])


@pytest.mark.parametrize("px,pc", [(96.0, 100.0), (96.0, 97.0), (99.0, 100.0), (104.5, 104.0),
                                   (104.5, 106.0), (110.0, 130.0), (130.0, 100.0)])
def test_first_overhead_agrees_with_bounce_room_when_a_band_IS_broken(px, pc):
    """Integrator 2026-09-05: bounce_room.first_overhead learned prev_close, so the
    parity holds on the broken-band geometry too — the 🪃 push body and the SEPA
    🪃 chip / Demand sort quote the same first ceiling."""
    from supply_demand import bounce_room as BR
    bands = [DEM, _sup(95.0, 97.0), _sup(99.0, 101.0), _sup(104.0, 105.0), _sup(120.0, 125.0),
             {"kind": "demand", "lo": 105.0, "hi": 107.0, "touches": 2, "strength": 50.0}]
    theirs = BR.first_overhead(BR.overhead_bands(bands, px, pc), px)
    ours = AG.first_overhead(bands, px, pc)
    if theirs is None:
        assert ours is None
    else:
        assert (ours["lo"], ours["hi"]) == (theirs["lo"], theirs["hi"])


def test_boundary_4_995_pct_rounds_to_5_0_but_FAILS_and_says_so_raw():
    """review 2026-09-05: room_pct is shown at 1 dp, the gate compares RAW.
    4.995% prints as 5.0 and must still fail — and room_pct_raw carries the
    number the callers format (2 dp) so the message never reads '5.0% < 5%'."""
    ok, room = AG.room_gate(100.0, [_sup(104.995, 106.0)], None)
    assert ok is False
    assert room["room_pct"] == 5.0
    assert room["room_pct_raw"] == pytest.approx(4.995, abs=1e-6)
    assert room["room_pct_raw"] < AG.ALERT_MIN_ROOM_PCT
    ok, room = AG.room_gate(100.0, [_sup(105.0, 106.0)], None)
    assert ok is True and room["room_pct_raw"] == pytest.approx(5.0, abs=1e-9)
    inb = AG.room_read(100.0, [_sup(99.0, 101.0)])
    assert inb["state"] == "IN_BAND" and inb["room_pct_raw"] == pytest.approx(1.0, abs=1e-9)


# ── proven lids (Ajay 2026-09-06, "ok please all 3" — the KLAC lesson) ────────
KLAC_BANDS = [{"kind": "demand", "lo": 164.60, "hi": 169.81, "touches": 3, "strength": 100.0},
              {"kind": "supply", "lo": 166.37, "hi": 172.30, "touches": 1, "strength": 32.0},
              {"kind": "supply", "lo": 191.11, "hi": 193.94, "touches": 2, "strength": 53.0}]


def test_proven_band_is_the_boards_own_bar():
    assert (AG.LID_MIN_TOUCHES, AG.LID_MIN_STRENGTH) == (2, 40.0)
    assert AG.is_proven_band({"lo": 1, "hi": 2, "touches": 2, "strength": 40.0}) is True
    assert AG.is_proven_band({"lo": 1, "hi": 2, "touches": 1, "strength": 90.0}) is False, "one touch is not structure"
    assert AG.is_proven_band({"lo": 1, "hi": 2, "touches": 3, "strength": 39.9}) is False, "weak band"
    assert AG.is_proven_band({"lo": 1, "hi": 2, "touches": 2}) is True, "unknown strength: judged on touches"
    assert AG.is_proven_band({"lo": 1, "hi": 2}) is True, "unknown touches: keep the lid (conservative)"
    assert AG.is_proven_band({"lo": 1, "hi": 2, "touches": 0, "strength": 5.0}) is True, "0 = nobody counted"
    assert AG.is_proven_band({"lo": 1, "hi": 2, "touches": "nan", "strength": 5.0}) is True
    assert AG.is_proven_band(None) is False and AG.is_proven_band("x") is False


def test_klac_2026_09_02_the_one_touch_lid_no_longer_blocks_the_push():
    """Print 169.50 inside the 164.60-169.81 demand band with a 1-touch /
    strength-32 supply band 166.37-172.30 on top of it. Before: IN_BAND, no
    push, no paper buy for two days. Now: room to the next PROVEN lid 191.11."""
    ok, room = AG.room_gate(169.50, KLAC_BANDS, 167.56)
    assert ok is True and room["state"] == "ROOM" and room["target"] == 191.11
    assert room["room_pct"] == 12.7 and room["touches"] == 2
    assert AG.demand_proximity_gate(169.50, KLAC_BANDS[0]) is True
    # the same lid PROVEN (2 touches, strength 53) is a real ceiling: blocked as before
    proven = [dict(b, touches=2, strength=53.0) if b["lo"] == 166.37 else b for b in KLAC_BANDS]
    ok2, room2 = AG.room_gate(169.50, proven, 167.56)
    assert ok2 is False and room2["state"] == "IN_BAND" and room2["target"] == 172.30
    # strength alone does not rescue a one-touch lid; touches alone do not rescue a weak one
    assert AG.room_gate(169.50, [dict(b, strength=90.0) if b["lo"] == 166.37 else b for b in KLAC_BANDS], 167.56)[0] is True
    assert AG.room_gate(169.50, [dict(b, touches=3) if b["lo"] == 166.37 else b for b in KLAC_BANDS], 167.56)[0] is True
    # overhead_bands itself drops the lid; the board still holds every band (the caller's list is untouched)
    assert [b["lo"] for b in AG.overhead_bands(KLAC_BANDS, 169.50, 167.56)] == [191.11]
    assert len(KLAC_BANDS) == 3


def test_plan_txt_is_the_paper_lanes_stop_and_the_first_proven_target():
    room = AG.room_read(169.50, KLAC_BANDS, 167.56)
    txt = AG.plan_txt(169.50, KLAC_BANDS[0], room)
    assert txt == "buy $164.6-169.81 · stop $163.78 (0.5% under the floor, 3.4% risk) · target $191.11 (3.8R)"
    assert AG.plan_txt(169.50, KLAC_BANDS[0], None) == \
        "buy $164.6-169.81 · stop $163.78 (0.5% under the floor, 3.4% risk) · target: clear runway"
    # risk is measured from the PRINT: a bounce that already ran shows the wider risk
    assert "5.8% risk" in AG.plan_txt(173.9, KLAC_BANDS[0], room)
    # garbage in -> '' (the body omits the plan, never prints nonsense)
    assert AG.plan_txt(None, KLAC_BANDS[0], room) == ""
    assert AG.plan_txt(0, KLAC_BANDS[0], room) == ""
    assert AG.plan_txt(169.5, {"lo": 170.0, "hi": 160.0}, room) == ""
    assert AG.plan_txt(169.5, None, room) == ""
    # a target under the print (stale room) prints no R multiple rather than a negative one
    assert AG.plan_txt(169.5, KLAC_BANDS[0], {"target": 150.0}).endswith("target $150")
    assert AG.STOP_BUFFER_PCT == 0.5
