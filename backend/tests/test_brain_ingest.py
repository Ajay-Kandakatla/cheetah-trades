"""Brain ingest — chunker behavior + wipe-and-replace (FakeColl, no Mongo).

Host-runnable (py3.9): cd backend && python3 -m pytest tests/test_brain_ingest.py -q
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.ingest import build_chunks, chunk_page, run_ingest


class FakeColl:
    """Dict-backed stand-in for Mongo brain_chunks (house pattern)."""
    def __init__(self):
        self.docs = []

    def find_one(self, q=None, sort=None, **kw):
        docs = list(self.docs)
        if sort:
            field, direction = sort[0]
            docs.sort(key=lambda d: d.get(field) or 0, reverse=(direction == -1))
        return dict(docs[0]) if docs else None

    def delete_many(self, q):
        self.docs = []

    def insert_many(self, docs):
        self.docs.extend(dict(d) for d in docs)


# ── chunk_page ───────────────────────────────────────────────────────────────

def test_short_page_single_chunk():
    assert chunk_page("Cut your losses quickly.") == ["Cut your losses quickly."]


def test_empty_page_no_chunks():
    assert chunk_page("") == []
    assert chunk_page("   \n  ") == []


def _long_text(n=40):
    # Distinct, numbered sentences so overlap is verifiable.
    return " ".join(f"Sentence number {i} talks about disciplined trading rules." for i in range(n))


def test_long_page_splits_near_target():
    chunks = chunk_page(_long_text(), target=900, overlap=150)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 900 + 200          # sentence-boundary slack only
    # All content survives the split (modulo whitespace normalization).
    joined = " ".join(chunks)
    for i in range(40):
        assert f"Sentence number {i} " in joined or joined.endswith(f"Sentence number {i} talks about disciplined trading rules.")


def test_chunks_overlap_on_sentence_boundary():
    chunks = chunk_page(_long_text(), target=900, overlap=150)
    for a, b in zip(chunks, chunks[1:]):
        # The next chunk starts with trailing sentences of the previous one.
        first_sentence_of_b = b.split(".")[0] + "."
        assert first_sentence_of_b in a, (
            "consecutive chunks must share ~overlap chars of trailing text")


def test_no_mid_sentence_cuts_for_normal_prose():
    chunks = chunk_page(_long_text(), target=900, overlap=150)
    for c in chunks:
        assert c.endswith("rules."), "chunks should end on a sentence boundary"


# ── build_chunks (ids + metadata) ────────────────────────────────────────────

PAGES = [
    {"book": "tlsw", "pdf_page": 125, "printed_page": 110, "chapter": 5,
     "text": _long_text(30)},
    {"book": "ttlac", "pdf_page": 87, "printed_page": None, "chapter": 4,
     "text": "Risk first. Always know your stop before you buy."},
]


def test_stable_ids_and_metadata():
    docs = build_chunks(PAGES, corpus_version=3, ingested_at="2026-06-12T00:00:00Z")
    tlsw = [d for d in docs if d["book"] == "tlsw"]
    ttlac = [d for d in docs if d["book"] == "ttlac"]
    assert len(tlsw) > 1 and len(ttlac) == 1
    assert [d["chunk_id"] for d in tlsw] == [f"tlsw-125-{n}" for n in range(len(tlsw))]
    assert ttlac[0]["chunk_id"] == "ttlac-87-0"
    for d in tlsw:
        assert d["printed_page"] == 110 and d["chapter"] == 5 and d["pdf_page"] == 125
    assert ttlac[0]["printed_page"] is None and ttlac[0]["chapter"] == 4
    for d in docs:
        assert d["corpus_version"] == 3
        assert d["ingested_at"] == "2026-06-12T00:00:00Z"


def test_ids_stable_across_reingest():
    a = build_chunks(PAGES, corpus_version=1)
    b = build_chunks(PAGES, corpus_version=2)
    assert [d["chunk_id"] for d in a] == [d["chunk_id"] for d in b]


# ── run_ingest (wipe-and-replace + version bump) ─────────────────────────────

def _write_jsonl(tmp_path):
    p = tmp_path / "corpus.jsonl"
    with open(p, "w") as fh:
        for rec in PAGES:
            fh.write(json.dumps(rec) + "\n")
    return str(p)


def test_wipe_and_replace_bumps_version(tmp_path):
    coll = FakeColl()
    coll.insert_many([{"chunk_id": "stale-1-0", "book": "tlsw",
                       "corpus_version": 3, "text": "old"}])
    summary = run_ingest(_write_jsonl(tmp_path), coll=coll)
    assert summary["corpus_version"] == 4           # bumped past the old 3
    assert all(d["corpus_version"] == 4 for d in coll.docs)
    assert not any(d["chunk_id"] == "stale-1-0" for d in coll.docs)  # wiped
    assert summary["pages"] == 2
    assert summary["chunks"] == len(coll.docs)
    assert set(summary["per_book"]) == {"tlsw", "ttlac"}
    assert summary["per_book"]["ttlac"] == 1


def test_fresh_ingest_starts_at_version_1(tmp_path):
    coll = FakeColl()
    summary = run_ingest(_write_jsonl(tmp_path), coll=coll)
    assert summary["corpus_version"] == 1
