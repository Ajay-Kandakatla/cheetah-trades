"""🩳🔀 The 🩳 High SI sub's 9-over-21 EMA cross push — a pass step of the 🚩 5-minute pass (2026-11-23, spec highsi §3.5).

Ajay, verbatim (2026-11-23, voice-typed — "talks" = stocks): "And also add alerts for these talks when they are crossing
EMA, 9 EMA over 21 EMA." His answer (question card): the 5-min AND the 15-min chart, closed bar only, each frame on its
own cross, a NEW push kind (GC.HIGH_SI_CROSS_PUSH_KIND, the ninth owner keep-set kind), 04:00–20:00 ET, ONE push per
name per frame per cross.

BUILT OFF, LIVE since 2026-11-23 (gate V0): `mode()` = high_si.push_mode() (the ONE mode read, fail closed to "off"). Only the main session writes the
live word into constants.py, after gate V0 (spec §0.3). Nothing here writes it.

WHO: a name of THIS pass's frames that high_si.classify lists — the SAME function the 🩳 board lists with, so a name
the two float reads disagree on never rings. The short interest is read ONCE per pass (`si_read`, default
high_si.si_blocks); an unread read rings nothing (unknown is not listed).

WHICH CROSS: the ONE engine — ema_cross.latest_up_cross over gajjala_watch.cross_alerts.watch_crosses(F) (today's
first drawn bar is never a cross) on the pass's own closed 5-min / 15-min Frame (bars.Frames.by — the house resample,
no fetch). Only on its own bar: the cross bar is the frame's latest closed bar AND fresh (alerts.is_fresh, GG5's
clock). A cross missed by a skipped pass, or held on its own bar and no longer the latest, is counted `late` — never
sent late. A cross under never rings.

GATE ORDER (every refusal counted, none written): not listed (its high_si reason) · no cross · mode off · not its own
bar (`claimed_before` when the claim is on file, else `late`) · closed day (alerts._closed_reason) · the HOURS on the
pass clock (potential.window_reason == "outside_hours"; its "muted" answer is NOT read) · the first-15 MUTE by the
candle's START (alerts.window_reason == "suppressed_first15" → `muted`; "suppressed_window" → `outside_hours`;
"suppressed_premarket" is not a refusal — his 04:00 start keeps pre-market) · GG's session-volume floor
(GC.K11_MIN_SESSION_VOLUME on the pass's own volume read; unknown → held) · dry · no alert collection (never a
claim-less send) · the insert-only claim (demand_alerts.claim_key, BEFORE the send; "GGS:" ids in gajjala_alerts,
states alerts.FADE_CROSS_STATES — never a ledger word, so the 🏁 never reads them) · the owner-scoped send
(push.hooks.notify_gajjala_si_cross) → alerts._settle.

Reads only what the pass already holds (and Mongo): nothing new is fetched, nothing streams, nothing trades — the 🚩
lane never reads this kind. UNMEASURED — information only, not an entry.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable, Optional

from . import alerts as AL
from . import constants as GC
from . import ema_cross as EX
from . import high_si as HS
from . import potential as PT
from . import variant as V
from chart_maps.gajjala_watch import constants as WC

log = logging.getLogger("chart_maps.gajjala.high_si_cross")

COUNT_KEYS = ("names", "si_unread", "listed", "no_si", "stale", "no_tier", "not_high", "floats_disagree",
              "float_unknown", "float_over", "si_float_over",
              "cross", "pushed", "dry", "off", "claimed_before", "late", "closed_day", "outside_hours", "muted",
              "under_floor", "no_store", "no_target", "failed")

mode = HS.push_mode                                     # THE mode read (one function, fail closed to "off")


def _iso(session) -> str:
    return session.isoformat()[:10] if isinstance(session, (date, datetime)) else str(session or "")[:10]


def claim_key(session, sym, frame, bar_t) -> str:
    """"GGS:{date}|{SYM}|{frame}|{bar_t}" (LATCH "cross"); "GGS:{date}|{SYM}|{frame}" (LATCH "session" — and any other
    value: fail closed to the quieter latch)."""
    base = f"{GC.HIGH_SI_CROSS_CLAIM_PREFIX}:{_iso(session)}|{str(sym or '').upper()}|{frame}"
    return f"{base}|{bar_t}" if GC.HIGH_SI_CROSS_LATCH == GC.HIGH_SI_CROSS_LATCHES[1] else base


def rules_line() -> str:
    """The ℹ️ / panel sentence — high_si.push_text() (one sentence, never a second copy)."""
    return HS.push_text()


def compose(sym, tf, x, *, si_chip=None, floats_text=None, sho_short=None, add_text=None, broker_text=None) -> dict:
    """The device payload of one 🩳 cross. NO `items`: the /alerts row links the stored `url` (push/recent.py)."""
    from .tab import BROKER_FLAG_ICON, SUB_META
    sym = str(sym or "").upper()
    words = WC.FRAME_WORDS[tf]
    close = AL.bar_close_et((x or {}).get("ts"))
    hhmm = close.strftime("%H:%M") if close else "—"
    emoji = SUB_META[GC.HIGH_SI_SUB][0]
    title = f"{emoji}🔀 {sym} · {GC.EMA_FAST} EMA over {GC.EMA_SLOW} EMA ({words})"
    if broker_text:
        title += f" · {BROKER_FLAG_ICON}"
    parts = (AL.FADE_CROSS_BODY.format(fast=GC.EMA_FAST, slow=GC.EMA_SLOW, frame=words, hhmm=hhmm,
                                       px=AL._px((x or {}).get("close"))),
             si_chip, floats_text, sho_short, add_text, broker_text, AL.FADE_CROSS_TAIL, HS.NOT_ADVICE)
    body = " · ".join(p for p in parts if isinstance(p, str) and p.strip())
    return {"title": title, "body": body, "tag": f"ggs-{tf}-{sym}-{hhmm.replace(':', '')}",
            "url": f"/chart-maps?tab={V.GG5.tab}&sub={GC.HIGH_SI_SUB}&tf={tf}&focus={sym}",
            "kind": GC.HIGH_SI_CROSS_PUSH_KIND, "ticker": sym}


def _send(owner: str, payload: dict) -> dict:
    from push import hooks
    return hooks.notify_gajjala_si_cross(owner=owner, payload=payload)


def _sho_items(sho_read: Optional[Callable], now) -> dict:
    """{SYM: 🔒 tag block} of the Reg SHO lists — Mongo only, never kicks the refresh worker. {} on any fault."""
    try:
        if sho_read is None:
            from short_interest import reg_sho
            pay = reg_sho.payload(kick=False, now=now)
        else:
            pay = sho_read(now)
        items = (pay or {}).get("items") if isinstance(pay, dict) else None
        return items if isinstance(items, dict) else {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala 🩳 cross: Reg SHO read failed: %s", type(exc).__name__)
        return {}


def _add_text(st, session, sym) -> Optional[str]:
    """The 📌 / 🎪 tag the pass stored on the name's read doc (ctx.trader_text / ctx.promo_text), joined " · "."""
    try:
        doc = st.get_read(session, sym) if st is not None else None
        ctx = (doc or {}).get("ctx") if isinstance(doc, dict) else None
        if not isinstance(ctx, dict):
            return None
        tags = [t for t in (ctx.get("trader_text"), ctx.get("promo_text")) if isinstance(t, str) and t.strip()]
        return " · ".join(tags) or None
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala 🩳 cross: tag read failed for %s: %s", sym, type(exc).__name__)
        return None


