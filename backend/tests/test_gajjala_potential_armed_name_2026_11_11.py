"""🧠 proposals #1 / #2 + the ⚡ tracker contract (entry spec 2026-11-11 §3.3, §3.4, §3.10 — WP-POT).

Ajay 2026-11-11: "Also apply your proposal too." — the proposals table of
eod-audits/research/2026-11-11_entries_followthrough.md: #1 a 🧠 rings only when ARMED (a doc first seen building rings
once when it arms; GC.POTENTIAL_PUSH_ARMED_ONLY), #2 one 🧠 ring per name per day (GC.POTENTIAL_ONE_RING_PER_NAME).
The ⚡ break watch reads `last.session_volume` (GG5 only) and — only while a suppression switch is ON —
`last.halt_resume_et` / `last.reg_gain_pct`.

P1–P11 of the spec §5.2; NEGATIVES are mandatory (P2, P4–P6, P8, P9, P11 and the eligible() table).
"""
from __future__ import annotations

import copy
import json
import re
from datetime import timedelta

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import variant as V
from tests.test_gajjala_potential import (LABOR_DAY, OK_SEND, S, Rec, at, bf_armed, ctx_for, doc_of, frame_at, go,
                                          one_per_setup, seed)
from tests.test_gajjala_store import fake_store
from tests.test_gajjala_variant_2026_10_27 import frame_1m, gg1_store


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def bf_building():
    """The SAME bull flag read with the trigger not armed yet (ready False) → kind "building", same doc id."""
    r = copy.deepcopy(bf_armed())
    r["ready"] = False
    assert PT.potential_kind(r) == "building"
    return r


def rs_armed():
    r = one_per_setup()["reversal_squeeze"]
    assert PT.potential_kind(r) == "armed"
    return r


def held(st, sym="AAA", setup="bull_flag", d=S):
    return [h["reason"] for h in (doc_of(st, sym, setup, d).get("held") or [])]


# ── P1 — building holds, the arm rings once ──────────────────────────────────────────────────────────────────────
def test_P1_a_building_first_sighting_is_held_and_rings_once_when_it_arms():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_building()}}, send=send)
    assert out["building_held"] == 1 and out["pushed"] == 0 and send.calls == []
    assert held(st) == ["building"] and "push" not in doc_of(st)
    out = go(st, at(10, 11), {"AAA": {"bull_flag": bf_building()}}, send=send)    # still building: held again
    assert out["building_held"] == 1 and send.calls == [] and held(st) == ["building"]   # _hold idempotent
    out = go(st, at(10, 16), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert out["pushed"] == 1 and len(send.calls) == 1 and out["building_held"] == 0
    assert doc_of(st)["push"]["kind_at_push"] == "armed"
    out = go(st, at(10, 21), {"AAA": {"bull_flag": bf_armed()}}, send=send)       # NEGATIVE: never twice
    assert out["pushed"] == 0 and len(send.calls) == 1


def test_P1_an_armed_first_sighting_still_rings_at_once():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert out["pushed"] == 1 and out["building_held"] == 0 and out["name_held"] == 0


# ── P2 — a joined doc never rings ────────────────────────────────────────────────────────────────────────────────
def test_P2_NEGATIVE_a_joined_building_doc_never_rings_when_it_arms():
    st = fake_store()                                   # no seed: the 10:06 pass is a JOIN pass (D9)
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_building()}}, send=send)
    assert out["joined"] == 1 and out["building_held"] == 0
    out = go(st, at(10, 11), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert send.calls == [] and out["pushed"] == 0 and "push" not in doc_of(st)


# ── P3 — the D3 continuity rule still decides a muted first sighting ─────────────────────────────────────────────
def test_P3_a_muted_building_sighting_rings_when_it_arms_on_an_unbroken_path():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    out = go(st, at(9, 40), {"AAA": {"bull_flag": bf_building()}}, send=send)
    assert out["muted"] == 1 and out["building_held"] == 0 and held(st) == ["muted"]
    out = go(st, at(9, 50), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert out["pushed"] == 1 and len(send.calls) == 1


def test_P3_a_muted_doc_still_building_after_the_mute_is_held_building_then_rings_armed():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    go(st, at(9, 40), {"AAA": {"bull_flag": bf_building()}}, send=send)
    out = go(st, at(9, 50), {"AAA": {"bull_flag": bf_building()}}, send=send)
    assert out["building_held"] == 1 and held(st) == ["muted", "building"] and send.calls == []
    out = go(st, at(9, 55), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert out["pushed"] == 1 and len(send.calls) == 1


def test_P3_NEGATIVE_a_broken_path_after_a_muted_sighting_never_rings():
    assert GC.POTENTIAL_DEFER_REFUSED is True
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    go(st, at(9, 40), {"AAA": {"bull_flag": bf_building()}}, send=send)
    partial = dict(bf_armed(), state="partial")
    assert PT.potential_kind(partial) is None
    go(st, at(9, 45), {"AAA": {"bull_flag": partial}}, send=send)                 # the path breaks
    out = go(st, at(9, 50), {"AAA": {"bull_flag": bf_armed()}}, send=send)
    assert send.calls == [] and out["pushed"] == 0 and "push" not in doc_of(st)  # "muted" is still a reason → D3


# ── P4 / P5 — one ring per name ──────────────────────────────────────────────────────────────────────────────────
def test_P4_two_armed_setups_of_one_name_ring_once_the_first_in_order_key_order():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {"AAA": {"reversal_squeeze": rs_armed(), "bull_flag": bf_armed()}}, send=send)
    first, second = sorted(("bull_flag", "reversal_squeeze"), key=GC.SETUPS.index)
    assert out["pushed"] == 1 and out["name_held"] == 1 and len(send.calls) == 1
    assert "push" in doc_of(st, setup=first) and held(st, setup=second) == ["name_rang"]
    assert send.calls[0][0][1]["tag"].endswith(f"{first}-AAA")
    # NEGATIVE: the next pass keeps the second held (final for the day) while another name rings normally
    out = go(st, at(10, 11), {"AAA": {"reversal_squeeze": rs_armed(), "bull_flag": bf_armed()},
                              "BBB": {"bull_flag": bf_armed()}}, send=send)
    assert out["pushed"] == 1 and [c[0][1]["ticker"] for c in send.calls] == ["AAA", "BBB"]
    assert "push" not in doc_of(st, setup=second) and held(st, setup=second) == ["name_rang"]


def test_P5_NEGATIVE_a_failed_push_consumes_the_name():
    st = fake_store()
    seed(st)
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_armed()}}, send=Rec(RuntimeError("push service down")))
    assert out["failed"] == 1 and doc_of(st)["push"]["state"] == "failed"
    send = Rec(OK_SEND)
    out = go(st, at(10, 11), {"AAA": {"bull_flag": bf_armed(), "reversal_squeeze": rs_armed()}}, send=send)
    assert send.calls == [] and out["name_held"] == 1 and held(st, setup="reversal_squeeze") == ["name_rang"]


