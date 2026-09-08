"""0DTE paper lane — same-day options on Signal Lab tags (Ajay 2026-09-08).

Ajay: "Can you also help me with doing options ODTE and Same day expire day
trading options please? I would like to see the accuracy and quick ness with
everything we have setup" … "Did you start the ODTE options".

OWNER RULES — no book, no cites (day-trading options scope, not Minervini):

  Universe   the 0DTE tab's names (options/zero_dte.UNIVERSE, 13). Only a name
             with a SAME-DAY expiry can trade (SPY/QQQ/IWM daily, the single
             names on their weekly Friday). No same-day chain = journaled skip.
  Signal     Signal Lab's composite 1-min BUY / SELL tag on today's session
             (daytrading/signal_lab.events_from_frame — sweep, then the
             opposite-side structure break; stop = the trap wick, target = 2R).
             BUY -> the tab's call pick, SELL -> the tab's put pick
             (options/zero_dte.pick_contract: delta ~0.35, spread <= 25%,
             volume >= 500, ask >= $0.20). Signal must be fresh: the tag's bar
             closed <= SIGNAL_MAX_AGE_SEC ago. Dealers PINNED -> skip.
  Window     entries 09:45–14:30 ET; everything flat by FLATTEN_ET (15:45).
  Size       premium at risk = min(RISK_PCT_OF_EQUITY % of equity, $MAX_PREMIUM)
             -> whole contracts at the ask; one contract over budget = skip.
  Caps       MAX_ENTRIES_PER_DAY, one entry per name per day, MAX_OPEN open.
  Exits      on the STOCK first (the signal's stop / 2R target), then the
             premium (+PREMIUM_TAKE_PCT% / -PREMIUM_STOP_PCT% off the fill),
             then the clock (FLATTEN_ET). Closes are sell_to_close LIMIT at
             the bid — never a market order on a contract.
  Latency    every row records signal bar close -> seen by the tick -> order
             sent -> broker fill, in seconds. That is the "quickness".
  Paper      the lane refuses a LIVE broker outright (mode() == "live").
             Switch `zero_dte_entry` (default ON, paper); `armed` still gates.

Runs inside the engine tick (trading/exit_engine.py step (l)) every minute in
RTH. State: Mongo `zero_dte_positions` (one doc per trade, the journal) and
`zero_dte_lane_state` (one attempt per (day, symbol, signal bar)). Ledger
events: zero_dte_entry / zero_dte_exit / zero_dte_disabled. Decision support
on a paper account — not advice.
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Optional

from trading.broker import BrokerError, get_broker
from trading.exit_engine import (_db, _et_day, get_config, ledger, update_config)

log = logging.getLogger("trading.zero_dte_lane")

broker = get_broker()    # module-level so tests can monkeypatch ZD.broker

# ── OWNER NUMBERS (locked in tests/test_trading_contracts.py) ────────────────
STRATEGY = "zero_dte"
ENTRY_OPEN_ET = dtime(9, 45)
LAST_ENTRY_ET = dtime(14, 30)
FLATTEN_ET = dtime(15, 45)
SIGNAL_MAX_AGE_SEC = 180          # the tag's bar closed at most 3 minutes ago
RISK_PCT_OF_EQUITY = 0.5
MAX_PREMIUM_PER_TRADE = 500.0
MAX_ENTRIES_PER_DAY = 3
MAX_OPEN = 3
PREMIUM_TAKE_PCT = 100.0          # +100% on the fill -> close
PREMIUM_STOP_PCT = 50.0           # -50% on the fill -> close
ENTRY_FILL_WAIT_SEC = 180         # a day limit not filled in 3 min is cancelled
SKIP_REGIMES = ("PINNED",)

POSITIONS_COLL = "zero_dte_positions"
STATE_COLL = "zero_dte_lane_state"
CITE = ("0DTE paper lane: OWNER RULES, no book (docs/trading_zero_dte_lane.md); "
        "signal = daytrading/signal_lab, contract = options/zero_dte")

ET_OFF = timedelta(hours=-4)


# ── small helpers ─────────────────────────────────────────────────────────────

def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (math.inf, -math.inf):
        return None
    return v


def _utc_iso(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


def _now_et() -> datetime:
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/New_York"))


def _coll(name: str):
    db = _db()
    return None if db is None else getattr(db, name)


def _broker_mode() -> str:
    try:
        return str(broker.mode())
    except Exception:                              # noqa: BLE001
        return "unknown"


def _has_options(brk) -> bool:
    return all(hasattr(brk, k) for k in ("submit_option_order", "option_snapshots"))


def occ_from_ticker(ticker: Optional[str]) -> Optional[str]:
    """Massive option tickers are 'O:' + the OCC symbol Alpaca trades."""
    if not ticker:
        return None
    t = str(ticker).strip()
    return t[2:] if t.upper().startswith("O:") else t


def option_tick(price: float) -> float:
    return 0.01 if price < 3.0 else 0.05


def round_down_tick(price: float) -> float:
    t = option_tick(price)
    return round(math.floor(price / t + 1e-9) * t, 2)


def round_up_tick(price: float) -> float:
    t = option_tick(price)
    return round(math.ceil(price / t - 1e-9) * t, 2)


# ── PURE pieces (unit-tested) ────────────────────────────────────────────────

def in_entry_window(now_et) -> bool:
    t = now_et.time() if hasattr(now_et, "time") else now_et
    return ENTRY_OPEN_ET <= t < LAST_ENTRY_ET


def past_flatten(now_et) -> bool:
    t = now_et.time() if hasattr(now_et, "time") else now_et
    return t >= FLATTEN_ET


def fresh_signal(events: list, frame_index, now_utc: datetime) -> Optional[dict]:
    """The LAST composite buy/sell tag if its bar closed <= SIGNAL_MAX_AGE_SEC
    ago, else None. `frame_index` = the frame's timestamps (tz-aware ET or
    naive UTC); the bar closes one minute after its stamp."""
    tags = [e for e in (events or []) if e.get("kind") in ("buy", "sell")]
    if not tags:
        return None
    ev = tags[-1]
    try:
        stamp = frame_index[int(ev["i"])]
    except Exception:                              # noqa: BLE001
        return None
    stamp = stamp.to_pydatetime() if hasattr(stamp, "to_pydatetime") else stamp
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    bar_close = stamp + timedelta(minutes=1)
    age = (now_utc - bar_close).total_seconds()
    if age < -5 or age > SIGNAL_MAX_AGE_SEC:
        return None
    out = dict(ev)
    out["bar_ts"] = stamp.astimezone(timezone.utc).isoformat()
    out["bar_close_ts"] = bar_close.astimezone(timezone.utc).isoformat()
    out["age_sec"] = round(age, 1)
    return out


def size_contracts(ask: float, equity: float) -> tuple:
    """(qty, budget, reason). Budget = min(RISK_PCT_OF_EQUITY% of equity,
    MAX_PREMIUM_PER_TRADE); whole contracts at the ask."""
    ask, equity = _f(ask), _f(equity)
    if ask is None or ask <= 0 or equity is None or equity <= 0:
        return 0, 0.0, "no ask or no equity"
    budget = min(equity * RISK_PCT_OF_EQUITY / 100.0, MAX_PREMIUM_PER_TRADE)
    qty = int(budget // (ask * 100.0))
    if qty < 1:
        return 0, round(budget, 2), ("one contract costs $%.0f, over the $%.0f budget"
                                     % (ask * 100.0, budget))
    return qty, round(budget, 2), None


def contract_for(row: Optional[dict], side: str) -> tuple:
    """(contract dict, reason). side = 'buy' -> the call pick, 'sell' -> the put."""
    if not row:
        return None, "no same-day chain"
    if str(row.get("regime") or "").upper() in SKIP_REGIMES:
        return None, "dealers %s — no 0DTE entry" % row.get("regime")
    c = row.get("call") if side == "buy" else row.get("put")
    if not c:
        return None, "no tradeable %s on the chain" % ("call" if side == "buy" else "put")
    occ = occ_from_ticker(c.get("ticker"))
    ask, bid = _f(c.get("ask")), _f(c.get("bid"))
    if not occ or ask is None or ask <= 0:
        return None, "contract has no ask"
    out = dict(c)
    out.update({"occ": occ, "otype": "call" if side == "buy" else "put",
                "ask": ask, "bid": bid, "expiry": row.get("expiry")})
    return out, None


def exit_reason(pos: dict, stock_last: Optional[float], mark: Optional[float],
                now_et) -> Optional[str]:
    """First matching exit, in the owner's order: clock, stock stop, stock
    target, premium stop, premium take. None = hold."""
    if past_flatten(now_et):
        return "flatten %s ET (0DTE never held into the last 15 minutes)" % FLATTEN_ET.strftime("%H:%M")
    sig = pos.get("signal") or {}
    stop, target = _f(sig.get("stop")), _f(sig.get("target"))
    side = pos.get("side")
    px = _f(stock_last)
    if px is not None:
        if side == "call":
            if stop is not None and px <= stop:
                return "stock %.2f hit the signal stop %.2f" % (px, stop)
            if target is not None and px >= target:
                return "stock %.2f hit the 2R target %.2f" % (px, target)
        else:
            if stop is not None and px >= stop:
                return "stock %.2f hit the signal stop %.2f" % (px, stop)
            if target is not None and px <= target:
                return "stock %.2f hit the 2R target %.2f" % (px, target)
    fill = _f(pos.get("fill_price")) or _f(pos.get("limit_price"))
    m = _f(mark)
    if fill and m is not None and fill > 0:
        chg = (m / fill - 1.0) * 100.0
        if chg <= -PREMIUM_STOP_PCT:
            return "premium %+.0f%% (bid %.2f vs fill %.2f)" % (chg, m, fill)
        if chg >= PREMIUM_TAKE_PCT:
            return "premium %+.0f%% (bid %.2f vs fill %.2f)" % (chg, m, fill)
    return None


def latency(pos: dict) -> dict:
    """Seconds between the stages, from the doc's stamps (None where unknown)."""
    def _p(k):
        v = pos.get(k)
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00")) if v else None
        except ValueError:
            return None
    sig = _p("signal_bar_close_ts") or _p("bar_close_ts")
    seen, sent, fill = _p("seen_ts"), _p("order_ts"), _p("fill_ts")
    def _d(a, b):
        return round((b - a).total_seconds(), 1) if a and b else None
    return {"signal_to_seen_sec": _d(sig, seen), "seen_to_order_sec": _d(seen, sent),
            "order_to_fill_sec": _d(sent, fill), "signal_to_fill_sec": _d(sig, fill)}


