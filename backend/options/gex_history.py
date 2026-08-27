"""Daily dealer-GEX snapshot ledger — makes "did GEX flag it?" answerable.

Ajay 2026-07-06, after today's watchlist pop: GEX was only computable LIVE
(post-move), so "did the dealer-gamma read predict this?" had no data. This
cron (17:50 ET weekdays, backend/crontab) stores one slim row per name per
day in `gex_history`: regime, net GEX, max pain vs spot, the walls.

Universe: portfolio holdings + both watchlists + current SOIR BULLISH/WATCH
names + top SEPA candidates — the names he'd actually ask about (~50-150
chain pulls, a few minutes). Rows are idempotent (_id = SYM:date) and never
pruned; GET /options/gex-history/{symbol} serves the series.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

log = logging.getLogger("options.gex_history")

TOP_SEPA_N = 30
MAX_UNIVERSE = 200


def _coll():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")].gex_history
    except Exception:
        return None


def _et_date() -> str:
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.utcnow().strftime("%Y-%m-%d")


def slim_row(sym: str, opex_out: Optional[dict], et_date: str) -> Optional[dict]:
    """compute_opex payload → the slim ledger row. Pure — unit-tested.
    None in → None out (no chain = no row, never a zero-filled fake)."""
    if not opex_out:
        return None
    g = opex_out.get("gamma") or {}
    mp = opex_out.get("max_pain") or {}
    return {
        "symbol": sym.upper(),
        "date_et": et_date,
        "spot": opex_out.get("spot"),
        "regime": g.get("regime"),
        "net_gex_dollars": g.get("net_gex_dollars"),
        "max_pain": mp.get("max_pain_strike"),
        "mp_pct_from_spot": mp.get("pct_from_spot"),
        "put_wall": g.get("put_wall"),
        "call_wall": g.get("call_wall"),
        # Flip + VEX (2026-07-17, GEX board): None-safe — rows from before
        # the fields existed simply read None and the board buckets them
        # on regime alone.
        "flip_strike": g.get("flip_strike"),
        "magnet": g.get("magnet_strike"),
        "net_vex_dollars": (opex_out.get("vex") or {}).get("net_vex_dollars"),
        "vex_read": (opex_out.get("vex") or {}).get("read"),
        "reliability": opex_out.get("gex_reliability"),
        "expiration_date": opex_out.get("expiration_date"),
        "recorded_at": int(time.time()),
    }


def board_bucket(row: dict) -> str:
    """Bullish / bearish / mixed for the GEX board. Pure — unit-tested.

    bullish: dealers net LONG gamma (pinning) AND spot at/above the flip
             (or no flip mapped) — dips get bought, moves dampened.
    bearish: dealers net SHORT gamma (amplifying) AND spot below the flip
             (or no flip mapped) — weakness gets amplified.
    mixed:   regime and flip disagree (e.g. pinning but spot below flip) —
             the board shows these last, smallest claim."""
    regime = (row.get("regime") or "").lower()
    spot = row.get("spot")
    flip = row.get("flip_strike")
    above = flip is None or (spot is not None and spot >= flip)
    if regime == "pinning" and above:
        return "bullish"
    if regime == "amplifying" and not above:
        return "bearish"
    if regime == "amplifying" and flip is None:
        return "bearish"
    return "mixed"


def board(days_back: int = 5) -> dict:
    """The cross-sectional GEX board: latest ledger date's rows bucketed
    bullish / bearish / mixed, each bucket sorted by |net GEX| descending.
    Falls back through the last `days_back` dates so a missed cron never
    blanks the page. {} DB -> empty board with a reason."""
    coll = _coll()
    empty = {"as_of_date": None, "bullish": [], "bearish": [], "mixed": [],
             "counts": {"bullish": 0, "bearish": 0, "mixed": 0},
             "note": None}
    if coll is None:
        return dict(empty, note="mongo unavailable")
    dates = sorted(coll.distinct("date_et"), reverse=True)[:days_back]
    if not dates:
        return dict(empty, note="no GEX snapshots yet — run options.gex_history")
    latest = dates[0]
    rows = list(coll.find({"date_et": latest}, {"_id": 0}))
    out = {"bullish": [], "bearish": [], "mixed": []}
    for r in rows:
        out[board_bucket(r)].append(r)
    for bucket in out.values():
        bucket.sort(key=lambda r: abs(r.get("net_gex_dollars") or 0),
                    reverse=True)
    # Legacy = the KEY is absent (pre-2026-08 rows). A PRESENT None means a
    # one-sided gamma profile — legitimate, not stale (MU-style all-negative).
    legacy = sum(1 for r in rows if "flip_strike" not in r)
    return {
        "as_of_date": latest,
        **out,
        "counts": {k: len(v) for k, v in out.items()},
        "note": ("%d of %d rows predate the flip field (bucketed on regime "
                 "alone — the next snapshot fills them in)"
                 % (legacy, len(rows)) if legacy else None),
    }


def snapshot_universe() -> list:
    """Portfolio + watchlists + SOIR BULLISH/WATCH + top SEPA. Deduped."""
    seen = []

    def _add(syms):
        for s in syms:
            t = (s or "").upper().strip()
            if t and t not in seen:
                seen.append(t)

    try:
        from options.scanner import _always_include_symbols
        _add(_always_include_symbols())
    except Exception as exc:
        log.debug("gex universe: always-include skipped: %s", exc)
    try:
        from watchlist import store as wl_store
        _add((e.get("ticker") or "") for e in wl_store.list_entries())
    except Exception as exc:
        log.debug("gex universe: watchlist store skipped: %s", exc)
    try:
        from options import soir as soir_mod
        rows = soir_mod.load_latest() or []
        _add(r.get("symbol") for r in rows
             if r.get("signal") in ("BULLISH", "WATCH"))
    except Exception as exc:
        log.debug("gex universe: soir signals skipped: %s", exc)
    try:
        from sepa import scanner as sepa_scanner
        latest = sepa_scanner.load_latest() or {}
        cands = sorted((latest.get("candidates") or []),
                       key=lambda c: -(c.get("score") or 0))
        _add(c.get("symbol") for c in cands[:TOP_SEPA_N])
        # Top day movers (2026-08-03, Ajay: "Why PLTR and SNAP are not in the
        # list they had earnings today") — earnings gappers and other big
        # movers join the universe even when no other tracker owns them.
        # Regular-session moves only; a post-close earnings pop shows up in
        # the NEXT session's scan, or immediately via the board's add-ticker.
        _add(top_movers(latest.get("all_results") or []))
    except Exception as exc:
        log.debug("gex universe: sepa top skipped: %s", exc)
    return seen[:MAX_UNIVERSE]


MOVER_MIN_ABS_PCT = 4.0
MOVER_TOP_N = 25


def top_movers(rows: list, n: int = MOVER_TOP_N,
               min_abs_pct: float = MOVER_MIN_ABS_PCT) -> list:
    """Symbols of the biggest |day-change| rows (>= min_abs_pct), largest
    first. Pure — unit-tested. Garbage day_change values are skipped."""
    scored = []
    for r in rows or []:
        try:
            chg = abs(float(r.get("day_change_pct")))
        except (TypeError, ValueError):
            continue
        sym = (r.get("symbol") or "").upper().strip()
        if sym and chg >= min_abs_pct:
            scored.append((chg, sym))
    scored.sort(reverse=True)
    return [s for _, s in scored[:n]]


def add_symbol(symbol: str) -> Optional[dict]:
    """Compute + upsert ONE symbol into today's board (the board page's
    add-ticker box; also how an after-hours earnings name gets on the board
    before any scan sees the move). Returns the stored row + its bucket, or
    None when Massive has no chain."""
    coll = _coll()
    if coll is None:
        return None
    from options import opex
    sym = (symbol or "").upper().strip()
    if not sym:
        return None
    d = _et_date()
    row = slim_row(sym, opex.compute_opex(sym), d)
    if row is None:
        return None
    coll.update_one({"_id": f"{sym}:{d}"}, {"$set": row}, upsert=True)
    return dict(row, bucket=board_bucket(row))


def run(workers: int = 8) -> dict:
    """One daily sweep: compute_opex per universe name, upsert slim rows.
    Threaded (2026-07-17) so the board's on-demand refresh finishes in ~20s
    instead of minutes; the scanner already runs 20 workers on the options
    key, so 8 is well inside the budget."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "no mongo"}
    from concurrent.futures import ThreadPoolExecutor
    from options import opex
    d = _et_date()
    syms = snapshot_universe()
    n_ok = n_fail = 0

    def _one(sym):
        try:
            return sym, slim_row(sym, opex.compute_opex(sym), d)
        except Exception as exc:                   # noqa: BLE001
            log.debug("gex snapshot failed %s: %s", sym, exc)
            return sym, None

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        results = list(ex.map(_one, syms))
    for sym, row in results:
        if row is None:
            n_fail += 1
            continue
        try:
            coll.update_one({"_id": f"{sym}:{d}"}, {"$set": row}, upsert=True)
            n_ok += 1
        except Exception as exc:
            log.warning("gex snapshot upsert failed %s: %s", sym, exc)
            n_fail += 1
    log.info("gex_history: %d recorded, %d skipped (of %d) for %s",
             n_ok, n_fail, len(syms), d)
    return {"ok": True, "date_et": d, "recorded": n_ok, "skipped": n_fail,
            "universe": len(syms)}


