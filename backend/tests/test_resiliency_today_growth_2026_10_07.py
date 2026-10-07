"""🛡️ Resiliency — 📅 today's move on every session, biggest gainers first, and
🚀 sales + EPS growth (2026-10-07).

Ajay 2026-10-07: "Can you do a scan for me on the reseliency tab.. Is it
working? Today is a very red day.. I wanna see which stocks were reselient cuz
Vista was very reselient", then "I want the highest growth stocks on top like
Vistra for example".

Pins: the ONE clock (`drop10_tab.mode_for`) — live / after_close / closed /
data-day pre-market; the resolved default order; the growth chip, fold stat and
🚀 order (material year-ago bases only, `qoq.score_board`); the market line; the
board wiring. POSITIVE and NEGATIVE cases; every NEG fails if its line is
reverted. Hermetic: frames, calendar, events, fundamentals and the snapshot are
injected (the conftest refuses Mongo and the network).
"""
from __future__ import annotations

import ast
import copy
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from chart_maps import board as B
from chart_maps import drop10_tab as D10
from chart_maps import resiliency_tab as R
from rotation import tracker as RT
from sepa import bonde as SB
from sepa import qoq
from tests.test_resiliency_tab import (CAL, ET, EV, FRAMES, LAST, NOW, PRE, SESSION,  # noqa: F401
                                       SNAPS, _clean, _events, _frame, _ms, _no_numpy, _pre,
                                       _rth, _spy_frame, res_board)

BACKEND = Path(__file__).resolve().parents[1]
_REAL_BUILD = R.build                     # the res_board fixture swaps R.build for a fake
NO_CAL = {"macro": [{"date": "2026-10-02", "kind": "jobs", "tier": 1,
                     "label": "Jobs report (NFP)"}]}
AFTER = datetime(2026, 9, 30, 16, 30, tzinfo=ET)            # Wed, after the close
WED21 = datetime(2026, 9, 30, 21, 0, tzinfo=ET)             # overnight -> session Thu 10-01
SAT = datetime(2026, 10, 3, 10, 0, tzinfo=ET)
PRE8 = datetime(2026, 9, 30, 8, 0, tzinfo=ET)

# Golden — captured from origin/main 99792ecb BEFORE the edit (spec §4 WP-BE step 0).
GOLDEN = json.loads(r'''{"study": {"status": "measured", "run_date": "2026-10-01", "t1": {"verdict": "no_signal", "text": "MEASURED 2026-10-01: names that held on at least 75% of the last year's T1 days held on the next one +4.3pp more often than other rated names grouped only by volatility quintile and beta tercile, and +2.9pp more often on the next ordinary day; the data-day edge beyond ordinary days is +1.5pp [-4.5, +7.2], 42 data days — NO_SIGNAL: the box can't be told apart from an ordinary day."}, "t2": {"verdict": "inverted", "text": "MEASURED 2026-10-01: names that held on at least 75% of the last year's T2 days held on the next one +1.4pp more often than other rated names grouped only by volatility quintile and beta tercile, and +4.8pp more often on the next ordinary day; the data-day edge beyond ordinary days is -3.3pp [-5.8, -1.0], 66 data days — INVERTED: the box holds worse on data days than on ordinary days — a weaker hold, not a sell read."}, "eod": {"verdict": "no_signal", "text": "MEASURED 2026-10-01: a volume-confirmed up close led the next session by +0.05pp against the same up close on lighter volume [-0.01, +0.09] — NO_SIGNAL."}, "pre": {"verdict": "unmeasured", "text": "UNMEASURED — pre-market volume history is the intraday cache: ≤31 sessions, patchy — too short to measure"}}, "box_notes": {"t1": "🛡️ A close on every T1 day of the last 365 days and down no more than 0.5% on at least 75% of them. MEASURED 2026-10-01: names that held on at least 75% of the last year's T1 days held on the next one +4.3pp more often than other rated names grouped only by volatility quintile and beta tercile, and +2.9pp more often on the next ordinary day; the data-day edge beyond ordinary days is +1.5pp [-4.5, +7.2], 42 data days — NO_SIGNAL: the box can't be told apart from an ordinary day.", "t2": "🛡️ A close on every T2 day of the last 365 days and down no more than 0.5% on at least 75% of them. MEASURED 2026-10-01: names that held on at least 75% of the last year's T2 days held on the next one +1.4pp more often than other rated names grouped only by volatility quintile and beta tercile, and +4.8pp more often on the next ordinary day; the data-day edge beyond ordinary days is -3.3pp [-5.8, -1.0], 66 data days — INVERTED: the box holds worse on data days than on ordinary days — a weaker hold, not a sell read.", "eod": "📈 The last session closed up, in the upper half of its range, on more volume than its 50-session average — the app's accumulation day. MEASURED 2026-10-01: a volume-confirmed up close led the next session by +0.05pp against the same up close on lighter volume [-0.01, +0.09] — NO_SIGNAL.", "pre": "🌅 Bullish tape pre-market: volume check off until the two volume sources are reconciled — the box passes none; each card still shows its pre-market move. Why: pre-market volume not compared — the snapshot's pre-market shares read higher than the 1-minute bars the usual volume is built from; your call. UNMEASURED."}, "hold_fmt": ["📅 T{tier} today · holding {move:+.2f}%", "📅 T{tier} today · down {move:+.2f}%"], "today_line_data": "📅 2026-09-30 is a T1 data day — Core PCE (T1); GDP (T2). SPY -0.42% vs its prior close (live 10:15 ET). 5 of 8 names with a print are holding (down no more than 0.5%).", "today_line_non": "📅 2026-10-07 has no T1 or T2 print. Next T1: CPI 2026-10-14."}''')


