"""📅 GET /chart-maps/gajjala-watch/runners/chart/{symbol} — owner only (spec runcharts rev 2 §3.5, §4.1, 2026-11-26).

Ajay 2026-11-26, verbatim: "I want you to have continous charts for previous day runners … I wanna able to horizontal
scroll tp check continuity like he does".

NEGATIVES: anyone else (another email, no email, a blank header, a direct call with the Depends OBJECT) gets exactly
`owner_only_payload()` and the engine is never called; `?sessions=` changes nothing; a raising engine answers `error`
with RUNCHART_FAULT_TEXT, never a 500; NaN never reaches the wire; the path is on no public allow-list.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import runchart as RC
from tests.test_gajjala_watch_api_2026_11_15 import OTHER, OWNER, _strict
from tests.test_gajjala_watch_runchart_2026_11_26 import Loader, raw_day

PATH = C.API_RUNCHART_PATH.replace("{symbol}", "BGLC")


class Rec:
    def __init__(self, out=None, exc=None):
        self.calls = []
        self.out = out if out is not None else {"state": "ok", "symbol": "BGLC", "bars": []}
        self.exc = exc

    def __call__(self, symbol, now=None, **kw):
        self.calls.append({"symbol": symbol, "now": now, "kw": dict(kw)})
        if self.exc is not None:
            raise self.exc
        return self.out


@pytest.fixture()
def owner(monkeypatch):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)


@pytest.fixture()
def client(owner):
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app)


def _use(monkeypatch, rec):
    monkeypatch.setattr(RC, "build", rec)
    return rec


def test_the_path_constant():
    assert C.API_RUNCHART_PATH == "/chart-maps/gajjala-watch/runners/chart/{symbol}"
    assert C.API_RUNCHART_PATH == C.API_RUNNERS_PATH + "/chart/{symbol}"
    got = [(r.path, m) for r in API.router.routes for m in getattr(r, "methods", ())]
    assert got.count((C.API_RUNCHART_PATH, "GET")) == 1


def test_owner_gets_the_engines_answer(client, monkeypatch):
    rec = _use(monkeypatch, Rec())
    r = client.get(PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200 and _strict(r.text) == rec.out
    assert len(rec.calls) == 1 and rec.calls[0]["symbol"] == "BGLC" and rec.calls[0]["kw"] == {"tf": None}
    assert isinstance(rec.calls[0]["now"], datetime) and rec.calls[0]["now"].tzinfo is not None
    assert OWNER not in r.text


def test_tf_reaches_the_engine_as_a_string(client, monkeypatch):
    rec = _use(monkeypatch, Rec())
    client.get(PATH + "?tf=15m", headers={"X-User-Email": OWNER})
    assert rec.calls[0]["kw"] == {"tf": "15m"} and isinstance(rec.calls[0]["kw"]["tf"], str)


@pytest.mark.parametrize("headers", [{"X-User-Email": OTHER}, {}, {"X-User-Email": "  "}])
def test_NEGATIVE_anyone_else_gets_owner_only_and_the_engine_is_never_called(client, monkeypatch, headers):
    rec = _use(monkeypatch, Rec())
    r = client.get(PATH, headers=headers)
    assert r.status_code == 200 and r.json() == PL.owner_only_payload()
    assert rec.calls == []


def test_NEGATIVE_sessions_from_the_owner_changes_nothing(client, monkeypatch):
    rec = _use(monkeypatch, Rec())
    a = client.get(PATH + "?sessions=99", headers={"X-User-Email": OWNER})
    b = client.get(PATH, headers={"X-User-Email": OWNER})
    assert a.text == b.text
    assert [c["kw"] for c in rec.calls] == [{"tf": None}, {"tf": None}]
    assert all("sessions" not in c["kw"] for c in rec.calls)


def test_NEGATIVE_a_direct_call_with_the_depends_object_is_owner_only(owner, monkeypatch):
    rec = _use(monkeypatch, Rec())
    out = asyncio.run(API.gajjala_watch_runner_chart("BGLC"))
    assert out == PL.owner_only_payload() and rec.calls == []


def test_NEGATIVE_a_raising_engine_answers_error_with_the_fault_words(client, monkeypatch):
    _use(monkeypatch, Rec(exc=RuntimeError("boom")))
    r = client.get(PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200
    assert r.json() == {"state": "error", "text": C.RUNCHART_FAULT_TEXT.format(sym="BGLC")}
    assert C.RUNCHART_FAULT_TEXT != C.RUNCHART_ERROR_TEXT


def test_NEGATIVE_a_non_dict_answer_is_the_fault_answer(client, monkeypatch):
    _use(monkeypatch, Rec(out=["not", "an", "answer"]))
    r = client.get(PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200 and r.json()["state"] == "error"


def test_a_busy_answer_passes_through_untouched(client, monkeypatch):
    rec = _use(monkeypatch, Rec(out=RC.busy("BGLC")))
    r = client.get(PATH, headers={"X-User-Email": OWNER})
    assert r.json() == rec.out == {"state": "busy", "symbol": "BGLC",
                                   "text": C.RUNCHART_BUSY_TEXT.format(sym="BGLC", sec=C.RUNCHART_BUSY_RETRY_SEC),
                                   "retry_sec": C.RUNCHART_BUSY_RETRY_SEC}


def test_NEGATIVE_nan_and_inf_are_null_on_the_wire(client, monkeypatch):
    _use(monkeypatch, Rec(out={"state": "ok", "bars": [{"c": float("nan"), "h": float("inf"), "l": -float("inf")}]}))
    r = client.get(PATH, headers={"X-User-Email": OWNER})
    body = _strict(r.text)
    assert body["bars"] == [{"c": None, "h": None, "l": None}]


def test_the_body_is_built_in_to_thread(client, monkeypatch):
    _use(monkeypatch, Rec())
    seen = []
    real = asyncio.to_thread

    async def spy(fn, *a, **k):
        seen.append(fn)
        return await real(fn, *a, **k)
    monkeypatch.setattr(API.asyncio, "to_thread", spy)
    client.get(PATH, headers={"X-User-Email": OWNER})
    assert seen == [API._runchart_body]


def test_the_real_engine_through_the_route_is_strict_json(client, monkeypatch):
    real = RC.build
    RC.reset()
    L = Loader()
    monkeypatch.setattr(RC, "build", lambda s, now, tf=None: real(
        s, datetime(2026, 11, 26, 12, 0, tzinfo=API.ET), tf=tf, load_day=L, splits_fn=lambda a, b: [],
        cached_at_fn=lambda a, b: {}, ran_fn=lambda n, d: {}, wait_sec=0.05))
    r = client.get(PATH + "?tf=15m", headers={"X-User-Email": OWNER})
    body = _strict(r.text)
    assert body["state"] == "ok" and body["tf"] == "15m" and len(body["bars"]) == 5 * 64
    assert [s["date"] for s in body["sessions"]] == ["2026-11-19", "2026-11-20", "2026-11-23", "2026-11-24",
                                                     "2026-11-25"]
    RC.reset()


def test_NEGATIVE_the_path_is_on_no_public_allow_list_of_main():
    src = (Path(API.__file__).resolve().parents[2] / "main.py").read_text(encoding="utf-8")
    i, j = src.index("_PUBLIC_API_PATHS = {"), src.index("_PUBLIC_API_PATHS_FINNHUB_V2 =")
    block = src[i:j]
    entries = re.findall(r"\"(/[^\"]*)\"", block)
    assert entries, "the allow-list block was not found"
    concrete = PATH
    for e in entries:
        assert concrete != e and not concrete.startswith(e), e
    assert "runners/chart" not in block


def test_NEGATIVE_the_route_module_names_no_session_count_parameter():
    import inspect
    sig = inspect.signature(API.gajjala_watch_runner_chart)
    assert set(sig.parameters) == {"symbol", "email", "tf"}
    assert "sessions" not in inspect.getsource(API._runchart_body)
