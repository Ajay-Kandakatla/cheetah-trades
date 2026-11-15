"""📶 GG's base count — the ONE engine chart_maps/gajjala/run_bases.py (spec ggbase rev 2 §3.1 / WP-A, 2026-11-15).

Ajay, verbatim: "There is a concept of 3 bases and climax run can you bake that in to the app please" · "I need that
tracked in to Gajjala's". His answers (2026-11-15) set the defaults pinned here: the count starts at the 09:30 open and
runs to the 16:00 close, the shortest base = K4_HF_BASE_MIN, a pause past K4_HF_BASE_MAX restarts the count, "Just show
it" (information only).

Synthetic frames are built on tests/fixtures/gajjala/detector_frames.frame (20 warm-up bars, today from 09:35); every
price is a multiple of 1/64. The four real replay-cache days pin the §1.5 table rows (the spec's rev-2 row, the rev-1 row
and Ajay's defaults). The walk is checked bar by bar against the reference walk (prefix + monotone sweeps).
"""
from __future__ import annotations

import ast
import json
import math
import re
from pathlib import Path

import pandas as pd
import pytest

from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run_bases as RB
from tests.fixtures.gajjala import detector_frames as FX

SRC = Path(RB.__file__)

# ── the synthetic builder ───────────────────────────────────────────────────────────────────────────────────────
LEG_R = 0.75                 # a demand bar's range (K1: +5% body at 10 and ≥ 1.5 × the 0.25 warm-up average)
LEG_V = 200_000
PAUSE_V = 50_000


def up(p: float, r: float = LEG_R, v: float = LEG_V) -> tuple:
    """A K1 demand bar from p: open = low = p, close = high = p + r."""
    return (p, p + r, p, p + r, v)


def pause_bar(top: float, v: float = PAUSE_V) -> tuple:
    """A quiet red bar UNDER `top` (never a new high, never a demand bar)."""
    return (top - 0.0625, top - 0.03125, top - 0.25, top - 0.125, v)


def build(segments: list, *, p0: float = 10.0) -> tuple:
    """segments = [("quiet", n) | ("leg", n[, range]) | ("pause", n) | ("drift", n) | ("fade", n)] → (bars, index of
    each segment's first today-offset). leg = n demand bars up (range LEG_R unless given); pause = n quiet bars under the high; drift = n small up bars
    that make new highs but are NOT K1; fade = n bars stepping down 0.125 each."""
    out, starts, p = [], [], p0
    for seg in segments:
        kind, n = seg[0], seg[1]
        r = seg[2] if len(seg) > 2 else LEG_R
        starts.append(len(out))
        for _ in range(n):
            if kind == "quiet":
                out.append(FX.quiet(p))
            elif kind == "leg":
                out.append(up(p, r))
                p += r
            elif kind == "pause":
                out.append(pause_bar(p))
            elif kind == "drift":
                q = p - 0.125 if out and out[-1][1] < p else p
                out.append((q, q + 0.25, q - 0.0625, q + 0.1875, PAUSE_V))
                p = q + 0.25
            elif kind == "fade":
                out.append((p, p, p - 0.1875, p - 0.125, PAUSE_V))
                p -= 0.125
            else:
                raise ValueError(kind)
        if kind == "pause":
            p -= 0.125                                         # the next leg opens at the pause's close
    return out, starts


def frame_of(segments, **kw):
    bars, starts = build(segments)
    return FX.frame(bars, **kw), starts


def t_of(F, k: int) -> str:
    return F.t[FX.today_index(F, k)]


def broke(blk) -> list:
    return [(ri, b["from_t"], b["to_t"], b["broke_t"]) for ri, r in enumerate(blk["runs"]) for b in r["bases"]
            if b["state"] == RB.BROKE]


def all_bases(blk) -> list:
    return [b for r in blk["runs"] for b in r["bases"]]


THREE = [("quiet", 3), ("leg", 2), ("pause", 6), ("leg", 2), ("pause", 6), ("leg", 2), ("pause", 6)]


