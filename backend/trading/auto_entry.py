"""Auto-entry — the engine BUYS Ajay's own SEPA picks (paper first, 2026-06-12).

Candidate funnel (the book lives in the SCANNER, not here):
  sepa.scanner latest scan rows where is_buyable == True (Trend Template p.79
  + Stage 2 + VCP/Power-Play pivot + volume-confirmed breakout, not extended
  past the pivot p.224) AND score >= AUTO_MIN_SCORE AND entry_setup.pivot
  exists. Sorted by score desc. Risk math (stop/target/size/streak) is NOT
  re-derived here either — every buy flows through trading.entries.enter(),
  which uses trading/risk_rules.py (TLSW pp.291-315, page-cited, FROZEN).

Hybrid trigger, two paths per symbol:
  a. INTRADAY        live > pivot, AND the FIRST tick we ever observed
                     live > pivot happened in the first half of the session
                     (cleared_at_frac <= FIRST_HALF_FRACTION, persisted per
                     symbol+ET-day in the auto_entry_state Mongo coll), AND
                     projected RelVol >= AUTO_RELVOL_MIN (sepa.live_gate),
                     AND live <= pivot * (1 + MAX_EXTENSION_PCT/100).
  b. CLOSE-CONFIRM   not entered intraday, prev_day_close > pivot AND
                     live > pivot AND not extended past the same cap ->
                     enter at next-morning ticks. No after-hours machinery.

Safety invariants (same house rules as exit_engine/entries):
  * NEVER places an order at the broker directly — buys flow through
    entries.enter() so armed / sizing / never-average-down / earnings all
    still apply (contract test greps this module for broker order calls).
  * armed=false places NO orders, ever.
  * run() is called from exit_engine.tick() inside try/except — an
    auto-entry crash can never break stop protection.
  * Import-light: no pandas at import time; every sepa import is lazy.

──────────────────────────────────────────────────────────────────────────────
ENGINE PARAMETERS — owner (Ajay) choices for the hybrid trigger, NOT
book-cited numbers. Minervini gives the SETUP and the RISK MATH; he does not
give an entries-per-day cap, a relative-volume floor, a session-half cutoff,
or a dollar cap for a paper trial. These five are engine tuning, locked in
tests/test_trading_contracts.py and documented (with this same honesty note)
in docs/sepa/auto_entry_methodology.md. Changing any of them needs Ajay's
sign-off, not a book page.
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import logging
from typing import Optional

from trading import broker_alpaca as broker
from trading import entries
from trading import risk_rules
from trading.exit_engine import _db, _et_day, _utc_iso, get_config, ledger, update_config

log = logging.getLogger("trading.auto_entry")

# Max auto buys per ET day — observation-friendly pace for the paper week.
MAX_AUTO_ENTRIES_PER_DAY = 2
# Projected full-session relative volume floor for the INTRADAY path
# (sepa.live_gate projects today's pace vs the 50-day average).
AUTO_RELVOL_MIN = 1.5
# The first observed pivot-clear must land in the first half of the session
# (session_fraction <= this) for the intraday path; later clears wait for
# the close-confirmation path.
FIRST_HALF_FRACTION = 0.5
# Buy-zone ceiling above the pivot. MIRRORS sepa.scanner.BUYABLE_MAX_EXT_PCT
# (book p.224 "without chasing ... more than a few percentage points" — no
# exact book number; 3% is the user-approved 2026-06-09 house value). Not
# imported because sepa.scanner pulls pandas at import time; the contract
# test cross-locks both source tokens so they cannot drift apart.
MAX_EXTENSION_PCT = 3.0
# "assume you have 5k" — sizing equity is min(Alpaca equity, this cap) for
# ALL entries (Alpaca paper accounts default to $100k).
DEFAULT_EQUITY_CAP = 5000.0
# Funnel score floor (the scanner's BUY tier starts at 70) — owner choice.
AUTO_MIN_SCORE = 70.0

FUNNEL_CITE = ("funnel: scanner is_buyable (trend template p.79 + stage 2 + "
               "pivot + volume breakout, ext cap p.224) + score>=70; risk math "
               "pp.291-315 via entries/risk_rules")


# ── Lazy sepa seams (each one monkeypatchable in tests) ─────────────────────

def _latest_scan_rows() -> list:
    """Rows of the latest completed SEPA scan — the SAME reader GET /sepa/scan
    uses (sepa.scanner.load_latest -> ~/.cheetah/scans/latest.json; the scan
    is file-persisted, with a separate Mongo history written by sepa.history).
    all_results carries every analyzed symbol; candidates is the slim list."""
    try:
        from sepa import scanner
        latest = scanner.load_latest() or {}
        return latest.get("all_results") or latest.get("candidates") or []
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry: latest scan unavailable: %s", exc)
        return []


def _bulk_live(symbols: list) -> dict:
    """ONE batched live-quote call for every surviving candidate per tick
    (sepa.prices.bulk_live_prices: {SYM: {price, volume, prev_day_close,...}})."""
    if not symbols:
        return {}
    try:
        from sepa.prices import bulk_live_prices
        return bulk_live_prices(list(symbols)) or {}
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry: bulk live prices failed: %s", exc)
        return {}


def _session_fraction() -> float:
    """Fraction of the 9:30-16:00 ET session elapsed (sepa.live_gate)."""
    try:
        from sepa.live_gate import session_fraction
        return float(session_fraction())
    except Exception as exc:                       # noqa: BLE001
        log.debug("auto_entry: session_fraction failed: %s", exc)
        return 0.0


def _projected_relvol(symbol: str) -> Optional[float]:
    """Projected full-session RelVol from sepa.live_gate — called ONLY for
    names that already passed every cheap check (it reloads daily prices)."""
    try:
        from sepa.live_gate import live_gate
        out = live_gate(symbol) or {}
        rv = (out.get("volume_live") or {}).get("projected_relvol")
        return float(rv) if rv is not None else None
    except Exception as exc:                       # noqa: BLE001
        log.debug("auto_entry: live_gate relvol failed %s: %s", symbol, exc)
        return None


def _gauge_state() -> str:
    """RAW Market Gauge state ('constructive'|'caution'|'risk_off') — the
    same underlying read exit_engine.regime() maps to normal/difficult, but
    auto-entry vetoes on the raw 'risk_off' verdict itself. Unavailable
    gauge degrades to '' (no veto), matching regime()'s degrade-to-normal."""
    try:
        from sepa.market_gauge import get_gauge
        return str((get_gauge(prefer_persisted=True) or {}).get("state") or "").lower()
    except Exception as exc:                       # noqa: BLE001
        log.debug("auto_entry: gauge unavailable: %s", exc)
        return ""


