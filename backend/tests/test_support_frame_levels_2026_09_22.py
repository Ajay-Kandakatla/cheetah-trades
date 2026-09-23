"""An intraday frame reads ITS OWN levels, and the dropdown got smaller.

Ajay, 2026-09-22, across three messages:

  "Once done can you add a 24 hour window for me on the supply demand chart
   please. I am tired of the pre live post.. It give me for an entire week
   with lil candles. I mainly need the support levels for the last 24 hours
   to see the support.. just last 24 hours if you cannot do it then support
   level from market open but I do not have to see previous days in that..
   even if Pre post I am not expecting to see Sept 15 why do I need the look
   at the drop down"

  "Just simpliyfy this drop down. I wanna use this for entries during the day
   and it been useless for that It does help with 6 months but when it comes
   to daily charts and checking support levels for daily. at any giving point
   This has been useless"

THE DEFECT, MEASURED LIVE 2026-09-22 on PTGX at 145.07:

    frame        nearest support band
    5m_live      142.43-144.15   <- the 6-month DAILY band
    5m_today     142.43-144.15   <- the 6-month DAILY band
    15m          140.44-142.48   <- its own bars
    60m          140.44-142.38   <- its own bars
    15m_open     none at all     <- 26 bars is too thin to cluster

Only a frame carrying `ext_hours` swapped the daily frame in before any level
was read — and those are exactly the two frames a person picks FOR AN ENTRY.
Meanwhile today's own 5-minute tape said PTGX was standing INSIDE a
$144.50-$145.96 band tested 13 times. The number he needed was computable and
was being thrown away.

WHAT THESE TESTS PIN
  * every intraday frame's levels come from the frame it draws
  * the gap case the 2026-09-02 comment warned about falls back to daily and
    SAYS SO — never silently
  * the BOARD block does not move: same daily-derived numbers on every frame,
    still labelled "BOARD (what alerts and lanes use)". This is the Rule #10
    guard — nothing the alerts or the lanes read may follow the chart.
  * a retired `?tf=` key still resolves instead of erroring
  * the 24-hour frame's span is true for a THIN name, which a bar budget
    could never promise
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from chart_maps import support as S
from supply_demand import patterns as pat_mod
from supply_demand import timeframes as TF


INTRADAY_KEYS = (TF.M5_TODAY, TF.H24, TF.M15, TF.H1)


# ── fixtures: two frames that cannot be confused for each other ──────────────

def _saw(low: float, high: float, leg: int, cycles: int) -> list:
    seq: list = []
    for _ in range(cycles):
        seq += list(np.linspace(low, high, leg, endpoint=False))
        seq += list(np.linspace(high, low, leg, endpoint=False))
    return seq


def _frame(closes, index) -> pd.DataFrame:
    c = pd.Series(list(closes), dtype=float)
    return pd.DataFrame(
        {"open": c.values, "high": c.values + 0.05, "low": c.values - 0.05,
         "close": c.values, "volume": np.ones(len(c)) * 1e6},
        index=index)


def _daily_frame() -> pd.DataFrame:
    """300 daily bars oscillating 80-92. Every level it holds is under 93."""
    c = _saw(80.0, 92.0, 10, 15)
    return _frame(c, pd.bdate_range("2025-06-02", periods=len(c)))


def _intraday_frame() -> pd.DataFrame:
    """340 five-minute bars oscillating 100-104. DISJOINT from the daily
    frame's price range on purpose: a level from one can never be mistaken
    for a level from the other, so the test needs no tolerance."""
    c = _saw(100.0, 104.0, 10, 17)
    idx = pd.date_range("2026-09-22 08:00", periods=len(c), freq="5min",
                        tz="UTC")
    return _frame(c, idx)


DAILY_LO, DAILY_HI = 79.0, 93.0
INTRA_LO, INTRA_HI = 99.0, 105.0


@pytest.fixture
def tab(monkeypatch):
    """The Support tab with both frames stubbed and nothing else faked."""
    from sepa import prices
    daily = _daily_frame()
    intra = _intraday_frame()
    monkeypatch.setattr(prices, "load_prices", lambda sym, *a, **k: daily.copy())
    monkeypatch.setattr(TF, "intraday_raw", lambda sym, key=None: None)
    monkeypatch.setattr(TF, "frame_for",
                        lambda sym, key, **k: (intra.copy(), {"tf": key}))
    # the opening range is a provider call and is not what this file is about
    monkeypatch.setattr(pat_mod, "opening_range", lambda sym, minutes: None)
    return S


def _all_bands(out: dict) -> list:
    bands = list(out.get("supports") or []) + list(out.get("overhead") or [])
    if out.get("standing_in"):
        bands.append(out["standing_in"])
    return bands


# ── (1) POSITIVE: an intraday frame reads its own levels ────────────────────

@pytest.mark.parametrize("tf", INTRADAY_KEYS)
def test_an_intraday_frame_reads_ITS_OWN_levels_not_the_daily_ones(tab, tf):
    out = tab.for_symbol("TEST", "6m", tf=tf)
    assert not out.get("error"), out.get("error")
    assert out.get("levels_fallback") is None, "this frame holds levels"
    bands = _all_bands(out)
    assert bands, "the intraday frame produced no band at all"
    for b in bands:
        assert INTRA_LO <= b["lo"] <= INTRA_HI, (tf, b)
        assert INTRA_LO <= b["hi"] <= INTRA_HI, (tf, b)
    # …and the daily read of the same symbol is somewhere else entirely, so
    # the assertion above is not accidentally true.
    daily = tab.for_symbol("TEST", "6m", tf="daily")
    for b in _all_bands(daily):
        assert DAILY_LO <= b["lo"] <= DAILY_HI, b


@pytest.mark.parametrize("tf", INTRADAY_KEYS)
def test_the_header_states_which_window_the_levels_came_from(tab, tf):
    """Ajay: "why do I need the look at the drop down" — the span sentence
    has to answer it without him opening anything, on EVERY frame."""
    out = tab.for_symbol("TEST", "6m", tf=tf)
    span = out["chart_span"]
    assert "levels from" in span, span
    assert TF.tf_spec(tf)["bar_label"] in span, span
    # an own-bars frame must not name a DAILY window — nothing was redirected
    assert "of daily bars" not in span, span
    # the job name is for the dropdown; the header talks about bar sizes
    assert TF.tf_spec(tf)["label"] not in span, span


def test_the_DAILY_frame_also_states_its_provenance(tab):
    span = tab.for_symbol("TEST", "6m", tf="daily")["chart_span"]
    assert span == "6 months · levels from these daily bars", span


# ── (2) NEGATIVE: the gap case falls back, and says so ──────────────────────

@pytest.fixture
def gapped(monkeypatch):
    """An intraday window with NO structure — a straight ramp holds no swing
    to cluster. This is the case the 2026-09-02 comment warned about: "after
    a gap, [the intraday window] may hold no level at all"."""
    from sepa import prices
    daily = _daily_frame()
    n = 200
    ramp = np.linspace(100.0, 140.0, n)
    idx = pd.date_range("2026-09-22 08:00", periods=n, freq="5min", tz="UTC")
    monkeypatch.setattr(prices, "load_prices", lambda sym, *a, **k: daily.copy())
    monkeypatch.setattr(TF, "intraday_raw", lambda sym, key=None: None)
    monkeypatch.setattr(TF, "frame_for",
                        lambda sym, key, **k: (_frame(ramp, idx), {"tf": key}))
    monkeypatch.setattr(pat_mod, "opening_range", lambda sym, minutes: None)
    return S


