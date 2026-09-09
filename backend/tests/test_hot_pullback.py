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


def test_the_study_block_carries_the_CORRECTED_numbers_and_the_interval():
    """2026-09-09. The first numbers shipped here were wrong: the backtest's
    event window began at bar 301 instead of 252, deleting 17 trades that ran
    -0.418R (twelve on the 2025-11-06/07/11 flush days) and turning +0.10R into
    +0.27R. Four independent re-derivations agree on the figures below.

    The interval is pinned deliberately. A point estimate alone is what let a
    2.3x-overstated expectancy sit on a board he sizes off."""
    s = HP.STUDY
    assert s["sim_n"] == 83 and s["sim_distinct_dates"] == 50 and s["names"] == 71
    assert s["sim_win_pct"] == 51.8
    assert s["sim_mean_pct"] == 0.75
    assert s["sim_expectancy_r"] == 0.10
    assert s["sim_worst_pct"] == -14.61
    assert (s["sim_exit_clock"], s["sim_exit_stop"], s["sim_exit_target"]) == (54, 21, 8)
    # the interval INCLUDES ZERO — that is the finding, not a footnote
    assert s["ci_lo_r"] < 0 < s["ci_hi_r"]
    assert s["p_r_le_zero"] == 0.264
    # and the fragility: 83 trades on 50 dates, one date carrying it
    assert abs(s["drop_top_date_r"]) < 0.05
    assert s["sim_n"] > s["sim_distinct_dates"]
    # "2 years" was never reachable through a ~501-bar cache with a 252-day gate
    assert "2 years" not in s["window"]
    assert "2025-10-21" in s["window"] and "2026-08-25" in s["window"]


def test_the_old_wrong_numbers_are_gone_for_good():
    """Regression guard. Every one of these was on his live board and every one
    was wrong; none may come back without a fresh measurement."""
    # The VALUES, not the prose: the rules panel deliberately quotes the old
    # +0.27R to explain what was corrected, and that sentence must stay.
    vals = {k: v for k, v in HP.STUDY.items() if isinstance(v, (int, float))}
    assert vals["sim_expectancy_r"] != 0.27
    assert vals["sim_mean_pct"] != 2.29
    assert vals["sim_win_pct"] != 58
    assert vals["sim_worst_pct"] != -13.3
    assert vals["next_open_fwd1_pct"] != 2.40
    assert vals.get("next_open_fwd2_pct") != 2.85
    # and the keys whose only purpose was to carry an invalidated claim are gone
    for dead in ("fwd1_median_pct", "fwd3_median_pct", "fwd5_median_pct", "fwd5_p",
                 "trigger_rate_pct", "trigger_fwd3_pct", "worst_3d_pct",
                 "no_band_fwd1_pct", "mean_fwd3_pct"):
        assert dead not in HP.STUDY, f"{dead} belonged to the invalidated run"
    # the correction must be stated on the board, not quietly applied
    assert "CORRECTED" in " ".join(HP.rules_lines())


def test_the_band_is_no_longer_called_load_bearing():
    """It measured +0.007R against +0.100R at p=0.191 — the WEAKEST gate in the
    rule. The module used to call it 'the one that matters'."""
    blob = " ".join(HP.rules_lines()) + (HP.__doc__ or "")
    assert "NO GATE IN THIS RULE SEPARATES" in blob or "does not" in blob
    assert HP.STUDY["no_band_p"] > 0.05, "no band claim may assert significance"
    assert HP.STUDY["snapback_p"] > 0.05, "no snapback claim may assert significance either"
    assert HP.STUDY["band_separation_r"] < 0.1


