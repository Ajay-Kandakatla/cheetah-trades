"""🚫 "not eligible at the broker" — his own list, a TAG on every Gajjala row (2026-10-17, DECISIONS12 D1–D9,
BUILD_SPEC12 §3 / WP-A, AMENDMENTS12 A1 + F1–F9).

Ajay 2026-10-17, verbatim (his 2nd and 3rd lines): "ok then avoid showing me names that are not eligible in Fidelity
then." / "Or just add a tag that not eligible on Fidelity". A TAG, never a filter: nothing here may hide, reorder or
mute a name. The list = constants.BROKER_FLAG_SEED (EMPTY — he withdrew WORX) ∪ his adds − his removes in ONE
gajjala_state doc; served to the PRIMARY admin only (ollama_chat.api.is_primary_admin — the second household email is a
non-owner here, F1); a store read fault FAILS OPEN TO THE SEED and says so (F5). Every seed below is a monkeypatch.
NEGATIVES are mandatory: two emails, a faulting store, a removed seed, no chip on an unflagged row, the clause only when
flagged, routes 404 / 400 / 503 / round-trip / idempotent, the interleaved writes.
"""
from __future__ import annotations

import contextlib
import json
import threading
from datetime import datetime

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from tests.test_gajjala_store import FakeColl, fake_store
from tests import test_gajjala_tab as TT
from tests import test_gajjala_potential as TP
from tests import test_gajjala_potential_tab as PTT
from tests import test_gajjala_on_open as OO
from tests import test_gajjala_track_record_tab as TRT
from tests import test_gajjala_alerts as TA

TEXT = "🚫 not eligible at Fidelity"
OWNER = "ajaykandakatla@gmail.com"                 # the primary admin (ollama_chat.api.PRIMARY_ADMIN_EMAIL)
COHOST = "cohost@example.com"                      # a SECOND house owner: is_admin_email True, NOT the primary admin
DOUG = "doug@example.com"
BROKER_KEYS = ("broker_text", "broker_flags", "graveyard_broker_text")


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture
def cohost(monkeypatch):
    import auth
    monkeypatch.setattr(auth, "HOUSE_OWNER_EMAILS", [OWNER, COHOST])
    assert auth.is_admin_email(COHOST) is True          # a house admin …
    from ollama_chat.api import is_primary_admin
    assert is_primary_admin(COHOST) is False            # … but not HIS Fidelity list's owner (F1)
    return COHOST


def flag(st, *syms, removed=()):
    """His list through the doc itself (the shape set_broker_flag writes)."""
    st.coll(ST.STATE).docs[ST.BROKER_STATE_ID] = {"_id": ST.BROKER_STATE_ID, "added": list(syms),
                                                   "removed": list(removed)}
    return st


def strip_broker(o):
    if isinstance(o, dict):
        return {k: strip_broker(v) for k, v in o.items() if k not in BROKER_KEYS}
    if isinstance(o, list):
        return [strip_broker(v) for v in o]
    return o


