"""Formulas-audit defects on the Gajjala detectors (2026-11-11), one step per commit.

Step A1 — K7 D9 (`_vcp_leg`): "waiting for cycle 2" is decided BEFORE the "B — imperfect" grade. A pending k4 (no break
yet, fewer than K4_VCP_MIN_CYCLES cycles) is not a miss, so a 1-cycle read whose low sits under the 21 EMA reads what
its 2-cycle self reads (partial · B) instead of invalid. Frames = the audit demo `demos/L2/k7_b_n1.py`."""
import json

import pytest

from chart_maps.gajjala import constants as GC, detectors as D, potential as PT, tab as T
from tests.fixtures.gajjala import detector_frames as FX

B_REASON = "B — imperfect · missed K7 contraction lows hold the 21 EMA"

# the reads at bars 13 and 14 as HEAD 192baf63 served them (before D9) — two cycles, so D9 must not move one byte
HEAD_READ_13 = '{"as_of_bar_t": "2026-10-13 10:40", "bars_since_entry": null, "base": {"bars": 10, "from_t": "2026-10-13 09:55", "to_t": "2026-10-13 10:40"}, "broke": false, "criteria": [{"key": "k4_cycles", "label": "K4 at least 2 contractions", "need": "2 or more", "ok": true, "value": "2 contractions"}, {"key": "k7_ratio", "label": "K7 each contraction tighter than the last", "need": "each at most 75% of the one before", "ok": true, "value": "high to low 1.25 → 0.875"}, {"key": "k7_ema21", "label": "K7 contraction lows hold the 21 EMA", "need": "every low no more than 0.5% under the 21 EMA", "ok": false, "value": "lows 9.75 · 9.88"}, {"key": "k3_vol", "label": "K3 volume dried up on the pullbacks", "need": "every bar must be ≤ 150,000: half the average bar of the run up", "ok": true, "value": "busiest bar 80,000"}], "cycles": 2, "entry_bar_t": null, "flag_k": null, "frame": "5m", "grade": "B", "leg": {"bars": 1, "e_t": "2026-10-13 09:50", "s_t": "2026-10-13 09:50"}, "meta": {"structure_alive": true}, "missed": ["k7_ema21"], "ready": false, "reason": "B — imperfect · missed K7 contraction lows hold the 21 EMA", "red_closes": 5, "risk_pct": 8.13953488372093, "setup": "intraday_vcp", "state": "partial", "stop": 9.875, "trigger": 10.75, "unjudged": [], "variant": null}'
HEAD_READ_14 = '{"as_of_bar_t": "2026-10-13 10:45", "bars_since_entry": 0, "base": {"bars": 10, "from_t": "2026-10-13 09:55", "to_t": "2026-10-13 10:40"}, "broke": true, "criteria": [{"key": "k4_cycles", "label": "K4 at least 2 contractions", "need": "2 or more", "ok": true, "value": "2 contractions"}, {"key": "k7_ratio", "label": "K7 each contraction tighter than the last", "need": "each at most 75% of the one before", "ok": true, "value": "high to low 1.25 → 0.875"}, {"key": "k7_ema21", "label": "K7 contraction lows hold the 21 EMA", "need": "every low no more than 0.5% under the 21 EMA", "ok": false, "value": "lows 9.75 · 9.88"}, {"key": "k3_vol", "label": "K3 volume dried up on the pullbacks", "need": "every bar must be ≤ 150,000: half the average bar of the run up", "ok": true, "value": "busiest bar 80,000"}], "cycles": 2, "entry_bar_t": "2026-10-13 10:45", "flag_k": null, "frame": "5m", "grade": "B", "leg": {"bars": 1, "e_t": "2026-10-13 09:50", "s_t": "2026-10-13 09:50"}, "meta": {"structure_alive": true}, "missed": ["k7_ema21"], "ready": false, "reason": "B — imperfect · missed K7 contraction lows hold the 21 EMA", "red_closes": 5, "risk_pct": 8.13953488372093, "setup": "intraday_vcp", "state": "partial", "stop": 9.875, "trigger": 10.75, "unjudged": [], "variant": null}'


def _demo():
    """The fixture VCP with cycle-1's low 9.75 (bar 8) 2.5% under a 10.0 21 EMA (audit demo k7_b_n1.py)."""
    return FX.vcp_frame(e21_at={8: 10.0})


def _read(F, k):
    return D.intraday_vcp(F, last=FX.today_index(F, k))


