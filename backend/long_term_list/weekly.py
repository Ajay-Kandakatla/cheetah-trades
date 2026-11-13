"""📅 Long Term — the weekly re-read (spec §3.9, WP-RUN).

Ajay 2026-11-12, verbatim: "Save this entire list for me. In a New tab - Long Term - Remember this analays criteria I
am asking you to for this tab and keep updating it from all the other tabs info.. Weekly and if something gets dropped
let me know when to like is Sales drop or Stage 2 to Stage 3 or stage 4 changes."

WHEN: `sepa.context_refresh.after_scan` (the 16:30 ET `fast-scan` cron job — no crontab line of its own) calls
`spawn_after_scan(kind)`. On the LAST trading day of the ISO week, at/after `constants.RUN_AFTER_ET` (the SEPA re-rate),
it starts `python -m long_term_list.weekly --after-scan KIND` DETACHED (`chart_maps.gajjala.run_1m._popen`, the one
spawn engine) so the 24 MB scan and the 📉 build never sit in the scan process. The eligibility read touches no Mongo.

WHAT `run()` does, once per ISO week (the `run:<week>` claim is the dedupe):
  seed + baseline + prior runs → previous flags (the latest run, else the baseline) → `sources.load_all` (every other
  tab's own engine, cache-only) → `facts.build` → each screened list's "this week's top" strip (UNSAVED: the saved set
  is the seed, always) → every saved name's legs, 🧭 zone read and notices → the digest → the forward record (the base
  doc frozen ONCE, then one point per ISO week, missing weeks backfilled) → INSERT the run doc → INSERT the points →
  `push.send_digest` (today: "push off") → the claim marked done.
Run docs and forward docs are INSERT ONLY — nothing here updates, replaces or deletes them. `dry_run` claims, writes
and pushes nothing. Never raises: an exception marks the claim failed and returns {"ran": False, "reason"}.

UNMEASURED — a list kept up to date, not a signal.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import math
import os
import sys
import time
from datetime import date, datetime, time as dtime, timedelta
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from . import constants as C
from . import store as ST

log = logging.getLogger("long_term_list.weekly")
ET = ZoneInfo("America/New_York")

R_OFF = f"off ({C.ENV_SWITCH}=0)"
R_OVERRIDE = "calendar override active (CHEETAH_IGNORE_HOLIDAY) — use --run-now"
R_NOT_LAST = "not the last trading day of the week"
R_ALREADY = "already ran this week"
R_NO_STORE = "store unreachable — not run"


# ── clock + calendar ────────────────────────────────────────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(ET)


def _et(now: Optional[datetime]) -> datetime:
    n = now if now is not None else _now()
    if n.tzinfo is None:
        return n.replace(tzinfo=ET)                            # a naive clock is ET (the house rule)
    return n.astimezone(ET)


def _run_after() -> dtime:
    hh, mm = (int(x) for x in str(C.RUN_AFTER_ET).split(":"))
    return dtime(hh, mm)


def _run_after_text() -> str:
    t = _run_after()
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'} ET"


def _closed(d: date) -> Optional[str]:
    """market_hours.gate.closed_reason at NOON ET of `d` (zoneinfo clock, never the gate's fixed −4)."""
    from market_hours.gate import closed_reason
    return closed_reason(datetime.combine(d, dtime(12, 0), tzinfo=ET))


def is_open(d) -> bool:
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return _closed(d) is None


def is_last_trading_day(d) -> bool:
    """`d` is open and every later day of its ISO week is closed."""
    if isinstance(d, datetime):
        d = d.date()
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    if not is_open(d):
        return False
    nxt = d + timedelta(days=1)
    while nxt.isocalendar()[1] == d.isocalendar()[1]:
        if is_open(nxt):
            return False
        nxt += timedelta(days=1)
    return True


def eligible(now: Optional[datetime] = None, *, force: bool = False) -> Optional[str]:
    """None when a weekly run may start now, else why not. The env switch wins always; `force` (the manual
    `--run-now` / the probe) skips the calendar and the clock; the calendar override is refused unforced."""
    if os.environ.get(C.ENV_SWITCH, "").strip() == "0":
        return R_OFF
    if force:
        return None
    from market_hours.gate import override_active
    if override_active():
        return R_OVERRIDE
    et = _et(now)
    why = _closed(et.date())
    if why:
        return why
    if not is_last_trading_day(et.date()):
        return R_NOT_LAST
    if et.time() < _run_after():
        return f"before {_run_after_text()}"
    return None


def session_for(now: Optional[datetime] = None) -> str:
    """The closed session a run reads: today once open and past RUN_AFTER_ET, else the last open day before."""
    et = _et(now)
    d = et.date()
    if is_open(d) and et.time() >= _run_after():
        return d.isoformat()
    for _ in range(14):
        d -= timedelta(days=1)
        if is_open(d):
            return d.isoformat()
    return d.isoformat()


# ── the spawn (the cron path) ───────────────────────────────────────────────────────────────────────────────────
def child_argv(kind: str) -> list:
    return [sys.executable, "-m", C.CHILD_ARGV_MODULE, "--after-scan", str(kind)]


def spawn_after_scan(kind: str, spawn: Optional[Callable] = None) -> bool:
    """Start the weekly child DETACHED when eligible. True when started; never raises. With no injected `spawn`, a
    pytest run never starts a real process (the bar_close.spawn_child guard)."""
    try:
        why = eligible(_now())
        if why:
            log.debug("long-term list weekly: not spawned after %s (%s)", kind, why)
            return False
        if spawn is None and os.environ.get("PYTEST_CURRENT_TEST"):
            log.debug("long-term list weekly: not spawned under pytest")
            return False
        if spawn is None:
            from chart_maps.gajjala import run_1m as R1
            spawn = R1._popen
        proc = spawn(child_argv(kind), C.CHILD_NAME)
        log.debug("long-term list weekly: %s pid %s", C.CHILD_NAME, getattr(proc, "pid", None))
        return True
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long-term list weekly: spawn raised %s", type(exc).__name__)
        return False


# ── plain values for Mongo / JSON ──────────────────────────────────────────────────────────────────────────────
def _plain(o):
    if dataclasses.is_dataclass(o) and not isinstance(o, type):
        return _plain(dataclasses.asdict(o))
    if isinstance(o, dict):
        return {str(k): _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set, frozenset)):
        return [_plain(v) for v in o]
    if isinstance(o, bool) or o is None or isinstance(o, str):
        return o
    if isinstance(o, int):
        return int(o)
    if isinstance(o, float):
        return None if (o != o or math.isinf(o)) else float(o)
    try:                                                       # numpy / pandas scalars
        import numpy as np
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            f = float(o)
            return None if (f != f or math.isinf(f)) else f
    except Exception:                                          # noqa: BLE001
        pass
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    return str(o)


