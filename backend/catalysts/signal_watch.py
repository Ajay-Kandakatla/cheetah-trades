"""Continuous buy/sell signal monitor on 15m and hourly bars.

Ajay 2026-08-29: "I need some chart analytics continuous monitor to give
me a buy sell signal like that" (after asking about GainzAlgo Alpha V2).

WHAT THIS IS AND IS NOT
───────────────────────
GainzAlgo's Pine source is protected and its accuracy figures are vendor
marketing, so this does not imitate their formula — nobody outside the
vendor can. It implements the architecture they describe (structure,
momentum, volatility, price action, adaptive filters, fixed SL/TP, no
repainting) out of components this app can verify, and then does the thing
a closed vendor indicator cannot: every signal is written to
`learning.observations` and resolved against real forward prices, so the
hit rate he trades on is measured from his own tape.

NO REPAINTING is a property here, not a claim: `mood`/`signal` read only
CLOSED bars, so a signal that fired at 10:15 still reads the same at 15:45.

WHAT IT WATCHES
───────────────
Names he already has a stake or an interest in — holdings first, then the
current demand-re-entry candidates. NOT the full universe: 1,700 intraday
fetches every ten minutes would be both slow and pointless, since a signal
on a name he will never trade is noise with a stop attached.

NOISE RULES (the same discipline as every other push here)
──────────────────────────────────────────────────────────
* Kind is ``pivot_alert`` — "price at a buy zone with a plan" is exactly
  what that kind means, and the standing 2026-06-24 keep-set gains NO new
  kinds.
* One push per (ticker, timeframe, action, ET day). A signal that is still
  true an hour later is the same signal, not a new one.
* Only BUY on names he does not hold, and SELL on names he does — a buy
  alert for something already in the book is not a decision he can act on,
  and a sell alert for something he does not own is noise.
* Outside 9:35-15:55 ET the module refuses to run.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("catalysts.signal_watch")

ET = ZoneInfo("America/New_York")
WATCH_TFS = ("15m", "60m")
MAX_NAMES = 40


def _now_et() -> datetime:
    return datetime.now(tz=ET)


def in_session(now: Optional[datetime] = None) -> bool:
    now = now or _now_et()
    if now.weekday() >= 5:
        return False
    hm = now.hour * 60 + now.minute
    return (9 * 60 + 35) <= hm <= (15 * 60 + 55)


def should_push(action: str, held: bool) -> tuple:
    """(fire, why) — a BUY on something he already owns is not a decision;
    a SELL on something he does not own is noise. PURE."""
    if action == "BUY":
        return (not held), ("already held" if held else "")
    if action == "SELL":
        return held, ("" if held else "not held")
    return False, "no signal"


def watchlist(owner: str, limit: int = MAX_NAMES) -> tuple:
    """(symbols, held_set). Holdings first, then demand-re-entry candidates."""
    held: set = set()
    syms: list = []
    try:
        from portfolio import store
        for h in store.list_holdings(owner):
            t = (h.get("ticker") or "").upper()
            if t:
                held.add(t)
                syms.append(t)
    except Exception as exc:
        log.warning("signal-watch: holdings read failed: %s", exc)
    try:
        from supply_demand import demand_reentry as dr
        # Cache read only — cached_or_warm never blocks the caller, so a cold
        # cache here yields holdings alone rather than a 3-minute stall.
        cached = dr.cached_or_warm("full", limit=limit)
        rows = (cached or {}).get("rows") or []
        for r in rows:
            t = (r.get("symbol") or "").upper()
            if t and t not in syms:
                syms.append(t)
            if len(syms) >= limit:
                break
    except Exception as exc:
        log.debug("signal-watch: candidate read failed: %s", exc)
    return syms[:limit], held


def _already_sent(db, ticker: str, tf: str, action: str, date_key: str) -> bool:
    return bool(db.signal_watch_state.find_one(
        {"ticker": ticker, "tf": tf, "action": action, "date_key": date_key}))


def _record_sent(db, ticker: str, tf: str, action: str, date_key: str,
                 payload: dict) -> None:
    db.signal_watch_state.update_one(
        {"ticker": ticker, "tf": tf, "action": action, "date_key": date_key},
        {"$set": {"payload": payload, "sent_at": _now_et().isoformat()}},
        upsert=True)


def check_once(*, push: bool = True, force: bool = False,
               symbols: Optional[list] = None) -> dict:
    """One pass. `force` skips the session gate for container smoke tests."""
    if not force and not in_session():
        return {"ran": False, "reason": "outside RTH"}

    from portfolio.alerts import _resolve_owner
    from portfolio.store import _get_db
    from supply_demand import mood as mood_mod
    from supply_demand import patterns as pat_mod
    from supply_demand import price_zones as pz_mod
    from supply_demand import timeframes as tf_mod

    owner = _resolve_owner()
    if symbols:
        names, held = [s.upper() for s in symbols], set()
    else:
        names, held = watchlist(owner)
    db = _get_db()
    date_key = _now_et().date().isoformat()
    fired, pushed, skipped = [], 0, 0

    for sym in names:
        for tf in WATCH_TFS:
            try:
                df, meta = tf_mod.frame_for(sym, tf)
                if df is None or len(df) < 30:
                    continue
                zones = pz_mod.compute(
                    df, swing_window=tf_mod.tf_spec(tf)["swing_window"],
                    lookback_bars=len(df))
                if not zones:
                    continue
                last = float(zones.get("last_price") or df["close"].iloc[-1])
                atr_value = pat_mod.atr(df)
                bands = [{"kind": z.get("kind"), "lo": z.get("lo"),
                          "hi": z.get("hi"), "source": "swing"}
                         for z in (list(zones.get("demand_zones") or [])
                                   + list(zones.get("supply_zones") or []))
                         if z.get("lo") and z.get("hi")]
                bands += pat_mod.fair_value_gaps(df, last)
                sig = mood_mod.signal(df, bands, last_price=last,
                                      atr_value=atr_value)
            except Exception as exc:
                log.warning("signal-watch: %s %s failed: %s", sym, tf, exc)
                continue

            if sig.get("action") == "WAIT":
                continue
            fire, why = should_push(sig["action"], sym in held)
            rec = {"symbol": sym, "tf": tf, "action": sig["action"],
                   "mood": sig.get("mood"), "trade": sig.get("trade"),
                   "held": sym in held, "suppressed": None if fire else why}
            fired.append(rec)
            if not fire:
                skipped += 1
                continue
            if not push or _already_sent(db, sym, tf, sig["action"], date_key):
                continue

            tr = sig.get("trade") or {}
            body = (f"{sym} {tf} · mood {sig.get('mood')} "
                    f"({sig.get('mood_label')})")
            if tr:
                body += (f" · entry {tr.get('entry')} stop {tr.get('stop')} "
                         f"{tr.get('rr')}R")
            try:
                from push import sender as _push
                _push.send_to_user(owner, {
                    "title": f"{'🟢 Buy' if sig['action'] == 'BUY' else '🔴 Sell'} signal",
                    "body": body,
                    "data": {"url": f"/chart-maps?tab=support&symbol={sym}&tf={tf}"},
                }, kind="pivot_alert")
                _record_sent(db, sym, tf, sig["action"], date_key, rec)
                pushed += 1
            except Exception as exc:
                log.warning("signal-watch: push for %s failed: %s", sym, exc)

            try:
                from learning import observations as obs
                import time
                obs.record_observation(
                    source=f"signal_watch:{tf}", ticker=sym,
                    ts=int(time.time()),
                    direction="up" if sig["action"] == "BUY" else "down",
                    baseline_price=last,
                    horizon_hours=6 if tf == "15m" else 24,
                    predicted_pct=float((sig.get("trade") or {}).get("rr") or 0))
            except Exception as exc:                        # pragma: no cover
                log.debug("signal-watch: ledger write failed: %s", exc)

    return {"ran": True, "date": date_key, "checked": len(names),
            "signals": fired, "pushed": pushed, "skipped": skipped}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    out = check_once()
    log.info("SIGNAL-WATCH: ran=%s checked=%s signals=%d pushed=%s",
             out.get("ran"), out.get("checked"),
             len(out.get("signals") or []), out.get("pushed"))
