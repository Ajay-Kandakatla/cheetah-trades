"""🔑 Key Levels tab on Chart Maps (2026-09-28) — spec §3, tests 1-30.

Ajay 2026-09-28: "Also create me tab for keylevel main. Sort them by stocks
that are near lower keylevels".

Pins the engine additions in `supply_demand/key_levels.py` (the frozen half of
`tile_block`, `anchor_read`, `nearest_lower`, `last_bar_read`, the near
block and its words), the per-session memo + per-request rank in
`chart_maps/key_levels_tab.py`, and the board wiring (one snapshot, one
first-seen read, one clock, the turnover fallback, the sort label).
Positive AND negative cases. Stubs only — the conftest refuses Mongo; no
thread is ever started (`_spawn` is patched) and nothing reaches the network.
"""
from __future__ import annotations

import inspect
import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from chart_maps import board as B
from chart_maps import key_levels_tab as KLT
from supply_demand import key_levels as KL
from supply_demand import quick_bounce as QB

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]

NOW = datetime(2026, 9, 29, 11, 0, tzinfo=ET)          # Tuesday, rth
SESSION = date(2026, 9, 29)
OFF = datetime(2026, 9, 28, 21, 0, tzinfo=ET)          # Monday after the 20:00 roll
AH = datetime(2026, 9, 29, 16, 30, tzinfo=ET)          # close phase


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------
def _market_days(end: str, n: int) -> list:
    from market_hours.reminder import ALL_HOLIDAYS
    out, d = [], pd.Timestamp(end)
    while len(out) < n:
        if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in ALL_HOLIDAYS:
            out.append(d)
        d -= pd.Timedelta(days=1)
    return sorted(out)


def _frame(end="2026-09-28", n=60, *, close=101.0, pwl=100.0, pml=97.0,
           pwl_day="2026-09-23", pml_day="2026-08-12", sets=None, volume=1_000_000.0):
    """Close `close`, lows 0.2 under it, one prior-week low `pwl` (on
    `pwl_day`) and one August low `pml` — so PWL / PML are exact."""
    idx = pd.DatetimeIndex(_market_days(end, n))
    df = pd.DataFrame({"open": close, "high": close + 1.0, "low": close - 0.2,
                       "close": close, "volume": volume}, index=idx)
    base = {}
    if pwl is not None:
        base[pwl_day] = {"low": pwl}
    if pml is not None:
        base.setdefault(pml_day, {})["low"] = pml
    for day, vals in {**base, **(sets or {})}.items():
        for k, v in vals.items():
            df.loc[pd.Timestamp(day), k] = v
    return df


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _snap(*, px=None, at=None, open_=None, high=None, low=None, close=None, pdc=None,
          age_sec=30) -> dict:
    """A raw bulk_snapshot row (the shape `row_from_snapshot` reads)."""
    ts = _ms(at) - age_sec * 1000 if (px is not None and at is not None) else None
    return {"open": open_, "high": high, "low": low, "close": close,
            "last_trade_price": px, "last_trade_ts_ms": ts, "prev_day_close": pdc}


def _rth(px, *, ref=101.0, low=None, close=None, at=NOW, age_sec=30):
    return _snap(px=px, at=at, open_=ref, high=max(ref, px), low=low if low is not None else px,
                 close=close if close is not None else px, pdc=ref, age_sec=age_sec)


def _entry(frames: dict, session=SESSION) -> dict:
    return KLT.build("full", session, universe_fn=lambda k: list(frames),
                     frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames})


def _read(df, row, now=NOW, sym="AAA"):
    session = KL.levels_session(now)
    cl = KL.closed_levels(sym, df, frame="daily", session=session)
    read = KL.read_levels(cl["levels"], symbol=sym, ref_close=cl["ref_close"], row=row,
                          now=now, session=session, first_seen={})
    px = KL._anchor(row, now, session, cl["ref_close"])
    return read, px


@pytest.fixture(autouse=True)
def _clean_memo(monkeypatch):
    KLT._memo.clear()
    KLT._warming.clear()
    spawned = []
    monkeypatch.setattr(KLT, "_spawn", lambda target, name: spawned.append(name))
    yield spawned
    KLT._memo.clear()
    KLT._warming.clear()


# --------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------
def test_1_closed_levels_is_the_frozen_half_of_tile_block():
    df = _frame(n=300, sets={"2026-03-04": {"low": 80.0}})
    row = KL.row_from_snapshot(_rth(101.2))
    block, _ = KL.tile_block("AAA", df, frame="daily", row=row, now=NOW,
                             per_side=KL.GRID_PER_SIDE)
    cl = KL.closed_levels("AAA", df, frame="daily", session=SESSION)
    assert [(m["id"], m["price"]) for m in cl["levels"]] == \
        [(m["id"], m["price"]) for m in block["levels"]]
    assert cl["ref_close"] == 101.0 and cl["last_date"] == "2026-09-28" and cl["stale_note"] is None
    passed = KL.closed_levels("AAA", df, frame="daily", session=SESSION,
                              closed=KL.closed_frame(df, SESSION))
    assert passed == cl
    assert block["verified"] is True and block["stale_note"] is None
    # NEGATIVE: no bars -> no levels and the note; bars behind -> the note, levels kept.
    none = KL.closed_levels("zzz", None, frame="daily", session=SESSION)
    assert none == {"levels": [], "ref_close": None, "last_date": None,
                    "stale_note": "no cached daily bars for ZZZ"}
    behind = KL.closed_levels("AAA", _frame(end="2026-09-24"), frame="daily", session=SESSION)
    assert behind["stale_note"].startswith("key levels need bars through 2026-09-28")
    assert behind["levels"]