# ── the walk ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_his_defaults_are_the_constants():
    assert (GC.RUN_BASE_FROM, GC.RUN_BASE_UNTIL, GC.RUN_BASE_RESTART) == ("rth", "rth", True)
    assert GC.RUN_BASE_MIN_BARS == GC.K4_HF_BASE_MIN and GC.RUN_BASE_MAX_BARS == GC.K4_HF_BASE_MAX
    assert GC.RUN_BASE_LEG_MIN_BARS == GC.BF_LEG_MIN_BARS and GC.RUN_BASE_DEPTH_FLOOR is False
    assert GC.RUN_BASE_FRAME == "5m" and set(GC.RUN_BASE_HOURS) == {"session", "rth"}
    assert GC.RUN_BASE_FROM in GC.RUN_BASE_HOURS and GC.RUN_BASE_UNTIL in GC.RUN_BASE_HOURS
    assert (GC.RUN_BASE_CLIMAX_N, GC.RUN_BASE_OUT_N) == (3, 4)


def test_run_base_one_break_base_two_break_base_three_forming():
    F, st = frame_of(THREE)
    blk = RB.count(F)
    assert blk["version"] == RB.VERSION and blk["frame"] == "5m" and blk["as_of_bar_t"] == F.t[-1]
    assert (blk["from"], blk["until"], blk["restart"], blk["depth_floor"]) == ("rth", "rth", True, False)
    assert len(blk["runs"]) == 1
    run = blk["runs"][0]
    assert run["from_t"] == t_of(F, st[1]) and run["n"] == 2 and run["state"] == RB.FORMING
    b1, b2, b3 = run["bases"]
    assert (b1["n"], b1["from_t"], b1["to_t"], b1["bars"], b1["state"], b1["broke_t"]) == (
        1, t_of(F, st[2]), t_of(F, st[2] + 5), 6, RB.BROKE, t_of(F, st[3]))
    assert (b2["n"], b2["from_t"], b2["bars"], b2["state"], b2["broke_t"]) == (2, t_of(F, st[4]), 6, RB.BROKE,
                                                                               t_of(F, st[5]))
    assert (b3["n"], b3["from_t"], b3["to_t"], b3["state"], b3["broke_t"]) == (3, t_of(F, st[6]), F.t[-1],
                                                                               RB.FORMING, None)
    assert b1["leg"] == {"s_t": t_of(F, st[1]), "e_t": t_of(F, st[1] + 1), "bars": 2}
    assert b1["quiet"] is True and b1["shallow"] is True and "tight" not in b1      # stored for the study only
    assert b1["lo"] < b1["hi"]
    assert (blk["n"], blk["forming"], blk["state"]) == (2, True, RB.FORMING)


def test_every_last_is_a_prefix_and_the_broke_total_never_decreases():
    F, _st = frame_of(THREE + [("leg", 2), ("pause", 6), ("leg", 2)])
    full = broke(RB.count(F))
    assert len(full) == 4
    prev = 0
    for j in F.today:
        b = broke(RB.count(F, last=j))
        assert b == full[:len(b)], j
        assert len(b) >= prev, j
        prev = len(b)
    # the frame cut at j (fixture prefix) reads the same as last=j
    j = FX.today_index(F, 20)
    assert broke(RB.count(FX.prefix(F, j))) == broke(RB.count(F, last=j))


def test_a_new_run_after_a_stall_counts_from_one_and_the_card_number_drops_on_purpose():
    F, st = frame_of([("quiet", 3), ("leg", 2), ("pause", 6), ("leg", 2), ("pause", GC.RUN_BASE_MAX_BARS + 1),
                      ("leg", 2), ("pause", 6), ("leg", 2)])
    stalled = RB.count(F, last=FX.today_index(F, st[5] - 1))
    assert stalled["n"] == 1 and stalled["state"] == RB.STALLED
    blk = RB.count(F)
    assert len(blk["runs"]) == 2 and blk["runs"][0]["state"] == RB.STALLED and blk["runs"][0]["n"] == 1
    assert blk["n"] == 1 and blk["runs"][1]["from_t"] == t_of(F, st[5])
    fresh = RB.count(F, last=FX.today_index(F, st[5] + 1))           # the new run, no base yet → n 0 (drop pinned)
    assert fresh["n"] == 0 and fresh["state"] == RB.RUNNING and len(fresh["runs"]) == 2


