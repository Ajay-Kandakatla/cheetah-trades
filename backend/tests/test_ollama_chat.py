"""Private Ollama chat — the gate, the stream relay, the input guards.

Ajay 2026-09-14: "only available for me". The tests that matter are the ones
that pin WHO: the primary-admin address and nobody else — including a house
owner who carries ``is_admin`` — and that the answer to everyone else is a 404
that arrives before body validation could leak the route's shape.
"""
from __future__ import annotations

import json
import re
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

ADMIN = O.PRIMARY_ADMIN_EMAIL
STRANGER = "friend@example.com"


def _client(email: str) -> TestClient:
    app = FastAPI()
    app.include_router(O.router)
    app.dependency_overrides[current_user_email] = lambda: email
    return TestClient(app)


def _events(text: str) -> list[dict]:
    out = []
    for line in text.split("\n"):
        if line.startswith("data:"):
            out.append(json.loads(line[5:].strip()))
    return out


# ---------------------------------------------------------------------------
# Fake Ollama — what httpx.AsyncClient returns in the stream path
# ---------------------------------------------------------------------------
class _Resp:
    def __init__(self, lines, status=200):
        self.status_code = status
        self._lines = lines

    async def aiter_lines(self):
        for ln in self._lines:
            yield ln

    async def aread(self):
        return b"upstream exploded"


class _StreamCM:
    def __init__(self, resp):
        self.resp = resp

    async def __aenter__(self):
        return self.resp

    async def __aexit__(self, *a):
        return False


class FakeClient:
    lines: list[str] = []
    status: int = 200
    captured: dict = {}

    def __init__(self, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, method, url, json=None):
        FakeClient.captured = {"method": method, "url": url, "payload": json}
        return _StreamCM(_Resp(FakeClient.lines, FakeClient.status))


@pytest.fixture
def fake_ollama(monkeypatch):
    FakeClient.lines = []
    FakeClient.status = 200
    FakeClient.captured = {}
    monkeypatch.setattr(O.httpx, "AsyncClient", FakeClient)
    return FakeClient


# ---------------------------------------------------------------------------
# WHO
# ---------------------------------------------------------------------------
def test_gate_constant_matches_access_api_admin():
    """Two gates, one address. The module keeps its own copy on purpose;
    this is the test that makes the duplication safe."""
    from access import api as access_api
    assert O.PRIMARY_ADMIN_EMAIL == access_api.ADMIN_EMAIL


def test_primary_admin_is_case_and_space_insensitive():
    assert O.is_primary_admin("  " + ADMIN.upper() + " ")
    assert not O.is_primary_admin(None)
    assert not O.is_primary_admin("")


