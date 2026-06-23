"""Brain /ask path — prompt assembly, grounding system, empty-corpus
short-circuit, citation shape. llm.chat is mocked; no network, no Mongo.

Host-runnable (py3.9): cd backend && python3 -m pytest tests/test_brain_ask.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import llm
from brain import api as brain_api
from brain import retriever
from brain.persona import SYSTEM_PROMPT
from fastapi import HTTPException

DOCS = [
    {"chunk_id": "tlsw-125-0", "book": "tlsw", "pdf_page": 125,
     "printed_page": 110, "chapter": 5,
     "text": "Cut your losses quickly. The stop loss protects capital."},
    {"chunk_id": "ttlac-87-0", "book": "ttlac", "pdf_page": 87,
     "printed_page": None, "chapter": 4,
     "text": "Set the stop loss before you buy; risk comes first."},
]


@pytest.fixture
def primed(monkeypatch):
    retriever.prime(DOCS, version=1)
    monkeypatch.setattr(retriever, "_current_version", lambda: 1)
    yield
    retriever.prime([], None)


@pytest.fixture
def fake_llm(monkeypatch):
    calls = {}

    def _chat(prompt, **kw):
        calls["prompt"] = prompt
        calls["system"] = kw.get("system")
        calls["provider"] = kw.get("provider")
        return {"ok": True, "text": "Cut losses fast (TLSW p.110).",
                "model": "claude-test", "latency_sec": 0.1}

    monkeypatch.setattr(llm, "chat", _chat)
    return calls


def test_ask_prompt_contains_passages_cites_and_persona(primed, fake_llm):
    out = brain_api.ask_impl("Where should my stop loss go?")
    assert out["answer"].startswith("Cut losses")
    # Passages + bracketed cite labels are in the prompt.
    assert "[TLSW p.110]" in fake_llm["prompt"]
    assert "[TTLAC §4 (ebook p.87)]" in fake_llm["prompt"]
    assert "stop loss protects capital" in fake_llm["prompt"]
    assert "QUESTION: Where should my stop loss go?" in fake_llm["prompt"]
    # The grounding persona is the system prompt, on Anthropic.
    assert fake_llm["system"] == SYSTEM_PROMPT
    assert fake_llm["provider"] == "anthropic"


def test_ask_citations_are_verbatim_cite_strings(primed, fake_llm):
    """FRONTEND CONTRACT: ChatWidget filters citations to strings and
    renders them verbatim as chips — dicts would silently never render."""
    out = brain_api.ask_impl("stop loss placement")
    assert out["retrieved"] > 0
    assert out["citations"], "citations must be present when rows retrieved"
    for c in out["citations"]:
        assert isinstance(c, str)
    assert "TLSW p.110" in out["citations"]
    assert "TTLAC §4 (ebook p.87)" in out["citations"]
    # Deduped, never longer than the retrieved row count.
    assert len(out["citations"]) == len(set(out["citations"]))
    assert len(out["citations"]) <= out["retrieved"]


def test_llm_raising_becomes_502_not_crash(primed, monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("socket exploded")

    monkeypatch.setattr(llm, "chat", _boom)
    with pytest.raises(HTTPException) as exc:
        brain_api.ask_impl("stop loss")
    assert exc.value.status_code == 502
    assert "socket exploded" in exc.value.detail


def test_ask_includes_live_portfolio_labeled_non_book(primed, fake_llm):
    """The live-positions snapshot rides into the prompt so the coach knows
    what he holds — but labelled app state, never a book source to cite."""
    pf = ("## Ajay's LIVE portfolio\n"
          "- MU: 42 sh · $591.00 avg · $746.50 · +26.3% open · 60% of book")
    brain_api.ask_impl("should I trim my MU?", portfolio=pf)
    assert "MU: 42 sh" in fake_llm["prompt"]
    assert "LIVE PORTFOLIO" in fake_llm["prompt"]
    # Grounding contract intact: portfolio is app state, never cited as books.
    assert "never cite it as the books" in fake_llm["prompt"]


def test_ask_without_portfolio_omits_the_block(primed, fake_llm):
    brain_api.ask_impl("where does my stop go?")
    assert "LIVE PORTFOLIO" not in fake_llm["prompt"]


def test_ask_history_clipped_to_last_6_and_context_included(primed, fake_llm):
    history = [{"role": "user", "text": f"turn-{i}"} for i in range(8)]
    brain_api.ask_impl("stop loss", history=history, app_context="viewing NVDA chart")
    assert "turn-7" in fake_llm["prompt"] and "turn-2" in fake_llm["prompt"]
    assert "turn-0" not in fake_llm["prompt"] and "turn-1" not in fake_llm["prompt"]
    assert "viewing NVDA chart" in fake_llm["prompt"]
    assert "APP CONTEXT" in fake_llm["prompt"]


def test_empty_corpus_returns_not_ingested_without_llm(monkeypatch):
    retriever.prime([], None)
    monkeypatch.setattr(retriever, "_current_version", lambda: None)

    def _boom(*a, **kw):
        raise AssertionError("llm.chat must NOT be called on empty corpus")

    monkeypatch.setattr(llm, "chat", _boom)
    out = brain_api.ask_impl("stop loss")
    assert out["not_ingested"] is True
    assert out["citations"] == [] and out["retrieved"] == 0
    assert "python -m brain.ingest" in out["answer"]


def test_llm_failure_becomes_502(primed, monkeypatch):
    monkeypatch.setattr(llm, "chat",
                        lambda *a, **kw: {"ok": False, "error": "boom"})
    with pytest.raises(HTTPException) as exc:
        brain_api.ask_impl("stop loss")
    assert exc.value.status_code == 502
    assert "boom" in exc.value.detail


def _lopsided_docs():
    """11 TTLAC 'cheat' chunks dominate any cheat query; ONE TLSW chunk also
    speaks to it but scores lower — so under a plain top-10 it is crowded out
    entirely (the real-corpus 'all one book' dropout)."""
    docs = [{"chunk_id": f"ttlac-{100 + i}-0", "book": "ttlac",
             "pdf_page": 100 + i, "printed_page": None, "chapter": 7,
             "text": "The cheat is an early entry; cheat plateau, cheat "
                     "shakeout, cheat pivot."}
            for i in range(11)]
    docs.append({"chunk_id": "tlsw-243-0", "book": "tlsw", "pdf_page": 243,
                 "printed_page": 228, "chapter": 10,
                 "text": "Cirrus Logic formed a 3C pivot point cheat at the "
                         "breakout."})
    return docs


@pytest.fixture
def primed_lopsided(monkeypatch):
    retriever.prime(_lopsided_docs(), version=1)
    monkeypatch.setattr(retriever, "_current_version", lambda: 1)
    yield
    retriever.prime([], None)


def test_ask_consults_both_books_when_one_would_crowd_out_the_other(
        primed_lopsided, fake_llm):
    """REGRESSION (real corpus): a query like 'climax top / selling into
    strength' returned 0 TLSW chunks in the live brain — TTLAC filled all 10
    slots. ask_impl now routes through the per-book floor, so the relevant
    TLSW chunk reaches both the prompt the persona reads AND the citation
    chips Ajay sees — both books verified."""
    plain = retriever.search_multi(["cheat plateau shakeout pivot"], k=10)
    assert {r["book"] for r in plain} == {"ttlac"}, \
        "precondition: TLSW is crowded out of the plain top-10"

    out = brain_api.ask_impl("Tell me about the cheat plateau shakeout pivot")
    assert "[TLSW p.228]" in fake_llm["prompt"]              # reached the model
    assert "TLSW p.228" in out["citations"]                 # reached the chips
    assert any(c.startswith("TTLAC") for c in out["citations"])   # both books


def test_distill_drops_stopwords_and_dupes():
    d = brain_api._distill("What does the book say about the stop loss stop?")
    toks = d.split()
    assert "the" not in toks and "what" not in toks
    assert toks.count("stop") == 1
    assert "loss" in toks and "book" in toks
