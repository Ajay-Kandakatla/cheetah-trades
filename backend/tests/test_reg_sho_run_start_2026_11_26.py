"""🔒 Reg SHO — the run's first day, read past the 30-day window for ASKED names only (2026-11-26, spec sitrack §3.4 A5).

Ajay 2026-11-26, verbatim: "can we make sure in the future these # are accurate ?" — WHLR read "day 30+" while it had
been on every Nasdaq list since 9/29 (40 settlement days; day 13 = Fri 10/16; start-by Mon 10/19).

Every list body in this file is SYNTHETIC (built here); the WHLR membership shape (on 9/29 → 11/25, off 9/28) is the
one re-counted twice in verify journal wf_f6d36638-f53 rows 9, 10.

Harness: this module's OWN autouse fixture (a module's fixture does not travel with an import) replaces the engine's
ONE outside-call seam with a recording refuser, resets the worker, the history breaker and the in-process ask set,
makes `_pause` a no-op, and asserts at teardown the seam was never reached. A test that wants an outside answer passes
its own `http=` fake.
"""
from __future__ import annotations

import inspect
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from short_interest import reg_sho as RS
from short_interest import reg_sho_runs as RUNS
from tests.test_reg_sho_threshold_2026_11_22 import (NASDAQ_302, FakeDB, FakeHTTP, Resp, StandIn, nasdaq_url, nyse_url,
                                                     seed_list, synthetic_nasdaq, synthetic_nyse)

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
NOW = datetime(2026, 11, 25, 23, 40, tzinfo=ET)       # Wed night: Nasdaq / NYSE 11-25 out, Cboe 11-24 the newest due
D = date.fromisoformat
THROUGH = D("2026-11-25")
CBOE_THROUGH = D("2026-11-24")
STORED_FROM = D("2026-10-09")                           # the stored Nasdaq list docs reach 10-09 (32 per market)
NASDAQ, NYSE, CBOE = RS.SOURCES
WHLR_CHIP = "🔒 Hard to borrow · threshold security · 11/25 · day 40 · close-out day passed Fri 10/16 · still on"


# ═════════════════════════════════════════════ the guard (this module's own)
@pytest.fixture(autouse=True)
def seam(monkeypatch):
    calls = []

    def recorder(url=None, *a, **k):
        calls.append(url)
        raise RuntimeError("reg_sho outside calls are refused in this file")
    monkeypatch.setattr(RS, "_http", recorder)
    monkeypatch.setattr(RS, "_bg", {"running": False, "last_start": None, "thread": None})
    monkeypatch.setattr(RS, "_hist", {"blocked_until": None})
    monkeypatch.setattr(RS, "_asks", {"seq": 0, "items": {}})
    monkeypatch.setattr(RS, "_pause", lambda s: None)
    yield calls
    t = RS._bg.get("thread")
    if t is not None:
        t.join(5)
    assert calls == [], "the engine reached the module seam: %s" % calls


# ═════════════════════════════════════════════ helpers (SYNTHETIC worlds)
def sdays(lo, hi):
    """Settlement days lo..hi, newest first."""
    out, d = [], RUNS.prev_settlement_day(hi)
    while d >= lo:
        out.append(d)
        d = RUNS.prev_settlement_day(d - timedelta(days=1))
    return out


def window(through):
    return RUNS.settlement_days_back(through, RS.RS_HIST_SETTLEMENT_DAYS)


def utc(dt):
    return dt.astimezone(UTC).isoformat()


def world(*, nasdaq=("WHLR",), nyse_arca=(), cboe=(), skip_nasdaq=(), whlr_off=()):
    """Every market holds every window list (so neither a refresh nor a backfill is due at NOW); the Nasdaq docs reach
    back to STORED_FROM. `nasdaq` names are on every stored Nasdaq list (minus `whlr_off` dates for WHLR)."""
    coll = StandIn()
    for d in sdays(STORED_FROM, THROUGH):
        if d.isoformat() in skip_nasdaq:
            continue
        names = [n for n in nasdaq if not (n == "WHLR" and d.isoformat() in whlr_off)]
        seed_list(coll, "nasdaq", d, ["ZNAS"] + names)
    for d in window(THROUGH):
        for mkt, _n in RS.NYSE_MARKETS:
            seed_list(coll, mkt, d, ["Z" + mkt[-3:].upper()] + (list(nyse_arca) if mkt == "nyse_arca" else []))
    for d in window(CBOE_THROUGH):
        seed_list(coll, "cboe_bzx", d, ["ZCBX"] + list(cboe))
    return coll


def nasdaq_file(d, names):
    return Resp(200, synthetic_nasdaq(d, ["%s|SYNTHETIC|S|Y|N|" % s for s in names]))