def test_a_forming_base_that_outlives_max_turns_stalled():
    F, st = frame_of([("quiet", 3), ("leg", 2), ("pause", 6), ("leg", 2), ("pause", GC.RUN_BASE_MAX_BARS + 1)])
    at_max = RB.count(F, last=FX.today_index(F, st[4] + GC.RUN_BASE_MAX_BARS - 1))
    assert (at_max["n"], at_max["forming"]) == (1, True)
    after = RB.count(F)
    assert (after["n"], after["forming"], after["state"]) == (1, False, RB.STALLED)


# ── constants read at CALL time, each both ways ─────────────────────────────────────────────────────────────────
def test_leg_min_bars_moves_the_count(monkeypatch):
    F, _st = frame_of(THREE)
    assert RB.count(F)["n"] == 2
    monkeypatch.setattr(GC, "RUN_BASE_LEG_MIN_BARS", 3)
    blk = RB.count(F)
    assert blk["n"] == 0 and blk["runs"] == [] and blk["state"] is None


def test_min_bars_moves_the_count(monkeypatch):
    F, _st = frame_of([("quiet", 3), ("leg", 2), ("pause", 3), ("leg", 2), ("pause", 3), ("leg", 2)])
    assert RB.count(F)["n"] == 0                                      # 3 bars < K4_HF_BASE_MIN
    monkeypatch.setattr(GC, "RUN_BASE_MIN_BARS", GC.K4_BF_PULL_MIN)
    assert RB.count(F)["n"] == 2


def test_max_bars_moves_the_count(monkeypatch):
    F, _st = frame_of(THREE)
    monkeypatch.setattr(GC, "RUN_BASE_MAX_BARS", 5)
    blk = RB.count(F)
    assert blk["n"] == 0 and not all_bases(blk)
    monkeypatch.setattr(GC, "RUN_BASE_MAX_BARS", GC.K4_HF_BASE_MAX)
    assert RB.count(F)["n"] == 2


def test_from_moves_the_count_premarket_bases_count_only_under_session(monkeypatch):
    F, _st = frame_of(THREE, start="07:00")                         # today's bars 07:00 … 08:40 — premarket only
    blk = RB.count(F)
    assert blk["n"] == 0 and blk["runs"] == [] and blk["from"] == "rth"   # NEGATIVE: FROM rth on a premarket frame
    monkeypatch.setattr(GC, "RUN_BASE_FROM", "session")
    blk = RB.count(F)
    assert blk["n"] == 2 and blk["forming"] is True and blk["from"] == "session"


def test_the_first_counted_bar_is_the_one_stamped_after_the_open():
    F, _st = frame_of(THREE, start="09:30")                         # the 09:30 stamp holds 09:25–09:29
    blk = RB.count(F)
    assert blk["runs"] and blk["runs"][0]["from_t"] > F.t[FX.today_index(F, 0)]
    # a 3-bar leg stamped 09:25 / 09:30 / 09:35: only ONE of its bars is after the open — never a run (needs 2)
    G, _st = frame_of([("leg", 3), ("pause", 6), ("leg", 1)], start="09:25")
    assert RB.count(G)["runs"] == [] and RB.count(G)["n"] == 0


