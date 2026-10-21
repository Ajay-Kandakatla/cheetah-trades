"""Gajjala detectors (chart_maps/gajjala/detectors.py) — every criterion positive + NEGATIVE, his own invalid examples
as synthetic shapes, the no-look-ahead prefix property, the H1–H5 option sweep and a monkeypatch-each-constant sweep.

Pure functions only: no Mongo, no network, no clock. Fixtures: tests/fixtures/gajjala/detector_frames.py.
"""
from __future__ import annotations

import ast
import copy
import pathlib

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from tests.fixtures.gajjala import detector_frames as FX

SRC = pathlib.Path(D.__file__)
TI = FX.today_index


def _key(r: dict) -> tuple:
    return (r["state"], r["trigger"], r["stop"], tuple(r["missed"]), tuple(r["unjudged"]), r["variant"],
            r["grade"], r["reason"], r["entry_bar_t"], r["broke"], r["ready"], r["red_closes"])


# ── shared helpers ──────────────────────────────────────────────────────────────────────────────────────────────
def _k1_frame(c_mult=None, high=10.375):
    o = 10.0
    c = o * (1 + GC.K1_BODY_GAIN_PCT / 100) if c_mult is None else o * c_mult
    return FX.frame([(o, high, 10.0, c, 200_000)])


def test_k1_body_edge_is_demand():
    F = _k1_frame()
    assert D.avg_rng(F, TI(F, 0)) == 0.25
    assert D.rng(F, TI(F, 0)) == 0.375 == GC.K1_RANGE_MULT * 0.25
    assert D.is_demand(F, TI(F, 0)) is True


def test_k1_body_just_under_edge_is_not_demand():
    assert D.is_demand(_k1_frame(c_mult=1.0299), TI(_k1_frame(), 0)) is False


def test_k1_range_just_under_1_5x_is_not_demand():
    F = _k1_frame(high=10.37)
    assert D.is_demand(F, TI(F, 0)) is False


def test_k1_first_20_frame_bars_are_never_demand():
    big = (10.0, 12.0, 10.0, 12.0, 500_000)
    F = FX.frame([FX.quiet(10.0)] * 5 + [big] + [FX.quiet(12.0)] * 3, prior=[])
    assert not any(D.is_demand(F, i) for i in range(len(F.c)))
    assert D.find_legs(F, 1) == []


def test_yesterdays_after_hours_leg_is_ignored():
    prior = FX.warm() + [FX.D1, FX.D2]
    F = FX.frame([FX.quiet(11.0)] * 4, prior=prior)
    assert D.is_demand(F, len(prior) - 1) is True                  # it IS a demand leg …
    assert D.find_legs(F, GC.BF_LEG_MIN_BARS) == []                 # … but not today's
    assert D.bull_flag(F)["state"] == "none"


def _k2(vols):
    F = FX.frame([(10.0, 10.5, 10.0, 10.5, v) for v in vols])
    return D.k2_ok(F, TI(F, 0), TI(F, len(vols) - 1))


def test_k2_equal_volumes_pass():
    assert _k2([200_000, 200_000]) is True


def test_k2_falling_volume_fails():
    assert _k2([200_000, 199_999]) is False


def test_k2_step_over_5x_fails():
    assert _k2([100_000, 100_000 * GC.K2_MAX_VOL_STEP]) is True
    assert _k2([100_000, 501_000]) is False


def test_k2_one_bar_leg_is_vacuous():
    assert _k2([200_000]) is True


def test_tri_state_comparisons_return_none_on_none():
    assert D.gt(None, 1) is None and D.ge(1, None) is None and D.le(None, None) is None
    assert D._and(True, None) is None and D._and(False, None) is False
    assert D._or(False, None) is None and D._or(True, None) is True


# entry_event / stopped_after — on the Bull Flag A+ frame (trigger 10.96875, stop 10.8125)
def _bf_with_minutes(mins):
    return FX.frame(FX.bf_bars(), minutes={7: mins})


def test_break_then_stop_later_in_the_entry_bar_reads_stopped_not_aplus():
    r = D.bull_flag(_bf_with_minutes([(10.875, 10.9, 10.85, 10.88, 1), (10.88, 11.0, 10.86, 10.99, 1),
                                      (10.99, 11.0, 10.8, 10.85, 1)]))
    assert r["state"] == "stopped" and r["broke"] is True


def test_stop_then_break_inside_the_entry_bar_is_invalid():
    r = D.bull_flag(_bf_with_minutes([(10.875, 10.9, 10.8, 10.85, 1), (10.85, 11.25, 10.85, 11.2, 1)]))
    assert r["state"] == "invalid" and "stopped before the break" in r["reason"]


def test_break_and_stop_in_the_same_minute_is_ambiguous_never_aplus():
    r = D.bull_flag(_bf_with_minutes([(10.875, 11.25, 10.75, 11.2, 1)]))
    assert r["state"] == "partial" and r["broke"] is True and "entry" in r["missed"]


def test_entry_event_without_minutes_uses_the_whole_bar():
    F = FX.bf_aplus()
    j = TI(F, 7)
    assert D.entry_event(F, j, 10.96875, 10.8125, []) == ("break", None)
    assert D.entry_event(F, j, 10.96875, 10.9, []) == ("ambiguous", None)


def test_first_print_name_12_bars_never_raises_and_reads_none():
    bars = [(4.0, 4.5, 4.0, 4.5, 900_000)] + [FX.quiet(4.5)] * 11
    F = FX.frame(bars, prior=[])
    assert all(x is None for x in F.ema9[:GC.EMA_FAST - 1])
    out = D.read_all({"5m": F, "15m": None}, {"symbol": "NEWB", "float_read": FX.float_read(3_000_000)})
    assert set(out) == set(GC.SETUPS)
    assert all(r["state"] == "none" for r in out.values())
    assert all(r["reason"] != "detector error" for r in out.values())


def test_ema_warming_up_is_not_judgeable_never_aplus():
    F = FX.kf_frame()
    F.ema9 = [None] * len(F.ema9)
    F.ema21 = [None] * len(F.ema21)
    r = D.kiss_fly(F)
    assert r["state"] != "aplus"
    assert {"k5_uptrend", "k5a_honor"} <= set(r["unjudged"])
    G = FX.prefix(F, len(F.c) - 2)                                   # the kiss bar is the latest bar
    rg = D.kiss_fly(G)
    assert rg["state"] == "forming" and rg["ready"] is False
    assert rg["reason"] == "9 EMA warming up — not judgeable yet"


def test_first_print_ema21_warm_up_from_the_real_mask():
    F = FX.frame([FX.quiet(10.0)] * 20 + [FX.KF_D, (10.5, 10.5, 10.4375, 10.46875, 100_000),
                                          (10.46875, 10.6, 10.46875, 10.55, 200_000)], prior=[])
    assert F.ema21[19] is None and F.ema21[20] is not None
    r = D.kiss_fly(F)
    assert r["state"] != "aplus"


def test_reads_are_deterministic():
    for fn, F in ((D.bull_flag, FX.bf_aplus()), (D.kiss_fly, FX.kf_frame()), (D.fade_on, FX.hf_frame()),
                  (D.intraday_vcp, FX.vcp_frame())):
        assert fn(F) == fn(copy.deepcopy(F))


def _all_fixtures():
    return [("bull_flag", D.bull_flag, FX.frame(FX.bf_bars(after=[(11.2, 11.3, 11.1, 11.25, 100_000)] * 3))),
            ("kiss_fly", D.kiss_fly, FX.kf_frame()),
            ("fade", D.fade_on, FX.hf_frame(after=[(11.0625, 11.2, 11.0, 11.1, 90_000)] * 3)),
            ("vcp", D.intraday_vcp, FX.vcp_frame(after=[(10.8, 11.1, 10.7, 11.0, 90_000), (11.0, 11.05, 10.6, 10.7,
                                                                                         90_000)] * 2)),
            ("squeeze", lambda F, last=None: D.reversal_squeeze(F, float_read=FX.float_read(5_000_000), last=last),
             FX.rs_frame(after=[(6.4, 6.6, 6.3, 6.5, 300_000)] * 3))]


@pytest.mark.parametrize("name,fn,F", _all_fixtures(), ids=[x[0] for x in _all_fixtures()])
def test_no_look_ahead_over_every_prefix(name, fn, F):
    """The read at an earlier as_of never depends on a later bar: reading the FULL frame with `last=k` equals reading
    the frame truncated at k, for every k — later bars, their EMAs and their minutes are invisible."""
    for k in range(F.today.start, len(F.c)):
        cut = fn(FX.prefix(F, k))
        assert fn(F, last=k) == cut, (name, k)
        assert cut["as_of_bar_t"] == F.t[k]


def test_trigger_and_stop_never_move_after_an_aplus():
    F = FX.frame(FX.bf_bars(after=[(11.2, 11.3, 11.1, 11.25, 100_000)] * 4))
    j = TI(F, 7)
    first = D.bull_flag(FX.prefix(F, j))
    assert first["state"] == "aplus"
    for k in range(j + 1, len(F.c)):
        r = D.bull_flag(FX.prefix(F, k))
        assert (r["state"], r["trigger"], r["stop"], r["entry_bar_t"]) == ("triggered", first["trigger"],
                                                                         first["stop"], first["entry_bar_t"])


