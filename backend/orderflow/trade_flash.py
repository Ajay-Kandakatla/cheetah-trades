"""Trade Flash — burst alerts on the demand-board names, tied to their zones.

Ajay 2026-08-24:

> *"Can you not do trade flash logic yourself? With in the Demand Zone tabs and
> push notification I can also get it on my phone..."*

— after describing the concept: *"To catch massive options sweeps or sudden
institutional block trades hitting the tape in real-time."* This module is the
STOCK-tape half; the options-sweep half is a separate, later module.

WHY IT IS ZONE-TIED AND NOT ALL-MARKET
--------------------------------------
Two reasons, one his and one measured:

* His framing: the flash belongs *"with in the Demand Zone tabs"* — the burst
  matters because of WHERE it happens. A $400k buy burst printing INTO a tested
  demand band is the entry confirmation his zone entries were missing ("all my
  entries are sitting ducks"); the same burst mid-range is trivia.
* The 2026-08-24 studies measured that a zone touch alone has no edge — the
  location is necessary context, not a trigger. This is the trigger layer,
  scoped to the locations he already watches.

An all-market burst feed would also be a firehose: the push keep-set on his
phone is deliberately tiny, and one spammy kind is how kinds get retired.

ONE SCALE — every burst threshold is imported from `tape` (`find_bursts`:
10s window, >=$250k, >=75% one-sided, >=15 prints), never re-declared. The
zone-proximity band reuses `price_zones.NEAR_PCT`. If either module moves,
this moves with it.

DELIVERY: one CONSOLIDATED push per poll cycle (the accumulation_change
pattern), owner-scoped via send_to_user — other users never receive it.
Kind `trade_flash` — the 4th kind on the phone keep-set, added with Ajay's
explicit OK 2026-08-24 ("push notification I can also get it on my phone").

NOT a signal with a measured record. Bursts are described (side, dollars,
where), never scored. Decision support, not advice.
"""
from __future__ import annotations

import logging
import os
import time as _time
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Optional

log = logging.getLogger("orderflow.trade_flash")

EVENTS_COLL = "trade_flash_events"

# How far back each poll looks. Slightly more than the cron cadence (5 min) so
# a slow cycle cannot open a gap the next poll never sees; the _id dedupe makes
# the overlap free rather than double-pushed.
LOOKBACK_MIN = 7

# BACKSTOP since 2026-09-27: fetch_recent_trades now drops every auction print
# by its CONDITION (tape.print_kind), which also catches crosses that print off
# the bell (ORCL 2026-09-25: 09:30:14 and 16:04:14). This clock filter stays for
# any path that hands build_events bursts from an unclassified frame.
#
# BOTH auction crosses print as one enormous trade stamped exactly at the bell,
# and `find_bursts` reads each as a giant one-sided burst on essentially every
# symbol. Measured 2026-08-21 — open: AVGO $1,085.3M "sell", FANG $33.2M
# "sell", ALLY $1.3M "buy". Close: AVGO $1,482.9M "sell", FANG $130.1M "buy",
# CR $22.1M "sell". None of it is anyone aggressing; it is the auction.
#
# The opening filter is load-bearing for LIVE polling specifically: the first
# poll runs at 9:32 and its 7-minute lookback reaches back over 09:30:00, so
# without this the first push of every session would be the cross on whichever
# board name crossed biggest. The close is already outside the watch window
# (the last poll is 15:57) but is excluded too, so any backfill or replay path
# gets the same clean answer.
AUCTION_CROSS_ET = frozenset({"09:30:00", "16:00:00"})


# The poll universe is whatever the demand + supply boards currently hold —
# capped here as a hard backstop so a future board change cannot silently turn
# this into a 500-symbol sweep of the shared API key.
MAX_SYMBOLS = 60

