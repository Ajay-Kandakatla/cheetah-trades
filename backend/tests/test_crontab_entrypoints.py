"""Every entrypoint in backend/crontab must RESOLVE before it ever runs.

2026-10-21: the 05:15 Gappers warm
    python -c "from overnight import movers as m; m.scan_movers(min_gap_pct=0.5)"
named a function that was never written (the line is from 05-11, overnight/movers.py
from 05-25) and raised AttributeError every morning for five months; nothing pinned
it. The line is gone, not replaced: GET /overnight/movers computes on demand with a
per-symbol Mongo cache whose TTL is 120 s in pre-market (movers._cache_ttl_sec), so
a 05:15 warm is stale by 05:17.

This suite, for every job line:
  * `python -c "<body>"` — imports the body's modules and getattr-resolves every
    import-rooted call target WITHOUT calling anything (ast only).
  * `python -m X …` — X must be importable (a package needs a __main__), and the
    module / pkg.mod:func the market_hours.gate wrapper runs must resolve the way
    gate.py resolves it (runpy.run_module / importlib + getattr).
Hermetic: no network, no Mongo (tests/conftest.py refuses MongoClient).

NEGATIVE: the dead line is gone; the resolver flags a missing attribute, a missing
module, an unbound name and a non-callable; the resolver never executes a call.
"""
from __future__ import annotations

import ast
import builtins
import importlib
import importlib.machinery
import importlib.util
import shlex
import sys
import types
from pathlib import Path

import pytest

CRONTAB = Path(__file__).resolve().parents[1] / "crontab"
PYTHON = "/usr/local/bin/python"
GATE = "market_hours.gate"
DEAD_LINE_BODY = "from overnight import movers as m; m.scan_movers(min_gap_pct=0.5)"


# ── crontab parsing ──────────────────────────────────────────────────────────

def job_lines(text: str | None = None) -> list[tuple[int, str]]:
    """(1-based line number, line) for every non-blank, non-comment line."""
    text = CRONTAB.read_text(encoding="utf-8") if text is None else text
    return [(n, line) for n, line in enumerate(text.splitlines(), 1)
            if line.strip() and not line.lstrip().startswith("#")]


def command_argv(line: str) -> list[str]:
    """The command after the five cron fields, shell-split (redirections become
    their own tokens, which the extractors below never read)."""
    return shlex.split(line.split(None, 5)[5])


def _python_at(argv: list[str], i: int) -> bool:
    return argv[i].rsplit("/", 1)[-1] in ("python", "python3")


def dash_c_bodies(argv: list[str]) -> list[str]:
    """Every `python -c "<body>"` body on the command line (usually one)."""
    out = []
    for i, tok in enumerate(argv):
        if _python_at(argv, i) and i + 2 < len(argv) and argv[i + 1] == "-c":
            out.append(argv[i + 2])
    return out


def dash_m_targets(argv: list[str]) -> list[tuple[str, str | None]]:
    """(module, func_or_None) for every `python -m` on the command line, plus what
    the market_hours.gate wrapper itself runs: `gate <module> [args]` → (module, None)
    via runpy; `gate --call pkg.mod:func` → (pkg.mod, func) via importlib + getattr."""
    out: list[tuple[str, str | None]] = []
    for i, tok in enumerate(argv):
        if not (_python_at(argv, i) and i + 2 < len(argv) and argv[i + 1] == "-m"):
            continue
        mod = argv[i + 2]
        out.append((mod, None))
        if mod != GATE:
            continue
        rest = argv[i + 3:]
        if rest and rest[0] == "--call" and len(rest) > 1:
            pkg_mod, _, func = rest[1].partition(":")
            out.append((pkg_mod, func or None))
        elif rest and not rest[0].startswith("-"):
            out.append((rest[0], None))
    return out


# ── resolution (imports + getattr only; never a call) ────────────────────────

class Unresolved(Exception):
    pass


def _import(name: str):
    try:
        return importlib.import_module(name)
    except Exception as exc:  # ModuleNotFoundError, or the module's own import-time crash
        raise Unresolved(f"import {name}: {type(exc).__name__}: {exc}") from exc


def _from_import(module: str, name: str):
    mod = _import(module)
    if hasattr(mod, name):
        return getattr(mod, name)
    try:
        return importlib.import_module(f"{module}.{name}")
    except Exception as exc:
        raise Unresolved(f"from {module} import {name}: module {module!r} has no attribute "
                         f"{name!r} and no submodule ({type(exc).__name__}: {exc})") from exc


