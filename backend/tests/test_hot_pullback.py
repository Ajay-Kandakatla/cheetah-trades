"""🔥 Hot Pullback board + paper lane (2026-09-09).

Ajay asked for "a new tab for hot pull back like 21 day moving average drops but
have a reversal from demand zones ... like DYN today which bounced back quick",
then "make sure we paper trade this in autopilot too".

The DYN 2026-09-08 archetype is the fixture throughout, because it is the bar he
pointed at and every number in it was measured by hand first:
    prev close 24.28 -> open 17.08 -> low 17.00 -> close 20.31
    the low landed inside a 4-touch demand band 16.56-17.02
    -36.3% off the prior 10-day high, -20.6% under the 21-day line,
    +19.5% off the low, 85% up the day's range.

What these pin, because getting any of it wrong costs real money:
  1. all four parts of the rule are REQUIRED, and each failure is named;
  2. a PROVEN band is NOT required — requiring one measured worse;
  3. the study numbers on the payload are the ones the study produced;
  4. the lane exits on the CLOCK, because the edge dies by day 5;
  5. the lane refuses a live broker.
"""
import importlib
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

HP = importlib.import_module("supply_demand.hot_pullback")
HPE = importlib.import_module("trading.hot_pullback_entry")

ET = ZoneInfo("America/New_York")

# the archetype
DYN_CLOSE, DYN_LOW, DYN_HIGH = 20.31, 17.00, 20.91
DYN_PREV, DYN_HI10, DYN_MA21, DYN_LO252 = 24.28, 26.49, 25.58, 12.37
BAND = {"kind": "demand", "lo": 16.56, "hi": 17.02, "touches": 4, "strength": 92.0}


def dyn_row(**over):
    row = {
        "symbol": "DYN", "date": "2026-09-08", "close": DYN_CLOSE,
        "low": DYN_LOW, "high": DYN_HIGH, "ma21": DYN_MA21,
        "hot": HP.is_hot(DYN_PREV, DYN_LO252),
        "flush_pct": HP.flush_pct(DYN_LOW, DYN_HI10),
        "under_ma21_pct": HP.under_ma_pct(DYN_CLOSE, DYN_MA21),
        "reversal": HP.reversal(DYN_CLOSE, DYN_LOW, DYN_HIGH),
        "band": dict(BAND),
    }
    row.update(over)
    return row


# ── the archetype ──────────────────────────────────────────────────────────
def test_the_dyn_bar_he_pointed_at_passes_every_part_of_the_rule():
    row = dyn_row()
    ok, miss = HP.qualifies(row)
    assert ok is True and miss == []
    assert row["hot"] is True
    # -35.8 with the 26.49 ten-day high in this fixture; the live board reads
    # -36.3 off its own (slightly higher) prior 10-day high. Both are far past
    # the -12% rule, which is what the assertion is actually about.
    assert row["flush_pct"] < HP.FALL_FROM_10D_HIGH_PCT
    assert round(row["flush_pct"], 1) == -35.8
    assert round(row["under_ma21_pct"], 1) == -20.6
    assert row["reversal"]["off_low_pct"] == pytest.approx(19.47, abs=0.02)
    assert row["reversal"]["range_pos"] == pytest.approx(0.847, abs=0.002)


def test_the_owner_constants_are_the_measured_cuts():
    assert HP.HOT_ABOVE_52W_LOW_PCT == 30.0
    assert HP.FALL_FROM_10D_HIGH_PCT == -12.0
    assert HP.UNDER_MA21_PCT == -10.0
    assert HP.OFF_LOW_PCT == 8.0
    assert HP.RANGE_POS_MIN == 0.70
    assert HP.MA_LEN == 21           # "21 day moving average drops" — his words
    assert HP.HIGH_LOOKBACK == 10
    assert HP.MIN_DOLLAR_VOL_USD == 5e6


