"""🧪 Gajjala · Audited — the three routes (BUILD_SPEC gg-audited §3.7 / WP-D, 2026-11-01).

Ajay 2026-11-01, verbatim: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited  So we can keep track of improvements on this tab".

GET /chart-maps/gajjala-audited builds with variant=GGA (no today read on ANY sub since 2026-11-05 [C2]); the POST
scan is owner-only (stealth 404) and is 🚩 Gajjala's own on-open pass — OD.request() with NO variant (the overlay
rides GG5's pass; there is no audited child slot); the entry tape reads ST.for_variant(GGA), 404 on an unknown id,
200 with the fault note on a raising build. NEGATIVES: non-owner 404 whatever the body, the Depends OBJECT is a
non-owner, no today read off 🏁, the 🚩 and 1-minute routes keep their own variant.
"""
from __future__ import annotations

import inspect

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import on_demand as OD
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import tape as TP
from chart_maps.gajjala import variant as V
from tests.test_gajjala_tab import run_route

OWNER = "ajaykandakatla@gmail.com"
DOUG = "doug@example.com"
BASE = "/chart-maps/gajjala-audited"


class Rec:
    """A recording stand-in: every call's (args, kwargs) kept; returns `ret` or raises `exc`."""

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
def build(monkeypatch):
    rec = Rec(ret={"tab": "gajjala_audited", "tiles": []})
    monkeypatch.setattr(GT, "build", rec)
    return rec


@pytest.fixture
def today(monkeypatch):
    rec = Rec(ret={"today": True})
    monkeypatch.setattr(LG, "today_read", rec)
    return rec


def _hdr(email):
    return {"X-User-Email": email}


# ── the route table ──────────────────────────────────────────────────────────────────────────────────────────────
def test_the_three_routes_live_under_the_variant_api_base():
    from chart_maps import api as API
    got = {(r.path, tuple(sorted(r.methods))) for r in API.router.routes if getattr(r, "path", "").startswith(BASE)}
    assert got == {(BASE, ("GET",)), (BASE + "/scan", ("POST",)), (BASE + "/entry-tape", ("GET",))}
    assert V.GGA.api_base == BASE
    for p in (BASE, BASE + "/scan", BASE + "/entry-tape?id=x"):
        assert V.for_api_base(p) is V.GGA


def test_NEGATIVE_the_get_never_names_the_trigger_or_the_tape_and_the_post_is_gated():
    from chart_maps import api as API
    get_src = inspect.getsource(API.chart_maps_gajjala_audited)
    assert "on_demand" not in get_src and "entry_tape" not in get_src
    assert "variant=V.GGA" in get_src
    post_src = inspect.getsource(API.chart_maps_gajjala_audited_scan)
    assert "is_admin_email(" in post_src and "404" in post_src
    assert "variant=" not in post_src.split('"""')[-1]                     # the code (not the docstring) names no variant


def test_the_docstrings_say_shadow_and_unmeasured():
    from chart_maps import api as API
    for fn in (API.chart_maps_gajjala_audited, API.chart_maps_gajjala_audited_scan,
               API.chart_maps_gajjala_audited_entry_tape):
        doc = (fn.__doc__ or "").lower()
        assert "shadow" in doc and "never sent" in doc, fn.__name__
    assert "UNMEASURED" in API.chart_maps_gajjala_audited.__doc__
    assert "UNMEASURED" in API.chart_maps_gajjala_audited_entry_tape.__doc__


# ── GET /chart-maps/gajjala-audited ─────────────────────────────────────────────────────────────────────────────
def test_get_builds_with_the_audited_variant_and_no_today_read_off_the_track_record(client, build, today):
    r = client.get(BASE, params={"sub": "bull_flag", "tf": "15m", "focus": "ABCD", "sort": "change", "limit": 7},
                   headers=_hdr(DOUG))
    assert r.status_code == 200 and r.json() == {"tab": "gajjala_audited", "tiles": []}
    (a, k), = build.calls
    assert a == ("bull_flag",)
    assert k["variant"] is V.GGA
    assert k["tf"] == "15m" and k["focus"] == "ABCD" and k["sort"] == "change" and k["limit"] == 7
    assert k["today"] is None and today.calls == []                       # NEGATIVE: Mongo-only off 🏁


