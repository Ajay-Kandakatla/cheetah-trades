"""👀 Gajjala's Watch — ✅ All rules met: the ONE engine (spec watchall rev 2, 2026-11-24 §3.3, WP be-engine).

Ajay 2026-11-24, verbatim: "Anytime stocks qualify all his rules should be auto added to the Watch list so I can keep
tracking them later" (with "Also Add every potential with all rules broke move to watch list.." · "That should be my
watch list").

WHAT. Once a minute, inside the Watch loop's lease and right AFTER `auto.step` (loop.run_iteration), `step` keeps a
THIRD doc `{_id: C.RULES_DOC_ID}` in the list collection (his doc "owner" and the 🤖 doc "auto" are never written here).
A name qualifies when a 🧠 tracker doc of the session carries a `state_path` turn into (GC.POTENTIAL_STATE,
GC.POTENTIAL_KINDS[0]) — "trigger armed": every rule met, only the break missing (potential.potential_kind, the 💧 push's
and the 🧠 armed push's own test) — with that session's volume (`auto.volume_of`: the scan row, else GG5's tracker
number) at or over C.RULES_MIN_VOLUME (GG's K11 floor); or when it is a 🎯 A+ (an A+ seat in the 🤖 doc, or a name of the
auto step's `aplus_now`; no extra floor).

KEPT. Uncapped (no 👤 / 🎯 / 🤖 seat is ever taken or evicted) and multi-session: an entry stays while its
`last_met_session` is inside `keep_window` — the last C.RULES_KEEP_SESSIONS market sessions, today included
(`context.history_window(next_market_day(session), N)`, the ledger's own "5d"). ↩️ / ✖️ never remove it. It leaves when
it ages out ("aged"), when its name joins his 🚫 list ("not_eligible", C.AUTO_NOT_ELIGIBLE_REMOVES) or on his ×
("dismissed", `dismiss`).

HIS ×. Every × he made blocks that (symbol, session) pair: the rules doc's own `dismissed` pairs ∪ the 🤖 doc's
`dismissed` of ITS session (auto.dismiss runs on EVERY DELETE, so it is the record of his × — [C1]). The 🤖 doc as read
BY THE LOOP BEFORE `auto.step` (`auto_prior`) is mirrored into the rules doc as `via: "auto"` pairs, so they survive the
04:00 🤖 reset. A fault reading it → no write at all (fail closed: an unknown × never seats).

BOUNDED BACK-FILL [C2]. On the first step of a new session, `auto_prior` still carries the PREVIOUS session (its ×
record intact), so that session's trackers are read once more — a pass after 20:05, a missed evening or a post-close
deploy is not lost. Older sessions are never back-filled (their × record is gone). The result says `backfilled`.
ONCE (2026-11-24 refix): the rules doc records every back-filled session in `backfilled_sessions` (pruned to the
window, written with the step's one compare-and-set); a session already recorded is never read again — so a 🤖 doc
left on yesterday (no entries, removals or × yesterday and none yet today: auto._changed writes nothing) does not
re-read yesterday every minute all day.

Writes are ONE compare-and-set `update_one` (auto._cas, doc id C.RULES_DOC_ID). Every stamp is the caller's `now`.
Never a fetch, never a push, never a claim; C.RULES_PUSH_MODE ("off") keeps these names out of the 1-min cross push
(loop.py holds them `suppressed_auto`). Display / tracking only. UNMEASURED.

⛔🩳🔒 SI / SSR / Reg SHO POTENTIALS (2026-11-24, spec sissr rev 2 §3.6 — Ajay, verbatim: "Then potentials to be alerts
sooner - add them to watch list and give them a time stamp of the day" · "Days past little bit like AKAN is what I am
mainly looking for"). The SAME step, the SAME doc, the SAME × / 🚫 / keep window — no second seating path. A 🧠 tracker
doc carrying potential.track's one-time `si_ssr` stamp (the first pass the name was tagged AND a potential) is a THIRD
kind of record, C.RULES_KINDS[2], at the same K11 floor (`skip` honoured as for armed). Precedence aplus > armed > si_ssr:
an entry never downgrades, and a si_ssr entry that later arms or turns A+ becomes ✅ (its met times then come from the ✅
records). A si_ssr-only record never refreshes a ✅ entry's met times. The entry keeps the EARLIEST stamp (`si_ssr`). A
tracker doc of an ADDED ⛔🔒 name (`si_ssr_add`, si_ssr_names.is_add — it failed GG's own scanner rule) yields NO armed
record [C2]; it can only sit in "sissr". 🚫 names of kind si_ssr only are counted apart (`not_eligible_sissr`).
"""
from __future__ import annotations

import copy
import logging
from datetime import date, datetime, timezone
from typing import Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import tab as GT                   # the 🚫 word / icon (auto.py imports it too)
from chart_maps.gajjala import variant as V

