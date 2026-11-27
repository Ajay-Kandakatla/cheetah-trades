"""✂️ 6-K split-word read — the probe gate, `split_doc_ok`, `read_split`, K-1 `sec.fts_split` (2026-11-27, spec sicheck
rev 2 §1.6 + §3.3 + §5.4, work package si-io).

Ajay 2026-11-27: "Can you double check short interest for these two please?" — the split filings behind BDMD / POM /
NXAT.

The gate's RAW answers (9 efts GETs: "share consolidation", "reverse stock split", "reverse share split" × BDMD, POM,
NXAT; generic User-Agent, 1 s apart, 2026-11-27 ~10:15 ET) are tests/fixtures/sec_6k_split_probe_2026_11_27.json — no
value typed. The hit table is rebuilt from them through parse_hits → split_doc_ok → by_accession. `reports` for the
gate = the 6-K / 6-K/A filings the answers themselves name (`_source.form`, `adsh`, `file_date`); for POM it is also
checked against the real POM listing. Hermetic otherwise: the refresh runs on the POM harness of
tests/test_si_sec_fts_2026_11_26.py (every outside call a fake). NEGATIVES are marked NEGATIVE.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import short_interest.sec_fts as SF
import short_interest.share_basis as SB
from tests import test_si_sec_fts_2026_11_26 as T                   # the POM harness (HTTP, DB, run, _iso)

_iso = T._iso                                                        # the autouse stops / pacer / key fixture
FIX = Path(__file__).resolve().parent / "fixtures"
PROBE = json.loads((FIX / "sec_6k_split_probe_2026_11_27.json").read_text())
ANS = {(a["symbol"], a["phrase"]): a for a in PROBE["answers"]}
CANDIDATES = ("share consolidation", "reverse stock split", "reverse share split")
SYMS = ("BDMD", "POM", "NXAT")
MUST_HIT = {("BDMD", "0001104659-26-128404"), ("POM", "0001213900-26-110501"), ("NXAT", "0001829126-26-012418")}
MUST_NOT_ACCN = {("BDMD", "0001104659-26-112324"),                    # BDMD 09-30 — financing agreement (EX-10 only)
                 ("POM", "0001213900-26-104640"),                     # POM 09-29 — interim financial statements
                 ("POM", "0001213900-26-116021"),                     # POM 11-04 — debt conversion
                 ("NXAT", "0001829126-26-010775")}                    # NXAT 10-05 — warrant exchange
MUST_NOT_DAY = {("NXAT", "2026-09-11")}                               # NXAT 09-11 — accession not in any answer


def _reports(body):
    """The filer's 6-K / 6-K/A filings as the answer names them (one per accession)."""
    out = {}
    for h in body["hits"]["hits"]:
        s = h["_source"]
        if SF.is_6k(s.get("form")):
            out.setdefault(s["adsh"], {"form": s["form"], "filed": s["file_date"], "accn": s["adsh"], "doc": None})
    return sorted(out.values(), key=lambda r: r["filed"], reverse=True)


def _hits(sym, phrase, gate=True):
    body = ANS[(sym, phrase)]["body"]
    rows = SF.parse_hits(body)["rows"]
    if gate:
        rows = [r for r in rows if SF.split_doc_ok(r.get("file_type"))]
    return SF.by_accession(rows, _reports(body))


def _table(gate=True):
    return {p: {(s, r["accn"], r["filed"]) for s in SYMS for r in _hits(s, p, gate)} for p in CANDIDATES}


def _bad(hits):
    return {h for h in hits if (h[0], h[1]) in MUST_NOT_ACCN or (h[0], h[2]) in MUST_NOT_DAY}


# ═════════════════════════════════════════════ the probe gate (§3.3) — the saved RAW answers are the proof
def test_the_probe_is_nine_raw_200_answers_with_the_generic_user_agent():
    assert len(PROBE["answers"]) == 9 and set(ANS) == {(s, p) for s in SYMS for p in CANDIDATES}
    assert PROBE["user_agent"] == SB.SB_HTTP_HEADERS["User-Agent"] and "@" not in PROBE["user_agent"]
    for a in PROBE["answers"]:
        assert a["status"] == 200 and "body" in a and a["q"] == '"%s"' % a["phrase"]
        assert a["since"] == ("2026-03-31" if a["symbol"] == "POM" else "2025-12-31")


