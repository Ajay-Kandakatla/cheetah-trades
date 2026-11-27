"""🩳 ON-ENTRY SOURCE CHECK — one check per (session, symbol) when a name enters 🚩 Gajjala's or 👀 Watch (2026-11-27).

THE ASK (Ajay 2026-11-27, verbatim)
  "Anytime something is in our Gajjalas we need to initiate a flow checking these values"

What this module is (spec sicheck rev 2 §3.2, package si-io):
  * `enqueue(symbols, session, source)` — called by the 🚩 pass (every listed name) and the 👀 minute loop (every Watch
    name). ONE skip read, then ONE atomic upsert per row not yet listing this source (the `_id` "<session>|<SYM>"
    dedupes per session), then — when a row is queued or running — ONE spawn claim on the lease doc (no second spawn inside
    EC_SPAWN_GAP_SEC, none while a child holds the lease) and ONE detached child (`ARGV_CHILD`).
  * `run_child()` — the detached child: ONE lease claim (an upsert; DuplicateKeyError = held), a `running` row left by a
    killed child is queued again, then THREE phases over the EXISTING share-basis steps (no step of its own):
      A. per name: `share_basis.is_due` → `share_basis.refresh_symbol`;
      B. ONE bulk second-float read (`share_basis.fetch_mfloats` in SB_MFLOAT_CHUNK chunks → `store_mfloats`);
      C. per name: `share_basis.widen_splits` (when `needs_window`), `share_basis.fts_split_step`, then the block
         through THE engine (`read.si_map`) → `source_check.audit_row` + the flag keys.
    Every row records what was re-read now, what was held and what failed (`steps`); `words(row)` says exactly that and
    always says Yahoo's float is not re-read (HIS CALL #13).

Mongo: only $or / $and / $ne / $lte / $exists / $in in a filter (the house FakeColl has no $lt / $gt / $gte) and
$set / $setOnInsert / $addToSet in an update. No http client of its own; no push / alert / lane module; never si_track.
Display only: no rule, gate, sort, push or lane reads a row. Not a signal. UNMEASURED.
Doc: docs/short_interest/entry_check_flow_2026_11_27.md.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional

from short_interest import basis_math as BM
from short_interest import sec_fts as SF
from short_interest import share_basis as SB

log = logging.getLogger("short_interest.entry_check")

# ───────────────────────────────────────────── constants (engineering, each derived by name; none a trading threshold)
EC_COLL = "si_entry_checks"
EC_VERSION = 1
EC_WHEN = "on"                                   # HIS CALL #14 — any other word: nothing queued, nothing spawned
EC_MODES = ("off", "on")
ST_QUEUED, ST_RUNNING, ST_DONE, ST_FAILED, ST_NO_RECORD = "queued", "running", "done", "failed", "no_record"
STATUSES = (ST_QUEUED, ST_RUNNING, ST_DONE, ST_FAILED, ST_NO_RECORD)
EC_LEASE_ID = "lease"
EC_LEASE_SEC = SB.SB_ERROR_RETRY_MIN * 60        # heartbeat lease
EC_SPAWN_GAP_SEC = EC_LEASE_SEC                  # by name: no second spawn inside one lease length
EC_MAX_PER_RUN = SB.SB_QUEUE_MAX
PROC_NAME = "si-entry-check"
SRC_GAJJALA = "gajjala"
SRC_WATCH = "watch"
SOURCE_WORDS = {SRC_GAJJALA: "🚩", SRC_WATCH: "👀"}
ARGV_CHILD = [sys.executable, "-m", "short_interest.entry_check", "--child"]     # FIXED argv, no variable args
STEP_KEYS = ("refresh", "mfloat", "widen", "split")
STEP_RAN, STEP_HELD, STEP_FAILED, STEP_OFF = "ran", "held", "failed", "off"
STEP_VALUES = (STEP_RAN, STEP_HELD, STEP_FAILED, STEP_OFF)
STEP_WORDS = {"refresh": "SEC share counts, filings and splits", "mfloat": "the second float",
              "widen": "splits back to the second float's date", "split": "the 6-K split-word search"}
REFRESH_SUBS = ("ref", "sec", "splits", "sec.fts")          # the subs of a refreshed doc whose fault fails `refresh`
TEXT_YAHOO = " Yahoo's float is not re-read by this check."
TEXT_DONE = "checked %s when it listed on %s"
TEXT_QUEUED = "queued %s when it listed on %s — not checked yet."
TEXT_FAILED = "check failed %s (%s) — the chip shows the last stored read."
GROUP_RAN = "re-read now: %s"
GROUP_HELD = "held from an earlier read: %s"
GROUP_FAILED = "failed, the earlier read stands: %s"
ERR_OLD_SESSION = "old_session"


# ───────────────────────────────────────────── small helpers (never raise)
def ec_on(mode=None) -> bool:
    """The switch: True only for the word "on" (EC_WHEN read at call time; any other word = off)."""
    m = EC_WHEN if mode is None else mode
    return m in EC_MODES and m == EC_MODES[1]


def _under_test() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _dup_error():
    try:
        from pymongo.errors import DuplicateKeyError
        return DuplicateKeyError
    except Exception:                                          # pragma: no cover — the house fake raises KeyError
        return KeyError


def _now(now=None) -> datetime:
    if isinstance(now, datetime):
        return now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _clock(now):
    """A fixed `now` (tests) or the wall clock at every call."""
    return (lambda: _now(now)) if isinstance(now, datetime) else (lambda: _now(None))


def _session(v) -> Optional[str]:
    return SF._day(v)


def _syms(symbols) -> list:
    """`share_basis._clean` (never a state id), minus anything that cannot sit in a row id."""
    return [s for s in SB._clean(symbols) if "|" not in s and not any(c.isspace() for c in s)]


def row_id(session: str, sym: str) -> str:
    return "%s|%s" % (session, sym)


def free(field: str, moment) -> dict:
    """{field absent, or field <= moment} — the only shape of a time test here ($or / $exists / $lte)."""
    return {"$or": [{field: {"$exists": False}}, {field: {"$lte": moment}}]}


def _default_db():
    return SB._default_db()


def _type(exc: BaseException) -> str:
    return SB._safe(type(exc).__name__)


# ───────────────────────────────────────────── enqueue (the two entry hooks call this)
def enqueue(symbols, session, source, *, db=None, now=None, spawn: Optional[Callable] = None) -> dict:
    """Queue each name once per (session, symbol); spawn ONE detached child when a row is queued. Never raises.
    -> {"new": names whose row this call created, "queued": rows this call wrote (created or a source added),
    "spawned": bool, "reason": None | "off" | "test" | "no_symbols" | "no_session" | "source" | "no_db" | "error"}."""
    out = {"new": [], "queued": 0, "spawned": False, "reason": None}
    try:
        if not ec_on():
            out["reason"] = "off"
            return out
        if spawn is None and _under_test():
            out["reason"] = "test"                             # BEFORE any read or write (the SB.kick guard)
            return out
        syms = _syms(symbols)
        s_iso = _session(session)
        if not syms:
            out["reason"] = "no_symbols"
            return out
        if s_iso is None:
            out["reason"] = "no_session"
            return out
        if source not in SOURCE_WORDS:
            out["reason"] = "source"
            return out
        d = db if db is not None else _default_db()
        if d is None:
            out["reason"] = "no_db"
            return out
        t = _now(now)
        coll = d[EC_COLL]
        ids = {row_id(s_iso, s): s for s in syms}
        # 1. the skip read: a row that already lists this source gets no write
        have: dict = {}
        for doc in coll.find({"_id": {"$in": list(ids)}}, {"sources": 1}):
            if isinstance(doc, dict) and doc.get("_id") in ids:
                srcs = doc.get("sources")
                have[doc["_id"]] = list(srcs) if isinstance(srcs, list) else []
        dup = _dup_error()
        for rid, sym in ids.items():
            if source in have.get(rid, []):
                continue
            upd = {"$setOnInsert": {"v": EC_VERSION, "session": s_iso, "symbol": sym, "status": ST_QUEUED,
                                    "queued_at": t, "at": t},
                   "$addToSet": {"sources": source}}
            # 2. ONE atomic upsert — never an insert-or-update branch; a DuplicateKeyError (two upserts racing on one
            #    `_id`) → that ONE update again, once
            try:
                try:
                    res = coll.update_one({"_id": rid}, upd, upsert=True)
                except dup:
                    res = coll.update_one({"_id": rid}, upd, upsert=True)
            except Exception as exc:                           # noqa: BLE001
                log.warning("entry check: %s queue write failed: %s", sym, _type(exc))
                continue
            out["queued"] += 1
            if getattr(res, "upserted_id", None) is not None:
                out["new"].append(sym)
        # 3. anything queued — or left `running` by a killed child (the child marks ALL its rows `running` up front) —
        #    this session? A live child holds the lease, so a `running` row of a live run spawns nothing (step 4).
        if coll.find_one({"session": s_iso, "status": {"$in": [ST_QUEUED, ST_RUNNING]}}, {"_id": 1}) is None:
            return out
        # 4. the spawn claim: free lease AND no spawn inside the gap
        gap = t - timedelta(seconds=EC_SPAWN_GAP_SEC)
        try:
            coll.find_one_and_update({"_id": EC_LEASE_ID, "$and": [free("until", t), free("spawned_at", gap)]},
                                     {"$set": {"spawned_at": t}}, upsert=True)
        except dup:
            return out                                         # a child holds the lease, or one was spawned inside the gap
        try:
            if spawn is None:
                from chart_maps.gajjala import run_1m as R1    # lazy: the one detached-spawn engine
                spawn = R1._popen
            spawn(list(ARGV_CHILD), PROC_NAME)
            out["spawned"] = True
        except Exception as exc:                               # noqa: BLE001
            log.warning("entry check: child could not start: %s", _type(exc))
            try:                                               # the gap is given back: the next call may spawn
                coll.update_one({"_id": EC_LEASE_ID}, {"$set": {"spawned_at": gap}})
            except Exception:                                  # noqa: BLE001
                pass
        return out
    except Exception as exc:                                   # noqa: BLE001
        log.warning("entry check: enqueue failed: %s", _type(exc))
        out["reason"] = "error"
        return out


# ───────────────────────────────────────────── the child
def _ensure_index(coll) -> None:
    """TTL GC.LEDGER_TTL_DAYS on `at` (the bar_close.ensure_index shape, best-effort). The lease doc has no `at`."""
    try:
        from chart_maps.gajjala import constants as GC             # lazy
        coll.create_index([("at", 1)], expireAfterSeconds=int(GC.LEDGER_TTL_DAYS) * 86400)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("entry check: index failed: %s", _type(exc))


def _default_steps() -> dict:
    from short_interest import read as SR                     # lazy

    def block(sym, d, today):
        return (SR.si_map([sym], d, today) or {}).get(sym)
    return {"refresh": SB.refresh_symbol, "fetch_mfloats": SB.fetch_mfloats, "store_mfloats": SB.store_mfloats,
            "widen": SB.widen_splits, "split": SB.fts_split_step, "block": block}


def _bad_subs(doc) -> list:
    """The REFRESH_SUBS of a refreshed doc that hold an `error` or are failed / blocked."""
    out = []
    if not isinstance(doc, dict):
        return out
    sec = doc.get("sec") if isinstance(doc.get("sec"), dict) else None
    for k in REFRESH_SUBS:
        sub = (sec or {}).get("fts") if k == "sec.fts" else doc.get(k)
        if isinstance(sub, dict) and (sub.get("error") or sub.get("status") in ("failed", "blocked")):
            out.append(k)
    return out


def _split_read_in(doc) -> bool:
    """A K-1 `sec.fts_split` written BY this refresh: read at the doc's own `checked_at`, good, no error."""
    if not isinstance(doc, dict):
        return False
    sec = doc.get("sec") if isinstance(doc.get("sec"), dict) else {}
    fs = sec.get("fts_split") if isinstance(sec.get("fts_split"), dict) else None
    return bool(fs and fs.get("status") in SF.FTS_GOOD and not fs.get("error") and fs.get("read_at")
                and fs.get("read_at") == doc.get("checked_at"))


