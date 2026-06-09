"""Engine heartbeat + staleness — "are the alerts actually running right now?"

Why this exists: the Cheetah engine runs as cron jobs inside Docker on a Mac that
sleeps. When the Mac sleeps, the whole container freezes and NO alerts fire — and
the user only finds out hours later. An in-container watchdog can't catch a freeze
that freezes itself, but the FRONTEND runs on the user's phone (not frozen), so it
CAN. This module exposes a freshness read the UI polls to show a "⚠ engine may be
paused" banner during market hours. Detection + honesty, not auto-repair.

Signal: the ``*/5`` ``sepa.cli alerts`` job calls :func:`beat` after each run, so a
fresh ``engine_heartbeat`` doc means "alerts ran within the last few minutes." If
the heartbeat goes stale during market hours, the engine is frozen/behind. We also
read the latest scan's ``generated_at`` as a corroborating signal.

DISPLAY-only / observability — touches no alert logic, no scoring. Additive.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("observability.engine_heartbeat")

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    _ET = None

# Alerts run every 5 min during the session; >12 min stale ⇒ ≥2 missed cycles.
ALERTS_STALE_SEC = 12 * 60

_db = None


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient
        client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"),
                             serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        return _db
    except Exception as exc:
        log.warning("engine_heartbeat: Mongo unavailable: %s", exc)
        return None


def _now_epoch() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def beat(name: str = "alerts") -> None:
    """Stamp 'this engine job just ran'. Best-effort; never raises."""
    db = _get_db()
    if db is None:
        return
    try:
        db.engine_heartbeat.update_one(
            {"name": name},
            {"$set": {"name": name, "ts": _now_epoch()}},
            upsert=True,
        )
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("engine_heartbeat.beat(%s) failed: %s", name, exc)


def _last_beat(name: str = "alerts") -> Optional[int]:
    db = _get_db()
    if db is None:
        return None
    try:
        doc = db.engine_heartbeat.find_one({"name": name})
        return int(doc["ts"]) if doc and doc.get("ts") is not None else None
    except Exception:
        return None


def _to_epoch(val) -> Optional[float]:
    """Accept epoch number OR ISO-8601 string (the scan stores ISO)."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def _market_open(now: Optional[datetime] = None) -> bool:
    """True on a weekday between 9:30 and 16:00 ET. Does NOT account for market
    holidays (a holiday would read 'open' and could show a false banner) — an
    accepted, low-harm edge for an informational banner."""
    n = now or (datetime.now(_ET) if _ET else datetime.utcnow())
    if n.weekday() >= 5:
        return False
    minutes = n.hour * 60 + n.minute
    return (9 * 60 + 30) <= minutes <= (16 * 60)


def engine_status() -> dict:
    """Freshness read for the UI banner. Never raises."""
    now_epoch = _now_epoch()
    mopen = _market_open()
    last_alert = _last_beat("alerts")
    alert_age = (now_epoch - last_alert) if last_alert else None

    scan_at = None
    try:
        from sepa import scanner
        latest = scanner.load_latest() or {}
        scan_at = _to_epoch(latest.get("generated_at"))
    except Exception:
        scan_at = None
    scan_age = (now_epoch - scan_at) if scan_at else None

    stale = False
    reason = None
    if mopen:
        if last_alert is None:
            stale = True
            reason = "no alert-engine heartbeat recorded yet today"
        elif alert_age is not None and alert_age > ALERTS_STALE_SEC:
            stale = True
            mins = round(alert_age / 60)
            reason = f"alert engine last ran {mins} min ago (expected every ~5 min)"

    return {
        "market_open": mopen,
        "stale": stale,
        "stale_reason": reason,
        "alerts_last_run_epoch": last_alert,
        "alerts_age_sec": alert_age,
        "scan_last_run_epoch": int(scan_at) if scan_at else None,
        "scan_age_sec": int(scan_age) if scan_age else None,
        "checked_at_epoch": now_epoch,
        "threshold_sec": ALERTS_STALE_SEC,
    }