def _earnings_days(symbol: str) -> Optional[int]:
    """Days to the next earnings event — the SAME helper entries.py uses
    (sepa.earnings_watch.next_event). None = no known upcoming event."""
    try:
        from sepa.earnings_watch import next_event
        ev = next_event(symbol)
        return ev.get("days_to") if ev else None
    except Exception as exc:                       # noqa: BLE001
        log.debug("auto_entry: earnings lookup failed %s: %s", symbol, exc)
        return None


def _notify(kind: str, ticker: str, detail: str) -> None:
    """Owner push (push.hooks.notify_autopilot). Failures logged + swallowed."""
    try:
        from push.hooks import notify_autopilot
        notify_autopilot(kind, ticker, detail)
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry: push failed (%s %s): %s", kind, ticker, exc)


# ── auto_entry_state (per symbol + ET day) ──────────────────────────────────

def _state_coll():
    db = _db()
    return None if db is None else db.auto_entry_state


def _get_state(symbol: str, day: str) -> dict:
    coll = _state_coll()
    if coll is None:
        return {}
    try:
        return coll.find_one({"symbol": symbol, "date": day}) or {}
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry_state read failed %s: %s", symbol, exc)
        return {}


def _set_state(symbol: str, day: str, **fields) -> None:
    coll = _state_coll()
    if coll is None:
        return
    fields["updated_at"] = _utc_iso()
    try:
        coll.update_one({"symbol": symbol, "date": day},
                        {"$set": fields}, upsert=True)
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry_state write failed %s: %s", symbol, exc)


