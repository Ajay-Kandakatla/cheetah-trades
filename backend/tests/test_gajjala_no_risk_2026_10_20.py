"""🚫 A no-risk A+ never rings · one price grid (2026-10-20).

Finding (live Mongo, 2026-10-20): the pushed alert `GG:2026-10-20|MMA|kiss_fly` carried trigger 0.31 = stop 0.31
(risk_pct 0.0). Nothing had rounded it: MMA is a one-print name — the kiss bar (10:45–10:50 ET) was a single trade at
0.31 (high = low), the "break" one 170-share print at 0.3101 — while the day's other sub-dollar alerts kept their
decimals (PLAG 0.5888 / 0.5668, REED 0.44495 / 0.4325). The 🏁 grader already kept that alert out of the % (plan
"no_risk", AMENDMENTS9 E4); what was wrong is that the detector called it A+ and the push rang with trigger = stop.

Pinned here: (1) a reference bar with no range → trigger = stop → the read is INVALID, never A+, never pushed — the
words are ledger.plan_of's own ("no_risk" / "no_plan"), used by every detector through _resolve_break; (2) the push
gate refuses such an A+ a second time ("no_risk", recorded "#no_risk", counted); (3) tab._px — the ONE price formatter
of the card, the push, the 🏁 Track record and the 🚩 lane — sits on the broker's grid (trading.broker.round_price /
price_decimals: four decimals under the sub-dollar line, two at or over), typed once, nowhere else.
NEGATIVES: a $4.46 level still prints two decimals; a 0.3101 trigger with a 0.2950 stop keeps its R (0.0151) and rings
with both numbers in the body; a kiss bar WITH a range still reads A+.
"""
from __future__ import annotations

import inspect
import re
from decimal import Decimal

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import tab as GT
from supply_demand import rules_info as RI
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_alerts import S, at, live, one, read, shadow, stamp   # noqa: F401 — the fixtures ride along
from tests.test_gajjala_store import fake_store
from trading import broker as BR
from trading import gajjala_entry as GE

B_WORD = re.compile("b" + "ounc", re.I)
KISS_BAR = 4 + 3                                                 # kf_frame: 4 quiet + the leg, then 3 pullback bars


# ── (1) the detector: a one-print reference bar is invalid, never A+ ─────────────────────────────────────────────
def test_a_one_print_kiss_bar_reads_invalid_no_risk_never_aplus():
    F = FX.kf_frame(one_print_kiss=True)
    k = F.today.start + KISS_BAR
    assert F.o[k] == F.h[k] == F.l[k] == F.c[k]                   # the MMA shape: one print, no range
    r = D.kiss_fly(F)
    assert r["state"] == "invalid" and r["reason"] == D.NO_RISK_REASON
    assert r["trigger"] == r["stop"] == F.h[k] and r["risk_pct"] == 0.0
    assert r["broke"] is False and r["ready"] is False
    assert r["entry_bar_t"] == F.t[k + 1]                        # the levels and the bar stay on the card
    assert {c["key"] for c in r["criteria"]} >= {"k5_kiss", "k5_uptrend"}
    assert AL._candidates({"MMA": {"kiss_fly": r}}) == []          # never a push candidate


def test_NEGATIVE_a_kiss_bar_with_range_still_reads_aplus_and_keeps_its_r():
    F = FX.kf_frame()
    r = D.kiss_fly(F)
    k = F.today.start + KISS_BAR
    assert r["state"] == "aplus" and (r["trigger"], r["stop"]) == (F.h[k], F.l[k]) and r["trigger"] > r["stop"]
    plan, rr = LG.plan_of(r["trigger"], r["stop"])
    assert plan == "ok" and rr == pytest.approx(F.h[k] - F.l[k]) and rr > 0
    assert len(AL._candidates({"GGA": {"kiss_fly": r}})) == 1


def test_a_stop_above_the_trigger_is_no_plan_invalid():
    F = FX.kf_frame()
    k = F.today.start + KISS_BAR
    r = D._blank("kiss_fly", F, len(F.c) - 1)
    out = D._resolve_break(r, F, k + 1, F.l[k], F.h[k], None, len(F.c) - 1, [])   # swapped: stop over the trigger
    assert out["state"] == "invalid" and out["reason"] == D.NO_PLAN_REASON


