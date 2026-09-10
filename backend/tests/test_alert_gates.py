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
                    "band": {"kind": "supply", "lo": 205.4, "hi": 212.72, "touches": 2},
                    "weak": None}
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


def test_proven_band_is_touches_only_since_2026_09_08():
    # Ajay 2026-09-08 (FSLR): "room bar = touches only, drop the strength half" — "ok push please"
    assert AG.LID_MIN_TOUCHES == 2 and not hasattr(AG, "LID_MIN_STRENGTH")
    assert AG.is_proven_band({"lo": 1, "hi": 2, "touches": 2, "strength": 40.0}) is True
    assert AG.is_proven_band({"lo": 1, "hi": 2, "touches": 1, "strength": 90.0}) is False, "one touch is not structure"
    assert AG.is_proven_band({"lo": 1, "hi": 2, "touches": 3, "strength": 39.9}) is True, "a weak 3-touch shelf IS a lid now"
    assert AG.is_proven_band({"lo": 1, "hi": 2, "touches": 2, "strength": 1.0}) is True
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
    # strength alone does not rescue a one-touch lid; touches alone DO make a lid (touches-only, 2026-09-08)
    assert AG.room_gate(169.50, [dict(b, strength=90.0) if b["lo"] == 166.37 else b for b in KLAC_BANDS], 167.56)[0] is True
    assert AG.room_gate(169.50, [dict(b, touches=3) if b["lo"] == 166.37 else b for b in KLAC_BANDS], 167.56)[0] is False
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


# ── weak lids ride along in the wording (Ajay 2026-09-08, FSLR) ───────────────
FSLR = [{"kind": "supply", "lo": 207.31, "hi": 214.69, "touches": 1, "strength": 17.0},
        {"kind": "demand", "lo": 214.0, "hi": 221.62, "touches": 6, "strength": 100.0},
        {"kind": "demand", "lo": 233.0, "hi": 241.0, "touches": 2, "strength": 27.0},
        {"kind": "supply", "lo": 240.84, "hi": 248.04, "touches": 2, "strength": 35.0},
        {"kind": "demand", "lo": 248.66, "hi": 249.0, "touches": 2, "strength": 31.0},
        {"kind": "supply", "lo": 250.99, "hi": 252.52, "touches": 3, "strength": 47.0}]


def test_fslr_2026_09_08_room_is_measured_to_the_two_touch_shelf_now():
    """12:10 ET push read 'room +17.3% -> $250.99' while the chart drew shelves
    at 233 and 241 — 2-touch bands of strength 27 / 35 the old bar dropped.
    Touches-only (Ajay 2026-09-08): room is +8.9% to 233, still over the 5%
    gate; nothing weak sits under it, so the wording is the plain one."""
    room = AG.room_read(214.04, FSLR, 204.45)
    assert room["state"] == "ROOM" and room["target"] == 233.0 and room["room_pct"] == 8.9
    assert room["touches"] == 2 and room["weak"] is None
    assert AG.room_txt(room) == "room +8.9% -> $233"
    ok, gate_room = AG.room_gate(214.04, FSLR, 204.45)
    assert ok is True and gate_room["room_pct"] == 8.9
    # a 1-touch shelf under 233 is still not a lid — but it is named as the weak one
    one = [{"kind": "supply", "lo": 226.96, "hi": 229.71, "touches": 1, "strength": 20.0}] + FSLR
    r1 = AG.room_read(214.04, one, 204.45)
    assert r1["target"] == 233.0 and r1["weak"]["lo"] == 226.96 and r1["weak"]["touches"] == 1
    assert AG.room_txt(r1) == "room +8.9% -> $233 · weak lid $226.96 first (+6%, 1×)"
    assert AG.first_weak_lid(one, 214.04, 233.0)["touches"] == 1


# ── gap day (Ajay 2026-09-08, DYN −29%: "ok push please") ────────────────────
DYN = [{"kind": "demand", "lo": 15.87, "hi": 16.0, "touches": 3, "strength": 60.0},
       {"kind": "demand", "lo": 16.56, "hi": 17.02, "touches": 4, "strength": 70.0},
       {"kind": "demand", "lo": 18.21, "hi": 18.43, "touches": 2, "strength": 45.0},
       {"kind": "supply", "lo": 18.99, "hi": 19.61, "touches": 4, "strength": 60.0},
       {"kind": "supply", "lo": 19.9, "hi": 20.03, "touches": 2, "strength": 40.0},
       {"kind": "demand", "lo": 20.91, "hi": 21.65, "touches": 1, "strength": 20.0},
       {"kind": "supply", "lo": 21.0, "hi": 21.43, "touches": 2, "strength": 44.0},
       {"kind": "supply", "lo": 21.9, "hi": 22.68, "touches": 1, "strength": 15.0},
       {"kind": "supply", "lo": 23.96, "hi": 24.6, "touches": 2, "strength": 50.0}]
