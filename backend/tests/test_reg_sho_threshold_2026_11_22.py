"""🔒 Hard to borrow (Reg SHO threshold security) — the backend engine, route, ℹ️ pick and test guard (2026-11-22).

Ajay 2026-11-22, verbatim: "Can you do something for me for reversal squeezes can you also tell me if something is
under when it's on our list.. i want to check if people are finding it hard to get stocks like AkAN now has that
issue.. add a tag to stocks tickers like short interest, name the tag " hard to borrow" threshold security"

Spec: scratchpad htb/spec.md §3.1-§3.2, §4 `be`. The 20 files under tests/fixtures/reg_sho/ are VERBATIM answers of
the three hosts (fetched 2026-11-22); every other body in this file is built here and named SYNTHETIC.

Harness [C6]: an autouse fixture replaces the engine's ONE outside-call seam (`RS._http`) with a RECORDING refuser and
asserts at teardown it was never called; a test that wants an outside answer passes its own `http=` fake. The
in-memory collection implements exactly the four operations the engine may use and FAILS on any other.
"""
from __future__ import annotations

import asyncio
import copy
import json
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from short_interest import api as SAPI
from short_interest import client as SIC
from short_interest import read as SR
from short_interest import reg_sho as RS

BACKEND = Path(__file__).resolve().parents[1]
FIX = BACKEND / "tests" / "fixtures" / "reg_sho"
GOLDEN = BACKEND / "tests" / "fixtures" / "reg_sho_payload_2026_11_22.json"
ET = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 22, 20, 42, tzinfo=ET)              # Sunday night, the planning clock
NASDAQ, NYSE, CBOE = RS.SOURCES
FORBIDDEN = re.compile(r"fee|impossible|cannot be borrowed|no shares|squeeze|bounce|fake|predict|will (rise|fall|drop)",
                       re.I)

# 2026-11-24: AKAN is day 1 of its run (the close-out day of spec regsho_tag §3.3)
AKAN_CHIP = "🔒 Hard to borrow · threshold security · 11/20 · day 1 of 13 · close-out day Wed 12/9 if it stays on"
AKAN_SHORT = "🔒 close-out Wed 12/9 · day 1 of 13"
AKAN_LABEL = ("🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 1 of 13 · close-out day "
              "Wed 12/9 if it stays on")
AKAN_TITLE = ("🔒 Hard to borrow — AKAN is a Reg SHO threshold security on the Nasdaq list for 2026-11-20: fails to "
              "deliver of at least 10,000 shares and at least 0.5% of shares outstanding for 5 straight settlement "
              "days (SEC Regulation SHO Rule 203(c)(6)). The threshold list measures persistent fails to deliver, not "
              "a broker's borrow rate — a broker's own hard-to-borrow list can differ. A data label, not a signal. "
              "UNMEASURED. On the list 1 straight settlement day since 11/20. Day 13 = Wed 12/9 if it stays on (Thu "
              "12/10 if counted from each list's next open). After day 13, Rule 203(b)(3) makes a clearing firm buy "
              "shares to close out a fail to deliver it carried on every one of those days; the buying may come from "
              "day 11 (Mon 12/7) and must start by the next open (SEC staff FAQ 6.5, 6.7). Rule 204 already requires a "
              "fail in any stock to be closed out 1 to 3 settlement days after settlement, so fails generally do not "
              "last 13 (SEC staff); for a Rule 144 sale the count is 35, not 13. Fails to deliver only, not every "
              "short position. A rule date — it says nothing about price. Not advice.")


