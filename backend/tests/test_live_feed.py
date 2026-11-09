"""Contracts for the Massive real-time WebSocket feed (``backend/live_feed.py``).

Pure-logic — no network. Locks the wire behaviour that the live-quote cache
(and therefore every price on the SEPA cards) depends on:

  - the feed turns on only when a stocks key exists (``auto``) or is forced;
  - a trade event maps to a live ``price`` tagged ``massive_ws``;
  - the snapshot poller backfills the day frame but NEVER writes ``price``
    (so it can't clobber the live tick);
  - subscribe frames use the Polygon ``CHANNEL.SYMBOL`` param shape.
"""
from __future__ import annotations

import asyncio
import json

import live_feed


def _run(coro):
    return asyncio.run(coro)


class _FakeWS:
    def __init__(self):
        self.sent = []

    async def send(self, msg):
        self.sent.append(json.loads(msg))


class _FakeCache:
    def __init__(self):
        self.calls = []

    async def update(self, sym, payload):
        self.calls.append((sym, dict(payload)))
        return payload


# ── enable gate ──────────────────────────────────────────────────────────

def test_enabled_explicit_off_on(monkeypatch):
    monkeypatch.setenv("MASSIVE_WS_ENABLED", "false")
    assert live_feed.enabled() is False
    monkeypatch.setenv("MASSIVE_WS_ENABLED", "true")
    assert live_feed.enabled() is True


def test_enabled_auto_follows_stocks_key(monkeypatch):
    monkeypatch.setenv("MASSIVE_WS_ENABLED", "auto")
    monkeypatch.delenv("MASSIVE_API_KEY_STOCKS", raising=False)
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    assert live_feed.enabled() is False
    monkeypatch.setenv("MASSIVE_API_KEY_STOCKS", "k")
    assert live_feed.enabled() is True


# ── subscribe frame shape ────────────────────────────────────────────────

def test_subscribe_frame_uses_channel_dot_symbol():
    ws = _FakeWS()
    _run(live_feed._subscribe(ws, ["AAPL", "MSFT"]))
    assert ws.sent == [{"action": "subscribe", "params": "T.AAPL,T.MSFT"}]


def test_subscribe_empty_sends_nothing():
    ws = _FakeWS()
    _run(live_feed._subscribe(ws, []))
    assert ws.sent == []


# ── trade / status handling ──────────────────────────────────────────────

def test_handle_trade_sets_live_price():
    cache = _FakeCache()
    _run(live_feed._handle(json.dumps([{"ev": "T", "sym": "AAPL", "p": 306.5, "s": 100, "t": 123}]), cache))
    assert len(cache.calls) == 1
    sym, payload = cache.calls[0]
    assert sym == "AAPL"
    assert payload["price"] == 306.5
    assert payload["volume"] == 100
    assert payload["source"] == "massive_ws"
    assert payload["trade_ts"] == 123


def test_handle_skips_trade_without_price():
    cache = _FakeCache()
    _run(live_feed._handle(json.dumps([{"ev": "T", "sym": "AAPL"}]), cache))
    assert cache.calls == []


def test_handle_ignores_non_list_frame():
    cache = _FakeCache()
    _run(live_feed._handle("{}", cache))
    _run(live_feed._handle("not json", cache))
    assert cache.calls == []


def test_handle_status_auth_success_sets_flag():
    live_feed.feed_state["authed"] = False
    _run(live_feed._handle(json.dumps([{"ev": "status", "status": "auth_success"}]), _FakeCache()))
    assert live_feed.feed_state["authed"] is True


# ── snapshot poller never clobbers the live price ────────────────────────

def test_snapshot_backfills_day_frame_without_price():
    cache = _FakeCache()

    def fake_bulk(_syms):
        return {
            "AAPL": {
                "open": 1.0, "high": 2.0, "low": 0.5, "volume": 1000,
                "prev_day_close": 1.2, "change_pct": 3.4, "vwap": 1.1,
                "close": 1.5,  # present but must NOT be forwarded as price
            }
        }

    async def go():
        t = asyncio.create_task(live_feed.massive_snapshot_poller(cache, {"AAPL"}, fake_bulk))
        await asyncio.sleep(0.2)  # let the first iteration run
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass

    _run(go())
    assert cache.calls, "snapshot should have updated AAPL"
    sym, payload = cache.calls[-1]
    assert sym == "AAPL"
    # The cardinal rule: the live WS tick owns `price`; the poller must not touch it.
    assert "price" not in payload
    assert "close" not in payload
    assert payload["prev_close"] == 1.2
    assert payload["open"] == 1.0
    assert payload["day_volume"] == 1000


# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# GG LIVE WP-A (2026-11-09, spec §3.1) — routing (hub listener FIRST, then tracked → cache) and the ONE ordered
# control queue. The tests above are unmodified; these isolate the module's run-time state per test.
# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════
import pytest  # noqa: E402


@pytest.fixture
def wpa(monkeypatch):
    monkeypatch.setattr(live_feed, "_listeners", [])
    monkeypatch.setattr(live_feed, "_views", {"tracked": None, "hub": None})
    monkeypatch.setattr(live_feed, "_queue", None)
    monkeypatch.setattr(live_feed, "_subscribed_t", set())
    monkeypatch.setattr(live_feed, "_events_coll", lambda: None)
    yield


class _OrderCache(_FakeCache):
    def __init__(self, order):
        super().__init__()
        self.order = order

    async def update(self, sym, payload):
        self.order.append(("cache", sym))
        return await super().update(sym, payload)


def _t(sym, p=1.5, c=None, t=None):
    e = {"ev": "T", "sym": sym, "p": p, "s": 100}
    if c is not None:
        e["c"] = c
    if t is not None:
        e["t"] = t
    return e


def test_wpa_hub_only_symbol_goes_to_the_listener_and_never_to_the_cache(wpa):
    got = []
    live_feed.add_listener(got.append)
    live_feed.set_views(set(), lambda: {"HUBX"})
    cache = _FakeCache()
    _run(live_feed._handle(json.dumps([_t("HUBX", c=[37], t=123)]), cache, set()))
    assert len(got) == 1 and cache.calls == []
    pr = got[0]
    assert set(pr) == {"sym", "p", "s", "c", "t_ms", "recv", "trfi"}
    assert pr["sym"] == "HUBX" and pr["c"] == [37] and pr["t_ms"] == 123 and pr["trfi"] is False


def test_wpa_tracked_symbol_updates_the_cache_with_todays_payload(wpa):
    got = []
    live_feed.add_listener(got.append)
    live_feed.set_views({"AAPL"}, lambda: set())
    cache = _FakeCache()
    _run(live_feed._handle(json.dumps([{"ev": "T", "sym": "AAPL", "p": 306.5, "s": 100, "t": 123}]), cache, {"AAPL"}))
    assert got == []
    assert cache.calls == [("AAPL", {"price": 306.5, "volume": 100, "source": "massive_ws", "trade_ts": 123})]


def test_wpa_both_routes_call_the_listener_before_the_cache(wpa):
    order = []
    live_feed.add_listener(lambda pr: order.append(("hub", pr["sym"])))
    live_feed.set_views({"BOTH"}, lambda: {"BOTH"})
    _run(live_feed._handle(json.dumps([_t("BOTH")]), _OrderCache(order), {"BOTH"}))
    assert order == [("hub", "BOTH"), ("cache", "BOTH")]


def test_wpa_NEG_no_tracked_argument_is_todays_behaviour(wpa):
    got = []
    live_feed.add_listener(got.append)
    live_feed.set_views(set(), lambda: {"ANY"})
    cache = _FakeCache()
    _run(live_feed._handle(json.dumps([_t("ANY"), _t("OTHER")]), cache))
    assert [c[0] for c in cache.calls] == ["ANY", "OTHER"]       # every T → cache, as before
    assert got == []


def test_wpa_NEG_untracked_and_unwatched_print_is_dropped(wpa):
    got = []
    live_feed.add_listener(got.append)
    live_feed.set_views({"AAPL"}, lambda: {"HUBX"})
    cache = _FakeCache()
    _run(live_feed._handle(json.dumps([_t("NOPE")]), cache, {"AAPL"}))
    assert got == [] and cache.calls == []


def test_wpa_NEG_a_raising_listener_never_stops_the_read_loop(wpa):
    def boom(pr):
        raise RuntimeError("consumer bug")

    live_feed.add_listener(boom)
    live_feed.set_views({"BOTH"}, lambda: {"BOTH"})
    cache = _FakeCache()
    _run(live_feed._handle(json.dumps([_t("BOTH", p=1.0), _t("BOTH", p=2.0)]), cache, {"BOTH"}))
    assert [c[1]["price"] for c in cache.calls] == [1.0, 2.0]


class _Q:
    """put_nowait recorder (the asyncio.Queue surface watch/unwatch use)."""

    def __init__(self):
        self.items = []

    def put_nowait(self, x):
        self.items.append(x)


