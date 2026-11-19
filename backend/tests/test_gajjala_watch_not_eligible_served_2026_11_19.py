"""🚫 his broker list on 👀 Gajjala's Watch — the served words (spec watchfid §3.2 / §4 WP-B, 2026-11-19).

Ajay 2026-11-19, verbatim: "Add a button to say not in fidelity, AZI and CHSN are not in fidelity don't add them to watch
list".

`gajjala_watch/broker.py` serves, on the owner's GET only and from ONE list read: every row's `broker_text`, the board's
`broker` block (BROKER_KEYS), and the 🤖 hint's sentence (auto.broker_words) before its final "UNMEASURED."; his add answer
carries the word (never blocked). The auto ENGINE (WP-A) is a sys.modules stub here — the seam is `broker_words()` plus the
loop state doc's `auto.not_eligible` / `auto.broker_fault`.

NEGATIVES: an unflagged name → None; a list-read fault → every row None, never the seed guess; another session's state doc
/ an empty list / an old doc → no auto line; no phrase / a raising phrase / a hint without the tail → the hint unchanged;
applying twice → once; an unflagged / faulting / bad add → the answer unchanged; a non-owner reads nothing and gets no
"broker"; the broker routes are a stealth 404 for anyone else; a raising broker module → the board still answers; the
code types neither the broker's name nor the word.
"""
from __future__ import annotations

import ast
import re
import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as GS
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import broker as BR
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import store as WST
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_api_2026_11_15 import FRI_IN, OTHER, OWNER, SESSION, _doc, _strict
from tests.test_gajjala_watch_auto_served_2026_11_17 import _db, _entry

AUTO_MOD = "chart_maps.gajjala_watch.auto"
WORDS = "a name on your 🚫 list never takes a 🤖 auto seat, and a seated potential leaves at the next minute"
SENTENCE = WORDS[0].upper() + WORDS[1:]
WATCH_DIR = Path(BR.__file__).resolve().parent


class StubAuto(types.SimpleNamespace):
    """WP-A's engine as a stub: no own reads of the broker list; `broker_words` is the seam."""

    def __init__(self):
        super().__init__(words=WORDS, raise_words=False)

    def read_doc(self, cs):
        try:
            return cs["list"].find_one({"_id": C.AUTO_DOC_ID}) or {}
        except Exception:                                      # noqa: BLE001
            return None

    def dismiss(self, symbol, *, by=None, db=None, now=None):
        return {"state": "absent"}

    def rules_line(self):
        return "STUB-AUTO-RULES-LINE"

    def broker_words(self):
        if self.raise_words:
            raise RuntimeError("words blew up")
        return self.words


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.build",
                        types.SimpleNamespace(uptrend_rule=lambda: "STUB-UPTREND-RULE"))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.cross_alerts",
                        types.SimpleNamespace(rules_line=lambda: "STUB-PUSH-TEXT"))
    monkeypatch.setitem(sys.modules, PL.TAGS_MODULE, types.SimpleNamespace(section=lambda *a, **k: {}))
    monkeypatch.setattr(PL, "aplus_section", lambda names, siso, **k: {})
    eng = StubAuto()
    monkeypatch.setitem(sys.modules, AUTO_MOD, eng)
    return eng


class Flags:
    """The ONE broker list behind `broker._store` — a GajjalaStore whose STATE collection is a FakeColl."""

    def __init__(self, monkeypatch, added=(), *, fail=False):
        self.coll = FakeColl([{"_id": GS.BROKER_STATE_ID, "added": list(added), "removed": []}], fail=fail)
        self.st = GS.GajjalaStore({GS.STATE: self.coll})
        monkeypatch.setattr(BR, "_store", lambda: self.st)


def _rows(out):
    return {r["symbol"]: r for r in out["rows"]}


def _state_doc(session=SESSION, **auto):
    return {"_id": C.STATE_LATEST_ID, "session": session, "auto": dict(auto)}


def _client(monkeypatch, db):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setattr(CO, "_db", lambda: db)
    monkeypatch.setattr(CO, "enabled", lambda: False)                  # no build child in these tests
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app)


