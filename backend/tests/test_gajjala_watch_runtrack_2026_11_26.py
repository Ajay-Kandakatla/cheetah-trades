"""📅 Runners — the nightly record (2026-11-26, spec watchrun rev 2 §3.4, WP-2 `be-track`). Negatives mandatory.
Hermetic: an in-memory collection, injected daily frames, the store seams patched (`_rings`, `_trackers`, `_grades`)."""
from __future__ import annotations

import inspect
import json
import math
import sys
import types
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import runtrack as RT

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
RUN = "2026-11-13"                      # a Friday; its 10-session window ends 2026-11-27 (11-26 is a market holiday)
WIN = ["2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-23",
       "2026-11-24", "2026-11-25", "2026-11-27"]


def night(iso: str) -> datetime:
    """The 20:15 ET nightly of that session, as aware UTC."""
    d = date.fromisoformat(iso)
    return datetime(d.year, d.month, d.day, 20, 15, tzinfo=ET).astimezone(UTC)


# ── fakes ────────────────────────────────────────────────────────────────────────────────────────────────────────
class Coll:
    def __init__(self, docs=None, fail_find=False, fail_write=False):
        self.docs = {d["_id"]: dict(d) for d in docs or []}
        self.fail_find, self.fail_write = fail_find, fail_write
        self.writes = []

    def find(self, q=None, proj=None):
        if self.fail_find:
            raise RuntimeError("down")
        q = q or {}
        return [dict(d) for d in self.docs.values() if all(d.get(k) == v for k, v in q.items())]

    def replace_one(self, flt, doc, upsert=False):
        if self.fail_write:
            raise RuntimeError("down")
        self.writes.append(flt["_id"])
        self.docs[flt["_id"]] = dict(doc)


def frame(bars: dict, prior: int = 0, prior_px: float = 1.0, prior_vol: float = 1000.0) -> pd.DataFrame:
    """A daily frame: `prior` business days before the first bar (flat at prior_px), then `bars` {iso: (o, h, l, c, v)}."""
    first = min(date.fromisoformat(k) for k in bars)
    rows, idx = [], []
    d = first
    pre = []
    while len(pre) < prior:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            pre.append(d)
    for p in sorted(pre):
        idx.append(pd.Timestamp(p))
        rows.append((prior_px, prior_px, prior_px, prior_px, prior_vol))
    for k in sorted(bars):
        idx.append(pd.Timestamp(k))
        rows.append(bars[k])
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx), columns=["open", "high", "low", "close", "volume"])


def day_run(iso=RUN, pct=176.0, high=5.5, peak="11:20", reg=4.0, **kw):
    r = {"date": iso, "rule": "day", "run_pct": pct, "prev_close": 2.0, "high": high, "peak_et": peak,
         "pm_high_pct": None, "reg_close": reg, "timing": "first_hour"}
    r.update(kw)
    return r


def aplus_run(iso=RUN, pct=34.0, high_px=1.34, high_et="11:00", reg=1.2, ring_id="GG:R1", ring_date=None):
    return {"date": iso, "rule": "aplus", "run_pct": pct, "trigger": 1.0, "high_px": high_px, "high_et": high_et,
            "from_et": "09:45", "to_et": "20:00", "ring_id": ring_id, "ring_date": ring_date or iso,
            "ring_at_et": "09:40", "setup": "reversal_squeeze", "page": "gajjala", "fetched": iso, "reg_close": reg,
            "day": None}


def entry(sym, *runs, reading="after_aplus"):
    last = runs[-1]
    return {"symbol": sym, "rule": last["rule"], "run_day": last["date"], "first_run_day": runs[0]["date"],
            "runs": list(runs), "reading": reading}


def rdoc(entries=(), removed=()):
    return {"_id": "runners", "entries": list(entries), "removed": list(removed)}


def removed(sym, reason, *runs, session="2026-11-16"):
    return {"symbol": sym, "reason": reason, "session": session, "text": "", "entry": entry(sym, *runs)}


def full_bars(run_bar=(2.0, 4.5, 2.0, 4.0, 9e6), after=None, skip=()):
    """Run-day bar + a bar on every later window session (or `after` {iso: bar}), minus `skip`."""
    out = {RUN: run_bar}
    for i, iso in enumerate(WIN[1:], start=1):
        if iso in skip:
            continue
        out[iso] = (after or {}).get(iso, (4.0, 4.4, 3.6, 4.0 + i * 0.01, 1e6))
    return out