def test_until_moves_the_count_after_hours_base(monkeypatch):
    # today from 15:20: the third leg + its pause print after 16:00
    F, st = frame_of([("quiet", 1), ("leg", 2), ("pause", 6), ("leg", 2), ("pause", 6), ("leg", 2)], start="15:15")
    assert t_of(F, st[3]) == "2026-10-13 16:00" and t_of(F, st[4]) > "2026-10-13 16:00"
    blk = RB.count(F)                                                 # rth: stops at the 16:00 bar
    assert [b["state"] for b in all_bases(blk)] == [RB.BROKE] and blk["until"] == "rth"
    assert all(b["to_t"] <= "2026-10-13 16:00" for b in all_bases(blk))
    monkeypatch.setattr(GC, "RUN_BASE_UNTIL", "session")
    blk = RB.count(F)
    assert blk["n"] == 2 and blk["until"] == "session"


def test_unknown_hours_value_reads_as_session(monkeypatch):
    F, _st = frame_of(THREE, start="07:00")
    monkeypatch.setattr(GC, "RUN_BASE_FROM", "nonsense")
    assert RB.count(F)["n"] == 2 and RB.count(F)["from"] == "session"


def _deep_frame():
    # leg to 11.5, then a 6-bar pause whose lows drop 35% of the price and recover under the high, then a break
    bars, _ = build([("quiet", 3), ("leg", 2)])
    top = bars[-1][1]
    deep = [(top - 0.25, top - 0.125, top * 0.65, top - 0.25, PAUSE_V)] + [pause_bar(top) for _ in range(5)]
    return FX.frame(bars + deep + [up(top - 0.125)])


def test_depth_floor_switch_both_ways(monkeypatch):
    F = _deep_frame()
    assert RB.count(F)["n"] == 1 and all_bases(RB.count(F))[0]["shallow"] is False   # OFF (default): any depth
    monkeypatch.setattr(GC, "RUN_BASE_DEPTH_FLOOR", True)
    blk = RB.count(F)
    assert blk["n"] == 0 and not all_bases(blk) and blk["depth_floor"] is True        # NEGATIVE: ON → no base


def _fade_then_rerun():
    # run 1 (one base, high ~13), a long fade under the morning high, then run 2: three bases, all UNDER that high
    segs = [("quiet", 3), ("leg", 2), ("pause", 6), ("leg", 2), ("fade", GC.RUN_BASE_MAX_BARS + 6)]
    for _ in range(3):
        segs += [("leg", 2, 0.5), ("pause", 6)]
    segs += [("leg", 2, 0.5)]
    bars, st = build(segs)
    return FX.frame(bars), st, bars


def test_fade_then_rerun_restart_on_counts_run_two():
    F, st, bars = _fade_then_rerun()
    assert max(b[1] for b in bars[st[5]:]) < max(b[1] for b in bars[:st[4] + 1])   # run 2 never takes the morning high
    blk = RB.count(F)
    assert len(blk["runs"]) == 2 and blk["runs"][0]["n"] == 1 and blk["runs"][0]["state"] == RB.STALLED
    assert blk["n"] == 3 and blk["runs"][1]["from_t"] == t_of(F, st[5])


def test_NEGATIVE_fade_then_rerun_restart_off_n_stays_one_and_stalled(monkeypatch):
    monkeypatch.setattr(GC, "RUN_BASE_RESTART", False)
    F, _st, _b = _fade_then_rerun()
    blk = RB.count(F)
    assert len(blk["runs"]) == 1 and blk["n"] == 1 and blk["state"] == RB.STALLED and blk["restart"] is False


# ── a dip shorter than a base hands the K1 leg back (2026-11-15 critic fix) ──────────────────────────────────────
DIP_BASE = [("quiet", 2), ("leg", 2), ("drift", 1), ("pause", 10), ("drift", 1)]


