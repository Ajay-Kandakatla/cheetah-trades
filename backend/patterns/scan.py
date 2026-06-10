"""On-demand pattern scan — the "full scan button" engine.

Runs the pattern detectors across the SEPA universe (the latest scan's symbols,
so every hit carries its SEPA context — RS rank, stage, candidate/buyable) using
the price_cache daily frames (no provider calls). Background thread + a polled
progress status, results persisted to Mongo `patterns_scan` so the page loads
instantly afterward.

Two scopes (Ajay 2026-06-09: "a chart pattern analysis to make a decision
besides the SEPA qualifications and VCP and volume"):
- "universe": hits-only sweep of every cached chart (the original mode).
- "qualifiers": EVERY SEPA qualifier gets a verdict row — the Bulkowski
  pattern(s) it matches (confirmed or forming), recent candle reads, or an
  explicit "no pattern". No-match is an answer too; that's the point.

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
_STATE: dict = {"running": False, "scope": "universe", "done": 0, "total": 0,
                "started_at": 0, "finished_at": 0, "error": None}


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


def _verdict_for_symbol(sym: str, ctx: dict) -> dict:
    """One qualifier's full verdict — every detector's answer (match or not),
    historical pattern counts on this chart, and the recent candle reads.
    Always returns a row: "no pattern" is an answer, not an omission."""
    from sepa import prices
    from . import candles_daily
    row: dict = {"symbol": sym, "sepa": ctx or {}, "matches": [],
                 "historical": {}, "candles": None, "no_match": True}
    try:
        df = prices.load_prices(sym)
    except Exception:
        df = None
    if df is None or len(df) < 80:
        row["error"] = "no usable daily frame"
        return row
    for name, fn in detector.DETECTORS.items():
        try:
            res = fn(df)
        except Exception as exc:
            log.debug("detector %s failed on %s: %s", name, sym, exc)
            continue
        for p in res.get("fresh", []):
            row["matches"].append({**p, "symbol": sym})
        n_hist = len(res.get("historical_confirms", []))
        if n_hist:
            row["historical"][name] = n_hist
    try:
        row["candles"] = candles_daily.read_daily(df)
    except Exception as exc:
        log.debug("candle read failed on %s: %s", sym, exc)
    has_formation = bool((row["candles"] or {}).get("formations"))
    row["no_match"] = not row["matches"] and not has_formation
    row["matches"].sort(key=lambda p: (0 if p["status"] == "confirmed" else 1,
                                       p.get("bars_since_confirm", 99),
                                       p.get("to_confirm_pct", 99)))
    # One verdict per pattern kind — the best (freshest-confirmed) instance.
    seen_kind: set = set()
    row["matches"] = [m for m in row["matches"]
                      if not (m["pattern"] in seen_kind or seen_kind.add(m["pattern"]))]
    return row


def _run_qualifier_scan() -> None:
    try:
        _, ctx = _universe_with_context()
        quals = {s: c for s, c in ctx.items() if c.get("is_candidate")}
        with _LOCK:
            _STATE.update(total=len(quals), done=0, error=None)
        if not quals:
            raise RuntimeError("no qualifiers in the latest SEPA scan — run a SEPA scan first")

        def work(item):
            sym, c = item
            r = _verdict_for_symbol(sym, c)
            with _LOCK:
                _STATE["done"] += 1
            return r

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            verdicts = [r for r in ex.map(work, sorted(quals.items())) if r]

        # Confirmed matches first, then forming, then candle-only, then no-match;
        # inside each bucket the higher RS rank first.
        def bucket(v):
            if any(p["status"] == "confirmed" for p in v["matches"]):
                return 0
            if v["matches"]:
                return 1
            if not v["no_match"]:
                return 2
            return 3
        verdicts.sort(key=lambda v: (bucket(v), -((v.get("sepa") or {}).get("rs_rank") or 0)))

        payload = {
            "generated_at": int(time.time()),
            "scope": "qualifiers",
            "n_symbols": len(verdicts),
            "n_matched": sum(1 for v in verdicts if v["matches"]),
            "n_candle_only": sum(1 for v in verdicts if not v["matches"] and not v["no_match"]),
            "n_no_match": sum(1 for v in verdicts if v["no_match"]),
            "verdicts": verdicts,
            "disclaimer": (
                "Every SEPA qualifier, answered: the Bulkowski pattern(s) its daily "
                "chart matches right now (confirmed or forming), recent candle "
                "formations, or — most of the time — no pattern at all. Geometry is "
                "descriptive, not predictive; candle formations have NO standalone "
                "academic support (Marshall 2006; Horton 2009). A decision input "
                "beside SEPA, VCP and volume — not advice."),
        }
        coll = _coll()
        if coll is not None:
            try:
                coll.update_one({"_id": "qualifier_verdicts"}, {"$set": payload}, upsert=True)
            except Exception as exc:
                log.warning("qualifier verdicts persist failed: %s", exc)
        with _LOCK:
            _STATE.update(running=False, finished_at=int(time.time()))
        log.info("qualifier verdict scan done: %d qualifiers, %d matched",
                 len(verdicts), payload["n_matched"])
    except Exception as exc:
        log.exception("qualifier verdict scan failed")
        with _LOCK:
            _STATE.update(running=False, error=str(exc), finished_at=int(time.time()))


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


def start_scan(scope: str = "universe") -> dict:
    scope = scope if scope in ("universe", "qualifiers") else "universe"
    with _LOCK:
        if _STATE["running"]:
            return {**_STATE, "note": "already running"}
        _STATE.update(running=True, scope=scope, done=0, total=0, error=None,
                      started_at=int(time.time()), finished_at=0)
    target = _run_qualifier_scan if scope == "qualifiers" else _run_scan
    t = threading.Thread(target=target, name=f"patterns-scan-{scope}", daemon=True)
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


def latest_qualifiers() -> dict:
    coll = _coll()
    doc = coll.find_one({"_id": "qualifier_verdicts"}) if coll is not None else None
    if not doc:
        return {"verdicts": [], "n_symbols": 0, "generated_at": 0,
                "note": "No qualifier verdict scan yet — hit Scan Qualifiers."}
    doc.pop("_id", None)
    return doc