def test_the_study_block_is_what_the_study_produced():
    s = HP.STUDY
    assert (s["events"], s["names"]) == (65, 56)
    assert s["fwd5_p"] == 0.450 and s["fwd5_up_pct"] == 51      # the edge dies
    assert s["no_band_p"] == 0.461                              # the band carries it
    assert s["next_open_fwd2_pct"] == 2.85 and s["next_open_up2_pct"] == 66
    assert s["worst_3d_pct"] == -36.1                           # the tail is ugly
    assert s["mean_fwd3_pct"] < s["fwd3_median_pct"]            # mean below median
    # the SIMULATED trade — the numbers that decide it (a median is not expectancy)
    assert s["sim_n"] == 65 and s["sim_win_pct"] == 58
    assert s["sim_expectancy_r"] == 0.27
    assert s["sim_mean_pct"] == 2.29
    assert s["sim_worst_pct"] == -13.3                          # the stop caps the tail
    assert s["sim_avg_win_pct"] > abs(s["sim_avg_loss_pct"])     # wins bigger than losses
    assert (s["sim_exit_clock"] + s["sim_exit_stop"] + s["sim_exit_target"]) == s["sim_n"]
    assert s["sim_distinct_dates"] < s["sim_n"]                 # the trades are clustered


# ── each part is required, and each failure is named ───────────────────────
@pytest.mark.parametrize("over,needle", [
    ({"hot": False}, "not hot"),
    ({"flush_pct": -6.0}, "flush is only"),
    ({"under_ma21_pct": -4.0}, "under the 21-day line"),
    ({"reversal": {"off_low_pct": 2.0, "range_pos": 0.9}}, "off the low"),
    ({"reversal": {"off_low_pct": 12.0, "range_pos": 0.4}}, "top 30%"),
    ({"band": None}, "never reached a tested demand band"),
])
def test_every_missing_part_blocks_the_row_and_says_which(over, needle):
    ok, miss = HP.qualifies(dyn_row(**over))
    assert ok is False
    assert any(needle in m for m in miss), miss


def test_the_edges_are_inclusive_where_the_study_measured_them():
    assert HP.qualifies(dyn_row(flush_pct=-12.0))[0] is True
    assert HP.qualifies(dyn_row(flush_pct=-11.99))[0] is False
    assert HP.qualifies(dyn_row(under_ma21_pct=-10.0))[0] is True
    assert HP.qualifies(dyn_row(under_ma21_pct=-9.99))[0] is False
    assert HP.qualifies(dyn_row(reversal={"off_low_pct": 8.0, "range_pos": 0.70}))[0] is True
    assert HP.qualifies(dyn_row(reversal={"off_low_pct": 7.99, "range_pos": 0.70}))[0] is False
    assert HP.qualifies(dyn_row(reversal={"off_low_pct": 8.0, "range_pos": 0.699}))[0] is False


# ── the band rule, which is the load-bearing one ───────────────────────────
def test_any_tested_band_counts_and_a_proven_one_is_not_required():
    """Requiring 2+ touches measured WORSE (52% up vs 53%); 3+ worse again."""
    one_touch = [{"kind": "demand", "lo": 16.5, "hi": 17.1, "touches": 1, "strength": 20}]
    assert HP.band_for_low(DYN_LOW, one_touch) is not None
    # The docstring EXPLAINS why the proven gate is absent, so grep for a real
    # call or import rather than the word.
    src = open(HP.__file__).read()
    assert "is_proven_band(" not in src, "the board must not CALL the proven-band gate"
    assert "alert_gates" not in src.replace("`alert_gates", ""), \
        "the board must not import alert_gates — it measured worse here"


def test_the_band_must_contain_the_low_not_merely_be_near_it():
    bands = [{"kind": "demand", "lo": 16.56, "hi": 17.02}]
    assert HP.band_for_low(17.00, bands) is not None
    assert HP.band_for_low(17.10, bands) is None      # low stopped above it
    assert HP.band_for_low(16.00, bands) is None      # low cut clean through