def _entry(frames=None, *, session=SESSION, events=None, cal=CAL, fund=None, fund_fn=None):
    fr = frames if frames is not None else FRAMES()
    ff = fund_fn or (lambda syms: dict(fund or {}))
    return R.build("full", session, universe_fn=lambda u: [s for s in fr if s not in ("SPY", "RSP")],
                   frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr},
                   events_fn=lambda a, b: (events if events is not None else _events()),
                   calendar_fn=lambda: cal, fund_fn=ff)


def _pill(r):
    return [b for b in R.tile_badges(r) if b["text"].startswith(R.TODAY_MARK)]


def _all_text(r) -> str:
    """Every badge + the Today stat (the T1/T2 history stats may legitimately say +0.00%)."""
    return " | ".join([b["text"] for b in R.tile_badges(r)]
                      + [s["v"] for s in R.tile_stats(r) if s["k"] == "Today"])


# --------------------------------------------------------------------------
# fundamentals fixtures (research.decision_snapshot rows)
# --------------------------------------------------------------------------
PER = [8105, 8104, 8103, 8102, 8101, 8100, 8099, 8098]          # FY2026 Q2 newest-first


def _fund(*, sales=None, rev=None, eps_pct=None, eps=None, periods=PER, src="massive",
          rev_q=None, cached_at=1790700000.0):
    return {"sales": {"growth_yoy_pct": sales} if sales is not None else {},
            "rev_growth_q_pct": rev if rev is not None else sales,
            "q_eps_growth_pct": eps_pct, "y_eps_growth_pct": 999.0,
            "q_period_series": periods, "rev_q_series": rev_q, "eps_q_series": eps,
            "ni_q_series": None, "_source": src, "cached_at": cached_at}


VST = _fund(sales=-5.48, eps_pct=-6.17, eps=[0.76, 1.0, 1.0, 1.0, 0.81, 1.0],
            rev_q=[4.0e9, 4.1e9, 4.1e9, 4.1e9, 4.232e9, 4.0e9])
TWLO = _fund(sales=12.0, eps_pct=4671.43, eps=[6.68, 1, 1, 1, 0.14, 1],
             rev_q=[1.2e9, 1, 1, 1, 1.07e9, 1])
PBF = _fund(sales=56.23, eps_pct=15180.0, eps=[7.54, 1, 1, 1, -0.05, 1],
            rev_q=[9.0e9, 1, 1, 1, 5.76e9, 1])
CRI = _fund(sales=-10.0, eps_pct=28600.0, eps=[2.87, 1, 1, 1, 0.01, 1],
            rev_q=[6.0e8, 1, 1, 1, 6.6e8, 1])
GROWER = _fund(sales=30.0, eps_pct=40.0, eps=[0.70, 1, 1, 1, 0.50, 1],
               rev_q=[1.3e8, 1, 1, 1, 1.0e8, 1])
AAON = _fund(sales=20.0, eps_pct=26.32, eps=[0.68, 1, 1, 1, 0.19, 1],
             rev_q=[3.0e8, 1, 1, 1, 2.5e8, 1])


# --------------------------------------------------------------------------
# 1 — the clock + constants
# --------------------------------------------------------------------------
def test_NEG_constants_are_the_owners():
    assert (R.MODE_LIVE, R.MODE_AFTER, R.MODE_CLOSED) == (D10.MODE_LIVE, D10.MODE_AFTER,
                                                          D10.MODE_CLOSED)
    assert R.EW_BENCH == RT.BENCHMARK == "RSP"
    assert R.EPS_MIN_BASE == qoq.MIN_EPS_BASE and R.REV_MIN_BASE == SB.MIN_MATERIAL_BASE_REV
    assert R.TAB_SORTS == ("res_t1", "res_t2", "res_down", "res_today", "res_growth")
    assert R.GROWTH_CHIP_PREFIX == "Sales " and R.GROWTH_CHIP_FMT.startswith(R.GROWTH_CHIP_PREFIX)
    assert not R.GROWTH_CHIP_FMT.startswith(R.GROWTH_MARK)      # cardLadder: '🚀 ' is PRICE


