"""Live portfolio alerts — fires Web Push when a position needs action.

What this is
------------
The user's broker positions live in ``portfolio.store`` (populated by
CSV import from Fidelity, or manual entry). This module runs across
those positions and decides which ones deserve a push.

Verdict source
--------------
We do NOT invent new sell logic — the canonical decision is already
made by ``sepa.position_lens.evaluate``, which combines:

  - sell_signals (Minervini Ch. 12-13: stop breach, close <200MA, climax run,
    biggest 1d/1w drop since Stage 2 start, down 10% from entry, …)
  - stage classifier (Stage 4 = full exit)
  - trade_plan stop levels
  - cross-module: whales 13F distribution, Chaikin CMF, options SOIR

…and returns one of: FULL_EXIT / REDUCE / TIGHTEN_STOP / HOLD.

This module is just the **delivery pipeline** — same verdict the SEPA
cards already display, just pushed to the phone with dedup so the user
doesn't have to remember to check the dashboard.

Cadence (mapped to crontab entries)
-----------------------------------
- Every 15 min during regular session (9:30–16:00 ET, Mon–Fri):
  ``check_intraday(user_email)`` → push FULL_EXIT + REDUCE verdicts.
  Re-fires every 15 min until ack'd. Max 12 fires/ticker/day.
- 3:00 PM ET weekdays: ``eod_brief(user_email)`` → push verdict for
  every position (including HOLD) so the user sees the full picture.
- 3:30 PM ET weekdays: ``eod_escalate(user_email)`` → re-push any
  SELL verdict (FULL_EXIT/REDUCE) not ack'd from the 3:00 PM round.

Acknowledge UX
--------------
Push payload sets ``data.url = /portfolio?ack=<symbol>``. When the user
taps the notification, the frontend POSTs to /portfolio/alerts/ack on
mount, which calls ``acknowledge(user_email, symbol)`` to mark the day.
Acknowledged alerts won't re-fire for that ticker on that date.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("portfolio.alerts")

# Dedup window: don't re-fire the same {user, ticker, kind} push more
# often than this. 15 min matches the cron tick during market hours —
# every cron run gets one shot per ticker; if user doesn't ack, next
# tick fires again. Lifted on ack.
_REFIRE_SECONDS = 14 * 60   # 14 min so cron-window jitter never skips a fire

# Fires per {ticker, day} cap. User 2026-06-02: "keep pushing until I
# acknowledge the sell signal." So this is raised to cover the FULL market
# session at the 14-min refire cadence (≈28 ticks 9:30-16:00 ET) — i.e. it
# keeps pinging all session until you ack, then stops; resets next day. It is
# NOT removed entirely: it stays as a runaway backstop in case the ack flow
# ever breaks (you'd still stop at end of session rather than ping forever).
_MAX_FIRES_PER_DAY = 40

# Which verdicts trigger an intraday push. HOLD and TIGHTEN_STOP are
# informational — the user doesn't need to be hounded for those. They
# do show up in the 3:00 PM EOD brief though.
_INTRADAY_PUSH_VERDICTS = {"FULL_EXIT", "REDUCE"}

_VERDICT_EMOJI = {
    "FULL_EXIT":     "🔴",
    "REDUCE":        "🟠",
    "TIGHTEN_STOP":  "🟡",
    "HOLD":          "🟢",
}


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _today_key_et() -> str:
    """Date key in ET so a 9:30 PM ET tick (= early next-day UTC) still
    rolls up under the trading day it belongs to."""
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def _get_db():
    """Lazy-load the Mongo handle. Same pattern as portfolio.store."""
    from portfolio import store as _store
    return _store._get_db()


# --------------------------------------------------------------------------
# Dedup state
# --------------------------------------------------------------------------
def _state_doc(user_email: str, symbol: str, date_key: str) -> Optional[dict]:
    db = _get_db()
    if db is None:
        return None
    return db.portfolio_alert_state.find_one({
        "user_email": user_email.lower(),
        "symbol":     symbol.upper(),
        "date_key":   date_key,
    })


def should_fire(user_email: str, symbol: str, *, kind: str = "intraday") -> tuple[bool, str]:
    """Return (allow_fire, reason). Reason is the dedup decision —
    useful for logs even when we DO fire."""
    state = _state_doc(user_email, symbol, _today_key_et())
    if state is None:
        return True, "first-fire-today"
    if state.get("acknowledged_at"):
        return False, "acknowledged"
    if (state.get("fired_count") or 0) >= _MAX_FIRES_PER_DAY:
        return False, f"daily-cap ({_MAX_FIRES_PER_DAY})"
    last = state.get("last_fired_at") or 0
    if _now() - last < _REFIRE_SECONDS:
        return False, f"refire-window ({_REFIRE_SECONDS}s)"
    return True, "refire-allowed"


def _record_fire(user_email: str, symbol: str, verdict: str) -> None:
    db = _get_db()
    if db is None:
        return
    db.portfolio_alert_state.update_one(
        {
            "user_email": user_email.lower(),
            "symbol":     symbol.upper(),
            "date_key":   _today_key_et(),
        },
        {
            "$set":         {"verdict": verdict, "last_fired_at": _now()},
            "$inc":         {"fired_count": 1},
            "$setOnInsert": {"first_fired_at": _now()},
        },
        upsert=True,
    )


def acknowledge(user_email: str, symbol: str) -> dict:
    """Mark today's alerts for this {user, ticker} as acknowledged.
    Stops intraday re-fires for the rest of the day. EOD brief still
    fires (it's informational, runs once)."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    res = db.portfolio_alert_state.update_one(
        {
            "user_email": user_email.lower(),
            "symbol":     symbol.upper(),
            "date_key":   _today_key_et(),
        },
        {"$set": {"acknowledged_at": _now()}},
        upsert=True,
    )
    return {
        "ok":       True,
        "symbol":   symbol.upper(),
        "matched":  res.matched_count,
        "modified": res.modified_count,
    }