def test_stranger_gets_404_on_every_route():
    c = _client(STRANGER)
    assert c.get("/ollama/me").status_code == 404
    assert c.post("/ollama/warm").status_code == 404
    r = c.post("/ollama/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 404


def test_house_owner_with_is_admin_is_still_404(monkeypatch):
    """The trap: ``auth.is_admin_email`` is TRUE for every house owner.
    'Only available for me' means the co-owner flag must not open this."""
    co = "co-owner@example.com"
    monkeypatch.setattr(auth, "HOUSE_OWNER_EMAILS", [ADMIN, co])
    assert auth.is_admin_email(co), "fixture: co-owner should read as admin"
    c = _client(co)
    assert c.get("/ollama/me").status_code == 404
    assert c.post("/ollama/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 404


def test_404_wins_over_body_validation_for_strangers():
    """Garbage body from a stranger must NOT turn into a 422 that lists our
    field names — the gate is a dependency so it fires first."""
    c = _client(STRANGER)
    assert c.post("/ollama/chat", json={"nonsense": 1}).status_code == 404
    assert c.post("/ollama/chat", json={"messages": "garbage"}).status_code == 404
    # Known limit: a body that is not JSON at all fails in FastAPI's parser
    # BEFORE dependencies run, so it is a 422 — the same generic 422 every
    # JSON route in the app returns, carrying no field names of ours.
    r = c.post("/ollama/chat", content=b"not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert "messages" not in r.text and "images" not in r.text


def test_admin_me_survives_unreachable_ollama(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("OLLAMA_CHAT_MODEL", "some/model:1b")
    r = _client(ADMIN).get("/ollama/me")
    assert r.status_code == 200
    j = r.json()
    assert j["model"] == "some/model:1b"
    assert j["reachable"] is False and j["resident"] is False
    assert j["base_url"] == "http://127.0.0.1:1"


def test_defaults_point_at_the_host_and_his_model(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_CHAT_MODEL", raising=False)
    assert O.base_url() == "http://host.docker.internal:11434"
    assert O.model_name() == "huihui_ai/Qwen3.8-abliterated:27b"
    assert O.KEEP_ALIVE == -1


# ---------------------------------------------------------------------------
# THE STREAM
# ---------------------------------------------------------------------------
def test_chat_relays_thinking_delta_done_and_pins_the_model(fake_ollama):
    fake_ollama.lines = [
        json.dumps({"message": {"role": "assistant", "thinking": "let me "}, "done": False}),
        json.dumps({"message": {"role": "assistant", "thinking": "see"}, "done": False}),
        json.dumps({"message": {"role": "assistant", "content": "Hel"}, "done": False}),
        "",  # keep-alive blank line
        json.dumps({"message": {"role": "assistant", "content": "lo"}, "done": False}),
        json.dumps({"model": "m", "message": {"role": "assistant", "content": ""}, "done": True,
                    "eval_count": 12, "prompt_eval_count": 30, "total_duration": 2_000_000_000}),
        json.dumps({"message": {"content": "NEVER"}, "done": False}),   # after done — must not relay
    ]
    c = _client(ADMIN)
    with c.stream("POST", "/ollama/chat",
                  json={"messages": [{"role": "user", "content": "hi"}], "think": True}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        assert r.headers["x-accel-buffering"] == "no"
        text = "".join(r.iter_text())
    ev = _events(text)
    assert ev == [
        {"thinking": "let me "}, {"thinking": "see"},
        {"delta": "Hel"}, {"delta": "lo"},
        {"done": True, "model": "m", "eval_count": 12, "prompt_eval_count": 30,
         "total_duration": 2_000_000_000},
    ]
    p = fake_ollama.captured["payload"]
    assert fake_ollama.captured["url"].endswith("/api/chat")
    assert p["keep_alive"] == -1 and p["stream"] is True and p["think"] is True
    assert p["messages"] == [{"role": "user", "content": "hi"}]


def test_chat_uses_env_model_unless_overridden(fake_ollama, monkeypatch):
    monkeypatch.setenv("OLLAMA_CHAT_MODEL", "env/model:7b")
    c = _client(ADMIN)
    with c.stream("POST", "/ollama/chat", json={"messages": [{"role": "user", "content": "x"}]}) as r:
        "".join(r.iter_text())
    assert fake_ollama.captured["payload"]["model"] == "env/model:7b"
    assert "think" not in fake_ollama.captured["payload"]
    with c.stream("POST", "/ollama/chat",
                  json={"messages": [{"role": "user", "content": "x"}], "model": "other:1b"}) as r:
        "".join(r.iter_text())
    assert fake_ollama.captured["payload"]["model"] == "other:1b"


def test_chat_images_pass_through_as_bare_base64(fake_ollama):
    fake_ollama.lines = [json.dumps({"message": {"content": "Red"}, "done": True})]
    c = _client(ADMIN)
    body = {"messages": [{"role": "user", "content": "what colour", "images": ["iVBORw0KGgo=", " ", ""]}]}
    with c.stream("POST", "/ollama/chat", json=body) as r:
        assert r.status_code == 200
        "".join(r.iter_text())
    sent = fake_ollama.captured["payload"]["messages"][0]
    assert sent["images"] == ["iVBORw0KGgo="]           # blanks dropped


def test_chat_upstream_error_line_becomes_error_event_and_stops(fake_ollama):
    fake_ollama.lines = [
        json.dumps({"message": {"content": "part"}, "done": False}),
        json.dumps({"error": "model not found"}),
        json.dumps({"message": {"content": "NEVER"}, "done": False}),
    ]
    c = _client(ADMIN)
    with c.stream("POST", "/ollama/chat", json={"messages": [{"role": "user", "content": "x"}]}) as r:
        ev = _events("".join(r.iter_text()))
    assert ev == [{"delta": "part"}, {"error": "model not found"}]


def test_chat_upstream_non_200_is_an_error_event_not_a_500(fake_ollama):
    fake_ollama.status = 500
    c = _client(ADMIN)
    with c.stream("POST", "/ollama/chat", json={"messages": [{"role": "user", "content": "x"}]}) as r:
        assert r.status_code == 200          # the SSE channel opened; the error rides inside it
        ev = _events("".join(r.iter_text()))
    assert len(ev) == 1 and ev[0]["error"].startswith("ollama 500")
    assert "upstream exploded" in ev[0]["error"]


def test_chat_skips_unparseable_lines(fake_ollama):
    fake_ollama.lines = ["{not json", json.dumps({"message": {"content": "ok"}, "done": True})]
    c = _client(ADMIN)
    with c.stream("POST", "/ollama/chat", json={"messages": [{"role": "user", "content": "x"}]}) as r:
        ev = _events("".join(r.iter_text()))
    assert ev[0] == {"delta": "ok"} and ev[1]["done"] is True


# ---------------------------------------------------------------------------
# INPUT GUARDS (admin only — strangers never get this far)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("body,code,needle", [
    ({"messages": []}, 400, "empty"),
    ({"messages": [{"role": "assistant", "content": "only me"}]}, 400, "no user message"),
    ({"messages": [{"role": "user", "content": "x", "images": ["data:image/png;base64,AAAA"]}]}, 400, "data: URL"),
    ({"messages": [{"role": "user", "content": "x", "images": ["A"] * 7}]}, 400, "images"),
    ({"messages": [{"role": "user", "content": "x"}] * 201}, 400, "200"),
    ({"messages": [{"role": "tool", "content": "x"}]}, 422, None),
    ({"messages": "nope"}, 422, None),
])
def test_bad_bodies_are_refused_before_ollama_is_called(fake_ollama, body, code, needle):
    r = _client(ADMIN).post("/ollama/chat", json=body)
    assert r.status_code == code, r.text
    if needle:
        assert needle in r.json()["detail"]
    assert fake_ollama.captured == {}, "must not reach the model"


def test_oversize_image_is_413(fake_ollama):
    big = "A" * (O.MAX_IMAGE_B64_BYTES + 1)
    r = _client(ADMIN).post("/ollama/chat", json={"messages": [{"role": "user", "content": "x", "images": [big]}]})
    assert r.status_code == 413
    assert fake_ollama.captured == {}


def test_limits_are_sane():
    assert O.MAX_IMAGES_PER_MESSAGE == 6
    assert O.MAX_IMAGE_B64_BYTES >= 8 * 1024 * 1024        # one downscaled photo is ~300 KB; leave room


# ---------------------------------------------------------------------------
# SOURCE GUARDS — the wiring around the router
# ---------------------------------------------------------------------------
def test_main_mounts_router_and_exposes_is_primary_admin():
    src = (ROOT / "main.py").read_text()
    assert "app.include_router(ollama_router)" in src
    assert '"is_primary_admin": _ollama_is_primary_admin(email)' in src
    assert '"is_admin": is_admin_email(email)' in src, "the house-owner flag must remain too"


def test_admin_menu_lists_the_page():
    from access import store
    tos = [i["to"] for i in store._ADMIN_MENU_ITEMS]
    assert "/ollama" in tos


@pytest.mark.parametrize("conf", ["nginx.conf", "nginx-oauth.conf"])
def test_nginx_api_block_accepts_image_bodies(conf):
    """nginx's 1 MB default rejects one photo. The raise must sit INSIDE the
    /api/ location — not server-wide — and in both confs."""
    src = (ROOT.parent / "frontend" / conf).read_text()
    m = re.search(r"location /api/ \{(.*?)\n    \}", src, re.S)
    assert m, f"{conf}: no /api/ block"
    assert "client_max_body_size 40m;" in m.group(1)
    assert "proxy_buffering off;" in m.group(1), "streaming needs buffering off"


def test_admin_email_never_reaches_the_frontend_sources():
    """Walks ALL of frontend/src — nothing excluded. The four-file version of
    this guard missed pages/AdminTodos.tsx, which kept a string compare on
    the address and shipped it in its bundle chunk (caught 2026-09-14 by
    grepping the nginx assets live). Gates read ``is_primary_admin`` /
    ``is_admin`` off /auth/me; the address itself stays server-side."""
    fe = ROOT.parent / "frontend" / "src"
    files = [p for p in fe.rglob("*") if p.suffix in (".ts", ".tsx")]
    assert len(files) > 100, "frontend/src walk found too few files"
    assert any(p.name == "AdminTodos.tsx" for p in files)
    hits = [
        str(p.relative_to(fe))
        for p in files
        if ADMIN in p.read_text(encoding="utf-8", errors="replace").lower()
    ]
    assert hits == [], hits


def test_env_has_the_two_settings():
    env = (ROOT / ".env").read_text()
    assert "OLLAMA_BASE_URL=" in env and "OLLAMA_CHAT_MODEL=" in env
