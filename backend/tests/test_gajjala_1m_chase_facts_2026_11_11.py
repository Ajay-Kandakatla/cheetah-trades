"""Proposal #3 (ADDITIVE) — facts on the 1-minute A+ push (spec four/entry §3.5 / §5.3, 2026-11-11).

Ajay 2026-11-11: "Also apply your proposal too." Built: on the one-minute page ONLY (GG1; 2026-11-11 — never GG5, never
the 🧪 GGA shadow records), the A+ body carries ONE clause right
after the stop bit — "last {px} · {pct} vs the trigger · {r}R left to +{m}R" (or "already past +{m}R" once the last
price is at or over GG's +R target). Facts only: no threshold, no verdict word, no gate. NEGATIVES are the point: the
GG5 bytes never move, a missing / non-finite / zero / bool last price or a no-risk plan never builds a clause, and the
1-minute push mode / toggle are untouched (shadow still records, never sends).
"""
from __future__ import annotations

import math

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import variant as V
from tests.test_gajjala_run import S, at
from tests.test_gajjala_variant_2026_10_27 import _frames, boom, gg1_store

B_WORD = "b" + "ounce"


def _aplus(trigger=2.0, stop=1.9, frame="1m", entry="2026-10-13 10:40"):
    return {"setup": "bull_flag", "state": "aplus", "entry_bar_t": entry, "frame": frame, "trigger": trigger,
            "stop": stop, "risk_pct": (trigger - stop) / trigger * 100 if trigger and stop is not None else None, "variant": None,
            "grade": None}


def _gg1(last_px, **kw):
    return AL.compose(_aplus(**kw), "gga", {}, session=S, variant=V.GG1, last_px=last_px)


def _after_stop(body: str) -> str:
    """The bit right after the stop bit in a composed body."""
    bits = body.split(" · ")
    i = next(k for k, b in enumerate(bits) if b.startswith("stop "))
    return " · ".join(bits[i + 1:i + 4])


# ── C1 / C2 — the facts ──────────────────────────────────────────────────────────────────────────────────────────
def test_C1_gg1_aplus_last_over_the_trigger_with_r_left():
    want = "last 2.02 · +1.1% vs the trigger · 0.78R left to +1R"
    assert AL.chase_text(2.0, 1.9, 2.022) == want
    p = _gg1(2.022)
    assert _after_stop(p["body"]) == want
    assert p["body"].index("stop 1.90") < p["body"].index(want) < p["body"].index(AL.entry_words("bull_flag"))


def test_C2_already_past_the_target_and_under_the_trigger():
    assert AL.chase_text(2.0, 1.9, 2.12) == "last 2.12 · +6.0% vs the trigger · already past +1R"
    assert AL.chase_text(2.0, 1.9, 1.99) == "last 1.99 · -0.5% vs the trigger · 1.10R left to +1R"
    assert AL.chase_text(2.0, 1.9, 2.10) == "last 2.10 · +5.0% vs the trigger · already past +1R"   # exactly +1R


def test_the_target_multiple_is_read_from_the_constant_at_call_time(monkeypatch):
    monkeypatch.setattr(GC, "LEDGER_R_MULT", 2.0)
    assert AL.chase_text(2.0, 1.9, 2.05) == "last 2.05 · +2.5% vs the trigger · 1.50R left to +2R"
    assert AL.chase_text(2.0, 1.9, 2.20) == "last 2.20 · +10.0% vs the trigger · already past +2R"


def test_sub_dollar_prices_print_on_the_broker_grid():
    assert AL.chase_text(0.31, 0.29, 0.3101) == "last 0.3101 · +0.0% vs the trigger · 0.99R left to +1R"


def test_the_words_are_facts_only():
    for t in (AL.CHASE_TEXT, AL.CHASE_PAST_TEXT):
        assert "chased" not in t.lower() and B_WORD not in t.lower() and "buy" not in t.lower()
    assert "{px}" in AL.CHASE_TEXT and "{pct}" in AL.CHASE_TEXT and "{r}" in AL.CHASE_TEXT and "{m}" in AL.CHASE_TEXT
    assert "{r}" not in AL.CHASE_PAST_TEXT