def test_read_all_never_raises_on_a_detector_error(monkeypatch):
    def boom(*a, **k):
        raise ValueError("synthetic")
    monkeypatch.setattr(D, "bull_flag", boom)
    out = D.read_all({"5m": FX.bf_aplus()}, {"symbol": "ZZZ"})
    assert out["bull_flag"]["state"] == "none" and out["bull_flag"]["reason"] == "detector error"
    assert out["kiss_fly"]["reason"] != "detector error"


def test_read_all_shape():
    out = D.read_all({"5m": FX.bf_aplus(), "15m": None}, {"symbol": "AAA", "float_read": None})
    assert list(out) == list(GC.SETUPS)
    keys = {"setup", "state", "frame", "ready", "broke", "leg", "base", "trigger", "stop", "risk_pct", "entry_bar_t",
            "bars_since_entry", "criteria", "missed", "unjudged", "reason", "as_of_bar_t", "meta", "grade", "variant",
            "red_closes", "flag_k"}
    for r in out.values():
        assert keys <= set(r) and r["state"] in D.STATES
    assert out["bull_flag"]["state"] == "aplus"


# ── placeholders (H1–H5) ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("h", sorted(GC.PLACEHOLDERS))
def test_an_unanswered_placeholder_reads_awaiting(monkeypatch, h):
    for name in GC.PLACEHOLDERS[h]:
        monkeypatch.setattr(GC, name, None)
    frames = {"5m": FX.vcp_frame(), "15m": FX.hf_frame()}
    out = D.read_all(frames, {"symbol": "AAA", "float_read": FX.float_read(5_000_000)})
    held = {s for s, hs in GC.PLACEHOLDER_BY_SETUP.items() if h in hs}
    assert held
    for s in GC.SETUPS:
        if s in held:
            assert out[s]["state"] == "none" and out[s]["reason"] == f"awaiting Ajay's answer ({h})"
        else:
            assert "awaiting" not in out[s]["reason"]


def test_an_out_of_list_event_rule_reads_awaiting(monkeypatch):
    monkeypatch.setattr(GC, "K8_FAIL_EVENT_RULE", "maybe")
    out = D.read_all({"5m": FX.rs_frame()}, {"float_read": FX.float_read(5_000_000)})
    assert out["reversal_squeeze"]["reason"] == "awaiting Ajay's answer (H2)"


H_SWEEP = [
    # (constants, value, setup, expected state) — the pinned reads in docs/gajjala/detectors_2026_10_13.md
    (("K8_FAIL_NEAR_PCT", "K8_FAIL_DROP_PCT"), (2.0, 8.0), "rs", "aplus"),       # H1-A (Ajay's answer)
    (("K8_FAIL_NEAR_PCT", "K8_FAIL_DROP_PCT"), (2.0, 4.0), "rs", "aplus"),       # H1-B
    (("K8_FAIL_EVENT_RULE",), ("distinct",), "rs", "aplus"),                      # H2-A (Ajay's answer)
    (("K8_FAIL_EVENT_RULE",), ("same_ok",), "rs", "aplus"),                       # H2-B
    (("K8_FAIL_EVENT_RULE",), ("distinct",), "rs_s8", "partial"),                 # S8 36:12 shape under "distinct"
    (("K8_FAIL_EVENT_RULE",), ("same_ok",), "rs_s8", "aplus"),                    # … and under "same_ok"
    (("HF_LEG_MIN_BARS",), (1,), "hf", "aplus"),
    (("HF_LEG_MIN_BARS",), (2,), "hf", "aplus"),                                  # Ajay's answer
    (("HF_LEG_MIN_BARS",), (3,), "hf", "none"),
    (("VCP_LEG_MIN_BARS",), (1,), "vcp", "aplus"),                                # Ajay's answer
    (("VCP_LEG_MIN_BARS",), (2,), "vcp", "none"),
    (("VCP_LEG_MIN_BARS",), (3,), "vcp", "none"),
    (("RS_BASE_MIN_BARS",), (1,), "rs", "aplus"),                                 # Ajay's answer
    (("RS_BASE_MIN_BARS",), (2,), "rs", "aplus"),
    (("RS_BASE_MIN_BARS",), (3,), "rs", "forming"),                               # the 2-bar base is too short: the top moves
    (("VCP_PIVOT_WINDOW",), (1,), "vcp", "aplus"),
    (("VCP_PIVOT_WINDOW",), (2,), "vcp", "aplus"),                                # Ajay's answer
    (("VCP_PIVOT_WINDOW",), (3,), "vcp", "forming"),                              # cycle-2 high unconfirmed → 1 cycle
]


def _h_read(kind):
    fr = FX.float_read(5_000_000)
    if kind == "rs":
        return D.reversal_squeeze(FX.rs_frame(), float_read=fr)
    if kind == "rs_s8":
        return D.reversal_squeeze(FX.rs_frame(FX.RS_S8_BARS, entry=FX.RS_S8_E), float_read=fr)
    if kind == "hf":
        return D.fade_on(FX.hf_frame())
    return D.intraday_vcp(FX.vcp_frame())


@pytest.mark.parametrize("names,values,kind,state", H_SWEEP, ids=[f"{n[0]}={v[-1]}:{k}" for n, v, k, _ in H_SWEEP])
def test_each_placeholder_option_reads_as_documented(monkeypatch, names, values, kind, state):
    for n, v in zip(names, values):
        monkeypatch.setattr(GC, n, v)
    assert _h_read(kind)["state"] == state


# ── 🚩 Bull Flag ──────────────────────────────────────────────────────────────────────────────────────────────
def test_bf_aplus_trigger_and_stop_are_the_pullback_bar():
    r = D.bull_flag(FX.bf_aplus())
    assert r["state"] == "aplus" and r["frame"] == "5m"
    assert (r["trigger"], r["stop"]) == (FX.P2[1], FX.P2[2])
    assert r["leg"]["bars"] == 2 and r["base"]["bars"] == 2 and r["flag_k"] == 1
    assert r["risk_pct"] == pytest.approx((FX.P2[1] - FX.P2[2]) / FX.P2[1] * 100)
    assert [c["key"] for c in r["criteria"]] == ["k2", "k3_vol", "k4"]


def test_bf_one_bar_leg_is_none():
    r = D.bull_flag(FX.frame(FX.bf_bars(leg=(FX.quiet(10.0), FX.D2))))
    assert r["state"] == "none"


def test_nvct_one_big_candle_then_a_deep_pullback_is_none():
    big = (10.0, 11.5, 10.0, 11.5, 900_000)
    r = D.bull_flag(FX.frame([FX.quiet(10.0)] * 3 + [big, (11.5, 11.5, 10.5, 10.6, 400_000),
                                                    (10.6, 10.9, 10.4, 10.8, 300_000)]))
    assert r["state"] == "none"


@pytest.mark.parametrize("n", [1, 2, 3])
def test_bf_1_to_3_bars_unchanged(n):
    """1–3 pullback bars with the break = A+, as before 2026-10-18 (NEGATIVE of the change: nothing below 4 moved)."""
    r = D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(n))))
    assert r["state"] == "aplus" and r["variant"] is None and r["entry_bar_t"] is not None and "k4" not in r["missed"]


@pytest.mark.parametrize("n", [4, 5])
def test_bf_4_or_5_bars_is_aplus_since_2026_10_18(n):
    """Ajay 2026-10-18 "make the change for Long flags" (DECISIONS13 D1): 4–5 bar flags with the break are A+ —
    entry set, k4 met, no long_flag variant (the band is empty while K4_BF_LONG_FLAG_MAX is None)."""
    # WIDENED 2026-10-18 (DECISIONS13 D1): was partial / variant long_flag / k4 missed (Ajay K4a 2026-10-13)
    assert (GC.K4_BF_PULL_MAX, GC.K4_BF_LONG_FLAG_MAX) == (5, None)
    r = D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(n))))
    assert r["state"] == "aplus" and r["broke"] is True and r["entry_bar_t"] is not None
    assert r["trigger"] is not None and r["stop"] is not None
    assert "k4" not in r["missed"] and r["variant"] is None
    assert next(c for c in r["criteria"] if c["key"] == "k4")["ok"] is True


def test_bf_4_bar_flag_without_the_break_is_forming():
    """WIDENED 2026-10-18 (DECISIONS13 D1): a 4-bar flag still waiting for the break is a FORMING read (was a listed
    partial long flag)."""
    r = D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(4), entry=None)))
    assert r["state"] == "forming" and r["variant"] is None and r["missed"] == []


def test_bf_6_bars_is_invalid():
    """NEGATIVE: more than K4_BF_PULL_MAX (5) bars = invalid, and the reason names 5 bars."""
    r = D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(6))))
    assert r["state"] == "invalid" and "longer than 5 bars" in r["reason"] and r["variant"] is None
    r = D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(6), entry=None)))
    assert r["state"] == "invalid" and "longer than 5 bars" in r["reason"]


