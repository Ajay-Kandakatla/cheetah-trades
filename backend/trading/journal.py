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

from trading.exit_engine import GAJJALA_LANE_COLL, _db, _utc_iso

log = logging.getLogger("trading.journal")

JOURNAL_CITE = ("journal: round-trips reconstructed from trade_ledger; entry "
                "plan p.299/301/311; breakeven ratchet p.308; realized gain "
                "p.299")

# Ledger kinds that CLOSE an open entry (in time order, next-after-entry).
# 2026-10-27 (BUILD_SPEC28 §3.1): "exit_fill" = the broker's fill of an engine market sell, booked by
# trading/exit_fills.py — journal-only (never read by the p.299 stop rule or progressive sizing).
_EXIT_KINDS = ("trade_closed", "flatten", "flatten_all", "exit_fill")


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


def _foreign_fill(r: dict, trade_id: str) -> bool:
    """An exit_fill booked for ANOTHER round trip (its detail.trade_id is set and differs) never closes this one."""
    if r.get("kind") != EXIT_FILL_KIND:
        return False
    tid = (r.get("detail") or {}).get("trade_id")
    return bool(tid) and tid != trade_id


def _has_fill(r: dict) -> bool:
    det = r.get("detail") or {}
    return any(det.get(k) is not None for k in ("fill", "price", "exit_price"))

# Journal lane tags (mirror of trading/entries.STRATEGIES — kept literal so
# this import-light module never pulls entries -> broker at import time).
STRATEGIES = ("minervini", "demand_zone", "breakout", "catalyst", "gajjala", "manual")

# ── 💵 P&L by lane (2026-10-27, BUILD_SPEC28 §3.1) ──────────────────────────
# Ajay: "Anyway you can can show me which tab made money or not?" — the journal stays the ONE engine.
LANE_TAGS = STRATEGIES + ("hot_pullback",)
LANE_ORDER = ("gajjala", "minervini", "demand_zone", "breakout", "catalyst", "options_zone", "zero_dte", "hot_pullback", "manual")
LANE_LABELS = {"gajjala": "🚩 Gajjala", "minervini": "📈 Minervini SEPA", "demand_zone": "🧲 demand zone",
               "breakout": "🚀 breakout (S/D supply band)", "catalyst": "🗞️ catalyst", "options_zone": "🎛️ Options",
               "zero_dte": "🎯 0DTE", "hot_pullback": "🔥 hot pullback", "manual": "✋ manual"}
LANE_LINKS = {"gajjala": ("/trading?view=gajjala", "→ 🚩 Gajjala tab"), "options_zone": ("/trading?view=options", "→ Options tab"),
              "zero_dte": ("/trading?view=zero_dte", "→ 0DTE tab")}
LANE_LINK_DEFAULT = ("/trading?view=journal", "→ Journal")
FORCE_EXIT_KINDS = ("distribution_exit", "watchdog_exit", "hot_pullback_exit")
FILLLESS_EXIT_KINDS = ("flatten", "flatten_all")
EXIT_FILL_KIND = "exit_fill"
SUPERSEDED_REASON = "🚩 breakeven add — merged into its alert's trade"
LANE_PNL_TITLE = "💵 Which lane made money"
LANE_PNL_HONESTY = ("Paper account, gross of fees. Realized $ = each lane's own book; engine sells are booked at the "
                    "broker's fill. Open $ = the broker's unrealized P&L on what it holds now. UNMEASURED — a tally of "
                    "what happened, not a study; small n.")

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
    except Exception as exc:                       # noqa: BLE001
        log.warning("journal: ledger read failed: %s", exc)
        return []
    # 2026-10-27 (BUILD_SPEC28 §3.2): rows written without an epoch (the 🔥 hot pullback lane's own _ledger:
    # top-level fields, an ET-offset ts) get one from their ts, then a stable re-sort puts them at their real time.
    for row in rows:
        if not row.get("epoch") and isinstance(row.get("ts"), str):
            try:
                dt = datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=_ET)
                row["epoch"] = dt.timestamp()
            except Exception:                      # noqa: BLE001
                pass                               # parse failure leaves 0 (_epoch)
    rows.sort(key=_epoch)
    return rows


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


