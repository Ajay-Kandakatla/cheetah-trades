"""Entry-quality fixes from the 2026-07-09 Auto-Pilot failure autopsy.

Four fixes, one branch (Ajay sign-off 2026-07-09):
  1. volume_confirmed() — the TLSW p.229 gate: projections only trusted past
     VOL_CONFIRM_MIN_FRAC of the session; actual volume >= floor passes any
     time; missing data fails closed. Kills the 9:31 infinite-projection buy.
  2. AUTO_MIN_SCORE 70 -> 85 + `auto_min_score` config override.
  3. patterns.history.backfill_fwd21 — fwd_21_pct was null on 100% of
     resolved docs (graded before the window completed, never revisited).
  4. soir history now stamps signal + soir_percentile (regression: writer
     must not run before classification — order guarded here by source).
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trading.auto_entry import (AUTO_MIN_SCORE, AUTO_RELVOL_MIN,
                                VOL_CONFIRM_MIN_FRAC, _min_score,
                                volume_confirmed)
from patterns.history import PATTERN_HORIZON, backfill_fwd21


# ── 1. the p.229 volume gate ─────────────────────────────────────────────────
VOL_OK = {"projected_relvol": 2.0, "today_volume": 200_000, "avg_vol_50": 1_000_000}


def test_projection_not_trusted_at_the_open():
    """9:31 (frac~0.003): projected RelVol 2.0 must NOT trigger — this is the
    exact failure mode that fired 12 of 18 entries in the first 2 minutes."""
    ok, detail = volume_confirmed(0.003, VOL_OK)
    assert ok is False
    assert detail["basis"] == "too_early_to_project"


def test_projection_trusted_after_the_floor():
    ok, detail = volume_confirmed(VOL_CONFIRM_MIN_FRAC, VOL_OK)
    assert ok is True and detail["basis"] == "projected"
    ok2, _ = volume_confirmed(0.35, VOL_OK)          # ~2h in, the p.229 example
    assert ok2 is True


def test_actual_monster_volume_passes_any_time():
    """A true monster open — ACTUAL volume already >= 1.5x the FULL 50-day
    average at 9:35 — proves itself without projection."""
    vol = {"projected_relvol": 9.9, "today_volume": 1_600_000, "avg_vol_50": 1_000_000}
    ok, detail = volume_confirmed(0.01, vol)
    assert ok is True and detail["basis"] == "actual"
    assert detail["actual_relvol"] == 1.6 >= AUTO_RELVOL_MIN


def test_weak_volume_fails_even_late():
    ok, detail = volume_confirmed(0.5, {"projected_relvol": 1.1,
                                        "today_volume": 300_000,
                                        "avg_vol_50": 1_000_000})
    assert ok is False and detail["basis"] == "insufficient_volume"


def test_missing_volume_data_fails_closed():
    for vol in ({}, {"projected_relvol": None},
                {"today_volume": 100, "avg_vol_50": 0},
                {"today_volume": None, "avg_vol_50": None, "projected_relvol": None}):
        ok, _ = volume_confirmed(0.5, vol)
        assert ok is False, f"gate must fail closed on {vol}"


# ── 2. score floor + config override ────────────────────────────────────────
def test_default_floor_is_85():
    assert AUTO_MIN_SCORE == 85.0
    assert _min_score({}) == 85.0
    assert _min_score(None) == 85.0


def test_config_override_wins_and_garbage_falls_back():
    assert _min_score({"auto_min_score": 70}) == 70.0
    assert _min_score({"auto_min_score": "90"}) == 90.0
    assert _min_score({"auto_min_score": "high"}) == 85.0


# ── 3. fwd_21_pct backfill ───────────────────────────────────────────────────
def _daily(n, start="2026-06-01", base=100.0, step=1.0):
    idx = pd.bdate_range(start, periods=n)
    return pd.DataFrame({"close": [base + step * i for i in range(n)]}, index=idx)


def test_backfill_computes_once_window_complete():
    df = _daily(PATTERN_HORIZON + 5)
    obs = {"et_date": "2026-06-01", "obs_close": 100.0}
    fwd = backfill_fwd21(df, obs)
    assert fwd == round(PATTERN_HORIZON * 1.0, 2)    # +1/day for 21 bars = +21%


def test_backfill_waits_for_the_window():
    df = _daily(PATTERN_HORIZON - 3)                 # window not complete yet
    assert backfill_fwd21(df, {"et_date": "2026-06-01", "obs_close": 100.0}) is None


def test_backfill_survives_garbage():
    df = _daily(PATTERN_HORIZON + 5)
    assert backfill_fwd21(df, {"et_date": "not-a-date", "obs_close": 100.0}) is None
    # obs_close 0/None falls back to the observation day's close — the same
    # `or closes[k]` convention _grade_pattern uses — and still computes.
    assert backfill_fwd21(df, {"et_date": "2026-06-01", "obs_close": 0}) == \
        round(PATTERN_HORIZON * 1.0, 2)


# ── 4. SOIR history signal write order (source guard) ───────────────────────
def test_soir_signal_recorded_after_classification():
    """_record_signal must be called AFTER _classify in compute_for_symbol —
    recording earlier would always write None (the bug this fix prevents) or
    change _percentile()'s rank-vs-history semantics."""
    path = os.path.join(os.path.dirname(__file__), "..", "options", "soir.py")
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    assert "def _record_signal" in src
    body = src.split("def compute_for_symbol", 1)[1]
    i_classify = body.find("_classify(")
    i_record = body.find("_record_signal(")
    assert i_classify != -1 and i_record != -1
    assert i_record > i_classify, (
        "_record_signal must run after _classify in compute_for_symbol")
