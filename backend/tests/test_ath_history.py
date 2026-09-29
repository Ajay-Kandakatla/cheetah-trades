"""🏔️ ATH tab — the long-history store `chart_maps/ath_history.py` and the
`prices._fetch_massive` extension (spec §3.1-§3.2, tests 1-7, 2026-09-29).

Ajay 2026-09-29: "Can you give me a new tab - for all the stocks that are
reaching all time highs? call it ATH. Once some of them are going below their
ATH or 52 Week Highs.."

Positive AND negative cases. Stubs only — the conftest refuses Mongo; the
HTTP layer is a stub; the memory store is the default here.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps import ath_history as AH
from sepa import prices, symbols

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 9, 29, 17, 0, tzinfo=ET)


def _months(start: str, end: str, *, high=10.0, skip=(), sets=None) -> pd.DataFrame:
    """Monthly bars stamped like Massive's (month start, 05:00 naive UTC)."""
    idx = [p.to_timestamp() + pd.Timedelta(hours=5)
           for p in pd.period_range(start, end, freq="M") if str(p) not in set(skip)]
    df = pd.DataFrame({"open": high - 1, "high": high, "low": high - 2, "close": high - 1,
                       "volume": 1e6}, index=pd.DatetimeIndex(idx))
    for month, vals in (sets or {}).items():
        ts = pd.Period(month, freq="M").to_timestamp() + pd.Timedelta(hours=5)
        for k, v in vals.items():
            df.loc[ts, k] = v
    return df


@pytest.fixture(autouse=True)
def _memory_store(monkeypatch):
    monkeypatch.setenv(AH.STORE_ENV, "memory")
    AH._MEM.clear()
    yield
    AH._MEM.clear()


# --------------------------------------------------------------------------
# 1 — the ONE Massive fetcher: default byte-identical, monthly on request
# --------------------------------------------------------------------------
class _Resp:
    status_code = 200
    text = ""

    def json(self):
        return {"results": [{"t": 1_709_269_200_000, "o": 1, "h": 2, "l": 0.5, "c": 1.5,
                             "v": 100}]}


@pytest.fixture
def http(monkeypatch):
    import requests
    calls = []

    def _get(url, params=None, timeout=None):
        calls.append({"url": url, "params": dict(params or {}), "timeout": timeout})
        return _Resp()

    monkeypatch.setattr(requests, "get", _get)
    monkeypatch.setattr(prices, "stocks_key", lambda: "TESTKEY")
    return calls


def test_01_default_fetch_url_is_byte_identical(http):
    to = pd.Timestamp.utcnow().normalize()
    frm = to - pd.Timedelta(days=prices.PERIOD_DAYS["2y"])
    df = prices._fetch_massive("AAPL", "2y")
    assert df is not None and len(df) == 1
    assert http[0]["url"] == (f"https://api.massive.com/v2/aggs/ticker/AAPL"
                              f"/range/1/day/{frm.date()}/{to.date()}")
    assert http[0]["params"] == {"adjusted": "true", "sort": "asc", "limit": 50000,
                                 "apiKey": "TESTKEY"}
    assert http[0]["timeout"] == 15


def test_01b_monthly_from_the_epoch(http):
    prices._fetch_massive("BRK-B", "max", timespan="month", start="1970-01-01",
                          end="2026-08-31")
    assert http[0]["url"] == ("https://api.massive.com/v2/aggs/ticker/BRK.B"
                              "/range/1/month/1970-01-01/2026-08-31")


def test_01c_NEGATIVE_start_none_still_counts_back_the_period(http):
    to = pd.Timestamp.utcnow().normalize()
    frm = to - pd.Timedelta(days=prices.PERIOD_DAYS["5y"])
    prices._fetch_massive("MSFT", "5y", timespan="month")
    assert http[0]["url"].endswith(f"/range/1/month/{frm.date()}/{to.date()}")
    prices._fetch_massive("MSFT", "1y", end="2026-01-02")
    frm1 = to - pd.Timedelta(days=prices.PERIOD_DAYS["1y"])
    assert http[1]["url"].endswith(f"/range/1/day/{frm1.date()}/2026-01-02")


def test_01d_fetch_monthly_asks_the_resolved_symbol_from_the_epoch_to_month_end():
    seen = []

    def fn(sym, period, **kw):
        seen.append((sym, period, kw))
        return _months("2020-01", "2020-03")

    df = AH.fetch_monthly("SATS", end=date(2026, 8, 31), fetch_fn=fn)
    assert len(df) == 3
    assert seen == [(symbols.resolve("SATS"), "max",
                     {"timespan": "month", "start": AH.FROM_DATE, "end": "2026-08-31"})]
    # NEGATIVE: an empty frame and a None are both None here
    assert AH.fetch_monthly("X", end=date(2026, 8, 31), fetch_fn=lambda *a, **k: None) is None
    assert AH.fetch_monthly("X", end=date(2026, 8, 31),
                            fetch_fn=lambda *a, **k: _months("2020-01", "2020-01").iloc[0:0]) is None


