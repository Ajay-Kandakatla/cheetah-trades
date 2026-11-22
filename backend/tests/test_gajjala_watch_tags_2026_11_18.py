"""🏷️ tags on 👀 Gajjala's Watch rows (spec wtags §3.1 / §4 WP-A, 2026-11-18).

Ajay 2026-11-18 ~12:00 ET, verbatim: "Also add Short Interest tag and other tags on top of stock ticker information for
me to read, like here".

`gajjala_watch/tags.py` serves the 🚩 GG5 card's own tags for a Watch name CARDED on today's 🚩 board (tab.TILE_STATES
+ the 🌀 D3 count — the board's own card rule); `payload._build` puts them on every row as `tags` (None off-board).
Display only. UNMEASURED.

NEGATIVES: no reads doc / none / invalid / a 🌀 read under the D3 count / yesterday's read / a potential that died this
session → None; D10 pair (an empty ledger → tab.NO_RING_TEXT; a raising ledger → today's words); faults are isolated
(broker → broker_text None; tracker → stages None; reads → {} and the GET still 200); projection pins via recording
colls; a board with no carded name = exactly ONE find; the clock is `_build`'s own (a pre-open Monday serves Friday);
no Massive call; no digit / f-string / clock in tags.py; the row key set gains "tags".
"""
from __future__ import annotations

import ast
import json
import re
import sys
import types
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import scanner as SC
from chart_maps.gajjala import stages as SG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab
from chart_maps.gajjala import trader_names as TN
from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import tags as TG
from tests.test_gajjala_stages_2026_11_11 import claim, e, pdoc
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_api_2026_11_15 import ET, FRI_IN, OWNER, SESSION, _db, _doc, _strict

FRI = date(2026, 11, 13)
YESTERDAY = "2026-11-12"
MON = date(2026, 11, 16)
# a Monday BEFORE the first pass time (GC.PASS_OPEN_ET) — tab's rule: the board's session is still Friday's
MON_PRE = datetime.combine(MON, dtime.fromisoformat(GC.PASS_OPEN_ET), tzinfo=ET) - timedelta(hours=1)
B_WORD = re.compile("b" + "ounc", re.I)
SRC = Path(TG.__file__)
FLOAT = {"shares": 4_200_000, "src": "float", "as_of": "2026-11-12"}
TRADER = "algo888"
PROMO_TEXT = "🎪 promo circuit name"


class Rec(FakeColl):
    """FakeColl that records every find (query, projection) and find_one."""

    def __init__(self, docs=None, fail=False):
        super().__init__(docs, fail=fail)
        self.finds, self.find_ones = [], []

    def find(self, q=None, projection=None):
        self.finds.append((q, projection))
        return super().find(q, projection)

    def find_one(self, q=None, projection=None):
        self.find_ones.append(q)
        return super().find_one(q, projection)


def _read(sym, setups, *, session=SESSION, ctx_float=FLOAT):
    d = {"_id": ST.key(session, sym), "date": session, "symbol": sym, "setups": setups,
         "tile": {"bars": ["NEVER-SERVED"]}}
    if ctx_float is not None:
        d["ctx"] = {"float": dict(ctx_float), "other": "NEVER-SERVED-CTX"}
    return d


def _r(state, at="10:35", **kw):
    return dict({"state": state, "entry_bar_t": f"{SESSION} {at}" if at else None, "trigger": 2.5, "stop": 2.1,
                 "bars_since_entry": 2}, **kw)


def _scan(sym, *, session=SESSION, trader=TRADER, promo_text=PROMO_TEXT, held=False):
    return {"_id": ST.key(session, sym), "date": session, "symbol": sym, "held": held,
            "last": {"trader": trader, "promo": promo_text is not None, "promo_text": promo_text}}


def _pot(sym, setup, *, d=FRI):
    return pdoc(d, sym, setup, [e("09:52", "forming", "building")])


