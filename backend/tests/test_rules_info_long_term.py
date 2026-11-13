"""ℹ️ Rules panel — the 📅 Long Term section (spec §3.12, WP-RUN, 2026-11-12).

Ajay 2026-11-12, verbatim: "… Remember this analays criteria I am asking you to for this tab …"

Every line is long_term_list.words.rules_lines() (numbers formatted there from long_term_list.constants): the eight
screened lists → picks; notices, schedule, push, forward record → alerts. Key "long_term" sits right BEFORE "luk" so
the luk → doji_sweep → … → short_interest chain holds. NEGATIVES: no 🧭 / Pankaj text (the panel is public); a raising
import drops only this section; a monkeypatched constant moves the line.
"""
from __future__ import annotations

import re

import pytest

from long_term_list import constants as LTC
from long_term_list import words as LTW
from supply_demand import rules_info as RI


@pytest.fixture()
def sec():
    return RI.sections()["long_term"]


def test_long_term_sits_right_before_luk_and_the_chain_pins_hold():
    keys = RI.SECTION_KEYS
    assert keys.count("long_term") == 1
    assert keys.index("long_term") == keys.index("luk") - 1
    assert keys.index("luk") == keys.index("doji_sweep") - 1             # test_rules_info_luk.py
    assert keys.index("doji_sweep") == keys.index("high_beta") - 1
    assert keys.index("high_beta") == keys.index("gajjala") - 1
    assert keys.index("gajjala") == keys.index("fallen") - 1
    assert keys[-3:] == ("fallen", "drop10", "short_interest")
    assert tuple(RI.sections()) == keys


def test_shape(sec):
    assert sec["emoji"] == LTC.MARK and sec["title"] == "Long Term"
    assert " ".join([sec["emoji"], sec["title"]]) == LTC.TITLE
    assert len(sec["picks"]) == len(LTC.SCREENED_KEYS) <= 8
    assert sec["stops"] and len(sec["stops"]) <= 6
    assert sec["note"] == LTW.NOTE and "UNMEASURED" in sec["note"]


def test_lines_are_the_words_rules_lines(sec):
    rules = LTW.rules_lines()
    want_picks = [f"{r['label']}: {r['text']}" for r in rules if r["key"] in LTC.SCREENED_KEYS]
    want_alerts = [f"{r['label']}: {r['text']}" for r in rules if r["key"] not in LTC.SCREENED_KEYS]
    assert sec["picks"] == want_picks and sec["alerts"] == want_alerts
    a = " ".join(sec["alerts"])
    for kind in LTC.RING_KINDS:
        assert kind in a
    # RE-PINNED 2026-11-12 (pkzone spec §3.6): the digest push is LIVE by his call ("Weekly and if something gets
    # dropped let me know …") — the push line is the live rule text, never "Phone push is off".
    assert LTW.pushed_text() in a and "Phone push is off" not in a
    assert "Zone reach push: " + LTW.zone_rule_text() in sec["alerts"]


def test_zone_reach_line_is_built_from_its_constants_2026_11_12(monkeypatch):
    a = " ".join(RI.sections()["long_term"]["alerts"])
    assert "Zone reach push:" in a and "within 0.5% of an edge" in a and "previous session's close" in a
    assert a.count("Zone reach push:") == 1
    monkeypatch.setattr(LTC, "PANKAJ_ZONE_PAD_PCT", 0.7)
    a2 = " ".join(RI.sections()["long_term"]["alerts"])
    assert "within 0.7%" in a2 and "within 0.5%" not in a2                   # NEG: the number is never typed
    monkeypatch.setattr(LTC, "ZONE_PUSH_MODE", "off")
    assert "Phone push off." in " ".join(RI.sections()["long_term"]["alerts"])


def test_NEGATIVE_zone_reach_line_lands_in_alerts_not_picks_2026_11_12(sec):
    assert not any("Zone reach push" in x for x in sec["picks"])
    line = next(x for x in sec["alerts"] if x.startswith("Zone reach push:"))
    assert "Pankaj" not in line and "\U0001F9ED" not in line


def test_a_monkeypatched_constant_moves_the_line(monkeypatch):
    monkeypatch.setattr(LTC, "CQ_MIN_ROE_PCT", 33.0)
    p = " ".join(RI.sections()["long_term"]["picks"])
    assert "ROE ≥ 33%" in p and "ROE ≥ 20%" not in p


def test_NEGATIVE_no_pankaj_text_anywhere_in_the_section(sec):
    blob = " ".join([sec["title"], sec["note"]] + sec["picks"] + sec["stops"] + sec["alerts"])
    assert "Pankaj" not in blob and "\U0001F9ED" not in blob


def test_NEGATIVE_no_trading_verbs(sec):
    blob = " ".join(sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]]).replace(LTW.NOT_A_SIGNAL, "")
    assert not re.search(r"\b(buy|buying|bought|sell|selling|sold|entry|entries|exit|exits)\b", blob, re.I)
    assert "b" + "ounce" not in blob.lower()


def test_NEGATIVE_a_raising_import_drops_only_this_section(monkeypatch):
    def _boom(**k):
        raise RuntimeError("words broke")
    monkeypatch.setattr(LTW, "rules_lines", _boom)
    secs = RI.sections()
    assert "long_term" not in secs and "luk" in secs and "fallen" in secs
