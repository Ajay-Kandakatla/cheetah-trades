"""Tape-burst kinds — 🎢 High-Beta and 🗺️ Chart Maps tape bursts (2026-10-14).

Ajay 2026-10-14: "I need a tape burst notification specific for High Beta
stocks from the reselinet separately and also other tape bursts from the Chart
Maps page" — then, asked which names: "High-Beta tab names + all Chart Maps
names".

Two owner-only LIVE kinds riding the EXISTING `sepa.cli trade-flash-watch`
cron line, in the same process, after the zone pass (no crontab line of their
own — a deploy does not ship the host-mounted crontab):

  tape_burst_highbeta   every name the 🎢 High Beta tab lists, biggest drop
                        first, cut at HIGHBETA_MAX_SYMBOLS.
  tape_burst_chartmaps  the union of every Chart Maps tab's served names
                        (`chart_maps_membership`, the served top of each tab),
                        round-robin by served rank across tabs, minus the zone
                        names trade_flash watches and the High-Beta names, cut
                        at CHARTMAPS_MAX_SYMBOLS. EXCLUDED_TABS (2026-10-16:
                        the 🕯️ Doji Sweep tab, no push in its build) never
                        ride it.

THE BURST RULE IS trade_flash's — the `tape` engine through
`trade_flash.bursts_from_tail` (10 s window, >= $250k, >= 75% one-sided, >= 15
regular prints; auction / average-price / busted prints never reach it). Only
the LOCATION differs: these kinds are location-free — a burst anywhere in the
day's range is an event (DECISIONS K4: location-free).

PRECEDENCE (AMENDMENTS A5): zone → High-Beta → Chart Maps, with one turn: a
High-Beta name's burst AT a zone rings as 🎢, not as ⚡ — trade_flash has been
muted on his phone since 2026-09-08. trade_flash.run_watch therefore leaves
the High-Beta names out of its own push (`deferred_symbols`); their event docs
here carry the zone they printed at. Every event `_id` is trade_flash's
`event_id` (SYM:day:time), so one burst is ONE /alerts row: each kind skips an
`_id` already in trade_flash_events, both kinds upsert `$setOnInsert` into ONE
`tape_burst_events` (the doc carries its `kind`), and the zone pass skips an
`_id` already here (two-way).

WATCH LISTS ARE READ OVER HTTP OR FROM MONGO, NEVER WARMED HERE (A9/A11): the
🎢 list is `GET {INTERNAL_API_BASE}/chart-maps/high-beta/watch` — the memo is
process-local to the api, and a cron process warming it would compute it a
second time; a `warming` answer is an empty list for THAT poll (the warm starts
server-side). The Chart Maps union is one read-only `find` on
`chart_maps_membership` (the `attach_also_on` read). This module imports
neither the High Beta tab nor the board.

Counters recorded per pass (supply_demand.alert_status) count FRESH bursts
only (A3): a burst re-seen inside the LOOKBACK_MIN overlap is `dup_same`, never
a second burst. UNMEASURED — a description of prints, never a signal; nothing
here gates a scan, sizes a position or enters a lane. Not advice.
"""
from __future__ import annotations

import logging
import os
import time as _time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Optional

from . import trade_flash as TF

log = logging.getLogger("orderflow.tape_burst_kinds")

KIND_HIGHBETA = "tape_burst_highbeta"
KIND_CHARTMAPS = "tape_burst_chartmaps"
KINDS = (KIND_HIGHBETA, KIND_CHARTMAPS)          # precedence after trade_flash, in this order
EVENTS_COLL = "tape_burst_events"

HIGHBETA_MAX_SYMBOLS = 150      # Ajay 2026-10-14 — "cap 150, biggest drop first"
CHARTMAPS_MAX_SYMBOLS = 150     # Ajay 2026-10-14 — cap 150
# ~6 names per tab under the cap, by round-robin over ~24 tabs (A13).
FETCH_WORKERS = 4               # MINE (AMENDMENTS §8) — tail fetches in flight
KINDS_BUDGET_SEC = 200          # MINE (AMENDMENTS §8) — wall budget for both kinds per poll
WATCH_HTTP_TIMEOUT_SEC = 20     # MINE (AMENDMENTS §8) — the board_bands timeout