def test_today_mode_is_drop10_mode_for():
    assert R.today_mode(NOW) == {"mode": "live", "day": "2026-09-30", "half_day": False}
    assert R.today_mode(AFTER)["mode"] == "after_close"
    assert R.today_mode(WED21) == {"mode": "closed", "day": "2026-09-30", "half_day": False}
    assert R.today_mode(SAT)["day"] == "2026-10-02"
    assert R.today_mode(PRE8) == {"mode": "closed", "day": "2026-09-29", "half_day": False}
    half = R.today_mode(datetime(2026, 11, 27, 14, 0, tzinfo=ET))
    assert half["mode"] == "after_close" and half["half_day"] is True


# --------------------------------------------------------------------------
# 2 — live, ordinary session
# --------------------------------------------------------------------------
def test_non_data_day_rth_reads_plain_pill_and_today_stat():
    t = R.today_read(_rth(100.42, ref=100.0), ref_close=100.0, ref_date=LAST, now=NOW,
                     session=SESSION, phase="rth", event=None)
    assert t["state"] == "read" and t["tier"] is None and t["for_today"] is True
    assert t["mode"] == "live" and t["move_pct"] == 0.42 and t["day"] == "2026-09-30"
    r = {"symbol": "X", "resiliency": {"today": t}, "res_filter": {}}
    assert _pill(r) == [{"text": "\U0001F4C5 today · +0.42%", "tone": "good"}]
    assert any(s["k"] == "Today" for s in R.tile_stats(r))


def test_NEG_non_data_day_still_reads_through_rank():
    """Reverting the event gate (no event -> no read) fails here."""
    snaps = dict(SNAPS, DROPR=_rth(50.1, ref=50.0))           # DROPR ties QUIET at +0.20%
    e = _entry(cal=NO_CAL)
    rows, counts, _f, today, su = R.rank(e, snaps, None, now=NOW, sort="default")
    assert su is None and today["event_day"] is False and today["read"] == 4
    assert R.resolve_sort("default", mode=today["mode"], n_read=today["read"],
                          n_growth=0) == ("res_today", None)
    syms = [r["symbol"] for r in rows]
    # move desc; QUIET (T1 100%) before DROPR (T1 62.5%) on the +0.20% tie (symbol would flip it)
    assert syms == ["ACCUM", "QUIET", "DROPR", "THIN", "HOLEY"]
    assert rows[-1]["resiliency"]["today"]["state"] == "no_print"
    assert counts["today_read"] == 4 and counts["today_up"] == 3


def test_NEG_zero_reads_in_rth_default_is_t1_and_res_today_says_why():
    e = _entry(cal=NO_CAL)
    rows, _c, _f, today, su = R.rank(e, {}, None, now=NOW, sort="default")
    assert today["read"] == 0 and su is None
    t1_order = [r["symbol"] for r in sorted(rows, key=lambda r: R.order_key(r, "res_t1"))]
    assert [r["symbol"] for r in rows] == t1_order
    _r, _c, _f, _t, su2 = R.rank(e, {}, None, now=NOW, sort="res_today")
    assert su2 == R.TODAY_SORT_NO_READ
    assert R.resolve_sort("res_today", mode="live", n_read=0, n_growth=5) == (
        "res_t1", R.TODAY_SORT_NO_READ)


def test_NEG_no_code_path_serves_not_a_data_day():
    src = (BACKEND / "chart_maps" / "resiliency_tab.py").read_text(encoding="utf-8")
    assert "TODAY_SORT_UNAVAILABLE" not in src and "not a T1 or T2 data day" not in src
    assert not hasattr(R, "TODAY_SORT_UNAVAILABLE")
    words = " ".join(n.value for n in ast.walk(ast.parse(src))
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)).lower()
    for w in ("red day", "bounce", "fake", "won't drop", "market-resilient"):
        assert w not in words, w


# --------------------------------------------------------------------------
# 3 — after the close: the 16:00 close, never the after-hours print
# --------------------------------------------------------------------------
def _after_row(*, close, ref, ah_px, ah_at):
    return {"open": ref, "high": max(close, ref) + 0.5, "low": min(close, ref) - 0.5,
            "close": close, "volume": 2_000_000, "date": None,
            "last_trade_price": ah_px, "last_trade_ts_ms": _ms(ah_at),
            "prev_day_close": ref, "min_t_ms": _ms(ah_at - timedelta(minutes=1))}


def test_NEG_after_close_ignores_a_fresher_after_hours_trade():
    row = _after_row(close=50.6, ref=50.0, ah_px=50.9, ah_at=AFTER - timedelta(seconds=20))
    t = R.today_read(row, ref_close=50.0, ref_date=LAST, now=AFTER, session=SESSION,
                     phase="close", event=None)
    assert t["state"] == "read" and t["mode"] == "after_close" and t["basis"] == "day_close"
    assert t["move_pct"] == 1.2 and t["move_pct"] != R.pct_ret(50.9, 50.0)   # AH would be +1.80
    assert t["tape"] is None and t["as_of_et"] is None
    assert R._today_stat(t).endswith(R.DAY_CLOSE_WORD)


