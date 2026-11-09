"""GG LIVE WP-A (spec §3.1, C11 — a DECLARED QuoteCache change, 2026-11-09): the Mongo persist of the latest quote
per symbol left the awaited per-trade path. `QuoteCache.update` parks the merged doc (latest wins); ONE drain task
writes it every LIVE_CACHE_PERSIST_SEC off the event loop. Payload, lock, indicators, `quote.update` and the restart
re-seed are unchanged.

`QuoteCache` and the lifespan are compiled straight out of main.py (the host venv cannot import main.py whole — the
same way test_scan_offloop_2026_09_30 does it).
"""
from __future__ import annotations

import ast
import asyncio
import json
import logging
import os
import threading
import time
from collections import deque
from pathlib import Path

import pytest

import live_feed

MAIN_SRC = (Path(__file__).resolve().parents[1] / "main.py").read_text()
TREE = ast.parse(MAIN_SRC)


class _Coll:
    """live_quote_cache stand-in: upserts by symbol; a slow write sleeps (the Mongo latency the read loop must not
    wait on)."""

    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.docs: dict = {}
        self.writes = []
        self.lock = threading.Lock()

    def update_one(self, flt, upd, upsert=False):
        if self.delay:
            time.sleep(self.delay)
        with self.lock:
            sym = flt["symbol"]
            self.writes.append((sym, dict(upd["$set"])))
            self.docs[sym] = {**self.docs.get(sym, {}), **upd["$set"], "symbol": sym}

    def find(self, _q):
        return [dict(d, _id=i) for i, d in enumerate(self.docs.values())]


def _ns(coll):
    names_fn = {"rsi_wilder", "vwap"}
    names_assign = {"TICK_WINDOW", "LIVE_CACHE_PERSIST_SEC"}
    body = []
    for n in TREE.body:
        if isinstance(n, ast.FunctionDef) and n.name in names_fn:
            body.append(n)
        elif isinstance(n, ast.ClassDef) and n.name == "QuoteCache":
            body.append(n)
        elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names_assign for t in n.targets):
            body.append(n)
    ns = {"asyncio": asyncio, "time": time, "deque": deque, "os": os, "log": logging.getLogger("t"),
          "_live_cache_mongo": lambda: coll, "Optional": None}
    exec(compile(ast.Module(body=body, type_ignores=[]), "main.py", "exec"), ns)
    return ns


@pytest.fixture(autouse=True)
def _quiet_bus(monkeypatch):
    import events
    pubs = []
    monkeypatch.setattr(events, "publish_throttled", lambda *a, **k: pubs.append((a, k)))
    return pubs


def test_persist_constant_is_one_second():
    assert _ns(_Coll())["LIVE_CACHE_PERSIST_SEC"] == 1.0


def test_NEG_update_has_no_awaited_mongo_call():
    cls = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "QuoteCache")
    upd = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "update")
    src = ast.get_source_segment(MAIN_SRC, upd)
    assert "update_one" not in src and "to_thread" not in src and "_live_cache_mongo" not in src


def test_read_loop_never_waits_on_a_slow_persist():
    coll = _Coll(delay=0.5)
    ns = _ns(coll)

    async def go():
        cache = ns["QuoteCache"]()
        frames = [json.dumps([{"ev": "T", "sym": "AAA", "p": 1.0 + i / 100, "s": 10}]) for i in range(200)]
        t0 = time.perf_counter()
        for f in frames:
            await live_feed._handle(f, cache, {"AAA"})
        return time.perf_counter() - t0, cache

    took, cache = asyncio.run(go())
    assert took < 0.5, f"200 trades took {took:.3f}s — the read loop waited on Mongo"
    assert coll.writes == []                                      # nothing written until the drain runs
    assert cache._persist_pending["AAA"]["price"] == pytest.approx(2.99)


