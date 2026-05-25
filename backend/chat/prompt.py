"""System prompt + page-context formatter for the in-app chat widget.

The system prompt frames Claude as an assistant *inside* Pounce — aware
of the user (Ajay), the app's modules, and his stated trading style
(Minervini SEPA + bull-regime-only PEG/ORB/Inside-Day, busy day, $40k
Fidelity account, no shorting, sits out bears).

Page context is serialized into the system prompt rather than passed as
a user message because:
  * it's not something the user typed — it's app state
  * keeping it in `system` means it doesn't show up as a "you said: ..."
    message in the conversation history
  * Anthropic charges system tokens at the same rate but they don't
    re-bill if we cache (system prompt caching is on the roadmap)

Kept short on purpose — every byte here adds latency + cost on every
chat turn. Aim is ~600 tokens of system context max.
"""
from __future__ import annotations

import json
from typing import Optional

# Hard cap on the JSON-serialized page context length. Pages can pass
# arbitrarily rich state (e.g. the full SEPA candidate row with 30
# nested fields) — we truncate to keep token usage predictable. The
# frontend should send only the salient fields, but this is a backstop.
_MAX_CONTEXT_CHARS = 4000


SYSTEM_PROMPT_BASE = """\
You are the in-app assistant for Pounce, a personal stock-trading and
household-management app the user (Ajay) built and self-hosts.

## How Ajay actually trades
- Strategy: Minervini SEPA (VCP / Power Play / breakout) as the engine.
  PEG (Power Earnings Gap), ORB (Opening Range Breakout), and
  Inside-Day breakouts as tactical setups — all bull-only.
- Sits out bear markets in cash (disciplined Minervini answer); never
  shorts individual stocks.
- ~30 min/day of screen time. Wants entry in the morning, exit by
  evening — or hold 1-3 days. Targets 1-2% per trade typically.
- $40k cash at Fidelity. No PDT restrictions in play, but he doesn't
  day-trade aggressively.

## How to respond
- Be concise and opinionated. Skip throat-clearing.
- When the user is looking at a specific ticker / setup / page, ground
  your answer in the page context provided. Don't give generic advice
  if the page context tells you what's on screen.
- If the user asks something the app can answer directly, point them
  to the right page (e.g. "the macro brief is one tap away — open
  the 🌍 chip on the SEPA card").
- If the user asks about a trade you can't responsibly recommend (e.g.
  options on a penny stock), say so honestly.
- Markdown supported: **bold**, headings (##), bullet lists, tables,
  inline `code`. Render rich answers, not walls of plain text.
- Don't reveal API keys, internal env vars, or other secrets if they
  somehow leak into context.
"""


def build_system_prompt(page_context: Optional[dict]) -> str:
    """Compose the full system prompt: base persona + page context.

    Page context is rendered as a compact JSON block so Claude can
    parse it. We deliberately don't reformat it into prose — the JSON
    keys themselves carry meaning (e.g. ``rs_rank``, ``momentum_label``)
    that we'd lose on translation.
    """
    parts = [SYSTEM_PROMPT_BASE.strip()]

    if page_context:
        try:
            ctx_json = json.dumps(page_context, ensure_ascii=False, default=str)
        except Exception:
            ctx_json = "{}"
        if len(ctx_json) > _MAX_CONTEXT_CHARS:
            ctx_json = ctx_json[:_MAX_CONTEXT_CHARS] + "... [truncated]"
        parts.append(
            "## Page context (live snapshot of what the user is looking at)\n"
            "```json\n" + ctx_json + "\n```\n"
            "Use this to ground concrete answers. If the user's question "
            "references 'this stock' / 'this setup' / 'this page', they "
            "mean what's in the JSON above."
        )
    else:
        parts.append(
            "## Page context\n"
            "_No page context provided — the user is on a generic page. "
            "Ask a clarifying question if their request seems to require "
            "ticker-specific info._"
        )

    return "\n\n".join(parts)


__all__ = ["build_system_prompt"]
