"""⛔ SSR — the exchanges' official short sale circuit breaker lists + the ONE worker (2026-11-24 branch; ask 2026-11-23).

Ajay 2026-11-23, verbatim: "No shorting at the bid (SEC short-sale restriction) Can we check or this for other stocks
too?"

Spec: scratchpad ssr/spec.md §3.3, §3.4, W2. The four files under tests/fixtures/ssr/ are VERBATIM exchange answers
(fetched 2026-11-23; the 11/23 Nasdaq file is its 04:15:15 pre-open edition). Every other body is built here and
named SYNTHETIC.

Harness: an autouse fixture replaces the module's outside-call seam (`SL._http`) with a RECORDING refuser and asserts
at teardown it was never called; it also installs a recording stand-in for `short_interest.ssr_corp` so no real
corporate-action read can run here. The in-memory collection implements exactly the operations the module may use
and FAILS on any other.
"""
from __future__ import annotations

import copy
import logging
import re
import sys
import threading
import types
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from catalysts.medical import reaction as R
from short_interest import biff_rows as BIFF
from short_interest import reg_sho as RS
from short_interest import ssr_lists as SL

BACKEND = Path(__file__).resolve().parents[1]
FIX = BACKEND / "tests" / "fixtures" / "ssr"
ET = ZoneInfo("America/New_York")
NASDAQ, NYSE = SL.SOURCES
D19, D20, D23, D24, D25 = (date(2026, 11, 19), date(2026, 11, 20), date(2026, 11, 23), date(2026, 11, 24),
                           date(2026, 11, 25))
MON_2209 = datetime(2026, 11, 23, 22, 9, tzinfo=ET)                # the evening he asked
MON_1400 = datetime(2026, 11, 23, 14, 0, tzinfo=ET)
FORBIDDEN_HEADER = re.compile(r"@|cheetah|pounce|ajay|kandakatla|chartmap|gmail", re.I)


# ═════════════════════════════════════════════ fakes
class StandIn:
    """The module's Mongo collection: find({"_id": {"$in": [...]}}, {"rows": 0}), find_one({"_id": x}),
    replace_one({"_id": x}, doc, upsert=True), create_index — and NOTHING else."""

    def __init__(self):
        self.docs = {}
        self.full_reads = []
        self.fail_writes = False

    def find(self, flt, projection=None):
        assert set(flt) == {"_id"} and set(flt["_id"]) == {"$in"}, flt
        assert projection == {"rows": 0}, projection
        ids = set(flt["_id"]["$in"])
        out = []
        for k, d in self.docs.items():
            if k in ids:
                d = copy.deepcopy(d)
                d.pop("rows", None)
                out.append(d)
        return out

    def find_one(self, flt):
        assert set(flt) == {"_id"}, flt
        self.full_reads.append(flt["_id"])
        d = self.docs.get(flt["_id"])
        return copy.deepcopy(d) if d else None

    def replace_one(self, flt, doc, upsert=False):
        assert upsert is True and flt == {"_id": doc["_id"]}, (flt, upsert)
        if self.fail_writes:
            raise RuntimeError("synthetic: Mongo write refused")
        self.docs[doc["_id"]] = copy.deepcopy(doc)

    def create_index(self, keys, **kw):
        assert keys == [("kind", 1), ("source", 1), ("file_date", -1)], keys
        return "noop"

    def __getattr__(self, name):
        raise AssertionError("ssr_lists used a collection operation outside its four: %s" % name)


class Resp:
    def __init__(self, status_code, content=b"", headers=None):
        self.status_code = status_code
        self.content = content if isinstance(content, bytes) else content.encode("utf-8")
        self.headers = headers or {}


class ReadTimeout(Exception):
    """SYNTHETIC stand-in for requests' timeout (the module reads the class name)."""


class FakeHTTP:
    def __init__(self, answers=None, on_call=None):
        self.answers = dict(answers or {})
        self.urls = []
        self.kwargs = []
        self.on_call = on_call

    def __call__(self, url, **kw):
        self.urls.append(url)
        self.kwargs.append(kw)
        if self.on_call:
            self.on_call(url, kw)
        a = self.answers.get(url)
        if a is None:
            raise LookupError("no answer for %s" % url)
        if isinstance(a, BaseException):
            raise a
        return a


class FakeCorp:
    """The FROZEN `ssr_corp.refresh_due(coll, days, now_et, *, http=None)` signature, recording."""

    def __init__(self, raises=None, log=None):
        self.calls = []
        self.raises = raises
        self.log = log

    def refresh_due(self, coll, days, now_et, *, http=None):
        self.calls.append((coll, list(days), now_et, http))
        if self.log is not None:
            self.log.append("corp")
        if self.raises:
            raise self.raises
        return {"ran": ["synthetic"]}


def _bytes(name):
    return (FIX / name).read_bytes()


def url(src, d):
    return SL.source_url(src, d)


# VERBATIM headers of the captures (ssr/*.hdr, 2026-11-23)
ANSWERS = {
    ("nasdaq", D20): Resp(200, _bytes("nasdaq_shorthalts20261120.txt"),
                          {"ETag": '"cfebd2633679dd1:0"', "Last-Modified": "Fri, 20 Nov 2026 21:30:40 GMT"}),
    ("nasdaq", D23): Resp(200, _bytes("nasdaq_shorthalts20261123_preopen.txt"),
                          {"ETag": '"8ae4a42c2b7bdd1:0"', "Last-Modified": "Mon, 23 Nov 2026 09:15:25 GMT"}),
    ("nyse", D20): Resp(200, _bytes("nyse_ssr20261120.xls"),
                        {"ETag": '"6b00ff90-fa00"', "Last-Modified": "Sat, 21 Nov 2026 02:18:56 GMT"}),
    ("nyse", D23): Resp(200, _bytes("nyse_ssr20261123.xls"),
                        {"ETag": '"6b04e32e-6600"', "Last-Modified": "Tue, 24 Nov 2026 01:06:54 GMT"}),
}
NASDAQ_302 = Resp(302, b"", {"Location": "/Trader.aspx?id=http404"})     # SYNTHETIC copy of the measured answer
NYSE_404 = Resp(404, b"<html>404 Not Found</html>")                      # SYNTHETIC copy of the measured answer


def answers(*keys):
    return {url(SL.source(k), d): ANSWERS[(k, d)] for k, d in keys}


def hold(coll, *keys, now=MON_2209):
    """Store the REAL fixture files through the module's own refresh_one (the stored doc shape)."""
    http = FakeHTTP(answers(*keys))
    for k, d in keys:
        st = SL.refresh_one(SL.source(k), d, coll, now, http=http)
        assert st["result"] == "found", st
    return coll