@pytest.fixture
def seams(monkeypatch):
    box = {"rings": [], "trackers": {}, "grades": {}, "ring_calls": [], "tracker_calls": []}

    def rings(dates, stores):
        box["ring_calls"].append(sorted(dates))
        if box["rings"] is None:
            raise RuntimeError("ledger down")
        return list(box["rings"])

    def trackers(iso, stores):
        box["tracker_calls"].append(iso)
        v = box["trackers"].get(iso, [])
        return None if v is None else list(v)

    monkeypatch.setattr(RT, "_rings", rings)
    monkeypatch.setattr(RT, "_trackers", trackers)
    monkeypatch.setattr(RT, "_grades", lambda dates, stores: box["grades"])
    return box


def run_night(iso, coll, seats, frames=None, fail=(), calls=None, **kw):
    calls = calls if calls is not None else []

    def daily(sym, *, now=None):
        calls.append((sym, now))
        if sym in fail:
            return None
        return (frames or {}).get(sym)
    return RT.nightly(night(iso), coll=coll, seats=seats, stores={}, daily=daily, **kw)


# ── the window ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_window_is_ten_market_sessions_the_run_day_first_and_skips_the_holiday():
    assert RT.window_of(RUN) == WIN and len(WIN) == C.RUNNERS_KEEP_SESSIONS == RT.KEEP
    assert "2026-11-26" not in RT.window_of(RUN)


def test_NEGATIVE_window_of_junk_is_empty():
    assert RT.window_of("not a date") == [] and RT.window_of(None) == []


def test_recorded_session_is_tonight_after_the_close_and_NEGATIVE_the_day_before_while_it_trades():
    assert RT.recorded_session(night("2026-11-25")) == date(2026, 11, 25)
    noon = datetime(2026, 11, 25, 12, 0, tzinfo=ET).astimezone(UTC)
    assert RT.recorded_session(noon) == date(2026, 11, 24)
    thanksgiving = datetime(2026, 11, 26, 21, 0, tzinfo=ET).astimezone(UTC)
    assert RT.recorded_session(thanksgiving) == date(2026, 11, 25)


# ── the base [C6] ────────────────────────────────────────────────────────────────────────────────────────────────
def test_POM_shaped_late_peak_is_based_on_the_runs_own_high_and_close_vs_run_close_is_none_on_every_row():
    seat = day_run(pct=75.0, high=3.5, peak="19:45", reg=2.4)          # the regular close 2.40 came before the run
    bars = full_bars(run_bar=(2.0, 2.5, 2.0, 2.4, 5e6), after={WIN[1]: (3.0, 3.2, 2.9, 3.0, 4e6)})
    df = frame(bars)
    b = RT.base_of(seat, df, RUN)
    assert b["kind"] == "run_high" and b["price"] == 3.5 and b["peak_late"] is True and b["adjusted"] is False
    rows = RT.session_rows(df, RUN, WIN, WIN[-1], b)
    assert len(rows) == 10 and all(r["close_vs_run_close_pct"] is None for r in rows)
    d2 = rows[1]
    assert d2["close"] == 3.0 and d2["close"] > 2.4                    # far above the run-day regular close …
    assert d2["close_vs_run_high_pct"] == round((3.0 / 3.5 - 1) * 100, 2) < 0   # … and still under the run's high


def test_BGLC_shaped_regular_hours_peak_is_based_on_the_frames_run_day_close_and_high():
    seat = day_run(pct=176.0, high=5.52, peak="11:20", reg=4.0)
    df = frame(full_bars(run_bar=(2.0, 4.5, 2.0, 4.0, 9e6), after={WIN[1]: (4.0, 4.8, 3.9, 4.4, 2e6)}))
    b = RT.base_of(seat, df, RUN)
    assert b["kind"] == "run_close" and b["price"] == 4.0 and b["run_high"] == 4.5 and b["peak_late"] is False
    d2 = RT.session_rows(df, RUN, WIN, WIN[1], b)[1]
    assert d2["close_vs_run_close_pct"] == 10.0                        # 4.4 vs the frame's 4.0
    assert d2["close_vs_run_high_pct"] == round((4.4 / 4.5 - 1) * 100, 2)   # vs the FRAME's high 4.5, never the seat's 5.52


def test_NEGATIVE_a_late_peak_on_a_rebased_frame_or_with_no_reg_close_has_no_base():
    df = frame(full_bars(run_bar=(18.0, 22.5, 18.0, 21.6, 5e5)))       # 1-for-9: 2.40 → 21.60
    b = RT.base_of(day_run(peak="19:45", high=3.5, reg=2.4), df, RUN)
    assert b["kind"] == "none" and b["price"] is None and b["adjusted"] is True and "another scale" in b["note"]
    rows = RT.session_rows(df, RUN, WIN, WIN[-1], b)
    assert all(r["close_vs_run_close_pct"] is None and r["close_vs_run_high_pct"] is None for r in rows)
    b2 = RT.base_of(day_run(peak="19:45", high=3.5, reg=None), df, RUN)
    assert b2["kind"] == "none" and b2["adjusted"] is None and "no regular close" in b2["note"]


