"""Behavioral + regression tests for the Market Gauge.

Book: Minervini, *Trade Like a Stock Market Wizard* (2013), pp.79, 248,
303-305; Ch.5/12-13. See docs/sepa/market_gauge_methodology.md.

Synthetic — the index distribution/follow-through helpers run on built frames;
the composition is tested by monkeypatching the component helpers so we assert
the SCORING, not live market data.
"""
import numpy as np
import pandas as pd

from sepa import market_gauge as mg


def _df(closes, vols):
    idx = pd.date_range("2025-01-01", periods=len(closes), freq="B")
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {"open": c, "high": c * 1.001, "low": c * 0.999, "close": c,
         "volume": np.asarray(vols, dtype=float)},
        index=idx,
    )


# ── price-signal helpers ─────────────────────────────────────────────────────
def test_distribution_count_flags_higher_volume_down_days():
    n = 40
    closes = list(np.linspace(100.0, 110.0, n))   # gentle uptrend (mostly up days)
    vols = [1_000_000.0] * n
    for i in (35, 38):                            # force 2 distribution days
        closes[i] = closes[i - 1] * 0.995         # ~-0.5% down close
        vols[i] = vols[i - 1] * 1.5               # on higher volume
    cnt = mg._distribution_count(_df(closes, vols), lookback=25)
    assert cnt is not None and cnt >= 2


def test_distribution_count_zero_in_quiet_uptrend():
    n = 40
    closes = list(np.linspace(100.0, 110.0, n))
    vols = [1_000_000.0] * n
    assert mg._distribution_count(_df(closes, vols), lookback=25) == 0


def test_follow_through_detects_power_up_day():
    n = 70
    closes = list(np.linspace(90.0, 100.0, n))    # above the 50-day near the end
    vols = [1_000_000.0] * n
    i = 66
    closes[i] = closes[i - 1] * 1.02              # +2% up close
    vols[i] = vols[i - 1] * 1.6                   # on higher volume
    assert mg._follow_through(_df(closes, vols), lookback=12) is True


def test_follow_through_false_when_no_power_day():
    n = 70
    closes = list(np.linspace(90.0, 100.0, n))    # ~+0.16%/day, never >= 1.4%
    vols = [1_000_000.0] * n
    assert mg._follow_through(_df(closes, vols), lookback=12) is False


# ── composition (monkeypatch the component helpers) ──────────────────────────
def _patch(monkeypatch, *, trend, level, breadth, dist, ftd, score=None):
    monkeypatch.setattr(mg, "_trend_state", lambda: (trend, {}))
    monkeypatch.setattr(mg, "_macro_level", lambda: (level, score))
    monkeypatch.setattr(mg, "_breadth_red_pct", lambda: breadth)
    monkeypatch.setattr(mg, "_index_distribution", lambda: dist)
    monkeypatch.setattr(mg, "_index_follow_through", lambda: ftd)


def test_compute_constructive(monkeypatch):
    _patch(monkeypatch, trend="confirmed_uptrend", level="low", breadth=30, dist=0, ftd=True, score=10)
    out = mg.compute()
    assert out["state"] == "constructive"
    assert out["score"] >= mg.STATE_CONSTRUCTIVE
    assert out["exposure_band"]["high"] == 100
    assert {c["key"] for c in out["components"]} == {
        "trend", "regime", "breadth", "distribution", "follow_through"}


def test_compute_risk_off(monkeypatch):
    _patch(monkeypatch, trend="caution", level="severe", breadth=80, dist=7, ftd=False, score=90)
    out = mg.compute()
    assert out["state"] == "risk_off"
    assert out["score"] < mg.STATE_CAUTION
    assert out["exposure_band"]["low"] == 0


def test_compute_caution_is_in_the_middle(monkeypatch):
    _patch(monkeypatch, trend="mixed", level="elevated", breadth=52, dist=3, ftd=False, score=40)
    out = mg.compute()
    assert out["state"] == "caution"
    assert mg.STATE_CAUTION <= out["score"] < mg.STATE_CONSTRUCTIVE


# ── constants ────────────────────────────────────────────────────────────────
def test_weights_sum_to_100():
    assert (mg.W_TREND + mg.W_REGIME + mg.W_BREADTH
            + mg.W_DISTRIBUTION + mg.W_FOLLOW_THROUGH) == 100


def test_constants_locked():
    assert mg.DIST_LOOKBACK == 25
    assert mg.DIST_DOWN_PCT == -0.2
    assert mg.DIST_TOPPING == 5
    assert mg.FTD_LOOKBACK == 12
    assert mg.FTD_UP_PCT == 1.4
    assert mg.STATE_CONSTRUCTIVE == 67
    assert mg.STATE_CAUTION == 34