# The watch window, ET. Named 2026-10-14 so the two tape-burst kinds that ride
# this pass (orderflow/tape_burst_kinds.py) and the /alerts window read ONE
# clock — the same values the literals in run_watch carried (9*60+32, 16*60),
# and the window his 2026-10-14 answer set for both kinds (DECISIONS K4:
# every 5 min, 09:32–16:00 ET).
WATCH_OPEN_ET = dtime(9, 32)      # Ajay 2026-10-14
WATCH_CLOSE_ET = dtime(16, 0)     # Ajay 2026-10-14

# The zone kind's push title (unchanged words, now a format so the two tape
# kinds can pass their own through the same record_and_push).
ZONE_TITLE_FMT = "⚡ Tape burst at a zone — {lead}"
MORE_FMT = " +{n} more"


def _owner_email() -> str:
    """Same pattern as house/daily_scrape: env override, owner default."""
    return os.getenv("TRADE_FLASH_OWNER_EMAIL", "ajaykandakatla@gmail.com").lower()


def _db():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        c = MongoClient(url, serverSelectionTimeoutMS=2000)
        c.admin.command("ping")
        return c[os.getenv("MONGO_DB", "cheetah")]
    except Exception:
        return None


def _now_et():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York"))


def _num(v) -> Optional[float]:
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


# ── pure: zone proximity ─────────────────────────────────────────────────────
def classify_zone(price, lo, hi) -> Optional[str]:
    """'in' when the burst printed inside the band, 'near' within NEAR_PCT of
    either edge, None otherwise. PURE.

    NEAR_PCT is imported from price_zones — the same 3% that already defines
    "at" a zone everywhere else in the app. A second nearness constant would be
    a second scale for the same idea.
    """
    from supply_demand.price_zones import NEAR_PCT

    p, l, h = _num(price), _num(lo), _num(hi)
    if p is None or l is None or h is None or p <= 0 or h < l:
        return None
    if l <= p <= h:
        return "in"
    edge = l if p < l else h
    if abs(p - edge) / p * 100.0 <= NEAR_PCT:
        return "near"
    return None


def event_id(symbol: str, day: str, time_et: str) -> str:
    """Deterministic id: one event per (symbol, day, 10s-window). Re-polling
    the same window can therefore never duplicate a push. PURE."""
    return f"{symbol.upper()}:{day}:{time_et}"


def build_events(symbol: str, board: str, band: dict, bursts: list,
                 day: str) -> list:
    """Bursts that landed in or near this symbol's band, as event docs. PURE.

    A burst away from the zone is dropped entirely — the whole point is that
    location gates the alert. `board` records WHICH board the band came from,
    because the same burst means opposite things: a buy burst into a demand
    floor is confirmation; a sell burst at a supply ceiling is rejection.
    """
    lo, hi = _num((band or {}).get("lo")), _num((band or {}).get("hi"))
    out = []
    for b in bursts or []:
        if b.get("time_et") in AUCTION_CROSS_ET:
            continue                             # the auction, not an aggressor
        where = classify_zone(b.get("price"), lo, hi)
        if not where:
            continue
        out.append({
            "_id": event_id(symbol, day, b["time_et"]),
            "symbol": symbol.upper(),
            "et_date": day,
            "time_et": b["time_et"],
            "side": b["side"],
            "dollars": _num(b.get("dollars")),
            "volume": b.get("volume"),
            "n_trades": b.get("n_trades"),
            "price": _num(b.get("price")),
            "board": board,                      # 'demand' | 'supply'
            "zone_lo": lo, "zone_hi": hi,
            "at_zone": where,                    # 'in' | 'near'
            "recorded_at": int(_time.time()),
        })
    return out


PUSH_BODY_LINES = 4     # lines the PHONE shows; /alerts lists every event (items)


def tape_url(sym: str) -> str:
    """The Tape tab of one name — the push's tap-route and each /alerts item's."""
    return f"/sepa/{sym}?tab=tape&from=supply-demand"


