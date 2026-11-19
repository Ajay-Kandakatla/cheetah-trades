"""👀 Gajjala's Watch — the owner doc's `added` map, his rows NEWEST ADDED FIRST, the late words, the honest cap words
(spec watchnew2 §3.1, WP-BE-list, 2026-11-19).

Ajay 2026-11-19, verbatim (relayed): "When I add a new ticket they are gettinf added in to que but not active" ·
"charts are not loading I amhaving to click on the chips again". Earlier: "When ever I push something to watch it make it
active by default and also on top".

NEGATIVES: an `already` never writes `symbols` and a failing write there is never `error`; no key holds a dot; junk
`added` values are undated and never break an add / remove / the board; the cap still takes the FIRST-added name (his
11-18 "Oldest added") and no served sentence says "oldest you added"; the evictee is never 🎯 A+; an A+ read fault
removes nothing; a 🤖 entry with no / junk time serves null; the pending words carry no time number; an `ok` row has no
`late_text`; no `pending_late_poll_sec` when nothing is pending; an order-sensitive store still takes our write.
"""
from __future__ import annotations

import json
import re
import sys
import types
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import auto as AUTO
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import store as ST
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_api_2026_11_15 import FRI_IN, SESSION, SUN, RecColl, _doc, _strict
from tests.test_gajjala_watch_auto_served_2026_11_17 import AUTO_MOD, StubAuto, _entry

ET = ZoneInfo("America/New_York")
T0 = datetime(2026, 11, 19, 14, 0, tzinfo=timezone.utc)
NAMES = [f"A{chr(65 + i)}" for i in range(C.MAX_SYMBOLS)]          # list order = first-add order


class Clock:
    """ST._now_utc stand-in — a fixed clock the test moves by hand."""

    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture()
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(ST, "_now_utc", c)
    return c


@pytest.fixture()
def board(monkeypatch):
    """The board's lazy siblings stubbed (the api tests' pattern) + no 🎯 A+ store read."""
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.build", types.SimpleNamespace(uptrend_rule=lambda: "R"))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.cross_alerts",
                        types.SimpleNamespace(rules_line=lambda: "P"))
    eng = StubAuto()
    monkeypatch.setitem(sys.modules, AUTO_MOD, eng)
    monkeypatch.setattr(PL, "aplus_section", lambda names, siso, stores=None: {})
    return eng


@pytest.fixture()
def aplus(monkeypatch):
    st = {"set": set(), "reads": 0, "boom": False}

    def fake(names):
        st["reads"] += 1
        if st["boom"]:
            raise RuntimeError("reads down")
        return {n for n in names if n in st["set"]}
    monkeypatch.setattr(ST, "aplus_names", fake)
    return st


def _list_doc(symbols, added=None, **extra):
    d = {"_id": C.LIST_DOC_ID, "symbols": list(symbols)}
    if added is not None:
        d["added"] = added
    d.update(extra)
    return d


def _db(symbols=None, added=None, *, entries=None, list_coll=None):
    docs = [_list_doc(symbols, added)] if symbols is not None else []
    if entries is not None:
        docs.append({"_id": C.AUTO_DOC_ID, "session": SESSION, "rev": 1, "entries": list(entries), "removed": [],
                     "dismissed": []})
    lc = list_coll if list_coll is not None else RecColl(docs)
    return {C.COLL_LIST: lc, C.COLL_TILES: RecColl(), C.COLL_ALERTS: RecColl(), C.COLL_STATE: RecColl()}


def _stored(db):
    d = db[C.COLL_LIST].docs.get(C.LIST_DOC_ID)
    return None if d is None else d


def _syms(out):
    return [r["symbol"] for r in out["rows"]]


class _Recording(FakeColl):
    def __init__(self, docs=None):
        super().__init__(docs)
        self.updates = []

    def update_one(self, q, upd, upsert=False):
        self.updates.append((q, upd))
        return super().update_one(q, upd, upsert=upsert)