@pytest.mark.parametrize("tf", INTRADAY_KEYS)
def test_NEGATIVE_a_structureless_intraday_window_falls_back_AND_SAYS_SO(
        gapped, tf):
    out = gapped.for_symbol("TEST", "6m", tf=tf)
    assert not out.get("error"), out.get("error")
    fb = out.get("levels_fallback")
    assert fb, "fell through with no levels and no fallback"
    assert fb["from"] == TF.tf_spec(tf)["label"]
    assert fb["to"] == "6 months"
    # THE SENTENCE. A silent fallback would recreate the exact confusion this
    # change removes, so it must be the first thing in the note a reader meets
    # and it must also be visible in the one-line header.
    assert out["note"].startswith(fb["note"]), out["note"]
    assert "held no level" in out["chart_span"], out["chart_span"]
    assert "6 months of daily bars" in out["chart_span"], out["chart_span"]
    # and the levels served really are the daily ones
    bands = _all_bands(out)
    assert bands
    for b in bands:
        assert DAILY_LO <= b["lo"] <= DAILY_HI, b
    # the CHART is still the intraday frame — a fallback moves the numbers,
    # never the candles. (Trimmed to the frame's own budget, so `5m_today`
    # draws its 192 and the rest draw all 200.)
    assert len(out["tile"]["bars"]) == min(200, TF.tf_spec(tf)["bars"])
    assert out["tile"]["bars"][0]["t"].startswith("2026-09-22")


