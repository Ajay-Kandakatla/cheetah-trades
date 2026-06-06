"""Tests for Cross Junctions — Pullback ∩ SEPA ∩ consistent-rank confluence.

Pure: monkeypatch the scan, the leaderboard, the pullback evaluator, and the
universe sets so we assert the intersection + S&P-first/Russell-fallback logic.
"""
from sepa import cross_junctions as cj


def rec(sym, score=80, is_candidate=True, rating="BUY"):
    return {"symbol": sym, "name": f"{sym} Inc", "score": score,
            "is_candidate": is_candidate, "rating": rating, "rs_rank": 90}


def pb(sym, score=70):
    return {"symbol": sym, "score": score, "pct_from_ma50": 3.0, "pullback_pct": 4.0,
            "pullback_band": "tight", "vol_ratio": 0.7, "vol_healthy": True}


def leader(sym, persistence=80, appearances=8, rank=3):
    return {"symbol": sym, "persistence_pct": persistence, "appearances": appearances,
            "current_rank": rank, "best_rank": rank, "rank_range": 5, "flag": "steady"}


def _setup(monkeypatch, *, all_results, leaders, pb_map, sp500, russell):
    monkeypatch.setattr(cj.sepa_scanner, "load_latest",
                        lambda: {"generated_at": 1, "all_results": all_results})
    monkeypatch.setattr(cj.leaderboard, "leaderboard",
                        lambda n=300, lookback_days=14: {"leaders": leaders, "scans_in_window": 9})
    monkeypatch.setattr(cj.pullback_ma, "_evaluate_row",
                        lambda r: pb_map.get((r or {}).get("symbol")))
    monkeypatch.setattr(cj, "_universe_set",
                        lambda mode: sp500 if mode == "sp500"
                        else (russell if mode == "russell1000" else set()))
    cj._CACHE.update(at=0.0, data=None)


def test_intersection_keeps_only_all_three_legs(monkeypatch):
    _setup(monkeypatch,
           all_results=[rec("AAA"), rec("BBB"), rec("CCC", is_candidate=False)],
           leaders=[leader("AAA", 80, 8), leader("BBB", 30, 2)],   # AAA consistent, BBB not
           pb_map={"AAA": pb("AAA"), "BBB": pb("BBB")},
           sp500={"AAA", "BBB"}, russell={"AAA", "BBB"})
    out = cj.compute()
    syms = {r["symbol"] for r in out["rows"]}
    assert "AAA" in syms          # SEPA + consistent + pullback + S&P
    assert "BBB" not in syms      # fails the consistency leg (persistence 30, 2 appearances)
    assert "CCC" not in syms      # not a SEPA candidate
    assert out["universe_used"] == "sp500"
    assert out["rows"][0]["junction_universe"] == "sp500"
    assert out["rows"][0]["junction_score"] > 0
    assert out["rows"][0]["rating"] == "BUY"      # chip data carried through


def test_sp500_first_then_russell_fallback(monkeypatch):
    # AAA in S&P; DDD only in Russell. S&P junctions = {AAA} (< MIN_SP500_RESULTS)
    # -> broaden to Russell -> DDD added.
    _setup(monkeypatch,
           all_results=[rec("AAA"), rec("DDD")],
           leaders=[leader("AAA", 80, 8), leader("DDD", 75, 8)],
           pb_map={"AAA": pb("AAA"), "DDD": pb("DDD")},
           sp500={"AAA"}, russell={"AAA", "DDD"})
    out = cj.compute()
    syms = {r["symbol"] for r in out["rows"]}
    assert syms == {"AAA", "DDD"}
    assert out["universe_used"] == "sp500+russell1000"
    duni = next(r for r in out["rows"] if r["symbol"] == "DDD")["junction_universe"]
    assert duni == "russell1000"


def test_consistent_sepa_without_pullback_is_excluded(monkeypatch):
    _setup(monkeypatch,
           all_results=[rec("AAA")],
           leaders=[leader("AAA", 90, 9)],
           pb_map={},                              # AAA not pulling back
           sp500={"AAA"}, russell={"AAA"})
    out = cj.compute()
    assert out["count"] == 0


def test_junction_score_is_weighted_blend(monkeypatch):
    _setup(monkeypatch,
           all_results=[rec("AAA", score=100)],
           leaders=[leader("AAA", persistence=100, appearances=10)],
           pb_map={"AAA": pb("AAA", score=100)},
           sp500={"AAA"}, russell={"AAA"})
    out = cj.compute()
    # 0.45*100 + 0.30*100 + 0.25*100 = 100
    assert out["rows"][0]["junction_score"] == 100.0
    assert out["rows"][0]["consistency"]["persistence_pct"] == 100
    assert out["rows"][0]["pullback"]["band"] == "tight"


def test_no_scan_yields_no_junctions(monkeypatch):
    monkeypatch.setattr(cj.sepa_scanner, "load_latest", lambda: {})
    monkeypatch.setattr(cj.leaderboard, "leaderboard",
                        lambda n=300, lookback_days=14: {"leaders": []})
    monkeypatch.setattr(cj, "_universe_set", lambda mode: set())
    cj._CACHE.update(at=0.0, data=None)
    out = cj.compute()
    assert out["count"] == 0 and out["rows"] == []


def test_config_thresholds_locked():
    assert cj.PERSISTENCE_FLOOR == 50 and cj.MIN_APPEARANCES == 4
    assert cj.MIN_SP500_RESULTS == 6
    assert round(cj.W_SEPA + cj.W_PULLBACK + cj.W_PERSIST, 5) == 1.0
