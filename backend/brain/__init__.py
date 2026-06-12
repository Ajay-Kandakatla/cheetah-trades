"""Minervini Brain — RAG over Mark Minervini's two books.

Corpus: books/extracted_books.jsonl (host-extracted, gitignored) —
  - "tlsw"  Trade Like a Stock Market Wizard (2013), printed pages
            (printed_page = pdf_page - 15), chapters 1-13.
  - "ttlac" Think & Trade Like a Champion (ebook), SECTIONS 1-11.
            The ebook has NO print page numbers — citations say
            "ebook p.N" and are never presented as print pages.

Pieces:
  ingest.py    — CLI: python -m brain.ingest  (chunk + wipe-and-replace
                 into Mongo `brain_chunks`; derived data, rebuildable)
  retriever.py — pure-python BM25 over an in-process chunk cache
  persona.py   — the grounded "trading coach" SYSTEM_PROMPT
  api.py       — /brain/search, /brain/ask, /brain/status

HARD BOUNDARY (architect decision, locked by tests/test_brain_contracts.py):
the Auto-Pilot trading engine NEVER consumes this package — no retrieval
and no LLM in the trade loop. trading/ and sepa/scanner.py must not
import brain. The brain powers chat + chart-analysis citations only.
"""
