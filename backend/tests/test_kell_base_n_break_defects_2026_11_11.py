"""Kell Base n' Break — formulas audit 2026-11-10 defect D12 (step F1).

D12: "missing = not dry", fail closed. One NaN volume in the 50-bar baseline
made `avg_vol` NaN; every NaN comparison is False, so the volume-dry gate and
the breakout-volume gate both PASSED and the name was listed (and could reach
the nightly `setup_base_n_break` push). The fix returns None when `avg_vol` or
`vol_mult` is not finite. Every base window (<= _BASE_MAX_LEN bars ending
yesterday) lies inside the `_AVG_VOL_WINDOW` baseline, so a NaN base volume is
caught by the `avg_vol` check: ONE pinned outcome, None.

Frames = the audit demo `L4/demo_kell_voldry.py` (same shape, rebuilt here so
the test does not read the audit folder). `sepa.prices.load_prices` is
monkeypatched; no network, no Mongo.

The fix can only REMOVE a listed name, never add one: the finite frames
(DRY listed, WET None) are pinned unchanged.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from kell import base_n_break as bnb

N_UP = 110
N_BASE = 15


def _frame(base_vol, today_vol=3000.0, n_up=N_UP, n_base=N_BASE, run_vol=1000.0):
    closes = [50 * 1.004 ** i for i in range(n_up)]
    top = closes[-1]
    closes += [top * (1 + 0.002 * ((i % 3) - 1)) for i in range(n_base)]
    closes.append(top * 1.012)
    c = np.array(closes)
    h = c * 1.003
    lo = c * 0.997
    v = np.array([run_vol] * n_up + list(base_vol) + [today_vol], dtype=float)
    return pd.DataFrame({"open": c, "high": h, "low": lo, "close": c, "volume": v})


@pytest.fixture
def frames(monkeypatch):
    store: dict[str, pd.DataFrame] = {}
    import sepa.prices as prices
    monkeypatch.setattr(prices, "load_prices", lambda sym, period="6mo": store[sym])
    return store


def _dry():
    return [500.0] * N_BASE


# ── finite frames: unchanged ────────────────────────────────────────────────

def test_dry_base_still_listed_unchanged(frames):
    frames["DRY"] = _frame(_dry())
    r = bnb._detect("DRY")
    assert r is not None
    assert r["meta"]["base_len"] == 15
    assert r["meta"]["pivot"] == 77.645
    assert r["trigger"] == 77.655
    assert r["meta"]["vol_dry_ratio"] == 0.59
    assert r["meta"]["breakout_vol_mult"] == 3.53
    assert all(math.isfinite(x) for x in (r["trigger"], r["stop"], r["target"]))


def test_wet_base_still_none(frames):
    frames["WET"] = _frame([1000.0] * N_BASE)
    assert bnb._detect("WET") is None


# ── NEGATIVES: missing volume = not dry ─────────────────────────────────────

def test_negative_demo_nan_base_bar_is_none(frames):
    """The audit demo NAN frame (1.0x base, NaN at base bar 7): was listed
    with vol_dry_ratio nan / breakout_vol_mult nan; now None, exactly."""
    v = [1000.0] * N_BASE
    v[7] = float("nan")
    frames["NAN"] = _frame(v)
    assert bnb._detect("NAN") is None


def test_negative_nan_inside_dry_base_is_none(frames):
    """A dry base with ONE NaN bar is not proven dry: None, never listed."""
    v = _dry()
    v[7] = float("nan")
    frames["NAND"] = _frame(v)
    assert bnb._detect("NAND") is None


def test_negative_nan_thirty_bars_back_is_none(frames):
    """NaN inside the 50-bar baseline but outside every base window."""
    df = _frame(_dry())
    idx = len(df) - 1 - 30
    assert idx < len(df) - 1 - bnb._BASE_MAX_LEN
    assert idx >= len(df) - 1 - bnb._AVG_VOL_WINDOW
    df.loc[idx, "volume"] = float("nan")
    frames["NAN30"] = df
    assert bnb._detect("NAN30") is None


def test_negative_nan_today_volume_is_none(frames):
    """A NaN breakout-bar volume is not expansion."""
    frames["NANT"] = _frame(_dry(), today_vol=float("nan"))
    assert bnb._detect("NANT") is None


def test_negative_inf_today_volume_is_none(frames):
    """isfinite, not isnan: an inf breakout volume is bad data, not expansion."""
    frames["INFT"] = _frame(_dry(), today_vol=float("inf"))
    assert bnb._detect("INFT") is None


def test_negative_nan_before_baseline_does_not_drop(frames):
    """A NaN OUTSIDE the 50-bar baseline is never read: still listed, same
    pivot — the guard only fires on volume the gates actually use."""
    df = _frame(_dry())
    idx = len(df) - 1 - bnb._AVG_VOL_WINDOW - 5
    df.loc[idx, "volume"] = float("nan")
    frames["OLD"] = df
    r = bnb._detect("OLD")
    assert r is not None
    assert r["meta"]["base_len"] == 15
    assert r["meta"]["pivot"] == 77.645


def test_constants_untouched():
    assert bnb._BASE_VOL_DRY_RATIO == 0.85
    assert bnb._BREAKOUT_VOL_MULT == 1.3
    assert bnb._AVG_VOL_WINDOW == 50
    assert bnb._BASE_MAX_LEN == 15