# ── C3 — GG5 never moves ─────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("last", [2.022, 2.12, 1.99, 11.1])
def test_C3_NEGATIVE_gg5_compose_is_byte_identical_with_or_without_last_px(last):
    r = _aplus(frame="5m")
    assert AL.compose(r, "gga", {}, session=S, last_px=last) == AL.compose(r, "gga", {}, session=S)
    assert AL.compose(r, "gga", {}, session=S, variant=V.GG5, last_px=last) == AL.compose(r, "gga", {}, session=S)
    assert "vs the trigger" not in AL.compose(r, "gga", {}, session=S, last_px=last)["body"]


def test_C3_NEGATIVE_gg5_run_pass_payload_ignores_the_ctx_price(monkeypatch):
    from tests.test_gajjala_alerts import Spy, frames_at, read, stamp
    from tests.test_gajjala_store import fake_store
    from tests.test_gajjala_alerts import at as at5
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    r = read(entry=stamp(10, 5))
    send = Spy()
    AL.run_pass({"GGA": {"bull_flag": r}}, {"GGA": frames_at(r["entry_bar_t"])}, at5(10, 6), S, store=fake_store(),
                send=send, owner="o", ctx={"GGA": {"price": 11.4}})
    assert len(send.calls) == 1
    assert send.calls[0][1] == AL.compose(r, "GGA", {"price": 11.4}, session=S)
    assert "vs the trigger" not in send.calls[0][1]["body"]


# ── C4 — no clause without a usable last price or plan ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), 0, 0.0, -1.0, True, False, "x"])
def test_C4_NEGATIVE_no_usable_last_px_no_clause(bad):
    assert AL.chase_text(2.0, 1.9, bad) == ""
    with_bad, without = _gg1(bad), AL.compose(_aplus(), "gga", {}, session=S, variant=V.GG1)
    assert with_bad == without and "vs the trigger" not in with_bad["body"]


@pytest.mark.parametrize("trigger,stop", [(2.0, 2.0), (1.9, 2.0), (None, 1.9), (2.0, None), (math.nan, 1.9), (0, 0)])
def test_C4_NEGATIVE_a_plan_that_is_not_ok_builds_no_clause(trigger, stop):
    assert AL.chase_text(trigger, stop, 2.02) == ""
    assert "vs the trigger" not in _gg1(2.02, trigger=trigger, stop=stop)["body"]


def test_NEGATIVE_the_title_and_the_item_line_never_change():
    with_px, without = _gg1(2.022), AL.compose(_aplus(), "gga", {}, session=S, variant=V.GG1)
    assert with_px["title"] == without["title"] and with_px["items"] == without["items"]
    assert {k: v for k, v in with_px.items() if k != "body"} == {k: v for k, v in without.items() if k != "body"}


# ── C5 — the 1-minute mode / toggle untouched; shadow records the clause, never sends ────────────────────────────
def test_C5_NEGATIVE_the_1m_push_mode_is_untouched():
    assert GC.GAJJALA_1M_PUSH_MODE == "live" and AL.push_mode(V.GG1) == "live"
    assert V.GG1.push_kind_setup == "gajjala_1m_setup" and AL.KIND == GC.PUSH_KIND == "gajjala_setup"


def test_C5_gg1_shadow_run_pass_records_the_facts_and_never_sends(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "shadow")
    monkeypatch.setattr(AL, "_default_send", boom)
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    st, shared = gg1_store()
    calls = []
    r = _aplus(trigger=11.0, stop=10.5)
    out = AL.run_pass({"GGA": {"bull_flag": r}}, _frames(), at(10, 41), S, store=st,
                      send=lambda o, p: calls.append(p), owner="o", ctx={"GGA": {"price": 11.1}})
    assert out["shadow"] == 1 and out["pushed"] == 0 and calls == []
    wp = st.alerts_coll().docs["SHADOW:GG1:2026-10-13|GGA|bull_flag"]["would_push"]
    assert _after_stop(wp["body"]).startswith("last 11.10 · +0.9% vs the trigger · 0.80R left to +1R")


