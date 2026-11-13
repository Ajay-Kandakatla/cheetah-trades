"""📅 Long Term — the store (spec §3.9, WP-RUN, 2026-11-12).

Ajay 2026-11-12, verbatim: "Save this entire list for me. In a New tab - Long Term - … keep updating it from all the
other tabs info.. Weekly …"

Runs and forward docs are INSERT ONLY; the claim insert is the dedupe. NEGATIVES: a duplicate week is never
overwritten; a "claimed"/"done" claim is never retaken; no store → None, never a raise.
"""
from __future__ import annotations

from datetime import date, datetime

from long_term_list import constants as C
from long_term_list import store as ST


class DuplicateKeyError(Exception):
    pass


class _Res:
    def __init__(self, n):
        self.modified_count = n


class FakeColl:
    def __init__(self, name="c"):
        self.name, self.docs, self.calls = name, {}, []

    def insert_one(self, doc):
        self.calls.append("insert_one")
        if doc["_id"] in self.docs:
            raise DuplicateKeyError(doc["_id"])
        self.docs[doc["_id"]] = dict(doc)

    def find(self, q=None):
        self.calls.append("find")
        return [dict(d) for d in self.docs.values()]

    def update_one(self, flt, upd):
        self.calls.append("update_one")
        d = self.docs.get(flt["_id"])
        if d is None or any(d.get(k) != v for k, v in flt.items() if k != "_id"):
            return _Res(0)
        d.update(upd["$set"])
        return _Res(1)


class Boom:
    def __getattr__(self, name):
        def _f(*a, **k):
            raise RuntimeError("mongo down")
        return _f


def test_iso_week_id():
    assert ST.iso_week_id(date(2026, 11, 13)) == "2026-W46"
    assert ST.iso_week_id("2026-11-13") == "2026-W46"
    assert ST.iso_week_id(datetime(2027, 1, 1, 17)) == "2026-W53"


def test_claim_once_then_held():
    c = FakeColl()
    assert ST.claim(c, "run:2026-W46", "t") is True
    assert ST.claim(c, "run:2026-W46", "t") is False               # NEG: the second claim never wins
    ST.set_claim(c, "run:2026-W46", "done")
    assert ST.claim(c, "run:2026-W46", "t") is False               # NEG: a done claim is never retaken


def test_a_failed_claim_is_retaken_once():
    c = FakeColl()
    ST.claim(c, "run:2026-W46", "t")
    ST.set_claim(c, "run:2026-W46", "failed", reason="boom")
    assert ST.claim(c, "run:2026-W46", "t2") is True
    assert c.docs["run:2026-W46"]["state"] == "claimed"
    assert ST.claim(c, "run:2026-W46", "t3") is False


def test_runs_are_insert_only_and_a_week_is_never_overwritten():
    r = FakeColl(C.RUNS_COLL)
    assert ST.insert_run(r, {"_id": "2026-W46", "v": 1}) is True
    assert ST.insert_run(r, {"_id": "2026-W46", "v": 2}) is False
    assert r.docs["2026-W46"]["v"] == 1
    ST.insert_run(r, {"_id": "2026-W47"})
    assert [d["_id"] for d in ST.runs_desc(r)] == ["2026-W47", "2026-W46"]
    assert set(r.calls) <= {"insert_one", "find"}                  # NEG: no update / replace / delete


def test_forward_base_frozen_once():
    f = FakeColl(C.FORWARD_COLL)
    assert ST.insert_forward(f, {"_id": "base", "session": "2026-11-13"}) is True
    assert ST.insert_forward(f, {"_id": "base", "session": "2026-11-20"}) is False
    assert f.docs["base"]["session"] == "2026-11-13"
    assert set(f.calls) <= {"insert_one", "find"}


def test_no_store_never_raises():
    assert ST.claim(None, "x", "t") is None
    assert ST.insert_run(None, {"_id": "x"}) is None
    assert ST.runs_desc(None) == [] and ST.forward_docs(None) == []
    assert ST.runs_desc(Boom()) == [] and ST.forward_docs(Boom()) == []
    assert ST.insert_run(Boom(), {"_id": "x"}) is None
    assert ST.claim(Boom(), "x", "t") is None
    assert ST.set_claim(Boom(), "x", "done") is False


def test_colls_resolve_the_three_names():
    db = {C.RUNS_COLL: 1, C.FORWARD_COLL: 2, C.CLAIMS_COLL: 3}
    assert ST.colls(db) == {"runs": 1, "forward": 2, "claims": 3}
    assert C.RUNS_COLL == "long_term_list_runs" and C.FORWARD_COLL == "long_term_list_forward"
    assert C.CLAIMS_COLL == "long_term_list_claims"


def test_db_unreachable_is_none(monkeypatch):
    from sepa import prices
    monkeypatch.setattr(prices, "_get_mongo", lambda: None)
    assert ST._db() is None and ST.colls() is None
