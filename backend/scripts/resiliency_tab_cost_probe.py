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
rank for `default` and each tab sort (2026-10-07: with the key `default`
resolved to, the 📅 market line, the fundamentals coverage and the WATCH names'
Tradeable position, 📅 pill and growth chip). It prints the counts, the hand-check names
(a utility, a staple, NVDA, MU, SPY) with their event-day closes, and the
count identity `scanned == rated + partial + no_bars`.

`--dump-fixture PATH` calls the REAL `api.chart_maps` handler with explicit
arguments for seven variants (default, sort=res_t1, sort=res_t2, res=t1,eod,
res=t1,eod&res_mode=all, sort=res_today, sort=res_growth — 2026-10-07) and writes each `JSONResponse.body`
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
2026-10-07 b (🚀 two legs first + every gap says why): it also prints the
memo's `growth_coverage`, the served `growth_line` and fold, the SNDK and DBRG
GrowthReads with their chips, the top 15 of `res_growth` with their legs, the
acceptance names (stale / ETF / disagreement), the count of growth chips that
contain a dash (must be 0) and the identity `sum(classes) == scanned − no_bars`.
`--dump-fixture` also writes `_sndk_tile` — SNDK's served badges + stats built
by `tile_badges` / `tile_stats` from its `rank()` row (it sits past the 80-tile
cut on 🚀) with its last 30 cached bars — and serves every variant off ONE
universe snapshot (memoised in this process) so the dump costs one fan-out.

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
VARIANTS = (("default", {}), ("res_t1", {"sort": "res_t1"}), ("res_t2", {"sort": "res_t2"}),
            ("t1_eod_any", {"res": "t1,eod"}),
            ("t1_eod_all", {"res": "t1,eod", "res_mode": "all"}),
            ("res_today", {"sort": "res_today"}), ("res_growth", {"sort": "res_growth"}))
# 2026-10-07: his example (VST), the tiny / negative year-ago EPS bases (PBF, CRI),
# a material +4,671% base (TWLO), a mega cap and the benchmark
WATCH = ("VST", "PBF", "CRI", "TWLO", "NVDA", "SPY", "SNDK", "DBRG")
# 2026-10-07 b acceptance names (SPEC §5 V3)
ACCEPT = {"stale": ("AIQ", "MRX", "GLIBA", "SE", "ASML", "DOX"),
          "etf": ("SPY", "QQQ", "DRAM"),
          "disagree": ("BAC", "JPM", "GS")}
GREAD_KEYS = ("state", "gap", "bars", "period", "year_ago_period", "source", "latest_idx",
              "expected_idx", "sales_yoy_pct", "sales_stored_pct", "sales_series_pct",
              "sales_base", "sales_reason", "sales_ranked", "sales_agrees", "eps_yoy_pct",
              "eps_stored_pct", "eps_series_pct", "eps_base", "eps_reason", "eps_ranked",
              "eps_year_ago_ni", "score", "legs", "as_of")


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


def _sndk_tile(sym: str, now: datetime) -> dict:
    """SNDK's card as the board builds it (badges + stats from its rank() row),
    with its last 30 cached bars — it sits past the 80-tile cut on 🚀."""
    from chart_maps import board as B
    from chart_maps import resiliency_tab as R
    from sepa import prices
    got = R.cached_or_warm("full", now=now, sync=True)
    entry = got["entry"]
    raw = B._bulk_snaps_fanout([sym, R.BENCH, R.EW_BENCH])
    rows, *_ = R.rank(entry, raw, None, now=now, sort=R.SORT_GROWTH)
    r = next((x for x in rows if x["symbol"] == sym), None)
    if r is None:
        return {"symbol": sym, "missing": True}
    df = (prices.bulk_cached_frames([sym]) or {}).get(sym)
    bars = []
    if df is not None:
        for ts, b in df.tail(30).iterrows():
            bars.append({"t": ts.date().isoformat(), "o": float(b["open"]), "h": float(b["high"]),
                         "l": float(b["low"]), "c": float(b["close"]), "v": float(b["volume"])})
    return {"symbol": sym, "theme": None, "href": f"/sepa/{sym}", "last_close": r.get("ref_close"),
            "bands": [], "markers": [], "lines": [], "bars": bars,
            "badges": R.tile_badges(r), "stats": R.tile_stats(r), "why": R.why_text(r),
            "resiliency": r["resiliency"], "res_filter": dict(r["res_filter"])}


