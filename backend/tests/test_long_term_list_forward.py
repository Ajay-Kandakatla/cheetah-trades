"""📅 Long Term (2026-11-12) — the forward record: base = the 11-13 OPEN, names never leave,
CI + placebo only from 21 sessions on (critique C7)."""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd
import pytest

from long_term_list import constants as C
from long_term_list import forward as FW


def _frame(rows):
    """rows: [(date, open, close)]"""
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame({"open": [r[1] for r in rows], "high": [max(r[1], r[2]) for r in rows],
                         "low": [min(r[1], r[2]) for r in rows], "close": [r[2] for r in rows],
                         "volume": [1e6] * len(rows)}, index=idx)


def test_base_session_is_the_first_open_day_after_the_save():
    assert FW.base_session("2026-11-12") == "2026-11-13"
    assert FW.base_session("2026-11-13") == "2026-11-16"          # weekend skipped
    assert FW.base_session("2026-11-25") == "2026-11-27"          # Thanksgiving skipped
    assert FW.base_session("2027-03-25") == "2027-03-29"          # Good Friday skipped


def test_last_trading_day_of_week_skips_holidays():
    assert FW.last_trading_day_of_week("2026-11-12") == "2026-11-13"
    assert FW.last_trading_day_of_week("2027-03-23") == "2027-03-25"   # Thu before Good Friday
    assert FW.last_trading_day_of_week("2026-11-24") == "2026-11-27"


def test_freeze_base_uses_the_open():
    frames = {"AAA": _frame([("2026-11-12", 9.0, 10.0), ("2026-11-13", 11.0, 12.0)])}
    b = FW.freeze_base(["AAA"], frames, "2026-11-13")
    assert b == {"session": "2026-11-13", "kind": "open", "prices": {"AAA": 11.0}, "no_base": []}
    assert C.FORWARD_BASE_KIND == "open"


def test_negative_no_base_bar_is_listed_never_dropped():
    frames = {"AAA": _frame([("2026-11-12", 9.0, 10.0)])}
    b = FW.freeze_base(["AAA", "BBB"], frames, "2026-11-13")
    assert b["no_base"] == ["AAA", "BBB"] and b["prices"] == {}
    blk = FW.block([{"at": "2026-11-20", "n_sessions": 6}], base=b, n_headline=2)
    assert blk["counts_line"].startswith("2 without a 2026-11-13 price")


def test_stale_and_carried_names_stay_in_the_mean():
    base = {"session": "2026-11-13", "prices": {"AAA": 10.0, "BBB": 20.0, "CCC": 40.0}, "no_base": []}
    frames = {"AAA": _frame([("2026-11-13", 10.0, 10.5), ("2026-11-20", 10.5, 11.0)]),
              "BBB": _frame([("2026-11-13", 20.0, 21.0), ("2026-11-18", 21.0, 22.0)])}
    p = FW.point(base, frames, "2026-11-20", {"CCC": 30.0})
    assert p["per_symbol"]["AAA"] == {"pct": pytest.approx(10.0), "price": 11.0, "how": "at"}
    assert p["per_symbol"]["BBB"]["how"] == "stale" and p["per_symbol"]["BBB"]["pct"] == pytest.approx(10.0)
    assert p["per_symbol"]["CCC"]["how"] == "carried" and p["per_symbol"]["CCC"]["pct"] == pytest.approx(-25.0)
    assert p["n_stale"] == 1 and p["n_carried"] == 1 and p["n_names"] == 3
    assert p["list_pct"] == pytest.approx((10.0 + 10.0 - 25.0) / 3)


def test_negative_missing_frame_without_a_stored_price_keeps_the_base():
    base = {"session": "2026-11-13", "prices": {"AAA": 10.0}, "no_base": []}
    p = FW.point(base, {}, "2026-11-20", None)
    assert p["per_symbol"]["AAA"] == {"pct": 0.0, "price": 10.0, "how": "carried"}
    assert p["n_names"] == 1


def test_hand_computed_three_name_chain_vs_benchmarks():
    days = ["2026-11-13", "2026-11-16", "2026-11-17"]
    frames = {
        "AAA": _frame([(days[0], 10.0, 10.2), (days[1], 10.2, 10.8), (days[2], 10.8, 11.0)]),
        "BBB": _frame([(days[0], 50.0, 49.0), (days[1], 49.0, 48.0), (days[2], 48.0, 45.0)]),
        "CCC": _frame([(days[0], 4.0, 4.1), (days[1], 4.1, 4.3), (days[2], 4.3, 5.0)]),
        "RSP": _frame([(days[0], 200.0, 201.0), (days[1], 201.0, 202.0), (days[2], 202.0, 204.0)]),
        "SPY": _frame([(days[0], 600.0, 603.0), (days[1], 603.0, 606.0), (days[2], 606.0, 594.0)]),
    }
    base = FW.freeze_base(["AAA", "BBB", "CCC"], frames, days[0])
    p = FW.point(base, frames, days[2], {}, groups={"pankaj": ["CCC"]})
    assert p["list_pct"] == pytest.approx((10.0 + (-10.0) + 25.0) / 3)
    assert p["per_category"]["pankaj"] == pytest.approx(25.0)
    b = FW.bench(frames, days[0], days[2])
    assert b["rsp_pct"] == pytest.approx(2.0) and b["spy_pct"] == pytest.approx(-1.0)
    assert FW.sessions_between(frames["RSP"], days[0], days[2]) == 3


