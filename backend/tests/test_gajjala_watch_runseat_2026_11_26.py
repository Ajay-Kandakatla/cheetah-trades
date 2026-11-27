"""📅 Runners kept on the 👀 Watch for two weeks — the seating engine: the cuts, the three readings, the provider
budget, the list and the loop hook (spec watchrun rev 2 §3.1–§3.3, WP-1 be-seat, 2026-11-26).

Ajay 2026-11-26, verbatim: "Ok then add them to our watch list and track them please.. I know he tracks them for two
weeks sometimes.. before he discards them.. Can you do that please" · "Make it 30% please after A+".

The guards (split / no prior bar) live in test_gajjala_watch_runseat_guards_2026_11_26.py, the two × in
…_x_2026_11_26.py, the served roster in …_served_2026_11_26.py, the pipeline pin in …_rule_pin_2026_11_26.py.
NEGATIVES are the point.
"""
from __future__ import annotations

import copy
import functools
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import runners as RN
from chart_maps.gajjala_watch import runseat as RS
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
TODAY = date(2026, 11, 25)                       # Wed — the live session; Thanksgiving 11-26 is closed
S = date(2026, 11, 24)                           # Tue — the completed session under test
NOW = datetime(2026, 11, 25, 4, 5, tzinfo=ET)    # the first minutes of TODAY
NEXT = date(2026, 11, 27)                        # Fri (half day) — the next session
NOW_NEXT = datetime(2026, 11, 27, 4, 5, tzinfo=ET)


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── builders ─────────────────────────────────────────────────────────────────────────────────────────────────────
def et(d, hh, mm, ss=0):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


def bars5(d, rows):
    """rows: (hh, mm, high[, s]) — 5-minute bars RIGHT-labelled at hh:mm (the stored `tile.bars5` shape)."""
    out = []
    for row in rows:
        hh, mm, h = row[:3]
        b = {"t": f"{d.isoformat()} {hh:02d}:{mm:02d}", "o": h * 0.9, "h": h, "l": h * 0.8, "c": h * 0.95}
        if len(row) > 3:
            b["s"] = row[3]
        out.append(b)
    return out


def bars1(d, rows):
    """rows: (hh, mm, high) ET minute STARTS → ledger.bars_from_frame rows (t_utc, o, h, l, c)."""
    return [(et(d, hh, mm).astimezone(UTC), h * 0.9, h, h * 0.8, h * 0.95) for hh, mm, h in rows]


class World:
    """The stored scanner days (scan + read docs per ISO), the split checks and the daily records."""

    def __init__(self):
        self.scan: dict = {}
        self.reads: dict = {}
        self.checks: dict = {}
        self.daily: dict = {}
        self.daily_calls: list = []
        self.boom = False

    def runner(self, sym, d=S, *, pc=1.0, high=1.5, peak=(10, 5), pm=None, check="ok", daily_ok=True, read=True):
        iso = d.isoformat()
        self.scan.setdefault(iso, {})[sym] = {"symbol": sym, "date": iso, "last": {"prev_close": pc}}
        rows = [(9, 35, pc * 1.01), (peak[0], peak[1], high), (15, 55, pc * 1.02)]
        if pm is not None:
            rows.insert(0, (8, 0, pm, "pre"))
        if read:
            self.reads.setdefault(iso, {})[sym] = {"symbol": sym, "date": iso, "tile": {"bars5": bars5(d, rows)}}
        if check is not None:
            self.checks.setdefault(iso, {})[sym] = check
        if daily_ok is not None:
            self.daily[(iso, sym)] = {"squeeze_history": {"daily_ok": daily_ok}}
        return self

    # the store surface the engine reads
    def split_checks(self, d):
        return dict(self.checks.get(d.isoformat(), {}))

    def get_daily(self, d, sym):
        self.daily_calls.append((d.isoformat(), sym))
        return copy.deepcopy(self.daily.get((d.isoformat(), sym)))

    def read_day(self, st, iso):
        if self.boom:
            raise RuntimeError("scan store down")
        return copy.deepcopy(self.scan.get(iso, {})), copy.deepcopy(self.reads.get(iso, {}))


def ring(sym, d, hh, mm, trigger=1.0, *, page="gajjala", rid=None, at_none=False):
    at = None if at_none else et(d, hh, mm).astimezone(UTC)
    pd_ = RS.play_day(d, at) if at is not None else d
    return {"id": rid or f"{d.isoformat()}|{sym}|reversal_squeeze|aplus", "page": page, "date": d.isoformat(),
            "symbol": sym, "setup": "reversal_squeeze", "at_utc": at, "at_et": f"{hh:02d}:{mm:02d}",
            "trigger": trigger, "play_day": pd_.isoformat()}


class Feed:
    """The injected provider side: 1-minute days, their cache stamps and the split lookup — every call recorded."""

    def __init__(self, days=None, stamps=None, splits=None, status=None):
        self.days = days or {}                   # {(SYM, iso): bars}
        self.stamps = stamps or {}               # {(SYM, iso): aware datetime}
        self.splits = splits or {}               # {(SYM, after_iso, through_iso): answer | Exception}
        self.status = status or {}               # {(SYM, iso): "failed" | "over_budget" | "no_bars"}
        self.loads: list = []
        self.looks: list = []
        self.cache_reads: list = []
        self.clock_step = 0.0
        self.t = 0.0

    def clock(self):
        return self.t

    def load(self, sym, day, budget_sec):
        self.loads.append((sym, day.isoformat(), budget_sec))
        self.t += self.clock_step
        st = self.status.get((sym, day.isoformat()))
        if st is not None:
            return None, st
        bars = self.days.get((sym, day.isoformat()))
        if bars:                                                  # a completed day is cached once loaded
            self.stamps.setdefault((sym, day.isoformat()), datetime(2026, 11, 25, 9, 5, tzinfo=UTC))
        return (bars, "loaded") if bars else (None, "no_bars")

    def cached_at(self, sym, isos):
        self.cache_reads.append((sym, tuple(isos)))
        return {i: self.stamps[(sym, i)] for i in isos if (sym, i) in self.stamps}

    def look(self, sym, after, through):
        self.looks.append((sym, after.isoformat(), through.isoformat()))
        v = self.splits.get((sym, after.isoformat(), through.isoformat()), False)
        if isinstance(v, Exception):
            raise v
        return v


