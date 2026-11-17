"""👀 Gajjala's Watch — the ONE gajjala edit in run.py (`_spawn_watch` + its one call), pinned structurally and by
behaviour (spec 2026-11-15 §3.5.4, WP-B).

Ajay, verbatim (2026-11-15): "I need dashboard to add tickers to Gajjalas watch dashboard … I need alerts on these from
1 min to I can be ready".

The call sits at the START of the cron path (after the --now refusal, BEFORE the store, the lease and run_pass) so the
loop's iteration 0 reads the bar that closed at the tick. NEGATIVES: --dry-run / --now / --on-demand / --symbols /
--at-bar-close never spawn; the switch off never spawns; a raising spawn keeps the exit code; the parent reads no Mongo
and no provider; the only files under chart_maps/gajjala/ that name the watch are run.py and (since 2026-11-16,
the live tab) live_events.py and (since 2026-11-16, the read-only card three-chart view GET) card_frames.py.
"""
from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from chart_maps.gajjala import bar_close as BC
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala import store as ST
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as WC
from chart_maps.luk import run as LR
from tests.test_gajjala_store import fake_store

GG_DIR = Path(RUN.__file__).resolve().parent
RUN_SRC = (GG_DIR / "run.py").read_text(encoding="utf-8")


class Rec:
    def __init__(self, ret=None, order=None, tag=None):
        self.calls, self.ret, self.order, self.tag = [], ret, order, tag

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        if self.order is not None:
            self.order.append(self.tag)
        return self.ret(*a, **k) if callable(self.ret) else self.ret


def _main_env(monkeypatch, *, on=True, status="ok", popen=None, order=None):
    order = order if order is not None else []
    rp = Rec({"status": status}, order, "run_pass")
    pop = popen if popen is not None else Rec(type("P", (), {"pid": 4242})(), order, "watch")
    monkeypatch.setattr(R1, "_popen", pop)
    monkeypatch.setattr(R1, "spawn_loop", Rec(True))
    monkeypatch.setattr(LR, "spawn_child", Rec(True))
    monkeypatch.setattr(RUN, "in_window", lambda *_a, **_k: True)
    monkeypatch.setattr(RUN, "run_pass", rp)
    monkeypatch.setattr(RUN, "run_on_demand", Rec({"status": status}))
    monkeypatch.setattr(RUN, "dry_store", lambda *a, **k: None)
    monkeypatch.setattr(ST, "default", lambda: (order.append("store"), fake_store())[1])
    monkeypatch.setattr(BC, "wait_and_run", Rec({"status": "ok"}))
    monkeypatch.setenv(WC.ENV_ENABLED, "1" if on else "0")
    return rp, pop, order


# ── structural ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_only_gajjala_run_py_names_the_watch():
    hits = sorted(p.relative_to(GG_DIR).as_posix() for p in GG_DIR.rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts
                  and "gajjala_watch" in p.read_text(encoding="utf-8", errors="ignore"))
    # 2026-11-16 (spec ggw_live §3.1, WP-A1): live_events.py now names chart_maps.gajjala_watch.constants for
    # extra_tabs()/quote_tabs() — the watch's live tab. Widened from ["run.py"].
    # 2026-11-16 (spec ggcard3 §3.1, WP-C): card_frames.py — the card three-chart view, display-only — imports the
    # Watch's axis/stale readers (gajjala_watch.build + .payload). Widened again; nothing else may join.
    # 📺 2026-11-17 (spec ggvideo, WP gg-card-axis): tab.card_axis lazily imports gajjala_watch.build (axis +
    # axis_end) for the card's own time axis — display-only. Widened to include tab.py; nothing else may join.
    assert hits == ["card_frames.py", "live_events.py", "run.py", "tab.py"]


def test_NEGATIVE_tab_imports_only_the_watch_build_reader_never_its_switch_or_store():
    # 📺 2026-11-17 (spec ggvideo, WP gg-card-axis): tab.py may name the Watch ONLY through gajjala_watch.build.
    tree = ast.parse((GG_DIR / "tab.py").read_text(encoding="utf-8"))
    mods = sorted({f"{n.module}.{a.name}" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                   and (n.module or "").startswith("chart_maps.gajjala_watch") for a in n.names}
                  | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
                     if a.name.startswith("chart_maps.gajjala_watch")})
    assert mods == ["chart_maps.gajjala_watch.build"]
    src = (GG_DIR / "tab.py").read_text(encoding="utf-8")
    for banned in ("gajjala_watch import colls", "gajjala_watch import constants", "gajjala_watch import loop",
                   "gajjala_watch import payload", "WCO."):
        assert banned not in src


