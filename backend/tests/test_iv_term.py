"""SPY IV term structure from the option chain (2026-09-06). Pure maths over
canned contracts — no network."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from sepa import iv_term as T

TODAY = date(2026, 9, 8)


def _c(exp, strike, side, iv, spot=770.0):
    return {"details": {"ticker": "O:SPY%s%s%08d" % (exp.replace("-", "")[2:], side[0].upper(), int(strike * 1000)),
                        "expiration_date": exp, "strike_price": strike, "contract_type": side},
            "implied_volatility": iv, "underlying_asset": {"price": spot}}


def _exp(days):
    return (TODAY + timedelta(days=days)).isoformat()


def test_atm_iv_is_the_mean_of_call_and_put_at_the_strike_nearest_spot():
    cs = [_c(_exp(9), 770, "call", 0.12), _c(_exp(9), 770, "put", 0.14),
          _c(_exp(9), 765, "call", 0.20), _c(_exp(9), 775, "put", 0.21),
          _c(_exp(30), 771, "call", 0.15),                       # put has no IV
          _c(_exp(30), 771, "put", None),
          _c(_exp(30), 760, "call", 0.30)]
    pts = T.atm_iv_by_expiry(cs, 770.19)
    assert pts[_exp(9)]["strike"] == 770 and pts[_exp(9)]["iv"] == pytest.approx(0.13)
    assert pts[_exp(9)]["legs"] == 2
    assert pts[_exp(30)]["strike"] == 771 and pts[_exp(30)]["iv"] == 0.15 and pts[_exp(30)]["legs"] == 1
    assert T.atm_iv_by_expiry([], 770.0) == {}


def test_tenor_iv_interpolates_in_total_variance_between_bracketing_expiries():
    pts = {_exp(75): {"iv": 0.16}, _exp(103): {"iv": 0.18}}
    r = T.tenor_iv(pts, 90, TODAY)
    assert r["method"] == "variance_interp" and r["expiries"] == [_exp(75), _exp(103)]
    t1, t2, t = 75 / 365, 103 / 365, 90 / 365
    var = 0.16 ** 2 * t1 + (0.18 ** 2 * t2 - 0.16 ** 2 * t1) * (t - t1) / (t2 - t1)
    assert r["iv"] == pytest.approx((var / t) ** 0.5, rel=1e-9)
    assert 0.16 < r["iv"] < 0.18


def test_tenor_iv_exact_and_nearest_and_min_dte():
    pts = {_exp(30): {"iv": 0.15}, _exp(1): {"iv": 0.40}, _exp(45): {"iv": 0.16}}
    assert T.tenor_iv(pts, 30, TODAY)["method"] == "exact"
    r = T.tenor_iv(pts, 9, TODAY)                     # only expiries above 9d (1d skipped)
    assert r["method"] == "nearest" and r["expiries"] == [_exp(30)]
    assert T.tenor_iv({}, 30, TODAY) is None
    assert T.tenor_iv({_exp(1): {"iv": 0.4}}, 9, TODAY) is None   # under MIN_DTE


def test_curve_builds_the_badge_block_with_ratios_and_shape():
    cs = []
    for days, iv in ((8, 0.12), (10, 0.13), (30, 0.15), (75, 0.16), (103, 0.18)):
        cs.append(_c(_exp(days), 770, "call", iv))
        cs.append(_c(_exp(days), 770, "put", iv))
    out = T.curve(cs, 770.19, TODAY, fetched_at=1.0)
    assert out["source"] == "spy_chain" and out["underlying"] == 770.19 and out["stale"] is False
    assert out["iv30d"] == 15.0 and 12.0 < out["iv9d"] < 13.0 and 16.0 < out["iv90d"] < 18.0
    assert out["ratio_9d_30d"] == pytest.approx(out["iv9d"] / 15.0, abs=0.002)
    assert out["ratio_30d_90d"] == out["ratio_30d_3m"]
    assert out["ratio_30d_90d"] == pytest.approx(15.0 / out["iv90d"], abs=0.002)
    assert out["shape"] == "contango" and out["as_of"] == TODAY.isoformat()
    assert [p["tenor_days"] for p in out["points"]] == [9, 30, 90]
    assert out["points"][0]["method"] == "variance_interp" and out["points"][1]["method"] == "exact"
    assert out["vix9d"] is None and out["vix3m"] is None


def test_curve_without_any_usable_iv_is_none_and_a_lone_expiry_is_nearest():
    assert T.curve([_c(_exp(8), 770, "call", None)], 770.0, TODAY) is None
    assert T.curve([], 770.0, TODAY) is None
    out = T.curve([_c(_exp(8), 770, "call", 0.12)], 770.0, TODAY)
    assert out["iv30d"] == 12.0 and out["points"][1]["method"] == "nearest"


def test_spy_curve_is_fenced():
    def boom(today):
        raise RuntimeError("massive down")
    assert T.spy_curve(TODAY, fetch=boom) is None
    assert T.spy_curve(TODAY, fetch=lambda today: (None, [])) is None
    good = lambda today: (770.0, [_c(_exp(30), 770, "call", 0.15), _c(_exp(30), 770, "put", 0.15)])
    out = T.spy_curve(TODAY, fetch=good)
    assert out["iv30d"] == 15.0 and out["iv9d"] == 15.0            # nearest for 9d / 90d
    assert out["points"][0]["method"] == "nearest"


def test_settings_locked():
    assert T.TENORS_DAYS == (9, 30, 90) and T.WINDOW_DAYS == {9: 5, 30: 10, 90: 25}
    assert T.STRIKE_BAND_PCT == 1.0 and T.MIN_DTE == 2 and T.MAX_PAGES == 4
