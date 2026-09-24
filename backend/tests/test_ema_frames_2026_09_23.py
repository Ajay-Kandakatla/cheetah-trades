"""〰️ 9 EMA · W/M — the weekly / monthly resample, the forming bar, the curve.

Ajay 2026-09-23: "Also a new tab for 9EMA lines on our charts for weekly
charts and monthly charts please".

Every test here is about ONE of four things that can silently go wrong:
  * the resample puts the wrong daily bars in a period (label / closed / anchor),
  * a FORMING period is drawn as a finished one,
  * the "9 EMA" is a 9-DAY EMA wearing a weekly label,
  * a frame with too little history draws a stub line anyway.
Negatives are first-class here: each of the four has its own.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from chart_maps import ema_frames as EF


# ── fixtures ────────────────────────────────────────────────────────────────
def _code(obj) -> str:
    """Source with every comment and string literal removed, so a ban list
    reads the CODE and not the prose that explains why the code is clean."""
    import inspect
    import io
    import tokenize
    src = inspect.getsource(obj)
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except (tokenize.TokenError, IndentationError):             # pragma: no cover
        return src
    return " ".join(out)


def _daily(start: str, end: str, *, closes=None) -> pd.DataFrame:
    """Business-day OHLCV. Close = 1, 2, 3 … unless `closes` is given, so a
    period's O/H/L/C can be asserted by eye."""
    idx = pd.bdate_range(start, end)
    n = len(idx)
    c = list(closes) if closes is not None else [float(i + 1) for i in range(n)]
    assert len(c) == n, f"fixture wants {n} closes, got {len(c)}"
    return pd.DataFrame(
        {"open": [x - 0.5 for x in c], "high": [x + 1.0 for x in c],
         "low": [x - 1.0 for x in c], "close": c, "volume": [100.0] * n},
        index=idx)


# ── 1. the weekly resample lands the right days in the right week ───────────
def test_weekly_bucket_is_monday_to_friday_labelled_by_that_friday():
    # Mon 2026-09-07 .. Wed 2026-09-23. Closes 1..13 over 13 business days.
    df = _daily("2026-09-07", "2026-09-23")
    w = EF.resample_ohlcv(df, "weekly")
    assert [str(d.date()) for d in w.index] == ["2026-09-11", "2026-09-18", "2026-09-25"]
    # Week 1 = Mon 09-07 (close 1) .. Fri 09-11 (close 5).
    row = w.loc["2026-09-11"]
    assert row["open"] == pytest.approx(0.5)     # Monday's open
    assert row["close"] == pytest.approx(5.0)    # FRIDAY's close, not Thursday's
    assert row["high"] == pytest.approx(6.0)     # Friday's high (5 + 1)
    assert row["low"] == pytest.approx(0.0)      # Monday's low (1 - 1)
    assert row["volume"] == pytest.approx(500.0)  # five sessions


def test_weekly_never_straddles_a_friday_boundary():
    """NEGATIVE: the Friday session must NOT open the next week's bar.

    With `closed="left"` (the INTRADAY convention — see the module docstring)
    Friday 09-11 would start the 09-11..09-17 bucket and every weekly open in
    the app would be one session early. Pin the boundary from both sides."""
    df = _daily("2026-09-07", "2026-09-23")
    w = EF.resample_ohlcv(df, "weekly")
    # Friday 09-11's close (5.0) closes week 1 and does NOT open week 2.
    assert w.loc["2026-09-11"]["close"] == pytest.approx(5.0)
    # Week 2 opens on MONDAY 09-14 (close 6 -> open 5.5).
    assert w.loc["2026-09-18"]["open"] == pytest.approx(5.5)
    assert w.loc["2026-09-18"]["close"] == pytest.approx(10.0)   # Fri 09-18


# ── 2. the monthly resample across a month boundary ─────────────────────────
def test_monthly_bucket_is_one_calendar_month_labelled_by_the_month_end():
    # Aug 3 .. Sep 30 2026. 43 business days.
    df = _daily("2026-08-03", "2026-09-30")
    m = EF.resample_ohlcv(df, "monthly")
    assert [str(d.date()) for d in m.index] == ["2026-08-31", "2026-09-30"]
    aug, sep = m.loc["2026-08-31"], m.loc["2026-09-30"]
    n_aug = len(pd.bdate_range("2026-08-03", "2026-08-31"))
    assert aug["open"] == pytest.approx(0.5)                  # first session of August
    assert aug["close"] == pytest.approx(float(n_aug))        # LAST session of August
    # September opens on the session after August's last — not on August's last.
    assert sep["open"] == pytest.approx(float(n_aug) + 0.5)
    assert sep["close"] == pytest.approx(float(len(df)))


