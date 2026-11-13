"""📅 Long Term (2026-11-12) — notices: what rings (stage_drop / sales_drop / started_moving only),
what is ⚠️ (a fundamental leg), what is a neutral line (moved / zone / absent). Critique C4 + C5."""
from __future__ import annotations

import datetime as dt

from long_term_list import constants as C
from long_term_list import criteria as CR
from long_term_list import notices as N

GOOD = {
    "s2_growth": {"qualifier": True, "stage": 2, "sales_tier": "strong", "sales_accelerating": False,
                  "c_strong_q_eps": True, "a_strong_y_eps": True},
    "capital_quality": {"qualifier": True, "roe_pct": 25.0, "fcf_margin_pct": 12.0, "net_debt_ebitda": 0.4},
    "fallen_growers": {"pct_below_high": 55.0, "pct_above_low": 20.0, "sales_yoy_pct": 40.0, "pair_blanked": False,
                       "floor_ok": True, "in_served_pool": True},
    "hot": {"sales_tier": "explosive", "q_eps_yoy": 30.0, "ret_21d": 12.0, "served": True},
    "quiet_strong": {"stage": 1, "score": 80.0, "score_ranked": True, "net_profit": 1e8, "ocf": 2e8,
                     "sales_cagr": 20.0, "liab_to_equity": 0.5, "sales_tier": "strong", "dollar_vol_50": 9e6,
                     "pct_below_high": 14.3, "net_debt_ebitda": -0.3},
    "accel_after_fall": {"market_cap": 2e9, "sales_tier": "strong", "sales_accelerating": True,
                         "growth_yoy_pct": 60.0, "prior_yoy_pct": 20.0, "pct_below_high": 45.0,
                         "pct_above_low": 30.0, "stage": 1, "dollar_vol_50": 4e6},
}
LABELS = {1: "Basing", 2: "Advancing", 3: "Topping", 4: "Decline"}


def _now(chips, stage, tier="strong", over=None, zone_read=None, absent=None):
    over = over or {}
    legs = {}
    for cat in chips:
        if cat == "pankaj":
            continue
        vals = {**GOOD[cat], **over.get(cat, {})}
        if "stage" in vals:
            vals["stage"] = stage
        if "sales_tier" in vals and cat not in over or "sales_tier" not in over.get(cat, {}):
            if "sales_tier" in vals:
                vals["sales_tier"] = tier
        legs[cat] = CR.legs(cat, vals)
    return {"stage": stage, "stage_label": LABELS.get(stage), "sales_tier": tier, "sales_yoy_pct": 12.3,
            "sales_q_end": "2026-09-30", "legs": legs, "zone_read": zone_read, "absent": absent or []}


def _save(chips, stage, tier="strong", over=None, zone_in=None):
    n = _now(chips, stage, tier, over)
    return {"stage": stage, "sales_tier": tier, "legs": {c: N.verdicts(v) for c, v in n["legs"].items()},
            "zone_in": list(zone_in or [])}


def _session(i):
    return (dt.date(2026, 11, 13) + dt.timedelta(days=7 * i)).isoformat()


def run_weeks(sym, chips, save, weeks):
    flags, prev, out = N.initial_flags(save), None, []
    for i, now in enumerate(weeks):
        evs, flags = N.detect(sym, chips, flags, prev, now, save, _session(i))
        prev = {c: N.verdicts(v) for c, v in now["legs"].items()}
        out.append(evs)
    return out, flags


def kinds(evs):
    return [e["kind"] for e in evs]


def all_kinds(weeks):
    return [k for evs in weeks for k in kinds(evs)]


S2 = ["s2_growth"]
Q = ["quiet_strong"]


# ── stage_drop ──
def test_stage_2_to_3_and_2_to_4_ring():
    for to in (3, 4):
        w, flags = run_weeks("AMD", S2, _save(S2, 2), [_now(S2, to)])
        ev = [e for e in w[0] if e["kind"] == "stage_drop"]
        assert len(ev) == 1 and ev[0]["rings"] is True
        assert ev[0]["text"] == f"⚠️ AMD Stage 2 → Stage {to} ({LABELS[to]}) — last read in Stage 2 on 2026-11-12"
        assert flags["stage_drop_active"] is True
        assert N.section_for(flags, _now(S2, to), _session(0)) == "changed"