def test_P5_NEGATIVE_a_shadow_push_consumes_the_name_on_the_1_minute_page(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "shadow")
    st, _ = gg1_store()
    seed(st)
    now = at(10, 6)
    reads = {"BBB": {"bull_flag": bf_armed(), "reversal_squeeze": rs_armed()}}
    out = PT.run_pass(reads, {"BBB": frame_1m(now)}, now, S, store=st, ctx={"BBB": ctx_for()},
                      rows={"BBB": {"volume": 2_000_000}}, send=Rec(AssertionError("sent")), owner="o@x", tape="rth")
    assert out["shadow"] == 1 and out["name_held"] == 1


# ── P6 — both switches off = the pre-2026-11-11 gate ─────────────────────────────────────────────────────────────
def test_P6_NEGATIVE_switches_off_ring_building_and_every_setup_of_a_name(monkeypatch):
    monkeypatch.setattr(GC, "POTENTIAL_PUSH_ARMED_ONLY", False)
    monkeypatch.setattr(GC, "POTENTIAL_ONE_RING_PER_NAME", False)
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {"AAA": {"bull_flag": bf_building(), "reversal_squeeze": rs_armed()}}, send=send)
    assert out["pushed"] == 2 and out["building_held"] == 0 and out["name_held"] == 0 and len(send.calls) == 2
    assert doc_of(st)["push"]["kind_at_push"] == "building"
    for setup in ("bull_flag", "reversal_squeeze"):
        assert not (set(held(st, setup=setup)) & {"building", "name_rang"})


def _strip_new(o):
    """Drop the two 2026-11-11 count keys and `last.session_volume` (the ⚡ contract) — what remains must be today's."""
    if isinstance(o, dict):
        out = {k: _strip_new(v) for k, v in o.items() if k not in ("building_held", "name_held")}
        if isinstance(out.get("last"), dict):
            out["last"] = {k: v for k, v in out["last"].items() if k != "session_volume"}
        return out
    if isinstance(o, list):
        return [_strip_new(v) for v in o]
    return o


