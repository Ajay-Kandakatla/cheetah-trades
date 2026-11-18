"""🧨 Divergence record — backfill of sessions the pass hook never saw (spec diverg2 §3.9, WP-D, 2026-11-18).

BUILT, NOT RUN: running it is HIS CALL #6 (the OOS sessions before deploy, 2026-11-17 and 2026-11-18; the ask day
2026-11-16 only on his word — its own block, never a criterion). The stored 5-min reads live 14 days (READS_TTL_DAYS):
a session is only backfillable before its reads expire.

Per session, read-only on every provider (no bar loader, no Massive, no network — Mongo reads + the engine):
  1. units      = divergence.units_today(store, session)  — the study's cohort from the 🏁 ledger rows (🚩 A+ + 🧠
                  pushes with a plan; clock = the first ring, 04:00 ET for yesterday's after-close ring);
  2. series     = divergence.from_tile(gajjala_reads doc)  — tile.bars5_prior (the prior session's tail) + bars5, with
                  the pass's OWN 9 / 21 EMA curves (curves5_prior + curves5) — the values the card drew, exact;
  3. listing    = divergence.detect(series, ring clock, session)  — the ONE engine (RTH first, then after hours);
  4. trade      = divergence.trade(...) on the same series — entry next 5-min open, exit X3, net of the study's costs.
Prints one table row per unit. Writes ONLY with --write: `upsert_divergence` with source "backfill", and ONLY for a
record id the store does not hold — an existing doc (the pass's, the nightly's, an earlier backfill's) is never touched.
The nightly grade (20:15 ET) then grades the written docs from the full-day frame, as it grades every record.

Honesty guards — a REFUSED session writes nothing and prints why:
  * session_open        the session's extended close + BAR_SETTLE_SEC has not passed (its reads are not final);
  * ledger_unreadable   units_today raised (a ledger read fault is never "no units");
  * record_unreadable   the divergence record could not be read (never-overwrite cannot be guaranteed);
  * reads_missing       a unit has no gajjala_reads doc (the gap is printed, symbol by symbol);
  * prior_short         a unit's tile.bars5_prior holds fewer than DIVERGENCE_ATR_PERIOD + 1 bars (no ATR warm);
  * tile_unreadable     from_tile could not read the stored tile.
No aggregate is printed: totals over OOS-session rows stay sealed until GC.DIVERGENCE_OOS_SEAL_ET (OOS_SPEC.md:7).

  docker exec -i -w /app <container> python -m scripts.gajjala_divergence_backfill --sessions 2026-11-17,2026-11-18
  docker exec -i -w /app <container> python -m scripts.gajjala_divergence_backfill --sessions 2026-11-17,2026-11-18 --write

Exit codes: 0 every session ok · 1 a write failed · 2 a session refused (or bad arguments).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SOURCE = "backfill"
EXIT_OK, EXIT_WRITE_FAILED, EXIT_REFUSED = 0, 1, 2
REFUSALS = ("session_open", "ledger_unreadable", "record_unreadable", "reads_missing", "prior_short", "tile_unreadable")
STATUSES = ("new", "exists", "no_listing")


def _engine():
    from chart_maps.gajjala import constants as GC
    from chart_maps.gajjala import divergence as DV
    return GC, DV


def _iso(session) -> str:
    return session.isoformat() if isinstance(session, (date, datetime)) else str(session)[:10]


def parse_sessions(raw: str) -> list:
    """'2026-11-17,2026-11-18' → [date, date], de-duplicated, in the order given; ValueError on a bad date."""
    out: list = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        d = date.fromisoformat(part)
        if d not in out:
            out.append(d)
    if not out:
        raise ValueError("no session given")
    return out


def session_closed(session: date, now: datetime) -> bool:
    """True once the session's extended close (half days per alerts._closes) + GC.BAR_SETTLE_SEC has passed."""
    from chart_maps.gajjala import alerts as AL
    GC, _DV = _engine()
    _rth, ext = AL._closes(session)
    end = datetime.combine(session, ext, tzinfo=ET) + timedelta(seconds=GC.BAR_SETTLE_SEC)
    return now >= end


