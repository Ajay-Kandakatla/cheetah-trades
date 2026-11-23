"""🔀 The 9 / 21 EMA blinker — THE engine read (ema_cross.blink_read / blink_from_bars), the words / counts module
(chart_maps.ema_blink) and the ℹ️ clause (SPEC blinker §3.1–§3.3, §3.8, WP-A tests (a)–(p), 2026-11-15).

Ajay, verbatim (2026-11-15): "On All of the charts and also the tabs I need a new blinker to show me EMA uptrends 9
crossing over 21 EMA please.." · "Yes and I need some sort of urgency or fast blink for the one are closer together than
approaching with sort also aligned with it" · "Or atleast closing in on other tabs for me". Information only, UNMEASURED.
"""
from __future__ import annotations

import ast
import json
import math
import pathlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps import ema_blink as EB
from chart_maps.gajjala import bars as GB
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ema_cross as EX

ET = ZoneInfo("America/New_York")
SRC_EB = pathlib.Path(EB.__file__).read_text(encoding="utf-8")
REPORT = pathlib.Path("/Users/ajay/clinet-test/eod-audits/research/2026-11-15_video_9x21_upcross/REPORT.md")


def _ts(n, day="2026-11-13", start_min=9 * 60 + 30, step=5):
    out = []
    for k in range(n):
        m = start_min + k * step
        out.append(f"{day} {m // 60:02d}:{m % 60:02d}")
    return out


def _et(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=ET)


# ── (a) / (b) crossed up ─────────────────────────────────────────────────────────────────────────────────────────
def test_a_cross_on_the_last_bar_is_fresh_with_closeness_0():
    fast = [None, 9.0, 9.5, 9.8, 10.2]
    slow = [None, 10.0, 10.0, 10.0, 10.0]
    ts = _ts(5)
    r = EX.blink_read(fast, slow, ts, [10.0] * 5)
    assert r["state"] == EX.BLINK_UP and r["tier"] == EX.TIER_FRESH and r["fresh"] is True
    assert r["closeness"] == 0 and r["bars_since_cross"] == 0 and r["cross_t"] == ts[4] == r["t"]
    b = EB.block(r, tf="5m")
    assert b["blink"] is True and b["text"] == f"● 9 EMA crossed over the 21 EMA on this bar ({ts[4][11:]} ET)"


def test_b_crossed_7_bars_ago_still_above_is_up_with_its_age():
    fast = [9.0] * 3 + [10.5 + 0.1 * k for k in range(8)]
    slow = [10.0] * 11
    ts = _ts(11)
    r = EX.blink_read(fast, slow, ts)
    assert r["state"] == EX.BLINK_UP and r["tier"] == EX.TIER_UP and r["fresh"] is False
    assert r["bars_since_cross"] == 7 and r["closeness"] == 7 and r["cross_t"] == ts[3]
    b = EB.block(r, tf="5m")
    assert b["text"] == f"● 9 EMA over the 21 EMA since {ts[3][11:]} ET · 7 bars"


def test_b2_a_cross_on_the_prior_date_keeps_its_date_same_date_prints_the_time():
    prior = _ts(3, day="2026-11-12", start_min=15 * 60 + 40)
    today = _ts(4, day="2026-11-13")
    ts = prior + today
    fast = [9.0, 10.5, 10.6, 10.7, 10.8, 10.9, 11.0]
    slow = [10.0] * 7
    b = EB.block(EX.blink_read(fast, slow, ts), tf="5m")
    assert b["cross_t"] == prior[1] and b["t"] == today[-1]
    assert f"since {prior[1]} ET · 5 bars" in b["text"]                     # "YYYY-MM-DD HH:MM ET"
    assert EB._when(prior[1], today[-1]) == f"{prior[1]} ET"
    assert EB._when(today[1], today[-1]) == f"{today[1][11:]} ET"            # same date → "HH:MM ET"
    assert EB._when("2026-11-12", "2026-11-13") == "2026-11-12"              # a daily stamp → the date
    assert EB._when(None, today[-1]) == EB.EARLIER_BAR


# ── (c) / (d) / (d2) closing in ──────────────────────────────────────────────────────────────────────────────────
def test_c_narrowing_gap_projected_2_bars_is_near():
    fast = [9.0, 9.2, 9.4, 9.6]                                             # gap −1.0 → −0.4 over L = 3: 0.2 / bar
    slow = [10.0] * 4
    r = EX.blink_read(fast, slow, _ts(4), [10.0] * 4)
    assert GC.BLINK_NARROW_BARS == 3
    assert r["state"] == EX.BLINK_IN and r["bars_to_cross"] == 2 and r["tier"] == EX.TIER_NEAR
    assert r["closeness"] == 2 and r["gap_pct"] == pytest.approx(4.0)
    b = EB.block(r, tf="5m")
    assert b["text"] == "◐ 9 EMA closing in on the 21 EMA · gap 4.00% · about 2 bars to the cross"


