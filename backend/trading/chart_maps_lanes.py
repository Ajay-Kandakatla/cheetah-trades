"""Chart Maps lanes — the generic paper lane and the tick dispatcher.

Ajay 2026-09-27: "stop minerviews use all strategies from Most used from Chart
maps. All of them and journal the," — "Small: 0.25% risk, 15 open max",
"Top 10 most-used first".

ONE generic lane engine with a small adapter per tab, not fifteen modules.
The snapshot job (chart_maps/lane_snapshot.py, api process, every 5 min in
RTH) calls each ON tab's OWN builder and stores its slim long candidates in
`cm_lane_snapshot`. The tick never builds a board: it reads that doc,
re-confirms ONE candidate on the live print through
`bounce_room.api_payload([sym], background=False)` — the same 🎯 READY read
(`supply_demand/enterable.py`, which carries the standing alert gate: at
least ALERT_MIN_ROOM_PCT room to the first proven supply and within
ALERT_MAX_ABOVE_DEMAND_PCT of demand) — and buys through `entries.enter`,
the only buy path, which applies every program cap (trading/program_caps.py).

ENTRY RULE for every generic adapter
  the tab's own list  +  🎯 READY on the live print  +  a stop that is either
  the tab's served STOP (PLAN adapters: deep_demand, ict, session) or the
  READY read's demand band floor x (1 - STOP_BUFFER_PCT/100) (LIST adapters).
  No band and no served stop = no trade. No stop is ever invented.
  A LIST lane therefore buys a READY demand REVERSAL on a name from the tab's
  list — not the tab's own setup (critic 10). The target is the frozen
  risk_rules.profit_target like every lane; the tab's served target is only
  journaled.

THE DISPATCHER (`run_program`, tick steps h/j/k/l/m)
  Program OFF -> exit_engine._run_lanes_fixed_order(): the pre-program lane
  code, verbatim. Program ON -> every lane in USAGE order (most-opened tab
  first, program_caps.priority_order), existing lanes run every tick
  whatever their strategy switch says (their exits live there), options last.
  Once this minute's entry is claimed no further generic slot runs; the
  existing lanes still run for their exits and stop at their cheap-skip.

UNMEASURED forward paper measurement. Paper/sim only. Never "bounce" on a
surface he reads — it is a reversal.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from supply_demand import enterable
from trading import program_caps as PC
from trading import strategy_tags as ST
from trading import zone_edge_entry

log = logging.getLogger("trading.chart_maps_lanes")

ET = ZoneInfo("America/New_York")

ADAPTER_VERSION = "cm-lanes-v1"
SNAPSHOT_COLL = "cm_lane_snapshot"
STATE_COLL = "cm_lane_state"
ENTRY_SNAPSHOT_COLL = "cm_lane_entries"
SNAPSHOT_MAX_AGE_SEC = 600
STOP_BUFFER_PCT = zone_edge_entry.STOP_BUFFER_PCT
LAST_ENTRY_ET = zone_edge_entry.LAST_ENTRY_ET
BAND_MATCH_TOL = enterable.BAND_MATCH_TOL
MAX_CONFIRMS_PER_SID = 3
SESSION_CLOSE_ET = dtime(16, 0)
PLAN_ADAPTERS = ("deep_demand", "ict", "session")
MINUTE_GONE_TEXT = PC.TRANSIENT_PREFIX + "minute taken"
NO_STOP_TEXT = "no stop served and no demand band"

# Existing-lane slot -> the legacy tick summary key (kept byte-for-byte).
_SLOT_KEYS = {"zone_edge_demand": "zone_edge_entry", "zone_edge_supply": "zone_edge_entry_supply",
              "catalyst_entry": "catalyst_entry", "hot_pullback_entry": "hot_pullback",
              "zero_dte_lane": "zero_dte_lane", "options_lane": "options_lane"}
# The lane's OWN flag (trading_config) for each existing-lane sid.
LANE_SWITCH = {"zones": "zone_edge_entry", "quick_bounce": "zone_edge_entry",
               "breaking": "zone_edge_entry", "catalysts": "catalyst_entry",
               "hot_pullback": "hot_pullback_entry", "signals": "zero_dte_entry"}


# ── plumbing ─────────────────────────────────────────────────────────────────
def _EE():
    from trading import exit_engine
    return exit_engine


def _coll(name: str):
    db = _EE()._db()
    if db is None:
        return None
    try:
        return getattr(db, name)
    except Exception:                              # noqa: BLE001
        return None


def _now_et(now: Optional[datetime] = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc).astimezone(ET)
    return now.replace(tzinfo=ET) if now.tzinfo is None else now.astimezone(ET)


def _f(x) -> Optional[float]:
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and not math.isinf(v) else None


def _mode(brk) -> str:
    m = getattr(brk, "mode", None)
    if callable(m):
        try:
            return str(m())
        except Exception:                          # noqa: BLE001
            pass
    return _EE()._broker_mode()


# ── time rules ───────────────────────────────────────────────────────────────
def prev_session_close(now: Optional[datetime] = None) -> datetime:
    """16:00 ET of the most recent session day (weekday that passes the one
    closed-day engine, market_hours.gate.closed_reason). Today counts once it
    is past 16:00 ET."""
    from market_hours import gate
    n = _now_et(now)
    d = n.date()
    if n.time() < SESSION_CLOSE_ET:
        d -= timedelta(days=1)
    for _ in range(15):
        noon = datetime.combine(d, dtime(12, 0), tzinfo=ET)
        if gate.closed_reason(noon) is None:
            return datetime.combine(d, SESSION_CLOSE_ET, tzinfo=ET)
        d -= timedelta(days=1)
    return datetime.combine(d, SESSION_CLOSE_ET, tzinfo=ET)


def _epoch_of(v) -> Optional[float]:
    """An epoch from a stored stamp (epoch number or ISO string; a naive ISO
    is UTC, the Mongo convention)."""
    f = _f(v)
    if f is not None:
        return f / 1000.0 if f > 1e12 else f
    if not isinstance(v, str) or not v:
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def snapshot_stale(doc: Optional[dict], now: Optional[datetime] = None) -> Optional[str]:
    """Why this snapshot may not be traded (first match wins), else None.

    The READY read must be at most SNAPSHOT_MAX_AGE_SEC old (the write time),
    and the board it was cut from must have been BUILT at or after the
    previous session's close (the board's own stamp). A daily list therefore
    trades on the last close's list; an unknown build time fails closed."""
    n = _now_et(now)
    if not isinstance(doc, dict):
        return "no snapshot"
    if str(doc.get("day") or "") != n.date().isoformat():
        return "stale snapshot (built another day)"
    written = _epoch_of(doc.get("as_of"))
    if written is None:
        return "stale snapshot (write time unknown)"
    age = n.timestamp() - written
    if age > SNAPSHOT_MAX_AGE_SEC:
        return "stale snapshot (%ds old)" % int(age)
    src = _epoch_of(doc.get("source_as_of"))
    if src is None:
        return "stale board (build time unknown)"
    close = prev_session_close(n)
    if src < close.timestamp():
        built = datetime.fromtimestamp(src, tz=ET).strftime("%Y-%m-%d %H:%M ET")
        return "stale board (built %s, before the last close)" % built
    return None