def test_the_admitted_phrases_are_exactly_FTS_SPLIT_PHRASES():
    tab = _table()
    admitted = tuple(p for p in CANDIDATES if not _bad(tab[p]))
    assert admitted == SF.FTS_SPLIT_PHRASES == ("share consolidation", "reverse stock split")
    hit = set().union(*(tab[p] for p in admitted))
    assert MUST_HIT <= {(s, a) for s, a, _ in hit}
    assert _bad(hit) == set()


def test_NEGATIVE_reverse_share_split_is_out_on_nxat_10_05_an_ex_99():
    bad = _bad(_table()["reverse share split"])
    assert bad == {("NXAT", "0001829126-26-010775", "2026-10-05")}
    raw = [h["_source"]["file_type"] for h in ANS[("NXAT", "reverse share split")]["body"]["hits"]["hits"]
           if h["_source"]["adsh"] == "0001829126-26-010775"]
    assert raw == ["EX-99.2"]                                           # an allowed type: the rule cannot drop it


def test_NEGATIVE_bdmd_09_30_is_dropped_only_by_the_document_type_rule():
    raw = _table(gate=False)
    assert ("BDMD", "0001104659-26-112324", "2026-09-30") in raw["share consolidation"]
    types = {h["_source"]["file_type"] for p in CANDIDATES for h in ANS[("BDMD", p)]["body"]["hits"]["hits"]
             if h["_source"]["adsh"] == "0001104659-26-112324"}
    assert types == {"EX-10.1", "EX-10.2"} and not any(SF.split_doc_ok(t) for t in types)
    assert all(("BDMD", "0001104659-26-112324", "2026-09-30") not in v for v in _table().values())


def test_the_hit_table_after_the_gate():
    tab = _table()
    days = lambda p, s: sorted(f for x, _, f in tab[p] if x == s)         # noqa: E731
    assert days("share consolidation", "BDMD") == ["2026-11-16"]
    assert days("share consolidation", "POM") == ["2026-09-04", "2026-10-02", "2026-10-19"]
    assert days("share consolidation", "NXAT") == ["2026-05-27", "2026-07-10", "2026-11-13", "2026-11-23"]
    assert days("reverse stock split", "BDMD") == []
    assert days("reverse stock split", "POM") == ["2026-10-09"]
    assert days("reverse stock split", "NXAT") == ["2026-01-09", "2026-11-17"]


def test_pom_reports_from_the_answer_agree_with_the_real_listing():
    real = T.pom_reports(since="2026-03-31")
    for p in CANDIDATES:
        body = ANS[("POM", p)]["body"]
        rows = [r for r in SF.parse_hits(body)["rows"] if SF.split_doc_ok(r.get("file_type"))]
        assert [r["accn"] for r in SF.by_accession(rows, real)] == [r["accn"] for r in _hits("POM", p)]


# ═════════════════════════════════════════════ split_doc_ok / read_split
@pytest.mark.parametrize("t,ok", [("6-K", True), ("6-K/A", True), ("EX-99.1", True), ("ex-99.2", True),
                                  (" EX-99.3 ", True), ("EX-10.1", False), ("EX-4.1", False), ("EX-1.1", False),
                                  (None, False), ("", False), ("   ", False), (5, False), ("GRAPHIC", False)])
def test_split_doc_ok(t, ok):
    assert SF.split_doc_ok(t) is ok
    assert SF.FTS_SPLIT_DOC_TYPES == ("6-K", "EX-99")


def _hit(accn, file, ftype, filed="2026-11-16"):
    return {"_id": "%s:%s" % (accn, file), "_source": {"adsh": accn, "file_date": filed, "form": "6-K",
                                                      "file_type": ftype, "file_description": ftype}}


class Get:
    def __init__(self, body, code=200):
        self.body, self.code, self.urls = body, code, []

    def __call__(self, url):
        self.urls.append(url)
        return T.Resp(self.code, self.body)


