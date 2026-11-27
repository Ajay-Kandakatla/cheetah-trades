"""🧮 the second dated float — share_basis I/O (spec floatguard §3.2 + §3.3, work package be-io, 2026-11-26).

Ajay 2026-11-26: "Also the Float share count issue and SI discrepancy happened too many times need to do something
about it". Massive's free float (`/stocks/vX/float`) is stored as `mfloat` on a CHECKED basis doc — read by the nightly
in bulk and by ONE worker step, NEVER inside `refresh_symbol` (which only carries a held one and widens `since2`).

Every outside call is a fake. The float answer is the REAL 11-26 read (`tests/fixtures/massive_float_2026_11_26.json`,
no key); the SMTK refresh fakes are reused from tests/test_si_share_basis_2026_11_24.py (the 11-24 SEC captures).
"""
from __future__ import annotations

import copy
import inspect
import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

import short_interest.share_basis as SB
from short_interest import ssr_corp as SC
from tests import test_si_share_basis_2026_11_24 as T

FIX = json.loads((Path(__file__).resolve().parent / "fixtures" / "massive_float_2026_11_26.json").read_text())
ANSWER = FIX["answer"]
RAW = {r["ticker"]: r for r in ANSWER["results"]}
NOW, NOW_ISO = T.NOW, T.NOW_ISO
FLOAT_URL = SC.BASE_URL + SB.MASSIVE_FLOAT_PATH
FLOAT_FRAG = "api.massive.com" + SB.MASSIVE_FLOAT_PATH


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    """Fresh worker state; no SEC pacing; a fake Massive key; the switch at its built value."""
    monkeypatch.setattr(SB, "_queue", [])
    monkeypatch.setattr(SB, "_inflight", set())
    monkeypatch.setattr(SB, "_bg", {"running": False, "thread": None})
    monkeypatch.setattr(SB, "_sec_last", {"t": None})
    monkeypatch.setattr(SB, "_sec_stop", {"until": None})
    monkeypatch.setattr(SB, "_sec_wait", lambda *a, **k: None)
    monkeypatch.setattr(SC, "_key", lambda: "TESTKEY")
    monkeypatch.setattr(SB, "SB_MFLOAT_WHEN", "on")


# ── fakes
class Coll(T.FakeColl):
    """Honours `{"checked_at": {"$exists": True}}` in find / update_one and never creates a doc without upsert."""

    def __init__(self, docs=()):
        super().__init__(docs)
        self.updates = []

    def find(self, q=None, proj=None):
        q = q or {}
        if "_id" in q:
            return super().find(q, proj)
        self.reads += 1
        if "checked_at" in q:
            return [copy.deepcopy(d) for d in self.docs.values() if "checked_at" in d]
        return [copy.deepcopy(d) for d in self.docs.values()]

    def update_one(self, q, upd, upsert=False):
        self.updates.append((copy.deepcopy(q), copy.deepcopy(upd), upsert))
        doc = self.docs.get(q["_id"])
        if doc is None and not upsert:
            return
        if "checked_at" in q and (doc is None or "checked_at" not in doc):
            return
        self.writes.append(("update", q["_id"]))
        self.docs.setdefault(q["_id"], {"_id": q["_id"]}).update(copy.deepcopy(upd.get("$set") or {}))


def db_with(*docs, records=None):
    return T.FakeDB(short_interest_latest=T.FakeColl(records if records is not None else [T.smtk_record()]),
                    shares_cache=T.FakeColl([{"_id": "SMTK", "float_shares": 546875, "shares_outstanding": 4859369,
                                              "as_of": T.epoch("2026-11-18")}]),
                    si_share_basis=Coll(docs))


def float_http(body=None, code=200):
    return T.FakeHTTP({FLOAT_FRAG: T.Resp(code, ANSWER if body is None else body)})


def checked(sym="SMTK", **over):
    d = {"_id": sym, "v": 1, "checked_at": "2026-11-24T17:00:00Z",
         "splits": {"status": "ok", "since": "2026-08-12", "rows": copy.deepcopy(T.SMTK_SPLITS),
                    "read_at": "2026-11-24T17:00:00Z", "error": None, "error_at": None, "strikes": 0}}
    d.update(over)
    return d


def held_sub(sym="GENI", read_at=NOW_ISO):
    """A stored sub built by the code from a REAL fixture row (GENI's is dated 03-18, before the SMTK window)."""
    r = RAW[sym]
    got = {"status": "ok", "shares": r["free_float"], "pct": r["free_float_percent"], "as_of": r["effective_date"]}
    return SB.mfloat_sub(None, got, read_at)