def test_NEGATIVE_the_fallback_is_ABANDONED_when_daily_holds_nothing_either(
        monkeypatch):
    """If neither frame holds a level, the honest answer is the intraday read
    that was asked for — empty lists and all. Turning that into an error would
    be a fresh regression on 15m/60m, which render an empty read today."""
    from sepa import prices
    n = 200
    ramp = np.linspace(100.0, 140.0, n)
    idx = pd.date_range("2026-09-22 08:00", periods=n, freq="5min", tz="UTC")
    flat = _frame(np.linspace(10.0, 90.0, 300),
                  pd.bdate_range("2025-06-02", periods=300))
    monkeypatch.setattr(prices, "load_prices", lambda sym, *a, **k: flat.copy())
    monkeypatch.setattr(TF, "intraday_raw", lambda sym, key=None: None)
    monkeypatch.setattr(TF, "frame_for",
                        lambda sym, key, **k: (_frame(ramp, idx), {"tf": key}))
    monkeypatch.setattr(pat_mod, "opening_range", lambda sym, minutes: None)
    out = S.for_symbol("TEST", "6m", tf=TF.M5_TODAY)
    if out.get("error"):
        # a refusal is acceptable — what is not acceptable is claiming a
        # fallback that did not happen
        assert out.get("levels_fallback") is None
    else:
        assert out.get("levels_fallback") is None
        assert out["chart_span"].endswith("levels from these 5-minute bars")


# ── (3) RULE #10: the board block does not move ─────────────────────────────

def test_the_BOARD_block_is_the_SAME_on_every_frame(tab):
    """NOTHING THE ALERTS OR THE LANES READ MAY FOLLOW THE CHART.

    The `board` block is `demand_reentry.decide_from_frame` at the board's own
    geometry on the DAILY closed frame — the one rule every S/D board, the
    alert gate and the paper lanes run. The chart's levels now follow the
    frame; this must not. Two readings, each labelled, never conflated.
    """
    boards = {tf: S.for_symbol("TEST", "6m", tf=tf).get("board")
              for tf in ("daily",) + INTRADAY_KEYS}
    ref = boards["daily"]
    assert ref, "the board block vanished from the daily view"
    for tf, got in boards.items():
        assert got == ref, (tf, got, ref)


def test_the_board_block_is_LABELLED_as_what_the_alerts_use(tab):
    for tf in ("daily",) + INTRADAY_KEYS:
        out = S.for_symbol("TEST", "6m", tf=tf)
        why = " ".join(w.get("text", w) if isinstance(w, dict) else str(w)
                       for w in [out["tile"]["why"]])
        assert "BOARD (what alerts and lanes use)" in why, tf
        assert S.BOARD_NOTE in out["note"], tf
        kinds = {b.get("kind") for b in out["tile"]["bands"]}
        assert "board_demand" in kinds or "board_supply" in kinds, tf


