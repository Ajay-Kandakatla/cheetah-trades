"""Auto-Pilot trade JOURNAL — a derived, read-only round-trip view of the
trade_ledger (the raw event log written by exit_engine.ledger()).

This module adds NO trading side effects. It only READS the ledger and writes
a derived, perpetual `trade_journal` Mongo collection (one doc per round-trip).
The journal is KEPT FOREVER — no TTL, no deletes — the same rule as the
pattern-accuracy ledger; a trade history is the raw material every analytic in
analytics.py reports on (Minervini's "mortality tables of your gains", TLSW
p.298), and pruning it would quietly corrupt the batting average / expectancy.

How a round-trip is reconstructed (the ledger is already the event log):
  * "entry" rows (trading/entries.py) carry the entry + its full plan
    (price, qty, stop, target, reward_risk, breakeven_trigger, regime, ...).
    The deterministic client_order_id (cheetah-{SYM}-{etday}-entry) enforces
    at most ONE same-symbol entry per ET day, so pairing each "entry" row with
    the NEXT "trade_closed"/"flatten"/"flatten_all" row for that symbol in
    time order is reliable.
  * "auto_entry" rows (trading/auto_entry.py) fire right before the entry on
    auto buys and carry the funnel decision (path, pivot, relvol, score,
    cleared_at_frac). Matched to the entry by symbol + same ET day to enrich
    trigger context; manual entries have no such row -> trigger=null.
  * "ratchet_breakeven" rows (exit_engine, p.308) between an entry and its
    exit mean the trade reached +3R and the stop was raised to breakeven.
  * "trade_closed" rows (exit_engine, p.299) carry the realized gain_pct and
    the exit leg (stop|take_profit). "flatten"/"flatten_all" rows are manual
    exits — they also close a trade (leg "flatten").
  * The entry row's detail.strategy / detail.entry_reason (entries.enter,
    2026-09-05 — Ajay: "journal it appropriately") name the LANE that bought:
    minervini | demand_zone | breakout | catalyst | manual. Older rows carry
    no tag: a trigger row infers minervini, everything else is manual, and
    entry_reason is null. summary() splits the book per lane (by_strategy).

Import-light: no pandas/numpy anywhere here. The Mongo handle, ledger reader
and config all come from exit_engine via lazy module-level imports of pure
helpers (no sepa import chain pulled in).

Page cites trace to backend/sepa/minervini.pdf (printed page = PDF page - 15).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from trading.exit_engine import _db, _utc_iso

log = logging.getLogger("trading.journal")

JOURNAL_CITE = ("journal: round-trips reconstructed from trade_ledger; entry "
                "plan p.299/301/311; breakeven ratchet p.308; realized gain "
                "p.299")

# Ledger kinds that CLOSE an open entry (in time order, next-after-entry).
_EXIT_KINDS = ("trade_closed", "flatten", "flatten_all")


def _is_exit_row(r: dict) -> bool:
    """A ledger row that actually closed the trade. A "flatten" row whose
    close Alpaca REFUSED (detail.closed False — shares held for pending-cancel
    orders, 2026-09-05) or that only QUEUED the exit is not an exit: the
    trade stays open until the drained sell's trade_closed row lands."""
    if r.get("kind") not in _EXIT_KINDS:
        return False
    det = r.get("detail") or {}
    if r.get("kind") == "flatten":
        if det.get("closed") is False or det.get("queued") is True:
            return False
    return True


def _has_fill(r: dict) -> bool:
    det = r.get("detail") or {}
    return any(det.get(k) is not None for k in ("fill", "price", "exit_price"))

# Journal lane tags (mirror of trading/entries.STRATEGIES — kept literal so
# this import-light module never pulls entries -> broker at import time).
STRATEGIES = ("minervini", "demand_zone", "breakout", "catalyst", "manual")

# Per ET trading day ~6.5h; holding_days counts CALENDAR days between entry and
# exit (weekends/holidays included) — a plain wall-clock read, labelled clearly.
_SECONDS_PER_DAY = 86400.0


# ── Ledger reads ────────────────────────────────────────────────────────────