# ── the live confirm + the stop ──────────────────────────────────────────────
def _band(b) -> Optional[dict]:
    if not isinstance(b, dict):
        return None
    lo, hi = _f(b.get("lo")), _f(b.get("hi"))
    if lo is None or hi is None:
        return None
    return {"lo": lo, "hi": hi}


def confirm_live(sid: str, cand: dict) -> dict:
    """The 🎯 READY read on the LIVE print for one candidate.

    ok only when the bounce-room row is covered (store / ondemand), its
    enterable verdict is READY (both standing alert gates + floor held + no
    measured drag), and — for PLAN adapters — the live band agrees with the
    snapshot's band within BAND_MATCH_TOL (the served plan belongs to it)."""
    sym = str((cand or {}).get("symbol") or "").upper()
    out = {"ok": False, "reason": None, "px": None, "band": None, "room": None,
           "gates": None, "verdict": None, "reasons": []}
    try:
        from supply_demand import bounce_room
        payload = bounce_room.api_payload([sym], background=False) or {}
        row = (payload.get("rows") or {}).get(sym) or {}
    except Exception as exc:                       # noqa: BLE001
        out["reason"] = "live read failed: %s" % str(exc)[:120]
        return out
    cov = row.get("coverage")
    if cov not in ("store", "ondemand"):
        out["reason"] = "no live read (coverage %s)" % (cov or "none")
        return out
    en = row.get("enterable") if isinstance(row.get("enterable"), dict) else {}
    out.update(px=_f((en.get("print") or {}).get("px")) or _f(row.get("print")),
               band=_band(en.get("band")), room=en.get("room"), gates=en.get("gates"),
               verdict=en.get("verdict"), reasons=list(en.get("reasons") or []))
    if out["verdict"] != enterable.READY:
        words = list(en.get("reason_short") or []) or out["reasons"]
        out["reason"] = "live read %s: %s" % (str(out["verdict"] or "none").lower(),
                                              "; ".join(str(w) for w in words) or "no reason")
        return out
    if out["px"] is None or out["px"] <= 0:
        out["reason"] = "no live print"
        return out
    if sid in PLAN_ADAPTERS:
        snap_band = _band(((cand or {}).get("enterable") or {}).get("band"))
        live_band = out["band"]
        if snap_band is not None and live_band is not None and (
                abs(snap_band["lo"] - live_band["lo"]) > BAND_MATCH_TOL
                or abs(snap_band["hi"] - live_band["hi"]) > BAND_MATCH_TOL):
            out["reason"] = ("band moved since the snapshot (%.2f-%.2f -> %.2f-%.2f)"
                             % (snap_band["lo"], snap_band["hi"], live_band["lo"], live_band["hi"]))
            return out
    out["ok"] = True
    return out


