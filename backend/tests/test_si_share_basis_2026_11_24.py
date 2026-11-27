"""🩳 share basis — the I/O engine (spec sidilute §3.1 + §3.2, work package be-basis, 2026-11-24).

Ajay 2026-11-24: "Make sure we are looking for Dilution.." · "Also split related events and filing so we flag them in
the right way". Every outside call here is a fake; `basis_math` is reached only through the `track_fn` / `kind_fn`
seams (fakes below). The SMTK bodies are trimmed copies of the 2026-11-24 data.sec.gov captures (companyconcept dei
EntityCommonStockSharesOutstanding + submissions filings.recent back to 2026-06-12).
"""
from __future__ import annotations

import copy
import io
import json
import re
import threading
from datetime import datetime, timedelta, timezone

import pytest

import short_interest.share_basis as SB
from short_interest import ssr_corp as SC

REAL_SEC_WAIT = SB._sec_wait
NOW = datetime(2026, 11, 24, 18, 5, 11, tzinfo=timezone.utc)
NOW_ISO = "2026-11-24T18:05:11Z"
CIK = "0001817760"

# ── captured SMTK bodies (2026-11-24), trimmed to the fields the engine reads
SMTK_DEI_ROWS = [
    ("2020-06-30", 5000000, "10-K", "2021-02-19"), ("2020-09-30", 5000000, "10-Q", "2020-09-30"),
    ("2020-11-16", 5000000, "10-Q", "2020-11-16"), ("2021-05-14", 25437000, "10-Q", "2021-05-17"),
    ("2021-08-11", 25462000, "10-Q", "2021-08-13"), ("2021-11-11", 25541809, "10-Q", "2021-11-12"),
    ("2021-11-11", 25541809, "10-Q/A", "2022-08-23"), ("2022-03-14", 26566809, "10-K", "2022-03-28"),
    ("2022-03-14", 26566809, "10-K/A", "2022-08-23"), ("2022-05-12", 26566809, "10-Q", "2022-05-13"),
    ("2022-05-12", 26566809, "10-Q/A", "2022-08-23"), ("2022-08-22", 26949282, "10-Q", "2022-08-22"),
    ("2022-11-10", 26949282, "10-Q", "2022-11-14"), ("2023-03-24", 27034996, "10-K", "2023-03-30"),
    ("2023-05-15", 27087773, "10-Q", "2023-05-15"), ("2023-08-14", 30387773, "10-Q", "2023-08-14"),
    ("2023-11-13", 883595, "10-Q", "2023-11-13"), ("2024-03-27", 1355361, "10-K", "2024-03-27"),
    ("2024-05-20", 1438324, "10-Q", "2024-05-20"), ("2024-08-12", 1750472, "10-Q", "2024-08-12"),
    ("2024-11-08", 1780472, "10-Q", "2024-11-08"), ("2025-03-26", 3620217, "10-K", "2025-03-31"),
    ("2025-05-12", 4431165, "10-Q", "2025-05-13"), ("2025-08-11", 4544490, "10-Q", "2025-08-12"),
    ("2025-11-11", 6134963, "10-Q", "2025-11-13"), ("2026-04-01", 21202911, "10-K", "2026-04-08"),
    ("2026-05-18", 21446213, "10-Q", "2026-05-20"), ("2026-08-12", 28263733, "10-Q", "2026-08-14"),
    ("2026-11-11", 4859369, "10-Q", "2026-11-13"),
]
SMTK_RECENT = [
    ("8-K", "2026-11-23", "5.03,9.01", "0001104659-26-130965"), ("4", "2026-11-19", "", "0001213900-26-122253"),
    ("SCHEDULE 13G", "2026-11-19", "", "0001213900-26-122248"), ("3", "2026-11-19", "", "0001213900-26-122247"),
    ("8-K", "2026-11-19", "8.01,9.01", "0001104659-26-129975"), ("10-Q", "2026-11-13", "", "0001104659-26-127038"),
    ("S-4", "2026-11-13", "", "0001104659-26-126378"), ("8-K", "2026-11-04", "1.01,9.01", "0001104659-26-122719"),
    ("8-K", "2026-09-21", "5.02", "0001104659-26-109357"), ("S-3", "2026-09-18", "", "0001104659-26-108966"),
    ("S-1", "2026-09-18", "", "0001104659-26-108965"), ("8-K", "2026-09-14", "3.01", "0001104659-26-107296"),
    ("8-K", "2026-09-04", "5.02", "0001104659-26-105497"), ("8-K", "2026-08-21", "5.03,9.01", "0001104659-26-099673"),
    ("8-K", "2026-08-19", "8.01,9.01", "0001104659-26-098592"), ("10-Q", "2026-08-14", "", "0001104659-26-097087"),
    ("SCHEDULE 13G/A", "2026-08-04", "", "0000921895-26-001958"),
    ("8-K", "2026-08-03", "1.01,7.01,9.01", "0001104659-26-089441"),
    ("8-K", "2026-07-27", "1.01,3.02,8.01,9.01", "0001104659-26-087085"),
    ("SCHEDULE 13G/A", "2026-07-27", "", "0001493152-26-034730"),
    ("8-K", "2026-07-21", "1.01,3.02,9.01", "0001104659-26-085121"), ("424B3", "2026-07-10", "", "0001104659-26-082473"),
    ("EFFECT", "2026-07-09", ",,", "9999999995-26-002246"), ("S-8 POS", "2026-07-07", "", "0001104659-26-081357"),
    ("S-3/A", "2026-07-07", "", "0001104659-26-081338"), ("S-8", "2026-07-02", "", "0001104659-26-080396"),
    ("S-3", "2026-07-02", "", "0001104659-26-080394"), ("8-K", "2026-06-26", "1.01,3.02,9.01", "0001104659-26-078247"),
    ("8-K", "2026-06-26", "5.07", "0001104659-26-077917"), ("8-K", "2026-06-12", "8.01", "0001104659-26-073563"),
]
SMTK_SPLITS = [{"execution_date": "2026-08-21", "split_from": 50.0, "split_to": 1.0},
               {"execution_date": "2026-11-23", "split_from": 5.0, "split_to": 1.0}]


def dei_body(rows=SMTK_DEI_ROWS):
    return {"cik": 1817760, "taxonomy": "dei", "tag": "EntityCommonStockSharesOutstanding",
            "units": {"shares": [{"end": e, "val": v, "form": f, "filed": fd, "accn": "x"} for e, v, f, fd in rows]}}


def sub_body(rows=SMTK_RECENT):
    return {"cik": CIK, "tickers": ["SMTK"], "filings": {"recent": {
        "form": [r[0] for r in rows], "filingDate": [r[1] for r in rows], "items": [r[2] for r in rows],
        "accessionNumber": [r[3] for r in rows]}}}