def _ledger_rows() -> list:
    """Every non-dry-run ledger row, oldest-first. dry_run rows are the
    "would have" narrations of a disarmed engine and never represent a real
    fill, so they are excluded from the round-trip reconstruction."""
    db = _db()
    if db is None:
        return []
    try:
        cur = (db.trade_ledger
               .find({"dry_run": {"$ne": True}})
               .sort("epoch", 1))
        rows = []
        for d in cur:
            d.pop("_id", None)
            rows.append(d)
        return rows
    except Exception as exc:                       # noqa: BLE001
        log.warning("journal: ledger read failed: %s", exc)
        return []


_ET = ZoneInfo("America/New_York")


def _et_day_of(ts) -> str:
    """ET calendar day of a ledger row's UTC ISO stamp ('2026-09-04T13:32:15Z'
    -> '2026-09-04'); falls back to the first ten characters."""
    try:
        t = str(ts or "")
        dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        return dt.astimezone(_ET).date().isoformat()
    except Exception:                              # noqa: BLE001
        return str(ts or "")[:10]


def _zone_lanes() -> dict:
    """{(SYMBOL, ET day): 'breakout' | 'demand_zone'} from every
    zone_edge_entry_state doc that actually placed an order (order_ts set).
    Lane fallback for entry rows written BEFORE 2026-09-05, when
    entries.enter did not yet stamp detail.strategy — the four zone-edge paper
    buys of 2026-09-04 (APLD, ATI, LUNR, AEIS) read as 'manual' on the
    Journal-by-strategy card otherwise. Read-only; {} when the coll is
    absent (tests) or unreadable."""
    db = _db()
    coll = getattr(db, "zone_edge_entry_state", None) if db is not None else None
    if coll is None:
        return {}
    out: dict = {}
    try:
        for st in coll.find({}):
            if not st.get("order_ts"):
                continue
            sym = str(st.get("symbol") or "").upper()
            day = str(st.get("date") or "")[:10]
            if not sym or not day:
                continue
            out[(sym, day)] = "breakout" if str(st.get("side") or "") == "supply" else "demand_zone"
    except Exception as exc:                       # noqa: BLE001
        log.warning("journal: zone lane read failed: %s", exc)
        return {}
    return out


def _journal_coll():
    db = _db()
    return None if db is None else db.trade_journal


# ── Round-trip reconstruction ───────────────────────────────────────────────

