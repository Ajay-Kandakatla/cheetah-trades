"""🩳 The on-entry SI source check — the two entry hooks and the watchdog's child list (SPEC sicheck rev 2 §3.5 / §4.3,
work package entry-hooks, 2026-11-27).

Ajay 2026-11-27, verbatim: "Anytime something is in our Gajjalas we need to initiate a flow checking these values".

- run.py: `Deps.si_entry` (None by default) → `_cron_deps()` wires `_si_entry`, which imports short_interest.entry_check
  lazily and calls `enqueue(names, session_iso, SRC_GAJJALA)`. Invoked after the ⛔ SSR step, never on a dry run or an
  on-open pass, in its OWN try, never a key of `out` / `out["errors"]`.
- loop.py: ONE `enqueue(syms + RUNSEAT.current_symbols(cs, session), session_iso, SRC_WATCH)` at the END of
  run_iteration (after `_seat`), never on a dry run or the stub, in its own try; no key of `out`, no state doc key.
- ops/docker_watchdog.py: `("-m", "short_interest.entry_check", "--child")` is a detached child; the same module with any
  other flag is a job.

No test here needs the si-io package's module: a stub `short_interest.entry_check` is installed where it is imported.
NEGATIVES are the point.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import logging
import sys
import types
from pathlib import Path

import pytest

from chart_maps.gajjala import run as RUN
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import loop as LP
from tests.test_gajjala_run import NOW, snap_row
from tests.test_gajjala_ssr_step_2026_11_24 import _bytes, _deps, _main_env, _summary, rec_store
from tests.test_gajjala_watch_auto_2026_11_17 import fake_db as auto_fake_db
from tests.test_gajjala_watch_build_2026_11_15 import S as LS, at as lat

ROOT = Path(__file__).resolve().parents[1]
RUN_PY = ROOT / "chart_maps" / "gajjala" / "run.py"
LOOP_PY = ROOT / "chart_maps" / "gajjala_watch" / "loop.py"
WD_PATH = ROOT.parent / "ops" / "docker_watchdog.py"
MOD = "short_interest.entry_check"
RUN_LOGGER = "chart_maps.gajjala.run"
LOOP_LOGGER = LP.log.name
SESSION_ISO = "2026-10-13"                                     # tests.test_gajjala_run's NOW session


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: True)


def _stub_ec(monkeypatch, enqueue=None):
    """The K-2 surface the hooks read: enqueue + the two source constants (si-io's module may not be on disk yet)."""
    calls: list = []
    mod = types.ModuleType(MOD)
    mod.SRC_GAJJALA, mod.SRC_WATCH = "gajjala", "watch"

    def rec(symbols, session, source, *, db=None, now=None, spawn=None):
        calls.append((list(symbols), session, source))
        return {"new": list(symbols), "queued": len(symbols), "spawned": False, "reason": None}
    mod.enqueue = enqueue or rec
    monkeypatch.setitem(sys.modules, MOD, mod)
    import short_interest
    monkeypatch.setattr(short_interest, "entry_check", mod, raising=False)
    return mod, calls


def _break_ec(monkeypatch):
    monkeypatch.setitem(sys.modules, MOD, None)                 # an import of a None entry raises ImportError
    import short_interest
    monkeypatch.delattr(short_interest, "entry_check", raising=False)


def _boom(*a, **k):
    raise RuntimeError("entry check down")


# ═════ run.py — the 🚩 pass hook ═══════════════════════════════════════════════════════════════════════════════════
def test_cron_deps_wire_the_si_entry_hook():
    d = RUN._cron_deps()
    assert d.si_entry is RUN._si_entry
    from chart_maps.gajjala import divergence as DV
    assert d.divergence is DV.run_step                          # the other cron steps unchanged


def test_the_hook_calls_enqueue_with_the_names_the_session_and_the_gajjala_source(monkeypatch):
    mod, calls = _stub_ec(monkeypatch)
    mod.SRC_GAJJALA = "<the module's own constant>"             # read by name, never retyped
    res = RUN._si_entry(("GGA", "OMH"), SESSION_ISO)
    assert calls == [(["GGA", "OMH"], SESSION_ISO, "<the module's own constant>")]
    assert res["queued"] == 2


def test_a_cron_pass_hands_every_listed_name_and_the_session_once():
    calls: list = []
    rows = {"GGA": snap_row(11.2, 8.0), "NOPE": snap_row(1.0, 0.95)}
    deps, _snap, _send, _status = _deps(rows=rows, si_entry=lambda names, s: calls.append((names, s)) or {})
    out = RUN.run_pass(NOW, store=rec_store()[0], deps=deps)
    assert out["ran"] and out["status"] == "ok" and out["errors"] == []
    assert calls == [(["GGA"], SESSION_ISO)]                    # the listed names (NOPE never listed), the ISO session


def test_a_cron_pass_through_the_real_hook_reaches_enqueue(monkeypatch):
    _mod, calls = _stub_ec(monkeypatch)
    deps, _snap, _send, _status = _deps(si_entry=RUN._si_entry)
    out = RUN.run_pass(NOW, store=rec_store()[0], deps=deps)
    assert out["errors"] == [] and calls == [(["GGA"], SESSION_ISO, "gajjala")]


def test_NEGATIVE_default_deps_never_carry_the_hook():
    assert RUN.Deps().si_entry is None
    assert RUN.dry_deps().si_entry is None
    deps, _snap, _send, _status = _deps()
    out = RUN.run_pass(NOW, store=rec_store()[0], deps=deps)
    assert out["errors"] == [] and not any("si_entry" in k or "entry" in k for k in out)


def test_NEGATIVE_a_default_deps_pass_never_imports_entry_check(monkeypatch):
    _mod, calls = _stub_ec(monkeypatch)
    deps, _snap, _send, _status = _deps()
    RUN.run_pass(NOW, store=rec_store()[0], deps=deps)
    assert calls == []


def test_NEGATIVE_a_dry_pass_never_calls_the_hook():
    calls: list = []
    deps, _snap, _send, _status = _deps(si_entry=lambda *a: calls.append(a))
    out = RUN.run_pass(NOW, store=rec_store()[0], deps=deps, dry=True)
    assert out["ran"] and calls == []


def test_NEGATIVE_an_on_open_pass_never_calls_the_hook():
    calls: list = []
    deps, _snap, _send, _status = _deps(si_entry=lambda *a: calls.append(a))
    out = RUN.run_on_demand(NOW, store=rec_store()[0], deps=deps)
    assert out["ran"] and calls == []


@pytest.mark.parametrize("argv", [["--on-demand"], ["--dry-run"], ["--dry-run", "--on-demand"]])
def test_NEGATIVE_main_open_and_dry_paths_carry_no_hook(monkeypatch, argv):
    _stub_ec(monkeypatch)
    rp, od = _main_env(monkeypatch)
    assert RUN.main(argv) == 0
    calls = rp.calls + od.calls
    assert len(calls) == 1 and calls[0][1]["deps"].si_entry is None


def test_main_cron_path_carries_the_hook(monkeypatch):
    rp, _od = _main_env(monkeypatch)
    assert RUN.main([]) == 0
    assert rp.calls[0][1]["deps"].si_entry is RUN._si_entry
    assert RUN._cron_deps() == rp.calls[0][1]["deps"]           # the one-definition pin still holds


def _pair(step):
    st0, log0 = rec_store()
    d0, _s, send0, status0 = _deps()
    out0 = RUN.run_pass(NOW, store=st0, deps=d0)
    st1, log1 = rec_store()
    d1, _s, send1, status1 = _deps(si_entry=step)
    out1 = RUN.run_pass(NOW, store=st1, deps=d1)
    return (out0, log0, send0, status0, st0), (out1, log1, send1, status1, st1)


def test_NEGATIVE_the_summary_and_every_store_write_are_byte_identical_with_and_without_the_hook():
    calls: list = []
    a, b = _pair(lambda names, s: calls.append(names) or {"new": names, "queued": 1, "spawned": True, "reason": None})
    assert len(calls) == 1
    (out0, log0, send0, status0, st0), (out1, log1, send1, status1, st1) = a, b
    assert log0 and _bytes(log0) == _bytes(log1)
    assert _summary(out0) == _summary(out1) and set(out0) == set(out1)
    assert _bytes(out0["errors"]) == _bytes(out1["errors"]) == "[]"
    assert _bytes(status0.calls) == _bytes(status1.calls) and len(send0.calls) == len(send1.calls)


@pytest.mark.parametrize("how", ["raise", "import"])
def test_NEGATIVE_a_raising_hook_leaves_the_pass_summary_and_errors_byte_identical(monkeypatch, caplog, how):
    caplog.set_level(logging.INFO, logger=RUN_LOGGER)
    if how == "raise":
        _stub_ec(monkeypatch, enqueue=_boom)
    else:
        _break_ec(monkeypatch)                                  # the lazy import itself fails INSIDE the try
    a, b = _pair(RUN._si_entry)
    (out0, log0, _s0, status0, st0), (out1, log1, _s1, status1, st1) = a, b
    assert out1["status"] == out0["status"] == "ok"
    assert _bytes(out0["errors"]) == _bytes(out1["errors"]) == "[]"
    assert _summary(out0) == _summary(out1) and _bytes(log0) == _bytes(log1)
    assert _bytes(status0.calls) == _bytes(status1.calls)
    msgs = [r.getMessage() for r in caplog.records if r.name == RUN_LOGGER]
    assert msgs.count("gajjala pass: the 🩳 si entry queue failed") == 1


def _ifs(tree, test: str):
    return [n for n in ast.walk(tree) if isinstance(n, ast.If)
            and ast.unparse(n.test).replace("(", "").replace(")", "") == test]


def test_the_hook_sits_after_the_ssr_step_and_before_the_day_read_in_its_own_try():
    body = inspect.getsource(RUN.run_pass)
    i = body.index("if deps.ssr is not None and not push_dry:")
    j = body.index("if deps.si_entry is not None and not push_dry:")
    k = body.index("if deps.day_read is not None and not dry:")
    assert i < j < k
    hooks = _ifs(ast.parse(RUN_PY.read_text(encoding="utf-8")), "deps.si_entry is not None and not push_dry")
    assert len(hooks) == 1
    src = ast.unparse(hooks[0])
    assert "errors" not in src and "out[" not in src            # NEVER out["errors"], never a key of out
    assert len(hooks[0].body) == 1 and isinstance(hooks[0].body[0], ast.Try)
    call = [n for n in ast.walk(hooks[0]) if isinstance(n, ast.Call) and ast.unparse(n.func) == "deps.si_entry"]
    assert len(call) == 1 and [ast.unparse(a) for a in call[0].args] == ["list(names)", "session_iso"]


def test_NEGATIVE_entry_check_is_never_imported_at_module_level():
    for path in (RUN_PY, LOOP_PY):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for n in tree.body:                                     # top-level statements only
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                assert "entry_check" not in ast.unparse(n), (path.name, ast.unparse(n))
    assert "entry_check" not in inspect.getsource(RUN._cron_deps)   # the wiring names the hook, never the module
    assert "entry_check" not in inspect.getsource(RUN.main)
    assert "si_entry" not in inspect.getsource(RUN.dry_deps)


# REFIX 2026-11-27 (review: importlib side-stepped the ⛔ AST pin) — the module is reached by ONE plain import line per
# file, inside the hook function, so every source guard sees it. No string import of the SI package anywhere.
EC_IMPORT_LINE = "from short_interest import entry_check as EC"


def _ec_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "short_interest"
            and [a.name for a in n.names] == ["entry_check"]]


