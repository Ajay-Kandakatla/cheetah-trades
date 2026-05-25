"""Catalyst history — hourly snapshots, intraday timeline, stalled-list
detection, and multi-day accumulators.

Three independent feeds derived from the same Mongo snapshot history:

  1. INTRADAY TIMELINE
     Every hour during market hours we snapshot the current /catalysts/scan
     output (slimmed to key fields). On request we diff adjacent snapshots
     to surface:
       - new entries (tickers that just appeared on the list)
       - exits (tickers that dropped off)
       - chatter spikes (chatter_score jumped ≥15 points)
       - evidence jumps (evidence_score jumped ≥10 points)
       - quadrant transitions (PUMP_RISK → REAL etc.)
       - pump-phase transitions (BREAKOUT → FRENZY → DISTRIBUTION)

  2. STALE TRACKER
     Tickers that have been on the list for ≥N hours TODAY without their
     composite_score changing meaningfully. Two flavours:
       - stable_winners: holding REAL or OVERLOOKED state — sustained
         signal. Often the highest-conviction entries.
       - stalled_chatter: stuck in PUMP_RISK with no evidence appearing.
         Chatter without conversion = pump fading without follow-through.

  3. MULTI-DAY ACCUMULATORS
     Tiny stocks that have appeared in the catalyst scan on ≥3 distinct
     session-dates AND show positive Chaikin Money Flow over the last 10
     sessions (using supply_demand.accumulation). These are the sustained
     small-cap accumulation stories — not one-day pumps but sustained
     buying interest across days.

Snapshots are kept 14 days (cron-cleaned), which is more than enough for
both intraday and multi-day signals.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("catalysts.history")


def _coll():
    try:
        from pymongo import MongoClient, ASCENDING, DESCENDING
        url = os.getenv("MONGO_URL", "mongodb://mongo:27017")
        db = os.getenv("MONGO_DB", "cheetah")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        c = client[db]["catalysts_history"]
        c.create_index([("session_date", ASCENDING), ("snapshot_at", DESCENDING)])
        return c
    except Exception as exc:
        log.warning("history mongo unavailable: %s", exc)
        return None


def _et_session_date() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


# What we keep from each candidate per snapshot — small enough that we can
# store many snapshots without ballooning Mongo.
def _slim(c: dict) -> dict:
    pump = c.get("pump") or {}
    return {
        "ticker": c.get("ticker"),
        "company_name": c.get("company_name"),
        "price": c.get("price"),
        "change_pct": c.get("change_pct"),
        "volume_surge_ratio": c.get("volume_surge_ratio"),
        "market_cap": c.get("market_cap"),
        "composite_score": c.get("composite_score"),
        "chatter_score": c.get("chatter_score"),
        "evidence_score": c.get("evidence_score"),
        "quadrant": c.get("quadrant"),
        "pump_phase": pump.get("phase"),
        "pump_action": pump.get("action"),
    }


# --- 1. SNAPSHOT WRITE ---------------------------------------------------

def record_snapshot(scan_result: dict) -> Optional[str]:
    """Persist a slimmed snapshot of the current scan. Idempotent — if a
    snapshot already exists within the last 30 minutes, skip (avoids
    re-counting transitions when /catalysts/scan is hit twice quickly).

    Returns the ID of the inserted snapshot, or None if skipped.
    """
    coll = _coll()
    if coll is None:
        return None
    candidates = scan_result.get("candidates") or []
    if not candidates:
        return None
    try:
        # Skip if a recent snapshot already exists (debouncer)
        thirty_min_ago = datetime.now(timezone.utc) - timedelta(minutes=30)
        recent = coll.find_one({"snapshot_at": {"$gte": thirty_min_ago}}, sort=[("snapshot_at", -1)])
        if recent:
            return None

        result = coll.insert_one({
            "snapshot_at": datetime.now(timezone.utc),
            "session_date": _et_session_date(),
            "n_candidates": len(candidates),
            "tickers": [_slim(c) for c in candidates],
        })
        # Cleanup: keep last 14 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        coll.delete_many({"snapshot_at": {"$lt": cutoff}})
        return str(result.inserted_id)
    except Exception as exc:
        log.warning("snapshot write failed: %s", exc)
        return None


def get_session_snapshots(session_date: Optional[str] = None) -> list[dict]:
    """Return all snapshots for the given session, oldest first. Times are
    normalised to ISO strings for JSON serialisability."""
    coll = _coll()
    if coll is None:
        return []
    sd = session_date or _et_session_date()
    try:
        docs = list(coll.find({"session_date": sd}).sort("snapshot_at", 1))
        for d in docs:
            d["_id"] = str(d["_id"])
            ts = d.get("snapshot_at")
            if hasattr(ts, "isoformat"):
                d["snapshot_at"] = ts.isoformat()
        return docs
    except Exception as exc:
        log.warning("snapshot read failed: %s", exc)
        return []


# --- 2. INTRADAY TIMELINE -----------------------------------------------

def _diff_snapshots(prev: dict, cur: dict) -> Optional[dict]:
    """Compute deltas between two adjacent snapshots."""
    prev_by_t = {t["ticker"]: t for t in prev.get("tickers", []) if t.get("ticker")}
    cur_by_t = {t["ticker"]: t for t in cur.get("tickers", []) if t.get("ticker")}

    entered: list[dict] = []
    exited: list[dict] = []
    chatter_jumpers: list[dict] = []
    evidence_jumpers: list[dict] = []
    quadrant_transitions: list[dict] = []
    phase_transitions: list[dict] = []

    for t, cur_data in cur_by_t.items():
        prev_data = prev_by_t.get(t)
        if not prev_data:
            entered.append({**cur_data})
            continue

        prev_ch = prev_data.get("chatter_score") or 0
        cur_ch = cur_data.get("chatter_score") or 0
        if cur_ch - prev_ch >= 15:
            chatter_jumpers.append({
                "ticker": t,
                "company_name": cur_data.get("company_name"),
                "delta": round(cur_ch - prev_ch, 1),
                "from_score": round(prev_ch, 1),
                "to_score": round(cur_ch, 1),
                "change_pct": cur_data.get("change_pct"),
            })

        prev_ev = prev_data.get("evidence_score") or 0
        cur_ev = cur_data.get("evidence_score") or 0
        if cur_ev - prev_ev >= 10:
            evidence_jumpers.append({
                "ticker": t,
                "company_name": cur_data.get("company_name"),
                "delta": round(cur_ev - prev_ev, 1),
                "from_score": round(prev_ev, 1),
                "to_score": round(cur_ev, 1),
            })

        prev_q = prev_data.get("quadrant")
        cur_q = cur_data.get("quadrant")
        if prev_q != cur_q and prev_q and cur_q:
            quadrant_transitions.append({
                "ticker": t,
                "company_name": cur_data.get("company_name"),
                "from_quadrant": prev_q,
                "to_quadrant": cur_q,
            })

        prev_p = prev_data.get("pump_phase")
        cur_p = cur_data.get("pump_phase")
        if prev_p != cur_p and prev_p and cur_p and prev_p != "NONE" and cur_p != "NONE":
            phase_transitions.append({
                "ticker": t,
                "company_name": cur_data.get("company_name"),
                "from_phase": prev_p,
                "to_phase": cur_p,
            })

    for t, prev_data in prev_by_t.items():
        if t not in cur_by_t:
            exited.append({**prev_data})

    if not (entered or exited or chatter_jumpers or evidence_jumpers
            or quadrant_transitions or phase_transitions):
        return None

    return {
        "entered": entered,
        "exited": exited,
        "chatter_jumpers": chatter_jumpers,
        "evidence_jumpers": evidence_jumpers,
        "quadrant_transitions": quadrant_transitions,
        "phase_transitions": phase_transitions,
        "n_entered": len(entered),
        "n_exited": len(exited),
        "n_chatter_jumps": len(chatter_jumpers),
        "n_evidence_jumps": len(evidence_jumpers),
        "n_quadrant_transitions": len(quadrant_transitions),
        "n_phase_transitions": len(phase_transitions),
    }


def get_intraday_timeline(session_date: Optional[str] = None) -> dict:
    """Return hour-by-hour deltas across today's snapshots."""
    snaps = get_session_snapshots(session_date)
    if not snaps:
        return {
            "events": [],
            "session_date": session_date or _et_session_date(),
            "n_snapshots": 0,
        }

    events = []
    prev = None
    for snap in snaps:
        if prev is not None:
            delta = _diff_snapshots(prev, snap)
            if delta:
                events.append({
                    "from_at": prev.get("snapshot_at"),
                    "at": snap.get("snapshot_at"),
                    **delta,
                })
        prev = snap

    return {
        "session_date": snaps[0].get("session_date"),
        "n_snapshots": len(snaps),
        "first_snapshot_at": snaps[0].get("snapshot_at"),
        "last_snapshot_at": snaps[-1].get("snapshot_at"),
        "events": events,
    }


