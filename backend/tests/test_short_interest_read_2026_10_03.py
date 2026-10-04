"""🩳 Short interest on every Chart Maps tab and the ticker page (2026-10-03).

Ajay, verbatim: "I would like to see a new field for sotcks about short interest
I heard EOSE has about 40% short interest is Short Interest always accurate
about a stocks down fall? can you add this field to all our chart maps scan.
also the individual tickers please"

Hermetic: no network (requests.get is replaced), Mongo is a fake. Pins:
  * the FINRA calendar (settlements, publication on the 7th business day, the
    six published 2026 pairs) and the stale label built on it;
  * the served block (shared fixture with the FE), its types, and every NEG:
    0 / NaN denominators, missing days-to-cover, legacy v1 docs, misses;
  * the ONE-read map and endpoint;
  * the bulk warm's 0 / 1 / 3 call economy, its atomic failure modes, and
    that the Massive key never reaches a log line or the result;
  * display only: no gate, sort, push or lane imports the read.
"""
from __future__ import annotations

import asyncio
import copy
import inspect
import json
import logging
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from short_interest import api as SAPI
from short_interest import client
from short_interest import read as SR

BACKEND = Path(__file__).resolve().parents[1]
FIXTURE = BACKEND / "tests" / "fixtures" / "short_interest_blocks_2026_10_03.json"
FORBIDDEN = re.compile(r"predict|will (fall|drop)|bounce|fake|squeeze", re.I)


# ───────────────────────────────────────────── fakes
class FakeColl:
    def __init__(self, docs=None, name="?"):
        self.name = name
        self.docs = {d["_id"]: copy.deepcopy(d) for d in (docs or [])}
        self.finds = []
        self.writes = []

    def find(self, q=None, proj=None):
        self.finds.append((copy.deepcopy(q), proj))
        q = q or {}
        idq = q.get("_id")
        out = []
        for d in self.docs.values():
            if isinstance(idq, dict) and d["_id"] not in idq.get("$in", []):
                continue
            out.append(copy.deepcopy(d))
        return iter(out)

    def bulk_write(self, reqs, ordered=True):
        self.writes.append(("bulk_write", len(reqs)))
        for op in reqs:
            f, doc = op._filter, op._doc
            if "$set" in doc:
                if f["_id"] in self.docs:
                    self.docs[f["_id"]].update(doc["$set"])
            else:
                self.docs[f["_id"]] = copy.deepcopy(doc)

    def replace_one(self, q, doc, upsert=False):
        self.writes.append(("replace_one", q))
        self.docs[q["_id"]] = copy.deepcopy(doc)

    def update_one(self, q, upd, upsert=False):
        self.writes.append(("update_one", q))
        if q["_id"] in self.docs:
            self.docs[q["_id"]].update(upd.get("$set", {}))


class FakeDB:
    def __init__(self, colls=None):
        self.colls = dict(colls or {})
        self.touched = []

    def __getitem__(self, name):
        self.touched.append(name)
        if name not in self.colls:
            self.colls[name] = FakeColl(name=name)
        return self.colls[name]

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return self[name]


class Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        return self._body


