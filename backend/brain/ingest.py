"""Ingest the extracted book corpus into Mongo `brain_chunks`.

CLI (run inside the api container, or on the host with MONGO_URL set):

    python -m brain.ingest                     # default jsonl path
    python -m brain.ingest --jsonl /tmp/extracted_books.jsonl

Chunking: per page, the text is split into ~900-char chunks with
~150-char overlap on sentence-ish boundaries. Every chunk doc:

    {chunk_id: "{book}-{pdf_page}-{n}",   # stable across re-ingests
     book, pdf_page, printed_page, chapter, text,
     is_index,                             # True for index/TOC pages —
     #                                       excluded from retriever search
     ingested_at,                          # ISO-8601 string
     corpus_version}                       # int, bumped on each full ingest

The collection is WIPE-AND-REPLACE on every run — brain_chunks is derived
data, rebuildable from the jsonl at any time (unlike the perpetual ledgers
such as pattern_observations / trade_journal, which must never be wiped).
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import List, Optional

log = logging.getLogger("brain.ingest")

TARGET_CHARS = 900
OVERLAP_CHARS = 150


# ── index/TOC page detection (pure — unit-tested without Mongo) ──────────────

# An index entry line: "averaging down, 305" / "VCP, 198–203" /
# "Bitauto Holdings Ltd Ads (BITA), 32, 125, 126". The space after each
# comma is load-bearing: it keeps dollar amounts ("$24,000") and other
# thousands-separated numbers from matching.
_INDEX_ENTRY = re.compile(
    r",\s+\d{1,4}(?:\s*[–—-]\s*\d{1,4})?"
    r"(?:\s*,\s+\d{1,4}(?:\s*[–—-]\s*\d{1,4})?)*$")

_NON_ALPHA = re.compile(r"[^a-z]+")

# Real-corpus margins behind these thresholds: content pages peak at ONE
# matching line (a stray "..., 305" in prose); true index pages run 11-60
# matching lines at >= 0.59 density.
INDEX_MIN_ENTRY_LINES = 6
INDEX_MIN_ENTRY_FRACTION = 0.45

_INDEX_HEADERS = frozenset({"index", "contents"})


def is_index_page(text: str) -> bool:
    """True when a page is back-of-book index or front-matter TOC — pages
    that LIST topics with page numbers instead of teaching them, and that
    BM25 otherwise ranks above the actual content (their keyword density
    is enormous). Two heuristics, either suffices:

    1. header — one of the first 3 non-empty lines is "Index"/"Contents"
       (letters only, so the running head "INDEX", the bare "Index" title
       page, and the extraction artifact "C ontents" all normalize in);
    2. entry density — >= 6 non-empty lines AND >= 45% of them look like
       index entries ("term, 305" / "term, 198–203" / trailing page
       lists). Catches index continuation pages that carry no header.

    Pure function on one page's text — position-independent on purpose,
    so it needs no knowledge of book length or page ordering."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return False
    for ln in lines[:3]:
        if _NON_ALPHA.sub("", ln.lower()) in _INDEX_HEADERS:
            return True
    hits = sum(1 for ln in lines if _INDEX_ENTRY.search(ln))
    return (hits >= INDEX_MIN_ENTRY_LINES
            and hits / len(lines) >= INDEX_MIN_ENTRY_FRACTION)


# ── chunking (pure — unit-tested without Mongo) ──────────────────────────────

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def _sentences(text: str) -> List[str]:
    """Sentence-ish pieces: split on terminal punctuation + whitespace and
    on newlines (the PDF extraction newlines often mark layout breaks)."""
    return [p.strip() for p in _SENT_SPLIT.split(text or "") if p and p.strip()]