def get_today_state(user_email: str) -> list[dict]:
    """Return today's alert state for every ticker the user has fired on.
    Used by the /portfolio page to show "last alert at X · ack'd" inline."""
    db = _get_db()
    if db is None:
        return []
    rows = list(db.portfolio_alert_state.find(
        {"user_email": user_email.lower(), "date_key": _today_key_et()},
        {"_id": 0},
    ))
    rows.sort(key=lambda r: r.get("last_fired_at") or 0, reverse=True)
    return rows


# --------------------------------------------------------------------------
# Verdict → push payload
# --------------------------------------------------------------------------
def _build_push_payload(verdict_doc: dict, *, source: str) -> dict:
    """Shape a position_lens verdict into a Web Push payload.

    Click_action goes to /portfolio?ack=<symbol> so tapping the
    notification both opens the page AND marks the alert ack'd via the
    frontend's mount-time POST to /portfolio/alerts/ack.
    """
    sym = verdict_doc.get("symbol", "?")
    verdict = verdict_doc.get("verdict", "HOLD")
    summary = verdict_doc.get("summary") or ""
    pnl = verdict_doc.get("pnl") or {}
    stop = verdict_doc.get("stop") or {}
    emoji = _VERDICT_EMOJI.get(verdict, "📊")

    # Headline: tight enough for an iOS lock-screen preview.
    gain_pct = pnl.get("gain_pct")
    pct_str = f" ({gain_pct:+.1f}%)" if isinstance(gain_pct, (int, float)) else ""
    title = f"{emoji} {sym} — {verdict}{pct_str}"

    # Body: the trigger that fired + suggested stop (so the user knows
    # what number to put in their broker).
    body_parts: list[str] = []
    if summary:
        # Strip the leading "VERDICT — " prefix that position_lens adds, since
        # the verdict is already in the title.
        body = summary.split(" — ", 1)[-1] if " — " in summary else summary
        body_parts.append(body)
    if stop.get("used"):
        body_parts.append(f"Stop ${stop['used']:.2f}")
    if verdict_doc.get("r_multiple") is not None:
        body_parts.append(f"{verdict_doc['r_multiple']:+.1f}R")
    body = " · ".join(body_parts) if body_parts else f"Open /portfolio for details."

    return {
        "title":  title,
        "body":   body[:240],  # Web Push title+body cap is ~3-4KB; this is generous
        "icon":   "/icon.svg",
        "tag":    f"portfolio-alert-{sym.lower()}",   # iOS coalesces same-tag pushes
        "data": {
            "url":     f"/portfolio?ack={sym}",
            "symbol":  sym,
            "verdict": verdict,
            "source":  source,   # "intraday" | "eod_brief" | "eod_escalate"
            "sent_at": _now(),
        },
    }


