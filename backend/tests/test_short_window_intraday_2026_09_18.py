"""A short window now trims the INTRADAY chart (Ajay 2026-09-18).

  "Can you increase the bars on the weekly chart please? I am trying to read
   more on the weekly chart"

He was on the 1W zoom, which served its honest 5 daily bars. Asked which of
three things he meant, he chose "1 week of HOURLY bars": keep the span, raise
the resolution. He explicitly DECLINED weekly candles, so nothing here
resamples.

Measured on MU the day it shipped:
    1w + 60m   5 daily bars ->  32 hourly over 5 sessions
    2w + 60m               ->  67 hourly over 10 sessions
    1w + 15m               -> 116 bars over 5 sessions
    1y + 60m               -> 330 bars, unchanged, zoom inert
"""
from __future__ import annotations

import inspect

import pandas as pd
import pytest

from chart_maps import support as S


def _frame(stamps, tz=None):
    idx = pd.DatetimeIndex(stamps, tz=tz)
    return pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.5,
                         "close": 1.5, "volume": 100.0}, index=idx)


# ── the slice itself ─────────────────────────────────────────────────────────

def test_it_counts_SESSIONS_not_bars():
    """A count-based slice needs a bars-per-session number this repo does not
    have. Sessions here are deliberately uneven — 3 bars, then 1, then 2."""
    df = _frame(["2026-09-15 14:00", "2026-09-15 15:00", "2026-09-15 16:00",
                 "2026-09-16 14:00",
                 "2026-09-17 14:00", "2026-09-17 15:00"])
    out, n = S._last_sessions(df, 2)
    assert n == 2
    assert len(out) == 3                      # 1 + 2, not "2 bars"
    assert str(out.index[0]).startswith("2026-09-16")


def test_a_HALF_DAY_still_counts_as_one_whole_session():
    """Christmas Eve closes at 13:00 ET. A count-based slice would pull bars
    from the prior session to make up the difference; a date slice does not."""
    df = _frame(["2026-12-23 14:00", "2026-12-23 15:00", "2026-12-23 16:00",
                 "2026-12-23 17:00", "2026-12-23 18:00",
                 "2026-12-24 14:00", "2026-12-24 15:00"])   # half day
    out, n = S._last_sessions(df, 1)
    assert n == 1 and len(out) == 2
    assert all(str(t).startswith("2026-12-24") for t in out.index)


def test_THE_UTC_TRAP_an_after_hours_bar_stays_on_ITS_OWN_session():
    """THE ONE THAT MATTERS. The frame's index is UTC and NAIVE — verified on
    the live frame 2026-09-18 12:23 ET / 16:23 UTC, where MU's last 60m bar
    stamped 16:30 and 2026-09-17 ran 17:00 -> 20:00 (13:00 -> 16:00 ET).

    The extended session runs to 20:00 ET = 00:00 UTC THE NEXT DAY. Taken as a
    raw UTC date, that last after-hours hour files under tomorrow and drops out
    of today. Converting to ET first keeps it where it belongs.
    """
    df = _frame([
        "2026-09-17 13:30",   # 09:30 ET open
        "2026-09-17 20:00",   # 16:00 ET close
        "2026-09-17 23:00",   # 19:00 ET after-hours — still the 17th in ET
        "2026-09-18 00:00",   # 20:00 ET on the 17th! midnight UTC
        "2026-09-18 13:30",   # 09:30 ET on the 18th
    ])
    out, n = S._last_sessions(df, 1)
    assert n == 1
    # the ET-18th session is ONE bar; a naive UTC date would have made it two
    assert len(out) == 1, [str(t) for t in out.index]
    assert str(out.index[0]) == "2026-09-18 13:30:00"

    out2, n2 = S._last_sessions(df, 2)
    assert n2 == 2 and len(out2) == 5      # the whole 17th + the 18th


def test_an_ALREADY_AWARE_index_is_not_double_localised():
    df = _frame(["2026-09-17 20:00", "2026-09-18 13:30"], tz="UTC")
    out, n = S._last_sessions(df, 1)
    assert n == 1 and len(out) == 1


# ── negatives ────────────────────────────────────────────────────────────────

def test_NEGATIVE_fewer_sessions_than_asked_is_reported_not_faked():
    """A shallow intraday cache is normal. It must return what it has and SAY
    how many, never claim the span it was asked for."""
    df = _frame(["2026-09-17 14:00", "2026-09-18 14:00"])
    out, n = S._last_sessions(df, 10)
    assert n == 2 and len(out) == 2


def test_NEGATIVE_empty_none_and_zero_do_not_raise():
    assert S._last_sessions(None, 5) == (None, 0)
    empty = _frame([])
    out, n = S._last_sessions(empty, 5)
    assert n == 0
    df = _frame(["2026-09-18 14:00"])
    out2, n2 = S._last_sessions(df, 0)
    assert n2 == 0 and out2 is df


def test_NEGATIVE_an_unlocalisable_index_degrades_to_the_whole_frame():
    """Fails OPEN: a frame it cannot date is drawn whole, with 0 sessions
    claimed, rather than blanking the chart."""
    df = pd.DataFrame({"close": [1.0, 2.0]}, index=[0, 1])
    out, n = S._last_sessions(df, 5)
    assert n == 0 and len(out) == 2


# ── the contract with the rest of the tab ────────────────────────────────────

def test_ONLY_the_two_short_windows_trim_an_intraday_chart():
    src = inspect.getsource(S)
    assert 'spec["key"] in CHART_ONLY_LEVELS_FROM' in src
    assert set(S.CHART_ONLY_LEVELS_FROM) == {"1w", "2w"}


def test_NEGATIVE_no_resample_was_introduced_he_declined_weekly_candles():
    src = inspect.getsource(S)
    for banned in (".resample(", "closed=left", "closed='left'", 'closed="left"'):
        assert banned not in src, banned


def _code_lines(src: str) -> str:
    """Source with comments and docstrings stripped — dates and measured
    numbers live in prose and must not trip a constant check."""
    import ast
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Module)):
            d = ast.get_docstring(node)
            if d:
                node.body = node.body[1:]
    return ast.unparse(tree)


def test_NEGATIVE_no_bars_per_session_constant_was_invented():
    """The whole point of counting dates is needing no such number. Checked
    against CODE only — the docstring carries dates and measured bar counts."""
    code = _code_lines(inspect.getsource(S._last_sessions))
    for n in ("6.5", "26", "33", "78", "13", "6.75", "390"):
        assert n not in code, "%s appears in the slice's code" % n


def test_the_ANALYSED_frame_is_never_the_trimmed_one():
    """Rule: he was told the levels still come from where they came from, and
    it was verified live — 1w+60m and 6m+60m return identical supports,
    overhead, verdict and bars_used (330). The slice may only ever reach what
    is DRAWN, so nothing may rebind the analysed frame to it."""
    src = inspect.getsource(S)
    for rebind in ("df = short_intraday", "chart_df = short_intraday",
                   "df=short_intraday", "chart_df=short_intraday"):
        assert rebind not in src, rebind
    # every analytic read still runs on `df` / its own tail, never the slice
    for reader in ("trend_read(df.tail(read_budget)",):
        assert reader in src, reader
    # and the slice IS consumed by the drawn bars
    assert "_frame_bars(short_intraday if short_intraday is not None" in src
