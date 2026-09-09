"""Auto-Pilot lane — 🔥 Hot Pullback (PAPER).

Ajay 2026-09-09: *"Can you make sure we paper trade this in autopilot too?"*

WHAT IT TRADES. Yesterday's `supply_demand.hot_pullback` signals, entered at
TODAY'S OPEN. That entry is not a convenience — it is the one the study
measured best, because the signal day gaps DOWN into the next open 60% of the
time (median -0.53%), so the morning fill is cheaper than the close the signal
printed at:

    entry at the signal-day close   +1.60% median by the next close, 62% up
    entry at the NEXT OPEN          +2.40% median by that close, +2.85% by
                                    day two, 66% up
    (placebo: +0.05% / +0.19%)

THE HORIZON IS THE RULE, NOT A PREFERENCE. The measured edge is gone by day
five (fwd5 +0.39%, 51% up, p=0.450 against a bootstrapped placebo). So this
lane closes on TIME after `MAX_HOLD_SESSIONS`, whatever the P&L, the same way
the 0DTE lane closes on the clock. A lane that held these would be trading a
different, unmeasured thing.

STOP. 0.5% under the signal day's LOW — the low that actually tagged the demand
band. If that gives way, the reason for the trade is gone. Measured on the
trigger variant, 17% were stopped inside three sessions.

SIZE. The risk from the signal close to that stop averaged ~17% on the
archetype, which is far outside the engine's normal stop budget. The lane
therefore sizes by RISK, not by a share count, and refuses anything whose stop
distance exceeds `MAX_STOP_PCT` — `entries.enter` would refuse it anyway
(risk_rules), and refusing here first makes the journal say why.

PAPER ONLY. The lane gates itself off on a live broker, like the 0DTE lane.
The study is 65 events with a worst three-day of -36.1%; that is not a record
to put real money behind, and Ajay's own Rule #10 says a new S&D rule proves
itself as a named paper variant before promotion. Journal tag: `hot_pullback`.

NOT ADVICE.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("trading.hot_pullback_entry")

ET = ZoneInfo("America/New_York")
STRATEGY = "hot_pullback"

# ── the lane's owner constants ─────────────────────────────────────────────
ENTRY_OPEN_ET = (9, 30)         # act at the open — the measured entry
LAST_ENTRY_ET = (10, 0)         # ...and only in the first half hour
MAX_ENTRIES_PER_DAY = 2         # the setup fired 65 times in 2 years; 2 is generous
MAX_OPEN = 3
MAX_STOP_PCT = 20.0             # a flush-day low can sit far under the close
MAX_HOLD_SESSIONS = 3           # the edge is gone by day 5 — exit on time
SIGNAL_MAX_AGE_SESSIONS = 1     # only YESTERDAY's flush; a stale one is a different trade

LEDGER_KINDS = ("hot_pullback_entry", "hot_pullback_skip",
                "hot_pullback_exit", "hot_pullback_disabled")


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


def _now_et(now: Optional[datetime] = None) -> datetime:
    return now or datetime.now(tz=ET)


# ── pure reads (all unit-tested) ───────────────────────────────────────────
def in_entry_window(now: Optional[datetime] = None) -> bool:
    """The lane acts only in the first half hour. Entry IS the open."""
    n = _now_et(now)
    mins = n.hour * 60 + n.minute
    return (ENTRY_OPEN_ET[0] * 60 + ENTRY_OPEN_ET[1]) <= mins <= (LAST_ENTRY_ET[0] * 60 + LAST_ENTRY_ET[1])


def signal_is_fresh(signal_date: str, today: str, sessions_between) -> bool:
    """True when the flush was the PREVIOUS session.

    `sessions_between(a, b)` counts trading sessions between two ET dates and is
    injected so the test does not need a market calendar. A two-day-old flush is
    not this setup: the study entered at the very next open.
    """
    if not signal_date or not today or signal_date >= today:
        return False
    try:
        gap = int(sessions_between(signal_date, today))
    except Exception:
        return False
    return 1 <= gap <= SIGNAL_MAX_AGE_SESSIONS


def stop_for(signal_low) -> Optional[float]:
    """0.5% under the signal day's low — the low that tagged the band."""
    lo = _f(signal_low)
    if lo is None or lo <= 0:
        return None
    return round(lo * 0.995, 2)