def test_headline_excludes_non_headline_names():
    base = {"session": "d", "prices": {"AAA": 10.0, "TSM": 10.0}}
    frames = {"AAA": _frame([("2026-11-20", 1, 11.0)]), "TSM": _frame([("2026-11-20", 1, 20.0)])}
    p = FW.point(base, frames, "2026-11-20", {}, headline=["AAA"])
    assert p["list_pct"] == pytest.approx(10.0) and p["n_names"] == 1


def test_boot_ci_deterministic_and_brackets_the_mean():
    xs = [1.0, -2.0, 5.0, 3.5, 0.2, -1.1, 7.7, 2.2]
    a = FW.boot_ci(xs, draws=500, seed=7, ci_pct=95.0)
    b = FW.boot_ci(xs, draws=500, seed=7, ci_pct=95.0)
    assert a == b
    m = sum(xs) / len(xs)
    assert a[0] < m < a[1]
    assert FW.boot_ci([]) == (None, None)


def test_placebo_list_equal_to_the_pool_sits_near_50():
    pool = [float(i % 17) - 8.0 for i in range(200)]
    obs = sum(pool) / len(pool)
    pl = FW.placebo(pool, 20, draws=400, seed=3, ci_pct=95.0, observed=obs)
    assert 35.0 <= pl["pctile_of_list"] <= 65.0
    assert pl["lo"] < pl["median"] < pl["hi"] and pl["pool_n"] == 200
    full = FW.placebo(pool, 200, draws=50, seed=3, ci_pct=95.0, observed=obs)
    assert full["pctile_of_list"] == pytest.approx(50.0)


def test_stats_uses_headline_names():
    pt = {"list_pct": 5.0, "per_symbol": {"A": {"pct": 4.0}, "B": {"pct": 6.0}, "TSM": {"pct": 90.0}}}
    st = FW.stats(pt, [1.0, 2.0, 3.0, 4.0], headline=["A", "B"])
    assert st["ci"][1] <= 6.0


_SIGNED_PCT = re.compile(r"[+\-−]\d+(\.\d+)?%")


def test_negative_too_early_has_no_number():
    pts = [{"at": "2026-11-20", "list_pct": 4.2, "rsp_pct": 1.0, "spy_pct": 1.5, "n_sessions": 6,
            "ci": [1.0, 7.0], "placebo": {"median": 1.0, "lo": -2.0, "hi": 3.0, "pctile_of_list": 80.0}}]
    blk = FW.block(pts, "2026-11-20", base={"session": "2026-11-13", "no_base": []}, n_headline=74)
    assert blk["too_early"] is True and blk["points"] == []
    assert blk["line"] == ("Too early — 6 of 21 sessions since the 2026-11-13 open. "
                           "Equal weight across the 74 screened names saved 2026-11-12.")
    assert not _SIGNED_PCT.search(blk["line"]) and "CI" not in blk["line"]


def test_line_after_21_sessions_carries_ci_and_placebo():
    pts = [{"at": "2026-12-14", "list_pct": 4.2, "rsp_pct": 1.0, "spy_pct": 1.5, "n_sessions": 21,
            "ci": [1.0, 7.0], "placebo": {"median": 1.0, "lo": -2.0, "hi": 3.0, "pctile_of_list": 80.0},
            "n_stale": 2, "n_carried": 1}]
    blk = FW.block(pts, "2026-12-14", base={"session": "2026-11-13", "no_base": ["XPEL"]}, n_headline=74)
    assert blk["too_early"] is False
    assert "saved list +4.20% (95% CI +1.00…+7.00 across names)" in blk["line"]
    assert "80th percentile" in blk["line"] and "RSP +1.00%" in blk["line"] and "SPY +1.50%" in blk["line"]
    assert blk["line"].endswith("One window — a tracking line, not a test.")
    assert blk["counts_line"] == ("1 without a 2026-11-13 price · 2 on an older close · "
                                  "1 carried at their last stored price")
    assert blk["points"] == [{"date": "2026-12-14", "list_pct": 4.2, "rsp_pct": 1.0, "spy_pct": 1.5}]


def test_week_sessions_skip_good_friday_and_thanksgiving():
    def open_days(a, b):
        d, out = dt.date.fromisoformat(a), []
        while d <= dt.date.fromisoformat(b):
            if FW.is_open_day(d):
                out.append((d.isoformat(), 1.0, 1.0))
            d += dt.timedelta(days=1)
        return out
    rsp = _frame(open_days("2026-11-13", "2026-11-30"))
    assert "2026-11-26" not in [str(i)[:10] for i in rsp.index]
    assert FW.sessions_between(rsp, "2026-11-13", "2026-11-30") == 11
    rsp27 = _frame(open_days("2027-03-22", "2027-03-29"))
    assert FW.sessions_between(rsp27, "2027-03-22", "2027-03-29") == 5