def test_d_projected_on_the_next_bar_is_imminent():
    fast = [9.0, 9.4, 9.7, 9.9]                                             # −1.0 → −0.1: 0.3 / bar → 1 bar
    r = EX.blink_read(fast, [10.0] * 4, _ts(4), [10.0] * 4)
    assert r["state"] == EX.BLINK_IN and r["tier"] == EX.TIER_IMMINENT and r["bars_to_cross"] == 1
    assert EB.block(r, tf="5m")["text"].endswith("could cross on the next bar")


def test_d_closing_tier_beyond_near():
    fast = [9.0, 9.02, 9.04, 9.06]                                          # −1.0 → −0.94: 0.02 / bar → 47 bars
    assert EX.blink_read(fast, [10.0] * 4)["state"] == EX.BLINK_NONE
    fast = [9.0, 9.1, 9.2, 9.3]                                             # −1.0 → −0.7: 0.1 / bar → 7 bars
    r = EX.blink_read(fast, [10.0] * 4)
    assert r["tier"] == EX.TIER_CLOSING and r["bars_to_cross"] == 7 and r["closeness"] == 7


def test_d2_gap_zero_is_imminent_with_closeness_1_never_0_never_crossed_up():
    fast = [9.0, 9.5, 9.8, 10.0]
    r = EX.blink_read(fast, [10.0] * 4, _ts(4), [10.0] * 4)
    assert r["above"] is False
    assert r["state"] == EX.BLINK_IN and r["tier"] == EX.TIER_IMMINENT
    assert r["bars_to_cross"] == 1 == r["closeness"] == GC.BLINK_IMMINENT_BARS
    assert r["closeness"] != 0 and r["state"] != EX.BLINK_UP
    assert EB.block(r, tf="5m")["gap_pct"] == 0.0


# ── NEGATIVES (e)–(i) ────────────────────────────────────────────────────────────────────────────────────────────
def test_e_NEGATIVE_projected_25_bars_is_not_closing_in():
    gap_then, rate = -1.0, 0.03                                             # −1.0 → −0.91 over 3: 0.03 / bar → 31
    fast = [10.0 + gap_then + rate * k for k in range(4)]
    assert EX.blink_read(fast, [10.0] * 4)["state"] == EX.BLINK_NONE
    # exactly 25 bars (> BLINK_MAX_BARS 24) → none; 24 → closing
    fast25 = [0.0, 0.0, 0.0, 0.0]
    slow = [2.5 + 0.3, 2.5 + 0.2, 2.5 + 0.1, 2.5]                           # gap −2.8 → −2.5: 0.1 / bar → 25 bars
    r = EX.blink_read(fast25, slow)
    assert GC.BLINK_MAX_BARS == 24 and r["state"] == EX.BLINK_NONE and r["tier"] is None and r["closeness"] is None
    slow24 = [2.4 + 0.3, 2.4 + 0.2, 2.4 + 0.1, 2.4]
    assert EX.blink_read(fast25, slow24)["bars_to_cross"] == 24


def test_f_NEGATIVE_under_and_widening_is_none():
    fast = [9.6, 9.4, 9.2, 9.0]
    r = EX.blink_read(fast, [10.0] * 4)
    assert r["state"] == EX.BLINK_NONE and r["tier"] is None and r["bars_to_cross"] is None
    assert EB.block(r, tf="5m")["blink"] is False and EB.block(r, tf="5m")["text"] is None
    assert EX.blink_read([9.0] * 4, [10.0] * 4)["state"] == EX.BLINK_NONE      # flat gap: not narrowing


def test_g_NEGATIVE_above_the_whole_frame_with_no_cross_is_none_above_true():
    r = EX.blink_read([11.0, 11.1, 11.2, 11.3], [10.0] * 4)
    assert r["state"] == EX.BLINK_NONE and r["above"] is True and r["cross_t"] is None
    assert EB.block(r, tf="5m")["above"] is True and EB.block(r, tf="5m")["blink"] is False


def test_h_up_max_bars_0_is_the_daily_rule():
    old = [9.0, 10.5, 10.6, 10.7]                                           # crossed 2 bars ago... (index 1 → i 3)
    r = EX.blink_read(old, [10.0] * 4, up_max_bars=0)
    assert r["bars_since_cross"] == 2 and r["state"] == EX.BLINK_NONE and r["tier"] is None
    fresh = [9.0, 9.2, 9.5, 10.5]
    r = EX.blink_read(fresh, [10.0] * 4, up_max_bars=GC.BLINK_DAILY_UP_MAX_BARS)
    assert r["state"] == EX.BLINK_UP and r["tier"] == EX.TIER_FRESH
    three = [9.0, 10.5, 10.6, 10.7, 10.8]
    assert EX.blink_read(three, [10.0] * 5, up_max_bars=0)["state"] == EX.BLINK_NONE
    assert EX.blink_read(three, [10.0] * 5)["state"] == EX.BLINK_UP          # Gajjala rule: no age cap


