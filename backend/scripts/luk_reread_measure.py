"""🥇 Luk realtime cards — the step-13b board re-read, measured (luk realtime cards spec WP-A, 2026-11-12).

Ajay 2026-11-12: "Luks scan is not realtime I see all dated values can you make it realtime"

READ ONLY: Mongo finds on luk_passes / luk_reads / luk_state, and (`--probe`) minute bars from the minute cache or a
Massive fetch WITHOUT the cache write. No write anywhere, no push, no broker, no HTTP to the api.

  --report [--date D]  per pass: `at`, `wall_s`, `refresh.{asked_n, read_n, not_read, aplus_not_rung, budget_s, wall_s,
                       skipped}`, board_n / board_read_n; then the ok-pass wall p50 / p90 BEFORE vs AFTER the first pass
                       that carries `refresh` (a timing count — no strategy number, so no CI / placebo applies).
  --probe [--date D]   the planner's refresh_probe: today's SHOWN names (run._board_names — the pass's own engine) that
                       are off the latest pass's shortlist, framed (prior days from the minute cache, today fetched
                       without a write) and read; prints frames / detectors wall and the per-name cost.

RUN (inside the cron container, single runs, never a loop):
  docker exec -i -w /app -e PYTHONPATH=/app cheetah-market-app-cron-1 python scripts/luk_reread_measure.py --report
  docker exec -i -w /app -e PYTHONPATH=/app cheetah-market-app-cron-1 python scripts/luk_reread_measure.py --probe
`calls.minute_prior` in a pass doc counts minute-CACHE reads too (every load_day call), not only Massive calls.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ET = ZoneInfo("America/New_York")
POINTER_IDS = ("latest", "latest_cron")
ROW_REFRESH_KEYS = ("asked_n", "read_n", "not_read", "aplus_not_rung", "budget_s", "wall_s", "skipped", "board_n",
                    "board_read_n")


def _at_key(d: dict) -> str:
    at = d.get("at")
    if isinstance(at, datetime):
        at = (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).astimezone(ET).isoformat()
    return str(at or d.get("_id") or "")


def _p(walls: list, q: float) -> Optional[float]:
    """Nearest-rank on the sorted list (the planner's passes_probe rule); None when empty."""
    if not walls:
        return None
    w = sorted(walls)
    return w[int(q * (len(w) - 1))]


def report(store, day: str) -> dict:
    """{rows: [...], before: {n, p50, p90}, after: {n, p50, p90}, first_refresh_at} over the day's pass docs."""
    from chart_maps.gajjala import store as GS
    c = store.coll(GS.PASSES)
    docs = [d for d in (c.find({"date": day}) if c is not None else []) or []
            if isinstance(d, dict) and d.get("_id") not in POINTER_IDS]
    docs.sort(key=_at_key)
    rows, first = [], None
    for d in docs:
        rf = d.get("refresh") if isinstance(d.get("refresh"), dict) else None
        if rf is not None and first is None:
            first = _at_key(d)
        rows.append({"id": d.get("_id"), "at": _at_key(d), "on_demand": bool(d.get("on_demand")),
                     "status": d.get("status"), "wall_s": d.get("wall_s"),
                     "refresh": {k: rf.get(k) for k in ROW_REFRESH_KEYS} if rf is not None else None})

    def walls(after: bool) -> list:
        return [r["wall_s"] for r in rows if r["status"] == "ok" and isinstance(r["wall_s"], (int, float))
                and not r["on_demand"] and ((first is not None and r["at"] >= first) is after)]
    out = {"date": day, "rows": rows, "first_refresh_at": first}
    for k, after in (("before", False), ("after", True)):
        w = walls(after)
        out[k] = {"n": len(w), "p50": statistics.median(w) if w else None, "p90": _p(w, 0.9)}
    return out


def render_report(r: dict) -> str:
    lines = [f"🥇 Luk passes {r['date']} — first pass carrying refresh: {r['first_refresh_at'] or 'none'}"]
    for row in r["rows"]:
        rf = row["refresh"]
        tail = ("refresh —" if rf is None else
                "refresh " + " ".join(f"{k}={json.dumps(rf.get(k), default=str)}" for k in ROW_REFRESH_KEYS))
        lines.append(f"{row['at']} {'OD ' if row['on_demand'] else ''}{row['status']} wall={row['wall_s']} {tail}")
    for k in ("before", "after"):
        b = r[k]
        lines.append(f"{k}: ok cron passes {b['n']} · wall p50 {b['p50']} s · p90 {b['p90']} s")
    return "\n".join(lines)


def _probe_load(session: date):
    from daytrading import data as D

    def load(sym, day, force=False, include_premarket=True, include_afterhours=False):
        if day != session:
            cached = D._mongo_get_day(sym, day)
            if cached is not None:
                return D._filter_sessions(cached, include_premarket, include_afterhours)
        df = D._fetch_massive_minute(sym, day, day)               # NO _mongo_put_day: nothing is written
        if df is None or df.empty:
            return None
        return D._filter_sessions(df, include_premarket, include_afterhours)
    return load


def probe(store, session: date, *, load_day=None, now: Optional[datetime] = None, clock=time.monotonic) -> dict:
    """Frames + detectors wall for today's shown names off the latest pass's shortlist. READ ONLY."""
    from chart_maps.luk import bars as BA
    from chart_maps.luk import constants as LC
    from chart_maps.luk import detectors as DT
    from chart_maps.luk import run as R
    now = now or datetime.now(timezone.utc)
    docs = [d for d in (store.reads(session) or []) if isinstance(d, dict)]
    latest = store.latest_pass() or {}
    sl = {str(s).upper() for s in ((latest.get("shortlist") or {}).get("symbols") or [])}
    board = R._board_names(docs, store.alert_rows([session]))
    asked = [s for s in board if s not in sl]
    stats: dict = {}
    t0 = clock()
    frames = BA.frames_for(asked, session, now, load_day=load_day or _probe_load(session),
                           budget_sec=LC.LUK_PASS_BUDGET_SEC - LC.LUK_GRADE_BUDGET_SEC, stats=stats) or {}
    t_frames = clock() - t0
    prev_t1, _ = R.prev_bars_through(store.get_state(LC.LUK_STATE_BARS_THROUGH), session.isoformat())
    by = {str(d["symbol"]).upper(): d for d in docs if d.get("symbol")}
    changes = []
    t0 = clock()
    for sym, F in frames.items():
        old = (by.get(sym) or {}).get("setups") or {}
        new = DT.read_all(F, (by.get(sym) or {}).get("facts"), session.isoformat(), prev_through_1m=prev_t1) or {}
        for setup in LC.SETUPS:
            a, b = (old.get(setup) or {}).get("state"), (new.get(setup) or {}).get("state")
            if a != b and (a or b):
                changes.append(f"{sym}:{setup}:{a}->{b}")
    t_detect = clock() - t0
    return {"date": session.isoformat(), "board_n": len(board), "asked_n": len(asked), "stats": stats,
            "frames_wall_s": round(t_frames, 3), "detect_wall_s": round(t_detect, 3),
            "per_name_s": round((t_frames + t_detect) / max(1, len(asked)), 3), "changes": changes}


def main(argv=None, *, store=None) -> int:
    ap = argparse.ArgumentParser(prog="luk_reread_measure", description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--report", action="store_true")
    g.add_argument("--probe", action="store_true")
    ap.add_argument("--date", help="ISO session (default: today ET)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    day = date.fromisoformat(a.date) if a.date else datetime.now(ET).date()
    if store is None:
        from chart_maps.luk import store as ST
        store = ST.default()
    out = report(store, day.isoformat()) if a.report else probe(store, day)
    if a.json:
        print(json.dumps(out, default=str))
    elif a.report:
        print(render_report(out))
    else:
        print(json.dumps(out, default=str, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