def stop_pct_from(entry_px, stop_px) -> Optional[float]:
    e, s = _f(entry_px), _f(stop_px)
    if e is None or s is None or e <= 0 or s <= 0 or s >= e:
        return None
    return round((e - s) / e * 100.0, 2)


def sizable(entry_px, stop_px) -> tuple:
    """(ok, reason). The stop must be real and inside the lane's budget."""
    pct = stop_pct_from(entry_px, stop_px)
    if pct is None:
        return False, "no usable stop under the entry"
    if pct > MAX_STOP_PCT:
        return False, (f"the signal-day low sits {pct:g}% under the open — "
                       f"past the lane's {MAX_STOP_PCT:g}% stop budget")
    return True, None


def should_exit(held_sessions, last_px, stop_px, target_px) -> Optional[str]:
    """Why to close, or None. Order matters: the stop first, then the target,
    then the CLOCK — because the clock is the measured edge boundary and must
    never be skipped in favour of hoping."""
    px = _f(last_px)
    st = _f(stop_px)
    tg = _f(target_px)
    if px is not None and st is not None and px <= st:
        return f"stop {st:g} hit — the low that tagged the band gave way"
    if px is not None and tg is not None and px >= tg:
        return f"target {tg:g} reached — the 21-day line the flush fell from"
    try:
        held = int(held_sessions)
    except (TypeError, ValueError):
        return None
    if held >= MAX_HOLD_SESSIONS:
        return (f"{held} sessions held — the measured edge is gone by day 5, "
                f"so the lane exits on time")
    return None


def narrative(row: dict, entry_px, stop_px, target_px) -> str:
    """The why-line on the ledger row, in the same voice as the board."""
    sym = row.get("symbol") or "?"
    band = row.get("band") or {}
    rev = row.get("reversal") or {}
    bits = [f"{sym}: flushed {row.get('flush_pct')}% off its 10-day high"]
    if row.get("under_ma21_pct") is not None:
        bits.append(f"closed {row['under_ma21_pct']}% under the 21-day line")
    if band.get("lo") is not None:
        bits.append(f"the low tagged demand {band['lo']}-{band['hi']}")
    if rev.get("off_low_pct") is not None:
        bits.append(f"then closed +{rev['off_low_pct']}% off it")
    tail = (f"Bought the next open at {entry_px}, stop {stop_px} under the signal low, "
            f"target {target_px} (the 21-day line), out after {MAX_HOLD_SESSIONS} sessions.")
    return "; ".join(bits) + ". " + tail


def gate(config: dict, broker_mode: str, market_open: bool) -> dict:
    """Everything that has to be true before the lane may place anything."""
    enabled = config.get("hot_pullback_entry")
    enabled = True if enabled is None else bool(enabled)
    paper = str(broker_mode or "").lower() != "live"
    return {
        "enabled": enabled,
        "paper": paper,
        "market_open": bool(market_open),
        "ok": bool(enabled and paper and market_open),
        "why": (None if enabled else "lane switched off")
               or (None if paper else "live broker — this lane is paper only")
               or (None if market_open else "market closed"),
    }


def status(config: dict, broker_mode: str, entries_today: int, open_n: int) -> dict:
    """The block `/trading/status` carries and the tab renders."""
    g = gate(config, broker_mode, True)
    return {
        "strategy": STRATEGY,
        "enabled": g["enabled"],
        "paper": g["paper"],
        "entries_today": int(entries_today or 0),
        "max_per_day": MAX_ENTRIES_PER_DAY,
        "max_open": MAX_OPEN,
        "entry_window": f"{ENTRY_OPEN_ET[0]:02d}:{ENTRY_OPEN_ET[1]:02d}–{LAST_ENTRY_ET[0]:02d}:{LAST_ENTRY_ET[1]:02d}",
        "max_hold_sessions": MAX_HOLD_SESSIONS,
        "max_stop_pct": MAX_STOP_PCT,
        "rules": [
            "Buys YESTERDAY's 🔥 Hot Pullback signals at TODAY's open — the entry the study measured best.",
            f"Stop 0.5% under the signal day's low; the lane refuses a stop wider than {MAX_STOP_PCT:g}%.",
            f"Closes on TIME after {MAX_HOLD_SESSIONS} sessions — the measured edge is gone by day 5.",
            "Paper only: a live broker gates the lane off. 65 events with a worst 3-day of -36% is not a live record.",
        ],
    }