def db_with(doc=None, rules=None, auto=None):
    docs = [{"_id": C.LIST_DOC_ID, "symbols": []}]
    for d in (doc, rules, auto):
        if d is not None:
            docs.append(copy.deepcopy(d))
    return {C.COLL_LIST: FakeColl(docs), C.COLL_TILES: FakeColl(), C.COLL_ALERTS: FakeColl(),
            C.COLL_STATE: FakeColl()}


def done_except(session, *open_isos, reading=None):
    """A runners doc whose `processed` marks every completed window session done EXCEPT `open_isos`."""
    rd = reading or RS.reading()
    proc = {d.isoformat(): {"reading": rd, "n_scan": 0, "n_reads": 0, "partial": False, "at": NOW}
            for d in RS.keep_window(session) if d < session and d.isoformat() not in open_isos}
    return {"_id": C.RUNNERS_DOC_ID, "rev": 1, "entries": [], "dismissed": [], "removed": [], "processed": proc,
            "pending": [], "answers": {}, "not_seated": []}


def runners_doc(db):
    return db[C.COLL_LIST].docs.get(C.RUNNERS_DOC_ID)


@pytest.fixture()
def world(monkeypatch):
    w = World()
    monkeypatch.setattr(RS.RN, "read_day", w.read_day)
    monkeypatch.setattr(RS, "aplus_rings", lambda dates, stores: [r for r in w.rings
                                                                 if r["date"] in {d.isoformat() for d in dates}])
    w.rings = []
    return w


def go(world, db, *, now=NOW, session=TODAY, feed=None, budget=None, auto_prior=None, dry=False, **kw):
    feed = feed or Feed()
    out = RS.step(now, session, db=db, dry=dry, stores={"gajjala": world, "gajjala_1m": world},
                  auto_prior=auto_prior if auto_prior is not None else {}, budget_sec=budget, clock=feed.clock,
                  load_1m=feed.load, cached_at=feed.cached_at, split_lookup=feed.look, **kw)
    return out, feed


def seated(db):
    return {e["symbol"]: e for e in (runners_doc(db) or {}).get("entries") or []}


def why_of(db, sym):
    return [r["why"] for r in (runners_doc(db) or {}).get("not_seated") or [] if r["symbol"] == sym]


# ── constants ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_his_numbers_by_name():
    assert C.RUNNERS_SEAT_APLUS_PCT == 30 and C.RUNNERS_KEEP_SESSIONS == 10
    assert C.RUNNERS_SEAT_DAY_PCT == C.RAN_MIN_PCT == 40.0
    assert C.RUNNERS_SEAT_READING in C.RUNNERS_SEAT_READINGS and C.RUNNERS_SEAT_READING == "after_aplus"
    assert C.RUNNERS_SEAT_PROVIDER_MAX == RS.GC.DAILY_MAX_NEW_PER_PASS
    assert C.RUNNERS_PUSH_MODE == "off" and RS.push_mode() == "off"
    from chart_maps.gajjala import variant as V
    assert C.RUNNERS_SEAT_PAGES == (V.GG5.key, V.GG1.key)
    assert set(C.RUNNERS_SEAT_PENDING_WHYS) <= set(C.RUNNERS_SEAT_SKIPS)
    assert set(C.RUNNERS_SEAT_WHY) <= set(C.RUNNERS_SEAT_SKIPS)
    assert set(C.RUNNERS_SEAT_HINT_RULE) == set(C.RUNNERS_SEAT_READINGS)
    assert C.API_RUNSEAT_PATH.endswith("/runners/seat/{symbol}") and C.API_RUNTRACK_PATH.endswith("/runners/track")
    assert C.MAX_SYMBOLS == 18                                   # his ➕ cap untouched


def test_NEGATIVE_no_served_word_says_the_b_word_calm_or_pullback():
    words = [v for k, v in vars(C).items() if k.startswith("RUNNERS_SEAT") and isinstance(v, str)]
    words += [x for k, v in vars(C).items() if k.startswith("RUNNERS_SEAT") and isinstance(v, dict)
              for x in v.values()]
    assert words and not any(w for w in words if any(b in w.lower() for b in ("bounce", "calm", "pullback")))


def test_runtrack_coll_handle_and_none():
    assert CO.runtrack_coll({C.COLL_RUNTRACK: "H"}) == "H"

    class Boom(dict):
        def __getitem__(self, k):
            raise RuntimeError("down")
    assert CO.runtrack_coll(Boom()) is None
    assert set(CO.colls({C.COLL_LIST: 1, C.COLL_TILES: 2, C.COLL_ALERTS: 3, C.COLL_STATE: 4})) == {
        "list", "tiles", "alerts", "state"}                      # colls() untouched


# ── the readings ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_reading_cut_and_rules(monkeypatch):
    assert RS.reading() == "after_aplus" and RS.day_cut() == 40.0 and RS.aplus_rule_on() and RS.day_rule_skips_related()
    monkeypatch.setattr(C, "RUNNERS_SEAT_READING", "seat_cut")
    assert RS.day_cut() == 30.0 and not RS.aplus_rule_on() and not RS.day_rule_skips_related()
    monkeypatch.setattr(C, "RUNNERS_SEAT_READING", "either")
    assert RS.day_cut() == 40.0 and RS.aplus_rule_on() and not RS.day_rule_skips_related()
    monkeypatch.setattr(C, "RUNNERS_SEAT_READING", "nonsense")
    assert RS.reading() == "after_aplus" and RS.day_cut() == 40.0       # NEGATIVE: unknown → the first


def test_day_counts_equals_ran_of_counts_at_the_house_cut():
    w = World().runner("A", high=1.4).runner("B", high=1.399).runner("P", high=1.6, pm=1.7)
    for sym in ("A", "B", "P"):
        r = RN.ran_of(w.scan[S.isoformat()][sym], w.reads[S.isoformat()][sym], S)
        assert RS.day_counts(r, C.RAN_MIN_PCT) == r["counts"]
    assert not RS.day_counts(None)


