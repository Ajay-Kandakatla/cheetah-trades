"""🚀 Explosive-growth demand alerts — a SEPARATE kind for a separate board.

Ajay 2026-09-11: *"Hot sector top growth stocks I need the same rules in demand
zone for these. I wanna know when ever these are in demand, separately just
trackers. I wanna keep adding during instituional orderblocks are present for
these... this is outside of regular supply and demand"*.

WHAT FIRES: a name on the 100/100 growth board (growth/tracker.py) whose LIVE
print ARRIVES at a tested demand band today, whose band FLOOR HAS NEVER BEEN
PIERCED (read on the session in progress), and that passes the same two
standing phone gates every other zone push passes:

  0. arrival              — demand_alerts.read(print, band, chg, prev_close)
                            is not None: the print is in / <= 1% above the
                            band and YESTERDAY closed outside that ring (the
                            identical rule the 🧲 pushes use)
  1. room_gate            — the first band overhead is >= 5% above the print
  2. demand_proximity_gate— the print sits between the band floor and 1% above
                            its top (not fallen through it)
  3. floor_held_gate      — `intact`, the ONE gate that measured (+8.6pp win,
                            n=31,861), re-read LIVE with the session's low

THE PRINT IS LIVE (review 2026-09-14, finding 3). Until then this pass rang on
the board row's stored `price` and `zone.in_band` — Friday's close on a
Sunday-built board — with no freshness check, no arrival rule and no session
window: HHH re-fired every day on Friday's price while it sat BELOW its band.
Now: one `prices.bulk_snapshot` per pass, the print through
zone_bounce_alerts.print_from_snapshot (its STALE_PRINT_SEC window — the
5-minute siblings' rule; a stale trade is skipped and counted), the arrival
rule above, and the floor gate on the live low. The stored row is kept for the
GROWTH NUMBERS only (sales / qEPS / warnings). Session window =
demand_alerts.in_session (RTH 9:32-16:00 ET on trading days), the 🧲 pass this
one mirrors; the 09:00 and 09:15 cron ticks now say "outside RTH".

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
from supply_demand import demand_alerts as DA
from supply_demand.zone_bounce_alerts import print_from_snapshot

log = logging.getLogger("growth.alerts")

ET = ZoneInfo("America/New_York")
KIND = "growth_demand_alert"
STATE_COLL = "growth_alert_state"
OWNER = "ajaykandakatla@gmail.com"
MAX_INDIVIDUAL = 4               # the rest share one digest, like every other kind
SOURCE = "growth_alerts"         # stamped on every dedupe claim this pass makes


def _now() -> datetime:
    return datetime.now(ET)


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _db():
    try:
        from portfolio.store import _get_db
        return _get_db()
    except Exception as exc:                                   # noqa: BLE001
        log.warning("growth.alerts: no mongo: %s", exc)
        return None


def _state_coll():
    db = _db()
    return db[STATE_COLL] if db is not None else None


def _state_key(symbol: str, band: dict, day: str) -> str:
    lo = round(float(band.get("lo") or 0), 2)
    hi = round(float(band.get("hi") or 0), 2)
    return "%s|%.2f-%.2f|%s" % (symbol.upper(), lo, hi, day)


def _seen(coll, keys: list) -> set:
    """The subset of `keys` already claimed — one `$in` read, never a find_one
    per name. A read failure is the empty set (push again rather than never)."""
    if coll is None or not keys:
        return set()
    try:
        return {str(d["_id"]) for d in coll.find({"_id": {"$in": sorted(set(keys))}}, {"_id": 1})}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("growth.alerts: dedupe read failed: %s", exc)
        return set()


def _snapshot_for(symbols: list) -> dict:
    """ONE bulk snapshot for the whole board (never a call per name)."""
    if not symbols:
        return {}
    try:
        from sepa import prices
        return prices.bulk_snapshot(sorted(set(symbols))) or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("growth.alerts: snapshot failed: %s", exc)
        return {}


def _hit_txt(hit: Optional[dict]) -> str:
    if isinstance(hit, dict) and hit.get("state") == "above":
        return "%g%% above demand" % float(hit.get("dist_pct") or 0.0)
    return "in demand"


def message(row: dict, band: dict, room: Optional[dict], hit: Optional[dict] = None) -> dict:
    """The push body. Leads with the growth, then the level, then the warnings —
    a name the engine will refuse to buy says so in the body, never silently.
    `row["price"]` is the LIVE print the pass read (2026-09-14), never the
    board's stored close."""
    sym = row["symbol"]
    sales = row.get("sales_growth_pct")
    eps = row.get("q_eps_growth_pct")
    px = row.get("price")

    parts = []
    if px:
        parts.append("$%g" % px)
    parts.append("%s $%g–%g" % (_hit_txt(hit), float(band["lo"]), float(band["hi"])))
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


