"""🏁 🩳 SI follow-up — what every name the 🩳 list held did in the sessions after it was listed (2026-11-26, SPEC
sishares rev 2 §3.5, WP be-track).

Ajay 2026-11-26, verbatim: "I think the short interest theory is actually working may be its a bias for me on the ones
its working out but lets track them in our list of SI. and maintain a track record of our stocks".

A LEDGER, UNMEASURED: counts only, no claim, no comparison group (names that were not on the 🩳 list on the same days
are not followed), no push, no gate, no sort outside its own tables.

Facts: ONE small doc per market session, `si_follow|YYYY-MM-DD` in gajjala_state (st.get_state / set_state, the fault-
aware si_track.state_read) — `{date, facts: [fact…] by symbol, version, updated_at}`. A fact is the day of ONE name:
its state, prior close, 09:30–20:00 high / low, last regular close, his +40% grade, and — on a session the name was
LISTED — the base the later sessions are read against. The 1 / 5 / 10-session outcomes, the per-name history and the
counts are DERIVED from those facts + the stored 🏁 rows, never stored twice.

Engines (one per concept, every one si_track's): the bars = si_track.day_read (the stored read doc when complete, else
the 1-minute stand-in, whose prior-day tail carries the prior close); the grade = si_track.outcome (the ONE grading
engine — prior close order, split guard, runners' +WIN_PCT rule); the budget = a si_track.Budget(MAX_LOADS) of its OWN
(the house's per-job pattern; the ledger's budget is never touched). A 🏁 row with outcome "ok" is COPIED (its split
check already passed — no budget).

Who is followed (`tracked`): every name with a 🏁 row on the session or on any of the FOLLOW_SESSIONS market sessions
before it, plus the owner's pins (`PINS_ID`, written ONLY by the script's --pin — followed, shown apart, NEVER in a
count).

Counts (`follow_stats`) run ONLY over listing days whose EVERY listed name is read through the horizon (a selected
sample — winners read, the rest not — would otherwise make the counts lie); a session the name did not trade is a
counted row (not a win). The unread name-days are printed. Definitions of base / run / low / new high are MINE (§7 #11).
Not advice.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Callable, Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import si_track as SIT

log = logging.getLogger("chart_maps.gajjala.si_follow")

# ── constants (every number by name) ──────────────────────────────────────────────────────────────────────────────
HORIZONS = (1, GC.LEDGER_SPAN_SESSIONS, GC.LEDGER_SPAN_SESSIONS_LONG)        # 1 = the next session; then by name
FOLLOW_SESSIONS = HORIZONS[-1]
DAY_HORIZON = GC.LEDGER_SPAN_SESSIONS        # the ONE forward column of the day table  [C15]
STATE_FMT = "si_follow|{date}"               # TRANSPORT — gajjala_state, one doc per session
PINS_ID = "si_follow_pins"                   # TRANSPORT — {"names": [{"symbol", "since": iso, "added_at": ts}]}  [C10]
VERSION = 1                                  # TRANSPORT
FACT_STATES = SIT.OUTCOME_STATES + ("no_trade",)
LOADS = ("reads", "loaded", "no_bars", "failed", "deferred")
FACT_KEYS = ("state", "retry", "load", "prev_close", "high", "low", "close", "high_pct", "winner", "bars_src",
             "base", "base_kind", "base_at")                 # the last three only on a session the name was LISTED
BASE_KEYS = FACT_KEYS[-3:]
BASE_KINDS = ("regular_close", "after_listing")
FWD_STATES = ("pending", "unread", "split", "ok")
FWD_KEYS = ("state", "n_read", "wins", "new_high", "close_pct", "run_pct", "low_pct", "no_trade", "ungraded")
COUNT_KEYS = ("again", "new_high", "closed_above", "no_trade", "split", "no_base", "ungraded")
NIGHT_KEYS = ("sessions", "facts", "pending", "no_trade", "loads", "split_calls", "deferred_cap", "faults")
DASH = SIT.DASH
WIN = "✅"


class Deferred(RuntimeError):
    """Raised by `stored_only` — the 1-minute seam was not asked (the stored-reads-only run): status "deferred"."""


def stored_only(sym, day):
    """The 1-minute seam of a stored-reads-only run: never calls a provider; every load reads "deferred"."""
    raise Deferred(sym)


# ── served words (every number filled from a constant at call time) ───────────────────────────────────────────────
TITLE = "🏁 What the 🩳 names did after they were listed · UNMEASURED"
SUMMARY_TEXT = "🔭 After the listing · {names} names · {days} listing days · followed {n} sessions"
EMPTY_SUMMARY = "🔭 After the listing · nothing followed yet"
CAVEAT = ("These are the names we listed — winners and losers both count. It is a record of what happened next, not a "
          "test. Names that were not on the 🩳 list on the same days are not followed, so this cannot say whether "
          "short interest made the difference. UNMEASURED.")
ASOF_TEXT = "followed nightly at {at} ET · through {date}"
LINE_TEXT = ("Within {k} {sess} after a listing day — counted on {d} of {e} listing days read in full · {n} name-days · "
             "{m} names: another +{pct:g}% day {a} of {n} · a new high {b} of {n} · closed above the base {c} of {n} · "
             "{t} did not trade a session · {s} cut short by a split · {u} with no base")
FIRST_TEXT = ("First listing only: another +{pct:g}% day {a} of {n} · a new high {b} of {n} · closed above the base "
              "{c} of {n} · {m} names{tail}")
FIRST_CI_TAIL = " · interval on names {lo}–{hi}"
FIRST_FEW_TAIL = " · too few names for an interval"
WAIT_TEXT = "{w} listing days are not counted yet: {u} name-days are not read in full."
NONE_TEXT = ("Within {k} {sess} after a listing day — no listing day is read in full yet ({u} name-days not read); "
             "nothing is counted.")
DUE_NONE_TEXT = "Within {k} {sess} after a listing day — no listing day has had {k} {sess} yet; nothing is counted."
NAMES_HEADS_FMT = [["ticker", "Ticker"], ["first", "First listed"], ["last", "Last listed"], ["days", "Days listed"],
                   ["wins_listed", "+{pct:g}% days while listed"], ["since", "+{pct:g}% days since first listed"]]
SINCE_TEXT = "{w} of {n} sessions read"
PINNED_LABEL = "Pinned by you — followed, never counted"
PINNED_HEADS_FMT = [["ticker", "Ticker"], ["since", "Pinned since"], ["days", "Days on the 🩳 list"],
                    ["read", "Sessions read"], ["wins", "+{pct:g}% days"]]
PINNED_EMPTY_TEXT = "No name is pinned."
PINNED_WAIT = "fills at the next {at} ET night"
SHOWN_TEXT = "Showing the first {lim} names of {n}."
PENDING_TEXT = ("{k} name-days are not read yet — the {at} ET night retries them for {n} market days.")
RULE_LABEL = "ⓘ how this is followed"
EMPTY_TEXT = "No listing day is recorded yet — the {at} ET night follows every name the 🩳 list holds."
CELL_PENDING = "pending"
CELL_UNREAD = "{n} of {k} read"
CELL_SPLIT = "split after {n}"
CELL_NEW_HIGH = "new high"
CELL_NO_TRADE = "{n} no trade"


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
_f, _pos, _d, _iso = SIT._f, SIT._pos, SIT._d, SIT._iso


def _bool(v) -> Optional[bool]:
    return v if isinstance(v, bool) else None


def _sess(k: int) -> str:
    return "session" if k == 1 else "sessions"


def _stamp(now) -> str:
    return SIT._stamp(now)


def _prev_n(d: date, n: int) -> list:
    """`d` and the n market sessions before it, newest first."""
    out = [d]
    while len(out) < n + 1:
        out.append(SIT._prev_day(out[-1]))
    return out


def _next_n(d: date, n: int) -> list:
    """The n market sessions after `d`, oldest first."""
    out = []
    x = d
    while len(out) < n:
        x = SIT._next_day(x)
        out.append(x)
    return out


# ── pins (his word only) [C10] ────────────────────────────────────────────────────────────────────────────────────
def _plain_symbol(raw) -> Optional[str]:
    """store.broker_symbol (the house symbol check, length by GC.BROKER_SYMBOL_MAX_LEN) AND plain A–Z / . / -."""
    from chart_maps.gajjala import store as ST
    s = ST.broker_symbol(raw)
    if s is None or any(ch.isdigit() for ch in s):
        return None
    return s


def _pins_doc(st) -> Optional[dict]:
    return SIT.state_read(st, PINS_ID)


def _clean_pins(doc) -> list:
    out = []
    for p in (doc or {}).get("names") or []:
        if not isinstance(p, dict):
            continue
        sym = _plain_symbol(p.get("symbol"))
        since = _d(p.get("since"))
        if sym is None or since is None:
            continue
        out.append({"symbol": sym, "since": since.isoformat(), "added_at": p.get("added_at")})
    out.sort(key=lambda p: p["symbol"])
    return out


def pins(st) -> list:
    """The owner's pins (symbol A–Z), [] when none or on a read fault (a pin is never guessed)."""
    return _clean_pins(_pins_doc(st))


