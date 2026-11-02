"""🥇 Luk's — the A+ gate over gajjala.alerts' primitives (BUILD_SPEC §3.8, WP-A4, 2026-11-01; LIVE 2026-11-01).

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources." Ajay 2026-11-01 (the go-live): "Lets make it live. also alerts
too." — LC.LUK_PUSH_MODE = "live" since LC.LUK_LIVE_SINCE (HIS CALL #19 answered).

WHAT RINGS (live). Every A+ read of the pass (detectors.py `state == "aplus"`), in (entry bar, SETUPS order, symbol)
order, once per (ET trading day, symbol, setup): the claim `LUK:{date}|SYM|setup` (`gajjala.alerts.claim_key` with the
Luk variant) in `luk_alerts` — GG's live branch: the SHADOW: twin of the key on file → claimed_before (a key shadowed
before the flip never rings after it); claim "claimed" with `at` = the pass clock → the sender
(`gajjala.alerts._default_send(owner, payload, LUK)` → push.hooks.<LUK.send_setup> = notify_luk_setup, the ONE sender
path) → settled "pushed" / "no_target" / "failed". The owner = `gajjala.alerts._owner()` unless injected.

THE SHADOW FALLBACK. Any LUK_PUSH_MODE but exactly "live" (luk.variant.push_mode(), fail closed): the claim
`SHADOW:LUK:{date}|SYM|setup` with state "shadow", the payload it WOULD have sent (`would_push`) and
`gajjala.alerts.SHADOW_NOTE` — recorded, never sent.

THE GATES (unchanged by the go-live). Freshness = `gajjala.alerts.is_fresh(read, now, LUK)` —
`gajjala.alerts.max_entry_age_sec(LUK)` = the Luk variant's cadence (PASS_CADENCE_SEC) + BAR_SETTLE_SEC: a staler read
(a skipped pass, a bar served late) is "#late", and a repeat of a key already on file is "#claimed_before"; the house
closed-day gate (`gajjala.alerts._closed_reason`, GG's point) → "#suppressed_closed"; GG's first-15-minutes window is
NOT applied (Luk trades the first candle); an entry bar that STARTS before the regular open or closes after the regular
close (16:00; 13:00 on a half day — the house calendar) is "#suppressed_outside_rth" (MINE: his setups are
regular-session). A refusal is recorded under `{key}#{state}` and never consumes the day's claim.

The counters are `gajjala.alerts.COUNT_KEYS` exactly; "#suppressed_outside_rth" is counted under GG's
"suppressed_window" key (outside the session the gate admits). UNMEASURED: nothing here trades, sizes or enters a lane;
every body ends "his setup, not a buy signal".
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

from chart_maps.gajjala import alerts as GA
from chart_maps.gajjala import constants as GC
from daytrading.data import ET_RTH_OPEN

from . import constants as LC
from . import variant as VL
from .variant import LUK

log = logging.getLogger("chart_maps.luk.alerts")

SUPPRESSED_OUTSIDE_RTH = "suppressed_outside_rth"     # MINE: his setups are regular-session
OUTSIDE_RTH_COUNT_KEY = "suppressed_window"           # the COUNT_KEYS slot the refusal above is counted in
COUNT_KEYS = GA.COUNT_KEYS
SHADOW_NOTE = GA.SHADOW_NOTE
UNMEASURED_TAIL = GA.UNMEASURED_TAIL
SETUP_META = {k: (e, label) for k, e, label in LC.SUBS}
FRAME_TEXT = {"1m": "1-minute candle", "5m": "5-minute candle"}
# his entry, one clause per setup, in his words with the cite (VKNEJA5r8zw / lS9zbnLi1Gg = his two long interviews)
ENTRY_WORDS = {
    "pullback_reversal": ("first breakout of the previous bar high after the flush into the hourly 9/21 EMA "
                          "(VKNEJA5r8zw 1:56:39)"),
    "opening_range_high": "take-out of the first 1-minute candle high, stop at its low (lS9zbnLi1Gg 0:38:40)",
    "inside_day_pdh": "prior-day high after an inside day (lS9zbnLi1Gg 0:36:11)",
}


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
    """The payload one A+ carries (sent live; stored as `would_push` in shadow). Every number is the read's own."""
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