def test_01e_month_end_before_is_the_last_complete_month():
    assert AH.month_end_before(NOW) == date(2026, 8, 31)
    assert AH.month_end_before(datetime(2026, 3, 1, 0, 30, tzinfo=ET)) == date(2026, 2, 28)
    assert AH.month_end_before(datetime(2026, 1, 15, 12, 0, tzinfo=ET)) == date(2025, 12, 31)


# --------------------------------------------------------------------------
# 2 — last_hole_cut
# --------------------------------------------------------------------------
def test_02_djt_shape_cuts_the_earlier_listing():
    old = _months("2003-09", "2004-08", high=300.0)
    new = _months("2024-03", "2026-08", high=80.0)
    df = pd.concat([old, new])
    cut, cut_from = AH.last_hole_cut(df)
    assert cut_from == "2024-03-01"
    assert float(cut["high"].max()) == 80.0 and len(cut) == len(new)
    doc = AH.summarize("DJT", df, now=NOW)
    assert doc["status"] == "ok" and doc["first_bar"] == "2024-03-01" and doc["hi"] == 80.0
    assert doc["cut_from"] == "2024-03-01" and doc["n_months"] == len(new)


def test_02b_NEGATIVE_continuous_series_is_never_cut():
    df = _months("2010-01", "2026-08", sets={"2012-05": {"high": 99.0}})
    cut, cut_from = AH.last_hole_cut(df)
    assert cut_from is None and len(cut) == len(df)
    doc = AH.summarize("ABC", df, now=NOW)
    assert doc["hi"] == 99.0 and doc["hi_month"] == "2012-05" and doc["cut_from"] is None
    assert doc["check_month"] == "2026-08" and doc["check_high"] == 10.0
    assert doc["first_bar"] == "2010-01-01"


def test_02c_a_dropped_zero_volume_month_IS_a_hole():
    df = _months("2018-01", "2026-08", skip=("2020-04",), sets={"2019-02": {"high": 50.0}})
    cut, cut_from = AH.last_hole_cut(df)
    assert cut_from == "2020-05-01" and float(cut["high"].max()) == 10.0


def test_02d_NEGATIVE_two_holes_cut_after_the_LAST():
    df = _months("2005-01", "2026-08", skip=("2008-03", "2015-07", "2015-08"),
                 sets={"2010-01": {"high": 70.0}, "2006-01": {"high": 90.0}})
    cut, cut_from = AH.last_hole_cut(df)
    assert cut_from == "2015-09-01"
    assert float(cut["high"].max()) == 10.0


def test_02e_short_frames_pass_through():
    one = _months("2026-08", "2026-08")
    assert AH.last_hole_cut(one) == (one, None)
    assert AH.last_hole_cut(None) == (None, None)


# --------------------------------------------------------------------------
# 3 — summarize: the curated foreign-head cut runs first
# --------------------------------------------------------------------------
def test_03_first_session_spike_never_counts(monkeypatch):
    monkeypatch.setitem(symbols.FIRST_SESSION, "ZZW", ("2020-06-15", "test"))
    df = _months("2019-01", "2026-08", sets={"2020-05": {"high": 500.0},
                                             "2020-06": {"high": 400.0},
                                             "2021-03": {"high": 42.0}})
    doc = AH.summarize("ZZW", df, now=NOW)
    assert doc["hi"] == 42.0 and doc["hi_month"] == "2021-03"
    # the first-session MONTH mixes two securities: its bar is dropped too
    assert doc["first_bar"] == "2020-07-01"
    # NEGATIVE: without the curated entry the spike is the high
    monkeypatch.delitem(symbols.FIRST_SESSION, "ZZW")
    assert AH.summarize("ZZW", df, now=NOW)["hi"] == 500.0


def test_03b_rename_head_behind_a_monthly_gap_is_cut(monkeypatch):
    monkeypatch.setitem(symbols.RENAMES, "OLDQ", ("NEWQ", "2022-03-01", "test"))
    monkeypatch.setitem(symbols._FORMER, "NEWQ", ["OLDQ"])
    df = _months("2018-01", "2026-08", sets={"2020-01": {"high": 300.0}})
    doc = AH.summarize("NEWQ", df, now=NOW)
    assert doc["first_bar"] == "2022-03-01" and doc["hi"] == 10.0


