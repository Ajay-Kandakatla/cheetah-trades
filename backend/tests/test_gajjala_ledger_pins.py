"""🏁 Track record — equality pins of chart_maps/gajjala/ledger.py against the 2026-10-14 study script (BUILD_SPEC9
§3.4.4, as amended by AMENDMENTS9 E1, 2026-10-16).

The ledger RE-IMPLEMENTS the small shared pieces (the session clock, the settle minute, the MFE) instead of importing
scripts/gajjala_study.py: the study is a MEASURED artifact (NULL) whose re-run must not move when runtime code is edited,
and its semantics differ from Ajay's answer (it fills unconditionally at the open, stops on "<", recomputes risk from
the fill and exits by rules). These pins prove the pieces that coincide are EQUAL. E1 changed one pin: an alert at or
after the regular close has its same session on the NEXT market day (its first regular session) — never the study's
extended close.
"""
from __future__ import annotations

import ast
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from catalysts.medical.reaction import next_market_day
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from scripts import gajjala_study as S

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
DAYS = (date(2026, 10, 16), date(2026, 11, 2), date(2026, 11, 27), date(2026, 12, 24))   # + DST-end week, 2 half days


def et(d, hh, mm, ss=0, us=0) -> datetime:
    return datetime(d.year, d.month, d.day, hh, mm, ss, us, tzinfo=ET)


@pytest.mark.parametrize("d", DAYS, ids=[d.isoformat() for d in DAYS])
def test_the_same_session_close_is_the_studys_regular_close(d):
    sb = S.session_bounds(d)
    assert LG.session_bounds(d, et(d, 10, 0))["same_end"] == sb["rth_close"]
    late = sb["rth_close"] + timedelta(minutes=30)
    got = LG.session_bounds(d, late)
    assert got["same_end"] == S.session_bounds(next_market_day(d))["rth_close"]          # E1
    assert got["same_end"] != sb["ah_close"]                 # NEGATIVE: never the extended close any more
    assert got["next_end"] == S.session_bounds(next_market_day(next_market_day(d)))["rth_close"]


def test_the_fill_window_opens_at_the_studys_push_open():
    """LEDGER_FILL_FROM_ET = 09:30 + NO_TRADE_AFTER_OPEN_MIN = the study's `push_open` (one rule, two copies pinned)."""
    for d in DAYS:
        assert et(d, GC.LEDGER_FILL_FROM_ET.hour, GC.LEDGER_FILL_FROM_ET.minute) == S.session_bounds(d)["push_open"]


def _grid(d, start, end, px):
    t, stop, rows = et(d, *start), et(d, *end), []
    while t <= stop:
        rows.append({"ts": t.astimezone(UTC).replace(tzinfo=None), "open": px, "high": px, "low": px, "close": px,
                     "volume": 1000.0})
        t += timedelta(minutes=1)
    return rows


def _df(rows):
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"])
    return df.drop_duplicates("ts", keep="last").set_index("ts").sort_index()


def _row(d, at, trig, stop):
    return LG.alert_of({"_id": f"{d}|AAA|bull_flag", "date": d.isoformat(), "symbol": "AAA", "setup": "bull_flag",
                        "first_seen_mode": "normal", "first_trigger": trig, "first_stop": stop,
                        "push": {"state": "pushed", "at": at.astimezone(UTC).isoformat()}}, "potential")


@pytest.mark.parametrize("d", DAYS[:2], ids=[d.isoformat() for d in DAYS[:2]])
def test_the_settle_minute_and_the_open_fill_equal_the_studys_push_fill(d):
    at = et(d, 10, 30, 0, 500000)
    rows = _grid(d, (10, 25), (15, 59), 10.5)                 # every minute opens above the 10.0 trigger
    rows.append({"ts": et(d, 10, 30).astimezone(UTC).replace(tzinfo=None), "open": 12.0, "high": 12.5, "low": 11.9,
                 "close": 12.0, "volume": 1000.0})            # the alert minute itself — never the fill
    df = _df(rows)
    label = pd.Timestamp(at.astimezone(UTC).replace(tzinfo=None))
    end = S.utc_naive(S.session_bounds(d)["rth_close"])
    status, ts, px = S.push_fill(df, label, end)
    row = _row(d, at, 10.0, 9.0)
    g = LG.grade(row, LG.bars_from_frame(df), LG.session_bounds(d, row["at_utc"]), "same")
    assert status == "ok"
    assert LG._parse_at(g["fill_t"]) == ts.tz_localize("UTC").to_pydatetime() == et(d, 10, 31)
    assert g["fill_px"] == px == 10.5


def test_one_mfe_the_best_pct_equals_the_studys_session_mfe_on_a_stop_free_path():
    d = date(2026, 10, 14)
    at = et(d, 10, 30, 0, 500000)
    rows = _grid(d, (10, 31), (15, 59), 10.5)
    for hh, mm, h in ((11, 5, 11.25), (13, 40, 12.375), (15, 59, 10.75)):
        rows.append({"ts": et(d, hh, mm).astimezone(UTC).replace(tzinfo=None), "open": 10.5, "high": h, "low": 10.4,
                     "close": 10.6, "volume": 1000.0})
    rows += _grid(d, (16, 0), (16, 30), 20.0)                 # after the regular close: outside both
    df = _df(rows)
    label = pd.Timestamp(at.astimezone(UTC).replace(tzinfo=None))
    stop = 9.0
    po = S.push_outcomes(df, label, stop, d, "rth", {}, rules=("session",))
    row = _row(d, at, 10.0, stop)
    g = LG.grade(row, LG.bars_from_frame(df), LG.session_bounds(d, row["at_utc"]), "same")
    fill = g["fill_px"]
    assert fill == po["push_fill_px"] == 10.5
    exact = (12.375 - fill) / fill * 100
    assert abs(round(exact, 2) - g["best_pct"]) < 1e-9
    assert abs(exact * fill / 100 - po["mfe_push_session"] * (fill - stop)) < 1e-9


def test_NEGATIVE_the_ledger_imports_nothing_from_scripts():
    tree = ast.parse(Path(LG.__file__).read_text(encoding="utf-8"))
    mods = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + \
        [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [m for m in mods if m == "scripts" or m.startswith("scripts.")], mods
    planted = ast.parse("from scripts import gajjala_study")
    assert [n.module for n in ast.walk(planted) if isinstance(n, ast.ImportFrom)] == ["scripts"]


def test_NEGATIVE_the_study_keeps_its_own_semantics():
    """The study is untouched: it still stops on a strict "<" (the ledger touches with "≤", Q0) and fills its push
    row unconditionally at the open — the two engines stay two."""
    d = date(2026, 10, 14)
    rows = _grid(d, (10, 31), (10, 40), 10.5) + [{"ts": et(d, 10, 41).astimezone(UTC).replace(tzinfo=None),
                                                  "open": 10.0, "high": 10.1, "low": 9.0, "close": 9.5,
                                                  "volume": 1.0}]
    after = _df(rows)
    end = pd.Timestamp(et(d, 16, 0).astimezone(UTC).replace(tzinfo=None))
    assert S.walk_exit(after, 10.5, 9.0, "session", session_end=end)["reason"] == "session_end"   # low == stop: no stop
    row = _row(d, et(d, 10, 30), 10.0, 9.0)
    g = LG.grade(row, LG.bars_from_frame(after), LG.session_bounds(d, row["at_utc"]), "same")
    assert (g["outcome"], g["reason"]) == ("loss", "stop")   # the ledger's touch
