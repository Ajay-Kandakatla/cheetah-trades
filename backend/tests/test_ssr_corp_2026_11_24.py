"""⛔ SSR tag — the session's dividends and splits, `short_interest.ssr_corp` (2026-11-23).

Ajay 2026-11-23, verbatim: "No shorting at the bid (SEC short-sale restriction)

Can we check or this for other stocks too?"

Spec rev 2 §3.4a, W5 (critique C1(b), C6). The two files under tests/fixtures/ssr_corp/ are the REAL Massive bodies
of 2026-11-23 (captured ~22:58 ET, no key in them); every other body here is built in this file and named SYNTHETIC.

Harness: an autouse fixture swaps the house client `sepa.prices._http` for a REFUSER and the key resolver for a
synthetic key, so no test can make an outside call; a test that wants an answer passes its own `http=` fake.
"""
from __future__ import annotations

import ast
import copy
import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from short_interest import ssr_corp as CA

BACKEND = Path(__file__).resolve().parents[1]
FIX = BACKEND / "tests" / "fixtures" / "ssr_corp"
SRC = BACKEND / "short_interest" / "ssr_corp.py"
ET = ZoneInfo("America/New_York")
D = date(2026, 11, 23)
KEY = "SYNTHKEYabc123"
DIV_URL = "https://api.massive.com/v3/reference/dividends"
SPL_URL = "https://api.massive.com/v3/reference/splits"


def _at(h, m, d=D):
    return datetime(d.year, d.month, d.day, h, m, tzinfo=ET)


# ═════════════════════════════════════════════ fakes
class Coll:
    """find_one({"_id"}) + replace_one({"_id"}, doc, upsert=True) — and NOTHING else."""

    def __init__(self):
        self.docs = {}
        self.writes = []
        self.fail_kind = None

    def find_one(self, flt):
        assert list(flt) == ["_id"], flt
        d = self.docs.get(flt["_id"])
        return copy.deepcopy(d) if d else None

    def replace_one(self, flt, doc, upsert=False):
        assert upsert is True and flt == {"_id": doc["_id"]}, (flt, upsert)
        if self.fail_kind and doc.get("kind") == self.fail_kind:
            raise RuntimeError("SYNTHETIC: write refused")
        self.writes.append(copy.deepcopy(doc))
        self.docs[doc["_id"]] = copy.deepcopy(doc)

    def __getattr__(self, name):
        raise AssertionError("ssr_corp used a collection operation outside its two: %s" % name)


class Raising:
    def find_one(self, flt):
        raise RuntimeError("SYNTHETIC: mongo down")

    def replace_one(self, *a, **k):
        raise RuntimeError("SYNTHETIC: mongo down")


class Resp:
    def __init__(self, status, body=None, bad_json=False):
        self.status_code = status
        self._body = body
        self._bad = bad_json

    def json(self):
        if self._bad:
            raise ValueError("SYNTHETIC: not json")
        return copy.deepcopy(self._body)


class Session:
    """Session-like `http`: `.get(url, params=, timeout=)`; answers keyed by (url, the date param or None)."""

    def __init__(self, answers, on_call=None):
        self.answers = answers
        self.calls = []
        self.on_call = on_call

    def get(self, url, **kw):
        self.calls.append((url, copy.deepcopy(kw)))
        if self.on_call:
            self.on_call(url, kw)
        a = self.answers.get(url)
        if callable(a):
            a = a(url, kw)
        if a is None:
            raise LookupError("SYNTHETIC: no answer")
        if isinstance(a, BaseException):
            raise a
        return a