# ── store: the `added` map ─────────────────────────────────────────────────────────────────────────────────────────
def test_add_stamps_the_time_and_the_answer_shape_is_unchanged(clock):
    db = _db([])
    t1 = clock.t = T0 + timedelta(minutes=1)
    a = ST.add("omh", by="owner", db=db)
    assert set(a) == {"state", "symbols", "symbol", "text"} and a["state"] == "added"
    assert _stored(db)["added"] == {"OMH": t1}
    t2 = clock.t = T0 + timedelta(minutes=2)
    b = ST.add("NVDA", by="owner", db=db)
    assert set(b) == {"state", "symbols", "symbol", "text"}
    assert _stored(db)["added"] == {"OMH": t1, "NVDA": t2} and _stored(db)["symbols"] == ["OMH", "NVDA"]


def test_already_refreshes_only_that_time_and_never_writes_symbols(clock):
    clock.t = T0 + timedelta(hours=1)
    lc = _Recording([_list_doc(["OMH", "NVDA"], {"OMH": T0, "NVDA": T0 + timedelta(seconds=1)})])
    db = _db(list_coll=lc)
    before = list(_stored(db)["symbols"])
    out = ST.add("omh", by="owner", db=db)
    assert out["state"] == "already" and out["symbols"] == ["OMH", "NVDA"]
    assert lc.writes == 1 and len(lc.updates) == 1
    assert "symbols" not in lc.updates[0][1]["$set"]
    assert _stored(db)["symbols"] == before == ["OMH", "NVDA"]
    assert _stored(db)["added"] == {"OMH": clock.t, "NVDA": T0 + timedelta(seconds=1)}


def test_already_via_the_other_spelling_keys_the_fold_never_a_dot(clock):
    db = _db([])
    assert ST.add("BRK.B", by="owner", db=db)["state"] == "added"
    out = ST.add("brk-b", by="owner", db=db)
    assert out["state"] == "already" and _stored(db)["symbols"] == ["BRK.B"]
    assert list(_stored(db)["added"]) == ["BRK-B"] and _stored(db)["added"]["BRK-B"] == clock.t
    ST.add("MOG.A", by="owner", db=db)
    assert not any("." in k for k in _stored(db)["added"])                  # NEGATIVE: a dot would nest in Mongo


def test_an_old_doc_without_added_serves_his_order_then_a_first_add_goes_first(clock, board):
    db = _db(["ZZT", "AAA", "MMM"])
    out = PL.build(FRI_IN, db=db)
    assert _syms(out) == ["ZZT", "AAA", "MMM"] and all(r["added_at"] is None for r in out["rows"])
    assert ST.add("NEW", by="owner", db=db)["state"] == "added"
    assert _stored(db)["added"] == {"NEW": clock.t}                          # that name only
    out = PL.build(FRI_IN, db=db)
    assert _syms(out) == ["NEW", "ZZT", "AAA", "MMM"]
    assert out["symbols"] == ["ZZT", "AAA", "MMM", "NEW"]                    # the card list stays the stored order


def test_remove_prunes_the_key_and_a_replace_prunes_old_and_stamps_new(clock, aplus):
    db = _db([])
    for s in ("OMH", "NVDA", "AMD"):
        ST.add(s, by="owner", db=db)
    assert ST.remove("nvda", by="owner", db=db)["state"] == "removed"
    assert set(_stored(db)["added"]) == {"OMH", "AMD"}
    full = _db(NAMES, {s: T0 + timedelta(minutes=i) for i, s in enumerate(NAMES)})
    out = ST.add("ZZZ", by="owner", db=full)
    assert out["state"] == "replaced" and out["replaced"] == NAMES[0]
    assert NAMES[0] not in _stored(full)["added"] and _stored(full)["added"]["ZZZ"] == clock.t
    assert set(_stored(full)["added"]) == set(NAMES[1:]) | {"ZZZ"}


