"""👀 Gajjala's Watch — the 🤖 auto section: the ONE engine (spec ggwauto 2026-11-17 §3.2, WP-A).

Ajay 2026-11-17, verbatim: "Can you add more stocks in to watch list basically I need portentials from Gajjals's 1 min
and regular and also Audited potentials with good volume to Watchlist on an interval.. Remove as they are not
progressing"

WHAT. Once a minute (inside the watch's own minute loop, under its lease — loop.run_iteration) `step` reads the STORED
🚩 5-min (GG5) and 🚩 1-min (GG1) read docs, the ONE shared scan set and GG5's 🧠 tracker docs — zero Massive fetches —
and keeps a SECOND doc `{_id: C.AUTO_DOC_ID}` in the list collection (his own doc `{_id: "owner"}` is never written
here). The 🧪 board BORROWS GG5's reads and potentials (variant.GGA.borrows), so a GG5 potential is tagged with both.

ADD (only inside the 🚩 pass window, `run.in_window`). A 🧠 potential (`potential.potential_kind`, the board's own test)
of a LISTED read (the board's filter, applied only when the listed set is non-empty — tab.build) with today's volume at
or over C.AUTO_MIN_VOLUME (GG's K11 floor). Today's volume [C2] = the scan row's (the number the 🧠 board orders by), else
GG5's tracker `last.session_volume` (the number K11 read on the pass); neither → unknown → refused, counted. A name on his
list, or one he × removed this session, is never added. Up to C.AUTO_MAX_SYMBOLS; a louder potential never displaces an
auto name. [C4] Order = the order added, frozen: one minute's batch lands in `potential.order_key` order; nothing moves
afterwards (the manual board's "his list order" rule).

REMOVE. [C1] When every board reads ↩️ back under / ✖️ stop printed (`breakout_state.block` on the stored read doc's own
tile bars) — at once, with the card's own line. ⏸ waiting (holding above the trigger, no new high since) KEEPS: it is
the consolidation after GG's entry signal. [C3] When the name has been a 🧠 potential NOWHERE (and no broke read keeps
it) for C.AUTO_DROP_GRACE_SEC — the first such step stamps `dropped_since`; a potential again clears it. A name he ➕ adds
to his own list leaves the auto section ("on_your_list"). An UNKNOWN (a read fault, the 1-min `off_chart`, a board that
could not be read) never removes — unknown is not gone (R1: `store._find` swallows faults, so every read here is its own
try/except).

SESSION. The doc carries its session; a new session clears entries, removed and dismissed (HIS CALL #5). `dismiss` (his ×,
api.py DELETE) performs that reset itself on a stale doc [C7].

Writes are ONE compare-and-set `update_one` on `{_id, rev}` with `$set` (whole arrays). Every stamp is the caller's `now`
(never the wall clock). Never a fetch, never a push, never a claim. UNMEASURED — display / selection only.
"""
from __future__ import annotations

import copy
import logging
from datetime import date, datetime, timezone
from typing import Optional

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import breakout_state as BS
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ema_cross as EX
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import scanner as SC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V

from . import colls as CO
from . import constants as C
from .store import _CAS_TRIES

log = logging.getLogger("chart_maps.gajjala_watch.auto")

REASONS = ("not_progressing", "dropped", "dismissed", "on_your_list")      # the stored removal reasons
STEP_REASONS = ("list_unreadable", "boards_unreadable", "closed", "write_failed")
STATES_DISMISS = ("dismissed", "absent", "error")
SKIPPED_KEYS = ("volume_unknown", "under_floor")
BY_LOOP = "loop"
_REMOVE_WORDS = {"back_under": "↩️ back under", "stop_printed": "✖️ stop printed"}
_KEEP_WORDS = {"waiting": "⏸ waiting above its trigger"}


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _iso(session) -> str:
    if isinstance(session, datetime):
        return session.date().isoformat()
    return session.isoformat() if isinstance(session, date) else str(session or "")[:10]