def test_negative_3_to_4_is_not_an_event():
    w, _ = run_weeks("ANET", S2, _save(S2, 3), [_now(S2, 4)])
    assert "stage_drop" not in kinds(w[0])


def test_negative_2_to_1_is_not_an_event():
    w, flags = run_weeks("AMD", S2, _save(S2, 2), [_now(S2, 1)])
    assert "stage_drop" not in kinds(w[0]) and flags["stage_drop_active"] is False


def test_c5_2_to_1_to_3_fires():
    w, _ = run_weeks("AMD", S2, _save(S2, 2), [_now(S2, 1), _now(S2, 3)])
    assert "stage_drop" not in kinds(w[0]) and kinds(w[1]).count("stage_drop") == 1


def test_c5_2_to_none_to_3_fires():
    w, flags = run_weeks("AMD", S2, _save(S2, 2), [_now(S2, None), _now(S2, 3)])
    assert kinds(w[1]).count("stage_drop") == 1
    assert flags["last_stage"] == 3


def test_negative_none_week_keeps_last_stage():
    _, flags = run_weeks("AMD", S2, _save(S2, 2), [_now(S2, None)])
    assert flags["last_stage"] == 2 and flags["last_stage2_on"] == C.SAVED_ON


def test_negative_saved_3_then_4_never():
    w, _ = run_weeks("X", S2, _save(S2, 3), [_now(S2, 4), _now(S2, 3), _now(S2, 4)])
    assert "stage_drop" not in all_kinds(w)


def test_negative_saved_1_then_3_never():
    w, _ = run_weeks("X", S2, _save(S2, 1), [_now(S2, 3), _now(S2, 4)])
    assert "stage_drop" not in all_kinds(w)


def test_2_to_3_then_3_again_one_event():
    w, flags = run_weeks("AMD", S2, _save(S2, 2), [_now(S2, 3), _now(S2, 3), _now(S2, 4)])
    assert all_kinds(w).count("stage_drop") == 1
    assert flags["stage_drop_active"] is True


def test_2_3_2_4_two_events():
    w, flags = run_weeks("AMD", S2, _save(S2, 2), [_now(S2, 3), _now(S2, 2), _now(S2, 4)])
    assert all_kinds(w).count("stage_drop") == 2
    assert flags["last_stage2_on"] == _session(1)


def test_back_to_stage_2_clears_the_drop():
    _, flags = run_weeks("AMD", S2, _save(S2, 2), [_now(S2, 3), _now(S2, 2)])
    assert flags["stage_drop_active"] is False


# ── started_moving ──
def test_quiet_1_to_2_started_moving_rings():
    w, flags = run_weeks("MPWR", Q, _save(Q, 1), [_now(Q, 2)])
    assert kinds(w[0]) == ["started_moving"]
    ev = w[0][0]
    assert ev["rings"] is True
    assert ev["text"] == "🌱 → 🚀 MPWR started moving: Stage 1 → Stage 2 (Advancing)"
    assert N.section_for(flags, _now(Q, 2), _session(0)) == "started_moving"


def test_negative_quiet_stage_leg_fail_on_start_is_no_other_event():
    w, flags = run_weeks("MPWR", Q, _save(Q, 1), [_now(Q, 2)])
    assert "fundamental" not in kinds(w[0]) and "moved" not in kinds(w[0])
    assert flags["fundamental_failing"] == []


def test_quiet_1_none_2_fires():
    w, _ = run_weeks("MPWR", Q, _save(Q, 1), [_now(Q, None), _now(Q, 2)])
    assert kinds(w[1]).count("started_moving") == 1


def test_negative_quiet_1_3_2_no_started_moving():
    w, _ = run_weeks("MPWR", Q, _save(Q, 1), [_now(Q, 3), _now(Q, 2)])
    assert "started_moving" not in all_kinds(w)