def test_1b_verify_last_row_is_a_thin_wrapper():
    df = _frame()
    closed = KL.closed_frame(df, SESSION)
    for row in (KL.row_from_snapshot(_rth(101.2)), KL.row_from_snapshot(_snap(close=101.5, pdc=101.7)),
                None, {"close": None, "prev_day_close": None, "last_trade_price": 3.0}):
        assert KL.verify_last_row(closed, row) == KL.verify_last(101.0, "2026-09-28", row)
    assert KL.verify_last(101.0, None, KL.row_from_snapshot(_rth(101.2))) == (None, False)


def test_2_anchor_read_matches_anchor_everywhere_with_its_basis():
    ref = 101.0
    cases = [
        (datetime(2026, 9, 29, 8, 0, tzinfo=ET), _snap(px=100.5, at=datetime(2026, 9, 29, 8, 0, tzinfo=ET),
                                                    pdc=ref), "live", "premarket"),
        (datetime(2026, 9, 29, 8, 0, tzinfo=ET), _snap(px=100.5, at=datetime(2026, 9, 29, 7, 0, tzinfo=ET),
                                                    pdc=ref), "last_close", None),
        (NOW, _rth(100.7), "live", "rth"),
        (NOW, _rth(100.7, age_sec=600), "day_close", None),
        (AH, _snap(px=100.2, at=AH, close=100.6, pdc=ref), "live", "afterhours"),
        (AH, _snap(close=100.6, pdc=ref), "day_close", None),
        (OFF, _snap(close=101.0, pdc=100.9), "last_close", None),
    ]
    for now, raw, basis, tape in cases:
        row = KL.row_from_snapshot(raw)
        session = KL.levels_session(now)
        px, b, t = KL.anchor_read(row, now, session, ref)
        assert px == KL._anchor(row, now, session, ref)
        assert (b, t) == (basis, tape), (now, raw)
    assert KL.anchor_read(None, OFF, SESSION, None) == (None, None, None)


def test_3_nearest_lower_picks_the_closest_and_a_tie_goes_to_the_longer_period():
    df = _frame(pwl=100.0, pml=97.0)
    read, px = _read(df, KL.row_from_snapshot(_rth(101.2)))
    nl = KL.nearest_lower(read, px)
    assert nl["status"] == "ranked" and nl["nearest"]["label"] == "PWL"
    tie = _frame(pwl=98.0, pml=98.0)
    read, px = _read(tie, KL.row_from_snapshot(_rth(101.2)))
    nl = KL.nearest_lower(read, px)
    assert nl["nearest"]["label"] == "PML" and nl["nearest"]["period"] == "month"


def test_4_NEGATIVE_a_low_above_the_last_close_is_not_a_lower_level():
    # Last close 101, PWL 101.5 above it (resistance side); the print 102 is above it.
    df = _frame(pwl=101.5, pml=None, sets={"2026-09-23": {"low": 101.5, "high": 103.0}})
    df["low"] = df["low"].clip(lower=101.5)
    read, px = _read(df, KL.row_from_snapshot(_rth(102.0)))
    pwl = [m for m in read if m["label"] == "PWL"][0]
    assert pwl["side"] == "resistance"
    nl = KL.nearest_lower(read, px)
    assert nl["status"] == "no_level" and nl["nearest"] is None and nl["through"] == []


def test_5_NEGATIVE_a_high_below_the_price_never_counts_under_the_default_kinds():
    member = {**KL._member("week", "high", 100.0, "2026-09-25"), "side": "support",
              "state": "intact", "dist_pct": -1.0, "ah_through": False}
    assert KL.nearest_lower([member], 101.0)["status"] == "no_level"
    low = {**member, **KL._member("week", "low", 100.0, "2026-09-25"), "side": "support"}
    assert KL.nearest_lower([low], 101.0)["status"] == "ranked"


def test_6_NEGATIVE_a_broken_low_never_ranks_the_next_one_does():
    df = _frame(pwl=100.0, pml=97.0)
    read, px = _read(df, KL.row_from_snapshot(_rth(99.5)))
    nl = KL.nearest_lower(read, px)
    assert nl["status"] == "ranked" and nl["nearest"]["label"] == "PML"
    assert [(t["label"], t["state"]) for t in nl["through"]] == [("PWL", "broken")]
    read, px = _read(df, KL.row_from_snapshot(_rth(96.0)))
    nl = KL.nearest_lower(read, px)
    assert nl["status"] == "broken" and nl["nearest"] is None
    assert {t["label"] for t in nl["through"]} == {"PWL", "PML"}


def test_7_NEGATIVE_closed_beyond_and_after_hours_through_never_rank():
    df = _frame(pwl=100.0, pml=None)
    read, px = _read(df, KL.row_from_snapshot(_snap(close=99.5, low=99.4, open_=101.0,
                                                    high=101.0, pdc=101.0)), now=AH)
    pwl = [m for m in read if m["label"] == "PWL"][0]
    assert pwl["state"] == "closed_beyond"
    assert KL.nearest_lower(read, px)["status"] == "broken"
    ah = _snap(px=99.5, at=AH, close=100.05, low=99.95, open_=101.0, high=101.0, pdc=101.0)
    read, px = _read(df, KL.row_from_snapshot(ah), now=AH)
    pwl = [m for m in read if m["label"] == "PWL"][0]
    assert pwl["state"] == "tested" and pwl["ah_through"] is True
    assert KL.nearest_lower(read, px)["status"] == "broken"