def narrative(pos: dict) -> str:
    sig, c = pos.get("signal") or {}, pos.get("contract") or {}
    side = "call" if pos.get("side") == "call" else "put"
    lat = latency(pos)
    parts = ["%s %s × %s %s $%s %s @ $%s ask" % (
        "Bought" if pos.get("status") != "missed" else "Tried",
        pos.get("qty") or "?", pos.get("symbol"), pos.get("expiry") or "same-day",
        c.get("strike"), side, pos.get("limit_price"))]
    parts.append("Signal Lab %s tag at %s (stock %s, stop %s, target %s = 2R)" % (
        str(sig.get("kind") or "").upper(), _et_hhmm(pos.get("signal_bar_close_ts")),
        sig.get("price"), sig.get("stop"), sig.get("target")))
    if c.get("delta") is not None:
        parts.append("contract: delta %s, spread %s%%, needs %sx the expected move (%s%%) to double, dealers %s"
                     % (c.get("delta"), c.get("spread_pct"), c.get("moves_needed"),
                        pos.get("expected_move_pct"), pos.get("regime") or "?"))
    if pos.get("fill_price") is not None:
        parts.append("filled $%s at %s (signal→fill %ss)" % (
            pos.get("fill_price"), _et_hhmm(pos.get("fill_ts")), lat.get("signal_to_fill_sec")))
    elif pos.get("status") == "missed":
        parts.append("never filled — cancelled after %ds" % ENTRY_FILL_WAIT_SEC)
    if pos.get("status") == "closed":
        parts.append("closed %s: %s — out at $%s, %s (stock %s%%)" % (
            _et_hhmm(pos.get("closed_ts")), pos.get("close_reason"), pos.get("exit_price"),
            _money(pos.get("realized_pnl")), pos.get("stock_move_pct")))
    elif pos.get("status") == "closing":
        parts.append("closing: %s" % pos.get("close_reason"))
    return ". ".join(p for p in parts if p) + "."


