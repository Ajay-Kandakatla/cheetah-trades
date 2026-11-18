"""🌫️ Day read — the WIRING (spec WP-B, 2026-11-15): the pass step in chart_maps/gajjala/run.py and the served key
`day_read` on gajjala.tab.build (GG5, GG1; None on 🧪) and luk.tab.build.

Ajay 2026-11-15, answering "do you want a 'choppy day' label on the Gajjala tab now, just as information? Making it a
gate would wait for that recorder's result." — verbatim: "yes". INFORMATION ONLY: the step's return is never bound,
never a key of the pass summary, never an error of the pass; the block is served to the primary owner only.

Every day_read seam is STUBBED here (a fake `chart_maps.gajjala.day_read` module, or the tabs' `_day_read` helper
monkeypatched), so this file is green with or without the engine module (WP-A). NEGATIVES: a dry pass never calls the
step; a raising step leaves the pass summary byte-equal; a superseded on-open pass never reaches the step; non-owners,
a truthy non-True owner and the 🧪 audited variant read None; a Luk build with an injected store never reaches
GS.default(); no gate / push / lane module imports or names the day read.
"""
from __future__ import annotations

import ast
import inspect
import logging
import re
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

import chart_maps.gajjala as GPKG
from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from chart_maps.luk import tab as LT
from tests.test_gajjala_run import NOW, S, make_deps
from tests.test_gajjala_store import FakeColl, fake_store
from tests import test_luk_tab as LTT
from chart_maps.gajjala import constants as GC


