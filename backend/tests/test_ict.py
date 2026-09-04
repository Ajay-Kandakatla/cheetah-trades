"""ICT strategy — structure primitives, the dormant engine, the Chart Maps tab.

Ajay 2026-09-03 (late): "create a new chart maps tab for ICT Strategy,
replace supply tab with this new tab." Source: his spec + Jesse Rogers'
video (URL in ict/structure.py). Everything here runs on SYNTHETIC frames
with the price loader, the intraday loader and Mongo stubbed — no network,
no scan on disk, no database.

The negatives carry the weight: a tie is not a swing, a touching candle is
not a gap, a wick through the far edge fills a gap but does not invert it,
one wide bar breaks a consolidation, a close through the level is a break
and not a manipulation, a big candle without a gap does not confirm, a cross
without a gap is not an MSS, and an untapped name never wakes the 60-minute
loop.
"""
from __future__ import annotations

import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ict import structure as S  # noqa: E402
from ict import engine as E  # noqa: E402
from ict import board as IB  # noqa: E402
from chart_maps import board as B  # noqa: E402
import supply_demand.into_supply  # noqa: E402,F401  (same pre-cache reason as test_chart_maps)

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# synthetic frames
# ---------------------------------------------------------------------------
def _daily(rows, start="2026-05-01"):
    """rows = [(o, h, l, c), ...] on business days."""
    idx = pd.bdate_range(start, periods=len(rows))
    return pd.DataFrame({"open": [r[0] for r in rows], "high": [r[1] for r in rows],
                         "low": [r[2] for r in rows], "close": [r[3] for r in rows],
                         "volume": [2_000_000.0] * len(rows)}, index=idx)