def test_NEGATIVE_the_board_read_never_runs_on_intraday_bars():
    """Source guard. `board_read` must be handed the DAILY closed frame on an
    intraday timeframe — handing it 5-minute bars would mint a "board band"
    the board has never seen and cannot reproduce."""
    import inspect
    src = inspect.getsource(S.for_symbol)
    assert "board_closed = daily_closed if intraday else closed" in src
    assert "board_read(board_closed, sym, board_px)" in src
    assert "board_read(closed, sym, last_price)" not in src


def test_NEGATIVE_a_five_minute_frame_writes_nothing_to_the_signal_ledger(tab,
                                                                         monkeypatch):
    """The horizon table knows 15m and 60m and defaults everything else to 72
    hours. Filing a five-minute call under a three-day outcome would quietly
    corrupt the accuracy ledger, so these frames record nothing."""
    seen = []
    monkeypatch.setattr(S, "_record_signal",
                        lambda *a, **k: seen.append(a[1] if len(a) > 1 else None))
    for tf in (TF.M5_TODAY, TF.H24):
        S.for_symbol("TEST", "6m", tf=tf)
    assert seen == [], seen


# ── (4) NEGATIVE: a retired key still resolves ──────────────────────────────

@pytest.mark.parametrize("retired, lands_on", sorted(TF.RETIRED.items()))
def test_NEGATIVE_a_retired_tf_key_still_resolves_and_never_errors(
        tab, retired, lands_on):
    """He has these links open. A removed key must land on the nearest
    surviving frame — never error, and never fall back to Daily without a
    word."""
    assert TF.parse_tf(retired) == lands_on
    assert lands_on != TF.DAILY, "a silent drop to Daily is the banned outcome"
    out = tab.for_symbol("TEST", "6m", tf=retired)
    assert not out.get("error"), out.get("error")
    assert out["timeframe"] == lands_on
    assert out["timeframe_label"] == TF.tf_spec(lands_on)["label"]


def test_NEGATIVE_a_retired_key_is_gone_from_the_offered_frames():
    offered = {o["key"] for o in TF.tf_options(include_live=True)}
    for retired in TF.RETIRED:
        assert retired not in offered, retired


# ── (5) the dropdown shrank, and every option states a TRUE span ────────────

def test_the_dropdown_is_at_most_five_options_named_by_the_job():
    opts = TF.tf_options(include_live=True)
    assert len(opts) <= 5, [o["key"] for o in opts]
    for o in opts:
        assert o["span"] == f"{o['bar_label']} bars · {o['window_label']}"
        # the job name must not just restate the bar size
        assert o["bar_label"] not in o["label"], o


def test_ONE_option_answers_last_24_hours_and_ONE_answers_from_the_open():
    """He asked for both, in that order of preference."""
    by_key = {o["key"]: o for o in TF.tf_options(include_live=True)}
    assert "24 hours" in by_key[TF.H24]["window_label"]
    assert TF.tf_spec(TF.H24)["days"] >= 2, "24h needs more than today's fetch"
    today = by_key[TF.M5_TODAY]
    assert "today only" in today["window_label"]
    assert TF.tf_spec(TF.M5_TODAY)["days"] == 1