def test_8_NEGATIVE_rth_day_close_through_by_the_buffer_is_through():
    df = _frame(pwl=100.0, pml=None)
    stale = _snap(px=101.0, at=NOW, age_sec=900, open_=101.0, high=101.0, low=99.6,
                  close=99.7, pdc=101.0)
    read, px = _read(df, KL.row_from_snapshot(stale))
    pwl = [m for m in read if m["label"] == "PWL"][0]
    assert pwl["state"] == "pierced" and px == 99.7
    assert KL.is_through(pwl, px) is True
    assert KL.nearest_lower(read, px)["status"] == "broken"
    # NEGATIVE control: the day close back above the buffer is not through.
    assert KL.is_through({**pwl, "state": "pierced"}, 100.2) is False


def _rank(frames, snaps, now=NOW, first_seen=None):
    entry = _entry(frames, KL.levels_session(now))
    return KLT.rank(entry, snaps, now=now, first_seen=first_seen or {})


def test_9_a_print_inside_the_buffer_ranks_with_a_negative_distance_ordered_by_abs():
    frames = {"AAA": _frame(), "BBB": _frame(), "CCC": _frame()}
    snaps = {"AAA": _rth(99.9), "BBB": _rth(100.2), "CCC": _rth(100.05)}
    ranked, counts = _rank(frames, snaps)
    # by ABS distance: +0.05 before −0.10 before +0.20
    assert [r["symbol"] for r in ranked] == ["CCC", "AAA", "BBB"]
    assert ranked[0]["near"]["distance_pct"] == 0.05
    a, b = ranked[1]["near"], ranked[2]["near"]
    assert a["distance_pct"] == -0.10 and b["distance_pct"] == 0.2
    assert a["state"] == "tested"
    assert a["text"] == (f"🔑 0.10% under PWL 100.00 — not through ({KL.PIERCE_PCT:g}% "
                         "breaks it) · tested")
    assert "0.15% breaks it" in a["text"]
    assert b["text"] == "🔑 0.20% above PWL 100.00 · tested"


def test_10_distance_is_the_engines_dist_pct_flipped_and_zero_is_never_negative():
    frames = {"AAA": _frame(), "ZZZ": _frame()}
    snaps = {"AAA": _rth(100.43), "ZZZ": _rth(100.0)}
    ranked, _ = _rank(frames, snaps)
    by = {r["symbol"]: r["near"] for r in ranked}
    n = by["AAA"]
    assert n["distance_pct"] == round((n["print"] - n["price"]) / n["print"] * 100, 2) == 0.43
    read, px = _read(frames["AAA"], KL.row_from_snapshot(snaps["AAA"]))
    pwl = [m for m in read if m["label"] == "PWL"][0]
    assert n["distance_pct"] == -pwl["dist_pct"]
    z = by["ZZZ"]
    assert z["distance_pct"] == 0.0 and math.copysign(1.0, z["distance_pct"]) == 1.0
    assert z["text"].startswith("🔑 at PWL 100.00")
    assert "−" not in z["text"] and "-0.00" not in z["text"]


def test_11_NEGATIVE_the_partial_bar_feeds_no_level_no_last_bar_and_no_turnover():
    df = _frame(n=300)
    partial = pd.DataFrame({"open": 101.0, "high": 101.0, "low": 1.0, "close": 50.0,
                            "volume": 9e12}, index=pd.DatetimeIndex([pd.Timestamp("2026-09-29")]))
    with_partial = pd.concat([df, partial])
    entry = _entry({"AAA": with_partial})
    lv = entry["levels"]["AAA"]
    assert lv["last_date"] == "2026-09-28" and lv["ref_close"] == 101.0
    assert all(m["price"] > 1.0 for m in lv["levels"])
    assert lv["avg_dollar_vol_50"] == QB.avg_dollar_vol(df) == 101_000_000.0
    assert lv["last_bar"] == {}
    # the raw frame WOULD have produced all three from the partial bar
    assert QB.avg_dollar_vol(with_partial) != lv["avg_dollar_vol_50"]


def _aa(last_low=41.75, last_close=42.25, n=60):
    return _frame(n=n, close=43.0, pwl=42.25, pml=None,
                  sets={"2026-09-28": {"low": last_low, "close": last_close}})


def test_12_last_bar_read_carries_the_closed_session_past_the_roll():
    df = _aa()
    closed = KL.closed_frame(df, SESSION)
    pwl = [m for m in KL.period_levels(closed, SESSION, ("week",)) if m["kind"] == "low"][0]
    assert pwl["price"] == 42.25 and pwl["as_of"] == "2026-09-25"
    assert KL.last_bar_read(pwl, closed) == {"date": "2026-09-28", "state": "tested",
                                             "low_through_pct": 1.18}
    rev = KL.closed_frame(_aa(last_close=42.40), SESSION)
    assert KL.last_bar_read(pwl, rev)["state"] == "reversal"
    # through the rank, off-hours (after the 20:00 roll the live state is gone)
    ranked, _ = _rank({"AA": df}, {"AA": _snap(close=42.25, pdc=43.0)}, now=OFF)
    near = ranked[0]["near"]
    assert near["label"] == "PWL" and near["state"] is None and near["print_basis"] == "last_close"
    assert near["last_bar"] == {"date": "2026-09-28", "state": "tested", "low_through_pct": 1.18}
    assert "· Mon 09-28 tested (low went 1.18% under)" in near["text"]
    assert "last close" not in near["text"]            # off-hours: the header says it once