def _hourly_index(n, start="2026-08-17"):
    """UTC-naive stamps the way the minute loader leaves them: seven
    right-labelled RTH hours per business day (14:30 .. 20:30 UTC =
    10:30 .. 16:30 ET)."""
    days = pd.bdate_range(start, periods=(n // 7) + 2)
    stamps = []
    for d in days:
        for hh in range(14, 21):
            stamps.append(pd.Timestamp(f"{d.strftime('%Y-%m-%d')} {hh:02d}:30:00"))
    return pd.DatetimeIndex(stamps[:n])


def _hourly(rows, start="2026-08-17"):
    idx = _hourly_index(len(rows), start)
    return pd.DataFrame({"open": [r[0] for r in rows], "high": [r[1] for r in rows],
                         "low": [r[2] for r in rows], "close": [r[3] for r in rows],
                         "volume": [300_000.0] * len(rows)}, index=idx)


def _flat(n, o=100.0, h=100.5, lo=99.5, c=100.0):
    return [(o, h, lo, c)] * n


def _accumulation(n):
    """Alternating tight bars: fractal highs on even bars, lows on odd."""
    out = []
    for i in range(n):
        if i % 2 == 0:
            out.append((100.0, 100.5, 99.7, 100.1))
        else:
            out.append((100.1, 100.3, 99.5, 100.0))
    return out


def _et_date(ts) -> str:
    return pd.Timestamp(ts).tz_localize("UTC").tz_convert("America/New_York").strftime("%Y-%m-%d")


# The confirmed-then-entry 60m frame used by the engine and board tests:
# accumulation (0-24) -> manipulation under its low (25) -> 2-ATR push that
# leaves a gap (26/27) -> MSS on 26 -> pullback into the gap (28-30).
def _micro_entry_frame():
    rows = _accumulation(25)
    rows += [(99.8, 100.2, 98.5, 99.6),      # 25 manipulation: wick under 99.5, close back above
             (99.7, 101.8, 99.6, 101.7),     # 26 displacement up, body 2.0
             (101.6, 102.4, 101.0, 102.2),   # 27 low 101.0 > bar-25 high 100.2 -> bullish FVG
             (102.2, 102.3, 101.5, 101.8),   # 28 pullback
             (101.8, 101.9, 101.2, 101.4),   # 29
             (101.4, 101.5, 100.9, 101.0)]   # 30 last = 101.0, inside the gap's edge
    return _hourly(rows)


# accumulation -> a bearish gap on the way down -> manipulation of the daily
# level -> a push that CLOSES above the bearish gap (inverting it) and leaves a
# bullish gap -> MSS -> pullback into the IFVG.
def _micro_ifvg_frame():
    rows = _accumulation(25)
    rows += [(100.0, 100.4, 99.6, 99.5),     # 25
             (99.5, 99.6, 98.0, 98.2),       # 26 drop, body 1.3
             (98.2, 98.9, 97.8, 98.5),       # 27 high 98.9 < bar-25 low 99.6 -> bearish FVG [98.9, 99.6]
             (98.5, 98.7, 97.2, 97.8),       # 28 wick under the daily level 97.5, close back above
             (97.8, 100.2, 97.7, 100.1),     # 29 push up, CLOSES above 99.6 -> the bearish gap inverts
             (100.0, 100.9, 99.8, 100.7),    # 30 low 99.8 > bar-28 high 98.7 -> bullish FVG; close > 100.5 = MSS
             (100.6, 100.7, 99.5, 99.6)]     # 31 pullback into the IFVG
    return _hourly(rows)


def _macro_ctx(tapped_bias="bullish", tapped_price=99.5):
    return {"symbol": "AAA", "last": 101.0, "atr": 1.5, "key_low": 97.0, "key_high": 103.0,
            "swings": [{"kind": "swing_low", "price": 97.0, "date": "2026-08-20", "i": 60},
                       {"kind": "swing_high", "price": 105.0, "date": "2026-08-10", "i": 50},
                       {"kind": "swing_high", "price": 103.0, "date": "2026-08-25", "i": 70}],
            "fvgs": [], "consolidations": 1, "stacked": False,
            "tapped": {"kind": "swing_low" if tapped_bias == "bullish" else "swing_high",
                       "price": tapped_price, "date": "2026-09-02", "bar_i": 78,
                       "bias": tapped_bias},
            "liquidity": {"avg_dollar_vol_50": 50_000_000.0}, "date": "2026-09-03"}


# ---------------------------------------------------------------------------
# swings — the 3-candle fractal
# ---------------------------------------------------------------------------
def test_fractal_swing_high_needs_strictly_lower_neighbours_on_both_sides():
    df = _daily([(10, 10, 9, 10), (10, 11, 9, 10), (10, 12, 9, 10), (10, 11, 9, 10), (10, 10, 9, 10)])
    lows, highs = S.swing_points_fractal(df)
    assert highs == [(2, 12.0)]
    assert lows == []                      # every low is 9 — ties are not swings


def test_fractal_swing_low_is_the_mirror():
    df = _daily([(10, 11, 10, 10), (10, 11, 9, 10), (10, 11, 8, 10), (10, 11, 9, 10), (10, 11, 10, 10)])
    lows, highs = S.swing_points_fractal(df)
    assert lows == [(2, 8.0)]
    assert highs == []


def test_a_tie_is_not_a_swing():
    df = _daily([(10, 10, 9, 10), (10, 12, 9, 10), (10, 12, 9, 10), (10, 10, 9, 10)])
    lows, highs = S.swing_points_fractal(df)
    assert highs == []


def test_swings_never_raise_on_junk():
    assert S.swing_points_fractal(None) == ([], [])
    assert S.swing_points_fractal(pd.DataFrame({"close": [1, 2, 3]})) == ([], [])
    assert S.swing_points_fractal(_daily([(1, 2, 0, 1)])) == ([], [])


def test_swing_targets_are_dated_and_ordered():
    df = _daily([(10, 11, 10, 10), (10, 11, 9, 10), (10, 11, 8, 10), (10, 11, 9, 10), (10, 13, 10, 10), (10, 11, 10, 10)])
    lows, highs = S.swing_points_fractal(df)
    t = S.swing_targets(df, lows, highs)
    assert [x["kind"] for x in t] == ["swing_low", "swing_high"]
    assert t[0]["at"].startswith("2026-05-05") and t[0]["price"] == 8.0


# ---------------------------------------------------------------------------
# raw fair value gaps
# ---------------------------------------------------------------------------
def test_bullish_gap_when_the_third_low_clears_the_first_high():
    df = _daily([(10, 10.0, 9.5, 9.9), (10, 11.5, 9.9, 11.4), (11.4, 12, 10.5, 11.8)])
    gaps = S.fair_value_gaps_raw(df)
    assert len(gaps) == 1
    g = gaps[0]
    assert g["kind"] == "bullish" and g["lo"] == 10.0 and g["hi"] == 10.5
    assert g["i"] == 2 and g["disp_i"] == 1


def test_bearish_gap_when_the_third_high_is_under_the_first_low():
    df = _daily([(10, 10.5, 10.0, 10.1), (10, 10.1, 8.5, 8.6), (8.6, 9.5, 8.0, 8.2)])
    gaps = S.fair_value_gaps_raw(df)
    assert len(gaps) == 1
    assert gaps[0]["kind"] == "bearish" and gaps[0]["lo"] == 9.5 and gaps[0]["hi"] == 10.0


def test_touching_candles_leave_no_gap():
    df = _daily([(10, 10.0, 9.5, 9.9), (10, 11.5, 9.9, 11.4), (11.4, 12, 10.0, 11.8)])
    assert S.fair_value_gaps_raw(df) == []


def test_no_gap_on_short_or_junk_frames():
    assert S.fair_value_gaps_raw(None) == []
    assert S.fair_value_gaps_raw(_daily([(1, 2, 0, 1), (1, 2, 0, 1)])) == []


# ---------------------------------------------------------------------------
# gap state: active -> mitigated -> filled, inverted only on a CLOSE
# ---------------------------------------------------------------------------
def _gap_frame(tail):
    rows = [(10, 10.0, 9.5, 9.9), (10, 11.5, 9.9, 11.4), (11.4, 12, 10.5, 11.8)] + tail
    return _daily(rows)


def test_a_gap_nobody_touched_is_active():
    df = _gap_frame([(11.8, 12.2, 11.0, 12.0)])
    st = S.fvg_state(S.fair_value_gaps_raw(df), df)
    assert st[0]["status"] == "active" and st[0]["mitigated_i"] is None


def test_a_wick_into_the_band_mitigates_it():
    df = _gap_frame([(11.8, 12.2, 10.3, 12.0)])
    st = S.fvg_state(S.fair_value_gaps_raw(df), df)
    assert st[0]["status"] == "mitigated" and st[0]["mitigated_i"] == 3


def test_a_wick_through_the_far_edge_fills_but_does_not_invert():
    df = _gap_frame([(11.8, 12.2, 9.8, 10.4)])         # low 9.8 < 10.0, close 10.4 >= 10.0
    st = S.fvg_state(S.fair_value_gaps_raw(df), df)
    assert st[0]["status"] == "filled"
    assert st[0]["inverted_kind"] is None


def test_a_close_beyond_the_far_edge_inverts_a_bullish_gap_to_bearish():
    df = _gap_frame([(11.8, 12.2, 10.3, 11.0), (11.0, 11.2, 9.6, 9.7)])
    st = S.fvg_state(S.fair_value_gaps_raw(df), df)
    assert st[0]["status"] == "inverted" and st[0]["inverted_kind"] == "bearish"
    assert st[0]["status_i"] == 4 and st[0]["mitigated_i"] == 3


def test_a_bearish_gap_closed_above_becomes_inverted_bullish_support():
    rows = [(10, 10.5, 10.0, 10.1), (10, 10.1, 8.5, 8.6), (8.6, 9.5, 8.0, 8.2),
            (8.2, 9.8, 8.1, 9.6),                       # wick into the band: mitigated
            (9.6, 10.4, 9.5, 10.3)]                     # CLOSE above 10.0: inverted
    df = _daily(rows)
    st = S.fvg_state(S.fair_value_gaps_raw(df), df)
    assert st[0]["kind"] == "bearish"
    assert st[0]["status"] == "inverted" and st[0]["inverted_kind"] == "bullish"


def test_fvg_state_survives_a_junk_frame():
    gaps = [{"kind": "bullish", "lo": 1, "hi": 2, "i": 2}]
    assert S.fvg_state(gaps, None)[0]["status"] == "active"
    assert S.fvg_state([{"kind": "bullish"}], _daily([(1, 2, 0, 1)] * 4))[0]["status"] == "active"


# ---------------------------------------------------------------------------
# consolidations
# ---------------------------------------------------------------------------
def test_a_tight_run_of_five_bars_is_a_consolidation():
    df = _daily(_flat(5, 100, 100.6, 99.8, 100.1) + [(100, 103, 99, 102.5)] * 2)
    out = S.consolidations(df, atr=1.0)
    assert len(out) == 1
    assert out[0]["start"] == 0 and out[0]["end"] == 4 and out[0]["bars"] == 5
    assert out[0]["lo"] == 99.8 and out[0]["hi"] == 100.6


def test_one_bar_too_wide_breaks_the_run():
    rows = _flat(4, 100, 100.6, 99.8, 100.1) + [(100, 102.5, 99.0, 101.0)] + _flat(4, 100, 100.6, 99.8, 100.1)
    df = _daily(rows)
    # 4 + wide + 4: neither side reaches CONSOL_MIN_BARS on its own
    assert S.consolidations(df, atr=1.0) == []
    # widen the tolerance and the same nine bars are one range
    assert len(S.consolidations(df, atr=1.0, max_atr=4.0)) == 1


def test_consolidations_need_an_atr():
    assert S.consolidations(_daily(_flat(5)), atr=None) == []   # 5 bars: no ATR14
    assert S.consolidations(None, atr=1.0) == []


# ---------------------------------------------------------------------------
# the manipulation (02:39) — wick through, close back
# ---------------------------------------------------------------------------
def test_a_wick_under_the_key_low_that_closes_back_above_is_a_manipulation():
    df = _daily(_flat(6) + [(100.0, 100.4, 98.9, 100.2)])
    m = S.manipulation(df, key_low=99.5, atr=1.0)
    assert m and m["i"] == 6 and m["side"] == "low" and m["bias"] == "bullish"
    assert m["extreme"] == 98.9 and m["displaced"] is False


def test_a_close_through_the_level_is_a_break_not_a_manipulation():
    df = _daily(_flat(6) + [(100.0, 100.4, 98.9, 99.1)])       # closes 0.4 under 99.5
    assert S.manipulation(df, key_low=99.5, atr=1.0) is None


def test_the_close_tolerance_is_an_owner_setting_defaulting_to_zero():
    assert S.DISPLACE_MAX_ATR == 0.0
    df = _daily(_flat(6) + [(100.0, 100.4, 98.9, 99.3)])
    assert S.manipulation(df, key_low=99.5, atr=1.0) is None
    assert S.manipulation(df, key_low=99.5, atr=1.0, close_tol_atr=0.5) is not None


def test_a_later_true_break_cancels_an_earlier_manipulation():
    df = _daily(_flat(6) + [(100.0, 100.4, 98.9, 100.2), (100, 100.3, 99.6, 100.0),
                            (100, 100.2, 98.5, 98.7)])
    assert S.manipulation(df, key_low=99.5, atr=1.0) is None


def test_the_mirror_manipulation_over_a_key_high():
    df = _daily(_flat(6) + [(100.0, 101.2, 99.8, 100.3)])
    m = S.manipulation(df, key_high=100.5, atr=1.0)
    assert m and m["side"] == "high" and m["bias"] == "bearish" and m["extreme"] == 101.2
    assert S.manipulation(df, key_high=100.5, atr=1.0, after=7) is None
    assert S.manipulation(df, atr=1.0) is None                  # no level, no answer


# ---------------------------------------------------------------------------
# Power of 3 (05:30)
# ---------------------------------------------------------------------------
def test_power_of_three_finds_the_range_then_the_sweep_under_it():
    df = _daily(_flat(6, 100, 100.6, 99.8, 100.1) + [(100.0, 100.4, 99.0, 100.0)])
    p3 = S.power_of_three(df, atr=1.0)
    assert p3 and p3["bias"] == "bullish"
    assert p3["accumulation"]["lo"] == 99.8 and p3["manipulation"]["i"] == 6


def test_power_of_three_is_none_while_the_range_is_still_forming():
    df = _daily(_flat(6, 100, 100.6, 99.8, 100.1))
    assert S.power_of_three(df, atr=1.0) is None


def test_power_of_three_bearish_is_the_mirror_and_direction_filters():
    df = _daily(_flat(6, 100, 100.6, 99.8, 100.1) + [(100.0, 101.4, 99.9, 100.3)])
    p3 = S.power_of_three(df, atr=1.0)
    assert p3 and p3["bias"] == "bearish" and p3["manipulation"]["extreme"] == 101.4
    assert S.power_of_three(df, atr=1.0, direction="bullish") is None


# ---------------------------------------------------------------------------
# opposite displacement that leaves a new gap
# ---------------------------------------------------------------------------
def _manip_then(tail):
    df = _daily(_flat(6) + [(100.2, 100.6, 99.5, 100.3)] + tail)
    return df, S.manipulation(df, key_low=100.0, atr=1.0)


def test_a_big_opposite_candle_that_leaves_a_gap_confirms():
    df, m = _manip_then([(100.3, 102.0, 100.2, 101.9), (101.8, 102.5, 101.0, 102.3)])
    d = S.opposite_displacement(df, m, atr=1.0)
    assert d and d["i"] == 7 and d["direction"] == "bullish" and d["atr_mult"] == 1.6
    assert d["fvg"]["lo"] == 100.6 and d["fvg"]["hi"] == 101.0


def test_a_big_candle_without_a_gap_does_not_confirm():
    df, m = _manip_then([(100.3, 102.0, 100.2, 101.9), (101.8, 102.5, 100.4, 102.3)])
    assert S.opposite_displacement(df, m, atr=1.0) is None


def test_a_small_candle_with_a_gap_does_not_confirm():
    df, m = _manip_then([(100.3, 101.0, 100.2, 100.8), (100.8, 101.2, 100.7, 101.0)])
    assert S.opposite_displacement(df, m, atr=1.0) is None      # body 0.5 < 1.0 ATR


def test_displacement_must_arrive_within_the_confirm_window():
    filler = [(100.3, 100.5, 100.1, 100.4)] * S.CONFIRM_MAX_BARS
    df, m = _manip_then(filler + [(100.4, 102.0, 100.3, 101.9), (101.9, 102.5, 101.0, 102.3)])
    assert S.opposite_displacement(df, m, atr=1.0) is None
    assert S.opposite_displacement(df, None, atr=1.0) is None


# ---------------------------------------------------------------------------
# MSS: the close beyond the last swing AND a new gap, within 1 bar
# ---------------------------------------------------------------------------
def _mss_frame(bar5_close=103.8, bar6=(103.5, 105.0, 103.0, 104.5)):
    rows = [(100, 101, 99, 100), (100, 103, 99.5, 102), (102, 102.5, 100, 100.5),
            (100.5, 101, 99, 99.5), (99.5, 100, 98.5, 99), (99, 104, 98.8, bar5_close), bar6]
    return _daily(rows)


def test_mss_is_the_cross_of_the_last_swing_with_a_gap_within_one_bar():
    df = _mss_frame()
    m = S.mss(df)
    # bar 5 crosses 103.0; its gap is only a fact once bar 6 prints, so the
    # MSS is labelled on bar 6 — the first bar on which both conditions hold
    assert m and m["i"] == 6 and m["cross_i"] == 5 and m["direction"] == "bullish"
    assert m["level"] == 103.0 and m["level_i"] == 1
    assert m["fvg"]["i"] == 6 and m["fvg"]["kind"] == "bullish"


def test_mss_never_reads_the_bar_after_the_one_it_labels():
    """Reviewer regression 2026-09-03: the first cut labelled the MSS on the
    crossing bar using the NEXT bar's low (the gap's third bar) — a
    look-ahead. The label must be prefix-stable: cutting the frame at the
    labelled bar still finds it, cutting one bar earlier finds nothing."""
    df = _mss_frame()
    assert S.mss(df.iloc[:7])["i"] == 6
    assert S.mss(df.iloc[:6]) is None                          # cross known, gap not yet


def test_a_gap_two_bars_after_the_cross_is_outside_the_window():
    assert S.MSS_FVG_WITHIN_BARS == 1
    rows = [(100, 101, 99, 100), (100, 103, 99.5, 102), (102, 102.5, 100, 100.5),
            (100.5, 101, 99, 99.5), (99.5, 100, 98.5, 99), (99, 104, 98.8, 103.8),
            (103.5, 104.2, 99.9, 104.0),                        # 6: no gap (low overlaps bar 4)
            (104.0, 105.5, 104.3, 105.0)]                       # 7: gap over bar 5 — two bars late
    assert S.mss(_daily(rows)) is None


def test_a_cross_and_gap_on_the_same_bar_are_labelled_on_that_bar():
    rows = [(100, 101, 99, 100), (100, 103, 99.5, 102), (102, 102.5, 100, 100.5),
            (100.5, 101, 99, 99.5), (99.5, 100, 98.5, 99), (99, 102, 98.8, 101.5),
            (101.5, 104.5, 101.2, 104.0)]                       # 6: closes over 103 AND lo > bar-4 high
    m = S.mss(_daily(rows))
    assert m and m["i"] == 6 and m["cross_i"] == 6 and m["fvg"]["i"] == 6


def test_a_cross_without_a_new_gap_is_not_an_mss():
    df = _mss_frame(bar6=(103.5, 105.0, 99.9, 104.5))           # bar 6 low overlaps bar 4
    assert S.mss(df) is None


def test_a_gap_without_the_cross_is_not_an_mss():
    df = _mss_frame(bar5_close=102.9, bar6=(102.9, 103.5, 102.5, 102.95))
    assert S.mss(df) is None


def test_mss_direction_and_after_filters():
    df = _mss_frame()
    assert S.mss(df, direction="bearish") is None
    assert S.mss(df, after=6) is None
    assert S.mss(None) is None


# ---------------------------------------------------------------------------
# stacked consolidations toward the HTF gap (03:57)
# ---------------------------------------------------------------------------
def _stack_frame(steps):
    rows = []
    for lo in steps:
        rows += _flat(5, lo + 0.3, lo + 0.9, lo, lo + 0.5)
        rows += [(lo, lo + 0.2, lo - 3.0, lo - 2.6)]           # the drop to the next shelf
    rows += [(88.0, 88.4, 87.6, 88.0)]
    return _daily(rows)


def test_two_or_more_ranges_stepping_down_to_the_gap_are_stacked():
    df = _stack_frame([100.0, 95.0, 90.0])
    gap = [{"kind": "bullish", "lo": 80.0, "hi": 82.0, "i": 1, "status": "active"}]
    st = S.stacked_consolidations(df, gap, atr=1.0)
    assert st["stacked"] is True and st["count"] == 3 and st["toward"] == "below"


def test_a_single_range_is_not_a_stack():
    df = _stack_frame([100.0])
    gap = [{"kind": "bullish", "lo": 80.0, "hi": 82.0, "i": 1, "status": "active"}]
    st = S.stacked_consolidations(df, gap, atr=1.0)
    assert st["stacked"] is False and st["count"] == 1


def test_ranges_beyond_the_gap_or_a_filled_gap_do_not_count():
    df = _stack_frame([100.0, 95.0, 90.0])
    beyond = [{"kind": "bullish", "lo": 96.0, "hi": 97.0, "i": 1, "status": "active"}]
    assert S.stacked_consolidations(df, beyond, atr=1.0)["count"] == 1    # only the 100 shelf is above it
    filled = [{"kind": "bullish", "lo": 80.0, "hi": 82.0, "i": 1, "status": "filled"}]
    assert S.stacked_consolidations(df, filled, atr=1.0)["stacked"] is False
    assert S.stacked_consolidations(df, [], atr=1.0)["count"] == 0
    assert S.stacked_consolidations(None, filled)["stacked"] is False


# ---------------------------------------------------------------------------
# engine — macro
# ---------------------------------------------------------------------------
def _macro_frame(last_low=99.5, n=80):
    rows = _flat(n)
    rows[40] = (100.0, 110.0, 99.5, 100.0)                     # a lone swing high
    rows[60] = (100.0, 100.5, 90.0, 100.0)                     # a lone swing low at 90
    rows[-1] = (100.0, 100.5, last_low, 100.0)
    return _daily(rows)


def test_macro_reads_key_levels_from_the_daily_swings():
    m = E.macro("aaa", df=_macro_frame())
    assert m["symbol"] == "AAA"
    assert m["key_low"] == 90.0 and m["key_high"] == 110.0
    assert {s["kind"] for s in m["swings"]} == {"swing_low", "swing_high"}
    assert m["tapped"] is None
    assert m["liquidity"]["avg_dollar_vol_50"] == pytest.approx(200_000_000.0)


def test_macro_marks_a_swept_daily_swing_low_as_tapped():
    m = E.macro("AAA", df=_macro_frame(last_low=90.1))          # within TAP_TOL_PCT of 90
    t = m["tapped"]
    assert t and t["kind"] == "swing_low" and t["price"] == 90.0 and t["bias"] == "bullish"
    assert t["bar_i"] == 79 and t["date"] == "2026-08-20"
    assert E.macro("AAA", df=_macro_frame(last_low=90.5))["tapped"] is None   # 0.55% away: no tap


def test_macro_marks_a_daily_gap_that_price_traded_into():
    rows = _flat(20) + [(100.0, 104.0, 100.0, 103.5), (103.0, 104.5, 102.0, 103.5)]
    rows += _flat(57, 103.5, 104.0, 103.0, 103.5) + [(103.5, 104.0, 101.8, 103.6)]
    m = E.macro("AAA", df=_daily(rows))
    t = m["tapped"]
    assert t and t["kind"] == "fvg" and t["bias"] == "bullish"
    assert t["lo"] == 100.5 and t["hi"] == 102.0


def test_macro_is_none_without_enough_bars_or_a_frame():
    assert E.macro("AAA", df=_daily(_flat(10))) is None
    assert E.macro("AAA", loader=lambda s: None) is None
    assert E.macro("AAA", loader=lambda s: (_ for _ in ()).throw(RuntimeError("x"))) is None


# ---------------------------------------------------------------------------
# engine — micro state machine, grade, plan
# ---------------------------------------------------------------------------
def test_micro_walks_accumulation_manipulation_confirmed_entry():
    df = _micro_entry_frame()
    mi = E.micro("AAA", "60m", df=df, macro_ctx=_macro_ctx())
    assert mi["bias"] == "bullish" and mi["state"] == "entry" and mi["grade"] == 100
    assert mi["accumulation"]["lo"] == 99.5 and mi["accumulation"]["hi"] == 100.5
    assert mi["manipulation"]["low"] == 98.5 and mi["manipulation"]["displaced"] is False
    assert mi["manipulation"]["date"] == _et_date(df.index[25])
    assert mi["displacement"]["atr_mult"] >= 1.0
    assert mi["mss"]["level"] == 100.5 and mi["mss"]["date"] == _et_date(df.index[27])
    assert mi["fvg"]["lo"] == 100.2 and mi["fvg"]["hi"] == 101.0
    assert mi["ifvg"] is None
    assert "no displacement" in mi["why"] and "MSS" in mi["why"]


def test_micro_plan_math_uses_the_zone_edge_the_sweep_and_the_next_daily_swing():
    df = _micro_entry_frame()
    mi = E.micro("AAA", "60m", df=df, macro_ctx=_macro_ctx())
    a = S.atr14(df)
    p = mi["plan"]
    assert p["entry_lo"] == 100.2 and p["entry_hi"] == 101.0 and p["entry"] == 101.0
    assert p["stop"] == pytest.approx(98.5 - E.STOP_BUFFER_ATR * a, abs=1e-4)
    # Owner rule MIN_TARGET_R (2026-09-04): 103.0 is the nearest swing high but
    # pays < 1R against this stop, so the target steps to the next one, 105.
    assert 103.0 - 101.0 < E.MIN_TARGET_R * (101.0 - p["stop"])
    assert p["target"] == 105.0
    assert p["rr"] == pytest.approx((105.0 - 101.0) / (101.0 - p["stop"]), abs=0.01)
    assert p["zone"] == "fvg"


def test_micro_stops_at_confirmed_when_price_has_left_the_zone():
    df = _micro_entry_frame()
    df.iloc[-1, df.columns.get_loc("close")] = 102.9            # 1.9% above the gap top
    mi = E.micro("AAA", "60m", df=df, macro_ctx=_macro_ctx())
    assert mi["state"] == "confirmed" and mi["grade"] == 80


def test_micro_stops_at_manipulation_when_nothing_confirms():
    df = _micro_entry_frame().iloc[:26]                        # ends on the sweep bar
    df = pd.concat([_hourly(_accumulation(6), start="2026-08-03"), df])   # keep >= MICRO_MIN_BARS
    mi = E.micro("AAA", "60m", df=df, macro_ctx=_macro_ctx())
    assert mi["state"] == "manipulation" and mi["grade"] == 30
    assert mi["mss"] is None and mi["plan"] is None


def test_micro_reports_accumulation_when_there_is_no_sweep_yet():
    df = _hourly(_accumulation(34))
    mi = E.micro("AAA", "60m", df=df, macro_ctx=_macro_ctx())
    assert mi["state"] == "accumulation" and mi["grade"] == 0
    assert mi["manipulation"] is None and "no sweep yet" in mi["why"]


def test_micro_inverted_fvg_is_the_entry_zone():
    df = _micro_ifvg_frame()
    mi = E.micro("AAA", "60m", df=df, macro_ctx=_macro_ctx(tapped_price=97.5))
    assert mi["state"] == "entry" and mi["bias"] == "bullish"
    assert mi["ifvg"] and mi["ifvg"]["lo"] == 98.9 and mi["ifvg"]["hi"] == 99.6
    assert mi["ifvg"]["date"] == _et_date(df.index[29])
    assert mi["plan"]["zone"] == "ifvg" and mi["plan"]["entry"] == 99.6
    assert mi["mss"]["date"] == _et_date(df.index[30])


def test_micro_is_none_on_short_or_junk_frames():
    assert E.micro("AAA", "60m", df=_hourly(_accumulation(10))) is None
    assert E.micro("AAA", "60m", df=None, loader=lambda s, tf: None) is None
    assert E.micro("AAA", "60m", loader=lambda s, tf: (_ for _ in ()).throw(RuntimeError("x"))) is None


def test_sort_rows_is_state_then_grade():
    rows = [{"symbol": "A", "state": "accumulation", "grade": 0},
            {"symbol": "B", "state": "confirmed", "grade": 60},
            {"symbol": "C", "state": "entry", "grade": 80},
            {"symbol": "D", "state": "confirmed", "grade": 80},
            {"symbol": "E", "state": "manipulation", "grade": 50}]
    assert [r["symbol"] for r in E.sort_rows(rows)] == ["C", "D", "B", "E", "A"]


# ---------------------------------------------------------------------------
# engine — scan: the dormant loop, caps, budget, persistence
# ---------------------------------------------------------------------------
class FakeColl:
    def __init__(self):
        self.docs: dict = {}

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)

    def find_one(self, q):
        d = self.docs.get(q.get("_id"))
        return dict(d) if d else None

    def delete_many(self, q):
        date_lt = (q.get("date") or {}).get("$lt")
        nin = set((q.get("_id") or {}).get("$nin") or [])
        gone = [k for k, d in self.docs.items()
                if k not in nin and date_lt and (d.get("date") or "") < date_lt]
        for k in gone:
            del self.docs[k]

        class _R:
            deleted_count = len(gone)
        return _R()


def _loaders(tapped=("TAP",), untapped=("NOT",)):
    daily = {s: _macro_frame(last_low=90.1) for s in tapped}
    daily.update({s: _macro_frame() for s in untapped})
    micro_calls: list = []

    def dl(sym):
        return daily.get(sym)

    def ml(sym, tf):
        micro_calls.append((sym, tf))
        return _micro_entry_frame()

    return dl, ml, micro_calls


def test_the_micro_loop_stays_dormant_for_untapped_names():
    dl, ml, calls = _loaders()
    out = E.scan(["TAP", "NOT", "tap"], daily_loader=dl, micro_loader=ml, persist=False)
    assert out["macro_n"] == 2 and out["tapped_n"] == 1 and out["micro_n"] == 1
    assert calls == [("TAP", "60m")]                            # NOT never loaded an intraday frame
    assert out["truncated"] is False
    assert [r["symbol"] for r in out["rows"]] == ["TAP"]
    row = out["rows"][0]
    assert row["state"] == "entry" and row["bias"] == "bullish" and row["grade"] == 100
    assert row["macro"]["tapped"]["kind"] == "swing_low"
    assert row["liquidity"]["avg_dollar_vol_50"] > 0 and row["plan"]["stop"] < 98.5
    assert set(out) >= {"as_of", "date", "macro_n", "tapped_n", "micro_n", "rows", "seconds",
                        "truncated", "micro_tf", "params", "source"}


def test_micro_max_caps_the_loop_and_flags_truncation():
    dl, ml, calls = _loaders(tapped=("T1", "T2", "T3"))
    out = E.scan(["T1", "T2", "T3", "NOT"], daily_loader=dl, micro_loader=ml,
                 micro_max=1, persist=False)
    assert out["tapped_n"] == 3 and out["micro_n"] == 1 and len(calls) == 1
    assert out["truncated"] is True


def test_a_spent_budget_flags_truncation_instead_of_pretending():
    dl, ml, calls = _loaders(tapped=("T1", "T2"))
    out = E.scan(["T1", "T2", "NOT"], daily_loader=dl, micro_loader=ml,
                 budget_sec=-1, persist=False)
    assert out["truncated"] is True
    assert out["micro_n"] == 0 and calls == []


def test_scan_persists_latest_plus_a_dated_copy_and_purges_old_ones():
    dl, ml, _ = _loaders()
    coll = FakeColl()
    coll.docs["2026-08-01:1000:60m"] = {"_id": "2026-08-01:1000:60m", "date": "2026-08-01"}
    coll.docs["latest"] = {"_id": "latest", "date": "2026-08-01", "rows": []}
    now = datetime(2026, 9, 3, 10, 15, tzinfo=ET)
    out = E.scan(["TAP", "NOT"], daily_loader=dl, micro_loader=ml, coll=coll, now=now)
    assert out["as_of"].startswith("2026-09-03T10:15")
    assert coll.docs["latest"]["date"] == "2026-09-03"          # replaced, never purged
    assert "2026-09-03:1015:60m" in coll.docs
    assert "2026-08-01:1000:60m" not in coll.docs               # older than KEEP_DAYS
    assert coll.docs["latest"]["rows"][0]["symbol"] == "TAP"


def _daily_end(rows, end="2026-09-03"):
    idx = pd.bdate_range(end=end, periods=len(rows))
    return pd.DataFrame({"open": [r[0] for r in rows], "high": [r[1] for r in rows],
                         "low": [r[2] for r in rows], "close": [r[3] for r in rows],
                         "volume": [2_000_000.0] * len(rows)}, index=idx)


def test_micro_cap_prefers_todays_tap_over_yesterdays_on_a_longer_frame():
    """Reviewer regression 2026-09-03: the cap was ordered by `bar_i`, an
    iloc into each name's OWN frame — a two-day-old tap on a 2y frame
    outranked today's tap on a short listing. Order by the tap's date."""
    short = _flat(80)
    short[40] = (100.0, 110.0, 99.5, 100.0)
    short[60] = (100.0, 100.5, 90.0, 100.0)
    short[-1] = (100.0, 100.5, 90.1, 100.0)                    # SHORT taps today
    long_ = _flat(120)
    long_[40] = (100.0, 110.0, 99.5, 100.0)
    long_[60] = (100.0, 100.5, 90.0, 100.0)
    long_[-2] = (100.0, 100.5, 90.1, 100.0)                    # LONG tapped yesterday
    frames = {"SHORT": _daily_end(short), "LONG": _daily_end(long_)}
    calls: list = []

    def ml(sym, tf):
        calls.append((sym, tf))
        return _micro_entry_frame()

    out = E.scan(["LONG", "SHORT"], daily_loader=lambda s: frames.get(s), micro_loader=ml,
                 micro_max=1, persist=False)
    assert out["tapped_n"] == 2 and out["truncated"] is True
    assert calls == [("SHORT", "60m")]


def test_a_name_missing_from_the_bulk_snapshot_stays_on_closed_bars(monkeypatch):
    """Reviewer regression 2026-09-03: `with_today_bar(df, sym, snap=None)`
    fetches its own snapshot, and the bulk call omits errored / unmapped
    tickers — so the first cut paid one HTTP call per missing name from
    inside the macro thread pool. Missing from the bulk = closed bars."""
    frames = {"TAP": _macro_frame(last_low=90.1), "NOT": _macro_frame()}
    overlay_calls: list = []

    class _P:
        PERIOD_DAYS = {"2y": 504}

        @staticmethod
        def load_prices(symbol, *a, **kw):
            return frames.get(symbol.upper())

        @staticmethod
        def with_today_bar(df, symbol, snap=None):
            overlay_calls.append((symbol, snap))
            assert snap, "with_today_bar without a snap fetches its own — one HTTP per name"
            return df, {"appended": False}

        @staticmethod
        def bulk_snapshot(syms):
            return {"TAP": {"open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0,
                            "volume": 1.0, "date": "2026-09-03"}}

    mod = _P()
    monkeypatch.setitem(sys.modules, "sepa.prices", mod)
    import sepa
    monkeypatch.setattr(sepa, "prices", mod, raising=False)
    _dl, ml, micro_calls = _loaders()
    out = E.scan(["TAP", "NOT"], micro_loader=ml, persist=False)
    assert out["macro_n"] == 2 and micro_calls == [("TAP", "60m")]
    assert [c[0] for c in overlay_calls] == ["TAP"]             # NOT: no snap, no overlay, no HTTP
    assert E._load_daily("NOT", snap=None, overlay=True) is frames["NOT"]
    assert len(overlay_calls) == 1


def test_scan_tolerates_a_dead_loader_and_an_empty_universe():
    out = E.scan([], daily_loader=lambda s: None, micro_loader=lambda s, tf: None, persist=False)
    assert out["macro_n"] == 0 and out["rows"] == []
    out = E.scan(["X"], daily_loader=lambda s: (_ for _ in ()).throw(RuntimeError("boom")),
                 micro_loader=lambda s, tf: None, persist=False)
    assert out["macro_n"] == 0 and out["truncated"] is False


# ---------------------------------------------------------------------------
# engine — cached_or_warm never blocks
# ---------------------------------------------------------------------------
def _latest_doc(as_of, rows=None):
    return {"_id": "latest", "as_of": as_of, "date": as_of[:10], "macro_n": 5, "tapped_n": 2,
            "micro_n": 2, "rows": rows or [{"symbol": "AAA", "state": "entry", "grade": 90}],
            "seconds": 3, "truncated": False, "micro_tf": "60m"}


def test_a_fresh_doc_is_served_from_cache(monkeypatch):
    monkeypatch.setattr(E, "scan", lambda **k: pytest.fail("a fresh cache must not scan"))
    coll = FakeColl()
    now = datetime(2026, 9, 3, 10, 20, tzinfo=ET)
    coll.docs["latest"] = _latest_doc("2026-09-03T10:15:00-04:00")
    out = E.cached_or_warm(coll=coll, now=now)
    assert out["cached"] is True and out["warming"] is False
    assert out["rows"][0]["symbol"] == "AAA" and out["stale_sec"] == 300
    assert out["params"] and out["source"]["video"] == S.VIDEO_URL


def test_a_stale_doc_is_served_while_a_background_scan_runs(monkeypatch):
    started = threading.Event()
    seen: list = []

    def fake_scan(**kw):
        seen.append(kw)
        started.set()
        time.sleep(0.2)

    monkeypatch.setattr(E, "scan", fake_scan)
    E._warming.clear()
    coll = FakeColl()
    now = datetime(2026, 9, 3, 10, 40, tzinfo=ET)
    coll.docs["latest"] = _latest_doc("2026-09-03T10:15:00-04:00")   # 25 min > ICT_TTL_SEC
    t0 = time.time()
    out = E.cached_or_warm(limit=5, coll=coll, now=now)
    assert time.time() - t0 < 0.15, "cached_or_warm blocked on the scan"
    assert out["warming"] is True and out["cached"] is True
    assert out["rows"][0]["symbol"] == "AAA"                      # stale rows still served
    assert started.wait(2.0) and seen[0]["micro_tf"] == "60m"
    E._last_warm_thread.join(2.0)
    assert "60m" not in E._warming


def test_one_warm_at_a_time(monkeypatch):
    gate = threading.Event()
    calls: list = []

    def fake_scan(**kw):
        calls.append(kw)
        gate.wait(2.0)

    monkeypatch.setattr(E, "scan", fake_scan)
    E._warming.clear()
    coll = FakeColl()
    E.cached_or_warm(coll=coll)
    E.cached_or_warm(coll=coll)
    time.sleep(0.05)
    assert len(calls) == 1
    gate.set()
    E._last_warm_thread.join(2.0)


def test_no_store_means_no_warm_and_an_honest_note(monkeypatch):
    monkeypatch.setattr(E, "scan", lambda **k: pytest.fail("no store, no scan"))
    monkeypatch.setattr(E, "_coll", lambda coll=None: None)
    out = E.cached_or_warm()
    assert out["warming"] is False and out["rows"] == [] and "unavailable" in out["note"]


def test_an_empty_store_warms_and_answers_empty(monkeypatch):
    started = threading.Event()
    monkeypatch.setattr(E, "scan", lambda **k: started.set())
    E._warming.clear()
    out = E.cached_or_warm(coll=FakeColl())
    assert out["warming"] is True and out["cached"] is False and out["rows"] == []
    assert started.wait(2.0)
    E._last_warm_thread.join(2.0)


# ---------------------------------------------------------------------------
# board — tiles
# ---------------------------------------------------------------------------
@pytest.fixture
def prices(monkeypatch):
    store: dict = {}

    class _Prices:
        PERIOD_DAYS = {"2y": 504}

        @staticmethod
        def load_prices(symbol, *a, **kw):
            return store.get(symbol.upper())

    mod = _Prices()
    monkeypatch.setitem(sys.modules, "sepa.prices", mod)
    import sepa
    monkeypatch.setattr(sepa, "prices", mod, raising=False)
    return store


def _entry_row(symbol="AAA", bias="bullish"):
    df = _micro_entry_frame() if bias == "bullish" else _micro_entry_frame()
    mi = E.micro(symbol, "60m", df=df, macro_ctx=_macro_ctx())
    m = dict(_macro_ctx(), symbol=symbol, fvgs=[
        {"kind": "bullish", "lo": 95.0, "hi": 96.0, "status": "active", "date": "2026-08-20"},
        {"kind": "bearish", "lo": 104.0, "hi": 105.0, "status": "inverted", "inverted_kind": "bullish"},
        {"kind": "bullish", "lo": 90.0, "hi": 91.0, "status": "filled"}])
    row = E._row(m, mi)
    row["bias"] = bias
    return row


def test_ict_tile_geometry(prices, monkeypatch):
    from ict import engine as IE
    row = _entry_row()
    prices["AAA"] = _daily(_flat(200))
    monkeypatch.setattr(IE, "cached_or_warm", lambda limit=None, **kw: {
        "rows": [row], "warming": False, "cached": True, "as_of": "2026-09-03T10:15:00-04:00",
        "macro_n": 1100, "tapped_n": 12, "micro_n": 12, "truncated": False})
    out = B.board("ict", limit=5, min_tier="any")
    assert out["tab"] == "ict" and out["count"] == 1
    t = out["tiles"][0]
    assert t["href"] == "/sepa/AAA?tab=supply"
    labels = {(b["kind"], b["label"]) for b in t["bands"]}
    assert ("base", "accumulation") in labels
    assert ("demand", "FVG") in labels and ("demand", "entry") in labels
    assert ("demand", "daily FVG") in labels and ("neutral", "IFVG (daily)") in labels
    assert not any(b["lo"] == 90.0 for b in t["bands"])          # the filled daily gap is not drawn
    tones = {l["tone"] for l in t["lines"]}
    assert tones == {"stop", "target", "neutral", "now"}
    assert {l["label"] for l in t["lines"] if l["tone"] == "neutral"} == {"key low 97.00", "key high 103.00"}
    kinds = {m["kind"]: m for m in t["markers"]}
    assert set(kinds) == {"sweep", "bos", "buy"}
    assert kinds["sweep"]["label"] == "MANIP" and kinds["bos"]["label"] == "MSS"
    assert kinds["buy"]["label"] == "ENTRY"                       # no IFVG: the FVG retest is the entry
    mdf = _micro_entry_frame()
    assert kinds["sweep"]["date"] == _et_date(mdf.index[25])
    assert kinds["bos"]["date"] == _et_date(mdf.index[26])
    assert [s["k"] for s in t["stats"]][:6] == ["State", "Grade", "R:R", "Bias", "Micro tf", "Tapped"]
    texts = [b["text"] for b in t["badges"]]
    assert "MSS ✓" in texts and "no displacement ✓" in texts and "at entry zone" in texts
    assert "_score" not in t and "_m" not in t
    # the envelope
    assert out["counts"] == {"macro_n": 1100, "tapped_n": 12, "micro_n": 12, "rows": 1, "matched": 1}
    assert out["source"]["video"] == S.VIDEO_URL and any("02:39" in s for s in out["source"]["timestamps"])
    keys = {p["key"] for p in out["params"]}
    assert {"CONSOL_MIN_BARS", "DISPLACE_MAX_ATR", "TAP_TOL_PCT", "ENTRY_TOL_PCT",
            "STOP_BUFFER_ATR", "MICRO_MAX", "BUDGET_SEC", "ICT_TTL_SEC"} <= keys
    assert all("not from the video" in p["note"] for p in out["params"] if not p["from_video"])
    assert out["warming"] is False and out["generated_at"] == "2026-09-03T10:15:00-04:00"
    assert out["micro"] == "60m" and out["bias"] == "all"


def test_ict_ifvg_row_draws_the_buy_marker_on_the_inversion_date(prices, monkeypatch):
    from ict import engine as IE
    df = _micro_ifvg_frame()
    mi = E.micro("BBB", "60m", df=df, macro_ctx=_macro_ctx(tapped_price=97.5))
    row = E._row(dict(_macro_ctx(), symbol="BBB", fvgs=[]), mi)
    prices["BBB"] = _daily(_flat(200))
    monkeypatch.setattr(IE, "cached_or_warm", lambda limit=None, **kw: {"rows": [row], "warming": False})
    t = B.board("ict", limit=5, min_tier="any")["tiles"][0]
    kinds = {m["kind"]: m for m in t["markers"]}
    assert kinds["buy"]["label"] == "IFVG" and kinds["buy"]["date"] == _et_date(df.index[29])
    assert ("neutral", "IFVG") in {(b["kind"], b["label"]) for b in t["bands"]}
    assert "IFVG" in [b["text"] for b in t["badges"]]


def test_ict_bias_filter_and_bearish_marker_kind(prices, monkeypatch):
    from ict import engine as IE
    bull, bear = _entry_row("AAA", "bullish"), _entry_row("CCC", "bearish")
    bear["micro"]["ifvg"] = {"lo": 101.0, "hi": 101.5, "date": "2026-08-21", "at": "x"}
    prices["AAA"] = _daily(_flat(200))
    prices["CCC"] = _daily(_flat(200))
    monkeypatch.setattr(IE, "cached_or_warm", lambda limit=None, **kw: {"rows": [bull, bear], "warming": False})
    assert {t["symbol"] for t in B.board("ict", limit=5, min_tier="any")["tiles"]} == {"AAA", "CCC"}
    out = B.board("ict", limit=5, min_tier="any", bias="bearish")
    assert [t["symbol"] for t in out["tiles"]] == ["CCC"] and out["bias"] == "bearish"
    t = out["tiles"][0]
    assert ("supply", "entry") in {(b["kind"], b["label"]) for b in t["bands"]}
    assert {m["kind"] for m in t["markers"]} >= {"sell"}
    assert B.board("ict", limit=5, min_tier="any", bias="nonsense")["bias"] == "all"


def test_ict_liquidity_floor_reads_the_daily_dollar_volume(prices, monkeypatch):
    from ict import engine as IE
    thin = _entry_row("THN")
    thin["liquidity"] = {"avg_dollar_vol_50": 1_000_000.0}
    deep = _entry_row("DEP")
    prices["THN"] = _daily(_flat(200))
    prices["DEP"] = _daily(_flat(200))
    monkeypatch.setattr(IE, "cached_or_warm", lambda limit=None, **kw: {"rows": [thin, deep], "warming": False})
    out = B.board("ict", limit=5)                                # default tier "ok" = $10M
    assert [t["symbol"] for t in out["tiles"]] == ["DEP"] and out["dropped_thin"] == 1


def test_ict_warming_and_empty_boards_say_so(prices, monkeypatch):
    from ict import engine as IE
    monkeypatch.setattr(IE, "cached_or_warm", lambda limit=None, **kw: {"rows": [], "warming": True})
    out = B.board("ict")
    assert out["tiles"] == [] and out["warming"] is True and "first ICT scan" in out["note"]
    monkeypatch.setattr(IE, "cached_or_warm", lambda limit=None, **kw: {"rows": [], "warming": False})
    assert "dormant" in B.board("ict")["note"]


def test_ict_micro_param_is_forwarded_and_junk_falls_back(prices, monkeypatch):
    from ict import engine as IE
    seen: list = []

    def fake(limit=None, **kw):
        seen.append(kw.get("micro_tf"))
        return {"rows": [], "warming": False}

    monkeypatch.setattr(IE, "cached_or_warm", fake)
    assert B.board("ict", micro="15m")["micro"] == "15m"
    assert B.board("ict", micro="7m")["micro"] == "60m"
    assert seen == ["15m", "60m"]


def test_tiles_from_rows_is_pure_and_skips_blank_symbols():
    rows = [{"symbol": "", "bias": "bullish"}, {"symbol": "aaa", "bias": "bullish", "grade": 40}]
    tiles = IB.tiles_from_rows(rows, href=lambda s, t: f"/{s}/{t}", name_for=lambda s: None,
                               theme=lambda s: None, metrics=lambda r: {"avg_turnover": None})
    assert [t["symbol"] for t in tiles] == ["AAA"] and tiles[0]["_score"] == 40.0
    assert tiles[0]["markers"] == [] and tiles[0]["lines"] == []


# ---------------------------------------------------------------------------
# wiring: TABS, api params, crontab
# ---------------------------------------------------------------------------
def test_ict_is_a_tab_and_supply_still_resolves():
    assert "ict" in B.TABS and "supply" in B.TABS
    assert B.TABS.index("ict") == B.TABS.index("supply") + 1


def test_api_accepts_bias_and_micro_and_forwards_them():
    import inspect
    from chart_maps import api as cm_api
    sig = inspect.signature(cm_api.chart_maps).parameters
    assert "bias" in sig and "micro" in sig
    src = inspect.getsource(cm_api.chart_maps)
    assert "bias=bias" in src and "micro=micro" in src
    assert "ict" in src


def test_crontab_runs_the_engine_every_fifteen_minutes_and_after_the_close():
    cron = (ROOT / "backend/crontab").read_text()
    lines = [l for l in cron.splitlines() if "ict.engine" in l and not l.startswith("#")]
    assert len(lines) == 2
    assert lines[0].split()[:5] == ["*/15", "9-16", "*", "*", "1-5"]
    assert lines[1].split()[:5] == ["50", "16", "*", "*", "1-5"]
    assert all(l.rstrip().endswith("/usr/local/bin/python -m ict.engine") for l in lines)


# ---------------------------------------------------------------------------
# source discipline
# ---------------------------------------------------------------------------
def test_ict_sources_cite_the_video_and_nothing_else():
    files = sorted((ROOT / "backend/ict").glob("*.py"))
    assert len(files) == 4
    for f in files:
        src = f.read_text()
        assert S.VIDEO_URL in src, f"{f.name} must carry the video URL"
        for banned in ("TLSW", "TTLAC", "Minervini"):
            assert banned not in src, f"{f.name} imports a SEPA cite: {banned}"
        assert re.search(r"\bpp?\.\s?\d", src) is None, f"{f.name} carries a page cite"
        assert re.search(r"\b(ema|sma|vwap)\b", src, re.IGNORECASE) is None, \
            f"{f.name} references a moving average"
    assert "02:39" in (ROOT / "backend/ict/structure.py").read_text()
    assert "05:30" in (ROOT / "backend/ict/structure.py").read_text()
    assert "03:57" in (ROOT / "backend/ict/structure.py").read_text()


def test_every_owner_constant_is_marked_and_the_video_ones_are_the_only_exceptions():
    ps = E.params()
    keys = {p["key"] for p in ps}
    assert set(S.PARAMS) <= keys and set(E._ENGINE_PARAMS) <= keys
    for p in ps:
        if p["from_video"]:
            assert p["key"] in S.FROM_VIDEO
        else:
            assert p["note"] == "owner rule — not from the video"
    src = (ROOT / "backend/ict/structure.py").read_text()
    for k in S.PARAMS:
        if k not in S.FROM_VIDEO:
            line = next(l for l in src.splitlines() if l.startswith(f"{k} ="))
            assert "owner rule" in line, f"{k} is not marked as an owner rule in code"
    doc = (ROOT / "docs/ict/ict_chart_maps.md").read_text()
    for k in list(S.PARAMS) + list(E._ENGINE_PARAMS):
        assert k in doc, f"docs/ict/ict_chart_maps.md does not list {k}"
    assert S.VIDEO_URL in doc and "not from the video" in doc


# ---------------------------------------------------------------------------
# 2026-09-04 fixes after the first live seed (tapped 1,122 of 1,123 names,
# 60m frames ~20 s each, R:R 0.01 targets)
# ---------------------------------------------------------------------------
def test_tap_must_be_a_fresh_touch_not_a_name_already_through_the_level():
    """The bar BEFORE the tap must still be on the far side of the level."""
    base = _flat(30, 100.0, 100.5, 99.5, 100.0)
    swing = [(100.0, 100.5, 90.0, 100.0)]                    # fractal low at 90
    body = _flat(40, 100.0, 100.5, 99.5, 100.0)
    fresh = _daily(base + swing + body + [(100.0, 100.5, 89.9, 100.0)])
    t = E.macro("AAA", df=fresh)["tapped"]
    assert t and t["kind"] == "swing_low" and t["price"] == 90.0
    # four sessions sitting at/under the level: nothing is "reaching" it
    stale = _daily(base + swing + body + _flat(4, 100.0, 100.5, 89.9, 100.0))
    assert E.macro("AAA", df=stale)["tapped"] is None


def test_plan_has_no_target_when_no_daily_swing_pays_min_target_r():
    read = {"bias": "bullish", "manipulation": {"extreme": 98.5},
            "fvg": {"lo": 100.2, "hi": 101.0}, "ifvg": None}
    ctx = {"swings": [{"kind": "swing_high", "price": 101.4},
                      {"kind": "swing_high", "price": 101.9}]}
    p = E._plan(read, ctx, a=1.0)
    assert p["target"] is None and p["rr"] is None
    ctx["swings"].append({"kind": "swing_high", "price": 108.0})
    p = E._plan(read, ctx, a=1.0)
    assert p["target"] == 108.0 and p["rr"] > 1.0


def test_micro_raw_window_is_micro_days_plus_weekend_padding():
    from datetime import date, timedelta
    start, end = E.micro_raw_window(date(2026, 9, 4))
    assert end == date(2026, 9, 4) and (end - start) == timedelta(days=E.MICRO_DAYS + 4)
    assert E.MICRO_DAYS < 70, "must be cheaper than frame_for's own 70-day span"
    keys = {x["key"] for x in E.params()}
    assert {"MICRO_DAYS", "MIN_TARGET_R"} <= keys


def test_tap_listens_to_window_swings_not_every_fractal_wiggle():
    """A 1-bar fractal low that is NOT a +/-TAP_SWING_WINDOW extremum does not
    wake the micro loop; a real structural low does. Fractals remain the
    swings/targets list."""
    base = _flat(30, 100.0, 100.5, 99.5, 100.0)
    deep = [(100.0, 100.5, 94.0, 100.0)]                       # bar 30: window-3 swing low at 94
    mid = _flat(2, 100.0, 100.5, 99.5, 100.0)
    wiggle = [(100.0, 100.5, 95.0, 100.0)]                     # bar 33: fractal low, but 94 sits 3 bars back
    body = _flat(40, 100.0, 100.5, 99.5, 100.0)
    touch_wiggle = _daily(base + deep + mid + wiggle + body + [(100.0, 100.5, 94.95, 100.0)])
    m = E.macro("AAA", df=touch_wiggle)
    assert any(s["kind"] == "swing_low" and s["price"] == 95.0 for s in m["swings"]), "fractal kept as a swing"
    assert m["tapped"] is None, "a fractal wiggle is not a key structural low"
    touch_deep = _daily(base + deep + mid + wiggle + body + [(100.0, 100.5, 93.9, 100.0)])
    t = E.macro("AAA", df=touch_deep)["tapped"]
    assert t and t["kind"] == "swing_low" and t["price"] == 94.0
    assert "TAP_SWING_WINDOW" in {x["key"] for x in E.params()}


def test_strict_window_swings_ignore_plateaus_and_match_the_fractal_at_window_1():
    rows = _flat(10, 100.0, 100.5, 99.5, 100.0)
    rows[5] = (100.0, 100.5, 95.0, 100.0)
    df = _daily(rows)
    lows, highs = S.swing_points_strict(df, 3)
    assert lows == [(5, 95.0)] and highs == []                  # the flat 99.5 plateau is not a swing
    f_lows, f_highs = S.swing_points_fractal(df)
    assert S.swing_points_strict(df, 1)[0] == f_lows and S.swing_points_strict(df, 1)[1] == f_highs
    assert S.swing_points_strict(None, 3) == ([], []) and S.swing_points_strict(df, 0) == ([], [])


def test_gap_tap_is_the_first_touch_only():
    """A daily gap wakes the loop on the bar that first trades into it; a
    later re-touch (even from outside) does not."""
    rows = _flat(20) + [(100.0, 104.0, 100.0, 103.5), (103.0, 104.5, 102.0, 103.5)]
    rows += _flat(57, 103.5, 104.0, 103.0, 103.5) + [(103.5, 104.0, 101.8, 103.6)]
    first = E.macro("AAA", df=_daily(rows))["tapped"]
    assert first and first["kind"] == "fvg" and first["gap_status"] == "mitigated"
    again = rows + [(103.5, 104.0, 103.0, 103.5), (103.5, 104.0, 101.9, 103.6)]
    assert E.macro("AAA", df=_daily(again))["tapped"] is None


def test_inverted_gap_taps_on_its_first_retest_only():
    """bearish gap [100.5, 102] inverted by a close above 102; the first bar
    trading back into it taps, the next re-touch does not."""
    rows = _flat(20) + [(103.5, 104.0, 102.0, 102.5), (102.0, 102.5, 101.0, 101.2),
                        (101.0, 101.2, 99.5, 100.5)]                    # bearish gap: High[i+2]=101.2 < Low[i]=102 ... build simply
    rows = _flat(20) + [(103.0, 103.5, 102.0, 102.2), (102.0, 102.4, 101.6, 101.8), (101.5, 100.5, 99.0, 99.4)]
    gaps = S.fair_value_gaps_raw(_daily(rows))
    assert gaps and gaps[-1]["kind"] == "bearish", gaps
    g_lo, g_hi = gaps[-1]["lo"], gaps[-1]["hi"]
    rows += _flat(30, 99.5, 99.9, 99.0, 99.5)
    rows += [(99.5, g_hi + 1.0, 99.4, g_hi + 0.8)]                      # close above the gap top -> inverted
    rows += _flat(20, g_hi + 0.6, g_hi + 0.9, g_hi + 0.4, g_hi + 0.6)   # sitting above it (highs well under the old 103.5 swing)
    retest = rows + [(g_hi + 0.6, g_hi + 0.8, g_hi - 0.2, g_hi + 0.5)]  # first retest into the gap
    t = E.macro("AAA", df=_daily(retest))["tapped"]
    assert t and t["kind"] == "fvg" and t["gap_status"] == "inverted" and t["bias"] == "bullish"
    again = retest + [(g_hi + 0.6, g_hi + 0.9, g_hi + 0.4, g_hi + 0.6), (g_hi + 0.6, g_hi + 0.8, g_hi - 0.2, g_hi + 0.5)]
    assert E.macro("AAA", df=_daily(again))["tapped"] is None