def _real(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _real_session(**kw):
    return Session({DIV_URL: Resp(200, _real("massive_dividends_20261123.json")),
                    SPL_URL: Resp(200, _real("massive_splits_20261123.json"))}, **kw)


def _body(rows, next_url=None):
    b = {"status": "OK", "results": rows}
    if next_url:
        b["next_url"] = next_url
    return b


class Refuser:
    def __init__(self):
        self.called = []

    def get(self, url, **kw):
        self.called.append(url)
        raise AssertionError("an outside call was attempted: %s" % url.split("?")[0])


@pytest.fixture(autouse=True)
def _harness(monkeypatch):
    import massive_keys
    from sepa import prices
    ref = Refuser()
    monkeypatch.setattr(prices, "_http", lambda: ref)
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: KEY)
    CA._reset_cache()
    yield
    CA._reset_cache()
    assert ref.called == []


def _refresh_real(now=None):
    coll = Coll()
    out = CA.refresh_due(coll, [D], now or _at(22, 58), http=_real_session())
    return coll, out


# ═════════════════════════════════════════════ the real bodies
def test_real_bodies_rows_and_names():
    got = CA.fetch_day(D, http=_real_session())
    assert got["result"] == "found"
    assert len(got["dividends"]) == 198
    assert len({r[0] for r in got["dividends"]}) == 195
    assert len(got["splits"]) == 15
    assert ["PXED", 2.36, "USD"] in got["dividends"]
    assert ["TOPP", 5.0, 1.0] in got["splits"]
    assert ["ITP", 40.0, 1.0] in got["splits"]


def test_real_bodies_actions_through_store():
    coll, out = _refresh_real()
    assert out["ran"] == ["2026-11-23"] and out["results"] == {"2026-11-23": "found"} and out["calls"] == 2
    doc = coll.docs["corp|2026-11-23"]
    assert doc["kind"] == "corp" and doc["n_div"] == 198 and doc["n_split"] == 15 and doc["after_open"] is True
    st = coll.docs["corpstate|2026-11-23"]
    assert st["result"] == "found" and st["errors"] == 0 and st["error"] is None
    acts = CA.actions(CA.load(coll, [D]), D)
    assert acts["PXED"] == "dividend"
    assert acts["TOPP"] == "split" and acts["ITP"] == "split"
    assert acts["NWSZF"] == "split"                            # the real name with both on 11/23: split wins
    assert len(acts) == 195 + 15 - 1
    assert KEY not in json.dumps(coll.docs)


def test_split_wins_and_class_share_spelling():
    s = Session({DIV_URL: Resp(200, _body([{"ticker": "BOTH", "cash_amount": 0.1, "currency": "USD"},
                                            {"ticker": "BRK.B", "cash_amount": 1.0, "currency": "USD"},
                                            {"ticker": "brk.a", "cash_amount": 1.0, "currency": "USD"}])),
                 SPL_URL: Resp(200, _body([{"ticker": "BOTH", "split_from": 2, "split_to": 1}]))})
    coll = Coll()
    CA.refresh_due(coll, [D], _at(10, 0), http=s)
    acts = CA.actions(CA.load(coll, [D]), D)
    assert acts == {"BOTH": "split", "BRK-B": "dividend", "BRK-A": "dividend"}
    assert "BRK.B" not in acts


def test_blank_ticker_row_skipped_not_fatal():
    s = Session({DIV_URL: Resp(200, _body([{"ticker": "", "cash_amount": 1}, {"ticker": None}, "junk",
                                            {"ticker": "   "}, {"ticker": "ok", "cash_amount": "x"}])),
                 SPL_URL: Resp(200, _body([{"split_from": 2, "split_to": 1}]))})
    got = CA.fetch_day(D, http=s)
    assert got == {"result": "found", "dividends": [["OK", None, None]], "splits": []}


# ═════════════════════════════════════════════ strict: a failure is an error, never an empty day
@pytest.mark.parametrize("bad", ["div", "spl"])
def test_http_500_on_either_read_is_error(bad):
    ans = {DIV_URL: Resp(200, _body([])), SPL_URL: Resp(200, _body([]))}
    ans[DIV_URL if bad == "div" else SPL_URL] = Resp(500, {"status": "ERROR"})
    got = CA.fetch_day(D, http=Session(ans))
    assert got["result"] == "error" and "500" in got["error"]
    assert "dividends" not in got and "splits" not in got