def _scan(rows: list, snapshot: dict, now: datetime) -> tuple:
    """(items, counts): every board row whose LIVE print arrives at a demand
    band and clears every gate, richest sales first. No push, no state write."""
    now_ts = now.timestamp()
    day = now.astimezone(ET).date()
    counts = {"rows": len(rows), "unpriced": 0, "stale_print": 0, "unknown_prev": 0,
              "no_bands": 0, "no_arrival": 0, "skipped_room": 0, "skipped_proximity": 0,
              "skipped_floor": 0}
    out = []
    for row in rows:
        sym = str(row.get("symbol") or "").upper()
        if not sym:
            continue
        snap = snapshot.get(sym)
        if not snap:
            counts["unpriced"] += 1
            continue
        px, stale = print_from_snapshot(snap, now_ts)          # zone_bounce_alerts.STALE_PRINT_SEC
        if stale:
            counts["stale_print"] += 1
            continue
        prev = _f(snap.get("prev_day_close"))
        if not prev or prev <= 0:
            counts["unknown_prev"] += 1                         # cannot tell arrival from residence
            continue
        bands = _bands_for(sym)
        demand = [b for b in bands if str(b.get("kind") or "demand").lower() == "demand"
                  and _f(b.get("lo")) and _f(b.get("hi"))]
        if not demand:
            counts["no_bands"] += 1
            continue
        # The arrival rule the 🧲 pushes use (demand_alerts.read): in / <= 1%
        # above the band, yesterday closed outside that ring. The containing
        # band wins over one the print sits above; then the nearest.
        hits = []
        for b in demand:
            h = DA.read(px, b, snap.get("change_pct"), prev)
            if h:
                hits.append((0 if h.get("state") == "in" else 1, float(h.get("dist_pct") or 0.0), b, h))
        if not hits:
            counts["no_arrival"] += 1
            continue
        hits.sort(key=lambda t: (t[0], t[1]))
        _, _, band, hit = hits[0]
        ok_room, room = AG.room_gate(px, bands)
        if not ok_room:
            counts["skipped_room"] += 1
            continue
        if not AG.demand_proximity_gate(px, band):
            counts["skipped_proximity"] += 1
            continue
        # The ONE gate that measured — read LIVE: the session's low and print
        # are merged into the daily frame so a floor swept this morning is
        # not "intact" (alert_gates.with_session_bar, 2026-09-14). Fails closed.
        day_low = _f(snap.get("low"))
        if not AG.floor_held_gate(band, sym, day_low=day_low, last=px, day=day):
            counts["skipped_floor"] += 1
            continue
        out.append({"row": dict(row, price=float(px), price_source="live"),
                    "band": band, "room": room, "hit": hit, "last": float(px),
                    "day_low": day_low, "prev_close": prev})
    out.sort(key=lambda i: -(i["row"].get("sales_growth_pct") or 0.0))
    return out, counts


def candidates(rows: Optional[list] = None, *, snapshot: Optional[dict] = None,
               now: Optional[datetime] = None) -> list:
    """Every board row whose LIVE print arrives at a demand band and clears
    every gate, richest sales first. `snapshot` = a `prices.bulk_snapshot`
    map (fetched ONCE here when None). No push, no state write. This is what
    the tests call."""
    if rows is None:
        from growth import tracker as T
        rows = (T.board() or {}).get("rows") or []
    now = now or _now()
    if snapshot is None:
        snapshot = _snapshot_for([r.get("symbol") for r in rows if r.get("symbol")])
    return _scan(rows, snapshot, now)[0]


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


