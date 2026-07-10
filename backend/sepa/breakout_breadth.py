"""Breakout breadth — the book's market thermometer, counted and graded.

WHAT (all book-anchored; Ajay asked 2026-07-10 "a few breakouts a day to
gauge the market — lmk if I'm going against Minervini"):
  * COUNT the volume-confirmed breakouts per ET day (TLSW p.164: "you should
    see multiple waves of stocks emerging into new high ground"; TTLAC §7
    ebook p.131: "your list of leaders expands, this should be viewed as a
    sign of strength").
  * GRADE each breakout afterwards — the inverse read is his loudest tell:
    "Rarely does a correct pivot point fail coming out of a sound
    consolidation in a healthy market" (TTLAC §6 ebook p.117); mass failures
    = hostile tape (TLSW p.303, p.165).
  * The read governs EXPOSURE ONLY — pilot buys first, pyramid on wins
    (TLSW p.307; TTLAC §5 ebook p.91-92). It NEVER gates an entry: "if you
    concentrate on the general market solely for timing your individual
    stock purchases, you're likely to miss many of the really great
    selections" (TLSW p.165); a lone leader with no confirming names is
    "normal" (TTLAC §7 ebook p.124). Nothing in this module is consumed by
    the scanner, the auto-entry funnel, or the Market Gauge score.

GRADING DEFINITIONS (book concepts; the window length is a HOUSE VALUE):
  failed          any close within FT_WINDOW_BARS back BELOW the level the
                  stock broke out over (volume.recent_high at breakout) —
                  the failed-pivot signature (TTLAC §6 p.117, §1 p.37).
  followed_through no such undercut AND the T+FT_WINDOW close is above the
                  breakout-day close — "multiple days of followthrough
                  action" (TTLAC §1 ebook p.29).
  stalled         neither (held the level but went nowhere).
  FT_WINDOW_BARS = 5 — the book quantifies no exact day count; 5 trading
  days is the configured house value (same convention as the candle ledger).

Data: candidate_snapshots (one doc per symbol per date_et) where
volume.days_since_breakout == 0 — the scanner's p.203 volume-confirmed flag.
Rollups persist to `breakout_breadth` (_id = date_et, never pruned).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

log = logging.getLogger("sepa.breakout_breadth")

FT_WINDOW_BARS = 5
SERIES_DAYS_DEFAULT = 30
# Exposure-read thresholds — HOUSE VALUES (the book says "expanding" /
# "failing wholesale", not numbers). Documented in the methodology doc.
EXPANDING_MIN_RATIO = 1.25       # today+yesterday vs the prior 10-day mean
FAILURE_RATE_HOSTILE = 0.5       # >=50% of graded recent breakouts failed
FAILURE_RATE_HEALTHY = 0.25


def _db():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")]
    except Exception:
        return None


# ── Pure grading (unit-tested) ───────────────────────────────────────────────
def grade_breakout(df, breakout_date: str, level: Optional[float]) -> Optional[dict]:
    """Grade one breakout vs the daily closes AFTER it. Pure.

    Returns None while the FT window is incomplete; else
    {outcome: failed|followed_through|stalled, fwd_pct}.
    """
    import pandas as pd
    try:
        ts = pd.Timestamp(breakout_date)
        k = int(df.index.searchsorted(ts, side="right")) - 1
    except Exception:
        return None
    if k < 0 or k + FT_WINDOW_BARS >= len(df):
        return None
    closes = df["close"].to_numpy(dtype=float)
    day_close = closes[k]
    if day_close <= 0:
        return None
    window = closes[k + 1: k + 1 + FT_WINDOW_BARS]
    fwd_pct = round((closes[k + FT_WINDOW_BARS] / day_close - 1) * 100, 2)
    lvl = None
    try:
        lvl = float(level) if level else None
    except (TypeError, ValueError):
        lvl = None
    if lvl and lvl > 0 and (window < lvl).any():
        return {"outcome": "failed", "fwd_pct": fwd_pct}
    if closes[k + FT_WINDOW_BARS] > day_close:
        return {"outcome": "followed_through", "fwd_pct": fwd_pct}
    return {"outcome": "stalled", "fwd_pct": fwd_pct}


def exposure_read(today: int, avg10: float, failure_rate: Optional[float],
                  graded_n: int) -> dict:
    """Counts + failure rate → the book's exposure posture. Pure.

    THE READ NEVER GATES AN ENTRY (TLSW p.165) — it answers "how aggressive
    should sizing be", i.e. the pilot-buys → pyramid ladder (TLSW p.307;
    TTLAC §5 p.91-92) and the hostile-tape warning (TLSW p.303).
    """
    if failure_rate is not None and graded_n >= 5 and failure_rate >= FAILURE_RATE_HOSTILE:
        return {"state": "HOSTILE", "icon": "🔴",
                "label": "Breakouts are failing",
                "guidance": ("Most recent breakouts are failing — the p.303 tell of a "
                             "hostile tape. Defense: pilot size only, honor every stop; "
                             "'if you get stopped out repeatedly, you may be too early' "
                             "(TLSW p.165).")}
    expanding = avg10 > 0 and today >= avg10 * EXPANDING_MIN_RATIO
    healthy_ft = failure_rate is not None and graded_n >= 5 and failure_rate <= FAILURE_RATE_HEALTHY
    if expanding and (failure_rate is None or failure_rate < FAILURE_RATE_HOSTILE):
        return {"state": "EXPANDING", "icon": "🟢",
                "label": "Leader list is expanding",
                "guidance": ("'Multiple waves of stocks emerging into new high ground' "
                             "(TLSW p.164) — a sign of strength (TTLAC §7). Step exposure "
                             "up AS YOUR TRADES WORK: pilot buys first, pyramid on wins "
                             "(TLSW p.307; TTLAC §5). Still take entries stock-by-stock at "
                             "their pivots — never wait on the market (TLSW p.165).")}
    if healthy_ft:
        return {"state": "HEALTHY", "icon": "🟢",
                "label": "Breakouts are holding",
                "guidance": ("Follow-through is healthy — 'rarely does a correct pivot "
                             "fail in a healthy market' (TTLAC §6 p.117). Normal "
                             "exposure ladder applies (TLSW p.307).")}
    return {"state": "MIXED", "icon": "🟡",
            "label": "Mixed tape",
            "guidance": ("No expansion signal and follow-through is unproven — stay on "
                         "the pilot-buy rung until a few trades work (TLSW p.307). A "
                         "lone leader breaking out alone is still valid and 'normal' "
                         "(TTLAC §7 p.124) — this read sizes positions, it never skips "
                         "a proper pivot.")}


# ── Data assembly ────────────────────────────────────────────────────────────
def _breakouts_by_day(days: int) -> dict:
    """{date_et: [{symbol, level}]} from candidate_snapshots (dsb == 0)."""
    db = _db()
    if db is None:
        return {}
    out: dict = {}
    try:
        cur = db.candidate_snapshots.aggregate([
            {"$match": {"volume.days_since_breakout": 0}},
            {"$group": {"_id": {"d": "$date_et", "s": "$symbol"},
                        "level": {"$last": "$volume.recent_high"}}},
        ])
        for row in cur:
            d = row["_id"]["d"]
            out.setdefault(d, []).append({"symbol": row["_id"]["s"],
                                          "level": row.get("level")})
    except Exception as exc:
        log.warning("breadth: snapshot aggregate failed: %s", exc)
        return {}
    dates = sorted(out)[-days:]
    return {d: out[d] for d in dates}


def rebuild(days: int = 60) -> dict:
    """Recompute + persist the daily rollups (idempotent; cron nightly).

    Grades every breakout whose FT window has completed; rollups keep
    absorbing late grades on re-runs (same never-prune convention as the
    pattern ledger)."""
    db = _db()
    if db is None:
        return {"ok": False, "reason": "no mongo"}
    from sepa import prices
    by_day = _breakouts_by_day(days)
    frames: dict = {}

    def _frame(sym):
        if sym not in frames:
            try:
                frames[sym] = prices.load_prices(sym)
            except Exception:
                frames[sym] = None
        return frames[sym]

    n_days = n_graded = 0
    for d, rows in by_day.items():
        graded = {"followed_through": 0, "failed": 0, "stalled": 0}
        pending = 0
        for r in rows:
            df = _frame(r["symbol"])
            g = grade_breakout(df, d, r.get("level")) if df is not None else None
            if g is None:
                pending += 1
                continue
            graded[g["outcome"]] += 1
            n_graded += 1
        total_graded = sum(graded.values())
        doc = {"date_et": d, "n_breakouts": len(rows),
               "symbols": sorted(r["symbol"] for r in rows),
               "graded": graded, "pending": pending,
               "failure_rate": round(graded["failed"] / total_graded, 3)
               if total_graded else None,
               "ft_rate": round(graded["followed_through"] / total_graded, 3)
               if total_graded else None,
               "updated_at": int(time.time())}
        try:
            db.breakout_breadth.update_one({"_id": d}, {"$set": doc}, upsert=True)
            n_days += 1
        except Exception as exc:
            log.warning("breadth upsert failed %s: %s", d, exc)
    log.info("breakout_breadth: %d days rolled up, %d breakouts graded",
             n_days, n_graded)
    return {"ok": True, "days": n_days, "graded": n_graded}


def summary(days: int = SERIES_DAYS_DEFAULT) -> dict:
    """The strip payload: series + today's count + the exposure read."""
    db = _db()
    rows = []
    if db is not None:
        try:
            rows = sorted(db.breakout_breadth.find({}), key=lambda r: r["_id"])[-days:]
            for r in rows:
                r.pop("_id", None)
        except Exception as exc:
            log.warning("breadth read failed: %s", exc)
            rows = []
    if not rows:
        return {"ok": False, "reason": "no rollups yet — run rebuild (cron 17:15 ET)"}

    today = rows[-1]
    prior = rows[:-1][-10:]
    avg10 = (sum(r["n_breakouts"] for r in prior) / len(prior)) if prior else 0.0
    # Recent follow-through: pool the graded outcomes of the last 10 GRADED days
    graded_days = [r for r in rows if sum((r.get("graded") or {}).values()) > 0][-10:]
    ft = sum((r["graded"]).get("followed_through", 0) for r in graded_days)
    fl = sum((r["graded"]).get("failed", 0) for r in graded_days)
    st = sum((r["graded"]).get("stalled", 0) for r in graded_days)
    graded_n = ft + fl + st
    failure_rate = round(fl / graded_n, 3) if graded_n else None

    read = exposure_read(today["n_breakouts"], avg10, failure_rate, graded_n)
    return {
        "ok": True,
        "today": {"date_et": today["date_et"], "n_breakouts": today["n_breakouts"]},
        "avg10": round(avg10, 1),
        "recent_graded": {"n": graded_n, "followed_through": ft, "failed": fl,
                          "stalled": st, "failure_rate": failure_rate,
                          "window_bars": FT_WINDOW_BARS},
        "read": read,
        "series": [{"date_et": r["date_et"], "n": r["n_breakouts"],
                    "failure_rate": r.get("failure_rate")} for r in rows],
        "boundary": ("Exposure guidance only — never an entry gate. Entries stay "
                     "stock-by-stock at their pivots (TLSW p.165; TTLAC §7 p.131). "
                     "Not consumed by the scanner, auto-entry, or the Market Gauge "
                     "score."),
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    r = rebuild()
    log.info("BREAKOUT-BREADTH: %s", r)
    sys.exit(0 if r.get("ok") else 1)