REF_BODY = {"status": "OK", "results": {"ticker": "SMTK", "cik": CIK, "type": "CS"}}


def smtk_record(**kw):
    rec = {"_id": "SMTK", "symbol": "SMTK", "v": 2, "settlement_date": "2026-10-30", "short_interest": 432313,
           "prev_settlement_date": "2026-10-15", "prev_short_interest": 99473, "days_to_cover": 1.0,
           "float_shares": 546875, "float_asof": "2026-11-02", "shares_outstanding": 1035799,
           "shares_asof": "2026-11-02"}
    rec.update(kw)
    return rec


def epoch(day: str) -> float:
    return datetime.fromisoformat(day + "T12:00:00+00:00").timestamp()


def fake_kind(form, items):
    """A stand-in for basis_math.filing_kind (be-read owns the real one)."""
    base = form.strip().upper()
    base = base[:-2] if base.endswith("/A") else base
    its = [x.strip() for x in (items or "").split(",")]
    if base in ("S-1", "S-3", "S-4", "F-1", "F-3"):
        return "registration"
    if base.startswith("424B"):
        return "prospectus"
    if base == "8-K" and "3.02" in its:
        return "unregistered_sale"
    if base == "8-K" and ("5.03" in its or "3.03" in its):
        return "charter"
    return None


TRACK = {"value": 546875, "since": "2026-11-02", "shares": 1035799, "shares_asof": "2026-11-02",
         "basis_asof": "2026-11-02", "origin": "si_doc", "carried": []}


class TrackSpy:
    def __init__(self, out=TRACK):
        self.calls, self.out = [], out

    def __call__(self, prev, rec, rows):
        self.calls.append((copy.deepcopy(prev), copy.deepcopy(rec), copy.deepcopy(rows)))
        return copy.deepcopy(self.out)


# ── fakes
class Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return copy.deepcopy(self._body)


class FakeHTTP:
    """A requests.get-like callable (NO `.get` attribute, so ssr_corp._getter calls it directly). Routes by URL
    substring; a route value may be a Resp, an exception (raised) or a callable(url) -> Resp."""

    def __init__(self, routes):
        self.routes, self.calls = dict(routes), []

    def __call__(self, url, params=None, headers=None, timeout=None, **kw):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        for frag, ans in self.routes.items():
            if frag in url:
                if isinstance(ans, BaseException):
                    raise ans
                return ans(url) if callable(ans) and not isinstance(ans, Resp) else ans
        raise AssertionError("unexpected URL " + url)

    def hits(self, frag):
        return [c for c in self.calls if frag in c["url"]]


def smtk_http(**over):
    routes = {"api.massive.com/v3/reference/tickers/SMTK": Resp(200, REF_BODY),
              "submissions/CIK" + CIK: Resp(200, sub_body()),
              "companyconcept/CIK" + CIK: Resp(200, dei_body())}
    routes.update(over)
    return FakeHTTP(routes)


class Splits:
    def __init__(self, rows=SMTK_SPLITS, exc=None):
        self.rows, self.exc, self.calls = rows, exc, []

    def __call__(self, sym, since):
        self.calls.append((sym, since))
        if self.exc is not None:
            raise self.exc
        return copy.deepcopy([r for r in self.rows if r["execution_date"] >= since])


class FakeColl:
    def __init__(self, docs=(), fail=False):
        self.docs = {d["_id"]: copy.deepcopy(d) for d in docs}
        self.fail, self.writes, self.reads = fail, [], 0

    def _ids(self, q):
        v = (q or {}).get("_id")
        return list(v["$in"]) if isinstance(v, dict) else [v]

    def find(self, q=None, proj=None):
        self.reads += 1
        if self.fail:
            raise RuntimeError("mongo down")
        return [copy.deepcopy(self.docs[i]) for i in self._ids(q) if i in self.docs]

    def find_one(self, q=None):
        r = self.find(q)
        return r[0] if r else None

    def replace_one(self, q, doc, upsert=False):
        if self.fail:
            raise RuntimeError("mongo down")
        self.writes.append(("replace", q["_id"]))
        self.docs[q["_id"]] = copy.deepcopy(doc)

    def update_one(self, q, upd, upsert=False):
        if self.fail:
            raise RuntimeError("mongo down")
        self.writes.append(("update", q["_id"]))
        d = self.docs.setdefault(q["_id"], {"_id": q["_id"]})
        d.update(copy.deepcopy(upd.get("$set") or {}))


class FakeDB:
    def __init__(self, strict=False, **colls):
        self.colls, self.strict = dict(colls), strict

    def __getitem__(self, name):
        if name not in self.colls:
            if self.strict:
                raise KeyError(name)
            self.colls[name] = FakeColl()
        return self.colls[name]

    def total_writes(self):
        return sum(len(c.writes) for c in self.colls.values())

    def total_reads(self):
        return sum(c.reads for c in self.colls.values())


def smtk_db(basis=(), records=None, shares=None):
    return FakeDB(short_interest_latest=FakeColl(records if records is not None else [smtk_record()]),
                  shares_cache=FakeColl(shares if shares is not None else [
                      {"_id": "SMTK", "float_shares": 546875, "shares_outstanding": 4859369,
                       "as_of": epoch("2026-11-18")}]),
                  si_share_basis=FakeColl(basis))


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    """Fresh module state; no real SEC pacing sleeps; no real outside call; a fake Massive key."""
    monkeypatch.setattr(SB, "_queue", [])
    monkeypatch.setattr(SB, "_inflight", set())
    monkeypatch.setattr(SB, "_bg", {"running": False, "thread": None})
    monkeypatch.setattr(SB, "_sec_last", {"t": None})
    monkeypatch.setattr(SB, "_sec_stop", {"until": None})
    waits = []
    monkeypatch.setattr(SB, "_sec_wait", lambda *a, **k: waits.append(1))

    def _refuse(*a, **k):
        raise RuntimeError("no outside call in this test")
    monkeypatch.setattr(SB, "_http", _refuse)
    monkeypatch.setattr(SC, "_key", lambda: "TESTKEY")
    return waits


def run(db=None, http=None, splits=None, track=None, now=NOW, sym="SMTK", **kw):
    return SB.refresh_symbol(sym, db if db is not None else smtk_db(), now,
                             http=http if http is not None else smtk_http(),
                             splits_fetch=splits if splits is not None else Splits(),
                             track_fn=track if track is not None else TrackSpy(), kind_fn=fake_kind, **kw)