def _epoch(row: dict) -> float:
    try:
        return float(row.get("epoch") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _trade_id(symbol: str, entry_epoch: float) -> str:
    return "%s-%s" % (symbol, int(round(entry_epoch)))


def _entry_doc(entry_row: dict, trigger_row: Optional[dict],
               ratcheted: bool, exit_row: Optional[dict],
               zone_lane: Optional[str] = None) -> dict:
    """Build one round-trip journal doc from the paired ledger rows."""
    det = entry_row.get("detail") or {}
    sym = (entry_row.get("symbol") or "").upper()
    entry_epoch = _epoch(entry_row)

    def _f(key):
        v = det.get(key)
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    price = _f("price")
    qty = det.get("qty")
    try:
        qty = int(qty) if qty is not None else None
    except (TypeError, ValueError):
        qty = None
    stop_pct = _f("stop_pct")
    mode = _entry_mode(det)

    trigger = None
    if trigger_row is not None:
        tdet = trigger_row.get("detail") or {}
        trigger = {
            "path": tdet.get("path"),
            "pivot": tdet.get("pivot"),
            "relvol": tdet.get("relvol"),
            "score": tdet.get("score"),
            "cleared_at_frac": tdet.get("cleared_at_frac"),
        }

    # Lane tag: the explicit tag wins; an untagged row with an auto_entry
    # trigger is the Minervini funnel (pre-2026-09-05 rows); else manual.
    tag = det.get("strategy")
    if tag not in STRATEGIES:
        # Untagged (pre-2026-09-05): a zone-edge state doc that ordered on the
        # same ET day names the lane; else an auto_entry trigger = Minervini;
        # else manual.
        tag = zone_lane or ("minervini" if (trigger and trigger.get("path")) else "manual")
    entry_reason = det.get("entry_reason")
    if not isinstance(entry_reason, dict):
        entry_reason = None

    entry = {
        "ts": entry_row.get("ts"),
        "epoch": entry_epoch,
        "strategy": tag,
        "entry_reason": entry_reason,
        "price": price,
        "qty": qty,
        "stop_price": _f("stop_price"),
        "stop_pct": stop_pct,
        "target_price": _f("target_price"),
        "target_pct": _f("target_pct"),
        "reward_risk": _f("reward_risk"),
        "breakeven_trigger": _f("breakeven_trigger"),
        "regime": det.get("regime"),
        "size_multiplier": _f("size_multiplier"),
        "mode": mode,
        "trigger": trigger,
    }

    doc = {
        "trade_id": _trade_id(sym, entry_epoch),
        "symbol": sym,
        "status": "open" if exit_row is None else "closed",
        "entry": entry,
        "protected_to_breakeven": bool(ratcheted),
        "exit": None,
        "realized": None,
        "cites": ["p.299", "p.301", "p.308", "p.311"],
    }

    if exit_row is not None:
        doc["exit"], doc["realized"] = _exit_and_realized(
            entry, exit_row, price, qty, stop_pct)

    doc["narrative"] = narrate(doc)
    return doc


def _entry_mode(det: dict) -> Optional[str]:
    """Derive sim/paper/live from the entry detail when possible. The entry
    row does not store the broker mode directly, so this stays best-effort:
    an explicit detail['mode'] wins; otherwise None (the API/status layer
    knows the ACTIVE broker mode and can fill it in for display)."""
    m = det.get("mode")
    return str(m) if m else None


def _exit_and_realized(entry: dict, exit_row: dict, entry_price,
                       qty, stop_pct):
    """Build the exit + realized sub-docs from the closing ledger row.

    gain_pct comes straight from the trade_closed row (exit_engine computed it
    at fill time, p.299). For a manual flatten the ledger row carries no fill
    price/gain, so we derive what we can and leave the rest null rather than
    invent numbers."""
    det = exit_row.get("detail") or {}
    kind = exit_row.get("kind")
    leg = det.get("leg")
    if leg not in ("stop", "take_profit", "sim_handover"):
        leg = "flatten"

    exit_price = None
    for key in ("fill", "price", "exit_price"):
        v = det.get(key)
        if v is not None:
            try:
                exit_price = float(v)
                break
            except (TypeError, ValueError):
                pass

    gain_pct = det.get("gain_pct")
    try:
        gain_pct = float(gain_pct) if gain_pct is not None else None
    except (TypeError, ValueError):
        gain_pct = None
    if (gain_pct is None and exit_price is not None
            and entry_price not in (None, 0)):
        gain_pct = round((exit_price / entry_price - 1) * 100, 2)

    gain_dollars = None
    if (exit_price is not None and entry_price is not None
            and qty is not None):
        gain_dollars = round(qty * (exit_price - entry_price), 2)

    r_multiple = None
    if gain_pct is not None and stop_pct not in (None, 0):
        r_multiple = round(gain_pct / stop_pct, 2)

    holding_days = None
    ee, xe = entry.get("epoch"), _epoch(exit_row)
    if ee and xe and xe >= ee:
        holding_days = round((xe - ee) / _SECONDS_PER_DAY, 2)

    exit_reason = {"stop": "stopped out", "take_profit": "take-profit",
                   "flatten": "manual flatten",
                   "sim_handover": "SIM paper handover"}.get(leg, leg)
    if kind == "flatten_all":
        exit_reason = "flatten-all (disaster plan)"
    elif leg == "flatten" and det.get("reason"):
        # Owner-typed reason (flatten queue, 2026-09-05) rides along so the
        # journal says WHY, not just "manual flatten".
        exit_reason = ("manual flatten, %s" % str(det["reason"]).strip())[:160]

    exit_doc = {
        "ts": exit_row.get("ts"),
        "epoch": xe,
        "price": exit_price,
        "leg": leg,
    }
    realized = {
        "gain_pct": gain_pct,
        "gain_dollars": gain_dollars,
        "r_multiple": r_multiple,
        "holding_days": holding_days,
        "exit_reason": exit_reason,
    }
    return exit_doc, realized


def _build_docs(rows: list, zone_lanes: Optional[dict] = None) -> list:
    """Reconstruct every round-trip from the ordered ledger rows.

    One pass, time-ordered: for each "entry" row, find the matching
    auto_entry trigger (same symbol + same ET day, the immediately-preceding
    auto_entry row), scan forward for the next exit of that symbol, and note
    any ratchet_breakeven between entry and exit.
    """
    docs = []
    n = len(rows)
    # Pre-index auto_entry rows by symbol for the "preceding same-day" match.
    for i, row in enumerate(rows):
        if row.get("kind") != "entry":
            continue
        sym = (row.get("symbol") or "").upper()
        entry_epoch = _epoch(row)
        entry_day = (row.get("ts") or "")[:10]

        # Matching auto_entry trigger: most-recent auto_entry for this symbol
        # AT or BEFORE the entry, same ET day.
        trigger_row = None
        for j in range(i, -1, -1):
            r = rows[j]
            if ((r.get("symbol") or "").upper() == sym
                    and r.get("kind") == "auto_entry"
                    and (r.get("ts") or "")[:10] == entry_day):
                trigger_row = r
                break

        # Forward scan for the next exit + any ratchet, for this symbol.
        exit_row = None
        ratcheted = False
        exit_k = None
        for k in range(i + 1, n):
            r = rows[k]
            if (r.get("symbol") or "").upper() != sym:
                # flatten_all has symbol=None but closes EVERY held symbol;
                # treat it as an exit for any still-open symbol.
                if r.get("kind") == "flatten_all":
                    exit_row, exit_k = r, k
                    break
                continue
            if r.get("kind") == "ratchet_breakeven":
                ratcheted = True
                continue
            if _is_exit_row(r):
                exit_row, exit_k = r, k
                break
        # A flatten row without a fill (the sell was only SUBMITTED) is
        # superseded by the trade_closed row the flatten queue writes once
        # the market sell filled — same symbol, before any new entry.
        if (exit_row is not None and exit_row.get("kind") in ("flatten", "flatten_all")
                and not _has_fill(exit_row)):
            for k in range(exit_k + 1, n):
                r = rows[k]
                if (r.get("symbol") or "").upper() != sym:
                    continue
                if r.get("kind") == "entry":
                    break
                if r.get("kind") == "trade_closed":
                    exit_row = r
                    break

        lane = (zone_lanes or {}).get((sym, _et_day_of(row.get("ts"))))
        docs.append(_entry_doc(row, trigger_row, ratcheted, exit_row, zone_lane=lane))
    return docs


# ── Public surface ──────────────────────────────────────────────────────────

def reconcile() -> dict:
    """Rebuild/update the perpetual trade_journal collection from the ledger.

    Idempotent: every round-trip has a stable trade_id ("{symbol}-{entry
    epoch}"), so re-running upserts in place — no duplicates, no deletes, no
    new trading side effects. Safe to call at the top of any read handler and
    once per engine tick. Returns the same shape as summary()."""
    docs = _build_docs(_ledger_rows(), _zone_lanes())
    coll = _journal_coll()
    now = _utc_iso()
    if coll is not None:
        for doc in docs:
            doc = dict(doc, last_reconcile_ts=now)
            try:
                coll.update_one({"trade_id": doc["trade_id"]},
                                {"$set": doc}, upsert=True)
            except Exception as exc:               # noqa: BLE001
                log.warning("journal upsert failed %s: %s",
                            doc.get("trade_id"), exc)
    n_open = sum(1 for d in docs if d["status"] == "open")
    n_closed = sum(1 for d in docs if d["status"] == "closed")
    return {"n_open": n_open, "n_closed": n_closed, "last_reconcile_ts": now}


def load(limit: Optional[int] = None, status: Optional[str] = None) -> list:
    """Read journal docs (most-recent entry first). Falls back to deriving
    them in-memory if the persisted collection is unavailable."""
    coll = _journal_coll()
    docs = []
    if coll is not None:
        try:
            cur = coll.find({} if status is None else {"status": status})
            for d in cur:
                d.pop("_id", None)
                docs.append(d)
        except Exception as exc:                   # noqa: BLE001
            log.warning("journal load failed: %s", exc)
    if not docs:                                   # derive on the fly
        docs = _build_docs(_ledger_rows(), _zone_lanes())
        if status is not None:
            docs = [d for d in docs if d.get("status") == status]
    docs.sort(key=lambda d: (d.get("entry") or {}).get("epoch") or 0.0,
              reverse=True)
    if limit is not None:
        docs = docs[:int(limit)]
    return docs


def _initial_risk_dollars(entry: dict):
    """qty x (entry price - placed stop) when all three are known, else None."""
    try:
        qty = int(entry.get("qty"))
        px = float(entry.get("price"))
        sp = float(entry.get("stop_price"))
    except (TypeError, ValueError):
        return None
    risk = qty * (px - sp)
    return risk if risk > 0 else None


def _realized_r(doc: dict):
    """Realized R for a closed doc: realized $ / initial risk $ when both are
    known (the honest R — the stop the engine PLACED), else the journal's
    gain_pct / stop_pct r_multiple, else None."""
    r = doc.get("realized") or {}
    risk = _initial_risk_dollars(doc.get("entry") or {})
    pnl = r.get("gain_dollars")
    if risk and pnl is not None:
        try:
            return round(float(pnl) / risk, 2)
        except (TypeError, ValueError):
            pass
    rm = r.get("r_multiple")
    try:
        return round(float(rm), 2) if rm is not None else None
    except (TypeError, ValueError):
        return None


def by_strategy(docs: list) -> dict:
    """{strategy: {n, open, closed, wins, losses, win_rate_pct, avg_r,
    expectancy_pct, realized_pnl}} over journal docs — one row per lane
    that has at least one trade (Ajay 2026-09-05: "journal it
    appropriately"). expectancy_pct = mean realized gain_pct over the lane's
    CLOSED trades (a 0% close is neither win nor loss); avg_r = mean
    realized R (see _realized_r); realized_pnl = summed gain_dollars.
    Rates are None until a lane has a closed trade. Pure."""
    out = {}
    for d in docs or []:
        if not isinstance(d, dict):
            continue
        e = d.get("entry") or {}
        tag = e.get("strategy")
        if tag not in STRATEGIES:
            tag = "manual"
        b = out.setdefault(tag, {"n": 0, "open": 0, "closed": 0, "wins": 0, "losses": 0,
                                 "win_rate_pct": None, "avg_r": None,
                                 "expectancy_pct": None, "realized_pnl": 0.0,
                                 "_gains": [], "_rs": []})
        b["n"] += 1
        if d.get("status") != "closed":
            b["open"] += 1
            continue
        b["closed"] += 1
        r = d.get("realized") or {}
        g = r.get("gain_pct")
        try:
            g = float(g) if g is not None else None
        except (TypeError, ValueError):
            g = None
        if g is not None:
            b["_gains"].append(g)
            if g > 0:
                b["wins"] += 1
            elif g < 0:
                b["losses"] += 1
        rr = _realized_r(d)
        if rr is not None:
            b["_rs"].append(rr)
        pnl = r.get("gain_dollars")
        try:
            b["realized_pnl"] += float(pnl) if pnl is not None else 0.0
        except (TypeError, ValueError):
            pass
    for b in out.values():
        gains, rs = b.pop("_gains"), b.pop("_rs")
        decided = b["wins"] + b["losses"]
        b["win_rate_pct"] = round(b["wins"] / decided * 100.0, 1) if decided else None
        b["avg_r"] = round(sum(rs) / len(rs), 2) if rs else None
        b["expectancy_pct"] = round(sum(gains) / len(gains), 2) if gains else None
        b["realized_pnl"] = round(b["realized_pnl"], 2)
    return out


def summary() -> dict:
    """{n_open, n_closed, last_reconcile_ts, by_strategy} without rebuilding."""
    coll = _journal_coll()
    docs = None
    last = None
    if coll is not None:
        try:
            docs = []
            for d in coll.find({}):
                d.pop("_id", None)
                docs.append(d)
            for d in coll.find({}).sort("last_reconcile_ts", -1).limit(1):
                last = d.get("last_reconcile_ts")
        except Exception as exc:                   # noqa: BLE001
            log.warning("journal summary failed: %s", exc)
            docs = None
    if docs is None:
        docs = _build_docs(_ledger_rows(), _zone_lanes())
    return {"n_open": sum(1 for d in docs if d.get("status") == "open"),
            "n_closed": sum(1 for d in docs if d.get("status") == "closed"),
            "last_reconcile_ts": last,
            "by_strategy": by_strategy(docs)}


# ── Narrative (deterministic, factual — never invents a number) ─────────────

def _fmt_money(v) -> str:
    try:
        return "$%.2f" % float(v)
    except (TypeError, ValueError):
        return "$?"


def _fmt_date(ts) -> str:
    """ISO 'YYYY-MM-DDThh:mm:ssZ' -> 'Jun 18 2026' (UTC date, no invention)."""
    if not ts or len(ts) < 10:
        return "?"
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    try:
        y, m, d = int(ts[0:4]), int(ts[5:7]), int(ts[8:10])
        return "%s %d %d" % (months[m - 1], d, y)
    except (ValueError, IndexError):
        return ts[:10]


def narrate(doc: dict) -> str:
    """Deterministic journal prose from a round-trip doc. Every number comes
    from the doc; nothing is invented. Open trades end at the plan; closed
    trades append the exit + realized result."""
    e = doc.get("entry") or {}
    sym = doc.get("symbol") or "?"
    qty = e.get("qty")
    price = e.get("price")

    parts = []
    head = "Bought %s" % sym
    if qty is not None and price is not None:
        head += " — %s sh @ %s." % (qty, _fmt_money(price))
    else:
        head += "."
    parts.append(head)

    trig = e.get("trigger")
    lane = e.get("strategy")
    if trig and trig.get("path"):
        path = trig["path"].replace("_", "-")
        seg = "Auto-entry, %s" % path
        if trig.get("pivot") is not None:
            seg += " pivot clear at %s" % _fmt_money(trig["pivot"])
        if trig.get("relvol") is not None:
            seg += " on %.1fx volume" % float(trig["relvol"])
        if trig.get("score") is not None:
            seg += " (score %s)" % _num(trig["score"])
        parts.append(seg + ".")
    elif lane in ("demand_zone", "breakout", "catalyst"):
        # Lane entries (S&D owner rules, no book): name the lane + the
        # level it rested on when the reason carries one.
        reason = e.get("entry_reason") or {}
        label = {"demand_zone": "Demand-zone", "breakout": "Breakout",
                 "catalyst": "Catalyst"}[lane]
        seg = "%s lane entry (paper Auto-Pilot, owner rules)" % label
        band = reason.get("band") if isinstance(reason.get("band"), dict) else None
        if band is None and isinstance(reason.get("proximity"), dict):
            band = reason["proximity"].get("band")
        if band is None and isinstance(reason.get("bounce"), dict):
            band = reason["bounce"].get("band")
        if isinstance(band, dict) and band.get("lo") is not None and band.get("hi") is not None:
            seg += ", band %s-%s" % (_num(band["lo"]), _num(band["hi"]))
        if lane == "catalyst" and reason.get("catalyst_summary"):
            seg += " — %s" % str(reason["catalyst_summary"])[:160]
        parts.append(seg + ".")
    else:
        parts.append("Manual entry.")

    sp, spct = e.get("stop_price"), e.get("stop_pct")
    tp, tpct = e.get("target_price"), e.get("target_pct")
    rr = e.get("reward_risk")
    plan = []
    if sp is not None:
        s = "Stop %s" % _fmt_money(sp)
        if spct is not None:
            s += " (-%s%%, TLSW p.311)" % _num(spct)
        plan.append(s)
    if tp is not None:
        t = "target %s" % _fmt_money(tp)
        bits = []
        if tpct is not None:
            bits.append("+%s%%" % _num(tpct))
        if rr is not None:
            bits.append("%s:1" % _num(rr))
        if bits:
            t += " (%s, p.301)" % ", ".join(bits)
        plan.append(t)
    if plan:
        parts.append("; ".join(plan) + ".")

    if doc.get("protected_to_breakeven"):
        parts.append("Stop raised to breakeven at +3R (p.308).")

    if doc.get("status") == "open":
        parts.append("Position open.")
        return " ".join(parts)

    x = doc.get("exit") or {}
    r = doc.get("realized") or {}
    leg = x.get("leg")
    verb = {"take_profit": "Exited via take-profit",
            "stop": "Stopped out",
            "flatten": "Manually flattened",
            "sim_handover": "Booked at SIM paper handover"}.get(leg, "Closed")
    seg = verb
    if x.get("price") is not None:
        seg += " @ %s" % _fmt_money(x["price"])
    if x.get("ts"):
        seg += " on %s" % _fmt_date(x["ts"])
    tail = []
    if r.get("gain_pct") is not None:
        tail.append("%s%%" % _signed(r["gain_pct"]))
    if r.get("r_multiple") is not None:
        tail.append("%sR" % _num(r["r_multiple"]))
    if r.get("holding_days") is not None:
        tail.append("held %s calendar days" % _num(r["holding_days"]))
    if tail:
        seg += " — " + ", ".join(tail)
    parts.append(seg + ".")
    return " ".join(parts)


def _num(v):
    """Trim trailing .0 so 15.0 -> '15' but 2.14 stays '2.14'."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f == int(f):
        return str(int(f))
    return ("%.2f" % f).rstrip("0").rstrip(".")


def _signed(v):
    """Like _num but with an explicit leading sign: +15.02 / -7 / 0."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    s = _num(abs(f))
    if f > 0:
        return "+" + s
    if f < 0:
        return "-" + s
    return s


# ── Decision journal (why it did / didn't buy) ──────────────────────────────

_DECISION_KINDS = ("auto_entry", "auto_entry_blocked", "auto_entry_disabled",
                   "auto_entry_error")


def decisions(days: int = 14) -> list:
    """Narrate the auto-entry DECISION rows (entered / blocked / disabled /
    error) into readable, most-recent-first lines. This is the "why it did or
    didn't buy" log, distinct from the round-trip journal."""
    db = _db()
    if db is None:
        return []
    import time
    cutoff = time.time() - max(1, int(days)) * _SECONDS_PER_DAY
    out = []
    try:
        cur = (db.trade_ledger
               .find({"kind": {"$in": list(_DECISION_KINDS)}})
               .sort("epoch", -1))
        for d in cur:
            if _epoch(d) < cutoff:
                continue
            d.pop("_id", None)
            out.append({
                "ts": d.get("ts"),
                "epoch": _epoch(d),
                "kind": d.get("kind"),
                "symbol": d.get("symbol"),
                "line": _narrate_decision(d),
            })
    except Exception as exc:                       # noqa: BLE001
        log.warning("journal decisions read failed: %s", exc)
    return out


def _narrate_decision(row: dict) -> str:
    kind = row.get("kind")
    sym = row.get("symbol") or "?"
    det = row.get("detail") or {}
    if kind == "auto_entry":
        path = (det.get("path") or "").replace("_", "-") or "?"
        seg = "BOUGHT %s — %s trigger" % (sym, path)
        if det.get("pivot") is not None:
            seg += ", pivot %s" % _fmt_money(det["pivot"])
        if det.get("live") is not None:
            seg += ", live %s" % _fmt_money(det["live"])
        if det.get("relvol") is not None:
            seg += ", %.1fx vol" % float(det["relvol"])
        if det.get("score") is not None:
            seg += ", score %s" % _num(det["score"])
        return seg + "."
    if kind == "auto_entry_blocked":
        return "SKIPPED %s — triggered but entry vetoed: %s" % (
            sym, det.get("reason") or "(no reason recorded)")
    if kind == "auto_entry_disabled":
        gate = det.get("gate") or {}
        off = [k for k, v in gate.items() if not v] or ["disabled"]
        return "OFF — auto-entry not running (%s)." % ", ".join(off)
    if kind == "auto_entry_error":
        return "ERROR %s — %s" % (sym, det.get("error") or "(unknown)")
    return "%s %s" % (kind, sym)