def test_get_on_the_track_record_does_no_today_read(client, build, today):
    """2026-11-05 [C2] (SPEC gg-track-parity §3.3) — the 🧪 🏁 lists 🚩's own A+ rows; a today read over the SHARED
    store would re-pay 🚩's whole today read (🧠 + A+) on every refresh. Default: none (HIS CALL #28)."""
    r = client.get(BASE, params={"sub": GC.LEDGER_SUB, "span": "10d"}, headers=_hdr(DOUG))
    assert r.status_code == 200
    assert today.calls == []                                               # NEGATIVE: never ANY store's today read
    (_a, bk), = build.calls
    assert bk["today"] is None and bk["variant"] is V.GGA and bk["span"] == "10d"
    from chart_maps import api as API
    assert "today_read" not in inspect.getsource(API.chart_maps_gajjala_audited).split('"""')[-1]


def test_NEGATIVE_a_raising_today_read_still_serves_the_board(client, build, monkeypatch):
    monkeypatch.setattr(LG, "today_read", Rec(exc=RuntimeError("down")))
    r = client.get(BASE, params={"sub": GC.LEDGER_SUB}, headers=_hdr(DOUG))
    assert r.status_code == 200
    (_a, k), = build.calls
    assert k["today"] is None and k["variant"] is V.GGA


@pytest.mark.parametrize("email,owner", [(OWNER, True), (DOUG, False)])
def test_get_owner_flag_is_the_primary_admin(client, build, monkeypatch, email, owner):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: e == OWNER)
    client.get(BASE, headers=_hdr(email))
    assert build.calls[-1][1]["owner"] is owner


def test_NEGATIVE_a_limit_past_the_max_is_refused_never_widened(client, build):
    assert client.get(BASE, params={"limit": GC.TILE_LIMIT_MAX + 1}, headers=_hdr(DOUG)).status_code == 422
    assert build.calls == []


def test_NEGATIVE_a_direct_call_coerces_the_query_objects(build, today):
    from chart_maps import api as API
    resp = run_route(API.chart_maps_gajjala_audited())                    # every arg = its Query / Depends OBJECT
    assert resp.status_code == 200
    (a, k), = build.calls
    assert a == ("",) and k["tf"] == "" and k["span"] == "" and k["owner"] is False
    assert k["limit"] == GC.TILE_LIMIT_DEFAULT and k["variant"] is V.GGA and today.calls == []


def test_NEGATIVE_the_flag_and_one_minute_routes_keep_their_own_variant(client, build):
    client.get("/chart-maps/gajjala", headers=_hdr(DOUG))
    client.get("/chart-maps/gajjala-1m", headers=_hdr(DOUG))
    assert len(build.calls) == 2
    assert build.calls[0][1].get("variant") in (None, V.GG5)
    assert build.calls[1][1].get("variant") is V.GG1
    assert all(c[1].get("variant") is not V.GGA for c in build.calls)


# ── POST /chart-maps/gajjala-audited/scan ───────────────────────────────────────────────────────────────────────
@pytest.fixture
def od(monkeypatch):
    rec = Rec(ret={"status": "started"})
    monkeypatch.setattr(OD, "request", rec)
    return rec


def test_post_owner_starts_the_flag_pass_with_no_variant(client, od, monkeypatch):
    import auth
    monkeypatch.setattr(auth, "is_admin_email", lambda e: e == OWNER)
    r = client.post(BASE + "/scan", headers=_hdr(OWNER))
    assert r.status_code == 200 and r.json() == {"status": "started"}
    assert od.calls == [((), {})]                                         # GG5's on-open pass — the overlay rides it


