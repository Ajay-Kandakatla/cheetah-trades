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
