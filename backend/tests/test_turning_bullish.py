"""Turning Bullish — the KC Coiled and AMD Raided tabs (Ajay 2026-09-13).

*"I need two tabs in chart maps for me to look at where stocks are bullish in
the recent 6 months where they are turning bullish"* and *"give me a Kelner
base verdict and AMD based verdict of stocks when I check those boxes in the
charts as well"*.

NEITHER STUDY IS CITED AND NEITHER GATES ANYTHING, so the tests that earn their
keep are the NEGATIVES: the ways a board about "turning bullish" could quietly
say a name is turning when it is not, or draw a channel where none was.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from supply_demand import keltner as KC
from supply_demand import turning_bullish as TB


def frame(close, hi=None, lo=None, index=None):
    c = [float(x) for x in close]
    return pd.DataFrame({"high": hi or [x * 1.01 for x in c],
                         "low": lo or [x * 0.99 for x in c],
                         "close": c}, index=index)


def dated(close, hi=None, lo=None, start="2026-01-01"):
    idx = pd.date_range(start, periods=len(close), freq="D")
    return frame(close, hi, lo, index=idx)


def coiled_frame():
    """A long rise, then a tight drift near the top: EMA rising, price in the
    upper half, and the Bollinger band squeezed inside the Keltner one."""
    rise = [100 + i * 1.2 for i in range(80)]
    tight = [rise[-1] + (i % 2) * 0.05 for i in range(30)]
    c = rise + tight
    return frame(c, [x * 1.002 for x in c], [x * 0.998 for x in c])


# ─────────────────────────────────────────── Keltner verdict
def test_coiled_up_needs_ALL_THREE_and_the_grade_says_which_it_got():
    v = TB.keltner_verdict(coiled_frame())
    assert v["grade"] == "coiled_up" and v["turning"] is True
    assert v["squeeze"] or v["squeeze_released"]
    assert v["position"] >= TB.COILED_MIN_POSITION
    assert v["mid_rising"] is True


def test_NEGATIVE_a_squeeze_in_the_LOWER_half_is_not_turning_bullish():
    """The whole point of the module's own warning: compression is not a
    direction. A tight drift at the BOTTOM of the channel is the same squeeze
    and must never grade as turning up."""
    fall = [200 - i * 1.2 for i in range(80)]
    tight = [fall[-1] - (i % 2) * 0.05 for i in range(30)]
    c = fall + tight
    v = TB.keltner_verdict(frame(c, [x * 1.002 for x in c], [x * 0.998 for x in c]))
    assert v["grade"] != "coiled_up" and v["turning"] is False


def test_NEGATIVE_a_squeeze_with_a_FALLING_midline_is_not_turning_bullish():
    """Upper half + squeezed, but the EMA is lower than it was — the name is
    rolling over inside its own channel, which is not a turn up."""
    c = [100 + i * 1.5 for i in range(70)] + [205 - i * 0.9 for i in range(40)]
    v = TB.keltner_verdict(frame(c, [x * 1.002 for x in c], [x * 0.998 for x in c]))
    assert v["mid_rising"] is False
    assert v["grade"] != "coiled_up"


def test_NEGATIVE_mid_rising_is_None_not_False_when_history_is_short():
    """'We cannot tell' must never render as 'no'. A False here would let a
    name with 25 bars of life be graded as definitely-not-rising, and the
    inverse mistake (None read as rising) would put it on the board."""
    c = [100 + i for i in range(25)]
    assert TB._mid_rising(frame(c)) is None


def test_NEGATIVE_an_unmeasurable_channel_says_unknown_not_lower_half():
    """THE DEFECT A REVIEW CAUGHT 2026-09-13. `position` is None when the
    channel has no span (ATR collapsed to zero — a halted or one-price name),
    and the old chain fell through every branch to the CONCRETE string
    "lower half". An unknown was rendering as a definite state."""
    flat = [50.0] * 80
    r = KC.reading(frame(flat, flat, flat))
    if r is not None:                      # a zero-ATR frame may not read at all
        if r["position"] is None:
            assert r["where"] == "unknown"
    v = TB.keltner_verdict(frame(flat, flat, flat))
    if v is not None and v["position"] is None:
        assert v["grade"] == "none" and v["turning"] is False


# ─────────────────────────────────────────── AMD verdict
def amd_raid_frame(bars_since_raid: int):
    """A base, a wick through its low that CLOSES back inside, then `n` quiet
    bars after it — the knob the recency bound is tested with."""
    c = [100 + (i % 3) * 0.4 for i in range(24)]
    hi = [x + 0.5 for x in c]
    lo = [x - 0.5 for x in c]
    c.append(100.1); hi.append(100.6); lo.append(96.0)      # the raid
    for i in range(bars_since_raid):
        c.append(100.2 + (i % 2) * 0.1)
        hi.append(c[-1] + 0.3)
        lo.append(c[-1] - 0.3)
    return frame(c, hi, lo)


def test_raided_is_the_modules_own_manipulation_phase_not_a_new_threshold():
    v = TB.amd_verdict(amd_raid_frame(1))
    assert v["phase"] == "manipulation"
    assert v["grade"] == "raided" and v["turning"] is True
    assert v["raid_bars_ago"] == 1


def test_NEGATIVE_a_STALE_raid_is_not_turning():
    """He asked for TURNING. A sweep older than the bound has had its chance,
    and grading it 'raided' is how a board about a turn fills with old news."""
    v = TB.amd_verdict(amd_raid_frame(TB.MAX_RAID_BARS_AGO + 4))
    assert v["phase"] == "manipulation"
    # 2026-09-14: the stale raid is NAMED rather than graded `none` — it used
    # to print "AMD no cycle · 7d ago", a sentence at war with itself.
    assert v["grade"] == "stale" and v["turning"] is False
    text, tone = TB.verdict_text("amd", v)
    assert text.startswith("AMD raid stale") and "d ago" in text and tone == "muted"


def test_NEGATIVE_a_CLOSE_beyond_the_base_low_is_a_breakdown_not_a_raid():
    """Identical to the AMD module's own rule and restated here because this
    board would otherwise list every name that merely traded lower."""
    c = [100 + (i % 3) * 0.4 for i in range(24)] + [97.0, 96.0, 95.5]
    hi = [x + 0.5 for x in c]
    lo = [x - 0.5 for x in c]
    lo[24] = 96.0
    v = TB.amd_verdict(frame(c, hi, lo))
    assert v is None or v["grade"] != "raided"


def test_the_recency_bound_is_3_and_the_reason_is_in_the_source():
    """SOURCE GUARD. 3 is not a taste call: at 10 the state fired on 759 of
    3,634 live names (21%; 45% on 2026-09-13 before the detector could FAIL a
    cycle). Anyone widening it re-creates a board that describes the market
    instead of selecting from it."""
    assert TB.MAX_RAID_BARS_AGO == 3
    src = open(TB.__file__).read()
    assert "759 of 3,634" in src and "21%" in src
    assert "758 of 3,633" not in src            # the superseded first re-run
    assert TB.WINDOW_SESSIONS == 126


# ─────────────────────────────────────────── the sentences
def test_verdict_text_is_ONE_helper_so_board_and_chart_cannot_disagree():
    v = TB.keltner_verdict(coiled_frame())
    text, tone = TB.verdict_text("keltner", v)
    assert text.startswith("KC coiled up") and tone == "good"
    a = TB.amd_verdict(amd_raid_frame(1))
    ta, tone_a = TB.verdict_text("amd", a)
    assert ta == "AMD raided · 1d ago" and tone_a == "good"


def test_NEGATIVE_a_missing_verdict_produces_NO_badge_not_an_empty_one():
    assert TB.verdict_text("keltner", None) == ("", "muted")
    assert TB.verdict_text("amd", {}) [0] == "AMD no cycle"


# ───────────────────────────────── the SHORT form (Ajay 2026-09-22)
#
# *"last column is hidded"* — the 🔥 Hottest board's 🌀 AMD column was clipped
# off the right edge, and every one of its 1,922 visible cells opened with the
# literal "AMD ", four characters repeating the column header. `verdict_short`
# serves the same sentence without that prefix. It is the SAME table and the
# SAME age rule, so these tests exist to prove there is no second wording
# engine hiding behind the new name.
#
# The long form is what the hover and the 🌀 AMD tab read, so the FIRST test
# here pins it byte-for-byte. If a refactor for the short's sake moves a
# character of the long form, this goes red before anything reaches a board.

# Every AMD sentence the engine can build. Typed out on purpose: derive them
# and the test proves only that the code agrees with itself.
AMD_SENTENCES = [
    ({"grade": "marked_up"},                        "AMD marked up",              "marked up"),
    ({"grade": "marked_up", "bars_ago": 124},       "AMD marked up · 124d ago",   "marked up · 124d ago"),
    ({"grade": "marked_up", "bars_ago": 0},         "AMD marked up · today",      "marked up · today"),
    ({"grade": "raided"},                           "AMD raided",                 "raided"),
    ({"grade": "raided", "raid_bars_ago": 2},       "AMD raided · 2d ago",        "raided · 2d ago"),
    ({"grade": "raided", "raid_bars_ago": 0},       "AMD raided · today",         "raided · today"),
    ({"grade": "stale"},                            "AMD raid stale",             "raid stale"),
    ({"grade": "stale", "raid_bars_ago": 19},       "AMD raid stale · 19d ago",   "raid stale · 19d ago"),
    ({"grade": "failed"},                           "AMD base failed",            "base failed"),
    ({"grade": "failed", "failed_bars_ago": 367},   "AMD base failed · 367d ago", "base failed · 367d ago"),
    ({"grade": "basing"},                           "AMD basing",                 "basing"),
    # a bare base and "no cycle" carry NO age even when the dict holds one
    ({"grade": "basing", "bars_ago": 4},            "AMD basing",                 "basing"),
    ({"grade": "none"},                             "AMD no cycle",               "no cycle"),
    ({"grade": "none", "bars_ago": 16},             "AMD no cycle",               "no cycle"),
]

KC_SENTENCES = [
    ({"grade": "coiled_up"},                            "KC coiled up"),
    ({"grade": "coiled_up", "squeeze": True, "squeeze_bars": 12},
     "KC coiled up · squeeze 12b"),
    ({"grade": "coiled_up", "squeeze": True, "squeeze_bars": 12, "squeeze_ratio": 0.63},
     "KC coiled up · squeeze 12b · 0.63× wide"),
    ({"grade": "breaking_up", "squeeze_released": True},
     "KC breaking up · squeeze just released"),
    ({"grade": "upper_half"},                           "KC upper half"),
    ({"grade": "lower_half"},                           "KC lower half"),
    ({"grade": "below_band"},                           "KC below the band"),
    ({"grade": "none"},                                 "KC no read"),
]


@pytest.mark.parametrize("v,long_,_short", AMD_SENTENCES)
def test_the_LONG_AMD_form_is_BYTE_FOR_BYTE_what_it_always_was(v, long_, _short):
    assert TB.verdict_text("amd", v)[0] == long_


@pytest.mark.parametrize("v,long_", KC_SENTENCES)
def test_the_LONG_KELTNER_form_is_BYTE_FOR_BYTE_what_it_always_was(v, long_):
    assert TB.verdict_text("keltner", v)[0] == long_


@pytest.mark.parametrize("v,long_,short", AMD_SENTENCES)
def test_the_SHORT_form_is_the_long_one_without_the_header_s_own_word(v, long_, short):
    s, tone = TB.verdict_short("amd", v)
    assert s == short
    # same tone, always — the short is a wording change, not a second read
    assert tone == TB.verdict_text("amd", v)[1]
    assert long_ == "AMD " + s


def test_EVERY_grade_has_a_short_and_it_comes_from_the_ONE_table():
    """The guard the ask asked for: a grade added to `AMD_GRADES` without a
    row in `AMD_TEXT` fails HERE, before it can reach a board wearing the
    fallback's words."""
    assert set(TB.AMD_GRADES) <= set(TB.AMD_TEXT), "a grade with no wording"
    for g in TB.AMD_GRADES:
        label = TB.grade_label("amd", g)
        assert label, g
        # the ONE table, not a second one kept in step by hand
        assert TB.AMD_TEXT[g][0] == "AMD " + label
        assert TB.verdict_short("amd", {"grade": g})[0] == label


