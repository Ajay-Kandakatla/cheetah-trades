"""Promo-circuit LIVE — real-time % on every tagged name + movers alerts.

Ajay 2026-09-02: "Give me a real time page.. with percentage and alerting
system ... just give me alerts from the topstock alerts only.. I need the
pre market alerts as well. After hours alerts."

Reads the promo board already in Mongo (never rebuilds it), prices every
SEEDING/RAN/DUMPED ticker off one Massive bulk snapshot (extended-hours
last trade), and pushes a ``promo_alert`` when a roster-tagged name moves
>= PROMO_MOVE_PCT vs the prior close — once per symbol per direction per
day, pre-market / regular / after-hours, off the 5-minute cron.
Reminder printed on every alert: the tag IS the promotion.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("catalysts.promo_live")

PROMO_MOVE_PCT = 8.0
# Ajay 2026-09-02: "just give me alerts from the topstock alerts only". Alerts
# fire ONLY on names carrying a tag from these handles; the live table still
# prices the whole board. User-editable; empty set = every roster handle.
PROMO_ALERT_HANDLES: frozenset = frozenset({"topstockalerts"})
LIVE_REFRESH_SEC = 30
_TTL = 20.0
_cache: dict = {"at": 0.0, "payload": None}
_lock = threading.Lock()


def _to_ms(ts: float) -> float:
    """Massive stamps trades in NANOSECONDS (19 digits) despite the field
    name; the snapshot's day bars use ms. Normalise by magnitude."""
    ts = float(ts)
    if ts > 1e15:
        return ts / 1e6
    if ts > 1e11:
        return ts
    return ts * 1000.0


def session_from_ts(ts_ms: Optional[float], now=None) -> str:
    """premarket | rth | afterhours | closed from a last-trade epoch-ms.
    A print older than 6h is not a live session (weekend/holiday tape)."""
    if not ts_ms:
        return "closed"
    try:
        import pandas as pd
        from daytrading.data import _classify_session
        ts = pd.Timestamp(int(_to_ms(ts_ms)), unit="ms", tz="UTC")
        ref = now if now is not None else pd.Timestamp.now(tz="UTC")
        if (ref - ts).total_seconds() > 6 * 3600:
            return "closed"          # a stale print is not a live session
        return _classify_session(ts)
    except Exception as exc:                                # pragma: no cover
        log.debug("promo_live: session classify failed: %s", exc)
        return "closed"


def _trading_day_et(now: Optional[datetime] = None) -> str:
    """Dedupe day in ET — a 19:02 ET after-hours mover in winter is already
    tomorrow in UTC (double alert tonight, suppressed alert tomorrow)."""
    now = now or datetime.now(timezone.utc)
    return now.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def is_alertable(handles: list) -> bool:
    return (not PROMO_ALERT_HANDLES) or any(h in PROMO_ALERT_HANDLES for h in handles)


def alert_gate(day_pct: Optional[float], threshold: float = PROMO_MOVE_PCT) -> Optional[str]:
    """Pure: 'up' | 'down' | None."""
    if day_pct is None:
        return None
    if day_pct >= threshold:
        return "up"
    if day_pct <= -threshold:
        return "down"
    return None


# ── Room to run (Ajay 2026-09-02: "Add room to run") ─────────────────────────
# Same read the Portfolio 🎯 table gives a holding: the first band price meets
# going UP (a supply band at/above the print, or a demand band it already
# broke through) and the % to its bottom. Zones come off DAILY bars, so they
# are cached for half an hour, shared through Mongo between the API process
# and the cron warm, and a live call never computes on its own clock — misses
# go to one background worker and fill in on the next poll.
ZONE_TTL_SEC = 30 * 60
ROOM_NEAR_PCT = 2.0
_zone_mem: dict = {}


