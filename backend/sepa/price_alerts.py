"""Per-stock on-demand price alerts.

Two collections:
  price_alerts          {_id, symbol, kind, level, created_price, created_at,
                         last_fired_at, channels[], note, user_email,
                         armed, triggered_at, triggered_price, triggered_ref,
                         rearmed_at, migrated_at?}
  price_alert_fires     {_id, alert_id, symbol, kind, level, price, fired_at,
                         channels[], message}
                        (sepa/vcp_watch.py writes into the SAME collection with
                         alert_id=None and an extra `meta` key — never pin
                         "every row" here.)

`kind` is one of:
  - "below"     → fire when last <= level
  - "above"     → fire when last >= level
  - "drop_pct"  → fire when last <= created_price * (1 - level/100)
  - "rise_pct"  → fire when last >= created_price * (1 + level/100)

`_threshold()` is the ONE place that line is computed; `_hit()` compares the
live print against it.

The latch (2026-09-21) — one fire per crossing
----------------------------------------------
Before this, an alert whose price simply STAYED past its line re-fired every
`ALERT_COOLDOWN_SEC` forever: a preset set in May/June printed a fresh "PRICE
ALERT" row twice a day, months later. Each doc now carries `armed`:

    armed | hit   | last_fired_at | live  | action        | effect
    ------+-------+---------------+-------+---------------+--------------------
    None  | True  | > 0           | any   | latch_legacy  | silent migrate
    None  | True  | 0             | any   | fire          | fires once
    None  | False | any           | True  | arm_legacy    | silent migrate
    None  | False | any           | False | noop          | stays legacy
    False | True  | any           | any   | hold          | nothing, ever
    False | False | any           | True  | rearm         | silent re-arm
    False | False | any           | False | hold          | nothing (see `live`)
    True  | False | any           | any   | noop          | nothing
    True  | True  | any           | any   | fire          | subject to cooldown

`live` = the print came from a `prices.bulk_live_prices` snapshot row (a real
quote). `prices.last_trade_price` falls back to the CACHED daily close on any
Massive failure — a real-looking number that may sit on the far side of the
line. Such a print may still fire/latch (unchanged behaviour) but it may NEVER
re-arm a latched doc nor arm a legacy one, or one provider outage would re-arm
everything and re-fire the whole set on the next real print.

Legacy docs (no `armed` key) self-migrate in the loop — idempotent, no
operator step. A legacy latch writes `triggered_price: None` on purpose:
`last_fired_at` is the moment of the LAST re-fire, and the migrating run's
print is a different moment. The price of every fire lives in
`price_alert_fires`.

The cron worker calls `check_alerts()` every 5 minutes during market hours; it
makes ONE `bulk_live_prices` call per run and falls back to
`last_trade_price` only for symbols the bulk call missed. A fire is still
rate-limited per alert by ALERT_COOLDOWN_SEC.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from . import notify, prices

log = logging.getLogger("sepa.price_alerts")

ALERT_COOLDOWN_SEC = 6 * 3600
KINDS = {"below", "above", "drop_pct", "rise_pct"}


def _db():
    try:
        from pymongo import MongoClient
        url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        client = MongoClient(url, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        return client[os.getenv("MONGO_DB", "cheetah")]
    except Exception as exc:
        log.warning("price_alerts: Mongo unavailable: %s", exc)
        return None


def _strip_id(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if doc and "alert_id" in doc:
        doc["alert_id"] = str(doc["alert_id"])
    return doc


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def _target_email(alert: dict) -> Optional[str]:
    """Who receives this alert's push. The alert's own creator wins; legacy
    alerts (created before user-scoping, 2026-06-02) fall back to the house
    owner so they still deliver. REQUIRED for delivery: `price_alert` is a
    PRIVATE notify kind, and notify._send_push REFUSES a private kind without a
    user_email (returns 0 = silent drop). This was the bug — check_alerts fired
    with no user_email, so every price-alert push was being dropped."""
    em = (alert.get("user_email") or "").strip()
    if em:
        return em
    try:
        from auth import HOUSE_OWNER_EMAIL
        return HOUSE_OWNER_EMAIL or None
    except Exception:
        return None


def create(symbol: str, kind: str, level: float,
           channels: Optional[list[str]] = None,
           note: Optional[str] = None,
           user_email: Optional[str] = None) -> Optional[dict]:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    db = _db()
    if db is None:
        return None
    last = prices.last_trade_price(symbol)
    doc = {
        "symbol": symbol.upper(),
        "kind": kind,
        "level": float(level),
        "created_price": float(last) if last else None,
        "created_at": int(time.time()),
        "last_fired_at": 0,
        "channels": channels or ["push", "browser"],
        "note": note,
        # Scope to creator so the fire path can deliver the push (see
        # _target_email — without this the private-kind guard drops it).
        "user_email": (user_email or "").lower().strip() or None,
        # Latch state, written at birth so a doc set after the 2026-09-21
        # deploy is never treated as legacy by check_alerts (no migration
        # branch, no `migrated_at`).
        "armed": True,
        "triggered_at": None,
        "triggered_price": None,
        "triggered_ref": None,
        "rearmed_at": None,
    }
    res = db.price_alerts.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _strip_id(doc)


def list_active() -> list[dict]:
    db = _db()
    if db is None:
        return []
    out: list[dict] = []
    for d in db.price_alerts.find().sort("created_at", -1):
        line = _state_line(d)
        row = _strip_id(d)
        # `armed` None = the doc has not been evaluated since the deploy.
        row["armed"] = row.get("armed")
        for k in ("triggered_at", "triggered_price", "triggered_ref", "rearmed_at"):
            row[k] = row.get(k)
        row["state_line"] = line
        out.append(row)
    return out


def delete(alert_id: str) -> bool:
    db = _db()
    if db is None:
        return False
    from bson import ObjectId
    try:
        oid = ObjectId(alert_id)
    except Exception:
        return False
    res = db.price_alerts.delete_one({"_id": oid})
    return res.deleted_count > 0


def recent_fires(since: int = 0, limit: int = 50) -> list[dict]:
    db = _db()
    if db is None:
        return []
    cur = db.price_alert_fires.find({"fired_at": {"$gt": int(since)}}).sort("fired_at", -1).limit(limit)
    return [_strip_id(d) for d in cur]


# ---------------------------------------------------------------------------
# Pure helpers (no I/O, never raise)
# ---------------------------------------------------------------------------
def _num(x) -> Optional[float]:
    """float(x) for a real int/float only. bools and strings are not numbers."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    try:
        return float(x)
    except Exception:
        return None


