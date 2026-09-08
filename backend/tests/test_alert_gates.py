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