def test_NEGATIVE_the_dormant_long_flag_band_still_reads_when_configured(monkeypatch):
    """The long-flag code path stays (config-driven): put the 2026-10-13 numbers back (PULL_MAX 3, LONG_FLAG_MAX 5)
    and a 4-bar flag is a listed partial long flag again, never A+; 6 bars stay invalid."""
    monkeypatch.setattr(GC, "K4_BF_PULL_MAX", 3)
    monkeypatch.setattr(GC, "K4_BF_LONG_FLAG_MAX", 5)
    for n in (4, 5):
        r = D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(n))))
        assert r["state"] == "partial" and r["broke"] is True and r["variant"] == "long_flag" and "k4" in r["missed"]
    r = D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(4), entry=None)))
    assert r["state"] == "partial" and r["variant"] == "long_flag"
    assert D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(3))))["state"] == "aplus"
    assert D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(6))))["state"] == "invalid"


def test_zyne_5_bar_flag_reads_per_setting(monkeypatch):
    """WIDENED 2026-10-18 (DECISIONS13 D1): the shipped setting reads ZYNE's 5-bar flag A+; the 1–3-only setting
    (LONG_FLAG_MAX None, PULL_MAX 3) reads it invalid."""
    F = FX.frame(FX.bf_bars(FX.flat_pull(5)))
    assert D.bull_flag(F)["state"] == "aplus" and D.bull_flag(F)["variant"] is None
    monkeypatch.setattr(GC, "K4_BF_PULL_MAX", 3)
    assert D.bull_flag(F)["state"] == "invalid"
    assert D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(6))))["state"] == "invalid"


def test_bf_pullback_low_under_the_midpoint_is_invalid():
    deep = (11.0, 11.0, 10.71875, 10.9375, 100_000)                # floor 10.75
    r = D.bull_flag(FX.frame(FX.bf_bars([deep, FX.P2])))
    assert r["state"] == "invalid" and "half the last demand bar" in r["reason"]


@pytest.mark.parametrize("first_bar", [False, True])
def test_rkda_two_sudden_bars_and_a_deep_first_pullback_is_invalid(monkeypatch, first_bar):
    monkeypatch.setattr(GC, "K2_CHECK_FIRST_BAR", first_bar)
    leg = ((10.0, 11.0, 10.0, 11.0, 2_000_000), (11.0, 12.0, 11.0, 12.0, 3_000_000))
    r = D.bull_flag(FX.frame(FX.bf_bars([(12.0, 12.0, 11.25, 11.4, 400_000)], leg=leg)))
    assert r["state"] == "invalid"


def test_bf_pullback_volume_051x_is_partial_broke():
    cap = GC.K3_VOL_FRAC * (FX.D1[4] + FX.D2[4]) / 2
    loud = FX.P1[:4] + (cap * 1.02,)
    r = D.bull_flag(FX.frame(FX.bf_bars([loud, FX.P2])))
    assert r["state"] == "partial" and r["broke"] is True and r["missed"] == ["k3_vol"]
    assert r["reason"] == "broke — not A+"


def test_bf_entry_not_latest_is_triggered():
    r = D.bull_flag(FX.frame(FX.bf_bars(after=[(11.2, 11.3, 11.1, 11.25, 100_000)])))
    assert r["state"] == "triggered" and r["bars_since_entry"] == 1


def test_bf_stopped_after_the_break():
    r = D.bull_flag(FX.frame(FX.bf_bars(after=[(11.2, 11.2, 10.75, 10.8, 100_000)])))
    assert r["state"] == "stopped"


def test_bf_forming_trigger_is_the_latest_bar():
    r = D.bull_flag(FX.frame(FX.bf_bars(entry=None)))
    assert r["state"] == "forming" and r["ready"] is True and (r["trigger"], r["stop"]) == (FX.P2[1], FX.P2[2])


def test_bf_forming_without_a_pullback_waits():
    r = D.bull_flag(FX.frame(FX.bf_bars([], entry=None)))
    assert r["state"] == "forming" and r["ready"] is False and r["reason"] == "waiting for the pullback bar"


def test_ocx_first_up_bar_10x_the_candle_before(monkeypatch):
    leg = (FX.D1[:4] + (1_000_000,), FX.D2[:4] + (1_200_000,))
    P = [FX.P1[:4] + (400_000,), FX.P2[:4] + (300_000,)]
    F = FX.frame(FX.bf_bars(P, leg=leg, entry=FX.BF_E))
    assert D.bull_flag(F)["state"] == "aplus"                    # Ajay round C: the step check stays within the leg
    monkeypatch.setattr(GC, "K2_CHECK_FIRST_BAR", True)
    r = D.bull_flag(F)
    assert r["state"] == "partial" and r["missed"] == ["k2"]


def test_bf_second_flag_of_the_session_is_flag_2():
    first = FX.bf_bars(after=[(11.2, 11.3, 11.1, 11.25, 100_000)] * 2)
    leg2 = ((11.25, 11.75, 11.25, 11.75, 300_000), (11.75, 12.25, 11.75, 12.25, 400_000))
    second = list(leg2) + [(12.25, 12.25, 12.125, 12.1875, 100_000), (12.1875, 12.5, 12.1875, 12.45, 300_000)]
    r = D.bull_flag(FX.frame(first + second))
    assert r["state"] == "aplus" and r["flag_k"] == 2


def test_bf_red_closes_chip_only_by_default(monkeypatch):
    reds = [(h, h, h - 0.0625, h - 0.03125, 80_000) for h in (11.0, 10.984375, 10.96875)]
    F = FX.frame(FX.bf_bars(reds))
    r = D.bull_flag(F)
    assert r["red_closes"] == 3 and r["state"] == "aplus"
    monkeypatch.setattr(GC, "RED_CLOSES_MODE", "criterion")
    assert D.bull_flag(F)["state"] == "aplus"                      # 3 is fine — "MORE than 3" is his flag


# ── 💋 EMA Kiss & Fly ─────────────────────────────────────────────────────────────────────────────────────────
def test_kf_aplus_entry_is_the_kiss_bar_high():
    F = FX.kf_frame()
    r = D.kiss_fly(F)
    kiss_bar = F.today.start + 4 + 3
    assert r["state"] == "aplus" and (r["trigger"], r["stop"]) == (F.h[kiss_bar], F.l[kiss_bar])
    assert {c["key"] for c in r["criteria"]} == {"k2", "k3_vol", "k5_uptrend", "k4", "k5a_honor", "k5_kiss"}


def test_kf_low_06pct_above_the_ema9_is_forming_not_ready():
    F = FX.kf_frame(kiss_above_pct=0.6, entry=False)
    r = D.kiss_fly(F)
    assert r["state"] == "forming" and r["ready"] is False
    assert r["reason"] == "0.6% above the 9 EMA — waiting for the kiss"


def test_kf_kiss_on_the_latest_bar_is_forming_ready():
    r = D.kiss_fly(FX.kf_frame(entry=False))
    assert r["state"] == "forming" and r["ready"] is True


def test_kf_a_pullback_close_under_ema9_invalidates_k5a():
    """Ajay K5a (round A) REVERSES BUILD_SPEC HIS CALL 5: a pullback bar closing under the 9 EMA did not honor it."""
    r = D.kiss_fly(FX.kf_frame(honor_fail_at=1))
    assert r["state"] == "invalid" and "did not honor" in r["reason"]


def test_kf_honor_rule_off_restores_the_build_read(monkeypatch):
    monkeypatch.setattr(GC, "KF_HONOR_ALL_PULLBACK_CLOSES", False)
    r = D.kiss_fly(FX.kf_frame(honor_fail_at=1))
    assert r["state"] == "aplus" and "k5a_honor" not in {c["key"] for c in r["criteria"]}


def test_hkd_9_bar_pullback_is_aplus():
    assert D.kiss_fly(FX.kf_frame(9))["state"] == "aplus"


def test_kf_10_bar_pullback_is_invalid():
    r = D.kiss_fly(FX.kf_frame(10))
    assert r["state"] == "invalid" and "longer than 9" in r["reason"]


def test_hkd_9_bars_invalid_at_the_old_8(monkeypatch):
    monkeypatch.setattr(GC, "K4_KF_PULL_MAX", 8)
    assert D.kiss_fly(FX.kf_frame(9))["state"] == "invalid"


def test_kf_ema9_under_ema21_is_partial():
    r = D.kiss_fly(FX.kf_frame(e21_over=0.0078125))
    assert r["state"] == "partial" and "k5_uptrend" in r["missed"]


def test_kf_ema21_not_above_3_bars_back_is_partial():
    r = D.kiss_fly(FX.kf_frame(e21_rise=0.0))
    assert r["state"] == "partial" and "k5_uptrend" in r["missed"]


def test_kf_pullback_volume_too_high_is_partial():
    r = D.kiss_fly(FX.kf_frame(pull_v=GC.K3_VOL_FRAC * FX.KF_D[4] * 1.02))
    assert r["state"] == "partial" and r["missed"] == ["k3_vol"]