# ── the cuts ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_day_rule_40_0_seats_and_39_9_does_not(world):
    world.runner("HIT", high=1.4).runner("MISS", high=1.399)
    db = db_with(done_except(TODAY, S.isoformat()))
    out, _ = go(world, db)
    e = seated(db)
    assert set(e) == {"HIT"} and e["HIT"]["rule"] == "day" and e["HIT"]["run_day"] == S.isoformat()
    assert e["HIT"]["runs"][0]["run_pct"] == 40.0 and out["added"] == ["HIT"]
    assert out["skipped"]["under_day"] == 1
    assert runners_doc(db)["processed"][S.isoformat()]["reading"] == "after_aplus"


def test_NEGATIVE_premarket_peak_day_does_not_seat(world):
    world.runner("PM", high=1.6, pm=1.7)
    db = db_with(done_except(TODAY, S.isoformat()))
    out, _ = go(world, db)
    assert seated(db) == {} and out["skipped"]["premarket_peak"] == 1


def test_NEGATIVE_aplus_name_29_9_from_trigger_not_seated_even_at_plus_40_day(world):
    world.runner("BEN", high=2.42)                                # +142% vs the prior close
    world.rings = [ring("BEN", S, 12, 11, trigger=1.0)]
    feed = Feed(days={("BEN", S.isoformat()): bars1(S, [(12, 30, 1.2999)])},
                stamps={("BEN", S.isoformat()): datetime(2026, 11, 25, 9, 0, tzinfo=UTC)})
    db = db_with(done_except(TODAY, S.isoformat()))
    out, _ = go(world, db, feed=feed, budget=30)
    assert seated(db) == {}
    ns = [r for r in runners_doc(db)["not_seated"] if r["symbol"] == "BEN"]
    assert [r["why"] for r in ns] == ["aplus_under"]
    assert "+29.9%" in ns[0]["text"] and "+30.0%" not in ns[0]["text"]        # floored, never across the bar


def test_aplus_30_0_exact_seats_0_9_to_1_17(world):
    world.rings = [ring("GP", S, 10, 0, trigger=0.9)]
    feed = Feed(days={("GP", S.isoformat()): bars1(S, [(10, 30, 1.17)])},
                stamps={("GP", S.isoformat()): datetime(2026, 11, 25, 9, 0, tzinfo=UTC)})
    db = db_with(done_except(TODAY, S.isoformat()))
    go(world, db, feed=feed, budget=30)
    e = seated(db)["GP"]
    assert e["rule"] == "aplus" and e["runs"][0]["run_pct"] == 30.0 and e["runs"][0]["trigger"] == 0.9
    assert e["runs"][0]["high_px"] == 1.17 and e["runs"][0]["from_et"] == "10:00" and e["runs"][0]["to_et"] == "20:00"


def test_from_trigger_window_edges():
    d = S
    at = et(d, 10, 0).astimezone(UTC)
    # NEGATIVE: a high before max(ring + 30 s, 09:45) or at / after 20:00 never counts
    early = RS.from_trigger(bars1(d, [(10, 0, 2.0), (10, 5, 1.1)]), d, at, 1.0)
    assert early["passed"] is False and early["high_px"] == 1.1
    pre = RS.from_trigger(bars1(d, [(9, 40, 3.0), (11, 0, 1.0)]), d, et(d, 9, 0).astimezone(UTC), 1.0)
    assert pre["from_et"] == "09:45" and pre["high_px"] == 1.0
    late = RS.from_trigger(bars1(d, [(20, 0, 5.0), (19, 59, 1.0)]), d, at, 1.0)
    assert late["high_px"] == 1.0 and late["passed"] is False
    # the FIRST minute printing the max
    tie = RS.from_trigger(bars1(d, [(11, 0, 1.5), (12, 0, 1.5)]), d, at, 1.0)
    assert tie["high_et"] == "11:00" and tie["passed"] and tie["run_pct"] == 50.0
    assert RS.from_trigger([], d, at, 1.0)["why"] == "aplus_no_bars"
    assert RS.from_trigger(bars1(d, [(11, 0, 1.5)]), d, at, None)["why"] == "aplus_no_trigger"
    assert RS.from_trigger(bars1(d, [(11, 0, 1.5)]), d, at, 0)["why"] == "aplus_no_trigger"
    assert RS.from_trigger(bars1(d, [(11, 0, 1.5)]), d, None, 1.0)["why"] == "aplus_no_time"
    assert set(RS.FROM_TRIGGER_KEYS) <= set(tie)


def test_NEGATIVE_trigger_or_ring_time_missing_not_seated_reason_served(world):
    world.runner("NT", high=1.6).runner("NOT", high=1.6)
    world.rings = [ring("NT", S, 10, 0, trigger=None), ring("NOT", S, 10, 0, at_none=True)]
    db = db_with(done_except(TODAY, S.isoformat()))
    go(world, db)
    assert seated(db) == {}
    assert why_of(db, "NT") == ["aplus_no_trigger"] and why_of(db, "NOT") == ["aplus_no_time"]
    texts = {r["symbol"]: r["text"] for r in runners_doc(db)["not_seated"]}
    assert "no trigger price" in texts["NT"] and "no ring time" in texts["NOT"]


def test_ring_after_the_close_measured_next_session_pending_until_then(world):
    world.runner("TOP", high=2.75)                                # +175% on S, peak 10:05
    world.rings = [ring("TOP", S, 16, 46, trigger=1.0)]           # rang after the close → plays TODAY
    assert world.rings[0]["play_day"] == TODAY.isoformat()
    db = db_with(done_except(TODAY, S.isoformat()))
    feed = Feed()
    out, _ = go(world, db, feed=feed, budget=30)
    assert seated(db) == {} and feed.loads == []                  # NEGATIVE: not measured on S, no day seat
    pend = runners_doc(db)["pending"]
    assert [(p["symbol"], p["session"], p["why"]) for p in pend] == [("TOP", TODAY.isoformat(), "aplus_pending")]
    assert S.isoformat() in runners_doc(db)["processed"]          # S itself is final
    # the next session: TODAY is complete → measured on its own bars
    feed2 = Feed(days={("TOP", TODAY.isoformat()): bars1(TODAY, [(10, 0, 1.31)])},
                 stamps={("TOP", TODAY.isoformat()): datetime(2026, 11, 26, 9, 0, tzinfo=UTC)})
    go(world, db, now=NOW_NEXT, session=NEXT, feed=feed2, budget=30)
    e = seated(db)["TOP"]
    assert e["rule"] == "aplus" and e["run_day"] == TODAY.isoformat()
    assert all(p["symbol"] != "TOP" for p in runners_doc(db)["pending"])


