"""🧪 Gajjala · Audited — the fenced overlay step inside the 5-minute pass (BUILD_SPEC 2026-11-01 §3.5, WP-B).

Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited. So we can keep track of improvements on this tab"

The audited variant (variant.GGA, tab `gajjala_audited`) has NO pass of its own and NO data pipeline: `run.run_pass`
calls `run_step` once per 🚩 pass, AFTER GG5's reads, read docs, A+ gate and pass summary are done, inside its own
fence. The step reads THIS pass's reads and Frames (already in memory — zero provider calls) and writes ONLY the GGA
store's own collections (`gajjala_audited_overlay`, `gajjala_audited_alerts`, `gajjala_audited_state`); GG5's read docs,
pass doc, `out` and `out["errors"]` never gain a byte (the GG5 WRITES golden pins run_pass's return dict).

Per name with something to say (an A+ read, or an ARMED 🎾 read — `wants_overlay`; every other name: no read, no write):
  1. the 🎾 frozen stops: the FIRST armed read per trigger is kept (a LIST — a price is never a Mongo field name);
  2. every A+ read is judged by `audited_rules.judge` on the read's OWN frame (the Fade's is 15-minute — HIS CALL #14);
     a read that fails an ON rule is handed on as `aplus_held` (never "aplus" — `alerts._candidates` skips it);
  3. the overlay doc is upserted only when an A+ was judged or the frozen list changed.
Then `alerts.run_pass` over the audited reads with the GGA store, `mode="shadow"` EXPLICITLY and a sender that refuses
(the DOUBLE lock: the explicit mode AND GAJJALA_AUDITED_PUSH_MODE; going live = HIS CALL #1) — an audited A+ is a
`SHADOW:GGA:` claim, never a push. A held A+ is one idempotent `GGA:{date}|SYM|setup#held` row (the `#` = never a 🏁 row).
The pass summary lands in `gajjala_audited_state` doc `audit_latest`; a raise inside writes `ok: False` + the error
type there and re-raises to run.py's fence (logged only). On a dry pass the GGA store is a dry store: its writes are
recorded, not made, and ONE log line names them ("gajjala audit overlay dry writes: …") — the CLI cost proof.
Every rule is UNMEASURED (the 2026-10-30 replay read TOO SMALL). Nothing here trades or enters a lane.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Callable, Optional

from . import constants as GC
from . import variant as V

log = logging.getLogger("chart_maps.gajjala.audited_pass")

LATEST_ID = "audit_latest"     # the GGA gajjala_audited_state doc the step writes every pass


def store_for(st, deps):
    """The GGA store this pass's overlay writes to, or None (the step is skipped).

    A non-GG5 store (a GG1 store — real, `for_variant`, or a dry one) is NEVER audited, hook or no hook (checked FIRST).
    Then `deps.audited_store(st)` when the hook is set (the tests); the real default store → `store.for_variant(GGA)`;
    a dry store → a dry GGA store (its writes recorded under `gajjala_audited_*`); any other injected store → None
    (existing tests never touch Mongo)."""
    from . import store as ST
    if not V.is_gg5(st):
        return None
    hook = getattr(deps, "audited_store", None)
    if hook is not None:
        return hook(st)
    if st is ST.default():
        return ST.for_variant(V.GGA)
    if getattr(st, "dry", False):
        from . import run as RUN
        return RUN.dry_store(ST.GajjalaStore(variant=V.GGA, shared=ST.default()))
    return None


def refuse_send(owner, payload) -> dict:
    """The audited variant's sender: it refuses. Never reached while the mode is shadow (the explicit mode)."""
    from . import audited_rules as AUD
    raise RuntimeError(AUD.NEVER_SENDS)


def frozen_update(existing: list, read: dict) -> list:
    """The 🎾 frozen-stop list after this read: an ARMED read (potential.potential_kind) with a numeric trigger and stop
    appends {trigger (the decimal string), stop, bar_t, at_et} when NO entry carries that trigger — the FIRST armed read
    of a trigger wins, never overwritten. Anything else → the list unchanged."""
    from . import ledger as LG
    from . import potential as PT
    out = list(existing or [])
    if not isinstance(read, dict) or PT.potential_kind(read) != GC.POTENTIAL_KINDS[0]:
        return out
    trig, stop = read.get("trigger"), read.get("stop")
    try:
        if isinstance(trig, bool) or isinstance(stop, bool):
            return out
        key = str(LG._D(trig))
        stop_f = float(stop)
    except (TypeError, ValueError, ArithmeticError):
        return out
    if stop_f != stop_f or any(isinstance(e, dict) and e.get("trigger") == key for e in out):
        return out
    bar_t = read.get("as_of_bar_t")
    out.append({"trigger": key, "stop": stop_f, "bar_t": bar_t,
                "at_et": bar_t[11:16] if isinstance(bar_t, str) and len(bar_t) >= 16 else None})
    return out


def wants_overlay(rs: dict) -> bool:
    """True when the name has something to say this pass: any A+ read, or an ARMED 🎾 read (the frozen-stop memory)."""
    from . import audited_rules as AUD
    from . import potential as PT
    rs = rs or {}
    if any(isinstance(r, dict) and r.get("state") == "aplus" for r in rs.values()):
        return True
    return any(PT.potential_kind(rs.get(s)) == GC.POTENTIAL_KINDS[0] for s in AUD.FROZEN_STOP_SETUPS)


