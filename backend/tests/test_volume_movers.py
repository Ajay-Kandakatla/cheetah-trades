"""Volume Movers board — volume + price change + the SUPPLY read (turnover).

Ajay 2026-06-15: "page with highest volume and price change ... track total
stocks of a company ... why did INTC's volume not deplete the stocks." These
lock the metric math (rvol / dollar_vol / turnover), the sorts, and the
soft-fail when float is unavailable (board must still render).

Run in the backend venv (needs pandas via sepa.scanner):
  cd backend && .venv/bin/python -m pytest tests/test_volume_movers.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import volume_movers as vm


def _row(sym, lv, av, close, chg):
    return {"symbol": sym, "name": f"{sym} Inc", "last_close": close,
            "day_change_pct": chg, "volume": {"last_vol": lv, "avg_vol_50": av}}


def _scan(rows):
    return {"all_results": rows, "generated_at": 123}


def test_movers_computes_rvol_dollarvol_turnover(monkeypatch):
    monkeypatch.setattr("sepa.scanner.load_latest",
                        lambda: _scan([_row("AAA", 1000, 500, 10, 2.0)]))
    monkeypatch.setattr(vm, "shares_for",
                        lambda s: {"float_shares": 100_000, "shares_outstanding": 120_000, "market_cap": None})
    r = vm.movers(top=10, sort="volume")["rows"][0]
    assert r["rvol"] == 2.0            # 1000 / 500
    assert r["dollar_vol"] == 10_000   # 1000 × 10
    assert r["turnover_pct"] == 1.0    # 1000 / 100_000 × 100
    assert r["float_shares"] == 100_000


def test_sort_volume_vs_rvol(monkeypatch):
    rows = [_row("AAA", 1000, 500, 10, 2.0),    # rvol 2.0, vol 1000
            _row("BBB", 5000, 5000, 4, -1.0)]   # rvol 1.0, vol 5000
    monkeypatch.setattr("sepa.scanner.load_latest", lambda: _scan(rows))
    monkeypatch.setattr(vm, "shares_for", lambda s: None)
    assert [r["symbol"] for r in vm.movers(sort="volume")["rows"]] == ["BBB", "AAA"]
    assert [r["symbol"] for r in vm.movers(sort="rvol")["rows"]] == ["AAA", "BBB"]


def test_float_softfail_keeps_board(monkeypatch):
    """INTC-style: float unavailable → turnover '—', but the board still lists."""
    monkeypatch.setattr("sepa.scanner.load_latest",
                        lambda: _scan([_row("AAA", 1000, 500, 10, 2.0)]))
    monkeypatch.setattr(vm, "shares_for", lambda s: None)
    out = vm.movers(top=10, sort="volume")
    assert out["n"] == 1
    assert out["rows"][0]["turnover_pct"] is None
    assert out["rows"][0]["float_shares"] is None


def test_rows_without_volume_are_dropped(monkeypatch):
    monkeypatch.setattr("sepa.scanner.load_latest",
                        lambda: _scan([_row("AAA", 1000, 500, 10, 2.0),
                                       {"symbol": "NOVOL", "volume": {}}]))
    monkeypatch.setattr(vm, "shares_for", lambda s: None)
    assert [r["symbol"] for r in vm.movers()["rows"]] == ["AAA"]


def test_unknown_sort_falls_back_to_volume(monkeypatch):
    monkeypatch.setattr("sepa.scanner.load_latest",
                        lambda: _scan([_row("AAA", 1000, 500, 10, 2.0)]))
    monkeypatch.setattr(vm, "shares_for", lambda s: None)
    assert vm.movers(sort="bogus")["sort"] == "volume"


def test_shares_for_softfails_without_mongo_or_yf(monkeypatch):
    monkeypatch.setattr(vm, "_shares_coll", lambda: None)
    monkeypatch.setattr(vm, "_fetch_shares_yf", lambda s: None)
    assert vm.shares_for("ZZZ") is None      # must not raise
