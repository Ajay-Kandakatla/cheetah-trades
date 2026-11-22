"""🎯 A+ tag on 👀 Gajjala's Watch rows (spec ggwaplus, 2026-11-17).

Ajay 2026-11-17 ~12:58 ET, verbatim: "Also add an A+ tag on watch list as they become A+".

Every row (his AND 🤖) carries `aplus` when ANY Gajjala board's stored read of the name THIS session has a setup in
tab.MARKED_STATES. Sources: GG5's reads (🚩 5-min), GG1's reads (🚩 1-min) — ONE projected `_id $in` find each — and
🧪 = THE 🧪 board's own call (`audited_tab.overlay_reads`) on GG5's reads. Display only. UNMEASURED.

NEGATIVES: forming / partial / potential / none / held → null; a read of YESTERDAY's session never tags; a 🧪-held A+
serves no 🧪 item (the 🚩 item stays); a read fault / a missing handle / a raising overlay → null on every row and the
GET still answers 200; no Massive call (the bar loaders are booby-trapped); one find per read store per GET, projected
(never the tile bars); an unlisted `only` name is never in the find; no digit typed in a served word.
"""
from __future__ import annotations

import json
import re
import sys
import types
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_api_2026_11_15 import FRI_IN, OWNER, SESSION, RecColl, _db, _doc, _strict
from tests.test_gajjala_watch_auto_served_2026_11_17 import _entry

YESTERDAY = "2026-11-12"
UPD = datetime(2026, 11, 13, 15, 25)          # naive = UTC (the Mongo read-back) — the read's updated_at
OV_FRESH = datetime(2026, 11, 13, 15, 26)     # an overlay written after the read (fresh)


class ProjColl(FakeColl):
    """FakeColl that records every find's (query, projection)."""

    def __init__(self, docs=None, fail=False):
        super().__init__(docs, fail=fail)
        self.finds = []

    def find(self, q=None, projection=None):
        self.finds.append((q, projection))
        return super().find(q, projection)


def _read(sym, setups, *, session=SESSION):
    return {"_id": ST.key(session, sym), "date": session, "symbol": sym, "updated_at": UPD, "setups": setups,
            "tile": {"bars": ["NEVER-SERVED"]}}


def _r(state, at="10:35", **kw):
    return dict({"state": state, "entry_bar_t": f"{SESSION} {at}" if at else None, "trigger": 2.5, "stop": 2.1}, **kw)


def _ov(sym, setups, *, at=OV_FRESH):
    return {"_id": ST.key(SESSION, sym), "date": SESSION, "symbol": sym, "pass_at": at, "setups": setups}


class Boards:
    def __init__(self, gg5=(), gg1=(), overlays=(), fail5=False, fail1=False):
        self.c5, self.c1 = ProjColl(list(gg5), fail=fail5), ProjColl(list(gg1), fail=fail1)
        self.cov = ProjColl(list(overlays))
        self.stores = {V.GG5.key: ST.GajjalaStore({ST.READS: self.c5}),
                       V.GG1.key: ST.GajjalaStore({ST.READS: self.c1}, variant=V.GG1),
                       V.GGA.key: ST.GajjalaStore({ST.OVERLAY: self.cov, ST.READS: self.c5}, variant=V.GGA)}


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.build",
                        types.SimpleNamespace(uptrend_rule=lambda: "STUB-UPTREND-RULE"))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.cross_alerts",
                        types.SimpleNamespace(rules_line=lambda: "STUB-PUSH-TEXT"))
    eng = types.SimpleNamespace(entries=[], read_doc=None, rules_line=lambda: "STUB-AUTO",
                                dismiss=lambda symbol, by=None: {"state": "absent"})
    eng.read_doc = lambda cs: {"session": SESSION, "entries": list(eng.entries), "removed": []}
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.auto", eng)
    return eng


def _set(monkeypatch, b):
    monkeypatch.setattr(PL, "_aplus_stores", lambda: b.stores)
    return b


def _rows(db=None, only=None):
    out = PL.build(FRI_IN, db=db or _db(["OMH", "NVDA"]), only=only)
    assert out["state"] == "ok"
    return {r["symbol"]: r for r in out["rows"]}, out


# ── words ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_words_keys_are_the_marked_states_and_equal_the_recap_words():
    assert tuple(PL.APLUS_WORDS) == tuple(tab.MARKED_STATES)
    for state, word in PL.APLUS_WORDS.items():                         # = tab.recap's inline map (tab.py:1796)
        doc = {"symbol": "OMH", "date": SESSION, "setups": {"kiss_fly": _r(state)}}
        txt = tab.recap([doc])["rows"][0]["text"]
        assert f" {word} at " in txt