# The 🎢 tab's own membership snapshot is NOT read into the 🗺️ union: its
# names belong to the 🎢 kind (A5 precedence), whose watch list is his cut
# (biggest drop first, HIGHBETA_MAX_SYMBOLS). The tab's top-80 snapshot, read
# here, would ring a name his cut left out as 🗺️ — the wrong kind.
OWNED_TABS = ("high_beta",)     # the 🎢 tab id (chart_maps TAB_KEY), owned by KIND_HIGHBETA
# 🕯️ Doji Sweep (AMENDMENTS6 B3, 2026-10-16): the tab ships with NO push (DECISIONS6 —
# "NO alert, NO push in this build"), so its membership snapshot never joins the 🗺️
# union and never thins the other tabs' share of the CHARTMAPS_MAX_SYMBOLS cap.
EXCLUDED_TABS = ("doji_sweep",)  # 2026-10-16 — Doji Sweep names never ride the 🗺️ watch (his call Q15)

HB_MARK = "\U0001F3A2"                           # 🎢
CM_MARK = "\U0001F5FA️"                     # 🗺️ — MINE (AMENDMENTS §8)
TITLE_FMT = {KIND_HIGHBETA: HB_MARK + " High-Beta tape burst — {lead}",
             KIND_CHARTMAPS: CM_MARK + " Chart Maps tape burst — {lead}"}
URL_FMT = "/sepa/{sym}?tab=tape&from=chart-maps"
WATCH_PATH = "/chart-maps/high-beta/watch"
WATCH_WARMING_REASON = "watch list warming — the next poll reads it"


def tape_url(sym: str) -> str:
    """The Tape tab of one name — the push's tap-route and each /alerts item's."""
    return URL_FMT.format(sym=sym)


def _price_floor() -> float:
    """The house share-price floor, by name (trading.safety_floor)."""
    from trading.safety_floor import MIN_SHARE_PRICE
    return float(MIN_SHARE_PRICE)


def parse_kinds(spec) -> tuple:
    """'all' / None / '' → every kind; a comma list → the known ones in
    precedence order (unknown names ignored — a list of only unknown names
    runs no kind). PURE."""
    if spec is None:
        return KINDS
    if isinstance(spec, (list, tuple, set, frozenset)):
        toks = {str(t).strip().lower() for t in spec}
    else:
        s = str(spec).strip().lower()
        if s in ("", "all"):
            return KINDS
        toks = {t.strip() for t in s.split(",")}
    if "all" in toks:
        return KINDS
    return tuple(k for k in KINDS if k in toks)


# ── watch lists ──────────────────────────────────────────────────────────────
def highbeta_watch(*, get=None) -> tuple:
    """(watch rows, reason | None, counts) for the 🎢 kind.

    ONE GET of the api's own memo (`board.high_beta_watch`, served biggest
    drop first). `state != "ready"` → [] with the reason (a cold memo starts
    its warm server-side; the next poll reads it). An HTTP failure → [] and
    `watch_http_fail: 1` — never an in-process warm (A9). Never raises."""
    counts = {"watch_http_fail": 0, "listed": 0}
    try:
        if get is None:
            import requests
            get = requests.get
        base = os.getenv("INTERNAL_API_BASE", "http://api:8000")
        r = get(f"{base}{WATCH_PATH}", headers={"X-User-Email": "cron@internal"},
                timeout=WATCH_HTTP_TIMEOUT_SEC)
        if getattr(r, "status_code", None) != 200:
            counts["watch_http_fail"] = 1
            return [], f"watch list HTTP {getattr(r, 'status_code', None)}", counts
        data = r.json() or {}
    except Exception as exc:
        counts["watch_http_fail"] = 1
        log.info("tape_burst_highbeta: watch list over HTTP failed: %s", exc)
        return [], f"watch list unreachable ({type(exc).__name__})", counts
    if not isinstance(data, dict):
        counts["watch_http_fail"] = 1
        return [], "watch list unreadable", counts
    if data.get("state") != "ready":
        reason = WATCH_WARMING_REASON if data.get("state") == "warming" else (
            "watch list %s%s" % (data.get("state") or "not ready",
                                 f" ({data['reason']})" if data.get("reason") else ""))
        return [], reason, counts
    seen, rows = set(), []
    for row in data.get("symbols") or []:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol") or "").strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        rows.append({"symbol": sym, "beta": TF._num(row.get("beta")),
                     "cats": [str(c) for c in (row.get("cats") or [])],
                     "move_pct": TF._num(row.get("move_pct")),
                     "state": row.get("state")})
    counts["listed"] = len(rows)
    return rows[:HIGHBETA_MAX_SYMBOLS], None, counts


