"""👀 Gajjala's Watch — the minute loop clock, the lease, one iteration, the add-time build child and the CLI
(spec 2026-11-15 §3.5.3, WP-B).

Ajay, verbatim (2026-11-15): "I need dashboard to add tickers to Gajjalas watch dashboard. I wanna be able to remove and
add remove tickers from the dashboard. When I add a ticker I need 1 min 3 min and 5 min charts... I need alerts on these
from 1 min to I can be ready".

Pins: iterations at tick+0:30 … tick+4:30 (a late spawn runs at once, [C1.4]); a wake in another slot ends the loop
([C2.6]); the ONE lease engine with GG1's (55, 0) on the watch's own state collection — two iterations 60 s apart both
claim, a held lease skips one minute and the loop goes on ([C1.1]); the push BEFORE the tile writes; the build child
reads only listed names and never pushes ([C2.5]); --now / --symbols refuse without --dry-run ([C2.8]).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala import store as ST
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import cross_alerts as XA
from chart_maps.gajjala_watch import loop as L
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_watch_build_2026_11_15 import PREV, S, at, raw_day, stamp

ET = ZoneInfo("America/New_York")
HALF = date(2026, 11, 27)
TICK = at(S, 10, 1)                                             # a 🚩 cron tick ("1-56/5")


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def fake_db(symbols=("OMH",), **docs):
    db = {C.COLL_LIST: FakeColl([{"_id": C.LIST_DOC_ID, "symbols": list(symbols)}] if symbols is not None else []),
          C.COLL_TILES: FakeColl(docs.get("tiles")), C.COLL_ALERTS: FakeColl(), C.COLL_STATE: FakeColl(docs.get("state"))}
    return db


class Clock:
    """A fake wall clock (UTC-aware): sleep advances it; `jumps` = {sleep call index: extra seconds} (host sleep)."""
    def __init__(self, t, jumps=None):
        self.t = t.astimezone(timezone.utc)
        self.sleeps = []
        self.jumps = jumps or {}

    def wall(self):
        return self.t

    def sleep(self, sec):
        self.sleeps.append(sec)
        self.t += timedelta(seconds=sec + self.jumps.get(len(self.sleeps) - 1, 0))


def deps_for(clock, load=None, send=None):
    return L.Deps(load_day=load or (lambda *a, **k: None), send=send, wall=clock.wall, sleep=clock.sleep)


def record_iterations(monkeypatch, clock, step=2.0, result=None):
    calls = []

    def fake(now, **k):
        calls.append({"now": now.astimezone(ET), "budget": k.get("budget_sec")})
        clock.t += timedelta(seconds=step)
        return dict(result or {"ran": True, "reason": None})
    monkeypatch.setattr(L, "run_iteration", fake)
    return calls


# ── the slot clock ───────────────────────────────────────────────────────────────────────────────────────────────
def test_iterations_run_at_tick_plus_0_30_to_4_30_and_none_at_5_30(monkeypatch):
    clock = Clock(TICK + timedelta(seconds=8))
    calls = record_iterations(monkeypatch, clock)
    out = L.loop(deps=deps_for(clock), db=fake_db())
    assert [c["now"].strftime("%H:%M:%S") for c in calls] == ["10:01:30", "10:02:30", "10:03:30", "10:04:30",
                                                                "10:05:30"]
    assert out["n"] == 5 and out["skipped"] == 0 and out["reason"] == "no time left in the slot"
    assert clock.sleeps[0] == pytest.approx(22.0)                       # spawn tick+0:08 → sleeps to tick+0:30
    assert [c["budget"] for c in calls] == [35.0, 35.0, 35.0, 35.0, 30.0]   # min(35, next_tick − start)


def test_C1_4_a_late_spawn_runs_at_once_and_reads_the_bar_that_closed_at_the_tick(monkeypatch):
    clock = Clock(TICK + timedelta(seconds=34))
    calls = record_iterations(monkeypatch, clock)
    L.loop(deps=deps_for(clock), db=fake_db())
    assert calls[0]["now"] == TICK + timedelta(seconds=34)
    assert len(clock.sleeps) == len(calls) - 1 == 4                     # no sleep before iteration 0
    assert R1._bar_label(calls[0]["now"]) == TICK
    assert calls[1]["now"].strftime("%H:%M:%S") == "10:02:30"


def test_C2_6_NEGATIVE_a_wake_in_the_next_slot_ends_the_loop(monkeypatch):
    clock = Clock(TICK + timedelta(seconds=8), jumps={1: 6 * 60})
    calls = record_iterations(monkeypatch, clock)
    out = L.loop(deps=deps_for(clock), db=fake_db())
    assert len(calls) == 1 and out["reason"] == "slot passed (host sleep)" and out["n"] == 1


def test_NEGATIVE_no_iteration_after_the_extended_close_and_the_half_day_stops_at_17(monkeypatch):
    clock = Clock(at(S, 20, 1, 5))
    calls = record_iterations(monkeypatch, clock)
    out = L.loop(deps=deps_for(clock), db=fake_db())
    assert calls == [] and out["reason"] == "after the extended close"
    clock = Clock(at(HALF, 17, 1, 5))
    calls = record_iterations(monkeypatch, clock)
    assert L.loop(deps=deps_for(clock), db=fake_db())["reason"] == "after the extended close" and calls == []
    clock = Clock(at(HALF, 16, 56, 5))
    calls = record_iterations(monkeypatch, clock)
    L.loop(deps=deps_for(clock), db=fake_db())
    assert calls[-1]["now"].strftime("%H:%M:%S") == "17:00:30" and len(calls) == 5
    clock = Clock(at(S, 17, 1, 5))                                     # a regular day runs past 17:00
    calls = record_iterations(monkeypatch, clock)
    assert L.loop(deps=deps_for(clock), db=fake_db())["reason"] == "no time left in the slot" and len(calls) == 5


def test_NEGATIVE_off_runs_nothing_and_writes_the_loop_state(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "0")
    clock = Clock(TICK)
    calls = record_iterations(monkeypatch, clock)
    db = fake_db()
    out = L.loop(deps=deps_for(clock), db=db)
    assert calls == [] and out["reason"] == "off"
    assert db[C.COLL_STATE].docs[C.LOOP_STATE_ID]["reason"] == "off"


# ── the lease [C1.1 / C2.2] ──────────────────────────────────────────────────────────────────────────────────────
def test_the_watch_lease_is_the_one_engine_with_gg1_numbers():
    st = L.lease_store(FakeColl())
    assert st._lease_nums() == (GC.GG1M_LEASE_SEC, GC.GG1M_LEASE_MIN_GAP_SEC) == (55, 0)


def test_the_store_level_demonstration_the_default_gap_would_refuse_a_minute_loop():
    now = datetime(2026, 11, 13, 15, 2, 30, tzinfo=timezone.utc)
    doc = {"_id": ST.LEASE_ID, "status": "running", "claimed_at": now - timedelta(seconds=60),
           "last_cron_started_at": now - timedelta(seconds=60)}
    assert ST.lease_claimable(doc, now, ST.LEASE_CRON, lease_sec=55) is False
    assert ST.lease_claimable(doc, now, ST.LEASE_CRON, lease_sec=55, gap_sec=0) is True


def frames_spy(monkeypatch, ret=None, raise_=None):
    calls = []

    def fake(symbols, session, now, **k):
        calls.append({"symbols": list(symbols), "session": session, "now": now, **k})
        if raise_:
            raise raise_
        return dict(ret or {})
    monkeypatch.setattr(BLD, "frames", fake)
    return calls


def test_two_iterations_60_s_apart_both_claim_and_release(monkeypatch):
    db = fake_db()
    frames_spy(monkeypatch)
    a = L.run_iteration(at(S, 10, 1, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    b = L.run_iteration(at(S, 10, 2, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert a["ran"] and b["ran"]
    lease = db[C.COLL_STATE].docs[ST.LEASE_ID]
    assert lease["status"] == "done" and lease["last_cron_started_at"] == at(S, 10, 2, 30).astimezone(timezone.utc)


def test_NEGATIVE_a_held_lease_skips_that_minute_without_a_fetch_and_the_loop_goes_on(monkeypatch):
    held_at = (TICK + timedelta(seconds=20)).astimezone(timezone.utc)
    db = fake_db(state=[{"_id": ST.LEASE_ID, "status": "running", "token": "other", "held_by": ST.LEASE_CRON,
                         "claimed_at": held_at, "last_cron_started_at": held_at}])
    calls = frames_spy(monkeypatch)
    clock = Clock(TICK + timedelta(seconds=8))
    out = L.loop(deps=deps_for(clock), db=db)
    assert out["skipped"] == 1 and out["n"] == 4 and out["reason"] == "no time left in the slot"
    assert out["iterations"][0]["reason"] == L.LEASE_HELD and len(calls) == 4      # no fetch on the held minute
    loop_doc = db[C.COLL_STATE].docs[C.LOOP_STATE_ID]
    assert (loop_doc["n"], loop_doc["skipped"], loop_doc["reason"]) == (4, 1, "no time left in the slot")


def test_NEGATIVE_a_raising_iteration_still_releases_its_own_lease(monkeypatch):
    db = fake_db()
    frames_spy(monkeypatch, raise_=RuntimeError("massive down"))
    with pytest.raises(RuntimeError):
        L.run_iteration(at(S, 10, 1, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    lease = db[C.COLL_STATE].docs[ST.LEASE_ID]
    assert lease["status"] == "done" and "done_at" in lease


def test_NEGATIVE_the_loop_survives_a_raising_iteration(monkeypatch):
    frames_spy(monkeypatch, raise_=RuntimeError("massive down"))
    clock = Clock(TICK + timedelta(seconds=30))
    out = L.loop(deps=deps_for(clock), db=fake_db())
    assert out["n"] == 5 and all(i["reason"] == "error" for i in out["iterations"])


# ── one iteration ────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_an_empty_list_claims_no_lease_and_calls_no_loader(monkeypatch):
    # 🤖 2026-11-17 (spec ggwauto §4 WP-A re-pin): IN the pass window an empty list now claims the lease ONCE for the
    # auto step (it may add 🧠 potentials) and still calls no loader when nothing is added; OUT of the window with
    # nothing listed and nothing auto → still no lease.
    db = fake_db(symbols=[])
    calls = frames_spy(monkeypatch)
    steps = []
    monkeypatch.setattr(L.AUTO, "step", lambda *a, **k: (steps.append(k), {"symbols": [], "reason": None})[1])
    loads = []
    out = L.run_iteration(at(S, 10, 1, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: loads.append(a)))
    assert out["reason"] == "no tickers" and not out["ran"] and calls == [] and loads == []
    assert len(steps) == 1 and db[C.COLL_STATE].docs[ST.LEASE_ID]["status"] == "done"
    assert db[C.COLL_STATE].docs[C.STATE_LATEST_ID]["reason"] == "no tickers"
    out = L.run_iteration(at(S, 10, 1, 30), db=fake_db(symbols=None), deps=L.Deps(load_day=lambda *a, **k: None))
    assert out["reason"] == "no tickers"
    db = fake_db(symbols=[])
    out = L.run_iteration(at(S, 20, 30, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: loads.append(a)))
    assert out["reason"] == "no tickers" and ST.LEASE_ID not in db[C.COLL_STATE].docs and len(steps) == 2
    assert calls == [] and loads == []


def test_NEGATIVE_env_0_is_off(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "0")
    calls = frames_spy(monkeypatch)
    db = fake_db()
    assert L.run_iteration(at(S, 10, 1, 30), db=db)["reason"] == "off" and calls == []
    assert db[C.COLL_STATE].docs == {}


def test_the_push_runs_before_the_tile_writes_and_both_see_the_listed_names(monkeypatch):
    order = []
    frames_spy(monkeypatch)
    monkeypatch.setattr(XA, "run", lambda *a, **k: (order.append("push"), {"names": 0})[1])
    real_write = BLD.write
    monkeypatch.setattr(BLD, "write", lambda c, u: (order.append("tiles"), real_write(c, u))[1])
    db = fake_db(symbols=["OMH", "AMD"])
    out = L.run_iteration(at(S, 10, 1, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert order == ["push", "tiles"] and out["ran"]
    assert sorted(db[C.COLL_TILES].docs) == ["AMD", "OMH"]
    st = db[C.COLL_STATE].docs[C.STATE_LATEST_ID]
    assert st["n_names"] == 2 and st["alerts"] == {"names": 0} and st["session"] == S.isoformat()


def test_NEGATIVE_a_raising_push_still_writes_the_tiles_and_the_state(monkeypatch):
    frames_spy(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(XA, "run", boom)
    db = fake_db()
    out = L.run_iteration(at(S, 10, 1, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert out["alerts"] == {"error": 1} and "OMH" in db[C.COLL_TILES].docs
    assert db[C.COLL_STATE].docs[C.STATE_LATEST_ID]["alerts"] == {"error": 1}


def test_an_iteration_on_real_frames_rings_and_writes_the_tile(monkeypatch):
    def price(ts):
        mm = ts.hour * 60 + ts.minute
        return 14.0 if mm >= 10 * 60 + 5 else 10.0 - 0.002 * (mm - 4 * 60)

    def load(sym, day, force=False, include_premarket=True, include_afterhours=False):
        return (raw_day(S, end=(10, 7), price=price, volume=5000.0) if day == S
                else raw_day(PREV, price=lambda ts: 10.0))
    sent = []
    db = fake_db()
    out = L.run_iteration(at(S, 10, 6, 30), db=db,
                          deps=L.Deps(load_day=load, send=lambda o, p: (sent.append(p), {"sent": 1,
                                                                                          "total_targets": 1})[1],
                                      owner="owner@example.com"))
    assert out["alerts"]["pushed"] == 1 and len(sent) == 1 and sent[0]["ticker"] == "OMH"
    tile = db[C.COLL_TILES].docs["OMH"]
    assert tile["status"] == "loaded" and tile["seen_bar_t"] == stamp(S, 10, 6)
    assert tile["held"]["1m"] == {"bar_t": stamp(S, 10, 6), "reason": "pushed"}
    assert list(tile["frames"]) == ["1m", "5m", "15m"]                              # RE-PINNED 2026-11-23 (3m → 15m)
    assert list(db[C.COLL_ALERTS].docs) == ["GGW:2026-11-13|OMH|1m"]


def test_a_failed_read_keeps_the_last_good_charts(monkeypatch):
    db = fake_db(tiles=[{"_id": "OMH", "symbol": "OMH", "status": "loaded", "session": S.isoformat(),
                         "frames": {"1m": {"bars": [1]}}, "seen_bar_t": stamp(S, 10, 5)}])

    def fake(symbols, session, now, **k):
        k["per_name"]["OMH"] = {"status": "failed", "prev": True}
        return {}
    monkeypatch.setattr(BLD, "frames", fake)
    L.run_iteration(at(S, 10, 6, 30), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    t = db[C.COLL_TILES].docs["OMH"]
    assert t["status"] == "failed" and t["frames"] == {"1m": {"bars": [1]}} and t["seen_bar_t"] == stamp(S, 10, 5)


# ── the build child [C2.5] ───────────────────────────────────────────────────────────────────────────────────────
def test_the_build_child_builds_every_pending_listed_name_only(monkeypatch):
    db = fake_db(symbols=["OMH", "AMD", "NVDA", "TSLA"],
                 # FIXTURE 2026-11-23: a loaded doc holds every tf of C.FRAMES (build_pending now rebuilds a doc
                 # lacking one — an old 1m/3m/5m doc has no 15m); the assertions are unchanged
                 tiles=[{"_id": "AMD", "session": S.isoformat(), "status": "loaded",
                         "frames": {tf: {"tf": tf} for tf, _r in C.FRAMES}},                    # done → never fetched
                        {"_id": "NVDA", "session": PREV.isoformat(), "status": "loaded"},   # another session
                        {"_id": "TSLA", "session": S.isoformat(), "status": "failed"},      # not loaded
                        {"_id": "ZZZZ", "session": PREV.isoformat(), "status": "failed"}])  # not listed
    calls = frames_spy(monkeypatch)
    monkeypatch.setattr(XA, "run", lambda *a, **k: pytest.fail("the build child never pushes"))
    out = L.build_pending(at(S, 12, 0), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert calls[0]["symbols"] == ["OMH", "NVDA", "TSLA"] and len(calls) == 1
    assert out["built"] == ["OMH", "NVDA", "TSLA"] and out["session"] == S.isoformat()
    assert "ZZZZ" not in [s for c in calls for s in c["symbols"]]
    assert db[C.COLL_STATE].docs == {}                                              # no state doc, no lease


def test_the_build_child_re_reads_the_list_and_tries_each_name_once(monkeypatch):
    db = fake_db(symbols=["OMH"])
    calls = []

    def fake(symbols, session, now, **k):
        calls.append(list(symbols))
        if len(calls) == 1:                                     # he adds AMD while the child builds
            db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"] = ["OMH", "AMD"]
        for s in symbols:
            k["per_name"][s] = {"status": "failed", "prev": False}
        return {}
    monkeypatch.setattr(BLD, "frames", fake)
    out = L.build_pending(at(S, 12, 0), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert calls == [["OMH"], ["AMD"]] and out["rounds"] == 2                     # failing names: once each
    assert db[C.COLL_TILES].docs["OMH"]["status"] == "failed" and "frames" not in db[C.COLL_TILES].docs["OMH"]


def test_the_build_child_on_a_closed_day_builds_the_last_session(monkeypatch):
    calls = frames_spy(monkeypatch)
    L.build_pending(at(date(2026, 11, 15), 12, 0), db=fake_db(), deps=L.Deps(load_day=lambda *a, **k: None))
    assert calls[0]["session"] == S


# ── CLI [C2.8] ───────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("argv", [["--now", "2026-11-13T10:30:30"], ["--loop", "--now", "2026-11-13T10:30:30"],
                                  ["--symbols", "OMH"], ["--build", "--symbols", "OMH"]])
def test_NEGATIVE_now_or_symbols_without_dry_run_refuse(monkeypatch, argv):
    called = []
    monkeypatch.setattr(L, "run_iteration", lambda *a, **k: called.append(1) or {})
    monkeypatch.setattr(L, "loop", lambda *a, **k: called.append(1) or {})
    monkeypatch.setattr(L, "build_pending", lambda *a, **k: called.append(1) or {})
    assert L.main(argv) == 2 and called == []


def test_dry_run_symbols_reads_those_names_and_writes_nothing(monkeypatch):
    db = fake_db(symbols=["OWNER1"])
    monkeypatch.setattr(CO, "_db", lambda: db)
    calls = frames_spy(monkeypatch)
    assert L.main(["--dry-run", "--symbols", "omh,AMD", "--now", "2026-11-13T10:30:30"]) == 0
    assert calls[0]["symbols"] == ["OMH", "AMD"] and calls[0]["load_day"] is RUN._dry_load_day
    assert all(c.writes == 0 for c in db.values())


def test_dry_run_records_the_tile_writes_instead_of_writing(monkeypatch):
    frames_spy(monkeypatch)
    out = L.run_iteration(at(S, 10, 30, 30), db=fake_db(), deps=L.dry_deps(), dry=True, symbols=["OMH"])
    assert out["ran"] and [w[0] for w in out["writes"]] == [{"_id": "OMH"}]


def test_NEGATIVE_the_bare_cli_is_off_or_out_of_window(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "0")
    monkeypatch.setattr(L, "loop", lambda *a, **k: pytest.fail("never"))
    assert L.main(["--loop"]) == 0
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.setattr(RUN, "in_window", lambda now: False)
    assert L.main(["--loop"]) == 0


def test_the_argv_constants_name_this_module():
    assert C.ARGV_LOOP[1:] == ("-m", L.__name__, "--loop") and C.ARGV_BUILD[1:] == ("-m", L.__name__, "--build")
