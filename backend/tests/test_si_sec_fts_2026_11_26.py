"""🩳 6-K issuance reader (SEC full-text search) + the Massive share counts (2026-11-26, spec sishares §3.1 + §3.3,
work package be-io).

Ajay 2026-11-26: "Fix the POM chip and the 6-K dilution check. Also find alternative srouces for this share count".

The efts answers are the three saved 2026-11-26 GETs (tests/fixtures/sec_fts_pom_2026_11_26.json), the POM listing
is its real `filings.recent` (sec_submissions_pom_2026_11_26.json), the filing texts are the nine POM 6-Ks and five
NCPL 8-Ks, tags stripped (sec_6k_text_pom_2026_11_26.json). Hermetic: every outside call is a fake; the session
refuser of tests/conftest.py stays on `share_basis._http`. NEGATIVES marked NEGATIVE.
"""
from __future__ import annotations

import copy
import json
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import short_interest.sec_fts as SF
import short_interest.share_basis as SB
from short_interest import ssr_corp as SC

FIX = Path(__file__).resolve().parent / "fixtures"
FTS = json.loads((FIX / "sec_fts_pom_2026_11_26.json").read_text())["answers"]
TXT = json.loads((FIX / "sec_6k_text_pom_2026_11_26.json").read_text())
SUB = json.loads((FIX / "sec_submissions_pom_2026_11_26.json").read_text())
CIK = "0001877971"
ACCN = "0001213900-26-116021"                      # the 11-04 debt-conversion 6-K
DOC = "ea0310863-6k_pomdoctor.htm"
TOP = "0001213900-26-116902"                       # the newest 6-K of the window (11-06)
NOW = datetime(2026, 11, 26, 21, 40, tzinfo=timezone.utc)
NOW_ISO = "2026-11-26T21:40:00Z"
TODAY = "2026-11-26"
GROWTH = {"from_shares": 2576092, "to_shares": 35761933, "to_asof": "2026-11-25"}
N = 33185841


# ═════════════════════════════════════════════ fakes
class Resp:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return copy.deepcopy(self._body)


class HTTP:
    """requests.get-like; routes by host; efts by the query kind (phrase / number)."""

    def __init__(self, sub=None, phrase=None, number=None, ref=None, efts_code=None, number_code=None):
        self.sub = sub if sub is not None else copy.deepcopy(SUB)
        self.phrase = phrase if phrase is not None else FTS["phrase"]
        self.number = number if number is not None else FTS["number"]
        self.ref = ref if ref is not None else {"results": {"ticker": "POM", "cik": CIK, "type": "CS",
                                                            "share_class_shares_outstanding": None,
                                                            "weighted_shares_outstanding": 35966137}}
        self.efts_code, self.number_code = efts_code, number_code
        self.calls = []

    def __call__(self, url, params=None, headers=None, timeout=None, **kw):
        u = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(u.query))
        self.calls.append({"host": u.netloc, "path": u.path, "q": q, "headers": headers, "params": params})
        if u.netloc == "api.massive.com":
            return Resp(200, self.ref)
        if u.netloc == "data.sec.gov":
            if "/submissions/" in u.path:
                return Resp(200, self.sub)
            return Resp(404, {})                                # POM: no dei cover fact (dual class)
        if u.netloc == "efts.sec.gov":
            is_num = q.get("q", "").startswith('"') and q["q"].strip('"').replace(",", "").isdigit()
            code = self.number_code if is_num else self.efts_code
            if code is not None:
                return Resp(code, {"error": "x"})
            return Resp(200, self.number if is_num else self.phrase)
        raise AssertionError("unexpected host " + u.netloc)

    def efts(self, kind=None):
        out = [c for c in self.calls if c["host"] == "efts.sec.gov"]
        if kind == "number":
            return [c for c in out if c["q"]["q"].strip('"').replace(",", "").isdigit()]
        if kind == "phrase":
            return [c for c in out if not c["q"]["q"].strip('"').replace(",", "").isdigit()]
        return out

    def hosts(self):
        return {c["host"] for c in self.calls}


class Coll:
    def __init__(self, docs=()):
        self.docs = {d["_id"]: copy.deepcopy(d) for d in docs}
        self.writes = []

    def find(self, q=None, proj=None):
        v = (q or {}).get("_id")
        if v is None:
            return [copy.deepcopy(d) for d in self.docs.values()]
        ids = v["$in"] if isinstance(v, dict) else [v]
        return [copy.deepcopy(self.docs[i]) for i in ids if i in self.docs]

    def replace_one(self, q, doc, upsert=False):
        self.writes.append(q["_id"])
        self.docs[q["_id"]] = copy.deepcopy(doc)

    def update_one(self, q, upd, upsert=False):
        self.writes.append(q["_id"])
        self.docs.setdefault(q["_id"], {"_id": q["_id"]}).update(copy.deepcopy(upd.get("$set") or {}))


class DB:
    def __init__(self, **colls):
        self.colls = dict(colls)

    def __getitem__(self, k):
        return self.colls.setdefault(k, Coll())

    def writes(self):
        return sum(len(c.writes) for c in self.colls.values())


def pom_record(**kw):
    rec = {"_id": "POM", "symbol": "POM", "v": 2, "settlement_date": "2026-11-13", "short_interest": 77883,
           "prev_settlement_date": "2026-10-30", "prev_short_interest": 250448, "days_to_cover": 1.0,
           "float_shares": 1119065, "float_asof": "2026-11-09", "shares_outstanding": 2576092,
           "shares_asof": "2026-11-09"}
    rec.update(kw)
    return rec


def pom_db(basis=(), rec=None):
    return DB(short_interest_latest=Coll([rec or pom_record()]),
              shares_cache=Coll([{"_id": "POM", "float_shares": 1545214, "shares_outstanding": 35761933,
                                  "as_of": datetime(2026, 11, 25, 17, tzinfo=timezone.utc).timestamp()}]),
              si_share_basis=Coll(basis))


TRACK = {"value": 1119065, "since": "2026-11-09", "shares": 2576092, "shares_asof": "2026-11-09",
         "basis_asof": "2026-11-09", "origin": "si_doc", "carried": []}


class Growth:
    def __init__(self, out=GROWTH, exc=None):
        self.out, self.exc, self.calls = out, exc, 0

    def __call__(self, rec, doc, today):
        self.calls += 1
        if self.exc:
            raise self.exc
        return copy.deepcopy(self.out)


def kind(form, items):
    b = form.strip().upper()
    return "registration" if b.startswith(("F-1", "F-3", "S-1", "S-3")) else (
        "prospectus" if b.startswith("424B") else None)