# ── 1. rows ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_every_row_carries_broker_text_flagged_uncarded_his_and_auto(monkeypatch):
    Flags(monkeypatch, ["OMH", "XXII"])
    out = PL.build(FRI_IN, db=_db(["OMH", "NVDA"], [_entry("XXII"), _entry("AAPL")]))
    rows = _rows(out)
    assert list(rows) == ["OMH", "NVDA", "XXII", "AAPL"]
    assert all("broker_text" in r for r in out["rows"])
    assert rows["OMH"]["tags"] is None and rows["OMH"]["broker_text"] == GT.BROKER_FLAG_TEXT   # uncarded, his
    assert rows["XXII"]["auto"] is not None and rows["XXII"]["broker_text"] == GT.BROKER_FLAG_TEXT  # a 🤖 row
    assert rows["NVDA"]["broker_text"] is None and rows["AAPL"]["broker_text"] is None          # NEG: unflagged


# ── 2. ONE read per build ──────────────────────────────────────────────────────────────────────────────────────────
def test_one_list_read_per_build_and_per_pending_poll(monkeypatch):
    Flags(monkeypatch, ["OMH"])
    real, calls = BR.read, []

    def counted():
        calls.append(1)
        return real()
    monkeypatch.setattr(BR, "read", counted)
    out = PL.build(FRI_IN, db=_db(["OMH", "NVDA"], [_entry("XXII")]))
    assert len(out["rows"]) == 3 and len(calls) == 1
    calls.clear()
    poll = PL.build(FRI_IN, db=_db(["OMH", "NVDA"], [_entry("XXII")]), only=["OMH"])
    assert [r["symbol"] for r in poll["rows"]] == ["OMH"] and len(calls) == 1


# ── 3. fold ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_fold_dot_equals_dash(monkeypatch):
    Flags(monkeypatch, ["BRK-B"])
    rows = _rows(PL.build(FRI_IN, db=_db(["BRK.B", "BRKB"])))
    assert rows["BRK.B"]["broker_text"] == GT.BROKER_FLAG_TEXT
    assert rows["BRKB"]["broker_text"] is None                                    # NEG: no fold beyond "." == "-"


# ── 4. fault ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_fault_every_row_none_not_editable_with_the_fault_line(monkeypatch):
    Flags(monkeypatch, ["OMH"], fail=True)
    out = PL.build(FRI_IN, db=_db(["OMH", "NVDA"]))
    assert [r["broker_text"] for r in out["rows"]] == [None, None]
    b = out["broker"]
    assert b["editable"] is False and b["fault_text"] == "🚫 " + GT.BROKER_FAULT_TEXT


def test_NEGATIVE_a_fault_never_serves_the_seed_guess(monkeypatch):
    monkeypatch.setattr(GC, "BROKER_FLAG_SEED", ("CHSN",))
    Flags(monkeypatch, [], fail=True)
    assert GS.broker_flags(BR._store()) == (("CHSN",), True)                      # the store fails open to the seed …
    rows = _rows(PL.build(FRI_IN, db=_db(["CHSN"])))
    assert rows["CHSN"]["broker_text"] is None                                    # … the Watch never serves it


def test_NEGATIVE_a_raising_store_reads_as_a_fault(monkeypatch):
    monkeypatch.setattr(BR, "_store", lambda: (_ for _ in ()).throw(RuntimeError("no store")))
    assert BR.read() == (None, True)
    out = PL.build(FRI_IN, db=_db(["OMH"]))
    assert out["state"] == "ok" and out["rows"][0]["broker_text"] is None and out["broker"]["editable"] is False


# ── 5. the board block ─────────────────────────────────────────────────────────────────────────────────────────────
def test_board_block_keys_and_words(monkeypatch):
    Flags(monkeypatch, ["OMH"])
    b = PL.build(FRI_IN, db=_db(["OMH"]))["broker"]
    assert tuple(b) == BR.BROKER_KEYS
    assert b["toggle"] == GT.BROKER_FLAG_ICON and b["text"] == GT.BROKER_FLAG_TEXT
    assert b["title"] == BR.MARK_TITLE_TEXT.format(text=GT.BROKER_FLAG_TEXT)
    assert b["editable"] is True and b["fault_text"] is None                      # NEG: no fault line on a good read
    assert b["auto_text"] is None and b["auto_fault_text"] is None