def _run(coro):
    """Run on a fresh loop and leave a loop installed. On Python 3.9 the stdlib
    run() leaves none, and a later first import of sepa.insider (an asyncio.Lock
    at import) then raises 'There is no current event loop'."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


@pytest.fixture
def no_network(monkeypatch):
    import requests

    def boom(*a, **k):
        raise AssertionError("a read path made a network call")

    monkeypatch.setattr(requests, "get", boom)
    return boom


@pytest.fixture
def sleeps(monkeypatch):
    rec = []
    monkeypatch.setattr(client.time, "sleep", lambda s: rec.append(s))
    return rec


class Provider:
    """Fake Massive: per-ticker probe answers `ref_dates`; a settlement_date
    query answers `bulk[date]` or a failure mode ("500" | "raise" | "empty")."""

    def __init__(self, ref_dates, bulk, fail=None, ref_fail=None):
        self.ref_dates = list(ref_dates)
        self.bulk = bulk
        self.fail = dict(fail or {})
        self.ref_fail = ref_fail
        self.calls = []

    def __call__(self, url, params=None, timeout=None, **k):
        params = dict(params or {})
        self.calls.append({k2: v for k2, v in params.items() if k2 != "apiKey"})
        if "ticker" in params:
            if self.ref_fail == "raise":
                raise RuntimeError("discovery down")
            if self.ref_fail == "500":
                return Resp(500, {})
            rows = [{"ticker": params["ticker"], "settlement_date": d,
                     "short_interest": 1, "avg_daily_volume": 1, "days_to_cover": 1.0}
                    for d in self.ref_dates[: int(params.get("limit") or 2)]]
            return Resp(200, {"results": rows})
        d = params.get("settlement_date")
        mode = self.fail.get(d)
        if mode == "raise":
            raise RuntimeError("bulk down")
        if mode == "500":
            return Resp(500, {"error": "boom"})
        if mode == "empty":
            return Resp(200, {"results": []})
        return Resp(200, {"results": list(self.bulk.get(d) or [])})


def _rows(date_iso, tickers, si_base=1000):
    return [{"ticker": t, "settlement_date": date_iso, "short_interest": si_base + i,
             "avg_daily_volume": 500 + i, "days_to_cover": 2.0} for i, t in enumerate(tickers)]


TICKERS = ["T%02d" % i for i in range(20)]


def _install(monkeypatch, prov):
    import requests
    monkeypatch.setattr(requests, "get", prov)
    monkeypatch.setattr(client, "stocks_key", lambda: "TESTKEY")


def _v2(sym, sd, checked=None, si=777):
    return {"_id": sym, "symbol": sym, "v": 2, "settlement_date": sd, "short_interest": si,
            "days_to_cover": 3.3, "checked_settlement": checked or sd, "fetched_at": 1.0}


def _db_with(si_docs, shares=None):
    return FakeDB({client.SI_COLL: FakeColl(si_docs, name=client.SI_COLL),
                   "shares_cache": FakeColl(shares or [], name="shares_cache")})


# ═════════════════════════════════════════════ calendar
def test_settlement_dates_follow_FINRAs_rule():
    assert SR.settlements_in_month(2026, 8) == [date(2026, 8, 14), date(2026, 8, 31)]
    assert SR.settlements_in_month(2026, 10) == [date(2026, 10, 15), date(2026, 10, 30)]
    assert SR.settlements_in_month(2026, 11)[0] == date(2026, 11, 13)   # the 15th is a Sunday


@pytest.mark.parametrize("settle,pub", [
    ("2026-08-14", "2026-08-25"), ("2026-08-31", "2026-09-10"), ("2026-09-15", "2026-09-24"),
    ("2026-09-30", "2026-10-09"), ("2026-10-15", "2026-10-26"), ("2026-10-30", "2026-11-10"),
])
def test_publication_date_reproduces_the_six_published_2026_pairs(settle, pub):
    assert SR.publication_date(date.fromisoformat(settle)) == date.fromisoformat(pub)


def test_labor_day_is_skipped():
    assert SR.is_business_day(date(2026, 9, 7)) is False
    assert SR.publication_date(date(2026, 8, 31)) == date(2026, 9, 10)


def test_next_settlement_crosses_the_year():
    assert SR.next_settlement_after(date(2026, 12, 31)) == date(2027, 1, 15)
    assert SR.next_settlement_after(date(2026, 9, 15)) == date(2026, 9, 30)


def test_freshness_reads_stale_once_the_next_settlement_is_overdue():
    f = SR.freshness("2026-08-31", today=date(2026, 10, 3))
    assert f["stale"] is True
    assert "2026-09-15" in f["stale_reason"] and "2026-09-28" in f["stale_reason"]
    assert SR.freshness("2026-09-15", date(2026, 10, 13))["stale"] is False
    assert SR.freshness("2026-09-15", date(2026, 10, 14))["stale"] is True
    assert SR.freshness("2026-09-15", date(2026, 10, 13))["next_due_on"] == "2026-10-13"


@pytest.mark.parametrize("bad", [None, "junk", "", 42])
def test_NEGATIVE_an_unreadable_date_is_unknown_never_stale(bad):
    f = SR.freshness(bad, today=date(2026, 10, 3))
    assert f["stale"] is None
    assert all(f[k] is None for k in ("stale_reason", "published_on",
                                      "next_settlement_date", "next_due_on"))


def test_newer_settlement_can_exist_follows_the_publication_day():
    assert SR.newer_settlement_can_exist("2026-09-15", date(2026, 10, 3)) is False
    assert SR.newer_settlement_can_exist("2026-09-15", date(2026, 10, 9)) is True
    assert SR.newer_settlement_can_exist(None, date(2026, 10, 3)) is True


# ═════════════════════════════════════════════ the block
FIX = json.loads(FIXTURE.read_text(encoding="utf-8"))
FIX_TODAY = date.fromisoformat(FIX["today"])
CASES = {c["name"]: c for c in FIX["cases"]}


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_fixture_case_is_exactly_what_si_block_serves(name):
    c = CASES[name]
    assert SR.si_block(c["doc"], FIX_TODAY) == c["block"]


def test_the_fixture_chips_match_the_spec_by_hand():
    chip = {n: c["block"]["chip"] for n, c in CASES.items()}
    assert chip["eose_v2_float"] == "🩳 SI 33.6% float · 4.1d · 9/15"
    assert chip["bynd_v2_float"] == "🩳 SI 1.0% float · 4.7d · 9/15"
    assert chip["fcg_v2_no_denoms"] == "🩳 SI 440.3K sh · 1.0d · 9/15"
    assert chip["eose_v1_legacy_stale"].endswith("· 8/31 · stale")
    assert chip["no_record_miss"] is None
    assert chip["dtc_missing"] == "🩳 SI 33.6% float · 9/15"
    assert set(CASES) == {"eose_v2_float", "bynd_v2_float", "fcg_v2_no_denoms",
                          "uhal_v2_conflict", "eose_v1_legacy_stale", "no_record_miss",
                          "dtc_missing"}
    b = CASES["bynd_v2_float"]["block"]
    assert b["pct_of_float"] == 1.02 and b["pct_of_shares_out"] == 0.99   # not 29.6
    e = CASES["eose_v2_float"]["block"]
    assert e["status"] == "ok" and e["si_change_pct"] == 7.8 and e["days_to_cover"] == 4.13
    assert e["published_on"] == "2026-09-24" and e["next_due_on"] == "2026-10-13"
    f = CASES["fcg_v2_no_denoms"]["block"]
    assert f["headline_basis"] is None and "float" not in f["chip"]
    u = CASES["uhal_v2_conflict"]["block"]
    assert "⚠" in u["title"] and any(r["k"] == "⚠ Counts disagree" for r in u["rows"])
    legacy = CASES["eose_v1_legacy_stale"]["block"]
    assert legacy["status"] == "stale" and legacy["headline_basis"] == "shares_out"
    assert legacy["shares_source"] == SR.LEGACY_SHARES_SOURCE


_NUM = ("si_shares", "prev_si_shares", "si_change_pct", "avg_daily_volume", "days_to_cover",
        "float_shares", "pct_of_float", "shares_outstanding", "pct_of_shares_out")
_DATES = ("settlement_date", "published_on", "prev_settlement_date", "float_asof",
          "shares_asof", "next_settlement_date", "next_due_on")


@pytest.mark.parametrize("name", sorted(CASES))
def test_block_keys_and_types_match_the_payload_contract(name):
    b = SR.si_block(CASES[name]["doc"], FIX_TODAY)
    assert set(b) == set(SR._BLOCK_KEYS)
    assert b["status"] in ("ok", "stale", "no_record")
    assert b["headline_basis"] in ("float", "shares_out", None)
    for k in _NUM:
        assert b[k] is None or (isinstance(b[k], (int, float)) and not isinstance(b[k], bool)
                                and math.isfinite(b[k])), k
    for k in _DATES:
        assert b[k] is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}", b[k]), k
    assert b["fetched_at"] is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                                                   b["fetched_at"])
    assert (b["chip"] is None) == (b["status"] == "no_record")
    assert isinstance(b["title"], str) and b["title"]
    assert all(set(r) == {"k", "v"} and isinstance(r["k"], str) and isinstance(r["v"], str)
               for r in b["rows"])
    assert "squeeze" not in b
    json.dumps(b, allow_nan=False)


def _eose(**over):
    d = copy.deepcopy(CASES["eose_v2_float"]["doc"])
    d.update(over)
    return d


@pytest.mark.parametrize("bad", [0, -5, float("nan"), float("inf"), "x", None])
def test_NEGATIVE_a_bad_float_is_missing_never_zero_percent(bad):
    b = SR.si_block(_eose(float_shares=bad), FIX_TODAY)
    assert b["pct_of_float"] is None and b["float_shares"] is None
    assert b["headline_basis"] == "shares_out"
    assert "float" not in b["chip"] and "0.0%" not in b["chip"]
    head = b["title"].split(" shares short")[0]
    assert "float" not in head
    json.dumps(b, allow_nan=False)


@pytest.mark.parametrize("bad", [0, -1, float("nan")])
def test_NEGATIVE_bad_float_AND_shares_fall_back_to_the_share_count(bad):
    b = SR.si_block(_eose(float_shares=bad, shares_outstanding=bad), FIX_TODAY)
    assert b["headline_basis"] is None and b["chip"].startswith("🩳 SI 120.0M sh")
    assert "%" not in b["chip"]


def test_NEGATIVE_a_zero_days_to_cover_never_prints_0_0d():
    b = SR.si_block(_eose(days_to_cover=0.0), FIX_TODAY)
    assert b["days_to_cover"] == 0.0
    assert "0.0d" not in b["chip"] and b["chip"] == "🩳 SI 33.6% float · 9/15"
    tiny = SR.si_block(_eose(days_to_cover=0.03), FIX_TODAY)
    assert tiny["chip"] == "🩳 SI 33.6% float · <0.1d · 9/15"


def test_NEGATIVE_nan_days_to_cover_is_none_and_drops_the_segment():
    b = SR.si_block(_eose(days_to_cover=float("nan")), FIX_TODAY)
    assert b["days_to_cover"] is None
    assert not re.search(r"\dd\b", b["chip"]) and "0.0d" not in b["chip"]
    assert "Days to cover: not read." in b["title"]
    json.dumps(b, allow_nan=False)


def test_NEGATIVE_no_served_string_reads_as_a_forecast():
    texts = []
    for c in CASES.values():
        b = SR.si_block(c["doc"], FIX_TODAY)
        texts += [b["chip"] or "", b["title"]] + [r["k"] + " " + r["v"] for r in b["rows"]]
    sec = SR.rules_section()
    texts += sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"], sec["title"]]
    for t in texts:
        assert not FORBIDDEN.search(t), t


def test_NEGATIVE_a_legacy_v1_doc_is_never_labelled_float():
    doc = copy.deepcopy(CASES["eose_v1_legacy_stale"]["doc"])
    doc["float_shares"] = 100_000_000          # a stray key must not become a float read
    b = SR.si_block(doc, FIX_TODAY)
    assert b["pct_of_float"] is None and b["headline_basis"] == "shares_out"
    assert b["shares_source"] == SR.LEGACY_SHARES_SOURCE
    assert "float" not in b["chip"]
    assert not re.search(r"30\.6%[^.]*float", b["title"])


@pytest.mark.parametrize("over", [{"short_interest": None}, {"short_interest": float("nan")},
                                  {"short_interest": -3}, {"settlement_date": None},
                                  {"settlement_date": "garbage"}])
def test_NEGATIVE_no_count_or_no_date_is_no_record(over):
    b = SR.si_block(_eose(**over), FIX_TODAY)
    assert b["status"] == "no_record" and b["chip"] is None
    assert all(b[k] is None for k in _NUM)
    assert "not read" in b["title"] and len(b["rows"]) == 1
    json.dumps(b, allow_nan=False)


def test_a_reported_zero_short_interest_is_real_and_kept():
    b = SR.si_block(_eose(short_interest=0), FIX_TODAY)
    assert b["status"] == "ok" and b["si_shares"] == 0 and b["pct_of_float"] == 0.0


def test_NEGATIVE_si_block_of_nothing_is_nothing():
    assert SR.si_block(None) is None
    assert SR.si_block("EOSE") is None


# ═════════════════════════════════════════════ the map
def test_si_map_is_ONE_find_on_the_short_INTEREST_cache(no_network):
    db = FakeDB({client.SI_COLL: FakeColl([CASES["eose_v2_float"]["doc"]], name=client.SI_COLL),
                 "short_volume_latest": FakeColl([{"_id": "EOSE", "short_volume_pct": 60.0}])})
    m = SR.si_map(["eose", "EOSE", "nope"], db=db, today=FIX_TODAY)
    assert list(m) == ["EOSE"]
    assert m["EOSE"] == CASES["eose_v2_float"]["block"]
    assert len(db.colls[client.SI_COLL].finds) == 1
    assert not any(t.startswith("short_volume") for t in db.touched)


def test_NEGATIVE_si_map_caps_at_MAP_MAX_SYMBOLS(no_network):
    db = _db_with([])
    SR.si_map(["S%03d" % i for i in range(250)], db=db)
    (q, _p), = db.colls[client.SI_COLL].finds
    assert len(q["_id"]["$in"]) == SR.MAP_MAX_SYMBOLS == 200


def test_NEGATIVE_empty_input_never_touches_the_db(no_network):
    db = FakeDB()
    assert SR.si_map(["", " ", None], db=db) == {}
    assert SR.si_map([], db=db) == {} and SR.si_map(None, db=db) == {}
    assert db.touched == []


def test_NEGATIVE_an_absent_symbol_is_absent_not_zero(no_network):
    db = _db_with([CASES["eose_v2_float"]["doc"]])
    m = SR.si_map(["EOSE", "FOO"], db=db, today=FIX_TODAY)
    assert "FOO" not in m


def test_NEGATIVE_the_read_never_calls_Massive_reference(no_network, monkeypatch):
    """The BYND trap: Massive's share count read BYND at 29.6% short."""
    def boom(*a, **k):
        raise AssertionError("the read called Massive reference shares")

    monkeypatch.setattr(client, "_shares_outstanding", boom)
    monkeypatch.setattr(client, "short_interest_for", boom)
    db = _db_with([CASES["bynd_v2_float"]["doc"]])
    assert SR.si_map(["BYND"], db=db, today=FIX_TODAY)["BYND"]["pct_of_shares_out"] == 0.99