# ═════════════════════════════════════════════ SMTK happy path → the §3.1 doc
def test_smtk_happy_path_builds_the_frozen_doc(_iso):
    db, http, sp, tr = smtk_db(), smtk_http(), Splits(), TrackSpy()
    doc = run(db, http, sp, tr)
    assert set(doc) == {"_id", "v", "checked_at", "seen", "ref", "sec", "splits", "yahoo", "float_track"}
    assert doc["_id"] == "SMTK" and doc["v"] == 1 and doc["checked_at"] == NOW_ISO
    assert doc["seen"] == {"settlement_date": "2026-10-30", "float_shares": 546875, "float_asof": "2026-11-02",
                           "shares_outstanding": 1035799, "shares_asof": "2026-11-02"}
    # 2026-11-26 sishares §3.1 [C16]: the ref also carries the two Massive counts (None — the body gives none)
    assert doc["ref"] == {"status": "ok", "cik": CIK, "type": "CS", "share_class_shares": None,
                          "weighted_shares": None, "read_at": NOW_ISO, "error": None, "error_at": None, "strikes": 0}
    sec = doc["sec"]
    # 2026-11-26 sishares §3.1: + `fts` (SMTK files no 6-K in the window → "none_6k", nothing asked)
    assert set(sec) == {"status", "read_at", "error", "error_at", "strikes", "since", "top_accn", "covers", "filings",
                        "fts"}
    assert sec["fts"]["status"] == "none_6k" and http.hits("efts") == []
    assert sec["status"] == "ok" and sec["read_at"] == NOW_ISO and sec["strikes"] == 0 and sec["error"] is None
    assert sec["since"] == "2026-10-15"                       # [C2] reaches back to prev_settlement_date
    assert sec["top_accn"] == "0001104659-26-127038"          # the 11-13 10-Q
    # 2026-11-26 sitrack A1: each row also carries doc / file / accn / with (the SMTK capture has no primaryDocument
    # or fileNumber arrays → None; `with` = the same-day report — the 8-K is its own, the S-4 sits beside the 10-Q)
    assert sec["filings"] == [{"form": "8-K", "filed": "2026-11-23", "items": "5.03,9.01", "doc": None, "file": None,
                               "accn": "0001104659-26-130965", "with": "8-K"},
                              {"form": "S-4", "filed": "2026-11-13", "items": "", "doc": None, "file": None,
                               "accn": "0001104659-26-126378", "with": "10-Q"}]
    assert len(sec["covers"]) == SB.SB_COVERS_KEPT == 8
    assert [c["as_of"] for c in sec["covers"]][0] == "2025-03-26"
    assert sec["covers"][-2:] == [{"as_of": "2026-08-12", "shares": 28263733, "form": "10-Q", "filed": "2026-08-14"},
                                  {"as_of": "2026-11-11", "shares": 4859369, "form": "10-Q", "filed": "2026-11-13"}]
    sp_doc = doc["splits"]
    assert set(sp_doc) == {"status", "read_at", "error", "error_at", "strikes", "since", "rows"}
    assert sp_doc["status"] == "ok" and sp_doc["since"] == "2026-08-12"   # the cover in force on 11-02 (§3.2 step 6)
    assert sp.calls == [("SMTK", "2026-08-12")]
    assert sp_doc["rows"] == [{"execution_date": "2026-08-21", "split_from": 50, "split_to": 1},
                              {"execution_date": "2026-11-23", "split_from": 5, "split_to": 1}]
    assert doc["yahoo"] == {"float_shares": 546875, "shares_outstanding": 4859369, "as_of": "2026-11-18"}
    assert doc["float_track"] == TRACK
    prev, rec, rows = tr.calls[0]
    assert prev is None and rec["float_shares"] == 546875 and rows == sp_doc["rows"]
    assert db["si_share_basis"].writes == [("replace", "SMTK")]
    assert db["si_share_basis"].docs["SMTK"] == doc


def test_outside_calls_carry_the_generic_headers_and_the_key_only_in_params(_iso):
    http = smtk_http()
    run(http=http)
    sec_calls = [c for c in http.calls if "data.sec.gov" in c["url"]]
    assert len(sec_calls) == 2 and len(_iso) == 2              # each SEC GET went through the ONE pacer
    for c in sec_calls:
        assert c["headers"] == SB.SB_HTTP_HEADERS and c["timeout"] == SB.SB_HTTP_TIMEOUT_SEC
        assert not c["params"]
    (m,) = http.hits("api.massive.com")
    assert m["params"] == {"apiKey": "TESTKEY"} and "TESTKEY" not in m["url"]


def test_since_reaches_back_to_prev_settlement_date(_iso):
    rec = smtk_record(prev_settlement_date="2026-09-30", float_asof="2026-11-02")
    doc = run(smtk_db(records=[rec]))
    assert doc["sec"]["since"] == "2026-09-30"
    # 2026-11-26 sitrack A1: rows carry doc / file / accn / with — compared on the three original fields
    s3 = {"form": "S-3", "filed": "2026-09-18", "items": ""}
    _3 = lambda rows: [{k: r[k] for k in ("form", "filed", "items")} for r in rows]
    assert s3 not in _3(doc["sec"]["filings"])
    rec2 = smtk_record(prev_settlement_date="2026-09-15")
    doc2 = run(smtk_db(records=[rec2]))
    assert doc2["sec"]["since"] == "2026-09-15"
    assert s3 in _3(doc2["sec"]["filings"])


def test_since_includes_the_held_track_since(_iso):
    held = {"_id": "SMTK", "float_track": dict(TRACK, since="2026-09-01")}
    doc = run(smtk_db(basis=[held]))
    assert doc["sec"]["since"] == "2026-09-01"


def test_store_false_writes_nothing(_iso):
    db = smtk_db()
    doc = run(db, store=False)
    assert doc["sec"]["status"] == "ok"
    assert db.total_writes() == 0


def test_no_record_returns_skipped_and_writes_nothing(_iso):
    for recs in ([], [{"_id": "SMTK", "settlement_date": None, "short_interest": 5}],
                 [{"_id": "SMTK", "settlement_date": "2026-10-30", "short_interest": None}]):
        db, http = smtk_db(records=recs), smtk_http()
        assert run(db, http) == {"skipped": "no_record"}
        assert db.total_writes() == 0 and http.calls == []


# ═════════════════════════════════════════════ NEGATIVES — the ticker reference
def test_no_massive_key_ref_failed_and_no_sec_call(_iso, monkeypatch):
    monkeypatch.setattr(SC, "_key", lambda: "")
    http = smtk_http()
    doc = run(http=http, splits=Splits(exc=RuntimeError("no stocks key")))
    assert doc["ref"]["status"] == "failed" and doc["ref"]["error"] == "no_key" and doc["ref"]["strikes"] == 1
    assert http.calls == []                                    # no SEC call, no Massive call
    assert doc["sec"]["status"] == "failed" and doc["sec"]["error"] == SB.ERR_NO_REF
    assert doc["splits"]["status"] == "failed" and doc["splits"]["error"] == "RuntimeError"