# ═════════════════════════════════════════════ fetch_mfloats — the real answer → the §3.2 shape
def test_fixture_answer_parses_for_all_16_names_and_jz_is_none():
    http = float_http()
    got = SB.fetch_mfloats(FIX["requested"], http=http)
    assert sorted(got) == FIX["requested"] and len(got) == 16
    assert got["JZ"] == {"status": "none"}
    for sym in FIX["requested"]:
        if sym == "JZ":
            continue
        r = RAW[sym]
        assert got[sym] == {"status": "ok", "shares": r["free_float"], "pct": float(r["free_float_percent"]),
                            "as_of": r["effective_date"]}
    (call,) = http.calls
    assert call["url"] == FLOAT_URL and call["timeout"] == SB.SB_HTTP_TIMEOUT_SEC
    assert call["params"]["limit"] == SB.SB_MFLOAT_CHUNK and call["params"]["apiKey"] == "TESTKEY"
    assert sorted(call["params"]["ticker.any_of"].split(",")) == FIX["requested"]
    assert "TESTKEY" not in call["url"]
    sub = SB.mfloat_sub(None, got["DKI"], NOW_ISO)
    assert sub == {"status": "ok", "shares": RAW["DKI"]["free_float"], "pct": RAW["DKI"]["free_float_percent"],
                   "as_of": "2026-10-20", "read_at": NOW_ISO, "error": None, "error_at": None, "strikes": 0}
    assert SB.mfloat_sub(None, got["JZ"], NOW_ISO) == {"status": "none", "shares": None, "pct": None, "as_of": None,
                                                       "read_at": NOW_ISO, "error": None, "error_at": None,
                                                       "strikes": 0}


def test_one_get_per_chunk_250_names_three_gets():
    names = ["Q%03dX" % i for i in range(250)]
    http = T.FakeHTTP({FLOAT_FRAG: T.Resp(200, {"results": [], "status": "OK"})})
    got = SB.fetch_mfloats(names, http=http)
    assert len(http.calls) == 3
    sizes = [len(c["params"]["ticker.any_of"].split(",")) for c in http.calls]
    assert sizes == [100, 100, 50]
    assert all(c["params"]["limit"] == SB.SB_MFLOAT_CHUNK == 100 for c in http.calls)
    assert all(got[n] == {"status": "none"} for n in names)


def test_class_share_is_spelled_with_a_dot_and_mapped_back():
    body = {"results": [{"ticker": "BRK.B", "free_float": RAW["NCPL"]["free_float"], "free_float_percent": 50.0,
                         "effective_date": "2026-08-14"}]}
    http = float_http(body)
    got = SB.fetch_mfloats(["brk-b"], http=http)
    assert http.calls[0]["params"]["ticker.any_of"] == "BRK.B"
    assert got == {"BRK-B": {"status": "ok", "shares": RAW["NCPL"]["free_float"], "pct": 50.0, "as_of": "2026-08-14"}}


def test_two_rows_for_one_ticker_keep_the_newest_date():
    a, b = dict(RAW["NCPL"]), dict(RAW["NCPL"], effective_date="2026-09-30", free_float=RAW["AKAN"]["free_float"])
    got = SB.fetch_mfloats(["NCPL"], http=float_http({"results": [a, b]}))
    assert got["NCPL"]["as_of"] == "2026-09-30" and got["NCPL"]["shares"] == RAW["AKAN"]["free_float"]


# ═════════════════════════════════════════════ NEGATIVES — fetch_mfloats
def test_NEGATIVE_no_key_no_get(monkeypatch):
    monkeypatch.setattr(SC, "_key", lambda: "")
    http = float_http()
    got = SB.fetch_mfloats(["NCPL", "DKI"], http=http)
    assert http.calls == [] and got == {s: {"status": "failed", "error": SB.ERR_NO_KEY} for s in ("NCPL", "DKI")}


@pytest.mark.parametrize("code", [429, 500, 404])
def test_NEGATIVE_non_200_fails_the_chunk_never_none(code):
    got = SB.fetch_mfloats(["NCPL", "JZ"], http=float_http(code=code))
    assert got == {s: {"status": "failed", "error": "http_%d" % code} for s in ("NCPL", "JZ")}


def test_NEGATIVE_non_json_and_malformed_bodies_fail_never_none():
    got = SB.fetch_mfloats(["JZ"], http=float_http(ValueError("not json")))
    assert got == {"JZ": {"status": "failed", "error": SB.ERR_MALFORMED}}
    for body in ({"results": {"ticker": "JZ"}}, ["x"], {"status": "OK"}, "text"):
        assert SB.fetch_mfloats(["JZ"], http=float_http(body))["JZ"] == {"status": "failed",
                                                                         "error": SB.ERR_MALFORMED}


def test_NEGATIVE_next_url_leaves_unanswered_names_failed_partial():
    body = {"results": [RAW["NCPL"]], "next_url": "https://api.massive.com/stocks/vX/float?cursor=abc"}
    got = SB.fetch_mfloats(["NCPL", "JZ"], http=float_http(body))
    assert got["NCPL"]["status"] == "ok" and got["JZ"] == {"status": "failed", "error": SB.ERR_PARTIAL}


def test_NEGATIVE_a_raising_get_keeps_only_the_type_and_no_key():
    class Boom(Exception):
        pass
    http = T.FakeHTTP({FLOAT_FRAG: Boom("GET https://api.massive.com/stocks/vX/float?apiKey=TESTKEY failed")})
    got = SB.fetch_mfloats(["NCPL"], http=http)
    assert got == {"NCPL": {"status": "failed", "error": "Boom"}}
    assert "TESTKEY" not in json.dumps(got) and "http" not in json.dumps(got)