# ═════════════════════════════════════════════ the endpoint
def test_endpoint_uppercases_and_reports_the_cap(no_network, monkeypatch):
    db = _db_with([CASES["eose_v2_float"]["doc"], CASES["bynd_v2_float"]["doc"]])
    monkeypatch.setattr(client, "_get_db", lambda: db)
    out = _run(SAPI.short_interest_read_map(symbols="eose,BYND"))
    assert set(out["items"]) == {"EOSE", "BYND"} and out["n"] == 2
    assert out["max_symbols"] == 200
    json.dumps(out, allow_nan=False)


def test_NEGATIVE_endpoint_with_no_symbols_is_empty(no_network, monkeypatch):
    db = FakeDB()
    monkeypatch.setattr(client, "_get_db", lambda: db)
    out = _run(SAPI.short_interest_read_map(symbols=""))
    assert out["items"] == {} and out["n"] == 0 and out["max_symbols"] == 200
    assert db.touched == []


def test_endpoint_runs_off_the_event_loop_and_the_old_route_is_unchanged():
    assert "asyncio.to_thread" in inspect.getsource(SAPI.short_interest_read_map)
    assert "short_interest_for" in inspect.getsource(SAPI.get_short_interest)
    paths = {r.path for r in SAPI.router.routes}
    assert "/short-interest/map" in paths and "/short/{symbol}/interest" in paths
    assert not any(p.startswith("/short-interest/{") for p in paths)


