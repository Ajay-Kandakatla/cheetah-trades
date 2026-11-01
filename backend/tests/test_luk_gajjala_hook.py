"""🥇 Luk's — the ONE gajjala edit (`gajjala/run.py` `_spawn_luk` + its one call), pinned STRUCTURALLY (BUILD_SPEC §3.8,
WP-A4, 2026-11-01; [fixed: C6] never a byte manifest — that is the §5 #2 one-time `git diff` check).

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources."

(a) the only file under chart_maps/gajjala/ whose source says "luk" is run.py; (b) the AST: one `_spawn_luk` def, one
call statement — right after `_spawn_1m()` in the same block of `main` — and no other luk identifier; (c) the cron path
calls `run_pass` with identical arguments hook on / off and spawns the Luk child once; (d) the 🚩 pass makes the same
provider calls hook on / off (the hook is outside run_pass). NEGATIVES: --dry-run / --now / --on-demand / --symbols
never spawn; a raising spawn keeps the exit code; LUK_ENABLED=0 → not spawned; a 17:06 ET clock → not spawned
([fixed: C11]).
"""
from __future__ import annotations

import ast
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala import store as ST
from chart_maps.luk import run as LR
from tests import test_gajjala_variant_gg5_identity as IDT
from tests.test_gajjala_run import NOW, make_deps
from tests.test_gajjala_store import fake_store

ET = ZoneInfo("America/New_York")
GG_DIR = Path(RUN.__file__).resolve().parent
RUN_SRC = (GG_DIR / "run.py").read_text(encoding="utf-8")
HOOK_LINE = "luk pass:"
REAL_RUN_PASS = RUN.run_pass                        # captured before any monkeypatch


class Rec:
    def __init__(self, ret=None):
        self.calls = []
        self.ret = ret

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self.ret(*a, **k) if callable(self.ret) else self.ret


# ── (a) + (b) STRUCTURAL ─────────────────────────────────────────────────────────────────────────────────────────
def test_a_only_gajjala_run_py_mentions_luk():
    hits = sorted(p.relative_to(GG_DIR).as_posix() for p in GG_DIR.rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts
                  and "luk" in p.read_text(encoding="utf-8", errors="ignore").lower())
    assert hits == ["run.py"]


def _main_fn(tree) -> ast.FunctionDef:
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")


def _is_call_stmt(node, name: str) -> bool:
    return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name) and node.value.func.id == name)


def test_b_one_spawn_luk_def_and_one_call_right_after_spawn_1m():
    tree = ast.parse(RUN_SRC)
    defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_spawn_luk"]
    assert len(defs) == 1 and defs[0] in tree.body                      # a module-level def, exactly one
    refs = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "_spawn_luk"]
    assert len(refs) == 1                                                # exactly ONE other reference: the call
    main = _main_fn(tree)
    blocks = [getattr(n, f) for n in ast.walk(main) for f in ("body", "orelse")
              if isinstance(getattr(n, f, None), list)]
    found = []
    for body in blocks:
        for i, stmt in enumerate(body):
            if _is_call_stmt(stmt, "_spawn_luk"):
                found.append((body, i))
    assert len(found) == 1
    body, i = found[0]
    assert i > 0 and _is_call_stmt(body[i - 1], "_spawn_1m")             # the statement right after _spawn_1m()
    assert sum(1 for n in ast.walk(main) if _is_call_stmt(n, "_spawn_1m")) == 1   # _spawn_1m() still there, once
    assert not body[i].value.args and not body[i].value.keywords


def test_b_no_other_luk_identifier_in_the_module():
    tree = ast.parse(RUN_SRC)
    hook = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_spawn_luk")
    inside = {id(n) for n in ast.walk(hook)}
    stray = []
    for n in ast.walk(tree):
        if id(n) in inside:
            continue
        names = []
        if isinstance(n, ast.Name):
            names.append(n.id)
        elif isinstance(n, ast.Attribute):
            names.append(n.attr)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            names += [a.name for a in n.names] + [a.asname or "" for a in n.names] + [getattr(n, "module", "") or ""]
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            names.append(n.value)
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            names.append(n.name)
        stray += [x for x in names if "luk" in x.lower() and x != "_spawn_luk"]
    assert stray == []
    imports = [n for n in ast.walk(hook) if isinstance(n, ast.ImportFrom)]
    assert [(n.module, [a.name for a in n.names]) for n in imports] == [("chart_maps.luk", ["run"])]