def test_the_strongest_containing_band_wins_and_supply_is_ignored():
    bands = [
        {"kind": "demand", "lo": 16.0, "hi": 18.0, "touches": 1, "strength": 10},
        {"kind": "demand", "lo": 16.5, "hi": 17.5, "touches": 4, "strength": 92},
        {"kind": "supply", "lo": 16.5, "hi": 17.5, "touches": 9, "strength": 99},
    ]
    b = HP.band_for_low(17.0, bands)
    assert b["strength"] == 92 and b["kind"] == "demand"


def test_band_lookup_on_garbage_is_none():
    assert HP.band_for_low(None, [{"kind": "demand", "lo": 1, "hi": 2}]) is None
    assert HP.band_for_low(0, [{"kind": "demand", "lo": 1, "hi": 2}]) is None
    assert HP.band_for_low(1.5, None) is None
    assert HP.band_for_low(1.5, [{"kind": "demand", "lo": None, "hi": 2}]) is None
    assert HP.band_for_low(1.5, [{"kind": "demand", "lo": 3, "hi": 2}]) is None


# ── the pure feature reads ─────────────────────────────────────────────────
def test_hot_is_measured_off_the_prior_close_not_the_flush():
    assert HP.is_hot(DYN_PREV, DYN_LO252) is True
    assert HP.is_hot(15.0, 12.37) is False             # only +21%
    assert HP.is_hot(16.081, 12.37) is True            # exactly +30%
    assert HP.is_hot(None, 12.37) is False
    assert HP.is_hot(20.0, 0) is False


def test_reversal_and_flush_on_garbage_are_none():
    assert HP.reversal(20.0, 17.0, 17.0) is None       # no range
    assert HP.reversal(20.0, 0, 25.0) is None
    assert HP.reversal(None, 17.0, 25.0) is None
    assert HP.flush_pct(17.0, 0) is None
    assert HP.flush_pct(None, 26.0) is None
    assert HP.under_ma_pct(20.0, 0) is None


def test_the_plan_stops_under_the_low_that_tagged_the_band():
    p = HP.plan_for(dyn_row())
    assert p["stop"] == round(DYN_LOW * 0.995, 2) == 16.91
    assert p["trigger"] == round(DYN_HIGH * 1.001, 2)
    assert p["target"] == round(DYN_MA21, 2)
    assert "1-3 sessions" in p["horizon"] and "day 5" in p["horizon"]
    assert "next open" in p["entry_note"]
    assert HP.plan_for({"close": None}) is None


def test_rows_sort_deepest_flush_first():
    a = dyn_row(symbol="A", flush_pct=-15.0)
    b = dyn_row(symbol="B", flush_pct=-36.0)
    assert [r["symbol"] for r in sorted([a, b], key=HP.sort_key)] == ["B", "A"]


def test_every_rules_line_is_built_from_its_constant():
    blob = " ".join(HP.rules_lines())
    assert f"{HP.HOT_ABOVE_52W_LOW_PCT:g}%" in blob
    assert f"{abs(HP.FALL_FROM_10D_HIGH_PCT):g}%" in blob
    assert f"{abs(HP.UNDER_MA21_PCT):g}%" in blob
    assert f"{HP.MA_LEN}-day" in blob
    assert str(HP.STUDY["events"]) in blob
    assert "DIES BY DAY 5" in blob
    assert "-36.1%" in blob or "−36.1" in blob
    assert f"{HP.STUDY['sim_expectancy_r']:+g}R" in blob        # expectancy is on the board
    assert "correlated flush days" in blob                      # and so is the caveat


# ── the paper lane ─────────────────────────────────────────────────────────
def test_the_lane_only_acts_in_the_first_half_hour():
    d = lambda h, m: datetime(2026, 9, 9, h, m, tzinfo=ET)
    assert HPE.in_entry_window(d(9, 30)) is True
    assert HPE.in_entry_window(d(10, 0)) is True
    assert HPE.in_entry_window(d(9, 29)) is False
    assert HPE.in_entry_window(d(10, 1)) is False
    assert HPE.in_entry_window(d(15, 0)) is False