def synthetic_nasdaq(d: date, rows, stamp_hms="163004") -> str:
    """SYNTHETIC Nasdaq file (CRLF, the measured shape)."""
    return "\r\n".join([SL.NASDAQ_HEADER] + list(rows) + [d.strftime("%Y%m%d") + stamp_hms]) + "\r\n"


@pytest.fixture(autouse=True)
def harness(monkeypatch):
    calls = []

    def recorder(u=None, *a, **k):
        calls.append(u)
        raise RuntimeError("ssr_lists outside calls are refused in this file")
    monkeypatch.setattr(SL, "_http", recorder)
    monkeypatch.setattr(SL, "_bg", {"running": False, "last_start": None, "thread": None})
    stub = types.ModuleType("short_interest.ssr_corp")
    stub.calls = []
    stub.refresh_due = lambda coll, days, now_et, *, http=None: stub.calls.append((list(days), now_et)) or {}
    monkeypatch.setitem(sys.modules, "short_interest.ssr_corp", stub)
    SL._reset_cache()
    yield {"calls": calls, "corp": stub}
    t = SL._bg.get("thread")
    if t is not None:
        t.join(5)
    SL._reset_cache()
    assert calls == [], "an outside call reached the module seam: %s" % calls


# ═════════════════════════════════════════════ registry
def test_registry_is_the_spec():
    assert SL.SSR_COLL == "ssr_rule_201"
    assert [s["key"] for s in SL.SOURCES] == ["nasdaq", "nyse"]
    assert NASDAQ["no_list"] == RS.NO_LIST_NASDAQ_302 and NYSE["no_list"] == SL.NO_LIST_NYSE_404
    assert NASDAQ["first_hm"] == (4, 20) and NYSE["first_hm"] == (20, 10)
    assert NASDAQ["carries_prior_day"] is True and NYSE["carries_prior_day"] is False
    assert SL.RETRY_AFTER_SEC == SL.SL_RETRY_AFTER_SEC == 20
    assert SL.Malformed is RS.Malformed
    assert url(NASDAQ, D23) == "https://www.nasdaqtrader.com/dynamic/symdir/shorthalts/shorthalts20261123.txt"
    assert url(NYSE, D23) == ("https://ftp.nyse.com/NYSEGroupSSRCircuitBreakers/NYSEGroupSSRCircuitBreakers_2026/"
                              "NYSEGroupSSRCircuitBreakers_202611/NYSEGroupSSRCircuitBreakers20261123.xls")


def test_NEGATIVE_no_project_name_and_no_email_in_the_headers():
    assert not FORBIDDEN_HEADER.search(repr(SL.HTTP_HEADERS))


def test_NEGATIVE_the_module_never_imports_ssr_py():
    src = Path(SL.__file__).read_text()
    assert not re.search(r"^\s*(from short_interest import ssr\b|import short_interest\.ssr\b|from short_interest\.ssr "
                         r"import|from \. import ssr\b)", src, re.M)
    assert "from short_interest import ssr_corp" not in src                   # the corp read is a fenced lazy import


# ═════════════════════════════════════════════ parse_nasdaq
def test_parse_nasdaq_the_real_11_20_final_edition():
    rows, stamp, skipped = SL.parse_nasdaq(_bytes("nasdaq_shorthalts20261120.txt").decode(), D20)
    assert len(rows) == 1635 and stamp == "20261120163031" and skipped == 0
    by_day = {}
    for r in rows:
        by_day[r[1]] = by_day.get(r[1], 0) + 1
    assert by_day == {"2026-11-19": 549, "2026-11-20": 1086}
    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1
    assert sum(1 for n in counts.values() if n == 2) == 261
    assert ("AKAN", "2026-11-19", "09:30:47", "R") in rows
    assert ("CSAI", "2026-11-19", "09:30:00", "R") in rows                   # the quoted-comma name read as ONE cell
    assert {r[3] for r in rows} == {"R", "Q"}                                 # stored raw, never decoded


def test_parse_nasdaq_the_real_11_23_pre_open_edition_is_not_final():
    rows, stamp, skipped = SL.parse_nasdaq(_bytes("nasdaq_shorthalts20261123_preopen.txt").decode(), D23)
    assert len(rows) == 1092 and stamp == "20261123041515" and skipped == 0
    assert {r[1] for r in rows} == {"2026-11-20"}
    assert ("GP", "2026-11-20", "09:45:36", "R") in rows
    assert SL.is_final(NASDAQ, {"stamp": stamp, "file_date": "2026-11-23"}) is False
    assert SL.is_final(NASDAQ, {"stamp": "20261120163031", "file_date": "2026-11-20"}) is True


def test_final_reads_the_half_day_close():
    assert SL.is_final(NASDAQ, {"stamp": "20261127133000", "file_date": "2026-11-27"}) is True
    assert SL.is_final(NASDAQ, {"stamp": "20261127125900", "file_date": "2026-11-27"}) is False
    assert SL.is_final(NASDAQ, {"stamp": "20261124163000", "file_date": "2026-11-23"}) is False   # another day's stamp
    assert SL.is_final(NASDAQ, None) is False
    assert SL.is_final(NYSE, {"file_date": "2026-11-23"}) is True


def test_NEGATIVE_parse_nasdaq_header_mismatch():
    text = _bytes("nasdaq_shorthalts20261120.txt").decode().replace("Trigger Time", "Trigger Stamp", 1)
    with pytest.raises(RS.Malformed, match="header"):
        SL.parse_nasdaq(text, D20)


def test_parse_nasdaq_header_cells_are_case_insensitive():
    text = _bytes("nasdaq_shorthalts20261120.txt").decode().replace("Trigger Time", "TRIGGER TIME", 1)
    assert len(SL.parse_nasdaq(text, D20)[0]) == 1635


def test_NEGATIVE_parse_nasdaq_trailer_missing():
    text = _bytes("nasdaq_shorthalts20261120.txt").decode().rstrip().rsplit("\r\n", 1)[0] + "\r\n"
    with pytest.raises(RS.Malformed, match="trailer"):
        SL.parse_nasdaq(text, D20)


def test_NEGATIVE_parse_nasdaq_trailer_of_another_date():
    with pytest.raises(RS.Malformed, match="trailer"):
        SL.parse_nasdaq(_bytes("nasdaq_shorthalts20261120.txt").decode(), D23)


def test_NEGATIVE_parse_nasdaq_an_html_body():
    html = "<html><head><title>Object moved</title></head><body><h2>Object moved</h2></body></html>"
    with pytest.raises(RS.Malformed):
        SL.parse_nasdaq(html, D23)


