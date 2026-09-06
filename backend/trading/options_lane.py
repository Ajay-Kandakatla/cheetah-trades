"""Options lane — paper options on demand-zone touches (Ajay 2026-09-06).

Ajay: "create a new tab on the Auto pilot on options trading and paper trade
with it please. Include our supply demand rule we defined and any others
that you think may be needed."

OWNER RULES (2026-09-06 chat, no book — S/D scope, no Minervini cites):
  signal      the SAME demand-zone touch the stock lane buys: a zone-edge
              `near_demand` row (tier in/near) that passes the alert gate —
              >= ALERT_MIN_ROOM_PCT room to the first band overhead and the
              print <= ALERT_MAX_ABOVE_DEMAND_PCT above the band top — cap
              >= $1B, signal <= 3 min old, no new entry after 15:45 ET.
  strike      from the zone, not the calendar: long call strike = the highest
              listed strike AT OR UNDER the band top with delta inside
              [DELTA_LO, DELTA_HI] (in the money the moment the bounce
              starts). Spread short strike = the lowest listed strike AT OR
              ABOVE the first supply band (the room target) — where the stock
              would be sold anyway.
  expiry      the nearest expiry with MIN_DTE..MAX_DTE days, so theta does
              not win if the bounce stalls (room is usually 2-3 ATR-days).
  earnings    no earnings date inside [today, expiry]; an open position is
              closed EARNINGS_CLOSE_DAYS before one.
  structure   long call by default. When the chosen call's IV >=
              IV_SPREAD_THRESHOLD (rich IV after a slide) the lane SELLS
              premium instead (Ajay 2026-09-06, "ok please all 3"): a short
              put spread UNDER the band floor — short put = the highest listed
              strike at or under the floor (the level the thesis says holds),
              long put = the highest strike at or under short x (1 -
              PUT_SPREAD_WIDTH_PCT/100); credit >= MIN_CREDIT_PCT_OF_WIDTH of
              the width; defined risk = width - credit. No liquid put spread
              -> bull call spread (short strike at the room target) -> long
              call. Sent as ONE mleg package at a net credit (Alpaca: a
              negative limit_price is a credit), so there is never a naked
              short. Extra exit for the credit structure: buy it back when
              the spread costs <= TAKE_PROFIT_PCT_OF_CREDIT of the credit.
  exits       thesis, not premium: underlying prints under the band floor
              minus STOP_BUFFER_PCT -> close; underlying reaches the room
              target -> close; DTE <= CLOSE_DTE -> close; earnings within
              EARNINGS_CLOSE_DAYS -> close. Never "the option is down 50%".
  sizing      premium at risk per trade = min(RISK_PCT_OF_EQUITY % of equity,
              MAX_PREMIUM_PER_TRADE); whole contracts; MAX_OPTIONS_ENTRIES_
              PER_DAY; MAX_OPEN_OPTIONS underlyings at once; one position per
              underlying.
  liquidity   underlying >= MIN_UNDERLYING_PRICE; contract open interest >=
              MIN_OPEN_INTEREST; bid > 0; bid-ask <= MAX_SPREAD_PCT_OF_MID of
              the mid or <= MAX_SPREAD_ABS.
  orders      paper: marketable limits (buy at the ask, sell at the bid,
              spreads at the net of those) rounded to the option tick; a
              spread closes leg by leg (short leg first, so there is never a
              naked short). Every order is journaled (ledger kinds
              options_entry / options_exit / options_blocked / options_close
              _sent) and the tab reads Mongo `options_positions`.
Safety: armed=false places NOTHING (dry-run ledger rows); the lane gates
itself off on a broker without the options helpers (broker_sim); every
broker call is fenced so a failure here can never touch stock protection.
Decision support on a PAPER account — not advice.
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta
from typing import Optional

from trading import risk_rules
from trading import zone_edge_entry as ZEE
from trading.broker import BrokerError, get_broker
from trading.exit_engine import (
    _broker_mode, _db, _et_day, _notify_autopilot, _utc_iso, get_config, ledger,
    update_config)

broker = get_broker()    # module-level so tests can monkeypatch OL.broker
log = logging.getLogger("trading.options_lane")

# ──────────────────────────────────────────────────────────────────────────────
# OWNER SETTINGS (paper trial; NOT book numbers). Locked in
# tests/test_trading_contracts.py; changing any needs Ajay's sign-off.
# ──────────────────────────────────────────────────────────────────────────────
STRATEGY = "options_zone"
MAX_OPTIONS_ENTRIES_PER_DAY = 1
MAX_OPEN_OPTIONS = 3
RISK_PCT_OF_EQUITY = 1.0          # premium at risk per trade, % of equity
MAX_PREMIUM_PER_TRADE = 1500.0    # $ cap on that premium
MIN_DTE = 28                      # "at least 3 to 4 weeks"
MAX_DTE = 60
CLOSE_DTE = 7                     # time exit
DELTA_LO, DELTA_HI = 0.55, 0.75   # long strike window ("delta 0.6-0.7")
IV_SPREAD_THRESHOLD = 0.45        # chosen call IV >= this -> sell premium (put spread), else spreads
PUT_SPREAD_WIDTH_PCT = 5.0        # long put ~5% under the short put (owner default, 2026-09-06)
MIN_CREDIT_PCT_OF_WIDTH = 15.0    # credit must be >= 15% of the spread width
TAKE_PROFIT_PCT_OF_CREDIT = 25.0  # buy the spread back at <= 25% of the credit received
MAX_SPREAD_PCT_OF_MID = 10.0      # bid-ask as % of mid
MAX_SPREAD_ABS = 0.15             # or this many dollars, whichever is looser
MIN_OPEN_INTEREST = 200
MIN_UNDERLYING_PRICE = 20.0
EARNINGS_CLOSE_DAYS = 2
STOP_BUFFER_PCT = ZEE.STOP_BUFFER_PCT      # 0.5 — one truth with the stock lane
LAST_ENTRY_ET = ZEE.LAST_ENTRY_ET
MIN_CAP_USD = ZEE.MIN_CAP_USD
STALE_QUOTE_OK = True             # indicative feed; the tick re-reads every minute
POSITIONS_COLL = "options_positions"
STATE_COLL = "options_lane_state"
CITE = ("entry: OWNER RULES for options on demand-zone touches, no book "
        "(docs/trading_options_lane.md); signal + gate shared with "
        "trading/zone_edge_entry.py")


# ── small helpers ────────────────────────────────────────────────────────────

def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _coll(name: str):
    db = _db()
    if db is None:
        return None
    try:
        return getattr(db, name)                   # pymongo Database + the test fakes
    except Exception as exc:                       # noqa: BLE001
        log.warning("options_lane: collection %s unavailable: %s", name, exc)
        return None


def _latest():
    return ZEE._latest_doc()


def _zone(symbol: str, day: str):
    return ZEE._zone_doc(symbol, day)


def _earnings(symbol: str) -> Optional[date]:
    """Next earnings date (sepa.earnings_watch) or None. Fenced."""
    try:
        from sepa.earnings_watch import next_event
        ev = next_event(symbol) or {}
        d = ev.get("date")
        return date.fromisoformat(str(d)[:10]) if d else None
    except Exception as exc:                       # noqa: BLE001
        log.debug("options_lane: earnings for %s unavailable: %s", symbol, exc)
        return None


def _has_options(brk) -> bool:
    return all(callable(getattr(brk, m, None)) for m in
               ("option_contracts", "option_snapshots", "submit_option_order",
                "submit_option_spread", "positions", "latest_trade"))


def option_tick(price: float) -> float:
    """Listed option tick: $0.05 under $3.00, $0.10 from $3.00 up."""
    return 0.05 if price < 3.0 else 0.10


def round_up_tick(price: float) -> float:
    t = option_tick(price)
    return round(math.ceil(price / t - 1e-9) * t, 2)


def round_down_tick(price: float) -> float:
    t = option_tick(price)
    return round(math.floor(price / t + 1e-9) * t, 2)


# ── pure rules ───────────────────────────────────────────────────────────────

def pick_expiry(expiries, today: date) -> Optional[str]:
    """Nearest expiry with MIN_DTE <= DTE <= MAX_DTE (ISO string) or None."""
    best = None
    for e in expiries or []:
        try:
            d = date.fromisoformat(str(e)[:10])
        except ValueError:
            continue
        dte = (d - today).days
        if MIN_DTE <= dte <= MAX_DTE and (best is None or d < best):
            best = d
    return best.isoformat() if best else None


def liquidity_ok(contract: dict, snap: Optional[dict]) -> Optional[str]:
    """None when tradeable, else the reason."""
    oi = _f((contract or {}).get("open_interest"))
    if oi is None or oi < MIN_OPEN_INTEREST:
        return "open interest %s < %d" % (int(oi) if oi is not None else "?", MIN_OPEN_INTEREST)
    bid, ask = _f((snap or {}).get("bid")), _f((snap or {}).get("ask"))
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        return "no two-sided quote"
    mid = (bid + ask) / 2.0
    spread = ask - bid
    if spread > MAX_SPREAD_ABS and spread / mid * 100.0 > MAX_SPREAD_PCT_OF_MID:
        return "bid-ask %.2f = %.0f%% of mid" % (spread, spread / mid * 100.0)
    return None


def pick_long_strike(contracts: list, snaps: dict, band_hi: float) -> tuple:
    """(contract, snap, reason). The highest strike <= band top whose delta
    sits in [DELTA_LO, DELTA_HI] and that is liquid. Falls back to the
    highest liquid strike <= band top when no contract carries a delta."""
    under = [c for c in contracts or []
             if _f(c.get("strike_price")) is not None
             and float(c["strike_price"]) <= band_hi + 1e-9]
    if not under:
        return None, None, "no strike at or under the band top %.2f" % band_hi
    under.sort(key=lambda c: -float(c["strike_price"]))
    with_delta, without_delta, why = [], [], []
    for c in under:
        snap = (snaps or {}).get(c.get("symbol")) or {}
        liq = liquidity_ok(c, snap)
        if liq:
            why.append("%s: %s" % (c.get("symbol"), liq))
            continue
        d = _f(snap.get("delta"))
        if d is None:
            without_delta.append((c, snap))
        elif DELTA_LO <= d <= DELTA_HI:
            with_delta.append((c, snap))
        else:
            why.append("%s: delta %.2f outside %.2f-%.2f" % (c.get("symbol"), d, DELTA_LO, DELTA_HI))
    if with_delta:
        c, s = with_delta[0]
        return c, s, None
    if without_delta:
        c, s = without_delta[0]
        return c, s, None
    return None, None, "; ".join(why[:3]) or "no liquid strike under the band top"


def pick_short_strike(contracts: list, snaps: dict, target: float, long_strike: float) -> tuple:
    """(contract, snap, reason): the lowest liquid strike >= the room target
    and above the long strike."""
    above = [c for c in contracts or []
             if _f(c.get("strike_price")) is not None
             and float(c["strike_price"]) >= target - 1e-9
             and float(c["strike_price"]) > long_strike + 1e-9]
    above.sort(key=lambda c: float(c["strike_price"]))
    for c in above:
        snap = (snaps or {}).get(c.get("symbol")) or {}
        if liquidity_ok(c, snap) is None:
            return c, snap, None
    return None, None, "no liquid strike at or above the target %.2f" % target


def pick_put_short_strike(contracts: list, snaps: dict, band_lo: float) -> tuple:
    """(contract, snap, reason): the HIGHEST liquid put strike at or under
    the band floor — the level the thesis says holds."""
    under = [c for c in contracts or []
             if _f(c.get("strike_price")) is not None
             and float(c["strike_price"]) <= band_lo + 1e-9]
    under.sort(key=lambda c: -float(c["strike_price"]))
    why = []
    for c in under:
        snap = (snaps or {}).get(c.get("symbol")) or {}
        liq = liquidity_ok(c, snap)
        if liq:
            why.append("%s: %s" % (c.get("symbol"), liq))
            continue
        return c, snap, None
    return None, None, "; ".join(why[:3]) or "no put strike at or under the band floor %.2f" % band_lo


def pick_put_long_strike(contracts: list, snaps: dict, short_strike: float,
                         width_pct: float = PUT_SPREAD_WIDTH_PCT) -> tuple:
    """(contract, snap, reason): the highest liquid put strike at or under
    short x (1 - width_pct/100) — the wing that defines the risk."""
    cap = short_strike * (1.0 - width_pct / 100.0)
    under = [c for c in contracts or []
             if _f(c.get("strike_price")) is not None
             and float(c["strike_price"]) <= cap + 1e-9
             and float(c["strike_price"]) < short_strike - 1e-9]
    under.sort(key=lambda c: -float(c["strike_price"]))
    why = []
    for c in under:
        snap = (snaps or {}).get(c.get("symbol")) or {}
        liq = liquidity_ok(c, snap)
        if liq:
            why.append("%s: %s" % (c.get("symbol"), liq))
            continue
        return c, snap, None
    return None, None, "; ".join(why[:3]) or "no put strike %g%% under the short %.2f" % (width_pct, short_strike)


def credit_ok(credit: float, width: float) -> Optional[str]:
    """None when the credit is worth the risk, else the reason."""
    if width <= 0:
        return "spread width %.2f not positive" % width
    if credit <= 0:
        return "net credit %.2f not positive" % credit
    if credit / width * 100.0 < MIN_CREDIT_PCT_OF_WIDTH:
        return "credit %.2f = %.0f%% of the %.2f width < %d%%" % (
            credit, credit / width * 100.0, width, MIN_CREDIT_PCT_OF_WIDTH)
    return None


def spread_cost_to_close(pos: dict, quotes: dict) -> Optional[float]:
    """What the credit spread costs to buy back now: short ask - long bid
    (per share). None without a two-sided read."""
    short = next((l for l in pos.get("legs") or [] if l.get("role") == "short"), None)
    long_ = next((l for l in pos.get("legs") or [] if l.get("role") == "long"), None)
    if not short or not long_:
        return None
    ask = _f(((quotes or {}).get(short.get("symbol")) or {}).get("ask"))
    bid = _f(((quotes or {}).get(long_.get("symbol")) or {}).get("bid"))
    if ask is None or bid is None:
        return None
    return round(ask - bid, 2)


def take_profit_reason(pos: dict, quotes: dict) -> Optional[str]:
    """Credit structures only: buy back when the spread costs <=
    TAKE_PROFIT_PCT_OF_CREDIT of the credit received. None = hold."""
    credit = _f(pos.get("credit"))
    if not credit or credit <= 0 or not str(pos.get("structure") or "").startswith("short_"):
        return None
    cost = spread_cost_to_close(pos, quotes)
    if cost is None:
        return None
    line = round(credit * TAKE_PROFIT_PCT_OF_CREDIT / 100.0, 2)
    if cost <= line:
        return "take profit: buy-back %.2f <= %d%% of the %.2f credit" % (
            cost, TAKE_PROFIT_PCT_OF_CREDIT, credit)
    return None


def structure_for(iv: Optional[float], has_target: bool) -> str:
    """long_call unless IV is rich: then short_put_spread (sell the rich
    premium under the floor); the bull call spread is the fallback when the
    put spread is not liquid and a supply target exists."""
    if iv is not None and iv >= IV_SPREAD_THRESHOLD:
        return "short_put_spread"
    return "long_call"


def call_spread_fallback(has_target: bool) -> str:
    return "bull_call_spread" if has_target else "long_call"


def size_contracts(debit_per_contract: float, equity: float) -> tuple:
    """(qty, budget) — whole contracts inside the premium budget."""
    budget = min(equity * RISK_PCT_OF_EQUITY / 100.0, MAX_PREMIUM_PER_TRADE)
    cost = debit_per_contract * 100.0
    if cost <= 0:
        return 0, budget
    return int(budget // cost), budget


def exit_reason(pos: dict, last: Optional[float], today: date,
                earnings: Optional[date] = None) -> Optional[str]:
    """Owner exit rules on one open position doc. None = hold."""
    stop = _f(pos.get("stop_underlying"))
    target = _f(pos.get("target_underlying"))
    if last is not None and stop is not None and last <= stop:
        return "underlying %.2f under the band floor stop %.2f" % (last, stop)
    if last is not None and target is not None and last >= target:
        return "underlying %.2f reached the supply target %.2f" % (last, target)
    try:
        exp = date.fromisoformat(str(pos.get("expiry"))[:10])
        dte = (exp - today).days
        if dte <= CLOSE_DTE:
            return "DTE %d <= %d" % (dte, CLOSE_DTE)
    except (TypeError, ValueError):
        pass
    if earnings is not None and 0 <= (earnings - today).days <= EARNINGS_CLOSE_DAYS:
        return "earnings %s within %d days" % (earnings.isoformat(), EARNINGS_CLOSE_DAYS)
    return None


# ── state ────────────────────────────────────────────────────────────────────

def _open_positions() -> Optional[list]:
    coll = _coll(POSITIONS_COLL)
    if coll is None:
        return None
    try:
        return [d for d in coll.find({"status": {"$in": ["open", "closing"]}})]
    except Exception as exc:                       # noqa: BLE001
        log.warning("options_lane: positions read failed: %s", exc)
        return None


def _recent_closed(limit: int = 30) -> list:
    coll = _coll(POSITIONS_COLL)
    if coll is None:
        return []
    try:
        return [d for d in coll.find({"status": "closed"}).sort("closed_ts", -1).limit(limit)]
    except Exception as exc:                       # noqa: BLE001
        log.warning("options_lane: closed read failed: %s", exc)
        return []


def _save_position(doc: dict) -> bool:
    coll = _coll(POSITIONS_COLL)
    if coll is None:
        return False
    try:
        d = dict(doc)
        d.pop("_id", None)
        coll.update_one({"pos_id": d["pos_id"]}, {"$set": d}, upsert=True)
        return True
    except Exception as exc:                       # noqa: BLE001
        log.warning("options_lane: position write failed: %s", exc)
        return False


def _attempts_today(day: str) -> Optional[list]:
    coll = _coll(STATE_COLL)
    if coll is None:
        return None
    try:
        return [d for d in coll.find({"date": day})]
    except Exception as exc:                       # noqa: BLE001
        log.warning("options_lane: state read failed: %s", exc)
        return None


def _record_attempt(day: str, symbol: str, result: str, reason: Optional[str],
                    detail: Optional[dict] = None) -> None:
    coll = _coll(STATE_COLL)
    if coll is None:
        return
    try:
        coll.update_one({"date": day, "symbol": symbol},
                        {"$set": {"date": day, "symbol": symbol, "result": result,
                                  "reason": reason, "ts": _utc_iso(),
                                  "detail": detail or {}}}, upsert=True)
    except Exception as exc:                       # noqa: BLE001
        log.warning("options_lane: state write failed: %s", exc)


def _ledger_disabled_once(cfg: dict, gate: dict) -> None:
    today = _et_day()
    if cfg.get("last_options_entry_disabled_day") == today:
        return
    ledger("options_disabled", detail={"gate": gate}, dry_run=True, cite=CITE)
    update_config(last_options_entry_disabled_day=today)


def _public(doc: dict) -> dict:
    d = {k: v for k, v in (doc or {}).items() if k != "_id"}
    return d


# ── entry ────────────────────────────────────────────────────────────────────

def _chain(brk, sym: str, today: date, band_hi: float, target: Optional[float]) -> tuple:
    """(contracts, snaps, expiry, reason) for one underlying."""
    exp_lo = (today + timedelta(days=MIN_DTE)).isoformat()
    exp_hi = (today + timedelta(days=MAX_DTE)).isoformat()
    lo_strike = round(band_hi * 0.80, 2)
    hi_strike = round((target if target else band_hi) * 1.15, 2)
    contracts = brk.option_contracts(sym, exp_lo, exp_hi, "call", lo_strike, hi_strike)
    if not contracts:
        return [], {}, None, "no listed calls %s..%s" % (exp_lo, exp_hi)
    expiry = pick_expiry({c.get("expiration_date") for c in contracts}, today)
    if not expiry:
        return [], {}, None, "no expiry with %d-%d DTE" % (MIN_DTE, MAX_DTE)
    contracts = [c for c in contracts if str(c.get("expiration_date")) == expiry]
    snaps = brk.option_snapshots(sym, expiry, expiry, "call", lo_strike, hi_strike)
    return contracts, snaps, expiry, None


def _put_chain(brk, sym: str, expiry: str, band_lo: float) -> tuple:
    """(contracts, snaps) for the PUTS of one expiry around the band floor."""
    lo_strike = round(band_lo * 0.80, 2)
    hi_strike = round(band_lo * 1.02, 2)
    contracts = brk.option_contracts(sym, expiry, expiry, "put", lo_strike, hi_strike)
    if not contracts:
        return [], {}
    snaps = brk.option_snapshots(sym, expiry, expiry, "put", lo_strike, hi_strike)
    return contracts, snaps


def _plan_put_spread(brk, sym: str, expiry: str, band_lo: float) -> dict:
    """{"ok", "reason", legs, credit, width, short_strike, long_strike}."""
    try:
        contracts, snaps = _put_chain(brk, sym, expiry, band_lo)
    except BrokerError as exc:
        return {"ok": False, "reason": "put chain unavailable: %s" % exc}
    short_c, short_s, why = pick_put_short_strike(contracts, snaps, band_lo)
    if why:
        return {"ok": False, "reason": why}
    k_short = float(short_c["strike_price"])
    long_c, long_s, why = pick_put_long_strike(contracts, snaps, k_short)
    if why:
        return {"ok": False, "reason": why}
    k_long = float(long_c["strike_price"])
    credit = round_down_tick(float(short_s["bid"]) - float(long_s["ask"]))
    width = round(k_short - k_long, 2)
    why = credit_ok(credit, width)
    if why:
        return {"ok": False, "reason": why}
    legs = [{"symbol": short_c["symbol"], "side": "sell", "position_intent": "sell_to_open",
             "ratio_qty": 1, "strike": k_short, "role": "short"},
            {"symbol": long_c["symbol"], "side": "buy", "position_intent": "buy_to_open",
             "ratio_qty": 1, "strike": k_long, "role": "long"}]
    return {"ok": True, "legs": legs, "credit": round(credit, 2), "width": width,
            "short_strike": k_short, "long_strike": k_long,
            "iv": _f(short_s.get("iv")), "delta": _f(short_s.get("delta"))}


def plan_entry(brk, c: dict, gate_detail: dict, equity: float, today: date) -> dict:
    """Build the order plan for one gated candidate. Pure apart from the
    broker chain reads. Returns {"ok": bool, "reason", ...plan}."""
    sym = c["symbol"]
    band = c["band"]
    room = (gate_detail or {}).get("room") or {}
    target = _f(room.get("target"))
    out = {"ok": False, "symbol": sym, "band": band, "last": c["last"],
           "target_underlying": target,
           "stop_underlying": round(float(band["lo"]) * (1.0 - STOP_BUFFER_PCT / 100.0), 2)}
    if c["last"] < MIN_UNDERLYING_PRICE:
        out["reason"] = "underlying %.2f < $%g" % (c["last"], MIN_UNDERLYING_PRICE)
        return out
    try:
        contracts, snaps, expiry, why = _chain(brk, sym, today, float(band["hi"]), target)
    except BrokerError as exc:
        out["reason"] = "chain unavailable: %s" % exc
        return out
    if why:
        out["reason"] = why
        return out
    out["expiry"] = expiry
    exp_d = date.fromisoformat(expiry)
    out["dte"] = (exp_d - today).days
    earn = _earnings(sym)
    out["earnings"] = earn.isoformat() if earn else None
    if earn is not None and today <= earn <= exp_d:
        out["reason"] = "earnings %s inside the window (expiry %s)" % (earn.isoformat(), expiry)
        return out
    long_c, long_s, why = pick_long_strike(contracts, snaps, float(band["hi"]))
    if why:
        out["reason"] = why
        return out
    iv = _f(long_s.get("iv"))
    out["iv"] = iv
    out["delta"] = _f(long_s.get("delta"))
    structure = structure_for(iv, target is not None)
    short_c, short_s = None, None
    if structure == "short_put_spread":
        ps = _plan_put_spread(brk, sym, expiry, float(band["lo"]))
        if ps["ok"]:
            out["structure"] = "short_put_spread"
            out["otype"] = "put"
            out["iv"], out["delta"] = ps["iv"] if ps["iv"] is not None else iv, ps["delta"]
            credit, width = ps["credit"], ps["width"]
            qty, budget = size_contracts(width - credit, equity)      # risk = width - credit
            out.update({"legs": ps["legs"], "credit": credit, "width": width,
                        "debit": round(-credit, 2), "limit_price": round(-credit, 2),
                        "qty": qty, "budget": round(budget, 2),
                        "max_loss": round((width - credit) * 100.0 * qty, 2),
                        "take_profit_debit": round(credit * TAKE_PROFIT_PCT_OF_CREDIT / 100.0, 2)})
            if qty < 1:
                out["reason"] = "put spread risk %.2f x100 over the budget $%.0f" % (width - credit, budget)
                return out
            out["ok"] = True
            return out
        out["put_spread_fallback"] = ps["reason"]
        structure = call_spread_fallback(target is not None)
    if structure == "bull_call_spread":
        short_c, short_s, why = pick_short_strike(contracts, snaps, target, float(long_c["strike_price"]))
        if why:
            structure = "long_call"            # no liquid short strike: keep it simple
            out["spread_fallback"] = why
    out["structure"] = structure
    out["otype"] = "call"
    long_ask = float(long_s["ask"])
    legs = [{"symbol": long_c["symbol"], "side": "buy", "position_intent": "buy_to_open",
             "ratio_qty": 1, "strike": float(long_c["strike_price"]), "role": "long"}]
    if structure == "bull_call_spread":
        debit = long_ask - float(short_s["bid"])
        legs.append({"symbol": short_c["symbol"], "side": "sell",
                     "position_intent": "sell_to_open", "ratio_qty": 1,
                     "strike": float(short_c["strike_price"]), "role": "short"})
    else:
        debit = long_ask
    if debit <= 0:
        out["reason"] = "net debit %.2f not positive" % debit
        return out
    limit = round_up_tick(debit)
    qty, budget = size_contracts(limit, equity)
    out.update({"legs": legs, "debit": round(debit, 2), "limit_price": limit,
                "qty": qty, "budget": round(budget, 2),
                "max_loss": round(limit * 100.0 * qty, 2)})
    if qty < 1:
        out["reason"] = "premium %.2f x100 over the budget $%.0f" % (limit, budget)
        return out
    out["ok"] = True
    return out


def _place(brk, plan: dict, day: str) -> dict:
    """Send the entry order(s). Returns the broker response dict."""
    cid = "opt-%s-%s" % (plan["symbol"], day.replace("-", ""))
    if plan["structure"] in ("bull_call_spread", "short_put_spread"):
        # ONE mleg package: a negative limit_price is a net CREDIT at Alpaca
        # ("A positive value indicates a debit ... A negative value signifies
        # a credit", POST /v2/orders reference) — never a naked short leg.
        return brk.submit_option_spread(plan["legs"], plan["qty"], plan["limit_price"],
                                        client_order_id=cid) or {}
    leg = plan["legs"][0]
    return brk.submit_option_order(leg["symbol"], plan["qty"], "buy", plan["limit_price"],
                                   position_intent="buy_to_open", client_order_id=cid) or {}


def _try_entries(brk, cfg: dict, out: dict, now_et: datetime, day: str,
                 open_docs: list, equity: float) -> None:
    latest = _latest()
    sig = ZEE.signal_state(latest, now_et, day)
    out["signal"] = sig
    if not sig["fresh"]:
        out["entry_reason"] = "stale_signal"
        return
    if now_et.time() >= LAST_ENTRY_ET:
        out["entry_reason"] = "after_last_entry_time"
        return
    attempts = _attempts_today(day)
    if attempts is None:
        out["ok"] = False
        out["errors"].append("options_lane_state unreadable — no attempts")
        out["entry_reason"] = "state_unavailable"
        return
    entered_today = [a for a in attempts if a.get("result") == "entered"]
    if len(entered_today) >= MAX_OPTIONS_ENTRIES_PER_DAY:
        out["entry_reason"] = "daily cap %d reached" % MAX_OPTIONS_ENTRIES_PER_DAY
        return
    if len(open_docs) >= MAX_OPEN_OPTIONS:
        out["entry_reason"] = "open cap %d reached" % MAX_OPEN_OPTIONS
        return
    held = {str(d.get("symbol") or "").upper() for d in open_docs}
    tried = {str(a.get("symbol") or "").upper() for a in attempts}
    rules = ZEE.active_rules(cfg)
    cands, rejected = ZEE.read_candidates(latest, rules)
    cands = [c for c in cands if c.get("kind") == "demand"]
    out["evaluated"] = len(cands)
    out["rejected"] = len(rejected)
    today = now_et.date()
    for c in cands:
        sym = c["symbol"]
        if sym in held:
            out["skipped"].append({"symbol": sym, "reason": "already holding options"})
            continue
        if sym in tried:
            out["skipped"].append({"symbol": sym, "reason": "attempted today"})
            continue
        zone_doc = _zone(sym, day)
        gate = ZEE.alert_gate(c, zone_doc)
        if gate is None or not gate[0]:
            why = "alert gate: room unknown" if gate is None else gate[1]["reason"]
            out["skipped_alert_gate"] += 1
            out["skipped"].append({"symbol": sym, "reason": why})
            continue
        plan = plan_entry(brk, c, gate[1], equity, today)
        if not plan["ok"]:
            _record_attempt(day, sym, "blocked", plan.get("reason"), plan)
            out["blocked"].append({"symbol": sym, "reason": plan.get("reason")})
            ledger("options_blocked", symbol=sym, detail=dict(plan, gate=gate[1]),
                   dry_run=True, cite=CITE)
            continue
        if not cfg.get("armed"):
            _record_attempt(day, sym, "dry_run", "disarmed", plan)
            ledger("options_entry", symbol=sym,
                   detail=dict(plan, strategy=STRATEGY, gate=gate[1],
                               note="disarmed — dry run, nothing sent"),
                   dry_run=True, cite=CITE)
            out["dry_run"].append(sym)
            return                                  # one per tick either way
        try:
            resp = _place(brk, plan, day)
        except BrokerError as exc:
            _record_attempt(day, sym, "error", str(exc), plan)
            out["errors"].append("%s: %s" % (sym, exc))
            ledger("options_blocked", symbol=sym,
                   detail=dict(plan, reason="order rejected: %s" % exc), dry_run=False, cite=CITE)
            return
        pos = {"pos_id": "%s-%s" % (sym, day), "symbol": sym, "strategy": STRATEGY,
               "status": "open", "structure": plan["structure"], "legs": plan["legs"],
               "otype": plan.get("otype") or "call",
               "qty": plan["qty"], "debit": plan["limit_price"],
               "credit": plan.get("credit"), "width": plan.get("width"),
               "take_profit_debit": plan.get("take_profit_debit"),
               "max_loss": plan["max_loss"], "expiry": plan["expiry"], "dte": plan["dte"],
               "iv": plan.get("iv"), "delta": plan.get("delta"), "band": plan["band"],
               "entry_underlying": plan["last"], "stop_underlying": plan["stop_underlying"],
               "target_underlying": plan.get("target_underlying"),
               "earnings": plan.get("earnings"), "room": gate[1].get("room"),
               "order_id": resp.get("id"), "entry_ts": _utc_iso(), "day": day,
               "mode": _broker_mode(), "close_reason": None, "exit_credit": None,
               "realized_pnl": None, "closed_ts": None}
        _save_position(pos)
        _record_attempt(day, sym, "entered", None, {"order_id": resp.get("id")})
        ledger("options_entry", symbol=sym,
               detail=dict(plan, strategy=STRATEGY, gate=gate[1], order_id=resp.get("id"),
                           pos_id=pos["pos_id"]),
               dry_run=False, cite=CITE)
        _notify_autopilot(
            "position_alert", sym,
            "%s options %s: %s x%d @ %s (exp %s, %d DTE) — stop %.2f / target %s"
            % (sym, plan["structure"].replace("_", " "),
               " / ".join("%s %g" % (l["role"], l["strike"]) for l in plan["legs"]),
               plan["qty"],
               ("%.2f credit" % plan["credit"]) if plan.get("credit") else "%.2f" % plan["limit_price"],
               plan["expiry"], plan["dte"],
               plan["stop_underlying"],
               ("%.2f" % plan["target_underlying"]) if plan.get("target_underlying") else "clear"))
        out["entered"].append(sym)
        return


# ── exits ────────────────────────────────────────────────────────────────────

def _broker_qty(brk, symbol: str, cache: dict) -> Optional[float]:
    if "positions" not in cache:
        try:
            cache["positions"] = {str(p.get("symbol") or ""): _f(p.get("qty"))
                                  for p in brk.positions()
                                  if (p.get("asset_class") or "") == "us_option"}
        except BrokerError as exc:
            cache["error"] = str(exc)
            cache["positions"] = None
    pos = cache.get("positions")
    if pos is None:
        return None
    return pos.get(symbol) or 0.0


def _pos_quotes(brk, pos: dict, snaps_cache: dict) -> dict:
    """Snapshots for the position's expiry and option type (call / put)."""
    expiry = str(pos.get("expiry"))
    otype = str(pos.get("otype") or "call")
    key = (pos["symbol"], expiry, otype)
    if key not in snaps_cache:
        snaps_cache[key] = brk.option_snapshots(pos["symbol"], expiry, expiry, otype)
    return snaps_cache[key] or {}