def _prior_len(doc: dict) -> Optional[int]:
    tile = (doc or {}).get("tile")
    prior = tile.get("bars5_prior") if isinstance(tile, dict) else None
    return len(prior) if isinstance(prior, list) else None


def _half_day(session: date) -> bool:
    from chart_maps.gajjala import alerts as AL
    from daytrading.data import ET_RTH_CLOSE
    return AL._closes(session)[0] != ET_RTH_CLOSE


def _refused(out: dict, reason: str, gaps: Optional[dict] = None) -> dict:
    out.update(status="refused", reason=reason, gaps=gaps or {}, rows=[])
    return out


def plan_session(store, session: date, now: datetime) -> dict:
    """{session, status ok|refused, reason, gaps, units, rows} — reads only. Each row: {id, symbol, ring, status
    new|exists|no_listing, window, alert, trade, live}. A refused session carries NO rows (nothing half-read)."""
    GC, DV = _engine()
    iso = _iso(session)
    out: dict = {"session": iso, "status": "ok", "reason": None, "gaps": {}, "units": 0, "rows": []}
    if not session_closed(session, now):
        return _refused(out, "session_open")
    try:
        units = DV.units_today(store, session)
    except Exception as exc:                                    # noqa: BLE001 — a fault is never "no units"
        return _refused(out, "ledger_unreadable", {"error": type(exc).__name__})
    out["units"] = len(units)
    existing = store.divergence_docs([session])
    if existing is None:
        return _refused(out, "record_unreadable")
    have = {d.get("_id") for d in existing} | {DV.record_id(iso, str(d.get("symbol") or "").upper())
                                               for d in existing if d.get("symbol")}
    need = GC.DIVERGENCE_ATR_PERIOD + 1
    missing, short, bad, series = [], [], [], {}
    for sym in sorted(units):
        doc = store.get_read(session, sym)
        if not doc:
            missing.append(sym)
            continue
        n = _prior_len(doc)
        if n is not None and n < need:
            short.append({"symbol": sym, "prior_bars": n, "need": need})
            continue
        try:
            b = DV.from_tile(doc, iso) if n is not None else None
        except Exception:                                       # noqa: BLE001 — a malformed tile is refused, never guessed
            b = None
        if b is None:
            bad.append(sym)
            continue
        series[sym] = b
    if missing:
        return _refused(out, "reads_missing", {"reads_missing": missing, "prior_short": short, "tile_unreadable": bad})
    if short:
        return _refused(out, "prior_short", {"prior_short": short, "tile_unreadable": bad})
    if bad:
        return _refused(out, "tile_unreadable", {"tile_unreadable": bad})
    for sym, b in series.items():
        unit = units[sym]
        rid = DV.record_id(iso, sym)
        row = {"id": rid, "symbol": sym, "ring": unit, "status": "no_listing", "window": None, "alert": None,
               "trade": None, "live": None}
        det = DV.detect(b, unit["clock"], session)
        if det is not None:
            window = det["window"]
            hm, _utc = DV.horizon_of(session, window)
            row.update(status="exists" if rid in have else "new", window=window,
                       alert={k: v for k, v in det.items() if k != "window"},
                       trade=DV.trade(b, det["i"], window, hm), live=DV.live_state(b, det["i"], window, hm))
        out["rows"].append(row)
    return out


def write_session(store, plan: dict, now: datetime) -> dict:
    """$setOnInsert of every `new` row (source "backfill"); an `exists` row is never written. → {written, skipped,
    failed}. A refused plan writes nothing."""
    res = {"written": 0, "skipped": 0, "failed": 0}
    if plan.get("status") != "ok":
        return res
    session = date.fromisoformat(plan["session"])
    half = _half_day(session)
    for row in plan["rows"]:
        if row["status"] == "exists":
            res["skipped"] += 1
            continue
        if row["status"] != "new":
            continue
        ins = {"date": plan["session"], "symbol": row["symbol"], "window": row["window"], "alert": row["alert"],
               "ring": row["ring"], "recorded_at": now, "source": SOURCE, "half_day": half, "live": row["live"]}
        ok = store.upsert_divergence(row["id"], ins, {"at": now})
        res["written" if ok else "failed"] += 1
    return res


