"""🩳 on-entry source check — enqueue, the leased child, steps + words, the audit's 🚩 group (2026-11-27, spec sicheck
rev 2 §3.2 + §3.3, work package si-io).

Ajay 2026-11-27: "Anytime something is in our Gajjalas we need to initiate a flow checking these values".

Hermetic: the Mongo fake below refuses every operator outside §3.2 ($lt / $gt / $gte raise), every share-basis step is
an injected seam, the spawn is a spy. NEGATIVES are marked NEGATIVE.
"""
from __future__ import annotations

import ast
import copy
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pymongo.errors import DuplicateKeyError

import short_interest.entry_check as EC
import short_interest.share_basis as SB
import short_interest.source_audit as SA
from short_interest import client as SIC
from short_interest import source_check as SCK

BACKEND = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc)          # 10:00 ET Fri 11-27
NOW_ISO = "2026-11-27T15:00:00Z"
SESSION = "2026-11-27"
ALLOWED_FILTER_OPS = {"$or", "$and", "$ne", "$lte", "$exists", "$in"}
ALLOWED_UPDATE_OPS = {"$set", "$setOnInsert", "$addToSet"}


# ═════════════════════════════════════════════ the Mongo fake (refuses $lt / $gt / $gte and every other operator)
class Res:
    def __init__(self, matched=0, upserted_id=None):
        self.matched_count, self.upserted_id = matched, upserted_id


def _get(doc, path):
    cur = doc
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return False, None
        cur = cur[p]
    return True, cur


def _set(doc, path, v):
    parts = path.split(".")
    cur = doc
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = copy.deepcopy(v)


def match(doc, q) -> bool:
    for k, v in (q or {}).items():
        if k == "$or":
            if not any(match(doc, x) for x in v):
                return False
            continue
        if k == "$and":
            if not all(match(doc, x) for x in v):
                return False
            continue
        if k.startswith("$"):
            raise AssertionError("filter operator refused: " + k)
        present, val = _get(doc, k)
        if isinstance(v, dict) and any(kk.startswith("$") for kk in v):
            for op, arg in v.items():
                if op not in ALLOWED_FILTER_OPS:
                    raise AssertionError("filter operator refused: " + op)
                if op == "$exists":
                    ok = present == bool(arg)
                elif op == "$lte":
                    ok = present and val is not None and val <= arg
                elif op == "$ne":
                    ok = (not present) or val != arg
                else:                                           # $in
                    ok = present and (val in arg or (isinstance(val, list) and any(x in arg for x in val)))
                if not ok:
                    return False
        elif not (present and (val == v or (isinstance(val, list) and v in val))):
            return False
    return True


class Coll:
    def __init__(self, docs=()):
        self.docs = {d["_id"]: copy.deepcopy(d) for d in docs}
        self.ops: list = []
        self.indexes: list = []
        self.before_upsert = None                             # one-shot hook: (coll, q, upd) before an insert

    def _apply(self, doc, upd, inserting):
        for op, fields in upd.items():
            if op not in ALLOWED_UPDATE_OPS:
                raise AssertionError("update operator refused: " + op)
            for k, v in fields.items():
                if op == "$set" or (op == "$setOnInsert" and inserting):
                    _set(doc, k, v)
                elif op == "$addToSet":
                    lst = doc.setdefault(k, [])
                    if v not in lst:
                        lst.append(copy.deepcopy(v))

    def find(self, q=None, proj=None):
        self.ops.append(("find", copy.deepcopy(q)))
        return [copy.deepcopy(d) for d in list(self.docs.values()) if match(d, q or {})]

    def find_one(self, q=None, proj=None):
        self.ops.append(("find_one", copy.deepcopy(q)))
        return next((copy.deepcopy(d) for d in self.docs.values() if match(d, q or {})), None)

    def _upsert(self, q, upd):
        if self.before_upsert is not None:
            hook, self.before_upsert = self.before_upsert, None
            hook(self, q, upd)
        _id = q.get("_id")
        if _id in self.docs:
            raise DuplicateKeyError("E11000 duplicate key")
        new = {"_id": _id}
        self._apply(new, upd, True)
        self.docs[_id] = new
        return new

    def update_one(self, q, upd, upsert=False):
        self.ops.append(("update_one", copy.deepcopy(q), copy.deepcopy(upd)))
        for d in self.docs.values():
            if match(d, q):
                self._apply(d, upd, False)
                return Res(1)
        if upsert:
            self._upsert(q, upd)
            return Res(0, q.get("_id"))
        return Res(0)

    def find_one_and_update(self, q, upd, upsert=False):
        self.ops.append(("find_one_and_update", copy.deepcopy(q), copy.deepcopy(upd)))
        for d in self.docs.values():
            if match(d, q):
                pre = copy.deepcopy(d)
                self._apply(d, upd, False)
                return pre
        if upsert:
            self._upsert(q, upd)
        return None

    def create_index(self, keys, **kw):
        self.indexes.append((keys, kw))

    def writes(self):
        return [o for o in self.ops if o[0] in ("update_one", "find_one_and_update")]

    def reads(self):
        return [o for o in self.ops if o[0] in ("find", "find_one")]


class DB:
    def __init__(self, **colls):
        self.colls = dict(colls)

    def __getitem__(self, k):
        return self.colls.setdefault(k, Coll())


class Spawn:
    def __init__(self, exc=None):
        self.calls, self.exc = [], exc

    def __call__(self, argv, name):
        self.calls.append((list(argv), name))
        if self.exc:
            raise self.exc
        return object()