@pytest.mark.parametrize("ff,ed", [(0, "2026-08-14"), (-5, "2026-08-14"), (True, "2026-08-14"), ("4246497", "2026-08-14"),
                                   (float("nan"), "2026-08-14"), (None, "2026-08-14"), (4246497, "junk"),
                                   (4246497, None), (4246497, "2026-13-45")])
def test_NEGATIVE_junk_free_float_or_date_is_none(ff, ed):
    row = dict(RAW["NCPL"], free_float=ff, effective_date=ed)
    assert SB.fetch_mfloats(["NCPL"], http=float_http({"results": [row]})) == {"NCPL": {"status": "none"}}


@pytest.mark.parametrize("pct", [0, -1, 100.5, True, "54.1", float("nan"), None])
def test_NEGATIVE_junk_percent_is_none_the_count_stands(pct):
    row = dict(RAW["NCPL"], free_float_percent=pct)
    got = SB.fetch_mfloats(["NCPL"], http=float_http({"results": [row]}))["NCPL"]
    assert got["status"] == "ok" and got["pct"] is None and got["shares"] == RAW["NCPL"]["free_float"]


def test_NEGATIVE_under_pytest_with_nothing_injected_no_call(monkeypatch):
    calls = []
    monkeypatch.setattr(SC, "_getter", lambda http: calls.append(1) or (lambda *a, **k: None))
    got = SB.fetch_mfloats(["NCPL"])
    assert got == {"NCPL": {"status": "failed", "error": SB.ERR_TEST}} and calls == []
    assert SB.fetch_mfloats([]) == {} and SB.fetch_mfloats(None) == {}


# ═════════════════════════════════════════════ mfloat_sub — the status rule
def test_failed_try_over_a_held_good_read_keeps_data_and_read_at():
    held = held_sub("NCPL", read_at="2026-11-20T00:00:00Z")
    out = SB.mfloat_sub(held, {"status": "failed", "error": "http_500"}, NOW_ISO)
    assert out == dict(held, error="http_500", error_at=NOW_ISO, strikes=1)
    again = SB.mfloat_sub(out, {"status": "failed", "error": "http_429"}, NOW_ISO)
    assert again["strikes"] == 2 and again["shares"] == held["shares"] and again["read_at"] == held["read_at"]
    none_held = SB.mfloat_sub(None, {"status": "none"}, "2026-11-20T00:00:00Z")
    assert SB.mfloat_sub(none_held, {"status": "failed", "error": "x"}, NOW_ISO)["status"] == "none"


def test_NEGATIVE_failed_with_nothing_good_held_is_failed():
    out = SB.mfloat_sub(None, {"status": "failed", "error": "http_500"}, NOW_ISO)
    assert out == {"status": "failed", "shares": None, "pct": None, "as_of": None, "read_at": None,
                   "error": "http_500", "error_at": NOW_ISO, "strikes": 1}
    junk = {"status": "absent", "shares": 5, "strikes": 3}               # never a good second-float status
    out2 = SB.mfloat_sub(junk, {"status": "failed", "error": "x"}, NOW_ISO)
    assert out2["status"] == "failed" and out2["shares"] is None and out2["strikes"] == 4
    for bad in (None, "x", {"status": "ok", "shares": True, "as_of": "2026-08-14"},
                {"status": "ok", "shares": 5, "as_of": "junk"}):
        assert SB.mfloat_sub(None, bad, NOW_ISO)["status"] == "failed"


# ═════════════════════════════════════════════ store_mfloats
def test_store_mfloats_sets_only_mfloat_on_a_checked_doc():
    before = checked()
    db = db_with(before)
    got = SB.fetch_mfloats(["NCPL"], http=float_http())
    out = SB.store_mfloats(db, {"SMTK": got["NCPL"]}, NOW)
    assert out == {"written": 1, "no_doc": 0, "failed": 0}
    coll = db["si_share_basis"]
    (q, upd, upsert) = coll.updates[0]
    assert q == {"_id": "SMTK", "checked_at": {"$exists": True}} and upsert is False
    assert list(upd) == ["$set"] and list(upd["$set"]) == ["mfloat"]
    after = coll.docs["SMTK"]
    assert {k: v for k, v in after.items() if k != "mfloat"} == before
    assert after["mfloat"] == SB.mfloat_sub(None, got["NCPL"], NOW_ISO)