def fmt_dollars(m) -> str:
    """$1.8M / $560K — the one money format of every tape-burst line. PURE."""
    m = m or 0
    return f"${m/1e6:.1f}M" if m >= 1e6 else f"${m/1e3:.0f}K"


def headline(ev: dict) -> str:
    """One push line per event. Names the meaning, not just the numbers. PURE."""
    amt = fmt_dollars(ev.get("dollars"))
    what = ("buyers stepping in AT the demand zone"
            if ev.get("board") == "demand" and ev.get("side") == "buy" else
            "sellers hitting the demand zone" if ev.get("board") == "demand" else
            "sellers defending the supply ceiling" if ev.get("side") == "sell" else
            "buyers pushing INTO the supply ceiling")
    return f"{ev['symbol']} {ev['time_et']} — {amt} {ev['side']} burst, {what}"


# ── impure: fetch, scan, record, push ────────────────────────────────────────
def fetch_recent_trades(symbol: str, minutes: int = LOOKBACK_MIN):
    """The last `minutes` of tape only — one page, not the whole session.

    A full-day fetch per poll (tape.fetch_trades) would be ~6 pages x 60 names
    x 78 polls/day against the shared key. The tail is one request.

    `order=desc` is LOAD-BEARING, not a style choice. One page caps at 50,000
    prints and a busy open blows straight through it — measured 2026-08-24 on
    the 9:30-9:37 window: NVDA returned a full 50,000 with `next_url` still
    set, TSLA 33,833, SPY 20,586. Ascending would therefore have handed back
    the OLDEST seven minutes and silently dropped the newest — exactly the
    prints this alert exists to catch, so the flash would fire late or not at
    all on the busiest tape of the day. Descending keeps the newest and lets
    the window shorten instead; the sort below restores ascending order, which
    `tick_rule_sides` and `find_bursts`'s resample both require.
    """
    import pandas as pd
    import requests
    from massive_keys import stocks_key
    from .tape import BASE_URL, FETCH_TIMEOUT_SEC

    key = stocks_key()
    if not key:
        return None
    gte_ns = int((datetime.now(timezone.utc) - timedelta(minutes=minutes))
                 .timestamp() * 1_000_000_000)
    try:
        r = requests.get(f"{BASE_URL}/v3/trades/{symbol.upper()}",
                         params={"timestamp.gte": gte_ns, "order": "desc",
                                 "sort": "timestamp", "limit": 50000, "apiKey": key},
                         timeout=FETCH_TIMEOUT_SEC)
        if r.status_code != 200:
            log.debug("trade_flash %s -> HTTP %s", symbol, r.status_code)
            return None
        rows = (r.json() or {}).get("results") or []
    except Exception as exc:
        log.debug("trade_flash fetch %s failed: %s", symbol, exc)
        return None
    if not rows:
        return None
    df = pd.DataFrame(rows)
    ts = "sip_timestamp" if "sip_timestamp" in df.columns else "participant_timestamp"
    df["ts_utc"] = pd.to_datetime(df[ts], unit="ns", utc=True)
    df = regular_only(df)
    # Restores ascending order after the descending fetch above.
    df = df[["ts_utc", "price", "size"]].dropna().sort_values("ts_utc").set_index("ts_utc")
    df = df[(df["price"] > 0) & (df["size"] > 0)]
    return df if len(df) else None


def regular_only(df):
    """Raw Massive rows → only the REGULAR prints (same row order). PURE.

    Trade eligibility (2026-09-27): the same `tape.print_kind` the Tape tab
    uses. Auction crosses, official open/close re-reports, average-price /
    contingent / derivatively-priced prints and busted prints never reach
    tick_rule_sides or find_bursts, so none of them can fire a flash. This is
    what catches ORCL's 09:30:14 open cross, which the clock-based
    AUCTION_CROSS_ET (kept as a backstop) cannot see. Rows with no
    `conditions` column read as regular — the pre-2026-09-27 behaviour.
    """
    from .tape import print_kind
    conds = df["conditions"] if "conditions" in df.columns else [None] * len(df)
    corr = df["correction"] if "correction" in df.columns else [None] * len(df)
    keep = [print_kind(c, k) == "regular" for c, k in zip(conds, corr)]
    return df[keep]


