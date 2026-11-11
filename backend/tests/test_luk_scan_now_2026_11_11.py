"""🔄 Luk's scan-now button — the trigger (spec lukscan WP-LUK-TRIGGER, 2026-11-11).

Ajay 2026-11-11, verbatim: "Can you put an ondeman scan button for Luk' scans too"

`gajjala.on_demand.request(profile=…)` runs 🚩's ONE order for another package's pass; `luk.on_demand` is 🥇's profile
(its child argv, its closed check, its kill switch, its slot gate, its words) and `POST /chart-maps/luk/scan` is the
owner's entry. NEGATIVES are mandatory: the GG5 / GG1 / GGA answers equal LITERAL dicts captured from the UNMODIFIED
on_demand.py before the edit (no self-compare); a tap before this slot's cron 🥇 pass settled never spawns; no_room
never spawns and carries no poll plan; a closed day never reads the lease; LUK off never spawns; a raising store is
refused, never a raise; a non-owner gets the stealth 404 and the trigger is never called.
"""
from __future__ import annotations

import ast
import inspect
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import on_demand as OD
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")


# ── N7: GG5 / GG1 / GGA byte identity against LITERALS (captured from the unmodified on_demand.py) ───────────────
S_GG = date(2026, 10, 13)                       # a Tuesday — a market day
PY = "<python>"                                 # sys.executable, normalised so the literal is portable


def _gg_at(hh, mm, ss=0, d=S_GG):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


class _Proc:
    def __init__(self):
        self.alive, self.pid = True, 4242

    def poll(self):
        return None if self.alive else 0


class _Spawn:
    def __init__(self, raises=False):
        self.calls, self.procs, self.raises = [], [], raises

    def __call__(self, argv, name):
        self.calls.append(([PY if a == sys.executable else a for a in argv], name))
        if self.raises:
            raise OSError("fork failed")
        p = _Proc()
        self.procs.append(p)
        return p


def _gg_store(v):
    return ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL}, variant=v)


def _gg_cron(st, t, wall=5.0):
    st.record_pass(t.astimezone(ET).date(), t, {"status": "ok", "wall_s": wall, "n_listed": 2, "n_read": 2,
                                                "on_demand": False, "bars_through_et": None,
                                                "finished_at": t + timedelta(seconds=wall)})
    return st


def _gg_lease(st, **doc):
    st.coll(ST.STATE).docs[ST.LEASE_ID] = dict({"_id": ST.LEASE_ID}, **doc)


def gg_table(v) -> dict:
    """{scenario: (answer, spawn calls)} — 🚩's request() for `v` (None = the GG5 route call: NO variant kwarg) over
    eleven states. Every child slot starts empty."""
    kw = {} if v is None else {"variant": v}
    out = {}

    def run(name, now, st, spawn=None, keep=False):
        if not keep:
            OD._STATE.update(proc=None, started_at=None)
            OD._STATES.clear()
        sp = spawn or _Spawn()
        out[name] = (OD.request(now, store=st, spawn=sp, **kw), list(sp.calls))
        return sp

    run("closed_last_pass", _gg_at(3, 0), _gg_cron(_gg_store(v), _gg_at(10, 0, d=date(2026, 10, 12))))
    run("closed_no_pass", _gg_at(3, 30), _gg_store(v))
    st = _gg_cron(_gg_store(v), _gg_at(10, 31))
    sp = run("started", _gg_at(10, 34, 10), st)
    run("waiting_child", _gg_at(10, 34, 11), st, spawn=sp, keep=True)
    st = _gg_cron(_gg_store(v), _gg_at(10, 26))
    t = _gg_at(10, 31, 1)
    _gg_lease(st, status="running", held_by="cron", token="c", claimed_at=t, started_at=t, last_cron_started_at=t)
    run("waiting_lease_cron", _gg_at(10, 31, 20), st)
    st = _gg_cron(_gg_store(v), _gg_at(10, 26))
    t = _gg_at(10, 29, 5)
    _gg_lease(st, status="running", held_by="on_demand", token="o", claimed_at=t, od_started_at=t,
              last_cron_started_at=_gg_at(10, 26))
    run("waiting_lease_on_demand", _gg_at(10, 29, 30), st)
    prev = date(2026, 10, 12)
    run("a12_before_first_tick", _gg_at(4, 0, 30), _gg_cron(_gg_store(v), _gg_at(20, 1, d=prev)))
    run("a12_after_first_tick", _gg_at(10, 22, 30), _gg_cron(_gg_store(v), _gg_at(20, 1, d=prev)))
    run("reused", _gg_at(10, 32, 4), _gg_cron(_gg_store(v), _gg_at(10, 31)))
    st = _gg_cron(_gg_store(v), _gg_at(10, 30))
    _gg_lease(st, status="done", held_by="on_demand", token="o", claimed_at=_gg_at(10, 30, 50),
              od_started_at=_gg_at(10, 30, 50), done_at=_gg_at(10, 31, 10))
    run("reused_via_open", _gg_at(10, 31, 40), st)
    run("refused_spawn", _gg_at(10, 34), _gg_cron(_gg_store(v), _gg_at(10, 31)), spawn=_Spawn(raises=True))
    run("refused_outer", "not-a-clock", _gg_cron(_gg_store(v), _gg_at(10, 31)))
    return out


