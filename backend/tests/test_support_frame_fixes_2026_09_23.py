"""The review round on the 2026-09-22 frame change — every defect, pinned.

Four adversarial reviewers read the "an intraday frame reads its own levels"
package. These are the BLOCKING findings that needed backend code, each with
the state that produced them measured live on 2026-09-22 from this worktree:

    frame     PTGX 145.07                    NVDA 228.56
    5m_today  supports []  overhead 145.53-147.71  supports []  overhead []
    24h       byte-identical to 5m_today     byte-identical to 5m_today
    15m       supports 140.44-142.48         supports 224.38-227.68
    daily     supports 142.43-144.15         supports 215.52-218.13

WHAT THIS FILE PINS
  * a JOB name never lands where a BAR SIZE belongs — not in the "no bars"
    error, not in the zone-map's sentences, not in the studies note
  * the recency unit is SERVED, so the surface cannot print a five-minute
    bar as a trading session
  * the empty level tables can name the frame's own scope instead of the
    pinned daily zoom, because the scope is served
  * the tab can say whether THIS frame's BUY/SELL reaches the forward ledger
  * the verdict beside the chart names the band the chart DRAWS
  * `24h` says so when its slice collapses onto one session

Nothing here changes a gate, a threshold or a level computation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from chart_maps import support as S
from supply_demand import patterns as pat_mod
from supply_demand import price_zones as pz
from supply_demand import timeframes as TF


EXT_KEYS = (TF.M5_TODAY, TF.H24)
INTRADAY_KEYS = (TF.M5_TODAY, TF.H24, TF.M15, TF.H1)


# ── fixtures ────────────────────────────────────────────────────────────────

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
    c = _saw(80.0, 92.0, 10, 15)
    return _frame(c, pd.bdate_range("2025-06-02", periods=len(c)))


def _intraday_frame() -> pd.DataFrame:
    c = _saw(100.0, 104.0, 10, 17)
    idx = pd.date_range("2026-09-22 08:00", periods=len(c), freq="5min",
                        tz="UTC")
    return _frame(c, idx)


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
    monkeypatch.setattr(pat_mod, "opening_range", lambda sym, minutes: None)
    return S


@pytest.fixture
def thin(monkeypatch):
    """A name Massive serves no minute data for — the ordinary thin case.
    `frame_for` is REAL here: the point is the sentence it hands back."""
    from sepa import prices
    daily = _daily_frame()
    monkeypatch.setattr(prices, "load_prices", lambda sym, *a, **k: daily.copy())
    monkeypatch.setattr(TF, "intraday_raw", lambda sym, key=None: None)
    monkeypatch.setattr(pat_mod, "opening_range", lambda sym, minutes: None)
    return S


# ── (1) a JOB name is not a noun ────────────────────────────────────────────

@pytest.mark.parametrize("tf", INTRADAY_KEYS)
def test_the_no_bars_error_names_the_BAR_SIZE_not_the_job(thin, tf):
    """Finding 9. Since 2026-09-22 `label` is "Today, for an entry", and the
    error read "No Today, for an entry bars for THIN — no intraday bars".
    The same package fixed this class 190 lines lower and missed this call
    site; `tf_meta` already carries `bar_label`."""
    out = thin.for_symbol("THIN", "6m", tf=tf)
    err = out.get("error") or ""
    assert "no intraday bars" in err, err
    assert err.startswith(f"No {TF.tf_spec(tf)['bar_label']} bars for THIN"), err
    # NEGATIVE: the job name never appears in a sentence built for a noun.
    assert TF.tf_spec(tf)["label"] not in err, err


def test_the_zone_map_and_the_studies_note_get_a_bar_size_to_use(tab):
    """Finding 2. `timeframe_label` is a dropdown row, not an adjective:
    "Entry & stop on The big picture bars" and "not drawn on the The last two
    weeks chart" were both live on this branch. The bar size is served
    alongside so those sentences have a noun."""
    for tf in INTRADAY_KEYS + (TF.DAILY,):
        out = tab.for_symbol("TEST", "6m", tf=tf)
        assert out["timeframe_bar_label"] == TF.tf_spec(tf)["bar_label"], tf
        assert out["timeframe_label"] == TF.tf_spec(tf)["label"], tf
        # the two are genuinely different strings — otherwise this pins nothing
        assert out["timeframe_bar_label"] != out["timeframe_label"], tf


def test_the_zones_payload_serves_the_bar_size_too():
    """Same finding, the /zones side: `price_zones.for_symbol` feeds the
    ticker page's Setup tab, which renders both sentences."""
    import inspect
    src = inspect.getsource(pz.for_symbol)
    assert 'out["timeframe_bar_label"]' in src, src[-400:]
    from supply_demand import api as sd_api
    src2 = inspect.getsource(sd_api)
    assert 'out["timeframe_bar_label"]' in src2


