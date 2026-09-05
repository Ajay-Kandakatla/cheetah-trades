"""Zone-edge entries — the engine BUYS the Supply & Demand board's own two
signals (paper first, 2026-09-03): demand ARRIVALS and supply BREAKOUTS to
new highs, read straight off the Mongo doc the board renders.

Ajay (2026-09-03): "by the time the alert reaches me I am late and the stock
is already bouncing off ... Can you autopilot this and make buys and sells
tomorrow in RTH? ... Paper trade ... I wanna see the execution time
comparison between you and I."

STRATEGY SCOPE — Supply & Demand, NOT Minervini. Every ENTRY rule below is
an OWNER RULE (Ajay's S&D playbook, docs/supply_demand/zone_edge_autopilot.md).
There is no book behind them and none is cited. The RISK math (stop clamp to
the 10% line, target >= 2:1, 25% sizing, streak multiplier, never average
down, earnings shield, MAX_POSITIONS) is the engine-wide contract every buy
already passes through — trading.entries.enter() -> trading/risk_rules.py
(FROZEN). This module only REQUESTS a stop; risk_rules decides.

Signal source (built by supply_demand/zone_edge.py, one pass a minute in
RTH; this module never computes zones itself):
  zone_edge_latest  _id 'latest' = {as_of (ET ISO), date, in_session,
                    breaking: [row], near_demand: [row], counts}
  zone_edge_track   {symbol, date, ts (ET ISO), side, tier, px, dist_pct,
                    band:{lo,hi}} — one row per listed row per pass
  row = {symbol, name, last, dist_pct, tier ('near'|'broke'|'in'),
         side ('supply'|'demand'), role, band:{kind,lo,hi,touches,strength},
         cap, new_highs, high_252, pct_to_52w, overhead_bands, arrival,
         first_seen ('HH:MM' ET), url}

Candidates per tick (owner rules; missing fields FAIL CLOSED):
  demand    near_demand rows with arrival=True, tier in ('near','in'),
            band.touches >= MIN_TOUCHES, cap >= MIN_CAP_USD.
            stop = band.lo * (1 - STOP_BUFFER_PCT/100)   (under the floor)
  breakout  breaking rows with tier='broke' AND new_highs=True AND
            band.touches >= MIN_TOUCHES AND cap >= MIN_CAP_USD.
            stop = band.lo * (1 - STOP_BUFFER_PCT/100)   (the cleared band
            becomes support). A 'near' resistance row is NEVER bought —
            it is not through yet.
  stop_pct = (last - stop) / last * 100; wider than risk_rules.
  ABS_MAX_STOP_PCT -> blocked. The stop is handed to entries.enter as the
  ABSOLUTE level (stop_price=), never as a percent of whatever the tape
  prints at order time: a print that drifted up since the signal would
  otherwise pull a percent stop up INSIDE the band being bought
  (2026-09-05 fix). entries refuses (does not clamp) when the drift
  pushes the level past ABS_MAX_STOP_PCT or through the print.
  Room sanity: the FIRST band overhead — a supply band with hi >= last
  (one containing the print = zero room) or a demand band with lo > last
  (broken support = resistance; the rule portfolio.supply_watch and
  supply_demand.bounce_room already apply) — read from the zone_store doc
  (ONE read per candidate) must sit at least MIN_REWARD_RISK x the stop
  that will be PLACED (max(stop_pct, RISK_STOP_FLOOR_PCT)) away;
  breakouts to new highs with no supply overhead skip the room check.
  Order: breakouts first, then demand arrivals by dist_pct ascending.

Safety invariants (same house rules as exit_engine / entries / auto_entry):
  * NEVER places an order at the broker directly — buys flow through
    entries.enter() so armed / sizing / never-average-down / earnings /
    MAX_POSITIONS all still apply (contract test greps this module).
  * armed=false places NO orders, ever; the zone_edge_entry flag is a
    second, independent switch (default OFF in every mode).
  * A stale signal doc (older than SIGNAL_MAX_AGE_SEC, wrong date, or
    unparseable) places NOTHING — the board's cron being dead must never
    turn into trades off yesterday's prints.
  * One attempt per (symbol, band, ET day), recorded BEFORE entries.enter
    is called (blocked / error attempts too) so a rejected name is never
    retried every minute. Only a 'market closed' veto is left unrecorded.
    The attempt store FAILS CLOSED: an unreadable or unwritable
    zone_edge_entry_state means NO order this tick (a crash mid-enter
    without a durable record would otherwise be retried every minute).
  * The try/except wraps ONLY entries.enter(): once it has returned an
    order exists, and no bookkeeping failure may relabel it blocked/error.
  * A symbol already bought today under another band is skipped, never
    re-attempted (the broker's same-day client_order_id would reject it).
  * run() is called from exit_engine.tick() step (h) inside try/except —
    a zone-entry crash can never break stop protection.
  * Import-light: stdlib + trading modules only; supply_demand and push
    imports are lazy.

EXECUTION RACE ledger (`execution_race`): one doc per (symbol, side, band,
ET day) for EVERY candidate attempt, blocked ones included — the race
records that the engine saw the signal at signal time. reconcile_race()
stamps the engine fill (broker closed orders by client_order_id, the same
path exit_engine reads fills from), Ajay's first view of the ticker page
(analytics usage_events, route /sepa/{SYM}) and his manual Portfolio fill
(portfolio_holdings added/updated after the signal). Read-only over every
collection but its own.
"""
from __future__ import annotations

import logging
import math
import os
import statistics
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from trading import entries
from trading import risk_rules
from trading.broker import get_broker
from trading.exit_engine import (
    _broker_mode, _db, _et_day, _utc_iso, get_config, ledger, update_config)

broker = get_broker()    # module-level so tests can monkeypatch ZE.broker

log = logging.getLogger("trading.zone_edge_entry")

ET = ZoneInfo("America/New_York")

# ──────────────────────────────────────────────────────────────────────────────
# OWNER RULES — Ajay's Supply & Demand entry parameters for the paper trial.
# NOT book numbers (no book exists for this strategy). Locked verbatim in
# tests/test_trading_contracts.py; changing any needs Ajay's sign-off.
# ──────────────────────────────────────────────────────────────────────────────
# Max zone-edge buys per ET day — observation-friendly pace for the trial.
MAX_ZONE_ENTRIES_PER_DAY = 4
# The requested stop sits this far UNDER the band floor (a print through
# the floor is the thesis failing, not noise to sit through).
STOP_BUFFER_PCT = 0.5
# Bands with fewer touches are not proven structure — same floor the board's
# own pushes use (supply_demand/zone_edge.py MIN_TOUCHES_PUSH).
MIN_TOUCHES = 2
# Owner switches (Ajay 2026-09-03 evening, for the paper run): "Enter anything
# that is in demand zone to buy ... Any time any stocks crossing the
# resistance or supply zone buy them too". Defaults = the STRICT rules the
# module shipped with; the live values come from get_config()["zone_edge_rules"]
# (POST /trading/config {"zone_edge_rules": {...}}), so the strict/wide split
# stays available as a named paper experiment without a code fork.
RULES_DEFAULT = {"demand_residents": False,   # True: buy names already IN a demand band
                 "breakout_any_band": False,  # True: buy any cross through a supply band
                 "min_touches": MIN_TOUCHES}  # bands tested fewer times are skipped
