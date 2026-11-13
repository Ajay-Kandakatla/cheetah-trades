"""`sepa.bonde.headline_sales_read` + `sepa.rev_ttm` quarter date — 2026-11-12.

Ajay 2026-11-12: "We got wrong numbers for Joby in sales in the undervalye can
you verfy". The 💎 board printed JOBY at +257,493% sales growth off a $15,000
year-ago quarter. ONE helper decides whether a stored headline YoY sales % may
be printed or ranked as growth; `rev_ttm` now stores the quarter its TTM runs
to (`ttm_q_end`) so the board can say when P/S and growth are on different
quarters. Spec: scratchpad uvfix/spec.md §3.1, §3.2, §4.1.
"""
from __future__ import annotations

import calendar
import inspect
import json
import time

import pytest

from sepa import bonde as SB
from sepa import qoq as Q
from sepa import rev_ttm as R

FLOOR = SB.MIN_MATERIAL_BASE_REV

JOBY_SERIES = [38_639_000, 24_246_000, 30_836_000, 22_574_000, 15_000,
               None, 55_000, 28_000]


def _quarter_ends(n, y=2026, m=6):
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}")
        m -= 3
        if m <= 0:
            m += 12
            y -= 1
    return out


def _doc(series=None, periods=None, ends=None, growth=257493.3,
         source="hybrid", drop=()):
    f = {
        "sales": {"growth_yoy_pct": growth},
        "rev_q_series": list(JOBY_SERIES) if series is None else series,
        "q_period_series": list(range(8105, 8093, -1)) if periods is None else periods,
        Q.END_SERIES_KEY: _quarter_ends(12) if ends is None else ends,
        "_source": source,
    }
    for k in drop:
        f.pop(k, None)
    return f


def _with_base(base, latest=20_000_000.0):
    s = list(JOBY_SERIES)
    s[0] = latest
    s[4] = base
    return s


def _dumps_ok(r):
    json.dumps(r, allow_nan=False)
    return r


# ──────────────────────────────────────────── the JOBY shape
def test_joby_shape_is_not_comparable_and_says_why():
    r = _dumps_ok(SB.headline_sales_read(_doc()))
    assert r["comparable"] is False
    assert r["reason"] == "base_too_small" == SB.READ_BASE_TOO_SMALL
    assert r["pct"] is None
    assert r["raw_pct"] == 257493.3
    assert r["base_rev"] == 15000.0
    assert r["latest_rev"] == 38_639_000.0
    assert r["base_state"] == "too_small"
    assert r["period"] == "FY2026 Q2"
    assert r["period_end"] == "2026-06-30"
    assert r["latest_idx"] == 8105


def test_return_keys_are_exactly_the_spec():
    r = SB.headline_sales_read(_doc())
    assert set(r) == {"pct", "raw_pct", "comparable", "reason", "base_state",
                      "base_rev", "latest_rev", "period", "period_end",
                      "latest_idx"}


def test_normal_base_is_comparable_and_the_number_is_untouched():
    r = _dumps_ok(SB.headline_sales_read(
        _doc(series=_with_base(12_209_793.0, 40_000_000.0), growth=227.6)))
    assert r["comparable"] is True
    assert r["reason"] is None
    assert r["pct"] == r["raw_pct"] == 227.6
    assert r["base_state"] == "ok"


# ──────────────────────────────────────────── the boundary reads the constant
def test_base_exactly_at_the_owner_floor_is_ok():
    r = SB.headline_sales_read(_doc(series=_with_base(FLOOR), growth=50.0))
    assert r["comparable"] is True and r["base_state"] == "ok"


def test_base_one_dollar_under_the_owner_floor_is_too_small():
    r = SB.headline_sales_read(_doc(series=_with_base(FLOOR - 1), growth=50.0))
    assert r["comparable"] is False
    assert r["reason"] == SB.READ_BASE_TOO_SMALL
    assert r["pct"] is None and r["raw_pct"] == 50.0


# ──────────────────────────────────────────── NEGATIVE: base at or below zero
@pytest.mark.parametrize("base", [-471_000_000.0, 0.0])
def test_non_positive_base_is_refused(base):
    r = _dumps_ok(SB.headline_sales_read(_doc(series=_with_base(base), growth=135.7)))
    assert r["comparable"] is False
    assert r["reason"] == SB.READ_BASE_NON_POSITIVE
    assert r["pct"] is None