def test_b_the_hook_is_fenced_and_checks_the_switch_and_the_window():
    hook = next(n for n in ast.parse(RUN_SRC).body if isinstance(n, ast.FunctionDef) and n.name == "_spawn_luk")
    assert len(hook.body) == 2 and isinstance(hook.body[1], ast.Try)    # docstring + one try
    assert [h.type.id for h in hook.body[1].handlers] == ["Exception"]
    calls = {n.func.attr for n in ast.walk(hook) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "LR"}
    assert calls == {"enabled", "in_window", "spawn_child"}


# ── (c) the cron path ────────────────────────────────────────────────────────────────────────────────────────────
def _main_env(monkeypatch, *, status="ok", luk_on=True, luk_window=True, luk_spawn=True, store=None):
    store = store if store is not None else fake_store()
    rp = Rec({"status": status})
    loop = Rec(True)
    child = Rec(luk_spawn) if not callable(luk_spawn) else luk_spawn
    monkeypatch.setattr(R1, "spawn_loop", loop)
    monkeypatch.setattr(RUN, "in_window", lambda *_a, **_k: True)
    monkeypatch.setattr(RUN, "run_pass", rp)
    monkeypatch.setattr(RUN, "run_on_demand", Rec({"status": status}))
    monkeypatch.setattr(RUN, "dry_store", lambda *a, **k: None)
    monkeypatch.setattr(ST, "default", lambda: store)
    monkeypatch.setattr(LR, "spawn_child", child)
    if luk_window is not None:
        monkeypatch.setattr(LR, "in_window", lambda now=None: luk_window)
    monkeypatch.setenv("LUK_ENABLED", "1" if luk_on else "0")
    return rp, loop, child


def test_c_the_cron_path_spawns_the_luk_child_once_and_run_pass_sees_identical_args(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")
    store = fake_store()
    rp_on, loop_on, child_on = _main_env(monkeypatch, luk_on=True, store=store)
    assert RUN.main([]) == 0
    assert len(child_on.calls) == 1 and len(loop_on.calls) == 1
    assert [r.getMessage() for r in caplog.records if r.getMessage().startswith(HOOK_LINE)] == ["luk pass: spawned"]
    rp_off, loop_off, child_off = _main_env(monkeypatch, luk_on=False, store=store)
    assert RUN.main([]) == 0
    assert child_off.calls == [] and len(loop_off.calls) == 1
    assert len(rp_on.calls) == len(rp_off.calls) == 1
    (a_on, k_on), (a_off, k_off) = rp_on.calls[0], rp_off.calls[0]
    assert a_on == a_off and set(k_on) == set(k_off)
    assert k_on["store"] is k_off["store"] and k_on["symbols"] == k_off["symbols"]
    assert k_on["deps"] == k_off["deps"]                                 # the Deps the pass runs with: unchanged


def test_c_the_hook_runs_after_the_1m_spawn(monkeypatch):
    order: list = []
    _main_env(monkeypatch)
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: order.append("1m") or True)
    monkeypatch.setattr(LR, "spawn_child", lambda *a, **k: order.append("luk") or True)
    RUN.main([])
    assert order == ["1m", "luk"]