def test_03c_everything_cut_is_an_empty_doc(monkeypatch):
    monkeypatch.setitem(symbols.FIRST_SESSION, "ZZE", ("2026-09-01", "test"))
    doc = AH.summarize("ZZE", _months("2020-01", "2026-08"), now=NOW)
    assert doc["status"] == "empty" and "hi" not in doc
    assert doc["_id"] == "ZZE" and doc["source"] == AH.SOURCE
    assert doc["fetched_at"] == NOW.timestamp()


# --------------------------------------------------------------------------
# 4 — curation_key
# --------------------------------------------------------------------------
def test_04_curation_edit_invalidates_the_doc(monkeypatch):
    doc = AH.summarize("CUR", _months("2020-01", "2026-08"), now=NOW)
    assert AH.needs_fetch(doc, "CUR", now=NOW) is None
    monkeypatch.setitem(symbols.FIRST_SESSION, "CUR", ("2021-01-04", "test"))
    assert AH.needs_fetch(doc, "CUR", now=NOW) == "curation"
    monkeypatch.delitem(symbols.FIRST_SESSION, "CUR")
    assert AH.needs_fetch(doc, "CUR", now=NOW) is None
    monkeypatch.setitem(symbols.RENAMES, "OLDC", ("CUR", "2023-01-03", "test"))
    monkeypatch.setitem(symbols._FORMER, "CUR", ["OLDC"])
    assert AH.needs_fetch(doc, "CUR", now=NOW) == "curation"


# --------------------------------------------------------------------------
# 5 — fill
# --------------------------------------------------------------------------
def test_05_fill_ok_empty_error_exception_progress(monkeypatch):
    monkeypatch.setattr(AH, "FILL_REBUILD_EVERY", 2)
    progress = []
    good = _months("2015-01", "2026-08", sets={"2016-01": {"high": 33.0}})

    def fn(sym, period, **kw):
        if sym == "BOOM":
            raise RuntimeError("apiKey=SECRET123 exploded")
        if sym == "ERR":
            return None
        if sym == "EMP":
            return good.iloc[0:0]
        return good

    counts = AH.fill(["OK1", "EMP", "ERR", "BOOM", "OK2", "ok1"], now=NOW, pause=0,
                     fetch_fn=fn, on_progress=progress.append)
    assert {k: counts[k] for k in ("asked", "ok", "empty", "error")} == \
        {"asked": 5, "ok": 2, "empty": 1, "error": 2}
    assert counts["error_symbols"] == ["ERR", "BOOM"]
    assert progress == [2, 4, 5]
    store = AH.read_many(["OK1", "OK2", "EMP", "ERR", "BOOM"])
    assert set(store) == {"OK1", "OK2", "EMP"}
    assert store["OK1"]["hi"] == 33.0 and store["OK1"]["status"] == "ok"
    assert store["EMP"]["status"] == "empty"
    # NEGATIVE: a transport None writes NOTHING (retried next pass)
    assert "ERR" not in AH._MEM and "BOOM" not in AH._MEM


def test_05b_fill_never_raises_on_a_bad_progress_hook():
    def bad(n):
        raise ValueError("hook")
    counts = AH.fill(["A1"], now=NOW, pause=0, fetch_fn=lambda *a, **k: _months("2020-01", "2020-02"),
                     on_progress=bad)
    assert counts["ok"] == 1


def test_05c_fill_paces_between_calls_only(monkeypatch):
    sleeps = []
    monkeypatch.setattr(AH.time, "sleep", sleeps.append)
    AH.fill(["A1", "A2", "A3"], now=NOW, fetch_fn=lambda *a, **k: None)
    assert sleeps == [AH.FILL_PAUSE_SEC, AH.FILL_PAUSE_SEC]


# --------------------------------------------------------------------------
# 6 — the store: memory never touches Mongo; Mongo writes only ath_history
# --------------------------------------------------------------------------
def test_06_memory_store_never_touches_mongo(monkeypatch):
    def refuse():
        raise AssertionError("Mongo reached in memory mode")
    monkeypatch.setattr(prices, "_get_mongo", refuse)
    AH.upsert({"_id": "MEM", "status": "ok"})
    assert AH.read_many(["mem", "none"]) == {"MEM": {"_id": "MEM", "status": "ok"}}
    # the held copy is not the caller's dict
    got = AH.read_many(["MEM"])
    got["MEM"]["status"] = "x"
    assert AH._MEM["MEM"]["status"] == "ok"


