"""📅 Runners — the read-only probe equals the engine (spec watchrun rev 2 §4 WP-1 step 4, 2026-11-26).

The container runs origin/main (no runseat there), so scripts/gajjala_watch_runseat_probe.py re-implements the judging
piece. This pins it: on the same fixtures, under each of the three readings, the probe's seats / not-seated / pending
equal the engine's. Its fallback copies of the numbers equal the constants. The probe never writes and never asks the
provider by default. NEGATIVES included.
"""
from __future__ import annotations

import ast
import inspect
from datetime import date, datetime, timezone

import pytest

from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import runseat as RS
from scripts import gajjala_watch_runseat_probe as PB
from tests.test_gajjala_watch_runseat_2026_11_26 import (NOW, S, TODAY, Feed, World, bars1, db_with, done_except,
                                                         ring, runners_doc)

UTC = timezone.utc
STAMP = datetime(2026, 11, 25, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def test_the_probe_copies_equal_the_constants():
    assert PB.READINGS == C.RUNNERS_SEAT_READINGS and PB.DAY_PCT == C.RUNNERS_SEAT_DAY_PCT
    assert PB.APLUS_PCT == C.RUNNERS_SEAT_APLUS_PCT and PB.KEEP == C.RUNNERS_KEEP_SESSIONS
    assert PB.PAGES == C.RUNNERS_SEAT_PAGES
    src = inspect.getsource(PB)
    for lit in ('("after_aplus", "seat_cut", "either")', ', 30)', ', 10))', '("gajjala", "gajjala_1m")'):
        assert lit in src                                            # the origin/main fallbacks, pinned here


def test_NEGATIVE_the_probe_never_writes_and_never_imports_runseat():
    tree = ast.parse(inspect.getsource(PB))
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {"update_one", "insert_one", "replace_one", "delete_one", "delete_many", "update_many",
                        "_cas", "upsert_daily", "load_intraday", "_fetch_massive_minute"}
    assert "runseat" not in inspect.getsource(PB).replace("runseat probe", "").replace("runseat._judge", "") \
        .replace("runseat.from_trigger", "").replace("gajjala_watch_runseat_probe", "").replace(
        "`chart_maps.gajjala_watch.runseat`", "")


def _fixture_world():
    w = World()
    w.runner("DAY", high=1.6)                                        # day rule
    w.runner("LOW", high=1.2)                                        # under the cut
    w.runner("BENF", high=2.42)                                      # A+ under +30% — related
    w.runner("GP", high=1.3)                                         # A+ +30% exact
    w.runner("HZN", pc=1.76, high=88.0, daily_ok=False)              # no prior bar
    w.runner("NOREC", high=1.9, daily_ok=None)                       # prior unknown
    w.runner("SPL", high=3.0, check="failed")                        # split that day
    w.runner("UNK", high=3.0, check="failed")                        # split check unanswered → pending
    w.runner("TOP", high=2.75)                                       # rang after the close → plays TODAY
    w.runner("N30", high=1.31)                                       # seats only under "seat_cut"
    w.rings = [ring("BENF", S, 12, 11, 1.0), ring("GP", S, 10, 0, 0.9), ring("NT", S, 10, 0, None),
               ring("TOP", S, 16, 46, 1.0)]
    w.checks[TODAY.isoformat()] = {"BENF": "ok", "GP": "ok", "NT": "ok"}
    feed = Feed(days={("BENF", S.isoformat()): bars1(S, [(13, 0, 1.294)]), ("GP", S.isoformat()): bars1(S, [(10, 30, 1.17)])},
                stamps={("BENF", S.isoformat()): STAMP, ("GP", S.isoformat()): STAMP},
                splits={("SPL", "2026-11-23", "2026-11-24"): "2026-11-24", ("UNK", "2026-11-23", "2026-11-24"): None})
    return w, feed


@pytest.mark.parametrize("reading", C.RUNNERS_SEAT_READINGS)
def test_probe_equals_engine_on_fixtures(monkeypatch, reading):
    monkeypatch.setattr(C, "RUNNERS_SEAT_READING", reading)
    w, feed = _fixture_world()
    monkeypatch.setattr(RS.RN, "read_day", w.read_day)
    monkeypatch.setattr(RS, "aplus_rings", lambda dates, stores: [r for r in w.rings
                                                                 if r["date"] in {d.isoformat() for d in dates}])
    db = db_with(done_except(TODAY, S.isoformat()))
    RS.step(NOW, TODAY, db=db, stores={"gajjala": w, "gajjala_1m": w}, auto_prior={}, budget_sec=30,
            clock=feed.clock, load_1m=feed.load, cached_at=feed.cached_at, split_lookup=feed.look)
    doc = runners_doc(db)
    eng_seats = {e["symbol"]: e["rule"] for e in doc["entries"]}
    eng_ns = {(r["symbol"], r["why"]) for r in doc["not_seated"]}
    eng_pend = {(p["symbol"], p["why"]) for p in doc["pending"] if p["session"] == S.isoformat()}
    scan_by, reads_by = w.read_day(None, S.isoformat())
    got = PB.judge(S, reading=reading, scan_by=scan_by, reads_by=reads_by, rings=w.rings,
                   checks_of=w.split_checks,
                   daily_ok_of=lambda sym, iso: (lambda d: None if not isinstance(d, dict) or not isinstance(
                       d.get("squeeze_history"), dict) else d["squeeze_history"].get("daily_ok") is True)(
                       w.daily.get((iso, sym))),
                   stamp_of=lambda sym, iso: feed.stamps.get((sym, iso)),
                   bars_of=lambda sym, iso: feed.days.get((sym, iso)), look=feed.look, now=NOW, ask=True,
                   day_of=lambda iso: w.read_day(None, iso))
    assert got["seats"] == eng_seats
    assert got["not_seated"] == eng_ns
    assert got["pending"] == eng_pend
    if reading == "after_aplus":
        assert eng_seats == {"DAY": "day", "GP": "aplus"}
        assert ("BENF", "aplus_under") in eng_ns and ("HZN", "no_prior_bar") in eng_ns
        assert ("NOREC", "prior_unknown") in eng_ns and ("SPL", "split_day") in eng_ns
        assert ("NT", "aplus_no_trigger") in eng_ns and ("UNK", "split_unchecked") in eng_pend
    if reading == "seat_cut":
        assert "N30" in eng_seats and "LOW" not in eng_seats


def test_NEGATIVE_probe_without_splits_asks_nothing_and_marks_pending():
    w, feed = _fixture_world()
    scan_by, reads_by = w.read_day(None, S.isoformat())
    got = PB.judge(S, reading="after_aplus", scan_by=scan_by, reads_by=reads_by, rings=w.rings,
                   checks_of=w.split_checks, daily_ok_of=lambda sym, iso: True,
                   stamp_of=lambda sym, iso: feed.stamps.get((sym, iso)),
                   bars_of=lambda sym, iso: feed.days.get((sym, iso)), look=feed.look, now=NOW, ask=False)
    assert ("SPL", "split_unchecked") in got["pending"] and ("UNK", "split_unchecked") in got["pending"]
    assert all(x[0] in {"BENF", "GP", "NT"} for x in feed.looks)    # only the stored one-session record answers


def test_NEGATIVE_splits_flag_refused_during_regular_hours(monkeypatch, capsys):
    class FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 24, 15, 0, tzinfo=UTC)        # 10:00 ET Tue
    monkeypatch.setattr(PB, "datetime", FakeDT)
    assert PB.main(["--splits"]) == 2 and "refused" in capsys.readouterr().out