# "billion or at least bigger than a billion" — mirrors zone_store.MIN_CAP_USD.
MIN_CAP_USD = 1e9
# risk_rules.initial_stop floors every PLACED stop at this percent ("a stop
# tighter than 1% is a data error, not a plan" — the bare literal
# `pct = max(pct, 1.0)` in trading/risk_rules.py, which is FROZEN, so the
# value is mirrored here rather than imported; tests/test_trading_contracts.py
# pins the two together). The room gate measures its 2R off the stop the
# engine will actually place, never off a tighter request it would widen.
RISK_STOP_FLOOR_PCT = 1.0
# A latest doc older than this is STALE: the 1-min board cron is behind or
# dead, and a 3-min-old print is not "now". No entries on a stale doc.
SIGNAL_MAX_AGE_SEC = 180
# No NEW entries at or after this ET time (the 15:44 tick is the last one);
# exits keep running to the close as always.
LAST_ENTRY_ET = dtime(15, 45)
STATE_COLL = "zone_edge_entry_state"
RACE_COLL = "execution_race"
# Signal source collections (owned by supply_demand/zone_edge.py — read only).
LATEST_COLL = "zone_edge_latest"
TRACK_COLL = "zone_edge_track"
# Race reconciliation window: today + yesterday (ET calendar days).
RECONCILE_DAYS = 2
# A track print counts as "the price at that minute" only inside this window.
TRACK_MATCH_SEC = 300

CITE = ("entry: Supply & Demand OWNER RULES, no book "
        "(docs/supply_demand/zone_edge_autopilot.md); stop/target/size via "
        "entries.enter -> trading/risk_rules.py (engine-wide risk contract)")


# ── Small pure helpers ───────────────────────────────────────────────────────

def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (math.inf, -math.inf):
        return None
    return v


def _i(x) -> Optional[int]:
    v = _f(x)
    return None if v is None else int(v)


def _num(x):
    """JSON-safe number: None for NaN/inf/non-numeric, else a rounded float."""
    v = _f(x)
    return None if v is None else round(v, 4)


def _to_dt(v) -> Optional[datetime]:
    """Aware datetime from an epoch (int/float, UTC), an ISO string ('Z' or
    offset; naive = UTC), or a datetime (naive = UTC). None when unreadable."""
    if v is None or v == "":
        return None
    try:
        if isinstance(v, datetime):
            dt = v
        elif isinstance(v, (int, float)):
            dt = datetime.fromtimestamp(float(v), timezone.utc)
        else:
            s = str(v).strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _secs(later, earlier) -> Optional[float]:
    a, b = _to_dt(later), _to_dt(earlier)
    if a is None or b is None:
        return None
    return round((a - b).total_seconds(), 1)


def _now_et() -> datetime:
    return datetime.now(ET)


def _recent_days(now_et: datetime, n: int) -> list:
    d0 = now_et.astimezone(ET).date()
    return [(d0 - timedelta(days=k)).isoformat() for k in range(max(1, int(n)))]


def _owner_email() -> str:
    """The owner whose views/fills the race is measured against — same env
    order as portfolio.alerts._resolve_owner (not imported: keep this module
    import-light)."""
    return (os.getenv("PORTFOLIO_ALERT_OWNER")
            or os.getenv("HOUSE_OWNER_EMAIL")
            or "ajaykandakatla@gmail.com").lower()


# ── Mongo seams (each monkeypatchable in tests) ─────────────────────────────

def _coll(name: str):
    db = _db()
    if db is None:
        return None
    try:
        return getattr(db, name)
    except Exception as exc:                       # noqa: BLE001
        log.warning("zone_edge_entry: collection %s unavailable: %s", name, exc)
        return None


def _latest_doc() -> Optional[dict]:
    coll = _coll(LATEST_COLL)
    if coll is None:
        return None
    try:
        return coll.find_one({"_id": "latest"})
    except Exception as exc:                       # noqa: BLE001
        log.warning("zone_edge_entry: latest read failed: %s", exc)
        return None


def _zone_doc(symbol: str, day: str) -> Optional[dict]:
    """The symbol's zone_store doc for `day` (ONE read, one symbol) — the
    room check's supply-overhead source. None = unknown (fails closed)."""
    try:
        from supply_demand import zone_store
        docs = zone_store.load([symbol], date.fromisoformat(day)) or {}
        return docs.get(symbol)
    except Exception as exc:                       # noqa: BLE001
        log.warning("zone_edge_entry: zone_store read failed %s: %s", symbol, exc)
        return None


def _notify(symbol: str, side: str, mode_word: str, body: str) -> None:
    """Owner push (push.sender.send_to_user to the admin, kind=None — the
    same always-wanted routing push.hooks.notify_autopilot uses). Failures
    are logged + swallowed: push can never break the entry path."""
    try:
        from push import sender
        from push.hooks import ADMIN_EMAIL
        payload = {"title": "🎯 Zone-edge %s buy %s %s" % (mode_word, symbol, side),
                   "body": body,
                   "tag": "zone-edge-entry-%s" % symbol,
                   "url": "/trading", "kind": "autopilot", "ticker": symbol}
        sender.send_to_user(ADMIN_EMAIL, payload, kind=None)
    except Exception as exc:                       # noqa: BLE001
        log.warning("zone_edge_entry: push failed (%s): %s", symbol, exc)


def _mode_word(brk) -> str:
    try:
        m = getattr(brk, "mode", None)
        mode = str(m()) if callable(m) else _broker_mode()
    except Exception:                              # noqa: BLE001
        mode = "paper"
    return "LIVE" if mode == "live" else mode


# ── zone_edge_entry_state (per symbol + band + ET day) ──────────────────────

def state_key(symbol: str, band: dict, day: str) -> str:
    return "%s:%g-%g:%s" % (symbol, float(band["lo"]), float(band["hi"]), day)


def _get_state(key: str) -> Optional[dict]:
    """The attempt record for `key` ({} when none). None = UNKNOWN (no
    collection / read failed) — run() fails closed on None (no order)."""
    coll = _coll(STATE_COLL)
    if coll is None:
        return None
    try:
        return coll.find_one({"key": key}) or {}
    except Exception as exc:                       # noqa: BLE001
        log.warning("zone_edge_entry_state read failed %s: %s", key, exc)
        return None


