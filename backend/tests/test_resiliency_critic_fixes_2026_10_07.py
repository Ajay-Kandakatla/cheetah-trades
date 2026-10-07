"""🛡️ Resiliency — critic follow-ups (2026-10-07).

1. The live / after-close session move is measured against the snapshot's
   OFFICIAL prior close (`prev_day_close`) when it agrees with the cached close
   within `drop10_tab.PREV_CLOSE_TOL_PCT` and the snapshot is dated the
   session. Real case: NNBR cached 10-06 close 4.025 vs official 4.04 — the
   card said -0.12%, the real move was -0.50% (the 0.5% hold line). Closed mode
   and a data day's pre-market are unchanged.
2. A stored sales % with no revenue series is never ranked.
3. The market line in closed mode with the cached bars behind (host sleep)
   says the bars are behind, never "no print".
4. `rank()` serves the MEDIAN move and counts only moves above zero as up.

Every NEGATIVE fails if its line is reverted. Hermetic (fixtures injected).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from chart_maps import drop10_tab as D10
from chart_maps import resiliency_tab as R
from tests.test_resiliency_tab import (ET, LAST, NOW, PRE, SESSION, SNAPS, _ms,  # noqa: F401
                                       _pre, _rth)
from tests.test_resiliency_today_growth_2026_10_07 import (AFTER, GOLDEN, NO_CAL, VST, WED21,
                                                           _closed_frames, _closed_snap, _entry,
                                                           _fund)


def _after(close, *, pdc, at=AFTER - timedelta(minutes=20)):
    """An after-close snapshot rolled to the session: day bar + official prior close."""
    return {"open": pdc, "high": max(close, pdc) + 0.05, "low": min(close, pdc) - 0.05,
            "close": close, "volume": 2_000_000, "last_trade_price": close,
            "last_trade_ts_ms": _ms(at), "prev_day_close": pdc,
            "min_t_ms": _ms(at - timedelta(minutes=1))}


# --------------------------------------------------------------------------
# 1 — the official prior close
# --------------------------------------------------------------------------
def test_after_close_nnbr_measures_against_the_official_prior_close():
    row = _after(4.021, pdc=4.04)
    t = R.today_read(row, ref_close=4.025, ref_date=LAST, now=AFTER, session=SESSION,
                     phase="close", event=None)
    assert t["state"] == "read" and t["mode"] == "after_close"
    assert t["move_pct"] == R.pct_ret(4.021, 4.04) == -0.47
    assert t["move_pct"] != R.pct_ret(4.021, 4.025)               # the cached base: -0.10%
    assert t["prev_close"] == 4.04
    assert R._today_stat(t).startswith("-0.47% vs 4.04 · ")


def test_live_rth_measures_against_the_official_prior_close():
    row = _rth(4.021, ref=4.04)                                   # prev_day_close 4.04
    t = R.today_read(row, ref_close=4.025, ref_date=LAST, now=NOW, session=SESSION,
                     phase="rth", event=None)
    assert t["state"] == "read" and t["basis"] == "live"
    assert t["move_pct"] == -0.47 and t["prev_close"] == 4.04


def test_NEG_official_close_tolerance_is_drop10s():
    tol = D10.PREV_CLOSE_TOL_PCT
    ref = 50.0
    inside = round(ref * (1 + (tol - 0.1) / 100.0), 4)
    outside = round(ref * (1 + (tol + 0.1) / 100.0), 4)
    assert R.official_prev_close(_after(50.0, pdc=inside), ref, SESSION) == inside
    assert R.official_prev_close(_after(50.0, pdc=outside), ref, SESSION) == ref
    # through today_read: a split-sized disagreement keeps the cached close
    t = R.today_read(_after(50.0, pdc=outside), ref_close=ref, ref_date=LAST, now=AFTER,
                     session=SESSION, phase="close", event=None)
    assert t["prev_close"] == ref and t["move_pct"] == 0.0


def test_NEG_no_or_bad_prev_day_close_keeps_the_cached_close():
    for pdc in (None, 0, -1.0, "x"):
        row = {**_after(50.5, pdc=50.0), "prev_day_close": pdc}
        assert R.official_prev_close(row, 50.0, SESSION) == 50.0
    assert R.official_prev_close(None, 50.0, SESSION) == 50.0
    assert R.official_prev_close(_after(50.5, pdc=50.2), None, SESSION) is None


def test_NEG_unrolled_snapshot_never_supplies_the_base():
    """A snapshot still dated the PRIOR session carries the close two days back as
    prev_day_close — never the base for today's move."""
    y = datetime(2026, 9, 29, 15, 59, tzinfo=ET)
    row = _after(50.0, pdc=49.8, at=y)                            # stamped Tue, session Wed
    assert R.official_prev_close(row, 50.0, SESSION) == 50.0


def test_NEG_closed_mode_is_unchanged_by_the_official_close():
    fr = _closed_frames(moves={"AAA": 50.5})
    e = _entry(fr, session=date(2026, 10, 1), cal={"macro": []})
    at = datetime(2026, 9, 30, 19, 59, tzinfo=ET)
    snap = {**_closed_snap(50.5, 50.2, at)}                       # official prior 50.20 (+0.40% off)
    rows, *_ = R.rank(e, {"AAA": snap}, None, now=WED21, sort="default")
    td = rows[0]["resiliency"]["today"]
    assert td["state"] == "read" and td["basis"] == R.LAST_BASIS
    assert td["move_pct"] == 1.0 and td["prev_close"] == 50.0     # the closed bars, not 50.20