def pin(st, symbol, since, now) -> dict:
    """Add / move one pin — called ONLY by the script's --pin (his word). A junk symbol or date, or a faulted read of
    the pins doc → refused, nothing written. -> {"ok", "error", "names"}."""
    sym = _plain_symbol(symbol)
    d = _d(since) if isinstance(since, (str, date)) else None
    if sym is None:
        return {"ok": False, "error": "symbol", "names": pins(st)}
    if d is None:
        return {"ok": False, "error": "since", "names": pins(st)}
    doc = _pins_doc(st)
    if doc is None:
        return {"ok": False, "error": "read_fault", "names": []}
    names = [p for p in _clean_pins(doc) if p["symbol"] != sym]
    names.append({"symbol": sym, "since": d.isoformat(), "added_at": _stamp(now)})
    names.sort(key=lambda p: p["symbol"])
    st.set_state(PINS_ID, {"names": names, "version": VERSION})
    return {"ok": True, "error": None, "names": names}


def unpin(st, symbol) -> dict:
    sym = _plain_symbol(symbol)
    if sym is None:
        return {"ok": False, "error": "symbol", "names": pins(st)}
    doc = _pins_doc(st)
    if doc is None:
        return {"ok": False, "error": "read_fault", "names": []}
    cur = _clean_pins(doc)
    names = [p for p in cur if p["symbol"] != sym]
    if len(names) == len(cur):
        return {"ok": False, "error": "not_pinned", "names": cur}
    st.set_state(PINS_ID, {"names": names, "version": VERSION})
    return {"ok": True, "error": None, "names": names}


# ── who is followed ───────────────────────────────────────────────────────────────────────────────────────────────
def tracked(st, session, *, index=None, pin_list=None, cache: Optional[dict] = None) -> list:
    """Symbols (A–Z) with a 🏁 row on `session` or on any of the FOLLOW_SESSIONS MARKET sessions before it, plus every
    pin whose `since` is on or before `session`. RAISES si_track.ReadFault on an index / session read fault."""
    d = _d(session)
    have = set(index if index is not None else SIT.index_dates(st))
    syms = set()
    for x in _prev_n(d, FOLLOW_SESSIONS):
        if x.isoformat() not in have:
            continue
        if cache is not None and x.isoformat() in cache:
            got = cache[x.isoformat()]
        else:
            got = SIT.session_doc(st, x, strict=True).get("rows") or []
            if cache is not None:
                cache[x.isoformat()] = got
        for r in got:
            if isinstance(r, dict) and isinstance(r.get("symbol"), str) and r["symbol"]:
                syms.add(r["symbol"].upper())
    for p in (pin_list if pin_list is not None else pins(st)):
        if p["since"] <= d.isoformat():
            syms.add(p["symbol"])
    return sorted(syms)


