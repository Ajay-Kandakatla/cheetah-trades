"""RS-rank robustness — one NaN score must not crash the whole scan.

Regression for 2026-06-16: rs_score returned NaN for a couple of hyphenated
dual-class tickers (MOG-A, BF-B); `val is not None` let NaN into the percentile
rank, and `int(NaN)` then raised "cannot convert float NaN to integer", killing
the entire scan's RS step (surfaced as a ⚠ in scan progress). Finite-only scores
are rankable; the rest are omitted (as the docstring already promised).

Run in the backend venv (needs pandas):
  cd backend && .venv/bin/python -m pytest tests/test_rs_rank.py -q
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import rs_rank


def _canned(scores):
    """Monkeypatch helper: rs_ranks calls _score_one(sym) per symbol."""
    return lambda s: (s, scores[s])


def test_nan_score_is_omitted_not_crashing(monkeypatch):
    scores = {"AAA": 1.0, "BBB": 2.0, "CCC": float("nan"), "DDD": 3.0}
    monkeypatch.setattr(rs_rank, "_score_one", _canned(scores))
    out = rs_rank.rs_ranks(list(scores))          # must NOT raise
    assert "CCC" not in out
    assert set(out) == {"AAA", "BBB", "DDD"}
    assert all(1 <= v <= 99 for v in out.values())


def test_inf_score_is_omitted(monkeypatch):
    scores = {"AAA": 1.0, "BBB": math.inf}
    monkeypatch.setattr(rs_rank, "_score_one", _canned(scores))
    assert set(rs_rank.rs_ranks(list(scores))) == {"AAA"}


def test_none_score_is_omitted(monkeypatch):
    scores = {"AAA": 1.0, "BBB": None}
    monkeypatch.setattr(rs_rank, "_score_one", _canned(scores))
    assert set(rs_rank.rs_ranks(list(scores))) == {"AAA"}


def test_all_unrankable_returns_empty(monkeypatch):
    monkeypatch.setattr(rs_rank, "_score_one", lambda s: (s, None))
    assert rs_rank.rs_ranks(["AAA", "BBB"]) == {}


def test_higher_score_ranks_higher(monkeypatch):
    scores = {"LO": 1.0, "MID": 5.0, "HI": 10.0}
    monkeypatch.setattr(rs_rank, "_score_one", _canned(scores))
    out = rs_rank.rs_ranks(list(scores))
    assert out["HI"] > out["MID"] > out["LO"]     # ranking semantics intact