def stop_for(sid: str, cand: dict, live: dict) -> tuple:
    """(stop, "served"|"band_floor") or (None, None). PLAN adapters use the
    tab's served STOP only when it sits below the live print; LIST adapters
    use the live READY band floor x (1 - STOP_BUFFER_PCT/100). Nothing else."""
    px = _f((live or {}).get("px"))
    if px is None or px <= 0:
        return None, None
    if sid in PLAN_ADAPTERS:
        served = _f(((cand or {}).get("plan") or {}).get("stop"))
        if served is not None and 0 < served < px:
            return served, "served"
        return None, None
    band = _band((live or {}).get("band"))
    if band is None or band["lo"] <= 0:
        return None, None
    stop = round(band["lo"] * (1.0 - STOP_BUFFER_PCT / 100.0), 4)
    return (stop, "band_floor") if stop < px else (None, None)


def _is_long(sid: str, cand: dict) -> Optional[str]:
    """None when the candidate is a long setup, else why not."""
    plan = (cand or {}).get("plan") or {}
    band = ((cand or {}).get("enterable") or {}).get("band")
    if _f(plan.get("stop")) is None and _band(band) is None:
        return "not long (no stop and no band)"
    if sid == "ict":
        served = (cand or {}).get("served") or {}
        if served.get("bias") != "bullish" or served.get("state") != "entry":
            return "not a bullish ICT entry"
    stop, buy = _f(plan.get("stop")), _f(plan.get("buy"))
    if sid in PLAN_ADAPTERS and stop is not None and buy is not None and stop >= buy:
        return "short geometry (stop above the entry)"
    return None


# ── attempt state (one per sid / symbol / ET day) ────────────────────────────
def _state_key(sid: str, sym: str, day: str) -> str:
    return "%s:%s:%s" % (sid, sym, day)


def _state_get(key: str) -> Optional[dict]:
    coll = _coll(STATE_COLL)
    if coll is None:
        return None
    try:
        return coll.find_one({"_id": key}) or {}
    except Exception as exc:                       # noqa: BLE001
        log.warning("cm_lane_state read failed %s: %s", key, exc)
        return None


def _state_set(key: str, **fields) -> bool:
    coll = _coll(STATE_COLL)
    if coll is None:
        return False
    try:
        coll.update_one({"_id": key}, {"$set": fields}, upsert=True)
        return True
    except Exception as exc:                       # noqa: BLE001
        log.warning("cm_lane_state write failed %s: %s", key, exc)
        return False


def _state_clear(key: str) -> None:
    coll = _coll(STATE_COLL)
    if coll is None:
        return
    try:
        coll.delete_one({"_id": key})
    except Exception as exc:                       # noqa: BLE001
        log.warning("cm_lane_state clear failed %s: %s", key, exc)


def _snapshot(sid: str) -> Optional[dict]:
    coll = _coll(SNAPSHOT_COLL)
    if coll is None:
        return None
    try:
        return coll.find_one({"_id": sid})
    except Exception as exc:                       # noqa: BLE001
        log.warning("cm_lane_snapshot read failed %s: %s", sid, exc)
        return None


