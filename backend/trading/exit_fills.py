"""Engine-sell fills — the ONE matcher (2026-10-27, BUILD_SPEC28 §3.13). ACCOUNTING ONLY.

Ajay 2026-10-27: "Anyway you can can show me which tab made money or not?"

The exit engine sells at market through its force exits (distribution_exit / watchdog_exit, the 🔥 lane's
hot_pullback_exit) and fill-less flattens, and none of those ledger rows carries the broker's fill — so the
journal kept 11 sold round trips "open" forever. This module reads the broker's OWN terminal orders for the
symbol (`closed_orders_for`, read-only) and books ONE `exit_fill` ledger row at the broker's fill price, qty and
time, so trading/journal.py closes the round trip.

Why `exit_fill` and not `trade_closed`: trade_closed is an ENGINE INPUT (entries._closed_trade_stats, the p.299
half-average-gain stop rule; progressive.last_gains, pilot sizing). exit_fill reaches only the journal.

Runs (a) in the minute tick, step (e2), over the decisions inside FLATTEN_SENT_LOOKBACK_DAYS, and (b) as a
one-shot, idempotent back-fill CLI (dry run first):

    python -m trading.exit_fills backfill --dry-run | --live
    python -m trading.exit_fills rollback --dry-run | --live

NEVER: places, cancels or replaces an order, sells a position, sends a push, or writes anything but
`EE.ledger(...)` and the single scoped delete in `rollback()`. The broker comes in as an argument; this module
imports no broker implementation. No fill found -> nothing is booked (never an estimate).
"""
from __future__ import annotations

import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from trading import exit_engine as EE
from trading import journal as JN

log = logging.getLogger("trading.exit_fills")

SOURCE_LIVE = "broker_fill"
SOURCE_BACKFILL = "broker_fill_backfill"
CITE = "broker fill of the engine's market sell (accounting only)"

_BOOKED_KINDS = ("trade_closed", "exit_fill")
_ROLLBACK_FILTER = {"kind": "exit_fill", "detail.source": SOURCE_BACKFILL}
_FRAC = re.compile(r"(\.\d{6})\d+")


def _out(**kw) -> dict:
    out = {"candidates": 0, "written": [], "would_write": [], "no_fill": [], "still_held": [],
           "skipped_queue": [], "partial": [], "overfill": [], "skipped": None, "errors": []}
    out.update(kw)
    return out


def _f(v) -> Optional[float]:
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def _q(v) -> int:
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


def _parse_iso(ts) -> Optional[datetime]:
    """An aware UTC datetime from a broker / ledger ISO string (Z, offsets, >6 fraction digits); None on failure.
    A naive string is read as ET (the journal's convention for the 🔥 lane's rows)."""
    if not isinstance(ts, str) or not ts.strip():
        return None
    try:
        dt = datetime.fromisoformat(_FRAC.sub(r"\1", ts.strip()).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JN._ET)
    return dt.astimezone(timezone.utc)


def _row_epoch(r: dict) -> float:
    """The row's epoch; a row written without one (the 🔥 lane's own _ledger) gets it from its ts, as
    journal._ledger_rows does."""
    e = JN._epoch(r)
    if e:
        return e
    dt = _parse_iso(r.get("ts"))
    return dt.timestamp() if dt is not None else 0.0


def _booked_order_ids(db) -> set:
    ids = set()
    for r in db.trade_ledger.find({"kind": {"$in": list(_BOOKED_KINDS)}}):
        det = r.get("detail") if isinstance(r.get("detail"), dict) else {}
        if det.get("order_id"):
            ids.add(str(det["order_id"]))
        for oid in det.get("order_ids") or []:
            if oid:
                ids.add(str(oid))
    return ids


def _stock_symbols(positions) -> set:
    return {(p.get("symbol") or "").upper() for p in (positions or [])
            if isinstance(p, dict) and (p.get("asset_class") or "") != "us_option" and p.get("symbol")}