# ── state ──────────────────────────────────────────────────────────────────
def _coll(name: str):
    """Mongo collection or None. `getattr`, not `db[name]`: the test FakeDB is
    attribute-style (the 0DTE lane's 2026-09-08 lesson)."""
    try:
        from sepa import prices
        c = prices._get_mongo()
        db = c.database if c is not None else None
        return getattr(db, name) if db is not None else None
    except Exception:                                          # pragma: no cover
        return None


def _today_et(now: Optional[datetime] = None) -> str:
    return _now_et(now).date().isoformat()


def _ledger(kind: str, symbol: Optional[str], detail: dict) -> None:
    c = _coll("trade_ledger")
    if c is None:
        return
    try:
        c.insert_one({"kind": kind, "strategy": STRATEGY, "symbol": symbol,
                      "ts": datetime.now(tz=ET).isoformat(timespec="seconds"),
                      "date_et": _today_et(), **detail})
    except Exception as exc:                                   # pragma: no cover
        log.warning("hot_pullback ledger write failed: %s", exc)


def _open_positions() -> list:
    c = _coll("hot_pullback_positions")
    if c is None:
        return []
    try:
        return list(c.find({"status": "open"}))
    except Exception:                                          # pragma: no cover
        return []


def _entries_today() -> int:
    c = _coll("hot_pullback_positions")
    if c is None:
        return 0
    try:
        return int(c.count_documents({"entry_date": _today_et()}))
    except Exception:                                          # pragma: no cover
        return 0


def _sessions_between_factory():
    """A session counter backed by the shared price cache — no calendar needed:
    the number of cached daily bars between two dates IS the session count."""
    from sepa import prices
    coll = prices._get_mongo()

    def between(a: str, b: str) -> int:
        if coll is None:
            return 1 if a < b else 0
        try:
            doc = coll.find_one({"symbol": "SPY"}, {"bars.date": 1, "_id": 0})
            days = [str(x.get("date"))[:10] for x in (doc or {}).get("bars") or []]
            return sum(1 for d in days if a < d <= b)
        except Exception:                                      # pragma: no cover
            return 1 if a < b else 0

    return between