def test_06b_mongo_mode_one_find_one_replace(monkeypatch):
    monkeypatch.setenv(AH.STORE_ENV, "mongo")
    calls = []

    class Coll:
        def find(self, q):
            calls.append(("find", q))
            return [{"_id": "AAA", "status": "ok"}]

        def replace_one(self, flt, doc, upsert=False):
            calls.append(("replace_one", flt, doc["_id"], upsert))

    monkeypatch.setattr(AH, "_coll", lambda: Coll())
    assert AH.read_many(["bbb", "aaa", "AAA"]) == {"AAA": {"_id": "AAA", "status": "ok"}}
    AH.upsert({"_id": "AAA", "status": "ok"})
    assert calls == [("find", {"_id": {"$in": ["AAA", "BBB"]}}),
                     ("replace_one", {"_id": "AAA"}, "AAA", True)]
    # NEGATIVE: Mongo down -> {} (callers read frame-only), upsert a no-op
    monkeypatch.setattr(AH, "_coll", lambda: None)
    assert AH.read_many(["AAA"]) == {}
    AH.upsert({"_id": "AAA"})


def test_06c_NEGATIVE_module_never_reaches_the_shared_cache_or_loader():
    src = (BACKEND / "chart_maps" / "ath_history.py").read_text(encoding="utf-8")
    for bad in ("price_cache", "_mongo_put", "load_prices("):
        assert bad not in src, bad
    assert "_cut_foreign_head(" in src and "_fetch_massive" in src
    assert 'COLL = "ath_history"' in src


# --------------------------------------------------------------------------
# 7 — needs_fetch
# --------------------------------------------------------------------------
def test_07_needs_fetch_reasons():
    assert AH.needs_fetch(None, "AAA", now=NOW) == "missing"
    empty = {"_id": "AAA", "status": "empty", "curation": AH.curation_key("AAA"),
             "fetched_at": NOW.timestamp() - AH.MISS_TTL_SEC + 60}
    assert AH.needs_fetch(empty, "AAA", now=NOW) is None
    older = {**empty, "fetched_at": NOW.timestamp() - AH.MISS_TTL_SEC - 1}
    assert AH.needs_fetch(older, "AAA", now=NOW) == "retry_empty"
    assert AH.needs_fetch(older, "AAA", now=NOW.timestamp()) == "retry_empty"
    ok = {**empty, "status": "ok", "fetched_at": 0.0}
    assert AH.needs_fetch(ok, "AAA", now=NOW) is None           # an ok doc never ages out here


def test_07c_a_check_month_older_than_the_frame_is_refetched():
    """critic 2026-09-29: the split check can never fail on an empty overlap,
    so a good doc whose check month predates the rolling frame's first bar is
    refetched."""
    ok = {"_id": "AAA", "status": "ok", "curation": AH.curation_key("AAA"),
          "check_month": "2024-08", "check_high": 10.0, "fetched_at": 0.0}
    assert AH.needs_fetch(ok, "AAA", now=NOW, frame_first="2024-09-30") == "check_stale"
    # NEGATIVE: the check month IS the frame's first month -> the overlap exists
    assert AH.needs_fetch(ok, "AAA", now=NOW, frame_first="2024-08-15") is None
    # NEGATIVE: a newer check month, and no frame given (the CLI path)
    assert AH.needs_fetch({**ok, "check_month": "2026-08"}, "AAA", now=NOW,
                          frame_first="2024-09-30") is None
    assert AH.needs_fetch(ok, "AAA", now=NOW) is None
    # a good doc with no check month at all can never be checked -> refetch
    assert AH.needs_fetch({**ok, "check_month": None}, "AAA", now=NOW,
                          frame_first="2024-09-30") == "check_stale"
    # NEGATIVE: a doc fetched inside REFETCH_MIN_AGE_SEC is not refetched (no loop),
    # though it still has no overlap (the tab reads it frame-only)
    young = {**ok, "fetched_at": NOW.timestamp() - 60}
    assert AH.needs_fetch(young, "AAA", now=NOW, frame_first="2024-09-30") is None
    assert AH.no_overlap(young, "2024-09-30") and not AH.no_overlap(young, "2024-08-02")
    assert not AH.no_overlap(young, None) and not AH.no_overlap(None, "2024-09-30")
    # NEGATIVE: an empty doc is never 'check_stale' (it has no check month by design)
    empty = {**ok, "status": "empty", "check_month": None, "fetched_at": NOW.timestamp()}
    assert AH.needs_fetch(empty, "AAA", now=NOW, frame_first="2024-09-30") is None


def test_07d_hole_wording_never_claims_a_blanket_never_count():
    src = (BACKEND / "chart_maps" / "ath_history.py").read_text(encoding="utf-8")
    assert "never count" not in src


def test_07b_constants_are_the_house_constants():
    from sepa import ipo_age
    assert AH.MISS_TTL_SEC is ipo_age._MISS_TTL_SEC
    assert AH.REFETCH_MIN_AGE_SEC is prices.CACHE_TTL_SEC
    src = (BACKEND / "chart_maps" / "ath_history.py").read_text(encoding="utf-8")
    assert not re.search(r"bounc|fake", src, re.I)