# ── 6. the 🤖 auto lines ───────────────────────────────────────────────────────────────────────────────────────────
def test_auto_text_from_this_sessions_state_doc(monkeypatch):
    Flags(monkeypatch, ["AZI", "CHSN"])
    db = _db(["OMH"])
    db[C.COLL_STATE].docs[C.STATE_LATEST_ID] = _state_doc(not_eligible=["AZI", "CHSN"], broker_fault=False)
    b = PL.build(FRI_IN, db=db)["broker"]
    assert b["auto_text"] == BR.AUTO_KEPT_OFF_TEXT.format(icon=GT.BROKER_FLAG_ICON, names="AZI, CHSN")
    assert b["auto_text"].endswith("AZI, CHSN") and b["auto_fault_text"] is None


def test_NEGATIVE_auto_lines():
    assert BR.auto_lines(_state_doc(session="2026-11-12", not_eligible=["AZI"], broker_fault=True), SESSION) \
        == (None, None)                                                           # another session
    assert BR.auto_lines(_state_doc(not_eligible=[], broker_fault=False), SESSION) == (None, None)
    assert BR.auto_lines(_state_doc(aplus_skipped=["X"]), SESSION) == (None, None)  # an old doc (no keys)
    assert BR.auto_lines({"_id": "latest", "session": SESSION}, SESSION) == (None, None)
    assert BR.auto_lines(None, SESSION) == (None, None) and BR.auto_lines(_state_doc(), None) == (None, None)
    assert BR.auto_lines(_state_doc(not_eligible=["", 5, None]), SESSION) == (None, None)
    assert BR.auto_lines(_state_doc(broker_fault="yes"), SESSION) == (None, None)  # only a real True
    t, f = BR.auto_lines(_state_doc(not_eligible=[], broker_fault=True), SESSION)
    assert t is None and f == BR.AUTO_FAULT_TEXT.format(icon=GT.BROKER_FLAG_ICON)


# ── 7. the 🤖 hint ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_hint_gains_the_sentence_once_before_unmeasured(monkeypatch):
    Flags(monkeypatch, [])
    h = PL.build(FRI_IN, db=_db(["OMH"], [_entry("XXII")]))["auto"]["hint"]
    base = PL.auto_hint()
    assert h.count(SENTENCE) == 1 and h.endswith("UNMEASURED.")
    assert h == base[:-len("UNMEASURED.")] + SENTENCE + ". UNMEASURED."
    assert BR.hint_with_rule(h) == h                                              # applying twice → still once


@pytest.mark.parametrize("mode", ["none", "raise", "blank", "missing"])
def test_NEGATIVE_no_phrase_leaves_the_hint_byte_equal(monkeypatch, stubs, mode):
    Flags(monkeypatch, [])
    if mode == "none":
        stubs.words = None
    elif mode == "raise":
        stubs.raise_words = True
    elif mode == "blank":
        stubs.words = "  "
    else:
        monkeypatch.setitem(sys.modules, AUTO_MOD, types.SimpleNamespace(
            read_doc=StubAuto().read_doc, rules_line=lambda: "X", dismiss=lambda *a, **k: {"state": "absent"}))
    out = PL.build(FRI_IN, db=_db(["OMH"], [_entry("XXII")]))
    assert out["auto"]["hint"] == PL.auto_hint()


def test_NEGATIVE_a_hint_without_the_tail_or_no_auto_block():
    assert BR.hint_with_rule("no tail here") == "no tail here"
    assert BR.hint_with_rule(None) is None
    out = {"rows": [], "auto": None}
    BR.apply(out, state_doc=None, siso=SESSION)                                   # never raises
    assert out["auto"] is None