def test_NEGATIVE_no_run_day_bar_or_no_peak_time_has_no_base():
    df = frame({WIN[1]: (4.0, 4.4, 3.6, 4.1, 1e6)})
    b = RT.base_of(day_run(peak="11:20"), df, RUN)
    assert b["kind"] == "none" and "no bar of the run day" in b["note"]
    b2 = RT.base_of(day_run(peak=None), frame(full_bars()), RUN)
    assert b2["kind"] == "none" and "peak time" in b2["note"]


def test_peak_exactly_1600_is_late_and_NEGATIVE_1559_is_not():
    df = frame(full_bars(run_bar=(2.0, 4.5, 2.0, 4.0, 9e6)))
    assert RT.base_of(day_run(peak="16:00", reg=4.0), df, RUN)["peak_late"] is True
    assert RT.base_of(day_run(peak="16:00", reg=4.0), df, RUN)["kind"] == "run_high"
    assert RT.base_of(day_run(peak="15:59", reg=4.0), df, RUN)["peak_late"] is False
    assert RT.base_of(day_run(peak="15:59", reg=4.0), df, RUN)["kind"] == "run_close"


def test_aplus_seat_reads_high_px_and_high_et():
    df = frame(full_bars(run_bar=(1.0, 1.3, 1.0, 1.2, 9e6)))
    b = RT.base_of(aplus_run(high_px=1.34, high_et="17:05", reg=1.2), df, RUN)
    assert b["kind"] == "run_high" and b["seat_high"] == 1.34 and b["peak_et"] == "17:05"


def test_NEGATIVE_a_rebased_frame_changes_no_ratio_of_a_run_close_doc():
    seat = day_run(peak="11:20", reg=4.0)
    bars = full_bars()
    k = 9.0
    scaled = {d: (o * k, h * k, lo * k, c * k, v / k) for d, (o, h, lo, c, v) in bars.items()}
    r1 = RT.session_rows(frame(bars), RUN, WIN, WIN[-1], RT.base_of(seat, frame(bars), RUN))
    r2 = RT.session_rows(frame(scaled), RUN, WIN, WIN[-1], RT.base_of(seat, frame(scaled), RUN))
    for a, b in zip(r1, r2):
        for key in ("change_pct", "high_pct", "low_pct", "close_vs_run_close_pct", "close_vs_run_high_pct"):
            assert a[key] == pytest.approx(b[key], abs=0.011), key


# ── rows ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_session_with_no_bar_is_no_bar_never_a_zero():
    df = frame(full_bars(skip=(WIN[3],)))
    rows = RT.session_rows(df, RUN, WIN, WIN[-1], RT.base_of(day_run(), df, RUN))
    r = rows[3]
    assert r["state"] == "no_bar" and r["date"] == WIN[3] and r["day_n"] == 4
    assert all(r[k] is None for k in ("close", "high", "low", "volume", "change_pct", "close_vs_run_close_pct",
                                      "close_vs_run_high_pct", "vol_x"))
    assert rows[4]["state"] == "ok"


def test_rows_stop_at_tonights_session_and_NEGATIVE_never_past_it():
    df = frame(full_bars())
    rows = RT.session_rows(df, RUN, WIN, WIN[4], RT.base_of(day_run(), df, RUN))
    assert [r["date"] for r in rows] == WIN[:5]


def test_NEGATIVE_fewer_than_50_sessions_is_vol_x_none_and_50_measures_it():
    short = frame(full_bars(), prior=10)
    rows = RT.session_rows(short, RUN, WIN, WIN[1], RT.base_of(day_run(), short, RUN))
    assert rows[1]["avg_vol_50"] is None and rows[1]["vol_x"] is None
    long_ = frame(full_bars(), prior=60, prior_vol=1000.0)
    r = RT.session_rows(long_, RUN, WIN, WIN[0], RT.base_of(day_run(), long_, RUN))[0]
    assert r["avg_vol_50"] == 1000.0 and r["vol_x"] == 9000.0


