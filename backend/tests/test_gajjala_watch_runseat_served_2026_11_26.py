"""📅 Runners — what is served: the board's `runners` roster, the row `runner` tag, the track route, the ℹ️ clause
(spec watchrun rev 2 §3.2–§3.3, WP-1, 2026-11-26). NEGATIVES are the point: no runners doc → no key anywhere.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import runners as RN
from chart_maps.gajjala_watch import runseat as RS
from tests.test_gajjala_watch_allrules_payload_2026_11_24 import _board_db, _quiet_broker
from tests.test_gajjala_watch_api_2026_11_15 import FRI_IN
from tests.test_gajjala_watch_newest_2026_11_19 import board  # noqa: F401 — fixture
from tests.test_gajjala_watch_sections_2026_11_22 import spies  # noqa: F401 — fixture

UTC = timezone.utc
SESS = date(2026, 11, 13)
D12, D11, D10 = date(2026, 11, 12), date(2026, 11, 11), date(2026, 11, 10)
OWNER = "owner@example.com"


@pytest.fixture(autouse=True)
def quiet(monkeypatch, board, spies):
    monkeypatch.setattr(PL, "_tags_section", lambda names, s, t: {})
    monkeypatch.setattr(PL, "_float_section", lambda names, s, now, tags: {})
    monkeypatch.setattr(PL, "_levels_section", lambda *a, **k: {})
    monkeypatch.setattr(PL, "_broker_section", _quiet_broker)
    monkeypatch.setattr(RN, "_broker_flags", lambda st: ["FIDX"])
    monkeypatch.setattr(RN, "_store", lambda: None)
    return board


def _entry(sym, run_day, rule="day", pct=75.0):
    run = {"date": run_day.isoformat(), "rule": rule, "run_pct": pct, "peak_et": "10:00"}
    if rule == "aplus":
        run.update(trigger=0.9, high_px=1.17, high_et="10:30", from_et="10:00", to_et="20:00",
                   ring_date=run_day.isoformat(), ring_at_et="09:59")
    return {"symbol": sym, "rule": rule, "run_day": run_day.isoformat(), "first_run_day": run_day.isoformat(),
            "runs": [run], "added_at": datetime(2026, 11, 13, 9, 5, tzinfo=UTC), "seated_session": SESS.isoformat(),
            "reading": "after_aplus"}


def _with_runners(db, entries, **extra):
    db[C.COLL_LIST].docs[C.RUNNERS_DOC_ID] = dict({"_id": C.RUNNERS_DOC_ID, "rev": 1, "entries": list(entries),
                                                    "dismissed": [], "removed": [], "processed": {}, "pending": [],
                                                    "answers": {}, "not_seated": []}, **extra)
    return db


def test_NEGATIVE_no_runners_doc_no_key_and_no_row_tag():
    out = PL.build(FRI_IN, db=_board_db())
    assert out["state"] == "ok" and "runners" not in out
    assert all("runner" not in r for r in out["rows"])


def test_NEGATIVE_a_doc_with_no_entry_in_the_window_serves_no_key():
    out = PL.build(FRI_IN, db=_with_runners(_board_db(), [_entry("OLD", date(2026, 10, 1))]))
    assert "runners" not in out and all("runner" not in r for r in out["rows"])


def test_roster_and_the_row_tag():
    db = _with_runners(_board_db(), [_entry("OMH", D12, pct=176.0), _entry("FIDX", D12, pct=300.0),
                                     _entry("POM", D12, pct=75.4), _entry("GP", D11, "aplus", 30.0)],
                       not_seated=[{"symbol": "HZN", "session": D12.isoformat(), "why": "no_prior_bar",
                                    "text": "HZN 2026-11-12: no daily bar before that session"}])
    out = PL.build(FRI_IN, db=db)
    ro = out["runners"]
    assert ro["state"] == "ok" and ro["n"] == 4 and ro["text"] == "📅 Runners · 4" and ro["folded_default"] is True
    assert [r["symbol"] for r in ro["rows"]] == ["OMH", "POM", "GP", "FIDX"]       # newest run, biggest; 🚫 last
    assert ro["rows"][-1]["broker_text"] is not None
    assert all(r["remove_title"].startswith(f"Remove {r['symbol']} from 📅 Runners") for r in ro["rows"])
    by = {r["symbol"]: r for r in ro["rows"]}
    assert by["OMH"]["on_watch"] is True and by["OMH"]["on_watch_text"] == C.RUNNERS_SEAT_ON_WATCH
    assert by["POM"]["on_watch"] is False and by["POM"]["on_watch_text"] is None
    assert by["OMH"]["day_text"] == "📅 day 2 of 10" and by["OMH"]["seat_text"] == "+176% day"
    assert by["GP"]["seat_text"] == "🎯 +30% from A+" and by["GP"]["day_n"] == 3
    assert ro["not_seated"][0]["why"] == "no_prior_bar" and ro["track_path"] == C.API_RUNTRACK_PATH
    rows = {r["symbol"]: r for r in out["rows"]}
    assert rows["OMH"]["runner"]["day_text"] == "📅 day 2 of 10"
    assert all("runner" not in r for s, r in rows.items() if s != "OMH")
    json.dumps(out, ensure_ascii=False, allow_nan=False)


def test_the_hint_states_the_live_reading(monkeypatch):
    db = _with_runners(_board_db(), [_entry("POM", D12)], pending=[{"kind": "aplus", "key": "k", "symbol": "TOP",
                                                                     "session": SESS.isoformat(), "why": "aplus_pending",
                                                                     "tried": None}],
                       processed={D12.isoformat(): {"reading": "after_aplus", "n_scan": 70, "n_reads": 60,
                                                    "partial": True}})
    hint = PL.build(FRI_IN, db=db)["runners"]["hint"]
    assert "With a 🚩 A+: a high of +30% or more above the A+ trigger" in hint and "+40%" in hint
    assert " 1 not checked yet." in hint and "2026-11-12: 10 of 70 scanner names" in hint
    monkeypatch.setattr(C, "RUNNERS_SEAT_READING", "seat_cut")
    hint2 = PL.build(FRI_IN, db=db)["runners"]["hint"]
    assert "A 09:30–20:00 ET high of +30% or more vs the prior close" in hint2 and "+40%" not in hint2
    assert RS.rule_sentence() in RS.rules_line()


def test_NEGATIVE_unreadable_doc_serves_the_line_and_the_board_answers(monkeypatch):
    monkeypatch.setattr(RS, "read_doc", lambda cs: None)
    out = PL.build(FRI_IN, db=_board_db())
    assert out["state"] == "ok" and out["runners"] == {"state": "unreadable", "text": C.RUNNERS_SEAT_UNREADABLE,
                                                       "rows": []}


def test_NEGATIVE_a_raising_engine_drops_the_key_only(monkeypatch):
    monkeypatch.setattr(RS, "roster", lambda *a, **k: 1 / 0)
    out = PL.build(FRI_IN, db=_with_runners(_board_db(), [_entry("POM", D12)]))
    assert out["state"] == "ok" and "runners" not in out


def test_NEGATIVE_off_and_the_only_poll_serve_nothing(monkeypatch):
    db = _with_runners(_board_db(), [_entry("OMH", D12)])
    assert "runners" not in PL.build(FRI_IN, db=db, only=["OMH"])
    assert all("runner" not in r for r in PL.build(FRI_IN, db=db, only=["OMH"])["rows"])
    monkeypatch.setattr(C, "RUNNERS_SEAT_ON", False)
    out = PL.build(FRI_IN, db=db)
    assert "runners" not in out and all("runner" not in r for r in out["rows"])


# ── the track route ──────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture()
def client(monkeypatch):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app)


def test_track_route_owner_only_and_error_on_a_missing_module(client, monkeypatch):
    called = []
    monkeypatch.setattr(C, "RUNTRACK_MODULE", "chart_maps.gajjala_watch.no_such_runtrack")
    r = client.get(C.API_RUNTRACK_PATH, headers={"X-User-Email": "else@example.com"})
    assert r.json() == PL.owner_only_payload()
    r = client.get(C.API_RUNTRACK_PATH, headers={"X-User-Email": OWNER})
    assert r.json()["state"] == "error"
    import sys
    import types
    monkeypatch.setitem(sys.modules, "tests._fake_runtrack", types.SimpleNamespace(
        payload=lambda now, symbol=None: called.append(symbol) or {"state": "ok", "x": float("nan")}))
    monkeypatch.setattr(C, "RUNTRACK_MODULE", "tests._fake_runtrack")
    r = client.get(C.API_RUNTRACK_PATH + "?symbol=pom", headers={"X-User-Email": OWNER})
    assert r.json() == {"state": "ok", "x": None} and called == ["POM"]          # scrubbed, normalized
    r = client.get(C.API_RUNTRACK_PATH, headers={"X-User-Email": "else@example.com"})
    assert called == ["POM"]                                                      # nothing read for a non-owner


# ── ℹ️ ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_rules_info_clause_is_in_the_note_and_types_no_digit():
    import ast
    import inspect
    import re
    from supply_demand import rules_info as RI
    line = RS.rules_line()
    assert line in RI._gajjala_section()["note"] and RI._gg_watch_runseat_clause() == " " + line
    tree = ast.parse(inspect.getsource(RS))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "rules_line")
    words = [n.value for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert [w for w in words if re.search(r"[0-9]", w)] == []
    for want in ("+40%", "+30%", "10 sessions", "UNMEASURED", "mode off"):
        assert want in line


def test_NEGATIVE_rules_info_clause_survives_a_broken_module(monkeypatch):
    from supply_demand import rules_info as RI
    monkeypatch.setattr(RS, "rules_line", lambda: 1 / 0)
    assert RI._gg_watch_runseat_clause() == ""
    assert "📅 Runners on 👀" not in RI._gajjala_section()["note"]