# CAPTURED 2026-11-11 from the UNMODIFIED chart_maps/gajjala/on_demand.py (before the `profile` parameter landed) by running
# gg_table() for GG5 / GG1 / GGA — pasted verbatim. A byte moving here is a BUG in the engine edit, never a re-capture.
GG_LITERALS = {'GG5': {'closed_last_pass': ({'state': 'closed',
                               'latest_at': '2026-10-12T14:00:00+00:00',
                               'eta_sec': None,
                               'poll_sec': None,
                               'wait_max_sec': None,
                               'text': 'market closed — no scan on open; last pass 10:00 ET 2026-10-12'},
                              []),
         'closed_no_pass': ({'state': 'closed',
                             'latest_at': None,
                             'eta_sec': None,
                             'poll_sec': None,
                             'wait_max_sec': None,
                             'text': 'market closed — no scan on open; no pass on file'},
                            []),
         'started': ({'state': 'started',
                      'latest_at': '2026-10-13T14:31:00+00:00',
                      'eta_sec': 5,
                      'poll_sec': 5,
                      'wait_max_sec': 90,
                      'text': '🔄 scanning on open — started 10:34:10 ET; the board below stays until it lands'},
                     [(['<python>', '-m', 'chart_maps.gajjala.run', '--on-demand'], 'gajjala-on-open')]),
         'waiting_child': ({'state': 'waiting',
                            'latest_at': '2026-10-13T14:31:00+00:00',
                            'eta_sec': 5,
                            'poll_sec': 5,
                            'wait_max_sec': 90,
                            'text': '🔄 a pass started on open at 10:34:10 ET is still running — showing it when it '
                                    'lands'},
                           [(['<python>', '-m', 'chart_maps.gajjala.run', '--on-demand'], 'gajjala-on-open')]),
         'waiting_lease_cron': ({'state': 'waiting',
                                 'latest_at': '2026-10-13T14:26:00+00:00',
                                 'eta_sec': 5,
                                 'poll_sec': 5,
                                 'wait_max_sec': 90,
                                 'text': '🔄 the 5-minute pass started at 10:31:01 ET is still running — showing it '
                                         'when it lands'},
                                []),
         'waiting_lease_on_demand': ({'state': 'waiting',
                                      'latest_at': '2026-10-13T14:26:00+00:00',
                                      'eta_sec': 5,
                                      'poll_sec': 5,
                                      'wait_max_sec': 90,
                                      'text': '🔄 a pass started on open at 10:29:05 ET is still running — showing it '
                                              'when it lands'},
                                     []),
         'a12_before_first_tick': ({'state': 'waiting',
                                    'latest_at': '2026-10-13T00:01:00+00:00',
                                    'eta_sec': 30,
                                    'poll_sec': 5,
                                    'wait_max_sec': 90,
                                    'text': '🔄 the first 5-minute pass of the session runs at 04:01 ET — showing it '
                                            'when it lands'},
                                   []),
         'a12_after_first_tick': ({'state': 'waiting',
                                   'latest_at': '2026-10-13T00:01:00+00:00',
                                   'eta_sec': 90,
                                   'poll_sec': 5,
                                   'wait_max_sec': 90,
                                   'text': '🔄 no 5-minute pass has landed this session yet — the next runs at 10:26 '
                                           'ET; showing it when it lands'},
                                  []),
         'reused': ({'state': 'reused',
                     'latest_at': '2026-10-13T14:31:00+00:00',
                     'eta_sec': None,
                     'poll_sec': None,
                     'wait_max_sec': None,
                     'text': '🔄 the 10:31 ET pass finished 59 s ago — reused (a pass under 60 s old is not re-run)'},
                    []),
         'reused_via_open': ({'state': 'reused',
                              'latest_at': '2026-10-13T14:30:00+00:00',
                              'eta_sec': None,
                              'poll_sec': None,
                              'wait_max_sec': None,
                              'text': '🔄 a scan on open finished 30 s ago — reused (a pass under 60 s old is not '
                                      're-run)'},
                             []),
         'refused_spawn': ({'state': 'refused',
                            'latest_at': '2026-10-13T14:31:00+00:00',
                            'eta_sec': None,
                            'poll_sec': None,
                            'wait_max_sec': None,
                            'text': '🔄 the scan could not start (store error) — the board shows the last pass'},
                           [(['<python>', '-m', 'chart_maps.gajjala.run', '--on-demand'], 'gajjala-on-open')]),
         'refused_outer': ({'state': 'refused',
                            'latest_at': None,
                            'eta_sec': None,
                            'poll_sec': None,
                            'wait_max_sec': None,
                            'text': '🔄 the scan could not start (store error) — the board shows the last pass'},
                           [])},
 'GG1': {'closed_last_pass': ({'state': 'closed',
                               'latest_at': '2026-10-12T14:00:00+00:00',
                               'eta_sec': None,
                               'poll_sec': None,
                               'wait_max_sec': None,
                               'text': 'market closed — no scan on open; last pass 10:00 ET 2026-10-12'},
                              []),
         'closed_no_pass': ({'state': 'closed',
                             'latest_at': None,
                             'eta_sec': None,
                             'poll_sec': None,
                             'wait_max_sec': None,
                             'text': 'market closed — no scan on open; no pass on file'},
                            []),
         'started': ({'state': 'started',
                      'latest_at': '2026-10-13T14:31:00+00:00',
                      'eta_sec': 5,
                      'poll_sec': 5,
                      'wait_max_sec': 90,
                      'text': '🔄 scanning on open — started 10:34:10 ET; the board below stays until it lands'},
                     [(['<python>', '-m', 'chart_maps.gajjala.run_1m', '--on-demand'], 'gajjala-1m-on-open')]),
         'waiting_child': ({'state': 'waiting',
                            'latest_at': '2026-10-13T14:31:00+00:00',
                            'eta_sec': 5,
                            'poll_sec': 5,
                            'wait_max_sec': 90,
                            'text': '🔄 a pass started on open at 10:34:10 ET is still running — showing it when it '
                                    'lands'},
                           [(['<python>', '-m', 'chart_maps.gajjala.run_1m', '--on-demand'], 'gajjala-1m-on-open')]),
         'waiting_lease_cron': ({'state': 'waiting',
                                 'latest_at': '2026-10-13T14:26:00+00:00',
                                 'eta_sec': 5,
                                 'poll_sec': 5,
                                 'wait_max_sec': 90,
                                 'text': '🔄 the 1-minute pass started at 10:31:01 ET is still running — showing it '
                                         'when it lands'},
                                []),
         'waiting_lease_on_demand': ({'state': 'waiting',
                                      'latest_at': '2026-10-13T14:26:00+00:00',
                                      'eta_sec': 5,
                                      'poll_sec': 5,
                                      'wait_max_sec': 90,
                                      'text': '🔄 a pass started on open at 10:29:05 ET is still running — showing it '
                                              'when it lands'},
                                     []),
         'a12_before_first_tick': ({'state': 'waiting',
                                    'latest_at': '2026-10-13T00:01:00+00:00',
                                    'eta_sec': 30,
                                    'poll_sec': 5,
                                    'wait_max_sec': 90,
                                    'text': '🔄 the first 1-minute pass of the session runs at 04:01 ET — showing it '
                                            'when it lands'},
                                   []),
         'a12_after_first_tick': ({'state': 'waiting',
                                   'latest_at': '2026-10-13T00:01:00+00:00',
                                   'eta_sec': 30,
                                   'poll_sec': 5,
                                   'wait_max_sec': 90,
                                   'text': '🔄 no 1-minute pass has landed this session yet — the next runs at 10:23 '
                                           'ET; showing it when it lands'},
                                  []),
         'reused': ({'state': 'reused',
                     'latest_at': '2026-10-13T14:31:00+00:00',
                     'eta_sec': None,
                     'poll_sec': None,
                     'wait_max_sec': None,
                     'text': '🔄 the 10:31 ET pass finished 59 s ago — reused (a pass under 60 s old is not re-run)'},
                    []),
         'reused_via_open': ({'state': 'reused',
                              'latest_at': '2026-10-13T14:30:00+00:00',
                              'eta_sec': None,
                              'poll_sec': None,
                              'wait_max_sec': None,
                              'text': '🔄 a scan on open finished 30 s ago — reused (a pass under 60 s old is not '
                                      're-run)'},
                             []),
         'refused_spawn': ({'state': 'refused',
                            'latest_at': '2026-10-13T14:31:00+00:00',
                            'eta_sec': None,
                            'poll_sec': None,
                            'wait_max_sec': None,
                            'text': '🔄 the scan could not start (store error) — the board shows the last pass'},
                           [(['<python>', '-m', 'chart_maps.gajjala.run_1m', '--on-demand'], 'gajjala-1m-on-open')]),
         'refused_outer': ({'state': 'refused',
                            'latest_at': None,
                            'eta_sec': None,
                            'poll_sec': None,
                            'wait_max_sec': None,
                            'text': '🔄 the scan could not start (store error) — the board shows the last pass'},
                           [])},
 'GGA': {'closed_last_pass': ({'state': 'closed',
                               'latest_at': '2026-10-12T14:00:00+00:00',
                               'eta_sec': None,
                               'poll_sec': None,
                               'wait_max_sec': None,
                               'text': 'market closed — no scan on open; last pass 10:00 ET 2026-10-12'},
                              []),
         'closed_no_pass': ({'state': 'closed',
                             'latest_at': None,
                             'eta_sec': None,
                             'poll_sec': None,
                             'wait_max_sec': None,
                             'text': 'market closed — no scan on open; no pass on file'},
                            []),
         'started': ({'state': 'started',
                      'latest_at': '2026-10-13T14:31:00+00:00',
                      'eta_sec': 5,
                      'poll_sec': 5,
                      'wait_max_sec': 90,
                      'text': '🔄 scanning on open — started 10:34:10 ET; the board below stays until it lands'},
                     [(['<python>', '-m', 'chart_maps.gajjala.run_1m', '--on-demand'], 'gajjala-1m-on-open')]),
         'waiting_child': ({'state': 'waiting',
                            'latest_at': '2026-10-13T14:31:00+00:00',
                            'eta_sec': 5,
                            'poll_sec': 5,
                            'wait_max_sec': 90,
                            'text': '🔄 a pass started on open at 10:34:10 ET is still running — showing it when it '
                                    'lands'},
                           [(['<python>', '-m', 'chart_maps.gajjala.run_1m', '--on-demand'], 'gajjala-1m-on-open')]),
         'waiting_lease_cron': ({'state': 'waiting',
                                 'latest_at': '2026-10-13T14:26:00+00:00',
                                 'eta_sec': 5,
                                 'poll_sec': 5,
                                 'wait_max_sec': 90,
                                 'text': '🔄 the 5-minute pass started at 10:31:01 ET is still running — showing it '
                                         'when it lands'},
                                []),
         'waiting_lease_on_demand': ({'state': 'waiting',
                                      'latest_at': '2026-10-13T14:26:00+00:00',
                                      'eta_sec': 5,
                                      'poll_sec': 5,
                                      'wait_max_sec': 90,
                                      'text': '🔄 a pass started on open at 10:29:05 ET is still running — showing it '
                                              'when it lands'},
                                     []),
         'a12_before_first_tick': ({'state': 'waiting',
                                    'latest_at': '2026-10-13T00:01:00+00:00',
                                    'eta_sec': 30,
                                    'poll_sec': 5,
                                    'wait_max_sec': 90,
                                    'text': '🔄 the first 5-minute pass of the session runs at 04:01 ET — showing it '
                                            'when it lands'},
                                   []),
         'a12_after_first_tick': ({'state': 'waiting',
                                   'latest_at': '2026-10-13T00:01:00+00:00',
                                   'eta_sec': 90,
                                   'poll_sec': 5,
                                   'wait_max_sec': 90,
                                   'text': '🔄 no 5-minute pass has landed this session yet — the next runs at 10:26 '
                                           'ET; showing it when it lands'},
                                  []),
         'reused': ({'state': 'reused',
                     'latest_at': '2026-10-13T14:31:00+00:00',
                     'eta_sec': None,
                     'poll_sec': None,
                     'wait_max_sec': None,
                     'text': '🔄 the 10:31 ET pass finished 59 s ago — reused (a pass under 60 s old is not re-run)'},
                    []),
         'reused_via_open': ({'state': 'reused',
                              'latest_at': '2026-10-13T14:30:00+00:00',
                              'eta_sec': None,
                              'poll_sec': None,
                              'wait_max_sec': None,
                              'text': '🔄 a scan on open finished 30 s ago — reused (a pass under 60 s old is not '
                                      're-run)'},
                             []),
         'refused_spawn': ({'state': 'refused',
                            'latest_at': '2026-10-13T14:31:00+00:00',
                            'eta_sec': None,
                            'poll_sec': None,
                            'wait_max_sec': None,
                            'text': '🔄 the scan could not start (store error) — the board shows the last pass'},
                           [(['<python>', '-m', 'chart_maps.gajjala.run_1m', '--on-demand'], 'gajjala-1m-on-open')]),
         'refused_outer': ({'state': 'refused',
                            'latest_at': None,
                            'eta_sec': None,
                            'poll_sec': None,
                            'wait_max_sec': None,
                            'text': '🔄 the scan could not start (store error) — the board shows the last pass'},
                           [])}}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setattr(OD, "_STATE", {"proc": None, "started_at": None})
    monkeypatch.setattr(OD, "_STATES", {})