def _et_hhmm(iso) -> str:
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (d.astimezone(timezone.utc) + ET_OFF).strftime("%H:%M:%S")
    except (TypeError, ValueError):
        return "?"


def _money(v) -> str:
    v = _f(v)
    return "P&L ?" if v is None else ("P&L %+.0f" % v)


# ── state ────────────────────────────────────────────────────────────────────

def _open_positions() -> Optional[list]:
    coll = _coll(POSITIONS_COLL)
    if coll is None:
        return None
    try:
        return [d for d in coll.find({"status": {"$in": ["open", "closing"]}})]
    except Exception as exc:                       # noqa: BLE001
        log.warning("zero_dte_lane: positions read failed: %s", exc)
        return None


def _recent(limit: int = 40) -> list:
    coll = _coll(POSITIONS_COLL)
    if coll is None:
        return []
    try:
        return [d for d in coll.find({"status": {"$in": ["closed", "missed"]}})
                .sort("closed_ts", -1).limit(limit)]
    except Exception as exc:                       # noqa: BLE001
        log.warning("zero_dte_lane: closed read failed: %s", exc)
        return []


def _save(doc: dict) -> bool:
    coll = _coll(POSITIONS_COLL)
    if coll is None:
        return False
    try:
        d = dict(doc)
        d.pop("_id", None)
        coll.update_one({"pos_id": d["pos_id"]}, {"$set": d}, upsert=True)
        return True
    except Exception as exc:                       # noqa: BLE001
        log.warning("zero_dte_lane: position write failed: %s", exc)
        return False


