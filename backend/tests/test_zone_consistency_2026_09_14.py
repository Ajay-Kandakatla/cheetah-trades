"""Supply / demand zones — the same answer on every surface (2026-09-14).

Ajay: "Basically I wanna make sure the overhead supply and demand zone logic
is accurate across board."

Measured that evening on 46 live board tickers: every board, alert gate and
paper lane shares ONE engine at ONE geometry and they agree with each other;
the Support tab and the holdings tab read the same engine at a finer geometry
and agreed with the boards on the nearest demand band 6 times in 46. Two
things fixed here, both pinned:

  1. `decide_from_frame` — the one rule the boards, the alert gate and the
     lanes run — reads STRUCTURE from closed bars. Today's partial bar (which
     the hourly cache patch writes into the shared frame from ~10:00 ET) may
     PRICE the record but may not mint a swing, a close or a "bars since".
  2. Every daily Support-tab view (so the holdings tab too) carries the
     BOARD's band, computed by that same function on the same closed frame,
     as its own dashed family — so the tab and an alert name the same band.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from chart_maps import support as S
from supply_demand import demand_reentry as DR
from supply_demand import price_zones as pz

ET = ZoneInfo("America/New_York")


# ── fixture: a year of structure with two floors and a lid ───────────────────
def _saw(low: float, high: float, leg: int, cycles: int) -> list[float]:
    out: list[float] = []
    for _ in range(cycles):
        out += list(np.linspace(low, high, leg))
        out += list(np.linspace(high, low, leg))
    return out


def frame(end: str = "2026-09-11", n_extra: int = 0) -> pd.DataFrame:
    """~330 daily bars ending on `end` (a Friday). Bars carry open/high/low/
    close/volume so every reader (structure, liquidity) has what it needs."""
    closes = _saw(100.0, 112.0, 12, 6) + _saw(104.0, 118.0, 14, 6)
    closes = closes[-330:]
    idx = pd.bdate_range(end=end, periods=len(closes))
    c = np.array(closes)
    df = pd.DataFrame({"open": c, "high": c * 1.006, "low": c * 0.994,
                       "close": c, "volume": 1_000_000.0}, index=idx)
    return df


def today_row(day: str, close: float, low: float, volume: float = 250_000.0) -> pd.DataFrame:
    return pd.DataFrame({"open": [close], "high": [close * 1.004], "low": [low],
                         "close": [close], "volume": [volume]},
                        index=pd.DatetimeIndex([pd.Timestamp(day)]))


# ── 1. split_today_partial ───────────────────────────────────────────────────
def test_todays_bar_is_split_off_while_the_session_is_open():
    df = pd.concat([frame("2026-09-11"), today_row("2026-09-14", 110.0, 99.0)])
    now = datetime(2026, 9, 14, 11, 0, tzinfo=ET)          # 90 min into the session
    closed, today = DR.split_today_partial(df, now_et=now)
    assert len(closed) == len(df) - 1
    assert today is not None and len(today) == 1
    assert closed.index[-1].date().isoformat() == "2026-09-11"


def test_NEGATIVE_after_the_close_todays_bar_is_a_closed_bar_and_stays():
    df = pd.concat([frame("2026-09-11"), today_row("2026-09-14", 110.0, 99.0)])
    now = datetime(2026, 9, 14, 16, 30, tzinfo=ET)
    closed, today = DR.split_today_partial(df, now_et=now)
    assert today is None and len(closed) == len(df)


def test_NEGATIVE_a_frame_ending_yesterday_is_never_split():
    df = frame("2026-09-11")
    now = datetime(2026, 9, 14, 11, 0, tzinfo=ET)
    closed, today = DR.split_today_partial(df, now_et=now)
    assert today is None and len(closed) == len(df)


def test_NEGATIVE_pre_market_phantom_bar_dated_today_is_not_structure():
    """The pre-market echo bar (2026-09-14 trap): dated today, session
    fraction 0. It is not a closed bar either."""
    df = pd.concat([frame("2026-09-11"), today_row("2026-09-14", 110.0, 99.0)])
    now = datetime(2026, 9, 14, 8, 30, tzinfo=ET)
    closed, today = DR.split_today_partial(df, now_et=now)
    assert today is not None and len(closed) == len(df) - 1


# ── 2. decide_from_frame with a partial bar ──────────────────────────────────
def test_the_partial_bar_prices_the_record_but_cannot_mint_structure():
    """A partial low 8% under every floor used to become a swing low the
    moment the cache patch wrote it. Now the bands are the closed frame's,
    the price is the partial close, and the liquidity read sees the bar."""
    closed = frame("2026-09-11")
    today = today_row("2026-09-14", 110.0, 92.0, volume=250_000.0)
    base = DR.decide_from_frame(closed, "TEST")
    rec = DR.decide_from_frame(closed, "TEST", today_row=today)
    assert base and rec
    assert rec["price_basis"] == "today_partial"
    assert rec["last_price"] == 110.0
    assert rec["structure_through"] == "2026-09-11"
    # same bands as the closed frame alone — the partial low made nothing
    assert [(z["lo"], z["hi"]) for z in rec["demand_zones"]] == \
           [(z["lo"], z["hi"]) for z in base["demand_zones"]]
    assert min(z["lo"] for z in rec["demand_zones"]) > 92.0
    # the prior CLOSED bar is the frame's last close
    assert rec["prev_close"] == round(float(closed["close"].iloc[-1]), 2)
    # the liquidity read saw today's bar
    assert rec["liquidity"]["last_close"] == 110.0


def test_NEGATIVE_without_a_partial_bar_the_frame_prices_itself_as_before():
    closed = frame("2026-09-11")
    rec = DR.decide_from_frame(closed, "TEST")
    assert rec["price_basis"] == "frame"
    assert rec["last_price"] == round(float(closed["close"].iloc[-1]), 2)
    assert rec["prev_close"] == round(float(closed["close"].iloc[-2]), 2)


def test_a_given_print_prices_the_record_and_the_frame_is_the_prior_close():
    closed = frame("2026-09-11")
    rec = DR.decide_from_frame(closed, "TEST", last_price=111.111)
    assert rec["price_basis"] == "given"
    assert rec["last_price"] == 111.11
    assert rec["prev_close"] == round(float(closed["close"].iloc[-1]), 2)


def test_analyze_symbol_splits_the_partial_bar_during_the_session(monkeypatch):
    from sepa import prices
    df = pd.concat([frame("2026-09-11"), today_row("2026-09-14", 110.0, 92.0)])
    monkeypatch.setattr(prices, "load_prices", lambda sym, period=None, **kw: df)
    monkeypatch.setattr(DR, "_session_fraction", lambda now=None: 0.4)
    real_split = DR.split_today_partial
    monkeypatch.setattr(DR, "split_today_partial",
                        lambda f, now_et=None: real_split(f, now_et=datetime(2026, 9, 14, 12, 0, tzinfo=ET)))
    rec = DR.analyze_symbol("TEST")
    assert rec["price_basis"] == "today_partial"
    assert rec["structure_through"] == "2026-09-11"
    assert min(z["lo"] for z in rec["demand_zones"]) > 92.0


# ── 3. the board's band on the Support tab ───────────────────────────────────
@pytest.fixture
def loaded(monkeypatch):
    from sepa import prices
    df = frame("2026-09-11")
    monkeypatch.setattr(prices, "load_prices", lambda sym, period=None, **kw: df)
    monkeypatch.setattr(S, "_overlay_today",
                        lambda prices_mod, d, sym: (d, d.index[-1].date().isoformat(), None, False))
    return df


def test_board_read_IS_the_decision_functions_band(loaded):
    """No second engine: the band the tab draws dashed is decide_from_frame's
    entry band and the alert gate's first overhead on the same closed frame."""
    px = float(loaded["close"].iloc[-1])
    rec = DR.decide_from_frame(loaded, "TEST", last_price=px)
    board = S.board_read(loaded, "TEST", px)
    assert board is not None
    dem = rec.get("entry_zone") or rec.get("nearest_support")
    assert (board["demand"]["lo"], board["demand"]["hi"]) == (round(dem["lo"], 2), round(dem["hi"], 2))
    assert board["geom"] == DR.zone_geom()
    assert board["lookback_bars"] == pz.LOOKBACK_BARS
    if board["supply"]:
        assert board["supply"]["lo"] > px or board["supply"]["lo"] <= px <= board["supply"]["hi"]