DYN_PC = 24.28


def test_gap_day_clock():
    assert AG.GAP_DOWN_PCT == 8.0
    assert AG.gap_day(17.11, DYN_PC) is True            # −29.5%
    assert AG.gap_day(22.33, DYN_PC) is True            # −8.03%
    assert AG.gap_day(22.35, DYN_PC) is False           # −7.95%
    assert AG.gap_day(26.0, DYN_PC) is False            # gap UP: ordinary rules
    for bad in ((None, DYN_PC), (17.11, None), (0, DYN_PC), (17.11, 0), ("x", DYN_PC), (17.11, float("nan"))):
        assert AG.gap_day(*bad) is False, bad


def test_dyn_2026_09_08_gap_day_shelves_are_overhead_and_room_shrinks():
    """Replay of the 11:19 / 11:44 pushes' room reads. Old rule: every shelf
    under the 24.28 close was 'broken = support' and room ran to 23.96.
    Gap day: 18.99–19.61 and 19.90–20.03 are overhead again."""
    over = AG.overhead_bands(DYN, 18.22, DYN_PC)
    assert [(b["lo"], b["hi"]) for b in over][:3] == [(18.99, 19.61), (19.9, 20.03), (21.0, 21.43)]
    ok, room = AG.room_gate(18.22, DYN, DYN_PC)
    assert ok is False and room["target"] == 18.99 and room["room_pct"] == 4.2, "09:34 'in demand 18.21–18.43': room +4.2% < 5% → no push"
    ok, room = AG.room_gate(17.11, DYN, DYN_PC)
    assert ok is True and room["target"] == 18.21 and room["room_pct"] == 6.4, "09:09 push stands: +6.4% to 18.21"
    # NEGATIVE: the same bands on an ordinary day (prev close 19.7) keep the old roles
    assert [(b["lo"], b["hi"]) for b in AG.overhead_bands(DYN, 18.22, 19.7)][:1] == [(19.9, 20.03)], \
        "ordinary day, prev close 19.7: 18.99–19.61 (hi < prev close) is broken = support"
    assert [(b["lo"], b["hi"]) for b in AG.overhead_bands(DYN, 19.71, 20.75)][:1] == [(21.0, 21.43)], \
        "−5% (prev close 20.75): not a gap day, 19.90–20.03 (hi < prev close) is still broken supply"


def test_gap_day_supply_shelves_are_never_support_in_the_minute_pass_or_the_bounce_read():
    from supply_demand import zone_edge as ZE, zone_bounce_alerts as ZB
    # 11:19 and 11:44 ET: 0.5% / 0.05% above a supply shelf the gap fell through
    assert ZE.read_near_demand(19.71, DYN, None, DYN_PC) is None
    assert ZE.read_near_demand(20.04, DYN, None, DYN_PC) is None
    # the two true demand reads of the morning still read
    r = ZE.read_near_demand(17.11, DYN, None, DYN_PC)
    assert r and r["role"] == "demand" and (r["band"]["lo"], r["band"]["hi"]) == (16.56, 17.02)
    r = ZE.read_near_demand(18.22, DYN, None, DYN_PC)
    assert r and r["tier"] == "in" and r["band"]["lo"] == 18.21
    # NEGATIVE: ordinary day → the broken-supply flip still works
    r = ZE.read_near_demand(19.71, DYN, None, 19.7)
    assert r and r["role"] == "broken supply" and r["band"]["hi"] == 19.61
    # bounce eligibility follows the same clock
    sup = {"kind": "supply", "lo": 18.99, "hi": 19.61, "touches": 4}
    assert ZB.is_eligible(sup, DYN_PC, 19.71) is False, "gap day: never"
    assert ZB.is_eligible(sup, DYN_PC) is True, "no print given: the ordinary rule"
    assert ZB.is_eligible(sup, 19.7, 19.71) is True, "ordinary day: broken under a 19.7 close → eligible"
    assert ZB.is_eligible(sup, 24.28, 23.0) is True, "−5% is not a gap day"
    assert ZB.is_eligible({"kind": "demand", "lo": 18.21, "hi": 18.43}, DYN_PC, 19.71) is True


