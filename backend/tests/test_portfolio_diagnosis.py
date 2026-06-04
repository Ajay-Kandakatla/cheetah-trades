"""Locks the pure factor formulas in portfolio/diagnosis (Ajay 2026-06-04 —
"explain what's causing the trend: accumulation/distribution, macro, liquidity").

The module is loaded standalone (not via `import portfolio`) because the
portfolio package's FastAPI models use 3.10 union syntax that the 3.9 test venv
can't import — these pure helpers don't touch the package.
"""
import importlib.util
import os

import numpy as np
import pandas as pd

_PATH = os.path.join(os.path.dirname(__file__), "..", "portfolio", "diagnosis.py")
_spec = importlib.util.spec_from_file_location("diagnosis_mod", _PATH)
dg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dg)


def _df(n=120, up_bias=0.0, vol_spike_on_down=False, base_vol=1_000_000, price=100.0, seed=1):
    rng = np.random.default_rng(seed)
    rets = rng.normal(up_bias, 0.02, n)
    close = price * np.cumprod(1 + rets)
    vol = np.full(n, float(base_vol))
    if vol_spike_on_down:
        for i in range(1, n):
            if close[i] < close[i - 1]:
                vol[i] = base_vol * 2.5          # heavy down-volume = distribution
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                         "close": close, "volume": vol}, index=idx)


def test_volume_factors_shape():
    f = dg.volume_factors(_df())
    assert "up_down_vol_ratio" in f and "distribution_days_25" in f and "avg_dollar_vol" in f
    assert dg.volume_factors(_df(n=20)) == {}      # too short → empty


def test_distribution_pressure_flags_heavy_down_volume():
    heavy = dg.volume_factors(_df(up_bias=-0.002, vol_spike_on_down=True))
    calm = dg.volume_factors(_df(up_bias=0.003))
    h_score, h_note = dg._distribution_pressure(heavy)
    c_score, _ = dg._distribution_pressure(calm)
    assert h_score > c_score
    assert "distribution" in h_note.lower() or "down-volume" in h_note.lower()


def test_liquidity_pressure_bands():
    thin = dg._liquidity_pressure({"avg_dollar_vol": 2_000_000})
    deep = dg._liquidity_pressure({"avg_dollar_vol": 500_000_000})
    assert thin[0] > deep[0]                       # thin name = higher liquidity risk
    assert deep[0] <= 10


def test_trend_health_rewards_stage2_leader():
    healthy = dg._trend_health({"stage": {"stage": 2}, "rs_rank": 90})
    broken = dg._trend_health({"stage": {"stage": 4}, "rs_rank": 25})
    assert healthy[0] > broken[0]
    assert healthy[0] >= 65 and broken[0] <= 35


def test_no_volume_data_is_safe():
    assert dg._distribution_pressure({})[0] == 0
    assert dg._liquidity_pressure({})[0] == 0
