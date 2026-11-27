"""📅 Runners — the two ×, both directions (spec watchrun rev 2 §3.3 [C4], WP-1, 2026-11-26).

The roster's × has its own route `DELETE C.API_RUNSEAT_PATH` that calls ONLY `runseat.dismiss`; the plain DELETE
(`C.API_SYMBOL_PATH`) is byte-unchanged and never touches the runners doc. NEGATIVES are the point.
"""
from __future__ import annotations

import copy
import inspect
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps.gajjala_watch import allrules as R
from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import auto as A
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import runseat as RS
from chart_maps.gajjala_watch import store as WST
from tests.test_gajjala_watch_allrules_2026_11_24 import armed, rules_doc, world as rworld
from tests.test_gajjala_watch_auto_2026_11_17 import fake_db, scan
from tests.test_gajjala_watch_build_2026_11_15 import S, at

OWNER = "owner@example.com"
UTC = timezone.utc
RUN_DAY = date(2026, 11, 12)                                          # the market day before S (Fri 11-13)


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def _seat(db, *syms, run_day=RUN_DAY):
    db[C.COLL_LIST].docs[C.RUNNERS_DOC_ID] = {
        "_id": C.RUNNERS_DOC_ID, "rev": 1, "dismissed": [], "removed": [], "processed": {}, "pending": [],
        "answers": {}, "not_seated": [],
        "entries": [{"symbol": s, "rule": "day", "run_day": run_day.isoformat(), "first_run_day": run_day.isoformat(),
                     "runs": [{"date": run_day.isoformat(), "rule": "day", "run_pct": 75.0, "peak_et": "10:00"}],
                     "added_at": datetime(2026, 11, 13, 9, 5, tzinfo=UTC), "seated_session": S.isoformat(),
                     "reading": "after_aplus"} for s in syms]}
    return db


@pytest.fixture()
def client(monkeypatch):
    import ollama_chat.api as OA
    db = fake_db(manual=("OMH", "XYZ"))
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setattr(CO, "_db", lambda: db)
    monkeypatch.setattr(CO, "loop_reads_soon", lambda now: True)
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    c.db = db
    return c


def _calls(monkeypatch):
    seen = []
    for mod, name in ((WST, "remove"), (A, "dismiss"), (R, "dismiss"), (RS, "dismiss")):
        real = getattr(mod, name)

        def rec(*a, _real=real, _n=f"{mod.__name__.rsplit('.', 1)[-1]}.{name}", **k):
            seen.append(_n)
            return _real(*a, **k)
        monkeypatch.setattr(mod, name, rec)
    return seen


# ── (a) the plain DELETE never touches the runners list ──────────────────────────────────────────────────────────
def test_a_plain_delete_on_a_seated_name_never_calls_runseat(client, monkeypatch):
    _seat(client.db, "XYZ")
    before = copy.deepcopy(client.db[C.COLL_LIST].docs[C.RUNNERS_DOC_ID])
    seen = _calls(monkeypatch)
    r = client.delete(C.API_SYMBOL_PATH.format(symbol="XYZ"), headers={"X-User-Email": OWNER})
    assert r.status_code == 200 and r.json()["state"] == "removed"
    assert "runseat.dismiss" not in seen and "store.remove" in seen
    assert client.db[C.COLL_LIST].docs[C.RUNNERS_DOC_ID] == before
    src = inspect.getsource(API.gajjala_watch_remove)
    assert "runseat" not in src.lower() and "RUNSEAT" not in src


# ── (b) the roster DELETE never touches the owner / 🤖 / ✅ docs ─────────────────────────────────────────────────
def test_b_roster_delete_only_pulls_the_runners_entry(client, monkeypatch):
    db = _seat(client.db, "XYZ")
    db[C.COLL_LIST].docs[C.AUTO_DOC_ID] = {"_id": C.AUTO_DOC_ID, "rev": 4, "session": S.isoformat(),
                                           "entries": [], "dismissed": [], "removed": []}
    db[C.COLL_LIST].docs[C.RULES_DOC_ID] = {"_id": C.RULES_DOC_ID, "rev": 2, "entries": [], "dismissed": []}
    others = {k: copy.deepcopy(v) for k, v in db[C.COLL_LIST].docs.items() if k != C.RUNNERS_DOC_ID}
    tiles = copy.deepcopy(db[C.COLL_TILES].docs)
    seen = _calls(monkeypatch)
    monkeypatch.setattr(RS, "_win_isos", lambda session: [RUN_DAY.isoformat(), S.isoformat(), str(session)[:10]])
    r = client.delete(C.API_RUNSEAT_PATH.format(symbol="xyz"), headers={"X-User-Email": OWNER})
    body = r.json()
    assert r.status_code == 200 and body["state"] == "dismissed" and body["text"] == "XYZ removed from 📅 Runners"
    assert seen == ["runseat.dismiss"]
    assert {k: v for k, v in db[C.COLL_LIST].docs.items() if k != C.RUNNERS_DOC_ID} == others
    assert db[C.COLL_TILES].docs == tiles and "XYZ" in db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"]
    doc = db[C.COLL_LIST].docs[C.RUNNERS_DOC_ID]
    assert doc["entries"] == []
    assert [(x["symbol"], x["reason"], x["entry"]["run_day"]) for x in doc["removed"]] == [
        ("XYZ", "dismissed", RUN_DAY.isoformat())]
    d = doc["dismissed"][0]
    assert (d["symbol"], d["run_day"], d["via"]) == ("XYZ", RUN_DAY.isoformat(), C.RUNNERS_SEAT_VIA)
    src = inspect.getsource(API.gajjala_watch_runseat_remove) + inspect.getsource(API._runseat_x)
    assert "ST.remove" not in src and "AUTO" not in src and "RULES" not in src and "_dismiss(" not in src