@pytest.fixture(autouse=True, scope="module")
def gg1_on():
    """2026-11-18 — the page retired (GC.GAJJALA_1M_ENABLED False, Ajay: "This is good info stop 1 min tab it was a good
    experiment"); this module pins how it RAN 2026-10-27 … 2026-11-17 and how it runs again if the word flips back.
    Module scope so the module-scoped fixture day is built ON too; a test that sets the switch False still can."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(GC, "GAJJALA_1M_ENABLED", True)
        yield


BACKEND = Path(__file__).resolve().parents[1]
SOURCES = {"run": BACKEND / "chart_maps" / "gajjala" / "run.py",
           "gtab": BACKEND / "chart_maps" / "gajjala" / "tab.py",
           "ltab": BACKEND / "chart_maps" / "luk" / "tab.py"}
WORD = re.compile(r"\bday_read\b")


# ── fixtures ───────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture(autouse=True)
def _no_1m_spawn(monkeypatch):
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: True)


class Rec:
    def __init__(self, ret=None, exc=None, log_=None, tag=None):
        self.calls, self.ret, self.exc, self.log, self.tag = [], ret, exc, log_, tag

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        if self.log is not None:
            self.log.append(self.tag)
        if self.exc is not None:
            raise self.exc
        return self.ret


@pytest.fixture
def stub_dr(monkeypatch):
    """A fake `chart_maps.gajjala.day_read` (the WP-A seams: run_step, load_doc, served_block) — sys.modules AND the
    package attribute, so `from . import day_read` resolves to it whether or not the real module exists."""
    m = types.ModuleType("chart_maps.gajjala.day_read")
    m.STATE_ID = "day_read"
    m.run_step = Rec(ret={"doc": 1})
    m.load_doc = Rec(ret={"the": "doc"})
    m.served_block = Rec(ret={"state": "read", "head": "stub"})
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala.day_read", m)
    monkeypatch.setattr(GPKG, "day_read", m, raising=False)
    return m


def _writes(st) -> dict:
    return {n: c.writes for n, c in st._injected.items()}


def _baseline():
    st = fake_store()
    deps, *_ = make_deps()
    out = RUN.run_pass(NOW, store=st, deps=deps)
    return out, _writes(st)


# ── the pass step (run.py) ─────────────────────────────────────────────────────────────────────────────────────────
def test_the_dep_defaults_to_none_and_the_dry_deps_leave_it_off():
    assert RUN.Deps().day_read is None
    assert RUN.dry_deps().day_read is None
    assert make_deps()[0].day_read is None                         # the WRITES golden's deps never run the step


def test_a_non_writing_step_leaves_the_pass_summary_and_writes_byte_equal():
    base_out, base_w = _baseline()
    st = fake_store()
    deps, *_ = make_deps()
    deps.day_read = Rec(ret={"never": "bound"})
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert len(deps.day_read.calls) == 1
    assert out == base_out and set(out) == set(base_out)           # no key added, nothing of the return read
    assert "day_read" not in out and "never" not in repr(out)
    assert _writes(st) == base_w


def test_the_step_runs_once_with_st_now_session_after_the_alerts_and_the_potentials(monkeypatch):
    order: list = []
    real_al, real_pt = AL.run_pass, PT.run_pass

    def al(*a, **k):
        order.append("alerts")
        return real_al(*a, **k)

    def pt(*a, **k):
        order.append("potential")
        return real_pt(*a, **k)
    monkeypatch.setattr(AL, "run_pass", al)
    monkeypatch.setattr(PT, "run_pass", pt)
    st = fake_store()
    deps, *_ = make_deps()
    deps.day_read = Rec(log_=order, tag="day_read")
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["ran"] and out["status"] == "ok"
    (a, k), = deps.day_read.calls
    assert a[0] is st and a[1] == NOW and a[2] == S and k == {}
    assert order == ["alerts", "potential", "day_read"]


def test_NEGATIVE_a_dry_pass_never_calls_the_step():
    deps, *_ = make_deps()
    deps.day_read = Rec()
    out = RUN.run_pass(NOW, store=RUN.dry_store(fake_store()), deps=deps, dry=True)
    assert out["ran"] and deps.day_read.calls == []


def test_NEGATIVE_a_raising_step_never_reaches_the_errors_and_the_summary_stays_byte_equal(caplog):
    base_out, base_w = _baseline()
    st = fake_store()
    deps, *_ = make_deps()
    deps.day_read = Rec(exc=RuntimeError("the read broke"))
    caplog.set_level(logging.ERROR, logger="chart_maps.gajjala.run")
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert len(deps.day_read.calls) == 1
    assert out == base_out and out["errors"] == base_out["errors"] and out["status"] == base_out["status"] == "ok"
    assert _writes(st) == base_w
    assert any("the day read failed" in r.getMessage() for r in caplog.records)


def test_C6_an_on_open_pass_checks_the_token_before_the_step(monkeypatch):
    order: list = []
    real_pt = PT.run_pass

    def pt(*a, **k):
        order.append("potential")
        return real_pt(*a, **k)
    monkeypatch.setattr(PT, "run_pass", pt)
    st = fake_store()
    real_owner = st.lease_owner_is

    def owner_is(token):
        order.append("mine")
        return real_owner(token)
    monkeypatch.setattr(st, "lease_owner_is", owner_is)
    deps, *_ = make_deps()
    deps.day_read = Rec(log_=order, tag="day_read")
    out = RUN.run_on_demand(NOW, store=st, deps=deps)
    assert out["ran"] and out.get("status") != "superseded"
    assert len(deps.day_read.calls) == 1
    i_dr = order.index("day_read")
    assert order[i_dr - 1] == "mine" and order.index("potential") < i_dr - 1      # potential → mine → day_read


def test_C6_a_superseded_token_check_propagates_and_the_step_is_never_called(monkeypatch):
    flipped = {"on": False}
    real_pt = PT.run_pass

    def pt(*a, **k):
        res = real_pt(*a, **k)
        flipped["on"] = True                                          # the cron takes the lease over right here
        return res
    monkeypatch.setattr(PT, "run_pass", pt)
    st = fake_store()
    real_owner = st.lease_owner_is
    monkeypatch.setattr(st, "lease_owner_is", lambda token: (not flipped["on"]) and real_owner(token))
    deps, *_ = make_deps()
    deps.day_read = Rec()
    out = RUN.run_on_demand(NOW, store=st, deps=deps)
    assert deps.day_read.calls == []
    assert out["status"] == "superseded" and out["superseded"] == 1
    assert not [k for k in st.coll(ST.PASSES).docs if k.endswith("|open")]


def test_NEGATIVE_a_cron_pass_never_calls_the_token_check_inside_the_step(monkeypatch):
    st = fake_store()
    monkeypatch.setattr(st, "lease_owner_is", lambda *a, **k: pytest.fail("the cron never checks"))
    deps, *_ = make_deps()
    deps.day_read = Rec()
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["ran"] and len(deps.day_read.calls) == 1


def _step_try() -> ast.Try:
    tree = ast.parse(SOURCES["run"].read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_pass")
    for node in ast.walk(fn):
        if (isinstance(node, ast.If) and "deps.day_read is not None" in ast.unparse(node.test)
                and node.body and isinstance(node.body[0], ast.Try)):
            return node
    raise AssertionError("no day-read step in run_pass")


def test_source_the_step_reraises_superseded_before_its_broad_except_and_binds_nothing():
    step = _step_try()
    assert "not dry" in ast.unparse(step.test)
    tr = step.body[0]
    first = tr.body[0]
    assert isinstance(first, ast.If) and ast.unparse(first.test) == "on_demand"
    assert ast.unparse(first.body[0]) == "mine()"                     # A8 first
    call = tr.body[1]
    assert isinstance(call, ast.Expr) and ast.unparse(call).startswith("deps.day_read(")   # a bare statement
    assert len(tr.body) == 2
    names = [ast.unparse(h.type) if h.type is not None else None for h in tr.handlers]
    assert names == ["_Superseded", "Exception"]
    assert isinstance(tr.handlers[0].body[0], ast.Raise) and tr.handlers[0].body[0].exc is None
    assert "errors" not in ast.unparse(tr.handlers[1])               # NEVER out["errors"]
    src = SOURCES["run"].read_text(encoding="utf-8")
    line = next(ln for ln in src.splitlines() if "deps.day_read(" in ln)
    assert line.strip().startswith("deps.day_read(") and "=" not in line.split("#")[0]


def test_the_cron_and_on_open_paths_wire_run_step(stub_dr):
    assert RUN._cron_deps().day_read is stub_dr.run_step
    src = SOURCES["run"].read_text(encoding="utf-8")
    assert src.count("day_read=DR.run_step") == 2                    # _cron_deps + main's on-demand Deps
    main_src = inspect.getsource(RUN.main)
    assert "Deps(promo_tags=PN.default_tags, day_read=DR.run_step)" in main_src
    assert "day_read" not in inspect.getsource(RUN.dry_deps)          # NEGATIVE: the dry deps stay off


# ── the gajjala tab (GG5 / GG1 / 🧪) ───────────────────────────────────────────────────────────────────────────────
TAB_NOW = datetime(2026, 10, 13, 14, 41, tzinfo=timezone.utc)                # 10:41 ET, a market day


def _gbuild(**kw):
    kw.setdefault("store", fake_store())
    return GT.build("", now=TAB_NOW, **kw)


def test_the_owner_is_served_the_block_on_gg5(monkeypatch):
    rec = Rec(ret={"state": "read", "head": "x"})
    monkeypatch.setattr(GT, "_day_read", rec)
    st = fake_store()
    out = _gbuild(store=st, owner=True)
    assert out["day_read"] == {"state": "read", "head": "x"}
    (a, _k), = rec.calls
    assert a[0] is st and a[2] == TAB_NOW


@pytest.mark.parametrize("owner", [False, object(), 1, "yes"])
def test_NEGATIVE_anyone_but_the_owner_reads_none(monkeypatch, owner):
    rec = Rec(ret={"state": "read", "head": "x"})
    monkeypatch.setattr(GT, "_day_read", rec)
    out = _gbuild(owner=owner)
    assert "day_read" in out and out["day_read"] is None and rec.calls == []


def test_NEGATIVE_the_audited_variant_never_serves_it(monkeypatch):
    rec = Rec(ret={"state": "read", "head": "x"})
    monkeypatch.setattr(GT, "_day_read", rec)
    g5 = fake_store()
    gga = ST.GajjalaStore(colls={n: FakeColl() for n in ST.OWN}, variant=V.GGA, shared=g5)
    out = GT.build("", now=TAB_NOW, store=gga, variant=V.GGA, owner=True)
    assert out["day_read"] is None and rec.calls == []


def test_gg1_hands_its_store_whose_shared_is_gg5(monkeypatch):
    rec = Rec(ret={"state": "read", "head": "x"})
    monkeypatch.setattr(GT, "_day_read", rec)
    g5 = fake_store()
    g1 = ST.GajjalaStore(colls={n: FakeColl() for n in ST.OWN}, variant=V.GG1, shared=g5)
    out = GT.build("", now=TAB_NOW, store=g1, variant=V.GG1, owner=True)
    assert out["day_read"] == {"state": "read", "head": "x"}
    (a, _k), = rec.calls
    assert a[0] is g1 and a[0].shared is g5


def test_the_helper_reads_gg5s_doc_through_shared_and_gg5_reads_its_own(stub_dr):
    g5 = fake_store()
    g1 = ST.GajjalaStore(colls={n: FakeColl() for n in ST.OWN}, variant=V.GG1, shared=g5)
    assert GT._day_read(g1, S, TAB_NOW) == {"state": "read", "head": "stub"}
    assert stub_dr.load_doc.calls[-1][0] == (g5,)                     # GG1 → GG5's state doc
    assert GT._day_read(g5, S, TAB_NOW) == {"state": "read", "head": "stub"}
    assert stub_dr.load_doc.calls[-1][0] == (g5,)                     # GG5 → its own
    assert stub_dr.served_block.calls[-1][0] == ({"the": "doc"}, S, TAB_NOW)


def test_NEGATIVE_a_raising_helper_serves_none_and_every_other_key_unchanged(monkeypatch):
    monkeypatch.setattr(GT, "_day_read", Rec(ret={"state": "read", "head": "x"}))
    good = _gbuild(store=fake_store(), owner=True)
    monkeypatch.setattr(GT, "_day_read", Rec(exc=RuntimeError("no doc")))
    bad = _gbuild(store=fake_store(), owner=True)
    assert bad["day_read"] is None
    assert {k: v for k, v in bad.items() if k != "day_read"} == {k: v for k, v in good.items() if k != "day_read"}


# ── the luk tab ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_luk_payload_keys_and_the_fault_payload():
    assert "day_read" in LT.PAYLOAD_KEYS and LT.PAYLOAD_KEYS[-1] == "ended"         # 🏁 fold contract pins "ended")
    f = LT.fault_payload("nope")
    assert set(f) == set(LT.PAYLOAD_KEYS) and f["day_read"] is None
    out = LTT._build()
    assert set(out) == set(LT.PAYLOAD_KEYS) and out["day_read"] is None


_LT_SRC = SOURCES["ltab"].read_text()


def _fn_body(src: str, name: str) -> str:
    i = src.index(f"\ndef {name}(")
    j = src.find("\ndef ", i + 1)
    return src[i:j if j >= 0 else None]


def test_the_luk_ended_fold_contract_pins_still_hold_with_day_read():
    pk = re.search(r'^PAYLOAD_KEYS = \([\s\S]*?\)\s*(?:#[^\n]*)?\n(?=\S)', _LT_SRC, re.M)
    assert pk and re.search(r'"ended"\)', pk.group(0)) and '"day_read",' in pk.group(0)
    body = _fn_body(_LT_SRC, "fault_payload")
    assert re.search(r'"scan": None, "ended": None\}', body) and '"day_read": None,' in body


def test_NEGATIVE_the_contract_regexes_reject_day_read_after_ended():
    bad_pk = 'PAYLOAD_KEYS = ("scan",\n                "ended",\n                "day_read")\nX = 1\n'
    m = re.search(r'^PAYLOAD_KEYS = \([\s\S]*?\)\s*(?:#[^\n]*)?\n(?=\S)', bad_pk, re.M)
    assert m and not re.search(r'"ended"\)', m.group(0))
    assert not re.search(r'"scan": None, "ended": None\}', '"scan": None, "ended": None,\n "day_read": None}')


def test_NEGATIVE_an_injected_store_without_gg5_store_never_reaches_gs_default(monkeypatch):
    from chart_maps.gajjala import store as GS
    monkeypatch.setattr(GS, "default", lambda: pytest.fail("GS.default() reached from a test build"))
    rec = Rec(ret={"state": "read"})
    monkeypatch.setattr(LT, "_day_read", rec)
    out = LT.build("", now=LTT.NOW, store=LTT.fixture_store(), owner=True)
    assert out["day_read"] is None and rec.calls == []


def test_the_owner_with_a_gg5_store_is_served(monkeypatch):
    rec = Rec(ret={"state": "read", "head": "x"})
    monkeypatch.setattr(LT, "_day_read", rec)
    g5 = fake_store()
    out = LT.build("", now=LTT.NOW, store=LTT.fixture_store(), owner=True, gg5_store=g5)
    assert out["day_read"] == {"state": "read", "head": "x"} and set(out) == set(LT.PAYLOAD_KEYS)
    (a, _k), = rec.calls
    assert a[0] is g5


@pytest.mark.parametrize("owner", [False, object(), 1])
def test_NEGATIVE_a_non_owner_on_luk_reads_none(monkeypatch, owner):
    rec = Rec(ret={"state": "read", "head": "x"})
    monkeypatch.setattr(LT, "_day_read", rec)
    out = LT.build("", now=LTT.NOW, store=LTT.fixture_store(), owner=owner, gg5_store=fake_store())
    assert out["day_read"] is None and rec.calls == []


def test_NEGATIVE_a_raising_luk_helper_serves_none_and_the_board_stands(monkeypatch):
    monkeypatch.setattr(LT, "_day_read", Rec(ret={"state": "read"}))
    good = LT.build("", now=LTT.NOW, store=LTT.fixture_store(), owner=True, gg5_store=fake_store())
    monkeypatch.setattr(LT, "_day_read", Rec(exc=RuntimeError("no doc")))
    bad = LT.build("", now=LTT.NOW, store=LTT.fixture_store(), owner=True, gg5_store=fake_store())
    assert bad["day_read"] is None and bad["fault"] is False
    assert {k: v for k, v in bad.items() if k != "day_read"} == {k: v for k, v in good.items() if k != "day_read"}


def test_the_luk_helper_reads_the_gg5_doc(stub_dr):
    g5 = fake_store()
    assert LT._day_read(g5, S, TAB_NOW) == {"state": "read", "head": "stub"}
    assert stub_dr.load_doc.calls[-1][0] == (g5,)
    assert stub_dr.served_block.calls[-1][0] == ({"the": "doc"}, S, TAB_NOW)


def test_the_live_luk_route_shape_reaches_gs_default(monkeypatch):
    """No store, no gg5_store (the route's call) → GS.default() is the GG5 store handed to the helper."""
    from chart_maps.gajjala import store as GS
    from chart_maps.luk import store as LS
    g5 = fake_store()
    monkeypatch.setattr(GS, "default", lambda: g5)
    monkeypatch.setattr(LS, "default", lambda: LTT.fixture_store())
    rec = Rec(ret={"state": "read"})
    monkeypatch.setattr(LT, "_day_read", rec)
    out = LT.build("", now=LTT.NOW, owner=True)
    assert out["day_read"] == {"state": "read"} and rec.calls[0][0][0] is g5


# ── [C8] the luk route pin (test_luk_api.py:36-54's fixtures, copied) ──────────────────────────────────────────────
DOUG = {"X-User-Email": "doug@example.com"}


@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps import api as API
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app)