# ── the loader [C3] ───────────────────────────────────────────────────────────────────────────────────────────────
def loader(load_1m, status: dict) -> Callable:
    """The 1-minute seam wrapped the runchart way: dt_data.clear_fetch_failed() → load → status[(sym, iso)] =
    "failed" (None and dt_data.last_fetch_failed(), or a raise) · "no_bars" (the provider answered, zero bars) ·
    "loaded" · "deferred" (the stored-reads-only seam). A failed / empty / deferred load returns None."""
    from daytrading import data as dt_data

    def load(sym, day):
        k = (sym, _iso(day))
        try:
            dt_data.clear_fetch_failed()
            df = load_1m(sym, day)
        except Deferred:
            status[k] = LOADS[4]
            return None
        except Exception as exc:                                # noqa: BLE001
            log.warning("si follow: 1-minute load %s %s failed: %s", sym, k[1], type(exc).__name__)
            status[k] = LOADS[3]
            return None
        if df is None or not len(df):
            status[k] = LOADS[3] if dt_data.last_fetch_failed() else LOADS[2]
            return None
        status[k] = LOADS[1]
        return df
    return load


# ── one fact ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _low(doc, day: date) -> Optional[float]:
    """min `l` of the 09:30–20:00 bars (`s` absent or after hours, starting at or after ET_RTH_OPEN)."""
    rth = SIT._hhmm(SIT.ET_RTH_OPEN)
    lows = [_pos(b.get("l")) for b in SIT.extended_bars(SIT.day_bars(doc, day)) if SIT.bar_start(b) >= rth]
    lows = [x for x in lows if x is not None]
    return min(lows) if lows else None


def base_of(doc, row, day) -> tuple:
    """PURE — (base, kind, at) of a LISTED session. cut = the day's regular close (a half day is right):
    listed before the session, or listed_at < cut → the day's last regular 5-minute close ("regular_close");
    listed_at ≥ cut → the close of the FIRST 5-minute bar starting at or after listed_at ("after_listing", at = its
    start); no such bar, no row, or first listed with no listed_at → (None, None, None) — never guessed."""
    none = (None, None, None)
    d = _d(day)
    if not isinstance(row, dict) or d is None or not isinstance(doc, dict):
        return none
    cut = SIT._hhmm(SIT._reg_close(d))
    la = row.get("listed_at") if isinstance(row.get("listed_at"), str) and row.get("listed_at") else None
    if row.get("listed_before") is True or (la is not None and la < cut):
        v = SIT._last_regular_close(doc, "bars5", d)
        return (v, BASE_KINDS[0], None) if v is not None else none
    if la is None:
        return none
    for b in SIT.day_bars(doc, d):
        start = SIT.bar_start(b)
        if start >= la:
            v = _pos(b.get("c"))
            return (v, BASE_KINDS[1], start) if v is not None else none
    return none


def _blank_fact(listed: bool) -> dict:
    keys = FACT_KEYS if listed else FACT_KEYS[:-3]
    return dict.fromkeys(keys)


def day_fact(ctx, sym: str, day, status: dict, *, row=None) -> dict:
    """One name-day [C2 C5]. `SIT.outcome` stays the ONE grading engine; this only prepares what it is handed:
    1. a 🏁 row of that day with outcome "ok" → prior close / high / high_pct / winner COPIED (no budget); low / close
       from the day's read (free when the stored read is complete);
    2. otherwise si_track.day_read FIRST (the stored read when complete, else the 1-minute stand-in whose prior-day
       tail carries the prior close), then SIT.outcome on it. No read and the provider answered with no bars →
       "no_trade" (terminal, a counted row); no read otherwise → "no_bars", retried.
    retry = a retry state, OR the budget refused a unit during this fact, OR a load this fact used failed — so a
    "no_prev_close" left by a refused / failed prior-day load is retried, and one after the provider answered is not."""
    d = _d(day)
    listed = isinstance(row, dict)
    f = _blank_fact(listed)
    before = ctx.budget.deferred
    stored = ctx.st.get_read(d, sym)
    doc, src = SIT.day_read(ctx, sym, d, stored)
    used = [] if src == "reads" else [(sym, d.isoformat())]
    if doc is not None and src != "reads":
        used.append((sym, SIT._prev_day(d).isoformat()))
    copied = listed and row.get("outcome_state") == "ok"
    if copied:
        f.update(state="ok", prev_close=_pos(row.get("prev_close")), high=_pos(row.get("high")),
                 high_pct=_f(row.get("high_pct")), winner=_bool(row.get("winner")),
                 bars_src=row.get("bars_src") if isinstance(row.get("bars_src"), str) else src)
    elif doc is None:
        got = status.get((sym, d.isoformat()))
        traded = bool(SIT.day_bars(stored, d)) if isinstance(stored, dict) else False
        if got == LOADS[2] and not traded:
            f.update(state=FACT_STATES[-1], retry=False, load=LOADS[2])
            return f
        f.update(state="no_bars", retry=True, load=got if got in LOADS else LOADS[4])
        return f
    else:
        o = SIT.outcome(ctx, sym, d, read_doc=doc, prev_read_doc=ctx.st.get_read(SIT._prev_day(d), sym),
                        scan_doc=ctx.scan_doc(sym, d), avg_vol_50=None)
        f.update(state=o.get("outcome_state"), prev_close=o.get("prev_close"), high=o.get("high"),
                 high_pct=o.get("high_pct"), winner=_bool(o.get("winner")), bars_src=o.get("bars_src") or src)
    if doc is not None:
        f["low"] = _low(doc, d)
        f["close"] = SIT._last_regular_close(doc, "bars5", d)
        f["load"] = LOADS[0] if src == "reads" else LOADS[1]
    else:                                                       # copied row, but no read for low / close / base
        got = status.get((sym, d.isoformat()))
        f["load"] = got if got in LOADS else LOADS[4]
    failed = any(status.get(k) == LOADS[3] for k in used)
    f["retry"] = bool(f["state"] in SIT.OUTCOME_RETRY or ctx.budget.deferred > before or failed
                      or (copied and doc is None))
    if listed:
        f["base"], f["base_kind"], f["base_at"] = base_of(doc, row, d)
    return f