def board_bands() -> list:
    """(symbol, board, band) for every name on the demand + supply boards.

    READ OVER HTTP, NOT AS AN IMPORT — the same lesson the crontab already
    records at the 16:55 warm (fixed 2026-08-15) and that this module walked
    into anyway on 2026-08-24. `demand_reentry._cache` is a PROCESS-LOCAL
    dict. The cron runs `python -m sepa.cli trade-flash-watch` as a fresh
    process, so an in-process `cached_or_warm` call sees an empty cache, gets
    `warming: True`, returns no rows, and dies — Trade Flash would have polled
    nothing, pushed nothing, and logged a healthy zero forever. Calling the API
    reads the memory that is actually warm.

    Falls back to the direct import when HTTP is unavailable, which is how the
    unit tests and any in-API caller reach it. A warming or unreachable board
    yields an empty watch list — the correct quiet answer, never a crash.
    """
    rows, supply_rows = [], []
    try:
        import requests
        base = os.getenv("INTERNAL_API_BASE", "http://api:8000")
        r = requests.get(f"{base}/supply-demand/demand-reentry",
                         params={"universe": "sp1500_plus", "limit": 200},
                         headers={"X-User-Email": "cron@internal"}, timeout=20)
        if r.status_code == 200:
            data = r.json() or {}
            if data.get("warming"):
                log.info("trade_flash: demand board still warming — nothing to watch")
                return []
            rows = data.get("rows") or []
            supply_rows = data.get("supply_rows") or []
        else:
            log.warning("trade_flash: board HTTP %s", r.status_code)
    except Exception as exc:
        log.debug("trade_flash: board over HTTP failed (%s) — trying import", exc)

    if not rows and not supply_rows:
        try:
            from supply_demand import demand_reentry as D
            data = D.cached_or_warm("sp1500_plus", limit=200)
            if data.get("warming"):
                return []
            rows = data.get("rows") or []
            supply_rows = data.get("supply_rows") or []
        except Exception:
            return []

    out = []
    for r_ in rows:
        band = r_.get("entry_zone") or {}
        if r_.get("symbol") and band.get("lo") is not None:
            out.append((r_["symbol"].upper(), "demand", band))
    for r_ in supply_rows:
        band = ((r_.get("supply") or {}).get("ceiling")) or {}
        if r_.get("symbol") and band.get("lo") is not None:
            out.append((r_["symbol"].upper(), "supply", band))

    # De-dupe symbols (a name can sit on both boards; the demand band wins —
    # it is the one with a trade attached) and apply the hard cap.
    seen, dedup = set(), []
    for sym, board, band in out:
        if sym in seen:
            continue
        seen.add(sym)
        dedup.append((sym, board, band))
    return dedup[:MAX_SYMBOLS]


def bursts_from_tail(df) -> Optional[list]:
    """A tail frame -> its bursts through the `tape` engine (tick_rule_sides +
    find_bursts). None when the frame is too thin to read (find_bursts' own
    15-print floor) or the engine fails. Shared with tape_burst_kinds — one
    burst rule for every kind."""
    from .tape import tick_rule_sides, find_bursts

    if df is None or len(df) < 15:              # find_bursts' own floor
        return None
    sided = df.copy()
    sided["side"] = tick_rule_sides(sided["price"].tolist())
    try:
        return find_bursts(sided)
    except Exception as exc:
        log.debug("trade_flash bursts failed: %s", exc)
        return None


