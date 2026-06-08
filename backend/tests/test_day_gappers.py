"""Contract tests for the overnight-gappers scan (daytrading/premarket.py).

Monkeypatches the universe pool, the bulk snapshot, and the per-name enrichment,
so no Mongo / network / yfinance. Locks the gap filter, the gap×relvol ranking,
and the enrichment merge.

Run:
  docker run --rm -e PYTHONPATH=/app -v "$PWD/backend:/app" -w /app \
      cheetah-api:latest python -m pytest tests/test_day_gappers.py -q
"""
from __future__ import annotations

from daytrading import premarket as P
from daytrading import universe as U

POOL = [
    {"symbol": "BIG",   "adr_pct": 8.0, "last_close": 50.0, "rs_rank": 50, "volume": {"avg_vol_50": 2_000_000}},
    {"symbol": "SMALL", "adr_pct": 6.0, "last_close": 40.0, "rs_rank": 50, "volume": {"avg_vol_50": 1_000_000}},
    {"symbol": "FLAT",  "adr_pct": 5.0, "last_close": 30.0, "rs_rank": 50, "volume": {"avg_vol_50": 1_000_000}},
]


def _patch(monkeypatch, snaps, session="regular"):
    monkeypatch.setattr(U, "_scan_rows", lambda: [dict(r) for r in POOL])
    monkeypatch.setattr(U, "_bulk_snapshot", lambda s: snaps)
    monkeypatch.setattr(P, "_enrich_one",
                        lambda sym: (sym, {"pm_high": 1.0, "pm_low": 0.5, "rel_vol_10d": 2.0}))
    monkeypatch.setattr(P, "_session_now", lambda: session)
    U._uni_cache.clear(); U._mov_cache.clear(); P._cache.clear()


def test_gappers_filters_below_threshold_and_ranks(monkeypatch):
    _patch(monkeypatch, {
        "BIG":   {"change_pct": 8.0, "volume": 6_000_000, "price": 54.0, "prev_close": 50.0},   # gap 8, rel 3x
        "SMALL": {"change_pct": 3.0, "volume": 1_000_000, "price": 41.0, "prev_close": 40.0},   # gap 3, rel 1x
        "FLAT":  {"change_pct": 0.5, "volume": 1_000_000, "price": 30.1, "prev_close": 30.0},   # gap 0.5 → out
    })
    d = P.gappers("aggressive", force=True)
    syms = [g["symbol"] for g in d["gappers"]]
    assert "FLAT" not in syms               # below the 2% gap floor
    assert d["n_gappers"] == 2
    assert syms[0] == "BIG"                 # ranked by gap × relvol
    big = d["gappers"][0]
    assert big["direction"] == "up"
    assert big["pm_high"] == 1.0 and big["rel_vol_10d"] == 2.0   # enrichment merged


def test_gappers_down_direction(monkeypatch):
    _patch(monkeypatch, {"BIG": {"change_pct": -5.0, "volume": 4_000_000, "price": 47.5, "prev_close": 50.0}})
    g = P.gappers("aggressive", force=True)["gappers"][0]
    assert g["direction"] == "down" and g["gap_pct"] == -5.0


def test_premarket_headlines_extended_move(monkeypatch):
    # Modest regular gap, but moving big in premarket → ext move headlines.
    _patch(monkeypatch, {
        "BIG": {"change_pct": 1.0, "volume": 6_000_000, "price": 55.0, "prev_close": 50.0, "reg_close": 50.5},
    }, session="premarket")
    d = P.gappers("aggressive", force=True)
    assert d["session"] == "premarket"
    g = d["gappers"][0]
    assert g["symbol"] == "BIG" and g["ext_label"] == "PM"
    assert g["ext_move_pct"] == 10.0           # (55 - prev_close 50) / 50
    assert g["move_pct"] == 10.0 and g["direction"] == "up"
    assert g["gap_pct"] == 1.0                  # regular gap still reported


def test_afterhours_uses_regular_close_reference(monkeypatch):
    _patch(monkeypatch, {
        "BIG": {"change_pct": 8.0, "volume": 6_000_000, "price": 48.0, "prev_close": 50.0, "reg_close": 53.0},
    }, session="afterhours")
    g = P.gappers("aggressive", force=True)["gappers"][0]
    assert g["ext_label"] == "AH"
    assert g["ext_move_pct"] == round((48 - 53) / 53 * 100, 2)   # vs today's close
    assert g["move_pct"] == g["ext_move_pct"] and g["direction"] == "down"


def test_closed_falls_back_to_session_gap_when_ah_flat(monkeypatch):
    _patch(monkeypatch, {
        "BIG": {"change_pct": 30.0, "volume": 6_000_000, "price": 65.1, "prev_close": 50.0, "reg_close": 65.0},
    }, session="closed")
    d = P.gappers("aggressive", force=True)
    g = d["gappers"][0]
    assert d["session"] == "closed"
    assert abs(g["ext_move_pct"]) < 2.0         # AH basically flat
    assert g["move_pct"] == 30.0                # → headline falls back to the session gap


def test_gappers_constants_locked():
    assert P.GAP_MIN_PCT == 2.0
    assert P.REL_VOL_ELEVATED == 1.5
    assert P.ENRICH_TOP_N == 15