def _gg_lane_docs() -> dict:
    """{alert_id: doc} from the 🚩 Gajjala lane's own book (exit_engine.GAJJALA_LANE_COLL, one doc per alert id —
    order_id, add_order_id, fill_px/qty, add_fill_px/qty, pnl_usd, r_mult). Read-only; {} when the coll is absent
    (tests) or unreadable — the same pattern as _zone_lanes (2026-10-27, BUILD_SPEC28 §3.3)."""
    db = _db()
    coll = getattr(db, GAJJALA_LANE_COLL, None) if db is not None else None
    if coll is None:
        return {}
    out: dict = {}
    try:
        for d in coll.find({}):
            aid = d.get("_id")
            if aid is None:
                continue
            out[aid] = d
    except Exception as exc:                       # noqa: BLE001
        log.warning("journal: gajjala lane read failed: %s", exc)
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
               zone_lane: Optional[str] = None,
               fill_wanted: Optional[dict] = None) -> dict:
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
    entry_reason = det.get("entry_reason")
    if not isinstance(entry_reason, dict):
        entry_reason = None
    tag = det.get("strategy")
    if tag not in STRATEGIES:
        # Untagged (pre-2026-09-05): a zone-edge state doc that ordered on the
        # same ET day names the lane; else an auto_entry trigger = Minervini;
        # else manual.
        tag = zone_lane or ("minervini" if (trigger and trigger.get("path")) else "manual")
    # 🔥 hot pullback (2026-10-27, BUILD_SPEC28 §3.4): entries._strategy_tag collapses the lane to "manual";
    # its entry_reason.lane still names it — journal-side only, entries.STRATEGIES unchanged.
    if tag == "manual" and isinstance(entry_reason, dict) and entry_reason.get("lane") == "hot_pullback":
        tag = "hot_pullback"

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
        # 2026-10-27 (BUILD_SPEC28 §3.4): the engine sold at market but no broker fill is booked yet.
        "fill_wanted": fill_wanted,
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
    if leg not in ("stop", "take_profit", "sim_handover", "force_exit"):
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

    # An exit_fill (2026-10-27) books the SOLD qty, never the planned entry qty (force exit AND flatten); a
    # fractional fill keeps its fraction (verifier LOW: int() truncated 0.5 to 0 and fell back to the planned qty).
    qty_used = qty
    if kind == EXIT_FILL_KIND:
        try:
            sold = float(det.get("qty") or 0)
            if sold > 0:
                qty_used = int(sold) if sold == int(sold) else sold
        except (TypeError, ValueError):
            pass
    gain_dollars = None
    if (exit_price is not None and entry_price is not None
            and qty_used is not None):
        gain_dollars = round(qty_used * (exit_price - entry_price), 2)

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
    if leg == "force_exit":
        exit_reason = {"distribution_exit": "engine sell rule (distribution exit)",
                       "watchdog_exit": "engine stop backstop (watchdog exit)",
                       "hot_pullback_exit": "🔥 lane exit"}.get(det.get("source_kind"), "engine market sell")
        if det.get("reason"):
            exit_reason = ("%s, %s" % (exit_reason, str(det["reason"]).strip()))[:160]

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
    if kind == EXIT_FILL_KIND:
        realized["source"] = det.get("source")         # "broker_fill" | "broker_fill_backfill"
        realized["qty"] = qty_used                     # the SOLD qty — _realized_r sizes the risk on it (verifier MED)
    return exit_doc, realized