def _attempts_today(day: str) -> Optional[list]:
    coll = _coll(STATE_COLL)
    if coll is None:
        return None
    try:
        return [d for d in coll.find({"date": day})]
    except Exception as exc:                       # noqa: BLE001
        log.warning("zero_dte_lane: state read failed: %s", exc)
        return None


def _record_attempt(day: str, symbol: str, key: str, result: str, reason: Optional[str],
                    detail: Optional[dict] = None) -> None:
    coll = _coll(STATE_COLL)
    if coll is None:
        return
    try:
        coll.update_one({"key": key},
                        {"$set": {"key": key, "date": day, "symbol": symbol, "result": result,
                                  "reason": reason, "ts": _utc_iso(), "detail": detail or {}}},
                        upsert=True)
    except Exception as exc:                       # noqa: BLE001
        log.warning("zero_dte_lane: state write failed: %s", exc)


def _disabled_once(cfg: dict, gate: dict) -> None:
    today = _et_day()
    if cfg.get("last_zero_dte_disabled_day") == today:
        return
    ledger("zero_dte_disabled", detail={"gate": gate}, dry_run=True, cite=CITE)
    update_config(last_zero_dte_disabled_day=today)


def _public(doc: dict) -> dict:
    d = {k: v for k, v in (doc or {}).items() if k != "_id"}
    d["latency"] = latency(doc)
    d["narrative"] = narrative(doc)
    return d


# ── signal + chain reads (IO, thin) ──────────────────────────────────────────

def _signal_for(sym: str, now_utc: datetime) -> Optional[dict]:
    from daytrading import signal_lab as SL
    frame = SL._last_session_frame(sym)
    if frame is None or getattr(frame, "empty", True):
        return None
    try:
        last_day = frame.index[-1].date()
        if str(last_day) != _et_day():
            return None                            # yesterday's session, no tape today yet
    except Exception:                              # noqa: BLE001
        pass
    events = SL.events_from_frame(frame)
    return fresh_signal(events, frame.index, now_utc)


def _chain_row(sym: str) -> Optional[dict]:
    from options import zero_dte as ZD
    try:
        return ZD.read_symbol(sym)
    except Exception as exc:                       # noqa: BLE001
        log.warning("zero_dte_lane: chain for %s failed: %s", sym, exc)
        return None


def _stock_last(brk, sym: str, cache: dict) -> Optional[float]:
    if sym not in cache:
        try:
            cache[sym] = _f(brk.latest_trade(sym))
        except Exception as exc:                   # noqa: BLE001
            log.debug("zero_dte_lane: latest trade %s: %s", sym, exc)
            cache[sym] = None
    return cache[sym]


def _quote(brk, pos: dict, snaps_cache: dict) -> Optional[dict]:
    expiry, otype = str(pos.get("expiry")), str(pos.get("side") or "call")
    key = (pos["symbol"], expiry, otype)
    if key not in snaps_cache:
        try:
            snaps_cache[key] = brk.option_snapshots(pos["symbol"], expiry, expiry, otype) or {}
        except BrokerError as exc:
            snaps_cache[key] = {}
            log.warning("zero_dte_lane: snapshots %s: %s", pos["symbol"], exc)
    return (snaps_cache[key] or {}).get(pos["occ"])


def _order_lookup(brk, order_id: Optional[str], cache: dict) -> Optional[dict]:
    """The broker's order doc for `order_id`: open orders first, then the
    day's closed orders. None when it cannot be found."""
    if not order_id:
        return None
    if "orders" not in cache:
        found = {}
        try:
            for o in brk.open_orders() or []:
                found[o.get("id")] = o
        except BrokerError as exc:
            log.warning("zero_dte_lane: open orders: %s", exc)
        try:
            since = _utc_iso(datetime.now(timezone.utc) - timedelta(days=1))
            for o in brk.closed_orders_since(since) or []:
                found.setdefault(o.get("id"), o)
        except BrokerError as exc:
            log.warning("zero_dte_lane: closed orders: %s", exc)
        cache["orders"] = found
    return cache["orders"].get(order_id)


# ── manage open positions ────────────────────────────────────────────────────

