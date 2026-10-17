"""Gajjala's tab — Mongo storage (spec §3.1.6). Written by the cron pass / nightly and by the owner's on-open pass
(run.run_on_demand — `python -m chart_maps.gajjala.run --on-demand`, a subprocess the api spawns); the GET endpoint reads.

Collections
  gajjala_scan      _id "{date}|{SYM}"         every scanner qualifier of a session (+ split check)        TTL 30 d on `at`
  gajjala_ah_carry  _id "{date}"               the session's after-hours carry set — REPLACED per AH pass  TTL 30 d
  gajjala_post      _id "{date}|{SYM}"         🌙 K10 confirmations                                         TTL 30 d
  gajjala_passes    _id "{date}|{HH:MM}" (cron) | "{date}|{HH:MM:SS}|open" (on-open) + "latest" + "latest_cron"
                    one doc per pass (counts, strip, snapshot meta); "latest" = any pass, "latest_cron" = cron only TTL 30 d
  gajjala_reads     _id "{date}|{SYM}"         detector reads + tile bars                                   TTL 14 d
  gajjala_alerts    _id "GG:{date}|{SYM}|{setup}"   the push ledger (demand_alerts.claim_key docs)         none
  gajjala_halts     _id "{date}|{SYM}"         halts per session (live + 30-session backfill)              none
  gajjala_daily     _id "{date}|{SYM}"         squeeze history + the float read of the session             TTL 30 d
  gajjala_state     _id "lease" | "float_backoff" | "types" | "broker_flags"                                  —
                    lease = {status running|done, held_by cron|on_demand, token (the holder's uuid4 hex), claimed_at,
                    started_at + last_cron_started_at (CRON claims only — the tick clock, the min-gap clock),
                    od_started_at (on-open claims only), pid, done_at}
                    broker_flags = {added: [SYM…], removed: [SYM…], updated_at, by} — 🚫 his own "not eligible at
                    the broker" list (2026-10-17, DECISIONS12 D1); written ONLY by set_broker_flag (the owner's POST /
                    DELETE through the api). A TAG, never a filter: nothing in the pass reads it to gate a name.
  gajjala_potentials _id "{date}|{SYM}|{setup}"  🧠 the potential tracker (2026-10-15) — first sighting + path    none
                    the push claim records the trigger / stop / price the push carried (`push.trigger/stop/px`,
                    2026-10-16) — the 🏁 ledger's plan
  gajjala_ledger    _id "{date}|{SYM}|{setup}|{kind}"  🏁 the Track record (2026-10-16) — graded nightly          none
  gajjala_replay    _id "REPLAY:{date}|{SYM}|{setup}"  ⏪ replayed A+ rows (2026-10-16 night, DECISIONS11 D4) —
                    written ONLY by scripts/gajjala_replay.py --write (pre-graded; the nightly never re-grades)   none

🧠 gajjala_potentials (Ajay 2026-10-15: "In all the sub tab and add a track and alert to show me new potential is
added everyday." / "Give me an alert all continous tracker on these specifically when I get alert I will jump on to
ride the wave"). Written ONLY by potential.track() inside the 5-minute pass, KEPT (the study's data spine, the
`gajjala_alerts` / `gajjala_halts` ledger pattern — HIS CALL P7). Every write here is an `update_one`: track() makes one
upsert with DISJOINT `$setOnInsert` / `$set` key sets and never names `push` / `held` / `graveyard_on`; the claim, the
hold and the graveyard mark are guarded updates (`push` / `graveyard_on` absent), and the settle is a dotted `$set` of
`push.*` only — so two overlapping passes can never wipe a claim. No whole-doc replace on this collection.

🔄 The split lease (Ajay 2026-10-15: "When ever I open Gajjala's intiate a new scan of stocks.  In that moment and if
there are any enterable stocks on the top which I see in potential i guess" — DECISIONS5 C1, AMENDMENTS5 A5–A10). ONE
atomic `find_one_and_update` + upsert collision on `_id "lease"` (the medical lease's primitive, not its function): the
min gap counts CRON starts only (`last_cron_started_at`), an on-open claim needs only "not held" and never writes
`started_at` (the baked old image gaps against it — A9), a cron may take over an on-open holder (run._claim waits for it
first), releases carry the holder's token (a holder that was taken over releases nothing), and every stamp read back
from Mongo goes through `_utc` (the live client is not tz-aware — A5). The cron's pass doc moves "latest" AND
"latest_cron"; an on-open pass doc moves "latest" only, never backwards in time (A10).

Every handle is injectable (`GajjalaStore(colls={...})`) — the tests pass in-memory stand-ins and tests/conftest.py
refuses a real MongoClient. Module-level functions delegate to one default store, so callers may hand either the
module or an instance to `scanner.listed_symbols(store, session)`. Every write soft-fails (logged, never raised): a
storage hiccup must not kill the pass, and a read of a missing handle is the documented "no data" answer.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

from . import constants as GC

log = logging.getLogger("chart_maps.gajjala.store")

SCAN = "gajjala_scan"
AH_CARRY = "gajjala_ah_carry"
POST = "gajjala_post"
PASSES = "gajjala_passes"
READS = "gajjala_reads"
ALERTS = "gajjala_alerts"
HALTS = "gajjala_halts"
DAILY = "gajjala_daily"
STATE = "gajjala_state"
POTENTIALS = "gajjala_potentials"            # 🧠 the potential tracker (2026-10-15) — kept, no TTL
LEDGER = "gajjala_ledger"                      # 🏁 the Track record (2026-10-16) — one doc per rung alert; kept, no TTL
REPLAY = "gajjala_replay"                      # ⏪ (2026-10-16, DECISIONS11 D4) — written ONLY by scripts/gajjala_replay.py --write; kept, no TTL
JOINED_MODE = "joined"                         # D9: potential.FIRST_SEEN_MODES[1] — never claimable (2026-10-15)
ALL = (SCAN, AH_CARRY, POST, PASSES, READS, ALERTS, HALTS, DAILY, STATE, POTENTIALS, LEDGER, REPLAY)
# 🏁 the only top-level keys a ledger write may carry (upsert_ledger refuses any other — BUILD_SPEC9 §3.2)
LEDGER_KEYS = frozenset({"date", "symbol", "setup", "kind", "line", "alert", "same", "next", "graded_at", "version"})
LEDGER_ALERT_STATES = ("shadow", "pushed")     # the A+ rows the ledger reads (ledger.alert_of filters the ids)
# ⏪ the only top-level keys a replay doc may carry besides `_id` (upsert_replay refuses any other — BUILD_SPEC11 §3.12)
REPLAY_KEYS = frozenset({"date", "symbol", "setup", "kind", "state", "alert", "same", "next", "bars5", "universe",
                         "float_gate", "detectors_sha", "detectors_sha256", "replayed_at", "caveats"})
# retention per collection (None = kept): the TTL index reads `at`
TTL_DAYS = {SCAN: GC.LEDGER_TTL_DAYS, AH_CARRY: GC.LEDGER_TTL_DAYS, POST: GC.LEDGER_TTL_DAYS,
            PASSES: GC.LEDGER_TTL_DAYS, DAILY: GC.LEDGER_TTL_DAYS, READS: GC.READS_TTL_DAYS}
_DAY_SEC = 86400
# 🔄 the split lease (2026-10-15) — strings, not numbers
LEASE_ID = "lease"
LEASE_CRON = "cron"
LEASE_ON_DEMAND = "on_demand"
LEASE_SOURCES = (LEASE_CRON, LEASE_ON_DEMAND)
LEASE_WHYS = ("claimed", "taken_over", "no_store", "held", "held_on_demand", "gap", "error")
ON_DEMAND_PASS_SUFFIX = "open"                 # the on-open pass doc id "{date}|{HH:MM:SS}|open" (DECISIONS5 C5)
LATEST_ID = "latest"
LATEST_CRON_ID = "latest_cron"                 # AMENDMENTS5 A10: the cron-only pointer (stale + the 🎯 gate read it)
POINTERS = (LATEST_ID, LATEST_CRON_ID)
# 🚫 his own broker list (2026-10-17, DECISIONS12 D1) — one gajjala_state doc, no new collection (ALL does not move)
BROKER_STATE_ID = "broker_flags"   # gajjala_state doc (DECISIONS12 D1): {added: [SYM…], removed: [SYM…], updated_at, by}; no new collection
# AMENDMENTS12 F2: the read + the $set of set_broker_flag run under ONE lock (one uvicorn worker) — two edits in flight
# never drop a name
_BROKER_LOCK = threading.Lock()


def _coll(name: str):
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[name] if db is not None else None
    except Exception as exc:                                    # noqa: BLE001
        log.debug("gajjala.store: no mongo for %s: %s", name, exc)
        return None


def _iso(d) -> str:
    return d.isoformat() if isinstance(d, (date, datetime)) else str(d)


def _utc(now: Optional[datetime]) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    return now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)


def key(session, sym: str) -> str:
    """`"{date}|{SYM}"` — the per-session doc id."""
    return f"{_iso(session)}|{(sym or '').upper()}"


def potential_key(session, sym: str, setup: str) -> str:
    """`"{date}|{SYM}|{setup}"` — the 🧠 tracker doc id (one per session, symbol and setup — K3)."""
    return f"{key(session, sym)}|{setup}"


# ── 🚫 his broker list (2026-10-17, DECISIONS12 D1 / D5; AMENDMENTS12 F5 / F8) — pure helpers ──────────────────────
# Ajay 2026-10-17: "ok then avoid showing me names that are not eligible in Fidelity then." / "Or just add a tag that
# not eligible on Fidelity". A TAG, never a filter: these helpers read and shape the list; nothing gates on it.
def broker_symbol(raw) -> Optional[str]:
    """D5 — `raw` stripped + upper-cased when it matches ^[A-Z][A-Z0-9.\\-]{0,N}$, N = GC.BROKER_SYMBOL_MAX_LEN - 1 (built at
    CALL time); else None (non-str, "", "1ABC", "AB C", "AB$", too long, a Query object). The typed form is kept
    ("BRK.B" stays "BRK.B"); membership folds "." and "-" (broker_fold)."""
    if not isinstance(raw, str):
        return None
    s = raw.strip().upper()
    try:
        n = int(GC.BROKER_SYMBOL_MAX_LEN) - 1
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    return s if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,%d}" % n, s) else None


def broker_fold(sym) -> str:
    """AMENDMENTS12 F8 — "." and "-" are one ticker ("MOG.A" == "MOG-A"): the membership key on both sides."""
    return sym.strip().upper().replace(".", "-") if isinstance(sym, str) else ""


def _broker_list(v) -> list:
    """A stored list field → its valid symbols (broker_symbol), deduped by broker_fold, typed order kept. A junk field
    (not a list) → []."""
    out, seen = [], set()
    for x in v if isinstance(v, (list, tuple)) else ():
        s = broker_symbol(x)
        if s is not None and broker_fold(s) not in seen:
            seen.add(broker_fold(s))
            out.append(s)
    return out


def _broker_effective(seed: list, added: list, removed: list) -> tuple:
    """(seed ∪ added) − removed, folded on "." / "-", deduped, sorted."""
    gone = {broker_fold(s) for s in removed}
    out, seen = [], set()
    for s in list(seed) + list(added):
        k = broker_fold(s)
        if k not in gone and k not in seen:
            seen.add(k)
            out.append(s)
    return tuple(sorted(out))


def _broker_read(store) -> tuple:
    """(doc, fault) — the gajjala_state broker doc through the store's fault-aware `_find_or_none` (None = a READ
    FAULT, AMENDMENTS12 F5); a store without it falls back to `get_state` (its {} cannot tell a fault, so it reads as
    "no doc"). store None / no reader / a raise → ({}, True). Never raises, never writes."""
    if store is None:
        return {}, True
    fon = getattr(store, "_find_or_none", None)
    if callable(fon):
        try:
            docs = fon(STATE, {"_id": BROKER_STATE_ID})
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: broker list read failed: %s", exc)
            return {}, True
        if docs is None:
            return {}, True
        return next((d for d in docs if isinstance(d, dict)), None) or {}, False
    gs = getattr(store, "get_state", None)
    if not callable(gs):
        return {}, True
    try:
        doc = gs(BROKER_STATE_ID)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala.store: broker list read failed: %s", exc)
        return {}, True
    return (doc if isinstance(doc, dict) else {}), False


def broker_flags(store) -> tuple:
    """D1 / AMENDMENTS12 F5 — (symbols, fault): symbols = (GC.BROKER_FLAG_SEED ∪ added) − removed, upper-cased, deduped
    ("." / "-" folded), sorted, from the gajjala_state doc BROKER_STATE_ID. A read fault (store None, no reader, a
    raise, `_find_or_none` None) → (the seed alone, True): FAIL-OPEN TO THE SEED. A junk field or junk entries
    (failing broker_symbol) are dropped. Never raises, never writes, never calls default() itself."""
    seed = _broker_list(GC.BROKER_FLAG_SEED)
    doc, fault = _broker_read(store)
    if fault:
        return _broker_effective(seed, [], []), True
    return _broker_effective(seed, _broker_list(doc.get("added")), _broker_list(doc.get("removed"))), False


def broker_doc(store) -> dict:
    """D5 — {"seed": sorted seed, "added": sorted, "removed": sorted, "symbols": list(broker_flags(store) symbols),
    "fault": bool} (a read fault: added / removed [], symbols = the seed, fault True — SAID, never disguised; the
    editor block turns it into tab.BROKER_FAULT_TEXT, AMENDMENTS12 F5 / critic 2026-10-17)."""
    doc, fault = _broker_read(store)
    doc = {} if fault else doc
    seed = _broker_list(GC.BROKER_FLAG_SEED)
    added, removed = _broker_list(doc.get("added")), _broker_list(doc.get("removed"))
    return {"seed": sorted(seed), "added": sorted(added), "removed": sorted(removed),
            "symbols": list(_broker_effective(seed, added, removed)), "fault": bool(fault)}


# ── 🔄 the split lease (2026-10-15, DECISIONS5 C1 + AMENDMENTS5 A5–A9) — pure helpers ───────────────────────────────
@dataclass(frozen=True)
class LeaseClaim:
    """A claim verdict. Truthy only when the lease is now this caller's (`ok`). `why` ∈ LEASE_WHYS: "claimed" /
    "taken_over" (a cron replaced an on-open holder) / "no_store" (no Mongo handle — the documented "run anyway" answer)
    on success; "held" / "held_on_demand" (a cron met an on-open holder — run._claim waits) / "gap" (a cron inside
    LEASE_MIN_GAP_SEC of the last CRON start) / "error" (a store fault, or the holder released between the attempt and
    the classify read) on refusal. `token` = the new holder's uuid4 hex (release_lease / lease_owner_is take it);
    `held_by` = the holder when refused."""
    ok: bool
    why: str
    token: Optional[str] = None
    held_by: Optional[str] = None

    def __bool__(self) -> bool:
        return bool(self.ok)


def _stamp(v) -> Optional[datetime]:
    """A stamp read back from Mongo → UTC-aware (the live client is NOT tz-aware: naive = UTC, A5); not a datetime → None."""
    return _utc(v) if isinstance(v, datetime) else None


def lease_free(doc: Optional[dict], now: datetime) -> bool:
    """Nobody holds the lease: no doc, or `status` ≠ "running", or the holder claimed it ≥ LEASE_SEC ago (a crashed
    holder frees itself). The python twin of `lease_query`'s `free` clause."""
    if not isinstance(doc, dict) or doc.get("status") != "running":
        return True
    claimed = _stamp(doc.get("claimed_at"))
    return claimed is not None and claimed <= _utc(now) - timedelta(seconds=GC.LEASE_SEC)


