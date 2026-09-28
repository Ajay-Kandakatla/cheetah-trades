"""Chart Maps lane program — the caps every buy passes (PAPER).

Ajay 2026-09-27: "stop minerviews use all strategies from Most used from Chart
maps. All of them and journal the," — then "Small: 0.25% risk, 15 open max"
and "Top 10 most-used first".

This is the ONE chokepoint gate. `entries._evaluate` calls `check()` for every
stock buy and the two options lanes call it before they submit, so an existing
lane (zones, breaking, catalysts, quick_bounce, hot_pullback, 0DTE) hits the
same caps and the same 0.25% sizing as the new generic lanes: every function
normalises its tag first (`strategy_tags.norm`).

WHAT APPLIES IN EVERY MODE (program ON or OFF, paper or live)
  * the in-flight open cap: positions + PENDING entry orders, option spread
    legs included (autopsy a1 / C1 — the old cap ignored sent-but-unfilled
    orders and two opening-bell fan-outs broke it);
  * a pending entry for the same symbol refuses a second one;
  * one lane per name: a lane tag never buys a name already held;
  * ONE new entry per ET minute across every lane (manual exempt), claimed
    atomically in Mongo (autopsy d1 / C3).
WHAT APPLIES ONLY WHILE THE PROGRAM IS ON (paper / sim only, never live)
  * the program open cap PROGRAM_MAX_OPEN (live stays risk_rules.MAX_POSITIONS);
  * per strategy: PER_STRATEGY_MAX_ENTRIES_PER_DAY new buy a day and
    PER_STRATEGY_MAX_OPEN open;
  * PROGRAM_RISK_PCT of equity at risk per stock trade, min-composed with the
    streak and progressive multipliers (never larger than position_size);
  * the per-strategy ON/OFF switches (cm_lanes).

No auto-pause: losers are reviewed daily (trading/lane_review.py) and every
change goes through his Confirm. Nothing here places, cancels or modifies an
order — it only answers "may this buy go out, and at what size".

Wording: UNMEASURED forward paper measurement. "Reversal", never the other word.
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from trading import risk_rules
from trading import strategy_tags as ST
from trading.broker import OPEN_STATUSES, BrokerError

log = logging.getLogger("trading.program_caps")

ET = ZoneInfo("America/New_York")

# ── Constants (locked by tests/test_trading_contracts.py) ────────────────────
PROGRAM_RISK_PCT = 0.25                    # "Small: 0.25% risk"
PER_STRATEGY_MAX_ENTRIES_PER_DAY = 1
PER_STRATEGY_MAX_OPEN = 2
PROGRAM_MAX_OPEN = 15                      # "15 open max" — paper-only, stocks + options + pending
PROGRAM_MAX_GROSS_PCT = 100.0              # program gross <= 100% of equity_used (HIS CALL #1 default)
PENDING_BUY_STATUSES = frozenset(OPEN_STATUSES) - {"held"}
OPEN_INTENTS = ("buy_to_open", "sell_to_open")
TRANSIENT_PREFIX = "program-wait: "
DAY_PREFIX = "program-cap: "
ENTRY_CLOCK_ID = "entry_clock"
USAGE_ORDER_ID = "usage_order"
PROGRAM_ENTRIES_COLL = "program_entries"
PROGRAM_STATE_COLL = "program_state"
LOG_COLL = "cm_lane_log"
LOG_REASON_KEY_CHARS = 80
USAGE_KEY_PREFIX = "chart-maps:tab:"

MINUTE_TAKEN_TEXT = "program-wait: one entry per minute"
_OCC_RE = re.compile(r"^[A-Z]{1,6}\d{6}[CP]\d{8}$")

# The tick pins its own minute so every claim inside one tick uses it.
_TICK_MINUTE: Optional[str] = None


# ── Mongo (resolved through exit_engine at CALL time so tests' fakes apply) ──
def _db():
    from trading import exit_engine as EE
    return EE._db()


def _coll(name: str):
    db = _db()
    if db is None:
        return None
    try:
        return getattr(db, name)
    except Exception:                              # noqa: BLE001 — attribute-style fakes
        return None


def _now_et(now: Optional[datetime] = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc).astimezone(ET)
    if now.tzinfo is None:
        return now.replace(tzinfo=ET)
    return now.astimezone(ET)


def et_day(now: Optional[datetime] = None) -> str:
    return _now_et(now).date().isoformat()


def _at(now: Optional[datetime] = None) -> str:
    return _now_et(now).isoformat(timespec="seconds")


def _hms(at) -> str:
    s = str(at or "")
    return s[11:19] if len(s) >= 19 else (s or "?")


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and not math.isinf(v) else None


# ── Program switches ─────────────────────────────────────────────────────────
def enabled(cfg: Optional[dict], mode) -> bool:
    """The program is ON only when cm_program is True AND the broker is paper
    or sim. Live is never a program."""
    cfg = cfg or {}
    return cfg.get("cm_program") is True and str(mode or "") in ("paper", "sim")


def strategy_on(tag, cfg: Optional[dict], mode) -> bool:
    """Is this strategy allowed to BUY right now (its exits never stop).

    non-roster (minervini / options_zone / manual)  True — own switches apply
    not a lane (vcp, topping, support, ...)          False, every mode
    program OFF                                      existing lanes True (own
                                                     switches as today), generic
                                                     sids False
    program ON                                       cm_lanes override, else
                                                     DEFAULT_ON membership
    """
    cfg = cfg or {}
    sid = ST.sid_for_tag(tag)
    if sid is None:
        return True
    if ST.is_not_a_lane(sid):
        return False
    if not enabled(cfg, mode):
        return sid in ST.EXISTING_LANE_SIDS
    return switch_on(sid, cfg)


def switch_on(tag, cfg: Optional[dict]) -> bool:
    """The strategy's own program switch, whatever the program's state: the
    cm_lanes override, else DEFAULT_ON membership (not-a-lane tabs: False).
    This is what buys once the program is ON; strategy_on is what buys NOW."""
    cfg = cfg or {}
    sid = ST.sid_for_tag(tag)
    if sid is None or ST.is_not_a_lane(sid):
        return False
    lanes = cfg.get("cm_lanes") if isinstance(cfg.get("cm_lanes"), dict) else {}
    v = lanes.get(sid)
    if isinstance(v, bool):
        return v
    return sid in ST.DEFAULT_ON


def open_cap(cfg: Optional[dict], mode) -> int:
    return PROGRAM_MAX_OPEN if enabled(cfg, mode) else risk_rules.MAX_POSITIONS


def _lane_caps(cfg: Optional[dict], sid: str) -> dict:
    caps = (cfg or {}).get("cm_lane_caps")
    caps = caps if isinstance(caps, dict) else {}
    c = caps.get(sid) if isinstance(caps.get(sid), dict) else {}
    per_day, max_open = PER_STRATEGY_MAX_ENTRIES_PER_DAY, PER_STRATEGY_MAX_OPEN
    try:
        if c.get("per_day") is not None:
            per_day = min(per_day, int(c["per_day"]))
    except (TypeError, ValueError):
        pass
    try:
        if c.get("max_open") is not None:
            max_open = min(max_open, int(c["max_open"]))
    except (TypeError, ValueError):
        pass
    return {"per_day": max(0, per_day), "max_open": max(0, max_open)}


# ── In-flight (a1): positions + pending entry orders ─────────────────────────
def _qty(o) -> float:
    return _f(o.get("qty")) or 0.0


def inflight(brk) -> dict:
    """{"positions": set, "pending_buys": set, "pending_notional": float}.

    Keys are broker symbols (a stock ticker or an OCC string).
      positions   every brk.positions() row — stocks AND option rows; a
                  filled spread is 2 rows.
      pending     top-level open BUY rows (status in PENDING_BUY_STATUSES,
                  not buy_to_close) -> the row's symbol; any open row with
                  order_class mleg, or with a leg whose position_intent opens
                  -> every opening leg's OCC (a pending 2-leg spread counts 2,
                  the same as once it fills).
    Raises BrokerError; the caller fails CLOSED."""
    positions = brk.positions() or []
    orders = brk.open_orders() or []
    pos_syms, marks = set(), {}
    for p in positions:
        if not isinstance(p, dict):
            continue
        s = str(p.get("symbol") or "").upper()
        if s:
            pos_syms.add(s)
            px = _f(p.get("current_price"))
            if px:
                marks[s] = px
    pending, notional = set(), 0.0
    for o in orders:
        if not isinstance(o, dict):
            continue
        status = str(o.get("status") or "").lower()
        if status not in PENDING_BUY_STATUSES:
            continue
        legs = [l for l in (o.get("legs") or []) if isinstance(l, dict)]
        is_mleg = str(o.get("order_class") or "").lower() == "mleg"
        has_intents = any(l.get("position_intent") for l in legs)
        opening = [l for l in legs
                   if str(l.get("position_intent") or "").lower() in OPEN_INTENTS]
        if is_mleg or opening:
            use = opening if (opening or has_intents) else legs
            for l in use:
                occ = str(l.get("symbol") or "").upper()
                if occ:
                    pending.add(occ)
            if use:
                lim = _f(o.get("limit_price"))
                notional += _qty(o) * 100.0 * abs(lim or 0.0)
            continue
        if str(o.get("side") or "").lower() != "buy":
            continue
        if str(o.get("position_intent") or "").lower() == "buy_to_close":
            continue
        sym = str(o.get("symbol") or "").upper()
        if not sym:
            continue
        pending.add(sym)
        lim = _f(o.get("limit_price"))
        if str(o.get("asset_class") or "") == "us_option" or _OCC_RE.match(sym):
            notional += _qty(o) * 100.0 * abs(lim or 0.0)
        elif lim:
            notional += _qty(o) * lim
        elif _f(o.get("notional")):
            notional += _f(o.get("notional"))
        else:                                      # a market order: price it at the mark
            notional += _qty(o) * (marks.get(sym) or 0.0)
    return {"positions": pos_syms, "pending_buys": pending,
            "pending_notional": round(notional, 2)}


# ── The minute clock (d1) ────────────────────────────────────────────────────
def minute_key(now: Optional[datetime] = None) -> str:
    """ET minute bucket "YYYY-MM-DDTHH:MM". With no `now`, the minute the
    current tick pinned (set_tick_minute), else the wall clock."""
    if now is None and _TICK_MINUTE:
        return _TICK_MINUTE
    return _now_et(now).strftime("%Y-%m-%dT%H:%M")


def set_tick_minute(now: Optional[datetime]) -> None:
    """Pin the minute for this process (the cron tick is one process per
    minute); None clears the pin."""
    global _TICK_MINUTE
    _TICK_MINUTE = None if now is None else _now_et(now).strftime("%Y-%m-%dT%H:%M")


def _taken_text(doc: Optional[dict]) -> str:
    d = doc if isinstance(doc, dict) else {}
    return "%s (taken by %s %s at %s ET)" % (
        MINUTE_TAKEN_TEXT, d.get("sid") or "?", d.get("symbol") or "?", _hms(d.get("at")))


def minute_taken(now: Optional[datetime] = None) -> Optional[dict]:
    """Read-only peek: {sid, symbol, at, minute} when this minute (or a newer
    one) is already claimed, else None. An unreadable clock is {"error": ...},
    which every caller treats as taken (fail closed)."""
    coll = _coll(PROGRAM_STATE_COLL)
    if coll is None:
        return {"error": "program_state unavailable"}
    try:
        doc = coll.find_one({"_id": ENTRY_CLOCK_ID})
    except Exception as exc:                       # noqa: BLE001
        return {"error": str(exc)[:200]}
    if not isinstance(doc, dict):
        return None
    key = minute_key(now)
    m = doc.get("minute")
    if isinstance(m, str) and m >= key:
        return {"sid": doc.get("sid"), "symbol": doc.get("symbol"),
                "at": doc.get("at"), "minute": m}
    return None


def minute_taken_reason(t: Optional[dict]) -> Optional[str]:
    if not t:
        return None
    if t.get("error"):
        return TRANSIENT_PREFIX + "entry clock unreadable"
    return _taken_text(t)


def _is_dup(exc) -> bool:
    try:
        from pymongo.errors import DuplicateKeyError
        if isinstance(exc, DuplicateKeyError):
            return True
    except Exception:                              # noqa: BLE001
        pass
    return type(exc).__name__ == "DuplicateKeyError"


def claim(tag, symbol, *, now: Optional[datetime] = None) -> tuple:
    """Take this ET minute for one entry — atomically, in every mode, program
    ON or OFF. manual is exempt. (True, None) or (False, reason).

    One find_one_and_update on program_state `entry_clock` filtered on
    minute < key with upsert: a missing doc is inserted; an existing doc at
    this minute (or a newer one) fails the filter, the upsert collides on _id
    and Mongo raises DuplicateKeyError -> refused. The keys are ISO strings,
    so a slow earlier tick can never claim backwards."""
    sid = ST.norm(tag)
    if sid == "manual":
        return True, None
    key = minute_key(now)
    coll = _coll(PROGRAM_STATE_COLL)
    if coll is None:
        return False, TRANSIENT_PREFIX + "entry clock unreadable"
    doc = {"minute": key, "sid": sid, "symbol": str(symbol or "").upper(), "at": _at(now)}
    try:
        coll.find_one_and_update({"_id": ENTRY_CLOCK_ID, "minute": {"$lt": key}},
                                 {"$set": doc}, upsert=True)
        return True, None
    except Exception as exc:                       # noqa: BLE001
        if _is_dup(exc):
            try:
                cur = coll.find_one({"_id": ENTRY_CLOCK_ID})
            except Exception:                      # noqa: BLE001
                cur = None
            return False, _taken_text(cur)
        log.warning("program entry clock claim failed: %s", exc)
        return False, TRANSIENT_PREFIX + "entry clock unreadable"


# ── The program ledger ───────────────────────────────────────────────────────
def record_entry(tag, symbol, *, asset: str = "stock", occ=None, order_id=None,
                 client_order_id=None, snapshot_ref=None,
                 now: Optional[datetime] = None) -> None:
    """One program_entries doc per placed entry (fenced; never raises)."""
    coll = _coll(PROGRAM_ENTRIES_COLL)
    if coll is None:
        return
    n = _now_et(now)
    try:
        coll.insert_one({"sid": ST.norm(tag), "tag": tag, "symbol": str(symbol or "").upper(),
                         "asset": asset, "occ": (str(occ).upper() if occ else None),
                         "day": n.date().isoformat(), "epoch": n.timestamp(),
                         "at": n.isoformat(timespec="seconds"),
                         "order_id": order_id, "client_order_id": client_order_id,
                         "snapshot_ref": snapshot_ref})
    except Exception as exc:                       # noqa: BLE001
        log.warning("program_entries write failed %s %s: %s", tag, symbol, exc)


def log_skip(tag, symbol, reason, *, now: Optional[datetime] = None) -> None:
    """Why a lane did not buy, deduped per ET day in Mongo (count + last_at).
    Sid-level reasons use the symbol "*". Fenced; never raises."""
    coll = _coll(LOG_COLL)
    if coll is None:
        return
    n = _now_et(now)
    day = n.date().isoformat()
    sid = ST.norm(tag)
    sym = str(symbol or "*").upper() if symbol not in (None, "*") else "*"
    text = str(reason or "")
    try:
        coll.update_one({"_id": "%s:%s:%s:%s" % (day, sid, sym, text[:LOG_REASON_KEY_CHARS])},
                        {"$inc": {"count": 1},
                         "$set": {"day": day, "sid": sid, "symbol": sym,
                                  "reason": text[:300],
                                  "last_at": n.isoformat(timespec="seconds")}},
                        upsert=True)
    except Exception as exc:                       # noqa: BLE001
        log.debug("cm_lane_log write failed: %s", exc)


def is_transient(reason) -> bool:
    return TRANSIENT_PREFIX in str(reason or "")


def is_day_cap(reason) -> bool:
    return str(reason or "").startswith(DAY_PREFIX)


def _entries_today(sid: str, day: str) -> Optional[int]:
    coll = _coll(PROGRAM_ENTRIES_COLL)
    if coll is None:
        return None
    try:
        return sum(1 for _ in coll.find({"sid": sid, "day": day}))
    except Exception as exc:                       # noqa: BLE001
        log.warning("program_entries read failed: %s", exc)
        return None


def open_by_sid(open_keys: set) -> Optional[dict]:
    """{sid: n} over the program entries whose symbol (stock) or OCC (option)
    is in positions ∪ pending. A key belongs to the MOST RECENT program entry
    for it. None when the ledger is unreadable."""
    keys = sorted(k for k in (open_keys or set()) if k)
    if not keys:
        return {}
    coll = _coll(PROGRAM_ENTRIES_COLL)
    if coll is None:
        return None
    try:
        rows = list(coll.find({"$or": [{"symbol": {"$in": keys}}, {"occ": {"$in": keys}}]}))
    except Exception as exc:                       # noqa: BLE001
        log.warning("program_entries read failed: %s", exc)
        return None
    latest: dict = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        k = str(r.get("occ") or r.get("symbol") or "").upper()
        if k not in open_keys:
            continue
        if k not in latest or (_f(r.get("epoch")) or 0) >= (_f(latest[k].get("epoch")) or 0):
            latest[k] = r
    out: dict = {}
    for r in latest.values():
        s = r.get("sid")
        out[s] = out.get(s, 0) + 1
    return out


# ── THE CHECK ────────────────────────────────────────────────────────────────
def check(tag, symbol, *, brk, cfg, mode, asset: str = "stock", held: bool = False,
          inf: Optional[dict] = None, now: Optional[datetime] = None,
          adds: int = 1) -> list:
    """Every program block reason for one prospective buy ([] = clear).

    Reasons starting with TRANSIENT_PREFIX clear on their own (retry next
    tick); DAY_PREFIX reasons hold for the ET day. `inf` lets the caller pass
    the inflight() read it already made; without it the broker is read here
    and an unreadable broker raises BrokerError (the caller fails closed).
    `adds` is how many open slots this order takes (2 for a spread)."""
    cfg = cfg or {}
    sid = ST.norm(tag)
    sym = str(symbol or "").upper()
    specific = sym not in ("", "*")
    reasons: list = []
    if ST.is_not_a_lane(tag):
        reasons.append(DAY_PREFIX + "%s is not a lane (%s)" % (sid, ST.NOT_A_LANE.get(sid)))
        return reasons
    if inf is None:
        inf = inflight(brk)
    positions, pending = inf["positions"], inf["pending_buys"]
    cap = open_cap(cfg, mode)
    n_pos, n_pend = len(positions), len(pending - positions)
    # (a) the in-flight open cap — every mode
    if not held and n_pos + n_pend + max(1, int(adds or 1)) > cap:
        text = (TRANSIENT_PREFIX + "portfolio full: %d positions + %d pending entries / %d"
                % (n_pos, n_pend, cap))
        if cap == risk_rules.MAX_POSITIONS:
            text += " (p.312)"
        reasons.append(text)
    # (b) a pending entry for the same symbol — every mode
    if specific and sym in pending:
        reasons.append(TRANSIENT_PREFIX + "entry already pending for %s" % sym)
    roster = ST.is_roster(tag)
    # (c) one lane per name — roster tags, every mode
    if roster and held and specific:
        reasons.append(DAY_PREFIX + "%s already held (one lane per name)" % sym)
    # (d) the minute peek — every non-manual tag, every mode
    if sid != "manual":
        why = minute_taken_reason(minute_taken(now))
        if why:
            reasons.append(why)
    # (e) the strategy switch (a generic sid can never buy while the program
    # is OFF; an existing lane is ON then — its own flag decides)
    if roster and not strategy_on(tag, cfg, mode):
        reasons.append(DAY_PREFIX + "%s is OFF" % sid)
    if roster and enabled(cfg, mode):
        caps = _lane_caps(cfg, sid)
        # (f) per-strategy entries today
        n_today = _entries_today(sid, et_day(now))
        if n_today is None:
            reasons.append(TRANSIENT_PREFIX + "program ledger unreadable")
        elif n_today >= caps["per_day"]:
            reasons.append(DAY_PREFIX + "%s daily cap %d reached" % (sid, caps["per_day"]))
        # (g) per-strategy open (positions + pending)
        by_sid = open_by_sid(positions | pending)
        if by_sid is None:
            reasons.append(TRANSIENT_PREFIX + "program ledger unreadable")
        else:
            n_open = by_sid.get(sid, 0)
            if n_open >= caps["max_open"]:
                reasons.append(TRANSIENT_PREFIX + "%s %d open (max %d)"
                               % (sid, n_open, caps["max_open"]))
    return list(dict.fromkeys(reasons))


def sid_level(reason) -> bool:
    """A reason that stops every candidate of the sid this tick (not one
    symbol's): OFF, the daily cap, the per-strategy open cap, the minute,
    the open cap, an unreadable ledger/clock."""
    r = str(reason or "")
    return not ("already held" in r or "entry already pending for" in r)


# ── Sizing ───────────────────────────────────────────────────────────────────
def risk_budget(tag, cfg, mode) -> Optional[float]:
    """PROGRAM_RISK_PCT for a roster STOCK sid while the program is ON."""
    if not enabled(cfg, mode) or not ST.is_roster(tag):
        return None
    if ST.norm(tag) == "signals":
        return None
    return PROGRAM_RISK_PCT


def option_risk_pct(tag, own_pct, cfg, mode) -> float:
    """min(own, PROGRAM_RISK_PCT) while the program is ON, else own (HIS CALL
    #3: options_zone drops to 0.25% premium while the program is ON)."""
    try:
        own = float(own_pct)
    except (TypeError, ValueError):
        own = PROGRAM_RISK_PCT
    return min(own, PROGRAM_RISK_PCT) if enabled(cfg, mode) else own


def gross_ok(*, positions: list, pending_notional: float, add_usd: float,
             equity_used: float, cfg=None, mode=None) -> tuple:
    """(ok, reason). Program gross = Σ|market_value| + pending + this buy,
    against PROGRAM_MAX_GROSS_PCT of equity_used. Active only while the
    program is ON (and the cap is not None)."""
    if PROGRAM_MAX_GROSS_PCT is None or not enabled(cfg, mode):
        return True, None
    gross = 0.0
    for p in positions or []:
        if isinstance(p, dict):
            gross += abs(_f(p.get("market_value")) or 0.0)
    gross += float(pending_notional or 0.0) + float(add_usd or 0.0)
    limit = float(equity_used or 0.0) * PROGRAM_MAX_GROSS_PCT / 100.0
    if limit <= 0 or gross > limit:
        return False, (TRANSIENT_PREFIX + "program gross $%.0f would exceed %g%% of equity "
                       "used ($%.0f)" % (gross, PROGRAM_MAX_GROSS_PCT, limit))
    return True, None


# ── Usage order ──────────────────────────────────────────────────────────────
def _usage_read() -> tuple:
    """(counts, last_seen) by TAB from usage_stats; ({}, {}) when unreadable."""
    try:
        import usage
        rows = usage.feature_counts(top=100) or []
    except Exception as exc:                       # noqa: BLE001
        log.debug("usage read failed: %s", exc)
        return {}, {}
    counts, seen = {}, {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        k = str(r.get("key") or "")
        if not k.startswith(USAGE_KEY_PREFIX):
            continue
        tab = k[len(USAGE_KEY_PREFIX):]
        try:
            counts[tab] = int(r.get("count") or 0)
        except (TypeError, ValueError):
            continue
        if r.get("last_seen") is not None:
            seen[tab] = r.get("last_seen")
    return counts, seen


def _sid_counts(counts: dict) -> dict:
    out = {}
    for r in ST.ROSTER:
        if r["klass"] != ST.LANE:
            continue
        out[r["sid"]] = sum(int(counts.get(t) or 0) for t in r["tabs"])
    return out


def priority_order(now: Optional[datetime] = None) -> dict:
    """{"day", "order": [sid], "counts": {sid: n}, "source"} — live usage
    order, read once per ET day and cached in program_state; an empty or
    unreadable usage read falls back to FROZEN_USAGE_2026_09_27."""
    day = et_day(now)
    coll = _coll(PROGRAM_STATE_COLL)
    if coll is not None:
        try:
            doc = coll.find_one({"_id": USAGE_ORDER_ID})
            if isinstance(doc, dict) and doc.get("day") == day and doc.get("order"):
                return {"day": day, "order": list(doc["order"]),
                        "counts": dict(doc.get("counts") or {}),
                        "source": doc.get("source") or "usage_stats"}
        except Exception as exc:                   # noqa: BLE001
            log.debug("usage order cache read failed: %s", exc)
    counts, seen = _usage_read()
    source = "usage_stats"
    if not any(v > 0 for v in counts.values()):
        counts, seen = ST.frozen_counts()
        source = "frozen"
    out = {"day": day, "order": ST.usage_rank(counts, seen),
           "counts": _sid_counts(counts), "source": source}
    if coll is not None and source == "usage_stats":
        try:
            coll.update_one({"_id": USAGE_ORDER_ID}, {"$set": dict(out)}, upsert=True)
        except Exception as exc:                   # noqa: BLE001
            log.debug("usage order cache write failed: %s", exc)
    return out


# ── Config validation (POST /trading/config and the review's Confirm) ────────
def _strict_int(v, lo: int, hi: int, name: str) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise ValueError("%s must be an integer %d..%d" % (name, lo, hi))
    return v


def _lane_sid(key: str) -> str:
    sid = ST.sid_for_tag(key)
    if sid is None or not ST.is_roster(sid):
        raise ValueError("unknown or non-lane strategy %r" % (key,))
    return sid


def validate_updates(payload: dict, current: dict) -> dict:
    """Pure; raises ValueError. Returns the trading_config fields to write
    for any of cm_program / cm_lanes / cm_lane_caps in `payload`."""
    payload = payload if isinstance(payload, dict) else {}
    current = current if isinstance(current, dict) else {}
    out: dict = {}
    if "cm_program" in payload:
        raw = payload.get("cm_program")
        if raw is None:
            out["cm_program"] = False
        elif isinstance(raw, bool):
            out["cm_program"] = raw
            if raw and not current.get("cm_program_started"):
                out["cm_program_started"] = et_day()
        else:
            raise ValueError("cm_program must be a boolean or null")
    if "cm_lanes" in payload:
        raw = payload.get("cm_lanes")
        if not isinstance(raw, dict):
            raise ValueError("cm_lanes must be an object {sid: bool|null}")
        merged = dict(current.get("cm_lanes") or {})
        for k, v in raw.items():
            sid = _lane_sid(k)
            if v is None:
                merged.pop(sid, None)
            elif isinstance(v, bool):
                merged[sid] = v
            else:
                raise ValueError("cm_lanes.%s must be a boolean or null" % k)
        out["cm_lanes"] = merged
    if "cm_lane_caps" in payload:
        raw = payload.get("cm_lane_caps")
        if not isinstance(raw, dict):
            raise ValueError("cm_lane_caps must be an object {sid: {per_day, max_open}|null}")
        merged = {k: dict(v) for k, v in (current.get("cm_lane_caps") or {}).items()
                  if isinstance(v, dict)}
        for k, v in raw.items():
            sid = _lane_sid(k)
            if v is None:
                merged.pop(sid, None)
                continue
            if not isinstance(v, dict) or not v:
                raise ValueError("cm_lane_caps.%s must be an object or null" % k)
            clean = {}
            for ck, cv in v.items():
                if ck == "per_day":
                    clean[ck] = _strict_int(cv, 0, PER_STRATEGY_MAX_ENTRIES_PER_DAY,
                                            "cm_lane_caps.%s.per_day" % k)
                elif ck == "max_open":
                    clean[ck] = _strict_int(cv, 0, PER_STRATEGY_MAX_OPEN,
                                            "cm_lane_caps.%s.max_open" % k)
                else:
                    raise ValueError("cm_lane_caps.%s: unknown key %r" % (k, ck))
            merged[sid] = clean
        out["cm_lane_caps"] = merged
    return out


# ── Status + rules ───────────────────────────────────────────────────────────
def rules_list() -> list:
    """Every program rule, built from the constants (never retyped)."""
    return [
        "Risk %g%% of equity per stock trade, never more than the normal position "
        "size (the losing-streak and pilot multipliers still apply)." % PROGRAM_RISK_PCT,
        "Each strategy: at most %d new buy a day and %d open."
        % (PER_STRATEGY_MAX_ENTRIES_PER_DAY, PER_STRATEGY_MAX_OPEN),
        "At most %d open across the program — stocks, options and pending entries "
        "together; a 2-leg option spread counts 2. Live stays at %d."
        % (PROGRAM_MAX_OPEN, risk_rules.MAX_POSITIONS),
        "One new entry per minute across every lane (manual exempt); the most-used "
        "tab goes first.",
        "One lane per name: a lane never buys a name that is already held.",
        ("Program gross stays at or under %g%% of the equity used for sizing."
         % PROGRAM_MAX_GROSS_PCT) if PROGRAM_MAX_GROSS_PCT is not None
        else "No program gross cap.",
        "Options lanes risk at most %g%% premium while the program is ON." % PROGRAM_RISK_PCT,
        "No auto-pause: a daily review proposes changes and nothing changes without "
        "his Confirm.",
        "UNMEASURED forward paper measurement — every prior is null, inverted or "
        "unmeasured.",
    ]


def _last_entry() -> Optional[dict]:
    coll = _coll(PROGRAM_ENTRIES_COLL)
    if coll is None:
        return None
    try:
        rows = list(coll.find({}).sort("epoch", -1).limit(1))
    except Exception:                              # noqa: BLE001
        return None
    if not rows:
        return None
    r = rows[0]
    return {"sid": r.get("sid"), "symbol": r.get("symbol"), "at": r.get("at")}


def status_block(cfg: Optional[dict], mode, brk=None) -> dict:
    """GET /trading/status `chart_maps_program` and the strategies header."""
    cfg = cfg or {}
    clock = None
    coll = _coll(PROGRAM_STATE_COLL)
    if coll is not None:
        try:
            clock = coll.find_one({"_id": ENTRY_CLOCK_ID})
        except Exception:                          # noqa: BLE001
            clock = None
    clock = clock if isinstance(clock, dict) else {}
    out = {
        "enabled": enabled(cfg, mode),
        "switch": bool(cfg.get("cm_program")),
        "started": cfg.get("cm_program_started"),
        "mode": mode,
        "caps": {"risk_pct": PROGRAM_RISK_PCT,
                 "per_strategy_per_day": PER_STRATEGY_MAX_ENTRIES_PER_DAY,
                 "per_strategy_open": PER_STRATEGY_MAX_OPEN,
                 "max_open": open_cap(cfg, mode),
                 "program_max_open": PROGRAM_MAX_OPEN,
                 "one_entry_per_minute": True,
                 "gross_pct": PROGRAM_MAX_GROSS_PCT,
                 "options_risk_pct": PROGRAM_RISK_PCT},
        "minute": {"key": clock.get("minute"), "sid": clock.get("sid"),
                   "symbol": clock.get("symbol"), "at": clock.get("at")},
        "last_entry": _last_entry(),
        "open": None,
        "rules": rules_list(),
    }
    if brk is not None:
        try:
            inf = inflight(brk)
            keys = inf["positions"] | inf["pending_buys"]
            out["open"] = {"n": len(keys), "positions": len(inf["positions"]),
                           "pending": len(inf["pending_buys"] - inf["positions"]),
                           "by_sid": open_by_sid(keys) or {}}
        except BrokerError as exc:
            out["open"] = {"error": str(exc)[:200]}
        except Exception as exc:                   # noqa: BLE001
            out["open"] = {"error": str(exc)[:200]}
    return out
