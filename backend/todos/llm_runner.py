"""LLM runner — picks up todos flagged ``ai_task=True`` and writes a
structured research note back to the same row.

Lifecycle on each todo
----------------------
    pending  -- created by user with "AI task" toggle on
       │
       ▼
    running  -- this runner pulled it off the queue and is calling the LLM
       │
       ▼
    done     -- ai_result populated with markdown; UI shows expand link
       │
       ▼  (or)
    failed   -- ai_result holds the failure reason; user can retry

Designed to run from cron every ~15 min during waking hours. Idempotent
— only picks up rows in ``status: pending`` so a re-run doesn't replay
already-done work.

Backend: the existing ``llm.chat`` helper, which talks to LM Studio
(local Gemma by default). Swap LLM_BASE_URL/LLM_MODEL env vars to point
at Claude API or any other OpenAI-compatible endpoint without touching
this file.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

import llm
from todos import store

log = logging.getLogger("todos.llm_runner")


SYSTEM_PROMPT = (
    "You are a research assistant inside a personal productivity app. "
    "The user has flagged a todo as a research task — they want you to "
    "produce a focused, scannable research note that helps them act.\n\n"
    "Output strict markdown with these sections, in this order:\n"
    "  ## TL;DR\n"
    "    Two or three sentences capturing the practical answer.\n"
    "  ## Key findings\n"
    "    3–6 bullet points. Each bullet leads with a concrete claim, "
    "    then a short evidence sentence.\n"
    "  ## Practical steps\n"
    "    3–5 bullets the user could take this week. Specific, not generic.\n"
    "  ## Suggested searches\n"
    "    3–5 short web-search queries the user can paste into Google/Perplexity "
    "    if they want to dig further. Each query on its own line.\n\n"
    "Constraints:\n"
    "  - No preamble. Start with '## TL;DR' on the first line.\n"
    "  - Don't invent specific company names, numbers, or links you're not confident about; "
    "    prefer 'companies like X and Y' phrasing when uncertain.\n"
    "  - Keep total length under ~500 words. Brevity > completeness."
)


def _extract_tldr(markdown: str) -> str:
    """Pull the body of the '## TL;DR' section as a short plain string.

    Strategy: find the TL;DR heading, take everything until the next
    '## ' heading, strip / collapse whitespace, cap at ~240 chars so
    it fits in a push notification body + an inline row preview. If
    no TL;DR heading is found, fall back to the first paragraph.
    """
    if not markdown:
        return ""
    import re
    m = re.search(
        r"##\s*tl;?\s*dr\s*\n(.*?)(?:\n##\s|$)",
        markdown,
        re.IGNORECASE | re.DOTALL,
    )
    body = m.group(1) if m else markdown.split("\n\n", 1)[0]
    # Collapse internal whitespace + drop list dashes that crept in.
    body = re.sub(r"\s+", " ", body).strip()
    if len(body) > 240:
        # Cut at the last sentence boundary within the limit so we
        # don't strand a half-sentence in the push body.
        clip = body[:240]
        last_dot = clip.rfind(". ")
        if last_dot > 100:
            body = clip[:last_dot + 1]
        else:
            body = clip.rstrip() + "…"
    return body


def _notify_completion(todo: dict, summary: str) -> None:
    """Push 'AI is done' to the todo's owner. Per-user scoping is
    mandatory here — see PRIVATE_KINDS in sepa.notify for the guard
    that catches us if we ever forget."""
    owner = (todo.get("user_email") or "").strip().lower()
    if not owner:
        return
    text = (todo.get("text") or "")[:80]
    try:
        from sepa import notify
        notify.send_alert(
            title=f"🤖 AI finished: {text}",
            body=summary or "Open /todos to view the research.",
            url="/todos",
            kind="todo_reminder",       # honors the user's existing toggle
            user_email=owner,
        )
    except Exception as exc:
        log.warning("llm_runner: completion push failed: %s", exc)


def _process_one(todo: dict) -> dict:
    """Run a single todo through the LLM, persist the result, mark the
    todo completed, and push a notification to the owner. Returns
    ``{ok, status, ...}``. Caller logs the dict."""
    todo_id = todo["_id"]
    prompt = todo.get("text") or ""
    if not prompt.strip():
        store.set_ai_status(todo_id, status="failed", result="(empty prompt)")
        return {"ok": False, "id": todo_id, "reason": "empty"}

    # Optimistic claim — flips status so a re-run mid-processing won't
    # pick this same row again.
    store.set_ai_status(todo_id, status="running")

    # Prefer Anthropic Claude for research-style prompts — it's a
    # markedly better researcher than local Gemma, and these tasks are
    # low-volume (a user clicks "🤖 research" on a specific todo, not
    # firing constantly like catalysts/gemma_review). Falls back to
    # local automatically if ANTHROPIC_LLM_API_KEY isn't set, so a
    # fresh deploy without the Claude key still works on local Gemma.
    resp = llm.chat(
        prompt=f"Research task: {prompt.strip()}",
        system=SYSTEM_PROMPT,
        # Claude can produce longer, better-organized output — let it.
        # Local fallback respects this cap too; Gemma will just stop
        # earlier if its context can't sustain 2k tokens.
        max_tokens=2000,
        temperature=0.4,
        timeout=180,
        provider="anthropic",
    )
    if not resp.get("ok"):
        msg = f"LLM error: {resp.get('error') or 'unknown'}"
        # Failures don't complete the todo — the user can re-run and
        # the row stays in active so they can see something went wrong.
        store.set_ai_status(todo_id, status="failed", result=msg)
        log.warning("llm_runner: %s failed — %s", todo_id, msg)
        return {"ok": False, "id": todo_id, "reason": msg}

    text = (resp.get("text") or "").strip()
    if not text:
        store.set_ai_status(todo_id, status="failed", result="LLM returned empty output")
        return {"ok": False, "id": todo_id, "reason": "empty output"}

    # Trim any preamble before the first heading. Some models still
    # add "Sure, here's the research:" despite the instruction.
    head = text.find("## ")
    if head > 0:
        text = text[head:]

    summary = _extract_tldr(text)

    # Success path: persist result + brief, mark the todo COMPLETED
    # (so it slides into the Done section), and ping the owner so
    # they know the research is ready without having to refresh.
    store.set_ai_status(
        todo_id,
        status="done",
        result=text,
        summary=summary,
        mark_completed=True,
    )
    # Re-read so the notifier has the user_email — _process_one's
    # caller may have given us a stale dict from earlier in the
    # batch loop.
    fresh = store.get_todo(todo_id) or todo
    _notify_completion(fresh, summary)

    log.info("llm_runner: %s done (%d chars, %.1fs, summary=%d chars)",
             todo_id, len(text), float(resp.get("latency_sec") or 0), len(summary))
    return {"ok": True, "id": todo_id, "chars": len(text), "summary": summary}


def run_once(*, limit: int = 5) -> dict:
    """Process up to ``limit`` pending AI tasks. Returns summary."""
    if not llm.is_enabled():
        log.info("llm_runner: LLM not configured, skipping")
        return {"ran": False, "reason": "llm_disabled"}

    pending = store.list_pending_ai_tasks(limit=limit)
    if not pending:
        return {"ran": True, "processed": 0, "pending": 0}

    results = []
    for t in pending:
        results.append(_process_one(t))
    return {
        "ran": True,
        "processed": len(results),
        "ok":        sum(1 for r in results if r.get("ok")),
        "failed":    sum(1 for r in results if not r.get("ok")),
        "details":   results,
    }


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    summary = run_once()
    print(f"todos.llm_runner: {summary}")
    return 0 if summary.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
