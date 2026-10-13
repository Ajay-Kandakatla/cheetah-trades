"""Gajjala's tab — Mongo storage (spec §3.1.6). Written ONLY by the cron pass / nightly; the endpoint reads.

Collections
  gajjala_scan      _id "{date}|{SYM}"         every scanner qualifier of a session (+ split check)        TTL 30 d on `at`
  gajjala_ah_carry  _id "{date}"               the session's after-hours carry set — REPLACED per AH pass  TTL 30 d
  gajjala_post      _id "{date}|{SYM}"         🌙 K10 confirmations                                         TTL 30 d
  gajjala_passes    _id "{date}|{HH:MM}" + "latest"   one doc per pass (counts, strip, snapshot meta)      TTL 30 d
  gajjala_reads     _id "{date}|{SYM}"         detector reads + tile bars                                   TTL 14 d
  gajjala_alerts    _id "GG:{date}|{SYM}|{setup}"   the push ledger (demand_alerts.claim_key docs)         none
  gajjala_halts     _id "{date}|{SYM}"         halts per session (live + 30-session backfill)              none
  gajjala_daily     _id "{date}|{SYM}"         squeeze history + the float read of the session             TTL 30 d
  gajjala_state     _id "lease" | "float_backoff" | "types"                                                 —

Every handle is injectable (`GajjalaStore(colls={...})`) — the tests pass in-memory stand-ins and tests/conftest.py
refuses a real MongoClient. Module-level functions delegate to one default store, so callers may hand either the
module or an instance to `scanner.listed_symbols(store, session)`. Every write soft-fails (logged, never raised): a
storage hiccup must not kill the pass, and a read of a missing handle is the documented "no data" answer.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
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
ALL = (SCAN, AH_CARRY, POST, PASSES, READS, ALERTS, HALTS, DAILY, STATE)
# retention per collection (None = kept): the TTL index reads `at`
TTL_DAYS = {SCAN: GC.LEDGER_TTL_DAYS, AH_CARRY: GC.LEDGER_TTL_DAYS, POST: GC.LEDGER_TTL_DAYS,
            PASSES: GC.LEDGER_TTL_DAYS, DAILY: GC.LEDGER_TTL_DAYS, READS: GC.READS_TTL_DAYS}
_DAY_SEC = 86400


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


class GajjalaStore:
    """The nine collections behind one object. `colls` = {name: collection}; a name not given resolves to Mongo."""

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
                if name in (SCAN, POST, READS, HALTS, DAILY):
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
    def record_pass(self, session, now: datetime, doc: dict, *, hhmm: Optional[str] = None) -> None:
        """One doc per pass plus the "latest" pointer (the board's as_of / stale line)."""
        now = _utc(now)
        if hhmm is None:
            from zoneinfo import ZoneInfo
            hhmm = now.astimezone(ZoneInfo("America/New_York")).strftime("%H:%M")
        body = dict(doc, date=_iso(session), at=now)
        self._replace(PASSES, f"{_iso(session)}|{hhmm}", body)
        self._replace(PASSES, "latest", dict(body, pass_id=f"{_iso(session)}|{hhmm}"))

    def latest_pass(self) -> Optional[dict]:
        return self._find_one(PASSES, {"_id": "latest"})

    def passes(self, session) -> list:
        return [d for d in self._find(PASSES, {"date": _iso(session)}) if d.get("_id") != "latest"]

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

    def claim_lease(self, now: datetime) -> bool:
        """The medical pass's lease, reused (not copied): free + started ≥ LEASE_MIN_GAP_SEC ago."""
        from catalysts.medical.store import claim_lease as _claim
        return _claim(self.coll(STATE), _utc(now), lease_sec=GC.LEASE_SEC,
                      min_gap_sec=GC.LEASE_MIN_GAP_SEC, pid=os.getpid())

    def release_lease(self, now: datetime) -> None:
        from catalysts.medical.store import release_lease as _release
        _release(self.coll(STATE), _utc(now))

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
              "latest_pass", "passes", "upsert_read", "reads", "get_read", "upsert_halt", "halts", "halt_dates",
              "halt_sessions", "get_daily", "upsert_daily", "get_state", "set_state", "claim_lease",
              "release_lease", "types_map", "set_types_map", "alerts_coll", "coll"):
    globals()[_name] = _delegate(_name)
del _name
