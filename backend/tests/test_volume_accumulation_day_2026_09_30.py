"""sepa.volume.accumulation_day — the ONE accumulation-day test (2026-09-30).

The 🛡️ Resiliency tab's 📈 bullish-EOD-tape read needs a single-bar version of
the accumulation day `_count_accum_dist_days` counts. The inline test was
extracted into `accumulation_day` — a behaviour-identical refactor. The golden
counts below were captured on the UNEDITED code (before the extraction) on
seeded synthetic frames, incl. flat bars, equal closes and volume == average.
"""
from __future__ import annotations

import inspect
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sepa import volume as V  # noqa: E402


def _frame(seed, n=120, flat_every=0, eq_every=0, avg_hits=False):
    rng = np.random.default_rng(seed)
    c = np.round(50 * np.cumprod(1 + rng.normal(0, 0.02, n)), 2)
    if eq_every:
        for i in range(eq_every, n, eq_every):
            c[i] = c[i - 1]
    hi = np.round(c * (1 + rng.uniform(0, 0.03, n)), 2)
    lo = np.round(c * (1 - rng.uniform(0, 0.03, n)), 2)
    if flat_every:
        for i in range(flat_every, n, flat_every):
            hi[i] = lo[i] = c[i]
    v = rng.integers(500_000, 2_000_000, n).astype(float)
    if avg_hits:
        av = float(pd.Series(v).iloc[-(25 + 51):-25].mean())
        for i in range(n - 20, n, 3):
            v[i] = av
    idx = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({"open": c, "high": hi, "low": lo, "close": c, "volume": v}, index=idx)


# Captured 2026-09-30 on the code BEFORE accumulation_day existed.
GOLDEN = {
    "plain_1": ((1, {}), (5, 6)),
    "plain_2": ((2, {}), (1, 3)),
    "plain_3": ((3, {"n": 300}), (4, 5)),
    "flat_bars": ((4, {"flat_every": 3}), (1, 2)),
    "equal_closes": ((5, {"eq_every": 2}), (1, 0)),
    "v_eq_avg": ((6, {"avg_hits": True}), (3, 7)),
    "short_45": ((7, {"n": 45}), (1, 9)),
    "short_29": ((8, {"n": 29}), (0, 0)),
    "mixed": ((9, {"flat_every": 5, "eq_every": 4, "avg_hits": True}), (0, 2)),
}


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_golden_counts_unchanged(name):
    (seed, kw), (acc, dist) = GOLDEN[name]
    out = V._count_accum_dist_days(_frame(seed, **kw))
    assert out == {"accumulation_days_25": acc, "distribution_days_25": dist}


def test_accumulation_day_positive():
    assert V.accumulation_day(10.5, 10.0, 10.6, 10.0, 2_000_000, 1_000_000) is True


def test_upper_half_boundary_is_inclusive():
    # close exactly at the midpoint: (10.3-10.0)/(10.6-10.0) == 0.5
    assert V.accumulation_day(10.3, 10.0, 10.6, 10.0, 2.0, 1.0) is True


def test_negative_equal_close_is_not_up():
    assert V.accumulation_day(10.0, 10.0, 10.6, 9.9, 2.0, 1.0) is False


def test_negative_down_close():
    assert V.accumulation_day(9.9, 10.0, 10.0, 9.5, 2.0, 1.0) is False


def test_negative_lower_half():
    assert V.accumulation_day(10.1, 10.0, 10.6, 10.0, 2.0, 1.0) is False


def test_negative_volume_equal_to_average_is_not_above():
    assert V.accumulation_day(10.5, 10.0, 10.6, 10.0, 1_000_000, 1_000_000) is False


def test_negative_flat_bar_never_counts():
    assert V.accumulation_day(10.5, 10.0, 10.5, 10.5, 9e9, 1.0) is False


def test_counter_calls_the_one_engine():
    src = inspect.getsource(V._count_accum_dist_days)
    assert "accumulation_day(" in src
    assert "upper_half and v_today > avg_vol" not in src


def test_mutation_in_engine_changes_counter(monkeypatch):
    """The counter really routes through accumulation_day (not a stale copy)."""
    df = _frame(1)
    monkeypatch.setattr(V, "accumulation_day", lambda *a, **k: False)
    assert V._count_accum_dist_days(df)["accumulation_days_25"] == 0