def _up(sym) -> str:
    return sym.strip().upper() if isinstance(sym, str) else ""


def _utc(t) -> Optional[datetime]:
    """A stored stamp as an aware UTC datetime (Mongo hands back naive UTC); anything else → None."""
    if not isinstance(t, datetime):
        return None
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)


def _variants() -> dict:
    return {v.key: v for v in V.VARIANTS}


def _borrowers() -> dict:
    """{source key: the read source it borrows} — derived from variant.borrows (🧪 borrows GG5's reads), never typed."""
    vs = _variants()
    return {k: V.GG5.key for k in C.AUTO_SOURCES
            if k not in C.AUTO_READ_SOURCES and k in vs and ST.READS in vs[k].borrows}


def _default_stores() -> dict:
    """{read source key: its real store} — GG5 → store.default(), GG1 → store.for_variant(V.GG1)."""
    vs = _variants()
    return {k: (ST.default() if V.is_gg5(vs[k]) else ST.for_variant(vs[k])) for k in C.AUTO_READ_SOURCES}


def _words():
    from . import payload as PL                                  # lazy: payload reads this module lazily too
    return PL


def _rec(sym, now, reason, *, state=None, source=None, text=None) -> dict:
    return {"symbol": sym, "at": now, "at_et": PT._hhmm(now), "reason": reason, "state": state, "source": source,
            "text": text}


# ── the doc ───────────────────────────────────────────────────────────────────────────────────────────────────────
def read_doc(cs) -> Optional[dict]:
    """The auto doc ({} when missing); None on a read fault (no "list" handle, or find_one raised). Never raises."""
    c = cs.get("list") if isinstance(cs, dict) else None
    if c is None:
        return None
    try:
        d = c.find_one({"_id": C.AUTO_DOC_ID})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 🤖: auto doc unreadable: %s", type(exc).__name__)
        return None
    return d if isinstance(d, dict) else {}


def entries_of(doc, session_iso: str) -> list:
    """The doc's entries (dicts with a str symbol) IF the doc is of `session_iso`, else []."""
    if not isinstance(doc, dict) or doc.get("session") != session_iso:
        return []
    return [e for e in doc.get("entries") or [] if isinstance(e, dict) and isinstance(e.get("symbol"), str)
            and e["symbol"].strip()]


def current_symbols(cs, session_iso: str) -> list:
    """The entries' symbols (house spelling, fold-de-duplicated, stored order) when the doc is of `session_iso`; a fault
    or another session → []."""
    out, keys = [], set()
    for e in entries_of(read_doc(cs), session_iso):
        k = CO.fold(e["symbol"])
        if k not in keys:
            keys.add(k)
            out.append(CO.house(e["symbol"]))
    return out


def _cas(coll, doc: dict, fields: dict) -> bool:
    """ONE update_one: lands ONLY IF the stored doc is still `doc` (its `rev`; a missing doc: still missing). False =
    another write landed in between. A failing write RAISES."""
    rev = doc.get("rev") if isinstance(doc, dict) else None
    fields = dict(fields, rev=(rev if isinstance(rev, int) and not isinstance(rev, bool) else 0) + 1)
    if doc:
        flt = {"_id": C.AUTO_DOC_ID, "rev": rev} if "rev" in doc else {"_id": C.AUTO_DOC_ID, "rev": {"$exists": False}}
        res = coll.update_one(flt, {"$set": fields}, upsert=False)
        return bool(getattr(res, "matched_count", 0))
    from pymongo.errors import DuplicateKeyError
    try:
        res = coll.update_one({"_id": C.AUTO_DOC_ID, "rev": {"$exists": False}}, {"$set": fields}, upsert=True)
    except DuplicateKeyError:
        return False
    return bool(getattr(res, "matched_count", 0)) or getattr(res, "upserted_id", None) is not None


