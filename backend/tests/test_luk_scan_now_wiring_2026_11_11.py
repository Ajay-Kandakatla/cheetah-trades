"""🔄 Luk's scan-now button — the wiring end to end (lukscan spec, main-session step 3, 2026-11-11).

Ajay 2026-11-11 ~10:10 ET, verbatim: "Can you put an ondeman scan button for Luk' scans too"

The packages test their own halves (tests/test_luk_scan_now_2026_11_11.py — the trigger and the route;
tests/test_luk_run_on_demand_2026_11_11.py — the pass; tests/test_luk_tab_scan_2026_11_11.py — the served block).
This file pins the SEAMS between them:
  1. the child argv the trigger spawns (`luk.on_demand.ARGV`) is exactly the CLI `luk.run.main` parses;
  2. a request → the spawn → the child (an in-process `LR.main(argv[3:])` with fakes) → the next GET's `pass.at`
     differs from the POST's `latest_at` and the served scan state is not "scanning" — the FE's landed rule
     (lib/luk.ts `lukScanLanded` == lib/gajjala.ts `ggScanAdvanced`) end to end.
NEGATIVES: a non-owner POST spawns nothing and the next GET's `pass.at` is unchanged; a reused answer spawns nothing
and never reads as landed; a child refused at its own start (switch off) writes no pass doc, so the board never reads
as landed; the on-demand child never moves "latest_cron"; a mistyped / combined flag is refused, never a pass.
"""
from __future__ import annotations

import copy
import json
import sys
from datetime import timedelta

import pytest

from chart_maps.gajjala import on_demand as OD
from chart_maps.gajjala import run as GR
from chart_maps.gajjala import store as GS
from chart_maps.luk import constants as LC
from chart_maps.luk import on_demand as LOD
from chart_maps.luk import run as LR
from chart_maps.luk import store as ST
from chart_maps.luk import tab as LT
from tests.test_luk_run import (Rec, _shadow_by_default, at, fake_deps, fake_steps, mk_store)  # noqa: F401

OWNER = "owner" + chr(64) + "example.com"
OTHER = "doug" + chr(64) + "example.com"
CRON_AT = at("09:36", 7)                       # this slot's cron 🥇 pass (tick 09:36)
TAP_AT = at("09:38", 10)                       # tick + 130 s: past the reuse window, inside the fit


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(OD, "_STATE", {"proc": None, "started_at": None})
    monkeypatch.setattr(OD, "_STATES", {})


@pytest.fixture
def luk_on(monkeypatch):
    monkeypatch.setenv("LUK_ENABLED", "1")
    monkeypatch.setattr(LC, "LUK_ENABLED", True)


class _Proc:
    pid = 4242

    def poll(self):
        return None


class _Spawn:
    """Records the argv the trigger hands 🚩's _spawn; runs nothing (the child runs later, like the real one)."""

    def __init__(self):
        self.calls = []

    def __call__(self, argv, name):
        self.calls.append((tuple(argv), name))
        return _Proc()


def _clock_at(monkeypatch, now):
    """The child's wall clock (luk.run reads gajjala.run._utc when it is handed no --now)."""
    monkeypatch.setattr(GR, "_utc", lambda v=None, _f=GR._utc: _f(now) if v is None else _f(v))


def _board_with_cron(monkeypatch):
    st, colls = mk_store()
    fake_steps(monkeypatch, t1=at("09:35"), t5=at("09:35"))
    LR.run_pass(CRON_AT, store=st, deps=fake_deps())
    return st, colls


def _post(monkeypatch, st, now, email, spawn):
    """POST /chart-maps/luk/scan through the REAL route, the REAL luk.on_demand.request on the fake store."""
    import auth
    from chart_maps import api as API
    from tests.test_gajjala_tab import run_route
    real = LOD.request
    monkeypatch.setattr(auth, "is_admin_email", lambda e: e == OWNER)
    monkeypatch.setattr(LOD, "request", lambda *a, **k: real(now, store=st, spawn=spawn))
    return json.loads(run_route(API.chart_maps_luk_scan(email=email)).body)


def _landed(board, latest_at) -> bool:
    """lib/luk.ts lukScanLanded == lib/gajjala.ts ggScanAdvanced: pass.at a string ≠ latest_at and the served scan
    state is not 'scanning'."""
    at_ = (board.get("pass") or {}).get("at")
    return isinstance(at_, str) and at_ != latest_at and (board.get("scan") or {}).get("state") != "scanning"


# ── 1. the argv seam ─────────────────────────────────────────────────────────────────────────────────────────────
def test_the_spawned_argv_names_luk_runs_on_demand_cli():
    assert LOD.ARGV[0] == sys.executable
    assert LOD.ARGV[1:] == ("-m", "chart_maps.luk.run", "--on-demand")
    assert LOD.ARGV[2] == LR.__name__                                       # the module the argv runs IS luk.run