def _split_by_refresh(doc) -> bool:
    """✂️ 2026-11-27 (critic finding, LOW) — phase A's refresh already ran the split-word step on the SAME listing:
    the refreshed doc's `sec.fts_split` is good, error-free and for the window `fts_split_step` would ask
    (`SB.split_since`). `fts_split_step` would refuse it (`_split_still`: a carried answer is older than the new
    `sec.read_at`) and spend one SEC listing GET to reach the same answer — so phase C does not ask. Window moved
    (phase B stored a newer second float), error, or no answer → False: the step runs as before. 2026-11-27 (critic
    LOW #2): the refresh must have READ the listing itself (`sec.read_at` == the doc's `checked_at`) — under an SEC
    403/429 stop it carries the held `sec` and its old split answer, which is not this refresh's read."""
    if not isinstance(doc, dict):
        return False
    sec = doc.get("sec") if isinstance(doc.get("sec"), dict) else {}
    fs = sec.get("fts_split") if isinstance(sec.get("fts_split"), dict) else None
    wide = SB.split_since(doc)
    read = SB._parse_ts(sec.get("read_at"))
    return bool(SB._split_good(fs) and not fs.get("error") and wide is not None
                and SB._day(fs.get("since")) == wide
                and read is not None and read == SB._parse_ts(doc.get("checked_at")))