def test_13_NEGATIVE_last_bar_read_cases():
    df = _aa()
    closed = KL.closed_frame(df, SESSION)
    pwl = [m for m in KL.period_levels(closed, SESSION, ("week",)) if m["kind"] == "low"][0]
    # the bar inside the level's own period: PWL on the Monday after a Friday low
    mon = date(2026, 9, 28)
    fri = _frame(end="2026-09-25", close=43.0, pwl=41.0, pwl_day="2026-09-25", pml=None)
    closed_fri = KL.closed_frame(fri, mon)
    pwl_fri = [m for m in KL.period_levels(closed_fri, mon, ("week",)) if m["kind"] == "low"][0]
    assert pwl_fri["as_of"] == "2026-09-25"
    assert KL.last_bar_read(pwl_fri, closed_fri) is None
    # every 52wL: as_of IS the last bar
    big = KL.closed_frame(_aa(n=300), SESSION)
    yl = [m for m in KL.period_levels(big, SESSION, ("year",)) if m["kind"] == "low"][0]
    assert yl["as_of"] == "2026-09-28" and KL.last_bar_read(yl, big) is None
    # a bar whose low stayed more than AT_LEVEL_PCT above -> intact -> None
    far = KL.closed_frame(_aa(last_low=42.25 * (1 + (KL.AT_LEVEL_PCT + 0.2) / 100),
                              last_close=43.0), SESSION)
    assert KL.last_bar_read(pwl, far) is None
    # one closed bar -> None
    assert KL.last_bar_read(pwl, closed.tail(1)) is None
    # the last close through the level: closed_beyond is not carried, and the
    # low sits on the RESISTANCE side for the next read, so it never ranks.
    thru = _aa(last_close=41.9)
    assert KL.last_bar_read(pwl, KL.closed_frame(thru, SESSION)) is None
    ranked, counts = _rank({"AA": thru}, {"AA": _snap(close=41.9, pdc=43.0)}, now=OFF)
    assert ranked == [] and counts["no_level"] == 1


def test_14_a_low_made_in_the_last_session_is_ranked_and_flagged():
    # 52wL set on the last closed bar; PWL/PML above the last close (resistance)
    df = _frame(n=300, close=100.0, pwl=None, pml=None,
                sets={"2026-09-28": {"low": 99.5, "close": 99.6}})
    ranked, counts = _rank({"YYY": df}, {"YYY": _rth(99.65, ref=99.6)})
    near = ranked[0]["near"]
    assert near["label"] == "52wL" and near["set_on"] == "2026-09-28"
    assert near["set_last_session"] is True and counts["set_last_session"] == 1
    assert "· made Mon 09-28, the last session" in near["text"]
    # PWL with session Monday: the prior Friday made the week's low
    mon = datetime(2026, 9, 28, 11, 0, tzinfo=ET)
    fri = _frame(end="2026-09-25", pwl=100.0, pwl_day="2026-09-25", pml=None)
    ranked, counts = _rank({"FRI": fri}, {"FRI": _rth(100.3, at=mon)}, now=mon)
    near = ranked[0]["near"]
    assert near["label"] == "PWL" and near["set_last_session"] is True
    assert "made Fri 09-25, the last session" in near["text"]
    # NEGATIVE: a PWL set Wednesday of the prior week, session Tuesday -> False
    ranked, counts = _rank({"WED": _frame()}, {"WED": _rth(100.3)})
    near = ranked[0]["near"]
    assert near["set_on"] == "2026-09-23" and near["set_last_session"] is False
    assert counts["set_last_session"] == 0 and "made" not in near["text"]


# --------------------------------------------------------------------------
# rank / counts
# --------------------------------------------------------------------------
def test_15_closest_first_then_the_symbol_and_stable():
    frames = {s: _frame() for s in ("CCC", "BBB", "AAA", "DDD")}
    snaps = {"CCC": _rth(100.5), "BBB": _rth(100.3), "AAA": _rth(100.3), "DDD": _rth(101.0)}
    ranked, _ = _rank(frames, snaps)
    assert [r["symbol"] for r in ranked] == ["AAA", "BBB", "CCC", "DDD"]
    again, _ = _rank(frames, snaps)
    assert [r["symbol"] for r in again] == [r["symbol"] for r in ranked]
    assert [KLT.rank_key(r) for r in ranked] == sorted(KLT.rank_key(r) for r in ranked)


def test_16_NEGATIVE_no_snapshot_row_is_no_print_in_every_phase():
    frames = {"AAA": _frame()}
    ranked, counts = _rank(frames, {})
    assert ranked == [] and counts["no_print"] == 1
    ranked, counts = _rank(frames, {}, now=OFF)
    assert ranked == [] and counts["no_print"] == 1
    ranked, counts = _rank(frames, {"AAA": _snap(close=101.0, pdc=100.9)}, now=OFF)
    assert counts["ranked"] == 1 and ranked[0]["near"]["print_basis"] == "last_close"
    assert ranked[0]["near"]["print"] == 101.0 and ranked[0]["near"]["state"] is None


def test_17_NEGATIVE_a_snapshot_outage_ranks_nothing():
    frames = {"AAA": _frame(), "BBB": _frame(), "OLD": _frame(end="2026-09-22")}
    for now in (NOW, OFF):
        ranked, counts = _rank(frames, {}, now=now)
        assert ranked == [] and counts["ranked"] == 0
        assert counts["no_print"] == counts["scanned"] - counts["stale"] == 2