def test_http_500_stores_no_day_and_actions_none():
    coll = Coll()
    out = CA.refresh_due(coll, [D], _at(10, 0), http=Session({DIV_URL: Resp(500, {}), SPL_URL: Resp(200, _body([]))}))
    assert out["results"] == {"2026-11-23": "error"}
    assert "corp|2026-11-23" not in coll.docs
    st = coll.docs["corpstate|2026-11-23"]
    assert st["result"] == "error" and st["errors"] == 1 and "500" in st["error"]
    assert CA.actions(CA.load(coll, [D]), D) is None


def test_no_key_is_error_and_no_call(monkeypatch):
    import massive_keys
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: "")
    s = _real_session()
    assert CA.fetch_day(D, http=s) == {"result": "error", "error": "no_key"}
    assert s.calls == []


class ReadTimeout(Exception):
    """SYNTHETIC stand-in for requests' timeout."""


def test_timeout_and_raising_session_are_errors_no_raise():
    got = CA.fetch_day(D, http=Session({DIV_URL: ReadTimeout("read timed out"), SPL_URL: Resp(200, _body([]))}))
    assert got == {"result": "error", "error": "dividends ReadTimeout"}

    class Boom:
        def get(self, *a, **k):
            raise RuntimeError("SYNTHETIC")
    assert CA.fetch_day(D, http=Boom())["result"] == "error"


@pytest.mark.parametrize("body,bad_json", [({"status": "OK"}, False), ({"results": None}, False),
                                           ({"results": {"a": 1}}, False), ([1, 2], False), (None, True),
                                           ("results", False)])
def test_results_missing_or_not_list_is_error(body, bad_json):
    got = CA.fetch_day(D, http=Session({DIV_URL: Resp(200, body, bad_json=bad_json), SPL_URL: Resp(200, _body([]))}))
    assert got == {"result": "error", "error": "dividends malformed"}


def test_key_never_logged_or_stored(caplog):
    leak = "HTTPSConnectionPool: Max retries exceeded with url: %s?ex_dividend_date=2026-11-23&apiKey=%s" % (
        "/v3/reference/dividends", KEY)
    coll = Coll()
    with caplog.at_level(logging.DEBUG):
        out = CA.refresh_due(coll, [D], _at(10, 0), http=Session({DIV_URL: ConnectionError(leak),
                                                                  SPL_URL: Resp(200, _body([]))}))
        lv = CA.load(coll, [D])
        view = CA.source_view(lv, [D], _at(10, 0))
    assert out["results"] == {"2026-11-23": "error"}
    text = " ".join(r.getMessage() for r in caplog.records)
    assert KEY not in text and "apiKey" not in text and "/v3/reference" not in text
    assert KEY not in json.dumps(coll.docs) and "apiKey" not in json.dumps(coll.docs)
    assert KEY not in json.dumps(view)
    assert coll.docs["corpstate|2026-11-23"]["error"] == "dividends ConnectionError"


# ═════════════════════════════════════════════ paging
def test_next_url_followed_with_key_reattached():
    nxt = "https://api.massive.com/v3/reference/dividends?cursor=abc"
    pages = {"n": 0}

    def div(url, kw):
        pages["n"] += 1
        if pages["n"] == 1:
            return Resp(200, _body([{"ticker": "AAA"}], next_url=nxt))
        return Resp(200, _body([{"ticker": "BBB"}]))
    s = Session({DIV_URL: div, nxt: div, SPL_URL: Resp(200, _body([]))})
    got = CA.fetch_day(D, http=s)
    assert [r[0] for r in got["dividends"]] == ["AAA", "BBB"]
    assert s.calls[1][0] == nxt and s.calls[1][1]["params"] == {"apiKey": KEY}
    assert s.calls[1][1]["timeout"] == CA.CA_HTTP_TIMEOUT_SEC