def _send_push(user_email: str, payload: dict, *, kind: str) -> dict:
    """Wrap push.sender.send_to_user so callers don't need to know the
    history-recording / kind-tagging conventions."""
    from push import sender as _push
    return _push.send_to_user(user_email, payload, kind=kind)


# --------------------------------------------------------------------------
# Position evaluation — calls sepa.position_lens for each holding
# --------------------------------------------------------------------------
def _evaluate_holding(holding: dict, meta: dict) -> Optional[dict]:
    """Evaluate one position. Returns the position_lens verdict dict or
    None if we can't evaluate (no entry, no SEPA data, …)."""
    sym = (holding.get("ticker") or "").upper().strip()
    if not sym:
        return None

    shares = float(holding.get("shares") or 0)
    cost = float(holding.get("cost_basis") or 0)
    # Entry resolution: user-typed entry > avg cost from CSV. Avg cost
    # is the fair fallback because the user paid that on average.
    entry = meta.get("entry") if meta.get("entry") else (cost / shares if shares > 0 and cost > 0 else None)
    if entry is None or entry <= 0:
        # Can't evaluate without an entry. Skip silently — UI will nudge
        # the user to set entry on each position.
        return None

    user_stop = meta.get("stop")

    try:
        from sepa import position_lens
        return position_lens.evaluate(
            symbol=sym,
            entry=float(entry),
            shares=shares or None,
            user_stop=float(user_stop) if user_stop else None,
        )
    except Exception as exc:
        log.warning("portfolio.alerts: position_lens failed for %s: %s", sym, exc)
        return None


def _load_positions(user_email: str) -> list[tuple[dict, dict]]:
    """Return [(holding, meta), ...] for every CSV/manual position the
    user has. Meta is the position-meta doc (entry/stop/target/notes).
    """
    from portfolio import store as _store, plaid_store
    holdings = _store.list_holdings(user_email)
    metas = plaid_store.get_position_meta(user_email)
    meta_by_sym = {(m.get("symbol") or "").upper(): m for m in metas}
    return [(h, meta_by_sym.get((h.get("ticker") or "").upper(), {})) for h in holdings]


