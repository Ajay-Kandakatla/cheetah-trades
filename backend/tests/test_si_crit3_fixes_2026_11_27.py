"""⏱✂️ 2026-11-27 — two critic findings on the SI on-entry check (spec sicheck, crit3).

1 (MEDIUM) — the SEC pace was per PROCESS only: the cron entry-check child and the api's on-view worker each kept their
  own 0.5 s gap, so together they could start two data.sec.gov GETs at once. `_sec_wait` now also claims a host-wide
  slot in ONE atomic `find_one_and_update` on `state|sec_pace` (next_at = max(now, next_at) + SB_SEC_MIN_INTERVAL_SEC);
  any Mongo fault → the in-process pace alone, never a raise.
2 (LOW) — phase C asked `fts_split_step` (one SEC listing GET) right after phase A's refresh had already run the
  split-word step on the same listing; it now records `held` (or `ran` when the refresh wrote a fresh read) and asks
  nothing — unless the window moved or the refresh's answer is bad.

Hermetic: the pace collections below are fakes (in-memory, and file-backed with an flock for the two-process test);
`_default_db` is never reached by a child. NEGATIVES are marked NEGATIVE.
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import short_interest.entry_check as EC
import short_interest.share_basis as SB
from tests.test_si_entry_check_2026_11_27 import (NOW, NOW_ISO, Step, _steps, child_db, fresh_doc, ok_sub, rows)

BACKEND = Path(__file__).resolve().parents[1]
S = SB.SB_SEC_MIN_INTERVAL_SEC
_MISSING = object()


# ═════════════════════════════════════════════ a pipeline-update evaluator (the operators `_claim_shared_slot` sends)
def _ev(e, doc):
    if isinstance(e, str) and e.startswith("$"):
        return doc.get(e[1:], _MISSING)
    if isinstance(e, dict) and len(e) == 1:
        op, a = next(iter(e.items()))
        if op == "$add":
            return sum(_ev(x, doc) for x in a)
        if op == "$max":
            return max(_ev(x, doc) for x in a)
        if op == "$cond":
            return _ev(a[1], doc) if _ev(a[0], doc) else _ev(a[2], doc)
        if op == "$isNumber":
            v = _ev(a, doc)
            return isinstance(v, (int, float)) and not isinstance(v, bool)
        raise AssertionError("operator not modelled: %s" % op)
    return e


def _apply(doc, update):
    assert isinstance(update, list), "the slot claim must be ONE pipeline update (atomic read-modify-write)"
    for stage in update:
        assert set(stage) == {"$set"}
        vals = {k: _ev(v, doc) for k, v in stage["$set"].items()}
        doc.update(vals)
    return doc


class MemPaceColl:
    """In-memory, atomic under a lock; records every call."""

    def __init__(self, doc=None):
        self.docs = {} if doc is None else {doc["_id"]: dict(doc)}
        self.lock = threading.Lock()
        self.calls = []

    def find_one_and_update(self, flt, update, upsert=False, return_document=False):
        with self.lock:
            self.calls.append(("fau", flt, update, upsert, return_document))
            old = self.docs.get(flt["_id"])
            if old is None and not upsert:
                return None
            new = _apply(dict(old or {"_id": flt["_id"]}), update)
            self.docs[flt["_id"]] = new
            return dict(new) if return_document else (dict(old) if old else None)

    def update_one(self, flt, update):
        with self.lock:
            self.calls.append(("uo", flt, update))
            d = self.docs.get(flt["_id"])
            if d is not None and all(d.get(k) == v for k, v in flt.items()):
                d.update(update["$set"])


class FilePaceColl:
    """The same, shared by PROCESSES: the state is a JSON file behind an exclusive flock; every claimed next_at is
    appended to `claims` so the test can read the slots handed out."""

    def __init__(self, path):
        self.path = str(path)

    def find_one_and_update(self, flt, update, upsert=False, return_document=False):
        with open(self.path + ".lock", "a") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            try:
                st = json.loads(Path(self.path).read_text()) if os.path.exists(self.path) else {"docs": {}, "claims": []}
                old = st["docs"].get(flt["_id"])
                new = _apply(dict(old or {"_id": flt["_id"]}), update)
                st["docs"][flt["_id"]] = new
                st["claims"].append(new["next_at"])
                Path(self.path).write_text(json.dumps(st))
                return dict(new)
            finally:
                fcntl.flock(lk, fcntl.LOCK_UN)

    def update_one(self, flt, update):
        raise AssertionError("no reset expected in the two-process test")


class Boom:
    def find_one_and_update(self, *a, **k):
        raise RuntimeError("mongo down")

    def update_one(self, *a, **k):
        raise RuntimeError("mongo down")


class Junk:
    def __init__(self, ans):
        self.ans = ans

    def find_one_and_update(self, *a, **k):
        return self.ans


@pytest.fixture
def fresh_pace(monkeypatch):
    monkeypatch.setattr(SB, "_sec_last", {"t": None})
    monkeypatch.setattr(SB, "_pace_coll", None)


class Clock:
    """One fake time line for both clocks; `sleep` advances it."""

    def __init__(self, t=1000.0):
        self.t, self.slept = t, []

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.slept.append(s)
        self.t += s


def wait(coll, c):
    SB._sec_wait(clock=c, sleep=c.sleep, coll=coll, wall=c)


# ═════════════════════════════════════════════ 1. the shared slot
def test_the_claim_is_one_pipeline_update_on_its_own_doc_beside_state_sec(fresh_pace):
    coll, c = MemPaceColl(), Clock()
    wait(coll, c)
    assert len(coll.calls) == 1
    _, flt, update, upsert, ret = coll.calls[0]
    assert flt == {"_id": SB.SB_STATE_SEC_PACE_ID} and upsert is True and ret is True
    assert SB.SB_STATE_SEC_PACE_ID not in (SB.SB_STATE_SEC_ID, SB.SB_STATE_FTS_ID)
    assert coll.docs[SB.SB_STATE_SEC_PACE_ID]["next_at"] == 1000.0 + S
    assert c.slept == []                                             # first slot = now


def test_two_claims_at_the_same_instant_are_one_spacing_apart(fresh_pace):
    coll = MemPaceColl()
    a, b = Clock(), Clock()                                          # two "processes", same wall time, own monotonic
    SB._sec_wait(clock=a, sleep=a.sleep, coll=coll, wall=a)
    SB._sec_last["t"] = None                                         # the second caller's process has no history
    SB._sec_wait(clock=b, sleep=b.sleep, coll=coll, wall=b)
    assert a.slept == [] and b.slept == [pytest.approx(S)]
    assert coll.docs[SB.SB_STATE_SEC_PACE_ID]["next_at"] == pytest.approx(1000.0 + 2 * S)


def test_a_late_caller_takes_now_not_the_stale_next_at(fresh_pace):
    coll, c = MemPaceColl({"_id": SB.SB_STATE_SEC_PACE_ID, "next_at": 10.0}), Clock(1000.0)
    wait(coll, c)
    assert c.slept == [] and coll.docs[SB.SB_STATE_SEC_PACE_ID]["next_at"] == 1000.0 + S


def test_NEGATIVE_a_non_number_next_at_counts_as_now(fresh_pace):
    for junk in ("soon", True, None, {"x": 1}):
        SB._sec_last["t"] = None
        coll, c = MemPaceColl({"_id": SB.SB_STATE_SEC_PACE_ID, "next_at": junk}), Clock(1000.0)
        wait(coll, c)
        assert c.slept == [] and coll.docs[SB.SB_STATE_SEC_PACE_ID]["next_at"] == 1000.0 + S


def test_NEGATIVE_a_mongo_fault_falls_back_to_the_in_process_pace_and_never_raises(fresh_pace):
    c = Clock()
    wait(Boom(), c)
    wait(Boom(), c)
    assert c.slept == [S]                                            # the in-process gap still holds
    c.t += 10
    wait(Boom(), c)
    assert c.slept == [S]


@pytest.mark.parametrize("ans", [None, {}, {"next_at": "x"}, {"next_at": True}, ["junk"]])
def test_NEGATIVE_a_junk_answer_falls_back_to_the_in_process_pace(fresh_pace, ans):
    c = Clock()
    wait(Junk(ans), c)
    wait(Junk(ans), c)
    assert c.slept == [S]


def test_NEGATIVE_no_database_paces_in_process_only(fresh_pace, monkeypatch):
    monkeypatch.setattr(SB, "_default_db", lambda: None)
    assert SB._pace_collection() is None
    c = Clock()
    SB._sec_wait(clock=c, sleep=c.sleep, wall=c)
    SB._sec_wait(clock=c, sleep=c.sleep, wall=c)
    assert c.slept == [S]


def test_NEGATIVE_a_default_db_that_raises_never_raises_out(fresh_pace, monkeypatch):
    def boom():
        raise RuntimeError("x")
    monkeypatch.setattr(SB, "_pace_collection", boom)
    c = Clock()
    SB._sec_wait(clock=c, sleep=c.sleep, wall=c)
    assert c.slept == []


def test_NEGATIVE_a_slot_beyond_the_http_timeout_is_reset_and_never_slept(fresh_pace):
    far = 1000.0 + SB.SB_HTTP_TIMEOUT_SEC * 100
    coll, c = MemPaceColl({"_id": SB.SB_STATE_SEC_PACE_ID, "next_at": far}), Clock(1000.0)
    wait(coll, c)
    assert c.slept == []                                             # never blocks longer than one SEC call may
    assert coll.docs[SB.SB_STATE_SEC_PACE_ID]["next_at"] == 1000.0 + S   # compare-and-set reset
    assert coll.calls[-1][0] == "uo" and coll.calls[-1][1]["next_at"] == far + S
    wait(coll, c)                                                    # the next claim is a normal one
    assert c.slept == [pytest.approx(S)]


def test_a_slot_at_the_http_timeout_is_still_waited(fresh_pace):
    coll = MemPaceColl({"_id": SB.SB_STATE_SEC_PACE_ID, "next_at": 1000.0 + SB.SB_HTTP_TIMEOUT_SEC})
    c = Clock(1000.0)
    wait(coll, c)
    assert c.slept == [pytest.approx(SB.SB_HTTP_TIMEOUT_SEC)]


def test_the_pace_doc_is_never_a_symbol():
    assert SB._clean(["POM", "STATE|SEC_PACE", "state|sec_pace"]) == ["POM"]


def test_the_spacing_constant_is_reused_not_retyped():
    src = (BACKEND / "short_interest" / "share_basis.py").read_text()
    body = src[src.index("def _claim_shared_slot"):src.index("def _resolve_http")]
    assert "SB_SEC_MIN_INTERVAL_SEC" in body and "0.5" not in body


# ═════════════════════════════════════════════ 1b. the 403 backoff is unchanged
def test_NEGATIVE_a_403_still_stops_every_sec_call_and_the_pace_doc_is_separate(fresh_pace, monkeypatch):
    coll = MemPaceColl()
    monkeypatch.setattr(SB, "_pace_coll", coll)
    monkeypatch.setattr(SB, "_sec_stop", {"until": None})

    class R:
        status_code = 403

        def json(self):
            return {}
    got = SB.fetch_filings("0001877971", "2026-10-01", http=lambda url, **k: R(), kind_fn=lambda f, i: None)
    assert got == {"status": "failed", "error": "http_403", "blocked": True}
    assert coll.docs[SB.SB_STATE_SEC_PACE_ID]["next_at"] > 0          # the GET took a shared slot

    class Basis:
        def __init__(self):
            self.docs = {}

        def replace_one(self, flt, doc, upsert=False):
            self.docs[flt["_id"]] = dict(doc)

        def find(self, q, *a, **k):
            return [dict(self.docs[i]) for i in q["_id"]["$in"] if i in self.docs]
    basis = Basis()
    db = {SB.SB_COLL: basis}
    now = datetime(2026, 11, 27, 15, 0, tzinfo=timezone.utc)
    SB._block_sec(db, now, got["error"], True)
    assert basis.docs[SB.SB_STATE_SEC_ID]["blocked_until"] == SB._ts(now + timedelta(minutes=SB.SB_SEC_BLOCK_MIN))
    assert SB.SB_STATE_SEC_PACE_ID not in basis.docs
    assert SB._sec_blocked(db, now + timedelta(minutes=SB.SB_SEC_BLOCK_MIN - 1)) is True
    SB._sec_stop["until"] = None
    assert SB._sec_blocked(db, now + timedelta(minutes=SB.SB_SEC_BLOCK_MIN + 1)) is False


# ═════════════════════════════════════════════ 1c. two real processes
CHILD = r"""
import sys, time, json
sys.path.insert(0, %(backend)r)
import short_interest.share_basis as SB
from tests.test_si_crit3_fixes_2026_11_27 import FilePaceColl
SB._default_db = lambda: None
SB._pace_coll = FilePaceColl(%(path)r) if %(shared)r else None
start = %(start)r
while time.time() < start:
    time.sleep(0.005)