@pytest.mark.parametrize("dip", [1, 3, GC.K4_HF_BASE_MIN - 1])
def test_NEGATIVE_a_short_dip_never_uses_up_the_leg(dip):
    plain = RB.count(frame_of(DIP_BASE)[0])
    F, st = frame_of([("quiet", 2), ("leg", 2), ("pause", dip), ("drift", 1), ("pause", 10), ("drift", 1)])
    blk = RB.count(F)
    assert plain["n"] == 1
    assert blk["n"] == 1 and len(all_bases(blk)) == 1                 # was n 0 before the fix
    b = all_bases(blk)[0]
    assert (b["from_t"], b["bars"], b["state"]) == (t_of(F, st[4]), 10, RB.BROKE)
    assert b["leg"] == {"s_t": t_of(F, st[1]), "e_t": t_of(F, st[1] + 1), "bars": 2}


def test_NEGATIVE_a_dip_as_long_as_a_base_is_the_base_and_hands_nothing_back():
    F, st = frame_of([("quiet", 2), ("leg", 2), ("pause", GC.K4_HF_BASE_MIN), ("drift", 1), ("pause", 10),
                      ("drift", 1)])
    blk = RB.count(F)
    bases = all_bases(blk)
    assert blk["n"] == 1 and len(bases) == 1 and bases[0]["from_t"] == t_of(F, st[2])   # the drift anchors nothing


def test_NEGATIVE_a_newer_leg_keeps_its_own_anchor_after_a_dip():
    F, st = frame_of([("quiet", 2), ("leg", 2), ("pause", 1), ("leg", 2), ("pause", 6), ("leg", 1)])
    b = all_bases(RB.count(F))
    assert len(b) == 1 and b[0]["leg"]["s_t"] == t_of(F, st[3])      # the second leg, never the first one


# ── the half-day close (2026-11-15 critic fix) ──────────────────────────────────────────────────────────────────
def _on_day(F, day: str):
    F.t = [t.replace(FX.TODAY, day) for t in F.t]
    F.session = [s.replace(FX.TODAY, day) for s in F.session]
    return F


def test_NEGATIVE_half_day_after_hours_bars_never_count():
    from supply_demand.timeframes import HALF_DAYS
    half = "2026-11-27"
    assert half in HALF_DAYS
    segs = [("quiet", 1), ("leg", 2), ("pause", 6), ("leg", 2), ("pause", 6), ("leg", 2)]
    full = _on_day(frame_of(segs, start="12:15")[0], "2026-11-20")     # a normal Friday: the whole tape is RTH
    assert RB.count(full)["n"] == 2
    F, st = frame_of(segs, start="12:15")
    F = _on_day(F, half)
    assert t_of(F, st[3]) == f"{half} 13:00" and t_of(F, st[4]) > f"{half} 13:00"
    blk = RB.count(F)
    assert [b["state"] for b in all_bases(blk)] == [RB.BROKE] and blk["n"] == 1
    assert all(b["to_t"] <= f"{half} 13:00" for b in all_bases(blk))
    card = RB.card_block(blk)
    assert "to the 13:00 ET close" in card["title"] and "16:00" not in card["title"]


def test_a_base_open_at_the_close_says_so_and_never_forming_since():
    F, st = frame_of([("quiet", 1), ("leg", 2), ("pause", 6), ("leg", 2), ("pause", 8)], start="14:40")
    at_close = RB.count(F, last=next(i for i in F.today if F.t[i].endswith("16:00")))
    assert RB.card_block(at_close)["text"].startswith("📶 2nd base · forming since ")   # still the session
    after = RB.count(F)
    assert after["as_of_bar_t"] > f"{FX.TODAY} 16:00" and after["forming"] is True
    text = RB.card_block(after)["text"]
    assert text == "📶 2nd base · forming at the 16:00 ET close · 5-min bars" and "since" not in text


def test_NEGATIVE_session_until_keeps_forming_since(monkeypatch):
    monkeypatch.setattr(GC, "RUN_BASE_UNTIL", "session")
    F, _st = frame_of([("quiet", 1), ("leg", 2), ("pause", 6), ("leg", 2), ("pause", 8)], start="14:40")
    assert "forming since " in RB.card_block(RB.count(F))["text"]