# --------------------------------------------------------------------------
# Public entry points — called by cron + the /portfolio/alerts/run route
# --------------------------------------------------------------------------
def _intraday_triggers(holding: dict, meta: dict, live_price: Optional[float]) -> list[dict]:
    """Live-price stop checks. Returns a list of trigger dicts (kind,
    threshold, msg). Doesn't depend on the SEPA scanner — runs against
    real-time price, so a stop breach at 11:47 AM fires at the 11:45 cron
    tick instead of waiting for EOD.

    Three checks, fired in order of severity:
      1. ``user_stop_breach``  — live_price ≤ user-set stop
      2. ``minervini_7pct``    — live_price ≤ entry × 0.93 (Minervini hard cut)
      3. ``drawdown_12pct``    — live_price ≤ avg_cost × 0.88 (catch-all)
    """
    if live_price is None or live_price <= 0:
        return []

    shares = float(holding.get("shares") or 0)
    cost = float(holding.get("cost_basis") or 0)
    avg_cost = (cost / shares) if (shares > 0 and cost > 0) else None
    entry = meta.get("entry") if meta.get("entry") else avg_cost

    triggers: list[dict] = []

    # 1. Manual user stop (highest priority — they set it explicitly).
    user_stop = meta.get("stop")
    if user_stop and user_stop > 0 and live_price <= float(user_stop):
        triggers.append({
            "kind":      "user_stop_breach",
            "threshold": float(user_stop),
            "msg":       f"Live ${live_price:.2f} ≤ your stop ${float(user_stop):.2f} — exit.",
        })

    # 2. Minervini 7% hard cut from entry.
    if entry and entry > 0 and live_price <= entry * 0.93:
        triggers.append({
            "kind":      "minervini_7pct",
            "threshold": round(entry * 0.93, 2),
            "msg":       f"Live ${live_price:.2f} down ≥7% from entry ${entry:.2f} — Minervini hard cut.",
        })

    # 3. 12% drawdown from average cost (catch-all if no stop set).
    if avg_cost and avg_cost > 0 and live_price <= avg_cost * 0.88:
        triggers.append({
            "kind":      "drawdown_12pct",
            "threshold": round(avg_cost * 0.88, 2),
            "msg":       f"Live ${live_price:.2f} down ≥12% from avg cost ${avg_cost:.2f} — reassess.",
        })

    return triggers


def _live_prices_for(symbols: list[str]) -> dict[str, float]:
    """Bulk-fetch live prices via Massive. Falls back to per-symbol when
    bulk fails. Returns {SYM: last_price}."""
    out: dict[str, float] = {}
    if not symbols:
        return out
    try:
        from sepa import prices as _prices
        bulk = _prices.bulk_live_prices(symbols) or {}
        for sym, row in bulk.items():
            last = row.get("last_trade_price") or row.get("price")
            if last is not None:
                out[sym.upper()] = float(last)
    except Exception as exc:
        log.warning("portfolio.alerts: bulk_live_prices failed: %s — falling back", exc)
        from sepa import prices as _prices
        for sym in symbols:
            p = _prices.last_trade_price(sym)
            if p is not None:
                out[sym.upper()] = float(p)
    return out


def check_intraday(user_email: str) -> dict:
    """Every-15-min scan. Pushes when live price breaches a stop level.

    Uses **live prices from Massive** (not EOD scanner data) so a stop
    breached at 11:47 AM fires on the 11:45 cron tick. Three trigger
    kinds, see ``_intraday_triggers``:

      - user_stop_breach: live ≤ user-set stop
      - minervini_7pct:   live ≤ entry × 0.93
      - drawdown_12pct:   live ≤ avg_cost × 0.88

    Re-fires every 15 min until ack'd, max 12/ticker/day.
    """
    if not user_email:
        return {"ok": False, "reason": "no user_email"}

    positions = _load_positions(user_email)
    symbols = [h.get("ticker", "").upper() for h, _ in positions if h.get("ticker")]
    live_by_sym = _live_prices_for(symbols)

    scanned = 0
    pushed = 0
    skipped: list[dict] = []

    for holding, meta in positions:
        scanned += 1
        sym = (holding.get("ticker") or "").upper()
        live = live_by_sym.get(sym)
        if live is None:
            skipped.append({"sym": sym, "reason": "no-live-price"})
            continue

        triggers = _intraday_triggers(holding, meta, live)
        if not triggers:
            continue   # No stop breached, no alert needed

        allow, reason = should_fire(user_email, sym)
        if not allow:
            skipped.append({"sym": sym, "reason": reason})
            continue

        # Pick the most severe trigger (first in the list — user_stop first,
        # then Minervini 7%, then drawdown 12%).
        primary = triggers[0]
        gain_pct = None
        cost = float(holding.get("cost_basis") or 0)
        shares = float(holding.get("shares") or 0)
        if cost and shares:
            avg_cost = cost / shares
            gain_pct = (live / avg_cost - 1) * 100

        # Synthesize a minimal verdict-doc shape that _build_push_payload
        # understands, then upgrade with extra fields for the title/body.
        verdict_doc = {
            "ok":      True,
            "symbol":  sym,
            "verdict": "FULL_EXIT",
            "summary": f"FULL_EXIT — {primary['msg']}",
            "pnl":     {"gain_pct": round(gain_pct, 2) if gain_pct is not None else None},
            "stop":    {"used": primary.get("threshold")},
            "r_multiple": None,
        }
        payload = _build_push_payload(verdict_doc, source="intraday")
        # Make the body more actionable by stacking all triggers.
        if len(triggers) > 1:
            payload["body"] = " · ".join(t["msg"] for t in triggers)[:240]
        send_result = _send_push(user_email, payload, kind="position_alert")
        if (send_result or {}).get("sent", 0) > 0:
            _record_fire(user_email, sym, "FULL_EXIT")
            pushed += 1
        else:
            skipped.append({"sym": sym, "reason": "push-not-delivered"})

    log.info(
        "portfolio.alerts: intraday user=%s scanned=%d pushed=%d skipped=%d (live_prices=%d)",
        user_email, scanned, pushed, len(skipped), len(live_by_sym),
    )
    return {"ok": True, "scanned": scanned, "pushed": pushed, "skipped": skipped}