@pytest.mark.parametrize("key,v", [("GG5", None), ("GG1", V.GG1), ("GGA", V.GGA)])
def test_N7_NEGATIVE_gg_answers_equal_the_literals_captured_before_the_edit(key, v):
    got = gg_table(v)
    assert set(got) == set(GG_LITERALS[key]) and len(got) >= 9
    for name, want in GG_LITERALS[key].items():
        assert got[name] == want, (key, name)
        assert tuple(got[name][0]) == OD.RESPONSE_KEYS                       # the key ORDER too


def test_N7_the_literal_table_covers_every_state_of_the_engine():
    for key in ("GG5", "GG1", "GGA"):
        assert {a["state"] for a, _c in GG_LITERALS[key].values()} == set(OD.STATES)


def test_N8_NEGATIVE_no_gajjala_file_but_run_py_names_the_other_package():
    gg = Path(OD.__file__).resolve().parent
    hits = sorted(p.relative_to(gg).as_posix() for p in gg.rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts
                  and "l" "uk" in p.read_text(encoding="utf-8", errors="ignore").lower())
    assert hits == ["run.py"]


# ── 🥇 Luk's profile ─────────────────────────────────────────────────────────────────────────────────────────────
from chart_maps.gajjala import tab as GT                                    # noqa: E402
from chart_maps.luk import constants as LC                                  # noqa: E402
from chart_maps.luk import on_demand as LOD                                 # noqa: E402
from chart_maps.luk import run as LR                                        # noqa: E402  (the TEST imports it; the trigger never does at module level)
from chart_maps.luk import store as LS                                      # noqa: E402