# ── NEGATIVES ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_k1_run_is_the_empty_block():
    F = FX.frame([FX.quiet(10.0)] * 30)
    blk = RB.count(F)
    assert (blk["n"], blk["forming"], blk["state"], blk["runs"]) == (0, False, None, [])


def test_NEGATIVE_critic_case_b_the_legs_last_bar_anchors_its_own_pause():
    """C2.1: a leg whose LAST bar makes no new high — that bar starts the pause the leg anchors; never a phantom
    base later."""
    d1 = (10.0, 10.75, 10.0, 10.75, LEG_V)
    d2 = (10.25, 10.6875, 10.1875, 10.6875, LEG_V)                   # K1 (+4.3%, range 0.5) but under d1's high
    rest = [pause_bar(10.75) for _ in range(5)]
    brk = up(10.625)
    after = [pause_bar(brk[1]) for _ in range(2)] + [up(brk[1] - 0.125)]   # a 2-bar pause later: never a base
    F = FX.frame([FX.quiet(10.0)] * 3 + [d1, d2] + rest + [brk] + after)
    blk = RB.count(F)
    bases = all_bases(blk)
    assert len(bases) == 1 and bases[0]["from_t"] == t_of(F, 4) and bases[0]["bars"] == 6
    assert bases[0]["broke_t"] == t_of(F, 10) and bases[0]["leg"]["e_t"] == t_of(F, 4)
    assert not [b for b in bases if b["from_t"] > t_of(F, 10)]


def test_NEGATIVE_a_leg_straddling_the_stall_bar_never_starts_a_run():
    bars, st = build([("quiet", 3), ("leg", 2), ("pause", 6), ("leg", 2), ("fade", GC.RUN_BASE_MAX_BARS - 1)])
    p = bars[-1][3]
    leg = [up(p, 0.375), up(p + 0.375, 0.375), up(p + 0.75, 0.375)]  # starts on pause bar 24, the stall is its bar 2
    tail = [pause_bar(p + 1.125) for _ in range(6)]
    F = FX.frame(bars + leg + tail)
    blk = RB.count(F)
    assert len(blk["runs"]) == 1 and blk["state"] == RB.STALLED and blk["n"] == 1


def test_NEGATIVE_a_pause_longer_than_max_is_no_base(monkeypatch):
    monkeypatch.setattr(GC, "RUN_BASE_RESTART", False)
    F, _st = frame_of([("quiet", 3), ("leg", 2), ("pause", GC.RUN_BASE_MAX_BARS + 1), ("leg", 2)])
    blk = RB.count(F)
    assert blk["n"] == 0 and not all_bases(blk)
    assert RB.ellipses(blk, [{"t": t} for t in F.t], "5m") == []


def test_NEGATIVE_a_pause_after_a_non_k1_drift_is_not_counted():
    F, _st = frame_of([("quiet", 3), ("leg", 2), ("pause", 6), ("drift", 3), ("pause", 6), ("drift", 1)])
    blk = RB.count(F)
    assert blk["n"] == 1 and len(all_bases(blk)) == 1                # base 1 only — the drift anchors nothing


