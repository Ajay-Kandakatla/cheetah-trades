"""OpEx pure-logic tests — max-pain, expiration classification, dealer GEX sign.

Includes the design review's worked example (spot 100, NetGEX +$4.0M → pinning,
max-pain $100) as a regression, plus the sign-rule guard (the #1 risk was a
flipped GEX sign calling 'pinning' what is actually 'amplifying')."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from options.opex import classify_expiration, max_pain, net_gex_and_walls


# --------------------------------------------------------------------------
# expiration classification
# --------------------------------------------------------------------------
def test_classify_quad_witching():
    # 2026-06-19 is the 3rd Friday of June → quad-witching
    c = classify_expiration("2026-06-19", date(2026, 6, 1))
    assert c["expiration_type"] == "quad_witching"
    assert c["days_to_expiry"] == 18


def test_classify_monthly_third_friday():
    # 2026-07-17 is the 3rd Friday of July (not Mar/Jun/Sep/Dec) → monthly
    assert classify_expiration("2026-07-17", date(2026, 7, 1))["expiration_type"] == "monthly"


def test_classify_weekly():
    # 2026-07-10 is a Friday but the 2nd Friday → weekly
    assert classify_expiration("2026-07-10", date(2026, 7, 1))["expiration_type"] == "weekly"
    # a non-Friday listed expiry is also weekly
    assert classify_expiration("2026-07-08", date(2026, 7, 1))["expiration_type"] == "weekly"


# --------------------------------------------------------------------------
# max-pain (the design review's worked example)
# --------------------------------------------------------------------------
def test_max_pain_worked_example():
    # calls: 100→10k, 105→12k ; puts: 95→8k, 100→6k. min payout at S=100.
    call_oi = {100: 10_000, 105: 12_000}
    put_oi = {95: 8_000, 100: 6_000}
    mp = max_pain(call_oi, put_oi, spot=100.0)
    assert mp["max_pain_strike"] == 100
    assert mp["total_oi"] == 36_000
    assert mp["pct_from_spot"] == 0.0


def test_max_pain_empty_and_zero_oi_return_none():
    assert max_pain({}, {}) is None
    assert max_pain({100: 0}, {100: 0}) is None


def test_max_pain_single_strike():
    mp = max_pain({100: 500}, {100: 200}, spot=100.0)
    assert mp["max_pain_strike"] == 100 and mp["strike_count"] == 1


# --------------------------------------------------------------------------
# dealer GEX — the sign rule is the crux
# --------------------------------------------------------------------------
def test_net_gex_worked_example_is_pinning():
    rows = [
        {"strike": 95, "type": "put", "gamma": 0.020, "oi": 8_000},
        {"strike": 100, "type": "call", "gamma": 0.050, "oi": 10_000},
        {"strike": 100, "type": "put", "gamma": 0.050, "oi": 6_000},
        {"strike": 105, "type": "call", "gamma": 0.030, "oi": 12_000},
    ]
    g = net_gex_and_walls(rows, spot=100.0)
    # scale = 100 * 0.01 * 100^2 = 10_000 ; net gamma·OI = -160+200+360 = 400
    assert g["net_gex_dollars"] == 4_000_000.0
    assert g["regime"] == "pinning"          # positive net GEX = pinning
    assert g["call_wall"] == 105             # upper gamma cap (above spot)
    assert g["put_wall"] == 95               # support (below spot)
    assert g["magnet_strike"] == 105         # largest |per-strike gamma|


def test_net_gex_sign_flips_to_amplifying():
    # a put-gamma-dominated book → negative net GEX → amplifying
    rows = [
        {"strike": 90, "type": "put", "gamma": 0.060, "oi": 20_000},
        {"strike": 100, "type": "call", "gamma": 0.020, "oi": 3_000},
    ]
    g = net_gex_and_walls(rows, spot=100.0)
    assert g["net_gex_dollars"] < 0
    assert g["regime"] == "amplifying"


def test_net_gex_none_without_spot_or_gamma():
    assert net_gex_and_walls([{"strike": 100, "type": "call", "gamma": 0.05, "oi": 1}], spot=None) is None
    assert net_gex_and_walls([{"strike": 100, "type": "call", "gamma": None, "oi": 1}], spot=100.0) is None


def test_net_gex_coverage_pct_when_some_gamma_missing():
    rows = [
        {"strike": 100, "type": "call", "gamma": 0.05, "oi": 8_000},
        {"strike": 105, "type": "call", "gamma": None, "oi": 2_000},   # no gamma
    ]
    g = net_gex_and_walls(rows, spot=100.0)
    assert g["oi_coverage_pct"] == 80.0   # 8k of 10k OI covered


# ── Flip point + top nodes (2026-07-17, GEX board) ───────────────────────────

def test_flip_strike_interpolates_the_zero_gamma_crossing():
    # cumulative: -0.4*10k=-4000 @90 ... crosses into +0.05*100k=+5000 @110
    rows = [
        {"strike": 90, "type": "put", "gamma": 0.04, "oi": 10_000},
        {"strike": 110, "type": "call", "gamma": 0.05, "oi": 100_000},
    ]
    g = net_gex_and_walls(rows, spot=100.0)
    # cum at 90 = -400; crossing to +5000 at 110: frac = 400/5400
    expected = 90 + (400 / 5400) * 20
    assert g["flip_strike"] == round(expected, 2)
    assert g["regime"] == "pinning"


def test_flip_none_when_profile_is_one_sided():
    calls_only = [{"strike": k, "type": "call", "gamma": 0.03, "oi": 1000}
                  for k in (95, 100, 105)]
    g = net_gex_and_walls(calls_only, spot=100.0)
    assert g["flip_strike"] is None
    puts_only = [{"strike": k, "type": "put", "gamma": 0.03, "oi": 1000}
                 for k in (95, 100, 105)]
    g2 = net_gex_and_walls(puts_only, spot=100.0)
    assert g2["flip_strike"] is None and g2["regime"] == "amplifying"


def test_top_nodes_sorted_by_absolute_gamma():
    rows = [
        {"strike": 90, "type": "put", "gamma": 0.10, "oi": 50_000},
        {"strike": 100, "type": "call", "gamma": 0.02, "oi": 1_000},
        {"strike": 110, "type": "call", "gamma": 0.05, "oi": 20_000},
    ]
    g = net_gex_and_walls(rows, spot=100.0)
    strikes = [n["strike"] for n in g["top_nodes"]]
    assert strikes[0] == 90 and strikes[1] == 110
    assert g["top_nodes"][0]["gex_dollars"] < 0     # put node is dealer-negative


# ── VEX (net vanna) ──────────────────────────────────────────────────────────

def test_bs_vanna_signs_and_degenerate_inputs():
    from options.opex import _bs_vanna
    # OTM call above spot: d2 < 0 -> vanna positive
    v_otm = _bs_vanna(100.0, 120.0, 0.4, 30)
    assert v_otm is not None and v_otm > 0
    # deep ITM call: d2 > 0 -> vanna negative
    v_itm = _bs_vanna(100.0, 60.0, 0.4, 30)
    assert v_itm is not None and v_itm < 0
    for bad in ((0, 100, 0.4, 30), (100, 0, 0.4, 30), (100, 100, 0, 30)):
        assert _bs_vanna(*bad) is None


def test_net_vex_reads_and_fails_closed():
    from options.opex import net_vex
    rows = [{"strike": 110, "type": "call", "vanna": 2.0, "oi": 1_000},
            {"strike": 90, "type": "put", "vanna": 1.0, "oi": 500}]
    v = net_vex(rows, spot=100.0)
    assert v["net_vex_dollars"] > 0
    assert "tailwind" in v["read"]

    flipped = net_vex([{"strike": 90, "type": "put", "vanna": 2.0, "oi": 5_000}],
                      spot=100.0)
    assert flipped["net_vex_dollars"] < 0 and "headwind" in flipped["read"]

    assert net_vex(rows, spot=None) is None
    assert net_vex([{"strike": 90, "type": "put", "vanna": None, "oi": 100}],
                   spot=100.0) is None


# ── Best case (setup-tab lens) ───────────────────────────────────────────────

def test_best_case_bullish_bearish_mixed_and_none():
    from options.opex import best_case
    gamma_bull = {"net_gex_dollars": 5e8, "flip_strike": 95.0,
                  "call_wall": 110.0, "put_wall": 90.0}
    b = best_case(100.0, gamma_bull, {"read": "falling IV = dealer buying (vanna tailwind)"})
    assert b["bias"] == "bullish"
    assert "110" in b["path"] and "+10" in b["path"]
    assert "95" in b["risk"]
    assert "tailwind" in b["vanna_note"]

    gamma_bear = {"net_gex_dollars": -5e8, "flip_strike": 105.0,
                  "call_wall": 110.0, "put_wall": 90.0}
    b2 = best_case(100.0, gamma_bear, None)
    assert b2["bias"] == "bearish"
    assert "105" in b2["path"] and b2["vanna_note"] is None

    mixed = best_case(100.0, {"net_gex_dollars": 5e8, "flip_strike": 105.0,
                              "call_wall": None, "put_wall": None}, None)
    assert mixed["bias"] == "mixed"

    assert best_case(None, gamma_bull, None) is None
    assert best_case(100.0, None, None) is None