def test_NEGATIVE_store_never_upserts_state_or_seed_only_docs():
    seed_only = {"_id": "SEED", "float_track": T.TRACK}
    state = {"_id": SB.SB_STATE_SEC_ID, "blocked_until": NOW_ISO, "checked_at": NOW_ISO}
    fts = {"_id": SB.SB_STATE_FTS_ID, "blocked_until": NOW_ISO, "checked_at": NOW_ISO}
    db = db_with(seed_only, state, fts)
    ok = {"status": "ok", "shares": RAW["NCPL"]["free_float"], "pct": 54.1, "as_of": "2026-08-14"}
    out = SB.store_mfloats(db, {"SEED": ok, "MISSING": ok, SB.SB_STATE_SEC_ID: ok, SB.SB_STATE_FTS_ID: ok,
                                "state|fts": ok}, NOW)
    coll = db["si_share_basis"]
    assert out == {"written": 0, "no_doc": 2, "failed": 0}
    assert coll.writes == [] and "MISSING" not in coll.docs
    assert "mfloat" not in coll.docs["SEED"] and "mfloat" not in coll.docs[SB.SB_STATE_SEC_ID]
    assert "mfloat" not in coll.docs[SB.SB_STATE_FTS_ID]
    assert all(u[2] is False for u in coll.updates)
    assert SB.store_mfloats(None, {"SMTK": ok}) == {"written": 0, "no_doc": 0, "failed": 0}


def test_NEGATIVE_a_failing_write_is_counted_never_raised():
    db = db_with(checked())

    def boom(*a, **k):
        raise RuntimeError("mongo down")
    db["si_share_basis"].update_one = boom
    out = SB.store_mfloats(db, {"SMTK": {"status": "none"}}, NOW)
    assert out == {"written": 0, "no_doc": 0, "failed": 1}


# ═════════════════════════════════════════════ checked_symbols
def test_checked_symbols_lists_only_clean_checked_ids():
    db = db_with(checked("SMTK"), checked("NCPL"), {"_id": "SEED", "float_track": T.TRACK},
                 {"_id": SB.SB_STATE_SEC_ID, "checked_at": NOW_ISO}, {"_id": SB.SB_STATE_FTS_ID, "checked_at": NOW_ISO},
                 {"_id": "lower", "checked_at": NOW_ISO}, {"_id": "NULLCHK", "checked_at": None})
    assert SB.checked_symbols(db) == ["NCPL", "SMTK"]


def test_NEGATIVE_checked_symbols_never_raises():
    assert SB.checked_symbols(T.FakeDB(strict=True)) == []

    class Boom:
        def __getitem__(self, k):
            raise RuntimeError("down")
    assert SB.checked_symbols(Boom()) == []


# ═════════════════════════════════════════════ mfloat_step — the worker's per-name read
def test_mfloat_step_stores_on_a_doc_with_none_then_is_fresh_without_a_get():
    db = db_with(checked())
    http = float_http({"results": [dict(RAW["NCPL"], ticker="SMTK")]})
    assert SB.mfloat_step("smtk", db, NOW, http=http) == "stored"
    mf = db["si_share_basis"].docs["SMTK"]["mfloat"]
    assert mf["status"] == "ok" and mf["shares"] == RAW["NCPL"]["free_float"] and mf["read_at"] == NOW_ISO
    http2 = float_http()
    later = NOW + timedelta(days=SB.SB_REF_REFRESH_DAYS) - timedelta(minutes=1)
    assert SB.mfloat_step("SMTK", db, later, http=http2) == "fresh" and http2.calls == []
    http3 = float_http({"results": []})
    assert SB.mfloat_step("SMTK", db, NOW + timedelta(days=SB.SB_REF_REFRESH_DAYS), http=http3) == "stored"
    assert len(http3.calls) == 1 and db["si_share_basis"].docs["SMTK"]["mfloat"]["status"] == "none"


def test_NEGATIVE_mfloat_step_failed_and_held_error_is_not_fresh():
    db = db_with(checked())
    assert SB.mfloat_step("SMTK", db, NOW, http=float_http(code=500)) == "failed"
    assert db["si_share_basis"].docs["SMTK"]["mfloat"]["status"] == "failed"
    held = dict(held_sub("NCPL"), error="http_500", error_at=NOW_ISO, strikes=1)
    assert SB._mfloat_fresh(held, NOW) is False
    assert SB._mfloat_fresh(dict(held_sub("NCPL"), read_at="2026-12-01T00:00:00Z"), NOW) is False   # future
    assert SB._mfloat_fresh({"status": "failed", "read_at": NOW_ISO}, NOW) is False
    assert SB._mfloat_fresh(None, NOW) is False and SB._mfloat_fresh(held_sub("NCPL"), NOW) is True


@pytest.mark.parametrize("word", ["off", "OFF", "yes", None, ""])
def test_NEGATIVE_switch_off_or_unknown_makes_zero_reads_and_zero_gets(monkeypatch, word):
    monkeypatch.setattr(SB, "SB_MFLOAT_WHEN", word)
    db, http = db_with(checked()), float_http()
    assert SB.mfloat_step("SMTK", db, NOW, http=http) == "off"
    assert http.calls == [] and db.total_reads() == 0 and db.total_writes() == 0
    assert SB.mfloat_on() is False and SB.mfloat_on("on") is True and SB.mfloat_on("ON") is False


def test_NEGATIVE_under_pytest_nothing_injected_is_test_before_any_read():
    db = db_with(checked())
    assert SB.mfloat_step("SMTK", db, NOW) == "test" and db.total_reads() == 0


