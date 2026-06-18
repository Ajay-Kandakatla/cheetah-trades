"""rs_rank.rank_one — single-symbol RS for the ticker-details off-scan path
(Ajay 2026-06-18 perf: was re-scoring all ~3000 names per request, ~5s).

Locks: it returns the SAME 1-99 percentile rs_ranks() would, it caches the
universe-score distribution per scan cycle (no re-scoring), and it soft-fails to
None when the symbol (or the universe) has no usable score.

Run in the backend venv:
  cd backend && .venv/bin/python -m pytest tests/test_rs_rank_one.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import rs_rank


def _reset():
    rs_rank._UNIVERSE_SCORES.update(key=None, scores=None)


def test_rank_one_matches_rs_ranks(monkeypatch):
    # Controlled scores (no real prices) — _score_one is the single hook both
    # rs_ranks and rank_one go through.
    scores = {"A": 0.10, "B": 0.20, "C": 0.30, "D": 0.40, "X": 0.25}
    monkeypatch.setattr(rs_rank, "_score_one", lambda s: (s, scores.get(s)))
    _reset()
    full = rs_rank.rs_ranks(["A", "B", "C", "D", "X"])
    one = rs_rank.rank_one("X", ["A", "B", "C", "D"], cache_key="scan1")
    assert one == full["X"]          # identical percentile to the full re-rank
    assert one == 59                 # 0.25 is the 3rd of 5 → pct .6 → round(.6*99)


def test_rank_one_caches_universe_per_scan(monkeypatch):
    scores = {"A": 0.1, "B": 0.2, "C": 0.3}
    calls = {"n": 0}

    def fake(s):
        if s in scores:
            calls["n"] += 1          # count only universe scorings
        return (s, scores.get(s, 0.25))

    monkeypatch.setattr(rs_rank, "_score_one", fake)
    _reset()
    rs_rank.rank_one("X", ["A", "B", "C"], cache_key="scan1")
    assert calls["n"] == 3           # scored the 3 universe names once
    rs_rank.rank_one("Y", ["A", "B", "C"], cache_key="scan1")
    assert calls["n"] == 3           # same scan cycle → reused cache, no re-score
    rs_rank.rank_one("Z", ["A", "B", "C"], cache_key="scan2")
    assert calls["n"] == 6           # new scan → recompute


def test_rank_one_none_without_symbol_history(monkeypatch):
    monkeypatch.setattr(rs_rank, "_score_one", lambda s: (s, None))
    _reset()
    assert rs_rank.rank_one("X", ["A", "B"], cache_key="s") is None


def test_rank_one_none_when_universe_unrankable(monkeypatch):
    # The searched symbol scores, but no universe name does → can't rank it.
    monkeypatch.setattr(rs_rank, "_score_one",
                        lambda s: (s, 0.5) if s == "X" else (s, None))
    _reset()
    assert rs_rank.rank_one("X", ["A", "B"], cache_key="s") is None