def _set_state(key: str, **fields) -> bool:
    """True only when the write went through. run() places NO order on
    False: without a durable attempt record a crash mid-enter would be
    retried every minute."""
    coll = _coll(STATE_COLL)
    if coll is None:
        return False
    fields["updated_at"] = _utc_iso()
    try:
        coll.update_one({"key": key}, {"$set": fields}, upsert=True)
        return True
    except Exception as exc:                       # noqa: BLE001
        log.warning("zone_edge_entry_state write failed %s: %s", key, exc)
        return False


def _clear_state(key: str) -> None:
    coll = _coll(STATE_COLL)
    if coll is None:
        return
    try:
        coll.delete_many({"key": key})
    except Exception as exc:                       # noqa: BLE001
        log.warning("zone_edge_entry_state clear failed %s: %s", key, exc)


def _entered_today(day: str) -> Optional[list]:
    """State rows with entered=True for `day`; None = UNKNOWN (no collection
    / read failed) so the daily cap and per-symbol guards fail closed."""
    coll = _coll(STATE_COLL)
    if coll is None:
        return None
    try:
        return [d for d in coll.find({"date": day, "entered": True})
                if isinstance(d, dict)]
    except Exception as exc:                       # noqa: BLE001
        log.warning("zone_edge_entry_state count failed: %s", exc)
        return None


def _entries_today(day: str) -> Optional[int]:
    rows = _entered_today(day)
    return None if rows is None else len(rows)


def _today_attempts(day: str) -> list:
    coll = _coll(STATE_COLL)
    rows = []
    if coll is None:
        return rows
    try:
        for d in coll.find({"date": day}):
            d.pop("_id", None)
            rows.append(d)
    except Exception as exc:                       # noqa: BLE001
        log.warning("zone_edge_entry_state list failed: %s", exc)
    return rows


# ── Pure funnel pieces (unit-tested) ─────────────────────────────────────────

def signal_state(latest: Optional[dict], now_et: datetime, day: str) -> dict:
    """Freshness verdict for the board doc. FAILS CLOSED: no doc, wrong ET
    date, missing/unparseable as_of, or age > SIGNAL_MAX_AGE_SEC -> not
    fresh. Returns the detail dict the status block and ledger carry."""
    out = {"fresh": False, "as_of": None, "date": None, "age_sec": None,
           "max_age_sec": SIGNAL_MAX_AGE_SEC, "in_session": None,
           "counts": None, "reason": None}
    if not latest or not isinstance(latest, dict):
        out["reason"] = "no zone_edge_latest doc"
        return out
    out["as_of"] = latest.get("as_of")
    out["date"] = latest.get("date")
    out["in_session"] = latest.get("in_session")
    out["counts"] = latest.get("counts")
    if str(latest.get("date") or "") != str(day):
        out["reason"] = "doc date %s != today %s" % (latest.get("date"), day)
        return out
    as_of = _to_dt(latest.get("as_of"))
    if as_of is None:
        out["reason"] = "as_of missing/unparseable"
        return out
    age = (now_et - as_of).total_seconds()
    out["age_sec"] = round(age, 1)
    if age > SIGNAL_MAX_AGE_SEC:
        out["reason"] = "stale: %.0fs old > %ds" % (age, SIGNAL_MAX_AGE_SEC)
        return out
    if age < -SIGNAL_MAX_AGE_SEC:
        # A doc stamped well in the future is a clock-skew / bad-data sign,
        # not a fresh print — fail closed rather than trust it.
        out["reason"] = "as_of %.0fs in the future — not trusted" % (-age)
        return out
    out["fresh"] = True
    return out


def active_rules(cfg: Optional[dict] = None) -> dict:
    """RULES_DEFAULT overlaid with cfg["zone_edge_rules"] — unknown keys
    ignored, wrong types fall back to the default (fail to STRICT)."""
    out = dict(RULES_DEFAULT)
    raw = (cfg or {}).get("zone_edge_rules") if isinstance(cfg, dict) else None
    if isinstance(raw, dict):
        for key in ("demand_residents", "breakout_any_band"):
            if isinstance(raw.get(key), bool):
                out[key] = raw[key]
        mt = raw.get("min_touches")
        if isinstance(mt, int) and not isinstance(mt, bool) and 1 <= mt <= 10:
            out["min_touches"] = mt
    return out


def _qualify(kind: str, row: dict, rules: Optional[dict] = None) -> Optional[str]:
    """None when the row is a candidate of `kind` ('breakout'|'demand'),
    else the rejection reason. Every missing field fails CLOSED. `rules` =
    active_rules(cfg); None = the strict defaults."""
    rules = rules or RULES_DEFAULT
    raw_sym = row.get("symbol")
    sym = raw_sym.strip().upper() if isinstance(raw_sym, str) else ""
    if not sym:
        return "no symbol"
    last = _f(row.get("last"))
    if last is None or last <= 0:
        return "no print"
    band = row.get("band")
    if not isinstance(band, dict):
        return "no band"
    lo, hi = _f(band.get("lo")), _f(band.get("hi"))
    if lo is None or hi is None or lo <= 0 or hi < lo:
        return "no band"
    touches = _i(band.get("touches"))
    if touches is None:
        return "touches unknown"
    min_touches = int(rules.get("min_touches", MIN_TOUCHES))
    if touches < min_touches:
        return "touches %d < %d" % (touches, min_touches)
    cap = _f(row.get("cap"))
    if cap is None:
        return "cap unknown"
    if cap < MIN_CAP_USD:
        return "cap < $%gB" % (MIN_CAP_USD / 1e9)
    side = str(row.get("side") or "")
    tier = str(row.get("tier") or "")
    if kind == "breakout":
        if side != "supply":
            return "not a supply row"
        if tier != "broke":
            return "near resistance (not through)"
        if not rules.get("breakout_any_band") and row.get("new_highs") is not True:
            return "no new highs"
        return None
    if side != "demand":
        return "not a demand row"
    if tier not in ("near", "in"):
        return "tier %r not near/in" % tier
    if not rules.get("demand_residents") and row.get("arrival") is not True:
        return "resident (no arrival)"
    return None


def stop_request(last, band_lo) -> tuple:
    """(stop_price, stop_pct) — the OWNER stop under the band floor as a
    percent request for entries.enter. (None, None) on bad inputs."""
    last, lo = _f(last), _f(band_lo)
    if last is None or lo is None or last <= 0 or lo <= 0:
        return None, None
    stop_price = round(lo * (1.0 - STOP_BUFFER_PCT / 100.0), 4)
    stop_pct = round((last - stop_price) / last * 100.0, 2)
    return stop_price, stop_pct


