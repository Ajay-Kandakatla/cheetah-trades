"""The 🚩 card's chart lines carry ONE served print of their level (2026-10-21).

Ajay, on a NUAI 🧠 card (Horizontal Fade, trigger 3.605) whose chart label read "TRIGGER 3.61", whose read line read
"trigger 3.61 · stop 3.41", and whose PLAN row read "Entry 3.60 · STOP 3.41 3.41": "The entry getting changed..".
The float was the same everywhere; the server printed it on the broker grid (tab._px → round_price, half-up: 3.61) while
the browser's PLAN row rounded the raw float itself (toFixed(2) of 3.605 = "3.60"), and the STOP row printed the served
label "STOP 3.41" as its name and then the price again. Now tab._tile_lines serves `text` = _px(price) on every line,
and the FE prints that text (PatternChart PLAN rows; cardLadder.planLineKey strips it off the label to name the row).
NEGATIVES: no trigger → no trigger line (and no text); the text is never a second number — it is the one in the label;
the raw `price` is unchanged (the chart's geometry and the lane's order math never read `text`).
"""
from __future__ import annotations

import pytest

from chart_maps.gajjala import tab as GT


@pytest.mark.parametrize("trigger, stop, t_text, s_text", [
    (3.605, 3.41, "3.61", "3.41"),         # NUAI: the half-cent high prints on the broker grid, half-up
    (2.72, 2.64, "2.72", "2.64"),
    (0.3101, 0.2975, "0.3101", "0.2975"),  # sub-dollar: four decimals, trailing zeros trimmed
    (0.31, 0.30, "0.31", "0.3"),
    (12.0, 11.5, "12.00", "11.50"),        # a dollar price always carries its two
])
def test_every_line_carries_the_one_served_print(trigger, stop, t_text, s_text):
    lines = GT._tile_lines({"state": "forming", "trigger": trigger, "stop": stop, "ready": False})
    assert [l["tone"] for l in lines] == ["buy", "stop"]
    assert lines[0]["text"] == t_text == GT._px(trigger)
    assert lines[1]["text"] == s_text == GT._px(stop)
    # the label ends with the same text — the FE strips exactly this to name the row
    assert lines[0]["label"] == f"TRIGGER {t_text}"
    assert lines[1]["label"] == f"STOP {s_text}"
    # the raw price is untouched (geometry, not print)
    assert lines[0]["price"] == trigger and lines[1]["price"] == stop


def test_the_entry_read_keeps_the_buy_word_and_the_same_text():
    lines = GT._tile_lines({"state": "aplus", "trigger": 3.605, "stop": 3.41, "ready": True})
    assert lines[0]["label"] == "BUY > 3.61" and lines[0]["text"] == "3.61"


def test_NEGATIVE_no_trigger_no_trigger_text_and_no_stop_no_stop_text():
    only_stop = GT._tile_lines({"state": "forming", "trigger": None, "stop": 3.41})
    assert [l["tone"] for l in only_stop] == ["stop"] and only_stop[0]["text"] == "3.41"
    only_trig = GT._tile_lines({"state": "forming", "trigger": 3.605, "stop": None, "ready": False})
    assert [l["tone"] for l in only_trig] == ["buy"] and only_trig[0]["text"] == "3.61"
    assert GT._tile_lines({"state": "none"}) == []


def test_NEGATIVE_text_is_never_a_second_number():
    """A line's `text` is the label's own number, never computed twice: for a grid of raw floats the text is always
    the tail of the label and never carries more decimals than the broker grid."""
    for raw in (3.605, 3.615, 3.6049, 0.30005, 0.31005, 1.005, 99.995):
        lines = GT._tile_lines({"state": "forming", "trigger": raw, "stop": raw, "ready": False})
        for l in lines:
            assert l["label"].endswith(" " + l["text"]), (raw, l)
            dec = l["text"].split(".")[1] if "." in l["text"] else ""
            assert len(dec) <= (4 if float(l["text"]) < 1 else 2), (raw, l)
