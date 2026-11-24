"""⛔ SSR — SEC Rule 201 short-sale restriction: the rule, the computed read, the served read (W1 ssr-core).

Ajay 2026-11-23: "No shorting at the bid (SEC short-sale restriction) Can we check or this for other stocks too?"
Spec: scratchpad ssr/spec.md §3.1, §3.2, §3.5–§3.8, W1. Every name below is SYNTHETIC unless a comment cites the
measured number (§1.3: AKAN prev 4.23 / 09:30 minute; GP prev 2.81 / 13:43 minute low 2.50; PXED prev 19.66 /
snapshot day low 17.39 + a 2.36 dividend ex 11/23; TOPP split 11/23; GP and GIPR on Nasdaq's 11/20 file).
The lists / corp sides are FAKES with the FROZEN interfaces (spec §3.3 / §3.4a)."""
from __future__ import annotations

import ast
import copy
import inspect
import json
import math
import re
import sys
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from short_interest import api as SAPI
from short_interest import read as SR
from short_interest import reg_sho as RS
from short_interest import ssr as SSR

ET = ZoneInfo("America/New_York")
FIXTURE = Path(__file__).parent / "fixtures" / "ssr_payload_2026_11_24.json"
SRC = Path(SSR.__file__).read_text()
FORBIDDEN = re.compile(r"bounce|predict|will (fall|drop)|fake", re.I)

D20, D23, D24, D25, D27 = date(2026, 11, 20), date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 27)


def et(d: date, h: int, m: int, s: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, s, tzinfo=ET)


def ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def ns(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000_000_000)


def utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def snap(low, prev, *, stamp=None, last=None, close=None, high=None, open_=None):
    """A `prices._snapshot_row`-shaped row. `stamp` = the minute stamp (ms); `last` = the last-trade stamp."""
    c = close if close is not None else low
    top = max(low, prev) if isinstance(prev, (int, float)) and prev == prev else low
    return {"open": open_ if open_ is not None else top, "high": high if high is not None else top,
            "low": low, "close": c, "volume": 1000, "prev_day_close": prev,
            "min_t_ms": stamp, "last_trade_ts_ms": last}


def minutes(session: date, items, session_col=None) -> pd.DataFrame:
    """1-minute bars, `Frames.raw`-shaped: UTC-naive minute-START index. items = [(hh, mm, low)]."""
    idx, rows = [], []
    for hh, mm, lo in items:
        t = et(session, hh, mm).astimezone(timezone.utc).replace(tzinfo=None)
        idx.append(pd.Timestamp(t))
        r = {"open": lo + 0.05, "high": lo + 0.1, "low": lo, "close": lo + 0.02, "volume": 100}
        if session_col is not None:
            r["session"] = session_col
        rows.append(r)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


def fr(raw):
    return types.SimpleNamespace(raw=raw)