def test_reads_are_the_stored_times_never_now_and_NEGATIVE_none_is_empty():
    first_seen = datetime(2026, 11, 16, 14, 5, tzinfo=UTC)               # 09:05 ET
    armed = datetime(2026, 11, 16, 15, 31, tzinfo=UTC)                   # 10:31 ET
    tdoc = {"_id": "2026-11-16|XYZ|reversal_squeeze", "symbol": "XYZ", "date": "2026-11-16",
            "setup": "reversal_squeeze", "first_seen": first_seen,
            "state_path": [{"state": RT.GC.POTENTIAL_STATE, "kind": RT.GC.POTENTIAL_KINDS[0], "at": armed}]}
    ring = {"symbol": "XYZ", "date": "2026-11-16", "setup": "reversal_squeeze", "at_et": "11:02"}
    got = RT.reads_of("XYZ", "2026-11-16", [tdoc], [ring])
    assert [(e["kind"], e["at_et"], e["rs"]) for e in got] == [("potential", "09:05", True), ("armed", "10:31", True),
                                                               ("aplus", "11:02", True)]
    assert RT.reads_of("XYZ", "2026-11-16", [], []) == []
    assert RT.reads_of("XYZ", "2026-11-16", [dict(tdoc, symbol="ABC")], [dict(ring, date="2026-11-17")]) == []
    assert RT._reads_text([]) == RT.NO_READ and RT._reads_text(None) == RT.READS_FAULT


def test_NEGATIVE_no_served_word_says_calm_pullback_or_bounce():
    words = []

    def walk(v):
        if isinstance(v, str):
            words.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
    for name, v in vars(RT).items():
        if name.isupper():
            walk(v)
    assert words and not [w for w in words if any(b in w.lower() for b in ("calm", "pullback", "bounce"))]


# ── the record [C5] ──────────────────────────────────────────────────────────────────────────────────────────────
def test_a_blocked_run_opens_a_doc_listed_false_and_is_recorded_to_day_10(seams):
    coll = Coll()
    seats = rdoc(removed=[removed("DOGZ", "blocked", day_run(), session=RUN)])
    frames = {"DOGZ": frame(full_bars())}
    for iso in WIN:
        run_night(iso, coll, seats, frames)
    d = coll.docs[f"{RUN}|DOGZ"]
    assert d["listed"] is False and d["seat_end"]["reason"] == "blocked"
    assert d["state"] == "closed" and len(d["sessions"]) == 10 and d["closed"]["listed"] is False


def test_a_dismissed_and_an_aged_name_are_recorded_to_day_10(seams):
    coll = Coll()
    seats = rdoc(removed=[removed("AAA", "dismissed", day_run()), removed("BBB", "aged", day_run())])
    frames = {"AAA": frame(full_bars()), "BBB": frame(full_bars())}
    for iso in WIN:
        run_night(iso, coll, seats, frames)
    for s in ("AAA", "BBB"):
        d = coll.docs[f"{RUN}|{s}"]
        assert d["listed"] is True and d["state"] == "closed" and d["sessions"][-1]["day_n"] == 10


def test_NEGATIVE_a_removed_entry_with_an_unknown_reason_is_not_recorded(seams):
    coll = Coll()
    run_night(RUN, coll, rdoc(removed=[removed("CCC", "not_a_reason", day_run())]), {"CCC": frame(full_bars())})
    assert coll.docs == {}


def test_a_second_run_marks_another_run_on_the_first_doc_and_opens_its_own(seams):
    coll = Coll()
    second = day_run(iso=WIN[3], peak="10:00", reg=4.0)
    frames = {"NCPL": frame(full_bars())}
    run_night(WIN[1], coll, rdoc([entry("NCPL", day_run())]), frames)
    out = run_night(WIN[3], coll, rdoc([entry("NCPL", day_run(), second)]), frames)
    assert out["opened"] == 1
    first = coll.docs[f"{RUN}|NCPL"]
    assert first["another_run"] == {"date": WIN[3], "rule": "day"}
    assert coll.docs[f"{WIN[3]}|NCPL"]["window"][0] == WIN[3]


def test_NEGATIVE_a_run_dated_after_tonight_is_not_opened(seams):
    coll = Coll()
    run_night(RUN, coll, rdoc([entry("ZZZ", day_run(iso=WIN[2]))]), {"ZZZ": frame(full_bars())})
    assert coll.docs == {}


def test_NEGATIVE_seats_unreadable_writes_nothing(seams, monkeypatch):
    coll = Coll()
    monkeypatch.setattr(RT, "_read_seats", lambda db: None)
    out = RT.nightly(night(RUN), coll=coll, stores={}, daily=lambda s, now=None: frame(full_bars()))
    assert out["faults"] == ["seats"] and coll.writes == [] and out["opened"] == 0


def test_NEGATIVE_no_record_handle_or_a_faulted_record_read_writes_nothing(seams, monkeypatch):
    monkeypatch.setattr(RT.CO, "runtrack_coll", lambda db=None: None)
    assert RT.nightly(night(RUN), seats=rdoc([entry("A", day_run())]))["faults"] == ["record"]
    bad = Coll(fail_find=True)
    out = run_night(RUN, bad, rdoc([entry("A", day_run())]), {"A": frame(full_bars())})
    assert out["faults"] == ["record"] and bad.writes == []