# ═════════════════════════════════════════════ the bulk warm
def test_ZERO_calls_when_no_newer_settlement_can_be_out(monkeypatch, sleeps):
    prov = Provider(["2026-09-15", "2026-08-31"], {})
    _install(monkeypatch, prov)
    db = _db_with([_v2("AAA", "2026-09-15"), _v2("BBB", "2026-09-15")])
    res = client.warm_short_interest_bulk(scope=["AAA", "BBB"], db=db, today=date(2026, 10, 3))
    assert prov.calls == [] and res["provider_calls"] == 0
    assert res["skipped_reason"].startswith("no newer FINRA settlement can be out before 2026-10-09")
    assert res["error"] is None and db.colls[client.SI_COLL].writes == []


def test_ONE_call_when_the_provider_has_not_loaded_the_next_settlement(monkeypatch, sleeps):
    prov = Provider(["2026-09-15", "2026-08-31"], {})
    _install(monkeypatch, prov)
    db = _db_with([_v2("AAA", "2026-09-15")])
    res = client.warm_short_interest_bulk(scope=["AAA"], db=db, today=date(2026, 10, 9))
    assert len(prov.calls) == 1 and res["provider_calls"] == 1
    assert res["skipped_reason"] == "provider still at 2026-09-15"
    assert db.colls[client.SI_COLL].writes == []


def test_THREE_calls_on_a_new_settlement_write_v2_docs(monkeypatch, sleeps):
    prov = Provider(["2026-09-15", "2026-08-31"],
                    {"2026-09-15": _rows("2026-09-15", TICKERS, 2000),
                     "2026-08-31": _rows("2026-08-31", TICKERS, 1000)})
    _install(monkeypatch, prov)
    shares = [{"_id": "T00", "float_shares": 20000, "shares_outstanding": 40000,
               "as_of": 1788523200},
              {"_id": "T01", "float_shares": 0, "shares_outstanding": float("nan"),
               "as_of": 1788523200}]
    db = _db_with([_v2(t, "2026-08-31") for t in TICKERS], shares)
    res = client.warm_short_interest_bulk(scope=TICKERS, db=db, today=date(2026, 9, 28))
    assert len(prov.calls) == 3 and res["provider_calls"] == 3
    assert res["error"] is None and res["latest"] == "2026-09-15" and res["prior"] == "2026-08-31"
    assert res["written"] == 20 and res["rows_latest"] == 20 and res["rows_prior"] == 20
    assert len(sleeps) >= 2
    assert len(db.colls["shares_cache"].finds) == 1
    d0 = db.colls[client.SI_COLL].docs["T00"]
    assert d0["v"] == 2 and d0["settlement_date"] == "2026-09-15"
    assert d0["checked_settlement"] == "2026-09-15"
    assert d0["prev_settlement_date"] == "2026-08-31" and d0["prev_short_interest"] == 1000
    assert d0["si_change_pct"] == 100.0
    assert d0["pct_of_float"] == 10.0 and d0["pct_of_shares"] == 5.0
    assert d0["float_asof"] == "2026-09-04" and d0["float_source"] == SR.FLOAT_SOURCE
    d1 = db.colls[client.SI_COLL].docs["T01"]
    assert d1["float_shares"] is None and d1["pct_of_float"] is None
    assert d1["shares_outstanding"] is None and d1["pct_of_shares"] is None
    # the served read of a freshly written doc
    b = SR.si_block(d0, date(2026, 9, 28))
    assert b["chip"] == "🩳 SI 10.0% float · 2.0d · 9/15" and b["status"] == "ok"