def run(db=None, http=None, now=NOW, growth=None, sym="POM", **kw):
    return SB.refresh_symbol(sym, db if db is not None else pom_db(), now, http=http if http is not None else HTTP(),
                             splits_fetch=lambda s, since: [], track_fn=lambda prev, rec, rows: dict(TRACK),
                             kind_fn=kind, growth_fn=growth if growth is not None else Growth(), **kw)


def pom_reports(since="2026-10-30"):
    got = SB.fetch_filings(CIK, since, http=HTTP(), kind_fn=lambda f, i: None)
    assert got["status"] == "ok"
    return got["reports"]


def body_with(hits, total=None):
    b = copy.deepcopy(FTS["phrase"])
    b["hits"]["hits"] = hits
    b["hits"]["total"]["value"] = len(hits) if total is None else total
    return b


def sub_plus(form, filed, accn, doc="x-6k.htm"):
    """The POM listing with one more filing on top (the newest)."""
    s = copy.deepcopy(SUB)
    new = {"form": form, "filingDate": filed, "accessionNumber": accn, "primaryDocument": doc, "items": ""}
    for k, v in s["filings"]["recent"].items():
        v.insert(0, new.get(k, ""))
    return s


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    """Fresh stops; the pacer counted, never slept; a fake Massive key. The conftest refuser stays on `_http`."""
    monkeypatch.setattr(SB, "_sec_stop", {"until": None})
    monkeypatch.setattr(SB, "_fts_stop", {"until": None})
    waits = []
    monkeypatch.setattr(SB, "_sec_wait", lambda *a, **k: waits.append(1))
    monkeypatch.setattr(SC, "_key", lambda: "TESTKEY")
    monkeypatch.setattr(SF, "FTS_WHEN", "on")
    return waits


# ═════════════════════════════════════════════ the literals (one per side; the be-verdict side pins its own)
def test_literals_and_modes():
    assert SF.FTS_ISSUANCE == "issuance" and SF.FTS_GOOD == ("ok", "none_6k")
    assert SB.SB_REPORT_FORMS[1] == "6-K" == SF.FTS_FORMS[0]
    assert SF.FTS_WHEN in SF.FTS_MODES == ("off", "on")
    assert SB.SB_STATE_FTS_ID == "state|fts" and len(SF.FTS_ISSUANCE_PHRASES) == 9
    assert urllib.parse.urlsplit(SF.FTS_URL).netloc == "efts.sec.gov"


def test_NEGATIVE_only_the_word_on_turns_the_reader_on(monkeypatch):
    assert SF.fts_on("on") is True and SF.fts_on("off") is False
    for junk in ("On", "yes", "", True, 1):
        assert SF.fts_on(junk) is False
    assert SF.fts_on() is True                                  # no argument = the module constant ("on" here)
    monkeypatch.setattr(SF, "FTS_WHEN", "maybe")
    assert SF.fts_on() is False


# ═════════════════════════════════════════════ the saved answers
def test_phrase_answer_is_one_issuance_row():
    p = SF.parse_hits(FTS["phrase"])
    assert p["total"] == 2 and [r["accn"] for r in p["rows"]] == [ACCN, ACCN]
    rows = SF.by_accession(p["rows"], pom_reports())
    assert len(rows) == 1
    (r,) = rows
    assert r["form"] == "6-K" and r["filed"] == "2026-11-04" and r["accn"] == ACCN and r["doc"] == DOC
    (ex,) = r["ex"]
    assert ex["type"] == "EX-10.1" and ex["desc"].startswith("DEBT CONVERSION AGREEMENT")
    assert len(ex["desc"]) == SF.FTS_DESC_MAX


def test_number_answer_is_one_hit():
    calls = []

    def get(url):
        calls.append(url)
        return Resp(200, FTS["number"])
    got = SF.read_number(CIK, N, "2026-10-30", TODAY, pom_reports(), get=get)
    assert got == {"status": "ok", "hits": [{"accn": ACCN, "filed": "2026-11-04", "form": "6-K", "doc": DOC}]}
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(calls[0]).query))
    assert q == {"q": '"33,185,841"', "forms": "6-K", "ciks": CIK, "dateRange": "custom", "startdt": "2026-10-30",
                 "enddt": TODAY}


def test_a_broad_answer_groups_by_accession_newest_first():
    rows = SF.by_accession(SF.parse_hits(FTS["ordinary_shares"])["rows"], pom_reports("2026-10-01"))
    assert [(r["filed"], r["accn"]) for r in rows] == [
        ("2026-11-06", TOP), ("2026-11-04", ACCN), ("2026-11-02", "0001213900-26-114970"),
        ("2026-10-19", "0001213900-26-110501"), ("2026-10-02", "0001213900-26-106373")]
    by = {r["accn"]: r for r in rows}
    assert [e["type"] for e in by[ACCN]["ex"]] == ["EX-10.1"] and by[ACCN]["doc"] == DOC
    assert by["0001213900-26-106373"]["ex"] == []


def test_NEGATIVE_parse_hits_refuses_a_junk_answer():
    for junk in (None, [], "x", {}, {"hits": []}, {"hits": {}}, {"hits": {"total": {"value": True}, "hits": []}},
                 {"hits": {"total": {"value": 1}, "hits": {}}}, {"hits": {"total": {"value": -1}, "hits": []}},
                 {"hits": {"total": "2", "hits": []}}):
        with pytest.raises(ValueError):
            SF.parse_hits(junk)
    ok = {"hits": {"total": 3, "hits": [
        "junk", {"_id": "nope:x.htm", "_source": {"file_date": "2026-11-04"}},
        {"_id": ACCN + ":a.htm", "_source": {"file_date": "11/04/2026"}},
        {"_id": ACCN + ":../a.htm", "_source": {"file_date": "2026-11-04", "form": "6-K"}}]}}
    p = SF.parse_hits(ok)
    assert p["total"] == 3 and len(p["rows"]) == 1 and p["rows"][0]["file"] is None      # a path is never a file


def test_NEGATIVE_a_hit_that_is_not_a_6k_of_the_listing_is_dropped():
    rows = SF.parse_hits(FTS["phrase"])["rows"]
    stray = dict(rows[0], accn="0009999999-26-000001")
    assert SF.by_accession(rows + [stray], pom_reports()) == SF.by_accession(rows, pom_reports())
    as_8k = [dict(r, form="8-K") for r in pom_reports()]
    assert SF.by_accession(rows, as_8k) == []
    assert SF.by_accession(rows, []) == [] and SF.by_accession(rows, None) == []
    assert SF.by_accession(None, pom_reports()) == []


def test_queries():
    q = SF.phrase_query(SF.FTS_ISSUANCE_PHRASES)
    assert q.split(" OR ") == ['"%s"' % p for p in SF.FTS_ISSUANCE_PHRASES]
    assert SF.number_query(N) == '"33,185,841"'
    assert SF.phrase_query(['a "b"', " ", None, "c"]) == '"c"'          # NEGATIVE a quote / blank / junk is dropped


