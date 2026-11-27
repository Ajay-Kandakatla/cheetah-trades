"""📶 The base count in the passes — run.py (GG5) and run_1m.py (GG1) store `run_bases` on the read doc (spec ggbase §3.3
/ WP-A steps 3–4, 2026-11-15).

Ajay, verbatim: "I need that tracked in to Gajjala's". The block is STORED only: never in ctx (the 🧠 tracker copies it),
never in alert_ctx, never a gate. A failing count never breaks a pass — the read doc is written without the key.
"""
from __future__ import annotations

import logging

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import run_bases as RB
from tests import test_gajjala_run_1m_2026_10_27 as T1M
from tests.test_gajjala_run import NOW, PREV, PRIOR_1M, S, at, make_deps, minutes_from_5m, snap_row
from tests.test_gajjala_run_bases_2026_11_15 import THREE, build
from tests.test_gajjala_store import fake_store


@pytest.fixture(autouse=True, scope="module")
def gg1_on():
    """2026-11-18 — the page retired (GC.GAJJALA_1M_ENABLED False, Ajay: "This is good info stop 1 min tab it was a good
    experiment"); this module pins how it RAN 2026-10-27 … 2026-11-17 and how it runs again if the word flips back.
    Module scope so the module-scoped fixture day is built ON too; a test that sets the switch False still can."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(GC, "GAJJALA_1M_ENABLED", True)
        yield


GG5_KEYS = {"as_of_bar_t5", "as_of_bar_t15", "setups", "ctx", "tile", "listed", "stopped_today", "date", "symbol",
            "updated_at", "at"}
# 🧘 2026-11-27 (spec gg-like §3.6 / §3.8, suite refix): the pass also stores `gg_like` on a read doc when a setup was
# judged — a sibling ADDED key of its own, pinned in tests/test_gajjala_gg_like_suite_2026_11_27.py. The 📶 pins below
# compare the doc's keys with it set aside; it is never in ctx either way.
GL_KEY = "gg_like"


def _keys(doc) -> set:
    return set(doc) - {"_id", GL_KEY}


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: True)


def _reads(st):
    return {d["symbol"]: d for d in st.reads(S)}


# ── GG5 ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_every_gg5_read_doc_carries_the_block_of_its_5m_frame():
    st = fake_store()
    out = RUN.run_pass(NOW, store=st, deps=make_deps()[0])
    assert out["errors"] == []
    docs = _reads(st)
    assert docs
    for sym, doc in docs.items():
        blk = doc["run_bases"]
        assert _keys(doc) == GG5_KEYS | {"run_bases"}, sym
        assert blk["version"] == RB.VERSION and blk["frame"] == GC.RUN_BASE_FRAME
        assert blk["as_of_bar_t"] == doc["as_of_bar_t5"]
        assert "run_bases" not in doc["ctx"]                           # NEGATIVE: never in ctx (🧠 copies it)


def test_a_three_base_day_is_stored_and_served_through_the_pass():
    bars, _st = build(THREE)
    today = minutes_from_5m(bars, S, "09:30")                         # labels 09:35 … 11:55

    def load(sym, day):
        return PRIOR_1M.copy() if day == PREV else today.copy()
    now = at(11, 56)
    rows = {"GGA": snap_row(13.0, 8.0, when=at(11, 55))}
    st = fake_store()
    RUN.run_pass(now, store=st, deps=make_deps(rows=rows, load=load)[0])
    blk = st.get_read(S, "GGA")["run_bases"]
    assert (blk["n"], blk["forming"], blk["state"]) == (2, True, RB.FORMING)
    assert RB.card_block(blk)["text"].startswith("📶 3rd base — climax run, GG peels early · forming since 11:20 ET")


def test_NEGATIVE_nothing_enters_alert_ctx(monkeypatch):
    seen = {}
    real = AL.run_pass

    def spy(reads, frames, now, session, **kw):
        seen.update(kw.get("ctx") or {})
        return real(reads, frames, now, session, **kw)
    monkeypatch.setattr(AL, "run_pass", spy)
    RUN.run_pass(NOW, store=fake_store(), deps=make_deps()[0])
    assert seen and not [k for c in seen.values() for k in c if "base" in k]


def test_NEGATIVE_a_raising_count_still_writes_every_read_doc_without_the_key(monkeypatch, caplog):
    monkeypatch.setattr(RB, "count", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    st = fake_store()
    with caplog.at_level(logging.WARNING, logger="chart_maps.gajjala.run"):
        out = RUN.run_pass(NOW, store=st, deps=make_deps(rows={"GGA": snap_row(11.2, 8.0),
                                                                "GGB": snap_row(11.0, 8.0)})[0])
    assert out["errors"] == [] and out["status"] == "ok"
    docs = _reads(st)
    assert len(docs) == 2
    for doc in docs.values():
        assert _keys(doc) == GG5_KEYS
    assert len([r for r in caplog.records if "base count failed" in r.getMessage()]) == 1     # once per pass


def test_NEGATIVE_a_none_count_adds_no_key(monkeypatch):
    monkeypatch.setattr(RB, "count", lambda *a, **k: None)
    st = fake_store()
    RUN.run_pass(NOW, store=st, deps=make_deps()[0])
    assert all(_keys(d) == GG5_KEYS for d in _reads(st).values())


def test_NEGATIVE_the_pass_summary_is_byte_equal_with_and_without_the_count(monkeypatch):
    a = RUN.run_pass(NOW, store=fake_store(), deps=make_deps()[0])
    monkeypatch.setattr(RB, "count", lambda *a, **k: None)
    b = RUN.run_pass(NOW, store=fake_store(), deps=make_deps()[0])
    assert a == b


# ── GG1 ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_gg1_read_doc_counts_on_its_5m_frame(monkeypatch):
    calls = []
    real = RB.count

    def spy(F, **kw):
        calls.append(getattr(F, "frame", None))
        return real(F, **kw)
    monkeypatch.setattr(RB, "count", spy)
    db, _shared, st = T1M.world(monkeypatch)
    T1M.R1.run_iteration(T1M.NOW, store=st, deps=T1M.deps())
    doc = db["gajjala_1m_reads"].docs["2026-10-13|GGA"]
    assert doc["run_bases"]["frame"] == "5m" and doc["run_bases"]["as_of_bar_t"] == doc["as_of_bar_t5"]
    assert calls and set(calls) == {"5m"}                              # never the 1-minute frame (HIS CALL #2)
    assert "run_bases" not in doc["ctx"]


def test_NEGATIVE_gg1_raising_count_writes_the_doc_without_the_key(monkeypatch):
    monkeypatch.setattr(RB, "count", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    db, _shared, st = T1M.world(monkeypatch)
    out = T1M.R1.run_iteration(T1M.NOW, store=st, deps=T1M.deps())
    assert out["errors"] == []
    doc = db["gajjala_1m_reads"].docs["2026-10-13|GGA"]
    assert "run_bases" not in doc and doc["setups"]