def test_NEG_after_close_no_trade_today_never_reads_zero():
    """Massive not rolled: close == yesterday's close, last trade yesterday — the old
    anchor_read path read it as day_close +0.00%."""
    y = datetime(2026, 9, 29, 15, 59, tzinfo=ET)
    row = {"open": 50.0, "high": 50.5, "low": 49.5, "close": 50.0, "volume": 1e6,
           "last_trade_price": 50.0, "last_trade_ts_ms": _ms(y), "prev_day_close": 49.0}
    t = R.today_read(row, ref_close=50.0, ref_date=LAST, now=AFTER, session=SESSION,
                     phase="close", event=None)
    assert t["state"] == "no_print" and t["move_pct"] is None
    assert R._today_stat(t) == "no trade in today's session — not read"
    r = {"symbol": "X", "resiliency": {"today": t}, "res_filter": {}}
    assert _pill(r) == [] and "+0.00%" not in _all_text(r)


def test_data_day_after_close_keeps_the_t1_words():
    row = _after_row(close=50.1, ref=50.0, ah_px=48.0, ah_at=AFTER - timedelta(seconds=20))
    t = R.today_read(row, ref_close=50.0, ref_date=LAST, now=AFTER, session=SESSION,
                     phase="close", event=EV)
    assert t["basis"] == "day_close" and t["tier"] == 1 and t["for_today"] is True
    r = {"symbol": "X", "resiliency": {"today": t}, "res_filter": {}}
    assert _pill(r)[0]["text"] == GOLDEN["hold_fmt"][0].format(tier=1, move=0.2)
    assert _pill(r)[0]["text"] == "\U0001F4C5 T1 today · holding +0.20%"


# --------------------------------------------------------------------------
# 4 — closed: the last session, dated, never "today", never a tier
# --------------------------------------------------------------------------
def _closed_frames(end="2026-09-30", moves=None):
    """Frames through `end`; each name's last close moves off a 50.0 base."""
    fr = {"SPY": _spy_frame(end=end), "RSP": _frame(end=end, closes={end: 50.25})}
    for sym, last in (moves or {"AAA": 50.5, "BBB": 49.0, "CCC": 51.5}).items():
        fr[sym] = _frame(end=end, closes={end: last})
    return fr


def _closed_snap(close, prev, at):
    return {"open": prev, "high": max(close, prev) + 0.5, "low": min(close, prev) - 0.5,
            "close": close, "volume": 1e6, "last_trade_price": close,
            "last_trade_ts_ms": _ms(at), "prev_day_close": prev}


THU_T1 = {"macro": [{"date": "2026-10-01", "kind": "cpi", "tier": 1, "label": "CPI"}]}


def test_closed_overnight_reads_the_last_session_dated():
    fr = _closed_frames()
    sess = R.session_for(WED21)
    assert sess == date(2026, 10, 1)
    e = _entry(fr, session=sess, cal=THU_T1)
    assert e["session_events"]["tier"] == 1                     # Thu is a data day
    at = datetime(2026, 9, 30, 19, 59, tzinfo=ET)
    snaps = {s: _closed_snap(float(fr[s]["close"].iloc[-1]), 50.0, at) for s in ("AAA", "BBB", "CCC")}
    rows, counts, _f, today, su = R.rank(e, snaps, None, now=WED21, sort="default")
    assert today["mode"] == "closed" and today["day"] == "2026-09-30" and not today["data_pre"]
    by = {r["symbol"]: r for r in rows}
    td = by["CCC"]["resiliency"]["today"]
    assert td["state"] == "read" and td["tier"] is None and td["for_today"] is False
    assert td["basis"] == R.LAST_BASIS and td["move_pct"] == 3.0
    assert _pill(by["CCC"]) == [{"text": "\U0001F4C5 last session Wed 09-30 · +3.00%", "tone": "good"}]
    assert _pill(by["BBB"])[0]["tone"] == "warn"
    for r in rows:
        assert not any(s["k"] == "Today" for s in R.tile_stats(r))
        assert "today" not in " ".join(b["text"] for b in _pill(r))
    # default -> the T1 order; explicit res_today orders by the last session's move
    assert R.resolve_sort("default", mode="closed", n_read=3, n_growth=0)[0] == "res_t1"
    rows2, *_ = R.rank(e, snaps, None, now=WED21, sort="res_today")
    assert [r["symbol"] for r in rows2] == ["CCC", "AAA", "BBB"]
    assert R.served_sorts("res_t1", today_label=R.today_sort_label("closed"))[1]["label"] == \
        "\U0001F4C5 Last session's move"
    # the data-day sentence never prints the last session's numbers as Thursday's
    line = R.today_line(today)
    assert line.startswith("\U0001F4C5 2026-10-01 is a T1 data day — CPI (T1).")
    assert "SPY" not in line and "holding" not in line
    assert R.market_line(today).startswith("\U0001F4C5 Last session (Wed 09-30 close): SPY ")