def test_NEGATIVE_parse_nasdaq_not_text_and_oversize():
    with pytest.raises(RS.Malformed):
        SL.parse_nasdaq(b"bytes", D23)
    with pytest.raises(RS.Malformed, match="oversize"):
        SL.parse_nasdaq("x" * (SL.SL_MAX_BYTES + 1), D23)


def test_parse_nasdaq_skips_and_counts_bad_rows():
    """SYNTHETIC rows: a short row, a bad time, a date outside (prev day, day) — skipped and counted."""
    text = synthetic_nasdaq(D23, ["AAA,Alpha,R,11/23/2026 9:31:00 AM", "BBB,Beta,R",
                                  "CCC,Gamma,Q,23/11/2026 9:31:00", "DDD,Delta,Q,11/18/2026 9:31:00 AM",
                                  "EEE,Eps,Q,11/20/2026 3:59:59 PM"])
    rows, stamp, skipped = SL.parse_nasdaq(text, D23)
    assert rows == [("AAA", "2026-11-23", "09:31:00", "R"), ("EEE", "2026-11-20", "15:59:59", "Q")]
    assert skipped == 3 and stamp == "20261123163004"


def test_NEGATIVE_parse_nasdaq_more_than_max_skipped_rows():
    bad = ["X%02d,Bad,R,not a time" % i for i in range(SL.SL_MAX_SKIPPED_ROWS + 1)]
    with pytest.raises(RS.Malformed, match="skipped"):
        SL.parse_nasdaq(synthetic_nasdaq(D23, ["AAA,Alpha,R,11/23/2026 9:31:00 AM"] + bad), D23)


def test_NEGATIVE_parse_nasdaq_every_row_of_another_day():
    with pytest.raises(RS.Malformed):
        SL.parse_nasdaq(synthetic_nasdaq(D23, ["AAA,Alpha,R,11/10/2026 9:31:00 AM"]), D23)


def test_parse_nasdaq_a_file_with_no_rows_is_an_empty_list():
    assert SL.parse_nasdaq(synthetic_nasdaq(D23, []), D23) == ([], "20261123163004", 0)


# ═════════════════════════════════════════════ parse_nyse
@pytest.mark.parametrize("name,d,n", [("nyse_ssr20261120.xls", D20, 330), ("nyse_ssr20261123.xls", D23, 114)])
def test_parse_nyse_the_real_files(name, d, n):
    rows, skipped = SL.parse_nyse(_bytes(name), d)
    assert len(rows) == n and skipped == 0
    assert {r[1] for r in rows} == {d.isoformat()}
    assert {r[3] for r in rows} <= {"NYSE", "NYSE American", "NYSE Arca"}
    assert {"NYSE American", "NYSE Arca"} <= {r[3] for r in rows}             # MKT and P mapped
    # the exchange confirms the window: deactivation = the 2nd trading day after the trigger, house calendar
    assert {r[4] for r in rows} == {R.next_market_day(R.next_market_day(d)).isoformat()}


def test_parse_nyse_first_rows_and_spellings():
    rows, _ = SL.parse_nyse(_bytes("nyse_ssr20261123.xls"), D23)
    assert rows[0] == ("AGL", "2026-11-23", "09:37:47", "NYSE", "2026-11-25")
    rows20, _ = SL.parse_nyse(_bytes("nyse_ssr20261120.xls"), D20)
    assert rows20[0] == ("AAC.WS", "2026-11-20", "15:38:33", "NYSE", "2026-11-24")   # NYSE's "AAC WS", normalised


def test_NEGATIVE_parse_nyse_a_file_of_another_date_is_malformed():
    with pytest.raises(RS.Malformed):
        SL.parse_nyse(_bytes("nyse_ssr20261120.xls"), D23)


def test_NEGATIVE_parse_nyse_a_wrong_header(monkeypatch):
    grid = BIFF.read_rows(_bytes("nyse_ssr20261123.xls"))
    grid[0][1] = "Symbol"                                                     # SYNTHETIC
    monkeypatch.setattr(BIFF, "read_rows", lambda data: grid)
    with pytest.raises(RS.Malformed, match="header"):
        SL.parse_nyse(_bytes("nyse_ssr20261123.xls"), D23)


@pytest.mark.parametrize("cut", [100, 5000, 20000])
def test_NEGATIVE_parse_nyse_a_reader_error_is_malformed_never_empty(cut):
    with pytest.raises(RS.Malformed, match="reader"):
        SL.parse_nyse(_bytes("nyse_ssr20261123.xls")[:cut], D23)


def test_parse_nyse_skips_and_counts_other_states_and_bad_cells(monkeypatch):
    grid = BIFF.read_rows(_bytes("nyse_ssr20261123.xls"))
    grid[1][4] = "D"                                                          # SYNTHETIC: an unseen SSR State
    grid[2][5] = "9:5"                                                        # SYNTHETIC: a bad time
    grid[3][6] = None                                                         # SYNTHETIC: a missing cell
    grid[4][2] = None                                                         # SYNTHETIC: a blank NAME is not a skip
    monkeypatch.setattr(BIFF, "read_rows", lambda data: grid)
    rows, skipped = SL.parse_nyse(b"x", D23)
    assert skipped == 3 and len(rows) == 111
    assert "AGL" not in {r[0] for r in rows}
    exch = {r[0]: r[3] for r in rows}
    assert exch.get("ZOAR") == "NYSE American" and exch.get("ZSL") == "NYSE Arca"


def test_parse_nyse_an_unseen_exchange_code_prints_as_itself(monkeypatch):
    grid = BIFF.read_rows(_bytes("nyse_ssr20261123.xls"))
    grid[1][3] = "XYZ"                                                        # SYNTHETIC
    monkeypatch.setattr(BIFF, "read_rows", lambda data: grid)
    rows, _ = SL.parse_nyse(b"x", D23)
    assert rows[0][3] == "XYZ"


def test_NEGATIVE_parse_nyse_more_than_max_skipped_rows(monkeypatch):
    grid = BIFF.read_rows(_bytes("nyse_ssr20261123.xls"))
    for r in grid[1: SL.SL_MAX_SKIPPED_ROWS + 2]:
        r[4] = "D"
    monkeypatch.setattr(BIFF, "read_rows", lambda data: grid)
    with pytest.raises(RS.Malformed, match="skipped"):
        SL.parse_nyse(b"x", D23)