def _send_close(brk, pos: dict, snaps_cache: dict) -> tuple:
    """Close the position's legs (short leg first). Returns (order_ids, errors)."""
    ids, errors = [], []
    legs = sorted(pos.get("legs") or [], key=lambda l: 0 if l.get("role") == "short" else 1)
    for leg in legs:
        sym = leg["symbol"]
        quote = None
        try:
            quote = (_pos_quotes(brk, pos, snaps_cache) or {}).get(sym)
        except BrokerError as exc:
            errors.append("quote %s: %s" % (sym, exc))
        try:
            if leg.get("role") == "short":
                ask = _f((quote or {}).get("ask")) or 0.0
                px = round_up_tick(max(ask, 0.05))
                resp = brk.submit_option_order(sym, pos["qty"], "buy", px,
                                               position_intent="buy_to_close")
            else:
                bid = _f((quote or {}).get("bid")) or 0.0
                px = round_down_tick(max(bid, 0.05))
                resp = brk.submit_option_order(sym, pos["qty"], "sell", px,
                                               position_intent="sell_to_close")
            ids.append({"symbol": sym, "order_id": (resp or {}).get("id"), "price": px})
        except BrokerError as exc:
            errors.append("close %s: %s" % (sym, exc))
    return ids, errors


def _finish_close(brk, pos: dict, out: dict) -> None:
    """Every leg gone at the broker: realize P&L from the close fills."""
    credit = 0.0
    filled = 0
    try:
        since = _utc_iso(datetime.now(tz=__import__("datetime").timezone.utc) - timedelta(days=7))
        closed = brk.closed_orders_since(since)
    except (BrokerError, Exception) as exc:        # noqa: BLE001
        closed = []
        out["errors"].append("closed orders: %s" % exc)
    for co in pos.get("close_orders") or []:
        oid = co.get("order_id")
        for o in closed or []:
            if oid and o.get("id") == oid and (o.get("status") or "").lower() == "filled":
                px = _f(o.get("filled_avg_price")) or 0.0
                role = next((l.get("role") for l in pos.get("legs") or []
                             if l.get("symbol") == co.get("symbol")), "long")
                credit += px if role == "long" else -px
                filled += 1
    if filled == 0:
        credit = sum((co.get("price") or 0.0) * (1 if next((l.get("role") for l in pos.get("legs") or []
                                                            if l.get("symbol") == co.get("symbol")), "long") == "long" else -1)
                     for co in pos.get("close_orders") or [])
    pnl = round((credit - float(pos.get("debit") or 0.0)) * 100.0 * int(pos.get("qty") or 0), 2)
    pos.update({"status": "closed", "exit_credit": round(credit, 2), "realized_pnl": pnl,
                "closed_ts": _utc_iso(), "fills_seen": filled})
    _save_position(pos)
    ledger("options_exit", symbol=pos["symbol"],
           detail={"pos_id": pos["pos_id"], "strategy": STRATEGY, "structure": pos.get("structure"),
                   "reason": pos.get("close_reason"), "debit": pos.get("debit"),
                   "exit_credit": round(credit, 2), "realized_pnl": pnl, "qty": pos.get("qty"),
                   "legs": pos.get("legs"), "fills_seen": filled},
           dry_run=False, cite=CITE)
    _notify_autopilot("position_alert", pos["symbol"],
                      "%s options closed: %s — %s (P&L %+.0f)"
                      % (pos["symbol"], pos.get("close_reason") or "closed", pos.get("structure"), pnl))
    out["closed"].append(pos["symbol"])