def _flag_keys(block) -> list:
    b = block.get("basis") if isinstance(block, dict) else None
    fl = b.get("flags") if isinstance(b, dict) else None
    return [f["key"] for f in (fl if isinstance(fl, list) else [])
            if isinstance(f, dict) and isinstance(f.get("key"), str)]


def run_child(db=None, now=None, *, steps: Optional[dict] = None, sleep: Callable = time.sleep,
              clock: Callable = time.monotonic) -> dict:
    """The detached child (spec §3.2): claim → re-queue → phases A / B / C → release. Never raises.
    -> {"reason", "rows", "done", "failed", "no_record", "old", "stopped"}. `steps` = {name: callable} seams
    (refresh, fetch_mfloats, store_mfloats, widen, split, block); a name not given is share_basis's own. Under pytest
    with no `steps` nothing is read and no outside call is made."""
    out = {"reason": None, "rows": 0, "done": 0, "failed": 0, "no_record": 0, "old": 0, "stopped": False}
    if not ec_on():
        out["reason"] = "off"
        return out
    if steps is None and _under_test():
        out["reason"] = "test"
        return out
    try:
        d = db if db is not None else _default_db()
    except Exception:                                          # noqa: BLE001
        d = None
    if d is None:
        out["reason"] = "no_db"
        return out
    tick = _clock(now)
    seams = _default_steps()
    seams.update({k: v for k, v in (steps or {}).items() if callable(v)})
    token = uuid.uuid4().hex
    try:
        coll = d[EC_COLL]
        t = tick()
        lease = {"_id": EC_LEASE_ID}
        lease.update(free("until", t))
        coll.find_one_and_update(lease, {"$set": {"until": t + timedelta(seconds=EC_LEASE_SEC), "token": token,
                                                  "claimed_at": t}}, upsert=True)
    except _dup_error():
        out["reason"] = "lease held"
        return out
    except Exception as exc:                                   # noqa: BLE001
        log.warning("entry check: lease claim failed: %s", _type(exc))
        out["reason"] = "error"
        return out
    try:
        _run_claimed(d, coll, token, tick, seams, sleep, out)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("entry check: child failed: %s", _type(exc))
        out["reason"] = "error"
    finally:
        try:
            t = tick()
            coll.update_one({"_id": EC_LEASE_ID, "token": token},
                            {"$set": {"until": t, "spawned_at": t - timedelta(seconds=EC_SPAWN_GAP_SEC)}})
        except Exception as exc:                               # noqa: BLE001
            log.warning("entry check: lease release failed: %s", _type(exc))
    return out