def test_negative_non_quiet_1_to_2_no_event():
    w, _ = run_weeks("X", ["accel_after_fall"], _save(["accel_after_fall"], 1), [_now(["accel_after_fall"], 2)])
    assert w[0] == []
    w2, _ = run_weeks("X", S2, _save(S2, 1), [_now(S2, 2)])
    assert "started_moving" not in kinds(w2[0])


def test_quiet_1_to_4_is_moved_not_warning():
    w, flags = run_weeks("XPEL", Q, _save(Q, 1), [_now(Q, 4)])
    assert kinds(w[0]) == ["moved"]
    assert w[0][0]["rings"] is False
    assert "left Stage 1 → Stage 4 · Decline" in w[0][0]["text"]
    assert "⚠️" not in w[0][0]["text"]
    assert N.section_for(flags, _now(Q, 4), _session(0)) == "holding"


# ── sales_drop ──
def test_sales_strong_to_steady_rings():
    w, flags = run_weeks("AMD", S2, _save(S2, 2, "strong"), [_now(S2, 2, "steady")])
    ev = [e for e in w[0] if e["kind"] == "sales_drop"]
    assert len(ev) == 1 and ev[0]["rings"] is True
    assert ev[0]["text"] == "⚠️ AMD sales tier strong → steady (y/y +12.3%, quarter ended 2026-09-30)"
    assert flags["sales_drop_active"] is True
    assert "fundamental" not in kinds(w[0])                 # the tier leg folds into sales_drop


def test_sales_declining_text_says_down():
    w, _ = run_weeks("AMD", S2, _save(S2, 2, "strong"), [_now(S2, 2, "declining")])
    assert w[0][0]["text"].endswith("— sales now down y/y")


def test_negative_unknown_tier_either_side_no_event():
    w, _ = run_weeks("AMD", S2, _save(S2, 2, "unknown"), [_now(S2, 2, "weak")])
    assert "sales_drop" not in kinds(w[0])
    w, _ = run_weeks("AMD", S2, _save(S2, 2, "strong"), [_now(S2, 2, "unknown")])
    assert "sales_drop" not in kinds(w[0])
    w, _ = run_weeks("AMD", S2, _save(S2, 2, None), [_now(S2, 2, "weak")])
    assert "sales_drop" not in kinds(w[0])


def test_negative_second_week_still_low_no_second_event_still_changed():
    w, flags = run_weeks("AMD", S2, _save(S2, 2, "strong"), [_now(S2, 2, "steady"), _now(S2, 2, "steady")])
    assert all_kinds(w).count("sales_drop") == 1
    assert N.section_for(flags, _now(S2, 2, "steady"), _session(1)) == "changed"


def test_sales_recovery_clears():
    _, flags = run_weeks("AMD", S2, _save(S2, 2, "strong"), [_now(S2, 2, "steady"), _now(S2, 2, "explosive")])
    assert flags["sales_drop_active"] is False


# ── C4: market legs are neutral, fundamental legs are ⚠️ but never ring ──
def test_c4_quiet_mpwr_off_high_is_moved_only():
    save = _save(Q, 1)
    w, flags = run_weeks("MPWR", Q, save, [_now(Q, 1, over={"quiet_strong": {"pct_below_high": 8.2}})])
    assert kinds(w[0]) == ["moved"]
    assert w[0][0]["rings"] is False
    assert w[0][0]["text"] == "MPWR 8.2% under its 52-week high (needs ≥ 10%)"
    assert N.section_for(flags, _now(Q, 1), _session(0)) == "holding"


def test_c4_fallen_recovery_is_moved():
    ch = ["fallen_growers"]
    w, flags = run_weeks("ONDS", ch, _save(ch, 1), [_now(ch, 1, over={"fallen_growers": {"pct_below_high": 30.0}})])
    assert kinds(w[0]) == ["moved"] and flags["fundamental_failing"] == []


def test_c4_hot_return_sign_flip_is_moved():
    ch = ["hot"]
    w, _ = run_weeks("APP", ch, _save(ch, 2, "explosive"),
                     [_now(ch, 2, "explosive", over={"hot": {"ret_21d": -3.0}})])
    assert kinds(w[0]) == ["moved"] and not w[0][0]["rings"]