def test_18_NEGATIVE_a_row_with_nothing_to_verify_against_is_no_print():
    raw = {"last_trade_price": 100.5, "last_trade_ts_ms": _ms(NOW) - 30_000}
    ranked, counts = _rank({"AAA": _frame()}, {"AAA": raw})
    assert ranked == [] and counts["no_print"] == 1 and counts["stale"] == 0
    # off-hours too: never ranked on cached bars nothing checked
    off = {"last_trade_price": 100.5, "last_trade_ts_ms": _ms(OFF) - 30_000}
    ranked, counts = _rank({"AAA": _frame()}, {"AAA": off}, now=OFF)
    assert ranked == [] and counts["no_print"] == 1 and counts["stale"] == 0


def test_19_NEGATIVE_stale_by_date_and_a_verify_mismatch_are_stale_never_ranked():
    frames = {"OLD": _frame(end="2026-09-24"), "MIS": _frame()}
    snaps = {"OLD": _rth(100.5), "MIS": _rth(100.5, ref=102.0)}
    ranked, counts = _rank(frames, snaps)
    assert ranked == [] and counts["stale"] == 2


def test_20_the_counts_invariant_over_a_mixed_pool():
    frames = {"RNK": _frame(), "BRK": _frame(), "NOL": _frame(pwl=None, pml=None),
              "OLD": _frame(end="2026-09-22"), "NOP": _frame(), "MIS": _frame()}
    frames["NOL"]["low"] = 101.5        # every low above the last close: nothing below
    snaps = {"RNK": _rth(100.5), "BRK": _rth(96.0), "NOL": _rth(101.0),
             "OLD": _rth(100.5), "MIS": _rth(100.5, ref=103.0)}
    entry = _entry(frames)
    entry["syms"].append("NOENTRY")
    ranked, c = KLT.rank(entry, snaps, now=NOW, first_seen={})
    assert c == {"scanned": 7, "ranked": 1, "broken": 1, "no_level": 1, "stale": 3,
                 "no_print": 1, "set_last_session": 0}
    assert c["scanned"] == c["ranked"] + c["broken"] + c["no_level"] + c["stale"] + c["no_print"]


def test_21_off_hours_nothing_is_broken():
    frames = {s: _frame() for s in ("AAA", "BBB", "CCC")}
    snaps = {"AAA": _snap(close=101.0, pdc=100.9),
             "BBB": _snap(px=95.0, at=OFF, close=101.0, pdc=100.9),
             "CCC": _snap(px=99.0, at=OFF, age_sec=5, close=101.0, pdc=100.9)}
    ranked, counts = _rank(frames, snaps, now=OFF)
    assert counts["broken"] == 0 and counts["ranked"] == 3
    assert all(r["near"]["state"] is None for r in ranked)


# --------------------------------------------------------------------------
# memo
# --------------------------------------------------------------------------
def _patch_build(monkeypatch, frames, calls=None):
    real = KLT.build

    def fake(universe, session, **k):
        if calls is not None:
            calls.append((universe, session))
        return real(universe, session, universe_fn=lambda u: list(frames),
                    frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames})
    monkeypatch.setattr(KLT, "build", fake)


def test_22_cold_is_warming_then_a_sync_build_is_ready(monkeypatch, _clean_memo):
    _patch_build(monkeypatch, {"AAA": _frame()})
    got = KLT.cached_or_warm("full", now=NOW)
    assert got == {"state": "warming", "entry": None} and len(_clean_memo) == 1
    out = B.key_level_tiles(24, 130, "full", now=NOW)
    assert out["tiles"] == [] and out["warming"] is True and out["note"] == KLT.WARMING_NOTE
    kb = out["key_levels_board"]
    assert kb["state"] == "warming" and kb["counts"] is None and kb["header"] == KLT.WARMING_NOTE
    assert len(_clean_memo) == 1                        # the guard: still ONE build in flight
    got = KLT.cached_or_warm("full", now=NOW, sync=True)
    assert got["state"] == "ready" and got["entry"]["syms"] == ["AAA"]
    assert KLT.cached_or_warm("full", now=NOW)["entry"] is got["entry"]


def test_23_the_session_key_rolls_at_2000_and_the_ttl_serves_the_old_entry(monkeypatch, _clean_memo):
    calls = []
    _patch_build(monkeypatch, {"AAA": _frame()}, calls)
    a = KLT.cached_or_warm("full", now=datetime(2026, 9, 28, 19, 59, tzinfo=ET), sync=True)
    b = KLT.cached_or_warm("full", now=datetime(2026, 9, 28, 20, 1, tzinfo=ET), sync=True)
    assert a["entry"]["session"] == "2026-09-28" and b["entry"]["session"] == "2026-09-29"
    assert len(calls) == 2
    old = b["entry"]
    old["built_ts"] -= KLT.MEMO_TTL_SEC + 1
    n = len(_clean_memo)
    got = KLT.cached_or_warm("full", now=datetime(2026, 9, 28, 20, 2, tzinfo=ET))
    assert got["state"] == "ready" and got["entry"] is old
    KLT.cached_or_warm("full", now=datetime(2026, 9, 28, 20, 3, tzinfo=ET))
    assert len(_clean_memo) == n + 1                    # ONE rebuild scheduled
    # NEGATIVE: a fresh entry schedules nothing
    KLT._warming.clear()
    old["built_ts"] += KLT.MEMO_TTL_SEC + 1
    KLT.cached_or_warm("full", now=datetime(2026, 9, 28, 20, 4, tzinfo=ET))
    assert len(_clean_memo) == n + 1


