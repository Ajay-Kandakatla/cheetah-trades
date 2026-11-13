"""📅 Long Term — the weekly digest as a phone push: COMPOSED, and HELD (spec §3.9, [C9], HIS CALL #1).

Ajay 2026-11-12, verbatim: "… Weekly and if something gets dropped let me know when to like is Sales drop or Stage 2 to
Stage 3 or stage 4 changes."

Today the digest is computed, stored on the week's run doc and shown on the tab. `constants.DIGEST_PUSH_MODE` is "off",
so `send_digest` returns "push off" before it reads a pref, a claim or a sender — nothing rings, nothing is claimed.
The rest of the path is written for the day he says yes (WP-PUSH registers the kind + the hook), in this order:
mode → kind registered in `push.subs.default_prefs()` → `CHEETAH_IGNORE_HOLIDAY` override (a manual run never pushes)
→ closed day → `digest.rings` (only RING_KINDS events ring) → the sender hook exists → claim `digest:<week>` (the
insert is the dedupe) → ONE owner-scoped send (`hooks.notify_long_term_digest(owner=subs._owner_email(), payload)`).
NEVER `send_to_all`: this module does not import it and no branch reaches it.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional

from . import constants as C
from . import store as ST
from . import words as W

log = logging.getLogger("long_term_list.push")

R_OFF = "push off"
R_KIND = "kind not registered"
R_OVERRIDE = "calendar override active — a manual run never pushes"
R_QUIET = "nothing to ring"
R_NO_HOOK = "no sender hook"
R_CLAIMED = "already pushed this week"
R_NO_STORE = "claim store unreachable — not sent"


def compose(digest: dict, week_id: str) -> dict:
    """The push payload: the digest title, its first DIGEST_BODY_LINES lines (+ the served 'more on the tab' line)."""
    digest = digest or {}
    return {"title": str(digest.get("title") or ""),
            "body": "\n".join(_body(list(digest.get("lines") or []))),
            "url": C.DIGEST_URL, "kind": C.DIGEST_KIND, "tag": f"{C.DIGEST_KIND}:{week_id}",
            "ticker": None,
            "tickers": [str(i.get("symbol")) for i in (digest.get("items") or []) if isinstance(i, dict)][:C.DIGEST_BODY_LINES]}


def _body(lines: list) -> list:
    """The digest's own lines (notices.digest already caps them at DIGEST_BODY_LINES + words.more_text); a longer
    list handed in is capped here the same way, never cut silently."""
    if len(lines) <= C.DIGEST_BODY_LINES + 1:
        return lines
    return lines[:C.DIGEST_BODY_LINES] + [W.more_text(len(lines) - C.DIGEST_BODY_LINES)]


def _hook() -> Optional[Callable]:
    try:
        from push import hooks
        return getattr(hooks, "notify_long_term_digest", None)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list.push: hooks unavailable: %s", exc)
        return None


def _skip(reason: str) -> dict:
    log.info("long-term digest push skipped: %s", reason)
    return {"state": "skipped", "reason": reason, "sent": 0}


def send_digest(run_doc: dict, now: datetime, *, db=None, send: Optional[Callable] = None) -> dict:
    """{"state": "skipped" | "pushed" | "no_target" | "failed", "reason", "sent"}. Never raises."""
    try:
        if C.DIGEST_PUSH_MODE != "live":
            return _skip(R_OFF)
        from push import subs
        if C.DIGEST_KIND not in (subs.default_prefs() or {}):
            return _skip(R_KIND)
        from market_hours import gate
        if gate.override_active():
            return _skip(R_OVERRIDE)
        why = gate.closed_reason(now)
        if why:
            return _skip(why)
        digest = (run_doc or {}).get("digest") or {}
        if not digest.get("rings"):
            return _skip(R_QUIET)
        sender = send if send is not None else _hook()
        if sender is None:
            return _skip(R_NO_HOOK)
        week = str((run_doc or {}).get("iso_week") or (run_doc or {}).get("_id") or "")
        cs = ST.colls(db)
        claims = cs["claims"] if cs else None
        cid = ST.DIGEST_CLAIM + week
        got = ST.claim(claims, cid, now.isoformat())
        if got is None:
            return _skip(R_NO_STORE)
        if not got:
            return _skip(R_CLAIMED)
        payload = compose(digest, week)
        try:
            res = sender(owner=subs._owner_email(), payload=payload) or {}
        except Exception as exc:                               # noqa: BLE001
            log.warning("long_term_list.push: send failed: %s", exc)
            res = {"sent": 0, "failed": 0, "error": type(exc).__name__}
        sent = int(res.get("sent") or 0)
        if sent > 0:
            state = "pushed"
        elif "total_targets" in res and int(res.get("total_targets") or 0) == 0:
            state = "no_target"
        else:
            state = "failed"
        ST.set_claim(claims, cid, state, result={k: v for k, v in res.items() if k != "payload"})
        return {"state": state, "reason": None if state != "failed" else "send failed", "sent": sent}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list.push: send_digest raised: %s", exc)
        return {"state": "failed", "reason": f"{type(exc).__name__}", "sent": 0}
