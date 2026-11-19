"""👀 Gajjala's Watch — × regressions (spec watchnew2 2026-11-19 §1 "×" / §4 WP-BE-build). No code change expected.

Ajay, verbatim: "The X buttons are not working". Relayed: "When I add a new ticket they are gettinf added in to que but
not active / charts are not loading I amhaving to click on the chips again".

The live read (2026-11-19) proved no backend × defect: every DELETE answered 200, the auto doc `dismissed` holds every
×'d name and none was re-seated. These pins keep it so: his OWN name ×'d (store.remove + auto.dismiss — what the
DELETE route does) is never re-seated by the 🤖 engine on the 🎯 A+ path, the 🧠 potential path or the tracker-only path;
dismiss survives a racing step write; a step refused because dismiss landed recomputes without the name. The one known
gap is pinned AS-IS: dismiss refused `_CAS_TRIES` times answers `error` and the DELETE route answers the store's
`removed` (HIS CALL #9). Reuses the auto test doubles; nothing trades.
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import auto as A
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import store as WST
from tests.test_gajjala_watch_auto_2026_11_17 import (T0, auto_doc, fake_db, rdoc, run, scan, stored, stores,
                                                      tracker)
from tests.test_gajjala_watch_auto_aplus_2026_11_17 import T_GP, marked, mread, stores_ap
from tests.test_gajjala_watch_build_2026_11_15 import S, at

OWNER = "owner@example.com"
BY = "o@example.com"


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def _x(db, sym, now):
    """What the DELETE route does: store.remove, then ALWAYS auto.dismiss."""
    out = WST.remove(sym, by=BY, db=db)
    a = A.dismiss(sym, by=BY, db=db, now=now)
    return out, a


def _aplus():
    return stores_ap(gg5=[mread("GP", marked())]), T_GP, "GP"


def _potential():
    return stores(gg5=[rdoc("AAA")], scans=[scan("AAA", 5e6)]), T0, "AAA"


def _tracker_only():
    return stores(scans=[scan("CCC", 5e6)], trackers=[tracker("CCC", 5e6, first_seen=at(S, 9, 33))]), T0, "CCC"


PATHS = {"aplus": _aplus, "potential": _potential, "tracker_only": _tracker_only}


@pytest.mark.parametrize("path", list(PATHS))
def test_control_without_a_x_the_engine_seats_the_name(path):
    st, now, sym = PATHS[path]()
    db = fake_db(manual=[])
    assert sym in run(db, st, now=now, manual=[])["added"]


@pytest.mark.parametrize("path", list(PATHS))
def test_NEGATIVE_his_own_name_xd_is_never_re_seated_on_the_next_two_steps(path):
    st, now, sym = PATHS[path]()
    db = fake_db(manual=[sym])
    assert sym not in run(db, st, now=now, manual=[sym])["symbols"]                 # his name: never a 🤖 entry
    out, a = _x(db, sym, now)
    assert out["state"] == "removed" and sym not in out["symbols"] and a["state"] == "absent"
    assert sym in stored(db)["dismissed"] and CO.owner_symbols(db) == []
    for m in (1, 2):
        res = run(db, st, now=now + timedelta(minutes=m), manual=[])
        assert sym not in res["symbols"] and sym not in res["added"]
    assert sym not in [e["symbol"] for e in stored(db)["entries"]] and sym in stored(db)["dismissed"]


def test_a_x_on_a_seated_auto_name_pulls_it_and_it_stays_out():
    st, now, sym = _potential()
    db = fake_db(manual=[])
    assert run(db, st, now=now, manual=[])["added"] == [sym]
    out, a = _x(db, sym, now)
    assert out["state"] == "absent" and a["state"] == "dismissed"
    for m in (1, 2):
        assert sym not in run(db, st, now=now + timedelta(minutes=m), manual=[])["symbols"]


def test_dismiss_racing_a_step_write_retries_and_lands():
    db = fake_db(manual=[], auto=auto_doc(rev=4))
    coll = db[C.COLL_LIST]
    real = coll.update_one
    fired = []

    def racing(q, upd, upsert=False):
        if q.get("_id") == C.AUTO_DOC_ID and not fired:
            fired.append(1)
            coll.docs[C.AUTO_DOC_ID]["rev"] = 5                  # a step write lands between dismiss's read and write
        return real(q, upd, upsert)
    coll.update_one = racing
    assert A.dismiss("ZZZ", by=BY, db=db, now=T0)["state"] == "absent"
    d = stored(db)
    assert d["dismissed"] == ["ZZZ"] and d["rev"] == 6
    assert [q.get("rev") for q in coll.updates] == [4, 5]


def test_a_step_refused_because_dismiss_landed_recomputes_without_the_name():
    db = fake_db(manual=[], auto=auto_doc(rev=4))
    coll = db[C.COLL_LIST]
    real = coll.update_one
    fired = []

    def racing(q, upd, upsert=False):
        if q.get("_id") == C.AUTO_DOC_ID and not fired:
            fired.append(1)
            assert A.dismiss("AAA", by=BY, db=db, now=T0)["state"] == "absent"   # his × lands first
        return real(q, upd, upsert)
    coll.update_one = racing
    res = run(db, stores(gg5=[rdoc("AAA")], scans=[scan("AAA", 5e6)]), manual=[])
    d = stored(db)
    assert "AAA" not in res["symbols"] and res["added"] == []
    assert d["entries"] == [] and d["dismissed"] == ["AAA"] and d["rev"] == 5


# ── the known gap, pinned as-is (HIS CALL #9) ────────────────────────────────────────────────────────────────────
def _refusing(db):
    coll = db[C.COLL_LIST]
    real = coll.update_one
    tries = []

    def refuse(q, upd, upsert=False):
        if q.get("_id") == C.AUTO_DOC_ID:
            tries.append(1)
            return SimpleNamespace(upserted_id=None, matched_count=0)
        return real(q, upd, upsert)
    coll.update_one = refuse
    return tries


def test_NEGATIVE_dismiss_refused_every_try_answers_error():
    db = fake_db(manual=["OMH"], auto=auto_doc(rev=1))
    tries = _refusing(db)
    out = A.dismiss("OMH", by=BY, db=db, now=T0)
    assert out["state"] == "error" and len(tries) == WST._CAS_TRIES
    assert stored(db)["dismissed"] == []


def test_NEGATIVE_the_delete_route_then_answers_the_stores_removed_as_is(monkeypatch):
    """KNOWN GAP (HIS CALL #9): his name leaves his list but is not dismissed; the route answers `removed`."""
    import ollama_chat.api as OA
    db = fake_db(manual=["OMH", "NVDA"], auto=auto_doc(rev=1))
    tries = _refusing(db)
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setattr(CO, "_db", lambda: db)
    app = FastAPI()
    app.include_router(API.router)
    out = TestClient(app).delete(C.API_PATH + "/symbols/omh", headers={"X-User-Email": OWNER}).json()
    assert out["state"] == "removed" and out["symbols"] == ["NVDA"] and out["symbol"] == "OMH"
    assert len(tries) == WST._CAS_TRIES and stored(db)["dismissed"] == []