def test_read_split_is_one_get_drops_contract_exhibits_and_keeps_a_6k_body_beside_one():
    a, b = "0001104659-26-128404", "0001104659-26-112324"
    body = {"hits": {"total": {"value": 4}, "hits": [_hit(a, "d.htm", "6-K"), _hit(a, "ex10.htm", "EX-10.1"),
                                                     _hit(b, "x1.htm", "EX-10.1", "2026-09-30"),
                                                     _hit(b, "x2.htm", "EX-10.2", "2026-09-30")]}}
    reps = [{"form": "6-K", "filed": "2026-11-16", "accn": a, "doc": "d.htm"},
            {"form": "6-K", "filed": "2026-09-30", "accn": b, "doc": "e.htm"}]
    g = Get(body)
    got = SF.read_split("0001982444", "2025-12-31", "2026-11-27", reps, get=g)
    assert got == {"status": "ok", "rows": [{"form": "6-K", "filed": "2026-11-16", "accn": a, "doc": "d.htm",
                                             "ex": []}]}
    (u,) = g.urls
    q = dict(__import__("urllib.parse").parse.parse_qsl(u.split("?", 1)[1]))
    assert q["q"] == '"share consolidation" OR "reverse stock split"' and q["forms"] == "6-K"
    assert q["ciks"] == "0001982444" and q["startdt"] == "2025-12-31" and q["enddt"] == "2026-11-27"


def test_read_split_cap_and_failures():
    body = copy.deepcopy(ANS[("POM", "share consolidation")]["body"])
    body["hits"]["total"]["value"] = 150
    got = SF.read_split("0001877971", "2026-03-31", "2026-11-27", T.pom_reports("2026-03-31"), get=Get(body))
    assert got["cap"] == 5 and [r["filed"] for r in got["rows"]] == ["2026-10-19", "2026-10-02", "2026-09-04"]
    assert SF.read_split("x", "a", "b", [], get=Get({}, 403)) == {"status": "failed", "error": "http_403", "code": 403}
    assert SF.read_split("x", "a", "b", [], get=Get("junk"))["error"] == "ValueError"


def test_NEGATIVE_the_issuance_phrases_and_read_are_unchanged():
    assert SF.FTS_ISSUANCE_PHRASES == ("agreed to issue", "issued an aggregate", "private placement",
                                       "registered direct", "securities purchase agreement", "debt conversion",
                                       "at-the-market", "exercise of warrants", "subscription agreement")
    assert not set(SF.FTS_SPLIT_PHRASES) & set(SF.FTS_ISSUANCE_PHRASES)


@pytest.mark.parametrize("mode,on", [("on", True), ("off", False), ("ON", False), ("", False), (None, True)])
def test_split_on(mode, on):
    assert SF.split_on(mode) is on


# ═════════════════════════════════════════════ K-1 through refresh_symbol (the POM harness)
SPLIT_BODY = ANS[("POM", "share consolidation")]["body"]
MF = {"status": "ok", "shares": 10373225, "pct": None, "as_of": "2026-03-31", "read_at": "2026-11-26T03:00:00Z",
      "error": None, "error_at": None, "strikes": 0}


def pom_with_mfloat():
    return T.pom_db(basis=[{"_id": "POM", "mfloat": dict(MF)}])


