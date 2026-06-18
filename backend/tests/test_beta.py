"""Beta — a stock's volatility vs the market (SPY). Ajay 2026-06-17: a Beta
column on the breakouts page to sort by LOW-volatility names.

Locks the canonical cov/var-of-log-returns formula (same as
portfolio/drop_attribution._beta), the 252-bar window guard, the per-day cache,
the batch helper, and the soft-fail (a missing beta must never raise).

Run in the backend venv (py3.9):
  cd backend && .venv/bin/python -m pytest tests/test_beta.py -q
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import beta


def _series(values, start="2024-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="D"))


def _prices(values, start="2023-01-01"):
    """A price frame indexed by date, like prices.load_prices returns."""
    return pd.DataFrame({"close": values},
                        index=pd.date_range(start, periods=len(values), freq="D"))


# ── the formula ──────────────────────────────────────────────────────────────

def test_beta_of_2x_market_is_two():
    rng = np.random.RandomState(1)
    spy = _series(rng.normal(0, 0.01, 300))
    assert round(beta._beta(2.0 * spy, spy), 6) == 2.0          # amplifies 2× → β=2
    assert round(beta._beta(spy.copy(), spy), 6) == 1.0         # moves with market → β=1
    assert round(beta._beta(0.5 * spy, spy), 6) == 0.5          # half as volatile → β=0.5


def test_beta_needs_a_full_lookback_window():
    spy = _series(np.random.RandomState(2).normal(0, 0.01, 300))
    # Fewer than BETA_LOOKBACK common bars → None, never a wrong number.
    assert beta._beta(spy.iloc[:100], spy.iloc[:100]) is None


def test_beta_aligns_on_dates_not_position():
    # A later-starting stock series still aligns by DATE (inner join), not by
    # row position — the overlapping 350 dates are 2× SPY → β=2.0.
    rng = np.random.RandomState(3)
    spy = _series(rng.normal(0, 0.01, 400), start="2024-01-01")
    stock = (2.0 * spy).iloc[50:]            # 350 common dated bars (≥ lookback)
    b = beta._beta(stock, spy)
    assert b is not None and round(b, 1) == 2.0


def test_zero_variance_benchmark_is_none():
    flat = _series([0.0] * 300)
    assert beta._beta(_series(np.random.RandomState(4).normal(0, 0.01, 300)), flat) is None


# ── beta_for: cache + soft-fail ──────────────────────────────────────────────

def test_beta_for_uses_prices_and_caches(monkeypatch):
    rng = np.random.RandomState(5)
    spy_close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 400)))
    stock_close = 100 * np.exp(np.cumsum(2 * np.diff(np.log(spy_close), prepend=np.log(100))))
    loads = {"n": 0}

    def fake_load(sym, *a, **k):
        loads["n"] += 1
        return _prices(spy_close) if sym == "SPY" else _prices(stock_close)

    import sepa.prices
    monkeypatch.setattr(sepa.prices, "load_prices", fake_load)
    beta._cache.clear(); beta._spy_lr_cache.update(date=None, lr=None)

    b1 = beta.beta_for("ZZZ")
    assert b1 is not None and 1.8 < b1 < 2.2          # ~2× SPY
    n_after_first = loads["n"]
    b2 = beta.beta_for("ZZZ")                          # second call → cache, no reload
    assert b2 == b1 and loads["n"] == n_after_first


def test_beta_for_soft_fails(monkeypatch):
    import sepa.prices
    monkeypatch.setattr(sepa.prices, "load_prices", lambda *a, **k: None)
    beta._cache.clear(); beta._spy_lr_cache.update(date=None, lr=None)
    assert beta.beta_for("NOPE") is None               # no data → None, no raise
    assert beta.beta_for("") is None


def test_betas_for_batch(monkeypatch):
    rng = np.random.RandomState(6)
    spy_close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 400)))

    def fake_load(sym, *a, **k):
        if sym == "SPY":
            return _prices(spy_close)
        mult = {"AAA": 1.0, "BBB": 2.0}.get(sym, 0.5)
        return _prices(100 * np.exp(np.cumsum(mult * np.diff(np.log(spy_close), prepend=np.log(100)))))

    import sepa.prices
    monkeypatch.setattr(sepa.prices, "load_prices", fake_load)
    beta._cache.clear(); beta._spy_lr_cache.update(date=None, lr=None)

    out = beta.betas_for(["AAA", "BBB", "AAA"])         # dup collapses
    assert set(out) == {"AAA", "BBB"}
    assert 0.8 < out["AAA"] < 1.2 and 1.8 < out["BBB"] < 2.2


def test_betas_for_no_spy_is_all_none(monkeypatch):
    import sepa.prices
    monkeypatch.setattr(sepa.prices, "load_prices", lambda *a, **k: None)
    beta._cache.clear(); beta._spy_lr_cache.update(date=None, lr=None)
    assert beta.betas_for(["AAA", "BBB"]) == {"AAA": None, "BBB": None}
