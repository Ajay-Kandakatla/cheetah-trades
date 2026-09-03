"""Zone-bounce alerts — a $1B+ name touched a demand level intraday and is
already bouncing off it.

Ajay 2026-09-03: "NTAP did hit the demand zone in the morning and bounced
back immediately 20 point I am looking for those."

The NTAP morning (verified 1-min forensics, 2026-09-03)
-------------------------------------------------------
prev close 180.77 · pre-market 158.23-168.27 · 09:30 open 161.95 (-10.4%
gap), day low 161.00 in the first minute · 09:33 close 171.2 · 09:42 178.38
· 09:57 >= 181 · 11:49 high 187.45 (+26.45, +16.4% off the low).

The engine had NO demand band at 161 (nearest demand tops 157.2 / 158.99).
What the low hit was a BROKEN-SUPPLY shelf — board geometry supply band
161.78-167.54, one touch, strength 18: the open printed inside it, the low
undercut its floor by 0.48%, then price reclaimed it and the next shelf
(173.87-180.07) inside twelve minutes. Old resistance acting as support —
the S/R flip — MUST count, and every band involved had touches=1 and
strength 15-24, which the demand board (MIN_TOUCHES=2, MIN_ZONE_STRENGTH=40,
demand only, scores the close) and today's demand_alerts pass are
structurally blind to. Hence: every band, both kinds, from zone_store.

The rule (pure: ``read``)
-------------------------
For each band drawn BEFORE today (zone_store, board geometry):

  eligible  demand bands, plus supply bands whose top is BELOW yesterday's
            close (broken supply = support). A supply band still overhead is
            resistance, not a level to bounce off.
  TOUCH     day_low <= hi * (1 + TOUCH_TOL_PCT%)    a wick that stopped just
            AND day_low >= lo * (1 - WICK_PCT%)      short, or undercut a
                                                     little (NTAP: -0.48%).
  ARRIVAL   prev_close > hi * (1 + ARRIVAL_PCT%)    yesterday was OUTSIDE.
            A name that closed in/near the band yesterday is residence, not
            an arrival — the demand board's business, never this phone kind.
  BOUNCE    print > hi  AND  print >= day_low * (1 + max(BOUNCE_MIN_PCT,
            ATR14/day_low)%). Above the band again AND a real move off the
            low, scaled by the name's own volatility. A gap-through that
            keeps falling never fires (print <= hi).
  STRONG    bounce_pct >= max(STRONG_PCT, 2 * ATR14/day_low)  -> its own push.

Everything else fresh in a pass goes into ONE digest (trade_flash
discipline: five names in one poll is one notification). At most
MAX_SINGLES_PER_PASS individual pushes per pass, strongest first.

Data: sepa.prices.bulk_snapshot DIRECTLY — it carries the day LOW, the last
trade and its timestamp (bulk_live_prices drops the low). The print is the
last trade only while it is within STALE_PRINT_SEC of now; otherwise the
bounce leg is SKIPPED for that name (2026-09-03: Massive aggregates lagged
~3h after 13:13 ET — a stale print is not a bounce, it is an old price).

Cap gate: catalysts.promo_circuit.market_caps_for + demand_alerts.passes_cap
— unknown cap is skipped and counted. Dedupe once per (symbol, band, ET
day); state written only on a terminal send (delivered, or nobody
targeted). Kind = ``zone_bounce_alert`` (Ajay asked for these explicitly,
2026-09-03; separately mutable at /notifications).

Configured price-structure heuristic, S/D scope, NOT a book method, no
Minervini cites. Decision support, not a buy signal, not advice.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, time as dtime
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
KIND = "zone_bounce_alert"
STATE_COLL = "zone_bounce_state"

# Thresholds — configured house values (Ajay 2026-09-03, the NTAP morning):
TOUCH_TOL_PCT = 1.0        # low within 1% above the top still counts as a touch
WICK_PCT = 1.5             # low may undercut the floor this much (NTAP: 0.48%)
ARRIVAL_PCT = 3.0          # prev close must be > 3% above the top: arrivals only
BOUNCE_MIN_PCT = 3.0       # floor on the move off the low (raised by ATR)
STRONG_PCT = 5.0           # floor for an individual push (raised by 2x ATR)
STALE_PRINT_SEC = 600      # a last trade older than 10 min is not "now"
MIN_CAP_USD = 1_000_000_000.0
MAX_SINGLES_PER_PASS = 3   # strongest first; the rest ride the digest
DIGEST_MAX = 6             # names spelled out in one digest body
SESSION_OPEN = dtime(9, 33)   # first pass after the 9:30 open + first prints
SESSION_CLOSE = dtime(16, 0)


def _now_et() -> datetime:
    return datetime.now(ET)


def in_session(now: Optional[datetime] = None) -> bool:
    """RTH weekdays 9:33-16:00 ET."""
    now = now or _now_et()
    if now.weekday() >= 5:
        return False
    return SESSION_OPEN <= now.time() <= SESSION_CLOSE


# --------------------------------------------------------------------------
# Pure reads
# --------------------------------------------------------------------------
def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None          # NaN guard


def is_eligible(band: dict, prev_close: float) -> bool:
    """Demand bands always; supply bands only once BROKEN (top below
    yesterday's close). Garbage bands are never eligible."""
    lo, hi = _f(band.get("lo")), _f(band.get("hi"))
    if lo is None or hi is None or lo <= 0 or lo > hi:
        return False
    kind = str(band.get("kind") or "demand").lower()
    if kind == "supply":
        pc = _f(prev_close)
        return pc is not None and hi < pc
    return True


def read(day_low, print_px, prev_close, band: dict, atr14,
         touch_tol_pct: float = TOUCH_TOL_PCT, wick_pct: float = WICK_PCT,
         arrival_pct: float = ARRIVAL_PCT, bounce_min_pct: float = BOUNCE_MIN_PCT,
         strong_pct: float = STRONG_PCT) -> Optional[dict]:
    """Touched this band today and bouncing off it? None = nothing to say.

    {"bounce_pct", "floor_pct", "strong", "strong_pct", "undercut_pct", "atr_x"}
    """
    low, px, pc = _f(day_low), _f(print_px), _f(prev_close)
    if low is None or px is None or pc is None or low <= 0 or px <= 0 or pc <= 0:
        return None
    if not is_eligible(band, pc):
        return None
    lo, hi = float(band["lo"]), float(band["hi"])
    if not (low <= hi * (1 + touch_tol_pct / 100.0) and low >= lo * (1 - wick_pct / 100.0)):
        return None                                   # never reached it / fell through
    if not pc > hi * (1 + arrival_pct / 100.0):
        return None                                   # residence, not an arrival
    if px <= hi:
        return None                                   # still in / under the band
    a = _f(atr14) or 0.0
    atr_pct = 100.0 * a / low
    floor = max(bounce_min_pct, atr_pct)
    bounce_pct = (px / low - 1.0) * 100.0
    if bounce_pct < floor:
        return None
    strong_floor = max(strong_pct, 2.0 * atr_pct)
    return {"bounce_pct": round(bounce_pct, 2), "floor_pct": round(floor, 2),
            "strong": bounce_pct >= strong_floor, "strong_pct": round(strong_floor, 2),
            "undercut_pct": round(max(0.0, (lo - low) / lo * 100.0), 2),
            "atr_x": round((px - low) / a, 1) if a > 0 else None}


def print_from_snapshot(snap: dict, now_ts: float, stale_sec: float = STALE_PRINT_SEC):
    """(print, stale). The last trade when its stamp is within `stale_sec`
    of now; (None, True) otherwise. Massive stamps lastTrade.t in ns, older
    payloads in ms — both are normalised to seconds."""
    px, ts = _f(snap.get("last_trade_price")), _f(snap.get("last_trade_ts_ms"))
    if px is None or px <= 0 or ts is None or ts <= 0:
        return None, True
    if ts > 1e15:
        ts /= 1e9                                     # ns
    elif ts > 1e11:
        ts /= 1e3                                     # ms
    if now_ts - ts > stale_sec:
        return None, True
    return px, False


def state_key(symbol: str, band: dict, day: str) -> str:
    return f"{symbol}:{float(band['lo']):g}-{float(band['hi']):g}:{day}"


def _band_txt(band: dict) -> str:
    return f"${float(band['lo']):g}-{float(band['hi']):g}"


def _band_role(band: dict) -> str:
    tested = f"tested {int(band.get('touches') or 0)}x" if band.get("touches") else "untested"
    if str(band.get("kind") or "").lower() == "supply":
        return f"broken supply -> support ({tested})"
    return f"demand ({tested})"


def single_message(item: dict) -> dict:
    """'🪃 NTAP bounced +6.3% off demand $161.78-167.54'"""
    from supply_demand.demand_alerts import fmt_cap
    sym, hit, band = item["symbol"], item["hit"], item["band"]
    px, low = float(item["print"]), float(item["day_low"])
    level = ("support (old resistance)" if str(band.get("kind") or "").lower() == "supply"
             else "demand")
    title = f"🪃 {sym} bounced +{hit['bounce_pct']:.1f}% off {level} {_band_txt(band)}"
    parts = [f"${px:g} · low ${low:g} -> +${px - low:.1f}",
             " | ".join(_band_role(b) for b in item["bands"])]
    if hit.get("atr_x") is not None:
        parts.append(f"{hit['atr_x']:g}x ATR")
    parts.append(fmt_cap(item.get("cap")))
    if item.get("name"):
        parts.append(str(item["name"]))
    url = f"/sepa/{sym}?tab=supply"
    return {"title": title, "body": " · ".join(parts), "url": url,
            "data": {"url": url}, "kind": KIND}


def digest_message(items: list) -> dict:
    """'🪃 Bouncing off demand - NTAP +6.3% +4 more' — strongest first."""
    from supply_demand.demand_alerts import fmt_cap
    if not items:
        return None
    items = sorted(items, key=lambda it: -it["hit"]["bounce_pct"])
    lead = items[0]
    title = f"🪃 Bouncing off demand levels — {lead['symbol']} +{lead['hit']['bounce_pct']:.1f}%"
    if len(items) > 1:
        title += f" +{len(items) - 1} more"
    lines = []
    for it in items[:DIGEST_MAX]:
        role = "broken supply" if str(it["band"].get("kind") or "").lower() == "supply" else "demand"
        lines.append(f"{it['symbol']} ${float(it['print']):g} · +{it['hit']['bounce_pct']:.1f}% "
                     f"off {_band_txt(it['band'])} ({role}) · {fmt_cap(it.get('cap'))}")
    if len(items) > DIGEST_MAX:
        lines.append(f"+{len(items) - DIGEST_MAX} more")
    url = "/chart-maps?tab=zones"
    return {"title": title, "body": "\n".join(lines), "url": url,
            "data": {"url": url}, "kind": KIND}


# --------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------
def _state_coll():
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[STATE_COLL] if db is not None else None
    except Exception as exc:
        log.warning("zone_bounce_alerts: no mongo for dedupe: %s", exc)
        return None


def _state(coll, key: str) -> Optional[dict]:
    """The recorded state doc for (symbol, band, day), or None when unseen."""
    if coll is None:
        return None
    try:
        return coll.find_one({"_id": key})
    except Exception as exc:
        log.warning("zone_bounce_alerts: dedupe read failed: %s", exc)
        return None


def _already(coll, key: str) -> bool:
    return _state(coll, key) is not None


def _upgradable(doc: Optional[dict], hit: dict) -> bool:
    """Seen today as a digest item (not strong) and now STRONG → one more push,
    as a single. NTAP 2026-09-03: +6.3% at 09:33 (digest tier, ATR floor
    8.6%), +10.8% by 09:42 — the second leg is the one he means by 'bounced
    back immediately 20 point', so the day's one digest line must not eat it.
    A strong-recorded band never fires again that day."""
    return bool(doc) and not doc.get("strong") and bool(hit.get("strong"))


def _record(coll, item: dict, now: datetime) -> None:
    if coll is None:
        return
    for key, band in zip(item["keys"], item["bands"]):
        try:
            coll.update_one({"_id": key}, {"$set": {
                "symbol": item["symbol"], "band": {"lo": band["lo"], "hi": band["hi"],
                                                   "kind": band.get("kind")},
                "print": item["print"], "day_low": item["day_low"],
                "bounce_pct": item["hit"]["bounce_pct"], "strong": item["hit"]["strong"],
                "cap": item.get("cap"), "sent_at": now.isoformat()}}, upsert=True)
        except Exception as exc:
            log.warning("zone_bounce_alerts: dedupe write failed: %s", exc)


def _terminal(res: Optional[dict]) -> bool:
    """Delivered, or nobody targeted (muted pref / no device) — both mean
    'do not retry today'. A transport failure is retried next pass."""
    res = res or {}
    return (res.get("sent") or 0) > 0 or (res.get("total_targets") or 0) == 0


def _band_rank(band: dict, day_low: float) -> tuple:
    """The band the low actually sat in first, then the more-tested one."""
    lo, hi = float(band["lo"]), float(band["hi"])
    dist = 0.0 if lo <= day_low <= hi else min(abs(day_low - lo), abs(day_low - hi))
    return (dist, -(band.get("touches") or 0))


def check_once(*, push: bool = True, force: bool = False, store: Optional[dict] = None,
               snapshot: Optional[dict] = None, caps: Optional[dict] = None,
               names: Optional[dict] = None, coll=None, owner: Optional[str] = None,
               now: Optional[datetime] = None) -> dict:
    """One 5-min pass. Every input is injectable for tests; the cron passes
    none. `force` skips the session gate for in-container smoke tests only."""
    now = now or _now_et()
    if not force and not in_session(now):
        return {"ran": False, "reason": "outside RTH"}
    day = now.astimezone(ET).date()
    if store is None:
        from supply_demand import zone_store
        store = zone_store.load(None, day)
    if not store:
        return {"ran": True, "reason": "zone store empty for today", "candidates": 0,
                "hits": [], "singles": 0, "digest": 0, "pushed": 0}
    syms = sorted(store)
    if snapshot is None:
        try:
            from sepa import prices
            snapshot = prices.bulk_snapshot(syms) or {}
        except Exception as exc:
            log.warning("zone_bounce_alerts: snapshot failed: %s", exc)
            return {"ran": False, "reason": f"snapshot failed: {exc}"}
    if not snapshot:
        log.warning("zone_bounce_alerts: snapshot returned nothing for %d stored names "
                    "(key missing or every chunk failed) — a quiet pass, not a quiet day",
                    len(syms))
    now_ts = now.timestamp()
    prints: dict = {}
    stale_print = 0
    for s in syms:
        snap = snapshot.get(s)
        if not snap:
            continue
        px, stale = print_from_snapshot(snap, now_ts)
        if stale:
            stale_print += 1
            continue
        prints[s] = px
    if caps is None:
        try:
            from catalysts.promo_circuit import market_caps_for
            caps = market_caps_for(list(prints), prints) or {}
        except Exception as exc:
            log.warning("zone_bounce_alerts: market caps failed: %s", exc)
            caps = {}
    if coll is None:
        coll = _state_coll()
    day_iso = day.isoformat()
    hits, items = [], []
    unknown_prev = unknown_cap = skipped_cap = 0
    for sym in syms:
        px = prints.get(sym)
        if px is None:
            continue
        doc, snap = store[sym], snapshot.get(sym) or {}
        low = _f(snap.get("low"))
        prev = _f(snap.get("prev_day_close")) or _f(doc.get("prev_close"))
        if low is None or low <= 0:
            continue
        if not prev:
            unknown_prev += 1
            continue
        atr14 = doc.get("atr14")
        touched = []
        for band in doc.get("bands") or []:
            hit = read(low, px, prev, band, atr14)
            if hit:
                touched.append((band, hit))
        if not touched:
            continue
        touched.sort(key=lambda bh: _band_rank(bh[0], low))
        cap = caps.get(sym)
        item = {"symbol": sym, "print": float(px), "day_low": low, "prev_close": prev,
                "atr14": atr14, "band": touched[0][0], "hit": touched[0][1],
                "bands": [b for b, _ in touched], "cap": cap, "name": None}
        hits.append(item)
        from supply_demand.demand_alerts import passes_cap
        if not passes_cap(cap, MIN_CAP_USD):
            if cap is None:
                unknown_cap += 1
            else:
                skipped_cap += 1
            continue
        fresh, upgrades = [], []
        for b, h in touched:
            doc_state = _state(coll, state_key(sym, b, day_iso))
            if doc_state is None:
                fresh.append((b, h))
            elif _upgradable(doc_state, h):
                upgrades.append((b, h))
        if not fresh and not upgrades:
            continue
        chosen = fresh or upgrades
        item = dict(item, band=chosen[0][0], hit=chosen[0][1], bands=[b for b, _ in chosen],
                    keys=[state_key(sym, b, day_iso) for b, _ in chosen],
                    upgrade=not fresh)
        if names is not None:
            item["name"] = names.get(sym)
        else:
            try:
                from sepa import company_names
                item["name"] = company_names.name_for(sym)
            except Exception:
                item["name"] = None
        items.append(item)
    strong = sorted((it for it in items if it["hit"]["strong"]),
                    key=lambda it: -it["hit"]["bounce_pct"])
    singles = strong[:MAX_SINGLES_PER_PASS]
    # An upgrade rides ONLY as a single: it was already in a digest today. If
    # the singles slots are full it waits for the next pass (state unchanged).
    digest = [it for it in items if it not in singles and not it.get("upgrade")]
    pushed = 0
    if push and (singles or digest):
        from push import sender
        if owner is None:
            from portfolio.alerts import _resolve_owner
            owner = _resolve_owner()
        for it in singles:
            try:
                res = sender.send_to_user(owner, single_message(it), kind=KIND)
            except Exception as exc:
                log.warning("zone_bounce_alerts: push for %s failed: %s", it["symbol"], exc)
                continue
            if _terminal(res):
                _record(coll, it, now)
                pushed += 1
        if digest:
            try:
                res = sender.send_to_user(owner, digest_message(digest), kind=KIND)
            except Exception as exc:
                log.warning("zone_bounce_alerts: digest push failed: %s", exc)
                res = None
            if _terminal(res):
                for it in digest:
                    _record(coll, it, now)
                pushed += 1
    return {"ran": True, "date": day_iso, "candidates": len(syms), "priced": len(prints),
            "stale_print": stale_print, "hits": hits, "singles": len(singles),
            "digest": len(digest), "pushed": pushed, "skipped_cap": skipped_cap,
            "unknown_cap": unknown_cap, "unknown_prev": unknown_prev}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    t0 = time.time()
    out = check_once()
    log.info("ZONE-BOUNCE: ran=%s candidates=%s priced=%s stale_print=%s hits=%d "
             "singles=%s digest=%s pushed=%s skipped_cap=%s unknown_cap=%s "
             "unknown_prev=%s seconds=%.1f", out.get("ran"), out.get("candidates"),
             out.get("priced"), out.get("stale_print"), len(out.get("hits") or []),
             out.get("singles"), out.get("digest"), out.get("pushed"),
             out.get("skipped_cap"), out.get("unknown_cap"), out.get("unknown_prev"),
             time.time() - t0)
