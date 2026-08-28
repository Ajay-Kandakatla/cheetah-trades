"""Live watcher: push when a name reaches its Gabbar band.

Ajay 2026-08-27: "I wanna see the one approaching too I missed the Adobe
today man it was a good explosive bounce can you do something about that
so I don't miss." (ADBE itself has NO Gabbar level — it is one of the
author's 13 empty stubs — but the miss generalises: nobody watches the
curated levels intraday, so a touch only gets seen if he happens to open
the tab.)

What fires
----------
For every covered name (catalysts/gabbar_levels.BANDS, the author's 66):
price INSIDE a band, or within APPROACH_PCT of a band edge, pushes ONCE
per (ticker, band, ET day). Approaching from either side fires — a bounce
entry and a fade-through-to-deeper-band both start with "price is at the
level".

Noise rules (the same discipline as every other push here)
----------------------------------------------------------
* Kind = ``pivot_alert`` — "price at a buy zone" is exactly that kind's
  meaning, and the standing 2026-06-24 keep-set gains NO new kinds.
* Bonde gate: declining/weak-sales names never page (the falling-knife
  rule the boards enforce); unknown sales fire but say so — VOO has no
  quarterly revenue and it is still his curated level.
* Dedup is per band, not per day-of-noise: touching the aggressive band
  at 10:00 and the conservative 1 band at 14:00 are two different facts.
* Outside 9:32-16:00 ET the module refuses to run, so the cron window
  can be generous.

Thresholds
----------
APPROACH_PCT = 1.0 — tighter than the boards' 3% NEAR_PCT on purpose: a
board answers "what should I look at", a phone buzz answers "look NOW",
and 3% of drift pages far too early.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("catalysts.gabbar_watch")

ET = ZoneInfo("America/New_York")
APPROACH_PCT = 1.0


def _now_et() -> datetime:
    return datetime.now(tz=ET)


def in_session(now: Optional[datetime] = None) -> bool:
    now = now or _now_et()
    if now.weekday() >= 5:
        return False
    hm = now.hour * 60 + now.minute
    return (9 * 60 + 32) <= hm <= (16 * 60)


# --------------------------------------------------------------------------
# Pure reads — testable without prices, Mongo, or push
# --------------------------------------------------------------------------
def band_proximity(last: float, bands: list) -> list:
    """Every band `last` is at: [{idx, label, lo, hi, state, dist_pct}] for
    bands where state is "in" or within APPROACH_PCT of an edge. Empty list
    when price is far from everything — which is almost always."""
    out = []
    if not last or last <= 0:
        return out
    for i, b in enumerate(bands or []):
        try:
            lo, hi = float(b["lo"]), float(b["hi"])
        except (KeyError, TypeError, ValueError):
            continue
        label = b.get("label") or f"band {i + 1}"
        if lo <= last <= hi:
            out.append({"idx": i, "label": label, "lo": lo, "hi": hi,
                        "state": "in", "dist_pct": 0.0})
            continue
        edge = lo if last < lo else hi
        dist = abs(last - edge) / last * 100.0
        if dist <= APPROACH_PCT:
            out.append({"idx": i, "label": label, "lo": lo, "hi": hi,
                        "state": "approaching", "dist_pct": round(dist, 2)})
    return out


def should_alert(hit: dict, sales: Optional[dict]) -> tuple:
    """(fire, note) for one band hit. Bonde-failing names never page —
    the board's falling-knife rule, applied to the phone."""
    tier = (sales or {}).get("tier")
    if sales and sales.get("score") is not None and tier in ("declining", "weak"):
        return False, f"suppressed — sales {tier}"
    note = "" if sales and sales.get("score") is not None else " · sales unknown"
    return True, note


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------
def _already_sent(db, ticker: str, band_idx: int, date_key: str) -> bool:
    return bool(db.gabbar_watch_state.find_one(
        {"ticker": ticker, "band_idx": band_idx, "date_key": date_key}))


def _record_sent(db, ticker: str, band_idx: int, date_key: str, hit: dict) -> None:
    db.gabbar_watch_state.update_one(
        {"ticker": ticker, "band_idx": band_idx, "date_key": date_key},
        {"$set": {"hit": hit, "sent_at": _now_et().isoformat()}}, upsert=True)


def check_once(*, push: bool = True, force: bool = False) -> dict:
    """One pass over every covered name. `force` skips the session gate for
    in-container smoke tests only — the cron never passes it."""
    if not force and not in_session():
        return {"ran": False, "reason": "outside RTH"}

    from catalysts import gabbar_levels as GL
    from portfolio.alerts import _resolve_owner
    from portfolio.store import _get_db
    from sepa import prices, research

    covered = GL.list_covered_symbols()
    live = {}
    try:
        live = prices.bulk_live_prices(covered) or {}
    except Exception as exc:
        log.warning("gabbar-watch: live prices failed: %s", exc)
        return {"ran": False, "reason": f"live prices failed: {exc}"}

    snaps = {}
    try:
        snaps = research.sales_snapshot(covered)
    except Exception as exc:
        log.warning("gabbar-watch: sales snapshot failed: %s", exc)

    db = _get_db()
    owner = _resolve_owner()
    date_key = _now_et().date().isoformat()
    hits, pushed, suppressed = [], 0, 0
    for sym in covered:
        last = (live.get(sym) or {}).get("price")
        payload = GL.get_bands(sym)
        if not last or not payload:
            continue
        for hit in band_proximity(float(last), payload.get("bands") or []):
            fire, note = should_alert(hit, (snaps.get(sym) or {}).get("sales"))
            rec = {**hit, "ticker": sym, "price": float(last)}
            hits.append(rec)
            if not fire:
                suppressed += 1
                continue
            if not push or _already_sent(db, sym, hit["idx"], date_key):
                continue
            body = (f"{sym} ${float(last):g} "
                    + ("inside" if hit["state"] == "in"
                       else f"{hit['dist_pct']:g}% from")
                    + f" Gabbar {hit['label']} (${hit['lo']:g}–{hit['hi']:g})"
                    + note)
            try:
                from push import sender as _push
                _push.send_to_user(owner, {
                    "title": "🎯 At a Gabbar level",
                    "body": body,
                    "data": {"url": "/chart-maps?tab=gabbar"},
                }, kind="pivot_alert")
                _record_sent(db, sym, hit["idx"], date_key, rec)
                pushed += 1
            except Exception as exc:
                log.warning("gabbar-watch: push for %s failed: %s", sym, exc)

    return {"ran": True, "date": date_key, "checked": len(covered),
            "hits": hits, "pushed": pushed, "suppressed": suppressed}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    out = check_once()
    log.info("GABBAR-WATCH: ran=%s hits=%d pushed=%s",
             out.get("ran"), len(out.get("hits") or []), out.get("pushed"))