# ── the boards (read-only) ────────────────────────────────────────────────────────────────────────────────────────
def shared_sets(session, store=None) -> dict:
    """[C5][F25] Read ONCE per step from the GG5 store (every variant's scan set is GG5's): `listed` (the board's filter;
    {} on a raise — empty hides nothing), `scan_by` {SYM: scan doc}, `trackers` {SYM: the GG5 tracker doc with the
    newest last.at} or None on a READ FAULT (store.potentials' own rule)."""
    st = store if store is not None else ST.default()
    try:
        listed = SC.listed_symbols(st, session) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 🤖: listed read failed: %s", type(exc).__name__)
        listed = {}
    scan_by = {_up(d.get("symbol")): d for d in st.scan_docs([session]) if isinstance(d, dict) and _up(d.get("symbol"))}
    docs = st.potentials(session)
    trackers: Optional[dict] = None
    if docs is not None:
        trackers = {}
        floor = datetime.min.replace(tzinfo=timezone.utc)
        for d in docs:
            sym = _up(d.get("symbol")) if isinstance(d, dict) else ""
            if not sym:
                continue
            at = _utc((d.get("last") or {}).get("at") if isinstance(d.get("last"), dict) else None) or floor
            cur = trackers.get(sym)
            if cur is None or at > cur[0]:
                trackers[sym] = (at, d)
        trackers = {s: d for s, (_at, d) in trackers.items()}
    return {"listed": {_up(k): v for k, v in listed.items() if _up(k)}, "scan_by": scan_by, "trackers": trackers}


def volume_of(sym, scan_row, trackers) -> tuple:
    """[C2] (volume, source): the scan row's volume ("scan"), else the GG5 tracker's `last.session_volume` ("tracker"),
    else (None, None) — unknown. The scan row wins whenever it holds a number (the 🧠 board's own number first)."""
    v = PT._num((scan_row or {}).get("volume")) if isinstance(scan_row, dict) else None
    if v is not None:
        return v, C.AUTO_VOLUME_SOURCES[0]
    doc = trackers.get(_up(sym)) if isinstance(trackers, dict) else None
    last = doc.get("last") if isinstance(doc, dict) else None
    v = PT._num(last.get("session_volume")) if isinstance(last, dict) else None
    if v is not None:
        return v, C.AUTO_VOLUME_SOURCES[1]
    return None, None


def _read_docs(st, iso: str):
    """The session's read docs of one store, projected (symbol, setups, ctx — never the tile bars). None on a fault."""
    c = st.coll(ST.READS) if st is not None else None
    if c is None:
        return None
    try:
        return list(c.find({"date": iso}, {"symbol": 1, "setups": 1, "ctx": 1}))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 🤖: reads unreadable: %s", type(exc).__name__)
        return None


def potential_sets(session, *, shared: dict, stores: Optional[dict] = None) -> Optional[dict]:
    """{source key: {SYM: cand}} for C.AUTO_READ_SOURCES — None when ANY store cannot be read (the whole answer is
    unknown, never "none"). cand = the setup with the least potential.order_key among the name's 🧠 setups."""
    stores = stores if stores is not None else _default_stores()
    iso = _iso(session)
    listed = shared.get("listed") or {}
    scan_by = shared.get("scan_by") or {}
    out: dict = {}
    for key in C.AUTO_READ_SOURCES:
        docs = _read_docs(stores.get(key), iso)
        if docs is None:
            return None
        cands: dict = {}
        for doc in docs:
            sym = _up(doc.get("symbol")) if isinstance(doc, dict) else ""
            if not sym or (listed and sym not in listed):             # [C5] the board's filter, only when non-empty
                continue
            setups = doc.get("setups") if isinstance(doc.get("setups"), dict) else {}
            kinds = {s: PT.potential_kind(setups.get(s)) for s in GC.SETUPS}
            also = [s for s in GC.SETUPS if kinds[s]]
            if not also:
                continue
            scan_row = (scan_by.get(sym) or {}).get("last")
            vol, vsrc = volume_of(sym, scan_row, shared.get("trackers"))
            best = None
            for s in also:
                values = PT.tell_values(sym, s, ctx=doc.get("ctx"), scan_row=scan_row, ah_prev=None, prev_scan=None,
                                        also=also)
                values = dict(values, volume=vol)
                ok = PT.order_key(kinds[s], values, s, sym)
                if best is None or ok < best[0]:
                    best = (ok, s, values)
            ok, s, values = best
            cands[sym] = {"setup": s, "kind": kinds[s], "volume": vol, "volume_source": vsrc,
                          "float_shares": values.get("float_shares"), "order_key": ok,
                          "also": [x for x in also if x != s]}
        out[key] = cands
    return out


