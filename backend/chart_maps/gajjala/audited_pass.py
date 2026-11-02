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
2026-11-01 (the eight modifications, SPEC rev 2 §3.2 — Ajay: "Yes make the changes in audited please" / "But keep a
track record too to see the winners and loster"): step 2 judges ONLY the A+ bars 🚩 would ring on this pass —
`alerts.refusal(...)` is None (the ONE refusal chain run_pass itself calls) and the (symbol, setup) is not already
claimed today; every other A+ read passes through unchanged (no judge, no overlay entry, no marker, no slot) and is
counted in the state doc's `n_unjudged` by its refusal word [C1]. T4 reads the pass's own scanner strip
(`best_change_pct`, `best_symbol`; absent → fail-closed). T1 (the daily cap) is judged LAST over the claimable
survivors in 🚩's ring order (audited_rules.ring_order = alerts._candidates' key) against today's GGA claims [C3, C4].
The #held marker and the shadow claim (settled ONCE) carry the audit {passed, failed, values, version, frame, rules};
the state doc counts the day's T4 holds from the durable markers (`t4_session`) [C2].
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


def session_claims(gga, session) -> tuple:
    """(today's audited claims as {(SYM, setup)}, read_fault) — through the ONE row reader `ledger.alert_of` (the
    shadow claims and any live ones; a `#held` marker or `#state` refusal is never a row). A read fault → (set(), True):
    T1 then reads None for every survivor (fail-closed, NONE_WHY["T1"])."""
    from . import ledger as LG
    docs = gga.alert_rows([session])
    if docs is None:
        return set(), True
    claimed = set()
    for d in docs:
        row = LG.alert_of(d, LG.KINDS[1], variant=V.GGA)
        if row:
            claimed.add((row["symbol"], row["setup"]))
    return claimed, False


def _failed_ids(audit) -> list:
    return [f.get("id") for f in ((audit or {}).get("failed") or []) if isinstance(f, dict)]


def _audit_block(audit: dict) -> dict:
    """The audit a 🧪 record carries (the #held marker and the settled shadow claim) — the per-rule table's source."""
    return {k: audit.get(k) for k in ("passed", "failed", "values", "version", "frame", "rules")}


def t4_session(gga, session) -> dict:
    """[C2] The day's T4 count from the DURABLE #held markers (idempotent per date, symbol, setup — a repeated pass
    never double-counts): fired = markers whose failed ids include T4, fired_alone = markers whose failed ids are
    exactly [T4]. A read fault → both None + read_fault True."""
    rows = gga.held_rows([session])
    if rows is None:
        return {"fired": None, "fired_alone": None, "read_fault": True}
    ids = [_failed_ids(d.get("audit")) for d in rows if isinstance(d, dict)]
    return {"fired": sum(1 for f in ids if "T4" in f), "fired_alone": sum(1 for f in ids if f == ["T4"])}