# ── the readings, end to end ─────────────────────────────────────────────────────────────────────────────────────
def _benf_gdhg(world):
    world.runner("BENF", high=2.42)                               # +142%, A+ 12:11 runs +29.4%
    world.runner("GDHG", high=16.0, peak=(12, 10))                # +1500%, ring 19:29 (after the close)
    world.rings = [ring("BENF", S, 12, 11, trigger=1.0), ring("GDHG", S, 19, 29, trigger=10.0)]
    stamp = datetime(2026, 11, 25, 9, 0, tzinfo=UTC)
    return Feed(days={("BENF", S.isoformat()): bars1(S, [(13, 0, 1.294)])},
                stamps={("BENF", S.isoformat()): stamp})


def test_after_aplus_neither_benf_nor_gdhg_seats(world):
    feed = _benf_gdhg(world)
    db = db_with(done_except(TODAY, S.isoformat()))
    go(world, db, feed=feed, budget=30)
    assert seated(db) == {}
    assert why_of(db, "BENF") == ["aplus_under"]


def test_either_seats_both_by_the_day_rule(world, monkeypatch):
    monkeypatch.setattr(C, "RUNNERS_SEAT_READING", "either")
    feed = _benf_gdhg(world)
    db = db_with(done_except(TODAY, S.isoformat()))
    go(world, db, feed=feed, budget=30)
    e = seated(db)
    assert set(e) == {"BENF", "GDHG"} and e["BENF"]["rule"] == "day" and e["GDHG"]["rule"] == "day"
    assert why_of(db, "BENF") == []


def test_either_one_run_rule_aplus_with_the_day_facts_kept(world, monkeypatch):
    monkeypatch.setattr(C, "RUNNERS_SEAT_READING", "either")
    world.runner("BOTH", high=1.8)
    world.rings = [ring("BOTH", S, 10, 0, trigger=1.0)]
    feed = Feed(days={("BOTH", S.isoformat()): bars1(S, [(10, 30, 1.5)])},
                stamps={("BOTH", S.isoformat()): datetime(2026, 11, 25, 9, 0, tzinfo=UTC)})
    db = db_with(done_except(TODAY, S.isoformat()))
    go(world, db, feed=feed, budget=30)
    e = seated(db)["BOTH"]
    assert e["rule"] == "aplus" and len(e["runs"]) == 1
    assert e["runs"][0]["day"]["rule"] == "day" and e["runs"][0]["day"]["run_pct"] == 80.0


def test_seat_cut_30_vs_prior_close_with_or_without_aplus(world, monkeypatch):
    monkeypatch.setattr(C, "RUNNERS_SEAT_READING", "seat_cut")
    world.runner("N30", high=1.3).runner("A30", high=1.3).runner("N29", high=1.299)
    world.rings = [ring("A30", S, 10, 0, trigger=1.0)]
    feed = Feed()
    db = db_with(done_except(TODAY, S.isoformat()))
    go(world, db, feed=feed, budget=30)
    assert set(seated(db)) == {"N30", "A30"} and feed.loads == []      # the A+ rule is off
    assert seated(db)["A30"]["rule"] == "day"


def test_flip_rereads_only_adds_and_live_reading_is_never_read_again(world, monkeypatch):
    feed = _benf_gdhg(world)
    world.runner("KEEP", high=1.9)
    db = db_with(done_except(TODAY, S.isoformat()))
    go(world, db, feed=feed, budget=30)
    assert set(seated(db)) == {"KEEP"}
    world.boom = True                                              # NEGATIVE: a done session is never read again
    out, _ = go(world, db, feed=feed, budget=30)
    assert out["reason"] is None and set(seated(db)) == {"KEEP"}
    world.boom = False
    monkeypatch.setattr(C, "RUNNERS_SEAT_READING", "either")
    go(world, db, feed=feed, budget=30)                                       # the flip re-reads the window and ADDS
    assert set(seated(db)) == {"KEEP", "BENF", "GDHG"}
    monkeypatch.setattr(C, "RUNNERS_SEAT_READING", "after_aplus")
    go(world, db, feed=feed, budget=30)                                       # flipping back never removes a seat
    assert set(seated(db)) == {"KEEP", "BENF", "GDHG"}
    assert runners_doc(db)["processed"][S.isoformat()]["reading"] == "after_aplus"


# ── the provider budget [C8] ─────────────────────────────────────────────────────────────────────────────────────
def _cold_rings(world, n):
    world.checks.setdefault(TODAY.isoformat(), {})
    days = {}
    world.rings = []
    for i in range(n):
        sym = f"R{i:02d}"
        world.rings.append(ring(sym, S, 10, 0, trigger=1.0))
        world.checks[TODAY.isoformat()][sym] = "ok"                # the ring guard answers from the stored record
        days[(sym, S.isoformat())] = bars1(S, [(10, 30, 1.4)])
    return Feed(days=days)


@pytest.mark.parametrize("budget", [None, 0, -1])
def test_NEGATIVE_no_budget_no_provider_read_stored_seats_still_land(world, budget):
    feed = _cold_rings(world, 2)
    world.runner("DAY", high=1.6)
    db = db_with(done_except(TODAY, S.isoformat()))
    out, _ = go(world, db, feed=feed, budget=budget)
    assert feed.loads == [] and out["provider"]["started"] == 0
    assert set(seated(db)) == {"DAY"}
    assert {p["symbol"] for p in runners_doc(db)["pending"]} == {"R00", "R01"}
    assert S.isoformat() not in runners_doc(db)["processed"]       # the session stays open


def test_cap_stops_at_provider_max_then_the_rest_next_minute(world):
    n = int(C.RUNNERS_SEAT_PROVIDER_MAX) + 2
    feed = _cold_rings(world, n)
    db = db_with(done_except(TODAY, S.isoformat()))
    out, _ = go(world, db, feed=feed, budget=30)
    assert len(feed.loads) == C.RUNNERS_SEAT_PROVIDER_MAX == out["provider"]["started"]
    assert len(seated(db)) == C.RUNNERS_SEAT_PROVIDER_MAX
    pend = runners_doc(db)["pending"]
    assert len(pend) == 2 and all(p["tried"] is None and p["why"] == "aplus_pending" for p in pend)
    go(world, db, feed=feed, budget=30)                             # a deferred item is asked the next minute
    assert len(seated(db)) == n and S.isoformat() in runners_doc(db)["processed"]