class _TakenOver(Exception):
    pass


def _run_claimed(d, coll, token, tick, seams, sleep, out) -> None:
    _ensure_index(coll)
    t = tick()
    today = SF.et_day(t)
    mine: list = []
    for r in coll.find({"status": {"$in": [ST_QUEUED, ST_RUNNING]}}):
        if not isinstance(r, dict) or r.get("_id") == EC_LEASE_ID:
            continue
        sess, sym = _session(r.get("session")), r.get("symbol")
        if sess is None or not isinstance(sym, str) or not _syms([sym]):
            continue
        if today and sess < today:
            coll.update_one({"_id": r["_id"]}, {"$set": {"status": ST_FAILED, "error": ERR_OLD_SESSION,
                                                         "done_at": t, "at": t}})
            out["old"] += 1
            continue
        if r.get("status") == ST_RUNNING:                      # left by a killed child → runs again
            coll.update_one({"_id": r["_id"]}, {"$set": {"status": ST_QUEUED, "at": t}})
        mine.append(r)
    mine.sort(key=lambda r: (str(BM._ts_iso(r.get("queued_at")) or ""), str(r.get("_id"))))
    mine = mine[:EC_MAX_PER_RUN]
    out["rows"] = len(mine)
    if not mine:
        return

    def beat():
        b = tick()
        res = coll.update_one({"_id": EC_LEASE_ID, "token": token},
                              {"$set": {"until": b + timedelta(seconds=EC_LEASE_SEC)}})
        if getattr(res, "matched_count", 1) == 0:
            raise _TakenOver()

    rows = {r["_id"]: {"id": r["_id"], "sym": _syms([r["symbol"]])[0],
                       "sources": [s for s in (r.get("sources") or []) if s in SOURCE_WORDS],
                       "steps": {"refresh": None, "mfloat": None, "widen": None, "split": None, "failed_subs": []},
                       "live": True, "split_in_refresh": False} for r in mine}
    for x in rows.values():
        coll.update_one({"_id": x["id"]}, {"$set": {"status": ST_RUNNING, "started_at": t, "at": t}})

    def finish(x, status, error=None, result=None):
        e = tick()
        coll.update_one({"_id": x["id"]}, {"$set": {"status": status, "steps": x["steps"], "error": error,
                                                    "result": result, "done_at": e, "at": e}})
        x["live"] = False
        out[{ST_DONE: "done", ST_FAILED: "failed", ST_NO_RECORD: "no_record"}[status]] += 1

    try:
        syms = [x["sym"] for x in rows.values()]
        recs = SB._find_map(d[SB._SIC().SI_COLL], syms)
        docs = SB._find_map(d[SB.SB_COLL], syms)
        # A. per name: refresh when due
        for x in rows.values():
            rec = recs.get(x["sym"])
            if not SB._usable(rec):
                finish(x, ST_NO_RECORD)
                beat()
                continue
            try:
                if SB.is_due(docs.get(x["sym"]), rec, tick()):
                    got = seams["refresh"](x["sym"], d)
                    bad = _bad_subs(got)
                    ok = isinstance(got, dict) and "skipped" not in got
                    x["steps"]["refresh"] = STEP_RAN if ok and not bad else STEP_FAILED
                    x["steps"]["failed_subs"] = bad
                    x["split_in_refresh"] = ok and _split_read_in(got)
                else:
                    x["steps"]["refresh"] = STEP_HELD
            except Exception as exc:                           # noqa: BLE001
                finish(x, ST_FAILED, _type(exc))
            beat()
        # B. ONE bulk second-float read
        live = [x for x in rows.values() if x["live"]]
        if live:
            if not SB.mfloat_on():
                for x in live:
                    x["steps"]["mfloat"] = STEP_OFF
            else:
                docs = SB._find_map(d[SB.SB_COLL], [x["sym"] for x in live])
                t2 = tick()
                need = []
                for x in live:
                    doc = docs.get(x["sym"])
                    if not isinstance(doc, dict) or doc.get("checked_at") is None:
                        continue                               # no checked doc: no second-float step
                    if SB._mfloat_fresh(doc.get("mfloat"), t2):
                        x["steps"]["mfloat"] = STEP_HELD
                    else:
                        need.append(x)
                got: dict = {}
                step = int(SB.SB_MFLOAT_CHUNK)
                from short_interest import client as SIC           # lazy (the bulk pacing constant)
                for i in range(0, len(need), step):
                    if i:
                        sleep(SIC.SI_BULK_SLEEP_SEC)
                    chunk = [x["sym"] for x in need[i:i + step]]
                    try:
                        ans = seams["fetch_mfloats"](chunk) or {}
                    except Exception as exc:                   # noqa: BLE001
                        log.warning("entry check: second-float read failed: %s", _type(exc))
                        ans = {}
                    for s in chunk:
                        a = ans.get(s) if isinstance(ans, dict) else None
                        got[s] = a if isinstance(a, dict) else {"status": "failed", "error": SB.ERR_MALFORMED}
                    beat()
                if got:
                    try:
                        seams["store_mfloats"](d, got, tick())
                        stored = True
                    except Exception as exc:                   # noqa: BLE001
                        log.warning("entry check: second-float store failed: %s", _type(exc))
                        stored = False
                    for x in need:
                        good = stored and (got.get(x["sym"]) or {}).get("status") in SB.MFLOAT_GOOD
                        x["steps"]["mfloat"] = STEP_RAN if good else STEP_FAILED
        # C. per name: widen, the split-word read, then the block through THE engine
        from short_interest import source_check as SCK         # lazy
        today_d = date.fromisoformat(today) if today else None
        for x in rows.values():
            if not x["live"]:
                continue
            try:
                doc = SB._find_one(d[SB.SB_COLL], x["sym"])
                if isinstance(doc, dict) and SB.needs_window(doc):
                    w = seams["widen"](x["sym"], d)
                    ws = w.get("status") if isinstance(w, dict) else None
                    x["steps"]["widen"] = STEP_RAN if ws == "widened" else (STEP_FAILED if ws == "failed"
                                                                            else STEP_HELD)
                else:
                    x["steps"]["widen"] = STEP_HELD
                if x["steps"].get("refresh") == STEP_RAN and _split_by_refresh(doc):
                    sp = "held"                                # the refresh ran it on this listing — no 2nd GET
                else:
                    sp = seams["split"](x["sym"], d)
                if sp == "stored" or (x["split_in_refresh"] and sp not in ("failed", "off")):
                    x["steps"]["split"] = STEP_RAN
                elif sp == "failed":
                    x["steps"]["split"] = STEP_FAILED
                elif sp == "off":
                    x["steps"]["split"] = STEP_OFF
                else:
                    x["steps"]["split"] = STEP_HELD
                blk = seams["block"](x["sym"], d, today_d)
                bdoc = SB.load([x["sym"]], d).get(x["sym"])
                res = SCK.audit_row(blk, bdoc, groups=x["sources"])
                res["flags"] = _flag_keys(blk)
                finish(x, ST_DONE, None, res)
            except _TakenOver:
                raise
            except Exception as exc:                           # noqa: BLE001
                finish(x, ST_FAILED, _type(exc))
            beat()
    except _TakenOver:
        out["stopped"] = True                                  # rows stay `running`: the next claim re-queues them


