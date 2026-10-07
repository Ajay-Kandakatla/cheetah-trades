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


# --- 4. Boards that say "activist" count only the 13D family ----------------
# Critic probe 2026-10-06: of 20 form13 filings on 20 liquid names, 18 were
# passive SCHEDULE 13G / 13G/A. Before the rename fix they never reached the
# boards; they must not now score as "activist" (SMCI: 6 x 13G = 240 points).

from sepa import confluence as cf                       # noqa: E402
from sepa import money_movement as mm                   # noqa: E402


@pytest.mark.parametrize("form", ["SC 13D", "SC 13D/A", "SCHEDULE 13D", "SCHEDULE 13D/A"])
def test_13d_family_is_activist(form):
    assert whales_13d.is_activist_13d(form) is True


@pytest.mark.parametrize("form", ["SC 13G", "SC 13G/A", "SCHEDULE 13G", "SCHEDULE 13G/A",
                                  "SCHEDULE 13E3", "4", "144", "", None])
def test_NEGATIVE_13g_and_others_are_not_activist(form):
    assert whales_13d.is_activist_13d(form) is False


def test_count_activist_13d_skips_13g_and_formless_rows():
    fl = [{"bucket": "form13", "form": "SCHEDULE 13G"},
          {"bucket": "form13", "form": "SCHEDULE 13G/A"},
          {"bucket": "form13", "form": "SCHEDULE 13D/A"},
          {"bucket": "form13"},                         # no form -> cannot tell, not counted
          {"bucket": "form4", "form": "4"}]
    assert whales_13d.count_activist_13d(fl) == 1
    assert whales_13d.count_activist_13d(None) == 0


class _ProjColl:
    """Fake Mongo collection that honours the projection the caller asks for,
    so a board that forgets to project ``payload.filings.form`` sees no forms."""
    def __init__(self, docs):
        self._docs, self.projections = docs, []

    def find(self, q=None, proj=None):
        self.projections.append(proj or {})
        keep = set((proj or {}).keys())
        for d in self._docs:
            fl = []
            for f in d["payload"]["filings"]:
                fl.append({k: v for k, v in f.items() if f"payload.filings.{k}" in keep})
            yield {"ticker": d["ticker"], "payload": {"filings": fl}}


def _d13(ticker, *forms):
    return {"ticker": ticker,
            "payload": {"filings": [{"bucket": whales_13d._form_bucket(f), "form": f} for f in forms]}}


def _mm_setup(monkeypatch, d13_docs, allr):
    coll = _ProjColl(d13_docs)

    class _DB:
        whales_cache = _ProjColl([])
        whales13d_cache = coll
    monkeypatch.setattr(mm.history, "_get_db", lambda: _DB())
    monkeypatch.setattr(mm.sepa_scanner, "load_latest", lambda: {"generated_at": 1, "all_results": allr})
    monkeypatch.setattr(mm.pullback_ma, "load_latest_pullback", lambda: {"rows": []})
    mm._CACHE.update(at=0.0, data=None)
    return coll


def test_money_movement_13d_scores_and_13g_does_not(monkeypatch):
    allr = [{"symbol": "ACT", "name": "Act"}, {"symbol": "SMCI", "name": "Smci"},
            {"symbol": "INS", "name": "Ins", "insider": {"cluster_buy": True}}]
    coll = _mm_setup(monkeypatch, [
        _d13("ACT", "SCHEDULE 13D/A"),
        _d13("SMCI", *(["SCHEDULE 13G"] * 3 + ["SCHEDULE 13G/A"] * 3)),
    ], allr)
    rows = {r["ticker"]: r for r in mm.compute()["sec_moves"]}
    assert rows["ACT"]["n_form13"] == 1 and "activist_13d" in rows["ACT"]["signals"]
    assert rows["ACT"]["score"] == 40
    # NEGATIVE: six passive 13Gs are not an activist stake and earn no row/score.
    assert "SMCI" not in rows
    # NEGATIVE: an insider cluster is not outranked by passive filings.
    assert rows["INS"]["signals"] == ["insider_cluster"]
    assert "payload.filings.form" in coll.projections[0]


def test_NEGATIVE_money_movement_13g_only_ticker_with_cluster_gets_no_activist(monkeypatch):
    allr = [{"symbol": "SMCI", "name": "Smci", "insider": {"cluster_buy": True}}]
    _mm_setup(monkeypatch, [_d13("SMCI", "SCHEDULE 13G", "SC 13G/A")], allr)
    r = mm.compute()["sec_moves"][0]
    assert r["ticker"] == "SMCI" and r["n_form13"] == 0
    assert "activist_13d" not in r["signals"] and r["score"] == 30


def _cf_setup(monkeypatch, d13_docs, allr):
    coll = _ProjColl(d13_docs)
    monkeypatch.setattr(cf.sepa_scanner, "load_latest", lambda: {"generated_at": 1, "all_results": allr})
    monkeypatch.setattr(cf.leaderboard, "leaderboard", lambda n=300: {"leaders": []})
    monkeypatch.setattr(cf.pullback_ma, "load_latest_pullback", lambda: {"rows": []})
    monkeypatch.setattr(cf.market_gauge, "get_gauge",
                        lambda force=False: {"state": "constructive", "score": 75})

    class _DB:
        whales_cache = _ProjColl([])
        whales13d_cache = coll
    monkeypatch.setattr(cf.history, "_get_db", lambda: _DB())
    cf._CACHE.update(at=0.0, data=None)
    return coll


def test_confluence_13d_counts_13g_does_not(monkeypatch):
    def rec(s):
        return {"symbol": s, "name": s, "is_candidate": True, "score": 80,
                "is_buyable": True, "rating": "STRONG_BUY"}
    coll = _cf_setup(monkeypatch, [_d13("ACT", "SC 13D"),
                                   _d13("PAS", "SCHEDULE 13G", "SCHEDULE 13G/A")],
                     [rec("ACT"), rec("PAS")])
    rows = {r["symbol"]: r for r in cf.compute(top_n=10)["rows"]}
    assert "13D activist" in rows["ACT"]["matches"]
    # NEGATIVE: passive 13G never earns the +2 "13D activist" credit.
    assert "13D activist" not in rows["PAS"]["matches"]
    assert rows["ACT"]["confluence_score"] - rows["PAS"]["confluence_score"] == cf.WEIGHTS["activist_13d"]
    assert "payload.filings.form" in coll.projections[0]


# --- 5. No-primary-doc fallback link points at the filing itself ------------

def test_accession_link_without_primary_doc_is_the_filing_index():
    u = whales_13d._accession_to_url("0001692819", "0001193125-26-123456", None)
    assert u == "https://www.sec.gov/Archives/edgar/data/1692819/000119312526123456/"
    # NEGATIVE: never the type=SC+13 browse filter (it cannot list SCHEDULE 13… filings).
    assert "browse-edgar" not in u and "type=SC" not in u


def test_NEGATIVE_accession_link_with_primary_doc_unchanged():
    u = whales_13d._accession_to_url("0001692819", "0001193125-26-123456", "x.htm")
    assert u == "https://www.sec.gov/Archives/edgar/data/1692819/000119312526123456/x.htm"
