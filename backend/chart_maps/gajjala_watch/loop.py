"""👀 Gajjala's Watch — the minute loop, the add-time build child and the CLI (spec 2026-11-15 §3.5.3, WP-B).

Ajay, verbatim (2026-11-15): "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and
add remove tickers from the dashboard. When I add a ticker I need 1 min 3 min and 5 min charts... I need alerts on these
from 1 min to I can be ready".

CADENCE. The 5-minute 🚩 cron pass (`chart_maps.gajjala.run.main`, cron path only) SPAWNS `python -m
chart_maps.gajjala_watch.loop --loop` DETACHED at the START of its path (`run._spawn_watch`) and goes on with its own
pass. The loop reads one closed 1-minute bar per iteration: iteration 0 at max(spawn, tick + BAR_SETTLE_SEC) (a late
spawn runs at once, [C1.4]), then :30 of each following minute — tick+0:30 … tick+4:30 (≤ 5 per slot) while
start + BAR_SETTLE_SEC ≤ the next cron tick and the bar closes by the session's extended close. After every sleep the
wall clock is re-checked: a wake in another slot (host sleep) ends the loop ([C2.6]). The host-sleep watchdog counts this
argv as a detached child (`ops/docker_watchdog.py CRON_DETACHED_CHILD_ARGS`).

LEASE ([C1.1/C2.2]). The ONE lease engine (`chart_maps.gajjala.store.GajjalaStore.claim_lease` / `release_lease`) with
GG1's numbers (GG1M_LEASE_SEC 55 s, GG1M_LEASE_MIN_GAP_SEC 0 — `_lease_nums()` of a V.GG1 store) on an INJECTED
collection (`gajjala_watch_state`, `_id` "lease"): claimed and released once per iteration; a held lease skips THAT
minute (`skipped`), never ends the loop.

ITERATION. owner list (empty → no lease, no fetch) → lease → session → the last good read's stamps (`seen`) → the
closed 1/3/5-minute frames (budget = min(GG1M_MINUTE_BUDGET_SEC, the time left in the slot)) → the cross push
(cross_alerts.run — BEFORE the tile writes, fenced) → one tile doc per listed name → the state doc "latest" → release.

BUILD CHILD (`--build`, [C2.5]): the API spawns it when a name is added and the loop will not read within the minute;
it builds every listed name with no tile doc / another session / not loaded, re-reading the list until nothing is left
(each name tried once). Never the cross push, never a state doc, no lease. UNMEASURED — nothing here trades.

🤖 AUTO (2026-11-17, spec ggwauto §3.3 — Ajay: "I need portentials from Gajjals's 1 min and regular and also Audited
potentials with good volume to Watchlist on an interval.. Remove as they are not progressing"). Each iteration, under the
SAME lease and before the frame build, `auto.step` keeps the auto doc (adds / removals, zero fetches); the frames, the
tiles and the state doc then cover his names + the auto names (his first, the auto names in the order they were added).
With nothing listed and nothing auto, out of the pass window → no lease (as before); IN the window an empty list claims
the lease once for the auto step and calls no loader when nothing is added. The cross push (cross_alerts.run, byte
untouched) is GIVEN his names' frames only while C.AUTO_PUSH_MODE is "off"; an auto name's own-minute up cross is held
`suppressed_auto` (auto.hold_crosses — never sent, never claimed). [C6] `alerts` stays the cross engine's OWN counts
over the frames it was GIVEN — `alerts.names` = his names (manual + auto only when the auto mode is "live");
`alerts.suppressed_auto` (present only when auto names were read) = the held count; `n_names` = manual + auto; `auto.n`
= the auto count. Never rewritten after the run. `--dry-run --symbols` (the stub) skips the auto step entirely;
`--dry-run` without it runs `auto.step(dry=True)` → `auto.writes` = the would-be doc, nothing written.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V

from . import auto as AUTO
from . import build as BLD
from . import colls as CO
from . import constants as C
from . import cross_alerts as XA

log = logging.getLogger("chart_maps.gajjala_watch.loop")

ET = ZoneInfo("America/New_York")
LEASE_HELD = "lease held"
LOOP_REASONS = ("no time left in the slot", "after the extended close", "slot passed (host sleep)", "off")
NO_TICKERS = "no tickers"
AUTO_OUT_KEYS = ("n", "cap", "added", "removed", "leaving", "skipped", "reason",     # the state doc's `auto` block
                 "aplus_skipped",                                                  # 🎯 2026-11-17 (spec ggwaplus2) — APPEND only
                 "not_eligible", "broker_fault")                                   # 🚫 2026-11-19 (spec watchfid) — APPEND only


def _default_load():
    return R1._memo_prev(RUN._load_day)


@dataclass
class Deps:
    load_day: Callable = field(default_factory=_default_load)   # prior day memoised per process, today re-fetched
    send: Optional[Callable] = None                             # (owner, payload) — None = cross_alerts._send
    owner: Optional[str] = None
    wall: Callable = R1._wall                                   # UTC-aware wall clock
    sleep: Callable = time.sleep


def dry_deps() -> Deps:
    """The loader WITHOUT the cache write (run._dry_load_day) and a recording sender (never called: dry stops first)."""
    sent: list = []
    d = Deps(load_day=RUN._dry_load_day,
             send=lambda owner, payload: (sent.append(payload), {"sent": 0, "failed": 0, "total_targets": 0})[1])
    d.sent = sent                                               # type: ignore[attr-defined]
    return d


def lease_store(state_coll) -> ST.GajjalaStore:
    """The ONE lease engine with GG1's (55, 0) on the watch's own state collection (a None handle → "no_store")."""
    return ST.GajjalaStore(colls={ST.STATE: state_coll}, variant=V.GG1)


def _state(cs: Optional[dict], _id: str, fields: dict) -> None:
    if not cs or cs.get("state") is None:
        return
    try:
        cs["state"].update_one({"_id": _id}, {"$set": fields}, upsert=True)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch: state write failed: %s", type(exc).__name__)


# ── one iteration ─────────────────────────────────────────────────────────────────────────────────────────────────
def run_iteration(now: Optional[datetime] = None, *, db=None, deps: Optional[Deps] = None, dry: bool = False,
                  symbols: Optional[list] = None, budget_sec: Optional[float] = None) -> dict:
    """One minute: the owner's tickers (+ 🤖 the auto step's names, 2026-11-17) → closed 1/3/5-minute frames → the cross
    push (his names' frames only while the auto mode is off) → the tile docs → the state doc.
    `symbols` (the --dry-run --symbols stub) REPLACES the owner list for this call and skips the auto step. `dry`: nothing written, nothing
    sent, no lease (the writes are returned in `writes`)."""
    deps = deps or Deps()
    now = RUN._utc(now) if now is not None else RUN._utc(deps.wall())
    t0 = time.monotonic()
    out: dict = {"at": now.isoformat(), "ran": False, "reason": None, "n_names": 0, "n_read": 0}
    if not dry and not CO.enabled():
        out["reason"] = "off"
        return out
    cs = CO.colls(db)
    stub = symbols is not None
    manual = list(dict.fromkeys(s for s in (symbols if stub else CO.owner_symbols(db)) if s))
    mk = {CO.fold(s) for s in manual}
    auto_known = ([] if stub else
                  [s for s in AUTO.current_symbols(cs, BLD.session_of(now)[0].isoformat()) if CO.fold(s) not in mk])
    out["n_names"] = len(manual) + len(auto_known)
    if not manual and (stub or (not auto_known and not RUN.in_window(now))):
        out["reason"] = NO_TICKERS
        if not dry:
            _state(cs, C.STATE_LATEST_ID, {"at": now, "n_names": 0, "reason": NO_TICKERS})
        return out
    lst = claim = None
    if not dry:
        lst = lease_store(cs["state"] if cs else None)
        claim = lst.claim_lease(now, ST.LEASE_CRON)
        if not claim:
            out["reason"] = LEASE_HELD
            out["lease"] = getattr(claim, "why", None)
            return out
    try:
        session = BLD.session_of(now)[0]
        if stub:
            auto_res: dict = {"symbols": [], "reason": "stub"}
        else:
            auto_res = {"symbols": auto_known, "reason": "error"}
            try:
                auto_res = AUTO.step(now, session, db=db, manual=manual, dry=dry)
            except Exception as exc:                            # noqa: BLE001 — the last entries stay served
                log.warning("gajjala watch 🤖: auto step failed: %s", type(exc).__name__)
        auto_syms = [s for s in dict.fromkeys(auto_res.get("symbols") or []) if CO.fold(s) not in mk]
        syms = manual + auto_syms
        auto_out = {k: auto_res.get(k) for k in AUTO_OUT_KEYS}
        auto_out.update(n=len(auto_syms), cap=C.AUTO_MAX_SYMBOLS)
        out["auto"] = dict(auto_out, writes=auto_res["writes"]) if dry and "writes" in auto_res else auto_out
        out["n_names"] = len(syms)
        if not syms:
            out["reason"] = NO_TICKERS
            if not dry:
                _state(cs, C.STATE_LATEST_ID, {"at": now, "n_names": 0, "reason": NO_TICKERS, "auto": auto_out})
            return out
        tiles = cs["tiles"] if cs else None
        seen = BLD.seen(tiles, syms)
        per_name: dict = {}
        stats: dict = {}
        budget = GC.GG1M_MINUTE_BUDGET_SEC if budget_sec is None else budget_sec
        w0 = RUN._utc(deps.wall())
        F = BLD.frames(syms, session, now, load_day=deps.load_day, budget_sec=budget, stats=stats,
                       per_name=per_name)
        # fix 2026-11-15: freshness is judged on the clock AFTER the fetch — `now` plus the wall time the fetch took
        # (a host sleep mid-fetch makes the cross stale: never sent late). The tile docs keep `now`.
        now_x = now + max(timedelta(0), RUN._utc(deps.wall()) - w0)
        held: dict = {}
        auto_live = AUTO.push_mode() == C.AUTO_PUSH_MODES[1]
        ak = {CO.fold(s) for s in auto_syms}
        F_push = {s: f for s, f in F.items() if auto_live or CO.fold(s) not in ak}      # [C6] his names' frames only
        try:
            counts = XA.run(F_push, now_x, session, coll=(cs["alerts"] if cs else None), send=deps.send,
                            owner=deps.owner, dry=dry, seen=seen, held=held)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala watch: cross push failed: %s", type(exc).__name__)
            counts = {"error": 1}
        if auto_syms and not auto_live:
            try:
                counts[C.AUTO_HELD_REASON] = AUTO.hold_crosses({s: f for s, f in F.items() if CO.fold(s) in ak},
                                                               now_x, session, held)
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch 🤖: auto hold failed: %s", type(exc).__name__)
        updates = []
        for sym in syms:
            try:
                updates.append(BLD.tile_update(sym, F.get(sym), session, now, BLD.status_of(per_name.get(sym, {})),
                                               held.get(sym, {})))
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch: tile %s failed: %s", sym, type(exc).__name__)
                updates.append(BLD.tile_update(sym, None, session, now, "failed", held.get(sym, {})))
        if dry:
            out["writes"] = updates
        else:
            BLD.write(tiles, updates)
        out.update(ran=True, session=session.isoformat(), n_read=len(F), bars=stats, alerts=counts,
                   wall_s=round(time.monotonic() - t0, 3))
        if not dry:
            _state(cs, C.STATE_LATEST_ID, {"at": now, "session": session.isoformat(), "n_names": len(syms),
                                           "n_read": len(F), "bars": stats, "alerts": counts,
                                           "wall_s": out["wall_s"], "reason": None, "auto": auto_out})
        return out
    finally:
        if lst is not None and claim is not None:
            try:
                lst.release_lease(now, getattr(claim, "token", None))
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch: lease release failed: %s", type(exc).__name__)


# ── the slot's iterations (a DETACHED child of the 5-minute cron pass) ─────────────────────────────────────────────
def loop(now: Optional[datetime] = None, *, db=None, deps: Optional[Deps] = None) -> dict:
    """The slot's iterations at tick+0:30 … tick+4:30 (iteration 0 at max(spawn, tick + BAR_SETTLE_SEC)). A held lease
    skips that minute; the loop ends on: no time left in the slot · after the extended close · slot passed (host
    sleep) · off. Ends with the state doc "loop" {tick, n, skipped, reason, ended_at}."""
    deps = deps or Deps()
    spawn = RUN._utc(now) if now is not None else RUN._utc(deps.wall())
    tick, next_tick = R1.slot_of(spawn)
    settle = timedelta(seconds=GC.BAR_SETTLE_SEC)
    start = max(spawn, RUN._utc(tick + settle))
    out: dict = {"tick": tick.isoformat(), "n": 0, "skipped": 0, "reason": None, "iterations": []}
    n = skipped = 0
    if not CO.enabled():
        out["reason"] = "off"
    else:
        while True:
            if start + settle > RUN._utc(next_tick):
                out["reason"] = LOOP_REASONS[0]
                break
            if R1._after_extended_close(start):
                out["reason"] = LOOP_REASONS[1]
                break
            delay = (start - RUN._utc(deps.wall())).total_seconds()
            if delay > 0:
                deps.sleep(delay)
            wall = RUN._utc(deps.wall())
            # [C2.6] re-checked AFTER the sleep: a wake in another slot, or more than BAR_SETTLE_SEC past the planned
            # start, ends the loop. A real sleep always wakes a little late, so the planned-start test is never
            # `wall + settle > next_tick` (that dropped the tick+4:30 iteration on every slot — refix 2026-11-15).
            if R1.slot_of(wall)[0] != tick or wall > start + settle:
                out["reason"] = LOOP_REASONS[2]
                break
            budget = min(float(GC.GG1M_MINUTE_BUDGET_SEC), (RUN._utc(next_tick) - start).total_seconds())
            try:
                res = run_iteration(max(wall, start), db=db, deps=deps, budget_sec=budget)
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch: iteration failed: %s", type(exc).__name__)
                res = {"ran": False, "reason": "error"}
            out["iterations"].append({k: res.get(k) for k in ("at", "ran", "reason", "n_names", "n_read",
                                                               "wall_s")})
            if res.get("reason") == LEASE_HELD:
                skipped += 1                                    # [C1.1] skip that minute, keep looping
            else:
                n += 1
            start = max(RUN._utc(deps.wall()), R1.next_start(start))
    out["n"], out["skipped"] = n, skipped
    _state(CO.colls(db), C.LOOP_STATE_ID, {"tick": RUN._utc(tick), "n": n, "skipped": skipped,
                                           "reason": out["reason"], "ended_at": RUN._utc(deps.wall())})
    log.info("gajjala watch loop: tick %s — %d iteration(s), %d skipped, %s", tick.strftime("%H:%M"), n, skipped,
             out["reason"])
    return out


# ── the add-time build child ──────────────────────────────────────────────────────────────────────────────────────
def build_pending(now: Optional[datetime] = None, *, db=None, deps: Optional[Deps] = None) -> dict:
    """[C2.5] Build every LISTED name whose tile is missing, from another session, or not loaded — the session of
    `now` (a closed day / before 04:00 → the last market session). Re-reads the list after each round (a name added
    meanwhile is picked up); each name is tried once per child. No cross push, no state doc, no lease."""
    deps = deps or Deps()
    now = RUN._utc(now) if now is not None else RUN._utc(deps.wall())
    if not CO.enabled():                                        # off → no minute fetch from the build child either
        return {"session": None, "built": [], "rounds": 0, "reason": "off"}
    session = BLD.session_of(now)[0]
    iso = session.isoformat()
    cs = CO.colls(db)
    tiles = cs["tiles"] if cs else None
    tried: set = set()
    out: dict = {"session": iso, "built": [], "rounds": 0}
    while True:
        syms = CO.owner_symbols(db)
        docs: dict = {}
        if tiles is not None and syms:
            try:
                docs = {d["_id"]: d for d in tiles.find({"_id": {"$in": list(syms)}}, {"session": 1, "status": 1})
                        if isinstance(d, dict)}
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch build: tile read failed: %s", type(exc).__name__)
        todo = [s for s in syms if s not in tried
                and (s not in docs or docs[s].get("session") != iso or docs[s].get("status") != "loaded")]
        if not todo:
            break
        out["rounds"] += 1
        per_name: dict = {}
        F = BLD.frames(todo, session, now, load_day=deps.load_day, budget_sec=GC.PASS_BUDGET_SEC, stats={},
                       per_name=per_name)
        updates = []
        for s in todo:
            try:
                updates.append(BLD.tile_update(s, F.get(s), session, now, BLD.status_of(per_name.get(s, {}))))
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch build: tile %s failed: %s", s, type(exc).__name__)
                updates.append(BLD.tile_update(s, None, session, now, "failed"))
        BLD.write(tiles, updates)
        tried |= set(todo)
        out["built"] += todo
    return out


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chart_maps.gajjala_watch.loop", description=__doc__.split("\n")[0])
    ap.add_argument("--loop", action="store_true", help="the slot's iterations (run.main spawns this, detached)")
    ap.add_argument("--build", action="store_true", help="build every pending listed name (the API spawns this)")
    ap.add_argument("--dry-run", action="store_true", help="one iteration; record every write and send; touch nothing")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    ap.add_argument("--now", help="ISO clock to replay (a naive stamp is ET) — --dry-run only")
    ap.add_argument("--symbols", help="comma list REPLACING the owner list for this run — --dry-run only")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if args.now and not args.dry_run:
        log.warning("gajjala watch: a --now replay writes the real store unless --dry-run; refusing")
        return 2
    if args.symbols and not args.dry_run:
        log.warning("gajjala watch: --symbols replaces the owner list only on a --dry-run; refusing")
        return 2
    now = datetime.fromisoformat(args.now) if args.now else None
    if now is not None and now.tzinfo is None:
        now = now.replace(tzinfo=ET)                            # a naive --now is ET (the house rule), never UTC
    if args.dry_run:
        syms = [s.strip().upper() for s in (args.symbols or "").split(",") if s.strip()] or None
        out = run_iteration(now, deps=dry_deps(), dry=True, symbols=syms)
    elif args.build:
        if not CO.enabled():
            log.info("gajjala watch: off (%s) — no build", C.ENV_ENABLED)
            return 0
        out = build_pending(now)
    else:
        if not CO.enabled():
            log.info("gajjala watch: off (%s) — nothing to do", C.ENV_ENABLED)
            return 0
        if not RUN.in_window(RUN._utc(now)):
            log.info("gajjala watch: outside %s–%s ET on a market day — nothing to do", GC.PASS_OPEN_ET,
                     GC.PASS_CLOSE_ET)
            return 0
        out = loop(now) if args.loop else run_iteration(now)
    if args.json:
        print(json.dumps(out, default=str))
    elif not args.loop:
        log.info("gajjala watch: %s", {k: out.get(k) for k in ("ran", "reason", "n_names", "n_read", "bars", "alerts",
                                                              "built", "wall_s")})
    return 0


__all__ = ["Deps", "dry_deps", "lease_store", "run_iteration", "loop", "build_pending", "main", "LEASE_HELD",
           "LOOP_REASONS", "NO_TICKERS"]


if __name__ == "__main__":
    sys.exit(main())
