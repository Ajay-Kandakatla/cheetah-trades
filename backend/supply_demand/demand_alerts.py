"""Demand-zone approach alerts — $1B+ names at or nearing a tested demand band.

Ajay 2026-09-03: "I need a notifications when Gabbar levels are reaching
Demand zone like NTAP today.. Also other big companies billion or atleast
bigger than a billion coming close to Demand zones."

The curated half lives in catalysts/gabbar_watch.py (its NEAR tier was added
the same day). This module is the universe half: every name the demand board
already qualified — ``approaching_rows`` (falling toward a tested band, see
supply_demand/demand_reentry.approaching_read) and ``rows`` (back inside one)
— re-read against the LIVE print every 5 minutes, gated to market cap >= $1B.

Why the board and not a fresh zone scan
---------------------------------------
The board IS the app's definition of "a demand zone worth the phone":
MIN_TOUCHES / MIN_ZONE_STRENGTH, the falling-knife guard, trend_ok and the
5-bar drift predicate (docs/supply_demand/demand_reentry_methodology.md).
Re-deriving zones per symbol here would be a second definition, and a cold
full-universe zone pass is minutes. The board is fetched OVER HTTP from the
api container — its cache is process-local (crontab note of 2026-08-15) —
exactly as orderflow/trade_flash.py does.

Tiers (pure: ``read``)
----------------------
AT   — price inside the band, or <= AT_PCT above its top. ONE push per
       (symbol, band, ET day): "look NOW".
NEAR — (AT_PCT, NEAR_PCT] above the top AND down on the day. ONE digest push
       per run for all fresh names (trade_flash discipline: five names in one
       poll is one notification, not five), each name once per (symbol, band,
       day). Flat or up on the day is departing, not approaching.
Below the band is a breakdown, not an approach — never fires here.

ARRIVALS ONLY. Both tiers also require yesterday's close to have been OUTSIDE
the ring (prev close more than AT_PCT / NEAR_PCT above the top). The first
dry run (2026-09-03 after the close) found 58 names already sitting inside a
band — the reached board's whole population — which would have been 58
pushes at 9:33. A name that closed in the band yesterday is the board's
business; the phone gets the day it ARRIVES. Unknown prev close = silent
(counted as unknown_prev), never a guess.

Phone gate (Ajay 2026-09-05, alert_gates.py): "Need only alerts on stocks
that have atleast 5% to Supply and also <1% bounce from demand zone". AT was
already the <=1% tier (AT_PCT = 1.0; the tier measures (px-hi)/px, the gate
px <= hi*1.01 — an AT hit in the (0.99%, 1.0%] sliver between the two bases is
counted skipped_proximity: silence, never a wrong push); NEAR (1-3% above) is
looser than 1%, so it is still read and listed in `hits` / counted in `near`
but no longer pushed (skipped_proximity). Every push also wants at least
ALERT_MIN_ROOM_PCT (5%) from the print to the first UNBROKEN supply band in
the zone_store doc for the name (`store`, loaded once per pass); a name with
no store doc has an UNKNOWN room and stays silent (unknown_room) — "at least
5%" cannot be asserted about supply nobody measured. Boards unchanged.

Cap gate: catalysts/promo_circuit.market_caps_for (weekly shares cache × the
live print). Unknown cap is SKIPPED, not kept — the ask is "big companies",
and an ETF or a name the shares cache never saw is not a known-big company.
(The promo board keeps unknowns visible for the opposite reason: a hidden row
there is a hidden promotion.)

Kind = ``demand_alert`` — a NEW kind, like promo_alert (2026-09-02):
explicitly asked for, and separately mutable at /notifications if the
universe half gets loud. Nothing is suppressed on quality here: the board
already did that.

Configured price-structure method, NOT a book method. Decision support, not a
buy signal, not advice.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, time as dtime
from typing import Optional
from zoneinfo import ZoneInfo

from market_hours.reminder import is_market_day
from . import alert_gates as AG
from . import alert_status as AS

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
AT_PCT = 1.0                       # inside, or this close above the top → push
NEAR_PCT = 3.0                     # (AT_PCT, NEAR_PCT] above + falling → digest
MIN_CAP_USD = 1_000_000_000.0      # "billion or at least bigger than a billion"
KIND = "demand_alert"
STATE_COLL = "demand_alert_state"
DIGEST_MAX = 6                     # names spelled out in one digest body
MAX_SINGLES_PER_PASS = 4           # first pass after a deploy fired 14 singles at once
                                   # (2026-09-03 12:48); closest first, the rest ride the digest
BOARD_LIMIT = 500
BOARD_TIMEOUT_SEC = 30
SESSION_OPEN = dtime(9, 32)        # let the opening print settle
SESSION_CLOSE = dtime(16, 0)


def _now_et() -> datetime:
    return datetime.now(ET)


def in_session(now: Optional[datetime] = None) -> bool:
    """RTH 9:32-16:00 ET on NYSE trading days — weekends AND the house holiday
    calendar (market_hours.reminder.is_market_day; fix 2026-09-05)."""
    now = now or _now_et()
    et = now.astimezone(ET) if now.tzinfo is not None else now
    if not is_market_day(et):
        return False
    return SESSION_OPEN <= now.time() <= SESSION_CLOSE


# --------------------------------------------------------------------------
# Pure reads
# --------------------------------------------------------------------------
def _dist_above(px: float, hi: float) -> float:
    """% of price that `px` sits above the band top (negative inside/below)."""
    return (px - hi) / px * 100.0


def read(last, band: dict, change_pct=None, prev_close=None,
         at_pct: float = AT_PCT, near_pct: float = NEAR_PCT) -> Optional[dict]:
    """Where is `last` relative to one demand band? None = nothing to say.

    {"tier": "at",   "state": "in"|"above",  "dist_pct"}  inside / <= at_pct above
    {"tier": "near", "state": "falling",     "dist_pct"}  (at, near] above, down today
    Below the band (breakdown) and flat/up-on-the-day approaches are None.

    `prev_close` given = arrivals only: the tier fires only if yesterday's
    close was still OUTSIDE that tier's ring (more than at_pct / near_pct
    above the top). None = no arrival check (pure geometry).
    """
    try:
        last = float(last)
        lo, hi = float(band["lo"]), float(band["hi"])
    except (KeyError, TypeError, ValueError):
        return None
    if last <= 0 or hi <= 0 or lo > hi:
        return None
    was_at = was_near = False
    if prev_close is not None:
        try:
            pc = float(prev_close)
        except (TypeError, ValueError):
            pc = 0.0
        if pc <= 0:
            return None                        # cannot tell arrival from residence
        # Yesterday inside the band, or above it within the ring, = residence.
        # Under the floor is NOT residence: closing back inside today is a
        # reclaim, and a reclaim is an arrival.
        pdist = _dist_above(pc, hi)
        was_at = (lo <= pc <= hi) or (pc > hi and pdist <= at_pct)
        was_near = (lo <= pc <= hi) or (pc > hi and pdist <= near_pct)
    if lo <= last <= hi:
        return None if was_at else {"tier": "at", "state": "in", "dist_pct": 0.0}
    if last < lo:
        return None                            # under the floor: not an approach
    dist = _dist_above(last, hi)
    if dist <= at_pct:
        return None if was_at else {"tier": "at", "state": "above", "dist_pct": round(dist, 2)}
    if dist <= near_pct:
        if was_near:
            return None                        # was already near yesterday
        try:
            chg = None if change_pct is None else float(change_pct)
        except (TypeError, ValueError):
            chg = None
        if chg is not None and chg < 0:
            return {"tier": "near", "state": "falling", "dist_pct": round(dist, 2)}
    return None


def passes_cap(cap, floor: float = MIN_CAP_USD) -> bool:
    """Known AND >= floor. Unknown (None) fails — see the module docstring."""
    try:
        return cap is not None and float(cap) >= float(floor)
    except (TypeError, ValueError):
        return False


def candidates(board: Optional[dict]) -> dict:
    """{SYMBOL: {"name", "bands": [{lo, hi, touches, strength, source}]}}.

    approaching_rows carry the band under ``approaching.band`` (falls back to
    ``entry_zone``); reached ``rows`` carry it as ``entry_zone``. One band per
    (lo, hi) per symbol — a name on both boards with the same band is one fact.
    Empty when the board is missing or still warming.
    """
    out: dict = {}
    if not board:
        return out
    for source, key in (("approaching", "approaching_rows"), ("reentry", "rows")):
        for r in board.get(key) or []:
            sym = str(r.get("symbol") or "").upper()
            band = None
            if source == "approaching":
                band = (r.get("approaching") or {}).get("band")
            band = band or r.get("entry_zone")
            if not sym or not band or band.get("lo") is None or band.get("hi") is None:
                continue
            ent = out.setdefault(sym, {"name": r.get("name") or "", "bands": []})
            if any(b["lo"] == band["lo"] and b["hi"] == band["hi"] for b in ent["bands"]):
                continue
            ent["bands"].append({"lo": band["lo"], "hi": band["hi"],
                                 "touches": band.get("touches"),
                                 "strength": band.get("strength"),
                                 "source": source})
    return out


def state_key(symbol: str, band: dict, day: str, tier: str) -> str:
    """Fixed 2 dp (2026-09-05): ':g' collapsed two bands on a $10,000+ name into
    one key (zone_edge shares this key for its near-demand pushes)."""
    return f"{symbol}:{float(band['lo']):.2f}-{float(band['hi']):.2f}:{day}:{tier}"


def fmt_cap(cap) -> str:
    if cap is None:
        return "cap n/a"
    cap = float(cap)
    return f"${cap / 1e12:.1f}T" if cap >= 1e12 else f"${cap / 1e9:.1f}B"


def _band_txt(band: dict) -> str:
    return f"${float(band['lo']):g}–{float(band['hi']):g}"


def at_message(item: dict) -> dict:
    sym, hit, band = item["symbol"], item["hit"], item["band"]
    where = "in demand" if hit["state"] == "in" else f"{hit['dist_pct']:g}% above demand"
    tested = f"tested {int(band['touches'])}x" if band.get("touches") else "tested band"
    parts = [f"${float(item['last']):g}", tested]
    if "room" in item:                                    # the phone gate's read (2026-09-05)
        parts.append(AG.room_txt(item.get("room")))
    parts.append(fmt_cap(item.get("cap")))
    body = " · ".join(parts)
    if item.get("name"):
        body += f" · {item['name']}"
    # "kind" rides in the payload: push/history.py records payload["kind"], so
    # without it every 🧲 push logged as kind=None (found 2026-09-03).
    return {"title": f"🧲 {sym} {where} {_band_txt(band)}", "body": body,
            "url": f"/sepa/{sym}?tab=supply", "data": {"url": f"/sepa/{sym}?tab=supply"},
            "kind": KIND}


def digest_message(items: list) -> Optional[dict]:
    """One push for many names. NEAR items ("nearing demand") and any AT items
    that spilled past MAX_SINGLES_PER_PASS share it; the title says which."""
    if not items:
        return None
    items = sorted(items, key=lambda it: it["hit"]["dist_pct"])
    lead = items[0]["symbol"]
    has_at = any(it["hit"].get("tier") == "at" for it in items)
    head = "🧲 Demand zone — " if has_at else "🧲 Nearing demand — "
    title = head + lead + (f" +{len(items) - 1} more" if len(items) > 1 else "")
    lines = []
    for it in items[:DIGEST_MAX]:
        where = ("in demand" if it["hit"].get("state") == "in"
                 else f"{it['hit']['dist_pct']:g}% above")
        room = f" · {AG.room_txt(it.get('room'))}" if "room" in it else ""
        lines.append(f"{it['symbol']} ${float(it['last']):g} · {where} "
                     f"{_band_txt(it['band'])}{room} · {fmt_cap(it.get('cap'))}")
    if len(items) > DIGEST_MAX:
        lines.append(f"+{len(items) - DIGEST_MAX} more on the board")
    url = "/chart-maps?tab=zones&phase=approaching"
    return {"title": title, "body": "\n".join(lines), "url": url, "data": {"url": url},
            "kind": KIND}


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------
def fetch_board(base: Optional[str] = None, universe: str = "full",
                limit: int = BOARD_LIMIT, timeout: float = BOARD_TIMEOUT_SEC) -> Optional[dict]:
    """The demand board over HTTP from the api container; None when it is
    unreachable or still warming (a warming board is 'nothing to watch', not
    an error — the next 5-min pass reads the filled cache)."""
    base = base or os.getenv("INTERNAL_API_BASE", "http://api:8000")
    try:
        import requests
        r = requests.get(f"{base}/supply-demand/demand-reentry",
                         params={"universe": universe, "limit": limit},
                         headers={"X-User-Email": "cron@internal"}, timeout=timeout)
    except Exception as exc:
        log.warning("demand_alerts: board over HTTP failed: %s", exc)
        return None
    if r.status_code != 200:
        log.warning("demand_alerts: board HTTP %s", r.status_code)
        return None
    data = r.json() or {}
    if data.get("warming"):
        log.info("demand_alerts: board still warming — nothing to watch")
        return None
    return data


def _state_coll():
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[STATE_COLL] if db is not None else None
    except Exception as exc:
        log.warning("demand_alerts: no mongo for dedupe: %s", exc)
        return None


def _already(coll, key: str) -> bool:
    if coll is None:
        return False
    try:
        return coll.find_one({"_id": key}) is not None
    except Exception as exc:
        log.warning("demand_alerts: dedupe read failed: %s", exc)
        return False


def _record(coll, key: str, item: dict, now: datetime) -> None:
    if coll is None:
        return
    try:
        coll.update_one({"_id": key}, {"$set": {
            "symbol": item["symbol"], "tier": item["hit"]["tier"],
            "band": {"lo": item["band"]["lo"], "hi": item["band"]["hi"]},
            "last": item["last"], "dist_pct": item["hit"]["dist_pct"],
            "cap": item.get("cap"), "sent_at": now.isoformat()}}, upsert=True)
    except Exception as exc:
        log.warning("demand_alerts: dedupe write failed: %s", exc)


def _terminal(res: Optional[dict]) -> bool:
    """Delivered, or nobody targeted (muted pref / no device) — both mean
    'do not retry today'. A transport failure is retried next pass."""
    res = res or {}
    return (res.get("sent") or 0) > 0 or (res.get("total_targets") or 0) == 0


def check_once(*, push: bool = True, force: bool = False, board: Optional[dict] = None,
               live: Optional[dict] = None, caps: Optional[dict] = None, coll=None,
               owner: Optional[str] = None, now: Optional[datetime] = None,
               store: Optional[dict] = None, pass_coll=None) -> dict:
    """One pass. Every input is injectable for tests; the cron passes none.
    `force` skips the session gate for in-container smoke tests only. `store`
    = zone_store docs {SYM: doc} for the room gate (loaded for the candidate
    names when None). Every pass that ran the read records its counters to
    `alert_pass_latest` (`pass_coll`; alert_status.record_result, best-effort)
    so the /alerts page can explain a quiet phone — Ajay 2026-09-05: "Do we
    have the same logic in back end demand for the ones that I get alerts"."""
    now = now or _now_et()
    if not force and not in_session(now):
        return {"ran": False, "reason": "outside RTH"}
    out = _check_once(push=push, board=board, live=live, caps=caps, coll=coll, owner=owner,
                      now=now, store=store)
    AS.record_result(KIND, out, now, coll=pass_coll)
    return out


