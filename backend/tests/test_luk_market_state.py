"""chart_maps/luk/market_state.py — the QQQ / IWM state WORD, never a gate (BUILD SPEC luk-tab §3.5, WP-A1).
WORD_UNDER for 9 < 21, WORD_OVER otherwise (equal included), WORD_NONE on None; the 2% remark is prose — no number is
applied. NEGATIVES included."""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

from chart_maps.luk import constants as LC
from chart_maps.luk import market_state as MS

B_WORD = re.compile("b" + "ounc", re.I)
EDGE = re.compile(r"\bedge\b", re.I)


def test_the_words():
    assert MS.WORD_UNDER == "{sym}: 9 EMA under 21 — his not-favourable-for-longs read"
    assert MS.WORD_OVER == "{sym}: 9 EMA over 21"
    assert MS.WORD_NONE == "{sym}: daily bars not cached — no read"
    assert MS.DIST_TEXT == "{sym} {pct:+.1f}% vs its 9 EMA"


@pytest.mark.parametrize("state,want", [
    ({"ema9": 10.0, "ema21": 10.5}, MS.WORD_UNDER),
    ({"ema9": 10.0, "ema21": 10.0000001}, MS.WORD_UNDER),
    ({"ema9": 10.5, "ema21": 10.0}, MS.WORD_OVER),
    ({"ema9": 10.0, "ema21": 10.0}, MS.WORD_OVER),            # equal → over (only "under" is his not-favourable read)
    (None, MS.WORD_NONE),
    ({}, MS.WORD_NONE),
    ({"ema9": None, "ema21": 1.0}, MS.WORD_NONE),
    ({"ema9": 1.0, "ema21": float("nan")}, MS.WORD_NONE),
    ("junk", MS.WORD_NONE),
])
def test_word(state, want):
    assert MS.word("QQQ", state) == want.format(sym="QQQ")


def test_dist_text_is_a_fact():
    assert MS.dist_text("QQQ", {"dist_9_pct": 1.84}) == "QQQ +1.8% vs its 9 EMA"
    assert MS.dist_text("IWM", {"close": 99.0, "ema9": 100.0}) == "IWM -1.0% vs its 9 EMA"
    assert MS.dist_text("IWM", {"close": 99.0, "ema9": 0}) is None
    assert MS.dist_text("IWM", None) is None and MS.dist_text("IWM", {"close": 1.0}) is None


def test_block_rows_follow_the_index_symbols():
    b = MS.block({"QQQ": {"ema9": 2.0, "ema21": 1.0, "close": 2.04}, "SPY": {"ema9": 1, "ema21": 2}})
    assert b["title"] == "🧭 Indices" and b["note"] == MS.NOTE
    assert [r["symbol"] for r in b["rows"]] == list(LC.LUK_INDEX_SYMBOLS) == ["QQQ", "IWM"]
    assert b["rows"][0] == {"symbol": "QQQ", "text": "QQQ: 9 EMA over 21", "dist_text": "QQQ +2.0% vs its 9 EMA"}
    assert b["rows"][1] == {"symbol": "IWM", "text": "IWM: daily bars not cached — no read", "dist_text": None}


def test_negative_block_survives_junk():
    for junk in (None, [], "x"):
        b = MS.block(junk)
        assert [r["text"] for r in b["rows"]] == [MS.WORD_NONE.format(sym=s) for s in LC.LUK_INDEX_SYMBOLS]


def test_negative_a_steep_extension_is_still_only_a_word():
    """His 2% remark is an example: a QQQ 5% over its 9 EMA reads WORD_OVER — nothing turns into a gate."""
    b = MS.block({"QQQ": {"ema9": 100.0, "ema21": 95.0, "close": 105.0}})
    assert b["rows"][0]["text"] == "QQQ: 9 EMA over 21"
    assert set(b) == {"title", "rows", "note"}


def test_the_note_says_never_a_gate_and_names_the_example():
    assert "never a gate" in MS.NOTE and "HIS CALL #8" in MS.NOTE and "not a threshold" in MS.NOTE


def test_no_threshold_number_is_typed_in_the_module():
    tree = ast.parse(pathlib.Path(MS.__file__).read_text(encoding="utf-8"))
    nums = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool)}
    assert nums <= {0, 1.0, 100.0}                                   # units only
    assert not [n for n in dir(MS) if "THRESHOLD" in n.upper()]


def test_no_b_word_no_edge():
    for s in (MS.WORD_UNDER, MS.WORD_OVER, MS.WORD_NONE, MS.DIST_TEXT, MS.NOTE, MS.TITLE):
        assert not B_WORD.search(s) and not EDGE.search(s)