def _threshold(alert: dict, last: Optional[float] = None) -> Optional[float]:
    """THE price line this alert is measured against. None when it cannot be
    computed (unknown/missing kind, missing level, pct kind with neither a
    created_price nor a live print)."""
    try:
        kind = alert.get("kind")
        if kind not in KINDS:
            return None
        level = _num(alert.get("level"))
        if level is None:
            return None
        if kind in ("below", "above"):
            return level
        created = _num(alert.get("created_price")) or _num(last)
        if not created:
            return None
        if kind == "drop_pct":
            return created * (1 - level / 100)
        return created * (1 + level / 100)
    except Exception:
        return None


def _hit(alert: dict, last: float) -> bool:
    thr = _threshold(alert, last)
    lastf = _num(last)
    if thr is None or lastf is None:
        return False
    kind = alert.get("kind")
    if kind in ("below", "drop_pct"):
        return lastf <= thr
    if kind in ("above", "rise_pct"):
        return lastf >= thr
    return False


def _live_print(row: Optional[dict]) -> Optional[float]:
    """The house read of a live print from a bulk_live_prices row:
    last_trade_price first, then price. 0 / None = no print (the
    prices.extended_print convention)."""
    if not isinstance(row, dict):
        return None
    px = _num(row.get("last_trade_price")) or _num(row.get("price")) or 0.0
    return px if px > 0 else None


def _today_pct(last: float, row: Optional[dict]) -> Optional[float]:
    """Today's move off the SAME snapshot row's previous close. None (never 0)
    when there is no usable previous close."""
    lastf = _num(last)
    if lastf is None or not isinstance(row, dict):
        return None
    prev = _num(row.get("prev_day_close"))
    if not prev or prev <= 0:
        return None
    return (lastf / prev - 1) * 100


def _et_day_label(epoch) -> Optional[str]:
    """"Jun 1" in market time. None for 0 / None / garbage."""
    if isinstance(epoch, bool):
        return None
    try:
        ts = int(epoch)
    except Exception:
        return None
    if ts <= 0:
        return None
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        dt = datetime.fromtimestamp(ts, ZoneInfo("America/New_York"))
        return f"{dt.strftime('%b')} {dt.day}"
    except Exception:
        return None


def _money(x) -> Optional[str]:
    n = _num(x)
    if n is None:
        return None
    return f"${n:,.2f}"