# ═════════════════════════════════════════════ fetch
def test_fetch_200_found_with_the_request_contract():
    http = FakeHTTP(answers(("nasdaq", D20)))
    r = SL.fetch(NASDAQ, D20, http=http)
    assert r["result"] == "found" and len(r["rows"]) == 1635 and r["stamp"] == "20261120163031"
    assert r["etag"] == '"cfebd2633679dd1:0"' and r["skipped"] == 0 and r["url"] == url(NASDAQ, D20)
    kw = http.kwargs[0]
    assert kw["allow_redirects"] is False and kw["timeout"] == SL.SL_HTTP_TIMEOUT_SEC
    assert kw["headers"] == SL.HTTP_HEADERS                                   # no If-None-Match without an etag
    assert "If-None-Match" not in kw["headers"]


def test_fetch_nyse_found_reads_the_edition_from_last_modified():
    r = SL.fetch(NYSE, D23, http=FakeHTTP(answers(("nyse", D23))))
    assert r["result"] == "found" and len(r["rows"]) == 114
    assert r["stamp"] == "20261123200654"                                     # 01:06:54 GMT = 20:06:54 ET


def test_fetch_sends_if_none_match_only_with_an_etag_and_304_is_unchanged():
    http = FakeHTTP({url(NASDAQ, D23): Resp(304)})
    r = SL.fetch(NASDAQ, D23, http=http, etag='"8ae4a42c2b7bdd1:0"')
    assert r["result"] == "unchanged"
    assert http.kwargs[0]["headers"] == dict(SL.HTTP_HEADERS, **{"If-None-Match": '"8ae4a42c2b7bdd1:0"'})


def test_fetch_nasdaq_302_to_http404_is_missing():
    assert SL.fetch(NASDAQ, D24, http=FakeHTTP({url(NASDAQ, D24): NASDAQ_302}))["result"] == "missing"


def test_NEGATIVE_fetch_nasdaq_302_elsewhere_is_an_error():
    r = SL.fetch(NASDAQ, D24, http=FakeHTTP({url(NASDAQ, D24): Resp(302, b"", {"Location": "/login"})}))
    assert r == {"result": "error", "error": "redirect"}


def test_fetch_nyse_404_is_missing():
    assert SL.fetch(NYSE, D24, http=FakeHTTP({url(NYSE, D24): NYSE_404}))["result"] == "missing"


@pytest.mark.parametrize("src,resp,err", [
    (NYSE, Resp(302, b"", {"Location": "/Trader.aspx?id=http404"}), "redirect"),
    (NYSE, Resp(403, b"<Code>AccessDenied</Code>"), "http_403"),
    (NASDAQ, Resp(403), "http_403"),
    (NASDAQ, Resp(500), "http_500"),
    (NYSE, Resp(500), "http_500"),
    (NASDAQ, Resp(404), "unseen_404"),
])
def test_NEGATIVE_fetch_other_answers_are_errors(src, resp, err):
    assert SL.fetch(src, D24, http=FakeHTTP({url(src, D24): resp})) == {"result": "error", "error": err}


def test_NEGATIVE_fetch_timeout_and_exception_are_errors_never_raised():
    assert SL.fetch(NASDAQ, D24, http=FakeHTTP({url(NASDAQ, D24): ReadTimeout("t")})) == {"result": "error",
                                                                                         "error": "timeout"}
    assert SL.fetch(NYSE, D24, http=FakeHTTP({url(NYSE, D24): OSError("x")})) == {"result": "error",
                                                                                 "error": "exception"}


def test_NEGATIVE_fetch_a_200_html_body_is_malformed_never_an_empty_list():
    html = b"<html><body>Service Unavailable</body></html>" + b" " * 600
    assert SL.fetch(NASDAQ, D23, http=FakeHTTP({url(NASDAQ, D23): Resp(200, html)}))["error"] == "malformed"
    assert SL.fetch(NYSE, D23, http=FakeHTTP({url(NYSE, D23): Resp(200, html)}))["error"] == "malformed"


def test_NEGATIVE_fetch_an_oversize_body_is_malformed():
    big = Resp(200, b"x" * (SL.SL_MAX_BYTES + 1))
    assert SL.fetch(NYSE, D23, http=FakeHTTP({url(NYSE, D23): big}))["error"] == "malformed"


# ═════════════════════════════════════════════ calendar
@pytest.mark.parametrize("now,want", [
    (MON_2209, [D20, D23]),
    (datetime(2026, 11, 24, 3, 0, tzinfo=ET), [D23, D24]),
    (datetime(2026, 11, 26, 12, 0, tzinfo=ET), [D24, D25]),                   # Thanksgiving: closed
    (datetime(2026, 11, 28, 12, 0, tzinfo=ET), [D25, date(2026, 11, 27)]),    # Saturday after the half day
    (datetime(2026, 11, 22, 9, 0, tzinfo=ET), [date(2026, 11, 19), D20]),     # Sunday
])
def test_file_dates(now, want):
    assert SL.file_dates(now) == want


# ═════════════════════════════════════════════ worker
def test_the_state_doc_is_written_before_the_first_outside_call():
    coll = StandIn()
    seen = []

    def on_call(u, kw):
        sid = "state|nasdaq|2026-11-23" if "shorthalts20261123" in u else None
        if sid:
            seen.append(coll.docs.get(sid, {}).get("result"))
    http = FakeHTTP(answers(("nasdaq", D23)), on_call=on_call)
    st = SL.refresh_one(NASDAQ, D23, coll, MON_2209, http=http)
    assert seen == ["running"] and st["result"] == "found"
    doc = coll.docs["list|nasdaq|2026-11-23"]
    assert doc["kind"] == "list" and doc["n"] == 1092 and doc["final"] is False
    assert doc["stamp"] == "20261123041515" and doc["editions"] == ["20261123041515"]
    assert doc["rev"] == "20261123041515|1092" and doc["etag"] == '"8ae4a42c2b7bdd1:0"'
    assert doc["rows"][0] == list(SL.parse_nasdaq(_bytes("nasdaq_shorthalts20261123_preopen.txt").decode(),
                                                  D23)[0][0])
    assert coll.docs["state|nasdaq|2026-11-23"]["result"] == "found"


def test_NEGATIVE_a_refused_state_write_abandons_before_any_call():
    coll = StandIn()
    coll.fail_writes = True
    http = FakeHTTP(answers(("nasdaq", D23)))
    assert SL.refresh_one(NASDAQ, D23, coll, MON_2209, http=http) is None
    assert http.urls == []


