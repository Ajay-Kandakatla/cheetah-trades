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
* Bonde read: NOTHING is suppressed (Ajay 2026-08-27, "dont suppress
  show with a chip") — declining/weak-sales names page WITH the knife
  warning in the message; unknown sales fire but say so — VOO has no
  quarterly revenue and it is still his curated level.
* Dedup is per band, not per day-of-noise: touching the aggressive band
  at 10:00 and the conservative 1 band at 14:00 are two different facts.
* Outside 9:32-16:00 ET the module refuses to run, so the cron window
  can be generous.

Thresholds
----------
NEAR_PCT = 3.0 (added 2026-09-03, "I need a notifications when Gabbar levels
are reaching Demand zone") — a second, EARLIER tier: price ABOVE a band,
within 3% of its top and down on the day pushes "🎯 Nearing a Gabbar level"
once per (ticker, band, day), separately from the touch below, so the
heads-up at 10:00 never eats the arrival at 14:00. Above-only + falling on
purpose: from below is a fade into supply, flat/up is departing.
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
NEAR_PCT = 3.0        # "nearing" tier: above the band, falling (Ajay 2026-09-03)


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
def _falling(change_pct) -> bool:
    try:
        return change_pct is not None and float(change_pct) < 0
    except (TypeError, ValueError):
        return False


def band_proximity(last: float, bands: list, change_pct=None) -> list:
    """Every band `last` is at: [{idx, label, lo, hi, state, dist_pct}] for
    bands where state is "in", "approaching" (within APPROACH_PCT of an edge,
    either side) or "near" (ABOVE the band, within NEAR_PCT of its top AND
    down on the day — Ajay 2026-09-03 "reaching Demand zone"; a flat or
    rising name at 2% is departing, and from below it is a fade into supply,
    so neither reads near). Empty list when price is far from everything —
    which is almost always. `change_pct` None = the near tier cannot be
    told and stays silent."""
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
        elif last > hi and dist <= NEAR_PCT and _falling(change_pct):
            out.append({"idx": i, "label": label, "lo": lo, "hi": hi,
                        "state": "near", "dist_pct": round(dist, 2)})
    return out


def should_alert(hit: dict, sales: Optional[dict]) -> tuple:
    """(fire, note) for one band hit. NOTHING is suppressed (Ajay
    2026-08-27: "dont suppress show with a chip") — a Bonde-failing name
    still pages, carrying the knife warning in the message itself, and an
    unknown one says it is unknown. He decides; the label travels."""
    tier = (sales or {}).get("tier")
    if sales and sales.get("score") is not None and tier in ("declining", "weak"):
        return True, f" · ⚠️ sales {tier} — knife risk"
    note = "" if sales and sales.get("score") is not None else " · sales unknown"
    return True, note


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------
def _tier_q(tier: str):
    # Pre-2026-09-03 docs have no tier and were all "at" — they still block
    # a second "at" push, never a "near" one.
    return {"$in": ["at", None]} if tier == "at" else tier


def _already_sent(db, ticker: str, band_idx: int, date_key: str, tier: str = "at") -> bool:
    return bool(db.gabbar_watch_state.find_one(
        {"ticker": ticker, "band_idx": band_idx, "date_key": date_key,
         "tier": _tier_q(tier)}))


def _record_sent(db, ticker: str, band_idx: int, date_key: str, hit: dict,
                 tier: str = "at") -> None:
    db.gabbar_watch_state.update_one(
        {"ticker": ticker, "band_idx": band_idx, "date_key": date_key, "tier": tier},
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
        chg = (live.get(sym) or {}).get("change_pct")
        for hit in band_proximity(float(last), payload.get("bands") or [], chg):
            fire, note = should_alert(hit, (snaps.get(sym) or {}).get("sales"))
            rec = {**hit, "ticker": sym, "price": float(last)}
            hits.append(rec)
            if not fire:                       # unreachable since 08-27; kept
                suppressed += 1                    # so a future rule has a seat
                continue
            tier = "near" if hit["state"] == "near" else "at"
            if not push or _already_sent(db, sym, hit["idx"], date_key, tier):
                continue
            where = ("inside" if hit["state"] == "in"
                     else f"{hit['dist_pct']:g}% above" if tier == "near"
                     else f"{hit['dist_pct']:g}% from")
            body = (f"{sym} ${float(last):g} {where}"
                    + f" Gabbar {hit['label']} (${hit['lo']:g}–{hit['hi']:g})"
                    + (f" · down {abs(float(chg)):g}% today" if tier == "near" else "")
                    + note)
            title = "🎯 Nearing a Gabbar level" if tier == "near" else "🎯 At a Gabbar level"
            try:
                from push import sender as _push
                _push.send_to_user(owner, {
                    "title": title,
                    "body": body,
                    "data": {"url": "/chart-maps?tab=gabbar"},
                }, kind="pivot_alert")
                _record_sent(db, sym, hit["idx"], date_key, rec, tier)
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