# ── injectable reads (tests replace these; production reads every other tab's own engine, cache-only) ──────────
def _load_sources(now: datetime, saved: list, seed: dict) -> dict:
    from . import sources as SRC
    return SRC.load_all(now, saved=set(saved), seed=seed)


def _build_facts(src: dict, saved: list, seed: dict) -> dict:
    from . import facts as FACTS
    return FACTS.build(src, saved, seed)


def _pool_frames(now: datetime) -> dict:
    """The forward placebo pool: every `load_universe(ACCEL_UNIVERSE)` name's cached frame (ONE find, never a
    fetch), cut to closed bars by the same rule as every other bar read."""
    from sepa import prices
    from sepa.universe import load_universe
    from . import sources as SRC
    syms = sorted({str(s).upper() for s in (load_universe(C.ACCEL_UNIVERSE) or []) if s})
    frames = prices.bulk_cached_frames(syms) or {}
    out = {}
    for s, df in frames.items():
        d = SRC.closed_frame(df, now)
        if d is not None:
            out[str(s).upper()] = d
    return out


# ── the run ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _prev_top(prior: list, cat: str, seed: dict) -> set:
    """Last week's strip for `cat`: the newest prior run that READ that list; week 1 → the seed's own names."""
    from . import seed as SEED
    for r in prior:
        if (r.get("top_read") or {}).get(cat):
            return {str(t.get("symbol")) for t in (r.get("top") or {}).get(cat) or []}
    return set(SEED.category_names(seed, cat))


