"""Tests for the FRED macro dashboard (backend/macro_indicators.py + the
fred.yoy_history / level_history helpers it uses).

Synthetic observation series → assert the value / prior / change / direction /
trend-orientation / date-label logic, with NO network. Guards the "how it's
changing" math the Market Gauge page renders.
"""
import macro_indicators as mi
from sepa import fred

CFG_YOY = {"id": "cpi", "series": "CPIAUCSL", "label": "CPI", "blurb": "x",
           "unit": "%", "good": "down", "transform": "yoy", "freq": "monthly",
           "release": "cpi"}
CFG_LEVEL = {"id": "unrate", "series": "UNRATE", "label": "Unemp", "blurb": "y",
             "unit": "%", "good": "down", "transform": "level", "freq": "monthly",
             "release": "jobs"}
CFG_DAILY = {"id": "yield_curve", "series": "T10Y3M", "label": "Curve", "blurb": "z",
             "unit": "%", "good": "up", "transform": "level", "freq": "daily",
             "release": None}


def test_assemble_yoy_value_change_direction_and_labels():
    hist = [("2026-04-01", 3.4), ("2026-03-01", 3.1), ("2026-02-01", 3.0)]
    ind = mi._assemble(CFG_YOY, hist, "2026-06-10")
    assert ind["value"] == 3.4 and ind["prev"] == 3.1
    assert ind["change"] == 0.3 and ind["direction"] == "up"
    assert ind["as_of_label"] == "Apr 2026"            # monthly → month label
    assert ind["next_release_label"] == "Jun 10"
    assert ind["trend"] == [3.0, 3.1, 3.4]             # oldest → newest for sparkline


def test_assemble_level_falling_is_negative_change():
    hist = [("2026-05-01", 4.2), ("2026-04-01", 4.4)]
    ind = mi._assemble(CFG_LEVEL, hist, None)
    assert ind["change"] == -0.2 and ind["direction"] == "down"
    assert ind["next_release_label"] is None


def test_assemble_daily_keeps_full_date():
    hist = [("2026-06-08", 0.76), ("2026-06-07", 0.77)]
    ind = mi._assemble(CFG_DAILY, hist, None)
    assert ind["as_of_label"] == "2026-06-08"          # daily → no month collapse


def test_assemble_empty_history_returns_none():
    assert mi._assemble(CFG_YOY, [], None) is None


def test_assemble_single_point_has_no_change():
    ind = mi._assemble(CFG_YOY, [("2026-04-01", 3.4)], None)
    assert ind["prev"] is None and ind["change"] is None and ind["direction"] == "flat"


def test_fred_yoy_history_computes_year_over_year(monkeypatch):
    # newest-first values: idx0=110, idx1=105, … idx12=idx13=100. YoY pairs
    # idx i with idx i+12, so two computable points: 110/100-1 and 105/100-1.
    vals = [110.0, 105.0] + [100.0] * 12          # len 14
    data = [("2026-d%02d" % i, vals[i]) for i in range(14)]
    monkeypatch.setattr(fred, "_fetch", lambda s, limit=24: list(data))
    h = fred.yoy_history("X", points=24)
    assert len(h) == 2
    assert h[0][1] == 10.0 and h[1][1] == 5.0


def test_fred_level_history_truncates_to_points(monkeypatch):
    data = [("2026-d%02d" % i, float(i)) for i in range(30)]
    monkeypatch.setattr(fred, "_fetch", lambda s, limit=24: list(data))
    h = fred.level_history("X", points=10)
    assert len(h) == 10 and h[0][1] == 0.0