def _et_date(stamp, tz) -> Optional[str]:
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        dt = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).date().isoformat()


def _prev_market_day(d):
    """The market day before `d` on the house NYSE calendar
    (market_hours.reminder.is_market_day), walking back like
    KL.prev_market_day. Calendar only, so this push path never imports the
    display-only supply_demand.key_levels (test_key_levels import guard)."""
    from market_hours.reminder import is_market_day
    x = d - timedelta(days=1)
    for _ in range(8):
        if is_market_day(datetime.combine(x, dtime(12, 0))):
            return x
        x -= timedelta(days=1)
    return x


def chartmaps_watch(*, exclude, now, db=None) -> tuple:
    """(watch rows, counts) for the 🗺️ kind. ONE projected find on
    `chart_maps_membership` (the 🎢 tab skipped — OWNED_TABS; the 🕯️ tab
    skipped — EXCLUDED_TABS, no push in its build); a tab counts
    only when its snapshot was written
    today or on the last market day (ET) — else `tabs_old`, its names not
    watched. Round-robin by served rank over the fresh tabs in tab-id order
    (rank 1 of every tab, then rank 2 …), deduped, minus `exclude`, cut at
    CHARTMAPS_MAX_SYMBOLS. Each row: {symbol, tabs: every fresh tab holding
    it}. A dead Mongo → [] (counted `mongo_down`). Never raises."""
    counts = {"tabs_read": 0, "tabs_old": 0, "union": 0, "excluded": 0,
              "watched": 0, "mongo_down": 0}
    try:
        from chart_maps import membership as M
        d = db if db is not None else TF._db()
        if d is None:
            counts["mongo_down"] = 1
            return [], counts
        docs = list(d[M.COLL].find({}, M.PROJECTION) or [])
    except Exception as exc:
        log.info("tape_burst_chartmaps: membership read failed: %s", exc)
        counts["mongo_down"] = 1
        return [], counts
    tz = now.tzinfo or timezone.utc
    today = now.date()
    ok_days = {today.isoformat(), _prev_market_day(today).isoformat()}
    tabs = {}
    for doc in docs:
        tab = doc.get("_id") if isinstance(doc, dict) else None
        if (not tab or tab == M.SELF_TAB or tab in M.SKIP_TABS or tab in OWNED_TABS
                or tab in EXCLUDED_TABS):
            continue
        if _et_date(doc.get("built_at"), tz) not in ok_days:
            counts["tabs_old"] += 1
            continue
        syms, seen = [], set()
        for s in doc.get("symbols") or []:
            u = str(s or "").strip().upper()
            if u and u not in seen:
                seen.add(u)
                syms.append(u)
        tabs[str(tab)] = syms
    counts["tabs_read"] = len(tabs)
    order = sorted(tabs)
    union = set().union(*tabs.values()) if tabs else set()
    excl = {str(s).upper() for s in (exclude or ())}
    counts["union"] = len(union)
    counts["excluded"] = len(union & excl)
    picked, seen = [], set()
    depth = max((len(v) for v in tabs.values()), default=0)
    for rank in range(depth):
        for tab in order:
            syms = tabs[tab]
            if rank >= len(syms):
                continue
            sym = syms[rank]
            if sym in seen or sym in excl:
                continue
            seen.add(sym)
            picked.append(sym)
            if len(picked) >= CHARTMAPS_MAX_SYMBOLS:
                break
        if len(picked) >= CHARTMAPS_MAX_SYMBOLS:
            break
    rows = [{"symbol": s, "tabs": [t for t in order if s in tabs[t]]} for s in picked]
    counts["watched"] = len(rows)
    return rows, counts