def test_saturday_reads_friday():
    fr = _closed_frames(end="2026-10-02")
    sess = R.session_for(SAT)
    e = _entry(fr, session=sess, cal={"macro": []})
    at = datetime(2026, 10, 2, 19, 0, tzinfo=ET)
    snaps = {"AAA": _closed_snap(50.5, 50.0, at)}
    rows, *_ = R.rank(e, snaps, None, now=SAT, sort="default")
    a = next(r for r in rows if r["symbol"] == "AAA")
    assert _pill(a)[0]["text"] == "\U0001F4C5 last session Fri 10-02 · +1.00%"


def test_NEG_closed_mode_without_a_snapshot_or_with_bars_behind_never_reads():
    fr = _closed_frames()
    fr["LAG"] = _frame(end=LAST)                                 # ends Tue; the last session is Wed
    e = _entry(fr, session=date(2026, 10, 1), cal={"macro": []})
    at = datetime(2026, 9, 30, 19, 59, tzinfo=ET)
    snaps = {"AAA": _closed_snap(50.5, 50.0, at), "LAG": _closed_snap(50.0, 50.0, at)}
    rows, counts, *_ = R.rank(e, snaps, None, now=WED21, sort="res_today")
    by = {r["symbol"]: r for r in rows}
    assert by["BBB"]["resiliency"]["today"]["state"] == "no_print"      # no snapshot
    assert by["LAG"]["resiliency"]["today"]["state"] == "stale"
    for s in ("BBB", "LAG", "CCC"):
        assert _pill(by[s]) == [] and "+0.00%" not in _all_text(by[s])
    assert [r["symbol"] for r in rows][0] == "AAA"
    assert counts["today_stale"] >= 1


def test_NEG_partial_cached_bar_is_stale_in_closed_mode():
    fr = _closed_frames(moves={"AAA": 50.5})                     # cached an intraday 50.50
    e = _entry(fr, session=date(2026, 10, 1), cal={"macro": []})
    at = datetime(2026, 9, 30, 19, 59, tzinfo=ET)
    snaps = {"AAA": _closed_snap(50.8, 50.0, at)}                # the final close was 50.80
    rows, *_ = R.rank(e, snaps, None, now=WED21, sort="default")
    td = rows[0]["resiliency"]["today"]
    assert td["state"] == "stale" and _pill(rows[0]) == []


def test_NEG_premarket_ordinary_day_is_the_last_session_never_today():
    """A FRESH pre-market print on a non-data day: the 📅 pill is the dated last
    session; an overnight snapshot dated today never reads as 'today'."""
    e = _entry(cal=NO_CAL)
    snaps = {"ACCUM": _pre(51.3, ref=51.0, at=PRE8),
             "QUIET": dict(_rth(50.0, ref=50.0, at=datetime(2026, 9, 29, 19, 0, tzinfo=ET)),
                           date=SESSION.isoformat())}
    rows, _c, _f, today, _su = R.rank(e, snaps, None, now=PRE8, sort="default")
    a = next(r for r in rows if r["symbol"] == "ACCUM")
    assert _pill(a)[0]["text"] == "\U0001F4C5 last session Tue 09-29 · +2.00%"
    for r in rows:
        for b in _pill(r):
            assert not b["text"].startswith("\U0001F4C5 today")
    assert today["mode"] == "closed" and today["data_pre"] is False


def test_data_day_premarket_keeps_the_live_read_golden_bytes():
    e = _entry()                                                 # CAL: Core PCE on 09-30
    snaps = {"ACCUM": _pre(51.3, ref=51.0)}
    rows, _c, _f, today, _su = R.rank(e, snaps, None, now=PRE, sort="default")
    a = next(r for r in rows if r["symbol"] == "ACCUM")
    td = a["resiliency"]["today"]
    assert td["basis"] == "live" and td["for_today"] is True and td["tier"] == 1
    assert _pill(a)[0]["text"] == GOLDEN["hold_fmt"][0].format(tier=1, move=0.59)
    assert today["data_pre"] is True
    assert R.market_line(today).startswith("\U0001F4C5 Pre-market today, live: ")


# --------------------------------------------------------------------------
# 5 — the market line
# --------------------------------------------------------------------------
def test_market_line_exact_strings():
    base = {"mode": "after_close", "half_day": False, "read": 2729, "up": 864,
            "median_move_pct": -0.84, "spy_move_pct": -0.2, "rsp_move_pct": -0.63}
    assert R.market_line(base) == ("\U0001F4C5 Today's close (16:00 ET): SPY -0.20% · RSP -0.63% · "
                                   "median name -0.84% (down) · 864 of 2,729 names read are up.")
    up = R.market_line({**base, "median_move_pct": 0.31})
    assert "median name +0.31% (up)" in up
    flat = R.market_line({**base, "median_move_pct": 0.0})
    assert "median name +0.00% (flat)" in flat
    assert R.market_line({**base, "half_day": True}).startswith(
        "\U0001F4C5 Today's close (13:00 ET): ")
    assert R.market_line({**base, "rsp_move_pct": None}).count("RSP no print") == 1
    live = R.market_line({**base, "mode": "live", "spy_as_of_et": "14:31"})
    assert live.startswith("\U0001F4C5 Today, live 14:31 ET: SPY -0.20%")
    assert R.market_line({**base, "read": 0, "mode": "live"}) == \
        "\U0001F4C5 Today, live: no name has a print to read yet."
    closed = R.market_line({**base, "mode": "closed", "day": "2026-10-07"})
    assert closed.startswith("\U0001F4C5 Last session (Wed 10-07 close): ")
    # NEGATIVE: no mode -> no line; the word comes ONLY from the median's sign
    assert R.market_line({}) is None and R.market_line(None) is None
    assert "(down)" in R.market_line({**base, "spy_move_pct": 2.0, "rsp_move_pct": 1.0})


