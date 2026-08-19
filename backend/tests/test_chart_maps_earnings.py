"""Institutional volume around the earnings print.

Ajay 2026-08-19: *"I need a tracker on the Chart maps page a new tab.. Where it
tracks earnings that had huge instituonal volume. Like BULL for example and
TGT"*, then *"pre earnings bullish momentum is also fine.. If Institutions are
coming in I want to ride along the momentum"*, then *"remove the ones that are
coming not pre earning of same day earnings"*.

    docker compose exec api python -m pytest /app/tests/test_chart_maps_earnings.py -v

The numbers here are the REAL 2026-08-19 tape, so a threshold change that would
have dropped TGT, BULL or EL fails by name.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import earnings as E


# ── the measurement his examples defined ─────────────────────────────────────
def test_close_location_puts_the_close_inside_the_bars_own_range():
    assert E.close_location(10.0, 8.0, 9.8) == 0.9
    assert E.close_location(10.0, 8.0, 8.2) == 0.1
    assert E.close_location(10.0, 8.0, 10.0) == 1.0
    assert E.close_location(10.0, 8.0, 8.0) == 0.0


def test_a_zero_range_bar_has_NO_close_location_rather_than_a_neutral_one():
    """A bar that never moved has no opinion about who won it. Returning 0.5
    would let a halted or untraded session read like a normal one."""
    assert E.close_location(10.0, 10.0, 10.0) is None


def test_close_location_refuses_junk_instead_of_returning_a_number():
    assert E.close_location(None, 8.0, 9.0) is None
    assert E.close_location("10", 8.0, 9.0) is None
    assert E.close_location(float("nan"), 8.0, 9.0) is None
    assert E.close_location(8.0, 10.0, 9.0) is None


def test_volume_ratio_needs_a_positive_base():
    assert E.volume_ratio(300, 100) == 3.0
    assert E.volume_ratio(300, 0) is None
    assert E.volume_ratio(300, None) is None
    assert E.volume_ratio(-5, 100) is None


# ── the gate ─────────────────────────────────────────────────────────────────
def _bar(vol=2.2, loc=0.81, dv=1.5e9, chg=4.28):
    return {"vol_ratio": vol, "close_loc": loc, "dollar_vol": dv, "change_pct": chg}


def test_the_two_names_he_named_pass_on_their_REAL_numbers():
    assert E.is_institutional_buy(_bar(2.19, 0.81, 1.503e9, 4.28)) is True    # TGT
    assert E.is_institutional_buy(_bar(3.11, 0.92, 2.81e8, 8.95)) is True     # BULL


def test_a_high_volume_COLLAPSE_is_not_a_buy():
    """VIK, same session: 2.37x volume, close at 0.01 of range. Huge
    participation, all of it selling. He chose buying-only, so False here is
    the intended answer — a later 'show both' has to be a decision, not a slip."""
    assert E.is_institutional_buy(_bar(2.37, 0.01, 4.91e8, -7.65)) is False


def test_a_big_gap_that_FADES_to_the_low_is_not_a_buy():
    """The hole in the existing picks list, which gates on reaction % and
    volume only — a +8% gap closing on its low passes there. Not here."""
    assert E.is_institutional_buy(_bar(3.0, 0.12, 9e8, 8.0)) is False


def test_a_thin_name_fails_however_violent_the_move():
    """COTY, same session: +10.58% on 1.71x — and $47M traded. A scale-free
    ratio is the wrong test for a question about institutions."""
    assert E.is_institutional_buy(_bar(1.71, 0.80, 4.7e7, 10.58)) is False


def test_a_flat_or_down_day_never_qualifies():
    assert E.is_institutional_buy(_bar(chg=0.0)) is False
    assert E.is_institutional_buy(_bar(chg=-0.01)) is False


def test_a_missing_measurement_FAILS_rather_than_being_skipped():
    """'Could not measure participation' and 'participation was large' must
    not render as the same tile."""
    for k in ("vol_ratio", "close_loc", "dollar_vol", "change_pct"):
        b = _bar(); b[k] = None
        assert E.is_institutional_buy(b) is False
    assert E.is_institutional_buy(None) is False
    assert E.is_institutional_buy({}) is False


def test_a_bool_is_not_a_measurement():
    """True >= 0.6 is True, so a bool would pass the close-location gate and
    hide an upstream bug."""
    b = _bar(); b["close_loc"] = True
    assert E.is_institutional_buy(b) is False


def test_the_thresholds_are_locked_to_what_was_measured():
    assert E.MIN_VOL_RATIO == 1.5
    assert E.MIN_CLOSE_LOC == 0.60
    assert E.MIN_DOLLAR_VOL == 50_000_000.0


def test_the_size_floor_is_IMPORTED_from_the_shared_liquidity_scale():
    from supply_demand import demand_reentry as dr
    assert E.MIN_DOLLAR_VOL == dr.LIQ_DEEP_USD


# ── reacted vs upcoming: the rule that separates TGT from BULL ───────────────
TODAY = "2026-08-19"


def test_an_AFTER_CLOSE_report_dated_today_has_NOT_been_seen_by_todays_bar():
    """BULL. Reports tonight, so today's +8.95% traded without the numbers."""
    assert E.phase_for({"next_date": TODAY, "when": "AMC"}, TODAY, TODAY) == E.UPCOMING