# ── pure: events + words ─────────────────────────────────────────────────────
def free_events(symbol: str, kind: str, bursts: list, day: str, *, meta: dict,
                zone: Optional[tuple] = None) -> tuple:
    """(event docs, n at a zone) — EVERY burst is an event (location-free),
    the auction crosses excepted. `zone` = (board, band) when the name is on
    the zone boards: a burst in / near that band carries it (`board`,
    `zone_lo`, `zone_hi`, `at_zone`) and still rings as this kind (A5). PURE."""
    board, band = zone if zone else (None, None)
    lo, hi = TF._num((band or {}).get("lo")), TF._num((band or {}).get("hi"))
    out, at_zone = [], 0
    for b in bursts or []:
        if b.get("time_et") in TF.AUCTION_CROSS_ET:
            continue                             # the auction, not an aggressor
        ev = {
            "_id": TF.event_id(symbol, day, b["time_et"]),
            "kind": kind,
            "symbol": symbol.upper(),
            "et_date": day,
            "time_et": b["time_et"],
            "side": b["side"],
            "dollars": TF._num(b.get("dollars")),
            "volume": b.get("volume"),
            "n_trades": b.get("n_trades"),
            "price": TF._num(b.get("price")),
            **(meta or {}),
            "recorded_at": int(_time.time()),
        }
        where = TF.classify_zone(b.get("price"), lo, hi) if board else None
        if where:
            ev.update({"board": board, "zone_lo": lo, "zone_hi": hi, "at_zone": where})
            at_zone += 1
        out.append(ev)
    return out, at_zone


def headline(ev: dict) -> str:
    """One push line per event — what printed, never what it means next. PURE."""
    amt = TF.fmt_dollars(ev.get("dollars"))
    head = f"{ev['symbol']} {ev['time_et']} — {amt} {ev['side']} burst"
    if ev.get("kind") == KIND_CHARTMAPS:
        n = len(ev.get("tabs") or [])
        price = TF._num(ev.get("price"))
        at = f" at {price:.2f}" if price is not None else ""
        return f"{head}{at} · on {n} Chart Maps tab{'' if n == 1 else 's'}"
    beta, move = TF._num(ev.get("beta")), TF._num(ev.get("move_pct"))
    line = head + (f" · β {beta:.2f}" if beta is not None else "")
    line += f" · {move:+.2f}% today" if move is not None else ""
    if ev.get("at_zone") and ev.get("board") in ("demand", "supply"):
        line += f" · {ev['at_zone']} the {ev['board']} zone"
    return line


def _meta(kind: str, row: dict) -> dict:
    if kind == KIND_CHARTMAPS:
        return {"tabs": list(row.get("tabs") or [])}
    return {"beta": row.get("beta"), "cats": list(row.get("cats") or []),
            "move_pct": row.get("move_pct")}


# ── impure: scan one kind ────────────────────────────────────────────────────
_SKIPPED = object()