@pytest.mark.parametrize("fast,slow", [
    ([], []), (None, None), ([10.0], [9.0]), ([None, None, None], [None, None, None]),
    ([float("nan"), 9.0], [10.0, 10.0]), ([True, False, True], [1, 0, 1]), (["a", "b"], ["c", "d"]),
    ([None, 9.0, 9.1], [None, None, 10.0]), (5, 6), ("abc", "def"),
])
def test_i_NEGATIVE_junk_reads_none_and_never_raises(fast, slow):
    assert EX.blink_read(fast, slow) is None


def test_i_warmup_nones_are_skipped_and_ts_none_still_reads():
    fast = [None] * 20 + [9.0, 9.2, 9.4, 9.6]
    slow = [None] * 20 + [10.0] * 4
    r = EX.blink_read(fast, slow)
    assert r["state"] == EX.BLINK_IN and r["t"] is None and r["cross_t"] is None and r["i"] == 23
    assert EX.blink_read(fast, slow, ts=None, closes=None)["gap_pct"] is None
    # trailing None (a padded wide frame) → the last bar with both finite
    r2 = EX.blink_read(fast + [None], slow + [None])
    assert r2["i"] == 23
    # a non-finite lookback bar → none (not judgeable as narrowing)
    r3 = EX.blink_read([9.0, float("nan"), 9.2, 9.4, 9.6][1:] + [9.8], [10.0] * 5)
    assert r3 is None or r3["state"] in EX.BLINK_STATES
    assert EX.blink_read([None, 9.4, 9.6], [None, 10.0, 10.0])["state"] == EX.BLINK_NONE   # no bar L back


def test_i_NEGATIVE_block_from_curves_missing_or_ragged_is_none():
    bars = [{"t": t, "c": 10.0} for t in _ts(4)]
    curves = [{"tone": "ema9", "values": [9.0, 9.2, 9.4, 9.6]}, {"tone": "ema21", "values": [10.0] * 4}]
    assert EB.block_from_curves(curves, bars, tf="5m")["state"] == EX.BLINK_IN
    assert EB.block_from_curves(None, bars, tf="5m") is None
    assert EB.block_from_curves(curves, None, tf="5m") is None
    assert EB.block_from_curves(curves[:1], bars, tf="5m") is None
    assert EB.block_from_curves(curves, bars[:3], tf="5m") is None                  # ragged
    assert EB.block_from_curves("junk", {"x": 1}, tf="5m") is None
    no_c = [{"t": t} for t in _ts(4)]                                                # stamps only (the counts' shape)
    b = EB.block_from_curves(curves, no_c, tf="5m")
    assert b["state"] == EX.BLINK_IN and b["gap_pct"] is None and b["t"] == _ts(4)[-1]
    assert b["text"] == "◐ 9 EMA closing in on the 21 EMA · about 2 bars to the cross"     # no "gap None%"
    assert "None" not in json.dumps(b["text"])


# ── (j) / (j2) ONE EMA path + the daily live bar ─────────────────────────────────────────────────────────────────
def _daily(closes, start="2026-09-01"):
    days = pd.bdate_range(start, periods=len(closes))
    return [{"t": d.date().isoformat(), "c": c} for d, c in zip(days, closes)]


def test_j_blink_from_bars_equals_blink_read_over_the_house_ema():
    closes = [10 + math.sin(k / 4.0) * 2 + k * 0.03 for k in range(60)]
    bars = _daily(closes)
    s = pd.Series(closes)
    e9, e21 = GB._masked_ema(s, GC.EMA_FAST), GB._masked_ema(s, GC.EMA_SLOW)
    want = EX.blink_read(e9, e21, [b["t"] for b in bars], closes)
    assert EX.blink_from_bars(bars) == want and want is not None


def test_j_through_drops_every_bar_stamped_after_it():
    closes = [10 + k * 0.01 for k in range(40)]
    bars = _daily(closes)
    r = EX.blink_from_bars(bars, through=bars[-2]["t"])
    assert r["t"] == bars[-2]["t"] and r["i"] == len(bars) - 2
    assert EX.blink_from_bars(bars)["t"] == bars[-1]["t"]
    assert EX.blink_from_bars([]) is None and EX.blink_from_bars(None) is None
    assert EX.blink_from_bars(bars[:10]) is None                                   # under the 21 warm-up


