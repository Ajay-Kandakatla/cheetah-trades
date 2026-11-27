"""🩳 chip accuracy (2026-11-26, spec sitrack §3.1–§3.3, work package be-si-chip): A1 A2 A3 A4 A6.

Ajay 2026-11-26: "can we make sure in the future these # are accurate ?" — after WHLR's 📄 read "+18" (one prospectus
filed under three registration files, five times) and AKAN's same-day F-1/A was not counted.

A1 the 📄 chip counts filing EVENTS, never copies · A2 S-11 / S-11MEF are registrations · A3 a filing dated ON the
float's (or share count's) date is counted and labelled · A4 days to cover = shares short ÷ average daily volume, with
FINRA's 1.00 floor said · A6 no usable float: the "shares up" baseline is the larger of the record's count and the SEC
cover dated on or before it [C8: `fell` reads that baseline and is NOT suppressed].

The SEC bodies are the real `filings.recent` arrays of WHLR (2026-10-20 → 11-24) and AKAN (2026-09-25 → 11-20), cut
into `tests/fixtures/sec_submissions_{whlr,akan}_2026_11_26.json`. The WHLR record / basis doc are the stored
2026-11-26 shapes (read-only container probe). Hermetic: every outside call is a fake. NEGATIVES marked NEGATIVE.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

import short_interest.share_basis as SB
from short_interest import basis_math as BM
from short_interest import read as SR

FIX = Path(__file__).resolve().parent / "fixtures"
TODAY = date(2026, 11, 26)
OK_AT = "2026-11-26T05:42:15Z"
WHLR_CIK = "0001527541"


def _body(name):
    return json.loads((FIX / ("sec_submissions_%s_2026_11_26.json" % name)).read_text())


class Resp:
    def __init__(self, body, code=200):
        self.status_code, self._body = code, body

    def json(self):
        return copy.deepcopy(self._body)


class HTTP:
    def __init__(self, body, code=200):
        self.body, self.code, self.calls = body, code, []

    def __call__(self, url, params=None, headers=None, timeout=None, **kw):
        self.calls.append(url)
        return Resp(self.body, self.code)


@pytest.fixture(autouse=True)
def _no_pace(monkeypatch):
    monkeypatch.setattr(SB, "_sec_wait", lambda *a, **k: None)


def _fetch(name="whlr", since="2026-10-30", body=None):
    got = SB.fetch_filings(WHLR_CIK, since, http=HTTP(body if body is not None else _body(name)))
    assert got["status"] == "ok"
    return got


def _ok(**kw):
    d = {"status": "ok", "read_at": OK_AT, "error": None, "error_at": None, "strikes": 0}
    d.update(kw)
    return d


WHLR_COVERS = [{"as_of": "2026-05-06", "shares": 1042613, "form": "10-Q", "filed": "2026-05-08"},
               {"as_of": "2026-08-04", "shares": 1931568, "form": "10-Q", "filed": "2026-08-06"},
               {"as_of": "2026-11-03", "shares": 1788532, "form": "10-Q", "filed": "2026-11-05"}]
WHLR_SPLITS = [{"execution_date": "2026-10-30", "split_from": 6, "split_to": 1},
               {"execution_date": "2026-11-30", "split_from": 4, "split_to": 1}]


def whlr_rec(**over):
    r = {"_id": "WHLR", "symbol": "WHLR", "v": 2, "settlement_date": "2026-11-13", "short_interest": 439892,
         "avg_daily_volume": 8981291, "days_to_cover": 1.0, "prev_settlement_date": "2026-10-30",
         "prev_short_interest": 221228, "si_change_pct": 98.8, "float_shares": 53655, "float_asof": "2026-11-07",
         "float_source": "yfinance floatShares (shares_cache)", "shares_outstanding": 978675,
         "shares_asof": "2026-11-07", "shares_source": "yfinance sharesOutstanding (shares_cache)",
         "source": "FINRA short interest (Rule 4560) via Massive /stocks/v1/short-interest",
         "fetched_at": 1795563605.5}
    r.update(over)
    return r


def whlr_doc(filings=None, covers=None, splits=None, yahoo="default", rtype="CS", **sec_over):
    sec = _ok(since="2026-10-30", top_accn="0001527541-26-000418",
              covers=WHLR_COVERS if covers is None else covers,
              filings=_fetch()["filings"] if filings is None else filings)
    sec.update(sec_over)
    return {"_id": "WHLR", "v": 1, "checked_at": OK_AT,
            "ref": _ok(cik=WHLR_CIK, type=rtype),
            "sec": sec,
            "splits": _ok(since="2026-10-30", rows=WHLR_SPLITS if splits is None else splits),
            "yahoo": ({"float_shares": 1667144, "shares_outstanding": 2220906, "as_of": "2026-11-25"}
                      if yahoo == "default" else yahoo),
            "float_track": {"value": 53655, "since": "2026-11-07", "shares": 978675, "shares_asof": "2026-11-07",
                            "basis_asof": "2026-11-07", "origin": "si_doc", "carried": []}}


def _flag(v, key):
    return next((f for f in v["flags"] if f["key"] == key), None)


def _row(b, k):
    return next(r["v"] for r in b["rows"] if r["k"] == k)


# ═════════════════════════════════════════════ A1 — the fetch row shape
def test_fetch_filings_row_shape_carries_doc_file_accn_and_the_same_day_report():
    got = _fetch()
    rows = got["filings"]
    assert "cap" not in got and len(rows) == 28
    assert all(set(r) == {"form", "filed", "items", "doc", "file", "accn", "with"} for r in rows)
    assert rows[0] == {"form": "424B3", "filed": "2026-11-24", "items": "", "doc": "areversestocksplitnovember.htm",
                       "file": "333-298634", "accn": "0001527541-26-000475", "with": "8-K"}
    # the 11/19 8-K is Item 8.01 (no kind, not kept) — it still marks its day
    assert not any(r["filed"] == "2026-11-19" and r["form"] == "8-K" for r in rows)
    assert {r["with"] for r in rows if r["filed"] == "2026-11-19"} == {"8-K"}
    # 11/05: an 8-K and a 10-Q the same day — the first report in listing order
    assert {r["with"] for r in rows if r["filed"] == "2026-11-05"} == {"8-K"}
    # 11/10 S-11 and 10/23 (ARS / DEF 14A only) — no report that day
    assert {r["with"] for r in rows if r["filed"] in ("2026-11-10", "2026-10-23")} == {None}


def test_report_forms_pin_the_house_8k_form():
    assert SB.SB_REPORT_FORMS[0] == BM.FILING_8K_FORM
    assert SB._is_report("8-K") and SB._is_report("6-K/A") and SB._is_report("10-Q") and SB._is_report("20-F")
    assert not SB._is_report("8-K12B") and not SB._is_report("DEFA14A") and not SB._is_report("NT 20-F")


def test_share_basis_imports_nothing_new_from_basis_math():
    src = Path(SB.__file__).read_text()
    assert src.count("from short_interest import basis_math") == 2          # the two lazy seams, as before


def test_NEGATIVE_fetch_filings_junk_arrays_never_raise_and_rows_count_as_before():
    rec = _body("whlr")["filings"]["recent"]
    for mutate in (lambda r: r.pop("primaryDocument"), lambda r: r.update(primaryDocument="x"),
                   lambda r: r.update(primaryDocument=r["primaryDocument"][:3]),
                   lambda r: r.update(fileNumber=[5] * len(r["fileNumber"])),
                   lambda r: r.update(primaryDocument=[None] * len(r["primaryDocument"]))):
        r = copy.deepcopy(rec)
        mutate(r)
        got = _fetch(body={"filings": {"recent": r}})
        assert len(got["filings"]) == 28
    bad = copy.deepcopy(rec)
    bad.pop("primaryDocument")
    bad.pop("fileNumber")
    rows = _fetch(body={"filings": {"recent": bad}})["filings"]
    assert all(r["doc"] is None and r["file"] is None for r in rows)


def test_fetch_filings_cap_is_returned_only_when_the_list_is_cut():
    n = SB.SB_FILINGS_KEPT + 3
    body = {"filings": {"recent": {"form": ["424B5"] * n, "filingDate": ["2026-11-%02d" % (1 + i % 20) for i in range(n)],
                                   "items": [""] * n}}}
    got = _fetch(body=body, since="2026-01-01")
    assert got["cap"] == SB.SB_FILINGS_KEPT and len(got["filings"]) == SB.SB_FILINGS_KEPT
    body["filings"]["recent"] = {k: v[:SB.SB_FILINGS_KEPT] for k, v in body["filings"]["recent"].items()}
    assert "cap" not in _fetch(body=body, since="2026-01-01")


def test_sec_step_stores_the_cap_and_verdict_says_it(monkeypatch):
    monkeypatch.setattr(SB, "_sec_blocked", lambda db, now: False)
    n = SB.SB_FILINGS_KEPT + 1
    sub = {"filings": {"recent": {"form": ["424B5"] * n, "filingDate": ["2026-11-20"] * n, "items": [""] * n}}}
    dei = {"units": {"shares": [{"end": "2026-11-03", "val": 1788532, "form": "10-Q", "filed": "2026-11-05"}]}}

    def http(url, **kw):
        return Resp(sub if "submissions" in url else dei)

    now = datetime(2026, 11, 26, 5, 0, tzinfo=timezone.utc)
    out = SB._sec_step(None, WHLR_CIK, {}, {}, "2026-10-30", now, OK_AT, http, None, False)
    assert out["filings_cap"] == SB.SB_FILINGS_KEPT
    v = BM.verdict(whlr_rec(), whlr_doc(filings=out["filings"], filings_cap=out["filings_cap"]), TODAY)
    assert _flag(v, BM.FLAG_FILING)["text"].endswith(BM.TEXT_FILING_CAPPED % SB.SB_FILINGS_KEPT)
    sub["filings"]["recent"] = {k: v[:2] for k, v in sub["filings"]["recent"].items()}
    out2 = SB._sec_step(None, WHLR_CIK, {}, {}, "2026-10-30", now, OK_AT, http, None, False)
    assert "filings_cap" not in out2
    v2 = BM.verdict(whlr_rec(), whlr_doc(filings=out2["filings"]), TODAY)
    assert "only the newest" not in _flag(v2, BM.FLAG_FILING)["text"]


# ═════════════════════════════════════════════ A1 — events, not copies (WHLR)
def test_WHLR_five_events_fifteen_copies_and_the_chip():
    ev = BM.filing_events(_fetch()["filings"], "2026-11-07")
    assert [(e["label"], e["filed"]) for e in ev["events"]] == [
        ("8-K 3.02", "2026-11-20"), ("424B3", "2026-11-18"), ("8-K 3.02", "2026-11-18"), ("S-11", "2026-11-10"),
        ("8-K 3.02", "2026-11-09")]
    assert ev["n_filings"] == 20 and ev["n_copies"] == 15 and ev["unchecked"] == 0 and ev["cap"] is None
    assert [(e["form"], e["filed"], e["items"]) for e in ev["charter"]] == [("8-K", "2026-11-24", "3.03,5.03,9.01")]
    assert all(e["same_day"] is False for e in ev["events"])
    v = BM.verdict(whlr_rec(), whlr_doc(), TODAY)
    f = _flag(v, BM.FLAG_FILING)
    assert f["short"] == "📄 8-K 3.02 11/20 +4"
    assert f["text"] == ("📄 5 dilution filings since 11/7: 8-K 3.02 11/20 · 424B3 11/18 · 8-K 3.02 11/18 (+2 more)"
                         " — 15 prospectus copies of same-day reports not counted (one document filed under several "
                         "registrations)")
    assert [x["filed"] for x in v["filings"]] == ["2026-11-20", "2026-11-18", "2026-11-18", "2026-11-10", "2026-11-09"]
    assert set(v["filings"][0]) == {"form", "filed", "items", "kind", "copies", "same_day"}
    assert "Charter filing (a reverse split is filed under this item; so are other charter changes): 8-K Item " \
           "3.03/5.03 11/24." in v["title_lines"]
    b = SR.si_block(whlr_rec(), TODAY, basis=whlr_doc())
    assert b["chip"] == ("🩳 SI EXTREME 26.4% float · <0.1d · 11/13 · ⚠️ float updated · ✂️ split due 11/30 · "
                         "📄 8-K 3.02 11/20 +4")
    json.dumps(b, allow_nan=False)


def test_NEGATIVE_WHLR_the_11_24_reverse_split_document_is_never_a_dilution_event():
    ev = BM.filing_events(_fetch()["filings"], "2026-11-21")
    assert ev["events"] == [] and ev["n_copies"] == 3 and len(ev["charter"]) == 1


def test_NEGATIVE_two_different_documents_the_same_day_stay_two_events():
    rows = [r for r in _fetch(since="2026-10-20")["filings"] if r["filed"] == "2026-10-23"]
    ev = BM.filing_events(rows, "2026-10-20")
    assert [e["form"] for e in ev["events"]] == ["424B3"] * 3 and ev["n_copies"] == 0


def _frow(form, filed, items="", doc=None, file=None, with_=None):
    return {"form": form, "filed": filed, "items": items, "doc": doc, "file": file, "accn": None, "with": with_}


def test_NEGATIVE_a_single_file_424B5_beside_an_8K_801_stays_an_event():
    ev = BM.filing_events([_frow("424B5", "2026-11-20", doc="p.htm", file="333-1", with_="8-K")], "2026-11-10")
    assert [(e["form"], e["copies"]) for e in ev["events"]] == [("424B5", 0)] and ev["n_copies"] == 0


def test_NEGATIVE_a_multi_file_document_with_no_same_day_report_counts_once_not_zero():
    rows = [_frow("424B3", "2026-11-20", doc="p.htm", file="333-%d" % i) for i in range(3)]
    ev = BM.filing_events(rows, "2026-11-10")
    assert [(e["form"], e["copies"]) for e in ev["events"]] == [("424B3", 2)] and ev["n_copies"] == 2


def test_NEGATIVE_a_424B_beside_a_10Q_only_under_three_files_adds_no_event():
    body = {"filings": {"recent": {
        "form": ["424B3", "424B3", "424B3", "10-Q"], "filingDate": ["2026-11-05"] * 4, "items": [""] * 4,
        "primaryDocument": ["q.htm"] * 3 + ["whlr-q.htm"], "fileNumber": ["333-1", "333-2", "333-3", "001-1"],
        "accessionNumber": ["a1", "a2", "a3", "a4"]}}}
    rows = _fetch(body=body, since="2026-11-01")["filings"]
    assert {r["with"] for r in rows} == {"10-Q"}
    ev = BM.filing_events(rows, "2026-11-01")
    assert ev["events"] == [] and ev["n_copies"] == 3 and ev["n_filings"] == 3


def test_NEGATIVE_rows_without_doc_count_as_before_and_say_not_yet_checked():
    stored = [{"form": r["form"], "filed": r["filed"], "items": r["items"]} for r in _fetch()["filings"]
              if r["form"] != "S-11"]                                # the shape stored before 2026-11-26
    v = BM.verdict(whlr_rec(), whlr_doc(filings=stored), TODAY)
    f = _flag(v, BM.FLAG_FILING)
    assert f["short"] == "📄 424B3 11/24 +18"                          # what the chip read on 11-26 — unchanged
    assert f["text"].endswith(" — 16 prospectus filings not yet checked for copies")
    assert "copies of same-day reports" not in f["text"]


@pytest.mark.parametrize("junk", [
    None, "x", 5, {"form": "424B3"}, [None, 5, "x", {}], [{"form": 5, "filed": "2026-11-20"}],
    [{"form": "424B3", "filed": "not a date"}], [{"form": "424B3", "filed": "2026-11-20", "doc": 7, "file": [1],
                                                  "with": 3, "accn": {}}],
    [{"form": "424B3", "filed": "2026-11-20", "items": ["3.02", None, True]}],
])
def test_NEGATIVE_filing_events_never_raises_on_junk(junk):
    ev = BM.filing_events(junk, "2026-11-01")
    # 2026-11-26 sishares §3.2 (C13): + n_reports (a marked 6-K reporting an offering already counted that day)
    assert set(ev) == {"events", "charter", "n_filings", "n_copies", "unchecked", "n_reports", "cap"}
    json.dumps(ev, allow_nan=False)
    for e in ev["events"]:
        assert e["copies"] == 0                                      # junk doc / file → a row of its own


@pytest.mark.parametrize("anchor", [None, "", "nope", 5])
def test_NEGATIVE_no_anchor_no_events(anchor):
    ev = BM.filing_events(_fetch()["filings"], anchor)
    assert ev["events"] == [] and ev["charter"] == [] and ev["n_filings"] == 0


# ═════════════════════════════════════════════ A2 — S-11
@pytest.mark.parametrize("form", ["S-11", "S-11/A", "S-11MEF", " s-11 "])
def test_S11_is_a_registration(form):
    assert BM.filing_kind(form, "") == BM.KIND_REGISTRATION


@pytest.mark.parametrize("form", ["S-8", "F-11", "S-111", "S-11X", "S-1MEFX"])
def test_NEGATIVE_not_a_registration(form):
    assert BM.filing_kind(form, "") is None


def test_NEGATIVE_without_S11_in_the_tuple_the_WHLR_count_drops(monkeypatch):
    monkeypatch.setattr(BM, "FILING_REGISTRATION_FORMS",
                        tuple(f for f in BM.FILING_REGISTRATION_FORMS if f not in ("S-11", "S-11MEF")))
    assert BM.filing_kind("S-11", "") is None                        # "S-1" never catches "S-11" by prefix
    v = BM.verdict(whlr_rec(), whlr_doc(filings=_fetch()["filings"]), TODAY)
    assert _flag(v, BM.FLAG_FILING)["short"] == "📄 8-K 3.02 11/20 +3"   # the WHLR pin above goes red


# ═════════════════════════════════════════════ A3 — same day (AKAN)
def akan_rec(**over):
    r = {"_id": "AKAN", "symbol": "AKAN", "v": 2, "settlement_date": "2026-11-13", "short_interest": 120000,
         "avg_daily_volume": 400000, "days_to_cover": 1.0, "prev_settlement_date": "2026-10-31",
         "prev_short_interest": 100000, "float_shares": 2000000, "float_asof": "2026-11-20",
         "shares_outstanding": 2500000, "shares_asof": "2026-11-20"}
    r.update(over)
    return r


def akan_doc(filings):
    return {"_id": "AKAN", "v": 1, "checked_at": OK_AT, "ref": _ok(cik="0001888014", type="CS"),
            "sec": _ok(since="2026-09-25", top_accn=None, covers=[], filings=filings),
            "splits": _ok(since="2026-09-25", rows=[]), "yahoo": None, "float_track": None}


def _akan_filings():
    return SB.fetch_filings("0001888014", "2026-09-25", http=HTTP(_body("akan")))["filings"]


def test_AKAN_same_day_F1A_is_counted_and_labelled():
    rows = _akan_filings()
    assert [(r["form"], r["filed"]) for r in rows] == [("F-1/A", "2026-11-20"), ("F-1/A", "2026-11-06"),
                                                       ("F-1/A", "2026-10-19"), ("F-1", "2026-10-01")]
    v = BM.verdict(akan_rec(), akan_doc(rows), TODAY)
    f = _flag(v, BM.FLAG_FILING)
    assert f["short"] == "📄 F-1/A 11/20 · same day"
    assert f["text"] == ("📄 dilution filing: F-1/A 11/20 — F-1/A 11/20 filed the same day the float was read; which "
                         "came first is not known")
    assert v["filings"][0]["same_day"] is True and v["filings"][0]["copies"] == 0
    assert "📄 F-1/A 11/20 · same day" in SR.si_block(akan_rec(), TODAY, basis=akan_doc(rows))["chip"]


def test_NEGATIVE_a_filing_the_day_BEFORE_the_anchor_is_not_counted():
    v = BM.verdict(akan_rec(float_asof="2026-11-21", shares_asof="2026-11-21"), akan_doc(_akan_filings()), TODAY)
    assert _flag(v, BM.FLAG_FILING) is None and v["filings"] == []


def test_NEGATIVE_a_mixed_list_uses_the_plain_short_and_names_the_same_day_one():
    v = BM.verdict(akan_rec(float_asof="2026-11-06", shares_asof="2026-11-06"), akan_doc(_akan_filings()), TODAY)
    f = _flag(v, BM.FLAG_FILING)
    assert f["short"] == "📄 F-1/A 11/20 +1"
    assert f["text"] == ("📄 2 dilution filings since 11/6: F-1/A 11/20 · F-1/A 11/6 — F-1/A 11/6 filed the same day "
                         "the float was read; which came first is not known")


def test_same_day_on_a_share_count_anchor_says_the_share_count():
    rows = [_frow("424B5", "2026-11-07", doc="p.htm", file="333-1")]
    v = BM.verdict(whlr_rec(), whlr_doc(filings=rows), TODAY)              # WHLR: no usable float, anchor = Pa
    f = _flag(v, BM.FLAG_FILING)
    assert f["short"] == "📄 424B5 11/7 · same day"
    assert "filed the same day the share count was read" in f["text"] and "the float was read" not in f["text"]


def test_a_same_day_charter_filing_is_named_with_the_same_tail():
    rows = [_frow("8-K", "2026-11-07", items="5.03,9.01")]
    v = BM.verdict(whlr_rec(), whlr_doc(filings=rows), TODAY)
    assert ("Charter filing (a reverse split is filed under this item; so are other charter changes): 8-K Item 5.03 "
            "11/7 — 8-K Item 5.03 11/7 filed the same day the share count was read; which came first is not known."
            ) in v["title_lines"]


def test_several_events_all_same_day_keep_the_same_day_short():
    rows = [_frow("424B5", "2026-11-20", doc="a.htm", file="333-1"), _frow("S-1", "2026-11-20")]
    v = BM.verdict(akan_rec(), akan_doc(rows), TODAY)
    assert _flag(v, BM.FLAG_FILING)["short"] == "📄 424B5 11/20 +1 · same day"


# ═════════════════════════════════════════════ A4 — days to cover
def test_WHLR_days_to_cover_is_computed_and_names_the_floor():
    b = SR.si_block(whlr_rec(), TODAY)
    assert SR.dtc_computed(b) == pytest.approx(439892 / 8981291)
    assert b["days_to_cover"] == 1.0                                     # the provider's value stays on the block
    assert " · <0.1d · " in b["chip"]
    assert ("0.05 days to cover — 439,892 shares short ÷ 8,981,291 average daily volume (the provider's window). "
            "FINRA's file shows 1.00 for any value at or under 1.") in b["title"]
    assert _row(b, "Days to cover") == ("0.05 — 439,892 shares short ÷ 8,981,291 average daily volume (the "
                                        "provider's window). FINRA's file shows 1.00 for any value at or under 1.")
    assert SR.DTC_SPLIT_NOTE not in b["title"]                           # no basis → no split read


def test_the_split_note_only_when_basis_change_is_a_dict():
    # PIN MOVED 2026-11-27 (spec sicheck §3.4 B1): the note needs a split STRICTLY after the prior settlement and on or
    # before this one. WHLR's 10/30 split IS its prior settlement day → a change dict, but no sentence now; the same
    # doc with the split moved to 11/2 (inside the window) keeps the sentence.
    b = SR.si_block(whlr_rec(), TODAY, basis=whlr_doc())
    assert isinstance(b["basis"]["change"], dict)
    assert SR.DTC_SPLIT_NOTE.strip() not in b["title"] and SR.DTC_SPLIT_NOTE.strip() not in _row(b, "Days to cover")
    inside = [dict(r, execution_date="2026-11-02") if r["execution_date"] == "2026-10-30" else r for r in WHLR_SPLITS]
    b1 = SR.si_block(whlr_rec(), TODAY, basis=whlr_doc(splits=inside))
    assert isinstance(b1["basis"]["change"], dict)
    assert SR.DTC_SPLIT_NOTE.strip() in b1["title"] and SR.DTC_SPLIT_NOTE.strip() in _row(b1, "Days to cover")
    b2 = SR.si_block(whlr_rec(), TODAY, basis=whlr_doc(splits=[]))
    assert b2["basis"]["change"] is None and SR.DTC_SPLIT_NOTE.strip() not in b2["title"]


@pytest.mark.parametrize("adv", [0, None, float("nan"), -5, "x", True])
def test_NEGATIVE_no_usable_adv_reads_the_provider_never_divides(adv):
    b = SR.si_block(whlr_rec(avg_daily_volume=adv, days_to_cover=3.2), TODAY)
    assert SR.dtc_computed(b) is None
    assert " · 3.2d · " in b["chip"]
    assert "3.2 days to cover (the provider's figure)." in b["title"] and "FINRA's file" not in b["title"]
    assert _row(b, "Days to cover") == "3.20 — the provider's figure"


def test_NEGATIVE_provider_floor_with_no_adv_prints_at_most_one_day():
    b = SR.si_block(whlr_rec(avg_daily_volume=None), TODAY)
    assert " · ≤1d · " in b["chip"]
    assert "1.0 days to cover (the provider's figure). FINRA's file shows 1.00 for any value at or under 1." in b["title"]
    assert _row(b, "Days to cover") == ("1.00 — the provider's figure. FINRA's file shows 1.00 for any value at or "
                                        "under 1.")


def test_NEGATIVE_a_real_figure_carries_no_floor_sentence():
    b = SR.si_block(whlr_rec(short_interest=3200, avg_daily_volume=1000, days_to_cover=3.2), TODAY)
    assert " · 3.2d · " in b["chip"]
    assert "3.20 days to cover — 3,200 shares short ÷ 1,000 average daily volume" in b["title"]
    assert "FINRA's file" not in b["title"] and "FINRA's file" not in _row(b, "Days to cover")
    above = SR.si_block(whlr_rec(short_interest=1500, avg_daily_volume=1000, days_to_cover=1.0), TODAY)
    assert " · 1.5d · " in above["chip"] and "FINRA's file" not in above["title"]


@pytest.mark.parametrize("dtc", [0, 0.0, None])
def test_NEGATIVE_zero_short_and_no_provider_figure_prints_no_segment(dtc):
    b = SR.si_block(whlr_rec(short_interest=0, days_to_cover=dtc), TODAY)
    assert SR.dtc_computed(b) is None and "d · 11/13" not in b["chip"] and "0.0d" not in b["chip"]


@pytest.mark.parametrize("blk", [None, [], "x", {}, {"si_shares": 5}, {"si_shares": 5, "avg_daily_volume": 0},
                                 {"si_shares": True, "avg_daily_volume": 5}, {"si_shares": float("inf"),
                                                                              "avg_daily_volume": 5}])
def test_NEGATIVE_dtc_computed_is_None_on_junk(blk):
    assert SR.dtc_computed(blk) is None


def test_the_floor_constants_and_the_rules_sentence():
    assert SR.DTC_FINRA_FLOOR == 1.0
    assert SR.DTC_FLOOR_NOTE == " FINRA's file shows 1.00 for any value at or under 1."
    pick = next(p for p in SR.rules_section()["picks"] if p.startswith("Days to cover = "))
    assert pick.endswith(SR.DTC_FLOOR_NOTE) and SR.DTC_CHIP_FLOOR in pick


# ── A4 refix (2026-11-26): the EXTREME hover on the same card reads the same days-to-cover sentence as the title
def test_WHLR_extreme_hover_prints_the_division_never_the_providers_floor():
    b = SR.si_block(whlr_rec(float_shares=900000), TODAY)            # WHLR with a float on file → the EXTREME note
    assert b["tier"] == "extreme" and " · <0.1d · " in b["chip"]
    t = b["extreme"]["title"]
    assert ("0.05 days to cover — 439,892 shares short ÷ 8,981,291 average daily volume (the provider's window). "
            "FINRA's file shows 1.00 for any value at or under 1. Float basis:") in t
    assert "1.0 days to cover" not in t and t.count("days to cover") == 1
    assert SR._dtc_sentence(b, SR.dtc_computed(b)) in b["title"]       # the card title carries the same sentence
    assert b["days_to_cover"] == 1.0                                     # the provider's value stays on the block


@pytest.mark.parametrize("over", [
    {},                                                                  # computed, floor sentence
    {"short_interest": 3200, "avg_daily_volume": 1000, "days_to_cover": 3.2},   # computed, no floor sentence
    {"avg_daily_volume": None},                                          # provider floor, floor sentence
    {"avg_daily_volume": None, "days_to_cover": 3.2},                    # provider figure, no floor sentence
    {"avg_daily_volume": 0, "days_to_cover": 2.5},                       # ✗ ADV 0 → the provider, never a division
])
def test_extreme_hover_and_card_title_carry_one_sentence(over):
    kw = {"float_shares": 900000, **over}
    if "short_interest" in over:
        kw.update(float_shares=8000, shares_outstanding=10000)           # keep it EXTREME on the small count
    b = SR.si_block(whlr_rec(**kw), TODAY)
    assert b["extreme"] is not None
    calc = SR.dtc_computed(b)
    want = SR._dtc_sentence(b, calc)
    assert want in b["extreme"]["title"] and want in b["title"]
    assert b["extreme"]["title"].count("days to cover") == 1


def test_NEGATIVE_extreme_hover_provider_figure_with_no_adv():
    b = SR.si_block(whlr_rec(float_shares=900000, avg_daily_volume=None, days_to_cover=3.2), TODAY)
    t = b["extreme"]["title"]
    assert "3.2 days to cover (the provider's figure). Float basis:" in t
    assert "FINRA's file" not in t and "average daily volume" not in t
    f = SR.si_block(whlr_rec(float_shares=900000, avg_daily_volume=None), TODAY)["extreme"]["title"]
    assert "1.0 days to cover (the provider's figure). FINRA's file shows 1.00 for any value at or under 1." in f


@pytest.mark.parametrize("dtc", [0, 0.0, None, float("nan"), -1.0])
def test_NEGATIVE_extreme_hover_no_adv_and_no_positive_provider_figure_prints_nothing(dtc):
    b = SR.si_block(whlr_rec(float_shares=900000, avg_daily_volume=None, days_to_cover=dtc), TODAY)
    e = b["extreme"]
    assert e is not None and "days to cover" not in e["title"] and "FINRA's file" not in e["title"]
    json.dumps(b, allow_nan=False)


def test_NEGATIVE_extreme_hover_split_note_only_with_a_change_dict():
    b = SR.si_block(whlr_rec(float_shares=900000), TODAY)
    assert SR.DTC_SPLIT_NOTE.strip() not in b["extreme"]["title"]
    bb = copy.deepcopy(b)
    # PIN MOVED 2026-11-27 (spec sicheck §3.4 B1): a change dict alone is not enough — its split must sit strictly after
    # the prior settlement (10/30) and on or before this one (11/13)
    bb["basis"] = {"change": {"pct": 1.0}}
    assert SR.DTC_SPLIT_NOTE.strip() not in SR.extreme_title(bb, bb["pct_of_float"])
    bb["basis"] = {"change": {"pct": 1.0, "splits": [{"execution_date": "2026-11-02"}]}}
    assert SR.DTC_SPLIT_NOTE.strip() in SR.extreme_title(bb, bb["pct_of_float"])
    bb["basis"] = {"change": {"pct": 1.0, "splits": [{"execution_date": "2026-10-30"}]}}
    assert SR.DTC_SPLIT_NOTE.strip() not in SR.extreme_title(bb, bb["pct_of_float"])
    bb["basis"] = {"change": "x"}
    assert SR.DTC_SPLIT_NOTE.strip() not in SR.extreme_title(bb, bb["pct_of_float"])


# ═════════════════════════════════════════════ A6 — the no-usable-float baseline
def test_WHLR_shares_up_flag_goes_and_the_three_counts_are_in_the_hover():
    v = BM.verdict(whlr_rec(), whlr_doc(), TODAY)
    assert _flag(v, BM.FLAG_COUNT_STALE) is None and v["fell"] is None and _flag(v, BM.FLAG_COUNT_FELL) is None
    g = v["growth"]
    assert (g["from_shares"], g["from_asof"], g["from_source"]) == (1788532, "2026-11-03", "sec")
    assert (g["to_shares"], g["to_asof"], g["to_source"], g["ratio"]) == (2220906, "2026-11-25", "yahoo", 1.242)
    assert g["record_under"] == {"shares": 978675, "as_of": "2026-11-07"}
    assert ("Share counts: the record carried 978,675 (11/7), under the SEC 10-Q cover count 1,788,532 (11/3) already "
            "dated — growth is read from the SEC count: 2,220,906 (Yahoo, 11/25) = 1.2×.") in v["title_lines"]
    b = SR.si_block(whlr_rec(), TODAY, basis=whlr_doc())
    assert "shares up" not in b["chip"] and b["basis"]["growth"]["record_under"]["shares"] == 978675
    assert b["pct_of_shares_out"] == 19.81                               # step 3 untouched


def test_the_raised_baseline_can_still_flag_shares_up_with_the_sec_words():
    yahoo = {"float_shares": 1667144, "shares_outstanding": 4000000, "as_of": "2026-11-25"}
    v = BM.verdict(whlr_rec(), whlr_doc(yahoo=yahoo), TODAY)
    f = _flag(v, BM.FLAG_COUNT_STALE)
    assert f["short"] == "⚠️ shares up 2.2×"
    assert f["text"] == ("⚠️ 2.2× more shares than the SEC 10-Q cover count dated on or before the record: 4,000,000 "
                         "(Yahoo, 11/25) vs 1,788,532 (11/3) — the % uses the newer count; the record itself carried "
                         "978,675 (11/7)")


def test_NEGATIVE_a_cover_under_the_record_leaves_the_baseline():
    covers = [{"as_of": "2026-11-03", "shares": 900000, "form": "10-Q", "filed": "2026-11-05"}]
    v = BM.verdict(whlr_rec(), whlr_doc(covers=covers), TODAY)
    assert v["growth"]["from_source"] == "record" and "record_under" not in v["growth"]
    assert _flag(v, BM.FLAG_COUNT_STALE)["short"] == "⚠️ shares up 2.3×"
    assert not any(l.startswith("Share counts:") for l in v["title_lines"])


def test_NEGATIVE_a_cover_dated_after_the_anchor_never_becomes_the_baseline():
    covers = [{"as_of": "2026-11-10", "shares": 1788532, "form": "10-Q", "filed": "2026-11-12"}]
    v = BM.verdict(whlr_rec(), whlr_doc(covers=covers), TODAY)
    assert v["growth"]["from_source"] == "record" and "record_under" not in v["growth"]


def test_a_cover_across_a_split_is_rebased_first():
    up = [{"as_of": "2026-10-20", "shares": 6000000, "form": "10-Q", "filed": "2026-10-21"}]      # ÷6 → 1,000,000
    v = BM.verdict(whlr_rec(), whlr_doc(covers=up), TODAY)
    assert (v["growth"]["from_shares"], v["growth"]["from_source"]) == (1000000, "sec")
    down = [{"as_of": "2026-10-20", "shares": 5000000, "form": "10-Q", "filed": "2026-10-21"}]    # ÷6 → 833,333
    v2 = BM.verdict(whlr_rec(), whlr_doc(covers=down), TODAY)
    assert v2["growth"]["from_source"] == "record"                     # NEGATIVE: raw 5M > record, rebased it is not


@pytest.mark.parametrize("split_day", ["2026-11-03", "2026-11-07"])
def test_NEGATIVE_a_split_ON_either_date_leaves_the_baseline(split_day):
    splits = [{"execution_date": split_day, "split_from": 1, "split_to": 2}]
    v = BM.verdict(whlr_rec(), whlr_doc(splits=splits, yahoo=None), TODAY)
    assert "record_under" not in (v["growth"] or {})
    assert not any(l.startswith("Share counts:") for l in v["title_lines"])


def test_NEGATIVE_an_ADR_cover_is_not_compared():
    v = BM.verdict(whlr_rec(), whlr_doc(rtype="ADRC"), TODAY)
    assert v["growth"]["from_source"] == "record" and "record_under" not in v["growth"]
    assert v["sources"]["sec"] == "units"


# The float branch is byte-identical to cc63e6ff: sha256 of the canonical JSON of cc63e6ff's own `verdict` on the
# 11-24 fixtures (computed 2026-11-26 from `git show cc63e6ff:backend/short_interest/basis_math.py`). The only new
# served keys (`copies`, `same_day` on each filing) are dropped before hashing.
FLOAT_BRANCH_GOLDEN = {
    "SMTK": "5a0876f34f5c66bb3c769c0642dc05c274493b6e7866038696ce2e1dfa681125",
    "MEDS": "d8e16d5222062c3620e4a2d8aca6c99dfe2e4b796b4ebce6f7d00034c5d2bbf6",
    "JELD": "78515a6e7aa6e605fe28da95f85953fe38d1ff9cb61322c02c1eec19d00d8ee9",
    "SMX": "e57b07d2a6ecfc9edc53e840d6db515bc07790a4f7ef55e64a21bf9198bafd92",
}


@pytest.mark.parametrize("name", sorted(FLOAT_BRANCH_GOLDEN))
def test_NEGATIVE_the_float_branch_is_byte_identical_to_before(name):
    from tests import test_si_basis_math_2026_11_24 as T
    rec, doc = {"SMTK": lambda: (T._rec(), T._doc()), "MEDS": T._meds, "JELD": T._jeld,
                "SMX": lambda: (T._smx_rec(), T._smx_doc())}[name]()
    v = BM.verdict(rec, doc, T.TODAY)
    for f in v["filings"]:
        f.pop("copies")
        f.pop("same_day")
    # 2026-11-26 sishares §3.2 / §5.5: the new verdict keys and their two rows are dropped before hashing too
    for k in ("issuances", "share_counts", "float_fresh"):
        v.pop(k)
    # PIN MOVED 2026-11-27 (spec sicheck §3.4): the three new verdict keys are None on these names, then dropped too
    for k in ("lagged", "split_filings", "date_gap"):
        assert v.pop(k) is None, (name, k)
    v["rows"] = [r for r in v["rows"] if r["k"] not in (BM.ROW_SHARE_COUNTS, BM.ROW_SHARE_ISSUANCE)]
    got = hashlib.sha256(json.dumps(v, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()
    assert got == FLOAT_BRANCH_GOLDEN[name]


# ── [C8] `fell` reads the raised baseline and is NOT suppressed
def test_C8_a_cover_over_twice_the_newer_count_fires_fell_from_the_sec_side():
    covers = [{"as_of": "2026-11-03", "shares": 3000000, "form": "10-Q", "filed": "2026-11-05"}]
    yahoo = {"float_shares": 1667144, "shares_outstanding": 1200000, "as_of": "2026-11-25"}
    rec = whlr_rec(shares_outstanding=1000000)
    v = BM.verdict(rec, whlr_doc(covers=covers, yahoo=yahoo), TODAY)
    assert 1200000 <= 3000000 * SR.SUSPECT_MAX_SHARES_OUT_FRACTION
    assert v["fell"] == {"ratio": 2.5, "from_shares": 3000000, "from_asof": "2026-11-03", "from_source": "sec",
                         "to_shares": 1200000, "to_asof": "2026-11-25", "to_source": "yahoo", "to_form": None}
    f = _flag(v, BM.FLAG_COUNT_FELL)
    assert f["short"] == "❔ shares fell 2.5×"
    # PIN MOVED 2026-11-27 (spec sicheck §3.4 B4): WHLR's 1-for-6 on 10/30 is on file before the older count and
    # explains the fall, but no SEC cover dated before it corroborates → the flag stays and its text names the split
    assert f["text"] == ("❔ share count fell 2.5×: 1,200,000 (Yahoo, 11/25) vs 3,000,000 (11/3) — a 1-for-6 reverse "
                         "split on 10/30 is on file: the older count may already be adjusted for it, or a split the "
                         "splits read does not list is possible; the % shown is not adjusted for one "
                         "· charter filing 8-K Item 3.03/5.03 11/24")
    assert "no split on file" not in f["text"]
    assert v["status"] == "partial"


def test_C8_NEGATIVE_WHLR_has_no_fell():
    v = BM.verdict(whlr_rec(), whlr_doc(), TODAY)
    assert 2220906 > 1788532 * SR.SUSPECT_MAX_SHARES_OUT_FRACTION and v["fell"] is None


def test_C8_NEGATIVE_record_only_baseline_fell_exactly_as_before():
    yahoo = {"float_shares": 1667144, "shares_outstanding": 400000, "as_of": "2026-11-25"}
    v = BM.verdict(whlr_rec(), whlr_doc(covers=[], yahoo=yahoo), TODAY)
    assert v["fell"]["from_source"] == "record" and v["fell"]["from_shares"] == 978675
    # PIN MOVED 2026-11-27 (spec sicheck §3.4 B4): the on-file 10/30 split predates the record's 11/7 count and no
    # cover corroborates → the flag stays, its text names the split (never "no split on file")
    assert _flag(v, BM.FLAG_COUNT_FELL)["text"].startswith(
        "❔ share count fell 2.4×: 400,000 (Yahoo, 11/25) vs 978,675 (11/7) — a 1-for-6 reverse split on 10/30 is on "
        "file: the older count may already be adjusted for it")