def _coid(brk, sym: str) -> Optional[str]:
    mk = getattr(brk, "make_client_order_id", None)
    if callable(mk):
        try:
            return str(mk(sym, "entry"))
        except Exception:                          # noqa: BLE001
            return None
    return None


# ── the generic lane ─────────────────────────────────────────────────────────
def run_generic(broker, cfg: Optional[dict], sids, *, now: Optional[datetime] = None) -> dict:
    """At most ONE entry for the first sid (in the order given) that has a
    fresh snapshot and a candidate that re-confirms READY on the live print.
    Never raises."""
    out = {"entered": None, "sids": {}, "errors": []}
    try:
        return _run_generic(broker, cfg or {}, list(sids or []), out, now)
    except Exception as exc:                       # noqa: BLE001
        log.warning("chart_maps_lanes.run_generic failed: %s", exc)
        out["errors"].append("run_generic: %s" % exc)
        return out


def _run_generic(brk, cfg: dict, sids: list, out: dict, now) -> dict:
    from trading import entries
    n = _now_et(now)
    day = n.date().isoformat()
    mode = _mode(brk)
    try:
        market_open = bool(brk.clock().get("is_open"))
    except Exception as exc:                       # noqa: BLE001
        out["errors"].append("clock: %s" % exc)
        market_open = False
    for sid in sids:
        r = out["sids"].setdefault(sid, {"reason": None, "confirmed": 0, "skips": []})
        # 1. the gate: ON, armed, market open, before the last entry time
        if not PC.strategy_on(sid, cfg, mode) or ST.roster_entry(sid) is None:
            r["reason"] = "off"
            continue
        if not cfg.get("armed"):
            r["reason"] = "disarmed"
            continue
        if not market_open:
            r["reason"] = "market closed"
            continue
        if n.time() >= LAST_ENTRY_ET:
            r["reason"] = "after_last_entry_time"
            continue
        # 2. the minute is already gone: nothing else can enter this tick
        why = PC.minute_taken_reason(PC.minute_taken())
        if why:
            r["reason"] = why
            PC.log_skip(sid, "*", why)
            return out
        # 3. the snapshot
        doc = _snapshot(sid)
        stale = snapshot_stale(doc, n)
        if stale:
            r["reason"] = stale
            PC.log_skip(sid, "*", stale)
            continue
        # 4. the per-strategy caps, cheaply, before any live read
        try:
            inf = PC.inflight(brk)
        except Exception as exc:                   # noqa: BLE001
            out["errors"].append("inflight: %s" % exc)
            r["reason"] = "broker unreadable"
            return out
        pre = PC.check(sid, "*", brk=brk, cfg=cfg, mode=mode, inf=inf)
        if pre:
            r["reason"] = pre[0]
            PC.log_skip(sid, "*", pre[0])
            if any("portfolio full" in x or PC.MINUTE_TAKEN_TEXT in x
                   or "entry clock unreadable" in x for x in pre):
                return out
            continue
        busy = inf["positions"] | inf["pending_buys"]
        cands = [c for c in (doc.get("candidates") or []) if isinstance(c, dict)]
        cands.sort(key=lambda c: (_f(c.get("board_rank")) if _f(c.get("board_rank")) is not None
                                  else float("inf")))
        for cand in cands:
            sym = str(cand.get("symbol") or "").upper()
            if not sym or sym in busy:
                continue
            key = _state_key(sid, sym, day)
            st = _state_get(key)
            if st is None:
                out["errors"].append("%s: cm_lane_state unreadable — no attempts" % sid)
                r["reason"] = "state unreadable"
                return out
            if st:
                continue
            if _is_long(sid, cand) is not None:
                continue
            if r["confirmed"] >= MAX_CONFIRMS_PER_SID:
                break
            r["confirmed"] += 1
            live = confirm_live(sid, cand)
            if not live["ok"]:
                r["skips"].append({"symbol": sym, "reason": live["reason"]})
                PC.log_skip(sid, sym, live["reason"])
                continue
            stop, src = stop_for(sid, cand, live)
            if stop is None or stop >= live["px"]:
                r["skips"].append({"symbol": sym, "reason": NO_STOP_TEXT})
                PC.log_skip(sid, sym, NO_STOP_TEXT)
                continue
            snap_ref = _coid(brk, sym) or key
            if not _state_set(key, sid=sid, symbol=sym, day=day, attempted=True,
                              result="pending", at=n.isoformat(timespec="seconds"),
                              stop=stop, stop_src=src):
                out["errors"].append("%s %s: state write failed — not attempting" % (sid, sym))
                r["reason"] = "state write failed"
                return out
            roster = ST.roster_entry(sid) or {}
            reason = {"sid": sid, "tab": roster.get("label_tab") or sid,
                      "adapter": roster.get("adapter"), "adapter_version": ADAPTER_VERSION,
                      "kind": "demand", "band": live["band"], "room": live["room"],
                      "gate": live["gates"], "stop_src": src,
                      "stop_pct": round((live["px"] - stop) / live["px"] * 100.0, 2),
                      "served_target": _f((cand.get("plan") or {}).get("target")),
                      "board_rank": cand.get("board_rank"),
                      "source_as_of": doc.get("source_as_of"), "snapshot_ref": snap_ref}
            try:
                res = entries.enter(sym, limit_price=None, stop_price=stop, strategy=sid,
                                    allow_earnings=False, reason=reason)
            except ValueError as exc:
                veto = str(exc)
                PC.log_skip(sid, sym, veto)
                r["skips"].append({"symbol": sym, "reason": veto})
                if PC.is_transient(veto):
                    _state_clear(key)              # not an attempt: retried next tick
                    r["reason"] = veto
                    return out
                _state_set(key, result="blocked", reason=veto[:300])
                continue
            except Exception as exc:               # noqa: BLE001
                out["errors"].append("%s %s: %s" % (sid, sym, exc))
                _state_set(key, result="error", reason=str(exc)[:300])
                continue
            order_id = (res or {}).get("order_id") if isinstance(res, dict) else None
            _state_set(key, result="entered", order_id=order_id)
            coll = _coll(ENTRY_SNAPSHOT_COLL)
            if coll is not None:
                try:
                    coll.update_one({"_id": snap_ref},
                                    {"$set": {"sid": sid, "tab": reason["tab"],
                                              "adapter": reason["adapter"],
                                              "adapter_version": ADAPTER_VERSION,
                                              "symbol": sym, "day": day, "epoch": n.timestamp(),
                                              "candidate": cand,
                                              "live": {k: live.get(k) for k in
                                                       ("px", "band", "room", "gates",
                                                        "verdict", "reasons")},
                                              "source_as_of": doc.get("source_as_of"),
                                              "order": res if isinstance(res, dict) else str(res)}},
                                    upsert=True)
                except Exception as exc:           # noqa: BLE001
                    log.warning("cm_lane_entries write failed %s: %s", sym, exc)
            out["entered"] = {"sid": sid, "symbol": sym, "order_id": order_id,
                              "stop": stop, "stop_src": src}
            r["reason"] = "entered"
            return out
        if r["reason"] is None:
            r["reason"] = "no candidate confirmed"
    return out