# ═════════════════════════════════════════════ phrase precision on the saved texts
TEXTS = {t["accn"]: t for t in TXT["texts"]}


def test_phrases_hit_only_the_issuance_filings():
    hit = {a for a, t in TEXTS.items() if SF.text_matches(t["text"], SF.FTS_ISSUANCE_PHRASES)}
    assert hit == {ACCN, "0001493152-26-047783"}                    # POM 11-04 6-K · NCPL 10-20 8-K (Item 3.02)
    assert sum(1 for t in TEXTS.values() if t["form"] == "6-K") == 9
    assert sum(1 for t in TEXTS.values() if t["form"].startswith("8-K")) == 5
    assert "33,185,841" in TEXTS[ACCN]["text"]


@pytest.mark.parametrize("accn,cue", [
    ("0001213900-26-110501", "share consolidation"),          # 10-19 consolidation / ADS exchange
    ("0001213900-26-110501", "ads"),
    ("0001213900-26-108499", "issued the delisting determination"),   # 10-09 Nasdaq letter
    ("0001213900-26-108499", "1-for-18 reverse stock split"),
    ("0001213900-26-114970", "nasdaq"),                       # 11-02
    ("0001213900-26-116902", "issued a press release"),       # 11-06
    ("0001213900-26-106373", "were issued and outstanding"),  # 10-02 meeting results
    ("0001213900-26-102849", None),                           # 09-24
    ("0001213900-26-104915", None),                           # 09-30
    ("0001213900-26-104640", None),                           # 09-29 interim report (cut; checked on the full text)
])
def test_NEGATIVE_the_other_pom_6ks_match_no_phrase(accn, cue):
    t = TEXTS[accn]["text"]
    if cue:
        assert cue in t.lower()                                # the near-miss words are really there
    assert SF.text_matches(t, SF.FTS_ISSUANCE_PHRASES) == []


def test_the_long_interim_report_is_cut_and_said():
    t = TEXTS["0001213900-26-104640"]
    assert t["cut_to_first"] == 6000 and len(t["text"]) == 6000
    assert all(x["cut_to_first"] is None for a, x in TEXTS.items() if a != "0001213900-26-104640")


def test_NEGATIVE_text_matches_on_word_edges_and_junk():
    assert SF.text_matches("They disagreed to issue nothing", ["agreed to issue"]) == []
    assert SF.text_matches("we  AGREED\nto   issue shares", ["agreed to issue"]) == ["agreed to issue"]
    assert SF.text_matches(None, ["x"]) == [] and SF.text_matches("x", [None, " "]) == []


# ═════════════════════════════════════════════ holds [C8]
def test_holds_a_no_hit_until_two_days_after_the_filing():
    f = "2026-11-24"
    assert SF.holds(f, "2026-11-24T20:00:00Z", False) is False          # the filing day
    assert SF.holds(f, "2026-11-25T20:00:00Z", False) is False          # the day after
    assert SF.holds(f, "2026-11-26T15:00:00Z", False) is True           # two days after
    assert SF.holds(f, "2026-11-24T20:00:00Z", True) is True            # a HIT is held from the first read
    # the read date is EASTERN: 11-26 03:00Z is still 11-25 in New York → the day after → asked again
    assert SF.holds(f, "2026-11-26T03:00:00Z", False) is False


def test_NEGATIVE_holds_junk_is_never_held():
    for top, at, hit in ((None, NOW_ISO, True), ("x", NOW_ISO, True), ("2026-11-24", None, True),
                         ("2026-11-24", "junk", True), ("2026-02-30", NOW_ISO, False), (5, NOW_ISO, True)):
        assert SF.holds(top, at, hit) is False
    assert SF.holds("2026-11-01", NOW_ISO, "yes") is True               # a no-hit read long after → held anyway
    assert SF.holds("2026-11-25", NOW_ISO, "yes") is False              # "yes" is not a hit


# ═════════════════════════════════════════════ the worker step — POM end to end
def test_pom_pass_reads_both_queries_and_marks_the_6k(_iso):
    db, http, g = pom_db(), HTTP(), Growth()
    doc = run(db, http, growth=g)
    sec = doc["sec"]
    assert sec["status"] == "none" and sec["since"] == "2026-10-30"     # no dei cover fact; filings still read
    fts = sec["fts"]
    assert fts["status"] == "ok" and fts["since"] == "2026-10-30" and fts["read_at"] == NOW_ISO
    assert fts["top_6k"] == TOP and fts["top_6k_filed"] == "2026-11-06" and fts["error"] is None
    assert "cap" not in fts
    assert [(r["accn"], r["filed"], r["doc"]) for r in fts["issuance"]] == [(ACCN, "2026-11-04", DOC)]
    assert fts["number"] == {"n": N, "from": 2576092, "to": 35761933, "read_at": NOW_ISO,
                             "hits": [{"accn": ACCN, "filed": "2026-11-04", "form": "6-K", "doc": DOC}]}
    marked = [f for f in sec["filings"] if f.get("fts")]
    assert marked == [{"form": "6-K", "filed": "2026-11-04", "items": "", "doc": DOC, "file": None, "accn": ACCN,
                       "with": None, "fts": "issuance"}]
    assert not any(f["form"] == "6-K" and not f.get("fts") for f in sec["filings"])    # an unmarked 6-K is never kept
    assert [f["filed"] for f in sec["filings"]] == sorted((f["filed"] for f in sec["filings"]), reverse=True)
    assert doc["ref"]["weighted_shares"] == 35966137 and doc["ref"]["share_class_shares"] is None
    assert g.calls == 1 and len(http.efts("phrase")) == 1 and len(http.efts("number")) == 1
    (p,) = http.efts("phrase")
    assert p["q"]["forms"] == "6-K" and p["q"]["ciks"] == CIK and p["q"]["startdt"] == "2026-10-30"
    assert p["q"]["enddt"] == TODAY and p["q"]["dateRange"] == "custom"
    assert db["si_share_basis"].docs["POM"] == doc


def test_every_efts_call_goes_through_the_pacer_with_the_generic_headers(_iso):
    http = HTTP()
    run(http=http)
    sec_like = [c for c in http.calls if c["host"] in ("data.sec.gov", "efts.sec.gov")]
    assert len(http.efts()) == 2 and len(_iso) == len(sec_like)          # every SEC / efts GET paced
    for c in http.efts():
        assert c["headers"] == SB.SB_HTTP_HEADERS and not c["params"]
    assert "@" not in json.dumps(SB.SB_HTTP_HEADERS)
    assert http.hosts() == {"api.massive.com", "data.sec.gov", "efts.sec.gov"}