def _manage(brk, cfg: dict, out: dict, open_docs: list, today: date) -> None:
    cache, snaps_cache = {}, {}
    for pos in open_docs:
        sym = pos["symbol"]
        legs = pos.get("legs") or []
        qtys = [_broker_qty(brk, l["symbol"], cache) for l in legs]
        if any(q is None for q in qtys):
            out["errors"].append("%s: broker positions unavailable (%s)" % (sym, cache.get("error")))
            continue
        gone = all(abs(q or 0.0) < 1e-9 for q in qtys)
        if pos.get("status") == "closing":
            if gone:
                _finish_close(brk, pos, out)
                continue
            # Legs still at the broker: are the close orders still working?
            # A day limit that expired / was rejected is re-sent with a fresh
            # quote (never a market order on a contract).
            if "open_orders" not in cache:
                try:
                    cache["open_orders"] = {o.get("id") for o in brk.open_orders()}
                except BrokerError as exc:
                    cache["open_orders"] = None
                    out["errors"].append("open orders: %s" % exc)
            working = cache.get("open_orders")
            ids = {co.get("order_id") for co in pos.get("close_orders") or []}
            if working is not None and not (ids & working) and cfg.get("armed"):
                new_ids, errors = _send_close(brk, pos, snaps_cache)
                out["errors"].extend(errors)
                if new_ids:
                    pos["close_orders"] = (pos.get("close_orders") or []) + new_ids
                    pos["close_resent_ts"] = _utc_iso()
                    _save_position(pos)
                    ledger("options_close_sent", symbol=sym,
                           detail={"pos_id": pos["pos_id"], "reason": pos.get("close_reason"),
                                   "orders": new_ids, "note": "re-sent: previous close not working"},
                           dry_run=False, cite=CITE)
            out["closing"].append(sym)
            continue
        if gone and pos.get("order_id") and pos.get("entry_ts"):
            # Entry never filled (day order expired) or closed by hand.
            try:
                age = (datetime.now(tz=__import__("datetime").timezone.utc)
                       - datetime.fromisoformat(str(pos["entry_ts"]).replace("Z", "+00:00"))).total_seconds()
            except ValueError:
                age = 0.0
            if age > 600:
                pos.update({"status": "closed", "close_reason": "no contracts at the broker "
                            "(entry unfilled or closed by hand)", "realized_pnl": 0.0,
                            "closed_ts": _utc_iso()})
                _save_position(pos)
                ledger("options_exit", symbol=sym,
                       detail={"pos_id": pos["pos_id"], "strategy": STRATEGY,
                               "reason": pos["close_reason"], "realized_pnl": 0.0},
                       dry_run=False, cite=CITE)
                out["closed"].append(sym)
            continue
        try:
            last = brk.latest_trade(sym)
        except BrokerError:
            last = None
        why = exit_reason(pos, last, today, _earnings(sym))
        if not why and _f(pos.get("credit")):
            try:
                why = take_profit_reason(pos, _pos_quotes(brk, pos, snaps_cache))
            except BrokerError as exc:
                out["errors"].append("%s: quotes for take-profit: %s" % (sym, exc))
        if not why:
            out["held"].append(sym)
            continue
        if not cfg.get("armed"):
            ledger("options_close_sent", symbol=sym,
                   detail={"pos_id": pos["pos_id"], "reason": why,
                           "note": "disarmed — dry run, nothing sent"},
                   dry_run=True, cite=CITE)
            out["dry_run"].append(sym)
            continue
        ids, errors = _send_close(brk, pos, snaps_cache)
        out["errors"].extend(errors)
        if ids:
            pos.update({"status": "closing", "close_reason": why, "close_orders": ids,
                        "close_ts": _utc_iso()})
            _save_position(pos)
            ledger("options_close_sent", symbol=sym,
                   detail={"pos_id": pos["pos_id"], "reason": why, "orders": ids},
                   dry_run=False, cite=CITE)
            _notify_autopilot("position_alert", sym, "%s options closing — %s" % (sym, why))
            out["closing"].append(sym)