@pytest.mark.parametrize("label,fail,ref_fail,bulk_latest", [
    ("latest_500", {"2026-09-15": "500"}, None, TICKERS),
    ("latest_raises", {"2026-09-15": "raise"}, None, TICKERS),
    ("latest_empty", {"2026-09-15": "empty"}, None, TICKERS),
    ("prior_fails", {"2026-08-31": "500"}, None, TICKERS),
    ("discovery_fails", {}, "500", TICKERS),
    ("discovery_raises", {}, "raise", TICKERS),
    ("partial_settlement", {}, None, TICKERS[:5]),
])
def test_NEGATIVE_any_failure_writes_nothing(monkeypatch, sleeps, label, fail, ref_fail,
                                             bulk_latest):
    prov = Provider(["2026-09-15", "2026-08-31"],
                    {"2026-09-15": _rows("2026-09-15", bulk_latest, 2000),
                     "2026-08-31": _rows("2026-08-31", TICKERS, 1000)},
                    fail=fail, ref_fail=ref_fail)
    _install(monkeypatch, prov)
    before = [_v2(t, "2026-08-31") for t in TICKERS]
    db = _db_with(before)
    res = client.warm_short_interest_bulk(scope=TICKERS + ["NEWNAME"], db=db,
                                          today=date(2026, 9, 28))
    assert res["error"], label
    assert res["written"] == 0 and res["misses"] == 0 and res["kept"] == 0
    coll = db.colls[client.SI_COLL]
    assert coll.writes == []
    assert json.dumps(coll.docs, sort_keys=True) == json.dumps(
        {d["_id"]: d for d in before}, sort_keys=True)
    if label == "partial_settlement":
        assert res["error"] == "partial settlement 2026-09-15: 5 of 20 rows"


def test_NEGATIVE_a_name_missing_from_the_new_settlement_keeps_its_good_doc(monkeypatch, sleeps):
    prov = Provider(["2026-09-15", "2026-08-31"],
                    {"2026-09-15": _rows("2026-09-15", TICKERS, 2000),
                     "2026-08-31": _rows("2026-08-31", TICKERS, 1000)})
    _install(monkeypatch, prov)
    gone = _v2("GONE", "2026-08-31", si=4242)
    db = _db_with([gone])
    # after due_date(2026-09-15) = 2026-09-28; inside the window the name is deferred
    res = client.warm_short_interest_bulk(scope=["GONE"], db=db, today=date(2026, 10, 3))
    assert res["error"] is None and res["kept"] == 1
    after = db.colls[client.SI_COLL].docs["GONE"]
    assert after["checked_settlement"] == "2026-09-15"
    assert {k: v for k, v in after.items() if k != "checked_settlement"} == \
        {k: v for k, v in gone.items() if k != "checked_settlement"}


def test_NEGATIVE_a_doc_with_a_NEWER_settlement_is_never_moved_back(monkeypatch, sleeps):
    prov = Provider(["2026-09-15", "2026-08-31"],
                    {"2026-09-15": _rows("2026-09-15", TICKERS, 2000),
                     "2026-08-31": _rows("2026-08-31", TICKERS, 1000)})
    _install(monkeypatch, prov)
    newer = _v2("T03", "2026-09-30", checked="2026-08-31", si=999)
    db = _db_with([newer, _v2("T04", "2026-08-31")])
    res = client.warm_short_interest_bulk(scope=["T03", "T04"], db=db,
                                          today=date(2026, 9, 28), force=True)
    assert res["error"] is None
    assert db.colls[client.SI_COLL].docs["T03"] == newer
    assert db.colls[client.SI_COLL].docs["T04"]["settlement_date"] == "2026-09-15"


def test_NEGATIVE_dry_run_returns_docs_and_writes_nothing(monkeypatch, sleeps):
    prov = Provider(["2026-09-15", "2026-08-31"],
                    {"2026-09-15": _rows("2026-09-15", TICKERS, 2000),
                     "2026-08-31": _rows("2026-08-31", TICKERS, 1000)})
    _install(monkeypatch, prov)
    db = _db_with([])
    res = client.warm_short_interest_bulk(scope=TICKERS + ["NOROW"], db=db, dry_run=True,
                                          force=True, today=date(2026, 10, 3))
    assert res["error"] is None and len(res["docs"]) == 21
    assert res["written"] == 20 and res["misses"] == 1
    assert db.colls[client.SI_COLL].writes == [] and db.colls[client.SI_COLL].docs == {}


def test_NEGATIVE_a_universe_name_with_no_FINRA_row_and_no_doc_is_a_remembered_miss(
        monkeypatch, sleeps):
    prov = Provider(["2026-09-15", "2026-08-31"],
                    {"2026-09-15": _rows("2026-09-15", TICKERS, 2000),
                     "2026-08-31": _rows("2026-08-31", TICKERS, 1000)})
    _install(monkeypatch, prov)
    db = _db_with([])
    res = client.warm_short_interest_bulk(scope=["NOROW"], db=db, today=date(2026, 10, 3))
    assert res["misses"] == 1
    miss = db.colls[client.SI_COLL].docs["NOROW"]
    assert miss["settlement_date"] is None and miss["v"] == 2
    assert miss["checked_settlement"] == "2026-09-15"
    assert SR.si_block(miss)["status"] == "no_record"