# ── 8. pinned shapes stay ──────────────────────────────────────────────────────────────────────────────────────────
def test_the_auto_block_key_set_is_unchanged(monkeypatch):
    Flags(monkeypatch, ["XXII"])
    a = PL.build(FRI_IN, db=_db(["OMH"], [_entry("XXII")]))["auto"]
    assert set(a) == {"state", "cap", "n", "symbols", "title", "hint", "empty_text", "text", "removed",
                      "removed_total", "removed_title", "push_mode", "skipped_text"}


# ── 9. his add: the word, never a block ────────────────────────────────────────────────────────────────────────────
def test_add_of_a_flagged_name_lands_and_carries_the_word(monkeypatch):
    Flags(monkeypatch, ["AMD"])
    db = _db(["OMH"])
    out = _client(monkeypatch, db).post(C.API_PATH + "/symbols/amd", headers={"X-User-Email": OWNER}).json()
    assert out["state"] == "added" and out["symbols"] == ["OMH", "AMD"]
    assert set(out) == {"state", "symbols", "symbol", "text"}
    assert out["text"] == PL.store_text("added", "AMD") + " · " + GT.BROKER_FLAG_TEXT
    assert db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"] == ["OMH", "AMD"]       # never blocked


def test_a_replaced_answer_at_the_cap_carries_the_word(monkeypatch):
    Flags(monkeypatch, ["AMD"])
    monkeypatch.setattr(WST, "aplus_names", lambda cur: set())
    full = [f"N{chr(65 + i // 26)}{chr(65 + i % 26)}" for i in range(C.MAX_SYMBOLS)]
    db = _db(full)
    out = _client(monkeypatch, db).post(C.API_PATH + "/symbols/AMD", headers={"X-User-Email": OWNER}).json()
    assert out["state"] == "replaced" and out["symbols"][-1] == "AMD"
    assert out["text"].endswith(" · " + GT.BROKER_FLAG_TEXT) and out["replaced"] == full[0]
    assert set(out) == {"state", "symbols", "symbol", "text", "replaced"}         # the store's own keys, none added


@pytest.mark.parametrize("case", ["unflagged", "fault", "bad_symbol", "raise"])
def test_NEGATIVE_the_add_answer_unchanged(monkeypatch, case):
    Flags(monkeypatch, ["OTHR"] if case != "fault" else ["AMD"], fail=(case == "fault"))
    if case == "raise":
        monkeypatch.setitem(sys.modules, PL.BROKER_MODULE, types.SimpleNamespace(
            add_note=lambda out: (_ for _ in ()).throw(RuntimeError("boom"))))
    db = _db(["OMH"])
    sym = "1BAD" if case == "bad_symbol" else "AMD"
    out = _client(monkeypatch, db).post(C.API_PATH + f"/symbols/{sym}", headers={"X-User-Email": OWNER}).json()
    if case == "bad_symbol":
        assert out["state"] == "bad_symbol" and out["text"] == PL.store_text("bad_symbol", None)
    else:
        assert out["state"] == "added" and out["text"] == PL.store_text("added", "AMD")
        assert db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"] == ["OMH", "AMD"]
    assert GT.BROKER_FLAG_TEXT not in out["text"] and set(out) == {"state", "symbols", "symbol", "text"}


def test_add_note_states_and_keys():
    flagged = lambda: (("AMD",), False)                                            # noqa: E731
    import unittest.mock as M
    with M.patch.object(BR, "read", flagged):
        for st in BR.NOTE_STATES:
            o = {"state": st, "symbols": [], "symbol": "AMD", "text": "t"}
            assert BR.add_note(o) == dict(o, text="t · " + GT.BROKER_FLAG_TEXT) and o["text"] == "t"
        for st in ("full", "error", "bad_symbol", "removed"):                     # NEG: other states
            o = {"state": st, "symbols": [], "symbol": "AMD", "text": "t"}
            assert BR.add_note(o) is o
        assert BR.add_note(None) is None


