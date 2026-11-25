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

ACCUMULATE (2026-11-17 12:55 ET, spec ggwauto2 — Ajay, verbatim: "please keep adding more to watch list as they come
in to Potentials intraday"). SUPERSEDES the ADD source and the [C3] "dropped" removal above:
  * ADD SOURCE = every name with a 🧠 tracker doc of TODAY's session in the GG5 or GG1 store (`ST.POTENTIALS`, ONE
    projected find per store per step — `tracker_sets`) UNION the current potentials (`potential_sets`, unchanged). A
    tracker-only candidate: setup = the doc with the earliest `first_seen`, kind = its `first_kind`, sources = the
    stores it appears in (+ the borrowers). ONE order per step (`arrivals`): the earliest tracker doc's `first_seen`
    ascending (ties symbol); a current potential with no tracker doc yet sorts last, by `potential.order_key`. The
    listed filter, the volume floor, his names, his × and the names already on the list apply unchanged. A tracker-only
    name removed earlier THIS session is not re-added from its tracker doc alone (a current potential again still is) —
    without it a name made room for would come straight back every minute (executor's judgement, 2026-11-17).
  * A lapsed name (progress verdict "dropped") now STAYS all session, stamped `dropped_since` (cleared when it is a
    potential / progressing again) and served with the "lapsed" word — `C.AUTO_DROP_GRACE_SEC` removes nothing now.
  * AT THE CAP each arrival that does not fit removes the OLDEST-ADDED name lapsed THIS step (reason "made_room", text
    payload.AUTO_MADE_ROOM_TEXT). A potential, a broke-kept or an unknown name is never evicted; none lapsed → the
    arrival is skipped, counted "full". A tracker read fault → no tracker adds and no "made room" that step.
  * AMENDMENT A (2026-11-17, main session — his "as they come in"; SUPERSEDES the ONE order above): each step's
    arrivals are (i) the CURRENT 🧠 potentials not on the list, in `potential.order_key` order, THEN (ii) the
    tracker-only names (came in earlier today, not a potential now), `first_seen` DESCENDING (newest first; ties
    symbol; none carrying a first_seen last). Only a CURRENT potential evicts ("made_room"); a tracker-only name takes a
    FREE seat or is skipped ("full") — no minute-to-minute churn. A tracker-only name is read by `progress` first: ↩️ / ✖️
    → not added, counted "failed"; else it lands with `dropped_since` = the newest `last.at` across its tracker docs
    (the real lapse time; a missing / bad stamp → now) — None when `progress` reads it KEEP (a broke read still
    progressing: the step's own clear rule).

🎯 A+ SEATS (2026-11-17 ~17:20 ET, spec ggwaplus2 WP-1 — Ajay, verbatim: "Push new Apluses immediately in to watch list
and an alert for me please Missed AKAN and GP"). Each in-window step classifies A+ with THE 🎯 tag's classifier
(`payload.aplus_by_symbol` over the step's OWN read docs + the 🧪 board's `audited_tab.overlay_reads`; the read projection
carries `updated_at` for the 🧪 freshness check) — `aplus_sets`. Every A+ name (tab.MARKED_STATES on any of the three
boards; 🥇 Luk never) is seated FIRST, earliest A+ first (`aplus_arrivals`): a free seat, else (C.AUTO_APLUS_EVICTS) the
oldest-added name lapsed THIS step, else the oldest-added 🧠 potential — never another A+, never his name; none → the
name is listed in `aplus_skipped`. No volume floor (K11 — the same number — is judged on every A+ on all three boards);
the volume words = `volume_of` or none. An A+ entry carries `why` C.AUTO_APLUS_WHY + its `aplus` block (the tag's first
item), STAYS all session (C.AUTO_APLUS_STAYS — never `progress()`-read, never lapsed; only his ×), and its A+ words
(`aplus`, `sources`, `setup`) follow the live read every step; a step with no hit keeps the LAST block (the Watch's last
sighting). A 🧠 potential entry that becomes A+ is promoted IN PLACE (`promoted` True, its seat clock unchanged). A name
removed earlier today comes back as A+ (a board arrival — `out_today` blocks tracker-only arrivals only); his × blocks.
`aplus_sets` answers None (unknown, never "none") on any read fault, a missing 🧪 overlay handle or a raise → no A+ add,
no refresh, no promote that step. Potential entries never gain a key. UNMEASURED — display / selection only.

⏹ 1-MINUTE PAGE RETIRED (2026-11-18 — Ajay, verbatim: "This is good info stop 1 min tab it was a good experiment", then
"But keep the one min chart in the watch list I still want them"). The ACTIVE sources follow `variant.enabled` (the ONE
predicate over GC.GAJJALA_1M_ENABLED): `read_sources()` / `sources()` drop "gajjala_1m" while the page is off — no GG1
store is read, a GG1-only potential / tracker / A+ never seats, the hint and the ℹ️ line name only the 🚩 5-min and 🧪
boards. C.AUTO_SOURCES / C.AUTO_SOURCE_WORDS / C.AUTO_READ_SOURCES stay the registry, so an entry stored with
"gajjala_1m" still prints its words (history). The Watch's own minute bars never came from that pass — untouched.
Reversible: the switch back on → the three sources return.

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
from chart_maps.gajjala import tab as GT                  # 🚫 2026-11-19 (spec watchfid [C7]): the served word; no cycle
from chart_maps.gajjala import variant as V

from . import colls as CO
from . import constants as C
from .store import _CAS_TRIES

log = logging.getLogger("chart_maps.gajjala_watch.auto")

REASONS = ("not_progressing", "dropped", "dismissed", "on_your_list",      # the stored removal reasons — APPEND only:
           "made_room",                                                   # "dropped" = old docs only (12:55 accumulate)
           "made_room_aplus",                                             # 🎯 2026-11-17 (spec ggwaplus2) — an A+ seat
           "not_eligible")                                                # 🚫 2026-11-19 (spec watchfid) — on his broker list
STEP_REASONS = ("list_unreadable", "boards_unreadable", "closed", "write_failed")
STATES_DISMISS = ("dismissed", "absent", "error")
SKIPPED_KEYS = ("volume_unknown", "under_floor", "full",                 # "full" appended 2026-11-17 12:55
                "failed",                                                  # "failed" appended (Amendment A4) — APPEND only
                "not_eligible",                                            # 🚫 2026-11-19 (spec watchfid) — on his broker list
                "si_ssr")                                                  # ⛔🔒 2026-11-24 (spec sissr C2) — an ADDED name
_TRACKER_FIELDS = {"symbol": 1, "setup": 1, "date": 1, "first_seen": 1, "first_kind": 1, "last.at": 1,
                   "last.state": 1, "last.session_volume": 1,             # the ONE projected tracker find per store
                   "si_ssr_add": 1}                                       # ⛔🔒 2026-11-24 — the insert-only add marker
_FAR = datetime.max.replace(tzinfo=timezone.utc)
_READ = object()                                                          # shared_sets: "read the trackers yourself"
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


def read_sources() -> tuple:
    """The ACTIVE stored read sets — C.AUTO_READ_SOURCES whose variant is enabled (`variant.enabled`, the ONE switch
    predicate, read at call time; 2026-11-18: the retired 1-minute page drops out; reversible)."""
    vs = _variants()
    return tuple(k for k in C.AUTO_READ_SOURCES if k in vs and V.enabled(vs[k]))


def sources() -> tuple:
    """The ACTIVE source tags — C.AUTO_SOURCES minus a disabled variant's key ("gga" stays: 🧪 is always on)."""
    vs = _variants()
    return tuple(k for k in C.AUTO_SOURCES if k not in vs or V.enabled(vs[k]))


def _borrowers() -> dict:
    """{source key: the read source it borrows} — derived from variant.borrows (🧪 borrows GG5's reads), never typed."""
    vs = _variants()
    return {k: V.GG5.key for k in C.AUTO_SOURCES
            if k not in C.AUTO_READ_SOURCES and k in vs and ST.READS in vs[k].borrows}


def _default_stores() -> dict:
    """{read source key: its real store} — GG5 → store.default(), GG1 → store.for_variant(V.GG1); 🎯 2026-11-17 + the 🧪
    store (store.for_variant(V.GGA) — its overlay handle, for the A+ classifier)."""
    vs = _variants()
    out = {k: (ST.default() if V.is_gg5(vs[k]) else ST.for_variant(vs[k])) for k in read_sources()}
    out[V.GGA.key] = ST.for_variant(V.GGA)
    return out


def _words():
    from . import payload as PL                                  # lazy: payload reads this module lazily too
    return PL


# ── 🚫 his broker list (2026-11-19, spec watchfid) ──────────────────────────────────────────────────────────────────
def broker_gate(stores) -> tuple:
    """🚫 (frozenset of folded symbols, fault) — THE list (gajjala.store.broker_flags over the GG5 store), read ONCE per
    step. Ajay 2026-11-19, verbatim: "Add a button to say not in fidelity, AZI and CHSN are not in fidelity don't add
    them to watch list". The switch off → (frozenset(), False). A read fault or a raise → (frozenset(), True): the seed
    is ignored on a fault (it is empty by HIS rule) and the caller fails OPEN (only today's own removals stay out).
    Never raises."""
    if not C.AUTO_SKIP_NOT_ELIGIBLE:
        return frozenset(), False
    try:
        syms, fault = ST.broker_flags((stores or {}).get(V.GG5.key))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 🤖: broker list unreadable: %s", type(exc).__name__)
        return frozenset(), True
    if fault:
        return frozenset(), True
    return frozenset(CO.fold(s) for s in syms if isinstance(s, str)), False


def broker_words() -> Optional[str]:
    """🚫 THE one phrase on the Watch exception (the ℹ️ auto clause, the ℹ️ 🚫 line, the 🤖 hover hint), from the
    constants at CALL time; None when the switch is off. No digit, never the broker's name."""
    if not C.AUTO_SKIP_NOT_ELIGIBLE:
        return None
    s = f"a name on your {GT.BROKER_FLAG_ICON} list never takes a 🤖 auto seat"
    if C.AUTO_NOT_ELIGIBLE_REMOVES:
        s += (", and a seated one leaves at the next minute, an A+ seat too" if C.AUTO_NOT_ELIGIBLE_REMOVES_APLUS
              else ", and a seated potential leaves at the next minute (an A+ seat stays until your ×)")
    return s


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


def _cas(coll, doc: dict, fields: dict, doc_id: str = C.AUTO_DOC_ID) -> bool:
    """ONE update_one: lands ONLY IF the stored doc is still `doc` (its `rev`; a missing doc: still missing). False =
    another write landed in between. A failing write RAISES. `doc_id` (2026-11-24, spec watchall §3.4): the ✅ engine's
    own doc (C.RULES_DOC_ID) uses the SAME compare-and-set; the default is the auto doc, as before."""
    rev = doc.get("rev") if isinstance(doc, dict) else None
    fields = dict(fields, rev=(rev if isinstance(rev, int) and not isinstance(rev, bool) else 0) + 1)
    if doc:
        flt = {"_id": doc_id, "rev": rev} if "rev" in doc else {"_id": doc_id, "rev": {"$exists": False}}
        res = coll.update_one(flt, {"$set": fields}, upsert=False)
        return bool(getattr(res, "matched_count", 0))
    from pymongo.errors import DuplicateKeyError
    try:
        res = coll.update_one({"_id": doc_id, "rev": {"$exists": False}}, {"$set": fields}, upsert=True)
    except DuplicateKeyError:
        return False
    return bool(getattr(res, "matched_count", 0)) or getattr(res, "upserted_id", None) is not None


# ── the boards (read-only) ────────────────────────────────────────────────────────────────────────────────────────
def shared_sets(session, store=None, *, tracker_docs=_READ) -> dict:
    """[C5][F25] Read ONCE per step from the GG5 store (every variant's scan set is GG5's): `listed` (the board's filter;
    {} on a raise — empty hides nothing), `scan_by` {SYM: scan doc}, `trackers` {SYM: the GG5 tracker doc with the
    newest last.at} or None on a READ FAULT (store.potentials' own rule). `tracker_docs` (2026-11-17 12:55): the GG5
    tracker docs the step already read (`_tracker_docs`; None = a fault) — so GG5's tracker is found ONCE per step."""
    st = store if store is not None else ST.default()
    try:
        listed = SC.listed_symbols(st, session) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 🤖: listed read failed: %s", type(exc).__name__)
        listed = {}
    scan_by = {_up(d.get("symbol")): d for d in st.scan_docs([session]) if isinstance(d, dict) and _up(d.get("symbol"))}
    docs = st.potentials(session) if tracker_docs is _READ else tracker_docs
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


_READ_FIELDS = {"symbol": 1, "setups": 1, "ctx": 1, "updated_at": 1}    # updated_at: the 🧪 freshness check (3), 2026-11-17


def _read_docs(st, iso: str):
    """The session's read docs of one store, projected (symbol, setups, ctx, updated_at — never the tile bars). None on
    a fault."""
    c = st.coll(ST.READS) if st is not None else None
    if c is None:
        return None
    try:
        return list(c.find({"date": iso}, _READ_FIELDS))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 🤖: reads unreadable: %s", type(exc).__name__)
        return None


def potential_sets(session, *, shared: dict, stores: Optional[dict] = None, docs=_READ) -> Optional[dict]:
    """{source key: {SYM: cand}} for the ACTIVE read sources (`read_sources()`) — None when ANY store cannot be read (the whole answer is
    unknown, never "none"). cand = the setup with the least potential.order_key among the name's 🧠 setups. `docs`
    (2026-11-17): {read source: the step's `_read_docs` answer} — read ONCE per step and shared with `aplus_sets`."""
    stores = stores if stores is not None else _default_stores()
    iso = _iso(session)
    listed = shared.get("listed") or {}
    scan_by = shared.get("scan_by") or {}
    pre = docs
    out: dict = {}
    for key in read_sources():
        docs = _read_docs(stores.get(key), iso) if pre is _READ else (pre or {}).get(key)
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
    for key in read_sources():
        for sym, cand in ((sets or {}).get(key) or {}).items():
            k = CO.fold(sym)
            if k not in by:
                by[k] = [cand["order_key"], CO.house(sym), cand, {key}]
                continue
            e = by[k]
            e[3].add(key)
            if cand["order_key"] < e[0]:
                e[0], e[2] = cand["order_key"], cand
    bor, act = _borrowers(), sources()
    out = []
    for ok, sym, cand, present in by.values():
        srcs = [s for s in act if s in present or bor.get(s) in present]
        out.append((ok, sym, cand, srcs))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


# ── came in to Potentials today (2026-11-17 12:55 accumulate) ─────────────────────────────────────────────────────
def _tracker_docs(st, iso: str, fields: dict = _TRACKER_FIELDS) -> Optional[list]:
    """ONE projected find of a store's 🧠 tracker (`ST.POTENTIALS`) for the session — the docs whose `_id` carries the
    "<iso>|" prefix; None on a READ FAULT (no handle, or the find raised — unknown is never "none"). `fields`
    (2026-11-24, spec watchall §3.4): the projection — `_TRACKER_FIELDS` by default, as before; the ✅ engine passes
    C.RULES_TRACKER_FIELDS (it needs `state_path`)."""
    c = st.coll(ST.POTENTIALS) if st is not None else None
    if c is None:
        return None
    try:
        docs = list(c.find({"date": iso}, fields))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 🤖: trackers unreadable: %s", type(exc).__name__)
        return None
    pre = f"{iso}|"
    return [d for d in docs if isinstance(d, dict) and isinstance(d.get("_id"), str) and d["_id"].startswith(pre)]


def _setup_rank(setup) -> int:
    return GC.SETUPS.index(setup) if setup in GC.SETUPS else len(GC.SETUPS)


def tracker_sets(session, *, shared: dict, docs: Optional[dict]) -> Optional[dict]:
    """{FOLD: (SYM, cand, sources)} — every name with a 🧠 tracker doc of the session in the GG5 or GG1 store (`docs` =
    {read source key: `_tracker_docs` answer}); None when ANY store's read faulted. The listed filter applies (only when
    the listed set is non-empty — tab.build). cand: setup = the doc with the earliest `first_seen` (ties: GC.SETUPS
    order), kind = its `first_kind`, volume = `volume_of` (unchanged), `first_seen` (None when no doc carries one),
    `last_at` (Amendment A3: the NEWEST `last.at` across its docs — the lapse time; None when none carries one);
    sources = the stores it appears in, + every borrower of a present store (as `merge`)."""
    listed = shared.get("listed") or {}
    scan_by = shared.get("scan_by") or {}
    by: dict = {}
    for key in read_sources():
        ds = (docs or {}).get(key)
        if ds is None:
            return None
        for d in ds:
            sym = _up(d.get("symbol")) if isinstance(d, dict) else ""
            if not sym or (listed and sym not in listed):
                continue
            fs = _utc(d.get("first_seen"))
            la = _utc((d.get("last") or {}).get("at")) if isinstance(d.get("last"), dict) else None
            setup = d.get("setup")
            rank = (fs or _FAR, _setup_rank(setup))
            k = CO.fold(sym)
            cur = by.get(k)
            if cur is None:
                by[k] = {"symbol": CO.house(sym), "up": sym, "rank": rank, "first_seen": fs, "setup": setup,
                         "kind": d.get("first_kind"), "present": {key}, "last_at": la}
                continue
            cur["present"].add(key)
            if la is not None and (cur["last_at"] is None or la > cur["last_at"]):
                cur["last_at"] = la
            if rank < cur["rank"]:
                cur.update(rank=rank, first_seen=fs, setup=setup, kind=d.get("first_kind"))
    bor, act = _borrowers(), sources()
    out: dict = {}
    for k, t in by.items():
        vol, vsrc = volume_of(t["up"], (scan_by.get(t["up"]) or {}).get("last"), shared.get("trackers"))
        cand = {"setup": t["setup"] if isinstance(t["setup"], str) else None,
                "kind": t["kind"] if isinstance(t["kind"], str) else None, "volume": vol, "volume_source": vsrc,
                "float_shares": None, "order_key": None, "first_seen": t["first_seen"], "last_at": t["last_at"]}
        srcs = [s for s in act if s in t["present"] or bor.get(s) in t["present"]]
        out[k] = (t["symbol"], cand, srcs)
    return out


def arrivals(merged: list, tracked: Optional[dict]) -> list:
    """[(SYM, cand, sources, tracker_only)] — Amendment A1 (his "as they come in"): (i) every CURRENT potential, in
    `merged`'s own `potential.order_key` order [C4] (its live cand and sources); THEN (ii) the tracker-only names (a
    tracker doc today, not a potential now), `first_seen` DESCENDING — newest first, ties symbol; a tracker-only name
    without a first_seen last (by symbol)."""
    tracked = tracked or {}
    rows, seen = [], set()
    for _ok, sym, cand, srcs in merged or []:
        seen.add(CO.fold(sym))
        rows.append((sym, cand, srcs, False))
    later = []
    for k, (sym, cand, srcs) in tracked.items():
        if k in seen:
            continue
        fs = cand.get("first_seen")
        later.append(((0, -fs.timestamp(), sym) if fs is not None else (1, 0.0, sym), sym, cand, srcs))
    later.sort(key=lambda r: r[0])
    return rows + [(sym, cand, srcs, True) for _key, sym, cand, srcs in later]


# ── 🎯 A+ (2026-11-17, spec ggwaplus2 WP-1) ───────────────────────────────────────────────────────────────────────
def _by_symbol(docs) -> dict:
    out: dict = {}
    for d in docs or []:
        sym = _up(d.get("symbol")) if isinstance(d, dict) else ""
        if sym and sym not in out:
            out[sym] = d
    return out


def aplus_sets(session, *, docs: dict, stores: dict) -> Optional[dict]:
    """{FOLD: (SYM, ap, sources)} — every name in tab.MARKED_STATES on any of the three boards THIS session, by THE 🎯
    tag's classifier (`payload.aplus_by_symbol` + the 🧪 board's `audited_tab.overlay_reads`) over the step's OWN read
    docs (`docs` = {read source: `_read_docs` answer}). ap = the tag's sorted first item {source, source_word, setup,
    setup_label, state, word, at_et}; sources = the tag's own source list (C.AUTO_SOURCES order — a 🚩 5-min A+ with no
    overlay doc passes through as 🧪 too, as the 🧪 board lists it). No listed filter (the tag has none). None —
    unknown, never "none" — when a read set faulted, the 🧪 store / its overlay handle is missing, or anything raises.
    A 🧪 overlay FIND fault is swallowed by store.overlays (→ "no overlay") and cannot be told apart here."""
    try:
        rs = read_sources()
        if not isinstance(docs, dict) or any(docs.get(k) is None for k in rs):
            return None
        sta = (stores or {}).get(V.GGA.key)
        if sta is None or sta.coll(ST.OVERLAY) is None:
            return None
        from chart_maps.gajjala import audited_tab as AT                # lazy: the 🧪 board's module (0.6 s once)
        PL = _words()
        gg5 = _by_symbol(docs[V.GG5.key])
        gg1 = _by_symbol(docs.get(V.GG1.key) or []) if V.GG1.key in rs else {}     # 2026-11-18: retired → not read
        gga, _stats = AT.overlay_reads(gg5, sta, _iso(session))
        act = sources()
        out: dict = {}
        for sym, items in PL.aplus_by_symbol(gg5, gg1, gga).items():
            blk = PL.aplus_row_block(items)
            k = CO.fold(sym)
            if blk is None or k in out:
                continue
            have = {it.get("source") for it in blk["items"]}
            out[k] = (CO.house(sym), dict(blk["items"][0]), [s for s in act if s in have])
        return out
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 🤖: A+ classifier failed: %s", type(exc).__name__)
        return None


def aplus_arrivals(aps: Optional[dict]) -> list:
    """[(SYM, ap, sources)] — earliest A+ first (`ap.at_et` ascending, a missing clock last), ties symbol."""
    rows = list((aps or {}).values())
    rows.sort(key=lambda r: (r[1].get("at_et") is None, r[1].get("at_et") or "", r[0]))
    return rows


def _is_aplus(e) -> bool:
    return isinstance(e, dict) and e.get("why") == C.AUTO_APLUS_WHY


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
    rs = read_sources()
    for key in rs:
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
    vals = [verdicts[k]["verdict"] for k in rs]
    out = {"keep": True, "unknown": False, "reason": None, "state": None, "source": None, "text": None, "word": None}
    if "keep" in vals:
        return out
    if "fault" in vals or "unknown" in vals:
        out["unknown"] = True
        return out
    rem = [k for k in rs if verdicts[k]["verdict"] == "remove"]
    if rem:
        k = first_src if first_src in rem else rem[0]
        out.update(keep=False, reason=REASONS[0], state=verdicts[k]["state"], source=k, text=verdicts[k]["text"])
        return out
    k = first_src if first_src in verdicts else rs[0]
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


def _si_ssr_adds(read_docs, tracker_docs) -> set:
    """⛔🔒 2026-11-24 (spec sissr §3.6, C2) — {FOLD} of the ADDED ⛔ / 🔒 names (si_ssr_names.is_add: a read doc whose
    ctx tag carries the add flag, or a 🧠 tracker doc with the insert-only `si_ssr_add`) across {source: docs} maps
    (None entries skipped). Such a name failed GG's own scanner rule: it never takes a 🤖 / 🎯 seat and never evicts —
    it can only sit in the ✅ engine's "sissr" section. The module is imported LAZILY; a fault → set() and one log line
    (the add flag is then not read — the pass's own push hold is unchanged)."""
    try:
        from chart_maps.gajjala import si_ssr_names as SSN
        out = set()
        for docs in (read_docs, tracker_docs):
            for ds in (docs or {}).values() if isinstance(docs, dict) else []:
                for d in ds or []:
                    if SSN.is_add(d) and isinstance(d.get("symbol"), str) and d["symbol"].strip():
                        out.add(CO.fold(d["symbol"]))
        return out
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch 🤖: the ⛔🔒 add read failed: %s", type(exc).__name__)
        return set()


def _compute(doc, now, session, manual, stores, in_window: bool) -> tuple:
    iso = _iso(session)
    entries, removed, dismissed = _lists(doc, iso)
    mk = {CO.fold(m) for m in manual or [] if isinstance(m, str)}
    dk = {CO.fold(s) for s in dismissed}
    bk, bfault = broker_gate(stores)                           # 🚫 2026-11-19 (spec watchfid): ONE list read per step
    ne_seen = {CO.fold(r.get("symbol")) for r in removed
               if isinstance(r, dict) and r.get("reason") == REASONS[6] and isinstance(r.get("symbol"), str)}
    refuse_k = ne_seen if bfault else bk                       # [C8] a fault minute: today's own 🚫 removals stay out
    ne: list = []                                              # house spellings, fold-deduped, first-refusal order

    def refuse(sym) -> None:
        if CO.fold(sym) not in {CO.fold(x) for x in ne}:
            ne.append(CO.house(sym))

    tdocs = {k: _tracker_docs(stores.get(k), iso) for k in read_sources()}          # ONE find per store
    shared = shared_sets(session, store=stores.get(V.GG5.key), tracker_docs=tdocs.get(V.GG5.key))
    rdocs = {k: _read_docs(stores.get(k), iso) for k in read_sources()}             # ONE read find per store
    sets = potential_sets(session, shared=shared, stores=stores, docs=rdocs)
    # 🎯 2026-11-17 (spec ggwaplus2): the A+ set — in window only (out of window: no add, no promote, no refresh)
    aps = aplus_sets(session, docs=rdocs, stores=stores) if in_window else None
    # ⛔🔒 2026-11-24 (spec sissr C2): the ADDED names — a current potential / A+ by its read doc's add flag; a
    # tracker-only arrival by the read flag OR its tracker's insert-only flag (an add that later made GG's list keeps
    # the tracker flag, so only its current-potential arrival — read doc, no add flag — can seat it)
    ss_read = _si_ssr_adds(rdocs, None)
    ss_any = ss_read | _si_ssr_adds(None, tdocs)
    ss_skip: set = set()
    if aps is not None:                                        # words move, positions do not [C4]; unknown ≠ none
        for e in entries:
            k = CO.fold(e["symbol"])
            if k in mk or k in dk or k not in aps:
                continue                                       # no hit → an A+ entry keeps its LAST block
            if k in bk and not _is_aplus(e):
                continue                                       # 🚫 a flagged potential is never promoted in place [C9]
            _s, ap, srcs = aps[k]
            e.update(aplus=dict(ap), sources=list(srcs), setup=ap.get("setup"))
            if not _is_aplus(e):                               # a 🧠 potential that became A+ — promoted in place
                e.update(why=C.AUTO_APLUS_WHY, kind=None, dropped_since=None, promoted=True, aplus_at=now,
                         aplus_et=PT._hhmm(now))
    gone_now: list = []
    kept: list = []
    lapsed: dict = {}                                          # {FOLD: progress} — lapsed THIS step (evictable)
    for e in entries:
        sym, k = e["symbol"], CO.fold(e["symbol"])
        if k in mk:
            gone_now.append(_rec(sym, now, REASONS[3], text=_words().AUTO_ON_LIST_TEXT))
            continue
        if k in dk:
            continue                                           # recorded by dismiss
        if k in bk and C.AUTO_NOT_ELIGIBLE_REMOVES and (C.AUTO_NOT_ELIGIBLE_REMOVES_APLUS or not _is_aplus(e)):
            gone_now.append(_rec(sym, now, REASONS[6], text=GT.BROKER_FLAG_TEXT))     # 🚫 his list (spec watchfid)
            continue
        if _is_aplus(e) and C.AUTO_APLUS_STAYS:                # 🎯 an A+ seat stays all session (HIS CALL #2)
            kept.append(e)
            continue
        p = progress(sym, session, stores=stores, shared=shared, entry=e)
        if p["reason"] == REASONS[0]:
            gone_now.append(_rec(sym, now, REASONS[0], state=p["state"], source=p["source"], text=p["text"]))
            continue
        if p["reason"] == REASONS[1]:
            if sets is not None:                               # unknown boards → no "lapsed" judgement this step
                e["dropped_since"] = e.get("dropped_since") if _utc(e.get("dropped_since")) else now
                lapsed[k] = p                                  # 12:55 accumulate: STAYS (no grace removal)
        elif p["keep"] and not p["unknown"]:
            e["dropped_since"] = None
        kept.append(e)
    entries = kept
    merged = merge(sets) if sets is not None else []
    tracked = tracker_sets(session, shared=shared, docs=tdocs) if sets is not None else None
    by = {CO.fold(sym): (cand, srcs) for _ok, sym, cand, srcs in merged}
    for e in entries:                                          # words move, positions do not
        hit = by.get(CO.fold(e["symbol"])) if not _is_aplus(e) else None      # an A+ entry's words come from `aps`
        if hit:
            cand, srcs = hit
            e.update(sources=list(srcs), setup=cand["setup"], kind=cand["kind"], volume=cand["volume"],
                     volume_source=cand["volume_source"], float_shares=cand["float_shares"])
    skipped = {k: 0 for k in SKIPPED_KEYS}
    added: list = []
    aplus_skipped: list = []
    reason = None
    if sets is None:
        reason = STEP_REASONS[1]
    elif not in_window:
        reason = STEP_REASONS[2]
    else:
        have = {CO.fold(e["symbol"]) for e in entries}
        out_today = {CO.fold(r.get("symbol")) for r in removed + gone_now if isinstance(r.get("symbol"), str)}
        victims = [e for e in entries if CO.fold(e["symbol"]) in lapsed]           # oldest-added first (frozen order)
        evict = tracked is not None                            # a tracker fault → nothing removed for "made room"
        for sym, ap, srcs in aplus_arrivals(aps):              # 🎯 A+ FIRST (spec ggwaplus2 §3.3 step 4)
            k = CO.fold(sym)
            if k in mk or k in dk or k in have:
                continue
            if k in ss_read:                                   # ⛔🔒 C2: an ADDED name never takes a 🎯 seat
                ss_skip.add(k)
                continue
            if k in refuse_k:                                  # 🚫 never seated; not "aplus_skipped" (no free seat)
                refuse(sym)
                continue
            if not C.AUTO_APLUS_STAYS and k in out_today:      # the alternative of HIS CALL #2: a removal sticks today
                continue
            if len(entries) + len(added) >= C.AUTO_MAX_SYMBOLS:
                if not (evict and C.AUTO_APLUS_EVICTS):
                    aplus_skipped.append(sym)                  # a tracker fault / free seats only → never displace
                    continue
                was_lapsed = bool(victims)
                v = victims.pop(0) if was_lapsed else next((e for e in entries if not _is_aplus(e)), None)
                if v is None:
                    aplus_skipped.append(sym)                  # every seat an A+ (his names are not seats here)
                    continue
                vk = CO.fold(v["symbol"])
                entries = [e for e in entries if CO.fold(e["symbol"]) != vk]
                out_today.add(vk)
                if was_lapsed:
                    p = lapsed[vk]
                    text = _words().AUTO_MADE_ROOM_APLUS_LAPSED_TEXT.format(
                        new=sym, since_et=PT._hhmm(_utc(v["dropped_since"])))
                    gone_now.append(_rec(v["symbol"], now, REASONS[5], state=p.get("state"), source=p.get("source"),
                                         text=text))
                else:                                          # no lapsed name: the oldest-added 🧠 potential
                    gone_now.append(_rec(v["symbol"], now, REASONS[5],
                                         text=_words().AUTO_MADE_ROOM_APLUS_TEXT.format(new=sym)))
            scan_row = ((shared.get("scan_by") or {}).get(_up(sym)) or {}).get("last")
            vol, vsrc = volume_of(sym, scan_row, shared.get("trackers"))   # (None, None) when neither knows it — no floor
            have.add(k)
            added.append({"symbol": sym, "sources": list(srcs), "setup": ap.get("setup"), "kind": None,
                          "volume": vol, "volume_source": vsrc, "float_shares": None, "added_at": now,
                          "added_et": PT._hhmm(now), "dropped_since": None, "why": C.AUTO_APLUS_WHY,
                          "aplus": dict(ap), "promoted": False, "aplus_at": now, "aplus_et": PT._hhmm(now)})
        for sym, cand, srcs, tracker_only in arrivals(merged, tracked):
            k = CO.fold(sym)
            if k in mk or k in dk or k in have or (tracker_only and k in out_today):
                continue
            if k in (ss_any if tracker_only else ss_read):     # ⛔🔒 C2: never a 🤖 seat, never evicts
                ss_skip.add(k)
                continue
            if k in refuse_k:                                  # 🚫 before the volume floor — counted once, here
                refuse(sym)
                continue
            if not good_volume(cand):
                skipped[SKIPPED_KEYS[0] if PT._num(cand.get("volume")) is None else SKIPPED_KEYS[1]] += 1
                continue
            full = len(entries) + len(added) >= C.AUTO_MAX_SYMBOLS
            since = None
            if tracker_only:                                   # Amendment A2–A4: a FREE seat only, never evicts
                if full:
                    skipped[SKIPPED_KEYS[2]] += 1
                    continue
                p = progress(sym, session, stores=stores, shared=shared,
                             entry={"sources": list(srcs), "setup": cand["setup"]})
                if p["reason"] == REASONS[0]:
                    skipped[SKIPPED_KEYS[3]] += 1              # ↩️ / ✖️ already — it failed, never added
                    continue
                if not (p["keep"] and not p["unknown"]):
                    since = cand.get("last_at") or now         # the real lapse time (A3)
            elif full:
                if not (evict and victims):
                    skipped[SKIPPED_KEYS[2]] += 1              # full of live names — never displace one
                    continue
                v = victims.pop(0)
                vk = CO.fold(v["symbol"])
                entries = [e for e in entries if CO.fold(e["symbol"]) != vk]
                out_today.add(vk)
                p = lapsed[vk]
                text = _words().AUTO_MADE_ROOM_TEXT.format(new=sym, since_et=PT._hhmm(_utc(v["dropped_since"])))
                gone_now.append(_rec(v["symbol"], now, REASONS[4], state=p.get("state"), source=p.get("source"),
                                     text=text))
            have.add(k)
            added.append({"symbol": sym, "sources": list(srcs), "setup": cand["setup"], "kind": cand["kind"],
                          "volume": cand["volume"], "volume_source": cand["volume_source"],
                          "float_shares": cand["float_shares"], "added_at": now, "added_et": PT._hhmm(now),
                          "dropped_since": since})
        skipped[SKIPPED_KEYS[4]] = len(ne)
        skipped[SKIPPED_KEYS[5]] = len(ss_skip)                # ⛔🔒 C2: each ADDED name counted once
        entries = entries + added
    removed += gone_now
    res = {"symbols": [e["symbol"] for e in entries], "added": [e["symbol"] for e in added],
           "removed": [{k: r.get(k) for k in ("symbol", "reason", "state", "text")} for r in gone_now],
           "leaving": [e["symbol"] for e in entries if _utc(e.get("dropped_since"))],
           "n": len(entries), "cap": C.AUTO_MAX_SYMBOLS, "skipped": skipped, "reason": reason,
           "removed_total": len(removed), "aplus_skipped": aplus_skipped,
           "not_eligible": ne, "broker_fault": bool(bfault),
           # ✅ 2026-11-24 (spec watchall §3.4 [C7]): every A+ name of this step — seated, skipped or already held —
           # handed to allrules.step by the loop; [] when the A+ set is unknown or out of window
           "aplus_now": [sym for sym, _ap, _srcs in aplus_arrivals(aps)
                         if CO.fold(sym) not in ss_read] if aps is not None else []}   # ⛔🔒 C2: never a ✅ A+
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
                    "skipped": {k: 0 for k in SKIPPED_KEYS}, "reason": STEP_REASONS[0], "changed": False,
                    "aplus_skipped": [], "not_eligible": [], "broker_fault": False, "aplus_now": []}
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
    words = [C.AUTO_SOURCE_WORDS[k] for k in sources()]
    boards = ", ".join(words[:-1]) + " and " + words[-1] if len(words) > 1 else "".join(words)
    gone = " or ".join(_REMOVE_WORDS.get(s, s) for s in C.AUTO_REMOVE_STATES)
    stays = "; ".join(_KEEP_WORDS[s] for s in C.AUTO_KEEP_STATES if s in _KEEP_WORDS)
    frames = " / ".join(C.FRAME_WORDS[tf] for tf, _r in C.FRAMES if tf in C.PUSH_FRAMES)
    mode = push_mode()
    push = (f"auto names do not ring the {frames} cross (mode {mode})" if mode == C.AUTO_PUSH_MODES[0]
            else f"auto names ring the {frames} cross like yours (mode {mode})")
    return (f"🤖 Gajjala's Watch adds, once a minute during the {GC.PASS_OPEN_ET}–{GC.PASS_CLOSE_ET} ET pass window, every "
            f"name that came into a 🧠 potential on the {boards} boards at any time today with today's volume at or "
            f"over {C.AUTO_MIN_VOLUME:,} shares (GG's K11 floor; the scan row, else the pass's own stored number), up to "
            f"{C.AUTO_MAX_SYMBOLS} at a time, in the order added — a current potential first, then today's earlier ones "
            f"newest first into free seats only (one already {gone} is not added); an auto name stays all session and "
            f"leaves when every board reads it {gone}, or on your ×; at {C.AUTO_MAX_SYMBOLS} the oldest name whose "
            f"potential lapsed makes room for a current potential"
            + (f"; {stays} stays" if stays else "")
            + f"; a name that becomes {_words().APLUS_TEXT} on any of the {boards} boards today takes a seat at once, "
            f"ahead of the potentials (at {C.AUTO_MAX_SYMBOLS} it displaces the oldest name whose potential lapsed, "
            f"then the oldest-added potential, never another A+ or your own name) and stays all session — {gone} "
            f"never removes it"
            + (f"; {bw}" if (bw := broker_words()) else "")
            + f"; your own names are never touched; {push}. UNMEASURED.")


__all__ = ["REASONS", "STEP_REASONS", "STATES_DISMISS", "SKIPPED_KEYS", "read_doc", "entries_of", "current_symbols",
           "shared_sets", "volume_of", "read_sources", "sources", "potential_sets", "good_volume", "merge", "tracker_sets", "arrivals", "progress",
           "aplus_sets", "aplus_arrivals", "broker_gate", "broker_words",
           "step", "dismiss",
           "hold_crosses", "push_mode", "rules_line"]