S = date(2026, 11, 3)                           # a Tuesday — a market day (test_luk_run.py's clock)
PREV = date(2026, 11, 2)
B_WORD = re.compile("b" + "ounc", re.I)
EDGE = re.compile(r"\bedge\b", re.I)
NOTHING = re.compile(r"nothing (rings|reaches|is sent)", re.I)          # contracts.mjs :7883 (A13)


@pytest.fixture
def luk_on(monkeypatch):
    monkeypatch.setattr(LC, "LUK_ENABLED", True)
    monkeypatch.setenv("LUK_ENABLED", "1")


def at(hh, mm, ss=0, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


def luk_store():
    colls = {n: FakeColl() for n in LS.LOGICAL}
    colls[LS.SCREENS_KEY] = FakeColl()
    return LS.LukStore(colls=colls)


def cron(t, st=None, wall=10.0):
    """A CRON 🥇 pass at `t` (record_pass default source → "latest" + "latest_cron")."""
    st = st or luk_store()
    st.record_pass(t.astimezone(ET).date(), t, {"status": "ok", "wall_s": wall, "n_read": 2, "on_demand": False,
                                                "finished_at": t + timedelta(seconds=wall)})
    return st


def set_lease(st, **doc):
    st.coll(ST.STATE).docs[ST.LEASE_ID] = dict({"_id": ST.LEASE_ID}, **doc)


def skip_doc(st, t):
    st.set_state(LR.CHILD_STATE_ID, {"state": "skipped", "reason": LR.SKIP_SLOT, "at": t})


class Spawn(_Spawn):
    def __call__(self, argv, name):
        self.calls.append((tuple(argv), name))
        if self.raises:
            raise OSError("fork failed")
        p = _Proc()
        self.procs.append(p)
        return p


def tap(now, st, spawn=None):
    sp = spawn if spawn is not None else Spawn()
    return LOD.request(now, store=st, spawn=sp), sp


def no_plan(r):
    return r["eta_sec"] is None and r["poll_sec"] is None and r["wait_max_sec"] is None


def plan(r):
    return (r["poll_sec"] == GC.ON_DEMAND_POLL_SEC and r["wait_max_sec"] == GC.ON_DEMAND_WAIT_MAX_SEC
            and r["poll_sec"] <= r["eta_sec"] <= r["wait_max_sec"])


# started / the child slot
def test_started_spawns_luks_on_demand_child_once(luk_on):
    st = cron(at(10, 31, 15))                                       # this slot's cron pass (finished 10:31:25)
    r, sp = tap(at(10, 33), st)                                     # tick + 120 s
    assert r["state"] == "started" and tuple(r) == OD.RESPONSE_KEYS
    assert sp.calls == [(LOD.ARGV, "luk-on-demand")] and LOD.PROC_NAME == "luk-on-demand"
    assert LOD.ARGV == (sys.executable, "-m", "chart_maps.luk.run", "--on-demand")
    assert r["text"] == "🔄 scanning on demand — started 10:33:00 ET; the board below stays until it lands"
    assert plan(r) and r["eta_sec"] == 10                           # the last pass's wall time
    assert OD._STATES["luk"]["proc"] is sp.procs[0] and OD._STATE["proc"] is None
    assert r["latest_at"] == GT.pass_stamp(st.latest_pass()) == LR.GR._utc(at(10, 31, 15)).isoformat()


def test_NEGATIVE_a_second_tap_while_the_child_lives_waits_and_never_spawns_twice(luk_on):
    st = cron(at(10, 31, 15))
    _r, sp = tap(at(10, 33), st)
    r, _ = tap(at(10, 33, 1), st, sp)
    assert r["state"] == "waiting" and len(sp.calls) == 1 and plan(r)
    assert r["text"] == "🔄 an on-demand pass started at 10:33:00 ET is still running — showing it when it lands"


def test_the_child_slots_are_separate_both_ways(luk_on):
    OD._STATE.update(proc=_Proc(), started_at=at(10, 32))           # a live 🚩 child
    OD._STATES["gajjala_1m"] = {"proc": _Proc(), "started_at": at(10, 32)}   # a live 1-minute child
    r, sp = tap(at(10, 33), cron(at(10, 31, 15)))
    assert r["state"] == "started" and len(sp.calls) == 1           # 🥇 never waits on a 🚩 / GG1 child
    OD._STATE.update(proc=None, started_at=None)                    # and back: a live 🥇 child never makes 🚩 wait
    gst = _gg_cron(_gg_store(None), at(10, 31))
    gsp = _Spawn()
    assert OD.request(at(10, 34), store=gst, spawn=gsp)["state"] == "started" and len(gsp.calls) == 1
    assert gsp.calls[0][1] == OD.PROC_NAME and OD._STATES["luk"]["proc"] is sp.procs[0]


def test_a_spawn_that_raises_is_refused_with_luks_store_error_line(luk_on):
    r, _ = tap(at(10, 33), cron(at(10, 31, 15)), Spawn(raises=True))
    assert r["state"] == "refused" and no_plan(r)
    assert r["text"] == LOD.WORDS["refused"] == "🔄 the scan could not start (store error) — the board shows the last pass"
    assert OD._STATES["luk"]["proc"] is None


# reused
def test_reused_on_the_cron_pass_under_the_reuse_window(luk_on):
    st = cron(at(10, 31, 15))                                       # finished 10:31:25
    r, sp = tap(at(10, 32), st)                                     # 35 s
    assert r["state"] == "reused" and sp.calls == [] and no_plan(r)
    assert r["text"] == "🔄 the 10:31 ET pass finished 35 s ago — reused (a pass under 60 s old is not re-run)"


def test_reused_on_an_on_demand_release(luk_on):
    st = cron(at(10, 31, 15))
    set_lease(st, status="done", held_by="on_demand", token="o", claimed_at=at(10, 33), od_started_at=at(10, 33),
              done_at=at(10, 33, 30))
    r, sp = tap(at(10, 34), st)                                     # 30 s after the release
    assert r["state"] == "reused" and sp.calls == []
    assert r["text"] == "🔄 an on-demand pass finished 30 s ago — reused (a pass under 60 s old is not re-run)"


# waiting: the lease
def test_a_lease_held_by_the_cron_is_waited_for(luk_on):
    st = cron(at(10, 31, 15))
    set_lease(st, status="running", held_by="cron", token="c", claimed_at=at(10, 36, 12), started_at=at(10, 36, 12),
              last_cron_started_at=at(10, 36, 12))
    r, sp = tap(at(10, 36, 20), st)
    assert r["state"] == "waiting" and sp.calls == [] and plan(r)
    assert r["text"] == "🔄 the 5-minute 🥇 pass started at 10:36:12 ET is still running — showing it when it lands"


def test_a_lease_held_by_an_on_demand_pass_is_waited_for(luk_on):
    st = cron(at(10, 31, 15))
    set_lease(st, status="running", held_by="on_demand", token="o", claimed_at=at(10, 33), od_started_at=at(10, 33),
              last_cron_started_at=at(10, 31, 15))
    r, sp = tap(at(10, 33, 20), st)
    assert r["state"] == "waiting" and sp.calls == []
    assert r["text"] == "🔄 an on-demand pass started at 10:33:00 ET is still running — showing it when it lands"


# waiting: A12 — no cron 🥇 pass this session
def test_A12_before_and_after_the_first_tick(luk_on):
    st = cron(at(16, 1, d=PREV))                                    # yesterday's last pass only
    r, sp = tap(at(4, 0, 30), st)
    assert r["state"] == "waiting" and sp.calls == [] and r["eta_sec"] == 30
    assert r["text"] == "🔄 the first 5-minute 🥇 pass of the session runs at 04:01 ET — showing it when it lands"
    r, sp = tap(at(10, 22, 30), st)
    assert r["state"] == "waiting" and sp.calls == []
    assert r["text"] == ("🔄 no 5-minute 🥇 pass has landed this session yet — the next runs at 10:26 ET; showing it "
                         "when it lands")


# waiting: the slot gate (N5) and no_room (N6)
def test_N5_NEGATIVE_a_tap_at_tick_plus_5_with_the_lease_free_waits_for_the_slots_cron_pass(luk_on):
    st = cron(at(10, 31, 15))                                       # the PREVIOUS slot's pass only
    r, sp = tap(at(10, 36, 5), st)                                  # the 🚩 pass still running; no Luk child yet
    assert r["state"] == "waiting" and sp.calls == [] and plan(r)
    assert r["text"] == ("🔄 the 10:36 ET 5-minute 🥇 pass has not landed yet — showing it when it lands, if it runs (a "
                         "scan never starts before it)")
    assert ST.LEASE_ID not in st.coll(ST.STATE).docs                # NEGATIVE: never claimed
    assert OD._STATES.get("luk", {}).get("proc") is None


def test_C2_a_child_skip_doc_stamped_in_this_slot_settles_it(luk_on):
    st = cron(at(10, 31, 15))
    skip_doc(st, LR.GR._utc(at(10, 36, 15)))                        # this slot's cron child refused itself
    r, sp = tap(at(10, 37, 40), st)                                 # tick + 100 s → gate 2 decides
    assert r["state"] == "started" and len(sp.calls) == 1
    OD._STATES.clear()
    r, sp = tap(at(10, 38, 50), st)                                 # tick + 170 s → gate 2: no room
    assert r["state"] == "waiting" and sp.calls == [] and r["text"].startswith("🔄 too close to the 10:41 ET pass")


@pytest.mark.parametrize("doc", [{"state": "skipped", "at": "before"}, {"state": "ran", "at": "in_slot"},
                                 {"state": "skipped"}, {"state": "skipped", "at": "not-a-date"}],
                         ids=["before_tick", "not_skipped", "no_stamp", "junk_stamp"])
def test_C2_NEGATIVE_a_skip_doc_outside_the_slot_or_malformed_never_settles_it(doc, luk_on):
    st = cron(at(10, 31, 15))
    d = dict(doc)
    if d.get("at") == "before":
        d["at"] = LR.GR._utc(at(10, 35, 50))
    elif d.get("at") == "in_slot":
        d["at"] = LR.GR._utc(at(10, 36, 15))
    st.set_state(LR.CHILD_STATE_ID, d)
    r, sp = tap(at(10, 37, 40), st)
    assert r["state"] == "waiting" and sp.calls == [] and "has not landed yet" in r["text"]


def test_C2_NEGATIVE_a_raising_skip_doc_read_is_not_settled_never_refused(luk_on, monkeypatch):
    st = cron(at(10, 31, 15))
    skip_doc(st, LR.GR._utc(at(10, 36, 15)))

    def boom(sid):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(st, "get_state", boom)
    r, sp = tap(at(10, 37, 40), st)
    assert r["state"] == "waiting" and sp.calls == [] and "has not landed yet" in r["text"]


def test_H7_NEGATIVE_with_the_cron_down_every_tap_waits_and_nothing_starts(luk_on):
    st = cron(at(10, 31, 15))
    for now in (at(10, 37), at(10, 38, 30), at(10, 40, 50), at(10, 44), at(11, 2, 40)):
        r, sp = tap(now, st)
        assert r["state"] == "waiting" and sp.calls == [], now
        assert "has not landed yet" in r["text"] and "if it runs" in r["text"]


def test_N6_no_room_waits_with_no_poll_plan_and_never_spawns(luk_on):
    st = cron(at(10, 36, 15))                                       # this slot's cron pass landed
    r, sp = tap(at(10, 38, 50), st)                                 # tick + 170 s: 170 + 120 + 20 > 300
    assert r["state"] == "waiting" and sp.calls == [] and no_plan(r)
    assert r["text"] == ("🔄 too close to the 10:41 ET pass for another one (a pass needs 120 s + 20 s before it) — the "
                         "board picks that pass up on its next 5-minute refresh")
    assert ST.LEASE_ID not in st.coll(ST.STATE).docs


def test_the_fit_boundary_is_luk_runs_own_fits(luk_on):
    st = cron(at(10, 36, 15))
    edge_ok = at(10, 41) - timedelta(seconds=LC.LUK_PASS_BUDGET_SEC + LC.LUK_SLOT_MARGIN_SEC)     # tick + 160 s
    assert LR.fits(edge_ok, at(10, 41)) and not LR.fits(edge_ok + timedelta(seconds=1), at(10, 41))
    assert tap(edge_ok + timedelta(seconds=1), st)[0]["state"] == "waiting"
    assert tap(edge_ok, st)[0]["state"] == "started"


def test_the_words_follow_the_constants_at_call_time(luk_on, monkeypatch):
    monkeypatch.setattr(LC, "LUK_PASS_BUDGET_SEC", 100)
    monkeypatch.setattr(LC, "LUK_SLOT_MARGIN_SEC", 30)
    r, _ = tap(at(10, 39, 0), cron(at(10, 36, 15)))                 # 180 + 130 > 300
    assert "(a pass needs 100 s + 30 s before it)" in r["text"]
    monkeypatch.setattr(GC, "ON_DEMAND_REUSE_SEC", 45)
    r, _ = tap(at(10, 36, 50), cron(at(10, 36, 15)))
    assert r["text"].endswith("(a pass under 45 s old is not re-run)")


# closed / off
@pytest.mark.parametrize("now", [datetime(2026, 11, 7, 10, 0, tzinfo=ET), at(3, 59), at(16, 6)],
                         ids=["saturday", "0359", "1606"])
def test_NEGATIVE_closed_never_spawns_and_never_reads_the_lease(now, luk_on, monkeypatch):
    st = cron(at(10, 31, 15))
    reads = []
    monkeypatch.setattr(st, "lease_state", lambda *a, **k: reads.append(a) or {})
    r, sp = tap(now, st)
    assert r["state"] == "closed" and sp.calls == [] and reads == [] and no_plan(r)
    assert r["text"] == ("outside 🥇 Luk's pass window (04:00–16:05 ET on a market day) — no scan; last pass 10:31 ET "
                         "2026-11-03")


def test_closed_with_no_pass_on_file_says_so(luk_on):
    r, _ = tap(at(3, 30), luk_store())
    assert r == {"state": "closed", "latest_at": None, "eta_sec": None, "poll_sec": None, "wait_max_sec": None,
                 "text": "outside 🥇 Luk's pass window (04:00–16:05 ET on a market day) — no scan; no pass on file"}


@pytest.mark.parametrize("how", ["constant", "env"])
def test_NEGATIVE_luk_off_is_refused_and_never_spawns_or_reads_the_lease(how, luk_on, monkeypatch):
    if how == "constant":
        monkeypatch.setattr(LC, "LUK_ENABLED", False)
    else:
        monkeypatch.setenv("LUK_ENABLED", "0")
    st = cron(at(10, 31, 15))
    reads = []
    monkeypatch.setattr(st, "lease_state", lambda *a, **k: reads.append(a) or {})
    r, sp = tap(at(10, 33), st)
    assert r["state"] == "refused" and sp.calls == [] and reads == [] and no_plan(r)
    assert r["text"] == "🔄 🥇 Luk's pass is switched off (LUK_ENABLED) — nothing runs"


def test_the_session_conftest_default_keeps_the_button_from_spawning():
    r, sp = tap(at(10, 33), cron(at(10, 31, 15)))                   # no luk_on: tests/conftest.py LUK_ENABLED=0
    assert r["state"] == "refused" and sp.calls == []


# never raises (N8 of the package)
def test_NEGATIVE_a_raising_store_is_refused_never_a_raise(luk_on):
    class Dead:
        def __getattr__(self, name):
            raise RuntimeError("mongo down")
    r, sp = tap(at(10, 33), Dead())
    assert r["state"] == "refused" and sp.calls == [] and tuple(r) == OD.RESPONSE_KEYS
    assert r["text"] == LOD.WORDS["refused"]


def test_NEGATIVE_a_store_that_cannot_be_built_is_refused(luk_on, monkeypatch):
    def boom():
        raise RuntimeError("no mongo")
    monkeypatch.setattr(LS, "default", boom)
    r = LOD.request(at(10, 33), spawn=Spawn())
    assert r == {"state": "refused", "latest_at": None, "eta_sec": None, "poll_sec": None, "wait_max_sec": None,
                 "text": LOD.WORDS["refused"]}


def test_a_dead_fake_store_never_raises(luk_on):
    colls = {n: FakeColl(fail=True) for n in LS.LOGICAL}
    colls[LS.SCREENS_KEY] = FakeColl(fail=True)
    r, _ = tap(at(10, 33), LS.LukStore(colls=colls))
    assert r["state"] in OD.STATES and tuple(r) == OD.RESPONSE_KEYS


def test_the_default_store_is_luks_own(luk_on, monkeypatch):
    seen = []
    st = cron(at(10, 31, 15))
    monkeypatch.setattr(LS, "default", lambda: seen.append(1) or st)
    monkeypatch.setattr(ST, "for_variant", lambda *a, **k: (_ for _ in ()).throw(AssertionError("GG's store")))
    r = LOD.request(at(10, 33), spawn=Spawn())
    assert r["state"] == "started" and seen == [1]


# every state: the shape and the words (N4)
def _every_luk_answer():
    yield tap(at(3, 0), cron(at(10, 31, 15, d=PREV)))[0]                                  # closed
    yield tap(at(3, 0), luk_store())[0]                                                   # closed, none on file
    yield tap(at(10, 33), cron(at(10, 31, 15)))[0]                                        # started
    OD._STATES.clear()
    yield tap(at(10, 32), cron(at(10, 31, 15)))[0]                                        # reused
    st = cron(at(10, 31, 15))
    set_lease(st, status="done", held_by="on_demand", claimed_at=at(10, 33), done_at=at(10, 33, 30))
    yield tap(at(10, 34), st)[0]                                                          # reused (on-demand)
    st = cron(at(10, 31, 15))
    set_lease(st, status="running", held_by="cron", claimed_at=at(10, 36, 12), started_at=at(10, 36, 12))
    yield tap(at(10, 36, 20), st)[0]                                                      # waiting cron
    st = cron(at(10, 31, 15))
    set_lease(st, status="running", held_by="on_demand", claimed_at=at(10, 33), od_started_at=at(10, 33))
    yield tap(at(10, 33, 20), st)[0]                                                      # waiting on-demand
    yield tap(at(4, 0, 30), cron(at(16, 1, d=PREV)))[0]                                   # A12 before
    yield tap(at(10, 22, 30), cron(at(16, 1, d=PREV)))[0]                                 # A12 after
    yield tap(at(10, 36, 5), cron(at(10, 31, 15)))[0]                                     # slot_wait
    yield tap(at(10, 38, 50), cron(at(10, 36, 15)))[0]                                    # no_room
    yield tap(at(10, 33), cron(at(10, 31, 15)), Spawn(raises=True))[0]                    # refused
    LC.LUK_ENABLED = False
    try:
        yield tap(at(10, 33), cron(at(10, 31, 15)))[0]                                    # refused off
    finally:
        LC.LUK_ENABLED = True


def test_N4_NEGATIVE_every_answer_has_the_keys_and_none_of_the_banned_words(luk_on):
    from chart_maps.high_beta_tab import FORBIDDEN_WORDS
    seen = set()
    texts = []
    for r in _every_luk_answer():
        seen.add(r["state"])
        assert tuple(r) == OD.RESPONSE_KEYS and isinstance(r["text"], str) and r["text"]
        texts.append(r["text"])
    assert seen == set(OD.STATES) and len(set(texts)) == 13
    for t in texts + list(LOD.WORDS.values()):
        low = t.lower()
        assert "on open" not in low and not B_WORD.search(t) and not EDGE.search(t) and not NOTHING.search(t), t
        assert "enterable" not in low and "fresh bar" not in low and "none" not in low.split() and "nan" not in low.split()
        for w in FORBIDDEN_WORDS:
            assert w.lower() not in low, (w, t)


# the trigger's source (N3 — the gajjala on_demand guard + contracts.mjs :7977 A1 regex)
LSRC = Path(LOD.__file__).read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    tree = ast.parse(src)
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = getattr(node, "body", None) or []
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant):
                docs.add((b[0].lineno, b[0].end_lineno))
    keep = [ln.split("#", 1)[0] for i, ln in enumerate(src.splitlines(), 1) if not any(a <= i <= z for a, z in docs)]
    return "\n".join(keep)