def lease_gap_ok(doc: Optional[dict], now: datetime) -> bool:
    """The last CRON start is ≥ LEASE_MIN_GAP_SEC ago (the duplicate-cron guard). The clock is `last_cron_started_at`
    when on file, else `started_at` (a legacy medical-shape doc — its started_at was always a cron start, and an on-open
    claim never writes started_at, A9), else none → True. The python twin of `lease_query`'s `gap` clause."""
    if not isinstance(doc, dict):
        return True
    cut = _utc(now) - timedelta(seconds=GC.LEASE_MIN_GAP_SEC)
    for k in ("last_cron_started_at", "started_at"):
        if k in doc:
            v = _stamp(doc.get(k))
            return v is not None and v <= cut
    return True


def lease_claimable(doc: Optional[dict], now: datetime, source: str, *, take_over: bool = False) -> bool:
    """What `lease_query(now, source, take_over=)` matches, in python (a test pins the two together on a doc table):
    on_demand = free (NO gap — C1); cron = (free, or with take_over an on-open holder) AND the gap."""
    if source == LEASE_ON_DEMAND:
        return lease_free(doc, now)
    holder_ok = lease_free(doc, now) or (take_over and isinstance(doc, dict) and doc.get("status") == "running"
                                         and doc.get("held_by") == LEASE_ON_DEMAND)
    return bool(holder_ok) and lease_gap_ok(doc, now)


