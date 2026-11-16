"""👀 Watch LIVE (2026-11-16, WP-E, critique C7) — how blind is THE one Massive socket, per session? READ-ONLY.

Ajay 2026-11-16: "I need live volume to be shown at the bottom" · "Of each chart". The live column counts only the
prints the ONE socket saw; a second client on the key kicks it, and until the next auth it sees nothing. This probe
turns "kicks every ~2 min" into a number from the feed's OWN persisted kick timeline (Mongo
`live_feed.LIVE_FEED_EVENTS_COLL`, TTL `live_feed.LIVE_FEED_EVENTS_TTL_DAYS` days).

The rule is the feed's, replayed — never a new counter (spec §1.6):
  * `live_feed._on_drop`: a drop opens the blind window only when the link was authed OR the drop is a kick, and only
    when no window is open yet (`not _link.get("drop_ts")`) — a second close before an auth never re-opens it;
  * `live_feed._on_auth`: the next auth closes it (gap = auth − first drop); an auth with no open window adds nothing;
  * a kick = `live_feed._is_kick` per drop: a `live_feed.KICK_STATUS` status earlier in this connection, the close
    code `live_feed.KICK_CLOSE_CODE`, or the status text in the close message. One kick per drop, never one per row.
Per market day (`market_hours.gate.closed_reason` is None) the window is `GC.PASS_OPEN_ET`–`GC.PASS_CLOSE_ET` (the
hub's `active()` window), clipped at `now` for today. A day with no timeline rows at all (persist disabled, or before
the collection existed) is "no rows" with `blind_pct` None — never 0 %.

Never writes (no index build, no file); never prints a row's message. Re-run inside the api container from stdin:

  docker exec -i -w /app -e PYTHONPATH=/app cheetah-market-app-api-1 python - --md < backend/scripts/live_feed_blind_fraction.py
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

import live_feed
from chart_maps.gajjala import constants as GC
from market_hours import gate as MH_GATE

ET = ZoneInfo("America/New_York")
SCRIPT = "backend/scripts/live_feed_blind_fraction.py"
NO_ROWS = "no rows"
MD_HEADER = "| day | kicks | blind s | blind % | p50 gap |"
_FIELDS = {"_id": 0, "ts": 1, "kind": 1, "status": 1, "close_code": 1, "message": 1}


# ── the feed's rule, replayed (pure) ──────────────────────────────────────────────────────────────────────────────
def _sorted(rows: Iterable[dict]) -> list:
    """Rows in `ts` order; a stable sort keeps the read order (Mongo `ts`, `_id`) for equal stamps."""
    return sorted((r for r in rows if r.get("ts") is not None), key=lambda r: float(r["ts"]))


def _close_is_kick(row: dict, kick_seen: bool) -> bool:
    """`live_feed._is_kick` on one close row."""
    return (bool(kick_seen) or row.get("close_code") == live_feed.KICK_CLOSE_CODE
            or live_feed.KICK_STATUS in (row.get("message") or "").lower())


def _walk(rows: Iterable[dict]) -> tuple:
    """(raw windows [(start, end | None)], kick stamps) over the whole timeline — the feed's state machine."""
    windows: list = []
    kick_ts: list = []
    authed = False
    kick_seen = False
    drop_ts: Optional[float] = None
    for r in _sorted(rows):
        ts = float(r["ts"])
        kind = r.get("kind")
        if kind == "connect":
            authed, kick_seen = False, False
        elif kind == "auth":
            if drop_ts is not None:
                windows.append((drop_ts, ts))
                drop_ts = None
            authed = True
        elif kind == "status":
            if r.get("status") == live_feed.KICK_STATUS:
                kick_seen = True
        elif kind == "close":
            kicked = _close_is_kick(r, kick_seen)
            if (authed or kicked) and drop_ts is None:
                drop_ts = ts
            if kicked:
                kick_ts.append(ts)
            authed, kick_seen = False, False
    if drop_ts is not None:
        windows.append((drop_ts, None))
    return windows, kick_ts


def blind_windows(rows: Iterable[dict], open_epoch: float, close_epoch: float) -> list:
    """Blind windows intersected with [open_epoch, close_epoch]; a window still open is clipped at close_epoch;
    zero-length windows after clipping are dropped."""
    out = []
    for start, end in _walk(rows)[0]:
        lo = max(float(start), float(open_epoch))
        hi = min(float(close_epoch) if end is None else float(end), float(close_epoch))
        if hi > lo:
            out.append((lo, hi))
    return out


def kicks(rows: Iterable[dict], open_epoch: Optional[float] = None, close_epoch: Optional[float] = None) -> int:
    """Kicks (one per kicked drop, = `live_feed._is_kick`) whose close falls in [open_epoch, close_epoch)."""
    lo = float("-inf") if open_epoch is None else float(open_epoch)
    hi = float("inf") if close_epoch is None else float(close_epoch)
    return sum(1 for t in _walk(rows)[1] if lo <= t < hi)


