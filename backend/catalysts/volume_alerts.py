"""Volume-spike alert engine.

Runs every 5 min during market hours via cron. Watches the entire universe
of sub-$500M tickers; the catalysts PAGE shows everything that surges, but
PUSH NOTIFICATIONS only fire for names with HUGE real-money volume.

Why two tiers?
  Without the strict push gate the phone gets flooded with sub-$1, sub-$1M-
  traded micro-caps that are 95% pump. The push tier (PUSH_*) requires real
  participation — $10M+ traded today, 10×+ average volume, $1+ share price —
  so what makes the phone buzz is something a real institution could actually
  exit on. Everything else still appears on /catalysts for review.

Idempotency: each (ticker, market_session_date) pair fires AT MOST ONCE per
session. Mongo `volume_alert_history` tracks fired alerts.

Usage as a cron entry (every 5 min, 9:30-15:55 ET, Mon-Fri):
  */5 9-15 * * 1-5  /usr/local/bin/python -m catalysts.volume_alerts
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("catalysts.volume_alerts")

# --- Scan tier (loose — used for /catalysts page + history) --------------
# These thresholds decide which candidates get RECORDED. The page shows them
# all so the user can sanity-check what surged today.
DEFAULT_SURGE_THRESHOLD = 5.0     # 5× avg volume to register at all
MIN_DOLLAR_VOLUME = 500_000        # $500k traded — barely-real names land here
MIN_PRICE = 0.50                   # filter sub-pennies
MAX_MARKET_CAP = 500_000_000       # tiny stocks only

# --- Push tier (STRICT — only "huge volume" names buzz the phone) --------
# Pump-and-dump filter: anything below these floors stays on the page but
# does NOT generate a push. Tunable via env so the cron can be loosened
# without a redeploy.
PUSH_MIN_SURGE = float(os.getenv("CATALYST_PUSH_MIN_SURGE", "10.0"))             # 10× avg vol
PUSH_MIN_DOLLAR_VOLUME = float(os.getenv("CATALYST_PUSH_MIN_DVOL", "10000000"))  # $10M traded
PUSH_MIN_PRICE = float(os.getenv("CATALYST_PUSH_MIN_PRICE", "1.00"))             # no sub-$1
PUSH_MIN_MARKET_CAP = float(os.getenv("CATALYST_PUSH_MIN_MCAP", "50000000"))     # $50M+ cap


def _alerts_coll():
    """Mongo collection used to dedupe alerts within a session."""
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        c = client[db]["volume_alert_history"]
        c.create_index([("ticker", ASCENDING), ("session_date", ASCENDING)], unique=True)
        return c
    except Exception as exc:
        log.warning("volume alerts mongo unavailable: %s", exc)
        return None


def _et_session_date() -> str:
    """ISO date string in America/New_York — used as the dedupe key.

    A "session" is one trading day; pre-market spikes count as same day.
    """
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


def _already_fired(ticker: str) -> bool:
    coll = _alerts_coll()
    if coll is None:
        return False
    try:
        return coll.find_one({"ticker": ticker, "session_date": _et_session_date()}) is not None
    except Exception:
        return False


def _record_fired(ticker: str, payload: dict) -> None:
    coll = _alerts_coll()
    if coll is None:
        return
    try:
        coll.insert_one({
            "ticker": ticker,
            "session_date": _et_session_date(),
            "fired_at": datetime.now(timezone.utc),
            "payload": payload,
        })
    except Exception as exc:
        # Duplicate key is normal — race condition between scan + retry
        log.debug("volume alert insert skipped for %s: %s", ticker, exc)


# --- Scan logic ---------------------------------------------------------

def _build_alert_message(c: dict) -> str:
    """Compact WhatsApp message for one volume-spike alert."""
    surge = c.get("volume_surge_ratio") or 0
    cap_m = (c.get("market_cap") or 0) / 1e6
    chg = c.get("change_pct") or 0
    chg_emoji = "📈" if chg > 0 else "📉" if chg < 0 else "·"
    name = c.get("company_name") or ""
    return (
        f"🚨 *Volume spike: ${c['ticker']}*\n"
        f"{name[:60]}\n"
        f"Price: ${c.get('price', 0):.2f}  ·  {chg_emoji} {chg:+.1f}% today\n"
        f"Volume: *{surge:.1f}× avg*  ·  Cap: ${cap_m:.0f}M\n"
        f"\n"
        f"→ http://localhost:5173/catalysts (deep-dive: ${c['ticker']})"
    )


def _is_huge_volume(c: dict) -> tuple[bool, str]:
    """Strict push-tier gate. Returns (passed, reason_if_failed).

    "Huge volume" means real institutional-scale participation:
      • surge ≥ PUSH_MIN_SURGE (10× by default)
      • dollar volume ≥ PUSH_MIN_DOLLAR_VOLUME ($10M by default)
      • share price ≥ PUSH_MIN_PRICE ($1 by default — sub-$1 = pump)
      • market cap ≥ PUSH_MIN_MARKET_CAP ($50M by default)

    Anything failing one of these still gets recorded for the /catalysts
    page but stays silent on the phone.
    """
    surge = c.get("volume_surge_ratio") or 0
    dvol = c.get("dollar_volume") or 0
    price = c.get("price") or 0
    mcap = c.get("market_cap") or 0

    if surge < PUSH_MIN_SURGE:
        return False, f"surge {surge:.1f}× < {PUSH_MIN_SURGE:.0f}×"
    if dvol < PUSH_MIN_DOLLAR_VOLUME:
        return False, f"$vol {dvol/1e6:.1f}M < ${PUSH_MIN_DOLLAR_VOLUME/1e6:.0f}M"
    if price < PUSH_MIN_PRICE:
        return False, f"price ${price:.2f} < ${PUSH_MIN_PRICE:.2f}"
    if mcap and mcap < PUSH_MIN_MARKET_CAP:
        return False, f"cap ${mcap/1e6:.0f}M < ${PUSH_MIN_MARKET_CAP/1e6:.0f}M"
    return True, ""


def run(threshold: float = DEFAULT_SURGE_THRESHOLD,
        force_scan_dead: bool = False) -> dict:
    """Run one alert sweep. Returns counts of {scanned, recorded, pushed, skipped}.

    Two-tier flow:
      1. Run the existing tiny-stock scanner.
      2. RECORD any candidate above the loose scan threshold (page history).
      3. PUSH only candidates that pass _is_huge_volume() — strict tier.
    """
    from . import scanner
    from sepa import notify

    candidates = scanner.scan(
        max_share_price=20.0,
        max_market_cap=MAX_MARKET_CAP,
        min_abs_change_pct=2.0,   # lower bar — volume can spike before price
        max_results=50,
    )

    recorded = []                 # cleared scan tier (shows on page)
    pushed = []                   # cleared push tier (sent to phone)
    skipped_already = []
    skipped_thresh = []
    skipped_filter = []
    skipped_pump = []             # cleared scan tier but blocked from push

    for c in candidates:
        t = c["ticker"]
        surge = c.get("volume_surge_ratio") or 0
        dvol = c.get("dollar_volume") or 0
        price = c.get("price") or 0

        # --- Scan-tier gate (decides whether to record at all) ---
        if surge < threshold:
            skipped_thresh.append(t)
            continue
        if dvol < MIN_DOLLAR_VOLUME or price < MIN_PRICE:
            skipped_filter.append(t)
            continue
        if _already_fired(t):
            skipped_already.append(t)
            continue

        # --- Push-tier gate (huge volume only — anti-pump) ---
        push_ok, push_reason = _is_huge_volume(c)
        sent_ok = False
        if push_ok:
            # Scope gate — only buzz the phone for tickers in the user's
            # narrow allowlist (top-5 SEPA + watchlist). The catalyst row
            # is still recorded so it shows up on the /catalysts page.
            try:
                from push import scope as push_scope
                in_scope = push_scope.allowed_for(t)
            except Exception:
                in_scope = True   # fail-open if scope module misbehaves
            if in_scope:
                sent_ok = notify.send_alert(
                    title=f"🚀 {t} · vol surge {surge:.1f}×",
                    body=(f"${price:.2f} · {c.get('change_pct') or 0:+.1f}% · "
                          f"${dvol/1e6:.1f}M traded"),
                    url=f"/sepa/{t}",
                    kind="volume_breakout",
                    ticker=t,
                )
                log.info("volume alert PUSHED: %s surge=%.1fx dvol=$%.1fM sent=%s",
                         t, surge, dvol/1e6, sent_ok)
                pushed.append(t)
            else:
                log.info("volume alert push SUPPRESSED (out of scope): %s", t)
                skipped_pump.append({"ticker": t, "reason": "out of alert scope"})
        else:
            log.info("volume alert RECORDED-only (no push): %s — %s", t, push_reason)
            skipped_pump.append({"ticker": t, "reason": push_reason})

        _record_fired(t, {
            "surge": surge,
            "price": price,
            "change_pct": c.get("change_pct"),
            "market_cap": c.get("market_cap"),
            "dollar_volume": dvol,
            "company_name": c.get("company_name"),
            "pushed": push_ok,
            "push_blocked_reason": push_reason or None,
            "sent_whatsapp": sent_ok,
        })
        recorded.append(t)

    return {
        "scanned": len(candidates),
        "recorded": recorded,
        "pushed": pushed,
        "skipped_already_fired": skipped_already,
        "skipped_threshold": len(skipped_thresh),
        "skipped_filter": len(skipped_filter),
        "skipped_pump_filter": skipped_pump,
        "threshold": threshold,
        "push_thresholds": {
            "surge": PUSH_MIN_SURGE,
            "dollar_volume": PUSH_MIN_DOLLAR_VOLUME,
            "price": PUSH_MIN_PRICE,
            "market_cap": PUSH_MIN_MARKET_CAP,
        },
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


def get_history(session_date: Optional[str] = None) -> list[dict]:
    """Return alerts fired today (or specified session_date) for the UI."""
    coll = _alerts_coll()
    if coll is None:
        return []
    sd = session_date or _et_session_date()
    try:
        cursor = coll.find({"session_date": sd}).sort("fired_at", -1)
        return [
            {
                "ticker": d["ticker"],
                "fired_at": d["fired_at"].isoformat() if d.get("fired_at") else None,
                "payload": d.get("payload") or {},
            }
            for d in cursor
        ]
    except Exception as exc:
        log.warning("history fetch failed: %s", exc)
        return []


__all__ = ["run", "get_history", "DEFAULT_SURGE_THRESHOLD"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
    threshold = float(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SURGE_THRESHOLD
    result = run(threshold=threshold)
    log.info("volume alerts done: %s", result)