def whlr_answers(*, extra=(), back_to=D("2026-09-28"), first=D("2026-09-29")):
    """Nasdaq files for every settlement day before STORED_FROM back to `back_to`; WHLR on from `first`."""
    out = {}
    for d in sdays(back_to, STORED_FROM - timedelta(days=1)):
        out[nasdaq_url(d)] = nasdaq_file(d, ["ZNAS"] + list(extra) + (["WHLR"] if d >= first else []))
    return out


def walk_urls(lo, hi):
    return [nasdaq_url(d) for d in sdays(lo, hi)]


def cboe_file(d, syms):
    body = "\r\n".join([RS.CBOE_HEADER] + ["%s|SYNTHETIC" % s for s in syms] + [d.strftime("%Y%m%d") + "040000"])
    return Resp(200, body + "\r\n")


def nyse_files(d, arca):
    out = {}
    for mkt, name in RS.NYSE_MARKETS:
        rows = ["Z%s|SYNTHETIC|%s|Y||" % (mkt[-3:].upper(), name)] + (
            ["%s|SYNTHETIC|%s|Y||" % (s, name) for s in arca] if mkt == "nyse_arca" else [])
        out[nyse_url(mkt, d)] = Resp(200, synthetic_nyse(d, rows))
    return out


def join():
    t = RS._bg.get("thread")
    if t is not None:
        t.join(5)


def items(coll, now=NOW):
    return RS.payload(FakeDB(coll), now, kick=False)["items"]


def runstart(coll, sym, mkt="nasdaq"):
    return coll.docs.get("runstart|%s|%s" % (mkt, sym))


def ext_doc(coll, sym, *, start=None, on_from="2026-10-09", on_through="2026-11-25", blocked=None, blocked_on=None,
            tries=0, asked_at=None, mkt="nasdaq"):
    doc = {"_id": "runstart|%s|%s" % (mkt, sym), "kind": RS.RUNSTART_KIND, "market": mkt, "symbol": sym,
           "start": start, "on_from": on_from, "on_through": on_through, "blocked": blocked, "blocked_on": blocked_on,
           "tries": tries, "asked_at": asked_at or utc(NOW)}
    coll.docs[doc["_id"]] = doc
    return doc


class KickSpy:
    """Counts kick_refresh attempts; starts nothing."""

    def __init__(self):
        self.n = 0

    def __call__(self, *a, **k):
        self.n += 1
        return False


def resolved_whlr():
    coll = world()
    http = FakeHTTP(whlr_answers())
    out = RS.payload(FakeDB(coll), NOW, check=["WHLR"], http=http)
    join()
    return coll, http, out


# ═════════════════════════════════════════════ pure math (reg_sho_runs)
def test_settlement_days_between_counts_both_ends_and_skips_bank_holidays():
    assert RUNS.settlement_days_between(D("2026-09-29"), D("2026-11-25")) == 40
    assert RUNS.settlement_days_between(D("2026-10-09"), D("2026-10-13")) == 2         # 10-12 Columbus Day out
    assert RUNS.settlement_days_between(D("2026-11-10"), D("2026-11-12")) == 2         # 11-11 Veterans Day out
    assert RUNS.settlement_days_between(D("2026-11-25"), D("2026-11-25")) == 1


def test_NEGATIVE_settlement_days_between_reversed_or_closed_days_is_zero():
    assert RUNS.settlement_days_between(D("2026-11-25"), D("2026-11-24")) == 0
    assert RUNS.settlement_days_between(D("2026-10-12"), D("2026-10-12")) == 0         # bank holiday alone
    assert RUNS.settlement_days_between(D("2026-11-21"), D("2026-11-22")) == 0         # a weekend


def _open_run(through=THROUGH):
    days = window(through)
    return RUNS.run_for("WHLR", days, {d.isoformat(): frozenset(["WHLR"]) for d in days})


def test_ext_usable_needs_a_dict_contiguous_with_the_window():
    run = _open_run()
    assert run["state"] == "passed_open" and run["window_from"] == "2026-10-14"
    assert RUNS.ext_usable(run, {"on_from": "2026-09-29", "on_through": "2026-10-14"}) is True
    assert RUNS.ext_usable(run, {"on_from": "2026-09-29", "on_through": "2026-11-25"}) is True


@pytest.mark.parametrize("ext", [None, "x", {}, {"on_from": "2026-09-29"}, {"on_through": "2026-11-25"},
                                 {"on_from": "2026-09-29", "on_through": "2026-10-13"},
                                 {"on_from": "2026-09-29", "on_through": "garbage"}])
def test_NEGATIVE_ext_usable_rejects_missing_broken_or_stale_docs(ext):
    assert RUNS.ext_usable(_open_run(), ext) is False


