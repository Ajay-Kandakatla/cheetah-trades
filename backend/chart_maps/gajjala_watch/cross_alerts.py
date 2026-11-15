"""👀 Gajjala's Watch — the 1-minute 9-over-21 EMA cross push (spec 2026-11-15 §3.6, WP-B).

Ajay, verbatim (2026-11-15): "from the videos I notice that when ever 9 EMA crosses over 21 EMA on uptrend is where the
bullish momentum started I need alerts on these from 1 min to I can be ready... I think the cross over is slow but once
it picks up its very rapid.."

WHICH CROSS. `watch_crosses(F)` = the ONE engine's `ema_cross.frame_crosses(F)` minus today's FIRST bar (it has no prior
bar on the chart, so the chart never marks it — [C1.5]: the chart, the push and the count script agree). The LATEST up
cross of the session, on its own minute only: the cross bar is the frame's latest closed bar AND fresh
(`alerts.is_fresh` on the 1-minute page's clock, V.GG1: one cadence + BAR_SETTLE_SEC = 90 s).

GATE ORDER (the ➖ fade-cross template, `alerts.run_fade_cross`): not a push frame (C.PUSH_FRAMES ∩
alerts.FRAME_MINUTES — fail closed, drawn only) · mode off · not its own minute (claimed_before / missed_fetch / late —
a cross missed by a failed / skipped / slept minute is counted `missed_fetch` and NEVER sent late) · closed day · the
A+ push window (`alerts.window_reason`) · GG's session-volume floor (GC.K11_MIN_SESSION_VOLUME on
`bars.session_volume`; unknown → held) · the trend filter (C.UPTREND_FILTER; default None = no filter, K5 recorded) ·
dry · no alert store (never a claim-less send) · the insert-only claim (`demand_alerts.claim_key`, BEFORE the send;
`GGW:` ids in `gajjala_watch_alerts` only) · the send (owner-scoped, C.PUSH_KIND = the 🧠 kind) → `alerts._settle`.

A down cross never rings (it is drawn). 3- and 5-minute crosses are drawn only. Every body ends UNMEASURED; never "buy".
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Callable, Optional

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ema_cross as EX
from chart_maps.gajjala import variant as V
from daytrading.data import ET_RTH_OPEN

from . import build as BLD
from . import constants as C

log = logging.getLogger("chart_maps.gajjala_watch.cross_alerts")

COUNT_KEYS = ("names", "cross", "pushed", "dry", "off", "not_push_frame", "not_uptrend", "claimed_before", "late",
              "missed_fetch", "suppressed_closed", "suppressed_premarket", "suppressed_first15", "suppressed_window",
              "under_floor", "no_store", "no_target", "failed")
PUSHED = "pushed"                                       # the held verdict of a cross that rang (never a chip)
MARK = {True: "✓", False: "✗", None: "—"}


def mode() -> str:
    """C.PUSH_MODE when it is one of C.PUSH_MODES, else "off" (fail closed). Read at CALL time."""
    m = C.PUSH_MODE
    return m if isinstance(m, str) and m in C.PUSH_MODES else C.PUSH_MODES[0]


def _iso(session) -> str:
    return session.isoformat()[:10] if isinstance(session, (date, datetime)) else str(session or "")[:10]


def claim_key(session, sym: str, frame: str, bar_t: str) -> str:
    """"GGW:{date}|{SYM}|{frame}" (LATCH "session"), "GGW:{date}|{SYM}|{frame}|{bar_t}" (LATCH "cross"); any other
    latch value fails closed to "session"."""
    base = f"{C.CLAIM_PREFIX}:{_iso(session)}|{(sym or '').upper()}|{frame}"
    return f"{base}|{bar_t}" if C.LATCH == C.LATCHES[1] else base


def watch_crosses(F) -> list:
    """[C1.5] ema_cross.frame_crosses(F) without today's first bar (no prior bar on the chart → never a watch cross)."""
    if F is None:
        return []
    first = F.today.start if len(F.today) else None
    return [x for x in EX.frame_crosses(F) if x["i"] != first]


def k5_5m_at(fr, bar_t: str) -> Optional[bool]:
    """K5 on the 5-minute frame at its last closed bar stamped at or before `bar_t` (None when there is none)."""
    by = getattr(fr, "by", {}) or {}
    F5 = by.get("5m")
    if F5 is None or not F5.t:
        return None
    j = None
    for i, t in enumerate(F5.t):
        if t <= bar_t:
            j = i
        else:
            break
    return BLD.k5(F5, j)