def room_ok(last, stop_pct, zone_doc: Optional[dict]) -> tuple:
    """Room sanity for an entry: the FIRST band price meets going up must
    sit >= risk_rules.MIN_REWARD_RISK x the stop that will be PLACED
    (max(stop_pct, RISK_STOP_FLOOR_PCT)) away, in %.

    Overhead is kind-agnostic — the same rule portfolio.supply_watch.
    overhead_bands and supply_demand.bounce_room.first_overhead apply:
      * a SUPPLY band with hi >= last; one CONTAINING the print (lo <= last
        <= hi) is zero room -> blocked 'inside supply band';
      * a DEMAND band with lo > last — broken support is resistance. A
        demand band containing or below the print is support, not overhead.
    Nothing overhead = unbounded room = ok. No zone doc = unknown = NOT ok
    (fails closed). Returns (ok, detail)."""
    last, stop_pct = _f(last), _f(stop_pct)
    need = None
    if last is not None and stop_pct is not None:
        need = round(risk_rules.MIN_REWARD_RISK * max(stop_pct, RISK_STOP_FLOOR_PCT), 2)
    detail = {"need_pct": need, "room_pct": None, "next_band": None,
              "reason": None}
    if not isinstance(zone_doc, dict) or last is None or stop_pct is None:
        detail["reason"] = "room unknown (no zone_store doc)"
        return False, detail
    bands = zone_doc.get("bands")
    if not isinstance(bands, list) or not all(isinstance(b, dict) for b in bands):
        detail["reason"] = "room unknown (malformed zone_store doc)"
        return False, detail
    overhead = []                                  # (lo, hi, kind)
    for b in bands:
        kind = str(b.get("kind") or "")
        lo, hi = _f(b.get("lo")), _f(b.get("hi"))
        if lo is None:
            continue
        if hi is None or hi < lo:
            hi = lo                                # degenerate band = its floor
        if kind == "supply" and hi >= last:
            overhead.append((lo, hi, kind))
        elif kind == "demand" and lo > last:
            overhead.append((lo, hi, kind))
    if not overhead:
        detail["reason"] = "no band overhead"
        return True, detail
    inside = [b for b in overhead if b[0] <= last <= b[1]]
    nxt = min(inside or overhead, key=lambda b: b[0])
    detail["next_band"] = {"kind": nxt[2], "lo": nxt[0], "hi": nxt[1]}
    if inside:
        detail["room_pct"] = 0.0
        detail["reason"] = "inside supply band (%g-%g): no room" % (nxt[0], nxt[1])
        return False, detail
    room = round((nxt[0] - last) / last * 100.0, 2)
    detail["room_pct"] = room
    if room < need:
        detail["reason"] = "room < %gR (%.2f%% < %.2f%% to %s band %g-%g)" % (
            risk_rules.MIN_REWARD_RISK, room, need, nxt[2], nxt[0], nxt[1])
        return False, detail
    detail["reason"] = "ok"
    return True, detail


def _candidate(kind: str, row: dict) -> dict:
    band = row.get("band") or {}
    return {"symbol": str(row.get("symbol") or "").strip().upper(),
            "kind": kind, "side": str(row.get("side") or ""),
            "tier": str(row.get("tier") or ""), "role": row.get("role"),
            "last": float(row.get("last")),
            "band": {"kind": band.get("kind"), "lo": float(band["lo"]),
                     "hi": float(band["hi"]), "touches": _i(band.get("touches")),
                     "strength": _f(band.get("strength"))},
            "dist_pct": _f(row.get("dist_pct")),
            "first_seen": row.get("first_seen"),
            "new_highs": row.get("new_highs"),
            "arrival": row.get("arrival") is True,
            "overhead_bands": _i(row.get("overhead_bands")),
            "cap": _f(row.get("cap")), "url": row.get("url")}


def read_candidates(latest: Optional[dict], rules: Optional[dict] = None) -> tuple:
    """Pure funnel over one zone_edge_latest doc -> (candidates, rejected).
    Breakouts first (least extended past the cleared band first), then
    demand ARRIVALS by dist_pct ascending, then (wide rules only) demand
    RESIDENTS by band quality: touches desc, strength desc, dist asc — with
    a 4-a-day cap the freshest touch and the most-tested band go first."""
    rules = rules or RULES_DEFAULT
    breakouts, demands, rejected = [], [], []
    if not isinstance(latest, dict):
        return [], []
    for kind, key in (("breakout", "breaking"), ("demand", "near_demand")):
        rows = latest.get(key)
        for row in (rows if isinstance(rows, list) else []):
            if not isinstance(row, dict):
                continue
            why = _qualify(kind, row, rules)
            if why is None:
                (breakouts if kind == "breakout" else demands).append(
                    _candidate(kind, row))
            else:
                rejected.append({"symbol": str(row.get("symbol") or "").upper(),
                                 "kind": kind, "reason": why})

    def _dist(c):
        d = c.get("dist_pct")
        return math.inf if d is None else abs(float(d))

    breakouts.sort(key=_dist)
    arrivals = [c for c in demands if c.get("arrival")]
    residents = [c for c in demands if not c.get("arrival")]
    arrivals.sort(key=lambda c: (math.inf if c.get("dist_pct") is None
                                 else float(c["dist_pct"])))
    residents.sort(key=lambda c: (-(c["band"].get("touches") or 0),
                                  -(c["band"].get("strength") or 0.0),
                                  math.inf if c.get("dist_pct") is None
                                  else float(c["dist_pct"])))
    return breakouts + arrivals + residents, rejected


def _needs_room_check(c: dict) -> bool:
    """Breakouts to new highs with NO supply overhead skip the room check;
    everything else (demand arrivals, breakouts with bands still above,
    unknown overhead) needs it."""
    return not (c["kind"] == "breakout" and c.get("new_highs") is True
                and c.get("overhead_bands") == 0)


# ── Execution race ledger ────────────────────────────────────────────────────

def race_id(symbol: str, side: str, band: dict, day: str) -> str:
    return "%s:%s:%g-%g:%s" % (symbol, side, float(band["lo"]),
                               float(band["hi"]), day)


def signal_ts_for(day: str, first_seen, as_of) -> tuple:
    """(signal_ts ET ISO, basis). day + 'HH:MM' when the row carries
    first_seen; else the doc's as_of (the engine's first sight)."""
    try:
        hh, mm = str(first_seen).split(":")[:2]
        dt = datetime.combine(date.fromisoformat(day),
                              dtime(int(hh), int(mm)), tzinfo=ET)
        return dt.isoformat(), "first_seen"
    except (TypeError, ValueError, AttributeError):
        pass
    dt = _to_dt(as_of)
    if dt is not None:
        return dt.astimezone(ET).isoformat(), "as_of"
    return None, None


