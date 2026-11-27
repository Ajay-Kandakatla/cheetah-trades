"""🧘 GG-like calm check — the suite refix pins (spec gg-like 2026-11-27 §3.6 / §5, package `suite`).

Ajay, verbatim (2026-11-27): "find calmer and better setups.. I want to make sure we are finding similar setups to
Gajjala".

Three older pins moved because the spec wires the 🧘 block into the pass and the two rings:
  * the push-path source pins (test_gajjala_pot_all_2026_11_24, test_gajjala_si_ssr_potential_2026_11_24) — this file
    proves the new `alerts.run_pass` / `potential.run_pass` are the OLD bytes plus the gg_like lines only: undoing
    exactly those lines reproduces the old sha256 values;
  * the 📶 read-doc key pins (test_gajjala_run_bases_pass_2026_11_15) — this file pins the sibling `gg_like` key: it is
    gg_like.doc_blocks of the doc the pass stored, absent when nothing is judged or the check faults, never in ctx;
  * the Watch hook list (test_gajjala_watch_hook_2026_11_15) — pinned there by its own NEGATIVE.
"""
from __future__ import annotations

import hashlib
import inspect
import logging
import re

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import gg_like as GL
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from tests.test_gajjala_run import NOW, S, make_deps, snap_row
from tests.test_gajjala_store import fake_store

# sha256(inspect.getsource) BEFORE the gg-like build (base 6a67007f — the values the two pins held until 2026-11-27)
OLD_SHA = {"alerts.run_pass": "d2ded91a11f4fecd41deb023adb6ca4104ba9fcebbea8c808ebb8fff9acbc778",
           "potential.run_pass": "629c24a61435d57743a7be44ed6f30ad15adde584b3d674ae9d99397354f49a0"}
FNS = {"alerts.run_pass": AL.run_pass, "potential.run_pass": PT.run_pass}

_SIG = (", gg_like: Optional[dict] = None) -> dict:", ") -> dict:")
_CLAIM = (", **_gl_claim(gg_like, sym, setup, r)})", "})")
_DOC = re.compile(r"\n    🧘 2026-11-27: `gg_like` = .*?(?=\"\"\")", re.S)
_FIELDS = re.compile(r"\n[ ]+base\.update\(_gl_fields\(gg_like, sym, setup, entry_t\)\)[^\n]*")


def _sha(src: str) -> str:
    return hashlib.sha256(src.encode()).hexdigest()


def undo_gg_like(src: str) -> str:
    """The source with exactly the 🧘 additions taken out: the kwarg, its docstring paragraph, the A+ `_gl_fields`
    line, the 🧠 `_gl_claim` spread. Each piece must be there ONCE (the kwarg and the paragraph in both functions)."""
    assert src.count(_SIG[0]) == 1, "the gg_like kwarg"
    src = src.replace(*_SIG)
    if _CLAIM[0] in src:
        assert src.count(_CLAIM[0]) == 1
        src = src.replace(*_CLAIM)
    src, n = _DOC.subn("", src)
    assert n == 1, "the 🧘 docstring paragraph"
    src, n = _FIELDS.subn("", src)
    assert n <= 1
    return src


# ── the push path moved by the gg_like lines ONLY ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", sorted(FNS))
def test_run_pass_is_the_old_bytes_plus_the_gg_like_lines_only(name):
    src = inspect.getsource(FNS[name])
    assert _sha(src) != OLD_SHA[name]                                   # the function did change …
    assert _sha(undo_gg_like(src)) == OLD_SHA[name]                     # … and by the 🧘 lines alone


@pytest.mark.parametrize("name", sorted(FNS))
def test_the_kwarg_defaults_to_none_so_the_1m_page_and_the_audited_pass_move_nothing(name):
    p = inspect.signature(FNS[name]).parameters["gg_like"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is None


@pytest.mark.parametrize("name", sorted(FNS))
def test_NEGATIVE_any_other_byte_moved_fails_the_undo_pin(name):
    src = inspect.getsource(FNS[name])
    head, tail = src.rsplit("return counts", 1)
    tampered = head + "return  counts" + tail                           # one byte outside the 🧘 lines
    assert tampered != src
    assert _sha(undo_gg_like(tampered)) != OLD_SHA[name]


def test_NEGATIVE_the_undo_refuses_a_source_without_the_gg_like_lines():
    with pytest.raises(AssertionError):
        undo_gg_like(undo_gg_like(inspect.getsource(AL.run_pass)))


def test_NEGATIVE_the_a_plus_line_is_only_in_alerts_and_the_claim_spread_only_in_potential():
    a, p = inspect.getsource(AL.run_pass), inspect.getsource(PT.run_pass)
    assert len(_FIELDS.findall(a)) == 1 and _CLAIM[0] not in a
    assert not _FIELDS.findall(p) and p.count(_CLAIM[0]) == 1


# ── the read doc's sibling `gg_like` key ─────────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: True)


def _reads(st):
    return {d["symbol"]: d for d in st.reads(S)}


def test_the_pass_stores_gg_like_equal_to_doc_blocks_of_the_doc_it_stored():
    st = fake_store()
    out = RUN.run_pass(NOW, store=st, deps=make_deps()[0])
    assert out["errors"] == [] and out["status"] == "ok"
    docs = _reads(st)
    judged = [s for s, d in docs.items() if "gg_like" in d]
    assert judged                                                       # the fixture day judges a setup
    for sym, doc in docs.items():
        base = {k: v for k, v in doc.items() if k != "gg_like"}
        want = GL.doc_blocks(base)
        assert doc.get("gg_like", {}) == want, sym                       # the engine's own block, nothing retyped
        assert set(doc.get("gg_like", {})) <= set(GC.SETUPS), sym
        assert "gg_like" not in (doc.get("ctx") or {}), sym             # NEGATIVE: never in ctx (🧠 copies ctx)


def test_NEGATIVE_nothing_judged_adds_no_key(monkeypatch):
    monkeypatch.setattr(GL, "doc_blocks", lambda doc: {})
    st = fake_store()
    RUN.run_pass(NOW, store=st, deps=make_deps()[0])
    docs = _reads(st)
    assert docs and all("gg_like" not in d for d in docs.values())


def test_NEGATIVE_a_raising_check_writes_every_read_doc_without_the_key_and_logs_once(monkeypatch, caplog):
    monkeypatch.setattr(GL, "doc_blocks", lambda doc: (_ for _ in ()).throw(RuntimeError("x")))
    st = fake_store()
    with caplog.at_level(logging.WARNING, logger="chart_maps.gajjala.run"):
        out = RUN.run_pass(NOW, store=st, deps=make_deps(rows={"GGA": snap_row(11.2, 8.0),
                                                                "GGB": snap_row(11.0, 8.0)})[0])
    assert out["errors"] == [] and out["status"] == "ok"
    docs = _reads(st)
    assert len(docs) == 2 and all("gg_like" not in d for d in docs.values())
    assert len([r for r in caplog.records if "gg like check failed" in r.getMessage()]) == 1   # once per pass


def test_NEGATIVE_the_pass_summary_is_byte_equal_with_and_without_the_check(monkeypatch):
    a = RUN.run_pass(NOW, store=fake_store(), deps=make_deps()[0])
    monkeypatch.setattr(GL, "doc_blocks", lambda doc: {})
    b = RUN.run_pass(NOW, store=fake_store(), deps=make_deps()[0])
    assert a == b
