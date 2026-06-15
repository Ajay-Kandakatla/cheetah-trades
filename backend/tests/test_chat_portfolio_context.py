"""Chat portfolio memory — the live-positions snapshot + its injection.

Ajay 2026-06-15: *"always remember my current portfolio# ... answer based on
Minervini."* The chat agent now folds his real holdings into the system prompt
every turn. These lock:
  - the block lists positions with P/L + weight,
  - it SOFT-FAILS to None on every failure path (no holdings, db down, bad
    email, missing quote fields) — a chat turn must never die over portfolio
    data,
  - build_system_prompt injects the block AND carries the agent framing (his
    agent, Minervini lens, no reflexive "not financial advice" disclaimers).

Run in the backend venv (py3.9 has fastapi/pandas):
  cd backend && .venv/bin/python -m pytest tests/test_chat_portfolio_context.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import chat.portfolio_context as pc
from chat.prompt import SYSTEM_PROMPT_BASE, build_system_prompt


def _fake_summary():
    """Shape mirrors portfolio.api.build_summary() (rollup of holdings+quotes)."""
    return {
        "available": True,
        "count": 2,
        "total_value": 42000.0,
        "total_cost": 35000.0,
        "pl_dollars": 7000.0,
        "pl_pct": 20.0,
        "day_dollars": 312.0,
        "rows": [
            {"ticker": "MU", "shares": 42.0, "avg_cost": 591.0, "last": 746.5,
             "pl_pct": 26.3, "day_change_pct": 1.4, "weight_pct": 60.0},
            {"ticker": "WDC", "shares": 100.0, "avg_cost": 100.0, "last": 108.7,
             "pl_pct": 8.7, "day_change_pct": -0.6, "weight_pct": 26.0},
        ],
    }


# ── the snapshot block ──────────────────────────────────────────────────────

def test_block_lists_positions_pl_and_weight(monkeypatch):
    monkeypatch.setattr(pc, "_fetch_summary", lambda email: _fake_summary())
    block = pc.live_portfolio_block("ajaykandakatla@gmail.com")
    assert block is not None
    # Header carries account-level totals.
    assert "LIVE portfolio" in block
    assert "$42,000" in block and "+20.0%" in block
    # Each position is on its own line with ticker, P/L%, weight.
    assert "MU:" in block and "+26.3% open" in block and "60% of book" in block
    assert "WDC:" in block and "-0.6% today" in block
    # Plain text, not a JSON payload to echo back.
    assert "{" not in block


def test_quote_outage_suppresses_bogus_pl(monkeypatch):
    """When every quote fails, build_summary reports total_value 0 / pl_pct
    -100. The block must NOT print that fake wipeout — show cost basis +
    positions and say quotes are unavailable."""
    summ = {
        "available": True, "count": 2,
        "total_value": 0.0, "total_cost": 35000.0,
        "pl_dollars": -35000.0, "pl_pct": -100.0, "day_dollars": -35000.0,
        "rows": [
            # Live outage returns last=0.0 (not None) — the guard must catch it.
            {"ticker": "LRCX", "shares": 10.0, "avg_cost": 900.0, "last": 0.0,
             "pl_pct": -100.0, "day_change_pct": -100.0, "weight_pct": None},
            {"ticker": "CNC", "shares": 50.0, "avg_cost": 60.0, "last": 0.0,
             "pl_pct": -100.0, "day_change_pct": -100.0, "weight_pct": None},
        ],
    }
    monkeypatch.setattr(pc, "_fetch_summary", lambda email: summ)
    block = pc.live_portfolio_block("ajaykandakatla@gmail.com")
    assert block is not None
    assert "-100" not in block and "$0" not in block      # no fake wipeout
    assert "live quotes unavailable" in block
    assert "Cost basis $35,000" in block                  # cost basis still real
    assert "LRCX:" in block and "no live quote" in block


# ── soft-fail contract (NEGATIVES) ──────────────────────────────────────────

def test_no_holdings_returns_none(monkeypatch):
    monkeypatch.setattr(pc, "_fetch_summary",
                        lambda email: {"available": False, "count": 0, "rows": []})
    assert pc.live_portfolio_block("ajaykandakatla@gmail.com") is None


def test_empty_rows_returns_none(monkeypatch):
    monkeypatch.setattr(pc, "_fetch_summary",
                        lambda email: {"available": True, "rows": []})
    assert pc.live_portfolio_block("ajaykandakatla@gmail.com") is None


def test_summary_exception_returns_none_not_raise(monkeypatch):
    def _boom(email):
        raise RuntimeError("mongo is down")
    monkeypatch.setattr(pc, "_fetch_summary", _boom)
    # Must swallow and return None — a chat turn cannot die over portfolio data.
    assert pc.live_portfolio_block("ajaykandakatla@gmail.com") is None


def test_empty_email_returns_none_without_fetch(monkeypatch):
    def _must_not_call(email):
        raise AssertionError("should not fetch for an empty email")
    monkeypatch.setattr(pc, "_fetch_summary", _must_not_call)
    assert pc.live_portfolio_block("") is None
    assert pc.live_portfolio_block(None) is None


def test_missing_quote_fields_dont_crash(monkeypatch):
    """A quote outage leaves last/avg/weight/pl as None — block still renders."""
    summ = {
        "available": True, "count": 1,
        "total_value": None, "pl_dollars": None, "pl_pct": None, "day_dollars": None,
        "rows": [{"ticker": "RNG", "shares": 50.0, "avg_cost": None, "last": None,
                  "pl_pct": None, "day_change_pct": None, "weight_pct": None}],
    }
    monkeypatch.setattr(pc, "_fetch_summary", lambda email: summ)
    block = pc.live_portfolio_block("ajaykandakatla@gmail.com")
    assert block is not None
    assert "RNG:" in block
    assert "—" in block            # placeholders, never a crash or "None"


# ── injection + agent framing ───────────────────────────────────────────────

def test_portfolio_block_injected_into_system_prompt():
    sp = build_system_prompt(None, "## PORTFOLIO_SENTINEL\n- MU: 42 sh")
    assert "PORTFOLIO_SENTINEL" in sp


def test_none_portfolio_omitted_cleanly():
    sp = build_system_prompt({"path": "/sepa"}, None)
    # Page context still rendered, and no stray "None" leaked into the prompt.
    assert "/sepa" in sp
    assert "PORTFOLIO_SENTINEL" not in sp


def test_agent_framing_present_and_disclaimers_suppressed():
    base = SYSTEM_PROMPT_BASE
    # His agent, Minervini lens.
    assert "personal trading agent" in base
    assert "not a compliance bot" in base
    assert "Minervini SEPA" in base
    # Reflexive "not financial advice" hedging is explicitly suppressed.
    assert "Never add them" in base
    assert "not financial advice" in base.lower()   # named only to forbid it
    # Still guards against invented numbers (Rule #1 spirit).
    assert "do NOT invent numbers" in base
    # The stale hardcoded cash figure is gone.
    assert "$40k cash at Fidelity" not in base
