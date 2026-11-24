"""🩳 High SI card chip carries the % (Ajay 2026-11-23, on three cards where a 49.2% High sat beside a 26.8% EXTREME:
"Why is high more than extreme? can you actually put a percentage directly here?").

The chip now reads e.g. "🩳 49.2% short interest · High (float unconfirmed) · float at or under 10,000,000". The % is the
short-interest record's own % of float (what the house tier is read on), else the card's float %. Words only: the tier,
the listing and the gates are untouched. NEGATIVES: no number → no %, never "None"/"nan"; a confirmed float never says
"unconfirmed"; the chartless line carries the same chip words and still never names the ticker.
"""
from __future__ import annotations

from chart_maps.gajjala import high_si as HS
from short_interest import read as SR

import tests.test_gajjala_high_si_2026_11_23 as B           # the house fixtures (si_block over synthetic docs)

si, board, store, rdoc, HIGH, EXTR, AKAN = B.si, B.board, B.store, B.rdoc, B.HIGH, B.EXTR, B.AKAN
_no_override = B._no_override                               # the house autouse fixture (no holiday override)


def _label(out, sym):
    return next(t for t in out["tiles"] if t["symbol"] == sym)["gajjala"]["state_label"]


def test_chip_prints_the_record_pct_and_the_tier_word(si):
    si["blocks"] = {"HIGH": HIGH[0], "EXTR": EXTR[0]}
    out = board(store([rdoc("HIGH", HIGH[1]), rdoc("EXTR", EXTR[1])]))
    hi, ex = _label(out, "HIGH"), _label(out, "EXTR")
    assert hi == "🩳 %s short interest · High · float at or under %s" % (SR._pct_tier(HIGH[0]["pct_of_float"]), f"{B.CAP:,}")
    assert ex.startswith("🩳 %s short interest · EXTREME" % SR._pct_tier(EXTR[0]["pct_of_float"]))
    assert "15.0%" in hi and "30.0%" in ex
    assert "unconfirmed" not in hi and "unconfirmed" not in ex          # NEGATIVE: confirmed floats never say so


def test_unconfirmed_float_says_why_a_high_can_carry_a_bigger_pct(si):
    si["blocks"] = {"AKAN": AKAN[0], "EXTR": EXTR[0]}
    out = board(store([rdoc("AKAN", AKAN[1]), rdoc("EXTR", EXTR[1])]))
    ak = _label(out, "AKAN")
    assert AKAN[0]["float_check"] == SR.FLOAT_UNCONFIRMED and AKAN[0]["tier"] == SR.TIER_HIGH
    assert ak.startswith("🩳 36.4%% short interest · High (%s)" % SR.FLOAT_UNCONFIRMED_WORD)
    assert AKAN[0]["pct_of_float"] > EXTR[0]["pct_of_float"]         # the case he asked about: High % > EXTREME %


def test_tier_chip_negatives_no_number_no_pct():
    assert HS.tier_chip({"tier_word": "High"}) == "🩳 short interest · High"
    for bad in (None, "x", float("nan"), float("inf"), True):
        lab = HS.tier_chip({"tier_word": "High", "pct_record": bad, "pct_card": bad})
        assert lab == "🩳 short interest · High" and "None" not in lab and "nan" not in lab.lower()
    assert HS.tier_chip({"tier_word": "High", "pct_card": 12.34}) == "🩳 %s short interest · High" % SR._pct_tier(12.34)
    assert HS.tier_chip({"tier_word": "High", "pct_record": 40.0, "pct_card": 12.0}).startswith("🩳 40.0% ")
    assert HS.tier_chip(None) == "🩳 short interest · %s" % HS.DASH
    assert HS.tier_chip({"tier_word": "EXTREME", "float_check": SR.FLOAT_CONFIRMED, "pct_record": 25}).endswith("EXTREME")


def test_chartless_line_carries_the_pct_and_never_the_ticker(si):
    si["blocks"] = {"HIGH": HIGH[0], "EXTR": EXTR[0]}
    empty = {"bars5": [], "curves5": [], "bars15": [], "curves15": []}
    out = board(store([rdoc("HIGH", HIGH[1], tile=empty), rdoc("EXTR", EXTR[1])]))
    line = out["high_si"]["chartless"][0]
    assert line["state_label"] == "🩳 15.0% short interest · High" and "HIGH" not in line["state_label"]