def _terminal(f) -> bool:
    return isinstance(f, dict) and f.get("retry") is False and f.get("state") in FACT_STATES


def _facts_of(doc) -> dict:
    out = {}
    for f in (doc or {}).get("facts") or []:
        if isinstance(f, dict) and isinstance(f.get("symbol"), str) and f["symbol"]:
            out[f["symbol"].upper()] = f
    return out


def read_facts(st, isos, have=None) -> dict:
    """{iso: {SYM: fact}} — one fault-aware read per session; RAISES si_track.ReadFault on a read fault. `have` = facts
    already read this build ({iso: {SYM: fact}}): a session it holds is taken from it, never read again."""
    out = {}
    for iso in isos:
        if isinstance(have, dict) and _iso(iso) in have:
            out[_iso(iso)] = have[_iso(iso)]
            continue
        sid = STATE_FMT.format(date=_iso(iso))
        doc = SIT.state_read(st, sid)
        if doc is None:
            raise SIT.ReadFault(sid)
        out[_iso(iso)] = _facts_of(doc)
    return out


def fact_days(dates, now) -> list:
    """Every market session from the first recorded listing day through FOLLOW_SESSIONS sessions after the last one,
    never past tonight — the sessions a count can need."""
    ds = sorted({_d(x) for x in dates or [] if _d(x) is not None})
    if not ds:
        return []
    end = SIT.tonight(now)
    last = _next_n(ds[-1], FOLLOW_SESSIONS)[-1]
    stop = min(end, last)
    out, x = [], ds[0]
    while x <= stop:
        if SIT._is_market_day(x):
            out.append(x.isoformat())
        x = SIT._next_day(x)
    return out


# ── the night [C4] ────────────────────────────────────────────────────────────────────────────────────────────────
def _ctx(st, now, *, load_1m, split_lookup, max_loads, share, status):
    ctx = SIT.Ctx(st, now, load_1m=loader(load_1m or SIT.default_load_1m, status), split_lookup=split_lookup,
                  budget=SIT.Budget(SIT.MAX_LOADS if max_loads is None else max_loads))
    if share is not None:                                       # a load / split check the ledger already made is free
        for k, v in (getattr(share, "raw", None) or {}).items():
            if v is not None and len(v):
                ctx.raw[k] = v
        for k, v in (getattr(share, "memo", None) or {}).items():
            if v is not None:
                ctx.memo[k] = v
        if split_lookup is None and getattr(share, "_split", None) is not None:
            ctx._split = share._split
    return ctx


def _sessions(now) -> list:
    return [d for d in SIT.lookback(SIT.tonight(now)) if SIT._ended(d, now)]


def fill_night(st, now, *, load_1m=None, split_lookup=None, max_loads=None, share=None, write=True) -> dict:
    """The ended sessions of the look-back, OLDEST first; inside a session the tracked names with no stored terminal
    fact, A–Z; one set_state per session that changed. Its OWN SIT.Budget(SIT.MAX_LOADS) (`max_loads` names another
    cap); `share` = the ledger's Ctx — its loaded frames and split answers are copied in. Never raises."""
    out = {"sessions": [], "facts": 0, "pending": 0, "no_trade": 0, "loads": 0, "split_calls": 0, "deferred_cap": 0,
           "faults": []}
    try:
        status: dict = {}
        ctx = _ctx(st, now, load_1m=load_1m, split_lookup=split_lookup, max_loads=max_loads, share=share,
                   status=status)
        try:
            have = SIT.index_dates(st)
        except SIT.ReadFault:
            out["faults"].append("index_read")
            return out
        pin_list = pins(st)
        stamp = _stamp(now)
        cache: dict = {}
        for d in _sessions(now):
            iso = d.isoformat()
            try:
                sid = STATE_FMT.format(date=iso)
                cur = SIT.state_read(st, sid)
                if cur is None:                                 # never overwrite on a faulted read
                    out["faults"].append("read:" + iso)
                    continue
                facts = _facts_of(cur)
                rows = {}
                if iso in have:
                    rows = {str(r.get("symbol") or "").upper(): r
                            for r in SIT.session_doc(st, d, strict=True).get("rows") or [] if isinstance(r, dict)}
                changed = 0
                for sym in tracked(st, d, index=have, pin_list=pin_list, cache=cache):
                    old = facts.get(sym)
                    row = rows.get(sym)
                    if _terminal(old) and not (row is not None and "base_kind" not in old):
                        continue
                    f = day_fact(ctx, sym, d, status, row=row)
                    f["symbol"] = sym
                    facts[sym] = f
                    changed += 1
                    out["facts"] += 1
                    out["pending"] += 1 if f.get("retry") else 0
                    out["no_trade"] += 1 if f.get("state") == FACT_STATES[-1] else 0
                if changed:
                    out["sessions"].append(iso)
                    if write:
                        st.set_state(sid, {"date": iso, "facts": [facts[s] for s in sorted(facts)],
                                           "version": VERSION, "updated_at": stamp})
            except Exception as exc:                            # noqa: BLE001 — the next session still runs
                log.warning("si follow: %s failed: %s", iso, type(exc).__name__)
                out["faults"].append("session:%s:%s" % (iso, type(exc).__name__))
        out.update(loads=ctx.budget.loads, split_calls=ctx.budget.split_calls, deferred_cap=ctx.budget.deferred)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("si follow: the night failed: %s", type(exc).__name__)
        out["faults"].append("night:%s" % type(exc).__name__)
    return out


