"""MongoDB-backed scan history.

Persists every scan run + per-candidate snapshot so historical queries
("AAPL's score over the last 30 days", "what was the candidate list on
2026-04-20?") don't need to re-run the scan or re-hit the price API.

Connection is configured via MONGO_URL (default: mongodb://localhost:27017).
If Mongo is unavailable, all writes/reads are no-ops — the rest of the app
keeps working off latest.json.

Collections
-----------
scan_runs           one document per scan
  _id, generated_at (epoch), generated_at_iso, date_et,
  market_context, universe_size, analyzed, candidate_count,
  duration_sec, has_catalyst

candidate_snapshots one document per (scan, symbol)
  _id, scan_run_id, generated_at, date_et, symbol,
  score, rating, rs_rank, stage, trend (dict), vcp (dict),
  entry_setup (dict), fundamentals (dict|null), catalyst (dict|null),
  insider (dict|null)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

log = logging.getLogger("sepa.history")

_client = None
_db = None
_disabled = False
_DB_NAME = os.getenv("MONGO_DB", "cheetah")


def _eastern_date(epoch: int) -> str:
    """Return YYYY-MM-DD in US Eastern (close enough — we use fixed -05:00).
    The scan timestamp is what matters for "yesterday's predictions"."""
    et = datetime.fromtimestamp(epoch, tz=timezone(timedelta(hours=-5)))
    return et.strftime("%Y-%m-%d")


def _get_db():
    global _client, _db, _disabled
    if _disabled:
        return None
    if _db is not None:
        return _db
    try:
        from pymongo import MongoClient, ASCENDING, DESCENDING
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        _client = MongoClient(url, serverSelectionTimeoutMS=2000)
        _client.admin.command("ping")
        _db = _client[_DB_NAME]
        _db.scan_runs.create_index([("generated_at", DESCENDING)])
        _db.scan_runs.create_index([("date_et", ASCENDING)])
        _db.candidate_snapshots.create_index(
            [("symbol", ASCENDING), ("generated_at", DESCENDING)]
        )
        _db.candidate_snapshots.create_index([("scan_run_id", ASCENDING)])
        _db.candidate_snapshots.create_index([("date_et", ASCENDING)])
        log.info("history: connected to %s/%s", url, _DB_NAME)
        return _db
    except Exception as exc:
        log.warning("history: Mongo unavailable (%s) — disabling persistence", exc)
        _disabled = True
        return None


def write_scan(payload: dict) -> Optional[str]:
    """Insert a scan_runs doc + N candidate_snapshots. Returns scan_run_id or None."""
    db = _get_db()
    if db is None:
        return None
    try:
        ts = int(payload.get("generated_at") or 0)
        date_et = _eastern_date(ts) if ts else None
        run_doc = {
            "generated_at": ts,
            "generated_at_iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None,
            "date_et": date_et,
            "market_context": payload.get("market_context"),
            "universe_size": payload.get("universe_size"),
            "analyzed": payload.get("analyzed"),
            "candidate_count": payload.get("candidate_count"),
            "duration_sec": payload.get("duration_sec"),
            "has_catalyst": any(
                (c or {}).get("catalyst") is not None
                for c in (payload.get("candidates") or [])
            ),
        }
        run_id = db.scan_runs.insert_one(run_doc).inserted_id

        rows = payload.get("all_results") or payload.get("candidates") or []
        if rows:
            docs = []
            for r in rows:
                docs.append({
                    "scan_run_id": run_id,
                    "generated_at": ts,
                    "date_et": date_et,
                    "symbol": r.get("symbol"),
                    "score": r.get("score"),
                    "rating": r.get("rating"),
                    "rs_rank": r.get("rs_rank"),
                    "stage": (r.get("stage") or {}).get("stage") if isinstance(r.get("stage"), dict) else r.get("stage"),
                    "stage_label": (r.get("stage") or {}).get("label") if isinstance(r.get("stage"), dict) else None,
                    "trend": r.get("trend"),
                    "vcp": r.get("vcp"),
                    "entry_setup": r.get("entry_setup"),
                    "fundamentals": r.get("fundamentals"),
                    "catalyst": r.get("catalyst"),
                    "insider": r.get("insider"),
                    "adr_pct": r.get("adr_pct"),
                })
            db.candidate_snapshots.insert_many(docs, ordered=False)
        log.info("history: persisted scan run %s with %d snapshots", run_id, len(rows))
        return str(run_id)
    except Exception as exc:
        log.warning("history: write failed: %s", exc)
        return None


def _strip_id(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if doc and "scan_run_id" in doc:
        doc["scan_run_id"] = str(doc["scan_run_id"])
    return doc


def get_symbol_history(symbol: str, days: int = 30) -> list[dict]:
    """Trajectory of one symbol over the last `days` days."""
    db = _get_db()
    if db is None:
        return []
    cutoff = int((datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp())
    cur = db.candidate_snapshots.find(
        {"symbol": symbol.upper(), "generated_at": {"$gte": cutoff}},
        projection={
            "generated_at": 1, "date_et": 1, "symbol": 1, "score": 1,
            "rating": 1, "rs_rank": 1, "stage": 1, "stage_label": 1,
            "entry_setup": 1, "adr_pct": 1,
        },
    ).sort("generated_at", -1).limit(500)
    return [_strip_id(d) for d in cur]


def get_recent_runs(limit: int = 30) -> list[dict]:
    db = _get_db()
    if db is None:
        return []
    cur = db.scan_runs.find().sort("generated_at", -1).limit(limit)
    return [_strip_id(d) for d in cur]


def get_scan_by_date(date_et: str) -> Optional[dict]:
    """Return the most recent scan run from a given Eastern date, plus its candidates."""
    db = _get_db()
    if db is None:
        return None
    run = db.scan_runs.find_one(
        {"date_et": date_et}, sort=[("generated_at", -1)]
    )
    if not run:
        return None
    snapshots = list(db.candidate_snapshots.find({"scan_run_id": run["_id"]}))
    run = _strip_id(run)
    run["candidates"] = [_strip_id(s) for s in snapshots]
    return run


def diff_dates(from_date: str, to_date: str) -> dict:
    """What changed between two scan dates? entered/exited/score deltas."""
    a = get_scan_by_date(from_date) or {"candidates": []}
    b = get_scan_by_date(to_date) or {"candidates": []}
    a_map = {c["symbol"]: c for c in a["candidates"]}
    b_map = {c["symbol"]: c for c in b["candidates"]}

    def _is_candidate(c):
        return c.get("rating") in ("STRONG_BUY", "BUY", "WATCH")

    a_set = {s for s, c in a_map.items() if _is_candidate(c)}
    b_set = {s for s, c in b_map.items() if _is_candidate(c)}
    entered = sorted(b_set - a_set)
    exited = sorted(a_set - b_set)
    common = a_set & b_set
    deltas = []
    for s in common:
        d = round((b_map[s].get("score") or 0) - (a_map[s].get("score") or 0), 1)
        if abs(d) >= 0.1:
            deltas.append({"symbol": s, "delta": d,
                           "from": a_map[s].get("score"), "to": b_map[s].get("score")})
    deltas.sort(key=lambda x: -abs(x["delta"]))
    return {
        "from_date": from_date,
        "to_date": to_date,
        "entered": entered,
        "exited": exited,
        "score_deltas": deltas[:50],
    }