# ── the tick ───────────────────────────────────────────────────────────────
def run(broker=None, cfg: Optional[dict] = None, now: Optional[datetime] = None) -> dict:
    """Close what is due, then buy yesterday's signals at today's open.

    Never raises past its own fence — the engine wraps this too, but a lane
    that throws is a lane that stops managing its open risk.
    """
    cfg = cfg or {}
    out = {"strategy": STRATEGY, "closed": [], "entered": [], "skipped": []}
    try:
        mode = broker.mode() if broker is not None and hasattr(broker, "mode") else "paper"
    except Exception:                                          # pragma: no cover
        mode = "paper"
    try:
        from market_hours import gate as mh
        market_open = mh.closed_reason(_now_et(now)) is None
    except Exception:                                          # pragma: no cover
        market_open = True

    g = gate(cfg, mode, market_open)
    out["gate"] = g
    if not g["ok"]:
        if g["enabled"] and not g["paper"]:
            day = _today_et(now)
            if cfg.get("last_hot_pullback_disabled_day") != day:
                _ledger("hot_pullback_disabled", None, {"why": g["why"]})
        return out

    # ── 1. manage what is open ─────────────────────────────────────────────
    between = _sessions_between_factory()
    positions = _open_positions()
    for p in positions:
        try:
            last = None
            if broker is not None and hasattr(broker, "last_price"):
                last = _f(broker.last_price(p["symbol"]))
            if last is None:
                from sepa import prices
                last = _f((prices.bulk_snapshot([p["symbol"]]).get(p["symbol"]) or {}).get("close"))
            held = between(p.get("entry_date") or "", _today_et(now))
            why = should_exit(held, last, p.get("stop"), p.get("target"))
            if not why:
                continue
            if broker is not None and hasattr(broker, "close_position"):
                broker.close_position(p["symbol"])
            c = _coll("hot_pullback_positions")
            if c is not None:
                c.update_one({"_id": p["_id"]},
                             {"$set": {"status": "closed", "close_reason": why,
                                       "closed_ts": _now_et(now).isoformat(timespec="seconds"),
                                       "exit_price": last, "held_sessions": held}})
            _ledger("hot_pullback_exit", p["symbol"], {"why": why, "price": last, "held": held})
            out["closed"].append({"symbol": p["symbol"], "why": why})
        except Exception as exc:                               # noqa: BLE001
            log.warning("hot_pullback: closing %s failed: %s", p.get("symbol"), exc)

    # ── 2. look for new entries, but only at the open ──────────────────────
    if not in_entry_window(now):
        out["note"] = "outside the entry window — this lane buys the open"
        return out
    entries_today = _entries_today()
    open_n = len(_open_positions())
    if entries_today >= MAX_ENTRIES_PER_DAY or open_n >= MAX_OPEN:
        out["note"] = f"caps: {entries_today}/{MAX_ENTRIES_PER_DAY} today, {open_n}/{MAX_OPEN} open"
        return out

    try:
        from supply_demand import hot_pullback as HP
        board = HP.cached_or_warm()
    except Exception as exc:                                   # noqa: BLE001
        log.warning("hot_pullback: board read failed: %s", exc)
        return out
    today = _today_et(now)
    held_syms = {p["symbol"] for p in _open_positions()}

    from trading import entries as TE
    for row in (board.get("rows") or []):
        if entries_today >= MAX_ENTRIES_PER_DAY or open_n >= MAX_OPEN:
            break
        sym = row.get("symbol")
        if not sym or sym in held_syms:
            continue
        if not signal_is_fresh(str(row.get("date") or ""), today, between):
            out["skipped"].append({"symbol": sym, "why": "signal is not yesterday's flush"})
            continue
        entry_px = None
        try:
            from sepa import prices
            entry_px = _f((prices.bulk_snapshot([sym]).get(sym) or {}).get("open"))
        except Exception:                                      # pragma: no cover
            pass
        entry_px = entry_px or _f(row.get("close"))
        stop = stop_for(row.get("low"))
        ok, why = sizable(entry_px, stop)
        if not ok:
            _ledger("hot_pullback_skip", sym, {"why": why})
            out["skipped"].append({"symbol": sym, "why": why})
            continue
        target = _f((row.get("plan") or {}).get("target"))
        note = narrative(row, entry_px, stop, target)
        try:
            res = TE.enter(sym, stop_price=stop, strategy=STRATEGY,
                           reason={"lane": STRATEGY, "why": note,
                                   "signal_date": row.get("date"),
                                   "flush_pct": row.get("flush_pct"),
                                   "band": row.get("band")})
        except ValueError as exc:
            _ledger("hot_pullback_skip", sym, {"why": str(exc)})
            out["skipped"].append({"symbol": sym, "why": str(exc)})
            continue
        except Exception as exc:                               # noqa: BLE001
            log.warning("hot_pullback: enter %s failed: %s", sym, exc)
            continue
        c = _coll("hot_pullback_positions")
        if c is not None:
            try:
                c.insert_one({"symbol": sym, "status": "open", "strategy": STRATEGY,
                              "entry_date": today, "entry_price": entry_px,
                              "stop": stop, "target": target,
                              "signal_date": row.get("date"), "signal_low": row.get("low"),
                              "flush_pct": row.get("flush_pct"),
                              "under_ma21_pct": row.get("under_ma21_pct"),
                              "band": row.get("band"), "narrative": note,
                              "order": (res or {}).get("order_id")})
            except Exception as exc:                           # pragma: no cover
                log.warning("hot_pullback: position write failed: %s", exc)
        _ledger("hot_pullback_entry", sym, {"price": entry_px, "stop": stop,
                                            "target": target, "why": note})
        out["entered"].append({"symbol": sym, "price": entry_px, "stop": stop, "target": target})
        entries_today += 1
        open_n += 1
        held_syms.add(sym)
    return out