# ── 10. non-owner ──────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("headers", [{"X-User-Email": OTHER}, {}])
def test_NEGATIVE_a_non_owner_reads_nothing_and_gets_no_broker(monkeypatch, headers):
    calls = []
    monkeypatch.setattr(BR, "read", lambda: calls.append(1) or (("OMH",), False))
    r = _client(monkeypatch, _db(["OMH"])).get(C.API_PATH, headers=headers)
    body = _strict(r.text)
    assert r.status_code == 200 and body == PL.owner_only_payload() and set(body) == {"state", "reason", "title"}
    assert "broker" not in r.text and "🚫" not in r.text and calls == []


def test_NEGATIVE_the_broker_routes_are_a_stealth_404_for_anyone_else(monkeypatch):
    import ollama_chat.api as OA
    from chart_maps import api as CMAPI
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    f = Flags(monkeypatch, [])
    monkeypatch.setattr(GS, "default", lambda: f.st)
    app = FastAPI()
    app.include_router(CMAPI.router)
    c = TestClient(app)
    P, h = "/chart-maps/gajjala/broker-flags", {"X-User-Email": OTHER}
    assert c.get(P, headers=h).status_code == 404
    assert c.post(P, json={"symbol": "AZI"}, headers=h).status_code == 404
    assert c.delete(P + "/AZI", headers=h).status_code == 404
    assert f.coll.writes == 0


# ── 11. NaN-free ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_owner_get_with_flags_is_strict_json(monkeypatch):
    Flags(monkeypatch, ["OMH"])
    db = _db(["OMH"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH", nan=True)
    r = _client(monkeypatch, db).get(C.API_PATH, headers={"X-User-Email": OWNER})
    body = _strict(r.text)
    assert body["rows"][0]["broker_text"] == GT.BROKER_FLAG_TEXT and body["broker"]["editable"] is True


# ── 12. a raising broker module ────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_raising_broker_module_keeps_the_board(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("broker blew up")
    monkeypatch.setitem(sys.modules, PL.BROKER_MODULE, types.SimpleNamespace(apply=boom))
    out = PL.build(FRI_IN, db=_db(["OMH", "NVDA"], [_entry("XXII")]))
    assert out["state"] == "ok" and len(out["rows"]) == 3
    assert all(r["broker_text"] is None for r in out["rows"]) and out["broker"] is None
    assert out["auto"]["hint"] == PL.auto_hint()


def test_NEGATIVE_apply_inner_fault_serves_none_rows_and_a_fault_block(monkeypatch):
    monkeypatch.setattr(BR, "read", lambda: (("OMH",), False))
    monkeypatch.setattr(BR, "text_for", lambda s, f: (_ for _ in ()).throw(RuntimeError("x")))
    out = {"rows": [{"symbol": "OMH"}, "junk"], "auto": None}
    BR.apply(out, state_doc=None, siso=SESSION)
    assert out["rows"][0]["broker_text"] is None and out["broker"]["editable"] is False


# ── 13. source ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _code(path: Path) -> str:
    """The module's code with every docstring and comment stripped (ast round-trip)."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant) \
                    and isinstance(first.value.value, str):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


@pytest.mark.parametrize("name", ["broker.py", "payload.py", "api.py"])
def test_the_code_types_neither_the_broker_name_nor_the_word(name):
    code = _code(WATCH_DIR / name)
    assert not re.search("fidelity", code, re.I) and "not eligible" not in code


def test_broker_py_composes_from_tab_and_store():
    code = _code(WATCH_DIR / "broker.py")
    for n in ("GT.BROKER_FLAG_TEXT", "GT.BROKER_FLAG_ICON", "GT.BROKER_FAULT_TEXT", "GT.broker_text_for",
              "GS.broker_flags", "broker_words"):
        assert n in code, n
    src = (WATCH_DIR / "payload.py").read_text()
    call = "\n    _broker_section(out, state_doc, siso)"
    assert src.count("BROKER_MODULE = ") == 1 and src.count("def _broker_section(") == 1 and src.count(call) == 1
    assert src.index(call) < src.index('if any(r["state"] == "pending"')