def _attr(obj, attr: str):
    """getattr, with one more chance for a submodule that the package does not
    import itself (`import catalysts; catalysts.premarket.x()`)."""
    if hasattr(obj, attr):
        return getattr(obj, attr)
    if isinstance(obj, types.ModuleType):
        try:
            return importlib.import_module(f"{obj.__name__}.{attr}")
        except Exception:
            pass
    raise Unresolved(f"{getattr(obj, '__name__', type(obj).__name__)!r} has no attribute {attr!r}")


def _chain(func: ast.expr) -> list[str] | None:
    """`m.a.b` → ["m", "a", "b"]; None when the call is not rooted in a plain name
    (`x().get(...)`, `d["k"](...)`) — those are not import targets."""
    if isinstance(func, ast.Name):
        return [func.id]
    if isinstance(func, ast.Attribute):
        base = _chain(func.value)
        return None if base is None else base + [func.attr]
    return None


def resolve_body(body: str) -> list[str]:
    """Problems with one `python -c` body; [] means every import resolves and every
    import-rooted call target exists and is callable. Nothing is executed."""
    try:
        tree = ast.parse(body)
    except SyntaxError as exc:
        return [f"syntax: {exc}"]
    problems: list[str] = []
    bound: dict[str, object] = {}
    local: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                try:
                    _import(a.name)
                    bound[a.asname or a.name.split(".")[0]] = (
                        sys.modules[a.name] if a.asname else sys.modules[a.name.split(".")[0]])
                except Unresolved as exc:
                    problems.append(str(exc))
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                try:
                    bound[a.asname or a.name] = _from_import(node.module or "", a.name)
                except Unresolved as exc:
                    problems.append(str(exc))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            local.add(node.id)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        chain = _chain(node.func)
        if chain is None:
            continue
        root, *attrs = chain
        if root in bound:
            obj = bound[root]
            try:
                for attr in attrs:
                    obj = _attr(obj, attr)
            except Unresolved as exc:
                problems.append(f"{'.'.join(chain)}: {exc}")
                continue
            if not callable(obj):
                problems.append(f"{'.'.join(chain)}: not callable ({type(obj).__name__})")
        elif root in local or hasattr(builtins, root):
            continue
        else:
            problems.append(f"{'.'.join(chain)}: name {root!r} is never imported or assigned")
    return problems


def resolve_module_target(module: str, func: str | None) -> list[str]:
    """What `python -m module` (runpy) or gate `--call module:func` needs to exist."""
    try:
        spec = importlib.util.find_spec(module)
    except Exception as exc:  # a missing parent package raises ModuleNotFoundError
        return [f"-m {module}: {type(exc).__name__}: {exc}"]
    if spec is None:
        return [f"-m {module}: no such module"]
    if func is None:
        if spec.submodule_search_locations is not None:  # a package: runpy needs __main__
            try:
                main_spec = importlib.util.find_spec(f"{module}.__main__")
            except Exception:
                main_spec = None
            if main_spec is None:
                return [f"-m {module}: package without a __main__ module"]
        return []
    try:
        fn = _attr(_import(module), func)
    except Unresolved as exc:
        return [f"--call {module}:{func}: {exc}"]
    return [] if callable(fn) else [f"--call {module}:{func}: not callable"]


# ── the crontab, line by line ────────────────────────────────────────────────

DASH_C = [(n, body) for n, line in job_lines() for body in dash_c_bodies(command_argv(line))]
DASH_M = [(n, mod, func) for n, line in job_lines() for mod, func in dash_m_targets(command_argv(line))]


@pytest.mark.parametrize("lineno,body", DASH_C, ids=[f"L{n}" for n, _ in DASH_C])
def test_every_python_dash_c_target_resolves(lineno, body):
    assert resolve_body(body) == [], f"crontab:{lineno}: {body}"


@pytest.mark.parametrize("lineno,module,func", DASH_M,
                         ids=[f"L{n}:{m}" + (f":{f}" if f else "") for n, m, f in DASH_M])
def test_every_python_dash_m_module_resolves(lineno, module, func):
    assert resolve_module_target(module, func) == [], f"crontab:{lineno}: -m {module} {func or ''}"


def test_the_parser_sees_the_known_lines():
    bodies = [b for _, b in DASH_C]
    assert len(bodies) >= 15, bodies
    assert any("reminder.fire_due()" in b for b in bodies)
    assert any("scan_premarket()" in b for b in bodies)
    mods = {m for _, m, _ in DASH_M}
    assert {"overnight.scan", "overnight.push", "sepa.cli", GATE} <= mods, mods
    assert ("portfolio.alerts", "run_drop_attribution_default") in {(m, f) for _, m, f in DASH_M}