def good_volume(cand) -> bool:
    """A finite volume at or over C.AUTO_MIN_VOLUME; None / NaN → False (fail closed)."""
    v = PT._num((cand or {}).get("volume")) if isinstance(cand, dict) else None
    return v is not None and v >= C.AUTO_MIN_VOLUME


def merge(sets) -> list:
    """[(order_key, SYM, cand, sources)] across the read sources, one per fold; `sources` in C.AUTO_SOURCES order with
    every borrower ("gga") added when the source it borrows from is present; order_key = the least; sorted."""
    by: dict = {}
    for key in C.AUTO_READ_SOURCES:
        for sym, cand in ((sets or {}).get(key) or {}).items():
            k = CO.fold(sym)
            if k not in by:
                by[k] = [cand["order_key"], CO.house(sym), cand, {key}]
                continue
            e = by[k]
            e[3].add(key)
            if cand["order_key"] < e[0]:
                e[0], e[2] = cand["order_key"], cand
    bor = _borrowers()
    out = []
    for ok, sym, cand, present in by.values():
        srcs = [s for s in C.AUTO_SOURCES if s in present or bor.get(s) in present]
        out.append((ok, sym, cand, srcs))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


# ── progress (one name, every board) ──────────────────────────────────────────────────────────────────────────────
def _source_verdict(doc, v, first_setup) -> dict:
    """One board's verdict on one read doc: keep (a potential / a broke read still progressing) · remove (↩️ / ✖️, with
    the card's line) · unknown (off_chart) · dropped (no potential, no broke read; `word` = the read's state word)."""
    setups = doc.get("setups") if isinstance(doc.get("setups"), dict) else {}
    if any(PT.potential_kind(setups.get(s)) for s in GC.SETUPS):
        return {"verdict": "keep"}
    removes, unknown, keep, broke = [], False, False, False
    for s in GC.SETUPS:
        read = setups.get(s)
        if not (isinstance(read, dict) and read.get("broke") is True and read.get("state") not in BS.SKIP_STATES
                and isinstance(read.get("entry_bar_t"), str)):
            continue
        broke = True
        b = BS.block(read, doc, v)
        st = b.get("state") if isinstance(b, dict) else None
        if b is None or st in C.AUTO_KEEP_STATES:
            keep = True
        elif st in C.AUTO_REMOVE_STATES:
            removes.append({"state": st, "text": b.get("text")})
        else:
            unknown = True                                     # off_chart (or a word this module does not know)
    if keep:
        return {"verdict": "keep"}
    if unknown:
        return {"verdict": "unknown"}
    if broke and removes:
        return {"verdict": "remove", **removes[0]}
    states = [(setups.get(s) or {}).get("state") for s in GC.SETUPS if isinstance(setups.get(s), dict)]
    own = (setups.get(first_setup) or {}).get("state") if isinstance(setups.get(first_setup), dict) else None
    pick = own if isinstance(own, str) and own else next((x for x in states if isinstance(x, str) and x != "none"),
                                                          states[0] if states else None)
    return {"verdict": "dropped", "state": pick, "word": PT.state_word(pick, None)}