def test_NEGATIVE_the_grade_label_check_above_has_TEETH():
    """`grade_label` returns "" for a grade the table does not hold — which is
    exactly what the assertion above is testing for. Prove it can go false."""
    assert TB.grade_label("amd", "a_grade_nobody_tabled") == ""
    assert TB.grade_label("amd", None) == ""
    assert TB.grade_label("keltner", "a_grade_nobody_tabled") == ""


def test_the_short_is_STRICTLY_shorter_than_the_long_for_every_grade():
    """The whole point is width. A short that saved nothing would be a second
    wording table with no reason to exist."""
    for g in TB.AMD_GRADES:
        v = {"grade": g, "raid_bars_ago": 2, "failed_bars_ago": 2, "bars_ago": 2}
        long_ = TB.verdict_text("amd", v)[0]
        short = TB.verdict_short("amd", v)[0]
        assert len(short) < len(long_), g
        assert len(long_) - len(short) == len("AMD "), g


def test_NEGATIVE_the_short_introduces_NO_vocabulary_the_long_form_lacks():
    """A short is allowed to drop a word. It is never allowed to invent one —
    that is how two wording tables start."""
    for v, long_, short in AMD_SENTENCES:
        assert "AMD" not in short, short
        for word in short.split():
            assert word in long_.split(), (word, long_)
    for v, long_ in KC_SENTENCES:
        short = TB.verdict_short("keltner", v)[0]
        assert "KC" not in short.split(), short
        for word in short.split():
            assert word in long_.split(), (word, long_)