# ── (2) the recency unit, and the scope the tables name ─────────────────────

@pytest.mark.parametrize("tf", INTRADAY_KEYS)
def test_the_level_reads_bar_size_is_SERVED(tab, tf):
    """Findings 5 and 13. `bars_since_test` is a BAR count. On an own-bars
    5-minute frame the surface printed `bars_since_test: 6` as "tested 6
    sessions ago" for a band touched half an hour earlier. The unit has to
    come off the wire — the frame key alone cannot answer it, because on the
    named fallback the frame is 5-minute and the levels are daily."""
    out = tab.for_symbol("TEST", "6m", tf=tf)
    assert not out.get("error"), out.get("error")
    assert out["levels_bar_label"] == TF.tf_spec(tf)["bar_label"], tf


def test_the_daily_frame_still_counts_in_daily_bars(tab):
    out = tab.for_symbol("TEST", "6m", tf=TF.DAILY)
    assert out["levels_bar_label"] == "daily"


@pytest.mark.parametrize("tf", INTRADAY_KEYS)
def test_the_scope_the_tables_name_is_the_frames_own(tab, tf):
    """Findings 3 and 12. The empty "Support below" table was built from
    `window_label` — the pinned DAILY zoom — so on an entry frame with no
    support below price it asserted "No band below price in the last 6
    months", which is both the wrong window AND false about it (PTGX's own
    6-month read holds a band at 142.43-144.15). The scope is served, and it
    is the SAME string the stats row is labelled with."""
    out = tab.for_symbol("TEST", "6m", tf=tf)
    assert not out.get("error"), out.get("error")
    scope = out["levels_scope"]
    assert TF.tf_spec(tf)["bar_label"] in scope, scope
    assert scope != out["window_label"], scope
    # it is the stats row's own label — one fact, one string
    zoom = [s for s in out["tile"]["stats"] if s["k"] == "zoom"]
    assert zoom and zoom[0]["v"] == scope, (zoom, scope)


def test_the_daily_frames_scope_IS_its_zoom(tab):
    out = tab.for_symbol("TEST", "6m", tf=TF.DAILY)
    assert out["levels_scope"] == out["window_label"] == "6 months"


# ── (3) the ledger claim, qualified where it is not true ────────────────────

@pytest.mark.parametrize("tf", EXT_KEYS)
def test_a_five_minute_signal_is_NOT_written_to_the_ledger_and_says_so(tab, tf):
    """Finding 6. `_record_signal` skips `ext_frame`. Until 2026-09-22 the
    ext-frame signal WAS the daily signal, so the tab's "Every BUY/SELL is
    written to the forward ledger" held; it is now the frame's own signal and
    nothing records it."""
    out = tab.for_symbol("TEST", "6m", tf=tf)
    sig = out.get("signal")
    assert sig is not None, "no signal to qualify"
    assert sig["recorded"] is False, tf
    note = sig.get("recorded_note") or ""
    assert "not written to the forward ledger" in note.lower(), note


@pytest.mark.parametrize("tf", (TF.M15, TF.H1, TF.DAILY))
def test_NEGATIVE_the_recorded_frames_carry_no_exception(tab, tf):
    out = tab.for_symbol("TEST", "6m", tf=tf)
    sig = out.get("signal")
    assert sig is not None
    assert sig["recorded"] is True, tf
    assert "recorded_note" not in sig, sig.get("recorded_note")