def test_only_yesterdays_flush_is_traded():
    one = lambda a, b: 1
    two = lambda a, b: 2
    assert HPE.signal_is_fresh("2026-09-08", "2026-09-09", one) is True
    assert HPE.signal_is_fresh("2026-09-04", "2026-09-09", two) is False   # stale
    assert HPE.signal_is_fresh("2026-09-09", "2026-09-09", one) is False   # same day
    assert HPE.signal_is_fresh("", "2026-09-09", one) is False
    assert HPE.signal_is_fresh("2026-09-08", "2026-09-09",
                               lambda a, b: (_ for _ in ()).throw(RuntimeError)) is False


def test_the_stop_sits_under_the_signal_low():
    assert HPE.stop_for(DYN_LOW) == 16.91
    assert HPE.stop_for(0) is None and HPE.stop_for(None) is None
    # DYN's own numbers: 20.31 down to 16.91 is 16.74%, inside the 20% budget
    ok, why = HPE.sizable(DYN_CLOSE, HPE.stop_for(DYN_LOW))
    assert ok is True and why is None
    assert HPE.stop_pct_from(DYN_CLOSE, 16.91) == pytest.approx(16.74, abs=0.02)


def test_stop_budget_boundary():
    assert HPE.stop_pct_from(100.0, 80.0) == 20.0
    assert HPE.sizable(100.0, 80.0)[0] is True           # exactly at the budget
    assert HPE.sizable(100.0, 79.0)[0] is False          # 21% — refused
    assert HPE.sizable(100.0, 100.0)[0] is False         # stop at the entry
    assert HPE.sizable(100.0, 110.0)[0] is False         # stop above the entry
    assert HPE.sizable(None, 80.0)[0] is False


def test_the_lane_exits_on_the_clock_because_the_edge_dies():
    assert HPE.MAX_HOLD_SESSIONS == 3
    why = HPE.should_exit(3, 100.0, 80.0, 200.0)
    assert why and "sessions held" in why and "day 5" in why


def test_the_stop_beats_the_target_and_both_beat_the_clock():
    assert "stop" in HPE.should_exit(3, 79.0, 80.0, 120.0)      # stop wins
    assert "target" in HPE.should_exit(3, 121.0, 80.0, 120.0)   # then target
    assert HPE.should_exit(1, 100.0, 80.0, 120.0) is None       # nothing yet
    assert HPE.should_exit(None, 100.0, 80.0, 120.0) is None
    assert HPE.should_exit(1, None, 80.0, 120.0) is None


def test_the_lane_refuses_a_live_broker():
    g = HPE.gate({"hot_pullback_entry": True}, "live", True)
    assert g["ok"] is False and "paper only" in g["why"]
    g = HPE.gate({"hot_pullback_entry": True}, "paper", True)
    assert g["ok"] is True and g["why"] is None


def test_the_switch_and_the_calendar_both_gate_the_lane():
    assert HPE.gate({"hot_pullback_entry": False}, "paper", True)["ok"] is False
    assert HPE.gate({"hot_pullback_entry": True}, "paper", False)["ok"] is False
    # absent key = ON (the lane refuses live on its own)
    assert HPE.gate({}, "paper", True)["ok"] is True


def test_the_status_block_says_paper_and_names_the_horizon():
    st = HPE.status({"hot_pullback_entry": True}, "paper", 1, 2)
    assert st["strategy"] == "hot_pullback"
    assert st["paper"] is True
    assert st["entries_today"] == 1 and st["max_per_day"] == HPE.MAX_ENTRIES_PER_DAY
    assert st["max_hold_sessions"] == 3
    assert any("Paper only" in r for r in st["rules"])
    assert any("day 5" in r for r in st["rules"])


def test_the_narrative_names_the_band_and_the_exit():
    n = HPE.narrative(dyn_row(), 17.5, 16.92, 25.58)
    assert "DYN" in n and "16.56-17.02" in n and "21-day line" in n
    assert "3 sessions" in n