def plan(st, now, *, sessions=None) -> dict:
    """PURE reads (no outside call, no write): per ended look-back session (or per `sessions`, ISO — the backfill's
    range) the facts a run would ask, how many are free (a complete stored read), how many need minutes, and the units
    (1-minute loads, deduplicated across the run as its memo does, + split checks; a copied 🏁 row asks no split) vs
    SIT.MAX_LOADS. An upper bound where a load would come back empty."""
    out = {"sessions": [], "units": 0, "cap": SIT.MAX_LOADS, "over_cap": False, "faults": []}
    try:
        have = SIT.index_dates(st)
    except SIT.ReadFault:
        out["faults"].append("index_read")
        return out
    pin_list = pins(st)
    loads: set = set()
    cache: dict = {}
    days = _sessions(now) if sessions is None else [_d(x) for x in sessions if _d(x) is not None]
    for d in days:
        iso = d.isoformat()
        line = {"session": iso, "wanted": 0, "free": 0, "minutes": 0, "loads": 0, "splits": 0, "units": 0}
        cur = SIT.state_read(st, STATE_FMT.format(date=iso))
        if cur is None:
            out["faults"].append("read:" + iso)
            continue
        facts = _facts_of(cur)
        rows = {}
        if iso in have:
            rows = {str(r.get("symbol") or "").upper(): r
                    for r in SIT.session_doc(st, d, strict=True).get("rows") or [] if isinstance(r, dict)}
        prev = SIT._prev_day(d)
        for sym in tracked(st, d, index=have, pin_list=pin_list, cache=cache):
            old, row = facts.get(sym), rows.get(sym)
            if _terminal(old) and not (row is not None and "base_kind" not in old):
                continue
            line["wanted"] += 1
            stored = st.get_read(d, sym)
            done = SIT.complete(stored, d)
            if done:
                line["free"] += 1
            else:
                line["minutes"] += 1
                for k in ((sym, iso), (sym, prev.isoformat())):
                    if k not in loads:
                        loads.add(k)
                        line["loads"] += 1
            if isinstance(row, dict) and row.get("outcome_state") == "ok":
                continue                                        # copied: its split check already passed
            if done:
                pc, _src = SIT.prior_close_of(stored, st.get_read(prev, sym), _scan(st, sym, d), d)
                if pc is None:
                    continue
            line["splits"] += 1
        line["units"] = line["loads"] + line["splits"]
        out["units"] += line["units"]
        out["sessions"].append(line)
    out["over_cap"] = out["units"] > SIT.MAX_LOADS
    return out


def _scan(st, sym, d):
    return next((x for x in st.scan_docs([d]) if str(x.get("symbol") or "").upper() == sym), None)


# ── the forward read (PURE) ───────────────────────────────────────────────────────────────────────────────────────
def _read(f) -> bool:
    return _terminal(f)


def forward(row, base_fact, after, horizons=HORIZONS) -> dict:
    """PURE — {k: {state, n_read, wins, new_high, close_pct, run_pct, low_pct, no_trade, ungraded}} per horizon.
    `after` = the FOLLOW_SESSIONS MARKET sessions after the listing day as (iso, fact | None, ended).
    state: "pending" (the k-th session has not ended) · "unread" (ended; the listing day's own fact or a fact of the k
    is missing or `retry`) · "split" (a terminal split fact among the k — numbers from the sessions before it only) ·
    "ok". wins = sessions whose own `winner` is True · new_high = a later 09:30–20:00 high STRICTLY above the listing
    day's high (None with no listing high) · close_pct = the k-th session's last regular close vs the base (None until
    read, or with no base) · run_pct / low_pct = best high / worst low of the read sessions vs the base · no_trade /
    ungraded = sessions the name did not trade / with bars and no prior close."""
    after = list(after or [])
    base = _pos(base_fact.get("base")) if isinstance(base_fact, dict) else None
    lh = _pos(row.get("high")) if isinstance(row, dict) else None
    if lh is None and isinstance(base_fact, dict):
        lh = _pos(base_fact.get("high"))
    base_ok = _read(base_fact)
    out = {}
    for k in horizons:
        w = after[:k]
        r = dict.fromkeys(FWD_KEYS)
        r.update(n_read=0, wins=0, no_trade=0, ungraded=0)
        ended = len(w) == k and bool(w[-1][2])
        state = None
        highs, lows = [], []
        if not base_ok:
            state = "unread"
        for i, (_iso_, f, _e) in enumerate(w):
            if state is not None:
                break
            if not _read(f):
                state = "unread"
                break
            if f.get("state") == "split":
                state = "split"
                break
            r["n_read"] += 1
            if f.get("winner") is True:
                r["wins"] += 1
            if f.get("state") == FACT_STATES[-1]:
                r["no_trade"] += 1
            if f.get("state") == "no_prev_close":
                r["ungraded"] += 1
            h, lo = _pos(f.get("high")), _pos(f.get("low"))
            if h is not None:
                highs.append(h)
            if lo is not None:
                lows.append(lo)
            if i == k - 1:
                c = _pos(f.get("close"))
                r["close_pct"] = SIT._pct(c, base) if c is not None and base is not None else None
        if not ended:
            state = "pending"
        r["state"] = state or "ok"
        if r["state"] != "ok":
            r["close_pct"] = None
        r["new_high"] = (any(h > lh for h in highs)) if lh is not None else None
        r["run_pct"] = SIT._pct(max(highs), base) if highs and base is not None else None
        r["low_pct"] = SIT._pct(min(lows), base) if lows and base is not None else None
        out[k] = r
    return out