def test_drain_writes_the_last_doc_per_symbol_once():
    coll = _Coll()
    ns = _ns(coll)

    async def go():
        cache = ns["QuoteCache"]()
        for p in (1.0, 2.0, 3.0):
            await cache.update("AAA", {"price": p, "volume": 1})
        await cache.update("BBB", {"price": 5.0, "volume": 1})
        n1 = await cache.flush_persist()
        n2 = await cache.flush_persist()                          # NEG: nothing pending → no write
        return n1, n2

    n1, n2 = asyncio.run(go())
    assert (n1, n2) == (2, 0)
    assert [w[0] for w in coll.writes] == ["AAA", "BBB"]
    assert coll.docs["AAA"]["price"] == 3.0 and "_persisted_at" in coll.docs["AAA"]


def test_the_drain_task_runs_on_its_interval():
    coll = _Coll()
    ns = _ns(coll)

    async def go():
        cache = ns["QuoteCache"]()
        task = asyncio.create_task(cache.persist_drain(interval=0.05))
        await cache.update("AAA", {"price": 1.0})
        await cache.update("AAA", {"price": 1.5})
        await asyncio.sleep(0.12)
        await cache.update("AAA", {"price": 2.0})
        await asyncio.sleep(0.12)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(go())
    prices = [w[1]["price"] for w in coll.writes]
    assert prices == [1.5, 2.0]                                   # coalesced: one write per symbol per drain


def test_NEG_restart_reseed_reads_every_symbol_the_drain_wrote():
    coll = _Coll()
    ns = _ns(coll)

    async def go():
        a = ns["QuoteCache"]()
        await a.update("AAA", {"price": 1.0})
        await a.update("BBB", {"price": 2.0})
        await a.update("AAA", {"price": 1.1})
        await a.flush_persist()
        b = ns["QuoteCache"]()                                    # a restart
        n = await b.hydrate_from_mongo()
        return n, await b.snapshot()

    n, snap = asyncio.run(go())
    assert n == 2 and set(snap) == {"AAA", "BBB"}
    assert snap["AAA"]["price"] == 1.1 and snap["BBB"]["price"] == 2.0


def test_NEG_no_mongo_drops_the_batch_quietly():
    ns = _ns(None)

    async def go():
        c = ns["QuoteCache"]()
        await c.update("AAA", {"price": 1.0})
        return await c.flush_persist(), c._persist_pending

    n, pending = asyncio.run(go())
    assert n == 0 and pending == {}


def test_payload_indicators_and_quote_update_unchanged(_quiet_bus):
    ns = _ns(_Coll())

    async def go():
        c = ns["QuoteCache"]()
        await c.update("AAA", {"price": 1.0, "volume": 10})
        return await c.update("AAA", {"price": 1.2, "volume": 10})

    merged = asyncio.run(go())
    for k in ("rsi14", "vwap", "sparkline", "change", "symbol", "ts"):
        assert k in merged
    args, kw = _quiet_bus[-1]
    assert args[0] == "quote.update" and args[1] == "AAA" and kw == {"min_interval_s": 0.5}
    assert set(args[2]) == {"symbol", "price", "change", "open", "high", "low", "prev_close", "source", "ts"}


# ── the lifespan wiring (source-level: main.py cannot be imported on the host) ────────────────────────────────
def _lifespan_src() -> str:
    fn = next(n for n in TREE.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "lifespan")
    return ast.get_source_segment(MAIN_SRC, fn)


def test_lifespan_starts_the_drain_and_the_hub_only_with_the_massive_feed():
    src = _lifespan_src()
    assert "cache.persist_drain()" in src
    massive = src.split("if live_feed.enabled():", 1)[1].split("elif _finnhub_poller_enabled():", 1)[0]
    assert "live_hub.run()" in massive
    assert "live_feed.set_views(tracked_symbols, live_hub.watched, _ws_subscribe_queue)" in massive
    assert massive.index("set_views") < massive.index("massive_ws_consumer") < massive.index("live_hub.run()")
    tail = src.split("elif _finnhub_poller_enabled():", 1)[1]
    assert "live_hub" not in tail                                  # NEG: never on the Finnhub path