# ──────────────────────────────────────────── NEGATIVE: base missing
def test_series_on_file_with_an_empty_year_ago_slot_is_base_missing():
    r = _dumps_ok(SB.headline_sales_read(_doc(series=_with_base(None), growth=80.0)))
    assert r["reason"] == SB.READ_BASE_MISSING
    assert r["base_state"] == "unknown"
    assert r["comparable"] is False and r["pct"] is None


def test_series_shorter_than_five_is_base_missing():
    r = _dumps_ok(SB.headline_sales_read(
        _doc(series=[30_000_000, 20_000_000, 10_000_000], growth=80.0)))
    assert r["reason"] == SB.READ_BASE_MISSING
    assert r["comparable"] is False


def test_a_headline_hole_reads_base_missing_not_pair_mismatch():
    periods = [8105, 8104, 8103, 8102, None, 8100, 8099, 8098]
    ends = _quarter_ends(8)
    ends[4] = None
    r = _dumps_ok(SB.headline_sales_read(
        _doc(series=_with_base(None), periods=periods, ends=ends, growth=80.0)))
    assert Q.period_ok(periods, (Q.HEADLINE_PAIR,), ends=ends) is False
    assert r["reason"] == SB.READ_BASE_MISSING
    assert r["reason"] != SB.READ_PAIR_MISMATCH


def test_no_rev_q_series_at_all_is_accepted_by_default():
    r = _dumps_ok(SB.headline_sales_read(
        _doc(growth=80.0, drop=("rev_q_series",))))
    assert r["comparable"] is True
    assert r["base_state"] == "unknown"
    assert r["pct"] == 80.0


def test_unverifiable_legacy_row_is_accepted_by_default():
    f = {"sales": {"growth_yoy_pct": 40.0},
         "rev_q_series": [20_000_000, 1, 1, 1, 10_000_000]}
    r = _dumps_ok(SB.headline_sales_read(f))
    assert r["comparable"] is True
    assert r["period"] is None and r["period_end"] is None
    assert r["latest_idx"] is None


# ──────────────────────────────────────────── NEGATIVE: the pair test (C2)
LABEL_SKIP = [8105, 8104, 8103, 8102, 8100, 8099, 8098, 8097]


def test_headline_label_mismatch_is_pair_mismatch_with_a_material_base():
    r = _dumps_ok(SB.headline_sales_read(
        _doc(series=_with_base(12_000_000.0), periods=LABEL_SKIP,
             ends=_quarter_ends(8), growth=60.0)))
    assert r["reason"] == SB.READ_PAIR_MISMATCH
    assert r["comparable"] is False and r["pct"] is None


def test_pair_mismatch_takes_precedence_over_a_tiny_base():
    r = SB.headline_sales_read(
        _doc(series=_with_base(15_000.0), periods=LABEL_SKIP,
             ends=_quarter_ends(8)))
    assert r["base_state"] == "too_small"
    assert r["reason"] == SB.READ_PAIR_MISMATCH


def test_crdo_shape_labels_four_apart_but_ends_455_days_apart():
    ends = _quarter_ends(8)
    ends[0] = "2026-08-01"
    ends[4] = "2025-05-03"
    periods = list(range(8105, 8097, -1))
    assert Q.period_ok(periods, (Q.HEADLINE_PAIR,)) is True
    r = _dumps_ok(SB.headline_sales_read(
        _doc(series=_with_base(12_000_000.0), periods=periods, ends=ends,
             growth=60.0)))
    assert r["reason"] == SB.READ_PAIR_MISMATCH
    assert r["period_end"] == "2026-08-01"


def test_a_prior_only_mismatch_stays_comparable():
    periods = [8105, 8104, 8103, 8102, 8101, 8099, 8098, 8097]
    f = _doc(series=_with_base(12_000_000.0), periods=periods,
             ends=_quarter_ends(8), growth=60.0)
    assert SB._pair_mismatch({"fundamentals": f}) is True
    r = _dumps_ok(SB.headline_sales_read(f))
    assert r["comparable"] is True
    assert r["pct"] == 60.0