def test_extend_run_with_a_start_is_the_passed_run_with_true_dates():
    r = RUNS.extend_run(_open_run(), {"start": "2026-09-29", "on_from": "2026-09-29", "on_through": "2026-11-25"})
    assert r["state"] == "passed" and r["days"] == 40 and r["start"] == "2026-09-29"
    assert (r["day11"], r["day13"], r["day13_late"], r["start_by"]) == ("2026-10-14", "2026-10-16", "2026-10-19",
                                                                        "2026-10-19")
    assert r["read_back_to"] is None and r["blocked"] is None
    assert RS.past_closeout_text(r) == "🔒 day 27 past close-out"


def test_extend_run_without_a_start_counts_back_to_on_from():
    r = RUNS.extend_run(_open_run(), {"start": None, "on_from": "2026-10-08", "on_through": "2026-11-25",
                                      "blocked": "missing"})
    assert r["state"] == "passed_open" and r["days"] == 33 and r["start"] is None
    assert r["read_back_to"] == "2026-10-08" and r["blocked"] == "missing" and r["day13"] is None
    assert RS.past_closeout_text(r) == "🔒 day 20+ past close-out"


def test_NEGATIVE_counting_reached_unknown_passed_and_holed_runs_are_byte_identical():
    days = window(THROUGH)
    ext = {"start": "2026-09-29", "on_from": "2026-09-29", "on_through": "2026-11-25"}
    runs = []
    for on in (4, RUNS.REG_SHO_CLOSEOUT_SETTLEMENT_DAYS, 20):
        mem = {d.isoformat(): frozenset(["Z"] if i < on else []) for i, d in enumerate(days)}
        runs.append(RUNS.run_for("Z", days, mem))
    holed = {d.isoformat(): frozenset(["Z"]) for d in days}
    holed[days[-1].isoformat()] = None
    runs.append(RUNS.run_for("Z", days, holed))
    runs.append(RUNS.unknown_block())
    assert [r["state"] for r in runs] == ["counting", "reached", "passed", "passed_open", "unknown"]
    assert runs[3]["missing"] is not None
    for r in runs:
        assert RUNS.extend_run(r, ext) == r and "read_back_to" in r and r["read_back_to"] is None
        assert r["blocked"] is None


def test_NEGATIVE_a_stale_ext_leaves_the_open_run_alone():
    run = _open_run()
    assert RUNS.extend_run(run, {"start": "2026-09-29", "on_from": "2026-09-29", "on_through": "2026-10-13"}) == run


# ═════════════════════════════════════════════ ext_due — the ONE definition of done
def test_ext_due_table():
    run = _open_run()
    base = {"on_from": "2026-10-09", "on_through": "2026-11-25"}
    assert RS.ext_due(run, None, NOW) is True
    assert RS.ext_due(run, dict(base, on_through="2026-10-13", start="2026-09-29"), NOW) is True   # not usable
    assert RS.ext_due(run, dict(base, start="2026-09-29"), NOW) is False
    assert RS.ext_due(run, dict(base, blocked="cap"), NOW) is False
    assert RS.ext_due(run, dict(base, blocked=None, start=None), NOW) is True                       # budget ran out
    final = dict(base, blocked="missing", tries=RS.RS_HIST_MAX_TRIES, asked_at=utc(NOW - timedelta(days=9)))
    assert RS.ext_due(run, final, NOW) is False


def test_ext_due_error_follows_the_hole_clock_never_every_read():
    run = _open_run()
    err = {"on_from": "2026-10-09", "on_through": "2026-11-25", "blocked": "error", "tries": 1,
           "asked_at": utc(NOW - timedelta(minutes=5))}
    assert RS.ext_due(run, err, NOW) is False
    assert RS.ext_due(run, err, NOW + timedelta(minutes=RS.RS_RETRY_MIN)) is True
    late = dict(err, tries=RS.RS_HIST_MAX_TRIES)
    assert RS.ext_due(run, late, NOW + timedelta(minutes=RS.RS_RETRY_MIN)) is False
    assert RS.ext_due(run, late, NOW + timedelta(minutes=RS.RS_HIST_REASK_MIN)) is True


# ═════════════════════════════════════════════ the ask set
def test_the_ask_set_keeps_the_newest_check_max_newest_first():
    RS._note_asks([("nasdaq", "A%02d" % i) for i in range(RS.RS_CHECK_MAX + 1)])
    got = RS._asked()
    assert len(got) == RS.RS_CHECK_MAX
    assert ("nasdaq", "A00") not in got and got[0] == ("nasdaq", "A%02d" % RS.RS_CHECK_MAX)
    RS._note_asks([("nasdaq", "A05")])
    assert RS._asked()[0] == ("nasdaq", "A05") and len(RS._asked()) == RS.RS_CHECK_MAX