def test_N3_NEGATIVE_the_luk_trigger_runs_no_pass_and_sends_nothing():
    bad = re.compile(r"threading\.Thread\(|notify_|send_to_user|alert_status|record_status|import pandas|"
                     r"from \. import (bars|detectors|scanner|alerts|potential)")
    assert not bad.search(LSRC), bad.search(LSRC)
    code = _code_only(LSRC)
    assert "run_pass(" not in code and "run_on_demand(" not in code
    assert not re.search(r"chart_maps\.(gajjala|luk)\.(bars|detectors|scanner|alerts|potential)|import pandas", code)
    assert "Popen" not in code                                       # the spawn is gajjala.on_demand._spawn's


def test_N3_NEGATIVE_run_is_imported_only_inside_a_function():
    tree = ast.parse(LSRC)
    for node in tree.body:                                           # module level
        if isinstance(node, ast.ImportFrom):
            assert not (node.module in (None, "") and any(a.name == "run" for a in node.names)), ast.dump(node)
            assert node.module not in ("run", "chart_maps.luk.run"), ast.dump(node)
        if isinstance(node, ast.Import):
            assert all(a.name != "chart_maps.luk.run" for a in node.names)
    inner = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and any(a.name == "run" for a in n.names)]
    assert inner and all(n not in tree.body for n in inner)