def test_massive_404_absent_then_sec_no_cik(_iso):
    http = smtk_http(**{"api.massive.com/v3/reference/tickers/SMTK": Resp(404, {"status": "NOT_FOUND"})})
    doc = run(http=http)
    assert doc["ref"]["status"] == "absent" and doc["ref"]["cik"] is None and doc["ref"]["error"] is None
    assert doc["sec"]["status"] == "no_cik" and doc["sec"]["error"] is None and doc["sec"]["covers"] == []
    assert http.hits("data.sec.gov") == []


def test_ref_ok_without_cik_is_no_cik(_iso):
    http = smtk_http(**{"api.massive.com/v3/reference/tickers/SMTK": Resp(200, {"results": {"type": "ETF"}})})
    doc = run(http=http)
    assert doc["ref"]["status"] == "ok" and doc["ref"]["type"] == "ETF" and doc["ref"]["cik"] is None
    assert doc["sec"]["status"] == "no_cik" and http.hits("data.sec.gov") == []


def test_held_fresh_ref_is_reused_and_an_old_one_refetched(_iso):
    # 2026-11-26 sishares [C16]: a held ref is fresh only WITH the two count keys (a ref without them is re-read —
    # tests/test_si_sec_fts_2026_11_26.py pins that negative)
    held_ref = {"status": "ok", "cik": CIK, "type": "CS", "share_class_shares": None, "weighted_shares": None,
                "read_at": "2026-11-20T00:00:00Z", "error": None, "error_at": None, "strikes": 0}
    http = smtk_http()
    doc = run(smtk_db(basis=[{"_id": "SMTK", "ref": held_ref}]), http)
    assert http.hits("api.massive.com") == [] and doc["ref"] == held_ref
    old = dict(held_ref, read_at="2026-11-10T00:00:00Z")
    http2 = smtk_http()
    doc2 = run(smtk_db(basis=[{"_id": "SMTK", "ref": old}]), http2)
    assert len(http2.hits("api.massive.com")) == 1 and doc2["ref"]["read_at"] == NOW_ISO


def test_ref_failure_over_held_ok_keeps_the_cik(_iso):
    old = {"status": "ok", "cik": CIK, "type": "CS", "read_at": "2026-11-10T00:00:00Z", "error": None,
           "error_at": None, "strikes": 0}
    http = smtk_http(**{"api.massive.com/v3/reference/tickers/SMTK": Resp(500, {})})
    doc = run(smtk_db(basis=[{"_id": "SMTK", "ref": old}]), http)
    assert doc["ref"] == dict(old, error="http_500", error_at=NOW_ISO, strikes=1)
    assert doc["sec"]["status"] == "ok" and len(http.hits("data.sec.gov")) == 2


# ═════════════════════════════════════════════ NEGATIVES — SEC
def test_companyconcept_404_is_none_never_failed(_iso):
    http = smtk_http(**{"companyconcept/CIK" + CIK: Resp(404, {})})
    doc = run(http=http)
    assert doc["sec"]["status"] == "none" and doc["sec"]["error"] is None and doc["sec"]["strikes"] == 0
    assert doc["sec"]["covers"] == [] and len(doc["sec"]["filings"]) == 2


def test_sec_403_blocks_and_the_next_symbol_makes_no_sec_call(_iso):
    http = smtk_http(**{"submissions/CIK" + CIK: Resp(403, "denied")})
    db = smtk_db(records=[smtk_record(), smtk_record(_id="ABCD", symbol="ABCD")])
    doc = run(db, http)
    assert http.hits("companyconcept") == []                   # SEC stopped for this run
    assert doc["sec"]["status"] == "failed" and doc["sec"]["error"] == "http_403"
    state = db["si_share_basis"].docs[SB.SB_STATE_SEC_ID]
    assert state["blocked_until"] == "2026-11-24T18:20:11Z" and state["reason"] == "http_403"
    # the NEXT symbol, a minute later: no SEC call; holding no sec → "blocked"
    SB._sec_stop["until"] = None                               # only the Mongo state doc carries the stop now
    http2 = FakeHTTP({"api.massive.com/v3/reference/tickers/ABCD": Resp(200, REF_BODY)})
    doc2 = run(db, http2, sym="ABCD", now=NOW + timedelta(minutes=1))
    assert http2.hits("data.sec.gov") == []
    assert doc2["sec"]["status"] == "blocked" and doc2["sec"]["read_at"] is None and doc2["sec"]["covers"] == []


def test_sec_block_keeps_a_held_good_sec_untouched(_iso):
    held_sec = {"status": "ok", "read_at": "2026-11-24T10:00:00Z", "error": None, "error_at": None, "strikes": 0,
                "since": "2026-10-15", "top_accn": "a", "covers": [{"as_of": "2026-11-11", "shares": 4859369,
                                                                    "form": "10-Q", "filed": "2026-11-13"}],
                "filings": []}
    db = smtk_db(basis=[{"_id": "SMTK", "sec": held_sec},
                        {"_id": SB.SB_STATE_SEC_ID, "blocked_until": "2026-11-24T18:15:00Z", "reason": "http_429"}])
    http = smtk_http()
    doc = run(db, http)
    assert http.hits("data.sec.gov") == [] and doc["sec"] == held_sec
    # past the stop → SEC is asked again
    http2 = smtk_http()
    run(db, http2, now=datetime(2026, 11, 24, 18, 16, tzinfo=timezone.utc))
    assert len(http2.hits("data.sec.gov")) >= 1


def test_sec_429_on_covers_blocks_too(_iso):
    db = smtk_db()
    doc = run(db, smtk_http(**{"companyconcept/CIK" + CIK: Resp(429, {})}))
    assert doc["sec"]["status"] == "failed" and doc["sec"]["error"] == "http_429"
    assert SB.SB_STATE_SEC_ID in db["si_share_basis"].docs


