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
    assert "Phone push is off" in a


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