def close_now(underlying: str, reason: str = "owner close") -> dict:
    """Owner-triggered close of the lane's open position on one underlying."""
    sym = (underlying or "").strip().upper()
    if not sym:
        raise ValueError("symbol required")
    cfg = get_config()
    if not cfg.get("armed"):
        raise ValueError("engine is disarmed — nothing sent")
    docs = _open_positions() or []
    pos = next((d for d in docs if d.get("symbol") == sym and d.get("status") == "open"), None)
    if pos is None:
        raise ValueError("no open options position on %s" % sym)
    ids, errors = _send_close(broker, pos, {})
    if ids:
        pos.update({"status": "closing", "close_reason": reason, "close_orders": ids,
                    "close_ts": _utc_iso()})
        _save_position(pos)
        ledger("options_close_sent", symbol=sym,
               detail={"pos_id": pos["pos_id"], "reason": reason, "orders": ids},
               dry_run=False, cite=CITE)
    return {"symbol": sym, "orders": ids, "errors": errors}


# ── tick entry point ─────────────────────────────────────────────────────────

def run(broker=None, cfg: Optional[dict] = None) -> dict:
    """Tick step (k): manage open contracts, then at most one new entry."""
    brk = broker if broker is not None else globals()["broker"]
    cfg = cfg or get_config()
    day = _et_day()
    out = {"ok": True, "ran": False, "day": day, "entered": [], "blocked": [],
           "skipped": [], "skipped_alert_gate": 0, "evaluated": 0, "rejected": 0,
           "held": [], "closing": [], "closed": [], "dry_run": [], "errors": []}
    try:
        configured = bool(brk.configured())
    except Exception as exc:                       # noqa: BLE001
        configured = False
        out["errors"].append("configured: %s" % exc)
    gate = {"configured": configured, "armed": bool(cfg.get("armed")),
            "options_entry": bool(cfg.get("options_entry")),
            "broker_has_options": _has_options(brk), "market_open": False}
    if gate["configured"]:
        try:
            gate["market_open"] = bool(brk.clock().get("is_open"))
        except Exception as exc:                   # noqa: BLE001
            out["errors"].append("clock: %s" % exc)
    out["gate"] = gate
    if not (gate["configured"] and gate["options_entry"] and gate["broker_has_options"]
            and gate["market_open"]):
        if gate["options_entry"]:
            # The owner turned the lane on and something else gates it: say so
            # once a day. A lane that is simply OFF writes nothing (the
            # disarmed-tick invariant: exactly one dry-run row per tick).
            _ledger_disabled_once(cfg, gate)
        out["reason"] = "gated"
        return out
    out["ran"] = True
    open_docs = _open_positions()
    if open_docs is None:
        out["ok"] = False
        out["errors"].append("options_positions unreadable — nothing managed or entered")
        out["reason"] = "state_unavailable"
        return out
    now_et = ZEE._now_et()
    _manage(brk, cfg, out, open_docs, now_et.date())
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