def test_NEGATIVE_mfloat_step_no_doc_and_seed_only_make_no_get():
    http = float_http()
    assert SB.mfloat_step("MISSING", db_with(checked()), NOW, http=http) == "no_doc"
    assert SB.mfloat_step("SEED", db_with({"_id": "SEED", "float_track": T.TRACK}), NOW, http=http) == "no_doc"
    assert SB.mfloat_step(SB.SB_STATE_SEC_ID, db_with(), NOW, http=http) == "no_doc"
    assert SB.mfloat_step("", db_with(), NOW, http=http) == "no_doc"
    assert http.calls == []

    class Boom:
        def __getitem__(self, k):
            raise RuntimeError("down")
    assert SB.mfloat_step("SMTK", Boom(), NOW, http=http) == "failed"


# ═════════════════════════════════════════════ refresh_symbol — carries, widens since2 only, no new call
def _refresh(db, http=None, splits=None, **kw):
    return T.run(db, http if http is not None else T.smtk_http(), splits if splits is not None else T.Splits(), **kw)


def test_refresh_carries_a_held_mfloat_and_widens_only_since2():
    mf = held_sub("GENI")                                          # dated 2026-03-18 < the SMTK window 2026-08-12
    db_a, db_b = T.smtk_db(basis=[checked()]), T.smtk_db(basis=[checked(mfloat=copy.deepcopy(mf))])
    http_a, http_b, sp_a, sp_b = T.smtk_http(), T.smtk_http(), T.Splits(), T.Splits()
    doc_a = _refresh(db_a, http_a, sp_a)
    doc_b = _refresh(db_b, http_b, sp_b)
    assert "mfloat" not in doc_a and doc_b["mfloat"] == mf
    assert set(doc_b) - set(doc_a) == {"mfloat"}
    assert sp_a.calls == [("SMTK", "2026-08-12")] and sp_b.calls == [("SMTK", "2026-03-18")]
    assert doc_a["splits"]["since"] == "2026-08-12" and doc_b["splits"]["since"] == "2026-03-18"
    # PIN MOVED 2026-11-27 (spec sicheck §3.3, K-1): `sec.fts_split`'s window reaches back to the held second float's
    # date (min(sec.since, mfloat.as_of)); every other key of `sec` is unchanged
    nosplit = lambda sec: {k: v for k, v in sec.items() if k != "fts_split"}
    assert nosplit(doc_a["sec"]) == nosplit(doc_b["sec"]) and doc_b["sec"]["since"] == doc_a["sec"]["since"] == "2026-10-15"
    assert doc_a["sec"]["fts_split"]["since"] == "2026-10-15" and doc_b["sec"]["fts_split"]["since"] == "2026-03-18"
    assert [(c["url"], c["params"]) for c in http_a.calls] == [(c["url"], c["params"]) for c in http_b.calls]
    assert http_b.hits(SB.MASSIVE_FLOAT_PATH) == []
    assert db_b["si_share_basis"].docs["SMTK"]["mfloat"] == mf
    assert SB.needs_window(checked(mfloat=mf)) is True and SB.needs_window(doc_b) is False


def test_NEGATIVE_refresh_never_adds_mfloat_and_a_newer_one_does_not_move_since2():
    doc = _refresh(T.smtk_db())
    assert "mfloat" not in doc                                     # the key-set pin (:262) stays exact
    newer = held_sub("SMTK")                                       # dated 2026-11-10, after the window
    sp = T.Splits()
    doc2 = _refresh(T.smtk_db(basis=[checked(mfloat=newer)]), splits=sp)
    assert sp.calls == [("SMTK", "2026-08-12")] and doc2["mfloat"] == newer
    for junk in (dict(held_sub("GENI"), status="failed"), dict(held_sub("GENI"), as_of="junk"),
                 {"status": "none", "shares": None, "pct": None, "as_of": None}):
        sp3 = T.Splits()
        doc3 = _refresh(T.smtk_db(basis=[checked(mfloat=junk)]), splits=sp3)
        assert sp3.calls == [("SMTK", "2026-08-12")] and doc3["mfloat"] == junk


def test_NEGATIVE_refresh_carries_a_held_mfloat_with_the_switch_off(monkeypatch):
    monkeypatch.setattr(SB, "SB_MFLOAT_WHEN", "off")
    mf = held_sub("GENI")
    http = T.smtk_http()
    doc = _refresh(T.smtk_db(basis=[checked(mfloat=mf)]), http)
    assert doc["mfloat"] == mf and http.hits(SB.MASSIVE_FLOAT_PATH) == []
    assert len(http.hits("api.massive.com")) == 1                  # the ticker reference only, as before


def test_NEGATIVE_refresh_source_holds_no_second_float_call():
    src = inspect.getsource(SB.refresh_symbol)
    for name in ("fetch_mfloats(", "mfloat_step(", "store_mfloats(", "widen_splits(", "MASSIVE_FLOAT_PATH"):
        assert name not in src
    assert list(inspect.signature(SB.refresh_symbol).parameters) == [
        "sym", "db", "now", "http", "splits_fetch", "track_fn", "kind_fn", "growth_fn", "store"]