def test_j_a_cross_only_the_live_bar_makes_is_not_reported_through_yesterday():
    closes = [20 - k * 0.1 for k in range(40)] + [30.0]                           # the last (live) bar crosses
    bars = _daily(closes)
    live = EX.blink_from_bars(bars, up_max_bars=0)
    assert live["state"] == EX.BLINK_UP and live["fresh"] is True
    closed = EX.blink_from_bars(bars, through=bars[-2]["t"], up_max_bars=0)
    assert closed["state"] != EX.BLINK_UP and closed["t"] == bars[-2]["t"]


def test_j2_daily_through_follows_the_house_close_clock():
    assert EB.daily_through(_et(2026, 11, 16, 11, 0)) == "2026-11-15"              # Monday RTH → drop today
    assert EB.daily_through(_et(2026, 11, 16, 16, 1)) is None                      # after the close → keep it
    assert EB.daily_through(_et(2026, 11, 16, 16, 0)) is None
    assert EB.daily_through(_et(2026, 11, 16, 8, 0)) == "2026-11-15"               # pre-market synthetic bar dropped
    assert EB.daily_through(_et(2026, 11, 27, 13, 1)) is None                      # HALF_DAYS: 13:00 close
    assert EB.daily_through(_et(2026, 11, 27, 12, 59)) == "2026-11-26"
    assert EB.daily_through(_et(2026, 11, 14, 10, 0)) == "2026-11-13"              # Saturday: harmless
    assert EB.daily_through(datetime(2026, 11, 16, 21, 5, tzinfo=timezone.utc)) is None     # 16:05 ET in UTC
    assert EB.daily_through(datetime(2026, 11, 16, 15, 0)) == "2026-11-15"         # naive = UTC (10:00 ET)


def test_j2_NEGATIVE_a_raising_calendar_drops_today(monkeypatch):
    import catalysts.medical.reaction as R
    monkeypatch.setattr(R, "is_market_day", lambda d: 1 / 0)
    assert EB.daily_through(_et(2026, 11, 16, 17, 0)) == "2026-11-15"


# ── (k) words ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_k_every_number_in_a_word_comes_from_gc_at_call_time(monkeypatch):
    monkeypatch.setattr(GC, "EMA_FAST", 8)
    monkeypatch.setattr(GC, "BLINK_NARROW_BARS", 5)
    monkeypatch.setattr(GC, "BLINK_MAX_BARS", 30)
    assert "8 EMA" in EB.rules_line() and "over 5 bars, projected within 30" in EB.rules_line()
    assert "8-over-21" in EB.info() and "smaller than 5 closed bars ago" in EB.info() and "30 bars at most" in EB.info()
    assert EB.title().startswith("🔀 8/21") and EB.sort_label() == "🔀 closest to the 8/21 cross"
    assert "8/21" in EB.order_text() and "8/21" in EB.sort_unavailable()
    r = EX.blink_read([9.0, 9.1, 9.2, 9.3, 9.4, 9.5], [10.0] * 6)          # L = 5 now: 0.1 / bar → 5 bars
    b = EB.block(r, tf="5m")
    assert r["bars_to_cross"] == 5 and b["fast"] == 8 and b["text"].startswith("◔ 8 EMA")
    assert EX.blink_read([9.0, 9.2, 9.4, 9.6], [10.0] * 4)["state"] == EX.BLINK_NONE   # no bar 5 back


def test_k_words_cite_the_report_verbatim_and_never_advise():
    info = EB.info()
    assert "2026-11-15" in info
    for frag in ("+36.6% mean ride", "38 video charts", "1,497 other", "lost 2.0% net", "won 27%",
                 "12 times per chart", "UNMEASURED", "not an entry", "Cheetah's definition, not Gajjala's"):
        assert frag in info, frag
    if REPORT.exists():
        rep = REPORT.read_text(encoding="utf-8")
        for n in ("+36.6%", "-2.0%", "win 27%", "1,497", "11.9 crosses per chart", "38 video charts"):
            assert n in rep, n
    assert len(EB.title()) <= 100
    words = [EB.info(), EB.title(), EB.sort_label(), EB.order_text(), EB.sort_unavailable(), EB.rules_line(),
             EB.SORT_DEFAULT_LABEL, *EB.TEXT.values(), EB.TAB_TEXT, EB.TAB_TEXT_ONE, EB.N_MEANS]
    for w in words:
        low = w.lower()
        assert "buy" not in low and "b" + "ounce" not in low and "@" not in w, w


def test_k_block_keys_and_nan_free():
    r = EX.blink_read([9.0, 9.2, 9.4, 9.6], [10.0] * 4, _ts(4), [float("nan")] * 4)
    b = EB.block(r, tf="5m")
    assert tuple(b) == EB.BLOCK_KEYS
    json.dumps(b, allow_nan=False)
    assert EB.block(None, tf="5m") is None and EB.block({"state": "junk"}, tf="5m") is None