def test_nexi_near_kiss_is_listed_never_aplus():
    r = D.kiss_fly(FX.kf_near_kiss())
    assert r["state"] == "partial" and r["variant"] == GC.KF_NO_TOUCH_VARIANT == "near_kiss"
    assert r["broke"] is True and "k5_kiss" in r["missed"]


def test_near_kiss_off_reads_without_the_variant(monkeypatch):
    monkeypatch.setattr(GC, "KF_ALLOW_NO_TOUCH", False)
    r = D.kiss_fly(FX.kf_near_kiss())
    assert r["variant"] is None and r["state"] != "aplus"


def test_a_touch_that_closes_on_the_ema_is_not_a_near_kiss():
    r = D.kiss_fly(FX.kf_near_kiss(allow_touch_close_eq=True))
    assert r["variant"] is None and r["state"] != "aplus"


def test_kf_red_closes_counted_and_criterion_mode(monkeypatch):
    F4 = FX.kf_frame(5, red=4)
    assert D.kiss_fly(F4)["red_closes"] == 4 and D.kiss_fly(F4)["state"] == "aplus"
    monkeypatch.setattr(GC, "RED_CLOSES_MODE", "criterion")
    r = D.kiss_fly(F4)
    assert r["state"] == "partial" and "red_closes" in r["missed"]
    assert D.kiss_fly(FX.kf_frame(5, red=3))["state"] == "aplus"


def test_red_close_definition_switch_on_a_doji_sequence(monkeypatch):
    F = FX.kf_frame(5, doji=4)
    P = range(F.today.start + 5, F.today.start + 10)
    assert D.red_closes(F, P) == 0                                    # close == open is not red (close < open)
    monkeypatch.setattr(GC, "RED_CLOSE_DEF", "close_below_prior_close")
    assert D.red_closes(F, P) >= 3


# ── ➖ Horizontal Fade ─────────────────────────────────────────────────────────────────────────────────────────
def test_hf_aplus_on_15m_trigger_is_the_base_high():
    r = D.fade_on(FX.hf_frame())
    assert r["state"] == "aplus" and r["frame"] == "15m"
    assert r["trigger"] == max(b[1] for b in FX.HF_BASE) and r["stop"] == FX.HF_BASE[-1][2]


def test_hf_prior_bar_trigger_mode(monkeypatch):
    monkeypatch.setattr(GC, "HF_TRIGGER", "prior_bar")
    assert D.fade_on(FX.hf_frame())["trigger"] == FX.HF_BASE[-1][1]


def test_hf_last_bar_under_the_base_high_prior_bar_triggers_base_high_stays_forming(monkeypatch):
    e = (10.84375, 10.90625, 10.8125, 10.875, 50_000)              # above the last base bar, under the base high
    F = FX.hf_frame(entry=e)
    r = D.fade_on(F)
    assert r["state"] == "forming" and r["ready"] is True and r["trigger"] == max(b[1] for b in FX.HF_BASE)
    monkeypatch.setattr(GC, "HF_TRIGGER", "prior_bar")
    r2 = D.fade_on(F)
    assert r2["state"] == "aplus" and r2["trigger"] == FX.HF_BASE[-1][1]


def test_hf_base_5_is_forming_not_ready():
    r = D.fade_on(FX.hf_frame(FX.HF_BASE[:5], entry=None))
    assert r["state"] == "forming" and r["ready"] is False and r["reason"] == "base 5 of 6 bars"


def test_bwv_impatient_break_before_6_base_bars_is_never_aplus():
    early = (10.875, 11.25, 10.875, 11.2, 250_000)
    r = D.fade_on(FX.hf_frame(FX.HF_BASE[:3], entry=early))
    assert r["state"] == "forming" and r["ready"] is False


def test_hf_base_25_is_invalid():
    base = [(10.875, 10.9375, 10.8125, 10.875, 40_000)] * 25
    r = D.fade_on(FX.hf_frame(base, entry=None))
    assert r["state"] == "invalid" and "longer than 24" in r["reason"]


def test_hf_emas_051pct_apart_is_partial():
    r = D.fade_on(FX.hf_frame(gap_frac=0.0051))
    assert r["state"] == "partial" and "k6_merge" in r["missed"]


def test_hf_base_801pct_wide_is_invalid():
    base = list(FX.HF_BASE)
    base[1] = base[1][:2] + (10.9375 - FX.HF_BASE[-1][3] * 0.0801,) + base[1][3:]
    r = D.fade_on(FX.hf_frame(base, entry=None))
    assert r["state"] == "invalid" and "wider than 8%" in r["reason"]


def test_hf_second_half_volume_070x_is_partial():
    v = GC.K6_SELL_DECAY * 100_000
    base = FX.HF_BASE[:3] + [b[:4] + (v,) for b in FX.HF_BASE[3:]]
    F = FX.hf_frame(base, entry=None)
    r = D.fade_on(F)
    assert r["state"] == "partial" and r["missed"] == ["k6_decay"]


def test_hf_k3_depth_does_not_bind_the_fade():
    base = list(FX.HF_BASE)
    base[2] = (10.84375, 10.9375, 10.6875, 10.90625, 100_000)     # under 11.0 − 0.5 × 0.5 = 10.75
    assert D.fade_on(FX.hf_frame(base))["state"] == "aplus"


def test_hf_earlier_higher_high_is_a_base_bar_while_k6_fails():
    b7 = (10.84375, 11.0, 10.8125, 10.96875, 50_000)
    b8 = (10.96875, 10.96875, 10.875, 10.90625, 50_000)
    e = (10.90625, 11.125, 10.90625, 11.0625, 250_000)
    F = FX.hf_frame(FX.HF_BASE + [b7, b8], entry=e, merge_from=7)
    r = D.fade_on(F)
    assert r["state"] == "aplus" and r["entry_bar_t"] == F.t[-1] and r["base"]["bars"] == 8


def _none_frame(tf="5m"):
    return FX.frame([FX.quiet(10.0)] * 12, tf=tf)


def test_hf_5m_fallback_when_15m_has_no_leg():
    r = D.horizontal_fade(_none_frame("15m"), FX.hf_frame(tf="5m"))
    assert r["state"] == "aplus" and r["frame"] == "5m"


def test_hf_15m_partial_and_5m_aplus_returns_the_5m_aplus():
    r = D.horizontal_fade(FX.hf_frame(gap_frac=0.0051), FX.hf_frame(tf="5m"))
    assert r["state"] == "aplus" and r["frame"] == "5m"


def test_hf_15m_forming_ready_wins_over_5m_aplus():
    r = D.horizontal_fade(FX.hf_frame(entry=None), FX.hf_frame(tf="5m"))
    assert r["state"] == "forming" and r["ready"] is True and r["frame"] == "15m"


def test_hf_15m_partial_stays_visible_when_5m_has_nothing():
    r = D.horizontal_fade(FX.hf_frame(gap_frac=0.0051), _none_frame())
    assert r["state"] == "partial" and r["frame"] == "15m"


def test_hf_15m_aplus_wins():
    assert D.horizontal_fade(FX.hf_frame(), _none_frame())["frame"] == "15m"


# ── 🌀 Intraday VCP ───────────────────────────────────────────────────────────────────────────────────────────
def test_vcp_aplus_two_cycles_at_070x():
    r = D.intraday_vcp(FX.vcp_frame())
    assert r["state"] == "aplus" and r["grade"] is None
    assert (r["trigger"], r["stop"]) == (10.75, 9.875)               # the last cycle's high / low (S8 33:50)


def test_vcp_fixture_leg_is_the_one_demand_bar():
    F = FX.vcp_frame()
    assert D.find_legs(F, 1) == [(TI(F, 3), TI(F, 3))]


def test_vcp_one_cycle_is_partial():
    bars = FX.VCP_BARS[:11] + [(10.5, 11.125, 10.4375, 10.75, 150_000)]
    r = D.intraday_vcp(FX.vcp_frame(bars, entry=None))
    assert r["state"] == "partial" and "k4_cycles" in r["missed"]


def test_vcp_076x_is_partial_grade_b():
    bars = FX.vcp_replace(r13=(10.1875, 10.25, 9.8, 10.125, 40_000))
    r = D.intraday_vcp(FX.vcp_frame(bars, e21_at={13: 9.8}))
    assert r["state"] == "partial" and r["grade"] == "B" and r["missed"] == ["k7_ratio"]
    assert r["reason"].startswith("B — imperfect")


def test_vcp_076x_without_b_reads_is_partial_no_grade(monkeypatch):
    monkeypatch.setattr(GC, "VCP_B_READS", False)
    r = D.intraday_vcp(FX.vcp_frame(FX.vcp_replace(r13=(10.1875, 10.25, 9.8, 10.125, 40_000)), e21_at={13: 9.8}))
    assert r["state"] == "partial" and r["grade"] is None


def test_vcp_lower_low_is_invalid_in_both(monkeypatch):
    bars = FX.vcp_replace(r13=(10.1875, 10.25, 9.6875, 10.125, 40_000))
    for b in (True, False):
        monkeypatch.setattr(GC, "VCP_B_READS", b)
        assert D.intraday_vcp(FX.vcp_frame(bars))["reason"] == "lower low — not contracting up"