def _strips(facts: dict, saved: list, prior: list, seed: dict) -> tuple:
    """({cat: [{symbol, name, sector, rank_text, new}]}, {cat: read?}, {cat: [new symbols]}). UNSAVED — a strip name
    never becomes a saved row."""
    from . import criteria as CR
    from . import words as W
    top, read, new = {}, {}, {}
    cats = facts.get("categories") or {}
    names = facts.get("names") or {}
    for cat in C.SCREENED_KEYS:
        cf = cats.get(cat) or {}
        read[cat] = bool(cf.get("ok"))
        pop = list(cf.get("population") or [])
        by_sym = {str(c.get("symbol")).upper(): c for c in pop if c.get("symbol")}
        picks = CR.pick_top(cat, pop, saved=frozenset(saved))
        before = _prev_top(prior, cat, seed)
        rows = []
        for s in picks:
            c = by_sym.get(s) or {}
            rows.append({"symbol": s, "name": (names.get(s) or {}).get("name"), "sector": c.get("sector"),
                         "rank_text": W.rank_text(cat, c.get("values") or {}), "new": s not in before})
        top[cat] = rows
        new[cat] = [r["symbol"] for r in rows if r["new"]]
    return top, read, new


def _names_and_events(facts: dict, seed: dict, baseline: dict, prev: Optional[dict], session: str) -> tuple:
    from . import criteria as CR
    from . import notices as N
    from . import seed as SEED
    chips = SEED.chips(seed)
    pk = SEED.pankaj_entries(seed)
    order = SEED.zone_order(seed)
    cats = facts.get("categories") or {}
    fnames = facts.get("names") or {}
    prev_names = (prev or {}).get("names") or {}
    base_flags = baseline.get("flags") or {}
    out, events = {}, []
    for sym in SEED.unique_names(seed):
        fn = fnames.get(sym) or {}
        legs, qual = {}, {}
        for cat in chips.get(sym) or []:
            if cat == C.PANKAJ_KEY:
                continue
            cand = ((cats.get(cat) or {}).get("lookup") or {}).get(sym) or {}
            vals = cand.get("values")
            legs[cat] = [lg.to_dict() for lg in CR.legs(cat, vals)]
            qual[cat] = CR.qualifies(cat, vals)
        zr = None
        if sym in pk:
            pv = ((((cats.get(C.PANKAJ_KEY) or {}).get("lookup") or {}).get(sym) or {}).get("values") or {})
            zr = CR.zone_read(pk[sym]["zones"], pv.get("close"), pv.get("close_date"), order)
        pn = prev_names.get(sym) or {}
        now_in = list(fn.get("in") or [])
        absent = [k for k in (pn.get("in") or []) if k not in now_in]
        now = {"stage": fn.get("stage"), "stage_label": fn.get("stage_label"), "sales_tier": fn.get("sales_tier"),
               "sales_yoy_pct": fn.get("sales_yoy_pct"), "sales_q_end": fn.get("sales_q_end"),
               "legs": legs, "zone_read": zr, "absent": absent}
        flags_prev = pn.get("flags") if pn else base_flags.get(sym)
        prev_legs = pn.get("legs") if pn else None
        evs, flags = N.detect(sym, chips.get(sym) or [], flags_prev, prev_legs, now, N.at_save(sym, baseline),
                              session)
        events.extend(evs)
        out[sym] = {"symbol": sym, "name": fn.get("name"), "sector": fn.get("sector"),
                    "stage": fn.get("stage"), "stage_label": fn.get("stage_label"),
                    "stage_bar_date": fn.get("stage_bar_date"), "close": fn.get("close"),
                    "close_date": fn.get("close_date"), "sales_tier": fn.get("sales_tier"),
                    "sales_yoy_pct": fn.get("sales_yoy_pct"), "sales_q_end": fn.get("sales_q_end"),
                    "sales_read_on": fn.get("sales_read_on"), "in": now_in, "legs": legs, "qualifies": qual,
                    "zone_read": zr, "flags": flags}
    return out, events


def _weeks_between(first: str, last: str) -> list:
    """[(iso week, its last trading day ≤ last)] from `first`'s week through `last`'s week."""
    from . import forward as FW
    d = date.fromisoformat(first[:10])
    end = date.fromisoformat(last[:10])
    d -= timedelta(days=d.weekday())
    out = []
    while d <= end:
        ltd = FW.last_trading_day_of_week(d, is_open)
        if ltd:
            at = min(ltd, last)
            if at >= first:
                out.append((ST.iso_week_id(d), at))
        d += timedelta(days=7)
    return out