# ── (l) / (m) THE order ──────────────────────────────────────────────────────────────────────────────────────────
def _tile(sym, state="none", tier=None, closeness=None, gap=None):
    return {"symbol": sym, "ema_blink": {"state": state, "tier": tier, "blink": state != "none",
                                          "closeness": closeness, "gap_pct": gap}}


def test_l_sort_key_blinking_first_then_tier_then_closeness_then_gap():
    tiles = [_tile("Q"), _tile("UP2", "crossed_up", "up", 2, 3.0), _tile("NEAR3", "closing_in", "near", 3, 1.0),
             _tile("FRESH", "crossed_up", "fresh", 0, 0.1), _tile("IMM", "closing_in", "imminent", 1, 0.5),
             _tile("UP1", "crossed_up", "up", 1, 9.0), _tile("NEAR2", "closing_in", "near", 2, 2.0),
             _tile("CL", "closing_in", "closing", 10, 4.0), {"symbol": "NOKEY"}]
    got = [t["symbol"] for t in sorted(tiles, key=EB.sort_key)]
    assert got == ["FRESH", "IMM", "NEAR2", "NEAR3", "CL", "UP1", "UP2", "Q", "NOKEY"]


def test_l_gap_zero_is_a_real_tie_break_not_unknown():
    a = _tile("A", "closing_in", "imminent", 1, 1.0)
    b = _tile("B", "closing_in", "imminent", 1, 0.0)
    c = _tile("C", "closing_in", "imminent", 1, None)
    assert [t["symbol"] for t in sorted([a, c, b], key=EB.sort_key)] == ["B", "A", "C"]


def test_l_NEGATIVE_twenty_non_blinking_tiles_keep_their_order_byte_for_byte():
    syms = ["ZZ", "AA", "MM", "BB", "YY", "CC", "XX", "DD", "WW", "EE", "VV", "FF", "UU", "GG", "TT", "HH", "SS",
            "II", "RR", "JJ"]
    tiles = []
    for k, s in enumerate(syms):
        t = _tile(s) if k % 3 else {"symbol": s, "ema_blink": None}
        if k % 4 == 0:
            t = {"symbol": s, "ema_blink": {"state": "none", "tier": None, "blink": False, "closeness": None,
                                            "gap_pct": 2.0, "above": True}}
        tiles.append(t)
    before = json.dumps(tiles)
    assert json.dumps(sorted(tiles, key=EB.sort_key)) == before
    assert len({EB.sort_key(t) for t in tiles}) == 1                                 # no symbol in the key
    assert EB.sort_key({"symbol": "AA"}) == (1, len(EX.TIERS), 0, math.inf)


def test_l_top_key_carries_the_symbol_tie_break_only():
    b = {"blink": True, "tier": "near", "closeness": 2, "gap_pct": 1.0}
    assert EB.top_key("AAA", b) < EB.top_key("BBB", b)
    assert EB.top_key("AAA", b)[:-1] == EB.sort_key({"ema_blink": b})


def test_m_tiers_order_is_one_axis_and_tab_tier_is_the_fastest():
    assert EX.TIERS == ("fresh", "imminent", "near", "closing", "up")
    assert [EX.tier_rank(t) for t in EX.TIERS] == [0, 1, 2, 3, 4]
    assert EX.tier_rank(None) == EX.tier_rank("junk") == len(EX.TIERS)
    blocks = [{"blink": True, "tier": "up"}, {"blink": True, "tier": "near"}, {"blink": False, "tier": "fresh"},
              {"blink": True, "tier": "closing"}, None, "junk"]
    assert EB.tab_tier(blocks) == "near"
    assert EB.tab_tier([{"blink": True, "tier": "fresh"}, {"blink": True, "tier": "imminent"}]) == "fresh"
    assert EB.tab_tier([]) is None and EB.tab_tier([{"blink": False, "tier": "fresh"}]) is None


# ── (n) source guards ────────────────────────────────────────────────────────────────────────────────────────────
def test_n_NEGATIVE_the_words_module_computes_no_ema_and_types_no_clock():
    assert "ewm(" not in SRC_EB and "import numpy" not in SRC_EB
    for lit in ('"04:00"', '"20:05"', '"16:00"', '"13:00"', "'04:00'", "'16:00'"):
        assert lit not in SRC_EB, lit
    tree = ast.parse(SRC_EB)
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "chart_maps.gajjala" in mods
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "chart_maps.gajjala"
             for a in n.names}
    assert {"ema_cross", "constants"} <= names
    assert "_masked_ema(" not in SRC_EB                                             # the engine owns the EMA path
    assert "b" + "ounce" not in SRC_EB.lower() and "@gmail" not in SRC_EB