def _partial_then_complete(monkeypatch, first_rows):
    """Held at 09-15; FINRA publishes 09-30 on 10-09 (due 10-13)."""
    held = [_v2(t, "2026-09-15") for t in TICKERS]
    db = _db_with(held)
    prov = Provider(["2026-09-30", "2026-09-15"],
                    {"2026-09-30": _rows("2026-09-30", first_rows, 3000),
                     "2026-09-15": _rows("2026-09-15", TICKERS, 2000)})
    _install(monkeypatch, prov)
    return db, prov


def test_NEGATIVE_a_95pct_load_inside_the_window_leaves_the_gap_pending_and_refills_it(
        monkeypatch, sleeps):
    assert SR.due_date(date(2026, 9, 30)) == date(2026, 10, 13)
    db, prov = _partial_then_complete(monkeypatch, TICKERS[:19])     # 19 of 20 = 95%
    r1 = client.warm_short_interest_bulk(scope=TICKERS, db=db, today=date(2026, 10, 9))
    assert r1["error"] is None and r1["written"] == 19 and r1["provider_calls"] == 3
    assert r1["kept"] == 0 and r1["misses"] == 0 and r1["deferred"] == 1
    gap = db.colls[client.SI_COLL].docs["T19"]
    assert gap["settlement_date"] == "2026-09-15" and gap["checked_settlement"] == "2026-09-15"
    # Massive finishes loading: the next run fetches again and fills the gap
    prov.bulk["2026-09-30"] = _rows("2026-09-30", TICKERS, 3000)
    r2 = client.warm_short_interest_bulk(scope=TICKERS, db=db, today=date(2026, 10, 12))
    assert r2["skipped_reason"] is None and r2["error"] is None
    assert r2["provider_calls"] == 3 and r2["written"] == 1 and r2["deferred"] == 0
    gap = db.colls[client.SI_COLL].docs["T19"]
    assert gap["settlement_date"] == "2026-09-30" and gap["checked_settlement"] == "2026-09-30"
    # all answered: the next run is 0 calls
    n = len(prov.calls)
    r3 = client.warm_short_interest_bulk(scope=TICKERS, db=db, today=date(2026, 10, 13))
    assert r3["provider_calls"] == 0 and len(prov.calls) == n and r3["skipped_reason"]


def test_NEGATIVE_inside_the_window_a_missing_name_gets_no_miss_doc_and_no_check(
        monkeypatch, sleeps):
    db, prov = _partial_then_complete(monkeypatch, TICKERS)
    r = client.warm_short_interest_bulk(scope=TICKERS + ["NOROW"], db=db,
                                        today=date(2026, 10, 13))      # = due_date: still inside
    assert r["error"] is None and r["written"] == 20 and r["misses"] == 0
    assert r["deferred"] == 1 and "NOROW" not in db.colls[client.SI_COLL].docs
    assert SR.si_map(["NOROW"], db=db, today=date(2026, 10, 13)) == {}


def test_NEGATIVE_after_the_window_a_name_FINRA_never_lists_is_recorded_once_then_quiet(
        monkeypatch, sleeps):
    db, prov = _partial_then_complete(monkeypatch, TICKERS)
    client.warm_short_interest_bulk(scope=TICKERS + ["NOROW"], db=db, today=date(2026, 10, 9))
    assert "NOROW" not in db.colls[client.SI_COLL].docs
    r = client.warm_short_interest_bulk(scope=TICKERS + ["NOROW"], db=db,
                                        today=date(2026, 10, 14))
    assert r["error"] is None and r["misses"] == 1 and r["deferred"] == 0
    assert db.colls[client.SI_COLL].docs["NOROW"]["checked_settlement"] == "2026-09-30"
    n = len(prov.calls)
    r2 = client.warm_short_interest_bulk(scope=TICKERS + ["NOROW"], db=db,
                                         today=date(2026, 10, 15))
    assert r2["provider_calls"] == 0 and len(prov.calls) == n


def test_NEGATIVE_a_dry_run_inside_the_window_counts_the_deferred_names(monkeypatch, sleeps):
    db, prov = _partial_then_complete(monkeypatch, TICKERS[:19])
    r = client.warm_short_interest_bulk(scope=TICKERS + ["NOROW"], db=db, dry_run=True,
                                        today=date(2026, 10, 9))
    assert r["deferred"] == 2 and r["misses"] == 0 and r["kept"] == 0
    assert db.colls[client.SI_COLL].writes == []


def test_NEGATIVE_no_db_returns_an_error_and_never_raises(monkeypatch):
    monkeypatch.setattr(client, "_get_db", lambda: None)
    res = client.warm_short_interest_bulk(scope=["AAA"])
    assert res["error"] == "no_db" and res["provider_calls"] == 0


def test_NEGATIVE_the_Massive_key_never_reaches_a_log_or_the_result(monkeypatch, caplog):
    import requests

    def leaky(url, params=None, **k):
        raise Exception("https://api.massive.com/x?apiKey=SECRETKEY123")

    monkeypatch.setattr(requests, "get", leaky)
    monkeypatch.setattr(client, "stocks_key", lambda: "SECRETKEY123")
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    caplog.set_level(logging.DEBUG)
    db = _db_with([])
    res = client.warm_short_interest_bulk(scope=["AAA"], db=db, today=date(2026, 10, 3))
    assert res["error"]
    assert "SECRETKEY123" not in caplog.text
    assert "SECRETKEY123" not in json.dumps(res, default=str)
    # the bulk fetcher on its own, too
    assert client._fetch_settlement_rows("2026-09-15") is None
    assert "SECRETKEY123" not in caplog.text


