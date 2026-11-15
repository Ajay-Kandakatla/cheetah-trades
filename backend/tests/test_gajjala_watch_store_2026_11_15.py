"""👀 Gajjala's Watch — the owner list store (spec §3.3, WP-A, 2026-11-15).

Ajay 2026-11-15, verbatim: "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and
add remove tickers from the dashboard."

NEGATIVES: junk symbols are `bad_symbol` and the list is unchanged; an add at the cap is `full` (REFUSED — the OLDEST name
stays, Signal Lab's silent drop is not copied); removing an absent name is `absent`; no database / a failing read is
`error`, never a raise and never an empty list written over his names.
"""
from __future__ import annotations

import pytest

from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import store as ST
from tests.test_gajjala_store import FakeColl


def _db(symbols=None, fail=False):
    docs = [{"_id": C.LIST_DOC_ID, "symbols": list(symbols)}] if symbols is not None else []
    return {C.COLL_LIST: FakeColl(docs, fail=fail), C.COLL_TILES: FakeColl(), C.COLL_ALERTS: FakeColl(),
            C.COLL_STATE: FakeColl()}


def _stored(db):
    d = db[C.COLL_LIST].docs.get(C.LIST_DOC_ID)
    return None if d is None else list(d["symbols"])


# ── normalize ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_normalize_strips_and_upper_cases():
    assert ST.normalize(" omh ") == "OMH"
    assert ST.normalize("brk.b") == "BRK.B" and ST.normalize("mog-a") == "MOG.A"      # PIN MOVED 2026-11-15: ONE house spelling


@pytest.mark.parametrize("raw", ["", "   ", "TOOLONGX", "$OMH", "OM H", "OMH1", None, 5, 5.0, ["OMH"], {"s": "OMH"}])
def test_NEGATIVE_normalize_refuses_junk(raw):
    assert ST.normalize(raw) is None


def test_normalize_reuses_the_house_ticker_shape():
    import inspect
    from supply_demand import accumulation_changes as AC
    src = inspect.getsource(ST)
    assert "_TICKER_SHAPE" in src and "re.compile" not in src                # imported, never retyped
    assert AC._TICKER_SHAPE.match("OMH")


@pytest.mark.parametrize("raw", ["", "TOOLONGX", "$OMH", "OM H", None, 7])
def test_NEGATIVE_add_bad_symbol_leaves_the_list_unchanged(raw):
    db = _db(["OMH", "NVDA"])
    out = ST.add(raw, by="owner", db=db)
    assert out["state"] == "bad_symbol" and out["symbol"] is None
    assert out["symbols"] == ["OMH", "NVDA"] and _stored(db) == ["OMH", "NVDA"]
    assert db[C.COLL_LIST].writes == 0
    assert out["text"] == PL.store_text("bad_symbol", None)


# ── add ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_add_appends_at_the_end_in_his_order():
    db = _db()
    assert ST.add("omh", by="owner", db=db)["state"] == "added"
    out = ST.add("NVDA", by="owner", db=db)
    assert out == {"state": "added", "symbols": ["OMH", "NVDA"], "symbol": "NVDA", "text": PL.store_text("added", "NVDA")}
    assert _stored(db) == ["OMH", "NVDA"]
    doc = db[C.COLL_LIST].docs[C.LIST_DOC_ID]
    assert doc["by"] == "owner" and doc["updated_at"] is not None


def test_add_is_idempotent_already():
    db = _db(["OMH"])
    out = ST.add(" omh", by="owner", db=db)
    assert out["state"] == "already" and out["symbols"] == ["OMH"] and _stored(db) == ["OMH"]
    assert db[C.COLL_LIST].writes == 0


def test_NEGATIVE_add_at_the_cap_is_full_and_refused():
    names = [f"A{chr(65 + i)}" for i in range(C.MAX_SYMBOLS)]
    db = _db(names)
    out = ST.add("ZZZ", by="owner", db=db)
    assert out["state"] == "full" and out["symbols"] == names
    assert _stored(db) == names and names[0] in _stored(db) and "ZZZ" not in _stored(db)   # the OLDEST stays
    assert out["text"] == PL.full_text() and str(C.MAX_SYMBOLS) in out["text"]
    assert db[C.COLL_LIST].writes == 0


def test_add_one_below_the_cap_still_adds():
    names = [f"A{chr(65 + i)}" for i in range(C.MAX_SYMBOLS - 1)]
    db = _db(names)
    assert ST.add("ZZZ", by="owner", db=db)["state"] == "added"
    assert len(_stored(db)) == C.MAX_SYMBOLS


def test_NEGATIVE_no_database_is_error_never_raises(monkeypatch):
    monkeypatch.setattr(CO, "_db", lambda: None)
    for fn in (ST.add, ST.remove):
        out = fn("OMH", by="owner")
        assert out["state"] == "error" and out["symbols"] == [] and out["symbol"] == "OMH"
        assert out["text"] == PL.store_text("error", "OMH")


def test_NEGATIVE_a_failing_read_is_error_and_never_writes_over_his_list():
    db = _db(["OMH", "NVDA"], fail=True)
    for fn in (ST.add, ST.remove):
        out = fn("AMD", by="owner", db=db)
        assert out["state"] == "error"
    db[C.COLL_LIST].fail = False
    assert _stored(db) == ["OMH", "NVDA"]


def test_NEGATIVE_a_failing_write_is_error():
    db = _db(["OMH"])

    def _boom(*a, **k):
        raise RuntimeError("write refused")
    db[C.COLL_LIST].update_one = _boom
    assert ST.add("NVDA", by="owner", db=db)["state"] == "error"
    assert ST.remove("OMH", by="owner", db=db)["state"] == "error"


# ── remove ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_remove_keeps_the_others_in_order():
    db = _db(["OMH", "NVDA", "AMD"])
    out = ST.remove("nvda", by="owner", db=db)
    assert out["state"] == "removed" and out["symbols"] == ["OMH", "AMD"] and _stored(db) == ["OMH", "AMD"]
    assert out["text"] == PL.store_text("removed", "NVDA")


def test_remove_keeps_the_tile_doc_and_claims_for_audit():
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = {"_id": "OMH", "status": "loaded"}
    db[C.COLL_ALERTS].docs["GGW:2026-11-13|OMH|1m"] = {"_id": "GGW:2026-11-13|OMH|1m"}
    ST.remove("OMH", by="owner", db=db)
    assert "OMH" in db[C.COLL_TILES].docs and db[C.COLL_ALERTS].docs


@pytest.mark.parametrize("raw", ["AMD", "$AMD", None])
def test_NEGATIVE_remove_absent(raw):
    db = _db(["OMH"])
    out = ST.remove(raw, by="owner", db=db)
    assert out["state"] == "absent" and out["symbols"] == ["OMH"] and _stored(db) == ["OMH"]
    assert db[C.COLL_LIST].writes == 0


def test_every_store_state_has_served_words_without_typed_digits():
    import re
    for st in ST.STATES_ADD + ST.STATES_REMOVE:
        assert st in PL.STORE_TEXT
        assert not re.search(r"[0-9]", re.sub(r"\{[^}]*\}", "", PL.STORE_TEXT[st]))