def test_next_url_carrying_a_key_is_stripped_then_ours_attached():
    nxt = "https://api.massive.com/v3/reference/splits?cursor=z&apiKey=OTHER"
    first = {"n": 0}

    def spl(url, kw):
        first["n"] += 1
        return Resp(200, _body([], next_url=nxt if first["n"] == 1 else None))
    s = Session({DIV_URL: Resp(200, _body([])), SPL_URL: spl,
                 "https://api.massive.com/v3/reference/splits?cursor=z": spl})
    assert CA.fetch_day(D, http=s)["result"] == "found"
    assert "OTHER" not in s.calls[-1][0] and s.calls[-1][1]["params"] == {"apiKey": KEY}


def test_more_than_max_pages_is_truncated_error():
    nxt = "https://api.massive.com/v3/reference/dividends?cursor=again"
    s = Session({DIV_URL: lambda u, k: Resp(200, _body([{"ticker": "X"}], next_url=nxt)),
                 nxt: lambda u, k: Resp(200, _body([{"ticker": "X"}], next_url=nxt)),
                 SPL_URL: Resp(200, _body([]))})
    got = CA.fetch_day(D, http=s)
    assert got == {"result": "error", "error": "dividends truncated"}
    assert len(s.calls) == CA.CA_MAX_PAGES


def test_exactly_max_pages_is_complete():
    n = {"i": 0}
    nxt = "https://api.massive.com/v3/reference/dividends?cursor=p"

    def div(u, k):
        n["i"] += 1
        return Resp(200, _body([{"ticker": "P%d" % n["i"]}], next_url=nxt if n["i"] < CA.CA_MAX_PAGES else None))
    s = Session({DIV_URL: div, nxt: div, SPL_URL: Resp(200, _body([]))})
    got = CA.fetch_day(D, http=s)
    assert got["result"] == "found" and len(got["dividends"]) == CA.CA_MAX_PAGES


def test_next_url_to_another_host_is_error_and_never_asked():
    evil = "https://evil.example.com/v3/reference/dividends?cursor=1"
    s = Session({DIV_URL: Resp(200, _body([], next_url=evil)), SPL_URL: Resp(200, _body([]))})
    got = CA.fetch_day(D, http=s)
    assert got == {"result": "error", "error": "dividends bad_next_url"}
    assert all(not u.startswith("https://evil") for u, _ in s.calls)


# ═════════════════════════════════════════════ the request
def test_both_reads_by_date_no_ticker_limit_timeout():
    s = _real_session()
    CA.fetch_day(D, http=s)
    assert [u for u, _ in s.calls] == [DIV_URL, SPL_URL]
    (_, k1), (_, k2) = s.calls
    assert k1["params"] == {"ex_dividend_date": "2026-11-23", "limit": CA.CA_PAGE_LIMIT, "apiKey": KEY}
    assert k2["params"] == {"execution_date": "2026-11-23", "limit": CA.CA_PAGE_LIMIT, "apiKey": KEY}
    for _, k in s.calls:
        assert "ticker" not in k["params"]
        assert k["timeout"] == CA.CA_HTTP_TIMEOUT_SEC == 15
    assert CA.CA_PAGE_LIMIT == 1000


def test_default_client_is_the_house_session(monkeypatch):
    from sepa import prices
    s = _real_session()
    monkeypatch.setattr(prices, "_http", lambda: s)
    assert CA.fetch_day(D)["result"] == "found" and len(s.calls) == 2


def test_requests_get_like_callable_is_accepted():
    s = _real_session()
    assert CA.fetch_day(D, http=lambda url, **kw: s.get(url, **kw))["result"] == "found"


# ═════════════════════════════════════════════ due rule
def _loaded(coll, days=(D,)):
    return CA.load(coll, list(days))