def test_sec_timeout_over_held_covers_keeps_them_ok(_iso):
    first = run(smtk_db())
    db = smtk_db(basis=[first])

    class ReadTimeout(Exception):
        pass
    later = NOW + timedelta(hours=2)
    doc = run(db, smtk_http(**{"submissions/CIK" + CIK: ReadTimeout("apiKey=SECRET123 timed out")}), now=later)
    sec = doc["sec"]
    assert sec["status"] == "ok" and sec["covers"] == first["sec"]["covers"] and sec["read_at"] == NOW_ISO
    assert sec["error"] == "ReadTimeout" and sec["error_at"] == "2026-11-24T20:05:11Z" and sec["strikes"] == 1
    assert "SECRET123" not in json.dumps(doc)
    # the next good read clears all three
    db2 = smtk_db(basis=[doc])
    doc2 = run(db2, now=later + timedelta(minutes=10))
    assert doc2["sec"]["error"] is None and doc2["sec"]["error_at"] is None and doc2["sec"]["strikes"] == 0
    assert doc2["sec"]["read_at"] == "2026-11-24T20:15:11Z"


def test_sec_failure_with_nothing_held_is_failed(_iso):
    doc = run(http=smtk_http(**{"submissions/CIK" + CIK: Resp(500, {})}))
    assert doc["sec"]["status"] == "failed" and doc["sec"]["read_at"] is None and doc["sec"]["strikes"] == 1
    assert doc["sec"]["covers"] == [] and doc["sec"]["filings"] == []


def test_covers_refetched_only_when_top_accn_changes(_iso):
    first = run(smtk_db())
    http = smtk_http()
    doc = run(smtk_db(basis=[first]), http, now=NOW + timedelta(hours=2))
    assert len(http.hits("submissions")) == 1 and http.hits("companyconcept") == []
    assert doc["sec"]["covers"] == first["sec"]["covers"] and doc["sec"]["read_at"] == "2026-11-24T20:05:11Z"
    moved = dict(first, sec=dict(first["sec"], top_accn="older-accn"))
    http2 = smtk_http()
    run(smtk_db(basis=[moved]), http2)
    assert len(http2.hits("companyconcept")) == 1


def test_fetch_covers_drops_bad_rows_and_dedupes(_iso):
    rows = [("2026-01-01", float("nan"), "10-Q", "2026-01-02"), ("2026-02-01", 0, "10-Q", "2026-02-02"),
            ("2026-03-01", -5, "10-Q", "2026-03-02"), ("2026-04-01", True, "10-Q", "2026-04-02"),
            ("2026-05-01", "abc", "10-Q", "2026-05-02"), ("bad-date", 100, "10-Q", "2026-05-02"),
            ("2026-06-01", float("inf"), "10-Q", "2026-06-02"),
            ("2026-07-01", 1000, "10-Q", "2026-07-02"), ("2026-07-01", 1200, "10-Q/A", "2026-08-01"),
            ("2026-07-01", 900, "10-Q", "2026-07-05")]
    http = FakeHTTP({"companyconcept": Resp(200, dei_body(rows))})
    got = SB.fetch_covers(CIK, http=http)
    assert got == {"status": "ok", "covers": [{"as_of": "2026-07-01", "shares": 1200, "form": "10-Q/A",
                                               "filed": "2026-08-01"}]}
    only_bad = FakeHTTP({"companyconcept": Resp(200, dei_body(rows[:7]))})
    assert SB.fetch_covers(CIK, http=only_bad) == {"status": "none"}
    no_unit = FakeHTTP({"companyconcept": Resp(200, {"units": {"pure": []}})})
    assert SB.fetch_covers(CIK, http=no_unit) == {"status": "none"}
    malformed = FakeHTTP({"companyconcept": Resp(200, ValueError("not json"))})
    assert SB.fetch_covers(CIK, http=malformed) == {"status": "failed", "error": "ValueError", "blocked": False}


def test_fetch_filings_filters_by_since_and_kind_newest_first(_iso):
    got = SB.fetch_filings(CIK, "2026-07-01", http=FakeHTTP({"submissions": Resp(200, sub_body())}), kind_fn=fake_kind)
    assert got["status"] == "ok" and got["top_accn"] == "0001104659-26-127038"
    assert [(f["form"], f["filed"]) for f in got["filings"]] == [
        ("8-K", "2026-11-23"), ("S-4", "2026-11-13"), ("S-3", "2026-09-18"), ("S-1", "2026-09-18"),
        ("8-K", "2026-08-21"), ("8-K", "2026-07-27"), ("8-K", "2026-07-21"), ("424B3", "2026-07-10"),
        ("S-3/A", "2026-07-07"), ("S-3", "2026-07-02")]
    none_kind = SB.fetch_filings(CIK, "2026-01-01", http=FakeHTTP({"submissions": Resp(200, sub_body())}),
                                 kind_fn=lambda f, i: None)
    assert none_kind["filings"] == [] and none_kind["top_accn"] == "0001104659-26-127038"
    bad = SB.fetch_filings(CIK, "2026-01-01", http=FakeHTTP({"submissions": Resp(200, {"filings": {}})}),
                           kind_fn=fake_kind)
    assert bad == {"status": "failed", "error": "malformed", "blocked": False}


def test_fetch_filings_passes_form_and_items_to_kind_fn(_iso):
    seen = []
    SB.fetch_filings(CIK, "2026-11-20", http=FakeHTTP({"submissions": Resp(200, sub_body())}),
                     kind_fn=lambda f, i: seen.append((f, i)))
    assert seen == [("8-K", "5.03,9.01")]


# ═════════════════════════════════════════════ NEGATIVES — splits + the status rule [C1]
def test_splits_raise_over_held_rows_keeps_ok_then_a_good_read_clears(_iso):
    first = run(smtk_db())
    tr = TrackSpy()
    later = NOW + timedelta(hours=2)
    doc = run(smtk_db(basis=[first]), splits=Splits(exc=RuntimeError("splits HTTP 503 apiKey=SECRET123")),
              track=tr, now=later)
    sp = doc["splits"]
    assert sp["status"] == "ok" and sp["rows"] == first["splits"]["rows"] and sp["read_at"] == NOW_ISO
    assert sp["since"] == first["splits"]["since"]
    assert sp["error"] == "RuntimeError" and sp["error_at"] == "2026-11-24T20:05:11Z" and sp["strikes"] == 1
    assert "SECRET123" not in json.dumps(doc) and "503" not in json.dumps(sp)
    assert tr.calls[0][2] == first["splits"]["rows"]           # the HELD rows reach the tracker
    doc2 = run(smtk_db(basis=[doc]), splits=Splits(exc=RuntimeError("x")), now=later + timedelta(minutes=6))
    assert doc2["splits"]["strikes"] == 2 and doc2["splits"]["status"] == "ok"
    doc3 = run(smtk_db(basis=[doc2]), now=later + timedelta(minutes=20))
    assert doc3["splits"]["error"] is None and doc3["splits"]["error_at"] is None and doc3["splits"]["strikes"] == 0
    assert doc3["splits"]["read_at"] == "2026-11-24T20:25:11Z"