def test_vcp_cycle_low_under_the_21_ema_is_b_or_invalid(monkeypatch):
    F = FX.vcp_frame(e21_at={13: 10.0})
    r = D.intraday_vcp(F)
    assert r["state"] == "partial" and r["grade"] == "B" and r["missed"] == ["k7_ema21"]
    monkeypatch.setattr(GC, "VCP_B_READS", False)
    assert D.intraday_vcp(F)["reason"] == "cycle low under the 21 EMA"


def test_vcp_trigger_is_the_last_cycle_high():
    r = D.intraday_vcp(FX.vcp_frame(entry=None, after=[(10.125, 10.4375, 10.0, 10.375, 40_000)]))
    assert r["state"] == "forming" and r["ready"] is True and (r["trigger"], r["stop"]) == (10.75, 9.875)


def test_vcp_not_ready_while_the_latest_bar_is_the_cycle_low():
    r = D.intraday_vcp(FX.vcp_frame(entry=None))
    assert r["state"] == "forming" and r["ready"] is False
    assert r["reason"] == "the last cycle is still making its low"


def test_vcp_post_break_lower_low_under_the_frozen_cycle_low_is_stopped():
    r = D.intraday_vcp(FX.vcp_frame(after=[(10.8125, 10.8125, 9.8125, 9.9, 200_000)]))
    assert r["state"] == "stopped" and r["stop"] == 9.875


def test_vcp_entry_bar_undercuts_before_its_break_minute_is_invalid():
    mins = [(10.5625, 10.6, 9.8, 10.0, 1), (10.0, 10.875, 10.0, 10.8, 1)]
    r = D.intraday_vcp(FX.vcp_frame(minutes={14: mins}))
    assert r["state"] == "invalid"


def test_vcp_entry_bar_undercuts_after_its_break_minute_is_stopped():
    mins = [(10.5625, 10.875, 10.5, 10.8, 1), (10.8, 10.8, 9.8, 10.0, 1)]
    r = D.intraday_vcp(FX.vcp_frame(minutes={14: mins}))
    assert r["state"] == "stopped"


def test_vcp_a_new_pivot_high_after_the_break_never_moves_trigger_or_stop():
    after = [(10.8125, 11.5, 10.75, 11.1, 90_000), (11.1, 11.45, 11.0, 11.1, 60_000),
             (11.1, 11.2, 10.9, 11.0, 50_000), (11.0, 11.3, 11.0, 11.25, 50_000),
             (11.25, 11.4, 11.1, 11.3, 50_000)]
    r = D.intraday_vcp(FX.vcp_frame(after=after))
    assert r["state"] == "triggered" and (r["trigger"], r["stop"]) == (10.75, 9.875)
    assert r["entry_bar_t"] == FX.vcp_frame().t[-1]


def test_lqr_heavy_selling_after_the_main_bar_is_invalid_in_both(monkeypatch):
    bars = FX.vcp_replace(r6=(10.875, 10.9375, 10.375, 10.4375, 600_000), r7=(10.4375, 10.5, 10.0, 10.0625, 500_000))
    F = FX.vcp_frame(bars, e21_at={8: 10.0})
    for b in (True, False):
        monkeypatch.setattr(GC, "VCP_B_READS", b)
        assert D.intraday_vcp(F)["state"] == "invalid"


def test_ayla_sharp_pullback_is_invalid_in_both(monkeypatch):
    bars = FX.vcp_replace(r13=(10.1875, 10.25, 9.8, 10.125, 40_000))   # expands (0.76×) AND under the 21 EMA
    F = FX.vcp_frame(bars, e21_at={13: 10.0})
    for b in (True, False):
        monkeypatch.setattr(GC, "VCP_B_READS", b)
        assert D.intraday_vcp(F)["reason"] == "cycle low under the 21 EMA"


def test_vcp_k3_depth_does_not_bind():
    assert D.intraday_vcp(FX.vcp_frame())["state"] == "aplus"          # cycle 1 sinks to 9.75, under 10.25
    assert FX.VCP_BARS[8][2] < D.k3_floor(FX.vcp_frame(), TI(FX.vcp_frame(), 3))


# ── 🌀 the read carries its contraction count (2026-10-20, BUILD_SPEC18 D2) ────────────────────────────────────
# Ajay 2026-10-20: "show me stocks only that have 2 contractions" — the tab cards from `cycles`; the detector only
# COUNTS (no state, criterion, trigger or stop moves).
VCP_THIRD = [(10.125, 10.375, 10.0625, 10.3125, 40_000), (10.3125, 10.5, 10.25, 10.4375, 40_000),
             (10.4375, 10.5625, 10.375, 10.5, 40_000), (10.5, 10.5, 10.25, 10.3125, 30_000),
             (10.3125, 10.375, 10.0625, 10.125, 30_000), (10.125, 10.25, 10.0, 10.1875, 30_000),
             (10.1875, 10.3125, 10.125, 10.25, 30_000), (10.25, 10.375, 10.1875, 10.3125, 30_000),
             (10.3125, 10.4375, 10.25, 10.375, 30_000)]           # a third, tighter cycle: H3 10.5625, L3 10.0

VCP_STATE_TABLE = [   # (name, frame builder, cycles, state, reason, missed, grade, trigger, stop, ready)
    ("printing_highs", lambda: FX.vcp_frame(FX.VCP_BARS[:6], entry=None), 0, "forming",
     "no pullback yet — the leg is still printing highs", [], None, 11.0, None, False),
    ("one_forming", lambda: FX.vcp_frame(FX.VCP_BARS[:11], entry=None), 1, "forming",
     "1 of 2 cycles", [], None, 11.0, 9.75, False),
    ("one_broke", lambda: FX.vcp_frame(FX.VCP_BARS[:11] + [(10.5, 11.125, 10.4375, 10.75, 150_000)], entry=None), 1,
     "partial", "broke — not A+", ["k4_cycles"], None, 11.0, 9.75, False),
    ("two_aplus", lambda: FX.vcp_frame(), 2, "aplus", "", [], None, 10.75, 9.875, False),
    ("two_forming", lambda: FX.vcp_frame(entry=None), 2, "forming", "the last cycle is still making its low", [],
     None, 10.75, 9.875, False),
    ("two_b", lambda: FX.vcp_frame(FX.vcp_replace(r13=(10.1875, 10.25, 9.8, 10.125, 40_000)), e21_at={13: 9.8}), 2,
     "partial", "B — imperfect · missed k7_ratio", ["k7_ratio"], "B", 10.75, 9.8, False),
    ("three_b", lambda: FX.vcp_frame(FX.VCP_BARS + VCP_THIRD, entry=None), 3, "partial",
     "B — imperfect · missed k7_ema21", ["k7_ema21"], "B", 10.5625, 10.0, False),
    ("two_lower_low", lambda: FX.vcp_frame(FX.vcp_replace(r13=(10.1875, 10.25, 9.6875, 10.125, 40_000))), 2,
     "invalid", "lower low — not contracting up", [], None, None, None, False),
]


@pytest.mark.parametrize("row", VCP_STATE_TABLE, ids=[r[0] for r in VCP_STATE_TABLE])
def test_vcp_read_carries_its_cycle_count(row):
    _name, build, cycles, *_ = row
    r = D.intraday_vcp(build())
    assert r["cycles"] == cycles and isinstance(r["cycles"], int) and not isinstance(r["cycles"], bool)


@pytest.mark.parametrize("row", VCP_STATE_TABLE, ids=[r[0] for r in VCP_STATE_TABLE])
def test_NEGATIVE_the_vcp_state_table_is_unchanged_by_the_count(row):
    """The count is the ONLY new key: state / reason / missed / grade / trigger / stop / ready are the pre-2026-10-20
    values, and the key set is the blank read's plus nothing else."""
    _name, build, _c, state, reason, missed, grade, trigger, stop, ready = row
    r = D.intraday_vcp(build())
    assert (r["state"], r["reason"], r["missed"], r["grade"], r["trigger"], r["stop"], r["ready"]) == \
        (state, reason, missed, grade, trigger, stop, ready)
    assert set(r) == set(D._blank("intraday_vcp", None, -1))


def test_NEGATIVE_cycles_is_none_on_every_other_setup_and_on_a_read_with_no_leg():
    assert D._blank("bull_flag", None, -1)["cycles"] is None
    assert D.bull_flag(FX.frame(FX.bf_bars()))["cycles"] is None
    assert D.intraday_vcp(FX.frame([FX.quiet(10.0)] * 5))["cycles"] is None     # no demand leg — nothing counted
    assert D.intraday_vcp(FX.vcp_frame())["cycles"] == GC.K4_VCP_MIN_CYCLES


# ── 🎾 Reversal Squeeze ──────────────────────────────────────────────────────────────────────────────────────
def _rs(F=None, shares=5_000_000, **kw):
    return D.reversal_squeeze(F if F is not None else FX.rs_frame(), float_read=FX.float_read(shares, **kw))


def test_rs_aplus_float_5m():
    r = _rs()
    assert r["state"] == "aplus" and (r["trigger"], r["stop"]) == (6.25, 6.09375)
    assert r["meta"]["structure_alive"] is True