def test_NEGATIVE_under_pytest_the_refused_seam_blocks_efts_too():
    with pytest.raises(RuntimeError, match="disabled during tests"):
        SB._sec_get(SF.url_of('"x"', CIK, "2026-10-30", TODAY), None)
    got = SF.read_issuance(CIK, "2026-10-30", TODAY, pom_reports(), get=SB._fts_get(None))
    assert got == {"status": "failed", "error": "RuntimeError", "code": None}


def test_no_6k_in_the_window_asks_nothing(_iso):
    sub = copy.deepcopy(SUB)
    r = sub["filings"]["recent"]
    r["form"] = ["8-K" if f.startswith("6-K") else f for f in r["form"]]
    http, g = HTTP(sub=sub), Growth()
    doc = run(http=http, growth=g)
    fts = doc["sec"]["fts"]
    assert fts["status"] == "none_6k" and fts["issuance"] == [] and fts["number"] is None
    assert fts["top_6k"] is None and fts["read_at"] == NOW_ISO
    assert http.efts() == [] and g.calls == 0
    assert not any(f.get("fts") for f in doc["sec"]["filings"])


@pytest.mark.parametrize("mode", ["off", "yes", "", None])
def test_NEGATIVE_switched_off_asks_nothing(_iso, monkeypatch, mode):
    monkeypatch.setattr(SF, "FTS_WHEN", mode)
    http, g = HTTP(), Growth()
    doc = run(http=http, growth=g)
    fts = doc["sec"]["fts"]
    assert fts["status"] == "off" and fts["read_at"] is None and fts["issuance"] == [] and fts["number"] is None
    assert http.efts() == [] and g.calls == 0
    assert not any(f.get("fts") for f in doc["sec"]["filings"])
    assert doc["sec"]["status"] == "none"                                # data.sec.gov still read


def test_an_unchanged_answer_read_after_the_filing_is_not_asked_again(_iso):
    db = pom_db()
    first = run(db)                                              # read 11-26; newest 6-K filed 11-06
    http = HTTP()
    doc = run(db, http, now=NOW + timedelta(hours=2))
    assert http.efts() == []
    assert doc["sec"]["fts"] == first["sec"]["fts"]
    assert [f for f in doc["sec"]["filings"] if f.get("fts")] == [f for f in first["sec"]["filings"] if f.get("fts")]


def test_a_new_6k_is_asked_again(_iso):
    db = pom_db()
    run(db)
    http = HTTP(sub=sub_plus("6-K", "2026-11-20", "0001213900-26-120000"))
    doc = run(db, http, now=NOW + timedelta(hours=2))
    assert len(http.efts("phrase")) == 1 and len(http.efts("number")) == 1       # top_6k moved → both re-asked
    assert doc["sec"]["fts"]["top_6k"] == "0001213900-26-120000"
    assert doc["sec"]["fts"]["top_6k_filed"] == "2026-11-20"


def test_a_moved_window_is_asked_again(_iso):
    db = pom_db()
    run(db)
    http = HTTP()
    doc = run(pom_db(basis=[db["si_share_basis"].docs["POM"]], rec=pom_record(prev_settlement_date="2026-10-15")),
              http, now=NOW + timedelta(hours=2))
    assert doc["sec"]["fts"]["since"] == "2026-10-15"
    assert len(http.efts("phrase")) == 1 and len(http.efts("number")) == 1
    assert http.efts("phrase")[0]["q"]["startdt"] == "2026-10-15"


def test_a_no_hit_on_a_fresh_6k_is_asked_again_until_two_days_after(_iso):
    sub = sub_plus("6-K", "2026-11-25", "0001213900-26-120000")
    db = pom_db()
    empty = body_with([])
    run(db, HTTP(sub=sub, phrase=empty, number=empty))             # read 11-26 (ET) — the day after 11-25
    h2 = HTTP(sub=sub, phrase=empty, number=empty)
    run(db, h2, now=NOW + timedelta(hours=2))                      # still 11-26 ET → both asked again
    assert len(h2.efts("phrase")) == 1 and len(h2.efts("number")) == 1
    h3 = HTTP(sub=sub, phrase=empty, number=empty)
    run(db, h3, now=datetime(2026, 11, 27, 15, tzinfo=timezone.utc))   # 11-27: two days after → asked again ONCE
    h4 = HTTP(sub=sub, phrase=empty, number=empty)
    run(db, h4, now=datetime(2026, 11, 27, 17, tzinfo=timezone.utc))   # read 11-27 > 11-26 → held
    assert len(h3.efts()) == 2 and h4.efts() == []


def test_efts_403_stops_only_the_full_text_and_is_persisted(_iso):
    db, http = pom_db(), HTTP(efts_code=403)
    doc = run(db, http)
    fts = doc["sec"]["fts"]
    assert fts["status"] == "failed" and fts["error"] == "http_403" and fts["read_at"] is None
    assert len(http.efts()) == 1                                    # the number query never ran
    assert doc["sec"]["status"] == "none" and len([c for c in http.calls if c["host"] == "data.sec.gov"]) == 2
    st = db["si_share_basis"].docs[SB.SB_STATE_FTS_ID]
    assert st == {"_id": "state|fts", "blocked_until": "2026-11-26T21:55:00Z", "reason": "http_403"}
    assert SB.SB_STATE_SEC_ID not in db["si_share_basis"].docs and SB._sec_stop["until"] is None
    # a second process (fresh in-process stop) reads the stored one: no efts call; data.sec.gov still asked
    SB._fts_stop["until"] = None
    h2 = HTTP()
    doc2 = run(db, h2, now=NOW + timedelta(minutes=5))
    assert h2.efts() == [] and doc2["sec"]["fts"]["status"] == "blocked"
    assert doc2["sec"]["fts"]["read_at"] is None and doc2["sec"]["fts"]["error_at"] == "2026-11-26T21:45:00Z"
    assert len([c for c in h2.calls if c["host"] == "data.sec.gov"]) >= 1
    # past the stop → asked again
    h3 = HTTP()
    run(db, h3, now=NOW + timedelta(minutes=16))
    assert len(h3.efts()) == 2


def test_efts_429_on_the_number_query_stops_too(_iso):
    db, http = pom_db(), HTTP(number_code=429)
    doc = run(db, http)
    fts = doc["sec"]["fts"]
    assert fts["status"] == "ok" and fts["issuance"] and fts["number"] is None     # the phrase answer stands
    assert fts["error"] == "http_429" and fts["strikes"] == 1
    assert db["si_share_basis"].docs[SB.SB_STATE_FTS_ID]["reason"] == "http_429"


def test_NEGATIVE_store_false_writes_no_stop(_iso):
    db = pom_db()
    doc = run(db, HTTP(efts_code=403), store=False)
    assert doc["sec"]["fts"]["error"] == "http_403" and db.writes() == 0
    assert SB._fts_stop["until"] is not None                         # this process still stops