def test_n_the_engine_reuses_the_cross_rule_and_the_house_ema():
    src = pathlib.Path(EX.__file__).read_text(encoding="utf-8")
    body = src[src.index("def blink_read"):src.index("def blink_from_bars")]
    assert "crosses_from_emas(" in body
    fb = src[src.index("def blink_from_bars"):]
    assert "_masked_ema" in fb and "ewm(" not in src
    assert set(EX.__all__) >= {"blink_read", "blink_from_bars", "TIERS", "tier_rank", "BLINK_STATES"}


def test_n_the_constants_guards_still_pass():
    import tests.test_gajjala_constants as TC
    TC.test_every_number_carries_a_provenance_comment()
    TC.test_NEGATIVE_no_bounce_word_and_no_other_board_names()
    TC.test_the_only_none_values_are_the_named_off_switches()
    TC.test_NEGATIVE_the_constants_import_only_the_stdlib_datetime_besides_the_ema_pair()


# ── (o) the ℹ️ clause ────────────────────────────────────────────────────────────────────────────────────────────
def test_o_the_rules_clause_rides_the_gajjala_note_after_the_base_count():
    from supply_demand import rules_info as RI
    note = RI._gajjala_section()["note"]
    line = EB.rules_line()
    assert line in note and RI._gg_ema_blink_clause() == " " + line
    assert "over 3 bars, projected within 24" in line and "9 EMA is over the 21 EMA" in line
    bases = RI._gg_run_bases_clause()
    if bases:
        assert note.index(bases) < note.index(line)
    assert note.index(line) < note.index("UNMEASURED — no study here says these setups win")


def test_o_NEGATIVE_a_raising_line_drops_the_clause_and_the_panel_stands(monkeypatch):
    from supply_demand import rules_info as RI
    monkeypatch.setattr(EB, "rules_line", lambda: 1 / 0)
    assert RI._gg_ema_blink_clause() == ""
    note = RI._gajjala_section()["note"]
    assert "🔀 Blinker" not in note and "UNMEASURED — no study here says these setups win" in note


# ── (p) the window ───────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def no_override(monkeypatch):
    from market_hours import gate
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)


def test_p_in_window_is_the_closed_day_gate_and_the_pass_window(no_override):
    assert EB.in_window(_et(2026, 11, 17, 10, 0)) is True                         # market Tuesday
    assert EB.in_window(_et(2026, 11, 14, 10, 0)) is False                        # Saturday
    assert EB.in_window(_et(2026, 11, 17, 20, 6)) is False                        # after PASS_CLOSE_ET
    assert EB.in_window(_et(2026, 11, 17, 3, 59)) is False                        # before PASS_OPEN_ET
    assert EB.in_window(_et(2026, 11, 26, 10, 0)) is False                        # Thanksgiving


def test_p_NEGATIVE_a_raising_gate_is_closed(no_override, monkeypatch):
    from market_hours import gate
    monkeypatch.setattr(gate, "closed_reason", lambda now=None: 1 / 0)
    assert EB.in_window(_et(2026, 11, 17, 10, 0)) is False


# ── the tab-dot counts (§3.8) over fake stores ───────────────────────────────────────────────────────────────────
class _Coll:
    def __init__(self, docs, boom=False):
        self.docs, self.boom, self.calls = list(docs), boom, []

    def find(self, q=None, proj=None):
        self.calls.append((q, proj))
        if self.boom:
            raise RuntimeError("down")
        out = []
        for d in self.docs:
            if "date" in (q or {}) and d.get("date") != q["date"]:
                continue
            if "_id" in (q or {}) and d.get("_id") not in q["_id"]["$in"]:
                continue
            out.append(d)
        return out

    def find_one(self, q):
        return next((d for d in self.docs if d.get("_id") == q.get("_id")), None)


class _Store:
    def __init__(self, reads, boom=False):
        self.reads_c = _Coll(reads, boom)

    def coll(self, name):
        from chart_maps.gajjala import store as ST
        assert name == ST.READS
        return self.reads_c

    def scan_docs(self, sessions):
        return []


def _curves(f, s, suf="5"):
    return {f"bars{suf}": [{"t": t} for t in _ts(len(f))],
            f"curves{suf}": [{"tone": "ema9", "values": f}, {"tone": "ema21", "values": s}]}


SESSION = "2026-11-17"
NOW = _et(2026, 11, 17, 10, 0)
NEAR = ([9.0, 9.2, 9.4, 9.6], [10.0] * 4)
FRESH = ([9.0, 9.5, 9.8, 10.2], [10.0] * 4)
WIDEN = ([9.6, 9.4, 9.2, 9.0], [10.0] * 4)


def _gg(sym, setups, tile):
    return {"date": SESSION, "symbol": sym, "setups": {s: {"state": st} for s, st in setups.items()}, "tile": tile}


