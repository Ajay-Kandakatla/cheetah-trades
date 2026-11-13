"""📅 Long Term — 🔔 the zone pass: a 🧭 name reaching one of Pankaj's zones (2026-11-12, pkzone spec §3.3).

Ajay 2026-11-12, verbatim: "add an alert list when stocks reach Pankaj's zones and also tell me if you finish the long
term tabs in general". This REVERSES his 2026-09-08 "Remove all of Pankaj's alerts" for HIS ZONES on the 📅 Long Term
🧭 list ONLY — the /pankaj page's own picks stay without alerts.

Rides the existing 5-minute `sepa.cli alerts` pass (09:00–16:30 ET, no crontab edit). Per pass:
  ONE `prices.bulk_snapshot` of the 40 names + ONE `sources.pankaj_closes(..., before=session)` cache read.

"Reached" = a print stamped TODAY sits inside a zone (`criteria.zone_read`, the /pankaj page's pad — ONE engine) AND
the previous market day's close sat outside that zone. The baseline must be dated
`supply_demand.key_levels.prev_market_day(session)` (critique C4): a missing or older close cannot reach and the tab
says so (`stale_text`).

The log is not the latch (critique C2): every pass `$set`s its read on the session's state doc and logs every reach
(`reaches.<SYM|zone>`, first write wins) WHATEVER the push reason. The latch (insert-only, `_id`
"<session>|<SYM>|<zone>") is consulted only when a push is allowed; a duplicate insert = no send and NO write
(critique C1). Results are written once, by the inserting pass. Owner only — one owner-scoped send per reach,
never the all-devices broadcast.
UNMEASURED; Pankaj's zones are his, not a signal. Never raises.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from . import constants as C
from . import criteria as CR
from . import store as ST
from . import words as W

log = logging.getLogger("long_term_list.zone_watch")
ET = ZoneInfo("America/New_York")

R_OVERRIDE, R_SEED, R_NO_SNAPSHOT, R_WINDOW, R_OFF, R_KIND, R_NO_HOOK, R_NO_STORE, R_DRY = (
    "override", "seed", "no_snapshot", "window", "off", "kind", "no_hook", "no_store", "dry")
P_OK, P_STALE, P_NONE = "ok", "stale", "none"          # prior_basis per row [C4]


# ── pure helpers ────────────────────────────────────────────────────────────────────────────────────────────────
def _et(now=None) -> datetime:
    n = now or datetime.now(ET)
    return (n if n.tzinfo else n.replace(tzinfo=ET)).astimezone(ET)


def session_of(now) -> str:
    """The ET date (ISO) of `now`; a naive datetime is read as ET."""
    return _et(now).date().isoformat()


def prev_session(session: str) -> str:
    """The market day before `session` on the shipped calendar — `key_levels.prev_market_day`, the ONE helper
    (`key_level_alerts.py` uses it for the same stale-frame test)."""
    from supply_demand import key_levels as KL
    return KL.prev_market_day(date.fromisoformat(str(session)[:10])).isoformat()


def live_print(raw, session) -> Optional[dict]:
    """{price, epoch, session} of the snapshot's last trade when it is stamped `session` and priced (a finite number
    > 0 — `extended_print` lets NaN through), else None."""
    try:
        from sepa import prices
        ep = prices.extended_print(raw)
    except Exception:                                          # noqa: BLE001
        return None
    if not ep or ep.get("date") != session:
        return None
    px = CR._num(ep.get("price"))
    if px is None or px <= 0:
        return None
    return {"price": px, "epoch": ep.get("epoch"), "session": ep.get("session")}


def read_all(entries, order, snaps, closes, session, prev) -> dict:
    """{SYM: row} in seed order. A reach needs a live print AND a prior close dated `prev` outside that zone."""
    out = {}
    for sym, ent in (entries or {}).items():
        zones = ent.get("zones") or {}
        live = live_print((snaps or {}).get(sym), session)
        prior = (closes or {}).get(sym) or {}
        p_close, p_date = CR._num(prior.get("close")), prior.get("date")
        if p_close is None or not p_date:
            basis_p = P_NONE
        else:
            basis_p = P_OK if (prev is not None and p_date == prev) else P_STALE
        if live:
            now_r = CR.zone_read(zones, live["price"], session, order)
        else:
            now_r = CR.zone_read(zones, p_close, p_date, order)
        prior_r = CR.zone_read(zones, p_close, p_date, order)
        reached = [zk for zk in now_r.get("in") or []
                   if live and basis_p == P_OK and not prior_r.get("unknown") and zk not in (prior_r.get("in") or [])]
        out[sym] = {"basis": "live" if live else ("close" if p_close is not None else "none"),
                    "price": live["price"] if live else p_close,
                    "at_epoch": live["epoch"] if live else None,
                    "date": session if live else p_date,
                    "in": list(now_r.get("in") or []),
                    "prior_basis": basis_p, "prior_close": p_close, "prior_date": p_date,
                    "prior_in": list(prior_r.get("in") or []) if basis_p == P_OK else None,
                    "reached": reached}
    return out


def reached_list(reads, order, entries) -> list:
    """[(SYM, zone)] ordered by zone `order`, then seed order."""
    seq = list(entries or {})
    out = []
    for zk in order or ():
        for sym in seq:
            if zk in ((reads or {}).get(sym) or {}).get("reached") or []:
                out.append((sym, zk))
    return out


def latch_id(session, sym, zone) -> str:
    return f"{session}|{sym}|{zone}"


def reach_key(sym, zone) -> str:
    """One Mongo field-name segment: "." and "$" never reach a field path."""
    return f"{sym}|{zone}".replace(".", "_").replace("$", "_")


def _zone_edges(ent, zone):
    pair = list((ent.get("zones") or {}).get(zone) or (None, None)) + [None, None]
    return CR._num(pair[0]), CR._num(pair[1])


def reach_rec(sym, ent, zone, read, at_iso, at_hhmm, tape_session, push_reason) -> dict:
    """The log row (first write wins on the state doc)."""
    lo, hi = _zone_edges(ent, zone)
    return {"symbol": sym, "his_symbol": ent.get("sheet_symbol") or sym, "zone": zone, "lo": lo, "hi": hi,
            "price": (read or {}).get("price"), "print_epoch": (read or {}).get("at_epoch"),
            "at_iso": at_iso, "at_hhmm": at_hhmm, "tier": ent.get("tier"), "zt": ent.get("zt"),
            "prior_close": (read or {}).get("prior_close"), "prior_close_date": (read or {}).get("prior_date"),
            "tape_session": tape_session, "push_reason": push_reason}


def compose(sym, ent, zone, price, session, tape_session) -> dict:
    """The zone-reach push payload (§3.5). No per-name item list (critique C5): the feed renders the body as is."""
    from supply_demand import zone_edge as ZE
    lo, hi = _zone_edges(ent, zone)
    tag = ZE.tape_tag(tape_session)
    body = W.zone_push_line(sym, price, zone, lo, hi, ent.get("tier"), ent.get("zt"), tag) + "\n" + W.ZONE_PUSH_TAIL
    return {"title": W.zone_push_title(sym, zone), "body": body, "url": C.ZONE_URL, "kind": C.KIND,
            "tag": f"{C.KIND}:zone:{session}:{sym}:{zone}", "ticker": sym, "tickers": [sym]}


def log_session(now) -> str:
    """The session whose log the tab shows: today when the market trades today, else the last market day."""
    from chart_maps import board as B
    return B._session_day(_et(now)).isoformat()


def serve_state(state, now) -> Optional[dict]:
    """The stored pass read when it belongs to today's session and the house clock is not closed, else None."""
    if not isinstance(state, dict) or state.get("session") != session_of(now):
        return None
    try:
        from supply_demand import zone_edge as ZE
        if ZE.session_state(_et(now)) == "closed":
            return None
    except Exception:                                          # noqa: BLE001
        return None
    return state