# --------------------------------------------------------------------------
# 6 — growth
# --------------------------------------------------------------------------
def test_growth_vst_and_twlo_ranked_and_the_blend_is_score_board():
    v = R.growth_read(VST)
    assert R.growth_chip(v) == "Sales -5.5% · EPS -6.2% YoY (FY2026 Q2)"
    assert v["sales_ranked"] and v["eps_ranked"] and v["eps_agrees"] is True
    assert v["period"] == "FY2026 Q2" and v["year_ago_period"] == "FY2025 Q2"
    t = R.growth_read(TWLO)
    assert t["eps_ranked"] and t["eps_yoy_pct"] == 4671.43 and t["eps_base"] == "ok"
    gs = [R.growth_read(f) for f in (VST, TWLO, GROWER, PBF)]
    R.score_growth(gs)
    direct = [{"i": g["eps_yoy_pct"] if g["eps_ranked"] else None,
               "g": g["sales_yoy_pct"] if g["sales_ranked"] else None} for g in gs]
    qoq.score_board(direct, income_key="i", growth_key="g", out_key="s")
    assert [g["score"] for g in gs] == [d["s"] for d in direct]
    assert [g["legs"] for g in gs] == [2, 2, 2, 1]
    st = R._growth_stat(v)
    assert st.startswith("FY2026 Q2 vs FY2025 Q2 · sales -5.48% · EPS -6.17% (year-ago $0.81)")


def _growth_rows(funds: dict) -> list:
    gs = {s: R.growth_read(f) for s, f in funds.items()}
    R.score_growth(list(gs.values()))
    return [{"symbol": s, "resiliency": {"growth": g, "t1": None}} for s, g in gs.items()]


def test_NEG_tiny_or_negative_year_ago_eps_never_tops_growth():
    rows = _growth_rows({"PBF": PBF, "CRI": CRI, "GROW": GROWER})
    order = [r["symbol"] for r in sorted(rows, key=lambda r: R.order_key(r, "res_growth"))]
    assert order[0] == "GROW"
    by = {r["symbol"]: r["resiliency"]["growth"] for r in rows}
    assert by["PBF"]["eps_base"] == "non_positive" and by["CRI"]["eps_base"] == "too_small"
    assert not by["PBF"]["eps_ranked"] and not by["CRI"]["eps_ranked"]
    assert R.growth_chip(by["PBF"]) == "Sales +56.2% · EPS — YoY (FY2026 Q2)"
    assert "EPS — YoY" in R.growth_chip(by["CRI"])
    assert "sign flip" in R._growth_stat(by["PBF"]) and "-$0.05" in R._growth_stat(by["PBF"])
    assert "under the $0.10 floor" in R._growth_stat(by["CRI"])
    # the floor is EPS_MIN_BASE: without it CRI's $0.01 base would rank
    assert R._yoy_base([2.87, 1, 1, 1, 0.01], R.EPS_MIN_BASE)[1] == qoq.BASE_TOO_SMALL
    assert R._yoy_base([2.87, 1, 1, 1, 0.01], 0.0)[1] == qoq.BASE_OK


def test_NEG_year_ago_revenue_at_or_under_zero_or_under_1m_is_blank_unranked():
    neg = R.growth_read(_fund(sales=900.0, eps_pct=None, rev_q=[5e6, 1, 1, 1, -3e6, 1]))
    small = R.growth_read(_fund(sales=9000.0, eps_pct=None, rev_q=[5.5e6, 1, 1, 1, 6.1e4, 1]))
    for g, word in ((neg, "non_positive"), (small, "too_small")):
        assert g["sales_base"] == word and g["sales_yoy_pct"] is None and not g["sales_ranked"]
        assert R.growth_chip(g).startswith("Sales — · ")
    assert "sign flip" in R._growth_stat(neg) and "under $1M" in R._growth_stat(small)


def test_NEG_stored_eps_that_disagrees_with_its_series_is_shown_not_ranked():
    g = R.growth_read(AAON)
    assert g["eps_yoy_pct"] == 26.32 and g["eps_agrees"] is False and not g["eps_ranked"]
    assert "disagree" in R._growth_stat(g)