# ──────────────────────────────────────────── NEGATIVE: no figure
@pytest.mark.parametrize("g", [None, float("nan"), float("inf"), float("-inf"), "x"])
def test_no_finite_growth_is_no_figure(g):
    r = _dumps_ok(SB.headline_sales_read(_doc(growth=g)))
    assert r["reason"] == SB.READ_NO_FIGURE
    assert r["raw_pct"] is None and r["pct"] is None
    assert r["comparable"] is False


@pytest.mark.parametrize("f", [None, [], [1, 2], 5, "JOBY", {"sales": 3}, {}])
def test_non_dict_or_empty_input_never_raises(f):
    r = _dumps_ok(SB.headline_sales_read(f))
    assert r["reason"] == SB.READ_NO_FIGURE
    assert r["comparable"] is False


def test_a_non_sequence_series_never_raises():
    r = _dumps_ok(SB.headline_sales_read(
        {"sales": {"growth_yoy_pct": 10.0}, "rev_q_series": 5}))
    assert r["base_state"] == "unknown"


def test_nan_in_the_series_never_reaches_json():
    s = _with_base(float("nan"), float("inf"))
    r = _dumps_ok(SB.headline_sales_read(_doc(series=s, growth=40.0)))
    assert r["base_rev"] is None and r["latest_rev"] is None
    assert r["reason"] == SB.READ_BASE_MISSING


def test_yfinance_source_reads_the_calendar_label():
    r = SB.headline_sales_read(_doc(source="yfinance"))
    assert r["period"] == "Q2 2026"


# ──────────────────────────────────────────── pins
def test_read_reasons_order_is_pinned():
    assert SB.READ_REASONS == ("no_figure", "pair_mismatch", "base_non_positive",
                               "base_too_small", "base_missing")
    assert SB.READ_REASONS == (SB.READ_NO_FIGURE, SB.READ_PAIR_MISMATCH,
                               SB.READ_BASE_NON_POSITIVE, SB.READ_BASE_TOO_SMALL,
                               SB.READ_BASE_MISSING)


def test_source_guard_reuses_the_engines_and_never_the_prior_pair_test():
    src = inspect.getsource(SB.headline_sales_read)
    for needle in ("_rev_base(", "period_ok(", "headline_hole(",
                   "HEADLINE_PAIR", "END_SERIES_KEY"):
        assert needle in src, needle
    assert "_pair_mismatch(" not in src
    for lit in ("1_000_000", "1000000", "1e6", "1E6"):
        assert lit not in src, lit


def test_sales_py_is_not_touched_by_the_helper():
    src = inspect.getsource(SB.headline_sales_read)
    assert "sepa.sales" not in src and "from sepa import sales" not in src


# ──────────────────────────────────────────── rev_ttm: fakes
class _FakeColl:
    def __init__(self, docs=None, raise_on_find=False):
        self.docs = {d["symbol"]: dict(d) for d in (docs or [])}
        self.raise_on_find = raise_on_find
        self.updates = []

    def find(self, query, proj=None):
        if self.raise_on_find:
            raise RuntimeError("mongo down")
        syms = set(query["symbol"]["$in"])
        gte = (query.get("cached_at") or {}).get("$gte")
        out = []
        for s, d in self.docs.items():
            if s not in syms:
                continue
            if gte is not None and (d.get("cached_at") or 0) < gte:
                continue
            if proj:
                keep = {k for k, v in proj.items() if v and k != "_id"}
                d = {k: v for k, v in d.items() if k in keep}
            out.append(dict(d))
        return out

    def update_one(self, filt, upd, upsert=False):
        self.updates.append((filt, upd))
        s = filt["symbol"]
        self.docs.setdefault(s, {"symbol": s}).update(upd["$set"])


class _FakeTicker:
    def __init__(self, info):
        self.info = info


def _yf(monkeypatch, info=None, exc=None):
    import sepa.symbols as SYM

    def fake(sym):
        if exc:
            raise exc
        return _FakeTicker(info)
    monkeypatch.setattr(SYM, "yf_ticker", fake)


