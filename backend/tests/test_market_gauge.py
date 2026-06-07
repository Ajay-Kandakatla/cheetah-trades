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


# ── FRED reader (the Economic pillars' source) ───────────────────────────────
def test_fred_parse_drops_missing_and_sorts_newest_first():
    from sepa import fred
    payload = {"observations": [
        {"date": "2026-01-01", "value": "100.0"},
        {"date": "2026-03-01", "value": "."},        # FRED "missing" -> dropped
        {"date": "2026-02-01", "value": "102.0"},
    ]}
    out = fred._parse_observations(payload)
    assert [d for d, _ in out] == ["2026-02-01", "2026-01-01"]   # newest-first, "." gone
    assert out[0][1] == 102.0


def test_fred_yoy_and_change_compute_from_series(monkeypatch):
    from sepa import fred
    # newest-first: data[0]=112 (latest), data[6]=106, data[12]=100 (12mo ago)
    data = [("d%02d" % (12 - i), 100.0 + (12 - i)) for i in range(13)]
    monkeypatch.setattr(fred, "_fetch", lambda sid, limit=fred._DEFAULT_LIMIT: data)
    assert fred.yoy("X") == 12.0          # (112/100 - 1) * 100
    assert fred.change("X", 6) == 6.0     # 112 - 106
    assert fred.latest("X") == 112.0


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
    # FRED T10Y3M negative -> inverted curve -> low credit + driver.
    monkeypatch.setattr(mg.fred, "latest", lambda sid: -0.4)
    comp, drv = mg._yield_curve_component()
    assert comp["points"] < round(mg.W_YIELD * 0.5)
    assert drv and "inverted" in drv
    assert mg.FRED_CURVE_SERIES in comp["basis"]


def test_yield_curve_steep_scores_high(monkeypatch):
    monkeypatch.setattr(mg.fred, "latest", lambda sid: 1.6)   # >= CURVE_STEEP
    comp, drv = mg._yield_curve_component()
    assert comp["points"] == mg.W_YIELD and drv is None


# ── FRED economic pillars (behavioral) ───────────────────────────────────────
def test_cpi_hot_inflation_scores_low(monkeypatch):
    monkeypatch.setattr(mg.fred, "yoy", lambda sid: 6.5)     # above CPI_HOT
    comp, drv = mg._cpi_component()
    assert comp["points"] <= round(mg.W_CPI * 0.1)
    assert drv and "inflation hot" in drv
    assert mg.FRED_CPI_SERIES in comp["basis"]


def test_cpi_target_inflation_scores_full(monkeypatch):
    monkeypatch.setattr(mg.fred, "yoy", lambda sid: 2.0)     # at Fed target
    comp, drv = mg._cpi_component()
    assert comp["points"] == mg.W_CPI and drv is None


def test_unemployment_rising_scores_low(monkeypatch):
    monkeypatch.setattr(mg.fred, "latest", lambda sid: 5.0)
    monkeypatch.setattr(mg.fred, "change", lambda sid, n: 0.6)   # +0.6pp/6mo (Sahm)
    comp, drv = mg._unemployment_component()
    assert comp["points"] < round(mg.W_UNEMP * 0.5)
    assert drv and "rising" in drv
    assert mg.FRED_UNEMP_SERIES in comp["basis"]


def test_unemployment_low_and_stable_scores_high(monkeypatch):
    monkeypatch.setattr(mg.fred, "latest", lambda sid: 3.6)
    monkeypatch.setattr(mg.fred, "change", lambda sid, n: -0.1)
    comp, drv = mg._unemployment_component()
    assert comp["points"] > round(mg.W_UNEMP * 0.5) and drv is None


def test_fed_funds_tightening_scores_low(monkeypatch):
    monkeypatch.setattr(mg.fred, "latest", lambda sid: 5.5)
    monkeypatch.setattr(mg.fred, "change", lambda sid, n: 1.5)   # +1.5pp/yr hiking
    comp, drv = mg._fed_funds_component()
    assert comp["points"] < round(mg.W_FEDFUNDS * 0.5)
    assert drv and "tightening" in drv
    assert mg.FRED_FEDFUNDS_SERIES in comp["basis"]


def test_fed_funds_easing_scores_high(monkeypatch):
    monkeypatch.setattr(mg.fred, "latest", lambda sid: 2.0)
    monkeypatch.setattr(mg.fred, "change", lambda sid, n: -1.5)  # cutting
    comp, drv = mg._fed_funds_component()
    assert comp["points"] > round(mg.W_FEDFUNDS * 0.5) and drv is None


def test_economic_pillars_degrade_to_neutral_without_fred(monkeypatch):
    # No FRED data (no key / fetch fail) -> neutral, never crash, basis cites FRED.
    monkeypatch.setattr(mg.fred, "latest", lambda sid: None)
    monkeypatch.setattr(mg.fred, "yoy", lambda sid: None)
    monkeypatch.setattr(mg.fred, "change", lambda sid, n: None)
    for fn, w in ((mg._cpi_component, mg.W_CPI), (mg._unemployment_component, mg.W_UNEMP),
                  (mg._fed_funds_component, mg.W_FEDFUNDS), (mg._yield_curve_component, mg.W_YIELD)):
        comp, drv = fn()
        assert comp["points"] == round(w * 0.5)        # neutral, not faked
        assert "FRED" in comp["basis"] and drv is None


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
    # Honesty: the feeds we STILL don't have (a real tape) stay listed; the
    # economic feeds are now WIRED via FRED, so they must NOT be flagged unwired.
    nw = " ".join(mg._config()["not_wired"]).lower()
    assert "order-flow" in nw or "dark-pool" in nw
    assert "cpi" not in nw and "unemployment" not in nw and "fed funds" not in nw
    assert "fred" not in nw


def test_config_exposes_fred_series():
    # The Economic pillars cite their FRED series ids (source-of-truth in config).
    fs = mg._config()["fred_series"]
    assert fs["cpi"] == "CPIAUCSL" and fs["unemployment"] == "UNRATE"
    assert fs["fed_funds"] == "FEDFUNDS" and fs["yield_curve"] == "T10Y3M"


def test_constants_locked():
    assert mg.DIST_LOOKBACK == 25 and mg.DIST_DOWN_PCT == -0.2 and mg.DIST_TOPPING == 5
    assert mg.FTD_LOOKBACK == 12 and mg.FTD_UP_PCT == 1.4
    assert mg.STATE_CONSTRUCTIVE == 67 and mg.STATE_CAUTION == 34