def test_NEG_period_mismatch_blanks_both():
    g = R.growth_read(_fund(sales=10.0, eps_pct=10.0, eps=[1.1, 1, 1, 1, 1.0, 1],
                            periods=[8105, 8104, 8103, 8102, 8100, 8099, 8098, 8097]))
    assert g["state"] == "period_mismatch" and g["sales_yoy_pct"] is None and g["eps_yoy_pct"] is None
    assert R.growth_chip(g) == "Sales — · EPS — YoY (quarters not a year apart on file)"
    assert not g["sales_ranked"] and not g["eps_ranked"]


def test_NEG_no_figures_sorts_last_and_an_all_unknown_pool_is_unavailable():
    g = R.growth_read(None)
    assert R.growth_chip(g) == "Sales — · EPS — YoY (no quarterly figures on file)"
    assert R._growth_stat(g) == R.GROWTH_NO_FIGURES
    rows = _growth_rows({"NONE": None, "VST": VST})
    order = [r["symbol"] for r in sorted(rows, key=lambda r: R.order_key(r, "res_growth"))]
    assert order == ["VST", "NONE"]
    e = _entry(cal=NO_CAL)                                       # fund {} -> nothing ranked
    rows2, counts, _f, today, su = R.rank(e, SNAPS, None, now=NOW, sort="res_growth")
    assert counts["growth_ranked"] == 0 and su == R.GROWTH_SORT_UNAVAILABLE
    assert R.resolve_sort("res_growth", mode="live", n_read=today["read"], n_growth=0) == (
        "res_today", R.GROWTH_SORT_UNAVAILABLE)


def test_growth_through_build_and_rank_orders_by_the_blend():
    fund = {"QUIET": VST, "ACCUM": PBF, "DROPR": GROWER, "THIN": CRI}
    e = _entry(cal=NO_CAL, fund=fund)
    assert e["fund_summary"] == {"available": True, "n": 4, "error": None}
    rows, counts, _f, _t, su = R.rank(e, SNAPS, None, now=NOW, sort="res_growth")
    assert su is None and counts["growth_eps_ranked"] == 2 and counts["growth_ranked"] == 4
    syms = [r["symbol"] for r in rows]
    assert syms[:2] == ["DROPR", "QUIET"] and syms[-1] == "HOLEY"
    q = next(r for r in rows if r["symbol"] == "QUIET")
    assert R.tile_badges(q)[-1] == {"text": "Sales -5.5% · EPS -6.2% YoY (FY2026 Q2)", "tone": "muted"}
    assert R.tile_stats(q)[-1]["k"] == "Growth"


# --------------------------------------------------------------------------
# 7 — the words stay; the measured lines stay
# --------------------------------------------------------------------------
def test_NEG_data_day_words_and_measured_lines_are_golden():
    assert [R.TODAY_HOLD_FMT, R.TODAY_DOWN_FMT] == GOLDEN["hold_fmt"]
    assert R.study_block() == GOLDEN["study"]
    assert R.box_notes() == GOLDEN["box_notes"]
    for k in R.FILTER_KEYS:
        low = R.study_block()[k]["text"].lower()
        assert "today" not in low and "growth" not in low
    s = {"event_day": True, "session": "2026-09-30", "t1": ["Core PCE"], "t2": ["GDP"], "tier": 1,
         "spy_move_pct": -0.42, "spy_tape": "rth", "spy_as_of_et": "10:15", "spy_basis": "live",
         "holding": 5, "read": 8}
    assert R.today_line(s) == GOLDEN["today_line_data"]
    assert R.today_line({**s, "mode": "live"}) == GOLDEN["today_line_data"]
    assert R.today_line({**s, "mode": "closed", "data_pre": True}) == GOLDEN["today_line_data"]
    assert R.today_line({"event_day": False, "session": "2026-10-07",
                         "next_t1": {"date": "2026-10-14", "label": "CPI"}}) == GOLDEN["today_line_non"]


def test_rules_and_note_say_unmeasured_built_from_constants():
    rb = R.rules_block()
    assert rb["eps_min_base"] == R.EPS_MIN_BASE and rb["rev_min_base"] == R.REV_MIN_BASE
    txt = " ".join(rb["lines"])
    assert "$0.10" in txt and "$1M" in txt and "UNMEASURED" in txt
    assert "Default order: today's move, biggest gain first" in txt
    assert "orders, UNMEASURED" in R.note_text()


# --------------------------------------------------------------------------
# 8 — the request path, failures, serialization
# --------------------------------------------------------------------------
def test_NEG_fund_fn_raising_is_named_never_its_text():
    def boom(syms):
        raise ConnectionError("https://x/y?apiKey=SECRET")
    e = _entry(cal=NO_CAL, fund_fn=boom)
    assert e["fund_summary"] == {"available": False, "n": 0, "error": "ConnectionError"}
    assert "SECRET" not in json.dumps(e, default=str)
    assert all(rd["growth"]["state"] == "no_figures" for rd in e["reads"].values())