def test_NEGATIVE_is_due_is_the_same_with_and_without_mfloat():
    rec = T.smtk_record()
    base = T._checked()
    for over in ({}, {"checked_at": "2026-11-24T17:00:00Z"}, {"checked_at": "2026-11-24T18:00:00Z"},
                 {"seen": {}}, {"splits": dict(base["splits"], error="x", error_at="2026-11-24T17:00:00Z")}):
        d = dict(base, **over)
        for mf in (held_sub("GENI"), {"status": "failed", "error": "http_500", "error_at": NOW_ISO}):
            assert SB.is_due(dict(d, mfloat=mf), rec, NOW) == SB.is_due(d, rec, NOW)


# ═════════════════════════════════════════════ needs_window + widen_splits
def test_needs_window_cases():
    mf = held_sub("GENI")
    assert SB.needs_window(checked(mfloat=mf)) is True
    assert SB.needs_window(checked(mfloat=mf, splits={"status": "ok", "since": "2026-03-18"})) is False
    assert SB.needs_window(checked(mfloat=mf, splits={"status": "failed", "since": None})) is True
    assert SB.needs_window(checked(mfloat=mf, splits={"since": "junk"})) is True
    assert SB.needs_window({"_id": "X", "mfloat": mf}) is True


def test_NEGATIVE_needs_window_false_without_an_ok_dated_mfloat():
    assert SB.needs_window(checked()) is False
    assert SB.needs_window(checked(mfloat=held_sub("SMTK"))) is False                # newer than the window
    for mf in ({"status": "none"}, {"status": "failed", "as_of": "2026-03-18"}, dict(held_sub("GENI"), as_of="x"),
               "junk", None):
        assert SB.needs_window(checked(mfloat=mf)) is False
    assert SB.needs_window(None) is False and SB.needs_window("x") is False


def test_widen_splits_sets_only_splits_from_the_second_float_date():
    before = checked(mfloat=held_sub("GENI"))
    db, sp = db_with(before), T.Splits()
    out = SB.widen_splits("SMTK", db, NOW, splits_fetch=sp)
    assert out["status"] == "widened" and sp.calls == [("SMTK", "2026-03-18")]
    coll = db["si_share_basis"]
    (q, upd, upsert) = coll.updates[0]
    assert q == {"_id": "SMTK", "checked_at": {"$exists": True}} and upsert is False
    assert list(upd["$set"]) == ["splits"] and out["splits"] == upd["$set"]["splits"]
    assert out["splits"] == {"status": "ok", "since": "2026-03-18", "read_at": NOW_ISO, "error": None,
                             "error_at": None, "strikes": 0,
                             "rows": [{"execution_date": "2026-08-21", "split_from": 50, "split_to": 1},
                                      {"execution_date": "2026-11-23", "split_from": 5, "split_to": 1}]}
    after = coll.docs["SMTK"]
    drop = lambda d: {k: v for k, v in d.items() if k != "splits"}
    assert drop(after) == drop(before) and after["mfloat"] == before["mfloat"]
    assert SB.needs_window(after) is False
    assert SB.widen_splits("SMTK", db, NOW, splits_fetch=T.Splits())["status"] == "not_needed"


def test_widen_shares_step_7_body():
    src = inspect.getsource(SB.refresh_symbol)
    assert "_splits_sub(sym, hsp, since2, now_iso, splits_fetch)" in src and "fetch_splits(" not in src
    assert "_splits_sub(" in inspect.getsource(SB.widen_splits)


def test_NEGATIVE_widen_not_needed_makes_no_call():
    for doc in (checked(), checked(mfloat=held_sub("SMTK")), checked(mfloat={"status": "none"})):
        sp = T.Splits()
        db = db_with(doc)
        assert SB.widen_splits("SMTK", db, NOW, splits_fetch=sp) == {"status": "not_needed", "splits": None}
        assert sp.calls == [] and db.total_writes() == 0


def test_NEGATIVE_widen_failed_read_keeps_held_rows_and_since():
    before = checked(mfloat=held_sub("GENI"))
    db = db_with(before)
    out = SB.widen_splits("SMTK", db, NOW, splits_fetch=T.Splits(exc=RuntimeError("key in text TESTKEY")))
    assert out["status"] == "failed"
    stored = db["si_share_basis"].docs["SMTK"]["splits"]
    assert stored == dict(before["splits"], error="RuntimeError", error_at=NOW_ISO, strikes=1)
    assert "TESTKEY" not in json.dumps(stored)


def test_NEGATIVE_widen_store_false_writes_nothing_and_returns_the_sub():
    db = db_with(checked(mfloat=held_sub("GENI")))
    out = SB.widen_splits("SMTK", db, NOW, splits_fetch=T.Splits(), store=False)
    assert out["status"] == "widened" and out["splits"]["since"] == "2026-03-18"
    assert db.total_writes() == 0 and db["si_share_basis"].updates == []
    assert db["si_share_basis"].docs["SMTK"]["splits"]["since"] == "2026-08-12"


