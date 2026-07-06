"""Order-flow signal ledger — the forward track record for the Tape verdict.

Ajay heard "these strategies hit ~70% of the time" in a WhatsApp group
(2026-07-06). We don't assume that — we measure OUR implementation:

  1. RECORD  — every computed snapshot appends one observation per
               (symbol, ET date, verdict). _id encodes identity, so
               re-scans never double-count. ALL three verdicts are
               recorded — BUY needs WAIT/AVOID as the control group.
  2. RESOLVE — daily cron (17:10 ET, backend/crontab) grades against the
               daily close: fwd_1d as soon as T+1 exists, fwd_5d added
               when T+5 exists. hit = next-day close in the verdict's
               direction (BUY: up, AVOID: down; WAIT records returns only).
  3. ACCURACY — GET /orderflow/accuracy aggregates the graded ledger.

Same honesty contract as patterns/history.py: gross close-to-close, no
costs; entry = last tape price when the verdict was computed; small n early
means wide error bars — the API says so out loud.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import pandas as pd

log = logging.getLogger("orderflow.history")

HORIZON_1D = 1
HORIZON_5D = 5


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].orderflow_observations
    except Exception:
        return None


# ── 1. RECORD ────────────────────────────────────────────────────────────────
def record(snap: dict) -> bool:
    """One observation per (symbol, et_date, verdict). Idempotent."""
    coll = _coll()
    if coll is None or not snap.get("symbol") or not snap.get("verdict"):
        return False
    sym = snap["symbol"].upper()
    d = snap.get("et_date")
    v = snap["verdict"]
    doc_id = f"{sym}:{d}:{v}"
    doc = {"symbol": sym, "et_date": d, "verdict": v,
           "entry_price": snap.get("last_price"),
           "checks_passed": snap.get("checks_passed"),
           "recorded_at": int(time.time()), "resolved": False}
    try:
        r = coll.update_one({"_id": doc_id}, {"$setOnInsert": doc}, upsert=True)
        return r.upserted_id is not None
    except Exception as exc:
        log.debug("orderflow record failed %s: %s", doc_id, exc)
        return False


# ── 2. RESOLVE ───────────────────────────────────────────────────────────────
def grade(df: pd.DataFrame, obs: dict) -> Optional[dict]:
    """Forward returns vs the observation day's close. Pure — unit-tested.

    Returns None while T+1 isn't on the tape yet. fwd_5d is None until T+5
    exists (a later pass fills it in).
    """
    try:
        ts = pd.Timestamp(obs["et_date"])
        k = int(df.index.searchsorted(ts, side="right")) - 1
    except Exception:
        return None
    if k < 0 or k + HORIZON_1D >= len(df):
        return None
    closes = df["close"].to_numpy(dtype=float)
    entry = float(obs.get("entry_price") or closes[k])
    if entry <= 0:
        return None
    fwd_1d = round((closes[k + HORIZON_1D] / entry - 1) * 100, 2)
    fwd_5d = (round((closes[k + HORIZON_5D] / entry - 1) * 100, 2)
              if k + HORIZON_5D < len(df) else None)
    v = obs.get("verdict")
    hit_1d = bool(fwd_1d > 0) if v == "BUY" else (bool(fwd_1d < 0) if v == "AVOID" else None)
    hit_5d = None
    if fwd_5d is not None:
        hit_5d = bool(fwd_5d > 0) if v == "BUY" else (bool(fwd_5d < 0) if v == "AVOID" else None)
    return {"fwd_1d_pct": fwd_1d, "fwd_5d_pct": fwd_5d,
            "hit_1d": hit_1d, "hit_5d": hit_5d}


def resolve_pending(limit: int = 2000) -> dict:
    """Grade unresolved observations + backfill missing fwd_5d on resolved ones."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "no mongo"}
    from sepa import prices
    frames: dict = {}

    def _frame(sym: str):
        if sym not in frames:
            try:
                frames[sym] = prices.load_prices(sym)
            except Exception:
                frames[sym] = None
        return frames[sym]

    n_resolved = n_checked = n_backfilled = 0
    for obs in coll.find({"resolved": False}).limit(limit):
        n_checked += 1
        df = _frame(obs["symbol"])
        if df is None or len(df) < 10:
            continue
        res = grade(df, obs)
        if res is None:
            continue
        coll.update_one({"_id": obs["_id"]},
                        {"$set": {**res, "resolved": True,
                                  "resolved_at": int(time.time())}})
        n_resolved += 1
    for obs in coll.find({"resolved": True, "fwd_5d_pct": None}).limit(limit):
        df = _frame(obs["symbol"])
        if df is None:
            continue
        res = grade(df, obs)
        if res and res.get("fwd_5d_pct") is not None:
            coll.update_one({"_id": obs["_id"]},
                            {"$set": {"fwd_5d_pct": res["fwd_5d_pct"],
                                      "hit_5d": res["hit_5d"]}})
            n_backfilled += 1
    log.info("orderflow ledger: %d/%d resolved, %d fwd_5d backfilled",
             n_resolved, n_checked, n_backfilled)
    return {"ok": True, "checked": n_checked, "resolved": n_resolved,
            "backfilled_5d": n_backfilled}


