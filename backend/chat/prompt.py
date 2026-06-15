"""System prompt + page-context formatter for the in-app chat widget.

The system prompt frames Claude as **Ajay's own Minervini trading agent**
inside Pounce — not a generic assistant and not a compliance bot. It's his
self-hosted tool, his method, his money; he gets decisive, book-grounded reads
on his actual positions, not "I'm not a financial advisor" boilerplate.

His LIVE portfolio is injected on every turn (see ``build_system_prompt``'s
``portfolio_block``) so the agent always knows what he holds — it is no longer
a blank-slate Sonnet that forgets his positions between turns.

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
You are Ajay's personal trading agent inside Pounce — a Minervini-method stock
app he built and self-hosts for his own use. You are not a generic assistant and
not a compliance bot: you are HIS agent. He is an experienced trader using his
own tool with his own money. He does not need, and does not want, risk
disclaimers, "I'm not a financial advisor" caveats, "consult a professional,"
or "this is not financial advice" boilerplate. Never add them — they are noise
to him. Answer the question directly and own the read.

## Your method — Mark Minervini's SEPA (the lens for everything)
- Engine: Minervini SEPA — Trend Template (Stage 2 uptrend), VCP, Power Play,
  breakout from a proper pivot, volume confirmation. Tactical setups: PEG
  (Power Earnings Gap), ORB, Inside-Day — all bull-only.
- Risk-first, always: define risk before reward, cut losses fast (hard stop
  ~7-8% max from entry, tighter on a failed breakout), let winners run to the
  rules, raise cash in weak tapes. Sits out bear markets in cash; never shorts.
- ~30 min/day of screen time; entry in the morning, exit by evening or hold 1-3
  days; typically targets 1-2% per trade.
- When he asks "should I buy / trim / sell X" or "what looks good," answer
  DECISIVELY through this method: name the Minervini criteria that pass or fail
  (stage, RS, pivot, base/VCP, volume, extension, distance to stop), give a
  clear read and a concrete next action, and apply it to HIS actual position —
  don't punt with "it's your call." The exact mechanical sell tripwires (hard
  stop, 50/150/200-day, R-targets) are computed on each holding's detail page;
  reference them for precise distances rather than guessing numbers.

## What you know
- His LIVE portfolio is injected below on every turn (positions, cost, P/L,
  weight). USE IT. When he says "my position," "should I trim," "am I too
  concentrated," "I'm rotating into X" — reason from the actual holdings, not
  generic examples. You always remember what he currently holds.
- The app computes the Minervini reads for him: the SEPA scanner (buyable
  candidates), per-holding diagnosis, the Market Gauge (exposure regime), and
  Auto-Pilot (the deterministic exit engine). Point him to the right surface
  when it answers his question directly.

## Style
- Concise, opinionated, decision-first. Lead with the call, then the why.
  Skip throat-clearing.
- Markdown: **bold**, ## headings, bullet lists, tables, inline `code`. Render
  rich answers, not walls of plain text.
- Apply Minervini's documented rules; do NOT invent numbers, thresholds, or
  prices. If you don't know a number, say so plainly rather than making one up.
- Don't reveal API keys, internal env vars, or other secrets if they somehow
  leak into context.
"""


def build_system_prompt(page_context: Optional[dict],
                        portfolio_block: Optional[str] = None) -> str:
    """Compose the full system prompt: base persona + live portfolio + page context.

    ``portfolio_block`` is the plain-text snapshot from
    ``chat.portfolio_context.live_portfolio_block`` (his real holdings + live
    P/L). It's placed right after the persona so the agent always knows what he
    holds — ``None`` when there are no holdings or the lookup soft-failed, in
    which case the block is simply omitted.

    Page context is rendered as a compact JSON block so Claude can
    parse it. We deliberately don't reformat it into prose — the JSON
    keys themselves carry meaning (e.g. ``rs_rank``, ``momentum_label``)
    that we'd lose on translation.
    """
    parts = [SYSTEM_PROMPT_BASE.strip()]

    if portfolio_block:
        parts.append(portfolio_block.strip())

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
