"""🚀 Explosive-growth demand alerts — a SEPARATE kind for a separate board.

Ajay 2026-09-11: *"Hot sector top growth stocks I need the same rules in demand
zone for these. I wanna know when ever these are in demand, separately just
trackers. I wanna keep adding during instituional orderblocks are present for
these... this is outside of regular supply and demand"*.

WHAT FIRES: a name on the 100/100 growth board (growth/tracker.py) that is
inside a tested demand band today, whose band FLOOR HAS NEVER BEEN PIERCED, and
that passes the same two standing phone gates every other zone push passes:

  1. room_gate            — the first band overhead is >= 5% above the print
  2. demand_proximity_gate— the print sits between the band floor and 1% above
                            its top (not fallen through it)
  3. floor_held_gate      — `intact`, the ONE gate that measured (+8.6pp win,
                            n=31,861)

WHY THE STANDING GATES APPLY EVEN THOUGH THE BOARD IS "OUTSIDE REGULAR S/D":
the board is separate, the SCREEN is separate, the alert KIND is separate — but
his 2026-09-05 rule ("Need only alerts on stocks that have atleast 5% to Supply
and also <1% bounce from demand zone") is about what reaches his PHONE, and it
is not weakened by a stock also having good sales. A 100% sales grower with 2%
of room overhead is still a bad entry.

WHAT DOES NOT GATE: the market cap (this board has no cap floor, his explicit
call) and the order block (display only — the 2026-09-04 ICT study measured
+0.03R over 6,004 signals against placebo). The push BODY still says when the
engine will refuse to buy the name, so a $0.45 or a $218M name reaches him
labelled rather than silently.

ONE PUSH PER SYMBOL PER BAND PER DAY.

NOTHING HERE IS BACKTESTED. The 100/100 screen has never been measured forward.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from supply_demand import alert_gates as AG

log = logging.getLogger("growth.alerts")

ET = ZoneInfo("America/New_York")
KIND = "growth_demand_alert"
STATE_COLL = "growth_alert_state"
OWNER = "ajaykandakatla@gmail.com"
MAX_INDIVIDUAL = 4               # the rest share one digest, like every other kind


def _db():
    try:
        from portfolio.store import _get_db
        return _get_db()
    except Exception as exc:                                   # noqa: BLE001
        log.warning("growth.alerts: no mongo: %s", exc)
        return None


def _state_key(symbol: str, band: dict, day: str) -> str:
    lo = round(float(band.get("lo") or 0), 2)
    hi = round(float(band.get("hi") or 0), 2)
    return "%s|%.2f-%.2f|%s" % (symbol.upper(), lo, hi, day)


def _already(key: str) -> bool:
    db = _db()
    if db is None:
        return False
    try:
        return db[STATE_COLL].find_one({"_id": key}) is not None
    except Exception:                                          # noqa: BLE001
        return False


def _remember(key: str) -> None:
    db = _db()
    if db is None:
        return
    try:
        db[STATE_COLL].update_one({"_id": key},
                                  {"$set": {"at": datetime.now(ET).isoformat()}},
                                  upsert=True)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("growth.alerts: state write failed: %s", exc)


def message(row: dict, band: dict, room: Optional[dict]) -> dict:
    """The push body. Leads with the growth, then the level, then the warnings —
    a name the engine will refuse to buy says so in the body, never silently."""
    sym = row["symbol"]
    sales = row.get("sales_growth_pct")
    eps = row.get("q_eps_growth_pct")
    px = row.get("price")

    parts = []
    if px:
        parts.append("$%g" % px)
    parts.append("in demand $%g–%g" % (float(band["lo"]), float(band["hi"])))
    if band.get("touches"):
        parts.append("tested %dx" % int(band["touches"]))
    parts.append("floor intact")
    room_s = AG.room_txt(room)
    if room_s:
        parts.append(room_s)
    if row.get("zone", {}).get("order_block"):
        parts.append("order block present (display only — measured no edge)")
    for w in (row.get("warnings") or []):
        parts.append(w)

    title = "🚀 %s — sales %+.0f%%, qEPS %+.0f%% — at demand" % (
        sym, sales or 0.0, eps or 0.0)
    return {"title": title, "body": " · ".join(parts), "ticker": sym,
            "url": "/chart-maps?tab=growth&symbol=%s" % sym, "kind": KIND}


def digest_message(items: list) -> dict:
    syms = ", ".join(i["row"]["symbol"] for i in items)
    return {"title": "🚀 %d growth names at demand" % len(items),
            "body": syms, "url": "/chart-maps?tab=growth", "kind": KIND}


def candidates(rows: Optional[list] = None) -> list:
    """Every board row that clears all three gates, richest sales first.

    Pure — no push, no state write. This is what the tests call."""
    if rows is None:
        from growth import tracker as T
        rows = (T.board() or {}).get("rows") or []

    out = []
    for row in rows:
        zone = row.get("zone") or {}
        band = zone.get("band")
        if not zone.get("in_band") or not band:
            continue
        if not zone.get("intact"):
            continue                       # the one gate that measured
        px = row.get("price")
        if not px:
            continue
        bands = _bands_for(row["symbol"])
        ok_room, room = AG.room_gate(px, bands)
        if not ok_room:
            continue
        if not AG.demand_proximity_gate(px, band):
            continue
        out.append({"row": row, "band": band, "room": room})
    out.sort(key=lambda i: -(i["row"].get("sales_growth_pct") or 0.0))
    return out


def _bands_for(symbol: str) -> list:
    db = _db()
    if db is None:
        return []
    try:
        doc = db.zone_store.find_one({"symbol": symbol.upper()},
                                     sort=[("date", -1)]) or {}
    except Exception:                                          # noqa: BLE001
        return []
    return doc.get("bands") or []


def run(dry_run: bool = False) -> dict:
    """One pass. Returns a summary; sends at most MAX_INDIVIDUAL individual
    pushes plus one digest, once per symbol per band per day."""
    day = datetime.now(ET).date().isoformat()
    items = candidates()
    fresh = [i for i in items
             if not _already(_state_key(i["row"]["symbol"], i["band"], day))]

    sent, digest = 0, []
    for idx, it in enumerate(fresh):
        key = _state_key(it["row"]["symbol"], it["band"], day)
        if idx < MAX_INDIVIDUAL:
            if not dry_run:
                try:
                    from push import sender
                    sender.send_to_user(OWNER, message(it["row"], it["band"],
                                                       it["room"]), kind=KIND)
                except Exception as exc:                       # noqa: BLE001
                    log.warning("growth.alerts: push failed for %s: %s",
                                it["row"]["symbol"], exc)
            sent += 1
        else:
            digest.append(it)
        if not dry_run:
            _remember(key)

    if digest and not dry_run:
        try:
            from push import sender
            sender.send_to_user(OWNER, digest_message(digest), kind=KIND)
        except Exception as exc:                               # noqa: BLE001
            log.warning("growth.alerts: digest push failed: %s", exc)

    return {"kind": KIND, "candidates": len(items), "fresh": len(fresh),
            "individual": sent, "digest": len(digest), "dry_run": dry_run}