def test_each_hook_reaches_entry_check_by_one_plain_import_inside_the_hook():
    for path, fn in ((RUN_PY, "_si_entry"), (LOOP_PY, "_si_entry")):
        hits = _ec_imports(path)
        assert len(hits) == 1, path.name
        assert ast.unparse(hits[0]) == EC_IMPORT_LINE
        owner = [f for f in ast.parse(path.read_text(encoding="utf-8")).body
                 if isinstance(f, ast.FunctionDef) and f.name == fn][0]
        assert [ast.unparse(n) for n in ast.walk(owner) if isinstance(n, ast.ImportFrom)
                and n.module == "short_interest"] == [EC_IMPORT_LINE], path.name   # lazily, inside the hook function
    run_lines = RUN_PY.read_text(encoding="utf-8").split("\n")
    assert [ln.strip() for ln in run_lines if "short_interest" in ln] == [
        "from short_interest import ssr as SSR", EC_IMPORT_LINE]  # run.py names the SI package on exactly these two lines


def test_NEGATIVE_no_string_import_of_the_si_package_in_either_hook_file():
    for path in (RUN_PY, LOOP_PY):
        src = path.read_text(encoding="utf-8")
        assert '"short_interest' not in src and "'short_interest" not in src, path.name
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Call) and ast.unparse(n.func) in ("importlib.import_module", "__import__"):
                assert "short_interest" not in ast.unparse(n), (path.name, ast.unparse(n))