def test_a_500_over_a_held_good_answer_keeps_the_rows_and_sets_error(_iso):
    db = pom_db()
    first = run(db)
    http = HTTP(sub=sub_plus("6-K", "2026-11-20", "0001213900-26-120000"), efts_code=500, number_code=500)
    doc = run(db, http, now=NOW + timedelta(hours=2))
    fts, held = doc["sec"]["fts"], first["sec"]["fts"]
    assert fts["status"] == "ok" and fts["issuance"] == held["issuance"] and fts["read_at"] == held["read_at"]
    assert fts["top_6k"] == held["top_6k"] and fts["number"] == held["number"]
    assert fts["error"] == "http_500" and fts["error_at"] == "2026-11-26T23:40:00Z" and fts["strikes"] == 1
    assert [f["accn"] for f in doc["sec"]["filings"] if f.get("fts")] == [ACCN]
    assert len(http.efts("phrase")) == 1 and http.efts("number") == []      # the number needs a good phrase pass


def test_NEGATIVE_a_malformed_answer_is_failed_never_raises(_iso):
    for bad in ("junk", {"hits": {}}, ValueError("not json")):
        doc = run(http=HTTP(phrase=bad))
        fts = doc["sec"]["fts"]
        assert fts["status"] == "failed" and fts["error"] in ("ValueError",) and fts["issuance"] == []
        assert not any(f.get("fts") for f in doc["sec"]["filings"])


def test_a_total_above_the_rows_sets_cap(_iso):
    b = copy.deepcopy(FTS["phrase"])
    b["hits"]["total"]["value"] = 150
    doc = run(http=HTTP(phrase=b))
    assert doc["sec"]["fts"]["cap"] == 2
    doc2 = run(http=HTTP())
    assert "cap" not in doc2["sec"]["fts"]


def test_NEGATIVE_a_phrase_hit_outside_the_listing_is_not_marked(_iso):
    b = copy.deepcopy(FTS["phrase"])
    stray = copy.deepcopy(b["hits"]["hits"][0])
    stray["_id"] = "0009999999-26-000001:x.htm"
    stray["_source"]["adsh"] = "0009999999-26-000001"
    b["hits"]["hits"].append(stray)
    b["hits"]["total"]["value"] = 3
    doc = run(http=HTTP(phrase=b))
    assert [r["accn"] for r in doc["sec"]["fts"]["issuance"]] == [ACCN]
    assert [f["accn"] for f in doc["sec"]["filings"] if f.get("fts")] == [ACCN]


def test_marked_rows_join_the_kept_cap(_iso):
    filings = [{"form": "424B5", "filed": "2026-11-%02d" % (1 + i % 20), "items": "", "accn": "a%d" % i}
               for i in range(SB.SB_FILINGS_KEPT)]
    m = [{"form": "6-K", "filed": "2026-11-25", "accn": "m1", "fts": "issuance"}]
    rows, cut = SB._with_marked(filings, m)
    assert cut is True and len(rows) == SB.SB_FILINGS_KEPT and rows[0]["accn"] == "m1"
    rows2, cut2 = SB._with_marked(filings[:3], [dict(m[0], accn="a1")])
    assert cut2 is False and len(rows2) == 3 and [r.get("fts") for r in rows2 if r["accn"] == "a1"] == ["issuance"]
    assert SB._marked({"status": "failed", "issuance": [{"accn": "x", "filed": "2026-11-04"}]}, None) == []
    assert SB._marked({"status": "ok", "issuance": [{"accn": "x", "filed": "2026-10-01"}, "junk"]}, "2026-10-30") == []


# ═════════════════════════════════════════════ step 8b — the number read, NEGATIVES
def test_NEGATIVE_no_growth_asks_no_number(_iso):
    http = HTTP()
    doc = run(http=http, growth=Growth(out=None))
    assert len(http.efts("phrase")) == 1 and http.efts("number") == []
    assert doc["sec"]["fts"]["number"] is None


@pytest.mark.parametrize("g", [{"from_shares": 5, "to_shares": 5}, {"from_shares": 9, "to_shares": 5},
                               {"from_shares": 0, "to_shares": 5}, {"from_shares": 5.0, "to_shares": 9.0},
                               {"from_shares": True, "to_shares": 9}, {"to_shares": 9}, "junk"])
def test_NEGATIVE_no_positive_whole_n_asks_no_number(_iso, g):
    http = HTTP()
    doc = run(http=http, growth=Growth(out=g))
    assert http.efts("number") == [] and doc["sec"]["fts"]["number"] is None


def test_NEGATIVE_a_raising_growth_seam_asks_no_number_and_the_doc_is_stored(_iso):
    db, http = pom_db(), HTTP()
    doc = run(db, http, growth=Growth(exc=RuntimeError("boom")))
    assert http.efts("number") == [] and doc["sec"]["fts"]["status"] == "ok"
    assert db["si_share_basis"].docs["POM"] == doc


def test_a_moved_growth_asks_the_number_again(_iso):
    db = pom_db()
    run(db)
    http = HTTP()
    doc = run(db, http, now=NOW + timedelta(hours=2), growth=Growth(out=dict(GROWTH, to_shares=35761934)))
    assert http.efts("phrase") == [] and len(http.efts("number")) == 1
    q = http.efts("number")[0]["q"]["q"]
    assert q == '"33,185,842"' and doc["sec"]["fts"]["number"]["n"] == N + 1


def test_the_number_query_runs_only_with_6ks_in_the_window(_iso):
    sub = copy.deepcopy(SUB)
    sub["filings"]["recent"]["form"] = ["8-K" if f.startswith("6-K") else f for f in sub["filings"]["recent"]["form"]]
    http, g = HTTP(sub=sub), Growth()
    run(http=http, growth=g)
    assert http.efts() == [] and g.calls == 0


def test_the_default_growth_seam_reads_the_verdict():
    from short_interest import basis_math as BM
    fn = SF.default_growth_fn()
    rec = pom_record()
    doc = {"_id": "POM", "v": 1, "ref": {"status": "ok", "cik": CIK, "type": "CS"},
           "sec": {"status": "none", "since": "2026-10-30", "covers": [], "filings": []},
           "splits": {"status": "ok", "since": "2026-10-30", "rows": []},
           "yahoo": {"float_shares": 1545214, "shares_outstanding": 35761933, "as_of": "2026-11-25"},
           "float_track": dict(TRACK)}
    g = fn(rec, doc, TODAY)
    want = (BM.verdict(rec, doc, TODAY) or {}).get("growth")
    assert g == want
    if g is not None:
        assert SF.growth_numbers(g) == (N, 2576092, 35761933)
    assert fn("junk", None, TODAY) is None


