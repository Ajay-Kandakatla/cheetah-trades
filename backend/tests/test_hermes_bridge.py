"""Hermes bridge — gate, socket target, turn relay, image ordering, guards.

The live wire was probed from inside the api container (see the module
docstring); these tests pin the contract that probe established against a
scripted fake socket, so a Hermes upgrade that changes an event name or a
refactor that drops the loopback Host trick fails here first.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import auth  # noqa: E402
from auth import current_user_email  # noqa: E402
from ollama_chat import api as O  # noqa: E402
from ollama_chat import hermes as H  # noqa: E402

ADMIN = O.PRIMARY_ADMIN_EMAIL
STRANGER = "friend@example.com"
TOKEN = "test-token-abc"


def _client(email: str) -> TestClient:
    app = FastAPI()
    app.include_router(H.router)
    app.dependency_overrides[current_user_email] = lambda: email
    return TestClient(app)


def _events(text: str) -> list[dict]:
    return [json.loads(ln[5:].strip()) for ln in text.split("\n") if ln.startswith("data:")]


def _ev(ty: str, payload, sid="rt1") -> dict:
    return {"jsonrpc": "2.0", "method": "event", "params": {"type": ty, "session_id": sid, "payload": payload}}


# ---------------------------------------------------------------------------
# Fake Hermes socket
# ---------------------------------------------------------------------------
class FakeWS:
    """Scripted server: ``results`` maps method → result (or an error dict via
    ``{"__error__": ...}``); ``after`` maps method → events pushed right after
    that method's reply. ``gateway.ready`` is sent on connect like Hermes."""
    instances: list["FakeWS"] = []

    def __init__(self, results: dict, after: dict, ready: bool = True):
        self.results, self.after = results, after
        self.q: asyncio.Queue = asyncio.Queue()
        self.sent: list[dict] = []
        self.closed = False
        if ready:
            self.q.put_nowait(json.dumps(_ev("gateway.ready", {"heartbeat": 15}, sid="")))
        FakeWS.instances.append(self)

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.q.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def send(self, raw: str):
        req = json.loads(raw)
        self.sent.append(req)
        m = req["method"]
        res = self.results.get(m, {})
        if isinstance(res, dict) and "__error__" in res:
            await self.q.put(json.dumps({"jsonrpc": "2.0", "id": req["id"], "error": {"code": 1, "message": res["__error__"]}}))
        else:
            await self.q.put(json.dumps({"jsonrpc": "2.0", "id": req["id"], "result": res}))
        for e in self.after.get(m, []):
            await self.q.put(json.dumps(e) if isinstance(e, dict) else e)

    async def close(self):
        self.closed = True
        await self.q.put(None)

    def calls(self, method: str) -> list[dict]:
        return [r["params"] for r in self.sent if r["method"] == method]


@pytest.fixture
def hermes(monkeypatch):
    """Install a fake connect; tests configure ``fx.results`` / ``fx.after``."""
    FakeWS.instances = []
    state = {"results": {}, "after": {}, "connect_kwargs": [], "fail": None, "ready": True}

    async def fake_connect(uri, **kw):
        state["connect_kwargs"].append({"uri": uri, **kw})
        if state["fail"] is not None:
            raise state["fail"]
        return FakeWS(state["results"], state["after"], ready=state["ready"])

    monkeypatch.setattr(H, "ws_connect", fake_connect)
    monkeypatch.setenv(H.TOKEN_ENV, TOKEN)
    monkeypatch.setenv("HERMES_BASE_URL", "http://host.docker.internal:9119")
    return state


CREATE = {"session_id": "rt1", "stored_session_id": "20260914_1", "info": {"model": "m", "cwd": "/x", "tools": ["terminal"], "approval_mode": "off"}}


def _happy_turn():
    return {
        "session.create": CREATE,
        "session.resume": {"session_id": "rt1", "info": {"stored_session_id": "20260914_1", "model": "m"}},
        "prompt.submit": {"status": "streaming"},
        "image.attach_bytes": {"attached": True, "count": 1},
    }