def _manage(brk, cfg: dict, out: dict, open_docs: list, now_et: datetime) -> None:
    cache, snaps, px_cache = {}, {}, {}
    for pos in open_docs:
        sym = pos["symbol"]
        # 1. entry fill / miss
        if pos.get("fill_price") is None and pos.get("status") == "open":
            o = _order_lookup(brk, pos.get("order_id"), cache)
            st = str((o or {}).get("status") or "").lower()
            if st == "filled":
                pos["fill_price"] = _f(o.get("filled_avg_price"))
                pos["fill_ts"] = o.get("filled_at") or _utc_iso()
                pos["fill_qty"] = int(_f(o.get("filled_qty")) or pos.get("qty") or 0)
                _save(pos)
                ledger("zero_dte_filled", symbol=sym,
                       detail={"pos_id": pos["pos_id"], "fill_price": pos["fill_price"],
                               "latency": latency(pos)}, dry_run=False, cite=CITE)
            elif st in ("canceled", "cancelled", "expired", "rejected"):
                pos.update({"status": "missed", "closed_ts": _utc_iso(),
                            "close_reason": "entry %s at the broker" % st})
                _save(pos)
                out["missed"].append(sym)
                continue
            else:
                sent = pos.get("order_ts")
                try:
                    age = (datetime.now(timezone.utc)
                           - datetime.fromisoformat(str(sent).replace("Z", "+00:00"))).total_seconds()
                except (TypeError, ValueError):
                    age = 0
                if age > ENTRY_FILL_WAIT_SEC and cfg.get("armed"):
                    try:
                        brk.cancel_order(pos.get("order_id"))
                    except BrokerError as exc:
                        out["errors"].append("cancel %s: %s" % (sym, exc))
                    pos.update({"status": "missed", "closed_ts": _utc_iso(),
                                "close_reason": "not filled in %ds — cancelled" % ENTRY_FILL_WAIT_SEC})
                    _save(pos)
                    ledger("zero_dte_missed", symbol=sym,
                           detail={"pos_id": pos["pos_id"], "limit_price": pos.get("limit_price")},
                           dry_run=False, cite=CITE)
                    out["missed"].append(sym)
                    continue
                out["held"].append(sym)
                continue
        # 2. closing: done when the broker no longer holds the contract
        if pos.get("status") == "closing":
            o = _order_lookup(brk, pos.get("close_order_id"), cache)
            st = str((o or {}).get("status") or "").lower()
            if st == "filled":
                exit_px = _f(o.get("filled_avg_price")) or _f(pos.get("close_price")) or 0.0
                _finish(brk, pos, out, exit_px, o.get("filled_at"), px_cache)
            elif st in ("canceled", "cancelled", "expired", "rejected") and cfg.get("armed"):
                _send_close(brk, pos, out, snaps, resend=True)
            else:
                out["closing"].append(sym)
            continue
        # 3. open + filled: the exit read
        q = _quote(brk, pos, snaps) or {}
        mark = _f(q.get("bid"))
        stock = _stock_last(brk, sym, px_cache)
        pos["mark"] = mark
        pos["stock_last"] = stock
        why = exit_reason(pos, stock, mark, now_et)
        if why and cfg.get("armed"):
            pos["close_reason"] = why
            _send_close(brk, pos, out, snaps)
        else:
            _save(pos)
            out["held"].append(sym)


def _send_close(brk, pos: dict, out: dict, snaps: dict, resend: bool = False) -> None:
    q = _quote(brk, pos, snaps) or {}
    bid = _f(q.get("bid")) or 0.0
    px = round_down_tick(max(bid, 0.01))
    try:
        resp = brk.submit_option_order(pos["occ"], int(pos.get("fill_qty") or pos.get("qty") or 0),
                                       "sell", px, position_intent="sell_to_close",
                                       client_order_id="zdte-x-%s-%s" % (pos["pos_id"], _utc_iso()[-8:-2]))
    except BrokerError as exc:
        out["errors"].append("close %s: %s" % (pos["symbol"], exc))
        _save(pos)
        return
    pos.update({"status": "closing", "close_order_id": (resp or {}).get("id"),
                "close_price": px, "close_sent_ts": _utc_iso()})
    _save(pos)
    ledger("zero_dte_close_sent", symbol=pos["symbol"],
           detail={"pos_id": pos["pos_id"], "reason": pos.get("close_reason"), "price": px,
                   "resend": resend}, dry_run=False, cite=CITE)
    out["closing"].append(pos["symbol"])


def _finish(brk, pos: dict, out: dict, exit_px: float, filled_at, px_cache: dict) -> None:
    fill = _f(pos.get("fill_price")) or _f(pos.get("limit_price")) or 0.0
    qty = int(pos.get("fill_qty") or pos.get("qty") or 0)
    pnl = round((exit_px - fill) * 100.0 * qty, 2)
    stock_now = _stock_last(brk, pos["symbol"], px_cache)
    sig_px = _f((pos.get("signal") or {}).get("price"))
    stock_move = (round((stock_now / sig_px - 1.0) * 100.0, 2)
                  if stock_now and sig_px else None)
    pos.update({"status": "closed", "exit_price": round(exit_px, 2), "realized_pnl": pnl,
                "premium_return_pct": round((exit_px / fill - 1.0) * 100.0, 1) if fill else None,
                "stock_move_pct": stock_move, "closed_ts": filled_at or _utc_iso()})
    _save(pos)
    ledger("zero_dte_exit", symbol=pos["symbol"],
           detail={"pos_id": pos["pos_id"], "strategy": STRATEGY, "reason": pos.get("close_reason"),
                   "fill_price": fill, "exit_price": exit_px, "qty": qty, "realized_pnl": pnl,
                   "stock_move_pct": stock_move, "latency": latency(pos)},
           dry_run=False, cite=CITE)
    out["closed"].append(pos["symbol"])


