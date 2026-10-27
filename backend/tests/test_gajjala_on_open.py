"""🔄 Scan on open + 🎯 A+ banner on Gajjala's tab (BUILD_SPEC5 §3.4–§3.7 / WP-B, AMENDMENTS5 A1 / A5 / A10–A13).

Ajay 2026-10-15, verbatim: "When ever I open Gajjala's intiate a new scan of stocks.  In that moment and if there are
any enterable stocks on the top which I see in potential i guess".

The trigger (chart_maps/gajjala/on_demand.py) answers at once and spawns the pass as a SUBPROCESS (A1); the api process
never runs it. Every store here is the in-memory FakeColl set (tests/conftest.py refuses a real MongoClient); every
spawn is a stub except the two real-`_spawn` checks, which run `python -c "sleep"` — never the pass. NEGATIVES are
mandatory: a closed day never spawns, two opens never start two passes, a held lease is waited for, a pass under 60 s
old is reused, a non-owner never triggers, the banner never lists a non-A+ / an older pass's read / anything while
the 5-minute pass is dead, and no served string carries "enterable", "fresh bar", None / NaN, a forecast word or the
b-word.

GOLDEN: `GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_on_open.py -k golden` writes the FE fixture
(frontend/src/components/__fixtures__/gajjala_on_open_golden_2026_10_15.json) from a REAL cron pass and a REAL on-open
pass (run.run_on_demand); without the env the test proves the file IS the served payload, byte for byte.
"""
from __future__ import annotations

import ast
import inspect
import json
import math
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import on_demand as OD
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import R, read_doc, run_route, scan_doc, store_with

ET = ZoneInfo("America/New_York")
S = date(2026, 10, 13)                          # a Tuesday — a market day
PREV = date(2026, 10, 12)
B_WORD = re.compile("b" + "ounc", re.I)
NOTHING_R = "nothing" + " rings"                # the banned phrase (AMENDMENTS5 A13), built so it never sits here
GOLDEN = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "__fixtures__" /
          "gajjala_on_open_golden_2026_10_15.json")
RECIPE = "GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_on_open.py -k golden"
SRC = Path(OD.__file__).read_text(encoding="utf-8")
BF, HF, KF, VCP = "bull_flag", "horizontal_fade", "kiss_fly", "intraday_vcp"