def test_tab_counts_counts_symbols_with_a_card_near_or_at_the_cross(no_override):
    from chart_maps.gajjala import tab as GT
    reads = [_gg("NEAR", {"bull_flag": "forming"}, _curves(*NEAR)),
             _gg("FRSH", {"kiss_fly": "aplus"}, _curves(*FRESH)),
             _gg("WIDE", {"bull_flag": "triggered"}, _curves(*WIDEN)),
             _gg("NOCARD", {"bull_flag": "none"}, _curves(*FRESH)),                 # no card → never counted
             dict(_gg("OLD", {"bull_flag": "aplus"}, _curves(*FRESH)), date="2026-11-16")]
    st = _Store(reads)
    out = EB.tab_counts(NOW, owner=False, gg_store=st, gg1_store=_Store([]), luk_store=_Store([]))
    g = out["tabs"]["gajjala"]
    assert g["n"] == 2 and g["crossed_up"] == 1 and g["closing_in"] == 1 and g["tier"] == "fresh"
    assert g["top"] == {"symbol": "FRSH", "tier": "fresh", "closeness": 0} and g["frame"] == "5m"
    assert g["text"] == "2 cards at or near the 9/21 cross · closest FRSH" and g["session"] == SESSION
    assert out["tabs"]["gajjala_audited"] == g and out["tabs"]["gajjala_watch"] is None
    assert set(out["tabs"]) == set(EB.TAB_KEYS)
    assert out["in_window"] is True and out["refresh_sec"] == GC.BLINK_TAB_REFRESH_SEC == 60
    assert out["info"] == EB.info() and out["session"] == SESSION
    q, proj = st.reads_c.calls[0]
    assert q == {"date": SESSION}
    assert proj["tile.bars5.t"] == 1 and "tile.bars5" not in proj and proj["tile.curves5_prior"] == 1
    assert proj["tile.bars5_prior.t"] == 1 and all(f"setups.{s}.state" in proj for s in GC.SETUPS)
    assert "POTENTIAL_STATE" and GC.POTENTIAL_STATE in GT.TILE_STATES                 # every 🧠 card is a read card
    json.dumps(out, allow_nan=False)


def test_tab_counts_C4a_a_potential_card_counts_through_its_forming_read_and_the_tracker_is_never_read(no_override):
    """C4a deviation (documented, HIS call): the count does not read st.potentials; every 🧠 card is a read in
    POTENTIAL_STATE ("forming", one of tab.TILE_STATES), so it is carded and counted via its setup state."""
    from chart_maps.gajjala import potential as PT
    from chart_maps.gajjala import tab as GT
    assert GC.POTENTIAL_STATE in GT.TILE_STATES
    assert PT.potential_kind({"state": "none"}) is None and PT.potential_kind({"state": "triggered"}) is None

    class _Tracked(_Store):
        def __init__(self, reads, rows):
            super().__init__(reads)
            self.rows, self.potential_calls = rows, 0

        def potentials(self, session):
            self.potential_calls += 1
            return self.rows

    reads = [_gg("BRAIN", {"bull_flag": "forming"}, _curves(*NEAR)),
             _gg("GONE", {"bull_flag": "none"}, _curves(*FRESH))]
    st = _Tracked(reads, [{"symbol": "BRAIN", "setup": "bull_flag"}, {"symbol": "GONE", "setup": "bull_flag"}])
    g = EB.tab_counts(NOW, gg_store=st, gg1_store=_Store([]), luk_store=_Store([]))["tabs"]["gajjala"]
    assert g["n"] == 1 and g["top"]["symbol"] == "BRAIN" and g["tier"] == "near"
    assert st.potential_calls == 0                                                  # the tracker is never read
    assert "potentials" not in SRC_EB                                                # nor named in the counts


def test_tab_counts_C4a_NEGATIVE_a_tracker_row_without_a_card_state_is_not_counted(no_override):
    class _Tracked(_Store):
        def potentials(self, session):
            return [{"symbol": "GONE", "setup": "bull_flag"}]

    reads = [_gg("GONE", {"bull_flag": "none"}, _curves(*FRESH))]
    g = EB.tab_counts(NOW, gg_store=_Tracked(reads), gg1_store=_Store([]), luk_store=_Store([]))["tabs"]["gajjala"]
    assert g["n"] == 0 and g["top"] is None and g["tier"] is None


def test_tab_counts_the_squeeze_card_merges_its_prior_tail_through_the_frame_builder(no_override):
    prior = {"bars5_prior": [{"t": t} for t in _ts(2, day="2026-11-16", start_min=15 * 60)],
             "curves5_prior": [{"tone": "ema9", "values": [9.0, 10.5]}, {"tone": "ema21", "values": [10.0, 10.0]}]}
    tile = dict(_curves([10.6, 10.7, 10.8], [10.0] * 3), **prior)
    reads = [_gg("SQZ", {"reversal_squeeze": "forming"}, tile), _gg("BF", {"bull_flag": "forming"}, tile)]
    out = EB.tab_counts(NOW, gg_store=_Store(reads), gg1_store=_Store([]), luk_store=_Store([]))
    g = out["tabs"]["gajjala"]
    assert g["n"] == 1 and g["top"]["symbol"] == "SQZ" and g["top"]["tier"] == "up" and g["top"]["closeness"] == 3
    assert g["text"] == "SQZ at or near the 9/21 cross"                              # BF draws today only: above, none