def after_of(listing_iso, sym, facts, now) -> list:
    d = _d(listing_iso)
    return [(x.isoformat(), (facts.get(x.isoformat()) or {}).get(sym), SIT._ended(x, now))
            for x in _next_n(d, FOLLOW_SESSIONS)]


def _fwd_of(row, facts, now, horizons=HORIZONS) -> dict:
    iso, sym = row.get("date"), str(row.get("symbol") or "").upper()
    return forward(row, (facts.get(iso) or {}).get(sym), after_of(iso, sym, facts, now), horizons)


def _good_rows(rows) -> list:
    return [r for r in rows or [] if isinstance(r, dict) and isinstance(r.get("date"), str) and _d(r["date"])
            and isinstance(r.get("symbol"), str) and r["symbol"]]


# ── names, pins, counts (PURE) ────────────────────────────────────────────────────────────────────────────────────
def names(rows, facts) -> list:
    """PURE — per listed name: first / last listing day, days listed, +WIN_PCT days while listed (the 🏁 rows'
    `winner`), and since its first listing day: sessions READ (a terminal fact) and their wins. Last listed DESC, then
    ticker (MINE, §7 #14)."""
    by: dict = {}
    for r in _good_rows(rows):
        by.setdefault(r["symbol"].upper(), []).append(r)
    out = []
    for sym, rs in by.items():
        ds = sorted({r["date"] for r in rs})
        n = w = 0
        for iso, fs in (facts or {}).items():
            f = (fs or {}).get(sym)
            if iso > ds[0] and _read(f):
                n += 1
                w += 1 if f.get("winner") is True else 0
        out.append({"symbol": sym, "first": ds[0], "last": ds[-1], "days": len(ds),
                    "wins_listed": sum(1 for r in rs if r.get("winner") is True), "since_n": n, "since_wins": w})
    out.sort(key=lambda x: x["symbol"])
    out.sort(key=lambda x: x["last"], reverse=True)
    return out


def pinned(pin_list, rows, facts) -> list:
    """PURE — per pin: since, days on the 🩳 list since then, sessions read since then, +WIN_PCT days. Never counted."""
    out = []
    good = _good_rows(rows)
    for p in pin_list or []:
        sym, since = p.get("symbol"), p.get("since")
        if not isinstance(sym, str) or not isinstance(since, str):
            continue
        days = len({r["date"] for r in good if r["symbol"].upper() == sym and r["date"] >= since})
        n = w = 0
        for iso, fs in (facts or {}).items():
            f = (fs or {}).get(sym)
            if iso >= since and _read(f):
                n += 1
                w += 1 if f.get("winner") is True else 0
        out.append({"symbol": sym, "since": since, "days": days, "read": n, "wins": w})
    return out


def _study():
    return SIT._study()


def follow_stats(rows, facts, now) -> dict:
    """PURE but the lazy bootstrap — per horizon k, per recorded listing day D: `due` once the k-th market session
    after D has ended; `complete` when EVERY listed row of D is "ok" or "split" at k. Counts run over complete days
    only; N = every listed name-day of those days (no-trade, split and no-base rows included). Also the first-listing-
    only counts (each name's first listed day) with the names interval (GS.cluster_ci at SIT.MIN_NAMES). Pins are
    never in a count."""
    GS = _study()
    good = _good_rows(rows)
    by_day: dict = {}
    first: dict = {}
    for r in good:
        sym = r["symbol"].upper()
        by_day.setdefault(r["date"], {})[sym] = r
        if sym not in first or r["date"] < first[sym]:
            first[sym] = r["date"]
    fwd = {(iso, sym): _fwd_of(r, facts or {}, now) for iso, rs in by_day.items() for sym, r in rs.items()}
    out = {"horizons": list(HORIZONS), "by": {}, "interval_ok": GS is not None, "version": VERSION}
    for k in HORIZONS:
        line = {"days_due": 0, "days_complete": 0, "n": 0, "names": 0, "unread_days": 0, "unread_rows": 0}
        line.update(dict.fromkeys(COUNT_KEYS, 0))
        fst = {"n": 0, "names": 0, "again": 0, "new_high": 0, "closed_above": 0, "ci": None}
        syms, f_vals, f_syms = set(), [], []
        for iso in sorted(by_day):
            rs = by_day[iso]
            states = {sym: fwd[(iso, sym)][k]["state"] for sym in rs}
            if any(s == "pending" for s in states.values()):
                continue
            line["days_due"] += 1
            if not all(s in ("ok", "split") for s in states.values()):
                line["unread_days"] += 1
                line["unread_rows"] += sum(1 for s in states.values() if s == "unread")
                continue
            line["days_complete"] += 1
            for sym, r in rs.items():
                x = fwd[(iso, sym)][k]
                bf = (facts.get(iso) or {}).get(sym) or {}
                vals = {"again": x["wins"] > 0, "new_high": x["new_high"] is True,
                        "closed_above": (x["close_pct"] or 0) > 0, "no_trade": x["no_trade"] > 0,
                        "split": x["state"] == "split", "no_base": _pos(bf.get("base")) is None,
                        "ungraded": x["ungraded"] > 0}
                line["n"] += 1
                syms.add(sym)
                for key in COUNT_KEYS:
                    line[key] += 1 if vals[key] else 0
                if first.get(sym) == iso:
                    fst["n"] += 1
                    for key in ("again", "new_high", "closed_above"):
                        fst[key] += 1 if vals[key] else 0
                    f_vals.append(1.0 if vals["again"] else 0.0)
                    f_syms.append(sym)
        line["names"] = len(syms)
        fst["names"] = len(set(f_syms))
        if GS is not None and fst["names"] >= SIT.MIN_NAMES:
            fst["ci"] = GS.cluster_ci(f_vals, f_syms)
        line["first"] = fst
        out["by"][str(k)] = line
    return out


