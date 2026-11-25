"""🔒 Reg SHO close-out day on the "Hard to borrow" tag — run math, history backfill, words, guards (2026-11-24).

Ajay 2026-11-23, verbatim: "I need to know when it would like to Potentially squeeze.." · "Add a tag with date in it.."

Spec: scratchpad regsho_tag/spec.md §3.1-§3.5, §4 `be`. The membership fixture
tests/fixtures/reg_sho_history/nasdaq_membership_2026_10_13_to_11_20.json is DERIVED: the membership of three names
(AKAN, GMEX, SMTK) read from the real Nasdaq threshold files 10-13 … 11-20, not a verbatim file. It holds no 10-09 /
10-08 key (those two window days are "not read") and keeps the 11-11 key (Veterans Day — the bank-holiday NEGATIVE).
Every other body in this file is built here and named SYNTHETIC.

Harness: this module's OWN autouse fixture (a module's fixture does not travel with an import) replaces the engine's ONE
outside-call seam with a recording refuser, resets the worker and the history breaker, makes `_pause` a no-op, and
asserts at teardown the seam was never reached.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from short_interest import api as SAPI
from short_interest import client as SIC
from short_interest import reg_sho as RS
from short_interest import reg_sho_runs as RUNS
from tests.test_reg_sho_threshold_2026_11_22 import (FORBIDDEN, NASDAQ_302, FakeDB, FakeHTTP, ReadTimeout, Resp,
                                                     StandIn, build_golden_payload, fixture_answers, golden_round,
                                                     nasdaq_url, nyse_url, seed_list, synthetic_nasdaq,
                                                     synthetic_nyse)

BACKEND = Path(__file__).resolve().parents[1]
HIST_FIX = BACKEND / "tests" / "fixtures" / "reg_sho_history" / "nasdaq_membership_2026_10_13_to_11_20.json"
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
NOW = datetime(2026, 11, 22, 20, 42, tzinfo=ET)              # Sunday night: the Nasdaq 11-20 list is the newest
T_STALE = datetime(2026, 11, 23, 23, 30, tzinfo=ET)          # E = 11-23 for Nasdaq; the 11-20 list is held
NASDAQ, NYSE, CBOE = RS.SOURCES
FORBIDDEN_NEW = re.compile(r"forecast|guarantee|buy-in|must cover|earliest|forced", re.I)
TITLE_MAX = 1350                                              # a regression bound, not an engine constant
D = date.fromisoformat


def prefix(sym):
    return ("🔒 Hard to borrow — %s is a Reg SHO threshold security on the Nasdaq list for 2026-11-20: fails to "
            "deliver of at least 10,000 shares and at least 0.5%% of shares outstanding for 5 straight settlement "
            "days (SEC Regulation SHO Rule 203(c)(6)). The threshold list measures persistent fails to deliver, not "
            "a broker's borrow rate — a broker's own hard-to-borrow list can differ. A data label, not a signal. "
            "UNMEASURED." % sym)


TAILS = (" Rule 204 already requires a fail in any stock to be closed out 1 to 3 settlement days after settlement, so "
         "fails generally do not last 13 (SEC staff); for a Rule 144 sale the count is 35, not 13. Fails to deliver "
         "only, not every short position. A rule date — it says nothing about price. Not advice.")
RULE_S = ("After day 13, Rule 203(b)(3) makes a clearing firm buy shares to close out a fail to deliver it carried on "
          "every one of those days")

GMEX = {
    "chip": "🔒 Hard to borrow · threshold security · 11/20 · day 9 of 13 · close-out day Fri 11/27 if it stays on",
    "short": "🔒 close-out Fri 11/27 · day 9 of 13",
    "label": ("🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 9 of 13 · close-out day "
              "Fri 11/27 if it stays on"),
    "tail": (" On the list 9 straight settlement days since 11/9. Day 13 = Fri 11/27 if it stays on (Mon 11/30 if "
             "counted from each list's next open). " + RULE_S + "; the buying may come from day 11 (Tue 11/24) and "
             "must start by the next open (SEC staff FAQ 6.5, 6.7)." + TAILS),
}
SMTK = {
    "chip": "🔒 Hard to borrow · threshold security · 11/20 · day 18 · close-out day passed Fri 11/13 · still on",
    "short": "🔒 close-out passed Fri 11/13 · day 18",
    "label": ("🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 18 · close-out day passed "
              "Fri 11/13 · still on the list"),
    "tail": (" On the list 18 straight settlement days since 10/27. Day 13 was Fri 11/13 (Mon 11/16 if counted from "
             "each list's next open); it is still on the list 5 settlement days later. " + RULE_S + ". Staying listed "
             "means the total of fails is still over the level, not that any one fail is that old — a name leaves a "
             "list only after 5 straight settlement days back under it." + TAILS),
}
AKAN = {
    "chip": "🔒 Hard to borrow · threshold security · 11/20 · day 1 of 13 · close-out day Wed 12/9 if it stays on",
    "short": "🔒 close-out Wed 12/9 · day 1 of 13",
    "label": ("🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 1 of 13 · close-out day "
              "Wed 12/9 if it stays on"),
    "tail": (" On the list 1 straight settlement day since 11/20. Day 13 = Wed 12/9 if it stays on (Thu 12/10 if "
             "counted from each list's next open). " + RULE_S + "; the buying may come from day 11 (Mon 12/7) and "
             "must start by the next open (SEC staff FAQ 6.5, 6.7)." + TAILS),
}


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
    monkeypatch.setattr(RS, "_pause", lambda s: None)
    yield calls
    t = RS._bg.get("thread")
    if t is not None:
        t.join(5)
    assert calls == [], "the engine reached the module seam: %s" % calls


# ═════════════════════════════════════════════ helpers
def derived():
    """{iso: frozenset} — the DERIVED membership (3 names), no 11-23 key."""
    raw = json.loads(HIST_FIX.read_text())
    return {k: frozenset(v) for k, v in raw.items()}


def days_1120(n=30):
    return RUNS.settlement_days_back(D("2026-11-20"), n)


def utc(dt):
    return dt.astimezone(UTC).isoformat()


def seed_nasdaq_history(coll, mem=None, *, skip=()):
    """Seed one believed Nasdaq list doc per fixture date (SYNTHETIC docs, DERIVED names)."""
    for iso, names in (mem if mem is not None else derived()).items():
        if iso in skip:
            continue
        seed_list(coll, "nasdaq", D(iso), sorted(names), confirmed=True)
    return coll


def world(*, skip=(), mem=None):
    return seed_nasdaq_history(StandIn(), mem, skip=skip)


def strings_of(p):
    out = []
    for it in p["items"].values():
        out += [it["chip"], it["short"], it["label"], it["title"]]
    return out


def synthetic_cboe(d, syms):
    """SYNTHETIC Cboe BZX file (CRLF) for date d."""
    return "\r\n".join([RS.CBOE_HEADER] + ["%s|SYNTHETIC" % s for s in syms] + [d.strftime("%Y%m%d") + "040000"]) + "\r\n"


def full_answers(dates, nasdaq_names=("ZNAS",)):
    """SYNTHETIC found answers for every source URL of every date."""
    out = {}
    for d in dates:
        out[nasdaq_url(d)] = Resp(200, synthetic_nasdaq(d, ["%s|SYNTHETIC|S|Y|N|" % s for s in nasdaq_names]))
        for mkt, name in RS.NYSE_MARKETS:
            out[nyse_url(mkt, d)] = Resp(200, synthetic_nyse(d, ["Z%s|SYNTHETIC|%s|Y||" % (mkt[:3].upper(), name)]))
        out[RS.source_url(CBOE, "cboe_bzx", d)] = Resp(200, synthetic_cboe(d, ["ZCBO"]))
    return out


def seed_all_newest(coll, d=D("2026-11-20"), cboe=D("2026-11-19")):
    """SYNTHETIC: every market holds a believed newest list, so no latest refresh is due at NOW."""
    if "list|nasdaq|%s" % d.isoformat() not in coll.docs:
        seed_list(coll, "nasdaq", d, ["ZNAS"])
    for mkt, _n in RS.NYSE_MARKETS:
        if "list|%s|%s" % (mkt, d.isoformat()) not in coll.docs:
            seed_list(coll, mkt, d, ["Z" + mkt[:3].upper()])
    if "list|cboe_bzx|%s" % cboe.isoformat() not in coll.docs:
        seed_list(coll, "cboe_bzx", cboe, ["ZCBO"])
    return coll


def seed_window(coll, n_days):
    """Docs for every window day of every market, so no fetch is due (window = n_days)."""
    for d in days_1120(n_days):
        for mkt in ("nasdaq",) + tuple(m for m, _n in RS.NYSE_MARKETS):
            if "list|%s|%s" % (mkt, d.isoformat()) not in coll.docs:
                seed_list(coll, mkt, d, ["Z" + mkt[:3].upper()])
    for d in RUNS.settlement_days_back(D("2026-11-19"), n_days):
        if "list|cboe_bzx|%s" % d.isoformat() not in coll.docs:
            seed_list(coll, "cboe_bzx", d, ["ZCBO"])
    return coll


def zero_row(coll, mkt, d, *, minutes_ago):
    fa = utc(NOW - timedelta(minutes=minutes_ago))
    return seed_list(coll, mkt, d, [], fetched_at=fa, confirmed=False)


def todo_now(coll, now=NOW):
    loaded = RS.load(coll)
    return RS.history_todo(loaded, RS.load_history(coll, loaded), now)


def hole(coll, op, src_key, d, *, result="error", tries=1, minutes_ago=0, mkt=None, now=NOW):
    hid = "nolist|%s|%s" % (src_key, d.isoformat()) if op == "fetch" else "nolist|confirm|%s|%s" % (mkt, d.isoformat())
    coll.docs[hid] = {"_id": hid, "kind": "nolist", "op": op, "source": src_key, "market": mkt,
                      "trade_date": d.isoformat(), "result": result, "error": None if result == "missing" else "x",
                      "tries": tries, "asked_at": utc(now - timedelta(minutes=minutes_ago))}
    return coll.docs[hid]


# ═════════════════════════════════════════════ calendar
def test_bank_holidays_and_the_settlement_calendar():
    assert RUNS.columbus_day(2026) == D("2026-10-12")
    assert [RUNS.veterans_day_observed(y) for y in (2026, 2027, 2028, 2029)] == [
        D("2026-11-11"), D("2027-11-11"), None, D("2029-11-12")]                 # Sat → None, Sun → Mon
    assert RUNS.is_settlement_day(D("2026-11-10")) is True
    assert RUNS.is_settlement_day(D("2026-11-27")) is True                      # the half day counts
    assert RUNS.is_settlement_day(D("2026-11-11")) is False                     # Veterans Day
    assert RUNS.is_settlement_day(D("2026-10-12")) is False                     # Columbus Day
    assert RUNS.is_settlement_day(D("2026-11-26")) is False                     # Thanksgiving (market shut)
    assert RUNS.add_settlement_days(D("2026-11-25"), 1) == D("2026-11-27")
    assert RUNS.add_settlement_days(D("2026-11-10"), 1) == D("2026-11-12")
    assert RUNS.add_settlement_days(D("2026-11-10"), 0) == D("2026-11-10")
    w = RUNS.settlement_days_back(D("2026-11-20"), 30)
    assert len(w) == 30 and w[0] == D("2026-11-20") and w[-1] == D("2026-10-08")
    assert D("2026-10-12") not in w and D("2026-11-11") not in w
    assert RUNS.settlement_days_back(D("2026-11-11"), 3) == [D("2026-11-10"), D("2026-11-09"), D("2026-11-06")]
    assert RUNS.prev_settlement_day(D("2026-11-22")) == D("2026-11-20")
    assert RUNS.next_trading_day(D("2026-11-25")) == D("2026-11-27")


@pytest.mark.parametrize("start,want", [
    ("2026-11-09", ("2026-11-24", "2026-11-27", "2026-11-30", "2026-11-30")),
    ("2026-10-27", ("2026-11-10", "2026-11-13", "2026-11-16", "2026-11-16")),
    ("2026-11-20", ("2026-12-07", "2026-12-09", "2026-12-10", "2026-12-10")),
])
def test_closeout_dates(start, want):
    got = RUNS.closeout_dates(D(start))
    assert tuple(got[k].isoformat() for k in ("day11", "day13", "day13_late", "start_by")) == want
    assert RUNS.first_buy_day() == 11


def test_first_buy_day_is_derived_from_the_two_constants(monkeypatch):
    monkeypatch.setattr(RUNS, "REG_SHO_CLOSEOUT_SETTLEMENT_DAYS", 10)
    assert RUNS.first_buy_day() == 8
    monkeypatch.setattr(RUNS, "REG_SHO_CLOSEOUT_BUY_WINDOW_DAYS", 2)
    assert RUNS.first_buy_day() == 9


# ═════════════════════════════════════════════ runs on the DERIVED fixture
def test_fixture_is_the_derived_membership_without_the_unpublished_day():
    mem = derived()
    assert "2026-11-23" not in mem                      # "file not published yet", never "off the list"
    assert "2026-11-11" in mem                          # kept: the bank-holiday NEGATIVE
    assert "2026-10-09" not in mem and "2026-10-08" not in mem
    assert set().union(*mem.values()) == {"AKAN", "GMEX", "SMTK"}


def test_runs_on_the_derived_fixture():
    days, mem = days_1120(), derived()
    s = RUNS.run_for("SMTK", days, mem)
    assert (s["state"], s["days"], s["start"], s["day13"]) == ("passed", 18, "2026-10-27", "2026-11-13")
    g = RUNS.run_for("GMEX", days, mem)
    assert (g["state"], g["days"], g["start"], g["day13"], g["day13_late"]) == (
        "counting", 9, "2026-11-09", "2026-11-27", "2026-11-30")
    assert g["day11"] == "2026-11-24" and g["start_by"] == "2026-11-30" and g["missing"] is None
    assert g["through"] == "2026-11-20" and g["window_from"] == "2026-10-08"
    assert g["rule_days"] == 13 and g["first_buy_day"] == 11
    a = RUNS.run_for("AKAN", days, mem)
    assert (a["state"], a["days"], a["start"]) == ("counting", 1, "2026-11-20")


def test_reached_is_exactly_the_rule_days():
    days = days_1120()
    mem = {d.isoformat(): frozenset(["ZZZT"]) if i < 13 else frozenset() for i, d in enumerate(days)}
    r = RUNS.run_for("ZZZT", days, mem)
    assert r["state"] == "reached" and r["days"] == 13 and r["day13"] == r["through"] == "2026-11-20"
    assert r["start"] == "2026-11-03"


def test_a_holiday_and_the_half_day_inside_a_run():
    days = RUNS.settlement_days_back(D("2026-11-27"), 30)
    on = {D("2026-11-16") + timedelta(days=i) for i in range(12)}
    mem = {d.isoformat(): (frozenset(["ZZZT"]) if d in on else frozenset()) for d in days}
    r = RUNS.run_for("ZZZT", days, mem)
    assert r["state"] == "counting" and r["days"] == 9 and r["start"] == "2026-11-16"   # 11-26 not, 11-27 counted


def test_on_every_list_of_the_window_is_passed_open():
    days = days_1120()
    r = RUNS.run_for("ZZZT", days, {d.isoformat(): frozenset(["ZZZT"]) for d in days})
    assert r["state"] == "passed_open" and r["days"] == 30 and r["missing"] is None
    assert all(r[k] is None for k in ("start", "day11", "day13", "day13_late", "start_by"))


def test_NEGATIVE_a_missing_list_day_is_neither_on_nor_off():
    mem = dict(derived())
    mem["2026-11-13"] = None
    r = RUNS.run_for("GMEX", days_1120(), mem)
    assert r["state"] == "unknown" and r["days"] == 5 and r["missing"] == "2026-11-13"
    assert r["days"] != 9 and r["start"] is None and r["day13"] is None
    del mem["2026-11-13"]                                       # an ABSENT key reads the same
    assert RUNS.run_for("GMEX", days_1120(), mem)["days"] == 5


def test_NEGATIVE_a_missing_day_after_the_rule_days_is_passed_open():
    mem = dict(derived())
    mem["2026-10-28"] = None
    r = RUNS.run_for("SMTK", days_1120(), mem)
    assert r["state"] == "passed_open" and r["days"] == 16 and r["day13"] is None and r["missing"] == "2026-10-28"


def test_NEGATIVE_off_and_back_on_restarts_the_run():
    r = RUNS.run_for("GMEX", days_1120(), derived())
    assert r["days"] != 14 and r["days"] == 9 and r["start"] == "2026-11-09"


def test_NEGATIVE_a_read_list_without_the_name_ends_the_run_and_is_not_a_hole():
    mem = dict(derived())
    assert mem["2026-11-06"] == frozenset(["SMTK"])
    r = RUNS.run_for("GMEX", days_1120(), mem)
    assert r["state"] == "counting" and r["missing"] is None                   # an empty believed list ends it
    mem["2026-11-06"] = frozenset()
    assert RUNS.run_for("GMEX", days_1120(), mem)["state"] == "counting"
    mem["2026-11-06"] = None
    assert RUNS.run_for("GMEX", days_1120(), mem)["state"] == "unknown"


@pytest.mark.parametrize("variant", ["absent", "with", "without"])
def test_NEGATIVE_veterans_day_is_never_counted(variant):
    mem = dict(derived())
    if variant == "absent":
        del mem["2026-11-11"]
    elif variant == "with":
        mem["2026-11-11"] = frozenset(["GMEX"])
    else:
        mem["2026-11-11"] = frozenset()
    r = RUNS.run_for("GMEX", days_1120(), mem)
    assert r["days"] == 9 and r["days"] != 10
    assert r["day13"] == "2026-11-27" and r["day13"] != "2026-11-25"


def test_NEGATIVE_never_on_is_unknown_with_no_dates():
    r = RUNS.run_for("ZZZZ", days_1120(), derived())
    assert r["state"] == "unknown" and r["days"] == 0 and r["day13"] is None and r["start"] is None
    p = RS.payload(FakeDB(world()), NOW, kick=False)
    assert "ZZZZ" not in p["items"]
    assert not [it for it in p["items"].values() if it["symbol"] == "ZZZZ"]


def test_an_empty_day_list_is_the_unknown_block():
    assert RUNS.run_for("GMEX", [], derived()) == RUNS.unknown_block()
    u = RUNS.unknown_block()
    assert u["state"] == "unknown" and u["days"] == 0 and u["rule_days"] == 13


# ═════════════════════════════════════════════ words through payload()
def _items(coll, now=NOW):
    return RS.payload(FakeDB(coll), now, kick=False)["items"]


@pytest.mark.parametrize("sym,want", [("GMEX", GMEX), ("SMTK", SMTK), ("AKAN", AKAN)])
def test_worked_strings_verbatim(sym, want):
    it = _items(world())[sym]
    assert (it["chip"], it["short"], it["label"]) == (want["chip"], want["short"], want["label"])
    assert it["title"] == prefix(sym) + want["tail"]
    assert it["run"]["state"] in ("counting", "passed")


def test_worked_unknown_strings():
    it = _items(world(skip=("2026-11-18",)))["GMEX"]
    assert it["chip"] == "🔒 Hard to borrow · threshold security · 11/20 · day count unknown"
    assert it["short"] == "🔒 Hard to borrow · 11/20"
    assert it["label"] == "🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day count unknown"
    assert it["title"] == prefix("GMEX") + (" Days on the list: not known — the Nasdaq list for 11/18 has not been "
                                            "read. Not advice.")
    assert it["run"]["days"] == 2 and it["run"]["missing"] == "2026-11-18"


def _zzzt_world(on_days):
    coll = StandIn()
    for i, d in enumerate(days_1120()):
        seed_list(coll, "nasdaq", d, ["ZZZT"] if i < on_days else [])
    return coll


def test_worked_passed_open_strings():
    it = _items(_zzzt_world(30))["ZZZT"]
    assert it["chip"] == "🔒 Hard to borrow · threshold security · 11/20 · day 30+ · close-out day passed · still on"
    assert it["short"] == "🔒 close-out passed · day 30+"
    assert it["label"] == ("🔒 Hard to borrow · Reg SHO threshold security · Nasdaq list for 11/20 · day 30+ · "
                           "close-out day passed · still on the list")
    assert it["title"] == prefix("ZZZT") + (" On every list read for the last 30 settlement days (back to 10/8), so "
                                            "day 13 has passed; its date is not known. " + RULE_S + "." + TAILS)


def test_worked_passed_open_hole_strings():
    it = _items(world(skip=("2026-10-28",)))["SMTK"]
    assert it["chip"] == "🔒 Hard to borrow · threshold security · 11/20 · day 16+ · close-out day passed · still on"
    assert it["short"] == "🔒 close-out passed · day 16+"
    assert it["title"] == prefix("SMTK") + (" On the list at least 16 straight settlement days, so day 13 has passed; "
                                            "its date is not known — the Nasdaq list for 10/28 has not been read. "
                                            + RULE_S + "." + TAILS)


def test_worked_reached_strings():
    it = _items(_zzzt_world(13))["ZZZT"]
    assert it["chip"] == "🔒 Hard to borrow · threshold security · 11/20 · day 13 of 13 · close-out day Fri 11/20"
    assert it["short"] == "🔒 close-out Fri 11/20 · day 13 of 13"
    assert it["title"].startswith(prefix("ZZZT") + " On the list 13 straight settlement days since 11/3. Day 13 = "
                                  "Fri 11/20, this list's date (Mon 11/23 if counted from each list's next open). "
                                  "After day 13, ")
    assert it["title"].endswith(TAILS)


def _stale(coll):
    coll.docs["state|nasdaq"] = {"_id": "state|nasdaq", "kind": "state", "source": "nasdaq",
                                 "attempt_at": utc(T_STALE), "attempt_for": "2026-11-23", "result": "error",
                                 "error": "timeout", "errors": RS.RS_ERROR_STRIKES, "good_date": "2026-11-20",
                                 "checked_at": None}
    return RS.payload(FakeDB(coll), T_STALE, kick=False)


def test_stale_stays_last_on_all_three_and_the_title():
    p = _stale(world())
    for sym in ("GMEX", "SMTK", "AKAN"):
        it = p["items"][sym]
        assert it["stale"] is True
        for k in ("chip", "short", "label"):
            assert it[k].endswith(" · stale"), it[k]
        assert it["title"].endswith(RS.STALE_TITLE % "11/20")
    g = p["items"]["GMEX"]
    assert g["chip"] == GMEX["chip"] + " · stale" and g["short"] == GMEX["short"] + " · stale"
    assert g["chip"][: -len(" · stale")].endswith(RS.IF_STAYS)


def test_every_dated_short_leads_with_the_date():
    items = dict(_items(world()))
    items.update(_items(_zzzt_world(13)))
    lead = RS.GLYPH + " " + RS.CLOSEOUT_WORD + " "
    for sym in ("GMEX", "SMTK", "AKAN", "ZZZT"):
        s = items[sym]["short"]
        assert s.startswith(lead), s
        m = re.search(r"(Mon|Tue|Wed|Thu|Fri) \d+/\d+", s)
        assert m and m.end() <= s.index(" · day"), s


def test_if_it_stays_on_only_while_counting():
    items = dict(_items(world()))
    assert items["GMEX"]["chip"].endswith(RS.IF_STAYS) and items["GMEX"]["label"].endswith(RS.IF_STAYS)
    assert items["AKAN"]["chip"].endswith(RS.IF_STAYS) and items["AKAN"]["label"].endswith(RS.IF_STAYS)
    others = [items["SMTK"], _items(_zzzt_world(13))["ZZZT"], _items(_zzzt_world(30))["ZZZT"]]
    for it in others:
        for k in ("chip", "short", "label"):
            assert RS.IF_STAYS not in it[k], it[k]


def test_NEGATIVE_smtk_already_past_never_says_of_13_or_if_it_stays_on():
    it = _items(world())["SMTK"]
    for k in ("chip", "short", "label"):
        assert "of 13" not in it[k] and RS.IF_STAYS not in it[k]


def test_the_numbers_move_with_the_constants(monkeypatch):
    monkeypatch.setattr(RUNS, "REG_SHO_CLOSEOUT_SETTLEMENT_DAYS", 10)
    p = RS.payload(FakeDB(world()), NOW, kick=False)
    g = p["items"]["GMEX"]
    assert "day 9 of 10" in g["chip"] and "Mon 11/23" in g["chip"] and g["short"] == "🔒 close-out Mon 11/23 · day 9 of 10"
    assert "from day 8 (" in g["title"]
    texts = strings_of(p) + [RS.rules_pick()]
    for t in texts:
        assert not re.search(r"of 13|[Dd]ay 13", t), t
    assert "dates day 10" in RS.rules_pick() and "from day 8)" in RS.rules_pick()


def test_the_rule_204_and_rule_144_numbers_move_hover_and_pick(monkeypatch):
    monkeypatch.setattr(RUNS, "REG_SHO_204_LONG_MM_SETTLEMENT_DAYS", 4)
    monkeypatch.setattr(RUNS, "REG_SHO_144_SETTLEMENT_DAYS", 40)
    t = _items(world())["GMEX"]["title"]
    for text in (t, RS.rules_pick()):
        assert "closed out 1 to 4 settlement days" in text and "the count is 40, not 13" in text
        assert "1 to 3 settlement" not in text and "is 35" not in text


# ═════════════════════════════════════════════ load_history / history_todo
def test_load_history_reads_nothing_when_no_list_is_held():
    class NoFind(StandIn):
        def find(self, flt):
            raise AssertionError("no read expected: %s" % flt)
    coll = NoFind()
    loaded = RS.load(StandIn())
    assert RS.load_history(coll, loaded) == {"days": {}, "members": {}, "docs": {}, "holes": {}}
    assert RS.load_history(None, loaded)["days"] == {}


def test_load_history_window_and_members():
    coll = world()
    h = RS.load_history(coll, RS.load(coll))
    assert list(h["days"]) == ["nasdaq"] and len(h["days"]["nasdaq"]) == RS.RS_HIST_SETTLEMENT_DAYS
    m = h["members"]["nasdaq"]
    assert m["2026-11-20"] == frozenset(["AKAN", "GMEX", "SMTK"])
    assert m["2026-10-09"] is None and m["2026-10-08"] is None
    assert "2026-11-11" not in m                                               # never a window day


def test_NEGATIVE_an_unconfirmed_zero_row_history_list_is_not_read():
    coll = world()
    zero_row(coll, "nasdaq", D("2026-11-06"), minutes_ago=5)
    h = RS.load_history(coll, RS.load(coll))
    assert h["members"]["nasdaq"]["2026-11-06"] is None
    assert RUNS.run_for("GMEX", h["days"]["nasdaq"], h["members"]["nasdaq"])["state"] == "unknown"


def test_NEGATIVE_history_todo_never_builds_a_bank_holiday_or_closed_day_url(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 40)
    coll = StandIn()
    seed_list(coll, "nasdaq", D("2026-11-30"), ["ZNAS"])
    for mkt, _n in RS.NYSE_MARKETS:
        seed_list(coll, mkt, D("2026-11-30"), ["ZNYS"])
    seed_list(coll, "cboe_bzx", D("2026-11-30"), ["ZCBO"])
    todo = todo_now(coll, datetime(2026, 12, 1, 10, 0, tzinfo=ET))
    ds = {it[2] for it in todo if it[0] == "fetch"}
    assert D("2026-10-13") in ds and D("2026-11-27") in ds
    for bad in (D("2026-10-12"), D("2026-11-11"), D("2026-11-26")):
        assert bad not in ds
    urls = [RS.source_url(it[1], m, it[2]) for it in todo if it[0] == "fetch"
            for m, _e, _f in RS.source_markets(it[1])]
    for frag in ("20261012", "20261111", "20261126", "2026-10-12", "2026-11-11", "2026-11-26"):
        assert not [u for u in urls if frag in u], frag


def test_ordering_newest_first_registry_order_and_reasks_last(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 3)
    coll = StandIn()
    seed_all_newest(coll)
    todo = todo_now(coll)
    assert [(it[0], it[1]["key"], it[2].isoformat()) for it in todo] == [
        ("fetch", "nasdaq", "2026-11-19"), ("fetch", "nyse", "2026-11-19"),
        ("fetch", "nasdaq", "2026-11-18"), ("fetch", "nyse", "2026-11-18"), ("fetch", "cboe_bzx", "2026-11-18"),
        ("fetch", "cboe_bzx", "2026-11-17")]
    hole(coll, "fetch", "nasdaq", D("2026-11-19"), minutes_ago=RS.RS_RETRY_MIN + 1)     # a due re-ask
    for mkt, _n in RS.NYSE_MARKETS:
        seed_list(coll, mkt, D("2026-11-19"), ["Z"] if mkt != "nyse" else [], confirmed=(mkt != "nyse"),
                  fetched_at=utc(NOW - timedelta(minutes=RS.RS_RETRY_MIN + 1)))
    todo = todo_now(coll)
    keys = [(it[0], it[1]["key"], it[-1].isoformat()) for it in todo]
    assert keys[-1] == ("fetch", "nasdaq", "2026-11-19")                          # the re-ask sorts after all
    assert ("confirm", "nyse", "2026-11-19") in keys
    assert keys.index(("confirm", "nyse", "2026-11-19")) < keys.index(("fetch", "nasdaq", "2026-11-19"))
    fetch_idx = [i for i, k in enumerate(keys[:-1]) if k[0] == "fetch"]
    conf_idx = [i for i, k in enumerate(keys[:-1]) if k[0] == "confirm"]
    assert max(fetch_idx) < min(conf_idx)                                         # fetches before confirms


# ═════════════════════════════════════════════ backfill
def _pinned_urls(dates):
    return {RS.source_url(s, m, d) for d in dates for s, m, _e, _f in RS.all_markets()}


def test_backfill_writes_backfilled_docs_in_order_with_the_house_call_shape(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 3)
    coll = seed_all_newest(StandIn())
    events = []
    monkeypatch.setattr(RS, "_pause", lambda s: events.append(("pause", s)))
    http = FakeHTTP(full_answers(days_1120(4)), on_call=lambda u: events.append(("call", u)))
    out = RS.backfill_history(coll, NOW, http=http)
    assert set(out) == {"calls", "found", "confirmed", "holes", "seconds"}
    assert out["calls"] == 1 + 3 + 1 + 3 + 1 + 1 and out["found"] == 6 and out["holes"] == 0
    assert http.urls[:5] == [nasdaq_url(D("2026-11-19"))] + [nyse_url(m, D("2026-11-19")) for m, _n in
                                                               RS.NYSE_MARKETS] + [nasdaq_url(D("2026-11-18"))]
    assert set(http.urls) <= _pinned_urls(days_1120(4)) and http.unexpected == []
    for kw in http.kwargs:
        assert kw["headers"] == RS.HTTP_HEADERS and kw["timeout"] == RS.RS_HTTP_TIMEOUT_SEC
        assert kw["allow_redirects"] is False
    assert coll.docs["list|nasdaq|2026-11-19"]["backfilled"] is True
    assert coll.docs["list|nyse_arca|2026-11-18"]["backfilled"] is True
    assert "backfilled" not in coll.docs["list|nasdaq|2026-11-20"]
    assert events[0][0] == "call" and events[-1][0] == "call"                     # pauses only BETWEEN items
    assert [e for e in events if e[0] == "pause"] == [("pause", RS.RS_HIST_PAUSE_SEC)] * 5
    assert todo_now(coll) == []


def test_backfill_starts_no_item_past_the_get_cap(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_MAX_GETS", 2)
    coll = seed_all_newest(StandIn())
    http = FakeHTTP(full_answers(days_1120(31)))
    out = RS.backfill_history(coll, NOW, http=http)
    assert out["calls"] == 4 and out["calls"] <= RS.RS_HIST_MAX_GETS + 2           # nasdaq, then one NYSE group
    monkeypatch.setattr(RS, "RS_HIST_MAX_GETS", 40)
    out = RS.backfill_history(coll, NOW, http=FakeHTTP(full_answers(days_1120(31))))
    assert RS.RS_HIST_MAX_GETS <= out["calls"] <= RS.RS_HIST_MAX_GETS + 2


def test_backfill_honours_the_deadline(monkeypatch):
    clock = {"t": 0.0}
    monkeypatch.setattr(RS, "_mono", lambda: clock["t"])

    def tick(url):
        clock["t"] += 20.0
    coll = seed_all_newest(StandIn())
    http = FakeHTTP(full_answers(days_1120(31)), on_call=tick)
    out = RS.backfill_history(coll, NOW, http=http)
    assert out["calls"] == 4 and clock["t"] > RS.RS_HIST_BUDGET_SEC


def test_a_missing_answer_writes_a_missing_hole_and_keeps_the_source(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 3)
    coll = StandIn()
    seed_list(coll, "nasdaq", D("2026-11-20"), ["ZNAS"])
    ans = full_answers([D("2026-11-18")])
    ans[nasdaq_url(D("2026-11-19"))] = NASDAQ_302
    out = RS.backfill_history(coll, NOW, http=FakeHTTP(ans))
    h = coll.docs["nolist|nasdaq|2026-11-19"]
    assert (h["kind"], h["op"], h["result"], h["tries"], h["market"]) == ("nolist", "fetch", "missing", 1, None)
    assert h["asked_at"] == utc(NOW) and h["source"] == "nasdaq"
    assert "list|nasdaq|2026-11-18" in coll.docs and out["holes"] == 1 and out["found"] == 1
    assert todo_now(coll) == []                                                   # a missing waits a day


def test_NEGATIVE_backfill_never_overwrites_a_held_doc(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 2)
    coll = seed_all_newest(StandIn())
    seed_window(coll, 2)
    held = seed_list(coll, "nyse_arca", D("2026-11-19"), ["SEEDED"],
                     fetched_at=utc(NOW - timedelta(days=2)))
    del coll.docs["list|nyse|2026-11-19"]
    del coll.docs["list|nyse_american|2026-11-19"]
    RS.backfill_history(coll, NOW, http=FakeHTTP(full_answers([D("2026-11-19")])))
    arca = coll.docs["list|nyse_arca|2026-11-19"]
    assert arca == held and "backfilled" not in arca and arca["symbols"] == ["SEEDED"]
    assert coll.docs["list|nyse|2026-11-19"]["backfilled"] is True


def test_confirm_a_zero_row_history_list_with_one_call_then_it_ends_a_run(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 2)
    coll = seed_all_newest(StandIn())
    seed_window(coll, 2)
    del coll.docs["list|nyse|2026-11-19"]
    zero_row(coll, "nyse", D("2026-11-19"), minutes_ago=RS.RS_RETRY_MIN + 1)
    h = RS.load_history(coll, RS.load(coll))
    assert RUNS.run_for("ZNYS", h["days"]["nyse"], h["members"]["nyse"])["state"] == "unknown"
    assert [it[0] for it in todo_now(coll)] == ["confirm"]
    http = FakeHTTP({nyse_url("nyse", D("2026-11-19")): Resp(200, synthetic_nyse(D("2026-11-19"), []))})
    out = RS.backfill_history(coll, NOW, http=http)
    assert http.urls == [nyse_url("nyse", D("2026-11-19"))] and out["confirmed"] == 1 and out["calls"] == 1
    assert coll.docs["list|nyse|2026-11-19"]["confirmed_at"] == utc(NOW)
    h = RS.load_history(coll, RS.load(coll))
    assert h["members"]["nyse"]["2026-11-19"] == frozenset()
    r = RUNS.run_for("ZNYS", h["days"]["nyse"], h["members"]["nyse"])
    assert r["state"] == "counting" and r["days"] == 1


def test_NEGATIVE_a_young_zero_row_history_list_is_not_confirmed_yet(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 2)
    coll = seed_all_newest(StandIn())
    seed_window(coll, 2)
    del coll.docs["list|nyse|2026-11-19"]
    zero_row(coll, "nyse", D("2026-11-19"), minutes_ago=RS.RS_RETRY_MIN - 1)
    assert todo_now(coll) == []


def test_NEGATIVE_a_fetch_error_skips_the_source_for_the_round_and_cools_it(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 4)
    coll = StandIn()
    seed_list(coll, "nasdaq", D("2026-11-20"), ["ZNAS"])
    ans = full_answers(days_1120(4))
    ans[nasdaq_url(D("2026-11-19"))] = Resp(500, "synthetic")
    http = FakeHTTP(ans)
    out = RS.backfill_history(coll, NOW, http=http)
    assert http.urls == [nasdaq_url(D("2026-11-19"))] and out["calls"] == 1 and out["holes"] == 1
    h = coll.docs["nolist|nasdaq|2026-11-19"]
    assert h["result"] == "error" and h["error"] == "http_500" and h["tries"] == 1
    assert todo_now(coll) == []
    assert todo_now(coll, NOW + timedelta(minutes=RS.RS_RETRY_MIN - 1)) == []
    later = todo_now(coll, NOW + timedelta(minutes=RS.RS_RETRY_MIN))
    assert later and all(it[1]["key"] == "nasdaq" for it in later)


def test_NEGATIVE_an_error_hole_is_never_final(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 2)
    coll = StandIn()
    seed_list(coll, "nasdaq", D("2026-11-20"), ["ZNAS"])
    t0 = NOW - timedelta(minutes=RS.RS_HIST_REASK_MIN)
    hole(coll, "fetch", "nasdaq", D("2026-11-19"), tries=RS.RS_HIST_MAX_TRIES, now=t0)
    assert todo_now(coll, NOW - timedelta(minutes=1)) == []                       # REASK - 1 minutes old
    assert [it[0] for it in todo_now(coll, NOW)] == ["fetch"]                     # REASK minutes old
    http = FakeHTTP({nasdaq_url(D("2026-11-19")): ReadTimeout("synthetic")})
    out = RS.backfill_history(coll, NOW, http=http)
    assert out["calls"] == 1 and http.urls == [nasdaq_url(D("2026-11-19"))]
    h = coll.docs["nolist|nasdaq|2026-11-19"]
    assert h["tries"] == RS.RS_HIST_MAX_TRIES + 1 and h["asked_at"] == utc(NOW) and h["error"] == "timeout"
    assert todo_now(coll, NOW + timedelta(minutes=1)) == []
    assert RS._hole_due(h, NOW + timedelta(minutes=RS.RS_HIST_REASK_MIN)) is True


def test_NEGATIVE_a_missing_hole_past_the_tries_is_final():
    h = {"result": "missing", "tries": RS.RS_HIST_MAX_TRIES, "asked_at": utc(NOW - timedelta(days=30))}
    assert RS._hole_due(h, NOW) is False
    h["tries"] = RS.RS_HIST_MAX_TRIES - 1
    assert RS._hole_due(h, NOW) is True
    h["asked_at"] = utc(NOW - timedelta(minutes=RS.RS_HIST_REASK_MIN - 1))
    assert RS._hole_due(h, NOW) is False


def test_hole_due_reads_odd_fields_without_raising():
    assert RS._hole_due(None, NOW) is True
    assert RS._hole_due({"result": "error", "tries": 1, "asked_at": "garbage"}, NOW) is True
    h = {"result": "error", "tries": "x", "asked_at": utc(NOW - timedelta(minutes=RS.RS_RETRY_MIN))}
    assert RS._hole_due(h, NOW) is True                                           # "x" reads as 0 tries


def _failing_confirm_world(n_zero=1):
    coll = seed_all_newest(StandIn())
    seed_window(coll, n_zero + 1)
    ds = days_1120(n_zero + 1)[1:]
    for d in ds:
        del coll.docs["list|nyse|%s" % d.isoformat()]
        zero_row(coll, "nyse", d, minutes_ago=RS.RS_RETRY_MIN + 1)
    return coll, ds


def test_NEGATIVE_a_failing_confirm_writes_a_hole_and_leaves_the_todo(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 2)
    coll, (d,) = _failing_confirm_world(1)
    http = FakeHTTP({nyse_url("nyse", d): Resp(403, "<html>SYNTHETIC block</html>")})
    out = RS.backfill_history(coll, NOW, http=http)
    h = coll.docs["nolist|confirm|nyse|%s" % d.isoformat()]
    assert (h["op"], h["market"], h["result"], h["tries"], h["error"]) == ("confirm", "nyse", "error", 1, "http_403")
    assert out["calls"] == 1 and out["holes"] == 1 and out["confirmed"] == 0
    assert todo_now(coll) == []
    p = RS.payload(FakeDB(coll), NOW, kick=True, http=FakeHTTP())
    assert p["refreshing"] is False and RS._bg["thread"] is None
    assert p["closeout"]["history"]["pending"] is False


def test_NEGATIVE_a_timeout_on_confirm_is_a_hole_too(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 2)
    coll, (d,) = _failing_confirm_world(1)
    RS.backfill_history(coll, NOW, http=FakeHTTP({nyse_url("nyse", d): ReadTimeout("synthetic")}))
    assert coll.docs["nolist|confirm|nyse|%s" % d.isoformat()]["error"] == "timeout"


def test_NEGATIVE_three_failing_confirms_of_one_source_make_one_call(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 4)
    coll, ds = _failing_confirm_world(3)
    assert [it[0] for it in todo_now(coll)] == ["confirm"] * 3
    http = FakeHTTP({nyse_url("nyse", d): Resp(403, "x") for d in ds})
    out = RS.backfill_history(coll, NOW, http=http)
    assert out["calls"] == 1 and len(http.urls) == 1


def test_NEGATIVE_a_fresh_confirm_error_blocks_the_sources_fetches_too(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 3)
    coll = seed_all_newest(StandIn())
    seed_window(coll, 3)
    for mkt, _n in RS.NYSE_MARKETS:
        del coll.docs["list|%s|2026-11-18" % mkt]                                 # a NYSE fetch would be due
    assert [it[1]["key"] for it in todo_now(coll)] == ["nyse"]
    hole(coll, "confirm", "nyse", D("2026-11-19"), mkt="nyse", minutes_ago=1)
    assert todo_now(coll) == []


def test_NEGATIVE_the_write_failure_breaker(monkeypatch):
    clock = {"t": 5000.0}
    monkeypatch.setattr(RS, "_mono", lambda: clock["t"])
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 3)

    class BrokenWrites(StandIn):
        def replace_one(self, flt, doc, upsert=False):
            if doc.get("kind") in ("list", "nolist"):
                raise RuntimeError("synthetic: Mongo write refused")
            return StandIn.replace_one(self, flt, doc, upsert)
    coll = BrokenWrites()
    seed_window(seed_all_newest(coll), 3)
    del coll.docs["list|nasdaq|2026-11-19"]
    del coll.docs["list|nasdaq|2026-11-18"]
    http = FakeHTTP(full_answers(days_1120(3)))
    out = RS.backfill_history(coll, NOW, http=http)
    assert out["calls"] == 1 and out["found"] == 0                               # ONE item, not RS_HIST_MAX_GETS
    assert RS._hist["blocked_until"] == clock["t"] + RS.RS_RETRY_MIN * 60
    assert RS.backfill_history(coll, NOW, http=http)["calls"] == 0 and len(http.urls) == 1
    p = RS.payload(FakeDB(coll), NOW, kick=True, http=FakeHTTP())
    assert p["refreshing"] is False and RS._bg["thread"] is None
    assert p["closeout"]["ok"] is True and p["closeout"]["history"]["pending"] is False
    clock["t"] += RS.RS_RETRY_MIN * 60 - 1
    assert RS.backfill_history(coll, NOW, http=http)["calls"] == 0
    clock["t"] += 1
    loaded = RS.load(coll)
    assert RS._history_view(coll, loaded, NOW)[1] != []                           # the history is back


def test_a_failing_hole_write_trips_the_breaker_too(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 3)

    class BrokenHoles(StandIn):
        def replace_one(self, flt, doc, upsert=False):
            if doc.get("kind") == "nolist":
                raise RuntimeError("synthetic")
            return StandIn.replace_one(self, flt, doc, upsert)
    coll = BrokenHoles()
    seed_list(coll, "nasdaq", D("2026-11-20"), ["ZNAS"])
    out = RS.backfill_history(coll, NOW, http=FakeHTTP({nasdaq_url(D("2026-11-19")): NASDAQ_302}))
    assert out["calls"] == 1 and RS._hist["blocked_until"] is not None


# ═════════════════════════════════════════════ the worker
def test_worker_runs_refresh_due_then_backfill_in_one_thread(monkeypatch):
    seen = []
    monkeypatch.setattr(RS, "refresh_due", lambda coll, now_et=None, http=None:
                        seen.append(("refresh", threading.get_ident())))
    monkeypatch.setattr(RS, "backfill_history", lambda coll, now_et=None, http=None:
                        seen.append(("backfill", threading.get_ident())))
    assert RS.kick_refresh(StandIn(), NOW, http=FakeHTTP()) is True
    RS._bg["thread"].join(5)
    assert [s[0] for s in seen] == ["refresh", "backfill"] and seen[0][1] == seen[1][1]
    assert RS._bg["running"] is False


def test_a_raising_refresh_due_does_not_skip_the_backfill(monkeypatch):
    seen = []

    def boom(coll, now_et=None, http=None):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(RS, "refresh_due", boom)
    monkeypatch.setattr(RS, "backfill_history", lambda coll, now_et=None, http=None: seen.append(1))
    assert RS.kick_refresh(StandIn(), NOW, http=FakeHTTP()) is True
    RS._bg["thread"].join(5)
    assert seen == [1] and RS._bg["running"] is False


def test_NEGATIVE_refresh_due_does_not_call_the_backfill(monkeypatch):
    seen = []
    monkeypatch.setattr(RS, "backfill_history", lambda *a, **k: seen.append(1))
    coll, http, ran = golden_round()
    assert ran["calls"] == 5 and len(http.urls) == 5 and seen == []


# ═════════════════════════════════════════════ refreshing — the loop is closed [C2]
def test_NEGATIVE_kick_false_with_a_todo_makes_no_call_and_starts_no_thread():
    coll = world()
    assert todo_now(coll)                                                         # 10-09 / 10-08 not read
    http = FakeHTTP()
    p = RS.payload(FakeDB(coll), NOW, kick=False, http=http)
    assert http.urls == [] and RS._bg["thread"] is None and p["refreshing"] is False
    assert p["closeout"]["history"]["pending"] is True


def test_NEGATIVE_every_hole_final_or_waiting_serves_refreshing_false(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 3)
    coll = seed_window(seed_all_newest(StandIn()), 3)
    del coll.docs["list|nasdaq|2026-11-19"]
    del coll.docs["list|nasdaq|2026-11-18"]
    hole(coll, "fetch", "nasdaq", D("2026-11-19"), result="missing", tries=RS.RS_HIST_MAX_TRIES, minutes_ago=99999)
    hole(coll, "fetch", "nasdaq", D("2026-11-18"), result="missing", tries=1, minutes_ago=10)
    p = RS.payload(FakeDB(coll), NOW, kick=True, http=FakeHTTP())
    assert p["refreshing"] is False and p["retry_after_sec"] is None and RS._bg["thread"] is None


def test_NEGATIVE_a_thread_that_cannot_start_serves_refreshing_false(monkeypatch):
    class NoThread:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("can't start new thread")
    monkeypatch.setattr(RS.threading, "Thread", NoThread)
    coll = seed_all_newest(world())
    assert todo_now(coll)
    p = RS.payload(FakeDB(coll), NOW, kick=True, http=FakeHTTP())
    assert p["refreshing"] is False and p["retry_after_sec"] is None


def test_a_floor_refused_kick_with_a_todo_serves_refreshing_with_the_kick_floor(monkeypatch):
    clock = {"t": 9000.0}
    monkeypatch.setattr(RS, "_mono", lambda: clock["t"])
    coll = seed_all_newest(world())
    del coll.docs["list|nyse_american|2026-11-20"]                                # one market holds no list: a red fault line
    assert todo_now(coll)
    base = RS.payload(FakeDB(coll), NOW, kick=False)
    assert base["fault_text"] is not None and "NYSE American" in base["fault_text"]
    RS._bg["last_start"] = clock["t"] - 10
    p = RS.payload(FakeDB(coll), NOW, kick=True, http=FakeHTTP())
    assert RS._bg["thread"] is None
    assert p["refreshing"] is True and p["retry_after_sec"] == RS.RS_KICK_MIN_SEC
    assert p["fault_text"] is not None and p["fault_text"] == base["fault_text"]  # the history never hides the fault line
    assert p["sources"] == base["sources"]


def test_a_kick_that_starts_the_history_worker_serves_refreshing(monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(RS, "refresh_due", lambda coll, now_et=None, http=None: None)
    monkeypatch.setattr(RS, "backfill_history", lambda coll, now_et=None, http=None: gate.wait(5))
    coll = seed_all_newest(world())
    try:
        p = RS.payload(FakeDB(coll), NOW, kick=True, http=FakeHTTP())
        assert p["refreshing"] is True and RS._bg["thread"] is not None
    finally:
        gate.set()
        RS._bg["thread"].join(5)


# ═════════════════════════════════════════════ [C4] the history path cannot take the tag down
def _golden_parts(p):
    return p["fault_text"], p["sources"], p.get("check")


def test_NEGATIVE_load_history_raising_keeps_akan_served(monkeypatch):
    coll, _h, _ = golden_round()
    good = RS.payload(FakeDB(coll), NOW, kick=False, check=["AKAN", "ZZZZ"])

    def boom(*a, **k):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(RS, "load_history", boom)
    p = RS.payload(FakeDB(coll), NOW, kick=False, check=["AKAN", "ZZZZ"])
    a = p["items"]["AKAN"]
    assert all(a[k] for k in ("chip", "short", "label", "title"))
    assert a["chip"].endswith("· day count unknown") and a["short"] == "🔒 Hard to borrow · 11/20"
    assert a["run"]["state"] == "unknown"
    assert _golden_parts(p) == _golden_parts(good)
    assert p["closeout"]["ok"] is False and p["closeout"]["history"] is None


def test_NEGATIVE_run_for_raising_keeps_akan_served(monkeypatch):
    coll, _h, _ = golden_round()
    good = RS.payload(FakeDB(coll), NOW, kick=False, check=["AKAN"])

    def boom(*a, **k):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(RUNS, "run_for", boom)
    p = RS.payload(FakeDB(coll), NOW, kick=False, check=["AKAN"])
    a = p["items"]["AKAN"]
    assert all(a[k] for k in ("chip", "short", "label", "title"))
    assert a["chip"].endswith("· day count unknown") and _golden_parts(p) == _golden_parts(good)


def test_NEGATIVE_a_malformed_run_block_reads_unknown_in_tag_block():
    bad = dict(RUNS.unknown_block(), state="counting", days=4)                     # no dates
    t = RS.tag_block("AKAN", "nasdaq", "Nasdaq", "2026-11-20", False, run=bad)
    assert t["chip"].endswith(RS.RUN_UNKNOWN) and t["short"] == "🔒 Hard to borrow · 11/20"


def test_NEGATIVE_a_window_doc_with_null_symbols_reads_not_read():
    coll = world()
    coll.docs["list|nasdaq|2026-11-19"]["symbols"] = None
    p = RS.payload(FakeDB(coll), NOW, kick=False)
    g = p["items"]["GMEX"]["run"]
    assert g["state"] == "unknown" and g["missing"] == "2026-11-19"
    coll.docs["list|nasdaq|2026-11-19"].update({"symbols": ["GMEX"], "n": "x", "confirmed_at": None})
    p = RS.payload(FakeDB(coll), NOW, kick=False)
    assert p["items"]["GMEX"]["run"]["missing"] == "2026-11-19"


def test_NEGATIVE_a_hole_doc_with_odd_tries_raises_nothing(monkeypatch):
    monkeypatch.setattr(RS, "RS_HIST_SETTLEMENT_DAYS", 2)
    coll = StandIn()
    seed_list(coll, "nasdaq", D("2026-11-20"), ["ZNAS"])
    h = hole(coll, "fetch", "nasdaq", D("2026-11-19"), tries="x", minutes_ago=RS.RS_RETRY_MIN)
    p = RS.payload(FakeDB(coll), NOW, kick=False)
    assert p["closeout"]["ok"] is True and p["closeout"]["history"]["pending"] is True
    RS.backfill_history(coll, NOW, http=FakeHTTP({nasdaq_url(D("2026-11-19")): NASDAQ_302}))
    assert coll.docs[h["_id"]]["tries"] == 1


def test_NEGATIVE_through_the_route_a_raising_history_still_serves_items(monkeypatch):
    from tests.test_reg_sho_threshold_2026_11_22 import _route_client
    coll, _h, _ = golden_round()
    monkeypatch.setattr(SIC, "_get_db", lambda: FakeDB(coll))
    monkeypatch.setattr(RS, "kick_refresh", lambda *a, **k: False)

    def boom(*a, **k):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(RS, "load_history", boom)
    j = _route_client().get("/short-interest/reg-sho?check=AKAN").json()
    assert j != RS.fault_payload() and j["items"]["AKAN"]["chip"].endswith("· day count unknown")
    assert j["closeout"]["ok"] is False


def test_fault_payload_carries_closeout_none_and_the_route_still_serves_it(monkeypatch):
    from tests.test_reg_sho_threshold_2026_11_22 import _route_client
    assert RS.fault_payload()["closeout"] is None

    def boom(*a, **k):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(RS, "payload", boom)
    j = _route_client().get("/short-interest/reg-sho").json()
    assert j == RS.fault_payload() and j["closeout"] is None


def test_tag_block_called_the_old_way_still_serves_four_strings():
    t = RS.tag_block("AKAN", "nasdaq", "Nasdaq", "2026-11-20", True)
    assert all(t[k] for k in ("chip", "short", "label", "title"))
    assert t["chip"].endswith(RS.RUN_UNKNOWN + RS.STALE_WORD)


# ═════════════════════════════════════════════ payload keys
def test_closeout_keys_and_the_golden_world():
    p = build_golden_payload()
    c = p["closeout"]
    assert c["rule"] == "SEC Regulation SHO Rule 203(b)(3)" and c["rule_days"] == 13 and c["first_buy_day"] == 11
    assert c["ok"] is True and set(c) == {"rule", "rule_days", "first_buy_day", "ok", "history"}
    h = c["history"]
    assert set(h) == {"window_days", "read", "not_read", "pending"} and h["window_days"] == RS.RS_HIST_SETTLEMENT_DAYS
    assert h["read"] == {"nasdaq": 2, "nyse": 2, "nyse_american": 2, "nyse_arca": 2, "cboe_bzx": 1}
    assert h["not_read"]["nasdaq"][0] == "2026-11-18" and len(h["not_read"]["nasdaq"]) == RS.RS_HIST_NOT_READ_MAX
    assert h["pending"] is False and p["refreshing"] is False
    assert p["items"]["AKAN"]["run"]["state"] == "counting" and p["items"]["AKAN"]["run"]["days"] == 1
    smtk_like = [it for it in p["items"].values() if it["run"]["state"] == "unknown"]
    assert smtk_like and all(it["run"]["missing"] in ("2026-11-18", None) for it in smtk_like)


def test_the_golden_round_makes_seven_calls_and_none_for_veterans_day():
    coll, _h, _ = golden_round()
    http = FakeHTTP(fixture_answers())
    out = RS.backfill_history(coll, NOW, http=http)
    assert out["calls"] == 7 and out["found"] == 2 and out["holes"] == 3
    assert not [u for u in http.urls if "20261111" in u or "2026-11-11" in u]
    assert {k for k in coll.docs if k.startswith("nolist|")} == {
        "nolist|nasdaq|2026-11-18", "nolist|nyse|2026-11-18", "nolist|cboe_bzx|2026-11-18"}


def test_NEGATIVE_no_survivorship_sentence_and_no_count_keys():
    p = build_golden_payload()
    for k in ("text", "past_n", "counted_n"):
        assert k not in p["closeout"]
    for t in strings_of(p) + [RS.rules_pick()]:
        assert not re.search(r"names are past day", t), t


# ═════════════════════════════════════════════ every state: JSON-safe, bounded, clean words
def _state_payloads():
    out = []
    for coll, now in ((world(), NOW), (world(skip=("2026-11-18",)), NOW), (world(skip=("2026-10-28",)), NOW),
                      (_zzzt_world(30), NOW), (_zzzt_world(13), NOW)):
        out.append(RS.payload(FakeDB(coll), now, kick=False, check=["GMEX"]))
    out.append(_stale(world()))
    out.append(_stale(_zzzt_world(30)))
    out.append(_stale(_zzzt_world(13)))
    out.append(_stale(world(skip=("2026-10-28",))))
    out.append(_stale(world(skip=("2026-11-18",))))
    out.append(build_golden_payload())
    out.append(RS.fault_payload())
    return out


def test_every_state_payload_is_json_safe_typed_and_bounded():
    states = set()
    for p in _state_payloads():
        json.dumps(p, allow_nan=False)

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
        for it in p["items"].values():
            states.add(it["run"]["state"])
            assert len(it["title"]) <= TITLE_MAX, (len(it["title"]), it["symbol"])
    assert states == {"counting", "reached", "passed", "passed_open", "unknown"}


def test_NEGATIVE_words_carry_neither_banned_list():
    texts = [RS.rules_pick()]
    for p in _state_payloads():
        texts += strings_of(p)
    assert len(texts) > 60
    for t in texts:
        assert not FORBIDDEN.search(t), t
        assert not FORBIDDEN_NEW.search(t), t
    assert FORBIDDEN_NEW.search("Day 13 is the earliest day a clearing firm must close out")
    assert FORBIDDEN_NEW.search("A rule date, not a forecast.")


def test_NEGATIVE_reg_sho_source_types_no_bare_rule_number_and_no_banned_word():
    src = (BACKEND / "short_interest" / "reg_sho.py").read_text()
    code = "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())
    assert not re.search(r"\b13\b", code)
    assert not re.search(r"earliest|forecast|buy-in", src, re.I)


# ═════════════════════════════════════════════ ℹ️ pick
def test_the_pick_names_the_rules_and_the_bank_holidays():
    pk = RS.rules_pick()
    assert pk.startswith("🔒 Hard to borrow (the tag's name) = ")
    for w in ("Rule 203(b)(3)", "Rule 204", "Rule 144", "Columbus Day", "Veterans Day", "Rule 203(c)(5)",
              "dates day 13", "from day 11"):
        assert w in pk, w
    assert pk.endswith(RS.NOT_A_PRICE_READ)


def test_the_pick_moves_with_the_rule_days(monkeypatch):
    monkeypatch.setattr(RUNS, "REG_SHO_CLOSEOUT_SETTLEMENT_DAYS", 12)
    pk = RS.rules_pick()
    assert "dates day 12" in pk and "from day 10)" in pk and "dates day 13" not in pk


# ═════════════════════════════════════════════ display only
# WIDENED 2026-11-24 (main session): the 🩳 High SI sub (main 2026-11-23) prints the SAME 🔒 tag on its cards and in its
# push text — a display read with payload(kick=False). Those two files are the ONLY allowed readers; they never kick the
# worker and never gate on it (they never import reg_sho_runs).
# WIDENED 2026-11-24 (SPEC sissr §3.3, WP be-pass — Ajay "Days past little bit like AKAN is what I am mainly looking for"):
# si_ssr_names.py reads the SAME payload(kick=False) to TAG names past their close-out date (a source of names GG's
# rules read, HIS CALL #0) — it never kicks the worker, never reads the run engine and never gates on it.
DISPLAY_READERS = {"chart_maps/gajjala/high_si.py", "chart_maps/gajjala/high_si_cross.py",
                   "chart_maps/gajjala/si_ssr_names.py"}


def test_NEGATIVE_display_only_nothing_in_the_trading_paths_reads_it():
    hits, readers = [], []
    for sub in ("chart_maps", "push", "trading"):
        for f in (BACKEND / sub).rglob("*.py"):
            txt = f.read_text(errors="ignore")
            if "reg_sho" in txt or "reg_sho_runs" in txt:
                rel = f.relative_to(BACKEND).as_posix()
                (readers if rel in DISPLAY_READERS else hits).append(rel)
    assert hits == []
    for rel in readers:
        txt = (BACKEND / rel).read_text(errors="ignore")
        assert "reg_sho_runs" not in txt and "kick_refresh" not in txt and "backfill_history" not in txt
        assert "payload(kick=False" in txt
    assert "reg_sho" not in (BACKEND / "crontab").read_text()
