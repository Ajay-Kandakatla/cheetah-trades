"""Live portfolio snapshot injected into the in-app chat.

Ajay 2026-06-15: *"I am changing my positions to new stocks — I want it to
always remember my current portfolio# ... answer based on Minervini."* The chat
used to be stateless about positions: a blank-slate Sonnet every turn that had
no idea what he actually held. This pulls his CURRENT holdings (live P/L from
``portfolio.api.build_summary``, which is quote-cached ~60s) into a compact
text block the chat handlers fold into the system prompt on every turn.

Contract: **soft-fail to None.** Any error — no Mongo, no holdings, a quote
outage — returns ``None`` and the chat proceeds without the block. It must
never raise into a chat turn. (Locked by tests/test_chat_portfolio_context.py.)

Lean on purpose — one line per position — because it rides on EVERY chat turn's
system prompt, so every byte is tokens + latency.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("chat.portfolio_context")


def _fetch_summary(user_email: str) -> Optional[dict]:
    """Lazy indirection so the heavy portfolio/quote stack isn't imported at
    module load — and so tests can monkeypatch a fake summary cleanly."""
    from portfolio.api import build_summary  # lazy: pulls quotes/yfinance
    return build_summary(user_email)


def _money(n) -> str:
    try:
        return f"${float(n):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _pct(n) -> str:
    try:
        return f"{float(n):+.1f}%"
    except (TypeError, ValueError):
        return "—"


def live_portfolio_block(user_email: str) -> Optional[str]:
    """Compact text snapshot of the user's live portfolio, or None.

    None when: no email, no holdings, or anything fails. The block is plain
    text (not JSON) so the model reads it as fact, not a payload to echo.
    """
    if not user_email:
        return None
    try:
        s = _fetch_summary(user_email)
    except Exception as exc:  # never break a chat turn over portfolio data
        log.debug("portfolio_context: build_summary failed: %s", exc)
        return None

    if not s or not s.get("available") or not s.get("rows"):
        return None

    rows = s["rows"]
    count = s.get("count", len(rows))
    total_value = s.get("total_value")
    total_cost = s.get("total_cost")
    # When the quote provider is down, build_summary returns last=0 (or None)
    # for every row → total_value 0 and a bogus "-100%" P/L. Detect that and
    # suppress the misleading numbers rather than alarming him with a fake
    # wipeout. (Seen live: a quote outage yields last=0.0, not None.)
    has_live = isinstance(total_value, (int, float)) and total_value > 0

    lines = ["## Ajay's LIVE portfolio — his real Fidelity positions right now"]
    if has_live:
        lines.append(
            f"Cost basis {_money(total_cost)} · value {_money(total_value)} · "
            f"open P/L {_money(s.get('pl_dollars'))} ({_pct(s.get('pl_pct'))}) · "
            f"today {_money(s.get('day_dollars'))} · {count} positions"
        )
    else:
        lines.append(
            f"Cost basis {_money(total_cost)} · {count} positions · "
            f"live quotes unavailable this turn — current value / P/L not shown"
        )
    lines.append("Positions:")

    for r in rows:
        tkr = r.get("ticker") or "?"
        sh = r.get("shares")
        avg = r.get("avg_cost")
        last = r.get("last")
        wt = r.get("weight_pct")
        sh_s = f"{sh:g}" if isinstance(sh, (int, float)) else "—"
        avg_s = f"${avg:,.2f}" if isinstance(avg, (int, float)) else "—"
        line = f"- {tkr}: {sh_s} sh · {avg_s} avg"
        if isinstance(last, (int, float)) and last > 0:
            line += (
                f" · ${last:,.2f} · {_pct(r.get('pl_pct'))} open · "
                f"{_pct(r.get('day_change_pct'))} today"
            )
            if isinstance(wt, (int, float)):
                line += f" · {wt:.0f}% of book"
        else:
            line += " · (no live quote this turn)"
        lines.append(line)
    return "\n".join(lines)


__all__ = ["live_portfolio_block"]