# ──────────────────────────────────────────── rev_ttm: _fetch_meta
def test_fetch_meta_reads_revenue_and_quarter_end(monkeypatch):
    _yf(monkeypatch, {"totalRevenue": 148810000, "mostRecentQuarter": 1790726400})
    assert R._fetch_meta("JOBY") == (148810000.0, "2026-09-30")
    assert R.TTM_Q_END_KEY == "ttm_q_end"


@pytest.mark.parametrize("mrq", [None, 0, -5, "x", True, float("nan")])
def test_fetch_meta_bad_quarter_is_none(monkeypatch, mrq):
    _yf(monkeypatch, {"totalRevenue": 148810000, "mostRecentQuarter": mrq})
    assert R._fetch_meta("JOBY") == (148810000.0, None)


@pytest.mark.parametrize("rev", [0, None, float("nan"), float("inf"), True, -3, "12"])
def test_fetch_meta_bad_revenue_is_none(monkeypatch, rev):
    _yf(monkeypatch, {"totalRevenue": rev, "mostRecentQuarter": 1790726400})
    assert R._fetch_meta("JOBY") == (None, "2026-09-30")


def test_fetch_meta_exception_is_none_none(monkeypatch):
    _yf(monkeypatch, exc=RuntimeError("yahoo 429"))
    assert R._fetch_meta("JOBY") == (None, None)


def test_fetch_meta_info_none_is_none_none(monkeypatch):
    _yf(monkeypatch, None)
    assert R._fetch_meta("JOBY") == (None, None)


def test_fetch_one_still_returns_a_float_or_none(monkeypatch):
    _yf(monkeypatch, {"totalRevenue": 148810000, "mostRecentQuarter": 1790726400})
    v = R._fetch_one("JOBY")
    assert isinstance(v, float) and v == 148810000.0
    _yf(monkeypatch, {"totalRevenue": None})
    assert R._fetch_one("JOBY") is None


# ──────────────────────────────────────────── rev_ttm: bulk
def test_bulk_fill_writes_both_keys_and_keeps_the_return_shape(monkeypatch):
    coll = _FakeColl()
    monkeypatch.setattr(R, "_coll", lambda: coll)
    monkeypatch.setattr(R, "_fetch_meta",
                        lambda s: {"JOBY": (148810000.0, "2026-09-30"),
                                   "NOQ": (5_000_000.0, None),
                                   "NONE": (None, "2026-09-30")}[s])
    out = R.bulk(["joby", "NOQ", "NONE"], fill_missing=True)
    assert out == {"JOBY": 148810000.0, "NOQ": 5_000_000.0}
    assert all(isinstance(v, float) for v in out.values())
    assert coll.docs["JOBY"]["rev_ttm"] == 148810000.0
    assert coll.docs["JOBY"][R.TTM_Q_END_KEY] == "2026-09-30"
    assert coll.docs["NOQ"][R.TTM_Q_END_KEY] is None
    assert "NONE" not in coll.docs


def test_bulk_does_not_refetch_a_fresh_doc_lacking_the_quarter(monkeypatch):
    now = time.time()
    coll = _FakeColl([{"symbol": "OLD", "rev_ttm": 9e6, "cached_at": now - 60}])
    calls = []
    monkeypatch.setattr(R, "_coll", lambda: coll)
    monkeypatch.setattr(R, "_fetch_meta",
                        lambda s: calls.append(s) or (1.0, "2026-09-30"))
    out = R.bulk(["OLD"], fill_missing=True)
    assert out == {"OLD": 9e6}
    assert calls == []
    assert coll.updates == []
    assert R.TTM_Q_END_KEY not in coll.docs["OLD"]


def test_bulk_still_refills_a_stale_doc(monkeypatch):
    now = time.time()
    coll = _FakeColl([{"symbol": "ST", "rev_ttm": 9e6, "cached_at": now - R.TTL_SEC - 5}])
    monkeypatch.setattr(R, "_coll", lambda: coll)
    monkeypatch.setattr(R, "_fetch_meta", lambda s: (7e6, "2026-09-30"))
    assert R.bulk(["ST"]) == {"ST": 7e6}
    assert coll.docs["ST"][R.TTM_Q_END_KEY] == "2026-09-30"


