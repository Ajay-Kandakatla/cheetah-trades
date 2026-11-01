"""🥇 Luk's — the SHADOW gate over gajjala.alerts' primitives (BUILD_SPEC §3.8, WP-A4, 2026-11-01).

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources."

WHAT IS RECORDED. Every A+ read of the pass (detectors.py `state == "aplus"`), in (entry bar, SETUPS order, symbol)
order, once per (ET trading day, symbol, setup): the claim `LUK:{date}|SYM|setup` under the house SHADOW prefix
(`gajjala.alerts.shadow_key` with the Luk variant), stored in `luk_alerts` with state "shadow", the payload it WOULD
have sent (`would_push`) and `gajjala.alerts.SHADOW_NOTE`. Nothing is ever sent: there is no push kind, no sender and
no live branch — `refuse_send` is the only send-shaped function here and it raises NEVER_SENDS (HIS CALL #19).

THE CLOCK. Freshness = `gajjala.alerts.is_fresh(read, now, LUK)` — the Luk variant's cadence (PASS_CADENCE_SEC) +
BAR_SETTLE_SEC = 330 s ([fixed: C1]): a 1-minute A+ read up to 5 minutes after its bar closed is recorded; a staler
one (a skipped pass) is "#late", and a repeat of a key already on file is "#claimed_before". GG's first-15-minutes
window is NOT applied (Luk trades the first candle); an entry bar that STARTS before the regular open or closes after
the regular close (16:00; 13:00 on a half day — the house calendar) is "#suppressed_outside_rth" (MINE: his setups
are regular-session). A refusal is recorded under `{key}#{state}` and never consumes the day's claim.

The counters are `gajjala.alerts.COUNT_KEYS` exactly; "#suppressed_outside_rth" is counted under GG's
"suppressed_window" key (outside the session the gate admits). UNMEASURED: nothing here trades, sizes or enters a lane.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from chart_maps.gajjala import alerts as GA
from daytrading.data import ET_RTH_OPEN

from . import constants as LC
from .variant import LUK

log = logging.getLogger("chart_maps.luk.alerts")

NEVER_SENDS = ("🥇 Luk's never sends: LUK_PUSH_MODE is shadow, no push kind is registered, no sender exists, the "
               "owner keep-set is unchanged (HIS CALL #19)")
SUPPRESSED_OUTSIDE_RTH = "suppressed_outside_rth"     # MINE: his setups are regular-session
OUTSIDE_RTH_COUNT_KEY = "suppressed_window"           # the COUNT_KEYS slot the refusal above is counted in
COUNT_KEYS = GA.COUNT_KEYS
SHADOW_NOTE = GA.SHADOW_NOTE
UNMEASURED_TAIL = GA.UNMEASURED_TAIL
MODE = "shadow"
SETUP_META = {k: (e, label) for k, e, label in LC.SUBS}
FRAME_TEXT = {"1m": "1-minute candle", "5m": "5-minute candle"}
# his entry, one clause per setup, in his words with the cite (VKNEJA5r8zw / lS9zbnLi1Gg = his two long interviews)
ENTRY_WORDS = {
    "pullback_reversal": ("first breakout of the previous bar high after the flush into the hourly 9/21 EMA "
                          "(VKNEJA5r8zw 1:56:39)"),
    "opening_range_high": "take-out of the first 1-minute candle high, stop at its low (lS9zbnLi1Gg 0:38:40)",
    "inside_day_pdh": "prior-day high after an inside day (lS9zbnLi1Gg 0:36:11)",
}


def refuse_send(owner, payload):
    """The only send-shaped function of the package: it refuses. run_pass never calls it (there is nothing to call)."""
    raise RuntimeError(NEVER_SENDS)


def _num(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def outside_rth(bar_t_et, session, frame: str) -> bool:
    """The entry bar STARTED before the regular open (label − its frame length < 09:30 ET) or CLOSED after the regular
    close (16:00; 13:00 on a half day — gajjala.alerts._closes, the house calendar). An unreadable stamp → True."""
    label = GA.bar_close_et(bar_t_et)
    if label is None:
        return True
    rth_open = datetime.combine(label.date(), ET_RTH_OPEN, tzinfo=GA.ET)
    rth_close_t, _ah = GA._closes(session)
    rth_close = datetime.combine(label.date(), rth_close_t, tzinfo=GA.ET)
    start = label - timedelta(minutes=GA.FRAME_MINUTES.get(frame, GA.FRAME_MINUTES["5m"]))
    return start < rth_open or label > rth_close


def compose(read: dict, sym: str, ctx: Optional[dict] = None, *, session=None) -> dict:
    """The payload one A+ WOULD carry (stored as `would_push`; never sent). Every number is the read's own."""
    read = read or {}
    sym = (sym or "").upper()
    setup = read.get("setup") or ""
    _emoji, label = SETUP_META.get(setup, ("🥇", setup))
    frame = read.get("frame") or LUK.primary
    facts = read.get("facts") if isinstance(read.get("facts"), dict) else {}
    frame_text = facts.get("frame_text") or FRAME_TEXT.get(frame, frame)
    close = GA.bar_close_et(read.get("entry_bar_t"))
    hhmm = close.strftime("%H:%M") if close else "—"
    risk = _num(read.get("risk_pct"))
    r_usd = _num(read.get("r_usd"))
    stop_bit = f"stop {GA._px(read.get('stop'))}" + (f" (−{risk:.1f}%)" if risk is not None else "")
    r_bit = f"R ${r_usd:.2f}" if r_usd is not None else ""
    words = ENTRY_WORDS.get(setup, "")
    broke = f"broke {GA._px(read.get('trigger'))} on the {frame_text} closing {hhmm} ET"
    body = " · ".join(b for b in (broke, stop_bit, r_bit, words, UNMEASURED_TAIL) if b)
    line = " · ".join(b for b in (f"{sym} · {label} A+ entry", f"broke {GA._px(read.get('trigger'))}", stop_bit)
                      if b)
    return {"title": f"🥇 {sym} · {label} A+ entry", "body": body, "tag": f"luk-{setup}-{sym}",
            "url": f"/chart-maps?tab={LUK.tab}&sub={setup}&focus={sym}", "kind": LUK.push_kind_setup,
            "ticker": sym, "items": [{"symbol": sym, "text": line}]}