def book(brk, *, held_symbols: Optional[set] = None, skip_symbols: Optional[set] = None,
         lookback_days: Optional[float] = None, source: str = SOURCE_LIVE, dry_run: bool = False,
         now: Optional[float] = None) -> dict:
    """Book the broker's fill of every engine market sell the journal still lists as unbooked
    (journal.unbooked_exits). Returns {candidates, written, would_write, no_fill, still_held, skipped_queue,
    partial, overfill, skipped, errors}. Reads the broker; writes ONLY exit_fill ledger rows (none when
    dry_run)."""
    db = EE._db()
    if db is None:
        return _out(candidates=0, skipped="no ledger")
    now = time.time() if now is None else float(now)
    cutoff = None
    if lookback_days is not None:
        cutoff = now - float(lookback_days) * 86400.0
        kinds = list(JN.FORCE_EXIT_KINDS + JN.FILLLESS_EXIT_KINDS)
        recent = [r for r in db.trade_ledger.find({"kind": {"$in": kinds}})
                  if r.get("dry_run") is not True and _row_epoch(r) >= cutoff]
        if not recent:
            return _out(candidates=0)
    reader = getattr(brk, "closed_orders_for", None)
    if not callable(reader):
        return _out(skipped="broker has no closed_orders_for")
    cands = JN.unbooked_exits()
    if cutoff is not None:
        cands = [c for c in cands if (_f(c.get("epoch")) or 0.0) >= cutoff]
    out = _out(candidates=len(cands))
    if held_symbols is None:
        try:
            held = _stock_symbols(brk.positions())
        except Exception as exc:                   # noqa: BLE001 — BrokerError text is pre-scrubbed
            out["errors"].append("positions unavailable: %s" % exc)
            return out
    else:
        held = {str(s).upper() for s in held_symbols}
    skip = {str(s).upper() for s in (skip_symbols or set())}
    booked_ids = _booked_order_ids(db)

    for c in cands:
        sym = (c.get("symbol") or "").upper()
        if sym in skip:
            out["skipped_queue"].append(sym)
            continue
        if sym in held:
            out["still_held"].append(sym)
            continue
        try:
            orders = reader(sym, after_iso=c.get("entry_ts"), until_iso=c.get("window_end_ts")) or []
        except Exception as exc:                   # noqa: BLE001 — BrokerError text is pre-scrubbed
            out["errors"].append("%s: %s" % (sym, exc))
            continue
        sells = [o for o in orders if isinstance(o, dict)
                 and (o.get("side") or "").lower() == "sell"
                 and (_f(o.get("filled_qty")) or 0.0) > 0
                 and _f(o.get("filled_avg_price")) is not None
                 and str(o.get("id")) not in booked_ids
                 and (o.get("symbol") or "").upper() == sym]
        sells.sort(key=lambda o: str(o.get("filled_at") or ""))
        if not sells:
            out["no_fill"].append(sym)
            continue
        caps = [x for x in (_q(c.get("entry_qty")), _q(c.get("held_qty"))) if x]
        cap = min(caps) if caps else None
        used, takes, taken = [], [], 0.0
        for o in sells:
            fq = _f(o.get("filled_qty")) or 0.0
            take = fq if cap is None else min(fq, cap - taken)
            if take <= 0:
                break
            used.append(o)
            takes.append(take)
            taken += take
            if cap is not None and taken >= cap:
                break
        sold = sum(takes)
        total_filled = sum(_f(o.get("filled_qty")) or 0.0 for o in sells)
        overfill = (total_filled - sold) if cap is not None else 0
        fill = round(sum(t * _f(o.get("filled_avg_price")) for t, o in zip(takes, used)) / sold, 4)
        entry = _f(c.get("entry_price"))
        gain_pct = round((fill / entry - 1) * 100, 2) if entry else None
        partial = cap is not None and sold < cap
        sold_n = int(sold) if float(sold).is_integer() else sold
        over_n = int(overfill) if float(overfill).is_integer() else overfill
        detail = {"leg": "force_exit" if c.get("kind") in JN.FORCE_EXIT_KINDS else "flatten",
                  "source_kind": c.get("kind"), "source": source,
                  "trade_id": c.get("trade_id"), "strategy": c.get("lane"),
                  "order_id": used[0].get("id"), "order_ids": [o.get("id") for o in used],
                  "fill": fill, "qty": sold_n, "entry": c.get("entry_price"), "gain_pct": gain_pct,
                  "decision_ts": c.get("ts"), "decision_last": c.get("last"), "held_qty": c.get("held_qty"),
                  "reason": c.get("reason"), "filled_at": used[-1].get("filled_at"),
                  "partial": partial, "overfill_qty": over_n or 0, "est": False}
        if source == SOURCE_BACKFILL:
            detail["backfilled_at"] = EE._utc_iso()
        rec = {"symbol": sym, "lane": c.get("lane"), "trade_id": c.get("trade_id"), "qty": sold_n,
               "fill": fill, "entry": c.get("entry_price"),
               "realized": round(sold * (fill - entry), 2) if entry is not None else None,
               "orders": len(used)}
        if partial:
            out["partial"].append(sym)
        if overfill:
            out["overfill"].append(sym)
        if dry_run:
            out["would_write"].append(rec)
        else:
            EE.ledger(JN.EXIT_FILL_KIND, symbol=sym, detail=detail, dry_run=False, cite=CITE,
                      at=_parse_iso(used[-1].get("filled_at")))
            out["written"].append(rec)
        booked_ids.update(str(o.get("id")) for o in used)
    return out