def test_the_reasons_are_the_ledgers_plan_words_and_every_break_passes_the_rule():
    src = inspect.getsource(D._resolve_break)
    assert "plan_of(trigger, stop)" in src and "PLANS[0]" in src and "PLANS[2]" in src
    assert "ledger import PLANS, plan_of" in inspect.getsource(D)
    assert LG.PLANS == ("ok", "no_plan", "no_risk")
    assert D.NO_RISK_REASON.startswith("no risk") and D.NO_PLAN_REASON.startswith("no plan")
    for s in (D.NO_RISK_REASON, D.NO_PLAN_REASON):
        assert not any(ch.isdigit() for ch in s) and not B_WORD.search(s)
    whole = inspect.getsource(D)
    # every setup resolves its break through the ONE resolver (7 call sites: flag, kiss ×2, fade, vcp, squeeze + def)
    assert whole.count("_resolve_break(") >= 7
    assert "def _resolve_break" in whole and whole.count("def _resolve_break") == 1


def test_a_sub_dollar_criterion_value_keeps_its_decimals():
    assert D._px(0.3087) == "0.3087" and D._px(0.31) == "0.31" and D._px(10.41) == "10.41" and D._px(None) == "—"
    src = inspect.getsource(D)
    assert "9 EMA {_px(_e9(F, ref))} · 21 EMA {_px(_e21(F, ref))}" in src
    assert '" → ".join(_px(x) for x in ranges)' in src and '" · ".join(_px(x) for x in lows)' in src


# ── (2) the push gate: the second lock ───────────────────────────────────────────────────────────────────────────
def test_an_aplus_with_trigger_equal_stop_is_no_risk_recorded_never_sent(live):
    st = fake_store()
    counts, send = one(st, read(trigger=0.31, stop=0.31))
    assert counts["no_risk"] == 1 and counts["pushed"] == 0 and counts["aplus"] == 1 and send.calls == []
    doc = st.alerts_coll().docs["GG:2026-10-13|GGA|bull_flag#no_risk"]
    assert doc["state"] == "no_risk" and doc["trigger"] == doc["stop"] == 0.31
    assert "GG:2026-10-13|GGA|bull_flag" not in st.alerts_coll().docs      # never claimed as a push


def test_a_stop_above_the_trigger_is_no_risk_at_the_gate_too(live):
    counts, send = one(fake_store(), read(trigger=0.31, stop=0.32))
    assert counts["no_risk"] == 1 and counts["pushed"] == 0 and send.calls == []


def test_shadow_mode_refuses_it_the_same_way(shadow):
    st = fake_store()
    counts, send = one(st, read(trigger=0.31, stop=0.31))
    assert counts["no_risk"] == 1 and counts["shadow"] == 0 and send.calls == []
    assert "SHADOW:GG:2026-10-13|GGA|bull_flag" not in st.alerts_coll().docs


def test_the_count_key_sits_before_broker_flagged_which_stays_last():
    assert "no_risk" in AL.COUNT_KEYS and AL.COUNT_KEYS[-1] == "broker_flagged"
    assert AL.COUNT_KEYS.index("no_risk") == len(AL.COUNT_KEYS) - 2
    assert "no_risk" not in PT.COUNT_KEYS                        # the 🧠 pass is untouched (HIS CALL — see the doc)


def test_NEGATIVE_a_sub_dollar_aplus_with_r_rings_with_both_numbers(live):
    r = read(trigger=0.3101, stop=0.2950)
    assert LG.plan_of(r["trigger"], r["stop"]) == ("ok", 0.0151)
    counts, send = one(fake_store(), r)
    assert counts["pushed"] == 1 and counts["no_risk"] == 0
    body = send.calls[0][1]["body"]
    assert "broke 0.3101 on the 5m bar" in body and "stop 0.295 (−4.9%)" in body
    assert send.calls[0][1]["items"][0]["text"].count("0.3101") == 1


