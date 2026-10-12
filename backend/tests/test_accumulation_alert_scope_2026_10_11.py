"""The Sunday accumulation push must watch the names Ajay actually holds.

Measured 2026-10-11: `python -m supply_demand.accumulation_changes` printed
sweep {scanned: 1, compared: 1}. `_alert_symbols()` read only the manual
holdings store (one row, WULX) and the SEPA file watchlist (empty). The live
book is the Plaid -> Fidelity link, keyed by security_id, and his watchlist is
the Mongo list behind /watchlist — neither was read.

Every store is monkeypatched here; nothing touches Mongo or the network.
"""
from __future__ import annotations

import importlib.util
import logging
import sys
import types
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import auth  # noqa: E402
from sepa import scanner  # noqa: E402
from supply_demand import accumulation_changes as ac  # noqa: E402
from watchlist import store as wstore  # noqa: E402

OWNER = "owner@example.com"


def _load_plaid_store():
    """The real plaid_store.py, loaded by path. The `portfolio` package's
    __init__ loads its FastAPI router (py3.10 annotations), which the host
    py3.9 venv cannot import — plaid_store itself is stdlib-only."""
    spec = importlib.util.spec_from_file_location(
        "_plaid_store_under_test", BACKEND / "portfolio" / "plaid_store.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plaid_store = _load_plaid_store()


def _plaid_resp(*rows):
    """rows: (security_id, ticker, type, is_cash_equivalent) — Plaid's shape,
    where the holding carries only the security_id."""
    return {
        "holdings": [{"security_id": sid, "quantity": 1} for sid, *_ in rows],
        "securities": [{"security_id": sid, "ticker_symbol": t, "type": ty,
                        "is_cash_equivalent": cash} for sid, t, ty, cash in rows],
    }


@pytest.fixture
def sources(monkeypatch):
    """Four stand-in sources; each test overrides what it needs."""
    state = {"plaid": ["RCAT", "APLD"], "manual": [{"ticker": "WULX"}],
             "watchlist": [{"ticker": "MU"}, {"ticker": "ARM"}], "sepa": [],
             "calls": []}

    def _held(email):
        state["calls"].append(("plaid", email))
        v = state["plaid"]
        if isinstance(v, Exception):
            raise v
        return v

    def _manual(email):
        state["calls"].append(("manual", email))
        v = state["manual"]
        if isinstance(v, Exception):
            raise v
        return v

    def _watch():
        v = state["watchlist"]
        if isinstance(v, Exception):
            raise v
        return v

    # portfolio stand-in (see _load_plaid_store for why not the real package).
    pkg = types.ModuleType("portfolio")
    pkg.plaid_store = types.ModuleType("portfolio.plaid_store")
    pkg.plaid_store.held_tickers = _held
    pkg.store = types.ModuleType("portfolio.store")
    pkg.store.list_holdings = _manual
    monkeypatch.setitem(sys.modules, "portfolio", pkg)
    monkeypatch.setitem(sys.modules, "portfolio.plaid_store", pkg.plaid_store)
    monkeypatch.setitem(sys.modules, "portfolio.store", pkg.store)
    monkeypatch.setattr(auth, "HOUSE_OWNER_EMAILS", [OWNER])
    monkeypatch.setattr(wstore, "list_entries", _watch)
    monkeypatch.setattr(scanner, "load_watchlist", lambda: state["sepa"])
    return state


# ---------------------------------------------------------------------------
# the union
# ---------------------------------------------------------------------------
def test_scope_is_plaid_then_manual_then_watchlist(sources):
    assert ac._alert_symbols() == ["RCAT", "APLD", "WULX", "MU", "ARM"]
    assert ("plaid", OWNER) in sources["calls"]
    assert ("manual", OWNER) in sources["calls"]


def test_the_sepa_file_watchlist_is_still_read(sources):
    sources["sepa"] = [{"symbol": "nvda"}]
    assert ac._alert_symbols()[-1] == "NVDA"


def test_an_explicit_email_beats_the_house_owner(sources):
    ac._alert_symbols("other@example.com")
    assert ("plaid", "other@example.com") in sources["calls"]
    assert ("plaid", OWNER) not in sources["calls"]


def test_duplicates_across_and_within_sources_appear_once(sources):
    sources["plaid"] = ["RCAT", "RCAT", " mu "]
    sources["manual"] = [{"ticker": "rcat"}, {"symbol": "MU"}]
    sources["watchlist"] = [{"ticker": "MU"}, {"ticker": "ARM"}, {"ticker": "arm"}]
    assert ac._alert_symbols() == ["RCAT", "MU", "ARM"]


# ---------------------------------------------------------------------------
# non-tickers
# ---------------------------------------------------------------------------
def test_dollar_positions_are_skipped(sources):
    sources["plaid"] = ["$BTC.LP.IDX.2055.H", "RCAT"]
    sources["manual"] = [{"ticker": "$RESTRICTED.STOCK.UNITS"}, {"ticker": "$$CASH"}]
    assert ac._alert_symbols() == ["RCAT", "MU", "ARM"]


def test_fidelity_pseudo_symbols_without_a_dollar_are_skipped(sources):
    """Measured on the live Plaid cache 2026-10-11: these ride WITHOUT a `$`."""
    sources["plaid"] = ["RESTRICTED.STOCK.UNITS", "SP.TTL.INTL.IDX.CL.C",
                        "BTC.LP.IDX.2055.H", "APLD"]
    assert ac._alert_symbols() == ["APLD", "WULX", "MU", "ARM"]


def test_class_shares_are_kept(sources):
    sources["plaid"] = ["BRK.B", "MOG-A"]
    assert ac._alert_symbols()[:2] == ["BRK.B", "MOG-A"]


def test_junk_values_never_crash(sources):
    sources["plaid"] = [None, "", 123, "RCAT"]
    sources["manual"] = [{}, {"ticker": None}]
    sources["watchlist"] = [{"ticker": ""}, {"note": "no ticker key"}]
    assert ac._alert_symbols() == ["RCAT"]


# ---------------------------------------------------------------------------
# a source down never empties the others
# ---------------------------------------------------------------------------
def test_plaid_store_unreachable_keeps_the_other_sources(sources, caplog):
    sources["plaid"] = None                      # held_tickers' "store down"
    with caplog.at_level(logging.INFO, logger="supply_demand.accumulation_changes"):
        assert ac._alert_symbols() == ["WULX", "MU", "ARM"]
    assert any("plaid source unavailable" in r.message and r.levelno == logging.WARNING
               for r in caplog.records)
    assert any("plaid=down" in r.message for r in caplog.records)


def test_plaid_raising_keeps_the_other_sources(sources):
    sources["plaid"] = RuntimeError("Plaid timeout")
    assert ac._alert_symbols() == ["WULX", "MU", "ARM"]


def test_watchlist_raising_keeps_the_holdings(sources):
    sources["watchlist"] = RuntimeError("mongo gone")
    assert ac._alert_symbols() == ["RCAT", "APLD", "WULX"]


def test_every_source_down_is_an_empty_scope_not_a_crash(sources):
    for k in ("plaid", "manual", "watchlist"):
        sources[k] = RuntimeError("down")
    sources["sepa"] = None
    assert ac._alert_symbols() == []


# ---------------------------------------------------------------------------
# empty owner
# ---------------------------------------------------------------------------
def test_no_owner_skips_holdings_but_keeps_the_watchlist(sources, monkeypatch, caplog):
    monkeypatch.setattr(auth, "HOUSE_OWNER_EMAILS", [])
    with caplog.at_level(logging.WARNING, logger="supply_demand.accumulation_changes"):
        assert ac._alert_symbols() == ["MU", "ARM"]
    # Neither holdings store is ever asked for a None owner.
    assert sources["calls"] == []
    assert any("no house owner email" in r.message for r in caplog.records)


def test_an_owner_holding_nothing_is_the_watchlist_alone(sources):
    sources["plaid"], sources["manual"] = [], []
    assert ac._alert_symbols() == ["MU", "ARM"]


# ---------------------------------------------------------------------------
# the log line
# ---------------------------------------------------------------------------
def test_the_count_per_source_is_logged_at_info(sources, caplog):
    sources["plaid"] = ["RCAT", "APLD", "RESTRICTED.STOCK.UNITS"]
    with caplog.at_level(logging.INFO, logger="supply_demand.accumulation_changes"):
        ac._alert_symbols()
    line = next(r for r in caplog.records if "alert scope" in r.message)
    assert line.levelno == logging.INFO
    for part in ("5 symbol(s)", "plaid=2", "manual=1", "watchlist=2",
                 "sepa_watchlist=0", "1 non-ticker skipped"):
        assert part in line.message


def test_sweep_without_symbols_reads_the_owner_scope(monkeypatch):
    seen = []
    monkeypatch.setattr(ac, "_alert_symbols", lambda email=None: seen.append(email) or [])
    monkeypatch.setattr(ac, "_db", lambda: None)
    res = ac.sweep(email="x@example.com")
    assert seen == ["x@example.com"] and res["scanned"] == 0


# ---------------------------------------------------------------------------
# plaid_store.tickers_from_holdings / held_tickers
# ---------------------------------------------------------------------------
def test_plaid_tickers_join_through_security_id():
    resp = _plaid_resp(("s1", "rcat", "equity", False), ("s2", "IRE", "etf", False))
    # The holding itself carries no ticker — the bug in main.py's focus set.
    assert all("ticker_symbol" not in h and "symbol" not in h for h in resp["holdings"])
    assert plaid_store.tickers_from_holdings(resp) == ["RCAT", "IRE"]


def test_plaid_cash_equivalents_are_not_holdings():
    resp = _plaid_resp(("s1", "SPAXX", "cash", True), ("s2", "FDRXX", "cash", False),
                       ("s3", "XYZ", "equity", True), ("s4", "APLD", "equity", False))
    assert plaid_store.tickers_from_holdings(resp) == ["APLD"]


def test_plaid_lots_in_two_accounts_are_one_ticker():
    resp = _plaid_resp(("s1", "RCAT", "equity", False))
    resp["holdings"].append({"security_id": "s1", "quantity": 5})
    assert plaid_store.tickers_from_holdings(resp) == ["RCAT"]


def test_plaid_orphan_holding_and_missing_ticker_are_skipped():
    resp = _plaid_resp(("s1", None, "equity", False))
    resp["holdings"].append({"security_id": "nope"})
    resp["holdings"].append(None)
    assert plaid_store.tickers_from_holdings(resp) == []
    assert plaid_store.tickers_from_holdings({}) == []
    assert plaid_store.tickers_from_holdings(None) == []


def test_held_tickers_is_none_when_the_store_is_down(monkeypatch):
    monkeypatch.setattr(plaid_store, "_get_db", lambda: None)
    assert plaid_store.held_tickers(OWNER) is None


def test_held_tickers_reads_the_cache_whatever_its_age(monkeypatch):
    asked = {}

    def _cached(email, max_age_sec=3600):
        asked.update(email=email, max_age_sec=max_age_sec)
        return _plaid_resp(("s1", "RCAT", "equity", False))

    monkeypatch.setattr(plaid_store, "_get_db", lambda: object())
    monkeypatch.setattr(plaid_store, "get_cached_holdings", _cached)
    assert plaid_store.held_tickers(OWNER) == ["RCAT"]
    # A weekly cron must not go blind because Plaid last synced 3 days ago.
    assert asked == {"email": OWNER, "max_age_sec": 0}


def test_held_tickers_with_nothing_cached_is_empty_not_none(monkeypatch):
    monkeypatch.setattr(plaid_store, "_get_db", lambda: object())
    monkeypatch.setattr(plaid_store, "get_cached_holdings", lambda e, max_age_sec=0: None)
    assert plaid_store.held_tickers(OWNER) == []