# ── the dispatcher ───────────────────────────────────────────────────────────
def _slots(order: list) -> list:
    slots, seen = [], set()
    for sid in order:
        r = ST.roster_entry(sid)
        if r is None or r["klass"] != ST.LANE:
            continue
        lane = r["lane"]
        if lane == "generic":
            slots.append(("generic", sid))
        elif lane in _SLOT_KEYS and lane not in seen:
            seen.add(lane)
            slots.append((lane, sid))
    for lane in ("zone_edge_demand", "zone_edge_supply", "catalyst_entry",
                 "hot_pullback_entry", "zero_dte_lane"):
        if lane not in seen:                       # never drop an existing lane's exits
            slots.append((lane, None))
    slots.append(("options_lane", None))
    return slots


def _run_existing(lane: str, brk, cfg: dict):
    if lane == "zone_edge_demand":
        return zone_edge_entry.run(broker=brk, cfg=cfg, sides=("demand",), reconcile=False)
    if lane == "zone_edge_supply":
        return zone_edge_entry.run(broker=brk, cfg=cfg, sides=("supply",), reconcile=True)
    if lane == "catalyst_entry":
        from trading import catalyst_entry
        return catalyst_entry.run(broker=brk, cfg=cfg)
    if lane == "hot_pullback_entry":
        from trading import hot_pullback_entry
        return hot_pullback_entry.run(broker=brk, cfg=cfg)
    if lane == "zero_dte_lane":
        from trading import zero_dte_lane
        return zero_dte_lane.run(broker=brk, cfg=cfg)
    if lane == "options_lane":
        from trading import options_lane
        return options_lane.run(broker=brk, cfg=cfg)
    raise ValueError("unknown lane %r" % lane)