def test_a_THIN_name_gets_the_24_hours_it_was_promised():
    """THE REASON `24h` IS TIME-WINDOWED. A fixed BAR COUNT makes the span a
    function of liquidity: measured 2026-09-22, the retired `5m_live`'s
    480-bar budget drew 3 sessions of NVDA and 5 of PTGX — 2026-09-16 onward,
    which is the "I am not expecting to see Sept 15" complaint — under one
    label claiming "last ~2.5 sessions". A clock slice cannot do that.
    """
    # a name that prints ~12 bars a session over six sessions
    blocks = []
    for day in ("2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18",
                "2026-09-21", "2026-09-22"):
        idx = pd.date_range(f"{day} 10:00", f"{day} 11:00", freq="1min",
                            tz="America/New_York").tz_convert("UTC")
        blocks.append(pd.DataFrame(
            {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05,
             "volume": 100, "session": "rth"}, index=idx))
    thin = pd.concat(blocks).sort_index()

    df, meta = TF.frame_for("THIN", TF.H24, raw=thin, allow_ext=True)
    assert df is not None and len(df)
    span_h = (df.index.max() - df.index.min()) / pd.Timedelta(hours=1)
    assert span_h <= 24, span_h
    et = df.index.tz_convert("America/New_York")
    assert set(et.date) == {pd.Timestamp("2026-09-22").date()}, sorted(set(et.date))
    assert meta["window_hours"] == 24
    # the bar budget is a CEILING the clip never needs
    assert len(df) < TF.tf_spec(TF.H24)["bars"]


def test_NEGATIVE_the_24h_slice_is_anchored_on_the_TAPE_not_on_now():
    """Anchoring on wall-clock now() would serve an empty chart every weekend
    and every holiday, and would make this untestable without freezing time."""
    idx = pd.date_range("2026-09-18 14:00", "2026-09-18 15:00", freq="1min",
                        tz="UTC")                       # days before "today"
    old = pd.DataFrame({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05,
                        "volume": 100, "session": "rth"}, index=idx)
    df, meta = TF.frame_for("OLD", TF.H24, raw=old, allow_ext=True)
    assert df is not None and len(df), "a stale tape must still draw"
    assert meta["window_hours"] == 24


# ── (6) NEGATIVE: an empty intraday fetch refuses with a named reason ───────

def test_NEGATIVE_an_empty_intraday_fetch_refuses_with_a_NAMED_reason(
        monkeypatch):
    from sepa import prices
    monkeypatch.setattr(prices, "load_prices",
                        lambda sym, *a, **k: _daily_frame())
    monkeypatch.setattr(TF, "intraday_raw", lambda sym, key=None: None)
    monkeypatch.setattr(pat_mod, "opening_range", lambda sym, minutes: None)
    for tf in INTRADAY_KEYS:
        out = S.for_symbol("THIN", "6m", tf=tf)
        assert out.get("error"), tf
        assert "Massive serves minute data" in out["error"], out["error"]
        # the controls must still render — his next move is the dropdown
        assert out["timeframes"] and out["windows"]
        assert out["timeframe"] == tf


def test_NEGATIVE_an_extended_frame_is_still_refused_to_a_structure_caller():
    """The guard that keeps a 07:12 print on 400 shares out of the zone
    engine. Both 5-minute frames carry it; only the Support tab opts out."""
    for tf in (TF.M5_TODAY, TF.H24):
        df, meta = TF.frame_for("X", tf, raw=_intraday_frame())
        assert df is None
        assert "chart frame" in (meta["reason"] or "")
        assert not any(o["key"] == tf for o in TF.tf_options())


# ── (7) NEGATIVE: no NaN reaches the FE ─────────────────────────────────────

def _nans(obj, path="$"):
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += _nans(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out += _nans(v, f"{path}[{i}]")
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        out.append(path)
    elif isinstance(obj, str) and obj.strip().lower() in ("nan", "inf", "-inf"):
        out.append(path)
    return out


@pytest.mark.parametrize("tf", ("daily",) + INTRADAY_KEYS)
def test_NEGATIVE_no_NaN_or_Inf_anywhere_in_the_payload(tab, tf):
    """A NaN breaks the FE's JSON.parse silently and the tab sticks. It has
    happened on this app before (the SSE 'done' event, 2026-05-29)."""
    assert _nans(S.for_symbol("TEST", "6m", tf=tf)) == []


@pytest.mark.parametrize("tf", INTRADAY_KEYS)
def test_NEGATIVE_no_NaN_on_the_fallback_path_either(gapped, tf):
    assert _nans(S.for_symbol("TEST", "6m", tf=tf)) == []