def _write_race(c: dict, day: str, outcome: str, reason: Optional[str],
                as_of, **engine) -> Optional[str]:
    coll = _coll(RACE_COLL)
    if coll is None:
        return None
    rid = race_id(c["symbol"], c["side"], c["band"], day)
    sig_ts, basis = signal_ts_for(day, c.get("first_seen"), as_of)
    stop_pct = engine.pop("stop_pct", None)
    doc = {"symbol": c["symbol"], "side": c["side"], "kind": c["kind"],
           "tier": c["tier"],
           "band": {"lo": c["band"]["lo"], "hi": c["band"]["hi"]},
           "day": day,
           "signal_first_seen": c.get("first_seen"),
           "signal_ts": sig_ts, "signal_ts_basis": basis,
           "signal_px": c["last"], "dist_pct": c.get("dist_pct"),
           "stop_pct": stop_pct,
           "engine_order_ts": engine.get("engine_order_ts"),
           "engine_order_id": engine.get("engine_order_id"),
           "engine_client_order_id": engine.get("engine_client_order_id"),
           "engine_fill_ts": None, "engine_fill_px": None,
           "user_view_ts": None, "user_view_px": None,
           "user_fill_ts": None, "user_fill_px": None,
           "outcome": outcome, "reason": reason,
           "created_at": _utc_iso()}
    try:
        coll.update_one({"_id": rid}, {"$set": doc}, upsert=True)
    except Exception as exc:                       # noqa: BLE001
        log.warning("execution_race write failed %s: %s", rid, exc)
    return rid


def _client_order_id(symbol: str, order_id, brk) -> Optional[str]:
    """The client_order_id entries.enter stamped on its 'entry' ledger row
    for this order; falls back to the broker's deterministic id."""
    db = _db()
    if db is not None and order_id:
        try:
            cur = (db.trade_ledger.find({"kind": "entry", "symbol": symbol})
                   .sort("epoch", -1).limit(5))
            for d in cur:
                det = d.get("detail") or {}
                if det.get("order_id") == order_id and det.get("client_order_id"):
                    return str(det["client_order_id"])
        except Exception as exc:                   # noqa: BLE001
            log.debug("client_order_id lookup failed %s: %s", symbol, exc)
    mk = getattr(brk, "make_client_order_id", None)
    if callable(mk):
        try:
            return str(mk(symbol, "entry"))
        except Exception:                          # noqa: BLE001
            return None
    return None


def _route_matches(route, symbol: str) -> bool:
    r = str(route or "").split("?")[0].split("#")[0].rstrip("/")
    return r.upper() == "/SEPA/%s" % symbol.upper()


def _first_view(owner: str, symbol: str, after_dt: datetime) -> Optional[datetime]:
    """First analytics usage_events row for the owner whose route is the
    ticker page /sepa/{SYM} (any query string) started after `after_dt`."""
    coll = _coll("usage_events")
    if coll is None:
        return None
    try:
        rows = list(coll.find({"user_email": owner.lower(),
                               "started_at": {"$gt": int(after_dt.timestamp())}}))
    except Exception as exc:                       # noqa: BLE001
        log.warning("usage_events read failed: %s", exc)
        return None
    best = None
    for r in rows:
        if not _route_matches(r.get("route"), symbol):
            continue
        ts = _to_dt(r.get("started_at"))
        if ts is None or ts <= after_dt:
            continue
        if best is None or ts < best:
            best = ts
    return best


def _track_px_near(symbol: str, day: str, when: datetime) -> Optional[float]:
    """zone_edge_track px for the symbol nearest `when` (within
    TRACK_MATCH_SEC), else None."""
    coll = _coll(TRACK_COLL)
    if coll is None:
        return None
    try:
        rows = list(coll.find({"symbol": symbol, "date": day}))
    except Exception as exc:                       # noqa: BLE001
        log.warning("zone_edge_track read failed: %s", exc)
        return None
    best, best_gap = None, None
    for r in rows:
        ts = _to_dt(r.get("ts"))
        px = _f(r.get("px"))
        if ts is None or px is None:
            continue
        gap = abs((ts - when).total_seconds())
        if gap <= TRACK_MATCH_SEC and (best_gap is None or gap < best_gap):
            best, best_gap = px, gap
    return best


def _user_fill(owner: str, symbol: str, after_dt: datetime) -> tuple:
    """(fill_dt, per-share cost) from the owner's portfolio_holdings row for
    the symbol added or updated after `after_dt`; (None, None) otherwise."""
    coll = _coll("portfolio_holdings")
    if coll is None:
        return None, None
    try:
        rows = list(coll.find({"user_email": owner.lower(), "ticker": symbol}))
    except Exception as exc:                       # noqa: BLE001
        log.warning("portfolio_holdings read failed: %s", exc)
        return None, None
    best_dt, best_px = None, None
    for r in rows:
        added, updated = _to_dt(r.get("added_at")), _to_dt(r.get("updated_at"))
        ts = None
        if added is not None and added > after_dt:
            ts = added
        elif updated is not None and updated > after_dt:
            ts = updated
        if ts is None:
            continue
        if best_dt is None or ts < best_dt:
            shares, cost = _f(r.get("shares")), _f(r.get("cost_basis"))
            px = round(cost / shares, 4) if (shares and cost is not None
                                             and shares > 0) else None
            best_dt, best_px = ts, px
    return best_dt, best_px


def _engine_fill(doc: dict, orders: list) -> tuple:
    """(fill_ts UTC ISO, fill_px) from the broker's closed orders — matched
    by client_order_id (or order id), filled buys only."""
    coid, oid = doc.get("engine_client_order_id"), doc.get("engine_order_id")
    for o in orders or []:
        if (o.get("status") or "").lower() != "filled":
            continue
        if (o.get("side") or "buy").lower() != "buy":
            continue
        if not ((coid and o.get("client_order_id") == coid)
                or (oid and o.get("id") == oid)):
            continue
        px = _f(o.get("filled_avg_price"))
        ts = _to_dt(o.get("filled_at")) or _to_dt(o.get("updated_at"))
        if px is None or ts is None:
            continue
        return _utc_iso(ts.astimezone(timezone.utc)), px
    return None, None


