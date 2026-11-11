"""Formulas audit D3 (2026-11-11) — the 🌙 K10 clock and the pass tape session read the house calendar.

Before: `context._post_minutes` used a fixed 09:30–15:59 regular / 16:01–19:59 after-hours clock and
`scanner.pass_tape_session` read exchange hours only, so on a NYSE half day (regular close 13:00, extended close 17:00)
the 13:01–15:59 after-hours minutes were read as the regular session (demo `L3/k10_half_day.py`: close_pos 0.40 instead
of 0.90, after-hours volume 148,117 instead of 600,000) and the 17:01–20:05 passes read "afterhours".
After: both read `alerts._closes(session)`. A normal day is byte-identical (frozen tables below, copied from the HEAD
192baf63 functions). Step B1 of the defects spec; B2 (the D11 scanner line) is NOT in this file.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import context as CX
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import scanner as SC
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_run import make_deps, minutes_from_5m, snap_row
from tests.test_gajjala_store import fake_store

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
NORMAL = date(2026, 11, 25)
HALF = date(2026, 11, 27)
HALF2 = date(2026, 12, 24)
HOLIDAY = date(2026, 11, 26)
PREV_OF_HALF = date(2026, 11, 25)                       # 11-26 = Thanksgiving
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def at(hh, mm, d=HALF):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET)


# ── the demo frame (eod-audits/research/2026-11-10_formulas_audit/demos/L3/k10_half_day.py, copied verbatim) ────────
def demo_minutes(day, rth_close_hhmm, ah_end_hhmm):
    """RTH: 10.00–11.00, closing 10.90 (top 10% of the range). After hours: runs to 12.50 on 600,000 shares."""
    rows, idx = [], []
    t = datetime.combine(day, datetime.min.time(), tzinfo=ET).replace(hour=9, minute=30)
    close = t.replace(hour=rth_close_hhmm[0], minute=rth_close_hhmm[1])
    end = t.replace(hour=ah_end_hhmm[0], minute=ah_end_hhmm[1])
    n_rth = int((close - t).total_seconds() // 60)
    n_ah = int((end - close).total_seconds() // 60) - 1            # the closing-cross minute carries no AH volume here
    for k in range(n_rth):
        px = 10.0 + 0.9 * k / (n_rth - 1)
        rows.append({"open": px, "high": min(11.0, px + 0.1), "low": max(10.0, px - 0.02), "close": px, "volume": 5_000})
        idx.append(t + timedelta(minutes=k))
    rows.append({"open": 10.9, "high": 10.9, "low": 10.9, "close": 10.9, "volume": 40_000})   # closing cross minute
    idx.append(close)
    for k in range(n_ah):
        px = 11.5 + 1.0 * k / (n_ah - 1)
        rows.append({"open": px, "high": px, "low": px - 0.02, "close": px, "volume": 600_000 / n_ah})
        idx.append(close + timedelta(minutes=k + 1))
    return pd.DataFrame(rows, index=pd.DatetimeIndex([x.astimezone(UTC).replace(tzinfo=None) for x in idx]))


CAND = [{"symbol": "HALF", "price": 12.4, "day_c": 10.9, "prev_close": 9.0, "ah_move_pct": 13.76}]


def confirm(day, df):
    return CX.postmarket_confirm(CAND, {}, lambda s: df, session=day,
                                 now=datetime.combine(day, datetime.min.time(), tzinfo=ET).replace(hour=16, minute=31))


# ── _post_clock / _post_minutes ───────────────────────────────────────────────────────────────────────────────────
def test_post_clock_reads_the_house_calendar():
    assert CX._post_clock(NORMAL) == (dtime(9, 30), dtime(15, 59), dtime(16, 1), dtime(20, 0))
    assert CX._post_clock(HALF) == (dtime(9, 30), dtime(12, 59), dtime(13, 1), dtime(17, 0))
    assert CX._post_clock(HALF2) == CX._post_clock(HALF)
    assert CX._post_clock(HALF.isoformat()) == CX._post_clock(HALF)          # a string session reads the same
    rth_close, ext_close = AL._closes(HALF)                                  # one engine: alerts._closes
    assert CX._post_clock(HALF)[3] == ext_close and CX._post_clock(HALF)[2] > rth_close


@pytest.mark.parametrize("day", [HALF, HALF2])
def test_half_day_post_minutes_split_at_13_00(day):
    m = CX._post_minutes(demo_minutes(day, (13, 0), (17, 0)), day)
    assert m["rth_high"] == 11.0 and m["rth_low"] == 10.0 and m["close_1559"] == 10.9
    assert m["ah_volume"] == pytest.approx(600_000)


@pytest.mark.parametrize("day", [HALF, HALF2])
def test_half_day_postmarket_confirm_lists_HALF_at_close_pos_0_9(day):
    rows, unchecked = confirm(day, demo_minutes(day, (13, 0), (17, 0)))
    assert unchecked == 0 and [r["symbol"] for r in rows] == ["HALF"]
    assert rows[0]["close_pos"] == 0.9 and rows[0]["rth_high"] == 11.0
    assert rows[0]["ah_volume"] == pytest.approx(600_000)


# Frozen from the HEAD 192baf63 function on the same frame (the fixed 15:59 / 16:01 / 20:00 clock).
HEAD_NORMAL_POST = {"rth_high": 11.0, "rth_low": 10.0, "close_1559": 10.9, "ah_volume": 600000.000000002}


def test_NEGATIVE_normal_day_post_minutes_byte_equal_to_head():
    df = demo_minutes(NORMAL, (16, 0), (20, 0))
    assert CX._post_minutes(df, NORMAL) == HEAD_NORMAL_POST
    rows, unchecked = confirm(NORMAL, df)
    assert unchecked == 0 and len(rows) == 1
    r = rows[0]
    assert (r["close_pos"], r["reg_close"], r["reg_close_src"], r["rth_high"], r["rth_low"], r["ah_volume"],
            r["ah_gain_pct"], r["reg_gain_pct"], r["checked_text"]) == (
        0.9, 10.9, "snapshot_day_c", 11.0, 10.0, 600000.000000002, 13.76, 21.11, "checked 16:31 ET")


def _one_min_frame(day, bars):
    """bars = [(HH, MM, high, low, close, volume)] → the 1-minute frame (naive UTC, index = minute START)."""
    idx = [datetime(day.year, day.month, day.day, h, m, tzinfo=ET).astimezone(UTC).replace(tzinfo=None)
           for h, m, *_ in bars]
    rows = [{"open": c, "high": hi, "low": lo, "close": c, "volume": v} for _h, _m, hi, lo, c, v in bars]
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


def test_NEGATIVE_half_day_closing_cross_and_after_extended_close_minutes_are_excluded():
    """13:00 (the closing-cross minute, T7) is neither regular nor after-hours; 17:00 is past the extended close; a
    13:30 print belongs to after-hours (its high never stretches the regular range)."""
    df = _one_min_frame(HALF, [(9, 30, 10.5, 10.0, 10.2, 1_000), (12, 59, 10.8, 10.4, 10.7, 1_000),
                               (13, 0, 99.0, 1.0, 50.0, 9_000_000), (13, 1, 11.0, 10.9, 11.0, 300),
                               (13, 30, 20.0, 10.9, 19.0, 400), (16, 59, 12.0, 11.9, 12.0, 500),
                               (17, 0, 13.0, 12.9, 13.0, 7_000_000)])
    m = CX._post_minutes(df, HALF)
    assert m == {"rth_high": 10.8, "rth_low": 10.0, "close_1559": 10.7, "ah_volume": 1_200.0}


def test_NEGATIVE_normal_day_closing_cross_still_excluded():
    df = _one_min_frame(NORMAL, [(9, 30, 10.5, 10.0, 10.2, 1_000), (13, 30, 10.9, 10.1, 10.6, 1_000),
                                 (15, 59, 10.8, 10.4, 10.7, 1_000), (16, 0, 99.0, 1.0, 50.0, 9_000_000),
                                 (16, 1, 11.0, 10.9, 11.0, 300), (19, 59, 12.0, 11.9, 12.0, 500),
                                 (20, 0, 13.0, 12.9, 13.0, 7_000_000)])
    assert CX._post_minutes(df, NORMAL) == {"rth_high": 10.9, "rth_low": 10.0, "close_1559": 10.7, "ah_volume": 800.0}


# ── pass_tape_session ─────────────────────────────────────────────────────────────────────────────────────────────
HALF_GRID = [((12, 55), "rth"), ((13, 0), "afterhours"), ((13, 5), "afterhours"), ((16, 55), "afterhours"),
             ((17, 3), "afterhours"), ((17, 5), "afterhours"), ((17, 6), "closed"), ((19, 55), "closed"),
             ((20, 1), "closed"), ((20, 5), "closed")]


@pytest.mark.parametrize("day", [HALF, HALF2])
@pytest.mark.parametrize("hhmm,want", HALF_GRID)
def test_half_day_pass_tape_session(day, hhmm, want):
    assert SC.pass_tape_session(at(*hhmm, d=day)) == want


# Frozen from the HEAD 192baf63 `pass_tape_session` (exchange hours + the 20:00–20:05 after-hours grace): a normal
# day, the Thanksgiving holiday (the house calendar gives it the normal closes), a weekend day, and the existing cases
# of tests/test_gajjala_scanner.py (S = 2026-10-13, 2026-10-17 = a Saturday).
HEAD_GRID = {
    NORMAL: {(3, 59): "closed", (4, 0): "premarket", (4, 1): "premarket", (9, 29): "premarket", (9, 30): "rth",
             (12, 59): "rth", (13, 0): "rth", (13, 5): "rth", (15, 59): "rth", (16, 0): "afterhours",
             (16, 1): "afterhours", (17, 0): "afterhours", (17, 6): "afterhours", (19, 59): "afterhours",
             (20, 0): "afterhours", (20, 1): "afterhours", (20, 5): "afterhours", (20, 6): "closed",
             (23, 59): "closed"},
    HOLIDAY: {(9, 30): "rth", (13, 0): "rth", (15, 59): "rth", (16, 0): "afterhours", (17, 6): "afterhours",
              (20, 0): "afterhours", (20, 5): "afterhours", (20, 6): "closed"},
    date(2026, 11, 28): {(9, 30): "closed", (13, 0): "closed", (16, 0): "closed", (20, 1): "closed"},
    date(2026, 10, 13): {(4, 1): "premarket", (9, 31): "rth", (16, 1): "afterhours", (20, 1): "afterhours",
                         (20, 5): "afterhours", (20, 6): "closed", (3, 59): "closed"},
    date(2026, 10, 17): {(20, 1): "closed"},
}


@pytest.mark.parametrize("day,hhmm,want", [(d, k, v) for d, g in HEAD_GRID.items() for k, v in g.items()])
def test_NEGATIVE_normal_day_pass_tape_session_equal_to_head(day, hhmm, want):
    assert SC.pass_tape_session(at(*hhmm, d=day)) == want


def test_NEGATIVE_utc_and_naive_clocks_read_the_same_half_day():
    utc = at(17, 5).astimezone(ZoneInfo("UTC"))
    assert SC.pass_tape_session(utc) == "afterhours"
    assert SC.pass_tape_session(utc + timedelta(minutes=1)) == "closed"
    assert SC.pass_tape_session(datetime(2026, 11, 27, 13, 0)) == "afterhours"       # naive = ET


def test_the_grace_is_derived_from_PASS_CLOSE_ET(monkeypatch):
    """The 5-minute grace = PASS_CLOSE_ET − ET_AFTERHOURS_CLOSE, never typed: a shorter pass window shortens it on
    BOTH day kinds."""
    monkeypatch.setattr(GC, "PASS_CLOSE_ET", "20:03")
    assert SC.pass_tape_session(at(20, 3, d=NORMAL)) == "afterhours"
    assert SC.pass_tape_session(at(20, 4, d=NORMAL)) == "closed"
    assert SC.pass_tape_session(at(17, 3)) == "afterhours"
    assert SC.pass_tape_session(at(17, 4)) == "closed"


def test_source_guard_no_fixed_clock_left():
    for name in ("scanner.py", "context.py"):
        src = (BACKEND / "chart_maps" / "gajjala" / name).read_text()
        for bad in ("20 * 60", "dtime(15, 59)", "dtime(16, 1)", "dtime(20, 0)", "_RTH_LAST", "_AH_FIRST", "_AH_END"):
            assert bad not in src, f"{name}: {bad}"


@pytest.mark.parametrize("mod", ["chart_maps.gajjala.context", "chart_maps.gajjala.scanner",
                                 "chart_maps.gajjala.squeeze_marks"])
def test_fresh_interpreter_imports_without_a_cycle(mod):
    r = subprocess.run([sys.executable, "-B", "-c", f"import {mod}"], cwd=str(BACKEND), capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]


# ── scan_rows on a half day ───────────────────────────────────────────────────────────────────────────────────────
TYPES = {"GGA": "CS"}


def test_half_day_scan_rows_carry_only_before_the_extended_close():
    rows = {"GGA": snap_row(13.0, 8.0, when=at(17, 2), close=11.2)}
    live = SC.scan_rows(rows, at(17, 3), HALF, types=TYPES)
    assert live["tape_session"] == "afterhours"
    assert [r["symbol"] for r in live["ah_carry"]] == ["GGA"] and [r["symbol"] for r in live["k10_candidates"]] == ["GGA"]
    rows = {"GGA": snap_row(13.0, 8.0, when=at(17, 29), close=11.2)}
    late = SC.scan_rows(rows, at(17, 30), HALF, types=TYPES)
    assert late["tape_session"] == "closed"
    assert late["ah_carry"] is None and late["k10_candidates"] == []


def test_half_day_14_00_reads_after_hours_not_rth():
    rows = {"GGA": snap_row(13.0, 8.0, when=at(13, 59), close=11.2)}
    res = SC.scan_rows(rows, at(14, 0), HALF, types=TYPES)
    assert res["tape_session"] == "afterhours" and [r["symbol"] for r in res["ah_carry"]] == ["GGA"]


# ── the closed-tape pass on a half day (spec C6) ──────────────────────────────────────────────────────────────────
def _half_day_deps(hh, mm):
    """An A+ bull flag whose bars run 16:45–17:25 on the half day (entry bar after the 17:00 extended close)."""
    prior = minutes_from_5m(FX.warm(), PREV_OF_HALF, "14:00")
    today = minutes_from_5m(FX.bf_bars(), HALF, "16:45", session="afterhours")
    rows = {"GGA": snap_row(13.0, 8.0, when=at(hh, mm - 1), close=11.2)}
    deps, _snap, send, _status = make_deps(rows=rows,
                                           load=lambda s, d: prior.copy() if d == PREV_OF_HALF else today.copy())
    deps.trader_posts = lambda key: []
    return deps, send


def test_half_day_closed_tape_pass_is_inert():
    st = fake_store()
    deps, send = _half_day_deps(17, 3)
    twin = RUN.run_pass(at(17, 3), store=st, deps=deps, dry=False)       # the last after-hours pass
    assert twin["tape_session"] == "afterhours" and twin["ah_carry"] == "replaced"
    assert isinstance(twin["postmarket"], dict)                          # 🌙 confirm ran
    carry = st.ah_carry(HALF)
    assert carry["names"]["GGA"]["ah_move_pct"] > GC.K9_AH_CARRY_PCT

    deps2, send2 = _half_day_deps(17, 30)
    out = RUN.run_pass(at(17, 30), store=st, deps=deps2, dry=False)
    assert out["ran"] and out["status"] == "ok" and out["tape_session"] == "closed"
    assert out["ah_carry"] == "skipped"
    assert st.ah_carry(HALF) == carry                                    # the 17:03 carry still decides Monday's ☀️
    assert out["postmarket"] is None and st.latest_pass()["postmarket"] is None   # no 🌙 rows
    sessions = {d["symbol"]: d.get("sessions") for d in st.scan_docs([HALF])}
    assert sessions["GGA"].get("closed") is True and sessions["GGA"].get("afterhours") is True
    # a fresh A+ whose entry bar closes after the half-day extended close never rings
    assert "GGA:bull_flag" in out["aplus"] and out["alerts"]["suppressed_window"] == 1
    assert out["alerts"]["pushed"] == 0
    assert send.calls == [] and send2.calls == []
    assert deps.send_potential.calls == [] and deps2.send_potential.calls == []