@pytest.mark.parametrize("over,needle", [
    ({"hot": False}, "not hot"),
    ({"flush_pct": -5.0}, "off the 10-day high"),
    ({"under_ma21_pct": -2.0}, "under the 21-day line"),
    ({"reversal": {"off_low_pct": 2.0, "range_pos": 0.9}}, "no real snapback"),
    ({"reversal": {"off_low_pct": 20.0, "range_pos": 0.2}}, "top 30%"),
    ({"band": None}, "tested demand band"),
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
    assert "1-3 sessions" in p["horizon"]
    # The clock is the LANE's rule now, not a measured edge boundary — the
    # corrected study found no edge at any horizon.
    assert "No measured edge" in p["horizon"]
    assert "day 5" not in p["horizon"], "that claim came from the invalidated run"
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
    assert "NO MEASURED EDGE" in blob
    assert "CORRECTED" in blob
    assert f"{HP.STUDY['sim_worst_pct']:g}%" in blob     # the CORRECTED worst case
    assert f"{HP.STUDY['sim_expectancy_r']:+g}R" in blob
    assert f"{HP.STUDY['sim_expectancy_r']:+g}R" in blob        # expectancy is on the board
    assert "correlated market-wide flush days" in blob          # and so is the caveat
    assert "INCLUDES ZERO" in blob                              # the whole point


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


# ── the scan that was missing (2026-09-09, "hot pull back doesn't have scan") ──
# The board recomputed only when the tab was opened, and the paper lane read a
# LIVE re-scan. During RTH that scan describes today's PARTIAL session, so every
# row is dated today and `signal_is_fresh` rejects all of them — the lane could
# never fire. These pin the fix: the CLOSED session is written down, and the
# lane reads that history rather than re-scanning.
class _FakeColl:
    def __init__(self):
        self.docs = []

    def replace_one(self, flt, doc, upsert=False):
        self.docs = [d for d in self.docs if d.get("day") != flt.get("day")]
        self.docs.append(doc)

    def find_one(self, q=None, sort=None):
        rows = list(self.docs)
        lt = ((q or {}).get("day") or {}).get("$lt")
        if lt:
            rows = [d for d in rows if str(d.get("day")) < str(lt)]
        if not rows:
            return None
        return sorted(rows, key=lambda d: str(d.get("day")))[-1]


class _FakeDB:
    def __init__(self):
        self.hot_pullback_runs = _FakeColl()


def _board(rows, **over):
    d = {"warming": False, "universe": "full", "as_of": "2026-09-08T17:05:00-04:00",
         "scanned": 2594, "rows": rows, "near_miss": []}
    d.update(over)
    return d


def test_only_a_closed_session_is_ever_written_down(monkeypatch):
    """A `live` row is today's unfinished bar — fine to look at, ruinous to
    trade off tomorrow. It must never reach history."""
    live = dict(dyn_row(), date="2026-09-09", live=True)
    closed = dict(dyn_row(), date="2026-09-08", live=False)
    older = dict(dyn_row(symbol="OLD"), date="2026-09-05", live=False)

    day, rows = HP.closed_session_rows(_board([closed, older]))
    assert day == "2026-09-08" and [r["symbol"] for r in rows] == ["DYN"]
    # the whole board live (the RTH case that broke the lane) -> nothing
    assert HP.closed_session_rows(_board([live])) == (None, [])
    assert HP.closed_session_rows(_board([])) == (None, [])
    assert HP.closed_session_rows(None) == (None, [])
    assert HP.closed_session_rows(_board([dict(dyn_row(), date=None)])) == (None, [])


def test_record_writes_one_doc_per_session_and_replaces_on_a_rerun(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(HP, "_db", lambda: db)
    monkeypatch.setattr(HP, "market_closed_reason", lambda now=None: None)

    row = dict(dyn_row(), date="2026-09-08", live=False)
    assert HP.record(_board([row])) is True
    assert len(db.hot_pullback_runs.docs) == 1
    assert db.hot_pullback_runs.docs[0]["day"] == "2026-09-08"
    assert db.hot_pullback_runs.docs[0]["n"] == 1
    # the 08:05 backstop re-runs the same session: replace, never stack
    assert HP.record(_board([row])) is True
    assert len(db.hot_pullback_runs.docs) == 1


@pytest.mark.parametrize("why,board,closed", [
    ("market closed", _board([dict(dyn_row(), date="2026-09-08", live=False)]), "weekend"),
    ("still warming", _board([], warming=True), None),
    ("mid-session, every row live", _board([dict(dyn_row(), date="2026-09-09", live=True)]), None),
    ("empty board", _board([]), None),
])
def test_record_refuses_when_there_is_nothing_honest_to_write(monkeypatch, why, board, closed):
    db = _FakeDB()
    monkeypatch.setattr(HP, "_db", lambda: db)
    monkeypatch.setattr(HP, "market_closed_reason", lambda now=None: closed)
    assert HP.record(board) is False, why
    assert db.hot_pullback_runs.docs == []


def test_the_lane_reads_yesterdays_recorded_session_never_today(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(HP, "_db", lambda: db)
    monkeypatch.setattr(HP, "market_closed_reason", lambda now=None: None)
    HP.record(_board([dict(dyn_row(symbol="OLD"), date="2026-09-05", live=False)]))
    HP.record(_board([dict(dyn_row(), date="2026-09-08", live=False)]))
    # the morning cron may already have re-written TODAY before the lane runs
    HP.record(_board([dict(dyn_row(symbol="TDY"), date="2026-09-09", live=False)]))

    day, rows = HP.last_closed_signals(before="2026-09-09")
    assert day == "2026-09-08" and [r["symbol"] for r in rows] == ["DYN"]
    # every recorded field the lane and the board need survives the round trip
    assert rows[0]["low"] == DYN_LOW and rows[0]["band"]["lo"] == BAND["lo"]
    # without a cutoff it is simply the newest
    assert HP.last_closed_signals()[0] == "2026-09-09"


def test_no_history_means_the_lane_buys_nothing_and_says_so(monkeypatch):
    monkeypatch.setattr(HP, "_db", lambda: None)
    assert HP.last_closed_signals(before="2026-09-09") == (None, [])
    assert HP.last_closed_signals() == (None, [])


def test_the_lane_never_goes_back_to_a_live_rescan():
    """Source guard for the bug this fixed. `run` re-scanning the board means
    every row is dated TODAY during RTH and the lane silently never fires."""
    import inspect
    src = inspect.getsource(HPE.run)
    assert "last_closed_signals" in src, "the lane must read the recorded session"
    assert "cached_or_warm" not in src, "a live re-scan is dated today — the lane cannot use it"


def test_the_scan_is_actually_scheduled():
    """Ajay 2026-09-09: "hot pull back doesn't have scan." It had none. The
    post-close record is the one the lane depends on."""
    import pathlib
    lines = [l for l in pathlib.Path(__file__).resolve().parents[1]
             .joinpath("crontab").read_text().splitlines()
             if "hot-pullback" in l and not l.lstrip().startswith("#")]
    assert len(lines) >= 2, "the board needs at least a post-close and a premarket pass"
    recorders = [l for l in lines if "record=true" in l]
    assert recorders, "at least one pass must persist the closed session"
    assert any(l.split()[:2] == ["5", "17"] for l in recorders), \
        "the post-close record must run after the 16:55 band warm"
    for l in lines:
        assert l.strip().startswith("curl") or " curl " in l, \
            "curl the API, never `python -m` — the cron container is a different process"


# ── force has to actually force (2026-09-09) ───────────────────────────────
# `force=True` used to fall through to the background-warm path and hand back
# the STALE board flagged warming:True. Two callers read that as failure: the
# Scan button (same rows, looked like nothing happened) and record(), which
# refuses a warming payload — so the 17:05 cron, the one the paper lane depends
# on, wrote nothing. Proven live: a forced pass at 02:39 did not update the
# 02:32 history row.
def _seed_cache(monkeypatch, key="full:60", age=0.0, warming=False):
    import time as _t
    monkeypatch.setattr(HP, "_CACHE", {key: {
        "ts": _t.time() - age, "warming": warming,
        "data": {"warming": False, "rows": [], "scanned": 1, "as_of": "STALE"}}})


def test_force_blocks_and_rescans_instead_of_serving_the_stale_board(monkeypatch):
    calls = []

    def fake_scan(u="full", limit=HP.MAX_ROWS):
        calls.append(u)
        return {"warming": False, "rows": [], "scanned": 2594, "as_of": "FRESH"}

    _seed_cache(monkeypatch, age=0.0)            # cache is FRESH, the worst case
    monkeypatch.setattr(HP, "scan", fake_scan)
    out = HP.cached_or_warm("full", HP.MAX_ROWS, force=True)
    assert out["as_of"] == "FRESH", "force must re-scan, not serve the cache"
    assert out.get("warming") is False, "a forced pass must never come back warming"
    assert len(calls) == 1


def test_without_force_a_fresh_cache_is_still_served_without_scanning(monkeypatch):
    """The 524 guard stays: only `force` is allowed to block."""
    calls = []
    monkeypatch.setattr(HP, "scan", lambda *a, **k: calls.append(1) or {})
    _seed_cache(monkeypatch, age=0.0)
    out = HP.cached_or_warm("full", HP.MAX_ROWS)
    assert out["as_of"] == "STALE" and out["cached"] is True
    assert calls == []


def test_two_scan_buttons_at_once_coalesce_onto_one_scan(monkeypatch):
    """He can click Scan twice. That must not start two universe walks."""
    import threading, time as _t
    calls, started = [], threading.Event()

    def slow_scan(u="full", limit=HP.MAX_ROWS):
        calls.append(u)
        started.set()
        _t.sleep(0.25)
        return {"warming": False, "rows": [], "scanned": 2594, "as_of": "FRESH"}

    _seed_cache(monkeypatch, age=0.0)
    monkeypatch.setattr(HP, "scan", slow_scan)
    monkeypatch.setattr(HP, "_SCAN_LOCKS", {})
    out = {}
    def go(i):
        out[i] = HP.cached_or_warm("full", HP.MAX_ROWS, force=True)
    a = threading.Thread(target=go, args=(0,)); a.start()
    started.wait(2)
    b = threading.Thread(target=go, args=(1,)); b.start()
    a.join(5); b.join(5)
    assert len(calls) == 1, "the second Scan must ride the first, not re-walk the universe"
    assert out[0]["as_of"] == "FRESH" and out[1]["as_of"] == "FRESH"


def test_a_forced_pass_is_recordable_which_is_the_whole_point(monkeypatch):
    """The regression that mattered: force -> warming:True -> record() bails."""
    db = _FakeDB()
    monkeypatch.setattr(HP, "_db", lambda: db)
    monkeypatch.setattr(HP, "market_closed_reason", lambda now=None: None)
    row = dict(dyn_row(), date="2026-09-08", live=False)
    monkeypatch.setattr(HP, "scan", lambda *a, **k: _board([row], as_of="FRESH"))
    _seed_cache(monkeypatch, age=0.0)
    data = HP.cached_or_warm("full", HP.MAX_ROWS, force=True)
    assert data.get("warming") is False
    assert HP.record(data) is True
    assert db.hot_pullback_runs.docs[0]["day"] == "2026-09-08"