def dump_fixture(path: str, now: datetime) -> dict:
    from chart_maps import api
    from chart_maps import board as B
    variants = {}
    # ONE universe snapshot for every variant (this process only) — the Massive
    # snapshot is the probe's only network read; seven fan-outs bought nothing
    real_fan = B._bulk_snaps_fanout
    memo: dict = {}

    def _fan_once(symbols):
        key = "u" if len(list(symbols or [])) > 50 else ",".join(sorted(symbols or []))
        if key not in memo:
            memo[key] = real_fan(symbols)
        return memo[key]
    B._bulk_snaps_fanout = _fan_once
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
    doc["_sndk_tile"] = _sndk_tile("SNDK", now)
    B._bulk_snaps_fanout = real_fan
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
    syms = list(entry["syms"])
    raw = B._bulk_snaps_fanout(syms + [s for s in (R.BENCH, R.EW_BENCH) if s not in set(syms)])
    out["s_snapshot_fanout"] = round(time.perf_counter() - t2, 2)
    out["n_snap"] = len(raw)
    spy = raw.get(R.BENCH) or {}
    out["spy_snapshot"] = {k: spy.get(k) for k in ("change_pct", "prev_day_close",
                                                   "last_trade_price", "min_av", "min_t_ms")}

    ranks = {}
    for srt in ("default",) + R.TAB_SORTS:
        t3 = time.perf_counter()
        rows, counts, filters, today, su = R.rank(entry, raw, pm, now=now, sort=srt)
        resolved = R.resolve_sort(srt, mode=today.get("mode"), n_read=today.get("read"),
                                  n_growth=counts.get("growth_ranked"))
        tradeable = [r for r in rows if B.passes_liquidity(r.get("adv50"), "ok")]
        pos = {r["symbol"]: i + 1 for i, r in enumerate(tradeable)}
        watch = {}
        for w in WATCH:
            r = next((x for x in rows if x["symbol"] == w), None)
            if r is None:
                watch[w] = None
                continue
            badges = R.tile_badges(r)
            watch[w] = {"tradeable_pos": pos.get(w),
                        "pill": next((b["text"] for b in badges
                                      if b["text"].startswith(R.TODAY_MARK)), None),
                        "growth_chip": R.growth_chip(r["resiliency"].get("growth")),
                        "move_pct": (r["resiliency"].get("today") or {}).get("move_pct")}
        ranks[srt] = {"s": round(time.perf_counter() - t3, 3), "sort_unavailable": su,
                      "resolved": list(resolved), "n_tradeable": len(tradeable),
                      "top": [r["symbol"] for r in rows[:15]],
                      "top_legs": [
                          {"symbol": r["symbol"],
                           "legs": (r["resiliency"].get("growth") or {}).get("legs"),
                           "score": (r["resiliency"].get("growth") or {}).get("score"),
                           "eps_ranked": (r["resiliency"].get("growth") or {}).get("eps_ranked")}
                          for r in tradeable[:15]],
                      "top_tradeable": [
                          {"symbol": r["symbol"],
                           "move_pct": (r["resiliency"].get("today") or {}).get("move_pct"),
                           "chip": R.growth_chip(r["resiliency"].get("growth"))}
                          for r in tradeable[:15]],
                      "watch": watch}
    out["ranks"] = ranks
    out["counts"] = counts
    out["today"] = today
    out["market_line"] = R.market_line(today)
    out["fund_summary"] = entry.get("fund_summary")
    out["identity_scanned_eq_rated_partial_no_bars"] = (
        counts["scanned"] == counts["rated_t1"] + counts["partial_t1"] + counts["no_bars"])
    out["filters_pass"] = {i["key"]: i["pass"] for i in filters["items"]}

    # 🚀 growth coverage (2026-10-07 b)
    cov = entry.get("growth_coverage") or {}
    out["growth_coverage"] = cov
    out["growth_line"] = R.growth_line(cov)
    out["growth_gaps"] = R.growth_gaps_block(cov)
    out["identity_classes_eq_scanned_minus_no_bars"] = (
        sum((cov.get("classes") or {}).values()) == counts["scanned"] - counts["no_bars"])
    greads = {s: (rd.get("growth") or {}) for s, rd in (entry.get("reads") or {}).items()}
    out["growth_chips_with_dash"] = sorted(s for s, g in greads.items() if "—" in R.growth_chip(g))
    out["growth_named"] = {s: ({k: greads[s].get(k) for k in GREAD_KEYS}
                               | {"chip": R.growth_chip(greads[s]), "stat": R._growth_stat(greads[s])}
                               if s in greads else None)
                           for s in ("SNDK", "DBRG", "MU", "VST")}
    out["growth_accept"] = {grp: {s: ({"gap": greads[s].get("gap"), "score": greads[s].get("score"),
                                       "sales_reason": greads[s].get("sales_reason"),
                                       "chip": R.growth_chip(greads[s])} if s in greads else None)
                                  for s in names} for grp, names in ACCEPT.items()}
    g_rows, *_ = R.rank(entry, raw, pm, now=now, sort=R.SORT_GROWTH)
    lg = [int((r["resiliency"]["growth"] or {}).get("legs") or 0)
          if (r["resiliency"]["growth"] or {}).get("score") is not None else 0 for r in g_rows]
    out["growth_order_legs_non_increasing"] = all(a >= b for a, b in zip(lg, lg[1:]))
    out["growth_sndk_position"] = next((i + 1 for i, r in enumerate(g_rows)
                                        if r["symbol"] == "SNDK"), None)

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
