"""📅 Runners record — the 20:15 fence in `chart_maps.gajjala.nightly`, the `--once` CLI and the read-only probe's pins
(2026-11-26, spec watchrun rev 2 §3.4, WP-2 `be-track`). Negatives mandatory. Hermetic."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from chart_maps.gajjala import nightly as NG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import runtrack as RT
from tests.test_gajjala_watch_runtrack_2026_11_26 import RUN, WIN, aplus_run, day_run, entry, rdoc, removed

PROBE = Path(__file__).resolve().parents[1] / "scripts" / "gajjala_watch_runtrack_probe.py"


def _probe():
    spec = importlib.util.spec_from_file_location("gajjala_watch_runtrack_probe", PROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── the fence in nightly.main ────────────────────────────────────────────────────────────────────────────────────
def _main(monkeypatch, capsys, record, steps="grade"):
    order = []
    monkeypatch.setattr(ST, "default", lambda: ST.GajjalaStore(colls={}))
    monkeypatch.setattr(NG, "run", lambda *a, **k: {"errors": []})
    monkeypatch.setattr(NG, "grade_1m", lambda now, **k: {})
    monkeypatch.setattr(NG, "grade_audited", lambda now, **k: {})
    from chart_maps.gajjala import divergence as DV
    from chart_maps.gajjala import si_track as SIT
    from chart_maps.gajjala import vol_dried as VD
    monkeypatch.setattr(DV, "grade_divergence", lambda now, **k: {})
    monkeypatch.setattr(VD, "grade_night", lambda now: order.append("vol_dried") or {})
    monkeypatch.setattr(SIT, "record_night", lambda now, **k: order.append("si_track") or {})
    if record is not None:
        monkeypatch.setattr(RT, "nightly", lambda now, **k: order.append("runtrack") or record(now))
    code = NG.main(["--steps", steps])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return code, out, order


def test_main_runs_the_runners_record_after_the_si_track(monkeypatch, capsys):
    code, out, order = _main(monkeypatch, capsys, lambda now: {"opened": 2})
    assert code == 0 and order == ["vol_dried", "si_track", "runtrack"]
    assert out["gajjala_watch_runtrack"] == {"opened": 2}


def test_NEGATIVE_a_raising_record_never_reaches_errors_or_the_exit_code(monkeypatch, capsys):
    def boom(now):
        raise RuntimeError("down")
    code, out, _ = _main(monkeypatch, capsys, boom)
    assert code == 0 and out["errors"] == [] and out["gajjala_watch_runtrack"] == {"error": "record: RuntimeError"}


def test_NEGATIVE_a_broken_module_is_fenced_too(monkeypatch, capsys):
    import chart_maps.gajjala_watch as pkg
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.runtrack", None)
    monkeypatch.delattr(pkg, "runtrack", raising=False)
    code, out, _ = _main(monkeypatch, capsys, None)
    assert code == 0 and out["errors"] == [] and out["gajjala_watch_runtrack"]["error"].startswith("record: ")


def test_NEGATIVE_the_real_record_with_no_database_is_a_fault_not_an_error(monkeypatch, capsys):
    monkeypatch.setattr(RT.CO, "runtrack_coll", lambda db=None: None)
    code, out, _ = _main(monkeypatch, capsys, None)
    assert code == 0 and out["gajjala_watch_runtrack"]["faults"] == ["record"]


def test_NEGATIVE_without_the_grade_step_no_runners_record(monkeypatch, capsys):
    monkeypatch.setattr(ST, "default", lambda: ST.GajjalaStore(colls={}))
    monkeypatch.setattr(NG, "run", lambda *a, **k: {"errors": []})
    seen = []
    monkeypatch.setattr(RT, "nightly", lambda now, **k: seen.append(now) or {})
    assert NG.main(["--steps", "floats"]) == 0
    assert seen == [] and "gajjala_watch_runtrack" not in capsys.readouterr().out


def test_steps_unchanged_pin():
    assert NG.STEPS == ("floats", "halts", "history", "bases", "grade")


# ── the --once CLI ───────────────────────────────────────────────────────────────────────────────────────────────
def test_once_runs_the_same_function_and_dry_run_is_passed(monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr(RT, "nightly", lambda now, **k: seen.update(k) or {"opened": 0})
    assert RT.main(["--once", "--dry-run"]) == 0
    assert seen == {"dry": True} and json.loads(capsys.readouterr().out.strip().splitlines()[-1]) == {"opened": 0}
    assert RT.main(["--once"]) == 0 and seen == {"dry": False}


def test_NEGATIVE_without_once_nothing_runs(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(RT, "nightly", lambda now, **k: seen.append(1) or {})
    assert RT.main([]) == 2 and seen == []


# ── the probe's pins ─────────────────────────────────────────────────────────────────────────────────────────────
def test_probe_typed_names_equal_the_constants():
    p = _probe()
    assert p.KEEP == C.RUNNERS_KEEP_SESSIONS == RT.KEEP
    assert p.READS_COLL == ST.READS and p.LIST_COLL == C.COLL_LIST and p.RUNNERS_ID == C.RUNNERS_DOC_ID
    assert p.RECORD_COLL == C.COLL_RUNTRACK and set(p.REASONS) == set(RT.SEAT_REASONS)


@pytest.mark.parametrize("d", [RUN, "2026-11-20", "2026-11-25", "2026-12-24", "2027-01-02"])
def test_probe_window_equals_the_engine(d):
    assert _probe().window_of(d) == RT.window_of(d)


def test_probe_seat_keys_equal_the_engine_and_NEGATIVE_skip_the_same_runs():
    doc = rdoc([entry("BGLC", day_run(iso="2026-11-25")), entry("brk-b", day_run(), aplus_run(iso=WIN[3]))],
               [removed("DOGZ", "blocked", day_run()), removed("OLD", "not_a_reason", day_run()),
                removed("AXTX", "dismissed", day_run(iso=WIN[1]))])
    for through in (RUN, WIN[3], "2026-11-25"):
        assert _probe().seat_keys(doc, through) == {s["key"] for s in RT.seat_runs(doc, through)}
    assert not any(k.endswith("|OLD") for k in _probe().seat_keys(doc, "2026-11-25"))
    assert _probe().seat_keys(None, RUN) == set() == {s["key"] for s in RT.seat_runs(None, RUN)}


def test_NEGATIVE_the_probe_writes_nothing():
    src = PROBE.read_text()
    for w in ("insert_one", "insert_many", "update_one", "update_many", "replace_one", "delete_one", "delete_many",
              "find_one_and_", "bulk_write", "drop("):
        assert w not in src, w


# ── structural: nightly.py names the Watch ONLY for runtrack, ONLY inside the fence ──────────────────────────────
def _nightly_watch_imports():
    import ast
    tree = ast.parse(Path(NG.__file__).read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("chart_maps.gajjala_watch"):
            names = [f"{node.module}.{a.name}" for a in node.names]
        elif isinstance(node, ast.Import):
            names = [a.name for a in node.names if a.name.startswith("chart_maps.gajjala_watch")]
        elif isinstance(node, ast.ImportFrom) and node.module == "chart_maps":
            names = [f"chart_maps.{a.name}" for a in node.names if a.name.startswith("gajjala_watch")]
        hits += [(n, node) for n in names]
    return tree, hits


def test_NEGATIVE_nightly_names_the_watch_only_for_runtrack_inside_the_fence():
    import ast
    tree, hits = _nightly_watch_imports()
    assert [n for n, _ in hits] == ["chart_maps.gajjala_watch.runtrack"]
    node = hits[0][1]
    top = {id(n) for n in tree.body}
    assert id(node) not in top
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    fences = [t for t in ast.walk(main) if isinstance(t, ast.Try) and any(b is node for b in t.body)]
    assert len(fences) == 1 and fences[0].handlers
    assert any(isinstance(h.type, ast.Name) and h.type.id == "Exception" for h in fences[0].handlers)
    src = Path(NG.__file__).read_text(encoding="utf-8")
    for banned in ("gajjala_watch import colls", "gajjala_watch import loop", "gajjala_watch import build",
                   "gajjala_watch import constants", "gajjala_watch import payload", "gajjala_watch import store",
                   "gajjala_watch import runseat", "gajjala_watch.cross_alerts", "_popen", "spawn_child",
                   "spawn_loop", "WCO."):
        assert banned not in src, banned