# ───────────────────────────────────────────── the read API (si-pure and the audit call these lazily)
def load(symbols, session, db=None) -> dict:
    """{SYM: row} for this session — ONE `$in` find. {} on any failure. Never the lease doc."""
    try:
        s_iso = _session(session)
        syms = _syms(symbols)
        if s_iso is None or not syms:
            return {}
        d = db if db is not None else _default_db()
        if d is None:
            return {}
        ids = {row_id(s_iso, s): s for s in syms}
        out = {}
        for doc in d[EC_COLL].find({"_id": {"$in": list(ids)}}):
            if isinstance(doc, dict) and doc.get("_id") in ids and doc.get("session") == s_iso:
                out[ids[doc["_id"]]] = dict(doc)
        return out
    except Exception as exc:                                   # noqa: BLE001
        log.warning("entry check: load failed: %s", _type(exc))
        return {}


def entered(session, db=None, source=None, *, strict: bool = False) -> list:
    """The session's row symbols, sorted; `source` None = any, else only rows whose `sources` list it. [] on any
    failure — `strict=True` RAISES instead (the nightly audit names a read fault)."""
    try:
        s_iso = _session(session)
        if s_iso is None:
            return []
        d = db if db is not None else _default_db()
        if d is None:
            if strict:
                raise RuntimeError("no database")
            return []
        out = set()
        for doc in d[EC_COLL].find({"session": s_iso}, {"symbol": 1, "sources": 1, "session": 1}):
            if not isinstance(doc, dict) or doc.get("_id") == EC_LEASE_ID or doc.get("session") != s_iso:
                continue
            srcs = doc.get("sources") if isinstance(doc.get("sources"), list) else []
            if source is not None and source not in srcs:
                continue
            c = _syms([doc.get("symbol")]) if isinstance(doc.get("symbol"), str) else []
            if c:
                out.add(c[0])
        return sorted(out)
    except Exception as exc:                                   # noqa: BLE001
        if strict:
            raise
        log.warning("entry check: entered failed: %s", _type(exc))
        return []


