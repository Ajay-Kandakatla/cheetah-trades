"""Catalyst-lane entries — the engine BUYS a name off the Catalysts board
(paper account, 2026-09-05) when the cached catalyst scan says the move is
REAL and the Supply & Demand bands say the print sits AT a demand level with
room overhead.

Ajay (2026-09-05, verbatim): "What ever rules I created for the alerts are the
ideal conditions for a stock to be bough in Autopilot. Keep the minervini
entries but also make sure you have demand zone and catalyst based entries
time to time and journal it appropriately."

STRATEGY SCOPE — Supply & Demand + the Catalysts board, NOT Minervini. Every
ENTRY rule below is an OWNER RULE (Ajay's playbook,
docs/supply_demand/catalyst_entry.md); there is no book behind them and none
is cited. The RISK math (stop clamp to the engine's absolute line, target >=
the engine's reward:risk floor, sizing, streak multiplier, never average
down, earnings shield, MAX_POSITIONS) is the engine-wide contract every buy
passes through — trading.entries.enter() -> trading/risk_rules.py (FROZEN).
This module only REQUESTS a stop; risk_rules decides.

Signal source — the CACHED catalyst scan only (catalysts.api._cache_get()):
the same payload the Catalysts board shows, built by a user's page visit or
the board's own poll. This module NEVER triggers a scan (a 30-45 s pipeline
with LLM review does not belong in a 60 s engine tick); no cached scan (or an
expired one — 5 min in RTH) = "no cached catalyst scan", nothing bought.

Quality funnel (owner settings; every missing field FAILS CLOSED):
  quadrant        in QUADRANTS_OK  (REAL | OVERLOOKED — evidence-backed
                  moves; PUMP_RISK / DEAD never)          -- owner setting
  review grade    in GRADES_OK     (A | B from the review) -- owner setting
  pump warning    review.is_pump_warning is False          -- owner setting
  offering        evidence.sec_filings.has_offering False  -- owner setting
  price           >= CATALYST_MIN_PRICE                    -- NOT from Ajay
  dollar volume   >= CATALYST_MIN_DOLLAR_VOL               -- NOT from Ajay
The last two are conservative defaults chosen by the builder so the lane
never buys a sub-$2 or illiquid name; Ajay has not set them. No market-cap
floor: the scan is sub-$500M by construction (scanner max_market_cap), so a
cap gate would be a tautology — said plainly rather than invented.

Gate = the phone's alert rules (supply_demand/alert_gates, same quote):
  print      the cached scan's OWN price (+ day_low / day_high / prev_close),
             shaped like a provider snapshot row and read through
             bounce_room.read_symbol (pure) — the tick reads NO tape. Its age
             is the scan's as_of; older than the phone's stale line
             (zone_bounce_alerts.STALE_PRINT_SEC — the constant the 🪃 push
             refuses to act past) = skip. Reused, not a new number.
  room       alert_gates.room_gate(print, bands, prev_close): at least
             ALERT_MIN_ROOM_PCT to the first UNBROKEN band overhead; CLEAR
             passes; IN_BAND / NEAR-under-the-floor fail.
  level      a bounce read (supply_demand.bounce_room: touched a demand band
             or broken-supply shelf and lifted off it) AND the print still
             within alert_gates.demand_proximity_gate of THAT band — a bounce
             that already ran 4% above the top lists on the board, it does not
             ring and it is not bought (review 2026-09-05: zone_bounce_alerts
             gates every 🪃 push on the same line); OR, with no bounce read, a
             demand band that satisfies the proximity gate on its own — the
             print between the band floor and ALERT_MAX_ABOVE_DEMAND_PCT
             above its top.
  coverage   zone docs are READ from Mongo only (bounce_room.load_docs: the
             zone_store warm + the `bounce_room_zones` on-demand cache the
             Catalysts board's own bounce-room call fills). A name without a
             doc is skipped "no zone doc yet" and re-read next tick; the tick
             NEVER queues a build and never calls the provider (review
             2026-09-05: it used to call the board's payload builder, which
             snapshots the tape and queues 2-year price loads + zone builds
             for every miss — from inside a 60 s tick).
Stop = the anchoring demand band's lo x (1 - STOP_BUFFER_PCT/100) handed to
entries.enter as the ABSOLUTE level (stop_price=), the zone_edge rule; a pure
bounce off a broken-supply shelf (no demand band) uses that shelf's lo.

Pace: MAX_CATALYST_ENTRIES_PER_DAY = 1 ("time to time"), none at/after
zone_edge_entry.LAST_ENTRY_ET, one attempt per (symbol, ET day) recorded in
`catalyst_entry_state` BEFORE entries.enter (fails closed like zone_edge).

Safety invariants (same house rules as exit_engine / entries / zone_edge):
  * NEVER places an order at the broker directly — buys flow through
    entries.enter() (contract test greps this module).
  * armed=false places NO orders; the catalyst_entry flag is a second,
    independent switch (default OFF in every mode).
  * The try/except wraps ONLY entries.enter(); once it returns an order
    exists and no bookkeeping failure may relabel it.
  * run() is called from exit_engine.tick() step (j) inside try/except.
  * Import-light: stdlib + trading modules + supply_demand.alert_gates (a
    pure leaf) + zone_bounce_alerts.STALE_PRINT_SEC (the phone's constant);
    catalysts, bounce_room, zone_store and push imports are lazy.
  * No tape, no builds from the tick (tests/test_trading_contracts.py greps
    this file for the payload builder, the on-demand queue, the provider
    snapshot and the price/zone build calls — all must stay absent).
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from supply_demand import alert_gates
from supply_demand.zone_bounce_alerts import STALE_PRINT_SEC   # the phone's line, reused
from trading import entries
from trading import risk_rules
from trading import zone_edge_entry
from trading.broker import get_broker
from trading.exit_engine import (
    _broker_mode, _db, _et_day, _utc_iso, get_config, ledger, update_config)

broker = get_broker()    # module-level so tests can monkeypatch CE.broker

log = logging.getLogger("trading.catalyst_entry")

ET = ZoneInfo("America/New_York")

# ──────────────────────────────────────────────────────────────────────────────
# OWNER SETTINGS — the catalyst lane for the paper trial. NOT book numbers.
# Locked verbatim in tests/test_trading_contracts.py; changing any needs
# Ajay's sign-off.
# ──────────────────────────────────────────────────────────────────────────────
# "time to time" (Ajay 2026-09-05) — one catalyst buy per ET day.
MAX_CATALYST_ENTRIES_PER_DAY = 1
# Which scan quadrants may be bought: evidence-backed moves only.
QUADRANTS_OK = ("REAL", "OVERLOOKED")
# Review evidence grades that may be bought.
GRADES_OK = ("A", "B")
# Conservative liquidity floors — NOT from Ajay (builder defaults so the lane
# never buys a sub-$2 or thinly traded name; listed as owner settings in
# docs/supply_demand/catalyst_entry.md for him to change).
CATALYST_MIN_PRICE = 2.0
CATALYST_MIN_DOLLAR_VOL = 2_000_000
# The review's one-line catalyst summary is journaled at most this long.
SUMMARY_MAX_CHARS = 160
# Reused from the zone-edge lane (one truth, never redefined here).
LAST_ENTRY_ET = zone_edge_entry.LAST_ENTRY_ET
STOP_BUFFER_PCT = zone_edge_entry.STOP_BUFFER_PCT
STATE_COLL = "catalyst_entry_state"
# A name whose zone doc is not in Mongo yet. The tick never builds one — the
# Catalysts board's bounce-room call does (on-demand worker) — so this is a
# skip that clears itself once the board has been open.
NO_DOC_REASON = ("no zone doc yet (a Catalysts board visit builds it; "
                 "retried next tick)")

CITE = ("entry: Catalysts board + Supply & Demand OWNER RULES, no book "
        "(docs/supply_demand/catalyst_entry.md); stop/target/size via "
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


def _now_et() -> datetime:
    return datetime.now(ET)


def _band_txt(b: dict) -> str:
    return "%s %g-%g" % (b.get("kind"), b.get("lo", 0.0), b.get("hi", 0.0))


# ── Seams (each monkeypatchable in tests; every one lazy + fail-soft) ────────

def _cached_scan() -> Optional[dict]:
    """The Catalysts board's cached scan payload, or None. NEVER scans."""
    try:
        from catalysts.api import _cache_get
        payload = _cache_get()
        return payload if isinstance(payload, dict) else None
    except Exception as exc:                       # noqa: BLE001
        log.warning("catalyst_entry: cached scan read failed: %s", exc)
        return None