def test_rs_float_over_10m_is_none():
    r = _rs(shares=10_000_001)
    assert r["state"] == "none" and r["reason"] == "Float 10.0M > 10,000,000" and r["meta"]["structure_alive"]


def test_rs_float_exactly_10m_is_eligible():
    assert _rs(shares=GC.K8_MAX_FLOAT)["state"] == "aplus"


def test_rs_float_unknown_is_none_with_structure_alive():
    r = D.reversal_squeeze(FX.rs_frame(), float_read=None)
    assert r["state"] == "none" and r["reason"] == "float unknown" and r["meta"]["structure_alive"] is True
    r2 = _rs(shares=None)
    assert r2["reason"] == "float unknown" and r2["as_of_bar_t"] is not None


def test_fchl_suspect_float_per_policy(monkeypatch):
    r = _rs(shares=1_314_047, suspect="float_exceeds_shares_out")
    assert r["state"] == "none" and r["reason"] == "float unknown"
    monkeypatch.setattr(GC, "FLOAT_SUSPECT_POLICY", "shares_out")
    assert _rs(shares=1_299_391, suspect="float_exceeds_shares_out")["state"] == "aplus"


def test_rs_799pct_drop_is_no_tennis_ball():
    F = FX.rs_frame(FX.rs_replace(r9=(6.1875, 6.25, 6.25 * (1 - 0.0799), 5.8, 500_000)))
    r = _rs(F)
    assert r["state"] == "none" and r["reason"].startswith("no tennis ball")


def test_rs_recovery_on_the_4th_bar_is_no_tennis_ball():
    slow = FX.rs_replace(r10=(5.75, 6.0, 5.75, 5.875, 400_000), r11=(5.875, 6.0, 5.8125, 5.9375, 60_000),
                         r12=(5.9375, 6.0625, 5.875, 6.0, 50_000))
    F = FX.rs_frame(slow, entry=(6.0, 6.25, 6.0, 6.1875, 400_000))
    assert D.tennis_balls(F, len(F.c) - 1) == []
    assert _rs(F)["state"] == "none"


def test_rs_no_failed_attempt_is_partial():
    calm = FX.rs_replace(r3=(5.875, 5.875, 5.75, 5.8125, 100_000), r4=(5.8125, 5.84375, 5.75, 5.8125, 100_000),
                         r5=(5.8125, 5.84375, 5.75, 5.8125, 100_000), r6=(5.8125, 5.84375, 5.75, 5.8125, 100_000),
                         r7=(5.8125, 5.84375, 5.75, 5.8125, 100_000))
    r = _rs(FX.rs_frame(calm))
    assert r["state"] == "partial" and r["missed"] == ["k8_failed"]


def test_s8_3612_shape_partial_under_distinct_aplus_under_same_ok(monkeypatch):
    F = FX.rs_frame(FX.RS_S8_BARS, entry=FX.RS_S8_E)
    assert _rs(F)["state"] == "partial"
    monkeypatch.setattr(GC, "K8_FAIL_EVENT_RULE", "same_ok")
    assert _rs(F)["state"] == "aplus"


def test_an_attempt_that_made_a_new_high_and_closed_above_it_is_not_an_attempt():
    F = FX.rs_frame()
    a = TI(F, 8)                                                       # 6.25 high, closes 6.1875 above the 6.0 high
    assert a not in [x for x, _ in D.failed_attempts(F, len(F.c) - 1)]
    assert TI(F, 3) in [x for x, _ in D.failed_attempts(F, len(F.c) - 1)]


def test_rs_base_volume_051x_of_the_squeeze_back_is_partial():
    loud = FX.rs_replace(r11=(6.1875, 6.21875, 6.125, 6.15625, 0.51 * FX.RS_BARS[10][4]))
    r = _rs(FX.rs_frame(loud))
    assert r["state"] == "partial" and r["missed"] == ["k3_vol"]


def test_rs_base_under_the_top_bars_midpoint_does_not_invalidate(monkeypatch):
    """Ajay round C: the K3 depth floor binds Bull Flag + Kiss & Fly only — never the squeeze."""
    deep = FX.rs_replace(r12=(6.15625, 6.1875, 6.0, 6.125, 50_000))    # midpoint of 5.8125–6.25 = 6.03125
    assert _rs(FX.rs_frame(deep))["state"] == "aplus"
    monkeypatch.setattr(GC, "K3_DEPTH_SETUPS", GC.K3_DEPTH_SETUPS + ("reversal_squeeze",))
    assert _rs(FX.rs_frame(deep))["state"] == "invalid"


def test_rs_a_higher_high_before_the_minimum_base_moves_the_top():
    up = FX.rs_replace(r11=(6.1875, 6.3125, 6.15625, 6.28125, 60_000))
    F = FX.rs_frame(up[:12], entry=None)
    r = _rs(F)
    assert r["broke"] is False and r["leg"]["e_t"] == F.t[TI(F, 11)]
    assert r["state"] == "forming" and r["ready"] is False


def test_rs_criteria_carry_no_k1_leg_or_k2():
    keys = {c["key"] for c in _rs()["criteria"]}
    assert keys == {"k8_tennis", "k8_failed", "k3_vol", "k8_base_len"}
    assert not keys & {"k2", "k1"}


def test_snes_spike_and_violent_decline_is_no_tennis_ball():
    bars = [(5.0, 5.125, 4.875, 5.0, 100_000), (5.0, 8.0, 5.0, 7.75, 3_000_000), (7.75, 7.75, 6.5, 6.6, 2_000_000),
            (6.6, 6.7, 5.75, 5.8, 1_500_000), (5.8, 6.0, 5.5, 5.6, 900_000), (5.6, 5.75, 5.25, 5.3, 600_000)]
    assert _rs(FX.rs_frame(bars, entry=None))["state"] == "none"


def test_sasi_steady_fade_is_none():
    bars = [(8.0 - 0.125 * i, 8.0625 - 0.125 * i, 7.875 - 0.125 * i, 7.875 - 0.125 * i, 300_000) for i in range(14)]
    assert _rs(FX.rs_frame(bars, entry=None))["state"] == "none"


def test_sgd_no_demand_after_the_open_is_none():
    pm = [(3.0, 3.0625, 2.96875, 3.0, 100_000), (3.0, 4.0, 3.0, 3.9375, 2_000_000)]
    drift = [(3.9375 - 0.0625 * i, 3.96875 - 0.0625 * i, 3.875 - 0.0625 * i, 3.875 - 0.0625 * i, 80_000)
             for i in range(12)]
    assert _rs(FX.rs_frame(pm + drift, entry=None))["state"] == "none"


# ── source guards ─────────────────────────────────────────────────────────────────────────────────────────────
def test_no_numeric_literal_in_detectors_beyond_indexing_and_percent():
    """Every threshold lives in constants.py. Only 0 / 1 / 2 (indexing, the K6 halves) and 100 (percent) appear."""
    tree = ast.parse(SRC.read_text())
    bad = [(n.lineno, n.value) for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)
           and n.value not in (0, 1, 2, 100)]
    assert bad == []


def test_constants_are_read_at_call_time_not_imported_by_name():
    text = SRC.read_text()
    assert "from chart_maps.gajjala.constants import" not in text
    assert "from chart_maps.gajjala import constants as GC" in text


def test_no_sepa_or_bonde_import_or_word():
    tree = ast.parse(SRC.read_text())
    mods = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    mods += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not [m for m in mods if "sepa" in m.lower() or "bonde" in m.lower()]
    low = SRC.read_text().lower()
    assert "bonde" not in low and "minervini" not in low and "is_candidate" not in low


def test_served_strings_never_say_bounce():
    tree = ast.parse(SRC.read_text())
    strs = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not [s for s in strs if "bounce" in s.lower()]


# ── monkeypatch-each-constant sweep ───────────────────────────────────────────────────────────────────────────
def _fix(kind):
    fr = FX.float_read(5_000_000)
    return {
        "bf": lambda: D.bull_flag(FX.bf_aplus()),
        # WIDENED 2026-10-21 (BUILD_SPEC22 B1, K11): the bf A+ at exactly the floor (= SCAN_MIN_VOLUME, read at call time)
        "bf_k11": lambda: D.k11_gate(D.bull_flag(FX.bf_aplus()), GC.SCAN_MIN_VOLUME),
        "bf5": lambda: D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(5)))),
        "rkda": lambda: D.bull_flag(FX.frame(FX.bf_bars([(11.0, 11.0, 10.6, 10.9, 100_000), FX.P2]))),
        "ocx": lambda: D.bull_flag(FX.frame(FX.bf_bars([FX.P1[:4] + (400_000,), FX.P2[:4] + (300_000,)],
                                                       leg=(FX.D1[:4] + (1_000_000,), FX.D2[:4] + (1_200_000,)),
                                                       entry=FX.BF_E))),
        "kf": lambda: D.kiss_fly(FX.kf_frame()),
        "kf_honor": lambda: D.kiss_fly(FX.kf_frame(honor_fail_at=1)),
        "kf_near": lambda: D.kiss_fly(FX.kf_near_kiss()),
        "kf_red": lambda: D.kiss_fly(FX.kf_frame(5, red=4)),
        "kf_doji": lambda: D.kiss_fly(FX.kf_frame(5, doji=4)),
        "kf_red_crit": lambda: _crit_mode(lambda: D.kiss_fly(FX.kf_frame(5, red=4))),
        "hf": lambda: D.fade_on(FX.hf_frame()),
        "vcp": lambda: D.intraday_vcp(FX.vcp_frame()),
        "vcp76": lambda: D.intraday_vcp(FX.vcp_frame(FX.vcp_replace(r13=(10.1875, 10.25, 9.8, 10.125, 40_000)),
                                                     e21_at={13: 9.8})),
        "rs": lambda: D.reversal_squeeze(FX.rs_frame(), float_read=fr),
        "rs_s8": lambda: D.reversal_squeeze(FX.rs_frame(FX.RS_S8_BARS, entry=FX.RS_S8_E), float_read=fr),
        "rs_suspect": lambda: D.reversal_squeeze(FX.rs_frame(), float_read=FX.float_read(
            1_299_391, suspect="float_exceeds_shares_out")),
    }[kind]()


