"""Measure the 🛡️ Resiliency tab's cost and counts on the full universe. READ-ONLY.

The re-runnable measurement behind the numbers in
`docs/chart_maps/resiliency_tab_2026_09_30.md` — the doc quotes whatever this
prints. Run it in the api container against the BRANCH tree copied to /tmp
(nothing is copied into /app; see the spec §5):

    docker exec -w /tmp/resil -e PYTHONPATH=/tmp/resil cheetah-market-app-api-1 \\
        python scripts/resiliency_tab_cost_probe.py [--dump-fixture PATH]

READ-ONLY BY CONSTRUCTION: every pymongo write method is replaced, in this
process only, by a RECORDED NO-OP before anything connects (`create_index`
returns the index name, so the connection helpers still work — a raising
blocker would make `prices._get_mongo` disable Mongo for the whole run). The
attempted writes are printed (expected: `create_index` only).

It times the stages the tab runs: the memo build (ONE `bulk_cached_frames`
read + ONE `past_events` + ONE macro-calendar read + the closed half per
name), the pre-market baseline aggregation (ONE `intraday_cache` aggregate +
ONE find), ONE universe snapshot (the board's fan-out), and the per-request
rank for each of the four sorts. It prints the counts, the hand-check names
(a utility, a staple, NVDA, MU, SPY) with their event-day closes, and the
count identity `scanned == rated + partial + no_bars`.

`--dump-fixture PATH` calls the REAL `api.chart_maps` handler with explicit
arguments for five variants (default, sort=res_t2, res=t1,eod,
res=t1,eod&res_mode=all, sort=res_today) and writes each `JSONResponse.body`
(parsed) into one JSON file — the frontend payload test's fixture. A
JSONResponse that serialized proves the payload is NaN-free. Every payload
sits at the TOP LEVEL of the file (the FE test reads every top-level value
whose `tab` is "resiliency"); the capture keys start with "_". A ready-state
capture has no warming or error payload, so two more come through the same
handler with the memo FORCED (in this process only, restored after):
`warming_forced` (memo empty, the background build never started) and
`error_forced` (the build raises once, then the back-off serves the error).

Imports ONLY `chart_maps.resiliency_tab`, `chart_maps.board`,
`chart_maps.api` and `sepa.prices` (+ pymongo to block writes) — never the
key-levels engine directly (the display-only import guard scans scripts/).
Not a study of edge: a timing and a count, no placebo applies.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ET = ZoneInfo("America/New_York")
NAMED = ("DUK", "SO", "PG", "KO", "NVDA", "MU", "SPY")
HAND_DAYS = (("2026-09-11", "CPI"), ("2026-09-16", "FOMC decision"))
WRITE_METHODS = ("insert_one", "insert_many", "update_one", "update_many", "replace_one",
                 "delete_one", "delete_many", "find_one_and_update", "find_one_and_replace",
                 "find_one_and_delete", "bulk_write", "create_index", "create_indexes",
                 "drop", "drop_index", "drop_indexes", "rename")
ATTEMPTED: list = []
VARIANTS = (("default", {}), ("res_t2", {"sort": "res_t2"}),
            ("t1_eod_any", {"res": "t1,eod"}),
            ("t1_eod_all", {"res": "t1,eod", "res_mode": "all"}),
            ("res_today", {"sort": "res_today"}))


def block_writes() -> None:
    """Every pymongo write method -> a recorded no-op (this process only)."""
    from pymongo.collection import Collection

    def _make(name):
        def _noop(self, *a, **k):
            ATTEMPTED.append(f"{getattr(self, 'name', '?')}.{name}")
            if name == "create_index":
                return "blocked_index"
            return None
        return _noop
    for m in WRITE_METHODS:
        if hasattr(Collection, m):
            setattr(Collection, m, _make(m))


def _hand(entry: dict, frames: dict) -> dict:
    from chart_maps import resiliency_tab as R
    out = {}
    for s in NAMED:
        df = frames.get(s)
        rd = (entry.get("reads") or {}).get(s) or {}
        closes = R.closes_by_day(df) if df is not None else {}
        days = sorted(closes)
        hand = {}
        for d, lab in HAND_DAYS:
            if d in days and days.index(d) > 0:
                p = days[days.index(d) - 1]
                hand[d] = {"label": lab, "prev_day": p, "prev_close": closes[p],
                           "close": closes[d], "ret_pct": R.pct_ret(closes[d], closes[p])}
            else:
                hand[d] = None
        out[s] = {"t1": rd.get("t1"), "t2": rd.get("t2"), "sigma_pct": rd.get("sigma_pct"),
                  "beta": rd.get("beta"), "eod": rd.get("eod"), "hand": hand}
    return out


def dump_fixture(path: str, now: datetime) -> dict:
    from chart_maps import api
    variants = {}
    for name, kw in VARIANTS:
        args = {"tab": "resiliency", "limit": 80, "days": 130, "universe": "full",
                "min_tier": "ok", "sort": kw.get("sort", "default"),
                "res": kw.get("res", ""), "res_mode": kw.get("res_mode", "")}
        t0 = time.perf_counter()
        resp = asyncio.run(api.chart_maps(**args))
        body = json.loads(resp.body)
        variants[name] = {"args": args, "s": round(time.perf_counter() - t0, 2),
                          "payload": body}
    base = dict(variants["default"]["args"])
    for name in FORCED:
        t0 = time.perf_counter()
        variants[name] = {"args": dict(base, _forced=name), "payload": _forced(name, base),
                          "s": round(time.perf_counter() - t0, 2)}
    doc = {"_about": ("REAL capture: the api.chart_maps handler's JSONResponse bodies, "
                      "scripts/resiliency_tab_cost_probe.py --dump-fixture; "
                      + ", ".join(FORCED) + " = the same handler with the memo forced "
                      "into that state in the probe's process"),
           "_captured_at": now.isoformat(timespec="seconds"),
           "_args": {k: v["args"] for k, v in variants.items()}}
    doc.update({k: v["payload"] for k, v in variants.items()})
    Path(path).write_text(json.dumps(doc, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return {k: v["s"] for k, v in variants.items()}


FORCED = ("warming_forced", "error_forced")


def _forced(name: str, args: dict) -> dict:
    """The real handler's body with the resiliency memo forced into `name`'s
    state (this process only; the memo, the warm set, the failures, `build`
    and `_spawn` are restored afterwards)."""
    from chart_maps import api
    from chart_maps import resiliency_tab as R
    saved = (dict(R._memo), set(R._warming), dict(R._failed), R.build, R._spawn)
    try:
        R._memo.clear()
        R._warming.clear()
        R._failed.clear()
        if name == "warming_forced":
            R._spawn = lambda target, nm: None                 # the build never starts
            return json.loads(asyncio.run(api.chart_maps(**args)).body)

        def _raise(*a, **k):
            raise RuntimeError("forced by the probe for the fixture")
        R.build = _raise
        R._spawn = lambda target, nm: target()                 # the failing build runs inline
        asyncio.run(api.chart_maps(**args))                    # warming; the build fails
        return json.loads(asyncio.run(api.chart_maps(**args)).body)   # the back-off -> error
    finally:
        R._memo.clear()
        R._memo.update(saved[0])
        R._warming.clear()
        R._warming.update(saved[1])
        R._failed.clear()
        R._failed.update(saved[2])
        R.build, R._spawn = saved[3], saved[4]


def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(prog="python scripts/resiliency_tab_cost_probe.py")
    ap.add_argument("--dump-fixture", default=None, help="write the real payloads here")
    args = ap.parse_args(argv)
    block_writes()

    from chart_maps import board as B
    from chart_maps import resiliency_tab as R
    from sepa import prices

    now = datetime.now(ET)
    session = R.session_for(now)
    out = {"date": now.isoformat(timespec="seconds"), "session": session.isoformat()}

    t0 = time.perf_counter()
    got = R.cached_or_warm("full", now=now, sync=True)
    entry = got["entry"]
    out["s_build_cold"] = round(time.perf_counter() - t0, 2)
    out["n"] = len(entry["syms"])
    out["n_reads"] = len(entry["reads"])
    out["events_error"] = entry.get("events_error")
    out["events"] = entry.get("events_summary")
    out["session_events"] = entry.get("session_events")
    out["next_t1"] = entry.get("next_t1")

    t1 = time.perf_counter()
    pm = R.pm_cached_or_warm(entry["syms"], session, sync=True)
    out["s_pm_baseline"] = round(time.perf_counter() - t1, 2)
    by = pm.get("by_sym") or {}
    out["pm"] = {"state": pm.get("state"), "names": len(by),
                 "with_min_sessions": sum(1 for v in by.values()
                                          if v["sessions"] >= R.PM_BASELINE_MIN_SESSIONS)}

    t2 = time.perf_counter()
    raw = B._bulk_snaps_fanout(list(entry["syms"]) + [R.BENCH])
    out["s_snapshot_fanout"] = round(time.perf_counter() - t2, 2)
    out["n_snap"] = len(raw)
    spy = raw.get(R.BENCH) or {}
    out["spy_snapshot"] = {k: spy.get(k) for k in ("change_pct", "prev_day_close",
                                                   "last_trade_price", "min_av", "min_t_ms")}

    ranks = {}
    for srt in ("default",) + R.TAB_SORTS:
        t3 = time.perf_counter()
        rows, counts, filters, today, su = R.rank(entry, raw, pm, now=now, sort=srt)
        ranks[srt] = {"s": round(time.perf_counter() - t3, 3), "sort_unavailable": su,
                      "top": [r["symbol"] for r in rows[:15]]}
    out["ranks"] = ranks
    out["counts"] = counts
    out["today"] = today
    out["identity_scanned_eq_rated_partial_no_bars"] = (
        counts["scanned"] == counts["rated_t1"] + counts["partial_t1"] + counts["no_bars"])
    out["filters_pass"] = {i["key"]: i["pass"] for i in filters["items"]}

    frames = prices.bulk_cached_frames([s for s in NAMED])
    out["named"] = _hand(entry, frames)

    if args.dump_fixture:
        out["s_api_variants"] = dump_fixture(args.dump_fixture, now)
        out["fixture"] = args.dump_fixture
    out["attempted_writes"] = sorted(set(ATTEMPTED))
    print(json.dumps(out, default=str))
    return out


if __name__ == "__main__":
    main()