def test_NEGATIVE_a_dollar_aplus_prints_two_decimals(live):
    counts, send = one(fake_store(), read(trigger=4.46, stop=4.3))
    assert counts["pushed"] == 1
    body = send.calls[0][1]["body"]
    assert "broke 4.46 on the 5m bar" in body and "stop 4.30 (" in body and "4.4600" not in body


# ── (3) the ONE price formatter on the broker's grid ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("x, want", [
    (4.46, "4.46"),                      # NEGATIVE: a dollar level keeps two decimals, never four
    (4.12, "4.12"), (3.95, "3.95"), (10.8125, "10.81"), (2.375, "2.38"),
    (1.0, "1.00"), (0.99996, "1.00"),    # a sub-dollar price that rounds onto $1.00 re-grids at two
    (0.3101, "0.3101"), (0.31, "0.31"), (0.2950, "0.295"), (0.44495, "0.445"), (0.5888, "0.5888"), (0.0921, "0.0921"),
    (None, "—"), ("x", "—"), (float("nan"), "—"),
])
def test_px_is_the_broker_grid(x, want):
    assert GT._px(x) == want


@pytest.mark.parametrize("x", [0.0921, 0.1012, 0.2648, 0.3101, 0.44495, 0.5888, 0.8744, 0.99996, 1.0, 2.375, 4.46,
                               10.8125, 143.21, 1234.5])
def test_px_equals_round_price_and_price_decimals(x):
    v = BR.round_price(x)
    s = GT._px(x)
    assert float(s) == v
    assert len(s.split(".")[1]) <= BR.price_decimals(v)
    if BR.price_decimals(v) == BR.DOLLAR_DECIMALS:
        assert len(s.split(".")[1]) == BR.DOLLAR_DECIMALS


def test_px_types_no_decimal_count_of_its_own():
    src = inspect.getsource(GT._px)
    assert "round_price(" in src and "price_decimals(" in src and "DOLLAR_DECIMALS" in src
    assert not re.search(r"\.[24]f|< 1\b|<\s*1\.0", src)          # the rule lives in trading/broker_alpaca.py only
    assert BR.SUB_DOLLAR_LINE == 1.00 and BR.SUB_DOLLAR_DECIMALS == 4 and BR.DOLLAR_DECIMALS == 2


def test_every_surface_formats_through_the_one_px():
    for x in (0.3101, 0.44495, 4.46, None):
        assert AL._px(x) == PT._px(x) == LG._px(x) == GE._px(x) == GT._px(x)


# ── (4) the ledger's rule is unchanged: the stored MMA alert is "no risk", out of the % ──────────────────────────
def test_the_stored_mma_alert_is_no_risk_and_never_graded_win_or_loss():
    mma = {"trigger": 0.31, "stop": 0.31, "price": 0.3101}
    assert LG.plan_of(mma["trigger"], mma["stop"]) == ("no_risk", None)
    from datetime import date
    rang = at(11, 1, date(2026, 10, 20))                          # the real alert's clock (15:01 UTC)
    bounds = LG.session_bounds(date(2026, 10, 20), rang)
    g = LG.grade(dict(mma, at_utc=rang), [(rang, 0.31, 0.3101, 0.31, 0.3101)], bounds, LG.GC.LEDGER_HORIZONS[0])
    assert g["entry"] == "no_risk" and g.get("outcome") is None and LG.GC.LEDGER_HORIZONS[0] == "same"
    c = LG._counts_blank("same")
    assert "no_risk" in c and "thin" in c                          # its own bucket, never win / loss
    assert LG.plan_of(0.3101, 0.2950) == ("ok", 0.0151) and Decimal("0.3101") - Decimal("0.2950") == Decimal("0.0151")


# ── (5) the words on his surfaces ────────────────────────────────────────────────────────────────────────────────
def test_the_legend_and_the_rules_panel_say_it_in_words():
    inv = next(r for r in GT.count_legend() if r["key"] == "invalid")["text"]
    assert "no risk" in inv and "the trigger would equal the stop" in inv
    stops = RI.sections()["gajjala"]["stops"]
    assert len(stops) <= 6
    assert "no risk" in stops[0] and "never A+, never pushed" in stops[0]
    for s in (inv, stops[0]):
        assert not B_WORD.search(s)