def _candidates(reads: dict) -> list:
    """Every A+ of the pass: (entry bar, SETUPS order, symbol, setup, read)."""
    order = {s: i for i, s in enumerate(LC.SETUPS)}
    out = []
    for sym, by_setup in (reads or {}).items():
        for setup, r in (by_setup or {}).items():
            if isinstance(r, dict) and r.get("state") == "aplus":
                out.append((str(r.get("entry_bar_t") or ""), order.get(setup, len(order)), str(sym).upper(), setup,
                            dict(r, setup=r.get("setup") or setup)))
    out.sort(key=lambda x: x[:4])
    return out


def run_pass(reads: dict, frames, now: datetime, session, *, store, dry: bool = False,
             ctx: Optional[dict] = None) -> dict:
    """Record (never send) every fresh, in-session A+ of this pass. `reads` = {SYM: {setup: Read}}; `frames` is
    accepted for the gajjala.alerts shape and not read (the detector already judged freshness by its frame's rule);
    `ctx` = {SYM: {"price"}}; `store` = the LukStore (`alerts_coll()` → luk_alerts). `dry` → nothing recorded
    (refusals counted, every recordable A+ counted "dry"). -> counts (gajjala.alerts.COUNT_KEYS)."""
    from supply_demand.demand_alerts import claim_key as _claim
    ctx = ctx or {}
    coll = store.alerts_coll() if store is not None else None
    counts = {k: 0 for k in COUNT_KEYS}
    counts["shadow_mode"] = 1
    session_iso = GA._session_iso(session)
    for entry_t, _o, sym, setup, r in _candidates(reads):
        counts["aplus"] += 1
        key = GA.claim_key(session, sym, setup, LUK)
        sk = GA.shadow_key(session, sym, setup, LUK)
        c = ctx.get(sym) or {}
        frame = r.get("frame") or LUK.primary
        base = {"date": session_iso, "symbol": sym, "setup": setup, "mode": MODE, "entry_bar_t": entry_t,
                "frame": frame, "trigger": r.get("trigger"), "stop": r.get("stop"), "risk_pct": r.get("risk_pct"),
                "r_usd": r.get("r_usd"), "stop_src": r.get("stop_src"), "price": c.get("price"),
                "kind": LUK.push_kind_setup}
        if not GA.is_fresh(r, now, LUK):
            state = "claimed_before" if (GA._exists(coll, sk) or GA._exists(coll, key)) else "late"
        elif outside_rth(entry_t, session, frame):
            state = SUPPRESSED_OUTSIDE_RTH
        else:
            state = None
        if state == "claimed_before":
            counts[state] += 1
            continue
        if state:
            counts[OUTSIDE_RTH_COUNT_KEY if state == SUPPRESSED_OUTSIDE_RTH else state] += 1
            if not dry:
                GA._record(coll, f"{key}#{state}", dict(base, state=state, at=now.isoformat()))
            continue
        if dry:
            counts["dry"] += 1
            continue
        payload = compose(r, sym, c, session=session)
        if not _claim(coll, sk, dict(base, state="shadow", would_push=payload, note=SHADOW_NOTE,
                                    at=now.isoformat())):
            counts["claimed_before"] += 1
            continue
        counts["shadow"] += 1                                   # no sender exists: a shadow row is the whole effect
    counts["shadow_session"] = GA.shadow_session_count(coll, session) if not dry else 0
    return counts


__all__ = ["NEVER_SENDS", "SUPPRESSED_OUTSIDE_RTH", "OUTSIDE_RTH_COUNT_KEY", "COUNT_KEYS", "SHADOW_NOTE",
           "ENTRY_WORDS", "refuse_send", "outside_rth", "compose", "run_pass"]