def test_no_doc_is_due():
    assert CA.any_due(_loaded(Coll()), [D], _at(8, 0)) is True


def test_pre_open_read_due_once_more_after_open_not_before():
    coll, _ = _refresh_real(_at(8, 0))
    assert coll.docs["corp|2026-11-23"]["after_open"] is False
    assert CA.any_due(_loaded(coll), [D], _at(9, 0)) is False
    assert CA.any_due(_loaded(coll), [D], _at(9, 29)) is False
    assert CA.any_due(_loaded(coll), [D], _at(9, 31)) is True
    out = CA.refresh_due(coll, [D], _at(9, 31), http=_real_session())
    assert out["calls"] == 2 and coll.docs["corp|2026-11-23"]["after_open"] is True
    for t in (_at(10, 5), _at(23, 0), _at(12, 0, date(2026, 11, 24))):
        assert CA.any_due(_loaded(coll), [D], t) is False


def test_read_at_0931_never_due_again_zero_calls():
    coll, _ = _refresh_real(_at(9, 31))
    s = _real_session()
    for t in (_at(10, 2), _at(16, 0), _at(9, 31, date(2026, 11, 25))):
        assert CA.any_due(_loaded(coll), [D], t) is False
        assert CA.refresh_due(coll, [D], t, http=s) == {"ran": [], "results": {}, "calls": 0}
    assert s.calls == []


def test_open_boundary_is_inclusive():
    coll, _ = _refresh_real(_at(9, 30))
    assert coll.docs["corp|2026-11-23"]["after_open"] is True


def test_error_retry_waits():
    coll = Coll()
    bad = Session({DIV_URL: Resp(500, {}), SPL_URL: Resp(200, _body([]))})
    CA.refresh_due(coll, [D], _at(10, 0), http=bad)
    assert coll.docs["corpstate|2026-11-23"]["errors"] == 1
    assert CA.any_due(_loaded(coll), [D], _at(10, 4)) is False
    assert CA.any_due(_loaded(coll), [D], _at(10, CA.CA_ERROR_RETRY_MIN)) is True
    CA.refresh_due(coll, [D], _at(10, 5), http=bad)
    assert coll.docs["corpstate|2026-11-23"]["errors"] == CA.CA_ERROR_STRIKES
    assert CA.any_due(_loaded(coll), [D], _at(10, 10)) is False
    assert CA.any_due(_loaded(coll), [D], _at(10, 34)) is False
    assert CA.any_due(_loaded(coll), [D], _at(10, 5 + CA.CA_RETRY_MIN)) is True
    CA.refresh_due(coll, [D], _at(10, 35), http=_real_session())
    assert coll.docs["corpstate|2026-11-23"]["errors"] == 0


def test_throttled_refresh_makes_no_call():
    coll = Coll()
    CA.refresh_due(coll, [D], _at(10, 0), http=Session({DIV_URL: Resp(500, {}), SPL_URL: Resp(200, _body([]))}))
    s = _real_session()
    assert CA.refresh_due(coll, [D], _at(10, 2), http=s)["calls"] == 0 and s.calls == []


def test_state_doc_written_before_the_outside_call():
    coll = Coll()
    seen = []

    def on_call(url, kw):
        st = coll.docs.get("corpstate|2026-11-23")
        seen.append(st and st["result"])
    CA.refresh_due(coll, [D], _at(10, 0), http=_real_session(on_call=on_call))
    assert seen == ["running", "running"]


def test_state_write_refused_means_no_outside_call():
    coll = Coll()
    coll.fail_kind = "corpstate"
    s = _real_session()
    out = CA.refresh_due(coll, [D], _at(10, 0), http=s)
    assert s.calls == [] and out["ran"] == [] and "corp|2026-11-23" not in coll.docs