def test_NEGATIVE_kick_false_or_no_check_notes_nothing():
    coll = world()
    RS.payload(FakeDB(coll), NOW, kick=False, check=["WHLR"])
    RS.payload(FakeDB(coll), NOW)
    RS.payload(FakeDB(coll), NOW, kick=False)
    assert RS._asked() == [] and RS._bg["last_start"] is None


def test_NEGATIVE_an_unlisted_or_counting_name_is_not_asked():
    coll = world(nasdaq=("WHLR", "ZNEW"), whlr_off=())
    seed_list(coll, "nasdaq", D("2026-11-24"), ["ZNAS", "WHLR"])                      # ZNEW off 11-24 → counting
    spy = KickSpy()
    RS.kick_refresh, real = spy, RS.kick_refresh
    try:
        p = RS.payload(FakeDB(coll), NOW, check=["ZNEW", "NOPE"])
    finally:
        RS.kick_refresh = real
    assert p["items"]["ZNEW"]["run"]["state"] == "counting"
    assert RS._asked() == [] and spy.n == 0 and p["refreshing"] is False


# ═════════════════════════════════════════════ WHLR — the worked case
def test_whlr_asked_resolves_in_one_round_with_exactly_nine_nasdaq_calls():
    coll, http, first = resolved_whlr()
    assert first["refreshing"] is True and RS._asked() == [("nasdaq", "WHLR")]
    assert http.urls == walk_urls(D("2026-09-28"), D("2026-10-08")) and len(http.urls) == 9
    assert http.unexpected == []
    it = items(coll)["WHLR"]
    r = it["run"]
    assert r["state"] == "passed" and r["days"] == 40 and r["start"] == "2026-09-29"
    assert r["day13"] == "2026-10-16" and r["start_by"] == "2026-10-19"
    assert it["chip"] == WHLR_CHIP
    assert RS.past_closeout_text(r) == "🔒 day 27 past close-out"
    doc = runstart(coll, "WHLR")
    assert (doc["start"], doc["on_from"], doc["on_through"], doc["blocked"]) == ("2026-09-29", "2026-09-29",
                                                                                "2026-11-25", None)
    for d in sdays(D("2026-09-28"), D("2026-10-08")):                                  # backfilled, never newest
        assert coll.docs["list|nasdaq|%s" % d.isoformat()]["backfilled"] is True


def test_whlr_kicks_end_after_done_twenty_reads_start_zero_workers():
    coll, _http, _ = resolved_whlr()
    RS._bg.update({"running": False, "last_start": None, "thread": None})
    spy = KickSpy()
    real = RS.kick_refresh
    RS.kick_refresh = spy
    try:
        outs = [RS.payload(FakeDB(coll), NOW + timedelta(minutes=i), check=["WHLR"]) for i in range(20)]
    finally:
        RS.kick_refresh = real
    assert spy.n == 0
    assert all(o["refreshing"] is False and o["retry_after_sec"] is None for o in outs)
    assert all(o["items"]["WHLR"]["chip"] == WHLR_CHIP for o in outs)


@pytest.mark.parametrize("blocked,tries", [("cap", 0), ("missing", RS.RS_HIST_MAX_TRIES)])
def test_NEGATIVE_cap_and_final_missing_end_the_kicks(blocked, tries):
    coll = world()
    ext_doc(coll, "WHLR", on_from="2026-10-09", blocked=blocked, blocked_on="2026-10-08", tries=tries,
            asked_at=utc(NOW - timedelta(days=3)))
    spy = KickSpy()
    real = RS.kick_refresh
    RS.kick_refresh = spy
    try:
        outs = [RS.payload(FakeDB(coll), NOW, check=["WHLR"]) for _ in range(20)]
    finally:
        RS.kick_refresh = real
    assert spy.n == 0 and all(o["refreshing"] is False for o in outs)
    assert RS._asked() == [("nasdaq", "WHLR")]                         # noted (refix 2026-11-26), never kicked
    assert outs[0]["items"]["WHLR"]["run"]["state"] == "passed_open"


def test_an_error_block_is_due_again_only_on_the_hole_clock():
    coll = world()
    ext_doc(coll, "WHLR", on_from="2026-10-09", blocked="error", blocked_on="2026-10-08", tries=1,
            asked_at=utc(NOW - timedelta(minutes=5)))
    spy = KickSpy()
    real = RS.kick_refresh
    RS.kick_refresh = spy
    try:
        for _ in range(10):
            RS.payload(FakeDB(coll), NOW, check=["WHLR"])
        assert spy.n == 0 and RS._asked() == [("nasdaq", "WHLR")]      # noted (refix 2026-11-26), never kicked
        RS.payload(FakeDB(coll), NOW + timedelta(minutes=RS.RS_RETRY_MIN), check=["WHLR"])
        assert spy.n == 1 and RS._asked() == [("nasdaq", "WHLR")]
    finally:
        RS.kick_refresh = real


