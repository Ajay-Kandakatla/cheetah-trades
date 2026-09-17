"""`5m_today` — the today-only 5-minute chart frame (Ajay 2026-09-17).

Ajay, on a CRDO 5-minute chart that spanned Sep 15/16/17: "For the live 5 min
chart data, can you make sure its only showing from todays open only. it going
till 6 months." Asked the two open questions he answered "Today 04:00 ET —
incl. pre-market" and "No — keep current default, just add it."

So this file guards an ADDITION. The negatives carry the weight: `5m_live`'s
3-session span is the overnight view he asked for on 2026-09-02 and must not be
eaten by this change; the new frame is still a CHART frame and must stay
refused to any caller that is not drawing; and nothing anywhere may default to
it.
"""
from __future__ import annotations

import pandas as pd
import pytest

from supply_demand import timeframes as TF


# --- fixtures ---------------------------------------------------------------

def _minutes(day: str, start: str, end: str, session: str) -> pd.DataFrame:
    """One block of 1-minute bars stamped in ET, stored UTC (as the loader
    serves them), tagged with the session the minute belongs to."""
    idx = pd.date_range(f"{day} {start}", f"{day} {end}", freq="1min",
                        tz="America/New_York").tz_convert("UTC")
    return pd.DataFrame({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05,
                         "volume": 100, "session": session}, index=idx)


def _two_days() -> pd.DataFrame:
    """Two ET days of extended-hours minutes: pre-market, RTH, after-hours."""
    blocks = []
    for day in ("2026-09-16", "2026-09-17"):
        blocks.append(_minutes(day, "04:00", "04:29", "premarket"))
        blocks.append(_minutes(day, "09:30", "09:59", "rth"))
        blocks.append(_minutes(day, "16:00", "16:29", "afterhours"))
    return pd.concat(blocks).sort_index()


def _et(idx) -> pd.DatetimeIndex:
    return idx.tz_convert("America/New_York")


# --- positive: the spec -----------------------------------------------------

def test_the_today_only_five_minute_spec_is_registered():
    spec = TF.tf_spec(TF.M5_TODAY)
    assert spec["key"] == "5m_today"
    assert spec["days"] == 1
    assert spec["ext_hours"] is True
    assert spec["rule"] == "5min"
    assert spec["swing_window"] == 2
    assert spec["orb_minutes"] == 5
    # The label and the span have to tell him which of the two 5-minute
    # frames he is looking at without opening anything.
    assert spec["label"] == "5 min · today only · from 04:00 ET"
    assert "today only" in spec["span"] and "04:00 ET" in spec["span"]
    assert spec["label"] != TF.tf_spec(TF.M5_LIVE)["label"]


def test_the_bar_budget_covers_the_whole_extended_session():
    """04:00-20:00 ET = 16h = 960 minutes; 960 / 5 = 192 buckets. A budget
    under that would silently clip the morning he reads."""
    assert TF.tf_spec(TF.M5_TODAY)["bars"] == (20 - 4) * 60 // 5 == 192


def test_the_aliases_a_url_might_carry_resolve():
    for raw in ("5m_today", "5TODAY", " today ", "5m_day", "5m_open", "5open"):
        assert TF.parse_tf(raw) == TF.M5_TODAY, raw


# --- positive: the session slice --------------------------------------------

def test_the_frame_is_todays_et_date_only_and_keeps_pre_and_post_market():
    df, meta = TF.frame_for("CRDO", TF.M5_TODAY, raw=_two_days(),
                            allow_ext=True)
    assert df is not None and len(df)
    et = _et(df.index)
    # ONLY the latest ET date — the Sep 16 bars are gone.
    assert set(et.date) == {pd.Timestamp("2026-09-17").date()}
    assert meta["session"] == "2026-09-17"
    assert meta["ext_hours"] is True
    assert meta["available"] is True and meta["bars"] == len(df)
    mins = [t.hour * 60 + t.minute for t in et]
    # a pre-market bucket for TODAY (04:00-09:29 ET) survived …
    assert any(4 * 60 <= m < 9 * 60 + 30 for m in mins), mins
    # … and so did an after-hours one (past 16:00 ET).
    assert any(m > 16 * 60 for m in mins), mins
    # the budget is never the thing doing the cutting on this frame
    assert len(df) <= TF.tf_spec(TF.M5_TODAY)["bars"]


def test_the_frame_reports_the_right_source_and_a_real_as_of():
    raw = _two_days()
    _df, meta = TF.frame_for("CRDO", TF.M5_TODAY, raw=raw, allow_ext=True)
    assert "pre/post market drawn" in meta["source"]
    # as_of is the last raw MINUTE seen, never a future bucket label
    assert meta["as_of"] == str(raw.index[-1])
    assert meta["partial"] is False


