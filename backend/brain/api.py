"""Brain API — book-grounded Q&A + raw retrieval debug.

GET  /brain/search?q=&k=&book=   raw BM25 rows (debug / UI)
POST /brain/ask                  {question, history?, app_context?} ->
                                 {answer, citations: [str], retrieved}
                                 (citations are verbatim cite strings —
                                 the frontend renders them as chips)
GET  /brain/status               {chunks, books, corpus_version}

Auth: normal app users (the global auth middleware rejects anonymous
requests before these handlers run) — these are app features for the
house, NOT admin-only.

BOUNDARY: the Auto-Pilot trading engine never calls any of this — the
brain grounds chat and chart-analysis citations only
(tests/test_brain_contracts.py locks it).
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse

from auth import current_user_email

log = logging.getLogger("brain.api")

router = APIRouter(tags=["brain"])

NOT_INGESTED_ANSWER = ("The brain isn't ingested yet — run "
                       "python -m brain.ingest")


def _distill(question: str) -> str:
    """Top informative tokens of the question — searched ALONGSIDE the raw
    question so BM25 isn't drowned by conversational phrasing."""
    from brain import retriever
    seen, out = set(), []
    for t in retriever.tokenize(question):
        if len(t) > 2 and t not in seen:
            seen.add(t)
            out.append(t)
    return " ".join(out[:12])


def ask_impl(question: str, history: Optional[List[dict]] = None,
             app_context: Optional[str] = None,
             portfolio: Optional[str] = None) -> dict:
    """Retrieve -> build grounded prompt -> Claude with the persona system.
    Sync (runs in a thread from the route).

    ``portfolio`` is the user's live-positions snapshot (app state, NOT book
    material) so the coach knows what he actually holds when restating the
    book's rules for a position. The persona's grounding/citation contract is
    untouched: this is injected as app state and labelled never-cite-as-books.
    """
    from brain import retriever
    from brain.persona import SYSTEM_PROMPT

    queries = [question]
    distilled = _distill(question)
    if distilled and distilled != question.strip().lower():
        queries.append(distilled)
    # Balanced retrieval: BM25 top-k WITH a per-book floor, so both TLSW and
    # TTLAC are consulted whenever both carry relevant material — a strongly
    # one-book question never silently drops the other book from the passages
    # the persona reasons over (Ajay's "verify both books" requirement).
    rows = retriever.search_balanced(queries, k=10)

    if not rows and not retriever.status()["chunks"]:
        # Empty corpus: answer deterministically, never bill the LLM.
        return {"answer": NOT_INGESTED_ANSWER, "citations": [],
                "retrieved": 0, "not_ingested": True}

    parts: List[str] = []
    if rows:
        parts.append("PASSAGES from Mark Minervini's books — your ONLY "
                     "factual source; cite by the bracketed label:")
        for r in rows:
            parts.append("[%s] %s" % (r["cite"], r["text"]))
    else:
        parts.append("PASSAGES: none retrieved for this question.")

    if portfolio:
        parts.append("\nAJAY'S LIVE PORTFOLIO (his real positions — app state, "
                     "NOT book material, never cite it as the books). When he "
                     "asks about 'my position', restate the relevant book rules "
                     "WITH citations against these actual holdings:\n"
                     + str(portfolio)[:2500])

    if app_context:
        parts.append("\nAPP CONTEXT (the user's screen/app state — NOT book "
                     "material, never cite it as the books):\n"
                     + str(app_context)[:4000])

    hist = [h for h in (history or []) if isinstance(h, dict)][-6:]
    if hist:
        parts.append("\nRECENT CONVERSATION:")
        for h in hist:
            parts.append("%s: %s" % (h.get("role") or "user",
                                     str(h.get("text") or "")[:1000]))

    parts.append("\nQUESTION: " + question)
    prompt = "\n".join(parts)

    import llm
    try:
        r = llm.chat(prompt, system=SYSTEM_PROMPT, provider="anthropic",
                     max_tokens=1200, temperature=0.3, timeout=90)
    except Exception as exc:                  # llm.chat raising ≠ a 500 crash
        raise HTTPException(502, "brain LLM call failed: %s" % exc)
    if not r.get("ok"):
        raise HTTPException(502, "brain LLM call failed: %s"
                            % r.get("error", "unknown"))

    # FRONTEND CONTRACT (ChatWidget/ChartAnalysisPanel): citations is a list
    # of cite STRINGS — "TLSW p.{printed}" / "TTLAC §{ch} (ebook p.{pdf})" —
    # rendered verbatim as chips. Deduped, retrieval (best-score) order.
    citations: List[str] = []
    for x in rows:
        c = x.get("cite")
        if c and c not in citations:
            citations.append(c)
    return {
        "answer":      r.get("text"),
        "citations":   citations,
        "retrieved":   len(rows),
        "model":       r.get("model"),
        "latency_sec": r.get("latency_sec"),
    }


@router.get("/brain/search")
async def brain_search(q: str, k: int = 8, book: Optional[str] = None):
    """Raw retrieval rows — debug + citation UI."""
    from brain import retriever
    if book not in (None, "tlsw", "ttlac"):
        raise HTTPException(400, "book must be tlsw or ttlac")
    k = max(1, min(int(k), 25))
    rows = await asyncio.to_thread(retriever.search, q, k, book)
    return JSONResponse({"rows": rows, "n": len(rows)})


@router.post("/brain/ask")
async def brain_ask(payload: dict = Body(...),
                    email: str = Depends(current_user_email)):
    question = str(payload.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "question required")
    history = payload.get("history") or []
    if not isinstance(history, list):
        history = []
    app_context = payload.get("app_context")
    # His live positions (soft-fails to None) so the coach knows what he holds.
    from chat.portfolio_context import live_portfolio_block
    portfolio = await asyncio.to_thread(live_portfolio_block, email)
    out = await asyncio.to_thread(
        ask_impl, question[:2000], history,
        str(app_context) if app_context else None,
        portfolio)
    return JSONResponse(out)


@router.get("/brain/status")
async def brain_status():
    from brain import retriever
    return JSONResponse(await asyncio.to_thread(retriever.status))