# ═════════════════════════════════════════════ the stop [C12]
def test_fts_stop_reads_and_writes_the_state_doc():
    db = DB(si_share_basis=Coll())
    assert SB._fts_blocked(db, NOW) is False and SB._fts_blocked(None, NOW) is False
    SB._block_fts(db, NOW, "http_403", store=False)
    assert db.writes() == 0 and SB._fts_blocked(None, NOW) is True
    SB._fts_stop["until"] = None
    SB._block_fts(db, NOW, "http_429", store=True)
    SB._fts_stop["until"] = None
    assert SB._fts_blocked(db, NOW + timedelta(minutes=14)) is True
    assert SB._fts_blocked(db, NOW + timedelta(minutes=SB.SB_SEC_BLOCK_MIN)) is False
    assert SB._sec_blocked(db, NOW) is False                          # the SEC stop is a different doc


def test_NEGATIVE_the_state_ids_are_never_symbols():
    assert SB._clean(["POM", "STATE|FTS", "state|fts", "state|sec", " pom "]) == ["POM"]
    assert SB.load(["state|fts"], DB(si_share_basis=Coll([{"_id": "state|fts"}]))) == {}


# ═════════════════════════════════════════════ the Massive counts [C16]
def _ref(results, code=200):
    return SB.fetch_ref("POM", http=lambda url, params=None, timeout=None, **k: Resp(code, {"results": results}))


def test_fetch_ref_keeps_the_two_counts():
    got = _ref({"cik": CIK, "type": "CS", "share_class_shares_outstanding": 35761933,
                "weighted_shares_outstanding": 35966137.0})
    assert got == {"status": "ok", "cik": CIK, "type": "CS", "share_class_shares": 35761933,
                   "weighted_shares": 35966137}
    assert _ref({}, code=404) == {"status": "absent"}


@pytest.mark.parametrize("junk", [True, False, float("nan"), float("inf"), 0, -5, "35761933", None, [1], {"v": 1}])
def test_NEGATIVE_fetch_ref_junk_counts_are_none(junk):
    got = _ref({"cik": CIK, "type": "CS", "share_class_shares_outstanding": junk, "weighted_shares_outstanding": junk})
    assert got["share_class_shares"] is None and got["weighted_shares"] is None and got["status"] == "ok"


def _held_ref(**kw):
    r = {"status": "ok", "cik": CIK, "type": "CS", "read_at": "2026-11-25T21:49:15Z", "error": None,
         "error_at": None, "strikes": 0}
    r.update(kw)
    return r


def test_NEGATIVE_a_day_old_ref_without_the_count_keys_is_read_once_more(_iso):
    http = HTTP()
    doc = run(pom_db(basis=[{"_id": "POM", "ref": _held_ref()}]), http)
    assert len([c for c in http.calls if c["host"] == "api.massive.com"]) == 1
    assert doc["ref"]["weighted_shares"] == 35966137 and doc["ref"]["read_at"] == NOW_ISO
    assert SB._ref_fresh(_held_ref(share_class_shares=None), NOW) is False          # one key is not both


def test_a_ref_with_the_keys_even_none_is_fresh(_iso):
    held = _held_ref(share_class_shares=None, weighted_shares=None)
    http = HTTP()
    doc = run(pom_db(basis=[{"_id": "POM", "ref": held}]), http)
    assert [c for c in http.calls if c["host"] == "api.massive.com"] == [] and doc["ref"] == held


def test_absent_and_failed_refs_write_both_keys(_iso, monkeypatch):
    class H(HTTP):
        def __call__(self, url, **kw):
            if "api.massive.com" in url:
                return Resp(404, {})
            return super().__call__(url, **kw)
    doc = run(http=H())
    assert doc["ref"]["status"] == "absent"
    assert doc["ref"]["share_class_shares"] is None and doc["ref"]["weighted_shares"] is None
    monkeypatch.setattr(SC, "_key", lambda: "")
    doc2 = run(http=HTTP())
    assert doc2["ref"]["status"] == "failed" and "weighted_shares" in doc2["ref"] and "share_class_shares" in doc2["ref"]


# ═════════════════════════════════════════════ fetch_filings `reports`
def test_fetch_filings_returns_the_6k_reports_newest_first():
    reps = pom_reports()
    assert reps == [{"form": "6-K", "filed": "2026-11-06", "accn": TOP, "doc": "ea0311269-6k_pomdoctor.htm"},
                    {"form": "6-K", "filed": "2026-11-04", "accn": ACCN, "doc": DOC},
                    {"form": "6-K", "filed": "2026-11-02", "accn": "0001213900-26-114970",
                     "doc": "ea0310295-6k_pomdoctor.htm"}]
    got = SB.fetch_filings(CIK, "2026-10-30", http=HTTP(), kind_fn=lambda f, i: "registration")
    assert got["reports"] == reps                                  # reports never depend on the kind filter


def test_NEGATIVE_a_6k_without_accession_or_an_8k_is_no_report():
    sub = {"filings": {"recent": {"form": ["6-K", "6-K/A", "8-K", "6-K12B", "6-K"],
                                  "filingDate": ["2026-11-20", "2026-11-19", "2026-11-18", "2026-11-17", "2026-10-01"],
                                  "accessionNumber": ["", "0001-26-1", "0001-26-2", "0001-26-3", "0001-26-4"],
                                  "items": [""] * 5}}}
    got = SB.fetch_filings(CIK, "2026-10-30", http=HTTP(sub=sub), kind_fn=lambda f, i: None)
    assert got["reports"] == [{"form": "6-K/A", "filed": "2026-11-19", "accn": "0001-26-1", "doc": None}]


# ═════════════════════════════════════════════ source guards
def test_source_guards():
    sb = Path(SB.__file__).read_text()
    sf = Path(SF.__file__).read_text()
    assert set(re.findall(r"https?://([^/\"'\s]+)", sb)) <= {"data.sec.gov", "api.massive.com"}
    assert "www.sec.gov" not in sb and "efts.sec.gov" not in sb and "@" not in sb
    assert set(re.findall(r"https?://([^/\"'\s]+)", sf)) == {"efts.sec.gov"}
    assert "www.sec.gov" not in sf and "@" not in sf
    assert not re.search(r"^\s*(import|from)\s+(requests|httpx|aiohttp|socket|http\.client|urllib\.request|urllib3)\b",
                         sf, re.M)
    assert "urlopen" not in sf
    assert sb.count("from short_interest import basis_math") == 2            # spec §3.3: exactly the two lazy seams
    assert not re.search(r"^(from short_interest import basis_math|from short_interest\.basis_math)", sf, re.M)