# --- 3. STALLED TICKERS --------------------------------------------------

def get_stalled(min_age_hours: float = 3.0,
                max_score_drift: float = 8.0,
                session_date: Optional[str] = None) -> dict:
    """Tickers in the latest snapshot that have been on the list for
    ≥min_age_hours TODAY with composite_score drift ≤ max_score_drift.

    Bucketed by quadrant:
      stable_winners   : REAL or OVERLOOKED — sustained high-quality signal
      stalled_chatter  : PUMP_RISK — chatter not converting to evidence
      ambient_dead     : DEAD — moves without follow-through
    """
    snaps = get_session_snapshots(session_date)
    if not snaps or len(snaps) < 2:
        return {
            "stable_winners": [],
            "stalled_chatter": [],
            "ambient_dead": [],
            "n_snapshots": len(snaps),
            "session_date": (session_date or _et_session_date()),
        }

    cutoff = datetime.now(timezone.utc) - timedelta(hours=min_age_hours)
    cur = snaps[-1]
    cur_by_t = {t["ticker"]: t for t in cur.get("tickers", []) if t.get("ticker")}

    stable_winners = []
    stalled_chatter = []
    ambient_dead = []

    for ticker, cur_data in cur_by_t.items():
        # Find earliest appearance today
        earliest_idx = None
        earliest_data = None
        for i, snap in enumerate(snaps):
            for t_data in snap.get("tickers", []):
                if t_data.get("ticker") == ticker:
                    earliest_idx = i
                    earliest_data = t_data
                    break
            if earliest_idx is not None:
                break

        if earliest_idx is None or earliest_idx == len(snaps) - 1:
            continue  # only in current snap → not yet stalled

        # Time delta
        first_ts = snaps[earliest_idx].get("snapshot_at")
        if isinstance(first_ts, str):
            try:
                first_dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            except Exception:
                continue
        elif isinstance(first_ts, datetime):
            first_dt = first_ts if first_ts.tzinfo else first_ts.replace(tzinfo=timezone.utc)
        else:
            continue

        if first_dt > cutoff:
            continue  # not old enough

        # Stability: composite_score didn't move much
        first_comp = (earliest_data or {}).get("composite_score") or 0
        cur_comp = cur_data.get("composite_score") or 0
        drift = abs(cur_comp - first_comp)
        if drift > max_score_drift:
            continue

        hours_old = (datetime.now(timezone.utc) - first_dt).total_seconds() / 3600
        record = {
            "ticker": ticker,
            "company_name": cur_data.get("company_name"),
            "first_seen_at": first_dt.isoformat(),
            "hours_on_list": round(hours_old, 1),
            "composite_score": round(cur_comp, 1),
            "score_drift": round(drift, 1),
            "quadrant": cur_data.get("quadrant"),
            "change_pct": cur_data.get("change_pct"),
            "chatter_score": round(cur_data.get("chatter_score") or 0, 1),
            "evidence_score": round(cur_data.get("evidence_score") or 0, 1),
            "volume_surge_ratio": cur_data.get("volume_surge_ratio"),
        }

        quad = cur_data.get("quadrant") or ""
        if quad in ("REAL", "OVERLOOKED"):
            stable_winners.append(record)
        elif quad == "PUMP_RISK":
            stalled_chatter.append(record)
        elif quad == "DEAD":
            ambient_dead.append(record)

    stable_winners.sort(key=lambda x: -x["hours_on_list"])
    stalled_chatter.sort(key=lambda x: -x["hours_on_list"])
    ambient_dead.sort(key=lambda x: -x["hours_on_list"])

    return {
        "session_date": cur.get("session_date"),
        "min_age_hours": min_age_hours,
        "stable_winners": stable_winners,
        "stalled_chatter": stalled_chatter,
        "ambient_dead": ambient_dead,
        "n_snapshots": len(snaps),
    }


