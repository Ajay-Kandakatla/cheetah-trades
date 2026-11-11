"""🥇 Luk's — the two GET routes (BUILD SPEC luk-tab §3.11 / WP-C, 2026-11-01).

Ajay 2026-11-01, verbatim: "look at other winners of US stocks champion ship and pic the next best one like Gajjala.
Implement their strategy please if they have online resources. ... I need something like Gajjlala that is exposed".

GET /chart-maps/luk builds `luk.tab.build` (coerced args) + the ONE live fan-out for the shown tiles; a raising build
serves 200 with the fault note. GET /chart-maps/luk/entry-tape serves `luk.tape.entry_tape`, 404 for an unknown id, 200
with the fault payload on a raise. NEGATIVES: exactly ONE non-GET route under the Luk base — the owner's scan POST
(REVERSED 2026-11-11 by his word, Ajay: "Can you put an ondeman scan button for Luk' scans too"; its tests live in
tests/test_luk_scan_now_2026_11_11.py); the 🚩 / 1-minute / audited routes are the same set and still build with their
own variant; the Luk GET never touches gajjala.tab.build nor names the trigger.
"""
from __future__ import annotations

import inspect

import pytest

from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import tape as GTP
from chart_maps.gajjala import variant as V
from chart_maps.luk import tab as LT
from chart_maps.luk import tape as LTP
from chart_maps.luk.variant import LUK

BASE = "/chart-maps/luk"
DOUG = {"X-User-Email": "doug@example.com"}
GG_ROUTES = {("/chart-maps/gajjala", "GET"), ("/chart-maps/gajjala/scan", "POST"),
             ("/chart-maps/gajjala/entry-tape", "GET"), ("/chart-maps/gajjala-1m", "GET"),
             ("/chart-maps/gajjala-1m/scan", "POST"), ("/chart-maps/gajjala-1m/entry-tape", "GET"),
             ("/chart-maps/gajjala-audited", "GET"), ("/chart-maps/gajjala-audited/scan", "POST"),
             ("/chart-maps/gajjala-audited/entry-tape", "GET"), ("/chart-maps/gajjala/broker-flags", "GET"),
             ("/chart-maps/gajjala/broker-flags", "POST"), ("/chart-maps/gajjala/broker-flags/{symbol}", "DELETE")}


class Rec:
    def __init__(self, ret=None, exc=None):
        self.calls, self.ret, self.exc = [], ret, exc

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        if self.exc is not None:
            raise self.exc
        return self.ret


@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps import api as API
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app)


@pytest.fixture
def live(monkeypatch):
    from chart_maps import board as board_mod
    snap, attach = Rec(ret={"AAA": {"price": 1.0}}), Rec(ret={})
    monkeypatch.setattr(board_mod, "_live_snapshot", snap)
    monkeypatch.setattr(board_mod, "attach_live_now", attach)
    return snap, attach


def _routes():
    from chart_maps import api as API
    out = set()
    for r in API.router.routes:
        for m in getattr(r, "methods", None) or ():
            out.add((getattr(r, "path", ""), m))
    return out


# ── the route table ────────────────────────────────────────────────────────────────────────────────────────────────
def test_two_gets_and_the_owner_scan_post_live_under_the_variant_api_base():
    # WIDENED 2026-11-11 (Ajay: "Can you put an ondeman scan button for Luk' scans too"): + POST /chart-maps/luk/scan
    got = {(p, m) for p, m in _routes() if p == BASE or p.startswith(BASE + "/")}
    assert got == {(BASE, "GET"), (BASE + "/entry-tape", "GET"), (BASE + "/scan", "POST")}
    assert LUK.api_base == BASE


def test_the_one_luk_post_is_the_owner_scan_route(client, monkeypatch):
    # REVERSED 2026-11-11 (was test_NEGATIVE_no_post_or_scan_route_exists_for_luk — HIS CALL #20 answered by his word)
    import auth
    from chart_maps.luk import on_demand as LOD
    assert [(p, m) for p, m in _routes() if p.startswith(BASE) and m != "GET"] == [(BASE + "/scan", "POST")]
    calls = []
    monkeypatch.setattr(auth, "is_admin_email", lambda e: e == "owner@example.com")
    monkeypatch.setattr(LOD, "request", lambda *a, **k: calls.append(1) or {})
    assert client.post(BASE + "/scan", headers=DOUG).status_code == 404               # NEGATIVE: Doug → stealth 404
    assert calls == []                                                               # … and the trigger never ran
    assert client.post(BASE, headers=DOUG).status_code == 405                        # NEGATIVE: the board stays a GET
    assert client.get(BASE + "/scan", headers=DOUG).status_code in (404, 405)        # NEGATIVE: no GET trigger


