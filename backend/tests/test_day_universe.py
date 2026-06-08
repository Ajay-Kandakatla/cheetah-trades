"""Contract tests for the dynamic day-trade universe (daytrading/universe.py).

Monkeypatches the cached-scan reader + the bulk snapshot, so no Mongo / network.
Locks the day-tradeable filters (liquidity + volatility), the per-profile ranking,
the active-movers bounding, and the closed-market fallback.

Run:
  docker run --rm -e PYTHONPATH=/app -v "$PWD/backend:/app" -w /app \
      cheetah-api:latest python -m pytest tests/test_day_universe.py -q
"""
from __future__ import annotations

from daytrading import universe as U


def _row(sym, adr, close, avg_vol):
    return {"symbol": sym, "adr_pct": adr, "last_close": close,
            "rs_rank": 50, "volume": {"avg_vol_50": avg_vol}}


# WILD  adr12 $100M  → aggressive ✓ ; conservative ✗ (adr > 9 cap)
# MEGA  adr3  $400M  → aggressive ✗ (adr<4) ; conservative ✓
# PENNY adr20 px$2   → excluded both (price floor)
# THIN  adr8  $5M    → excluded both (liquidity floor)
# AGGR  adr6  $80M   → aggressive ✓ ; conservative ✗ ($vol < $100M)
ROWS = [
    _row("WILD", 12.0, 20.0, 5_000_000),
    _row("MEGA", 3.0, 200.0, 2_000_000),
    _row("PENNY", 20.0, 2.0, 50_000_000),
    _row("THIN", 8.0, 50.0, 100_000),
    _row("AGGR", 6.0, 40.0, 2_000_000),
]


def _patch_scan(monkeypatch):
    monkeypatch.setattr(U, "_scan_rows", lambda: [dict(r) for r in ROWS])
    U._uni_cache.clear()
    U._mov_cache.clear()


def test_aggressive_filters_and_ranks_by_adr(monkeypatch):
    _patch_scan(monkeypatch)
    syms = [n["symbol"] for n in U.day_trade_universe("aggressive", force=True)["names"]]
    assert "PENNY" not in syms and "THIN" not in syms      # price + liquidity floors
    assert "MEGA" not in syms                              # adr < 4
    assert "WILD" in syms and "AGGR" in syms
    assert syms.index("WILD") < syms.index("AGGR")         # ranked by ADR desc


def test_conservative_excludes_wild_and_illiquid(monkeypatch):
    _patch_scan(monkeypatch)
    syms = [n["symbol"] for n in U.day_trade_universe("conservative", force=True)["names"]]
    assert "WILD" not in syms        # adr 12 > 9 cap
    assert "AGGR" not in syms        # $80M < $100M conservative floor
    assert "MEGA" in syms            # adr 3, $400M → ok


def test_active_movers_bounds_and_ranks(monkeypatch):
    _patch_scan(monkeypatch)
    monkeypatch.setattr(U, "_bulk_snapshot", lambda syms: {
        "WILD": {"volume": 25_000_000, "change_pct": 10.0, "price": 22.0},   # rel ~5x
        "AGGR": {"volume": 2_000_000, "change_pct": 1.0, "price": 40.0},     # rel ~1x
    })
    m = U.active_movers("aggressive", top_n=1, force=True)
    assert m["live"] is True
    assert m["n"] == 1 and m["symbols"] == ["WILD"]        # bounded + ranked by rel×move


def test_active_movers_fallback_when_market_closed(monkeypatch):
    _patch_scan(monkeypatch)
    monkeypatch.setattr(U, "_bulk_snapshot", lambda syms: {})   # no snapshot
    m = U.active_movers("aggressive", top_n=2, force=True)
    assert m["live"] is False
    assert len(m["symbols"]) == 2     # falls back to the top pool names


def test_constants_locked():
    assert U.LIVE_SCAN_CAP == 20
    assert U.PRICE_FLOOR == 5.0
    assert U.ADR_FLOOR_AGGR == 4.0
    assert U.ADR_FLOOR_CONS == 2.5
    assert U.ADR_CAP_CONS == 9.0