def test_P6_NEGATIVE_switches_off_the_gg5_run_fixture_writes_equal_todays(monkeypatch):
    """The GG5 WRITES golden (two real run.run_pass, LIVE and SHADOW) with both switches OFF: every write equal to the
    pre-2026-11-11 golden once the two new count keys and `last.session_volume` are dropped. After the main session's
    dated regen (the golden then carries the switched-ON behaviour) this byte check has nothing to compare against."""
    from tests.test_gajjala_variant_gg5_identity import WRITES, writes_text
    golden = WRITES.read_text(encoding="utf-8")
    if '"building_held"' in golden:
        pytest.skip("the WRITES golden was regenerated with proposals #1 / #2 ON (entry spec §6)")
    monkeypatch.setattr(GC, "POTENTIAL_PUSH_ARMED_ONLY", False)
    monkeypatch.setattr(GC, "POTENTIAL_ONE_RING_PER_NAME", False)
    _stores, text = writes_text(monkeypatch)
    ran = json.loads(text)
    assert '"session_volume"' in text and '"building_held"' in text            # the strip below has work to do
    assert _strip_new(ran) == _strip_new(json.loads(golden))


# ── P7 — the words ───────────────────────────────────────────────────────────────────────────────────────────────
def test_P7_the_words_say_armed_and_one_push_per_name():
    gg5 = PT.push_note(S)
    assert gg5.startswith("🧠 Potentials ring your phone live — the first time it is armed (every rule met, only the "
                          "break missing) — one push per name and session, 04:00–20:00 ET")
    b = PT.rules_lines()[1]
    assert "the first time it is armed (every rule met, only the break missing) — one push per name and session" in b
    g1 = PT.push_note(S, V.GG1)
    assert "armed" in g1 and "one push per name and session" in g1
    for t in (gg5, b, g1):
        assert "first time it is a potential" not in t and "name, setup and session" not in t
        assert "b" + "ounc" not in t.lower() and "SHADOW" not in t
    assert PT.HELD_WORDS["building"] == "building — rings once when the trigger arms"
    assert PT.HELD_WORDS["name_rang"] == "this name already rang today — one 🧠 ring per name"
    assert PT.held_words(V.GG1)["building"] == PT.HELD_WORDS["building"]


def test_P7_NEGATIVE_the_shadow_sentence_says_the_built_rule_and_switches_off_restore_the_old_words(monkeypatch):
    # MOVED 2026-11-11 (T-PINS #5): the shadow sentence said "one per name, setup and session the first time it is a
    # potential" — not the built rule. It now says ring_rule()'s words (both switches on), "push" dropped: shadow.
    shadow = V.WORDS_1M_SHADOW["push_potential"]
    assert shadow == (
        "🧠 Potentials on this page are recorded in shadow — the first time it is armed (every rule met, only the "
        "break missing) — one per name and session, {open}–{close} ET on the {cad}-minute pass, never "
        "{rth_open}–{mute_end} (his first {n} minutes). Never sent until you say so. {tail}.")
    assert PT.ring_rule().replace("one push per", "one per") in shadow          # the ring rule's own words
    assert "first time it is a potential" not in shadow and "name, setup and session" not in shadow
    assert "ring your phone" not in shadow and "push" not in shadow             # NEGATIVE: shadow never says sent
    assert not re.search(r"\d", shadow)                                        # types no number
    monkeypatch.setattr(GC, "POTENTIAL_PUSH_ARMED_ONLY", False)
    monkeypatch.setattr(GC, "POTENTIAL_ONE_RING_PER_NAME", False)
    assert PT.ring_rule() == "one push per name, setup and session the first time it is a potential"
    assert PT.push_note(S).startswith("🧠 Potentials ring your phone live — one push per name, setup and session the "
                                      "first time it is a potential, 04:00–20:00 ET on the 5-minute pass")
    monkeypatch.setattr(GC, "POTENTIAL_PUSH_ARMED_ONLY", True)
    assert PT.ring_rule() == ("the first time it is armed (every rule met, only the break missing) — one push per "
                              "name, setup and session")


