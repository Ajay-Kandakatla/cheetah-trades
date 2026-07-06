"""Coverage fixes from the 2026-07-06 stale-watchlist incident (AMBA/CRWV
served 5-week-old SOIR): the always-include universe merge, the 24h
self-heal staleness rule, and the GEX-history slim row. Negative cases
included per Rule #6 (empty sources, undated rows, missing chains)."""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from options.api import _soir_row_is_stale, SOIR_STALE_HOURS
from options.gex_history import slim_row
from options import scanner as soir_scanner


# ── universe: portfolio + file-watchlist always included ────────────────────
# portfolio.store uses py3.10 `X | None` annotations, so the local py3.9 venv
# can't import the real module (prod containers are 3.11 — fine there). The
# scanner imports it lazily inside the function, so we inject a fake module.
import types


class _FakeHoldings:
    def distinct(self, field):
        assert field == "ticker"
        return ["amba", "CRWV", ""]


class _FakeDb:
    portfolio_holdings = _FakeHoldings()


def _install_fake_portfolio(monkeypatch, get_db):
    pkg = types.ModuleType("portfolio")
    store = types.ModuleType("portfolio.store")
    store._get_db = get_db
    pkg.store = store
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.store", store)


def test_always_include_merges_portfolio_and_file_watchlist(monkeypatch):
    import sepa.scanner as sscanner
    _install_fake_portfolio(monkeypatch, lambda: _FakeDb())
    monkeypatch.setattr(sscanner, "load_watchlist",
                        lambda: [{"symbol": "mksi"}, {"symbol": None}, {}])
    syms = soir_scanner._always_include_symbols()
    assert "AMBA" in syms and "CRWV" in syms and "MKSI" in syms
    assert "" not in syms


def test_always_include_survives_dead_sources(monkeypatch):
    import sepa.scanner as sscanner
    _install_fake_portfolio(monkeypatch, lambda: None)
    monkeypatch.setattr(sscanner, "load_watchlist",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert soir_scanner._always_include_symbols() == []


def test_build_universe_contains_always_include(monkeypatch):
    _install_fake_portfolio(monkeypatch, lambda: _FakeDb())
    universe = soir_scanner._build_universe(mode="curated", max_size=5000)
    syms = {t for t, _ in universe}
    assert "AMBA" in syms and "CRWV" in syms


# ── SOIR staleness rule ──────────────────────────────────────────────────────
NOW = datetime(2026, 7, 6, 15, 0)


def test_fresh_row_is_not_stale():
    row = {"scanned_at": NOW - timedelta(hours=2)}
    assert _soir_row_is_stale(row, now=NOW) is False


def test_old_row_is_stale():
    row = {"scanned_at": NOW - timedelta(hours=SOIR_STALE_HOURS + 1)}
    assert _soir_row_is_stale(row, now=NOW) is True


def test_undated_or_garbage_row_is_stale():
    assert _soir_row_is_stale({}, now=NOW) is True
    assert _soir_row_is_stale({"scanned_at": "not-a-date"}, now=NOW) is True


def test_iso_string_timestamps_parse():
    row = {"scanned_at": (NOW - timedelta(hours=1)).isoformat()}
    assert _soir_row_is_stale(row, now=NOW) is False


# ── GEX slim row ─────────────────────────────────────────────────────────────
def test_slim_row_maps_the_opex_payload():
    out = {"spot": 795.25, "expiration_date": "2026-07-17",
           "gex_reliability": "single_name",
           "gamma": {"regime": "pinning", "net_gex_dollars": 400000,
                     "put_wall": 790, "call_wall": 1100},
           "max_pain": {"max_pain_strike": 850, "pct_from_spot": 6.9}}
    row = slim_row("mu", out, "2026-07-06")
    assert row["symbol"] == "MU" and row["date_et"] == "2026-07-06"
    assert row["regime"] == "pinning" and row["max_pain"] == 850
    assert row["mp_pct_from_spot"] == 6.9 and row["call_wall"] == 1100


def test_slim_row_no_chain_records_nothing():
    assert slim_row("XXXX", None, "2026-07-06") is None


def test_slim_row_missing_gamma_still_keeps_max_pain():
    out = {"spot": 50.0, "gamma": None,
           "max_pain": {"max_pain_strike": 48, "pct_from_spot": -4.0}}
    row = slim_row("abc", out, "2026-07-06")
    assert row["regime"] is None and row["max_pain"] == 48