def test_NEGATIVE_card_frames_imports_only_the_watch_readers_never_its_switch_or_store():
    tree = ast.parse((GG_DIR / "card_frames.py").read_text(encoding="utf-8"))
    mods = sorted({f"{n.module}.{a.name}" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                   and (n.module or "").startswith("chart_maps.gajjala_watch") for a in n.names}
                  | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
                     if a.name.startswith("chart_maps.gajjala_watch")})
    assert mods == ["chart_maps.gajjala_watch.build", "chart_maps.gajjala_watch.payload"]
    src = (GG_DIR / "card_frames.py").read_text(encoding="utf-8")
    for banned in ("gajjala_watch import colls", "gajjala_watch import constants", "gajjala_watch import loop",
                   "WCO.", "_popen", "spawn"):
        assert banned not in src


def _main_fn(tree):
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")


def _is_call(node, name):
    return (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name) and node.value.func.id == name)


def test_one_def_one_guarded_call_before_the_store_and_run_pass():
    tree = ast.parse(RUN_SRC)
    defs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_spawn_watch"]
    assert len(defs) == 1 and defs[0] in tree.body
    assert len([n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "_spawn_watch"]) == 1
    main = _main_fn(tree)
    ifs = [n for n in main.body if isinstance(n, ast.If) and any(_is_call(s, "_spawn_watch") for s in n.body)]
    assert len(ifs) == 1
    guard = ast.unparse(ifs[0].test)
    assert guard == "not args.dry_run and (not args.on_demand) and (not syms) and (not args.now)"
    i = main.body.index(ifs[0])
    later = ast.unparse(ast.Module(body=main.body[i + 1:], type_ignores=[]))
    earlier = ast.unparse(ast.Module(body=main.body[:i], type_ignores=[]))
    assert "run_pass(" in later and "ST.default()" in later and "_spawn_1m()" in later
    assert "args.now and (not args.dry_run)" in earlier                     # after the --now refusal
    assert "at_bar_close" in earlier                                        # the bar-close child returned before


def test_the_hook_is_fenced_and_reads_only_the_switch():
    hook = next(n for n in ast.parse(RUN_SRC).body if isinstance(n, ast.FunctionDef) and n.name == "_spawn_watch")
    assert len(hook.body) == 2 and isinstance(hook.body[1], ast.Try)
    assert [h.type.id for h in hook.body[1].handlers] == ["Exception"]
    called = {(n.func.value.id, n.func.attr) for n in ast.walk(hook) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)}
    assert called == {("WCO", "enabled"), ("R1", "_popen"), ("log", "info"), ("log", "warning")}


def test_the_luk_hook_still_follows_the_1m_spawn():
    main = _main_fn(ast.parse(RUN_SRC))
    for node in ast.walk(main):
        for body in (getattr(node, "body", None), getattr(node, "orelse", None)):
            if isinstance(body, list):
                for i, s in enumerate(body):
                    if _is_call(s, "_spawn_luk"):
                        assert _is_call(body[i - 1], "_spawn_1m")


# ── behaviour ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_cron_path_spawns_the_loop_once_before_the_store_and_the_pass(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")
    rp, pop, order = _main_env(monkeypatch)
    assert RUN.main([]) == 0
    assert len(pop.calls) == 1 and pop.calls[0][0] == (list(WC.ARGV_LOOP), WC.PROC_NAME_LOOP)
    assert order[0] == "watch" and order.count("watch") == 1 and order.index("store") < order.index("run_pass")
    assert "gajjala watch: spawned (pid 4242)" in [r.getMessage() for r in caplog.records]


@pytest.mark.parametrize("argv", [["--dry-run"], ["--dry-run", "--now", "2026-11-13T10:41"], ["--on-demand"],
                                  ["--symbols", "OMH"], ["--now", "2026-11-13T10:41"], ["--at-bar-close"]])
def test_NEGATIVE_the_non_cron_paths_never_spawn(monkeypatch, argv):
    _rp, pop, _o = _main_env(monkeypatch)
    RUN.main(argv)
    assert pop.calls == []


def test_NEGATIVE_off_is_not_spawned(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")
    _rp, pop, _o = _main_env(monkeypatch, on=False)
    assert RUN.main([]) == 0 and pop.calls == []
    assert "gajjala watch: off — not spawned" in [r.getMessage() for r in caplog.records]


def test_NEGATIVE_a_raising_spawn_keeps_the_exit_code(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")

    def boom(*a, **k):
        raise OSError("fork")
    _main_env(monkeypatch, popen=boom)
    assert RUN.main([]) == 0
    assert "gajjala watch: spawn step failed: OSError" in [r.getMessage() for r in caplog.records]
    _main_env(monkeypatch, popen=boom, status="error")
    assert RUN.main([]) == 1


def test_NEGATIVE_the_parent_reads_no_mongo_and_no_list(monkeypatch):
    _rp, pop, _o = _main_env(monkeypatch)
    monkeypatch.setattr(CO, "_db", lambda: pytest.fail("the parent never reads Mongo"))
    monkeypatch.setattr(CO, "owner_symbols", lambda *a, **k: pytest.fail("the parent never reads the list"))
    RUN._spawn_watch()
    assert len(pop.calls) == 1


def test_the_session_conftest_keeps_the_watch_off():
    import os
    assert os.environ.get(WC.ENV_ENABLED) == "0" and CO.enabled() is False