def test_a_BEFORE_OPEN_report_dated_today_IS_already_priced():
    """EL. Reported this morning; today's bar is the response."""
    assert E.phase_for({"next_date": TODAY, "when": "BMO"}, TODAY, TODAY) == E.REACTED


def test_unknown_timing_on_a_dated_report_is_treated_as_ALREADY_OUT():
    """TGT's calendar row has `when: null`. Calling a released report
    'upcoming' understates risk far more dangerously than the reverse."""
    assert E.phase_for({"next_date": TODAY, "when": None}, TODAY, TODAY) == E.REACTED


def test_a_future_report_is_upcoming_and_a_past_one_is_reacted():
    assert E.phase_for({"next_date": "2026-08-21"}, TODAY, TODAY) == E.UPCOMING
    assert E.phase_for({"next_date": "2026-08-15"}, TODAY, TODAY) == E.REACTED


def test_a_name_with_no_dates_at_all_has_no_phase():
    assert E.phase_for({}, TODAY, TODAY) is None
    assert E.phase_for(None, TODAY, TODAY) is None
    assert E.phase_for({"next_date": TODAY}, "", TODAY) is None


def test_the_board_does_not_look_AHEAD_past_today():
    """His correction after UI showed up two sessions out. Widen this and the
    board silently becomes a watchlist of strong names again."""
    assert E.LOOKAHEAD_DAYS == 0


def test_it_still_looks_BACK_far_enough_to_catch_after_close_reporters():
    """Deliberately asymmetric: a report after yesterday's close reacts on
    TODAY's bar, and most reports are after the close."""
    assert E.LOOKBACK_DAYS >= 1


# ── bar metrics ──────────────────────────────────────────────────────────────
def _frame(n=80, last=None):
    idx = pd.bdate_range("2026-04-01", periods=n)
    base = [100.0] * n
    df = pd.DataFrame({"open": base, "high": [c * 1.01 for c in base],
                       "low": [c * 0.99 for c in base], "close": base,
                       "volume": [1_000_000.0] * n}, index=idx)
    if last:
        for k, v in last.items():
            df.iloc[-1, df.columns.get_loc(k)] = v
    return df


def test_bar_metrics_reads_the_bar_it_was_asked_for():
    df = _frame(last={"open": 97.0, "high": 112.0, "low": 96.0,
                      "close": 110.0, "volume": 3_000_000.0})
    m = E.bar_metrics(df, len(df) - 1)
    assert m["vol_ratio"] == 3.0
    assert m["change_pct"] == 10.0
    assert m["close_loc"] == round((110 - 96) / (112 - 96), 4)
    assert m["gap_pct"] == -3.0            # opened BELOW the prior close — TGT
    assert m["dollar_vol"] == 110.0 * 3_000_000.0


def test_the_median_window_EXCLUDES_the_bar_being_judged():
    """Otherwise a 5x day helps raise its own bar and the ratio understates."""
    df = _frame(last={"volume": 9_000_000.0})
    assert E.bar_metrics(df, len(df) - 1)["vol_ratio"] == 9.0


def test_a_frame_too_short_for_a_median_returns_nothing():
    assert E.bar_metrics(_frame(20), 19) is None
    assert E.read_bar(_frame(20)) is None


def test_bar_metrics_refuses_an_out_of_range_index():
    df = _frame()
    assert E.bar_metrics(df, len(df)) is None
    assert E.bar_metrics(df, -1) is None
    assert E.bar_metrics(None, 5) is None


# ── the module boundary ──────────────────────────────────────────────────────
def test_the_reaction_bar_is_located_by_the_SHARED_reader():
    """`earnings_picks.reaction_read` already anchors BMO vs AMC. A second copy
    would drift, and the two surfaces would disagree about which bar reacted."""
    import inspect
    assert "earnings_picks.reaction_read(" in inspect.getsource(E.scan)


def test_it_reads_the_SHARED_calendar_and_never_fetches_its_own():
    """A private yfinance call here would double rate-limit pressure on the
    module that owns this data, and could disagree with it."""
    import inspect
    src = inspect.getsource(E)
    assert "earnings_watch._coll()" in src
    assert "yf.Ticker" not in src


def test_the_two_halves_are_never_merged_into_one_list():
    import inspect
    src = inspect.getsource(E.scan)
    assert '"reacted": reacted' in src and '"upcoming": upcoming' in src


def test_ranking_is_by_SIZE_not_by_percentage_move():
    """The defect in the existing picks list, which put CURI (+42.5% on $81M)
    second while TGT ($1.5B) and EL ($1.33B) were absent entirely."""
    import inspect
    assert 'key=lambda r: -(r.get("dollar_vol") or 0)' in inspect.getsource(E.scan)