def test_NEGATIVE_the_post_never_asks_for_an_audited_or_one_minute_slot(client, od, monkeypatch):
    import auth
    monkeypatch.setattr(auth, "is_admin_email", lambda e: e == OWNER)
    client.post(BASE + "/scan", headers=_hdr(OWNER))
    (_a, k), = od.calls
    assert k.get("variant") not in (V.GGA, V.GG1)


@pytest.mark.parametrize("body", [None, {"symbol": "ABCD"}, b"{not json"])
def test_NEGATIVE_a_non_owner_gets_404_whatever_the_body(client, od, monkeypatch, body):
    import auth
    monkeypatch.setattr(auth, "is_admin_email", lambda e: e == OWNER)
    if isinstance(body, bytes):
        r = client.post(BASE + "/scan", content=body, headers=dict(_hdr(DOUG), **{"Content-Type": "application/json"}))
    else:
        r = client.post(BASE + "/scan", json=body, headers=_hdr(DOUG))
    assert r.status_code == 404 and od.calls == []


def test_NEGATIVE_a_direct_call_with_the_depends_object_is_a_404(od, monkeypatch):
    import auth
    from fastapi import HTTPException
    from chart_maps import api as API
    seen = []
    monkeypatch.setattr(auth, "is_admin_email", lambda e: seen.append(e) or False)
    with pytest.raises(HTTPException) as e:
        run_route(API.chart_maps_gajjala_audited_scan())
    assert e.value.status_code == 404 and seen == [""] and od.calls == []


# ── GET /chart-maps/gajjala-audited/entry-tape ──────────────────────────────────────────────────────────────────
ID = "2026-11-03|ABCD|bull_flag|aplus"


def test_entry_tape_reads_the_audited_store(client, monkeypatch):
    rec = Rec(ret={"id": ID, "bars": []})
    monkeypatch.setattr(TP, "entry_tape", rec)
    r = client.get(BASE + "/entry-tape", params={"id": ID, "lite": 1})
    assert r.status_code == 200 and r.json() == {"id": ID, "bars": []}
    (a, k), = rec.calls
    assert a == (ID,) and k["lite"] is True
    assert k["store"] is ST.for_variant(V.GGA)
    assert k["store"] is not ST.default() and k["store"] is not ST.for_variant(V.GG1)


def test_NEGATIVE_an_unknown_id_is_a_404_with_the_served_words(client, monkeypatch):
    monkeypatch.setattr(TP, "entry_tape", Rec(ret=None))
    r = client.get(BASE + "/entry-tape", params={"id": "nope"})
    assert r.status_code == 404 and r.json() == {"detail": TP.ENTRY_TAPE_WORDS["not_found"]}


def test_NEGATIVE_a_raising_build_serves_200_with_the_audited_fault_note(client, monkeypatch):
    monkeypatch.setattr(TP, "entry_tape", Rec(exc=RuntimeError("boom")))
    fault = Rec(ret={"id": ID, "fault": True})
    monkeypatch.setattr(TP, "fault_payload", fault)
    r = client.get(BASE + "/entry-tape", params={"id": ID})
    assert r.status_code == 200 and r.json() == {"id": ID, "fault": True}
    (a, k), = fault.calls
    assert a == (ID,) and k["lite"] is False and k["variant"] is V.GGA


def test_NEGATIVE_a_direct_entry_tape_call_is_an_empty_id(monkeypatch):
    from chart_maps import api as API
    rec = Rec(ret=None)
    monkeypatch.setattr(TP, "entry_tape", rec)
    resp = run_route(API.chart_maps_gajjala_audited_entry_tape())
    assert resp.status_code == 404
    (a, k), = rec.calls
    assert a == ("",) and k["lite"] is False and k["store"] is ST.for_variant(V.GGA)