def test_one_fetch_per_due_day_and_days_deduped():
    d2 = date(2026, 11, 20)
    s = Session({DIV_URL: Resp(200, _body([])), SPL_URL: Resp(200, _body([]))})
    out = CA.refresh_due(Coll(), [d2, D, D, "2026-11-23"], _at(10, 0), http=s)
    assert out["ran"] == ["2026-11-20", "2026-11-23"] and len(s.calls) == 4
    assert [k["params"].get("ex_dividend_date") for u, k in s.calls if u == DIV_URL] == ["2026-11-20", "2026-11-23"]


def test_zero_calls_when_every_day_read_after_open():
    coll = Coll()
    days = [date(2026, 11, 20), D]
    CA.refresh_due(coll, days, _at(10, 0), http=Session({DIV_URL: Resp(200, _body([])),
                                                         SPL_URL: Resp(200, _body([]))}))
    s = _real_session()
    assert CA.refresh_due(coll, days, _at(15, 0), http=s)["calls"] == 0 and s.calls == []
    assert CA.any_due(_loaded(coll, days), days, _at(15, 0)) is False


# ═════════════════════════════════════════════ actions
def test_actions_none_when_day_not_read_never_empty():
    coll, _ = _refresh_real()
    lv = _loaded(coll, [D, date(2026, 11, 20)])
    assert CA.actions(lv, date(2026, 11, 20)) is None
    assert CA.actions(CA.load(None, [D]), D) is None
    assert CA.actions(None, D) is None
    assert CA.actions({}, D) is None


def test_actions_empty_only_for_a_read_day_with_no_rows():
    coll = Coll()
    CA.refresh_due(coll, [D], _at(10, 0), http=Session({DIV_URL: Resp(200, _body([])),
                                                        SPL_URL: Resp(200, _body([]))}))
    assert CA.actions(_loaded(coll), D) == {}


def test_decoded_once_per_rev():
    coll, _ = _refresh_real()
    a = CA.load(coll, [D])["actions"]["2026-11-23"]
    b = CA.load(coll, [D])["actions"]["2026-11-23"]
    assert a is b
    doc = coll.docs["corp|2026-11-23"]
    doc["rev"] = "new"
    doc["dividends"] = [["NEWDIV", 1.0, "USD"]]
    doc["splits"] = []
    assert CA.actions(CA.load(coll, [D]), D) == {"NEWDIV": "dividend"}


# ═════════════════════════════════════════════ source_view
FORBIDDEN = re.compile(r"bounce|apiKey|https?://|massive\.com|" + KEY, re.I)


def _assert_clean(view):
    for k in ("text", "error"):
        assert not FORBIDDEN.search(str(view.get(k) or "")), view


def test_source_view_ok():
    coll, _ = _refresh_real()
    v = CA.source_view(_loaded(coll), [D], _at(23, 0))
    assert v == {"key": "corp_actions", "exchange": None, "ok": True, "status": "ok",
                 "as_of": coll.docs["corp|2026-11-23"]["read_at"], "n": 209, "error": None,
                 "text": "dividends and splits of 11/23 read · 209 names"}
    _assert_clean(v)


def test_source_view_pending():
    v = CA.source_view(_loaded(Coll(), [date(2026, 11, 20), D]), [D, date(2026, 11, 20)], _at(8, 0))
    assert v["status"] == "pending" and v["ok"] is False
    assert v["text"] == "dividends and splits of 11/20, 11/23 not read yet"
    _assert_clean(v)


def test_source_view_first_error_still_pending_then_failed():
    coll = Coll()
    bad = Session({DIV_URL: Resp(500, {}), SPL_URL: Resp(200, _body([]))})
    CA.refresh_due(coll, [D], _at(10, 0), http=bad)
    assert CA.source_view(_loaded(coll), [D], _at(10, 1))["status"] == "pending"
    CA.refresh_due(coll, [D], _at(10, 6), http=bad)
    v = CA.source_view(_loaded(coll), [D], _at(10, 7))
    assert v["status"] == "failed" and v["ok"] is False
    assert v["text"] == "dividends and splits of 11/23 could not be read"
    assert v["error"] == "dividends HTTP 500"
    _assert_clean(v)