def _broken_one_cycle():
    """One cycle (H1 bar 5, low bar 8 under the 21 EMA), then bar 11 takes H1 = 11.0 before any 2nd cycle. The break
    bar is not itself a K1 bar (+1.7% body), so the structure stays the one leg."""
    bars = list(FX.VCP_BARS[:11]) + [(10.875, 11.125, 10.8125, 11.0625, 150_000), (11.0625, 11.2, 11.0, 11.1, 90_000)]
    return FX.vcp_frame(bars, entry=None, e21_at={8: 10.0})


# ── A1 · K7 D9 ────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("k", [8, 9, 10, 11, 12])
def test_d9_one_cycle_waiting_read_is_b_not_invalid(k):
    r = _read(_demo(), k)
    assert r["cycles"] == 1
    assert r["state"] == "partial" and r["grade"] == GC.VCP_B_GRADE == "B"
    assert r["meta"]["structure_alive"] is True
    assert r["reason"] == B_REASON
    assert r["missed"] == ["k7_ema21"]                         # the pending k4 is waiting, never listed as missed
    assert (r["trigger"], r["stop"]) == (11.0, 9.75)


@pytest.mark.parametrize("k,pin", [(13, HEAD_READ_13), (14, HEAD_READ_14)])
def test_d9_two_cycle_reads_byte_equal_to_head(k, pin):
    assert json.dumps(_read(_demo(), k), sort_keys=True, ensure_ascii=False) == pin


def test_d9_prefix_property_now_holds_across_the_cycle_count():
    """The audit's broken prefix property: bars 10-12 read invalid, bars 13-14 read B on the same bars. Now one
    reading from the first B to the break."""
    F = _demo()
    seen = [(_read(F, k)["state"], _read(F, k)["grade"]) for k in range(8, 15)]
    assert seen == [("partial", "B")] * 7


def test_d9_no_look_ahead_on_the_demo_frame():
    F = _demo()
    for k in range(F.today.start, len(F.c)):
        assert D.intraday_vcp(F, last=k) == D.intraday_vcp(FX.prefix(F, k)), k


def test_d9_control_low_holding_the_21_ema_still_forming_waiting():
    r = _read(FX.vcp_frame(), 10)
    assert (r["state"], r["cycles"], r["reason"], r["missed"], r["grade"]) == (
        "forming", 1, f"1 of {GC.K4_VCP_MIN_CYCLES} contractions", [], None)


# NEGATIVES ───────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("k", [11, 12])
def test_d9_negative_broken_one_cycle_under_the_21_ema_stays_invalid(k):
    F = _broken_one_cycle()
    r = _read(F, k)
    assert r["cycles"] == 1
    assert r["state"] == "invalid" and r["grade"] is None
    assert r["reason"] == "contraction low under the 21 EMA"
    assert r["meta"]["structure_alive"] is False


@pytest.mark.parametrize("k", [8, 10, 12])
def test_d9_negative_one_cycle_read_is_never_a_potential_nor_listed(k):
    r = _read(_demo(), k)
    assert PT.potential_kind(r) is None
    assert GC.vcp_list_min_cycles() == GC.K4_VCP_MIN_CYCLES == 2
    assert T._vcp_listed("intraday_vcp", r) is False
    # even stripped of the B grade and read as the potential state, one cycle is never a potential (BUILD_SPEC18 D4)
    assert PT.potential_kind({**r, "state": GC.POTENTIAL_STATE, "grade": None}) is None


def test_d9_negative_b_reads_off_one_cycle_under_the_21_ema_stays_invalid(monkeypatch):
    monkeypatch.setattr(GC, "VCP_B_READS", False)
    r = _read(_demo(), 10)
    assert (r["state"], r["reason"], r["grade"]) == ("invalid", "contraction low under the 21 EMA", None)


def test_d9_negative_only_the_pending_k4_is_excused_k3_volume_miss_stays_invalid():
    """A loud pullback bar (k3_vol False) on the waiting 1-cycle read: two rules missed besides k4 → not B."""
    bars = FX.vcp_replace(r7=(10.4375, 10.5, 10.0, 10.0625, 400_000))
    F = FX.vcp_frame(bars, e21_at={8: 10.0})
    for k in (10, 11):
        r = _read(F, k)
        assert (r["state"], r["reason"], r["grade"]) == ("invalid", "contraction low under the 21 EMA", None), k