def progress(sym, session, *, stores: Optional[dict] = None, shared: Optional[dict] = None,
             entry: Optional[dict] = None) -> dict:
    """{keep, unknown, reason, state, source, text, word} for one auto name over every read source. KEEP when ANY source
    keeps or is unknown / a fault; REMOVE only when every source reads remove / dropped — "not_progressing" when at least
    one reads ↩️ / ✖️ (words: the entry's first source's, else the first source with the line), else "dropped"."""
    stores = stores if stores is not None else _default_stores()
    shared = shared or {}
    listed = shared.get("listed") or {}
    entry = entry if isinstance(entry, dict) else {}
    first_src = next(iter(entry.get("sources") or []), None)
    first_src = _borrowers().get(first_src, first_src)
    first_setup = entry.get("setup")
    vs = _variants()
    sym = _up(sym)
    gone = bool(listed) and sym not in listed                     # [C5] only a NON-EMPTY listed set says "gone"
    verdicts: dict = {}
    for key in C.AUTO_READ_SOURCES:
        if gone:
            verdicts[key] = {"verdict": "dropped", "state": "graveyard", "word": PT.state_word("graveyard", None)}
            continue
        st = stores.get(key)
        c = st.coll(ST.READS) if st is not None else None
        if c is None:
            verdicts[key] = {"verdict": "fault"}
            continue
        try:
            doc = c.find_one({"_id": ST.key(session, sym)})
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala watch 🤖: read of %s unreadable: %s", sym, type(exc).__name__)
            verdicts[key] = {"verdict": "fault"}
            continue
        if not isinstance(doc, dict):
            verdicts[key] = {"verdict": "dropped", "state": None, "word": PT.state_word(None, None)}
            continue
        verdicts[key] = _source_verdict(doc, vs[key], first_setup)
    vals = [verdicts[k]["verdict"] for k in C.AUTO_READ_SOURCES]
    out = {"keep": True, "unknown": False, "reason": None, "state": None, "source": None, "text": None, "word": None}
    if "keep" in vals:
        return out
    if "fault" in vals or "unknown" in vals:
        out["unknown"] = True
        return out
    rem = [k for k in C.AUTO_READ_SOURCES if verdicts[k]["verdict"] == "remove"]
    if rem:
        k = first_src if first_src in rem else rem[0]
        out.update(keep=False, reason=REASONS[0], state=verdicts[k]["state"], source=k, text=verdicts[k]["text"])
        return out
    k = first_src if first_src in verdicts else C.AUTO_READ_SOURCES[0]
    out.update(keep=False, reason=REASONS[1], state=verdicts[k].get("state"), source=k, word=verdicts[k].get("word"))
    return out


# ── the minute step ───────────────────────────────────────────────────────────────────────────────────────────────
def _lists(doc, iso: str) -> tuple:
    if not isinstance(doc, dict) or doc.get("session") != iso:
        return [], [], []
    entries = copy.deepcopy(entries_of(doc, iso))
    removed = copy.deepcopy([r for r in doc.get("removed") or [] if isinstance(r, dict)])
    dismissed = [s for s in doc.get("dismissed") or [] if isinstance(s, str)]
    return entries, removed, dismissed


def _changed(doc, iso: str, entries, removed, dismissed) -> bool:
    if isinstance(doc, dict) and doc.get("session") == iso:
        return (entries, removed, dismissed) != _lists(doc, iso)
    stored = _lists(doc, _iso(doc.get("session")) if isinstance(doc, dict) else "")
    return bool(entries or removed or dismissed or any(stored))