# ── the cap: unchanged order (his 11-18 "Oldest added"), honest words ──────────────────────────────────────────────
def test_cap_still_takes_the_first_added_even_when_it_was_re_added(clock, aplus, board):
    added = {s: T0 + timedelta(minutes=i) for i, s in enumerate(NAMES)}
    added[NAMES[0]] = T0 + timedelta(hours=5)                                 # NAMES[0] ➕'d again — newest time
    db = _db(NAMES, added)
    assert _syms(PL.build(FRI_IN, db=db))[0] == NAMES[0]                      # first on the board
    out = ST.add("ZZZ", by="owner", db=db)
    assert out["state"] == "replaced" and out["replaced"] == NAMES[0]         # still the cap's pick (list order)
    assert "(on your watch the longest)" in out["text"]


def test_NEGATIVE_no_served_sentence_says_oldest_you_added():
    texts = [PL.FULL_REPLACES_TEXT, PL.REPLACED_TEXT, PL.REPLACED_PAST_APLUS_TEXT, PL.full_hint(), PL.full_text()]
    texts += [PL.store_text(st, "OMH", old="NVDA", past_aplus=p) for st in ST.STATES_ADD + ST.STATES_REMOVE
              for p in (False, True)]
    assert texts and not any("oldest you added" in t for t in texts)
    assert "on your watch the longest" in PL.full_hint()
    assert PL.store_text("replaced", "ZZZ", old="OMH", past_aplus=True).endswith(
        "(on your watch the longest that is not 🎯 A+) made room")


def test_an_aplus_oldest_is_passed_over(clock, aplus):
    aplus["set"] = {NAMES[0]}
    out = ST.add("ZZZ", by="owner", db=_db(NAMES))
    assert out["state"] == "replaced" and out["replaced"] == NAMES[1]
    assert out["text"] == PL.store_text("replaced", "ZZZ", old=NAMES[1], past_aplus=True)


def test_NEGATIVE_every_name_aplus_is_full_and_nothing_is_written(clock, aplus):
    aplus["set"] = set(NAMES)
    db = _db(NAMES)
    out = ST.add("ZZZ", by="owner", db=db)
    assert out["state"] == "full" and _stored(db)["symbols"] == NAMES and db[C.COLL_LIST].writes == 0
    assert "added" not in _stored(db)


def test_NEGATIVE_an_aplus_read_fault_removes_nothing(clock, aplus):
    aplus["boom"] = True
    db = _db(NAMES)
    out = ST.add("ZZZ", by="owner", db=db)
    assert out["state"] == "full" and _stored(db)["symbols"] == NAMES and db[C.COLL_LIST].writes == 0


@pytest.mark.parametrize("aps", [{NAMES[0]}, {NAMES[0], NAMES[1], NAMES[2]}, set(NAMES[:-1]), {NAMES[3]}])
def test_NEGATIVE_the_evicted_name_is_never_aplus(clock, aplus, aps):
    aplus["set"] = set(aps)
    out = ST.add("ZZZ", by="owner", db=_db(NAMES))
    assert out["state"] == "replaced" and out["replaced"] not in aps


# ── compare-and-set on `added` ─────────────────────────────────────────────────────────────────────────────────────
class _RacingAdded(FakeColl):
    """Another tab's ➕ again of AMD lands right after OUR first read: it changes ONLY `added`."""

    def __init__(self, docs, tx):
        super().__init__(docs)
        self.tx, self.reads = tx, 0

    def find_one(self, q=None, projection=None):
        d = super().find_one(q, projection)
        self.reads += 1
        if self.reads == 1:
            self.docs[C.LIST_DOC_ID]["added"]["AMD"] = self.tx
        return d


def test_a_racer_that_changes_only_added_is_refused_then_both_times_survive(clock):
    tx = T0 + timedelta(hours=1)
    lc = _RacingAdded([_list_doc(["OMH", "AMD"], {"OMH": T0})], tx)
    db = _db(list_coll=lc)
    out = ST.add("NVDA", by="owner", db=db)
    assert out["state"] == "added" and lc.reads == 2 and lc.writes == 2        # first write refused, re-read, landed
    assert _stored(db)["added"] == {"OMH": T0, "AMD": tx, "NVDA": clock.t}
    assert _stored(db)["symbols"] == ["OMH", "AMD", "NVDA"]