@pytest.fixture
def live(monkeypatch):
    from chart_maps import board as board_mod
    snap, attach = Rec(ret={"AAA": {"price": 1.0}}), Rec(ret={})
    monkeypatch.setattr(board_mod, "_live_snapshot", snap)
    monkeypatch.setattr(board_mod, "attach_live_now", attach)
    return snap, attach


def test_C8_the_luk_route_passes_owner_and_no_store(client, monkeypatch, live):
    monkeypatch.setattr("ollama_chat.api.is_primary_admin", lambda e: True)
    build = Rec(ret={"tab": "luk"})
    monkeypatch.setattr(LT, "build", build)
    r = client.get("/chart-maps/luk")
    assert r.status_code == 200
    (_a, k), = build.calls
    assert k["owner"] is True and "store" not in k and "gg5_store" not in k


def test_C8_NEGATIVE_doug_is_not_the_owner(client, monkeypatch, live):
    build = Rec(ret={"tab": "luk"})
    monkeypatch.setattr(LT, "build", build)
    r = client.get("/chart-maps/luk", headers=DOUG)
    assert r.status_code == 200
    (_a, k), = build.calls
    assert k["owner"] is False and "store" not in k and "gg5_store" not in k


def test_C8_source_pin_the_luk_route_body():
    from chart_maps import api as API
    src = inspect.getsource(API.chart_maps_luk)
    assert "owner=owner" in src and "store=" not in src