# ── entries ──────────────────────────────────────────────────────────────────

def _try_entries(brk, cfg: dict, out: dict, now_et: datetime, day: str,
                 open_docs: list, equity: float) -> None:
    from options import zero_dte as ZD
    if not in_entry_window(now_et):
        out["entry_reason"] = "outside %s–%s ET" % (ENTRY_OPEN_ET.strftime("%H:%M"),
                                                    LAST_ENTRY_ET.strftime("%H:%M"))
        return
    attempts = _attempts_today(day)
    if attempts is None:
        out["ok"] = False
        out["errors"].append("zero_dte_lane_state unreadable — no entries")
        return
    entered_today = {a["symbol"] for a in attempts if a.get("result") == "entered"}
    if len(entered_today) >= MAX_ENTRIES_PER_DAY:
        out["entry_reason"] = "daily cap %d reached" % MAX_ENTRIES_PER_DAY
        return
    held = {d["symbol"] for d in open_docs}
    if len(held) >= MAX_OPEN:
        out["entry_reason"] = "%d open (max %d)" % (len(held), MAX_OPEN)
        return
    tried = {a["key"] for a in attempts}
    now_utc = datetime.now(timezone.utc)
    for sym in ZD.UNIVERSE:
        out["evaluated"] += 1
        if sym in held or sym in entered_today:
            continue
        sig = _signal_for(sym, now_utc)
        if not sig:
            continue                               # no fresh tag: cheap skip, no state
        key = "%s:%s:%s" % (sym, day, sig["bar_ts"])
        if key in tried:
            continue
        side = "buy" if sig["kind"] == "buy" else "sell"
        row = _chain_row(sym)
        c, reason = contract_for(row, side)
        if reason:
            _record_attempt(day, sym, key, "skipped", reason, {"signal": sig})
            out["skipped"].append({"symbol": sym, "reason": reason})
            continue
        qty, budget, reason = size_contracts(c["ask"], equity)
        if reason:
            _record_attempt(day, sym, key, "skipped", reason, {"signal": sig, "ask": c["ask"]})
            out["skipped"].append({"symbol": sym, "reason": reason})
            continue
        limit = round_up_tick(c["ask"])
        pos_id = "%s-%s-%s" % (sym, day, sig["bar_ts"][11:16].replace(":", ""))
        seen_ts = _utc_iso(now_utc)
        if not cfg.get("armed"):
            _record_attempt(day, sym, key, "dry_run", "not armed", {"signal": sig, "occ": c["occ"]})
            out["dry_run"].append(sym)
            continue
        try:
            resp = brk.submit_option_order(c["occ"], qty, "buy", limit, position_intent="buy_to_open",
                                           client_order_id="zdte-%s" % pos_id)
        except BrokerError as exc:
            _record_attempt(day, sym, key, "blocked", str(exc), {"signal": sig, "occ": c["occ"]})
            out["blocked"].append({"symbol": sym, "reason": str(exc)})
            continue
        order_ts = _utc_iso()
        doc = {"pos_id": pos_id, "symbol": sym, "side": c["otype"], "strategy": STRATEGY,
               "status": "open", "occ": c["occ"], "expiry": c.get("expiry"), "qty": qty,
               "limit_price": limit, "budget": budget, "order_id": (resp or {}).get("id"),
               "signal": {k: sig.get(k) for k in ("kind", "price", "stop", "target", "i")},
               "signal_bar_ts": sig["bar_ts"], "signal_bar_close_ts": sig["bar_close_ts"],
               "seen_ts": seen_ts, "order_ts": order_ts, "fill_price": None, "fill_ts": None,
               "contract": {k: c.get(k) for k in ("strike", "bid", "ask", "delta", "spread_pct",
                                                    "moves_needed", "day_volume", "iv")},
               "expected_move_pct": (row or {}).get("expected_move_pct"),
               "regime": (row or {}).get("regime"), "spot": (row or {}).get("spot"),
               "mode": _broker_mode(), "day": day, "cite": CITE}
        _save(doc)
        _record_attempt(day, sym, key, "entered", None, {"pos_id": pos_id, "occ": c["occ"]})
        ledger("zero_dte_entry", symbol=sym,
               detail={"pos_id": pos_id, "strategy": STRATEGY, "occ": c["occ"], "qty": qty,
                       "limit_price": limit, "signal": doc["signal"], "latency": latency(doc),
                       "order": resp if isinstance(resp, dict) else str(resp)},
               dry_run=False, cite=CITE)
        out["entered"].append(sym)
        entered_today.add(sym)
        held.add(sym)
        if len(entered_today) >= MAX_ENTRIES_PER_DAY or len(held) >= MAX_OPEN:
            break