def test_monthly_does_not_fold_september_into_august():
    """NEGATIVE: one month per bar. A rule that merged the two would leave a
    single bar, and every 9-month EMA in the app would be a 9-of-something-else."""
    m = EF.resample_ohlcv(_daily("2026-08-03", "2026-09-30"), "monthly")
    assert len(m) == 2
    assert m.loc["2026-08-31"]["close"] != m.loc["2026-09-30"]["close"]


# ── 3. the FORMING bar is marked, and a completed one is not ────────────────
def test_current_week_is_marked_forming():
    df = _daily("2026-05-04", "2026-09-23")          # today = Wed 2026-09-23
    out = EF.build("TEST", "weekly", today=date(2026, 9, 23), df=df)
    bars = out["tile"]["bars"]
    assert bars[-1]["t"] == "2026-09-25"             # the week ENDING Friday
    assert bars[-1]["s"] == EF.FORMING_TAG
    assert out["forming"] and out["forming"]["date"] == "2026-09-25"
    assert "forming" in (out["tile"]["why"] or "")
    assert any("forming" in (b.get("text") or "") for b in out["tile"]["badges"])


def test_completed_periods_are_not_marked_forming():
    """NEGATIVE: every bar except the current period is a finished bar and must
    carry NO tag — a chart where everything is dimmed says nothing."""
    df = _daily("2026-05-04", "2026-09-23")
    out = EF.build("TEST", "weekly", today=date(2026, 9, 23), df=df)
    bars = out["tile"]["bars"]
    assert [b for b in bars[:-1] if "s" in b] == []
    assert out["completed_periods"] == len(bars) - 1


def test_a_stale_frame_has_no_forming_bar_at_all():
    """NEGATIVE: the frame ends Fri 09-18 and it is now Wed 09-23 — the last
    bar is a FINISHED week and must not be tagged, badged or excluded from the
    completed count."""
    df = _daily("2026-05-04", "2026-09-18")
    out = EF.build("TEST", "weekly", today=date(2026, 9, 23), df=df)
    assert out["forming"] is None
    assert "s" not in out["tile"]["bars"][-1]
    assert out["completed_periods"] == len(out["tile"]["bars"])
    assert not any("forming" in (b.get("text") or "") for b in out["tile"]["badges"])


def test_is_forming_is_inclusive_of_today():
    assert EF.is_forming(pd.Timestamp("2026-09-25"), date(2026, 9, 23)) is True
    assert EF.is_forming(pd.Timestamp("2026-09-25"), date(2026, 9, 25)) is True
    assert EF.is_forming(pd.Timestamp("2026-09-25"), date(2026, 9, 26)) is False


# ── 4. the 9 EMA is computed on RESAMPLED closes ────────────────────────────
def test_nine_week_ema_is_not_a_nine_day_ema_resampled():
    """THE BUG THIS PREVENTS. A 9-DAY EMA sampled at each week's Friday and a
    9-WEEK EMA on weekly closes are different numbers; a trending frame makes
    the daily one far closer to price."""
    df = _daily("2026-01-05", "2026-09-18")          # ~37 full weeks, trending
    w = EF.resample_ohlcv(df, "weekly")
    weekly_ema = EF.ema_values(list(w["close"]))

    daily_ema = df["close"].ewm(span=EF.EMA_SPAN, adjust=False).mean()
    daily_at_friday = [float(daily_ema.loc[:ts].iloc[-1]) for ts in w.index]

    assert weekly_ema[-1] is not None
    assert weekly_ema[-1] != pytest.approx(daily_at_friday[-1], abs=1e-6)
    # And the weekly line sits FURTHER from price — nine weeks of memory, not nine days.
    last_close = float(w["close"].iloc[-1])
    assert abs(last_close - weekly_ema[-1]) > abs(last_close - daily_at_friday[-1])


def test_ema_uses_the_house_call_and_his_span():
    """span=9, adjust=False — hand-computed, so a silent switch to `adjust=True`
    or to a rolling mean fails here and not on his chart."""
    closes = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0]
    got = EF.ema_values(closes)
    k = 2.0 / (EF.EMA_SPAN + 1)
    want = closes[0]
    for c in closes[1:]:
        want = c * k + want * (1 - k)
    assert got[-1] == pytest.approx(round(want, 4))
    assert EF.EMA_SPAN == 9 and EF.MIN_PERIODS == 9