def test_a_resumed_error_walk_starts_at_on_from_and_counts_tries():
    coll = world()
    ext_doc(coll, "WHLR", on_from="2026-10-09", blocked="error", blocked_on="2026-10-08", tries=1,
            asked_at=utc(NOW - timedelta(minutes=RS.RS_RETRY_MIN)))
    RS._note_asks([("nasdaq", "WHLR")])
    http = FakeHTTP({nasdaq_url(D("2026-10-08")): Resp(500, "")})
    out = RS.extend_runs(coll, NOW, http=http)
    assert http.urls == [nasdaq_url(D("2026-10-08"))] and out["calls"] == 1 and out["blocked"] == 1
    doc = runstart(coll, "WHLR")
    assert (doc["blocked"], doc["blocked_on"], doc["tries"]) == ("error", "2026-10-08", 2)


# ═════════════════════════════════════════════ scope — only asked names, Nasdaq first, a market stops when done
def _fifty_nine():
    nas = tuple("ZN%02d" % i for i in range(23))
    arca = tuple("ZA%02d" % i for i in range(5))
    cbo = tuple("ZC%02d" % i for i in range(31))
    return nas, arca, cbo


def test_NEGATIVE_an_empty_ask_set_makes_zero_outside_calls_though_59_names_are_passed_open():
    nas, arca, cbo = _fifty_nine()
    coll = world(nasdaq=nas, nyse_arca=arca, cboe=cbo)
    its = items(coll)
    assert [its[n]["run"]["state"] for n in nas + arca + cbo] == ["passed_open"] * 59
    http = FakeHTTP({})
    assert RS.extend_runs(coll, NOW, http=http)["calls"] == 0
    p = RS.payload(FakeDB(coll), NOW, http=http)                                       # no check: nothing kicks
    assert RS.kick_refresh(coll, NOW, http=http) is True
    join()
    assert http.urls == [] and p["refreshing"] is False and RS._asked() == []
    assert not [k for k in coll.docs if k.startswith("runstart|")]


def test_NEGATIVE_an_unasked_long_listed_name_is_never_walked():
    coll = world(nasdaq=("WHLR", "ZLNG"))
    answers = whlr_answers(extra=("ZLNG",), back_to=D("2026-03-01"))                  # ZLNG on 200+ days back
    http = FakeHTTP(answers)
    RS.payload(FakeDB(coll), NOW, check=["WHLR"], http=http)
    join()
    assert len(http.urls) == 9 and items(coll)["WHLR"]["run"]["state"] == "passed"
    assert runstart(coll, "ZLNG") is None and items(coll)["ZLNG"]["run"]["state"] == "passed_open"


def test_markets_walk_in_registry_order_and_an_unasked_market_makes_no_call():
    coll = world(nyse_arca=("ZARC",), cboe=("ZCBO",))
    answers = whlr_answers()
    answers.update(nyse_files(D("2026-10-13"), arca=()))                               # ZARC off 10-13
    answers[RS.source_url(CBOE, "cboe_bzx", D("2026-10-09"))] = cboe_file(D("2026-10-09"), ["ZCBX"])
    RS._note_asks([("cboe_bzx", "ZCBO"), ("nyse_arca", "ZARC"), ("nasdaq", "WHLR")])
    http = FakeHTTP(answers)
    out = RS.extend_runs(coll, NOW, http=http)
    hosts = ["nasdaq" if "nasdaqtrader" in u else "nyse" if "nyse.com" in u else "cboe" for u in http.urls]
    assert hosts == ["nasdaq"] * 9 + ["nyse"] * 3 + ["cboe"]
    assert out["resolved"] == 3 and out["names"] == 3 and out["calls"] == 13
    assert items(coll)["ZARC"]["run"]["start"] == "2026-10-14"
    assert items(coll)["ZCBO"]["run"]["start"] == "2026-10-13"


def test_NEGATIVE_only_the_asked_market_is_walked():
    coll = world(nyse_arca=("ZARC",), cboe=("ZCBO",))
    http = FakeHTTP(whlr_answers())
    RS._note_asks([("nasdaq", "WHLR")])
    RS.extend_runs(coll, NOW, http=http)
    assert all("nasdaqtrader" in u for u in http.urls) and len(http.urls) == 9
    assert runstart(coll, "ZARC", "nyse_arca") is None and runstart(coll, "ZCBO", "cboe_bzx") is None