class World:
    """The GG5 store the tags block reads — every collection a recording FakeColl."""

    def __init__(self, reads=(), pots=(), alerts=(), scan=(), state=(), fail=()):
        self.c = {n: Rec(list(docs), fail=(n in fail))
                  for n, docs in ((ST.READS, reads), (ST.POTENTIALS, pots), (ST.ALERTS, alerts), (ST.SCAN, scan),
                                  (ST.STATE, state))}
        self.st = ST.GajjalaStore(dict(self.c))

    def reads_of(self, *names):
        return {n: (len(self.c[n].finds), len(self.c[n].find_ones)) for n in names}


def _broker_doc(*syms):
    return {"_id": ST.BROKER_STATE_ID, "added": list(syms), "removed": []}


def _omh_world(**kw):
    kw.setdefault("reads", [_read("OMH", {"reversal_squeeze": _r("forming", at=None)})])
    kw.setdefault("pots", [_pot("OMH", "reversal_squeeze")])
    kw.setdefault("scan", [_scan("OMH")])
    kw.setdefault("state", [_broker_doc("OMH")])
    return World(**kw)


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.build",
                        types.SimpleNamespace(uptrend_rule=lambda: "STUB-UPTREND-RULE"))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.cross_alerts",
                        types.SimpleNamespace(rules_line=lambda: "STUB-PUSH-TEXT"))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.auto",
                        types.SimpleNamespace(read_doc=lambda cs: {}, rules_line=lambda: "STUB-AUTO",
                                              dismiss=lambda symbol, by=None: {"state": "absent"}))


def _set(monkeypatch, w):
    monkeypatch.setattr(TG, "_store", lambda: w.st)
    return w


def _rows(db=None, only=None, now=FRI_IN):
    out = PL.build(now, db=db or _db(["OMH", "NVDA"]), only=only)
    assert out["state"] == "ok"
    return {r["symbol"]: r for r in out["rows"]}, out


def _record_by_symbol(monkeypatch):
    calls = []
    real = SG.by_symbol

    def rec(sessions, **kw):
        calls.append(kw)
        return real(sessions, **kw)
    monkeypatch.setattr(SG, "by_symbol", rec)
    return calls


# ── the served block ─────────────────────────────────────────────────────────────────────────────────────────────
def test_a_carded_name_serves_the_cards_own_tags(monkeypatch):
    _set(monkeypatch, _omh_world())
    rows, _ = _rows()
    t = rows["OMH"]["tags"]
    assert set(t) == set(TG.TAGS_KEYS) and t["on_board"] is True
    r = _r("forming", at=None)
    assert t["setups"] == [{"setup": "reversal_squeeze", "label": tab._setup_label("reversal_squeeze"),
                            "state": "forming", "state_label": tab.state_label(r, None)}]
    assert t["setups"][0]["state_label"] == tab.state_label(r)          # a forming read: rang is irrelevant
    st = t["stages"]
    assert st["title"] == SG.TITLE
    first = st["groups"][0]["tags"][0]["text"]
    assert first.startswith("🎾") and st["text"] == f"{SG.TODAY_LABEL}: {first}"
    assert all(tg["here"] is False for g in st["groups"] for tg in g["tags"])     # no single card → no `here`
    assert t["float"] == tab._float_chip(FLOAT) and t["float"]["text"] == tab._float_chip(FLOAT)["text"]
    assert t["broker_text"] == tab.BROKER_FLAG_TEXT
    assert t["trader_text"] == TN.text_for(TRADER) and t["promo_text"] == PROMO_TEXT
    assert rows["NVDA"]["tags"] is None
    blob = json.dumps(rows, default=str)
    assert "NEVER-SERVED" not in blob


def test_NEGATIVE_off_lists_serve_none_for_trader_promo_broker_float(monkeypatch):
    _set(monkeypatch, _omh_world(scan=[_scan("OMH", trader=None, promo_text=None)], state=[],
                                 reads=[_read("OMH", {"reversal_squeeze": _r("forming", at=None)}, ctx_float=None)]))
    t = _rows()[0]["OMH"]["tags"]
    assert t["on_board"] is True
    assert (t["trader_text"], t["promo_text"], t["broker_text"], t["float"]) == (None, None, None, None)


def test_NEGATIVE_a_held_scan_doc_never_tags():
    w = _omh_world(scan=[_scan("OMH", held=True)])
    t = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]
    assert t["trader_text"] is None and t["promo_text"] is None


