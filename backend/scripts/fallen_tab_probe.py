"""Probe the 📉 Down 40%+ tab on the real caches. READ-ONLY, cache-only.

The re-runnable check behind the numbers in
`docs/chart_maps/fallen_40_tab_2026_10_02.md` (spec §5.3). Run it in a
THROWAWAY container only — never in the live api / cron / frontend containers,
never on ports 8000 / 5173:

    docker run --rm --cpus 2 --memory 3g --network cheetah-market-app_default \\
      -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York \\
      -e SEPA_UNIVERSE_MODE=full -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 \\
      -v <tree>/backend:/app:ro -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro \\
      -v <outdir>:/out -w /out cheetah-api:latest python -u /app/scripts/fallen_tab_probe.py

READ-ONLY BY CONSTRUCTION, set up BEFORE any app import can connect:
  * every pymongo write method is a RECORDED no-op in this process
    (`create_index` returns a name so the connection helpers still work);
  * every socket connect other than the Mongo host is REFUSED and recorded;
  * `prices.bulk_snapshot` -> {} and `prices.load_prices` -> the cached frame
    only, so no provider (Massive / Finnhub / Yahoo / FRED) can be called.
The attempted writes and refused connects are printed (expected: create_index
no-ops only, no refused connect from the tab's own path).

What it does: ONE cold build (`fallen_tab.cached_or_warm(sync=True)`, timed),
then `board.board(tab="fallen")` for every served sort at depth 40 and the
default sort at 50 / 60 / 70 (each timed — a warm request minus the live
snapshot, which is stubbed). Writes /out/fallen_payload_<sort>_<depth>.json and
/out/fallen_probe_summary.json: counts + the counts invariant, the APP row,
CTVA's and the ETFs' classes, the named suspects, per-source coverage, the
drop days with nothing on file, timings, attempted writes, refused connects.

Not a study: a count and a timing; no placebo applies. UNMEASURED.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ET = ZoneInfo("America/New_York")
OUT = Path(os.environ.get("FALLEN_PROBE_OUT", "/out"))
NAMED = ("APP", "CTVA", "SION", "RNA", "WSHP", "BITO", "REMX", "SLV", "SOXL", "WGMI")
WRITE_METHODS = ("insert_one", "insert_many", "update_one", "update_many", "replace_one",
                 "delete_one", "delete_many", "find_one_and_update", "find_one_and_replace",
                 "find_one_and_delete", "bulk_write", "create_index", "create_indexes",
                 "drop", "drop_index", "drop_indexes", "rename")
ATTEMPTED: list = []
REFUSED: list = []


def block_writes() -> None:
    """Every pymongo write method -> a recorded no-op (the resiliency_study pattern)."""
    from pymongo.collection import Collection

    def _make(name):
        def _noop(self, *a, **k):
            ATTEMPTED.append(f"{getattr(self, 'name', '?')}.{name}")
            return "blocked_index" if name == "create_index" else None
        return _noop
    for m in WRITE_METHODS:
        if hasattr(Collection, m):
            setattr(Collection, m, _make(m))


def block_network() -> None:
    """Refuse every connect except the Mongo host (and unix sockets)."""
    host = urlparse(os.environ.get("MONGO_URL", "mongodb://mongo:27017")).hostname or "mongo"
    try:
        allowed = {host, socket.gethostbyname(host)}
    except OSError:
        allowed = {host}
    real_connect, real_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def _ok(addr):
        try:
            return addr[0] in allowed
        except Exception:                                       # noqa: BLE001
            return False

    def connect(self, addr):
        if self.family == socket.AF_UNIX or _ok(addr):
            return real_connect(self, addr)
        REFUSED.append(str(addr))
        raise ConnectionRefusedError(f"refused by fallen_tab_probe: {addr}")

    def connect_ex(self, addr):
        if self.family == socket.AF_UNIX or _ok(addr):
            return real_connect_ex(self, addr)
        REFUSED.append(str(addr))
        return 111
    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex


def stub_providers() -> None:
    from sepa import prices

    def _no_snapshot(*a, **k):
        return {}

    def _cached_only(symbol, *a, **k):
        return prices.bulk_cached_frames([symbol]).get(str(symbol or "").upper())
    prices.bulk_snapshot = _no_snapshot
    prices.load_prices = _cached_only


def _dump(path: Path, obj) -> bool:
    """True when the payload serialises with allow_nan=False (NaN-free)."""
    try:
        txt = json.dumps(obj, allow_nan=False, default=str)
        ok = True
    except ValueError:
        txt = json.dumps(obj, default=str)
        ok = False
    path.write_text(txt, encoding="utf-8")
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Probe the Down 40%+ tab (read-only).")
    ap.add_argument("--now", default=None, help="ISO datetime in ET (default: now)")
    ap.add_argument("--universe", default="full")
    args = ap.parse_args(argv)

    block_network()
    block_writes()
    stub_providers()

    from chart_maps import board as BOARD
    from chart_maps import fallen_tab as FAL
    from sepa import prices

    now = (datetime.fromisoformat(args.now).replace(tzinfo=ET) if args.now
           else datetime.now(ET))
    OUT.mkdir(parents=True, exist_ok=True)
    timings: dict = {}

    t0 = time.perf_counter()
    got = FAL.cached_or_warm(args.universe, now=now, sync=True)
    timings["cold_build_s"] = round(time.perf_counter() - t0, 2)
    entry = got["entry"]
    c = dict(entry["counts"])
    invariant = c["scanned"] == sum(c[k] for k in FAL.STATUSES)

    runs = [(s["key"], FAL.DEPTH_STEPS[0]) for s in FAL.served_sorts()]
    runs += [("default", d) for d in FAL.DEPTH_STEPS[1:]]
    payloads: dict = {}
    for sort, depth in runs:
        t1 = time.perf_counter()
        out = BOARD.board(tab="fallen", limit=BOARD.LIMIT_MAX, sort=sort, depth=str(depth),
                          universe=args.universe)
        dt = round(time.perf_counter() - t1, 2)
        nan_free = _dump(OUT / f"fallen_payload_{sort}_{depth}.json", out)
        fb = out.get("fallen_board") or {}
        payloads[f"{sort}_{depth}"] = {"s": dt, "nan_free": nan_free,
                                       "tiles": [t["symbol"] for t in out.get("tiles") or []],
                                       "counts": fb.get("counts"),
                                       "header": fb.get("header"),
                                       "count_line": fb.get("count_line")}

    # The named names' classes off the same cached frames; the scan row's
    # `is_etf` is not re-read here (the static ETF lists still apply) — a listed
    # name's own row is in the entry.
    frames = prices.bulk_cached_frames(list(NAMED))
    etfs = FAL._static_etfs()
    session = FAL.session_for(now)
    named = {}
    for s in NAMED:
        st, rd = FAL.classify(s, frames.get(s), None, etfs, session)
        named[s] = {"status": st, "read": {k: (rd or {}).get(k) for k in (
            "close", "close_date", "high", "high_date", "low", "low_date", "pct_below",
            "suspect")} if rd else None}
    app = (entry.get("rows") or {}).get("APP")
    shown = payloads.get(f"default_{FAL.DEPTH_STEPS[0]}", {}).get("tiles") or []
    summary = {
        "now": now.isoformat(), "session": entry.get("session"), "as_of": entry.get("as_of"),
        "counts": c, "invariant_holds": invariant,
        "app": None if app is None else {k: app.get(k) for k in (
            "close", "close_date", "high", "high_date", "low", "low_date", "pct_below",
            "pct_above_low", "market_cap", "sector", "in_scan", "top3_share_pct")},
        "app_listed": "APP" in (entry.get("rows") or {}), "app_shown_default": "APP" in shown,
        "named": named,
        "ctva_in_tiles": any("CTVA" in p["tiles"] for p in payloads.values()),
        "etfs_in_tiles": sorted({s for p in payloads.values() for s in p["tiles"]
                                 if s in etfs}),
        "suspects": FAL.suspects_block(entry.get("suspects")),
        "sources": entry.get("sources"),
        "drops_total": entry.get("drops_total"), "drops_nothing": entry.get("drops_nothing"),
        "timings": {**timings, **{k: v["s"] for k, v in payloads.items()}},
        "payloads": payloads,
        "attempted_writes": sorted(set(ATTEMPTED)), "attempted_write_count": len(ATTEMPTED),
        "refused_connects": REFUSED,
    }
    _dump(OUT / "fallen_probe_summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("session", "as_of", "counts", "invariant_holds",
                                              "app", "ctva_in_tiles", "etfs_in_tiles",
                                              "drops_total", "drops_nothing", "timings",
                                              "attempted_writes", "refused_connects")},
                     default=str, indent=2))
    return 0 if invariant else 1


if __name__ == "__main__":                                   # pragma: no cover
    raise SystemExit(main())