# ── P8 / P11 — the ⚡ tracker contract ───────────────────────────────────────────────────────────────────────────
def test_P8_gg5_run_pass_writes_the_session_volume_run_py_read(monkeypatch):
    from tests.test_gajjala_variant_gg5_identity import scenario
    seen = {}
    real = PT.run_pass

    def spy(*a, **k):
        seen.update(k.get("session_volume") or {})
        return real(*a, **k)
    monkeypatch.setattr(PT, "run_pass", spy)
    st, out = scenario("live", monkeypatch)
    assert seen and all(isinstance(v, (int, float)) for v in seen.values() if v is not None)
    lasts = [(w["body"]["q"]["_id"], w["body"]["upd"]["$set"]["last"]) for w in out["writes"]
             if w["coll"] == "gajjala_potentials" and w["op"] == "update_one"
             and "last" in (w["body"]["upd"].get("$set") or {})]
    assert lasts
    for _id, last in lasts:
        sym = _id.split("|")[1]
        assert "session_volume" in last and last["session_volume"] == seen.get(sym)
        assert "halt_resume_et" not in last and "reg_gain_pct" not in last     # NEGATIVE: both switches None
    assert GC.HALT_CALM_BARS is None and GC.AH_EXHAUSTION_MAX_PCT is None


def _sv_pass(st, now, frames, *, sv=..., ctx=None):
    reads = {"AAA": {"bull_flag": bf_armed()}}
    kw = {} if sv is ... else {"session_volume": sv}
    return PT.run_pass(reads, frames, now, S, store=st, ctx=ctx or {"AAA": ctx_for()},
                       rows={"AAA": {"volume": 2_000_000}}, send=Rec(OK_SEND), owner="o@x", tape="rth", **kw)


def test_P8_session_volume_lands_only_when_handed():
    st = fake_store()
    seed(st)
    now = at(10, 6)
    _sv_pass(st, now, {"AAA": frame_at(now)}, sv={"aaa": 2_345_678})
    assert doc_of(st)["last"]["session_volume"] == 2_345_678
    _sv_pass(st, now + timedelta(minutes=5), {"AAA": frame_at(now + timedelta(minutes=5))}, sv={"ZZZ": 1})
    assert doc_of(st)["last"]["session_volume"] is None                           # handed, unread → None
    st2 = fake_store()
    seed(st2)
    _sv_pass(st2, now, {"AAA": frame_at(now)})                                    # NEGATIVE: not handed → no key
    assert "session_volume" not in doc_of(st2)["last"]


def test_P8_NEGATIVE_the_1_minute_tracker_has_no_session_volume():
    st, _ = gg1_store()
    seed(st)
    now = at(10, 6)
    _sv_pass(st, now, {"AAA": frame_1m(now)})
    doc = st.get_potential(S, "AAA", "bull_flag")
    assert doc and "session_volume" not in doc["last"] and "halt_resume_et" not in doc["last"]


@pytest.mark.parametrize("switch,value", [("HALT_CALM_BARS", 2), ("AH_EXHAUSTION_MAX_PCT", 50.0)])
def test_P11_a_suppression_switch_on_puts_the_halt_ctx_on_gg5_last(monkeypatch, switch, value):
    monkeypatch.setattr(GC, switch, value)
    st = fake_store()
    seed(st)
    now = at(10, 6)
    ctx = {"AAA": dict(ctx_for(), last_halt_resume_et="09:58", reg_gain_pct=42.5)}
    _sv_pass(st, now, {"AAA": frame_at(now)}, sv={"AAA": 3_000_000}, ctx=ctx)
    last = doc_of(st)["last"]
    assert last["halt_resume_et"] == "09:58" and last["reg_gain_pct"] == 42.5 and last["session_volume"] == 3_000_000
    st1, _ = gg1_store()                                                          # NEGATIVE: GG1 never carries them
    seed(st1)
    _sv_pass(st1, now, {"AAA": frame_1m(now)}, ctx=ctx)
    assert "halt_resume_et" not in st1.get_potential(S, "AAA", "bull_flag")["last"]


def test_P11_NEGATIVE_both_switches_none_no_halt_keys():
    assert GC.HALT_CALM_BARS is None and GC.AH_EXHAUSTION_MAX_PCT is None
    st = fake_store()
    seed(st)
    now = at(10, 6)
    ctx = {"AAA": dict(ctx_for(), last_halt_resume_et="09:58", reg_gain_pct=42.5)}
    _sv_pass(st, now, {"AAA": frame_at(now)}, sv={"AAA": 3_000_000}, ctx=ctx)
    last = doc_of(st)["last"]
    assert "halt_resume_et" not in last and "reg_gain_pct" not in last