def run_step(st, gga, reads: dict, frames: dict, now: datetime, session, *, alert_ctx: Optional[dict], owner,
             dry: bool, push_dry: bool, record_status: Optional[Callable] = None,
             strip: Optional[dict] = None) -> dict:
    """The overlay over THIS pass's reads (module docstring). -> the counts (alerts.COUNT_KEYS + aplus_original,
    aplus_audited, held) — never stored on GG5's `out`. Raises (after a best-effort `ok: False` state doc) so run.py's
    fence logs it. `strip` = the pass's scanner strip (`best_change_pct`, `best_symbol` — T4's number; absent → T4
    fails closed)."""
    from . import alerts as AL
    from . import audited_rules as AUD
    v = V.GGA
    session_iso = session.isoformat() if hasattr(session, "isoformat") else str(session)
    gga_dry = bool(getattr(gga, "dry", False))
    writes_ok = (not dry) or gga_dry                            # a dry pass lands nothing; a dry store only records
    try:
        coll = gga.alerts_coll()
        closed = AL._closed_reason(now)                         # ONCE per pass, as run_pass
        claimed, claims_fault = session_claims(gga, session)
        strip = strip if isinstance(strip, dict) else {}
        ctx = {"session": session, "best_change_pct": strip.get("best_change_pct"),
               "best_symbol": strip.get("best_symbol")}
        actx = alert_ctx or {}
        gga_reads: dict = {}
        per_sym: dict = {}
        judged: list = []                                       # (sym, setup, read, audit) — the reads 🚩 would ring
        n_unjudged: dict = {}
        n_orig = 0
        # phase 1 — the frozen stops, then judge ONLY the A+ bars the pass would claim [C1]
        for sym in sorted(frames):
            rs = reads.get(sym) or {}
            if not wants_overlay(rs):
                gga_reads[sym] = rs
                continue
            existing = gga.get_overlay(session, sym) or {}
            frozen = dict(existing.get("frozen") or {})
            frozen_before = _dump(frozen)
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
                why = AL.refusal(dict(r, setup=r.get("setup") or setup), sym, str(r.get("entry_bar_t") or ""),
                                 frames[sym], now, session, actx.get(sym), v, coll, closed=closed)
                if why is None and (str(sym).upper(), setup) in claimed:
                    why = "claimed_before"                      # 🚩's own word at its _claim
                if why is not None:
                    n_unjudged[why] = n_unjudged.get(why, 0) + 1
                    continue                                    # passes through UNCHANGED: no judge, no record, no slot
                F = frames[sym].frame(r.get("frame") or v.primary)   # the read's OWN frame (HIS CALL #14)
                judged.append((sym, setup, r, AUD.judge(r, F, frozen.get(setup) or [], ctx=ctx)))
            per_sym[sym] = (rs, frozen, frozen_before)
        # phase 2 — T1 LAST, over the claimable survivors in 🚩's ring order, against today's claims [C3, C4]
        survivors = [(str(s).upper(), k, r, a) for s, k, r, a in judged if (a or {}).get("aplus") is True]
        slots = AUD.t1_slots(AUD.ring_order(survivors), claimed, claims_fault=claims_fault) if survivors else {}
        taken = 0
        final: dict = {}
        for sym, setup, r, audit in judged:
            if (audit or {}).get("aplus") is True:
                ok, why_t1, vals = slots.get((str(sym).upper(), setup), (None, AUD.NONE_WHY["T1"], {}))
                audit = AUD.with_t1(audit, ok, why_t1, vals)
                taken += 1 if ok is True else 0
            final[(sym, setup)] = (r, audit)
        # phase 3 — the overlay docs, the audited reads, the shadow pass, the #held markers
        held: list = []
        n_aud = n_written = n_t4 = 0
        for sym, (rs, frozen, frozen_before) in per_sym.items():
            setups: dict = {}
            out_rs = dict(rs)                                   # the read objects pass through unchanged
            for setup in GC.SETUPS:
                if (sym, setup) not in final:
                    continue
                r, audit = final[(sym, setup)]
                setups[setup] = {**audit, "entry_bar_t": r.get("entry_bar_t"),
                                 "frame": r.get("frame") or audit.get("frame"), "trigger": r.get("trigger"),
                                 "stop": r.get("stop"), "risk_pct": r.get("risk_pct")}
                n_t4 += 1 if "T4" in _failed_ids(audit) else 0
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
            for sym, setup, r, audit in held:
                c = actx.get(sym) or {}
                AL._record(coll, f"{AL.claim_key(session, sym, setup, v)}#{AUD.HELD_ROW_STATE}", {
                    "date": session_iso, "symbol": sym, "setup": setup, "state": AUD.HELD_ROW_STATE,
                    "kind": v.push_kind_setup, "mode": "shadow", "entry_bar_t": r.get("entry_bar_t"),
                    "frame": r.get("frame"), "trigger": r.get("trigger"), "stop": r.get("stop"),
                    "risk_pct": r.get("risk_pct"), "price": c.get("price"), "audit": _audit_block(audit),
                    "at": now.isoformat()})
            for (sym, setup), (_r, audit) in final.items():     # the shadow claim carries its audit — ONCE
                if audit.get("aplus") is not True:
                    continue
                sk = AL.shadow_key(session, sym, setup, v)
                try:
                    doc = coll.find_one({"_id": sk}) if coll is not None else None
                except Exception as exc:                        # noqa: BLE001 — best-effort, never the pass
                    log.warning("gajjala audit overlay: claim read failed for %s: %s", sk, type(exc).__name__)
                    doc = None
                if isinstance(doc, dict) and "audit" not in doc:
                    AL._settle(coll, sk, {"audit": _audit_block(audit)})
        summary = dict(counts, aplus_original=n_orig, aplus_audited=n_aud, held=len(held))
        if writes_ok:
            gga.set_state(LATEST_ID, {
                "at": now, "session": session_iso, "n_read": len(reads or {}), "n_aplus_original": n_orig,
                "n_aplus_audited": n_aud, "n_held": len(held), "n_overlay_written": n_written,
                "n_unjudged": dict(sorted(n_unjudged.items())),
                "held": [{"symbol": s, "setup": k, "failed": _failed_ids(a)} for s, k, _r, a in held],
                "alerts": counts, "ok": True,
                "best_change_pct": ctx["best_change_pct"], "best_symbol": ctx["best_symbol"],
                "t1_slots_used": len(claimed) + taken, "n_t4_fired_pass": n_t4,
                "t4_session": t4_session(gga, session),
                "rules": [rule.id for rule in AUD.filter_rules()],
                "exit_rules": [rule.id for rule in AUD.exit_rules()],
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


__all__ = ["LATEST_ID", "store_for", "refuse_send", "frozen_update", "wants_overlay", "session_claims",
           "t4_session", "run_step"]