def test_source_guard_no_digit_typed_in_the_aplus_words():
    bad = []
    for name, v in vars(PL).items():
        if not name.startswith("APLUS_") or not isinstance(v, (str, dict)):
            continue
        for s in (v.values() if isinstance(v, dict) else [v]):
            if isinstance(s, str) and re.search(r"[0-9]", re.sub(r"\{[^}]*\}", "", s)):
                bad.append((name, s))
    assert bad == []


# ── tags ──────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("state", ["aplus", "triggered", "stopped"])
def test_each_marked_state_tags_with_its_word(monkeypatch, state):
    _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r(state)})],
                             overlays=[_ov("OMH", {"kiss_fly": {"entry_bar_t": f"{SESSION} 10:35", "aplus": True}})]))
    rows, _ = _rows()
    blk = rows["OMH"]["aplus"]
    gg5 = [it for it in blk["items"] if it["source"] == V.GG5.key]
    assert len(gg5) == 1
    it = gg5[0]
    assert it == {"source": "gajjala", "source_word": C.AUTO_SOURCE_WORDS["gajjala"], "setup": "kiss_fly",
                  "setup_label": tab._setup_label("kiss_fly"), "state": state, "word": PL.APLUS_WORDS[state],
                  "at_et": "10:35"}
    assert blk["text"] == "🎯 A+ 10:35" and blk["tag"] == PL.APLUS_TAG
    assert PL.APLUS_ITEM_TEXT.format(source=it["source_word"], setup=it["setup_label"], word=it["word"],
                                     at_et="10:35") in blk["title"]
    assert rows["NVDA"]["aplus"] is None


@pytest.mark.parametrize("state", ["forming", "partial", "potential", "armed", "none", None, "aplus_held", "APLUS"])
def test_NEGATIVE_non_marked_states_never_tag(monkeypatch, state):
    _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r(state)})], gg1=[_read("OMH", {"bull_flag": _r(state)})]))
    rows, _ = _rows()
    assert rows["OMH"]["aplus"] is None and rows["NVDA"]["aplus"] is None


def test_NEGATIVE_a_read_of_yesterdays_session_never_tags(monkeypatch):
    b = _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r("aplus")}, session=YESTERDAY)],
                                 gg1=[_read("OMH", {"kiss_fly": _r("triggered")}, session=YESTERDAY)]))
    rows, _ = _rows()
    assert rows["OMH"]["aplus"] is None
    assert b.c5.finds[0][0] == {"_id": {"$in": [ST.key(SESSION, "OMH"), ST.key(SESSION, "NVDA")]}}


def test_gg1_only_aplus_tags_with_the_one_minute_word(monkeypatch):
    _set(monkeypatch, Boards(gg1=[_read("NVDA", {"bull_flag": _r("aplus", at="09:47")})]))
    rows, _ = _rows()
    blk = rows["NVDA"]["aplus"]
    assert [(it["source"], it["source_word"], it["setup"]) for it in blk["items"]] == \
        [("gajjala_1m", "🚩 1-min", "bull_flag")]
    assert blk["text"] == "🎯 A+ 09:47" and "🚩 1-min" in blk["title"]
    assert rows["OMH"]["aplus"] is None


def test_both_boards_two_items_and_a_held_aplus_serves_no_gga_item(monkeypatch):
    ov = {"kiss_fly": {"entry_bar_t": f"{SESSION} 10:35", "aplus": False, "failed": ["K3"]}}   # 🧪 HELD
    _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r("aplus")})],
                             gg1=[_read("OMH", {"kiss_fly": _r("triggered", at="10:31")})],
                             overlays=[_ov("OMH", ov)]))
    rows, _ = _rows()
    items = rows["OMH"]["aplus"]["items"]
    assert [(it["source"], it["state"], it["at_et"]) for it in items] == \
        [("gajjala_1m", "triggered", "10:31"), ("gajjala", "aplus", "10:35")]          # by at_et first
    assert rows["OMH"]["aplus"]["text"] == "🎯 A+ 10:31"


def test_an_audited_aplus_carries_a_gga_item(monkeypatch):
    ov = {"kiss_fly": {"entry_bar_t": f"{SESSION} 10:35", "aplus": True}}
    _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r("aplus")})], overlays=[_ov("OMH", ov)]))
    rows, _ = _rows()
    items = rows["OMH"]["aplus"]["items"]
    assert [(it["source"], it["source_word"]) for it in items] == [("gajjala", "🚩 5-min"), ("gga", "🧪")]


def test_a_k3s_admit_is_a_gga_only_aplus(monkeypatch):
    from chart_maps.gajjala import audited_rules as AUD
    partial = _r("partial", broke=True, bars_since_entry=0, missed=list(AUD.K3S_MISSED))
    ov = {"reversal_squeeze": {"entry_bar_t": f"{SESSION} 10:35", "aplus": True, "admit": "K3S"}}
    _set(monkeypatch, Boards(gg5=[_read("OMH", {"reversal_squeeze": partial})], overlays=[_ov("OMH", ov)]))
    rows, _ = _rows()
    assert [(it["source"], it["state"], it["setup"]) for it in rows["OMH"]["aplus"]["items"]] == \
        [("gga", "aplus", "reversal_squeeze")]


