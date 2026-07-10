"""Breakout breadth — pure-logic tests (synthetic frames, no Mongo/network).

The two book invariants under test:
  * grading uses the book's definitions — failed = closed back below the
    level it broke (TTLAC §6 p.117, §1 p.37); followed_through = extending
    after the break (§1 p.29); window incomplete -> None (never guessed).
  * exposure_read NEVER produces an entry gate — it returns sizing posture
    strings; the HOSTILE read needs real graded evidence (n >= 5), and a
    lone-breakout day still reads as valid market data (MIXED, not a veto).
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa.breakout_breadth import (FT_WINDOW_BARS, exposure_read,
                                   grade_breakout)


def _daily(closes, start="2026-06-01"):
    idx = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({"close": closes}, index=idx)


BREAK_DAY = "2026-06-03"      # index position 2


# ── grading ──────────────────────────────────────────────────────────────────
def test_followed_through_holds_level_and_extends():
    # broke over 100, closes 102 -> climbs, never undercuts the level
    df = _daily([98, 99, 102, 103, 104, 105, 106, 107, 108])
    g = grade_breakout(df, BREAK_DAY, level=100.0)
    assert g["outcome"] == "followed_through"
    assert g["fwd_pct"] > 0


def test_failed_when_price_closes_back_below_the_level():
    # breaks over 100 then closes at 97 two days later — the §6 p.117 failure
    df = _daily([98, 99, 102, 101, 97, 99, 101, 103, 105])
    g = grade_breakout(df, BREAK_DAY, level=100.0)
    assert g["outcome"] == "failed"


def test_stalled_holds_level_but_goes_nowhere():
    df = _daily([98, 99, 102, 101.5, 101, 101.2, 100.8, 101.9, 101])
    g = grade_breakout(df, BREAK_DAY, level=100.0)
    assert g["outcome"] == "stalled"


def test_window_incomplete_returns_none():
    df = _daily([98, 99, 102, 103])           # only 1 bar after the break
    assert grade_breakout(df, BREAK_DAY, level=100.0) is None


def test_missing_level_still_grades_direction():
    # no recent_high recorded -> can't test undercut; direction still grades
    df = _daily([98, 99, 102, 103, 104, 105, 106, 107, 108])
    g = grade_breakout(df, BREAK_DAY, level=None)
    assert g["outcome"] == "followed_through"


def test_garbage_dates_return_none():
    df = _daily([98, 99, 102, 103, 104, 105, 106, 107, 108])
    assert grade_breakout(df, "not-a-date", level=100.0) is None


# ── the exposure read ────────────────────────────────────────────────────────
def test_expanding_when_count_jumps_and_failures_low():
    r = exposure_read(today=60, avg10=40.0, failure_rate=0.1, graded_n=20)
    assert r["state"] == "EXPANDING"
    assert "p.164" in r["guidance"] and "p.165" in r["guidance"]


def test_hostile_when_breakouts_fail_wholesale():
    r = exposure_read(today=50, avg10=40.0, failure_rate=0.6, graded_n=20)
    assert r["state"] == "HOSTILE"
    assert "p.303" in r["guidance"]


def test_hostile_needs_evidence_small_n_stays_mixed():
    # 2 graded breakouts, both failed — not enough evidence for the p.303 call
    r = exposure_read(today=30, avg10=35.0, failure_rate=1.0, graded_n=2)
    assert r["state"] in ("MIXED", "EXPANDING")
    assert r["state"] != "HOSTILE"


def test_healthy_follow_through_without_expansion():
    r = exposure_read(today=35, avg10=40.0, failure_rate=0.1, graded_n=20)
    assert r["state"] == "HEALTHY"


def test_mixed_default_never_reads_as_entry_veto():
    r = exposure_read(today=10, avg10=40.0, failure_rate=None, graded_n=0)
    assert r["state"] == "MIXED"
    # the boundary language must survive: sizing guidance, never a skip rule
    assert "never skips" in r["guidance"] or "sizes positions" in r["guidance"]