def test_NEGATIVE_widen_no_doc_seed_only_and_test():
    sp = T.Splits()
    assert SB.widen_splits("MISSING", db_with(), NOW, splits_fetch=sp)["status"] == "no_doc"
    seed = {"_id": "SEED", "float_track": T.TRACK, "mfloat": held_sub("GENI")}
    assert SB.widen_splits("SEED", db_with(seed), NOW, splits_fetch=sp)["status"] == "no_doc"
    assert SB.widen_splits(SB.SB_STATE_FTS_ID, db_with(), NOW, splits_fetch=sp)["status"] == "no_doc"
    assert sp.calls == []
    db = db_with(checked(mfloat=held_sub("GENI")))
    assert SB.widen_splits("SMTK", db, NOW) == {"status": "test", "splits": None} and db.total_reads() == 0

    class Boom:
        def __getitem__(self, k):
            raise RuntimeError("down")
    assert SB.widen_splits("SMTK", Boom(), NOW, splits_fetch=sp)["status"] == "failed"


# ═════════════════════════════════════════════ the worker
def _worker_db():
    return T.FakeDB(short_interest_latest=T.FakeColl([T.smtk_record()]), si_share_basis=Coll())


@pytest.mark.parametrize("step,widened", [("stored", True), ("fresh", False), ("failed", False), ("off", False),
                                          ("no_doc", False), ("test", False)])
def test_worker_calls_the_step_after_the_refresh_and_widens_only_on_stored(monkeypatch, step, widened):
    order = []
    monkeypatch.setattr(SB, "refresh_symbol", lambda sym, d: order.append(("refresh", sym)))
    monkeypatch.setattr(SB, "mfloat_step", lambda sym, d: order.append(("step", sym)) or step)
    monkeypatch.setattr(SB, "widen_splits", lambda sym, d: order.append(("widen", sym)))
    SB._queue[:] = ["SMTK"]
    SB._worker(_worker_db())
    want = [("refresh", "SMTK"), ("step", "SMTK")] + ([("widen", "SMTK")] if widened else [])
    assert order == want and SB._queue == [] and SB._inflight == set()


def test_NEGATIVE_worker_under_pytest_makes_no_second_float_call(monkeypatch):
    order = []
    monkeypatch.setattr(SB, "refresh_symbol", lambda sym, d: order.append("refresh"))
    monkeypatch.setattr(SB, "widen_splits", lambda sym, d: order.append("widen"))
    monkeypatch.setattr(SB, "fetch_mfloats", lambda *a, **k: order.append("fetch") or {})
    SB._queue[:] = ["SMTK"]
    SB._worker(_worker_db())
    assert order == ["refresh"]


def test_NEGATIVE_a_raising_step_never_stops_the_worker(monkeypatch):
    seen = []
    monkeypatch.setattr(SB, "refresh_symbol", lambda sym, d: seen.append(sym))

    def boom(sym, d):
        raise RuntimeError("x")
    monkeypatch.setattr(SB, "mfloat_step", boom)
    db = T.FakeDB(short_interest_latest=T.FakeColl([T.smtk_record(), T.smtk_record(_id="ABCD", symbol="ABCD")]),
                  si_share_basis=Coll())
    SB._queue[:] = ["SMTK", "ABCD"]
    SB._worker(db)
    assert seen == ["SMTK", "ABCD"] and SB._bg["running"] is False
    assert "refresh_symbol(sym, db)" in inspect.getsource(SB._worker)


# ═════════════════════════════════════════════ CLI + summary
def test_summary_names_mfloat_only_when_held():
    doc = T.run(T.smtk_db(), store=False)
    assert "mfloat" not in SB._summary("SMTK", doc)
    assert SB._summary("SMTK", dict(doc, mfloat=held_sub("GENI"))).endswith(" | mfloat ok")


def test_cli_mfloat_prints_and_writes_nothing(monkeypatch, capsys):
    def no_db():
        raise AssertionError("the mfloat command needs no database")
    monkeypatch.setattr(SB, "_default_db", no_db)
    monkeypatch.setattr(SB, "fetch_mfloats", lambda syms, **k: {s: {"status": "none"} for s in syms})
    assert SB.main(["mfloat", "--symbols", "ncpl,JZ"]) == 0
    assert json.loads(capsys.readouterr().out) == {"JZ": {"status": "none"}, "NCPL": {"status": "none"}}


# ── the doc's "today the worker step is the ONLY writer, and only for a due name" (be-io refix 2026-11-27)
def _kick_and_run(monkeypatch, basis):
    steps, refreshed = [], []
    monkeypatch.setattr(SB, "refresh_symbol", lambda sym, d: refreshed.append(sym))
    monkeypatch.setattr(SB, "mfloat_step", lambda sym, d: steps.append(sym) or "fresh")
    monkeypatch.setattr(SB, "widen_splits", lambda sym, d: steps.append(("widen", sym)))
    db = T.kick_db(basis=basis)
    out = SB.kick(["FRESH", "A"], db, NOW, spawn=lambda fn: fn())
    return out, steps, refreshed