# ═════════════════════════════════════════════ the recall probe [C7]
def _probe_db():
    def doc(sym, cik, filings, since="2026-10-30"):
        return {"_id": sym, "ref": {"status": "ok", "cik": cik, "type": "CS"},
                "sec": {"status": "ok", "since": since, "filings": filings}}
    return DB(si_share_basis=Coll([
        doc("POM", CIK, [{"form": "424B4", "filed": "2026-11-01"}]),
        doc("NOF", "0000000002", [{"form": "8-K", "filed": "2026-11-01"}, {"form": "S-1", "filed": "2026-11-02"}]),
        doc("ZED", "0000000003", [{"form": "F-1/A", "filed": "2026-11-03"}]),
        {"_id": "state|fts", "blocked_until": "x"}]))


class ProbeHTTP(HTTP):
    def __call__(self, url, **kw):
        if "CIK0000000003" in url:                              # ZED: a listing with no 6-K
            self.calls.append({"host": "data.sec.gov", "path": url, "q": {}, "headers": kw.get("headers"),
                               "params": None})
            return Resp(200, {"filings": {"recent": {"form": ["F-1/A"], "filingDate": ["2026-11-03"],
                                                     "accessionNumber": ["0000000003-26-000001"], "items": [""]}}})
        return super().__call__(url, **kw)


def test_recall_probe_reads_writes_nothing_and_skips_names_with_no_offering(_iso, capsys):
    from scripts import si_fts_recall_probe as RP
    db, http = _probe_db(), ProbeHTTP()
    assert RP.main(["--max", "10"], db=db, http=http, now=NOW) == 0
    out = capsys.readouterr().out
    assert db.writes() == 0
    assert not any("CIK0000000002" in c["path"] for c in http.calls)        # NEGATIVE no F- / 424B row → not asked
    assert len(http.efts()) == 1 and http.efts()[0]["q"]["ciks"] == CIK      # ZED: no 6-K → not asked
    assert "POM    | offerings 424B4 2026-11-01 | 6-Ks since 2026-10-30: 2026-11-06, 2026-11-04, 2026-11-02 " \
           "| phrases hit: 6-K 2026-11-04" in out
    assert "ZED    | offerings F-1/A 2026-11-03 | 6-Ks since 2026-10-30: none — not asked" in out
    assert "asked 1 / with a hit 1 / with none 0 · no 6-K in window 1 · failed 0" in out
    assert "http" not in out and "@" not in out
    assert all(c["headers"] == SB.SB_HTTP_HEADERS for c in http.calls if c["host"] != "api.massive.com")


def test_recall_probe_lists_the_names_with_none_and_honours_max(_iso, capsys):
    from scripts import si_fts_recall_probe as RP
    res = RP.run(_probe_db(), max_names=1, http=ProbeHTTP(phrase=body_with([])), now=NOW, out=lambda s: None)
    assert res["read"] == 1 and res["none"] == ["POM"] and res["asked"] == 1
    res2 = RP.run(_probe_db(), max_names=5, symbols=["zed"], http=ProbeHTTP(), now=NOW, out=lambda s: None)
    assert res2["read"] == 1 and res2["no_6k"] == ["ZED"] and res2["asked"] == 0


def test_NEGATIVE_recall_probe_needs_max_and_stops_on_a_block(_iso, capsys):
    from scripts import si_fts_recall_probe as RP
    with pytest.raises(SystemExit):
        RP.main([], db=_probe_db(), http=ProbeHTTP())
    assert RP.main(["--max", "0"], db=_probe_db(), http=ProbeHTTP()) == 2
    db = _probe_db()
    res = RP.run(db, max_names=5, http=ProbeHTTP(efts_code=403), now=NOW, out=lambda s: None)
    assert res["stopped"] == "http_403" and res["failed"] == ["POM"] and db.writes() == 0
    assert SB._fts_stop["until"] is None                                     # the probe stores and sets no stop


def test_a_held_error_is_retried_on_the_next_pass_and_a_good_read_clears_it(_iso):
    db = pom_db()
    run(db)
    sub = sub_plus("6-K", "2026-11-20", "0001213900-26-120000")
    run(db, HTTP(sub=sub, efts_code=500), now=NOW + timedelta(hours=2))
    assert db["si_share_basis"].docs["POM"]["sec"]["fts"]["error"] == "http_500"
    http = HTTP(sub=sub)
    doc = run(db, http, now=NOW + timedelta(hours=3))
    fts = doc["sec"]["fts"]
    assert len(http.efts("phrase")) == 1 and len(http.efts("number")) == 1
    assert fts["error"] is None and fts["strikes"] == 0 and fts["top_6k"] == "0001213900-26-120000"
    assert fts["read_at"] == "2026-11-27T00:40:00Z"


def test_an_error_left_by_the_number_read_re_asks_the_phrase_next_pass(_iso):
    db = pom_db()
    first = run(db, HTTP(number_code=500))
    assert first["sec"]["fts"]["error"] == "http_500" and first["sec"]["fts"]["number"] is None
    http = HTTP()
    doc = run(db, http, now=NOW + timedelta(hours=2))              # same top 6-K, same window, a held hit
    fts = doc["sec"]["fts"]
    assert len(http.efts("phrase")) == 1 and len(http.efts("number")) == 1
    assert fts["error"] is None and fts["number"]["n"] == N


def test_the_cli_summary_says_the_full_text_read(_iso):
    doc = run()
    assert SB._summary("POM", doc).endswith("| fts ok, 1 issuance 6-K, number 1 hit")
    off = copy.deepcopy(doc)
    off["sec"].pop("fts")
    assert "fts" not in SB._summary("POM", off)                     # NEGATIVE a doc with no fts keeps the old line


# ═════════════════════════════════════════════ refix 2026-11-26: a blocked read never passes a stale answer as known [C1]
def sub_without_6k():
    """The POM listing with every 6-K taken out (the window then holds no 6-K)."""
    s = copy.deepcopy(SUB)
    rc = s["filings"]["recent"]
    keep = [i for i, f in enumerate(rc["form"]) if not str(f).startswith("6-K")]
    for k, v in list(rc.items()):
        if isinstance(v, list):
            rc[k] = [v[i] for i in keep]
    return s


def test_NEGATIVE_a_held_none_6k_under_the_stop_with_6ks_now_listed_is_flagged(_iso):
    from short_interest import basis_math as BM
    db = pom_db()
    first = run(db, HTTP(sub=sub_without_6k()))
    assert first["sec"]["fts"]["status"] == "none_6k" and BM.filings_known(first["sec"]) is True
    SB._fts_stop["until"] = NOW + timedelta(hours=1)
    http = HTTP()
    doc = run(db, http, now=NOW + timedelta(minutes=30))
    fts = doc["sec"]["fts"]
    assert http.efts() == []                                            # the stop holds: no call
    assert fts["status"] == "none_6k" and fts["error"] == "blocked" and fts["error_at"] == "2026-11-26T22:10:00Z"
    assert fts["read_at"] == first["sec"]["fts"]["read_at"] and fts["strikes"] == first["sec"]["fts"]["strikes"]
    assert BM.filings_known(doc["sec"]) is False                        # never "no 6-K filed in the window"