def _crit_mode(fn):
    keep = GC.RED_CLOSES_MODE
    GC.RED_CLOSES_MODE = "criterion"
    try:
        return fn()
    finally:
        GC.RED_CLOSES_MODE = keep


SWEEP = [
    ("K1_RANGE_LOOKBACK", 40, "bf"), ("K1_BODY_GAIN_PCT", 6.0, "bf"), ("K1_RANGE_MULT", 3.0, "bf"),
    ("K2_MAX_VOL_STEP", 1.2, "bf"), ("K2_CHECK_FIRST_BAR", True, "ocx"), ("K3_DEPTH_FRAC", 0.1, "bf"),
    ("K3_VOL_FRAC", 0.2, "bf"), ("K3_DEPTH_SETUPS", (), "rkda"), ("K4_BF_PULL_MIN", 3, "bf"),
    ("K4_BF_PULL_MAX", 1, "bf"), ("K4_BF_LONG_FLAG_MAX", 4, "bf5"), ("K4_BF_PULL_MAX", 3, "bf5"),
    ("BF_LEG_MIN_BARS", 3, "bf"),   # 2026-10-18 (DECISIONS13 D1): bf5 is A+ shipped; LONG_FLAG_MAX 4 → invalid, PULL_MAX 3 → invalid
    ("K4_KF_PULL_MAX", 2, "kf"), ("K5_KISS_TOL_PCT", 0.0, "kf"), ("K5_SLOPE_BARS", 40, "kf"),
    ("KF_HONOR_ALL_PULLBACK_CLOSES", False, "kf_honor"), ("KF_ALLOW_NO_TOUCH", False, "kf_near"),
    ("KF_NO_TOUCH_VARIANT", "nk", "kf_near"), ("KF_LEG_MIN_BARS", 2, "kf"),
    ("RED_CLOSES_MODE", "criterion", "kf_red"), ("RED_CLOSES_WAIT", 5, "kf_red_crit"),
    ("RED_CLOSE_DEF", "close_below_prior_close", "kf_doji"),
    ("K4_HF_BASE_MIN", 7, "hf"), ("K4_HF_BASE_MAX", 5, "hf"), ("K6_MERGE_PCT", 0.1, "hf"), ("K6_TIGHT_PCT", 1.0, "hf"),
    ("K6_SELL_DECAY", 0.4, "hf"), ("HF_TRIGGER", "prior_bar", "hf"), ("HF_LEG_MIN_BARS", 3, "hf"),
    ("K4_VCP_MIN_CYCLES", 3, "vcp"), ("K7_CONTRACTION", 0.5, "vcp"), ("K7_EMA21_TOL_PCT", 0.1, "vcp"),
    ("VCP_B_READS", False, "vcp76"), ("VCP_B_GRADE", "Z", "vcp76"), ("VCP_LEG_MIN_BARS", 2, "vcp"),
    ("VCP_PIVOT_WINDOW", 3, "vcp"),
    ("K8_MAX_FLOAT", 1_000_000, "rs"), ("K8_DROP_PCT", 12.0, "rs"), ("K8_RECOVER_PCT", 0.5, "rs"),
    ("K8_RECOVER_BARS", 0, "rs"), ("K8_FAIL_NEAR_PCT", 0.0, "rs"), ("K8_FAIL_DROP_PCT", 20.0, "rs"),
    ("K8_FAIL_EVENT_RULE", "same_ok", "rs_s8"), ("RS_BASE_MIN_BARS", 3, "rs"),
    ("FLOAT_SUSPECT_POLICY", "shares_out", "rs_suspect"),
    ("K11_MIN_SESSION_VOLUME", GC.SCAN_MIN_VOLUME + 1, "bf_k11"),   # WIDENED 2026-10-21 (K11): one share over → not A+
]


@pytest.mark.parametrize("name,value,kind", SWEEP, ids=[s[0] for s in SWEEP])
def test_every_constant_moves_a_read(monkeypatch, name, value, kind):
    """Mutation sweep: each constant the detectors read changes at least one pinned read when patched — proof it is
    read at call time from constants.py and actually enforced."""
    assert hasattr(GC, name)
    before = _key(_fix(kind))
    monkeypatch.setattr(GC, name, value)
    assert _key(_fix(kind)) != before


def test_the_sweep_covers_every_constant_the_detectors_read():
    used = set()
    for n in ast.walk(ast.parse(SRC.read_text())):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "GC":
            used.add(n.attr)
    structural = {"PLACEHOLDER_BY_SETUP", "PLACEHOLDERS", "K8_FAIL_EVENT_RULES", "SETUPS"}
    assert used - structural == {s[0] for s in SWEEP}


# ── tennis-ball bar order + the open leg question ────────────────────────────────────────────────────────────
def test_a_wide_green_bar_is_not_a_tennis_ball_by_itself():
    """A ≥ 8%-range green bar has its low BEFORE its high — not a drop from a high (d == r needs minute order)."""
    F = FX.rs_frame([(5.0, 5.125, 4.875, 5.0, 100_000), (5.0, 5.5, 5.0, 5.5, 900_000)] + [FX.quiet(5.5)] * 3,
                    entry=None)
    assert D.tennis_balls(F, len(F.c) - 1) == []


def test_high_then_low_inside_one_bar_is_a_drop_from_that_high():
    bars = [(5.0, 5.125, 4.875, 5.0, 100_000), (5.0, 5.5, 5.0, 5.4375, 900_000)] + [FX.quiet(5.5)] * 3
    hi_first = [(5.3, 5.5, 5.3, 5.4, 1), (5.4, 5.4, 5.0, 5.1, 1), (5.1, 5.45, 5.1, 5.4375, 1)]
    lo_first = [(5.0, 5.1, 5.0, 5.05, 1), (5.05, 5.5, 5.05, 5.4375, 1)]
    F1 = FX.rs_frame(bars, entry=None, minutes={1: hi_first})
    F2 = FX.rs_frame(bars, entry=None, minutes={1: lo_first})
    j = TI(F1, 1)
    assert D.tennis_balls(F1, len(F1.c) - 1) == [(j, j, j)]
    assert D.tennis_balls(F2, len(F2.c) - 1) == []


def _kf_demand_breakout():
    """kf_frame without its entry, then an entry bar that is ITSELF a K1 demand bar (a strong breakout bar)."""
    F = FX.kf_frame(entry=False)
    last = len(F.c) - 1
    o = F.c[last]
    big = (o, F.h[last] + 0.5, F.l[last] + 0.015625, o * (1 + GC.K1_BODY_GAIN_PCT / 100) + 0.25, 300_000)
    return FX.frame([(F.o[i], F.h[i], F.l[i], F.c[i], F.v[i]) for i in F.today] + [big],
                    ema9=F.ema9[F.today.start:] + [F.ema9[-1]], ema21=F.ema21[F.today.start:] + [F.ema21[-1]])


def test_a_k1_entry_bar_does_not_erase_the_kiss_fly_a_plus():
    """NEGATIVE (was open question Q1, pinned the wrong way): a breakout bar that is itself a K1 demand bar starts a
    new leg AT the structure's break bar — it must not restart the read; the original leg's A+ stands."""
    G = _kf_demand_breakout()
    assert D.is_demand(G, len(G.c) - 1)
    base = D.kiss_fly(FX.kf_frame())
    r = D.kiss_fly(G)
    assert r["state"] == "aplus" and r["leg"] == base["leg"] and r["leg"]["e_t"] != G.t[-1]
    assert (r["trigger"], r["stop"]) == (base["trigger"], base["stop"])


