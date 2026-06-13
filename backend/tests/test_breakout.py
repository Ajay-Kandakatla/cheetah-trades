"""Breakout leaders board — ranks names by breakout count, drops names without
one. (The count itself is tested in test_volume_spark.py.)"""
from __future__ import annotations

from sepa import breakout, scanner


def test_leaders_sort_desc_and_drop_missing(monkeypatch):
    fake = {
        "generated_at": 123,
        "all_results": [
            {"symbol": "AAA", "last_close": 10,
             "volume": {"breakout_count": 2, "breakout_window_bars": 252,
                        "last_vol": 1000, "avg_vol_50": 500}},
            {"symbol": "BBB", "last_close": 20,
             "volume": {"breakout_count": 9, "breakout_window_bars": 252,
                        "last_vol": 3000, "avg_vol_50": 1000}},
            {"symbol": "CCC", "last_close": 30, "volume": {}},          # no count → dropped
            {"symbol": "DDD", "last_close": 40, "volume": None},        # no volume → dropped
        ],
    }
    monkeypatch.setattr(scanner, "load_latest", lambda: fake)
    out = breakout.leaders(top=10)
    assert [r["symbol"] for r in out["rows"]] == ["BBB", "AAA"]
    assert out["rows"][0]["breakout_count"] == 9
    assert out["n"] == 2


def test_leaders_empty_scan_is_safe(monkeypatch):
    monkeypatch.setattr(scanner, "load_latest", lambda: {})
    out = breakout.leaders()
    assert out["rows"] == [] and out["n"] == 0
