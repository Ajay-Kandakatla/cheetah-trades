"""Climax-top institutional distribution (Ajay 2026-06-21: "on the climax run …
institutions sell in bulk. Track the concept").

Behavioral + regression locks for sepa.climax_distribution.detect, the
Minervini climax-top read (Think & Trade Like a Champion pp.186-188):
  * BEHAVIORAL — a climax run with a heavy-volume DOWN day reads
    "distribution underway"; churn + exhaustion-gap tells fire on the tape.
  * REGRESSION — a CLEAN climax (all up, rising volume, no heavy selling) must
    NOT read distribution (it's "climax_extended" — a watch, not a sell). This
    guards the real-money failure mode: don't scream "institutions selling" at a
    healthy strong run.
  * NEGATIVES — not climaxing → "none"; short history → no crash.

Run in the backend venv:
  cd backend && .venv/bin/python -m pytest tests/test_climax_distribution.py -q
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import climax_distribution as cd


def _df(close, high, low, vol, openp):
    n = len(close)
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    return pd.DataFrame({"open": openp, "high": high, "low": low,
                         "close": close, "volume": vol}, index=idx)


def _climax(n=130, gain=30.0):
    """Flat 100 baseline, then a clean up-ramp over the last 15 bars to
    +`gain`% — every climax bar an up day on mildly elevated volume."""
    close = np.full(n, 100.0); high = np.full(n, 100.5)
    low = np.full(n, 99.5); vol = np.full(n, 1_000_000.0); openp = np.full(n, 100.0)
    step = (100.0 * (1 + gain / 100.0) - 100.0) / 15
    for k, p in enumerate(range(n - 15, n)):
        px = 100.0 + step * (k + 1)
        close[p] = px; high[p] = px + 0.4; low[p] = px - 0.4
        openp[p] = px - step * 0.5; vol[p] = 1_200_000.0
    return close, high, low, vol, openp


def test_distribution_underway_on_heavy_volume_down_day():
    """The core tell (p.188): a climax run + a heavy-volume DOWN day = large
    investors liquidating into the strength → distribution underway."""
    close, high, low, vol, openp = _climax(gain=30.0)
    p = 130 - 4                                    # one heavy-volume down day
    close[p] = close[p - 1] - 1.5
    high[p] = close[p] + 2.0; low[p] = close[p] - 0.5; openp[p] = close[p] + 1.2
    vol[p] = 3_500_000.0
    out = cd.detect(_df(close, high, low, vol, openp))
    assert out["in_climax"] is True
    assert out["is_distribution"] is True
    assert out["read"] == "distribution_underway"
    assert out["tells"]["heavy_volume_down_day"] is True
    assert out["tells"]["largest_volume_down_in_move"] is True
    assert out["climax_gain_pct"] >= 25
    assert out["up_day_ratio"] >= 0.6


def test_clean_climax_is_not_distribution_regression():
    """REGRESSION: a clean parabolic run (all up days, rising volume, NO heavy
    selling) must read 'climax_extended' (a watch), never 'distribution'. This
    is the false-positive we must not ship on a real holding."""
    out = cd.detect(_df(*_climax(gain=35.0)))
    assert out["in_climax"] is True
    assert out["up_day_dominant"] is True
    assert out["is_distribution"] is False         # the key regression assertion
    assert out["read"] == "climax_extended"
    assert out["severity"] == 0


def test_churning_tell_fires_on_heavy_volume_no_progress():
    """Elevated volume with almost no price progress = churning (p.188)."""
    close, high, low, vol, openp = _climax(gain=28.0)
    p = 130 - 3
    close[p] = close[p - 1] * 1.001                # +0.1% — no real progress
    high[p] = close[p] + 1.5; low[p] = close[p] - 1.5; openp[p] = close[p - 1]
    vol[p] = 3_200_000.0                           # heavy
    out = cd.detect(_df(close, high, low, vol, openp))
    assert out["tells"]["churning"] is True
    assert out["is_distribution"] is True


def test_exhaustion_gap_tell_fires_on_recent_gap_up():
    """A recent gap-up open ≥3% above the prior close = exhaustion gap (p.188).
    On its own (no heavy selling) it's still a 'climax_extended' watch."""
    close, high, low, vol, openp = _climax(gain=30.0)
    p = 130 - 2
    openp[p] = close[p - 1] * 1.05                 # gap up 5%
    high[p] = openp[p] + 0.5
    out = cd.detect(_df(close, high, low, vol, openp))
    assert out["tells"]["exhaustion_gap"] is True
    assert out["read"] in ("climax_extended", "distribution_underway")


def test_not_climaxing_reads_none():
    """A mild advance (< +25% over three weeks) is not a climax — no read."""
    out = cd.detect(_df(*_climax(gain=6.0)))
    assert out["in_climax"] is False
    assert out["is_distribution"] is False
    assert out["read"] == "none"


def test_short_history_is_safe():
    n = 40
    flat = (np.full(n, 100.0), np.full(n, 100.5), np.full(n, 99.5),
            np.full(n, 1_000_000.0), np.full(n, 100.0))
    out = cd.detect(_df(*flat))
    assert out["is_distribution"] is False and out["in_climax"] is False


def test_late_stage_context_passthrough():
    out = cd.detect(_df(*_climax(gain=30.0)), {"is_late_stage": True})
    assert out["late_stage"] is True