def test_roster_x_blocks_that_run_day_and_that_session_a_later_day_seats_again():
    doc = {"dismissed": [{"symbol": "XYZ", "session": S.isoformat(), "run_day": RUN_DAY.isoformat(),
                          "via": C.RUNNERS_SEAT_VIA}]}
    blk = RS.blocked(doc, {}, {}, date(2026, 11, 17))
    assert ("XYZ", RUN_DAY.isoformat()) in blk and ("XYZ", S.isoformat()) in blk
    assert ("XYZ", "2026-11-16") not in blk                            # a later qualifying day seats again


# ── (c) the roster × never blocks a 🤖 / ✅ seat ─────────────────────────────────────────────────────────────────
def test_c_roster_x_at_0900_then_the_rules_step_at_1030_seats(monkeypatch):
    db = _seat(fake_db(manual=()), "XYZ")
    monkeypatch.setattr(RS, "_win_isos", lambda session: [RUN_DAY.isoformat(), S.isoformat()])
    out = RS.dismiss("XYZ", by=OWNER, db=db, now=at(S, 9, 0))
    assert out["state"] == "dismissed"
    assert C.RULES_DOC_ID not in db[C.COLL_LIST].docs and C.AUTO_DOC_ID not in db[C.COLL_LIST].docs
    st = rworld(trackers=[armed("XYZ")], scans=[scan("XYZ", 5e6)])
    res = R.step(at(S, 10, 30), S, db=db, manual=[], stores=st, auto_prior={})
    assert "XYZ" in res["symbols"] and "XYZ" in [e["symbol"] for e in rules_doc(db)["entries"]]


# ── (d) the gate, "absent", "error" ──────────────────────────────────────────────────────────────────────────────
def test_d_non_owner_gets_404_before_any_read(client, monkeypatch):
    seen = _calls(monkeypatch)
    reads = []
    monkeypatch.setattr(RS, "read_doc", lambda cs: reads.append(1) or {})
    for h in ({"X-User-Email": "someone@else.com"}, {}):
        r = client.delete(C.API_RUNSEAT_PATH.format(symbol="XYZ"), headers=h)
        assert r.status_code in (401, 404)
    assert seen == [] and reads == []


def test_d_a_name_not_seated_is_absent_and_nothing_written(client):
    _seat(client.db, "AAA")
    before = copy.deepcopy(client.db[C.COLL_LIST].docs)
    w0 = client.db[C.COLL_LIST].writes
    r = client.delete(C.API_RUNSEAT_PATH.format(symbol="XYZ"), headers={"X-User-Email": OWNER})
    assert r.json() == {"state": "absent", "symbol": "XYZ", "text": "XYZ is not on 📅 Runners"}
    assert client.db[C.COLL_LIST].docs == before and client.db[C.COLL_LIST].writes == w0


def test_d_a_missing_module_or_the_switch_off_answers_error(client, monkeypatch):
    monkeypatch.setattr(C, "RUNSEAT_MODULE", "chart_maps.gajjala_watch.no_such_module")
    r = client.delete(C.API_RUNSEAT_PATH.format(symbol="XYZ"), headers={"X-User-Email": OWNER})
    assert r.json()["state"] == "error" and r.json()["text"] == C.RUNNERS_SEAT_X_TEXT["error"]
    monkeypatch.setattr(C, "RUNSEAT_MODULE", "chart_maps.gajjala_watch.runseat")
    monkeypatch.setattr(C, "RUNNERS_SEAT_ON", False)
    r = client.delete(C.API_RUNSEAT_PATH.format(symbol="XYZ"), headers={"X-User-Email": OWNER})
    assert r.json()["state"] == "error"


def test_dismiss_never_raises_and_a_non_ticker_is_absent_without_a_read(monkeypatch):
    reads = []
    monkeypatch.setattr(RS, "read_doc", lambda cs: reads.append(1) or {})
    assert RS.dismiss("not a ticker!", by=OWNER, db=fake_db())["state"] == "absent" and reads == []
    db = fake_db()
    db[C.COLL_LIST].fail = True
    monkeypatch.undo()
    assert RS.dismiss("XYZ", by=OWNER, db=db, now=at(S, 9, 0))["state"] == "error"