def test_NEGATIVE_a_second_run_the_same_night_writes_nothing_new(seams):
    coll = Coll()
    seats = rdoc([entry("XYZ", day_run())])
    frames = {"XYZ": frame(full_bars())}
    run_night(WIN[2], coll, seats, frames)
    n = len(coll.writes)
    out = run_night(WIN[2], coll, seats, frames)
    assert out["opened"] == 0 and out["updated"] == 0 and len(coll.writes) == n
    assert run_night(WIN[2], coll, seats, frames, dry=True)["writes"] == []


def test_NEGATIVE_dry_run_writes_nothing():
    coll = Coll()
    out = RT.nightly(night(RUN), coll=coll, seats=rdoc([entry("XYZ", day_run())]), stores={},
                     daily=lambda s, now=None: frame(full_bars()), dry=True)
    assert out["writes"] == [f"{RUN}|XYZ"] and coll.writes == [] and coll.docs == {}


def test_the_daily_read_asks_for_tonights_bar_by_the_next_midnight_and_without_the_cache(seams, monkeypatch):
    calls = []
    run_night(WIN[1], Coll(), rdoc([entry("XYZ", day_run())]), {"XYZ": frame(full_bars())}, calls=calls)
    assert calls == [("XYZ", datetime(2026, 11, 17, 0, 0))]
    seen = {}
    import sepa.prices as P
    monkeypatch.setattr(P, "closed_daily_frame", lambda sym, **kw: seen.update(kw, sym=sym))
    RT._default_daily("XYZ", now=datetime(2026, 11, 17))
    assert seen == {"sym": "XYZ", "now": datetime(2026, 11, 17), "use_cache": False}


# ── closing [C7] ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_doc_closes_only_when_its_window_is_due(seams):
    coll = Coll()
    seats = rdoc([entry("XYZ", day_run())])
    for iso in WIN[:-1]:
        out = run_night(iso, coll, seats, {"XYZ": frame(full_bars())})
        assert out["closed"] == 0 and coll.docs[f"{RUN}|XYZ"]["state"] == "open"
    out = run_night(WIN[-1], coll, seats, {"XYZ": frame(full_bars())})
    d = coll.docs[f"{RUN}|XYZ"]
    assert out["closed"] == 1 and d["state"] == "closed" and d["closed"]["closed_by"] == "window"
    assert d["closed"]["no_price"] is False and d["closed"]["sessions_watched"] == 9


def test_NEGATIVE_a_read_that_fails_every_night_closes_on_the_calendar_and_is_never_fetched_again(seams):
    coll = Coll()
    seats = rdoc([entry("DEAD", day_run())])
    calls = []
    for iso in WIN:
        run_night(iso, coll, seats, fail=("DEAD",), calls=calls)
        assert coll.docs[f"{RUN}|DEAD"]["state"] == "open"
    out = run_night("2026-11-30", coll, seats, fail=("DEAD",), calls=calls)
    d = coll.docs[f"{RUN}|DEAD"]
    assert out["closed_calendar"] == 1 and d["state"] == "closed" and d["closed"]["closed_by"] == "calendar"
    assert [r["date"] for r in d["sessions"]] == WIN and all(r["state"] == "no_bar" for r in d["sessions"])
    assert d["closed"]["no_price"] is True and d["base"]["kind"] == "none"
    n = len(calls)
    assert n == len(WIN) + 1                                            # KEEP + 1 fetches, ever
    run_night("2026-12-01", coll, seats, fail=("DEAD",), calls=calls)
    assert len(calls) == n


def test_a_read_that_fails_only_on_the_closing_night_closes_by_the_window_the_next_night(seams):
    coll = Coll()
    seats = rdoc([entry("XYZ", day_run())])
    for iso in WIN[:-1]:
        run_night(iso, coll, seats, {"XYZ": frame(full_bars())})
    out = run_night(WIN[-1], coll, seats, {"XYZ": frame(full_bars())}, fail=("XYZ",))
    assert out["closed"] == 0 and out["failed"] == 1 and coll.docs[f"{RUN}|XYZ"]["state"] == "open"
    run_night("2026-11-30", coll, seats, {"XYZ": frame(full_bars())})
    d = coll.docs[f"{RUN}|XYZ"]
    assert d["closed"]["closed_by"] == "window" and len(d["sessions"]) == 10
    assert all(r["state"] == "ok" for r in d["sessions"])


