"""Pattern observation ledger — the forward track record (Ajay 2026-06-10:
"I want this pattern data stored to review later if they are accurate or not
on the long run, like we do the leaderboard for ranking… I will ask you for
accuracy and probability of success rate on our patterns").

Three pieces, mirroring the leaderboard-history pattern:
  1. RECORD — every qualifier verdict scan appends observations to Mongo
     `pattern_observations`. One doc per EVENT, not per scan: a confirmation
     is keyed by its confirm date, a forming pattern by its line, a candle
     formation by its day — re-scans never double-count.
  2. RESOLVE — daily cron grades observations against what the tape actually
     did: confirmed patterns → did price reach the measure-rule target before
     the stop within 21 bars (+ the +21-bar return); forming → did it go on
     to CONFIRM within 21 bars or break the stop first; candle reads → was the
     next-5-bar move in the read's direction. Ambiguous same-bar target+stop
     counts as STOP (pessimistic). Entry convention: the close on the day the
     system flagged it — what a reader of the page could actually have done.
  3. ACCURACY — aggregates the resolved ledger per pattern/status/formation.

Honesty contract: gross close-to-close moves, no costs; the 21/5-bar horizons
are CONVENTIONS (matching the retrospective self-validation); small n early
means wide error bars — the API says all of this out loud.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import pandas as pd

from . import detector

log = logging.getLogger("patterns.history")

PATTERN_HORIZON = detector.VALIDATION_HORIZON   # 21 bars — same convention as self-validation
CANDLE_HORIZON = 5                              # CONVENTION — candle reads are short-lived


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].pattern_observations
    except Exception:
        return None


def _et_date() -> str:
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        from datetime import datetime
        return datetime.now().astimezone().strftime("%Y-%m-%d")


# ── 1. RECORD ────────────────────────────────────────────────────────────────
def record_observations(verdicts: list, et_date: Optional[str] = None) -> int:
    """Append one observation per NEW event from a verdict scan. Idempotent —
    the _id encodes the event identity, so re-running a scan adds nothing."""
    coll = _coll()
    if coll is None or not verdicts:
        return 0
    d = et_date or _et_date()
    now = int(time.time())
    n = 0
    for v in verdicts:
        sym = (v.get("symbol") or "").upper()
        if not sym:
            continue
        sepa = v.get("sepa") or {}
        base = {"symbol": sym, "et_date": d, "recorded_at": now,
                "rs_rank": sepa.get("rs_rank"), "stage": sepa.get("stage"),
                "is_buyable": bool(sepa.get("is_buyable")),
                "is_candidate": bool(sepa.get("is_candidate")),
                "resolved": False}
        for m in v.get("matches") or []:
            status = m.get("status")
            if status not in ("confirmed", "forming") or not m.get("neckline"):
                continue
            # Event identity: a confirmation IS its confirm date; a forming
            # pattern IS its line (re-flagged daily until it resolves).
            anchor = m.get("confirmed_date") if status == "confirmed" \
                else f"L{round(float(m['neckline']), 2)}"
            doc_id = f"{sym}:{m['pattern']}:{status}:{anchor}"
            doc = {**base, "kind": "pattern", "pattern": m["pattern"],
                   "status": status, "neckline": float(m["neckline"]),
                   "target": m.get("target"), "stop": m.get("stop"),
                   "obs_close": m.get("last_close"),
                   "confirmed_date": m.get("confirmed_date"),
                   "to_confirm_pct": m.get("to_confirm_pct")}
            try:
                r = coll.update_one({"_id": doc_id}, {"$setOnInsert": doc}, upsert=True)
                n += 1 if r.upserted_id is not None else 0
            except Exception as exc:
                log.debug("record pattern obs failed %s: %s", doc_id, exc)
        for f in (v.get("candles") or {}).get("formations") or []:
            read = f.get("read")
            if read not in ("bullish_reversal_setup", "bearish_warning"):
                continue                       # indecision has no direction to grade
            doc_id = f"{sym}:candle:{f.get('name')}:{f.get('date')}"
            last_bar = (v.get("candles") or {}).get("last_bar") or {}
            doc = {**base, "kind": "candle", "formation": f.get("name"),
                   "read": read, "formed_date": f.get("date"),
                   "obs_close": last_bar.get("c") or None}
            try:
                r = coll.update_one({"_id": doc_id}, {"$setOnInsert": doc}, upsert=True)
                n += 1 if r.upserted_id is not None else 0
            except Exception as exc:
                log.debug("record candle obs failed %s: %s", doc_id, exc)
    if n:
        log.info("pattern ledger: %d new observations recorded for %s", n, d)
    return n


# ── 2. RESOLVE ───────────────────────────────────────────────────────────────
def _obs_index(df: pd.DataFrame, et_date: str) -> Optional[int]:
    """Position of the bar ON the observation date (or the last bar before it)."""
    try:
        ts = pd.Timestamp(et_date)
        k = int(df.index.searchsorted(ts, side="right")) - 1
        return k if k >= 0 else None
    except Exception:
        return None


def _grade_pattern(df: pd.DataFrame, obs: dict) -> Optional[dict]:
    closes = df["close"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    k = _obs_index(df, obs["et_date"])
    if k is None:
        return None
    entry = float(obs.get("obs_close") or closes[k])
    if entry <= 0:
        return None
    end = min(k + PATTERN_HORIZON, len(df) - 1)

    if obs["status"] == "confirmed":
        target, stop = obs.get("target"), obs.get("stop")
        outcome = None
        hit_bar = None
        for j in range(k + 1, end + 1):
            # Pessimistic: a bar that touches BOTH counts as the stop.
            if stop is not None and lows[j] <= float(stop):
                outcome, hit_bar = "stop_first", j
                break
            if target is not None and highs[j] >= float(target):
                outcome, hit_bar = "target_first", j
                break
        full_window = k + PATTERN_HORIZON < len(df)
        if outcome is None:
            if not full_window:
                return None                    # nothing hit yet, window incomplete
            outcome = "neither"
        res = {"outcome": outcome,
               "bars_to_outcome": (hit_bar - k) if hit_bar else None,
               "fwd_21_pct": round((closes[k + PATTERN_HORIZON] / entry - 1) * 100, 2)
               if full_window else None,
               "max_gain_pct": round((highs[k + 1: end + 1].max() / entry - 1) * 100, 2)
               if end > k else None}
        return res

    # forming → did it go on to CONFIRM (close above the line) or stop out first?
    neckline = float(obs["neckline"])
    stop = obs.get("stop")
    for j in range(k + 1, end + 1):
        if stop is not None and lows[j] <= float(stop):
            return {"outcome": "stopped", "bars_to_outcome": j - k}
        if closes[j] > neckline:
            return {"outcome": "confirmed", "bars_to_outcome": j - k}
    if k + PATTERN_HORIZON < len(df):
        return {"outcome": "expired", "bars_to_outcome": None}
    return None                                # window still open


def _grade_candle(df: pd.DataFrame, obs: dict) -> Optional[dict]:
    closes = df["close"].to_numpy(dtype=float)
    k = _obs_index(df, obs["et_date"])
    if k is None or k + CANDLE_HORIZON >= len(df):
        return None
    entry = float(obs.get("obs_close") or closes[k])
    if entry <= 0:
        return None
    fwd = (closes[k + CANDLE_HORIZON] / entry - 1) * 100
    hit = fwd > 0 if obs["read"] == "bullish_reversal_setup" else fwd < 0
    return {"outcome": "hit" if hit else "miss", "fwd_5_pct": round(float(fwd), 2)}


def resolve_pending(limit: int = 2000) -> dict:
    """Grade unresolved observations against the price cache. Run daily after
    the post-close fast-scan so today's bar is in the frames."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "no mongo"}
    from sepa import prices
    n_resolved = n_checked = 0
    frames: dict = {}
    for obs in coll.find({"resolved": False}).limit(limit):
        n_checked += 1
        sym = obs["symbol"]
        if sym not in frames:
            try:
                frames[sym] = prices.load_prices(sym)
            except Exception:
                frames[sym] = None
        df = frames[sym]
        if df is None or len(df) < 30:
            continue
        try:
            res = _grade_pattern(df, obs) if obs.get("kind") == "pattern" \
                else _grade_candle(df, obs)
        except Exception as exc:
            log.debug("grade failed %s: %s", obs["_id"], exc)
            continue
        if res is None:
            continue                           # horizon not complete yet
        coll.update_one({"_id": obs["_id"]},
                        {"$set": {**res, "resolved": True,
                                  "resolved_at": int(time.time())}})
        n_resolved += 1
    log.info("pattern ledger resolve: %d/%d resolved", n_resolved, n_checked)
    return {"ok": True, "checked": n_checked, "resolved": n_resolved}


