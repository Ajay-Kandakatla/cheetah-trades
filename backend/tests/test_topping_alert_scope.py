"""Locks the topping-alert scoping (Ajay 2026-06-04: "I only need topping alerts
for my portfolio and leaderboards top stocks").

Two regressions this guards:
  1. _topping_watch_symbols must read holdings by "ticker" (the store's key) —
     the old "symbol" lookup silently dropped EVERY portfolio name, so owned
     stocks like ST/DINO never made the watch set.
  2. breakouts.list_active must hide stage-breakdown / topping alerts for
     tickers NOT on the watch set (so a non-owned, non-leaderboard name like SLF
     stops showing in the banner), while letting volume breakouts pass through.
"""
import sys
import types

import sepa.alerts as alerts
import sepa.breakouts as breakouts


# ── 1) watch set reads holdings by "ticker" ─────────────────────────────────
def test_watch_set_includes_portfolio_by_ticker(monkeypatch):
    import sepa.leaderboard as lb
    monkeypatch.setattr(lb, "leaderboard", lambda n, d: {"leaders": [{"symbol": "AAA"}]})

    fake_auth = types.ModuleType("auth")
    fake_auth.HOUSE_OWNER_EMAILS = ["owner@x.com"]
    monkeypatch.setitem(sys.modules, "auth", fake_auth)

    fake_store = types.ModuleType("portfolio.store")
    fake_store.list_holdings = lambda em: [{"ticker": "ST"}, {"ticker": "DINO"}]
    fake_pkg = types.ModuleType("portfolio")
    fake_pkg.store = fake_store
    monkeypatch.setitem(sys.modules, "portfolio", fake_pkg)
    monkeypatch.setitem(sys.modules, "portfolio.store", fake_store)

    watch = alerts._topping_watch_symbols()
    assert "AAA" in watch          # leaderboard name
    assert "ST" in watch           # portfolio holding (by ticker) — the fix
    assert "DINO" in watch


# ── 2) list_active hides out-of-scope topping alerts ────────────────────────
class _FakeCursor:
    def __init__(self, rows): self._rows = rows
    def sort(self, *a, **k): return self
    def limit(self, *a, **k): return list(self._rows)


class _FakeColl:
    def __init__(self, rows): self._rows = rows
    def find(self, *a, **k): return _FakeCursor(self._rows)


class _FakeDB:
    def __init__(self, rows): self.sepa_breakouts = _FakeColl(rows)


def test_list_active_filters_topping_to_watch(monkeypatch):
    rows = [
        {"_id": 1, "ticker": "SLF",  "kind": "stage_breakdown_2_3"},   # not watched → hide
        {"_id": 2, "ticker": "NUE",  "kind": "stage_breakdown_2_3"},   # watched → keep
        {"_id": 3, "ticker": "ZZZZ", "kind": "high_vol_breakout"},     # volume → always keep
    ]
    monkeypatch.setattr(breakouts, "_get_db", lambda: _FakeDB(rows))
    monkeypatch.setattr(alerts, "_topping_watch_symbols", lambda: {"NUE", "ST"})

    out = breakouts.list_active(0, 50)
    tickers = {r["ticker"] for r in out}
    assert "SLF" not in tickers        # out-of-scope topping alert hidden
    assert "NUE" in tickers            # watched topping alert kept
    assert "ZZZZ" in tickers           # volume breakout untouched


def test_volume_breakouts_never_filtered(monkeypatch):
    rows = [{"_id": i, "ticker": t, "kind": "high_vol_breakout"} for i, t in enumerate(["A", "B", "C"])]
    monkeypatch.setattr(breakouts, "_get_db", lambda: _FakeDB(rows))
    # Even with an empty watch set, non-topping alerts pass through untouched.
    monkeypatch.setattr(alerts, "_topping_watch_symbols", lambda: set())
    out = breakouts.list_active(0, 50)
    assert {r["ticker"] for r in out} == {"A", "B", "C"}