def test_a_name_off_the_list_before_the_window_resolves_with_one_call():
    coll = world(nasdaq=("WHLR", "ZSHT"))
    answers = whlr_answers()
    RS._note_asks([("nasdaq", "ZSHT")])
    http = FakeHTTP(answers)
    out = RS.extend_runs(coll, NOW, http=http)
    assert http.urls == [nasdaq_url(D("2026-10-08"))] and out["resolved"] == 1
    assert items(coll)["ZSHT"]["run"]["start"] == "2026-10-09"
    assert items(coll)["ZSHT"]["run"]["days"] == 32


# ═════════════════════════════════════════════ blocked walks and their words
def test_NEGATIVE_a_missing_list_inside_the_walk_blocks_it_and_says_so():
    coll = world()
    http = FakeHTTP({nasdaq_url(D("2026-10-08")): nasdaq_file(D("2026-10-08"), ["ZNAS", "WHLR"]),
                     nasdaq_url(D("2026-10-07")): NASDAQ_302})
    RS._note_asks([("nasdaq", "WHLR")])
    out = RS.extend_runs(coll, NOW, http=http)
    assert out["calls"] == 2 and out["blocked"] == 1 and out["resolved"] == 0
    doc = runstart(coll, "WHLR")
    assert (doc["start"], doc["on_from"], doc["blocked"], doc["blocked_on"], doc["tries"]) == (
        None, "2026-10-08", "missing", "2026-10-07", 1)
    it = items(coll)["WHLR"]
    assert it["run"]["state"] == "passed_open" and it["run"]["read_back_to"] == "2026-10-08"
    assert it["run"]["days"] == 33
    assert it["chip"] == "🔒 Hard to borrow · threshold security · 11/25 · day 33+ · close-out day passed · still on"
    assert (" On every list read back to 10/8 (33 settlement days), so day 13 has passed. The lists before 10/8 could "
            "not be read, so the first day is not known to this app. ") in it["title"]
    assert RS.ext_due(it["run"], doc, NOW) is False                                    # missing: the long clock


def test_NEGATIVE_the_cap_blocks_the_walk_and_the_title_names_it(monkeypatch):
    monkeypatch.setattr(RS, "RS_RUN_START_MAX_SETTLEMENT_DAYS", 35)
    coll = world()
    http = FakeHTTP(whlr_answers())
    RS._note_asks([("nasdaq", "WHLR")])
    out = RS.extend_runs(coll, NOW, http=http)
    assert out["calls"] == 3 and out["blocked"] == 1
    doc = runstart(coll, "WHLR")
    assert doc["blocked"] == "cap" and doc["on_from"] == "2026-10-06" and doc["start"] is None
    it = items(coll)["WHLR"]
    assert it["run"]["days"] == 35 and it["run"]["blocked"] == "cap"
    assert "The lists before 10/6 are past the 35 settlement days this app reads back" in it["title"]
    assert RS.ext_due(it["run"], doc, NOW) is False