# ── the tick ─────────────────────────────────────────────────────────────────

def run(broker=None, cfg: Optional[dict] = None) -> dict:
    """Engine tick step (l): manage open 0DTE contracts, then new entries."""
    brk = broker if broker is not None else globals()["broker"]
    cfg = cfg or get_config()
    day = _et_day()
    out = {"ok": True, "ran": False, "day": day, "entered": [], "blocked": [], "skipped": [],
           "dry_run": [], "held": [], "closing": [], "closed": [], "missed": [],
           "evaluated": 0, "errors": []}
    try:
        configured = bool(brk.configured())
    except Exception as exc:                       # noqa: BLE001
        configured = False
        out["errors"].append("configured: %s" % exc)
    mode = "unknown"
    try:
        mode = str(brk.mode())
    except Exception:                              # noqa: BLE001
        pass
    gate = {"configured": configured, "armed": bool(cfg.get("armed")),
            "zero_dte_entry": bool(cfg.get("zero_dte_entry")),
            "broker_has_options": _has_options(brk), "paper": mode != "live",
            "market_open": False}
    if gate["configured"]:
        try:
            gate["market_open"] = bool(brk.clock().get("is_open"))
        except Exception as exc:                   # noqa: BLE001
            out["errors"].append("clock: %s" % exc)
    out["gate"] = gate
    if not (gate["configured"] and gate["zero_dte_entry"] and gate["broker_has_options"]
            and gate["paper"] and gate["market_open"]):
        if gate["zero_dte_entry"] and not gate["paper"]:
            out["errors"].append("live broker: the 0DTE lane is paper-only and did nothing")
        # Say so once a day only when an OPTIONS-capable broker is gated (a
        # live account, not configured). A sim broker with no options helpers
        # is the ordinary disarmed-tick case and writes nothing — the
        # disarmed-tick invariant (exactly one dry-run row per tick) holds.
        if gate["zero_dte_entry"] and gate["market_open"] and gate["broker_has_options"]:
            _disabled_once(cfg, gate)
        out["reason"] = "gated"
        return out
    out["ran"] = True
    open_docs = _open_positions()
    if open_docs is None:
        out["ok"] = False
        out["errors"].append("zero_dte_positions unreadable — nothing managed or entered")
        out["reason"] = "state_unavailable"
        return out
    now_et = _now_et()
    _manage(brk, cfg, out, open_docs, now_et)
    still_open = [d for d in open_docs if d.get("status") in ("open", "closing")]
    try:
        equity = _f((brk.account() or {}).get("equity")) or 0.0
    except Exception as exc:                       # noqa: BLE001
        out["errors"].append("account: %s" % exc)
        equity = 0.0
    if equity <= 0:
        out["entry_reason"] = "equity unknown"
        return out
    _try_entries(brk, cfg, out, now_et, day, still_open, equity)
    return out


def close_now(symbol: str, reason: str = "owner close") -> dict:
    sym = (symbol or "").upper()
    open_docs = _open_positions() or []
    pos = next((d for d in open_docs if d["symbol"] == sym and d.get("status") == "open"), None)
    if pos is None:
        raise ValueError("no open 0DTE position on %s" % sym)
    cfg = get_config()
    if not cfg.get("armed"):
        raise ValueError("engine not armed")
    out = {"errors": [], "closing": []}
    pos["close_reason"] = reason
    _send_close(broker, pos, out, {})
    return {"ok": not out["errors"], "closing": out["closing"], "errors": out["errors"]}


# ── read side ────────────────────────────────────────────────────────────────

def rules_list() -> list:
    from options import zero_dte as ZD
    return [
        "Names: the 0DTE tab (%s) — only a name with a SAME-DAY expiry trades; no chain today = journaled skip."
        % ", ".join(ZD.UNIVERSE),
        "Signal: Signal Lab's 1-min BUY / SELL tag on today's tape (sweep, then the opposite-side "
        "structure break); the tag's bar must have closed <= %d s ago. BUY = the tab's call pick, "
        "SELL = its put pick (delta ~%.2f, spread <= %d%%, volume >= %d, ask >= $%.2f). Dealers PINNED = skip."
        % (SIGNAL_MAX_AGE_SEC, ZD.TARGET_DELTA, int(ZD.MAX_SPREAD_PCT), int(ZD.MIN_DAY_VOLUME), ZD.MIN_ASK),
        "Window: entries %s–%s ET; everything flat by %s ET." % (
            ENTRY_OPEN_ET.strftime("%H:%M"), LAST_ENTRY_ET.strftime("%H:%M"), FLATTEN_ET.strftime("%H:%M")),
        "Size: premium at risk = min(%g%% of equity, $%d) in whole contracts at the ask; %d entries a day, "
        "one per name, %d open." % (RISK_PCT_OF_EQUITY, int(MAX_PREMIUM_PER_TRADE), MAX_ENTRIES_PER_DAY, MAX_OPEN),
        "Exits: the stock first (the signal's stop / 2R target), then the premium (+%d%% / -%d%% off the fill), "
        "then the clock. Closes are sell-to-close limits at the bid, never market." % (
            int(PREMIUM_TAKE_PCT), int(PREMIUM_STOP_PCT)),
        "Latency on every row: signal bar close -> seen -> order -> fill, in seconds. An entry not filled in %d s is cancelled."
        % ENTRY_FILL_WAIT_SEC,
        "Paper only: a live broker gates the lane off. Not advice.",
    ]


