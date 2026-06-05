"""Insider result cache — behavioral (2026-06-05).

Broad cluster-buy coverage requires caching insider_activity so a scan doesn't
re-hit EDGAR for hundreds of names every run. Verifies the Mongo-backed wrapper:
a fresh entry is served without refetching, a stale one (TTL) refetches, and a
missing DB degrades to compute-every-time. The Mongo collection + the EDGAR
fetch are both faked, so no network/DB needed.
"""
import asyncio

from sepa import insider


class _FakeColl:
    """Minimal dict-backed stand-in for the Mongo insider_cache collection."""
    def __init__(self):
        self.store = {}

    def find_one(self, q):
        doc = self.store.get(q["_id"])
        return dict(doc) if doc else None

    def update_one(self, q, upd, upsert=False):
        self.store[q["_id"]] = dict(upd["$set"])


def _patch(monkeypatch, fetch, coll):
    """Wire a fake EDGAR fetch (counting calls) + a fake collection."""
    calls = {"n": 0}

    async def _fetch(sym):
        calls["n"] += 1
        return fetch(sym, calls["n"])

    monkeypatch.setattr(insider, "insider_activity", _fetch)
    monkeypatch.setattr(insider, "_insider_coll", lambda: coll)
    return calls


def test_fresh_cache_hit_skips_refetch(monkeypatch):
    coll = _FakeColl()
    calls = _patch(monkeypatch, lambda sym, n: {"symbol": sym, "form4_cluster_buy": True, "resolved_cik": "X"}, coll)
    d1 = asyncio.run(insider.insider_activity_cached("aaa"))
    d2 = asyncio.run(insider.insider_activity_cached("AAA"))   # case-folded to the same key
    assert calls["n"] == 1                          # second call served from cache
    assert d1["form4_cluster_buy"] is True and d2["form4_cluster_buy"] is True
    assert "computed_at" not in d2 and "_id" not in d2          # internal fields stripped
    assert "AAA" in coll.store                                  # stored upper-cased


def test_stale_entry_refetches(monkeypatch):
    coll = _FakeColl()
    calls = _patch(monkeypatch, lambda sym, n: {"symbol": sym, "v": n}, coll)
    monkeypatch.setattr(insider, "_INSIDER_TTL_SEC", 0)         # everything instantly stale
    asyncio.run(insider.insider_activity_cached("BBB"))
    second = asyncio.run(insider.insider_activity_cached("BBB"))
    assert calls["n"] == 2                          # TTL=0 → always refetch
    assert second["v"] == 2                          # fresh value, not the cached one


def test_no_mongo_still_returns_data(monkeypatch):
    """Cache off (no collection) must not break — just compute every time."""
    calls = _patch(monkeypatch, lambda sym, n: {"symbol": sym, "ok": True}, None)
    d = asyncio.run(insider.insider_activity_cached("CCC"))
    assert d["ok"] is True and calls["n"] == 1