def test_a_full_round_reads_every_due_file_then_the_corp_job_last():
    coll = StandIn()
    order = []
    http = FakeHTTP(answers(("nasdaq", D20), ("nasdaq", D23), ("nyse", D20), ("nyse", D23)),
                    on_call=lambda u, kw: order.append("list"))
    corp = FakeCorp(log=order)
    out = SL.refresh_due(coll, MON_2209, http=http, corp=corp)
    assert out["calls"] == 4 and sorted(out["ran"]) == ["nasdaq|2026-11-20", "nasdaq|2026-11-23",
                                                         "nyse|2026-11-20", "nyse|2026-11-23"]
    assert order == ["list"] * 4 + ["corp"]
    assert corp.calls == [(coll, [D20, D23], MON_2209, http)]
    assert out["corp"] == {"ran": ["synthetic"]}
    for c in http.kwargs:                                                     # every list call: the house headers
        assert c["headers"]["User-Agent"] == SL.HTTP_HEADERS["User-Agent"]
        assert not FORBIDDEN_HEADER.search(repr(c["headers"]))


def test_NEGATIVE_zero_list_calls_when_both_sources_are_final_for_both_file_dates():
    coll = StandIn()
    hold(coll, ("nasdaq", D20), ("nyse", D20), ("nyse", D23))
    final23 = synthetic_nasdaq(D23, ["GP,GreenPower,R,11/23/2026 1:43:10 PM"])
    SL.refresh_one(NASDAQ, D23, coll, MON_2209, http=FakeHTTP({url(NASDAQ, D23): Resp(200, final23)}))
    assert all(d["final"] for k, d in coll.docs.items() if k.startswith("list|"))
    http = FakeHTTP()
    corp = FakeCorp()
    out = SL.refresh_due(coll, MON_2209 + timedelta(hours=1), http=http, corp=corp)
    assert out["calls"] == 0 and http.urls == [] and out["ran"] == []
    assert len(corp.calls) == 1                                               # the corp job still runs (its own throttle)


def test_NEGATIVE_nothing_is_due_before_the_first_publish_clock():
    loaded = SL.load(StandIn(), datetime(2026, 11, 24, 4, 19, tzinfo=ET))
    assert SL.is_due(NASDAQ, D24, loaded, datetime(2026, 11, 24, 4, 19, tzinfo=ET)) is False
    assert SL.is_due(NASDAQ, D24, loaded, datetime(2026, 11, 24, 4, 20, tzinfo=ET)) is True
    assert SL.is_due(NYSE, D24, loaded, datetime(2026, 11, 24, 20, 9, tzinfo=ET)) is False
    assert SL.is_due(NYSE, D24, loaded, datetime(2026, 11, 24, 20, 10, tzinfo=ET)) is True
    assert SL.is_due(NYSE, D23, loaded, datetime(2026, 11, 24, 4, 19, tzinfo=ET)) is True   # the earlier file


def test_retry_waits_error_then_long():
    coll = StandIn()
    t0 = MON_2209
    http = FakeHTTP({url(NASDAQ, D23): Resp(500)})
    SL.refresh_one(NASDAQ, D23, coll, t0, http=http)
    st = coll.docs["state|nasdaq|2026-11-23"]
    assert st["result"] == "error" and st["errors"] == 1 and st["error"] == "http_500"

    def due(at):
        return SL.is_due(NASDAQ, D23, SL.load(coll, at), at)
    assert due(t0 + timedelta(minutes=SL.SL_ERROR_RETRY_MIN - 1)) is False
    t1 = t0 + timedelta(minutes=SL.SL_ERROR_RETRY_MIN)
    assert due(t1) is True
    SL.refresh_one(NASDAQ, D23, coll, t1, http=http)
    assert coll.docs["state|nasdaq|2026-11-23"]["errors"] == SL.SL_ERROR_STRIKES
    assert due(t1 + timedelta(minutes=SL.SL_ERROR_RETRY_MIN)) is False          # strikes reached → the long wait
    assert due(t1 + timedelta(minutes=SL.SL_RETRY_MIN)) is True
    SL.refresh_one(NASDAQ, D23, coll, t1 + timedelta(minutes=SL.SL_RETRY_MIN), http=FakeHTTP(answers(("nasdaq", D23))))
    assert coll.docs["state|nasdaq|2026-11-23"]["errors"] == 0


def test_missing_waits_the_long_retry():
    coll = StandIn()
    at = datetime(2026, 11, 24, 4, 25, tzinfo=ET)
    SL.refresh_one(NASDAQ, D24, coll, at, http=FakeHTTP({url(NASDAQ, D24): NASDAQ_302}))
    st = coll.docs["state|nasdaq|2026-11-24"]
    assert st["result"] == "missing" and st["errors"] == 0 and "list|nasdaq|2026-11-24" not in coll.docs
    lt = at + timedelta(minutes=SL.SL_RETRY_MIN - 1)
    assert SL.is_due(NASDAQ, D24, SL.load(coll, lt), lt) is False
    lt = at + timedelta(minutes=SL.SL_RETRY_MIN)
    assert SL.is_due(NASDAQ, D24, SL.load(coll, lt), lt) is True


def test_NEGATIVE_the_measured_trap_a_04_15_edition_read_at_22_10_is_not_final_and_stays_due():
    coll = StandIn()
    at = datetime(2026, 11, 23, 22, 10, tzinfo=ET)
    hold(coll, ("nasdaq", D23), now=at)
    assert coll.docs["list|nasdaq|2026-11-23"]["final"] is False
    later = at + timedelta(minutes=SL.SL_RETRY_MIN)
    assert SL.is_due(NASDAQ, D23, SL.load(coll, later), later) is True
    assert SL.any_due(SL.load(coll, later), later) is True


def test_a_newer_edition_replaces_the_doc_and_appends_to_editions():
    coll = StandIn()
    hold(coll, ("nasdaq", D23), now=datetime(2026, 11, 23, 9, 0, tzinfo=ET))
    first = coll.docs["list|nasdaq|2026-11-23"]
    pre = _bytes("nasdaq_shorthalts20261123_preopen.txt").decode().rstrip().rsplit("\r\n", 1)[0]
    final = pre + "\r\nNEWX,New Name Inc,R,11/23/2026 10:01:02 AM\r\n20261123163004\r\n"   # SYNTHETIC 16:30 edition
    st = SL.refresh_one(NASDAQ, D23, coll, MON_2209,
                        http=FakeHTTP({url(NASDAQ, D23): Resp(200, final, {"ETag": '"new"'})}))
    assert st["result"] == "found"
    doc = coll.docs["list|nasdaq|2026-11-23"]
    assert doc["editions"] == ["20261123041515", "20261123163004"] and doc["final"] is True
    assert doc["n"] == 1093 and doc["rev"] != first["rev"] and doc["etag"] == '"new"'
    assert doc["first_fetched_at"] == first["first_fetched_at"] and doc["fetched_at"] != first["fetched_at"]
    rows = SL.rows_for(SL.load(coll, MON_2209), "NEWX")
    assert [(r["trigger_date"], r["trigger_time"]) for r in rows] == [("2026-11-23", "10:01:02")]