def test_one_round_never_passes_the_call_budget_backfill_and_walk_together(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_MAX_GETS", 5)
    holes = ("2026-11-20", "2026-11-19", "2026-11-18")
    coll = world(skip_nasdaq=holes)
    answers = whlr_answers()
    for iso in holes:
        answers[nasdaq_url(D(iso))] = nasdaq_file(D(iso), ["ZNAS", "WHLR"])
    http = FakeHTTP(answers)
    RS._note_asks([("nasdaq", "WHLR")])
    assert RS.kick_refresh(coll, NOW, http=http) is True
    join()
    assert len(http.urls) == 5
    assert http.urls[:3] == [nasdaq_url(D(i)) for i in holes]                          # the window first
    assert http.urls[3:] == walk_urls(D("2026-10-07"), D("2026-10-08"))
    it = items(coll)["WHLR"]
    assert it["run"]["read_back_to"] == "2026-10-07" and it["run"]["blocked"] is None
    assert "The lists before 10/7 have not been read yet, so the first day is not known to this app." in it["title"]
    assert RS.ext_due(it["run"], runstart(coll, "WHLR"), NOW) is True                 # due again: not done


def test_NEGATIVE_a_zero_calls_left_round_reads_held_lists_only():
    coll = world()
    RS._note_asks([("nasdaq", "WHLR")])
    out = RS.extend_runs(coll, NOW, http=FakeHTTP({}), calls_left=0)
    assert out["calls"] == 0 and runstart(coll, "WHLR")["on_from"] == "2026-10-09"
    assert runstart(coll, "WHLR")["blocked"] is None


# ═════════════════════════════════════════════ contiguity
def test_NEGATIVE_an_ext_older_than_the_window_is_ignored_and_the_name_is_due_again():
    coll = world()
    ext_doc(coll, "WHLR", start="2026-09-29", on_from="2026-09-29", on_through="2026-10-13")
    it = items(coll)["WHLR"]
    assert it["chip"] == "🔒 Hard to borrow · threshold security · 11/25 · day 30+ · close-out day passed · still on"
    spy = KickSpy()
    real = RS.kick_refresh
    RS.kick_refresh = spy
    try:
        p = RS.payload(FakeDB(coll), NOW, check=["WHLR"])
    finally:
        RS.kick_refresh = real
    assert spy.n == 1 and RS._asked() == [("nasdaq", "WHLR")] and p["items"]["WHLR"]["run"]["days"] == 30


def test_NEGATIVE_a_name_that_left_the_list_reads_from_the_window_alone():
    coll = world(whlr_off=("2026-11-24",))
    ext_doc(coll, "WHLR", start="2026-09-29", on_from="2026-09-29", on_through="2026-11-20")
    r = items(coll)["WHLR"]["run"]
    assert r["state"] == "counting" and r["days"] == 1 and r["start"] == "2026-11-25"


def test_a_resolved_names_on_through_moves_up_with_no_outside_call():
    coll = world()
    ext_doc(coll, "WHLR", start="2026-09-29", on_from="2026-09-29", on_through="2026-11-20")
    RS._note_asks([("nasdaq", "WHLR")])
    out = RS.extend_runs(coll, NOW, http=FakeHTTP({}))
    assert out["calls"] == 0 and runstart(coll, "WHLR")["on_through"] == "2026-11-25"
    assert runstart(coll, "WHLR")["start"] == "2026-09-29"


def test_after_a_restart_card_reads_note_a_resolved_name_and_the_round_moves_its_on_through_up():
    """Refix 2026-11-26: an API restart empties the ask set; a resolved doc 3 days behind must still be moved up by
    the worker's round once a card asks — before, only DUE names were noted and the doc fell behind the window."""
    coll = world()
    ext_doc(coll, "WHLR", start="2026-09-29", on_from="2026-09-29", on_through="2026-11-20")
    assert RS._asked() == []
    spy = KickSpy()
    real = RS.kick_refresh
    RS.kick_refresh = spy
    try:
        outs = [RS.payload(FakeDB(coll), NOW, check=["WHLR"]) for _ in range(5)]
    finally:
        RS.kick_refresh = real
    assert spy.n == 0                                                   # a resolved name never kicks
    assert all(o["refreshing"] is False and o["retry_after_sec"] is None for o in outs)
    assert all(o["items"]["WHLR"]["chip"] == WHLR_CHIP for o in outs)
    assert RS._asked() == [("nasdaq", "WHLR")]
    http = FakeHTTP({})
    r = RS.extend_runs(coll, NOW, http=http)
    assert r["calls"] == 0 and http.urls == []
    doc = runstart(coll, "WHLR")
    assert (doc["start"], doc["on_from"], doc["on_through"]) == ("2026-09-29", "2026-09-29", "2026-11-25")


def test_NEGATIVE_without_the_note_the_round_leaves_a_resolved_doc_behind():
    coll = world()
    ext_doc(coll, "WHLR", start="2026-09-29", on_from="2026-09-29", on_through="2026-11-20")
    RS.payload(FakeDB(coll), NOW, check=["WHLR"], kick=False)           # the cron pass / nightly: notes nothing
    RS.payload(FakeDB(coll), NOW)                                       # no check: notes nothing
    assert RS._asked() == []
    assert RS.extend_runs(coll, NOW, http=FakeHTTP({}))["calls"] == 0
    assert runstart(coll, "WHLR")["on_through"] == "2026-11-20"


def test_a_resolved_and_a_due_name_both_noted_the_due_one_newest_and_one_kick():
    coll = world(nasdaq=("WHLR", "ZDUE"))
    ext_doc(coll, "WHLR", start="2026-09-29", on_from="2026-09-29", on_through="2026-11-20")
    spy = KickSpy()
    real = RS.kick_refresh
    RS.kick_refresh = spy
    try:
        RS.payload(FakeDB(coll), NOW, check=["ZDUE", "WHLR", "whlr"])
    finally:
        RS.kick_refresh = real
    assert spy.n == 1
    assert RS._asked() == [("nasdaq", "ZDUE"), ("nasdaq", "WHLR")]       # due newest: the set evicts oldest first


def test_NEGATIVE_due_asks_splits_and_holds_nothing_while_the_breaker_is_open():
    coll = world(nasdaq=("WHLR", "ZDUE", "ZNEW"))
    seed_list(coll, "nasdaq", D("2026-11-24"), ["ZNAS", "WHLR", "ZDUE"])                # ZNEW off 11-24 → counting
    ext_doc(coll, "WHLR", start="2026-09-29", on_from="2026-09-29", on_through="2026-11-20")
    loaded = RS.load(coll)
    hist = RS.load_history(coll, loaded)
    its = RS.payload(FakeDB(coll), NOW, kick=False)["items"]
    noted, due = RS._due_asks(["WHLR", "ZDUE", "ZNEW", "NOPE"], its, hist, NOW)
    assert noted == [("nasdaq", "WHLR"), ("nasdaq", "ZDUE")] and due == [("nasdaq", "ZDUE")]
    RS._hist["blocked_until"] = RS._mono() + 3600
    assert RS._due_asks(["WHLR", "ZDUE"], its, hist, NOW) == ([], [])


def test_the_window_title_says_how_far_the_app_read():
    it = items(world())["WHLR"]
    assert (" On every list read for the last 30 settlement days (back to 10/14), so day 13 has passed; this app has "
            "read only those 30 days, so the date is not known to it. ") in it["title"]
    assert it["run"]["read_back_to"] is None and it["run"]["blocked"] is None


# ═════════════════════════════════════════════ guards
def test_NEGATIVE_a_raising_runstart_write_trips_the_breaker_and_the_read_serves_day_30_plus():
    class NoRunstartWrites(StandIn):
        def replace_one(self, flt, doc, upsert=False):
            if doc.get("kind") == RS.RUNSTART_KIND:
                raise RuntimeError("synthetic: the runstart write fails")
            return super().replace_one(flt, doc, upsert=upsert)
    coll = NoRunstartWrites()
    coll.docs = world().docs
    RS._note_asks([("nasdaq", "WHLR")])
    RS.extend_runs(coll, NOW, http=FakeHTTP(whlr_answers()))
    assert RS._hist_blocked() is True
    assert items(coll)["WHLR"]["chip"].endswith("· day 30+ · close-out day passed · still on")
    spy = KickSpy()
    real = RS.kick_refresh
    RS.kick_refresh = spy
    try:
        RS.payload(FakeDB(coll), NOW, check=["WHLR"])
    finally:
        RS.kick_refresh = real
    assert spy.n == 0                                                                   # nothing kicks while paused
    assert RS.extend_runs(coll, NOW, http=FakeHTTP({}))["calls"] == 0


def test_NEGATIVE_a_broken_ext_doc_never_breaks_the_read():
    coll = world()
    coll.docs["runstart|nasdaq|WHLR"] = {"_id": "runstart|nasdaq|WHLR", "kind": RS.RUNSTART_KIND, "market": "nasdaq",
                                         "symbol": "WHLR", "on_through": "2026-11-25", "on_from": "garbage",
                                         "start": "garbage", "blocked": "weird"}
    it = items(coll)["WHLR"]
    assert it["run"]["state"] == "passed_open" and it["run"]["days"] == 30


def test_NEGATIVE_extend_runs_never_raises():
    class Boom(StandIn):
        def find(self, flt):
            raise RuntimeError("synthetic")
    RS._note_asks([("nasdaq", "WHLR")])
    out = RS.extend_runs(Boom(), NOW, http=FakeHTTP({}))
    assert out["calls"] == 0
    assert RS.extend_runs(None, NOW, http=FakeHTTP({}))["calls"] == 0


def test_load_history_reads_runstart_docs_with_one_bounded_find():
    coll = world()
    ext_doc(coll, "WHLR", start="2026-09-29", on_from="2026-09-29")
    seen = []
    real = coll.find

    def spy(flt):
        seen.append(flt)
        return real(flt)
    loaded = RS.load(coll)
    coll.find = spy
    h = RS.load_history(coll, loaded)
    assert {"kind": RS.RUNSTART_KIND, "on_through": {"$gte": "2026-10-13"}} in seen and len(seen) == 3
    assert h["ext"][("nasdaq", "WHLR")]["start"] == "2026-09-29"


# ═════════════════════════════════════════════ source pins
def _src(fn):
    return re.sub(r'"""[\s\S]*?"""', "", inspect.getsource(fn))


def test_source_pins_the_walk_runs_only_in_the_worker_after_backfill():
    kick = _src(RS.kick_refresh)
    assert kick.index("backfill_history(") < kick.index("extend_runs(")
    assert "RS_HIST_MAX_GETS - used" in kick
    for fn in (RS.payload, RS.refresh_due, RS.backfill_history, RS._due_asks):
        assert "extend_runs(" not in _src(fn), fn.__name__


def test_source_pins_the_read_and_the_ask_set_hold_no_mongo_write():
    write = re.compile(r"replace_one|insert_|update_one|update_many|delete_|_write_|bulk_write")
    for fn in (RS.payload, RS._note_asks, RS._asked, RS._due_asks, RS.ext_due, RS.load_history, RS._run_block):
        assert not write.search(_src(fn)), fn.__name__


def test_constants_by_name():
    assert RS.RS_RUN_START_MAX_SETTLEMENT_DAYS == 250 and RS.RUNSTART_KIND == "runstart"
    assert RS.RS_HIST_SETTLEMENT_DAYS == 30                                             # his call #11 — unchanged
