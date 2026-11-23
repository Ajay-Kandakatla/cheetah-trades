"""👀 Gajjala's Watch — the REST counter, read-only (2026-11-23, spec ggconn rev 2 §3.4, WP-3).

Ajay, verbatim (2026-11-23): "Can you clean up some connection I am seeing delays price update for AKAN on the watch
chart.." · "I would like us to focus on connections of Gajjala more for the rest of the tabs."

Reads the per-session counter docs `rest:{session}` (gajjala_watch.constants.REST_COUNT_ID_PREFIX) of the Watch's state
collection (C.COLL_STATE) and prints, per session: iterations, names (name-minutes read), failed_minutes, failed
(failed name-minutes), retried, recovered, pushed, no_time, errors, the share failed / names with a Wilson 95 % interval
(the scripts' own `wilson(k, n)`, scripts/spy_levels_study_2026_11_05.py) and `last`. Newest session first. No write.
A frequency, not an edge. This is the number C.REST_REREAD_ON (HIS CALL) is decided on.

  python -m scripts.gajjala_watch_rest_count [--sessions 10] [--json]
  python scripts/gajjala_watch_rest_count.py [--sessions 10] [--json]     (same, from backend/)

Both forms work (refix 2026-11-23): run by file path, `sys.path[0]` is backend/scripts, so the lazy
`from scripts.spy_levels_study_2026_11_05 import wilson` raised ModuleNotFoundError once a doc had names > 0. The
file-path form now puts backend/ first on the path; the `-m` form (and an import from the tests) never touches it.
The interval is the study's `wilson`, rounded to 3 dp (0.1 pp) — at a share under 0.1 % it reads 0.0 %–0.1 %;
widening that precision is not this script's call.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = str(Path(__file__).resolve().parents[1])


def _ensure_backend_on_path(path=None) -> list:
    """The file-path form only: backend/ first on `path` (sys.path), once. Already there → unchanged."""
    path = sys.path if path is None else path
    if BACKEND not in path:
        path[:0] = [BACKEND]
    return path


if not __package__:
    _ensure_backend_on_path()

KEYS = ("iterations", "names", "failed_minutes", "failed", "retried", "recovered", "pushed", "no_time", "errors")


def _wilson(k: int, n: int):
    from scripts.spy_levels_study_2026_11_05 import wilson
    return wilson(k, n)


def rows(state_coll, sessions: int = 0) -> list:
    """One row per `rest:*` doc, newest session first (`sessions` > 0 keeps that many). A None collection → []."""
    from chart_maps.gajjala_watch import constants as C
    if state_coll is None:
        return []
    docs = [d for d in state_coll.find({}) if isinstance(d, dict)
            and str(d.get("_id") or "").startswith(C.REST_COUNT_ID_PREFIX)]
    docs.sort(key=lambda d: str(d.get("session") or d["_id"]), reverse=True)
    if sessions and sessions > 0:
        docs = docs[:sessions]
    out = []
    for d in docs:
        r = {"session": d.get("session") or str(d["_id"])[len(C.REST_COUNT_ID_PREFIX):]}
        r.update({k: int(d.get(k) or 0) for k in KEYS})
        n, k = r["names"], r["failed"]
        r["share"] = round(k / n, 6) if n > 0 else None
        r["ci95"] = _wilson(k, n) if n > 0 else None
        r["last"] = d.get("last")
        out.append(r)
    return out


def main(argv=None, *, state_coll=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts.gajjala_watch_rest_count", description=__doc__.split("\n")[0])
    ap.add_argument("--sessions", type=int, default=0, help="keep the newest N sessions (0 = all)")
    ap.add_argument("--json", action="store_true", help="print the rows as JSON")
    args = ap.parse_args(argv)
    if state_coll is None:
        from chart_maps.gajjala_watch import colls as CO
        cs = CO.colls()
        state_coll = cs["state"] if cs else None
    out = rows(state_coll, args.sessions)
    if args.json:
        print(json.dumps(out, default=str))
        return 0
    if not out:
        print("no rest:* counter docs")
        return 0
    for r in out:
        ci = r["ci95"]
        print(f"{r['session']}: " + ", ".join(f"{k} {r[k]}" for k in KEYS)
              + (f" · failed/names {r['share']:.2%} (Wilson 95% {ci[0]:.1%}–{ci[1]:.1%})" if ci else " · failed/names —")
              + f" · last {r['last']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
