"""Real-time pivot / entry alerts — runs with the `alerts` cron (every ~5 min in
market hours). Fires ONCE per symbol per kind per ET trading day:

  • AT_PIVOT    🟢 — a candidate AT its pivot on a fresh breakout (entry_exit
                     decision ENTER), Stage 2, not extended/climaxing — the clean
                     entry, the moment it triggers (catch the $65.77, not the $80.80).
  • APPROACHING 🟡 — within ~5% BELOW the pivot — set the buy-stop now so an
                     overnight/pre-market gap can't steal the entry.
  • BUYABLE     ✅ — the raw is_buyable gate flipped (with an honest caveat when the
                     name is actually extended/climaxing, e.g. KNX +22.9% past pivot).

Reuses the at-pivot derived view + notify (Web Push + WhatsApp). Dedup in Mongo
`pivot_alerts`. Educational, not advice (Ajay 2026-06-08: "I keep missing pivots").
"""
from __future__ import annotations

import logging
import os
import time

log = logging.getLogger("sepa.pivot_alerts")
_mem: dict = {}

# Alert only when REALLY imminent (the at-pivot SECTION shows the full 5% band, but
# an alert within 5% would spam ~30 names) and skip ETFs — these are VCP-pivot stock
# plays, not leveraged/index funds.
ALERT_NEAR_PCT = 2.5


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].pivot_alerts
    except Exception:
        return None


def _et_date() -> str:
    try:
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        return datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return time.strftime("%Y-%m-%d")


def _already(coll, key: str) -> bool:
    if coll is None:
        return key in _mem
    try:
        return coll.find_one({"_id": key}) is not None
    except Exception:
        return False


def _mark(coll, key: str) -> None:
    if coll is None:
        _mem[key] = 1
        return
    try:
        coll.update_one({"_id": key}, {"$set": {"ts": int(time.time())}}, upsert=True)
    except Exception as exc:
        log.debug("pivot_alerts mark failed: %s", exc)


def check_pivot_alerts(buyable_raw: bool = True, dry_run: bool = False) -> dict:
    """Fire the three pivot alert kinds for newly-qualifying names. dry_run returns
    what WOULD fire without sending (used by the smoke test)."""
    from . import at_pivot, scanner, notify
    coll = _coll()
    d = _et_date()
    fired: list[str] = []
    skipped: list[str] = []
    would: list[str] = []

    def fire(sym: str, kind: str, emoji: str, title: str, body: str) -> None:
        key = f"{sym}:{kind}:{d}"
        if _already(coll, key):
            skipped.append(key)
            return
        would.append(f"{kind}:{sym}")
        if dry_run:
            return
        ok = notify.send_alert(title=f"{emoji} {title}", body=body,
                               url=f"/sepa/{sym}", kind="pivot_alert", ticker=sym)
        if ok:
            _mark(coll, key)
            fired.append(key)
        else:
            skipped.append(key + ":send_failed")

    # AT_PIVOT + APPROACHING — from the at-pivot derived view (already Stage 2 +
    # setup, NOT extended, NOT climaxing).
    try:
        ap = at_pivot.get_at_pivot(force=True)
    except Exception as exc:
        log.warning("pivot_alerts at_pivot load failed: %s", exc)
        ap = {"rows": []}
    for r in ap.get("rows", []):
        sym = r.get("symbol")
        if not sym or r.get("is_etf"):              # stock pivot plays only — skip funds
            continue
        if r.get("bucket") == "at_pivot" and r.get("decision") == "ENTER":
            px = r.get("live_price") or r.get("pivot")
            fire(sym, "AT_PIVOT", "🟢", f"At the pivot: {sym} @ ${px}",
                 f"{sym} is at its pivot ${r.get('pivot')} (RS {r.get('rs_rank')}) — "
                 f"clean breakout in the buy zone, not extended. Buy at the pivot, not chasing.")
        elif r.get("bucket") == "approaching" and (r.get("dist_pct") or -99) >= -ALERT_NEAR_PCT:
            fire(sym, "APPROACHING", "🟡",
                 f"Approaching pivot: {sym} ({r.get('dist_pct')}% below)",
                 f"{sym} is {abs(r.get('dist_pct') or 0)}% below its pivot ${r.get('pivot')} "
                 f"(RS {r.get('rs_rank')}) — set a buy-stop at ${r.get('pivot')} so a gap can't steal the entry.")

    # BUYABLE (raw) — every is_buyable flip, with an honest caveat if extended/climax.
    if buyable_raw:
        for r in [x for x in (scanner.load_latest() or {}).get("all_results") or [] if x.get("is_buyable")]:
            sym = r.get("symbol")
            if not sym or r.get("is_etf"):
                continue
            ee = r.get("entry_exit") or {}
            ss = r.get("sell_signals") or {}
            extended = (ee.get("entry") or {}).get("status") == "missed_extended"
            reduce = ss.get("action") in ("REDUCE", "SELL")
            caveat = ""
            if reduce:
                caveat = " ⚠ but flagged REDUCE — don't chase"
            elif extended:
                pivot = (r.get("entry_setup") or {}).get("pivot")
                cur = r.get("last_close")
                pct = round((cur / pivot - 1) * 100) if (pivot and cur and pivot > 0) else None
                caveat = f" ⚠ but +{pct}% past pivot — extended, don't chase" if pct is not None else " ⚠ but extended"
            fire(sym, "BUYABLE", "✅",
                 f"Buyable: {sym}{' (extended)' if (extended or reduce) else ''}",
                 f"{sym} cleared the full buy gate (RS {r.get('rs_rank')}, Stage 2, breakout){caveat}.")

    log.info("pivot_alerts: fired=%d skipped=%d%s", len(fired), len(skipped),
             f" would={would}" if dry_run else "")
    return {"fired": fired, "skipped": skipped, "would_fire": would,
            "checked_at": int(time.time()), "dry_run": dry_run}