def test_NEGATIVE_a_stale_overlay_does_not_hold_the_aplus(monkeypatch):
    """The 🧪 board's own rule (3): an overlay older than the read is not applied — the A+ passes through there too."""
    ov = {"kiss_fly": {"entry_bar_t": f"{SESSION} 10:35", "aplus": False}}
    _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r("aplus")})],
                             overlays=[_ov("OMH", ov, at=datetime(2026, 11, 13, 15, 0))]))
    rows, _ = _rows()
    assert [it["source"] for it in rows["OMH"]["aplus"]["items"]] == ["gajjala", "gga"]


def test_items_order_at_et_then_setups_then_source_missing_clock_last(monkeypatch):
    gg5 = {"reversal_squeeze": _r("aplus", at="10:00"), "bull_flag": _r("stopped", at="10:00"),
           "kiss_fly": _r("triggered", at=None)}
    gg1 = {"bull_flag": _r("aplus", at="10:00")}
    _set(monkeypatch, Boards(gg5=[_read("OMH", gg5)], gg1=[_read("OMH", gg1)],
                             overlays=[_ov("OMH", {"reversal_squeeze": {"entry_bar_t": f"{SESSION} 10:00",
                                                                         "aplus": False}})]))
    rows, _ = _rows()
    got = [(it["at_et"], it["setup"], it["source"]) for it in rows["OMH"]["aplus"]["items"]]
    assert got == [("10:00", "bull_flag", "gajjala"), ("10:00", "bull_flag", "gajjala_1m"),
                   ("10:00", "bull_flag", "gga"), ("10:00", "reversal_squeeze", "gajjala"),
                   (None, "kiss_fly", "gajjala"), (None, "kiss_fly", "gga")]
    blk = rows["OMH"]["aplus"]
    assert blk["text"] == "🎯 A+ 10:00"
    assert PL.APLUS_ITEM_NO_TIME_TEXT.format(source="🧪", setup=tab._setup_label("kiss_fly"),
                                             word=PL.APLUS_WORDS["triggered"]) in blk["title"]
    assert blk["title"] == PL.APLUS_TITLE_TEXT.format(
        text=PL.APLUS_TEXT, items=PL.APLUS_ITEM_SEP.join(PL._aplus_item_text(it) for it in blk["items"]))


def test_no_clock_text_is_the_bare_tag(monkeypatch):
    _set(monkeypatch, Boards(gg1=[_read("OMH", {"kiss_fly": _r("aplus", at=None)})]))
    rows, _ = _rows()
    assert rows["OMH"]["aplus"]["text"] == PL.APLUS_TEXT


def test_his_names_and_auto_names_both_tagged(monkeypatch, stubs):
    stubs.entries = [_entry("ZZZ")]
    _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r("aplus")})],
                             gg1=[_read("ZZZ", {"bull_flag": _r("aplus")})]))
    rows, out = _rows()
    assert list(rows) == ["OMH", "NVDA", "ZZZ"]                                      # row order unchanged
    assert rows["OMH"]["aplus"] and rows["OMH"]["auto"] is None
    assert rows["ZZZ"]["aplus"] and rows["ZZZ"]["auto"] is not None
    assert rows["NVDA"]["aplus"] is None
    assert out["symbols"] == ["OMH", "NVDA"]


# ── faults ────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("which", ["fail5", "fail1"])
def test_NEGATIVE_a_read_fault_serves_null_everywhere(monkeypatch, which):
    _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r("aplus")})],
                             gg1=[_read("NVDA", {"kiss_fly": _r("aplus")})], **{which: True}))
    rows, out = _rows()
    assert all(r["aplus"] is None for r in rows.values())
    assert out["state"] == "ok" and len(rows) == 2