def test_splits_raise_with_nothing_held_is_failed_and_the_tracker_gets_none(_iso):
    tr = TrackSpy()
    doc = run(splits=Splits(exc=ValueError("boom apiKey=SECRET123")), track=tr)
    sp = doc["splits"]
    assert sp["status"] == "failed" and sp["rows"] == [] and sp["read_at"] is None
    assert sp["error"] == "ValueError" and sp["strikes"] == 1
    assert tr.calls[0][2] is None
    assert "SECRET123" not in json.dumps(doc)


def test_ref_exception_text_never_stored(_iso):
    doc = run(http=smtk_http(**{"api.massive.com/v3/reference/tickers/SMTK":
                                ConnectionError("https://x?apiKey=SECRET123")}))
    assert doc["ref"]["error"] == "ConnectionError" and "SECRET123" not in json.dumps(doc)


def test_fetch_splits_drops_bad_rows_sorts_and_keeps_future(_iso):
    raw = [{"execution_date": "2026-12-24", "split_from": 10, "split_to": 1},
           {"execution_date": "2026-09-01", "split_from": 2, "split_to": 2},
           {"execution_date": "2026-09-02", "split_from": 0, "split_to": 1},
           {"execution_date": "2026-09-03", "split_from": 5, "split_to": -1},
           {"execution_date": None, "split_from": 5, "split_to": 1},
           {"execution_date": "2026-09-04", "split_from": float("nan"), "split_to": 1},
           {"execution_date": "2026-09-05", "split_from": True, "split_to": 1},
           "junk",
           {"execution_date": "2026-11-09", "split_from": 2.8, "split_to": 1},
           {"execution_date": "2026-10-01", "split_from": 1, "split_to": 2},
           {"execution_date": "2026-10-01", "split_from": 1, "split_to": 2}]
    got = SB.fetch_splits("X", "2026-01-01", fetch=lambda s, d: raw)
    assert got == {"status": "ok", "rows": [
        {"execution_date": "2026-10-01", "split_from": 1, "split_to": 2},
        {"execution_date": "2026-11-09", "split_from": 2.8, "split_to": 1},
        {"execution_date": "2026-12-24", "split_from": 10, "split_to": 1}]}
    assert SB.fetch_splits("X", "2026-01-01", fetch=lambda s, d: {"rows": []}) == {"status": "failed",
                                                                                   "error": "malformed"}


def test_track_failure_keeps_the_held_track(_iso):
    held = {"_id": "SMTK", "float_track": TRACK}

    def boom(*a):
        raise ValueError("x")
    doc = run(smtk_db(basis=[held]), track=boom)
    assert doc["float_track"] == TRACK


def test_yahoo_row_missing_or_junk_is_none(_iso):
    assert run(smtk_db(shares=[]))["yahoo"] is None
    assert run(smtk_db(shares=[{"_id": "SMTK", "float_shares": 0, "shares_outstanding": float("nan")}]))["yahoo"] is None
    y = run(smtk_db(shares=[{"_id": "SMTK", "float_shares": True, "shares_outstanding": 10, "as_of": None}]))["yahoo"]
    assert y == {"float_shares": None, "shares_outstanding": 10, "as_of": None}


# ═════════════════════════════════════════════ is_due [C5][C11]
def _checked(**over):
    base = run(smtk_db(), store=False)
    base.update(over)
    return base


def test_is_due_rules(_iso):
    rec = smtk_record()
    assert SB.is_due(None, None, NOW) is False                                   # no_record is never due
    assert SB.is_due(None, {"settlement_date": None, "short_interest": 1}, NOW) is False
    assert SB.is_due({"checked_at": None}, {"settlement_date": "2026-10-30"}, NOW) is False
    assert SB.is_due(None, rec, NOW) is True                                     # no doc
    assert SB.is_due({"_id": "SMTK", "float_track": TRACK}, rec, NOW) is True    # seed-only
    doc = _checked()
    assert SB.is_due(doc, rec, NOW + timedelta(minutes=59)) is False             # inside SB_REFRESH_MIN
    assert SB.is_due(doc, rec, NOW + timedelta(minutes=SB.SB_REFRESH_MIN)) is True
    assert SB.is_due(doc, smtk_record(float_shares=109375), NOW) is True         # seen differs
    assert SB.is_due(doc, smtk_record(settlement_date="2026-11-13"), NOW) is True


def test_is_due_error_backoff(_iso):
    rec = smtk_record()
    one = _checked()
    one["splits"] = dict(one["splits"], error="RuntimeError", error_at=NOW_ISO, strikes=1)
    assert SB.is_due(one, rec, NOW + timedelta(minutes=4)) is False
    assert SB.is_due(one, rec, NOW + timedelta(minutes=SB.SB_ERROR_RETRY_MIN)) is True
    two = _checked()
    two["sec"] = dict(two["sec"], error="ReadTimeout", error_at=NOW_ISO, strikes=SB.SB_ERROR_STRIKES)
    assert SB.is_due(two, rec, NOW + timedelta(minutes=5)) is False
    assert SB.is_due(two, rec, NOW + timedelta(minutes=59)) is False
    assert SB.is_due(two, rec, NOW + timedelta(minutes=SB.SB_REFRESH_MIN)) is True
    blocked = _checked()
    blocked["sec"] = {"status": "blocked", "read_at": None, "error": None, "error_at": NOW_ISO, "strikes": 0}
    assert SB.is_due(blocked, rec, NOW + timedelta(minutes=4)) is False
    assert SB.is_due(blocked, rec, NOW + timedelta(minutes=5)) is True
    failed = _checked()
    failed["ref"] = {"status": "failed", "cik": None, "type": None, "read_at": None, "error": "no_key",
                     "error_at": NOW_ISO, "strikes": 1}
    assert SB.is_due(failed, rec, NOW + timedelta(minutes=5)) is True


# ═════════════════════════════════════════════ load
def test_load_one_in_find_and_empty_on_failure(_iso):
    coll = FakeColl([{"_id": "SMTK", "v": 1}, {"_id": "JZ", "v": 1}])
    db = FakeDB(si_share_basis=coll)
    assert SB.load(["smtk", "JZ", "NONE", 5, "SMTK"], db) == {"SMTK": {"_id": "SMTK", "v": 1},
                                                             "JZ": {"_id": "JZ", "v": 1}}
    assert coll.reads == 1 and coll.writes == []
    assert SB.load(["SMTK"], FakeDB(si_share_basis=FakeColl(fail=True))) == {}
    assert SB.load(["SMTK"], FakeDB(strict=True)) == {}
    assert SB.load([], db) == {}
    assert SB.load(["SMTK"]) == {}                               # no handle under the test guard


