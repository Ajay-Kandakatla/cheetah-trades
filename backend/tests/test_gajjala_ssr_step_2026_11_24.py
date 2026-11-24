"""chart_maps/gajjala/run.py — the ⛔ SSR pass step (spec ssr §3.9, work package W3, 2026-11-24).

Ajay, verbatim (2026-11-23): "No shorting at the bid (SEC short-sale restriction) Can we check or this for other stocks
too?"

The pass hands its whole-market snapshot DICT {SYM: row}, the listed names' frames, the clock, the session, the listed
names and the snapshot's `good` bit to `short_interest.ssr.record_pass` — in its OWN try, after the 🧨 divergence step
and before the 🌫️ day read, never on an open and never on a dry run, never a key of `out`, never `out["errors"]`.
`_cron_deps()` wires it behind a FENCED import (a missing or broken module leaves the step off and logs one warning).
The pass summary and every store write are byte-identical with and without the step. No test here needs W1's module:
a stub `short_interest.ssr` is installed where the wiring is read.
"""
from __future__ import annotations

import ast
import copy
import inspect
import json
import logging
import re
import sys
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import store as ST
from tests.test_gajjala_run import NOW, Rec, make_deps, snap_row
from tests.test_gajjala_store import FakeColl

ROOT = Path(__file__).resolve().parents[1]
RUN_PY = ROOT / "chart_maps" / "gajjala" / "run.py"
SESSION = date(2026, 10, 13)
LOGGER = "chart_maps.gajjala.run"


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: True)


# ── helpers ───────────────────────────────────────────────────────────────────────────────────────────────────────
class RecColl(FakeColl):
    """A FakeColl that also LOGS every write (collection, op, args) into one shared list, deep-copied."""

    def __init__(self, name, log_):
        super().__init__()
        self._name, self._log = name, log_

    def update_one(self, q, upd, upsert=False):
        self._log.append((self._name, "update_one", copy.deepcopy(q), copy.deepcopy(upd), upsert))
        return super().update_one(q, upd, upsert=upsert)

    def replace_one(self, q, doc, upsert=False):
        self._log.append((self._name, "replace_one", copy.deepcopy(q), copy.deepcopy(doc), upsert))
        return super().replace_one(q, doc, upsert=upsert)

    def find_one_and_update(self, q, upd, upsert=False):
        self._log.append((self._name, "find_one_and_update", copy.deepcopy(q), copy.deepcopy(upd), upsert))
        return super().find_one_and_update(q, upd, upsert=upsert)

    def create_index(self, spec, **kw):
        self._log.append((self._name, "create_index", tuple(spec), copy.deepcopy(kw), None))
        return super().create_index(spec, **kw)


def rec_store():
    log_: list = []
    st = ST.GajjalaStore(colls={n: RecColl(n, log_) for n in ST.ALL})
    return st, log_


def _deps(**kw):
    deps, snapshot, send, status = make_deps(**{k: v for k, v in kw.items() if k in ("rows", "http")})
    for k, v in kw.items():
        if k not in ("rows", "http"):
            setattr(deps, k, v)
    return deps, snapshot, send, status


