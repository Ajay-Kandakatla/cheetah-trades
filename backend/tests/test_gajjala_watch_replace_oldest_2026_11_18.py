"""👀 Gajjala's Watch — 🔁 an add at the cap replaces the OLDEST name he added (2026-11-18).

Ajay 2026-11-18, verbatim: "For watch list when I add new ones remove the ones that are not active in the watch list".
Asked what "not active" means, he picked "Oldest added" — "Remove the one you added longest ago, whatever it is doing."
Told: "A+ names are never removed, and you'll see a line saying which one went."

NEGATIVES: below the cap nothing is removed (and the A+ set is not even read); an add of a name already on the list, or
of a junk string, removes nothing; an oldest 🎯 A+ is passed over; every name A+ → the old `full` refusal, list
unchanged; an A+ read fault → `full`, nothing removed on a guess; a pending poll never serves `full_blocked`.
"""
from __future__ import annotations

import re
import sys
import types

import pytest

from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import store as ST
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_api_2026_11_15 import FRI_IN, _db as _board_db

NAMES = [f"A{chr(65 + i)}" for i in range(C.MAX_SYMBOLS)]          # oldest first (list order = add order)


def _db(symbols=None):
    docs = [{"_id": C.LIST_DOC_ID, "symbols": list(symbols)}] if symbols is not None else []
    return {C.COLL_LIST: FakeColl(docs), C.COLL_TILES: FakeColl(), C.COLL_ALERTS: FakeColl(), C.COLL_STATE: FakeColl()}


def _stored(db):
    d = db[C.COLL_LIST].docs.get(C.LIST_DOC_ID)
    return None if d is None else list(d["symbols"])


@pytest.fixture()
def aplus(monkeypatch):
    """The 🎯 A+ set the store reads — a mutable set; `reads` counts the calls."""
    st = {"set": set(), "reads": 0, "boom": False}

    def fake(names):
        st["reads"] += 1
        if st["boom"]:
            raise RuntimeError("reads down")
        return {n for n in names if n in st["set"]}
    monkeypatch.setattr(ST, "aplus_names", fake)
    return st


# ── store.add at the cap ───────────────────────────────────────────────────────────────────────────────────────────
def test_full_add_replaces_the_oldest_and_appends_at_the_end(aplus):
    db = _db(NAMES)
    out = ST.add("zzz", by="owner", db=db)
    assert out["state"] == "replaced" and out["replaced"] == NAMES[0] and out["symbol"] == "ZZZ"
    assert out["symbols"] == NAMES[1:] + ["ZZZ"] == _stored(db)
    assert len(_stored(db)) == C.MAX_SYMBOLS and db[C.COLL_LIST].writes == 1          # ONE write: drop + append
    # RE-PINNED 2026-11-19 — words only — a ➕ again now puts a name first (HIS CALL #2). Ajay 2026-11-19: "When I add a new ticket they are gettinf added in to que but not active"
    assert out["text"] == f"ZZZ added — your watch was full, so {NAMES[0]} (on your watch the longest) made room"


def test_an_aplus_oldest_is_passed_over_the_next_oldest_goes(aplus):
    aplus["set"] = {NAMES[0], NAMES[1]}
    db = _db(NAMES)
    out = ST.add("ZZZ", by="owner", db=db)
    assert out["state"] == "replaced" and out["replaced"] == NAMES[2]
    assert _stored(db) == NAMES[:2] + NAMES[3:] + ["ZZZ"]                     # both A+ stay, in place
    # RE-PINNED 2026-11-19 — words only — a ➕ again now puts a name first (HIS CALL #2). Ajay 2026-11-19: "When I add a new ticket they are gettinf added in to que but not active"
    assert out["text"] == (f"ZZZ added — your watch was full, so {NAMES[2]} (on your watch the longest that is not "
                           "🎯 A+) made room")


def test_a_later_aplus_does_not_change_which_oldest_goes(aplus):
    aplus["set"] = {NAMES[-1]}
    out = ST.add("ZZZ", by="owner", db=_db(NAMES))
    assert out["replaced"] == NAMES[0] and "not 🎯 A+" not in out["text"]


