"""Test-session isolation.

WHY THIS FILE EXISTS (2026-08-17)
--------------------------------
It didn't, and the suite was talking to the LIVE database.

Every Mongo-backed module here resolves its connection from `MONGO_URL` at call
time, defaulting to a reachable host. Inside the api container that default IS
production. Nothing in the suite overrode it, so any test that reached a real
write path wrote real rows — and the day this was found, a fresh
`demand_reentry.scan()` recording hook did exactly that: fixture symbols AAA,
BBB and GOOD, plus two runs for universe "Test", landed in the live
`demand_board_runs` / `demand_episodes` collections on the first full run of
`pytest`.

That is the same defect that had just been fixed one module over, where 5,371
simulated `zone_backtest` rows were being served from the pattern ledger as if
they were live observations. Simulated data in a live ledger is not a cosmetic
problem: it is published on a page as a track record.

The guard REPLACES `pymongo.MongoClient` rather than pointing `MONGO_URL` at a
dead address. Both block the writes; only this one is free. Redirecting the URL
was measured first and cost the suite 44s -> 109s, because pymongo keeps
retrying a refused socket for the whole `serverSelectionTimeoutMS` window on
every single call. Raising at construction is instant, and every `_coll()` /
`_db()` helper in this codebase already catches a construction failure and
returns None — the documented "no mongo" path each module handles. So the guard
needs no per-module cooperation.

`MONGO_URL` is redirected as well, for the belt-and-braces case of a module
that builds a client through some other import path.

A test that genuinely wants to exercise a Mongo path monkeypatches the module's
own accessor with an in-memory stand-in (see `tests/test_demand_history.py`),
which is faster and more precise than a live database anyway.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True, scope="session")
def _never_touch_a_real_database():
    import os
    prior = {k: os.environ.get(k) for k in ("MONGO_URL", "MONGO_DB")}
    os.environ["MONGO_URL"] = "mongodb://mongo.disabled-in-tests.invalid:27017"
    os.environ["MONGO_DB"] = "cheetah_test_should_never_exist"

    try:
        import pymongo
    except Exception:                             # pragma: no cover
        pymongo = None

    real = getattr(pymongo, "MongoClient", None) if pymongo else None
    if real is not None:
        def _refuse(*a, **k):
            raise RuntimeError(
                "MongoClient is disabled during tests (tests/conftest.py). "
                "Patch the module's own _coll()/_db() with an in-memory "
                "stand-in instead — see tests/test_demand_history.py.")
        pymongo.MongoClient = _refuse

    yield

    if real is not None:
        pymongo.MongoClient = real
    for k, v in prior.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