def lease_query(now: datetime, source: str, *, take_over: bool = False) -> dict:
    """The claim's filter on `_id "lease"` — only $or / $and / $ne / $lte / $exists (the FakeColl has no $lt / $gt).
    on_demand → free only (C1: an open skips the cron gap); cron → holder AND gap, holder = free, or with `take_over`
    free OR running-and-held-by-on_demand."""
    now = _utc(now)
    free = {"$or": [{"status": {"$ne": "running"}},
                    {"claimed_at": {"$lte": now - timedelta(seconds=GC.LEASE_SEC)}}]}
    if source == LEASE_ON_DEMAND:
        return {"_id": LEASE_ID, "$and": [free]}
    cut = now - timedelta(seconds=GC.LEASE_MIN_GAP_SEC)
    gap = {"$or": [{"last_cron_started_at": {"$lte": cut}},
                   {"last_cron_started_at": {"$exists": False}, "started_at": {"$lte": cut}},
                   {"last_cron_started_at": {"$exists": False}, "started_at": {"$exists": False}}]}
    holder = free if not take_over else {"$or": [free, {"status": "running", "held_by": LEASE_ON_DEMAND}]}
    return {"_id": LEASE_ID, "$and": [holder, gap]}


class GajjalaStore:
    """The twelve collections behind one object. `colls` = {name: collection}; a name not given resolves to Mongo."""

    def __init__(self, colls: Optional[dict] = None):
        self._injected = dict(colls or {})
        self._cache: dict = {}

    def coll(self, name: str):
        if name in self._injected:
            return self._injected[name]
        if name not in self._cache:
            self._cache[name] = _coll(name)
        return self._cache[name]

    # ── indexes ────────────────────────────────────────────────────────────────────────────────────────────────
    def ensure_indexes(self) -> None:
        """Idempotent: TTL on `at` where the spec keeps a retention, plus the read paths' keys."""
        for name in ALL:
            c = self.coll(name)
            if c is None:
                continue
            try:
                days = TTL_DAYS.get(name)
                if days:
                    c.create_index([("at", 1)], expireAfterSeconds=int(days * _DAY_SEC))
                if name in (SCAN, POST, READS, HALTS, DAILY, POTENTIALS, LEDGER, REPLAY):
                    c.create_index([("date", 1), ("symbol", 1)])
                    c.create_index([("symbol", 1), ("date", -1)])
                if name == ALERTS:
                    c.create_index([("claimed_at", -1)])
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala.store: index build failed on %s: %s", name, exc)

    # ── gajjala_scan ───────────────────────────────────────────────────────────────────────────────────────────
    def record_qualifiers(self, session, now: datetime, rows: Iterable[dict], tape_session: str) -> set:
        """Upsert today's qualifiers; returns the symbols seen for the FIRST time this session (the split check
        runs once per symbol per session on exactly these)."""
        c = self.coll(SCAN)
        rows = [r for r in rows or [] if r.get("symbol")]
        if c is None or not rows:
            return {r["symbol"] for r in rows} if c is None else set()
        now = _utc(now)
        ids = [key(session, r["symbol"]) for r in rows]
        try:
            have = {d["_id"] for d in c.find({"_id": {"$in": ids}}, {"_id": 1})}
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: scan read failed: %s", exc)
            have = set()
        new = set()
        for r, _id in zip(rows, ids):
            sym = r["symbol"]
            if _id not in have:
                new.add(sym)
            try:
                c.update_one({"_id": _id}, {
                    "$setOnInsert": {"date": _iso(session), "symbol": sym, "first_qualified_at": now},
                    "$set": {"last_qualified_at": now, "last": dict(r), "at": now,
                             f"sessions.{tape_session}": True},
                    "$inc": {"n_passes": 1},
                    "$max": {"max_change_pct": float(r.get("change_pct") or 0.0)}}, upsert=True)
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala.store: scan write failed for %s: %s", sym, exc)
        return new

    def set_split_check(self, session, sym: str, check: str, *, now: Optional[datetime] = None,
                        held: bool = False) -> None:
        """`check` ∈ "ok" | "held" | "failed"; a held name is excluded from every listed set."""
        c = self.coll(SCAN)
        if c is None:
            return
        try:
            c.update_one({"_id": key(session, sym)},
                         {"$set": {"split_check": check, "held": bool(held), "at": _utc(now),
                                   "date": _iso(session), "symbol": sym.upper()}}, upsert=True)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: split write failed for %s: %s", sym, exc)

    def split_checks(self, session) -> dict:
        """{SYM: split_check} already decided this session (so nobody re-fetches)."""
        return {d["symbol"]: d.get("split_check") for d in self._find(SCAN, {"date": _iso(session)})
                if d.get("split_check")}

    def scan_docs(self, sessions: Iterable) -> list:
        """Every NON-held qualifier doc of the given sessions."""
        days = [_iso(s) for s in sessions]
        return [d for d in self._find(SCAN, {"date": {"$in": days}}) if not d.get("held")]

    def qualified_symbols(self, session) -> set:
        return {d["symbol"] for d in self.scan_docs([session])}

    # ── gajjala_ah_carry ───────────────────────────────────────────────────────────────────────────────────────
    def replace_ah_carry(self, session, pass_at: datetime, rows: Iterable[dict]) -> None:
        """REPLACE the session's carry set wholesale — a name that fell back under the line at a later pass drops
        out, and the LAST after-hours pass that ran decides tomorrow's carry (spec C4)."""
        c = self.coll(AH_CARRY)
        if c is None:
            return
        names = {r["symbol"]: {"ah_move_pct": r.get("ah_move_pct"), "ah_last": r.get("price"),
                               "reg_close": r.get("day_c")} for r in rows or [] if r.get("symbol")}
        doc = {"_id": _iso(session), "date": _iso(session), "pass_at": _utc(pass_at), "at": _utc(pass_at),
               "names": names}
        try:
            c.replace_one({"_id": doc["_id"]}, doc, upsert=True)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: ah carry write failed: %s", exc)

    def ah_carry(self, session) -> Optional[dict]:
        return self._find_one(AH_CARRY, {"_id": _iso(session)})

    # ── gajjala_post ───────────────────────────────────────────────────────────────────────────────────────────
    def upsert_post(self, session, sym: str, fields: dict, *, now: Optional[datetime] = None) -> None:
        self._upsert(POST, key(session, sym), dict(fields, date=_iso(session), symbol=sym.upper(), at=_utc(now)))

    def post_docs(self, session) -> list:
        return self._find(POST, {"date": _iso(session)})

    # ── gajjala_passes ─────────────────────────────────────────────────────────────────────────────────────────
    def record_pass(self, session, now: datetime, doc: dict, *, hhmm: Optional[str] = None,
                    source: str = LEASE_CRON, latest_if_newer: bool = False, move_latest: bool = True) -> None:
        """One doc per pass `"{date}|{hhmm}"` (hhmm default = the ET minute; the on-open pass hands
        "HH:MM:SS|open", so it never overwrites the cron's minute doc — C5) plus the pointers (AMENDMENTS5 A10):
        "latest" (ANY pass — the board's as_of / "scanned on open" line) when `move_latest`, and "latest_cron" (CRON
        passes only — the stale line and the 🎯 gate read it, so opens can never hide a dead cron) when `source` is
        LEASE_CRON. `latest_if_newer` (the on-open path): the stored "latest" is NOT replaced when its `at` is newer
        than `now` (an on-open pass finishing after a newer cron pass never moves "latest" back; naive → UTC). The
        cron path keeps today's behaviour (always replaces)."""
        now = _utc(now)
        if hhmm is None:
            from zoneinfo import ZoneInfo
            hhmm = now.astimezone(ZoneInfo("America/New_York")).strftime("%H:%M")
        pass_id = f"{_iso(session)}|{hhmm}"
        body = dict(doc, date=_iso(session), at=now)
        self._replace(PASSES, pass_id, body)
        if move_latest:
            stored = self.latest_pass() if latest_if_newer else None
            at = _stamp((stored or {}).get("at"))
            if at is None or at <= now:
                self._replace(PASSES, LATEST_ID, dict(body, pass_id=pass_id))
        if source == LEASE_CRON:
            self._replace(PASSES, LATEST_CRON_ID, dict(body, pass_id=pass_id, pointer=LATEST_CRON_ID))

    def latest_pass(self) -> Optional[dict]:
        """CONTRACT: the "latest" pointer — the newest pass of ANY source (cron or on-open; `on_demand` in the body
        says which) — or None."""
        return self._find_one(PASSES, {"_id": LATEST_ID})

    def latest_cron_pass(self) -> Optional[dict]:
        """CONTRACT (AMENDMENTS5 A10 / A12): the "latest_cron" pointer — the newest CRON pass only (an on-open pass never
        moves it) — or None (none on file since the split, or a read fault). The stale line, the 🎯 banner's gate and
        "has the session's first 5-minute pass run" read this one."""
        return self._find_one(PASSES, {"_id": LATEST_CRON_ID})

    def passes(self, session) -> list:
        """The session's pass docs (cron and on-open), never a pointer."""
        return [d for d in self._find(PASSES, {"date": _iso(session)}) if d.get("_id") not in POINTERS]

    def recent_passes(self, session, since: datetime, until: datetime) -> Optional[list]:
        """The session's pass docs stamped `since` … `until` (both inclusive), projected to {at, potential} — the 🧠
        join rule's previous-pass read (potential._previous_pass_ran_gate), never the whole pass bodies. The "latest"
        pointer is excluded, and so is "latest_cron" (2026-10-15: its `pointer` field). None on a read fault or a
        missing handle ([] = none on file) — the caller fails closed. An on-open pass doc IS included: its potential
        block was computed dry and still carries `tracked_today` (DECISIONS5 C5)."""
        c = self.coll(PASSES)
        if c is None:
            return None
        q = {"date": _iso(session), "_id": {"$ne": LATEST_ID}, "pointer": {"$exists": False},
             "at": {"$gte": _utc(since), "$lte": _utc(until)}}
        try:
            return list(c.find(q, {"at": 1, "potential": 1}))
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: recent pass read failed: %s", exc)
            return None

    # ── gajjala_reads ──────────────────────────────────────────────────────────────────────────────────────────
    def upsert_read(self, session, sym: str, doc: dict, *, now: Optional[datetime] = None) -> None:
        now = _utc(now)
        self._replace(READS, key(session, sym),
                      dict(doc, date=_iso(session), symbol=sym.upper(), updated_at=now, at=now))

    def reads(self, session) -> list:
        return self._find(READS, {"date": _iso(session)})

    def get_read(self, session, sym: str) -> Optional[dict]:
        return self._find_one(READS, {"_id": key(session, sym)})

    # ── gajjala_halts ──────────────────────────────────────────────────────────────────────────────────────────
    def upsert_halt(self, session, sym: str, fields: dict) -> None:
        self._upsert(HALTS, key(session, sym), dict(fields, date=_iso(session), symbol=sym.upper()))

    def halts(self, session) -> list:
        return self._find(HALTS, {"date": _iso(session)})

    def halt_dates(self, sym: str) -> set:
        """Every session (ISO date) with a halt on file for `sym`."""
        return {d.get("date") for d in self._find(HALTS, {"symbol": (sym or "").upper()}) if d.get("date")}

    def halt_sessions(self) -> set:
        """Every session (ISO date) the halt ledger holds at least one row for (the nightly backfill's gap list)."""
        c = self.coll(HALTS)
        if c is None:
            return set()
        try:
            return {d for d in c.distinct("date") if d}
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: halt sessions read failed: %s", exc)
            return set()

    # ── gajjala_daily ──────────────────────────────────────────────────────────────────────────────────────────
    def get_daily(self, session, sym: str) -> Optional[dict]:
        return self._find_one(DAILY, {"_id": key(session, sym)})

    def upsert_daily(self, session, sym: str, fields: dict, *, now: Optional[datetime] = None) -> None:
        self._upsert(DAILY, key(session, sym), dict(fields, date=_iso(session), symbol=sym.upper(), at=_utc(now)))

    # ── gajjala_state ──────────────────────────────────────────────────────────────────────────────────────────
    def get_state(self, sid: str) -> dict:
        return self._find_one(STATE, {"_id": sid}) or {}

    def set_state(self, sid: str, fields: dict) -> None:
        self._upsert(STATE, sid, dict(fields))

    def set_broker_flag(self, sym: str, on: bool, *, by: str, now: Optional[datetime] = None) -> Optional[tuple]:
        """D5 — THE broker write (the owner's POST / DELETE only); `sym` must pass broker_symbol (else None, no write).
        Under _BROKER_LOCK (AMENDMENTS12 F2): a fault-aware read `_find_or_none(STATE, {"_id": BROKER_STATE_ID})` → None
        → None, NOTHING written. on: removed −= {sym}; sym ∉ seed → added ∪= {sym}. off: added −= {sym}; sym ∈ seed →
        removed ∪= {sym} (a seed is overridden without a deploy). "." / "-" fold on every comparison (F8). ONE
        `update_one({"_id": BROKER_STATE_ID}, {"$set": {added, removed (sorted lists), updated_at, by}}, upsert=True)`
        in its own try (a raise → None). -> the effective symbols (broker_flags' first item)."""
        s = broker_symbol(sym)
        if s is None:
            return None
        k = broker_fold(s)
        with _BROKER_LOCK:
            docs = self._find_or_none(STATE, {"_id": BROKER_STATE_ID})
            if docs is None:
                return None
            doc = next((d for d in docs if isinstance(d, dict)), None) or {}
            seed = _broker_list(GC.BROKER_FLAG_SEED)
            added, removed = _broker_list(doc.get("added")), _broker_list(doc.get("removed"))
            in_seed = k in {broker_fold(x) for x in seed}
            if on:
                removed = [x for x in removed if broker_fold(x) != k]
                if not in_seed and k not in {broker_fold(x) for x in added}:
                    added.append(s)
            else:
                added = [x for x in added if broker_fold(x) != k]
                if in_seed and k not in {broker_fold(x) for x in removed}:
                    removed.append(s)
            c = self.coll(STATE)
            if c is None:
                return None
            try:
                c.update_one({"_id": BROKER_STATE_ID},
                             {"$set": {"added": sorted(added), "removed": sorted(removed), "updated_at": _utc(now),
                                       "by": by if isinstance(by, str) else ""}}, upsert=True)
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala.store: broker list write failed: %s", exc)
                return None
        return _broker_effective(seed, added, removed)

    # ── 🔄 the split lease (2026-10-15; DECISIONS5 C1, AMENDMENTS5 A5–A9) ─────────────────────────────────────────
    def claim_lease(self, now: datetime, source: str = LEASE_CRON, *, take_over: bool = False,
                    cron_start: Optional[datetime] = None) -> LeaseClaim:
        """Claim the pass lease for `source` (LEASE_CRON | LEASE_ON_DEMAND) → LeaseClaim (truthy when held now).

        ONE `find_one_and_update(lease_query(...), $set, upsert=True)` — the medical lease's atomic primitive: a held
        lease makes the upsert collide on `_id` (DuplicateKeyError), then ONE read classifies the refusal (see
        LeaseClaim.why). A cron claim writes `started_at` and `last_cron_started_at` = `cron_start` (the TICK clock,
        before any wait — A6; default `now`); an on-open claim writes `od_started_at` and NEVER `started_at` /
        `last_cron_started_at` (A9: the old image gaps against started_at; C1: an open never moves the cron gap).
        `take_over=True` (cron only) also matches a lease an on-open pass holds → why "taken_over". Every stamp read
        back is UTC-normalised before a comparison (A5). No handle → LeaseClaim(True, "no_store"). Never raises."""
        c = self.coll(STATE)
        if c is None:
            return LeaseClaim(True, "no_store")
        now = _utc(now)
        source = source if source in LEASE_SOURCES else LEASE_CRON
        take_over = bool(take_over) and source == LEASE_CRON
        token = uuid.uuid4().hex
        sets = {"status": "running", "held_by": source, "token": token, "claimed_at": now, "pid": os.getpid()}
        if source == LEASE_CRON:
            start = _utc(cron_start) if isinstance(cron_start, datetime) else now
            sets.update({"started_at": start, "last_cron_started_at": start})
        else:
            sets["od_started_at"] = now
        try:
            from pymongo.errors import DuplicateKeyError
        except Exception:                                       # pragma: no cover
            DuplicateKeyError = KeyError                        # noqa: N806
        try:
            pre = c.find_one_and_update(lease_query(now, source, take_over=take_over), {"$set": sets}, upsert=True)
        except DuplicateKeyError:
            return self._classify_refusal(c, now, source)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: lease claim failed: %s", type(exc).__name__)
            return LeaseClaim(False, "error")
        try:
            # pymongo returns the PRE-image by default; a non-dict (the dry-run recorder) reads as "no prior holder"
            taken = (take_over and isinstance(pre, dict) and pre.get("status") == "running"
                     and pre.get("held_by") == LEASE_ON_DEMAND and not lease_free(pre, now))
        except Exception:                                       # noqa: BLE001
            taken = False
        return LeaseClaim(True, "taken_over" if taken else "claimed", token=token)

    def _classify_refusal(self, c, now: datetime, source: str) -> LeaseClaim:
        try:
            doc = c.find_one({"_id": LEASE_ID})
            if not isinstance(doc, dict):
                return LeaseClaim(False, "error")
            if not lease_free(doc, now):
                holder = doc.get("held_by") or LEASE_CRON
                if source == LEASE_CRON and holder == LEASE_ON_DEMAND:
                    why = "gap" if not lease_gap_ok(doc, now) else "held_on_demand"
                    return LeaseClaim(False, why, held_by=holder)
                return LeaseClaim(False, "held", held_by=holder)
            if source == LEASE_CRON and not lease_gap_ok(doc, now):
                return LeaseClaim(False, "gap", held_by=None)
            return LeaseClaim(False, "error")                   # freed between the attempt and this read (A7 retries)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: lease read failed: %s", type(exc).__name__)
            return LeaseClaim(False, "error")

    def release_lease(self, now: datetime, token: Optional[str] = None) -> bool:
        """Release the lease the caller holds: `update_one({_id: "lease", token: <token>}, $set status done)` — no
        upsert. A holder that was taken over releases NOTHING (its token no longer matches); a tokenless release only
        matches a tokenless (legacy) lease, never a tokened one. True when a doc matched. Never raises (False)."""
        c = self.coll(STATE)
        if c is None:
            return False
        q = {"_id": LEASE_ID, "token": token} if token else {"_id": LEASE_ID, "token": {"$exists": False}}
        try:
            res = c.update_one(q, {"$set": {"status": "done", "done_at": _utc(now)}})
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: lease release failed: %s", type(exc).__name__)
            return False
        return int(getattr(res, "matched_count", 0) or 0) > 0

    def lease_owner_is(self, token: Optional[str]) -> bool:
        """CONTRACT (AMENDMENTS5 A8, for run_pass's on-open tail): is `token` still the lease holder's? One cheap
        `find_one`. True when there is no handle, or no lease doc on file (nobody took it over — a dry store reads
        through and never lands the claim); False when the doc's token differs (a cron took the lease over) or the read
        FAILED (fail closed: an on-open pass stops writing rather than risk writing over the cron). Never raises."""
        c = self.coll(STATE)
        if c is None:
            return True
        try:
            doc = c.find_one({"_id": LEASE_ID})
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: lease owner read failed: %s", type(exc).__name__)
            return False
        if not isinstance(doc, dict):
            return True
        return bool(token) and doc.get("token") == token

    def lease_state(self, now: datetime) -> dict:
        """CONTRACT (for tab.py / on_demand.py, 2026-10-15): the lease as the board and the trigger see it, Mongo read
        only. {} on no handle or a read fault. Else {"held": bool (not lease_free — a holder that claimed ≥ LEASE_SEC
        ago is NOT held), "held_by": "cron" | "on_demand" | None (a running legacy doc with no held_by reads "cron"),
        "claimed_at", "started_at" (the last CRON start), "od_started_at" (the last on-open start),
        "last_cron_started_at", "holder_started_at" (the holder's own start: od_started_at for an on-open holder, else
        started_at; None when not held), "status" (the doc's status), "done_at" (the last release — on_demand.request's
        reuse check reads an on-open release that moved `latest` nowhere, final critic 2026-10-16)} — every stamp UTC-aware (naive Mongo stamps normalised, A5) or None."""
        c = self.coll(STATE)
        if c is None:
            return {}
        try:
            doc = c.find_one({"_id": LEASE_ID})
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: lease state read failed: %s", type(exc).__name__)
            return {}
        doc = doc if isinstance(doc, dict) else {}
        held = not lease_free(doc or None, now)
        held_by = doc.get("held_by") or (LEASE_CRON if doc.get("status") == "running" else None)
        stamps = {k: _stamp(doc.get(k)) for k in ("claimed_at", "started_at", "od_started_at", "last_cron_started_at")}
        own = None
        if held:
            own = stamps["od_started_at"] if held_by == LEASE_ON_DEMAND else stamps["started_at"]
            own = own or stamps["claimed_at"]
        return dict({"held": held, "held_by": held_by, "holder_started_at": own, "status": doc.get("status"),
                     "done_at": _stamp(doc.get("done_at"))}, **stamps)

    def types_map(self) -> dict:
        """The instrument-type reference doc {as_of, types{SYM: type}, complete, ...} or {}."""
        return self.get_state("types")

    def set_types_map(self, doc: dict) -> None:
        c = self.coll(STATE)
        if c is None:
            return
        try:
            c.replace_one({"_id": "types"}, dict(doc, _id="types"), upsert=True)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: types write failed: %s", exc)

    # ── gajjala_alerts (WP4 claims through demand_alerts.claim_key on this handle) ─────────────────────────────
    def alerts_coll(self):
        return self.coll(ALERTS)

    # ── gajjala_potentials (🧠 the tracker, 2026-10-15 — written ONLY by potential.track / run_pass) ─────────────
    def potentials(self, session) -> Optional[list]:
        """Every tracker doc of the session (`date` = the ET session) — None on a READ FAULT (no handle, or the find
        raised), [] only when nothing is on file. An unreadable tracker is never an empty one: read as [], the gate saw
        every joined doc (D9) as a first sighting, would have rung them all in one burst and replaced their timelines
        (final critic 2026-10-15). potential.run_pass skips the gate on None; count_potentials and tab.py soften it."""
        c = self.coll(POTENTIALS)
        if c is None:
            return None
        try:
            return list(c.find({"date": _iso(session)}))
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: read failed on %s: %s", POTENTIALS, exc)
            return None

    def get_potential(self, session, sym: str, setup: str) -> Optional[dict]:
        return self._find_one(POTENTIALS, {"_id": potential_key(session, sym, setup)})

    def potential_docs_for_symbol(self, sym: str) -> list:
        """Every tracker doc of `sym`, any session (the graveyard mark reads them)."""
        return self._find(POTENTIALS, {"symbol": (sym or "").upper()})

    def count_potentials(self, session) -> int:
        """Tracker docs of the session (len of a find — the FakeColl has no count_documents). 0 on any failure."""
        docs = self.potentials(session)
        return len(docs) if docs is not None else 0

    def upsert_potential(self, _id: str, insert_fields: dict, set_fields: dict) -> bool:
        """THE track write: one upsert, `$setOnInsert` (identity + first_*) and `$set` (last / path / prices) — two
        disjoint key sets (Mongo refuses a path in both). Never names push / held / graveyard_on. False on failure."""
        c = self.coll(POTENTIALS)
        if c is None:
            return False
        clash = set(insert_fields or {}) & set(set_fields or {})
        banned = {"push", "held", "graveyard_on"} & (set(insert_fields or {}) | set(set_fields or {}))
        if clash or banned:
            log.warning("gajjala.store: refused potential write %s (clash %s, banned %s)", _id, clash, banned)
            return False
        upd = {}
        if insert_fields:
            upd["$setOnInsert"] = dict(insert_fields)
        if set_fields:
            upd["$set"] = dict(set_fields)
        if not upd:
            return False
        try:
            c.update_one({"_id": _id}, upd, upsert=True)
            return True
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: potential write failed for %s: %s", _id, exc)
            return False

    def hold_potential(self, _id: str, held: list) -> bool:
        """`held` lands only on a doc that was never claimed (`push` absent). True when a doc matched."""
        return self._guarded_set(_id, {"push": {"$exists": False}}, {"held": list(held or [])}) == "matched"

    def claim_potential_push(self, _id: str, fields: dict) -> str:
        """The once-per-(date, symbol, setup) claim: `push` set only where it is absent AND the doc was not first seen
        by a join pass (`first_seen_mode` ≠ JOINED_MODE — absent on a pre-build doc matches; the second guard of D9,
        final critic 2026-10-15: the gate's own check is the first).
        -> "claimed" (this pass owns the send) | "taken" (no claimable doc matched) | "error" (store fault)."""
        res = self._guarded_set(_id, {"push": {"$exists": False}, "first_seen_mode": {"$ne": JOINED_MODE}},
                                {"push": dict(fields or {})})
        return {"matched": "claimed", "unmatched": "taken"}.get(res, "error")

    def settle_potential_push(self, _id: str, fields: dict) -> bool:
        """The send's outcome: a dotted `$set` of push.state / push.result / push.at_et ONLY — never a whole `push`."""
        sets = {f"push.{k}": v for k, v in (fields or {}).items() if k in ("state", "result", "at_et")}
        if not sets:
            return False
        return self._guarded_set(_id, {"push": {"$exists": True}}, sets) == "matched"

    def mark_potential_graveyard(self, _id: str, day, state_path: list) -> bool:
        """`graveyard_on` + the path entry, once (guarded on `graveyard_on` absent). True when a doc matched."""
        return self._guarded_set(_id, {"graveyard_on": {"$exists": False}},
                                 {"graveyard_on": _iso(day), "state_path": list(state_path or [])}) == "matched"

    def _guarded_set(self, _id: str, guard: dict, sets: dict) -> str:
        """"matched" | "unmatched" | "error" — an `update_one({_id, **guard}, {$set})`, never an upsert."""
        c = self.coll(POTENTIALS)
        if c is None:
            return "error"
        try:
            res = c.update_one(dict({"_id": _id}, **guard), {"$set": sets})
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: guarded potential update failed for %s: %s", _id, exc)
            return "error"
        return "matched" if int(getattr(res, "matched_count", 0) or 0) > 0 else "unmatched"

    # ── 🏁 gajjala_ledger (the Track record, 2026-10-16 — written ONLY by ledger.grade_step, the nightly) ───────────
    def _find_or_none(self, name: str, q: dict) -> Optional[list]:
        """A find that tells a READ FAULT (None — no handle, or the find raised) from "nothing on file" ([])."""
        c = self.coll(name)
        if c is None:
            return None
        try:
            return list(c.find(q))
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: read failed on %s: %s", name, exc)
            return None

    def potential_pushes(self, sessions: Iterable) -> Optional[list]:
        """🏁 Every 🧠 tracker doc of these ET sessions whose push RANG (`push.state` "pushed") — the ledger's live rows.
        None on a read fault / no handle ([] = none on file)."""
        days = [_iso(s) for s in sessions or []]
        return self._find_or_none(POTENTIALS, {"date": {"$in": days}, "push.state": "pushed"})

    def alert_rows(self, sessions: Iterable) -> Optional[list]:
        """🏁 Every A+ ledger doc of these sessions in state shadow / pushed (ledger.alert_of keeps the SHADOW: claims
        and the live claims, never a `#state` refusal). None on a read fault / no handle."""
        days = [_iso(s) for s in sessions or []]
        return self._find_or_none(ALERTS, {"date": {"$in": days}, "state": {"$in": list(LEDGER_ALERT_STATES)}})

    def ledger_docs(self, sessions: Iterable) -> Optional[list]:
        """🏁 The graded ledger docs of these sessions. None on a read fault / no handle."""
        days = [_iso(s) for s in sessions or []]
        return self._find_or_none(LEDGER, {"date": {"$in": days}})

    def ledger_dates(self) -> Optional[list]:
        """🏁 Every session (ISO date) the ledger holds a graded doc for, sorted. None on a read fault / no handle."""
        c = self.coll(LEDGER)
        if c is None:
            return None
        try:
            return sorted({d for d in c.distinct("date") if d})
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: ledger dates read failed: %s", exc)
            return None

    def alert_dates(self) -> Optional[list]:
        """🏁 AMENDMENTS9 E7 — the distinct alert dates of the rows themselves (pushed 🧠 potentials ∪ A+ shadow / live
        claims), sorted: the "all" span reads these, never the ledger's own dates alone (a night that failed must not
        hide a day). None on a read fault on either collection."""
        pot = self._find_or_none(POTENTIALS, {"push.state": "pushed"})
        al = self._find_or_none(ALERTS, {"state": {"$in": list(LEDGER_ALERT_STATES)}})
        if pot is None or al is None:
            return None
        return sorted({d.get("date") for d in pot + al if isinstance(d, dict) and isinstance(d.get("date"), str)
                       and d.get("date")})

    def upsert_ledger(self, _id: str, sets: dict) -> bool:
        """THE ledger write: one `update_one({_id}, {$set: sets}, upsert=True)` on gajjala_ledger — refused (logged,
        False) when a top-level key falls outside LEDGER_KEYS; never touches another collection. False on a fault."""
        bad = set(sets or {}) - LEDGER_KEYS
        if not sets or bad or not isinstance(_id, str) or not _id:
            log.warning("gajjala.store: refused ledger write %s (keys outside LEDGER_KEYS: %s)", _id, sorted(bad))
            return False
        c = self.coll(LEDGER)
        if c is None:
            return False
        try:
            c.update_one({"_id": _id}, {"$set": dict(sets)}, upsert=True)
            return True
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: ledger write failed for %s: %s", _id, exc)
            return False

    # ── ⏪ gajjala_replay (2026-10-16 night, DECISIONS11 D4 / D5 — written ONLY by scripts/gajjala_replay.py --write) ──
    def replay_rows(self, sessions: Iterable) -> Optional[list]:
        """⏪ Every replay doc of these sessions in state "replayed" (ledger.REPLAY_STATE; ledger.alert_of checks the id).
        None on a read fault / no handle ([] = none on file)."""
        from . import ledger as LG
        days = [_iso(s) for s in sessions or []]
        return self._find_or_none(REPLAY, {"date": {"$in": days}, "state": LG.REPLAY_STATE})

    def replay_dates(self) -> Optional[list]:
        """⏪ Every session (ISO date) the replay collection holds a doc for, sorted. None on a read fault / no handle."""
        c = self.coll(REPLAY)
        if c is None:
            return None
        try:
            return sorted({d for d in c.distinct("date") if d})
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: replay dates read failed: %s", exc)
            return None

    def records_on(self, session) -> Optional[int]:
        """⏪ How many records the session already has: its gajjala_alerts + gajjala_scan docs (len of a find — the
        FakeColl has no count_documents). The replay script refuses a session with any (DECISIONS11 D4). None when
        either read faults (an unreadable record is never "no record")."""
        q = {"date": _iso(session)}
        al = self._find_or_none(ALERTS, q)
        sc = self._find_or_none(SCAN, q)
        if al is None or sc is None:
            return None
        return len(al) + len(sc)

    def upsert_replay(self, doc: dict) -> bool:
        """THE replay write: one `replace_one({_id}, doc, upsert=True)` on gajjala_replay ONLY — refused (logged, False)
        unless `_id` starts ledger.REPLAY_ID_PREFIX ("REPLAY:") and every other top-level key is in REPLAY_KEYS (a
        re-run replaces: idempotent). False on a refusal / fault / no handle."""
        from . import ledger as LG
        _id = doc.get("_id") if isinstance(doc, dict) else None
        bad = (set(doc) - {"_id"} - REPLAY_KEYS) if isinstance(doc, dict) else set()
        if not isinstance(_id, str) or not _id.startswith(LG.REPLAY_ID_PREFIX) or bad:
            log.warning("gajjala.store: refused replay write %s (keys outside REPLAY_KEYS: %s)", _id, sorted(bad))
            return False
        c = self.coll(REPLAY)
        if c is None:
            return False
        try:
            c.replace_one({"_id": _id}, dict(doc), upsert=True)
            return True
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: replay write failed for %s: %s", _id, exc)
            return False

    # ── plumbing ───────────────────────────────────────────────────────────────────────────────────────────────
    def _find(self, name: str, q: dict) -> list:
        c = self.coll(name)
        if c is None:
            return []
        try:
            return list(c.find(q))
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: read failed on %s: %s", name, exc)
            return []

    def _find_one(self, name: str, q: dict) -> Optional[dict]:
        c = self.coll(name)
        if c is None:
            return None
        try:
            return c.find_one(q)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: read failed on %s: %s", name, exc)
            return None

    def _upsert(self, name: str, _id: str, fields: dict) -> None:
        c = self.coll(name)
        if c is None:
            return
        try:
            c.update_one({"_id": _id}, {"$set": fields}, upsert=True)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: write failed on %s: %s", name, exc)

    def _replace(self, name: str, _id: str, doc: dict) -> None:
        c = self.coll(name)
        if c is None:
            return
        try:
            c.replace_one({"_id": _id}, dict(doc, _id=_id), upsert=True)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala.store: write failed on %s: %s", name, exc)