# ── per day / summary (pure) ──────────────────────────────────────────────────────────────────────────────────────
def _at(day: date, hhmm: str) -> float:
    t = datetime.strptime(hhmm, "%H:%M").time()
    return datetime.combine(day, t, tzinfo=ET).timestamp()


def day_window(day: date, now: Optional[float] = None) -> tuple:
    """(open, close) epochs of the hub window on `day`, close clipped at `now` when given."""
    lo = _at(day, GC.PASS_OPEN_ET)
    hi = _at(day, GC.PASS_CLOSE_ET)
    if now is not None:
        hi = min(hi, float(now))
    return lo, hi


def _pctl(vals: list, q: float) -> Optional[float]:
    v = live_feed._pctl(sorted(vals), q)
    return None if v is None else round(v, 1)


def day_row(rows: list, day: date, now: Optional[float] = None) -> dict:
    """One day: window, blind seconds, blind % (None when the day has no rows at all), kicks, gaps."""
    lo, hi = day_window(day, now)
    window_s = max(0.0, hi - lo)
    d0 = datetime.combine(day, datetime.min.time(), tzinfo=ET).timestamp()
    d1 = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=ET).timestamp()
    has_rows = any(d0 <= float(r["ts"]) < d1 for r in rows if r.get("ts") is not None)
    if not has_rows or window_s <= 0:
        return {"day": day.isoformat(), "window_s": round(window_s, 1), "blind_s": 0.0, "blind_pct": None,
                "kicks": 0, "gaps_s": [], "note": NO_ROWS if not has_rows else "window not open"}
    gaps = [b - a for a, b in blind_windows(rows, lo, hi)]
    blind = sum(gaps)
    return {"day": day.isoformat(), "window_s": round(window_s, 1), "blind_s": round(blind, 1),
            "blind_pct": round(100.0 * blind / window_s, 2), "kicks": kicks(rows, lo, hi),
            "gaps_s": [round(g, 1) for g in gaps], "note": None}


def build_days(rows: list, first: date, last: date, now: Optional[float] = None) -> list:
    """Every market day first..last (the house gate skips weekends / holidays)."""
    out = []
    d = first
    while d <= last:
        if MH_GATE.closed_reason(datetime(d.year, d.month, d.day, 12, tzinfo=ET)) is None:
            out.append(day_row(rows, d, now))
        d += timedelta(days=1)
    return out


def summarize(days: list) -> dict:
    """Over the days WITH rows only — a no-rows day is never a 0 % session."""
    seen = [d for d in days if d["blind_pct"] is not None]
    gaps = [g for d in seen for g in d["gaps_s"]]
    pcts = [d["blind_pct"] for d in seen]
    n = len(seen)
    return {"sessions": n,
            "blind_pct_mean": round(statistics.mean(pcts), 2) if n else None,
            "blind_pct_median": round(statistics.median(pcts), 2) if n else None,
            "kicks_per_session": round(sum(d["kicks"] for d in seen) / n, 1) if n else None,
            "gap_s_p50": _pctl(gaps, 50), "gap_s_p90": _pctl(gaps, 90)}


def render_md(days: list) -> str:
    def cell(v, suffix=""):
        return "—" if v is None else f"{v}{suffix}"
    lines = [MD_HEADER, "|---|---|---|---|---|"]
    for d in days:
        if d["blind_pct"] is None:
            lines.append(f"| {d['day']} | — | — | {d['note']} | — |")
        else:
            lines.append(f"| {d['day']} | {d['kicks']} | {d['blind_s']} | {d['blind_pct']} % | "
                         f"{cell(_pctl(d['gaps_s'], 50), ' s')} |")
    return "\n".join(lines)


# ── the one Mongo read ────────────────────────────────────────────────────────────────────────────────────────────
def _load_rows(now: float) -> list:
    """Rows from the last TTL days, `ts` order — the connection as `live_feed._events_coll` builds it, read-only."""
    from pymongo import MongoClient
    client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"), serverSelectionTimeoutMS=2000)
    coll = client[os.getenv("MONGO_DB", "cheetah")][live_feed.LIVE_FEED_EVENTS_COLL]
    since = datetime.fromtimestamp(now, tz=timezone.utc) - timedelta(days=live_feed.LIVE_FEED_EVENTS_TTL_DAYS)
    return list(coll.find({"at": {"$gte": since}}, _FIELDS).sort([("ts", 1), ("_id", 1)]))


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Blind fraction of the one Massive socket (read-only).")
    ap.add_argument("--md", action="store_true", help="also print the markdown table")
    args = ap.parse_args(argv)
    now = time.time()
    rows = _load_rows(now)
    today = datetime.fromtimestamp(now, tz=ET).date()
    first = (datetime.fromtimestamp(now, tz=ET) - timedelta(days=live_feed.LIVE_FEED_EVENTS_TTL_DAYS)).date()
    days = build_days(rows, first, today, now)
    print(json.dumps({"rows": len(rows), "days": days, "summary": summarize(days)}, indent=1))
    if args.md:
        print()
        print(render_md(days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
