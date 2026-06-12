"""Ingest the extracted book corpus into Mongo `brain_chunks`.

CLI (run inside the api container, or on the host with MONGO_URL set):

    python -m brain.ingest                     # default jsonl path
    python -m brain.ingest --jsonl /tmp/extracted_books.jsonl

Chunking: per page, the text is split into ~900-char chunks with
~150-char overlap on sentence-ish boundaries. Every chunk doc:

    {chunk_id: "{book}-{pdf_page}-{n}",   # stable across re-ingests
     book, pdf_page, printed_page, chapter, text,
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
        for n, text in enumerate(chunk_page(rec.get("text") or "")):
            docs.append({
                "chunk_id":       f"{book}-{pdf_page}-{n}",
                "book":           book,
                "pdf_page":       pdf_page,
                "printed_page":   rec.get("printed_page"),
                "chapter":        rec.get("chapter"),
                "text":           text,
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
    print(f"  corpus_version: {summary['corpus_version']}")


if __name__ == "__main__":
    main()