class _Ordered(FakeColl):
    """BSON compares sub-documents in KEY ORDER: an `added` filter matches only the same keys in the same order."""

    def update_one(self, q, upd, upsert=False):
        want = q.get("added") if isinstance(q, dict) else None
        if isinstance(want, dict) and not any(k.startswith("$") for k in want):
            have = (self.docs.get(q.get("_id")) or {}).get("added")
            if not isinstance(have, dict) or list(have.items()) != list(want.items()):
                self.writes += 1
                return types.SimpleNamespace(upserted_id=None, matched_count=0)
        return super().update_one(q, upd, upsert=upsert)


def test_NEGATIVE_an_order_sensitive_store_still_takes_our_write(clock):
    stored = {"NVDA": T0 + timedelta(minutes=1), "OMH": T0}                    # NOT the `_stamped` order (OMH first)
    lc = _Ordered([_list_doc(["OMH", "NVDA"], stored)])
    flipped = {"OMH": T0, "NVDA": T0 + timedelta(minutes=1)}
    probe = lc.update_one({"_id": C.LIST_DOC_ID, "added": flipped}, {"$set": {"x": 1}})
    assert probe.matched_count == 0                                            # the double IS order-sensitive
    lc.writes = 0
    out = ST.add("AMD", by="owner", db=_db(list_coll=lc))
    assert out["state"] == "added" and lc.writes == 1                          # we filter with the value READ
    assert _stored({C.COLL_LIST: lc})["symbols"] == ["OMH", "NVDA", "AMD"]


def test_NEGATIVE_a_raising_write_on_already_is_already_never_error(clock):
    db = _db(["OMH", "NVDA"], {"OMH": T0})

    def _boom(*a, **k):
        raise RuntimeError("write refused")
    db[C.COLL_LIST].update_one = _boom
    out = ST.add("omh", by="owner", db=db)
    assert out["state"] == "already" and out["state"] != "error" and out["symbols"] == ["OMH", "NVDA"]
    assert _stored(db)["symbols"] == ["OMH", "NVDA"] and _stored(db)["added"] == {"OMH": T0}
    assert ST.add("AMD", by="owner", db=db)["state"] == "error"                # a real add still errors as today


class _AlwaysBumpAdded(FakeColl):
    """Another tab re-stamps OMH right after EVERY read of ours."""

    def __init__(self, docs):
        super().__init__(docs)
        self.n = 0

    def find_one(self, q=None, projection=None):
        d = super().find_one(q, projection)
        self.n += 1
        self.docs[C.LIST_DOC_ID]["added"] = {"OMH": T0 + timedelta(minutes=self.n)}
        return d


def test_NEGATIVE_endless_contention_on_already_is_still_already():
    lc = _AlwaysBumpAdded([_list_doc(["OMH"], {"OMH": T0})])
    out = ST.add("OMH", by="owner", db=_db(list_coll=lc))
    assert out["state"] == "already" and out["symbols"] == ["OMH"] and lc.writes == ST._CAS_TRIES


# ── junk `added` ───────────────────────────────────────────────────────────────────────────────────────────────────
JUNK = ["junk", [], 7, None, {"OMH": float("nan"), "AMD": "2026-11-19T10:00", "NVDA": 5, "XYZQ": None}]


@pytest.mark.parametrize("junk", JUNK)
def test_NEGATIVE_junk_added_is_undated_and_add_remove_board_still_work(clock, board, junk):
    db = _db(["OMH", "AMD", "NVDA"], junk)
    assert CO.added_of(_stored(db)) == {}
    out = PL.build(FRI_IN, db=db)
    assert _syms(out) == ["OMH", "AMD", "NVDA"] and all(r["added_at"] is None for r in out["rows"])
    _strict(json.dumps(out, default=str, allow_nan=True))                       # no NaN reaches the wire
    assert ST.add("AAPL", by="owner", db=db)["state"] == "added"
    assert _stored(db)["added"] == {"AAPL": clock.t}                            # a clean map
    assert ST.remove("OMH", by="owner", db=db)["state"] == "removed"
    assert _stored(db)["added"] == {"AAPL": clock.t}
    assert _stored(db)["symbols"] == ["AMD", "NVDA", "AAPL"]