def test_NEGATIVE_an_older_edition_never_replaces_a_newer_one():
    coll = StandIn()
    final = synthetic_nasdaq(D23, ["NEWX,New Name Inc,R,11/23/2026 10:01:02 AM"])
    SL.refresh_one(NASDAQ, D23, coll, MON_2209, http=FakeHTTP({url(NASDAQ, D23): Resp(200, final)}))
    before = copy.deepcopy(coll.docs["list|nasdaq|2026-11-23"])
    st = SL.refresh_one(NASDAQ, D23, coll, MON_2209 + timedelta(minutes=40), http=FakeHTTP(answers(("nasdaq", D23))))
    assert st["result"] == "older_edition" and st["errors"] == 0
    assert coll.docs["list|nasdaq|2026-11-23"] == before


def test_a_held_etag_is_sent_and_304_keeps_the_doc():
    coll = StandIn()
    hold(coll, ("nasdaq", D23), now=datetime(2026, 11, 23, 9, 0, tzinfo=ET))
    before = copy.deepcopy(coll.docs["list|nasdaq|2026-11-23"])
    http = FakeHTTP({url(NASDAQ, D23): Resp(304)})
    st = SL.refresh_one(NASDAQ, D23, coll, MON_2209, http=http)
    assert st["result"] == "unchanged" and coll.docs["list|nasdaq|2026-11-23"] == before
    assert http.kwargs[0]["headers"]["If-None-Match"] == '"8ae4a42c2b7bdd1:0"'


def test_NEGATIVE_a_304_with_nothing_held_is_an_error():
    st = SL.refresh_one(NASDAQ, D23, StandIn(), MON_2209, http=FakeHTTP({url(NASDAQ, D23): Resp(304)}))
    assert st["result"] == "error" and st["error"] == "unexpected_304"


def test_NEGATIVE_a_raising_corp_refresh_never_fails_the_list_refresh(caplog):
    coll = StandIn()
    http = FakeHTTP(answers(("nasdaq", D20), ("nasdaq", D23), ("nyse", D20), ("nyse", D23)))
    corp = FakeCorp(raises=RuntimeError("synthetic corp failure"))
    with caplog.at_level(logging.WARNING, logger="short_interest.ssr_lists"):
        out = SL.refresh_due(coll, MON_2209, http=http, corp=corp)
    assert out["calls"] == 4 and out["corp"] is None and len(corp.calls) == 1
    assert {k for k in coll.docs if k.startswith("list|")} == {"list|nasdaq|2026-11-20", "list|nasdaq|2026-11-23",
                                                              "list|nyse|2026-11-20", "list|nyse|2026-11-23"}
    assert sum("corporate-action read did not run" in r.getMessage() for r in caplog.records) == 1


def test_NEGATIVE_an_unimportable_ssr_corp_never_fails_the_list_refresh(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "short_interest.ssr_corp", None)         # import → ModuleNotFoundError
    coll = StandIn()
    http = FakeHTTP(answers(("nasdaq", D20), ("nasdaq", D23), ("nyse", D20), ("nyse", D23)))
    with caplog.at_level(logging.WARNING, logger="short_interest.ssr_lists"):
        out = SL.refresh_due(coll, MON_2209, http=http)
    assert out["calls"] == 4 and out["corp"] is None
    assert len([k for k in coll.docs if k.startswith("list|")]) == 4
    msgs = [r.getMessage() for r in caplog.records if "corporate-action" in r.getMessage()]
    assert len(msgs) == 1 and "ModuleNotFoundError" in msgs[0]


def test_corp_none_reaches_the_real_module_by_a_lazy_import(harness):
    out = SL.refresh_due(StandIn(), MON_2209, http=FakeHTTP(answers(("nasdaq", D20), ("nasdaq", D23),
                                                                     ("nyse", D20), ("nyse", D23))))
    assert harness["corp"].calls == [([D20, D23], MON_2209)] and out["corp"] == {}


def test_NEGATIVE_a_failing_list_round_still_runs_the_corp_job():
    class Broken(StandIn):
        def find(self, flt, projection=None):
            raise RuntimeError("synthetic: Mongo read refused")
    corp = FakeCorp()
    out = SL.refresh_due(Broken(), MON_2209, http=FakeHTTP(), corp=corp)
    assert out["calls"] == 0 and len(corp.calls) == 1