def test_first_failure_stops_the_step_and_is_not_asked_again_this_session(world):
    feed = _cold_rings(world, 3)
    feed.status[("R00", S.isoformat())] = "failed"
    db = db_with(done_except(TODAY, S.isoformat()))
    out, _ = go(world, db, feed=feed, budget=30)
    assert [x[0] for x in feed.loads] == ["R00"] and out["provider"] == {"started": 1, "failed": True,
                                                                         "over_budget": 0}
    pend = {p["symbol"]: p for p in runners_doc(db)["pending"]}
    assert pend["R00"]["tried"] == TODAY.isoformat() and pend["R01"]["tried"] is None
    assert pend["R00"]["why"] == "aplus_pending"                   # NEGATIVE: a provider failure is never "no bars"
    assert why_of(db, "R00") == []
    feed.loads.clear()
    go(world, db, feed=feed, budget=30)                             # the same session: R00 not asked again
    assert [x[0] for x in feed.loads] == ["R01", "R02"]
    assert "R00" not in seated(db)
    feed.loads.clear()
    del feed.status[("R00", S.isoformat())]
    out3, _ = go(world, db, now=NOW_NEXT, session=NEXT, feed=feed, budget=30)    # a LATER session asks it again
    # R00: one split check (no cache stamp → the window runs to today, two sessions: the provider) + its load;
    # R01 / R02: cache reads, not counted
    assert out3["provider"]["started"] == 2 and "R00" in seated(db) and ("R00", S.isoformat(), 0.0) not in feed.loads


def test_no_read_starts_after_the_deadline(world):
    feed = _cold_rings(world, 4)
    feed.clock_step = 3.0                                           # every load takes 3 s of the fake clock
    db = db_with(done_except(TODAY, S.isoformat()))
    go(world, db, feed=feed, budget=5)
    assert len(feed.loads) == 2                                     # t=0 ✓, t=3 ✓, t=6 > 5 → stop
    assert feed.loads[1][2] == pytest.approx(2.0)                   # the time LEFT is handed to the loader


def test_over_budget_status_is_a_provider_failure_per_spec(world):
    """Spec §3.2: status "failed" / "over_budget" → provider.used(False): counted, the step stops, the item is
    stamped tried and asked again only on a LATER session."""
    feed = _cold_rings(world, 3)
    feed.status[("R00", S.isoformat())] = "over_budget"
    db = db_with(done_except(TODAY, S.isoformat()))
    out, _ = go(world, db, feed=feed, budget=30)
    assert [x[0] for x in feed.loads] == ["R00"]                    # NEGATIVE: no further read after it this step
    assert out["provider"] == {"started": 1, "failed": True, "over_budget": 1}
    pend = {p["symbol"]: p for p in runners_doc(db)["pending"]}
    assert pend["R00"]["tried"] == TODAY.isoformat() and pend["R00"]["why"] == "aplus_pending"
    assert pend["R01"]["tried"] is None and pend["R02"]["tried"] is None    # the deferred ones keep tried None
    assert why_of(db, "R00") == []                                  # NEGATIVE: over budget is never "no bars"
    assert S.isoformat() not in runners_doc(db)["processed"]
    feed.loads.clear()
    out2, _ = go(world, db, feed=feed, budget=30)                   # the same session: R00 not asked again
    assert [x[0] for x in feed.loads] == ["R01", "R02"] and out2["provider"]["over_budget"] == 0
    assert "R00" not in seated(db) and {"R01", "R02"} <= set(seated(db))
    feed.loads.clear()
    del feed.status[("R00", S.isoformat())]
    go(world, db, now=NOW_NEXT, session=NEXT, feed=feed, budget=30)  # a LATER session asks it again
    assert "R00" in seated(db) and any(x[0] == "R00" for x in feed.loads)


def test_NEGATIVE_over_budget_on_a_cached_day_is_not_counted(world):
    world.rings = [ring("CA", S, 10, 0)]
    feed = Feed(stamps={("CA", S.isoformat()): datetime(2026, 11, 25, 9, 0, tzinfo=UTC)},
                status={("CA", S.isoformat()): "over_budget"})
    world.checks[TODAY.isoformat()] = {"CA": "ok"}
    db = db_with(done_except(TODAY, S.isoformat()))
    out, _ = go(world, db, feed=feed, budget=30)
    assert out["provider"] == {"started": 0, "failed": False, "over_budget": 0}
    pend = {p["symbol"]: p for p in runners_doc(db)["pending"]}
    assert pend["CA"]["tried"] is None and "CA" not in seated(db)


def test_cached_day_is_not_counted(world):
    world.rings = [ring("CA", S, 10, 0)]
    feed = Feed(days={("CA", S.isoformat()): bars1(S, [(10, 30, 1.4)])},
                stamps={("CA", S.isoformat()): datetime(2026, 11, 25, 9, 0, tzinfo=UTC)})
    world.checks[TODAY.isoformat()] = {"CA": "ok"}
    db = db_with(done_except(TODAY, S.isoformat()))
    out, _ = go(world, db, feed=feed, budget=None)                  # no provider budget at all
    assert "CA" in seated(db) and out["provider"]["started"] == 0


def test_loader_uses_this_modules_own_breaker(monkeypatch):
    from daytrading import data as dt_data
    from chart_maps.gajjala_watch import rest as REST
    from chart_maps.gajjala_watch import runchart as RCH
    seen = {}

    def fake_load_days(sym, days, *, load_day=None, budget_sec=None, **k):
        seen["load"], seen["budget"] = load_day, budget_sec
        return {}, {days[0].isoformat(): "no_bars"}
    monkeypatch.setattr(RCH, "load_days", fake_load_days)
    assert RS._default_load_1m("ABC", S, 7.5) == (None, "no_bars")
    cb = seen["load"].keywords["cb"]
    assert isinstance(seen["load"], functools.partial) and seen["load"].func is dt_data.load_intraday
    assert cb is RS._breaker() and cb is not dt_data._CB and cb is not REST.breaker() and cb is not RCH.breaker()
    assert seen["budget"] == 7.5