def test_kick_then_worker_runs_the_step_for_a_due_name(monkeypatch):
    out, steps, refreshed = _kick_and_run(monkeypatch, [dict(T._checked(), _id="FRESH")])
    assert out["queued"] == ["A"] and refreshed == ["A"] and steps == ["A"]


def test_NEGATIVE_a_name_that_is_not_due_never_reaches_the_step(monkeypatch):
    out, steps, refreshed = _kick_and_run(monkeypatch, [dict(T._checked(), _id="FRESH"),
                                                        dict(T._checked(), _id="A")])
    assert out == {"queued": [], "pending": []} and steps == [] and refreshed == []


def test_NEGATIVE_store_mfloats_has_one_caller_in_share_basis_and_it_is_the_step():
    text = Path(SB.__file__).read_text(encoding="utf-8")
    calls = [m.start() for m in re.finditer(r"(?<!def )\bstore_mfloats\(", text)]
    step_src = inspect.getsource(SB.mfloat_step)
    assert len(calls) == 1 and step_src.count("store_mfloats(") == 1
    assert "store_mfloats" not in inspect.getsource(SB.refresh_symbol)
    assert "store_mfloats" not in inspect.getsource(SB._worker)
    assert "store_mfloats" not in inspect.getsource(SB.kick)


# 2026-11-27: be-audit landed — short_interest/source_audit.py calls SB.store_mfloats every night, so the doc names two
# writers and the nightly as built (the earlier pin held the "PLANNED, NOT BUILT" / "ONLY writer" wording).
_MF_DOC = Path(__file__).resolve().parents[2] / "docs" / "short_interest" / "massive_float_source_2026_11_26.md"
_STALE = ("PLANNED, NOT BUILT", "ONLY writer of `mfloat`", "does not exist in this package", "once it ships",
          "until\nthe nightly lands", "Once the planned nightly exists", "not built yet")


def _stale_hits(text):
    body = text.split("## Correction (2026-11-27)")[0]
    return [w for w in _STALE if w in body]


def test_doc_names_two_writers_and_the_nightly_as_built():
    from short_interest import source_audit as SA
    assert "SB.store_mfloats(" in inspect.getsource(SA.audit_night)
    doc = _MF_DOC.read_text(encoding="utf-8")
    assert "Two writers of `mfloat`" in doc and "`mfloat_step`" in doc and "`source_audit.audit_night`" in doc
    assert "package be-audit, BUILT" in doc
    assert _stale_hits(doc) == []
    for line in doc.splitlines():
        if line.startswith("| the nightly `source_audit.audit_night`"):
            assert "BUILT" in line and "store_mfloats" in line and "would" not in line, line
            break
    else:
        raise AssertionError("the nightly row is missing from 'Who reads it'")


def test_NEGATIVE_the_stale_wording_checker_catches_the_old_rows():
    old = ("| PLANNED, NOT BUILT: the nightly `source_audit.audit_night` | 20:15 ET night, once it ships | would call |\n"
           "**Today (2026-11-27) the worker step is the ONLY writer of `mfloat`.**")
    assert set(_stale_hits(old)) == {"PLANNED, NOT BUILT", "ONLY writer of `mfloat`", "once it ships"}
    corrected = "fine\n## Correction (2026-11-27)\nThis page first said \"PLANNED, NOT BUILT\" — ONLY writer of `mfloat`."
    assert _stale_hits(corrected) == []


# ═════════════════════════════════════════════ source guard + fixture hygiene
def test_source_guard_two_hosts_no_contact_no_new_basis_math_import():
    text = Path(SB.__file__).read_text(encoding="utf-8")
    hosts = set(re.findall(r"https?://([^/\"'\s]+)", text))
    assert hosts <= {"data.sec.gov", "api.massive.com"}
    assert "@" not in text and "www.sec.gov" not in text
    assert text.count("from short_interest import basis_math") == 2
    assert SB.MASSIVE_FLOAT_PATH == "/stocks/vX/float" and SB.SB_MFLOAT_WHEN in SB.SB_MFLOAT_MODES
    assert SB.SB_MFLOAT_MODES == ("off", "on")


def test_NEGATIVE_no_exception_text_or_key_in_any_stored_sub():
    class Boom(Exception):
        pass
    db = db_with(checked())
    http = T.FakeHTTP({FLOAT_FRAG: Boom("https://api.massive.com/stocks/vX/float?apiKey=TESTKEY")})
    assert SB.mfloat_step("SMTK", db, NOW, http=http) == "failed"
    stored = json.dumps(db["si_share_basis"].docs["SMTK"])
    assert "TESTKEY" not in stored and "apiKey" not in stored and "https" not in stored
    assert db["si_share_basis"].docs["SMTK"]["mfloat"]["error"] == "Boom"


def test_fixture_is_real_and_holds_no_key():
    raw = (Path(__file__).resolve().parent / "fixtures" / "massive_float_2026_11_26.json").read_text()
    assert "apiKey" not in raw and "TESTKEY" not in raw and "@" not in raw
    assert FIX["http"] == 200 and len(FIX["requested"]) == 16 and "JZ" not in RAW and len(RAW) == 15
    assert ANSWER["status"] == "OK"