def test_NEGATIVE_a_planted_string_import_is_caught():
    planted = 'def _x():\n    import importlib\n    return importlib.import_module("short_interest.entry_check")\n'
    calls = [n for n in ast.walk(ast.parse(planted)) if isinstance(n, ast.Call)
             and ast.unparse(n.func) == "importlib.import_module"]
    assert calls and "short_interest" in ast.unparse(calls[0])
    assert '"short_interest' in planted


# ═════ loop.py — the 👀 iteration hook ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture()
def world(monkeypatch):
    """His OMH (the list doc) + 🤖 AUTOX + ✅ RULEX + 📅 the seated RUNR, every engine stubbed; `order` records the
    state writes, the seat step and the enqueue."""
    order: list = []
    real_state = LP._state

    def state(cs, _id, fields):
        order.append(("state", _id))
        return real_state(cs, _id, fields)
    monkeypatch.setattr(LP, "_state", state)
    monkeypatch.setattr(LP.AUTO, "step", lambda *a, **k: {"symbols": ["AUTOX"], "reason": None})
    monkeypatch.setattr(LP.RULES, "step", lambda *a, **k: {"symbols": ["RULEX"], "reason": None})
    monkeypatch.setattr(LP.RUNSEAT, "step", lambda *a, **k: order.append(("seat",)) or {"added": []})
    monkeypatch.setattr(LP.RUNSEAT, "current_symbols", lambda cs, session: ["RUNR"])
    mod, calls = _stub_ec(monkeypatch)
    real = mod.enqueue

    def enqueue(*a, **k):
        order.append(("enqueue",))
        return real(*a, **k)
    mod.enqueue = enqueue
    return order, calls, mod