# ── the list ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _entry(sym, run_day, rule="day", pct=60.0):
    return {"symbol": sym, "rule": rule, "run_day": run_day.isoformat(), "first_run_day": run_day.isoformat(),
            "runs": [{"date": run_day.isoformat(), "rule": rule, "run_pct": pct, "peak_et": "10:00"}],
            "added_at": NOW.astimezone(UTC), "seated_session": TODAY.isoformat(), "reading": "after_aplus"}


def test_day_10_kept_day_11_aged():
    first = RS.keep_window(TODAY)[0]
    assert RS.day_n(first, TODAY) == 10 and RS.day_n(TODAY, TODAY) == 1 and RS.day_n(S, TODAY) == 2
    assert RS.day_n(first - timedelta(days=1), TODAY) is None
    assert len(RS.keep_window(TODAY)) == C.RUNNERS_KEEP_SESSIONS


def test_aged_entry_leaves_with_its_record(world):
    first = RS.keep_window(TODAY)[0]
    doc = done_except(NEXT)
    doc["entries"] = [_entry("OLD", first), _entry("MID", S)]
    db = db_with(doc)
    go(world, db)                                                   # day 10 at TODAY: nothing to do
    assert set(seated(db)) == {"OLD", "MID"}
    out, _ = go(world, db, now=NOW_NEXT, session=NEXT)
    assert set(seated(db)) == {"MID"} and out["removed"] == [{"symbol": "OLD", "reason": "aged"}]
    # `removed` is pruned by the ENTRY's run day (spec §3.2): an aged run's 10 sessions are over, so its record is
    # not kept — the nightly opened its doc while it was seated
    assert runners_doc(db)["removed"] == []


def test_a_second_qualifying_day_restarts_and_not_when_off(world, monkeypatch):
    prev = date(2026, 11, 20)
    world.runner("TWO", high=1.6)
    doc = done_except(TODAY, S.isoformat())
    doc["entries"] = [_entry("TWO", prev)]
    db = db_with(doc)
    out, _ = go(world, db)
    e = seated(db)["TWO"]
    assert e["run_day"] == S.isoformat() and e["first_run_day"] == prev.isoformat() and len(e["runs"]) == 2
    assert out["restarted"] == ["TWO"]
    monkeypatch.setattr(C, "RUNNERS_SEAT_RESTART", False)
    db2 = db_with(doc)
    go(world, db2)
    e2 = seated(db2)["TWO"]
    assert e2["run_day"] == prev.isoformat() and len(e2["runs"]) == 2       # NEGATIVE: no restart


def test_broker_names_seat(world):
    world.runner("FID", high=1.7)
    db = db_with(done_except(TODAY, S.isoformat()))
    go(world, db)
    assert "FID" in seated(db)                                     # 🚫 names seat (sorted last when served)


def test_blocked_by_a_rules_or_auto_pair_written_once_to_removed(world):
    world.runner("DOGZ", high=1.9).runner("TWG", high=2.05)
    rules = {"_id": C.RULES_DOC_ID, "dismissed": [{"symbol": "DOGZ", "session": S.isoformat(), "via": "rules"}]}
    auto = {"session": S.isoformat(), "dismissed": ["TWG"]}
    db = db_with(done_except(TODAY, S.isoformat()), rules=rules)
    out, _ = go(world, db, auto_prior=auto)
    assert seated(db) == {}
    rm = runners_doc(db)["removed"]
    assert sorted((r["symbol"], r["reason"]) for r in rm) == [("DOGZ", "blocked"), ("TWG", "blocked")]
    assert all(r["entry"]["run_day"] == S.isoformat() and r["entry"]["runs"] for r in rm)
    assert out["skipped"]["dismissed"] == 2 and sorted(out["blocked"]) == ["DOGZ", "TWG"]
    # NEGATIVE: a re-read of the same session does not duplicate it
    runners_doc(db)["processed"].pop(S.isoformat())
    go(world, db, auto_prior=auto)
    assert len(runners_doc(db)["removed"]) == 2


def _open_session_with_x_and_y(world):
    """S stays open (ZZZ's ring is pending with no budget), XXX and YYY seated; WWW is new so the next minute writes."""
    world.runner("XXX", high=1.8).runner("YYY", high=1.6)
    world.rings = [ring("ZZZ", S, 10, 0, trigger=1.0)]
    db = db_with(done_except(TODAY, S.isoformat()))
    go(world, db)
    assert set(seated(db)) == {"XXX", "YYY"}
    assert S.isoformat() not in (runners_doc(db).get("processed") or {})
    world.runner("WWW", high=1.7)
    return db


def test_NEGATIVE_roster_x_between_the_read_and_the_write_is_not_reseated(world, monkeypatch):
    """Critic P1 (REFIX 2026-11-26): the × lands between the step's read and its compare-and-set; the retry re-reads
    the doc AND re-derives the blocked pairs, so XXX stays off and only WWW is added."""
    db = _open_session_with_x_and_y(world)
    real = RS.AUTO._cas
    fired: list = []

    def cas(coll, doc, fields, doc_id=None):
        if not fired:
            fired.append(1)
            assert RS.dismiss("XXX", by="owner", db=db, now=NOW)["state"] == "dismissed"
        return real(coll, doc, fields, doc_id=doc_id)
    monkeypatch.setattr(RS.AUTO, "_cas", cas)
    out, _ = go(world, db)
    assert fired
    assert sorted(seated(db)) == ["WWW", "YYY"]
    assert out["added"] == ["WWW"]
    assert [(r["symbol"], r["run_day"]) for r in runners_doc(db)["dismissed"]] == [("XXX", S.isoformat())]
    # NEGATIVE: a later minute does not bring it back either
    go(world, db)
    assert "XXX" not in seated(db)


def test_NEGATIVE_no_x_mid_step_keeps_the_seat_and_adds_the_new_name(world):
    db = _open_session_with_x_and_y(world)
    out, _ = go(world, db)
    assert sorted(seated(db)) == ["WWW", "XXX", "YYY"] and out["added"] == ["WWW"]
    assert runners_doc(db)["dismissed"] == []


def test_NEGATIVE_a_tile_x_on_a_later_day_blocks_nothing(world):
    world.runner("LATE", high=1.9)
    rules = {"_id": C.RULES_DOC_ID, "dismissed": [{"symbol": "LATE", "session": TODAY.isoformat(), "via": "rules"}]}
    db = db_with(done_except(TODAY, S.isoformat()), rules=rules)
    go(world, db)
    assert "LATE" in seated(db)


