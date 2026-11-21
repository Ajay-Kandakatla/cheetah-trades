"""`sepa.volume_movers.shares_status(…, coll=…)` — a caller's long-lived handle (2026-11-21, spec watchfloat §3.1, C3).

Ajay 2026-11-21, verbatim: "can you add the current float value also to the tickers on the watch list."

The 👀 Watch float reads the cache through the store's process-wide handle so a Watch GET opens ZERO new MongoClients.
`coll=None` is today's path exactly (`_shares_coll()`). NEGATIVES: a handle never touches `_shares_coll`; an expired
row with no fetch never fetches; a raising handle reads "missing" and never fetches.
"""
from __future__ import annotations

import time

import pytest

from sepa import volume_movers as VM
from tests.test_gajjala_store import FakeColl

VALS = {"shares_outstanding": 8_100_000, "float_shares": 3_100_000, "market_cap": 50_000_000}


def _row(age_sec, **kw):
    return dict({"_id": "OMH", **VALS, "as_of": int(time.time()) - age_sec}, **kw)


@pytest.fixture()
def traps(monkeypatch):
    hits = []

    def trap(name):
        def _t(*a, **k):
            hits.append(name)
            raise AssertionError(f"{name} must not run")
        return _t
    monkeypatch.setattr(VM, "_fetch_shares_status", trap("_fetch_shares_status"))
    monkeypatch.setattr(VM, "_fetch_shares_yf", trap("_fetch_shares_yf"))
    return hits


def test_the_collection_name_is_one_constant():
    assert VM.SHARES_COLL == "shares_cache"


def test_default_path_unchanged_reads_shares_coll_once(monkeypatch, traps):
    row = _row(3600)
    fake = FakeColl([row])
    calls = []
    monkeypatch.setattr(VM, "_shares_coll", lambda: calls.append(1) or fake)
    out = VM.shares_status("omh", fetch=False)
    assert out == (dict(VALS, as_of=row["as_of"]), "cached")
    assert calls == [1] and traps == []


def test_a_handle_gives_the_same_answer_and_never_opens_a_client(monkeypatch, traps):
    row = _row(3600)
    fake = FakeColl([row])
    opened = []
    monkeypatch.setattr(VM, "_shares_coll", lambda: opened.append(1) or FakeColl())
    out = VM.shares_status("OMH", fetch=False, coll=fake)
    assert out == (dict(VALS, as_of=row["as_of"]), "cached")
    assert opened == [] and traps == []                                # NEGATIVE: _shares_coll never touched


def test_NEGATIVE_expired_row_no_fetch_is_stale_and_never_fetches(monkeypatch, traps):
    monkeypatch.setattr(VM, "_shares_coll", lambda: (_ for _ in ()).throw(AssertionError("no client")))
    fake = FakeColl([_row(VM._SHARES_TTL_SEC + 60)])
    assert VM.shares_status("OMH", fetch=False, coll=fake) == (None, "stale")
    assert traps == [] and fake.writes == 0


def test_expired_row_under_a_429_marker_is_served_stale(monkeypatch, traps):
    row = _row(VM._SHARES_TTL_SEC + 60, rl_until=time.time() + 3600)
    fake = FakeColl([row])
    assert VM.shares_status("OMH", fetch=False, coll=fake) == (dict(VALS, as_of=row["as_of"]), "stale_served")
    assert traps == [] and fake.writes == 0


def test_NEGATIVE_a_raising_handle_reads_missing_and_never_fetches(monkeypatch, traps):
    opened = []
    monkeypatch.setattr(VM, "_shares_coll", lambda: opened.append(1) or FakeColl())
    assert VM.shares_status("OMH", fetch=False, coll=FakeColl([_row(60)], fail=True)) == (None, "missing")
    assert traps == [] and opened == []


def test_NEGATIVE_a_none_handle_is_todays_path(monkeypatch, traps):
    fake = FakeColl([_row(60)])
    calls = []
    monkeypatch.setattr(VM, "_shares_coll", lambda: calls.append(1) or fake)
    assert VM.shares_status("OMH", fetch=False, coll=None)[1] == "cached" and calls == [1]