# ───────────────────────────────────────────── the sentence (PURE)
def _src_words(row) -> str:
    srcs = row.get("sources") if isinstance(row.get("sources"), list) else []
    return " ".join(SOURCE_WORDS[k] for k in SOURCE_WORDS if k in srcs)


def _group(steps, value) -> list:
    return [STEP_WORDS[k] for k in STEP_KEYS if steps.get(k) == value]


def words(row) -> Optional[str]:
    """The one sentence for the 🩳 hover / panel (PURE; ET via basis_math._et), built from `steps`: a group with no
    step is left out, an `off` step is never named, and a `done` sentence always ends with TEXT_YAHOO. no_record /
    junk → None."""
    if not isinstance(row, dict):
        return None
    st = row.get("status")
    src = _src_words(row)
    if st == ST_DONE:
        when = BM._et(row.get("done_at")) or BM._et(row.get("at"))
        if when is None or not src:
            return None
        head = TEXT_DONE % (when, src)
        steps = row.get("steps")
        if not isinstance(steps, dict):
            return head + "." + TEXT_YAHOO
        parts = []
        ran, held, bad = _group(steps, STEP_RAN), _group(steps, STEP_HELD), _group(steps, STEP_FAILED)
        if ran:
            parts.append(GROUP_RAN % ", ".join(ran))
        if held:
            parts.append(GROUP_HELD % ", ".join(held))
        if bad:
            subs = steps.get("failed_subs")
            subs = [s for s in subs if isinstance(s, str) and s] if isinstance(subs, list) else []
            parts.append(GROUP_FAILED % ", ".join(bad) + (" (%s)" % ", ".join(subs) if subs else ""))
        if not parts:
            return head + "." + TEXT_YAHOO
        return head + " — " + "; ".join(parts) + "." + TEXT_YAHOO
    if st in (ST_QUEUED, ST_RUNNING):
        when = BM._et(row.get("queued_at")) or BM._et(row.get("at"))
        if when is None or not src:
            return None
        return TEXT_QUEUED % (when, src)
    if st == ST_FAILED:
        when = BM._et(row.get("done_at")) or BM._et(row.get("at"))
        if when is None:
            return None
        err = row.get("error") if isinstance(row.get("error"), str) and row.get("error") else "error"
        return TEXT_FAILED % (when, err)
    return None