def _broker_flags(st):
    try:
        from . import store as ST
        return frozenset(ST.broker_flags(st)[0])
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala 🩳 cross: broker list read failed: %s", type(exc).__name__)
        return None


def _fenced(fn, *a):
    try:
        return fn(*a)
    except Exception as exc:                                    # noqa: BLE001 — a fault drops the clause, never the push
        log.warning("gajjala 🩳 cross: a body clause failed: %s", type(exc).__name__)
        return None


def _floats_text(fr, blk):
    return HS.floats_text(fr, blk)


def _si_chip(blk):
    c = blk.get("chip") if isinstance(blk, dict) else None
    return c if isinstance(c, str) else None


def _broker_text(sym, flags):
    from .tab import broker_text_for
    return broker_text_for(sym, flags)


def run_step(st, frames, now, session, *, floats, volume, owner=None, send=None, dry=False,
             si_read=None, sho_read=None, flags=None) -> dict:
    """Judge every listed 🩳 member's latest up cross on each GC.HIGH_SI_CROSS_FRAMES frame → counts (COUNT_KEYS)."""
    from chart_maps.gajjala_watch.cross_alerts import watch_crosses
    from supply_demand.demand_alerts import claim_key as _claim
    counts = {k: 0 for k in COUNT_KEYS}
    if not V.is_gg5(V.of(st)):
        return counts
    frames = frames if isinstance(frames, dict) else {}
    floats = floats if isinstance(floats, dict) else {}
    volume = volume if isinstance(volume, dict) else {}
    names = sorted({str(s).upper() for s in frames})
    counts["names"] = len(names)
    by_up = {str(s).upper(): fr for s, fr in frames.items()}
    fl_up = {str(s).upper(): f for s, f in floats.items()}
    vol_up = {str(s).upper(): n for s, n in volume.items()}
    if si_read is None:
        today = AL.bar_close_et(now).date() if AL.bar_close_et(now) is not None else session
        si_read = (lambda syms: HS.si_blocks(syms, today=today))
    try:
        blocks = si_read(names)
    except Exception as exc:                                    # noqa: BLE001 — unread = unknown = nothing rings
        log.warning("gajjala 🩳 cross: short-interest read failed: %s", type(exc).__name__)
        blocks = None
    if not isinstance(blocks, dict):
        counts["si_unread"] = 1
        return counts
    send = send or _send
    session_iso = _iso(session)
    coll = None
    coll_read = False
    closed = hours = None
    sho = None
    brk = flags
    brk_read = flags is not None
    for sym in names:
        blk = blocks.get(sym)
        fr_read = fl_up.get(sym)
        cl = HS.classify(blk, fr_read)
        if not cl.get("listed"):
            r = cl.get("reason")
            if r in counts:
                counts[r] += 1
            continue
        counts["listed"] += 1
        fr = by_up.get(sym)
        by = getattr(fr, "by", None) or {}
        for tf in GC.HIGH_SI_CROSS_FRAMES:
            F = by.get(tf)
            if F is None:
                continue
            x = EX.latest_up_cross(watch_crosses(F), session_iso)
            if x is None:
                continue
            counts["cross"] += 1
            if mode() != GC.HIGH_SI_CROSS_PUSH_MODES[1]:
                counts["off"] += 1
                continue
            if not coll_read:
                coll = st.alerts_coll() if st is not None else None
                coll_read = True
            key = claim_key(session, sym, tf, x["ts"])
            if x["ts"] != (F.t[-1] if F.t else None) or not AL.is_fresh({"entry_bar_t": x["ts"]}, now, V.GG5):
                counts["claimed_before" if AL._exists(coll, key) else "late"] += 1
                continue
            if closed is None:
                closed = AL._closed_reason(now) or ""
            if closed:
                counts["closed_day"] += 1
                continue
            if hours is None:
                hours = PT.window_reason(now, session) or ""
            if hours == "outside_hours":
                counts["outside_hours"] += 1
                continue
            w = AL.window_reason(x["ts"], session, tf)
            if w == "suppressed_first15":
                counts["muted"] += 1
                continue
            if w == "suppressed_window":
                counts["outside_hours"] += 1
                continue
            sv = EX.finite(vol_up.get(sym))                     # None / NaN / inf / bool / text → unknown → held
            if sv is None or sv < GC.K11_MIN_SESSION_VOLUME:
                counts["under_floor"] += 1
                continue
            if dry:
                counts["dry"] += 1
                continue
            if coll is None:
                counts["no_store"] += 1                         # never a claim-less send
                continue
            doc = {"date": session_iso, "symbol": sym, "frame": tf, "bar_t": x["ts"], "close": x.get("close"),
                   "kind": GC.HIGH_SI_CROSS_PUSH_KIND, "tier": cl.get("tier"),
                   "float_shares": cl.get("float_shares"), "si_float_shares": cl.get("si_float_shares"),
                   "state": AL.FADE_CROSS_STATES[0], "at": now.isoformat() if isinstance(now, datetime) else now}
            if not _claim(coll, key, doc):
                counts["claimed_before"] += 1
                continue
            try:
                if sho is None:
                    sho = _sho_items(sho_read, now)
                if not brk_read:
                    brk, brk_read = _broker_flags(st), True
                sho_blk = sho.get(sym) if isinstance(sho, dict) else None
                payload = compose(sym, tf, x,
                                  si_chip=_fenced(_si_chip, blk),
                                  floats_text=_fenced(_floats_text, fr_read, blk),
                                  sho_short=(sho_blk.get("short") if isinstance(sho_blk, dict)
                                             and isinstance(sho_blk.get("short"), str) else None),
                                  add_text=_add_text(st, session, sym),
                                  broker_text=_fenced(_broker_text, sym, brk))
                res = send(owner or AL._owner(), payload) or {}
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala 🩳 cross: send failed for %s %s: %s", sym, tf, type(exc).__name__)
                counts["failed"] += 1
                AL._settle(coll, key, {"state": AL.FADE_CROSS_STATES[3], "result": {"error": type(exc).__name__}})
                continue
            sent, targets = int(res.get("sent") or 0), int(res.get("total_targets") or 0)
            state = (AL.FADE_CROSS_STATES[1] if sent > 0 else AL.FADE_CROSS_STATES[2] if targets == 0
                     else AL.FADE_CROSS_STATES[3])
            counts[{AL.FADE_CROSS_STATES[1]: "pushed", AL.FADE_CROSS_STATES[2]: "no_target"}.get(state, "failed")] += 1
            AL._settle(coll, key, {"state": state, "result": {k: res.get(k) for k in ("sent", "failed",
                                                                                      "total_targets", "skipped")}})
    return counts


__all__ = ["COUNT_KEYS", "mode", "claim_key", "compose", "run_step", "rules_line"]
