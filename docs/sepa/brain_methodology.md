# Minervini Brain — methodology

RAG ("retrieval-augmented generation") layer over Mark Minervini's two
books, powering (a) the Minervini-persona mode in the app chat
(`POST /brain/ask`) and (b) book-grounded citations inside the existing
AI chart analysis (`sepa/chart_analysis.py`).

**What it is NOT:** an input to the Auto-Pilot trading engine. See
[The engine boundary](#the-engine-boundary-brain-never-trades).

## Corpus

`backend/books/extracted_books.jsonl` — host-extracted, **gitignored**
(copyrighted text never enters the repo). One JSON object per page:

```json
{"book": "tlsw"|"ttlac", "pdf_page": int, "printed_page": int|null,
 "chapter": int|null, "text": str}
```

| book | title | pages | page anchoring | chapters |
|---|---|---|---|---|
| `tlsw` | *Trade Like a Stock Market Wizard* (2013) | 352 | printed pages: `printed_page = pdf_page − 15` | 1–13 |
| `ttlac` | *Think & Trade Like a Champion* | 214 | **ebook pages only — the ebook has NO print page numbers** | SECTIONS 1–11 |

~912K chars total → ~2k chunks.

## Chunking (`brain/ingest.py`)

- Per page, split into **~900-char chunks with ~150-char overlap**, on
  sentence-ish boundaries (terminal punctuation / newlines); pathological
  run-ons are hard-split as a last resort.
- Chunk ids are **stable across re-ingests**: `"{book}-{pdf_page}-{n}"`.
- Each chunk doc: `{chunk_id, book, pdf_page, printed_page, chapter,
  text, is_index, ingested_at, corpus_version}`.
- Storage: Mongo collection **`brain_chunks`**, **wipe-and-replace** on
  every ingest with `corpus_version` bumped. This collection is *derived
  data* — rebuildable from the jsonl at any time, unlike the perpetual
  ledgers (`pattern_observations`, `trade_journal`) which are never wiped.

### Index/TOC page detection (`is_index_page`)

Back-of-book index pages are short, keyword-dense lists ("VCP, 198–203"),
which makes them **BM25 magnets**: before tagging, the query *"volatility
contraction pattern pivot"* returned TLSW p.330 and p.322 (index pages)
**above** TLSW p.198 — the page that actually teaches the VCP. TTLAC had
the same failure (its index at ebook p.197–213).

Ingest tags every chunk with `is_index` (pure, position-independent
heuristics on the page text; either one suffices):

1. **Header** — one of the first 3 non-empty lines normalizes (letters
   only, lowercased) to `index` or `contents`. Catches the running head
   `INDEX`, the bare `Index` title page, and the extraction artifact
   `C ontents` in the TLSW front matter.
2. **Entry density** — ≥ 6 non-empty lines AND ≥ 45% of them match the
   index-entry shape `term, 305` / `term, 198–203` / `term, 32, 125, 126`
   (en-dash or hyphen ranges, trailing page lists). The space after the
   comma is load-bearing: dollar amounts (`$24,000`) on chart pages have
   none and must not match. Catches index continuation pages that carry
   no header.

Real-corpus margins (why 6 / 0.45 is safe): content pages peak at **one**
matching line; true index pages run **11–60** matching lines at ≥ 0.59
density. On the real corpus this flags exactly TLSW pdf 8–9 (contents),
334 + 336–346 (index) and TTLAC pdf 5 (contents), 197–213 (index) — 54
chunks of 1410 — with zero content pages flagged.

Chunks are **tagged, not skipped** (`{"is_index": true}` stays in Mongo,
inspectable and reversible); exclusion happens in the retriever. The CLI
prints `index_chunks` so a re-ingest can be sanity-checked at a glance.

## Retrieval: BM25, pure python (`brain/retriever.py`)

- Okapi BM25, `k1 = 1.5`, `b = 0.75`; tokenizer = lowercase, alnum
  split, tiny stopword list. **No new pip dependencies** — the corpus is
  tiny and lexical retrieval at this scale is strong, and the book
  vocabulary ("pivot", "VCP", "stop loss") is exactly what users type.
- All chunks live in an **in-process cache** loaded from Mongo once and
  invalidated when `corpus_version` changes (cheap max-version probe per
  search), so a re-ingest is picked up without a restart.
- `search(query, k, book)` and `search_multi(queries, k)` — the ask path
  searches both the raw question AND a distilled-keyword variant, unions
  by `chunk_id` keeping each chunk's best score.
- **`search_balanced(queries, k, min_per_book=3)` — the both-book floor.**
  The `/brain/ask` path retrieves through this, *not* raw `search_multi`.
  Plain top-k is a single global ranking, so a question whose vocabulary
  lives mostly in one book can take **all** k slots and drop the other book
  entirely — on the live corpus *"climax top / selling into strength"*
  returned 0 TLSW chunks (all 10 were TTLAC), even though TLSW devotes a
  chapter to selling into strength. `search_balanced` guarantees every book
  with **any** relevant (positive-score, non-index) chunk at least
  `min(min_per_book, available)` seats, so **both books are consulted on
  every question**. It is a safety net, not an equal-weight mandate: a book
  with **no** matching chunk is never forced in (no off-topic passages to
  miscite), the global best chunks are always kept, and the floor only ever
  displaces an over-represented book's lowest-scoring chunks. Result stays
  capped at `k` and best-score ordered. This is Ajay's "verify both books
  when I ask a question" requirement, made deterministic.
- **Index/TOC chunks never surface**: any chunk tagged `is_index` at
  ingest is filtered out of search results regardless of score (an index
  page *locates* content, it isn't content — and citing "TLSW p.330" at
  a user asking about the VCP is a useless answer). Chunks from a
  pre-tagging ingest carry no flag and keep working unchanged.
- The BM25 math is a **pure function** (`bm25_scores(query_tokens,
  corpus)`) unit-tested without Mongo (`tests/test_brain_retriever.py`).

**Embeddings upgrade path** (only if recall disappoints): add an
`embedding` field per chunk at ingest (any local embedding model via LM
Studio), cosine-rerank the BM25 top-50 in `search()`. The API surface
(`search`/`search_multi` row shape) would not change, so callers and
tests stay put. Not built now — BM25 + tiny corpus didn't justify the
moving parts.

## Citation formats (strict, app-wide)

| book | format | example |
|---|---|---|
| tlsw | `TLSW p.{printed_page}` | `TLSW p.110` |
| tlsw front matter (printed_page < 1) | `TLSW (pdf p.{pdf_page})` | `TLSW (pdf p.10)` |
| ttlac | `TTLAC §{chapter} (ebook p.{pdf_page})` | `TTLAC §4 (ebook p.87)` |
| ttlac front matter (no section) | `TTLAC (ebook p.{pdf_page})` | `TTLAC (ebook p.3)` |

**TTLAC honesty note:** the TTLAC ebook has no print page numbers. Its
citations always carry the `ebook p.` label and are **never presented as
print pages** — anyone checking against a paper copy must navigate by
SECTION, not page. The persona prompt restates this rule to the model.

**TLSW front-matter note:** the extraction derives `printed_page` as a
fixed `pdf_page - 15` offset, which goes zero/negative across the 14
front-matter pages (title/copyright/contents/foreword). Those chunks cite
as `TLSW (pdf p.N)` — never a fabricated negative print page
(regression-locked in `tests/test_brain_retriever.py`).

## Grounding rules (`brain/persona.py`, source-guarded)

- Answers come **only from the retrieved passages**; every factual claim
  carries a citation in the formats above.
- If the passages don't cover the question, the persona says **"the
  books don't cover this"** — no improvising, no numbers/thresholds/page
  numbers invented.
- **Copyright guardrail:** direct quotes ≤ 25 words, paraphrase
  preferred. The brain teaches what the books say; it does not reproduce
  the books (and the corpus itself stays out of git).
- The persona states it is **not Mark Minervini** and is **not
  investment advice**; asked for a personal buy/sell call it restates
  the relevant book rules with cites and declines to issue an order.
- Exact phrases are locked by `tests/test_brain_contracts.py` — editing
  the persona means updating the contract test in the same change.

## Chart-analysis integration (`sepa/chart_analysis.py`)

After fact-gathering, the analyzer *optionally* pulls ≤6 setup-specific
passages (`search_multi` on pattern/setup + "stop loss placement" +
"extended chase" style queries) and appends a `BOOK PASSAGES (cite when
you use them)` block. The model may add an optional `"citations": [str]`
array — every entry is validated by substring-match against the provided
cite strings; invalid entries are dropped, never fatal. **Soft-fail is
contract:** brain absent / not ingested / raising leaves the prompt and
system byte-identical to the legacy path (locked by
`test_brain_contracts.py`).

## The engine boundary (brain never trades)

Architect decision (2026-06-12): the Auto-Pilot trading engine does
**not** consume the brain. No retrieval and no LLM anywhere in the trade
loop — entries, exits, stops, and sizing remain fully deterministic
(`trading/risk_rules.py`, TLSW pp.291–315). Locked by
`tests/test_brain_contracts.py`: no `brain` reference may appear in any
`trading/` source file or in `sepa/scanner.py`. The brain explains the
rules; the engine executes them.

## Ingest runbook

The jsonl lives on the host (gitignored). To (re)ingest into the running
stack:

```bash
docker cp backend/books/extracted_books.jsonl cheetah-api:/tmp/extracted_books.jsonl
docker exec cheetah-api python -m brain.ingest --jsonl /tmp/extracted_books.jsonl
```

(Container name per `docker compose ps`; the api container already has
`MONGO_URL` set.) The CLI prints pages/chunks-per-book/index_chunks/
corpus_version — expect `index_chunks: 54` for the current corpus (TLSW
contents + index, TTLAC contents + index); verify chunk totals with
`GET /brain/status`. Re-running is always safe — wipe-and-replace with a
version bump, and the in-process retriever cache reloads itself on the
next search.

## Tests

- `tests/test_brain_ingest.py` — chunker (overlap, sentence boundaries,
  stable ids, metadata), index/TOC detection on synthetic pages (entry
  density, headers, dollar-amount + market-index non-matches), is_index
  tagging, wipe-and-replace + version bump (FakeColl).
- `tests/test_brain_retriever.py` — BM25 pure math, tokenizer, exact
  cite strings for both books, book filter, `search_multi` dedupe,
  index-chunk exclusion (REGRESSION: index pages outranked TLSW p.198
  for the VCP query; raw-BM25 sanity check proves the filter does real
  work), untagged legacy chunks still searchable, **both-book floor**
  (`search_balanced`: floors in the crowded-out book, does NOT force a
  no-match book, keeps the global best first, respects `k`).
- `tests/test_brain_ask.py` — prompt assembly (passages + cites +
  persona system), history clipping, empty-corpus short-circuit (no LLM
  call), citation shape, LLM-error → 502, **both-book floor at the ask
  layer** (REGRESSION: a one-book-dominant query still lands the other
  book's chunk in both the prompt and the citation chips).
- `tests/test_brain_contracts.py` — persona source-guard, **engine
  boundary lock**, chart-analysis soft-fail, citation validation,
  import-lightness (pandas/numpy/pymongo blocked).