def journal_block(docs: Optional[list] = None) -> dict:
    if docs is None:
        coll = _coll(POSITIONS_COLL)
        docs = []
        if coll is not None:
            try:
                docs = [d for d in coll.find({})]
            except Exception as exc:               # noqa: BLE001
                log.warning("zero_dte_lane: journal read failed: %s", exc)
    b = {"n": 0, "open": 0, "closed": 0, "missed": 0, "wins": 0, "losses": 0, "win_rate_pct": None,
         "avg_premium_return_pct": None, "realized_pnl": 0.0, "avg_stock_move_pct": None,
         "median_signal_to_fill_sec": None, "median_order_to_fill_sec": None}
    rets, moves, s2f, o2f = [], [], [], []
    for d in docs:
        b["n"] += 1
        st = d.get("status")
        if st in ("open", "closing"):
            b["open"] += 1
        elif st == "missed":
            b["missed"] += 1
        lat = latency(d)
        if lat.get("signal_to_fill_sec") is not None:
            s2f.append(lat["signal_to_fill_sec"])
        if lat.get("order_to_fill_sec") is not None:
            o2f.append(lat["order_to_fill_sec"])
        if st != "closed":
            continue
        b["closed"] += 1
        pnl = _f(d.get("realized_pnl")) or 0.0
        b["realized_pnl"] += pnl
        r = _f(d.get("premium_return_pct"))
        if r is not None:
            rets.append(r)
        m = _f(d.get("stock_move_pct"))
        if m is not None:
            moves.append(m)
        if pnl > 0:
            b["wins"] += 1
        elif pnl < 0:
            b["losses"] += 1
    decided = b["wins"] + b["losses"]
    b["win_rate_pct"] = round(b["wins"] / decided * 100.0, 1) if decided else None
    b["avg_premium_return_pct"] = round(sum(rets) / len(rets), 1) if rets else None
    b["avg_stock_move_pct"] = round(sum(moves) / len(moves), 2) if moves else None
    b["realized_pnl"] = round(b["realized_pnl"], 2)
    b["median_signal_to_fill_sec"] = _median(s2f)
    b["median_order_to_fill_sec"] = _median(o2f)
    return b


def _median(xs: list) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return round(s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0, 1)


def status_block(cfg: Optional[dict] = None) -> dict:
    cfg = cfg or get_config()
    day = _et_day()
    attempts = _attempts_today(day) or []
    return {"enabled": bool(cfg.get("zero_dte_entry")),
            "strategy": STRATEGY,
            "paper": _broker_mode() != "live",
            "broker_has_options": _has_options(broker),
            "entries_today": len({a["symbol"] for a in attempts if a.get("result") == "entered"}),
            "max_per_day": MAX_ENTRIES_PER_DAY, "max_open": MAX_OPEN,
            "entry_window": "%s–%s" % (ENTRY_OPEN_ET.strftime("%H:%M"), LAST_ENTRY_ET.strftime("%H:%M")),
            "flatten_et": FLATTEN_ET.strftime("%H:%M"),
            "rules": rules_list(),
            "settings": {"risk_pct_of_equity": RISK_PCT_OF_EQUITY,
                         "max_premium_per_trade": MAX_PREMIUM_PER_TRADE,
                         "signal_max_age_sec": SIGNAL_MAX_AGE_SEC,
                         "premium_take_pct": PREMIUM_TAKE_PCT, "premium_stop_pct": PREMIUM_STOP_PCT,
                         "entry_fill_wait_sec": ENTRY_FILL_WAIT_SEC, "skip_regimes": list(SKIP_REGIMES)},
            "open": [_public(d) for d in (_open_positions() or [])],
            "attempts": [{k: a.get(k) for k in ("symbol", "result", "reason", "ts")} for a in attempts],
            "journal": journal_block()}


def tab_payload() -> dict:
    cfg = get_config()
    return {"status": status_block(cfg), "armed": bool(cfg.get("armed")),
            "mode": _broker_mode(), "recent": [_public(d) for d in _recent()]}
