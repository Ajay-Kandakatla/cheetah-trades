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
closed 1/5/15-minute frames (budget = min(GG1M_MINUTE_BUDGET_SEC, the time left in the slot)) → the cross push
(cross_alerts.run — BEFORE the tile writes, fenced) → one tile doc per listed name → the state doc "latest" → release.

BUILD CHILD (`--build`, [C2.5]): the API spawns it when a name is added and the loop will not read within the minute;
it builds every listed name with no tile doc / another session / not loaded, re-reading the list until nothing is left
(each name tried once). Never the cross push, never a state doc, no lease. UNMEASURED — nothing here trades.

C2.5 SUPERSEDED 2026-11-19 (Ajay, relayed verbatim: "When I add a new ticket they are gettinf added in to que but not
active / charts are not loading I amhaving to click on the chips again"): IN the window the API now spawns the same child
with `--new-only` (C.ARGV_BUILD_NEW) instead of waiting for the minute loop. `--new-only` reads ONLY a listed name with
no tile doc, or whose add time (the list doc's `added`, CO.added_of) is LATER than its tile doc's last write `at`
(`_new_only_todo`). Cost: 1–2 Massive minute calls per added name: today (forced, bars.py:287) + the prior day when the
1-minute cache misses (bars.py:283 — a brand-new name always misses); single-flight. Out of the window the plain
`--build` child is unchanged (its path never reads `added`).

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

📈📐 2026-11-23 (spec vwapzones rev 2 §3.5 — Ajay: "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15
accross board" · "Add vwap and supply demand too"). Frames 1 / 5 / 15 (C.FRAMES); the VWAP is computed inside the tile
build (after the cross push — nothing here can delay a ring). The daily zones NEVER run inside `run_iteration` (a slow
daily read would end the slot, Z7): `--loop` starts the levels module's daemon thread (`_levels(thread=True)`) before the
slot's iterations; `--build` [C1] loops `build_pending` → `_levels(first=built)` with ONE shared `tried` set (a
`no_prints` / `failed` name is fetched once per child) and ENDS on the list re-read (the child's LAST act — a name added
while the zones were read is built by the same child). `build_pending` also rebuilds a listed doc that lacks a tf of
C.FRAMES (an old 1m/3m/5m doc → 15m); `--new-only` does not. Display only, UNMEASURED.

🔌 2026-11-23 (spec ggconn rev 2 §3.4, WP-3 — Ajay: "Can you clean up some connection I am seeing delays price update for
AKAN on the watch chart.." · "I would like us to focus on connections of Gajjala more for the rest of the tabs."). The
minute loader reads with the Watch's OWN breaker (rest.load_day, C.REST_OWN_BREAKER_ON), a new closed one for every read
(`REST.open_read()` on this thread, before the frame build) — a trip costs the rest of that read, never the next minute;
`dry_deps` and every other caller keep the module breaker. A per-session counter doc `rest:{session}` (C.COLL_STATE)
counts iterations, names and failed name-minutes on every iteration that ran (never on --dry-run); the `latest` state doc
gains no key. The re-read of a minute's `failed` names is BUILT and OFF (C.REST_REREAD_ON = HIS CALL) — order when on:
push → tiles → pause → re-read → push → tiles, one fenced block after today's tile write; a re-read keeps the iteration's
own `now` (the frame cut) and judges freshness on the clock after it. `build_pending` gets none of it. `main` installs
the log key scrub (observability.logsetup.install_redaction). UNMEASURED.

✅ 2026-11-24 (spec watchall rev 2 §3.4 — Ajay: "Anytime stocks qualify all his rules should be auto added to the Watch
list so I can keep tracking them later"). Before `auto.step` the loop reads the 🤖 doc once (`auto_prior`, its own try —
a fault → None); after it `allrules.step` keeps the ✅ doc (own try/except; given `auto_prior` and the step's
`aplus_now`). The ✅ names join the frames LAST (`syms = manual + auto + rules`, fold-de-duplicated) so the minute budget
falls on them first. [C3] Their crosses ring only while C.RULES_PUSH_MODE is "live" (built "off", NOT tied to
C.AUTO_PUSH_MODE): `hold_k` = the 🤖 folds unless the auto mode is live ∪ the ✅ folds unless the rules mode is live;
the cross push is given every frame outside `hold_k`, and `auto.hold_crosses` holds the `hold_k` frames
`suppressed_auto` (both the first push and the REST re-read twin). The state doc gains `rules` (C.RULES_OUT_KEYS).
"""
from __future__ import annotations

import argparse
import importlib
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

from . import allrules as RULES
from . import auto as AUTO
from . import build as BLD
from . import colls as CO
from . import constants as C
from . import cross_alerts as XA
from . import rest as REST
from . import runseat as RUNSEAT

log = logging.getLogger("chart_maps.gajjala_watch.loop")

ET = ZoneInfo("America/New_York")
LEASE_HELD = "lease held"
LOOP_REASONS = ("no time left in the slot", "after the extended close", "slot passed (host sleep)", "off")
NO_TICKERS = "no tickers"
AUTO_OUT_KEYS = ("n", "cap", "added", "removed", "leaving", "skipped", "reason",     # the state doc's `auto` block
                 "aplus_skipped",                                                  # 🎯 2026-11-17 (spec ggwaplus2) — APPEND only
                 "not_eligible", "broker_fault")                                   # 🚫 2026-11-19 (spec watchfid) — APPEND only


def _default_load():
    return R1._memo_prev(REST.load_day if C.REST_OWN_BREAKER_ON else RUN._load_day)


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
    """One minute: the owner's tickers (+ 🤖 the auto step's names, 2026-11-17) → closed 1/5/15-minute frames → the cross
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
    s0 = None if stub else BLD.session_of(now)[0]
    auto_known = ([] if stub else
                  [s for s in AUTO.current_symbols(cs, s0.isoformat()) if CO.fold(s) not in mk])
    rules_known = [] if stub else _rules_known(cs, s0, mk | {CO.fold(s) for s in auto_known})     # ✅ 2026-11-24
    out["n_names"] = len(manual) + len(auto_known) + len(rules_known)
    if not manual and (stub or (not auto_known and not rules_known and not RUN.in_window(now))):
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
            rules_res: dict = {"symbols": [], "reason": "stub"}
        else:
            auto_prior = None                                   # ✅ [C1] the 🤖 doc BEFORE the step (his × record)
            try:
                auto_prior = AUTO.read_doc(cs)
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch ✅: auto doc read failed: %s", type(exc).__name__)
            auto_res = {"symbols": auto_known, "reason": "error"}
            try:
                auto_res = AUTO.step(now, session, db=db, manual=manual, dry=dry)
            except Exception as exc:                            # noqa: BLE001 — the last entries stay served
                log.warning("gajjala watch 🤖: auto step failed: %s", type(exc).__name__)
            rules_res = {"symbols": rules_known, "reason": "error"}
            try:
                rules_res = RULES.step(now, session, db=db, manual=manual, dry=dry, auto_prior=auto_prior,
                                       aplus=auto_res.get("aplus_now"))
            except Exception as exc:                            # noqa: BLE001 — the last entries stay served
                log.warning("gajjala watch ✅: rules step failed: %s", type(exc).__name__)
        auto_syms = [s for s in dict.fromkeys(auto_res.get("symbols") or []) if CO.fold(s) not in mk]
        ak = {CO.fold(s) for s in auto_syms}
        rules_syms = [s for s in dict.fromkeys(rules_res.get("symbols") or [])
                      if CO.fold(s) not in mk and CO.fold(s) not in ak]
        syms = manual + auto_syms + rules_syms                  # ✅ LAST — the minute budget falls on them first
        auto_out = {k: auto_res.get(k) for k in AUTO_OUT_KEYS}
        auto_out.update(n=len(auto_syms), cap=C.AUTO_MAX_SYMBOLS)
        out["auto"] = dict(auto_out, writes=auto_res["writes"]) if dry and "writes" in auto_res else auto_out
        rules_out = {k: rules_res.get(k) for k in C.RULES_OUT_KEYS}
        rules_out.update(n=len(rules_syms))
        out["rules"] = dict(rules_out, writes=rules_res["writes"]) if dry and "writes" in rules_res else rules_out
        out["n_names"] = len(syms)
        if not syms:
            out["reason"] = NO_TICKERS
            if not dry:
                _state(cs, C.STATE_LATEST_ID, {"at": now, "n_names": 0, "reason": NO_TICKERS, "auto": auto_out,
                                               "rules": rules_out})
            if not stub:                                        # 📅 2026-11-26 — no frame read: the whole minute budget
                _seat(cs, now, session, db=db, dry=dry, auto_prior=auto_prior,
                      left_sec=GC.GG1M_MINUTE_BUDGET_SEC if budget_sec is None else budget_sec, out=out)
                if not dry:                                     # 🩳 2026-11-27 — after the seat, its OWN try
                    _si_entry(cs, session, syms)
            return out
        tiles = cs["tiles"] if cs else None
        seen = BLD.seen(tiles, syms)
        per_name: dict = {}
        stats: dict = {}
        budget = GC.GG1M_MINUTE_BUDGET_SEC if budget_sec is None else budget_sec
        w0 = RUN._utc(deps.wall())
        REST.open_read()                                        # 🔌 2026-11-23 — a new closed own breaker (never raises)
        F = BLD.frames(syms, session, now, load_day=deps.load_day, budget_sec=budget, stats=stats,
                       per_name=per_name)
        # fix 2026-11-15: freshness is judged on the clock AFTER the fetch — `now` plus the wall time the fetch took
        # (a host sleep mid-fetch makes the cross stale: never sent late). The tile docs keep `now`.
        now_x = now + max(timedelta(0), RUN._utc(deps.wall()) - w0)
        held: dict = {}
        auto_live = AUTO.push_mode() == C.AUTO_PUSH_MODES[1]
        rules_live = RULES.push_mode() == C.AUTO_PUSH_MODES[1]                          # ✅ [C3] its OWN switch
        rk = {CO.fold(s) for s in rules_syms} - ak
        hold_k = (set() if auto_live else ak) | (set() if rules_live else rk)
        F_push = {s: f for s, f in F.items() if CO.fold(s) not in hold_k}            # [C6] his names' frames only
        try:
            counts = XA.run(F_push, now_x, session, coll=(cs["alerts"] if cs else None), send=deps.send,
                            owner=deps.owner, dry=dry, seen=seen, held=held)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala watch: cross push failed: %s", type(exc).__name__)
            counts = {"error": 1}
        if hold_k:
            try:
                counts[C.AUTO_HELD_REASON] = AUTO.hold_crosses({s: f for s, f in F.items() if CO.fold(s) in hold_k},
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
        # 🔌 2026-11-23 (spec ggconn §3.4 [C3]) — everything new sits in THIS one fence, after the cross push and every
        # tile write. The re-read (C.REST_REREAD_ON, built OFF = HIS CALL) keeps the iteration's own `now`; `now_x2`
        # is the clock AFTER the re-read. `counts` (alerts) is never rewritten — the re-read's counts go under rest.alerts.
        n_read, rest_out = len(F), None
        try:
            failed = REST.failed_names(per_name, syms)
            if failed:
                plan = REST.retry_plan(failed, budget_sec=budget,
                                       elapsed_sec=(RUN._utc(deps.wall()) - w0).total_seconds())
                rest_out = REST.summary(len(failed), plan)
                if plan.names:
                    deps.sleep(plan.wait)
                    REST.open_read()
                    pn2: dict = {}
                    st2: dict = {}
                    F2 = BLD.frames(list(plan.names), session, now, load_day=deps.load_day, budget_sec=plan.left,
                                    stats=st2, per_name=pn2)            # the SAME `now` — never deps.wall()
                    changed = REST.merge(per_name, stats, pn2, st2, plan.names)
                    rest_out["recovered"] = len(F2)
                    now_x2 = now + max(timedelta(0), RUN._utc(deps.wall()) - w0)   # the clock AFTER the re-read
                    if F2:
                        try:
                            c2 = XA.run({s: f for s, f in F2.items() if CO.fold(s) not in hold_k}, now_x2,
                                        session, coll=(cs["alerts"] if cs else None), send=deps.send,
                                        owner=deps.owner, dry=dry, seen=seen, held=held)
                        except Exception as exc:                # noqa: BLE001
                            log.warning("gajjala watch: cross push (re-read) failed: %s", type(exc).__name__)
                            c2 = {"error": 1}
                        if hold_k:
                            try:
                                c2[C.AUTO_HELD_REASON] = AUTO.hold_crosses(
                                    {s: f for s, f in F2.items() if CO.fold(s) in hold_k}, now_x2, session, held)
                            except Exception as exc:            # noqa: BLE001
                                log.warning("gajjala watch 🤖: auto hold (re-read) failed: %s", type(exc).__name__)
                        rest_out["alerts"] = c2
                        rest_out["pushed"] = int(c2.get(XA.PUSHED) or 0)
                    part = []
                    for sym in changed:                         # loaded, or failed → no_bars
                        try:
                            u = BLD.tile_update(sym, F2.get(sym), session, now, BLD.status_of(per_name.get(sym, {})),
                                                held.get(sym, {}))
                        except Exception as exc:                # noqa: BLE001 — the first pass's `failed` write stands
                            log.warning("gajjala watch: tile %s (re-read) failed: %s", sym, type(exc).__name__)
                            continue
                        part.append(u)
                        updates[syms.index(sym)] = u            # --dry-run's `writes` stays one per name
                    if part and not dry:
                        BLD.write(tiles, part)
                    n_read += len(F2)
        except Exception as exc:                                # noqa: BLE001 — the minute keeps its tiles and state doc
            log.warning("gajjala watch: REST re-read failed: %s", type(exc).__name__)
            rest_out = dict(rest_out or {}, error=type(exc).__name__)
        out.update(ran=True, session=session.isoformat(), n_read=n_read, bars=stats, alerts=counts,
                   wall_s=round(time.monotonic() - t0, 3))
        if rest_out is not None:
            out["rest"] = rest_out
        if not dry:
            _state(cs, C.STATE_LATEST_ID, {"at": now, "session": session.isoformat(), "n_names": len(syms),
                                           "n_read": n_read, "bars": stats, "alerts": counts,
                                           "wall_s": out["wall_s"], "reason": None, "auto": auto_out,
                                           "rules": rules_out})
            REST.count(cs["state"] if cs else None, session, now, n_names=len(syms), rest=rest_out)
        if not stub:                                            # 📅 2026-11-26 — LAST, on what is left of the minute
            _seat(cs, now, session, db=db, dry=dry, auto_prior=auto_prior,
                  left_sec=max(0.0, budget - (RUN._utc(deps.wall()) - w0).total_seconds()), out=out)
        if not dry and not stub:                                # 🩳 2026-11-27 — LAST, after the seat, its OWN try
            _si_entry(cs, session, syms)
        if rest_out is not None:
            log.info("gajjala watch: REST — %d failed, %d re-read after %.1f s, %d recovered, %d rang (%s)",
                     int(rest_out.get("failed") or 0), int(rest_out.get("retried") or 0),
                     float(rest_out.get("wait_s") or 0.0), int(rest_out.get("recovered") or 0),
                     int(rest_out.get("pushed") or 0), rest_out.get("error") or rest_out.get("skip"))
        return out
    finally:
        if lst is not None and claim is not None:
            try:
                lst.release_lease(now, getattr(claim, "token", None))
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch: lease release failed: %s", type(exc).__name__)


def _seat(cs, now, session, *, db, dry, auto_prior, left_sec, out) -> None:
    """📅 2026-11-26 (spec watchrun §3.3 [C8]) — the runners seat step, in its OWN try, at the END of the iteration (after
    the frames, the cross push, every tile write and the `latest` state write — that doc's keys and `wall_s` are
    untouched): runseat.step on `left_sec` (what is left of the minute budget, never negative) → out["runners"] and, when
    not dry, the state doc C.RUNNERS_STATE_ID. A raise leaves the iteration's answer intact."""
    try:
        t0 = time.monotonic()
        res = RUNSEAT.step(now, session, db=db, dry=dry, auto_prior=auto_prior, budget_sec=max(0.0, float(left_sec)))
        block = {k: res.get(k) for k in C.RUNNERS_SEAT_OUT_KEYS}
        out["runners"] = dict(block, writes=res["writes"]) if dry and "writes" in res else block
        if not dry:
            _state(cs, C.RUNNERS_STATE_ID, {"at": now, "session": session.isoformat(),
                                            "wall_s": round(time.monotonic() - t0, 3), **block})
    except Exception as exc:                                    # noqa: BLE001 — the minute keeps its answer
        log.warning("gajjala watch 📅: runners step failed: %s", type(exc).__name__)


def _si_entry(cs, session, syms) -> None:
    """🩳 2026-11-27 (Ajay "Anytime something is in our Gajjalas we need to initiate a flow checking these values"; SPEC
    sicheck §3.5) — the on-entry SI source check queue, in its OWN try, at the END of the iteration (after `_seat`):
    his + 🤖 auto + ✅ all-rules names (`syms`) + the 📅 runner seats → short_interest.entry_check.enqueue under the 👀
    source (imported lazily HERE; the row's `_id` dedupes per session). Never a dry run, never the stub (the caller's
    rule). No key of `out`, no state doc key; a raise leaves the iteration's answer intact."""
    try:
        from short_interest import entry_check as EC         # the plain import, lazily inside the try
        EC.enqueue(syms + RUNSEAT.current_symbols(cs, session), session.isoformat(), EC.SRC_WATCH)
    except Exception as exc:                                    # noqa: BLE001 — the minute keeps its answer
        log.warning("gajjala watch 🩳: si entry queue failed: %s", type(exc).__name__)


def _rules_known(cs, session, taken: set) -> list:
    """✅ the names the rules doc serves now (allrules.current_symbols — [] on a fault), minus `taken` folds. Never
    raises."""
    try:
        return [s for s in RULES.current_symbols(cs, session) if CO.fold(s) not in taken]
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch ✅: rules names unreadable: %s", type(exc).__name__)
        return []


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
def _new_only_todo(syms: list, docs: dict, added: dict, tried: set) -> list:
    """--new-only (2026-11-19): a listed name not yet tried with NO tile doc, or with an add time (the list doc's
    `added`, CO.added_of) LATER than its tile doc's last write `at` (CO.stamp_utc; an unreadable `at` counts as never
    written). An undated name with a doc, or a doc written at/after the add (a loaded, no_prints, failed or
    over_budget write alike), is never fetched. List order."""
    out: list = []
    for s in syms:
        if s in tried:
            continue
        if s not in docs:
            out.append(s)
            continue
        t_add = added.get(CO.fold(s)) if isinstance(added, dict) else None
        if t_add is None:
            continue                                            # undated (listed before 2026-11-19) → the minute loop
        t_doc = CO.stamp_utc(docs[s].get("at") if isinstance(docs[s], dict) else None)
        if t_doc is None or t_add > t_doc:
            out.append(s)
    return out


def build_pending(now: Optional[datetime] = None, *, db=None, deps: Optional[Deps] = None,
                  new_only: bool = False, tried: Optional[set] = None) -> dict:
    """[C2.5] Build every LISTED name whose tile is missing, from another session, or not loaded — the session of
    `now` (a closed day / before 04:00 → the last market session). Re-reads the list after each round (a name added
    meanwhile is picked up); each name is tried once per child. No cross push, no state doc, no lease.
    `new_only` (2026-11-19, the in-window add-time child `--new-only`): only `_new_only_todo` names — no tile doc, or
    added after the tile doc's last write. Cost: 1–2 Massive minute calls per added name: today (forced, bars.py:287) +
    the prior day when the 1-minute cache misses (bars.py:283 — a brand-new name always misses); single-flight. The
    default path never reads `added`.
    2026-11-23 [C1]: `tried` = the CALLER's set, shared across calls (main's `--build` loop) and filled in place — a
    name is tried once per child however many rounds run; None = a fresh set (byte-identical to before). The default
    path also rebuilds a listed doc lacking ANY tf of C.FRAMES (an old 1m/3m/5m doc has no 15m); `--new-only` never."""
    deps = deps or Deps()
    now = RUN._utc(now) if now is not None else RUN._utc(deps.wall())
    if not CO.enabled():                                        # off → no minute fetch from the build child either
        return {"session": None, "built": [], "rounds": 0, "reason": "off"}
    session = BLD.session_of(now)[0]
    iso = session.isoformat()
    cs = CO.colls(db)
    tiles = cs["tiles"] if cs else None
    tried = tried if tried is not None else set()
    out: dict = {"session": iso, "built": [], "rounds": 0}
    while True:
        if new_only:
            ldoc = CO.owner_doc(db)
            syms = CO.symbols_of(ldoc)
            added = CO.added_of(ldoc)
            proj = {"session": 1, "status": 1, "at": 1}
        else:
            syms = CO.owner_symbols(db)
            added, proj = {}, {"session": 1, "status": 1}
            proj.update({f"frames.{tf}.tf": 1 for tf, _r in C.FRAMES})        # 2026-11-23: a doc lacking a tf → todo
        docs: dict = {}
        if tiles is not None and syms:
            try:
                docs = {d["_id"]: d for d in tiles.find({"_id": {"$in": list(syms)}}, proj)
                        if isinstance(d, dict)}
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch build: tile read failed: %s", type(exc).__name__)
        if new_only:
            todo = _new_only_todo(syms, docs, added, tried)
        else:
            todo = [s for s in syms if s not in tried
                    and (s not in docs or docs[s].get("session") != iso or docs[s].get("status") != "loaded"
                         or _lacks_frame(docs[s]))]
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


def _lacks_frame(doc) -> bool:
    """2026-11-23: a tile doc that does not hold EVERY tf of C.FRAMES (an old 1m/3m/5m doc has no 15m)."""
    fr = doc.get("frames") if isinstance(doc, dict) else None
    return not isinstance(fr, dict) or any(not isinstance(fr.get(tf), dict) for tf, _r in C.FRAMES)


# ── 📐 the daily zones hook (2026-11-23, spec vwapzones §3.5) ─────────────────────────────────────────────────────────
def _levels(now: Optional[datetime], *, thread: bool = False, first: Optional[list] = None, rest: bool = True) -> int:
    """The levels module (C.LEVELS_MODULE, imported LAZILY — loop.py never imports payload): `thread` → `.spawn(now)`
    (the daemon thread of the `--loop` child) → 0; else the number of daily reads `.warm(now, first=, rest=)` made
    (0 = it waited on nothing). 0 when C.ZONES_ON is off, on no store, and on ANY fault (one log line, nothing else
    changes). Never called on `--dry-run`."""
    if not C.ZONES_ON:
        return 0
    try:
        mod = importlib.import_module(C.LEVELS_MODULE)
        if thread:
            mod.spawn(now)
            return 0
        res = mod.warm(now, first=list(first or []), rest=bool(rest))
        read = res.get("read") if isinstance(res, dict) else None
        return len(read) if isinstance(read, (list, tuple)) else 0
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch: daily zones unavailable: %s", type(exc).__name__)
        return 0


def build_all(now: Optional[datetime] = None, *, new_only: bool = False) -> dict:
    """[C1] The `--build` child: `build_pending` → `_levels(first=built)` rounds with ONE shared `tried`, ending when a
    round built nothing AND read nothing — so the list re-read (`build_pending`) is the child's LAST act and a name added
    while the zones were read is built by this child. `rest` (round 0 only, never `--new-only`) also reads listed names
    still lacking this session's zones, inside the levels module's cap. Nothing to build and nothing to read → ONE
    `build_pending` call, as before."""
    tried: set = set()
    built_all: list = []
    rounds = 0
    out: dict = {}
    while True:
        out = build_pending(now, new_only=new_only, tried=tried)
        built = list(out.get("built") or [])
        built_all += built
        rest = rounds == 0 and not new_only
        # nothing built and no rest pass → the zones read would read nothing: skipped, so the list re-read stays LAST
        n = _levels(now, first=built, rest=rest) if (built or rest) else 0
        rounds += 1
        if not built and not n:
            break
    out["built"] = built_all
    return out


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chart_maps.gajjala_watch.loop", description=__doc__.split("\n")[0])
    ap.add_argument("--loop", action="store_true", help="the slot's iterations (run.main spawns this, detached)")
    ap.add_argument("--build", action="store_true", help="build every pending listed name (the API spawns this)")
    ap.add_argument("--new-only", action="store_true",
                    help="with --build: only names with no tile doc or added after its last write (2026-11-19)")
    ap.add_argument("--dry-run", action="store_true", help="one iteration; record every write and send; touch nothing")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    ap.add_argument("--now", help="ISO clock to replay (a naive stamp is ET) — --dry-run only")
    ap.add_argument("--symbols", help="comma list REPLACING the owner list for this run — --dry-run only")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    try:                                                        # 🔌 2026-11-23 — the key scrub on every log line
        from observability.logsetup import install_redaction
        install_redaction()
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch: log redaction unavailable: %s", type(exc).__name__)
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
        out = build_all(now, new_only=args.new_only)          # [C1] 2026-11-23 — the list re-read stays the LAST act
    else:
        if not CO.enabled():
            log.info("gajjala watch: off (%s) — nothing to do", C.ENV_ENABLED)
            return 0
        if not RUN.in_window(RUN._utc(now)):
            log.info("gajjala watch: outside %s–%s ET on a market day — nothing to do", GC.PASS_OPEN_ET,
                     GC.PASS_CLOSE_ET)
            return 0
        if args.loop:
            _levels(now, thread=True)                           # 📐 2026-11-23 — off the minute path (a daemon thread)
            out = loop(now)
        else:
            out = run_iteration(now)
    if args.json:
        print(json.dumps(out, default=str))
    elif not args.loop:
        log.info("gajjala watch: %s", {k: out.get(k) for k in ("ran", "reason", "n_names", "n_read", "bars", "alerts",
                                                              "built", "wall_s")})
    return 0


__all__ = ["Deps", "dry_deps", "lease_store", "run_iteration", "loop", "build_pending", "build_all", "main", "LEASE_HELD",
           "LOOP_REASONS", "NO_TICKERS"]


if __name__ == "__main__":
    sys.exit(main())