# ═════════════════════════════════════════════ fakes
class StandIn:
    """The engine's Mongo collection: find_one(filter, sort=[("trade_date", -1)]), find({"kind": "state"}),
    replace_one(filter, doc, upsert=True), create_index — and NOTHING else [C9]."""

    def __init__(self):
        self.docs = {}
        self.fail_final_state = False

    @staticmethod
    def _match(doc, flt):
        for k, v in flt.items():
            if isinstance(v, dict):
                assert set(v) == {"$gte"} and isinstance(v["$gte"], str), v
                if not isinstance(doc.get(k), str) or doc.get(k) < v["$gte"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def find_one(self, flt, sort=None):
        assert sort == [("trade_date", -1)], sort
        hits = [d for d in self.docs.values() if self._match(d, flt)]
        hits.sort(key=lambda d: str(d.get("trade_date") or ""), reverse=True)
        return copy.deepcopy(hits[0]) if hits else None

    def find(self, flt):
        # 2026-11-24: the close-out day's history adds exactly two window-bounded filters
        # 2026-11-26 (sitrack §3.4): and ONE bounded read of the walked-back run starts
        ok = flt == {"kind": "state"} or (
            set(flt) == {"kind", "trade_date"} and flt["kind"] in ("list", "nolist")
            and isinstance(flt["trade_date"], dict) and set(flt["trade_date"]) == {"$gte"}
            and isinstance(flt["trade_date"]["$gte"], str)) or (
            set(flt) == {"kind", "on_through"} and flt["kind"] == RS.RUNSTART_KIND
            and isinstance(flt["on_through"], dict) and set(flt["on_through"]) == {"$gte"}
            and isinstance(flt["on_through"]["$gte"], str))
        assert ok, flt
        return [copy.deepcopy(d) for d in self.docs.values() if self._match(d, flt)]

    def replace_one(self, flt, doc, upsert=False):
        assert upsert is True and flt == {"_id": doc["_id"]}, (flt, upsert)
        if self.fail_final_state and doc.get("kind") == "state" and doc.get("result") != "running":
            raise RuntimeError("synthetic: the final state write fails")
        self.docs[doc["_id"]] = copy.deepcopy(doc)

    def create_index(self, keys, **kw):
        return "noop"

    def __getattr__(self, name):
        raise AssertionError("reg_sho used a collection operation outside its four: %s" % name)


class FakeDB:
    def __init__(self, coll=None):
        self.coll = coll if coll is not None else StandIn()

    def __getitem__(self, name):
        assert name == RS.RS_COLL, name
        return self.coll


class Resp:
    def __init__(self, status_code, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class ReadTimeout(Exception):
    """SYNTHETIC stand-in for requests' timeout (the engine reads the class name)."""


class FakeHTTP:
    def __init__(self, answers=None, on_call=None):
        self.answers = dict(answers or {})
        self.urls = []
        self.kwargs = []
        self.unexpected = []
        self.on_call = on_call

    def __call__(self, url, **kw):
        self.urls.append(url)
        self.kwargs.append(kw)
        if self.on_call:
            self.on_call(url)
        a = self.answers.get(url)
        if a is None:
            self.unexpected.append(url)
            raise LookupError("no answer for %s" % url)
        if isinstance(a, BaseException):
            raise a
        return a


def _body(name: str) -> str:
    return (FIX / name).read_bytes().decode("utf-8")          # keeps CRLF / LF exactly


def _d8(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


_NYSE_FILE_MKT = {"NYSE": "nyse", "NYSE-American": "nyse_american", "NYSE-Arca": "nyse_arca"}


def fixture_answers() -> dict:
    """url → the VERBATIM answer, for the 20 fixture files."""
    out = {}
    for f in sorted(FIX.iterdir()):
        n = f.name
        m = re.match(r"nasdaq_(\d{8})\.txt$", n)
        if m:
            out[RS.source_url(NASDAQ, "nasdaq", _d8(m[1]))] = Resp(200, _body(n))
            continue
        m = re.match(r"nyse_(NYSE(?:-American|-Arca)?)_(\d{4}-\d{2}-\d{2})", n)
        if m:
            out[RS.source_url(NYSE, _NYSE_FILE_MKT[m[1]], date.fromisoformat(m[2]))] = Resp(200, _body(n))
            continue
        m = re.match(r"cboe_bzx_(\d{8})\.txt$", n)
        if m:
            out[RS.source_url(CBOE, "cboe_bzx", _d8(m[1]))] = Resp(200, _body(n))
            continue
        m = re.match(r"cboe_bzx_(\d{8})_missing_403\.xml$", n)
        assert m, n
        out[RS.source_url(CBOE, "cboe_bzx", _d8(m[1]))] = Resp(403, _body(n))
    assert len(out) == 20
    return out


def nasdaq_url(d):
    return RS.source_url(NASDAQ, "nasdaq", d)


def nyse_url(mkt, d):
    return RS.source_url(NYSE, mkt, d)


def cboe_url(d):
    return RS.source_url(CBOE, "cboe_bzx", d)


def synthetic_nasdaq(d: date, rows) -> str:
    """SYNTHETIC Nasdaq file (CRLF, the measured shape) for date d."""
    return "\r\n".join([RS.NASDAQ_HEADER] + list(rows) + [d.strftime("%Y%m%d") + "230006"]) + "\r\n"


def synthetic_nyse(d: date, rows) -> str:
    """SYNTHETIC NYSE file (LF rows, CRLF trailer — the measured shape) for date d."""
    stamp = d.strftime("%Y%m%d") + ("220201" if rows else "210500")
    return "\n".join([RS.NYSE_HEADER] + list(rows)) + "\n" + stamp + "\r\n"


NASDAQ_302 = Resp(302, "", {"Location": "/Trader.aspx?id=http404"})     # SYNTHETIC copy of the measured answer


def seed_list(coll, mkt, d, symbols, *, fetched_at=None, confirmed=True):
    src = next(s for s, m, _e, _f in RS.all_markets() if m == mkt)
    ex = next(e for _s, m, e, _f in RS.all_markets() if m == mkt)
    fa = fetched_at or (datetime(d.year, d.month, d.day, 23, 30, tzinfo=ET)).astimezone(ZoneInfo("UTC")).isoformat()
    doc = {"_id": "list|%s|%s" % (mkt, d.isoformat()), "kind": "list", "source": src["key"], "market": mkt,
           "exchange": ex, "trade_date": d.isoformat(), "symbols": sorted(symbols), "n": len(symbols), "skipped": 0,
           "file_stamp": "synthetic", "url": "synthetic", "fetched_at": fa,
           "confirmed_at": fa if (symbols or confirmed) else None, "revised_at": None}
    coll.docs[doc["_id"]] = doc
    return doc


def parse_fixture(name, src, d, mkt=None):
    return RS.parse_list(_body(name), header=src["header"], flag_col=src["flag_col"], want=d,
                         market_name=(RS._exchange(src, mkt) if mkt and src["market_col"] else None))


def golden_round(answers=None, now=NOW):
    coll = StandIn()
    http = FakeHTTP(answers if answers is not None else fixture_answers())
    ran = RS.refresh_due(coll, now, http=http)
    return coll, http, ran


def build_golden_payload() -> dict:
    coll, _http, _ran = golden_round()
    RS.backfill_history(coll, NOW, http=FakeHTTP(fixture_answers()))     # 2026-11-24: ONE history round
    return RS.payload(FakeDB(coll), NOW, kick=False)


def _run(coro):
    return asyncio.run(coro)


# ═════════════════════════════════════════════ the guard [C6]
@pytest.fixture(autouse=True)
def outside_calls(monkeypatch):
    calls = []

    def recorder(url=None, *a, **k):
        calls.append(url)
        raise RuntimeError("reg_sho outside calls are refused in this file")
    monkeypatch.setattr(RS, "_http", recorder)
    monkeypatch.setattr(RS, "_bg", {"running": False, "last_start": None, "thread": None})
    monkeypatch.setattr(RS, "_pause", lambda s: None)
    monkeypatch.setattr(RS, "_hist", {"blocked_until": None})
    monkeypatch.setattr(RS, "_asks", {"seq": 0, "items": {}})       # 2026-11-26: the in-process ask set
    yield calls
    t = RS._bg.get("thread")
    if t is not None:
        t.join(5)
    assert calls == [], "the engine reached the module seam: %s" % calls


# ═════════════════════════════════════════════ parse — the verbatim files
LIST_FILES = sorted(n.name for n in FIX.iterdir() if n.suffix == ".txt")


def _parse_any(name):
    m = re.match(r"nasdaq_(\d{8})\.txt$", name)
    if m:
        return parse_fixture(name, NASDAQ, _d8(m[1]))
    m = re.match(r"nyse_(NYSE(?:-American|-Arca)?)_(\d{4}-\d{2}-\d{2})", name)
    if m:
        return parse_fixture(name, NYSE, date.fromisoformat(m[2]), _NYSE_FILE_MKT[m[1]])
    m = re.match(r"cboe_bzx_(\d{8})\.txt$", name)
    return parse_fixture(name, CBOE, _d8(m[1]))


def test_fixtures_are_the_twenty_verbatim_files():
    assert len(list(FIX.iterdir())) == 20 and len(LIST_FILES) == 19


@pytest.mark.parametrize("name", LIST_FILES)
def test_every_verbatim_list_file_parses_with_nothing_skipped(name):
    syms, skipped = _parse_any(name)
    assert skipped == 0
    assert syms == sorted(set(syms))


def test_parse_counts_and_names_on_the_verbatim_files():
    n20, _ = parse_fixture("nasdaq_20261120.txt", NASDAQ, date(2026, 11, 20))
    n19, _ = parse_fixture("nasdaq_20261119.txt", NASDAQ, date(2026, 11, 19))
    assert len(n20) == 76 and "AKAN" in n20 and "ACONW" in n20
    assert "AKAN" not in n19 and "ACONW" not in n19                 # AKAN joined on Friday's file
    am, _ = parse_fixture("nyse_NYSE-American_2026-11-20.txt", NYSE, date(2026, 11, 20), "nyse_american")
    assert am == ["OPTT", "POAS"]
    bzx, _ = parse_fixture("cboe_bzx_20261119.txt", CBOE, date(2026, 11, 19))
    assert len(bzx) == 57
    assert parse_fixture("nyse_NYSE_2026-11-10.txt", NYSE, date(2026, 11, 10), "nyse") == ([], 0)


@pytest.mark.parametrize("name", [n for n in LIST_FILES if n.startswith("nyse_")])
def test_mixed_line_ending_nyse_file_reads_the_same_as_its_crlf_copy(name):
    raw = (FIX / name).read_bytes()
    assert raw.endswith(b"\r\n") and raw.count(b"\r\n") == 1     # LF rows, CRLF trailer (od -c) [C10]
    text = raw.decode("utf-8")
    crlf = text.replace("\r\n", "\n").replace("\n", "\r\n")
    m = re.match(r"nyse_(NYSE(?:-American|-Arca)?)_(\d{4}-\d{2}-\d{2})", name)
    d, mkt = date.fromisoformat(m[2]), _NYSE_FILE_MKT[m[1]]
    kw = dict(header=NYSE["header"], flag_col=3, want=d, market_name=RS._exchange(NYSE, mkt))
    assert RS.parse_list(text, **kw) == RS.parse_list(crlf, **kw) == RS.parse_list(text.replace("\r\n", "\n"), **kw)


# ═════════════════════════════════════════════ the golden payload
def test_golden_payload_equals_the_engine():
    gold = json.loads(GOLDEN.read_text())
    assert gold["now"] == NOW.isoformat()
    assert build_golden_payload() == gold["payload"]


def test_golden_akan_block_is_the_four_worked_strings():
    p = build_golden_payload()
    a = p["items"]["AKAN"]
    assert (a["chip"], a["short"], a["label"], a["title"]) == (AKAN_CHIP, AKAN_SHORT, AKAN_LABEL, AKAN_TITLE)
    assert a["state"] == "on" and a["market"] == "nasdaq" and a["exchange"] == "Nasdaq"
    assert a["as_of"] == "2026-11-20" and a["stale"] is False


def test_golden_sources_counts_and_flags():
    p = build_golden_payload()
    assert p["kind"] == RS.KIND and p["complete"] is True and p["n"] == 160 and p["as_of"] == "2026-11-20"
    assert [s["market"] for s in p["sources"]] == ["nasdaq", "nyse", "nyse_american", "nyse_arca", "cboe_bzx"]
    assert [s["faults"] for s in p["sources"]] == [True, True, True, False, False]
    assert [s["n"] for s in p["sources"]] == [76, 1, 2, 24, 57]
    assert [s["as_of"] for s in p["sources"]] == ["2026-11-20"] * 4 + ["2026-11-19"]
    assert all(s["status"] == "ok" and s["ok"] and not s["stale"] and not s["behind"] for s in p["sources"])
    assert p["sources"][0]["text"] == "Nasdaq threshold list for 11/20 · 76 names"
    assert p["fault_text"] is None and p["refreshing"] is False and p["retry_after_sec"] is None
    assert p["note"] == RS.HONESTY_NOTE


# ═════════════════════════════════════════════ URLs [C2]
PIN_URLS = {
    "nasdaq": "https://www.nasdaqtrader.com/dynamic/symdir/regsho/nasdaqth20261120.txt",
    "nyse": "https://www.nyse.com/api/regulatory/threshold-securities/download?selectedDate=2026-11-20&market=NYSE",
    "nyse_american": ("https://www.nyse.com/api/regulatory/threshold-securities/download?selectedDate=2026-11-20"
                      "&market=NYSE%20American"),
    "nyse_arca": ("https://www.nyse.com/api/regulatory/threshold-securities/download?selectedDate=2026-11-20"
                  "&market=NYSE%20Arca"),
    "cboe_bzx": ("https://cdn.cboe.com/resources/us/equities/market-statistics/reg-sho-threshold/"
                 "bzx_equities_reg_sho_threshold_20261120.txt"),
}


def _urls_for(d):
    return {mkt: RS.source_url(src, mkt, d) for src, mkt, _e, _f in RS.all_markets()}


def test_source_url_is_pinned_for_all_five_markets():
    assert _urls_for(date(2026, 11, 20)) == PIN_URLS
    assert RS.NYSE_MARKETS == (("nyse", "NYSE"), ("nyse_american", "NYSE American"), ("nyse_arca", "NYSE Arca"))


def test_NEGATIVE_a_lower_cased_nyse_market_name_breaks_the_url_pin(monkeypatch):
    monkeypatch.setattr(RS, "NYSE_MARKETS", (("nyse", "NYSE"), ("nyse_american", "nyse american"),
                                             ("nyse_arca", "NYSE Arca")))
    assert _urls_for(date(2026, 11, 20)) != PIN_URLS
    assert _urls_for(date(2026, 11, 20))["nyse_american"].endswith("market=nyse%20american")


def test_a_refresh_round_asks_exactly_the_pinned_urls_with_the_house_call_shape():
    _coll, http, ran = golden_round()
    want = {nasdaq_url(date(2026, 11, 20)), PIN_URLS["nyse"], PIN_URLS["nyse_american"], PIN_URLS["nyse_arca"],
            cboe_url(date(2026, 11, 19))}
    assert set(http.urls) == want and len(http.urls) == 5 and http.unexpected == []
    assert ran["ran"] == ["nasdaq", "nyse", "cboe_bzx"] and ran["calls"] == 5
    for kw in http.kwargs:
        assert kw["allow_redirects"] is False and kw["timeout"] == RS.RS_HTTP_TIMEOUT_SEC
        assert kw["headers"] == RS.HTTP_HEADERS


# ═════════════════════════════════════════════ calendar
def test_expected_trade_date_worked_clocks():
    assert [RS.expected_trade_date(s, NOW) for s in RS.SOURCES] == [date(2026, 11, 20)] * 2 + [date(2026, 11, 19)]
    mon = datetime(2026, 11, 23, 10, 0, tzinfo=ET)
    assert [RS.expected_trade_date(s, mon) for s in RS.SOURCES] == [date(2026, 11, 20)] * 3
    fri = datetime(2026, 11, 27, 10, 0, tzinfo=ET)
    assert RS.expected_trade_date(NASDAQ, fri) == date(2026, 11, 25)
    assert RS.publish_dt(CBOE, date(2026, 11, 20)) == datetime(2026, 11, 23, 3, 30, tzinfo=ET)
    assert RS.bdays_between(date(2026, 11, 20), date(2026, 11, 23)) == 1
    assert RS.bdays_between(date(2026, 11, 25), date(2026, 11, 27)) == 1        # 11-26 is a holiday
    assert RS.bdays_between(date(2026, 11, 20), date(2026, 11, 20)) == 0


def test_weekend_asks_friday_for_nasdaq_and_thursday_for_cboe_only():
    _coll, http, _ran = golden_round()
    assert [u for u in http.urls if "nasdaqth" in u] == [nasdaq_url(date(2026, 11, 20))]
    assert [u for u in http.urls if "cboe" in u] == [cboe_url(date(2026, 11, 19))]


def test_holiday_walk_back_asks_the_day_before_thanksgiving_never_the_holiday():
    coll = StandIn()
    fri = datetime(2026, 11, 27, 10, 0, tzinfo=ET)
    body = synthetic_nasdaq(date(2026, 11, 25), ["AKAN|SYNTHETIC|S|Y|N|"])
    http = FakeHTTP({nasdaq_url(date(2026, 11, 25)): Resp(200, body)})
    st = RS.refresh_source(NASDAQ, coll, fri, http=http)
    assert http.urls == [nasdaq_url(date(2026, 11, 25))]
    assert nasdaq_url(date(2026, 11, 26)) not in http.urls
    assert st["result"] == "found" and st["attempt_for"] == "2026-11-25"


def test_nasdaq_302_to_http404_walks_to_the_previous_business_day():
    coll = StandIn()
    now = datetime(2026, 11, 23, 23, 30, tzinfo=ET)
    ans = fixture_answers()
    ans[nasdaq_url(date(2026, 11, 23))] = NASDAQ_302
    http = FakeHTTP(ans)
    st = RS.refresh_source(NASDAQ, coll, now, http=http)
    assert http.urls == [nasdaq_url(date(2026, 11, 23)), nasdaq_url(date(2026, 11, 20))]
    assert st["result"] == "missing_walked" and st["good_date"] == "2026-11-20" and st["errors"] == 0
    loaded = RS.load(coll)
    v = RS.market_view(NASDAQ, "nasdaq", loaded, now)
    assert v["status"] == "ok" and v["behind"] is True and v["stale"] is False
    p = RS.payload(FakeDB(coll), now, kick=False)
    assert p["sources"][0]["text"] == "Nasdaq threshold list for 11/20 · 76 names (none published for 11/23)"
    assert p["items"]["AKAN"]["stale"] is False


# ═════════════════════════════════════════════ [C2] a zero-row list is believed after two reads
T1110 = datetime(2026, 11, 10, 23, 30, tzinfo=ET)


def _round_1110(coll, http, now):
    return RS.refresh_due(coll, now, http=http)


def test_zero_row_nyse_market_is_pending_until_a_second_read_confirms_it():
    coll = StandIn()
    seed_list(coll, "cboe_bzx", date(2026, 11, 9), ["SYNTHFUND"])        # SYNTHETIC: Cboe's E (11-09) held
    http = FakeHTTP(fixture_answers())
    r1 = _round_1110(coll, http, T1110)
    assert r1["calls"] == 4 and http.unexpected == []                      # Nasdaq + the three NYSE markets
    nyse_doc = coll.docs["list|nyse|2026-11-10"]
    assert nyse_doc["n"] == 0 and nyse_doc["confirmed_at"] is None
    assert coll.docs["list|nyse_american|2026-11-10"]["confirmed_at"] is not None
    p = RS.payload(FakeDB(coll), T1110, kick=False, check=["ZZZZ"])
    nyse = p["sources"][1]
    assert nyse["status"] == "pending" and nyse["text"] == "NYSE threshold list for 11/10 · 0 names (re-reading to confirm)"
    assert p["complete"] is False and p["check"]["ZZZZ"] == "unknown"
    assert p["fault_text"] is None                                           # held (zero rows) ≠ nothing held

    r2 = _round_1110(coll, http, T1110 + timedelta(minutes=10))
    assert r2["calls"] == 0

    first_fetch = coll.docs["list|nyse|2026-11-10"]["fetched_at"]
    later = T1110 + timedelta(minutes=RS.RS_RETRY_MIN + 1)
    n_before = len(http.urls)
    r3 = _round_1110(coll, http, later)
    assert r3["calls"] == 1 and http.urls[n_before:] == [nyse_url("nyse", date(2026, 11, 10))]
    doc = coll.docs["list|nyse|2026-11-10"]
    assert doc["confirmed_at"] is not None and doc["revised_at"] is None
    assert doc["fetched_at"] == first_fetch                                  # [C9] the first write stays
    p = RS.payload(FakeDB(coll), later, kick=False, check=["ZZZZ"])
    assert p["sources"][1]["status"] == "ok" and p["complete"] is True and p["check"]["ZZZZ"] == "off"
    assert p["sources"][1]["text"] == "NYSE threshold list for 11/10 · 0 names"


def test_zero_row_re_read_that_returns_a_row_replaces_the_list():
    coll = StandIn()
    seed_list(coll, "cboe_bzx", date(2026, 11, 9), ["SYNTHFUND"])
    ans = fixture_answers()
    http = FakeHTTP(ans)
    _round_1110(coll, http, T1110)
    ans[nyse_url("nyse", date(2026, 11, 10))] = Resp(200, synthetic_nyse(
        date(2026, 11, 10), ["ZZZT|SYNTHETIC LATE ROW|NYSE|Y||"]))
    http.answers = ans
    later = T1110 + timedelta(minutes=RS.RS_RETRY_MIN + 1)
    assert _round_1110(coll, http, later)["calls"] == 1
    doc = coll.docs["list|nyse|2026-11-10"]
    assert doc["symbols"] == ["ZZZT"] and doc["n"] == 1 and doc["revised_at"] and doc["confirmed_at"]
    p = RS.payload(FakeDB(coll), later, kick=False, check=["ZZZT"])
    assert p["check"]["ZZZT"] == "on" and p["items"]["ZZZT"]["market"] == "nyse"


def test_nyse_bank_holiday_reads_missing_and_keeps_the_confirmed_lists():
    coll = StandIn()
    for name, mkt in (("nyse_NYSE_2026-11-10.txt", "nyse"), ("nyse_NYSE-American_2026-11-10.txt", "nyse_american"),
                      ("nyse_NYSE-Arca_2026-11-10.txt", "nyse_arca")):
        syms, _ = parse_fixture(name, NYSE, date(2026, 11, 10), mkt)
        seed_list(coll, mkt, date(2026, 11, 10), syms, confirmed=True)
    now = datetime(2026, 11, 12, 0, 30, tzinfo=ET)
    http = FakeHTTP(fixture_answers())
    st = RS.refresh_source(NYSE, coll, now, http=http)
    assert set(http.urls) == {nyse_url(m, date(2026, 11, 11)) for m in ("nyse", "nyse_american", "nyse_arca")}
    assert st["result"] == "missing_walked" and st["good_date"] == "2026-11-10"
    assert not [k for k in coll.docs if "2026-11-11" in k]
    loaded = RS.load(coll)
    for mkt in ("nyse", "nyse_american", "nyse_arca"):
        v = RS.market_view(NYSE, mkt, loaded, now)
        assert v["status"] == "ok" and v["behind"] is True and v["as_of"] == "2026-11-10"
    # the throttle: a second round inside RS_RETRY_MIN asks nothing
    assert not RS.is_due(NYSE, loaded, now + timedelta(minutes=RS.RS_RETRY_MIN - 1))
    assert RS.is_due(NYSE, loaded, now + timedelta(minutes=RS.RS_RETRY_MIN))


def test_throttle_no_call_when_held_is_current_or_inside_the_retry():
    coll, http, _ = golden_round()
    n = len(http.urls)
    assert RS.refresh_due(coll, NOW + timedelta(minutes=10), http=http)["calls"] == 0
    later = RS.refresh_due(coll, NOW + timedelta(hours=3), http=http)
    assert later["calls"] == 0 and later["ran"] == []
    assert len(http.urls) == n
    loaded = RS.load(coll)
    assert not any(RS.is_due(s, loaded, NOW + timedelta(hours=3)) for s in RS.SOURCES)


# ═════════════════════════════════════════════ [C8] strikes
def _held_round_then_timeouts(now_first, now_fail, held_nasdaq_date):
    coll, _http, _ = golden_round()
    if held_nasdaq_date != date(2026, 11, 20):
        del coll.docs["list|nasdaq|2026-11-20"]
        syms, _ = parse_fixture("nasdaq_%s.txt" % held_nasdaq_date.strftime("%Y%m%d"), NASDAQ, held_nasdaq_date)
        seed_list(coll, "nasdaq", held_nasdaq_date, syms)
    E = RS.expected_trade_date(NASDAQ, now_fail)
    http = FakeHTTP({nasdaq_url(E): ReadTimeout("synthetic")})
    return coll, http


def test_one_timeout_with_a_held_list_is_quiet_pending_then_two_read_failed():
    t = datetime(2026, 11, 23, 23, 30, tzinfo=ET)                          # E = 11-23, the 11-20 list held
    coll, http = _held_round_then_timeouts(NOW, t, date(2026, 11, 20))
    st = RS.refresh_source(NASDAQ, coll, t, http=http)
    assert st["result"] == "error" and st["error"] == "timeout" and st["errors"] == 1
    assert http.urls == [nasdaq_url(date(2026, 11, 23))]                    # an error never walks back
    p = RS.payload(FakeDB(coll), t, kick=False)
    nas = p["sources"][0]
    assert nas["status"] == "pending" and nas["stale"] is False and nas["error"] == "timeout"
    assert p["items"]["AKAN"]["stale"] is False and p["fault_text"] is None
    loaded = RS.load(coll)
    assert not RS.is_due(NASDAQ, loaded, t + timedelta(minutes=RS.RS_ERROR_RETRY_MIN - 1))
    assert RS.is_due(NASDAQ, loaded, t + timedelta(minutes=RS.RS_ERROR_RETRY_MIN))

    t2 = t + timedelta(minutes=RS.RS_ERROR_RETRY_MIN)
    st = RS.refresh_source(NASDAQ, coll, t2, http=http)
    assert st["errors"] == RS.RS_ERROR_STRIKES
    p = RS.payload(FakeDB(coll), t2, kick=False, check=["AKAN"])
    a = p["items"]["AKAN"]
    assert p["check"]["AKAN"] == "on" and a["stale"] is True
    for k in ("chip", "short", "label"):
        assert a[k].endswith(" · stale"), a[k]
    assert a["title"].endswith(RS.STALE_TITLE % "11/20")
    nas = p["sources"][0]
    assert nas["ok"] is False and nas["status"] == "failed" and nas["as_of"] == "2026-11-20"
    assert p["fault_text"] == ("🔒 Hard to borrow tags may be missing or out of date: Nasdaq threshold list could "
                               "not be read — last good list 11/20.")


def test_worked_fault_string_nasdaq_errored_twice_with_the_1119_list_held():
    t = datetime(2026, 11, 21, 10, 0, tzinfo=ET)                           # Sat: E = 11-20, 11-19 held
    coll, http = _held_round_then_timeouts(NOW, t, date(2026, 11, 19))
    RS.refresh_source(NASDAQ, coll, t, http=http)
    RS.refresh_source(NASDAQ, coll, t + timedelta(minutes=5), http=http)
    p = RS.payload(FakeDB(coll), t + timedelta(minutes=5), kick=False)
    assert p["fault_text"] == ("🔒 Hard to borrow tags may be missing or out of date: Nasdaq threshold list could "
                               "not be read — last good list 11/19.")


def test_NEGATIVE_one_error_with_nothing_held_is_failed_at_once():
    coll = StandIn()
    http = FakeHTTP({nasdaq_url(date(2026, 11, 20)): ReadTimeout("synthetic")})
    st = RS.refresh_source(NASDAQ, coll, NOW, http=http)
    assert st["errors"] == 1
    v = RS.market_view(NASDAQ, "nasdaq", RS.load(coll), NOW)
    assert v["status"] == "failed" and v["as_of"] is None
    p = RS.payload(FakeDB(coll), NOW, kick=False)
    assert "Nasdaq threshold list could not be read" in p["fault_text"]


# ═════════════════════════════════════════════ [C7] state first; a dead worker is throttled
def test_running_state_is_written_before_the_first_outside_call():
    coll = StandIn()
    seen = []

    def on_call(url):
        st = coll.docs.get("state|nasdaq")
        seen.append(st and st["result"])
    http = FakeHTTP(fixture_answers(), on_call=on_call)
    RS.refresh_source(NASDAQ, coll, NOW, http=http)
    assert seen and seen[0] == "running"
    assert coll.docs["state|nasdaq"]["result"] == "found"


def test_a_final_state_write_that_raises_leaves_running_and_the_next_round_waits():
    coll = StandIn()
    coll.fail_final_state = True
    http = FakeHTTP({nasdaq_url(date(2026, 11, 20)): ReadTimeout("synthetic")})
    RS.refresh_source(NASDAQ, coll, NOW, http=http)
    assert coll.docs["state|nasdaq"]["result"] == "running"
    coll.fail_final_state = False
    n = len(http.urls)
    # an `error` state would be due after RS_ERROR_RETRY_MIN; a `running` one waits RS_RETRY_MIN
    out = RS.refresh_due(coll, NOW + timedelta(minutes=RS.RS_ERROR_RETRY_MIN + 1), http=http)
    assert "nasdaq" not in out["ran"] and http.urls[n:].count(nasdaq_url(date(2026, 11, 20))) == 0


def test_NEGATIVE_a_state_write_that_raises_first_abandons_the_source_with_no_call():
    class Broken(StandIn):
        def replace_one(self, flt, doc, upsert=False):
            raise RuntimeError("synthetic: Mongo write refused")
    coll = Broken()
    http = FakeHTTP(fixture_answers())
    assert RS.refresh_source(NASDAQ, coll, NOW, http=http) is None
    assert http.urls == []


def test_kick_refresh_floor_starts_one_worker_inside_kick_min_sec(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(RS, "_mono", lambda: clock["t"])
    ran = []
    monkeypatch.setattr(RS, "refresh_due", lambda coll, now_et=None, http=None: ran.append(1))
    assert RS.kick_refresh(StandIn(), NOW, http=FakeHTTP()) is True
    RS._bg["thread"].join(5)
    assert RS._bg["running"] is False
    clock["t"] += RS.RS_KICK_MIN_SEC - 1
    assert RS.kick_refresh(StandIn(), NOW, http=FakeHTTP()) is False
    assert ran == [1]
    clock["t"] += 1
    assert RS.kick_refresh(StandIn(), NOW, http=FakeHTTP()) is True
    RS._bg["thread"].join(5)
    assert ran == [1, 1]


def test_kick_refresh_is_single_flight(monkeypatch):
    gate = threading.Event()
    ran = []

    def slow(coll, now_et=None, http=None):
        ran.append(1)
        gate.wait(5)
    monkeypatch.setattr(RS, "refresh_due", slow)
    assert RS.kick_refresh(StandIn(), NOW, http=FakeHTTP()) is True
    monkeypatch.setattr(RS, "_mono", lambda: 10 ** 9)                       # past the floor: only the flag refuses
    assert RS.kick_refresh(StandIn(), NOW, http=FakeHTTP()) is False
    gate.set()
    RS._bg["thread"].join(5)
    assert ran == [1] and RS._bg["running"] is False


def test_a_thread_that_cannot_start_resets_the_flag(monkeypatch):
    class NoThread:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")
    real_thread = RS.threading.Thread
    monkeypatch.setattr(RS.threading, "Thread", NoThread)
    assert RS.kick_refresh(StandIn(), NOW, http=FakeHTTP()) is False
    assert RS._bg["running"] is False and RS._bg["last_start"] is None
    monkeypatch.setattr(RS.threading, "Thread", real_thread)
    monkeypatch.setattr(RS, "refresh_due", lambda coll, now_et=None, http=None: None)
    assert RS.kick_refresh(StandIn(), NOW, http=FakeHTTP()) is True
    RS._bg["thread"].join(5)


# ═════════════════════════════════════════════ [C4] skipped symbol cells
def test_an_odd_symbol_cell_is_skipped_and_counted_never_rewritten():
    ans = fixture_answers()
    text = _body("nasdaq_20261120.txt")
    lines = text.split("\r\n")
    lines.insert(2, "ABCpA|SYNTHETIC PREFERRED ROW|S|Y|N|")                # SYNTHETIC
    ans[nasdaq_url(date(2026, 11, 20))] = Resp(200, "\r\n".join(lines))
    coll, _http, _ = golden_round(ans)
    p = RS.payload(FakeDB(coll), NOW, kick=False, check=["ABCPA", "ABCpA", "AKAN"])
    nas = p["sources"][0]
    assert nas["status"] == "ok" and nas["skipped"] == 1 and nas["n"] == 76
    assert nas["text"].endswith(" · 1 not read")
    assert "ABCPA" not in p["items"] and "ABCpA" not in p["items"]
    assert p["check"] == {"ABCPA": "off", "AKAN": "on"}                   # keys upper-cased; ABCpA never ABCPA


def test_NEGATIVE_more_than_the_cap_of_unreadable_symbols_is_an_error_never_a_short_list():
    rows = ["x%d|SYNTHETIC|S|Y|N|" % i for i in range(RS.RS_MAX_SKIPPED_ROWS + 1)] + ["AKAN|SYNTHETIC|S|Y|N|"]
    body = synthetic_nasdaq(date(2026, 11, 20), rows)
    with pytest.raises(RS.Malformed):
        RS.parse_list(body, header=RS.NASDAQ_HEADER, flag_col=3, want=date(2026, 11, 20))
    r = RS.fetch_market(NASDAQ, "nasdaq", date(2026, 11, 20),
                        http=FakeHTTP({nasdaq_url(date(2026, 11, 20)): Resp(200, body)}))
    assert r == {"result": "error", "error": "malformed"}
    ok_rows = rows[1:]                                                       # exactly the cap → still a list
    syms, skipped = RS.parse_list(synthetic_nasdaq(date(2026, 11, 20), ok_rows), header=RS.NASDAQ_HEADER,
                                  flag_col=3, want=date(2026, 11, 20))
    assert syms == ["AKAN"] and skipped == RS.RS_MAX_SKIPPED_ROWS


# ═════════════════════════════════════════════ [C9] history kept; newest per market
def test_old_list_docs_survive_and_load_reads_the_newest_per_market():
    coll = StandIn()
    seed_list(coll, "nasdaq", date(2026, 11, 20), ["AKAN"])
    seed_list(coll, "nasdaq", date(2026, 9, 21), ["OLDNAME"])               # inserted after the newer one
    seed_list(coll, "nasdaq", date(2026, 11, 19), ["MIDNAME"])
    loaded = RS.load(coll)
    assert loaded["lists"]["nasdaq"]["trade_date"] == "2026-11-20"
    http = FakeHTTP(fixture_answers())
    RS.refresh_due(coll, NOW, http=http)
    assert "list|nasdaq|2026-09-21" in coll.docs and "list|nasdaq|2026-11-19" in coll.docs
    assert nasdaq_url(date(2026, 11, 20)) not in http.urls                  # held ≥ E: never re-fetched


# ═════════════════════════════════════════════ [C1] faults and Mongo down
def test_mongo_down_names_exactly_the_three_stock_lists_and_never_calls_out():
    http = FakeHTTP(fixture_answers())
    p = RS.payload(None, NOW, http=http, check=["AKAN"])
    assert http.urls == [] and RS._bg["thread"] is None and RS._bg["running"] is False
    assert p["fault_text"] == ("🔒 Hard to borrow tags may be missing or out of date: Nasdaq threshold list not read "
                               "yet; NYSE threshold list not read yet; NYSE American threshold list not read yet.")
    assert p["items"] == {} and p["check"] == {"AKAN": "unknown"} and p["as_of"] is None
    assert all(s["status"] == "pending" for s in p["sources"]) and p["refreshing"] is False


def test_NEGATIVE_first_read_with_a_worker_running_draws_no_fault_line(monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(RS, "refresh_due", lambda coll, now_et=None, http=None: gate.wait(5))
    p = RS.payload(FakeDB(), NOW, kick=True, http=FakeHTTP())
    try:
        assert p["refreshing"] is True and p["retry_after_sec"] == RS.RS_RETRY_AFTER_SEC
        assert p["fault_text"] is None and p["items"] == {}
    finally:
        gate.set()
        RS._bg["thread"].join(5)


def test_NEGATIVE_the_same_read_with_no_worker_started_draws_the_fault_line(monkeypatch):
    class NoThread:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")
    monkeypatch.setattr(RS.threading, "Thread", NoThread)
    p = RS.payload(FakeDB(), NOW, kick=True, http=FakeHTTP())
    assert p["refreshing"] is False and p["retry_after_sec"] is None
    assert p["fault_text"] and "Nasdaq threshold list not read yet" in p["fault_text"]


def _route_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(SAPI.router)
    return TestClient(app)


def test_route_never_500s_a_raising_read_serves_the_fault_payload(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(RS, "payload", boom)
    r = _route_client().get("/short-interest/reg-sho?check=AKAN")
    assert r.status_code == 200
    j = r.json()
    assert j["kind"] == RS.KIND and j["fault_text"] == RS.FAULT_UNREADABLE % (RS.GLYPH, RS.TAG_WORDS)
    assert j == RS.fault_payload()
    assert j["fault_text"] == ("🔒 Hard to borrow tags could not be read — a missing tag does not mean the name is "
                               "off the list.")
    assert [s["status"] for s in j["sources"]] == ["pending"] * 5 and j["complete"] is False


def test_route_reads_the_check_list_and_with_mongo_down_says_unknown(monkeypatch):
    monkeypatch.setattr(SIC, "_get_db", lambda: None)
    r = _route_client().get("/short-interest/reg-sho?check=akan, AKANW ,")
    assert r.status_code == 200
    j = r.json()
    assert j["check"] == {"AKAN": "unknown", "AKANW": "unknown"} and j["fault_text"]
    assert RS.API_PATH == "/short-interest/reg-sho"


def test_route_with_no_check_serves_no_check_key(monkeypatch):
    monkeypatch.setattr(SIC, "_get_db", lambda: None)
    j = _route_client().get("/short-interest/reg-sho").json()
    assert "check" not in j and j["kind"] == RS.KIND


# ═════════════════════════════════════════════ symbols
def test_alias_keys_serve_both_house_spellings_and_count_once():
    assert RS.norm_symbol("brk-b") == RS.norm_symbol("BRK B") == RS.norm_symbol("BRK/B") == "BRK.B"
    assert RS.norm_symbol(" akanw ") == "AKANW" and RS.alias_keys("AKAN") == ("AKAN",)
    assert RS.alias_keys("BRK.B") == ("BRK.B", "BRK-B")
    coll, _h, _ = golden_round()
    seed_list(coll, "nasdaq", date(2026, 11, 20), ["AKAN", "BRK.B"])        # SYNTHETIC replacement
    p = RS.payload(FakeDB(coll), NOW, kick=False, check=["brk-b", "BRK.B"])
    assert p["items"]["BRK.B"] == p["items"]["BRK-B"] and p["items"]["BRK.B"]["symbol"] == "BRK.B"
    assert p["n"] == 2 + 1 + 2 + 24 + 57
    assert p["check"] == {"BRK-B": "on", "BRK.B": "on"}


def test_NEGATIVE_exact_match_only():
    p = build_golden_payload()
    n20, _ = parse_fixture("nasdaq_20261120.txt", NASDAQ, date(2026, 11, 20))
    assert "AKANW" not in n20 and "ACON" not in n20
    coll, _h, _ = golden_round()
    p = RS.payload(FakeDB(coll), NOW, kick=False, check=["AKANW", "ACON", " akan ", "aconw"])
    assert "AKANW" not in p["items"] and "ACON" not in p["items"]
    assert p["check"] == {"AKANW": "off", "ACON": "off", "AKAN": "on", "ACONW": "on"}


def test_NEGATIVE_not_on_any_list_with_all_sources_ok_is_absent_and_off():
    coll, _h, _ = golden_round()
    p = RS.payload(FakeDB(coll), NOW, kick=False, check=["ZZZZ"])
    assert "ZZZZ" not in p["items"] and p["check"]["ZZZZ"] == "off" and p["complete"] is True


def test_NEGATIVE_nothing_held_and_every_source_unreadable_is_unknown_never_off():
    ans = {u: Resp(500, "synthetic") for u in fixture_answers()}
    coll, http, _ = golden_round(ans)
    p = RS.payload(FakeDB(coll), NOW, kick=False, check=["AKAN", "ZZZZ"])
    assert p["items"] == {} and p["as_of"] is None and p["n"] == 0
    assert p["check"]["AKAN"] != "off" and p["check"] == {"AKAN": "unknown", "ZZZZ": "unknown"}
    assert all(s["status"] == "failed" and s["error"] == "http_500" for s in p["sources"])
    assert p["fault_text"] is not None


def test_NEGATIVE_one_source_failed_with_nothing_held_leaves_absent_names_unknown():
    ans = fixture_answers()
    ans[nasdaq_url(date(2026, 11, 20))] = Resp(500, "synthetic")
    coll, _h, _ = golden_round(ans)
    p = RS.payload(FakeDB(coll), NOW, kick=False, check=["ZZZZ", "OPTT"])
    assert p["check"] == {"ZZZZ": "unknown", "OPTT": "on"}
    assert p["sources"][0]["status"] == "failed" and p["complete"] is False


# ═════════════════════════════════════════════ [C3] fund lists never raise the line
def _seed_for_E(coll, markets, now):
    for _src, mkt, _e, _f in RS.all_markets():
        if mkt in markets:
            src = next(s for s, m, _x, _y in RS.all_markets() if m == mkt)
            seed_list(coll, mkt, RS.expected_trade_date(src, now), ["SYN" + mkt.upper()[:3]])


def _seed_error_state(coll, key, now, errors=1):
    src = next(s for s in RS.SOURCES if s["key"] == key)
    E = RS.expected_trade_date(src, now).isoformat()
    at = now.astimezone(ZoneInfo("UTC")).isoformat()
    coll.docs["state|%s" % key] = {"_id": "state|%s" % key, "kind": "state", "source": key, "attempt_at": at,
                                   "attempt_for": E, "result": "error", "error": "timeout", "errors": errors,
                                   "good_date": None, "checked_at": None}


def test_NEGATIVE_fund_lists_failing_raise_no_fault_line():
    coll = StandIn()
    _seed_for_E(coll, {"nasdaq", "nyse", "nyse_american"}, NOW)
    _seed_error_state(coll, "nyse", NOW)
    _seed_error_state(coll, "cboe_bzx", NOW)
    p = RS.payload(FakeDB(coll), NOW, kick=False, check=["ZZZZ"])
    st = {s["market"]: s["status"] for s in p["sources"]}
    assert st == {"nasdaq": "ok", "nyse": "ok", "nyse_american": "ok", "nyse_arca": "failed", "cboe_bzx": "failed"}
    assert p["fault_text"] is None and p["complete"] is False and p["check"]["ZZZZ"] == "unknown"


def test_NEGATIVE_nasdaq_failed_alone_names_nasdaq_and_not_the_fund_lists():
    coll = StandIn()
    _seed_for_E(coll, {"nyse", "nyse_american"}, NOW)
    _seed_error_state(coll, "nasdaq", NOW)
    _seed_error_state(coll, "nyse", NOW)
    _seed_error_state(coll, "cboe_bzx", NOW)
    p = RS.payload(FakeDB(coll), NOW, kick=False)
    assert "Nasdaq" in p["fault_text"] and "Arca" not in p["fault_text"] and "Cboe" not in p["fault_text"]
    assert p["fault_text"] == ("🔒 Hard to borrow tags may be missing or out of date: Nasdaq threshold list could "
                               "not be read.")


# ═════════════════════════════════════════════ [C10] the measured "no list" answers only
def test_NEGATIVE_a_plain_404_and_a_nosuchkey_404_are_errors_and_never_walk_back():
    for src, mkt, url in ((NASDAQ, "nasdaq", nasdaq_url(date(2026, 11, 20))),
                          (CBOE, "cboe_bzx", cboe_url(date(2026, 11, 19)))):
        coll = StandIn()
        body = "<Error><Code>NoSuchKey</Code></Error>" if src is CBOE else "Not Found"     # SYNTHETIC
        http = FakeHTTP({url: Resp(404, body)})
        st = RS.refresh_source(src, coll, NOW, http=http)
        assert http.urls == [url]
        assert st["result"] == "error" and st["error"] == "unseen_404"


def test_NEGATIVE_a_403_without_access_denied_and_a_302_elsewhere_are_errors():
    d = date(2026, 11, 20)
    waf = FakeHTTP({cboe_url(d): Resp(403, "<html>Attention Required! (SYNTHETIC WAF page)</html>")})
    assert RS.fetch_market(CBOE, "cboe_bzx", d, http=waf) == {"result": "error", "error": "http_403"}
    real = FakeHTTP(fixture_answers())
    assert RS.fetch_market(CBOE, "cboe_bzx", d, http=real) == {"result": "missing"}
    other = FakeHTTP({nasdaq_url(d): Resp(302, "", {"Location": "https://login.example.invalid/"})})
    assert RS.fetch_market(NASDAQ, "nasdaq", d, http=other) == {"result": "error", "error": "redirect"}
    assert RS.fetch_market(NASDAQ, "nasdaq", d, http=FakeHTTP({nasdaq_url(d): NASDAQ_302})) == {"result": "missing"}
    # a Cboe-shaped 403 on Nasdaq and a Nasdaq-shaped 302 on Cboe are errors too
    assert RS.fetch_market(NASDAQ, "nasdaq", d, http=FakeHTTP({nasdaq_url(d): Resp(
        403, _body("cboe_bzx_20261120_missing_403.xml"))}))["result"] == "error"
    assert RS.fetch_market(CBOE, "cboe_bzx", d, http=FakeHTTP({cboe_url(d): NASDAQ_302}))["result"] == "error"


@pytest.mark.parametrize("answer,code", [(Resp(500, "x"), "http_500"), (ReadTimeout("synthetic"), "timeout"),
                                         (ValueError("synthetic"), "exception"), (Resp(200, None), "malformed")])
def test_NEGATIVE_transport_failures_are_errors(answer, code):
    d = date(2026, 11, 20)
    http = FakeHTTP({nasdaq_url(d): answer})
    assert RS.fetch_market(NASDAQ, "nasdaq", d, http=http) == {"result": "error", "error": code}
    assert http.kwargs[0]["allow_redirects"] is False and http.kwargs[0]["timeout"] == RS.RS_HTTP_TIMEOUT_SEC


# ═════════════════════════════════════════════ malformed → error, never an empty list
def _nasdaq_kw(d=date(2026, 11, 20)):
    return dict(header=RS.NASDAQ_HEADER, flag_col=3, want=d)


@pytest.mark.parametrize("label,body", [
    ("html", "<!DOCTYPE html><html><body>SYNTHETIC block page</body></html>"),
    ("wrong header", "Symbol|Name|Flag\r\nAKAN|X|Y\r\n20261120230006\r\n"),
    ("truncated", "\r\n".join(_body("nasdaq_20261120.txt").split("\r\n")[:20])),
    ("other day", synthetic_nasdaq(date(2026, 11, 19), ["AKAN|SYNTHETIC|S|Y|N|"])),
    ("bad flag", synthetic_nasdaq(date(2026, 11, 20), ["AKAN|SYNTHETIC|S|Q|N|"])),
    ("no flag cell", synthetic_nasdaq(date(2026, 11, 20), ["AKAN|SYNTHETIC|S"])),
    ("oversize", synthetic_nasdaq(date(2026, 11, 20), ["AKAN|" + "X" * (RS.RS_MAX_BYTES + 1) + "|S|Y|N|"])),
    ("empty", ""),
])
def test_NEGATIVE_malformed_nasdaq_bodies_are_errors(label, body):
    with pytest.raises(RS.Malformed):
        RS.parse_list(body, **_nasdaq_kw())
    http = FakeHTTP({nasdaq_url(date(2026, 11, 20)): Resp(200, body)})
    assert RS.fetch_market(NASDAQ, "nasdaq", date(2026, 11, 20), http=http) == {"result": "error",
                                                                                 "error": "malformed"}


def test_NEGATIVE_a_nyse_row_for_another_market_is_malformed():
    d = date(2026, 11, 20)
    body = synthetic_nyse(d, ["OPTT|SYNTHETIC|NYSE Arca|Y||"])
    with pytest.raises(RS.Malformed):
        RS.parse_list(body, header=RS.NYSE_HEADER, flag_col=3, want=d, market_name="NYSE American")
    assert RS.parse_list(body.replace("NYSE Arca", "NYSE American"), header=RS.NYSE_HEADER, flag_col=3, want=d,
                         market_name="NYSE American") == (["OPTT"], 0)


def test_NEGATIVE_too_many_rows_is_malformed(monkeypatch):
    monkeypatch.setattr(RS, "RS_MAX_ROWS", 3)
    rows = ["A%d|SYNTHETIC|S|Y|N|" % i for i in range(4)]
    with pytest.raises(RS.Malformed):
        RS.parse_list(synthetic_nasdaq(date(2026, 11, 20), rows), **_nasdaq_kw())


def test_a_bom_and_blank_lines_are_read():
    body = "﻿" + synthetic_nasdaq(date(2026, 11, 20), ["AKAN|SYNTHETIC|S|Y|N|", "", "  "])
    assert RS.parse_list(body, **_nasdaq_kw()) == (["AKAN"], 0)


def test_NEGATIVE_a_nasdaq_row_flagged_N_is_not_on_the_list():
    body = synthetic_nasdaq(date(2026, 11, 20), ["AKAN|SYNTHETIC|S|N|N|", "ZZZT|SYNTHETIC|S|Y|N|"])
    assert RS.parse_list(body, **_nasdaq_kw()) == (["ZZZT"], 0)


# ═════════════════════════════════════════════ behind beyond the grace
def test_NEGATIVE_behind_beyond_the_grace_reads_failed_and_stale():
    coll = StandIn()
    seed_list(coll, "nasdaq", date(2026, 11, 10), ["AKAN"])                # SYNTHETIC old list
    loaded = RS.load(coll)
    v = RS.market_view(NASDAQ, "nasdaq", loaded, NOW)
    assert v["status"] == "pending" and v["stale"] is True                  # no finished state for E yet
    coll.docs["state|nasdaq"] = {"_id": "state|nasdaq", "kind": "state", "source": "nasdaq",
                                 "attempt_at": NOW.astimezone(ZoneInfo("UTC")).isoformat(),
                                 "attempt_for": "2026-11-20", "result": "missing_walked", "error": None,
                                 "errors": 0, "good_date": "2026-11-10", "checked_at": None}
    p = RS.payload(FakeDB(coll), NOW, kick=False)
    assert p["sources"][0]["status"] == "failed" and p["sources"][0]["stale"] is True
    assert p["items"]["AKAN"]["stale"] is True and p["items"]["AKAN"]["chip"].endswith(" · stale")
    assert p["sources"][0]["text"] == "Nasdaq threshold list could not be read — last good list 11/10"


def _finished_state(coll, src, now, *, result="missing_walked", attempt_at=None):
    E = RS.expected_trade_date(src, now).isoformat()
    at = (attempt_at or now).astimezone(ZoneInfo("UTC")).isoformat()
    coll.docs["state|%s" % src["key"]] = {"_id": "state|%s" % src["key"], "kind": "state", "source": src["key"],
                                          "attempt_at": at, "attempt_for": E, "result": result, "error": None,
                                          "errors": 0, "good_date": None, "checked_at": at}


def _bdays_back(d, n):
    for _ in range(n):
        d = SR.prev_business_day(d - timedelta(days=1))
    return d


@pytest.mark.parametrize("extra,status,stale", [(0, "ok", False), (1, "failed", True)])
def test_the_grace_boundary_is_pinned_at_exactly_RS_BEHIND_GRACE_BDAYS(extra, status, stale):
    E = RS.expected_trade_date(NASDAQ, NOW)
    held = _bdays_back(E, RS.RS_BEHIND_GRACE_BDAYS + extra)
    assert RS.bdays_between(held, E) == RS.RS_BEHIND_GRACE_BDAYS + extra
    coll = StandIn()
    seed_list(coll, "nasdaq", held, ["AKAN"])                                 # SYNTHETIC
    _finished_state(coll, NASDAQ, NOW)
    v = RS.market_view(NASDAQ, "nasdaq", RS.load(coll), NOW)
    assert v["status"] == status and v["behind"] is True and v["stale"] is stale
    assert v["as_of"] == held.isoformat()


def _unconfirmed_current_list(fetched_min_ago):
    coll = StandIn()
    E = RS.expected_trade_date(NASDAQ, NOW)
    fa = (NOW - timedelta(minutes=fetched_min_ago)).astimezone(ZoneInfo("UTC")).isoformat()
    seed_list(coll, "nasdaq", E, [], fetched_at=fa, confirmed=False)          # SYNTHETIC zero-row, unconfirmed
    return coll


def test_NEGATIVE_an_old_unconfirmed_list_with_a_fresh_state_is_not_due():
    coll = _unconfirmed_current_list(RS.RS_RETRY_MIN * 2)
    _finished_state(coll, NASDAQ, NOW, result="found", attempt_at=NOW - timedelta(minutes=RS.RS_RETRY_MIN - 1))
    assert not RS.is_due(NASDAQ, RS.load(coll), NOW)


def test_an_old_unconfirmed_list_is_due_once_the_state_is_RS_RETRY_MIN_old_or_absent():
    coll = _unconfirmed_current_list(RS.RS_RETRY_MIN * 2)
    _finished_state(coll, NASDAQ, NOW, result="found", attempt_at=NOW - timedelta(minutes=RS.RS_RETRY_MIN))
    assert RS.is_due(NASDAQ, RS.load(coll), NOW)
    del coll.docs["state|nasdaq"]
    assert RS.is_due(NASDAQ, RS.load(coll), NOW)


def test_NEGATIVE_a_young_unconfirmed_list_with_an_old_state_is_not_due():
    coll = _unconfirmed_current_list(RS.RS_RETRY_MIN - 1)
    _finished_state(coll, NASDAQ, NOW, result="found", attempt_at=NOW - timedelta(minutes=RS.RS_RETRY_MIN * 2))
    assert not RS.is_due(NASDAQ, RS.load(coll), NOW)


# ═════════════════════════════════════════════ [C6] the read never fetches
def test_NEGATIVE_the_read_with_kick_false_makes_no_call():
    coll = StandIn()
    http = FakeHTTP(fixture_answers())
    RS.payload(FakeDB(coll), NOW, kick=False, http=http)
    assert http.urls == [] and RS._bg["thread"] is None


def test_NEGATIVE_a_kicked_read_with_no_http_reaches_only_the_module_seam(outside_calls):
    coll = StandIn()
    p = RS.payload(FakeDB(coll), NOW, kick=True)
    assert p["refreshing"] is True or RS._bg["thread"] is not None
    RS._bg["thread"].join(5)
    assert outside_calls and all(isinstance(u, str) for u in outside_calls)
    assert PIN_URLS["nasdaq"] in outside_calls
    assert coll.docs["state|nasdaq"]["result"] == "error"
    outside_calls.clear()                                                    # the one test allowed to see it


def test_conftest_installs_the_session_refuser():
    src = (BACKEND / "tests" / "conftest.py").read_text()
    assert "RS._http = _refuse_http" in src and "RS._http = prior_rs_http" in src


def test_NEGATIVE_nyse_partial_failure_writes_nothing_for_that_date():
    coll = StandIn()
    ans = fixture_answers()
    ans[PIN_URLS["nyse_american"]] = ReadTimeout("synthetic")
    st = RS.refresh_source(NYSE, coll, NOW, http=FakeHTTP(ans))
    assert st["result"] == "error"
    assert not [k for k in coll.docs if k.startswith("list|")]


def test_NEGATIVE_nyse_all_three_empty_is_missing_not_found():
    d = date(2026, 11, 11)
    r = RS.fetch_source(NYSE, d, http=FakeHTTP(fixture_answers()))
    assert r == {"result": "missing"}
    r = RS.fetch_source(NYSE, date(2026, 11, 10), http=FakeHTTP(fixture_answers()))
    assert r["result"] == "found" and r["markets"]["nyse"]["symbols"] == []


# ═════════════════════════════════════════════ JSON-safe everywhere
def _all_payloads():
    out = [build_golden_payload(), RS.fault_payload(), RS.payload(None, NOW, kick=False, check=["AKAN"])]
    ans = {u: Resp(500, "x") for u in fixture_answers()}
    coll, _h, _ = golden_round(ans)
    out.append(RS.payload(FakeDB(coll), NOW, kick=False, check=["AKAN"]))
    t = datetime(2026, 11, 23, 23, 30, tzinfo=ET)
    coll, http = _held_round_then_timeouts(NOW, t, date(2026, 11, 20))
    RS.refresh_source(NASDAQ, coll, t, http=http)
    out.append(RS.payload(FakeDB(coll), t, kick=False, check=["AKAN"]))
    RS.refresh_source(NASDAQ, coll, t + timedelta(minutes=5), http=http)
    out.append(RS.payload(FakeDB(coll), t + timedelta(minutes=5), kick=False, check=["AKAN"]))
    coll = StandIn()
    seed_list(coll, "cboe_bzx", date(2026, 11, 9), ["SYNTHFUND"])
    RS.refresh_due(coll, T1110, http=FakeHTTP(fixture_answers()))
    out.append(RS.payload(FakeDB(coll), T1110, kick=False, check=["ZZZZ"]))
    return out


def test_every_payload_state_is_json_safe_and_typed():
    for p in _all_payloads():
        json.dumps(p, allow_nan=False)
        assert p["kind"] == RS.KIND and len(p["sources"]) == 5

        def walk(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    assert isinstance(k, str)
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
            else:
                assert x is None or isinstance(x, (str, bool, int)), x
        walk(p)
        assert not any(k.startswith("_") for s in p["sources"] for k in s)


def test_NEGATIVE_no_served_string_says_fee_impossible_squeeze_or_forecast():
    texts = [RS.rules_pick(), RS.HONESTY_NOTE, RS.NOT_A_SIGNAL, RS.FAULT_UNREADABLE % (RS.GLYPH, RS.TAG_WORDS)]
    for p in _all_payloads():
        texts += [p["note"]] + ([p["fault_text"]] if p["fault_text"] else [])
        texts += [s["text"] for s in p["sources"]]
        for it in p["items"].values():
            texts += [it["chip"], it["short"], it["label"], it["title"]]
    texts.append(RS.tag_block("AKAN", "nasdaq", "Nasdaq", "2026-11-20", True)["title"])
    assert len(texts) > 100
    for t in texts:
        assert not FORBIDDEN.search(t), t


# ═════════════════════════════════════════════ ℹ️ pick
def test_rules_pick_is_the_last_pick_and_the_section_is_at_the_cap():
    picks = SR.rules_section()["picks"]
    assert picks[-1] == RS.rules_pick()
    assert len(picks) == 8                                                   # the house cap — the next line must fold
    # 2026-11-26 floatguard (spec §1.7 / §6, predicted): pick 1 ('% of float = ') now names EXTREME too
    assert picks[1].startswith("% of float = ") and "EXTREME" in picks[1]
    (ext,) = [p for p in picks if "EXTREME" in p and not p.startswith("% of float = ")]
    assert picks.index(ext) == 2
    assert RS.rules_pick().startswith("🔒 Hard to borrow (the tag's name) = ")
    for w in ("Nasdaq, NYSE, NYSE American, NYSE Arca and Cboe BZX", "(Nasdaq, NYSE, NYSE American)",
              "10,000 shares", "0.5% of shares outstanding", "5 straight settlement days", RS.HONESTY_NOTE,
              "UNMEASURED",
              # 2026-11-24: the close-out day folds into this pick (the section is at its cap)
              "dates day 13", "SEC Regulation SHO Rule 203(b)(3)", "the buying may come from day 11",
              "Rule 204 already requires", "for a Rule 144 sale the count is 35, not 13",
              "Bank holidays (Columbus Day and Veterans Day) are not settlement days (Rule 203(c)(5))",
              "one settlement day later", "A rule date — it says nothing about price."):
        assert w in RS.rules_pick(), w


def test_rules_pick_moves_with_the_constants(monkeypatch):
    monkeypatch.setattr(RS, "REG_SHO_MIN_FTD_SHARES", 20_000)
    monkeypatch.setattr(RS, "REG_SHO_CONSEC_SETTLEMENT_DAYS", 6)
    assert "20,000 shares" in SR.rules_section()["picks"][-1] and "10,000" not in RS.rules_pick()
    assert "6 straight settlement days" in RS.rules_pick()


def test_NEGATIVE_a_failing_pick_is_skipped_not_raised(monkeypatch):
    monkeypatch.setattr(RS, "rules_pick", lambda: 1 / 0)
    assert len(SR.rules_section()["picks"]) == 7


# ═════════════════════════════════════════════ display only
REG_SHO_READERS_2026_11_23 = ("chart_maps/gajjala/high_si.py", "chart_maps/gajjala/high_si_cross.py")
# WIDENED 2026-11-24 (⛔🔒🩳 SPEC sissr §3.3, WP be-pass — Ajay "Days past little bit like AKAN is what I am mainly
# looking for many were so confident on SSR.."): si_ssr_names.py reads the SAME stored payload(kick=False) to TAG names
# past their close-out date, plus the pure RSH.past_closeout_text word. It aliases the module RSH, so it has its own
# read-only pin below (test_NEGATIVE_si_ssr_names_reads_the_stored_payload_only); nothing else may join.
REG_SHO_READERS_2026_11_24 = ("chart_maps/gajjala/si_ssr_names.py",)
# WIDENED 2026-11-26 (spec sitrack WP5, main-session suite gate): si_track.py (the 🏁 SI track record) records the 🔒
# fields through the SAME stored payload(kick=False) — display only; aliases the module RSH; read-only pin in
# test_gajjala_si_track_guards_2026_11_26. Nothing else may join.
REG_SHO_READERS_2026_11_26 = ("chart_maps/gajjala/si_track.py",)


def test_NEGATIVE_display_only_nothing_in_the_trading_paths_reads_it():
    # 🩳 2026-11-23 (spec highsi §3.2 / §3.5, OWNER'S CALL — it reverses this file's display-only pin): the 🩳 High
    # short interest sub's counts line (high_si.sho_text) and the 🩳 cross push body (high_si_cross._sho_items) carry
    # the 🔒 tag. Widened from []; exactly these two modules, read-only (payload(kick=False)), nothing else may join.
    hits = []
    for sub in ("chart_maps", "push", "trading"):
        for f in (BACKEND / sub).rglob("*.py"):
            if "__pycache__" not in f.parts and "reg_sho" in f.read_text(errors="ignore"):
                hits.append(f.relative_to(BACKEND).as_posix())
    assert sorted(hits) == sorted(REG_SHO_READERS_2026_11_23 + REG_SHO_READERS_2026_11_24 + REG_SHO_READERS_2026_11_26)
    assert "reg_sho" not in (BACKEND / "crontab").read_text()
    ua = RS.HTTP_HEADERS["User-Agent"]
    assert "cheetah" not in ua.lower() and "@" not in ua


def test_NEGATIVE_si_ssr_names_reads_the_stored_payload_only():
    import ast
    for rel in REG_SHO_READERS_2026_11_24:
        src = (BACKEND / rel).read_text(encoding="utf-8")
        tree = ast.parse(src)
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        assert not [n for n in top if "reg_sho" in ast.dump(n)], rel                 # lazy only
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and isinstance(n.func.value, ast.Name) and n.func.value.id in ("RS", "RSH", "reg_sho")]
        assert {c.func.attr for c in calls} == {"payload", "past_closeout_text"}, rel  # the matcher can fail
        for c in calls:
            if c.func.attr == "payload":
                kw = {k.arg: k.value for k in c.keywords}
                assert isinstance(kw.get("kick"), ast.Constant) and kw["kick"].value is False, rel
        for banned in ("refresh(", "kick=True", "_fetch", "spawn", "_popen", "reg_sho" + "_runs"):
            assert banned not in src, (rel, banned)


def test_NEGATIVE_a_kicking_payload_read_in_si_ssr_names_would_trip():
    import ast
    src = (BACKEND / REG_SHO_READERS_2026_11_24[0]).read_text(encoding="utf-8")
    planted = src + "\ndef _x(now):\n    from short_interest import reg_sho as RSH\n    return RSH.payload(kick=True)\n"
    tree = ast.parse(planted)
    kicks = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "RSH" and n.func.attr == "payload"
             and any(k.arg == "kick" and isinstance(k.value, ast.Constant) and k.value.value is True
                     for k in n.keywords)]
    assert kicks and "kick=True" in planted


def test_NEGATIVE_the_two_2026_11_23_readers_only_read_the_stored_payload_never_kick_or_refresh():
    import ast
    for rel in REG_SHO_READERS_2026_11_23:
        src = (BACKEND / rel).read_text(encoding="utf-8")
        tree = ast.parse(src)
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        assert not [n for n in top if "reg_sho" in ast.dump(n)], rel                 # lazy only (tab import cycle)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and isinstance(n.func.value, ast.Name) and n.func.value.id in ("RS", "reg_sho")]
        assert calls, rel                                                           # the matcher can fail
        for c in calls:
            assert c.func.attr == "payload", (rel, c.func.attr)
            kw = {k.arg: k.value for k in c.keywords}
            assert isinstance(kw.get("kick"), ast.Constant) and kw["kick"].value is False, rel
        for banned in ("refresh(", "kick=True", "_fetch", "spawn", "_popen"):
            assert banned not in src, (rel, banned)
    probe = "from short_interest import reg_sho\nreg_sho.payload(kick=True)\n"
    c = next(n for n in ast.walk(ast.parse(probe)) if isinstance(n, ast.Call))
    assert c.keywords[0].value.value is True                                        # the kick check can go red


def test_si_map_route_answers_the_same_three_keys(monkeypatch):
    monkeypatch.setattr(SIC, "_get_db", lambda: None)
    out = _run(SAPI.short_interest_read_map(symbols=""))
    assert set(out) == {"items", "n", "max_symbols"}


def test_the_route_runs_off_the_event_loop():
    import inspect
    src = inspect.getsource(SAPI.reg_sho_threshold)
    assert "asyncio.to_thread" in src and "fault_payload" in src