def frozen_stub(calls: list, ret=None):
    """W1's FROZEN signature (spec §3.5) — a call that does not bind to it fails here, not in the cron."""
    def record_pass(rows, frames, now, session, *, followed=(), good=True, db=None):
        calls.append({"rows": rows, "frames": frames, "now": now, "session": session, "followed": followed,
                      "good": good, "db": db})
        return ret if ret is not None else {"rows": len(rows), "new": 0}
    return record_pass


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def _scrub(obj, tokens: dict):
    """Two things differ run to run whatever the step does, and only those are masked: the lease token (a fresh uuid
    per pass — each distinct token reads as its first-seen ordinal, so WHERE a token is written stays compared) and the
    two pre-existing wall-clock stamps of the pass (the 🎾 squeeze_history `at`, the push claim's `claimed_at`) — a
    timestamp dated within two days of the REAL wall clock reads "<wall>" (every replayed clock is in October 2026)."""
    wall_from = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
    if isinstance(obj, datetime):
        return "<wall>" if obj.astimezone(timezone.utc).date().isoformat() >= wall_from else obj
    if isinstance(obj, str) and _ISO.match(obj):
        return "<wall>" if obj[:10] >= wall_from else obj
    if isinstance(obj, dict):
        return {k: (f"<token{tokens.setdefault(v, len(tokens))}>" if "token" in str(k) and isinstance(v, str)
                    else _scrub(v, tokens)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_scrub(v, tokens) for v in obj]
    return obj


def _bytes(obj) -> str:
    return json.dumps(_scrub(obj, {}), default=str, sort_keys=True)


def _summary(out: dict) -> str:
    return _bytes({k: v for k, v in out.items() if k != "wall_s"})


def _stub_module(monkeypatch, record_pass=None, *, has_record_pass=True):
    import short_interest
    mod = types.ModuleType("short_interest.ssr")
    if has_record_pass:
        mod.record_pass = record_pass or (lambda *a, **k: {})
    monkeypatch.setitem(sys.modules, "short_interest.ssr", mod)
    monkeypatch.setattr(short_interest, "ssr", mod, raising=False)
    return mod


def _break_import(monkeypatch):
    import short_interest
    monkeypatch.setitem(sys.modules, "short_interest.ssr", None)       # `import` of a None entry raises ImportError
    monkeypatch.delattr(short_interest, "ssr", raising=False)


# ── the call ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_cron_pass_calls_the_step_once_with_the_snapshot_dict_frames_and_listed_names():
    calls: list = []
    rows = {"GGA": snap_row(11.2, 8.0), "NOPE": snap_row(1.0, 0.95)}
    rows_copy = copy.deepcopy(rows)
    st, _log = rec_store()
    deps, snapshot, _send, _status = _deps(rows=rows, ssr=frozen_stub(calls))
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["ran"] and out["status"] == "ok" and out["errors"] == []
    assert len(calls) == 1
    c = calls[0]
    assert isinstance(c["rows"], dict) and c["rows"] is rows and c["rows"] == rows_copy   # handed over as is [C8]
    assert c["now"] == NOW.astimezone(timezone.utc) and c["session"] == SESSION
    assert c["followed"] == ["GGA"] == sorted(c["followed"])                           # the listed names
    assert set(c["frames"]) == {"GGA"} and c["good"] is True
    assert c["db"] is None                                                             # the pass never hands a store


def test_a_failed_snapshot_hands_good_false():
    calls: list = []
    deps, _snap, _send, _status = _deps(http=500, ssr=frozen_stub(calls))
    out = RUN.run_pass(NOW, store=rec_store()[0], deps=deps)
    assert out["status"] == "failed"
    assert len(calls) == 1 and calls[0]["good"] is False                               # NEGATIVE: never good on a 500


def test_a_narrowed_cron_pass_hands_only_the_narrowed_names():
    calls: list = []
    deps, _snap, _send, _status = _deps(ssr=frozen_stub(calls))
    RUN.run_pass(NOW, store=rec_store()[0], deps=deps, symbols=["NOPE"])
    assert len(calls) == 1 and calls[0]["followed"] == []                              # NOPE is not listed


# ── never on a default / dry / open pass ─────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_default_deps_never_carry_the_step():
    assert RUN.Deps().ssr is None
    assert RUN.dry_deps().ssr is None
    deps, _snap, _send, _status = _deps()
    assert deps.ssr is None
    out = RUN.run_pass(NOW, store=rec_store()[0], deps=deps)
    assert out["errors"] == [] and "ssr" not in out


def test_NEGATIVE_a_dry_pass_never_calls_the_step():
    calls: list = []
    deps, _snap, _send, _status = _deps(ssr=frozen_stub(calls))
    out = RUN.run_pass(NOW, store=rec_store()[0], deps=deps, dry=True)
    assert out["ran"] and calls == []


def test_NEGATIVE_an_on_open_pass_never_calls_the_step():
    calls: list = []
    deps, _snap, _send, _status = _deps(ssr=frozen_stub(calls))
    out = RUN.run_on_demand(NOW, store=rec_store()[0], deps=deps)
    assert out["ran"] and calls == []


def _main_env(monkeypatch):
    from chart_maps.gajjala import bar_close as BC
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.setattr(BC, "spawn_child", Rec(True))
    monkeypatch.setattr(R1, "spawn_loop", Rec(True))
    monkeypatch.setattr(RUN, "in_window", lambda *_a, **_k: True)
    for name in ("_spawn_watch", "_spawn_1m", "_spawn_luk", "_spawn_bar_close"):
        monkeypatch.setattr(RUN, name, lambda: None)
    monkeypatch.setattr(RUN, "dry_store", lambda *a, **k: None)
    monkeypatch.setattr(ST, "default", lambda: rec_store()[0])
    rp, od = Rec({"status": "ok"}), Rec({"status": "ok"})
    monkeypatch.setattr(RUN, "run_pass", rp)
    monkeypatch.setattr(RUN, "run_on_demand", od)
    return rp, od


@pytest.mark.parametrize("argv", [["--on-demand"], ["--dry-run"], ["--dry-run", "--on-demand"]])
def test_NEGATIVE_main_open_and_dry_paths_carry_no_step(monkeypatch, argv):
    _stub_module(monkeypatch)                                          # even with the module importable
    rp, od = _main_env(monkeypatch)
    assert RUN.main(argv) == 0
    calls = rp.calls + od.calls
    assert len(calls) == 1 and calls[0][1]["deps"].ssr is None


def test_main_cron_path_carries_the_step(monkeypatch):
    mod = _stub_module(monkeypatch)
    rp, _od = _main_env(monkeypatch)
    assert RUN.main([]) == 0
    assert rp.calls[0][1]["deps"].ssr is mod.record_pass


# ── byte-identical with and without the step ─────────────────────────────────────────────────────────────────────
def _run_pair(step):
    st0, log0 = rec_store()
    d0, _s, send0, status0 = _deps()
    out0 = RUN.run_pass(NOW, store=st0, deps=d0)
    st1, log1 = rec_store()
    d1, _s, send1, status1 = _deps(ssr=step)
    out1 = RUN.run_pass(NOW, store=st1, deps=d1)
    return (out0, log0, send0, status0, st0), (out1, log1, send1, status1, st1)


def test_NEGATIVE_the_summary_and_every_store_write_are_byte_identical_with_and_without_the_step():
    calls: list = []
    a, b = _run_pair(frozen_stub(calls, ret={"rows": 2, "new": 1, "final": False}))
    assert len(calls) == 1
    (out0, log0, send0, status0, st0), (out1, log1, send1, status1, st1) = a, b
    assert log0 and _bytes(log0) == _bytes(log1)                       # every recorded write, in order
    assert _bytes(log0).count('"<wall>"') == 2 and "2026-10-13 14:41:00" in _bytes(log0)   # the mask hides 2 stamps only
    assert _summary(out0) == _summary(out1)
    assert "ssr" not in out1 and "rows" not in _bytes(out1.get("errors"))
    assert _bytes(status0.calls) == _bytes(status1.calls)               # the /alerts row unchanged
    assert len(send0.calls) == len(send1.calls)                         # the step never sends
    assert {n: _bytes(c.docs) for n, c in st0._injected.items()} == {n: _bytes(c.docs) for n, c in st1._injected.items()}


def test_NEGATIVE_a_raising_step_still_records_the_pass_unchanged(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)

    def boom(rows, frames, now, session, *, followed=(), good=True, db=None):
        raise RuntimeError("ssr down")

    a, b = _run_pair(boom)
    (out0, log0, _s0, status0, st0), (out1, log1, _s1, status1, st1) = a, b
    assert out1["errors"] == out0["errors"] == [] and out1["status"] == out0["status"] == "ok"
    assert _summary(out0) == _summary(out1) and _bytes(log0) == _bytes(log1)
    assert st1.coll(ST.PASSES).docs                                     # the pass doc was recorded
    assert _bytes(status0.calls) == _bytes(status1.calls)
    msgs = [r.getMessage() for r in caplog.records if r.name == LOGGER]
    assert msgs.count("gajjala pass: the ⛔ SSR read failed") == 1


def test_NEGATIVE_a_raising_step_never_changes_the_exit_status(monkeypatch):
    real_run_pass = RUN.run_pass
    codes = {}
    for key, step in (("none", None), ("boom", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))):
        mp = pytest.MonkeyPatch()
        try:
            deps, _s, _send, _status = _deps(ssr=step)
            deps.audited_store = lambda _st: None
            mp.setattr(RUN, "in_window", lambda *_a, **_k: True)
            for name in ("_spawn_watch", "_spawn_1m", "_spawn_luk", "_spawn_bar_close"):
                mp.setattr(RUN, name, lambda: None)
            mp.setattr(ST, "default", lambda: rec_store()[0])
            mp.setattr(RUN, "_cron_deps", lambda d=deps: d)
            seen = {}

            def rp(now=None, *, store=None, deps=None, symbols=None, **k):
                seen["out"] = real_run_pass(NOW, store=store, deps=deps, symbols=symbols)
                return seen["out"]
            mp.setattr(RUN, "run_pass", rp)
            codes[key] = (RUN.main([]), seen["out"]["status"], seen["out"]["errors"])
        finally:
            mp.undo()
    assert codes["none"] == codes["boom"] == (0, "ok", [])