def test_c4_s2_qualifier_flip_is_moved():
    w, flags = run_weeks("AMD", S2, _save(S2, 2), [_now(S2, 2, over={"s2_growth": {"qualifier": False}})])
    assert kinds(w[0]) == ["moved"]
    assert N.section_for(flags, _now(S2, 2), _session(0)) == "holding"


def test_c4_roe_25_to_18_is_fundamental_warning_not_ring():
    ch = ["capital_quality"]
    w, flags = run_weeks("MA", ch, _save(ch, 2), [_now(ch, 2, over={"capital_quality": {"roe_pct": 18.0}})])
    assert kinds(w[0]) == ["fundamental"]
    ev = w[0][0]
    assert ev["rings"] is False and ev["text"].startswith("⚠️ MA no longer meets 💎 Capital quality: ROE 18.0%")
    assert flags["fundamental_failing"] == ["capital_quality"]
    assert N.section_for(flags, _now(ch, 2), _session(0)) == "changed"


def test_fundamental_clears_when_every_leg_passes():
    ch = ["capital_quality"]
    _, flags = run_weeks("MA", ch, _save(ch, 2), [_now(ch, 2, over={"capital_quality": {"roe_pct": 18.0}}),
                                                  _now(ch, 2)])
    assert flags["fundamental_failing"] == []


def test_negative_unknown_legs_never_an_event():
    ch = ["capital_quality"]
    w, flags = run_weeks("MA", ch, _save(ch, 2), [_now(ch, 2, over={"capital_quality": {
        "roe_pct": None, "qualifier": None, "net_debt_ebitda": None}})])
    assert w[0] == [] and flags["fundamental_failing"] == []


def test_negative_absent_text_never_says_dropped_except_not_dropped():
    w, flags = run_weeks("XPEL", Q, _save(Q, 1), [_now(Q, 1, absent=["scan", "fallen"])])
    ev = [e for e in w[0] if e["kind"] == "absent"][0]
    assert ev["rings"] is False
    assert ev["text"].endswith("— not read, not dropped")
    assert "dropped" not in ev["text"].replace("not dropped", "")
    assert flags["absent"] == ["scan", "fallen"]


def test_precedence_accel_2_to_4_one_stage_drop_both_categories():
    ch = ["fallen_growers", "accel_after_fall"]
    w, _ = run_weeks("LUNR", ch, _save(ch, 2), [_now(ch, 4)])
    assert kinds(w[0]) == ["stage_drop"]
    assert w[0][0]["categories"] == ch


def test_events_ordered_by_precedence():
    ch = ["s2_growth"]
    w, _ = run_weeks("AMD", ch, _save(ch, 2), [_now(ch, 3, "steady", over={"s2_growth": {
        "qualifier": False, "c_strong_q_eps": False}}, absent=["research"])])
    assert kinds(w[0]) == ["stage_drop", "sales_drop", "fundamental", "moved", "absent"]


def test_pankaj_zone_newly_in_is_neutral():
    ch = ["pankaj"]
    zr = CR.zone_read({"Agg": (400.0, 410.0)}, 405.49, "2026-11-13", ("Agg",))
    w, flags = run_weeks("TSM", ch, _save(ch, 2), [_now(ch, 2, zone_read=zr), _now(ch, 2, zone_read=zr)])
    assert kinds(w[0]) == ["zone"] and w[0][0]["rings"] is False
    assert w[0][0]["text"] == "🧭 TSM in Pankaj's Agg zone (400–410) at the 11-13 close"
    assert w[1] == []                                     # still in -> no second line
    assert flags["zone_in"] == ["Agg"]


def test_negative_pankaj_saved_in_zone_no_event():
    ch = ["pankaj"]
    zr = CR.zone_read({"Agg": (400.0, 410.0)}, 405.49, "2026-11-13", ("Agg",))
    w, _ = run_weeks("TSM", ch, _save(ch, 2, zone_in=["Agg"]), [_now(ch, 2, zone_read=zr)])
    assert w[0] == []


