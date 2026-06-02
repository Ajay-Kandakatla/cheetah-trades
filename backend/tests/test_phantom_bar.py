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