# ═════════════════════════════════════════════ fakes
class FakeColl:
    """find / find_one / update_one ($set dotted, $unset, $setOnInsert) / insert_many / create_index."""

    def __init__(self, docs=None):
        self.docs = {d["_id"]: copy.deepcopy(d) for d in (docs or [])}
        self.raise_all = False
        self.writes = []

    def _chk(self):
        if self.raise_all:
            raise RuntimeError("synthetic: the store fails")

    @staticmethod
    def _match(doc, flt):
        for k, v in flt.items():
            if isinstance(v, dict) and "$in" in v:
                if doc.get(k) not in v["$in"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def find(self, flt=None, *a, **k):
        self._chk()
        return [copy.deepcopy(d) for d in self.docs.values() if self._match(d, flt or {})]

    def find_one(self, flt, *a, **k):
        self._chk()
        for d in self.docs.values():
            if self._match(d, flt):
                return copy.deepcopy(d)
        return None

    def update_one(self, flt, upd, upsert=False):
        self._chk()
        assert set(flt) == {"_id"}, flt
        _id = flt["_id"]
        doc = self.docs.get(_id)
        inserted = doc is None
        if inserted:
            if not upsert:
                return
            doc = {"_id": _id}
        for k, v in (upd.get("$set") or {}).items():
            if "." in k:
                a, b = k.split(".", 1)
                doc.setdefault(a, {})[b] = copy.deepcopy(v)
            else:
                doc[k] = copy.deepcopy(v)
        for k in (upd.get("$unset") or {}):
            doc.pop(k, None)
        if inserted:
            for k, v in (upd.get("$setOnInsert") or {}).items():
                doc[k] = copy.deepcopy(v)
        self.docs[_id] = doc
        self.writes.append(("update", _id))

    def insert_many(self, docs, ordered=True):
        self._chk()
        dup = 0
        for d in docs:
            if d["_id"] in self.docs:
                dup += 1
                continue
            self.docs[d["_id"]] = copy.deepcopy(d)
            self.writes.append(("insert", d["_id"]))
        if dup:
            raise RuntimeError("synthetic duplicate")

    def create_index(self, keys, **kw):
        return "noop"

    def kind(self, k):
        return {i: d for i, d in self.docs.items() if d.get("kind") == k}


class FakeDB:
    def __init__(self, coll):
        self.coll = coll

    def __getitem__(self, name):
        assert name == "ssr_rule_201", name
        return self.coll


class FakeLists:
    """The FROZEN `ssr_lists` interface (spec §3.3)."""
    SSR_COLL = "ssr_rule_201"
    SOURCES = ({"key": "nasdaq", "exchange": "Nasdaq"}, {"key": "nyse", "exchange": "NYSE Group"})
    RETRY_AFTER_SEC = 20

    def __init__(self, rows=(), complete=(), due=False, running=False, views=None):
        self.rows = list(rows)
        self.complete = set(complete)
        self.due = due
        self.running = running
        self.kicks = []
        self.views = views if views is not None else [
            {"key": "nasdaq", "exchange": "Nasdaq", "ok": True, "status": "ok", "as_of": "2026-11-23",
             "edition_et": "04:15:15", "final": False, "n": 1092, "error": None,
             "text": "Nasdaq list (fake view)"},
            {"key": "nyse", "exchange": "NYSE Group", "ok": True, "status": "ok", "as_of": "2026-11-20",
             "edition_et": None, "final": True, "n": 330, "error": None, "text": "NYSE Group list (fake view)"}]

    def load(self, coll, now_et):
        return {"fake": True}

    def rows_for(self, loaded, sym):
        keys = set(SSR._spellings(sym))
        out = [dict(r) for r in self.rows if r["_sym"] in keys]
        for r in out:
            r.pop("_sym")
        return sorted(out, key=lambda r: (r["trigger_date"], r["trigger_time"]), reverse=True)

    def complete_for(self, loaded, T):
        return T in self.complete

    def file_dates(self, now_et):
        return []

    def any_due(self, loaded, now_et):
        return self.due

    def kick_refresh(self, coll, now_et=None, *, http=None):
        self.kicks.append((now_et, http))
        return True

    def worker_running(self):
        return self.running

    def source_views(self, loaded, now_et):
        return copy.deepcopy(self.views)


class FakeCorp:
    """The FROZEN `ssr_corp` interface (spec §3.4a). acts = {iso: {SYM: kind} | None}."""

    def __init__(self, acts=None, due=False):
        self.acts = acts or {}
        self.due = due

    def load(self, coll, days):
        return {"fake": True}

    def actions(self, loaded, T):
        a = self.acts.get(T.isoformat())
        return None if a is None else dict(a)

    def any_due(self, loaded, days, now_et):
        return self.due

    def source_view(self, loaded, days, now_et):
        return {"key": "corp_actions", "exchange": None, "ok": True, "status": "ok", "as_of": "2026-11-23", "n": 2,
                "error": None, "text": "dividends and splits (fake view)"}


def nasdaq_row(sym, tdate, ttime, file_date=None, stamp="20261120163031"):
    return {"_sym": sym, "source": "nasdaq", "exchange": "Nasdaq", "trigger_date": tdate, "trigger_time": ttime,
            "file_date": file_date or tdate, "stamp": stamp}


def nyse_row(sym, tdate, ttime, exchange="NYSE"):
    return {"_sym": sym, "source": "nyse", "exchange": exchange, "trigger_date": tdate, "trigger_time": ttime,
            "file_date": tdate, "stamp": None}


def trig(T: date, sym, basis="snapshot", **kw):
    d = {"_id": "trig|%s|%s" % (T.isoformat(), sym), "kind": "trig", "date": T.isoformat(), "symbol": sym,
         "basis": basis, "created_at": "2026-11-23T15:00:00+00:00"}
    d.update(kw)
    return d


def day(T: date, last_ok: datetime, names=None, final=False):
    d = {"_id": "day|%s" % T.isoformat(), "kind": "day", "date": T.isoformat(), "last_ok_at": utc_iso(last_ok),
         "n_rows": 13000, "n_usable": 12800, "n_trig": 3, "names": names or {}}
    if final:
        d["final"] = True
    return d


def entry(s, at, why=None, by="minute", pc=None, lo=None):
    return {"s": s, "why": why, "by": by, "pc": pc, "lo": lo, "mlo": lo, "drop_pct": None, "at": utc_iso(at)}


def judged(T: date, off, unjudged=None):
    return {"_id": "judged|%s" % T.isoformat(), "kind": "judged", "date": T.isoformat(),
            "at": utc_iso(et(T, 16, 5)), "off": " ".join(sorted(off)), "unjudged": unjudged or {},
            "n_off": len(off), "n_unjudged": len(unjudged or {})}


def read(symbols, docs=(), now=None, lists=None, corp=None, **kw):
    coll = FakeColl(docs)
    lists = lists if lists is not None else FakeLists()
    corp = corp if corp is not None else FakeCorp()
    SSR._reset_cache()
    return SSR.payload(symbols, db=FakeDB(coll), now=now, lists=lists, corp=corp, **kw)


@pytest.fixture(autouse=True)
def _clean():
    SSR._reset_cache()
    yield
    SSR._reset_cache()


# ═════════════════════════════════════════════ the 10% edge
@pytest.mark.parametrize("prev", [4.23, 2.81, 0.07, 1.1, 1.2345, 100.0])
def test_exactly_ten_percent_is_on_for_float_awkward_prices(prev):
    pct = SSR.SSR_TRIGGER_DROP_PCT
    for low in (prev * (1 - pct / 100.0), prev - prev * pct / 100.0, prev * (100 - pct) / 100.0,
                round(prev * (1 - pct / 100.0), 6)):
        assert SSR.is_trigger(low, prev) is True, (prev, low)
    assert SSR.is_trigger(prev * (1 - 10.01 / 100.0), prev) is True


@pytest.mark.parametrize("prev", [4.23, 2.81, 0.07, 1.1, 1.2345, 100.0])
def test_NEGATIVE_a_9_9_percent_drop_and_one_tick_above_the_line_are_off(prev):
    assert SSR.is_trigger(prev * (1 - 9.9 / 100.0), prev) is False
    assert SSR.is_trigger(SSR.trigger_line(prev) + 0.0001, prev) is False


def test_trigger_line_for_akan_and_gp():
    assert SSR.trigger_line(4.23) == 3.807                     # §1.3 measured AKAN line
    assert SSR.trigger_line(2.81) == 2.529                     # §1.3 measured GP line


@pytest.mark.parametrize("bad", [None, 0, -1.0, float("nan"), float("inf"), "x"])
def test_NEGATIVE_no_line_without_a_positive_prior_close(bad):
    assert SSR.trigger_line(bad) is None
    assert SSR.is_trigger(1.0, bad) is None
    assert SSR.is_trigger(bad, 4.23) is None


# ═════════════════════════════════════════════ eval_row
@pytest.mark.parametrize("bad", [None, 0, float("nan")])
def test_NEGATIVE_prior_close_missing_zero_nan_is_unknown_never_off(bad):
    e = SSR.eval_row(snap(4.0, bad, stamp=ms(et(D23, 10, 0))), D23)
    assert e == {"s": "unknown", "why": "no_prior_close"}


def test_NEGATIVE_day_bar_not_dated_the_session_is_no_day_bar():
    e = SSR.eval_row(snap(3.0, 4.23, stamp=ms(et(D20, 15, 59))), D23)
    assert e == {"s": "unknown", "why": "no_day_bar"}


def test_NEGATIVE_a_5x_discontinuity_is_price_suspect_never_on():
    e = SSR.eval_row(snap(4.23 / 5, 4.23, stamp=ms(et(D23, 10, 0)), high=4.23, open_=4.23), D23)
    assert e == {"s": "unknown", "why": "price_suspect"}


def test_eval_row_on_and_off_carry_the_numbers():
    on = SSR.eval_row(snap(17.39, 19.66, stamp=ms(et(D23, 10, 0))), D23)   # PXED §1.3
    assert on == {"s": "on", "pc": 19.66, "lo": 17.39, "drop_pct": -11.5}
    off = SSR.eval_row(snap(4.0, 4.23, stamp=ms(et(D23, 10, 0))), D23)
    assert off["s"] == "off" and off["drop_pct"] == -5.4


# ═════════════════════════════════════════════ the stamp guard [C3]
def test_NEGATIVE_the_critics_pre_open_row_is_no_day_bar_and_stale():
    row = snap(2.58, 4.23, stamp=ms(et(D24, 9, 29)), close=2.58)
    assert SSR.eval_row(row, D24) == {"s": "unknown", "why": "no_day_bar", "stale": True}


def test_NEGATIVE_the_critics_row_writes_no_trig_doc_after_a_pass():
    coll = FakeColl()
    rows = {"AKAN": snap(2.58, 4.23, stamp=ms(et(D24, 9, 29)), close=2.58)}
    out = SSR.record_pass(rows, {}, et(D24, 9, 31), D24, db=FakeDB(coll))
    assert coll.kind("trig") == {} and out["stale_bar"] == 1 and out["new"] == 0


def test_stamp_guard_admits_0930_and_a_nanosecond_last_trade():
    assert SSR.eval_row(snap(3.0, 4.23, stamp=ms(et(D24, 9, 30))), D24)["s"] == "on"
    assert SSR.eval_row(snap(3.0, 4.23, last=ns(et(D24, 9, 31))), D24)["s"] == "on"


def test_NEGATIVE_stamp_guard_refusals():
    assert SSR.eval_row(snap(3.0, 4.23, last=ns(et(D24, 9, 20))), D24)["why"] == "no_day_bar"
    r = SSR.eval_row(snap(3.0, 4.23, stamp=ms(et(D24, 9, 29)), last=ns(et(D24, 9, 31))), D24)
    assert r == {"s": "unknown", "why": "no_day_bar", "stale": True}           # the minute stamp rules
    assert SSR.eval_row(snap(3.0, 4.23), D24) == {"s": "unknown", "why": "no_day_bar"}


# ═════════════════════════════════════════════ minute bars
AKAN_PRE = [(4, 0, 3.90), (8, 15, 3.61), (9, 29, 3.85)]          # §1.3: pre-market low 3.61 under 3.807


def test_NEGATIVE_a_pre_market_drop_does_not_trigger():
    raw = minutes(D23, AKAN_PRE + [(9, 30, 3.90), (9, 31, 3.95)])
    assert SSR.first_trigger_minute(raw, D23, 4.23) is None


def test_the_akan_0930_minute_triggers():
    raw = minutes(D23, AKAN_PRE + [(9, 30, 3.68), (9, 31, 3.60)])
    assert SSR.first_trigger_minute(raw, D23, 4.23) == {"at": "09:30", "low": 3.68, "drop_pct": -13.0}


def test_NEGATIVE_an_after_hours_minute_does_not_trigger():
    raw = minutes(D23, [(15, 59, 3.90), (16, 0, 3.00), (19, 30, 2.78)])
    assert SSR.first_trigger_minute(raw, D23, 4.23) is None
    assert SSR.rth_minutes(raw, D23) == {"n": 1, "low": 3.90}


def test_NEGATIVE_half_day_1330_minute_does_not_trigger_despite_an_rth_session_column():
    raw = minutes(D27, [(12, 59, 3.90), (13, 30, 3.00)], session_col="rth")
    assert SSR.first_trigger_minute(raw, D27, 4.23) is None
    assert SSR.rth_minutes(raw, D27)["n"] == 1


def test_gp_retrigger_minute():
    raw = minutes(D23, [(13, 42, 2.60), (13, 43, 2.50)])           # §1.3 GP first at/under 13:43 low 2.50
    assert SSR.first_trigger_minute(raw, D23, 2.81) == {"at": "13:43", "low": 2.50, "drop_pct": -11.0}


def test_NEGATIVE_rth_minutes_of_nothing():
    assert SSR.rth_minutes(None, D23) == {"n": 0, "low": None}
    assert SSR.rth_minutes(pd.DataFrame(), D23) == {"n": 0, "low": None}


# ═════════════════════════════════════════════ judge_followed [C2]
ROW_ON = snap(2.64, 3.00, stamp=ms(et(D23, 11, 0)))               # SYNTHETIC: −12% snapshot day low


def test_judge_rows_no_prior_close_and_price_suspect_are_snapshot_unknowns():
    raw = minutes(D23, [(10, 0, 2.0)])
    assert SSR.judge_followed(snap(2.0, None, stamp=ms(et(D23, 10, 0))), raw, D23) == \
        {"s": "unknown", "why": "no_prior_close", "by": "snapshot"}
    assert SSR.judge_followed(None, raw, D23)["why"] == "no_prior_close"
    j = SSR.judge_followed(snap(0.5, 3.0, stamp=ms(et(D23, 10, 0)), high=3.0, open_=3.0), raw, D23)
    assert j["why"] == "price_suspect" and j["by"] == "snapshot"


def test_judge_minute_hit_is_on_by_minute():
    j = SSR.judge_followed(ROW_ON, minutes(D23, [(9, 45, 2.95), (10, 5, 2.70)]), D23)
    assert j["s"] == "on" and j["by"] == "minute" and j["at"] == "10:05" and j["lo"] == 2.70


def test_NEGATIVE_judge_snapshot_on_without_a_minute_hit_is_bars_disagree():
    j = SSR.judge_followed(ROW_ON, minutes(D23, [(9, 45, 2.95), (10, 5, 2.82)]), D23)
    assert j["s"] == "unknown" and j["why"] == "bars_disagree" and j["lo"] == 2.64 and j["mlo"] == 2.82


def test_judge_minutes_off_with_snapshot_off_or_no_day_bar_is_off_by_minute():
    raw = minutes(D23, [(9, 45, 2.95), (10, 5, 2.82)])
    j = SSR.judge_followed(snap(2.9, 3.0, stamp=ms(et(D23, 11, 0))), raw, D23)
    assert j["s"] == "off" and j["by"] == "minute"
    j2 = SSR.judge_followed(snap(2.9, 3.0, stamp=ms(et(D23, 9, 20))), raw, D23)
    assert j2["s"] == "off" and j2["by"] == "minute"


def test_judge_without_minutes_is_the_snapshot_as_is():
    j = SSR.judge_followed(ROW_ON, None, D23)
    assert j["s"] == "on" and j["by"] == "snapshot" and j["lo"] == 2.64


def test_akan_real_numbers_day_low_2_58_with_the_0930_minute_is_on_by_minute():
    row = snap(2.58, 4.23, stamp=ms(et(D23, 15, 59)), close=2.58)
    raw = minutes(D23, AKAN_PRE + [(9, 30, 3.68), (14, 50, 2.80)])
    j = SSR.judge_followed(row, raw, D23)
    assert j["s"] == "on" and j["by"] == "minute" and j["at"] == "09:30"


# ═════════════════════════════════════════════ window / in_play
@pytest.mark.parametrize("now,want", [
    (et(D23, 22, 9), [D23]),
    (et(D24, 8, 0), [D23]),
    (et(D25, 10, 0), [D25, D24]),
    (et(date(2026, 11, 26), 12, 0), [D25]),
    (et(D27, 14, 0), [D27, D25]),
    (et(D27, 17, 30), [D27]),
    (et(date(2026, 11, 28), 12, 0), [D27]),
])
def test_in_play_scenarios(now, want):
    assert SSR.in_play(now) == want


def test_window_mon_trigger():
    w = SSR.window(D23)
    assert w["through"] == D24 and w["off_from"] == D25 and w["expires_at"] == et(D24, 20, 0)
    assert w["half_day"] is False


def test_NEGATIVE_tuesday_2001_the_monday_trigger_is_out_of_play():
    assert D23 not in SSR.in_play(et(D24, 20, 1))
    assert SSR.in_play(et(D24, 19, 59)) == [D24, D23]


def test_holiday_wed_trigger_runs_through_fri():
    w = SSR.window(D25)
    assert w["through"] == D27 and w["off_from"] == date(2026, 11, 30)


def test_half_day_window_and_title():
    w = SSR.window(D25)
    assert w["half_day"] is True and w["expires_at"] == et(D27, 17, 0) and w["rth_close"].strftime("%H:%M") == "13:00"
    docs = [trig(D25, "ZZHD", "minute_bar", at="10:00", low=2.0, drop_pct=-20.0, prev_close=2.5)]
    p = read(["ZZHD"], docs, now=et(date(2026, 11, 26), 12, 0))
    assert "regular close 13:00 ET" in p["items"]["ZZHD"]["title"]
    assert p["items"]["ZZHD"]["half_day"] is True


def test_clocks_half_day_1730_in_play_drops_wed_while_mode_for_reads_after_hours():
    from chart_maps import drop10_tab
    assert D25 not in SSR.in_play(et(D27, 17, 30))
    assert drop10_tab.mode_for(et(D27, 17, 30))[0] == drop10_tab.MODE_AFTER
    out = SSR.record_pass({"A": snap(1.0, 1.2, stamp=ms(et(D27, 12, 0)))}, {}, et(D27, 17, 30), D27,
                          db=FakeDB(FakeColl()))
    assert "error" not in out


# ═════════════════════════════════════════════ record_pass
def _pass(coll, rows, now, session, frames=None, followed=(), good=True):
    return SSR.record_pass(rows, frames or {}, now, session, followed=followed, good=good, db=FakeDB(coll))


def test_NEGATIVE_closed_and_pre_market_write_nothing():
    coll = FakeColl()
    rows = {"A": snap(1.0, 2.0, stamp=ms(et(D23, 10, 0)))}
    assert _pass(coll, rows, et(D23, 8, 0), D23) == {"skipped": "closed"}
    assert _pass(coll, rows, et(D23, 21, 0), D23) == {"skipped": "closed"}
    assert _pass(coll, rows, et(D23, 10, 0), D24) == {"skipped": "closed"}
    assert coll.docs == {}


def test_NEGATIVE_good_false_writes_nothing_and_no_at_moves():
    coll = FakeColl([day(D23, et(D23, 10, 0), {"A": entry("off", et(D23, 10, 0))})])
    before = copy.deepcopy(coll.docs)
    rows = {"A": snap(1.0, 2.0, stamp=ms(et(D23, 10, 0)))}
    assert _pass(coll, rows, et(D23, 10, 5), D23, followed=["A"], good=False) == {"skipped": "snapshot"}
    assert _pass(coll, {}, et(D23, 10, 5), D23, followed=["A"]) == {"skipped": "snapshot"}
    assert coll.docs == before


def test_snapshot_trigger_inserts_once_in_rth():
    coll = FakeColl()
    rows = {"ZZA": snap(1.0, 2.0, stamp=ms(et(D23, 10, 0))), "ZZB": snap(1.9, 2.0, stamp=ms(et(D23, 10, 0)))}
    out = _pass(coll, rows, et(D23, 10, 1), D23)
    assert out["new"] == 1 and list(coll.kind("trig")) == ["trig|2026-11-23|ZZA"]
    d = coll.docs["trig|2026-11-23|ZZA"]
    assert d["basis"] == "snapshot" and d["at"] is None and d["seen_at"] == "10:01" and d["drop_pct"] == -50.0
    out2 = _pass(coll, rows, et(D23, 10, 6), D23)
    assert out2["new"] == 0 and len(coll.kind("trig")) == 1
    assert coll.docs["trig|2026-11-23|ZZA"]["seen_at"] == "10:01"


def test_NEGATIVE_after_close_writes_no_snapshot_trig_and_lands_late_print():
    rows = {"ZZL": snap(1.0, 2.0, stamp=ms(et(D23, 15, 59)), last=ns(et(D23, 16, 9)))}
    coll = FakeColl()
    above = {"ZZL": snap(1.95, 2.0, stamp=ms(et(D23, 15, 59)))}
    _pass(coll, above, et(D23, 15, 55), D23)
    out = _pass(coll, rows, et(D23, 16, 10), D23)
    assert coll.kind("trig") == {} and out["new"] == 0
    assert coll.docs["judged|2026-11-23"]["unjudged"] == {"ZZL": "late_print"}
    assert out["final"] is True and coll.docs["day|2026-11-23"]["final"] is True


def test_minute_hit_upgrades_a_snapshot_doc_and_never_downgrades():
    coll = FakeColl()
    rows = {"ZZM": ROW_ON}
    _pass(coll, rows, et(D23, 11, 1), D23)                     # not followed → snapshot doc
    assert coll.docs["trig|2026-11-23|ZZM"]["basis"] == "snapshot"
    raw = minutes(D23, [(9, 45, 2.95), (10, 5, 2.70)])
    out = _pass(coll, rows, et(D23, 11, 6), D23, frames={"ZZM": fr(raw)}, followed=["ZZM"])
    d = coll.docs["trig|2026-11-23|ZZM"]
    assert out["upgraded"] == 1 and d["basis"] == "minute_bar" and d["at"] == "10:05" and d["low"] == 2.70
    assert d["created_at"] == coll.docs["trig|2026-11-23|ZZM"]["created_at"]
    _pass(coll, rows, et(D23, 11, 11), D23)                    # not followed again: no snapshot overwrite
    assert coll.docs["trig|2026-11-23|ZZM"]["basis"] == "minute_bar"


def test_NEGATIVE_bars_disagree_writes_no_trig_and_voids_an_existing_snapshot_doc():
    raw = minutes(D23, [(9, 45, 2.95), (10, 5, 2.82)])
    coll = FakeColl()
    out = _pass(coll, {"ZZD": ROW_ON}, et(D23, 11, 1), D23, frames={"ZZD": fr(raw)}, followed=["ZZD"])
    assert coll.kind("trig") == {} and out["disagree"] == 1 and out["lo_under_minutes"] == 1
    assert coll.docs["day|2026-11-23"]["names"]["ZZD"]["why"] == "bars_disagree"
    coll2 = FakeColl()
    _pass(coll2, {"ZZD": ROW_ON}, et(D23, 11, 1), D23)         # snapshot doc first (not followed)
    out2 = _pass(coll2, {"ZZD": ROW_ON}, et(D23, 11, 6), D23, frames={"ZZD": fr(raw)}, followed=["ZZD"])
    assert out2["voided"] == 1 and coll2.docs["trig|2026-11-23|ZZD"]["void"] == "bars_disagree"
    p = SSR.payload(["ZZD"], db=FakeDB(coll2), now=et(D23, 11, 7), lists=FakeLists(complete={D20}), corp=FakeCorp())
    assert p["states"]["ZZD"] == "unknown" and p["whys"]["ZZD"] == "bars_disagree"
    assert p["items"]["ZZD"]["chip"] is None
    raw_hit = minutes(D23, [(9, 45, 2.95), (10, 5, 2.82), (11, 3, 2.69)])
    out3 = _pass(coll2, {"ZZD": ROW_ON}, et(D23, 11, 11), D23, frames={"ZZD": fr(raw_hit)}, followed=["ZZD"])
    d = coll2.docs["trig|2026-11-23|ZZD"]
    assert out3["upgraded"] == 1 and "void" not in d and d["basis"] == "minute_bar" and d["at"] == "11:03"


def test_close_pass_writes_judged_once_byte_identical_and_final_never_unset():
    coll = FakeColl()
    rows = {"ZZON": snap(1.0, 2.0, stamp=ms(et(D23, 15, 0))), "ZZOFF": snap(1.95, 2.0, stamp=ms(et(D23, 15, 0))),
            "BRK-B": snap(500.0, 505.0, stamp=ms(et(D23, 15, 0))), "ZZNOP": snap(1.0, None, stamp=ms(et(D23, 15, 0)))}
    _pass(coll, rows, et(D23, 15, 0), D23)
    out = _pass(coll, rows, et(D23, 16, 5), D23)
    j = copy.deepcopy(coll.docs["judged|2026-11-23"])
    assert out["final"] is True and j["off"] == "BRK-B ZZOFF" and j["unjudged"] == {"ZZNOP": "no_prior_close"}
    assert j["n_off"] == 2 and j["n_unjudged"] == 1
    rows2 = dict(rows, ZZOFF=snap(1.0, 2.0, stamp=ms(et(D23, 15, 0))))
    _pass(coll, rows2, et(D23, 16, 30), D23)
    assert coll.docs["judged|2026-11-23"] == j
    assert coll.docs["day|2026-11-23"]["final"] is True


def _keys_deep(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys_deep(v)


def test_close_pass_stores_a_dotted_snapshot_symbol_under_its_dash_field_key():
    """60 of 13,282 live snapshot keys hold a dot (warrants such as FCRS.WS — refix 2026-11-23)."""
    coll = FakeColl()
    above = {"ZZW.WS": snap(1.95, 2.0, stamp=ms(et(D23, 15, 59)))}
    _pass(coll, above, et(D23, 15, 55), D23)
    rows = {"FCRS.WS": snap(1.0, None, stamp=ms(et(D23, 15, 0))),
            "ZZW.WS": snap(1.0, 2.0, stamp=ms(et(D23, 15, 59)), last=ns(et(D23, 16, 9))),
            "ZZO.U": snap(1.95, 2.0, stamp=ms(et(D23, 15, 0)))}
    out = _pass(coll, rows, et(D23, 16, 10), D23)
    j = coll.docs["judged|2026-11-23"]
    assert out["final"] is True
    assert j["unjudged"] == {"FCRS-WS": "no_prior_close", "ZZW-WS": "late_print"} and j["n_unjudged"] == 2
    assert j["off"] == "ZZO.U"
    p = SSR.payload(["FCRS.WS", "FCRS-WS", "ZZW.WS", "ZZO.U", "ZZO-U"], db=FakeDB(coll), now=EVE, lists=FakeLists(),
                    corp=FakeCorp())
    assert p["whys"]["FCRS.WS"] == "no_prior_close" and p["whys"]["FCRS-WS"] == "no_prior_close"
    assert p["whys"]["ZZW.WS"] == "late_print"
    assert p["states"]["ZZO.U"] == "off" and p["states"]["ZZO-U"] == "off"


def test_NEGATIVE_no_dotted_or_dollar_field_key_ever_reaches_the_judged_doc():
    coll = FakeColl()
    rows = {"FCRS.WS": snap(1.0, None, stamp=ms(et(D23, 15, 0))), "$ZZ": snap(1.0, None, stamp=ms(et(D23, 15, 0))),
            "A.B.C": snap(1.0, None, stamp=ms(et(D23, 15, 0)))}
    _pass(coll, rows, et(D23, 16, 5), D23, followed=["FCRS.WS"])
    j = coll.docs["judged|2026-11-23"]
    for k in _keys_deep(j):
        assert "." not in k and not k.startswith("$"), k
    for k in _keys_deep(coll.docs["day|2026-11-23"]):
        assert "." not in k and not k.startswith("$"), k
    assert j["unjudged"] == {"FCRS-WS": "no_prior_close", "A-B-C": "no_prior_close"}
    p = SSR.payload(["FCRS.WS", "FCRSWS", "$ZZ"], db=FakeDB(coll), now=EVE, lists=FakeLists(), corp=FakeCorp())
    assert p["states"]["FCRSWS"] == "unknown" and p["whys"]["FCRSWS"] == "no_final_read"
    assert p["states"].get("$ZZ") != "off"
    assert p["states"]["FCRS.WS"] == "unknown"


def test_half_day_1306_is_a_close_pass_and_1310_writes_no_snapshot_trig():
    coll = FakeColl()
    rows = {"ZZH": snap(1.95, 2.0, stamp=ms(et(D27, 12, 59)))}
    out = _pass(coll, rows, et(D27, 13, 6), D27)
    assert out["final"] is True and coll.docs["day|2026-11-27"]["final"] is True
    rows2 = {"ZZH": snap(1.0, 2.0, stamp=ms(et(D27, 12, 59)), last=ns(et(D27, 13, 8)))}
    _pass(coll, rows2, et(D27, 13, 10), D27)
    assert coll.kind("trig") == {}


def test_names_are_merged_each_with_its_own_at():
    coll = FakeColl()
    rows = {"ZZA": snap(1.95, 2.0, stamp=ms(et(D23, 10, 0))), "ZZB": snap(1.95, 2.0, stamp=ms(et(D23, 10, 0)))}
    _pass(coll, rows, et(D23, 10, 0), D23, followed=["ZZA", "ZZB"])
    _pass(coll, rows, et(D23, 10, 5), D23, followed=["ZZB"])
    names = coll.docs["day|2026-11-23"]["names"]
    assert names["ZZA"]["at"] == utc_iso(et(D23, 10, 0)) and names["ZZB"]["at"] == utc_iso(et(D23, 10, 5))
    assert coll.docs["day|2026-11-23"]["last_ok_at"] == utc_iso(et(D23, 10, 5))


def test_rows_are_read_as_a_dict_and_a_raising_collection_returns_an_error():
    coll = FakeColl()
    coll.raise_all = True
    out = _pass(coll, {"A": snap(1.0, 2.0, stamp=ms(et(D23, 10, 0)))}, et(D23, 10, 1), D23)
    assert out == {"error": "RuntimeError"}


def test_the_return_carries_the_standing_measurements():
    coll = FakeColl()
    out = _pass(coll, {"A": snap(1.95, 2.0, stamp=ms(et(D23, 10, 0)))}, et(D23, 10, 1), D23)
    for k in ("rows", "usable", "new", "upgraded", "voided", "followed", "final", "stale_bar", "lo_under_minutes",
              "disagree"):
        assert k in out, k


def test_NEGATIVE_record_pass_never_imports_ssr_corp(monkeypatch):
    monkeypatch.setitem(sys.modules, "short_interest.ssr_corp", None)      # any import of it now raises
    coll = FakeColl()
    out = _pass(coll, {"ZZA": snap(1.0, 2.0, stamp=ms(et(D23, 10, 0)))}, et(D23, 10, 1), D23)
    assert out["new"] == 1
    for fn in (SSR._record_pass, SSR.record_pass, SSR._judge, SSR.eval_row):
        tree = ast.parse(inspect.getsource(fn).strip())
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                assert "ssr_corp" not in [a.name for a in n.names] and "ssr_corp" not in (n.module or "")
            if isinstance(n, ast.Name):
                assert n.id != "_resolve_corp"


def test_NEGATIVE_record_pass_writes_on_when_ssr_lists_cannot_import(monkeypatch):
    """§6.15 severability: a broken ssr_lists stops the official half only, never the computed half."""
    monkeypatch.setitem(sys.modules, "short_interest.ssr_lists", None)      # any import of it now raises
    monkeypatch.delattr(sys.modules["short_interest"], "ssr_lists", raising=False)
    with pytest.raises(ImportError):
        SSR._resolve_lists(None)
    coll = FakeColl()
    out = _pass(coll, {"ZZA": snap(1.0, 2.0, stamp=ms(et(D23, 10, 0)))}, et(D23, 10, 1), D23)
    assert "error" not in out and out["new"] == 1
    assert "trig|2026-11-23|ZZA" in coll.docs and "day|2026-11-23" in coll.docs


def test_NEGATIVE_record_pass_writes_on_when_ssr_lists_raises_on_import(monkeypatch):
    broken = types.ModuleType("short_interest.ssr_lists")

    def _boom(name):
        raise RuntimeError("broken module")
    broken.__getattr__ = _boom                                               # SSR_COLL access raises
    monkeypatch.setitem(sys.modules, "short_interest.ssr_lists", broken)
    monkeypatch.setattr(sys.modules["short_interest"], "ssr_lists", broken, raising=False)
    assert SSR._coll_name() == SSR.SSR_COLL_FALLBACK
    out = _pass(FakeColl(), {"ZZA": snap(1.0, 2.0, stamp=ms(et(D23, 10, 0)))}, et(D23, 10, 1), D23)
    assert "error" not in out and out["new"] == 1


def test_the_fallback_collection_name_equals_ssr_lists():
    from short_interest import ssr_lists
    assert SSR.SSR_COLL_FALLBACK == ssr_lists.SSR_COLL
    assert SSR._coll_name() == ssr_lists.SSR_COLL


# ═════════════════════════════════════════════ the resolution
NOW = et(D23, 14, 0)


def test_official_on_wins_over_computed_off_with_a_conflict():
    lists = FakeLists(rows=[nasdaq_row("ZZOF", "2026-11-23", "10:12:00", stamp="20261123163004")], complete={D20})
    docs = [day(D23, et(D23, 13, 56), {"ZZOF": entry("off", et(D23, 13, 56), pc=5.0, lo=4.8)})]
    p = read(["ZZOF"], docs, now=NOW, lists=lists)
    it = p["items"]["ZZOF"]
    assert it["state"] == "on" and it["source"] == "official" and it["conflict"] == "official_on_computed_off"
    assert "the exchange's list decides" in it["title"] and "day low 4.80 vs the prior close 5.00" in it["title"]
    assert it["label"] == "⛔ SSR on · no shorting at the bid · through Tue 11/24 · Nasdaq list"
    assert "file stamped 11/23 16:30:04 ET" in it["title"]


def test_official_on_with_a_judged_off_has_a_bare_conflict_clause():
    lists = FakeLists(rows=[nyse_row("ZZJ", "2026-11-23", "09:37:47", "NYSE American")], complete={D20})
    docs = [day(D23, et(D23, 20, 1), final=True), judged(D23, {"ZZJ"})]
    p = read(["ZZJ"], docs, now=et(D23, 22, 9), lists=lists)
    it = p["items"]["ZZJ"]
    assert it["conflict"] == "official_on_computed_off" and "the exchange's list decides" in it["title"]
    assert it["label"].endswith("· NYSE American list") and "NYSE Group short sale circuit breaker list" in it["title"]


def test_re_trigger_governed_by_the_newer_day():
    lists = FakeLists(rows=[nasdaq_row("GP", "2026-11-20", "09:45:36")], complete={D20})
    docs = [trig(D23, "GP", "minute_bar", at="13:43", low=2.50, drop_pct=-11.0, prev_close=2.81)]
    it = read(["GP"], docs, now=NOW, lists=lists)["items"]["GP"]
    assert it["triggered_on"] == "2026-11-23" and it["retriggered"] is True and it["through"] == "2026-11-24"
    assert it["source"] == "computed" and "Also triggered Fri 11/20" in it["title"]


def test_NEGATIVE_a_d_plus_1_with_no_new_trigger_still_ends_at_d_plus_1():
    lists = FakeLists(rows=[nasdaq_row("GIPR", "2026-11-20", "11:44:16")], complete={D20})
    docs = [day(D23, et(D23, 13, 56), {"GIPR": entry("off", et(D23, 13, 56))})]
    it = read(["GIPR"], docs, now=NOW, lists=lists)["items"]["GIPR"]
    assert it["through"] == "2026-11-23" and it["retriggered"] is False and it["chip"].endswith("thru Mon 11/23")
    p = read(["GIPR"], docs, now=et(D23, 20, 1), lists=lists)     # 11/20's window closed at 20:00 on Mon 11/23
    assert p["session"]["in_play"] == ["2026-11-23"] and p["states"]["GIPR"] != "on"


def test_NEGATIVE_computed_only_once_lists_complete_no_item_never_off():
    docs = [trig(D20, "ZZCO", seen_at="11:00", prev_close=5.0, low=4.4, drop_pct=-12.0),
            day(D23, et(D23, 13, 56), {"ZZCO": entry("off", et(D23, 13, 56))})]
    p = read(["ZZCO"], docs, now=NOW, lists=FakeLists(complete={D20}))
    assert p["states"]["ZZCO"] == "unknown" and p["whys"]["ZZCO"] == "computed_only" and "ZZCO" not in p["items"]


def test_computed_only_with_the_switch_off_is_an_item(monkeypatch):
    monkeypatch.setattr(SSR, "SSR_COMPUTED_UNTIL_LISTS_COMPLETE", False)
    docs = [trig(D20, "ZZCO", seen_at="11:00", prev_close=5.0, low=4.4, drop_pct=-12.0),
            day(D23, et(D23, 13, 56), {"ZZCO": entry("off", et(D23, 13, 56))})]
    it = read(["ZZCO"], docs, now=NOW, lists=FakeLists(complete={D20}))["items"]["ZZCO"]
    assert it["state"] == "on" and it["chip"].endswith(" · computed") and it["conflict"] == "computed_only"
    assert SSR.NOT_ON_ANY_LIST in it["title"]


def test_computed_tag_shows_while_lists_are_not_complete():
    docs = [trig(D23, "AKAN", "minute_bar", at="09:30", low=3.68, drop_pct=-13.0, prev_close=4.23)]
    it = read(["AKAN"], docs, now=NOW, lists=FakeLists(complete={D20}))["items"]["AKAN"]
    assert it["chip"] == "⛔ SSR · no shorting at the bid · thru Tue 11/24 · computed"
    assert it["short"] == "⛔ SSR thru 11/24 · computed"
    assert it["label"] == "⛔ SSR on · no shorting at the bid · through Tue 11/24 · computed from the house's bars"
    assert SSR.NOT_ON_LIST_YET in it["title"] and it["time_basis"] == "minute_bar" and it["triggered_at_et"] == "09:30"


# ── corporate actions [C1b, C6]
PXED_TRIG = trig(D23, "PXED", seen_at="10:05", prev_close=19.66, low=17.39, drop_pct=-11.5)   # §1.3 measured


def test_NEGATIVE_pxed_dividend_is_unknown_corp_action_label_only():
    p = read(["PXED"], [PXED_TRIG], now=NOW, lists=FakeLists(complete={D20}),
             corp=FakeCorp({"2026-11-23": {"PXED": "dividend"}, "2026-11-20": {}}))
    it = p["items"]["PXED"]
    assert p["whys"]["PXED"] == "corp_action" and it["chip"] is None and it["short"] is None
    assert it["label"] == "⛔ SSR not read" and "a dividend or a split took effect on Mon 11/23" in it["title"]


def test_pxed_once_both_lists_are_complete_reads_off():
    docs = [PXED_TRIG, day(D23, et(D23, 20, 1), final=True), judged(D23, set())]
    p = read(["PXED"], docs, now=et(D23, 22, 9), lists=FakeLists(complete={D23}),
             corp=FakeCorp({"2026-11-23": {"PXED": "dividend"}}))
    assert p["states"]["PXED"] == "off" and "PXED" not in p["items"]


def test_a_dividend_name_judged_off_stays_off():
    docs = [day(D23, et(D23, 20, 1), final=True), judged(D23, {"ZZDV"})]
    p = read(["ZZDV"], docs, now=et(D23, 22, 9), corp=FakeCorp({"2026-11-23": {"ZZDV": "dividend"}}))
    assert p["states"]["ZZDV"] == "off"


def test_NEGATIVE_a_split_name_computed_off_is_corp_action_never_off():
    docs = [day(D23, et(D23, 20, 1), final=True), judged(D23, {"TOPP"})]
    p = read(["TOPP"], docs, now=et(D23, 22, 9), corp=FakeCorp({"2026-11-23": {"TOPP": "split"}}))
    assert p["states"]["TOPP"] == "unknown" and p["whys"]["TOPP"] == "corp_action"
    docs2 = [day(D23, et(D23, 13, 56), {"TOPP": entry("off", et(D23, 13, 56))})]
    p2 = read(["TOPP"], docs2, now=NOW, lists=FakeLists(complete={D20}),
              corp=FakeCorp({"2026-11-23": {"TOPP": "split"}, "2026-11-20": {}}))
    assert p2["whys"]["TOPP"] == "corp_action"


def test_NEGATIVE_a_split_name_computed_on_is_unknown():
    docs = [trig(D23, "TOPP", seen_at="10:00", prev_close=1.0, low=0.5, drop_pct=-50.0)]
    p = read(["TOPP"], docs, now=NOW, lists=FakeLists(complete={D20}),
             corp=FakeCorp({"2026-11-23": {"TOPP": "split"}, "2026-11-20": {}}))
    assert p["states"]["TOPP"] == "unknown" and p["whys"]["TOPP"] == "corp_action"


def test_a_split_name_with_an_official_row_is_on_official():
    lists = FakeLists(rows=[nyse_row("TOPP", "2026-11-23", "10:01:02", "NYSE American")], complete={D20})
    p = read(["TOPP"], [], now=NOW, lists=lists, corp=FakeCorp({"2026-11-23": {"TOPP": "split"}}))
    assert p["items"]["TOPP"]["state"] == "on" and p["items"]["TOPP"]["source"] == "official"


def test_corp_unread_keeps_the_computed_tag_with_the_note(monkeypatch):
    it = read(["ZZU"], [trig(D23, "ZZU", seen_at="10:00", prev_close=2.0, low=1.0, drop_pct=-50.0)], now=NOW,
              lists=FakeLists(complete={D20}), corp=FakeCorp({}))["items"]["ZZU"]
    assert it["state"] == "on" and it["corp_checked"] is False and SSR.CORP_UNREAD_NOTE.strip() in it["title"]
    assert SSR.PRIOR_CLOSE_NOTE.strip() in it["title"]


def test_NEGATIVE_an_unimportable_ssr_corp_reads_as_not_read_no_raise(monkeypatch):
    monkeypatch.setitem(sys.modules, "short_interest.ssr_corp", None)
    monkeypatch.delattr(sys.modules["short_interest"], "ssr_corp", raising=False)
    coll = FakeColl([trig(D23, "ZZU", seen_at="10:00", prev_close=2.0, low=1.0, drop_pct=-50.0)])
    p = SSR.payload(["ZZU"], db=FakeDB(coll), now=NOW, lists=FakeLists(complete={D20}))
    it = p["items"]["ZZU"]
    assert it["state"] == "on" and it["corp_checked"] is False and SSR.CORP_UNREAD_NOTE.strip() in it["title"]
    assert [s["key"] for s in p["sources"]] == ["nasdaq", "nyse"]


# ── coverage [C4, C5]
EVE = et(D23, 22, 9)
EVE_DOCS = [day(D23, et(D23, 20, 1), final=True),
            judged(D23, {"ZZOK", "BRK-B"}, {"ZZBD": "bars_disagree", "ZZLP": "late_print"})]


def test_evening_coverage_rests_on_the_judged_doc():
    p = read(["ZZOK", "ZZBD", "ZZLP", "ZZNONE"], EVE_DOCS, now=EVE)
    assert p["states"] == {"ZZOK": "off", "ZZBD": "unknown", "ZZLP": "unknown", "ZZNONE": "unknown"}
    assert p["whys"] == {"ZZBD": "bars_disagree", "ZZLP": "late_print", "ZZNONE": "no_final_read"}
    assert "only after the last regular-hours scan" in p["items"]["ZZLP"]["title"]


def test_NEGATIVE_spellings_brk_dot_b_finds_brk_dash_b_and_a_miss_reads_unknown():
    p = read(["BRK.B", "BRK B", "BRKB"], EVE_DOCS, now=EVE)
    assert p["states"]["BRK.B"] == "off" and p["states"]["BRK B"] == "off"
    assert p["states"]["BRKB"] == "unknown" and p["whys"]["BRKB"] == "no_final_read"


def test_a_late_print_name_turns_on_when_the_official_row_arrives():
    lists = FakeLists(rows=[nasdaq_row("ZZLP", "2026-11-23", "15:58:10", stamp="20261123163004")])
    p = read(["ZZLP"], EVE_DOCS, now=EVE, lists=lists)
    assert p["items"]["ZZLP"]["state"] == "on" and p["items"]["ZZLP"]["source"] == "official"


# ── missing sources → unknown, never off
def test_NEGATIVE_mongo_down_every_name_unread_with_the_fault_line():
    p = SSR.payload(["AKAN", "aapl"], db=None, now=NOW, lists=FakeLists(), corp=FakeCorp())
    assert p["status"] == "failed" and p["states"] == {"AKAN": "unknown", "AAPL": "unknown"}
    assert p["whys"] == {"AKAN": "unread", "AAPL": "unread"}
    assert p["fault_text"] == "⛔ SSR tags could not be read — a missing tag does not mean the restriction is off."


def test_NEGATIVE_no_list_docs_and_no_day_doc_is_unknown():
    p = read(["ZZX"], [], now=NOW, lists=FakeLists())
    assert p["states"]["ZZX"] == "unknown" and p["whys"]["ZZX"] == "scan_stale"


def test_NEGATIVE_a_stale_names_entry_in_rth_is_scan_stale_even_in_a_fresh_doc():
    limit = SSR.SSR_STALE_PASSES * 300
    docs = [day(D23, et(D23, 13, 59), {"ZZS": entry("off", NOW - timedelta(seconds=limit + 60)),
                                        "ZZF": entry("off", NOW - timedelta(seconds=limit - 60))})]
    p = read(["ZZS", "ZZF"], docs, now=NOW, lists=FakeLists(complete={D20}))
    assert p["states"] == {"ZZS": "unknown", "ZZF": "off"} and p["whys"]["ZZS"] == "scan_stale"


def test_NEGATIVE_a_not_followed_name_in_rth_is_not_followed():
    docs = [day(D23, et(D23, 13, 56))]
    p = read(["ZZNF"], docs, now=NOW, lists=FakeLists(complete={D20}))
    assert p["whys"]["ZZNF"] == "not_followed" and p["items"]["ZZNF"]["label"] == "⛔ SSR not read"


def test_awaiting_first_scan_serves_no_form():
    p = read(["ZZW"], [], now=et(D24, 9, 33), lists=FakeLists(complete={D23}))
    assert p["whys"]["ZZW"] == "awaiting_first_scan" and "ZZW" not in p["items"]


def test_NEGATIVE_the_read_makes_zero_outside_calls_and_kicks_only_through_lists():
    calls = []

    def http(*a, **k):
        calls.append(a)
        raise AssertionError("outside call")

    lists = FakeLists(due=True)
    p = read(["AKAN"], [], now=NOW, lists=lists, http=http)
    assert calls == [] and len(lists.kicks) == 1 and lists.kicks[0][1] is http
    assert p["refreshing"] is True and p["retry_after_sec"] == 20
    lists2 = FakeLists(due=False)
    read(["AKAN"], [], now=NOW, lists=lists2, corp=FakeCorp(due=True))
    assert len(lists2.kicks) == 1
    lists3 = FakeLists(due=False)
    p3 = read(["AKAN"], [], now=NOW, lists=lists3, corp=FakeCorp(due=False))
    assert lists3.kicks == [] and p3["refreshing"] is False and p3["retry_after_sec"] is None


def test_fault_text_when_no_official_source_ok_and_computed_not_ok():
    views = [{"key": "nasdaq", "exchange": "Nasdaq", "ok": False, "status": "failed", "text": "Nasdaq bad"},
             {"key": "nyse", "exchange": "NYSE Group", "ok": False, "status": "pending", "text": "NYSE pending"}]
    p = read(["AKAN"], [], now=NOW, lists=FakeLists(views=views))
    assert p["fault_text"].startswith("⛔ SSR tags may be missing: Nasdaq bad; NYSE pending")
    p2 = read(["AKAN"], [day(D23, et(D23, 13, 56))], now=NOW, lists=FakeLists(views=views))
    assert p2["fault_text"] is None and p2["computed"]["ok"] is True


def test_NEGATIVE_a_failed_corp_source_alone_is_no_fault_line():
    class BadCorp(FakeCorp):
        def source_view(self, loaded, days, now_et):
            return {"key": "corp_actions", "exchange": None, "ok": False, "status": "failed", "text": "corp bad"}

    p = read(["AKAN"], [day(D23, et(D23, 13, 56))], now=NOW, corp=BadCorp())
    assert p["fault_text"] is None


# ═════════════════════════════════════════════ words
def _all_served(p):
    out = [p["note"], p.get("fault_text") or "", (p.get("computed") or {}).get("text") or ""]
    for it in p["items"].values():
        out += [it.get(k) or "" for k in ("chip", "short", "label", "title")]
    return out


def test_words_and_titles():
    p = golden_payload()
    for sym, it in p["items"].items():
        assert it["title"].endswith(RS.NOT_A_SIGNAL), sym
        if it["state"] == "on":
            assert SSR.TAG_WORDS in it["chip"] and SSR.TAG_WORDS in it["label"] and SSR.TAG_WORDS in it["title"]
            assert "  " not in it["title"]
    for t in _all_served(p) + [SSR.rules_line()]:
        assert not FORBIDDEN.search(t), t


def test_NEGATIVE_no_bare_10_90_0_9_outside_the_constant_block():
    tree = ast.parse(SRC)
    const_line = next(n.lineno for n in tree.body if isinstance(n, ast.Assign)
                      and any(getattr(t, "id", None) == "SSR_TRIGGER_DROP_PCT" for t in n.targets))
    for n in ast.walk(tree):
        if isinstance(n, ast.Constant) and not isinstance(n.value, bool) and isinstance(n.value, (int, float)):
            if n.value in (10, 90, 0.9):
                assert n.lineno == const_line, (n.lineno, n.value)


def test_NEGATIVE_the_percent_prints_through_the_constant(monkeypatch):
    monkeypatch.setattr(SSR, "SSR_TRIGGER_DROP_PCT", 15)
    for why in ("bars_disagree", "late_print", "computed_only"):
        t = SSR._why_text(why, None)
        assert "15%" in t and "10%" not in t, why
    assert "15%" in SSR.HONESTY_NOTE % SSR.SSR_TRIGGER_DROP_PCT
    line = SSR.rules_line()
    assert "15%" in line and "10%" not in line
    assert SSR.trigger_line(100.0) == 85.0
    docs = [trig(D23, "ZZP", "minute_bar", at="10:00", low=8.0, drop_pct=-20.0, prev_close=10.0)]
    t = read(["ZZP"], docs, now=NOW, lists=FakeLists(complete={D20}))["items"]["ZZP"]["title"]
    assert "15%" in t and "10%" not in t


def test_NEGATIVE_ssr_never_reads_the_tab_threshold_and_imports_no_trading_path():
    assert "THRESHOLD_PCT" not in SRC
    tree = ast.parse(SRC)
    mods = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            mods.append((n.module or "", [a.name for a in n.names]))
        elif isinstance(n, ast.Import):
            mods += [(a.name, []) for a in n.names]
    for mod, names in mods:
        parts = mod.split(".")
        assert not ({"push", "autopilot", "trading", "potential", "ledger", "tab"} & set(parts)), mod
        assert not any("lane" in p for p in parts), mod
        if mod == "chart_maps.gajjala.alerts":
            assert names == ["_closes"], names
    assert any(m == "chart_maps.gajjala.alerts" for m, _ in mods)


def test_module_top_imports_only_the_short_interest_siblings():
    tree = ast.parse(SRC)
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    sibs = {n.module for n in top if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("short_interest")}
    assert sibs == {"short_interest"}
    names = {a.name for n in top if isinstance(n, ast.ImportFrom) and n.module == "short_interest" for a in n.names}
    assert names == {"client", "read", "reg_sho", "borrow"}


def test_constants_cite_the_rule():
    assert SSR.SSR_TRIGGER_DROP_PCT == 10 and SSR.SSR_FOLLOWING_TRADING_DAYS == 1
    assert SSR.SSR_COMPUTED_UNTIL_LISTS_COMPLETE is True and "242.201" in SRC and "rule201faq" in SRC
    assert SSR.TAG_WORDS == "no shorting at the bid" and SSR.MAP_MAX_SYMBOLS == SR.MAP_MAX_SYMBOLS == 200


# ═════════════════════════════════════════════ route
def _route_client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(SAPI.router)
    return TestClient(app)


def test_route_serves_the_envelope(monkeypatch):
    seen = {}

    def fake(syms):
        seen["syms"] = syms
        return SSR.fault_payload(syms)

    monkeypatch.setattr(SSR, "payload", fake)
    r = _route_client().get("/short-interest/ssr?symbols=akan, gp ,,")
    assert r.status_code == 200 and r.json()["kind"] == SSR.KIND and seen["syms"] == ["akan", "gp"]


def test_NEGATIVE_a_raising_payload_serves_the_fault_payload_never_a_500(monkeypatch):
    monkeypatch.setattr(SSR, "payload", lambda syms: 1 / 0)
    r = _route_client().get("/short-interest/ssr?symbols=AKAN")
    j = r.json()
    assert r.status_code == 200 and j["status"] == "failed" and j["states"] == {"AKAN": "unknown"}


def test_NEGATIVE_empty_symbols_is_empty_items_no_error(monkeypatch):
    real = SSR.payload
    monkeypatch.setattr(SSR, "payload", lambda syms: real(syms, db=FakeDB(FakeColl()), now=NOW, lists=FakeLists(),
                                                          corp=FakeCorp()))
    j = _route_client().get("/short-interest/ssr?symbols=").json()
    assert j["items"] == {} and j["asked"] == 0 and j["status"] == "ok"


def test_201_symbols_read_the_first_200():
    syms = ["ZZ%03d" % i for i in range(201)]
    p = read(syms, [], now=NOW)
    assert p["asked"] == 200 and len(p["states"]) == 200 and "ZZ200" not in p["states"]


# ═════════════════════════════════════════════ ℹ️
def test_rules_line_is_the_last_alert_and_the_picks_are_untouched():
    sec = SR.rules_section()
    assert sec["alerts"][-1] == SSR.rules_line()
    assert len(sec["picks"]) == 8 and sec["picks"][-1] == RS.rules_pick()
    line = SSR.rules_line()
    assert "UNMEASURED" in line and "Nasdaq and NYSE Group" in line and "dividend or split day" in line


def test_NEGATIVE_a_raising_rules_line_leaves_alerts_as_they_were(monkeypatch):
    monkeypatch.setattr(SSR, "rules_line", lambda: 1 / 0)
    sec = SR.rules_section()
    assert sec["alerts"] == ["Pushes nothing, gates nothing, sorts nothing and enters no lane."]


# ═════════════════════════════════════════════ golden
GOLDEN_NOW = "2026-11-23T14:00:00-05:00"
GOLDEN_SYMBOLS = ["AKAN", "GP", "GIPR", "PXED", "ZZNP", "ZZCO", "AAPL"]


def golden_docs():
    at = et(D23, 13, 56)
    return [
        trig(D23, "AKAN", "minute_bar", at="09:30", low=3.68, drop_pct=-13.0, prev_close=4.23),   # §1.3 measured
        trig(D23, "GP", "minute_bar", at="13:43", low=2.50, drop_pct=-11.0, prev_close=2.81),     # §1.3 measured
        trig(D23, "PXED", seen_at="10:05", prev_close=19.66, low=17.39, drop_pct=-11.5),           # §1.3 measured
        trig(D20, "ZZCO", seen_at="11:00", prev_close=5.0, low=4.4, drop_pct=-12.0),               # SYNTHETIC
        day(D23, at, {
            "AKAN": entry("on", at, pc=4.23, lo=3.68),
            "GP": entry("on", at, pc=2.81, lo=2.50),
            "GIPR": entry("off", at, pc=None, lo=None),
            "AAPL": entry("off", at, pc=None, lo=345.442189),       # §1.3 day low; prev not measured → None
            "ZZCO": entry("off", at),
            "ZZNP": entry("unknown", at, why="no_prior_close", by="snapshot"),
        }),
    ]


def golden_payload():
    lists = FakeLists(rows=[nasdaq_row("GP", "2026-11-20", "09:45:36"),            # Nasdaq 11/20 file, real rows
                            nasdaq_row("GIPR", "2026-11-20", "11:44:16")],
                      complete={D20})
    corp = FakeCorp({"2026-11-23": {"PXED": "dividend", "TOPP": "split"}, "2026-11-20": {}})
    return read(GOLDEN_SYMBOLS, golden_docs(), now=datetime.fromisoformat(GOLDEN_NOW), lists=lists, corp=corp)


def test_golden_contains_every_state():
    p = golden_payload()
    assert p["states"] == {"AKAN": "on", "GP": "on", "GIPR": "on", "PXED": "unknown", "ZZNP": "unknown",
                           "ZZCO": "unknown", "AAPL": "off"}
    assert p["whys"] == {"PXED": "corp_action", "ZZNP": "no_prior_close", "ZZCO": "computed_only"}
    assert set(p["items"]) == {"AKAN", "GP", "GIPR", "PXED", "ZZNP"}
    assert p["items"]["GIPR"]["source"] == "official" and p["items"]["GIPR"]["through"] == "2026-11-23"
    assert p["items"]["AKAN"]["chip"].endswith(" · computed") and p["items"]["AKAN"]["through"] == "2026-11-24"
    assert p["items"]["GP"]["retriggered"] is True
    assert p["items"]["PXED"]["label"] == "⛔ SSR not read" and p["items"]["PXED"]["chip"] is None
    assert p["session"]["in_play"] == ["2026-11-23", "2026-11-20"]


def test_golden_equals_the_fixture():
    want = json.loads(FIXTURE.read_text())
    assert want["now"] == GOLDEN_NOW and want["symbols"] == GOLDEN_SYMBOLS
    assert json.loads(json.dumps(golden_payload())) == want["payload"]


# ═════════════════════════════════════════════ scripts/ssr_agreement.py (read-only)
def test_agreement_script_prints_both_off_diagonals_and_never_writes(monkeypatch, capsys):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import ssr_agreement as AG
    from short_interest import client as SIC
    docs = [{"_id": "list|nasdaq|2026-11-23", "kind": "list", "stamp": "20261123163004", "n": 2,
             "rows": [["ZZA", "2026-11-23", "09:31:00", "Q"], ["ZZOLD", "2026-11-20", "10:00:00", "Q"]]},
            {"_id": "list|nasdaq|2026-11-24", "kind": "list", "stamp": "20261124041515", "n": 1,
             "rows": [["ZZB", "2026-11-23", "15:58:00", "R"]]},
            {"_id": "list|nyse|2026-11-23", "kind": "list", "stamp": None, "n": 1,
             "rows": [["BRK B", "2026-11-23", "10:00:00", "NYSE", "2026-11-25"]]},
            trig(D23, "ZZA", seen_at="10:00", prev_close=2.0, low=1.0, drop_pct=-50.0),
            trig(D23, "BRK-B", "minute_bar", at="10:00", low=450.0, drop_pct=-11.0, prev_close=505.0),
            trig(D23, "PXED", seen_at="10:05", prev_close=19.66, low=17.39, drop_pct=-11.5),
            trig(D23, "ZZV", seen_at="10:05", prev_close=2.0, low=1.0, drop_pct=-50.0, void="bars_disagree"),
            judged(D23, {"AAPL"}, {"ZZB": "late_print"}),
            {"_id": "corp|2026-11-23", "kind": "corp", "dividends": [["PXED", 2.36, "USD"]], "splits": []}]
    coll = FakeColl(docs)
    coll.update_one = coll.insert_many = lambda *a, **k: (_ for _ in ()).throw(AssertionError("write"))
    monkeypatch.setattr(SIC, "_get_db", lambda: {"ssr_rule_201": coll})
    assert AG.main(["x", "2026-11-23"]) == 0
    out = capsys.readouterr().out
    assert "| 3 | 3 | 2 | 1 | 1 |" in out
    assert "official-only (recall misses, 1): ZZB" in out
    assert "computed-only, dividend or split names (1): PXED" in out and "computed-only, the rest (0)" in out
    assert "void docs (bars_disagree, 1): ZZV" in out and "late_print names (1): ZZB" in out
    assert "recall" in out and "precision" in out and "95% CI" in out and "complete: yes" in out
    assert AG.main(["x"]) == 2


def _agreement_out(monkeypatch, capsys, nyse_rows, trigs, corp=None):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import ssr_agreement as AG
    from short_interest import client as SIC
    docs = [{"_id": "list|nasdaq|2026-11-24", "kind": "list", "stamp": "20261124041515", "n": 0, "rows": []},
            {"_id": "list|nyse|2026-11-23", "kind": "list", "stamp": None, "n": len(nyse_rows),
             "rows": [[s, "2026-11-23", "10:00:00", "NYSE", "2026-11-25"] for s in nyse_rows]}]
    docs += [trig(D23, s, seen_at="10:00", prev_close=2.0, low=1.7, drop_pct=-15.0) for s in trigs]
    if corp is not None:
        docs.append(dict({"_id": "corp|2026-11-23", "kind": "corp"}, **corp))
    coll = FakeColl(docs)
    coll.update_one = coll.insert_many = lambda *a, **k: (_ for _ in ()).throw(AssertionError("write"))
    monkeypatch.setattr(SIC, "_get_db", lambda: {"ssr_rule_201": coll})
    assert AG.main(["x", "2026-11-23"]) == 0
    return capsys.readouterr().out


def test_agreement_matches_the_snapshot_dot_spelling_to_the_list_name(monkeypatch, capsys):
    """REFIX 11-23: trig docs carry the snapshot spelling ('BIII.WS'); the list key is 'BIII-WS'. One name, a hit."""
    out = _agreement_out(monkeypatch, capsys, ["BIII WS", "TONT WS", "NMZ RT", "BRK B", "AKAN"],
                         ["BIII.WS", "TONT.WS", "NMZ-RT", "BRK.B", "AKAN"])
    assert "| 5 | 5 | 5 | 0 | 0 |" in out
    assert "recall    (official names the computed read caught): 5 / 5 = 100.0%" in out
    assert "precision (computed names on an official list):      5 / 5 = 100.0%" in out
    assert "official-only (recall misses, 0): —" in out and "computed-only, the rest (0): —" in out
    assert "| plain | 1 | 1 | 1 | 0 | 0 |" in out and "| suffixed | 4 | 4 | 4 | 0 | 0 |" in out
    assert "plain    recall 1 / 1 = 100.0%" in out and "suffixed recall 4 / 4 = 100.0%" in out


def test_agreement_counts_two_spellings_of_one_name_once(monkeypatch, capsys):
    out = _agreement_out(monkeypatch, capsys, ["BIII WS"], ["BIII.WS", "BIII-WS"])
    assert "| 1 | 1 | 1 | 0 | 0 |" in out and "(2 live docs)" in out
    assert "precision (computed names on an official list):      1 / 1 = 100.0%" in out


def test_agreement_negative_a_different_name_never_matches_on_spelling(monkeypatch, capsys):
    """NEGATIVE: the common 'BIII' is not the warrant 'BIII WS'; 'BIIIWS' (no separator) is not either; a dotted
    computed name with no list row stays computed-only; and no preferred mapping is invented ('AHTPD' ≠ 'AHT PRD')."""
    out = _agreement_out(monkeypatch, capsys, ["BIII WS", "AHT PRD"], ["BIII", "BIIIWS", "ZZQ.WS", "AHTPD"])
    assert "| 2 | 4 | 0 | 2 | 4 |" in out
    assert "official-only (recall misses, 2): AHT-PRD BIII-WS" in out
    assert "computed-only, the rest (4): AHTPD BIII BIIIWS ZZQ.WS" in out
    assert "| plain | 0 | 3 | 0 | 0 | 3 |" in out and "| suffixed | 2 | 1 | 0 | 2 | 1 |" in out
    assert "plain    recall n/a (n = 0)" in out


def test_agreement_dividend_split_names_match_on_any_spelling_and_only_those(monkeypatch, capsys):
    out = _agreement_out(monkeypatch, capsys, ["AKAN"], ["AKAN", "BRK.B", "ZZW.WS", "PXED"],
                         corp={"dividends": [["BRK-B", 1.0, "USD"]], "splits": [["ZZW WS", 1, 10]]})
    assert "computed-only, dividend or split names (2): BRK.B ZZW.WS" in out
    assert "computed-only, the rest (1): PXED" in out
