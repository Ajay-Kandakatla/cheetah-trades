"""📅 Long Term — 🔔 `zones.alert` on the owner payload + the GET (pkzone spec §3.7, 2026-11-12).

Ajay 2026-11-12, verbatim: "add an alert list when stocks reach Pankaj's zones and also tell me if you finish the long
term tabs in general". The block is the zone pass's stored session doc (the GET never fetches, never snapshots, never
touches the latch). NEGATIVES: yesterday's pass is never served as live; a non-owner reads nothing; NaN scrubbed;
"dup" never reads as a result.
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from long_term_list import api as API
from long_term_list import constants as C
from long_term_list import payload as P
from long_term_list import sources as SRC
from long_term_list import store as ST
from long_term_list import words as W
from long_term_list import zone_watch as ZW
from tests.test_long_term_list_store import FakeColl
from tests.test_long_term_zone_watch_2026_11_12 import (ENTRIES, ET, MON_PREV, OWNER, SEED, TUE, Closes, FakeLatch,
                                                         FakeState, Sender, Snaps, _env, at, mkdb, snap)

assert _env                                                    # the shared autouse fixture (prefs, owner, no broadcast)
CLOSES = {"TSM": {"close": 405.49, "date": MON_PREV}, "META": {"close": 623.61, "date": MON_PREV}}


def _pass(db, now, prices, closes=None, **kw):
    return ZW.run_pass(now, seed=SEED, snap_fn=Snaps(prices), closes_fn=closes or Closes(
        {"TSM": {"close": 430.0, "date": MON_PREV}, "NVDA": {"close": 200.0, "date": MON_PREV}}),
        db=db, send=Sender(), **kw)


def _alert(day_doc, now, zone_closes=None, session=TUE):
    return P.build_payload(SEED, {}, [], [], zone_closes or {}, now=now, owner=True,
                           zone_live=ZW.serve_state(day_doc, now), zone_day=day_doc,
                           log_session=session)["zones"]["alert"]


def _live_db():
    db = mkdb()
    _pass(db, at(10, 0), {"TSM": snap(405.0, at(9, 59))})
    _pass(db, at(10, 35), {"TSM": snap(406.0, at(10, 30)), "NVDA": snap(166.0, at(10, 34))})
    return db


def test_live_state_today_is_served_live():
    db = _live_db()
    a = _alert(db[C.ZONE_STATE_COLL].docs[TUE], at(10, 36))
    assert a["live"] is True and a["title"] == W.ZONE_ALERT_TITLE
    assert a["as_of_text"] == "Live prints at the 10:35 ET alerts pass"
    assert [(n["symbol"], n["zone"]) for n in a["now"]] == [("TSM", "Agg"), ("NVDA", "C2")]
    assert a["now"][0]["text"] == "406.00 at 10:30 ET · in Pankaj's Agg zone (400–410) · Tier A"
    assert not a["now"][0]["text"].startswith("TSM")                    # the FE prints the ticker
    assert a["empty_text"] is None and a["reason"] is None and a["stale_text"] is None
    assert a["push_text"] == W.zone_push_text()
    assert a["log_title"] == "🔔 Reached one of Pankaj's zones — 11-17"
    assert [(r["symbol"], r["zone"], r["at_text"]) for r in a["log"]] == [("TSM", "Agg", "10:00 ET"),
                                                                       ("NVDA", "C2", "10:35 ET")]
    assert a["log"][0]["text"] == "405.00 reached Pankaj's Agg zone (400–410) · Tier A"
    assert [r["push_text"] for r in a["log"]] == ["rang your phone", "rang your phone"]
    assert a["log_empty_text"] is None


def test_NEGATIVE_yesterdays_state_is_close_basis_and_labelled():
    db = _live_db()
    wed = datetime(2026, 11, 18, 10, 0, tzinfo=ET)
    a = _alert(db[C.ZONE_STATE_COLL].docs[TUE], wed, zone_closes=CLOSES, session=TUE)
    assert a["live"] is False and a["reason"] is None and a["stale_text"] is None
    assert a["as_of_text"] == "At the 11-16 close — no live read now"
    assert [n["symbol"] for n in a["now"]] == ["TSM", "META"]
    assert a["now"][0]["text"] == "in Pankaj's Agg zone (400–410) at the 11-16 close (405.49) · Tier A"


def test_after_hours_clock_closed_is_close_basis():
    db = _live_db()
    a = _alert(db[C.ZONE_STATE_COLL].docs[TUE], at(20, 30), zone_closes=CLOSES)
    assert a["live"] is False and len(a["log"]) == 2                    # the day's log still shows


def test_empty_texts():
    a = _alert(None, at(10, 0))
    assert a["now"] == [] and a["empty_text"] == W.ZONE_NOW_EMPTY
    assert a["log"] == [] and a["log_empty_text"] == "No name reached one of Pankaj's zones on 11-17."
    assert a["as_of_text"] == "No cached closes for Pankaj's names"


def test_log_sort_and_push_text_mapping():
    day = {"session": TUE, "reaches": {}, "results": {}}
    rows = [("META|C1", "META", "C1", "2026-11-17T11:00:00-05:00", "11:00", None, "pushed"),
            ("TSM|Agg", "TSM", "Agg", "2026-11-17T09:35:00-05:00", "09:35", "off", None),
            ("NVDA|C2", "NVDA", "C2", "2026-11-17T09:35:00-05:00", "09:35", None, None),
            ("ASML|Agg", "ASML", "Agg", "2026-11-17T12:00:00-05:00", "12:00", None, "dup"),
            ("INTU|Agg", "INTU", "Agg", "2026-11-17T13:00:00-05:00", "13:00", "window", "no_target")]
    for rkey, sym, zk, iso, hhmm, why, state in rows:
        lo, hi = ENTRIES[sym]["zones"][zk]
        day["reaches"][rkey] = {"symbol": sym, "his_symbol": sym, "zone": zk, "lo": lo, "hi": hi, "price": lo,
                                "at_iso": iso, "at_hhmm": hhmm, "tier": "A", "push_reason": why}
        if state:
            day["results"][rkey] = {"state": state}
    a = _alert(day, datetime(2026, 11, 18, 10, 0, tzinfo=ET))
    assert [r["symbol"] for r in a["log"]] == ["TSM", "NVDA", "META", "ASML", "INTU"]   # time, zone order, seed
    assert [r["push_text"] for r in a["log"]] == ["not sent — phone push is off", W.ZONE_RESULT_MISSING,
                                                  "rang your phone", W.ZONE_RESULT_MISSING,
                                                  "no phone has this alert on"]
    assert W.zone_log_push_text("dup") == W.ZONE_RESULT_MISSING                 # NEG: dup is never a result
    assert W.zone_log_push_text("no_store", "off") == "not sent — the alert store was unreachable"


def test_stale_text_none_without_stale_names_and_nan_scrubbed():
    db = _live_db()
    doc = db[C.ZONE_STATE_COLL].docs[TUE]
    assert doc["n_stale"] == 0 and _alert(doc, at(10, 36))["stale_text"] is None
    doc["rows"]["TSM"]["price"] = float("nan")
    doc["reaches"]["TSM|Agg"]["price"] = float("inf")
    full = P.build_payload(SEED, {}, [], [], {}, now=at(10, 36), owner=True, zone_live=doc, zone_day=doc,
                           log_session=TUE)
    json.dumps(full, allow_nan=False)
    a = full["zones"]["alert"]
    assert "nan" not in json.dumps(a).lower() and "—" in a["now"][0]["text"] and a["log"][0]["text"].startswith("—")


def test_back_compat_keys_unchanged():
    z = P.build_payload(SEED, {}, [], [], CLOSES, now=at(10, 0), owner=True)["zones"]
    assert {"as_of_text", "at_zone", "rows_note", "alert"} == set(z)
    assert z["alert"]["live"] is False and [a["symbol"] for a in z["at_zone"]] == ["TSM", "META"]


# ── the GET ─────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture()
def wired(monkeypatch):
    import ollama_chat.api as OA
    db = {C.RUNS_COLL: FakeColl(C.RUNS_COLL), C.FORWARD_COLL: FakeColl(C.FORWARD_COLL),
          C.CLAIMS_COLL: FakeColl(C.CLAIMS_COLL), C.ZONE_LATCH_COLL: FakeLatch(), C.ZONE_STATE_COLL: FakeState()}
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setattr(ST, "_db", lambda: db)
    monkeypatch.setattr(SRC, "pankaj_closes", lambda symbols, now=None: dict(CLOSES))
    return db


def test_saturday_get_is_close_basis_with_fridays_log(wired):
    fri = "2026-11-20"
    wired[C.ZONE_STATE_COLL].docs[fri] = {"_id": fri, "session": fri, "as_of_hhmm": "16:30", "rows": {},
                                          "reaches": {"TSM|Agg": {"symbol": "TSM", "zone": "Agg", "lo": 400.0,
                                                                  "hi": 410.0, "price": 404.0, "tier": "A",
                                                                  "at_iso": "x", "at_hhmm": "15:10",
                                                                  "push_reason": None}},
                                          "results": {"TSM|Agg": {"state": "pushed"}}}
    out = API.owner_payload(datetime(2026, 11, 21, 11, 0, tzinfo=ET))
    a = out["zones"]["alert"]
    assert a["live"] is False and a["log_title"].endswith("11-20")
    assert [(r["symbol"], r["push_text"]) for r in a["log"]] == [("TSM", "rang your phone")]
    assert wired[C.ZONE_LATCH_COLL].calls == []                         # NEG: the GET never touches the latch
    assert set(wired[C.ZONE_STATE_COLL].calls) == {"find_one"}          # NEG: read only


def test_live_get_today(wired):
    _pass(wired, at(10, 0), {"TSM": snap(405.0, at(9, 59))})
    wired[C.ZONE_LATCH_COLL].calls.clear()
    a = API.owner_payload(at(10, 2))["zones"]["alert"]
    assert a["live"] is True and a["now"][0]["symbol"] == "TSM" and a["log"][0]["push_text"] == "rang your phone"
    assert wired[C.ZONE_LATCH_COLL].calls == []


def test_NEGATIVE_non_owner_reads_nothing(wired, monkeypatch):
    def _never(*a, **k):
        raise AssertionError("zone store read for a non-owner")
    monkeypatch.setattr(ST, "zone_colls", _never)
    monkeypatch.setattr(ST, "zone_state", _never)
    app = FastAPI()
    app.include_router(API.router)
    r = TestClient(app).get(C.API_PATH, headers={"X-User-Email": "doug@example.com"})
    assert r.status_code == 200
    assert r.json() == {"state": "owner_only", "reason": W.OWNER_ONLY_TEXT, "title": C.TITLE}


def test_NEGATIVE_a_raising_zone_store_still_answers(wired, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(ST, "zone_colls", _boom)
    out = API.owner_payload(at(10, 0))
    assert out["state"] == "seed_only" and out["zones"]["alert"]["live"] is False