def reconcile_race(now: Optional[datetime] = None, broker=None) -> dict:
    """Stamp engine fills / owner views / owner fills onto today's and
    yesterday's race docs. Writes ONLY execution_race; every other
    collection (ledger, usage_events, zone_edge_track, portfolio_holdings)
    and the broker are read-only here. Never raises."""
    brk = broker if broker is not None else globals()["broker"]
    now_et = (now or _now_et()).astimezone(ET)
    out = {"checked": 0, "engine_filled": 0, "user_viewed": 0,
           "user_filled": 0, "errors": []}
    coll = _coll(RACE_COLL)
    if coll is None:
        return out
    try:
        docs = list(coll.find({"day": {"$in": _recent_days(now_et, RECONCILE_DAYS)}}))
    except Exception as exc:                       # noqa: BLE001
        out["errors"].append("race read: %s" % exc)
        return out
    owner = _owner_email()
    pending = [d for d in docs
               if d.get("outcome") == "ordered" and not d.get("engine_fill_ts")]
    orders = []
    if pending:
        try:
            since = _utc_iso(datetime.now(timezone.utc)
                             - timedelta(days=RECONCILE_DAYS))
            orders = list(brk.closed_orders_since(since) or [])
        except Exception as exc:                   # noqa: BLE001
            out["errors"].append("closed_orders: %s" % exc)
    for d in docs:
        out["checked"] += 1
        sig = _to_dt(d.get("signal_ts"))
        if sig is None:
            continue
        sym = str(d.get("symbol") or "")
        upd = {}
        if d.get("outcome") == "ordered" and not d.get("engine_fill_ts"):
            ts, px = _engine_fill(d, orders)
            if ts is not None:
                upd["engine_fill_ts"], upd["engine_fill_px"] = ts, px
                out["engine_filled"] += 1
        if not d.get("user_view_ts"):
            view = _first_view(owner, sym, sig)
            if view is not None:
                upd["user_view_ts"] = _utc_iso(view.astimezone(timezone.utc))
                upd["user_view_px"] = _track_px_near(sym, str(d.get("day")), view)
                out["user_viewed"] += 1
        if not d.get("user_fill_ts"):
            fdt, fpx = _user_fill(owner, sym, sig)
            if fdt is not None:
                upd["user_fill_ts"] = _utc_iso(fdt.astimezone(timezone.utc))
                upd["user_fill_px"] = fpx
                out["user_filled"] += 1
        if upd:
            upd["reconciled_at"] = _utc_iso()
            try:
                coll.update_one({"_id": d.get("_id")}, {"$set": upd})
            except Exception as exc:               # noqa: BLE001
                out["errors"].append("race write %s: %s" % (d.get("_id"), exc))
    return out


def enrich_race_row(d: dict) -> dict:
    """One race doc -> API row: doc minus _id plus the lag / price-gap reads.
    JSON-safe (no NaN)."""
    row = {k: v for k, v in d.items() if k != "_id"}
    sig = d.get("signal_ts")
    row["engine_lag_sec"] = _secs(d.get("engine_order_ts"), sig)
    row["engine_fill_lag_sec"] = _secs(d.get("engine_fill_ts"), sig)
    row["user_view_lag_sec"] = _secs(d.get("user_view_ts"), sig)
    row["user_fill_lag_sec"] = _secs(d.get("user_fill_ts"), sig)
    base = _f(d.get("engine_fill_px"))
    if base is None:
        base = _f(d.get("signal_px"))
    row["px_base"] = _num(base)
    vpx, fpx = _f(d.get("user_view_px")), _f(d.get("user_fill_px"))
    row["px_gap_view"] = _num(vpx - base) if (vpx is not None and base is not None) else None
    row["px_gap_fill"] = _num(fpx - base) if (fpx is not None and base is not None) else None
    row["px_gap_fill_pct"] = (_num((fpx - base) / base * 100.0)
                              if (fpx is not None and base) else None)
    for k in ("signal_px", "engine_fill_px", "user_view_px", "user_fill_px",
              "dist_pct", "stop_pct"):
        row[k] = _num(row.get(k))
    return row


def _median(vals: list):
    xs = [float(v) for v in vals if v is not None]
    return _num(statistics.median(xs)) if xs else None


def race_report(days: int = 5, now: Optional[datetime] = None,
                reconcile: bool = True, broker=None) -> dict:
    """GET /trading/race payload: rows (newest signal first) + summary."""
    try:
        days = 5 if days is None else int(days)
    except (TypeError, ValueError):
        days = 5
    days = max(1, min(days, 30))
    now_et = (now or _now_et()).astimezone(ET)
    if reconcile:
        reconcile_race(now=now_et, broker=broker)
    coll = _coll(RACE_COLL)
    docs = []
    if coll is not None:
        try:
            docs = list(coll.find({"day": {"$in": _recent_days(now_et, days)}}))
        except Exception as exc:                   # noqa: BLE001
            log.warning("execution_race read failed: %s", exc)
    rows = [enrich_race_row(d) for d in docs]
    rows.sort(key=lambda r: str(r.get("signal_ts") or ""), reverse=True)
    summary = {
        "n": len(rows),
        "n_ordered": sum(1 for r in rows if r.get("outcome") == "ordered"),
        "n_engine_filled": sum(1 for r in rows if r.get("engine_fill_ts")),
        "n_user_viewed": sum(1 for r in rows if r.get("user_view_ts")),
        "n_user_filled": sum(1 for r in rows if r.get("user_fill_ts")),
        "median_engine_lag_sec": _median([r["engine_lag_sec"] for r in rows]),
        "median_engine_fill_lag_sec": _median([r["engine_fill_lag_sec"] for r in rows]),
        "median_user_view_lag_sec": _median([r["user_view_lag_sec"] for r in rows]),
        "median_user_fill_lag_sec": _median([r["user_fill_lag_sec"] for r in rows]),
        "median_px_gap_fill_pct": _median([r["px_gap_fill_pct"] for r in rows]),
    }
    return {"rows": rows, "summary": summary, "days": days,
            "owner": _owner_email()}


def _res_get(res, key):
    """Field of entries.enter's result; None when the result is not a dict."""
    return res.get(key) if isinstance(res, dict) else None


def _push_body(sym: str, c: dict, res, stop_price, stop_pct) -> str:
    """Push body for a PLACED order. Never raises — a formatting problem
    must not touch the order bookkeeping around it."""
    try:
        plan = _res_get(res, "stop")
        stop_px = _f(plan.get("stop_price")) if isinstance(plan, dict) else None
        if stop_px is None:
            stop_px = _f(stop_price) or 0.0
        return ("%s %s %s: %d sh at ~%.2f, stop %.2f (%.2f%%), band %g-%g, "
                "signal %s"
                % (sym, c["kind"], c["tier"], int(_f(_res_get(res, "shares")) or 0),
                   c["last"], stop_px, _f(stop_pct) or 0.0,
                   c["band"]["lo"], c["band"]["hi"], c.get("first_seen") or "?"))
    except Exception as exc:                       # noqa: BLE001
        log.warning("zone_edge_entry: push body failed %s: %s", sym, exc)
        return "%s %s %s: ordered (detail unavailable)" % (
            sym, c.get("kind"), c.get("tier"))


# ── Disabled-once ledger (mirrors auto_entry) ───────────────────────────────

def _ledger_disabled_once(cfg: dict, gate: dict) -> bool:
    today = _et_day()
    if cfg.get("last_zone_entry_disabled_day") == today:
        return False
    ledger("zone_entry_disabled",
           detail={"gate": gate,
                   "hint": "needs configured + armed + zone_edge_entry flag "
                           "+ market open"})
    update_config(last_zone_entry_disabled_day=today)
    return True