def scan_kind(kind: str, watch: list, *, zone_map: dict, tails: dict, day: str,
              deadline: float, fetch_fn=None, clock=_time.monotonic,
              floor: Optional[float] = None) -> tuple:
    """(events, counts) for one kind's watch list. A name the zone pass
    already fetched reuses its tail (no second request, never budget-cut);
    the rest are fetched FETCH_WORKERS at a time, and a fetch that would START
    at or after `deadline` is not made (`skipped_budget`). A tail whose last
    regular print is under the house share-price floor is `under_floor`."""
    fetch_fn = fetch_fn or TF.fetch_recent_trades
    floor = _price_floor() if floor is None else floor
    counts = {"watched": len(watch), "fetched": 0, "no_tape": 0, "under_floor": 0,
              "skipped_budget": 0}
    frames = {}
    need = []
    for row in watch:
        sym = row["symbol"]
        if sym in tails:
            frames[sym] = tails[sym]
        else:
            need.append(sym)

    def one(sym):
        if clock() >= deadline:
            return sym, _SKIPPED
        try:
            return sym, fetch_fn(sym)
        except Exception as exc:
            log.debug("%s fetch %s failed: %s", kind, sym, exc)
            return sym, None

    if need:
        with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
            for sym, df in pool.map(one, need):
                if df is _SKIPPED:
                    counts["skipped_budget"] += 1
                    continue
                counts["fetched"] += 1
                frames[sym] = df
    events = []
    for row in watch:
        sym = row["symbol"]
        if sym not in frames:
            continue
        df = frames[sym]
        try:
            last = float(df["price"].iloc[-1]) if df is not None and len(df) else None
        except Exception:
            last = None
        if last is not None and last < floor:
            counts["under_floor"] += 1
            continue
        bursts = TF.bursts_from_tail(df)
        if bursts is None:
            counts["no_tape"] += 1
            continue
        evs, _n_zone = free_events(sym, kind, bursts, day, meta=_meta(kind, row),
                                   zone=zone_map.get(sym))
        events.extend(evs)
    counts["_at_zone_ids"] = [e["_id"] for e in events if e.get("at_zone")]
    return events, counts


# ── the pass ─────────────────────────────────────────────────────────────────
def prepare(kinds=None, *, get=None) -> dict:
    """The plan the zone pass reads BEFORE its push: the kinds to run and the
    🎢 watch list (read once, here). Never raises."""
    ks = parse_kinds(kinds)
    plan = {"kinds": ks, "hb_watch": [], "hb_reason": None, "hb_counts": {}}
    if KIND_HIGHBETA in ks:
        plan["hb_watch"], plan["hb_reason"], plan["hb_counts"] = highbeta_watch(get=get)
    return plan


def deferred_symbols(plan: Optional[dict]) -> frozenset:
    """The names whose bursts — at a zone or not — ring as 🎢, so the zone
    pass leaves them out of its own push (A5). Empty when the 🎢 kind is not
    running this poll (the zone pass is then exactly what it was)."""
    if not plan or KIND_HIGHBETA not in (plan.get("kinds") or ()):
        return frozenset()
    return frozenset(r["symbol"] for r in plan.get("hb_watch") or [])


def _record(kind, events, *, fresh_since, dry_run, record_fn):
    return record_fn(events, kind=kind, coll_name=EVENTS_COLL,
                     title_fmt=TITLE_FMT[kind], headline_fn=headline, url_fn=tape_url,
                     precheck_colls=(TF.EVENTS_COLL,), fresh_since=fresh_since,
                     dry_run=dry_run)


def _served(scan_counts: dict, rec: dict) -> dict:
    """Fresh-only counters (A3): `candidates` = this poll's new bursts on the
    watch list (written now by this kind, by ⚡ trade flash, or by the other
    tape kind); a re-sighting inside the LOOKBACK_MIN overlap counts nowhere
    but `dup_same` / `dup_earlier`."""
    fresh_ids = set(rec.get("fresh_ids") or [])
    out = {k: v for k, v in scan_counts.items() if not k.startswith("_")}
    out.update({
        "new": int(rec.get("new") or 0) if not rec.get("dry_run") else int(rec.get("would_push") or 0),
        "pushed": int(bool(rec.get("pushed"))),
        "dup_trade_flash": int(rec.get("dup_precheck_fresh") or 0),
        "dup_kind": int(rec.get("dup_kind") or 0),
        "dup_same": int(rec.get("dup_same") or 0),
        "dup_earlier": int(rec.get("dup_earlier") or 0)
        + int(rec.get("dup_precheck") or 0) - int(rec.get("dup_precheck_fresh") or 0),
        "at_zone": len(fresh_ids & set(scan_counts.get("_at_zone_ids") or [])),
    })
    out["candidates"] = out["new"] + out["dup_trade_flash"] + out["dup_kind"]
    return out


