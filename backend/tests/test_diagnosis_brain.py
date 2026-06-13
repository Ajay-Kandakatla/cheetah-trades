"""Holding-diagnosis × Minervini brain — grounding is OPTIONAL and soft-fails.

The write-up's hold/sell teaching point is grounded in retrieved Minervini
passages so its [cite] is a real page. That grounding must NEVER take down the
diagnosis: a brain that's absent, empty, or erroring returns None and the
write-up falls back to the legacy prompt. Negative + positive paths.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import types

# Load diagnosis.py STANDALONE — importing the `portfolio` package trips a
# py3.9 annotation-eval quirk (same reason test_portfolio_diagnosis.py does this).
_PATH = os.path.join(os.path.dirname(__file__), "..", "portfolio", "diagnosis.py")
_spec = importlib.util.spec_from_file_location("diagnosis_mod", _PATH)
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)


def _install_fake_brain(monkeypatch, search_impl):
    """Inject a fake `brain.retriever` so the test doesn't depend on the real
    BM25 corpus / Mongo being present."""
    fake_ret = types.ModuleType("brain.retriever")
    fake_ret.search_multi = search_impl
    fake_pkg = types.ModuleType("brain")
    fake_pkg.retriever = fake_ret
    monkeypatch.setitem(sys.modules, "brain", fake_pkg)
    monkeypatch.setitem(sys.modules, "brain.retriever", fake_ret)


def test_soft_fails_to_none_when_the_brain_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("brain down")
    _install_fake_brain(monkeypatch, boom)
    # Must return None, never propagate the error.
    assert D._book_passages({"position": {"verdict": "TIGHTEN_STOP"}}) is None


def test_none_when_the_brain_returns_empty(monkeypatch):
    _install_fake_brain(monkeypatch, lambda queries, k=5: [])
    assert D._book_passages({"position": {"verdict": "HOLD"}}) is None


def test_returns_passages_and_adds_riskoff_query_for_tighten(monkeypatch):
    captured = {}
    passages = [{"cite": "TLSW p.295", "text": "raise the stop as it advances"}]

    def fake(queries, k=5):
        captured["queries"] = list(queries)
        return passages

    _install_fake_brain(monkeypatch, fake)
    out = D._book_passages({"position": {"verdict": "TIGHTEN_STOP"}})
    assert out == passages
    assert any("risk-off" in q for q in captured["queries"])


def test_plain_hold_keeps_the_query_set_minimal(monkeypatch):
    captured = {}

    def fake(queries, k=5):
        captured["queries"] = list(queries)
        return [{"cite": "x", "text": "y"}]

    _install_fake_brain(monkeypatch, fake)
    D._book_passages({"position": {"verdict": "HOLD"}})
    # A plain HOLD doesn't pull risk-off / sell-rule passages.
    assert not any("risk-off" in q for q in captured["queries"])
    assert not any("50-day 200-day" in q for q in captured["queries"])