# ═════════════════════════════════════════════ CLI
def test_cli_warm_si_dry_run_writes_nothing(monkeypatch, sleeps, capsys):
    from sepa import universe

    prov = Provider(["2026-09-15", "2026-08-31"],
                    {"2026-09-15": _rows("2026-09-15", TICKERS, 2000),
                     "2026-08-31": _rows("2026-08-31", TICKERS, 1000)})
    _install(monkeypatch, prov)
    db = _db_with([])
    monkeypatch.setattr(client, "_get_db", lambda: db)
    monkeypatch.setattr(universe, "load_universe", lambda mode=None: ["T00", "NOROW"])
    assert client._main(["warm-si", "--dry-run"]) == 0
    assert db.colls[client.SI_COLL].writes == []
    out = capsys.readouterr().out
    assert "DRY-RUN" in out and "TESTKEY" not in out and "apiKey" not in out


def test_cli_per_symbol_routes_to_the_old_warm(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(client, "_get_db", lambda: FakeDB())
    monkeypatch.setattr(client, "warm_short_interest",
                        lambda syms, **k: seen.append(syms) or client._WarmResult(
                            n=1, fetched=1, written=1, skipped=0, failed=0))
    monkeypatch.setattr(client, "warm_short_interest_bulk",
                        lambda *a, **k: pytest.fail("bulk path taken"))
    assert client._main(["warm-si", "--per-symbol", "--symbols", "A"]) == 0
    assert seen == [["A"]]


def test_cli_show_si_still_returns_zero(monkeypatch, capsys):
    db = _db_with([_v2("AAA", "2026-09-15"), {"_id": "OLD", "settlement_date": "2026-08-31"}])
    monkeypatch.setattr(client, "_get_db", lambda: db)
    assert client._main(["show-si"]) == 0
    out = capsys.readouterr().out
    assert "1 v2 (bulk), 1 legacy" in out and "2026-09-15" in out


def test_no_top_level_sepa_or_market_hours_import():
    for mod, banned in ((client, r"^(from|import) sepa"),
                        (SR, r"^(from|import) (sepa|market_hours)")):
        for line in open(mod.__file__).read().splitlines():
            assert not re.match(banned, line), (mod.__name__, line)


# ═════════════════════════════════════════════ display only
GUARDED = ("supply_demand/alert_gates.py", "supply_demand/zone_bounce_alerts.py",
           "supply_demand/zone_edge.py", "supply_demand/demand_alerts.py",
           "supply_demand/hot_pullback_alerts.py", "supply_demand/alert_status.py",
           "trading/entries.py", "trading/auto_entry.py", "trading/zone_edge_entry.py",
           "trading/hot_pullback_entry.py", "trading/catalyst_entry.py",
           "sepa/scanner.py", "chart_maps/board.py")


def test_SOURCE_GUARD_no_gate_lane_scan_or_board_reads_the_short_interest_read():
    for rel in GUARDED:
        src = (BACKEND / rel).read_text(encoding="utf-8")
        assert not re.search(r"short_interest\.read\b|from\s+short_interest\s+import\s+[^\n]*\bread\b",
                             src), rel


def test_SOURCE_GUARD_nothing_attaches_or_sorts_by_short_interest():
    from chart_maps import board

    assert board.ATTACH_OWNED_KEYS == ("explosive", "band_structure")
    bad = re.compile(r"short|(^|_)si(_|$)")
    assert not [k for k in board.tile_metrics({}) if bad.search(k)]
    assert not [k for k in board.SORTS if bad.search(k)]


# ═════════════════════════════════════════════ ℹ️ rules section
def test_rules_section_is_last_and_says_what_it_is_not():
    from supply_demand import rules_info as RI

    assert RI.SECTION_KEYS[-1] == "short_interest"
    secs = RI.sections()
    assert list(secs)[-1] == "short_interest"
    sec = secs["short_interest"]
    text = " ".join(sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])
    assert "not a forecast" in text.lower() and "UNMEASURED" in text
    assert sec["emoji"] == "🩳"
    assert "7th business day" in text and "plus 2 business days" in text
    # the old per-name records use Massive's count, not yfinance's — say so
    assert "older per-name records use Massive's shares outstanding" in text
    assert "Massive" in SR.LEGACY_SHARES_SOURCE


def test_rules_section_numbers_move_with_the_constants(monkeypatch):
    from supply_demand import rules_info as RI

    monkeypatch.setattr(SR, "SI_INGEST_GRACE_BDAYS", 3)
    monkeypatch.setattr(SR, "FINRA_PUBLICATION_BDAYS", 8)
    text = " ".join(RI.sections()["short_interest"]["picks"])
    assert "8th business day" in text and "plus 3 business days" in text
    assert "7th business day" not in text and "plus 2 business days" not in text