def test_a_partial_read_is_carded():
    w = _omh_world(reads=[_read("OMH", {"bull_flag": _r("partial", missed=["k2"])})], pots=[])
    t = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]
    assert t["on_board"] is True and [s["state"] for s in t["setups"]] == ["partial"] and t["stages"] is None


def test_setups_follow_the_setups_order_and_only_carded_states():
    w = _omh_world(reads=[_read("OMH", {"reversal_squeeze": _r("forming"), "kiss_fly": _r("stopped"),
                                        "bull_flag": _r("none"), "horizontal_fade": _r("invalid")})])
    t = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]
    assert [s["setup"] for s in t["setups"]] == ["kiss_fly", "reversal_squeeze"]


# ── D10: the rang answer (C1) ────────────────────────────────────────────────────────────────────────────────────
def test_D10_an_empty_ledger_says_no_alert_rang():
    r = _r("triggered")
    w = _omh_world(reads=[_read("OMH", {"kiss_fly": r})], pots=[_pot("OMH", "kiss_fly")], alerts=[])
    lbl = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]["setups"][0]["state_label"]
    assert tab.NO_RING_TEXT in lbl and "A+ on the" not in lbl
    assert lbl == tab.state_label(r, False)
    assert lbl != tab.state_label(r)                                   # the un-ranged words would claim the A+


def test_NEGATIVE_D10_a_raising_ledger_keeps_todays_words_and_the_stages():
    r = _r("triggered")
    w = _omh_world(reads=[_read("OMH", {"kiss_fly": r})], pots=[_pot("OMH", "kiss_fly")], fail=(ST.ALERTS,))
    t = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]
    lbl = t["setups"][0]["state_label"]
    assert tab.NO_RING_TEXT not in lbl and lbl == tab.state_label(r)   # unknown is never "nothing rang"
    assert t["stages"] is not None and t["stages"]["title"] == SG.TITLE


def test_D10_a_pushed_claim_reads_rang():
    r = _r("triggered")
    w = _omh_world(reads=[_read("OMH", {"kiss_fly": r})], pots=[_pot("OMH", "kiss_fly")],
                   alerts=[claim(FRI, "OMH", "kiss_fly", 10, 35)])
    t = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]
    assert t["setups"][0]["state_label"] == tab.state_label(r, True)
    assert tab.NO_RING_TEXT not in t["setups"][0]["state_label"]
    assert "🎯 A+ 10:35" in t["stages"]["text"]                          # the rang A+ merged into the stages


# ── carded NEGATIVES (C2) ────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_reads_doc_serves_none(monkeypatch):
    _set(monkeypatch, _omh_world(reads=[]))
    rows, _ = _rows()
    assert rows["OMH"]["tags"] is None and rows["NVDA"]["tags"] is None


@pytest.mark.parametrize("states", [("none",), ("invalid",), ("none", "invalid"), ("aplus_held",), ("armed",)])
def test_NEGATIVE_none_or_invalid_reads_serve_none(states):
    setups = {s: _r(st) for s, st in zip(GC.SETUPS, states)}
    w = World(reads=[_read("OMH", setups)])
    assert TG.blocks(["OMH"], FRI, True, st=w.st) == {}


def test_NEGATIVE_a_potential_that_died_has_no_tags_and_is_never_read_further(monkeypatch):
    calls = _record_by_symbol(monkeypatch)
    w = _set(monkeypatch, World(reads=[_read("OMH", {"reversal_squeeze": _r("none")}),
                                       _read("NVDA", {"bull_flag": _r("aplus")})],
                                pots=[_pot("OMH", "reversal_squeeze"), _pot("NVDA", "bull_flag")],
                                scan=[_scan("OMH"), _scan("NVDA")]))
    rows, _ = _rows()
    assert rows["OMH"]["tags"] is None
    assert rows["NVDA"]["tags"]["on_board"] is True
    assert [list(c["symbols"]) for c in calls] == [["NVDA"]]
    (q, proj), = w.c[ST.SCAN].finds
    assert q["symbol"] == {"$in": ["NVDA"]} and proj == TG.SCAN_TAG_FIELDS