def test_N3_NEGATIVE_the_guard_bites():
    bad = re.compile(r"threading\.Thread\(|notify_|send_to_user|alert_status|record_status|import pandas|"
                     r"from \. import (bars|detectors|scanner|alerts|potential)")
    for s in ("from . import alerts", "AS.record_status(x)", "notify_luk_setup()", "import pandas as pd"):
        assert bad.search(s), s
    assert "run_pass(" in _code_only("def f():\n    LR.run_pass(now)\n")


def test_NEGATIVE_the_trigger_never_runs_the_pass_in_this_process(luk_on, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the api process must never run the pass")
    monkeypatch.setattr(LR, "run_pass", boom)
    if hasattr(LR, "run_on_demand"):
        monkeypatch.setattr(LR, "run_on_demand", boom)
    r, sp = tap(at(10, 33), cron(at(10, 31, 15)))
    assert r["state"] == "started" and len(sp.calls) == 1


# the route
def test_route_owner_gets_the_request_answer_scrubbed(monkeypatch):
    import auth
    from chart_maps import api as API
    from tests.test_gajjala_tab import run_route
    monkeypatch.setattr(auth, "is_admin_email", lambda e: e == "owner@example.com")
    sentinel = {"state": "started", "latest_at": None, "eta_sec": float("nan"), "poll_sec": 5, "wait_max_sec": 90,
                "text": "x"}
    calls = []
    monkeypatch.setattr(LOD, "request", lambda *a, **k: calls.append((a, k)) or dict(sentinel))
    monkeypatch.setattr(OD, "request", lambda *a, **k: (_ for _ in ()).throw(AssertionError("🚩's entry")))
    body = json.loads(run_route(API.chart_maps_luk_scan(email="owner@example.com")).body)
    assert body == dict(sentinel, eta_sec=None) and calls == [((), {})]


def test_route_NEGATIVE_a_non_owner_gets_404_and_never_triggers(monkeypatch):
    import auth
    from fastapi import HTTPException
    from chart_maps import api as API
    from tests.test_gajjala_tab import run_route
    monkeypatch.setattr(auth, "is_admin_email", lambda e: False)
    calls = []
    monkeypatch.setattr(LOD, "request", lambda *a, **k: calls.append(1) or {})
    with pytest.raises(HTTPException) as e:
        run_route(API.chart_maps_luk_scan(email="doug@example.com"))
    assert e.value.status_code == 404 and calls == []


def test_route_NEGATIVE_a_direct_call_with_the_depends_object_is_a_404(monkeypatch):
    import auth
    from fastapi import HTTPException
    from chart_maps import api as API
    from tests.test_gajjala_tab import run_route
    seen, calls = [], []
    monkeypatch.setattr(auth, "is_admin_email", lambda e: seen.append(e) or False)
    monkeypatch.setattr(LOD, "request", lambda *a, **k: calls.append(1) or {})
    with pytest.raises(HTTPException) as e:
        run_route(API.chart_maps_luk_scan())
    assert e.value.status_code == 404 and seen == [""] and calls == []


def test_route_is_a_post_gated_first_and_the_get_never_names_the_trigger():
    from chart_maps import api as API
    posts = [r for r in API.router.routes if getattr(r, "path", "") == "/chart-maps/luk/scan"]
    assert posts and all(r.methods == {"POST"} for r in posts)
    assert "on_demand" not in inspect.getsource(API.chart_maps_luk)              # N7 of the package
    src = inspect.getsource(API.chart_maps_luk_scan)
    body = src.split('"""')[-1]
    assert body.index("is_admin_email(") < body.index("LOD.request")             # the gate before anything else
    assert "404" in body and "luk import on_demand as LOD" in body