# ── (4) the verdict names the band the chart draws ──────────────────────────

def _band(lo, hi, kind, touches=3):
    return {"lo": lo, "hi": hi, "mid": round((lo + hi) / 2, 2), "kind": kind,
            "touches": touches, "strength": 50, "bars_since_test": 2,
            "oldest_touch_bars": 40, "touch_dates": []}


def test_the_why_sentence_names_the_DRAWN_band_not_the_raw_one():
    """Finding 16. `verdict` is pz.compute's own raw pool; the chart draws the
    DE-DUPED, merged pool. Measured 2026-09-22, NVDA `5m_today`: the tile drew
    a demand band at 225.56-229.44 while the sentence beside it read "In an
    overhead-supply band ($226.40-$229.98)" — neither the numbers nor the side
    matched and $226.40-$229.98 was drawn nowhere."""
    drawn = _band(225.56, 229.44, "demand", touches=29)
    zones = {"last_price": 228.56,
             "verdict": {"state": "AT_SUPPLY", "entry_read": "caution",
                         "label": ("In an overhead-supply band "
                                   "($226.4–$229.98) — resistance right here; "
                                   "it needs to clear this before it runs.")}}
    levels = S.levels_from_zones(
        {"demand_zones": [drawn], "supply_zones": [], "last_price": 228.56},
        228.56)
    why = S._why(levels, zones, {"label": "192 x 5-minute bars"})
    assert "225.56" in why and "229.44" in why, why
    # NEGATIVE: the band nobody can find is gone
    assert "226.4" not in why, why
    assert "229.98" not in why, why
    # …and the side follows the DRAWN band, using `_verdict`'s own wording
    assert "demand zone" in why, why


def test_an_agreeing_verdict_keeps_its_own_words():
    """The rewrite is not churn: when the raw band IS the drawn band the
    sentence is the engine's, to the character."""
    drawn = _band(144.50, 145.96, "demand", touches=13)
    zones = {"last_price": 145.07,
             "verdict": {"state": "AT_DEMAND",
                         "label": ("In a demand zone ($144.5–$145.96, "
                                   "13x tested) — support is right here.")}}
    levels = S.levels_from_zones(
        {"demand_zones": [drawn], "supply_zones": [], "last_price": 145.07},
        145.07)
    why = S._why(levels, zones, {"label": "79 x 5-minute bars"})
    assert why.startswith("In a demand zone ($144.5–$145.96, 13x tested) — "
                          "support is right here."), why


def test_NEGATIVE_an_in_zone_verdict_with_nothing_drawn_states_no_band():
    """If the merge left price outside every band, the verdict is naming
    numbers the chart does not paint. It says nothing rather than pointing at
    them."""
    below = _band(100.0, 101.0, "demand")
    zones = {"last_price": 145.07,
             "verdict": {"state": "AT_SUPPLY",
                         "label": "In an overhead-supply band ($226.4–$229.98) — x"}}
    levels = S.levels_from_zones(
        {"demand_zones": [below], "supply_zones": [], "last_price": 145.07},
        145.07)
    assert levels["standing_in"] is None
    why = S._why(levels, zones, {"label": "79 x 5-minute bars"})
    assert "226.4" not in why and "229.98" not in why, why


def test_a_verdict_that_is_NOT_in_zone_is_untouched():
    zones = {"last_price": 145.07,
             "verdict": {"state": "MID_RANGE",
                         "label": "Mid-range — support ~0.6% below, "
                                  "resistance ~3.6% above."}}
    levels = S.levels_from_zones(
        {"demand_zones": [], "supply_zones": [], "last_price": 145.07}, 145.07)
    why = S._why(levels, zones, {"label": "6 months"})
    assert why.startswith("Mid-range — support ~0.6% below"), why


# ── (5) `24h` says when it collapses onto one session ───────────────────────

