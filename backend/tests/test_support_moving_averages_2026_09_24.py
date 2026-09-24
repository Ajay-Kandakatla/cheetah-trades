"""〰️ The three moving averages on the Support tab's own frames (2026-09-24).

Ajay, on a screenshot of this tab's LEDGER checkbox row:

    "I would need 9EMA and 20 SMA here too as check boxes"

The Chart Maps tiles got them on 2026-09-23; this tab builds its OWN tiles in
`chart_maps/support.py`, so they did not reach it. Same engine
(`board._ma_curves`), same three families, same shared checkboxes — the only
thing `_attach_ma` owns is WHICH FRAME and WHICH KEY.

THE TWO THINGS THAT CAN SILENTLY GO WRONG, both pinned here:

1. THE KEY. `board._ma_curves` joins the series to the drawn bars by STRING.
   Daily bars are stamped "%Y-%m-%d"; this tab's INTRADAY bars are stamped
   "%Y-%m-%d %H:%M" in ET. Hand an intraday frame the date-only default and
   NOTHING RAISES — the join matches nothing, every column comes back all-None,
   every curve is dropped as warm-up, and the averages silently never appear on
   a 5-minute chart. `test_NEGATIVE_the_board_default_key_draws_NOTHING_intraday`
   is that bug, kept on purpose.

2. THE FRAME. The averages must be computed on the FULL frame and aligned down,
   never on the drawn window. On daily that is `bars_for(frame_out=...)`; a
   200 SMA under a 1-year chart is a true 200-bar average and must not move
   when he changes the Zoom.

AND ONE RULE INHERITED FROM THIS TAB: an intraday frame's averages are in ITS
OWN BARS. A 20 SMA on the 15-minute chart is twenty 15-minute bars — never
twenty DAYS painted under a 15-minute label, which is the 2026-08-29
"why is one hour showing Monthly?" bug.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import board as B          # noqa: E402
from chart_maps import support as S        # noqa: E402

TONES = ("ema9", "sma20", "sma200")


def _daily(n: int, start: float = 10.0, step: float = 0.1):
    idx = pd.bdate_range("2024-01-01", periods=n)
    return pd.DataFrame({"open": start, "high": start + 1, "low": start - 1,
                         "close": [start + i * step for i in range(n)],
                         "volume": 1e6}, index=idx)


def _intraday(n: int, start: float = 10.0, step: float = 0.01):
    idx = pd.date_range("2026-09-22 13:30", periods=n, freq="5min", tz="UTC")
    return pd.DataFrame({"open": start, "high": start + 1, "low": start - 1,
                         "close": [start + i * step for i in range(n)],
                         "volume": 1e5}, index=idx)


def _curves(tile):
    return {c["tone"]: c for c in (tile.get("curves") or [])}


# ── 1. the daily path ───────────────────────────────────────────────────────
def test_all_three_reach_a_daily_support_tile():
    df = _daily(300)
    tile = {"bars": B._frame_to_bars(df.tail(120))}
    S._attach_ma(tile, df, intraday=False)
    cur = _curves(tile)
    assert set(cur) == set(TONES)
    for c in cur.values():
        assert len(c["values"]) == 120


def test_the_200_is_the_TRUE_200_bar_average_not_the_visible_window():
    """The point of the whole design. A 120-bar view off a 300-bar frame."""
    df = _daily(300)
    tile = {"bars": B._frame_to_bars(df.tail(120))}
    S._attach_ma(tile, df, intraday=False)
    served = _curves(tile)["sma200"]["values"][-1]
    closes = df["close"].tolist()
    assert served == pytest.approx(sum(closes[-200:]) / 200)
    visible_mean = sum(closes[-120:]) / 120
    assert served != pytest.approx(visible_mean), (
        "the 200 SMA equals the visible-window mean — it was computed AFTER "
        "the tail and is a 120-bar average wearing a 200 label")


def test_NEGATIVE_the_200_does_not_move_when_the_zoom_does():
    df = _daily(400)
    last = []
    for window in (60, 120, 250):
        tile = {"bars": B._frame_to_bars(df.tail(window))}
        S._attach_ma(tile, df, intraday=False)
        last.append(_curves(tile)["sma200"]["values"][-1])
    assert last[0] == pytest.approx(last[1]) == pytest.approx(last[2])


# ── 2. the intraday path, and the key that makes it work ───────────────────
def test_all_three_reach_an_INTRADAY_support_tile():
    idf = _intraday(300)
    tile = {"bars": S._frame_bars(idf.tail(80))}
    S._attach_ma(tile, idf, intraday=True)
    cur = _curves(tile)
    assert set(cur) == set(TONES), (
        "an intraday frame served no averages — check the stamp")
    assert all(v is not None for v in cur["ema9"]["values"])


def test_NEGATIVE_the_board_default_key_draws_NOTHING_intraday():
    """THE BUG THIS WRAPPER EXISTS TO PREVENT, kept as a test.

    `board._ma_curves` with its date-only default against bars stamped with
    HH:MM matches nothing and fails SILENTLY — no exception, no curves. If this
    ever starts producing curves, the stamps converged and `_attach_ma`'s
    `intraday` branch can go; until then, deleting it re-introduces the bug.
    """
    idf = _intraday(300)
    tile = {"bars": S._frame_bars(idf.tail(80))}
    B._ma_curves(tile, idf)                       # no stamp — the trap
    assert not (tile.get("curves") or [])


def test_the_intraday_average_is_in_ITS_OWN_BARS_not_days():
    """A 20 SMA on a 5-minute frame is twenty 5-MINUTE closes."""
    idf = _intraday(300)
    tile = {"bars": S._frame_bars(idf.tail(80))}
    S._attach_ma(tile, idf, intraday=True)
    served = _curves(tile)["sma20"]["values"][-1]
    closes = idf["close"].tolist()
    assert served == pytest.approx(sum(closes[-20:]) / 20)


def test_the_intraday_key_FORMAT_is_pinned():
    """Not `_frame_bars() == _intraday_stamp()` — that is a tautology now that
    the first calls the second. The FORMAT itself is the contract, because
    `board._ma_series` is handed this function and joins on its output. A
    13:30 UTC bar is 09:30 ET, the opening print."""
    ts = pd.Timestamp("2026-09-22 13:30", tz="UTC")
    assert S._intraday_stamp(ts) == "2026-09-22 09:30"
    # ...and the drawn bars really do carry exactly that
    bars = S._frame_bars(_intraday(3))
    assert bars[0]["t"] == "2026-09-22 09:30"
    assert [b["t"] for b in bars] == [S._intraday_stamp(t)
                                      for t in _intraday(3).index]


# ── 3. warm-up and short frames ─────────────────────────────────────────────
def test_a_short_frame_serves_NO_200_and_still_serves_the_other_two():
    df = _daily(150)
    tile = {"bars": B._frame_to_bars(df)}
    S._attach_ma(tile, df, intraday=False)
    cur = _curves(tile)
    assert "sma200" not in cur
    assert set(cur) == {"ema9", "sma20"}


def test_NEGATIVE_a_four_bar_frame_serves_no_9_EMA_seeded_on_four_closes():
    df = _daily(4)
    tile = {"bars": B._frame_to_bars(df)}
    S._attach_ma(tile, df, intraday=False)
    assert not (tile.get("curves") or [])


def test_warm_up_is_a_gap_never_a_guess():
    """THE EMA IS THE ONE THAT MATTERS HERE. pandas gives the SMA its warm-up
    for free (`rolling(20)` needs 20 observations), so asserting on the 20 is
    asserting on pandas. `ewm(adjust=False)` emits a value from the very FIRST
    bar — a "9 EMA" of one close — and only the explicit mask stops it. A
    mutation that deletes the mask must fail HERE."""
    df = _daily(60)
    tile = {"bars": B._frame_to_bars(df)}
    S._attach_ma(tile, df, intraday=False)

    ema = _curves(tile)["ema9"]["values"]
    assert ema[:8] == [None] * 8, "the EMA warm-up mask is gone"
    assert ema[8] is not None

    sma = _curves(tile)["sma20"]["values"]
    assert sma[:19] == [None] * 19
    assert sma[19] is not None


# ── 4. it can never break a tile ────────────────────────────────────────────
@pytest.mark.parametrize("frame", [None, pd.DataFrame()])
def test_a_missing_or_empty_frame_leaves_the_tile_alone(frame):
    tile = {"bars": B._frame_to_bars(_daily(30)), "bands": [{"kind": "demand"}]}
    before = dict(tile)
    S._attach_ma(tile, frame, intraday=False)
    assert not (tile.get("curves") or [])
    assert tile["bands"] == before["bands"]


def test_a_frame_that_RAISES_leaves_the_tile_alone():
    class Boom:
        empty = False
        columns = ["close"]

        def __getitem__(self, k):
            raise RuntimeError("bad frame")

    tile = {"bars": B._frame_to_bars(_daily(30)), "bands": []}
    S._attach_ma(tile, Boom(), intraday=False)
    assert not (tile.get("curves") or [])


def test_a_tile_with_no_bars_is_untouched():
    tile = {"bars": []}
    S._attach_ma(tile, _daily(300), intraday=False)
    assert not (tile.get("curves") or [])


def test_never_attached_twice():
    df = _daily(300)
    tile = {"bars": B._frame_to_bars(df.tail(120))}
    S._attach_ma(tile, df, intraday=False)
    n = len(tile["curves"])
    S._attach_ma(tile, df, intraday=False)
    assert len(tile["curves"]) == n


def test_it_rides_ALONGSIDE_an_existing_curve_and_eats_nothing():
    df = _daily(300)
    tile = {"bars": B._frame_to_bars(df.tail(120)),
            "curves": [{"tone": "keltner", "label": "KC mid",
                        "values": [1.0] * 120}]}
    S._attach_ma(tile, df, intraday=False)
    tones = [c["tone"] for c in tile["curves"]]
    assert "keltner" in tones and set(TONES) <= set(tones)


# ── 5. no NaN reaches the payload ──────────────────────────────────────────
def test_no_NaN_survives_to_the_payload():
    import json
    import math

    df = _daily(300)
    df.iloc[5, df.columns.get_loc("close")] = float("nan")
    tile = {"bars": B._frame_to_bars(df.tail(120))}
    S._attach_ma(tile, df, intraday=False)
    json.dumps(tile, allow_nan=False)             # raises if a NaN got through
    for c in tile.get("curves") or []:
        for v in c["values"]:
            assert v is None or not math.isnan(v)


# ── 6. the WIRING — caught by mutation, 2026-09-24 ─────────────────────────
# Every test above hands `_attach_ma` the full frame DIRECTLY, so none of them
# notices if the tile builder stops passing it one. Breaking that wiring
# (`_ma_frame[0]` -> `None`) left all 17 green. These two close it.
import inspect                                                  # noqa: E402
import re                                                       # noqa: E402

SRC = Path(__file__).resolve().parents[1] / "chart_maps" / "support.py"


def test_SOURCE_GUARD_the_daily_tile_asks_bars_for_for_the_UNTAILED_frame():
    src = SRC.read_text(errors="replace")
    assert "frame_out=_ma_frame" in src, (
        "the Support tile no longer asks bars_for for the untailed frame — "
        "its 200 SMA is now a window-length average wearing a 200 label")
    assert re.search(r"_attach_ma\(\s*tile,", src), "_attach_ma is not called"
    assert "_ma_frame[0] if _ma_frame else None" in src, (
        "the untailed frame is captured but never handed to _attach_ma")


def test_SOURCE_GUARD_the_intraday_arm_passes_the_intraday_stamp():
    src = inspect.getsource(S._attach_ma)
    assert "_intraday_stamp if intraday else None" in src, (
        "the intraday arm lost its stamper — the join will match nothing and "
        "the averages will silently vanish from every 5m/15m/60m chart")