def _forward(src: dict, seed: dict, fwd_docs: list, session: str, week: str, now: datetime,
             pool_loader: Callable) -> tuple:
    """(new base doc | None, [new point docs], pool read seconds | None). Pure apart from `pool_loader`."""
    from . import forward as FW
    from . import seed as SEED
    fr = src.get("frames") if isinstance(src.get("frames"), dict) else {}
    frames = (fr.get("frames") or {}) if fr.get("ok") else {}
    base = next((d for d in fwd_docs if d.get("_id") == ST.BASE_ID), None)
    pool, pool_s = None, None

    def _pool():
        nonlocal pool, pool_s
        if pool is None:
            t = time.time()
            try:
                pool = pool_loader(now) or {}
            except Exception as exc:                           # noqa: BLE001
                log.warning("long-term list weekly: pool frames unreadable: %s", exc)
                pool = {}
            pool_s = round(time.time() - t, 2)
        return pool

    new_base = None
    base_sess = FW.base_session(C.SAVED_ON, is_open)
    if base is None and session >= base_sess and FW.freeze_base([C.BENCHMARK], frames, base_sess)["prices"]:
        b = FW.freeze_base(SEED.unique_names(seed), frames, base_sess)
        pb = FW.freeze_base(sorted(_pool()), _pool(), base_sess)
        new_base = {"_id": ST.BASE_ID, **b, "pool_prices": pb["prices"], "pool_no_base": pb["no_base"],
                    "frozen_at_iso": now.isoformat(timespec="seconds")}
        base = new_base
    if base is None:
        return None, [], pool_s
    have = {d.get("_id") for d in fwd_docs if d.get("_id") != ST.BASE_ID}
    stored = sorted((d for d in fwd_docs if d.get("_id") not in (ST.BASE_ID, None)), key=lambda d: d["_id"])
    headline = SEED.screened_names(seed)
    groups = {cat: SEED.category_names(seed, cat) for cat in C.CATEGORY_KEYS}
    points = []
    for wk, at in _weeks_between(base["session"], session):
        prior = [d for d in stored if d["_id"] < wk] + [p for p in points if p["_id"] < wk]
        if wk in have:
            continue
        carried = {}
        if prior:
            last = sorted(prior, key=lambda d: d["_id"])[-1]
            carried = {s: v.get("price") for s, v in (last.get("per_symbol") or {}).items() if isinstance(v, dict)}
        p = FW.point(base, frames, at, carried, headline=headline, groups=groups)
        bench = FW.bench(frames, base["session"], at)
        st = FW.stats(p, FW.pool_pcts(base.get("pool_prices"), _pool(), at), headline=headline)
        points.append({"_id": wk, "iso_week": wk, **p, **bench,
                       "n_sessions": FW.sessions_between(frames.get(C.BENCHMARK), base["session"], at),
                       "ci": st["ci"], "placebo": st["placebo"], "backfilled": wk != week,
                       "built_at_iso": now.isoformat(timespec="seconds")})
    return new_base, points, pool_s


def _build(now: datetime, session: str, week: str, cs: Optional[dict], sources: Optional[dict], trigger: str,
           pool_loader: Callable) -> dict:
    from . import notices as N
    from . import seed as SEED
    t0 = time.time()
    seed = SEED.load()
    baseline = SEED.load_baseline()
    prior = [r for r in ST.runs_desc(cs["runs"] if cs else None) if r["_id"] < week]
    prev = prior[0] if prior else None
    saved = SEED.unique_names(seed)
    t = time.time()
    src = sources if sources is not None else _load_sources(now, saved, seed)
    sources_s = round(time.time() - t, 2)
    facts = _build_facts(src, saved, seed)
    top, top_read, top_new = _strips(facts, saved, prior, seed)
    names, events = _names_and_events(facts, seed, baseline, prev, session)
    events.sort(key=lambda e: (N.KIND_ORDER.index(e["kind"]) if e["kind"] in N.KIND_ORDER else 99, e["symbol"]))
    digest = N.digest(events, top_new, session)
    fwd_docs = ST.forward_docs(cs["forward"] if cs else None)
    new_base, points, pool_s = _forward(src, seed, fwd_docs, session, week, now, pool_loader)
    doc = {"_id": week, "iso_week": week, "session": session, "trigger": trigger,
           "built_at": time.time(), "built_at_iso": now.isoformat(timespec="seconds"),
           "duration_s": round(time.time() - t0, 2),
           "timings": {"sources_s": sources_s, "source_load_s": (src or {}).get("duration_s"), "pool_s": pool_s},
           "sources": facts.get("sources") or {}, "names": names, "top": top, "top_read": top_read,
           "events": events, "digest": digest,
           "constants": {k: getattr(C, k) for k in C.CONSTANT_SOURCES if hasattr(C, k)}}
    return {"run": _plain(doc), "base": _plain(new_base) if new_base else None, "points": _plain(points)}