out = []
for _ in range(%(n)d):
    SB._sec_wait()
    out.append(time.time())
print(json.dumps(out))
"""


def _two_processes(tmp_path, shared, n=4):
    path = tmp_path / "pace.json"
    start = time.time() + 4.0
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    code = CHILD % {"backend": str(BACKEND), "path": str(path), "shared": shared, "start": start, "n": n}
    ps = [subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                           cwd=str(BACKEND), env=env) for _ in range(2)]
    outs = [p.communicate(timeout=60) for p in ps]
    for p, (o, e) in zip(ps, outs):
        assert p.returncode == 0, e
    stamps = sorted(t for o, _ in outs for t in json.loads(o))
    claims = json.loads(path.read_text())["claims"] if shared else []
    return stamps, claims


def test_two_processes_never_get_two_slots_closer_than_the_spacing(tmp_path):
    stamps, claims = _two_processes(tmp_path, True)
    assert len(stamps) == 8 and len(claims) == 8
    slots = sorted(x - S for x in claims)
    assert all(b - a >= S - 1e-9 for a, b in zip(slots, slots[1:]))   # the atomic property, exact
    assert stamps[-1] - stamps[0] >= 7 * S - 0.05                      # 8 starts span at least 7 spacings
    assert min(b - a for a, b in zip(stamps, stamps[1:])) > S / 2      # measured; far from the in-process 0.0


def test_NEGATIVE_without_the_shared_slot_two_processes_start_together(tmp_path):
    stamps, _ = _two_processes(tmp_path, False)
    assert min(b - a for a, b in zip(stamps, stamps[1:])) < S          # the defect the shared slot removes


# ═════════════════════════════════════════════ 2. phase C: no second listing GET after a refresh that ran it
def _due_child(fs, mfloat_asof="2026-11-10"):
    """A due name (no doc) whose refresh stores a doc carrying `fs` as `sec.fts_split`."""
    db = child_db()

    def refresh(sym, d):
        doc = fresh_doc(sym, mfloat_asof=mfloat_asof)
        if fs is not None:
            doc["sec"]["fts_split"] = fs
        d[SB.SB_COLL].docs[sym] = doc
        return doc
    split = Step(lambda sym, d: "held")
    return db, _steps(refresh=Step(refresh), split=split), split


WIDE = "2026-10-30"                                                    # fresh_doc: min(sec.since, mfloat as_of)


def test_a_refresh_that_carried_a_good_split_answer_makes_no_second_listing_get():
    held = ok_sub(since=WIDE, top_6k="0001104659-26-128404", top_6k_filed="2026-11-16", rows=[],
                  read_at="2026-11-27T14:00:00Z")                      # older than the refresh: carried, not re-read
    db, st, split = _due_child(held)
    assert SB.split_since(fresh_doc("BDMD")) == WIDE
    EC.run_child(db, NOW, steps=st)
    s = rows(db)["2026-11-27|BDMD"]["steps"]
    assert split.calls == [] and s["refresh"] == "ran" and s["split"] == "held"


def test_a_refresh_that_wrote_a_fresh_split_read_counts_ran_without_a_second_get():
    db = child_db()

    def refresh(sym, d):
        doc = fresh_doc(sym, checked_at=NOW_ISO)
        doc["sec"]["fts_split"] = ok_sub(since=WIDE, read_at=NOW_ISO, top_6k="x", top_6k_filed="2026-11-06", rows=[])
        doc["sec"]["read_at"] = NOW_ISO        # a real refresh stamps the listing read with its own checked_at
        d[SB.SB_COLL].docs[sym] = doc
        return doc
    split = Step(lambda sym, d: "held")
    EC.run_child(db, NOW, steps=_steps(refresh=Step(refresh), split=split))
    s = rows(db)["2026-11-27|BDMD"]["steps"]
    assert split.calls == [] and s["refresh"] == "ran" and s["split"] == "ran"


def test_a_none_6k_answer_from_the_refresh_is_held_without_a_get():
    db, st, split = _due_child(ok_sub(status="none_6k", since=WIDE, rows=[], read_at="2026-11-27T14:00:00Z"))
    EC.run_child(db, NOW, steps=st)
    assert split.calls == [] and rows(db)["2026-11-27|BDMD"]["steps"]["split"] == "held"


def test_NEGATIVE_refresh_not_ran_the_split_step_still_runs():
    held = ok_sub(since=WIDE, top_6k="a", top_6k_filed="2026-11-16", rows=[])
    doc = fresh_doc("BDMD")
    doc["sec"]["fts_split"] = held
    db = child_db(docs=[doc])                                          # fresh doc → refresh held
    split = Step(lambda sym, d: "held")
    EC.run_child(db, NOW, steps=_steps(split=split))
    s = rows(db)["2026-11-27|BDMD"]["steps"]
    assert s["refresh"] == "held" and len(split.calls) == 1 and s["split"] == "held"


def test_NEGATIVE_refresh_failed_the_split_step_still_runs():
    db = child_db()

    def refresh(sym, d):
        doc = fresh_doc(sym, sec=ok_sub(error="http_500", since=WIDE))
        doc["sec"]["fts_split"] = ok_sub(since=WIDE, rows=[])
        d[SB.SB_COLL].docs[sym] = doc
        return doc
    split = Step(lambda sym, d: "stored")
    EC.run_child(db, NOW, steps=_steps(refresh=Step(refresh), split=split))
    s = rows(db)["2026-11-27|BDMD"]["steps"]
    assert s["refresh"] == "failed" and len(split.calls) == 1 and s["split"] == "ran"


@pytest.mark.parametrize("fs", [
    None,                                                              # the refresh wrote no split answer
    ok_sub(since=WIDE, rows=[], error="http_403"),                     # an error on it → retried
    ok_sub(status="failed", since=WIDE, rows=[]),                      # not good
    ok_sub(status="off", since=WIDE, rows=[]),                         # off → the step says so
    ok_sub(since="2026-03-31", rows=[]),                               # another window
])
def test_NEGATIVE_refresh_ran_but_its_split_answer_does_not_cover_the_step_still_runs(fs):
    db, st, split = _due_child(fs)
    EC.run_child(db, NOW, steps=st)
    s = rows(db)["2026-11-27|BDMD"]["steps"]
    assert s["refresh"] == "ran" and len(split.calls) == 1


def test_NEGATIVE_a_second_float_stored_in_phase_b_moves_the_window_and_the_step_runs():
    """Phase B stores a newer second float dated before sec.since → split_since moves → the refresh's answer (old
    window) no longer covers it."""
    db = child_db()
    held = ok_sub(since=WIDE, rows=[], read_at="2026-11-27T14:00:00Z")

    def refresh(sym, d):
        doc = fresh_doc(sym, mfloat=ok_sub(shares=1, pct=None, as_of="2026-11-10", read_at="2026-11-01T00:00:00Z"))
        doc["sec"]["fts_split"] = held
        d[SB.SB_COLL].docs[sym] = doc
        return doc

    def store(d, got, now):
        for s in got:
            d[SB.SB_COLL].docs[s]["mfloat"] = ok_sub(shares=1, pct=None, as_of="2026-09-30", read_at=NOW_ISO)
        return {"written": len(got)}
    split = Step(lambda sym, d: "stored")
    EC.run_child(db, NOW, steps=_steps(refresh=Step(refresh), store_mfloats=Step(store), split=split))
    s = rows(db)["2026-11-27|BDMD"]["steps"]
    assert s["refresh"] == "ran" and len(split.calls) == 1 and s["split"] == "ran"


def test_split_by_refresh_is_false_on_junk():
    for d in (None, {}, {"sec": None}, {"sec": {"fts_split": "x"}}, fresh_doc("X")):
        assert EC._split_by_refresh(d) is False


# ── 2026-11-27 critic LOW #2: under an SEC 403/429 stop the refresh carries the held `sec` (old split answer) ─────
def _stop_doc(sym, sec_read_at="2026-11-27T13:00:00Z"):
    from tests.test_si_entry_check_2026_11_27 import fresh_doc, ok_sub
    doc = fresh_doc(sym)
    doc["sec"]["fts_split"] = ok_sub(since="2026-10-30", top_6k="a1", top_6k_filed="2026-11-26", rows=[],
                                     read_at="2026-11-27T14:00:00Z")
    doc["sec"]["read_at"] = sec_read_at
    doc["checked_at"] = "2026-11-27T15:00:00Z"
    return doc


def test_NEGATIVE_a_carried_sec_under_the_stop_is_not_this_refreshs_read():
    import short_interest.entry_check as EC
    assert EC._split_by_refresh(_stop_doc("BDMD")) is False


def test_the_skip_still_holds_when_the_refresh_read_the_listing_itself(monkeypatch):
    import short_interest.entry_check as EC
    import short_interest.share_basis as SB
    doc = _stop_doc("BDMD", sec_read_at="2026-11-27T15:00:00Z")
    monkeypatch.setattr(SB, "split_since", lambda d: SB._day("2026-10-30"))
    assert EC._split_by_refresh(doc) is True


def test_NEGATIVE_phase_c_under_the_stop_runs_the_split_step_and_reports_it():
    from datetime import timedelta
    import short_interest.entry_check as EC
    import short_interest.share_basis as SB
    from tests.test_si_entry_check_2026_11_27 import NOW, Step, _steps, child_db, rows

    def _http(*a, **k):
        raise AssertionError("no SEC GET expected under the stop")

    db = child_db()

    def refresh(sym, d):
        doc = _stop_doc(sym)
        d[SB.SB_COLL].docs[sym] = doc
        return doc
    SB._sec_stop["until"] = NOW + timedelta(hours=1)
    try:
        split = Step(lambda sym, d: SB.fts_split_step(sym, d, NOW, http=_http))
        EC.run_child(db, NOW, steps=_steps(refresh=Step(refresh), split=split))
        s = rows(db)["2026-11-27|BDMD"]["steps"]
        assert len(split.calls) == 1
        assert s["split"] != EC.STEP_HELD if hasattr(EC, "STEP_HELD") else s["split"] != "held"
    finally:
        SB._sec_stop["until"] = None