def _entries_today(day: str) -> int:
    coll = _state_coll()
    if coll is None:
        return 0
    try:
        return sum(1 for _ in coll.find({"date": day, "entered": True}))
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry_state count failed: %s", exc)
        return 0


def _today_snapshots(day: str) -> list:
    coll = _state_coll()
    rows = []
    if coll is None:
        return rows
    try:
        for d in coll.find({"date": day}):
            d.pop("_id", None)
            rows.append(d)
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry_state list failed: %s", exc)
    return rows


# ── Funnel + trigger pieces ─────────────────────────────────────────────────

def _candidates() -> list:
    """Latest-scan rows passing the funnel, score desc."""
    out = []
    for r in _latest_scan_rows():
        try:
            if not r.get("is_buyable"):
                continue
            score = float(r.get("score") or 0)
            pivot = (r.get("entry_setup") or {}).get("pivot")
            if score < AUTO_MIN_SCORE or not pivot or float(pivot) <= 0:
                continue
            sym = (r.get("symbol") or "").strip().upper()
            if sym:
                out.append(r)
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda r: float(r.get("score") or 0), reverse=True)
    return out


def _structural_stop_pct(row: dict, live: float) -> Optional[float]:
    """The scan row's entry_setup.stop as a stop_pct request — passed to
    entries.enter ONLY when it is BETWEEN 1% and risk_rules.DEFAULT_STOP_PCT
    below the live price (structure stop tighter than the band default =
    allowed; wider = ignored, band default applies)."""
    stop = (row.get("entry_setup") or {}).get("stop")
    try:
        stop = float(stop)
    except (TypeError, ValueError):
        return None
    if not live or live <= 0 or stop <= 0 or stop >= live:
        return None
    dist = (live - stop) / live * 100.0
    if 1.0 <= dist <= risk_rules.DEFAULT_STOP_PCT:
        return round(dist, 2)
    return None


def _check(checks: dict, name: str, ok: bool, value=None) -> bool:
    checks[name] = {"pass": bool(ok), "value": value}
    return bool(ok)


def _ledger_disabled_once(cfg: dict, gate: dict) -> bool:
    """One auto_entry_disabled ledger row per ET day max (no tick spam)."""
    today = _et_day()
    if cfg.get("last_auto_entry_disabled_day") == today:
        return False
    ledger("auto_entry_disabled",
           detail={"gate": gate,
                   "hint": "needs configured + armed + auto_entry flag + market open"})
    update_config(last_auto_entry_disabled_day=today)
    return True


# ── The per-tick runner (called from exit_engine.tick, AFTER exits) ─────────