def test_NEGATIVE_the_gajjala_routes_are_the_same_set():
    got = {(p, m) for p, m in _routes() if p.startswith("/chart-maps/gajjala")}
    assert got == GG_ROUTES
    assert V.for_api_base(BASE) is None                                     # GG's registry never names Luk


def test_the_docstrings_say_live_since_the_go_live_unmeasured_and_name_the_shadow_fallback():
    # FLIPPED 2026-11-01 (Ajay: "Lets make it live. also alerts too."): live + the date, the shadow fallback still named
    from chart_maps import api as API
    for fn in (API.chart_maps_luk, API.chart_maps_luk_entry_tape):
        doc = " ".join((fn.__doc__ or "").split())
        assert "live" in doc and "2026-11-01" in doc and "UNMEASURED" in doc, fn.__name__
        assert "shadow = recorded, never sent" in doc, fn.__name__
        assert "Every Luk alert is recorded in SHADOW" not in doc                   # NEGATIVE: the old claim is gone


def test_NEGATIVE_the_luk_get_never_names_gajjala_tab_build_or_a_trigger():
    from chart_maps import api as API
    src = inspect.getsource(API.chart_maps_luk)
    assert "GT.build" not in src and "on_demand" not in src and "entry_tape" not in src
    assert "LT.build(" in src


# ── GET /chart-maps/luk ────────────────────────────────────────────────────────────────────────────────────────────
def test_get_builds_the_luk_board_with_coerced_args(client, monkeypatch, live):
    build = Rec(ret={"tab": "luk", "tiles": []})
    monkeypatch.setattr(LT, "build", build)
    r = client.get(BASE, params={"sub": "potent", "span": "10d", "focus": "abc", "limit": 7}, headers=DOUG)
    assert r.status_code == 200 and r.json() == {"tab": "luk", "tiles": []}
    (a, k), = build.calls
    assert a == ("potent",) and k["span"] == "10d" and k["focus"] == "abc" and k["limit"] == 7
    assert k["owner"] is False
    assert live[0].calls == [] and live[1].calls == []                     # NEGATIVE: no tiles → no live fan-out


def test_get_makes_the_one_live_fan_out_for_shown_tiles(client, monkeypatch, live):
    tiles = [{"symbol": "AAA", "lines": []}]
    monkeypatch.setattr(LT, "build", Rec(ret={"tab": "luk", "tiles": tiles}))
    r = client.get(BASE, headers=DOUG)
    assert r.status_code == 200
    (a, _k), = live[0].calls
    assert a == (tiles,)
    (a2, k2), = live[1].calls
    assert a2[0] == tiles and k2["live"] == {"AAA": {"price": 1.0}}


def test_a_raising_build_serves_200_with_the_fault_note(client, monkeypatch, live):
    monkeypatch.setattr(LT, "build", Rec(exc=RuntimeError("mongo down")))
    r = client.get(BASE, params={"sub": "leader"})
    assert r.status_code == 200
    body = r.json()
    assert body["fault"] is True and body["fault_text"] == LT.FAULT_TEXT and body["sub"] == "leader"
    assert body["tab"] == "luk" and body["title"] == LT.TITLE


def test_a_raising_live_fan_out_still_serves(client, monkeypatch):
    from chart_maps import board as board_mod
    monkeypatch.setattr(LT, "build", Rec(ret={"tab": "luk", "tiles": [{"symbol": "AAA"}]}))
    monkeypatch.setattr(board_mod, "_live_snapshot", Rec(exc=RuntimeError("tape down")))
    monkeypatch.setattr(board_mod, "attach_live_now", Rec(exc=RuntimeError("tape down")))
    r = client.get(BASE)
    assert r.status_code == 200 and r.json()["tiles"] == [{"symbol": "AAA"}]


