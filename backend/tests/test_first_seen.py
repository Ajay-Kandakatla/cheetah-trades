"""first_seen — the ✨ NEW ledger, and the drift guard against its twin.

`growth/tracker.py` has its own copy of this logic, written first (2026-09-12)
and live on the Explosive Growth board. It is deliberately NOT refactored to
call this module: that board works, is tested, and moving it buys the user
nothing. This file is what stops the duplication drifting.
"""
from __future__ import annotations

import time

from sepa import first_seen as FS


class _Coll:
    def __init__(self):
        self.docs = {}

    def update_one(self, q, upd, upsert=False):
        _id = q["_id"]
        is_new = _id not in self.docs
        d = self.docs.setdefault(_id, {"_id": _id})
        if is_new:
            d.update(upd.get("$setOnInsert") or {})
        d.update(upd.get("$set") or {})

    def find_one(self, q, *a, **k):
        return self.docs.get(q.get("_id"))

    def find(self, q, *a, **k):
        ids = (q.get("_id") or {}).get("$in")
        gt = (q.get("first_seen") or {}).get("$gt")
        for _id, d in self.docs.items():
            if _id == FS.META_ID:
                continue
            if ids is not None and _id not in ids:
                continue
            if gt is not None and not str(d.get("first_seen", "")) > str(gt):
                continue
            yield d


class _DB:
    def __init__(self):
        self.colls = {}

    def __getitem__(self, name):
        return self.colls.setdefault(name, _Coll())


def test_the_first_cohort_reports_ZERO_arrivals():
    db = _DB()
    FS.record("c", ["AAA", "BBB"], db=db)
    assert FS.newly_found("c", days=30, db=db) == set()


def test_only_the_ARRIVAL_is_new_on_a_later_build():
    db = _DB()
    FS.record("c", ["AAA", "BBB"], db=db)
    time.sleep(0.01)
    FS.record("c", ["AAA", "BBB", "CCC"], db=db)
    assert FS.newly_found("c", days=30, db=db) == {"CCC"}


def test_NEGATIVE_a_name_that_LEAVES_and_returns_keeps_its_original_first_seen():
    """first_seen is when we FIRST saw it. Re-stamping on every appearance
    would make a name that drops out for a day and comes back look new
    forever."""
    db = _DB()
    FS.record("c", ["AAA"], db=db)
    first = db["c"].docs["AAA"]["first_seen"]
    time.sleep(0.01)
    FS.record("c", ["AAA"], db=db)
    assert db["c"].docs["AAA"]["first_seen"] == first
    assert db["c"].docs["AAA"]["last_seen"] > first


def test_NEGATIVE_an_unreachable_db_badges_NOTHING_and_never_raises():
    """A board must still render when the ledger is down — it simply badges
    nothing. An exception here would take out the whole tab."""
    class _Boom:
        def __getitem__(self, name):
            raise RuntimeError("mongo down")
    assert FS.record("c", ["AAA"], db=_Boom()) == 0
    assert FS.newly_found("c", db=_Boom()) == set()
    assert FS.first_seen_map("c", ["AAA"], db=_Boom()) == {}


def test_windows_out_older_arrivals():
    db = _DB()
    FS.record("c", ["OLD"], db=db)
    time.sleep(0.01)
    FS.record("c", ["NEW"], db=db)
    assert FS.newly_found("c", days=30, db=db) == {"NEW"}
    # A zero-length window admits nothing: the cut is now, and `>` is strict.
    assert FS.newly_found("c", days=0, db=db) == set()


def test_first_seen_map_answers_only_for_the_symbols_asked():
    db = _DB()
    FS.record("c", ["AAA", "BBB"], db=db)
    m = FS.first_seen_map("c", ["AAA"], db=db)
    assert set(m) == {"AAA"} and m["AAA"]


def test_the_two_implementations_BEHAVE_IDENTICALLY():
    """DRIFT GUARD. `growth/tracker.py` predates this module and keeps its own
    copy; same inputs must give the same answer, or the ✨ badge means one thing
    on the Explosive Growth board and another on the Bonde board."""
    from growth import tracker as T

    db_a, db_b = _DB(), _DB()
    FS.record(T.SEEN_COLL, ["AAA", "BBB"], db=db_a)
    T._record_seen([{"symbol": "AAA"}, {"symbol": "BBB"}], db=db_b)
    assert FS.newly_found(T.SEEN_COLL, days=30, db=db_a) == T.newly_found(days=30, db=db_b)

    time.sleep(0.01)
    FS.record(T.SEEN_COLL, ["AAA", "BBB", "CCC"], db=db_a)
    T._record_seen([{"symbol": "AAA"}, {"symbol": "BBB"}, {"symbol": "CCC"}], db=db_b)
    assert FS.newly_found(T.SEEN_COLL, days=30, db=db_a) == {"CCC"}
    assert T.newly_found(days=30, db=db_b) == {"CCC"}