def _result_state(res: dict) -> str:
    if int(res.get("sent") or 0) > 0:
        return "pushed"
    if "total_targets" in res and int(res.get("total_targets") or 0) == 0:
        return "no_target"
    return "failed"


# ── the pass ────────────────────────────────────────────────────────────────────────────────────────────────────
def run_pass(now=None, *, seed=None, snap_fn: Optional[Callable] = None, closes_fn: Optional[Callable] = None,
             db=None, send: Optional[Callable] = None, owner: Optional[str] = None, dry: bool = False) -> dict:
    """One zone pass. Never raises."""
    try:
        return _run(now, seed=seed, snap_fn=snap_fn, closes_fn=closes_fn, db=db, send=send, owner=owner, dry=dry)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list.zone_watch: pass raised: %s", exc)
        return {"ran": False, "reason": f"error: {type(exc).__name__}"}


def _run(now, *, seed, snap_fn, closes_fn, db, send, owner, dry) -> dict:
    from market_hours import gate
    et = _et(now)
    session = session_of(et)
    if gate.override_active():
        return {"ran": False, "reason": R_OVERRIDE}
    why = gate.closed_reason(et)
    if why:
        return {"ran": False, "reason": why}

    from . import seed as SD
    try:
        seed = seed if seed is not None else SD.load()
        entries = SD.pankaj_entries(seed)
        order = SD.zone_order(seed)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list.zone_watch: seed unreadable: %s", exc)
        return {"ran": False, "reason": R_SEED}

    if snap_fn is None:
        from sepa import prices
        snap_fn = prices.bulk_snapshot
    try:
        snaps = snap_fn(sorted(entries)) or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list.zone_watch: snapshot failed: %s", exc)
        snaps = {}
    if closes_fn is None:
        from . import sources as SRC
        closes_fn = SRC.pankaj_closes
    try:
        closes = closes_fn(list(entries), et, before=session) or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list.zone_watch: closes failed: %s", exc)
        closes = {}
    try:
        prev = prev_session(session)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list.zone_watch: previous session unknown: %s", exc)
        prev = None

    reads = read_all(entries, order, snaps, closes, session, prev)
    reached = reached_list(reads, order, entries)
    n_stale = sum(1 for r in reads.values() if r["prior_basis"] == P_STALE)
    n_live = sum(1 for r in reads.values() if r["basis"] == "live")
    n_in = sum(1 for r in reads.values() if r["in"])

    from supply_demand import zone_edge as ZE
    sender = send
    zc = None
    if not snaps:
        reason = R_NO_SNAPSHOT
    elif not ZE.push_window(et):
        reason = R_WINDOW
    elif C.ZONE_PUSH_MODE != "live":
        reason = R_OFF
    elif not _kind_registered():
        reason = R_KIND
    else:
        if sender is None:
            from . import push as PUSH
            sender = PUSH._hook()
        if sender is None:
            reason = R_NO_HOOK
        elif dry:
            reason = R_DRY
        else:
            reason = None
    if not dry:
        zc = ST.zone_colls(db)
        if zc is None and reason is None:
            reason = R_NO_STORE

    at_iso = et.isoformat(timespec="seconds")
    at_hhmm = et.strftime("%H:%M")
    tape_session = ZE.session_state(et)
    ents = entries
    state_coll = zc["state"] if zc else None
    latch_coll = zc["latch"] if zc else None

    logged = 0
    if not dry and zc is not None:                              # the log — whatever the push reason [C2]
        ST.zone_state_write(state_coll, session, {
            "session": session, "as_of_iso": at_iso, "as_of_hhmm": at_hhmm, "rows": reads, "reason": reason,
            "mode": C.ZONE_PUSH_MODE, "n_names": len(ents), "n_live": n_live, "n_stale": n_stale,
            "prev_session": prev})
        for sym, zk in reached:
            got = ST.zone_reach_add(state_coll, session, reach_key(sym, zk),
                                    reach_rec(sym, ents[sym], zk, reads[sym], at_iso, at_hhmm, tape_session, reason))
            logged += 1 if got is True else 0

    pushed, dup, results = 0, 0, []
    if reason is None:                                          # the push — the latch is the gate [C1]
        to = owner
        if not to:
            from push import subs
            to = subs._owner_email()
        for sym, zk in reached:
            ent, rd = ents[sym], reads[sym]
            lid, rkey = latch_id(session, sym, zk), reach_key(sym, zk)
            lo, hi = _zone_edges(ent, zk)
            got = ST.latch(latch_coll, {
                "_id": lid, "session": session, "symbol": sym, "zone": zk, "lo": lo, "hi": hi,
                "price": rd["price"], "print_epoch": rd["at_epoch"], "at_iso": at_iso, "at_hhmm": at_hhmm,
                "tier": ent.get("tier"), "zt": ent.get("zt"), "prior_close": rd["prior_close"],
                "prior_close_date": rd["prior_date"], "tape_session": tape_session, "kind": C.KIND})
            if got is False:
                dup += 1
                results.append({"id": lid, "state": "dup", "sent": 0})
                continue
            if got is None:
                ST.zone_result_set(state_coll, session, rkey, {"state": "no_store", "sent": 0, "at_hhmm": at_hhmm})
                results.append({"id": lid, "state": "no_store", "sent": 0})
                continue
            try:
                res = sender(owner=to, payload=compose(sym, ent, zk, rd["price"], session, tape_session)) or {}
            except Exception as exc:                           # noqa: BLE001
                log.warning("long_term_list.zone_watch: send %s failed: %s", lid, exc)
                res = {"sent": 0, "failed": 0, "error": type(exc).__name__}
            st = _result_state(res)
            sent = int(res.get("sent") or 0)
            pushed += 1 if st == "pushed" else 0
            ST.zone_result_set(state_coll, session, rkey, {"state": st, "sent": sent, "at_hhmm": at_hhmm})
            results.append({"id": lid, "state": st, "sent": sent})

    return {"ran": True, "session": session, "prev_session": prev, "n_names": len(ents), "n_live": n_live,
            "n_stale": n_stale, "n_in": n_in, "reached": [latch_id(session, s, z) for s, z in reached],
            "logged": logged, "pushed": pushed, "dup": dup, "results": results, "reason": reason, "reads": reads}


def _kind_registered() -> bool:
    try:
        from push import subs
        return C.KIND in (subs.default_prefs() or {})
    except Exception as exc:                                   # noqa: BLE001
        log.warning("long_term_list.zone_watch: prefs unreadable: %s", exc)
        return False


def summary(res) -> str:
    """One log line for the cron pass."""
    r = res or {}
    if not r.get("ran"):
        return f"ran=False reason={r.get('reason')}"
    return (f"ran=True session={r.get('session')} prev={r.get('prev_session')} names={r.get('n_names')} "
            f"live={r.get('n_live')} stale={r.get('n_stale')} in={r.get('n_in')} reached={len(r.get('reached') or [])} "
            f"logged={r.get('logged')} pushed={r.get('pushed')} dup={r.get('dup')} reason={r.get('reason')}")