def test_track_preserves_the_break_blocks_and_never_writes_them():
    st = fake_store()
    seed(st)
    now = at(10, 6)
    _sv_pass(st, now, {"AAA": frame_at(now)}, sv={"AAA": 3_000_000})
    _id = doc_of(st)["_id"]
    st.coll("gajjala_potentials").docs[_id]["brk"] = {"state": "shadow"}
    st.coll("gajjala_potentials").docs[_id]["brk_held"] = [{"reason": "blind"}]
    doc, is_new = PT.track(st, S, "AAA", "bull_flag", bf_armed(), "armed", now + timedelta(minutes=5), px=10.9,
                           values={}, session_volume=1)
    assert not is_new and doc["brk"] == {"state": "shadow"} and doc["brk_held"] == [{"reason": "blind"}]
    assert doc_of(st)["brk"] == {"state": "shadow"}


# ── P9 — the building check runs LAST ────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("when,day,age,reason", [((9, 40), S, 1, "muted"), ((20, 5), S, 1, "outside_hours"),
                                                 ((10, 6), LABOR_DAY, 1, "closed_day"), ((10, 6), S, 30, "stale_tape")])
def test_P9_NEGATIVE_every_other_gate_wins_over_building(when, day, age, reason):
    st = fake_store()
    seed(st, d=day)
    send = Rec(OK_SEND)
    out = go(st, at(*when, d=day), {"AAA": {"bull_flag": bf_building()}}, send=send, age_min=age)
    assert out[reason] == 1 and out["building_held"] == 0 and send.calls == []
    assert held(st, d=day) == [reason]


def test_P9_NEGATIVE_the_trader_floor_wins_over_building_and_name():
    st = fake_store()
    seed(st)
    now = at(10, 6)
    out = PT.run_pass({"MXCT": {"bull_flag": bf_building()}}, {"MXCT": frame_at(now)}, now, S, store=st,
                      ctx={"MXCT": {"trader": "x"}}, rows={}, send=Rec(OK_SEND), owner="o@x", tape="rth",
                      trader_hold={"MXCT": 300_000})
    assert out["trader_held"] == 1 and out["building_held"] == 0


# ── P10 — the count keys ─────────────────────────────────────────────────────────────────────────────────────────
def test_P10_the_two_counts_are_appended_after_trader_held():
    k = PT.COUNT_KEYS
    assert k[k.index("trader_held"):] == ("trader_held", "building_held", "name_held")
    st = fake_store()
    seed(st)
    now = at(10, 6)
    out = PT.run_pass({"AAA": {"bull_flag": bf_armed()}}, {"AAA": frame_at(now)}, now, S, store=st,
                      ctx={"AAA": ctx_for()}, rows={}, send=Rec(OK_SEND), owner="o@x", tape="rth", promo_hold={})
    assert tuple(out) == PT.COUNT_KEYS + ("promo_held",)                         # promo_held still LAST
    assert PT.BUILDING_HELD == ("building",) and PT.NAME_HELD == ("name_rang",)
    assert not (set(PT.BUILDING_HELD + PT.NAME_HELD) & set(PT.RULE_HELD + PT.STORE_HELD + PT.JOIN_HELD + PT.ADD_HELD))


# ── eligible() — the gate table ──────────────────────────────────────────────────────────────────────────────────
FORMING = [{"state": "forming", "kind": "building"}, {"state": "forming", "kind": "armed"}]
BROKEN = [{"state": "forming", "kind": "building"}, {"state": "partial", "kind": None},
          {"state": "forming", "kind": "armed"}]


@pytest.mark.parametrize("reasons,path,ok", [
    (["building"], BROKEN, True),                     # building only: rings the first time it arms, no D3 test
    (["building", "muted"], FORMING, True),           # a RULE hold keeps D3 — unbroken
    (["muted", "building"], BROKEN, False),           # NEGATIVE: … broken
    (["name_rang"], FORMING, False),                  # NEGATIVE: final for the day
    (["building", "name_rang"], FORMING, False),      # NEGATIVE
    (["joined_midsession", "building"], FORMING, False),   # NEGATIVE: D9
    (["building", "claim_error"], BROKEN, True),      # a store fault is always retried
])
def test_eligible_table(reasons, path, ok):
    doc = {"held": [{"reason": r} for r in reasons], "state_path": path, "first_seen_mode": "normal"}
    assert PT.eligible(doc, False, "armed") is ok


def test_eligible_NEGATIVE_a_rung_or_joined_doc_never_passes():
    assert PT.eligible({"push": {"state": "pushed"}, "held": [{"reason": "building"}]}, False, "armed") is False
    assert PT.eligible({"first_seen_mode": "joined", "held": [{"reason": "building"}]}, False, "armed") is False
    assert PT.eligible({"held": [{"reason": "building"}]}, False, None) is False


def test_the_run_module_hands_the_session_volume_map():
    import inspect
    src = inspect.getsource(RUN.run_pass)
    assert "session_volume=sv)" in src
