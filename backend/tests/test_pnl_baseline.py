"""Account starting-equity baseline for the Auto-Pilot P&L header (Ajay
2026-06-19: the "started $X -> made $Y" line must compute on Alpaca too).

The SIM reports `starting_cash`; a brokerage account doesn't, so
exit_engine.account_starting_cash snapshots the equity on first sight and reads
that snapshot forever after. These tests cover: sim passthrough, the one-time
Alpaca snapshot + persistence, equity drift NOT moving the baseline, the
no-Mongo degrade, and the pnl_summary total computing once a baseline exists.

  cd backend && .venv/bin/python -m pytest tests/test_pnl_baseline.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class _FakeColl:
    def __init__(self):
        self.docs = {}

    def find_one(self, q):
        return self.docs.get(q.get("account_key"))

    def update_one(self, q, upd, upsert=False):
        key = q.get("account_key")
        doc = self.docs.get(key) or {}
        doc.update(upd.get("$set") or {})
        self.docs[key] = doc


class _FakeDB:
    def __init__(self):
        self.trading_account_baseline = _FakeColl()


def _boom():
    raise AssertionError("the DB must not be touched for a sim account")


def test_sim_account_uses_starting_cash_directly(monkeypatch):
    from trading import exit_engine as ee
    monkeypatch.setattr(ee, "_db", _boom)          # would raise if touched
    assert ee.account_starting_cash(
        {"starting_cash": 5000.0, "equity": 5196.0}) == 5000.0


def test_alpaca_snapshots_equity_once_then_persists(monkeypatch):
    from trading import exit_engine as ee
    db = _FakeDB()
    monkeypatch.setattr(ee, "_db", lambda: db)
    monkeypatch.setattr(ee, "_broker_mode", lambda: "paper")
    acct = {"account_number": "PA123", "equity": 100000.0}   # no starting_cash
    assert ee.account_starting_cash(acct) == 100000.0        # first sight -> snapshot
    # Equity climbs; the baseline must stay the original snapshot.
    assert ee.account_starting_cash(
        {"account_number": "PA123", "equity": 100250.0}) == 100000.0
    assert db.trading_account_baseline.docs["PA123"]["starting_equity"] == 100000.0


def test_no_mongo_degrades_to_current_equity(monkeypatch):
    from trading import exit_engine as ee
    monkeypatch.setattr(ee, "_db", lambda: None)
    monkeypatch.setattr(ee, "_broker_mode", lambda: "paper")
    # No persistence available -> P&L reads $0 (start == equity), never crashes.
    assert ee.account_starting_cash({"equity": 100000.0}) == 100000.0


def test_pnl_summary_total_computes_with_baseline(monkeypatch):
    from trading import exit_engine as ee
    db = _FakeDB()
    monkeypatch.setattr(ee, "_db", lambda: db)
    monkeypatch.setattr(ee, "_broker_mode", lambda: "paper")
    # First sight at $100,000 seeds the baseline (mirrors seeding it at connect
    # time while the account is pristine).
    ee.account_starting_cash({"account_number": "PA1", "equity": 100000.0})
    # Later the account is at $100,200; the baseline read returns the seed.
    acct = {"account_number": "PA1", "equity": 100200.0, "cash": 100200.0}
    start = ee.account_starting_cash(acct)
    assert start == 100000.0
    summ = ee.pnl_summary({**acct, "starting_cash": start}, [])
    assert summ["starting_cash"] == 100000.0
    assert summ["total_pnl_dollars"] == 200.0
    assert summ["total_pnl_pct"] == 0.2