def test_added_of_unit():
    naive = datetime(2026, 11, 19, 15, 0)
    et = datetime(2026, 11, 19, 10, 0, tzinfo=ET)
    doc = {"added": {"": naive, "   ": naive, 5: naive, "omh": naive, "BRK.B": et, "X": "2026-11-19", "Y": None,
                     "Z": True}}
    assert CO.added_of(doc) == {"OMH": naive.replace(tzinfo=timezone.utc), "BRK-B": et.astimezone(timezone.utc)}
    for bad in (None, "junk", 7, [], {"added": "x"}, {"added": [("OMH", naive)]}):
        assert CO.added_of(bad) == {}


def test_stamp_utc_is_the_auto_rule():
    vals = [datetime(2026, 11, 19, 15, 0), datetime(2026, 11, 19, 10, 0, tzinfo=ET),
            datetime(2026, 11, 19, 15, 0, tzinfo=timezone.utc), "2026-11-19T15:00", None, 5, float("nan"), True]
    for v in vals:
        assert CO.stamp_utc(v) == AUTO._utc(v)
    assert CO.stamp_utc(vals[1]).tzinfo == timezone.utc and CO.stamp_utc(vals[0]).hour == 15


def test_added_iso_and_newest_first_units():
    assert CO.added_iso(datetime(2026, 11, 19, 15, 0, 1, 234567)) == "2026-11-19T15:00:01.234+00:00"
    assert CO.added_iso(datetime(2026, 11, 19, 10, 0, tzinfo=ET)) == "2026-11-19T15:00:00.000+00:00"
    for bad in (None, "2026-11-19", 5, float("nan")):
        assert CO.added_iso(bad) is None
    t = T0
    syms = ["A", "B", "C", "D", "E"]
    added = {"B": t, "D": t, "E": t + timedelta(minutes=1)}
    assert CO.newest_first(syms, added) == ["E", "D", "B", "A", "C"]          # tie → later list position first
    assert CO.newest_first(syms, {}) == syms and CO.newest_first(syms, "junk") == syms
    assert CO.newest_first(["brk.b", "OMH"], {"BRK-B": t}) == ["brk.b", "OMH"]  # keyed by fold


def test_owner_doc_is_the_one_read_strict_raises_soft_is_none():
    class _Raising(FakeColl):
        def find_one(self, q=None, projection=None):
            raise RuntimeError("down")
    assert CO.owner_doc(_db(list_coll=_Raising())) is None
    with pytest.raises(RuntimeError):
        CO.owner_doc(_db(list_coll=_Raising()), strict=True)
    db = _db(["OMH"], {"OMH": T0})
    assert CO.owner_doc(db)["added"] == {"OMH": T0}
    assert CO.owner_symbols(db) == ["OMH"]


# ── the board: rows newest added first ─────────────────────────────────────────────────────────────────────────────
def test_board_rows_newest_first_then_undated_then_auto_in_stored_order(board):
    added = {"OMH": T0, "NVDA": T0 + timedelta(minutes=2), "AMD": T0 + timedelta(minutes=2), "TSLA": T0 + timedelta(1)}
    autos = [_entry("ZZT"), _entry("MMM"), _entry("AAA")]
    db = _db(["OMH", "NVDA", "UND1", "AMD", "TSLA", "UND2"], added, entries=autos)
    out = PL.build(FRI_IN, db=db)
    assert _syms(out) == ["TSLA", "AMD", "NVDA", "OMH", "UND1", "UND2", "ZZT", "MMM", "AAA"]
    assert out["symbols"] == ["OMH", "NVDA", "UND1", "AMD", "TSLA", "UND2"]       # stored order
    assert db[C.COLL_LIST].find_ones.count({"_id": C.LIST_DOC_ID}) == 1        # the owner doc read EXACTLY once
    rows = {r["symbol"]: r for r in out["rows"]}
    for s in ("TSLA", "AMD", "NVDA", "OMH"):
        iso = rows[s]["added_at"]
        assert iso.endswith("+00:00") and datetime.fromisoformat(iso) == added[s]
    assert rows["UND1"]["added_at"] is None and rows["UND2"]["added_at"] is None
    ent = datetime(2026, 11, 13, 15, 5)                                        # _entry's naive (Mongo) time
    assert rows["ZZT"]["added_at"] == ent.replace(tzinfo=timezone.utc).isoformat(timespec="milliseconds")
    poll = PL.build(FRI_IN, db=db, only=["OMH", "AMD", "TSLA", "ZZT"])
    assert _syms(poll) == ["TSLA", "AMD", "OMH", "ZZT"]                         # the pending poll keeps the order


