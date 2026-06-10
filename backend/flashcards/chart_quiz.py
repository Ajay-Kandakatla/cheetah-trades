"""Daily chart-identification quiz — Chart School's interactive half.

Ajay 2026-06-09: "I want daily one or two charts to identify the patterns."
Each weekday this picks 2 REAL historical pattern confirmations (double bottom /
inverse H&S, found by patterns.detector across the SEPA universe's cached daily
frames), serves the bars UP TO the confirmation bar with the name hidden, and
asks "what pattern is this?". The reveal explains the WHY (supply/demand
mechanics) and shows what actually happened next (+21 bars, gross — honest
outcome, win or lose).

Deterministic per ET date (same quiz on phone + desktop all day). Persisted to
Mongo `chart_quiz`; generated on-demand if the cron hasn't run. Pushed once per
weekday morning under the existing learning pref (`minervini_flashcards`).
"""
from __future__ import annotations

import hashlib
import logging
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger("flashcards.chart_quiz")

N_ITEMS = 2
BARS_BEFORE = 65            # context bars shown before the confirmation bar
CANDIDATE_POOL = 60        # symbols sampled per generation attempt
CHOICES = ["Double bottom (W)", "Inverse head & shoulders", "Flat base / no reversal pattern"]
ANSWER_OF = {"double_bottom": CHOICES[0], "inverse_head_shoulders": CHOICES[1]}

WHY = {
    "double_bottom": (
        "The second trip to the low was the TEST: the sellers who wanted out at "
        "that price already sold on the first low, so the retest found no new "
        "supply. The close above the middle peak (the confirmation line) proved "
        "demand had absorbed the overhead — that close is the pattern; the W "
        "shape alone continues lower 48% of the time (Bulkowski)."),
    "inverse_head_shoulders": (
        "The head was the panic low. The right shoulder made a HIGHER low — "
        "sellers couldn't push price back down — and the close through the "
        "neckline added short-covering to fresh demand. The best-studied "
        "reversal family in the academic record (Chang & Osler 1999; Savin et "
        "al. 2007), both short of standalone-profit claims."),
}


def _et_date() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().astimezone().strftime("%Y-%m-%d")


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].chart_quiz
    except Exception:
        return None


def _bars_payload(df, start: int, end: int) -> list:
    """[{t,o,h,l,c,v}] for iloc [start:end] — slim for the page's SVG candles."""
    out = []
    for ts, row in df.iloc[start:end].iterrows():
        try:
            out.append({"t": ts.strftime("%Y-%m-%d"),
                        "o": round(float(row["open"]), 2), "h": round(float(row["high"]), 2),
                        "l": round(float(row["low"]), 2), "c": round(float(row["close"]), 2),
                        "v": int(row.get("volume") or 0)})
        except Exception:
            continue
    return out


def _item_from_symbol(sym: str, rng: random.Random) -> Optional[dict]:
    """Find one usable historical confirmation on this symbol → a quiz item."""
    from patterns import detector
    from sepa import prices
    try:
        df = prices.load_prices(sym)
    except Exception:
        return None
    if df is None or len(df) < 150:
        return None
    closes = df["close"].to_numpy(dtype=float)
    options = []
    for kind, fn in detector.DETECTORS.items():
        try:
            res = fn(df)
        except Exception:
            continue
        for c in res.get("historical_confirms", []):
            k = c["confirm_idx"]
            # need full context before + a complete +21-bar outcome after
            if k < BARS_BEFORE or k + detector.VALIDATION_HORIZON >= len(df):
                continue
            options.append((kind, c))
    if not options:
        return None
    kind, c = rng.choice(options)
    k = c["confirm_idx"]
    base = closes[k]
    fwd = round(float(closes[k + detector.VALIDATION_HORIZON] / base - 1) * 100, 2)
    return {
        "symbol": sym,
        "pattern": kind,
        "answer": ANSWER_OF[kind],
        "choices": list(CHOICES),
        "bars": _bars_payload(df, k - BARS_BEFORE, k + 1),   # ends ON the confirmation bar
        "confirm_date": df.index[k].strftime("%Y-%m-%d"),
        "neckline": round(float(c["neckline"]), 2),
        "pattern_low": round(float(c["pattern_low"]), 2),
        "why": WHY[kind],
        "outcome_fwd_21d_pct": fwd,
        "outcome_note": (
            f"What actually happened: {fwd:+.1f}% over the next 21 trading days "
            "(gross, close-to-close). One sample proves nothing — that's the point "
            "of showing it either way."),
    }


def generate(date_str: Optional[str] = None, n: int = N_ITEMS) -> dict:
    """Build the day's quiz deterministically from the universe's cached frames."""
    d = date_str or _et_date()
    seed = int(hashlib.sha256(d.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    try:
        from sepa import scanner
        syms = [r["symbol"] for r in (scanner.load_latest() or {}).get("all_results") or []
                if r.get("symbol") and not r.get("is_etf")]
    except Exception:
        syms = []
    if not syms:
        return {"et_date": d, "items": [], "error": "no universe — run a SEPA scan first"}
    rng.shuffle(syms)

    items, used = [], set()
    for sym in syms[:CANDIDATE_POOL * 3]:
        if len(items) >= n:
            break
        if sym in used:
            continue
        it = _item_from_symbol(sym, rng)
        if it:
            # avoid two of the same pattern when possible
            if len(items) == 1 and items[0]["pattern"] == it["pattern"] and rng.random() < 0.7:
                continue
            items.append(it)
            used.add(sym)
    return {
        "et_date": d, "items": items, "n": len(items),
        "disclaimer": (
            "Real historical charts from the scan universe, cut at the pattern's "
            "confirmation bar. Educational pattern-recognition practice — base "
            "rates are historical tendencies, not guarantees. Not advice."),
    }


def get_today(force: bool = False) -> dict:
    """Today's quiz — from Mongo if the cron made it, else generate + persist."""
    d = _et_date()
    coll = _coll()
    if not force and coll is not None:
        doc = coll.find_one({"_id": d})
        if doc and doc.get("items"):
            doc.pop("_id", None)
            return doc
    quiz = generate(d)
    if coll is not None and quiz.get("items"):
        try:
            coll.update_one({"_id": d}, {"$set": quiz}, upsert=True)
        except Exception as exc:
            log.warning("chart_quiz persist failed: %s", exc)
    return quiz


def fire_daily() -> dict:
    """Cron: generate (warm) today's quiz + one morning push under the existing
    learning pref. Deduped per day by the notification tag."""
    quiz = get_today()
    n = quiz.get("n") or len(quiz.get("items") or [])
    if not n:
        log.info("chart_quiz: nothing generated (%s)", quiz.get("error"))
        return {"ok": False, "reason": quiz.get("error", "no items")}
    try:
        from sepa import notify
        ok = notify.send_alert(
            title="🕯 Chart School — today's charts are up",
            body=(f"{n} real chart{'s' if n > 1 else ''} from your universe, cut at the "
                  "moment of truth. Name the pattern, then see the why and what "
                  "happened next."),
            url="/chart-school", kind="minervini_flashcards", ticker=None)
    except Exception as exc:
        log.warning("chart_quiz push failed: %s", exc)
        ok = False
    return {"ok": bool(ok), "n": n, "et_date": quiz["et_date"]}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    r = fire_daily()
    log.info("CHART-QUIZ: %s", r)
    sys.exit(0 if r.get("ok") or r.get("n") else 1)