# ── served ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _pct_word(x) -> str:
    v = _f(x)
    return DASH if v is None else SIT._signed(v, "%")


def cells(row, fwd) -> dict:
    """{"f<DAY_HORIZON>": text} — the day table's ONE follow-up cell [C15]."""
    key = "f%d" % DAY_HORIZON
    r = (fwd or {}).get(DAY_HORIZON) if isinstance(fwd, dict) else None
    if not isinstance(r, dict) or r.get("state") not in FWD_STATES:
        return {key: DASH}
    st = r["state"]
    if st == "pending":
        return {key: CELL_PENDING}
    if st == "unread":
        return {key: CELL_UNREAD.format(n=int(r.get("n_read") or 0), k=DAY_HORIZON)}
    if st == "split":
        return {key: CELL_SPLIT.format(n=int(r.get("n_read") or 0))}
    parts = ["%d%s" % (int(r.get("wins") or 0), WIN)]
    if r.get("new_high") is True:
        parts.append(CELL_NEW_HIGH)
    for word, k in (("close", "close_pct"), ("run", "run_pct"), ("low", "low_pct")):
        if _f(r.get(k)) is not None:
            parts.append("%s %s" % (word, _pct_word(r[k])))
    if int(r.get("no_trade") or 0):
        parts.append(CELL_NO_TRADE.format(n=int(r["no_trade"])))
    return {key: " · ".join(parts)}


def _cell_days(by_day, now) -> list:
    """The sessions the shown rows' DAY_HORIZON cells can need: oldest shown day → DAY_HORIZON sessions after the
    newest, never past tonight."""
    ds = sorted({_d(iso) for iso, _rows in by_day or [] if _d(iso) is not None})
    if not ds:
        return []
    stop = min(SIT.tonight(now), _next_n(ds[-1], DAY_HORIZON)[-1])
    out, x = [], ds[0]
    while x <= stop:
        if SIT._is_market_day(x):
            out.append(x.isoformat())
        x = SIT._next_day(x)
    return out


def cell_facts(st, by_day, now) -> dict:
    """The facts of every session the shown rows' cells can need — read ONCE per 🩳 block build and handed to both
    `forwards` and `served` (2026-11-26 refix). RAISES on a read fault."""
    return read_facts(st, _cell_days(by_day, now))


def forwards(st, by_day, now, *, facts=None) -> dict:
    """{(iso, SYM): forward at DAY_HORIZON} for the shown rows. Mongo reads only; RAISES on a read fault. `facts` =
    `cell_facts(st, by_day, now)` already read — no read is made for a session it holds."""
    facts = read_facts(st, _cell_days(by_day, now), have=facts)
    out = {}
    for iso, rows in by_day or []:
        for r in rows or []:
            if isinstance(r, dict) and isinstance(r.get("symbol"), str):
                out[(iso, r["symbol"])] = _fwd_of(dict(r, date=iso), facts, now, (DAY_HORIZON,))
    return out


def rule_text() -> str:
    """Every number read from a constant at CALL time."""
    w = SIT.clock_words()
    hs = ", ".join(str(k) for k in HORIZONS[:-1]) + " and %d" % HORIZONS[-1]
    return ("A listing day is a session the 🩳 list held the name (its 🏁 row). Each listed name is followed for the "
            "next %d market sessions and read at %s sessions. Another +%g%% day = a session whose %s–%s high is at "
            "least +%g%% over that session's own prior close (the 🏁 rule). A new high = a later %s–%s high above the "
            "listing day's high. The base is the listing day's last regular 5-minute close, or — for a name first "
            "listed at or after the regular close — the close of the first 5-minute bar at or after its listing "
            "time; with no listing time on file there is no base. Run / low = the best high / worst low of the "
            "sessions read vs the base; close = the last regular close of the last session vs the base. A listing "
            "day is counted only when every name listed that day is read through that session; a session the name "
            "did not trade is counted and is never a +%g%% day. Read nightly at %s ET and retried for %d market days. "
            "Pinned names are followed and never counted."
            % (FOLLOW_SESSIONS, hs, SIT.WIN_PCT, w["open"], w["end"], SIT.WIN_PCT, w["open"], w["end"], SIT.WIN_PCT,
               GC.LEDGER_GRADE_AT_ET, SIT.LOOKBACK_SESSIONS))


def _ci_word(x) -> str:
    return SIT._pct_text(x)


def base_lines(fs) -> list:
    """The served count lines, per horizon (see LINE_TEXT / WAIT_TEXT / NONE_TEXT)."""
    out = []
    by = (fs or {}).get("by") if isinstance(fs, dict) else None
    for k in HORIZONS:
        x = (by or {}).get(str(k)) if isinstance(by, dict) else None
        if not isinstance(x, dict):
            continue
        g = {key: int(x.get(key) or 0) for key in ("days_due", "days_complete", "n", "names", "unread_days",
                                                   "unread_rows") + COUNT_KEYS}
        sess = _sess(k)
        if g["days_complete"]:
            out.append(LINE_TEXT.format(k=k, sess=sess, d=g["days_complete"], e=g["days_due"], n=g["n"], m=g["names"],
                                        pct=SIT.WIN_PCT, a=g["again"], b=g["new_high"], c=g["closed_above"],
                                        t=g["no_trade"], s=g["split"], u=g["no_base"]))
            fx = x.get("first") if isinstance(x.get("first"), dict) else {}
            ci = fx.get("ci")
            tail = FIRST_CI_TAIL.format(lo=_ci_word(ci[0]), hi=_ci_word(ci[1])) \
                if isinstance(ci, (list, tuple)) and len(ci) == 2 else FIRST_FEW_TAIL
            out.append(FIRST_TEXT.format(pct=SIT.WIN_PCT, a=int(fx.get("again") or 0), b=int(fx.get("new_high") or 0),
                                         c=int(fx.get("closed_above") or 0), n=int(fx.get("n") or 0),
                                         m=int(fx.get("names") or 0), tail=tail))
            if g["days_due"] > g["days_complete"]:
                out.append(WAIT_TEXT.format(w=g["days_due"] - g["days_complete"], u=g["unread_rows"]))
        elif g["days_due"]:
            out.append(NONE_TEXT.format(k=k, sess=sess, u=g["unread_rows"]))
        else:
            out.append(DUE_NONE_TEXT.format(k=k, sess=sess))
    return out