def test_the_short_takes_its_AGE_from_the_SAME_rule_as_the_long_form():
    """Which age belongs beside which word is decided ONCE, in `_suffix`. Hand
    every grade a dict carrying ALL THREE age fields at once: whichever one the
    long form picks, the short must pick the same, and the two grades that
    carry no age must still carry none."""
    for g in TB.AMD_GRADES:
        v = {"grade": g, "raid_bars_ago": 7, "failed_bars_ago": 9, "bars_ago": 11}
        long_ = TB.verdict_text("amd", v)[0]
        short = TB.verdict_short("amd", v)[0]
        assert short == long_[len("AMD "):], g
        if g in ("basing", "none"):
            assert "d ago" not in short and "today" not in short, g
        else:
            assert "d ago" in short, g


def test_NEGATIVE_a_missing_verdict_has_NO_short_either():
    for junk in (None, {}, "raided", 3, []):
        short, tone = TB.verdict_short("amd", junk)
        long_, _ = TB.verdict_text("amd", junk)
        if isinstance(junk, dict):
            # {} is a real dict with no grade: it takes the table's fallback,
            # the SAME one the long form takes — never a different word.
            assert short == "no cycle" and long_ == "AMD no cycle"
        else:
            assert short == "" and long_ == "" and tone == "muted"


