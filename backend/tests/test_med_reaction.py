"""🧬 Medical catalysts — reaction without lookahead (catalysts/medical/reaction.py, §3.7).

Frames are the REAL prod price-cache export for KOD / MIRM / MNOV / HUMA
(tests/fixtures/medical/frames_KOD_MIRM_MNOV_HUMA.json, read-only 2026-09-29).
KOD numbers pinned to spec §1.6: base $32.35, +178.0%, RVOL 57.1, ADV $22.7M.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts.medical import reaction as R   # noqa: E402

ET = ZoneInfo("America/New_York")
FX = Path(__file__).resolve().parent / "fixtures" / "medical"
MON = date(2026, 9, 28)


def et(*a):
    return datetime(*a, tzinfo=ET)


def frame(sym: str) -> pd.DataFrame:
    d = json.loads((FX / "frames_KOD_MIRM_MNOV_HUMA.json").read_text())["frames"][sym]
    df = pd.DataFrame(d, columns=["date", "open", "high", "low", "close", "volume"])
    df.index = pd.to_datetime(df.pop("date"))
    return df


# ── session mapping ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("pub,expected", [
    (et(2026, 9, 28, 2, 34), date(2026, 9, 28)),     # Mon pre-dawn -> Mon
    (et(2026, 9, 28, 15, 59), date(2026, 9, 28)),
    (et(2026, 9, 28, 16, 0), date(2026, 9, 29)),     # at the close -> next day
    (et(2026, 9, 28, 17, 43), date(2026, 9, 29)),    # Mon after hours -> Tue
    (et(2026, 9, 26, 10, 0), date(2026, 9, 28)),     # Saturday -> Monday
    (et(2026, 9, 7, 10, 0), date(2026, 9, 8)),       # Labor Day -> Tuesday
    (et(2026, 11, 27, 13, 30), date(2026, 11, 30)),  # half day, after its 13:00 close
    (et(2026, 11, 27, 12, 59), date(2026, 11, 27)),
])
def test_session_date_for(pub, expected):
    assert R.session_date_for(pub) == expected


def test_released_bucket():
    assert R.released_bucket(et(2026, 9, 28, 2, 34)) == "overnight"
    assert R.released_bucket(et(2026, 9, 28, 6, 30)) == "premarket"
    assert R.released_bucket(et(2026, 9, 28, 11, 0)) == "intraday"
    assert R.released_bucket(et(2026, 9, 28, 17, 43)) == "afterhours"
    assert R.released_bucket(et(2026, 9, 26, 11, 0)) == "closed_day"
    assert R.released_bucket(et(2026, 11, 27, 13, 30)) == "afterhours"


@pytest.mark.parametrize("a,b,mins", [
    (et(2026, 9, 28, 6, 0), et(2026, 9, 28, 9, 20), 0),
    (et(2026, 9, 28, 6, 0), et(2026, 9, 28, 9, 36), 6),
    (et(2026, 9, 28, 6, 0), et(2026, 9, 28, 13, 0), 210),
    (et(2026, 9, 28, 11, 0), et(2026, 9, 28, 11, 5), 5),
    (et(2026, 9, 25, 15, 0), et(2026, 9, 28, 4, 5), 60),   # Fri 15:00 -> Mon 04:05
    (et(2026, 11, 27, 12, 30), et(2026, 11, 27, 14, 0), 30),  # half day closes 13:00
    (et(2026, 9, 7, 9, 0), et(2026, 9, 7, 15, 0), 0),      # holiday
    (et(2026, 9, 26, 9, 0), et(2026, 9, 28, 4, 5), 0),     # Saturday news seen Monday 04:05
    (et(2026, 9, 28, 13, 0), et(2026, 9, 28, 6, 0), 0),    # b <= a
])
def test_rth_minutes_between(a, b, mins):
    assert R.rth_minutes_between(a, b) == pytest.approx(mins)


def test_prev_regular_close():
    assert R.prev_regular_close(et(2026, 9, 28, 17, 0)) == et(2026, 9, 28, 16, 0)
    assert R.prev_regular_close(et(2026, 9, 28, 10, 0)) == et(2026, 9, 25, 16, 0)
    assert R.prev_regular_close(et(2026, 11, 27, 14, 0)) == et(2026, 11, 27, 13, 0)


# ── KOD numbers (spec §1.6) ─────────────────────────────────────────────────
def test_KOD_base_liquidity_close_match_the_spec_numbers():
    df = frame("KOD")
    now = et(2026, 9, 29, 5, 0)
    cf = R.closed_frame(df, now)
    base = R.base_close(cf, None, MON, now)
    assert base == (32.35, "frame")
    liq = R.liquidity(cf, MON)
    assert liq["adv50_usd"] / 1e6 == pytest.approx(22.7, abs=0.05)
    assert liq["frame_last_date"] == "2026-09-25"
    ac = R.at_close(cf, MON, base, liq["avg_vol50"])
    assert ac["day_pct"] == pytest.approx(178.0, abs=0.05)
    assert ac["rvol"] == pytest.approx(57.1, abs=0.05)
    assert ac["basis"] == "closed_bar" and 0 <= ac["close_loc"] <= 1
    assert ac["gap_pct"] == pytest.approx((61.705 / 32.35 - 1) * 100)


def test_MIRM_MNOV_HUMA_bases_are_the_prior_closes():
    now = et(2026, 9, 29, 5, 0)
    for sym, px in (("MIRM", 89.70), ("MNOV", 2.58), ("HUMA", 0.5573)):
        cf = R.closed_frame(frame(sym), now)
        assert R.base_close(cf, None, MON, now)[0] == pytest.approx(px, abs=1e-4), sym
    assert R.liquidity(R.closed_frame(frame("MNOV"), now), MON)["adv50_usd"] / 1e6 == pytest.approx(0.1, abs=0.1)


def test_NEGATIVE_the_event_bar_never_feeds_its_own_base_or_ADV():
    """Append a +178% bar dated the session — base and adv50 unchanged."""
    df = frame("KOD")
    pre = df[df.index < "2026-09-28"]
    b0, l0 = R.base_close(pre, None, MON, et(2026, 9, 29, 5)), R.liquidity(pre, MON)
    b1, l1 = R.base_close(df, None, MON, et(2026, 9, 29, 5)), R.liquidity(df, MON)
    assert b0 == b1 and l0 == l1


def test_intraday_bar_in_the_cache_is_not_a_close_until_16_45():
    """The live-bar overlay trap: the cache carries today's in-progress bar."""
    df = frame("KOD")
    at_1400 = R.closed_frame(df, et(2026, 9, 28, 14, 0))
    assert R.at_close(at_1400, MON, 32.35, 1.0) is None
    at_1646 = R.closed_frame(df, et(2026, 9, 28, 16, 46))
    assert R.at_close(at_1646, MON, 32.35, 1.0) is not None