TURN_EVENTS = [
    _ev("message.start", None),
    _ev("sessions.changed", {}, sid=""),
    _ev("thinking.delta", {"text": "hmm "}),
    _ev("reasoning.delta", {"text": "ok"}),
    _ev("message.delta", {"text": "I will run it. "}),
    _ev("tool.generating", {"name": "terminal"}),
    _ev("tool.start", {"tool_id": "c1", "name": "terminal", "context": "uname -a", "args": {"command": "uname -a"}}),
    _ev("tool.complete", {"tool_id": "c1", "name": "terminal", "duration_s": 0.2, "args": {}, "result": {"output": "Darwin", "exit_code": 0}}),
    _ev("message.delta", {"text": "Darwin"}),
    _ev("message.delta", {"text": "IGNORED"}, sid="other"),      # other session — must not relay
    _ev("session.info", {"model": "m"}),
    _ev("status.update", {"kind": "warn", "text": "title gen failed"}),
    _ev("message.complete", {"text": "Darwin", "usage": {"input": 10, "output": 5}, "status": "complete"}),
    _ev("message.delta", {"text": "AFTER"}),                       # after complete — must not relay
]


# ---------------------------------------------------------------------------
# WHO
# ---------------------------------------------------------------------------
def test_stranger_and_house_owner_get_404(hermes, monkeypatch):
    for who in (STRANGER, "co@example.com"):
        if who != STRANGER:
            monkeypatch.setattr(auth, "HOUSE_OWNER_EMAILS", [ADMIN, who])
            assert auth.is_admin_email(who)
        c = _client(who)
        assert c.get("/hermes/me").status_code == 404
        assert c.post("/hermes/chat", json={"text": "hi"}).status_code == 404
        assert c.post("/hermes/approve", json={"session_id": "s", "request_id": "r"}).status_code == 404
        assert c.post("/hermes/interrupt", json={"session_id": "s"}).status_code == 404
    assert hermes["connect_kwargs"] == [], "no socket may be opened for a stranger"


# ---------------------------------------------------------------------------
# SOCKET TARGET — the loopback Host trick
# ---------------------------------------------------------------------------
def test_ws_target_keeps_loopback_host_but_dials_the_real_one(monkeypatch):
    monkeypatch.setenv("HERMES_BASE_URL", "http://host.docker.internal:9119")
    monkeypatch.setenv(H.TOKEN_ENV, TOKEN)
    uri, host, port = H.ws_target()
    assert uri == f"ws://127.0.0.1:9119/api/ws?token={TOKEN}"
    assert (host, port) == ("host.docker.internal", 9119)
    monkeypatch.setenv("HERMES_BASE_URL", "http://10.0.0.5:9200/")
    uri, host, port = H.ws_target()
    assert uri.startswith("ws://127.0.0.1:9200/api/ws?token=") and (host, port) == ("10.0.0.5", 9200)


def test_connect_is_called_with_host_override(hermes):
    hermes["results"] = _happy_turn()
    hermes["after"] = {"prompt.submit": TURN_EVENTS}
    with _client(ADMIN).stream("POST", "/hermes/chat", json={"text": "hi"}) as r:
        "".join(r.iter_text())
    kw = hermes["connect_kwargs"][0]
    assert kw["uri"].startswith("ws://127.0.0.1:9119/api/ws?token=")
    assert kw["host"] == "host.docker.internal" and kw["port"] == 9119


def test_missing_token_never_dials(hermes, monkeypatch):
    monkeypatch.delenv(H.TOKEN_ENV, raising=False)
    j = _client(ADMIN).get("/hermes/me").json()
    assert j["reachable"] is False and j["token_set"] is False and "HERMES_WS_TOKEN" in j["reason"]
    with _client(ADMIN).stream("POST", "/hermes/chat", json={"text": "hi"}) as r:
        ev = _events("".join(r.iter_text()))
    assert len(ev) == 1 and "HERMES_WS_TOKEN" in ev[0]["error"]
    assert hermes["connect_kwargs"] == []


def test_me_reports_connection_refused_as_a_reason(hermes):
    hermes["fail"] = ConnectionRefusedError(61, "refused")
    j = _client(ADMIN).get("/hermes/me").json()
    assert j["reachable"] is False and "not reachable" in j["reason"] and "ai.hermes.serve" in j["reason"]


def test_me_reports_http_403_as_host_or_peer(hermes):
    class Refused(Exception):
        status_code = 403
    hermes["fail"] = Refused("server rejected WebSocket connection: HTTP 403")
    j = _client(ADMIN).get("/hermes/me").json()
    assert j["reachable"] is False and "403" in j["reason"] and "loopback" in j["reason"]