def test_NEG_build_reads_fundamentals_rank_and_the_request_never_do(res_board, monkeypatch):
    from sepa import research
    calls = []
    monkeypatch.setattr(research, "decision_snapshot", lambda syms, *a, **k: calls.append(1) or {})
    fr = FRAMES()
    _REAL_BUILD("full", SESSION, universe_fn=lambda u: ["QUIET"],
            frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr},
            events_fn=lambda a, b: _events(), calendar_fn=lambda: CAL)
    assert calls == [1]                                          # the warm thread's ONE read
    res_board["seed"]()

    def boom(*a, **k):
        raise AssertionError("the request path read fundamentals")
    monkeypatch.setattr(research, "decision_snapshot", boom)
    out = B.board(tab="resiliency", limit=24)
    assert out["resiliency_board"]["state"] == "ready"
    R.rank(R._memo[next(iter(R._memo))], SNAPS, None, now=NOW, sort="res_growth")


def test_NEG_source_guards():
    src = (BACKEND / "chart_maps" / "resiliency_tab.py").read_text(encoding="utf-8")
    for w in ("qoq.score_board", "qoq._seq_pct", "_rev_base", "decision_snapshot", "mode_for",
              "day_from_snapshot"):
        assert w in src, w
    bsrc = (BACKEND / "chart_maps" / "board.py").read_text(encoding="utf-8")
    body = bsrc[bsrc.index("def resiliency_tiles("):bsrc.index("def fallen_tiles(")]
    assert "load_latest_shared()" in body and "scanner.load_latest()" not in body
    assert "import drop10_tab" not in src.split("def ")[0]        # lazy, never at module top


def test_NEG_closed_mode_growth_payload_serializes_clean():
    fr = _closed_frames()
    fund = {"AAA": VST, "BBB": PBF, "CCC": {**GROWER, "q_eps_growth_pct": float("nan")}}
    e = _entry(fr, session=date(2026, 10, 1), cal={"macro": []}, fund=fund)
    at = datetime(2026, 9, 30, 19, 59, tzinfo=ET)
    snaps = {s: _closed_snap(float(fr[s]["close"].iloc[-1]), 50.0, at) for s in ("AAA", "BBB")}
    rows, counts, filters, today, su = R.rank(e, snaps, None, now=WED21, sort="res_growth")
    blk = R.ready_block(counts, entry=e, now=WED21, sort="res_growth", filters=filters, today=today)
    payload = {"rows": rows, "block": blk,
               "tiles": [{"badges": R.tile_badges(r), "stats": R.tile_stats(r)} for r in rows]}
    json.dumps(payload, allow_nan=False)
    _no_numpy(payload)
    assert blk["market_line"].startswith("\U0001F4C5 Last session (Wed 09-30 close)")


# --------------------------------------------------------------------------
# 9 — the board
# --------------------------------------------------------------------------
def test_board_resolves_the_default_and_serves_six_sorts(res_board):
    res_board["seed"]()
    a = B.board(tab="resiliency", limit=24)
    assert a["sort"] == "res_today" and a["resiliency_board"]["sort"] == "res_today"
    assert [s["key"] for s in a["sorts"]] == ["default", "res_today", "res_t1", "res_t2",
                                              "res_down", "res_growth"]
    assert a["sorts"][0]["label"] == "\U0001F4C5 Today's move (default)"
    assert a["sort_unavailable"] is None
    assert a["resiliency_board"]["market_line"].startswith("\U0001F4C5 Today, live")
    assert len(res_board["snap_calls"]) == 1
    assert {"SPY", "RSP"} <= set(res_board["snap_calls"][0])
    t1 = B.board(tab="resiliency", sort="res_t1", limit=24)
    want = [r["symbol"] for r in sorted(
        R.rank(R._memo[next(iter(R._memo))], SNAPS, None, now=NOW, sort="res_t1")[0],
        key=lambda r: R.order_key(r, "res_t1")) if r["symbol"] != "THIN"]
    assert t1["sort"] == "res_t1" and [t["symbol"] for t in t1["tiles"]] == want
    bogus = B.board(tab="resiliency", sort="volume", limit=24)
    assert bogus["sort"] == "res_today"
    g = B.board(tab="resiliency", sort="res_growth", limit=24)        # nothing on file
    assert g["sort"] == "res_today" and g["sort_unavailable"] == R.GROWTH_SORT_UNAVAILABLE
    for p in (a, t1, bogus, g):
        assert "not a T1 or T2 data day" not in json.dumps(p, ensure_ascii=False)


def test_board_before_the_open_serves_t1(res_board):
    res_board["seed"]()
    pre = B.resiliency_tiles(24, 130, "full", False, "default", now=PRE)
    assert pre["res_sort"] == "res_t1"
    assert pre["res_sorts"][0]["label"] == "\U0001F6E1️ T1 hold rate (default)"
    assert pre["res_sorts"][1]["label"] == R.TODAY_SORT_LABEL       # data-day pre-market: today