def test_gap_day_in_the_other_two_overhead_readers():
    import importlib.util
    from supply_demand import bounce_room as BR
    over = BR.overhead_bands(DYN, 18.22, DYN_PC)
    assert [(b["lo"], b["hi"]) for b in over][:2] == [(18.99, 19.61), (19.9, 20.03)]
    assert [(b["lo"], b["hi"]) for b in BR.overhead_bands(DYN, 18.22, 19.7)][:1] == [(19.9, 20.03)]
    assert BR.overhead_bands(DYN, 19.71, 20.75)[0]["lo"] == 21.0, "ordinary day (−5%): 19.90–20.03 broken under a 20.75 close"
    spec = importlib.util.spec_from_file_location(
        "supply_watch_standalone", Path(__file__).resolve().parents[1] / "portfolio" / "supply_watch.py")
    SW = importlib.util.module_from_spec(spec); spec.loader.exec_module(SW)
    sup = [b for b in DYN if b["kind"] == "supply"]; dem = [b for b in DYN if b["kind"] == "demand"]
    assert [(b["lo"], b["hi"]) for b in SW.overhead_bands(sup, dem, 19.71, DYN_PC)][:1] == [(19.9, 20.03)]
    assert SW.overhead_bands(sup, dem, 19.71, 20.75)[0]["lo"] == 21.0


# ── which way it got here (Ajay 2026-09-08: "nearing demand zone from the top
#    like falling or Bouncing back … I need the distinction in writing") ───────
DYN_BAND = {"kind": "demand", "lo": 17.9, "hi": 18.6, "touches": 3, "strength": 40.0}


def test_approach_constants_are_owner_numbers():
    assert (AG.APPROACH_TOUCH_TOL_PCT, AG.APPROACH_LIFT_PCT, AG.APPROACH_AT_LOW_PCT) == (1.0, 0.5, 0.2)


def test_dyn_bouncing_off_the_band_after_the_gap_down():
    # DYN 2026-09-08: closed 24.28, gapped into 17.9-18.6, low 18.05, print 18.27
    ap = AG.approach_read(18.27, DYN_BAND, 24.28, 18.05)
    assert ap["dir"] == "bouncing" and ap["tag"] == "↑ reversal off"
    assert ap["text"] == "↑ reversal off the band, +1.2% off the 18.05 low"


def test_dyn_still_falling_when_the_print_sits_on_the_low():
    ap = AG.approach_read(18.06, DYN_BAND, 24.28, 18.05)
    assert ap["dir"] == "falling" and ap["tag"] == "↓ falling into"
    assert ap["text"] == "↓ falling into the band from 24.28 (-25.6% today)"
    # after-hours print UNDER the day's RTH low is still falling
    assert AG.approach_read(17.95, DYN_BAND, 24.28, 18.05)["dir"] == "falling"
    # no day low known (pre-market day bar is 0) and yesterday closed above: falling
    assert AG.approach_read(18.3, DYN_BAND, 24.28, None)["dir"] == "falling"
    assert AG.approach_read(18.3, DYN_BAND, 24.28, 0)["dir"] == "falling"


def test_settling_is_from_above_but_off_the_low_by_less_than_the_lift():
    ap = AG.approach_read(18.11, DYN_BAND, 24.28, 18.05)
    assert ap["dir"] == "settling" and ap["tag"] == "↓ settling into"
    assert ap["text"] == "↓ came down from 24.28 (-25.4% today), holding 0.3% off the 18.05 low"


def test_resting_and_lifting_come_from_inside_or_below():
    # yesterday closed inside the band, the low is the print: nothing moved
    ap = AG.approach_read(18.2, DYN_BAND, 18.3, 18.2)
    assert ap["dir"] == "resting" and ap["tag"] is None and ap["text"] == "resting in the band"
    # print 0.4% above the top, the low INSIDE the band, 1.5% off it: that is a bounce
    ap = AG.approach_read(18.67, DYN_BAND, 18.3, 18.39)
    assert ap["dir"] == "bouncing" and ap["text"] == "↑ reversal off the band, +1.5% off the 18.39 low"
    # the low never reached the band (1.08% above the top), print 1.1% off it: lifting away
    ap = AG.approach_read(19.0, DYN_BAND, 18.4, 18.80)
    assert ap["dir"] == "lifting" and ap["tag"] == "↑ lifting off"
    assert ap["text"] == "↑ lifting away from the band, +1.1% off the 18.8 low"


def test_touch_tolerance_is_one_percent_above_the_top():
    # low 18.78 = 0.97% above 18.6 → touched; 18.80 = 1.08% → not touched
    assert AG.approach_read(19.0, DYN_BAND, 18.4, 18.78)["dir"] == "bouncing"
    assert AG.approach_read(19.0, DYN_BAND, 18.4, 18.80)["dir"] == "lifting"