from . import auto as AUTO
from . import colls as CO
from . import constants as C
from .store import _CAS_TRIES

log = logging.getLogger("chart_maps.gajjala_watch.allrules")

_UNREAD = object()                                             # step: "read the auto doc yourself"
BY_LOOP = AUTO.BY_LOOP
_STAMPS = ("first_met_at", "last_met_at", "added_at")
BACKFILLED_KEY = "backfilled_sessions"                         # the rules doc's record of the sessions back-filled once


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _as_date(session) -> Optional[date]:
    if isinstance(session, datetime):
        return session.date()
    if isinstance(session, date):
        return session
    try:
        return date.fromisoformat(str(session or "")[:10])
    except ValueError:
        return None


def _u(t) -> Optional[datetime]:
    """A stamp as aware UTC cut to the millisecond (what Mongo keeps), so a stored stamp compares equal to the one it
    was written from; anything but a datetime → None."""
    t = AUTO._utc(t)
    return t.replace(microsecond=t.microsecond // 1000 * 1000) if t is not None else None


def _at(x) -> Optional[datetime]:
    """A state_path `at` (an ISO string; a datetime too — naive = UTC, the store's rule) → aware UTC (ms); else None."""
    if isinstance(x, datetime):
        return _u(x)
    if isinstance(x, str) and x:
        try:
            return _u(datetime.fromisoformat(x))
        except ValueError:
            return None
    return None


def _armed_stamps(doc) -> list:
    path = doc.get("state_path") if isinstance(doc, dict) else None
    if not isinstance(path, list):
        return []
    out = []
    for e in path:
        if isinstance(e, dict) and (e.get("state"), e.get("kind")) == (GC.POTENTIAL_STATE, GC.POTENTIAL_KINDS[0]):
            t = _at(e.get("at"))
            if t is not None:
                out.append(t)
    return out


def _ssn():
    """The ⛔🔒 names step (chart_maps.gajjala.si_ssr_names), imported LAZILY — its `is_add` is the ONE add test."""
    from chart_maps.gajjala import si_ssr_names as SSN
    return SSN


def si_ssr_stamp(doc) -> Optional[dict]:
    """⛔🩳🔒 the tracker doc's stored one-time stamp (potential.track, key PT.SI_SSR_TAG_KEY) as a copy with `first_at`
    as aware UTC (ms) — None when absent, not a dict, without a readable `first_at` or without a source key."""
    st = doc.get(PT.SI_SSR_TAG_KEY) if isinstance(doc, dict) else None
    if not isinstance(st, dict):
        return None
    t = _at(st.get("first_at"))
    keys = st.get("keys")
    if t is None or not (isinstance(keys, list) and any(isinstance(k, str) and k for k in keys)):
        return None
    out = copy.deepcopy(st)
    out["first_at"] = t
    return out


def first_si_ssr_at(doc) -> Optional[datetime]:
    """⛔🩳🔒 the stamp's `first_at` (aware UTC, ms) — None when the doc carries no readable stamp."""
    st = si_ssr_stamp(doc)
    return st["first_at"] if st is not None else None


def _is_add_doc(doc) -> bool:
    try:
        return bool(_ssn().is_add(doc))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch ✅: the add test failed: %s", type(exc).__name__)
        return True                                             # fail closed: an unknown add never seats in ✅


def first_armed_at(doc) -> Optional[datetime]:
    """The EARLIEST state_path turn into (forming, armed) — aware UTC; None when none / malformed."""
    s = _armed_stamps(doc)
    return min(s) if s else None


def last_armed_at(doc) -> Optional[datetime]:
    """The LATEST state_path turn into (forming, armed) [C8] — aware UTC; None when none / malformed."""
    s = _armed_stamps(doc)
    return max(s) if s else None


def keep_window(session) -> list:
    """The last C.RULES_KEEP_SESSIONS market sessions, today included, oldest first — `context.history_window(
    next_market_day(session), N)` (the ledger's "5d" span). [] when the session is unreadable."""
    d = _as_date(session)
    if d is None:
        return []
    from catalysts.medical.reaction import next_market_day   # lazy: the house calendar
    from chart_maps.gajjala import context as CX              # lazy: keeps the loop child's import graph
    return list(CX.history_window(next_market_day(d), C.RULES_KEEP_SESSIONS))


def _window_isos(session) -> set:
    return {d.isoformat() for d in keep_window(session)}


def push_mode() -> str:
    """C.RULES_PUSH_MODE when it is one of C.AUTO_PUSH_MODES, else "off" (fail closed). Read at CALL time."""
    m = C.RULES_PUSH_MODE
    return m if isinstance(m, str) and m in C.AUTO_PUSH_MODES else C.AUTO_PUSH_MODES[0]


# ── the doc ───────────────────────────────────────────────────────────────────────────────────────────────────────
def read_doc(cs) -> Optional[dict]:
    """The rules doc ({} when missing); None on a read fault (no "list" handle, or find_one raised). Never raises."""
    c = cs.get("list") if isinstance(cs, dict) else None
    if c is None:
        return None
    try:
        d = c.find_one({"_id": C.RULES_DOC_ID})
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch ✅: rules doc unreadable: %s", type(exc).__name__)
        return None
    return d if isinstance(d, dict) else {}


def _entries(doc) -> list:
    """Deep copies of the doc's entries (dicts with a non-blank str symbol), fold-de-duplicated (first wins), stamps
    normalised to aware UTC (Mongo hands back naive UTC) so an unchanged doc compares equal."""
    out, keys = [], set()
    for e in (doc.get("entries") if isinstance(doc, dict) else None) or []:
        if not (isinstance(e, dict) and isinstance(e.get("symbol"), str) and e["symbol"].strip()):
            continue
        k = CO.fold(e["symbol"])
        if k in keys:
            continue
        keys.add(k)
        e = copy.deepcopy(e)
        for f in _STAMPS:
            if f in e:
                e[f] = _u(e[f])
        if isinstance(e.get(PT.SI_SSR_TAG_KEY), dict) and "first_at" in e[PT.SI_SSR_TAG_KEY]:
            e[PT.SI_SSR_TAG_KEY]["first_at"] = _u(e[PT.SI_SSR_TAG_KEY]["first_at"])
        out.append(e)
    return out


def _pairs_list(doc, key: str) -> list:
    out = []
    for r in (doc.get(key) if isinstance(doc, dict) else None) or []:
        if isinstance(r, dict) and isinstance(r.get("symbol"), str):
            r = copy.deepcopy(r)
            if "at" in r:
                r["at"] = _u(r["at"])
            out.append(r)
    return out


def _backfilled_of(doc) -> list:
    """The sessions the rules doc recorded as back-filled (ISO strings, sorted, de-duplicated); [] when none."""
    xs = doc.get(BACKFILLED_KEY) if isinstance(doc, dict) else None
    return sorted({x for x in xs if isinstance(x, str)}) if isinstance(xs, list) else []


def entries_in_window(doc, session) -> list:
    """The entries whose `last_met_session` is inside `keep_window(session)`; fold-de-duplicated; stored order."""
    win = _window_isos(session)
    return [e for e in _entries(doc) if e.get("last_met_session") in win]


def current_symbols(cs, session) -> list:
    """House spellings of `entries_in_window` (stored order); C.RULES_ON off, a fault or nothing → []."""
    if not C.RULES_ON:
        return []
    doc = read_doc(cs)
    if not doc:
        return []
    return [CO.house(e["symbol"]) for e in entries_in_window(doc, session)]


def blocked(doc, auto_prior, session) -> set:
    """{(FOLD, ISO)} — every × he made: the rules doc's `dismissed` pairs ∪ the 🤖 doc's `dismissed` of ITS session
    [C1]. Pairs outside `keep_window(session)` are dropped (they can block nothing that is read)."""
    win = _window_isos(session)
    out = set()
    for r in _pairs_list(doc, "dismissed"):
        s = r.get("session")
        if isinstance(s, str) and s in win:
            out.add((CO.fold(r["symbol"]), s))
    ps = auto_prior.get("session") if isinstance(auto_prior, dict) else None
    if isinstance(ps, str) and ps in win:
        for s in auto_prior.get("dismissed") or []:
            if isinstance(s, str) and s.strip():
                out.add((CO.fold(s), ps))
    return out


# ── qualifiers ────────────────────────────────────────────────────────────────────────────────────────────────────
def _rec(sym, session, kind, *, setup=None, setups=(), sources=(), volume=None, volume_source=None, first=None,
         last=None, skip=None) -> dict:
    return {"fold": CO.fold(sym), "symbol": CO.house(sym), "session": session, "kind": kind, "setup": setup,
            "setups": list(setups), "sources": list(sources), "volume": volume, "volume_source": volume_source,
            "first": first, "last": last, "skip": skip}


def _vol_skip(vol) -> Optional[str]:
    v = PT._num(vol)
    if v is None:
        return C.RULES_SKIPPED_KEYS[4]                         # volume_unknown
    if v < C.RULES_MIN_VOLUME:
        return C.RULES_SKIPPED_KEYS[3]                         # under_floor
    return None


def qualifiers(isos, *, stores, tdocs_by_iso, aplus, auto_prior) -> Optional[list]:
    """[record] — one per (fold, session) armed qualifier, plus one per A+ name (kind "aplus"). None = unknown (a read
    fault of the scan set). An armed record of a session: the earliest first / the latest last armed stamp across its
    tracker docs, every armed setup (GC.SETUPS order), the read sources it appears in + their borrowers (auto.merge's
    rule), the volume of THAT session (`auto.volume_of`) — None → `skip` volume_unknown, under the floor → under_floor.
    A+ records (no floor): every 🤖 entry with `why` C.AUTO_APLUS_WHY of `auto_prior`'s session (when it is read here)
    and every name of `aplus` (the auto step's `aplus_now`) for today's session (isos[0])."""
    bor, act = AUTO._borrowers(), AUTO.sources()
    recs: list = []
    shared_by: dict = {}
    for s in isos:
        try:
            shared = AUTO.shared_sets(_as_date(s), store=(stores or {}).get(V.GG5.key),
                                      tracker_docs=(tdocs_by_iso.get(s) or {}).get(V.GG5.key))
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala watch ✅: scan set unreadable: %s", type(exc).__name__)
            return None
        shared_by[s] = shared
        by: dict = {}
        sby: dict = {}                                          # ⛔🩳🔒 {FOLD: stamped trackers} (spec sissr §3.6)
        for key in AUTO.read_sources():
            for d in (tdocs_by_iso.get(s) or {}).get(key) or []:
                sym = AUTO._up(d.get("symbol")) if isinstance(d, dict) else ""
                stamp = si_ssr_stamp(d) if sym else None
                if stamp is not None:
                    _stamp_into(sby, sym, d, stamp, key)
                fa = first_armed_at(d) if sym else None
                if fa is None or _is_add_doc(d):                # [C2] an ADDED ⛔🔒 name is never an armed record
                    continue
                la = last_armed_at(d)
                setup = d.get("setup") if isinstance(d.get("setup"), str) else None
                k = CO.fold(sym)
                cur = by.get(k)
                if cur is None:
                    by[k] = {"sym": sym, "first": fa, "last": la, "setup": setup, "setups": {setup} - {None},
                             "present": {key}}
                    continue
                cur["present"].add(key)
                cur["setups"].discard(None)
                if setup is not None:
                    cur["setups"].add(setup)
                if la is not None and (cur["last"] is None or la > cur["last"]):
                    cur["last"] = la
                if (fa, AUTO._setup_rank(setup)) < (cur["first"], AUTO._setup_rank(cur["setup"])):
                    cur.update(first=fa, setup=setup)
        scan_by = shared.get("scan_by") or {}
        for _k, t in by.items():
            vol, vsrc = AUTO.volume_of(t["sym"], (scan_by.get(t["sym"]) or {}).get("last"), shared.get("trackers"))
            setups = sorted(t["setups"], key=lambda x: (AUTO._setup_rank(x), x))
            srcs = [x for x in act if x in t["present"] or bor.get(x) in t["present"]]
            recs.append(_rec(t["sym"], s, C.RULES_KINDS[0], setup=t["setup"], setups=setups, sources=srcs,
                             volume=vol, volume_source=vsrc, first=t["first"], last=t["last"], skip=_vol_skip(vol)))
        for _k, t in sby.items():                               # ⛔🩳🔒 one si_ssr record per (fold, session)
            vol, vsrc = AUTO.volume_of(t["sym"], (scan_by.get(t["sym"]) or {}).get("last"), shared.get("trackers"))
            setups = sorted(t["setups"], key=lambda x: (AUTO._setup_rank(x), x))
            srcs = [x for x in act if x in t["present"] or bor.get(x) in t["present"]]
            r = _rec(t["sym"], s, C.RULES_KINDS[2], setup=t["setup"], setups=setups, sources=srcs, volume=vol,
                     volume_source=vsrc, first=t["first"], last=t["last"], skip=_vol_skip(vol))
            r["si_ssr"] = t["stamp"]
            recs.append(r)
    ps = auto_prior.get("session") if isinstance(auto_prior, dict) else None
    if isinstance(ps, str) and ps in shared_by:
        for e in AUTO.entries_of(auto_prior, ps):
            if not AUTO._is_aplus(e):
                continue
            sh = shared_by[ps]
            vol, vsrc = AUTO.volume_of(e["symbol"], ((sh.get("scan_by") or {}).get(AUTO._up(e["symbol"])) or {})
                                       .get("last"), sh.get("trackers"))
            t = _u(e.get("aplus_at")) or _u(e.get("added_at"))
            setup = e.get("setup") if isinstance(e.get("setup"), str) else None
            recs.append(_rec(e["symbol"], ps, C.RULES_KINDS[1], setup=setup, setups=[setup] if setup else [],
                             sources=[x for x in e.get("sources") or [] if isinstance(x, str)], volume=vol,
                             volume_source=vsrc, first=t, last=t))
    if isos and aplus:
        s0 = isos[0]
        sh = shared_by.get(s0) or {}
        for sym in aplus:
            if not (isinstance(sym, str) and sym.strip()):
                continue
            vol, vsrc = AUTO.volume_of(sym, ((sh.get("scan_by") or {}).get(AUTO._up(sym)) or {}).get("last"),
                                       sh.get("trackers"))
            recs.append(_rec(sym, s0, C.RULES_KINDS[1], volume=vol, volume_source=vsrc))   # stamps: `now` if new
    return recs


def _stamp_into(sby: dict, sym: str, d: dict, stamp: dict, key: str) -> None:
    """Fold one stamped tracker doc into `sby`: the EARLIEST stamp (then GC.SETUPS order) wins the setup and the stamp,
    the latest `first_at` is `last`, every setup and read source is kept."""
    setup = stamp.get("setup") if isinstance(stamp.get("setup"), str) else (
        d.get("setup") if isinstance(d.get("setup"), str) else None)
    t0 = stamp["first_at"]
    k = CO.fold(sym)
    cur = sby.get(k)
    if cur is None:
        sby[k] = {"sym": sym, "first": t0, "last": t0, "setup": setup, "setups": {setup} - {None}, "present": {key},
                  "stamp": stamp}
        return
    cur["present"].add(key)
    if setup is not None:
        cur["setups"].add(setup)
    if t0 > cur["last"]:
        cur["last"] = t0
    if (t0, AUTO._setup_rank(setup)) < (cur["first"], AUTO._setup_rank(cur["setup"])):
        cur.update(first=t0, setup=setup, stamp=stamp)


# ── the minute step ───────────────────────────────────────────────────────────────────────────────────────────────
def _removed_rec(sym, now, iso, reason, text=None) -> dict:
    return {"symbol": sym, "at": now, "at_et": PT._hhmm(now), "session": iso, "reason": reason, "text": text}


def _words_of(rs: list) -> dict:
    """setup / setups / sources / volume from one session's records — an A+ setup first, else the armed one."""
    ap = [r for r in rs if r["kind"] == C.RULES_KINDS[1]]
    ar = [r for r in rs if r["kind"] == C.RULES_KINDS[0]]
    ss = [r for r in rs if r["kind"] == C.RULES_KINDS[2]]      # ⛔🩳🔒 [C9] the fallback when no ✅ record
    setup = next((r["setup"] for r in ap + ar + ss if r["setup"]), None)
    setups: list = []
    for r in ar + ap + (ss if not (ar or ap) else []):
        for x in r["setups"]:
            if x and x not in setups:
                setups.append(x)
    setups.sort(key=lambda x: (AUTO._setup_rank(x), x))
    present = {x for r in rs for x in r["sources"]}
    sources = [x for x in C.AUTO_SOURCES if x in present] + sorted(present - set(C.AUTO_SOURCES))
    vr = next((r for r in ar + ap + ss if PT._num(r["volume"]) is not None), None)
    return {"setup": setup, "setups": setups, "sources": sources,
            "volume": PT._num(vr["volume"]) if vr else None, "volume_source": vr["volume_source"] if vr else None}


_PRECEDENCE = (C.RULES_KINDS[2], C.RULES_KINDS[0], C.RULES_KINDS[1])     # ⛔🩳🔒 si_ssr < armed < aplus


def _rank(kind) -> int:
    """The kind's precedence (an unknown kind ranks below si_ssr — it never wins)."""
    return _PRECEDENCE.index(kind) + 1 if kind in _PRECEDENCE else 0


def _earliest_stamp(stamps) -> Optional[dict]:
    """The stamp with the earliest readable `first_at` (aware UTC); None when none is readable."""
    best = None
    for st in stamps:
        t = _u(st.get("first_at")) if isinstance(st, dict) else None
        if t is not None and (best is None or t < best[0]):
            best = (t, st)
    return dict(copy.deepcopy(best[1]), first_at=best[0]) if best is not None else None


def _compute(doc, now, iso, recs, manual, bk, auto_prior, backfilled=()) -> tuple:
    win = _window_isos(iso)
    entries = _entries(doc)
    dismissed = _pairs_list(doc, "dismissed")
    removed = _pairs_list(doc, "removed")
    marks0 = _backfilled_of(doc)
    stored = (copy.deepcopy(entries), copy.deepcopy(dismissed), copy.deepcopy(removed), marks0)
    mk = {CO.fold(m) for m in manual or [] if isinstance(m, str)}
    blk = blocked(doc, auto_prior, iso)
    skipped = {k: 0 for k in C.RULES_SKIPPED_KEYS}
    ne_by: dict = {}                                           # {FOLD: [house spelling, {kinds}]} — first-refusal order
    survivors: dict = {}
    for r in recs:
        if r["kind"] in (C.RULES_KINDS[0], C.RULES_KINDS[2]) and r["skip"]:     # ⛔🩳🔒 [C9] the floor for both
            skipped[r["skip"]] += 1
            continue
        k = r["fold"]
        if k in mk:
            skipped[C.RULES_SKIPPED_KEYS[0]] += 1
            continue
        if (k, r["session"]) in blk:
            skipped[C.RULES_SKIPPED_KEYS[1]] += 1
            continue
        if k in bk:
            skipped[C.RULES_SKIPPED_KEYS[2]] += 1
            ne_by.setdefault(k, [r["symbol"], set()])[1].add(r["kind"])
            continue
        survivors.setdefault(k, []).append(r)
    ne = [v[0] for v in ne_by.values() if v[1] - {C.RULES_KINDS[2]}]           # ✅ 🚫 (an armed / A+ record)
    ne_ss = [v[0] for v in ne_by.values() if not (v[1] - {C.RULES_KINDS[2]})]  # ⛔🩳🔒 🚫 (si_ssr records only) [C5]
    by = {CO.fold(e["symbol"]): e for e in entries}
    added: list = []
    for k, rs in survivors.items():
        stamp = _earliest_stamp([r.get("si_ssr") for r in rs])
        kind = max((r["kind"] for r in rs), key=_rank)
        core = [r for r in rs if r["kind"] != C.RULES_KINDS[2]]
        use = core or rs                                       # ✅ records decide the met times when there are any
        newest = max(r["session"] for r in use)
        words = _words_of([r for r in rs if r["session"] == newest])
        firsts = [r["first"] for r in use if r["first"] is not None]
        lasts = [r["last"] for r in use if r["last"] is not None]
        sess = sorted({r["session"] for r in use})
        e = by.get(k)
        if e is None:
            e = dict(symbol=rs[0]["symbol"], kind=kind, **words,
                     first_met_at=min(firsts) if firsts else now, first_met_session=sess[0],
                     last_met_at=max(lasts) if lasts else (max(firsts) if firsts else now), last_met_session=newest,
                     sessions=[x for x in sess if x in win], added_at=now)
            if stamp is not None:
                e["si_ssr"] = stamp
            entries.append(e)
            by[k] = e
            added.append(e["symbol"])
            continue
        if stamp is not None:                                  # ⛔🩳🔒 the entry keeps the EARLIEST stamp
            e["si_ssr"] = _earliest_stamp([e.get("si_ssr"), stamp])
        old_kind = e.get("kind")
        if not core and old_kind != C.RULES_KINDS[2]:
            continue                                           # a si_ssr-only read never refreshes a ✅ entry
        if core and old_kind == C.RULES_KINDS[2]:              # promoted to ✅: its met times are the ✅ records'
            e.update(kind=kind, first_met_at=min(firsts) if firsts else now, first_met_session=sess[0],
                     last_met_at=max(lasts) if lasts else (max(firsts) if firsts else now), last_met_session="",
                     sessions=[])
        elif _rank(kind) > _rank(old_kind):
            e["kind"] = kind                                   # an A+ wins; an armed read never downgrades it
        old_last_s = e.get("last_met_session") if isinstance(e.get("last_met_session"), str) else ""
        if firsts:
            f0 = _u(e.get("first_met_at"))
            e["first_met_at"] = min(firsts + ([f0] if f0 else []))
        if lasts:
            l0 = _u(e.get("last_met_at"))
            e["last_met_at"] = max(lasts + ([l0] if l0 else []))                   # [C8]
        fs = e.get("first_met_session") if isinstance(e.get("first_met_session"), str) else None
        e["first_met_session"] = min([sess[0]] + ([fs] if fs else []))
        e["last_met_session"] = max(newest, old_last_s)
        old = [x for x in e.get("sessions") or [] if isinstance(x, str)]
        e["sessions"] = sorted(x for x in set(old) | set(sess) if x in win)
        if newest >= old_last_s:                               # words refreshed only from the NEWEST session —
            e.update({w: v for w, v in words.items() if v not in (None, [])})   # a word it lacks keeps the stored one
    kept: list = []
    gone: list = []
    for e in entries:
        k = CO.fold(e["symbol"])
        if e.get("last_met_session") not in win:
            gone.append(_removed_rec(e["symbol"], now, iso, C.RULES_REASONS[0]))
            continue
        if k in bk and C.AUTO_NOT_ELIGIBLE_REMOVES:
            gone.append(_removed_rec(e["symbol"], now, iso, C.RULES_REASONS[2], GT.BROKER_FLAG_TEXT))
            continue
        kept.append(e)
    entries = kept
    added = [s for s in added if CO.fold(s) in {CO.fold(e["symbol"]) for e in entries}]
    have = {(CO.fold(r["symbol"]), r.get("session")) for r in dismissed}
    ps = auto_prior.get("session") if isinstance(auto_prior, dict) else None
    if isinstance(ps, str) and ps in win:                      # mirror his 🤖 × so it survives the 04:00 reset
        for s in auto_prior.get("dismissed") or []:
            if isinstance(s, str) and s.strip() and (CO.fold(s), ps) not in have:
                have.add((CO.fold(s), ps))
                dismissed.append({"symbol": CO.house(s), "session": ps, "at": now, "via": "auto"})
    removed = [r for r in removed + gone if r.get("session") in win]
    dismissed = [r for r in dismissed if r.get("session") in win]
    res = {"symbols": [CO.house(e["symbol"]) for e in entries], "added": added,
           "removed": [{k: r.get(k) for k in ("symbol", "reason", "text")} for r in gone], "n": len(entries),
           "skipped": skipped, "reason": None, "not_eligible": ne, "not_eligible_sissr": ne_ss}
    marks = sorted({x for x in marks0 + list(backfilled) if x in win})   # the back-fill record, pruned to the window
    res["changed"] = (entries, dismissed, removed, marks) != stored
    return res, {"entries": entries, "dismissed": dismissed, "removed": removed, BACKFILLED_KEY: marks}


def _early(reason, symbols=None, backfilled=None) -> dict:
    syms = list(symbols or [])
    return {"symbols": syms, "added": [], "removed": [], "n": len(syms),
            "skipped": {k: 0 for k in C.RULES_SKIPPED_KEYS}, "reason": reason, "changed": False, "not_eligible": [],
            "backfilled": list(backfilled or []), "not_eligible_sissr": []}


def step(now, session, *, db=None, manual: list, dry: bool = False, stores: Optional[dict] = None,
         auto_prior=_UNREAD, aplus: Optional[list] = None) -> dict:
    """THE minute step (module docstring; spec §3.3 steps 1–10) -> {symbols, added, removed, n, skipped, reason,
    changed, not_eligible, backfilled} (+ `writes` when dry). `auto_prior` = the 🤖 doc as the loop read it BEFORE
    auto.step (`_UNREAD` → read here); `aplus` = the auto step's `aplus_now`. Never raises on a read fault."""
    now = _u(RUN._utc(now))
    iso = AUTO._iso(session)
    if not C.RULES_ON:
        return _early(C.RULES_STEP_REASONS[0])
    cs = CO.colls(db)
    if not RUN.in_window(now):                                 # a closed day included — no write
        return _early(C.RULES_STEP_REASONS[1], current_symbols(cs, iso))
    doc = read_doc(cs)
    if doc is None:
        return _early(C.RULES_STEP_REASONS[2])
    syms0 = [CO.house(e["symbol"]) for e in entries_in_window(doc, iso)]
    prior = AUTO.read_doc(cs) if auto_prior is _UNREAD else auto_prior
    if not isinstance(prior, dict):                            # [C1] fail closed: an unknown × never seats
        return _early(C.RULES_STEP_REASONS[5], syms0)
    win = _window_isos(iso)
    isos = [iso]
    ps = prior.get("session")
    if isinstance(ps, str) and ps != iso and ps in win and ps not in _backfilled_of(doc):   # [C2] ONE previous
        isos.append(ps)                                        # session, ONCE (recorded in BACKFILLED_KEY)
    backfilled = isos[1:]
    stores = stores if stores is not None else AUTO._default_stores()
    tdocs_by_iso = {s: {k: AUTO._tracker_docs((stores or {}).get(k), s, fields=C.RULES_TRACKER_FIELDS)
                        for k in AUTO.read_sources()} for s in isos}
    if any(v is None for per in tdocs_by_iso.values() for v in per.values()):
        return _early(C.RULES_STEP_REASONS[3], syms0, backfilled)
    bk, bfault = AUTO.broker_gate(stores)
    if bfault:
        return _early(C.RULES_STEP_REASONS[4], syms0, backfilled)
    recs = qualifiers(isos, stores=stores, tdocs_by_iso=tdocs_by_iso, aplus=aplus, auto_prior=prior)
    if recs is None:
        return _early(C.RULES_STEP_REASONS[3], syms0, backfilled)
    res: dict = {}
    for _ in range(_CAS_TRIES):
        res, new = _compute(doc, now, iso, recs, manual, bk, prior, backfilled)
        res["backfilled"] = list(backfilled)
        if dry:
            res["writes"] = new
            return res
        if not res["changed"]:
            return res
        try:
            if AUTO._cas(cs["list"], doc, dict(new, updated_at=now, by=BY_LOOP), doc_id=C.RULES_DOC_ID):
                return res
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala watch ✅: rules write failed: %s", type(exc).__name__)
            break
        doc = read_doc(cs)
        if doc is None:
            break
    log.warning("gajjala watch ✅: the rules write did not land")
    syms = current_symbols(cs, iso)
    return dict(res or _early(None), symbols=syms, n=len(syms), added=[], removed=[], changed=False,
                reason=C.RULES_STEP_REASONS[6], backfilled=list(backfilled))


# ── his × on a ✅ name (api.py DELETE) ─────────────────────────────────────────────────────────────────────────────
def dismiss(symbol, *, by, db=None, now=None) -> dict:
    """His ×: pulls the entry (removed "dismissed") and records the (symbol, today's session) pair `via` "rules" — the
    name is not seated again THIS session even if it re-arms (HIS CALL #4); a later session's qualification seats it
    again. -> {state ∈ auto.STATES_DISMISS, symbols (his), symbol, text}. A non-ticker → "absent" without a read.
    Never raises (a fault → "error")."""
    from . import build as BLD
    from .store import normalize
    sym = normalize(symbol)
    if sym is None:
        return AUTO._dismiss_answer(AUTO.STATES_DISMISS[1], None, db)
    try:
        now = _u(RUN._utc(now) if now is not None else datetime.now(timezone.utc))
        cs = CO.colls(db)
        if cs is None:
            return AUTO._dismiss_answer(AUTO.STATES_DISMISS[2], sym, db)
        iso = BLD.session_of(now)[0].isoformat()
        win = _window_isos(iso)
        k = CO.fold(sym)
        for _ in range(_CAS_TRIES):
            doc = read_doc(cs)
            if doc is None:
                return AUTO._dismiss_answer(AUTO.STATES_DISMISS[2], sym, db)
            entries = _entries(doc)
            dismissed = _pairs_list(doc, "dismissed")
            removed = _pairs_list(doc, "removed")
            hit = [e for e in entries if CO.fold(e["symbol"]) == k]
            state = AUTO.STATES_DISMISS[0] if hit else AUTO.STATES_DISMISS[1]
            if hit:
                entries = [e for e in entries if CO.fold(e["symbol"]) != k]
                removed.append(_removed_rec(hit[0]["symbol"], now, iso, C.RULES_REASONS[1],
                                            AUTO._words().AUTO_DISMISSED_TEXT))
            if (k, iso) not in {(CO.fold(r["symbol"]), r.get("session")) for r in dismissed}:
                dismissed.append({"symbol": sym, "session": iso, "at": now, "via": "rules"})
            elif not hit:
                return AUTO._dismiss_answer(state, sym, db)     # already blocked this session — nothing to write
            new = {"entries": entries, "dismissed": [r for r in dismissed if r.get("session") in win],
                   "removed": [r for r in removed if r.get("session") in win]}
            if AUTO._cas(cs["list"], doc, dict(new, updated_at=now, by=by if isinstance(by, str) else None),
                         doc_id=C.RULES_DOC_ID):
                return AUTO._dismiss_answer(state, sym, db)
        log.warning("gajjala watch ✅: dismiss %s lost the compare-and-set %d times", sym, _CAS_TRIES)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch ✅: dismiss %s failed: %s", sym, type(exc).__name__)
    return AUTO._dismiss_answer(AUTO.STATES_DISMISS[2], sym, db)


# ── ℹ️ ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def rules_line() -> str:
    """The ℹ️ clause — every number and word from the constants at CALL time (never typed here)."""
    words = [C.AUTO_SOURCE_WORDS[k] for k in AUTO.sources()]
    boards = ", ".join(words[:-1]) + " and " + words[-1] if len(words) > 1 else "".join(words)
    keys = list(C.SECTION_KEYS)
    before = [C.SECTION_WORDS[k] for k in keys[:keys.index("rules")]] if "rules" in keys else []
    after = (", ".join(before[:-1]) + " and " + before[-1] if len(before) > 1 else "".join(before))
    mode = push_mode()
    broker = ""
    if C.AUTO_SKIP_NOT_ELIGIBLE:
        broker = f"; a name on your {GT.BROKER_FLAG_ICON} list is never added" + (
            " and a kept one leaves at the next minute" if C.AUTO_NOT_ELIGIBLE_REMOVES else "")
    return (f"{C.RULES_TAG} Gajjala's Watch keeps every name that met all of Gajjala's rules on the {boards} boards — "
            f"trigger armed (only the break missing) with that session's volume at or over {C.RULES_MIN_VOLUME:,} "
            f"shares (GG's K11 floor) — and every {AUTO._words().APLUS_TEXT}, newest first, with no cap"
            + (f", shown after {after}" if after else "")
            + f"; it stays until {C.RULES_KEEP_SESSIONS} sessions (today included) pass without it meeting them again, "
            f"or your × (which holds for that session); ↩️ / ✖️ never remove it; your own names are never added"
            + broker
            + f"; this list never rings (mode {mode}) — the board's pushes are unchanged. UNMEASURED.")


__all__ = ["first_armed_at", "last_armed_at", "keep_window", "read_doc", "entries_in_window", "current_symbols",
           "blocked", "qualifiers", "step", "dismiss", "rules_line", "push_mode"]