def test_tab_counts_NEGATIVE_a_raising_store_is_that_tab_none_and_the_feed_stands(no_override):
    out = EB.tab_counts(NOW, gg_store=_Store([], boom=True), gg1_store=_Store([_gg("ONE", {"bull_flag": "forming"},
                                                                                  _curves(*NEAR, suf="1"))]),
                        luk_store=_Store([], boom=True))
    assert out["tabs"]["gajjala"] is None and out["tabs"]["gajjala_audited"] is None and out["tabs"]["luk"] is None
    one = out["tabs"]["gajjala_1m"]
    assert one["n"] == 1 and one["frame"] == "1m" and one["tier"] == "near"


def test_tab_counts_NEGATIVE_zero_blinking_and_closed_day(no_override):
    sat = _et(2026, 11, 14, 10, 0)
    reads = [dict(_gg("WIDE", {"bull_flag": "forming"}, _curves(*WIDEN)), date="2026-11-13")]
    out = EB.tab_counts(sat, gg_store=_Store(reads), gg1_store=_Store([]), luk_store=_Store([]))
    g = out["tabs"]["gajjala"]
    assert g["n"] == 0 and g["tier"] is None and g["text"] is None and g["top"] is None
    assert g["session"] == "2026-11-13"
    assert out["in_window"] is False and out["refresh_sec"] == 0
    late = EB.tab_counts(_et(2026, 11, 17, 20, 6), gg_store=_Store([]), gg1_store=_Store([]), luk_store=_Store([]))
    assert late["refresh_sec"] == 0


def test_tab_counts_luk_and_the_owner_watch(no_override):
    from chart_maps.gajjala_watch import constants as WC
    luk = [_gg("LK", {"pullback_reversal": "listed"}, _curves(*FRESH)),
           _gg("LN", {"pullback_reversal": "none"}, _curves(*FRESH))]
    w_tile = {"_id": "OMH", "frames": {"1m": {"bars": [{"t": t} for t in _ts(4)],
                                              "curves": [{"tone": "ema9", "values": NEAR[0]},
                                                         {"tone": "ema21", "values": NEAR[1]}]},
                                       "3m": {"bars": [], "curves": []}}}
    db = {WC.COLL_LIST: _Coll([{"_id": WC.LIST_DOC_ID, "symbols": ["OMH", "QQQ"]}]),
          WC.COLL_TILES: _Coll([w_tile]), WC.COLL_ALERTS: _Coll([]), WC.COLL_STATE: _Coll([])}
    out = EB.tab_counts(NOW, owner=True, gg_store=_Store([]), gg1_store=_Store([]), luk_store=_Store(luk),
                        watch_db=db)
    assert out["tabs"]["luk"]["n"] == 1 and out["tabs"]["luk"]["top"]["symbol"] == "LK"
    w = out["tabs"]["gajjala_watch"]
    assert w["n"] == 1 and w["tier"] == "near" and w["frame"] == "1m/5m/15m"         # RE-PINNED 2026-11-23 (C.FRAMES)
    _q, proj = db[WC.COLL_TILES].calls[0]
    assert proj["frames.1m.bars.t"] == 1 and "frames.1m.bars" not in proj
    # NEGATIVE: a non-owner never reads the watch (the collection is not touched)
    db2 = dict(db, **{WC.COLL_TILES: _Coll([w_tile])})
    out2 = EB.tab_counts(NOW, owner=False, gg_store=_Store([]), gg1_store=_Store([]), luk_store=_Store(luk),
                         watch_db=db2)
    assert out2["tabs"]["gajjala_watch"] is None and db2[WC.COLL_TILES].calls == []
    # NEGATIVE: truthy-but-not-True owner (a Query object) is a non-owner
    out3 = EB.tab_counts(NOW, owner="yes", gg_store=_Store([]), gg1_store=_Store([]), luk_store=_Store(luk),
                         watch_db=db2)
    assert out3["tabs"]["gajjala_watch"] is None


def test_tab_keys_are_the_variants_own_tab_names():
    from chart_maps.gajjala import variant as V
    from chart_maps.gajjala_watch import constants as WC
    from chart_maps.luk.variant import LUK
    assert set(EB.TAB_KEYS) == {V.GG5.tab, V.GGA.tab, V.GG1.tab, LUK.tab, WC.TAB}