def tagged_dicts(o, path="$"):
    """Every served dict carrying a `broker_text` key, with its path."""
    if isinstance(o, dict):
        if "broker_text" in o:
            yield path, o
        for k, v in o.items():
            yield from tagged_dicts(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from tagged_dicts(v, f"{path}[{i}]")


def assert_tags(out, flagged):
    """Every tagged row: the served word iff its symbol is on the list ("." / "-" folded) — NEGATIVE: never on any other
    row. -> the paths that carry the word."""
    want = {ST.broker_fold(s) for s in flagged}
    hits = []
    for path, d in tagged_dicts(out):
        on = ST.broker_fold(d.get("symbol")) in want
        assert d["broker_text"] == (TEXT if on else None), (path, d.get("symbol"), d["broker_text"])
        if on:
            hits.append(path)
    return hits


def assert_all_null(out):
    assert out["broker_flags"] is None
    for path, d in tagged_dicts(out):
        assert d["broker_text"] is None, path
    assert out.get("graveyard_broker_text") is None


# ── 1. the effective set (D1, F5) ─────────────────────────────────────────────────────────────────────────────────
def test_effective_set_is_seed_union_added_minus_removed(monkeypatch):
    monkeypatch.setattr(GC, "BROKER_FLAG_SEED", ("AAA", "BBB"))
    st = flag(fake_store(), "ccc", " ddd ", "ccc", 5, "1X", removed=["BBB"])
    assert ST.broker_flags(st) == (("AAA", "CCC", "DDD"), False)
    assert ST.broker_doc(st) == {"seed": ["AAA", "BBB"], "added": ["CCC", "DDD"], "removed": ["BBB"],
                                 "symbols": ["AAA", "CCC", "DDD"], "fault": False}


def test_the_shipped_seed_is_empty_and_no_doc_is_an_empty_list():
    assert GC.BROKER_FLAG_SEED == () and GC.BROKER_NAME == "Fidelity"
    assert ST.broker_flags(fake_store()) == ((), False)


class _NoFind:
    def __init__(self, get_state):
        self.get_state = get_state


@pytest.mark.parametrize("make", [
    lambda: fake_store(**{ST.STATE: FakeColl(fail=True)}),            # Mongo down on the state collection
    lambda: object(),                                                  # no reader at all
    lambda: _NoFind(lambda sid: (_ for _ in ()).throw(RuntimeError("boom"))),   # a raising get_state
    lambda: None,                                                      # no store
], ids=["state_fault", "no_reader", "raising_get_state", "none"])
def test_NEGATIVE_a_read_fault_fails_open_to_the_seed(monkeypatch, make):
    monkeypatch.setattr(GC, "BROKER_FLAG_SEED", ("AAA",))
    assert ST.broker_flags(make()) == (("AAA",), True)


def test_NEGATIVE_a_junk_doc_reads_the_seed_alone(monkeypatch):
    monkeypatch.setattr(GC, "BROKER_FLAG_SEED", ("AAA",))
    st = fake_store()
    st.coll(ST.STATE).docs[ST.BROKER_STATE_ID] = {"_id": ST.BROKER_STATE_ID, "added": "XYZ", "removed": None}
    assert ST.broker_flags(st) == (("AAA",), False)


def test_a_removed_seed_is_gone(monkeypatch):
    monkeypatch.setattr(GC, "BROKER_FLAG_SEED", ("AAA", "BBB"))
    assert ST.broker_flags(flag(fake_store(), removed=["AAA"])) == (("BBB",), False)


def test_dot_and_dash_are_one_ticker_both_ways():
    """AMENDMENTS12 F8 — the list stores the typed form; membership folds "." / "-" on both sides."""
    assert GT.broker_text_for("MOG-A", frozenset({"MOG.A"})) == TEXT
    assert GT.broker_text_for("mog.a", frozenset({"MOG-A"})) == TEXT
    assert GT.broker_text_for("MOGA", frozenset({"MOG.A"})) is None                  # NEGATIVE
    assert GT.broker_text_for("ABCD", None) is None                                   # NEGATIVE: a non-owner
    assert GT.broker_text_for(None, frozenset({"ABCD"})) is None
    assert GT.broker_text_for("ABCD", frozenset()) is None


# ── 2. writes (D5, F2) ────────────────────────────────────────────────────────────────────────────────────────────
def _doc(st):
    return st.coll(ST.STATE).docs.get(ST.BROKER_STATE_ID)


def test_add_writes_the_doc_once_and_is_idempotent():
    st = fake_store()
    assert st.set_broker_flag("abcd", True, by=OWNER) == ("ABCD",)
    d = _doc(st)
    assert d["added"] == ["ABCD"] and d["removed"] == [] and d["by"] == OWNER
    assert isinstance(d["updated_at"], datetime) and d["updated_at"].tzinfo is not None
    assert st.set_broker_flag("ABCD", True, by=OWNER) == ("ABCD",)
    assert _doc(st)["added"] == ["ABCD"]                                             # one entry
    assert st.coll(ST.STATE).writes == 2


def test_remove_an_added_name_then_a_seeded_name_then_re_add(monkeypatch):
    monkeypatch.setattr(GC, "BROKER_FLAG_SEED", ("SEED",))
    st = fake_store()
    assert st.set_broker_flag("ABCD", True, by=OWNER) == ("ABCD", "SEED")
    assert st.set_broker_flag("ABCD", False, by=OWNER) == ("SEED",)
    assert _doc(st)["added"] == []
    assert st.set_broker_flag("SEED", False, by=OWNER) == ()                         # a seed overridden, no deploy
    assert _doc(st)["removed"] == ["SEED"] and ST.broker_flags(st) == ((), False)
    assert st.set_broker_flag("seed", True, by=OWNER) == ("SEED",)
    assert _doc(st)["removed"] == [] and _doc(st)["added"] == []                     # back from the seed alone


def test_NEGATIVE_a_read_fault_writes_nothing():
    coll = FakeColl(fail=True)
    st = fake_store(**{ST.STATE: coll})
    assert st.set_broker_flag("ABCD", True, by=OWNER) is None
    assert coll.writes == 0


@pytest.mark.parametrize("bad", ["", "1ABC", "AB C", "AB$", "ABCDEFGHIJK", None, 5])
def test_NEGATIVE_an_invalid_symbol_writes_nothing(bad):
    st = fake_store()
    assert st.set_broker_flag(bad, True, by=OWNER) is None
    assert st.coll(ST.STATE).writes == 0 and _doc(st) is None


class _SlowState(FakeColl):
    """Both writers read before either writes when nothing serialises them (a barrier inside the read)."""
    def __init__(self):
        super().__init__()
        self.barrier = threading.Barrier(2, timeout=0.5)

    def find(self, q=None, projection=None):
        snap = super().find(q, projection)
        try:
            self.barrier.wait()
        except threading.BrokenBarrierError:
            pass
        return snap


def _two_writers(st):
    ts = [threading.Thread(target=st.set_broker_flag, args=(s, True), kwargs={"by": OWNER}) for s in ("AAA", "BBB")]
    for t in ts:
        t.start()
    for t in ts:
        t.join(5)
    return _doc(st)["added"]


def test_two_interleaved_writes_keep_both_names():
    """AMENDMENTS12 F2 — the read + the $set run under one lock."""
    assert _two_writers(fake_store(**{ST.STATE: _SlowState()})) == ["AAA", "BBB"]


def test_NEGATIVE_a_lock_free_write_drops_a_name(monkeypatch):
    """The mutation proves the test bites: without the lock both read an empty doc and the last write wins."""
    monkeypatch.setattr(ST, "_BROKER_LOCK", contextlib.nullcontext())
    assert len(_two_writers(fake_store(**{ST.STATE: _SlowState()}))) == 1


# ── 3. broker_symbol (D5) ─────────────────────────────────────────────────────────────────────────────────────────
def test_broker_symbol_normalises_a_ticker():
    assert ST.broker_symbol("abc") == "ABC"
    assert ST.broker_symbol(" brk.b ") == "BRK.B"
    assert ST.broker_symbol("BF-B") == "BF-B"
    assert ST.broker_symbol("ABCDEFGHIJ") == "ABCDEFGHIJ"                           # 10 = the cap


@pytest.mark.parametrize("bad", ["", "1ABC", "AB C", "AB$", "ABCDEFGHIJK", None, 5])
def test_NEGATIVE_broker_symbol_refuses(bad):
    assert ST.broker_symbol(bad) is None


def test_NEGATIVE_a_query_object_is_not_a_symbol():
    from fastapi import Query
    assert ST.broker_symbol(Query("")) is None


def test_the_length_cap_is_read_at_call_time(monkeypatch):
    assert ST.broker_symbol("ABCDEFGHIJK") is None
    monkeypatch.setattr(GC, "BROKER_SYMBOL_MAX_LEN", 11)
    assert ST.broker_symbol("ABCDEFGHIJK") == "ABCDEFGHIJK"
    assert "at most 10 characters" in GT.BROKER_BAD_SYMBOL                          # built from the constant


# ── 4. build: EVERY §3.4 surface carries the tag, no other row does, nothing hidden ───────────────────────────────
def test_the_served_words_are_built_from_the_constants():
    assert GT.BROKER_FLAG_TEXT == TEXT == f"🚫 not eligible at {GC.BROKER_NAME}"
    assert GT.BROKER_FLAG_ICON == "🚫"
    b = GT.broker_block(frozenset({"ABCD"}))
    assert b == {"editable": True, "symbols": ["ABCD"], "text": TEXT, "broker": "Fidelity", "toggle": "🚫",
                 "empty_text": "none on your list yet — add a ticker when its order ticket refuses it",
                 "fault_text": None, "add_label": "add", "add_placeholder": "ticker",
                 "remove_title": "take it off the list"}


def test_setup_tiles_and_the_aplus_rows():
    st = flag(TT.ordering_store(), "AAA")
    out = GT.build("bull_flag", now=TT.NOW, store=st, owner=True)
    hits = assert_tags(out, {"AAA"})
    assert any(p.startswith("$.tiles[") for p in hits)
    assert [t["symbol"] for t in out["tiles"]] == TT.EXPECTED                         # NEGATIVE: nothing hidden / moved
    assert out["broker_flags"]["symbols"] == ["AAA"] and out["broker_flags"]["editable"] is True


def test_the_enterable_rows():
    out, st = OO.board({"GGA": {OO.BF: TT.R(OO.BF, "aplus", entry_bar_t="2026-10-13 10:30", broke=True)},
                        "GGB": {OO.BF: TT.R(OO.BF, "aplus", entry_bar_t="2026-10-13 10:25", broke=True)}})
    flag(st, "GGA")
    o = GT.build(OO.BF, now=OO.NOW, store=st, owner=True)
    rows = {r["symbol"]: r["broker_text"] for r in o["enterable"]["rows"]}
    assert rows == {"GGA": TEXT, "GGB": None}
    assert_tags(o, {"GGA"})


def test_premarket_tiles():
    out = GT.build("premarket", now=TT.NOW, store=flag(TT._pm_store(), "CARY"), owner=True)
    assert {t["symbol"]: t["broker_text"] for t in out["tiles"]} == {"BIGV": None, "BIGC": None, "CARY": TEXT}
    assert_tags(out, {"CARY"})


def test_postmarket_tiles_and_the_recap_rows():
    out = GT.build("postmarket", now=TT.utc(19, 58), store=flag(TT._post_store(), "HIGG", "PFAI"), owner=True)
    assert {t["symbol"]: t["broker_text"] for t in out["tiles"]} == {"HIGG": TEXT, "LOWG": None}
    assert {r["symbol"]: r["broker_text"] for r in out["postmarket"]["recap"]["rows"]} == {"PFAI": TEXT, "STOP": None}
    assert_tags(out, {"HIGG", "PFAI"})


def test_potential_tiles_track_rows_watch_and_the_strip():
    st = flag(PTT.day_store(), "AAA", "PMX")
    p = PTT.build(GC.POTENTIAL_SUB, st, owner=True)
    hits = assert_tags(p, {"AAA", "PMX"})
    for prefix in ("$.tiles[", "$.track.today.rows[", "$.track.yesterday.rows[", "$.watch.symbols["):
        assert any(h.startswith(prefix) for h in hits), prefix
    bf = PTT.build("bull_flag", st, owner=True)
    assert any(h.startswith("$.potential.rows[") for h in assert_tags(bf, {"AAA", "PMX"}))


def test_the_graveyard_line_names_only_flagged_names():
    scans = [TT.scan_doc("OLDX", day=TT.GONE), TT.scan_doc("KEEP", day=TT.GONE), TT.scan_doc("KEEP", day=TT.PREV)]
    st = TT.store_with(scans=scans, passes=[TT.latest()])
    out = GT.build("bull_flag", now=TT.NOW, store=flag(st, "OLDX"), owner=True)
    assert out["graveyard_today"] == ["OLDX"] and out["graveyard_broker_text"] == "🚫 not eligible at Fidelity: OLDX"
    neg = GT.build("bull_flag", now=TT.NOW, store=flag(st, "KEEP"), owner=True)
    assert neg["graveyard_text"] and neg["graveyard_broker_text"] is None            # NEGATIVE: not on the list
    none = GT.build("bull_flag", now=TT.NOW, store=TT.store_with(passes=[TT.latest()]), owner=True)
    assert "graveyard_text" not in none and "graveyard_broker_text" not in none     # present iff graveyard_text


def test_the_track_record_rows():
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()
    st = flag(TRT.golden_store(), "RPL")
    out = TRT.board(st, "5d", owner=True)
    rows = [r for d in out["track_record"]["days"] for r in d["rows"]]
    assert rows and {r["symbol"] for r in rows if r["broker_text"] == TEXT} == {"RPL"}
    assert all(r["broker_text"] is None for r in rows if r["symbol"] != "RPL")     # NEGATIVE
    assert_tags(out, {"RPL"})


def test_NEGATIVE_served_block_without_a_callable_serves_null_and_a_raising_one_too():
    LG._TODAY_MEMO.clear()
    st = TRT.golden_store()
    b = LG.served_block(st, TRT.D16, TRT.NOW, span="5d", is_today=True, today=None)
    assert all(r["broker_text"] is None for d in b["days"] for r in d["rows"])
    boom = LG.served_block(st, TRT.D16, TRT.NOW, span="5d", is_today=True, today=None,
                           broker_text_of=lambda s: (_ for _ in ()).throw(RuntimeError("x")))
    assert strip_broker(boom) == strip_broker(b)


def _boards():
    pst = flag(PTT.day_store(post_rows=[{"symbol": "AAA", "ah_gain_pct": 5.0, "close_pos": 0.9, "ah_volume": 3e5}]),
               "AAA", "PMX")
    tst = flag(TT._post_store(), "HIGG", "PFAI")
    for k, _e, _l in GC.SUBS:
        if k == GC.LEDGER_SUB:
            continue
        yield k, (lambda owner, k=k: PTT.build(k, pst, owner=owner))
    yield "postmarket_tab", (lambda owner: GT.build("postmarket", now=TT.utc(19, 58), store=tst, owner=owner))

    def tr(owner):
        LG._TODAY_MEMO.clear()
        LG._TODAY_SPLIT.clear()
        return TRT.board(flag(TRT.golden_store(), "RPL"), "5d", owner=owner)
    yield GC.LEDGER_SUB, tr


@pytest.mark.parametrize("name,make", list(_boards()), ids=[n for n, _m in _boards()])
def test_NEGATIVE_nothing_hidden_the_owner_payload_minus_the_tags_is_the_non_owner_payload(name, make):
    own, other = make(True), make(False)
    assert own["broker_flags"] and own["broker_flags"]["editable"] is True
    assert_all_null(other)
    assert json.dumps(strip_broker(own), sort_keys=True, default=str) == json.dumps(strip_broker(other),
                                                                                    sort_keys=True, default=str)


@pytest.mark.parametrize("owner", [False, None, 1, "yes", object()])
def test_NEGATIVE_only_owner_True_is_an_owner(owner):
    st = flag(TT.ordering_store(), "AAA")
    assert_all_null(GT.build("bull_flag", now=TT.NOW, store=st, owner=owner))


def test_NEGATIVE_an_empty_list_tags_nothing_and_serves_the_empty_text():
    out = GT.build("bull_flag", now=TT.NOW, store=TT.ordering_store(), owner=True)
    assert assert_tags(out, set()) == []
    b = out["broker_flags"]
    assert b["symbols"] == [] and b["empty_text"] == GT.BROKER_EMPTY_TEXT and b["fault_text"] is None


def test_NEGATIVE_a_faulting_store_still_tags_the_seed_and_says_so(monkeypatch):
    """F5 — WORX (a monkeypatched seed) stays tagged with Mongo's state collection down; the block says the list could
    not be read (editable False, fault_text), never "none on your list yet"."""
    monkeypatch.setattr(GC, "BROKER_FLAG_SEED", ("AAA",))
    st = _with_state(TT.ordering_store(), FakeColl(fail=True))
    out = GT.build("bull_flag", now=TT.NOW, store=st, owner=True)
    assert any(p.startswith("$.tiles[") for p in assert_tags(out, {"AAA"}))
    b = out["broker_flags"]
    assert b["editable"] is False and b["fault_text"] == GT.BROKER_FAULT_TEXT and b["empty_text"] is None
    assert b["symbols"] == ["AAA"]


def _with_state(st, coll):
    """The fixture store with its gajjala_state collection replaced."""
    colls = {n: st.coll(n) for n in ST.ALL}
    colls[ST.STATE] = coll
    return ST.GajjalaStore(colls=colls)


# ── 5. the board GET (D3, F1) ─────────────────────────────────────────────────────────────────────────────────────
def _get(monkeypatch, st, **kw):
    from chart_maps import api as API
    from chart_maps import board as board_mod
    monkeypatch.setattr(ST, "default", lambda: st)
    monkeypatch.setattr(GT, "_clock", lambda: TT.NOW)
    monkeypatch.setattr(board_mod, "_live_snapshot", lambda tiles: {})
    monkeypatch.setattr(board_mod, "attach_live_now", lambda tiles, out, live=None: None)
    return json.loads(TT.run_route(API.chart_maps_gajjala(**kw)).body)


def test_the_board_get_serves_the_owner_the_block_and_the_tags(monkeypatch):
    body = _get(monkeypatch, flag(TT.ordering_store(), "AAA"), email=OWNER)
    assert body["broker_flags"]["symbols"] == ["AAA"] and body["broker_flags"]["text"] == TEXT
    assert {t["symbol"]: t["broker_text"] for t in body["tiles"]}["AAA"] == TEXT
    assert_tags(body, {"AAA"})


@pytest.mark.parametrize("who", ["doug", "cohost", "nobody"])
def test_NEGATIVE_any_other_reader_gets_null_everywhere(monkeypatch, request, who):
    kw = {"doug": {"email": DOUG}, "cohost": {"email": request.getfixturevalue("cohost")},
          "nobody": {}}[who]                                                          # nobody = the Depends OBJECT
    body = _get(monkeypatch, flag(TT.ordering_store(), "AAA"), **kw)
    assert_all_null(body)
    assert [t["symbol"] for t in body["tiles"]] == TT.EXPECTED                        # the same rows, nothing hidden


def test_the_board_get_slice_gates_on_the_primary_admin_and_names_no_route():
    import inspect
    from chart_maps import api as API
    src = inspect.getsource(API.chart_maps_gajjala)
    assert "is_primary_admin(" in src and "owner=" in src
    assert "on_demand" not in src and "entry_tape" not in src and "broker-flags" not in src


# ── 6. the three owner routes (D5, F1, F3) — through HTTP ────────────────────────────────────────────────────────
@pytest.fixture
def client(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps import api as API
    st = fake_store()
    monkeypatch.setattr(ST, "default", lambda: st)
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    c.store = st
    return c


P = "/chart-maps/gajjala/broker-flags"


def _hdr(email):
    return {"X-User-Email": email}


@pytest.mark.parametrize("who", ["doug", "cohost"])
def test_NEGATIVE_a_non_owner_gets_404_on_all_three_whatever_the_body(client, request, who):
    email = DOUG if who == "doug" else request.getfixturevalue("cohost")
    h = _hdr(email)
    assert client.get(P, headers=h).status_code == 404
    assert client.post(P, json={"symbol": "ABCD"}, headers=h).status_code == 404
    assert client.post(P, json={"symbol": "1BAD"}, headers=h).status_code == 404
    assert client.post(P, content=b"{not json", headers=dict(h, **{"Content-Type": "application/json"})).status_code == 404
    assert client.post(P, content=b"[1, 2", headers=h).status_code == 404            # F3: never a 422
    assert client.post(P, headers=h).status_code == 404
    assert client.delete(f"{P}/ABCD", headers=h).status_code == 404
    assert client.delete(f"{P}/AB%20C", headers=h).status_code == 404
    assert client.store.coll(ST.STATE).writes == 0 and _doc(client.store) is None


def test_owner_bad_symbol_is_400_with_the_served_reason(client):
    h = _hdr(OWNER)
    for r in (client.post(P, json={"symbol": "1BAD"}, headers=h), client.post(P, json=None, headers=h),
              client.post(P, content=b"{not json", headers=dict(h, **{"Content-Type": "application/json"})),
              client.post(P, headers=h), client.post(P, json=["ABCD"], headers=h),
              client.delete(f"{P}/AB%20C", headers=h), client.delete(f"{P}/1BAD", headers=h)):
        assert r.status_code == 400 and r.json() == {"detail": GT.BROKER_BAD_SYMBOL}, (r.status_code, r.text)
    assert client.store.coll(ST.STATE).writes == 0


def test_owner_round_trip_add_idempotent_remove(client):
    h = _hdr(OWNER)
    g = client.get(P, headers=h)
    assert g.status_code == 200 and set(g.json()) == {"symbols", "seed", "added", "removed", "text", "broker", "fault_text"}
    assert g.json() == {"symbols": [], "seed": [], "added": [], "removed": [], "text": TEXT, "broker": "Fidelity",
                        "fault_text": None}
    assert "fault" not in g.json()                                                     # the store flag is not served
    a = client.post(P, json={"symbol": "abcd"}, headers=h)
    assert a.status_code == 200 and a.json()["symbols"] == ["ABCD"] and a.json()["added"] == ["ABCD"]
    assert client.post(P, json={"symbol": "ABCD"}, headers=h).json() == a.json()   # idempotent
    assert _doc(client.store)["by"] == OWNER
    d = client.delete(f"{P}/abcd", headers=h)
    assert d.status_code == 200 and d.json()["symbols"] == []
    u = client.delete(f"{P}/ZZZZ", headers=h)
    assert u.status_code == 200 and u.json() == d.json()                              # unknown: 200, unchanged


def test_NEGATIVE_the_editor_block_says_a_read_fault_and_serves_the_seed_alone(monkeypatch):
    """Critic 2026-10-17 (AMENDMENTS12 F5 reaches the editor too): the owner's GET on a faulting store is 200 with the
    seed alone AND `fault_text` = BROKER_FAULT_TEXT — never a silent `added: []` that reads as an empty list. A healthy
    store serves `fault_text: None`. `broker_doc` carries the flag; the block never serves the raw `fault` key."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps import api as API
    monkeypatch.setattr(GC, "BROKER_FLAG_SEED", ("AAA",))
    bad = fake_store(**{ST.STATE: FakeColl(fail=True)})
    assert ST.broker_doc(bad) == {"seed": ["AAA"], "added": [], "removed": [], "symbols": ["AAA"], "fault": True}
    b = GT.editor_block(bad)
    assert b["fault_text"] == GT.BROKER_FAULT_TEXT and b["symbols"] == ["AAA"] and "fault" not in b
    assert GT.editor_block(fake_store())["fault_text"] is None
    monkeypatch.setattr(ST, "default", lambda: bad)
    app = FastAPI()
    app.include_router(API.router)
    r = TestClient(app).get(P, headers=_hdr(OWNER))
    assert r.status_code == 200 and r.json()["fault_text"] == GT.BROKER_FAULT_TEXT and r.json()["symbols"] == ["AAA"]
    assert bad.coll(ST.STATE).writes == 0


def test_owner_write_fault_is_503_and_writes_nothing(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps import api as API
    coll = FakeColl(fail=True)
    st = fake_store(**{ST.STATE: coll})
    monkeypatch.setattr(ST, "default", lambda: st)
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    for r in (c.post(P, json={"symbol": "ABCD"}, headers=_hdr(OWNER)), c.delete(f"{P}/ABCD", headers=_hdr(OWNER))):
        assert r.status_code == 503 and r.json() == {"detail": GT.BROKER_WRITE_FAULT}
    assert coll.writes == 0


def test_the_routes_sit_after_the_entry_tape_and_a_put_is_405(client):
    from pathlib import Path
    from chart_maps import api as API
    src = Path(API.__file__).read_text(encoding="utf-8")
    tape = src.index('@router.get("/chart-maps/gajjala/entry-tape")')
    news = src.index('@router.get("/chart-maps/news")')
    marks = [src.index(m) for m in ('@router.get("/chart-maps/gajjala/broker-flags")',
                                    '@router.post("/chart-maps/gajjala/broker-flags")',
                                    '@router.delete("/chart-maps/gajjala/broker-flags/{symbol}")')]
    assert tape < marks[0] < marks[1] < marks[2] < news
    for a, b in zip(marks, marks[1:] + [src.index("\nasync def _broker_answer")]):
        sl = src[a:b]
        assert "is_primary_admin(" in sl and "404" in sl
    assert client.put(P, json={"symbol": "ABCD"}, headers=_hdr(OWNER)).status_code == 405


# ── 7. the push bodies (D4, A1) ───────────────────────────────────────────────────────────────────────────────────
OLD_BODY = ("broke 11.00 on the 5m bar closing 10:35 ET · stop 10.81 (−1.7%) · Kissed and honored the 9 EMA; entry = "
            "the kiss bar's high · 🧠 potential rang 10:05 ET · Float 3.2M · UNMEASURED — his setup, not a buy signal")


def _ab(**kw):
    return AL.compose(TA.read("kiss_fly", entry=TA.stamp(10, 35)), "gga", {"float_text": "Float 3.2M"}, session=TA.S,
                      potential_at_et="10:05", **kw)


def test_the_aplus_body_says_it_before_unmeasured_and_the_title_carries_the_icon():
    p = _ab(broker_text=GT.BROKER_FLAG_TEXT)
    assert p["body"] == ("broke 11.00 on the 5m bar closing 10:35 ET · stop 10.81 (−1.7%) · Kissed and honored the 9 "
                         "EMA; entry = the kiss bar's high · 🧠 potential rang 10:05 ET · Float 3.2M · 🚫 not eligible "
                         "at Fidelity · UNMEASURED — his setup, not a buy signal")
    assert p["title"] == "💋 GGA · EMA Kiss & Fly A+ entry · 🚫" and p["title"].endswith(" · " + GT.BROKER_FLAG_ICON)
    ah = AL.compose(TA.read("kiss_fly", entry=TA.stamp(16, 35)), "gga", {}, session=TA.S,
                    broker_text=GT.BROKER_FLAG_TEXT)["body"]
    assert ah.index(AL.AH_TAG) < ah.index(TEXT) < ah.index(AL.UNMEASURED_TAIL)


@pytest.mark.parametrize("bad", [None, "", 5])
def test_NEGATIVE_unflagged_aplus_body_and_title_are_todays(bad):
    p = _ab(broker_text=bad)
    assert p["body"] == OLD_BODY and p["title"] == "💋 GGA · EMA Kiss & Fly A+ entry"
    assert _ab() == p


def test_the_potential_body_says_it_right_before_the_tail_on_the_lock_screen():
    r = TP.bf_armed()
    p = PT.compose("AAA", "bull_flag", r, "armed", {"float_text": "Float 3.1M"}, first_seen_et="10:06", tape="rth",
                   broker_text=GT.BROKER_FLAG_TEXT)
    bits = p["body"].split(" · ")
    assert bits[:4] == ["trigger 10.97", "stop 10.81 (−1.4%)", GT.BROKER_FLAG_TEXT, PT.TAIL]
    assert len(p["title"] + " " + " · ".join(bits[:3])) <= 180
    assert p["title"] == "🧠 AAA · 🚩 Bull Flag — trigger armed · UNMEASURED · 🚫"
    k = TP.kf_building()
    b = PT.compose("AAA", "kiss_fly", k, "building", {}, first_seen_et=None, tape="rth",
                   broker_text=GT.BROKER_FLAG_TEXT)["body"].split(" · ")
    assert b[:5] == [k["reason"], "trigger 10.48 (not armed yet)", "stop 10.42 (−0.6%)", GT.BROKER_FLAG_TEXT, PT.TAIL]


@pytest.mark.parametrize("bad", [None, "", 5])
def test_NEGATIVE_unflagged_potential_body_and_title_are_todays(bad):
    r = TP.bf_armed()
    p = PT.compose("AAA", "bull_flag", r, "armed", {}, first_seen_et="10:06", tape="rth", broker_text=bad)
    assert p["body"].split(" · ")[2] == PT.TAIL
    assert p["title"] == "🧠 AAA · 🚩 Bull Flag — trigger armed · UNMEASURED"
    assert p == PT.compose("AAA", "bull_flag", r, "armed", {}, first_seen_et="10:06", tape="rth")


class _CountingState(FakeColl):
    def __init__(self, docs=None):
        super().__init__(docs)
        self.reads = 0

    def find(self, q=None, projection=None):
        self.reads += 1
        return super().find(q, projection)

    def find_one(self, q=None, projection=None):
        self.reads += 1
        return super().find_one(q, projection)


def _counting(monkeypatch):
    n = {"calls": 0}
    real = ST.broker_flags

    def wrapped(store):
        n["calls"] += 1
        return real(store)
    monkeypatch.setattr(ST, "broker_flags", wrapped)
    return n


def _ab_pass(st, sender):
    return AL.run_pass({"GGA": {"bull_flag": TA.read()}, "GGB": {"bull_flag": TA.read()}},
                       {"GGA": TA.frames_at(TA.stamp(10, 5)), "GGB": TA.frames_at(TA.stamp(10, 5))},
                       TA.at(10, 6), TA.S, store=st, send=sender, owner="owner@example.com", ctx={})


def test_the_aplus_pass_rings_both_and_only_the_flagged_body_says_it(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    state = _CountingState([{"_id": ST.BROKER_STATE_ID, "added": ["GGA"], "removed": []}])
    st = fake_store(**{ST.STATE: state})
    n = _counting(monkeypatch)
    send = TA.Spy()
    counts = _ab_pass(st, send)
    assert counts["pushed"] == 2 and counts["broker_flagged"] == 1 and "broker_flagged" == AL.COUNT_KEYS[-1]
    by = {p["ticker"]: p for _o, p in send.calls}
    assert TEXT in by["GGA"]["body"] and by["GGA"]["title"].endswith(" · 🚫")
    assert TEXT not in by["GGB"]["body"] and not by["GGB"]["title"].endswith("🚫")   # NEGATIVE
    assert n["calls"] == 1 and state.reads == 1                                       # ONE read per pass


def test_NEGATIVE_an_empty_list_leaves_the_aplus_bodies_byte_equal(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    a, b = TA.Spy(), TA.Spy()
    ca = _ab_pass(fake_store(), a)
    cb = _ab_pass(flag(fake_store(), "ZZZZ"), b)
    assert [p for _o, p in a.calls] == [p for _o, p in b.calls] and ca["broker_flagged"] == cb["broker_flagged"] == 0
    assert all(TEXT not in p["body"] for _o, p in a.calls)


def _pot_pass(st, send):
    TP.seed(st)
    return TP.go(st, TP.at(10, 6), {"AAA": {"bull_flag": TP.bf_armed()}, "BBB": {"bull_flag": TP.bf_armed()}},
                 send=send)


def test_the_potential_pass_rings_both_and_only_the_flagged_body_says_it(monkeypatch):
    st = flag(fake_store(), "AAA")
    n = _counting(monkeypatch)
    send = TP.Rec(TP.OK_SEND)
    out = _pot_pass(st, send)
    assert out["pushed"] == 2 and set(out) == set(PT.COUNT_KEYS)                     # PT.COUNT_KEYS unchanged
    by = {a[1]["ticker"]: a[1] for a, _k in send.calls}
    assert TEXT in by["AAA"]["body"] and by["AAA"]["title"].endswith(" · 🚫")
    assert TEXT not in by["BBB"]["body"] and not by["BBB"]["title"].endswith("🚫")   # NEGATIVE
    assert n["calls"] == 1


def test_NEGATIVE_an_empty_list_leaves_the_potential_bodies_byte_equal():
    a, b = TP.Rec(TP.OK_SEND), TP.Rec(TP.OK_SEND)
    _pot_pass(fake_store(), a)
    _pot_pass(flag(fake_store(), "ZZZZ"), b)
    assert [x[0][1] for x in a.calls] == [x[0][1] for x in b.calls] and len(a.calls) == 2
    assert all(TEXT not in x[0][1]["body"] for x in a.calls)


def test_NEGATIVE_a_faulting_store_still_tags_the_seeded_push(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    monkeypatch.setattr(GC, "BROKER_FLAG_SEED", ("GGA",))
    st = fake_store(**{ST.STATE: FakeColl(fail=True)})
    send = TA.Spy()
    counts = _ab_pass(st, send)
    assert counts["pushed"] == 2 and counts["broker_flagged"] == 1
    assert TEXT in {p["ticker"]: p for _o, p in send.calls}["GGA"]["body"]


# ── 8. ℹ️ the Rules panel (D6) ────────────────────────────────────────────────────────────────────────────────────
def test_the_rules_line_and_the_note():
    from supply_demand import rules_info as RI
    sec = RI._gajjala_section()
    assert sec["stops"][-1] == ("🚫 Not eligible at Fidelity — your own list of names Fidelity would not let you buy "
                                "online; a tag only — nothing is hidden, the pushes still ring and carry the tag. "
                                "Nothing is seeded.")
    assert "went through at Fidelity on 2026-10-16" in sec["note"] and "XELB under a dollar" in sec["note"]
    assert sec["note"].endswith("Not advice.")


def test_the_rules_line_follows_the_seed(monkeypatch):
    from supply_demand import rules_info as RI
    monkeypatch.setattr(GC, "BROKER_FLAG_SEED", ("ABC",))
    assert RI._gajjala_section()["stops"][-1].endswith("Seeded with ABC.")
    monkeypatch.setattr(GC, "BROKER_NAME", "Other")
    assert RI._gajjala_section()["stops"][-1].startswith("🚫 Not eligible at Other — ")


# ── the words ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_ban_word_and_no_forecast_in_the_served_words():
    words = [GT.BROKER_FLAG_TEXT, GT.BROKER_EMPTY_TEXT, GT.BROKER_FAULT_TEXT, GT.BROKER_ADD_LABEL,
             GT.BROKER_ADD_PLACEHOLDER, GT.BROKER_REMOVE_TITLE, GT.BROKER_BAD_SYMBOL, GT.BROKER_WRITE_FAULT]
    for w in words:
        low = w.lower()
        assert "b" + "ounc" not in low and "fake" not in low and "forecast" not in low and "predict" not in low, w