# ── no gate path, no recorder name, lazy imports ───────────────────────────────────────────────────────────────────
GATE_FILES = ([BACKEND / "chart_maps" / "gajjala" / f"{n}.py" for n in
               ("alerts", "potential", "break_watch", "live_events", "audited_pass", "audited_rules", "ledger")]
              + [BACKEND / "chart_maps" / "luk" / f"{n}.py" for n in ("alerts", "run", "ledger")]
              + [BACKEND / "trading" / "gajjala_entry.py"]
              + sorted((BACKEND / "push").glob("*.py")))


def _imports(tree) -> list:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            out += [f"{n.module or ''}.{a.name}" for a in n.names] + [n.module or ""]
    return out


@pytest.mark.parametrize("path", GATE_FILES, ids=lambda p: str(p.relative_to(BACKEND)))
def test_NEGATIVE_no_gate_push_or_lane_module_imports_or_names_the_day_read(path):
    assert path.exists(), path
    src = path.read_text(encoding="utf-8")
    assert not WORD.search(src) and "shadow_day_tags" not in src
    assert not [i for i in _imports(ast.parse(src)) if "day_read" in i.split(".")]


def test_the_scan_is_not_vacuous():
    assert len(GATE_FILES) >= 12 and all(p.exists() for p in GATE_FILES)
    assert WORD.search(SOURCES["run"].read_text(encoding="utf-8"))  # the regex does find a real mention


