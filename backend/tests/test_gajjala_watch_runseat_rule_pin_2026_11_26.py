"""📅 Runners — the A+ rule pinned to the 🎬 pipeline's (spec watchrun rev 2 §4 WP-1 "the rule pin", 2026-11-26).

Ajay 2026-11-26: "Make it 30% please after A+" — the same 30 as the pipeline's WIN_MIN_RUN_FROM_TRIGGER_PCT (his
"Unless there are 30% uptrend don't call them winners from our A+ trigger.."). Source text AND behaviour: the pipeline
module is imported from the host folder and `replay_win30.measure` is compared with `runseat.from_trigger` on synthetic
1-minute frames with NO split. The split guard is app-only (HIS CALL #18) and is not part of this pin. Skipped cleanly
when the host folder is absent.
"""
from __future__ import annotations

import importlib
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import runseat as RS

REPLAYS = Path("/Users/ajay/clinet-test/eod-audits/replays")
WIN30 = REPLAYS / "replay_win30.py"
GIF = REPLAYS / "replay_gif.py"
ET = ZoneInfo("America/New_York")
UTC = timezone.utc
D = date(2026, 11, 24)
pytestmark = pytest.mark.skipif(not (WIN30.exists() and GIF.exists()), reason="the host replay folder is absent")


def test_source_text_equals_the_app_constants():
    src, gif = WIN30.read_text(encoding="utf-8"), GIF.read_text(encoding="utf-8")
    assert f"WIN_MIN_RUN_FROM_TRIGGER_PCT = {C.RUNNERS_SEAT_APLUS_PCT}" in src
    assert "L_GRADE_CAN_WIN = True" in src
    assert "max(at.astimezone(UTC) + L.SETTLE, opens)" in gif
    assert "L.fill_window(day)[0]" in gif
    assert "ET_AFTERHOURS_CLOSE" in src
    assert 'session_bounds(ring_date, at)["same_date"]' in gif
    pages = next(line for line in gif.splitlines() if line.startswith("PAGES = "))
    assert set(eval(pages.split("=", 1)[1])) == set(C.RUNNERS_SEAT_PAGES)                 # noqa: S307 — a dict literal


@pytest.fixture(scope="module")
def W():
    sys.path.insert(0, str(REPLAYS))
    try:
        yield importlib.import_module("replay_win30")
    finally:
        sys.path.remove(str(REPLAYS))


def _frame(rows):
    """rows: (ET hh, mm, high) → the load_intraday shape: a naive-UTC minute-START index, OHLC columns."""
    idx = [pd.Timestamp(datetime(D.year, D.month, D.day, hh, mm, tzinfo=ET).astimezone(UTC).replace(tzinfo=None))
           for hh, mm, _ in rows]
    hs = [h for _, _, h in rows]
    return pd.DataFrame({"open": [h * 0.9 for h in hs], "high": hs, "low": [h * 0.8 for h in hs],
                         "close": [h * 0.95 for h in hs], "volume": [1000] * len(hs)}, index=pd.DatetimeIndex(idx))


def _at(d, hh, mm):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).astimezone(UTC)


CASES = {
    "pass": ([(10, 0, 0.95), (10, 30, 1.17), (11, 0, 1.0)], (10, 0), 0.9),
    "under": ([(10, 30, 1.2999), (11, 0, 1.1)], (10, 0), 1.0),
    "exact_bar": ([(10, 1, 1.3)], (10, 0), 1.0),
    "premarket_spike": ([(8, 0, 3.0), (9, 40, 2.5), (10, 0, 1.1)], (8, 0), 1.0),
    "ring_after_close": ([(9, 50, 1.4), (12, 0, 1.2)], (16, 56), 1.0),
    "no_bar": ([(9, 0, 1.4)], (10, 0), 1.0),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_from_trigger_equals_the_pipeline_measure(W, case):
    rows, (hh, mm), trig = CASES[case]
    ring_day = D if case != "ring_after_close" else date(2026, 11, 23)
    at = _at(ring_day, hh, mm)
    day = RS.play_day(ring_day, at)
    assert day == W.RG.play_day(ring_day, at)
    raw = _frame(rows)
    want = W.measure(raw, day, at, trig)
    from chart_maps.gajjala import ledger as L
    got = RS.from_trigger(L.bars_from_frame(raw), day, at, trig)
    for k in ("measured", "passed", "high_px", "high_et", "run_pct", "from_et", "to_et"):
        assert got[k] == want[k], (case, k, got[k], want[k])
    assert RS.measure_start(day, at) == W.RG.measure_start(day, at)
    assert RS.reaches(1.17, 0.9) is W.reaches(1.17, 0.9) is True
    assert RS.reaches(1.1699, 0.9) is W.reaches(1.1699, 0.9) is False
