"""Earnings-report picks — names whose LAST report was good and the tape
agreed (Ajay 2026-06-11: shaken out of ATEX hours before its post-earnings
rip — "keep track of post-earnings that got a good reaction as a trigger").

The judge is the REACTION, not the press release:
  - reported within the last REPORT_WINDOW_DAYS calendar days
  - reaction day closed >= +MIN_REACTION_PCT vs the pre-report close
  - reaction-day volume >= MIN_VOL_RATIO x the 50-day average (participation)
  - still holding: latest close above the pre-report close (drift intact)
EPS beat (surprise %) is a RANK BOOST, stated on the row — a name can react
well on revenue/guidance without an EPS beat.

Why this is a real setup and not vibes: gap-and-volume reactions tend to
drift further for weeks ("post-earnings announcement drift", documented in
the academic literature; the setups/post_earnings_drift module trades the
same effect by pure price action). This module ties it to the actual report
via the earnings_calendar cache (earnings_watch stores each name's last
report — date, actual vs estimate, surprise — from the same yfinance fetch
that gets the next date).

Persisted: `earnings_picks` Mongo doc (_id "latest"); nightly cron
19:10 ET + read-through stale kick on the endpoint. Surfaced as the
"Earnings report picks" section on Portfolio / SEPA / Leaderboard /
Scalping.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import List, Optional

log = logging.getLogger("sepa.earnings_picks")

REPORT_WINDOW_DAYS = 7     # calendar days back a report still counts
MIN_REACTION_PCT = 3.0     # reaction-day close vs pre-report close
MIN_VOL_RATIO = 1.5        # reaction-day volume vs 50-day average
MAX_PICKS = 24
_STALE_AFTER_SEC = 26 * 60 * 60

_REFRESH = {"running": False}
_LOCK = threading.Lock()


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")]
    except Exception:
        return None


def _today_iso() -> str:
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return time.strftime("%Y-%m-%d")


def reaction_read(df, report_date: str, when: Optional[str]) -> Optional[dict]:
    """Pure: the post-report tape read from a daily frame.

    Reaction day = the report day for BMO, the NEXT session for AMC (or
    unknown timing — yfinance stamps most after-close reports correctly,
    and a same-day stamp with unknown timing behaves like BMO).
    Returns None when the reaction day's bar isn't in the frame yet."""
    import pandas as pd
    try:
        ts = pd.Timestamp(report_date)
        idx = df.index
        # position of the report day (or the first session at/after it)
        k = int(idx.searchsorted(ts, side="left"))
        if when == "AMC":
            # reaction prints on the NEXT session after the report day
            if k < len(idx) and idx[k].normalize() == ts.normalize():
                k += 1
        if k >= len(idx):
            return None                      # reaction session not traded yet
        pre = k - 1
        if pre < 0 or k < 50:
            return None
        closes = df["close"].to_numpy(dtype=float)
        vols = df["volume"].to_numpy(dtype=float)
        pre_close = closes[pre]
        if pre_close <= 0:
            return None
        reaction_pct = (closes[k] / pre_close - 1) * 100
        avg50 = vols[max(0, k - 50):k].mean()
        vol_ratio = (vols[k] / avg50) if avg50 > 0 else None
        last = len(closes) - 1
        return {
            "reaction_date": idx[k].date().isoformat(),
            "reaction_pct": round(float(reaction_pct), 2),
            "vol_ratio": round(float(vol_ratio), 2) if vol_ratio else None,
            "drift_since_pct": round((closes[last] / closes[k] - 1) * 100, 2),
            "still_above_pre": bool(closes[last] > pre_close),
            "last_close": round(float(closes[last]), 2),
        }
    except Exception as exc:
        log.debug("reaction read failed: %s", exc)
        return None


def passes_gates(read: Optional[dict], provisional: bool = False) -> bool:
    """provisional=True (reaction day IS today, session in progress): the
    volume gate can't be honestly judged against full-day averages mid-
    session, so price + still-holding decide and the pick is FLAGGED
    provisional — the 17:55 nightly re-grade applies the full-volume gate.
    (ATEX 2026-06-11: +19.5% at 11 AM read vol_ratio 1.31 on PARTIAL volume
    and was wrongly dropped.)"""
    if not read:
        return False
    if not (read["reaction_pct"] >= MIN_REACTION_PCT and read["still_above_pre"]):
        return False
    if provisional:
        return True
    return (read["vol_ratio"] or 0) >= MIN_VOL_RATIO


def rank_score(read: dict, surprise_pct: Optional[float],
               rs_rank: Optional[int]) -> float:
    """Transparent blend — reaction strength leads, beat + RS boost."""
    s = read["reaction_pct"] * 2 + min(read["vol_ratio"] or 0, 6) * 5
    if surprise_pct is not None and surprise_pct > 0:
        s += min(surprise_pct, 50) * 0.4
    if rs_rank:
        s += rs_rank * 0.15
    return round(s, 1)


def scan() -> dict:
    """Build the picks doc from the earnings_calendar cache + daily frames."""
    db = _coll()
    if db is None:
        return {"ok": False, "reason": "no mongo"}
    from datetime import date, timedelta
    today = _today_iso()
    cutoff = (date.fromisoformat(today) - timedelta(days=REPORT_WINDOW_DAYS)).isoformat()

    # scan context (RS/stage/buy gate) for the rows that have it
    ctx: dict = {}
    try:
        from . import scanner
        for r in (scanner.load_latest() or {}).get("all_results") or []:
            ctx[r.get("symbol")] = {
                "rs_rank": r.get("rs_rank"), "score": r.get("score"),
                "stage": (r.get("stage") or {}).get("stage"),
                "is_buyable": bool(r.get("is_buyable")),
                "is_candidate": bool(r.get("qualifier") or r.get("is_candidate")),
            }
    except Exception as exc:
        log.debug("earnings picks: scan ctx unavailable: %s", exc)

    from . import prices
    picks: List[dict] = []
    checked = 0
    for d in db.earnings_calendar.find({"last_report.date": {"$gte": cutoff}}):
        sym = d["_id"]
        rep = d.get("last_report") or {}
        checked += 1
        try:
            df = prices.load_prices(sym)
        except Exception:
            df = None
        if df is None or len(df) < 60:
            continue
        read = reaction_read(df, rep["date"], rep.get("when"))
        provisional = bool(read and read.get("reaction_date") == today)
        if not passes_gates(read, provisional=provisional):
            continue
        c = ctx.get(sym) or {}
        if c.get("stage") == 4:
            continue                          # downtrends don't get a bull pick
        picks.append({
            "symbol": sym,
            "report_date": rep["date"], "when": rep.get("when"),
            "eps_actual": rep.get("eps_actual"),
            "eps_estimate": rep.get("eps_estimate"),
            "surprise_pct": rep.get("surprise_pct"),
            **read,
            **c,
            "provisional": provisional,
            "rank_score": rank_score(read, rep.get("surprise_pct"),
                                     c.get("rs_rank")),
        })
    picks.sort(key=lambda p: -p["rank_score"])
    doc = {
        "_id": "latest",
        "generated_at": int(time.time()),
        "as_of_date": today,
        "n_checked": checked,
        "picks": picks[:MAX_PICKS],
        "criteria": {
            "report_window_days": REPORT_WINDOW_DAYS,
            "min_reaction_pct": MIN_REACTION_PCT,
            "min_vol_ratio": MIN_VOL_RATIO,
            "gates": "reaction >= +3% vs pre-report close on >=1.5x volume, "
                     "still above the pre-report close, not Stage 4; EPS beat "
                     "boosts rank but is not required",
        },
        "disclaimer": ("Post-earnings reactions that the tape endorsed. The "
                       "drift effect (PEAD) is documented but gross/no-costs "
                       "and not a promise — confirm the SEPA read before "
                       "entering. Earnings data via yfinance; verify on "
                       "EarningsWhispers. Not advice."),
    }
    try:
        db.earnings_picks.replace_one({"_id": "latest"}, doc, upsert=True)
    except Exception as exc:
        log.warning("earnings picks write failed: %s", exc)
    log.info("earnings picks: %d/%d names passed the reaction gates",
             len(doc["picks"]), checked)
    return {"ok": True, "n": len(doc["picks"]), "checked": checked}


def latest(kick_if_stale: bool = True) -> dict:
    db = _coll()
    doc = None
    if db is not None:
        try:
            doc = db.earnings_picks.find_one({"_id": "latest"})
        except Exception:
            doc = None
    stale = doc is None or (int(time.time()) - (doc or {}).get("generated_at", 0)
                            > _STALE_AFTER_SEC)
    if kick_if_stale and stale:
        with _LOCK:
            if not _REFRESH["running"]:
                _REFRESH["running"] = True

                def run():
                    try:
                        scan()
                    finally:
                        _REFRESH["running"] = False
                threading.Thread(target=run, name="earnings-picks",
                                 daemon=True).start()
    if doc is None:
        return {"ok": True, "picks": [], "refreshing": True,
                "note": "first scan running — uses the earnings calendar "
                        "cache + daily frames, ~1 min"}
    doc.pop("_id", None)
    doc["refreshing"] = _REFRESH["running"]
    return doc


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    r = scan()
    log.info("EARNINGS-PICKS: %s", r)
    sys.exit(0 if r.get("ok") else 1)