def test_partial_session_counts(world):
    world.runner("HAS", high=1.2).runner("GONE", high=1.9, read=False).runner("GONE2", read=False)
    db = db_with(done_except(TODAY, S.isoformat()))
    out, _ = go(world, db)
    p = runners_doc(db)["processed"][S.isoformat()]
    assert p["partial"] is True and p["n_scan"] == 3 and p["n_reads"] == 1
    assert out["partial"] == [S.isoformat()] and out["skipped"]["no_bars"] == 2


@pytest.mark.parametrize("fault", ["list", "rules", "auto", "ledger", "boards"])
def test_NEGATIVE_a_read_fault_writes_nothing(world, monkeypatch, fault):
    world.runner("X", high=1.9)
    doc = done_except(TODAY, S.isoformat())
    db = db_with(doc)
    before = copy.deepcopy(db[C.COLL_LIST].docs)
    prior = {}
    if fault == "list":
        db[C.COLL_LIST].fail = True
    elif fault == "rules":
        monkeypatch.setattr(RS.RULES, "read_doc", lambda cs: None)
    elif fault == "auto":
        prior = None
    elif fault == "ledger":
        def boom(dates, stores):
            raise LG.LedgerReadError("down")
        monkeypatch.setattr(RS, "aplus_rings", boom)
    else:
        world.boom = True
    out = RS.step(NOW, TODAY, db=db, stores={"gajjala": world, "gajjala_1m": world},
                  auto_prior=prior if fault != "auto" else None, split_lookup=Feed().look)
    db[C.COLL_LIST].fail = False
    want = {"list": "list_unreadable", "rules": "dismissed_unreadable", "auto": "dismissed_unreadable",
            "ledger": "ledger_unreadable", "boards": "boards_unreadable"}[fault]
    assert out["reason"] == want and db[C.COLL_LIST].docs == before and db[C.COLL_LIST].writes == 0


def test_NEGATIVE_owner_auto_rules_docs_never_written(world):
    world.runner("ALL", high=1.9)
    rules = {"_id": C.RULES_DOC_ID, "rev": 3, "entries": [], "dismissed": []}
    auto = {"_id": C.AUTO_DOC_ID, "rev": 2, "session": S.isoformat(), "entries": [], "dismissed": []}
    db = db_with(done_except(TODAY, S.isoformat()), rules=rules, auto=auto)
    before = {k: copy.deepcopy(v) for k, v in db[C.COLL_LIST].docs.items() if k != C.RUNNERS_DOC_ID}
    RS.step(NOW, TODAY, db=db, stores={"gajjala": world, "gajjala_1m": world}, split_lookup=Feed().look)
    assert {k: v for k, v in db[C.COLL_LIST].docs.items() if k != C.RUNNERS_DOC_ID} == before
    assert "ALL" in seated(db)


def test_NEGATIVE_closed_off_and_nothing_to_do(world, monkeypatch):
    db = db_with(done_except(TODAY))
    out = RS.step(datetime(2026, 11, 26, 10, 0, tzinfo=ET), TODAY, db=db, auto_prior={})
    assert out["reason"] == "closed" and db[C.COLL_LIST].writes == 0
    out, _ = go(world, db)
    assert out["reason"] is None and out["changed"] is False and db[C.COLL_LIST].writes == 0
    monkeypatch.setattr(C, "RUNNERS_SEAT_ON", False)
    assert RS.step(NOW, TODAY, db=db)["reason"] == "off"


def test_dry_returns_writes_and_writes_nothing(world):
    world.runner("DRY", high=1.9)
    db = db_with(done_except(TODAY, S.isoformat()))
    out, _ = go(world, db, dry=True)
    assert out["writes"]["entries"][0]["symbol"] == "DRY" and runners_doc(db)["entries"] == []
    assert set(C.RUNNERS_SEAT_OUT_KEYS) <= set(out)


def test_aplus_rings_reads_both_pages_and_raises_on_a_fault():
    from chart_maps.gajjala import variant as V

    class Store:
        def __init__(self, rows, fail=False):
            self.rows, self.fail = rows, fail

        def potential_pushes(self, sessions):
            return None if self.fail else []

        def alert_rows(self, sessions):
            return None if self.fail else list(self.rows)
    at = et(S, 10, 0).astimezone(UTC).isoformat()
    doc = {"_id": "x", "state": "pushed", "symbol": "GP", "setup": "reversal_squeeze", "date": S.isoformat(),
           "at": at, "trigger": 1.0, "stop": 0.9}
    late = dict(doc, symbol="TOP", at=et(S, 16, 46).astimezone(UTC).isoformat())
    rows = RS.aplus_rings([S], stores={V.GG5.key: Store([doc, late]), V.GG1.key: Store([])})
    by = {r["symbol"]: r for r in rows}
    assert by["GP"]["play_day"] == S.isoformat() and by["TOP"]["play_day"] == TODAY.isoformat()
    assert by["GP"]["page"] == "gajjala" and by["GP"]["trigger"] == 1.0
    with pytest.raises(LG.LedgerReadError):
        RS.aplus_rings([S], stores={V.GG5.key: Store([], fail=True), V.GG1.key: Store([])})
    with pytest.raises(LG.LedgerReadError):
        RS.aplus_rings([S], stores={V.GG5.key: Store([])})


# ── the loop [C8] ────────────────────────────────────────────────────────────────────────────────────────────────
from chart_maps.gajjala_watch import loop as LP                                     # noqa: E402
from tests.test_gajjala_watch_auto_2026_11_17 import fake_db as auto_fake_db        # noqa: E402
from tests.test_gajjala_watch_build_2026_11_15 import S as LS, at as lat            # noqa: E402


@pytest.fixture()
def order(monkeypatch):
    calls = []
    real_state, real_write = LP._state, LP.BLD.write

    def state(cs, _id, fields):
        calls.append(("state", _id))
        return real_state(cs, _id, fields)

    def write(tiles, updates):
        calls.append(("tiles", len(updates)))
        return real_write(tiles, updates)

    def step(now, session, **kw):
        calls.append(("step", kw.get("budget_sec")))
        return dict(RS._early(None, ["ZZZ"]), added=["ZZZ"])
    monkeypatch.setattr(LP, "_state", state)
    monkeypatch.setattr(LP.BLD, "write", write)
    monkeypatch.setattr(LP.RUNSEAT, "step", step)
    monkeypatch.setattr(LP.RULES, "step", lambda *a, **k: {"symbols": [], "reason": None})
    monkeypatch.setattr(LP.AUTO, "step", lambda *a, **k: {"symbols": [], "reason": None})
    return calls