# ── (d) the 🚩 pass's provider calls, hook on / off ───────────────────────────────────────────────────────────────
def _counted_main(monkeypatch, luk_on: bool) -> tuple:
    counts: dict = {}

    def counted_pass(now, **k):
        deps = make_deps(rows={"GGA": IDT.snap_row(11.2, 8.0), "GGB": IDT.snap_row(11.0, 8.0)}, load=IDT._load)[0]
        for name in ("snapshot", "load_day", "status_lookup", "massive_lookup", "daily_loader", "fetch_types",
                     "fetch_splits", "halts"):
            fn = getattr(deps, name)

            def wrap(*a, _fn=fn, _n=name, **kw):
                counts[_n] = counts.get(_n, 0) + 1
                return _fn(*a, **kw)
            setattr(deps, name, wrap)
        deps.audited_store = lambda st: None
        return REAL_RUN_PASS(NOW, store=fake_store(), deps=deps)
    _main_env(monkeypatch, luk_on=luk_on)
    monkeypatch.setattr(RUN, "run_pass", counted_pass)
    child = Rec(True)
    monkeypatch.setattr(LR, "spawn_child", child)
    rc = RUN.main([])
    return counts, rc, child


def test_d_the_gajjala_pass_makes_identical_provider_calls_hook_on_or_off(monkeypatch):
    on, rc_on, child_on = _counted_main(monkeypatch, True)
    off, rc_off, child_off = _counted_main(monkeypatch, False)
    assert on == off and on.get("snapshot") == 1 and on.get("load_day", 0) >= 1
    assert rc_on == rc_off == 0
    assert len(child_on.calls) == 1 and child_off.calls == []


# ── NEGATIVES ────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("argv", [["--dry-run"], ["--dry-run", "--now", "2026-10-13T10:41"], ["--on-demand"],
                                  ["--symbols", "GGA"], ["--now", "2026-10-13T10:41"]])
def test_NEGATIVE_the_non_cron_paths_never_spawn_luk(monkeypatch, argv):
    _rp, _loop, child = _main_env(monkeypatch)
    RUN.main(argv)
    assert child.calls == []


def test_NEGATIVE_a_raising_spawn_keeps_the_exit_code(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")

    def boom(*a, **k):
        raise RuntimeError("fork")
    _main_env(monkeypatch, luk_spawn=boom)
    assert RUN.main([]) == 0
    assert any(r.getMessage() == "luk pass: spawn step failed: RuntimeError" for r in caplog.records)
    _main_env(monkeypatch, status="error", luk_spawn=boom)
    assert RUN.main([]) == 1
    _main_env(monkeypatch, luk_spawn=False)
    assert RUN.main([]) == 0
    _main_env(monkeypatch, status="error", luk_spawn=False)
    assert RUN.main([]) == 1


def test_NEGATIVE_a_raising_switch_is_fenced_too(monkeypatch):
    _main_env(monkeypatch)

    def boom():
        raise ImportError("x")
    monkeypatch.setattr(LR, "enabled", boom)
    assert RUN.main([]) == 0


def test_NEGATIVE_luk_enabled_0_is_not_spawned(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")
    _rp, _loop, child = _main_env(monkeypatch, luk_on=False)
    assert RUN.main([]) == 0 and child.calls == []
    assert any(r.getMessage() == "luk pass: off or outside its window — not spawned" for r in caplog.records)


def test_NEGATIVE_a_17_06_et_clock_is_not_spawned(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")
    _rp, loop, child = _main_env(monkeypatch, luk_window=None)          # Luk's REAL window check, bare clock
    late = datetime(2026, 11, 3, 17, 6, tzinfo=ET)
    real_utc = RUN._utc
    monkeypatch.setattr(RUN, "_utc", lambda now=None: real_utc(late if now is None else now))
    assert LR.in_window() is False
    assert RUN.main([]) == 0 and child.calls == [] and len(loop.calls) == 1
    assert any(r.getMessage() == "luk pass: off or outside its window — not spawned" for r in caplog.records)
    in_rth = datetime(2026, 11, 3, 10, 1, tzinfo=ET)
    monkeypatch.setattr(RUN, "_utc", lambda now=None: real_utc(in_rth if now is None else now))
    assert RUN.main([]) == 0 and len(child.calls) == 1                   # the same path inside the window spawns


def test_the_session_conftest_keeps_luk_off(monkeypatch):
    import os
    assert os.environ.get("LUK_ENABLED") == "0"                          # tests/conftest.py ASSIGNS it (C10)
    assert LR.enabled() is False
