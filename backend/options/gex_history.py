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
        "reliability": opex_out.get("gex_reliability"),
        "expiration_date": opex_out.get("expiration_date"),
        "recorded_at": int(time.time()),
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
    except Exception as exc:
        log.debug("gex universe: sepa top skipped: %s", exc)
    return seen[:MAX_UNIVERSE]


def run() -> dict:
    """One daily sweep: compute_opex per universe name, upsert slim rows."""
    coll = _coll()
    if coll is None:
        return {"ok": False, "reason": "no mongo"}
    from options import opex
    d = _et_date()
    syms = snapshot_universe()
    n_ok = n_fail = 0
    for sym in syms:
        try:
            row = slim_row(sym, opex.compute_opex(sym), d)
        except Exception as exc:
            log.debug("gex snapshot failed %s: %s", sym, exc)
            row = None
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