def _direction_back(kind) -> Optional[str]:
    if kind in ("below", "drop_pct"):
        return "above"
    if kind in ("above", "rise_pct"):
        return "below"
    return None


def _format(alert: dict, last: float, row: Optional[dict] = None) -> str:
    """The pushed / recorded text. Built from the doc's OWN set price and set
    date plus the same snapshot row's previous close — no bare floats, no
    undated percentages."""
    sym = alert.get("symbol")
    kind = alert.get("kind")
    level = alert.get("level")
    created = _num(alert.get("created_price"))
    set_lbl = _et_day_label(alert.get("created_at"))
    tp = _today_pct(last, row)
    today_seg = f" · today {tp:+.1f}%" if tp is not None else ""
    now_money = _money(last) or f"{last}"

    if kind in ("drop_pct", "rise_pct"):
        if created:
            pct = (float(last) / created - 1) * 100
            when = f"when you set it ({set_lbl})" if set_lbl else "when you set it"
            head = (f"{sym} {pct:+.1f}% vs {_money(created)} {when}"
                    f"{today_seg} · now {now_money}")
        else:
            head = f"{sym} now {now_money} (no set price on record)"
    else:
        arrow, op = ("↓", "≤") if kind == "below" else ("↑", "≥")
        lvl = _money(level) or f"{level}"
        if set_lbl and created:
            tail = f" (set {set_lbl} at {_money(created)})"
        elif set_lbl:
            tail = f" (set {set_lbl})"
        elif created:
            tail = f" (set at {_money(created)})"
        else:
            tail = ""
        head = f"{sym} {arrow} {now_money} crossed your {op} {lvl} line{tail}"

    note = alert.get("note")
    return head + (f"\nNote: {note}" if note else "")


def _state_line(alert: dict) -> Optional[str]:
    """The served one-liner the Active-alerts list prints verbatim. None unless
    the doc is latched AND its kind is known. NEVER raises — `list_active`
    serves every doc raw and one malformed doc must not 500 the GET."""
    try:
        if alert.get("armed") is not False:
            return None
        d = _direction_back(alert.get("kind"))
        if d is None:
            return None
        lbl = _et_day_label(alert.get("triggered_at"))
        px = _money(alert.get("triggered_price"))
        tail = f" — re-arms when price crosses back {d} the line"
        if lbl and px:
            return f"triggered {lbl} at {px}{tail}"
        if lbl:
            return f"triggered {lbl}{tail}"
        if px:
            return f"triggered at {px}{tail}"
        return f"triggered{tail}"
    except Exception:
        return None