def test_a_k1_upswing_inside_the_vcp_cycles_does_not_erase_the_vcp():
    """NEGATIVE: a +3.75% K1 bar on the cycle-2 upswing is a new 1-bar leg INSIDE the cycles — the VCP A+ stands."""
    base = D.intraday_vcp(FX.vcp_frame())
    F = FX.vcp_frame(FX.vcp_replace(r9=(10.0, 10.4375, 9.875, 10.375, 60_000)))
    assert D.is_demand(F, TI(F, 9)) and len(D.find_legs(F, GC.VCP_LEG_MIN_BARS)) == 2
    r = D.intraday_vcp(F)
    assert r["state"] == "aplus" and r["leg"] == base["leg"]
    assert (r["trigger"], r["stop"]) == (base["trigger"], base["stop"]) == (10.75, 9.875)


def test_a_two_bar_k1_breakout_keeps_the_bull_flag_triggered_and_flag_1():
    """NEGATIVE: the entry bar and the bar after it are both K1 bars (a new 2-bar leg starting AT the break bar) —
    the flag stays triggered and is still flag 1, not a new forming flag 2."""
    e1 = (10.875, 11.5, 10.875, 11.5, 400_000)
    e2 = (11.5, 12.25, 11.5, 12.25, 600_000)
    F = FX.frame(FX.bf_bars(entry=e1, after=[e2]))
    assert D.is_demand(F, len(F.c) - 2) and D.is_demand(F, len(F.c) - 1)
    r = D.bull_flag(F)
    assert r["state"] == "triggered" and r["flag_k"] == 1 and r["entry_bar_t"] == F.t[-2]
    assert r["leg"] == D.bull_flag(FX.bf_aplus())["leg"]


def test_a_leg_after_the_break_bar_does_start_a_new_structure():
    """NEGATIVE of the keep rule: a demand leg that starts AFTER the break bar is a new structure (the read moves)."""
    F = FX.kf_frame()
    o = F.c[-1]
    new = (o, o + 0.75, o, o + 0.75, 400_000)
    G = FX.frame([(F.o[i], F.h[i], F.l[i], F.c[i], F.v[i]) for i in F.today] + [FX.quiet(o + 0.0625), new],
                 ema9=F.ema9[F.today.start:] + [F.ema9[-1]] * 2, ema21=F.ema21[F.today.start:] + [F.ema21[-1]] * 2)
    assert D.is_demand(G, len(G.c) - 1)
    r = D.kiss_fly(G)
    assert r["leg"]["s_t"] == G.t[-1] and r["state"] == "forming"


def test_a_stopped_structure_does_not_hold_back_a_newer_leg():
    """NEGATIVE: only forming / aplus / triggered reads are kept — a leg inside a structure that is no longer live
    (here: the Kiss & Fly pullback ran past K4_KF_PULL_MAX → invalid) is read on its own."""
    assert set(D.LIVE_STATES) == {"forming", "aplus", "triggered"}
    F = FX.kf_frame(GC.K4_KF_PULL_MAX + 1, entry=False)
    assert D.kiss_fly(F)["state"] == "invalid"
    o = F.c[-1]
    new = (o, o + 0.75, o, o + 0.75, 400_000)
    G = FX.frame([(F.o[i], F.h[i], F.l[i], F.c[i], F.v[i]) for i in F.today] + [new],
                 ema9=F.ema9[F.today.start:] + [F.ema9[-1]], ema21=F.ema21[F.today.start:] + [F.ema21[-1]])
    assert D.is_demand(G, len(G.c) - 1)
    assert D.kiss_fly(G)["leg"]["s_t"] == G.t[-1]


def _kf_higher_high_then_kiss(entry: bool = True):
    """leg, P1, P2 (high 1/64 above P1, nothing touched yet), P3, P4 (a true kiss), then E breaks P4's high."""
    P1 = (10.5, 10.5, 10.40625, 10.46875, 100_000)
    P2 = (10.46875, 10.515625, 10.4375, 10.484375, 90_000)
    P3 = (10.484375, 10.5, 10.375, 10.4375, 80_000)
    P4 = (10.4375, 10.46875, 10.3125, 10.40625, 70_000)
    E = (10.40625, 10.6, 10.375, 10.59, 200_000)
    bars = [FX.quiet(10.0)] * 4 + [FX.KF_D, P1, P2, P3, P4] + ([E] if entry else [])
    e9 = [9.75] * 4 + [9.875, 10.0, 10.1, 10.2, 10.3046875] + ([10.33] if entry else [])
    e21 = [9.5 + 0.03125 * i for i in range(len(bars))]
    return FX.frame(bars, ema9=e9, ema21=e21)


def test_a_higher_high_before_a_later_kiss_still_reads_aplus():
    """NEGATIVE (Ajay K5a: near-kiss = a pullback that NEVER kissed): a pullback bar that ticks a higher high before
    any touch must not freeze the read — the later kiss-then-break is the A+ (same read as near-kiss switched off)."""
    F = _kf_higher_high_then_kiss()
    kb = TI(F, 8)
    assert D.kiss(F, kb) is True and D.touch(F, TI(F, 5)) is False and D.touch(F, TI(F, 6)) is False
    r = D.kiss_fly(F)
    assert r["state"] == "aplus" and r["variant"] is None and r["missed"] == []
    assert (r["trigger"], r["stop"]) == (F.h[kb], F.l[kb]) == (10.46875, 10.3125)


def test_higher_high_then_kiss_reads_through_time():
    """Before the touch it IS a never-kissed flight (near-kiss); once a bar kisses it is a Kiss & Fly waiting for the
    break (forming, ready) — never a near-kiss again."""
    F = _kf_higher_high_then_kiss(entry=False)
    r = D.kiss_fly(F, last=TI(F, 7))
    assert r["state"] == "partial" and r["variant"] == GC.KF_NO_TOUCH_VARIANT
    r = D.kiss_fly(F)
    assert r["state"] == "forming" and r["ready"] is True and r["variant"] is None


def test_long_flag_label_is_built_from_the_constants(monkeypatch):
    """2026-10-18 (DECISIONS13 D1): with K4_BF_LONG_FLAG_MAX None the k4 label is the plain 1–5 range and never names a
    long flag; with the band configured (PULL_MAX 2, LONG_FLAG_MAX 5) the label carries the band from the constants."""
    r = D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(5))))
    k4 = next(c for c in r["criteria"] if c["key"] == "k4")
    assert k4["label"] == f"K4 pullback {GC.K4_BF_PULL_MIN}–{GC.K4_BF_PULL_MAX} bars" == "K4 pullback 1–5 bars"
    assert "long flag" not in k4["label"]
    monkeypatch.setattr(GC, "K4_BF_PULL_MAX", 2)
    monkeypatch.setattr(GC, "K4_BF_LONG_FLAG_MAX", 5)
    r = D.bull_flag(FX.frame(FX.bf_bars(FX.flat_pull(5))))
    k4 = next(c for c in r["criteria"] if c["key"] == "k4")
    assert k4["label"].endswith(f"({GC.K4_BF_PULL_MAX + 1}–{GC.K4_BF_LONG_FLAG_MAX} = long flag)")
    assert "(3–5 = long flag)" in k4["label"] and "4–5" not in k4["label"]


def test_a_pending_criterion_is_not_listed_as_missed():
    """NEGATIVE: a forming read only WAITING for a length minimum / the kiss shows the criterion ✗ but never lists it
    in `missed` (a reader would show "missed: kiss" on a structure that is only waiting)."""
    r = D.kiss_fly(FX.kf_frame(kiss_above_pct=0.6, entry=False))
    assert r["state"] == "forming" and r["missed"] == []
    assert next(c for c in r["criteria"] if c["key"] == "k5_kiss")["ok"] is False
    r = D.bull_flag(FX.frame(FX.bf_bars([], entry=None)))
    assert r["state"] == "forming" and "k4" not in r["missed"]
    assert next(c for c in r["criteria"] if c["key"] == "k4")["ok"] is False
    assert not any("_pending" in c for c in r["criteria"])


def test_a_hard_failure_on_a_forming_read_is_still_missed():
    """…while a real failure on a read with no break is still `missed` (partial)."""
    r = D.kiss_fly(FX.kf_frame(e21_over=0.0078125, entry=False))
    assert r["state"] == "partial" and "k5_uptrend" in r["missed"]


def test_read_all_on_a_frame_built_by_bars_py():
    """The input contract end to end: WP1's `bars.build_frame` over a UTC-indexed closed frame → the same reads."""
    import pandas as pd
    from chart_maps.gajjala import bars as B
    src = FX.vcp_frame()
    n_prior = src.today.start
    idx = (list(pd.date_range("2026-10-12 19:05", periods=n_prior, freq="5min"))
           + list(pd.date_range("2026-10-13 13:35", periods=len(src.c) - n_prior, freq="5min")))
    closed = pd.DataFrame({"open": src.o, "high": src.h, "low": src.l, "close": src.c, "volume": src.v},
                          index=pd.DatetimeIndex(idx))
    f5 = B.build_frame(closed, "2026-10-13", "5min")
    assert f5.today == src.today
    f5.ema21 = list(src.ema21)                                       # the fixture's explicit 21 EMA under the lows
    out = D.read_all({"5m": f5, "15m": None}, {"symbol": "VCPX", "float_read": None})
    assert out["intraday_vcp"]["state"] == "aplus"
    assert out["intraday_vcp"]["as_of_bar_t"] == f5.t[-1]