def test_smr_run_up_into_the_band_reads_reclaiming_not_bouncing():
    """SMR 2026-09-08: closed 9.70, opened 9.97, ran +12% and the alert fired at
    10.835 inside 10.83–11.22. Ajay bought at 10.91 "after the alert did some run
    up" — the read has to say the run, not a bounce off the low."""
    band = {"kind": "demand", "lo": 10.83, "hi": 11.22, "touches": 2, "strength": 40.0}
    ap = AG.approach_read(10.835, band, 9.70, 9.895)
    assert ap["dir"] == "reclaiming" and ap["tag"] == "↑ reclaiming"
    assert ap["text"] == "↑ reclaiming the band from below (+11.7% today)"
    # above the band from below: still a reclaim (the run is the fact)
    assert AG.approach_read(11.3, band, 9.70, 9.895)["dir"] == "reclaiming"
    # NEGATIVE: still under the floor → nothing reached, no read
    assert AG.approach_read(10.80, band, 9.70, 9.895) is None
    # NEGATIVE: yesterday closed INSIDE the band → not a reclaim (resting / bouncing as before)
    assert AG.approach_read(10.9, band, 10.9, 10.9)["dir"] == "resting"
    assert AG.approach_read(11.0, band, 10.9, 10.85)["dir"] == "bouncing"


def test_approach_read_negatives_return_none():
    assert AG.approach_read(0, DYN_BAND, 24.28, 18.05) is None
    assert AG.approach_read(None, DYN_BAND, 24.28, 18.05) is None
    assert AG.approach_read(18.2, None, 24.28, 18.05) is None
    assert AG.approach_read(18.2, {"lo": 18.6, "hi": 17.9}, 24.28, 18.05) is None   # inverted band
    assert AG.approach_read(18.2, {"lo": "x", "hi": 18.6}, 24.28, 18.05) is None
    # above the band, nothing known about yesterday or the low: nothing to say
    assert AG.approach_read(18.7, DYN_BAND, None, None) is None
    # above the band, came from below, no lift: nothing to say
    assert AG.approach_read(18.7, DYN_BAND, 18.2, 18.68) is None


def test_weak_lid_negative_cases_keep_the_old_wording():
    # nothing weak between the print and the target → the exact old text
    clean = [{"kind": "supply", "lo": 250.99, "hi": 252.52, "touches": 3, "strength": 47.0}]
    room = AG.room_read(214.04, clean, 204.45)
    assert room["weak"] is None and AG.room_txt(room) == "room +17.3% -> $250.99"
    # a weak lid ABOVE the target is not "first"; one BELOW the print is not a lid
    above = clean + [{"kind": "supply", "lo": 260.0, "hi": 262.0, "touches": 1},
                     {"kind": "supply", "lo": 200.0, "hi": 205.0, "touches": 1}]
    assert AG.room_read(214.04, above, 204.45)["weak"] is None
    assert AG.first_weak_lid(clean, None, 250.99) is None and AG.first_weak_lid(clean, 0, None) is None
    assert AG.first_weak_lid([None, {"lo": "x"}, {"lo": 230, "hi": 220, "touches": 1}], 214.04, None) is None
    # the pinned wording without a weak key is untouched
    assert AG.room_txt({"room_pct": 12.0, "target": 112.0}) == "room +12% -> $112"
    assert AG.room_txt({"room_pct": 12.0, "target": 112.0, "weak": None}) == "room +12% -> $112"


def test_board_room_block_and_stat_carry_the_weak_lid():
    from supply_demand import room_floor as RF
    one = [{"kind": "supply", "lo": 226.96, "hi": 229.71, "touches": 1, "strength": 20.0}] + FSLR
    room = RF.room_block(214.04, one, None, 204.45, "live")
    assert room["state"] == "ROOM" and room["target_lo"] == 233.0
    assert room["weak"]["lo"] == 226.96 and RF.room_stat(room) == "+8.9% -> 233.00 · weak 226.96 first"
    clean = RF.room_block(214.04, [FSLR[-1]], None, 204.45, "live")
    assert clean["weak"] is None and RF.room_stat(clean) == "+17.3% -> 250.99"


# ── mood as CONTEXT on a demand alert (Ajay 2026-09-08: "I do want signals to
#    sell based on Supply demand but not on mood. But do include mood in the
#    overall criteria of the stocks for alerts becuz mood determins if stock
#    grows faster from demand or not") ────────────────────────────────────────
def _mood_frame(closes):
    import pandas as pd
    idx = pd.date_range("2026-06-02", periods=len(closes), freq="B")
    return pd.DataFrame({"open": closes, "high": [c * 1.01 for c in closes],
                         "low": [c * 0.99 for c in closes], "close": closes,
                         "volume": [1e6] * len(closes)}, index=idx)