def run_program(broker=None, cfg: Optional[dict] = None) -> dict:
    """Tick steps (h)(j)(k)(l)(m). Never raises."""
    try:
        EE = _EE()
        brk = broker if broker is not None else EE.broker
        cfg = cfg or EE.get_config()
        mode = _mode(brk)
        if not PC.enabled(cfg, mode):
            return EE._run_lanes_fixed_order()
        return _run_program_on(brk, cfg, mode)
    except Exception as exc:                       # noqa: BLE001
        log.warning("chart_maps_lanes.run_program failed: %s", exc)
        return {"errors": ["chart_maps_lanes: %s" % exc]}


def _run_program_on(brk, cfg: dict, mode: str) -> dict:
    out = {"errors": [], "chart_maps_lanes": {}}
    try:
        order = list(PC.priority_order().get("order") or [])
    except Exception as exc:                       # noqa: BLE001
        out["errors"].append("priority_order: %s" % exc)
        order = list(ST.usage_rank(*ST.frozen_counts()))
    minute_gone = False
    for lane, sid in _slots(order):
        if lane == "generic":
            if minute_gone:
                if PC.strategy_on(sid, cfg, mode):
                    PC.log_skip(sid, "*", MINUTE_GONE_TEXT)
                out["chart_maps_lanes"][sid] = {"reason": MINUTE_GONE_TEXT}
                continue
            try:
                res = run_generic(brk, cfg, [sid])
                out["errors"].extend(res.pop("errors", None) or [])
                out["chart_maps_lanes"][sid] = dict(res.get("sids", {}).get(sid) or {},
                                                    entered=res.get("entered"))
            except Exception as exc:               # noqa: BLE001
                out["errors"].append("%s: %s" % (sid, exc))
        else:
            key = _SLOT_KEYS[lane]
            try:
                out[key] = _run_existing(lane, brk, cfg)
            except Exception as exc:               # noqa: BLE001
                log.warning("%s run failed: %s", lane, exc)
                out["errors"].append("%s: %s" % (key, exc))
        if not minute_gone:
            try:
                t = PC.minute_taken()
            except Exception:                      # noqa: BLE001
                t = {"error": "peek failed"}
            minute_gone = bool(t)
    prog = {"order": order, "open": None, "minute": None}
    try:
        prog["minute"] = PC.minute_taken()
    except Exception:                              # noqa: BLE001
        pass
    try:
        inf = PC.inflight(brk)
        prog["open"] = {"n": len(inf["positions"] | inf["pending_buys"]),
                        "positions": len(inf["positions"]),
                        "pending": len(inf["pending_buys"] - inf["positions"])}
    except Exception as exc:                       # noqa: BLE001
        prog["open"] = {"error": str(exc)[:200]}
    out["program"] = prog
    return out


# ── GET /trading/strategies ──────────────────────────────────────────────────
def _log_today(day: str) -> dict:
    """{sid: {"skips": {reason: n}, "last": [{symbol, reason, at}]}} from cm_lane_log."""
    coll = _coll(PC.LOG_COLL)
    out: dict = {}
    if coll is None:
        return out
    try:
        rows = list(coll.find({"day": day}))
    except Exception as exc:                       # noqa: BLE001
        log.debug("cm_lane_log read failed: %s", exc)
        return out
    for r in rows:
        if not isinstance(r, dict):
            continue
        b = out.setdefault(r.get("sid"), {"skips": {}, "last": []})
        reason = str(r.get("reason") or "")
        b["skips"][reason] = b["skips"].get(reason, 0) + int(r.get("count") or 0)
        b["last"].append({"symbol": r.get("symbol"), "reason": reason, "at": r.get("last_at")})
    for b in out.values():
        b["last"].sort(key=lambda x: str(x.get("at") or ""), reverse=True)
        b["last"] = b["last"][:5]
    return out