def test_a_calendar_close_keeps_the_stored_rows_and_fills_the_rest_no_bar(seams):
    coll = Coll()
    seats = rdoc([entry("XYZ", day_run())])
    run_night(WIN[2], coll, seats, {"XYZ": frame(full_bars())})
    run_night("2026-11-30", coll, seats, fail=("XYZ",))
    d = coll.docs[f"{RUN}|XYZ"]
    assert [r["state"] for r in d["sessions"]] == ["ok"] * 3 + ["no_bar"] * 7
    assert d["closed"]["closed_by"] == "calendar" and d["closed"]["no_price"] is False


# ── the A+ rings and the counts [C6] ─────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_ring_on_the_run_day_is_listed_but_never_rang_A_later_and_a_later_ring_is(seams):
    coll = Coll()
    seats = rdoc([entry("AIMD", aplus_run(ring_id="GG:R1"))])
    seams["rings"] = [{"id": "GG:R1", "page": "gajjala", "date": RUN, "symbol": "AIMD", "setup": "reversal_squeeze",
                       "at_et": "09:40", "play_day": RUN}]
    seams["grades"] = {"GG:R1": "win"}
    for iso in WIN:
        run_night(iso, coll, seats, {"AIMD": frame(full_bars(run_bar=(1.0, 1.3, 1.0, 1.2, 9e6)))})
    d = coll.docs[f"{RUN}|AIMD"]
    assert d["aplus"] == [{"id": "GG:R1", "page": "gajjala", "date": RUN, "setup": "reversal_squeeze", "at_et": "09:40",
                           "play_day": RUN, "outcome": "win", "from_trigger_pct": 34.0, "passed": True,
                           "after_run": False}]
    assert d["closed"]["aplus_later"] is False
    coll2 = Coll()
    seams["rings"].append({"id": "GG:R2", "page": "gajjala", "date": WIN[4], "symbol": "AIMD", "setup": "vcp",
                           "at_et": "10:10", "play_day": WIN[4]})
    for iso in WIN:
        run_night(iso, coll2, seats, {"AIMD": frame(full_bars(run_bar=(1.0, 1.3, 1.0, 1.2, 9e6)))})
    d2 = coll2.docs[f"{RUN}|AIMD"]
    assert [a["after_run"] for a in d2["aplus"]] == [False, True] and d2["aplus"][1]["from_trigger_pct"] is None
    assert d2["closed"]["aplus_later"] is True
    assert d2["sessions"][4]["reads"] == [{"kind": "aplus", "setup": "vcp", "rs": False, "at_et": "10:10"}]


def test_NEGATIVE_a_ring_fault_keeps_the_stored_rings_and_a_tracker_fault_is_not_no_read(seams):
    coll = Coll()
    seats = rdoc([entry("AIMD", day_run())])
    seams["rings"] = [{"id": "GG:R9", "page": "gajjala", "date": WIN[1], "symbol": "AIMD", "setup": "vcp",
                       "at_et": "10:00", "play_day": WIN[1]}]
    run_night(WIN[1], coll, seats, {"AIMD": frame(full_bars())})
    assert len(coll.docs[f"{RUN}|AIMD"]["aplus"]) == 1
    seams["rings"] = None
    seams["trackers"] = {WIN[2]: None}
    out = run_night(WIN[2], coll, seats, {"AIMD": frame(full_bars())})
    d = coll.docs[f"{RUN}|AIMD"]
    assert "aplus" in out["faults"] and "trackers" in out["faults"] and len(d["aplus"]) == 1
    assert d["sessions"][2]["reads"] is None
    assert RT._session_row(d["sessions"][2])["cells"]["reads"] == RT.READS_FAULT


def test_rings_are_asked_over_the_window_and_the_day_before_the_run(seams):
    run_night(WIN[1], Coll(), rdoc([entry("XYZ", day_run())]), {"XYZ": frame(full_bars())})
    assert seams["ring_calls"] == [["2026-11-12", RUN, WIN[1]]]


def test_the_default_ring_reader_is_runseat_aplus_rings(monkeypatch):
    import chart_maps.gajjala_watch as pkg
    seen = {}
    fake = types.ModuleType("chart_maps.gajjala_watch.runseat")
    fake.aplus_rings = lambda dates, *, stores: seen.update(dates=dates, stores=stores) or ["ring"]
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.runseat", fake)
    monkeypatch.setattr(pkg, "runseat", fake, raising=False)
    assert RT._rings({"2026-11-16", "2026-11-13"}, {"k": 1}) == ["ring"]
    assert seen == {"dates": ["2026-11-13", "2026-11-16"], "stores": {"k": 1}}


