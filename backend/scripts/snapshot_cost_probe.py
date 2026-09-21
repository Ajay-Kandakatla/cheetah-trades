#!/usr/bin/env python
"""What ONE live-quote call costs — the numbers behind chart_maps.board.

READ-ONLY. It fetches quotes and prints; it writes nothing, stores nothing and
changes no board. Re-run it before quoting any of its numbers
(memory feedback_ship_the_backtest) and paste the printed dict into
`chart_maps.board.FLIGHT_COST_MEASURED`, with the environment line beside it.

Why it exists (Ajay 2026-09-21, the 🌀 AMD tab): the chips count every name at
the selected grades on every request, which is one `prices.bulk_snapshot` over
the whole grade set. That cost has to be MEASURED, not estimated, because it
sits on his click.

Three things it measures:

  1. handshake  — 3 x a one-symbol `bulk_snapshot` on a bare `requests.get`
                  versus a reused `requests.Session`. Most of a per-tile call
                  used to be the TLS handshake; `prices._http()` is the fix and
                  this is the number that justifies it.
  2. n_default  — the default grade set (`TB.board("amd", limit=
                  TB_FLIGHT_SCAN_LIMIT)`) and the wall of ONE bulk_snapshot
                  over it.
  3. n_all      — the same with `grades="all"` (11 sequential 250-name chunks).

Every wall is the MEDIAN of 3.

Run it pre-market or after 16:00 ET and state the wall beside the number — it
is one ~2 s call, not a heavy replay, but the tape's own load moves it.

    host:       backend/.venv/bin/python backend/scripts/snapshot_cost_probe.py
    container:  docker exec -i -w /app cheetah-market-app-api-1 \
                    sh -c 'PYTHONPATH=/app python -u scripts/snapshot_cost_probe.py'
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ET = ZoneInfo("America/New_York")
PROBE_SYMBOL = "AAPL"
REPEATS = 3


def _median_wall(fn, repeats: int = REPEATS):
    """(median seconds, every sample) for `fn` run `repeats` times."""
    walls = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        walls.append(round(time.perf_counter() - t0, 3))
    return round(statistics.median(walls), 3), walls


def _handshake():
    """Bare `requests.get` vs a reused Session, one symbol, same endpoint."""
    import requests

    from massive_keys import stocks_key

    key = stocks_key()
    if not key:
        return {"skipped": "no stocks key in this environment"}
    url = "https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers"
    params = {"tickers": PROBE_SYMBOL, "apiKey": key}
    bare, bare_all = _median_wall(lambda: requests.get(url, params=params, timeout=15))
    sess = requests.Session()
    # One warm-up so the Session number is the KEEP-ALIVE number, not the first
    # connection's handshake — which is exactly what the board reuses.
    sess.get(url, params=params, timeout=15)
    keep, keep_all = _median_wall(lambda: sess.get(url, params=params, timeout=15))
    return {"bare_s": bare, "bare_all": bare_all,
            "keepalive_s": keep, "keepalive_all": keep_all,
            "saved_s": round(bare - keep, 3)}


def _grade_set(grades):
    """The symbols one AMD request counts over, at `grades`."""
    from chart_maps.board import TB_FLIGHT_SCAN_LIMIT
    from supply_demand import turning_bullish as TB

    b = TB.board("amd", limit=TB_FLIGHT_SCAN_LIMIT, grades=grades)
    return [r.get("symbol") for r in (b.get("rows") or []) if r.get("symbol")]


def _sweep(label, grades):
    from sepa import prices

    syms = _grade_set(grades)
    if not syms:
        return {"label": label, "n": 0, "s": None,
                "skipped": "the stored turning-bullish document is empty here"}
    wall, walls = _median_wall(lambda: prices.bulk_snapshot(syms))
    return {"label": label, "n": len(syms), "s": wall, "all": walls,
            "chunks": -(-len(syms) // prices._SNAP_CHUNK)}


def main() -> int:
    now = datetime.now(ET)
    try:
        from supply_demand.zone_edge import session_state
        tape = session_state(now)
    except Exception as exc:                                    # noqa: BLE001
        tape = "unknown (%s)" % exc
    env = {
        "where": "container" if os.path.exists("/app") else "host",
        "et": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "tape_session": tape,
        "python": sys.version.split()[0],
    }

    handshake = _handshake()
    default = _sweep("default grades", None)
    every = _sweep("grades=all", "all")

    measured = {
        "date": now.date().isoformat(),
        "n_default": default.get("n") or 0,
        "s_default": default.get("s"),
        "n_all": every.get("n") or 0,
        "s_all": every.get("s"),
    }

    print("ENVIRONMENT      ", json.dumps(env))
    print("HANDSHAKE        ", json.dumps(handshake))
    print("DEFAULT GRADE SET", json.dumps(default))
    print("ALL GRADES       ", json.dumps(every))
    print()
    print("FLIGHT_COST_MEASURED =", json.dumps(measured, indent=4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
