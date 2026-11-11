"""🔄 🥇 Luk's scan now — the trigger (spec lukscan §3.2, WP-LUK-TRIGGER, 2026-11-11).

Ajay 2026-11-11, verbatim: "Can you put an ondeman scan button for Luk' scans too"

"too" = 🚩 Gajjala's 🔄 button: POST /chart-maps/luk/scan → `request()` answers at once (started | reused | waiting |
closed | refused) through 🚩's ONE order — `gajjala.on_demand.request(..., variant=LUK, profile=PROFILE)` — and, on
"started", ONE 🥇 pass runs in a SUBPROCESS (`python -m chart_maps.luk.run --on-demand`, its push gate dry). The api
process never runs or imports the pass: `chart_maps.luk.run` is imported inside the functions below for its window,
switch, slot and fit checks only. The store is always `luk.store.default()` (Luk's lease numbers — never
`gajjala.store.for_variant(LUK)`, which would carry the 1-minute page's); the child slot is `variant=LUK`'s own, so a
live 🚩 child never makes 🥇 "waiting", and back.

What this profile adds to 🚩's order:
  closed — a closed day (market_hours.gate.closed_reason) or outside Luk's pass window (luk.run.in_window, 04:00–16:05 ET);
  refused "off" — Luk's kill switch (luk.run.enabled) is off: nothing spawns;
  then 🚩's own child → lease → first-pass-of-the-session → reuse checks, unchanged;
  waiting "slot_wait" — this slot's 5-minute 🥇 pass has not landed (no "latest_cron" stamped ≥ the tick) and its cron
    child has not refused itself (no luk_state "child" skip doc ≥ the tick): a tap never starts before it, so it can
    never take the lease the cron pass is about to claim (with the cron down nothing starts — HIS CALL H7);
  waiting "no_room" — a pass started now could not end LUK_SLOT_MARGIN_SEC before the next tick (luk.run.fits): NO poll
    plan, nothing runs on his behalf, the button stays live;
  started — the child is spawned (a spawn that raises → refused).
Every word is a module constant below, its numbers formatted from the constants at call time. UNMEASURED — nothing here
trades; an on-demand pass rings no device (its push gate is dry).
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import on_demand as OD
from chart_maps.gajjala import variant as V

from . import constants as LC
from . import store as LS
from .variant import LUK

log = logging.getLogger("chart_maps.luk.on_demand")

ET = ZoneInfo("America/New_York")
ARGV = (sys.executable, "-m", "chart_maps.luk.run", "--on-demand")
PROC_NAME = "luk-on-demand"
WHY_OFF = "off"
WHY_SLOT_WAIT = "slot_wait"
WHY_NO_ROOM = "no_room"
# The served words (LW10–LW17, spec §3.2). {cad} = the 🥇 cadence in minutes; every other number is a constant's,
# formatted at call time. Never "on open", never the b-word, never "edge".
WORDS = {
    "started": "🔄 scanning on demand — started {hms} ET; the board below stays until it lands",                  # LW10
    "reused": "🔄 the {hhmm} ET pass finished {age} s ago — reused (a pass under {reuse} s old is not re-run)",       # LW11
    "reused_on_demand": ("🔄 an on-demand pass finished {age} s ago — reused (a pass under {reuse} s old is not "
                         "re-run)"),                                                                                 # LW11b
    "waiting_on_demand": "🔄 an on-demand pass started{at} is still running — showing it when it lands",            # LW12
    "waiting_cron": "🔄 the {cad}-minute 🥇 pass started{at} is still running — showing it when it lands",          # LW12
    "first_before": ("🔄 the first {cad}-minute 🥇 pass of the session runs at {hhmm} ET — showing it when it "
                     "lands"),                                                                                       # LW12c
    "first_after": ("🔄 no {cad}-minute 🥇 pass has landed this session yet — the next runs at {hhmm} ET; showing it "
                    "when it lands"),                                                                                # LW12c
    "slot_wait": ("🔄 the {hhmm} ET {cad}-minute 🥇 pass has not landed yet — showing it when it lands, if it runs (a "
                  "scan never starts before it)"),                                                                   # LW15
    "no_room": ("🔄 too close to the {hhmm} ET pass for another one (a pass needs {budget} s + {margin} s before it) "
                "— the board picks that pass up on its next {cad}-minute refresh"),                                  # LW16
    "closed": ("outside 🥇 Luk's pass window ({open}–{close} ET on a market day) — no scan; last pass {hhmm} ET "
               "{date}"),                                                                                            # LW13
    "closed_none": "outside 🥇 Luk's pass window ({open}–{close} ET on a market day) — no scan; no pass on file",   # LW13
    "off": "🔄 🥇 Luk's pass is switched off (LUK_ENABLED) — nothing runs",                                        # LW17
    "refused": "🔄 the scan could not start (store error) — the board shows the last pass",                         # LW14
}


def _run():
    """chart_maps.luk.run — imported HERE, never at module level: the window / switch / slot / fit checks only (the
    pass never runs in the api process)."""
    from . import run as LR
    return LR


def _hhmm(t) -> Optional[str]:
    return t.astimezone(ET).strftime("%H:%M") if isinstance(t, datetime) else None


def closed(now: datetime) -> bool:
    """A closed day (market_hours.gate.closed_reason — a raise reads closed) or outside Luk's pass window."""
    from market_hours.gate import closed_reason
    try:
        if closed_reason(now.astimezone(ET)) is not None:
            return True
    except Exception as exc:                                        # noqa: BLE001
        log.warning("luk on-demand: closed-day check failed: %s", exc)
        return True
    return not _run().in_window(now)