class Wall:
    def __init__(self, t0, step_s=1.0):
        from datetime import timedelta
        self.t, self.d = t0, timedelta(seconds=step_s)

    def __call__(self):
        t, self.t = self.t, self.t + self.d
        return t


def _iterate(db=None, **kw):
    t = lat(LS, 10, 6, 30)
    db = db if db is not None else auto_fake_db()
    deps = kw.pop("deps", None) or LP.Deps(load_day=lambda *a, **k: None, wall=Wall(t), sleep=lambda s: None)
    return LP.run_iteration(t, db=db, deps=deps, **kw), db


def test_the_watch_iteration_queues_his_auto_rules_and_runner_seat_names_once_last(world):
    order, calls, _mod = world
    out, _db = _iterate()
    assert out["ran"] is True
    assert calls == [(["OMH", "AUTOX", "RULEX", "RUNR"], LS.isoformat(), "watch")]
    assert order[-1] == ("enqueue",) and order.index(("seat",)) < order.index(("enqueue",))
    assert order.index(("state", C.STATE_LATEST_ID)) < order.index(("enqueue",))


def test_the_no_names_path_still_queues_the_runner_seats_once(world, monkeypatch):
    order, calls, _mod = world
    monkeypatch.setattr(LP.AUTO, "step", lambda *a, **k: {"symbols": [], "reason": None})
    monkeypatch.setattr(LP.RULES, "step", lambda *a, **k: {"symbols": [], "reason": None})
    out, _db = _iterate(auto_fake_db(manual=[]))
    assert out["reason"] == LP.NO_TICKERS
    assert calls == [(["RUNR"], LS.isoformat(), "watch")] and order[-1] == ("enqueue",)


def test_NEGATIVE_the_stub_never_queues(world):
    _order, calls, _mod = world
    _iterate(deps=LP.dry_deps(), dry=True, symbols=["OMH"])
    assert calls == []


def test_NEGATIVE_a_dry_run_never_queues(world):
    _order, calls, _mod = world
    out, _db = _iterate(dry=True)
    assert out["ran"] is True and calls == []


def test_NEGATIVE_a_dry_run_on_the_no_names_path_never_queues(world, monkeypatch):
    _order, calls, _mod = world
    monkeypatch.setattr(LP.AUTO, "step", lambda *a, **k: {"symbols": [], "reason": None})
    monkeypatch.setattr(LP.RULES, "step", lambda *a, **k: {"symbols": [], "reason": None})
    out, _db = _iterate(auto_fake_db(manual=[]), dry=True)
    assert out["reason"] == LP.NO_TICKERS and calls == []


