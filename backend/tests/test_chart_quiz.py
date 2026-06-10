"""Tests for the Chart School daily quiz — windowing (no answer leakage past the
confirmation bar), determinism per date, and outcome math. Synthetic frames.
"""
import numpy as np
import pandas as pd
import pytest

from flashcards import chart_quiz
from patterns import detector


def _w_frame():
    """Long frame with a confirmed W deep enough for context + a full outcome
    window: 80 quiet bars, then a W (sep ~26), confirmation, then 30 more."""
    seg = list(100 + np.random.RandomState(7).normal(0, 0.3, 80))
    seg += list(np.linspace(100, 80, 25))
    seg += list(np.linspace(80, 92, 13))
    seg += list(np.linspace(92, 80, 13))
    seg += list(np.linspace(80, 96, 12))     # confirms above 92
    seg += list(np.linspace(96, 104, 30))    # +21-bar outcome available
    idx = pd.bdate_range("2025-01-01", periods=len(seg))
    c = np.asarray(seg, float)
    return pd.DataFrame({"open": np.r_[c[0], c[:-1]], "high": c + 0.4, "low": c - 0.4,
                         "close": c, "volume": np.full(len(c), 1e6)}, index=idx)


@pytest.fixture
def _patched(monkeypatch):
    df = _w_frame()
    from sepa import scanner, prices
    monkeypatch.setattr(scanner, "load_latest",
                        lambda: {"all_results": [{"symbol": "TEST", "is_etf": False}]})
    monkeypatch.setattr(prices, "load_prices", lambda s, **k: df.copy())
    monkeypatch.setattr(chart_quiz, "_coll", lambda: None)   # no Mongo
    return df


def test_generate_produces_item_with_hidden_future(_patched):
    q = chart_quiz.generate("2026-06-10", n=1)
    assert q["items"], "should find the confirmed W"
    it = q["items"][0]
    assert it["symbol"] == "TEST"
    assert it["answer"] in it["choices"]
    assert it["pattern"] == "double_bottom"
    # The LAST bar served is the confirmation bar — nothing after it leaks.
    assert it["bars"][-1]["t"] == it["confirm_date"]
    assert len(it["bars"]) == chart_quiz.BARS_BEFORE + 1
    # The confirmation bar closes above the neckline (that's what confirmation means).
    assert it["bars"][-1]["c"] > it["neckline"]
    assert isinstance(it["outcome_fwd_21d_pct"], float)
    assert it["why"]


def test_generate_deterministic_per_date(_patched):
    a = chart_quiz.generate("2026-06-10", n=1)
    b = chart_quiz.generate("2026-06-10", n=1)
    assert [i["symbol"] for i in a["items"]] == [i["symbol"] for i in b["items"]]
    assert a["items"][0]["confirm_date"] == b["items"][0]["confirm_date"]


def test_generate_handles_empty_universe(monkeypatch):
    from sepa import scanner
    monkeypatch.setattr(scanner, "load_latest", lambda: {"all_results": []})
    monkeypatch.setattr(chart_quiz, "_coll", lambda: None)
    q = chart_quiz.generate("2026-06-10")
    assert q["items"] == [] and "error" in q


def test_outcome_matches_validation_horizon(_patched):
    df = _patched
    q = chart_quiz.generate("2026-06-10", n=1)
    it = q["items"][0]
    closes = df["close"].to_numpy(float)
    k = list(df.index.strftime("%Y-%m-%d")).index(it["confirm_date"])
    expect = round((closes[k + detector.VALIDATION_HORIZON] / closes[k] - 1) * 100, 2)
    assert it["outcome_fwd_21d_pct"] == expect
