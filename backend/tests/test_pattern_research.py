"""Locks the pattern-research engine (sepa/pattern_research).

The engine splits the scanned universe into bullish/bearish cohorts by trailing
3-month return and measures each signal's prevalence per cohort. These tests pin
the cohort math, the lift computation, and a couple of pattern predicates on
synthetic data (no network, no Mongo). Ajay 2026-06-04.
"""
import numpy as np
import pandas as pd

import sepa.pattern_research as pr


def _df(n=260, drift=0.001, vol=0.02, seed=1):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    close = 100 * np.cumprod(1 + rets)
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    return pd.DataFrame({"open": close, "high": close * 1.01,
                         "low": close * 0.99, "close": close,
                         "volume": 1_000_000}, index=idx)


def test_price_features_uptrend():
    f = pr.price_features(_df(drift=0.004))   # strong uptrend
    assert f is not None
    assert f["ret_3m"] > 0
    assert f["above_200dma"] is True
    assert f["pct_below_high"] is not None


def test_price_features_too_short_is_none():
    assert pr.price_features(_df(n=50)) is None
    assert pr.price_features(None) is None


def test_nested_get():
    rec = {"volume": {"vol_dryup": 0.6}, "stage": {"stage": 2}}
    assert pr._g(rec, "volume.vol_dryup") == 0.6
    assert pr._g(rec, "stage.stage") == 2
    assert pr._g(rec, "missing.path") is None
    assert pr._g(rec, "volume.nope") is None


def test_pattern_predicate_none_when_missing():
    # rs_strong predicate returns None when rs_rank absent → excluded from stats
    rs_strong = next(p for p in pr.PATTERNS if p["key"] == "rs_strong")
    assert rs_strong["fn"]({}) is None
    assert rs_strong["fn"]({"rs_rank": 90}) is True
    assert rs_strong["fn"]({"rs_rank": 50}) is False


def test_analyze_splits_cohorts_by_return_and_computes_lift():
    # 30 synthetic stocks: 10 strong up, 10 flat, 10 down. Attach an rs_rank that
    # tracks the trend so rs_strong should show a big positive lift.
    records = []
    loaders = {}
    for i in range(30):
        if i < 10:
            drift, rs = 0.005, 95        # winners
        elif i < 20:
            drift, rs = 0.0, 60          # middle
        else:
            drift, rs = -0.004, 20       # losers
        sym = f"S{i}"
        records.append({"symbol": sym, "rs_rank": rs})
        loaders[sym] = _df(drift=drift, seed=i + 1)

    res = pr.analyze(records, lambda s: loaders.get(s))
    assert res["ok"] is True
    assert res["universe_n"] == 30
    assert res["cohort_n"] == 10

    rows = {r["key"]: r for r in res["all_patterns"]}
    # RS strong must be a clear bullish tell (high in winners, ~0 in losers).
    rs = rows["rs_strong"]
    assert rs["bull_pct"] > rs["bear_pct"]
    assert rs["lift"] > 50
    # And it should be sorted into the bullish list, not bearish.
    assert any(r["key"] == "rs_strong" for r in res["bullish_patterns"])


def test_analyze_guards_small_universe():
    res = pr.analyze([{"symbol": "A"}], lambda s: _df())
    assert res["ok"] is False
    assert res["reason"] == "not_enough_history"
