"""A moat score of 0 FROM DATA is NONE, not UNKNOWN (2026-11-01).

`compute_moat` labelled ANY score of 0 "UNKNOWN" / tier 0, so Ford — 6 of 6
inputs read, every one of them poor — got the card's "No moat data —
yfinance is missing fundamentals". 79 served names were in that state on
2026-11-01. UNKNOWN is now only "could not score at all" (0 finite inputs:
an ETF, a Yahoo 404). Scoring is unchanged; only the label / tier of a 0.

Hermetic: yfinance is a stand-in returning the info dict under test.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sepa import moat as moat_mod  # noqa: E402

# Ford's live .info values, read 2026-10-12 (the case that surfaced this).
FORD = {"returnOnEquity": -0.18252, "grossMargins": 0.07115,
        "operatingMargins": 0.018819999, "freeCashflow": -7940250112,
        "totalRevenue": 187972993024, "totalDebt": 163296002048,
        "totalCash": 22119999488, "ebitda": 7642999808, "revenueGrowth": -0.038}
# An ETF / a quoteSummary 404: price fields only, no fundamentals.
NO_FUNDAMENTALS = {"quoteType": "ETF", "regularMarketPrice": 610.0,
                   "symbol": "SPY", "trailingPegRatio": None}
NAN = float("nan")


class _Ticker:
    def __init__(self, info):
        self.info = info


@pytest.fixture(autouse=True)
def _closed_breaker():
    moat_mod.reset_breaker()
    yield
    moat_mod.reset_breaker()


def _read(info):
    with mock.patch.object(moat_mod.symbols, "yf_ticker", return_value=_Ticker(info)):
        return moat_mod.compute_moat("X")


def test_ford_full_data_zero_score_is_NONE_not_UNKNOWN():
    m = _read(FORD)
    assert m["score"] == 0.0 and m["data_completeness"] == 6
    assert m["label"] == "NONE" and m["tier"] == 1
    assert m["is_partial"] is False
    assert m["narrative"] == "No measurable moat fingerprint — likely commodity / cyclical."


def test_one_input_zero_score_is_NONE_and_flagged_partial():
    m = _read({"revenueGrowth": -0.05})
    assert m["score"] == 0.0 and m["data_completeness"] == 1
    assert (m["label"], m["tier"], m["is_partial"]) == ("NONE", 1, True)


def test_NEGATIVE_zero_inputs_stays_UNKNOWN():
    m = _read(NO_FUNDAMENTALS)
    assert m["data_completeness"] == 0
    assert (m["label"], m["tier"], m["is_partial"]) == ("UNKNOWN", 0, False)
    assert m["narrative"] == "Insufficient data to score moat."


def test_NEGATIVE_nan_inputs_are_not_data_and_stay_UNKNOWN():
    m = _read({"returnOnEquity": NAN, "grossMargins": NAN,
               "operatingMargins": NAN, "revenueGrowth": NAN})
    assert m["data_completeness"] == 0
    assert (m["label"], m["tier"]) == ("UNKNOWN", 0)


def test_nan_beside_one_real_input_counts_only_the_real_one():
    m = _read({"returnOnEquity": NAN, "revenueGrowth": -0.02})
    assert m["data_completeness"] == 1
    assert (m["label"], m["tier"]) == ("NONE", 1)


def test_scored_tiers_unchanged():
    assert _read({"revenueGrowth": 0.05})["label"] == "NONE"          # 3 points
    wide = _read({"returnOnEquity": 0.30, "grossMargins": 0.60,
                  "operatingMargins": 0.30, "freeCashflow": 30,
                  "totalRevenue": 100, "totalDebt": 10, "totalCash": 50,
                  "ebitda": 40, "revenueGrowth": 0.20})
    assert (wide["label"], wide["tier"], wide["score"]) == ("WIDE", 4, 100.0)


def test_scale_band_negative_scores_zero_with_or_without_the_flag():
    # pins the documented behaviour: no band here has a negative threshold
    fcf_bands = [(25, 25), (15, 18), (8, 10), (0, 5)]
    assert moat_mod._scale_band(-4.2, fcf_bands, cap=25, allow_negative_zero=True) == 0
    assert moat_mod._scale_band(-4.2, fcf_bands, cap=25) == 0
    assert moat_mod._scale_band(0.0, fcf_bands, cap=25, allow_negative_zero=True) == 5
    assert moat_mod._scale_band(NAN, fcf_bands, cap=25) == 0
    assert moat_mod._scale_band(None, fcf_bands, cap=25) == 0


def test_a_NONE_from_data_is_not_a_lost_input_read():
    # the 10-11 guard keys off data_completeness, never the label
    m = _read(FORD)
    assert moat_mod.lost_inputs(m, {"tier": 3, "data_completeness": 6}) is False