def test_k1_shape_exact_and_the_window_reaches_the_second_float():
    db, http = pom_with_mfloat(), T.HTTP(split=copy.deepcopy(SPLIT_BODY))
    doc = T.run(db, http)
    fs = doc["sec"]["fts_split"]
    assert set(fs) == {"status", "since", "top_6k", "top_6k_filed", "rows", "read_at", "error", "error_at", "strikes"}
    assert fs["status"] == "ok" and fs["since"] == "2026-03-31" and fs["read_at"] == T.NOW_ISO
    assert fs["top_6k"] == T.TOP and fs["top_6k_filed"] == "2026-11-06" and fs["error"] is None and fs["strikes"] == 0
    assert fs["rows"] == [
        {"form": "6-K", "filed": "2026-10-19", "accn": "0001213900-26-110501", "doc": "ea0308609-6k_pomdoctor.htm",
         "ex": []},
        {"form": "6-K", "filed": "2026-10-02", "accn": "0001213900-26-106373", "doc": "ea0307400-6k_pomdoc.htm",
         "ex": []},
        {"form": "6-K", "filed": "2026-09-04", "accn": "0001213900-26-097663", "doc": "ea0304269-6k_pomdoctor.htm",
         "ex": [{"type": "EX-99.1", "desc": "NOTICE OF EXTRAORDINARY GENERAL MEETING OF SHAREHOLDERS"},
                {"type": "EX-99.2", "desc": "PROXY CARD FOR EXTRAORDINARY GENERAL MEETING OF SHAREHOLDERS"},
                {"type": "EX-99.3", "desc": "VOTING CARD FOR ADS HOLDERS"}]}]
    (sq,) = http.efts("split")
    assert sq["q"]["startdt"] == "2026-03-31" and sq["q"]["forms"] == "6-K"
    assert len([c for c in http.calls if c["host"] == "data.sec.gov" and "/submissions/" in c["path"]]) == 1
    assert db["si_share_basis"].docs["POM"]["sec"]["fts_split"] == fs


def test_one_split_get_per_refresh_and_none_when_held():
    db = pom_with_mfloat()
    first = T.run(db, T.HTTP(split=copy.deepcopy(SPLIT_BODY)))
    h2 = T.HTTP(split=copy.deepcopy(SPLIT_BODY))
    doc = T.run(db, h2, now=T.NOW + timedelta(hours=2))
    assert h2.efts("split") == [] and doc["sec"]["fts_split"] == first["sec"]["fts_split"]
    h3 = T.HTTP(sub=T.sub_plus("6-K", "2026-11-20", "0001213900-26-120000"), split=copy.deepcopy(SPLIT_BODY))
    doc3 = T.run(db, h3, now=T.NOW + timedelta(hours=3))
    assert len(h3.efts("split")) == 1 and doc3["sec"]["fts_split"]["top_6k"] == "0001213900-26-120000"


@pytest.mark.parametrize("mode", ["off", "yes", "", None])
def test_NEGATIVE_switched_off_no_call_status_off(monkeypatch, mode):
    monkeypatch.setattr(SF, "FTS_SPLIT_WHEN", mode)
    http = T.HTTP(split=copy.deepcopy(SPLIT_BODY))
    doc = T.run(pom_with_mfloat(), http)
    fs = doc["sec"]["fts_split"]
    assert http.efts("split") == [] and fs["status"] == "off" and fs["rows"] == [] and fs["read_at"] is None
    assert len(http.efts("phrase")) == 1                                # the issuance read is not switched


def test_NEGATIVE_sec_fts_is_byte_identical_with_the_split_read_on_or_off(monkeypatch):
    on = T.run(pom_with_mfloat(), T.HTTP(split=copy.deepcopy(SPLIT_BODY)))
    monkeypatch.setattr(SF, "FTS_SPLIT_WHEN", "off")
    off = T.run(pom_with_mfloat(), T.HTTP(split=copy.deepcopy(SPLIT_BODY)))
    assert on["sec"]["fts"] == off["sec"]["fts"]
    assert {k: v for k, v in on["sec"].items() if k != "fts_split"} == \
           {k: v for k, v in off["sec"].items() if k != "fts_split"}


def test_NEGATIVE_efts_403_sets_the_fts_stop_held_rows_stand_data_sec_gov_not_stopped():
    db = pom_with_mfloat()
    first = T.run(db, T.HTTP(split=copy.deepcopy(SPLIT_BODY)))
    http = T.HTTP(sub=T.sub_plus("6-K", "2026-11-20", "0001213900-26-120000"), efts_code=403)
    doc = T.run(db, http, now=T.NOW + timedelta(hours=2))
    fs, held = doc["sec"]["fts_split"], first["sec"]["fts_split"]
    assert fs["rows"] == held["rows"] and fs["read_at"] == held["read_at"] and fs["status"] == "ok"
    assert fs["error"] == "blocked" and fs["top_6k"] == held["top_6k"]      # the issuance 403 set the stop first
    assert db["si_share_basis"].docs[SB.SB_STATE_FTS_ID]["reason"] == "http_403"
    assert SB.SB_STATE_SEC_ID not in db["si_share_basis"].docs and SB._sec_stop["until"] is None