def _supply_watch():
    """portfolio.supply_watch, loaded by file when the package init cannot
    import (the py3.9 annotation quirk the tests hit)."""
    try:
        from portfolio import supply_watch
        return supply_watch
    except Exception:
        import importlib.util
        import pathlib
        path = pathlib.Path(__file__).resolve().parent.parent / "portfolio" / "supply_watch.py"
        spec = importlib.util.spec_from_file_location("_promo_supply_watch", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def room_read(supply: list, demand: list, last: Optional[float]) -> dict:
    """Pure decision: where is the first overhead band and how far is it.

    UNPRICED  no print yet.
    CLEAR     nothing overhead in the engine's 1y read (room unknown, not infinite).
    IN_BAND   the print is inside the band — room 0, the sell zone is here.
    NEAR      ≤ ROOM_NEAR_PCT under the band bottom.
    ROOM      further than that; room_pct = % from the print to the band bottom."""
    if not last or float(last) <= 0:
        return {"state": "UNPRICED", "room_pct": None, "band": None}
    sw = _supply_watch()
    live = float(last)
    band = sw.nearest_supply(sw.overhead_bands(supply or [], demand or [], live), live)
    if band is None:
        return {"state": "CLEAR", "room_pct": None, "band": None}
    b = {"lo": round(float(band["lo"]), 4), "hi": round(float(band["hi"]), 4),
         "kind": band.get("kind") or "supply"}
    if float(band["lo"]) <= live:
        return {"state": "IN_BAND", "room_pct": 0.0, "band": b}
    room = round((float(band["lo"]) / live - 1) * 100, 1)
    return {"state": "NEAR" if room <= ROOM_NEAR_PCT else "ROOM", "room_pct": room, "band": b}


def _zone_coll():
    from catalysts.promo_circuit import _coll
    return _coll("promo_zone_cache")


def _slim(zones: list) -> list:
    return [{"lo": float(z["lo"]), "hi": float(z["hi"])}
            for z in (zones or []) if z.get("lo") and z.get("hi")]


def _zones_load(syms: list) -> dict:
    """Fresh (< TTL) zones for `syms` from memory, then the shared Mongo cache."""
    now = time.time()
    have = {s: z for s in syms
            if (z := _zone_mem.get(s)) and now - float(z.get("at") or 0) < ZONE_TTL_SEC}
    missing = [s for s in syms if s not in have]
    if missing:
        coll = _zone_coll()
        if coll is not None:
            try:
                for d in coll.find({"_id": {"$in": missing}}):
                    if now - float(d.get("at") or 0) < ZONE_TTL_SEC:
                        have[d["_id"]] = {"at": d["at"], "supply": d.get("supply") or [],
                                          "demand": d.get("demand") or [], "err": d.get("err")}
            except Exception as exc:
                log.warning("promo_live: zone cache read failed: %s", exc)
    _zone_mem.update(have)
    return have


def _zones_compute(sym: str) -> dict:
    """Daily-bar zones for one name — the Chart Maps engine with EVERY swing
    cluster (max_zones=None; the first band overhead is routinely not among
    the 4 strongest). Anchored on the last daily close, never a live print.
    Lands in both caches; `err` is a string when the engine missed so the row
    says 'unavailable', never a false CLEAR."""
    supply, demand, err = [], [], None
    try:
        from supply_demand import price_zones as pz
        out = pz.for_symbol(sym, max_zones=None)
        if out.get("error"):
            err = str(out["error"])
        else:
            supply, demand = out.get("supply_zones") or [], out.get("demand_zones") or []
    except Exception as exc:
        err = str(exc)
    z = {"at": time.time(), "supply": _slim(supply), "demand": _slim(demand), "err": err}
    _zone_mem[sym] = z
    coll = _zone_coll()
    if coll is not None:
        try:
            coll.replace_one({"_id": sym}, {"_id": sym, **z}, upsert=True)
        except Exception as exc:
            log.warning("promo_live: zone cache write for %s failed: %s", sym, exc)
    return z


# One background worker at a time fills cache misses so a live poll never
# waits on the engine (a cold API container answered in 22 s when it computed
# inline; a row simply reads PENDING until the next 30 s tick).
_bg_lock = threading.Lock()
_bg = {"running": False}


def _bg_compute(syms: list) -> None:
    try:
        for s in syms:
            z = _zone_mem.get(s)
            if z and time.time() - float(z.get("at") or 0) < ZONE_TTL_SEC:
                continue
            _zones_compute(s)
    except Exception as exc:                                # pragma: no cover
        log.warning("promo_live: background zones failed: %s", exc)
    finally:
        with _bg_lock:
            _bg["running"] = False


def zones_for(syms: list, background: bool = True) -> dict:
    """Cached zones for `syms` (memory, then the shared Mongo cache). Misses
    are never computed on the caller's clock: one daemon worker fills them and
    a later call finds them. `background=False` just reads."""
    have = _zones_load(syms)
    missing = [s for s in syms if s not in have]
    if missing and background:
        with _bg_lock:
            kick = not _bg["running"]
            if kick:
                _bg["running"] = True
        if kick:        # started outside the lock — the worker takes it to release itself
            threading.Thread(target=_bg_compute, args=(missing,), daemon=True,
                             name="promo-zones").start()
    return have


def warm_zones(force: bool = False) -> dict:
    """Cron (after the alert pass): refresh every actionable board name whose
    zones are stale, so the live table never waits on the engine."""
    syms = [r["ticker"] for r in _board_rows()]
    have = {} if force else _zones_load(syms)
    warmed = 0
    for s in syms:
        if s in have:
            continue
        _zones_compute(s)
        warmed += 1
    return {"ok": True, "warmed": warmed, "total": len(syms)}


def _room_for(zone: Optional[dict], last: Optional[float]) -> dict:
    if zone is None:
        return {"state": "PENDING", "room_pct": None, "band": None}
    if zone.get("err"):
        return {"state": "UNAVAILABLE", "room_pct": None, "band": None, "error": str(zone["err"])}
    return room_read(zone.get("supply") or [], zone.get("demand") or [], last)


def _board_rows() -> list[dict]:
    from catalysts.promo_circuit import _coll
    cache = _coll("promo_circuit_cache")
    if cache is None:
        return []
    try:
        doc = cache.find_one({"_id": "latest"}) or {}
        rows = (doc.get("payload") or {}).get("rows") or []
        return [r for r in rows if r.get("status") in ("SEEDING", "RAN", "DUMPED")]
    except Exception as exc:
        log.warning("promo_live: board read failed: %s", exc)
        return []


def live_rows(force: bool = False) -> dict:
    with _lock:
        if not force and _cache["payload"] and time.time() - _cache["at"] < _TTL:
            return _cache["payload"]
    rows = _board_rows()
    syms = [r["ticker"] for r in rows]
    quotes: dict = {}
    if syms:
        try:
            from sepa import prices
            quotes = prices.bulk_live_prices(syms) or {}
        except Exception as exc:
            log.warning("promo_live: bulk prices failed: %s", exc)
    try:
        from supply_demand import timeframes as tf_mod
        st = tf_mod.live_state()
    except Exception:                                       # pragma: no cover
        st = {"state": "closed", "refresh_sec": 0, "as_of": None}
    try:
        zones = zones_for(syms) if syms else {}
    except Exception as exc:                                # pragma: no cover
        log.warning("promo_live: zones failed: %s", exc)
        zones = {}
    out = []
    for r in rows:
        q = quotes.get(r["ticker"]) or {}
        last = q.get("last_trade_price") or q.get("price")
        prev = q.get("prev_day_close")
        rth_close = q.get("price") or None      # Massive day.c: today's regular close, 0 pre-open
        day_pct = (round((float(last) / float(prev) - 1) * 100, 2)
                   if last and prev else None)
        # After the bell the move that matters is vs TODAY's close, not
        # yesterday's — an AH dump after an RTH run still reads +% on day_pct.
        ah_pct = (round((float(last) / float(rth_close) - 1) * 100, 2)
                  if (st["state"] == "afterhours" and last and rth_close) else None)
        handles = [a["handle"] for a in (r.get("accounts") or [])]
        base = r.get("base_close")
        out.append({
            "ticker": r["ticker"], "status": r["status"], "best_tier": r.get("best_tier"),
            "accounts": handles[:3], "alertable": is_alertable(handles),
            "days_since_last_tag": r.get("days_since_last_tag"),
            "last": float(last) if last else None, "prev_close": float(prev) if prev else None,
            "rth_close": float(rth_close) if rth_close else None,
            "day_pct": day_pct, "ah_pct": ah_pct,
            "session": session_from_ts(q.get("last_trade_ts_ms")),
            "pct_since_tag": r.get("pct_since_tag"),
            # LIVE since-tag: the last print vs the same base the board uses
            "pct_since_tag_live": (round((float(last) / float(base) - 1) * 100, 1)
                                   if (last and base) else None),
            "first_tagged_at": r.get("first_tagged_at"),
            "last_tagged_at": r.get("last_tagged_at"),
            "edgar": r.get("edgar"),
            # Room to run: first overhead band + % to it (daily-bar zones)
            "room": _room_for(zones.get(r["ticker"]), float(last) if last else None),
        })
    out.sort(key=lambda r: (r["day_pct"] is None, -(r["day_pct"] or 0)))
    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(), "rows": out, "n": len(out),
        "live": {"state": st["state"], "refresh_sec": LIVE_REFRESH_SEC if st["refresh_sec"] else 0,
                 "as_of": st.get("as_of")},
        "alert_threshold_pct": PROMO_MOVE_PCT,
        "alert_handles": sorted(PROMO_ALERT_HANDLES),
        "room_note": ("Room = % from the live print to the bottom of the first band overhead "
                      "(supply at/above it, or support it already broke); daily-bar zones, "
                      "every cluster, refreshed every 30 min. CLEAR = nothing found in 1y, "
                      "not unlimited."),
        "method_note": ("Live prints from the Massive snapshot incl. pre/post market; "
                        "% is vs the prior regular close (after the bell, also vs "
                        "today's close). Alerts: |move| ≥ "
                        f"{PROMO_MOVE_PCT:.0f}% on a name tagged by "
                        + (", ".join("@" + h for h in sorted(PROMO_ALERT_HANDLES)) or "any roster account")
                        + ", once per direction per trading day. The tag is the "
                        "promotion — this is a do-not-chase radar."),
    }
    with _lock:
        _cache.update(at=time.time(), payload=payload)
    return payload