def rollback(dry_run: bool = True) -> dict:
    """Remove ONLY the back-filled exit_fill rows (detail.source == SOURCE_BACKFILL), then reconcile the journal.
    A live-source exit_fill and every other ledger kind are untouched."""
    db = EE._db()
    if db is None:
        return {"rows": 0, "deleted": 0}
    n = len(list(db.trade_ledger.find(dict(_ROLLBACK_FILTER))))
    if dry_run or not n:
        return {"rows": n, "deleted": 0}
    db.trade_ledger.delete_many({"kind": "exit_fill", "detail.source": SOURCE_BACKFILL})
    JN.reconcile()
    return {"rows": n, "deleted": n}


def _queue_symbols() -> set:
    try:
        return {(e.get("symbol") or "").upper() for e in EE.get_config().get("flatten_queue") or []}
    except Exception as exc:                       # noqa: BLE001
        log.warning("exit_fills: flatten queue unreadable: %s", exc)
        return set()


def _cand_line(c: dict, outcome: str) -> str:
    return "%-6s %-13s entry %s %s @ %s · %s %s · %s" % (
        c.get("symbol"), c.get("lane"), JN._et_day_of(c.get("entry_ts")), c.get("entry_qty"),
        c.get("entry_price"), c.get("kind"), JN._et_day_of(c.get("ts")), outcome)


def _counts(res: dict) -> dict:
    out = dict(res)
    out["written"] = len(res.get("written") or [])
    out["would_write"] = len(res.get("would_write") or [])
    return out


def _main(argv) -> int:
    args = list(argv or [])
    if len(args) != 2 or args[0] not in ("backfill", "rollback") or args[1] not in ("--dry-run", "--live"):
        print("usage: python -m trading.exit_fills backfill --dry-run | --live ; rollback --dry-run | --live")
        return 2
    live = args[1] == "--live"
    if args[0] == "rollback":
        res = rollback(dry_run=not live)
        print("exit_fills rollback — %s" % ("LIVE" if live else "DRY RUN (nothing deleted)"))
        print(json.dumps(res, sort_keys=True))
        return 0
    print("exit_fills backfill — %s" % ("LIVE" if live else "DRY RUN (nothing written)"))
    try:
        cands = JN.unbooked_exits()
    except Exception as exc:                       # noqa: BLE001
        log.warning("exit_fills: candidates unreadable: %s", exc)
        cands = []
    res = book(EE.broker, skip_symbols=_queue_symbols(), source=SOURCE_BACKFILL, dry_run=not live)
    recs = {r.get("trade_id"): r for r in (res.get("written") or []) + (res.get("would_write") or [])}
    for c in cands:
        sym = (c.get("symbol") or "").upper()
        r = recs.get(c.get("trade_id"))
        if r is not None:
            outcome = "%d sold @ %s (%d order%s) · realized %s %s" % (
                int(r["qty"]), r["fill"], r["orders"], "" if r["orders"] == 1 else "s",
                JN._usd(r["realized"]) if r["realized"] is not None else "?",
                "WRITTEN" if live else "WOULD WRITE")
        elif sym in (res.get("still_held") or []):
            outcome = "STILL HELD — skipped"
        elif sym in (res.get("skipped_queue") or []):
            outcome = "IN FLATTEN QUEUE — skipped"
        else:
            outcome = "NO FILL FOUND — left open"
        print(_cand_line(c, outcome))
    if live:
        JN.reconcile()
        for key, row in sorted((JN.summary().get("by_strategy") or {}).items()):
            print("%-13s closed %s · open %s · realized %s · unbooked %s" % (
                key, row.get("closed"), row.get("open"), row.get("realized_pnl"), row.get("unbooked")))
    print(json.dumps(_counts(res), sort_keys=True))
    return 1 if res.get("errors") else 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
