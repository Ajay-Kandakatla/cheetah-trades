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


def _send_push(title: str, body: str, *, url: str, kind: str,
               ticker: Optional[str]) -> int:
    """Fire a notification to every subscribed device whose prefs allow this
    ``kind`` — Web Push for browsers/iPhone, SSE-via-Mongo-outbox for the
    native macOS app. Returns the (web_devices_reached + mac_users_enqueued)
    count, mostly useful for tests/diagnostics."""
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
        )
    except Exception as exc:
        log.warning("push delivery (mac) failed: %s", exc)
    return delivered


def send_alert(title: str, body: str, *,
               url: str = "/",
               kind: str = "generic",
               ticker: Optional[str] = None) -> bool:
    """Send a notification via Web Push. Returns True if at least one
    device received it."""
    pushed = _send_push(title=title, body=body, url=url,
                        kind=kind, ticker=ticker)
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
