"""SIM -> brokerage handover (Ajay 2026-06-19): book the sim's still-open paper
positions closed at their last mark so the track record captures the full sim
chapter and the only open trades going forward are the real brokerage ones.

Covers: books every open position as a `trade_closed`/`sim_handover` ledger
row; idempotency (already-booked symbol skipped, no second write); dry-run
writes nothing; zero qty/price skipped; no positions is a clean no-op.

  cd backend && .venv/bin/python -m pytest tests/test_sim_handover.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _no_dedupe_db():
    return None       # _already_booked() returns False -> nothing pre-booked


def test_books_open_positions_at_last_mark(monkeypatch):
    from trading import broker_sim, sim_handover as sh
    monkeypatch.setattr(broker_sim, "positions", lambda: [
        {"symbol": "ALGM", "qty": 22, "avg_entry_price": 55.06, "current_price": 59.0},
        {"symbol": "BNY", "qty": 8, "avg_entry_price": 147.8, "current_price": 143.63},
    ])
    monkeypatch.setattr(sh, "_db", _no_dedupe_db)
    calls = []
    monkeypatch.setattr(sh, "ledger",
                        lambda kind, **kw: calls.append((kind, kw)) or {})
    out = sh.run()
    assert out["ok"]
    assert sorted(r["symbol"] for r in out["booked"]) == ["ALGM", "BNY"]
    assert len(calls) == 2
    assert {c[0] for c in calls} == {"trade_closed"}
    assert {c[1]["detail"]["leg"] for c in calls} == {"sim_handover"}
    # Fill is the last simulated mark; mode is stamped sim.
    bny = next(c for c in calls if c[1]["symbol"] == "BNY")
    assert bny[1]["detail"]["fill"] == 143.63
    assert bny[1]["detail"]["mode"] == "sim"
    # gain_dollars_est on the winner (summary only — journal owns the canonical).
    algm = next(r for r in out["booked"] if r["symbol"] == "ALGM")
    assert algm["gain_dollars_est"] == round(22 * (59.0 - 55.06), 2)


def test_idempotent_skips_already_booked(monkeypatch):
    from trading import broker_sim, sim_handover as sh
    monkeypatch.setattr(broker_sim, "positions", lambda: [
        {"symbol": "ALGM", "qty": 22, "avg_entry_price": 55.06, "current_price": 59.0}])

    class _DB:
        class _Ledger:
            def find_one(self, q):
                return {"_id": "already"}          # this symbol is booked
        trade_ledger = _Ledger()

    monkeypatch.setattr(sh, "_db", lambda: _DB())
    calls = []
    monkeypatch.setattr(sh, "ledger", lambda *a, **k: calls.append(1))
    out = sh.run()
    assert out["booked"] == [] and out["skipped"] == ["ALGM"]
    assert calls == []                              # no double-book


def test_dry_run_writes_nothing(monkeypatch):
    from trading import broker_sim, sim_handover as sh
    monkeypatch.setattr(broker_sim, "positions", lambda: [
        {"symbol": "ROG", "qty": 8, "avg_entry_price": 157.19, "current_price": 162.68}])
    monkeypatch.setattr(sh, "_db", _no_dedupe_db)

    def _explode(*a, **k):
        raise AssertionError("dry-run must not write to the ledger")

    monkeypatch.setattr(sh, "ledger", _explode)
    out = sh.run(dry_run=True)
    assert out["booked"][0]["symbol"] == "ROG"
    assert out["booked"][0]["dry_run"] is True


def test_zero_qty_or_price_skipped(monkeypatch):
    from trading import broker_sim, sim_handover as sh
    monkeypatch.setattr(broker_sim, "positions", lambda: [
        {"symbol": "X", "qty": 0, "avg_entry_price": 10.0, "current_price": 11.0},
        {"symbol": "Y", "qty": 5, "avg_entry_price": 10.0, "current_price": 0.0},
    ])
    monkeypatch.setattr(sh, "_db", _no_dedupe_db)
    calls = []
    monkeypatch.setattr(sh, "ledger", lambda *a, **k: calls.append(1))
    out = sh.run()
    assert set(out["skipped"]) == {"X", "Y"} and calls == []


def test_no_positions_is_clean(monkeypatch):
    from trading import broker_sim, sim_handover as sh
    monkeypatch.setattr(broker_sim, "positions", lambda: [])
    monkeypatch.setattr(sh, "_db", _no_dedupe_db)
    out = sh.run()
    assert out == {"ok": True, "booked": [], "skipped": [], "errors": []}