def test_NEGATIVE_a_tracker_doc_alone_never_cards():
    w = World(reads=[], pots=[_pot("OMH", "reversal_squeeze")])
    assert TG.blocks(["OMH"], FRI, True, st=w.st) == {}
    assert TG.on_board(None) is False and TG.carded_setups(None) == []


def test_NEGATIVE_a_vcp_read_under_the_D3_count_is_not_carded_and_the_count_cards_it():
    m = GC.vcp_list_min_cycles()
    assert isinstance(m, int)
    under = World(reads=[_read("OMH", {"intraday_vcp": _r("forming", cycles=m - 1)})])
    assert TG.blocks(["OMH"], FRI, True, st=under.st) == {}
    at = World(reads=[_read("OMH", {"intraday_vcp": _r("forming", cycles=m)})])
    assert TG.blocks(["OMH"], FRI, True, st=at.st)["OMH"]["setups"][0]["setup"] == "intraday_vcp"


def test_NEGATIVE_a_read_of_yesterdays_session_never_tags(monkeypatch):
    w = _set(monkeypatch, _omh_world(reads=[_read("OMH", {"kiss_fly": _r("aplus")}, session=YESTERDAY)]))
    rows, _ = _rows()
    assert rows["OMH"]["tags"] is None
    assert w.c[ST.READS].finds[0][0] == {"_id": {"$in": [ST.key(SESSION, "OMH"), ST.key(SESSION, "NVDA")]}}


# ── faults ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_broker_fault_serves_broker_text_none_and_the_rest(monkeypatch):
    monkeypatch.setattr(GC, "BROKER_FLAG_SEED", ("OMH",))              # the fail-open seed WOULD tag OMH
    w = _omh_world(fail=(ST.STATE,))
    seed, fault = ST.broker_flags(w.st)
    assert fault is True and "OMH" in seed
    t = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]
    assert t["broker_text"] is None
    assert t["stages"] and t["float"] and t["trader_text"] and t["setups"]


def test_a_tracker_fault_serves_stages_none_and_the_rest():
    w = _omh_world(fail=(ST.POTENTIALS,))
    t = TG.blocks(["OMH"], FRI, True, st=w.st)["OMH"]
    assert t["stages"] is None
    assert t["broker_text"] == tab.BROKER_FLAG_TEXT and t["float"] and t["setups"]


def test_NEGATIVE_a_raising_reads_coll_serves_none_everywhere_and_the_get_answers_200(monkeypatch):
    import ollama_chat.api as OA
    db = _db(["OMH", "NVDA"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH")
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setattr(CO, "_db", lambda: db)
    monkeypatch.setattr(CO, "loop_reads_soon", lambda now: True)
    monkeypatch.setattr(PL, "_now", lambda now: FRI_IN)
    w = _set(monkeypatch, _omh_world(fail=(ST.READS,)))
    assert TG.section(["OMH"], FRI, True) == {}
    app = FastAPI()
    app.include_router(API.router)
    r = TestClient(app).get(C.API_PATH, headers={"X-User-Email": OWNER})
    assert r.status_code == 200
    out = _strict(r.text)
    assert out["state"] == "ok" and [x["tags"] for x in out["rows"]] == [None, None]
    assert w.reads_of(ST.POTENTIALS, ST.ALERTS, ST.SCAN, ST.STATE) == {n: (0, 0) for n in
                                                                       (ST.POTENTIALS, ST.ALERTS, ST.SCAN, ST.STATE)}


def test_NEGATIVE_a_missing_reads_handle_or_scan_fault_serves_empty(monkeypatch):
    st = ST.GajjalaStore({ST.READS: None})
    monkeypatch.setattr(TG, "_store", lambda: st)
    assert TG.section(["OMH"], FRI, True) == {}
    _set(monkeypatch, _omh_world(fail=(ST.SCAN,)))
    assert TG.section(["OMH"], FRI, True) == {}


def test_NEGATIVE_a_raising_tags_module_leaves_the_board_answering(monkeypatch):
    monkeypatch.setitem(sys.modules, PL.TAGS_MODULE, None)              # import → ImportError
    rows, out = _rows()
    assert out["state"] == "ok" and all(r["tags"] is None for r in rows.values())
    monkeypatch.setitem(sys.modules, PL.TAGS_MODULE,
                        types.SimpleNamespace(section=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))))
    rows, out = _rows()
    assert out["state"] == "ok" and all(r["tags"] is None for r in rows.values())


