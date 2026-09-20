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


# ── the look-back is SESSIONS, not calendar days (2026-09-20, critique F2) ───
def test_the_look_back_window_counts_SESSIONS_so_FRIDAY_reporters_survive_the_weekend():
    """POSITIVE, new 2026-09-20. `lo = today - 2 CALENDAR days` on a Monday
    opened the window at the Saturday, so every Friday reporter — 53 of the
    last 810 reports, 38 BMO and 13 AMC — was dropped before its phase was
    ever read. Two SESSIONS back from Monday 2026-09-21 is Thursday 09-17, so
    Friday's reporter is inside it."""
    assert E._trading_days_back("2026-09-21", 2) == "2026-09-17"
    assert E._trading_days_back("2026-09-21", 1) == "2026-09-18"
    assert E._trading_days_back("2026-09-18", 1) == "2026-09-17"
    assert E._trading_days_back("2026-09-21", 0) == "2026-09-21"
    # a Thursday reporter ahead of a Friday holiday survives too: 2026-07-03
    # is closed (July 4 observed), so two sessions back from Monday 07-06 is
    # Wednesday 07-01, and Thursday 07-02's reporter is inside the window.
    assert E._trading_days_back("2026-07-06", 2) == "2026-07-01"


def test_the_calendar_query_uses_the_SESSION_window(monkeypatch):
    """The window the Mongo query actually asks for, not the arithmetic alone."""
    seen = {}

    class FakeColl:
        def find(self, q):
            seen["q"] = q
            return []

    import sepa.earnings_watch as EW
    monkeypatch.setattr(EW, "_coll", lambda: FakeColl())
    E._calendar_rows("2026-09-21")
    rng = seen["q"]["$or"][0]["next_date"]
    assert rng["$gte"] == "2026-09-17" and rng["$lte"] == "2026-09-21"


def test_a_WEDNESDAY_still_does_not_show_MONDAYS_reporter(monkeypatch):
    """NEGATIVE, unchanged by the session look-back: the window reaches Monday,
    but the board only ever shows TODAY's bar, so a reaction two sessions old
    is history — and `dropped_not_last_bar` says so instead of the row simply
    vanishing."""
    cal = {"MON": {"_id": "MON", "next_date": "2026-09-21", "when": "BMO",
                   "last_report": {"date": "2026-09-21", "when": "BMO", "surprise_pct": 9.0}}}
    df = _frame(n=120)
    df.index = pd.bdate_range(end="2026-09-23", periods=120)
    monkeypatch.setattr(E, "_calendar_rows", lambda d: cal)
    import sepa.prices as P
    monkeypatch.setattr(P, "load_prices", lambda sym: df)
    res = E.scan(today="2026-09-23")
    assert res["reacted"] == []
    assert res["dropped_not_last_bar"] == 1


# ── the counters the 📣 push pass reports (2026-09-20) ───────────────────────
def _inst_frame(end="2026-09-18", n=120):
    df = _frame(n=n)
    df.index = pd.bdate_range(end=end, periods=n)
    df.iloc[-1, df.columns.get_loc("open")] = 99.0
    df.iloc[-1, df.columns.get_loc("high")] = 130.0
    df.iloc[-1, df.columns.get_loc("low")] = 98.0
    df.iloc[-1, df.columns.get_loc("close")] = 128.0
    df.iloc[-1, df.columns.get_loc("volume")] = 5_000_000.0
    return df


def _collapse_frame(end="2026-09-18", n=120):
    """VIK's shape: enormous participation, every bit of it selling."""
    df = _inst_frame(end=end, n=n)
    df.iloc[-1, df.columns.get_loc("close")] = 98.2
    return df


def test_scan_counts_the_reacted_rows_it_SAW_and_the_ones_that_were_not_buying(monkeypatch):
    """`scan()` drops a non-institutional reaction with a bare `continue`, so a
    pass reporting "0 candidates" could not say whether nothing reported or
    nothing was bought. Additive counters, no gate change."""
    cal = {"BUY": {"_id": "BUY", "next_date": "2026-09-18", "when": "BMO",
                   "last_report": {"date": "2026-09-18", "when": "BMO", "surprise_pct": 6.0}},
           "SELL": {"_id": "SELL", "next_date": "2026-09-18", "when": "BMO",
                    "last_report": {"date": "2026-09-18", "when": "BMO", "surprise_pct": 6.0}}}
    frames = {"BUY": _inst_frame(), "SELL": _collapse_frame()}
    monkeypatch.setattr(E, "_calendar_rows", lambda d: cal)
    import sepa.prices as P
    monkeypatch.setattr(P, "load_prices", lambda sym: frames[sym])
    res = E.scan(today="2026-09-18")
    assert [r["symbol"] for r in res["reacted"]] == ["BUY"]
    assert res["reacted_seen"] == 2
    assert res["reacted_not_institutional"] == 1
    assert res["dropped_not_last_bar"] == 0


def test_the_new_counters_never_reorder_or_gate_anything():
    """SOURCE GUARD: the counters are bookkeeping. The ranking is still dollar
    volume and the institutional read is still the only reason a row drops."""
    import inspect
    src = inspect.getsource(E.scan)
    assert 'key=lambda r: -(r.get("dollar_vol") or 0)' in src
    assert "reacted_not_institutional += 1" in src and "if not is_institutional_buy" in src


def test_the_docstring_no_longer_quotes_a_cron_minute_that_moved():
    """The calendar refresh runs at 17:45, not 19:10 — and the 17:45 roll is
    the whole reason the 📣 pass runs at 17:35."""
    assert "19:10" not in E.__doc__
    assert "17:45" in E.__doc__


def test_the_override_env_never_makes_a_WEEKEND_count_as_a_session(monkeypatch):
    """NEGATIVE, new 2026-09-20 (refix). `CHEETAH_IGNORE_HOLIDAY=1` makes
    `gate.closed_reason` answer None for EVERY day, weekends included — that
    env is a permission to RUN on a closed day, not a claim that the day was a
    session. Un-guarded, MAIN's Monday `--dry-run --force` check would count
    Sunday and Saturday, open the window at the Saturday and silently drop
    every Friday reporter: the F2 bug again, in the one run meant to prove it
    fixed. The weekday test is made before the gate is asked, so the answer is
    identical with and without the override."""
    monkeypatch.setenv("CHEETAH_IGNORE_HOLIDAY", "1")
    from market_hours import gate
    assert gate.override_active() is True
    assert gate.closed_reason(
        __import__("datetime").datetime(2026, 9, 19, 12, 0)) is None   # a Saturday
    # ...and yet the window still opens at Thursday, not at the Saturday.
    assert E._trading_days_back("2026-09-21", 2) == "2026-09-17"
    assert E._trading_days_back("2026-09-21", 1) == "2026-09-18"
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY")
    assert E._trading_days_back("2026-09-21", 2) == "2026-09-17"


def test_the_override_env_is_allowed_to_lift_a_HOLIDAY_and_that_is_documented(monkeypatch):
    """The deliberate residue, pinned so it cannot change unnoticed. The gate
    owns the holiday table and this module keeps no second copy, so under the
    override a holiday counts as open and the window is one session narrower.
    Weekends are the case that bit; holidays cost at most one session on a
    manual run, and `docs/alerts/earnings_reaction.md` says so."""
    assert E._trading_days_back("2026-07-06", 2) == "2026-07-01"        # no override
    monkeypatch.setenv("CHEETAH_IGNORE_HOLIDAY", "1")
    # 07-03 (July 4 observed) now counts, so the walk stops one session later.
    assert E._trading_days_back("2026-07-06", 2) == "2026-07-02"
