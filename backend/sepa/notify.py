"""WhatsApp notifications via Twilio.

Configure with these env vars (`backend/.env`):
  TWILIO_ACCOUNT_SID  — AC...
  TWILIO_AUTH_TOKEN   — auth token (rotate if leaked)
  TWILIO_FROM         — sender, e.g. whatsapp:+14155238886 (sandbox)
  TWILIO_TO           — destination, e.g. whatsapp:+13025636375

If any are missing, send_whatsapp() logs and returns False — the rest of the
app keeps working. The `twilio` package is imported lazily so the module is
safe to import even when twilio isn't installed.

Sandbox setup: send "join <your-code>" from your WhatsApp to the Twilio
sandbox number once (Twilio console shows your code). After that, outbound
messages from this code arrive in your WhatsApp.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger("sepa.notify")


def _config() -> Optional[dict]:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    tok = os.getenv("TWILIO_AUTH_TOKEN")
    src = os.getenv("TWILIO_FROM")
    dst = os.getenv("TWILIO_TO")
    if not (sid and tok and src and dst):
        return None
    return {"sid": sid, "token": tok, "from": src, "to": dst}


def send_whatsapp(body: str) -> bool:
    """Send `body` via Twilio WhatsApp. Returns True on success."""
    cfg = _config()
    if cfg is None:
        log.info("twilio not configured — skipping WhatsApp send")
        return False
    try:
        from twilio.rest import Client
        client = Client(cfg["sid"], cfg["token"])
        # WhatsApp body limit is 1600 chars; trim to be safe.
        msg = client.messages.create(
            from_=cfg["from"],
            to=cfg["to"],
            body=body[:1500],
        )
        log.info("whatsapp sent sid=%s", msg.sid)
        return True
    except Exception as exc:
        log.warning("whatsapp send failed: %s", exc)
        return False


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