def test_NEGATIVE_no_mongo_at_all_serves_none():
    """The real store with the test-session guard (no MongoClient) → every row None, the board answers."""
    rows, out = _rows()
    assert out["state"] == "ok" and all(r["tags"] is None for r in rows.values())


def test_NEGATIVE_no_massive_call_on_the_tags_path(monkeypatch):
    from chart_maps.gajjala import bars as B
    from daytrading import data as DT
    hits = []

    def trap(*a, **k):
        hits.append(a)
        raise AssertionError("the tags must never fetch")
    monkeypatch.setattr(B, "frames_for", trap)
    monkeypatch.setattr(DT, "load_intraday", trap)
    _set(monkeypatch, _omh_world())
    rows, _ = _rows()
    assert rows["OMH"]["tags"]["on_board"] is True and hits == []


# ── reads / projections ──────────────────────────────────────────────────────────────────────────────────────────
def test_projection_pins_reads_and_scan(monkeypatch):
    w = _set(monkeypatch, _omh_world())
    _rows()
    ids = [ST.key(SESSION, "OMH"), ST.key(SESSION, "NVDA")]
    assert w.c[ST.READS].finds == [({"_id": {"$in": ids}}, TG.TAGS_READ_FIELDS)]
    assert "tile" not in TG.TAGS_READ_FIELDS and set(TG.TAGS_READ_FIELDS) == {"symbol", "setups", "ctx.float"}
    win = SC._window(FRI)
    assert w.c[ST.SCAN].finds == [({"date": {"$in": [d.isoformat() for d in win]}, "symbol": {"$in": ["OMH"]}},
                                   TG.SCAN_TAG_FIELDS)]
    assert len(w.c[ST.POTENTIALS].finds) == len(win)                   # one per window session
    assert len(w.c[ST.ALERTS].finds) == 1 and len(w.c[ST.STATE].finds) == 1


def test_NEGATIVE_an_unlisted_only_name_is_never_in_any_find(monkeypatch):
    w = _set(monkeypatch, _omh_world(reads=[_read("OMH", {"kiss_fly": _r("aplus")}),
                                            _read("AMD", {"kiss_fly": _r("aplus")})],
                                     scan=[_scan("OMH"), _scan("AMD")]))
    rows, _ = _rows(only=["OMH", "AMD"])
    assert list(rows) == ["OMH"] and rows["OMH"]["tags"]["on_board"] is True
    assert w.c[ST.READS].finds == [({"_id": {"$in": [ST.key(SESSION, "OMH")]}}, TG.TAGS_READ_FIELDS)]
    assert "AMD" not in json.dumps([f for c in w.c.values() for f in c.finds], default=str)


def test_NEGATIVE_a_board_with_no_carded_name_makes_exactly_one_find(monkeypatch):
    w = _set(monkeypatch, _omh_world(reads=[_read("OMH", {"kiss_fly": _r("none")})]))
    rows, _ = _rows()
    assert all(r["tags"] is None for r in rows.values())
    assert w.reads_of(*w.c) == {ST.READS: (1, 0), ST.POTENTIALS: (0, 0), ST.ALERTS: (0, 0), ST.SCAN: (0, 0),
                                ST.STATE: (0, 0)}


def test_NEGATIVE_no_names_no_find(monkeypatch):
    w = _set(monkeypatch, _omh_world())
    out = PL.build(FRI_IN, db=_db([]))
    assert out["state"] == "ok" and out["rows"] == []
    assert all(len(c.finds) == 0 for c in w.c.values())


