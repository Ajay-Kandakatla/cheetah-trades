"""Offline tests for the catalyst summary (sepa/catalyst.py).

The LLM path needs LM Studio, so here we lock the DETERMINISTIC pieces: the
heuristic fallback (used when the LLM is off) and the no-LLM degradation. The
real-money guarantee we care about — the summary never *fabricates* — is upheld
by the heuristic (it only restates counts) and, for the LLM path, by the prompt.
"""
from __future__ import annotations

from sepa import catalyst as c


WDC = {
    "symbol": "WDC",
    "news_sentiment_score": 0, "news_count": 5,
    "analyst_up_revisions_30d": 0, "analyst_down_revisions_30d": 0,
    "earnings_upcoming": None, "last_earnings_surprise_pct": None,
    "top_news": [
        {"title": "WDC outperforms competitors on strong trading day", "score": 1},
        {"title": "WDC underperforms Friday vs competitors", "score": -1},
    ],
}


def test_heuristic_is_grounded_and_terse():
    s = c._heuristic_summary(WDC)
    assert "5 recent headlines" in s
    assert "neutral" in s
    # never claims a catalyst that isn't in the data
    assert "buy" not in s.lower() and "sell" not in s.lower()


def test_heuristic_empty_says_no_catalyst():
    s = c._heuristic_summary({"symbol": "ZZZ", "top_news": [], "news_count": 0})
    assert s == "No recent news catalyst found."


def test_generate_falls_back_to_heuristic_when_llm_off(monkeypatch):
    import llm
    monkeypatch.setattr(llm, "is_enabled", lambda: False)
    out = c._generate_summary(WDC, provider="local")
    assert out == c._heuristic_summary(WDC)


def test_summarize_requires_symbol():
    assert c.summarize_catalyst({}) is None
    assert c.summarize_catalyst({"symbol": ""}) is None


def test_heuristic_reports_revisions_and_earnings():
    s = c._heuristic_summary({
        "symbol": "AAA", "news_count": 2, "news_sentiment_score": 3,
        "analyst_up_revisions_30d": 4, "analyst_down_revisions_30d": 1,
        "earnings_upcoming": {"date": "2026-06-20"}, "top_news": [{"title": "x", "score": 1}],
    })
    assert "net-bullish" in s and "4 up / 1 down" in s and "earnings upcoming" in s