def test_stale_frame_falls_back_to_the_snapshot_and_stamps_its_basis():
    df = frame("KOD")
    stale = df[df.index < "2026-09-25"]                   # frame ends Thursday
    snap = {"price": 33.0, "prev_day_close": 32.35}
    # Monday pre-market: the snapshot's prior close
    assert R.base_close(stale, snap, MON, et(2026, 9, 28, 6, 0)) == (32.35, "snapshot_prev_close")
    # Friday after the close, for a Monday session: the snapshot's day close
    assert R.base_close(stale, snap, MON, et(2026, 9, 25, 17, 0)) == (33.0, "snapshot_day_close")


def test_NEGATIVE_unknown_base_is_None_so_the_gate_fails_closed():
    assert R.base_close(None, None, MON, et(2026, 9, 28, 6)) == (None, "unknown")
    assert R.base_close(None, {"price": 5.0}, MON, et(2026, 9, 29, 10)) == (None, "unknown")
    assert R.liquidity(None, MON)["adv50_usd"] is None


def test_forward_matured_flags():
    df = frame("KOD")
    fw = R.forward(df, date(2026, 8, 3), 10.0)
    assert fw["matured_5d"] and fw["matured_21d"] and fw["ret_5d_pct"] is not None
    fw2 = R.forward(df, MON, 32.35, 89.92)
    assert fw2 == {"ret_5d_pct": None, "ret_21d_pct": None, "drift_5d_pct": None,
                   "matured_5d": False, "matured_21d": False}
    fw3 = R.forward(df, date(2026, 9, 18), 10.0)
    assert fw3["matured_5d"] and not fw3["matured_21d"]


def test_at_detection_reads_the_extended_hours_print_and_latency():
    snap = {"price": 33.0, "last_trade_price": 55.6, "volume": 1_000_000.0, "prev_day_close": 32.35,
            "last_trade_ts_ms": et(2026, 9, 28, 7, 30).timestamp() * 1e9}     # ns stamp
    d = R.at_detection(snap, (32.35, "frame"), et(2026, 9, 28, 7, 31), avg_vol50=500_000.0,
                       published_et=et(2026, 9, 28, 2, 34), session_date=MON)
    assert d["price"] == 55.6 and d["move_pct"] == pytest.approx((55.6 / 32.35 - 1) * 100)
    assert d["rvol_so_far"] == 2.0 and d["latency_min"] == pytest.approx(297.0)
    assert d["session"] == "premarket" and d["post_session"] is False
    none = R.at_detection({}, (None, "unknown"), et(2026, 9, 28, 7, 31))
    assert none["move_pct"] is None and none["price"] is None