# ── module-level API: one default store (real Mongo), so `store.ah_carry(d)` works as the spec names it ──────────
_DEFAULT: Optional[GajjalaStore] = None


def default() -> GajjalaStore:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = GajjalaStore()
    return _DEFAULT


def _delegate(name: str):
    def fn(*a, **k):
        return getattr(default(), name)(*a, **k)
    fn.__name__ = name
    fn.__doc__ = getattr(GajjalaStore, name).__doc__
    return fn


for _name in ("ensure_indexes", "record_qualifiers", "set_split_check", "split_checks", "scan_docs",
              "qualified_symbols", "replace_ah_carry", "ah_carry", "upsert_post", "post_docs", "record_pass",
              "latest_pass", "latest_cron_pass", "passes", "recent_passes", "lease_state", "lease_owner_is", "upsert_read", "reads", "get_read", "upsert_halt", "halts", "halt_dates",
              "halt_sessions", "get_daily", "upsert_daily", "get_state", "set_state", "claim_lease",
              "release_lease", "types_map", "set_types_map", "alerts_coll", "coll", "potentials", "get_potential",
              "potential_docs_for_symbol", "count_potentials", "upsert_potential", "hold_potential",
              "claim_potential_push", "settle_potential_push", "mark_potential_graveyard", "potential_pushes",
              "alert_rows", "ledger_docs", "ledger_dates", "alert_dates", "upsert_ledger", "replay_rows",
              "replay_dates", "records_on", "upsert_replay", "set_broker_flag"):
    globals()[_name] = _delegate(_name)
del _name