# ── status / tab / journal ───────────────────────────────────────────────────

def rules_list() -> list:
    return [
        "Signal: the same demand-zone touch as the stock lane (zone-edge near/in row) passing "
        "the alert gate (>= %g%% room, <= %g%% above the band top), cap >= $%dB, no new entry "
        "after %s ET." % (ZEE.alert_gates.ALERT_MIN_ROOM_PCT, ZEE.alert_gates.ALERT_MAX_ABOVE_DEMAND_PCT,
                          int(MIN_CAP_USD / 1e9), LAST_ENTRY_ET.strftime("%H:%M")),
        "Strike from the zone: long call = highest strike at or under the band top with delta "
        "%.2f-%.2f; spread short strike = lowest strike at or above the first supply band."
        % (DELTA_LO, DELTA_HI),
        "Expiry %d-%d days out; no earnings inside the window." % (MIN_DTE, MAX_DTE),
        "Long call by default. IV >= %d%%: SELL a put spread under the band floor — short put = "
        "highest strike at or under the floor, long put ~%g%% lower, credit >= %d%% of the width, "
        "bought back at <= %d%% of the credit; no liquid put spread -> bull call spread -> long call."
        % (int(IV_SPREAD_THRESHOLD * 100), PUT_SPREAD_WIDTH_PCT, int(MIN_CREDIT_PCT_OF_WIDTH),
           int(TAKE_PROFIT_PCT_OF_CREDIT)),
        "Exit on the underlying, never on the premium: under the band floor -%g%%, at the supply "
        "target, DTE <= %d, or earnings within %d days." % (STOP_BUFFER_PCT, CLOSE_DTE, EARNINGS_CLOSE_DAYS),
        "Size: premium at risk = min(%g%% of equity, $%d); %d entry/day; %d open names; "
        "underlying >= $%d; OI >= %d; bid-ask <= %d%% of mid."
        % (RISK_PCT_OF_EQUITY, int(MAX_PREMIUM_PER_TRADE), MAX_OPTIONS_ENTRIES_PER_DAY,
           MAX_OPEN_OPTIONS, int(MIN_UNDERLYING_PRICE), MIN_OPEN_INTEREST, int(MAX_SPREAD_PCT_OF_MID)),
    ]