def eod_brief(user_email: str) -> dict:
    """3:00 PM ET ping — push verdict for EVERY position (including HOLD)
    so the user sees the full set 30 min before close. This is the
    "what do I do before EOD" round.

    Unlike intraday, this fires once per position regardless of
    acknowledgement (it's a daily brief, not a re-ringing alarm)."""
    if not user_email:
        return {"ok": False, "reason": "no user_email"}

    scanned = 0
    pushed = 0
    by_verdict: dict[str, int] = {}

    for holding, meta in _load_positions(user_email):
        scanned += 1
        sym = (holding.get("ticker") or "").upper()
        verdict_doc = _evaluate_holding(holding, meta)
        if not verdict_doc or not verdict_doc.get("ok"):
            continue
        verdict = verdict_doc.get("verdict", "HOLD")
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1

        payload = _build_push_payload(verdict_doc, source="eod_brief")
        # Tweak title to mark this as the EOD round so the user can
        # distinguish it from the intraday pings in the notification
        # history view.
        payload["title"] = "EOD · " + payload["title"]
        result = _send_push(user_email, payload, kind="position_alert")
        if (result or {}).get("sent", 0) > 0:
            _record_fire(user_email, sym, verdict)
            pushed += 1

    log.info(
        "portfolio.alerts: eod_brief user=%s scanned=%d pushed=%d by_verdict=%s",
        user_email, scanned, pushed, by_verdict,
    )
    return {"ok": True, "scanned": scanned, "pushed": pushed, "by_verdict": by_verdict}


def eod_escalate(user_email: str) -> dict:
    """3:30 PM ET escalation — re-push any FULL_EXIT/REDUCE verdict that
    wasn't acknowledged from the 3:00 PM round. This is the "you still
    haven't dealt with this, market closes in 30 min" nudge."""
    if not user_email:
        return {"ok": False, "reason": "no user_email"}

    scanned = 0
    pushed = 0

    for holding, meta in _load_positions(user_email):
        scanned += 1
        sym = (holding.get("ticker") or "").upper()
        verdict_doc = _evaluate_holding(holding, meta)
        if not verdict_doc or not verdict_doc.get("ok"):
            continue
        verdict = verdict_doc.get("verdict", "HOLD")
        if verdict not in _INTRADAY_PUSH_VERDICTS:
            continue   # Don't escalate HOLD/TIGHTEN

        state = _state_doc(user_email, sym, _today_key_et()) or {}
        if state.get("acknowledged_at"):
            continue   # User ack'd from the 3:00 PM round — leave alone

        payload = _build_push_payload(verdict_doc, source="eod_escalate")
        payload["title"] = "⏰ CLOSE-30 · " + payload["title"]
        payload["body"] = "Still unacknowledged — market closes in 30 min. " + payload["body"]
        result = _send_push(user_email, payload, kind="position_alert")
        if (result or {}).get("sent", 0) > 0:
            _record_fire(user_email, sym, verdict)
            pushed += 1

    log.info(
        "portfolio.alerts: eod_escalate user=%s scanned=%d pushed=%d",
        user_email, scanned, pushed,
    )
    return {"ok": True, "scanned": scanned, "pushed": pushed}