def _f_or_none(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _int0(v) -> int:
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


def _det_of(r: dict) -> dict:
    """detail for an engine row; the row itself for a lane row written with top-level fields (🔥 hot pullback)."""
    return r.get("detail") if isinstance(r.get("detail"), dict) else r


def _sent(r: dict) -> bool:
    """A force-exit row whose market sell was actually sent (closed not False)."""
    return _det_of(r).get("closed") is not False


def _want(r: dict, window_end_ts=None) -> dict:
    """fill_wanted: the engine sold at market and the broker's fill is not booked yet (BUILD_SPEC28 §3.4)."""
    det = _det_of(r)
    last = det.get("last")
    if last is None:
        last = det.get("price")
    reason = det.get("reason")
    if reason is None:
        reason = det.get("why")
    return {"kind": r.get("kind"), "ts": r.get("ts"), "epoch": _epoch(r), "last": last,
            "held_qty": _int0(det.get("qty")) or None, "reason": reason,
            "queued": bool(det.get("queued_at")), "window_end_ts": window_end_ts}


def _gg_groups(rows: list, gg_docs: dict) -> dict:
    """🚩 Gajjala pairing by ALERT id (2026-10-27, BUILD_SPEC28 §3.3). PURE.

    -> {"role": {row_index: (alert_id, "main"|"add")}, "main": {alert_id: row_index},
        "merged": {add_trade_id: main_trade_id}, "exit": {alert_id: the first gajjala_exit row}}.
    The breakeven add's entry row merges into its alert's trade; an entry row with no resolvable alert id stays
    on the generic path."""
    by_order: dict = {}
    for aid, d in (gg_docs or {}).items():
        if not isinstance(d, dict):
            continue
        if d.get("order_id"):
            by_order[d["order_id"]] = (aid, "main")
        if d.get("add_order_id"):
            by_order[d["add_order_id"]] = (aid, "add")
    exits: dict = {}
    for r in rows:
        if r.get("kind") != "gajjala_exit":
            continue
        aid = (r.get("detail") or {}).get("alert_id")
        if aid is not None and aid not in exits:
            exits[aid] = r
    role: dict = {}
    main: dict = {}
    for i, r in enumerate(rows):
        if r.get("kind") != "entry":
            continue
        det = r.get("detail") if isinstance(r.get("detail"), dict) else {}
        if det.get("strategy") != "gajjala":
            continue
        reason = det.get("entry_reason")
        if not isinstance(reason, dict) or reason.get("truncated"):
            reason = {}
        aid = reason.get("alert_id")
        rl = "add" if reason.get("add") is True else None
        oid = det.get("order_id")
        bo = by_order.get(oid) if oid is not None else None
        if aid is None and bo:
            aid = bo[0]
        if rl is None and bo:
            rl = bo[1]
        if "-gg-add-" in str(det.get("client_order_id") or ""):
            rl = "add"
        rl = rl or "main"
        if aid is None:
            continue                               # generic path, unchanged
        if rl == "main" and aid not in main:
            main[aid] = i
            role[i] = (aid, "main")
        else:
            role[i] = (aid, "add")
    merged: dict = {}
    for i, (aid, rl) in role.items():
        if rl != "add" or aid not in main:
            continue
        m = rows[main[aid]]
        merged[_trade_id((rows[i].get("symbol") or "").upper(), _epoch(rows[i]))] = \
            _trade_id((m.get("symbol") or "").upper(), _epoch(m))
    return {"role": role, "main": main, "merged": merged, "exit": exits}


def _gg_exit_and_realized(entry: dict, xr: dict, lane_doc: Optional[dict]):
    """exit + realized of an alert-paired 🚩 trade from the lane's own book (the gajjala_exit row, then the lane
    doc): realized $ = the lane's pnl_usd, R = its r_mult. Never a flatten / trade_closed row."""
    det = xr.get("detail") or {}
    ld = lane_doc or {}
    pnl = _f_or_none(det.get("pnl_usd"))
    if pnl is None:
        pnl = _f_or_none(ld.get("pnl_usd"))
    exit_px = _f_or_none(det.get("exit_px"))
    if exit_px is None:
        exit_px = _f_or_none(ld.get("exit_px"))
    fill_px = _f_or_none(ld.get("fill_px"))
    if fill_px is None:
        fill_px = _f_or_none(det.get("fill_px"))
    fill_qty = _int0(ld.get("fill_qty") or det.get("qty") or entry.get("qty") or 0)
    add_px = _f_or_none(ld.get("add_fill_px"))
    add_qty = _int0(ld.get("add_fill_qty") or det.get("add_qty") or 0)
    cost = (fill_px * fill_qty if fill_px is not None else 0.0) + \
        (add_px * add_qty if add_px is not None and add_qty > 0 else 0.0)
    if pnl is not None and cost > 0:
        gain_pct = round(pnl / cost * 100, 2)
    elif exit_px is not None and fill_px:
        gain_pct = round((exit_px / fill_px - 1) * 100, 2)
    else:
        gain_pct = None
    kind = det.get("exit_kind") or ld.get("exit_kind")
    leg = {"stop": "stop", "target": "take_profit"}.get(kind, "lane_exit")
    exit_reason = {"stop": "stopped out", "target": "take-profit", "trail": "🚩 lane trail exit",
                   "flatten": "🚩 lane flatten", "owner": "closed by the owner",
                   "carried": "🚩 lane carried exit"}.get(kind, "🚩 lane exit")
    holding_days = None
    ee, xe = entry.get("epoch"), _epoch(xr)
    if ee and xe and xe >= ee:
        holding_days = round((xe - ee) / _SECONDS_PER_DAY, 2)
    exit_doc = {"ts": xr.get("ts"), "epoch": xe, "price": exit_px, "leg": leg, "kind": kind}
    realized = {"gain_pct": gain_pct, "gain_dollars": pnl, "r_multiple": _f_or_none(det.get("r_mult")),
                "holding_days": holding_days, "exit_reason": exit_reason, "source": "lane_book",
                "cost_basis": round(cost, 2) or None}
    return exit_doc, realized


def _gg_entry_doc(entry_row: dict, rows: list, g: dict, lane_doc: Optional[dict]) -> dict:
    """One journal trade per 🚩 alert: the main entry row, the add merged in, closed ONLY by the alert's own
    gajjala_exit row."""
    aid = next((a for a, idx in g["main"].items() if rows[idx] is entry_row), None)
    doc = _entry_doc(entry_row, None, False, None)
    entry = doc["entry"]
    ld = lane_doc or {}
    add_row = next((rows[i] for i, (a, rl) in sorted(g["role"].items()) if a == aid and rl == "add"), None)
    add_det = (add_row.get("detail") or {}) if add_row is not None else {}
    entry["alert_id"] = aid
    entry["add_qty"] = ld.get("add_fill_qty") or add_det.get("qty") or None
    entry["add_price"] = ld.get("add_fill_px") or add_det.get("price")
    doc["fill_wanted"] = None
    xr = g["exit"].get(aid)
    if xr is not None and _epoch(xr) >= (entry.get("epoch") or 0.0):
        doc["status"] = "closed"
        doc["exit"], doc["realized"] = _gg_exit_and_realized(entry, xr, lane_doc)
    doc["narrative"] = narrate(doc)
    return doc


def _build_docs(rows: list, zone_lanes: Optional[dict] = None, gg_docs: Optional[dict] = None) -> list:
    """Reconstruct every round-trip from the ordered ledger rows.

    One pass, time-ordered: for each "entry" row, find the matching
    auto_entry trigger (same symbol + same ET day, the immediately-preceding
    auto_entry row), scan forward for the next exit of that symbol, and note
    any ratchet_breakeven between entry and exit.

    2026-10-27 (BUILD_SPEC28 §3.3-§3.4): 🚩 Gajjala entries pair by ALERT id (the add merges, the lane's own
    gajjala_exit closes it); a generic doc whose engine market sell has no booked fill carries fill_wanted.
    """
    gg_docs = gg_docs or {}
    g = _gg_groups(rows, gg_docs)
    docs = []
    n = len(rows)
    # Pre-index auto_entry rows by symbol for the "preceding same-day" match.
    for i, row in enumerate(rows):
        if row.get("kind") != "entry":
            continue
        if i in g["role"]:
            aid, rl = g["role"][i]
            if rl == "add":
                continue                           # merged into its alert's trade
            docs.append(_gg_entry_doc(row, rows, g, gg_docs.get(aid)))
            continue
        sym = (row.get("symbol") or "").upper()
        entry_epoch = _epoch(row)
        entry_day = (row.get("ts") or "")[:10]
        this_tid = _trade_id(sym, entry_epoch)

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
        next_entry_ts = None
        fill_wanted = None
        for k in range(i + 1, n):
            r = rows[k]
            if (r.get("symbol") or "").upper() != sym:
                # flatten_all has symbol=None but closes EVERY held symbol;
                # treat it as an exit for any still-open symbol.
                if r.get("kind") == "flatten_all":
                    exit_row, exit_k = r, k
                    break
                continue
            if r.get("kind") == "entry" and next_entry_ts is None:
                next_entry_ts = r.get("ts")       # records only; never stops the scan
            if (r.get("kind") in FORCE_EXIT_KINDS and fill_wanted is None
                    and next_entry_ts is None and _sent(r)):
                fill_wanted = _want(r)
            if r.get("kind") == "ratchet_breakeven":
                ratcheted = True
                continue
            if _foreign_fill(r, this_tid):
                continue                           # another trade's booked fill (2026-10-27)
            if _is_exit_row(r):
                exit_row, exit_k = r, k
                break
        # A flatten row without a fill (the sell was only SUBMITTED) is
        # superseded by the trade_closed row the flatten queue writes once
        # the market sell filled — same symbol, before any new entry (or by
        # the exit_fill the engine-sell matcher books, 2026-10-27).
        window_end = None
        if (exit_row is not None and exit_row.get("kind") in FILLLESS_EXIT_KINDS
                and not _has_fill(exit_row)):
            for k in range(exit_k + 1, n):
                r = rows[k]
                if (r.get("symbol") or "").upper() != sym:
                    continue
                if r.get("kind") == "entry":
                    window_end = r.get("ts")
                    break
                if _foreign_fill(r, this_tid):
                    continue
                if r.get("kind") in ("trade_closed", EXIT_FILL_KIND):
                    exit_row = r
                    break
        if exit_row is None and fill_wanted:
            fill_wanted["window_end_ts"] = next_entry_ts
        elif (exit_row is not None and exit_row.get("kind") in FILLLESS_EXIT_KINDS
                and not _has_fill(exit_row)):
            fill_wanted = _want(exit_row, window_end_ts=window_end)
        else:
            fill_wanted = None

        lane = (zone_lanes or {}).get((sym, _et_day_of(row.get("ts"))))
        docs.append(_entry_doc(row, trigger_row, ratcheted, exit_row, zone_lane=lane,
                               fill_wanted=fill_wanted))
    return docs


# ── Public surface ──────────────────────────────────────────────────────────

def reconcile() -> dict:
    """Rebuild/update the perpetual trade_journal collection from the ledger.

    Idempotent: every round-trip has a stable trade_id ("{symbol}-{entry
    epoch}"), so re-running upserts in place — no duplicates, no deletes, no
    new trading side effects. Safe to call at the top of any read handler and
    once per engine tick. Returns the same shape as summary().

    2026-10-27 (BUILD_SPEC28 §3.5): a 🚩 breakeven add's OLD doc (written before the alert pairing) is marked
    superseded — never deleted, never upserted here; load()/summary() skip it."""
    rows = _ledger_rows()
    gg = _gg_lane_docs()
    docs = _build_docs(rows, _zone_lanes(), gg)
    merged = _gg_groups(rows, gg)["merged"]
    coll = _journal_coll()
    now = _utc_iso()
    if coll is not None:
        for doc in docs:
            doc = dict(doc, last_reconcile_ts=now, superseded=False)
            try:
                coll.update_one({"trade_id": doc["trade_id"]},
                                {"$set": doc}, upsert=True)
            except Exception as exc:               # noqa: BLE001
                log.warning("journal upsert failed %s: %s",
                            doc.get("trade_id"), exc)
        for add_id, main_id in merged.items():
            try:
                coll.update_one({"trade_id": add_id},
                                {"$set": {"superseded": True, "superseded_by": main_id,
                                          "superseded_reason": SUPERSEDED_REASON,
                                          "last_reconcile_ts": now}})
            except Exception as exc:               # noqa: BLE001
                log.warning("journal supersede failed %s: %s", add_id, exc)
    n_open = sum(1 for d in docs if d["status"] == "open")
    n_closed = sum(1 for d in docs if d["status"] == "closed")
    return {"n_open": n_open, "n_closed": n_closed, "last_reconcile_ts": now,
            "superseded": len(merged),
            "unbooked": sum(1 for d in docs if d.get("fill_wanted"))}


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
                if d.get("superseded") is True:    # a merged 🚩 add (2026-10-27) — kept, never shown
                    continue
                docs.append(d)
        except Exception as exc:                   # noqa: BLE001
            log.warning("journal load failed: %s", exc)
    if not docs:                                   # derive on the fly
        docs = _build_docs(_ledger_rows(), _zone_lanes(), _gg_lane_docs())
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
    if r.get("source") == "lane_book":             # 🚩 alert-paired: the lane's own R (2026-10-27)
        try:
            return round(float(r.get("r_multiple")), 2) if r.get("r_multiple") is not None else None
        except (TypeError, ValueError):
            return None
    entry = doc.get("entry") or {}
    risk = _initial_risk_dollars(entry)
    # 2026-10-27 (verifier MED): an exit_fill that sold FEWER shares than the planned entry qty carries realized.qty;
    # the R on what was actually sold = $ on the sold shares / (sold shares x (entry - placed stop)) — never the
    # planned-qty risk, which would dilute a 6-of-56 partial from -0.09R to -0.01R.
    try:
        sold = float(r.get("qty")) if r.get("qty") is not None else None
        if sold and sold > 0 and entry.get("price") is not None and entry.get("stop_price") is not None:
            per_share = float(entry["price"]) - float(entry["stop_price"])
            risk = sold * per_share if per_share > 0 else None
    except (TypeError, ValueError):
        pass
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
    Rates are None until a lane has a closed trade. Pure.

    2026-10-27 (BUILD_SPEC28 §3.6): + unbooked (an engine sell with no booked fill, or a closed trade with no
    realized $), first_ts / last_ts (ISO UTC), label / url / link_text; 🔥 hot_pullback keeps its own row."""
    out = {}
    for d in docs or []:
        if not isinstance(d, dict):
            continue
        e = d.get("entry") or {}
        tag = e.get("strategy")
        if tag not in LANE_TAGS:
            tag = "manual"
        b = out.setdefault(tag, {"n": 0, "open": 0, "closed": 0, "wins": 0, "losses": 0,
                                 "win_rate_pct": None, "avg_r": None,
                                 "expectancy_pct": None, "realized_pnl": 0.0,
                                 "unbooked": 0, "first_ts": None, "last_ts": None,
                                 "_gains": [], "_rs": []})
        b["n"] += 1
        closed = d.get("status") == "closed"
        x = d.get("exit") or {}
        e_ts = e.get("ts")
        if e_ts and (b["first_ts"] is None or str(e_ts) < b["first_ts"]):
            b["first_ts"] = str(e_ts)
        l_ts = x.get("ts") if closed and x.get("ts") else e_ts
        if l_ts and (b["last_ts"] is None or str(l_ts) > b["last_ts"]):
            b["last_ts"] = str(l_ts)
        if d.get("fill_wanted") or (closed and (d.get("realized") or {}).get("gain_dollars") is None):
            b["unbooked"] += 1
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
    for key, b in out.items():
        gains, rs = b.pop("_gains"), b.pop("_rs")
        decided = b["wins"] + b["losses"]
        b["win_rate_pct"] = round(b["wins"] / decided * 100.0, 1) if decided else None
        b["avg_r"] = round(sum(rs) / len(rs), 2) if rs else None
        b["expectancy_pct"] = round(sum(gains) / len(gains), 2) if gains else None
        b["realized_pnl"] = round(b["realized_pnl"], 2)
        b["label"] = LANE_LABELS.get(key, key.replace("_", " "))
        b["url"], b["link_text"] = LANE_LINKS.get(key, LANE_LINK_DEFAULT)
    return out


def _summary_core() -> dict:
    """{n_open, n_closed, last_reconcile_ts, by_strategy} without rebuilding."""
    coll = _journal_coll()
    docs = None
    last = None
    if coll is not None:
        try:
            docs = []
            for d in coll.find({}):
                d.pop("_id", None)
                if d.get("superseded") is True:    # a merged 🚩 add (2026-10-27)
                    continue
                docs.append(d)
            for d in coll.find({}).sort("last_reconcile_ts", -1).limit(1):
                last = d.get("last_reconcile_ts")
        except Exception as exc:                   # noqa: BLE001
            log.warning("journal summary failed: %s", exc)
            docs = None
    if docs is None:
        docs = _build_docs(_ledger_rows(), _zone_lanes(), _gg_lane_docs())
    return {"n_open": sum(1 for d in docs if d.get("status") == "open"),
            "n_closed": sum(1 for d in docs if d.get("status") == "closed"),
            "last_reconcile_ts": last,
            "by_strategy": by_strategy(docs)}


def _lane_meta(key: str) -> dict:
    url, link_text = LANE_LINKS.get(key, LANE_LINK_DEFAULT)
    return {"label": LANE_LABELS.get(key, key.replace("_", " ")), "url": url, "link_text": link_text}


def _zero_dte_row(blk: dict) -> dict:
    """The 🎯 0DTE lane's journal_block reshaped to the by_strategy keys (BUILD_SPEC28 §3.7). PURE. n = open +
    closed (the lane's missed orders are not trades); expectancy = its avg_premium_return_pct; avg_r None."""
    b = blk if isinstance(blk, dict) else {}
    op, cl = _int0(b.get("open")), _int0(b.get("closed"))
    return dict({"n": op + cl, "open": op, "closed": cl, "wins": _int0(b.get("wins")),
                 "losses": _int0(b.get("losses")), "win_rate_pct": b.get("win_rate_pct"), "avg_r": None,
                 "expectancy_pct": b.get("avg_premium_return_pct"),
                 "realized_pnl": round(_f_or_none(b.get("realized_pnl")) or 0.0, 2),
                 "missed": _int0(b.get("missed")), "unbooked": 0,
                 "first_ts": b.get("first_ts"), "last_ts": b.get("last_ts")}, **_lane_meta("zero_dte"))


def summary(lane_blocks: Optional[dict] = None) -> dict:
    """{n_open, n_closed, last_reconcile_ts, by_strategy} without rebuilding.
    The options lane's contracts never pass through entries.enter, so its
    lane row is merged in from trading/options_lane.journal_block()
    (2026-09-06); fenced so a Mongo miss there cannot break the journal.
    2026-10-27 (BUILD_SPEC28 §3.7): the 🎯 0DTE lane's row is merged the same way from
    trading/zero_dte_lane.journal_block(); `lane_blocks` lets /trading/status hand in the blocks it already built."""
    out = _summary_core()
    lane_blocks = lane_blocks if isinstance(lane_blocks, dict) else {}
    try:
        from trading import options_lane
        blk = lane_blocks.get("options_zone")
        if not (isinstance(blk, dict) and "n" in blk):
            blk = options_lane.journal_block()
        if blk.get("n"):
            bs = dict(out.get("by_strategy") or {})
            bs[options_lane.STRATEGY] = dict(blk, unbooked=0, **_lane_meta(options_lane.STRATEGY))
            out["by_strategy"] = bs
    except Exception as exc:                       # noqa: BLE001
        log.warning("journal: options lane block unavailable: %s", exc)
    try:
        from trading import zero_dte_lane
        blk = lane_blocks.get("zero_dte")
        if not (isinstance(blk, dict) and "n" in blk):
            blk = zero_dte_lane.journal_block()
        row = _zero_dte_row(blk)
        if row["n"] > 0:
            bs = dict(out.get("by_strategy") or {})
            bs[zero_dte_lane.STRATEGY] = row
            out["by_strategy"] = bs
    except Exception as exc:                       # noqa: BLE001
        log.warning("journal: 0DTE lane block unavailable: %s", exc)
    return out


# ── Engine-sell fill candidates (the ONE candidate engine, BUILD_SPEC28 §3.9) ─

def unbooked_exits(rows: Optional[list] = None, zone_lanes: Optional[dict] = None,
                   gg_docs: Optional[dict] = None) -> list:
    """Every journal round trip whose engine market sell has no booked broker fill (fill_wanted), oldest entry
    first: {trade_id, symbol, lane, status, entry_ts, entry_epoch, entry_price, entry_qty, **fill_wanted}.
    trading/exit_fills.py matches these against the broker's own orders. Reads only."""
    rows = _ledger_rows() if rows is None else rows
    zone_lanes = _zone_lanes() if zone_lanes is None else zone_lanes
    gg_docs = _gg_lane_docs() if gg_docs is None else gg_docs
    out = []
    for d in _build_docs(rows, zone_lanes, gg_docs):
        fw = d.get("fill_wanted")
        if not fw:
            continue
        e = d.get("entry") or {}
        out.append(dict({"trade_id": d.get("trade_id"), "symbol": d.get("symbol"), "lane": e.get("strategy"),
                         "status": d.get("status"), "entry_ts": e.get("ts"), "entry_epoch": e.get("epoch"),
                         "entry_price": e.get("price"), "entry_qty": e.get("qty")}, **fw))
    out.sort(key=lambda c: c.get("entry_epoch") or 0.0)
    return out


# ── 💵 P&L by lane (2026-10-27, BUILD_SPEC28 §3.10) ─────────────────────────
# A TALLY of each lane's own book plus the broker's open P&L — not a study. Every served word is built here.

def _fin(v) -> float:
    """float(v), 0.0 for None / garbage / non-finite (the payload must survive allow_nan=False)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return f if f == f and f not in (float("inf"), float("-inf")) else 0.0


def _usd(v) -> str:
    f = round(_fin(v), 2)
    if f > 0:
        return "+$" + format(f, ",.2f")
    if f < 0:
        return "-$" + format(-f, ",.2f")
    return "$0.00"


def _pct0(v) -> str:
    return "%d%%" % round(float(v))


def _lane_of(tag) -> str:
    return tag if tag in LANE_TAGS else "manual"


def lane_pnl(summary: dict, positions: Optional[list], pnl: Optional[dict], since_ts: Optional[str],
             open_docs: list, contracts: dict, now_iso: Optional[str] = None) -> dict:
    """Which lane made money: one row per lane that traded (realized $ from its own book + the broker's open $ on
    what it holds now), the account line, and the part no lane explains. PURE."""
    bs = (summary or {}).get("by_strategy") or {}
    known = positions is not None
    pos = [p for p in (positions or []) if isinstance(p, dict)]
    stock = [p for p in pos if (p.get("asset_class") or "") != "us_option"]
    opts = [p for p in pos if (p.get("asset_class") or "") == "us_option"]
    contracts = contracts if isinstance(contracts, dict) else {}
    open_docs = [d for d in (open_docs or []) if isinstance(d, dict)]

    def upl(p) -> float:
        return _fin(p.get("unrealized_pl"))

    held_syms = set()
    lane_syms: dict = {}
    lane_upl: dict = {}
    for p in stock:
        if _fin(p.get("qty")) == 0:
            continue
        sym = str(p.get("symbol") or "").upper()
        held_syms.add(sym)
        cands = [d for d in open_docs if str(d.get("symbol") or "").upper() == sym]
        if not cands:
            continue                               # unattributed
        best = max(cands, key=lambda d: _fin((d.get("entry") or {}).get("epoch")))
        lane = _lane_of((best.get("entry") or {}).get("strategy"))
        lane_syms.setdefault(lane, set()).add(sym)
        lane_upl[lane] = lane_upl.get(lane, 0.0) + upl(p)
    lane_pos: dict = {}
    for p in opts:
        hit = contracts.get(str(p.get("symbol") or "").upper())
        if not hit:
            continue                               # unattributed
        lane, pos_id = hit
        lane_pos.setdefault(lane, set()).add(pos_id)
        lane_upl[lane] = lane_upl.get(lane, 0.0) + upl(p)

    rows = []
    for key, b in bs.items():
        if not isinstance(b, dict):
            continue
        closed, opened = _int0(b.get("closed")), _int0(b.get("open"))
        if closed + opened <= 0:
            continue
        realized = round(_fin(b.get("realized_pnl")), 2)
        if known:
            held = len(lane_syms.get(key, ())) + len(lane_pos.get(key, ()))
            unreal = round(lane_upl.get(key, 0.0), 2) if held > 0 else None
            if key in ("options_zone", "zero_dte"):
                unbooked = 0
                unheld = max(0, opened - held)
            else:
                mine = [d for d in open_docs if _lane_of((d.get("entry") or {}).get("strategy")) == key]
                unbooked = _int0(b.get("unbooked")) - len(
                    {d.get("trade_id") for d in mine if d.get("fill_wanted")
                     and str(d.get("symbol") or "").upper() in held_syms})
                unheld = len({d.get("trade_id") for d in mine if not d.get("fill_wanted")
                              and str(d.get("symbol") or "").upper() not in held_syms})
        else:
            held, unreal, unheld = None, None, None
            unbooked = _int0(b.get("unbooked"))
        total = round(realized + (unreal or 0.0), 2)
        wins, losses, wr = _int0(b.get("wins")), _int0(b.get("losses")), b.get("win_rate_pct")
        if not known:
            open_text = "open $ unavailable"
        elif held:
            open_text = "open %s on %d held" % (_usd(unreal), held)
        elif opened > 0:
            open_text = "nothing held at the broker"
        else:
            open_text = "nothing open"
        first_ts, last_ts = b.get("first_ts"), b.get("last_ts")
        d1 = _et_day_of(first_ts) if first_ts else None
        d2 = _et_day_of(last_ts) if last_ts else None
        if d1 and d2:
            dates_text = d1 if d1 == d2 else "%s → %s" % (d1, d2)
        else:
            dates_text = d1 or d2 or None
        notes = []
        if unbooked > 0:
            notes.append("%d sold without a booked fill — not in realized $" % unbooked)
        if unheld:
            notes.append("%d open in the lane's book but not held at the broker — no open $" % unheld)
        meta = _lane_meta(key)
        rows.append({
            "key": key, "label": b.get("label") or meta["label"], "url": b.get("url") or meta["url"],
            "link_text": b.get("link_text") or meta["link_text"],
            "closed": closed, "open": opened, "held": held, "unbooked": unbooked, "unheld": unheld,
            "wins": wins, "losses": losses, "win_rate_pct": wr,
            "realized_pnl": realized, "unrealized_pnl": unreal, "total_pnl": total,
            "first_ts": first_ts, "last_ts": last_ts,
            "total_text": _usd(total),
            "record_text": "%d closed · %d W / %d L" % (closed, wins, losses)
                           + (" · %s won" % _pct0(wr) if wr is not None else ""),
            "realized_text": "realized %s" % _usd(realized),
            "open_text": open_text, "dates_text": dates_text,
            "note_text": " · ".join(notes) if notes else None,
            "tone": "up" if total > 0 else ("down" if total < 0 else "flat"),
        })
    rows.sort(key=lambda r: (-r["total_pnl"], LANE_ORDER.index(r["key"]) if r["key"] in LANE_ORDER else 99))
    keys = {r["key"] for r in rows}
    untraded = [k for k in LANE_ORDER if k not in keys]
    untraded_text = ("No trades yet: " + " · ".join(LANE_LABELS[k] for k in untraded)) if untraded else None

    # Account line.
    pnl = pnl if isinstance(pnl, dict) else None
    total = _f_or_none((pnl or {}).get("total_pnl_dollars"))
    unreal_all = round(sum(upl(p) for p in pos), 2) if known else None
    # Broker unknown → the closed/open split of the account is unknown too: realized stays None and no "closed"
    # sentence is served (critic LOW: the total would otherwise be printed as "closed" while it holds open P&L).
    realized_all = round(total - unreal_all, 2) if (total is not None and known) else None
    if since_ts:
        since = _et_day_of(since_ts)
    else:
        firsts = [r["first_ts"] for r in rows if r.get("first_ts")]
        since = _et_day_of(min(firsts)) if firsts else None
    since_word = since or "?"
    account = None
    if pnl is not None:
        account = {"starting": _f_or_none(pnl.get("starting_cash")), "equity": _f_or_none(pnl.get("equity")),
                   "total_pnl": total, "unrealized_pnl": unreal_all, "realized_pnl": realized_all}
    if total is None:
        account_text = "Account baseline unavailable."
    elif not known:
        account_text = "Account since %s: %s" % (since_word, _usd(total))
    else:
        account_text = "Account since %s: %s (%s closed · %s open)" % (
            since_word, _usd(total), _usd(realized_all), _usd(unreal_all))

    lr = round(sum(r["realized_pnl"] for r in rows), 2)
    lu = round(sum(r["unrealized_pnl"] or 0.0 for r in rows), 2)
    lanes_total = {"realized_pnl": lr, "unrealized_pnl": lu, "total_pnl": round(lr + lu, 2)}
    unexplained = {"realized_pnl": round(realized_all - lr, 2) if realized_all is not None else None,
                   "unrealized_pnl": round(unreal_all - lu, 2) if unreal_all is not None else None}
    if total is None or not known:
        unexplained_text = None                     # no split to attribute without the broker's positions
    else:
        unexplained_text = ("Not attributed to a lane: %s closed · %s open — the account's P&L minus every "
                            "lane's book." % (_usd(unexplained["realized_pnl"]), _usd(unexplained["unrealized_pnl"])))

    def suffix(r) -> str:
        return "(%d closed" % r["closed"] + (", %d held" % r["held"] if r["held"] else "") + ")"

    if not rows:
        verdict = "No Auto-Pilot lane has traded since %s." % since_word
    else:
        pos_rows = [r for r in rows if r["total_pnl"] > 0]
        if not pos_rows:
            best = rows[0]
            if best["total_pnl"] == 0:
                verdict = "No lane is net positive on paper since %s · %s is flat %s." % (
                    since_word, best["label"], suffix(best))
            else:
                verdict = "No lane is net positive on paper since %s · %s is the smallest loser (%s, %d closed)." % (
                    since_word, best["label"], _usd(best["total_pnl"]), best["closed"])
        else:
            verdict = "%d of %d lanes net positive on paper since %s: " % (len(pos_rows), len(rows), since_word) \
                + ", ".join("%s %s %s" % (r["label"], _usd(r["total_pnl"]), suffix(r)) for r in pos_rows)
            if any(r["total_pnl"] < 0 for r in rows):
                w = rows[-1]
                verdict += " · biggest loser %s %s %s" % (w["label"], _usd(w["total_pnl"]), suffix(w))
            verdict += "."

    return {"title": LANE_PNL_TITLE, "as_of": now_iso or _utc_iso(), "since": since,
            "verdict_text": verdict, "honesty_text": LANE_PNL_HONESTY,
            "account": account, "account_text": account_text,
            "lanes_total": lanes_total, "unexplained": unexplained, "unexplained_text": unexplained_text,
            "rows": rows, "untraded": untraded, "untraded_text": untraded_text,
            "positions_text": None if known else "Broker positions not read — open $ not shown."}


def _lane_contracts(lane_status: dict) -> dict:
    """{OCC: (lane, pos_id)} for the options / 0DTE lanes' open positions — from the status blocks /trading/status
    already built, else a read-only read of the lane's positions coll (status open / closing)."""
    out: dict = {}
    for key, coll_name in (("options_zone", "options_positions"), ("zero_dte", "zero_dte_positions")):
        try:
            if key == "options_zone":
                from trading import options_lane as mod
            else:
                from trading import zero_dte_lane as mod
            coll_name = getattr(mod, "POSITIONS_COLL", coll_name)
        except Exception:                          # noqa: BLE001
            pass
        blk = lane_status.get(key)
        opens = blk.get("open") if isinstance(blk, dict) and isinstance(blk.get("open"), list) else None
        if opens is None:
            opens = []
            try:
                db = _db()
                coll = getattr(db, coll_name, None) if db is not None else None
                if coll is not None:
                    opens = [d for d in coll.find({"status": {"$in": ["open", "closing"]}})]
            except Exception as exc:               # noqa: BLE001
                log.warning("journal: %s positions read failed: %s", key, exc)
                opens = []
        for d in opens:
            if not isinstance(d, dict):
                continue
            occs = [leg.get("symbol") for leg in (d.get("legs") or []) if isinstance(leg, dict)]
            if d.get("occ"):
                occs.append(d.get("occ"))
            pos_id = d.get("pos_id") or d.get("occ") or d.get("symbol")
            for occ in occs:
                if occ:
                    out[str(occ).upper()] = (key, pos_id)
    return out


def lane_pnl_block(positions: Optional[list], pnl: Optional[dict], since_ts: Optional[str],
                   lane_status: Optional[dict] = None) -> dict:
    """/trading/status → lane_pnl: the journal's own summary (reusing the options / 0DTE blocks status already
    built), the persisted open docs and the lanes' open contracts, through the pure lane_pnl. Never reconciles."""
    lane_status = lane_status if isinstance(lane_status, dict) else {}
    s = summary(lane_blocks={k: (v if isinstance(v, dict) else {}).get("journal") for k, v in lane_status.items()})
    open_docs = _open_docs_persisted()
    contracts = _lane_contracts(lane_status)
    return lane_pnl(s, positions, pnl, since_ts, open_docs, contracts)


def _open_docs_persisted() -> list:
    """The PERSISTED open journal docs (superseded ones dropped) for the 10-second status poll — never a rebuild of
    the whole ledger when the collection simply holds no open doc (critic LOW: load() derives on an empty find, which
    would re-read every ledger row and the 🚩 lane book on every poll once the back-fill closes the phantoms). Only a
    missing collection derives, through load()."""
    coll = _journal_coll()
    if coll is None:
        return load(status="open")
    out = []
    try:
        for d in coll.find({"status": "open"}):
            d.pop("_id", None)
            if d.get("superseded") is True:
                continue
            out.append(d)
    except Exception as exc:                       # noqa: BLE001
        log.warning("journal open docs read failed: %s", exc)
        return []
    return out


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
    elif lane == "gajjala":
        add_qty = e.get("add_qty")
        parts.append("🚩 Gajjala lane entry (paper Auto-Pilot, GG's rules)"
                     + (", + breakeven add %s sh" % add_qty if add_qty else "") + ".")
    elif lane == "hot_pullback":
        parts.append("🔥 Hot pullback lane entry (paper Auto-Pilot, owner rules).")
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
        fw = doc.get("fill_wanted")
        if isinstance(fw, dict) and fw:
            parts.append("Sold at market by the engine on %s (%s); the broker's fill is not booked yet."
                         % (_fmt_date(fw.get("ts")), str(fw.get("kind") or "").replace("_", " ")))
        else:
            parts.append("Position open.")
        return " ".join(parts)

    x = doc.get("exit") or {}
    r = doc.get("realized") or {}
    leg = x.get("leg")
    verb = {"take_profit": "Exited via take-profit",
            "stop": "Stopped out",
            "flatten": "Manually flattened",
            "sim_handover": "Booked at SIM paper handover",
            "force_exit": "Sold at market by the engine",
            "lane_exit": "Closed by the 🚩 lane"}.get(leg, "Closed")
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