def check_alerts(owner: Optional[str] = None) -> dict:
    from portfolio.alerts import _resolve_owner
    from push import sender
    from catalysts.promo_circuit import _coll
    owner = (owner or _resolve_owner()).lower()
    payload = live_rows(force=True)
    if payload["live"]["state"] == "closed":
        return {"ok": True, "skipped": "tape closed", "pushed": 0}
    coll = _coll("promo_alerts")
    day = _trading_day_et()
    state = payload["live"]["state"]
    tag = {"premarket": "PRE", "afterhours": "AH", "rth": "RTH"}.get(state, "")
    pushed, fired = 0, []
    for r in payload["rows"]:
        if not r.get("alertable") or r.get("session") == "closed":
            continue
        # After the bell: the AH move vs today's close is the signal; before
        # and during: the move vs the prior close.
        if state == "afterhours":
            d = alert_gate(r.get("ah_pct"))
            if not d:
                continue
            key = f"{r['ticker']}:{day}:ah:{d}"
            move = f"{r['ah_pct']:+.1f}% vs close (day {r['day_pct']:+.1f}%)" if r.get("day_pct") is not None else f"{r['ah_pct']:+.1f}% vs close"
            base_px = r.get("rth_close")
        else:
            d = alert_gate(r.get("day_pct"))
            if not d:
                continue
            key = f"{r['ticker']}:{day}:{d}"
            move = f"{r['day_pct']:+.1f}%"
            base_px = r.get("prev_close")
        if coll is not None:
            try:
                if coll.find_one({"_id": key}):
                    continue
            except Exception as exc:                        # pragma: no cover
                log.warning("promo alert dedupe read failed: %s", exc)
        who = ", ".join("@" + h for h in r["accounts"][:2]) or "the circuit"
        age = r.get("days_since_last_tag")
        msg = {
            "title": f"🎪 {tag} {r['ticker']} {move} — tagged by {who}"
                     + (f" {age:.0f}d ago" if age is not None else ""),
            "body": (f"${r['last']:.2f} vs ${base_px:.2f} · {r['status']} · "
                     "the tag IS the promotion — do not chase"),
            "icon": "/icon.svg",
            "tag": f"promo-{r['ticker'].lower()}",
            "url": "/catalysts?tab=promo", "kind": "promo_alert", "ticker": r["ticker"],
            "data": {"url": "/catalysts?tab=promo", "symbol": r["ticker"], "source": "promo_live"},
        }
        res = sender.send_to_user(owner, msg, kind="promo_alert") or {}
        sent, targets = res.get("sent", 0), res.get("total_targets", 0)
        if sent > 0:
            pushed += 1
        # Terminal outcomes dedupe (delivered, or nobody targeted: muted pref /
        # quiet hours / no device) — else every 5-min run re-logs a feed row.
        if (sent > 0 or targets == 0) and coll is not None:
            try:
                coll.update_one({"_id": key}, {"$set": {
                    "at": datetime.now(timezone.utc), "symbol": r["ticker"],
                    "move": move, "session": state, "sent": sent, "targets": targets}}, upsert=True)
            except Exception as exc:                    # pragma: no cover
                log.warning("promo alert dedupe write failed: %s", exc)
        fired.append({"symbol": r["ticker"], "move": move,
                      "session": state, "sent": sent})
    out = {"ok": True, "pushed": pushed, "fired": fired, "session": payload["live"]["state"]}
    log.info("promo_live: %s", out)
    return out


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    res = check_alerts()
    try:
        res["zones"] = warm_zones()
    except Exception as exc:                                # pragma: no cover
        res["zones"] = {"ok": False, "error": str(exc)}
    print(json.dumps(res, indent=2, default=str))