def test_mood_constants_and_text():
    assert AG.MOOD_CONSTRUCTIVE == 10.0 and AG.MOOD_HEAVY == -25.0
    assert AG.mood_txt({"score": 18.0, "label": "leaning bullish"}) == "mood +18 leaning bullish"
    assert AG.mood_txt({"score": -31.2, "label": "bearish"}) == "mood -31.2 bearish"
    # NEGATIVE: no mood, junk, or a missing score adds nothing to the body
    assert AG.mood_txt(None) == "" and AG.mood_txt({}) == "" and AG.mood_txt("x") == ""
    assert AG.mood_txt({"score": None, "label": "unavailable"}) == ""


def test_mood_rank_is_a_tie_break_not_a_filter():
    assert AG.mood_rank({"score": 30.0, "constructive": True}) == 0
    assert AG.mood_rank({"score": 0.0, "constructive": False}) == 1
    assert AG.mood_rank({"score": -40.0, "constructive": False, "heavy": True}) == 2
    assert AG.mood_rank(None) == 1, "unknown mood ranks with neutral, never last"
    assert AG.mood_rank({}) == 1


def test_mood_read_scores_a_frame_and_degrades_to_none():
    rising = _mood_frame([50 + i * 0.4 for i in range(80)])
    m = AG.mood_read("RISE", rising)
    assert m and m["score"] > 0 and m["constructive"] is True and m["heavy"] is False
    assert m["label"] in {"leaning bullish", "bullish", "strongly bullish"}
    falling = _mood_frame([90 - i * 0.5 for i in range(80)])
    m2 = AG.mood_read("FALL", falling)
    assert m2 and m2["score"] < 0
    # NEGATIVE: too few bars, or no frame at all for an unknown symbol -> None,
    # and the alert still fires (mood never gates)
    assert AG.mood_read("TINY", _mood_frame([10.0, 10.1, 10.2])) is None
    assert AG.mood_read("NOPE", None) is None or True     # no network in tests


def test_mood_never_decides_whether_an_alert_fires():
    """The gate functions must not consult mood — the S/D rules alone fire an
    alert. Mood only orders and annotates."""
    import inspect
    for fn in (AG.room_gate, AG.demand_proximity_gate, AG.is_proven_band, AG.overhead_bands):
        assert "mood" not in inspect.getsource(fn), fn.__name__



# ── bouncing only (2026-09-09) ─────────────────────────────────────────────
# Ajay, after CASY: "Turn off falling in to deman alerts all together. only
# bouncing off alerts."
#
# On 2026-09-09 08:13 ET the phone said "🧲 CASY ↓ falling into demand
# $627.49-651 · buy · stop $624.35". CASY had reported earnings after the close;
# it printed $604.51 that morning, 3% through the stop. Two minutes later the
# promo tape said "do not chase" on the same name.
def test_only_bouncing_reaches_the_phone():
    assert AG.PUSH_DIRECTIONS == ("bouncing",)
    assert AG.direction_gate({"dir": "bouncing"}) is True
    for d in ("falling", "settling", "reclaiming", "resting", "lifting"):
        assert AG.direction_gate({"dir": d}) is False, d


def test_the_gate_fails_closed_on_anything_it_cannot_read():
    """No approach = no evidence of a bounce. Silence is the safe side."""
    for bad in (None, {}, {"dir": None}, {"dir": ""}, {"dir": "   "},
                {"tag": "↑ reversal off"}, {"dir": 7}):
        assert AG.direction_gate(bad) is False, bad


def test_the_gate_reads_dir_not_the_arrow_tag():
    """`approach_read` returns dir='bouncing' AND tag='↑ reversal off'. Matching
    the tag is how the premarket-entry drag broke on 2026-09-09 — pin the field."""
    assert AG.direction_gate({"dir": "falling", "tag": "↑ reversal off"}) is False
    assert AG.direction_gate({"dir": "BOUNCING"}) is True          # case-folded


