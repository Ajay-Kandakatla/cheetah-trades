#!/usr/bin/env python
"""What ONE Massive minute fetch costs — bare `requests.get` vs the recycled keep-alive session vs the real fetch.

READ-ONLY. It fetches today's 1-minute aggregates for a few names and prints ONE dict. No Mongo write, no websocket,
no board change. It NEVER prints a URL, the params or the key: errors are reported by exception TYPE name only.

Why it exists (spec ggconn 2026-11-23 §3.3, WP-4 — Ajay: "Can you clean up some connection I am seeing delays price
update for AKAN on the watch chart.."): `daytrading.data._fetch_massive_minute` moved from a bare `requests.get` (a new
TCP + TLS handshake per call) to `sepa.prices._http()` (http_hygiene tool 3). This is the re-runnable number behind it.

What it measures (medians of 2 runs each):
  1. sequential — N names one after another: per-call median ms, total s, failures — bare / pooled / real fetch.
  2. 8 threads  — the same N names on 8 workers (the `chart_maps.gajjala.bars.frames_for` shape): wall s, failures.
  3. idle gap   — ONE thread, the pooled session: a warm GET, an idle gap, the timed GET; gaps 5 / 10 / 15 /
                  `prices.IDLE_RECYCLE_SEC - 1` s (read from the module), 4 rounds each: per gap `n`, `fail`, the
                  error type names, median ms, and how many NEW connections the pool opened (`new_conn`, the
                  urllib3 `HTTPConnectionPool.num_connections` delta). A session idle `IDLE_RECYCLE_SEC` is closed
                  by us, so reuse is WITHIN one Watch iteration's worker threads, not across minutes.
  4. optional   — `--wall-readings K`: K readings of the 👀 Watch `latest` state doc's `wall_s`, one cadence
                  (`GG1M_CADENCE_SEC`) apart (a read, never a write).

Names: default = the 20 most recent 👀 Watch tiles (a read of `gajjala_watch_tiles`); `--symbols A,B,C` overrides.

    api container (after the deploy; the container runs origin/main):
      docker exec -i -w /app cheetah-market-app-api-1 python scripts/minute_fetch_cost_probe.py
      docker exec -i -w /app cheetah-market-app-api-1 python scripts/minute_fetch_cost_probe.py --skip-idle --wall-readings 10
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

GAPS_FIXED = (5.0, 10.0, 15.0)
ROUNDS = 4
RUNS = 2
THREADS = 8                     # = chart_maps.board.BAR_WORKERS (read at run time, see _threads())
N_DEFAULT = 20


def _threads() -> int:
    try:
        from chart_maps import board
        return int(board.BAR_WORKERS)
    except Exception:
        return THREADS


def gaps() -> tuple:
    """5 / 10 / 15 / IDLE_RECYCLE_SEC − 1 — the last one read from sepa.prices, never typed."""
    from sepa import prices
    return GAPS_FIXED + (float(prices.IDLE_RECYCLE_SEC) - 1.0,)


def _url(sym: str, day) -> str:
    from daytrading import data as D
    return f"{D.BASE_URL}/v2/aggs/ticker/{sym.upper()}/range/1/minute/{day}/{day}"


def _params(key: str) -> dict:
    return {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": key}


def _bare_get(url, **kw):
    """The old shape: a bare `requests.get` (a new connection per call). Tests replace this."""
    import requests
    return requests.get(url, **kw)


def _pooled_get(url, **kw):
    """The new shape: the minute fetch's own seam (`daytrading.data._http_get` = `prices._http().get`)."""
    from daytrading import data as D
    return D._http_get(url, **kw)


def _n_conn():
    """How many connections the calling thread's pooled session has opened to Massive (None when no session)."""
    try:
        from daytrading import data as D
        from sepa import prices
        s = prices._http().sess
        if s is None:
            return None
        pool = s.get_adapter(D.BASE_URL).poolmanager.connection_from_url(D.BASE_URL)
        return int(pool.num_connections)
    except Exception:
        return None


def _one_get(get, sym, day, key) -> dict:
    from daytrading import data as D
    t0 = time.perf_counter()
    try:
        r = get(_url(sym, day), params=_params(key), timeout=D._FETCH_TIMEOUT_SEC)
        ok = getattr(r, "status_code", None) == 200
        return {"ms": (time.perf_counter() - t0) * 1000.0, "ok": ok,
                "err": None if ok else f"HTTP{getattr(r, 'status_code', '?')}"}
    except Exception as exc:
        return {"ms": (time.perf_counter() - t0) * 1000.0, "ok": False, "err": type(exc).__name__}


def _one_fetch(sym, day) -> dict:
    """The REAL `_fetch_massive_minute` (module breaker, the house seam). A provider failure = `last_fetch_failed()`."""
    from daytrading import data as D
    t0 = time.perf_counter()
    try:
        D._fetch_massive_minute(sym, day, day)
        ok = not D.last_fetch_failed()
        return {"ms": (time.perf_counter() - t0) * 1000.0, "ok": ok, "err": None if ok else "provider_failed"}
    except Exception as exc:
        return {"ms": (time.perf_counter() - t0) * 1000.0, "ok": False, "err": type(exc).__name__}


def _sum(rows: list) -> dict:
    ms = [r["ms"] for r in rows]
    return {"n": len(rows), "fail": sum(1 for r in rows if not r["ok"]),
            "errs": sorted({r["err"] for r in rows if r["err"]}),
            "median_ms": round(statistics.median(ms)) if ms else None,
            "total_s": round(sum(ms) / 1000.0, 2)}


