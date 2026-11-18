"""📶 The base count stamped AT the entry bar — run_bases.claim_fields, alerts.run_pass (claims, refusals, shadow) and the
🧪 held record (spec ggbase §3.1 claim_fields / §3.3 / WP-A steps 5–6, 2026-11-15; C1.5, C2.5, C2.8).

Ajay, verbatim: "I need that tracked in to Gajjala's". The stamp is information for the 🏁 record and a later study only:
never in ctx, never read by `compose` (the push bytes are identical), never a gate.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import audited_rules as AUD
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import run_bases as RB
from chart_maps.gajjala import variant as V
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_alerts import Spy, at, read, stamp
from tests.test_gajjala_audited_pass import _audit, _forced, _hermetic, _scenario_one_pass   # noqa: F401 (autouse)
from tests.test_gajjala_run import NOW as RUN_NOW
from tests.test_gajjala_run import S, make_deps
from tests.test_gajjala_run_bases_2026_11_15 import THREE, frame_of
from tests.test_gajjala_store import fake_store


@pytest.fixture(autouse=True, scope="module")
def gg1_on():
    """2026-11-18 — the page retired (GC.GAJJALA_1M_ENABLED False, Ajay: "This is good info stop 1 min tab it was a good
    experiment"); this module pins how it RAN 2026-10-27 … 2026-11-17 and how it runs again if the word flips back.
    Module scope so the module-scoped fixture day is built ON too; a test that sets the switch False still can."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(GC, "GAJJALA_1M_ENABLED", True)
        yield


# THREE from 09:35: leg 09:50–09:55 · base 1 10:00–10:25 · break 10:30 · base 2 10:40–11:05 · break 11:10 ·
# base 3 forming 11:20–11:45
BREAK_2 = stamp(11, 10)
IN_PAUSE_6 = stamp(11, 45)


@pytest.fixture(scope="module")
def F():
    return frame_of(THREE)[0]


def _frames(F, as_of=None):
    """A bars.Frames-shaped namespace: `.by` (the counting frame) + `as_of_bar_t` (the refusal clock)."""
    t = as_of or F.t[-1]
    return SimpleNamespace(by={"5m": F}, as_of_bar_t={"5m": t, "15m": t})


# ── claim_fields ────────────────────────────────────────────────────────────────────────────────────────────────
def test_entry_at_the_break_of_base_two_with_a_later_pause_open(F):
    """C1.5 case 1: the pass reads bars past the entry (base 3 forming) — the stamp is still the count AT the entry."""
    assert RB.count(F)["forming"] is True
    assert RB.claim_fields(_frames(F), BREAK_2) == {"run_base_n": 2, "run_base_forming": False}


def test_entry_bar_inside_a_pause_after_base_two(F):
    """C1.5 case 2: the entry bar is the 6th bar of the pause after base 2 → 2 broke + the 3rd forming."""
    assert RB.claim_fields(_frames(F), IN_PAUSE_6) == {"run_base_n": 2, "run_base_forming": True}


def test_a_15m_stamp_and_a_1m_stamp_read_the_last_closed_5m_bar(F):
    assert RB.claim_fields({"5m": F}, stamp(11, 15)) == {"run_base_n": 2, "run_base_forming": False}   # 15m label
    assert RB.claim_fields({"5m": F}, stamp(11, 12)) == RB.claim_fields({"5m": F}, BREAK_2)              # 1m label
    assert RB.claim_fields({"5m": F}, stamp(10, 32)) == {"run_base_n": 1, "run_base_forming": False}


@pytest.mark.parametrize("frames,entry", [(None, BREAK_2), ("F", None), ("F", 1234), ("F", ""),
                                          ("F", "2026-10-12 09:00"), ({"15m": None}, BREAK_2),
                                          (SimpleNamespace(as_of_bar_t={"5m": BREAK_2}), BREAK_2)])
def test_NEGATIVE_claim_fields_unknown_is_empty(F, frames, entry):
    fr = {"5m": F} if frames == "F" else frames
    if entry == "2026-10-12 09:00":                                   # before the frame's first (prior-session) bar
        assert F.t[0] > entry
    assert RB.claim_fields(fr, entry) == {}


def test_NEGATIVE_claim_fields_never_raises_when_the_count_raises(F, monkeypatch):
    monkeypatch.setattr(RB, "_count", lambda *a, **k: 1 / 0)
    assert RB.claim_fields({"5m": F}, BREAK_2) == {}


# ── alerts.run_pass — the claim body ────────────────────────────────────────────────────────────────────────────
def _one(store, r, frames, *, now, dry=False, mode=None):
    send = Spy()
    counts = AL.run_pass({"GGA": {r["setup"]: r}}, {"GGA": frames}, now, S, store=store, send=send,
                         owner="owner@example.com", dry=dry, ctx={"GGA": {"price": 11.2}}, mode=mode)
    return counts, send


def test_the_live_claim_carries_the_count_at_its_entry_bar(F, monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    st = fake_store()
    counts, send = _one(st, read(entry=BREAK_2), _frames(F, as_of=BREAK_2), now=at(11, 11))
    assert counts["pushed"] == 1
    doc = st.alerts_coll().docs["GG:2026-10-13|GGA|bull_flag"]
    assert (doc["run_base_n"], doc["run_base_forming"]) == (2, False)


def test_the_shadow_claim_carries_the_count(F, monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "shadow")
    st = fake_store()
    counts, _s = _one(st, read(entry=IN_PAUSE_6), _frames(F, as_of=IN_PAUSE_6), now=at(11, 46))
    assert counts["shadow"] == 1
    doc = st.alerts_coll().docs["SHADOW:GG:2026-10-13|GGA|bull_flag"]
    assert (doc["run_base_n"], doc["run_base_forming"]) == (2, True)


def test_a_late_refusal_record_carries_the_count_at_the_entry_not_at_the_pass(F, monkeypatch):
    """C2.5: a claim judged bars after its entry stamps the count AT the entry bar."""
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    st = fake_store()
    counts, send = _one(st, read(entry=BREAK_2), _frames(F), now=at(11, 46))
    assert counts["late"] == 1 and send.calls == []
    doc = st.alerts_coll().docs["GG:2026-10-13|GGA|bull_flag#late"]
    assert (doc["run_base_n"], doc["run_base_forming"]) == (2, False)


def test_NEGATIVE_without_a_counting_frame_the_claim_body_is_byte_equal_to_today(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    st = fake_store()
    _one(st, read(), SimpleNamespace(as_of_bar_t={"5m": stamp(10, 5), "15m": stamp(10, 5)}), now=at(10, 6))
    doc = st.alerts_coll().docs["GG:2026-10-13|GGA|bull_flag"]
    assert "run_base_n" not in doc and "run_base_forming" not in doc


def test_NEGATIVE_rb_raising_leaves_the_claim_body_as_today_and_the_pass_rings(F, monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    monkeypatch.setattr(RB, "claim_fields", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    st = fake_store()
    counts, send = _one(st, read(entry=BREAK_2), _frames(F, as_of=BREAK_2), now=at(11, 11))
    assert counts["pushed"] == 1 and len(send.calls) == 1
    doc = st.alerts_coll().docs["GG:2026-10-13|GGA|bull_flag"]
    assert "run_base_n" not in doc and "run_base_forming" not in doc


def test_NEGATIVE_the_push_payload_is_byte_identical_with_and_without_the_stamp(F, monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    _c1, with_stamp = _one(fake_store(), read(entry=BREAK_2), _frames(F, as_of=BREAK_2), now=at(11, 11))
    bare = SimpleNamespace(as_of_bar_t={"5m": BREAK_2, "15m": BREAK_2})
    _c2, without = _one(fake_store(), read(entry=BREAK_2), bare, now=at(11, 11))
    assert with_stamp.calls == without.calls and with_stamp.calls
    blob = repr(with_stamp.calls)
    assert "run_base" not in blob and "📶" not in blob


def test_NEGATIVE_compose_never_reads_the_stamp(F):
    r = read(entry=BREAK_2)
    a = AL.compose(r, "GGA", {"price": 11.2}, session=S)
    b = AL.compose(r, "GGA", {"price": 11.2, "run_base_n": 3, "run_base_forming": True}, session=S)
    assert a == b


# ── end to end: GG5, GG1, GGA ───────────────────────────────────────────────────────────────────────────────────
def test_gg5_pass_claim_carries_both_keys(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    st = fake_store()
    RUN.run_pass(RUN_NOW, store=st, deps=make_deps()[0])
    docs = st.alerts_coll().docs
    claim = docs["GG:2026-10-13|GGA|bull_flag"]
    assert isinstance(claim["run_base_n"], int) and not isinstance(claim["run_base_n"], bool)
    assert isinstance(claim["run_base_forming"], bool)
    assert "run_base_n" not in (st.get_read(S, "GGA") or {}).get("ctx", {})            # NEGATIVE: never in ctx


def test_gg1_iteration_claim_carries_both_keys(monkeypatch):
    from tests import test_gajjala_run_1m_2026_10_27 as T1M
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "shadow")
    monkeypatch.setattr(T1M.R1, "_popen", lambda *a, **k: pytest.fail("spawn"))
    db, _shared, st = T1M.world(monkeypatch)
    T1M.R1.run_iteration(T1M.NOW, store=st, deps=T1M.deps())
    claim = db["gajjala_1m_alerts"].docs["SHADOW:GG1:2026-10-13|GGA|bull_flag"]
    assert claim["run_base_n"] == 0 and claim["run_base_forming"] is False


def test_gga_shadow_claim_carries_both_keys(monkeypatch):
    _st, gga, _d, _o = _scenario_one_pass(monkeypatch, judge=_forced(AUD.judge))
    key = f"SHADOW:{AL.claim_key(S, 'GGA', 'bull_flag', V.GGA)}"
    claim = gga.alerts_coll().docs[key]
    assert claim["run_base_n"] == 0 and claim["run_base_forming"] is False


def test_gga_held_record_carries_both_keys(monkeypatch):
    _st, gga, _d, _o = _scenario_one_pass(monkeypatch, judge=lambda r, F, fz=None, **kw: _audit(False, F.frame))
    held = gga.alerts_coll().docs[f"{AL.claim_key(S, 'GGA', 'bull_flag', V.GGA)}#{AUD.HELD_ROW_STATE}"]
    assert held["run_base_n"] == 0 and held["run_base_forming"] is False
    assert held["state"] == AUD.HELD_ROW_STATE and held["entry_bar_t"] == "2026-10-13 10:40"


def test_NEGATIVE_gga_held_record_without_the_engine_is_today(monkeypatch):
    monkeypatch.setattr(RB, "claim_fields", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    _st, gga, _d, _o = _scenario_one_pass(monkeypatch, judge=lambda r, F, fz=None, **kw: _audit(False, F.frame))
    held = gga.alerts_coll().docs[f"{AL.claim_key(S, 'GGA', 'bull_flag', V.GGA)}#{AUD.HELD_ROW_STATE}"]
    assert "run_base_n" not in held and "run_base_forming" not in held

