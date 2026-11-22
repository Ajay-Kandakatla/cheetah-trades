"""📅 GET /chart-maps/gajjala-watch/runners — owner only (spec watch_org rev 4 §3.4, WP-BE, 2026-11-22).

Ajay 2026-11-22, verbatim: "use that space between the parent tab of Gajjala and watch tab to be for previous day runners
but remove them if they don’t run the current day".

NEGATIVES: anyone else (another email, no email, a direct call with the Depends OBJECT) gets exactly `owner_only_payload()`
and ZERO store reads; a raising engine answers `error` with the served sentence, never a 500; NaN never reaches the wire.
"""
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps.gajjala import store as ST
from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import runners as RN
from tests.test_gajjala_watch_api_2026_11_15 import OTHER, OWNER, _strict
from tests.test_gajjala_watch_runners_2026_11_22 import NOW_PRE, ET, thu_world


@pytest.fixture()
def client(monkeypatch):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    w = thu_world()
    monkeypatch.setattr(RN, "_store", lambda: w.st)
    monkeypatch.setattr(RN, "_replays", lambda: None)

    class _DT:                                                     # the route's clock, pinned to Fri 09:44 ET
        @staticmethod
        def now(tz=None):
            return NOW_PRE.astimezone(tz) if tz else NOW_PRE
    monkeypatch.setattr(API, "datetime", _DT)
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    c.world = w
    return c


def _reads(w):
    return sum(len(c.finds) + len(c.find_ones) for c in w.c.values())


def test_owner_gets_the_strip(client):
    r = client.get(C.API_RUNNERS_PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200
    body = _strict(r.text)
    assert body["state"] == "ok" and [x["symbol"] for x in body["rows"]] == ["RUNA", "RUNB", "RUNC", "BRK"]
    assert body["day"] == "2026-11-19" and body["title"].startswith("📅 Previous day runners")
    for k in ("n_running", "n_not_read", "no_bars", "as_of_et", "stale", "refresh_sec", "fold_at", "fold_at_phone"):
        assert k in body
    assert "unread" not in body
    assert C.API_RUNNERS_PATH == "/chart-maps/gajjala-watch/runners"


@pytest.mark.parametrize("headers", [{"X-User-Email": OTHER}, {}, {"X-User-Email": "  "}])
def test_NEGATIVE_anyone_else_gets_owner_only_and_nothing_is_read(client, headers):
    r = client.get(C.API_RUNNERS_PATH, headers=headers)
    assert r.status_code == 200 and r.json() == PL.owner_only_payload()
    assert _reads(client.world) == 0


def test_NEGATIVE_a_direct_call_with_the_depends_object_is_owner_only(monkeypatch):
    called = []
    monkeypatch.setattr(RN, "strip", lambda now, **k: called.append(now) or {"state": "ok"})
    out = asyncio.run(API.gajjala_watch_runners())
    assert out == PL.owner_only_payload() and called == []


def test_NEGATIVE_a_raising_engine_answers_error_with_the_words(client, monkeypatch):
    monkeypatch.setattr(RN, "strip", lambda now, **k: 1 / 0)
    r = client.get(C.API_RUNNERS_PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200 and r.json() == {"state": "error", "text": C.RUNNERS_ERROR_TEXT}


def test_NEGATIVE_nan_is_scrubbed_on_the_wire(client, monkeypatch):
    monkeypatch.setattr(RN, "strip", lambda now, **k: {"state": "ok", "rows": [{"symbol": "X", "run_pct": float("nan"),
                                                                                "today_pct": float("inf")}]})
    r = client.get(C.API_RUNNERS_PATH, headers={"X-User-Email": OWNER})
    body = _strict(r.text)
    assert body["rows"][0]["run_pct"] is None and body["rows"][0]["today_pct"] is None


def test_NEGATIVE_store_fault_is_error_never_500(client):
    client.world.c[ST.SCAN].fail = True
    r = client.get(C.API_RUNNERS_PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200 and r.json()["state"] == "error" and r.json()["text"] == C.RUNNERS_ERROR_TEXT


def test_the_body_is_built_off_the_event_loop(monkeypatch):
    seen = []
    real = asyncio.to_thread

    async def spy(fn, *a, **k):
        seen.append(fn.__name__)
        return await real(fn, *a, **k)
    monkeypatch.setattr(API.asyncio, "to_thread", spy)
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: e == OWNER)
    monkeypatch.setattr(RN, "strip", lambda now, **k: {"state": "off"})
    out = asyncio.run(API.gajjala_watch_runners(email=OWNER))
    assert seen == ["_runners_body"] and json.loads(out.body) == {"state": "off"}
    assert ET.key == "America/New_York"