# ── the clock (C5) ───────────────────────────────────────────────────────────────────────────────────────────────
def test_C5_a_pre_open_monday_serves_fridays_tags_on_builds_own_clock(monkeypatch):
    assert MON_PRE.weekday() == 0 and tab.session_for(MON_PRE) == (FRI, False, False)
    calls = _record_by_symbol(monkeypatch)
    _set(monkeypatch, _omh_world())
    rows, out = _rows(now=MON_PRE)
    assert out["session"] == SESSION and out["is_today"] is False
    assert rows["OMH"]["tags"]["on_board"] is True
    assert [(c["board_session"], c["is_today"]) for c in calls] == [(FRI, False)]
    assert rows["OMH"]["tags"]["stages"]["groups"][0]["clock"] is False   # not today → the date label, no clock


def test_C5_the_payload_hands_its_own_session_and_is_today(monkeypatch):
    seen = []
    monkeypatch.setitem(sys.modules, PL.TAGS_MODULE,
                        types.SimpleNamespace(section=lambda n, s, t: seen.append((list(n), s, t)) or {}))
    _rows()
    assert seen == [(["OMH", "NVDA"], FRI, True)]


def test_source_guard_no_clock_in_tags_py():
    src = SRC.read_text()
    for bad in ("session_for(", "datetime.now", "_now(", "date.today("):
        assert bad not in src, bad


# ── source guards (C3a) ──────────────────────────────────────────────────────────────────────────────────────────
def _string_constants(src: str) -> list:
    tree = ast.parse(src)
    skip = set()
    first = tree.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
        skip.add(id(first.value))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("TAGS_READ_FIELDS",
                                                                                  "SCAN_TAG_FIELDS")
                                                for t in node.targets):
            skip.update(id(n) for n in ast.walk(node.value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip]


def test_source_guard_no_digit_typed_and_no_f_string():
    src = SRC.read_text()
    assert re.findall(r"\d", "".join(_string_constants(src))) == []
    assert sum(isinstance(n, ast.JoinedStr) for n in ast.walk(ast.parse(src))) == 0


def test_NEGATIVE_the_digit_guard_catches_a_typed_digit():
    bad = SRC.read_text() + '\nX = "the 5-minute board"\n'
    assert re.findall(r"\d", "".join(_string_constants(bad))) != []
    assert sum(isinstance(n, ast.JoinedStr) for n in ast.walk(ast.parse(bad + 'Y = f"{X}"\n'))) == 1


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _strings(v)


def test_served_strings_never_carry_the_b_word():
    w = _omh_world(reads=[_read("OMH", {"reversal_squeeze": _r("forming"), "kiss_fly": _r("triggered"),
                                        "bull_flag": _r("stopped")})],
                   pots=[_pot("OMH", "reversal_squeeze"), _pot("OMH", "kiss_fly")])
    blk = TG.blocks(["OMH"], FRI, True, st=w.st)
    words = list(_strings(blk))
    assert words and not [s for s in words if B_WORD.search(s)]
    assert not B_WORD.search("".join(_string_constants(SRC.read_text())))


def test_finder_keywords_default_to_the_tags_projection_byte_for_byte():
    """PIN 2026-11-22 (spec watch_org rev 4): `_find_scan` / `_find_reads` gained keyword-only `fields` (and `names=None`
    drops the symbol clause) for 📅 runners.py — the defaults ARE this block's own projection, so the tags query is
    unchanged."""
    import inspect
    ps, pr = inspect.signature(TG._find_scan).parameters, inspect.signature(TG._find_reads).parameters
    assert ps["fields"].default is TG.SCAN_TAG_FIELDS and pr["fields"].default is TG.TAGS_READ_FIELDS
    assert ps["fields"].kind is inspect.Parameter.KEYWORD_ONLY and pr["fields"].kind is inspect.Parameter.KEYWORD_ONLY
    w = World(scan=[_scan("OMH")], reads=[_read("OMH", {"kiss_fly": _r("aplus")})])
    TG._find_scan(w.st, [SESSION], ["OMH"])
    TG._find_reads(w.st, [ST.key(SESSION, "OMH")])
    assert w.c[ST.SCAN].finds == [({"date": {"$in": [SESSION]}, "symbol": {"$in": ["OMH"]}}, TG.SCAN_TAG_FIELDS)]
    assert w.c[ST.READS].finds == [({"_id": {"$in": [ST.key(SESSION, "OMH")]}}, TG.TAGS_READ_FIELDS)]
