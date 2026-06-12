"""Brain retriever — BM25 pure math (no Mongo) + cached search + cites.

The citation strings are CONTRACT: tlsw -> "TLSW p.{printed_page}";
ttlac -> "TTLAC §{chapter} (ebook p.{pdf_page})" — the TTLAC ebook has no
print page numbers, so its label must always say "ebook p.".

Host-runnable (py3.9): cd backend && python3 -m pytest tests/test_brain_retriever.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain import retriever


# ── tokenizer ────────────────────────────────────────────────────────────────

def test_tokenize_lowercase_alnum_stopwords():
    toks = retriever.tokenize("What IS the Stop-Loss at 8%?")
    assert toks == ["stop", "loss", "8"]
    assert "the" not in toks and "is" not in toks and "at" not in toks


# ── BM25 pure math (explicit corpus, zero Mongo) ─────────────────────────────

CORPUS = [
    ["stop", "loss", "placement", "protects", "capital"],
    ["volume", "dries", "up", "before", "pivot", "buy", "point"],
    ["stop", "stop", "stop", "loss", "discipline"],
    ["earnings", "growth", "accelerates", "quarters"],
]


def test_exact_term_ranks_matching_docs():
    scores = retriever.bm25_scores(["pivot"], CORPUS)
    assert scores[1] > 0
    assert scores[0] == scores[2] == scores[3] == 0.0


def test_multi_term_favors_doc_with_both():
    scores = retriever.bm25_scores(["stop", "loss"], CORPUS)
    assert scores[0] > 0 and scores[2] > 0
    assert scores[1] == 0.0 and scores[3] == 0.0
    # Higher tf scores higher (same doc length ballpark).
    assert scores[2] > scores[0] * 0.5      # tf saturation, but still ranked


def test_unknown_term_all_zero():
    assert retriever.bm25_scores(["zebra"], CORPUS) == [0.0] * 4


def test_empty_inputs():
    assert retriever.bm25_scores([], CORPUS) == [0.0] * 4
    assert retriever.bm25_scores(["stop"], []) == []


def test_term_in_every_doc_has_low_idf():
    corpus = [["stop", "alpha"], ["stop", "beta"], ["stop", "gamma"]]
    everywhere = retriever.bm25_scores(["stop"], corpus)
    rare = retriever.bm25_scores(["alpha"], corpus)
    assert rare[0] > everywhere[0]          # rarity outweighs ubiquity


# ── citation strings (EXACT contract) ────────────────────────────────────────

def test_cite_tlsw_printed_page():
    assert retriever.cite_for({"book": "tlsw", "printed_page": 110,
                               "pdf_page": 125, "chapter": 5}) == "TLSW p.110"


def test_cite_ttlac_section_and_ebook_page():
    assert retriever.cite_for({"book": "ttlac", "printed_page": None,
                               "pdf_page": 87, "chapter": 4}) \
        == "TTLAC §4 (ebook p.87)"


def test_cite_ttlac_front_matter_no_section():
    assert retriever.cite_for({"book": "ttlac", "printed_page": None,
                               "pdf_page": 3, "chapter": None}) \
        == "TTLAC (ebook p.3)"


def test_ttlac_cite_never_a_bare_print_page():
    cite = retriever.cite_for({"book": "ttlac", "pdf_page": 87, "chapter": 4})
    assert "ebook p." in cite               # honesty: no fake print pages


def test_tlsw_front_matter_never_a_negative_print_page():
    """REGRESSION (real corpus): the extraction sets printed_page =
    pdf_page - 15 blindly, so TLSW front matter (foreword etc.) carried
    printed_page values of -13..0 — which rendered garbage cites like
    'TLSW p.-11'. Front matter falls back to the honest pdf locator."""
    for pp, pdf in [(-11, 4), (0, 15), (None, 2)]:
        cite = retriever.cite_for({"book": "tlsw", "printed_page": pp,
                                   "pdf_page": pdf, "chapter": None})
        assert cite == "TLSW (pdf p.%s)" % pdf
        assert "p.-" not in cite and "p.0" not in cite.replace("(pdf p.", "x")
    # Real chapters are untouched.
    assert retriever.cite_for({"book": "tlsw", "printed_page": 1,
                               "pdf_page": 16, "chapter": 1}) == "TLSW p.1"


# ── cached search (primed cache, monkeypatched version probe) ────────────────

DOCS = [
    {"chunk_id": "tlsw-125-0", "book": "tlsw", "pdf_page": 125,
     "printed_page": 110, "chapter": 5,
     "text": "Cut your losses quickly. The stop loss protects capital."},
    {"chunk_id": "tlsw-218-0", "book": "tlsw", "pdf_page": 218,
     "printed_page": 203, "chapter": 9,
     "text": "Volume dries up near the pivot buy point before the breakout."},
    {"chunk_id": "ttlac-87-0", "book": "ttlac", "pdf_page": 87,
     "printed_page": None, "chapter": 4,
     "text": "Set the stop loss before you buy; risk comes first."},
]


@pytest.fixture
def primed(monkeypatch):
    retriever.prime(DOCS, version=1)
    monkeypatch.setattr(retriever, "_current_version", lambda: 1)
    yield
    retriever.prime([], None)               # don't leak cache across tests


def test_search_returns_cite_and_score(primed):
    rows = retriever.search("stop loss", k=8)
    assert rows
    assert rows[0]["score"] > 0
    cites = {r["cite"] for r in rows}
    assert "TLSW p.110" in cites and "TTLAC §4 (ebook p.87)" in cites


def test_search_book_filter(primed):
    rows = retriever.search("stop loss", k=8, book="ttlac")
    assert rows and all(r["book"] == "ttlac" for r in rows)
    rows = retriever.search("stop loss", k=8, book="tlsw")
    assert rows and all(r["book"] == "tlsw" for r in rows)


def test_search_k_limit(primed):
    assert len(retriever.search("stop loss buy", k=1)) == 1


def test_search_multi_dedupes_by_chunk_id_best_score(primed):
    rows = retriever.search_multi(["stop loss", "stop loss protects capital"], k=8)
    ids = [r["chunk_id"] for r in rows]
    assert len(ids) == len(set(ids))        # deduped union
    # Best-score order (descending).
    scores = [r["score"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    # The capital-specific query should push tlsw-125-0 to the top.
    assert rows[0]["chunk_id"] == "tlsw-125-0"


def test_search_multi_unions_distinct_hits(primed):
    rows = retriever.search_multi(["pivot breakout volume", "risk comes first"], k=8)
    ids = {r["chunk_id"] for r in rows}
    assert "tlsw-218-0" in ids and "ttlac-87-0" in ids


def test_unavailable_corpus_returns_empty(monkeypatch):
    monkeypatch.setattr(retriever, "_current_version", lambda: None)
    assert retriever.search("stop loss") == []
    assert retriever.search_multi(["stop loss"]) == []
    st = retriever.status()
    assert st["chunks"] == 0 and st["corpus_version"] is None


def test_status_counts_per_book(primed):
    st = retriever.status()
    assert st == {"chunks": 3, "books": {"tlsw": 2, "ttlac": 1},
                  "corpus_version": 1}