# ═════════════════════════════════════════════ crontab
def test_crontab_has_exactly_two_ungated_warm_si_lines():
    jobs = [ln for ln in (BACKEND / "crontab").read_text().splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    warm = [ln for ln in jobs if ln.rstrip().endswith("-m short_interest.client warm-si")]
    assert len(warm) == 2
    assert all("market_hours.gate" not in ln for ln in warm)
    assert {ln.split()[1] for ln in warm} == {"7", "18"}
    assert all(ln.split()[0] == "40" and ln.split()[4] == "1-5" for ln in warm)


# ═════════════════════════════════════════════ class shares (critic 2026-10-03)
def test_NEGATIVE_a_class_share_is_keyed_by_the_apps_dash_spelling(monkeypatch, sleeps):
    """Massive answers BRK.B; the universe, tiles and shares_cache say BRK-B.
    The doc must land under BRK-B with the float joined, and no miss."""
    prov = Provider(["2026-09-15", "2026-08-31"],
                    {"2026-09-15": _rows("2026-09-15", TICKERS + ["BRK.B"], 2000),
                     "2026-08-31": _rows("2026-08-31", TICKERS + ["BRK.B"], 1000)})
    _install(monkeypatch, prov)
    shares = [{"_id": "BRK-B", "float_shares": 200000, "shares_outstanding": 400000,
               "as_of": 1788523200}]
    db = _db_with([], shares)
    res = client.warm_short_interest_bulk(scope=["BRK-B", "T00"], db=db,
                                          today=date(2026, 10, 3))
    assert res["error"] is None and res["misses"] == 0
    docs = db.colls[client.SI_COLL].docs
    assert "BRK.B" not in docs
    d = docs["BRK-B"]
    assert d["_id"] == "BRK-B" and d["symbol"] == "BRK-B" and d["v"] == 2
    assert d["settlement_date"] == "2026-09-15"
    assert d["pct_of_float"] is not None and d["float_shares"] == 200000
    assert d["prev_short_interest"] is not None      # the prior row joined too
    assert SR.si_map(["BRK-B"], db=db)["BRK-B"]["status"] != "no_record"


def test_NEGATIVE_canonical_rows_prefers_the_dash_row_and_leaves_other_dots():
    dot, dash, ws = {"short_interest": 1}, {"short_interest": 2}, {"short_interest": 3}
    assert client._canonical_rows({"BRK.B": dot, "BRK-B": dash})["BRK-B"] is dash
    assert client._canonical_rows({"BRK-B": dash, "BRK.B": dot})["BRK-B"] is dash
    out = client._canonical_rows({"BRK.B": dot, "ABC.WS": ws})
    assert set(out) == {"BRK-B", "ABC.WS"}            # only a 1-letter class suffix moves
    assert client._canonical_rows(None) == {} and client._canonical_rows({}) == {}


# ═════════════════════════════════════════════ CLI routing (critic 2026-10-03)
def _cli(monkeypatch):
    calls = []
    monkeypatch.setattr(client, "_get_db", lambda: FakeDB())
    monkeypatch.setattr(client, "warm_short_interest",
                        lambda syms, **k: calls.append(("per", list(syms))) or
                        {"n": 0, "fetched": 0, "written": 0, "skipped": 0, "failed": 0,
                         "kept": 0})

    def bulk(**k):
        calls.append(("bulk", None))
        return {"latest": None, "prior": None, "provider_calls": 0, "rows_latest": 0,
                "rows_prior": 0, "written": 0, "misses": 0, "kept": 0, "deferred": 0,
                "skipped_reason": "x", "error": None}

    monkeypatch.setattr(client, "warm_short_interest_bulk", bulk)
    from sepa import universe
    monkeypatch.setattr(universe, "load_universe", lambda *a, **k: [])
    return calls


def test_NEGATIVE_symbols_without_per_symbol_never_runs_the_whole_market(monkeypatch):
    calls = _cli(monkeypatch)
    assert client._main(["warm-si", "--symbols", "eose,GME"]) == 0
    assert calls == [("per", ["EOSE", "GME"])]


def test_NEGATIVE_all_passers_without_per_symbol_never_runs_the_whole_market(monkeypatch):
    calls = _cli(monkeypatch)
    from sepa import scanner
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": []})
    assert client._main(["warm-si", "--all-passers"]) == 0
    assert calls == [("per", [])]


def test_plain_warm_si_is_still_the_bulk_warm(monkeypatch):
    calls = _cli(monkeypatch)
    assert client._main(["warm-si"]) == 0 and calls == [("bulk", None)]
    calls.clear()
    assert client._main(["warm-si", "--dry-run", "--force"]) == 0 and calls == [("bulk", None)]


# ── 2026-10-03 live check: a provably wrong float never heads the chip ─────────
def _sized(si, fl, so):
    d = dict(CASES["eose_v2_float"]["doc"])
    d.update({"short_interest": si, "float_shares": fl, "shares_outstanding": so})
    return d


def test_NEGATIVE_brk_b_shape_a_float_under_the_short_falls_back_to_shares_out():
    # live BRK-B read 1,015.5% "of float": short ~1.9M vs a float on file of ~0.19M,
    # shares outstanding ~2.16B -> the float is the wrong number, not the position
    b = SR.si_block(_sized(1_900_000, 187_100, 2_160_000_000), FIX_TODAY)
    assert b["float_suspect"] == SR.SHORT_EXCEEDS_FLOAT
    assert b["pct_of_float"] is None and b["headline_basis"] == "shares_out"
    assert "float" not in b["chip"] and "shs out" in b["chip"]
    assert "the float looks wrong" in b["title"]
    assert any(r["k"] == "⚠ Counts disagree" for r in b["rows"])


def test_a_genuinely_small_float_is_kept():
    # UI shape: insiders hold ~93%, float 4.2M of 60.5M, short 0.4M -> real, kept
    b = SR.si_block(_sized(405_000, 4_224_881, 60_528_381), FIX_TODAY)
    assert b["float_suspect"] is None and b["headline_basis"] == "float"
    assert b["pct_of_float"] == 9.59


def test_a_real_short_above_the_float_is_kept_when_it_is_also_large_vs_shares_out():
    # GameStop-2021 shape: re-lent shares push short interest past the float; with
    # the short also above half of shares outstanding the float is not called wrong
    b = SR.si_block(_sized(71_000_000, 50_000_000, 69_700_000), FIX_TODAY)
    assert b["float_suspect"] is None and b["headline_basis"] == "float"
    assert b["pct_of_float"] == 142.0


def test_NEGATIVE_a_float_above_shares_out_never_heads_the_chip():
    b = SR.si_block(_sized(1_600_483, 106_100_000, 19_440_000), FIX_TODAY)
    assert b["float_suspect"] == SR.FLOAT_EXCEEDS_SHARES
    assert b["pct_of_float"] is None and b["chip"].startswith("🩳 SI 8.2% shs out")
