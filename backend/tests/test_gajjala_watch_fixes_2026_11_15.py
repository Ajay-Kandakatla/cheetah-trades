"""👀 Gajjala's Watch — review fixes (2026-11-15).

1. An unreadable list (Mongo down / a raising find_one / no database) serves `error` + a served reason on the board —
   never `ok` + [] + "Your watch is empty". The loop / build child keep the fail-soft [].
2. ONE spelling per stock: BRK-B and BRK.B are one name (the house `broker_fold`), stored once as BRK.B, rung once.
3. add / remove are a compare-and-set: two adds at once keep both names; the cap refusal and the order hold.
4. The cross push judges freshness on the clock AFTER the fetch: a host sleep mid-fetch never sends a stale cross.

NEGATIVES throughout: no empty words on a failed read, no second spelling stored, no lost name, no write past the cap,
no late push.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from chart_maps.gajjala import store as GST
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import loop as L
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import store as ST
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_build_2026_11_15 import PREV, S, at, raw_day, stamp

NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def _db(symbols=None, list_coll=None):
    lc = list_coll if list_coll is not None else FakeColl(
        [{"_id": C.LIST_DOC_ID, "symbols": list(symbols)}] if symbols is not None else [])
    return {C.COLL_LIST: lc, C.COLL_TILES: FakeColl(), C.COLL_ALERTS: FakeColl(), C.COLL_STATE: FakeColl()}


def _stored(db):
    d = db[C.COLL_LIST].docs.get(C.LIST_DOC_ID)
    return None if d is None else list(d["symbols"])


class _RaisingFind(FakeColl):
    def find_one(self, q=None, projection=None):
        raise RuntimeError("list read refused")


# ── 1. an unreadable list is an error, never an empty watch ────────────────────────────────────────────────────────
def test_NEGATIVE_a_raising_list_read_is_error_with_a_reason_never_empty_text():
    out = PL.build(NOW, db=_db(list_coll=_RaisingFind()))
    assert out["state"] == "error"
    assert out == PL.error_payload(PL.LIST_UNREADABLE_WHY)
    assert out["reason"] == PL.ERROR_TEXT.format(why=PL.LIST_UNREADABLE_WHY)
    assert "empty_text" not in out and "symbols" not in out and "rows" not in out
    assert PL.empty_text() not in str(out)


def test_NEGATIVE_no_database_is_error_never_empty_text(monkeypatch):
    monkeypatch.setattr(CO, "_db", lambda: None)
    for only in (None, ["OMH"]):
        out = PL.build(NOW, only=only)
        assert out == PL.error_payload(PL.LIST_UNREADABLE_WHY) and "empty_text" not in out


def test_an_empty_list_doc_still_answers_ok_with_the_empty_words():
    for db in (_db(), _db([])):                                 # no doc / an empty list = a real empty watch
        out = PL.build(NOW, db=db)
        assert out["state"] == "ok" and out["symbols"] == [] and out["empty_text"] == PL.empty_text()


def test_strict_reader_raises_soft_reader_stays_empty(monkeypatch):
    db = _db(list_coll=_RaisingFind())
    with pytest.raises(RuntimeError):
        CO.owner_symbols(db, strict=True)
    assert CO.owner_symbols(db) == []                           # loop / cron callers: fail-soft
    monkeypatch.setattr(CO, "_db", lambda: None)
    with pytest.raises(RuntimeError):
        CO.owner_symbols(strict=True)
    assert CO.owner_symbols() == []


def test_strict_reader_a_malformed_doc_is_still_an_empty_list():
    for doc in ({"_id": C.LIST_DOC_ID}, {"_id": C.LIST_DOC_ID, "symbols": "OMH"}):
        assert CO.owner_symbols(_db(list_coll=FakeColl([doc])), strict=True) == []


def test_NEGATIVE_the_loop_keeps_the_soft_reader_and_never_raises():
    out = L.run_iteration(at(S, 10, 1, 30), db=_db(list_coll=_RaisingFind()),
                          deps=L.Deps(load_day=lambda *a, **k: pytest.fail("no fetch on an unreadable list")))
    assert out["reason"] == L.NO_TICKERS and out["ran"] is False


def test_the_error_reason_has_no_typed_digit():
    import re
    assert not re.search(r"[0-9]", PL.LIST_UNREADABLE_WHY)


# ── 2. one spelling per stock ──────────────────────────────────────────────────────────────────────────────────────
def test_fold_is_the_house_broker_fold():
    assert CO.fold("brk.b") == GST.broker_fold("brk.b") == CO.fold("BRK-B")
    assert CO.house("brk-b") == CO.house("BRK.B") == "BRK.B"


@pytest.mark.parametrize("first,second", [("BRK-B", "brk.b"), ("brk.b", "BRK-B"), ("MOG.A", "mog-a")])
def test_NEGATIVE_two_spellings_store_once(first, second):
    db = _db()
    a = ST.add(first, by="owner", db=db)
    b = ST.add(second, by="owner", db=db)
    assert a["state"] == "added" and b["state"] == "already"
    assert _stored(db) == [CO.house(first)] and len(_stored(db)) == 1
    assert "-" not in _stored(db)[0]


@pytest.mark.parametrize("stored,asked", [("BRK-B", "BRK.B"), ("BRK.B", "brk-b"), ("BRK.B", "BRK.B")])
def test_remove_drops_either_spelling(stored, asked):
    db = _db(["OMH", stored, "AMD"])
    out = ST.remove(asked, by="owner", db=db)
    assert out["state"] == "removed" and _stored(db) == ["OMH", "AMD"]


def test_a_legacy_list_with_both_spellings_reads_and_rings_once():
    db = _db(["BRK-B", "OMH", "BRK.B"])
    assert CO.owner_symbols(db) == ["BRK.B", "OMH"]
    out = L.run_iteration(at(S, 10, 1, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert out["n_names"] == 2
    assert PL.build(NOW, db=db)["symbols"] == ["BRK.B", "OMH"]


def test_NEGATIVE_a_ticker_without_a_separator_is_another_name():
    db = _db(["BRK.B"])
    assert ST.add("BRKB", by="owner", db=db)["state"] == "added"
    assert _stored(db) == ["BRK.B", "BRKB"]


# ── 3. compare-and-set: no lost write ──────────────────────────────────────────────────────────────────────────────
class _Racing(FakeColl):
    """Another writer lands right after OUR first read (`other` mutates the stored doc once)."""
    def __init__(self, docs, other):
        super().__init__(docs)
        self.other, self.reads = other, 0

    def find_one(self, q=None, projection=None):
        d = super().find_one(q, projection)
        self.reads += 1
        if self.reads == 1:
            self.other(self.docs)
        return d


def _doc(symbols):
    return [{"_id": C.LIST_DOC_ID, "symbols": list(symbols)}]


def test_two_adds_at_once_keep_both_names_in_order():
    lc = _Racing(_doc(["OMH"]), lambda docs: docs[C.LIST_DOC_ID]["symbols"].append("AMD"))
    db = _db(list_coll=lc)
    out = ST.add("NVDA", by="owner", db=db)
    assert out["state"] == "added" and out["symbols"] == ["OMH", "AMD", "NVDA"]
    assert _stored(db) == ["OMH", "AMD", "NVDA"]                # the other add is NOT lost
    assert lc.reads == 2


def test_NEGATIVE_a_racing_add_that_fills_the_list_is_refused_full():
    names = [f"A{chr(65 + i)}" for i in range(C.MAX_SYMBOLS - 1)]
    lc = _Racing(_doc(names), lambda docs: docs[C.LIST_DOC_ID]["symbols"].append("ZZ"))
    db = _db(list_coll=lc)
    out = ST.add("NVDA", by="owner", db=db)
    assert out["state"] == "full" and "NVDA" not in _stored(db) and len(_stored(db)) == C.MAX_SYMBOLS


def test_NEGATIVE_a_racing_same_name_add_is_already():
    lc = _Racing(_doc(["OMH"]), lambda docs: docs[C.LIST_DOC_ID]["symbols"].append("BRK-B"))
    db = _db(list_coll=lc)
    assert ST.add("brk.b", by="owner", db=db)["state"] == "already"
    assert _stored(db) == ["OMH", "BRK-B"]


def test_a_racing_add_during_a_remove_is_kept():
    lc = _Racing(_doc(["OMH", "NVDA"]), lambda docs: docs[C.LIST_DOC_ID]["symbols"].append("AMD"))
    db = _db(list_coll=lc)
    out = ST.remove("NVDA", by="owner", db=db)
    assert out["state"] == "removed" and _stored(db) == ["OMH", "AMD"]


def test_NEGATIVE_a_racing_remove_of_the_same_name_is_absent():
    lc = _Racing(_doc(["OMH", "NVDA"]), lambda docs: docs[C.LIST_DOC_ID]["symbols"].remove("NVDA"))
    db = _db(list_coll=lc)
    assert ST.remove("NVDA", by="owner", db=db)["state"] == "absent"
    assert _stored(db) == ["OMH"]


class _AlwaysRacing(FakeColl):
    def find_one(self, q=None, projection=None):
        d = super().find_one(q, projection)
        self.docs[C.LIST_DOC_ID]["symbols"].append(f"X{len(self.docs[C.LIST_DOC_ID]['symbols'])}"[:5])
        return d


def test_NEGATIVE_endless_contention_is_error_and_never_writes_a_stale_list():
    lc = _AlwaysRacing(_doc(["OMH"]))
    db = _db(list_coll=lc)
    out = ST.add("NVDA", by="owner", db=db)
    assert out["state"] == "error" and "NVDA" not in _stored(db)
    assert lc.writes == ST._CAS_TRIES                           # every compare-and-set refused, none landed


class _DupOnUpsert(FakeColl):
    """Real Mongo: an upsert whose filter misses an existing _id raises DuplicateKeyError (FakeColl overwrites)."""
    def __init__(self, created):
        super().__init__([])
        self.created, self.reads = created, 0

    def find_one(self, q=None, projection=None):
        d = super().find_one(q, projection)
        self.reads += 1
        if self.reads == 1:                                     # the doc appears right after our (empty) read
            self.docs[C.LIST_DOC_ID] = {"_id": C.LIST_DOC_ID, "symbols": list(self.created)}
        return d

    def update_one(self, q, upd, upsert=False):
        if upsert and "symbols" in self.docs.get(C.LIST_DOC_ID, {}):
            self.writes += 1
            from pymongo.errors import DuplicateKeyError
            raise DuplicateKeyError("dup")
        return super().update_one(q, upd, upsert=upsert)


def test_a_first_add_racing_the_doc_creation_keeps_both():
    lc = _DupOnUpsert(["AMD"])
    db = _db(list_coll=lc)
    out = ST.add("NVDA", by="owner", db=db)
    assert out["state"] == "added" and _stored(db) == ["AMD", "NVDA"]


def test_the_first_add_creates_the_doc():
    db = _db()
    assert ST.add("OMH", by="owner", db=db)["state"] == "added" and _stored(db) == ["OMH"]


def test_the_write_is_conditional_on_the_list_read():
    seen = []

    class _Spy(FakeColl):
        def update_one(self, q, upd, upsert=False):
            seen.append((q, upsert))
            return super().update_one(q, upd, upsert=upsert)
    db = _db(list_coll=_Spy(_doc(["OMH"])))
    ST.add("NVDA", by="owner", db=db)
    assert seen == [({"_id": C.LIST_DOC_ID, "symbols": ["OMH"]}, False)]


# ── 4. freshness on the clock AFTER the fetch ──────────────────────────────────────────────────────────────────────
def _price(ts):
    mm = ts.hour * 60 + ts.minute
    return 14.0 if mm >= 10 * 60 + 5 else 10.0 - 0.002 * (mm - 4 * 60)


class _Clock:
    def __init__(self, t):
        self.t = t.astimezone(timezone.utc)

    def wall(self):
        return self.t


def _ring(jump_sec):
    clock = _Clock(at(S, 10, 6, 30))
    jumped = []

    def load(sym, day, force=False, include_premarket=True, include_afterhours=False):
        if not jumped:                                          # the host sleeps DURING the fetch
            jumped.append(1)
            clock.t += timedelta(seconds=jump_sec)
        return (raw_day(S, end=(10, 7), price=_price, volume=5000.0) if day == S
                else raw_day(PREV, price=lambda ts: 10.0))
    sent = []
    db = _db(["OMH"])
    out = L.run_iteration(at(S, 10, 6, 30), db=db,
                          deps=L.Deps(load_day=load, wall=clock.wall,
                                      send=lambda o, p: (sent.append(p), {"sent": 1, "total_targets": 1})[1],
                                      owner="owner@example.com"))
    return out, sent, db


def test_a_quick_fetch_still_rings():
    out, sent, db = _ring(0)
    assert out["alerts"].get("pushed") == 1 and len(sent) == 1
    assert db[C.COLL_TILES].docs["OMH"]["seen_bar_t"] == stamp(S, 10, 6)


def test_NEGATIVE_a_host_sleep_during_the_fetch_never_sends_the_stale_cross():
    out, sent, db = _ring(10 * 60)
    assert sent == [] and not out["alerts"].get("pushed")
    assert db[C.COLL_TILES].docs["OMH"]["status"] == "loaded"   # the charts still land; only the push is held


def test_NEGATIVE_a_clock_stepped_back_during_the_fetch_is_not_a_younger_now():
    out, sent, _db_ = _ring(-10 * 60)
    assert out["alerts"].get("pushed") == 1 and len(sent) == 1  # clamped at zero elapsed — the planned clock
