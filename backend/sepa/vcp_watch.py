"""Hourly VCP watcher — diff-based notifications.

Pattern: run every hour during market hours, do a fast scan, find names with
a VCP base (or Power Play, optionally), compare against the previous run's
list in Mongo, and only notify on the *new* ones. This avoids spamming you
with the same VCP every hour for a week.

Mongo collection: `vcp_watch_state`
  Single doc {_id: "current", symbols: ["NVDA", "MU", ...], snapshot: {...}}

CLI entry: `python -m sepa.cli vcp-watch [--include-power-play]`.

Notifications:
  - WhatsApp via existing notify.send_whatsapp (Twilio sandbox)
  - Browser Notification (via the existing /sepa/alerts/recent feed; the
    frontend usePriceAlerts hook polls this and surfaces a system notification
    while the SEPA tab is open)
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

from . import scanner, notify

log = logging.getLogger("sepa.vcp_watch")


def _coll():
    """Return the vcp_watch_state Mongo collection, or None if unavailable."""
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[db_name].vcp_watch_state
    except Exception as exc:
        log.warning("vcp_watch: mongo unavailable (%s)", exc)
        return None


def _alerts_coll():
    """Persistent alerts feed read by /sepa/alerts/recent.

    The frontend's usePriceAlerts hook polls that endpoint and surfaces each
    new fire as a browser system notification. We piggy-back on the existing
    `price_alert_fires` collection so VCP alerts ride the same pipe as the
    pivot/stop alerts the user has configured manually."""
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        return client[db_name].price_alert_fires
    except Exception:
        return None


def _is_setup_match(rec: dict, include_power_play: bool) -> bool:
    s = rec.get("entry_setup")
    if not s:
        return False
    t = s.get("type")
    if t == "VCP":
        return True
    if include_power_play and t == "POWER_PLAY":
        return True
    return False


def _format_alert(rec: dict) -> str:
    """One-line alert text for WhatsApp + browser notification."""
    s = rec.get("entry_setup") or {}
    pivot = s.get("pivot")
    stop = s.get("stop")
    rs = rec.get("rs_rank")
    score = rec.get("score")
    rating = rec.get("rating") or "—"
    sym = rec.get("symbol")
    name = rec.get("name") or ""
    pct_risk = None
    if pivot and stop:
        try:
            pct_risk = (1 - float(stop) / float(pivot)) * 100
        except Exception:
            pct_risk = None
    risk_part = f" · risk {pct_risk:.1f}%" if pct_risk is not None else ""
    return (
        f"🎯 {sym} {s.get('type')} · pivot ${pivot} · stop ${stop}{risk_part}\n"
        f"   {name} · score {score} {rating} · RS {rs}"
    )


def run(include_power_play: bool = False,
        universe_mode: Optional[str] = None) -> dict:
    """Run a fast scan, diff against previous run, notify on new VCPs.

    Args:
        include_power_play: also alert on Power Play setups (looser than VCP).
        universe_mode: optional "curated" / "sp500" / "russell1000" / "expanded".

    Returns a summary dict suitable for logging / CLI output.
    """
    t0 = time.time()
    log.info("vcp_watch: running fast scan (mode=%s, include_pp=%s)",
             universe_mode or "default", include_power_play)

    # We persist the scan as a side effect — the regular UI benefits too.
    payload = scanner.scan_universe_fast(
        symbols=None, persist=True, universe_mode=universe_mode,
        fallback_when_missing=True, emitter=None,
    )

    matches = [r for r in (payload.get("all_results") or [])
               if _is_setup_match(r, include_power_play)]
    matches.sort(key=lambda r: r.get("score", 0), reverse=True)
    current_syms = sorted({r["symbol"] for r in matches})

    coll = _coll()
    prev_syms: set[str] = set()
    if coll is not None:
        try:
            doc = coll.find_one({"_id": "current"})
            if doc:
                prev_syms = set(doc.get("symbols") or [])
        except Exception as exc:
            log.warning("vcp_watch: state read failed (%s)", exc)

    new_syms = [s for s in current_syms if s not in prev_syms]
    cleared_syms = sorted(prev_syms - set(current_syms))
    new_records = [r for r in matches if r["symbol"] in new_syms]

    log.info("vcp_watch: %d total setups · %d new · %d cleared since last run",
             len(matches), len(new_syms), len(cleared_syms))

    # --- Notifications --------------------------------------------------------
    # Scope gate — only push setups in the user's allowlist (top-5 SEPA +
    # watchlist by default). VCP/Power Play setups OUTSIDE the allowlist
    # still surface on the /sepa page; they just don't buzz the phone.
    try:
        from push import scope as push_scope
        scoped_new = [r for r in new_records if push_scope.allowed_for(r.get("symbol", ""))]
        suppressed = len(new_records) - len(scoped_new)
        if suppressed:
            log.info("vcp_watch: %d new setup(s) suppressed (out of scope)", suppressed)
    except Exception:
        scoped_new = new_records   # fail-open

    notified = 0
    if scoped_new:
        kind_label = "VCP / Power Play" if include_power_play else "VCP"
        # If only one new setup, route the push to that ticker's SEPA page.
        # If multiple, route to /sepa so the user can scan the list.
        if len(scoped_new) == 1:
            sym = scoped_new[0].get("symbol", "")
            ok = notify.send_alert(
                title=f"🚀 New {kind_label} setup · {sym}",
                body=_format_alert(scoped_new[0]),
                url=f"/sepa/{sym}",
                kind="sepa_new_candidate",
                ticker=sym,
            )
        else:
            tickers = ", ".join(r.get("symbol", "?") for r in scoped_new[:5])
            extra = f" + {len(scoped_new) - 5} more" if len(scoped_new) > 5 else ""
            ok = notify.send_alert(
                title=f"🚀 {len(scoped_new)} new {kind_label} setups",
                body=f"{tickers}{extra}",
                url="/sepa",
                kind="sepa_new_candidate",
            )
        log.info("vcp_watch: notify send -> %s", ok)

        # Browser-notification feed — the frontend's usePriceAlerts hook polls
        # /sepa/alerts/recent and converts each entry into a system notification.
        # Use scoped_new (NOT new_records) so the browser-notification feed
        # also respects the allowlist — otherwise the page would still pop
        # toasts for out-of-scope tickers.
        afeed = _alerts_coll()
        if afeed is not None:
            now = int(time.time())
            sent_channels = ["whatsapp", "browser"] if ok else ["browser"]
            for rec in scoped_new:
                setup = rec.get("entry_setup") or {}
                try:
                    afeed.insert_one({
                        "alert_id": None,                           # no underlying user alert
                        "symbol":   rec["symbol"],
                        "kind":     f"setup_{(setup.get('type') or 'VCP').lower()}",
                        "level":    setup.get("pivot"),             # display as pivot price
                        "price":    setup.get("pivot"),
                        "fired_at": now,
                        "channels": sent_channels,
                        "message":  _format_alert(rec).replace("\n", " "),
                        "meta": {
                            "score":   rec.get("score"),
                            "rating":  rec.get("rating"),
                            "rs_rank": rec.get("rs_rank"),
                            "stop":    setup.get("stop"),
                        },
                    })
                    notified += 1
                except Exception as exc:
                    log.warning("vcp_watch: alerts_feed insert failed for %s: %s",
                                rec["symbol"], exc)

    # --- Persist new state ----------------------------------------------------
    if coll is not None:
        try:
            coll.update_one(
                {"_id": "current"},
                {"$set": {
                    "symbols":    current_syms,
                    "fetched_at": int(t0),
                    "fetched_at_iso": datetime.fromtimestamp(t0, tz=timezone.utc).isoformat(),
                    "include_power_play": include_power_play,
                    "snapshot":   {r["symbol"]: r.get("entry_setup") for r in matches},
                }},
                upsert=True,
            )
        except Exception as exc:
            log.warning("vcp_watch: state write failed (%s)", exc)

    return {
        "duration_sec":  round(time.time() - t0, 2),
        "scan_universe": payload.get("universe_size"),
        "scan_analyzed": payload.get("analyzed"),
        "current_setups": len(matches),
        "new_count":     len(new_records),
        "cleared_count": len(cleared_syms),
        "new_symbols":   new_syms,
        "cleared_symbols": cleared_syms,
        "notified":      notified,
    }