def _entries_today(day: str) -> dict:
    coll = _coll(PC.PROGRAM_ENTRIES_COLL)
    out: dict = {}
    if coll is None:
        return out
    try:
        rows = list(coll.find({"day": day}))
    except Exception:                              # noqa: BLE001
        return out
    for r in rows:
        if isinstance(r, dict):
            out.setdefault(r.get("sid"), []).append(
                {"symbol": r.get("symbol"), "at": r.get("at"), "order_id": r.get("order_id")})
    return out


def _snapshot_block(sid: str, n: datetime) -> Optional[dict]:
    doc = _snapshot(sid)
    if not isinstance(doc, dict):
        return None
    written = _epoch_of(doc.get("as_of"))
    stale = snapshot_stale(doc, n)
    cands = [c for c in (doc.get("candidates") or []) if isinstance(c, dict)]
    return {"as_of": doc.get("as_of"), "source_as_of": doc.get("source_as_of"),
            "source_key": doc.get("source_key"),
            "age_sec": int(n.timestamp() - written) if written is not None else None,
            "stale": stale is not None, "stale_reason": stale, "n": len(cands),
            "top": [str(c.get("symbol") or "") for c in cands[:5]],
            "error": doc.get("error")}


def strategies_payload(now: Optional[datetime] = None) -> dict:
    """GET /trading/strategies — the Trading page's 🗺️ Chart Maps view."""
    EE = _EE()
    n = _now_et(now)
    day = n.date().isoformat()
    cfg = EE.get_config()
    brk = EE.broker
    mode = _mode(brk)
    prog = PC.status_block(cfg, mode, brk)
    try:
        usage = PC.priority_order(n)
    except Exception as exc:                       # noqa: BLE001
        usage = {"day": day, "order": list(ST.usage_rank(*ST.frozen_counts())),
                 "counts": {}, "source": "frozen", "error": str(exc)[:200]}
    prog["usage_order"] = usage
    board: dict = {}
    try:
        from trading import lane_review
        board = lane_review.scoreboard() or {}
    except Exception as exc:                       # noqa: BLE001
        log.warning("strategies: scoreboard unavailable: %s", exc)
    logs = _log_today(day)
    ents = _entries_today(day)
    counts = usage.get("counts") or {}
    lanes_cfg = cfg.get("cm_lanes") if isinstance(cfg.get("cm_lanes"), dict) else {}
    rank = {sid: i + 1 for i, sid in enumerate(usage.get("order") or [])}
    rows = []
    for sid in (usage.get("order") or []):
        r = ST.roster_entry(sid)
        if r is None or r["klass"] != ST.LANE:
            continue
        lane_key = LANE_SWITCH.get(sid)
        lg = logs.get(sid) or {"skips": {}, "last": []}
        rows.append({
            "sid": sid, "tabs": list(r["tabs"]), "label_tab": r["label_tab"],
            "rank": rank.get(sid), "opens": counts.get(sid),
            "lane": r["lane"], "adapter": r["adapter"],
            "adapter_version": ADAPTER_VERSION if r["lane"] == "generic" else None,
            # enabled = the row's switch (what buys once the program is ON);
            # buying_now = what the engine lets buy right now (program OFF:
            # the existing lanes on their own switches, generic lanes never).
            "default_on": r["default_on"], "enabled": PC.switch_on(sid, cfg),
            "buying_now": PC.strategy_on(sid, cfg, mode),
            "note": r["note"],
            "switch": {"key": "cm_lanes", "value": lanes_cfg.get(sid)},
            "lane_switch": ({"key": lane_key, "value": bool(cfg.get(lane_key))}
                            if lane_key else None),
            "snapshot": _snapshot_block(sid, n) if r["lane"] == "generic" else None,
            "today": {"entries": ents.get(sid) or [], "skips": lg["skips"],
                      "last_skips": lg["last"]},
            "scoreboard": board.get(sid) or _empty_board(),
            "prior": ST.PRIORS.get(sid),
        })
    frozen_counts, _ = ST.frozen_counts()
    not_lanes = [{"tab": sid, "opens": frozen_counts.get(sid), "reason": reason}
                 for sid, reason in ST.NOT_A_LANE.items()]
    return {"program": prog, "strategies": rows, "not_lanes": not_lanes,
            "unmeasured": True,
            "note": ("UNMEASURED forward paper measurement: every strategy's prior is "
                     "null, inverted or unmeasured; judge in R, not dollars.")}


def _empty_board() -> dict:
    try:
        from trading import lane_review
        return lane_review.empty_board()
    except Exception:                              # noqa: BLE001
        return {}
