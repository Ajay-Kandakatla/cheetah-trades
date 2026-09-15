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
from . import bullish_context as BC
from . import alert_status as AS
# The 5-min siblings' freshness rule (review 2026-09-14, finding 5): this pass
# used to push on bulk_live_prices()['price'] — the day AGGREGATE's close, with
# no stamp — while zone_edge and zone_bounce refuse a print older than their
# stale window. Same snapshot, same reader, same 10-minute window as the other
# 5-minute pass. zone_bounce_alerts imports demand_alerts lazily only, so this
# module-level import is cycle-free.
from .zone_bounce_alerts import print_from_snapshot, STALE_PRINT_SEC as SNAPSHOT_STALE_SEC

log = logging.getLogger(__name__)
SOURCE = "demand_alerts"           # stamped on every dedupe claim this pass makes

ET = ZoneInfo("America/New_York")
AT_PCT = 1.0                       # inside, or this close above the top → push
NEAR_PCT = 3.0                     # (AT_PCT, NEAR_PCT] above + falling → digest
# Ajay 2026-09-10: "make cap 700 m" — was 1e9 (his 2026-09-03 "billion or at
# least bigger than a billion"). Measured the day it moved: 1,501 names had a
# known cap at or above $1B and 80 more sit in the $700M–$1B band, so this
# widens the eligible set by 5.3%. This is a LOOSENING and it was his call,
# not a measured improvement. Every S/D path carries its own copy of this
# floor; test_cap_floor_agrees pins them equal so they cannot drift apart.
MIN_CAP_USD = 700_000_000.0
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
    # Ajay 2026-09-08: the direction in writing — "falling into" vs "bouncing off"
    ap = item.get("approach") if isinstance(item.get("approach"), dict) else None
    ap = ap if ap and ap.get("tag") and ap.get("text") else None   # resting inside = the old wording
    tested = f"tested {int(band['touches'])}x" if band.get("touches") else "tested band"
    mood_s = AG.mood_txt(item.get("mood"))
    parts = [f"${float(item['last']):g}"]
    if ap:
        # the tag takes the title's slot, so the distance moves into the body
        if hit["state"] != "in":
            parts.append(f"{hit['dist_pct']:g}% above")
        where = f"{ap['tag']} demand"
        parts.append(ap["text"])
    parts.append(tested)
    # Stop hunt vs break (Ajay 2026-09-09: "Institutions hunt for stop losses ..
    # I been catching some falling knives"). A READ, not a gate — it says which
    # kind of dip this was, in his own terms.
    sweep_s = AG.sweep_txt(item.get("sweep"))
    if sweep_s:
        parts.append(sweep_s)
    # Where the money is (Ajay 2026-09-09). A READ, never a gate — it measured
    # FLAT on win rate over 50,191 replayed arrivals and his speed claim came
    # back inverted; see docs/supply_demand/sector_heat.md.
    heat_s = BC.sector_heat_txt((item.get("context") or {}).get("sector_heat"))
    if heat_s:
        parts.append(heat_s)
    if mood_s:
        parts.append(mood_s)
    if "room" in item:                                    # the phone gate's read (2026-09-05)
        parts.append(AG.room_txt(item.get("room")))
        plan = AG.plan_txt(item["last"], band, item.get("room"))   # the plan (2026-09-06)
        if plan:
            parts.append(plan)
    parts.append(fmt_cap(item.get("cap")))
    body = " · ".join(parts)
    if item.get("name"):
        body += f" · {item['name']}"
    # "kind" rides in the payload: push/history.py records payload["kind"], so
    # without it every 🧲 push logged as kind=None (found 2026-09-03).
    return {"title": f"🧲 {sym} {where} {_band_txt(band)}", "body": body,
            "url": f"/sepa/{sym}?tab=supply", "data": {"url": f"/sepa/{sym}?tab=supply"}, "ticker": sym,
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
        ap = it.get("approach") if isinstance(it.get("approach"), dict) else None
        if ap and ap.get("tag"):
            where = ap["tag"]
        room = f" · {AG.room_txt(it.get('room'))}" if "room" in it else ""
        mood_s = AG.mood_txt(it.get("mood"))
        room = room + (f" · {mood_s}" if mood_s else "")
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


# --------------------------------------------------------------------------
# Dedupe state — ONE claim per (symbol, band, ET day), shared with zone_edge
# (review 2026-09-14, findings 1 + 2)
# --------------------------------------------------------------------------
# Until 2026-09-14 both passes did read-then-send-then-write: zone_edge (every
# minute) and this pass (every 5) each read "not seen", each sent, each wrote —
# and the same 🧲 reached the phone twice inside a minute. The state key is
# now CLAIMED atomically BEFORE the send (`$setOnInsert` upsert: exactly one
# writer sees the insert), and a claim whose send fails in transport is
# RELEASED so the next pass retries — the per-day semantics are unchanged:
# one push per key per day, a transport failure retries, "nobody targeted" is
# terminal. What changed is only that the claim comes first.
#
# Same day, ONE LEVEL rings once (findings F4a/F4b, 2026-09-14): within a pass
# a name is read on ONE band (the containing one, else the nearest — see
# _check_once), and after the claims land each pass re-reads the day's state
# once more (`settle_claims`) so two same-minute claims on OVERLAPPING bands
# under two keys — this pass's board cut and zone_edge's zone_store cut of the
# same level — resolve to the earlier claim BY ITS WRITE STAMP (`claimed_at`,
# set here at the upsert, never the pass's `now`); the later one is released
# and counted `skipped_overlap`. A send that RAISES stands in `transport_failed`
# (F1): never "nobody targeted", so a raised digest releases like a single.
def write_clock() -> datetime:
    """The moment a claim is WRITTEN (ET). Every `claimed_at` stamp comes from
    here — module-level so a test can freeze or tick it — never from the
    pass's `now`, which is taken at pass START before the snapshot and the
    gate loop."""
    return datetime.now(ET)


def _iso(ts) -> str:
    return ts.isoformat() if hasattr(ts, "isoformat") else str(ts)


def claim_key(coll, key: str, doc: dict, claimed_at: Optional[datetime] = None) -> bool:
    """Atomically record `key` with `doc`. True when THIS caller inserted it,
    False when it already existed (another pass rang it). No coll, or a write
    error, reads True — push again rather than never, the same side the
    `$in` dedupe read fails on.

    The doc is stamped `claimed_at` at the moment of the upsert (`write_clock`,
    or `claimed_at` when injected by a test) — the stamp `settle_claims` orders
    two same-minute claims by. F4b residual (2026-09-14): `sent_at` / `at` are
    the pass-START clock, so ordering by them ordered the passes by when they
    STARTED, not by when each claim LANDED; cron aligns the 1-min and 5-min
    passes to the same wall-clock minute, so when the earlier-started pass
    claimed SECOND its re-read saw a LATER stamp and kept — one level, two
    rings. Both containers share the host clock, so the later WRITER always
    sees the earlier one at its re-read and yields. `sent_at` / `at` stay the
    pass time, for display only."""
    if coll is None:
        return True
    stamp = _iso(claimed_at or write_clock())            # taken right before the upsert
    try:
        res = coll.update_one({"_id": key}, {"$setOnInsert": dict(doc, _id=key, claimed_at=stamp)},
                              upsert=True)
    except Exception as exc:
        log.warning("demand_alerts: dedupe claim failed for %s: %s", key, exc)
        return True
    if getattr(res, "upserted_id", None) is not None:
        return True
    if getattr(res, "matched_count", 0):
        return False
    return True                                       # a driver that reports neither: ours


def release_key(coll, key: str) -> None:
    """Drop a claim whose send did not terminate (transport failure) so the
    next pass — either module — can try again. Best-effort."""
    if coll is None:
        return
    try:
        coll.delete_one({"_id": key})
    except Exception as exc:
        log.warning("demand_alerts: dedupe release failed for %s: %s", key, exc)


def recorded_today(coll, symbols, day: str) -> dict:
    """{SYM: [{"key", "lo", "hi"}]} — every state key already claimed for these
    symbols on `day`, in ONE `$in` read on `symbol` (never a find_one per
    candidate). The day is read off the key itself (`SYM:lo-hi:DAY:tier`), so
    a doc from another day never counts. A read failure is the empty map:
    push again rather than never."""
    out: dict = {}
    syms = sorted({str(s).upper() for s in (symbols or []) if s})
    if coll is None or not syms:
        return out
    tag = f":{day}:"
    try:
        cur = coll.find({"symbol": {"$in": syms}},
                        {"_id": 1, "symbol": 1, "band": 1, "claimed_at": 1, "sent_at": 1, "at": 1})
        for d in cur:
            key = str(d.get("_id") or "")
            if tag not in key:
                continue
            band = d.get("band") or {}
            lo, hi = AG._f(band.get("lo")), AG._f(band.get("hi"))
            sym = str(d.get("symbol") or key.split(":", 1)[0]).upper()
            # the claim's WRITE stamp (`claimed_at`, set by claim_key at the
            # upsert) — settle_claims orders two same-minute claims by it;
            # `sent_at` / `at` (the pass clock) only for docs that predate it
            out.setdefault(sym, []).append({"key": key, "lo": lo, "hi": hi,
                                            "at": d.get("claimed_at") or d.get("sent_at") or d.get("at")})
    except Exception as exc:
        log.warning("demand_alerts: dedupe read failed: %s", exc)
        return {}
    return out


def bands_overlap(a: dict, b: dict) -> bool:
    """[lo, hi] intervals share at least a point. Garbage never overlaps."""
    try:
        alo, ahi = float(a["lo"]), float(a["hi"])
        blo, bhi = float(b["lo"]), float(b["hi"])
    except (KeyError, TypeError, ValueError):
        return False
    if any(v != v for v in (alo, ahi, blo, bhi)):
        return False
    return alo <= bhi and blo <= ahi


def overlapping_key(symbol: str, band: dict, recorded: dict) -> Optional[str]:
    """The key already claimed today for `symbol` whose band overlaps `band`,
    or None. Finding 2 (2026-09-14): a broken-supply shelf and a demand band
    covering the same prices are ONE level — rung once, with one stop, not
    twice under two keys with two stops."""
    for r in (recorded or {}).get(str(symbol).upper(), []):
        if r.get("lo") is None or r.get("hi") is None:
            continue
        if bands_overlap(band, r):
            return r["key"]
    return None


def claim_doc(item: dict, now: datetime, source: str = SOURCE) -> dict:
    """The state doc for one 🧲 push — the same fields the pre-2026-09-14
    `_record` wrote, plus which pass claimed it."""
    return {"symbol": item["symbol"], "tier": item["hit"]["tier"],
            "band": {"lo": item["band"]["lo"], "hi": item["band"]["hi"]},
            "last": item["last"], "dist_pct": item["hit"]["dist_pct"],
            "cap": item.get("cap"), "sent_at": now.isoformat(),
            # Mood at the moment of the alert, so "does a constructive mood
            # bounce faster off demand?" can be answered from his own tape
            # later (Ajay 2026-09-08) instead of assumed.
            "mood": item.get("mood"),
            "approach": (item.get("approach") or {}).get("dir"),
            "source": source}


def claim(coll, key: str, item: dict, now: datetime, source: str = SOURCE,
          claimed_at: Optional[datetime] = None) -> bool:
    """claim_key with the 🧲 doc shape. True = ours to send. `now` is the pass
    clock (`sent_at`, display); the ordering stamp is `claimed_at` (the write
    clock unless injected)."""
    return claim_key(coll, key, claim_doc(item, now, source), claimed_at=claimed_at)


def _stamp(s):
    """An ISO claim stamp as a datetime for ordering; None when unparseable."""
    try:
        return datetime.fromisoformat(str(s))
    except (TypeError, ValueError):
        return None


def claim_precedes(other_at, other_key: str, our_at, our_key: str) -> bool:
    """True when the OTHER claim came first: an earlier stamp, or the same
    stamp and the smaller key (a deterministic tie, so two passes that see
    each other never BOTH yield and leave the level silent). An unstamped
    other doc is older by construction — it was there before ours landed.
    Two stamps that cannot both be parsed compare as strings."""
    if other_key == our_key:
        return False
    if other_at is None:
        return True
    if our_at is None:
        return False
    a, b = _stamp(other_at), _stamp(our_at)
    if a is not None and b is not None:
        if a != b:
            return a < b
    elif str(other_at) != str(our_at):
        return str(other_at) < str(our_at)
    return str(other_key) < str(our_key)


def settle_claims(coll, items: list, now: datetime, day: str, source: str = SOURCE,
                  claimed_at: Optional[datetime] = None) -> tuple:
    """Claim every item's key (`claim`, the 🧲 doc), then re-read today's
    state ONCE for the claimed symbols (`recorded_today` — one `$in`) and
    RELEASE any claim whose band overlaps a key another pass claimed EARLIER.

    Finding F4b (2026-09-14): `recorded` is read at the top of a pass and the
    claims land seconds later. Inside that window the sibling pass can claim an
    OVERLAPPING band under a DIFFERENT key (its zone_store cut of the level vs
    this pass's board cut), and both atomic claims succeed — one level, two 🧲,
    two stops. So after claiming, each pass looks once more and the LATER claim
    yields (`claim_precedes`: stamp, then key as the tie). The yielded claim
    is released so it never mutes the name; the winner rings. A re-read that
    fails keeps every claim (push again rather than never).

    "Later" is each claim's OWN write stamp (`claimed_at`, taken by `claim_key`
    right before its upsert — `write_clock`, or `claimed_at` when injected),
    NEVER the pass `now`: that is the pass-START clock, and ordering by it let
    the earlier-started pass that claimed SECOND keep its claim (its re-read
    saw a later stamp) — one level ringing twice inside one minute (the
    verifier's residual on F4b). With one host clock the later writer always
    sees the earlier writer at its re-read.

    Returns (ours, claimed_elsewhere, lost_overlap). Order is preserved."""
    ours, elsewhere, stamps = [], 0, {}
    for it in items:
        stamp = claimed_at or write_clock()               # this claim's write moment
        stamps[it["key"]] = _iso(stamp)
        if claim(coll, it["key"], it, now, source, claimed_at=stamp):
            ours.append(it)
        else:
            elsewhere += 1
    if not ours or coll is None:
        return ours, elsewhere, 0
    rec = recorded_today(coll, [it["symbol"] for it in ours], day)
    kept, lost = [], 0
    for it in ours:
        yielded = False
        for r in rec.get(it["symbol"], []):
            if r.get("lo") is None or r.get("hi") is None or not bands_overlap(it["band"], r):
                continue
            if claim_precedes(r.get("at"), r["key"], stamps[it["key"]], it["key"]):
                yielded = True
                break
        if yielded:
            log.info("demand_alerts: %s %s yields to an earlier overlapping claim", source, it["key"])
            release_key(coll, it["key"])
            lost += 1
        else:
            kept.append(it)
    return kept, elsewhere, lost


def live_from_snapshot(snapshot: dict, now_ts: float, stale_sec: float = SNAPSHOT_STALE_SEC) -> tuple:
    """({SYM: {price, change_pct, prev_day_close, low}}, stale_print) from a
    `prices.bulk_snapshot` map: the print is the last TRADE, kept only while
    its stamp is within `stale_sec` of now (zone_bounce_alerts.print_from_
    snapshot); a stale or missing trade drops the name and is counted. This
    replaced bulk_live_prices()['price'] — the day aggregate's close, which
    lagged ~3h on 2026-09-03 and carried no stamp to notice it by."""
    live: dict = {}
    stale = 0
    for sym, snap in (snapshot or {}).items():
        if not snap:
            continue
        px, is_stale = print_from_snapshot(snap, now_ts, stale_sec)
        if is_stale:
            stale += 1
            continue
        live[sym] = {"price": px, "change_pct": snap.get("change_pct"),
                     "prev_day_close": snap.get("prev_day_close"), "low": snap.get("low")}
    return live, stale


def transport_failed(exc=None) -> dict:
    """The result a send that RAISED stands for: 0 of 1 target reached, 1
    failed — the shape `_terminal` reads as 'retry next pass'. Finding F1
    (2026-09-14): the digest except-branches set `res = None`, and
    `_terminal(None)` read `total_targets 0 == 0` as "nobody targeted" —
    TERMINAL — so a digest whose send raised kept every claim and muted its
    names for the day, while the singles path released. Every digest
    except-branch (here, zone_edge ×2, growth.alerts) now stands in this."""
    return {"sent": 0, "failed": 1, "total_targets": 1, "error": str(exc or "transport")}


def _terminal(res: Optional[dict]) -> bool:
    """Delivered, or nobody targeted (muted pref / no device) — both mean
    'do not retry today'. A transport failure is retried next pass. NO result
    at all (None / not a dict — the sender raised) is NOT terminal: "nobody
    targeted" is a fact the sender reports, never one an exception implies."""
    if not isinstance(res, dict):
        return False
    return (res.get("sent") or 0) > 0 or (res.get("total_targets") or 0) == 0


def check_once(*, push: bool = True, force: bool = False, board: Optional[dict] = None,
               live: Optional[dict] = None, caps: Optional[dict] = None, coll=None,
               owner: Optional[str] = None, now: Optional[datetime] = None,
               store: Optional[dict] = None, pass_coll=None,
               snapshot: Optional[dict] = None) -> dict:
    """One pass. Every input is injectable for tests; the cron passes none.
    `force` skips the session gate for in-container smoke tests only. `store`
    = zone_store docs {SYM: doc} for the room gate (loaded for the candidate
    names when None). `live` = an already-priced map (tests); when None the
    print comes from `snapshot` (or `prices.bulk_snapshot`) through the
    freshness rule (`live_from_snapshot`, 2026-09-14). Every pass that ran the
    read records its counters to `alert_pass_latest` (`pass_coll`;
    alert_status.record_result, best-effort) so the /alerts page can explain a
    quiet phone — Ajay 2026-09-05: "Do we have the same logic in back end
    demand for the ones that I get alerts"."""
    now = now or _now_et()
    if not force and not in_session(now):
        return {"ran": False, "reason": "outside RTH"}
    out = _check_once(push=push, board=board, live=live, caps=caps, coll=coll, owner=owner,
                      now=now, store=store, snapshot=snapshot)
    AS.record_result(KIND, out, now, coll=pass_coll)
    return out


def _check_once(*, push: bool, board: Optional[dict], live: Optional[dict],
                caps: Optional[dict], coll, owner: Optional[str], now: datetime,
                store: Optional[dict], snapshot: Optional[dict] = None) -> dict:
    """The pass proper (session gate + pass record live in check_once)."""
    board = board if board is not None else fetch_board()
    cands = candidates(board)
    if not cands:
        return {"ran": True, "reason": "board empty or warming", "candidates": 0,
                "hits": [], "at": 0, "near": 0, "pushed": 0}
    syms = sorted(cands)
    stale_print = 0
    if live is None:
        if snapshot is None:
            try:
                from sepa import prices
                snapshot = prices.bulk_snapshot(syms) or {}
            except Exception as exc:
                log.warning("demand_alerts: snapshot failed: %s", exc)
                return {"ran": False, "reason": f"snapshot failed: {exc}"}
        live, stale_print = live_from_snapshot(snapshot, now.timestamp())
    last_px = {s: (live.get(s) or {}).get("price") for s in syms}
    priced = sum(1 for s in syms if last_px.get(s))
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
    # Dedupe state in ONE read for every candidate name (2026-09-14): the exact
    # keys already rung today AND the bands under them, so a level that
    # overlaps one already rung (a broken-supply shelf over a demand band —
    # finding 2) is skipped instead of ringing twice with two stops.
    recorded = recorded_today(coll, syms, day)
    hits, at_items, near_items = [], [], []
    skipped_cap = unknown_cap = unknown_prev = skipped_room = skipped_proximity = unknown_room = 0
    skipped_direction = 0
    skipped_knife = 0
    skipped_mood = 0
    skipped_floor = 0
    skipped_overlap = 0
    accepted: dict = {}                               # {SYM: [band]} taken THIS pass
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
        seen_keys = {r["key"] for r in recorded.get(sym, [])}
        # ONE level per name per pass (finding F4a, 2026-09-14). The board can
        # carry a name on both lists with two overlapping cuts of the same
        # level (a reentry band and an approaching band a few cents apart —
        # `candidates` dedupes only an exact lo/hi pair), and reading every
        # band rang the level twice with two stops inside ONE pass: the
        # overlap skip below only knows about EARLIER passes. The band
        # containing the print wins, else the nearest above it, ties to the
        # higher top — growth._scan and zone_edge.read_near_demand pick the
        # same way. `hits` lists that one band per name.
        band_hits = [(band, hit) for band in cands[sym]["bands"]
                     for hit in [read(last, band, chg, prev)] if hit]
        if not band_hits:
            continue
        band, hit = min(band_hits, key=lambda bh: (0 if bh[1]["state"] == "in" else 1,
                                                    bh[1]["dist_pct"], -float(bh[0]["hi"])))
        item = {"symbol": sym, "last": float(last), "band": band, "hit": hit,
                "cap": cap, "name": cands[sym]["name"], "prev_close": prev,
                "day_low": (live.get(sym) or {}).get("low"),
                "approach": AG.approach_read(last, band, prev, (live.get(sym) or {}).get("low"))}
        hits.append(item)
        if not passes_cap(cap):
            if cap is None:
                unknown_cap += 1
            else:
                skipped_cap += 1
            continue
        key = state_key(sym, band, day, hit["tier"])
        if key in seen_keys:
            continue
        if overlapping_key(sym, band, recorded):
            skipped_overlap += 1                  # one level, already rung under another key
            continue
        if any(bands_overlap(band, b) for b in accepted.get(sym, [])):
            skipped_overlap += 1                  # one level, already taken THIS pass
            continue
        accepted.setdefault(sym, []).append(band)
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
        # Bouncing only (Ajay 2026-09-09, after CASY). Falling / settling /
        # reclaiming / resting still list on the BOARDS; the phone stays quiet.
        if not AG.direction_gate(it.get("approach")):
            skipped_direction += 1
            continue
        # Bullish reversal, not a falling knife (Ajay 2026-09-09, after CASY:
        # "I need only bullish reversal stocks ... mood has to be bullish too
        # with reversal. After a stationary bottommed stocks as I caught a
        # fallig knife today with Casy"). "Bouncing" is an INTRADAY read and
        # CASY satisfied it while in free-fall; these two read the DAILY
        # structure. One frame load, shared by all three daily reads below.
        frame = AG.daily_frame(it["symbol"])
        kr = AG.knife_read(it["symbol"], frame=frame)
        it["knife"] = kr
        if not AG.knife_gate(it["symbol"], read=kr):
            skipped_knife += 1
            continue
        # The mood of the TURN, not of the two-year trend — a name that has
        # bottomed scores -45 on trend+location+structure before anything else,
        # so the full-frame read can never call a real bottom bullish.
        rm = AG.reversal_mood_read(it["symbol"], frame=frame)
        it["reversal_mood"] = rm
        # Which kind of dip this was — swept the stops and reclaimed, or broke
        # and stayed under. Same frame, no extra load. The session's own low
        # and print ride in (2026-09-14): the cached frame ends yesterday, so
        # without them a floor swept THIS morning read intact.
        sw = AG.sweep_read(it["band"], it["symbol"], frame=frame,
                           day_low=it.get("day_low"), last=it["last"], day=day_et)
        it["sweep"] = sw
        # The band floor must have HELD. The only gate measured to separate:
        # intact 30.7% win vs swept 22.7% and broken 21.5% (n=31,861, 192 dates,
        # Δwin +8.60pp CI[+6.39,+11.06]). The stop hunt he asked for is the
        # LOSING side — the reclaim does not save it.
        if not AG.floor_held_gate(it["band"], read=sw):
            skipped_floor += 1
            continue
        if not AG.reversal_mood_gate(it["symbol"], read=rm):
            skipped_mood += 1
            continue
        pushable.append(it)
    # Mood as CONTEXT (Ajay 2026-09-08: "do include mood in the overall
    # criteria of the stocks for alerts becuz mood determins if stock grows
    # faster from demand or not"). Read ONLY for names that already passed
    # every S/D gate — a handful a pass, so this costs one cached daily frame
    # each — and it never adds or removes a name.
    for it in pushable:
        it["mood"] = AG.mood_read(it["symbol"])
        # Things to SEE (Ajay 2026-09-09: "looking at GEX and other bullish
        # patterns to see and also most recent sentiment"). NEVER a gate — his
        # own ledger has no chart pattern beating the 50% placebo. One call per
        # surviving name, cached 15 min, all three fail to None silently.
        it["context"] = BC.bullish_context(it["symbol"])
    at_ok = [it for it in pushable if it["hit"]["tier"] == "at"]
    near_ok = [it for it in pushable if it["hit"]["tier"] != "at"]
    # Constructive mood first, then closest; only MAX_SINGLES_PER_PASS ring
    # individually, the rest join the digest so a first pass (deploy, 9:33
    # open) is one buzz, not 14.
    at_ok.sort(key=lambda it: (AG.mood_rank(it.get("mood")), it["hit"]["dist_pct"]))
    singles, spill = at_ok[:MAX_SINGLES_PER_PASS], at_ok[MAX_SINGLES_PER_PASS:]
    digest = spill + near_ok
    n_singles = len(singles)
    pushed = 0
    claimed_elsewhere = 0
    if push and (singles or digest):
        from push import sender
        if owner is None:
            from portfolio.alerts import _resolve_owner
            owner = _resolve_owner()
        # CLAIM, then send, then release on a transport failure (2026-09-14).
        # zone_edge reads the same key every minute; whichever pass inserts
        # the key owns the push, the other sees "claimed" and stays quiet.
        # Singles and digest are claimed together so the post-claim overlap
        # re-read (settle_claims, F4b) is ONE `$in`, never one per lane.
        single_keys = {it["key"] for it in singles}
        ours, claimed_elsewhere, lost = settle_claims(coll, singles + digest, now, day)
        skipped_overlap += lost                   # the sibling pass claimed the level first
        singles = [it for it in ours if it["key"] in single_keys]
        ours = [it for it in ours if it["key"] not in single_keys]
        for it in singles:
            try:
                res = sender.send_to_user(owner, at_message(it), kind=KIND)
            except Exception as exc:
                log.warning("demand_alerts: push for %s failed: %s", it["symbol"], exc)
                release_key(coll, it["key"])
                continue
            if _terminal(res):
                pushed += 1
            else:
                release_key(coll, it["key"])
        if ours:
            try:
                res = sender.send_to_user(owner, digest_message(ours), kind=KIND)
            except Exception as exc:
                log.warning("demand_alerts: digest push failed: %s", exc)
                res = transport_failed(exc)       # F1: a raise is NOT "nobody targeted"
            if _terminal(res):
                pushed += 1
            else:
                for it in ours:
                    release_key(coll, it["key"])
    return {"ran": True, "date": day, "candidates": len(syms), "priced": priced,
            "stale_print": stale_print, "hits": hits,
            "at": len(at_items), "at_singles": n_singles, "near": len(near_items),
            "pushed": pushed, "claimed_elsewhere": claimed_elsewhere,
            "skipped_cap": skipped_cap, "unknown_cap": unknown_cap,
            "unknown_prev": unknown_prev, "skipped_room": skipped_room,
            "skipped_proximity": skipped_proximity, "unknown_room": unknown_room,
            "skipped_direction": skipped_direction,
            "skipped_knife": skipped_knife, "skipped_mood": skipped_mood,
            "skipped_floor": skipped_floor, "skipped_overlap": skipped_overlap}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    out = check_once()
    log.info("DEMAND-ALERTS: ran=%s candidates=%s hits=%d at=%s near=%s pushed=%s "
             "skipped_cap=%s unknown_cap=%s unknown_prev=%s skipped_room=%s "
             "skipped_proximity=%s unknown_room=%s skipped_direction=%s skipped_knife=%s skipped_mood=%s skipped_floor=%s", out.get("ran"),
             out.get("candidates"), len(out.get("hits") or []), out.get("at"),
             out.get("near"), out.get("pushed"), out.get("skipped_cap"),
             out.get("unknown_cap"), out.get("unknown_prev"), out.get("skipped_room"),
             out.get("skipped_proximity"), out.get("unknown_room"),
             out.get("skipped_direction"), out.get("skipped_knife"),
             out.get("skipped_mood"), out.get("skipped_floor"))