def _transition(alert: dict, last: float, now: int,
                live: bool) -> tuple[str, dict]:
    """(action, $set patch) for one alert against one print. PURE — it never
    mutates `alert`. See the state table in the module docstring.

    `live` is True only when `last` came from a bulk_live_prices row. A
    fallback print (possibly a cached daily close) may fire or latch, but may
    never re-arm or arm a legacy doc."""
    armed = alert.get("armed")
    hit = _hit(alert, last)
    thr = _threshold(alert, last)
    lf = 0
    try:
        lf = int(alert.get("last_fired_at") or 0)
    except Exception:
        lf = 0

    if armed is None:                       # legacy doc, never evaluated
        if hit:
            if lf > 0:
                # Already fired for this crossing, before the latch existed.
                # triggered_price is None on purpose: lf is the LAST re-fire,
                # `last` is this run's print — two different moments.
                return "latch_legacy", {
                    "armed": False,
                    "triggered_at": lf,
                    "triggered_price": None,
                    "triggered_ref": thr,
                    "migrated_at": now,
                }
            return "fire", {
                "armed": False,
                "triggered_at": now,
                "triggered_price": float(last),
                "triggered_ref": thr,
            }
        if live:
            return "arm_legacy", {"armed": True, "rearmed_at": None,
                                  "migrated_at": now}
        return "noop", {}

    if armed is False:                      # latched
        if hit:
            return "hold", {}
        if live:
            return "rearm", {"armed": True, "rearmed_at": now}
        return "hold", {}

    if hit:                                 # armed
        return "fire", {
            "armed": False,
            "triggered_at": now,
            "triggered_price": float(last),
            "triggered_ref": thr,
        }
    return "noop", {}


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------
def check_alerts() -> dict:
    """Evaluate every active alert against the live last-trade price.

    ONE bulk_live_prices call per run; `last_trade_price` only for symbols the
    bulk call missed (and that print can never re-arm — see the module
    docstring). Fires once per crossing, still rate-limited per alert by
    ALERT_COOLDOWN_SEC. Returns counts."""
    db = _db()
    if db is None:
        return {"fired": 0, "checked": 0}

    fired: list[dict] = []
    checked = 0
    now = int(time.time())
    counters = {"latch_legacy": 0, "arm_legacy": 0, "rearm": 0,
                "hold": 0, "noop": 0}
    skipped_no_print = 0
    fallback_prints = 0

    # Group alerts by symbol so we only fetch each price once.
    alerts = list(db.price_alerts.find())
    by_sym: dict[str, list[dict]] = {}
    for a in alerts:
        sym = a.get("symbol")
        if sym:
            by_sym.setdefault(sym, []).append(a)

    try:
        snaps = prices.bulk_live_prices(sorted(by_sym)) or {}
    except Exception as exc:
        log.warning("price alerts: bulk_live_prices failed: %s", exc)
        snaps = {}

    for sym, group in by_sym.items():
        row = snaps.get(sym)
        if row is not None:
            # A row can exist with no print at all (closed day: only
            # prev_day_close). Never let a previous close stand in for a quote.
            last = _live_print(row)
            live = True
        else:
            last = prices.last_trade_price(sym)
            live = False
            fallback_prints += 1
        if not last:
            skipped_no_print += 1
            continue
        for a in group:
            checked += 1
            action, patch = _transition(a, last, now, live)
            if action == "fire":
                if now - int(a.get("last_fired_at") or 0) < ALERT_COOLDOWN_SEC:
                    continue
                msg = _format(a, last, row)
                channels = a.get("channels") or []
                sent_via: list[str] = []
                # 'push' is the new channel name; 'whatsapp' kept for legacy
                # alerts created before the migration. Both route to Web Push.
                if "push" in channels or "whatsapp" in channels:
                    # Route notification taps to /sepa/{ticker} so the user lands
                    # on that ticker's detail page from a phone push.
                    title_line = msg.split("\n", 1)[0][:80].lstrip("*").strip()
                    body_rest = msg.split("\n", 1)[1] if "\n" in msg else ""
                    if notify.send_alert(
                        title=f"🎯 {sym} · {title_line}" if title_line else f"🎯 {sym}",
                        body=body_rest or msg,
                        url=f"/sepa/{sym}",
                        kind="price_alert",
                        ticker=sym,
                        user_email=_target_email(a),
                    ):
                        sent_via.append("push")
                # "browser" is a passive channel — we record the fire and the UI
                # picks it up on its next /sepa/alerts/recent poll.
                if "browser" in channels:
                    sent_via.append("browser")

                db.price_alerts.update_one(
                    {"_id": a["_id"]},
                    {"$set": {**patch, "last_fired_at": now}})
                fire_doc = {
                    "alert_id": a["_id"],
                    "symbol": sym,
                    "kind": a["kind"],
                    "level": a["level"],
                    "price": float(last),
                    "fired_at": now,
                    "channels": sent_via,
                    "message": msg,
                }
                db.price_alert_fires.insert_one(fire_doc)
                fired.append(_strip_id(fire_doc))
                # Push the fire to every open tab via SSE so banners and
                # the in-page "recent fires" feed update without waiting
                # for the 30s poll cycle on the frontend.
                try:
                    from events import publish as _bus_publish
                    _bus_publish("alert.fired", {
                        "alert_id": str(a["_id"]),
                        "symbol":   sym,
                        "kind":     a["kind"],
                        "level":    a["level"],
                        "price":    float(last),
                        "fired_at": now,
                        "channels": sent_via,
                        "message":  msg,
                    })
                except Exception as exc:
                    log.debug("bus publish alert.fired failed: %s", exc)
            elif patch:
                db.price_alerts.update_one({"_id": a["_id"]}, {"$set": patch})
                counters[action] = counters.get(action, 0) + 1
            else:
                counters[action] = counters.get(action, 0) + 1

    log.info("price alerts: checked=%d fired=%d latched_legacy=%d armed_legacy=%d "
             "rearmed=%d held=%d skipped_no_print=%d fallback_prints=%d",
             checked, len(fired), counters["latch_legacy"], counters["arm_legacy"],
             counters["rearm"], counters["hold"], skipped_no_print, fallback_prints)
    return {
        "checked": checked,
        "fired": len(fired),
        "details": fired,
        "latched_legacy": counters["latch_legacy"],
        "armed_legacy": counters["arm_legacy"],
        "rearmed": counters["rearm"],
        "held": counters["hold"],
        "skipped_no_print": skipped_no_print,
        "fallback_prints": fallback_prints,
    }
