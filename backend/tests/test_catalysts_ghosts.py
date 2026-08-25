"""Catalysts scanner — dead tickers must not ride the movers snapshot.

GFRR (2026-08-25): Massive's gainers/losers snapshot kept serving a ticker its
own reference API returns NOT_FOUND for — zero daily aggs, Yahoo 404s the
quote. Every 5-minute volume_alerts cron re-discovered it as a "mover", ran
the yfinance enrich, and logged two ERRORs. Forever.

The fix drops any mover whose ticker is in sepa.symbols.DELISTED — the
curated, evidence-carrying map — right after snapshot normalization, before
any enrichment can touch the network.

All synthetic. No network.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts import scanner as cs  # noqa: E402


def _snap(ticker: str, price: float = 5.0, change: float = 25.0) -> dict:
    return {
        "ticker": ticker,
        "day": {"c": price, "v": 2_000_000, "h": price * 1.1,
                "l": price * 0.9, "o": price},
        "prevDay": {"c": price / (1 + change / 100)},
        "lastTrade": {"p": price},
        "lastQuote": {},
        "todaysChangePerc": change,
    }


@pytest.fixture
def offline(monkeypatch):
    """No network: movers come from the test, enrich is an identity+cap stub."""
    def fake_enrich(c):
        return {**c, "market_cap": 100_000_000, "avg_volume_10d": 400_000,
                "volume_surge_ratio": 5.0, "sector": None,
                "company_name": "Test Co", "float": None}
    monkeypatch.setattr(cs, "_enrich_with_yfinance", fake_enrich)

    def set_movers(tickers):
        snaps = [_snap(t) for t in tickers]
        monkeypatch.setattr(
            cs, "_fetch_movers",
            lambda direction, limit=50: snaps if direction == "gainers" else [])
    return set_movers


def test_the_gfrr_ghost_is_dropped(offline):
    offline(["GFRR", "LIVE"])
    got = [c["ticker"] for c in cs.scan()]
    assert "GFRR" not in got
    assert "LIVE" in got


def test_every_verified_delisting_is_dropped(offline):
    from sepa import symbols as S
    dead = sorted(S.DELISTED)
    offline(dead)
    assert cs.scan() == []


def test_live_movers_pass_untouched(offline):
    """NEGATIVE: the ghost filter must not eat real movers — RYOJ-style
    obscure names are the whole point of this scanner."""
    offline(["RYOJ", "AIXI", "TNMG"])
    got = [c["ticker"] for c in cs.scan()]
    assert got and set(got) == {"RYOJ", "AIXI", "TNMG"}
