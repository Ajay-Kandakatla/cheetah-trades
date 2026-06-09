"""Real-time pivot / entry alerts — runs with the `alerts` cron (every ~5 min in
market hours). Fires ONCE per symbol per kind per ET trading day:

  • AT_PIVOT    🟢 — a candidate AT its pivot on a fresh breakout (entry_exit
                     decision ENTER), Stage 2, not extended/climaxing — AND that
                     actually passes the buyable gate (`is_buyable`, which caps
                     extension at +3% past pivot, scanner.BUYABLE_MAX_EXT_PCT).
                     The clean entry, the moment it triggers — never a name you
                     can't actually buy (Ajay 2026-06-09: "don't report if it's
                     not buyable"; e.g. VECO at +4% past pivot is NOT alerted).
  • APPROACHING 🟡 — within ~2.5% BELOW the pivot — set the buy-stop now so an
                     overnight/pre-market gap can't steal the entry. (Pre-breakout
                     by definition, so it is gated on being a live Stage-2
                     candidate setup, not on is_buyable.)

DEDUP (2026-06-09): the per-(symbol, kind, ET-day) key is recorded the moment we
decide to fire — NOT contingent on a device actually ACKing the push. The old
"mark only if delivered" gate meant that whenever web-push returned 0 reached
(stale subs / Mac asleep), the key was never written and the SAME alert re-fired
into the feed every 5-min tick. Mark-on-attempt → once per name per kind per day,
full stop. The raw BUYABLE flip alert was removed — the buyable-gated AT_PIVOT
above subsumes it, so a buyable name at its pivot is one alert, not two.

Reuses the at-pivot derived view + notify (Web Push). Dedup in Mongo
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


def _buyable_set(scanner) -> set:
    """Symbols that pass the corrected buyable gate in the latest scan
    (`is_buyable` already caps extension at +3% past pivot). AT_PIVOT alerts are
    gated on membership so we never alert a name that isn't actually buyable."""
    rows = (scanner.load_latest() or {}).get("all_results") or []
    return {r.get("symbol") for r in rows if r.get("is_buyable") and r.get("symbol")}


def check_pivot_alerts(dry_run: bool = False) -> dict:
    """Fire the pivot alert kinds for newly-qualifying names. dry_run returns what
    WOULD fire without sending (used by the smoke test)."""
    from . import at_pivot, scanner, notify
    coll = _coll()
    d = _et_date()
    fired: list[str] = []
    skipped: list[str] = []
    delivery_failed: list[str] = []
    would: list[str] = []
    suppressed_not_buyable: list[str] = []

    def fire(sym: str, kind: str, emoji: str, title: str, body: str) -> None:
        key = f"{sym}:{kind}:{d}"
        if _already(coll, key):
            skipped.append(key)
            return
        would.append(f"{kind}:{sym}")
        if dry_run:
            return
        # Mark BEFORE the send so a transient push miss (0 devices reached —
        # stale subs / Mac asleep) can't make the next 5-min tick re-fire the
        # same name. Once per symbol/kind/ET-day, regardless of delivery.
        _mark(coll, key)
        ok = notify.send_alert(title=f"{emoji} {title}", body=body,
                               url=f"/sepa/{sym}", kind="pivot_alert", ticker=sym)
        (fired if ok else delivery_failed).append(key)

    buyable = _buyable_set(scanner)

    # AT_PIVOT + APPROACHING — from the at-pivot derived view (already Stage 2 +
    # setup, NOT climaxing). AT_PIVOT is ADDITIONALLY gated on the buyable set.
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
            if sym not in buyable:                  # at the pivot but NOT buyable → don't alert
                suppressed_not_buyable.append(sym)
                continue
            px = r.get("live_price") or r.get("pivot")
            fire(sym, "AT_PIVOT", "🟢", f"At the pivot: {sym} @ ${px}",
                 f"{sym} is at its pivot ${r.get('pivot')} (RS {r.get('rs_rank')}) — "
                 f"clean breakout in the buy zone, not extended. Buy at the pivot, not chasing.")
        elif r.get("bucket") == "approaching" and (r.get("dist_pct") or -99) >= -ALERT_NEAR_PCT:
            fire(sym, "APPROACHING", "🟡",
                 f"Approaching pivot: {sym} ({r.get('dist_pct')}% below)",
                 f"{sym} is {abs(r.get('dist_pct') or 0)}% below its pivot ${r.get('pivot')} "
                 f"(RS {r.get('rs_rank')}) — set a buy-stop at ${r.get('pivot')} so a gap can't steal the entry.")

    log.info("pivot_alerts: fired=%d delivery_failed=%d skipped=%d suppressed_not_buyable=%d%s",
             len(fired), len(delivery_failed), len(skipped), len(suppressed_not_buyable),
             f" would={would}" if dry_run else "")
    return {"fired": fired, "skipped": skipped, "delivery_failed": delivery_failed,
            "suppressed_not_buyable": suppressed_not_buyable, "would_fire": would,
            "checked_at": int(time.time()), "dry_run": dry_run}