def at(hh, mm, ss=0, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


def naive(dt):
    """The live Mongo shape (not tz-aware): naive UTC (AMENDMENTS5 A5)."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setattr(OD, "_STATE", {"proc": None, "started_at": None})


class FakeProc:
    def __init__(self):
        self.alive = True
        self.pid = 4242

    def poll(self):
        return None if self.alive else 0


class Spawn:
    def __init__(self, raises=False):
        self.calls, self.procs, self.raises = [], [], raises

    def __call__(self, argv, name):
        self.calls.append((list(argv), name))
        if self.raises:
            raise OSError("fork failed")
        p = FakeProc()
        self.procs.append(p)
        return p


def cron_doc(t, *, wall=5.0, n_listed=2, n_read=2, bt=None, day=S, finished=True, **kw):
    d = {"status": "ok", "wall_s": wall, "n_listed": n_listed, "n_read": n_read, "on_demand": False,
         "bars_through_et": bt}
    if finished:
        d["finished_at"] = t + timedelta(seconds=wall)
    d.update(kw)
    return d


def with_cron(t, st=None, **kw):
    """A store whose newest pass is a CRON pass at `t` — written through store.record_pass (latest + latest_cron)."""
    st = st or fake_store()
    st.record_pass(t.astimezone(ET).date(), t, cron_doc(t, day=t.astimezone(ET).date(), **kw))
    return st


def with_open(t, st, **kw):
    """An ON-OPEN pass doc at `t` (moves "latest" only — A10)."""
    d = cron_doc(t, **kw)
    d["on_demand"] = True
    st.record_pass(t.astimezone(ET).date(), t, d, hhmm=t.astimezone(ET).strftime("%H:%M:%S") + "|open",
                   source=ST.LEASE_ON_DEMAND, latest_if_newer=True)
    return st


def set_lease(st, **doc):
    st.coll(ST.STATE).docs[ST.LEASE_ID] = dict({"_id": ST.LEASE_ID}, **doc)


# ── request(): closed (C6) ────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("now", [datetime(2026, 9, 7, 10, 0, tzinfo=ET),          # Labor Day
                                 datetime(2026, 10, 17, 10, 0, tzinfo=ET),         # Saturday
                                 at(3, 59), at(20, 6)],
                         ids=["labor_day", "saturday", "0359", "2006"])
def test_NEGATIVE_closed_never_spawns_and_never_reads_the_lease(now, monkeypatch):
    st = with_cron(at(10, 0))
    reads = []
    monkeypatch.setattr(st, "lease_state", lambda *a, **k: reads.append(a) or {})
    spawn = Spawn()
    r = OD.request(now, store=st, spawn=spawn)
    assert r["state"] == "closed" and spawn.calls == [] and reads == []
    assert r["text"].startswith("market closed — no scan on open; last pass 10:00 ET 2026-10-13")
    assert r["eta_sec"] is None and r["poll_sec"] is None and r["wait_max_sec"] is None


def test_closed_with_no_pass_on_file_says_so():
    r = OD.request(at(3, 30), store=fake_store(), spawn=Spawn())
    assert r == {"state": "closed", "latest_at": None, "eta_sec": None, "poll_sec": None, "wait_max_sec": None,
                 "text": "market closed — no scan on open; no pass on file"}


# ── request(): started / waiting / reused / refused ──────────────────────────────────────────────────────────────
def test_started_spawns_the_cron_entry_once_as_a_subprocess():
    st = with_cron(at(10, 31))
    spawn = Spawn()
    r = OD.request(at(10, 34, 10), store=st, spawn=spawn)
    assert r["state"] == "started"
    assert spawn.calls == [(list(OD.ARGV), OD.PROC_NAME)] and OD.PROC_NAME == "gajjala-on-open"
    assert OD.ARGV == (sys.executable, "-m", "chart_maps.gajjala.run", "--on-demand")
    assert r["text"] == "🔄 scanning on open — started 10:34:10 ET; the board below stays until it lands"
    assert OD._STATE["proc"] is spawn.procs[0] and OD._STATE["started_at"] == RUN._utc(at(10, 34, 10))


def test_NEGATIVE_two_opens_within_a_second_start_one_pass():
    st = with_cron(at(10, 31))
    spawn = Spawn()
    assert OD.request(at(10, 34, 10), store=st, spawn=spawn)["state"] == "started"
    r = OD.request(at(10, 34, 11), store=st, spawn=spawn)
    assert r["state"] == "waiting" and len(spawn.calls) == 1
    assert r["text"] == "🔄 a pass started on open at 10:34:10 ET is still running — showing it when it lands"
    spawn.procs[0].alive = False                                    # the child exited; its doc not yet newer
    assert OD.request(at(10, 34, 40), store=st, spawn=spawn)["state"] == "started" and len(spawn.calls) == 2


def test_NEGATIVE_the_api_process_never_runs_the_pass(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the api process must never run the pass")
    monkeypatch.setattr(RUN, "run_on_demand", boom)
    monkeypatch.setattr(RUN, "run_pass", boom)
    spawn = Spawn()
    assert OD.request(at(10, 34), store=with_cron(at(10, 31)), spawn=spawn)["state"] == "started"
    assert len(spawn.calls) == 1


def test_the_real_spawn_starts_a_new_session_process(monkeypatch):
    seen = []
    real = subprocess.Popen

    def rec(argv, **kw):
        seen.append((list(argv), kw))
        return real(argv, **kw)
    monkeypatch.setattr(subprocess, "Popen", rec)
    proc = OD._spawn([sys.executable, "-c", "import time; time.sleep(0.2)"], OD.PROC_NAME)
    assert proc.wait(timeout=20) == 0
    (argv, kw), = seen
    assert kw["start_new_session"] is True and kw["close_fds"] is True and kw["cwd"] == OD._BACKEND_DIR
    assert "stdout" not in kw and "stderr" not in kw                 # inherited: the child logs to the api's log
    assert (Path(OD._BACKEND_DIR) / "chart_maps" / "gajjala" / "run.py").exists()


def test_the_real_spawn_through_request_one_child_then_waiting(monkeypatch):
    monkeypatch.setattr(OD, "ARGV", (sys.executable, "-c", "import time; time.sleep(0.6)"))
    st = with_cron(at(10, 31))
    assert OD.request(at(10, 34), store=st)["state"] == "started"
    proc = OD._STATE["proc"]
    assert OD.request(at(10, 34, 1), store=st)["state"] == "waiting"
    assert OD._STATE["proc"] is proc
    assert proc.wait(timeout=20) == 0
    assert OD.request(at(10, 34, 2), store=st)["state"] == "started" and OD._STATE["proc"] is not proc
    OD._STATE["proc"].wait(timeout=20)


@pytest.mark.parametrize("stamp", [lambda t: t, naive], ids=["aware", "naive_mongo"])
def test_a_lease_held_by_the_cron_is_waited_for(stamp):
    st = with_cron(at(10, 26))
    t = at(10, 31, 1)
    set_lease(st, status="running", held_by="cron", token="c", claimed_at=stamp(t), started_at=stamp(t),
              last_cron_started_at=stamp(t))
    spawn = Spawn()
    r = OD.request(at(10, 31, 20), store=st, spawn=spawn)
    assert r["state"] == "waiting" and spawn.calls == []
    assert r["text"] == ("🔄 the 5-minute pass started at 10:31:01 ET is still running — showing it when it lands")
    assert r["poll_sec"] <= r["eta_sec"] <= r["wait_max_sec"]


@pytest.mark.parametrize("stamp", [lambda t: t, naive], ids=["aware", "naive_mongo"])
def test_a_lease_held_by_an_open_is_waited_for(stamp):
    st = with_cron(at(10, 26))
    t = at(10, 29, 5)
    set_lease(st, status="running", held_by="on_demand", token="o", claimed_at=stamp(t), od_started_at=stamp(t),
              last_cron_started_at=stamp(at(10, 26)))
    spawn = Spawn()
    r = OD.request(at(10, 29, 30), store=st, spawn=spawn)
    assert r["state"] == "waiting" and spawn.calls == []
    assert r["text"] == "🔄 a pass started on open at 10:29:05 ET is still running — showing it when it lands"


def test_NEGATIVE_a_stale_held_lease_is_not_waited_for():
    st = with_cron(at(10, 26))
    old = at(10, 31) - timedelta(seconds=GC.LEASE_SEC)
    set_lease(st, status="running", held_by="on_demand", token="o", claimed_at=naive(old), od_started_at=naive(old))
    spawn = Spawn()
    assert OD.request(at(10, 31), store=st, spawn=spawn)["state"] == "started" and len(spawn.calls) == 1


def test_reused_under_60_seconds_and_started_past_it():
    assert GC.ON_DEMAND_REUSE_SEC == 60
    t = at(10, 31)
    st = with_cron(t, wall=5.0)                                      # finished 10:31:05
    spawn = Spawn()
    r = OD.request(at(10, 32, 4), store=st, spawn=spawn)             # 59 s after it finished
    assert r["state"] == "reused" and spawn.calls == []
    assert r["text"] == "🔄 the 10:31 ET pass finished 59 s ago — reused (a pass under 60 s old is not re-run)"
    assert r["eta_sec"] is None and r["poll_sec"] is None
    r = OD.request(at(10, 32, 6), store=st, spawn=spawn)             # NEGATIVE boundary: 61 s
    assert r["state"] == "started" and len(spawn.calls) == 1


def test_finished_at_absent_uses_at_plus_wall_and_a_naive_finished_at_reads_utc():
    t = at(10, 31)
    st = with_cron(t, wall=15.0, finished=False)                     # finished 10:31:15
    assert OD._finished_at(st.latest_pass()) == RUN._utc(t + timedelta(seconds=15))
    assert OD.request(at(10, 32, 10), store=st, spawn=Spawn())["state"] == "reused"       # 55 s
    st2 = with_cron(t, wall=5.0, finished=False)                     # finished 10:31:05 → 65 s
    assert OD.request(at(10, 32, 10), store=st2, spawn=Spawn())["state"] == "started"
    st3 = with_cron(t, wall=5.0, finished=False)
    st3.coll(ST.PASSES).docs["latest"]["finished_at"] = naive(at(10, 31, 50))
    assert OD._finished_at(st3.latest_pass()) == RUN._utc(at(10, 31, 50))                 # A5: naive = UTC
    OD._STATE.update(proc=None)                                      # st2's stub child
    assert OD.request(at(10, 32, 10), store=st3, spawn=Spawn())["state"] == "reused"
    assert OD._finished_at(None) is None and OD._finished_at({"wall_s": 3}) is None


def test_a_spawn_that_raises_is_refused():
    r = OD.request(at(10, 34), store=with_cron(at(10, 31)), spawn=Spawn(raises=True))
    assert r["state"] == "refused" and OD._STATE["proc"] is None
    assert r["text"] == "🔄 the scan could not start (store error) — the board shows the last pass"
    assert r["eta_sec"] is None and r["poll_sec"] is None and r["wait_max_sec"] is None


def test_a_dead_store_never_raises():
    dead = fake_store(**{n: FakeColl(fail=True) for n in ST.ALL})
    r = OD.request(at(10, 34), store=dead, spawn=Spawn())
    assert r["state"] in OD.STATES and tuple(r) == OD.RESPONSE_KEYS


# ── A12: before the session's first 5-minute pass ────────────────────────────────────────────────────────────────
def test_A12_an_open_before_the_first_cron_pass_waits_and_never_spawns():
    st = with_cron(at(20, 1, d=PREV))                                # yesterday's last pass only
    spawn = Spawn()
    r = OD.request(at(4, 0, 30), store=st, spawn=spawn)
    assert r["state"] == "waiting" and spawn.calls == []
    assert r["text"] == "🔄 the first 5-minute pass of the session runs at 04:01 ET — showing it when it lands"
    assert r["eta_sec"] == 30 and r["poll_sec"] == GC.ON_DEMAND_POLL_SEC
    with_cron(at(4, 1), st)
    r = OD.request(at(4, 3), store=st, spawn=spawn)
    assert r["state"] == "started" and len(spawn.calls) == 1


def test_A12_NEGATIVE_an_on_open_pass_alone_never_stands_in_for_the_first_cron_pass():
    st = with_cron(at(20, 1, d=PREV))
    with_open(at(10, 20), st)
    spawn = Spawn()
    r = OD.request(at(10, 22), store=st, spawn=spawn)
    assert r["state"] == "waiting" and spawn.calls == []
    assert r["text"] == ("🔄 no 5-minute pass has landed this session yet — the next runs at 10:26 ET; showing it "
                         "when it lands")
    assert r["eta_sec"] == min(GC.ON_DEMAND_WAIT_MAX_SEC, 240)


def test_A12_NEGATIVE_an_old_image_cron_pass_without_the_cron_pointer_never_spawns():
    """Final critic 2026-10-16: a cron of the old image writes "latest" alone (no "latest_cron") and reads an open's
    lease as held → it would skip its tick. The A12 gate reads the pointer ONLY: no pointer → waiting, no spawn;
    the banner keeps its own fallback (tab._cron_ref)."""
    st = fake_store()
    t = at(10, 31)
    old = dict(cron_doc(t), date=S.isoformat(), at=RUN._utc(t), pass_id="2026-10-13|10:31")
    old.pop("on_demand")                                             # the old image's body has no on_demand field
    st.coll(ST.PASSES).docs["latest"] = dict(old, _id="latest")
    assert st.latest_cron_pass() is None and OD._cron_pass(st) is None
    assert GT._cron_ref(st, st.latest_pass())["pass_id"] == "2026-10-13|10:31"     # the banner's fallback stays
    spawn = Spawn()
    r = OD.request(at(10, 34), store=st, spawn=spawn)
    assert r["state"] == "waiting" and spawn.calls == []
    assert r["text"] == ("🔄 no 5-minute pass has landed this session yet — the next runs at 10:36 ET; showing it "
                         "when it lands")
    assert r["eta_sec"] == min(GC.ON_DEMAND_WAIT_MAX_SEC, 120) and st.coll(ST.STATE).docs == {}
    with_cron(at(10, 36), st)                                        # a cron of this image writes the pointer
    assert OD.request(at(10, 37, 10), store=st, spawn=spawn)["state"] == "started" and len(spawn.calls) == 1


def test_A12_NEGATIVE_a_raising_cron_pointer_read_waits_and_never_spawns(monkeypatch):
    st = with_cron(at(10, 31))

    def boom():
        raise RuntimeError("mongo down")
    monkeypatch.setattr(st, "latest_cron_pass", boom)
    spawn = Spawn()
    r = OD.request(at(10, 34), store=st, spawn=spawn)
    assert r["state"] == "waiting" and spawn.calls == []


# ── the response shape ───────────────────────────────────────────────────────────────────────────────────────────
def _every_state():
    t = at(10, 31)
    yield "closed", OD.request(at(3, 0), store=with_cron(t), spawn=Spawn())
    yield "started", OD.request(at(10, 34), store=with_cron(t), spawn=Spawn())
    OD._STATE.update(proc=None)
    yield "reused", OD.request(at(10, 31, 30), store=with_cron(t), spawn=Spawn())
    yield "refused", OD.request(at(10, 34), store=with_cron(t), spawn=Spawn(raises=True))
    st = with_cron(t)
    set_lease(st, status="running", held_by="cron", token="c", claimed_at=at(10, 36), started_at=at(10, 36))
    yield "waiting", OD.request(at(10, 36, 10), store=st, spawn=Spawn())


def test_every_state_serves_exactly_the_response_keys():
    seen = set()
    for want, r in _every_state():
        seen.add(want)
        assert r["state"] == want and tuple(r) == OD.RESPONSE_KEYS
        assert isinstance(r["text"], str) and r["text"]
        if want in ("started", "waiting"):
            assert r["poll_sec"] == GC.ON_DEMAND_POLL_SEC and r["wait_max_sec"] == GC.ON_DEMAND_WAIT_MAX_SEC
            assert r["poll_sec"] <= r["eta_sec"] <= r["wait_max_sec"]
        else:
            assert r["eta_sec"] is None and r["poll_sec"] is None and r["wait_max_sec"] is None    # NEGATIVE
        for w in ("enterable", "fresh bar", "None", "NaN", NOTHING_R) + _forbidden():
            assert w.lower() not in r["text"].lower(), (want, w)
        assert not B_WORD.search(r["text"])
    assert seen == set(OD.STATES)


def test_eta_is_the_last_wall_time_left_clamped():
    st = with_cron(at(10, 31), wall=30.0)
    r = OD.request(at(10, 34), store=st, spawn=Spawn())
    assert r["eta_sec"] == 30                                        # nothing elapsed yet
    st2 = with_cron(at(10, 31), wall=1.0)
    OD._STATE.update(proc=None)
    assert OD.request(at(10, 34), store=st2, spawn=Spawn())["eta_sec"] == GC.ON_DEMAND_POLL_SEC     # floor
    st3 = with_cron(at(10, 31), wall=float("nan"), finished=False)
    OD._STATE.update(proc=None)
    assert OD.request(at(10, 34), store=st3, spawn=Spawn())["eta_sec"] == GC.ON_DEMAND_BUDGET_SEC   # NaN → budget


def test_latest_at_is_the_boards_pass_stamp():
    st = with_cron(at(10, 31))
    r = OD.request(at(10, 34), store=st, spawn=Spawn())
    assert r["latest_at"] == GT.pass_stamp(st.latest_pass()) == RUN._utc(at(10, 31)).isoformat()
    st.coll(ST.PASSES).docs["latest"]["at"] = naive(at(10, 31))      # the Mongo shape → the same stamp
    assert GT.pass_stamp(st.latest_pass()) == r["latest_at"]


# ── the route (C4) ───────────────────────────────────────────────────────────────────────────────────────────────
def test_route_owner_gets_the_request_answer_scrubbed(monkeypatch):
    import auth
    from chart_maps import api as API
    monkeypatch.setattr(auth, "is_admin_email", lambda e: e == "owner@example.com")
    sentinel = {"state": "started", "latest_at": None, "eta_sec": float("nan"), "poll_sec": 5, "wait_max_sec": 90,
                "text": "x"}
    monkeypatch.setattr(OD, "request", lambda *a, **k: dict(sentinel))
    body = json.loads(run_route(API.chart_maps_gajjala_scan(email="owner@example.com")).body)
    assert body == dict(sentinel, eta_sec=None)


def test_route_NEGATIVE_a_non_owner_gets_404_and_never_triggers(monkeypatch):
    import auth
    from fastapi import HTTPException
    from chart_maps import api as API
    monkeypatch.setattr(auth, "is_admin_email", lambda e: False)
    calls = []
    monkeypatch.setattr(OD, "request", lambda *a, **k: calls.append(1) or {})
    with pytest.raises(HTTPException) as e:
        run_route(API.chart_maps_gajjala_scan(email="someone@example.com"))
    assert e.value.status_code == 404 and calls == []


def test_route_NEGATIVE_a_direct_call_with_the_depends_object_is_a_404(monkeypatch):
    import auth
    from fastapi import HTTPException
    from chart_maps import api as API
    seen, calls = [], []
    monkeypatch.setattr(auth, "is_admin_email", lambda e: seen.append(e) or False)
    monkeypatch.setattr(OD, "request", lambda *a, **k: calls.append(1) or {})
    with pytest.raises(HTTPException) as e:
        run_route(API.chart_maps_gajjala_scan())                     # email = the Depends OBJECT
    assert e.value.status_code == 404 and seen == [""] and calls == []


def test_route_is_a_post_and_the_get_never_names_the_trigger():
    from chart_maps import api as API
    posts = [r for r in API.router.routes if getattr(r, "path", "") == "/chart-maps/gajjala/scan"]
    assert posts and all(r.methods == {"POST"} for r in posts)
    assert "on_demand" not in inspect.getsource(API.chart_maps_gajjala)
    src = inspect.getsource(API.chart_maps_gajjala_scan)
    assert "is_admin_email(" in src and "404" in src


# ── A1: the trigger's source ─────────────────────────────────────────────────────────────────────────────────────
def _code_only(src: str) -> str:
    """The module minus its docstrings and comments (what runs)."""
    tree = ast.parse(src)
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = getattr(node, "body", None) or []
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant):
                docs.add((b[0].lineno, b[0].end_lineno))
    lines = src.splitlines()
    keep = [ln.split("#", 1)[0] for i, ln in enumerate(lines, 1) if not any(a <= i <= z for a, z in docs)]
    return "\n".join(keep)


def test_A1_the_trigger_spawns_a_subprocess_and_imports_no_pass_code():
    assert re.search(r"subprocess\.Popen\(", SRC) and re.search(r"start_new_session=True", SRC)
    bad = re.compile(r"threading\.Thread\(|notify_|send_to_user|alert_status|record_status|import pandas|"
                     r"from \. import (bars|detectors|scanner|alerts|potential)")
    assert not bad.search(SRC), bad.search(SRC)
    code = _code_only(SRC)
    assert "run_pass(" not in code and "run_on_demand(" not in code
    assert not re.search(r"chart_maps\.gajjala\.(bars|detectors|scanner|alerts|potential)|import pandas", code)


def test_A1_NEGATIVE_the_source_guard_bites():
    bad = re.compile(r"threading\.Thread\(|notify_|send_to_user|from \. import (bars|detectors|scanner|alerts|potential)")
    for s in ("threading.Thread(target=f).start()", "from . import potential", "from . import bars as B",
              "notify_owner()"):
        assert bad.search(s), s
    assert "run_pass(" in _code_only("def f():\n    RUN.run_pass(now)\n")
    assert "run_pass(" not in _code_only('def f():\n    """run_pass( in a docstring"""\n    x = 1  # run_pass(\n')


# ── scan_block (§3.6 b) ──────────────────────────────────────────────────────────────────────────────────────────
def _forbidden() -> tuple:
    from chart_maps.high_beta_tab import FORBIDDEN_WORDS
    return tuple(FORBIDDEN_WORDS)


def _scan_strings(b: dict) -> list:
    return [v for v in b.values() if isinstance(v, str)]


def _pd(t, **kw):
    d = cron_doc(t, **kw)
    d.update({"date": t.astimezone(ET).date().isoformat(), "at": RUN._utc(t)})
    return d


def test_scan_idle_on_open_and_cron_lines():
    on = _pd(at(10, 41, 20), bt="10:40", on_demand=True)
    b = GT.scan_block(on, {}, at(10, 42), in_window=True, session=S)
    assert b["state"] == "idle" and b["on_demand"] is True and b["scanning_text"] is None
    assert b["as_of_text"] == b["text"] == "🔄 scanned on open 10:41 ET · bars through 10:40"
    assert b["started_at_et"] == "10:41" and b["bars_through_et"] == "10:40"
    cr = _pd(at(10, 36), bt="10:35")
    b = GT.scan_block(cr, {}, at(10, 37), in_window=True, session=S)
    assert b["text"] == "last pass 10:36 ET · bars through 10:35" and b["on_demand"] is False
    assert GT.scan_block(_pd(at(10, 36)), {}, at(10, 37), in_window=True, session=S)["text"] == "last pass 10:36 ET"
    assert b["rescan_label"] == "🔄 scan now"
    assert b["rescan_title"] == ("Run one pass now — both push gates run dry, so this pass rings no device; the last "
                                 "pass is reused when it finished under 60 s ago")


def test_scan_earlier_session_none_and_closed():
    old = _pd(at(20, 1, d=PREV))
    assert GT.scan_block(old, {}, at(4, 3), in_window=True, session=S)["text"] == \
        "last pass 2026-10-12 20:01 ET — none yet this session"
    assert GT.scan_block(None, {}, at(4, 3), in_window=True, session=S)["text"] == "no pass on file yet"
    b = GT.scan_block(old, {"held": True, "held_by": "cron"}, at(21, 0, d=PREV), in_window=False, session=PREV)
    assert b["state"] == "closed" and b["scanning_text"] is None                     # NEGATIVE: never "scanning"
    assert b["text"] == "market closed — last pass 20:01 ET 2026-10-12"
    assert GT.scan_block(None, {}, at(3, 0), in_window=False, session=PREV)["text"] == "market closed — no pass on file"


def test_scan_scanning_lines_on_open_and_cron():
    cr = _pd(at(10, 36))
    lease = {"held": True, "held_by": "on_demand", "holder_started_at": RUN._utc(at(10, 38, 7)),
             "claimed_at": RUN._utc(at(10, 38, 7))}
    b = GT.scan_block(cr, lease, at(10, 38, 20), in_window=True, session=S)
    assert b["state"] == "scanning" and b["started_at_et"] == "10:38:07"
    assert b["text"] == b["scanning_text"] == ("scanning… a pass started on open at 10:38:07 ET — the board below "
                                               "is the 10:36 ET read until it lands")
    assert b["as_of_text"] == "last pass 10:36 ET"
    lease = dict(lease, held_by="cron", holder_started_at=RUN._utc(at(10, 41, 1)))
    b = GT.scan_block(cr, lease, at(10, 41, 20), in_window=True, session=S)
    assert b["text"] == "scanning… the 5-minute pass started at 10:41:01 ET — the board below is the 10:36 ET read until it lands"
    b = GT.scan_block(None, lease, at(10, 41, 20), in_window=True, session=S)
    assert b["text"] == "scanning… the 5-minute pass started at 10:41:01 ET — the board fills when it lands"


def test_NEGATIVE_a_stale_lease_never_shows_scanning():
    st = with_cron(at(10, 26))
    old = at(10, 36) - timedelta(seconds=GC.LEASE_SEC)
    set_lease(st, status="running", held_by="on_demand", token="o", claimed_at=naive(old), od_started_at=naive(old))
    out = GT.build("bull_flag", now=at(10, 36), store=st)
    assert out["scan"]["state"] == "idle" and out["scan"]["scanning_text"] is None
    set_lease(st, status="running", held_by="on_demand", token="o", claimed_at=naive(at(10, 35, 50)),
              od_started_at=naive(at(10, 35, 50)))
    assert GT.build("bull_flag", now=at(10, 36), store=st)["scan"]["state"] == "scanning"


def test_W6_a_pass_that_re_read_fewer_names_says_how_many_kept_their_read():
    b = GT.scan_block(_pd(at(10, 41, 20), on_demand=True, n_listed=9, n_read=7), {}, at(10, 42), in_window=True,
                      session=S)
    assert b["note"] == "2 of 9 names kept their last pass read"
    cr = GT.scan_block(_pd(at(10, 41), n_listed=9, n_read=8), {}, at(10, 42), in_window=True, session=S)
    assert cr["note"] == "1 of 9 names kept their last pass read"                    # A13: whenever, cron too
    for n_l, n_r in ((9, 9), (None, 3), (3, None), (0, 0)):                           # NEGATIVE
        assert GT.scan_block(_pd(at(10, 41), n_listed=n_l, n_read=n_r), {}, at(10, 42), in_window=True,
                             session=S)["note"] is None


def test_scan_strings_carry_no_banned_word():
    leases = ({}, {"held": True, "held_by": "on_demand", "holder_started_at": RUN._utc(at(10, 38))},
              {"held": True, "held_by": "cron", "claimed_at": RUN._utc(at(10, 41))})
    docs = (None, _pd(at(10, 41, 20), on_demand=True, bt="10:40", n_listed=3, n_read=1), _pd(at(10, 36)),
            _pd(at(20, 1, d=PREV)))
    for doc in docs:
        for lease in leases:
            for win in (True, False):
                for s in _scan_strings(GT.scan_block(doc, lease, at(10, 42), in_window=win, session=S)):
                    low = s.lower()
                    for w in ("fresh bar", "enterable", NOTHING_R) + _forbidden():
                        assert w not in low, (w, s)
                    assert "None" not in s and not re.search(r"\bnan\b", low) and not B_WORD.search(s)


# ── aplus_block (§3.6 c, A10 / A11) ──────────────────────────────────────────────────────────────────────────────
NOW = at(10, 31)


def passes_at(t=NOW, *, on_demand=False, cron_at=None, n_listed=None, n_read=None):
    """Pass docs: "latest" at `t` (an on-open pass when `on_demand`) + "latest_cron" at `cron_at` (default `t` for a
    cron latest, none for an on-open one)."""
    lat = {"_id": "latest", "date": S.isoformat(), "at": RUN._utc(t), "status": "ok", "on_demand": on_demand,
           "n_listed": n_listed, "n_read": n_read, "pass_id": "x"}
    out = [lat]
    c = cron_at if cron_at is not None else (None if on_demand else t)
    if c is not None:
        out.append({"_id": "latest_cron", "date": c.astimezone(ET).date().isoformat(), "at": RUN._utc(c),
                    "status": "ok", "pointer": "latest_cron"})
    return out


def board(reads: dict, *, sub=BF, now=NOW, upd=None, passes=None, extra_reads=(), scans=None):
    """reads = {SYM: {setup: R(...)}}; every read doc stamped `upd` (default: the pass clock)."""
    upd = upd if upd is not None else RUN._utc(passes[0]["at"] if passes else now)
    docs = [read_doc(s, setups, updated_at=upd, at=upd) for s, setups in reads.items()] + list(extra_reads)
    sc = scans if scans is not None else [scan_doc(s) for s in reads]
    st = store_with(reads=docs, scans=sc, passes=passes if passes is not None else passes_at(now))
    return GT.build(sub, now=now, store=st), st


def rows(out):
    return [(r["symbol"], r["setup"]) for r in out["enterable"]["rows"]]


def test_one_aplus_row_with_the_card_words_and_a_deep_link():
    out, _ = board({"GGA": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:30", broke=True)}})
    e = out["enterable"]
    (row,) = e["rows"]
    assert row == {"symbol": "GGA", "setup": BF, "setup_label": "🚩 Bull Flag", "frame": "5m", "trigger": 4.12,
                   "stop": 3.95, "risk_pct": 4.13, "since_et": "10:30", "variant_label": None, "grade_label": None,
                   "href": "/chart-maps?tab=gajjala&sub=bull_flag&focus=GGA",
                   "text": "GGA · 🚩 Bull Flag · trigger 4.12 · stop 3.95 (−4.1%) · A+ since 10:30 ET",
                   "broker_text": None,     # WIDENED 2026-10-17: DECISIONS12 D2 / AMENDMENTS12 F4 — the 🚫 tag key (non-owner: null)
                   "trader_text": None}     # WIDENED 2026-10-27: BUILD_SPEC26 §3.3 — the 📌 tag key (untagged: null)
    assert e["title"] == "🎯 A+ — traded through the trigger and the bar closed (GG's entry) · 1 · UNMEASURED"
    assert e["empty_text"] is None


@pytest.mark.parametrize("read", [
    R(BF, "triggered", entry_bar_t="2026-10-13 10:10", bars_since_entry=4, broke=True),
    R(BF, "forming", ready=True, trigger=4.10),
    R(BF, "forming", ready=False, base={"bars": 1}),
    R(BF, "partial", missed=["k3_vol"], broke=True),
    R(BF, "stopped", entry_bar_t="2026-10-13 10:00", broke=True),
    R(BF, "invalid", reason="x"), R(BF, "none")],
    ids=["triggered", "forming_armed", "forming", "partial", "stopped", "invalid", "none"])
def test_NEGATIVE_the_banner_lists_only_aplus(read):
    out, _ = board({"XXX": {BF: read}})
    assert out["enterable"]["rows"] == [] and out["enterable"]["title"] is None
    assert out["enterable"]["empty_text"] == "🎯 No A+ right now · last pass 10:31 ET · UNMEASURED"


def test_A11_a_variant_and_a_grade_aplus_are_listed_with_the_cards_own_words():
    # the long_flag band is empty since 2026-10-18 — synthetic variant, the mechanism is what is tested
    out, _ = board({"LNG": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:30", variant="long_flag", broke=True)},
                    "VCB": {VCP: R(VCP, "aplus", entry_bar_t="2026-10-13 10:30", grade=GC.VCP_B_GRADE, broke=True,
                                   trigger=None, stop=None, risk_pct=None)}})
    by = {r["symbol"]: r for r in out["enterable"]["rows"]}
    assert by["LNG"]["variant_label"] == GT.variant_label({"variant": "long_flag"})
    assert GT.variant_label({"variant": "long_flag"}) in by["LNG"]["text"]
    assert by["VCB"]["grade_label"] and by["VCB"]["grade_label"] in by["VCB"]["text"]
    assert "trigger" not in by["VCB"]["text"] and "stop" not in by["VCB"]["text"]        # only when present


def test_A11_an_aplus_of_an_older_pass_is_never_listed_and_its_card_says_read_at():
    t = at(10, 36)
    old = read_doc("OLD", {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:30", broke=True)},
                   updated_at=RUN._utc(NOW), at=RUN._utc(NOW))
    out, _ = board({"NEW": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:35", broke=True)}}, now=at(10, 37),
                   passes=passes_at(t), extra_reads=[old], scans=[scan_doc("NEW"), scan_doc("OLD")])
    assert rows(out) == [("NEW", BF)]                                # NEGATIVE: OLD's read is the 10:31 pass's
    chips = {t_["symbol"]: t_["gajjala"]["chips"]["read_at"] for t_ in out["tiles"]}
    assert chips == {"NEW": None, "OLD": "read at the 10:31 ET pass"}


def test_A11_no_freshness_filter_at_the_request_clock():
    out, _ = board({"GGA": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:20", broke=True)}}, now=at(10, 34),
                   passes=passes_at(NOW))                            # the bar closed 14 min before the request
    assert rows(out) == [("GGA", BF)]


def test_NEGATIVE_a_non_listed_symbol_is_never_on_the_banner():
    stray = read_doc("STRAY", {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:30", broke=True)},
                     updated_at=RUN._utc(NOW), at=RUN._utc(NOW))
    out, _ = board({"GGA": {BF: R(BF, "forming")}}, extra_reads=[stray])               # STRAY has no scan doc
    assert rows(out) == []


def test_NEGATIVE_closed_and_no_pass_list_nothing():
    fri = date(2026, 10, 16)
    st = store_with(reads=[read_doc("FRI", {BF: R(BF, "aplus", entry_bar_t="2026-10-16 15:50")}, day=fri)],
                    scans=[scan_doc("FRI", day=fri)],
                    passes=[{"_id": "latest", "date": fri.isoformat(), "at": RUN._utc(at(20, 1, d=fri)),
                             "status": "ok"}])
    out = GT.build(BF, now=datetime(2026, 10, 17, 15, 0, tzinfo=timezone.utc), store=st)
    assert out["enterable"]["rows"] == []
    assert out["enterable"]["empty_text"] == "🎯 No A+ · market closed — last pass 20:01 ET 2026-10-16 · UNMEASURED"
    assert out["scan"]["state"] == "closed"
    out = GT.build(BF, now=at(3, 0), store=store_with())
    assert out["enterable"]["empty_text"] == "🎯 No A+ · market closed — no pass on file · UNMEASURED"
    reads = {"GGA": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:30")}}
    out, _ = board(reads, passes=[])
    assert out["enterable"]["rows"] == []
    assert out["enterable"]["empty_text"] == "🎯 No A+ right now · no pass this session yet · UNMEASURED"


def test_a_naive_utc_pass_and_read_still_list_the_aplus():
    t = NOW
    p = passes_at(t)
    for d in p:
        d["at"] = naive(t)
    out, _ = board({"GGA": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:30", broke=True)}}, passes=p,
                   upd=naive(t))
    assert rows(out) == [("GGA", BF)] and out["enterable"]["rows"][0]["since_et"] == "10:30"
    assert out["pass"]["at"] == RUN._utc(t).isoformat()


def test_a_15_minute_fade_aplus_says_so_and_the_order_is_newest_then_setups():
    out, _ = board({"FAD": {HF: R(HF, "aplus", frame="15m", entry_bar_t="2026-10-13 10:30", broke=True)},
                    "OLD": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:25", broke=True)},
                    "TWO": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:30", broke=True),
                            KF: R(KF, "aplus", entry_bar_t="2026-10-13 10:30", broke=True)}})
    assert rows(out) == [("TWO", BF), ("TWO", KF), ("FAD", HF), ("OLD", BF)]
    fad = next(r for r in out["enterable"]["rows"] if r["symbol"] == "FAD")
    assert fad["text"].endswith(" · A+ since 10:30 ET (15-min bar)") and fad["frame"] == "15m"
    assert out["enterable"]["title"].startswith("🎯 A+") and " · 4 · UNMEASURED" in out["enterable"]["title"]


def test_empty_in_window_says_scanned_on_open_or_last_pass():
    reads = {"GGA": {BF: R(BF, "forming")}}
    out, _ = board(reads, passes=passes_at(at(10, 33, 10), on_demand=True, cron_at=NOW), now=at(10, 34))
    assert out["enterable"]["empty_text"] == "🎯 No A+ right now · scanned on open 10:33 ET · UNMEASURED"
    out, _ = board(reads)
    assert out["enterable"]["empty_text"] == "🎯 No A+ right now · last pass 10:31 ET · UNMEASURED"


def test_A10_a_dead_cron_empties_the_banner_and_opens_never_clear_stale():
    reads = {"GGA": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:50", broke=True)}}
    p = passes_at(at(10, 51), on_demand=True, cron_at=at(10, 0))     # the cron last ran 10:00; an open at 10:51
    out, _ = board(reads, passes=p, now=at(10, 52))
    assert out["enterable"]["rows"] == []                            # NEGATIVE: the open's A+ is not shown
    assert out["enterable"]["empty_text"] == ("🎯 No A+ shown · the 5-minute pass has not run since 10:00 ET — no "
                                              "alert can ring without it; the banner waits for it · UNMEASURED")
    assert out["pass"]["stale"] is True and "10:00 ET" in out["pass"]["stale_text"]
    assert out["scan"]["text"] == "🔄 scanned on open 10:51 ET"
    p = passes_at(at(10, 51), on_demand=True)                        # no cron pass this session at all
    out, _ = board(reads, passes=p, now=at(10, 52))
    assert out["enterable"]["rows"] == [] and out["pass"]["stale"] is True
    assert "has not run this session" in out["enterable"]["empty_text"]
    p = passes_at(at(10, 51), on_demand=True, cron_at=at(10, 46))    # positive control: a live cron
    out, _ = board(reads, passes=p, now=at(10, 52))
    assert rows(out) == [("GGA", BF)] and out["pass"]["stale"] is False


def test_W19_the_note_slices_ggs_entry_quote_and_never_misattributes_k1():
    from chart_maps.gajjala import playbook as PB
    q = GT._entry_quote()
    item = next(it for it in PB.ENTRY[1] if it["ts"] == "1:40:56–1:41:55")
    assert q and q in item["text"] and q.startswith("I'll enter right at the break") and not q.endswith(".")
    out, _ = board({"GGA": {BF: R(BF, "forming")}})
    note = out["enterable"]["note"]
    assert f"“{q}” (S8 1:40:56–1:41:55)" in note and "UNMEASURED" in note and "K1" in note
    assert "extended periods" not in note and "rings no device" in note


def test_banner_strings_carry_no_banned_word():
    p = passes_at(at(10, 51), on_demand=True, cron_at=at(10, 0))
    # the long_flag band is empty since 2026-10-18 — synthetic variant, the mechanism is what is tested
    outs = [board({"GGA": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:30", variant="long_flag")}})[0],
            board({"GGA": {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:50")}}, passes=p, now=at(10, 52))[0],
            board({"GGA": {BF: R(BF, "forming")}})[0], GT.build(BF, now=at(3, 0), store=store_with())]
    for out in outs:
        e = out["enterable"]
        texts = [e["title"], e["empty_text"], e["note"]] + [r["text"] for r in e["rows"]]
        for s in (x for x in texts if x):
            low = s.lower()
            for w in ("enterable", "fresh bar", NOTHING_R) + _forbidden():
                assert w not in low, (w, s)
            assert "None" not in s and "NaN" not in s and not B_WORD.search(s)


# ── every sub · one stamp · soft ─────────────────────────────────────────────────────────────────────────────────
def test_every_sub_serves_scan_enterable_and_pass_at_with_one_stamp():
    from tests.test_gajjala_tab import ordering_store
    st = ordering_store()
    r = OD.request(NOW, store=st, spawn=Spawn())
    for k, _e, _l in GC.SUBS:
        out = GT.build(k, now=NOW, store=st)
        assert out["scan"]["state"] == "idle" and out["scan"]["text"] == "last pass 10:31 ET", k
        assert isinstance(out["enterable"], dict) and "rows" in out["enterable"], k
        assert out["pass"]["at"] == r["latest_at"] == RUN._utc(NOW).isoformat(), k
        assert [x["symbol"] for x in out["enterable"]["rows"]] == ["BBB", "AAA"], k        # A+ newest first


def test_NEGATIVE_a_raising_lease_read_or_banner_never_takes_down_the_board(monkeypatch):
    from tests.test_gajjala_tab import ordering_store

    def boom(*a, **k):
        raise RuntimeError("down")
    st = ordering_store()
    monkeypatch.setattr(st, "lease_state", boom)
    out = GT.build(BF, now=NOW, store=st)
    assert out["scan"]["state"] == "idle" and [t["symbol"] for t in out["tiles"]][:2] == ["BBB", "AAA"]
    monkeypatch.setattr(GT, "aplus_block", boom)
    monkeypatch.setattr(GT, "scan_block", boom)
    out = GT.build(BF, now=NOW, store=ordering_store())
    assert out["enterable"] is None and out["scan"] is None
    assert [t["symbol"] for t in out["tiles"]][:2] == ["BBB", "AAA"]                 # the A+ tiles still served


def test_read_at_chip_only_when_the_read_is_older_than_the_pass():
    out, _ = board({"GGA": {BF: R(BF, "forming")}}, upd=RUN._utc(NOW - timedelta(minutes=5)))
    assert out["tiles"][0]["gajjala"]["chips"]["read_at"] == "read at the 10:26 ET pass"
    out, _ = board({"GGA": {BF: R(BF, "forming")}})                                    # NEGATIVE: equal
    assert out["tiles"][0]["gajjala"]["chips"]["read_at"] is None
    out, _ = board({"GGA": {BF: R(BF, "forming")}}, upd=RUN._utc(NOW - timedelta(milliseconds=500)))
    assert out["tiles"][0]["gajjala"]["chips"]["read_at"] is None                      # under 1 s


# ── GOLDEN: the FE fixture IS the served payload (a REAL cron pass, then a REAL on-open pass) ───────────────────
def golden_store():
    from tests.test_gajjala_run import at as rat, make_deps, snap_row
    st = fake_store()
    cron_deps = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=rat(10, 35)), "NOPE": snap_row(1.0, 0.95)})[0]
    assert RUN.run_pass(rat(10, 36), store=st, deps=cron_deps)["ran"]
    deps, snap, send, status = make_deps()
    out = RUN.run_on_demand(rat(10, 41, ss=20), store=st, deps=deps)
    assert out["ran"] and out["on_demand"] is True and len(snap.calls) == 1
    assert send.calls == [] and deps.send_potential.calls == []                        # K2: an open rings no device
    assert status.calls == [] and deps.record_potential_status.calls == []
    return st


def golden_payload() -> str:
    st = golden_store()
    now = at(10, 42)
    # WIDENED 2026-10-17: DECISIONS12 D3 / BUILD_SPEC12 R10 — the golden is the OWNER's payload (the 🚫 strip block)
    doc = {"_recipe": RECIPE, "boards": {"bull_flag": GT.build("bull_flag", now=now, store=st, owner=True),
                                         "potential": GT.build("potential", now=now, store=st, owner=True),
                                         "playbook": GT.build("playbook", now=now, store=st, owner=True)}}
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"


def test_on_open_golden_fixture_is_the_served_payload():
    text = golden_payload()
    if os.environ.get("GG_WRITE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8")
    assert GOLDEN.exists(), f"missing {GOLDEN.name} — run: {RECIPE}"
    assert GOLDEN.read_text(encoding="utf-8") == text, f"the golden fixture drifted — run: {RECIPE}"
    boards = json.loads(text)["boards"]
    for k, b in boards.items():
        assert b["scan"]["as_of_text"] == "🔄 scanned on open 10:41 ET · bars through 10:40", k
        assert b["pass"]["on_demand"] is True and b["pass"]["stale"] is False, k
        assert [(r["symbol"], r["setup"]) for r in b["enterable"]["rows"]] == [("GGA", "bull_flag")], k
        assert b["enterable"]["rows"][0]["href"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=GGA", k
    assert "NaN" not in text and not B_WORD.search(text) and "enterable stocks" not in text


# ── final critic 2026-10-16: an open that re-read nothing is still reused (K4 / C7) ───────────────────────────────
def test_C7_an_open_that_re_read_nothing_is_still_reused_under_60_s():
    """A13 leaves `latest` on the cron pass when an open re-read 0 names; its lease release (held_by on_demand, status
    done) still counts for the 60 s reuse — otherwise every open re-spawned and the board said scanning for 90 s."""
    st = with_cron(at(10, 6))                                                   # latest = the cron pass, finished 10:06:05
    set_lease(st, held_by="on_demand", status="done", token="t-open", claimed_at=at(10, 7, 0),
              od_started_at=at(10, 7, 0), done_at=at(10, 7, 1))
    spawn = Spawn()
    r = OD.request(at(10, 7, 10), store=st, spawn=spawn)
    assert r["state"] == "reused" and spawn.calls == []
    assert r["text"] == "🔄 a scan on open finished 9 s ago — reused (a pass under 60 s old is not re-run)"
    assert r["eta_sec"] is None and r["poll_sec"] is None
    set_lease(st, held_by="on_demand", status="done", token="t-open", claimed_at=at(10, 7, 0),
              od_started_at=at(10, 7, 0), done_at=naive(at(10, 7, 1)))        # A5: the live Mongo shape
    assert OD.request(at(10, 7, 20), store=st, spawn=spawn)["state"] == "reused" and spawn.calls == []
    assert OD.request(at(10, 8, 5), store=st, spawn=spawn)["state"] == "started"   # 64 s later: past the reuse
    assert len(spawn.calls) == 1


def test_C7_NEGATIVE_a_cron_release_or_a_running_open_never_stands_in_for_the_reuse():
    st = with_cron(at(10, 6))                                                   # finished 10:06:05 → 65 s at 10:07:10
    set_lease(st, held_by="cron", status="done", token="t-cron", claimed_at=at(10, 7, 0), started_at=at(10, 7, 0),
              last_cron_started_at=at(10, 7, 0), done_at=at(10, 7, 1))
    assert OD.request(at(10, 7, 10), store=st, spawn=Spawn())["state"] == "started"   # a cron release is not an open
    st2 = with_cron(at(10, 6))
    set_lease(st2, held_by="on_demand", status="running", token="t-open", claimed_at=at(10, 7, 0),
              od_started_at=at(10, 7, 0))
    r = OD.request(at(10, 7, 10), store=st2, spawn=Spawn())
    assert r["state"] == "waiting" and r["text"].startswith("🔄 a pass started on open")  # running: wait, not reuse


def test_lease_state_serves_status_and_an_aware_done_at():
    """The store contract the reuse check reads (final critic 2026-10-16): status + done_at, naive → UTC-aware."""
    st = fake_store()
    set_lease(st, held_by="on_demand", status="done", token="t", claimed_at=naive(at(10, 7, 0)),
              od_started_at=naive(at(10, 7, 0)), done_at=naive(at(10, 7, 1)))
    ls = st.lease_state(at(10, 7, 10))
    assert ls["status"] == "done" and ls["held"] is False
    assert ls["done_at"].tzinfo is not None and ls["done_at"] == at(10, 7, 1)