def _closed(rule, base_kind, *, last_close=None, last_high=None, again=None, later=False, no_price=False, listed=True):
    return {"state": "closed", "rule": rule, "closed": {"rule": rule, "base_kind": base_kind,
                                                         "close_last_vs_run_close_pct": last_close,
                                                         "close_last_vs_run_high_pct": last_high,
                                                         "another_run": again, "aplus_later": later,
                                                         "no_price": no_price, "listed": listed}}


def test_summary_one_clause_per_rule_every_count_x_of_n_late_peaks_apart():
    docs = [_closed("day", "run_close", last_close=5.0), _closed("day", "run_close", last_close=-3.0),
            _closed("day", "run_high", last_high=2.0, again={"date": "x", "rule": "day"}),
            _closed("day", "none", no_price=True, listed=False),
            _closed("aplus", "run_close", last_close=1.0, later=True), {"state": "open"}, {"state": "open"}]
    s = RT.summary(docs)
    assert s["open"] == 2 and s["closed"] == 5
    assert s["rules"]["day"] == {"n": 4, "again": 1, "aplus_later": 0, "reg_n": 2, "reg_up": 1, "late_n": 1,
                                 "late_up": 1, "no_price": 1, "not_listed": 1}
    t = RT.summary_text(s)
    assert t.startswith("2 being watched · 5 finished")
    assert " · ran with no A+ (4): 1 of 4 ran again · 0 of 4 rang A+ on a later session" in t
    assert " · 1 of 2 closed day 10 above the run-day close" in t
    assert " · ran after the 16:00 close: 1 of 1 closed day 10 above the run's high" in t
    assert " · ran after an A+ (1): 0 of 1 ran again · 1 of 1 rang A+ on a later session" in t
    assert t.endswith(" · " + RT.NOTE)


def test_NEGATIVE_summary_carries_counts_only_no_rate_no_rank_and_no_price_absent_at_zero():
    t = RT.summary_text(RT.summary([_closed("day", "run_close", last_close=5.0)]))
    assert "%" not in t and "rate" not in t.lower() and "best" not in t.lower()
    assert "no price" not in t
    t2 = RT.summary_text(RT.summary([_closed("day", "none", no_price=True)]))
    assert " · 1 finished with no price" in t2
    assert "ran after an A+" not in t2                                 # a rule with no finished run has no clause
    t0 = RT.summary_text(RT.summary([{"state": "open"}]))
    assert t0 == "1 being watched · 0 finished · " + RT.NOTE


def test_close_of_ratios_follow_the_base_kind_only():
    doc = {"run_day": RUN, "rule": "day", "seat": day_run(), "window": WIN, "listed": True, "aplus": [],
           "another_run": None, "base": {"kind": "run_high", "seat_high": 5.0, "run_close": 4.0, "run_high": 4.5},
           "sessions": [{"date": iso, "state": "ok", "close": 4.5, "high": 5.5, "low": 4.0} for iso in WIN]}
    c = RT.close_of(doc, by="window")
    assert c["close_last_vs_run_close_pct"] is None and c["worst_low_vs_run_close_pct"] is None
    assert c["close_last_vs_run_high_pct"] == -10.0 and c["best_high_after"]["vs_run_high_pct"] == 10.0
    assert c["best_high_after"]["vs_run_close_pct"] is None