def test_every_python_job_line_uses_the_absolute_interpreter():
    """cheetah_cron_pitfalls: a bare `python` fork-execs to nothing under supercronic."""
    for n, line in job_lines():
        argv = command_argv(line)
        for i, tok in enumerate(argv):
            if _python_at(argv, i):
                assert tok == PYTHON, f"crontab:{n}: {tok}"


def test_the_parser_handles_both_gate_forms():
    argv = shlex.split(f"{PYTHON} -m {GATE} --call portfolio.alerts:run_drop_attribution_default")
    assert dash_m_targets(argv) == [(GATE, None), ("portfolio.alerts", "run_drop_attribution_default")]
    argv = shlex.split(f"{PYTHON} -m {GATE} growth earnings")
    assert dash_m_targets(argv) == [(GATE, None), ("growth", None)]
    argv = shlex.split(f"{PYTHON} -m sepa.qoq backfill --limit 900 >> /var/log/cron.log 2>&1")
    assert dash_m_targets(argv) == [("sepa.qoq", None)]
    assert dash_c_bodies(shlex.split("curl -sS 'http://api:8000/x'")) == []


# ── NEGATIVE ─────────────────────────────────────────────────────────────────

def test_negative_the_dead_gappers_warm_line_is_gone():
    lines = [ln for _, ln in job_lines()]
    assert not [ln for ln in lines if "scan_movers" in ln]
    assert not [ln for ln in lines if "overnight import movers" in ln or "overnight.movers" in ln]


def test_negative_the_resolver_flags_the_dead_line():
    problems = resolve_body(DEAD_LINE_BODY)
    assert len(problems) == 1 and "scan_movers" in problems[0], problems
    assert "no attribute" in problems[0]


def test_the_live_gappers_entrypoints_do_resolve():
    assert resolve_body("from overnight import movers as m; m.overnight_movers(['SPY'], min_gap_pct=0.5)") == []
    assert resolve_body("from overnight import movers as m; m.overnight_for_symbol_cached('SPY')") == []


def test_negative_missing_module():
    assert any("nope" in p for p in resolve_body("from overnight import nope as m; m.x()"))
    assert any("no_such_mod_xyz" in p for p in resolve_body("import no_such_mod_xyz; no_such_mod_xyz.f()"))
    assert resolve_module_target("overnight.nope", None) == ["-m overnight.nope: no such module"]
    assert resolve_module_target("no_such_pkg_xyz.mod", None)[0].startswith("-m no_such_pkg_xyz.mod:")


def test_negative_unbound_name_and_not_callable():
    probs = resolve_body("from overnight import movers as m; mm.overnight_movers([])")
    assert probs == ["mm.overnight_movers: name 'mm' is never imported or assigned"]
    probs = resolve_body("from overnight import movers as m; m.BASE_URL()")
    assert probs == ["m.BASE_URL: not callable (str)"]
    assert resolve_module_target("overnight.movers", "BASE_URL") == ["--call overnight.movers:BASE_URL: not callable"]
    assert resolve_module_target("overnight.movers", "scan_movers")[0].startswith("--call overnight.movers:scan_movers:")


def test_negative_a_syntax_error_is_reported_not_raised():
    assert resolve_body("from overnight import movers as m; m.(")[0].startswith("syntax:")


def test_negative_a_package_without_main_is_not_runnable(tmp_path, monkeypatch):
    pkg = tmp_path / "cron_probe_pkg_nomain"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    assert resolve_module_target("cron_probe_pkg_nomain", None) == \
        ["-m cron_probe_pkg_nomain: package without a __main__ module"]


def test_the_resolver_never_executes_a_call(monkeypatch):
    calls: list[int] = []

    def boom(*a, **k):
        calls.append(1)
        raise RuntimeError("executed")
    mod = types.ModuleType("cron_probe_fake_mod")
    mod.__spec__ = importlib.machinery.ModuleSpec("cron_probe_fake_mod", None)
    mod.boom = boom
    monkeypatch.setitem(sys.modules, "cron_probe_fake_mod", mod)
    assert resolve_body("import cron_probe_fake_mod as m; m.boom(1); [m.boom(x) for x in m.boom()]") == []
    assert resolve_module_target("cron_probe_fake_mod", "boom") == []
    assert calls == []