def test_NEGATIVE_every_name_aplus_is_the_old_full_refusal(aplus):
    aplus["set"] = set(NAMES)
    db = _db(NAMES)
    out = ST.add("ZZZ", by="owner", db=db)
    assert out["state"] == "full" and "replaced" not in out and out["symbols"] == NAMES
    assert _stored(db) == NAMES and db[C.COLL_LIST].writes == 0
    assert out["text"] == PL.full_text() == f"Your watch holds {C.MAX_SYMBOLS} tickers — remove one to add another"


def test_NEGATIVE_an_aplus_read_fault_removes_nothing(aplus):
    aplus["boom"] = True
    db = _db(NAMES)
    out = ST.add("ZZZ", by="owner", db=db)
    assert out["state"] == "full" and _stored(db) == NAMES and db[C.COLL_LIST].writes == 0


def test_NEGATIVE_below_the_cap_is_a_plain_add_nothing_removed(aplus):
    db = _db(NAMES[:-1])
    out = ST.add("ZZZ", by="owner", db=db)
    assert out == {"state": "added", "symbols": NAMES[:-1] + ["ZZZ"], "symbol": "ZZZ",
                   "text": PL.store_text("added", "ZZZ")}
    assert aplus["reads"] == 0                                                 # the A+ set is read at the cap only


def test_NEGATIVE_already_on_a_full_list_removes_nothing(aplus):
    db = _db(NAMES)
    out = ST.add(NAMES[5].lower(), by="owner", db=db)
    # RE-PINNED 2026-11-19 (writes 0 → 1: the add time only, never `symbols`) — Ajay 2026-11-19: "When I add a new ticket they are gettinf added in to que but not active"
    assert out["state"] == "already" and _stored(db) == NAMES and db[C.COLL_LIST].writes == 1
    assert aplus["reads"] == 0


@pytest.mark.parametrize("raw", ["", "$OMH", "TOOLONGX", None, 7])
def test_NEGATIVE_a_bad_symbol_on_a_full_list_removes_nothing(aplus, raw):
    db = _db(NAMES)
    out = ST.add(raw, by="owner", db=db)
    assert out["state"] == "bad_symbol" and _stored(db) == NAMES and db[C.COLL_LIST].writes == 0
    assert aplus["reads"] == 0


def test_the_replaced_name_can_be_added_back_by_hand(aplus):
    db = _db(NAMES)
    assert ST.add("ZZZ", by="owner", db=db)["replaced"] == NAMES[0]
    back = ST.add(NAMES[0], by="owner", db=db)                     # never blocked — it makes room in turn
    assert back["state"] == "replaced" and back["replaced"] == NAMES[1]
    assert _stored(db) == NAMES[2:] + ["ZZZ", NAMES[0]]
    assert ST.remove("ZZZ", by="owner", db=db)["state"] == "removed"
    assert ST.add(NAMES[1], by="owner", db=db)["state"] == "added"  # below the cap: a plain add


def test_NEGATIVE_a_replace_writes_nothing_to_the_auto_doc(aplus):
    db = _db(NAMES)
    ST.add("ZZZ", by="owner", db=db)
    assert C.AUTO_DOC_ID not in db[C.COLL_LIST].docs                  # no × block, no "removed today" entry


def test_the_aplus_read_is_the_watch_tags_own(monkeypatch):
    seen = {}

    def fake_blocks(names, siso, *, stores=None):
        seen.update(names=list(names), siso=siso)
        return {names[0]: {"tag": PL.APLUS_TAG}}
    monkeypatch.setattr(PL, "aplus_blocks", fake_blocks)
    monkeypatch.setattr(PL, "session_iso", lambda now=None: "2026-11-18")
    assert ST.aplus_names(["OMH", "NVDA"]) == {"OMH"}
    assert seen == {"names": ["OMH", "NVDA"], "siso": "2026-11-18"}