def test_a_direct_call_with_query_objects_is_coerced(monkeypatch, live):
    from chart_maps import api as API
    from tests.test_gajjala_tab import run_route
    build = Rec(ret={"tab": "luk", "tiles": []})
    monkeypatch.setattr(LT, "build", build)
    resp = run_route(API.chart_maps_luk())
    assert resp.status_code == 200
    (a, k), = build.calls
    assert a == ("",) and k["span"] == "" and k["focus"] == "" and isinstance(k["limit"], int)
    assert k["owner"] is False                                              # the Depends OBJECT is a non-owner


def test_the_real_build_serves_through_the_route(client, monkeypatch, live):
    from tests.test_luk_tab import NOW, fixture_store
    st = fixture_store()
    real = LT.build
    monkeypatch.setattr(LT, "build", lambda sub, **k: real(sub, now=NOW, store=st, **k))
    body = client.get(BASE, params={"sub": "pullback_reversal"}).json()
    assert body["tab"] == "luk" and body["variant"]["push_mode"] == "live"         # FLIPPED 2026-11-01 (go-live)
    assert [s["key"] for s in body["subs"]] == [k for k, _e, _l in __import__("chart_maps.luk.constants",
                                                                               fromlist=["SUBS"]).SUBS]
    assert body["tiles"] and body["fault"] is False


# ── GET /chart-maps/luk/entry-tape ────────────────────────────────────────────────────────────────────────────────
def test_entry_tape_serves_the_payload(client, monkeypatch):
    rec = Rec(ret={"id": "2026-11-03|AAA|pullback_reversal|aplus", "bars": []})
    monkeypatch.setattr(LTP, "entry_tape", rec)
    r = client.get(BASE + "/entry-tape", params={"id": "2026-11-03|AAA|pullback_reversal|aplus", "lite": 1})
    assert r.status_code == 200 and r.json()["id"] == "2026-11-03|AAA|pullback_reversal|aplus"
    (a, k), = rec.calls
    assert a == ("2026-11-03|AAA|pullback_reversal|aplus",) and k == {"lite": True}


def test_entry_tape_unknown_id_is_404(client):
    r = client.get(BASE + "/entry-tape", params={"id": "not-an-id"})
    assert r.status_code == 404 and r.json()["detail"] == GTP.ENTRY_TAPE_WORDS["not_found"]


def test_entry_tape_raising_build_serves_200_with_the_fault_payload(client, monkeypatch):
    monkeypatch.setattr(LTP, "entry_tape", Rec(exc=RuntimeError("boom")))
    _id = "2026-11-03|AAA|pullback_reversal|aplus"
    r = client.get(BASE + "/entry-tape", params={"id": _id})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == set(LTP.PAYLOAD_KEYS) and body["note"] == GTP.ENTRY_TAPE_WORDS["fault"]


def test_NEGATIVE_the_luk_tape_route_never_reads_a_gajjala_store(client, monkeypatch):
    rec = Rec(ret=None)
    monkeypatch.setattr(LTP, "entry_tape", rec)
    monkeypatch.setattr(GTP, "entry_tape", Rec(exc=AssertionError("the GG tape was read")))
    r = client.get(BASE + "/entry-tape", params={"id": "2026-11-03|AAA|pullback_reversal|aplus"})
    assert r.status_code == 404 and len(rec.calls) == 1
    assert "store" not in rec.calls[0][1]                                   # the Luk module picks its own store


# ── the GG routes' outputs are untouched ──────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_gajjala_gets_still_build_with_their_own_variant(client, monkeypatch, live):
    build = Rec(ret={"tab": "x", "tiles": []})
    monkeypatch.setattr(GT, "build", build)
    luk_build = Rec(exc=AssertionError("the Luk build was called by a GG route"))
    monkeypatch.setattr(LT, "build", luk_build)
    assert client.get("/chart-maps/gajjala", params={"sub": "bull_flag"}).status_code == 200
    assert client.get("/chart-maps/gajjala-audited", params={"sub": "bull_flag"}).status_code == 200
    assert client.get("/chart-maps/gajjala-1m", params={"sub": "bull_flag"}).status_code == 200
    variants = [k.get("variant") for _a, k in build.calls]
    assert variants[0] is None and variants[1] is V.GGA and variants[2] is V.GG1
    assert luk_build.calls == []