# ═════════════════════════════════════════════ kick [C5]
def kick_db(basis=(), extra=()):
    recs = [smtk_record(_id=s, symbol=s) for s in ("A", "B", "C", "D", "E", "SEED", "HOUR", "FRESH")]
    recs += [{"_id": "NOREC", "settlement_date": None, "short_interest": None}] + list(extra)
    return FakeDB(short_interest_latest=FakeColl(recs), si_share_basis=FakeColl(basis))


def test_kick_under_pytest_without_spawn_starts_and_reads_nothing(_iso):
    db = kick_db()
    assert SB.kick(["A", "B"], db, NOW) == {"queued": [], "pending": []}
    assert db.total_reads() == 0 and SB._queue == [] and SB._bg["running"] is False


def test_kick_queues_only_due_names_and_pending_lists_seed_and_hour_old(_iso):
    fresh = dict(_checked(), _id="FRESH")
    hour = dict(_checked(), _id="HOUR", checked_at="2026-11-24T17:00:00Z")
    seed = {"_id": "SEED", "float_track": TRACK}
    db = kick_db(basis=[fresh, hour, seed])
    started = []
    out = SB.kick(["FRESH", "SEED", "HOUR", "NOREC", "MISSING", "A"], db, NOW, spawn=started.append)
    assert out == {"queued": ["SEED", "HOUR", "A"], "pending": ["SEED", "HOUR", "A"]}
    assert SB._queue == ["SEED", "HOUR", "A"] and len(started) == 1 and SB._bg["running"] is True


def test_kick_newest_request_first_and_reasked_name_moves_to_front(_iso, monkeypatch):
    db = kick_db()
    started = []
    SB.kick(["A", "B"], db, NOW, spawn=started.append)
    out = SB.kick(["C", "D"], db, NOW, spawn=started.append)
    assert SB._queue == ["C", "D", "A", "B"] and len(started) == 1          # one worker only
    assert out == {"queued": ["C", "D"], "pending": ["C", "D"]}
    out2 = SB.kick(["B"], db, NOW, spawn=started.append)
    assert SB._queue == ["B", "C", "D", "A"] and out2 == {"queued": ["B"], "pending": ["B"]}
    order = []
    monkeypatch.setattr(SB, "refresh_symbol", lambda sym, d, *a, **k: order.append(sym))
    started[0]()                                                             # run the worker in this thread
    assert order == ["B", "C", "D", "A"]
    assert SB._queue == [] and SB._inflight == set() and SB._bg["running"] is False


def test_kick_over_queue_max_drops_the_oldest(_iso, monkeypatch):
    monkeypatch.setattr(SB, "SB_QUEUE_MAX", 3)
    db = kick_db()
    SB.kick(["A", "B"], db, NOW, spawn=lambda fn: None)
    out = SB.kick(["C", "D"], db, NOW, spawn=lambda fn: None)
    assert SB._queue == ["C", "D", "A"] and out["pending"] == ["C", "D"]
    out2 = SB.kick(["E", "B"], db, NOW, spawn=lambda fn: None)
    assert SB._queue == ["E", "B", "C"] and out2 == {"queued": ["E", "B"], "pending": ["E", "B"]}


def test_kick_pending_includes_in_flight_and_an_already_queued_not_due_name(_iso):
    fresh = dict(_checked(), _id="FRESH")
    db = kick_db(basis=[fresh])
    SB._inflight.add("A")
    SB._queue[:] = ["FRESH"]
    out = SB.kick(["A", "FRESH", "NOREC"], db, NOW, spawn=lambda fn: None)
    assert out == {"queued": [], "pending": ["A", "FRESH"]}
    assert SB._queue == ["FRESH"]                                            # an in-flight name is not re-queued


def test_kick_never_raises(_iso):
    assert SB.kick(["A"], FakeDB(strict=True), NOW, spawn=lambda fn: None) == {"queued": [], "pending": []}
    no_basis = FakeDB(strict=True, short_interest_latest=FakeColl([smtk_record(_id="A")]))
    out = SB.kick(["A"], no_basis, NOW, spawn=lambda fn: None)
    assert out == {"queued": ["A"], "pending": ["A"]}                        # no basis collection → the name is due

    class Boom:
        def __getitem__(self, k):
            raise RuntimeError("down")
    assert SB.kick(["A"], Boom(), NOW, spawn=lambda fn: None) == {"queued": [], "pending": []}
    assert SB.kick(None, kick_db(), NOW, spawn=lambda fn: None) == {"queued": [], "pending": []}

    def bad_spawn(fn):
        raise RuntimeError("no threads")
    SB._queue.clear()
    SB._bg["running"] = False
    out = SB.kick(["C"], kick_db(), NOW, spawn=bad_spawn)
    assert out["pending"] == ["C"] and SB._bg["running"] is False