class Wall:
    def __init__(self, t0, step_s):
        self.t, self.step_s = t0, step_s

    def __call__(self):
        t = self.t
        self.t = self.t + timedelta(seconds=self.step_s)
        return t


def test_loop_step_runs_after_the_tiles_and_the_latest_write(order):
    db = auto_fake_db()
    t = lat(LS, 10, 6, 30)
    out = LP.run_iteration(t, db=db, deps=LP.Deps(load_day=lambda *a, **k: None, wall=Wall(t, 4.0),
                                                  sleep=lambda s: None))
    kinds = [c[0] for c in order]
    assert kinds.index("tiles") < kinds.index("step")
    assert order.index(("state", C.STATE_LATEST_ID)) < kinds.index("step")
    assert order[-1] == ("state", C.RUNNERS_STATE_ID)
    left = next(c[1] for c in order if c[0] == "step")
    assert 0 <= left < RS.GC.GG1M_MINUTE_BUDGET_SEC
    latest = db[C.COLL_STATE].docs[C.STATE_LATEST_ID]
    assert set(latest) - {"_id"} == {"at", "session", "n_names", "n_read", "bars", "alerts", "wall_s", "reason",
                                     "auto", "rules"}                     # the latest doc gains no key
    assert out["runners"]["added"] == ["ZZZ"] and set(out["runners"]) == set(C.RUNNERS_SEAT_OUT_KEYS)
    st = db[C.COLL_STATE].docs[C.RUNNERS_STATE_ID]
    assert st["session"] == LS.isoformat() and "wall_s" in st


def test_loop_left_sec_never_negative(order):
    db = auto_fake_db()
    t = lat(LS, 10, 6, 30)
    LP.run_iteration(t, db=db, deps=LP.Deps(load_day=lambda *a, **k: None, wall=Wall(t, 60.0),
                                            sleep=lambda s: None))
    assert next(c[1] for c in order if c[0] == "step") == 0.0


def test_loop_no_names_path_still_runs_the_step_with_the_whole_budget(order):
    db = auto_fake_db(manual=[])
    t = lat(LS, 10, 6, 30)
    out = LP.run_iteration(t, db=db, deps=LP.Deps(load_day=lambda *a, **k: None, wall=Wall(t, 1.0),
                                                  sleep=lambda s: None))
    assert out["reason"] == LP.NO_TICKERS
    assert ("step", RS.GC.GG1M_MINUTE_BUDGET_SEC) in order


def test_NEGATIVE_stub_mode_never_runs_the_step(order):
    LP.run_iteration(lat(LS, 10, 6, 30), db=auto_fake_db(), deps=LP.dry_deps(), dry=True, symbols=["OMH"])
    assert not any(c[0] == "step" for c in order)


def test_NEGATIVE_a_raising_step_leaves_the_iteration_intact(order, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("seat down")
    monkeypatch.setattr(LP.RUNSEAT, "step", boom)
    db = auto_fake_db()
    t = lat(LS, 10, 6, 30)
    out = LP.run_iteration(t, db=db, deps=LP.Deps(load_day=lambda *a, **k: None, wall=Wall(t, 1.0),
                                                  sleep=lambda s: None))
    assert out["ran"] is True and "runners" not in out and C.STATE_LATEST_ID in db[C.COLL_STATE].docs
    assert C.RUNNERS_STATE_ID not in db[C.COLL_STATE].docs


# ── refix 2026-11-26 (spec §3.1 "pct floored to a whole %"): the run keeps the UNROUNDED value, every print floors it ──
def _seat_aplus(world, sym, trigger, high):
    world.rings = [ring(sym, S, 10, 0, trigger=trigger)]
    feed = Feed(days={(sym, S.isoformat()): bars1(S, [(10, 30, high)])},
                stamps={(sym, S.isoformat()): datetime(2026, 11, 25, 9, 0, tzinfo=UTC)})
    db = db_with(done_except(TODAY, S.isoformat()))
    go(world, db, feed=feed, budget=30)
    return seated(db)[sym]


def test_NEGATIVE_aplus_34_96_never_prints_35(world):
    from chart_maps.gajjala_watch import runtrack as RT
    e = _seat_aplus(world, "P2", 1.0, 1.3496)                      # raw +34.96% — rounded to 1 dp it would read 35.0
    run = e["runs"][0]
    assert run["run_pct"] == pytest.approx(34.96) and run["run_pct"] != 35.0
    tag = RS.tag_of(e, TODAY)
    assert tag["seat_text"] == "🎯 +34% from A+" and "+35%" not in tag["seat_text"]
    assert "= +34.9% above the trigger" in tag["seat_title"] and "+35.0%" not in tag["seat_title"]
    rec = RT._seat_text({"rule": C.RUNNERS_SEAT_RULES[1], "seat": dict(run)})   # the record copies the run (seat = dict(run))
    assert rec == "🎯 +34% from A+"


def test_aplus_exact_30_still_prints_30_no_float_noise(world):
    e = _seat_aplus(world, "GP", 0.9, 1.17)                        # (1.17 / 0.9 − 1) × 100 = 29.999…96 in floats
    assert e["runs"][0]["run_pct"] == 30.0
    tag = RS.tag_of(e, TODAY)
    assert tag["seat_text"] == "🎯 +30% from A+" and "+29%" not in tag["seat_text"]
    assert "= +30.0% above the trigger" in tag["seat_title"]


def test_from_trigger_keeps_its_1dp_key_and_the_raw_beside_it():
    d = S
    m = RS.from_trigger(bars1(d, [(11, 0, 1.3496)]), d, et(d, 10, 0).astimezone(UTC), 1.0)
    assert m["run_pct"] == 35.0                                    # the spec'd 1-dp key (replay_win30 parity) is unchanged
    assert m["_raw_pct"] == pytest.approx(34.96) and m["_raw_pct"] != m["run_pct"]