@pytest.mark.parametrize("key", sorted(SOURCES))
def test_the_three_wired_files_never_name_the_recorder_and_import_day_read_lazily(key):
    src = SOURCES[key].read_text(encoding="utf-8")
    assert "shadow_day_tags" not in src
    tree = ast.parse(src)
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not [i for i in _imports(ast.Module(body=top, type_ignores=[])) if "day_read" in i.split(".")]
    assert "import day_read as DR" in src                              # the lazy import is there


def test_the_tab_keys_are_served_after_enterable_and_before_the_audit_blocks():
    src = SOURCES["gtab"].read_text(encoding="utf-8")
    i_ent, i_dr = src.index('out["enterable"] = _soft('), src.index('out["day_read"] = (')
    assert i_ent < i_dr < src.index('out["audited"] = _soft(')
    assert 'if (owner is True and not aud) else None' in src
    lsrc = SOURCES["ltab"].read_text(encoding="utf-8")
    assert "if (owner is True and gg5 is not None) else None" in lsrc


# ── REFIX 2026-11-15: the golden drift is the ADDED `day_read` key and nothing else, on all SIX served goldens ──────
# The key moves six goldens (11 tests): gg5_board_2026_10_27.json (test_gajjala_variant_gg5_identity,
# test_gajjala_audited_k3s_track_2026_11_09, test_gajjala_audited_pass ×2, test_gajjala_audited_tab), the 1-minute,
# on_open, potential and track_record FE fixtures (test_gajjala_1m_page_2026_10_27, test_gajjala_on_open,
# test_gajjala_potential_tab + test_gajjala_squeeze_marks_2026_11_08, test_gajjala_track_record_tab) and
# luk_board_golden_2026_11_01.json (test_luk_tab). The dated regen is the main session's, under his word (spec §7 #7);
# this pin holds BEFORE and AFTER that regen: with every `day_read` key dropped from both sides, the served payload
# equals the golden on file — 0 changed, 0 removed leaves. The WRITES golden never moves (the step never runs there).
def _drop_day_read(o):
    if isinstance(o, dict):
        return {k: _drop_day_read(v) for k, v in o.items() if k != "day_read"}
    if isinstance(o, list):
        return [_drop_day_read(v) for v in o]
    return o