def test_C5_gg1_live_run_pass_sends_the_facts_once(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "live")
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    st, _ = gg1_store()
    calls = []

    def send(o, p):
        calls.append(p)
        return {"sent": 1, "failed": 0, "total_targets": 1}
    out = AL.run_pass({"GGA": {"bull_flag": _aplus(trigger=11.0, stop=10.5)}}, _frames(), at(10, 41), S, store=st,
                      send=send, owner="o", ctx={"GGA": {"price": 11.1}})
    assert out["pushed"] == 1 and len(calls) == 1
    assert "last 11.10 · +0.9% vs the trigger · 0.80R left to +1R" in calls[0]["body"]


def test_NEGATIVE_gg1_run_pass_without_a_ctx_price_has_no_clause(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_1M_PUSH_MODE", "shadow")
    monkeypatch.setattr(AL, "_default_send", boom)
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    st, _ = gg1_store()
    AL.run_pass({"GGA": {"bull_flag": _aplus(trigger=11.0, stop=10.5)}}, _frames(), at(10, 41), S, store=st,
                send=lambda o, p: None, owner="o")
    wp = st.alerts_coll().docs["SHADOW:GG1:2026-10-13|GGA|bull_flag"]["would_push"]
    assert "vs the trigger" not in wp["body"]


# ── 2026-11-11 (main-session delegation): the clause is the ONE-MINUTE page's only — never on 🧪 GGA shadow records ──
@pytest.mark.parametrize("last", [2.022, 2.12, 1.99, 11.1])
def test_NEGATIVE_gga_compose_is_byte_identical_with_or_without_last_px(last):
    r = _aplus(frame="5m")
    with_px = AL.compose(r, "gga", {}, session=S, variant=V.GGA, last_px=last)
    assert with_px == AL.compose(r, "gga", {}, session=S, variant=V.GGA)
    assert "vs the trigger" not in with_px["body"] and AL.chase_text(2.0, 1.9, last) not in with_px["body"]


def test_the_clause_is_built_on_gg1_and_on_no_other_variant():
    built = {v.key: "vs the trigger" in AL.compose(_aplus(), "gga", {}, session=S, variant=v, last_px=2.022)["body"]
             for v in V.VARIANTS}
    assert built == {V.GG5.key: False, V.GG1.key: True, V.GGA.key: False}


def test_NEGATIVE_gga_shadow_run_pass_record_carries_no_facts(monkeypatch):
    from chart_maps.gajjala import store as ST
    from tests.test_gajjala_alerts import frames_at, read, stamp
    from tests.test_gajjala_alerts import at as at5
    from tests.test_gajjala_store import FakeColl, fake_store
    monkeypatch.setattr(AL, "_default_send", boom)
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    assert AL.push_mode(V.GGA) == "shadow"
    st = ST.GajjalaStore(colls={n: FakeColl() for n in ST.OWN if n not in V.GGA.borrows}, variant=V.GGA,
                         shared=fake_store())
    r = read(entry=stamp(10, 5))
    out = AL.run_pass({"GGA": {"bull_flag": r}}, {"GGA": frames_at(r["entry_bar_t"])}, at5(10, 6), S, store=st,
                      send=boom, owner="o", ctx={"GGA": {"price": 11.4}})
    assert out["shadow"] == 1 and out["pushed"] == 0
    recs = [d for k, d in st.alerts_coll().docs.items() if k.startswith(AL.SHADOW_CLAIM_PREFIX)]
    assert len(recs) == 1
    assert "vs the trigger" not in recs[0]["would_push"]["body"]
    assert recs[0]["would_push"] == AL.compose(r, "GGA", {"price": 11.4}, session=S, variant=V.GGA)