def test_kick_real_thread_outside_pytest(_iso, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    done = threading.Event()
    order = []

    def fake_refresh(sym, d, *a, **k):
        order.append((sym, threading.current_thread().name))
        if sym == "B":
            done.set()
    monkeypatch.setattr(SB, "refresh_symbol", fake_refresh)
    out = SB.kick(["A", "B"], kick_db(), NOW)
    assert out["queued"] == ["A", "B"]
    assert done.wait(5)
    SB._bg["thread"].join(5)
    assert order == [("A", SB.SB_THREAD_NAME), ("B", SB.SB_THREAD_NAME)]
    assert SB._bg["running"] is False


# ═════════════════════════════════════════════ the SEC pace [C12]
def test_sec_pace_constant_and_two_gets_never_closer(_iso, monkeypatch):
    assert SB.SB_SEC_MIN_INTERVAL_SEC >= 0.5
    clock = {"t": 1000.0}
    slept = []

    def sleep(s):
        slept.append(s)
        clock["t"] += s
    monkeypatch.setattr(SB, "_sec_wait", lambda: REAL_SEC_WAIT(clock=lambda: clock["t"], sleep=sleep))
    stamps = []

    def stamp(body):
        def f(url):
            stamps.append(clock["t"])
            clock["t"] += 0.01                                  # a fast answer
            return Resp(200, body)
        return f
    http = FakeHTTP({"submissions": stamp(sub_body()), "companyconcept": stamp(dei_body())})
    for _ in range(3):
        SB.fetch_filings(CIK, "2026-10-15", http=http, kind_fn=fake_kind)
        SB.fetch_covers(CIK, http=http)
    assert len(stamps) == 6
    assert all(b - a >= SB.SB_SEC_MIN_INTERVAL_SEC - 1e-9 for a, b in zip(stamps, stamps[1:]))
    assert slept and all(s > 0 for s in slept)


def test_sec_wait_does_not_sleep_after_a_long_gap(_iso):
    clock = {"t": 0.0}
    slept = []
    REAL_SEC_WAIT(clock=lambda: clock["t"], sleep=slept.append)
    clock["t"] = 10.0
    REAL_SEC_WAIT(clock=lambda: clock["t"], sleep=slept.append)
    assert slept == []
    REAL_SEC_WAIT(clock=lambda: clock["t"], sleep=slept.append)
    assert slept == [SB.SB_SEC_MIN_INTERVAL_SEC]


# ═════════════════════════════════════════════ seed
def seed_db(basis=()):
    return FakeDB(short_interest_latest=FakeColl([smtk_record(), smtk_record(_id="CLRO", float_shares=888130)]),
                  si_share_basis=FakeColl(basis))


SEED_ROW = {"float_shares": 546875, "float_asof": "2026-11-02", "shares_outstanding": 1035799,
            "shares_asof": "2026-11-02", "settlement_date": "2026-10-30"}


def test_seed_writes_only_the_track(_iso):
    db = seed_db()
    c = SB.seed({"SMTK": SEED_ROW}, db)
    assert c["written"] == 1
    doc = db["si_share_basis"].docs["SMTK"]
    assert doc == {"_id": "SMTK", "float_track": {"value": 546875, "since": "2026-11-02", "shares": 1035799,
                                                  "shares_asof": "2026-11-02", "basis_asof": "2026-11-02",
                                                  "origin": "seed", "carried": []}}
    assert "checked_at" not in doc
    assert SB.is_due(doc, smtk_record(), NOW) is True                       # seed-only → due


def test_seed_refuses_a_float_that_differs_and_bad_rows(_iso):
    db = seed_db()
    c = SB.seed({"SMTK": dict(SEED_ROW, float_shares=546876), "CLRO": dict(SEED_ROW, float_shares=1),
                 "NOREC": SEED_ROW, "BAD": {"float_shares": "x"}, "BAD2": "junk",
                 "BAD3": dict(SEED_ROW, float_asof="nope")}, db)
    assert c == {"rows": 6, "written": 0, "no_record": 1, "float_differs": 2, "held_kept": 0, "bad_row": 3,
                 "write_failed": 0}
    assert db["si_share_basis"].writes == []


def test_seed_never_overwrites_an_earlier_since(_iso):
    earlier = {"_id": "SMTK", "float_track": dict(TRACK, since="2026-10-01", origin="si_doc")}
    db = seed_db([earlier])
    c = SB.seed({"SMTK": SEED_ROW}, db)
    assert c["held_kept"] == 1 and c["written"] == 0
    assert db["si_share_basis"].docs["SMTK"] == earlier
    same = {"_id": "SMTK", "float_track": dict(TRACK, since="2026-11-02")}
    db2 = seed_db([same])
    assert SB.seed({"SMTK": SEED_ROW}, db2)["held_kept"] == 1               # same since is not LATER
    other = {"_id": "SMTK", "float_track": dict(TRACK, value=109375, since="2026-11-24")}
    db3 = seed_db([other])
    assert SB.seed({"SMTK": SEED_ROW}, db3)["held_kept"] == 1               # a different value is never replaced


def test_seed_replaces_a_later_since_of_the_same_value_keeping_other_fields(_iso):
    later = {"_id": "SMTK", "checked_at": "2026-11-25T00:00:00Z", "v": 1,
             "float_track": dict(TRACK, since="2026-11-18")}
    db = seed_db([later])
    assert SB.seed({"SMTK": SEED_ROW}, db)["written"] == 1
    doc = db["si_share_basis"].docs["SMTK"]
    assert doc["float_track"]["since"] == "2026-11-02" and doc["float_track"]["origin"] == "seed"
    assert doc["checked_at"] == "2026-11-25T00:00:00Z"                       # only float_track was written


def test_cli_seed_file_and_stdin_print_counts_only(_iso, monkeypatch, tmp_path, capsys):
    db = seed_db()
    monkeypatch.setattr(SB, "_default_db", lambda: db)
    p = tmp_path / "seed.json"
    p.write_text(json.dumps({"captured_at": "x", "rows": {"SMTK": SEED_ROW}}))
    assert SB.main(["seed", "--file", str(p)]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)["written"] == 1 and "http" not in out
    db2 = seed_db()
    monkeypatch.setattr(SB, "_default_db", lambda: db2)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"rows": {"CLRO": dict(SEED_ROW, float_shares=888130)}})))
    assert SB.main(["seed", "--stdin"]) == 0
    assert json.loads(capsys.readouterr().out)["written"] == 1
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert SB.main(["seed", "--stdin"]) == 2


def test_cli_refresh_and_show_print_no_url_or_key(_iso, monkeypatch, capsys):
    db = smtk_db()
    monkeypatch.setattr(SB, "_default_db", lambda: db)
    real = SB.refresh_symbol
    monkeypatch.setattr(SB, "refresh_symbol", lambda sym, d: real(sym, d, NOW, http=smtk_http(),
                                                                   splits_fetch=Splits(), track_fn=TrackSpy(),
                                                                   kind_fn=fake_kind))
    assert SB.main(["refresh", "--symbols", "smtk,NOREC"]) == 0
    out = capsys.readouterr().out
    assert "SMTK | ref ok | sec ok, 8 covers, 2 filings | splits ok, 2 rows | track si_doc" in out
    assert "NOREC skipped no_record" in out
    assert "http" not in out and "TESTKEY" not in out
    assert SB.main(["show", "--symbols", "SMTK"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["SMTK"]["sec"]["top_accn"] == "0001104659-26-127038"
    monkeypatch.setattr(SB, "_default_db", lambda: None)
    assert SB.main(["show", "--symbols", "SMTK"]) == 2


# ═════════════════════════════════════════════ source guard
def test_source_guard_hosts_and_headers():
    text = open(SB.__file__, encoding="utf-8").read()
    assert "www.sec.gov" not in text and "@" not in text
    hosts = set(re.findall(r"https?://([^/\"'\s]+)", text))
    assert hosts <= {"data.sec.gov", "api.massive.com"} and "data.sec.gov" in hosts
    assert SC.BASE_URL == "https://api.massive.com"            # the Massive host comes from ssr_corp by name
    h = json.dumps(SB.SB_HTTP_HEADERS).lower()
    for w in ("cheetah", "pounce", "ajay", "@", "gmail"):
        assert w not in h
    assert not re.search(r"^(from short_interest import basis_math|import short_interest\.basis_math|"
                         r"from short_interest\.basis_math)", text, re.M)        # reached only lazily, via the seams