# --------------------------------------------------------------------------
# Multi-user dispatcher — used by cron when the env doesn't specify a
# particular user. Iterates over everyone with the `portfolio` feature.
# --------------------------------------------------------------------------
def _resolve_owner() -> str:
    """Resolve which user to scan for. Same fallback as the CSV import
    cron — env-driven, then hard fallback to the deployment owner."""
    return (
        os.getenv("PORTFOLIO_ALERT_OWNER")
        or os.getenv("HOUSE_OWNER_EMAIL")
        or "ajaykandakatla@gmail.com"
    ).lower()


def run_intraday_default() -> dict:
    return check_intraday(_resolve_owner())


def run_eod_brief_default() -> dict:
    return eod_brief(_resolve_owner())


def run_eod_escalate_default() -> dict:
    return eod_escalate(_resolve_owner())


# --------------------------------------------------------------------------
# Drop attribution — post-close, flag holdings dropping on their OWN (not the
# market/sector), so the user knows which names need a news check.
# --------------------------------------------------------------------------
DROP_ATTR_ALERT_PCT = -3.0   # only flag stock-specific 1-day drops worse than this


def eod_drop_attribution(user_email: str) -> dict:
    """Flag holdings whose drop is STOCK-SPECIFIC (market & sector don't
    explain it). One consolidated push so the user can separate 'the company
    has a problem' from 'just riding a red tape'."""
    if not user_email:
        return {"ok": False, "reason": "no user_email"}
    from portfolio import drop_attribution as da

    scanned = 0
    flagged: list[dict] = []
    for holding, _meta in _load_positions(user_email):
        sym = (holding.get("ticker") or "").upper()
        if not sym or not da.is_individual_stock(sym):   # stocks only — skip funds/cash
            continue
        scanned += 1
        a = da.attribute(sym, window_days=1)
        if a and a["verdict"] == "stock" and a["move_pct"] <= DROP_ATTR_ALERT_PCT:
            flagged.append(a)

    if not flagged:
        log.info("portfolio.alerts: drop_attribution user=%s scanned=%d flagged=0", user_email, scanned)
        return {"ok": True, "scanned": scanned, "flagged": 0}

    flagged.sort(key=lambda x: x["move_pct"])
    worst = flagged[0]
    names = ", ".join(f"{a['symbol']} {a['move_pct']:+.1f}%" for a in flagged[:5])
    n = len(flagged)
    payload = {
        "title": f"🎯 {n} holding{'s' if n != 1 else ''} dropping on their own",
        "body": f"{names} — not the market. ~{worst['idiosyncratic_pct']:.0f}% of "
                f"{worst['symbol']}'s drop is stock-specific. Check the news.",
        "tag": "portfolio-drop-attr",
        "url": "/portfolio",
    }
    result = _send_push(user_email, payload, kind="position_alert")
    log.info("portfolio.alerts: drop_attribution user=%s scanned=%d flagged=%d pushed=%s",
             user_email, scanned, n, (result or {}).get("sent", 0))
    return {"ok": True, "scanned": scanned, "flagged": n,
            "names": [a["symbol"] for a in flagged]}


def run_drop_attribution_default() -> dict:
    return eod_drop_attribution(_resolve_owner())