def test_the_first_eight_points_are_gaps_not_seeds():
    """NEGATIVE: a point computed from fewer than 9 closes is not a 9-period
    average and must not be drawn as one."""
    got = EF.ema_values([float(i) for i in range(1, 21)])
    assert got[:8] == [None] * 8
    assert got[8] is not None


# ── 5. too little history serves NO curve ───────────────────────────────────
def test_a_short_frame_serves_no_curve_and_says_how_short():
    """Eight completed months cannot carry a 9-month EMA. NO short curve, no
    stub line — a sentence instead."""
    df = _daily("2026-01-05", "2026-09-23")          # Jan..Aug complete, Sep forming
    out = EF.build("TEST", "monthly", today=date(2026, 9, 23), df=df)
    assert out["completed_periods"] == 8
    assert out["tile"]["curves"] == []
    assert out["curve_reason"] and "8 completed months" in out["curve_reason"]
    assert "9-month EMA needs 9" in out["curve_reason"]
    assert out["tile"]["why"] == out["curve_reason"]


def test_nine_completed_months_do_serve_a_curve():
    df = _daily("2026-01-05", "2026-10-23")          # Jan..Sep complete, Oct forming
    out = EF.build("TEST", "monthly", today=date(2026, 10, 23), df=df)
    assert out["completed_periods"] == 9
    curves = out["tile"]["curves"]
    assert len(curves) == 1 and curves[0]["tone"] == EF.CURVE_TONE
    assert curves[0]["label"] == "9 EMA (monthly)"


def test_the_forming_bar_does_not_count_toward_the_warm_up():
    """NEGATIVE: 8 completed + 1 forming is still 8. A forming period counted as
    history would hand him a line one period before it exists."""
    df = _daily("2026-01-05", "2026-09-23")
    out = EF.build("TEST", "monthly", today=date(2026, 9, 23), df=df)
    assert len(out["tile"]["bars"]) == 9 and out["completed_periods"] == 8
    assert out["tile"]["curves"] == []


# ── 6. the curve aligns BY DATE, and a missing date is a gap ────────────────
def test_curve_aligns_by_date_and_leaves_gaps():
    bars = [{"t": "2026-09-11"}, {"t": "2026-09-18"}, {"t": "2026-09-25"}]
    c = EF.curve_for(bars, ["2026-09-11", "2026-09-25"], [1.0, 3.0], "weekly")
    assert c["values"] == [1.0, None, 3.0]           # the unmatched bar is a GAP


def test_curve_is_none_when_no_bar_matches():
    """NEGATIVE: an alignment that matches nothing serves NO curve rather than a
    row of nulls the chart would draw as an empty legend entry."""
    bars = [{"t": "2026-09-11"}, {"t": "2026-09-18"}]
    assert EF.curve_for(bars, ["2025-01-03"], [1.0], "weekly") is None


def test_a_positional_tail_would_have_shifted_the_curve():
    """The reason alignment is by date: line up a series that is MISSING the
    first period and a positional zip puts every value one bar early."""
    bars = [{"t": "2026-09-04"}, {"t": "2026-09-11"}, {"t": "2026-09-18"}]
    c = EF.curve_for(bars, ["2026-09-11", "2026-09-18"], [10.0, 20.0], "weekly")
    assert c["values"] == [None, 10.0, 20.0]
    assert c["values"] != [10.0, 20.0, None]


# ── 7. frame parsing, and the shape of a bad request ────────────────────────
def test_parse_frame_falls_back_rather_than_erroring():
    assert EF.parse_frame("weekly") == "weekly"
    assert EF.parse_frame("MONTHLY") == "monthly"
    assert EF.parse_frame("daily") == EF.DEFAULT_FRAME
    assert EF.parse_frame(None) == EF.DEFAULT_FRAME
    assert EF.parse_frame(object()) == EF.DEFAULT_FRAME


def test_no_symbol_and_no_history_both_answer_without_raising():
    empty = EF.build("", "weekly")
    assert empty["tile"] is None and empty["error"]
    none_df = EF.build("TEST", "weekly", df=pd.DataFrame())
    assert none_df["tile"] is None and "No price history" in none_df["error"]


def test_resample_survives_an_unusable_frame():
    assert EF.resample_ohlcv(None, "weekly") is None
    assert EF.resample_ohlcv(pd.DataFrame(), "weekly") is None
    bad = pd.DataFrame({"px": [1.0]}, index=pd.bdate_range("2026-09-07", periods=1))
    assert EF.resample_ohlcv(bad, "weekly") is None


