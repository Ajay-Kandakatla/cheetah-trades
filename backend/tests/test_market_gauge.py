"""Behavioral + regression tests for the multi-pillar Market Gauge.

Book: Minervini, *Trade Like a Stock Market Wizard* (2013), pp.79, 248,
303-305; Ch.5/12-13. See docs/sepa/market_gauge_methodology.md.

Synthetic — the index price helpers run on built frames; the composition is
tested by swapping the PILLARS tuple / monkeypatching scan rows so we assert the
SCORING and the graceful-degradation, not live market data.
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


def _fake_pillar(points, key="x", drv=None):
    def f():
        return ({"key": key, "category": "T", "label": key, "value": "v",
                 "points": points, "max": points or 1, "basis": "b"}, drv)
    return f


# ── index price helpers ──────────────────────────────────────────────────────
def test_distribution_count_flags_higher_volume_down_days():
    n = 40
    closes = list(np.linspace(100.0, 110.0, n))
    vols = [1_000_000.0] * n
    for i in (35, 38):
        closes[i] = closes[i - 1] * 0.995
        vols[i] = vols[i - 1] * 1.5
    assert mg._distribution_count(_df(closes, vols), lookback=25) >= 2


def test_follow_through_detects_power_up_day():
    n = 70
    closes = list(np.linspace(90.0, 100.0, n))
    vols = [1_000_000.0] * n
    closes[66] = closes[65] * 1.02
    vols[66] = vols[65] * 1.6
    assert mg._follow_through(_df(closes, vols), lookback=12) is True


def test_treasury_yield_normalizes_x10_quote(monkeypatch):
    # yfinance sometimes quotes ^TNX as 42.5 (= 4.25%); we normalise /10.
    monkeypatch.setattr(mg.prices, "load_prices", lambda s: _df([40.0, 42.5], [0, 0]))
    assert mg._treasury_yield("^TNX") == 4.25
    monkeypatch.setattr(mg.prices, "load_prices", lambda s: _df([4.1, 4.25], [0, 0]))
    assert mg._treasury_yield("^TNX") == 4.25


# ── aggregating pillars (real shape, synthetic rows) ─────────────────────────
def test_flow_component_aggregates_scan(monkeypatch):
    rows = [{"volume": {"net_dollar_vol_50": 1e6, "cmf_20": 0.3}},
            {"volume": {"net_dollar_vol_50": 5e5, "cmf_20": 0.2}}]
    monkeypatch.setattr(mg, "_scan_rows", lambda: rows)
    comp, _ = mg._flow_component()
    assert comp["key"] == "flow" and comp["max"] == mg.W_FLOW
    assert comp["points"] > round(mg.W_FLOW * 0.5)        # net inflow -> above neutral


def test_insider_component_counts_cluster_buys(monkeypatch):
    rows = [{"insider": {"cluster_buy": True}}, {"insider": {"cluster_buy": True}},
            {"insider": {"cluster_sell": True}}]
    monkeypatch.setattr(mg, "_scan_rows", lambda: rows)
    comp, drv = mg._insider_component()
    assert "2 buys" in comp["value"]
    assert comp["points"] >= round(mg.W_INSIDER * 0.5)    # net buyers


def test_yield_curve_inverted_scores_low(monkeypatch):
    # 10y below 3m -> inverted -> low credit + driver.
    monkeypatch.setattr(mg, "_treasury_yield",
                        lambda s: 3.5 if s == "^TNX" else 4.5)
    comp, drv = mg._yield_curve_component()
    assert comp["points"] < round(mg.W_YIELD * 0.5)
    assert drv and "inverted" in drv


# ── composition + state ──────────────────────────────────────────────────────
def test_compute_sums_pillars_constructive(monkeypatch):
    monkeypatch.setattr(mg, "PILLARS", (_fake_pillar(70, "a"), _fake_pillar(25, "b", "up")))
    out = mg.compute()
    assert out["score"] == 95 and out["state"] == "constructive"
    assert out["exposure_band"]["high"] == 100
    assert len(out["components"]) == 2 and out["drivers"] == ["up"]


def test_compute_risk_off(monkeypatch):
    monkeypatch.setattr(mg, "PILLARS", (_fake_pillar(10, "a"), _fake_pillar(15, "b")))
    out = mg.compute()
    assert out["score"] == 25 and out["state"] == "risk_off"
    assert out["exposure_band"]["low"] == 0


def test_compute_caution_is_in_the_middle(monkeypatch):
    monkeypatch.setattr(mg, "PILLARS", (_fake_pillar(30, "a"), _fake_pillar(20, "b")))
    out = mg.compute()
    assert out["state"] == "caution"
    assert mg.STATE_CAUTION <= out["score"] < mg.STATE_CONSTRUCTIVE


def test_compute_survives_a_bad_pillar(monkeypatch):
    def boom():
        raise ValueError("data feed down")
    monkeypatch.setattr(mg, "PILLARS", (_fake_pillar(50, "a"), boom))
    out = mg.compute()
    assert out["score"] == 50          # bad pillar skipped, gauge still computes
    assert len(out["components"]) == 1


# ── constants / honesty ──────────────────────────────────────────────────────
def test_weights_sum_to_100():
    assert sum(mg._config()["weights"].values()) == 100


def test_config_flags_unwired_feeds():
    # Honesty: feeds we don't have are listed, not silently faked.
    nw = " ".join(mg._config()["not_wired"]).lower()
    assert "fred" in nw or "cpi" in nw
    assert "order-flow" in nw or "dark-pool" in nw


def test_constants_locked():
    assert mg.DIST_LOOKBACK == 25 and mg.DIST_DOWN_PCT == -0.2 and mg.DIST_TOPPING == 5
    assert mg.FTD_LOOKBACK == 12 and mg.FTD_UP_PCT == 1.4
    assert mg.STATE_CONSTRUCTIVE == 67 and mg.STATE_CAUTION == 34