# ── digest ──
def test_digest_rings_only_with_a_ring_kind():
    w, _ = run_weeks("AMD", S2, _save(S2, 2), [_now(S2, 3)])
    d = N.digest(w[0], {}, _session(0))
    assert d["rings"] is True and d["n_dropped"] == 1 and d["n_ring"] == 1
    assert d["title"] == "📅 Long Term — week of 2026-11-13: 1 dropped (stage or sales) · 0 started moving · 0 in Pankaj's zones"


def test_negative_digest_quiet_week_never_rings():
    evs = []
    evs += run_weeks("MPWR", Q, _save(Q, 1), [_now(Q, 1, over={"quiet_strong": {"pct_below_high": 8.2}})])[0][0]
    evs += run_weeks("MA", ["capital_quality"], _save(["capital_quality"], 2),
                     [_now(["capital_quality"], 2, over={"capital_quality": {"roe_pct": 18.0}})])[0][0]
    zr = CR.zone_read({"Agg": (400.0, 410.0)}, 405.49, "2026-11-13", ("Agg",))
    evs += run_weeks("TSM", ["pankaj"], _save(["pankaj"], 2), [_now(["pankaj"], 2, zone_read=zr)])[0][0]
    evs += run_weeks("XPEL", Q, _save(Q, 1), [_now(Q, 1, absent=["scan"])])[0][0]
    assert sorted(set(kinds(evs))) == ["absent", "fundamental", "moved", "zone"]
    d = N.digest(evs, {"s2_growth": ["NEW1"]}, _session(0))
    assert d["rings"] is False and d["n_ring"] == 0
    assert d["n_moved"] == 1 and d["n_fundamental"] == 1 and d["n_zone"] == 1 and d["n_absent"] == 1
    assert d["n_new_in_top"] == 1


def test_digest_body_cap_and_more_line():
    evs = []
    for i in range(9):
        evs += run_weeks(f"S{i}", S2, _save(S2, 2), [_now(S2, 3)])[0][0]
    d = N.digest(evs, {}, _session(0))
    assert len(d["lines"]) == C.DIGEST_BODY_LINES + 1
    assert d["lines"][-1] == f"+{9 - C.DIGEST_BODY_LINES} more on the tab"
    assert len(d["items"]) == 9


def test_digest_item_order():
    evs = []
    evs += run_weeks("ZZZ", S2, _save(S2, 2), [_now(S2, 3)])[0][0]
    evs += run_weeks("AAA", Q, _save(Q, 1), [_now(Q, 1, absent=["scan"])])[0][0]
    evs += run_weeks("MMM", Q, _save(Q, 1), [_now(Q, 2)])[0][0]
    assert [i["kind"] for i in N.digest(evs, {}, "d")["items"]] == ["stage_drop", "started_moving", "absent"]


# ── state helpers ──
def test_at_save_and_initial_flags_from_a_baseline():
    base = {"names": {"AMD": {"stage": 2, "sales_tier": "strong"}},
            "categories": {"s2_growth": {"AMD": {"values": GOOD["s2_growth"]}},
                           "hot": {"AMD": {"legs": [{"key": "ret_21d", "verdict": "pass"}]}}},
            "pankaj": {"AMD": {"zone_read": {"in": ["C1"]}}}}
    s = N.at_save("AMD", base)
    assert s["stage"] == 2 and s["sales_tier"] == "strong" and s["zone_in"] == ["C1"]
    assert s["legs"]["s2_growth"]["qualifier"] == "pass" and s["legs"]["hot"] == {"ret_21d": "pass"}
    f = N.initial_flags(s)
    assert f["last_stage2_on"] == C.SAVED_ON and f["last_stage"] == 2 and f["zone_in"] == ["C1"]
    assert N.initial_flags({"stage": 1})["last_stage2_on"] is None


def test_section_not_read_when_every_leg_unknown():
    now = {"stage": None, "legs": {"s2_growth": CR.legs("s2_growth", {})}, "zone_read": None}
    assert N.section_for(N.initial_flags({"stage": 2}), now, "d") == "not_read"
    pk_only = {"stage": None, "legs": {}, "zone_read": {"unknown": True}}
    assert N.section_for({}, pk_only, "d") == "not_read"