def refusal(now: datetime) -> Optional[str]:
    """WHY_OFF when Luk's kill switch is off (luk.run.enabled, read at call time), else None."""
    return None if _run().enabled() else WHY_OFF


def gate(now: datetime, st, latest, cron) -> Optional[dict]:
    """After 🚩's reuse check, before the spawn — the rule that keeps a tap from ever costing a cron pass.
    1. this slot SETTLED = its cron 🥇 pass landed ("latest_cron" `at` ≥ the tick, any status) OR its cron child refused
       itself (the luk_state "child" doc, state "skipped", `at` ≥ the tick); else waiting slot_wait (with a poll plan).
       A skip-doc read that raises reads as not settled.
    2. a pass started now must fit (luk.run.fits: start + LUK_PASS_BUDGET_SEC + LUK_SLOT_MARGIN_SEC ≤ the next tick);
       else waiting no_room with NO poll plan.
    None = spawn."""
    LR = _run()
    tick, nxt = LR.slot_of(now)
    c_at = OD._stamp(cron.get("at")) if isinstance(cron, dict) else None
    try:
        sk = st.get_state(LR.CHILD_STATE_ID)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("luk on-demand: child state read failed: %s", exc)
        sk = None
    sk_at = OD._stamp(sk.get("at")) if isinstance(sk, dict) and sk.get("state") == "skipped" else None
    settled = (c_at is not None and c_at >= tick) or (sk_at is not None and sk_at >= tick)
    if not settled:
        return {"state": "waiting", "why": WHY_SLOT_WAIT, "when": tick}
    if not LR.fits(now, nxt):
        return {"state": "waiting", "why": WHY_NO_ROOM, "when": nxt, "plan": False}
    return None


def text(state: str, latest: Optional[dict], now: datetime, *, holder=None, started=None, age=None, first_wait=None,
         via_open: bool = False, why=None, when=None) -> str:
    """The served sentence of an answer (WORDS, formatted at call time)."""
    cad = V.cadence_sec(LUK) // 60
    at = OD._stamp((latest or {}).get("at")) if isinstance(latest, dict) else None
    if state == "started":
        return WORDS["started"].format(hms=OD._hms(started or now))
    if state == "reused":
        key = "reused_on_demand" if via_open else "reused"
        return WORDS[key].format(hhmm=_hhmm(at), age=int(age or 0), reuse=GC.ON_DEMAND_REUSE_SEC)
    if state == "waiting" and why == WHY_SLOT_WAIT:
        return WORDS["slot_wait"].format(hhmm=_hhmm(when), cad=cad)
    if state == "waiting" and why == WHY_NO_ROOM:
        return WORDS["no_room"].format(hhmm=_hhmm(when), budget=LC.LUK_PASS_BUDGET_SEC, margin=LC.LUK_SLOT_MARGIN_SEC,
                                       cad=cad)
    if state == "waiting" and first_wait is not None:
        first, nxt = first_wait
        if now.astimezone(ET) <= first:
            return WORDS["first_before"].format(cad=cad, hhmm=_hhmm(first))
        return WORDS["first_after"].format(cad=cad, hhmm=_hhmm(nxt))
    if state == "waiting":
        at_s = f" at {OD._hms(started)} ET" if isinstance(started, datetime) else ""
        key = "waiting_on_demand" if holder == "on_demand" else "waiting_cron"
        return WORDS[key].format(at=at_s, cad=cad)
    if state == "closed":
        if at is None:
            return WORDS["closed_none"].format(open=LC.LUK_PASS_OPEN_ET, close=LC.LUK_PASS_CLOSE_ET)
        return WORDS["closed"].format(open=LC.LUK_PASS_OPEN_ET, close=LC.LUK_PASS_CLOSE_ET, hhmm=_hhmm(at),
                                      date=at.astimezone(ET).date().isoformat())
    if state == "refused" and why == WHY_OFF:
        return WORDS["off"]
    return WORDS["refused"]


PROFILE = OD.Profile(ARGV, PROC_NAME, closed, text, refusal=refusal, gate=gate)


def request(now: Optional[datetime] = None, *, store=None, spawn=None) -> dict:
    """CONTRACT — the POST's answer: 🚩's order on Luk's store (luk.store.default() unless injected), Luk's child slot
    (variant=LUK) and PROFILE. Never raises; keys = gajjala.on_demand.RESPONSE_KEYS (a store that cannot even be
    built → refused LW14)."""
    try:
        st = store if store is not None else LS.default()
    except Exception as exc:                                        # noqa: BLE001
        log.warning("luk on-demand: store failed: %s", exc)
        return dict({k: None for k in OD.RESPONSE_KEYS}, state="refused", text=WORDS["refused"])
    return OD.request(now, store=st, spawn=spawn, variant=LUK, profile=PROFILE)


__all__ = ["ARGV", "PROC_NAME", "WORDS", "PROFILE", "closed", "refusal", "gate", "text", "request"]