# ── 3. ACCURACY ──────────────────────────────────────────────────────────────
def _pct(part: int, whole: int) -> Optional[float]:
    return round(part / whole * 100, 1) if whole else None


def accuracy() -> dict:
    """The measured record per verdict — the answer to "is the 70% claim real?"."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "no mongo"}
    slots: dict = {}
    pending = 0
    earliest = None
    for obs in coll.find({}):
        if not obs.get("resolved"):
            pending += 1
            continue
        earliest = min(earliest or obs["et_date"], obs["et_date"])
        s = slots.setdefault(obs["verdict"], {
            "n": 0, "hit_1d": 0, "graded_1d": 0, "fwd_1d": [],
            "hit_5d": 0, "graded_5d": 0, "fwd_5d": []})
        s["n"] += 1
        if obs.get("hit_1d") is not None:
            s["graded_1d"] += 1
            s["hit_1d"] += 1 if obs["hit_1d"] else 0
        if obs.get("fwd_1d_pct") is not None:
            s["fwd_1d"].append(obs["fwd_1d_pct"])
        if obs.get("hit_5d") is not None:
            s["graded_5d"] += 1
            s["hit_5d"] += 1 if obs["hit_5d"] else 0
        if obs.get("fwd_5d_pct") is not None:
            s["fwd_5d"].append(obs["fwd_5d_pct"])

    out = {}
    for v, s in slots.items():
        f1, f5 = sorted(s["fwd_1d"]), sorted(s["fwd_5d"])
        out[v] = {"n": s["n"],
                  "hit_1d_pct": _pct(s["hit_1d"], s["graded_1d"]),
                  "median_fwd_1d_pct": f1[len(f1) // 2] if f1 else None,
                  "n_5d": len(f5),
                  "hit_5d_pct": _pct(s["hit_5d"], s["graded_5d"]),
                  "median_fwd_5d_pct": f5[len(f5) // 2] if f5 else None}
    return {
        "ok": True, "generated_at": int(time.time()),
        "verdicts": out, "pending": pending, "since": earliest,
        "conventions": {
            "entry": "last tape price when the verdict was computed",
            "hit": "close in the verdict's direction at T+1 / T+5 (BUY up, AVOID down; WAIT tracked, not scored)",
        },
        "disclaimer": (
            "OUR live forward record for the Tape verdict — every scan graded later "
            "against the real closes. Gross, no costs; small n early means wide error "
            "bars. A percentage here is a measured frequency, not a promise — and not "
            "the WhatsApp group's number."),
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    r = resolve_pending()
    log.info("ORDERFLOW-LEDGER: %s", r)
    sys.exit(0 if r.get("ok") else 1)
