"""👀 Gajjala's Watch — refix 2026-11-15 (critic round).

1. A real `time.sleep` always wakes a little late. The old post-sleep test `wall + settle > next_tick` therefore ended
   every slot before the tick+4:30 iteration, so the bar that closes at each :x0 / :x5 was never read as the latest
   bar (its cross counted `missed_fetch`, never pushed). The loop now ends after a sleep only on a wake in another
   slot or a wake more than BAR_SETTLE_SEC past the planned start (host sleep inside the slot).
2. The on/off switch now stops the `--build` child too: off → no build request from the API, and the child itself
   fetches nothing.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import build as BLD
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import loop as L
from tests.test_gajjala_watch_api_2026_11_15 import OWNER, wired, db  # noqa: F401  (fixtures)
from tests.test_gajjala_watch_build_2026_11_15 import S, at
from tests.test_gajjala_watch_loop_2026_11_15 import TICK, Clock, deps_for, fake_db, record_iterations


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


class LateClock(Clock):
    """Every sleep wakes `late` seconds after the asked time (a real OS sleep); `jumps` still adds host sleep."""
    def __init__(self, t, late, jumps=None):
        super().__init__(t, jumps)
        self.late = late

    def sleep(self, sec):
        super().sleep(sec)
        self.t += timedelta(seconds=self.late)


# ── 1. the slot keeps all five iterations on a late wake ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("late", [0.001, 0.002, 0.5, 5.0])
def test_a_late_wake_keeps_the_tick_plus_4_30_iteration(monkeypatch, late):
    clock = LateClock(TICK + timedelta(seconds=2), late)
    calls = record_iterations(monkeypatch, clock)
    out = L.loop(deps=deps_for(clock), db=fake_db())
    assert len(calls) == 5 and out["n"] == 5
    assert out["reason"] == "no time left in the slot"
    assert [c["now"].strftime("%H:%M") for c in calls] == ["10:01", "10:02", "10:03", "10:04", "10:05"]


def test_the_last_iteration_reads_the_bar_that_closes_at_the_next_x5_tick(monkeypatch):
    from chart_maps.gajjala import run_1m as R1
    clock = LateClock(TICK + timedelta(seconds=2), 0.002)
    calls = record_iterations(monkeypatch, clock)
    L.loop(deps=deps_for(clock), db=fake_db())
    assert R1._bar_label(calls[-1]["now"]) == TICK + timedelta(minutes=4)


def test_NEGATIVE_a_wake_more_than_the_settle_late_inside_the_slot_ends_the_loop(monkeypatch):
    clock = LateClock(TICK + timedelta(seconds=2), 0.002, jumps={2: GC.BAR_SETTLE_SEC + 1})
    calls = record_iterations(monkeypatch, clock)
    out = L.loop(deps=deps_for(clock), db=fake_db())
    assert len(calls) == 2 and out["n"] == 2 and out["reason"] == "slot passed (host sleep)"


def test_NEGATIVE_a_wake_in_the_next_slot_still_ends_the_loop_on_a_late_clock(monkeypatch):
    clock = LateClock(TICK + timedelta(seconds=8), 0.002, jumps={1: 6 * 60})
    calls = record_iterations(monkeypatch, clock)
    out = L.loop(deps=deps_for(clock), db=fake_db())
    assert len(calls) == 1 and out["reason"] == "slot passed (host sleep)"


def test_NEGATIVE_no_sixth_iteration_on_a_late_clock(monkeypatch):
    clock = LateClock(TICK + timedelta(seconds=2), 0.002)
    calls = record_iterations(monkeypatch, clock)
    L.loop(deps=deps_for(clock), db=fake_db())
    assert all(c["now"] < TICK + timedelta(minutes=5) for c in calls)


# ── 2. off stops the build child ─────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_build_child_off_fetches_nothing(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "0")
    monkeypatch.setattr(BLD, "frames", lambda *a, **k: pytest.fail("off → no minute fetch"))
    db = fake_db(symbols=["OMH", "AMD"])
    out = L.build_pending(at(S, 12, 0), db=db, deps=L.Deps(load_day=lambda *a, **k: None))
    assert out["built"] == [] and out["reason"] == "off" and db[C.COLL_TILES].docs == {}


def test_NEGATIVE_the_build_cli_off_runs_nothing(monkeypatch):
    monkeypatch.setenv(C.ENV_ENABLED, "0")
    monkeypatch.setattr(L, "build_pending", lambda *a, **k: pytest.fail("off → no build"))
    assert L.main(["--build"]) == 0


def test_the_build_cli_on_builds(monkeypatch):
    called = []
    monkeypatch.setattr(L, "build_pending", lambda *a, **k: called.append(1) or {})
    monkeypatch.setattr(L, "_levels", lambda *a, **k: 0)        # 📐 2026-11-23 [C1]: nothing read → still ONE call
    assert L.main(["--build"]) == 0 and called == [1]


def test_NEGATIVE_off_add_requests_no_build_child(wired, monkeypatch):  # noqa: F811
    monkeypatch.setenv(C.ENV_ENABLED, "0")
    r = wired.post(C.API_PATH + "/symbols/AMD", headers={"X-User-Email": OWNER})
    assert r.json()["state"] == "added" and wired.spawns == []


def test_on_add_still_requests_the_build_child(wired):  # noqa: F811
    assert CO.enabled() is True
    assert wired.post(C.API_PATH + "/symbols/AMD", headers={"X-User-Email": OWNER}).json()["state"] == "added"
    assert len(wired.spawns) == 1 and API._BUILD["proc"] is not None