def test_me_ok(hermes):
    j = _client(ADMIN).get("/hermes/me").json()
    assert j["reachable"] is True and j["token_set"] is True and j["heartbeat"] == 15
    assert FakeWS.instances[-1].closed


# ---------------------------------------------------------------------------
# THE TURN
# ---------------------------------------------------------------------------
def test_new_session_turn_relays_the_right_events_in_order(hermes):
    hermes["results"] = _happy_turn()
    hermes["after"] = {"prompt.submit": TURN_EVENTS}
    with _client(ADMIN).stream("POST", "/hermes/chat", json={"text": "run uname"}) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        ev = _events("".join(r.iter_text()))
    assert ev[0]["session"] == {"session_id": "rt1", "stored_session_id": "20260914_1", "model": "m",
                                "cwd": "/x", "tools": ["terminal"], "approval_mode": "off"}
    assert ev[1:] == [
        {"thinking": "hmm "}, {"thinking": "ok"},
        {"delta": "I will run it. "},
        {"tool_generating": "terminal"},
        {"tool_start": {"tool_id": "c1", "name": "terminal", "context": "uname -a", "args": {"command": "uname -a"}}},
        {"tool_done": {"tool_id": "c1", "name": "terminal", "duration_s": 0.2, "result": {"output": "Darwin", "exit_code": 0}}},
        {"delta": "Darwin"},
        {"status": {"kind": "warn", "text": "title gen failed"}},
        {"done": {"text": "Darwin", "usage": {"input": 10, "output": 5}, "status": "complete"}},
    ]
    ws = FakeWS.instances[-1]
    assert [r["method"] for r in ws.sent] == ["session.create", "prompt.submit"]
    assert ws.calls("prompt.submit") == [{"session_id": "rt1", "text": "run uname"}]
    assert ws.closed


def test_stored_session_is_resumed_and_images_attach_before_submit(hermes):
    hermes["results"] = _happy_turn()
    hermes["after"] = {"prompt.submit": [_ev("message.complete", {"text": "Blue", "usage": {}, "status": "complete"})]}
    body = {"text": "colour?", "session_id": "20260914_1", "images": ["AAAA", " ", "BBBB"]}
    with _client(ADMIN).stream("POST", "/hermes/chat", json=body) as r:
        ev = _events("".join(r.iter_text()))
    ws = FakeWS.instances[-1]
    assert [r["method"] for r in ws.sent] == ["session.resume", "image.attach_bytes", "image.attach_bytes", "prompt.submit"]
    assert ws.calls("session.resume") == [{"session_id": "20260914_1"}]
    assert ws.calls("image.attach_bytes") == [
        {"session_id": "rt1", "content_base64": "AAAA", "filename": "cheetah_1.png"},
        {"session_id": "rt1", "content_base64": "BBBB", "filename": "cheetah_2.png"},
    ]
    assert ev[0]["session"]["stored_session_id"] == "20260914_1"
    assert ev[-1]["done"]["text"] == "Blue"


def test_resume_failure_falls_back_to_a_new_session(hermes):
    hermes["results"] = {**_happy_turn(), "session.resume": {"__error__": "unknown session"}}
    hermes["after"] = {"prompt.submit": [_ev("message.complete", {"text": "ok"})]}
    with _client(ADMIN).stream("POST", "/hermes/chat", json={"text": "x", "session_id": "gone"}) as r:
        ev = _events("".join(r.iter_text()))
    ws = FakeWS.instances[-1]
    assert [r["method"] for r in ws.sent] == ["session.resume", "session.create", "prompt.submit"]
    assert ev[0]["session"]["stored_session_id"] == "20260914_1"


def test_turn_error_and_approval_and_truncation(hermes):
    big = "x" * (H.TOOL_RESULT_MAX + 50)
    hermes["results"] = _happy_turn()
    hermes["after"] = {"prompt.submit": [
        _ev("approval.request", {"request_id": "ap1", "command": "rm -rf /tmp/x", "choices": ["once", "deny"]}),
        _ev("tool.complete", {"tool_id": "c9", "name": "terminal", "duration_s": 1.0, "result": big}),
        _ev("turn.error", {"text": "model exploded"}),
        _ev("message.complete", {"text": "NEVER"}),
    ]}
    with _client(ADMIN).stream("POST", "/hermes/chat", json={"text": "x"}) as r:
        ev = _events("".join(r.iter_text()))
    assert ev[1]["approval"] == {"request_id": "ap1", "command": "rm -rf /tmp/x", "choices": ["once", "deny"], "session_id": "rt1"}
    assert ev[2]["tool_done"]["result"].startswith("x" * 10) and len(ev[2]["tool_done"]["result"]) < len(big)
    assert ev[3] == {"error": "model exploded"}
    assert len(ev) == 4