def test_NEGATIVE_a_missing_handle_and_a_raising_overlay_serve_null(monkeypatch):
    b = Boards(gg5=[_read("OMH", {"kiss_fly": _r("aplus")})])
    b.stores[V.GG1.key] = ST.GajjalaStore({ST.READS: None}, variant=V.GG1)
    _set(monkeypatch, b)
    rows, _ = _rows()
    assert rows["OMH"]["aplus"] is None
    from chart_maps.gajjala import audited_tab as AT
    _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r("aplus")})]))
    monkeypatch.setattr(AT, "overlay_reads", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    rows, _ = _rows()
    assert rows["OMH"]["aplus"] is None


def test_NEGATIVE_no_mongo_at_all_serves_null(monkeypatch):
    """The real stores with the test-session guard (no MongoClient) → every row null, the board answers."""
    rows, out = _rows()
    assert out["state"] == "ok" and all(r["aplus"] is None for r in rows.values())


def test_NEGATIVE_a_read_fault_still_answers_200_on_the_get(monkeypatch):
    import ollama_chat.api as OA
    db = _db(["OMH", "NVDA"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH")
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setattr(CO, "_db", lambda: db)
    monkeypatch.setattr(CO, "loop_reads_soon", lambda now: True)
    monkeypatch.setattr(PL, "_now", lambda now: FRI_IN)
    _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r("aplus")})], fail5=True))
    app = FastAPI()
    app.include_router(API.router)
    r = TestClient(app).get(C.API_PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200
    out = _strict(r.text)
    assert out["state"] == "ok" and [x["aplus"] for x in out["rows"]] == [None, None]


# ── reads ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_one_projected_find_per_store_per_get_never_the_bars(monkeypatch):
    b = _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r("aplus")})],
                                 gg1=[_read("OMH", {"kiss_fly": _r("aplus")})]))
    rows, _ = _rows()
    ids = [ST.key(SESSION, "OMH"), ST.key(SESSION, "NVDA")]
    for c in (b.c5, b.c1):
        assert c.finds == [({"_id": {"$in": ids}}, PL.APLUS_READ_FIELDS)]
    assert "tile" not in PL.APLUS_READ_FIELDS and set(PL.APLUS_READ_FIELDS) == {"symbol", "setups", "updated_at"}
    assert len(b.cov.finds) == 1                                                       # the 🧪 overlay, once
    assert "NEVER-SERVED" not in json.dumps(rows, default=str)


def test_NEGATIVE_an_unlisted_only_name_is_never_in_the_find(monkeypatch):
    b = _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r("aplus")}), _read("AMD", {"kiss_fly": _r("aplus")})]))
    rows, _ = _rows(only=["OMH", "AMD"])
    assert list(rows) == ["OMH"] and rows["OMH"]["aplus"]
    assert b.c5.finds == [({"_id": {"$in": [ST.key(SESSION, "OMH")]}}, PL.APLUS_READ_FIELDS)]


def test_NEGATIVE_no_names_no_find(monkeypatch):
    b = _set(monkeypatch, Boards())
    out = PL.build(FRI_IN, db=_db([]))
    assert out["state"] == "ok" and out["rows"] == []
    assert b.c5.finds == [] and b.c1.finds == [] and b.cov.finds == []


def test_NEGATIVE_no_massive_call_on_the_payload_path(monkeypatch):
    from chart_maps.gajjala import bars as B
    from daytrading import data as DT
    hits = []

    def trap(*a, **k):
        hits.append(a)
        raise AssertionError("the A+ tag must never fetch")
    monkeypatch.setattr(B, "frames_for", trap)
    monkeypatch.setattr(DT, "load_intraday", trap)
    _set(monkeypatch, Boards(gg5=[_read("OMH", {"kiss_fly": _r("aplus")})]))
    rows, _ = _rows()
    assert rows["OMH"]["aplus"] and hits == []


def test_row_keys_are_the_old_keys_plus_aplus(monkeypatch):
    _set(monkeypatch, Boards())
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH")
    rows, _ = _rows(db=db)
    # PIN MOVED 2026-11-19 (spec watchfid): + "broker_text"
    # PIN MOVED 2026-11-21 (spec watchfloat): + "float"
    # PIN MOVED 2026-11-22 (spec watch_org rev 4): + "org" while C.SECTIONS_ON (the OFF twin below keeps the old set)
    assert set(rows["OMH"]) == {"symbol", "state", "text", "from_session", "as_of_et", "stale", "frames", "rang",
                                "auto", "aplus", "tags", "broker_text",   # 🏷️ 2026-11-18 (spec wtags): + "tags"
                                "added_at", "late_text", "float", "org"}
    # RE-PINNED 2026-11-19 (+ "added_at", "late_text") — Ajay 2026-11-19: "When I add a new ticket they are gettinf added in to que but not active"
    assert C.AUTO_SOURCES == (V.GG5.key, V.GG1.key, V.GGA.key) and GC.SETUPS


def test_row_keys_OFF_twin_sections_off_keeps_the_11_21_keys(monkeypatch):
    """PIN MOVED 2026-11-22 (spec watch_org rev 4) — OFF twin: C.SECTIONS_ON False → no `org` key on a row, no `sections`
    key on the board."""
    monkeypatch.setattr(C, "SECTIONS_ON", False)
    _set(monkeypatch, Boards())
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH")
    rows, out = _rows(db=db)
    assert "sections" not in out
    assert set(rows["OMH"]) == {"symbol", "state", "text", "from_session", "as_of_et", "stale", "frames", "rang",
                                "auto", "aplus", "tags", "broker_text", "added_at", "late_text", "float"}