def _store_day(now_et: datetime) -> Optional[date]:
    """The zone store's latest stored session <= today (Mongo, one distinct
    query — the bounce-room payload builder's own rule), else the last weekday when
    the store is cold. None = the store could not be read (fails closed)."""
    try:
        from supply_demand import bounce_room, zone_store
        today = now_et.astimezone(ET).date()
        day = zone_store.latest_store_day(today=today)
        return day if day is not None else bounce_room.last_weekday(today)
    except Exception as exc:                       # noqa: BLE001
        log.warning("catalyst_entry: store day read failed: %s", exc)
        return None


def _zone_docs(tickers: list, store_date) -> dict:
    """{SYM: zone doc} for `store_date` — zone_store warm docs, then the
    `bounce_room_zones` on-demand cache (Mongo, then memory). READ ONLY: the
    misses are returned as absent, never queued for a build. {} on failure."""
    try:
        from supply_demand import bounce_room
        day = store_date
        if isinstance(day, str):
            day = date.fromisoformat(day)
        docs, _missing = bounce_room.load_docs(list(tickers), day)
        return {k: v for k, v in (docs or {}).items() if isinstance(v, dict)}
    except Exception as exc:                       # noqa: BLE001
        log.warning("catalyst_entry: zone docs read failed: %s", exc)
        return {}