def scan_events(*, bands=None, tails=None) -> list:
    """One poll: tail tape for every board name -> zone-tied burst events.

    `bands` defaults to board_bands(); `tails`, when a dict, is filled
    symbol -> tail frame (None for no answer) so the tape-burst kinds reuse
    the fetch instead of reading the same tape twice (2026-10-14)."""
    day = _now_et().strftime("%Y-%m-%d")
    events = []
    for sym, board, band in (board_bands() if bands is None else bands):
        df = fetch_recent_trades(sym)
        if tails is not None:
            tails[sym] = df
        bursts = bursts_from_tail(df)
        if bursts is None:
            continue
        events.extend(build_events(sym, board, band, bursts, day))
    return events


def _find_ids(coll, ids: list) -> dict:
    """{_id: doc} for the ids already stored, ONE `$in` read. Never raises — a
    failed read answers {} (nothing known), which leaves the caller's
    `$setOnInsert` dedupe as the backstop."""
    if not ids:
        return {}
    try:
        cur = coll.find({"_id": {"$in": list(ids)}},
                        {"_id": 1, "kind": 1, "recorded_at": 1})
        return {d["_id"]: d for d in (cur or []) if isinstance(d, dict) and "_id" in d}
    except Exception as exc:
        log.debug("trade_flash id read failed: %s", exc)
        return {}


def _is_fresh(doc: dict, fresh_since) -> bool:
    """Recorded during THIS poll (at or after `fresh_since`, epoch s)? A doc an
    earlier poll wrote is a re-sighting inside the LOOKBACK_MIN overlap."""
    if fresh_since is None:
        return True
    try:
        return int(doc.get("recorded_at") or 0) >= int(fresh_since)
    except (TypeError, ValueError):
        return False