def test_NEG_data_day_premarket_keeps_the_cached_close():
    """mode closed + a T1 day's pre-market keeps ref_close (the snapshot is not rolled)."""
    row = {**_pre(51.3, ref=51.2), "open": 51.1, "high": 51.4, "low": 50.9, "close": 51.0,
           "min_t_ms": _ms(PRE - timedelta(minutes=1))}         # verify_last matches on close
    assert R.official_prev_close(row, 51.0, SESSION) == 51.2       # it WOULD supply 51.20
    t = R.today_read(row, ref_close=51.0, ref_date=LAST, now=PRE, session=SESSION,
                     phase="pre", event={"tier": 1, "labels": ["Core PCE"]})
    assert t["state"] == "read" and t["mode"] == "closed" and t["for_today"] is True
    assert t["prev_close"] == 51.0 and t["move_pct"] == R.pct_ret(51.3, 51.0)


def test_rank_moves_use_the_official_close_and_study_lines_stay_golden():
    snaps = dict(SNAPS, QUIET=_rth(49.85, ref=49.9, close=49.996))   # cached 50.00, official 49.90
    e = _entry(cal=NO_CAL)
    rows, _c, _f, today, _su = R.rank(e, snaps, None, now=NOW, sort="res_today")
    q = next(r for r in rows if r["symbol"] == "QUIET")["resiliency"]["today"]
    assert q["state"] == "read" and q["prev_close"] == 49.9
    assert q["move_pct"] == R.pct_ret(49.85, 49.9) == -0.1
    assert R.study_block() == GOLDEN["study"] and R.box_notes() == GOLDEN["box_notes"]


# --------------------------------------------------------------------------
# 2 — a stored sales % with no revenue series is never ranked
# --------------------------------------------------------------------------
def test_NEG_stored_sales_without_a_revenue_series_is_never_ranked():
    g = R.growth_read(_fund(sales=48.0, eps_pct=None, eps=None, rev_q=None))
    assert g["state"] == "read" and g["sales_stored_pct"] == 48.0
    assert g["sales_base"] == "unknown" and g["sales_ranked"] is False
    assert g["eps_ranked"] is False
    gs = [g, R.growth_read(VST)]
    R.score_growth(gs)
    assert gs[0]["score"] is None and gs[0]["legs"] == 0
    assert gs[1]["score"] is not None                              # the pool did score


# --------------------------------------------------------------------------
# 3 — the market line with the cached bars behind (host sleep)
# --------------------------------------------------------------------------
def test_NEG_host_sleep_closed_market_line_says_bars_behind():
    fr = _closed_frames(end=LAST)                                 # bars end Tue; last session Wed
    e = _entry(fr, session=date(2026, 10, 1), cal={"macro": []})
    at = datetime(2026, 9, 30, 19, 59, tzinfo=ET)
    snaps = {s: _closed_snap(51.0, float(fr[s]["close"].iloc[-1]), at)
             for s in ("AAA", "BBB", "CCC", "SPY", "RSP")}
    rows, counts, _f, today, _su = R.rank(e, snaps, None, now=WED21, sort="default")
    assert today["mode"] == "closed" and today["read"] == 0
    assert today["stale"] == 3 and counts["today_stale"] == 3
    assert today["spy_state"] == "stale" and today["rsp_state"] == "stale"
    line = R.market_line(today)
    assert line == ("\U0001F4C5 Last session (Wed 09-30 close): daily bars behind — not read "
                    "(3 names).")
    assert R.NO_PRINT_WORD not in line and "no name has a print" not in line


def test_NEG_market_line_stale_bench_is_never_no_print():
    base = {"mode": "closed", "day": "2026-09-30", "read": 5, "up": 2, "stale": 1,
            "median_move_pct": -0.4, "spy_move_pct": None, "rsp_move_pct": None,
            "spy_state": "stale", "rsp_state": "no_print"}
    line = R.market_line(base)
    assert "SPY daily bars behind — not read · RSP no print · " in line
    assert line.count(R.NO_PRINT_WORD) == 1
    # no state served (older payload) -> the old word
    old = R.market_line({k: v for k, v in base.items() if k not in ("spy_state", "rsp_state")})
    assert "SPY no print · RSP no print" in old
    # zero reads and zero stale -> the empty line, unchanged
    assert R.market_line({**base, "read": 0, "stale": 0}) == \
        "\U0001F4C5 Last session (Wed 09-30 close): no name has a print to read yet."


# --------------------------------------------------------------------------
# 4 — rank: the median move and n up
# --------------------------------------------------------------------------
def test_NEG_rank_serves_the_median_and_counts_only_moves_above_zero():
    snaps = {"SPY": SNAPS["SPY"], "QUIET": _rth(52.5, ref=50.0),   # +5.00% (skews the mean)
             "DROPR": _rth(49.85, ref=50.0),                     # -0.30%
             "ACCUM": _rth(51.0, ref=51.0),                      # +0.00% -> not up
             "THIN": _rth(50.1, ref=50.0)}                       # +0.20%
    e = _entry(cal=NO_CAL)
    _rows, counts, _f, today, _su = R.rank(e, snaps, None, now=NOW, sort="res_today")
    assert today["read"] == 4
    assert today["median_move_pct"] == 0.1                       # mean would be +1.23
    assert today["up"] == 2 and counts["today_up"] == 2          # >= 0 would be 3
