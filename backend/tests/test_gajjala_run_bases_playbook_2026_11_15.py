"""📓 Playbook "Not built" item for the 📶 base count (spec WP-D, 2026-11-15).

Ajay 2026-11-15, verbatim: "There is a concept of 3 bases and climax run can you bake that in to the app please" ·
"I need that tracked in to Gajjala's". The cards COUNT the bases (information only); ACTING on the count — GG's peel at the
3rd base, out at the 4th, and his counter-rule trigger — stays not built. The item is APPENDED at the end of NOT_BUILT;
every earlier item, including the "Exits, partials, base counting, …" line, stays byte-equal (docs/gajjala/run_bases_2026_11_15.md).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from chart_maps.gajjala import playbook as PB

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "gajjala" / "first_hand_2026_10_13.md"
RAW = FIXTURE.read_text(encoding="utf-8")
_SPLIT = RAW.index("# PART 2")
PART = {"S8": RAW[:_SPLIT], "S9": RAW[_SPLIT:]}

NEW_TEXT = ("Acting on the base count — peel at the 3rd base, out at the 4th — and GG's counter-rule trigger. The cards "
            "COUNT the bases as information only (📶, 5-minute bars, my definition — your call); nothing peels, exits or "
            "rings on it.")
NEW_TS = "40:54–41:18"
FIRST_LINE = ("Exits, partials, base counting, breakeven-and-add — his discretion, shown above, never computed.",
              "24:46–26:40", "S8")
TITLE = "Not built — Playbook text only (each would need your numbers)"
# sha256 of json.dumps(NOT_BUILT rows, ensure_ascii=False) at origin/main be8be2fa — the 12 rows before this item.
EARLIER_N = 12
EARLIER_SHA = "ea3ae67425820fffd921e9aff755a9d1e0b255f1808e7c0558c05d626daadcf8"


def _sha(rows) -> str:
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()


@pytest.fixture(scope="module")
def section():
    pb = PB.playbook()
    return next(s for s in pb["sections"] if s["title"].startswith("Not built"))


def test_the_new_item_is_served_last_as_not_built_and_not_verbatim(section):
    it = section["items"][-1]
    assert it["text"] == NEW_TEXT
    assert it["kind"] == PB.KIND_NOT_BUILT == "not_built"
    assert it["verbatim"] is False
    assert it["status"] == "not_built" and it["status_label"] == PB.LABEL_NOT_BUILT
    assert it["ts"] == NEW_TS and it["source"] == PB.S8


def test_the_new_item_cites_the_climax_quote_timestamp_in_its_own_part(section):
    it = section["items"][-1]
    assert it["ts"] in PART[it["source"]]
    assert it["ts"] not in PART["S9"]
    climax = [m for m in PB.MANAGEMENT if m["ts"] == NEW_TS]
    assert len(climax) == 1 and climax[0]["source"] == PB.S8 and "third base, this is a climax run" in climax[0]["text"]


def test_the_module_table_appends_exactly_one_row():
    title, rows = PB.NOT_BUILT
    assert title == TITLE
    assert len(rows) == EARLIER_N + 1
    assert rows[-1] == (NEW_TEXT, NEW_TS, PB.S8)


def test_negative_every_earlier_row_is_byte_equal_to_main():
    _, rows = PB.NOT_BUILT
    assert _sha(list(rows[:EARLIER_N])) == EARLIER_SHA


def test_negative_the_base_counting_line_is_untouched_and_still_first(section):
    _, rows = PB.NOT_BUILT
    assert rows[0] == FIRST_LINE
    assert section["items"][0]["text"] == FIRST_LINE[0]
    assert section["items"][0]["ts"] == FIRST_LINE[1] and section["items"][0]["source"] == FIRST_LINE[2]
    blob = " ".join(it["text"] for it in section["items"][:-1])
    assert "base counting" in blob


def test_negative_a_changed_earlier_row_would_fail_the_pin():
    _, rows = PB.NOT_BUILT
    bent = list(rows[:EARLIER_N])
    bent[0] = (bent[0][0].replace("base counting", "base count"),) + tuple(bent[0][1:])
    assert _sha(bent) != EARLIER_SHA
    assert _sha(list(rows[1:EARLIER_N + 1])) != EARLIER_SHA


def test_negative_the_new_item_is_not_passed_off_as_his_words():
    norm = re.sub(r"\s+", " ", RAW.replace("**", ""))
    assert NEW_TEXT not in norm
    assert "my definition — your call" in NEW_TEXT and "information only" in NEW_TEXT


def test_negative_the_gg_quotes_the_count_reads_stay_byte_equal():
    by = {(m["ts"], m["source"]): m["text"] for m in PB.MANAGEMENT}
    assert by[("40:54–41:18", PB.S8)] == "first base, second base, third base, this is a climax run … I was peeling off early."
    assert by[("1:00:37", PB.S8)] == "fourth base, I came out of everything."
    sq = {(m["ts"], m["source"]): m["text"] for m in PB.SQUEEZE[1]}
    assert sq[("55:18–57:49", PB.S9)] == ("if it moves sideways with less volume and forms another base, high chance it "
                                          "has an even bigger move")


def test_negative_the_new_item_carries_no_advice_or_ban_words():
    low = NEW_TEXT.lower()
    for word in ("b" + "ounc", "buy", "sell", "you should"):
        assert word not in low, word
    assert "nothing peels, exits or rings on it" in NEW_TEXT