def _dump(x) -> str:
    return json.dumps(x, sort_keys=True, default=str)


def run_step(st, gga, reads: dict, frames: dict, now: datetime, session, *, alert_ctx: Optional[dict], owner,
             dry: bool, push_dry: bool, record_status: Optional[Callable] = None) -> dict:
    """The overlay over THIS pass's reads (module docstring). -> the counts (alerts.COUNT_KEYS + aplus_original,
    aplus_audited, held) — never stored on GG5's `out`. Raises (after a best-effort `ok: False` state doc) so run.py's
    fence logs it."""
    from . import alerts as AL
    from . import audited_rules as AUD
    v = V.GGA
    session_iso = session.isoformat() if hasattr(session, "isoformat") else str(session)
    gga_dry = bool(getattr(gga, "dry", False))
    writes_ok = (not dry) or gga_dry                            # a dry pass lands nothing; a dry store only records
    try:
        gga_reads: dict = {}
        held: list = []
        n_orig = n_aud = n_written = 0
        for sym in sorted(frames):
            rs = reads.get(sym) or {}
            if not wants_overlay(rs):
                gga_reads[sym] = rs
                continue
            existing = gga.get_overlay(session, sym) or {}
            frozen = dict(existing.get("frozen") or {})
            frozen_before = _dump(frozen)
            setups: dict = {}
            out_rs = dict(rs)                                   # the read objects pass through unchanged
            for setup in GC.SETUPS:
                r = rs.get(setup)
                if not isinstance(r, dict):
                    continue
                if setup in AUD.FROZEN_STOP_SETUPS:
                    new = frozen_update(frozen.get(setup) or [], r)
                    if new or setup in frozen:                  # no empty key for a name never armed
                        frozen[setup] = new
                if r.get("state") != "aplus":
                    continue
                n_orig += 1
                F = frames[sym].frame(r.get("frame") or v.primary)   # the read's OWN frame (HIS CALL #14)
                audit = AUD.judge(r, F, frozen.get(setup) or [])
                setups[setup] = {**audit, "entry_bar_t": r.get("entry_bar_t"),
                                 "frame": r.get("frame") or audit.get("frame"), "trigger": r.get("trigger"),
                                 "stop": r.get("stop"), "risk_pct": r.get("risk_pct")}
                if audit.get("aplus") is True:
                    n_aud += 1
                else:
                    out_rs[setup] = dict(r, state=AUD.HELD_STATE, audit=audit)
                    held.append((sym, setup, r, audit))
            gga_reads[sym] = out_rs
            if writes_ok and (setups or _dump(frozen) != frozen_before):
                gga.upsert_overlay(session, sym, {"date": session_iso, "symbol": sym, "setups": setups,
                                                  "frozen": frozen, "pass_at": now, "version": AUD.AUDIT_VERSION},
                                   now=now)
                n_written += 1
        counts = AL.run_pass(gga_reads, frames, now, session, store=gga, send=refuse_send, owner=owner,
                             dry=push_dry, ctx=alert_ctx, mode="shadow")
        if not push_dry:
            coll = gga.alerts_coll()
            for sym, setup, r, audit in held:
                c = (alert_ctx or {}).get(sym) or {}
                AL._record(coll, f"{AL.claim_key(session, sym, setup, v)}#{AUD.HELD_ROW_STATE}", {
                    "date": session_iso, "symbol": sym, "setup": setup, "state": AUD.HELD_ROW_STATE,
                    "kind": v.push_kind_setup, "mode": "shadow", "entry_bar_t": r.get("entry_bar_t"),
                    "frame": r.get("frame"), "trigger": r.get("trigger"), "stop": r.get("stop"),
                    "risk_pct": r.get("risk_pct"), "price": c.get("price"),
                    "audit": {k: audit.get(k) for k in ("passed", "failed", "values", "version", "frame")},
                    "at": now.isoformat()})
        summary = dict(counts, aplus_original=n_orig, aplus_audited=n_aud, held=len(held))
        if writes_ok:
            gga.set_state(LATEST_ID, {
                "at": now, "session": session_iso, "n_read": len(reads or {}), "n_aplus_original": n_orig,
                "n_aplus_audited": n_aud, "n_held": len(held), "n_overlay_written": n_written,
                "held": [{"symbol": s, "setup": k, "failed": [f.get("id") for f in (a.get("failed") or [])
                                                              if isinstance(f, dict)]}
                         for s, k, _r, a in held],
                "alerts": counts, "ok": True, "rules": [rule.id for rule in AUD.on_rules()],
                "version": AUD.AUDIT_VERSION})
        if record_status is not None:
            record_status(summary, now, None)
        return summary
    except Exception as exc:
        if writes_ok:
            try:
                gga.set_state(LATEST_ID, {"at": now, "session": session_iso, "ok": False,
                                          "error": type(exc).__name__})
            except Exception:                                   # noqa: BLE001 — best-effort
                log.warning("gajjala audit overlay: the failure state could not be written")
        raise
    finally:
        if gga_dry:
            log.info("gajjala audit overlay dry writes: %s", sorted(set(getattr(gga, "writes", []))))


__all__ = ["LATEST_ID", "store_for", "refuse_send", "frozen_update", "wants_overlay", "run_step"]