def _shape_seq(call, syms) -> dict:
    runs = [_sum([call(s) for s in syms]) for _ in range(RUNS)]
    return {"runs": runs, "median_ms": [r["median_ms"] for r in runs], "total_s": [r["total_s"] for r in runs],
            "fail": sum(r["fail"] for r in runs), "errs": sorted({e for r in runs for e in r["errs"]})}


def _shape_thr(call, syms, workers) -> dict:
    out = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as ex:
            rows = list(ex.map(call, syms))
        s = _sum(rows)
        s["wall_s"] = round(time.perf_counter() - t0, 2)
        out.append(s)
    return {"runs": out, "wall_s": [r["wall_s"] for r in out], "fail": sum(r["fail"] for r in out),
            "errs": sorted({e for r in out for e in r["errs"]})}


def idle_gap_series(syms, day, key, *, sleep=time.sleep, get=None, n_conn=None, gap_list=None,
                    rounds: int = ROUNDS) -> dict:
    """Per gap: a warm pooled GET, `sleep(gap)`, the timed pooled GET; `new_conn` = the pool's connection-count delta."""
    get = get or _pooled_get
    n_conn = n_conn or _n_conn
    out = {}
    for g in (gap_list if gap_list is not None else gaps()):
        rows = []
        for i in range(rounds):
            sym = syms[i % len(syms)]
            _one_get(get, sym, day, key)
            c0 = n_conn()
            sleep(g)
            r = _one_get(get, sym, day, key)
            c1 = n_conn()
            r["new_conn"] = (c1 - c0) if isinstance(c0, int) and isinstance(c1, int) else None
            rows.append(r)
        s = _sum(rows)
        s.pop("total_s", None)
        s["ms"] = [round(r["ms"]) for r in rows]
        s["new_conn"] = [r["new_conn"] for r in rows]
        out[f"{g:g}"] = s
    return out


def watch_names(n: int = N_DEFAULT) -> list:
    """The most recent `n` 👀 Watch tiles, in the Massive spelling (a read)."""
    from chart_maps.gajjala_watch import colls as CO
    from sepa.symbols import for_massive
    cs = CO.colls(None)
    if not cs:
        return []
    docs = list(cs["tiles"].find({}, {"_id": 1}).sort("at", -1).limit(n))
    return [for_massive(d["_id"]) for d in docs]


def wall_readings(k: int, *, sleep=time.sleep) -> list:
    """K readings of the Watch `latest` state doc's `wall_s` / `n_names` / `n_read`, one cadence apart (reads)."""
    from chart_maps.gajjala import constants as GC
    from chart_maps.gajjala_watch import colls as CO, constants as C
    out = []
    for i in range(k):
        cs = CO.colls(None)
        st = (cs["state"].find_one({"_id": C.STATE_LATEST_ID}) if cs else None) or {}
        out.append({"at": str(st.get("at")), "wall_s": st.get("wall_s"), "n_names": st.get("n_names"),
                    "n_read": st.get("n_read")})
        if i < k - 1:
            sleep(GC.GG1M_CADENCE_SEC)
    return out


def run(syms, day, *, key=None, skip_idle=False, sleep=time.sleep, n_conn=None, wall_k=0) -> dict:
    """The ONE dict. `key` None = `massive_keys.stocks_key()`; no key → nothing is fetched."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    if key is None:
        from massive_keys import stocks_key
        key = stocks_key()
    out = {"at_et": datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S"),
           "key": bool(key), "names": len(syms), "runs": RUNS}
    try:
        from sepa import prices
        out["idle_recycle_sec"] = float(prices.IDLE_RECYCLE_SEC)
    except Exception:
        pass
    if not key or not syms:
        out["skipped"] = "no key" if not key else "no names"
        return out
    workers = _threads()
    out["threads"] = workers
    bare = lambda s: _one_get(_bare_get, s, day, key)          # noqa: E731
    pooled = lambda s: _one_get(_pooled_get, s, day, key)      # noqa: E731
    real = lambda s: _one_fetch(s, day)                        # noqa: E731
    out["sequential"] = {"bare": _shape_seq(bare, syms), "pooled": _shape_seq(pooled, syms),
                         "real_fetch": _shape_seq(real, syms)}
    out["threads8"] = {"bare": _shape_thr(bare, syms, workers), "pooled": _shape_thr(pooled, syms, workers),
                       "real_fetch": _shape_thr(real, syms, workers)}
    if not skip_idle:
        out["idle_gap"] = idle_gap_series(syms, day, key, sleep=sleep, n_conn=n_conn)
    if wall_k:
        out["wall_readings"] = wall_readings(wall_k, sleep=sleep)
    return out


def main(argv=None) -> int:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from observability.logsetup import install_redaction
    logging.basicConfig(level=logging.ERROR)
    install_redaction()
    logging.getLogger("daytrading.data").setLevel(logging.CRITICAL)   # its failure lines carry the (scrubbed) URL
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--symbols", default="", help="comma-separated names (default: the 👀 Watch tiles)")
    ap.add_argument("--n", type=int, default=N_DEFAULT)
    ap.add_argument("--skip-idle", action="store_true")
    ap.add_argument("--wall-readings", type=int, default=0)
    a = ap.parse_args(argv)
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()] or watch_names(a.n)
    day = datetime.now(ZoneInfo("America/New_York")).date()
    print(json.dumps(run(syms[:a.n], day, skip_idle=a.skip_idle, wall_k=a.wall_readings), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