def test_NEGATIVE_dropped_bucket_gap_counts_printed_bars():
    """C2.4: the resampler drops an empty bucket — stamps skip 10:40 → 10:55, the base is 6 PRINTED bars."""
    F, st = frame_of([("quiet", 3), ("leg", 2), ("pause", 6), ("leg", 2)])
    first = FX.today_index(F, st[2])
    for j in range(first + 2, len(F.t)):                              # after pause bar 2: shift every stamp +10 min
        h, m = map(int, F.t[j].split(" ")[1].split(":"))
        tot = h * 60 + m + 10
        F.t[j] = "%s %02d:%02d" % (F.t[j].split(" ")[0], tot // 60, tot % 60)
    b = all_bases(RB.count(F))
    assert len(b) == 1 and b[0]["bars"] == 6 and b[0]["from_t"] == F.t[first] and b[0]["to_t"] == F.t[first + 5]


def test_NEGATIVE_halt_the_resume_bar_that_takes_the_high_breaks_the_base():
    F, st = frame_of([("quiet", 3), ("leg", 2), ("pause", 6), ("leg", 2)])
    resume = FX.today_index(F, st[3])
    for j in range(resume, len(F.t)):                                 # no bars for 15 minutes before the resume bar
        h, m = map(int, F.t[j].split(" ")[1].split(":"))
        tot = h * 60 + m + 15
        F.t[j] = "%s %02d:%02d" % (F.t[j].split(" ")[0], tot // 60, tot % 60)
    b = all_bases(RB.count(F))
    assert len(b) == 1 and b[0]["broke_t"] == F.t[resume] and b[0]["bars"] == 6


def test_NEGATIVE_none_and_empty_never_raise():
    assert RB.count(None) is None
    F = FX.frame([], prior=[])
    assert RB.count(F) is None


def test_NEGATIVE_nan_bars_never_raise():
    bars, _ = build(THREE)
    bars[8] = (float("nan"),) * 4 + (PAUSE_V,)
    blk = RB.count(FX.frame(bars))
    assert isinstance(blk, dict)
    for b in all_bases(blk):
        assert b["lo"] is None or math.isfinite(b["lo"])


def test_NEGATIVE_a_garbage_frame_returns_none_never_raises():
    class Junk:
        c = [1, 2]
        t = ["x", "y"]
        today = range(0, 2)
    assert RB.count(Junk()) is None


def test_frame_of_reads_the_counting_frame_only():
    F5 = FX.frame([FX.quiet(10.0)] * 3)
    F15 = FX.frame([FX.quiet(10.0)] * 3, tf="15m")
    assert RB.frame_of({"5m": F5, "15m": F15}) is F5
    assert RB.frame_of(F5) is F5
    assert RB.frame_of(F15) is None and RB.frame_of({"1m": F5}) is None and RB.frame_of(None) is None
    fr = B.Frames("X", "2026-10-13", {"5m": F5, "15m": F15}, raw=None)
    assert RB.frame_of(fr) is F5
    assert RB.frame_of(B.Frames("X", "2026-10-13", {"1m": F15, "5m": F5}, raw=None, primary="1m", slow="5m")) is F5


# ── the four real fixture days (§1.5) ───────────────────────────────────────────────────────────────────────────
_R = Path(__file__).parent / "fixtures" / "gajjala" / "replay_cache_2026_10_12" / "minutes"
_DAYS = (("WFF", "2026-10-08", "2026-10-09"), ("TCRT", "2026-10-09", "2026-10-12"),
         ("WFF", "2026-10-09", "2026-10-12"), ("TCRT", "2026-10-12", "2026-10-13"))


def _load(d, s):
    j = json.loads((_R / d / f"{s}.json").read_text())
    idx = pd.to_datetime(j["t"], unit="ms")
    return pd.DataFrame({"open": j["o"], "high": j["h"], "low": j["l"], "close": j["c"], "volume": j["v"]},
                        index=idx)


@pytest.fixture(scope="module")
def real_frames():
    return [B.build_frames(s, d, pd.Timestamp(d + " 23:59", tz="UTC"), _load(prev, s), _load(d, s)).f5
            for s, prev, d in _DAYS]


def _row(frames):
    return [(RB.count(F)["n"], len(all_bases(RB.count(F)))) for F in frames]


def test_real_days_at_his_defaults(real_frames):
    # WFF 10-09 was (1, 1) before the 2026-11-15 leg give-back fix: a sub-6-bar dip at 12:00 no longer eats the run's
    # K1 leg, so the 15:15–16:00 pause reads as the 2nd base, forming at the close
    assert _row(real_frames) == [(1, 2), (0, 1), (0, 0), (1, 1)]
    wff = RB.count(real_frames[0])
    assert [(b["from_t"][11:], b["to_t"][11:], b["state"]) for b in all_bases(wff)] == [
        ("10:05", "11:55", RB.BROKE), ("15:15", "16:00", RB.FORMING)]
    assert RB.card_block(wff)["text"] == "📶 2nd base · forming at the 16:00 ET close · 5-min bars"


def test_real_days_at_the_spec_rev2_row(real_frames, monkeypatch):
    monkeypatch.setattr(GC, "RUN_BASE_UNTIL", "session")
    monkeypatch.setattr(GC, "RUN_BASE_MIN_BARS", GC.K4_BF_PULL_MIN)
    assert _row(real_frames) == [(2, 2), (1, 2), (1, 1), (1, 1)]


def test_real_days_at_the_rev1_row(real_frames, monkeypatch):
    for k, v in (("RUN_BASE_FROM", "session"), ("RUN_BASE_UNTIL", "session"), ("RUN_BASE_RESTART", False),
                 ("RUN_BASE_MIN_BARS", GC.K4_BF_PULL_MIN)):
        monkeypatch.setattr(GC, k, v)
    assert [n for n, _a in _row(real_frames)] == [2, 2, 2, 3]


def test_NEGATIVE_until_rth_drops_the_tcrt_after_hours_base(real_frames, monkeypatch):
    monkeypatch.setattr(GC, "RUN_BASE_MIN_BARS", GC.K4_BF_PULL_MIN)
    F = real_frames[1]                                                # TCRT 2026-10-12
    monkeypatch.setattr(GC, "RUN_BASE_UNTIL", "session")
    ah = [(b["from_t"][11:], b["to_t"][11:]) for b in all_bases(RB.count(F))]
    assert ("16:10", "16:20") in ah
    monkeypatch.setattr(GC, "RUN_BASE_UNTIL", "rth")
    assert ("16:10", "16:20") not in [(b["from_t"][11:], b["to_t"][11:]) for b in all_bases(RB.count(F))]


@pytest.mark.parametrize("min_bars", ["K4_BF_PULL_MIN", "K4_HF_BASE_MIN"])
def test_real_days_prefix_and_monotone(real_frames, monkeypatch, min_bars):
    monkeypatch.setattr(GC, "RUN_BASE_MIN_BARS", getattr(GC, min_bars))
    monkeypatch.setattr(GC, "RUN_BASE_UNTIL", "session")
    for F in real_frames:
        full = broke(RB.count(F))
        prev = 0
        for j in F.today:
            b = broke(RB.count(F, last=j))
            assert b == full[:len(b)]
            assert len(b) >= prev
            prev = len(b)


# ── source guards ───────────────────────────────────────────────────────────────────────────────────────────────
def test_no_numeric_literal_beyond_zero_and_one():
    tree = ast.parse(SRC.read_text())
    bad = [(n.lineno, n.value) for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)
           and n.value not in (0, 1)]
    assert bad == []


def test_constants_are_read_at_call_time_and_no_sepa_import():
    text = SRC.read_text()
    assert "from .constants import" not in text and "from chart_maps.gajjala.constants import" not in text
    assert "GC.RUN_BASE_MIN_BARS" in text and "GC.RUN_BASE_FROM" in text
    tree = ast.parse(text)
    mods = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    mods += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [m for m in mods if "sepa" in m]


def test_NEGATIVE_no_k6_tight_or_runner_number_and_no_b_word():
    text = SRC.read_text()
    assert "K6_TIGHT_PCT" not in text and "SA_BIG_RUNNER_PCT" not in text
    served = [v for k, v in vars(RB).items() if k.isupper() and isinstance(v, (str, tuple, dict))]
    blob = json.dumps(served, ensure_ascii=False, default=str).lower()
    assert "b" + "ounce" not in blob
    for word in (" sell", " buy", " exit"):
        assert word not in blob, word


def test_NEGATIVE_tone_is_never_red():
    assert RB.MARK_TONE == "structure"
    assert not re.search(r"red|exit|stop", RB.MARK_TONE)