def test_the_on_demand_cli_parses_the_flags_the_child_and_a_dry_replay_use(monkeypatch, capsys):
    rod = Rec(lambda *a, **k: {"status": "ok", "on_demand": True})
    monkeypatch.setattr(LR, "run_on_demand", rod)
    real, _colls = mk_store()
    assert LR.main(["--on-demand", "--dry-run", "--json"], store=ST.dry_store(real)) == 0
    assert len(rod.calls) == 1 and rod.calls[0][1]["dry"] is True
    out = json.loads(capsys.readouterr().out)
    assert out["on_demand"] is True and "writes" in out


@pytest.mark.parametrize("argv", [["--on-demand", "--child"], ["--on-demand", "--now", "2026-11-03T09:38"]])
def test_NEGATIVE_a_combined_or_replay_flag_without_dry_run_is_refused_and_runs_no_pass(monkeypatch, argv):
    rod, rp = Rec({"status": "ok"}), Rec({"status": "ok"})
    monkeypatch.setattr(LR, "run_on_demand", rod)
    monkeypatch.setattr(LR, "run_pass", rp)
    st, colls = mk_store()
    assert LR.main(argv, store=st) == 2
    assert rod.calls == [] and rp.calls == [] and colls[GS.STATE].writes == 0


def test_NEGATIVE_a_mistyped_flag_is_an_argparse_refusal_never_a_pass(monkeypatch):
    rod = Rec({"status": "ok"})
    monkeypatch.setattr(LR, "run_on_demand", rod)
    with pytest.raises(SystemExit):
        LR.main(["--on_demand"], store=mk_store()[0])
    assert rod.calls == []


# ── 2. request → spawn → child → the next GET (the FE's landed rule) ────────────────────────────────────────────
def test_a_tap_spawns_the_child_and_the_next_get_reads_as_landed(monkeypatch, luk_on):
    st, colls = _board_with_cron(monkeypatch)
    before = LT.build("", now=at("09:38", 5), store=st)
    cron_ptr = copy.deepcopy(colls[GS.PASSES].docs["latest_cron"])
    sp = _Spawn()
    ans = _post(monkeypatch, st, TAP_AT, OWNER, sp)
    assert ans["state"] == "started" and tuple(ans) == OD.RESPONSE_KEYS
    assert ans["latest_at"] == before["pass"]["at"]                         # the POST's stamp == the GET's pass.at
    assert sp.calls == [(LOD.ARGV, LOD.PROC_NAME)]
    assert not _landed(before, ans["latest_at"])
    # the child, as the subprocess would run it: `python -m chart_maps.luk.run --on-demand`
    _clock_at(monkeypatch, TAP_AT + timedelta(seconds=1))
    fake_steps(monkeypatch, t1=at("09:37"), t5=at("09:35"))
    assert LR.main(list(sp.calls[0][0][3:]), store=st, deps=fake_deps()) == 0
    after = LT.build("", now=at("09:38", 30), store=st)
    assert _landed(after, ans["latest_at"])
    assert after["pass"]["on_demand"] is True and after["scan"]["state"] == "idle"
    assert colls[GS.PASSES].docs["latest_cron"] == cron_ptr                 # NEGATIVE: the cron pointer never moves


def test_NEGATIVE_a_non_owner_post_spawns_nothing_and_the_next_get_is_unchanged(monkeypatch, luk_on):
    from fastapi import HTTPException
    st, _colls = _board_with_cron(monkeypatch)
    before = LT.build("", now=at("09:38", 5), store=st)
    sp = _Spawn()
    with pytest.raises(HTTPException) as e:
        _post(monkeypatch, st, TAP_AT, OTHER, sp)
    assert e.value.status_code == 404 and sp.calls == []
    after = LT.build("", now=at("09:38", 30), store=st)
    assert after["pass"]["at"] == before["pass"]["at"]


def test_NEGATIVE_a_reused_answer_spawns_nothing_and_never_reads_as_landed(monkeypatch, luk_on):
    st, _colls = _board_with_cron(monkeypatch)
    sp = _Spawn()
    ans = _post(monkeypatch, st, CRON_AT + timedelta(seconds=GR.GC.ON_DEMAND_REUSE_SEC // 2), OWNER, sp)
    assert ans["state"] == "reused" and sp.calls == []
    after = LT.build("", now=at("09:37"), store=st)
    assert after["pass"]["at"] == ans["latest_at"] and not _landed(after, ans["latest_at"])


def test_NEGATIVE_a_child_refused_at_its_start_writes_no_pass_and_the_board_never_reads_as_landed(monkeypatch, luk_on):
    st, colls = _board_with_cron(monkeypatch)
    sp = _Spawn()
    ans = _post(monkeypatch, st, TAP_AT, OWNER, sp)
    assert ans["state"] == "started" and len(sp.calls) == 1
    passes = sorted(colls[GS.PASSES].docs)
    monkeypatch.setenv("LUK_ENABLED", "0")                                  # switched off between the tap and the child
    _clock_at(monkeypatch, TAP_AT + timedelta(seconds=1))
    assert LR.main(list(sp.calls[0][0][3:]), store=st, deps=fake_deps()) == 0
    assert sorted(colls[GS.PASSES].docs) == passes                          # no pass doc
    assert LR.CHILD_STATE_ID not in colls[GS.STATE].docs                    # the cron child's skip doc is not written
    after = LT.build("", now=at("09:38", 30), store=st)
    assert not _landed(after, ans["latest_at"])