# ── printing ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _num(x, fmt: str) -> str:
    from chart_maps.gajjala.ema_cross import finite
    return format(float(x), fmt) if finite(x) else "—"


def _hm(t) -> str:
    return str(t)[11:16] if isinstance(t, str) and len(t) >= 16 else "—"


HEADS = ("Ticker", "Rang", "Window", "Listed", "Gap ATRs", "Entry", "Exit", "Exit why", "Net %", "Outcome", "Record")


def row_cells(row: dict) -> tuple:
    ring = row.get("ring") or {}
    rang = f"{ring.get('kind') or '—'} {ring.get('at_et') or ''}".strip()
    if row["status"] == "no_listing":
        return (row["symbol"], rang, "—", "—", "—", "—", "—", "—", "—", "no listing", "—")
    al, tr = row.get("alert") or {}, row.get("trade") or {}
    entry, ex = tr.get("entry") or {}, tr.get("exit") or {}
    return (row["symbol"], rang, row.get("window") or "—", _hm(al.get("bar_t")), _num(al.get("r1"), ".2f"),
            f"{_num(entry.get('px'), '.4g')} {_hm(entry.get('t'))}" if entry else "no print",
            f"{_num(ex.get('px'), '.4g')} {_hm(ex.get('t'))}" if ex else "—", ex.get("reason") or "—",
            _num(tr.get("net_pct"), "+.2f"), tr.get("outcome") or "—", row["status"])


def render(plan: dict) -> str:
    GC, _DV = _engine()
    lines = [f"🧨 {plan['session']} · units {plan['units']} · {plan['status']}"
             + (f" ({plan['reason']})" if plan.get("reason") else "")]
    if plan["status"] != "ok":
        for k, v in (plan.get("gaps") or {}).items():
            if v:
                lines.append(f"  refused — {k}: {json.dumps(v, default=str)}")
        lines.append("  nothing read further, nothing written for this session")
        return "\n".join(lines)
    cells = [HEADS] + [row_cells(r) for r in plan["rows"]]
    widths = [max(len(str(c[k])) for c in cells) for k in range(len(HEADS))]
    for c in cells:
        lines.append("  " + "  ".join(str(v).ljust(w) for v, w in zip(c, widths)))
    n_list = sum(1 for r in plan["rows"] if r["status"] != "no_listing")
    lines.append(f"  {n_list} listing(s) of {len(plan['rows'])} unit(s) · per-listing only — totals over OOS sessions "
                 f"stay sealed until {GC.DIVERGENCE_OOS_SEAL_ET} ET")
    return "\n".join(lines)


def main(argv=None, *, store=None, now: Optional[datetime] = None) -> int:
    ap = argparse.ArgumentParser(prog="gajjala_divergence_backfill", description=__doc__.split("\n")[0])
    ap.add_argument("--sessions", required=True, help="comma-separated ISO dates, e.g. 2026-11-17,2026-11-18")
    ap.add_argument("--write", action="store_true", help="upsert the NEW records (source backfill); default: print only")
    ap.add_argument("--json", action="store_true", help="print the plan as JSON instead of the table")
    a = ap.parse_args(argv)
    try:
        sessions = parse_sessions(a.sessions)
    except ValueError as exc:
        print(f"bad --sessions: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    now = now or datetime.now(timezone.utc)
    if store is None:
        from chart_maps.gajjala import store as ST
        store = ST.default()
    code = EXIT_OK
    plans = []
    for s in sessions:
        plan = plan_session(store, s, now)
        if plan["status"] != "ok":
            code = max(code, EXIT_REFUSED)
        plan["write"] = write_session(store, plan, now) if a.write else None
        if plan["write"] and plan["write"]["failed"] and code == EXIT_OK:
            code = EXIT_WRITE_FAILED
        plans.append(plan)
        if not a.json:
            print(render(plan))
            if a.write and plan["status"] == "ok":
                w = plan["write"]
                print(f"  --write: {w['written']} written · {w['skipped']} already on file (untouched) · {w['failed']} failed")
    if a.json:
        print(json.dumps(plans, default=str, indent=1))
    elif not a.write:
        print("dry run — nothing written (pass --write to record the new listings)")
    return code


if __name__ == "__main__":
    sys.exit(main())
