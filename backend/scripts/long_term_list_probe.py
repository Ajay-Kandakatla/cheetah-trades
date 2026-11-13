"""Probe the 📅 Long Term weekly read on the real caches. READ-ONLY, cache-only (spec §3.9 / §5.5, WP-RUN, 2026-11-12).

Ajay 2026-11-12, verbatim: "… keep updating it from all the other tabs info.. Weekly and if something gets dropped let
me know when to like is Sales drop or Stage 2 to Stage 3 or stage 4 changes."

Run it in a THROWAWAY container only, outside RTH (09:30–16:00 ET) — never in the live api / cron / frontend containers:

    docker run --rm --cpus 2 --memory 4g --network cheetah-market-app_default \\
      -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York \\
      -e SEPA_UNIVERSE_MODE=full -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 \\
      -v <tree>/backend:/app:ro -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro \\
      -v <outdir>:/out -w /out cheetah-api:latest python -u /app/scripts/long_term_list_probe.py --out /out

READ-ONLY BY CONSTRUCTION, set up BEFORE any app import can connect (the fallen_tab_probe pattern):
  * every pymongo write method is a RECORDED no-op in this process;
  * every socket connect other than the Mongo host is REFUSED and recorded;
  * `prices.bulk_snapshot` -> {} and `prices.load_prices` -> the cached frame only (no provider call).

What it does: `sources.load_all` with every source timed, then `weekly.run(dry_run=True, force=True)` on those sources
(the placebo pool's universe-frames read timed, max RSS reported), then `payload.build_payload(owner=True)` twice — from
the dry run's own docs ("ready", the shape the first Friday will serve) and from what Mongo holds today (the served
"seed_only" before the first run). Writes /out/long_term_dry.json, /out/long_term_payload.json,
/out/long_term_payload_seed_only.json and /out/long_term_probe_summary.json.

Not a study: counts and timings; no placebo applies to a probe. UNMEASURED.
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ET = ZoneInfo("America/New_York")
WRITE_METHODS = ("insert_one", "insert_many", "update_one", "update_many", "replace_one",
                 "delete_one", "delete_many", "find_one_and_update", "find_one_and_replace",
                 "find_one_and_delete", "bulk_write", "create_index", "create_indexes",
                 "drop", "drop_index", "drop_indexes", "rename")
ATTEMPTED: list = []
REFUSED: list = []


def block_writes() -> None:
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
        raise ConnectionRefusedError(f"refused by long_term_list_probe: {addr}")

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


def _rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(r / (1024.0 * 1024.0) if sys.platform == "darwin" else r / 1024.0, 1)


def _dump(path: Path, obj) -> bool:
    """True when the object serialises with allow_nan=False (NaN-free)."""
    try:
        txt = json.dumps(obj, allow_nan=False, default=str)
        ok = True
    except ValueError:
        txt = json.dumps(obj, default=str)
        ok = False
    path.write_text(txt, encoding="utf-8")
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Probe the Long Term weekly read (read-only).")
    ap.add_argument("--now", default=None, help="ISO datetime in ET (default: now)")
    ap.add_argument("--out", default=os.environ.get("LONG_TERM_PROBE_OUT", "/out"))
    args = ap.parse_args(argv)

    block_network()
    block_writes()
    stub_providers()

    from long_term_list import constants as C
    from long_term_list import payload as PL
    from long_term_list import seed as SEED
    from long_term_list import sources as SRC
    from long_term_list import store as ST
    from long_term_list import weekly as WK

    now = (datetime.fromisoformat(args.now).replace(tzinfo=ET) if args.now else datetime.now(ET))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    t_all = time.perf_counter()

    source_s: dict = {}
    real_fenced = SRC._fenced

    def _timed(key, fn, *a, **kw):
        t = time.perf_counter()
        try:
            return real_fenced(key, fn, *a, **kw)
        finally:
            source_s[key] = round(time.perf_counter() - t, 2)
    SRC._fenced = _timed

    seed = SEED.load()
    saved = SEED.unique_names(seed)
    t = time.perf_counter()
    src = SRC.load_all(now, saved=set(saved), seed=seed)
    load_s = round(time.perf_counter() - t, 2)
    rss_after_sources = _rss_mb()

    t = time.perf_counter()
    dry = WK.run(now, sources=src, dry_run=True, force=True, trigger="probe")
    run_s = round(time.perf_counter() - t, 2)
    rss_after_run = _rss_mb()
    dry_ok = _dump(out_dir / "long_term_dry.json", dry)

    baseline = SEED.load_baseline()
    t = time.perf_counter()
    closes = SRC.pankaj_closes(sorted(SEED.pankaj_entries(seed)), now)
    closes_s = round(time.perf_counter() - t, 2)
    runs, fwd = [], []
    if dry.get("ran"):
        runs = [dry["run"]]
        fwd = ([dry["base"]] if dry.get("base") else []) + list(dry.get("points") or [])
    ready = PL.build_payload(seed, baseline, runs, fwd, closes, now=now, owner=True)
    ready_ok = _dump(out_dir / "long_term_payload.json", ready)
    cs = ST.colls()
    stored_runs = ST.runs_desc(cs["runs"]) if cs else []
    stored_fwd = ST.forward_docs(cs["forward"]) if cs else []
    served = PL.build_payload(seed, baseline, stored_runs, stored_fwd, closes, now=now, owner=True)
    served_ok = _dump(out_dir / "long_term_payload_seed_only.json", served)

    run_doc = dry.get("run") or {}
    rows = [r for c in ready.get("categories") or [] for r in c.get("rows") or []] + list(ready.get("changed") or [])
    summary = {
        "now": now.isoformat(timespec="seconds"),
        "ran": dry.get("ran"), "reason": dry.get("reason"), "week": dry.get("week"), "session": dry.get("session"),
        "sources": {k: {"ok": (src.get(k) or {}).get("ok"), "reason": (src.get(k) or {}).get("reason"),
                        "as_of": (src.get(k) or {}).get("as_of"), "n": (src.get(k) or {}).get("n"),
                        "seconds": source_s.get(k)} for k in SRC.SOURCE_KEYS},
        "timings_s": {"load_all": load_s, "dry_run_total": run_s, "pool_frames": (run_doc.get("timings") or {}).get(
            "pool_s"), "pankaj_closes": closes_s, "probe_total": round(time.perf_counter() - t_all, 2)},
        "max_rss_mb": {"after_sources": rss_after_sources, "after_dry_run": rss_after_run},
        "saved_rows": len(run_doc.get("names") or {}),
        "payload_rows": len(rows), "payload_unique_rows": len({r.get("symbol") for r in rows}),
        "categories": {c: {"strip": [t.get("symbol") for t in (run_doc.get("top") or {}).get(c) or []],
                           "read": (run_doc.get("top_read") or {}).get(c)} for c in C.SCREENED_KEYS},
        "digest": run_doc.get("digest"),
        "rings": (run_doc.get("digest") or {}).get("rings"),
        "events_by_kind": {},
        "at_zone": (ready.get("zones") or {}).get("at_zone"),
        "base": {k: v for k, v in (dry.get("base") or {}).items() if k in ("session", "kind", "no_base")},
        "n_points": len(dry.get("points") or []),
        "payload_state_ready": ready.get("state"), "payload_state_served": served.get("state"),
        "nan_free": {"dry": dry_ok, "ready": ready_ok, "served": served_ok},
        "attempted_writes": ATTEMPTED, "refused_connects": REFUSED,
        "over_300s": (time.perf_counter() - t_all) > 300,
    }
    for e in run_doc.get("events") or []:
        summary["events_by_kind"][e.get("kind")] = summary["events_by_kind"].get(e.get("kind"), 0) + 1
    _dump(out_dir / "long_term_probe_summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("ran", "reason", "week", "timings_s", "max_rss_mb", "saved_rows",
                                              "payload_rows", "rings", "nan_free", "refused_connects")},
                     default=str))
    return 0 if dry.get("ran") else 1


if __name__ == "__main__":                                     # pragma: no cover
    sys.exit(main())