def _boards(doc, depth):
    """The served boards of a golden doc: `depth` dict levels below the root (the `_recipe` string skipped)."""
    out = [doc]
    for _ in range(depth):
        out = [v for d in out for k, v in d.items() if isinstance(v, dict)]
    return out


def _golden_gg5(monkeypatch):
    from tests import test_gajjala_variant_gg5_identity as IDT
    stores, _t = IDT.writes_text(monkeypatch)
    return IDT.BOARD, IDT.board_text(stores), 2                         # {mode: {sub: board}}


def _golden_fe(modname):
    def _get(_mp):
        import importlib
        m = importlib.import_module(f"tests.{modname}")
        return m.GOLDEN, m.golden_payload(), 2                          # {"boards": {key: board}}
    return _get


def _golden_luk(_mp):
    return LTT.GOLDEN, LTT._golden_text(), 1                             # {name: board}


GOLDENS = {"gg5_board": _golden_gg5,
           "gajjala_1m": _golden_fe("test_gajjala_1m_page_2026_10_27"),
           "on_open": _golden_fe("test_gajjala_on_open"),
           "potential": _golden_fe("test_gajjala_potential_tab"),
           "track_record": _golden_fe("test_gajjala_track_record_tab"),
           "luk": _golden_luk}


@pytest.mark.parametrize("name", sorted(GOLDENS))
def test_every_golden_moves_only_by_the_added_day_read_key(name, monkeypatch):
    import json
    path, text, depth = GOLDENS[name](monkeypatch)
    old, new = json.loads(path.read_text(encoding="utf-8")), json.loads(text)
    assert _drop_day_read(new) == _drop_day_read(old), f"{path.name} moved beyond the added `day_read` key"
    boards = _boards(new, depth)
    assert boards and all("day_read" in b for b in boards), name        # the key is on EVERY served board
    if name == "luk":
        assert all(b["day_read"] is None for b in boards)               # the golden injects `store=` and no gg5_store
    else:
        assert all(b["day_read"] is None or b["day_read"]["state"] == "absent" for b in boards)   # no state doc


def test_NEGATIVE_the_golden_drift_pin_catches_a_foreign_leaf(monkeypatch):
    import json
    path, text, _d = _golden_luk(monkeypatch)
    old, new = json.loads(path.read_text(encoding="utf-8")), json.loads(text)
    new["default"]["day_read"] = {"state": "read"}                      # a day_read change alone still passes
    assert _drop_day_read(new) == _drop_day_read(old)
    new["default"]["sub"] = "not-the-sub"                               # any other leaf moving fails the pin
    assert _drop_day_read(new) != _drop_day_read(old)
    assert _drop_day_read({"a": [{"day_read": 1, "b": 2}]}) == {"a": [{"b": 2}]}


def test_NEGATIVE_the_writes_golden_is_untouched_by_the_day_read(monkeypatch):
    from tests import test_gajjala_variant_gg5_identity as IDT
    _stores, text = IDT.writes_text(monkeypatch)
    assert IDT.WRITES.read_text(encoding="utf-8") == text
    assert "day_read" not in text