def snapshot_for(symbols: list, max_age_days: int = 7) -> dict:
    """{symbol: latest slim row} for a set of symbols, one aggregation.

    Feeds the demand-zone boards' 🧲 chips (Ajay 2026-08-27: "add the gex
    chips to the demand zone tabs"). Latest row PER SYMBOL — a name that
    missed yesterday's 17:50 snapshot still answers with its last one —
    capped at `max_age_days` calendar days so a delisted or long-dropped
    name never wears a stale regime. Rows are POST-CLOSE snapshots (the
    standing lookahead rule): a date-D row describes D's close, so a board
    viewed on D+1 intraday is reading yesterday's dealer book, and says so
    via the date the caller surfaces. Returns {} on any failure — chips
    are decoration, never worth an error."""
    from datetime import date, timedelta

    coll = _coll()
    syms = sorted({str(s).upper() for s in (symbols or []) if s})
    if coll is None or not syms:
        return {}
    floor = (date.today() - timedelta(days=max_age_days)).isoformat()
    try:
        rows = coll.aggregate([
            {"$match": {"symbol": {"$in": syms}, "date_et": {"$gte": floor}}},
            {"$sort": {"symbol": 1, "date_et": -1}},
            {"$group": {"_id": "$symbol", "row": {"$first": "$$ROOT"}}},
            {"$replaceRoot": {"newRoot": "$row"}},
            {"$project": {"_id": 0}},
        ])
        return {r["symbol"]: r for r in rows if r.get("symbol")}
    except Exception as exc:
        log.warning("gex snapshot_for failed: %s", exc)
        return {}


def series(symbol: str, days: int = 90) -> list:
    """Stored daily rows for one symbol, oldest→newest."""
    coll = _coll()
    if coll is None:
        return []
    try:
        rows = list(coll.find({"symbol": symbol.upper()},
                              sort=[("date_et", -1)]).limit(days))
        for r in rows:
            r.pop("_id", None)
        return list(reversed(rows))
    except Exception as exc:
        log.warning("gex series read failed: %s", exc)
        return []


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    r = run()
    log.info("GEX-HISTORY: %s", r)
    sys.exit(0 if r.get("ok") else 1)