def journal_block() -> dict:
    """Per-lane journal numbers over the lane's own position docs (they never
    pass through entries.enter, so journal.by_strategy cannot see them)."""
    coll = _coll(POSITIONS_COLL)
    docs = []
    if coll is not None:
        try:
            docs = [d for d in coll.find({})]
        except Exception as exc:                   # noqa: BLE001
            log.warning("options_lane: journal read failed: %s", exc)
    b = {"n": 0, "open": 0, "closed": 0, "wins": 0, "losses": 0, "win_rate_pct": None,
         "avg_r": None, "expectancy_pct": None, "realized_pnl": 0.0}
    gains = []
    for d in docs:
        b["n"] += 1
        if d.get("status") != "closed":
            b["open"] += 1
            continue
        b["closed"] += 1
        pnl = _f(d.get("realized_pnl")) or 0.0
        b["realized_pnl"] += pnl
        debit = _f(d.get("debit")) or 0.0
        qty = int(d.get("qty") or 0)
        cost = _f(d.get("max_loss")) or 0.0          # $ at risk: premium, or width - credit
        if cost <= 0:
            cost = debit * 100.0 * qty
        if cost > 0:
            g = pnl / cost * 100.0
            gains.append(g)
            if g > 0:
                b["wins"] += 1
            elif g < 0:
                b["losses"] += 1
    decided = b["wins"] + b["losses"]
    b["win_rate_pct"] = round(b["wins"] / decided * 100.0, 1) if decided else None
    b["expectancy_pct"] = round(sum(gains) / len(gains), 2) if gains else None
    b["realized_pnl"] = round(b["realized_pnl"], 2)
    return b