def test_23b_NEGATIVE_an_empty_price_cache_read_raises_and_is_never_memoised(monkeypatch, _clean_memo):
    """Fix round 2026-09-28 (critic #1): `bulk_cached_frames` answers {} when
    Mongo is down. That must not become an hour of "every name has daily bars
    behind" — build raises, `_warm` stores nothing, clears its flag, and the
    next poll schedules a retry."""
    with pytest.raises(RuntimeError, match="no frames"):
        KLT.build("full", SESSION, universe_fn=lambda k: ["AAA", "BBB"],
                  frames_fn=lambda syms: {})
    with pytest.raises(RuntimeError):
        KLT.build("full", SESSION, universe_fn=lambda k: ["AAA"], frames_fn=lambda syms: None)
    # an empty universe is not a failed read: it builds (and ranks nothing)
    empty = KLT.build("full", SESSION, universe_fn=lambda k: [], frames_fn=lambda syms: {})
    assert empty["syms"] == [] and empty["levels"] == {}
    # one name missing from a non-empty read is still that name's stale note, not a raise
    part = KLT.build("full", SESSION, universe_fn=lambda k: ["AAA", "ZZZ"],
                     frames_fn=lambda syms: {"AAA": _frame()})
    assert part["levels"]["ZZZ"]["stale_note"] and not part["levels"]["AAA"]["stale_note"]

    real = KLT.build
    calls = []

    def blank(universe, session, **k):
        calls.append(session)
        return real(universe, session, universe_fn=lambda u: ["AAA", "BBB"],
                    frames_fn=lambda syms: {})
    monkeypatch.setattr(KLT, "build", blank)
    monkeypatch.setattr(KLT, "_spawn", lambda target, name: target())
    assert KLT.cached_or_warm("full", now=NOW) == {"state": "warming", "entry": None}
    assert KLT._memo == {} and KLT._warming == set()
    assert KLT.cached_or_warm("full", now=NOW)["state"] == "warming"
    assert len(calls) == 2                              # the next poll retried
    # an expired entry survives a failed rebuild (served, not replaced by a blank)
    monkeypatch.setattr(KLT, "build", real)
    _patch_build(monkeypatch, {"AAA": _frame()})
    monkeypatch.setattr(KLT, "_spawn", lambda target, name: None)
    old = KLT.cached_or_warm("full", now=NOW, sync=True)["entry"]
    old["built_ts"] -= KLT.MEMO_TTL_SEC + 1
    monkeypatch.setattr(KLT, "build", blank)
    monkeypatch.setattr(KLT, "_spawn", lambda target, name: target())
    got = KLT.cached_or_warm("full", now=NOW)
    assert got["state"] == "ready" and got["entry"] is old
    assert list(KLT._memo.values()) == [old] and KLT._warming == set()


def test_23c_NEGATIVE_a_late_old_session_build_never_evicts_the_new_session(monkeypatch, _clean_memo):
    """Fix round 2026-09-28 (critic #2): at 19:59 an expired S entry starts a
    rebuild; the S+1 build lands first at 20:00; the S build landing second
    must neither be stored nor evict S+1."""
    monkeypatch.setattr(KLT, "_spawn", lambda target, name: target())
    _patch_build(monkeypatch, {"AAA": _frame()})
    s_key = ("2026-09-28", "full")
    s1_key = ("2026-09-29", "full")
    KLT._warm(s1_key, "full", date(2026, 9, 29))
    new = KLT._memo[s1_key]
    KLT._warm(s_key, "full", date(2026, 9, 28))            # the late one
    assert list(KLT._memo) == [s1_key] and KLT._memo[s1_key] is new
    assert KLT._warming == set()
    # positive: a NEWER session landing evicts the older one
    KLT._memo.clear()
    KLT._warm(s_key, "full", date(2026, 9, 28))
    KLT._warm(s1_key, "full", date(2026, 9, 29))
    assert list(KLT._memo) == [s1_key]
    # same session, another universe: both kept
    KLT._warm(("2026-09-29", "sp1500"), "sp1500", date(2026, 9, 29))
    assert set(KLT._memo) == {s1_key, ("2026-09-29", "sp1500")}


def test_24_one_frames_read_per_build_one_closed_cut_per_name_and_no_writes(monkeypatch):
    frames = {s: _frame() for s in ("AAA", "BBB", "CCC")}
    reads, cuts = [], []
    real_cut = KL.closed_frame
    monkeypatch.setattr(KL, "closed_frame", lambda df, s: cuts.append(1) or real_cut(df, s))
    entry = KLT.build("full", SESSION, universe_fn=lambda k: list(frames),
                      frames_fn=lambda syms: reads.append(list(syms)) or frames)
    assert reads == [["AAA", "BBB", "CCC"]] and len(cuts) == 3
    assert set(entry["levels"]) == {"AAA", "BBB", "CCC"} and isinstance(entry["built_at"], str)
    src = (BACKEND / "chart_maps" / "key_levels_tab.py").read_text(encoding="utf-8")
    assert not re.search(r"insert_|update_|replace_|delete_|bulk_write|create_index|open\(", src)
    assert "UNMEASURED" in src and "QB.avg_dollar_vol(closed)" in src
    # the house engine's module name is an identifier (it keeps its word); no
    # served or written word here says it
    assert not re.search("bounc", src.replace("quick_bounce", ""), re.I)
    assert src.count("quick_bounce") == 1