# ── The per-tick runner (exit_engine.tick step (h), AFTER exits) ────────────

def run(broker=None, cfg: Optional[dict] = None) -> dict:
    """Evaluate the board once; place at most MAX_ZONE_ENTRIES_PER_DAY buys
    via entries.enter(). Returns a summary; never raises past its fence."""
    brk = broker if broker is not None else globals()["broker"]
    cfg = cfg or get_config()
    day = _et_day()
    out = {"ok": True, "ran": False, "day": day, "entered": [], "blocked": [],
           "skipped": [], "evaluated": 0, "rejected": 0, "entries_today": 0,
           "errors": []}

    # Master gate: configured AND armed AND zone_edge_entry flag AND open.
    try:
        configured = bool(brk.configured())
    except Exception as exc:                       # noqa: BLE001
        configured = False
        out["errors"].append("configured: %s" % exc)
    gate = {"configured": configured,
            "armed": bool(cfg.get("armed")),
            "zone_edge_entry": bool(cfg.get("zone_edge_entry")),
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
    now_et = _now_et()

    def _finish(reason: Optional[str] = None) -> dict:
        if reason:
            out["reason"] = reason
        try:
            out["race"] = reconcile_race(now=now_et, broker=brk)
        except Exception as exc:                   # noqa: BLE001
            out["errors"].append("reconcile_race: %s" % exc)
        return out

    # Signal freshness — a dead/behind board cron places NOTHING.
    latest = _latest_doc()
    sig = signal_state(latest, now_et, day)
    out["signal"] = sig
    if not sig["fresh"]:
        return _finish("stale_signal")
    # Entry window — no NEW entries at/after LAST_ENTRY_ET.
    if now_et.time() >= LAST_ENTRY_ET:
        return _finish("after_last_entry_time")

    rules = active_rules(cfg)
    out["rules"] = rules
    cands, rejected = read_candidates(latest, rules)
    out["rejected"] = len(rejected)
    if not cands:
        return _finish("no_candidates")

    try:
        positions = brk.positions()
    except Exception as exc:                       # noqa: BLE001
        out["ok"] = False
        out["errors"].append("positions: %s" % exc)
        return _finish("positions_unavailable")
    held = {str(p.get("symbol") or "").upper() for p in positions
            if isinstance(p, dict)}
    pos_count = len(positions)
    # Attempt bookkeeping FAILS CLOSED: if today's state rows cannot be read
    # the daily cap / per-symbol guards cannot be applied -> no attempts this
    # tick (nothing recorded; re-evaluated next tick).
    entered_rows = _entered_today(day)
    if entered_rows is None:
        out["ok"] = False
        out["errors"].append("zone_edge_entry_state unreadable — no attempts")
        return _finish("state_unavailable")
    entries_today = len(entered_rows)
    entered_syms = {str(r.get("symbol") or "").upper() for r in entered_rows}
    as_of = (latest or {}).get("as_of")
    mode_word = _mode_word(brk)
    seen = set()

    def _skip(sym, why):
        out["skipped"].append({"symbol": sym, "reason": why})

    for c in cands:
        sym = c["symbol"]
        out["evaluated"] += 1
        # Cheap skips — NOT attempts: no state, no race doc, re-evaluated
        # next tick if the situation changes.
        if sym in seen:
            _skip(sym, "already handled this tick")
            continue
        if sym in held:
            _skip(sym, "already held")
            continue
        if entries_today >= MAX_ZONE_ENTRIES_PER_DAY:
            _skip(sym, "daily cap %d reached" % MAX_ZONE_ENTRIES_PER_DAY)
            continue
        if pos_count >= risk_rules.MAX_POSITIONS:
            _skip(sym, "no position slot (%d/%d)" % (pos_count, risk_rules.MAX_POSITIONS))
            continue
        key = state_key(sym, c["band"], day)
        st = _get_state(key)
        if st is None:
            # Unknown whether this band was already attempted -> fail closed.
            out["ok"] = False
            out["errors"].append("%s: state read failed — not attempting" % sym)
            _skip(sym, "state unknown (read failed)")
            continue
        if st:
            _skip(sym, "attempted today (same band)")
            continue
        if sym in entered_syms:
            # Bought today under another band. The broker's same-day
            # client_order_id would reject a second entry anyway — skip
            # instead of burning a blocked attempt + race row on it.
            _skip(sym, "already entered today (other band)")
            continue
        seen.add(sym)

        # The owner stop request + the two pre-order sanity gates.
        stop_price, stop_pct = stop_request(c["last"], c["band"]["lo"])
        attempt = {"side": c["side"], "kind": c["kind"], "tier": c["tier"],
                   "band": c["band"], "last": c["last"],
                   "stop_price": stop_price, "stop_pct": stop_pct,
                   "dist_pct": c.get("dist_pct"),
                   "first_seen": c.get("first_seen"),
                   "new_highs": c.get("new_highs"),
                   "overhead_bands": c.get("overhead_bands"), "cap": c.get("cap")}
        reason = None
        if stop_pct is None or stop_pct <= 0:
            reason = "stop not below price (stop %s vs last %s)" % (stop_price, c["last"])
        elif stop_pct > risk_rules.ABS_MAX_STOP_PCT:
            reason = ("stop wider than book max (%.2f%% > %g%%)"
                      % (stop_pct, risk_rules.ABS_MAX_STOP_PCT))
        elif _needs_room_check(c):
            ok_room, room = room_ok(c["last"], stop_pct, _zone_doc(sym, day))
            attempt["room"] = room
            if not ok_room:
                reason = room["reason"]
        else:
            attempt["room"] = {"reason": "skipped: breakout to new highs, no supply overhead"}

        # Record the attempt BEFORE the order path — blocked or not, this
        # band is done for the day (no per-minute retry of a rejected name).
        # A failed write means NO order (fail closed): without a durable
        # record a crash mid-enter would be retried every minute.
        if not _set_state(key, symbol=sym, date=day, band=c["band"],
                          side=c["side"], kind=c["kind"], tier=c["tier"],
                          attempted=True, entered=False, stop_pct=stop_pct,
                          result="blocked" if reason else "pending", reason=reason,
                          first_seen=c.get("first_seen"), last=c["last"]):
            out["ok"] = False
            out["errors"].append("%s: state write failed — not attempting" % sym)
            _skip(sym, "state write failed (not attempted)")
            continue
        if reason:
            out["blocked"].append(sym)
            ledger("zone_entry_blocked", symbol=sym,
                   detail=dict(attempt, reason=reason), dry_run=True, cite=CITE)
            _write_race(c, day, "blocked", reason, as_of, stop_pct=stop_pct)
            continue

        # Buy through the ONLY buy path (entries.enter applies armed /
        # sizing / equity cap / MAX_POSITIONS / never-average-down /
        # earnings / the 10% clamp again). NO earnings override. The try
        # wraps ONLY the order call: once enter() has returned, an order
        # exists and nothing below may relabel it as blocked / error.
        veto = None
        res = None
        try:
            # stop_price = the ABSOLUTE owner level; entries converts it at
            # its own planning price and refuses if the drift since the
            # signal made it too wide or put the print through it. stop_pct
            # rides along as the signal-time request the ledgers record.
            res = entries.enter(sym, limit_price=None, stop_pct=stop_pct,
                                stop_price=stop_price, allow_earnings=False)
        except ValueError as exc:
            veto = str(exc)
        except Exception as exc:                   # noqa: BLE001
            # Unexpected (non-veto) failure — state already says attempted,
            # so this fires AT MOST once per band per day, and it must be
            # VISIBLE: a broker order may or may not exist.
            out["errors"].append("%s: %s" % (sym, exc))
            _set_state(key, result="error", reason=str(exc))
            ledger("zone_entry_error", symbol=sym,
                   detail=dict(attempt, error=str(exc),
                               hint="unexpected failure after trigger — "
                                    "verify at the broker whether an order exists"),
                   dry_run=False, cite=CITE)
            _write_race(c, day, "error", str(exc), as_of, stop_pct=stop_pct)
            continue
        if veto is not None:
            if "market closed" in veto.lower():
                # Not an attempt: the clock flipped under us — retry when open.
                _clear_state(key)
                _skip(sym, "market closed")
                continue
            out["blocked"].append(sym)
            _set_state(key, result="blocked", reason=veto)
            ledger("zone_entry_blocked", symbol=sym,
                   detail=dict(attempt, reason=veto), dry_run=True, cite=CITE)
            _write_race(c, day, "blocked", veto, as_of, stop_pct=stop_pct)
            continue

        # ORDER PLACED. Bookkeeping only from here; every step below swallows
        # its own failure so a placed order is always recorded as 'ordered'.
        order_ts = _utc_iso()
        entries_today += 1
        pos_count += 1
        entered_syms.add(sym)
        out["entered"].append(sym)
        order_id = _res_get(res, "order_id")
        coid = _client_order_id(sym, order_id, brk)
        ledger("zone_entry", symbol=sym,
               detail=dict(attempt, order=res if isinstance(res, dict) else str(res),
                           order_id=order_id, client_order_id=coid),
               dry_run=False, cite=CITE)
        _set_state(key, entered=True, result="entered", order_id=order_id,
                   client_order_id=coid, order_ts=order_ts)
        _write_race(c, day, "ordered", None, as_of, stop_pct=stop_pct,
                    engine_order_ts=order_ts, engine_order_id=order_id,
                    engine_client_order_id=coid)
        _notify(sym, c["side"], mode_word,
                _push_body(sym, c, res, stop_price, stop_pct))

    out["entries_today"] = entries_today
    return _finish()


# ── Status block (rides in GET /trading/status) ─────────────────────────────

def rules_list() -> list:
    """Every rule this module enforces, as data — the FE ⓘ panel renders
    THIS list so the page can never drift from the code. `source` is the
    honesty note: owner rule (no book) or the shared risk contract."""
    return [
        {"rule": "Demand arrivals only — a fresh touch of a demand band "
                 "(tier near/in, arrival flag set); residents that have "
                 "sat in the band are never bought",
         "value": "arrival = true", "source": "owner rule (S&D, no book)"},
        {"rule": "Breakouts only when THROUGH the supply band and heading "
                 "to new highs; a 'near' resistance row is never bought",
         "value": "tier = broke AND new_highs",
         "source": "owner rule (S&D, no book)"},
        {"rule": "Band must be proven structure and the name must be a "
                 "known big cap",
         "value": "touches >= %d, cap >= $%gB" % (MIN_TOUCHES, MIN_CAP_USD / 1e9),
         "source": "owner rule (S&D, no book)"},
        {"rule": "Requested stop sits under the band floor and is placed at "
                 "that LEVEL (not a percent of the order-time print); wider "
                 "than the engine's absolute maximum — at the signal or after "
                 "the print drifted — is refused, never clamped",
         "value": "band.lo x (1 - %g%%), refused past %g%%"
                  % (STOP_BUFFER_PCT, risk_rules.ABS_MAX_STOP_PCT),
         "source": "owner buffer; cap = trading/risk_rules.py risk contract"},
        {"rule": "Room sanity — the first band overhead (a supply band at/above "
                 "the print, or a demand band above it = broken support) must "
                 "leave at least %gx the stop the engine will place (min %g%%); "
                 "a print inside a supply band has no room; breakouts to new "
                 "highs with no supply overhead skip this"
                 % (risk_rules.MIN_REWARD_RISK, RISK_STOP_FLOOR_PCT),
         "value": "room >= %gR" % risk_rules.MIN_REWARD_RISK,
         "source": "owner rule using the engine's reward:risk floor"},
        {"rule": "Signal must be fresh — a board doc older than this (or "
                 "from another day) places nothing",
         "value": "<= %ds old" % SIGNAL_MAX_AGE_SEC,
         "source": "owner rule (S&D, no book)"},
        {"rule": "At most %d zone-edge buys a day, none at/after %s ET, "
                 "one attempt per band per day, never a name already held"
                 % (MAX_ZONE_ENTRIES_PER_DAY, LAST_ENTRY_ET.strftime("%H:%M")),
         "value": "%d/day, last tick %s" % (MAX_ZONE_ENTRIES_PER_DAY,
                                           LAST_ENTRY_ET.strftime("%H:%M")),
         "source": "owner rule (S&D, no book)"},
        {"rule": "Every buy flows through the same sized-and-stopped path as "
                 "manual and Minervini auto-entries: armed switch, %d-position "
                 "cap, 25%% sizing, streak multiplier, never average down, "
                 "earnings shield, target >= 2:1" % risk_rules.MAX_POSITIONS,
         "value": "entries.enter -> risk_rules (FROZEN)",
         "source": "trading/risk_rules.py (engine-wide risk contract)"},
    ]


def status_block(cfg: Optional[dict] = None) -> dict:
    cfg = cfg or get_config()
    day = _et_day()
    sig = signal_state(_latest_doc(), _now_et(), day)
    return {"enabled": bool(cfg.get("zone_edge_entry")),
            "entries_today": _entries_today(day),
            "max_per_day": MAX_ZONE_ENTRIES_PER_DAY,
            "last_entry_et": LAST_ENTRY_ET.strftime("%H:%M"),
            "signal": sig,
            "rules": rules_list(),
            "active_rules": active_rules(cfg),
            "attempts": _today_attempts(day)}