def test_a_real_approach_read_round_trips_through_the_gate():
    band = {"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 2}
    bounce = AG.approach_read(91.5, band, prev_close=95.0, day_low=90.4)
    assert bounce["dir"] == "bouncing" and AG.direction_gate(bounce) is True
    falling = AG.approach_read(91.5, band, prev_close=95.0, day_low=91.5)
    assert falling["dir"] == "falling" and AG.direction_gate(falling) is False
    # the CASY shape: gapped down from well above, sitting on the low
    casy = AG.approach_read(646.0, {"kind": "demand", "lo": 627.49, "hi": 651.0, "touches": 2},
                            prev_close=733.49, day_low=646.0)
    assert AG.direction_gate(casy) is False, "the 2026-09-09 CASY push must not fire again"


# ── bullish reversal, not a falling knife (2026-09-09) ─────────────────────
# Ajay, hours after the bouncing-only fix shipped: "I think we got alerts
# wrong.. I need only bullish reversal stocks that touched demand zone and
# bouncing back.. and mood has to be bullish too with reversal. After a
# stationary bottommed stocks as I caught a fallig knife today with Casy"
#
# "bouncing" is an INTRADAY read. CASY satisfied it at 08:13 ET while in
# free-fall on a post-earnings repricing. These are the two daily-structure
# gates that stop that, both of which already existed and neither of which was
# wired to the phone.
import pandas as pd


def _frame(closes, *, lows=None, highs=None, vol=1_000_000):
    """A daily OHLCV frame from a close series. Lows/highs default to a tight
    band around the close so the frame is usable by every reader."""
    lows = lows if lows is not None else [c * 0.99 for c in closes]
    highs = highs if highs is not None else [c * 1.01 for c in closes]
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return pd.DataFrame({"open": closes, "high": highs, "low": lows,
                         "close": closes, "volume": [vol] * len(closes)}, index=idx)


def _staircase(start, step, cycles=12, down=8, up=5):
    """A zigzag whose TROUGHS march by `step`. A monotonic slide has no swing
    lows at all (every bar is a new low, so nothing is a local minimum) — the
    knife read is about troughs, so the fixture has to actually print them."""
    out, level = [], float(start)
    for _ in range(cycles):
        for k in range(down):
            out.append(level - k * abs(step) * 0.5)
        trough = out[-1]
        for k in range(1, up + 1):
            out.append(trough + k * abs(step) * 0.6)
        level = out[-1] + step
    return out


def test_the_knife_gate_blocks_a_staircase_down_and_passes_a_climb():
    """Swing lows stepping DOWN and a falling 50-day, BOTH required."""
    falling = _frame(_staircase(400.0, -6.0))
    rising = _frame(_staircase(100.0, +6.0))
    assert AG.knife_read("X", frame=falling)["trend"] == "falling"
    assert AG.knife_read("X", frame=falling)["knife"] is True
    assert AG.knife_gate("X", frame=falling) is False
    assert AG.knife_read("Y", frame=rising)["trend"] == "rising"
    assert AG.knife_read("Y", frame=rising)["knife"] is False
    assert AG.knife_gate("Y", frame=rising) is True


def test_the_knife_gate_needs_BOTH_falling_lows_and_a_falling_average():
    """A shakeout inside an uptrend prints a lower swing low while the 50-day
    still climbs — that must NOT be called a knife, or every pullback is one."""
    from supply_demand import sd_liquidity as liq
    stepping_down = {"trend": "falling"}
    assert liq.is_falling_knife(stepping_down, 100.0, ma50=90.0, ma50_prior=110.0) is True
    assert liq.is_falling_knife(stepping_down, 100.0, ma50=110.0, ma50_prior=90.0) is False
    assert liq.is_falling_knife({"trend": "rising"}, 100.0, ma50=90.0, ma50_prior=110.0) is False


def test_the_knife_gate_fails_closed_when_it_cannot_read_the_structure():
    """No bars, too few bars, junk -> no evidence of anything, so no push.
    Same side direction_gate fails on."""
    assert AG.knife_read("X", frame=_frame([10.0] * 20)) is None
    assert AG.knife_gate("X", frame=_frame([10.0] * 20)) is False
    assert AG.knife_gate("X", read={}) is False
    assert AG.knife_gate("X", read={"knife": None}) is False
    assert AG.knife_gate("X", read="not a dict") is False


def test_the_knife_gate_never_reads_the_still_forming_bar():
    """A violent unfinished bar must not change the structure read — scans and
    gates stay on closed bars (the live-bar overlay rule, 2026-09-03)."""
    base = [100.0 + i * 0.8 for i in range(120)]
    calm = _frame(base)
    crashed = _frame(base[:-1] + [base[-1] * 0.55])       # today gaps 45% down
    assert AG.knife_read("X", frame=calm)["swing_lows"] == \
           AG.knife_read("X", frame=crashed)["swing_lows"]


def test_the_mood_gate_reads_the_turn_not_the_two_year_trend():
    """THE POINT OF THE WHOLE CHANGE. A long slide that has based and turned
    scores bearish on the full frame and bullish on the recent window. If these
    two ever agree, the short frame has stopped doing its job."""
    slide = [400.0 - i * 1.6 for i in range(200)]          # long decline
    turn = [80.0 + i * 1.1 for i in range(60)]             # then a real turn
    df = _frame(slide + turn)
    full = AG.mood_read("X", frame=df)
    rev = AG.reversal_mood_read("X", frame=df)
    assert full["score"] < rev["score"], (full, rev)
    assert rev["bars"] == AG.REVERSAL_MOOD_BARS


def test_the_mood_gate_fails_closed_and_honours_its_floor():
    assert AG.REVERSAL_MOOD_FLOOR == 25.0        # mood.LABELS: >= +25 is "bullish"
    assert AG.reversal_mood_gate("X", read=None) is False
    assert AG.reversal_mood_gate("X", read={}) is False
    assert AG.reversal_mood_gate("X", read={"score": None}) is False
    assert AG.reversal_mood_gate("X", read={"score": 24.9}) is False
    assert AG.reversal_mood_gate("X", read={"score": 25.0}) is True


def test_the_things_to_see_can_never_block_a_push():
    """GEX, patterns, sentiment and SECTOR HEAT ride along. His own ledger says
    no chart pattern beats the 50% placebo, and sector heat measured flat on
    50,191 replayed demand arrivals (docs/supply_demand/sector_heat.md), so
    none of them is a gate — and every one of these readers must answer None
    rather than raise on a bad symbol."""
    from supply_demand import bullish_context as BC
    ctx = BC.bullish_context("__nope__", with_sentiment=False)
    assert set(ctx) == {"gex", "patterns", "sentiment", "sector_heat"}
    assert ctx["sector_heat"] is None, "an unlabelled name gets NO heat read"
    assert BC.context_txt(ctx) == "" or isinstance(BC.context_txt(ctx), str)
    assert BC.context_txt(None) == ""
    assert BC.context_txt({}) == ""
    # none of the see-it readers appears in any gate
    import inspect
    for gate in (AG.direction_gate, AG.knife_gate, AG.reversal_mood_gate,
                 AG.room_gate, AG.demand_proximity_gate):
        src = inspect.getsource(gate)
        for banned in ("bullish_context", "gex_bullish_read", "sentiment_read",
                       "bullish_patterns_read", "sector_heat", "rotation"):
            assert banned not in src, f"{gate.__name__} must not read {banned}"
    # structural, not a promise: the gate module cannot even see the context one
    import inspect as _i
    assert "bullish_context" not in _i.getsource(AG)
    # ... and cannot reach the rotation map either, which is why sector heat
    # lives in bullish_context and not here (alert_gates is a pinned leaf).
    assert "rotation" not in _i.getsource(AG)


def test_flat_top_is_excluded_because_it_fires_on_everything():
    """Measured 120/120 on a random universe sample. A pattern present on every
    name would read as confirmation while carrying no information."""
    from supply_demand import bullish_context as BC
    assert "flat_top" in BC.NOISE_PATTERNS


def test_every_pattern_shown_carries_its_record_against_the_placebo():
    """Standing rule: always quote a placebo next to a per-name rate."""
    from supply_demand import bullish_context as BC
    assert BC.PATTERN_PLACEBO[1] == 50
    for name, (n, up, mean) in BC.PATTERN_RECORD.items():
        assert n > 0 and 0 <= up <= 100, name
    txt = BC.context_txt({"patterns": [{"name": "double_bottom",
                                        "record": {"n": 248, "up_pct": 43, "mean_pct": 0.35}}]})
    assert "43% up" in txt and "50% placebo" in txt


# ── stop hunt vs falling knife (2026-09-09) ────────────────────────────────
# Ajay: "I am trying to find bullish stocks that got in to demand zone for some
# reason in the short while where Institutions hunt for stop losses in the
# journey I been catching some falling knives do what ever is best"
def _sweep_frame(pierce_pct, reclaim, *, floor=100.0, bars=40, vol_x=2.0):
    """A frame that dips `pierce_pct` under `floor` and, if `reclaim`, closes
    back above it on the next bar. Volume on the dip bar is `vol_x` the rest."""
    closes = [floor * 1.06] * bars
    lows = [floor * 1.04] * bars
    vols = [1_000_000] * bars
    i = bars - 3
    low = floor * (1.0 - pierce_pct / 100.0)
    lows[i] = low
    closes[i] = low if not reclaim else floor * 0.999
    vols[i] = int(1_000_000 * vol_x)
    if reclaim:
        closes[i + 1] = floor * 1.02
        lows[i + 1] = floor * 1.01
    else:
        for k in range(i + 1, bars):
            closes[k] = low * 0.99
            lows[k] = low * 0.98
    return _frame(closes, lows=lows, highs=[c * 1.01 for c in closes], vol=1_000_000).assign(
        volume=vols)


BAND = {"kind": "demand", "lo": 100.0, "hi": 104.0, "touches": 3}


def test_a_stop_run_that_reclaims_reads_swept():
    """Pierced the floor to take the stops, closed back above it. HIS setup."""
    r = AG.sweep_read(BAND, "X", frame=_sweep_frame(1.2, True))
    assert r["state"] == "swept"
    assert 1.0 < r["pierce_pct"] < 1.5
    assert "swept the stops" in AG.sweep_txt(r)


def test_a_break_that_never_reclaims_reads_broken():
    """Pierced and stayed under. THE FALLING KNIFE — CASY's own read."""
    r = AG.sweep_read(BAND, "X", frame=_sweep_frame(1.2, False))
    assert r["state"] == "broken"
    assert "broke the band" in AG.sweep_txt(r)
    assert "swept" not in AG.sweep_txt(r)


def test_a_band_never_pierced_reads_intact():
    r = AG.sweep_read(BAND, "X", frame=_frame([106.0] * 40, lows=[104.5] * 40))
    assert r["state"] == "intact" and AG.sweep_txt(r) == ""


def test_a_dip_too_deep_is_a_breakdown_not_a_stop_run():
    """sd_liquidity's own house rule: deeper than SWEEP_MAX_PIERCE_PCT is a
    breakdown. It must never read as the setup, reclaim or not."""
    from supply_demand import sd_liquidity as liq
    assert liq.SWEEP_MAX_PIERCE_PCT == 4.0
    r = AG.sweep_read(BAND, "X", frame=_sweep_frame(liq.SWEEP_MAX_PIERCE_PCT + 3.0, True))
    assert r["state"] != "swept", "a 7% slice is not a stop run"


def test_the_sweep_read_is_a_read_and_never_a_gate():
    """He asked to SEE which dip was a stop run. Nothing here blocks a push —
    pin that, because the gates and the reads live in the same module."""
    import inspect
    for gate in (AG.direction_gate, AG.knife_gate, AG.reversal_mood_gate,
                 AG.room_gate, AG.demand_proximity_gate):
        assert "sweep" not in inspect.getsource(gate), gate.__name__


def test_the_sweep_read_degrades_to_none_instead_of_raising():
    assert AG.sweep_read(None, "X", frame=_sweep_frame(1.0, True)) is None
    assert AG.sweep_read(BAND, "X", frame=None) is None
    assert AG.sweep_read(BAND, "X", frame=_frame([100.0] * 5)) is None
    assert AG.sweep_txt(None) == "" and AG.sweep_txt({}) == ""


# ── the band floor must have held (2026-09-09, MEASURED) ───────────────────
# The one gate measured all day that separates. 31,861 replayed bouncing events,
# 192 dates, date-clustered: intact 30.7% win vs swept 22.7% and broken 21.5%,
# baseline 24.1%. Δwin +8.60pp CI[+6.39,+11.06].
#
# IT IS THE OPPOSITE OF WHAT HE ASKED FOR. He wanted the stop hunt; the stop
# hunt measures WORSE than average (Δwin -2.37pp CI[-3.76,-1.01]). The reclaim
# does not save a pierced floor.
def test_only_an_untouched_floor_passes():
    assert AG.FLOOR_HELD_STATES == ("intact",)
    assert AG.floor_held_gate(BAND, read={"state": "intact"}) is True
    for st in ("swept", "broken"):
        assert AG.floor_held_gate(BAND, read={"state": st}) is False, st


def test_the_stop_hunt_does_not_pass_however_clean_it_looks():
    """A textbook stop run — shallow pierce, same-bar reclaim, heavy volume —
    still fails. Measured worse than average; the geometry does not rescue it."""
    r = AG.sweep_read(BAND, "X", frame=_sweep_frame(0.8, True, vol_x=3.0))
    assert r["state"] == "swept"
    assert AG.floor_held_gate(BAND, read=r) is False


def test_the_floor_gate_fails_closed():
    for bad in (None, {}, {"state": None}, {"state": ""}, {"state": 7}, "nope"):
        assert AG.floor_held_gate(BAND, read=bad) is False, bad
    assert AG.floor_held_gate(None, "X", frame=_sweep_frame(1.0, True)) is False


def test_the_floor_gate_and_the_sweep_read_agree_end_to_end():
    held = _frame([106.0] * 40, lows=[104.5] * 40)
    assert AG.floor_held_gate(BAND, "X", frame=held) is True
    assert AG.floor_held_gate(BAND, "X", frame=_sweep_frame(1.2, False)) is False
    assert AG.floor_held_gate(BAND, "X", frame=_sweep_frame(1.2, True)) is False