def record_and_push(events: list, *, kind: str = "trade_flash",
                    coll_name: str = EVENTS_COLL,
                    title_fmt: str = ZONE_TITLE_FMT, headline_fn=None,
                    url_fn=None, precheck_colls: tuple = (),
                    fresh_since: Optional[int] = None,
                    dry_run: bool = False) -> dict:
    """Insert unseen events; ONE consolidated push for whatever is new.

    Batched because five names bursting in one poll must be one notification,
    not five — a spammy kind is how kinds get retired from the phone.

    Parameterized 2026-10-14 for the two tape-burst kinds; the defaults ARE
    the zone kind (same collection, title, lines, url, kind). An `_id` found
    in any `precheck_colls` collection is skipped (`dup_precheck`, of which
    `dup_precheck_fresh` were written during this poll). An `_id` already in
    `coll_name` is split by the stored doc's `kind` (a doc with none is this
    kind — the zone collection never stored one): `dup_same` (this kind,
    re-seen inside the LOOKBACK_MIN overlap), `dup_kind` (another kind,
    written during this poll), `dup_earlier` (another kind, an earlier
    poll). `dry_run`: no write, no push — `would_push` is what would be new.
    """
    headline_fn = headline_fn or headline
    url_fn = url_fn or tape_url
    counts = {"dup_precheck": 0, "dup_precheck_fresh": 0, "dup_same": 0,
              "dup_kind": 0, "dup_earlier": 0}
    db = _db()
    if db is None:
        if dry_run:
            return {"ok": False, "reason": "no mongo", "new": 0, "dry_run": True,
                    "would_push": len(events), **counts}
        return {"ok": False, "reason": "no mongo", "new": 0}
    todo = list(events)
    for name in precheck_colls or ():
        known = _find_ids(db[name], [ev["_id"] for ev in todo])
        if not known:
            continue
        keep = []
        for ev in todo:
            doc = known.get(ev["_id"])
            if doc is None:
                keep.append(ev)
                continue
            counts["dup_precheck"] += 1
            if _is_fresh(doc, fresh_since):
                counts["dup_precheck_fresh"] += 1
        todo = keep
    coll = db[coll_name]
    fresh, existing = [], []
    if dry_run:
        known = _find_ids(coll, [ev["_id"] for ev in todo])
        for ev in todo:
            (existing if ev["_id"] in known else fresh).append(ev)
    else:
        for ev in todo:
            try:
                res = coll.update_one({"_id": ev["_id"]}, {"$setOnInsert": ev}, upsert=True)
                if res.upserted_id is not None:
                    fresh.append(ev)
                else:
                    existing.append(ev)
            except Exception as exc:
                log.debug("trade_flash write failed: %s", exc)
        known = _find_ids(coll, [ev["_id"] for ev in existing]) if existing else {}
    for ev in existing:
        doc = known.get(ev["_id"]) or {}
        if (doc.get("kind") or kind) == kind:
            counts["dup_same"] += 1
        elif _is_fresh(doc, fresh_since):
            counts["dup_kind"] += 1
        else:
            counts["dup_earlier"] += 1
    fresh_ids = [ev["_id"] for ev in fresh]
    if dry_run:
        return {"ok": True, "new": 0, "pushed": False, "dry_run": True,
                "would_push": len(fresh), "fresh_ids": fresh_ids, **counts}
    if not fresh:
        return {"ok": True, "new": 0, "pushed": False, "fresh_ids": [], **counts}

    fresh.sort(key=lambda e: -(e.get("dollars") or 0))
    lead = fresh[0]
    title = title_fmt.format(lead=lead["symbol"]) + (
        MORE_FMT.format(n=len(fresh) - 1) if len(fresh) > 1 else "")
    lines = [headline_fn(e) for e in fresh]
    body = "\n".join(lines[:PUSH_BODY_LINES])
    # EVERY burst, in body order (2026-09-29, Ajay on "CRWV +7 more": "I am
    # unable to see the other that are hiddedn her"). Log-only: push.sender
    # strips `items` before the device payload, so the phone is unchanged.
    items = [{"symbol": e["symbol"], "text": ln} for e, ln in zip(fresh, lines)]
    pushed = False
    try:
        from push import sender
        r = sender.send_to_user(_owner_email(), {
            "title": title, "body": body,
            "url": url_fn(lead["symbol"]),
            "kind": kind,
            "items": items,
        }, kind=kind)
        pushed = bool(r and r.get("sent"))
    except Exception as exc:
        log.warning("%s push failed: %s", kind, exc)
    return {"ok": True, "new": len(fresh), "pushed": pushed,
            "fresh_ids": fresh_ids, **counts}


def today_events(limit: int = 50) -> dict:
    """Today's events, newest first — the strip on the Supply & Demand page and
    the ⚡ badge on the zone boards both read this."""
    db = _db()
    if db is None:
        return {"events": [], "n": 0}
    day = _now_et().strftime("%Y-%m-%d")
    rows = list(db[EVENTS_COLL].find({"et_date": day}, {"recorded_at": 0})
                .sort("time_et", -1).limit(limit))
    # 2026-10-14: a High-Beta name's burst AT a zone rings as 🎢 and is stored
    # in tape_burst_events, not here (A5) — the strip, the ⚡ badges and the
    # topping board's sell evidence still see it: those docs carry the same
    # board / zone_lo / zone_hi / at_zone. Merged by `_id`; a failed read
    # leaves the zone docs exactly as before.
    try:
        from .tape_burst_kinds import EVENTS_COLL as TAPE_KINDS_COLL
        more = list(db[TAPE_KINDS_COLL].find(
            {"et_date": day, "at_zone": {"$exists": True}}, {"recorded_at": 0})
            .sort("time_et", -1).limit(limit))
    except Exception as exc:
        log.debug("trade_flash: tape_burst_events read failed: %s", exc)
        more = []
    if more:
        seen = {r.get("_id") for r in rows}
        rows += [r for r in more if r.get("_id") not in seen]
        rows.sort(key=lambda r: r.get("time_et") or "", reverse=True)
        rows = rows[:limit]
    return {"events": rows, "n": len(rows),
            "symbols": sorted({r["symbol"] for r in rows})}


