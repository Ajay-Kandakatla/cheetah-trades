"""Overnight gappers honesty — the O/N chip follows the NUMBER, and the
extended-session dollar volume is the real overnight tape.

Born 2026-09-01: the board told Ajay SNDK was "+4.4% O/N" on a night SNDK
actually drifted -1.1% after hours — the +4.4% was Monday's regular session,
chipped O/N because the label was set by session state, not by which number
headlined. He asked "will IREN and SNDK bounce then tomorrow? that is a lot
of volume" off exactly that misread (the $ Vol column is 50-day AVERAGE
liquidity, not tonight's volume).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from daytrading.premarket import (  # noqa: E402
    GAP_MIN_PCT, _et_today, _extended_dollar_vol, _headline_move,
)


# ── _headline_move ──────────────────────────────────────────────────────────
def test_closed_small_drift_headlines_the_regular_gap_without_the_chip():
    # The SNDK bar: Monday +4.37% regular, after-hours drift -1.07%.
    move, is_ext = _headline_move("closed", 4.37, -1.07)
    assert move == 4.37
    assert is_ext is False          # -> FE must NOT stamp O/N on +4.4%


def test_closed_material_drift_headlines_the_drift():
    move, is_ext = _headline_move("closed", 1.0, 3.2)
    assert move == 3.2
    assert is_ext is True


def test_premarket_and_afterhours_always_headline_the_live_drift():
    assert _headline_move("premarket", 5.0, 0.4) == (0.4, True)
    assert _headline_move("afterhours", 5.0, -0.6) == (-0.6, True)


def test_regular_session_headlines_the_intraday_gap():
    assert _headline_move("regular", 2.5, None) == (2.5, False)


def test_missing_drift_falls_back_to_gap_everywhere():
    for session in ("premarket", "afterhours", "closed"):
        assert _headline_move(session, 2.5, None) == (2.5, False)


def test_closed_drift_exactly_at_threshold_counts_as_material():
    move, is_ext = _headline_move("closed", 0.5, GAP_MIN_PCT)
    assert (move, is_ext) == (GAP_MIN_PCT, True)


# ── _extended_dollar_vol ────────────────────────────────────────────────────
def _frame(rows):
    idx = pd.DatetimeIndex([r[0] for r in rows])
    return pd.DataFrame(
        {"close": [r[1] for r in rows], "volume": [r[2] for r in rows],
         "session": [r[3] for r in rows]}, index=idx)


def test_afterhours_dollar_volume_sums_only_tonights_ah_bars():
    df = _frame([
        ("2026-08-31 15:59", 100.0, 1_000, "rth"),          # UTC 15:59 = 11:59 ET
        ("2026-08-31 20:05", 101.0, 2_000, "afterhours"),
        ("2026-08-31 20:06", 102.0, 1_000, "afterhours"),
        ("2026-08-28 20:05", 90.0, 9_999, "afterhours"),    # FRIDAY's AH — excluded
    ])
    out = _extended_dollar_vol(df, "afterhours")
    assert out == {"shares": 3_000, "dollars": 101.0 * 2_000 + 102.0 * 1_000}


def test_no_extended_bars_returns_none_not_zero():
    df = _frame([("2026-08-31 15:59", 100.0, 1_000, "rth")])
    assert _extended_dollar_vol(df, "afterhours") is None
    assert _extended_dollar_vol(None, "afterhours") is None
    assert _extended_dollar_vol(df.drop(columns=["session"]), "afterhours") is None


def test_premarket_variant_reads_premarket_bars():
    df = _frame([
        ("2026-08-31 09:00", 50.0, 500, "premarket"),       # 05:00 ET
        ("2026-08-31 14:00", 51.0, 800, "rth"),
    ])
    out = _extended_dollar_vol(df, "premarket")
    assert out == {"shares": 500, "dollars": 50.0 * 500}


def test_zero_share_extended_session_returns_none():
    df = _frame([("2026-08-31 20:05", 101.0, 0, "afterhours")])
    assert _extended_dollar_vol(df, "afterhours") is None


# ── _et_today ───────────────────────────────────────────────────────────────
def test_et_today_is_the_et_calendar_date(monkeypatch):
    # 01:30 UTC "tomorrow" is 21:30 ET "today" — utcnow().date() names the
    # wrong day for the exact hours the overnight board is most read.
    frozen = pd.Timestamp("2026-09-01 01:30", tz="UTC")   # bind BEFORE the patch

    class FakeTs:
        @staticmethod
        def now(tz=None):
            return frozen.tz_convert(tz)
    monkeypatch.setattr(pd, "Timestamp", FakeTs)
    assert str(_et_today()) == "2026-08-31"