def run_pass(reads: dict, frames, now: datetime, session, *, store, send: Optional[Callable] = None,
             owner: Optional[str] = None, dry: bool = False, ctx: Optional[dict] = None,
             mode: Optional[str] = None) -> dict:
    """Ring (live) or record (shadow) every fresh, in-session A+ of this pass — each its own push. `reads` =
    {SYM: {setup: Read}}; `frames` is accepted for the gajjala.alerts shape and not read (the detector already judged
    freshness by its frame's rule); `ctx` = {SYM: {"price"}}; `store` = the LukStore (`alerts_coll()` → luk_alerts);
    `send(owner, payload)` defaults to `gajjala.alerts._default_send(…, LUK)`; `owner` defaults to
    `gajjala.alerts._owner()`; `mode` = "shadow" / "live" (anything else → luk.variant.push_mode()). `dry` → nothing
    claimed, recorded or sent (refusals counted, every ringable A+ counted "dry"). -> counts (COUNT_KEYS)."""
    from supply_demand.demand_alerts import claim_key as _claim
    mode = mode if mode in GC.PUSH_MODES else VL.push_mode()
    if send is None:
        send = lambda o, p: GA._default_send(o, p, LUK)          # noqa: E731 — the ONE sender path (LUK.send_setup)
    ctx = ctx or {}
    coll = store.alerts_coll() if store is not None else None
    counts = {k: 0 for k in COUNT_KEYS}
    counts["shadow_mode"] = 1 if mode == "shadow" else 0
    session_iso = GA._session_iso(session)
    closed = GA._closed_reason(now)
    for entry_t, _o, sym, setup, r in _candidates(reads):
        counts["aplus"] += 1
        key = GA.claim_key(session, sym, setup, LUK)
        sk = GA.shadow_key(session, sym, setup, LUK)
        c = ctx.get(sym) or {}
        frame = r.get("frame") or LUK.primary
        base = {"date": session_iso, "symbol": sym, "setup": setup, "mode": mode, "entry_bar_t": entry_t,
                "frame": frame, "trigger": r.get("trigger"), "stop": r.get("stop"), "risk_pct": r.get("risk_pct"),
                "r_usd": r.get("r_usd"), "stop_src": r.get("stop_src"), "price": c.get("price"),
                "kind": LUK.push_kind_setup}
        if not GA.is_fresh(r, now, LUK):
            state = "claimed_before" if (GA._exists(coll, sk) or GA._exists(coll, key)) else "late"
        elif closed:
            state = "suppressed_closed"
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
        if mode == "shadow":
            if not _claim(coll, sk, dict(base, state="shadow", would_push=payload, note=SHADOW_NOTE,
                                        at=now.isoformat())):
                counts["claimed_before"] += 1
                continue
            counts["shadow"] += 1                               # the sender is NEVER called in shadow
            continue
        if GA._exists(coll, sk) or not _claim(coll, key, dict(base, state="claimed", at=now.isoformat())):
            counts["claimed_before"] += 1
            continue
        try:
            res = send(owner or GA._owner(), payload) or {}
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk alerts: send failed for %s %s: %s", sym, setup, type(exc).__name__)
            counts["failed"] += 1
            GA._settle(coll, key, {"state": "failed", "result": {"error": type(exc).__name__}})
            continue
        sent, targets = int(res.get("sent") or 0), int(res.get("total_targets") or 0)
        st = "pushed" if sent > 0 else ("no_target" if targets == 0 else "failed")
        counts[st] += 1
        GA._settle(coll, key, {"state": st, "result": {k: res.get(k) for k in ("sent", "failed", "total_targets",
                                                                            "skipped")}})
    counts["shadow_session"] = GA.shadow_session_count(coll, session) if mode == "shadow" and not dry else 0
    return counts


__all__ = ["SUPPRESSED_OUTSIDE_RTH", "OUTSIDE_RTH_COUNT_KEY", "COUNT_KEYS", "SHADOW_NOTE", "ENTRY_WORDS",
           "outside_rth", "compose", "run_pass"]