def test_an_UNTABLED_grade_takes_the_SAME_fallback_in_both_forms():
    """`verdict_text` does `table.get(grade) or table["none"]`. If the short
    fell back differently the two forms would name the same row differently —
    and `hottest_amd.read_one` gates `known` on membership precisely because
    that fallback is a real read's words."""
    v = {"grade": "wat"}
    assert TB.verdict_text("amd", v) == ("AMD no cycle", "muted")
    assert TB.verdict_short("amd", v) == ("no cycle", "muted")
    assert TB.verdict_text("keltner", v) == ("KC no read", "muted")
    assert TB.verdict_short("keltner", v) == ("no read", "muted")


# ─────────────────────────────────────────── the channel as a CURVE
def test_the_channel_BENDS_because_an_EMA_and_an_ATR_both_move():
    """AJAY 2026-09-13 (MU): "I was hoping to see the KC bands like this but it
    should flat horizontal." Three scalars render as horizontal levels; the
    series must actually vary, or the fix is cosmetic."""
    ser = KC.channel_series(dated([100 + i * 1.3 for i in range(120)]))
    mids = [v for v in ser["mid"] if v is not None]
    assert len(set(mids)) > 50
    assert mids[-1] > mids[0]


def test_the_series_matches_the_SCALAR_reading_at_the_last_bar():
    """The curve and the number in the gutter are the same channel. If these
    ever drift, one of the two drawings is lying about the other."""
    df = dated([100 + i * 1.3 + (i % 5) for i in range(140)])
    ser, ch = KC.channel_series(df), KC.channel(df)
    for k in ("upper", "mid", "lower"):
        assert ser[k][-1] == pytest.approx(ch[k], abs=1e-3)