def _drain(ws, items, tracked):
    out = []
    for it in items:
        out.append(_run(live_feed._send_control(ws, it, tracked)))
    return out


def test_wpa_watch_sends_one_subscribe_frame_per_new_symbol(wpa):
    q = _Q()
    live_feed.set_views(set(), lambda: {"AAA", "BBB"}, q)
    assert live_feed.watch(["aaa", " BBB ", "AAA"]) == 2
    assert q.items == [("sub", "AAA"), ("sub", "BBB")]
    ws = _FakeWS()
    _drain(ws, q.items + [("sub", "AAA")], set())
    assert ws.sent == [{"action": "subscribe", "params": "T.AAA"}, {"action": "subscribe", "params": "T.BBB"}]


def test_wpa_NEG_unwatch_of_a_tracked_symbol_sends_no_unsubscribe(wpa):
    q = _Q()
    live_feed.set_views({"UI1"}, lambda: set(), q)
    live_feed._subscribed_t.add("UI1")
    assert live_feed.unwatch(["UI1"]) == 1
    ws = _FakeWS()
    assert _drain(ws, q.items, {"UI1"}) == [None]
    assert ws.sent == [] and "UI1" in live_feed._subscribed_t


def test_wpa_unwatch_of_a_hub_only_symbol_unsubscribes(wpa):
    live_feed.set_views(set(), lambda: set())
    live_feed._subscribed_t.add("GONE")
    ws = _FakeWS()
    assert _drain(ws, [("unsub", "GONE")], set()) == ["unsubscribe"]
    assert ws.sent == [{"action": "unsubscribe", "params": "T.GONE"}]
    assert "GONE" not in live_feed._subscribed_t


def test_wpa_NEG_unwatch_of_a_symbol_the_hub_still_watches_is_dropped(wpa):
    live_feed.set_views(set(), lambda: {"KEEP"})
    live_feed._subscribed_t.add("KEEP")
    ws = _FakeWS()
    assert _drain(ws, [("unsub", "KEEP")], set()) == [None] and ws.sent == []


def test_wpa_NEG_race_hub_unsub_then_ui_subscribe_keeps_the_ui_price(wpa):
    q = _Q()
    tracked = set()
    live_feed.set_views(tracked, lambda: set(), q)
    live_feed._subscribed_t.add("X")
    live_feed.unwatch(["X"])                      # the hub drops X …
    tracked.add("X")                              # … then the UI subscribes X (main.subscribe_symbols)
    q.put_nowait("X")
    ws = _FakeWS()
    _drain(ws, q.items, tracked)
    assert ws.sent == [{"action": "subscribe", "params": "T.X"}]       # the unsub re-checked tracked at SEND time
    assert "X" in live_feed._subscribed_t


def test_wpa_str_items_still_subscribe_like_today(wpa):
    ws = _FakeWS()
    live_feed._subscribed_t.add("AAPL")
    assert _drain(ws, ["AAPL"], {"AAPL"}) == ["subscribe"]               # always sent, as before
    assert ws.sent == [{"action": "subscribe", "params": "T.AAPL"}]


def test_wpa_NEG_watch_before_the_queue_exists_is_a_no_op(wpa):
    assert live_feed.watch(["AAA"]) == 0 and live_feed.unwatch(["AAA"]) == 0


def test_wpa_reconnect_subscribes_tracked_union_hub_exactly_once_each(wpa, monkeypatch):
    class _Conn:
        def __init__(self):
            self.sent = []
            self.auth = [json.dumps([{"ev": "status", "status": "auth_success"}])]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def send(self, m):
            self.sent.append(json.loads(m))

        async def recv(self):
            return self.auth.pop(0)

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise RuntimeError("dropped")

    class _Stop(BaseException):
        pass

    conn = _Conn()

    async def stop(_s):
        raise _Stop()

    monkeypatch.setenv("MASSIVE_API_KEY_STOCKS", "k")
    monkeypatch.setattr(live_feed.websockets, "connect", lambda url, **kw: conn)
    monkeypatch.setattr(live_feed, "_sleep", stop)
    live_feed.set_views({"A", "B"}, lambda: {"B", "C"})

    async def go():
        try:
            await live_feed.massive_ws_consumer(_FakeCache(), {"A", "B"}, asyncio.Queue())
        except _Stop:
            pass

    _run(go())
    subs = [m for m in conn.sent if m.get("action") == "subscribe"]
    assert subs == [{"action": "subscribe", "params": "T.A,T.B,T.C"}]
    assert live_feed._subscribed_t == {"A", "B", "C"}