def test_NEGATIVE_a_split_only_403_stops_the_full_text_and_keeps_the_held_rows(monkeypatch):
    db = pom_with_mfloat()
    first = T.run(db, T.HTTP(split=copy.deepcopy(SPLIT_BODY)))

    class SplitOnly403(T.HTTP):
        def __call__(self, url, **kw):
            r = super().__call__(url, **kw)
            c = self.calls[-1]
            return T.Resp(403, {}) if c["host"] == "efts.sec.gov" and T._is_split_q(c["q"].get("q", "")) else r
    http = SplitOnly403(sub=T.sub_plus("6-K", "2026-11-20", "0001213900-26-120000"))
    doc = T.run(db, http, now=T.NOW + timedelta(hours=2))
    fs = doc["sec"]["fts_split"]
    assert fs["status"] == "ok" and fs["rows"] == first["sec"]["fts_split"]["rows"]
    assert fs["error"] == "http_403" and fs["strikes"] == 1 and fs["error_at"] == "2026-11-26T23:40:00Z"
    assert db["si_share_basis"].docs[SB.SB_STATE_FTS_ID]["reason"] == "http_403"
    assert SB.SB_STATE_SEC_ID not in db["si_share_basis"].docs


def test_NEGATIVE_nothing_held_and_a_500_is_failed():
    doc = T.run(pom_with_mfloat(), T.HTTP(efts_code=500))
    fs = doc["sec"]["fts_split"]
    assert fs["status"] == "failed" and fs["error"] == "http_500" and fs["rows"] == [] and fs["read_at"] is None


def test_no_6k_in_the_wide_window_is_none_6k_and_asks_nothing():
    sub = copy.deepcopy(T.SUB)
    r = sub["filings"]["recent"]
    r["form"] = ["8-K" if f.startswith("6-K") else f for f in r["form"]]
    http = T.HTTP(sub=sub)
    fs = T.run(pom_with_mfloat(), http)["sec"]["fts_split"]
    assert fs["status"] == "none_6k" and fs["read_at"] == T.NOW_ISO and http.efts("split") == []


def test_a_refresh_with_no_listing_read_carries_the_held_split_read():
    db = pom_with_mfloat()
    first = T.run(db, T.HTTP(split=copy.deepcopy(SPLIT_BODY)))
    SB._sec_stop["until"] = T.NOW + timedelta(hours=5)                  # data.sec.gov stopped: no listing read
    http = T.HTTP()
    doc = T.run(db, http, now=T.NOW + timedelta(hours=2))
    assert doc["sec"]["fts_split"] == first["sec"]["fts_split"] and http.efts() == []


def test_NEGATIVE_fetch_filings_without_wide_since_is_the_old_answer():
    old = SB.fetch_filings(T.CIK, "2026-10-30", http=T.HTTP(), kind_fn=lambda f, i: None)
    new = SB.fetch_filings(T.CIK, "2026-10-30", http=T.HTTP(), kind_fn=lambda f, i: None, wide_since="2026-03-31")
    assert "reports_wide" not in old and {k: v for k, v in new.items() if k != "reports_wide"} == old
    assert [r["filed"] for r in new["reports_wide"]][-1] == "2026-04-08"
    assert new["reports_wide"][:len(old["reports"])] == old["reports"]


# ═════════════════════════════════════════════ fts_split_step (the entry check's phase C)
class DotColl(T.Coll):
    """The harness collection, with a dotted `$set` path written as Mongo does (into the sub-doc)."""

    def update_one(self, q, upd, upsert=False):
        self.writes.append(q["_id"])
        doc = self.docs.setdefault(q["_id"], {"_id": q["_id"]})
        for k, v in (upd.get("$set") or {}).items():
            cur, parts = doc, k.split(".")
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = copy.deepcopy(v)