def test_every_daily_view_carries_the_board_band_as_its_own_family(loaded):
    out = S.for_symbol("TEST", "6m")
    assert "error" not in out, out
    kinds = [b["kind"] for b in out["tile"]["bands"]]
    assert "board_demand" in kinds
    assert any(b["label"].startswith("board demand") for b in out["tile"]["bands"] if b["kind"] == "board_demand")
    assert out["board"]["demand"] is not None
    keys = [s["k"] for s in out["tile"]["stats"]]
    assert "board demand band" in keys and "board overhead" in keys
    assert out["tile"]["why"].startswith("BOARD (what alerts and lanes use):")
    assert "dashed band is the demand BOARD's band" in out["note"]


def test_the_board_band_does_NOT_replace_the_tabs_own_levels(loaded):
    out = S.for_symbol("TEST", "6m")
    kinds = [b["kind"] for b in out["tile"]["bands"]]
    assert "demand" in kinds or "supply" in kinds   # the finer levels are still drawn
    assert out["supports"] or out["overhead"]       # and still listed


def test_NEGATIVE_no_board_read_means_no_board_rows_and_no_prefix():
    assert S._board_bands(None) == []
    assert S._board_stats(None) == []
    assert S._board_why(None) == ""


def test_NEGATIVE_the_board_band_is_the_boards_geometry_not_the_tabs():
    """The whole point: a frame where the fine and the board geometries
    disagree must show the BOARD's answer in the board family."""
    df = frame("2026-09-11")
    px = float(df["close"].iloc[-1])
    fine = pz.compute(df, last_price=px, max_zones=None)
    board = S.board_read(df, "TEST", px)
    wide = pz.compute(df, last_price=px, max_zones=None, **DR.zone_geom())
    wide_bands = {(round(z["lo"], 2), round(z["hi"], 2)) for z in wide["demand_zones"] + wide["supply_zones"]}
    assert (board["demand"]["lo"], board["demand"]["hi"]) in wide_bands
    assert fine is not None