def test_NEGATIVE_a_held_ok_under_the_stop_with_a_newer_unread_6k_is_flagged(_iso):
    from short_interest import basis_math as BM
    db = pom_db()
    first = run(db)
    held = first["sec"]["fts"]
    assert held["status"] == "ok" and held["top_6k"] == TOP and held["error"] is None
    SB._fts_stop["until"] = NOW + timedelta(hours=1)
    http = HTTP(sub=sub_plus("6-K", "2026-11-20", "0001213900-26-120000"))
    doc = run(db, http, now=NOW + timedelta(minutes=30))
    fts = doc["sec"]["fts"]
    assert http.efts() == []
    assert fts["error"] == "blocked" and fts["error_at"] == "2026-11-26T22:10:00Z"
    assert fts["status"] == "ok" and fts["top_6k"] == TOP and fts["issuance"] == held["issuance"]
    assert fts["read_at"] == held["read_at"]                            # the data stands, flagged
    assert BM.filings_known(doc["sec"]) is False


def test_NEGATIVE_a_held_answer_under_the_stop_with_the_window_moved_is_flagged(_iso):
    reports = pom_reports()
    held = {"status": "ok", "since": "2026-10-30", "top_6k": reports[0]["accn"],
            "top_6k_filed": reports[0]["filed"], "issuance": [], "number": None,
            "read_at": "2026-11-26T20:00:00Z", "error": None, "error_at": None, "strikes": 0}
    SB._fts_stop["until"] = NOW + timedelta(hours=1)
    http = HTTP()
    out = SB._fts_step(pom_db(), CIK, held, reports, "2026-10-15", NOW, NOW_ISO, http, store=False)
    assert http.calls == [] and out["error"] == "blocked" and out["error_at"] == NOW_ISO
    assert out["since"] == "2026-10-30" and out["read_at"] == held["read_at"]


def test_a_held_answer_that_still_covers_the_window_stands_unflagged_under_the_stop(_iso):
    reports = pom_reports()
    for status in ("ok", "none_6k"):
        held = {"status": status, "since": "2026-10-30", "top_6k": reports[0]["accn"],
                "top_6k_filed": reports[0]["filed"], "issuance": [], "number": None,
                "read_at": "2026-11-26T20:00:00Z", "error": None, "error_at": None, "strikes": 0}
        SB._fts_stop["until"] = NOW + timedelta(hours=1)
        http = HTTP()
        out = SB._fts_step(pom_db(), CIK, held, reports, "2026-10-30", NOW, NOW_ISO, http, store=False)
        assert http.calls == []
        if status == "ok":
            assert out == held                                          # covers the window → as it is
        else:
            assert out["error"] == "blocked"                            # none_6k with 6-Ks listed never stands


def test_a_flagged_answer_is_re_asked_once_the_stop_ends_and_the_flag_clears(_iso):
    db = pom_db()
    run(db, HTTP(sub=sub_without_6k()))
    SB._fts_stop["until"] = NOW + timedelta(minutes=10)
    run(db, HTTP(), now=NOW + timedelta(minutes=5))
    assert db["si_share_basis"].docs["POM"]["sec"]["fts"]["error"] == "blocked"
    http = HTTP()
    doc = run(db, http, now=NOW + timedelta(minutes=20))
    fts = doc["sec"]["fts"]
    assert len(http.efts("phrase")) == 1
    assert fts["status"] == "ok" and fts["error"] is None and fts["top_6k"] == TOP


# ═════════════════════════════════════════════ refix 2026-11-26 — the retry clock of sec.fts (is_due reads ref / sec / splits only)
def _fts_states(monkeypatch):
    """Three real passes: the phrase read failed (500, nothing held), the efts stop on (nothing held), the number read
    failed (500, the phrase answer good). ref / sec / splits are clean in all three."""
    failed = run(pom_db(), HTTP(efts_code=500))
    monkeypatch.setattr(SB, "_fts_stop", {"until": NOW + timedelta(minutes=SB.SB_SEC_BLOCK_MIN)})
    blocked = run(pom_db())
    monkeypatch.setattr(SB, "_fts_stop", {"until": None})
    numerr = run(pom_db(), HTTP(number_code=500))
    assert failed["sec"]["fts"]["status"] == "failed" and failed["sec"]["fts"]["error"] == "http_500"
    assert blocked["sec"]["fts"]["status"] == "blocked"
    assert numerr["sec"]["fts"]["status"] == "ok" and numerr["sec"]["fts"]["error"] == "http_500"
    for d in (failed, blocked, numerr):
        for k in ("ref", "sec", "splits"):
            assert not d[k].get("error") and d[k].get("status") not in ("failed", "blocked"), (k, d[k])
    return {"failed": failed, "blocked": blocked, "number_error": numerr}


def test_NEGATIVE_a_failed_or_blocked_fts_alone_does_not_make_the_name_due(_iso, monkeypatch):
    rec = pom_record()
    for name, doc in _fts_states(monkeypatch).items():
        assert SB.is_due(doc, rec, NOW + timedelta(minutes=SB.SB_ERROR_RETRY_MIN)) is False, name
        assert SB.is_due(doc, rec, NOW + timedelta(minutes=SB.SB_REFRESH_MIN - 1)) is False, name


def test_a_failed_fts_is_due_again_at_the_refresh_clock(_iso, monkeypatch):
    rec = pom_record()
    for name, doc in _fts_states(monkeypatch).items():
        assert SB.is_due(doc, rec, NOW + timedelta(minutes=SB.SB_REFRESH_MIN)) is True, name
        assert SB.is_due(doc, pom_record(float_shares=1119066), NOW) is True, name    # a `seen` change still wins


def test_the_same_doc_with_a_sec_error_takes_the_short_clock(_iso, monkeypatch):
    """Control: the 5-minute rule is alive on the very doc the fts negatives use, so their False is the fts carve-out."""
    doc = copy.deepcopy(_fts_states(monkeypatch)["failed"])
    doc["sec"].update({"error": "http_500", "error_at": NOW_ISO, "strikes": 1})
    assert SB.is_due(doc, pom_record(), NOW + timedelta(minutes=SB.SB_ERROR_RETRY_MIN - 1)) is False
    assert SB.is_due(doc, pom_record(), NOW + timedelta(minutes=SB.SB_ERROR_RETRY_MIN)) is True


def test_the_reask_docstring_names_the_real_clock():
    d = SB._fts_reask.__doc__ + SB.is_due.__doc__
    assert "retry every sub-doc gets" not in d
    assert "SB_REFRESH_MIN" in SB._fts_reask.__doc__ and "sec.fts" in SB.is_due.__doc__