def compose(sym: str, tf: str, x: dict, uptrend_cross: Optional[bool], uptrend_5m: Optional[bool]) -> dict:
    """[C3.6, C3.2] The device payload of one watch cross — every FADE_CROSS_BODY field by keyword; NO `items` (the
    /alerts row then links the stored `url`, the watch tab — push/recent.py)."""
    sym = (sym or "").upper()
    close = AL.bar_close_et(x.get("ts"))
    hhmm = close.strftime("%H:%M") if close else "—"
    words = C.FRAME_WORDS[tf]
    body = " · ".join((
        AL.FADE_CROSS_BODY.format(fast=GC.EMA_FAST, slow=GC.EMA_SLOW, frame=words, hhmm=hhmm,
                                  px=AL._px(x.get("close"))),
        f"K5 uptrend at the cross: {words} {MARK.get(uptrend_cross, MARK[None])} · "
        f"{C.FRAME_WORDS['5m']} {MARK.get(uptrend_5m, MARK[None])}",
        AL.FADE_CROSS_TAIL))
    return {"title": f"🔀 {sym} · 👀 Watch · {GC.EMA_FAST} EMA over {GC.EMA_SLOW} EMA ({words})", "body": body,
            "tag": f"ggw-{tf}-{sym}", "url": f"/chart-maps?tab={C.TAB}&focus={sym}", "kind": C.PUSH_KIND,
            "ticker": sym}


def _hook_names() -> dict:
    """push kind → the push.hooks sender, from the variants (GG5 / GG1 setup + potential)."""
    return {V.GG5.push_kind_setup: V.GG5.send_setup, V.GG5.push_kind_potential: V.GG5.send_potential,
            V.GG1.push_kind_setup: V.GG1.send_setup, V.GG1.push_kind_potential: V.GG1.send_potential}


def _send(owner: str, payload: dict) -> dict:
    """The sender of C.PUSH_KIND — fail closed: an unmapped kind raises BEFORE push.hooks is imported."""
    name = _hook_names().get(C.PUSH_KIND)
    if not name:
        raise RuntimeError(f"no sender for the 👀 kind {C.PUSH_KIND!r}")
    from push import hooks
    return getattr(hooks, name)(owner=owner, payload=payload)


def _hold(held, sym: str, tf: str, bar_t, reason: str) -> None:
    if isinstance(held, dict):
        held.setdefault(sym, {})[tf] = {"bar_t": bar_t, "reason": reason}


def run(frames, now, session, *, coll, send: Optional[Callable] = None, owner: Optional[str] = None,
        dry: bool = False, seen: Optional[dict] = None, held: Optional[dict] = None) -> dict:
    """Judge the latest up cross of every listed name (list order) on every frame (C.FRAMES order) → counts
    (COUNT_KEYS). `held` (out-param, [C4.4]): {SYM: {tf: {bar_t, reason}}} for a cross judged on its own minute or
    `missed_fetch` (never for late / claimed_before / not_push_frame / dry)."""
    counts = {k: 0 for k in COUNT_KEYS}
    send = send or _send
    session_iso = _iso(session)
    closed = None
    for sym, fr in (frames or {}).items():
        counts["names"] += 1
        if fr is None:
            continue
        by = getattr(fr, "by", {}) or {}
        for tf, _rule in C.FRAMES:
            F = by.get(tf)
            if F is None:
                continue
            x = EX.latest_up_cross(watch_crosses(F), session_iso)
            if x is None:
                continue
            counts["cross"] += 1
            fresh = AL.is_fresh({"entry_bar_t": x["ts"]}, now, V.GG1)
            own = bool(F.t) and x["ts"] == F.t[-1] and fresh
            if tf not in C.PUSH_FRAMES or tf not in AL.FRAME_MINUTES:
                counts["not_push_frame"] += 1
                continue
            if mode() == C.PUSH_MODES[0]:
                counts["off"] += 1
                if own:
                    _hold(held, sym, tf, x["ts"], "off")
                continue
            key = claim_key(session, sym, tf, x["ts"])
            if not own:
                if AL._exists(coll, key):
                    counts["claimed_before"] += 1
                elif fresh and str((seen or {}).get(sym) or "") < x["ts"]:
                    counts["missed_fetch"] += 1                 # [C1.3] the last good read never held the cross bar
                    _hold(held, sym, tf, x["ts"], "missed_fetch")
                else:
                    counts["late"] += 1
                continue
            if closed is None:
                closed = AL._closed_reason(now) or ""
            if closed:
                counts["suppressed_closed"] += 1
                _hold(held, sym, tf, x["ts"], "suppressed_closed")
                continue
            w = AL.window_reason(x["ts"], session, F.frame)
            if w:
                counts[w] += 1
                _hold(held, sym, tf, x["ts"], w)
                continue
            sv = EX.finite(B.session_volume(fr))
            if sv is None or sv < GC.K11_MIN_SESSION_VOLUME:
                counts["under_floor"] += 1
                _hold(held, sym, tf, x["ts"], "under_floor")
                continue
            up_x, up_5 = BLD.k5(F, x["i"]), k5_5m_at(fr, x["ts"])
            if C.UPTREND_FILTER is not None:
                pick = {C.UPTREND_FILTERS[1]: up_x, C.UPTREND_FILTERS[2]: up_5}.get(C.UPTREND_FILTER)
                if pick is not True:
                    counts["not_uptrend"] += 1
                    _hold(held, sym, tf, x["ts"], "not_uptrend")
                    continue
            if dry:
                counts["dry"] += 1
                continue
            if coll is None:
                counts["no_store"] += 1                         # [C3.5] never a claim-less send
                _hold(held, sym, tf, x["ts"], "no_store")
                continue
            doc = {"date": session_iso, "symbol": (sym or "").upper(), "frame": tf, "bar_t": x["ts"],
                   "close": x.get("close"), "uptrend_cross": up_x, "uptrend_5m": up_5, "kind": C.PUSH_KIND,
                   "state": AL.FADE_CROSS_STATES[0], "at": now.isoformat() if isinstance(now, datetime) else now}
            from supply_demand.demand_alerts import claim_key as _claim
            if not _claim(coll, key, doc):
                counts["claimed_before"] += 1
                continue
            payload = compose(sym, tf, x, up_x, up_5)
            try:
                res = send(owner or AL._owner(), payload) or {}
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala watch 🔀: send failed for %s %s: %s", sym, tf, type(exc).__name__)
                counts["failed"] += 1
                _hold(held, sym, tf, x["ts"], "failed")
                AL._settle(coll, key, {"state": AL.FADE_CROSS_STATES[3], "result": {"error": type(exc).__name__}})
                continue
            sent, targets = int(res.get("sent") or 0), int(res.get("total_targets") or 0)
            st = (AL.FADE_CROSS_STATES[1] if sent > 0 else AL.FADE_CROSS_STATES[2] if targets == 0
                  else AL.FADE_CROSS_STATES[3])
            verdict = {AL.FADE_CROSS_STATES[1]: PUSHED, AL.FADE_CROSS_STATES[2]: "no_target"}.get(st, "failed")
            counts[verdict] += 1
            _hold(held, sym, tf, x["ts"], verdict)
            AL._settle(coll, key, {"state": st, "result": {k: res.get(k) for k in ("sent", "failed", "total_targets",
                                                                                   "skipped")}})
    return counts