# ── the cron wiring (fenced) ─────────────────────────────────────────────────────────────────────────────────────
def test_cron_deps_wire_record_pass(monkeypatch):
    mod = _stub_module(monkeypatch)
    d = RUN._cron_deps()
    assert d.ssr is mod.record_pass
    from chart_maps.gajjala import divergence as DV
    assert d.divergence is DV.run_step                                  # the other cron steps unchanged


def test_NEGATIVE_a_failed_import_leaves_the_step_off_with_one_warning(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    _break_import(monkeypatch)
    d = RUN._cron_deps()
    assert d.ssr is None
    from chart_maps.gajjala import divergence as DV
    assert d.divergence is DV.run_step                                  # the rest of the cron Deps still built
    warns = [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.WARNING]
    assert len(warns) == 1 and warns[0].getMessage().startswith("gajjala pass: the ⛔ SSR step is not wired: ")
    assert "ImportError" in warns[0].getMessage() or "ModuleNotFoundError" in warns[0].getMessage()


def test_NEGATIVE_a_broken_module_leaves_the_step_off_with_one_warning(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    _stub_module(monkeypatch, has_record_pass=False)
    d = RUN._cron_deps()
    assert d.ssr is None
    warns = [r for r in caplog.records if r.name == LOGGER and r.levelno == logging.WARNING]
    assert [w.getMessage() for w in warns] == ["gajjala pass: the ⛔ SSR step is not wired: AttributeError"]


def test_the_one_definition_pin_still_holds_with_the_step(monkeypatch):
    _stub_module(monkeypatch)
    rp, _od = _main_env(monkeypatch)
    RUN.main([])
    assert RUN._cron_deps() == rp.calls[0][1]["deps"]                    # test_gajjala_bar_close_2026_11_09.py:498


# ── source guards ────────────────────────────────────────────────────────────────────────────────────────────────
def _ifs(tree, test: str):
    return [n for n in ast.walk(tree) if isinstance(n, ast.If)
            and ast.unparse(n.test).replace("(", "").replace(")", "") == test]


def test_the_step_sits_after_the_divergence_step_and_before_the_day_read():
    body = inspect.getsource(RUN.run_pass)
    i = body.index("if deps.divergence is not None and not push_dry:")
    j = body.index("if deps.ssr is not None and not push_dry:")
    k = body.index("if deps.day_read is not None and not dry:")
    assert i < j < k
    tree = ast.parse(RUN_PY.read_text(encoding="utf-8"))
    hooks = _ifs(tree, "deps.ssr is not None and not push_dry")
    assert len(hooks) == 1
    src = ast.unparse(hooks[0])
    assert "errors" not in src and "out[" not in src                     # NEVER out["errors"], never a key of out
    assert len(hooks[0].body) == 1 and isinstance(hooks[0].body[0], ast.Try)   # its OWN try
    call = [n for n in ast.walk(hooks[0]) if isinstance(n, ast.Call) and ast.unparse(n.func) == "deps.ssr"]
    assert len(call) == 1
    assert [ast.unparse(a) for a in call[0].args] == ["rows", "frames", "now", "session"]
    assert {kw.arg: ast.unparse(kw.value) for kw in call[0].keywords} == {"followed": "names", "good": "good"}


def test_NEGATIVE_the_pass_never_imports_the_outside_readers():
    src = RUN_PY.read_text(encoding="utf-8")
    assert "ssr_lists" not in src and "ssr_corp" not in src              # an outside call never rides the pass
    tree = ast.parse(src)
    froms = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "short_interest"]
    assert [[a.name for a in n.names] for n in froms] == [["ssr"]]
    assert "ssr" not in inspect.getsource(RUN.dry_deps)
    assert "ssr" not in inspect.getsource(RUN.main)                      # main's on-demand Deps is not given it
    assert "ssr" not in inspect.getsource(RUN.run_on_demand)


@pytest.mark.parametrize("name", ["alerts.py", "potential.py", "tab.py", "ledger.py"])
def test_NEGATIVE_the_gates_and_the_board_import_no_ssr(name):
    tree = ast.parse((ROOT / "chart_maps" / "gajjala" / name).read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            assert "ssr" not in (n.module or "") and all("ssr" not in a.name for a in n.names), (name, ast.unparse(n))
        elif isinstance(n, ast.Import):
            assert all("ssr" not in a.name for a in n.names), (name, ast.unparse(n))
