"""Events audience — WP-B `events-audience` (2026-11-16, 👀 Gajjala's Watch LIVE).

    Ajay 2026-11-16: "Can you make the watch list charts live please" ·
    "Realtime updates.. Like the 1 min chart I need it to be live live.. per
    sec change" · "Also on the Watch list I need live volume to be shown at
    the bottom" · "Of each chart".

The watch batches are his private list, so they ride the ONE bus with an
OWNER-ONLY `audience` tag and the ONE SSE consumer loop filters per
connection. What this file pins:

1. `events.publish(..., audience=...)` attaches a frozenset of lower-cased
   emails; an EMPTY set is still attached (fail closed). Untagged envelopes
   are exactly today's `{type, ts, payload}`.
2. `sse.audience_allows` — pure, fail closed on an empty audience, a missing
   email and a non-set value.
3. `sse._frame` never puts `audience` (or any email) on the wire; untagged
   bytes are byte-identical to today's.
4. Source guards: `maybe_current_user` (never raises) not `current_user_email`;
   the filter runs BEFORE `_frame`; `/events` is still NOT in main.py's public
   allowlists (the middleware stays the gate).
5. The route alone adds no gate: 200 `text/event-stream` with AND without
   `X-User-Email`. Starlette 0.41's TestClient runs the app to completion
   before returning headers, and `/events` never completes, so the route is
   driven at the ASGI level: capture `http.response.start`, then hand the app
   `http.disconnect` — the infinite body is never iterated.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import events                                         # noqa: E402
from events import bus, sse                           # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolated_bus():
    """Each test gets an empty bus and no cached loop; the originals come back."""
    saved = (set(bus._subscribers), bus._loop, dict(bus._last_publish_ts))
    bus._subscribers.clear()
    bus._loop = None
    bus._last_publish_ts.clear()
    yield
    bus._subscribers.clear()
    bus._subscribers.update(saved[0])
    bus._loop = saved[1]
    bus._last_publish_ts.clear()
    bus._last_publish_ts.update(saved[2])


def _published(*calls):
    """Run `calls` (fn, args, kwargs) on a fresh loop with one subscriber;
    return every envelope that reached its queue."""
    async def go():
        q = bus.subscribe()
        for fn, args, kwargs in calls:
            fn(*args, **kwargs)
        out = []
        while not q.empty():
            out.append(q.get_nowait())
        return out
    try:
        return asyncio.run(go())
    finally:
        bus._loop = None


# ── 1. publish ──────────────────────────────────────────────────────────────
def test_untagged_envelope_has_exactly_todays_keys():
    (env,) = _published((bus.publish, ("t", {"a": 1}), {}))
    assert set(env) == {"type", "ts", "payload"}
    assert "audience" not in env
    assert env["type"] == "t" and env["payload"] == {"a": 1}


def test_audience_none_is_untagged():
    (env,) = _published((bus.publish, ("t", {"a": 1}), {"audience": None}))
    assert "audience" not in env


def test_audience_is_lowercased_stripped_frozenset():
    (env,) = _published((bus.publish, ("t", {}), {"audience": ["A@x.COM ", "b@y"]}))
    assert env["audience"] == frozenset({"a@x.com", "b@y"})
    assert isinstance(env["audience"], frozenset)


@pytest.mark.parametrize("aud", [[], [""], [None], ["   "], [None, "", 7]])
def test_NEGATIVE_empty_or_junk_audience_attaches_empty_set_fail_closed(aud):
    (env,) = _published((bus.publish, ("t", {}), {"audience": aud}))
    assert "audience" in env
    assert env["audience"] == frozenset()


def test_NEGATIVE_audience_is_keyword_only():
    with pytest.raises(TypeError):
        bus.publish("t", {}, ["a@x"])                 # positional → refused


def test_package_reexport_carries_the_keyword():
    assert events.publish is bus.publish
    (env,) = _published((events.publish, ("t", {}), {"audience": ["O@X"]}))
    assert env["audience"] == frozenset({"o@x"})


def test_publish_throttled_passes_audience_through():
    (env,) = _published((bus.publish_throttled, ("t", "k", {"p": 1}),
                         {"audience": ["Owner@X"], "min_interval_s": 60}))
    assert env["audience"] == frozenset({"owner@x"})


def test_publish_throttled_untagged_stays_untagged():
    (env,) = _published((bus.publish_throttled, ("t", "k", {"p": 1}), {"min_interval_s": 60}))
    assert "audience" not in env


def test_NEGATIVE_second_throttled_inside_window_still_coalesced():
    envs = _published(
        (bus.publish_throttled, ("t", "k", {"n": 1}), {"audience": ["a@x"], "min_interval_s": 60}),
        (bus.publish_throttled, ("t", "k", {"n": 2}), {"audience": ["a@x"], "min_interval_s": 60}),
    )
    assert [e["payload"] for e in envs] == [{"n": 1}]


# ── 2. audience_allows ──────────────────────────────────────────────────────
def test_untagged_envelope_allows_everyone():
    env = {"type": "t", "ts": 1.0, "payload": {}}
    assert sse.audience_allows(env, None) is True
    assert sse.audience_allows(env, "anyone") is True


def test_tagged_envelope_allows_only_members_case_insensitive():
    env = {"audience": frozenset({"a@x"})}
    assert sse.audience_allows(env, "A@X") is True
    assert sse.audience_allows(env, " a@x ") is True


def test_NEGATIVE_tagged_envelope_refuses_others():
    env = {"audience": frozenset({"a@x"})}
    assert sse.audience_allows(env, "b@y") is False
    assert sse.audience_allows(env, None) is False
    assert sse.audience_allows(env, "") is False
    assert sse.audience_allows(env, 7) is False


def test_NEGATIVE_empty_audience_refuses_everyone():
    assert sse.audience_allows({"audience": frozenset()}, "a@x") is False
    assert sse.audience_allows({"audience": frozenset()}, None) is False


@pytest.mark.parametrize("bad", ["a@x", ["a@x"], ("a@x",), None, {"a@x": 1}])
def test_NEGATIVE_non_set_audience_value_fails_closed(bad):
    assert sse.audience_allows({"audience": bad}, "a@x") is False


# ── 3. _frame ───────────────────────────────────────────────────────────────
def test_NEGATIVE_frame_never_puts_audience_or_email_on_the_wire():
    b = sse._frame("t", {"type": "t", "ts": 1.0, "payload": {"p": 1},
                         "audience": frozenset({"owner@x"})})
    assert b'"payload":{"p":1}' in b
    assert b"audience" not in b
    assert b"owner@x" not in b


def test_untagged_frame_bytes_pinned_exactly():
    b = sse._frame("t", {"type": "t", "ts": 1.0, "payload": {"p": 1}})
    assert b == b'event: t\ndata: {"type":"t","ts":1.0,"payload":{"p":1}}\n\n'


def test_untagged_frame_equals_todays_whole_envelope_dump():
    import json
    env = {"type": "gajjala.update", "ts": 1763300000.123456,
           "payload": {"kind": "quotes", "quotes": {"GP": {"price": 1.48}}}}
    today = ("event: gajjala.update\ndata: "
             + json.dumps(env, separators=(",", ":"), default=str) + "\n\n").encode()
    assert sse._frame("gajjala.update", env) == today


def test_tagged_frame_equals_the_untagged_frame():
    env = {"type": "t", "ts": 2.5, "payload": {"q": [1, 2]}}
    tagged = dict(env, audience=frozenset({"owner@x"}))
    assert sse._frame("t", tagged) == sse._frame("t", env)


# ── 4. source guards ────────────────────────────────────────────────────────
def test_events_route_uses_maybe_current_user_not_current_user_email():
    sig = inspect.signature(sse.events)
    assert "email" in sig.parameters
    assert sig.parameters["email"].default.dependency is sse.maybe_current_user
    src = (BACKEND / "events" / "sse.py").read_text()
    assert "Depends(maybe_current_user)" in src
    assert "current_user_email" not in src


def test_stream_loop_filters_before_framing():
    src = inspect.getsource(sse.events)
    i_allow = src.index("audience_allows(")
    i_frame = src.index("_frame(")
    assert i_allow < i_frame
    assert src.count("_frame(") == 1
    assert "if not audience_allows(evt, email):" in src


def test_publish_signature_has_keyword_only_audience():
    for fn in (bus.publish, bus.publish_throttled):
        p = inspect.signature(fn).parameters["audience"]
        assert p.kind is inspect.Parameter.KEYWORD_ONLY
        assert p.default is None


def _main_literal(name):
    tree = ast.parse((BACKEND / "main.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in main.py")


def test_NEGATIVE_events_still_not_public_in_main():
    paths = _main_literal("_PUBLIC_API_PATHS")
    prefixes = _main_literal("_PUBLIC_API_PREFIXES")
    assert "/events" not in paths
    assert not any("/events".startswith(p) for p in prefixes)
    assert not any(p.startswith("/events") for p in prefixes)


# ── 5. the route alone adds no gate ─────────────────────────────────────────
def _route_headers(headers):
    """Drive the router-only app at the ASGI level: capture the response
    start, then disconnect. The infinite body is never iterated."""
    app = FastAPI()
    app.include_router(sse.router)
    started = {}

    async def go():
        got_start = asyncio.Event()
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "GET", "scheme": "http", "path": "/events", "raw_path": b"/events",
            "root_path": "", "query_string": b"",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": ("127.0.0.1", 1), "server": ("testserver", 80),
        }
        sent_request = False

        async def receive():
            nonlocal sent_request
            if not sent_request:
                sent_request = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await got_start.wait()
            return {"type": "http.disconnect"}

        async def send(msg):
            if msg["type"] == "http.response.start":
                started["status"] = msg["status"]
                started["headers"] = {k.decode().lower(): v.decode()
                                      for k, v in msg.get("headers", [])}
            elif msg["type"] == "http.response.body" and "status" in started:
                got_start.set()

        await asyncio.wait_for(app(scope, receive, send), timeout=10)

    try:
        asyncio.run(go())
    finally:
        bus._loop = None
    return started


def test_route_answers_stream_with_the_owner_header():
    r = _route_headers({"X-User-Email": "owner@example.com"})
    assert r["status"] == 200
    assert r["headers"]["content-type"].startswith("text/event-stream")


def test_NEGATIVE_route_answers_stream_without_any_header():
    r = _route_headers({})
    assert r["status"] == 200
    assert r["headers"]["content-type"].startswith("text/event-stream")


def test_route_unsubscribes_after_disconnect():
    _route_headers({})
    assert len(bus._subscribers) == 0