def checked_pom():
    db = pom_with_mfloat()
    db.colls["si_share_basis"] = DotColl(db["si_share_basis"].docs.values())
    T.run(db, T.HTTP(split=copy.deepcopy(SPLIT_BODY)))
    return db


def test_fts_split_step_held_when_the_stored_read_still_holds():
    db = checked_pom()
    http = T.HTTP(split=copy.deepcopy(SPLIT_BODY))
    assert SB.fts_split_step("POM", db, T.NOW + timedelta(hours=1), http=http) == "held"
    assert http.calls == []


def test_fts_split_step_stored_when_the_window_moved():
    db = checked_pom()
    db["si_share_basis"].docs["POM"]["mfloat"]["as_of"] = "2026-01-15"   # a newer bulk read moved the date back
    http = T.HTTP(split=copy.deepcopy(SPLIT_BODY))
    assert SB.fts_split_step("POM", db, T.NOW + timedelta(hours=1), http=http) == "stored"
    assert len(http.efts("split")) == 1 and http.efts("split")[0]["q"]["startdt"] == "2026-01-15"
    assert len([c for c in http.calls if c["host"] == "data.sec.gov"]) == 1 and http.efts("phrase") == []
    fs = db["si_share_basis"].docs["POM"]["sec"]["fts_split"]
    assert fs["since"] == "2026-01-15" and fs["status"] == "ok" and fs["read_at"] == "2026-11-26T22:40:00Z"
    assert db["si_share_basis"].docs["POM"]["sec"]["fts"]["since"] == "2026-10-30"     # sec.fts untouched


def test_NEGATIVE_fts_split_step_off_test_no_doc():
    db = checked_pom()
    assert SB.fts_split_step("POM", db, T.NOW) == "test"                # http None under pytest: before any read
    assert SB.fts_split_step("NONE", db, T.NOW, http=T.HTTP()) == "no_doc"
    assert SB.fts_split_step("state|sec", db, T.NOW, http=T.HTTP()) == "no_doc"
    import short_interest.sec_fts as SF2
    old = SF2.FTS_SPLIT_WHEN
    try:
        SF2.FTS_SPLIT_WHEN = "off"
        assert SB.fts_split_step("POM", db, T.NOW, http=T.HTTP()) == "off"
    finally:
        SF2.FTS_SPLIT_WHEN = old


def test_NEGATIVE_fts_split_step_failed_under_the_sec_stop_or_a_failed_listing():
    db = checked_pom()
    db["si_share_basis"].docs["POM"]["mfloat"]["as_of"] = "2026-01-15"
    SB._sec_stop["until"] = T.NOW + timedelta(hours=5)
    http = T.HTTP()
    assert SB.fts_split_step("POM", db, T.NOW + timedelta(hours=1), http=http) == "failed" and http.calls == []
    SB._sec_stop["until"] = None
    bad = T.HTTP(sub={"junk": 1})
    assert SB.fts_split_step("POM", db, T.NOW + timedelta(hours=1), http=bad) == "failed"
    assert bad.efts() == []


def test_NEGATIVE_fts_split_step_never_raises():
    class Boom:
        def __getitem__(self, k):
            raise RuntimeError("down")
    assert SB.fts_split_step("POM", Boom(), T.NOW, http=T.HTTP()) == "failed"


def test_split_since_is_the_min_of_the_sec_window_and_the_second_float():
    assert SB.split_since({"sec": {"since": "2026-10-30"}, "mfloat": dict(MF)}) == "2026-03-31"
    assert SB.split_since({"sec": {"since": "2026-10-30"}, "mfloat": dict(MF, as_of="2026-11-20")}) == "2026-10-30"
    assert SB.split_since({"sec": {"since": "2026-10-30"}, "mfloat": dict(MF, status="none")}) == "2026-10-30"
    assert SB.split_since({"sec": {}}) is None and SB.split_since(None) is None


def test_share_basis_keeps_its_two_basis_math_import_lines():
    src = (Path(SB.__file__)).read_text()
    assert src.count("import basis_math") == 2