def test_NEGATIVE_warm_up_bars_are_None_and_never_a_guess():
    ser = KC.channel_series(dated([100 + i for i in range(120)]))
    assert ser["mid"][0] is None
    assert len(ser["mid"]) == len(ser["dates"]) == 120


def test_NEGATIVE_a_ZERO_RANGE_frame_yields_no_series_at_all():
    """One price, no range — a halted name. ATR is zero, the channel has no
    span, and every slot must be empty rather than three coincident lines
    drawn on top of the close as if they were a channel."""
    flat = [50.0] * 90
    idx = pd.date_range("2026-01-01", periods=90, freq="D")
    df = frame(flat, flat, flat, index=idx)
    assert KC.channel_series(df) is None


def test_a_flat_CLOSE_with_a_real_range_still_has_a_channel():
    """The mirror, so the guard above cannot be over-tightened into hiding
    ordinary quiet names: closes can repeat while the bars still have range,
    and that is a legitimate (very narrow) channel."""
    ser = KC.channel_series(dated([50.0] * 90))
    assert ser is not None and any(v is not None for v in ser["mid"])


def test_curves_align_BY_DATE_so_a_live_bar_cannot_shift_the_channel():
    """THE TRAP. Tile bars can carry today's extended-hours bar, which the
    cached frame the channel is computed from does not have. A positional tail
    would slide the whole channel one bar left and mis-state every value."""
    from chart_maps import board as B
    df = dated([100 + i * 1.1 for i in range(120)], start="2026-01-01")
    dates = [str(d.date()) for d in df.index]
    tile = {"bars": [{"t": d, "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}
                     for d in dates[-30:]] + [{"t": "2099-01-01", "o": 1, "h": 1,
                                               "l": 1, "c": 1, "v": 1}]}
    B._keltner_curves(tile, df)
    mid = next(c for c in tile["curves"] if c["label"] == "KC mid")
    assert len(mid["values"]) == 31
    assert mid["values"][-1] is None                  # the unknown live bar
    ser = KC.channel_series(df)
    assert mid["values"][-2] == ser["mid"][-1]        # ...and nothing shifted


# ─────────────────────────────────────────── the studies gate
def test_NEGATIVE_studies_is_gated_on_True_not_on_truthiness():
    """SOURCE GUARD, and it has a history: FastAPI resolves `Query(...)`
    defaults at REQUEST time, so every direct in-container call hands `board()`
    a Query OBJECT, which is truthy. That bug shipped twice on the demand board
    (2026-08-14) and `board()` was the one door still open on 2026-09-13."""
    src = open(__import__("chart_maps.board", fromlist=["x"]).__file__).read()
    assert "if studies is True:" in src
    assert "\n    if studies:\n" not in src


def test_the_verdict_is_read_BEFORE_the_zoom_cut():
    """A verdict that changes with the days dropdown is not a verdict. Pin the
    ORDER: verdicts first, the zoom slice after."""
    src = open(__import__("chart_maps.board", fromlist=["x"]).__file__).read()
    i_v = src.index("_attach_verdicts(t, df)")
    i_cut = src.index("df = df.iloc[-int(days):]")
    assert i_v < i_cut


def test_every_verdict_badge_carries_its_overlay_GROUP():
    """Without `group` the frontend cannot drop the SENTENCE when he unticks
    the family, and a chart would show a verdict for an overlay not drawn."""
    from chart_maps import board as B
    for kind, v in (("keltner", TB.keltner_verdict(coiled_frame())),
                    ("amd", TB.amd_verdict(amd_raid_frame(1)))):
        b = B._verdict_badges(kind, v)
        assert b and b[0]["group"] == kind and b[0]["text"]


def test_the_boards_are_UNCITED_and_say_so():
    """Guard the honesty, not just the arithmetic."""
    from supply_demand import amd as A
    assert KC.CITED is False and A.CITED is False
    src = open(TB.__file__).read()
    assert "+0.03R" in src and "cited" in src.lower()


def test_the_INVERTED_measurement_is_carried_in_the_source_not_just_the_page():
    """SOURCE GUARD, and the most important one in this file.

    Both reads were measured against a placebo on 2026-09-13 and BOTH CAME
    BACK INVERTED ON THEIR OWN CLAIM. AMD was re-measured on 2026-09-14 once
    the detector could FAIL a cycle: still inverted, smaller (51.9% vs 56.1%,
    −4.2pp), with the board's own 0-3 cut worse at −5.6pp.
    A future edit that softens these modules into something that reads like a
    signal has to delete these numbers first, and this test makes that a
    deliberate act rather than a drift.
    """
    src = open(TB.__file__).read()
    assert "INVERTED" in src
    assert "-0.55pp" in src or "\u22120.55pp" in src or "−0.55pp" in src
    assert "51.9% vs 56.1%" in src and "RE-MEASURED 2026-09-14" in src
    assert "42.7% vs 51.6%" not in src          # the old-detector number is gone
    assert "16.2pp" in src


def test_both_measurement_scripts_are_IN_THE_REPO_and_runnable():
    """His standing rule: a measured number on a board he trades ships with
    its re-runnable script and its CI, never as a bare point estimate. The
    board notes quote these two by path, so a missing file makes the page cite
    something that does not exist."""
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for name in ("turning_bullish_keltner_study.py", "turning_bullish_amd_study.py"):
        path = os.path.join(here, "scripts", name)
        assert os.path.exists(path), path
        head = open(path).read(4000)
        assert "INVERTED" in head and "docker compose exec" in head


def test_the_board_note_LEADS_with_the_measurement():
    """A note that explained the setup first and mentioned the study last
    would bury the only thing on the page that changes what he does."""
    from chart_maps import board as B
    for kind, verdict in (("keltner", "STILL INVERTED"), ("amd", "STILL INVERTED")):
        note = B._turning_note(kind, 100, 2000, 5.0)
        assert note.startswith("RE-MEASURED 2026-09-14")
        assert verdict in note[:120]                   # the verdict is in the first breath
        assert "95% CI" in note
        assert "backend/scripts/turning_bullish_" in note
        # the fire rate, always, next to any rate — his standing rule
        assert "100 of 2,000" in note


def test_NEGATIVE_the_board_payload_is_JSON_SERIALIZABLE():
    """CAUGHT IN THE CONTAINER 2026-09-13, one step before this shipped.

    `built_at` round-trips through Mongo, and pymongo hands BSON dates back as
    real `datetime` objects. `JSONResponse` calls `json.dumps`, which refuses
    them — so the tab would have answered 500, not a board with a missing
    field. Every board tab is served this way, so the guard belongs here.
    """
    import json
    from datetime import datetime, timezone
    assert TB._iso(None) is None
    assert TB._iso("2026-09-13T09:33:29") == "2026-09-13T09:33:29"
    iso = TB._iso(datetime(2026, 9, 13, 9, 33, tzinfo=timezone.utc))
    assert isinstance(iso, str) and iso.startswith("2026-09-13T09:33")
    json.dumps({"built_at": iso})       # the thing that actually blew up
