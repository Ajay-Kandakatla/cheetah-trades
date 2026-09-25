"""🔑 KEY LEVEL ALERTS (2026-09-25) — the phone half of key levels.

Ajay 2026-09-25 (verbatim): "I wanna know when key levels are broken for a
stock."

WHAT FIRES. A CLOSE through a prior-week, prior-month or 52-week RTH high or
low (`key_levels.PUSH_PERIODS`) on a name in his scope — his holdings plus the
Signals watchlist (`signal_lab.merge_holdings`). The close decides: from
`key_levels.close_confirm_at(session)` (16:05 ET, 13:05 on half days) for
`CLOSE_PUSH_WINDOW_MIN` minutes, a member whose state is `closed_beyond`
(through the level by `key_levels.PIERCE_PCT`, the house stop-sweep minimum)
is claimed and pushed. Day levels never push. An intraday pierce never pushes
(not built — HIS CALL). Every read is PER MEMBER, never per merged line.

LATCH. The claim key is written BEFORE the send (`demand_alerts.claim_key`,
the house `$setOnInsert` primitive) in `CLAIM_COLL`:
  week / month  `KL:{SYM}:{period}:{kind}:{direction}:{as_of}` — once per level
                LIFE and direction. A chop under → back over → under fires twice
                at most; next period's level is a new life.
  year          `KL:{SYM}:year:{kind}:{direction}` — an ARMED latch. The doc
                carries the claimed `level`; the key re-arms (silently, counted
                `rearmed`) only when a session CLOSE is back inside that claimed
                level by `PIERCE_PCT` on the original side. In an uptrend the
                nightly-redefined 52-week high therefore does not re-fire.
A transport failure (or a raise) releases the message's keys; "nobody
targeted" (the kind is OFF) is terminal: claims are KEPT and counted `muted`,
so turning the kind on never replays a backlog.

CARRIER. No crontab line: `zone_edge.check_once` calls `run_pass` at all three
of its in-session exits (store empty, snapshot failed, normal end).

FIRST-SEEN. Every pass (pre / rth / close) stamps the first minute each member
went `through` (and the first `reversal`) into ONE `key_levels.STATE_COLL` doc
per session — the chip's time on the chart comes from here.

SHIPS OFF: `push.subs.default_prefs()["key_level_alert"] is False` and it is
NOT in `OWNER_KEEP_SET` (HIS CALL #1). UNMEASURED: no study stands behind a
close through these levels (`key_levels.MEASURED is False`); every message
says so. Display and notification only — nothing here sizes, gates or enters.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

from . import demand_alerts as DA
from . import key_levels as KL

log = logging.getLogger("supply_demand.key_level_alerts")

KIND = "key_level_alert"
CLAIM_COLL = "key_level_alert_state"
CLOSE_PUSH_WINDOW_MIN = 25
SOURCE = "key_level_alert"

COUNTERS = ("scope", "priced", "stale_print", "no_frame", "stale_frame", "unverified",
            "members", "broken", "pierced", "reversal", "closed_beyond", "rearmed",
            "pushed", "muted", "claimed_elsewhere")

_THROUGH_STATES = ("broken", "pierced", "reversal", "closed_beyond")
_UNMEASURED_SINGLE = "Unmeasured: what happened, not a buy or sell signal."
_UNMEASURED_DIGEST = "Unmeasured — a close through a level, not a signal."


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _coll(name: str):
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[name] if db is not None else None
    except Exception as exc:                                    # noqa: BLE001
        log.debug("key_level_alerts: no mongo for %s: %s", name, exc)
        return None


def _hhmm(t) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _money(x) -> str:
    return f"${float(x):.2f}"


def _pct_vs(close, level) -> Optional[str]:
    c, L = KL._f(close), KL._f(level)
    if c is None or not L:
        return None
    return KL._fmt_pct((c - L) / L * 100.0)


def url_for(symbol: str) -> str:
    return f"/chart-maps?tab=support&symbol={str(symbol).upper()}"


def close_window(session) -> tuple[datetime, datetime]:
    """[start, end) of the close-verdict push window for `session`, ET."""
    start = datetime.combine(session, KL.close_confirm_at(session), tzinfo=KL.ET)
    return start, start + timedelta(minutes=CLOSE_PUSH_WINDOW_MIN)


def in_close_window(now: datetime, session) -> bool:
    et = KL._et(now)
    start, end = close_window(session)
    return KL.phase(et, session) == "close" and start <= et < end


def window_reason(session) -> str:
    start, end = close_window(session)
    return f"close verdicts push {_hhmm(start)}–{_hhmm(end)} ET"


# ---------------------------------------------------------------------------
# pure helpers: keys, latch
# ---------------------------------------------------------------------------
def claim_key_for(member: dict, symbol: str) -> str:
    """week / month: once per level LIFE and direction; year: an armed latch."""
    sym = str(symbol or "").upper()
    period, kind, direction = member["period"], member["kind"], member["direction"]
    if period == "year":
        return f"KL:{sym}:year:{kind}:{direction}"
    return f"KL:{sym}:{period}:{kind}:{direction}:{member.get('as_of')}"


def year_keys(symbol: str) -> list[str]:
    """Every year key a symbol can hold — both kinds, both directions."""
    sym = str(symbol or "").upper()
    return [f"KL:{sym}:year:{k}:{d}" for k in ("high", "low") for d in ("up", "down")]


def year_rearm(claim_doc: Optional[dict], close) -> bool:
    """True when the session close is back inside the CLAIMED level by
    PIERCE_PCT on the original side: an up-claim re-arms on a close under
    level(1-p), a down-claim on a close over level(1+p)."""
    if not isinstance(claim_doc, dict):
        return False
    L, C = KL._pos(claim_doc.get("level")), KL._pos(close)
    if L is None or C is None:
        return False
    side = "resistance" if claim_doc.get("direction") == "up" else "support"
    if claim_doc.get("direction") not in ("up", "down"):
        return False
    return KL._back_inside(side, C, L)


def write_first_seen(coll, session_iso: str, first: dict, now: datetime) -> bool:
    """Replace the session's ONE first-seen doc. The whole doc is written
    (never `$set` on `first.<key>`): a key carries the symbol, and a symbol
    like BRK.B would read as a dotted path. Best-effort, never raises."""
    if coll is None:
        return False
    try:
        coll.replace_one({"_id": str(session_iso)},
                         {"_id": str(session_iso), "first": dict(first),
                          "updated_at": KL._et(now).isoformat()}, upsert=True)
        return True
    except Exception as exc:                                    # noqa: BLE001
        log.warning("key_level_alerts: first-seen write failed: %s", exc)
        return False


def stamp_first_seen(first: dict, symbol: str, members: list, now: datetime) -> bool:
    """Add a `through` stamp the first pass a member is through, and a
    `reversal` stamp the first pass it reads as a reversal. True if changed."""
    hhmm = _hhmm(KL._et(now))
    changed = False
    for m in members:
        st, direction = m.get("state"), m.get("direction")
        if st is None or direction is None:
            continue
        events = []
        if st in _THROUGH_STATES:
            events.append("through")
        if st == "reversal":
            events.append("reversal")
        for ev in events:
            k = KL.first_seen_key(symbol, m.get("id"), direction, ev)
            if k not in first:
                first[k] = hhmm
                changed = True
    return changed


# ---------------------------------------------------------------------------
# pure helpers: words
# ---------------------------------------------------------------------------
def _order(members: list) -> list:
    return sorted(members, key=lambda m: (KL.PERIOD_RANK.get(m.get("period"), 0),
                                          0 if m.get("kind") == "high" else 1))


def _phrase(members: list, close=None) -> str:
    """'under prior-week low $14.80 and prior-month low $14.10' — the word is
    said once for a run of members that share it; with `close`, each level
    carries its own distance '(−1.9%)'."""
    groups: list[tuple[str, list[str]]] = []
    for m in members:
        word = KL._word(m["kind"], m["direction"])
        item = f"{m['name']} {_money(m['price'])}"
        if close is not None:
            p = _pct_vs(close, m["price"])
            if p:
                item += f" ({p})"
        if groups and groups[-1][0] == word:
            groups[-1][1].append(item)
        else:
            groups.append((word, [item]))
    parts: list[str] = []
    for w, items in groups:
        parts.extend([f"{w} {items[0]}"] + items[1:])
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _frozen_note(m: dict, several: bool) -> str:
    if m.get("period") == "year":
        return f"level: {m['name']}, set {KL._day_mmdd(m.get('set_on'), weekday=True)}"
    when = KL._day_mmdd(m.get("as_of"), weekday=True)
    return (f"{m['name']} frozen at the {when} close" if several
            else f"level frozen at the {when} close")


def single_text(symbol: str, members: list, *, close, first_seen: Optional[dict] = None,
                held: bool = True) -> dict:
    """ONE push for one held name. Exact strings, spec §3.7."""
    sym = str(symbol).upper()
    ms = _order(members)
    several = len(ms) > 1
    title = f"{KL.MARK} {sym} closed {_phrase(ms)}"
    if several:
        vs = ", ".join(f"{_pct_vs(close, m['price'])} vs {m['name']}" for m in ms)
        parts = [f"Close {_money(close)} ({vs})"]
    else:
        parts = [f"Close {_money(close)} ({_pct_vs(close, ms[0]['price'])} vs the level)"]
    lead = ms[0]
    first = (first_seen or {}).get(
        KL.first_seen_key(sym, lead.get("id"), lead.get("direction"), "through"))
    if first:
        parts.append(f"first through {first}")
    if held:
        parts.append("your position")
    parts.extend(_frozen_note(m, several) for m in ms)
    parts.append(_UNMEASURED_SINGLE)
    url = url_for(sym)
    return {"title": title, "body": " · ".join(parts), "url": url, "data": {"url": url},
            "kind": KIND, "ticker": sym}


def digest_text(items: list) -> dict:
    """ONE digest: items = [(SYM, members, close)] in send order."""
    items = [(str(s).upper(), _order(ms), c) for s, ms, c in items]
    lead_sym, lead_ms, _ = items[0]
    lead = lead_ms[0]
    title = (f"{KL.MARK} Key levels closed through — {lead_sym} "
             f"{KL._word(lead['kind'], lead['direction'])} {lead['name']}")
    if len(items) > 1:
        title += f" +{len(items) - 1} more"
    lines = [f"{s} closed {_phrase(ms, close=c)}" for s, ms, c in items[:DIGEST_MAX()]]
    if len(items) > DIGEST_MAX():
        lines.append(f"+{len(items) - DIGEST_MAX()} more")
    lines.append(_UNMEASURED_DIGEST)
    url = url_for(lead_sym)
    return {"title": title, "body": "\n".join(lines), "url": url, "data": {"url": url},
            "kind": KIND, "ticker": None, "tickers": [s for s, _m, _c in items]}


def MAX_SINGLES() -> int:
    from . import zone_edge as ZE                      # lazy: zone_edge imports this module lazily
    return int(ZE.MAX_SINGLES_PER_PASS)


def DIGEST_MAX() -> int:
    from . import zone_edge as ZE
    return int(ZE.DIGEST_MAX)


def _name_rank(members: list) -> tuple:
    top = max(KL.PERIOD_RANK.get(m.get("period"), 0) for m in members)
    far = max(abs(KL._f(m.get("beyond_pct")) or 0.0) for m in members)
    return (-top, -far)


# ---------------------------------------------------------------------------
# scope, prices, frames (the only I/O besides the colls)
# ---------------------------------------------------------------------------
def _scope(owner: str) -> dict:
    try:
        from daytrading import signal_lab as SL
        from portfolio.store import list_holdings
        return SL.merge_holdings(SL.get_watchlist(owner), list_holdings(owner))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("key_level_alerts: scope read failed: %s", exc)
        return {"symbols": [], "held": []}


def _default_send(owner, msg, kind):
    from push import sender
    return sender.send_to_user(owner, msg, kind=kind)


# ---------------------------------------------------------------------------
# the pass
# ---------------------------------------------------------------------------
def run_pass(*, snapshot: Optional[dict], now: Optional[datetime], push: bool,
             owner: Optional[str] = None, scope: Optional[dict] = None,
             frames: Optional[dict] = None, first_coll=None, claim_coll=None,
             pass_coll=None, sender: Optional[Callable] = None, dry_run: bool = False) -> dict:
    """One key-level pass on the zone_edge minute. Every input is injectable;
    the zone_edge hook passes snapshot / now / push / dry_run only."""
    t0 = time.time()
    now = KL._et(now)
    counts = {k: 0 for k in COUNTERS}

    # 1. scope
    if owner is None:
        from portfolio.alerts import _resolve_owner
        owner = _resolve_owner()
    sc = scope if isinstance(scope, dict) else _scope(owner)
    symbols = [str(s).upper() for s in (sc.get("symbols") or []) if s]
    held = {str(s).upper() for s in (sc.get("held") or []) if s}
    counts["scope"] = len(symbols)

    session = KL.levels_session(now)
    session_iso = session.isoformat()
    ph = KL.phase(now, session)
    out = {"ran": True, "session": session_iso, "phase": ph, "counts": counts,
           "reason": None, "messages": [], "keys": []}
    if not symbols:
        out["reason"] = "no names in scope (holdings + Signals watchlist)"
        return _finish(out, t0, now, pass_coll, dry_run)

    # 2. prices: ONE extra snapshot call for names the zone_edge snapshot lacks
    snap = dict(snapshot or {})
    missing = [s for s in symbols if not snap.get(s)]
    if missing:
        try:
            from sepa import prices
            snap.update(prices.bulk_snapshot(missing) or {})
        except Exception as exc:                                # noqa: BLE001
            log.warning("key_level_alerts: snapshot failed: %s", exc)

    # 3. levels, per MEMBER (no merge)
    if frames is None:
        try:
            from sepa import prices
            frames = prices.bulk_cached_frames(symbols) or {}
        except Exception as exc:                                # noqa: BLE001
            log.warning("key_level_alerts: cached frames failed: %s", exc)
            frames = {}
    if first_coll is None:
        first_coll = _coll(KL.STATE_COLL)
    first = KL.read_first_seen(session_iso, coll=first_coll) if first_coll is not None else {}
    first = dict(first)
    first_changed = False
    reads: dict = {}                    # SYM -> (members, close)
    for sym in symbols:
        row = KL.row_from_snapshot(snap.get(sym))
        has_row = KL._has_row(row)
        if has_row:
            if KL.fresh_print(row, now, session) is not None:
                counts["priced"] += 1
            else:
                counts["stale_print"] += 1
        df = frames.get(sym)
        closed = KL.closed_frame(df, session) if df is not None else None
        if closed is None or len(closed) == 0:
            counts["no_frame"] += 1
            continue
        if KL._norm_index(closed)[-1].date() < KL.prev_market_day(session):
            counts["stale_frame"] += 1
            continue
        note, verified = KL.verify_last_row(closed, row if has_row else None)
        if note:
            counts["stale_frame"] += 1
            continue
        if not verified:
            counts["unverified"] += 1
        ref_close = KL._f(closed["close"].iloc[-1])
        if ref_close is None:
            counts["no_frame"] += 1
            continue
        levels = KL.period_levels(closed, session, KL.PUSH_PERIODS)
        members = KL.read_levels(levels, symbol=sym, ref_close=ref_close, row=row, now=now,
                                 session=session, first_seen=first)
        counts["members"] += len(members)
        for m in members:
            st = m.get("state")
            if st in ("broken", "pierced", "reversal", "closed_beyond"):
                counts[st] += 1
        # 4. first-seen stamps (pre / rth / close)
        if ph is not None and stamp_first_seen(first, sym, members, now):
            first_changed = True
        reads[sym] = (members, row.get("close"))
    if first_changed and not dry_run:
        write_first_seen(first_coll, session_iso, first, now)

    # 5. close tier, the only tier
    if not in_close_window(now, session):
        out["reason"] = window_reason(session)
        return _finish(out, t0, now, pass_coll, dry_run)
    if claim_coll is None:
        claim_coll = _coll(CLAIM_COLL)
    act = bool(push) and not dry_run

    # 5a. year re-arm first: ONE find for every year key of the scope
    ykeys = [k for s in reads for k in year_keys(s)]
    claimed_year: dict = {}
    if claim_coll is not None and ykeys:
        try:
            for d in claim_coll.find({"_id": {"$in": ykeys}}):
                claimed_year[str(d.get("_id"))] = d
        except Exception as exc:                                # noqa: BLE001
            log.warning("key_level_alerts: year claim read failed: %s", exc)
    for key, doc in list(claimed_year.items()):
        sym = key.split(":")[1]
        close = (reads.get(sym) or ((), None))[1]
        if year_rearm(doc, close):
            counts["rearmed"] += 1
            if act:
                DA.release_key(claim_coll, key)
            claimed_year.pop(key, None)

    # 5b. fire: claim every closed_beyond member BEFORE sending
    cands = [(sym, m, claim_key_for(m, sym)) for sym, (members, _c) in reads.items()
             for m in members
             if m.get("state") == "closed_beyond" and m.get("period") in KL.PUSH_PERIODS]
    out["keys"] = [k for _s, _m, k in cands]
    # dry run / push off: ONE read says which keys are held; a year key held
    # and not re-armed above is in `claimed_year` already
    held_keys = set() if act else (set(claimed_year) | _existing(
        claim_coll, [k for k in out["keys"] if ":year:" not in k]))
    fired: dict = {}                    # SYM -> [(member, key)]
    for sym, m, key in cands:
        close = reads[sym][1]
        if not act:                                     # read, never write
            if key in held_keys:
                counts["claimed_elsewhere"] += 1
            else:
                fired.setdefault(sym, []).append((m, key))
            continue
        doc = {"symbol": sym, "period": m["period"], "kind": m["kind"],
               "direction": m["direction"], "level": float(m["price"]),
               "as_of": m.get("as_of"), "session": session_iso,
               "close": KL._f(close), "sent_at": now.isoformat(), "source": SOURCE}
        if DA.claim_key(claim_coll, key, doc):
            fired.setdefault(sym, []).append((m, key))
        else:
            counts["claimed_elsewhere"] += 1

    # 5c. group per NAME: holdings -> singles, the rest + overflow -> ONE digest
    order = sorted(fired, key=lambda s: _name_rank([m for m, _k in fired[s]]))
    singles = [s for s in order if s in held][:MAX_SINGLES()]
    rest = [s for s in order if s not in singles]
    msgs = []
    for s in singles:
        members = [m for m, _k in fired[s]]
        msgs.append((single_text(s, members, close=reads[s][1], first_seen=first, held=True),
                     [k for _m, k in fired[s]]))
    if rest:
        items = [(s, [m for m, _k in fired[s]], reads[s][1]) for s in rest]
        msgs.append((digest_text(items), [k for s in rest for _m, k in fired[s]]))
    send = sender or _default_send
    for msg, keys in msgs:
        out["messages"].append({"title": msg["title"], "body": msg["body"], "keys": keys})
        if not act:
            continue
        try:
            res = send(owner, msg, KIND)
        except Exception as exc:                                # noqa: BLE001
            log.warning("key_level_alerts: send failed: %s", exc)
            res = DA.transport_failed(exc)
        if not DA._terminal(res):
            for k in keys:
                DA.release_key(claim_coll, k)
            continue
        if (res.get("sent") or 0) > 0:
            counts["pushed"] += 1
        else:
            counts["muted"] += 1
    return _finish(out, t0, now, pass_coll, dry_run)


def _existing(coll, keys: list) -> set:
    """The subset of `keys` already claimed — ONE `$in` read (dry runs only;
    a live pass learns it from claim_key itself). A failure reads empty."""
    if coll is None or not keys:
        return set()
    try:
        return {str(d.get("_id")) for d in coll.find({"_id": {"$in": list(keys)}})}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("key_level_alerts: claim read failed: %s", exc)
        return set()


def _finish(out: dict, t0: float, now: datetime, pass_coll, dry_run: bool) -> dict:
    """Record the pass on /alerts (never in a dry run) and stamp the seconds."""
    out["seconds"] = round(time.time() - t0, 2)
    if not dry_run:
        from . import alert_status as AS
        AS.record_pass(KIND, out["counts"], now, coll=pass_coll, reason=out.get("reason"))
    return out


__all__ = ["KIND", "CLAIM_COLL", "CLOSE_PUSH_WINDOW_MIN", "COUNTERS", "run_pass",
           "claim_key_for", "year_keys", "year_rearm", "single_text", "digest_text",
           "write_first_seen", "stamp_first_seen", "close_window", "in_close_window",
           "window_reason", "url_for"]
