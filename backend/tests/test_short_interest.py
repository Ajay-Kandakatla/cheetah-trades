"""Contracts for short-interest squeeze gauges (short_interest/client.py).

Pure logic — fetchers are monkeypatched, no network. Locks the pct-primary
squeeze label and the percent-of-shares / days-to-cover / trend computation.
"""
from __future__ import annotations

from short_interest import client


def test_squeeze_signal_is_pct_primary():
    # Mega-cap: <1% short, moderate days-to-cover → must NOT flag (can't squeeze)
    assert client._squeeze_signal(0.94, 2.74) == "low"
    # Genuinely elevated short interest
    assert client._squeeze_signal(12.91, 4.16) == "elevated"
    # Very high short %
    assert client._squeeze_signal(25.0, 1.0) == "high"
    # Elevated short % that's also hard to cover → high
    assert client._squeeze_signal(12.0, 6.0) == "high"
    # Mid short % + hard to cover → elevated
    assert client._squeeze_signal(6.0, 6.0) == "elevated"
    # Mid short % + easy to cover → low
    assert client._squeeze_signal(6.0, 2.0) == "low"


def test_squeeze_signal_dtc_only_fallback():
    assert client._squeeze_signal(None, 6.0) == "elevated"
    assert client._squeeze_signal(None, 1.0) == "low"


def test_short_interest_for_computes(monkeypatch):
    monkeypatch.setattr(client, "_fetch_short_interest_rows", lambda s, limit=4: [
        {"settlement_date": "2026-05-15", "short_interest": 1000, "avg_daily_volume": 500, "days_to_cover": 2.0},
        {"settlement_date": "2026-04-30", "short_interest": 800, "avg_daily_volume": 400, "days_to_cover": 2.0},
    ])
    monkeypatch.setattr(client, "_shares_outstanding", lambda s: 10000)
    d = client.short_interest_for("FOO")
    assert d["short_interest"] == 1000
    assert d["pct_of_shares"] == 10.0          # 1000 / 10000 * 100
    assert d["days_to_cover"] == 2.0
    assert d["si_change_pct"] == 25.0          # (1000 - 800) / 800 * 100
    assert d["prev_settlement_date"] == "2026-04-30"
    assert d["squeeze"] == "elevated"          # pct == 10 → elevated


def test_short_interest_for_none_when_no_record(monkeypatch):
    monkeypatch.setattr(client, "_fetch_short_interest_rows", lambda s, limit=4: [])
    assert client.short_interest_for("FOO") is None


def test_short_interest_for_handles_missing_shares(monkeypatch):
    monkeypatch.setattr(client, "_fetch_short_interest_rows", lambda s, limit=4: [
        {"settlement_date": "2026-05-15", "short_interest": 1000, "avg_daily_volume": 500, "days_to_cover": 6.0},
    ])
    monkeypatch.setattr(client, "_shares_outstanding", lambda s: None)
    d = client.short_interest_for("FOO")
    assert d["pct_of_shares"] is None
    assert d["si_change_pct"] is None          # no prior settlement
    assert d["squeeze"] == "elevated"          # no pct, dtc 6 ≥ HIGH_DTC