@pytest.mark.parametrize("bad", ["missing", None, "2026-11-13T15:05", 5, float("nan")])
def test_NEGATIVE_an_auto_entry_with_no_or_junk_time_serves_null(board, bad):
    e = _entry("ZZT")
    if bad == "missing":
        e.pop("added_at")
    else:
        e["added_at"] = bad
    out = PL.build(FRI_IN, db=_db(["OMH"], {"OMH": T0}, entries=[e]))
    rows = {r["symbol"]: r for r in out["rows"]}
    assert rows["ZZT"]["auto"] is not None and rows["ZZT"]["added_at"] is None
    _strict(json.dumps(out, default=str))


def test_NEGATIVE_an_auto_name_never_takes_his_time(board):
    out = PL.build(FRI_IN, db=_db(["OMH"], {"OMH": T0, "ZZT": T0 + timedelta(1)}, entries=[_entry("ZZT")]))
    assert _syms(out) == ["OMH", "ZZT"]                                         # 🤖 rows after his, always


# ── pending words ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_pending_rows_serve_the_late_words_and_the_late_poll(board):
    db = _db(["OMH", "NVDA"])
    db[C.COLL_TILES].docs["NVDA"] = {"_id": "NVDA", "symbol": "NVDA", "status": "loaded"}   # loaded, no frames yet
    out = PL.build(FRI_IN, db=db)
    for r in out["rows"]:
        assert r["state"] == "pending" and r["text"] == PL.PENDING_TEXT[True]
        assert r["late_text"] == PL.PENDING_LATE_TEXT[True].format(sym=r["symbol"], sec=GC.GG1M_CADENCE_SEC)
    assert out["pending_late_poll_sec"] == GC.GG1M_CADENCE_SEC
    sun = PL.build(SUN, db=db)
    r = sun["rows"][0]
    assert r["late_text"] == PL.PENDING_LATE_TEXT[False].format(sym=r["symbol"], sec=GC.GG1M_CADENCE_SEC)
    assert r["symbol"] in r["late_text"] and str(GC.GG1M_CADENCE_SEC) in r["late_text"]


def test_NEGATIVE_the_in_window_pending_words_carry_no_time_number():
    t = PL.PENDING_TEXT[True]
    assert not re.search(r"[0-9]", t) and "minute" not in t and "second" not in t and "{" not in t
    for w in PL.PENDING_LATE_TEXT.values():
        assert not re.search(r"[0-9]", re.sub(r"\{[^}]*\}", "", w))             # numbers only through {sec}


def test_NEGATIVE_an_ok_row_has_no_late_words_and_no_late_poll_when_nothing_pends(board):
    db = _db(["OMH", "NVDA"])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH")
    db[C.COLL_TILES].docs["NVDA"] = _doc("NVDA", status="no_prints", frames=False)
    out = PL.build(FRI_IN, db=db)
    rows = {r["symbol"]: r for r in out["rows"]}
    assert rows["OMH"]["state"] == "ok" and rows["OMH"]["late_text"] is None
    assert rows["NVDA"]["state"] == "no_prints" and rows["NVDA"]["late_text"] is None
    assert "pending_late_poll_sec" not in out and "pending_poll_sec" not in out
