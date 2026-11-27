"""🩳 2026-11-26 floatguard (spec §1.7 line "Pick 1 does not contain EXTREME today; it will after §3.5", §6) — the
four existing pins that located the tier pick by `"EXTREME" in p` now exclude pick 1 ('% of float = ') by its
prefix. These tests pin that the selector still finds exactly ONE tier pick at index 2 in every mode, that pick 1
names EXTREME only when the source sentence does, and that pick 1 passes the forecast-word check in every mode.
"""
from __future__ import annotations

import pytest

from short_interest import basis_math as BM
from short_interest import read as SR
from short_interest import source_check as SCK
from tests.test_short_interest_read_2026_10_03 import FORBIDDEN

PICK1 = "% of float = "
WORD = SR.TIER_WORDS[SR.TIER_EXTREME]


def _tier_picks(picks):
    return [p for p in picks if WORD in p and not p.startswith(PICK1)]


@pytest.mark.parametrize("m", SCK.EXTREME_CONTEST_MODES)
def test_the_tier_pick_is_found_once_at_index_2_in_every_mode(monkeypatch, m):
    monkeypatch.setattr(SCK, "EXTREME_CONTEST", m)
    picks = SR.rules_section()["picks"]
    assert len(picks) == 8 and picks[1].startswith(PICK1) and picks[1].endswith(BM.rules_sentence())
    (tier,) = _tier_picks(picks)
    assert picks.index(tier) == 2


@pytest.mark.parametrize("m", SCK.EXTREME_CONTEST_MODES)
def test_pick_1_passes_the_forecast_words_in_every_mode(monkeypatch, m):
    monkeypatch.setattr(SCK, "EXTREME_CONTEST", m)
    p1 = SR.rules_section()["picks"][1]
    assert not FORBIDDEN.search(p1), p1
    assert "band" not in p1.lower()


def test_built_default_pick_1_names_extreme_and_the_warning():
    assert SCK.contest_mode() == "flag"
    p1 = SR.rules_section()["picks"][1]
    assert WORD in p1 and SCK.SHORT_SOURCES in p1
    assert len([p for p in SR.rules_section()["picks"] if WORD in p]) == 2


# ───────────────────────────────────────────── NEGATIVES
def test_NEGATIVE_off_mode_pick_1_holds_no_extreme_word_so_only_the_tier_pick_does(monkeypatch):
    monkeypatch.setattr(SCK, "EXTREME_CONTEST", "off")
    picks = SR.rules_section()["picks"]
    assert WORD not in picks[1] and SCK.SHORT_SOURCES not in picks[1]
    assert len([p for p in picks if WORD in p]) == 1


def test_NEGATIVE_unknown_mode_word_behaves_as_off(monkeypatch):
    monkeypatch.setattr(SCK, "EXTREME_CONTEST", "loud")
    picks = SR.rules_section()["picks"]
    assert WORD not in picks[1]
    (tier,) = _tier_picks(picks)
    assert picks.index(tier) == 2


def test_NEGATIVE_a_raising_source_sentence_leaves_pick_1_without_extreme(monkeypatch):
    monkeypatch.setattr(SCK, "rules_sentence", lambda: 1 / 0)
    picks = SR.rules_section()["picks"]
    assert len(picks) == 8 and WORD not in picks[1]
    (tier,) = _tier_picks(picks)
    assert picks.index(tier) == 2


def test_NEGATIVE_a_planted_forecast_word_in_the_source_sentence_trips_the_check(monkeypatch):
    planted = SCK.rules_sentence() + " The name will drop."
    monkeypatch.setattr(SCK, "rules_sentence", lambda: planted)
    p1 = SR.rules_section()["picks"][1]
    assert FORBIDDEN.search(p1)


def test_NEGATIVE_the_prefix_selector_does_not_hide_a_second_tier_pick():
    picks = list(SR.rules_section()["picks"])
    picks.insert(5, "A planted pick that says EXTREME twice.")
    with pytest.raises(ValueError):
        (_,) = _tier_picks(picks)