def status_block(cfg: Optional[dict] = None) -> dict:
    cfg = cfg or get_config()
    day = _et_day()
    attempts = _attempts_today(day) or []
    return {"enabled": bool(cfg.get("options_entry")),
            "strategy": STRATEGY,
            "broker_has_options": _has_options(broker),
            "entries_today": len([a for a in attempts if a.get("result") == "entered"]),
            "max_per_day": MAX_OPTIONS_ENTRIES_PER_DAY,
            "max_open": MAX_OPEN_OPTIONS,
            "last_entry_et": LAST_ENTRY_ET.strftime("%H:%M"),
            "rules": rules_list(),
            "settings": {"risk_pct_of_equity": RISK_PCT_OF_EQUITY,
                         "max_premium_per_trade": MAX_PREMIUM_PER_TRADE,
                         "min_dte": MIN_DTE, "max_dte": MAX_DTE, "close_dte": CLOSE_DTE,
                         "delta_lo": DELTA_LO, "delta_hi": DELTA_HI,
                         "iv_spread_threshold": IV_SPREAD_THRESHOLD,
                         "put_spread_width_pct": PUT_SPREAD_WIDTH_PCT,
                         "min_credit_pct_of_width": MIN_CREDIT_PCT_OF_WIDTH,
                         "take_profit_pct_of_credit": TAKE_PROFIT_PCT_OF_CREDIT,
                         "min_open_interest": MIN_OPEN_INTEREST,
                         "max_spread_pct_of_mid": MAX_SPREAD_PCT_OF_MID,
                         "min_underlying_price": MIN_UNDERLYING_PRICE,
                         "earnings_close_days": EARNINGS_CLOSE_DAYS,
                         "stop_buffer_pct": STOP_BUFFER_PCT},
            "open": [_public(d) for d in (_open_positions() or [])],
            "attempts": [{k: a.get(k) for k in ("symbol", "result", "reason", "ts")}
                         for a in attempts],
            "journal": journal_block()}


def tab_payload() -> dict:
    cfg = get_config()
    return {"status": status_block(cfg), "armed": bool(cfg.get("armed")),
            "mode": _broker_mode(),
            "recent_closed": [_public(d) for d in _recent_closed()]}
