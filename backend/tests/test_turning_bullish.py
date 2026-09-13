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
    assert v["grade"] == "none" and v["turning"] is False


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
    """SOURCE GUARD. 3 is not a taste call: at 10 the state fired on 1,212 of
    2,669 live names (45%). Anyone widening it re-creates a board that
    describes the market instead of selecting from it."""
    assert TB.MAX_RAID_BARS_AGO == 3
    src = open(TB.__file__).read()
    assert "1,212" in src and "45%" in src
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
    BACK INVERTED ON THEIR OWN CLAIM. A future edit that softens these modules
    into something that reads like a signal has to delete these numbers first,
    and this test makes that a deliberate act rather than a drift.
    """
    src = open(TB.__file__).read()
    assert "INVERTED" in src
    assert "-0.33pp" in src or "\u22120.33pp" in src or "−0.33pp" in src
    assert "42.7% vs 51.6%" in src
    assert "14.8pp" in src


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
    for kind in ("keltner", "amd"):
        note = B._turning_note(kind, 100, 2000, 5.0)
        assert note.startswith("MEASURED 2026-09-13 AND THE CLAIM IS INVERTED")
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