def _answer(out: dict, db) -> str:
    """The iteration's answer + every state / tile doc; masked: `wall_s` and the lease's fresh uuid token only."""
    states = {k: {f: ("<token>" if "token" in f else v) for f, v in d.items() if f != "wall_s"}
              for k, d in db[C.COLL_STATE].docs.items()}
    return json.dumps([{k: v for k, v in out.items() if k != "wall_s"}, states, db[C.COLL_TILES].docs],
                      default=str, sort_keys=True)


@pytest.mark.parametrize("how", ["raise", "import"])
def test_NEGATIVE_a_raising_hook_leaves_the_iteration_answer_intact(world, monkeypatch, caplog, how):
    _order, calls, mod = world
    base_out, base_db = _iterate()
    assert len(calls) == 1
    if how == "raise":
        mod.enqueue = _boom
    else:
        _break_ec(monkeypatch)
    caplog.set_level(logging.WARNING, logger=LOOP_LOGGER)
    out, db = _iterate()
    assert out["ran"] is True and _answer(out, db) == _answer(base_out, base_db)
    msgs = [r.getMessage() for r in caplog.records if r.name == LOOP_LOGGER]
    assert len([m for m in msgs if m.startswith("gajjala watch 🩳: si entry queue failed: ")]) == 1


def test_NEGATIVE_a_raising_runner_seat_read_still_leaves_the_answer_intact(world, monkeypatch):
    _order, calls, _mod = world
    base_out, base_db = _iterate()
    monkeypatch.setattr(LP.RUNSEAT, "current_symbols", _boom)
    out, db = _iterate()
    assert _answer(out, db) == _answer(base_out, base_db) and len(calls) == 1   # the second call never reached enqueue


def test_NEGATIVE_the_hook_adds_no_key_to_out_or_the_state_docs(world, monkeypatch):
    _order, calls, _mod = world
    with_out, with_db = _iterate()
    monkeypatch.setattr(LP, "_si_entry", lambda *a, **k: None)
    without_out, without_db = _iterate()
    assert len(calls) == 1 and set(with_out) == set(without_out)
    assert _answer(with_out, with_db) == _answer(without_out, without_db)


# ═════ ops/docker_watchdog.py — the child list ════════════════════════════════════════════════════════════════════
_spec = importlib.util.spec_from_file_location("docker_watchdog_si_entry", WD_PATH)
wd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wd)
PY = "/usr/local/bin/python"
CHILD = PY + " -m short_interest.entry_check --child"


def test_the_watchdog_counts_the_entry_check_child_as_detached():
    assert ("-m", "short_interest.entry_check", "--child") in wd.CRON_DETACHED_CHILD_ARGS
    assert len(wd.CRON_DETACHED_CHILD_ARGS) == 5
    assert wd.cron_detached_child(CHILD) is True
    busy, detached = wd.cron_split_procs(["docker-init", "supercronic /etc/crontab", CHILD])
    assert busy == [] and detached == [CHILD]
    assert len(CHILD) <= wd.CRON_CMD_MAX


@pytest.mark.parametrize("args", [
    PY + " -m short_interest.entry_check",
    PY + " -m short_interest.entry_check --show",
    PY + " -m short_interest.entry_check --show --session 2026-11-27",
    PY + " -m short_interest.entry_check --enqueue --symbols AKAN --source gajjala",
    PY + " -m short_interest.entry_check --child --extra",
    "sh -c " + PY + " -m short_interest.entry_check --child",
    PY + " -m short_interest.entry_checks --child",
])
def test_NEGATIVE_the_same_module_with_any_other_flag_is_a_job(args):
    assert wd.cron_detached_child(args) is False
    busy, detached = wd.cron_split_procs([args])
    assert busy == [args] and detached == []


def test_the_listed_argv_is_the_modules_own_spawn_constant():
    EC = pytest.importorskip(MOD)                               # si-io's module (K-2 ARGV_CHILD, a FIXED argv)
    assert tuple(EC.ARGV_CHILD[1:]) in wd.CRON_DETACHED_CHILD_ARGS
    assert wd.cron_detached_child(" ".join(EC.ARGV_CHILD)) is True