def test_NEGATIVE_aplus_blocks_raises_where_aplus_section_serves_nothing(monkeypatch):
    def boom():
        raise RuntimeError("stores down")
    monkeypatch.setattr(PL, "_aplus_stores", boom)
    with pytest.raises(RuntimeError):
        PL.aplus_blocks(["OMH"], "2026-11-18")
    assert PL.aplus_section(["OMH"], "2026-11-18") == {}                       # the board: unchanged, fail-soft
    assert PL.aplus_blocks([], "2026-11-18") == {}


def test_session_iso_is_the_boards_rule():
    session, _t, _w = PL._session_of(FRI_IN)
    assert PL.session_iso(FRI_IN) == session.isoformat()[:10] == "2026-11-13"


# ── the served words ───────────────────────────────────────────────────────────────────────────────────────────────
def test_replaced_is_appended_last_with_words_and_no_typed_digits():
    assert ST.STATES_ADD == ("added", "already", "full", "bad_symbol", "error", "replaced")
    for t in (PL.STORE_TEXT["replaced"], PL.REPLACED_PAST_APLUS_TEXT, PL.FULL_REPLACES_TEXT):
        assert not re.search(r"[0-9]", re.sub(r"\{[^}]*\}", "", t))
    # RE-PINNED 2026-11-19 — words only — a ➕ again now puts a name first (HIS CALL #2). Ajay 2026-11-19: "When I add a new ticket they are gettinf added in to que but not active"
    assert PL.store_text("replaced", "OMH", old=None) == \
        f"OMH added — your watch was full, so {PL.STORE_NO_SYMBOL} (on your watch the longest) made room"
    assert PL.store_text("added", "OMH", old="X") == PL.store_text("added", "OMH")      # other states ignore `old`


def test_the_card_list_serves_the_replace_hint_never_the_refusal():
    out = PL.list_payload(NAMES)
    assert out["full"] is True and out["full_text"] == PL.full_hint()
    # RE-PINNED 2026-11-19 — words only — a ➕ again now puts a name first (HIS CALL #2). Ajay 2026-11-19: "When I add a new ticket they are gettinf added in to que but not active"
    assert out["full_text"] == (f"Your watch holds {C.MAX_SYMBOLS} — adding one replaces the one on your watch the "
                                "longest (never a 🎯 A+)")
    assert "full_blocked" not in out                                        # the card list reads no A+ (unknown)


@pytest.fixture()
def board_stubs(monkeypatch):
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.build", types.SimpleNamespace(uptrend_rule=lambda: "R"))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.cross_alerts",
                        types.SimpleNamespace(rules_line=lambda: "P"))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.auto",
                        types.SimpleNamespace(read_doc=lambda cs: {}, rules_line=lambda: "A",
                                              dismiss=lambda symbol, by=None: {"state": "absent"}))
    tagged = {"set": set()}
    monkeypatch.setattr(PL, "aplus_section", lambda names, siso, stores=None:
                        {n: {"tag": PL.APLUS_TAG, "text": PL.APLUS_TEXT, "items": [], "title": "t"}
                         for n in names if n in tagged["set"]})
    return tagged


def test_board_full_with_room_serves_the_hint_and_is_not_blocked(board_stubs):
    board_stubs["set"] = set(NAMES[:-1])                                      # one name is not A+
    out = PL.build(FRI_IN, db=_board_db(NAMES))
    assert out["full"] is True and out["full_blocked"] is False and out["full_text"] == PL.full_hint()


def test_board_every_name_aplus_is_blocked_with_the_refusal_words(board_stubs):
    board_stubs["set"] = set(NAMES)
    out = PL.build(FRI_IN, db=_board_db(NAMES))
    assert out["full"] is True and out["full_blocked"] is True and out["full_text"] == PL.full_text()


def test_NEGATIVE_board_not_full_or_a_pending_poll_is_never_blocked(board_stubs):
    board_stubs["set"] = set(NAMES)
    out = PL.build(FRI_IN, db=_board_db(NAMES[:-1]))
    assert out["full"] is False and out["full_blocked"] is False
    poll = PL.build(FRI_IN, db=_board_db(NAMES), only=[NAMES[0]])
    assert poll["full"] is True and poll["full_blocked"] is False
    empty = PL.build(FRI_IN, db=_board_db([]))
    assert empty["full_blocked"] is False
