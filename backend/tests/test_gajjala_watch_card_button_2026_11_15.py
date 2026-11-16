"""➕/➖ Watch on every card (2026-11-15) — GET /chart-maps/gajjala-watch/symbols.

Ajay 2026-11-15, verbatim: "can you add an add to watch list button on all the stocks to move them and also remove button
from watch list too."

NEGATIVES: anyone else / no email / the Depends OBJECT get exactly owner_only and nothing is read; a failing read answers
`error`, never an empty list (an empty list would offer ➕ on a name already watched); no chart and no admin email in the
answer; `full` only at the cap.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from tests.test_gajjala_watch_api_2026_11_15 import OTHER, OWNER, _db, wired  # noqa: F401  (fixture)


@pytest.fixture()
def db():
    return _db(["OMH", "NVDA"])


def test_the_path_is_the_constant_next_to_the_symbol_route():
    assert C.API_LIST_PATH == "/chart-maps/gajjala-watch/symbols"
    assert C.API_SYMBOL_PATH.startswith(C.API_LIST_PATH + "/")


def test_owner_gets_his_names_in_his_order_with_the_served_words(wired):
    r = wired.get(C.API_LIST_PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200
    b = r.json()
    assert b == PL.list_payload(["OMH", "NVDA"])
    assert b["state"] == "ok" and b["symbols"] == ["OMH", "NVDA"] and b["max"] == C.MAX_SYMBOLS and b["full"] is False
    assert b["labels"] == {"add": "➕ Watch", "remove": "➖ Watch", "add_title": "Add {sym} to 👀 Gajjala's Watch",
                           "remove_title": "Remove {sym} from 👀 Gajjala's Watch"}
    assert OWNER not in r.text and "tile" not in b and "rows" not in b


def test_full_only_at_the_cap():
    names = [f"A{chr(65 + i)}" for i in range(C.MAX_SYMBOLS)]
    assert PL.list_payload(names)["full"] is True
    assert PL.list_payload(names[:-1])["full"] is False
    assert PL.list_payload([])["full"] is False
    assert PL.list_payload(["OMH", None, 3])["symbols"] == ["OMH"]        # NEGATIVE: junk never served


@pytest.mark.parametrize("headers", [{"X-User-Email": OTHER}, {}, {"X-User-Email": "  "}])
def test_NEGATIVE_anyone_else_gets_exactly_owner_only_and_nothing_is_read(wired, monkeypatch, headers):
    calls = []

    def _boom(*a, **k):
        calls.append(1)
        raise AssertionError("read for a non-owner")
    for name in ("colls", "_db", "owner_symbols"):
        monkeypatch.setattr(CO, name, _boom)
    r = wired.get(C.API_LIST_PATH, headers=headers)
    assert r.status_code == 200 and r.json() == PL.owner_only_payload() and calls == []
    assert "OMH" not in r.text


def test_NEGATIVE_a_direct_call_with_the_depends_object_is_a_non_owner(wired, monkeypatch):
    from fastapi.params import Depends as DependsParam
    monkeypatch.setattr(CO, "owner_symbols", lambda *a, **k: (_ for _ in ()).throw(AssertionError("read")))
    assert asyncio.run(API.gajjala_watch_symbols(email=DependsParam())) == PL.owner_only_payload()
    assert asyncio.run(API.gajjala_watch_symbols()) == PL.owner_only_payload()


def test_NEGATIVE_a_failing_read_is_error_never_an_empty_list(wired, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(CO, "colls", _boom)
    r = wired.get(C.API_LIST_PATH, headers={"X-User-Email": OWNER})
    b = r.json()
    assert r.status_code == 200 and b["state"] == "error" and "symbols" not in b


def test_add_then_list_then_remove_round_trip(wired):
    h = {"X-User-Email": OWNER}
    assert wired.post(C.API_SYMBOL_PATH.format(symbol="rain"), headers=h).json()["state"] == "added"
    assert wired.get(C.API_LIST_PATH, headers=h).json()["symbols"] == ["OMH", "NVDA", "RAIN"]
    assert wired.delete(C.API_SYMBOL_PATH.format(symbol="OMH"), headers=h).json()["state"] == "removed"
    assert wired.get(C.API_LIST_PATH, headers=h).json()["symbols"] == ["NVDA", "RAIN"]
    json.dumps(wired.get(C.API_LIST_PATH, headers=h).json(), allow_nan=False)