def _check_once(*, push: bool, board: Optional[dict], live: Optional[dict],
                caps: Optional[dict], coll, owner: Optional[str], now: datetime,
                store: Optional[dict]) -> dict:
    """The pass proper (session gate + pass record live in check_once)."""
    board = board if board is not None else fetch_board()
    cands = candidates(board)
    if not cands:
        return {"ran": True, "reason": "board empty or warming", "candidates": 0,
                "hits": [], "at": 0, "near": 0, "pushed": 0}
    syms = sorted(cands)
    if live is None:
        try:
            from sepa import prices
            live = prices.bulk_live_prices(syms) or {}
        except Exception as exc:
            log.warning("demand_alerts: live prices failed: %s", exc)
            return {"ran": False, "reason": f"live prices failed: {exc}"}
    last_px = {s: (live.get(s) or {}).get("price") for s in syms}
    if caps is None:
        try:
            from catalysts.promo_circuit import market_caps_for
            caps = market_caps_for(syms, last_px) or {}
        except Exception as exc:
            log.warning("demand_alerts: market caps failed: %s", exc)
            caps = {}
    if coll is None:
        coll = _state_coll()
    day_et = now.astimezone(ET).date() if now.tzinfo is not None else now.date()
    day = day_et.isoformat()
    if store is None:
        try:
            from supply_demand import zone_store
            store = zone_store.load(syms, day_et) or {}
        except Exception as exc:
            log.warning("demand_alerts: zone store read failed: %s", exc)
            store = {}
    hits, at_items, near_items = [], [], []
    skipped_cap = unknown_cap = unknown_prev = skipped_room = skipped_proximity = unknown_room = 0
    for sym in syms:
        last = last_px.get(sym)
        if not last:
            continue
        cap = caps.get(sym)
        chg = (live.get(sym) or {}).get("change_pct")
        prev = (live.get(sym) or {}).get("prev_day_close")
        if not prev:
            unknown_prev += 1
            continue
        for band in cands[sym]["bands"]:
            hit = read(last, band, chg, prev)
            if not hit:
                continue
            item = {"symbol": sym, "last": float(last), "band": band, "hit": hit,
                    "cap": cap, "name": cands[sym]["name"], "prev_close": prev}
            hits.append(item)
            if not passes_cap(cap):
                if cap is None:
                    unknown_cap += 1
                else:
                    skipped_cap += 1
                continue
            key = state_key(sym, band, day, hit["tier"])
            if _already(coll, key):
                continue
            item["key"] = key
            (at_items if hit["tier"] == "at" else near_items).append(item)
    # Phone gate (Ajay 2026-09-05): within 1% above the band (NEAR never is), and
    # >= 5% to the first unbroken supply band in the name's zone_store doc.
    pushable = []
    for it in at_items + near_items:
        if not AG.demand_proximity_gate(it["last"], it["band"]):
            skipped_proximity += 1
            continue
        zdoc = store.get(it["symbol"])
        if not zdoc:
            unknown_room += 1                             # nobody measured its supply: silent
            continue
        ok, room = AG.room_gate(it["last"], zdoc.get("bands") or [], it.get("prev_close"))
        it["room"] = room
        if not ok:
            skipped_room += 1
            continue
        pushable.append(it)
    at_ok = [it for it in pushable if it["hit"]["tier"] == "at"]
    near_ok = [it for it in pushable if it["hit"]["tier"] != "at"]
    # Closest first; only MAX_SINGLES_PER_PASS ring individually, the rest
    # join the digest so a first pass (deploy, 9:33 open) is one buzz, not 14.
    at_ok.sort(key=lambda it: it["hit"]["dist_pct"])
    singles, spill = at_ok[:MAX_SINGLES_PER_PASS], at_ok[MAX_SINGLES_PER_PASS:]
    digest = spill + near_ok
    pushed = 0
    if push and (singles or digest):
        from push import sender
        if owner is None:
            from portfolio.alerts import _resolve_owner
            owner = _resolve_owner()
        for it in singles:
            try:
                res = sender.send_to_user(owner, at_message(it), kind=KIND)
            except Exception as exc:
                log.warning("demand_alerts: push for %s failed: %s", it["symbol"], exc)
                continue
            if _terminal(res):
                _record(coll, it["key"], it, now)
                pushed += 1
        if digest:
            try:
                res = sender.send_to_user(owner, digest_message(digest), kind=KIND)
            except Exception as exc:
                log.warning("demand_alerts: digest push failed: %s", exc)
                res = None
            if _terminal(res):
                for it in digest:
                    _record(coll, it["key"], it, now)
                pushed += 1
    return {"ran": True, "date": day, "candidates": len(syms), "hits": hits,
            "at": len(at_items), "at_singles": len(singles), "near": len(near_items),
            "pushed": pushed,
            "skipped_cap": skipped_cap, "unknown_cap": unknown_cap,
            "unknown_prev": unknown_prev, "skipped_room": skipped_room,
            "skipped_proximity": skipped_proximity, "unknown_room": unknown_room}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    out = check_once()
    log.info("DEMAND-ALERTS: ran=%s candidates=%s hits=%d at=%s near=%s pushed=%s "
             "skipped_cap=%s unknown_cap=%s unknown_prev=%s skipped_room=%s "
             "skipped_proximity=%s unknown_room=%s", out.get("ran"),
             out.get("candidates"), len(out.get("hits") or []), out.get("at"),
             out.get("near"), out.get("pushed"), out.get("skipped_cap"),
             out.get("unknown_cap"), out.get("unknown_prev"), out.get("skipped_room"),
             out.get("skipped_proximity"), out.get("unknown_room"))