def run(now=None, *, sources=None, db=None, send=None, dry_run=False, force=False, trigger="manual",
        pool_loader: Optional[Callable] = None) -> dict:
    """One weekly re-read. Never raises. {"ran", "reason", "week", ...}; dry_run also returns the docs it would
    insert (and inserts, claims, pushes nothing)."""
    et = _et(now)
    try:
        why = eligible(et, force=force)
    except Exception as exc:                                   # noqa: BLE001
        why = f"eligibility unreadable: {type(exc).__name__}"
    if why:
        log.info("long-term list weekly: not run — %s", why)
        return {"ran": False, "reason": why}
    session = session_for(et)
    week = ST.iso_week_id(session)
    cs = ST.colls(db)
    cid = ST.RUN_CLAIM + week
    claims = cs["claims"] if cs else None
    if not dry_run:
        got = ST.claim(claims, cid, et.isoformat(timespec="seconds"), trigger=trigger, session=session)
        if got is None:
            return {"ran": False, "reason": R_NO_STORE, "week": week}
        if not got:
            log.info("long-term list weekly: %s (%s)", R_ALREADY, week)
            return {"ran": False, "reason": f"{R_ALREADY} ({week})", "week": week}
    try:
        built = _build(et, session, week, cs, sources, trigger, pool_loader or _pool_frames)
        doc = built["run"]
        if dry_run:
            return {"ran": True, "dry_run": True, "week": week, "session": session, "run": doc,
                    "base": built["base"], "points": built["points"]}
        if built["base"] is not None:
            ST.insert_forward(cs["forward"], built["base"])
        stored = ST.insert_run(cs["runs"], doc)
        if stored is not True:
            reason = f"{R_ALREADY} ({week})" if stored is False else R_NO_STORE
            ST.set_claim(claims, cid, "failed" if stored is None else "done", reason=reason)
            return {"ran": False, "reason": reason, "week": week}
        n_points = sum(1 for p in built["points"] if ST.insert_forward(cs["forward"], p) is True)
        from . import push as PUSH
        pushed = PUSH.send_digest(doc, et, db=db, send=send)
        ST.set_claim(claims, cid, "done", push=pushed, n_points=n_points,
                     finished_at=_et(None).isoformat(timespec="seconds"))
        log.info("long-term list weekly: %s stored — %s · push %s", week, doc["digest"].get("title"),
                 pushed.get("reason") or pushed.get("state"))
        return {"ran": True, "week": week, "session": session, "n_events": len(doc["events"]),
                "n_points": n_points, "base_frozen": built["base"] is not None, "push": pushed,
                "digest": doc["digest"]}
    except Exception as exc:                                   # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"[:300]
        log.warning("long-term list weekly: %s failed — %s", week, reason)
        if not dry_run:
            ST.set_claim(claims, cid, "failed", reason=reason)
        return {"ran": False, "reason": reason, "week": week}


# ── CLI ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="long_term_list.weekly", description="📅 Long Term — the weekly re-read")
    ap.add_argument("--after-scan", metavar="KIND", help="the cron path (spawned by context_refresh.after_scan)")
    ap.add_argument("--run-now", action="store_true", help="manual recovery run (skips the calendar and the clock)")
    ap.add_argument("--dry-run", action="store_true", help="build the week, write and push nothing")
    ap.add_argument("--out", help="with --dry-run: write the result JSON here")
    ap.add_argument("--now", help="ISO clock to replay (a naive stamp is ET)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    now = datetime.fromisoformat(args.now) if args.now else None
    if args.dry_run:
        res = run(now, dry_run=True, force=True, trigger="dry_run")
        txt = json.dumps(_plain(res), allow_nan=False, default=str)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(txt)
        else:
            print(txt)
        return 0 if res.get("ran") else 1
    if args.run_now:
        res = run(now, force=True, trigger="run_now")
    elif args.after_scan:
        res = run(now, trigger=f"after_scan:{args.after_scan}")
    else:
        ap.print_help()
        return 2
    log.info("long-term list weekly: %s", {k: v for k, v in res.items() if k not in ("digest",)})
    return 0


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(main())
