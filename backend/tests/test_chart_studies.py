"""AMD / Fibonacci / mean-reversion chart overlays (Ajay 2026-09-12).

"I wanna be able to toggle AMD ... and Fibonacci", "Also mean reversion please
on 1 year charts", then "Basically any chart time frame add this newly please".

ALL THREE ARE UNCITED AND UNMEASURED and every one of them gates nothing. The
tests that matter most here are therefore the NEGATIVES — the ways each could
quietly draw a level that is not there.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from supply_demand import amd as A
from supply_demand import fib as F
from supply_demand import meanrev as M
from daytrading import amd_sessions as S


def frame(close, hi=None, lo=None, index=None):
    c = list(close)
    return pd.DataFrame({"high": hi or [x * 1.005 for x in c],
                         "low": lo or [x * 0.995 for x in c],
                         "close": c}, index=index)


def amd_frame():
    """A base, a raid that CLOSES back inside it, then the markup."""
    c = [100 + (i % 3) * 0.4 for i in range(20)] + [100.1, 101.8, 103, 106, 109]
    hi = [x + 0.5 for x in c]
    lo = [x - 0.5 for x in c]
    lo[20] = 96.0          # the wick takes the stops under the base
    hi[20] = 100.6         # ...and the bar closes at 100.1, back inside
    return frame(c, hi, lo)


# ------------------------------------------------------------------ AMD daily
def test_the_three_phases_are_reached_in_order():
    df = amd_frame()
    assert A.chart_overlay(df.iloc[:20].reset_index(drop=True))["phase"] == "accumulation"
    assert A.chart_overlay(df.iloc[:21].reset_index(drop=True))["phase"] == "manipulation"
    assert A.chart_overlay(df)["phase"] == "distribution"


def test_a_close_BEYOND_the_edge_is_a_breakout_not_a_raid():
    """The entire test, and the one that separates AMD from a poke. A bar that
    closes outside the base is an accepted break and means the opposite."""
    c = [100 + (i % 3) * 0.4 for i in range(20)] + [97.0, 96.0, 95.0]
    hi = [x + 0.5 for x in c]
    lo = [x - 0.5 for x in c]
    lo[20] = 96.0
    out = A.chart_overlay(frame(c, hi, lo))
    assert out["phase"] != "manipulation"
    assert not any("raid" in l["label"] for l in out["lines"])


def test_the_base_does_not_swallow_its_own_raid_and_markup():
    """REGRESSION. The first version measured tightness against a 14-period ATR
    of the WHOLE frame, which the markup inflates — so the test meant to prove
    the base was tight was loosened by the move that followed it, and the
    'base' spanned the raid and the markup together. Tightness is now measured
    against the MEDIAN true range of the window's own bars, which one outlier
    bar cannot drag upward."""
    df = amd_frame()
    band = A.chart_overlay(df)["bands"][0]
    assert band["lo"] > 99.0, "the base must not reach down to the 96.00 raid"
    assert band["hi"] < 102.0, "the base must not reach up into the markup"
    cyc = A.find_cycle(df)
    assert cyc["accumulation"]["end"] < cyc["manipulation"]["idx"]


def test_a_bigger_markup_cannot_widen_the_base():
    """A base is history: adding bars AFTER it must not move it.

    This is a genuine invariant and it is worth holding. It is NOT, however,
    evidence for the choice of tightness statistic — mutation-tested
    2026-09-12, it passes with a whole-frame ATR and with a mean true range
    too. The docstring in amd.find_base says so; see the note there before
    assuming this suite protects that choice.

    (An earlier version asserted `mean(TR) > median(TR)` on the fixture — a
    property of the DATA, not of the code, which proved nothing at all.)"""
    df = amd_frame()
    base_band = A.chart_overlay(df)["bands"][0]
    # The extension must carry its OWN high/low. Deriving them from close would
    # overwrite the raid wick at bar 20 and the frame would no longer contain
    # the cycle this test is about.
    add = [140.0, 180.0, 240.0, 300.0]
    huge = pd.DataFrame({"high": list(df["high"]) + add,
                         "low": list(df["low"]) + add,
                         "close": list(df["close"]) + add})
    after = A.chart_overlay(huge)["bands"][0]
    assert (round(after["lo"], 2), round(after["hi"], 2)) == \
           (round(base_band["lo"], 2), round(base_band["hi"], 2))


def test_NEGATIVE_a_trending_frame_has_no_base_and_draws_nothing():
    out = A.chart_overlay(frame(list(np.linspace(50, 150, 120))))
    assert out["phase"] is None and out["bands"] == [] and out["lines"] == []


def test_NEGATIVE_too_few_bars_is_None_never_an_invented_band():
    assert A.chart_overlay(frame([100, 101, 102]))["bands"] == []
    assert A.find_cycle(None) is None


def test_the_bearish_mirror_works_on_an_inverted_series():
    df = amd_frame()
    inv = pd.DataFrame({"high": -df["low"], "low": -df["high"], "close": -df["close"]})
    assert A.chart_overlay(inv, direction="bearish")["phase"] == "distribution"


def test_amd_is_uncited_and_says_so():
    assert A.CITED is False and "no cited source" in A.SOURCE_NOTE


# ------------------------------------------------------------------ Fibonacci
def up_leg():
    return frame(list(np.linspace(100, 60, 20)) + list(np.linspace(60, 140, 20))
                 + list(np.linspace(140, 120, 8)))


def test_the_six_levels_are_the_ones_he_chose():
    got = [l["ratio"] for l in F.levels(up_leg())]
    assert sorted(got) == sorted(list(F.RETRACEMENTS) + list(F.EXTENSIONS))
    assert F.RETRACEMENTS == (0.382, 0.5, 0.618, 0.786)
    assert F.EXTENSIONS == (1.272, 1.618)


def test_retracements_sit_INSIDE_the_leg_and_extensions_BEYOND_it():
    leg = F.last_swing(up_leg())
    lo, hi = min(leg["a"], leg["b"]), max(leg["a"], leg["b"])
    for lv in F.levels(up_leg()):
        if lv["kind"] == "retracement":
            assert lo <= lv["price"] <= hi, lv
        else:
            assert lv["price"] > hi, lv


def test_the_golden_pocket_is_marked():
    pocket = {l["ratio"] for l in F.levels(up_leg()) if l["pocket"]}
    assert pocket == {0.618, 0.786}


def test_NEGATIVE_a_four_bar_wiggle_never_anchors_anything():
    """Without the size floor the anchor moves every session and the overlay
    becomes noise — the single most common way this feature turns useless."""
    rng = np.random.default_rng(3)
    flat = frame(list(100 + rng.normal(0, 0.05, 120)))
    assert F.last_swing(flat) is None and F.levels(flat) == []


def test_NEGATIVE_fib_lines_never_borrow_a_trade_tone():
    """Tone 'fib' keeps them on their own checkbox. Reusing 'buy'/'target'
    would fold an uncited level into the Trade-lines toggle and make it read
    as an instruction."""
    assert {l["tone"] for l in F.chart_lines(up_leg())} == {"fib"}


def test_fib_is_uncited_and_says_so():
    assert F.CITED is False and "never measured forward" in F.SOURCE_NOTE


# ------------------------------------------------------------- mean reversion
def test_the_channel_is_sloped_so_a_leader_is_not_permanently_rich():
    """The reason this is a regression fit and not a flat average: a name up
    100% on the year sits above its flat mean every single day."""
    rng = np.random.default_rng(7)
    up = frame(list(np.linspace(50, 150, 252) + rng.normal(0, 3, 252)))
    r = M.reading(up)
    assert r["trend"] == "rising" and r["state"] == "in range"
    # The flat mean parks the same name near the TOP of its own channel all
    # year: for a steady ramp the last bar sits ~1.7 sigma above a flat average
    # (uniform dispersion), against ~0 for the fit that removed the drift.
    flat = M.reading(up, sloped=False)
    assert flat["z"] > 1.5
    assert flat["z"] - r["z"] > 1.5
    assert flat["mean"] < r["mean"] * 0.75        # and it is anchored far below


def test_NEGATIVE_a_near_zero_sigma_reports_no_stretch():
    """REGRESSION. A perfectly straight series has residuals at float noise, so
    sigma is ~1e-14 and every z became astronomical — the channel called a name
    that had not moved "stretched high"."""
    r = M.reading(frame(list(np.linspace(50, 150, 252))))
    assert r["z"] == 0.0 and r["state"] == "in range"


def test_a_spike_reads_stretched_high():
    df = frame(list(np.linspace(50, 150, 251)) + [185.0])
    assert M.reading(df)["state"] == "stretched high"
    assert M.reading(df)["z"] > M.STRETCHED_SIGMA


def test_the_window_is_whatever_it_is_handed_not_a_fixed_year():
    """Ajay: "Basically any chart time frame add this newly please"."""
    big = frame(list(np.linspace(50, 150, 500)))
    assert M.fit(big)["n"] == 500
    assert M.fit(big.iloc[-120:])["n"] == 120


def test_NEGATIVE_too_few_bars_draws_nothing():
    assert M.fit(frame(list(np.linspace(1, 2, 10)))) is None
    assert M.chart_lines(frame(list(np.linspace(1, 2, 10)))) == []


def test_NEGATIVE_a_nan_close_cannot_poison_the_fit():
    c = list(np.linspace(50, 150, 200))
    c[40] = float("nan")
    f = M.fit(frame(c))
    assert f is not None and f["sigma"] == f["sigma"] and f["n"] == 199


def test_meanrev_is_uncited_and_sigma_is_not_a_probability():
    assert M.CITED is False and "NOT a probability" in M.SOURCE_NOTE


# ----------------------------------------------------------- session AMD
def session_frame():
    idx = pd.date_range("2026-09-11 08:00", periods=720, freq="1min", tz="UTC")
    c = []
    for i in range(720):
        if i < 240:
            c.append(100 + (i % 5) * 0.1)          # 04:00-08:00 ET accumulation
        elif i < 345:
            c.append(99.0 if i < 300 else 100.2)   # judas down, then reclaimed
        else:
            c.append(100.5 + (i - 345) * 0.01)     # NY markup
    df = frame(c, [x + 0.1 for x in c], [x - 0.1 for x in c], index=idx)
    df.loc[df.index[280], "low"] = 98.5
    return df


def test_the_session_cycle_finds_all_three_windows():
    o = S.chart_overlay(session_frame())
    assert o["phase"] == "distribution" and o["direction"] == "up"
    assert any("judas" in l["label"] for l in o["lines"])


def test_the_asian_range_DEVIATION_reaches_the_payload_not_just_the_docstring():
    """The app caches 04:00-20:00 ET only, so the canonical 19:00-00:00 ET
    Asian range does not exist in the data. Drawing one would be an invention;
    saying so only in a docstring would hide it from him."""
    o = S.chart_overlay(session_frame())
    assert "NOT the canonical" in o["note"] and "04:00-08:00" in o["note"]
    assert S.ACCUMULATION_WINDOW[0].hour == 4


def test_NEGATIVE_a_day_with_no_premarket_bars_draws_nothing():
    idx = pd.date_range("2026-09-11 14:00", periods=120, freq="1min", tz="UTC")
    assert S.session_cycle(frame(list(np.linspace(100, 101, 120)), index=idx)) is None


def test_NEGATIVE_a_two_sided_raid_claims_no_direction():
    """A window that swept BOTH edges has no thesis and must not invent one."""
    df = session_frame()
    df.loc[df.index[290], "high"] = 108.0
    d = S.session_cycle(df)
    assert d["manipulation"]["side"] == "both"
    assert d["distribution"]["direction"] is None


def test_both_amd_modules_share_one_kind_so_ONE_checkbox_governs_both():
    daily = A.chart_overlay(amd_frame())
    sess = S.chart_overlay(session_frame())
    assert daily["bands"][0]["kind"] == sess["bands"][0]["kind"] == "amd_accumulation"
    assert {l["tone"] for l in daily["lines"] + sess["lines"]} == {"amd"}
