"""On-demand pattern scan — the "full scan button" engine.

Runs the pattern detectors across the SEPA universe (the latest scan's symbols,
so every hit carries its SEPA context — RS rank, stage, candidate/buyable) using
the price_cache daily frames (no provider calls). Background thread + a polled
progress status, results persisted to Mongo `patterns_scan` so the page loads
instantly afterward.

SELF-VALIDATION in the same pass: every historically CONFIRMED pattern in the
~2y frames is measured (+21-bar return and max gain), aggregated per pattern,
and shown beside the practitioner base rates — our universe's own record, not a
book's. Educational, not advice.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from . import detector

log = logging.getLogger("patterns.scan")

MAX_WORKERS = 8
_LOCK = threading.Lock()
_STATE: dict = {"running": False, "done": 0, "total": 0, "started_at": 0,
                "finished_at": 0, "error": None}


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].patterns_scan
    except Exception:
        return None


def _universe_with_context() -> tuple:
    """(symbols, context_by_symbol) from the latest SEPA scan; fallback to the
    universe loader with empty context."""
    ctx: dict = {}
    try:
        from sepa import scanner
        rows = (scanner.load_latest() or {}).get("all_results") or []
        for r in rows:
            sym = r.get("symbol")
            if not sym or r.get("is_etf"):
                continue
            ctx[sym] = {
                "rs_rank": r.get("rs_rank"), "score": r.get("score"),
                "stage": (r.get("stage") or {}).get("stage"),
                "is_candidate": bool(r.get("is_candidate")),
                "is_buyable": bool(r.get("is_buyable")),
            }
        if ctx:
            return list(ctx.keys()), ctx
    except Exception as exc:
        log.warning("patterns universe from scan failed: %s", exc)
    try:
        from sepa.universe import load_universe
        return [s for s in load_universe("russell1000") or []], {}
    except Exception:
        return [], {}


def _scan_symbol(sym: str) -> Optional[dict]:
    from sepa import prices
    try:
        df = prices.load_prices(sym)
    except Exception:
        return None
    if df is None or len(df) < 80:
        return None
    found, confirms = [], {}
    for name, fn in detector.DETECTORS.items():
        try:
            res = fn(df)
        except Exception as exc:
            log.debug("detector %s failed on %s: %s", name, sym, exc)
            continue
        for p in res.get("fresh", []):
            found.append({**p, "symbol": sym})
        hist = res.get("historical_confirms", [])
        if hist:
            confirms[name] = detector.measure_outcomes(df, hist)
    if not found and not confirms:
        return None
    return {"symbol": sym, "found": found, "outcomes": confirms}


def _aggregate_validation(outcome_lists: dict) -> dict:
    out = {}
    for pattern, events in outcome_lists.items():
        if not events:
            continue
        fwd = sorted(e["fwd_pct"] for e in events)
        gains = sorted(e["max_gain_pct"] for e in events)
        n = len(fwd)
        out[pattern] = {
            "n": n,
            "pct_positive_21d": round(sum(1 for x in fwd if x > 0) / n * 100, 1),
            "median_fwd_21d_pct": round(fwd[n // 2], 2),
            "median_max_gain_21d_pct": round(gains[n // 2], 2),
        }
    return out


def _run_scan() -> None:
    try:
        symbols, ctx = _universe_with_context()
        with _LOCK:
            _STATE.update(total=len(symbols), done=0, error=None)
        if not symbols:
            raise RuntimeError("no universe — run a SEPA scan first")

        all_found: list = []
        outcome_lists: dict = {}

        def work(sym):
            r = _scan_symbol(sym)
            with _LOCK:
                _STATE["done"] += 1
            return r

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            for r in ex.map(work, symbols):
                if not r:
                    continue
                for p in r["found"]:
                    p["sepa"] = ctx.get(p["symbol"]) or {}
                    all_found.append(p)
                for pattern, events in r["outcomes"].items():
                    outcome_lists.setdefault(pattern, []).extend(events)

        # Confirmed-and-fresh first; inside each, SEPA candidates by RS rank.
        all_found.sort(key=lambda p: (
            0 if p["status"] == "confirmed" else 1,
            0 if (p.get("sepa") or {}).get("is_candidate") else 1,
            -((p.get("sepa") or {}).get("rs_rank") or 0),
        ))

        payload = {
            "generated_at": int(time.time()),
            "symbols_scanned": len(symbols),
            "n_found": len(all_found),
            "results": all_found[:200],
            "validation": _aggregate_validation(outcome_lists),
            "validation_note": (
                "OUR universe's measured outcomes: every historically CONFIRMED "
                "pattern in the scanned ~2y daily frames, +21-bar close return and "
                "max gain. Gross price moves, no costs — context, not a promise."),
            "disclaimer": (
                "Detected geometry with a confirmation level — descriptive, not a "
                "prediction. Practitioner base rates (Bulkowski) are daily-bar, "
                "no-cost statistics; the academic record (Lo-Mamaysky-Wang 2000) "
                "supports informational content, not guaranteed profitability. "
                "Educational, not advice."),
        }
        coll = _coll()
        if coll is not None:
            try:
                coll.update_one({"_id": "latest"}, {"$set": payload}, upsert=True)
            except Exception as exc:
                log.warning("patterns persist failed: %s", exc)
        with _LOCK:
            _STATE.update(running=False, finished_at=int(time.time()))
        log.info("patterns scan done: %d symbols, %d found", len(symbols), len(all_found))
    except Exception as exc:
        log.exception("patterns scan failed")
        with _LOCK:
            _STATE.update(running=False, error=str(exc), finished_at=int(time.time()))


def start_scan() -> dict:
    with _LOCK:
        if _STATE["running"]:
            return {**_STATE, "note": "already running"}
        _STATE.update(running=True, done=0, total=0, error=None,
                      started_at=int(time.time()), finished_at=0)
    t = threading.Thread(target=_run_scan, name="patterns-scan", daemon=True)
    t.start()
    return dict(_STATE)


def status() -> dict:
    with _LOCK:
        return dict(_STATE)


def latest() -> dict:
    coll = _coll()
    doc = coll.find_one({"_id": "latest"}) if coll is not None else None
    if not doc:
        return {"results": [], "n_found": 0, "generated_at": 0,
                "note": "No pattern scan yet — hit Scan Patterns."}
    doc.pop("_id", None)
    return doc
