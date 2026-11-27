"""📅 Runners — the two guards (spec watchrun rev 2 §3.2 [C1, C2], WP-1, 2026-11-26).

[C1] An A+ is never measured across a split between its ring and the day its 1-minute bars were fetched (SRTM 11-20:
1-for-9 on 2026-11-23, the cached day fetched 2026-11-23 14:51 UTC and re-based — "+838%" on the app's own cache).
[C2] A day-rule runner seats only on a traded prior close: no listed split that day, and a daily bar before that
session in the scanner's stored record (HZN 11-16: prior close 1.76, first bar 88.0, no split listed, check "ok",
`daily_ok` False). NEGATIVES are the point.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import runseat as RS
from tests.test_gajjala_watch_runseat_2026_11_26 import (NOW, TODAY, Feed, bars1, db_with, done_except, go, ring,
                                                         runners_doc, seated, why_of, world)  # noqa: F401 — fixture

UTC = timezone.utc
SRTM_DAY = date(2026, 11, 20)
HZN_DAY = date(2026, 11, 16)


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── [C1] the A+ split guard — the SRTM fixture ───────────────────────────────────────────────────────────────────
def _srtm(world, stamp, split):
    world.runner("SRTM", SRTM_DAY, pc=0.0465, high=0.0865)            # +86% that day (5-minute reads, old count)
    world.rings = [ring("SRTM", SRTM_DAY, 13, 16, trigger=0.0824)]
    rebased = bars1(SRTM_DAY, [(9, 30, 0.7875), (14, 33, 0.773)])      # the cache re-based by the 1-for-9
    fetched = stamp.astimezone(RS.ET).date()
    return Feed(days={("SRTM", SRTM_DAY.isoformat()): rebased}, stamps={("SRTM", SRTM_DAY.isoformat()): stamp},
                splits={("SRTM", SRTM_DAY.isoformat(), fetched.isoformat()): split})


def test_srtm_split_after_the_ring_before_the_fetch_is_never_measured(world):
    feed = _srtm(world, datetime(2026, 11, 23, 14, 51, tzinfo=UTC), "2026-11-23")
    db = db_with(done_except(TODAY, SRTM_DAY.isoformat()))
    out, _ = go(world, db, feed=feed, budget=30)
    assert seated(db) == {} and feed.loads == []                      # never measured, never seated
    assert feed.looks == [("SRTM", "2026-11-20", "2026-11-23")]       # (ring date, fetch date]
    ns = [r for r in runners_doc(db)["not_seated"] if r["symbol"] == "SRTM"]
    assert [r["why"] for r in ns] == ["aplus_split"] and "2026-11-23" in ns[0]["text"]
    assert "838" not in str(runners_doc(db))
    assert SRTM_DAY.isoformat() in runners_doc(db)["processed"]       # final
    ans = runners_doc(db)["answers"]
    assert list(ans.values())[0]["v"] == "2026-11-23"


def test_same_ring_fetched_before_the_split_is_measured_on_its_bars(world):
    feed = _srtm(world, datetime(2026, 11, 21, 15, 0, tzinfo=UTC), False)
    feed.days[("SRTM", SRTM_DAY.isoformat())] = bars1(SRTM_DAY, [(14, 33, 0.0859)])   # the old share count
    db = db_with(done_except(TODAY, SRTM_DAY.isoformat()))
    go(world, db, feed=feed, budget=30)
    assert feed.loads and seated(db) == {}
    ns = [r for r in runners_doc(db)["not_seated"] if r["symbol"] == "SRTM"]
    assert [r["why"] for r in ns] == ["aplus_under"] and "+4.2%" in ns[0]["text"]


def test_NEGATIVE_a_raising_split_check_keeps_the_session_open(world):
    feed = _srtm(world, datetime(2026, 11, 23, 14, 51, tzinfo=UTC), RuntimeError("massive down"))
    db = db_with(done_except(TODAY, SRTM_DAY.isoformat()))
    out, _ = go(world, db, feed=feed, budget=30)
    assert seated(db) == {} and feed.loads == []
    pend = runners_doc(db)["pending"]
    assert [(p["symbol"], p["why"], p["tried"]) for p in pend] == [("SRTM", "aplus_split_unchecked", TODAY.isoformat())]
    assert SRTM_DAY.isoformat() not in runners_doc(db)["processed"] and out["provider"]["failed"] is True
    assert runners_doc(db)["answers"] == {}


def test_an_answered_check_is_stored_and_not_asked_again(world):
    feed = _srtm(world, datetime(2026, 11, 23, 14, 51, tzinfo=UTC), False)
    feed.days[("SRTM", SRTM_DAY.isoformat())] = bars1(SRTM_DAY, [(14, 33, 0.0859)])
    world.runner("OPEN", SRTM_DAY, high=2.0, check="failed")           # keeps the session open (split unchecked)
    feed.splits[("OPEN", "2026-11-19", "2026-11-20")] = RuntimeError("down")
    db = db_with(done_except(TODAY, SRTM_DAY.isoformat()))
    go(world, db, feed=feed, budget=30)
    assert ("SRTM", "2026-11-20", "2026-11-23") in feed.looks and SRTM_DAY.isoformat() not in runners_doc(db)["processed"]
    n = len([x for x in feed.looks if x[0] == "SRTM"])
    go(world, db, feed=feed, budget=30)                               # the next minute
    assert len([x for x in feed.looks if x[0] == "SRTM"]) == n         # answered → never asked again


def test_a_one_session_window_the_scanner_answers_costs_no_provider_read(world, monkeypatch):
    from chart_maps import drop10_tab as DT
    monkeypatch.setattr(DT, "fetch_splits_strict", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fetched")))
    S = date(2026, 11, 24)
    world.rings = [ring("ONE", S, 10, 0, trigger=1.0)]
    world.checks[TODAY.isoformat()] = {"ONE": "ok"}
    feed = Feed(days={("ONE", S.isoformat()): bars1(S, [(10, 30, 1.5)])},
                stamps={("ONE", S.isoformat()): datetime(2026, 11, 25, 9, 0, tzinfo=UTC)})
    db = db_with(done_except(TODAY, S.isoformat()))
    out = RS.step(NOW, TODAY, db=db, stores={"gajjala": world, "gajjala_1m": world}, auto_prior={}, budget_sec=30,
                  clock=feed.clock, load_1m=feed.load, cached_at=feed.cached_at,
                  split_lookup=LG._default_split_lookup(world))       # the HOUSE lookup on the scanner's record
    assert "ONE" in seated(db) and out["provider"]["started"] == 0
    assert RS.split_is_stored(world.split_checks, "ONE", S, TODAY)
    assert not RS.split_is_stored(world.split_checks, "ONE", S, date(2026, 11, 27))   # two sessions: never stored
    assert not RS.split_is_stored(world.split_checks, "NOPE", S, TODAY)


def test_fetched_on():
    assert RS.fetched_on(datetime(2026, 11, 23, 14, 51, tzinfo=UTC), NOW) == date(2026, 11, 23)
    assert RS.fetched_on(datetime(2026, 11, 24, 3, 0), NOW) == date(2026, 11, 23)     # naive = UTC → ET evening
    assert RS.fetched_on(None, NOW) == TODAY                                         # no stamp → the widest window


# ── [C2] the day guards — the HZN fixture ────────────────────────────────────────────────────────────────────────
def _hzn(world, **kw):
    world.runner("HZN", HZN_DAY, pc=1.76, high=88.0, peak=(9, 35), check="ok", **kw)
    return db_with(done_except(TODAY, HZN_DAY.isoformat()))


def test_hzn_no_prior_bar_not_seated(world):
    db = _hzn(world, daily_ok=False)
    feed = Feed()
    out, _ = go(world, db, feed=feed, budget=30)
    assert seated(db) == {} and feed.looks == []                      # "ok" on file: no split read
    assert why_of(db, "HZN") == ["no_prior_bar"]
    assert "first session under this ticker" in runners_doc(db)["not_seated"][0]["text"]
    assert out["skipped"]["no_prior_bar"] == 1


def test_hzn_with_a_daily_bar_seats(world):
    db = _hzn(world, daily_ok=True)
    go(world, db, budget=30)
    assert "HZN" in seated(db) and seated(db)["HZN"]["runs"][0]["run_pct"] == pytest.approx(4900.0)


def test_NEGATIVE_daily_record_missing_is_prior_unknown(world):
    db = _hzn(world, daily_ok=None)
    go(world, db)
    assert seated(db) == {} and why_of(db, "HZN") == ["prior_unknown"]


def test_prior_bar_reads_and_faults():
    class St:
        def __init__(self, doc=None, boom=False):
            self.doc, self.boom = doc, boom

        def get_daily(self, d, sym):
            if self.boom:
                raise RuntimeError("down")
            return self.doc
    assert RS.prior_bar(St({"squeeze_history": {"daily_ok": True}}), "A", HZN_DAY) == "ok"
    assert RS.prior_bar(St({"squeeze_history": {"daily_ok": False}}), "A", HZN_DAY) == "no_prior_bar"
    assert RS.prior_bar(St({"squeeze_history": {}}), "A", HZN_DAY) == "no_prior_bar"
    assert RS.prior_bar(St({}), "A", HZN_DAY) == "prior_unknown"
    assert RS.prior_bar(St(None), "A", HZN_DAY) == "prior_unknown"
    assert RS.prior_bar(St(boom=True), "A", HZN_DAY) == "prior_unknown"


def test_check_failed_and_a_split_that_day_is_split_day(world):
    world.runner("SPL", HZN_DAY, high=3.0, check="failed")
    world.runner("NOREC", HZN_DAY, high=3.0, check=None)
    feed = Feed(splits={("SPL", "2026-11-13", "2026-11-16"): "2026-11-16",
                        ("NOREC", "2026-11-13", "2026-11-16"): "2026-11-16"})
    db = db_with(done_except(TODAY, HZN_DAY.isoformat()))
    go(world, db, feed=feed, budget=30)
    assert seated(db) == {} and why_of(db, "SPL") == ["split_day"] and why_of(db, "NOREC") == ["split_day"]


def test_NEGATIVE_check_failed_and_the_lookup_unreadable_is_pending(world):
    world.runner("UNK", HZN_DAY, high=3.0, check="failed")
    feed = Feed(splits={("UNK", "2026-11-13", "2026-11-16"): None})
    db = db_with(done_except(TODAY, HZN_DAY.isoformat()))
    out, _ = go(world, db, feed=feed, budget=30)
    assert seated(db) == {} and why_of(db, "UNK") == []
    assert [(p["symbol"], p["why"]) for p in runners_doc(db)["pending"]] == [("UNK", "split_unchecked")]
    assert HZN_DAY.isoformat() not in runners_doc(db)["processed"]
    db2 = db_with(done_except(TODAY, HZN_DAY.isoformat()))
    go(world, db2, feed=Feed(), budget=None)                          # no budget: pending too, never seated
    assert seated(db2) == {} and runners_doc(db2)["pending"][0]["why"] == "split_unchecked"


def test_NEGATIVE_a_name_under_the_cut_never_triggers_a_guard_read(world):
    world.runner("LOW", HZN_DAY, high=1.2, check="failed", daily_ok=False)
    feed = Feed()
    db = db_with(done_except(TODAY, HZN_DAY.isoformat()))
    out, _ = go(world, db, feed=feed, budget=30)
    assert feed.looks == [] and world.daily_calls == [] and out["provider"]["started"] == 0
    assert out["skipped"]["under_day"] == 1 and runners_doc(db)["not_seated"] == []