# ───────────────────────────────────────────── CLI
def _show(rows) -> str:
    return json.dumps(rows, default=str, indent=1, sort_keys=True, ensure_ascii=False)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m short_interest.entry_check")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--child", action="store_true", help="run the detached child (claims the lease)")
    g.add_argument("--show", action="store_true", help="print rows, write nothing")
    g.add_argument("--enqueue", action="store_true", help="queue names (the owner's one-off)")
    p.add_argument("--session", help="YYYY-MM-DD (default: today ET)")
    p.add_argument("--symbols", help="comma list")
    p.add_argument("--source", choices=sorted(SOURCE_WORDS))
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if a.child:
        print(json.dumps(run_child(), sort_keys=True))
        return 0
    session = a.session or SF.et_day(datetime.now(timezone.utc))
    if a.enqueue:
        if not a.symbols or not a.source:
            print("--enqueue needs --symbols and --source")
            return 2
        print(json.dumps(enqueue(a.symbols.split(","), session, a.source), sort_keys=True))
        return 0
    d = _default_db()
    if d is None:
        print("no database")
        return 2
    if a.symbols:
        rows = load(a.symbols.split(","), session, d)
    else:
        rows = {}
        for doc in d[EC_COLL].find({"session": _session(session)}):
            if isinstance(doc, dict) and isinstance(doc.get("symbol"), str):
                rows[doc["symbol"]] = doc
    print(_show({s: dict(r, words=words(r)) for s, r in sorted(rows.items())}))
    return 0


if __name__ == "__main__":                                     # pragma: no cover
    sys.exit(main())
