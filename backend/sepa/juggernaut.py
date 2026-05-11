"""Watchlist-scoped "Juggernaut" detector.

A *juggernaut* is a watchlist ticker showing BOTH institutional accumulation
AND rising momentum simultaneously — the early signature of "stealth"
buying that precedes the official high-volume breakout. The Nokia / NVTS
pattern: stock isn't on a 1.5× volume bar yet, but up-day volume has been
quietly stacking on top of down-day volume for weeks, RS rank is climbing,
and today's tape shows real engagement (1.2×+ avg volume) even without a
breakout candle.

Why this exists vs ``breakouts.py``
-----------------------------------
``breakouts.detect_volume_breakouts`` fires on the day of a >1.5× volume
candle — by then the entry is often past pivot. ``breakouts.detect_rising_momentum``
catches the setup but doesn't require a smart-money signature. This detector
is the *union*: rising momentum AND accumulation, scoped strictly to the
watchlist, surfaced as ONE consolidated daily-running notification rather
than per-ticker spam.

Detection criteria (ALL gates must pass)
----------------------------------------
1. Ticker is on the user's watchlist.
2. ``volume.up_down_vol_ratio >= UD_VOL_MIN`` (default 1.5) — up-day volume
   dominates down-day volume over the trailing 50 bars. Pure accumulation
   signal per Minervini Ch 10.
3. Today's volume / 50-day average >= ``TODAY_VOL_MULT`` (default 1.2) —
   confirms institutions are engaged *right now*, not just historically.
4. AT LEAST ONE of:
   a. RS rank climbed ``RS_CLIMB_MIN`` (default 5) points over the last
      ``LOOKBACK_DAYS`` scan_runs.
   b. Composite score climbed ``SCORE_CLIMB_MIN`` (default 3.0) points
      over the same window.
   c. day_change_pct >= ``DAY_PCT_BURST`` (default +3.0%) — an intraday
      surge that the multi-day deltas wouldn't catch yet.

Notification flow
-----------------
Each cron run computes the current juggernaut set. Compared against
``juggernaut_state.<today_et>`` in Mongo:
  - If new tickers emerged → fire ONE push titled
    "Juggernaut stocks today from SEPA watch List" listing the full current
    set with NEW emergences highlighted.
  - If nothing new, no push (the state collection prevents re-alerting).
State is keyed by ET date and naturally resets at the next session boundary.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("sepa.juggernaut")

# --- Tunables (env-overridable so personal Macs can dial sensitivity) ---
RS_CLIMB_MIN     = int(os.getenv("JUGGER_RS_CLIMB_MIN", "5"))
SCORE_CLIMB_MIN  = float(os.getenv("JUGGER_SCORE_CLIMB_MIN", "3"))
LOOKBACK_DAYS    = int(os.getenv("JUGGER_LOOKBACK_DAYS", "5"))
UD_VOL_MIN       = float(os.getenv("JUGGER_UD_VOL_MIN", "1.5"))
TODAY_VOL_MULT   = float(os.getenv("JUGGER_TODAY_VOL_MULT", "1.2"))
DAY_PCT_BURST    = float(os.getenv("JUGGER_DAY_PCT_BURST", "3.0"))


# ---------------------------------------------------------------------------
# Mongo helpers — lazy + best-effort. Detector is allowed to no-op if DB is
# unreachable so a temporary outage can't break the rest of the cron.
# ---------------------------------------------------------------------------
_db = None
_disabled = False


def _get_db():
    global _db, _disabled
    if _disabled:
        return None
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        _db = client[os.getenv("MONGO_DB", "cheetah")]
        _db.juggernaut_state.create_index([("date_et", ASCENDING)], unique=True)
        return _db
    except Exception as exc:
        log.warning("juggernaut: Mongo unavailable (%s) — disabling", exc)
        _disabled = True
        return None


def _now() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp())


def _today_key_et() -> str:
    """ET-aware date key so a juggernaut session maps to one trading day."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.now(tz=timezone.utc).date().isoformat()


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
def _watchlist_symbols() -> set[str]:
    """Watchlist is a JSON file managed by ``sepa.scanner``. We re-read on
    every cron tick so additions/removals take effect immediately — no
    daemon restart needed."""
    try:
        from sepa import scanner
        return {(x.get("symbol") or "").upper()
                for x in scanner.load_watchlist()
                if x.get("symbol")}
    except Exception as exc:
        log.warning("juggernaut: load_watchlist failed: %s", exc)
        return set()


def _latest_per_ticker(db, tickers: set[str]) -> dict[str, dict]:
    """For each watchlist ticker, fetch the most recent candidate_snapshot —
    regardless of whether it currently rates as a SEPA candidate. Watchlist
    names get evaluated independently of SEPA gating."""
    if not tickers:
        return {}
    pipeline = [
        {"$match": {"symbol": {"$in": list(tickers)}}},
        {"$sort": {"generated_at": -1}},
        {"$group": {"_id": "$symbol", "doc": {"$first": "$$ROOT"}}},
    ]
    out: dict[str, dict] = {}
    for row in db.candidate_snapshots.aggregate(pipeline):
        out[row["_id"]] = row["doc"]
    return out


def _historical(db, ticker: str, lookback_days: int) -> list[dict]:
    cutoff = _now() - lookback_days * 86400
    return list(db.candidate_snapshots.find(
        {"symbol": ticker, "generated_at": {"$gte": cutoff}}
    ).sort("generated_at", 1))


