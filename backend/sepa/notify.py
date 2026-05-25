"""Notifications router — Web Push only.

Twilio / WhatsApp was removed. All alerts now route through the Web Push
pipeline — phone PWA, laptop browser, etc. The service worker on each
device handles delivery and click-routing via the ``url`` field.

Public API
----------
send_alert(title, body, *, url='/', kind='generic', ticker=None)
    Structured payload with click routing.

send_whatsapp(body)
    Legacy alias kept for backward compat with older call sites that
    haven't been updated. Routes through send_alert.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("sepa.notify")


# ============================================================================
# Cross-user safety: kinds that are PER-USER by definition and must NEVER
# fall through to a system-wide broadcast.
#
# Why this exists:
#   On 2026-05-17 a bug in todos.reminder.fire_due() was discovered: it
#   called send_alert() without user_email, which routed through
#   sender.send_to_all() and pushed every user's private todo reminder
#   to every device on the system. Vineetha's nightly vitamin reminder
#   (and worse — the daily love note from Ajay) was hitting every other
#   subscribed user's phone.
#
#   Now fixed at the call site, but bugs like this are easy to
#   re-introduce — someone adds a new private notification kind, forgets
#   to pass user_email, and it broadcasts. This guard catches that
#   regression at the notify-layer:
#
#     - If kind is in PRIVATE_KINDS and user_email is missing, REFUSE
#       to send. Log loudly. Return False so the caller knows.
#
#   Private = "content meant for one specific user; embarrassing or
#   confusing if leaked to others." Trading alerts (breakouts, regime,
#   morning brief) are NOT private — they're the same data for everyone
#   and intentionally broadcast.
# ============================================================================
PRIVATE_KINDS: frozenset[str] = frozenset({
    "todo_reminder",        # personal todo pings (incl. love notes to spouse)
    "todo_daily_digest",    # personalized digest
    "price_alert",          # user-set price thresholds
    "position_alert",       # user's own portfolio stops/targets
})


def _send_push(title: str, body: str, *, url: str, kind: str,
               ticker: Optional[str],
               user_email: Optional[str] = None) -> int:
    """Fire a notification to subscribed devices whose prefs allow this
    ``kind``. Two delivery channels in parallel: Web Push (browser /
    iPhone PWA) and the mac_outbox → SSE drain for the native macOS app.

    user_email scopes the broadcast to a single user — used by
    per-user reminders (todos, household pings) so a notification meant
    for Vineetha doesn't also fire on Ajay's phone. When None, the
    notification goes to **every** matching subscription (the original
    behavior used by SEPA-wide alerts, breakouts, etc.).

    Safety guard (added 2026-05-17): if ``kind`` is in PRIVATE_KINDS
    and ``user_email`` is missing/empty, we REFUSE to send and return 0.
    The risk surface — accidentally pushing "💕 From Ajay…" to every
    friend's phone — is large enough that "fail loudly" beats "fall
    through to broadcast."

    Returns the (web_devices_reached + mac_users_enqueued) total. The
    diagnostic count is useful for tests/logs but callers usually
    don't act on it.
    """
    # Belt-and-suspenders cross-user safety. See PRIVATE_KINDS docstring
    # above for the rationale. We do this BEFORE building the payload
    # so a misconfigured caller can't even race the network.
    if kind in PRIVATE_KINDS and not (user_email and user_email.strip()):
        log.error(
            "notify: REFUSED to broadcast private kind=%s without user_email "
            "(title=%r). Caller bug — pass user_email or use a non-private kind.",
            kind, (title or "")[:80],
        )
        return 0
    payload = {
        "title": title,
        "body": (body or "")[:300],
        "tag": f"{kind}-{ticker}" if ticker else kind,
        "url": url,
        "kind": kind,
        "ticker": ticker,
    }
    delivered = 0
    # Web Push (browser + iPhone PWA).
    try:
        from push import sender
        if user_email:
            result = sender.send_to_user(
                user_email,
                payload,
                kind=kind if kind != "generic" else None,
            )
        else:
            result = sender.send_to_all(
                payload,
                kind=kind if kind != "generic" else None,
            )
        delivered += result.get("sent", 0)
    except Exception as exc:
        log.warning("push delivery (web) failed: %s", exc)
    # Native macOS app via the mac_outbox → SSE drain. Fully decoupled from
    # web push, so a flaky pywebpush call never blocks Mac delivery (and vice
    # versa). Same prefs schema, per-user fan-out.
    try:
        from push import mac_stream
        delivered += mac_stream.enqueue_for_outbox(
            payload,
            kind=kind if kind != "generic" else None,
            target_user_email=user_email,
        )
    except Exception as exc:
        log.warning("push delivery (mac) failed: %s", exc)
    return delivered


def send_alert(title: str, body: str, *,
               url: str = "/",
               kind: str = "generic",
               ticker: Optional[str] = None,
               user_email: Optional[str] = None) -> bool:
    """Send a notification via Web Push. Returns True if at least one
    device received it.

    Pass user_email to target a single user (e.g. todo reminders,
    household pings). Omit for system-wide alerts (breakouts, etc.).
    """
    pushed = _send_push(title=title, body=body, url=url,
                        kind=kind, ticker=ticker,
                        user_email=user_email)
    return pushed > 0


def send_whatsapp(body: str) -> bool:
    """Legacy alias — routes through send_alert. Kept so any old callers
    we missed continue working. The function name is now misleading but
    breaking it would require a wider sweep."""
    if not body:
        return False
    lines = body.split("\n", 1)
    title = lines[0][:80].lstrip("*").strip()
    rest = lines[1] if len(lines) > 1 else ""
    return send_alert(title=title, body=rest or title, kind="generic")


# ---------------------------------------------------------------------------
# Formatters — keep messages short and scannable on a phone.
# ---------------------------------------------------------------------------
def format_brief(brief: dict) -> str:
    lines: list[str] = []
    mkt = brief.get("market_context") or {}
    label = mkt.get("label") or "?"
    safe = "✅ longs OK" if mkt.get("safe_to_long") else "⚠️ defensive"
    lines.append(f"*Cheetah morning brief*  ({label} — {safe})")

    top = brief.get("top_candidates") or []
    if top:
        lines.append("")
        lines.append("*Top candidates:*")
        for c in top[:5]:
            es = c.get("entry_setup") or {}
            pivot = es.get("pivot")
            stop = es.get("stop")
            score = c.get("score")
            sym = c.get("symbol")
            extras = []
            if pivot: extras.append(f"buy ≥{pivot}")
            if stop: extras.append(f"stop {stop}")
            tail = " | ".join(extras) if extras else ""
            lines.append(f"• {sym}  score {score}  {tail}".rstrip())

    alerts = brief.get("watchlist_alerts") or []
    if alerts:
        lines.append("")
        lines.append("*Position alerts:*")
        for a in alerts:
            sym = a.get("symbol")
            action = a.get("action")
            last = a.get("last_price")
            pnl = a.get("pnl_pct")
            lines.append(f"• {sym}: {action} @ {last} ({pnl:+.1f}%)")

    cats = brief.get("catalyst_today") or []
    if cats:
        lines.append("")
        lines.append("*Catalysts today:*")
        for c in cats[:5]:
            sym = c.get("symbol")
            er = c.get("earnings_upcoming")
            tag = "earnings" if er else "news"
            lines.append(f"• {sym}: {tag}")

    return "\n".join(lines) or "Cheetah brief: nothing to report."


def format_position_alert(item: dict) -> str:
    sym = item.get("symbol")
    last = item.get("last_price")
    stop = item.get("stop")
    entry = item.get("entry")
    shares = item.get("shares") or 0
    action = item.get("action") or "REVIEW"
    pnl_pct = item.get("pnl_pct") or 0.0
    pnl_usd = ((last or 0) - (entry or 0)) * shares if entry and last else 0
    lines = [
        f"*{action}: {sym}* @ {last}",
        f"entry {entry}  stop {stop}  shares {shares}",
        f"P&L: {pnl_pct:+.1f}%  ({pnl_usd:+.0f} USD)",
    ]
    return "\n".join(lines)