def in_window(now) -> bool:
    """Weekday and WATCH_OPEN_ET <= now < WATCH_CLOSE_ET (minute resolution,
    the same test the literals made). PURE."""
    hm = (now.hour, now.minute)
    return (now.weekday() <= 4
            and (WATCH_OPEN_ET.hour, WATCH_OPEN_ET.minute) <= hm
            < (WATCH_CLOSE_ET.hour, WATCH_CLOSE_ET.minute))


def run_watch(*, kinds=None, dry_run: bool = False) -> dict:
    """Cron entry. RTH only — bursts on a closed tape are stale news.

    2026-10-14: the same pass then runs the two tape-burst kinds
    (orderflow/tape_burst_kinds.py — Ajay: "I need a tape burst notification
    specific for High Beta stocks … and also other tape bursts from the Chart
    Maps page"). Order: the zone scan; the High-Beta watch list is read; the
    zone push FIRST, minus the High-Beta names (their bursts, at a zone or
    not, ring as 🎢 — trade_flash is muted on his phone since 2026-09-08 —
    and the zone pass also skips any `_id` already in tape_burst_events);
    then the kinds; then any held-back zone burst the 🎢 kind did not store
    is recorded as ⚡ after all. A failure anywhere in the kinds never touches
    the zone result. `kinds`: "all" / a comma list (default all). `dry_run`: no write,
    no push, the clock gate bypassed (a manual check of both watch lists).
    """
    now = _now_et()
    if not dry_run and not in_window(now):
        return {"ok": True, "skipped": "market closed"}
    poll_ts = int(_time.time())
    bands = board_bands()
    tails: dict = {}
    events = scan_events(bands=bands, tails=tails)
    TBK = plan = None
    try:
        from . import tape_burst_kinds as TBK
        plan = TBK.prepare(kinds)
    except Exception as exc:
        log.warning("tape-burst kinds: prepare failed: %s", exc)
        TBK = plan = None
    deferred = TBK.deferred_symbols(plan) if plan is not None else frozenset()
    zone_events = [e for e in events if e["symbol"] not in deferred]
    held_back = [e for e in events if e["symbol"] in deferred]
    result = record_and_push(
        zone_events,
        precheck_colls=(TBK.EVENTS_COLL,) if TBK is not None else (),
        fresh_since=poll_ts, dry_run=dry_run)
    result.pop("fresh_ids", None)
    if deferred:
        result["deferred_highbeta"] = len(events) - len(zone_events)
    log.info("TRADE-FLASH: %d candidate, %s", len(events), result)
    if plan is None:
        result["kinds_error"] = "prepare failed"
        return result
    hb_ran = False
    try:
        result["kinds"] = TBK.run_all(zone_bands=bands, tails=tails, now=now,
                                      plan=plan, fresh_since=poll_ts,
                                      dry_run=dry_run)
        hb_ran = TBK.KIND_HIGHBETA in (result["kinds"] or {})
    except Exception as exc:
        log.warning("tape-burst kinds failed: %s", exc)
        result["kinds_error"] = type(exc).__name__
    # A held-back zone burst is never lost: whatever the 🎢
    # kind did not store (it failed, or a name was cut under the price floor)
    # lands here as ⚡ — muted on his phone, but on /alerts and the zone
    # boards. The precheck skips every `_id` the 🎢 kind holds, so on a normal
    # poll this is one `$in` read and no write. A dry run only checks when the
    # 🎢 kind did not run (its own dry run wrote nothing to skip against).
    if held_back and (not hb_ran or not dry_run):
        net = record_and_push(held_back, precheck_colls=(TBK.EVENTS_COLL,),
                              fresh_since=poll_ts, dry_run=dry_run)
        result["deferred_unclaimed"] = int(
            (net.get("would_push") if dry_run else net.get("new")) or 0)
        if net.get("pushed"):
            result["deferred_pushed"] = True
    return result