def _evaluate(db, ticker: str, latest: dict) -> Optional[dict]:
    """Apply the gate stack. Returns a rationale dict if the ticker qualifies,
    else None. Order matches the criteria comment at the top so a missing
    field on any gate skips cheaply."""
    vol = latest.get("volume") or {}
    ud_ratio = vol.get("up_down_vol_ratio")
    last_vol = vol.get("last_vol")
    avg_vol_50 = vol.get("avg_vol_50")
    day_pct = latest.get("day_change_pct")

    # Gate 2 — accumulation (up-volume dominates).
    if ud_ratio is None or ud_ratio < UD_VOL_MIN:
        return None

    # Gate 3 — today is engaged (institutional volume right now).
    today_mult: Optional[float] = None
    if last_vol and avg_vol_50:
        today_mult = last_vol / avg_vol_50
    if today_mult is None or today_mult < TODAY_VOL_MULT:
        return None

    # Gate 4 — momentum signal (any of three).
    hist = _historical(db, ticker, LOOKBACK_DAYS)
    momentum_reason: Optional[str] = None
    rs_delta = score_delta = 0
    if len(hist) >= 2:
        first_rs = hist[0].get("rs_rank") or 0
        last_rs  = hist[-1].get("rs_rank") or 0
        first_score = hist[0].get("score") or 0
        last_score  = hist[-1].get("score") or 0
        rs_delta = last_rs - first_rs
        score_delta = last_score - first_score
        if rs_delta >= RS_CLIMB_MIN:
            momentum_reason = f"RS {first_rs}→{last_rs} (+{rs_delta})"
        elif score_delta >= SCORE_CLIMB_MIN:
            momentum_reason = (
                f"score {first_score:.0f}→{last_score:.0f} "
                f"(+{score_delta:.0f})"
            )
    if (momentum_reason is None and day_pct is not None
            and day_pct >= DAY_PCT_BURST):
        momentum_reason = f"+{day_pct:.1f}% today"
    if momentum_reason is None:
        return None

    return {
        "ticker": ticker.upper(),
        "ud_ratio": round(float(ud_ratio), 2),
        "today_vol_mult": round(today_mult, 2),
        "momentum": momentum_reason,
        "rs_delta": rs_delta,
        "score_delta": round(score_delta, 1),
        "last_close": latest.get("last_close"),
        "day_change_pct": day_pct,
        "rating": latest.get("rating"),
        "score": latest.get("score"),
        "rs_rank": latest.get("rs_rank"),
    }


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------
def scan(*, force_push: bool = False, dry_run: bool = False) -> dict:
    """Run the detector once.

    Returns
    -------
    dict with:
      - ``ok``: bool
      - ``today_et``: ET date string for this session
      - ``juggernauts``: full current list of rationale dicts
      - ``new_today``: tickers that emerged on THIS tick (vs previously
        flagged tickers for the same date_et)
      - ``pushed``: 1 if a push notification was fired

    ``force_push=True`` fires a push even with no new emergences (used by
    the CLI ``--force`` flag and tests).
    ``dry_run=True`` skips the persisted-state update + push entirely.
    """
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db unavailable"}

    watch = _watchlist_symbols()
    if not watch:
        return {"ok": True, "today_et": _today_key_et(),
                "juggernauts": [], "new_today": [], "pushed": 0,
                "reason": "watchlist empty"}

    latest_per = _latest_per_ticker(db, watch)
    current: list[dict] = []
    for ticker in sorted(watch):
        latest = latest_per.get(ticker)
        if not latest:
            continue
        verdict = _evaluate(db, ticker, latest)
        if verdict:
            current.append(verdict)
    # Stable presentation order — biggest movers first (by abs day_change_pct
    # → up/down vol ratio → ticker for determinism).
    current.sort(
        key=lambda j: (
            -abs(j.get("day_change_pct") or 0),
            -(j.get("ud_ratio") or 0),
            j["ticker"],
        )
    )

    today = _today_key_et()
    state = db.juggernaut_state.find_one({"date_et": today}) or {}
    already: set[str] = set(state.get("tickers") or [])
    current_set: set[str] = {j["ticker"] for j in current}
    new_today = sorted(current_set - already)

    log.info("juggernaut: %d current, %d new (%s) on %s",
             len(current), len(new_today),
             ",".join(new_today) if new_today else "-",
             today)

    pushed = 0
    if not dry_run and (new_today or force_push):
        # Persist state BEFORE pushing — push failure must not cause a
        # second alert on the next run.
        db.juggernaut_state.update_one(
            {"date_et": today},
            {"$set": {
                "tickers": sorted(current_set | already),
                "updated_at": _now(),
            }},
            upsert=True,
        )
        if current:
            try:
                from push import hooks
                hooks.notify_juggernauts(
                    juggernauts=current,
                    new_today=new_today,
                    today_et=today,
                )
                pushed = 1
            except Exception as exc:
                log.warning("juggernaut push failed: %s", exc)

    return {
        "ok": True,
        "today_et": today,
        "juggernauts": current,
        "new_today": new_today,
        "pushed": pushed,
    }


def current_set(today_et: Optional[str] = None) -> list[str]:
    """Read-only — return the set of tickers already flagged today. Used by
    a future /api/sepa/juggernauts endpoint if surfaced in the UI."""
    db = _get_db()
    if db is None:
        return []
    state = db.juggernaut_state.find_one({"date_et": today_et or _today_key_et()})
    return sorted((state or {}).get("tickers") or [])