# ── 8. it gates NOTHING ─────────────────────────────────────────────────────
def test_the_module_orders_gates_and_alerts_nothing():
    """Rule #10. The tab is a DRAWING: no sort key, no filter, no threshold, no
    push. Read the source rather than trusting the docstring."""
    src = _code(EF)
    for banned in ("_sort_key", "min_room", "alert", "push",
                   "is_candidate", "gate"):
        assert banned not in src, f"{banned} has no business on a drawing board"
    out = EF.build("TEST", "weekly", today=date(2026, 9, 23),
                   df=_daily("2026-01-05", "2026-09-23"))
    assert out["tile"]["bands"] == [] and out["tile"]["lines"] == []
    assert "_score" not in out["tile"]


def test_only_his_numbers_appear():
    """Rule #1. 9 is his. There is no 10, 20, 21, 50 or 200 hiding in here as a
    second period."""
    assert EF.EMA_SPAN == 9
    assert set(EF.FRAMES) == {"weekly", "monthly"}
    assert EF.FRAME_RULE == {"weekly": "W-FRI", "monthly": "ME"}


def test_the_served_note_says_it_is_not_measured():
    assert "measured" in EF.NOT_MEASURED
    out = EF.build("TEST", "weekly", today=date(2026, 9, 23),
                   df=_daily("2026-01-05", "2026-09-23"))
    assert out["note"] == EF.NOT_MEASURED


# ── 9. the endpoint is registered and coerces its own arguments ─────────────
def test_the_endpoint_exists_and_never_starts_a_scan():
    from chart_maps import api as API
    src = _code(API.chart_maps_ema_frames)
    assert "ema_frames_mod" in src and "build" in src
    assert "scan" not in src
    paths = {r.path for r in API.router.routes}
    assert "/chart-maps/ema-frames" in paths


# ── the after-hours leak (found in review, 2026-09-23) ──────────────────────
# `build()` asks support._frame_for for CLOSED sessions only. That is only true
# if it ALSO refuses the live overlay, because `_closed_of` strips the last row
# ONLY when `with_today_bar` set `partial=True` — and NEITHER after-hours branch
# does (prices.py:706 sets no `partial`; :753 sets
# `partial=(session != "afterhours")`, i.e. False). Both call `_extend_last_row`,
# which OVERWRITES the last daily close with the after-hours print and widens
# its high/low. So between 16:00 and 20:00 ET, a frame fetched WITH an overlay
# hands this resample an AH close on its last session, and the forming
# weekly/monthly bar closes on it while the tile's own sentence says the bars
# are closed sessions.
#
# `snap={}` is support._overlay_today's documented sentinel for "already
# fetched, this symbol was absent" — no fetch, NO overlay. It is load-bearing
# here, not an optimisation.
def test_the_frame_is_fetched_with_NO_live_overlay_at_all(monkeypatch):
    seen = {}

    def _fake_frame_for(sym, need, **kw):
        seen.update(kw)
        raise RuntimeError("stop here — the kwargs are the assertion")

    from chart_maps import support as _support
    monkeypatch.setattr(_support, "_frame_for", _fake_frame_for)
    EF.build("AAA", "weekly")

    assert seen.get("with_closed") is True
    # THE ASSERTION: the sentinel, not None. `None` means "fetch the snapshot
    # yourself and overlay it", which is exactly the after-hours leak.
    assert "snap" in seen, (
        "build() must pass snap={} — without it support._overlay_today fetches "
        "a live print and an after-hours close lands on the last daily bar")
    assert seen["snap"] == {}
    assert seen["snap"] is not None


def test_NEGATIVE_an_extended_last_bar_would_change_the_forming_close(monkeypatch):
    """Shows what the leak COSTS, so the test above is not just shape-matching.

    Same daily frame twice: once as the closed sessions, once with the last
    row's close overwritten the way `_extend_last_row` does on an AH print.
    The forming period's close must follow the CLOSED frame.
    """
    import pandas as pd

    idx = pd.date_range("2026-09-01", periods=20, freq="B")
    closed = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
         "volume": 1_000_000.0}, index=idx)

    ah = closed.copy()
    ah.iloc[-1, ah.columns.get_loc("close")] = 130.0      # the after-hours print
    ah.iloc[-1, ah.columns.get_loc("high")] = 131.0

    a = EF.build("AAA", "weekly", df=closed)
    b = EF.build("AAA", "weekly", df=ah)

    ca = (a["tile"]["bars"] or [])[-1]
    cb = (b["tile"]["bars"] or [])[-1]
    assert ca["c"] == 100.0
    assert cb["c"] == 130.0                # the leak, made visible
    assert ca["c"] != cb["c"], (
        "if these ever agree this test has stopped measuring anything")