def _parse_as_of(as_of) -> Optional[datetime]:
    """The scan's as_of (catalysts.api: datetime.now(utc).isoformat()) as an
    aware datetime; naive = UTC; garbage = None."""
    if isinstance(as_of, datetime):
        dt = as_of
    elif isinstance(as_of, str) and as_of.strip():
        try:
            dt = datetime.fromisoformat(as_of.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def snap_from_scan(c: dict, as_of) -> Optional[dict]:
    """PURE. The cached scan's row as a snapshot-shaped dict (the provider row
    shape) so
    bounce_room.read_symbol can read it: price = the print (last trade AND
    close), day_low / day_high the session bar, prev_close the prior close,
    as_of the trade stamp (ms) and the bar's ET date. None without a price.
    Missing day fields stay None — the touch read then simply finds nothing
    (an honest miss, never a false touch)."""
    px = _f((c or {}).get("price"))
    if px is None or px <= 0:
        return None
    dt = _parse_as_of(as_of)
    low, high, pc = _f(c.get("day_low")), _f(c.get("day_high")), _f(c.get("prev_close"))
    return {"last_trade_price": px, "close": px,
            "last_trade_ts_ms": (dt.timestamp() * 1000.0) if dt is not None else None,
            "low": low if (low is not None and low > 0) else None,
            "high": high if (high is not None and high > 0) else None,
            "prev_day_close": pc if (pc is not None and pc > 0) else None,
            "date": dt.astimezone(ET).date().isoformat() if dt is not None else None}


def _age_sec(as_of, now_et: datetime) -> Optional[float]:
    dt = _parse_as_of(as_of)
    if dt is None:
        return None
    return round(now_et.timestamp() - dt.timestamp(), 1)


def zone_rows(cands: list, docs: dict, day, as_of, now_et: datetime) -> dict:
    """PURE. {SYM: bounce-room contract row} — bounce_room.read_symbol over
    the Mongo docs and the scan-shaped snapshot: no doc -> coverage
    'pending' (no build is queued), tombstone -> 'unavailable', else print /
    bounce / room exactly as the board reads them, plus `print_age_sec`
    (seconds from the scan's as_of to now; None when as_of is unreadable)."""
    from supply_demand import bounce_room
    age = _age_sec(as_of, now_et)
    rows = {}
    for c in cands or []:
        sym = str(c.get("symbol") or "").upper()
        if not sym:
            continue
        doc = (docs or {}).get(sym)
        row = bounce_room.read_symbol(sym, doc if isinstance(doc, dict) else None,
                                      snap_from_scan(c, as_of), now=now_et)
        if row.get("coverage") in ("store", "ondemand"):
            row["print_age_sec"] = age
        rows[sym] = row
    return rows


def _notify(symbol: str, mode_word: str, body: str) -> None:
    """Owner push (same routing as zone_edge_entry._notify). Failures are
    logged + swallowed: push can never break the entry path."""
    try:
        from push import sender
        from push.hooks import ADMIN_EMAIL
        payload = {"title": "🗞️ Catalyst %s buy %s" % (mode_word, symbol),
                   "body": body,
                   "tag": "catalyst-entry-%s" % symbol,
                   "url": "/trading", "kind": "autopilot", "ticker": symbol}
        sender.send_to_user(ADMIN_EMAIL, payload, kind=None)
    except Exception as exc:                       # noqa: BLE001
        log.warning("catalyst_entry: push failed (%s): %s", symbol, exc)


def _mode_word(brk) -> str:
    try:
        m = getattr(brk, "mode", None)
        mode = str(m()) if callable(m) else _broker_mode()
    except Exception:                              # noqa: BLE001
        mode = "paper"
    return "LIVE" if mode == "live" else mode


# ── catalyst_entry_state (per symbol + ET day) ──────────────────────────────

def _coll(name: str):
    db = _db()
    if db is None:
        return None
    try:
        return getattr(db, name)
    except Exception as exc:                       # noqa: BLE001
        log.warning("catalyst_entry: collection %s unavailable: %s", name, exc)
        return None


def state_key(symbol: str, day: str) -> str:
    return "%s:%s" % (symbol, day)


def _get_state(key: str) -> Optional[dict]:
    """{} when none; None = UNKNOWN (fails closed)."""
    coll = _coll(STATE_COLL)
    if coll is None:
        return None
    try:
        return coll.find_one({"key": key}) or {}
    except Exception as exc:                       # noqa: BLE001
        log.warning("catalyst_entry_state read failed %s: %s", key, exc)
        return None


def _set_state(key: str, **fields) -> bool:
    """True only when the write went through — no order on False."""
    coll = _coll(STATE_COLL)
    if coll is None:
        return False
    fields["updated_at"] = _utc_iso()
    try:
        coll.update_one({"key": key}, {"$set": fields}, upsert=True)
        return True
    except Exception as exc:                       # noqa: BLE001
        log.warning("catalyst_entry_state write failed %s: %s", key, exc)
        return False


def _clear_state(key: str) -> None:
    coll = _coll(STATE_COLL)
    if coll is None:
        return
    try:
        coll.delete_many({"key": key})
    except Exception as exc:                       # noqa: BLE001
        log.warning("catalyst_entry_state clear failed %s: %s", key, exc)


def _entered_today(day: str) -> Optional[list]:
    coll = _coll(STATE_COLL)
    if coll is None:
        return None
    try:
        return [d for d in coll.find({"date": day, "entered": True}) if isinstance(d, dict)]
    except Exception as exc:                       # noqa: BLE001
        log.warning("catalyst_entry_state count failed: %s", exc)
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
        log.warning("catalyst_entry_state list failed: %s", exc)
    return rows


# ── Pure funnel (unit-tested) ────────────────────────────────────────────────

def qualify(c) -> Optional[str]:
    """None when the scan candidate passes the quality funnel, else the
    rejection reason. Every missing field fails CLOSED."""
    if not isinstance(c, dict):
        return "malformed candidate"
    raw_sym = c.get("ticker") or c.get("symbol")
    sym = raw_sym.strip().upper() if isinstance(raw_sym, str) else ""
    if not sym:
        return "no symbol"
    quad = c.get("quadrant")
    if quad not in QUADRANTS_OK:
        return "quadrant %s" % quad
    review = c.get("review")
    if not isinstance(review, dict):
        return "no review"
    grade = review.get("evidence_grade")
    grade = grade.strip().upper()[:1] if isinstance(grade, str) else None
    if grade not in GRADES_OK:
        return "grade %s" % grade
    if review.get("is_pump_warning") is not False:
        return "pump warning (or unknown)"
    ev = c.get("evidence")
    sec = ev.get("sec_filings") if isinstance(ev, dict) else None
    if not isinstance(sec, dict) or "has_offering" not in sec:
        return "offering unknown (no sec_filings read)"
    if sec.get("has_offering") is not False:
        return "offering on file (S-1/S-3/424B5/FWP)"
    price = _f(c.get("price"))
    if price is None or price <= 0:
        return "no price"
    if price < CATALYST_MIN_PRICE:
        return "price %g < %g" % (price, CATALYST_MIN_PRICE)
    dv = _f(c.get("dollar_volume"))
    if dv is None:
        return "dollar volume unknown"
    if dv < CATALYST_MIN_DOLLAR_VOL:
        return "dollar volume $%.0f < $%d" % (dv, CATALYST_MIN_DOLLAR_VOL)
    return None


def _candidate(c: dict) -> dict:
    review = c.get("review") or {}
    summary = review.get("catalyst_summary")
    summary = str(summary)[:SUMMARY_MAX_CHARS] if summary else None
    return {"symbol": str(c.get("ticker") or c.get("symbol")).strip().upper(),
            "quadrant": c.get("quadrant"),
            "grade": str(review.get("evidence_grade")).strip().upper()[:1],
            "catalyst_summary": summary,
            "price": _f(c.get("price")), "dollar_volume": _f(c.get("dollar_volume")),
            "change_pct": _f(c.get("change_pct")), "market_cap": _f(c.get("market_cap")),
            "composite_score": _f(c.get("composite_score")),
            # the scan's own session bar — the print the zone gate reads
            "day_low": _f(c.get("day_low")), "day_high": _f(c.get("day_high")),
            "prev_close": _f(c.get("prev_close"))}


def read_candidates(payload) -> tuple:
    """Pure funnel over the cached scan payload -> (candidates, rejected),
    candidates by the scan's composite score desc (the board's own order)."""
    if not isinstance(payload, dict):
        return [], []
    rows = payload.get("candidates")
    if not isinstance(rows, list):
        return [], []
    cands, rejected = [], []
    for c in rows:
        if not isinstance(c, dict):
            continue
        why = qualify(c)
        if why is None:
            cands.append(_candidate(c))
        else:
            raw = c.get("ticker") or c.get("symbol")
            rejected.append({"symbol": str(raw).strip().upper() if isinstance(raw, str) else "",
                             "reason": why})
    cands.sort(key=lambda c: -(c.get("composite_score") or 0.0))
    return cands, rejected


def zone_gate(c: dict, row: Optional[dict], doc: Optional[dict]) -> tuple:
    """The phone's alert rules on the bounce-room row + its zone doc ->
    (ok, detail). detail = {reason, print, room, bounce, proximity, side,
    band, stop_price, stop_pct, coverage}. Pure."""
    d = {"reason": None, "print": None, "print_age_sec": None, "room": None, "bounce": None,
         "proximity": None, "side": None, "band": None, "stop_price": None, "stop_pct": None,
         "coverage": (row or {}).get("coverage")}
    if not isinstance(row, dict) or row.get("coverage") == "pending":
        d["reason"] = NO_DOC_REASON
        return False, d
    if row.get("coverage") == "unavailable":
        d["reason"] = "zone coverage unavailable: %s" % (row.get("error") or "no doc")
        return False, d
    px = _f(row.get("print"))
    if px is None or px <= 0:
        d["reason"] = "no print in bounce-room row"
        return False, d
    d["print"] = px
    # Stale print = the phone's rule (zone_bounce_alerts.STALE_PRINT_SEC): the
    # print is the cached scan's price, so its age is the scan's age. An
    # engine buy must not act on a print the phone would refuse to ring on.
    age = _f(row.get("print_age_sec"))
    d["print_age_sec"] = age
    if age is None:
        d["reason"] = "alert gate: print age unknown (scan as_of unreadable)"
        return False, d
    if age > STALE_PRINT_SEC:
        d["reason"] = ("alert gate: print stale (scan %ds old > %ds, "
                       "zone_bounce_alerts.STALE_PRINT_SEC)" % (age, STALE_PRINT_SEC))
        return False, d
    if not isinstance(doc, dict) or not isinstance(doc.get("bands"), list) \
            or not all(isinstance(b, dict) for b in doc["bands"]):
        d["reason"] = "zone doc unknown (bands unreadable)"
        return False, d
    bands = doc["bands"]
    # Room: the alert rule on the doc's bands (the source the row was read from).
    ok_room, room = alert_gates.room_gate(px, bands, doc.get("prev_close"))
    d["room"] = room or {"state": "CLEAR", "room_pct": None, "target": None, "band": None}
    if not ok_room:
        if room is None:
            d["reason"] = "alert gate: unusable print"
        elif room.get("state") == "IN_BAND":
            rb = room.get("band") or {}
            d["reason"] = "alert gate: inside %s band %g-%g" % (
                rb.get("kind"), rb.get("lo", 0.0), rb.get("hi", 0.0))
        else:
            # RAW at 2 dp — the 1-dp display number can read "5.0% < 5%"
            # (review 2026-09-05, the 4.995% boundary).
            d["reason"] = "alert gate: room %.2f%% < %g%% (%s)" % (
                room.get("room_pct_raw", room["room_pct"]), alert_gates.ALERT_MIN_ROOM_PCT,
                _band_txt(room.get("band") or {}))
        return False, d
    # Level: a bounce read whose band STILL holds the print within the
    # proximity line, else a demand band within that line on its own.
    bounce = row.get("bounce") if isinstance(row.get("bounce"), dict) else None
    anchor, side = None, None
    if bounce and isinstance(bounce.get("band"), dict):
        anchor = bounce["band"]
        side = "broken_supply" if bounce.get("role") == "broken_supply" else "demand"
        d["bounce"] = bounce
        # Phone gate = entry gate (review 2026-09-05): zone_bounce_alerts gates
        # every 🪃 push on demand_proximity_gate against the bounce band; a
        # bounce read NEEDS a 3%+ lift, so the print is routinely more than 1%
        # over the top — "I am late" — and must not be bought either.
        if not alert_gates.demand_proximity_gate(px, anchor):
            b_lo, b_hi = _f(anchor.get("lo")), _f(anchor.get("hi"))
            if b_lo is not None and px < b_lo:
                d["reason"] = ("alert gate: print %.2f back under bounce band floor %g"
                               % (px, b_lo))
            else:
                d["reason"] = ("alert gate: print %.1f%% above bounce band top %g (max %g%%)"
                               % ((px / (b_hi or px) - 1.0) * 100.0, b_hi or 0.0,
                                  alert_gates.ALERT_MAX_ABOVE_DEMAND_PCT))
            return False, d
        d["proximity"] = {"ok": True,
                          "band": {"kind": anchor.get("kind"), "lo": float(anchor["lo"]),
                                   "hi": float(anchor["hi"]),
                                   "touches": int(_f(anchor.get("touches")) or 0)},
                          "above_top_pct": round((px / float(anchor["hi"]) - 1.0) * 100.0, 2),
                          "anchor": "bounce"}
    else:
        near = [b for b in bands
                if str(b.get("kind") or "demand").lower() == "demand"
                and alert_gates.demand_proximity_gate(px, b)]
        if near:
            anchor = max(near, key=lambda b: float(b["lo"]))
            side = "demand"
            d["proximity"] = {"ok": True,
                              "band": {"kind": "demand", "lo": float(anchor["lo"]),
                                       "hi": float(anchor["hi"]),
                                       "touches": int(_f(anchor.get("touches")) or 0)},
                              "above_top_pct": round((px / float(anchor["hi"]) - 1.0) * 100.0, 2),
                              "anchor": "band"}
    if anchor is None:
        d["reason"] = ("alert gate: not at a demand level (no bounce, no demand band "
                       "within %g%% under the print)" % alert_gates.ALERT_MAX_ABOVE_DEMAND_PCT)
        return False, d
    lo = _f(anchor.get("lo"))
    if lo is None or lo <= 0:
        d["reason"] = "anchor band has no floor"
        return False, d
    d["side"] = side
    d["band"] = {"kind": anchor.get("kind"), "lo": lo, "hi": _f(anchor.get("hi")),
                 "touches": int(_f(anchor.get("touches")) or 0)}
    # Stop: under the demand floor (zone_edge rule); a broken-supply shelf's lo as is.
    stop = round(lo * (1.0 - STOP_BUFFER_PCT / 100.0), 4) if side == "demand" else round(lo, 4)
    stop_pct = round((px - stop) / px * 100.0, 2)
    d["stop_price"], d["stop_pct"] = stop, stop_pct
    if stop_pct <= 0:
        d["reason"] = "stop not below print (stop %s vs print %s)" % (stop, px)
        return False, d
    if stop_pct > risk_rules.ABS_MAX_STOP_PCT:
        d["reason"] = ("stop wider than engine max (%.2f%% > %g%%)"
                       % (stop_pct, risk_rules.ABS_MAX_STOP_PCT))
        return False, d
    return True, d


def _res_get(res, key):
    return res.get(key) if isinstance(res, dict) else None


def _push_body(sym: str, c: dict, g: dict, res) -> str:
    try:
        plan = _res_get(res, "stop")
        stop_px = _f(plan.get("stop_price")) if isinstance(plan, dict) else None
        if stop_px is None:
            stop_px = _f(g.get("stop_price")) or 0.0
        room = g.get("room") or {}
        room_txt = ("room +%g%%" % room["room_pct"] if room.get("room_pct") is not None
                    else "room: clear runway")
        return ("%s %s/%s: %d sh at ~%.2f, stop %.2f (%.2f%%), %s band %g-%g, %s — %s"
                % (sym, c.get("quadrant"), c.get("grade"),
                   int(_f(_res_get(res, "shares")) or 0), g["print"], stop_px,
                   _f(g.get("stop_pct")) or 0.0, g.get("side"),
                   (g.get("band") or {}).get("lo", 0.0), (g.get("band") or {}).get("hi", 0.0),
                   room_txt, c.get("catalyst_summary") or "(no summary)"))
    except Exception as exc:                       # noqa: BLE001
        log.warning("catalyst_entry: push body failed %s: %s", sym, exc)
        return "%s: ordered (detail unavailable)" % sym


def _ledger_disabled_once(cfg: dict, gate: dict) -> bool:
    today = _et_day()
    if cfg.get("last_catalyst_entry_disabled_day") == today:
        return False
    ledger("catalyst_entry_disabled",
           detail={"gate": gate,
                   "hint": "needs configured + armed + catalyst_entry flag + market open"})
    update_config(last_catalyst_entry_disabled_day=today)
    return True


# ── The per-tick runner (exit_engine.tick step (j), AFTER exits) ────────────

def run(broker=None, cfg: Optional[dict] = None) -> dict:
    """Evaluate the cached catalyst scan once; place at most
    MAX_CATALYST_ENTRIES_PER_DAY buys via entries.enter(). Never raises past
    its fence."""
    brk = broker if broker is not None else globals()["broker"]
    cfg = cfg or get_config()
    day = _et_day()
    out = {"ok": True, "ran": False, "day": day, "entered": [], "blocked": [],
           "skipped": [], "skipped_alert_gate": 0, "skipped_pending": 0,
           "evaluated": 0, "rejected": 0, "entries_today": 0, "errors": []}

    try:
        configured = bool(brk.configured())
    except Exception as exc:                       # noqa: BLE001
        configured = False
        out["errors"].append("configured: %s" % exc)
    gate = {"configured": configured, "armed": bool(cfg.get("armed")),
            "catalyst_entry": bool(cfg.get("catalyst_entry")), "market_open": False}
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
    if now_et.time() >= LAST_ENTRY_ET:
        out["reason"] = "after_last_entry_time"
        return out

    payload = _cached_scan()
    if payload is None:
        out["reason"] = "no cached catalyst scan"
        return out
    out["scan_as_of"] = payload.get("as_of")
    cands, rejected = read_candidates(payload)
    out["rejected"] = len(rejected)
    if not cands:
        out["reason"] = "no_candidates"
        return out

    try:
        positions = brk.positions()
    except Exception as exc:                       # noqa: BLE001
        out["ok"] = False
        out["errors"].append("positions: %s" % exc)
        out["reason"] = "positions_unavailable"
        return out
    held = {str(p.get("symbol") or "").upper() for p in positions if isinstance(p, dict)}
    pos_count = len(positions)
    entered_rows = _entered_today(day)
    if entered_rows is None:
        out["ok"] = False
        out["errors"].append("catalyst_entry_state unreadable — no attempts")
        out["reason"] = "state_unavailable"
        return out
    entries_today = len(entered_rows)
    out["entries_today"] = entries_today
    if entries_today >= MAX_CATALYST_ENTRIES_PER_DAY:
        out["reason"] = "daily cap reached"
        return out

    def _skip(sym, why):
        out["skipped"].append({"symbol": sym, "reason": why})

    # Cheap pre-filter so the zone read covers only names that could be bought.
    todo = []
    for c in cands:
        sym = c["symbol"]
        out["evaluated"] += 1
        if sym in held:
            _skip(sym, "already held")
            continue
        st = _get_state(state_key(sym, day))
        if st is None:
            out["ok"] = False
            out["errors"].append("%s: state read failed — not attempting" % sym)
            _skip(sym, "state unknown (read failed)")
            continue
        if st:
            _skip(sym, "attempted today")
            continue
        todo.append(c)
    if not todo:
        out["reason"] = "no_candidates_left"
        return out

    # Zone docs from Mongo only (never built here), priced off the scan's own
    # row: the tick reaches neither the tape nor the on-demand queue.
    store_day = _store_day(now_et)
    if store_day is None:
        out["ok"] = False
        out["errors"].append("zone store day unreadable — no attempts")
        for c in todo:
            _skip(c["symbol"], "zone store unreadable (no store day)")
        out["reason"] = "zone_store_unavailable"
        return out
    out["store_date"] = store_day.isoformat()
    docs = _zone_docs([c["symbol"] for c in todo], store_day)
    rows = zone_rows(todo, docs, store_day, payload.get("as_of"), now_et)
    mode_word = _mode_word(brk)

    for c in todo:
        sym = c["symbol"]
        if entries_today >= MAX_CATALYST_ENTRIES_PER_DAY:
            _skip(sym, "daily cap %d reached" % MAX_CATALYST_ENTRIES_PER_DAY)
            continue
        if pos_count >= risk_rules.MAX_POSITIONS:
            _skip(sym, "no position slot (%d/%d)" % (pos_count, risk_rules.MAX_POSITIONS))
            continue
        ok, g = zone_gate(c, rows.get(sym), docs.get(sym))
        if not ok:
            # A SKIP, not an attempt: pending coverage lands next tick, the
            # room can open, a bounce can print. Re-read every tick.
            if g["reason"] == NO_DOC_REASON:
                out["skipped_pending"] += 1
            elif str(g["reason"]).startswith("alert gate"):
                out["skipped_alert_gate"] += 1
            _skip(sym, g["reason"])
            continue

        key = state_key(sym, day)
        attempt = {"quadrant": c["quadrant"], "grade": c["grade"],
                   "catalyst_summary": c["catalyst_summary"], "price": c["price"],
                   "dollar_volume": c["dollar_volume"], "print": g["print"],
                   "print_basis": "catalyst scan price", "print_age_sec": g["print_age_sec"],
                   "room": g["room"], "bounce": g["bounce"], "proximity": g["proximity"],
                   "side": g["side"], "band": g["band"],
                   "stop_price": g["stop_price"], "stop_pct": g["stop_pct"],
                   "scan_as_of": payload.get("as_of")}
        # Record the attempt BEFORE the order path (fails closed on a failed write).
        if not _set_state(key, symbol=sym, date=day, attempted=True, entered=False,
                          result="pending", reason=None, **attempt):
            out["ok"] = False
            out["errors"].append("%s: state write failed — not attempting" % sym)
            _skip(sym, "state write failed (not attempted)")
            continue

        reason = {"quadrant": c["quadrant"], "grade": c["grade"],
                  "catalyst_summary": c["catalyst_summary"], "room": g["room"],
                  "bounce": g["bounce"], "proximity": g["proximity"], "side": g["side"],
                  "price": c["price"], "dollar_volume": c["dollar_volume"],
                  "print": g["print"], "print_basis": "catalyst scan price",
                  "print_age_sec": g["print_age_sec"], "stop_pct": g["stop_pct"]}
        veto = None
        res = None
        try:
            # stop_price = the ABSOLUTE owner level (entries converts it at its
            # own planning price and refuses, never clamps, on drift).
            res = entries.enter(sym, limit_price=None, stop_pct=g["stop_pct"],
                                strategy="catalyst", reason=reason,
                                stop_price=g["stop_price"], allow_earnings=False)
        except ValueError as exc:
            veto = str(exc)
        except Exception as exc:                   # noqa: BLE001
            out["errors"].append("%s: %s" % (sym, exc))
            _set_state(key, result="error", reason=str(exc))
            ledger("catalyst_entry_error", symbol=sym,
                   detail=dict(attempt, error=str(exc),
                               hint="unexpected failure after trigger — "
                                    "verify at the broker whether an order exists"),
                   dry_run=False, cite=CITE)
            continue
        if veto is not None:
            if "market closed" in veto.lower():
                _clear_state(key)
                _skip(sym, "market closed")
                continue
            out["blocked"].append(sym)
            _set_state(key, result="blocked", reason=veto)
            ledger("catalyst_entry_blocked", symbol=sym,
                   detail=dict(attempt, reason=veto), dry_run=True, cite=CITE)
            continue

        # ORDER PLACED. Bookkeeping only from here (each step swallows its own failure).
        entries_today += 1
        pos_count += 1
        out["entered"].append(sym)
        order_id = _res_get(res, "order_id")
        ledger("catalyst_entry", symbol=sym,
               detail=dict(attempt, strategy="catalyst",
                           order=res if isinstance(res, dict) else str(res),
                           order_id=order_id),
               dry_run=False, cite=CITE)
        _set_state(key, entered=True, result="entered", order_id=order_id,
                   order_ts=_utc_iso())
        _notify(sym, mode_word, _push_body(sym, c, g, res))

    out["entries_today"] = entries_today
    return out


# ── Status block (rides in GET /trading/status) ─────────────────────────────

def rules_list() -> list:
    """Every rule this lane enforces, as data — the FE renders THIS list.
    `source` is the honesty note per rule."""
    quote = ("Ajay 2026-09-05: 'What ever rules I created for the alerts are the "
             "ideal conditions for a stock to be bough in Autopilot ... catalyst "
             "based entries time to time'")
    return [
        {"rule": "Source is the Catalysts board's CACHED scan only — the lane never "
                 "triggers a scan; no cached scan (or an expired one) = nothing bought",
         "value": "catalysts.api._cache_get()", "source": "owner rule (%s; no book)" % quote},
        {"rule": "Quadrant must be evidence-backed", "value": " | ".join(QUADRANTS_OK),
         "source": "owner setting (builder default, NOT from Ajay; S&D/catalysts, no book)"},
        {"rule": "Review evidence grade", "value": " | ".join(GRADES_OK),
         "source": "owner setting (builder default, NOT from Ajay; no book)"},
        {"rule": "No pump warning on the review and no offering (S-1/S-3/424B5/FWP) "
                 "in the last 7 days of filings; unknown fails closed",
         "value": "is_pump_warning = false, has_offering = false",
         "source": "owner setting (builder default, NOT from Ajay; no book)"},
        {"rule": "Liquidity floors — never a sub-$%g name or thin tape; no market-cap "
                 "floor because the scan is sub-$500M by construction" % CATALYST_MIN_PRICE,
         "value": "price >= $%g, dollar volume >= $%s"
                  % (CATALYST_MIN_PRICE, format(CATALYST_MIN_DOLLAR_VOL, ",")),
         "source": "owner setting (conservative builder default, NOT from Ajay; no book)"},
        {"rule": "Phone gate = entry gate: at least %g%% room from the print to the "
                 "first UNBROKEN band overhead (CLEAR passes; inside a band fails)"
                 % alert_gates.ALERT_MIN_ROOM_PCT,
         "value": "room >= %g%% (alert_gates.ALERT_MIN_ROOM_PCT)" % alert_gates.ALERT_MIN_ROOM_PCT,
         "source": "owner rule (%s; S&D, no book)" % quote},
        {"rule": "Phone gate = entry gate: the print must sit AT a level — a bounce "
                 "read off a demand band / broken-supply shelf whose band STILL holds "
                 "the print within %g%% of its top, or (no bounce) a demand band with "
                 "the print between its floor and %g%% above its top; a bounce that "
                 "already ran past the line lists on the board, it is not bought"
                 % (alert_gates.ALERT_MAX_ABOVE_DEMAND_PCT, alert_gates.ALERT_MAX_ABOVE_DEMAND_PCT),
         "value": "band.lo <= print <= band.hi x (1 + %g%%) — bounce band or demand band"
                  % alert_gates.ALERT_MAX_ABOVE_DEMAND_PCT,
         "source": "owner rule (%s; S&D, no book)" % quote},
        {"rule": "The print is the cached scan's own price (no tape read from the tick); "
                 "older than the phone's stale line it is not acted on — "
                 "zone_bounce_alerts.STALE_PRINT_SEC, reused",
         "value": "scan age <= %ds" % STALE_PRINT_SEC,
         "source": "owner rule (the 🪃 push's own stale line; S&D, no book)"},
        {"rule": "Zone docs are READ from Mongo only (zone_store warm + the on-demand "
                 "cache the Catalysts board's bounce-room call fills); a name without a "
                 "doc is skipped and re-read next tick — the tick never builds one and "
                 "never assumes clear",
         "value": "coverage in (store, ondemand); else skip",
         "source": "owner rule (S&D, no book); review 2026-09-05"},
        {"rule": "Requested stop under the anchoring demand band's floor, handed as the "
                 "absolute LEVEL; a broken-supply shelf uses its lo; wider than the "
                 "engine's absolute maximum is skipped, never clamped",
         "value": "band.lo x (1 - %g%%), skipped past %g%%"
                  % (STOP_BUFFER_PCT, risk_rules.ABS_MAX_STOP_PCT),
         "source": "owner buffer (zone_edge_entry.STOP_BUFFER_PCT); cap = "
                   "trading/risk_rules.py risk contract"},
        {"rule": "At most %d catalyst buy a day ('time to time'), none at/after %s ET, "
                 "one attempt per symbol per day, never a name already held"
                 % (MAX_CATALYST_ENTRIES_PER_DAY, LAST_ENTRY_ET.strftime("%H:%M")),
         "value": "%d/day, last tick %s" % (MAX_CATALYST_ENTRIES_PER_DAY,
                                           LAST_ENTRY_ET.strftime("%H:%M")),
         "source": "owner rule (%s; no book)" % quote},
        {"rule": "Every buy flows through the same sized-and-stopped path as manual, "
                 "funnel and zone-edge entries: armed switch, %d-position cap, "
                 "sizing, streak multiplier, never average down, earnings shield, "
                 "reward:risk floor — PAPER account" % risk_rules.MAX_POSITIONS,
         "value": "entries.enter -> risk_rules (FROZEN)",
         "source": "trading/risk_rules.py (engine-wide risk contract)"},
    ]


def status_block(cfg: Optional[dict] = None, brk=None) -> dict:
    """{enabled, entries_today, max_per_day, last_entry_et, rules, candidates,
    skipped, attempts, as_of, scan, paper_only}. candidates / skipped = the
    quality funnel over the cached scan (the zone gate runs at tick time and
    lands in attempts / the tick summary). paper_only is DERIVED from the
    broker's mode (review 2026-09-05), never asserted."""
    cfg = cfg or get_config()
    brk = brk if brk is not None else globals()["broker"]
    day = _et_day()
    payload = _cached_scan()
    cands, rejected = read_candidates(payload)
    scan = None
    if isinstance(payload, dict):
        scan = {"cached": bool(payload.get("cached")),
                "cache_age_sec": payload.get("cache_age_sec"),
                "n_total": payload.get("n_total")}
    return {"enabled": bool(cfg.get("catalyst_entry")),
            "paper_only": _mode_word(brk) != "LIVE",
            "entries_today": _entries_today(day),
            "max_per_day": MAX_CATALYST_ENTRIES_PER_DAY,
            "last_entry_et": LAST_ENTRY_ET.strftime("%H:%M"),
            "as_of": payload.get("as_of") if isinstance(payload, dict) else None,
            "scan": scan,
            "rules": rules_list(),
            "candidates": cands,
            "skipped": rejected,
            "attempts": _today_attempts(day)}


# ── Warm (cron): keep the two inputs the lane READS from actually populated ──
# Ajay 2026-09-05: "make sure you have demand zone and catalyst based entries
# time to time". The tick itself never scans, never touches the tape and
# never builds zone docs (that keeps stop protection fast) — so without this
# pass the catalyst lane could only fire on a day someone had opened the
# Catalysts board (which caches the scan) AND that visit had built the zone
# docs. This runs OUTSIDE the tick, from the cron, twice an hour in RTH:
#   1. the Catalysts scan — reused when the board's cache is fresh, else run
#      through the SAME pipeline the board uses (with the LLM review, since
#      the funnel needs review.evidence_grade) and written to the same cache
#      so the board and the lane always read one payload;
#   2. bounce_room zone docs for every candidate that has none for the store
#      day (synchronous compute_batch; budget = bounce_room's own).
# Owner setting: WARM_CRON = "12,42 9-15 * * 1-5" (pinned in tests to
# backend/crontab). Failures are logged and returned, never raised.
WARM_CRON = "12,42 9-15 * * 1-5"


def warm(now: Optional[datetime] = None, *, cached=None, scan_fn=None, cache_put=None,
         load_docs=None, compute_batch=None) -> dict:
    """One warm pass. Every collaborator is injectable for tests; the cron
    passes none. Returns counts, never raises."""
    now_et = now or _now_et()
    out = {"scan": "cached", "candidates": 0, "docs_have": 0, "docs_built": 0,
           "docs_missing": 0, "error": None}
    try:
        payload = cached() if cached is not None else _cached_scan()
        if not isinstance(payload, dict):
            if scan_fn is None or cache_put is None:
                from catalysts.api import _cache_put as _put, _full_scan as _scan
                scan_fn = scan_fn or _scan
                cache_put = cache_put or _put
            payload = scan_fn(with_gemma=True)
            if isinstance(payload, dict):
                cache_put(payload)
            out["scan"] = "ran"
        cands = (payload or {}).get("candidates") if isinstance(payload, dict) else None
        tickers = sorted({str(c.get("ticker") or "").upper() for c in (cands or [])
                          if isinstance(c, dict) and c.get("ticker")})
        out["candidates"] = len(tickers)
        if not tickers:
            return out
        day = _store_day(now_et)
        if day is None:
            out["error"] = "store day unreadable"
            return out
        if load_docs is None or compute_batch is None:
            from supply_demand import bounce_room
            load_docs = load_docs or bounce_room.load_docs
            compute_batch = compute_batch or bounce_room.compute_batch
        docs, missing = load_docs(tickers, day)
        out["docs_have"] = len([v for v in (docs or {}).values() if isinstance(v, dict)])
        out["docs_missing"] = len(missing or [])
        if missing:
            res = compute_batch(list(missing), day) or {}
            out["docs_built"] = int(res.get("built") or 0)
    except Exception as exc:                       # noqa: BLE001
        log.warning("catalyst_entry: warm failed: %s", exc)
        out["error"] = str(exc)[:200]
    log.info("CATALYST-WARM: %s", out)
    return out


if __name__ == "__main__":
    import json
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if "--warm" in sys.argv[1:]:
        print(json.dumps(warm(), default=str))
    else:
        print(json.dumps(status_block(), indent=1, default=str))