def test_rpc_error_on_submit_becomes_error_event(hermes):
    hermes["results"] = {**_happy_turn(), "prompt.submit": {"__error__": "session busy"}}
    with _client(ADMIN).stream("POST", "/hermes/chat", json={"text": "x"}) as r:
        ev = _events("".join(r.iter_text()))
    assert ev[0].get("session") and ev[1] == {"error": "prompt.submit: session busy"}


def test_no_ready_is_an_error(hermes, monkeypatch):
    monkeypatch.setattr(H, "READY_TIMEOUT_SEC", 0.2)
    hermes["ready"] = False
    with _client(ADMIN).stream("POST", "/hermes/chat", json={"text": "x"}) as r:
        ev = _events("".join(r.iter_text()))
    assert len(ev) == 1 and "gateway.ready" in ev[0]["error"]


# ---------------------------------------------------------------------------
# APPROVE / INTERRUPT
# ---------------------------------------------------------------------------
def test_approve_relays_choice(hermes):
    hermes["results"] = {"approval.respond": {"ok": True}}
    r = _client(ADMIN).post("/hermes/approve", json={"session_id": "rt1", "request_id": "ap1", "choice": "session"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert FakeWS.instances[-1].calls("approval.respond") == [
        {"session_id": "rt1", "request_id": "ap1", "choice": "session", "all": False}]


def test_approve_rejects_unknown_choice_without_dialing(hermes):
    r = _client(ADMIN).post("/hermes/approve", json={"session_id": "rt1", "request_id": "ap1", "choice": "yolo"})
    assert r.status_code == 400 and hermes["connect_kwargs"] == []


def test_interrupt_relays_and_reports_502_when_down(hermes):
    hermes["results"] = {"session.interrupt": {"status": "interrupted"}}
    r = _client(ADMIN).post("/hermes/interrupt", json={"session_id": "rt1"})
    assert r.status_code == 200 and r.json()["result"] == {"status": "interrupted"}
    hermes["fail"] = ConnectionRefusedError()
    r = _client(ADMIN).post("/hermes/interrupt", json={"session_id": "rt1"})
    assert r.status_code == 502 and r.json()["ok"] is False


# ---------------------------------------------------------------------------
# INPUT GUARDS
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("body,code,needle", [
    ({"text": "   "}, 400, "empty"),
    ({"text": "x", "images": ["data:image/png;base64,AAAA"]}, 400, "data: URL"),
    ({"text": "x", "images": ["A"] * 7}, 400, "images"),
    ({"text": 5}, 422, None),
])
def test_bad_bodies_never_dial(hermes, body, code, needle):
    r = _client(ADMIN).post("/hermes/chat", json=body)
    assert r.status_code == code, r.text
    if needle:
        assert needle in r.json()["detail"]
    assert hermes["connect_kwargs"] == []


def test_oversize_image_is_413(hermes):
    r = _client(ADMIN).post("/hermes/chat", json={"text": "x", "images": ["A" * (O.MAX_IMAGE_B64_BYTES + 1)]})
    assert r.status_code == 413 and hermes["connect_kwargs"] == []


# ---------------------------------------------------------------------------
# SOURCE GUARDS
# ---------------------------------------------------------------------------
def test_main_mounts_the_bridge():
    src = (ROOT / "main.py").read_text()
    assert "app.include_router(hermes_router)" in src


def test_env_has_the_bridge_settings():
    env = (ROOT / ".env").read_text()
    assert "HERMES_BASE_URL=" in env and "HERMES_WS_TOKEN=" in env


def test_token_is_never_logged_or_echoed(hermes):
    """The token rides in the socket URI only; no endpoint may return it."""
    j = _client(ADMIN).get("/hermes/me").json()
    assert TOKEN not in json.dumps(j)
    src = (ROOT / "ollama_chat" / "hermes.py").read_text()
    assert "log.info(\"%s\", token()" not in src and "print(token" not in src