def run(broker=None, cfg: Optional[dict] = None) -> dict:
    """Evaluate every funnel candidate once; place at most
    MAX_AUTO_ENTRIES_PER_DAY buys via entries.enter(). Returns a summary.

    The `broker` param shadows the module-level import on purpose (tick()
    passes its own — possibly monkeypatched — reference); the globals()
    fallback resolves the module attribute so test monkeypatching of
    AE.broker works when called with no args."""
    brk = broker if broker is not None else globals()["broker"]
    cfg = cfg or get_config()
    day = _et_day()
    out = {"ok": True, "ran": False, "day": day, "entered": [], "blocked": [],
           "evaluated": 0, "entries_today": 0, "errors": []}

    # Master gate: configured AND armed AND auto_entry flag AND market open.
    gate = {"configured": bool(brk.configured()),
            "armed": bool(cfg.get("armed")),
            "auto_entry": bool(cfg.get("auto_entry")),
            "market_open": False}
    if gate["configured"]:
        try:
            gate["market_open"] = bool(brk.clock().get("is_open"))
        except Exception as exc:                   # noqa: BLE001
            out["errors"].append("clock: %s" % exc)
    if not all(gate.values()):
        _ledger_disabled_once(cfg, gate)
        out["reason"] = "gated"
        out["gate"] = gate
        return out
    out["ran"] = True

    cands = _candidates()
    if not cands:
        out["reason"] = "no_candidates"
        return out

    try:
        positions = brk.positions()
    except Exception as exc:                       # noqa: BLE001
        out["ok"] = False
        out["errors"].append("positions: %s" % exc)
        return out
    held = {(p.get("symbol") or "").upper() for p in positions}
    pos_count = len(positions)
    entries_today = _entries_today(day)
    gauge = _gauge_state()

    # Cheap-first pass (no quotes needed) — survivors get ONE batched quote.
    survivors = []
    for row in cands:
        sym = (row.get("symbol") or "").upper()
        out["evaluated"] += 1
        st = _get_state(sym, day)
        checks = {}
        ok = _check(checks, "not_already_held", sym not in held, sym in held)
        ok &= _check(checks, "not_attempted_today",
                     not (st.get("entered") or st.get("attempted")),
                     bool(st.get("entered") or st.get("attempted")))
        ok &= _check(checks, "position_slots",
                     pos_count < risk_rules.MAX_POSITIONS, pos_count)
        ok &= _check(checks, "daily_cap",
                     entries_today < MAX_AUTO_ENTRIES_PER_DAY, entries_today)
        ok &= _check(checks, "gauge_not_risk_off", gauge != "risk_off", gauge)
        edays = _earnings_days(sym)
        ok &= _check(checks, "earnings_shield",
                     edays is None or edays > entries.EARNINGS_SHIELD_DAYS, edays)
        if ok:
            survivors.append((row, checks))
        elif not (st.get("entered") or st.get("attempted")):
            # Snapshot the skip — but NEVER overwrite a terminal snapshot
            # (entered / blocked / error): once attempted, the trigger-time
            # eval is the informative one and must survive later ticks.
            _set_state(sym, day,
                       last_eval={"ts": _utc_iso(), "score": row.get("score"),
                                  "pivot": (row.get("entry_setup") or {}).get("pivot"),
                                  "checks": checks, "result": "skipped"})

    quotes = _bulk_live([(r.get("symbol") or "").upper() for r, _ in survivors])
    frac = _session_fraction()

    for row, checks in survivors:
        sym = (row.get("symbol") or "").upper()
        pivot = float((row.get("entry_setup") or {}).get("pivot"))
        q = quotes.get(sym) or {}
        live = q.get("price") or q.get("last_trade_price")
        prev_close = q.get("prev_day_close")
        result = "skipped"

        # Re-check the MUTABLE caps — entries placed earlier in THIS tick
        # consume daily-cap and position slots after the cheap pass ran.
        cap_ok = _check(checks, "daily_cap",
                        entries_today < MAX_AUTO_ENTRIES_PER_DAY, entries_today)
        slot_ok = _check(checks, "position_slots",
                         pos_count < risk_rules.MAX_POSITIONS, pos_count)
        if not (cap_ok and slot_ok):
            _set_state(sym, day,
                       last_eval={"ts": _utc_iso(), "score": row.get("score"),
                                  "pivot": pivot, "checks": checks,
                                  "result": result})
            continue

        if not _check(checks, "live_quote", bool(live), live):
            _set_state(sym, day,
                       last_eval={"ts": _utc_iso(), "score": row.get("score"),
                                  "pivot": pivot, "checks": checks,
                                  "result": result})
            continue
        live = float(live)

        # First-ever pivot clear today -> persist the session fraction.
        st = _get_state(sym, day)
        cleared_frac = st.get("cleared_at_frac")
        above = live > pivot
        if above and cleared_frac is None:
            cleared_frac = round(frac, 4)
            _set_state(sym, day,
                       cleared_at_frac=cleared_frac)

        extended = live > pivot * (1 + MAX_EXTENSION_PCT / 100.0)
        _check(checks, "live_above_pivot", above,
               {"live": live, "pivot": pivot})
        _check(checks, "not_extended", not extended,
               round((live / pivot - 1) * 100, 2) if pivot else None)

        path = None
        relvol = None
        if above and not extended:
            # path a — intraday: first-half clear + projected RelVol floor
            first_half = (cleared_frac is not None
                          and cleared_frac <= FIRST_HALF_FRACTION)
            _check(checks, "cleared_first_half", first_half, cleared_frac)
            if first_half:
                relvol = _projected_relvol(sym)
                if _check(checks, "relvol", relvol is not None
                          and relvol >= AUTO_RELVOL_MIN, relvol):
                    path = "intraday"
            # path b — close-confirmation: prior close already above pivot
            if path is None:
                cc = bool(prev_close) and float(prev_close) > pivot
                _check(checks, "close_confirm", cc, prev_close)
                if cc:
                    path = "close_confirm"

        if path is None:
            _set_state(sym, day,
                       last_eval={"ts": _utc_iso(), "score": row.get("score"),
                                  "pivot": pivot, "checks": checks,
                                  "result": result})
            continue

        # Triggered -> buy through the ONLY buy path (entries.enter applies
        # armed / sizing / equity cap / never-average-down / earnings again;
        # NO earnings override in auto mode).
        trigger = {"path": path, "pivot": pivot, "live": live,
                   "relvol": relvol, "cleared_at_frac": cleared_frac,
                   "prev_day_close": prev_close}
        stop_req = _structural_stop_pct(row, live)
        _set_state(sym, day, attempted=True)
        try:
            res = entries.enter(sym, limit_price=None, stop_pct=stop_req,
                                allow_earnings=False)
            entries_today += 1
            pos_count += 1
            result = "entered"
            out["entered"].append(sym)
            detail = dict(trigger)
            detail.update({"score": row.get("score"),
                           "stop_pct_requested": stop_req, "order": res})
            ledger("auto_entry", symbol=sym, detail=detail, dry_run=False,
                   cite=FUNNEL_CITE)
            _set_state(sym, day, entered=True,
                       path=path)
            _notify("auto_entry", sym,
                    "Auto-entry %s (%s): %d sh, pivot %.2f, live %.2f"
                    % (sym, path, (res or {}).get("shares") or 0, pivot, live))
        except ValueError as exc:
            # Otherwise-triggered but vetoed by the entry path — ledger the
            # first veto of the day per symbol (dry_run-style), not every tick.
            result = "blocked"
            out["blocked"].append(sym)
            if not st.get("blocked_ledgered"):
                ledger("auto_entry_blocked", symbol=sym,
                       detail=dict(trigger, reason=str(exc)), dry_run=True,
                       cite=FUNNEL_CITE)
                _set_state(sym, day,
                           blocked_ledgered=True)
        except Exception as exc:                   # noqa: BLE001
            # Unexpected (non-veto) failure — attempted=True already set, so
            # this fires AT MOST once per symbol per ET day (no retry loop)
            # and must be VISIBLE: a broker order may or may not exist, so
            # surface it in the ledger, never just in the tick summary.
            result = "error"
            out["errors"].append("%s: %s" % (sym, exc))
            ledger("auto_entry_error", symbol=sym,
                   detail=dict(trigger, error=str(exc),
                               hint="unexpected failure after trigger — "
                                    "verify at Alpaca whether an order exists"),
                   dry_run=False, cite=FUNNEL_CITE)

        _set_state(sym, day,
                   last_eval={"ts": _utc_iso(), "score": row.get("score"),
                              "pivot": pivot, "checks": checks,
                              "result": result})

    out["entries_today"] = entries_today
    return out


# ── Status block (rides in GET /trading/status) ─────────────────────────────

def status_block(cfg: Optional[dict] = None) -> dict:
    cfg = cfg or get_config()
    day = _et_day()
    return {"enabled": bool(cfg.get("auto_entry")),
            "equity_cap": cfg.get("equity_cap"),
            "entries_today": _entries_today(day),
            "max_per_day": MAX_AUTO_ENTRIES_PER_DAY,
            "candidates": _today_snapshots(day)}
