"""🎬 Replays files an A+ reel by the replay pipeline's +30%-from-trigger label (2026-11-26).

Ajay 2026-11-26, verbatim: "Unless there are 30% uptrend don't call them winners from our A+ trigger.." · "You can call
them losers.." · on this tab: "Don't think videos are up to date these are still in Winner" (CENN / OGEN 11-17 cards
read "A+ loser · +26.8% from trigger (under 30%) · app grade W +1R" under 🏁 A+ winners).

NEGATIVES: no win30 key, a non-dict win30, a "not final" label and an unknown label all fall back to the grade
exactly as before; a 🎾 potential or a mover is never moved by a win30 key; the grade on the card is unchanged.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from chart_maps.replays import constants as C
from chart_maps.replays import store as ST

DAY = "2026-11-17"
REPLAYS = Path("/Users/ajay/clinet-test/eod-audits/replays/replay_win30.py")


def _aplus(grade="W +1R", win30=None, ring_tail="|aplus"):
    s = {"file": "CENN_reversal_squeeze_45x.mp4", "ring_id": f"2026-11-16|CENN|reversal_squeeze{ring_tail}",
         "symbol": "CENN", "setup": "reversal_squeeze", "page": "gajjala",
         "why": ["5-min A+ loser · +26.8% from trigger (under 30%) · app grade W +1R"], "grade": grade,
         "speed": 45.0, "minutes": 21.4, "window": C.FULL_DAY_WINDOW}
    if win30 is not None:
        s[C.WIN30_KEY] = win30
    return s


def test_w_graded_under_30_files_under_losers():
    assert ST.group_of(_aplus("W +1R", {"label": "loser", "run_pct": 26.8}), DAY) == "aplus_losers"


def test_l_graded_that_ran_30_files_under_winners():
    assert ST.group_of(_aplus("L −1R", {"label": "winner", "run_pct": 31.9}), DAY) == "aplus_winners"


def test_winner_label_and_w_grade_stays_winners():
    assert ST.group_of(_aplus("W +1R", {"label": "winner", "run_pct": 47.0}), DAY) == "aplus_winners"


@pytest.mark.parametrize("w30", [None, "loser", ["loser"], {}, {"label": None}, {"label": "not final"},
                                 {"label": "LOSER"}, {"label": 1}])
def test_no_usable_label_falls_back_to_the_grade(w30):
    assert ST.group_of(_aplus("W +1R", w30), DAY) == "aplus_winners"
    assert ST.group_of(_aplus("L −1R", w30), DAY) == "aplus_losers"


def test_potential_and_mover_never_moved_by_win30():
    pot = _aplus("W +1R", {"label": "loser"}, ring_tail="|potential")
    pot["plan_word"] = C.RS_WORD
    assert ST.group_of(pot, DAY) == "rs_potentials"
    mov = _aplus("W +1R", {"label": "winner"}, ring_tail="|potential")
    mov["why"] = [f"biggest mover of {DAY}"]
    assert ST.group_of(mov, DAY) == "biggest_mover"
    other = _aplus("W +1R", {"label": "winner"}, ring_tail="|potential")
    assert ST.group_of(other, DAY) == "other"


def test_card_keeps_the_app_grade(tmp_path):
    side = _aplus("W +1R", {"label": "loser", "run_pct": 26.8})
    side.update({"fps": 10, "frames": 1, "story": "s", "move_pct": 1.0})
    card = ST.video_payload(side, DAY)
    assert card["grade"] == "W +1R"


@pytest.mark.skipif(not REPLAYS.exists(), reason="the host replay folder is not on this machine")
def test_words_equal_the_pipeline_constants():
    src = REPLAYS.read_text(encoding="utf-8")
    assert f'KEY = "{C.WIN30_KEY}"' in src
    assert 'WINNER, LOSER, OPEN = "winner", "loser", "not final"' in src
    assert set(C.WIN30_GROUP) == {"winner", "loser"}