def _heads(fmt) -> list:
    return [[k, label.format(pct=SIT.WIN_PCT)] for k, label in fmt]


def _name_rows(nm) -> list:
    out = []
    for x in nm or []:
        if not isinstance(x, dict) or not isinstance(x.get("symbol"), str) or not x["symbol"]:
            continue
        out.append({"symbol": x["symbol"], "href": SIT._href(x["symbol"]),
                    "cells": {"ticker": x["symbol"], "first": str(x.get("first") or DASH),
                              "last": str(x.get("last") or DASH), "days": str(int(x.get("days") or 0)),
                              "wins_listed": str(int(x.get("wins_listed") or 0)),
                              "since": SINCE_TEXT.format(w=int(x.get("since_wins") or 0),
                                                         n=int(x.get("since_n") or 0))}})
    return out


def _pinned_rows(pin_list, stored) -> list:
    by = {x.get("symbol"): x for x in stored or [] if isinstance(x, dict)}
    out = []
    for p in pin_list or []:
        x = by.get(p["symbol"])
        if isinstance(x, dict) and x.get("since") == p["since"]:
            c = {"ticker": p["symbol"], "since": p["since"], "days": str(int(x.get("days") or 0)),
                 "read": str(int(x.get("read") or 0)), "wins": str(int(x.get("wins") or 0))}
        else:                                                   # pinned after the last night's counts
            wait = PINNED_WAIT.format(at=GC.LEDGER_GRADE_AT_ET)
            c = {"ticker": p["symbol"], "since": p["since"], "days": wait, "read": DASH, "wins": DASH}
        out.append({"symbol": p["symbol"], "href": SIT._href(p["symbol"]), "cells": c})
    return out


def served(st, dates, rows_by_day, now, *, facts=None) -> Optional[dict]:
    """The 🏁 block's `follow` key — Mongo reads only (the stats doc the night wrote; the live counts when it holds
    none). RAISES on a read fault (si_track serves `follow` None). `facts` = `cell_facts(st, rows_by_day, now)`
    already read — a session it holds is never read again."""
    dates = sorted({x for x in dates or [] if isinstance(x, str)})
    cf = read_facts(st, _cell_days(rows_by_day, now), have=facts)
    sd = st.get_state(SIT.STATS_ID) or {}
    fs, nm, pd_ = sd.get("follow"), sd.get("names"), sd.get("pinned")
    if not isinstance(fs, dict) or not isinstance(nm, list):
        rows = SIT.all_rows(st)
        facts = read_facts(st, fact_days(dates, now), have=cf)
        fs, nm = follow_stats(rows, facts, now), names(rows, facts)
        pd_ = pinned(pins(st), rows, facts)
    pin_list = pins(st)
    nrows = _name_rows(nm)
    lim = int(SIT.ROWS_MAX)
    pend = 0
    for _iso_, fs_ in cf.items():
        pend += sum(1 for f in fs_.values() if isinstance(f, dict) and f.get("retry") is True)
    out = {"title": TITLE, "caveat": CAVEAT, "rule_label": RULE_LABEL, "rule_text": rule_text(),
           "names_heads": _heads(NAMES_HEADS_FMT), "pinned_label": PINNED_LABEL,
           "pinned_heads": _heads(PINNED_HEADS_FMT), "pinned": _pinned_rows(pin_list, pd_),
           "pinned_empty_text": None if pin_list else PINNED_EMPTY_TEXT,
           "names": nrows[:lim], "shown_text": SHOWN_TEXT.format(lim=lim, n=len(nrows)) if len(nrows) > lim else None,
           "pending_text": PENDING_TEXT.format(k=pend, at=GC.LEDGER_GRADE_AT_ET, n=SIT.LOOKBACK_SESSIONS)
           if pend else None,
           "asof_text": ASOF_TEXT.format(at=GC.LEDGER_GRADE_AT_ET, date=dates[-1]) if dates else None,
           "base_lines": base_lines(fs), "summary_text": None, "empty_text": None}
    if not dates or not nrows:
        out.update(summary_text=EMPTY_SUMMARY, empty_text=EMPTY_TEXT.format(at=GC.LEDGER_GRADE_AT_ET))
    else:
        out["summary_text"] = SUMMARY_TEXT.format(names=len(nrows), days=len(dates), n=FOLLOW_SESSIONS)
    return out


SERVED_KEYS = ("summary_text", "title", "caveat", "asof_text", "base_lines", "names_heads", "names", "pinned_label",
               "pinned_heads", "pinned", "pinned_empty_text", "shown_text", "pending_text", "rule_label", "rule_text",
               "empty_text")

__all__ = ["HORIZONS", "FOLLOW_SESSIONS", "DAY_HORIZON", "STATE_FMT", "PINS_ID", "VERSION", "FACT_STATES", "LOADS",
           "FACT_KEYS", "BASE_KINDS", "CAVEAT", "SERVED_KEYS", "Deferred", "stored_only", "pins", "pin", "unpin",
           "tracked", "loader", "day_fact", "base_of", "fill_night", "plan", "forward", "names", "pinned",
           "follow_stats", "served", "cells", "forwards", "cell_facts", "read_facts", "fact_days", "rule_text", "base_lines"]