def ec(db):
    return db[EC.EC_COLL]


def rows(db):
    return {k: v for k, v in ec(db).docs.items() if k != EC.EC_LEASE_ID}


# ═════════════════════════════════════════════ enqueue [C5]
def test_one_row_per_session_and_symbol_and_the_child_is_spawned_once():
    db, sp = DB(), Spawn()
    got = EC.enqueue(["bdmd", "POM", "BDMD"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW, spawn=sp)
    assert got == {"new": ["BDMD", "POM"], "queued": 2, "spawned": True, "reason": None}
    r = rows(db)
    assert set(r) == {"2026-11-27|BDMD", "2026-11-27|POM"}
    assert r["2026-11-27|BDMD"] == {"_id": "2026-11-27|BDMD", "v": EC.EC_VERSION, "session": SESSION, "symbol": "BDMD",
                                    "status": EC.ST_QUEUED, "queued_at": NOW, "at": NOW, "sources": ["gajjala"]}
    assert sp.calls == [(EC.ARGV_CHILD, EC.PROC_NAME)]
    assert EC.ARGV_CHILD == [sys.executable, "-m", "short_interest.entry_check", "--child"]


def test_a_second_call_from_the_same_source_writes_nothing():
    db, sp = DB(), Spawn()
    EC.enqueue(["BDMD"], SESSION, EC.SRC_WATCH, db=db, now=NOW, spawn=sp)
    before = len(ec(db).writes())
    got = EC.enqueue(["BDMD"], SESSION, EC.SRC_WATCH, db=db, now=NOW + timedelta(minutes=1), spawn=sp)
    upserts = [o for o in ec(db).writes()[before:] if o[0] == "update_one"]
    assert upserts == [] and got["new"] == [] and got["queued"] == 0


def test_a_call_from_the_other_source_only_adds_the_source():
    db, sp = DB(), Spawn()
    EC.enqueue(["BDMD"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW, spawn=sp)
    got = EC.enqueue(["BDMD"], SESSION, EC.SRC_WATCH, db=db, now=NOW + timedelta(minutes=1), spawn=sp)
    r = rows(db)["2026-11-27|BDMD"]
    assert r["sources"] == ["gajjala", "watch"] and r["queued_at"] == NOW and got["new"] == []
    assert got["queued"] == 1


def test_two_interleaved_calls_for_one_new_symbol_make_one_row_both_sources_new_once():
    db, sp = DB(), Spawn()
    inner = {}

    def racer(coll, q, upd):                                   # the other source's whole call lands first
        inner["got"] = EC.enqueue(["NXAT"], SESSION, EC.SRC_WATCH, db=db, now=NOW, spawn=sp)
    ec(db).before_upsert = racer
    outer = EC.enqueue(["NXAT"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW, spawn=sp)
    r = rows(db)
    assert list(r) == ["2026-11-27|NXAT"] and sorted(r["2026-11-27|NXAT"]["sources"]) == ["gajjala", "watch"]
    assert inner["got"]["new"] == ["NXAT"] and outer["new"] == []             # reported once
    assert outer["queued"] == 1


@pytest.mark.parametrize("bad", [[None, 5, "", "  ", "state|sec", "STATE|FTS", "A B", "X|Y"], []])
def test_NEGATIVE_a_state_id_blank_or_junk_symbol_is_dropped(bad):
    db, sp = DB(), Spawn()
    got = EC.enqueue(bad, SESSION, EC.SRC_GAJJALA, db=db, now=NOW, spawn=sp)
    assert got["reason"] == "no_symbols" and rows(db) == {} and sp.calls == [] and ec(db).ops == []
    got = EC.enqueue(bad + ["whlr"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW, spawn=sp)
    assert got["new"] == ["WHLR"] and list(rows(db)) == ["2026-11-27|WHLR"]


def test_NEGATIVE_under_pytest_with_no_spawn_nothing_is_read_written_or_spawned():
    class Boom:
        def __getitem__(self, k):
            raise AssertionError("no read under pytest")
    got = EC.enqueue(["BDMD"], SESSION, EC.SRC_GAJJALA, db=Boom(), now=NOW)
    assert got == {"new": [], "queued": 0, "spawned": False, "reason": "test"}


@pytest.mark.parametrize("mode", ["off", "yes", "", None, "ON"])
def test_NEGATIVE_switched_off_queues_and_spawns_nothing(monkeypatch, mode):
    monkeypatch.setattr(EC, "EC_WHEN", mode)
    db, sp = DB(), Spawn()
    got = EC.enqueue(["BDMD"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW, spawn=sp)
    assert got["reason"] == "off" and ec(db).ops == [] and sp.calls == []
    assert EC.run_child(db, NOW, steps={})["reason"] == "off" and ec(db).ops == []


@pytest.mark.parametrize("session,source,reason", [("junk", "gajjala", "no_session"), (None, "watch", "no_session"),
                                                   (SESSION, "luk", "source"), (SESSION, None, "source")])
def test_NEGATIVE_a_bad_session_or_source_writes_nothing(session, source, reason):
    db, sp = DB(), Spawn()
    assert EC.enqueue(["BDMD"], session, source, db=db, now=NOW, spawn=sp)["reason"] == reason
    assert ec(db).ops == [] and sp.calls == []


def test_NEGATIVE_no_spawn_when_no_row_is_queued():
    db, sp = DB(), Spawn()
    ec(db).docs["2026-11-27|BDMD"] = {"_id": "2026-11-27|BDMD", "session": SESSION, "symbol": "BDMD",
                                      "status": EC.ST_DONE, "sources": ["gajjala"], "at": NOW}
    got = EC.enqueue(["BDMD"], SESSION, EC.SRC_WATCH, db=db, now=NOW, spawn=sp)
    assert got["spawned"] is False and sp.calls == [] and EC.EC_LEASE_ID not in ec(db).docs
    assert rows(db)["2026-11-27|BDMD"]["sources"] == ["gajjala", "watch"]          # the source is still added
    assert rows(db)["2026-11-27|BDMD"]["status"] == EC.ST_DONE                    # once a session: not re-run


def test_spawn_gap_three_calls_inside_the_gap_one_spawn_then_a_second_after_it():
    db, sp = DB(), Spawn()
    for i, s in enumerate(("A", "B", "C")):                      # the child never claims
        EC.enqueue([s], SESSION, EC.SRC_WATCH, db=db, now=NOW + timedelta(seconds=60 * i), spawn=sp)
    assert len(sp.calls) == 1
    EC.enqueue(["D"], SESSION, EC.SRC_WATCH, db=db, now=NOW + timedelta(seconds=EC.EC_SPAWN_GAP_SEC + 1), spawn=sp)
    assert len(sp.calls) == 2
    EC.enqueue(["E"], SESSION, EC.SRC_WATCH, db=db, now=NOW + timedelta(seconds=EC.EC_SPAWN_GAP_SEC + 2), spawn=sp)
    assert len(sp.calls) == 2                                    # inside the new gap
    assert EC.EC_SPAWN_GAP_SEC == EC.EC_LEASE_SEC == SB.SB_ERROR_RETRY_MIN * 60


def test_NEGATIVE_a_held_lease_spawns_nothing():
    db, sp = DB(), Spawn()
    ec(db).docs[EC.EC_LEASE_ID] = {"_id": EC.EC_LEASE_ID, "until": NOW + timedelta(minutes=3), "token": "x",
                                   "claimed_at": NOW - timedelta(minutes=2),
                                   "spawned_at": NOW - timedelta(hours=1)}
    got = EC.enqueue(["BDMD"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW, spawn=sp)
    assert got["spawned"] is False and sp.calls == [] and got["new"] == ["BDMD"]


def test_a_clean_release_lets_the_next_call_spawn_at_once():
    db, sp = DB(), Spawn()
    EC.enqueue(["BDMD"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW, spawn=sp)
    EC.run_child(db, NOW + timedelta(seconds=5), steps=_steps())
    EC.enqueue(["POM"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW + timedelta(seconds=10), spawn=sp)
    assert len(sp.calls) == 2


def test_NEGATIVE_a_raising_spawn_gives_the_gap_back():
    db = DB()
    got = EC.enqueue(["BDMD"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW, spawn=Spawn(OSError("no fork")))
    assert got["spawned"] is False
    sp = Spawn()
    EC.enqueue(["POM"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW + timedelta(seconds=1), spawn=sp)
    assert len(sp.calls) == 1


# REFIX 2026-11-27: the child marks ALL its rows `running` up front, so a child killed after that mark (SIGKILL /
# deploy) left only `running` rows and step 3 (queued only) never spawned again — the "next claim re-queues" promise had
# no trigger. Step 3 now looks for `queued` OR `running`; the lease and the spawn gap still stop a double spawn.
class _Killed(BaseException):
    pass


def _kill_child_after_the_mark(db, at):
    snap = {}

    def refresh(sym, d):
        snap["docs"] = copy.deepcopy(ec(db).docs)              # the state at the moment of the kill
        raise _Killed()
    with pytest.raises(_Killed):
        EC.run_child(db, at, steps=_steps(refresh=refresh))
    ec(db).docs = snap["docs"]                                  # SIGKILL: no finally, no release


def test_a_child_killed_after_marking_its_rows_running_is_spawned_again_once_its_lease_runs_out():
    names = ("AAA", "BBB", "CCC")
    db, sp = child_db(names), Spawn()
    for src in (EC.SRC_GAJJALA, EC.SRC_WATCH):
        EC.enqueue(list(names), SESSION, src, db=db, now=NOW, spawn=sp)
    assert len(sp.calls) == 1
    _kill_child_after_the_mark(db, NOW + timedelta(seconds=5))
    assert {r["status"] for r in rows(db).values()} == {EC.ST_RUNNING}
    dead = NOW + timedelta(seconds=5 + EC.EC_LEASE_SEC + 1)    # lease and spawn gap both run out
    for src in (EC.SRC_GAJJALA, EC.SRC_WATCH):                 # both sources already listed: no row write at all
        got = EC.enqueue(list(names), SESSION, src, db=db, now=dead, spawn=sp)
        assert got["queued"] == 0 and got["new"] == []
    assert len(sp.calls) == 2                                   # ONE respawn, not one per call
    got = EC.run_child(db, dead + timedelta(seconds=5), steps=_steps())
    assert got["done"] == 3 and {r["status"] for r in rows(db).values()} == {EC.ST_DONE}
    for r in rows(db).values():
        assert "not checked yet" not in (EC.words(r) or "")


def test_NEGATIVE_running_rows_of_a_live_child_spawn_nothing_while_its_lease_holds():
    names = ("AAA", "BBB")
    db, sp = child_db(names), Spawn()
    EC.enqueue(list(names), SESSION, EC.SRC_WATCH, db=db, now=NOW, spawn=sp)
    _kill_child_after_the_mark(db, NOW + timedelta(seconds=5))   # same doc state as a live child mid-run
    for secs in (6, 60, EC.EC_LEASE_SEC):                         # inside the lease (until = claim + EC_LEASE_SEC)
        got = EC.enqueue(list(names), SESSION, EC.SRC_GAJJALA, db=db, now=NOW + timedelta(seconds=secs), spawn=sp)
        assert got["spawned"] is False
    assert len(sp.calls) == 1


def test_NEGATIVE_a_running_row_of_an_earlier_session_spawns_nothing():
    db, sp = child_db(("AAA",), status=EC.ST_RUNNING, session="2026-11-26"), Spawn()
    ec(db).docs["2026-11-27|BBB"] = {"_id": "2026-11-27|BBB", "session": SESSION, "symbol": "BBB",
                                     "status": EC.ST_DONE, "sources": ["watch"], "at": NOW}
    got = EC.enqueue(["BBB"], SESSION, EC.SRC_WATCH, db=db, now=NOW, spawn=sp)
    assert got["spawned"] is False and sp.calls == [] and EC.EC_LEASE_ID not in ec(db).docs


def test_NEGATIVE_a_running_row_inside_the_spawn_gap_spawns_nothing_then_spawns_after_it():
    db, sp = child_db(("AAA",), status=EC.ST_RUNNING), Spawn()
    ec(db).docs[EC.EC_LEASE_ID] = {"_id": EC.EC_LEASE_ID, "until": NOW - timedelta(seconds=1), "token": "dead",
                                   "spawned_at": NOW - timedelta(seconds=10)}
    got = EC.enqueue(["AAA"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW, spawn=sp)
    assert got["spawned"] is False and sp.calls == []
    got = EC.enqueue(["AAA"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW + timedelta(seconds=EC.EC_SPAWN_GAP_SEC),
                     spawn=sp)
    assert got["spawned"] is True and len(sp.calls) == 1


# ═════════════════════════════════════════════ run_child [C5]
def rec(sym, **kw):
    r = {"_id": sym, "symbol": sym, "v": 2, "settlement_date": "2026-11-13", "short_interest": 77883,
         "prev_settlement_date": "2026-10-30", "float_shares": 1545214, "float_asof": "2026-11-25",
         "shares_outstanding": 35761933, "shares_asof": "2026-11-25"}
    r.update(kw)
    return r


def ok_sub(**kw):
    s = {"status": "ok", "read_at": "2026-11-27T14:30:00Z", "error": None, "error_at": None, "strikes": 0}
    s.update(kw)
    return s


def fresh_doc(sym, mfloat_asof="2026-11-10", splits_since="2026-10-01", **kw):
    """A checked basis doc nothing is due on: checked 30 min ago, `seen` = the record, ok subs, a fresh second float
    dated on/after the splits window."""
    d = {"_id": sym, "v": 1, "checked_at": "2026-11-27T14:30:00Z", "seen": SB._seen_of(rec(sym)),
         "ref": ok_sub(cik="0001877971", type="ADRC"), "sec": ok_sub(since="2026-10-30", covers=[], filings=[]),
         "splits": ok_sub(since=splits_since, rows=[]),
         "mfloat": ok_sub(shares=10373225, pct=None, as_of=mfloat_asof, read_at="2026-11-26T03:00:00Z")}
    d.update(kw)
    return d


class Step:
    def __init__(self, fn=None):
        self.calls, self.fn = [], fn

    def __call__(self, *a, **k):
        self.calls.append(a)
        return self.fn(*a, **k) if self.fn else None


def block_of(sym, chip="SI High 30.1% float · 11/13", flags=()):
    return {"symbol": sym, "status": "ok", "chip": chip, "tier": "high", "si_shares": 1958070,
            "settlement_date": "2026-11-13", "shares_outstanding": 56518768,
            "basis": {"flags": [{"key": k, "short": "x", "text": "y", "emoji": "e"} for k in flags]}}


def _steps(**kw):
    s = {"refresh": Step(lambda sym, d: fresh_doc(sym)), "fetch_mfloats": Step(lambda syms: {
        x: {"status": "ok", "shares": 1, "pct": None, "as_of": "2026-11-20"} for x in syms}),
         "store_mfloats": Step(lambda d, got, now: {"written": len(got)}),
         "widen": Step(lambda sym, d: {"status": "widened"}), "split": Step(lambda sym, d: "held"),
         "block": Step(lambda sym, d, today: block_of(sym))}
    s.update(kw)
    return s


def child_db(syms=("BDMD",), docs=(), status=EC.ST_QUEUED, session=SESSION, recs=None):
    db = DB(**{SIC.SI_COLL: Coll(recs if recs is not None else [rec(s) for s in syms]), SB.SB_COLL: Coll(docs)})
    for s in syms:
        ec(db).docs["%s|%s" % (session, s)] = {"_id": "%s|%s" % (session, s), "v": 1, "session": session,
                                               "symbol": s, "status": status, "queued_at": NOW - timedelta(minutes=1),
                                               "at": NOW, "sources": ["gajjala"]}
    return db


def test_NEGATIVE_no_lease_doc_the_first_claim_succeeds_and_the_rows_run():
    db = child_db()
    assert EC.EC_LEASE_ID not in ec(db).docs
    got = EC.run_child(db, NOW, steps=_steps())
    assert got["reason"] is None and got["done"] == 1 and rows(db)["2026-11-27|BDMD"]["status"] == EC.ST_DONE
    lease = ec(db).docs[EC.EC_LEASE_ID]
    assert lease["until"] == NOW and lease["spawned_at"] == NOW - timedelta(seconds=EC.EC_SPAWN_GAP_SEC)   # released
    assert ec(db).indexes == [([("at", 1)], {"expireAfterSeconds": 30 * 86400})]


def test_NEGATIVE_a_held_lease_exits_without_a_read():
    db = child_db()
    ec(db).docs[EC.EC_LEASE_ID] = {"_id": EC.EC_LEASE_ID, "until": NOW + timedelta(minutes=4), "token": "other"}
    st = _steps()
    got = EC.run_child(db, NOW, steps=st)
    assert got["reason"] == "lease held"
    assert ec(db).reads() == [] and all(s.calls == [] for s in st.values())
    assert ec(db).docs[EC.EC_LEASE_ID]["token"] == "other"                         # nothing of the holder released
    assert rows(db)["2026-11-27|BDMD"]["status"] == EC.ST_QUEUED


def test_a_running_row_left_by_a_killed_child_is_queued_again_and_run():
    db = child_db(status=EC.ST_RUNNING)
    ec(db).docs[EC.EC_LEASE_ID] = {"_id": EC.EC_LEASE_ID, "until": NOW - timedelta(seconds=1), "token": "dead"}
    got = EC.run_child(db, NOW, steps=_steps())
    sets = [o[2]["$set"].get("status") for o in ec(db).writes() if o[0] == "update_one"
            and o[1] == {"_id": "2026-11-27|BDMD"}]
    assert sets[:3] == [EC.ST_QUEUED, EC.ST_RUNNING, EC.ST_DONE]
    assert got["done"] == 1


def test_phases_in_order_refresh_only_when_due_one_bulk_float_get_per_chunk_widen_only_when_needed(monkeypatch):
    monkeypatch.setattr(SB, "SB_MFLOAT_CHUNK", 2)
    names = ("AAA", "BBB", "CCC")
    stale_mf = fresh_doc("BBB", mfloat_asof="2026-03-31")              # older than splits.since → widen
    stale_mf["mfloat"]["read_at"] = "2026-11-01T00:00:00Z"            # not fresh → re-read
    docs = [fresh_doc("AAA"), stale_mf]                                 # CCC: no doc → refresh is due
    db = child_db(names, docs=docs)
    order = []
    st = _steps(refresh=Step(lambda sym, d: order.append(("refresh", sym)) or d[SB.SB_COLL].docs.setdefault(
        sym, fresh_doc(sym, mfloat=ok_sub(shares=1, pct=None, as_of="2026-11-10", read_at="2026-11-01T00:00:00Z")))),
        fetch_mfloats=Step(lambda syms: order.append(("mfloat", tuple(syms))) or {
            s: {"status": "ok", "shares": 1, "pct": None, "as_of": "2026-11-20"} for s in syms}),
        widen=Step(lambda sym, d: order.append(("widen", sym)) or {"status": "widened"}),
        split=Step(lambda sym, d: order.append(("split", sym)) or "held"))
    sleeps = []
    got = EC.run_child(db, NOW, steps=st, sleep=sleeps.append)
    assert got["done"] == 3
    assert order == [("refresh", "CCC"), ("mfloat", ("BBB", "CCC")),
                     ("split", "AAA"), ("widen", "BBB"), ("split", "BBB"), ("split", "CCC")]
    assert sleeps == []                                                # one chunk → no pause
    r = rows(db)
    assert r["2026-11-27|AAA"]["steps"] == {"refresh": "held", "mfloat": "held", "widen": "held", "split": "held",
                                            "failed_subs": []}
    assert r["2026-11-27|BBB"]["steps"]["widen"] == "ran" and r["2026-11-27|BBB"]["steps"]["mfloat"] == "ran"
    assert r["2026-11-27|CCC"]["steps"]["refresh"] == "ran"


def test_one_bulk_float_get_per_chunk_with_the_bulk_pause_between(monkeypatch):
    monkeypatch.setattr(SB, "SB_MFLOAT_CHUNK", 2)
    names = ("AAA", "BBB", "CCC", "DDD", "EEE")
    old = lambda s: fresh_doc(s, mfloat=ok_sub(shares=1, pct=None, as_of="2026-11-10",
                                               read_at="2026-11-01T00:00:00Z"))
    db = child_db(names, docs=[old(s) for s in names])
    st = _steps()
    sleeps = []
    EC.run_child(db, NOW, steps=st, sleep=sleeps.append)
    assert [c[0] for c in st["fetch_mfloats"].calls] == [["AAA", "BBB"], ["CCC", "DDD"], ["EEE"]]
    assert sleeps == [SIC.SI_BULK_SLEEP_SEC] * 2
    assert len(st["store_mfloats"].calls) == 1


def test_NEGATIVE_a_name_with_no_si_record_is_no_record_and_makes_no_outside_call():
    db = child_db(("ZZZ",), recs=[])
    st = _steps()
    got = EC.run_child(db, NOW, steps=st)
    assert got["no_record"] == 1 and rows(db)["2026-11-27|ZZZ"]["status"] == EC.ST_NO_RECORD
    assert all(s.calls == [] for s in st.values())
    assert EC.words(rows(db)["2026-11-27|ZZZ"]) is None


def test_NEGATIVE_a_raising_step_fails_that_name_by_type_and_the_next_name_still_runs():
    db = child_db(("AAA", "BBB"), docs=[fresh_doc("AAA"), fresh_doc("BBB")])

    def boom(sym, d, today):
        if sym == "AAA":
            raise ValueError("secret text https://x?apiKey=K")
        return block_of(sym)
    got = EC.run_child(db, NOW, steps=_steps(block=Step(boom)))
    a, b = rows(db)["2026-11-27|AAA"], rows(db)["2026-11-27|BBB"]
    assert a["status"] == EC.ST_FAILED and a["error"] == "ValueError" and "secret" not in repr(a)
    assert b["status"] == EC.ST_DONE and got["failed"] == 1 and got["done"] == 1
    assert EC.words(a) == "check failed 11/27 10:00 ET (ValueError) — the chip shows the last stored read."


def test_NEGATIVE_a_row_of_an_earlier_session_is_not_run():
    db = child_db(session="2026-11-26")
    st = _steps()
    got = EC.run_child(db, NOW, steps=st)
    r = rows(db)["2026-11-26|BDMD"]
    assert r["status"] == EC.ST_FAILED and r["error"] == EC.ERR_OLD_SESSION and got["old"] == 1
    assert st["block"].calls == [] and st["refresh"].calls == []


def test_NEGATIVE_a_taken_over_lease_stops_and_releases_nothing_of_the_new_holder():
    db = child_db(("AAA", "BBB"), docs=[fresh_doc("AAA"), fresh_doc("BBB")])

    def thief(sym, d, today):                                  # another child claims while this one works
        ec(db).docs[EC.EC_LEASE_ID].update({"token": "thief", "until": NOW + timedelta(minutes=5)})
        return block_of(sym)
    got = EC.run_child(db, NOW, steps=_steps(block=Step(thief)))
    assert got["stopped"] is True
    assert ec(db).docs[EC.EC_LEASE_ID]["token"] == "thief"
    assert ec(db).docs[EC.EC_LEASE_ID]["until"] == NOW + timedelta(minutes=5)      # not released
    assert rows(db)["2026-11-27|BBB"]["status"] == EC.ST_RUNNING                  # the next claim re-queues it


def test_the_lease_is_released_on_every_path(monkeypatch):
    db = child_db()
    monkeypatch.setattr(EC, "_run_claimed", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    got = EC.run_child(db, NOW, steps=_steps())
    assert got["reason"] == "error" and ec(db).docs[EC.EC_LEASE_ID]["until"] == NOW


def test_at_most_EC_MAX_PER_RUN_names(monkeypatch):
    monkeypatch.setattr(EC, "EC_MAX_PER_RUN", 2)
    names = ("AAA", "BBB", "CCC")
    db = child_db(names, docs=[fresh_doc(s) for s in names])
    got = EC.run_child(db, NOW, steps=_steps())
    assert got["rows"] == 2 and got["done"] == 2
    assert sum(1 for r in rows(db).values() if r["status"] == EC.ST_QUEUED) == 1
    assert EC.EC_MAX_PER_RUN != SB.SB_QUEUE_MAX and SB.SB_QUEUE_MAX == 400                 # patched here only


def test_NEGATIVE_the_fake_refuses_lt_gt_and_the_module_never_spells_them():
    with pytest.raises(AssertionError):
        match({"a": 1}, {"a": {"$lt": 2}})
    with pytest.raises(AssertionError):
        match({"a": 1}, {"a": {"$gt": 0}})
    tree = ast.parse((BACKEND / "short_interest" / "entry_check.py").read_text())
    doc = ast.get_docstring(tree, clean=False)
    lits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and n.value != doc and n.value.startswith("$")]
    assert lits and set(lits) <= ALLOWED_FILTER_OPS | ALLOWED_UPDATE_OPS, lits


def test_NEGATIVE_under_pytest_with_no_steps_nothing_is_read():
    class Boom:
        def __getitem__(self, k):
            raise AssertionError("no read")
    assert EC.run_child(Boom(), NOW)["reason"] == "test"


def test_the_result_is_the_audit_row_plus_the_flag_keys():
    db = child_db(docs=[fresh_doc("BDMD")])
    chip = "SI High 30.1% float · 11/13 · " + SCK.SHORT_SOURCES
    EC.run_child(db, NOW, steps=_steps(block=Step(lambda s, d, t: block_of(s, chip, ("sources_disagree",)))))
    res = rows(db)["2026-11-27|BDMD"]["result"]
    assert res["flags"] == ["sources_disagree"] and res["chip"] == chip and res["groups"] == ["gajjala"]
    assert set(res) == set(SCK.audit_row(block_of("BDMD"), None)) | {"flags"}


def test_the_default_block_is_THE_engine_si_map():
    db = child_db(docs=[fresh_doc("BDMD")])
    st = _steps()
    st.pop("block")
    EC.run_child(db, NOW, steps=st)
    r = rows(db)["2026-11-27|BDMD"]
    assert r["status"] == EC.ST_DONE and r["result"]["si_shares"] == 77883 and r["result"]["chip"]


# ═════════════════════════════════════════════ steps + words [C6]
def done_row(steps, sources=("gajjala",)):
    return {"status": EC.ST_DONE, "sources": list(sources), "done_at": NOW, "queued_at": NOW, "steps": steps}


def test_nothing_due_every_step_held_and_no_re_read_group():
    db = child_db(docs=[fresh_doc("BDMD")])
    EC.run_child(db, NOW, steps=_steps())
    r = rows(db)["2026-11-27|BDMD"]
    assert r["steps"] == {"refresh": "held", "mfloat": "held", "widen": "held", "split": "held", "failed_subs": []}
    w = EC.words(r)
    assert "re-read now" not in w and w.endswith(EC.TEXT_YAHOO)
    assert w == ("checked 11/27 10:00 ET when it listed on 🚩 — held from an earlier read: SEC share counts, filings "
                 "and splits, the second float, splits back to the second float's date, the 6-K split-word search."
                 " Yahoo's float is not re-read by this check.")


def test_a_due_refresh_ran_and_a_split_read_written_by_it_counts_ran():
    db = child_db()                                                    # no doc → due

    def refresh(sym, d):
        doc = fresh_doc(sym, checked_at=NOW_ISO)
        doc["sec"]["fts_split"] = ok_sub(read_at=NOW_ISO, since="2026-03-31", top_6k="x", top_6k_filed="2026-11-06",
                                         rows=[])
        d[SB.SB_COLL].docs[sym] = doc
        return doc
    EC.run_child(db, NOW, steps=_steps(refresh=Step(refresh)))
    s = rows(db)["2026-11-27|BDMD"]["steps"]
    assert s["refresh"] == "ran" and s["split"] == "ran"


def test_a_refresh_whose_sec_sub_holds_an_error_failed_and_the_sentence_names_it():
    db = child_db()

    def refresh(sym, d):
        doc = fresh_doc(sym, sec=ok_sub(error="http_500", since="2026-10-30"))
        d[SB.SB_COLL].docs[sym] = doc
        return doc
    EC.run_child(db, NOW, steps=_steps(refresh=Step(refresh)))
    r = rows(db)["2026-11-27|BDMD"]
    assert r["steps"]["refresh"] == "failed" and r["steps"]["failed_subs"] == ["sec"]
    assert "failed, the earlier read stands: SEC share counts, filings and splits (sec)" in EC.words(r)


def test_bad_subs_names_every_faulted_sub_and_the_fts_one():
    doc = fresh_doc("X", ref=ok_sub(status="failed"), splits=ok_sub(status="blocked"))
    doc["sec"]["fts"] = {"status": "ok", "error": "http_403"}
    assert EC._bad_subs(doc) == ["ref", "splits", "sec.fts"]
    assert EC._bad_subs(fresh_doc("X")) == [] and EC._bad_subs(None) == []


def test_off_steps_are_never_named_and_every_done_sentence_ends_with_yahoo():
    w = EC.words(done_row({"refresh": "ran", "mfloat": "off", "widen": "held", "split": "off", "failed_subs": []}))
    assert w == ("checked 11/27 10:00 ET when it listed on 🚩 — re-read now: SEC share counts, filings and splits; "
                 "held from an earlier read: splits back to the second float's date. Yahoo's float is not re-read by "
                 "this check.")
    assert "second float," not in w and "split-word" not in w
    for steps in ({"refresh": "failed", "failed_subs": ["ref"]}, {"split": "ran"}, {}, {"mfloat": "off"}):
        assert EC.words(done_row(steps)).endswith(EC.TEXT_YAHOO)


def test_the_source_words_are_in_a_fixed_order():
    assert "listed on 🚩 👀 —" in EC.words(done_row({"refresh": "ran"}, sources=("watch", "gajjala")))
    assert "listed on 👀 —" in EC.words(done_row({"refresh": "ran"}, sources=("watch",)))


def test_queued_and_failed_sentences():
    q = {"status": EC.ST_QUEUED, "sources": ["watch"], "queued_at": NOW}
    assert EC.words(q) == "queued 11/27 10:00 ET when it listed on 👀 — not checked yet."
    assert EC.words(dict(q, status=EC.ST_RUNNING)) == EC.words(q)
    f = {"status": EC.ST_FAILED, "error": "old_session", "done_at": NOW, "sources": ["gajjala"]}
    assert EC.words(f) == "check failed 11/27 10:00 ET (old_session) — the chip shows the last stored read."


@pytest.mark.parametrize("row", [None, "x", {}, {"status": "no_record", "sources": ["gajjala"], "done_at": NOW},
                                 {"status": "weird", "done_at": NOW}, {"status": "done", "sources": ["gajjala"]},
                                 {"status": "done", "done_at": NOW, "sources": []}])
def test_NEGATIVE_no_record_or_junk_is_None(row):
    assert EC.words(row) is None


@pytest.mark.parametrize("steps", [None, "x", 5, ["ran"], {"refresh": "bogus"}])
def test_NEGATIVE_junk_steps_give_the_short_sentence_plus_yahoo(steps):
    assert EC.words(done_row(steps)) == "checked 11/27 10:00 ET when it listed on 🚩." + EC.TEXT_YAHOO


# ═════════════════════════════════════════════ load / entered
def test_load_is_one_in_find_and_never_the_lease():
    db = child_db(("BDMD", "POM"))
    ec(db).docs[EC.EC_LEASE_ID] = {"_id": EC.EC_LEASE_ID, "until": NOW}
    ec(db).ops.clear()
    got = EC.load(["bdmd", "pom", "lease", "NONE"], SESSION, db)
    assert set(got) == {"BDMD", "POM"} and got["BDMD"]["symbol"] == "BDMD"
    assert ec(db).reads() == [("find", {"_id": {"$in": ["2026-11-27|BDMD", "2026-11-27|POM", "2026-11-27|LEASE",
                                                       "2026-11-27|NONE"]}})]


def test_NEGATIVE_load_and_entered_answer_empty_on_any_failure():
    class Boom:
        def __getitem__(self, k):
            raise RuntimeError("down")
    assert EC.load(["BDMD"], SESSION, Boom()) == {} and EC.entered(SESSION, Boom()) == []
    assert EC.load(["BDMD"], "junk", DB()) == {} and EC.entered("junk", DB()) == []
    with pytest.raises(RuntimeError):
        EC.entered(SESSION, Boom(), strict=True)


def test_entered_filters_by_source_and_session():
    db = DB()
    EC.enqueue(["BDMD", "POM"], SESSION, EC.SRC_GAJJALA, db=db, now=NOW, spawn=Spawn())
    EC.enqueue(["POM", "WATCHONLY"], SESSION, EC.SRC_WATCH, db=db, now=NOW, spawn=Spawn())
    EC.enqueue(["OLD"], "2026-11-26", EC.SRC_GAJJALA, db=db, now=NOW, spawn=Spawn())
    assert EC.entered(SESSION, db) == ["BDMD", "POM", "WATCHONLY"]
    assert EC.entered(SESSION, db, source=EC.SRC_GAJJALA) == ["BDMD", "POM"]
    assert EC.entered(SESSION, db, source=EC.SRC_WATCH) == ["POM", "WATCHONLY"]


# ═════════════════════════════════════════════ imports
def test_NEGATIVE_no_si_track_no_push_alert_lane_module_no_http_client():
    tree = ast.parse((BACKEND / "short_interest" / "entry_check.py").read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods |= {"%s.%s" % (n.module, a.name) for a in n.names} | {n.module or ""}
    joined = " ".join(sorted(mods))
    for bad in ("si_track", "push", "alert", "lane", "trading", "requests", "urllib", "http", "notify"):
        assert bad not in joined, bad
    code = ("import sys, short_interest.entry_check;"
            "bad=[m for m in sys.modules if 'si_track' in m or m.startswith('trading')];print(bad);"
            "sys.exit(1 if bad else 0)")
    r = subprocess.run([sys.executable, "-B", "-c", code], cwd=BACKEND, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


# ═════════════════════════════════════════════ CLI
def test_cli_show_writes_nothing(monkeypatch, capsys):
    db = child_db(("BDMD",))
    monkeypatch.setattr(EC, "_default_db", lambda: db)
    ec(db).ops.clear()
    assert EC.main(["--show", "--session", SESSION]) == 0
    out = capsys.readouterr().out
    assert '"BDMD"' in out and "not checked yet" in out and ec(db).writes() == []


# ═════════════════════════════════════════════ the audit's 🚩 group [C8]
from tests import test_si_source_audit_2026_11_26 as TA            # noqa: E402 — the audit harness (capture, fakes)


def _entry_rows(db, rows_):
    c = db[EC.EC_COLL]
    for sym, srcs in rows_:
        c.docs["%s|%s" % (TA.SESSION, sym)] = {"_id": "%s|%s" % (TA.SESSION, sym), "session": TA.SESSION,
                                                "symbol": sym, "status": "done", "sources": list(srcs)}


def test_audit_entered_group_lists_gajjala_rows_only(monkeypatch):
    TA._watch_dki(monkeypatch)
    st, db = TA.fake_store(), TA._db()
    _entry_rows(db, [("GMEX", ["gajjala", "watch"]), ("NCPL", ["watch"]), ("chwy", ["gajjala"])])
    got = SA.names(st, db, TA.NOW)
    assert got["entered"] == ["CHWY", "GMEX"] and "NCPL" not in got["entered"] and "entered" not in got["faults"]


def test_NEGATIVE_audit_entered_read_fault_is_named_and_the_others_stand(monkeypatch):
    TA._watch_dki(monkeypatch)
    monkeypatch.setattr(EC, "entered", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    got = SA.names(TA.fake_store(), TA._db(), TA.NOW)
    assert got["entered"] == [] and "entered" in got["faults"] and got["watch"] == ["DKI"]


def test_NEGATIVE_no_entry_rows_the_three_groups_exactly_as_before(monkeypatch):
    TA._watch_dki(monkeypatch)
    st = TA.fake_store()
    got = SA.names(st, TA._db(), TA.NOW)
    assert got == {"listed": [], "followed": [], "watch": ["DKI"], "entered": [], "faults": ["listed"]}
    assert SA.GROUPS[:3] == ("listed", "followed", "watch") and SA.GROUPS[-1] == "entered"
    assert SA.GROUP_WORDS == {"listed": "🩳", "followed": "🔭", "watch": "👀", "entered": "🚩"}


def test_audit_night_rows_carry_flagged_and_the_entered_group():
    res, sink, _ = TA._night(names_fn=lambda st, d, now: {"listed": ["NCPL"], "followed": [], "watch": [],
                                                          "entered": ["GMEX"], "faults": []})
    gm, nc = TA._row(sink, "GMEX"), TA._row(sink, "NCPL")
    assert gm["groups"] == ["entered"] and res["names"]["entered"] == 1
    assert [r["symbol"] for r in sink["rows"]] == ["NCPL", "GMEX"]                  # 🚩 LAST
    for r in sink["rows"]:
        assert r["flagged"] is (SCK.SHORT_SOURCES in (r["chip"] or ""))
    assert gm["flagged"] is True and nc["flagged"] is False
    assert SA.cells(gm)["on"] == "🚩"


def test_word_and_sort_treat_flagged_like_contested():
    base = {"tier": "high", "state": "compared", "float_rel": 0.5, "symbol": "B"}
    assert SA._word(dict(base, flagged=True)) == SA.WORD_CONTESTED % "High"
    assert SA._word(dict(base, flagged=False)) == "High"
    rs = [dict(base, symbol="A", float_rel=0.9), dict(base, symbol="B", flagged=True, float_rel=0.1)]
    assert [r["symbol"] for r in sorted(rs, key=SA._sort_key)] == ["B", "A"]