def chunk_page(text: str, target: int = TARGET_CHARS,
               overlap: int = OVERLAP_CHARS) -> List[str]:
    """Split one page's text into ~target-char chunks with ~overlap-char
    overlap, never cutting mid-sentence (pieces longer than `target` are
    hard-split as a last resort). Pure function."""
    norm = " ".join((text or "").split())
    if not norm:
        return []
    if len(norm) <= target:
        return [norm]

    pieces: List[str] = []
    for s in _sentences(text):
        s = " ".join(s.split())
        while len(s) > target:                      # pathological run-on
            pieces.append(s[:target])
            s = s[target - overlap:]
        if s:
            pieces.append(s)

    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0
    fresh = 0          # pieces appended since the last overlap seed —
    #                    guards against emitting a pure-overlap chunk
    for s in pieces:
        if cur and fresh and cur_len + 1 + len(s) > target:
            chunks.append(" ".join(cur))
            tail: List[str] = []                    # seed next chunk with
            tlen = 0                                # the trailing ~overlap
            for prev in reversed(cur):
                if tail and tlen + len(prev) + 1 > overlap:
                    break
                tail.insert(0, prev)
                tlen += len(prev) + 1
            cur, cur_len, fresh = tail, tlen, 0
        cur.append(s)
        cur_len += len(s) + 1
        fresh += 1
    if cur and fresh:
        chunks.append(" ".join(cur))
    return chunks


def build_chunks(records: List[dict], corpus_version: int,
                 ingested_at: Optional[str] = None) -> List[dict]:
    """Page records (jsonl rows) -> chunk docs. Pure function; chunk ids are
    stable across re-ingests: '{book}-{pdf_page}-{n}'."""
    stamp = ingested_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    docs: List[dict] = []
    for rec in records:
        book = rec.get("book")
        pdf_page = rec.get("pdf_page")
        page_text = rec.get("text") or ""
        is_index = is_index_page(page_text)
        for n, text in enumerate(chunk_page(page_text)):
            docs.append({
                "chunk_id":       f"{book}-{pdf_page}-{n}",
                "book":           book,
                "pdf_page":       pdf_page,
                "printed_page":   rec.get("printed_page"),
                "chapter":        rec.get("chapter"),
                "text":           text,
                "is_index":       is_index,
                "ingested_at":    stamp,
                "corpus_version": corpus_version,
            })
    return docs


# ── Mongo ────────────────────────────────────────────────────────────────────

def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        return MongoClient(url, serverSelectionTimeoutMS=4000)[db]["brain_chunks"]
    except Exception as exc:
        log.warning("brain_chunks mongo unavailable: %s", exc)
        return None


def _resolve_jsonl(path: Optional[str]) -> str:
    """Default: books/extracted_books.jsonl relative to backend/.
    Relative paths resolve against backend/; absolute paths pass through."""
    backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not path:
        return os.path.join(backend, "books", "extracted_books.jsonl")
    if os.path.isabs(path):
        return path
    cand = os.path.join(backend, path)
    return cand if os.path.exists(cand) else path


def run_ingest(jsonl_path: Optional[str] = None, coll=None) -> dict:
    """Read the corpus jsonl, chunk it, wipe-and-replace brain_chunks.
    Returns a summary dict (also what the CLI prints)."""
    path = _resolve_jsonl(jsonl_path)
    records: List[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    coll = coll if coll is not None else _coll()
    if coll is None:
        raise SystemExit("brain.ingest: Mongo unavailable (set MONGO_URL)")

    prev = coll.find_one({}, sort=[("corpus_version", -1)])
    version = int((prev or {}).get("corpus_version") or 0) + 1

    docs = build_chunks(records, version)
    if not docs:
        raise SystemExit(f"brain.ingest: no chunks built from {path}")

    coll.delete_many({})                 # wipe-and-replace: derived data
    coll.insert_many(docs)

    per_book: dict = {}
    for d in docs:
        per_book[d["book"]] = per_book.get(d["book"], 0) + 1
    return {
        "jsonl":          path,
        "pages":          len(records),
        "chunks":         len(docs),
        "index_chunks":   sum(1 for d in docs if d["is_index"]),
        "per_book":       per_book,
        "corpus_version": version,
    }


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description="Chunk the Minervini book corpus into Mongo brain_chunks "
                    "(wipe-and-replace).")
    ap.add_argument("--jsonl", default=None,
                    help="corpus jsonl (default: books/extracted_books.jsonl "
                         "relative to backend/)")
    args = ap.parse_args(argv)
    summary = run_ingest(args.jsonl)
    print("brain.ingest complete:")
    print(f"  pages:          {summary['pages']}")
    print(f"  chunks:         {summary['chunks']}")
    for book, n in sorted(summary["per_book"].items()):
        print(f"    {book}: {n}")
    print(f"  index_chunks:   {summary['index_chunks']} (index/TOC — excluded from search)")
    print(f"  corpus_version: {summary['corpus_version']}")


if __name__ == "__main__":
    main()