def _compute(doc, now, session, manual, stores, in_window: bool) -> tuple:
    iso = _iso(session)
    entries, removed, dismissed = _lists(doc, iso)
    mk = {CO.fold(m) for m in manual or [] if isinstance(m, str)}
    dk = {CO.fold(s) for s in dismissed}
    shared = shared_sets(session, store=stores.get(V.GG5.key))
    sets = potential_sets(session, shared=shared, stores=stores)
    gone_now: list = []
    kept: list = []
    for e in entries:
        sym, k = e["symbol"], CO.fold(e["symbol"])
        if k in mk:
            gone_now.append(_rec(sym, now, REASONS[3], text=_words().AUTO_ON_LIST_TEXT))
            continue
        if k in dk:
            continue                                           # recorded by dismiss
        p = progress(sym, session, stores=stores, shared=shared, entry=e)
        if p["reason"] == REASONS[0]:
            gone_now.append(_rec(sym, now, REASONS[0], state=p["state"], source=p["source"], text=p["text"]))
            continue
        if p["reason"] == REASONS[1]:
            if sets is not None:                               # unknown boards → no "dropped" judgement this step
                since = e.get("dropped_since") if _utc(e.get("dropped_since")) else now
                e["dropped_since"] = since
                if (now - _utc(since)).total_seconds() >= C.AUTO_DROP_GRACE_SEC:
                    text = _words().AUTO_DROPPED_TEXT.format(grace_min=C.AUTO_DROP_GRACE_SEC // 60, word=p["word"])
                    gone_now.append(_rec(sym, now, REASONS[1], state=p["state"], source=p["source"], text=text))
                    continue
        elif p["keep"] and not p["unknown"]:
            e["dropped_since"] = None
        kept.append(e)
    entries = kept
    removed += gone_now
    merged = merge(sets) if sets is not None else []
    by = {CO.fold(sym): (cand, srcs) for _ok, sym, cand, srcs in merged}
    for e in entries:                                          # words move, positions do not
        hit = by.get(CO.fold(e["symbol"]))
        if hit:
            cand, srcs = hit
            e.update(sources=list(srcs), setup=cand["setup"], kind=cand["kind"], volume=cand["volume"],
                     volume_source=cand["volume_source"], float_shares=cand["float_shares"])
    skipped = {k: 0 for k in SKIPPED_KEYS}
    added: list = []
    reason = None
    if sets is None:
        reason = STEP_REASONS[1]
    elif not in_window:
        reason = STEP_REASONS[2]
    else:
        have = {CO.fold(e["symbol"]) for e in entries}
        room = max(0, C.AUTO_MAX_SYMBOLS - len(entries))
        for _ok, sym, cand, srcs in merged:                    # merged is already in order_key order [C4]
            k = CO.fold(sym)
            if k in mk or k in dk or k in have:
                continue
            if not good_volume(cand):
                skipped[SKIPPED_KEYS[0] if PT._num(cand.get("volume")) is None else SKIPPED_KEYS[1]] += 1
                continue
            if len(added) >= room:
                continue                                       # never displace (HIS CALL #8)
            have.add(k)
            added.append({"symbol": sym, "sources": list(srcs), "setup": cand["setup"], "kind": cand["kind"],
                          "volume": cand["volume"], "volume_source": cand["volume_source"],
                          "float_shares": cand["float_shares"], "added_at": now, "added_et": PT._hhmm(now),
                          "dropped_since": None})
        entries = entries + added
    res = {"symbols": [e["symbol"] for e in entries], "added": [e["symbol"] for e in added],
           "removed": [{k: r.get(k) for k in ("symbol", "reason", "state", "text")} for r in gone_now],
           "leaving": [e["symbol"] for e in entries if _utc(e.get("dropped_since"))],
           "n": len(entries), "cap": C.AUTO_MAX_SYMBOLS, "skipped": skipped, "reason": reason,
           "removed_total": len(removed)}
    res["changed"] = _changed(doc, iso, entries, removed, dismissed)
    return res, {"session": iso, "entries": entries, "removed": removed, "dismissed": dismissed}


def step(now, session, *, db=None, manual: list, dry: bool = False, stores: Optional[dict] = None) -> dict:
    """THE minute step (module docstring). -> {symbols, added, removed (this step), leaving, n, cap, skipped, reason,
    removed_total, changed, writes (dry only)}. A fault of the auto doc → reason "list_unreadable", no write."""
    now = RUN._utc(now)
    stores = stores if stores is not None else _default_stores()
    cs = CO.colls(db)
    in_window = bool(RUN.in_window(now))
    res: dict = {}
    for _ in range(_CAS_TRIES):
        doc = read_doc(cs)
        if doc is None:
            return {"symbols": [], "added": [], "removed": [], "leaving": [], "n": 0, "cap": C.AUTO_MAX_SYMBOLS,
                    "skipped": {k: 0 for k in SKIPPED_KEYS}, "reason": STEP_REASONS[0], "changed": False}
        res, new = _compute(doc, now, session, manual, stores, in_window)
        if dry:
            res["writes"] = new
            return res
        if not res["changed"]:
            return res
        try:
            if _cas(cs["list"], doc, dict(new, updated_at=now, by=BY_LOOP)):
                return res
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala watch 🤖: auto write failed: %s", type(exc).__name__)
            break
    log.warning("gajjala watch 🤖: the auto write did not land")
    stored = read_doc(cs)
    syms = current_symbols(cs, _iso(session)) if stored is not None else []
    return dict(res, symbols=syms, n=len(syms), added=[], removed=[], changed=False, reason=STEP_REASONS[3])


# ── his × on an auto name (api.py DELETE) ─────────────────────────────────────────────────────────────────────────
def _dismiss_answer(state: str, sym, db) -> dict:
    return {"state": state, "symbols": CO.owner_symbols(db), "symbol": sym, "text": _words().store_text(state, sym)}


def dismiss(symbol, *, by, db=None, now=None) -> dict:
    """His × (every DELETE calls it — a × on a MANUAL name also blocks an auto re-add today, HIS CALL #6). A non-ticker →
    "absent" without reading or writing the auto doc [C8]; a doc of another session → the write IS the session reset
    [C7]; an entry → pulled, recorded "dismissed"; else the name joins `dismissed` → "absent". Never raises."""
    from . import build as BLD
    from .store import normalize
    sym = normalize(symbol)
    if sym is None:
        return _dismiss_answer(STATES_DISMISS[1], None, db)
    try:
        now = RUN._utc(now) if now is not None else datetime.now(timezone.utc)
        cs = CO.colls(db)
        if cs is None:
            return _dismiss_answer(STATES_DISMISS[2], sym, db)
        iso = BLD.session_of(now)[0].isoformat()
        k = CO.fold(sym)
        for _ in range(_CAS_TRIES):
            doc = read_doc(cs)
            if doc is None:
                return _dismiss_answer(STATES_DISMISS[2], sym, db)
            if doc.get("session") != iso:
                state, new = STATES_DISMISS[1], {"session": iso, "entries": [], "removed": [], "dismissed": [sym]}
            else:
                entries, removed, dismissed = _lists(doc, iso)
                hit = [e for e in entries if CO.fold(e["symbol"]) == k]
                state = STATES_DISMISS[0] if hit else STATES_DISMISS[1]
                if hit:
                    entries = [e for e in entries if CO.fold(e["symbol"]) != k]
                    removed.append(_rec(hit[0]["symbol"], now, REASONS[2], text=_words().AUTO_DISMISSED_TEXT))
                if k not in {CO.fold(s) for s in dismissed}:
                    dismissed.append(sym)
                elif not hit:
                    return _dismiss_answer(state, sym, db)     # already blocked today — nothing to write
                new = {"session": iso, "entries": entries, "removed": removed, "dismissed": dismissed}
            if _cas(cs["list"], doc, dict(new, updated_at=now, by=by if isinstance(by, str) else None)):
                return _dismiss_answer(state, sym, db)
        log.warning("gajjala watch 🤖: dismiss %s lost the compare-and-set %d times", sym, _CAS_TRIES)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 🤖: dismiss %s failed: %s", sym, type(exc).__name__)
    return _dismiss_answer(STATES_DISMISS[2], sym, db)


# ── the auto names' own-minute crosses (never rung while C.AUTO_PUSH_MODE is off) ─────────────────────────────────
def hold_crosses(frames_auto: dict, now, session, held: dict) -> int:
    """Every auto name's latest up cross on its OWN minute (the cross_alerts test: the frame's latest closed bar AND
    fresh on the 1-minute clock) on a push frame → held[SYM][tf] = {bar_t, reason: C.AUTO_HELD_REASON}. Returns the
    count. Never sends, never claims, never touches cross_alerts.run."""
    from . import cross_alerts as XA
    iso = _iso(session)
    n = 0
    for sym, fr in (frames_auto or {}).items():
        if fr is None:
            continue
        by = getattr(fr, "by", {}) or {}
        for tf, _rule in C.FRAMES:
            if tf not in C.PUSH_FRAMES or tf not in AL.FRAME_MINUTES:
                continue
            F = by.get(tf)
            if F is None:
                continue
            x = EX.latest_up_cross(XA.watch_crosses(F), iso)
            if x is None:
                continue
            own = bool(F.t) and x["ts"] == F.t[-1] and AL.is_fresh({"entry_bar_t": x["ts"]}, now, V.GG1)
            if own:
                if isinstance(held, dict):
                    held.setdefault(sym, {})[tf] = {"bar_t": x["ts"], "reason": C.AUTO_HELD_REASON}
                n += 1
    return n


def push_mode() -> str:
    """C.AUTO_PUSH_MODE when it is one of C.AUTO_PUSH_MODES, else "off" (fail closed). Read at CALL time."""
    m = C.AUTO_PUSH_MODE
    return m if isinstance(m, str) and m in C.AUTO_PUSH_MODES else C.AUTO_PUSH_MODES[0]


def rules_line() -> str:
    """The ℹ️ clause — every number and word from the constants at CALL time (never typed here)."""
    words = [C.AUTO_SOURCE_WORDS[k] for k in C.AUTO_SOURCES]
    boards = ", ".join(words[:-1]) + " and " + words[-1] if len(words) > 1 else "".join(words)
    gone = " or ".join(_REMOVE_WORDS.get(s, s) for s in C.AUTO_REMOVE_STATES)
    stays = "; ".join(_KEEP_WORDS[s] for s in C.AUTO_KEEP_STATES if s in _KEEP_WORDS)
    frames = " / ".join(C.FRAME_WORDS[tf] for tf, _r in C.FRAMES if tf in C.PUSH_FRAMES)
    mode = push_mode()
    push = (f"auto names do not ring the {frames} cross (mode {mode})" if mode == C.AUTO_PUSH_MODES[0]
            else f"auto names ring the {frames} cross like yours (mode {mode})")
    grace = C.AUTO_DROP_GRACE_SEC // 60
    return (f"🤖 Gajjala's Watch adds, once a minute during the {GC.PASS_OPEN_ET}–{GC.PASS_CLOSE_ET} ET pass window, the 🧠 "
            f"potentials the {boards} boards serve with today's volume at or over {C.AUTO_MIN_VOLUME:,} shares (GG's "
            f"K11 floor; the scan row, else the pass's own stored number), up to {C.AUTO_MAX_SYMBOLS} at a time, in the "
            f"order added; an auto name leaves the watch when every board reads it {gone}, or when it has been a "
            f"potential nowhere for {grace} minutes"
            + (f"; {stays} stays" if stays else "")
            + f"; your own names are never touched; {push}. UNMEASURED.")


__all__ = ["REASONS", "STEP_REASONS", "STATES_DISMISS", "SKIPPED_KEYS", "read_doc", "entries_of", "current_symbols",
           "shared_sets", "volume_of", "potential_sets", "good_volume", "merge", "progress", "step", "dismiss",
           "hold_crosses", "push_mode", "rules_line"]