# --- 4. MULTI-DAY ACCUMULATORS ------------------------------------------

def get_multi_day_accumulators(min_session_appearances: int = 3,
                                lookback_days: int = 10,
                                min_accumulation_score: float = 30.0) -> dict:
    """Find tiny stocks that have:
      - appeared in catalyst snapshots on ≥N distinct session_dates
      - shown positive Chaikin Money Flow (≥30) over recent sessions

    These are the sustained small-cap accumulation stories — names where
    chatter / catalyst recurs across multiple days AND the price/volume
    pattern confirms accumulation behaviour. The intersection of "this
    keeps coming up" + "smart money is positioning" is the signal.

    Returns ranked list with each ticker's:
      - n_session_dates_seen (sticking power across days)
      - cmf_score (Chaikin Money Flow, -100 to +100)
      - accumulation_label
      - latest catalyst metadata (composite_score, quadrant)
    """
    coll = _coll()
    if coll is None:
        return {"accumulators": [], "n_universe": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    try:
        # Aggregate: for each ticker, count distinct session_dates seen
        pipeline = [
            {"$match": {"snapshot_at": {"$gte": cutoff}}},
            {"$unwind": "$tickers"},
            {"$group": {
                "_id": "$tickers.ticker",
                "n_session_dates": {"$addToSet": "$session_date"},
                "latest_data": {"$last": "$tickers"},
                "first_seen": {"$min": "$snapshot_at"},
                "last_seen": {"$max": "$snapshot_at"},
            }},
            {"$project": {
                "ticker": "$_id",
                "n_session_dates": {"$size": "$n_session_dates"},
                "latest_data": 1,
                "first_seen": 1,
                "last_seen": 1,
            }},
            {"$match": {"n_session_dates": {"$gte": min_session_appearances}}},
            {"$sort": {"n_session_dates": -1}},
        ]
        rows = list(coll.aggregate(pipeline))
    except Exception as exc:
        log.warning("multi-day aggregate failed: %s", exc)
        return {"accumulators": [], "n_universe": 0}

    if not rows:
        return {"accumulators": [], "n_universe": 0}

    universe = [r["ticker"] for r in rows if r.get("ticker")]

    # Pull Chaikin Money Flow scores in one batch
    accum_scores: dict = {}
    try:
        from supply_demand.accumulation import get_accumulation_scores
        accum_scores = get_accumulation_scores(universe)
    except Exception as exc:
        log.warning("accumulation lookup failed: %s", exc)

    # Build output, filter to those meeting min_accumulation_score
    out = []
    for r in rows:
        t = r.get("ticker")
        if not t:
            continue
        score = accum_scores.get(t.upper())
        if not score:
            continue
        if (score.get("score") or 0) < min_accumulation_score:
            continue

        latest = r.get("latest_data") or {}
        first_seen = r.get("first_seen")
        last_seen = r.get("last_seen")
        if hasattr(first_seen, "isoformat"):
            first_seen = first_seen.isoformat()
        if hasattr(last_seen, "isoformat"):
            last_seen = last_seen.isoformat()

        out.append({
            "ticker": t,
            "company_name": latest.get("company_name"),
            "n_session_dates_seen": r.get("n_session_dates"),
            "first_seen_at": first_seen,
            "last_seen_at": last_seen,
            "accumulation_score": score.get("score"),
            "accumulation_label": score.get("label"),
            "cmf": score.get("cmf"),
            "up_down_vol_ratio": score.get("up_down_vol_ratio"),
            "close_position_5d": score.get("close_position_5d"),
            "n_days_data": score.get("n_days"),
            # latest catalyst metadata
            "latest_composite_score": latest.get("composite_score"),
            "latest_quadrant": latest.get("quadrant"),
            "latest_change_pct": latest.get("change_pct"),
            "latest_volume_surge": latest.get("volume_surge_ratio"),
            "market_cap": latest.get("market_cap"),
            "price": latest.get("price"),
        })

    # Rank: prioritise (sessions_seen × accumulation_score)
    out.sort(key=lambda x: (
        -(x["n_session_dates_seen"] or 0),
        -(x["accumulation_score"] or 0),
    ))

    return {
        "accumulators": out,
        "n_universe": len(universe),
        "n_with_strong_accum": len(out),
        "min_session_appearances": min_session_appearances,
        "lookback_days": lookback_days,
        "min_accumulation_score": min_accumulation_score,
    }


__all__ = [
    "record_snapshot",
    "get_session_snapshots",
    "get_intraday_timeline",
    "get_stalled",
    "get_multi_day_accumulators",
]