# ── served ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _scan_nan(v):
    if isinstance(v, float):
        assert math.isfinite(v)
    elif isinstance(v, dict):
        for x in v.values():
            _scan_nan(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            _scan_nan(x)


def test_payload_ok_rows_closed_newest_first_every_cell_a_string_and_NEGATIVE_no_nan(seams):
    coll = Coll()
    bars = full_bars()
    bars[WIN[2]] = (float("nan"), float("nan"), float("nan"), float("nan"), float("nan"))
    seats = rdoc([entry("AAA", day_run()), entry("BBB", day_run(iso=WIN[1]))])
    frames = {"AAA": frame(bars), "BBB": frame(full_bars())}
    for iso in WIN + ["2026-11-30"]:
        run_night(iso, coll, seats, frames)
    p = RT.payload(night("2026-11-30"), coll=coll)
    json.dumps(p, allow_nan=False)
    _scan_nan(p)
    assert p["state"] == "ok" and p["closed_n"] == 2 and p["open_n"] == 0 and p["note"] == RT.NOTE
    assert [r["symbol"] for r in p["rows"]] == ["BBB", "AAA"]
    keys = [h[0] for h in p["heads"]]
    for r in p["rows"]:
        assert set(r["cells"]) == set(keys) and all(isinstance(v, str) for v in r["cells"].values())
    assert p["shown_text"] is None and p["asof_text"].endswith("through 2026-11-30")
    sp = RT.payload(night("2026-11-30"), "aaa", coll=coll)
    json.dumps(sp, allow_nan=False)
    assert sp["symbol"] == "AAA" and len(sp["docs"]) == 1 and sp["docs"][0]["rows"][2]["cells"]["close"] == "no bar"
    assert sp["docs"][0]["base_note"].startswith("Base: the 2026-11-13 regular close")


def test_NEGATIVE_payload_error_empty_and_off(monkeypatch):
    assert RT.payload(night(RUN), coll=Coll(fail_find=True))["state"] == "error"
    monkeypatch.setattr(RT.CO, "runtrack_coll", lambda db=None: None)
    assert RT.payload(night(RUN))["state"] == "error"
    e = RT.payload(night(RUN), coll=Coll())
    assert e["state"] == "empty" and e["rows"] == [] and "nightly" in e["summary_text"]
    assert RT.payload(night(RUN), "XYZ", coll=Coll())["state"] == "empty"
    monkeypatch.setattr(C, "RUNNERS_SEAT_ON", False)
    assert RT.payload(night(RUN), coll=Coll())["state"] == "off"


def test_payload_caps_the_rows_at_rows_max_and_still_counts_every_run(monkeypatch):
    monkeypatch.setattr(RT, "ROWS_MAX", 2)
    docs = [dict(_closed("day", "run_close", last_close=1.0), _id=f"{RUN}|S{i}", symbol=f"S{i}", run_day=RUN)
            for i in range(3)]
    p = RT.payload(night(RUN), coll=Coll(docs))
    assert len(p["rows"]) == 2 and p["closed_n"] == 3 and "newest 2 of 3" in p["shown_text"]


def test_NEGATIVE_a_failed_write_is_a_fault_and_never_raises(seams):
    coll = Coll(fail_write=True)
    out = run_night(RUN, coll, rdoc([entry("XYZ", day_run())]), {"XYZ": frame(full_bars())})
    assert out["faults"] == ["write"] and coll.docs == {}


def test_nightly_returns_exactly_its_keys(seams):
    out = run_night(RUN, Coll(), rdoc([entry("XYZ", day_run())]), {"XYZ": frame(full_bars())})
    assert tuple(out) == RT.OUT_KEYS and out["reads"] == 1 and out["opened"] == 1


def test_signatures_match_the_spec():
    assert list(inspect.signature(RT.nightly).parameters)[:6] == ["now", "db", "stores", "daily", "coll", "seats"]
    assert list(inspect.signature(RT.payload).parameters)[:4] == ["now", "symbol", "db", "coll"]
    assert RT.STATES == ("open", "closed") and RT.BASE_KINDS == ("run_close", "run_high", "none")
    assert RT.CLOSED_BY == ("window", "calendar") and RT.READ_KINDS == ("potential", "armed", "aplus")
    assert RT.ROWS_MAX == RT.GC.LEDGER_ROWS_MAX and RT.KEEP == C.RUNNERS_KEEP_SESSIONS
    assert set(RT.SEAT_REASONS) == {"dismissed", "aged", "blocked"} and RT.BLOCKED == "blocked"


def test_the_seats_are_read_through_runseat_read_doc_and_NEGATIVE_a_fault_is_none():
    class L:
        def __init__(self, doc=None, boom=False):
            self.doc, self.boom = doc, boom

        def find_one(self, q):
            if self.boom:
                raise RuntimeError("down")
            return self.doc if q == {"_id": C.RUNNERS_DOC_ID} else None
    doc = rdoc([entry("XYZ", day_run())])
    db = {C.COLL_LIST: L(doc), C.COLL_TILES: L(), C.COLL_ALERTS: L(), C.COLL_STATE: L()}
    assert RT._read_seats(db) == doc
    assert [s["key"] for s in RT.seat_runs(RT._read_seats(db), RUN)] == [f"{RUN}|XYZ"]
    db[C.COLL_LIST] = L(boom=True)
    assert RT._read_seats(db) is None


def test_NEGATIVE_runtrack_takes_only_avg_volume_before_from_momentum_burst():
    """2026-11-26 refix — the burst engine is pinned as display-only
    (test_momentum_burst_2026_09_24 widened by runtrack.py): the run track may
    read avg_volume_before and nothing else (no burst gate, no RVOL threshold)."""
    import re
    src = inspect.getsource(RT)
    used = set(re.findall(r"\bMB\.([A-Za-z_]\w*)", src))
    assert used == {"avg_volume_before"}, used
    assert "from supply_demand.momentum_burst import" not in src
    for bad in ("BURST_", "burst_session", "rvol_leg", "is_burst"):
        assert bad not in src, bad
