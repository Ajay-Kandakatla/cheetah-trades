"""📅 Long Term — `GET /chart-maps/long-term` (spec §3.10, WP-RUN, 2026-11-12).

Ajay 2026-11-12, verbatim: "Save this entire list for me. In a New tab - Long Term - …" and "Yeah I wanna find out the
ones that are actually great in fundamentals and growth and sales and no debt but not growing in price action yet.."

PRIMARY OWNER ONLY (C10). NEGATIVES: another email, no email and a direct call (the Depends OBJECT) get exactly
{state: "owner_only", reason, title} with HTTP 200 and `sources.pankaj_closes` is never even called for them; the
owner's GET never builds a week; no Mongo still answers 200; the JSON is NaN-free.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from long_term_list import api as API
from long_term_list import constants as C
from long_term_list import seed as SEED
from long_term_list import sources as SRC
from long_term_list import store as ST
from long_term_list import weekly as WK
from long_term_list import words as W
from tests.test_long_term_list_store import FakeColl
from tests.test_long_term_list_weekly import make_facts

ET = ZoneInfo("America/New_York")
OWNER = "owner@example.com"
OTHER = "doug@example.com"
OWNER_ONLY = {"state": "owner_only", "reason": W.OWNER_ONLY_TEXT, "title": C.TITLE}


def _strict(txt):
    def _refuse(tok):
        raise ValueError(f"non-JSON constant {tok}")
    return json.loads(txt, parse_constant=_refuse)


@pytest.fixture()
def db():
    return {C.RUNS_COLL: FakeColl(C.RUNS_COLL), C.FORWARD_COLL: FakeColl(C.FORWARD_COLL),
            C.CLAIMS_COLL: FakeColl(C.CLAIMS_COLL)}


@pytest.fixture()
def wired(monkeypatch, db):
    """Owner = OWNER only; Mongo = the fakes; the 🧭 closes counted; building a week is a failure."""
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setattr(ST, "_db", lambda: db)
    calls = []

    def _closes(symbols, now=None):
        calls.append(list(symbols))
        return {"TSM": {"close": 405.49, "date": "2026-11-12"}, "META": {"close": float("nan"), "date": "2026-11-12"}}
    monkeypatch.setattr(SRC, "pankaj_closes", _closes)

    def _never(*a, **k):
        raise AssertionError("the GET built a week")
    monkeypatch.setattr(WK, "run", _never)
    monkeypatch.setattr(SRC, "load_all", _never)
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    c.closes_calls = calls
    return c


def test_path_is_the_constant():
    assert C.API_PATH == "/chart-maps/long-term"
    assert any(getattr(r, "path", None) == C.API_PATH for r in API.router.routes)


# ── owner-only ────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("headers", [{"X-User-Email": OTHER}, {}, {"X-User-Email": "  "}])
def test_NEGATIVE_anyone_else_gets_exactly_owner_only(wired, headers):
    r = wired.get(C.API_PATH, headers=headers)
    assert r.status_code == 200
    body = _strict(r.text)
    assert body == OWNER_ONLY and set(body) == {"state", "reason", "title"}
    assert wired.closes_calls == []                                      # NEG: never even called
    assert "Pankaj" not in r.text and "TSM" not in r.text


def test_NEGATIVE_a_direct_call_with_the_depends_object_is_a_non_owner(wired):
    from fastapi.params import Depends as DependsParam
    out = asyncio.run(API.long_term(email=DependsParam()))
    assert out == OWNER_ONLY
    assert asyncio.run(API.long_term()) == OWNER_ONLY
    assert wired.closes_calls == []


def test_owner_gets_seed_only_before_the_first_run(wired):
    r = wired.get(C.API_PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200
    body = _strict(r.text)                                                # NEG: NaN close scrubbed
    assert body["state"] == "seed_only" and body["title"] == C.TITLE
    rows = [x for c in body["categories"] for x in c["rows"]] + body["changed"]
    assert len(rows) == 109 and len({x["symbol"] for x in rows}) == 109
    assert len(wired.closes_calls) == 1 and sorted(wired.closes_calls[0]) == sorted(SEED.pankaj_entries(SEED.load()))
    assert any(z["symbol"] == "TSM" for z in body["zones"]["at_zone"])


def test_owner_gets_ready_from_a_stored_run(wired, db, monkeypatch):
    monkeypatch.setattr(WK, "_build_facts", lambda src, saved, seed: make_facts("2026-11-13"))
    out = WK._build(datetime(2026, 11, 13, 16, 40, tzinfo=ET), "2026-11-13", "2026-W46", ST.colls(db), {},
                    "test", lambda n: {})
    ST.insert_run(db[C.RUNS_COLL], out["run"])
    r = wired.get(C.API_PATH, headers={"X-User-Email": OWNER})
    body = _strict(r.text)
    assert body["state"] == "ready" and body["as_of"]["week"] == "2026-W46"


def test_owner_with_no_mongo_still_answers(wired, monkeypatch):
    monkeypatch.setattr(ST, "_db", lambda: None)
    r = wired.get(C.API_PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200 and _strict(r.text)["state"] == "seed_only"


def test_owner_with_a_changed_seed_gets_error_with_a_reason(wired, monkeypatch):
    def _changed(*a, **k):
        raise SEED.SeedChanged("sha differs")
    monkeypatch.setattr(SEED, "load", _changed)
    r = wired.get(C.API_PATH, headers={"X-User-Email": OWNER})
    body = _strict(r.text)
    assert r.status_code == 200 and body["state"] == "error" and "sha differs" in body["reason"]


def test_owner_when_the_closes_raise_still_answers(wired, monkeypatch):
    def _boom(symbols, now=None):
        raise RuntimeError("cache down")
    monkeypatch.setattr(SRC, "pankaj_closes", _boom)
    r = wired.get(C.API_PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200 and _strict(r.text)["state"] == "seed_only"


def test_the_route_is_registered_in_main():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "main.py").read_text()
    i = src.index("app.include_router(growth_router)")
    assert "from long_term_list.api import router as long_term_router" in src[i:i + 400]
    assert "app.include_router(long_term_router)" in src[i:i + 400]


def test_source_gates_with_is_primary_admin_and_maybe_current_user():
    import inspect
    src = inspect.getsource(API)
    assert "is_primary_admin" in src and "Depends(maybe_current_user)" in src
    assert "asyncio.to_thread" in src
    assert "load_all(" not in src and "weekly" not in src.split('"""', 2)[2]   # NEG: the GET never builds
