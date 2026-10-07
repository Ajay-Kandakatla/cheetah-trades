"""Whales data-read defects fixed 2026-10-06.

1. whales_13d matched only the pre-Dec-2024 EDGAR form names ("SC 13D/G").
   EDGAR now files them as "SCHEDULE 13D" / "SCHEDULE 13G" (+ "/A"); 0 of
   3,458 cached docs carried one and VST's 6 post-2025 13G filings were all
   missed (n_form13 = 0).
2. whales major_holders parser read row.iloc[1] off yfinance 1.2.0's 4x1
   index-keyed frame, so `major` was {} in all 4,033 cached docs.
3. moves.n_new / n_sold_out were hard-coded 0; a top-N list cannot prove a
   new position or an exit, so they are None until a real comparison exists.

Every test here fails if its fix is reverted.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from supply_demand import whales, whales_13d


# --- 1. 13D/G form names -------------------------------------------------

NEW_NAMES = ("SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A")
OLD_NAMES = ("SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A")


@pytest.mark.parametrize("form", NEW_NAMES + OLD_NAMES)
def test_both_naming_generations_are_tracked_and_bucketed(form):
    assert form in whales_13d._FORMS_TRACKED
    assert whales_13d._form_bucket(form) == "form13"


@pytest.mark.parametrize("form", ["SC 13E3", "SCHEDULE 13E3", "SC TO-T",
                                  "13F-HR", "SCHEDULE 13", "SC 13", "8-K"])
def test_NEGATIVE_other_schedules_are_not_counted_as_5pct_crossings(form):
    assert form not in whales_13d._FORMS_TRACKED
    assert whales_13d._form_bucket(form) is None


def test_NEGATIVE_form4_and_144_buckets_unchanged():
    assert whales_13d._form_bucket("4") == "form4"
    assert whales_13d._form_bucket("4/A") == "form4"
    assert whales_13d._form_bucket("144") == "form144"


def _d(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).date().isoformat()


@pytest.fixture
def vst_like(monkeypatch):
    rows = [
        {"form": "SCHEDULE 13G",   "filing_date": _d(60),  "accession_number": "0000000001-26-000001", "primary_doc": "a.xml", "primary_doc_desc": None},
        {"form": "SCHEDULE 13G/A", "filing_date": _d(90),  "accession_number": "0000000001-26-000002", "primary_doc": "b.xml", "primary_doc_desc": None},
        {"form": "SC 13G/A",       "filing_date": _d(100), "accession_number": "0000000001-26-000003", "primary_doc": "c.htm", "primary_doc_desc": None},
        {"form": "SCHEDULE 13E3",  "filing_date": _d(10),  "accession_number": "0000000001-26-000004", "primary_doc": "d.htm", "primary_doc_desc": None},
        {"form": "SCHEDULE 13G",   "filing_date": _d(400), "accession_number": "0000000001-25-000005", "primary_doc": "e.xml", "primary_doc_desc": None},
        {"form": "4",              "filing_date": _d(5),   "accession_number": "0000000001-26-000006", "primary_doc": "f.xml", "primary_doc_desc": None},
    ]
    monkeypatch.setattr(whales_13d, "_cache_get", lambda t: None)
    monkeypatch.setattr(whales_13d, "_cache_put", lambda t, p: None)
    monkeypatch.setattr(whales_13d, "_ticker_to_cik", lambda t: "0001692819")
    monkeypatch.setattr(whales_13d, "_fetch_recent_filings", lambda cik: rows)
    return rows


def test_get_13d_counts_schedule_named_filings(vst_like):
    p = whales_13d.get_13d("VST", days=120, force=True)
    forms = [f["form"] for f in p["filings"]]
    assert p["n_form13"] == 3
    assert "SCHEDULE 13G" in forms and "SCHEDULE 13G/A" in forms
    assert "SC 13G/A" in forms                     # old name still works
    assert p["latest"]["form"] == "4"
    assert all(f["bucket"] == "form13" for f in p["filings"] if f["form"] != "4")


def test_NEGATIVE_get_13d_excludes_13e3_and_out_of_window(vst_like):
    p = whales_13d.get_13d("VST", days=120, force=True)
    forms = [f["form"] for f in p["filings"]]
    assert "SCHEDULE 13E3" not in forms
    assert p["n_filings"] == 4                     # 3 x 13G-family + 1 Form 4
    assert all(f["filing_date"] >= _d(120) for f in p["filings"])


# --- 2. major_holders, both yfinance generations ---------------------------

def _new_shape(values=(0.00779, 0.92015, 0.92738, 1881.0)):
    """yfinance 1.2.0 shape, VST values measured 2026-10-06."""
    df = pd.DataFrame(
        {"Value": list(values)},
        index=["insidersPercentHeld", "institutionsPercentHeld",
               "institutionsFloatPercentHeld", "institutionsCount"],
    )
    df.index.name = "Breakdown"
    return df


def _old_shape():
    return pd.DataFrame([
        ["0.78%",  "% of Shares Held by All Insider"],
        ["92.02%", "% of Shares Held by Institutions"],
        ["92.74%", "% of Float Held by Institutions"],
        ["1881",   "Number of Institutions Holding Shares"],
    ])


def test_new_index_keyed_shape_is_parsed():
    m = whales._parse_major_holders(_new_shape())
    assert m == {
        "insider_pct": "0.78%",
        "institutional_pct": "92.02%",
        "institutional_float_pct": "92.74%",
        "n_institutions": 1881,
    }


def test_old_row_wise_shape_still_parsed():
    m = whales._parse_major_holders(_old_shape())
    assert m["insider_pct"] == "0.78%"
    assert m["institutional_pct"] == "92.02%"
    assert m["institutional_float_pct"] == "92.74%"
    assert m["n_institutions"] == 1881


def test_NEGATIVE_old_shape_count_row_does_not_overwrite_institutional_pct():
    m = whales._parse_major_holders(_old_shape())
    assert m["institutional_pct"] != "1881"


@pytest.mark.parametrize("mh", [None, pd.DataFrame()])
def test_NEGATIVE_missing_frame_gives_empty_not_zeros(mh):
    assert whales._parse_major_holders(mh) == {}


def test_NEGATIVE_nan_or_zero_values_are_left_out_not_zeroed():
    m = whales._parse_major_holders(_new_shape((float("nan"), 0.5, float("nan"), 0.0)))
    assert m == {"institutional_pct": "50.00%"}
    assert "n_institutions" not in m and "insider_pct" not in m


def test_NEGATIVE_unknown_index_keys_ignored():
    df = pd.DataFrame({"Value": [0.4]}, index=["somethingElse"])
    assert whales._parse_major_holders(df) == {}


class _FakeYf:
    def __init__(self, mh):
        self.major_holders = mh
        self.institutional_holders = pd.DataFrame()
        self.mutualfund_holders = pd.DataFrame()


def test_fetch_wires_new_shape_into_payload_major(monkeypatch):
    monkeypatch.setattr(whales.symbols, "yf_ticker", lambda t: _FakeYf(_new_shape()))
    raw = whales._fetch_yfinance_holders("VST")
    assert raw["major"]["institutional_pct"] == "92.02%"
    assert raw["major"]["n_institutions"] == 1881


def test_NEGATIVE_fetch_survives_broken_major_holders(monkeypatch):
    class _Boom(_FakeYf):
        @property
        def major_holders(self):
            raise RuntimeError("yahoo 500")

        @major_holders.setter
        def major_holders(self, v):
            pass
    monkeypatch.setattr(whales.symbols, "yf_ticker", lambda t: _Boom(None))
    assert whales._fetch_yfinance_holders("VST")["major"] == {}


# --- 3. n_new / n_sold_out are unknown, not zero ----------------------------

def _holder(pc):
    return {"holder": "FUND", "pct_change": pc, "type": "other",
            "value": 1e9, "pct_held": 0.01}


def test_n_new_and_n_sold_out_are_null_not_zero():
    m = whales._summarize_moves([_holder(0.2), _holder(-0.3), _holder(0.0)])
    assert m["n_new"] is None and m["n_sold_out"] is None
    assert (m["n_buying"], m["n_selling"], m["n_unchanged"]) == (1, 1, 1)


def test_NEGATIVE_null_survives_into_get_whales_payload(monkeypatch):
    monkeypatch.setattr(whales, "_cache_get", lambda t, ignore_ttl=False: None)
    monkeypatch.setattr(whales, "_cache_put", lambda t, p: None)
    monkeypatch.setattr(whales, "_fetch_yfinance_holders", lambda t: {
        "institutional": [dict(_holder(0.2), holder="A", kind="institutional",
                               date_reported="2026-06-30", ticker="VST")],
        "mutual_fund": [], "major": {}})
    p = whales.get_whales("VST", force=True)
    assert "n_new" in p["moves"] and "n_sold_out" in p["moves"]
    assert p["moves"]["n_new"] is None and p["moves"]["n_sold_out"] is None
    assert p["moves"]["n_new"] != 0