def test_bulk_without_fill_never_fetches(monkeypatch):
    coll = _FakeColl()
    monkeypatch.setattr(R, "_coll", lambda: coll)
    monkeypatch.setattr(R, "_fetch_meta", lambda s: pytest.fail("fetched"))
    assert R.bulk(["X"], fill_missing=False) == {}


# ──────────────────────────────────────────── rev_ttm: quarter_ends
def test_quarter_ends_reads_fresh_dated_docs_only(monkeypatch):
    now = time.time()
    coll = _FakeColl([
        {"symbol": "JOBY", "rev_ttm": 148810000.0, R.TTM_Q_END_KEY: "2026-09-30",
         "cached_at": now - 60},
        {"symbol": "LEGACY", "rev_ttm": 5e6, "cached_at": now - 60},
        {"symbol": "STALE", "rev_ttm": 5e6, R.TTM_Q_END_KEY: "2026-06-30",
         "cached_at": now - R.TTL_SEC - 5},
        {"symbol": "NOREV", "rev_ttm": None, R.TTM_Q_END_KEY: "2026-06-30",
         "cached_at": now - 60},
        {"symbol": "NULLQ", "rev_ttm": 5e6, R.TTM_Q_END_KEY: None,
         "cached_at": now - 60},
        {"symbol": "NUMQ", "rev_ttm": 5e6, R.TTM_Q_END_KEY: 20260630,
         "cached_at": now - 60},
    ])
    monkeypatch.setattr(R, "_coll", lambda: coll)
    out = R.quarter_ends(["joby", "legacy", "stale", "norev", "nullq", "numq", "absent"])
    assert out == {"JOBY": "2026-09-30"}
    assert coll.updates == []


def test_quarter_ends_no_collection_is_empty(monkeypatch):
    monkeypatch.setattr(R, "_coll", lambda: None)
    assert R.quarter_ends(["JOBY"]) == {}


def test_quarter_ends_find_raising_is_empty(monkeypatch):
    monkeypatch.setattr(R, "_coll", lambda: _FakeColl(raise_on_find=True))
    assert R.quarter_ends(["JOBY"]) == {}


def test_quarter_ends_coll_raising_is_empty(monkeypatch):
    def boom():
        raise RuntimeError("no db")
    monkeypatch.setattr(R, "_coll", boom)
    assert R.quarter_ends(["JOBY"]) == {}


def test_quarter_ends_empty_input_is_empty(monkeypatch):
    monkeypatch.setattr(R, "_coll", lambda: pytest.fail("read"))
    assert R.quarter_ends([]) == {} and R.quarter_ends(None) == {}


def test_quarter_ends_never_fills(monkeypatch):
    monkeypatch.setattr(R, "_coll", lambda: _FakeColl())
    monkeypatch.setattr(R, "_fetch_meta", lambda s: pytest.fail("fetched"))
    assert R.quarter_ends(["JOBY"]) == {}


# ──────────────────────────────────────────── rev_ttm: warm
def test_warm_writes_the_quarter_and_still_skips_fresh(monkeypatch):
    now = time.time()
    coll = _FakeColl([{"symbol": "FRESH", "rev_ttm": 9e6, "cached_at": now - 60}])
    calls = []
    monkeypatch.setattr(R, "_coll", lambda: coll)
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    monkeypatch.setattr(R, "_fetch_meta",
                        lambda s: calls.append(s) or (148810000.0, "2026-09-30"))
    res = R.warm(["fresh", "joby"])
    assert res == {"ok": True, "already_fresh": 1, "filled": 1}
    assert calls == ["JOBY"]
    assert coll.docs["JOBY"][R.TTM_Q_END_KEY] == "2026-09-30"
    assert R.TTM_Q_END_KEY not in coll.docs["FRESH"]


def test_warm_no_revenue_writes_nothing(monkeypatch):
    coll = _FakeColl()
    monkeypatch.setattr(R, "_coll", lambda: coll)
    monkeypatch.setattr(R.time, "sleep", lambda s: None)
    monkeypatch.setattr(R, "_fetch_meta", lambda s: (None, "2026-09-30"))
    assert R.warm(["X"]) == {"ok": True, "already_fresh": 0, "filled": 0}
    assert coll.docs == {}
