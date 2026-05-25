"""Daily real-estate scrape + notification.

Runs once a day at 8am ET (see backend/crontab). Replaces the inline
``python -c "..."`` one-liner that used to live in cron with a proper
module so we can:

  1. Compute deltas vs yesterday and push a concise "what changed"
     notification — not a noise alert, a daily summary the owner
     actually wants to see first thing in the morning.
  2. Detect scrape failure (all three sources blocked) and push a
     separate alert so the owner doesn't silently miss days.
  3. Detect engagement stagnation (no new views for N days) and
     suggest a price drop / photo refresh.
  4. Be testable / runnable manually:
         docker compose exec cron python -m house.daily_scrape
         docker compose exec cron python -m house.daily_scrape --dry-run

The notification kinds (``house_daily``, ``house_scrape_failed``,
``house_stagnant``) honor each device's pref toggles like every other
push — opt-out is per-category on the Notifications page.
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:                                          # python <3.9 fallback
    ZoneInfo = None                                          # type: ignore

from house import store, scraper as scraper_mod

log = logging.getLogger("house.daily_scrape")

# Engagement signals we sum for "daily interest" — Zillow views are the
# dominant signal but the others contribute when they're populated.
_INTEREST_FIELDS = (
    "zillow_views", "redfin_views",
    "zillow_saves", "redfin_saves", "realtor_saves",
    "redfin_tours", "showings_today", "offers_received",
)

# How many consecutive days of zero added views before we ping the
# "engagement stagnant" suggestion. 3 days = "a long weekend with no
# activity" — that's worth a nudge to consider a price drop or photo
# refresh. Shorter would be too noisy, longer too late.
_STAGNATION_DAYS = 3


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _owner_email() -> str:
    """Same lookup the cron one-liner used — HOUSE_OWNER_EMAIL env var,
    falling back to Ajay's address. Lower-cased so it matches the
    canonical key in Mongo."""
    return os.getenv("HOUSE_OWNER_EMAIL", "ajaykandakatla@gmail.com").lower()


def _today_et_str() -> str:
    tz = ZoneInfo("America/New_York") if ZoneInfo else None
    return (datetime.now(tz) if tz else datetime.now()).strftime("%Y-%m-%d")


def _yesterday_snapshot(owner: str) -> Optional[dict]:
    """The previous snapshot, regardless of how many days back. We
    don't require it to be literally yesterday — listing activity has
    natural gaps (weekends, holidays). The diff message names the
    actual prior date so the owner can interpret the comparison."""
    history = store.list_snapshots(owner, days=14)
    today = _today_et_str()
    for r in reversed(history):
        if r.get("date_et") and r["date_et"] != today:
            return r
    return None


def _interest_total(snap: Optional[dict]) -> int:
    if not snap:
        return 0
    return sum(int(snap.get(k) or 0) for k in _INTEREST_FIELDS)


def _consecutive_no_view_days(history: list[dict]) -> int:
    """Walk the snapshot history (oldest → newest) and count the trailing
    streak of days where view counts didn't move. Empty/missing fields
    are treated as zero, so a day with no scrape data counts as
    'no movement' too."""
    days = 0
    prev_views: Optional[int] = None
    for snap in history:
        views = int(snap.get("zillow_views") or 0) + int(snap.get("redfin_views") or 0)
        if prev_views is not None and views > prev_views:
            days = 0                                         # movement broke the streak
        else:
            days += 1
        prev_views = views
    return days


# ----------------------------------------------------------------------
# Push composition
# ----------------------------------------------------------------------
def _fmt_pct(cur: int, prev: int) -> str:
    if prev <= 0:
        return ""
    delta = ((cur - prev) / prev) * 100
    sign = "+" if delta >= 0 else ""
    return f" ({sign}{delta:.0f}%)"


def _compose_daily_body(today: dict, prev: Optional[dict]) -> str:
    """Build the human-readable summary line. Picks the most actionable
    numbers and omits zero fields so the body stays scannable on a
    lock-screen notification."""
    bits: list[str] = []
    today_views = int(today.get("zillow_views") or 0) + int(today.get("redfin_views") or 0)
    prev_views = (int((prev or {}).get("zillow_views") or 0) +
                  int((prev or {}).get("redfin_views") or 0))
    if today_views:
        bits.append(f"{today_views} views{_fmt_pct(today_views, prev_views)}")
    today_saves = (int(today.get("zillow_saves") or 0) +
                   int(today.get("redfin_saves") or 0) +
                   int(today.get("realtor_saves") or 0))
    if today_saves:
        bits.append(f"{today_saves} saves")
    tours = int(today.get("redfin_tours") or 0) + int(today.get("showings_today") or 0)
    if tours:
        bits.append(f"{tours} tour{'s' if tours != 1 else ''}")
    offers = int(today.get("offers_received") or 0)
    if offers:
        bits.append(f"🤝 {offers} offer{'s' if offers != 1 else ''}")
    open_houses = int(today.get("open_houses_scheduled") or 0)
    if open_houses:
        bits.append(f"{open_houses} open house{'s' if open_houses != 1 else ''}")
    if not bits:
        return "No new activity today."
    return " · ".join(bits)


def _push(owner: str, *, kind: str, title: str, body: str, url: str = "/house") -> None:
    """Per-user push targeted at the house owner. Uses send_alert which
    routes through send_to_user since user_email is supplied — no risk
    of broadcasting house data to other accounts (see the cross-user
    push safety work shipped on 2026-05-17)."""
    try:
        from sepa import notify
        notify.send_alert(
            title=title, body=body, url=url,
            kind=kind, user_email=owner,
        )
    except Exception as exc:
        log.warning("house: push %s failed: %s", kind, exc)


# ----------------------------------------------------------------------
# Main flow
# ----------------------------------------------------------------------
def run_once(*, dry_run: bool = False) -> dict:
    """Scrape, persist, notify. Returns a summary dict for the cron log."""
    owner = _owner_email()
    cfg = store.get_config(owner) or {}
    if not any(cfg.get(k) for k in ("redfin_url", "zillow_url", "realtor_url")):
        log.info("house: no URLs configured for %s — skipping scrape", owner)
        return {"ok": False, "reason": "no urls configured"}

    # Snapshot the "before" state so the delta computation isn't
    # confused by today's partial in-flight scrape merging into
    # itself when the cron re-runs.
    prev = _yesterday_snapshot(owner)

    # Scrape — best effort. Failures inside the scraper are converted
    # into _blocked_<src> markers in the returned dict, not exceptions.
    metrics = scraper_mod.scrape_all(
        redfin_url=cfg.get("redfin_url"),
        zillow_url=cfg.get("zillow_url"),
        realtor_url=cfg.get("realtor_url"),
    )
    blocked = [k.replace("_blocked_", "") for k in list(metrics) if k.startswith("_blocked_")]
    # Strip blocked-source markers before persisting — they're status,
    # not data.
    metrics_clean = {k: v for k, v in metrics.items() if not k.startswith("_blocked_")}
    real_keys = [k for k in metrics_clean if k != "source"]

    summary = {
        "owner": owner,
        "blocked": blocked,
        "real_keys": real_keys,
        "dry_run": dry_run,
    }

    # Path 1: nothing scraped (all sources blocked or empty config).
    # Push a failure notification so the owner can fall back to
    # manual entry and not silently lose days.
    if not real_keys:
        log.warning("house: scrape returned no usable data; blocked=%s", blocked)
        if not dry_run:
            _push(
                owner,
                kind="house_scrape_failed",
                title="⚠ Real-estate scrape failed",
                body=(
                    f"No numbers came back today. Blocked: {', '.join(blocked) or 'unknown'}. "
                    "Enter manually at /house."
                ),
                url="/house",
            )
        summary["push"] = "scrape_failed"
        return summary

    # Path 2: scrape succeeded — persist and decide if there's anything
    # worth notifying about.
    if not dry_run:
        store.upsert_snapshot(owner, metrics_clean)

    # Reload today's snapshot AFTER the upsert so we send a notification
    # based on the merged state (today's scrape + any manual numbers
    # the owner entered earlier in the day).
    today_snap = (
        store.latest_snapshot(owner)
        if not dry_run
        else {**(store.latest_snapshot(owner) or {}), **metrics_clean}
    ) or metrics_clean

    body = _compose_daily_body(today_snap, prev)
    if blocked:
        body += f"  ·  ⚠ blocked: {', '.join(blocked)}"
    title = "🏡 Daily listing update"
    if not dry_run:
        _push(owner, kind="house_daily", title=title, body=body, url="/house")
    summary["push"] = "house_daily"
    summary["body"] = body

    # Path 3: engagement stagnation — separate push so the owner can
    # opt out of "you should drop the price" suggestions without
    # losing the daily update. Skipped if any movement at all today.
    history = store.list_snapshots(owner, days=_STAGNATION_DAYS + 2)
    streak = _consecutive_no_view_days(history)
    summary["no_view_streak_days"] = streak
    if streak >= _STAGNATION_DAYS:
        # Suppress duplicates — only re-fire once per streak by checking
        # if we already sent a stagnant push today. We track this on
        # the snapshot itself so it survives container restarts.
        already_sent = bool((today_snap or {}).get("_stagnant_notified"))
        if not already_sent and not dry_run:
            _push(
                owner,
                kind="house_stagnant",
                title="📉 Listing engagement stalled",
                body=(
                    f"No new views for {streak} days. Worth considering: "
                    "price drop, fresh photos, or an open-house push."
                ),
                url="/house",
            )
            store.upsert_snapshot(owner, {"_stagnant_notified": True})
            summary["push_extra"] = "house_stagnant"
        elif already_sent:
            summary["push_extra_suppressed"] = "house_stagnant (already sent today)"

    log.info("house.daily_scrape: %s", summary)
    return summary


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = argv or sys.argv[1:]
    dry_run = "--dry-run" in args
    result = run_once(dry_run=dry_run)
    print(
        "house.daily_scrape: "
        f"real_keys={len(result.get('real_keys') or [])} "
        f"blocked={result.get('blocked') or []} "
        f"push={result.get('push')} "
        f"extra={result.get('push_extra') or result.get('push_extra_suppressed') or '-'} "
        f"dry_run={result.get('dry_run')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