def rules_line() -> str:
    """The ℹ️ clause — every number and word from the constants at CALL time."""
    words = [C.FRAME_WORDS[tf] for tf, _r in C.FRAMES]
    charts = ", ".join(w.replace("-min", "-") for w in words[:-1]) + " and " + words[-1]
    push = [C.FRAME_WORDS[tf] for tf, _r in C.FRAMES if tf in C.PUSH_FRAMES and tf in AL.FRAME_MINUTES]
    drawn = [C.FRAME_WORDS[tf] for tf, _r in C.FRAMES if C.FRAME_WORDS[tf] not in push]
    push_words = " / ".join(push) or "no"
    after_open = (datetime.combine(date(2000, 1, 3), ET_RTH_OPEN)
                  + timedelta(minutes=GC.NO_TRADE_AFTER_OPEN_MIN)).strftime("%H:%M")
    once = ("once per ticker, frame and session" if C.LATCH != C.LATCHES[1] else "on every up cross")
    filt = ("no trend filter" if C.UPTREND_FILTER is None else f"the K5 filter ({C.UPTREND_FILTER})")
    latch = (f" With {filt} the FIRST up cross after {after_open} uses that ticker's one ring for the day"
             + (", even inside a down-trend" if C.UPTREND_FILTER is None else "")
             + "; a later cross is still drawn, not rung." if C.LATCH != C.LATCHES[1] else "")
    fade = (f"{AL.FRAME_MINUTES[V.GG5.slow]}- or {AL.FRAME_MINUTES[V.GG5.primary]}-min")
    marked = (" and ".join(w.replace("-min", "-") if i < len(drawn) - 1 else w for i, w in enumerate(drawn))
              + " crosses are marked only; ") if drawn else ""
    return (f"👀 Gajjala's Watch marks every {GC.EMA_FAST} / {GC.EMA_SLOW} EMA cross on your tickers' {charts} charts "
            f"(closed bars); a cross ABOVE on the latest closed {push_words} bar rings {once} (the 🧠 alert kind) — "
            f"never pre-market, never the first {GC.NO_TRADE_AFTER_OPEN_MIN} minutes, never after the extended close, "
            f"never on a closed day, held under GG's {GC.K11_MIN_SESSION_VOLUME:,}-share session floor.{latch} "
            f"A cross missed by a failed minute read is never sent late. A name also on a ➖ Fade card can ring a "
            f"second 🔀 from the Fade's {fade} frame. {marked}a cross under never rings; mode {mode()}. "
            f"UNMEASURED — information, not an entry.")


__all__ = ["COUNT_KEYS", "mode", "claim_key", "watch_crosses", "compose", "run", "rules_line", "k5_5m_at"]
