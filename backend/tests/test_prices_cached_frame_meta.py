"""sepa.prices.cached_frame_meta — the ADDITIVE read Luk's trust rule needs (🥇 Luk's tab, 2026-11-01, spec C2).

The house price cache doc is {symbol, cached_at, bars}; `_mongo_get` hides `cached_at` and cuts at the 20 h TTL.
`cached_frame_meta` returns the frame (the two house cuts applied) AND `cached_at`, with NO TTL cut, never fetches and
never writes. `_mongo_get` / `load_prices` keep their behaviour (pinned here and by the existing test_prices* files).
"""
from __future__ import annotations

import time

import pandas as pd
import pytest

from sepa import prices as P


def _bars(n=5, last="2026-10-30", phantom=False):
    idx = pd.bdate_range(end=pd.Timestamp(last), periods=n)
    out = [{"date": ts.to_pydatetime(), "open": 10.0 + i, "high": 10.5 + i, "low": 9.5 + i, "close": 10.2 + i,
            "volume": 1e6 + i} for i, ts in enumerate(idx)]
    if phantom:
        nxt = (idx[-1] + pd.offsets.BDay(1)).to_pydatetime()
        out.append(dict(out[-1], date=nxt))
    return out


class _Coll:
    """price_cache stand-in: find_one only; any write is recorded (and must never happen)."""

    def __init__(self, docs=None, fail=False):
        self.docs = {d["symbol"]: d for d in docs or []}
        self.fail = fail
        self.writes = []

    def find_one(self, q):
        if self.fail:
            raise RuntimeError("mongo down")
        return self.docs.get(q.get("symbol"))

    def __getattr__(self, name):
        if name in ("update_one", "replace_one", "insert_one", "delete_one", "update_many", "bulk_write"):
            return lambda *a, **k: self.writes.append(name)
        raise AttributeError(name)


@pytest.fixture
def no_fetch(monkeypatch):
    calls = []

    def _spy(*a, **k):
        calls.append(a)
        raise AssertionError("cached_frame_meta must never fetch")

    monkeypatch.setattr(P, "_fetch", _spy)
    return calls


def test_returns_frame_and_cached_at(monkeypatch, no_fetch):
    coll = _Coll([{"symbol": "AAA", "cached_at": 1_790_000_000, "bars": _bars()}])
    monkeypatch.setattr(P, "_get_mongo", lambda: coll)
    got = P.cached_frame_meta("aaa")
    assert set(got) == {"frame", "cached_at"}
    assert got["cached_at"] == 1_790_000_000.0 and isinstance(got["cached_at"], float)
    df = got["frame"]
    assert list(df.columns) == ["open", "high", "low", "close", "volume"] and len(df) == 5
    assert isinstance(df.index, pd.DatetimeIndex)
    assert no_fetch == [] and coll.writes == []


def test_NO_ttl_cut_where_mongo_get_cuts(monkeypatch, no_fetch):
    old = time.time() - P.CACHE_TTL_SEC - 60
    coll = _Coll([{"symbol": "AAA", "cached_at": old, "bars": _bars()}])
    monkeypatch.setattr(P, "_get_mongo", lambda: coll)
    assert P._mongo_get("AAA") is None, "_mongo_get keeps its TTL cut (unchanged)"
    got = P.cached_frame_meta("AAA")
    assert got is not None and got["cached_at"] == pytest.approx(old)


def test_applies_both_house_cuts(monkeypatch, no_fetch):
    seen = []
    real_cut, real_tail = P._cut_foreign_head, P._drop_phantom_tail
    monkeypatch.setattr(P, "_cut_foreign_head", lambda df, sym: (seen.append(("cut", sym)), real_cut(df, sym))[1])
    monkeypatch.setattr(P, "_drop_phantom_tail", lambda df: (seen.append(("tail",)), real_tail(df))[1])
    coll = _Coll([{"symbol": "AAA", "cached_at": 1_790_000_000, "bars": _bars(phantom=True)}])
    monkeypatch.setattr(P, "_get_mongo", lambda: coll)
    got = P.cached_frame_meta("AAA")
    assert seen == [("cut", "AAA"), ("tail",)]
    assert len(got["frame"]) == 5, "the phantom duplicate tail is dropped"


@pytest.mark.parametrize("docs,fail", [
    ([], False),                                                           # absent
    ([{"symbol": "AAA", "cached_at": 1_790_000_000, "bars": []}], False),   # empty bars
    ([{"symbol": "AAA", "bars": _bars()}], False),                         # no cached_at
    ([{"symbol": "AAA", "cached_at": "x", "bars": _bars()}], False),       # junk cached_at
    ([{"symbol": "AAA", "cached_at": 1_790_000_000, "bars": _bars()}], True),   # find raises
])
def test_NEGATIVE_none_on_absent_empty_or_fault(monkeypatch, no_fetch, docs, fail):
    coll = _Coll(docs, fail=fail)
    monkeypatch.setattr(P, "_get_mongo", lambda: coll)
    assert P.cached_frame_meta("AAA") is None
    assert no_fetch == [] and coll.writes == []


def test_NEGATIVE_none_when_mongo_is_down(monkeypatch, no_fetch):
    monkeypatch.setattr(P, "_get_mongo", lambda: None)
    assert P.cached_frame_meta("AAA") is None
    assert P.cached_frame_meta("") is None
    assert no_fetch == []


def test_load_prices_and_mongo_get_behave_as_before(monkeypatch):
    """The cache hit path of load_prices is untouched: a fresh doc → served from the cache, no fetch, no write."""
    coll = _Coll([{"symbol": "AAA", "cached_at": time.time() - 60, "bars": _bars()}])
    monkeypatch.setattr(P, "_get_mongo", lambda: coll)
    fetched = []
    monkeypatch.setattr(P, "_fetch", lambda *a, **k: fetched.append(a))
    df = P.load_prices("AAA", "1y")
    assert df is not None and len(df) == 5 and fetched == [] and coll.writes == []
    assert P._mongo_get("AAA") is not None
