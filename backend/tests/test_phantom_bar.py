"""Behavioral contract for the phantom trailing-bar guard (backend/sepa/prices.py).

REGRESSION for the 2026-06-02 bug: before the regular session prints, the bulk
snapshot echoed the previous day's completed aggregate into a bar stamped with
*today's* date, leaving two adjacent bars with byte-identical close AND volume.
That duplicate close sits inside `recent_high`, so the breakout test
`last_close > recent_high` can never be true -> `high_vol_breakout` went to 0
for the WHOLE universe and `is_buyable` collapsed to ~1/511 (book pp.198-203).

`_drop_phantom_tail` strips the placeholder at read time; `patch_latest_closes`
refuses to write it in the first place. `test_phantom_suppresses_breakout...`
is the headline test that would have caught the bug.

Pure pandas — no network, no Mongo.
"""
from __future__ import annotations

import pandas as pd

from sepa import prices, volume


def _series(closes, vols):
    idx = pd.date_range("2025-01-01", periods=len(closes), freq="B")
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": vols},
        index=idx,
    )


def test_drops_exact_duplicate_tail():
    # Last bar duplicates the prior session's close AND volume -> phantom.
    df = _series([100, 101, 102, 102], [1000, 1100, 1200, 1200])
    out = prices._drop_phantom_tail(df)
    assert len(out) == len(df) - 1
    assert out["close"].iloc[-1] == 102


def test_keeps_same_close_different_volume():
    # Same close but a different volume is a real (flat) session — keep it.
    df = _series([100, 101, 102, 102], [1000, 1100, 1200, 1201])
    assert len(prices._drop_phantom_tail(df)) == len(df)


def test_keeps_different_close():
    df = _series([100, 101, 102, 103], [1000, 1100, 1200, 1200])
    assert len(prices._drop_phantom_tail(df)) == len(df)


def test_too_short_is_noop():
    assert len(prices._drop_phantom_tail(_series([100], [1000]))) == 1
    assert prices._drop_phantom_tail(None) is None


def test_phantom_suppresses_breakout_guard_restores_it():
    """HEADLINE: a phantom dup tail makes high_vol_breakout impossible; dropping
    it restores the real breakout signal that feeds is_buyable."""
    closes = [100 + (i % 3) * 0.2 for i in range(69)] + [110.0]
    vols = [1000 + (i % 5) * 10 for i in range(69)] + [2000.0]

    real = _series(closes, vols)
    assert volume.analyze(real)["high_vol_breakout"] is True          # real breakout fires

    phantom = _series(closes + [110.0], vols + [2000.0])              # byte-identical dup tail
    assert volume.analyze(phantom)["high_vol_breakout"] is False      # ...silently suppressed

    healed = prices._drop_phantom_tail(phantom)
    assert volume.analyze(healed)["high_vol_breakout"] is True        # guard brings it back


# --- staleness guard (delisted / halted / renamed) -------------------------

def _df_last_dated(last_date, n=6):
    idx = pd.bdate_range(end=last_date, periods=n)
    closes = [100.0] * n
    return pd.DataFrame(
        {"open": closes, "high": closes, "low": closes, "close": closes, "volume": [1000] * n},
        index=idx,
    )


def test_is_stale_fresh():
    df = _df_last_dated("2026-06-02")
    assert prices.is_stale(df, asof=pd.Timestamp("2026-06-02")) is False


def test_is_stale_delisted():
    # CFLT's real situation: last bar 2026-03-16, scan run 2026-06-02.
    df = _df_last_dated("2026-03-16")
    assert prices.is_stale(df, asof=pd.Timestamp("2026-06-02")) is True


def test_is_stale_within_window_is_fresh():
    df = _df_last_dated("2026-05-26")          # 5 market sessions back
    assert prices.is_stale(df, asof=pd.Timestamp("2026-06-02")) is False


def test_is_stale_trading_day_boundary():
    """The guard is TRADING-day based (STALE_MAX_TRADING_DAYS = 6): 6 missed
    market sessions is still fresh, 7 is stale. Dates chosen clear of market
    holidays so the session count is unambiguous."""
    base = pd.Timestamp("2026-03-16")                                  # Monday
    assert prices.is_stale(_df_last_dated("2026-03-06"), asof=base) is False   # 6 sessions
    assert prices.is_stale(_df_last_dated("2026-03-05"), asof=base) is True    # 7 sessions


def test_is_stale_kalv_under_calendar_ceiling_but_stale_by_sessions():
    """REGRESSION (KALV, Chiesi M&A 2026-06): last real bar ~12 calendar / ~8
    trading days back. That is FRESH under the old 14-calendar guard (which let
    its weeks-old frozen 'breakout' ride onto the Breakouts board) but STALE
    under the trading-day gate. This is the exact leak the user reported."""
    base = pd.Timestamp("2026-06-22")
    df = _df_last_dated("2026-06-10")
    assert (base - df.index[-1]).days < prices.STALE_MAX_CALENDAR_DAYS  # 12 < 14 (old guard passed it)
    assert prices.is_stale(df, asof=base) is True                      # now excluded


def test_is_stale_empty_is_stale():
    assert prices.is_stale(pd.DataFrame()) is True
    assert prices.is_stale(None) is True


def test_stale_constant_sane():
    assert 7 <= prices.STALE_MAX_CALENDAR_DAYS <= 30
    assert 3 <= prices.STALE_MAX_TRADING_DAYS <= 10
    assert prices.STALE_MAX_TRADING_DAYS < prices.STALE_MAX_CALENDAR_DAYS