def test_source_view_worst_day_wins():
    coll, _ = _refresh_real()
    v = CA.source_view(_loaded(coll, [date(2026, 11, 20), D]), [date(2026, 11, 20), D], _at(23, 0))
    assert v["status"] == "pending" and v["text"] == "dividends and splits of 11/20 not read yet"
    assert v["n"] == 209


def test_source_view_mongo_down_is_failed():
    v = CA.source_view(CA.load(None, [D]), [D], _at(10, 0))
    assert v["status"] == "failed" and v["error"] == "unread"
    v2 = CA.source_view(CA.load(Raising(), [D]), [D], _at(10, 0))
    assert v2["status"] == "failed"
    _assert_clean(v)


def test_served_texts_carry_no_forbidden_words():
    for t in (CA.SRC_OK, CA.SRC_PENDING, CA.SRC_FAILED):
        assert not FORBIDDEN.search(t)


# ═════════════════════════════════════════════ never raises
def test_refresh_due_never_raises_on_a_raising_collection():
    s = _real_session()
    assert CA.refresh_due(Raising(), [D], _at(10, 0), http=s) == {"ran": [], "results": {}, "calls": 0}
    assert s.calls == []
    assert CA.refresh_due(None, [D], _at(10, 0), http=s)["ran"] == []
    assert CA.any_due(CA.load(Raising(), [D]), [D], _at(10, 0)) is False


def test_corp_doc_write_failure_reads_error_no_raise():
    coll = Coll()
    coll.fail_kind = "corp"
    out = CA.refresh_due(coll, [D], _at(10, 0), http=_real_session())
    assert out["results"] == {"2026-11-23": "error"}
    st = coll.docs["corpstate|2026-11-23"]
    assert st["result"] == "error" and st["error"] == "store RuntimeError" and st["errors"] == 1


def test_final_state_write_failure_no_raise():
    class Half(Coll):
        def replace_one(self, flt, doc, upsert=False):
            if doc.get("kind") == "corpstate" and doc.get("result") != "running":
                raise RuntimeError("SYNTHETIC")
            return super().replace_one(flt, doc, upsert)
    coll = Half()
    assert CA.refresh_due(coll, [D], _at(10, 0), http=_real_session())["results"] == {"2026-11-23": "found"}


# ═════════════════════════════════════════════ source guards
def _code_without_docstrings():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body and \
                isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], "value", None), ast.Constant):
            node.body = node.body[1:] or [ast.Pass()]
    return tree


def test_imports_neither_ssr_nor_ssr_lists_and_lazy_heavy_imports():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update("%s.%s" % (node.module, a.name) for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    assert not any(n.endswith("ssr") or "ssr_lists" in n for n in names), names
    top = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            top.add(node.module)
        elif isinstance(node, ast.Import):
            top.update(a.name for a in node.names)
    assert not top & {"sepa", "sepa.prices", "sepa.symbols", "massive_keys", "daytrading.data", "requests"}, top


def test_by_date_endpoints_and_no_adjusted_close():
    src = SRC.read_text(encoding="utf-8")
    assert '"ex_dividend_date"' in src and '"execution_date"' in src
    code = ast.unparse(_code_without_docstrings())
    assert not re.search(r"prev_close|prior_close|adjust|'ticker'\s*:", code)
    assert not re.search(r"bounce", src, re.I)


def test_no_outside_call_without_a_seam():
    """Default refresh with the refuser installed: the refuser trips → stored error, never a raise."""
    coll = Coll()
    from sepa import prices
    ref = prices._http()
    out = CA.refresh_due(coll, [D], _at(10, 0))
    assert out["results"] == {"2026-11-23": "error"}
    assert ref.called == [DIV_URL]
    ref.called.clear()
