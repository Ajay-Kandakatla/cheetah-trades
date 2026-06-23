"""Pure-python BM25 retrieval over the `brain_chunks` collection.

Why BM25 and not embeddings: the corpus is tiny (~2k chunks, two books)
and entirely in-process — lexical BM25 with no new pip deps retrieves
well at this scale and keeps the container image unchanged. The upgrade
path (if recall ever disappoints) is documented in
docs/sepa/brain_methodology.md.

Cache: all chunks load from Mongo ONCE into module memory and are
re-loaded only when `corpus_version` changes (i.e. after a re-ingest).

Index/TOC pages: chunks tagged `is_index` at ingest (back-of-book index,
contents pages — see brain/ingest.py:is_index_page) are never returned
by search — their "term, page–page" density makes them BM25 magnets that
outrank the pages actually teaching the concept. Untagged chunks from a
pre-tagging ingest keep working (the flag simply reads falsy).

The BM25 math itself is PURE — `bm25_scores(query_tokens, corpus)` takes
its corpus explicitly and is unit-tested without Mongo.

Citation format (strict, used everywhere in the app):
    tlsw  -> "TLSW p.{printed_page}"
    tlsw front matter (printed_page < 1) -> "TLSW (pdf p.{pdf_page})"
    ttlac -> "TTLAC §{chapter} (ebook p.{pdf_page})"
The TTLAC ebook has no print page numbers — its cites always say
"ebook p.N", never bare page numbers. Same honesty rule for TLSW front
matter, where the extraction's fixed pdf->print offset would otherwise
fabricate zero/negative print pages.
"""
from __future__ import annotations

import logging
import math
import os
import re
import threading
from typing import Dict, List, Optional

log = logging.getLogger("brain.retriever")

K1 = 1.5
B = 0.75