def _minutes(start_et: str, hours: float) -> pd.DataFrame:
    n = int(hours * 60)
    idx = (pd.date_range(start_et, periods=n, freq="1min",
                         tz="America/New_York").tz_convert("UTC"))
    c = _saw(100.0, 104.0, 10, (n // 20) + 1)[:n]
    return _frame(c, idx)


def test_the_24h_label_says_when_only_one_session_printed_in_it():
    """Findings 11 and 15. The slice is anchored on the LAST BAR PRESENT and
    the extended session is 16 hours, so once the tape stops the 24-hour
    window IS today's session — measured 2026-09-22 after the close, PTGX
    `5m_today` and `24h` both returned 79 bars 04:10→16:05 with identical
    levels. Two of five dropdown rows are then the same answer, and the span
    text must not assert coverage the chart does not contain."""
    raw = _minutes("2026-09-22 04:00", 12)          # one ET session
    df, meta = TF.frame_for("TEST", TF.H24, allow_ext=True, raw=raw)
    assert df is not None and len(df)
    assert meta["sessions"] == 1, meta
    assert "only" in meta["window_label"], meta["window_label"]
    assert "2026-09-22" in meta["window_label"], meta["window_label"]
    # NEGATIVE: it stops claiming a span it does not hold
    assert "pre-market through after-hours" not in meta["window_label"]


def test_NEGATIVE_a_24h_slice_over_two_sessions_keeps_the_spec_wording():
    raw = _minutes("2026-09-21 18:00", 22)          # crosses the ET date
    df, meta = TF.frame_for("TEST", TF.H24, allow_ext=True, raw=raw)
    assert df is not None and len(df)
    assert meta["sessions"] == 2, meta
    assert meta.get("window_label") is None, meta
    assert TF.tf_spec(TF.H24)["window_label"].startswith("the 24 hours")


def test_the_served_span_follows_the_frame_not_the_spec(monkeypatch):
    """And the sentence a reader meets is built from what the FRAME said, so
    the header and the label cannot disagree."""
    from sepa import prices
    daily = _daily_frame()
    raw_meta = {"tf": TF.H24, "bar_label": "5-minute",
                "window_label": "the 24 hours up to the last print — only "
                                "2026-09-22 printed in it",
                "sessions": 1}
    intra = _intraday_frame()
    monkeypatch.setattr(prices, "load_prices", lambda sym, *a, **k: daily.copy())
    monkeypatch.setattr(TF, "intraday_raw", lambda sym, key=None: None)
    monkeypatch.setattr(TF, "frame_for",
                        lambda sym, key, **k: (intra.copy(), dict(raw_meta)))
    monkeypatch.setattr(pat_mod, "opening_range", lambda sym, minutes: None)
    out = S.for_symbol("TEST", "6m", tf=TF.H24)
    assert not out.get("error"), out.get("error")
    assert "only 2026-09-22 printed in it" in out["chart_span"], out["chart_span"]
    # NEGATIVE: the spec's wider claim is not also printed
    assert "pre-market through after-hours" not in out["chart_span"]


# ── (6) Rule #10 guard: none of this moved the board ────────────────────────

@pytest.mark.parametrize("tf", INTRADAY_KEYS + (TF.DAILY,))
def test_the_BOARD_block_is_unchanged_by_every_fix_in_this_file(tab, tf):
    """Nothing the alerts or the paper lanes read may follow the chart. The
    board band stays the DAILY-derived one on every frame, and it stays
    labelled as such."""
    out = tab.for_symbol("TEST", "6m", tf=tf)
    board = out.get("board")
    assert board, tf
    for side in ("demand", "supply"):
        b = board.get(side)
        if not b:
            continue
        # the daily fixture oscillates 80-92 and the intraday one 100-104,
        # so anything under 99 came off the DAILY frame. The board's own
        # geometry is wider than the swing pool, hence the loose floor.
        assert 60.0 <= b["lo"] < 99.0, (tf, side, b)
        assert 60.0 <= b["hi"] < 99.0, (tf, side, b)
    why = " ".join(out["tile"]["why"]) if isinstance(out["tile"]["why"], list) \
        else out["tile"]["why"]
    assert "BOARD (what alerts and lanes use)" in why, tf