def _terminal(res: Optional[dict]) -> bool:
    """Delivered, or nobody targeted — 'do not retry today'; a transport
    failure releases the claim (demand_alerts._terminal, same rule)."""
    res = res or {}
    return (res.get("sent") or 0) > 0 or (res.get("total_targets") or 0) == 0


def run(dry_run: bool = False, *, force: bool = False, now: Optional[datetime] = None,
        rows: Optional[list] = None, snapshot: Optional[dict] = None, coll=None) -> dict:
    """One pass. Returns a summary; sends at most MAX_INDIVIDUAL individual
    pushes plus one digest, once per symbol per band per day.

    Session window (2026-09-14): demand_alerts.in_session — RTH 9:32-16:00 ET
    on trading days, the window of the 🧲 pass this one mirrors. `force`
    skips it for in-container smoke tests only. Dedupe is claim-then-send
    (demand_alerts.claim_key); a send that fails in transport releases the
    key so the next pass retries — until 2026-09-14 the key was remembered
    even when the push raised."""
    now = now or _now()
    if not force and not DA.in_session(now):
        return {"kind": KIND, "ran": False, "dry_run": dry_run,
                "reason": "outside RTH (%s-%s ET, demand_alerts.in_session)"
                          % (DA.SESSION_OPEN.strftime("%H:%M"), DA.SESSION_CLOSE.strftime("%H:%M"))}
    day = now.astimezone(ET).date().isoformat()
    if rows is None:
        from growth import tracker as T
        rows = (T.board() or {}).get("rows") or []
    if snapshot is None:
        snapshot = _snapshot_for([r.get("symbol") for r in rows if r.get("symbol")])
    items, counts = _scan(rows, snapshot, now)
    if coll is None and not dry_run:
        coll = _state_coll()
    for it in items:
        it["key"] = _state_key(it["row"]["symbol"], it["band"], day)
    seen = _seen(coll, [it["key"] for it in items]) if not dry_run else set()
    fresh = [it for it in items if it["key"] not in seen]

    sent, digest, claimed_elsewhere = 0, [], 0
    singles, spill = fresh[:MAX_INDIVIDUAL], fresh[MAX_INDIVIDUAL:]
    if not dry_run:
        from push import sender
        for it in singles:
            doc = {"symbol": it["row"]["symbol"], "band": {"lo": it["band"]["lo"], "hi": it["band"]["hi"]},
                   "last": it["last"], "at": now.isoformat(), "source": SOURCE}
            if not DA.claim_key(coll, it["key"], doc):
                claimed_elsewhere += 1
                continue
            try:
                res = sender.send_to_user(OWNER, message(it["row"], it["band"], it["room"],
                                                         hit=it.get("hit")), kind=KIND)
            except Exception as exc:                           # noqa: BLE001
                log.warning("growth.alerts: push failed for %s: %s", it["row"]["symbol"], exc)
                DA.release_key(coll, it["key"])
                continue
            if _terminal(res):
                sent += 1
            else:
                DA.release_key(coll, it["key"])
        for it in spill:
            doc = {"symbol": it["row"]["symbol"], "band": {"lo": it["band"]["lo"], "hi": it["band"]["hi"]},
                   "last": it["last"], "at": now.isoformat(), "source": SOURCE, "digest": True}
            if DA.claim_key(coll, it["key"], doc):
                digest.append(it)
            else:
                claimed_elsewhere += 1
        if digest:
            try:
                res = sender.send_to_user(OWNER, digest_message(digest), kind=KIND)
            except Exception as exc:                           # noqa: BLE001
                log.warning("growth.alerts: digest push failed: %s", exc)
                res = None
            if not _terminal(res):
                for it in digest:
                    DA.release_key(coll, it["key"])
    else:
        sent, digest = len(singles), spill

    return {"kind": KIND, "ran": True, "date": day, "candidates": len(items), "fresh": len(fresh),
            "individual": sent, "digest": len(digest), "claimed_elsewhere": claimed_elsewhere,
            "dry_run": dry_run, **counts}