# Tiny stopword list — just the glue words that would otherwise dominate
# question-style queries ("what does the book say about ...").
STOPWORDS = frozenset(
    "a an and are as at be but by can do does for from has have how i if "
    "in is it my not of on or say says that the this to was we what when "
    "will with you your".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    """Lowercase, alnum split, stopwords dropped."""
    return [t for t in _TOKEN_RE.findall((text or "").lower())
            if t not in STOPWORDS]


# ── BM25 (pure — no Mongo, no cache) ─────────────────────────────────────────

def _build_index(token_docs: List[List[str]]) -> dict:
    """Precompute term freqs / doc freqs / lengths for a token corpus."""
    freqs: List[Dict[str, int]] = []
    df: Dict[str, int] = {}
    for toks in token_docs:
        c: Dict[str, int] = {}
        for t in toks:
            c[t] = c.get(t, 0) + 1
        freqs.append(c)
        for t in c:
            df[t] = df.get(t, 0) + 1
    doc_lens = [len(t) for t in token_docs]
    n = len(token_docs)
    avgdl = (sum(doc_lens) / n) if n else 0.0
    return {"freqs": freqs, "df": df, "doc_lens": doc_lens,
            "avgdl": avgdl, "n": n}


def _score_index(query_tokens: List[str], idx: dict,
                 k1: float = K1, b: float = B) -> List[float]:
    n = idx["n"]
    scores = [0.0] * n
    if not n or not query_tokens:
        return scores
    avgdl = idx["avgdl"] or 1.0
    for term in query_tokens:
        d_f = idx["df"].get(term)
        if not d_f:
            continue
        idf = math.log(1.0 + (n - d_f + 0.5) / (d_f + 0.5))
        for i, fr in enumerate(idx["freqs"]):
            tf = fr.get(term)
            if not tf:
                continue
            denom = tf + k1 * (1.0 - b + b * idx["doc_lens"][i] / avgdl)
            scores[i] += idf * tf * (k1 + 1.0) / denom
    return scores


def bm25_scores(query_tokens: List[str], corpus: List[List[str]],
                k1: float = K1, b: float = B) -> List[float]:
    """PURE BM25: corpus is an explicit list of token lists. Returns one
    score per corpus doc (0.0 when no query term matches)."""
    return _score_index(query_tokens, _build_index(corpus), k1, b)


# ── citation strings ─────────────────────────────────────────────────────────

def cite_for(doc: dict) -> str:
    """The strict app-wide citation string for one chunk."""
    if doc.get("book") == "tlsw":
        pp = doc.get("printed_page")
        if pp is None or pp < 1:
            # Front matter (title/copyright/foreword): the extraction's
            # fixed pdf->print offset goes negative there. Never emit a
            # fake print page — fall back to the honest pdf locator.
            return "TLSW (pdf p.%s)" % doc.get("pdf_page")
        return "TLSW p.%s" % pp
    ch = doc.get("chapter")
    if ch is None:                       # ttlac front matter (no section)
        return "TTLAC (ebook p.%s)" % doc.get("pdf_page")
    return "TTLAC §%s (ebook p.%s)" % (ch, doc.get("pdf_page"))


# ── in-process cache over Mongo ──────────────────────────────────────────────

_CACHE: dict = {"version": None, "chunks": [], "index": None}
_LOCK = threading.Lock()


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        return MongoClient(url, serverSelectionTimeoutMS=2000)[db]["brain_chunks"]
    except Exception as exc:
        log.warning("brain_chunks mongo unavailable: %s", exc)
        return None


def _current_version() -> Optional[int]:
    """Max corpus_version in Mongo, or None when empty/unavailable.
    Cheap query — runs per search to detect re-ingests."""
    coll = _coll()
    if coll is None:
        return None
    try:
        doc = coll.find_one({}, sort=[("corpus_version", -1)])
    except Exception as exc:
        log.warning("brain_chunks version probe failed: %s", exc)
        return None
    if not doc:
        return None
    return int(doc.get("corpus_version") or 0)


def prime(chunks: List[dict], version: Optional[int]) -> None:
    """Load chunks into the in-process cache (also the test seam)."""
    with _LOCK:
        clean = []
        for c in chunks:
            c = dict(c)
            c.pop("_id", None)
            clean.append(c)
        _CACHE["chunks"] = clean
        _CACHE["index"] = _build_index([tokenize(c.get("text") or "")
                                        for c in clean])
        _CACHE["version"] = version


def _ensure_loaded() -> bool:
    """True when the cache holds chunks at the current corpus_version."""
    v = _current_version()
    if v is None:
        return False
    if _CACHE["version"] != v or _CACHE["index"] is None:
        coll = _coll()
        if coll is None:
            return False
        try:
            chunks = list(coll.find({}, {"_id": 0}))
        except Exception as exc:
            log.warning("brain_chunks load failed: %s", exc)
            return False
        prime(chunks, v)
        log.info("brain cache loaded: %d chunks (corpus_version=%s)",
                 len(chunks), v)
    return bool(_CACHE["chunks"])


def _search_loaded(query: str, k: int, book: Optional[str]) -> List[dict]:
    scores = _score_index(tokenize(query), _CACHE["index"])
    chunks = _CACHE["chunks"]
    hits = []
    for i, c in enumerate(chunks):
        if scores[i] <= 0.0:
            continue
        if c.get("is_index"):
            # Back-of-book index / TOC pages (tagged at ingest): their
            # keyword density makes them BM25 magnets — "VCP, 198–203"
            # outranked the page that actually teaches the VCP. They
            # locate content, they aren't content; never surface them.
            continue
        if book and c.get("book") != book:
            continue
        hits.append((scores[i], i))
    hits.sort(key=lambda t: (-t[0], chunks[t[1]].get("chunk_id") or ""))
    out = []
    for s, i in hits[:k]:
        row = dict(chunks[i])
        row["score"] = round(s, 4)
        row["cite"] = cite_for(row)
        out.append(row)
    return out


def search(query: str, k: int = 8, book: Optional[str] = None) -> List[dict]:
    """Top-k chunks for one query. Rows = chunk fields + score + cite.
    Empty list when the corpus isn't ingested / Mongo is down."""
    if not _ensure_loaded():
        return []
    return _search_loaded(query, k, book)


def search_multi(queries: List[str], k: int = 8,
                 book: Optional[str] = None) -> List[dict]:
    """Union of per-query searches, deduped by chunk_id keeping each
    chunk's BEST score, ordered best-score-first, truncated to k."""
    if not _ensure_loaded():
        return []
    best: Dict[str, dict] = {}
    for q in queries or []:
        for row in _search_loaded(q, k, book):
            cid = row.get("chunk_id")
            prev = best.get(cid)
            if prev is None or row["score"] > prev["score"]:
                best[cid] = row
    rows = sorted(best.values(),
                  key=lambda r: (-r["score"], r.get("chunk_id") or ""))
    return rows[:k]


BOTH_BOOKS = ("tlsw", "ttlac")


def search_balanced(queries: List[str], k: int = 10, min_per_book: int = 3,
                    books=BOTH_BOOKS) -> List[dict]:
    """`search_multi`, but with a per-book FLOOR so every book actually gets
    consulted. Each book in ``books`` that has any relevant (positive-score,
    non-index) chunk is guaranteed at least ``min(min_per_book, available)``
    chunks in the result — so a question that scores heavily on ONE book can
    never crowd the OTHER book entirely out of the grounding set the persona
    reasons over (the "verify BOTH books on every question" guarantee).

    A book with NO matching chunk is never forced in — the floor only applies
    where the book has real material, so we never inject off-topic passages.
    The global best chunks are always kept; the floor only ever displaces the
    LOWEST-scoring chunks of an over-represented book. Result is best-score
    ordered and capped at ``k``. Empty when the corpus isn't ingested.

    Why this and not just k-per-book: a plain union dilutes strong single-book
    answers (relative strength is mostly TLSW; the cheat/3-C is mostly TTLAC).
    The floor is a SAFETY NET for total dropout, not an equal-weight mandate —
    BM25 still decides the bulk of the slots."""
    if not _ensure_loaded():
        return []
    by_id: Dict[str, dict] = {r["chunk_id"]: r for r in search_multi(queries, k)}
    floor_ids: set = set()
    for b in books:
        for r in search_multi(queries, max(1, min_per_book), book=b):
            by_id.setdefault(r["chunk_id"], r)
            floor_ids.add(r["chunk_id"])           # book HAS material -> protect it
    rows = sorted(by_id.values(),
                  key=lambda r: (-r["score"], r.get("chunk_id") or ""))
    if len(rows) <= k:
        return rows
    # Over k: keep the floor chunks (the both-book guarantee), then fill the
    # remaining slots with the best non-floor chunks — back to k, score order.
    floor_rows = [r for r in rows if r["chunk_id"] in floor_ids]
    rest = [r for r in rows if r["chunk_id"] not in floor_ids]
    keep = {r["chunk_id"] for r in floor_rows[:k]}
    keep |= {r["chunk_id"] for r in rest[:max(0, k - len(floor_rows))]}
    return [r for r in rows if r["chunk_id"] in keep]


def status() -> dict:
    """{chunks, books: {tlsw, ttlac}, corpus_version} — for /brain/status."""
    loaded = _ensure_loaded()
    chunks = _CACHE["chunks"] if loaded else []
    per: Dict[str, int] = {}
    for c in chunks:
        per[c.get("book") or "?"] = per.get(c.get("book") or "?", 0) + 1
    return {
        "chunks": len(chunks),
        "books": {"tlsw": per.get("tlsw", 0), "ttlac": per.get("ttlac", 0)},
        "corpus_version": _CACHE["version"] if loaded else None,
    }