# --------------------------------------------------------------------------
# board / api
# --------------------------------------------------------------------------
class _Fixed(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


@pytest.fixture
def kl_board(monkeypatch):
    """The key_levels tab through board() with every decorator stubbed and
    the memo seeded synchronously. `state` records the fan-outs."""
    from sepa import scanner
    state = {"frames": {}, "snaps": {}, "scan": [], "snap_calls": [], "fs_calls": [],
             "fs": {"sentinel": "first-seen"}, "attach": {}, "rank_now": []}

    def _snaps(syms):
        state["snap_calls"].append(sorted(syms))
        return {s: state["snaps"][s] for s in syms if s in state["snaps"]}

    def _fs(session_iso, coll=None):
        state["fs_calls"].append(session_iso)
        return state["fs"]

    def _bars(tiles, days, **k):
        for t in tiles:
            t["bars"] = [{"t": "2026-09-28", "o": 1, "h": 1, "l": 1, "c": 1, "v": 1}]

    real_rank = KLT.rank

    def _rank_spy(entry, raw, *, now, first_seen):
        state["rank_now"].append(now)
        return real_rank(entry, raw, now=now, first_seen=first_seen)

    real_attach = B.attach_key_levels

    def _attach_spy(tiles, out=None, **kw):
        state["attach"] = kw
        return real_attach(tiles, out, **kw)

    monkeypatch.setattr(B, "datetime", _Fixed)
    monkeypatch.setattr(B, "_bulk_snaps", _snaps)
    monkeypatch.setattr(KL, "read_first_seen", _fs)
    monkeypatch.setattr(KLT, "rank", _rank_spy)
    monkeypatch.setattr(scanner, "load_latest", lambda *a, **k: {"all_results": state["scan"]})
    monkeypatch.setattr(B, "_attach_bars", _bars)
    monkeypatch.setattr(B, "attach_explosive", lambda tiles: 0)
    monkeypatch.setattr(B, "attach_velocity", lambda tiles, **k: 0)
    monkeypatch.setattr(B, "_velocity_decor", lambda tiles: None)
    monkeypatch.setattr(B, "_name_for", lambda s: f"{s} Inc")
    monkeypatch.setattr(B, "attach_live_now", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(B, "attach_enterable", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "attach_band_structure", lambda tiles, kind="demand", **k: 0)
    monkeypatch.setattr(B, "band_structure_coverage", lambda tiles, kind="demand": {})
    monkeypatch.setattr(B, "attach_burst", lambda tiles, out=None, **k: {})
    monkeypatch.setattr(B, "_burst_frames", lambda syms: {s: state["frames"][s] for s in syms
                                                          if s in state["frames"]})
    monkeypatch.setattr(B, "attach_key_levels", _attach_spy)

    def seed(frames, snaps, scan=()):
        state["frames"], state["snaps"], state["scan"] = frames, snaps, list(scan)
        _patch_build(monkeypatch, frames)
        KLT.cached_or_warm("full", now=NOW, sync=True)
    state["seed"] = seed
    return state


def test_25_the_tab_through_board_one_snapshot_one_first_seen_rank_order(kl_board):
    assert "key_levels" in B.TABS and B.TABS[-1] == "key_levels"
    frames = {s: _frame() for s in ("AAA", "BBB", "CCC", "DDD")}
    kl_board["seed"](frames, {"AAA": _rth(100.9), "BBB": _rth(100.2), "CCC": _rth(96.0),
                              "DDD": _rth(100.5)})
    out = B.board(tab="key_levels", limit=24)
    assert len(kl_board["snap_calls"]) == 1 and kl_board["snap_calls"][0] == sorted(frames)
    assert kl_board["fs_calls"] == ["2026-09-29"]
    assert [t["symbol"] for t in out["tiles"]] == ["BBB", "DDD", "AAA"]
    c = out["key_levels_board"]["counts"]
    assert c["ranked"] == 3 and c["broken"] == 1 and c["shown"] == 3
    assert c["dropped_thin"] == 0 and c["no_turnover"] == 0 and out["matched"] == 3
    assert out["note"] == KLT.NOTE and out["tab"] == "key_levels"
    t = out["tiles"][0]
    assert t["badges"][0]["text"] == t["key_level_near"]["text"] and t["name"] == "BBB Inc"
    assert "_m" not in t and "_score" not in t
    assert "key_levels" in t                           # the 2026-09-25 block, as on every tab
    assert out["key_levels_board"]["state"] == "ready" and out["key_levels_board"]["measured"] is False
    assert out["key_levels_board"]["periods"] == ["PWL", "PML", "52wL"]
    # NEGATIVE: the limit cuts the page, never the counts
    out = B.board(tab="key_levels", limit=1)
    assert [t["symbol"] for t in out["tiles"]] == ["BBB"]
    assert out["key_levels_board"]["counts"]["shown"] == 1 and out["matched"] == 3


def test_26_turnover_falls_back_to_the_closed_frame(kl_board):
    from supply_demand.demand_reentry import LIQ_OK_USD
    frames = {"FRM": _frame(volume=200_000.0),                 # $20.2M, no scan row
              "SCN": _frame(volume=200_000.0),                 # scan row says $55M
              "NON": _frame(volume=np.nan),                    # neither
              "THN": _frame(volume=10_000.0)}                  # $1M, under the floor
    snaps = {s: _rth(100.5) for s in frames}
    scan = [{"symbol": "SCN", "liquidity": {"avg_dollar_vol": 55e6}}]
    kl_board["seed"](frames, snaps, scan)
    out = B.board(tab="key_levels", limit=24, min_tier="ok")
    by = {t["symbol"]: t for t in out["tiles"]}
    closed = KL.closed_frame(frames["FRM"], SESSION)
    assert by["FRM"]["avg_turnover"] == QB.avg_dollar_vol(closed) >= LIQ_OK_USD
    assert by["SCN"]["avg_turnover"] == 55e6
    assert "NON" not in by and "THN" not in by
    c = out["key_levels_board"]["counts"]
    assert c["no_turnover"] == 1 and c["dropped_thin"] == 1 and out["matched"] == 2
    out = B.board(tab="key_levels", limit=24, min_tier="any")
    c = out["key_levels_board"]["counts"]
    assert {t["symbol"] for t in out["tiles"]} == set(frames)
    assert c["no_turnover"] == 0 and c["dropped_thin"] == 0 and out["matched"] == 4


def test_27_one_clock_and_one_first_seen_read_for_badge_and_line(kl_board, monkeypatch):
    kl_board["seed"]({"AAA": _frame()}, {"AAA": _rth(100.5)})
    B.board(tab="key_levels", limit=24)
    kw = kl_board["attach"]
    assert kw["per_side"] == KL.SUPPORT_PER_SIDE == KLT.DRAW_PER_SIDE
    assert kw["now"] is kl_board["rank_now"][-1] and kw["now"] == NOW
    assert kw["first_seen"] is kl_board["fs"]
    # NEGATIVE: every other tab keeps the grid cap, its own clock, its own read
    monkeypatch.setattr(B, "earnings_tiles",
                        lambda limit, days: {"tiles": [{"symbol": "AAA", "bars": [], "lines": []}]})
    B.board(tab="earnings", limit=5)
    kw = kl_board["attach"]
    assert kw["per_side"] is None and kw["now"] is None and kw["first_seen"] is None
    src = inspect.getsource(B.board)
    assert 'now=_ctx.get("now")' in src and 'first_seen=_ctx.get("first_seen")' in src


def test_28_the_default_sort_is_labelled_for_this_tab_only(kl_board, monkeypatch):
    kl_board["seed"]({"AAA": _frame()}, {"AAA": _rth(100.5)})
    out = B.board(tab="key_levels", limit=24)
    labels = {s["key"]: s["label"] for s in out["sorts"]}
    assert labels["default"] == KLT.DEFAULT_SORT_LABEL
    monkeypatch.setattr(B, "vcp_tiles", lambda *a, **k: {"tiles": []})
    out = B.board(tab="vcp", limit=24)
    assert {s["key"]: s["label"] for s in out["sorts"]}["default"] == "⭐ Best setup first"


def test_29_payload_is_json_safe_and_the_words_are_honest(kl_board):
    frames = {"AAA": _frame(), "BBB": _frame()}
    kl_board["seed"](frames, {"AAA": _rth(99.9), "BBB": _rth(100.4)})
    out = B.board(tab="key_levels", limit=24)
    json.dumps(out, allow_nan=False)
    kb = out["key_levels_board"]
    assert isinstance(kb["built_at"], str)
    header = kb["header"]
    assert f"within the {KL.PIERCE_PCT:g}% break buffer" in header
    assert "intact" not in header.lower()
    assert "UNMEASURED" in KLT.NOTE and kb["note"] == KLT.NOTE
    from supply_demand import rules_info as RI
    pick = [p for p in RI._key_levels_section()["picks"] if "Key Levels tab" in p]
    assert len(pick) == 1 and "UNMEASURED" in pick[0] and "PWL / PML / 52wL" in pick[0]
    texts = [header, KLT.NOTE, KLT.WARMING_NOTE, KLT.EMPTY_NOTE, pick[0], KLT.DEFAULT_SORT_LABEL,
             *(t["key_level_near"]["text"] for t in out["tiles"])]
    for s in texts:
        assert "bounc" not in s.lower(), s
        assert "nan" not in s.lower().split() and "None" not in s
    # the header's numbers are the served counts
    c = kb["counts"]
    assert header.startswith(f"🔑 {c['ranked']} names sit above")
    assert f"showing {c['shown']}." in header
    # NEGATIVE: an explicit sort says so; the default does not
    out = B.board(tab="key_levels", limit=24, sort="rvol")
    assert "(your pick), closest first breaks ties" in out["key_levels_board"]["header"]
    assert "(your pick)" not in header


def test_29b_empty_board_serves_the_empty_note(kl_board):
    kl_board["seed"]({"AAA": _frame()}, {"AAA": _rth(96.0)})
    out = B.board(tab="key_levels", limit=24)
    assert out["tiles"] == [] and out["note"] == KLT.EMPTY_NOTE
    assert out["key_levels_board"]["counts"]["broken"] == 1


def test_30_the_ranking_and_the_decorator_read_the_same_row():
    from sepa import prices
    for raw in (_rth(100.5), _snap(close=101.0, pdc=100.9),
                _snap(px=99.0, at=OFF, close=101.0, pdc=100.9, low=98.0, high=102.0, open_=100.0)):
        live = prices.bulk_live_prices(["AAA"], snaps={"AAA": raw})["AAA"]
        assert KL.row_from_snapshot(raw) == KL.row_from_live(live)


def test_api_describes_the_tab():
    from chart_maps import api as A
    src = inspect.getsource(A.chart_maps)
    assert "key_levels" in src