def run_all(*, zone_bands, tails, now, kinds=None, plan=None, fresh_since=None,
            dry_run: bool = False, fetch_fn=None, clock=_time.monotonic,
            record_fn=None, status_fn=None, db=None) -> dict:
    """Both kinds, 🎢 first, one shared wall budget (KINDS_BUDGET_SEC).
    Returns {kind: {..counters, "ran": True[, "reason"][, "watch"]}}; a dry
    run also lists each watch list and records no pass."""
    plan = plan if plan is not None else prepare(kinds)
    record_fn = record_fn or TF.record_and_push
    if status_fn is None:
        from supply_demand import alert_status as AS
        status_fn = AS.record_pass
    day = now.strftime("%Y-%m-%d")
    zone_map = {sym: (board, band) for sym, board, band in (zone_bands or [])}
    deadline = clock() + KINDS_BUDGET_SEC
    out = {}
    hb_syms = set()

    if KIND_HIGHBETA in plan["kinds"]:
        watch = plan.get("hb_watch") or []
        hb_syms = {r["symbol"] for r in watch}
        events, sc = scan_kind(KIND_HIGHBETA, watch, zone_map=zone_map, tails=tails,
                               day=day, deadline=deadline, fetch_fn=fetch_fn, clock=clock)
        rec = _record(KIND_HIGHBETA, events, fresh_since=fresh_since, dry_run=dry_run,
                      record_fn=record_fn)
        res = dict(_served(sc, rec), **(plan.get("hb_counts") or {}), ran=True)
        reason = plan.get("hb_reason") or (rec.get("reason") if not rec.get("ok") else None)
        if reason:
            res["reason"] = reason
        if dry_run:
            res["watch"] = [r["symbol"] for r in watch]
        out[KIND_HIGHBETA] = res

    if KIND_CHARTMAPS in plan["kinds"]:
        watch, wc = chartmaps_watch(exclude=set(zone_map) | hb_syms, now=now, db=db)
        # zone names are excluded, so no zone band is passed: every event here
        # is off the zone boards by construction
        events, sc = scan_kind(KIND_CHARTMAPS, watch, zone_map={}, tails=tails,
                               day=day, deadline=deadline, fetch_fn=fetch_fn, clock=clock)
        rec = _record(KIND_CHARTMAPS, events, fresh_since=fresh_since, dry_run=dry_run,
                      record_fn=record_fn)
        res = dict(_served(sc, rec), **{k: v for k, v in wc.items() if k != "watched"},
                   ran=True)
        reason = ("Chart Maps membership unreadable" if wc.get("mongo_down") else
                  rec.get("reason") if not rec.get("ok") else None)
        if reason:
            res["reason"] = reason
        if dry_run:
            res["watch"] = [r["symbol"] for r in watch]
        out[KIND_CHARTMAPS] = res

    if not dry_run:
        for kind, res in out.items():
            try:
                status_fn(kind, {k: v for k, v in res.items()
                                 if k not in ("ran", "reason", "watch")},
                          now, reason=res.get("reason"))
            except Exception as exc:                     # best-effort, never fatal
                log.warning("%s: record_pass failed: %s", kind, exc)
    log.info("TAPE-BURST kinds: %s", {k: {kk: vv for kk, vv in v.items() if kk != "watch"}
                                      for k, v in out.items()})
    return out


__all__ = ["KIND_HIGHBETA", "KIND_CHARTMAPS", "KINDS", "EVENTS_COLL",
           "HIGHBETA_MAX_SYMBOLS", "CHARTMAPS_MAX_SYMBOLS", "FETCH_WORKERS",
           "KINDS_BUDGET_SEC", "WATCH_HTTP_TIMEOUT_SEC", "OWNED_TABS", "EXCLUDED_TABS", "TITLE_FMT", "URL_FMT",
           "WATCH_PATH", "tape_url", "parse_kinds", "highbeta_watch",
           "chartmaps_watch", "free_events", "headline", "scan_kind", "prepare",
           "deferred_symbols", "run_all"]