# --- NEGATIVE: the overnight view must survive untouched --------------------

def test_the_overnight_view_is_not_eaten_by_the_today_only_frame():
    """Ajay 2026-09-02: "I wanna see where things bounced over night." Pinned
    so the today-only frame can never quietly become the live one."""
    live = TF.tf_spec(TF.M5_LIVE)
    assert live["days"] == 3
    assert live["bars"] == 480
    assert live["label"] == "5 min · live · pre/post market"
    assert live["span"] == ("last ~2.5 sessions of 5-minute bars incl. "
                            "pre/post market")
    assert live["rule"] == "5min" and live["ext_hours"] is True
    for raw in ("live", "5m", "5min", "5m_live", "5m_ext"):
        assert TF.parse_tf(raw) == TF.M5_LIVE, raw


def test_the_live_frame_still_spans_more_than_one_day():
    df, meta = TF.frame_for("CRDO", TF.M5_LIVE, raw=_two_days(),
                            allow_ext=True)
    assert df is not None
    assert set(_et(df.index).date) == {pd.Timestamp("2026-09-16").date(),
                                       pd.Timestamp("2026-09-17").date()}
    # and it is NOT clipped to one session
    assert "session" not in meta


# --- NEGATIVE: still a chart frame, never a structure frame -----------------

def test_the_new_frame_is_refused_when_the_caller_is_not_drawing():
    df, meta = TF.frame_for("CRDO", TF.M5_TODAY, raw=_two_days())
    assert df is None
    assert "chart frame" in (meta["reason"] or "")
    assert meta["available"] is False


def test_the_new_frame_stays_out_of_the_zone_dropdown():
    assert not any(o["key"] == TF.M5_TODAY for o in TF.tf_options())
    assert any(o["key"] == TF.M5_TODAY
               for o in TF.tf_options(include_live=True))
    # the RTH-only frames are untouched by this change
    for k in (TF.H1, TF.M15, TF.M15_OPEN):
        assert not TF.tf_spec(k).get("ext_hours")


def test_the_minute_loader_is_asked_for_extended_hours(monkeypatch):
    import daytrading.data as dd
    seen = {}

    def fake(symbol, start, end, include_premarket=False,
             include_afterhours=False):
        seen[symbol] = (include_premarket, include_afterhours)
        return None
    monkeypatch.setattr(dd, "load_intraday_range", fake)
    TF.intraday_raw("TODAY", TF.M5_TODAY)
    assert seen["TODAY"] == (True, True)


# --- NEGATIVE: empty / junk inputs ------------------------------------------

@pytest.mark.parametrize("raw", [
    pd.DataFrame(),                                   # nothing at all
    pd.DataFrame(columns=["open", "high", "low", "close"]),
])
def test_an_empty_frame_reports_a_reason_instead_of_crashing(raw):
    df, meta = TF.frame_for("CRDO", TF.M5_TODAY, raw=raw, allow_ext=True)
    assert df is None and meta["available"] is False and meta["reason"]


def test_a_single_minute_day_does_not_crash():
    raw = _minutes("2026-09-17", "04:00", "04:00", "premarket")
    df, meta = TF.frame_for("CRDO", TF.M5_TODAY, raw=raw, allow_ext=True)
    assert df is not None and len(df) == 1
    assert meta["session"] == "2026-09-17"


def test_a_tz_naive_index_still_slices_to_one_day():
    raw = _two_days()
    raw.index = raw.index.tz_localize(None)            # UTC, tag dropped
    df, meta = TF.frame_for("CRDO", TF.M5_TODAY, raw=raw, allow_ext=True)
    assert df is not None and meta["session"] == "2026-09-17"


def test_junk_still_falls_back_to_daily():
    for raw in (None, "", "weekly", "4h", "5m_tomorrow", 5, {"tf": "5m_today"}):
        assert TF.parse_tf(raw) == TF.DAILY, raw


# --- NEGATIVE: nothing defaults to it ---------------------------------------

def test_no_default_points_at_the_new_frame():
    assert TF.DEFAULT_TF == TF.DAILY != TF.M5_TODAY
    from chart_maps import support as sup
    assert sup.TF_DEFAULT == TF.DAILY
    from supply_demand import session_board as sb
    assert sb.DEFAULT_TF != TF.M5_TODAY
    assert TF.M5_TODAY not in sb.ANALYSIS_TFS
    # the FE's single control keeps its daily default too
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib"
           / "supportLevels.ts").read_text()
    assert "export const DEFAULT_VIEW = 'daily:1y';" in src
    assert "export const DEFAULT_TF = 'daily';" in src