# ── 3. ACCURACY ──────────────────────────────────────────────────────────────
def _pct(part: int, whole: int) -> Optional[float]:
    return round(part / whole * 100, 1) if whole else None


def accuracy() -> dict:
    """The live record, aggregated — the answer to "are our patterns accurate?"
    computed from what the system actually flagged, day by day."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "no mongo"}
    patterns: dict = {}
    candles: dict = {}
    pending = 0
    earliest = None
    for obs in coll.find({}):
        if not obs.get("resolved"):
            pending += 1
            continue
        earliest = min(earliest or obs["et_date"], obs["et_date"])
        if obs.get("kind") == "pattern":
            slot = patterns.setdefault(obs["pattern"], {}).setdefault(obs["status"], {
                "n": 0, "target_first": 0, "stop_first": 0, "neither": 0,
                "confirmed": 0, "stopped": 0, "expired": 0, "fwd": [], "buyable_n": 0,
                "buyable_target_first": 0})
            slot["n"] += 1
            o = obs.get("outcome")
            if o in slot:
                slot[o] += 1
            if obs.get("fwd_21_pct") is not None:
                slot["fwd"].append(obs["fwd_21_pct"])
            if obs.get("is_buyable"):
                slot["buyable_n"] += 1
                if o == "target_first":
                    slot["buyable_target_first"] += 1
        else:
            slot = candles.setdefault(obs.get("formation"), {"n": 0, "hit": 0, "fwd": []})
            slot["n"] += 1
            if obs.get("outcome") == "hit":
                slot["hit"] += 1
            if obs.get("fwd_5_pct") is not None:
                slot["fwd"].append(obs["fwd_5_pct"])

    out_p = {}
    for pat, by_status in patterns.items():
        out_p[pat] = {}
        for status, s in by_status.items():
            fwd = sorted(s["fwd"])
            row = {"n": s["n"]}
            if status == "confirmed":
                row.update({
                    "target_before_stop_pct": _pct(s["target_first"], s["n"]),
                    "stop_first_pct": _pct(s["stop_first"], s["n"]),
                    "neither_pct": _pct(s["neither"], s["n"]),
                    "pct_positive_21d": _pct(sum(1 for x in fwd if x > 0), len(fwd)) if fwd else None,
                    "median_fwd_21d_pct": fwd[len(fwd) // 2] if fwd else None,
                    "buyable_n": s["buyable_n"],
                    "buyable_target_before_stop_pct": _pct(s["buyable_target_first"], s["buyable_n"]),
                })
            else:
                row.update({
                    "went_on_to_confirm_pct": _pct(s["confirmed"], s["n"]),
                    "stopped_first_pct": _pct(s["stopped"], s["n"]),
                    "expired_pct": _pct(s["expired"], s["n"]),
                })
            out_p[pat][status] = row
    out_c = {name: {"n": s["n"], "direction_hit_pct": _pct(s["hit"], s["n"]),
                    "median_fwd_5d_pct": sorted(s["fwd"])[len(s["fwd"]) // 2] if s["fwd"] else None}
             for name, s in candles.items()}

    return {
        "ok": True, "generated_at": int(time.time()),
        "patterns": out_p, "candles": out_c,
        "pending": pending, "since": earliest,
        "conventions": {
            "pattern_horizon_bars": PATTERN_HORIZON, "candle_horizon_bars": CANDLE_HORIZON,
            "entry": "close on the day the system flagged it",
            "tie_break": "a bar touching target AND stop counts as the stop (pessimistic)",
        },
        "disclaimer": (
            "OUR live forward record: every pattern/candle the verdict scan flagged, "
            "graded later against the real tape. Gross close-to-close, no costs; "
            "21/5-bar horizons are conventions; small n early means wide error bars. "
            "A probability here is a measured frequency, not a promise."),
    }


# ── 4. MONTHLY ROLLUP (perpetual) ────────────────────────────────────────────
# Ajay 2026-06-10: "record another set of analytics to track how accurate the
# winning patterns have been throughout the months going forward… I do not
# want the data to be pruned — available perpetually."
#
# One doc per calendar month in `pattern_accuracy_monthly` (_id "YYYY-MM"),
# recomputed idempotently from the observation ledger on every nightly run —
# months keep absorbing late-resolving observations near their boundary.
# NOTHING here or anywhere in this module deletes: no TTL index, no pruning.
# The raw `pattern_observations` ledger is likewise append+grade only, so the
# rollup can always be rebuilt from first principles.

def _monthly_coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].pattern_accuracy_monthly
    except Exception:
        return None


def compute_monthly() -> list:
    """Aggregate the resolved ledger per calendar month (of the observation
    date) → per-pattern winners' record. Pure read; returns oldest→newest."""
    coll = _coll()
    if coll is None:
        return []
    months: dict = {}
    for obs in coll.find({"resolved": True}):
        m = (obs.get("et_date") or "")[:7]
        if len(m) != 7:
            continue
        slot = months.setdefault(m, {"patterns": {}, "candles": {},
                                     "n_observations": 0})
        slot["n_observations"] += 1
        o = obs.get("outcome")
        if obs.get("kind") == "pattern":
            p = slot["patterns"].setdefault(obs["pattern"], {
                "confirmed_n": 0, "target_first": 0, "stop_first": 0,
                "neither": 0, "forming_n": 0, "went_on_to_confirm": 0,
                "fwd": [], "buyable_n": 0, "buyable_target_first": 0})
            if obs.get("status") == "confirmed":
                p["confirmed_n"] += 1
                if o in ("target_first", "stop_first", "neither"):
                    p[o] += 1
                if obs.get("fwd_21_pct") is not None:
                    p["fwd"].append(obs["fwd_21_pct"])
                if obs.get("is_buyable"):
                    p["buyable_n"] += 1
                    if o == "target_first":
                        p["buyable_target_first"] += 1
            else:
                p["forming_n"] += 1
                if o == "confirmed":
                    p["went_on_to_confirm"] += 1
        else:
            cd = slot["candles"].setdefault(obs.get("formation"),
                                            {"n": 0, "hit": 0})
            cd["n"] += 1
            if o == "hit":
                cd["hit"] += 1

    out = []
    for m in sorted(months):
        s = months[m]
        pats = {}
        for name, p in s["patterns"].items():
            fwd = sorted(p["fwd"])
            pats[name] = {
                "confirmed_n": p["confirmed_n"],
                "win_pct": _pct(p["target_first"], p["confirmed_n"]),
                "stop_pct": _pct(p["stop_first"], p["confirmed_n"]),
                "median_fwd_21d_pct": fwd[len(fwd) // 2] if fwd else None,
                "buyable_n": p["buyable_n"],
                "buyable_win_pct": _pct(p["buyable_target_first"], p["buyable_n"]),
                "forming_n": p["forming_n"],
                "forming_confirm_pct": _pct(p["went_on_to_confirm"], p["forming_n"]),
            }
        cands = {name: {"n": c["n"], "direction_hit_pct": _pct(c["hit"], c["n"])}
                 for name, c in s["candles"].items()}
        conf_total = sum(p["confirmed_n"] for p in s["patterns"].values())
        wins_total = sum(p["target_first"] for p in s["patterns"].values())
        out.append({"month": m,
                    "n_observations": s["n_observations"],
                    "confirmed_n": conf_total,
                    "overall_win_pct": _pct(wins_total, conf_total),
                    "patterns": pats, "candles": cands})
    return out


def snapshot_monthly() -> dict:
    """Persist the rollup — one upserted doc per month, kept forever."""
    rows = compute_monthly()
    coll = _monthly_coll()
    if coll is None:
        return {"ok": False, "reason": "no mongo"}
    now = int(time.time())
    for row in rows:
        try:
            coll.update_one({"_id": row["month"]},
                            {"$set": {**row, "updated_at": now}}, upsert=True)
        except Exception as exc:
            log.warning("monthly snapshot upsert failed %s: %s", row["month"], exc)
    log.info("pattern ledger: monthly rollup persisted for %d months", len(rows))
    return {"ok": True, "months": len(rows)}


def monthly_series() -> dict:
    """The persisted month-by-month record, oldest→newest (for the API)."""
    coll = _monthly_coll()
    rows = []
    if coll is not None:
        try:
            rows = sorted(coll.find({}), key=lambda r: r["_id"])
            for r in rows:
                r["month"] = r.pop("_id")
        except Exception as exc:
            log.warning("monthly series read failed: %s", exc)
            rows = []
    if not rows:                                # not snapshotted yet → live
        rows = compute_monthly()
    return {
        "ok": True, "months": rows,
        "retention": ("perpetual — pattern_observations and "
                      "pattern_accuracy_monthly are never pruned (no TTL, "
                      "no deletes); rollup recomputed nightly so months keep "
                      "absorbing late-resolving observations"),
        "disclaimer": ("Measured frequencies from OUR live forward ledger, "
                       "month by month. Gross, no costs; small months mean "
                       "wide error bars — read the n before the %."),
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    r = resolve_pending()
    s = snapshot_monthly()
    log.info("PATTERN-LEDGER: %s · monthly rollup: %s", r, s)
    sys.exit(0 if r.get("ok") else 1)