def test_kick_refresh_floor_starts_one_worker_inside_kick_min_sec(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(SL, "_mono", lambda: clock["t"])
    ran = []
    monkeypatch.setattr(SL, "refresh_due", lambda coll, now_et=None, http=None: ran.append(1))
    assert SL.kick_refresh(StandIn(), MON_2209, http=FakeHTTP()) is True
    SL._bg["thread"].join(5)
    assert SL.worker_running() is False
    clock["t"] += SL.SL_KICK_MIN_SEC - 1
    assert SL.kick_refresh(StandIn(), MON_2209, http=FakeHTTP()) is False
    assert ran == [1]
    clock["t"] += 1
    assert SL.kick_refresh(StandIn(), MON_2209, http=FakeHTTP()) is True
    SL._bg["thread"].join(5)
    assert ran == [1, 1]


def test_kick_refresh_is_single_flight(monkeypatch):
    gate = threading.Event()
    ran = []

    def slow(coll, now_et=None, http=None):
        ran.append(1)
        gate.wait(5)
    monkeypatch.setattr(SL, "refresh_due", slow)
    assert SL.kick_refresh(StandIn(), MON_2209, http=FakeHTTP()) is True
    assert SL.worker_running() is True
    monkeypatch.setattr(SL, "_mono", lambda: 10 ** 9)                         # past the floor: only the flag refuses
    assert SL.kick_refresh(StandIn(), MON_2209, http=FakeHTTP()) is False
    gate.set()
    SL._bg["thread"].join(5)
    assert ran == [1] and SL.worker_running() is False


def test_NEGATIVE_a_thread_that_cannot_start_resets_the_flag(monkeypatch):
    class NoThread:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")
    monkeypatch.setattr(SL.threading, "Thread", NoThread)
    assert SL.kick_refresh(StandIn(), MON_2209, http=FakeHTTP()) is False
    assert SL._bg["running"] is False and SL._bg["last_start"] is None


def test_kicked_worker_runs_the_real_round_end_to_end():
    coll = StandIn()
    http = FakeHTTP(answers(("nasdaq", D20), ("nasdaq", D23), ("nyse", D20), ("nyse", D23)))
    assert SL.kick_refresh(coll, MON_2209, http=http) is True
    SL._bg["thread"].join(10)
    assert len(http.urls) == 4 and len([k for k in coll.docs if k.startswith("list|")]) == 4


# ═════════════════════════════════════════════ load + the decode cache
def test_load_reads_only_file_dates_and_decodes_once_per_rev():
    coll = StandIn()
    hold(coll, ("nasdaq", D20), ("nasdaq", D23), ("nyse", D23))
    coll.docs["list|nasdaq|2026-11-19"] = {"_id": "list|nasdaq|2026-11-19", "kind": "list", "source": "nasdaq",
                                           "file_date": "2026-11-19", "rows": [["OLDX", "2026-11-19", "09:30:00",
                                                                                "R"]], "rev": "x|1"}
    coll.full_reads.clear()
    a = SL.load(coll, MON_2209)
    assert a["read"] is True and a["days"] == ["2026-11-20", "2026-11-23"]
    assert set(a["lists"]) == {("nasdaq", "2026-11-20"), ("nasdaq", "2026-11-23"), ("nyse", "2026-11-23")}
    assert "rows" not in a["lists"][("nasdaq", "2026-11-20")]
    assert SL.rows_for(a, "OLDX") == []                                       # a file outside file_dates is not read
    assert sorted(coll.full_reads) == ["list|nasdaq|2026-11-20", "list|nasdaq|2026-11-23", "list|nyse|2026-11-23"]
    coll.full_reads.clear()
    SL.load(coll, MON_2209)
    assert coll.full_reads == []                                              # same revs → no re-decode
    SL.refresh_one(NASDAQ, D23, coll, MON_2209,
                   http=FakeHTTP({url(NASDAQ, D23): Resp(200, synthetic_nasdaq(D23, ["NEWX,N,R,11/23/2026 "
                                                                                      "10:00:00 AM"]))}))
    coll.full_reads.clear()
    b = SL.load(coll, MON_2209)
    assert coll.full_reads == ["list|nasdaq|2026-11-23"]
    assert SL.rows_for(b, "NEWX")[0]["trigger_time"] == "10:00:00"


def test_NEGATIVE_load_with_no_collection_is_empty_and_unread():
    a = SL.load(None, MON_2209)
    assert a["read"] is False and a["lists"] == {} and SL.rows_for(a, "GP") == []
    assert SL.complete_for(a, D20) is False


def test_NEGATIVE_load_on_a_raising_collection_raises_for_the_caller_to_fence():
    class Broken(StandIn):
        def find(self, flt, projection=None):
            raise RuntimeError("synthetic: Mongo read refused")
    with pytest.raises(RuntimeError):
        SL.load(Broken(), MON_2209)


# ═════════════════════════════════════════════ complete_for [C4]
def test_NEGATIVE_complete_for_the_final_16_30_edition_of_file_T_alone_is_false():
    coll = StandIn()
    hold(coll, ("nasdaq", D20), ("nyse", D20))
    loaded = SL.load(coll, MON_2209)
    assert loaded["lists"][("nasdaq", "2026-11-20")]["final"] is True
    assert SL.complete_for(loaded, D20) is False


def test_complete_for_nasdaq_through_the_next_file_any_edition_plus_nyse_file_T():
    coll = StandIn()
    hold(coll, ("nasdaq", D20), ("nyse", D20), ("nasdaq", D23))              # 11/23 = the 04:15 pre-open edition
    assert SL.complete_for(SL.load(coll, MON_2209), D20) is True


def test_NEGATIVE_complete_for_one_source_missing_is_false():
    coll = StandIn()
    hold(coll, ("nasdaq", D23))
    assert SL.complete_for(SL.load(coll, MON_2209), D20) is False               # NYSE 11/20 missing
    coll2 = StandIn()
    hold(coll2, ("nyse", D20), ("nasdaq", D20))
    assert SL.complete_for(SL.load(coll2, MON_2209), D20) is False              # Nasdaq 11/23 missing


@pytest.mark.parametrize("hm", [(4, 30), (9, 31), (12, 0), (16, 31), (20, 30), (23, 59)])
def test_NEGATIVE_complete_for_today_is_false_all_day(hm):
    coll = StandIn()
    hold(coll, ("nasdaq", D20), ("nyse", D20), ("nyse", D23))
    SL.refresh_one(NASDAQ, D23, coll, MON_2209,
                   http=FakeHTTP({url(NASDAQ, D23): Resp(200, synthetic_nasdaq(D23, ["GP,G,R,11/23/2026 1:43:10 PM"]))}))
    now = datetime(2026, 11, 23, hm[0], hm[1], tzinfo=ET)
    assert SL.complete_for(SL.load(coll, now), D23) is False


# ═════════════════════════════════════════════ rows_for
def test_rows_for_the_union_of_file_T_and_file_next_T_without_duplicates():
    coll = StandIn()
    hold(coll, ("nasdaq", D20), ("nasdaq", D23))
    loaded = SL.load(coll, MON_2209)
    gp = SL.rows_for(loaded, "GP")
    assert gp == [
        {"source": "nasdaq", "exchange": "Nasdaq", "trigger_date": "2026-11-20", "trigger_time": "09:45:36",
         "file_date": "2026-11-23", "stamp": "20261123041515"},
        {"source": "nasdaq", "exchange": "Nasdaq", "trigger_date": "2026-11-19", "trigger_time": "09:30:01",
         "file_date": "2026-11-20", "stamp": "20261120163031"},
    ]
    akan = SL.rows_for(loaded, "akan")                                        # lower-case ask
    assert [(r["trigger_date"], r["trigger_time"]) for r in akan] == [("2026-11-19", "09:30:47")]


def test_rows_for_a_row_only_in_the_final_16_30_edition_still_counts():
    coll = StandIn()
    hold(coll, ("nasdaq", D20), ("nasdaq", D23))
    loaded = SL.load(coll, MON_2209)
    f20 = {(r[0], r[1], r[2]) for r in SL.parse_nasdaq(_bytes("nasdaq_shorthalts20261120.txt").decode(), D20)[0]
           if r[1] == "2026-11-20"}
    f23 = {(r[0], r[1], r[2]) for r in SL.parse_nasdaq(_bytes("nasdaq_shorthalts20261123_preopen.txt").decode(),
                                                       D23)[0]}
    only_final = sorted(f20 - f23)
    only_next = sorted(f23 - f20)
    assert only_final and only_next                                           # the measured both-ways difference
    sym, td, tt = only_final[0]
    assert {"trigger_date": td, "trigger_time": tt, "file_date": "2026-11-20"}.items() <= \
        [r for r in SL.rows_for(loaded, sym) if r["trigger_date"] == td][0].items()
    sym, td, tt = only_next[0]
    assert [r for r in SL.rows_for(loaded, sym) if r["trigger_date"] == td][0]["file_date"] == "2026-11-23"


def test_rows_for_brk_spellings_and_nyse_exchange_names():
    coll = StandIn()
    hold(coll, ("nyse", D23))
    SL.refresh_one(NASDAQ, D23, coll, MON_2209,
                   http=FakeHTTP({url(NASDAQ, D23): Resp(200, synthetic_nasdaq(D23, ["BRK B,Berk,Q,11/23/2026 "
                                                                                      "10:00:00 AM"]))}))
    loaded = SL.load(coll, MON_2209)
    want = SL.rows_for(loaded, "BRK.B")
    assert len(want) == 1 and want[0]["trigger_time"] == "10:00:00"
    for ask in ("BRK B", "BRK-B", "brk-b", "brk.b", "BRK/B"):
        assert SL.rows_for(loaded, ask) == want
    assert SL.rows_for(loaded, "AGL")[0]["exchange"] == "NYSE"
    assert SL.rows_for(loaded, "ZOAR")[0]["exchange"] == "NYSE American"
    assert SL.rows_for(loaded, "ZSL")[0]["exchange"] == "NYSE Arca"
    assert SL.rows_for(loaded, "AHT-PRD") == SL.rows_for(loaded, "AHT PRD") != []


def test_NEGATIVE_KNOWN_LIMIT_a_preferred_asked_without_its_separator_finds_no_official_row():
    """KNOWN LIMIT, pinned on purpose (review 2026-11-23, not fixed here): the official lists spell a preferred
    `AHT PRD` (stored `AHT.PRD`) while the snapshot keys it `AHTPD`. No alias joins the two spellings, so an ask
    by the snapshot key finds no official row. A fix (a preferred-class alias rule) moves this pin — and the doc's
    'Known limit' paragraph — on purpose."""
    coll = StandIn()
    hold(coll, ("nyse", D23))
    loaded = SL.load(coll, MON_2209)
    assert SL.rows_for(loaded, "AHT.PRD") != []                              # the row is held
    for ask in ("AHTPD", "ahtpd", "AHTPRD"):
        assert SL.rows_for(loaded, ask) == []


@pytest.mark.parametrize("ask", ["ZZZZQ", "", None, "AKA", "GPX"])
def test_NEGATIVE_a_symbol_on_no_list_is_empty(ask):
    coll = StandIn()
    hold(coll, ("nasdaq", D20), ("nasdaq", D23), ("nyse", D23))
    assert SL.rows_for(SL.load(coll, MON_2209), ask) == []


# ═════════════════════════════════════════════ source_views
def _views(coll, now):
    return {v["key"]: v for v in SL.source_views(SL.load(coll, now), now)}


def test_source_views_mid_session_pre_open_edition_and_nyse_not_published():
    coll = StandIn()
    hold(coll, ("nasdaq", D20), ("nasdaq", D23), ("nyse", D20), now=MON_1400)
    v = _views(coll, MON_1400)
    assert v["nasdaq"] == {"key": "nasdaq", "exchange": "Nasdaq", "ok": True, "status": "ok", "as_of": "2026-11-23",
                           "edition_et": "04:15", "final": False, "n": 1092, "error": None,
                           "text": "Nasdaq short sale list for 11/23 · edition 04:15 ET · 1092 rows (today's triggers "
                                   "not in it yet)"}
    assert v["nyse"]["status"] == "ok" and v["nyse"]["as_of"] == "2026-11-20" and v["nyse"]["n"] == 330
    assert v["nyse"]["text"] == "NYSE Group short sale list for 11/23 not published yet (after 20:10 ET)"
    assert v["nyse"]["edition_et"] == "21:18"                                 # 02:18:56 GMT Sat


def test_source_views_evening_final_editions():
    coll = StandIn()
    hold(coll, ("nyse", D23))
    SL.refresh_one(NASDAQ, D23, coll, MON_2209,
                   http=FakeHTTP({url(NASDAQ, D23): Resp(200, synthetic_nasdaq(D23, ["GP,G,R,11/23/2026 1:43:10 PM"]))}))
    v = _views(coll, MON_2209)
    assert v["nasdaq"]["text"] == "Nasdaq short sale list for 11/23 · edition 16:30 ET · 1 rows"
    assert v["nasdaq"]["final"] is True
    assert v["nyse"]["text"] == "NYSE Group short sale list for 11/23 · edition 20:06 ET · 114 rows"


def test_NEGATIVE_source_views_failed_after_the_strikes_names_the_last_good_list():
    coll = StandIn()
    hold(coll, ("nyse", D20), now=MON_2209)
    at = datetime(2026, 11, 23, 20, 30, tzinfo=ET)
    for i in range(SL.SL_ERROR_STRIKES):
        SL.refresh_one(NYSE, D23, coll, at + timedelta(minutes=10 * i), http=FakeHTTP({url(NYSE, D23): Resp(500)}))
    v = _views(coll, MON_2209)
    assert v["nyse"]["status"] == "failed" and v["nyse"]["ok"] is False and v["nyse"]["error"] == "http_500"
    assert v["nyse"]["text"] == "NYSE Group short sale list could not be read — last good list 11/20"


def test_NEGATIVE_source_views_nothing_read_is_pending_never_ok():
    v = _views(StandIn(), MON_2209)
    assert v["nasdaq"]["status"] == "pending" and v["nasdaq"]["ok"] is False and v["nasdaq"]["as_of"] is None
    assert v["nasdaq"]["text"] == "Nasdaq short sale list not read yet"
    assert v["nyse"]["text"] == "NYSE Group short sale list not read yet"


def test_source_views_a_missing_file_reads_not_published():
    coll = StandIn()
    at = datetime(2026, 11, 24, 5, 0, tzinfo=ET)
    SL.refresh_one(NASDAQ, D24, coll, at, http=FakeHTTP({url(NASDAQ, D24): NASDAQ_302}))
    v = _views(coll, at)
    assert v["nasdaq"]["status"] == "pending"                                 # nothing older held either
    assert v["nasdaq"]["text"] == "Nasdaq short sale list for 11/24 not published yet (after 04:20 ET)"


def test_NEGATIVE_no_bounce_and_no_url_in_any_served_text():
    coll = StandIn()
    hold(coll, ("nasdaq", D20), ("nasdaq", D23), ("nyse", D20), now=MON_1400)
    texts = [v["text"] for v in SL.source_views(SL.load(coll, MON_1400), MON_1400)]
    texts += [v["text"] for v in SL.source_views(SL.load(StandIn(), MON_2209), MON_2209)]
    for t in texts:
        assert "bounce" not in t.lower() and "http" not in t and "@" not in t
