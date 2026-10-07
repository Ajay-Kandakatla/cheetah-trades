"""`qoq.backfill` can no longer create a vintage mix (2026-10-07 b).

Ajay 2026-10-07: "yes please also no #s for SNDK can you do a deep analysis of
data and make sure you do a sanity chcek fo missing data pieces over all."

MEASURED by code read (SPEC §1.1, defects a-d): the series-only `$set` left the
stored % describing a different vintage from the series (SNDK: stored sales %
None, its own series +371.59%); an all-None list passed the truthy test; the
walk sliced the same unsorted head of `find()` every run; and the projection
omitted `q_period_series`, so `_series_missing` was True for EVERY doc.

The fake collection here APPLIES the projection, so defect (d) cannot hide.
"""
from __future__ import annotations

import copy
import inspect
import math

import pytest

from sepa import canslim, qoq, research


# --------------------------------------------------------------------------
# a fake Mongo collection that honours the projection
# --------------------------------------------------------------------------
def _project(doc: dict, proj: dict) -> dict:
    out: dict = {}
    for path, on in (proj or {}).items():
        if not on:
            continue
        parts = path.split(".")
        src, dst = doc, out
        for i, p in enumerate(parts):
            if not isinstance(src, dict) or p not in src:
                break
            if i == len(parts) - 1:
                dst[p] = copy.deepcopy(src[p])
            else:
                dst = dst.setdefault(p, {})
                src = src[p]
    return out


class FakeColl:
    def __init__(self, docs):
        self.docs = {d["symbol"]: copy.deepcopy(d) for d in docs}
        self.finds: list = []
        self.updates: list = []

    def find(self, q=None, proj=None):
        self.finds.append(proj)
        want = None
        if q and "symbol" in q:
            want = set(q["symbol"].get("$in") or [])
        # natural order = insertion order, NOT sorted (the defect (c) shape)
        return [_project(d, proj) for s, d in self.docs.items() if want is None or s in want]

    def update_one(self, flt, upd):
        self.updates.append((flt, upd))


def _doc(sym, *, periods=(8105, 8104, 8103, 8102, 8101, 8100), rev=None, eps=None, ni=None,
         rev_pct=None, eps_pct=None, src="hybrid"):
    return {"symbol": sym, "cached_at": 1790700000.0,
            "fundamentals": {"_source": src, "q_period_series": list(periods) if periods else periods,
                             "rev_q_series": rev, "eps_q_series": eps, "ni_q_series": ni,
                             "rev_growth_q_pct": rev_pct, "q_eps_growth_pct": eps_pct,
                             "sales": {"growth_yoy_pct": rev_pct}}}


def _m(*, periods=(8105, 8104, 8103, 8102, 8101, 8100), rev=None, eps=None, ni=None):
    return {"q_period_series": list(periods), "rev_q_series": rev, "eps_q_series": eps,
            "ni_q_series": ni}


@pytest.fixture
def wire(monkeypatch):
    def _wire(docs, fetched: dict):
        coll = FakeColl(docs)
        monkeypatch.setattr(research, "_get_cache", lambda: coll)
        monkeypatch.setattr(canslim, "_fetch_massive_financials",
                            lambda sym: copy.deepcopy(fetched.get(sym)))
        return coll
    return _wire


SNDK_REV = [8.965e9, 5.95e9, 3.025e9, 2.308e9, 1.901e9, 1.695e9]
SNDK_EPS = [44.83, 23.03, 5.15, 0.75, None, -13.33]
SNDK_PER = (8107, 8106, 8105, 8104, 8103, 8102)


# --------------------------------------------------------------------------
# 1 — defect (d): the projection carries the period keys
# --------------------------------------------------------------------------
def test_NEG_a_doc_with_period_keys_is_not_refetched_by_the_missing_only_run(wire):
    keyed = _doc("KEYED", rev=[1.1e9, 1, 1, 1, 1.0e9, 1], eps=[1.1, 1, 1, 1, 1.0, 1],
                 rev_pct=10.0, eps_pct=10.0)
    bare = _doc("BARE", periods=None, rev=[1.1e9, 1, 1, 1, 1.0e9, 1])
    coll = wire([keyed, bare], {})
    out = qoq.backfill(only_missing=True, now=0.0)
    assert "fundamentals.q_period_series" in coll.finds[0]
    assert coll.finds[0] == qoq.BACKFILL_PROJ
    projected = _project(keyed, qoq.BACKFILL_PROJ)
    assert qoq._series_missing(projected) is False
    assert out["attempted"] == 1                      # BARE only — KEYED is not re-fetched
    # NEGATIVE: the OLD projection hides the keys, so every doc looked missing
    old = {"symbol": 1, "fundamentals.rev_q_series": 1, "fundamentals.eps_q_series": 1,
           "fundamentals.ni_q_series": 1}
    assert qoq._series_missing(_project(keyed, old)) is True


# --------------------------------------------------------------------------
# 2 — the SNDK-shaped doc: stored % None, new series computes one -> skipped
# --------------------------------------------------------------------------
def test_NEG_sndk_shaped_doc_is_skipped_never_written(wire):
    d = _doc("SNDK", periods=SNDK_PER, rev=SNDK_REV, eps=SNDK_EPS)
    coll = wire([d], {"SNDK": _m(periods=SNDK_PER, rev=SNDK_REV, eps=SNDK_EPS,
                                 ni=[6.9e9, None, None, None, -23e6, None])})
    assert qoq.yoy_pct(SNDK_REV) == 371.59
    out = qoq.backfill(["SNDK"], only_missing=False, now=0.0)
    assert coll.updates == []
    assert out["skipped"] == {"rev_pct_would_disagree": 1}
    assert out["filled"] == 0 and out["failed"] == 0


# --------------------------------------------------------------------------
# 3 — an agreeing doc IS written, series keys only
# --------------------------------------------------------------------------
def test_agreeing_doc_is_written_with_series_keys_only(wire):
    rev, eps = [1.1e9, 1, 1, 1, 1.0e9, 1], [1.1, 1, 1, 1, 1.0, 1]
    d = _doc("OK", rev=rev, eps=eps, rev_pct=10.0, eps_pct=10.0)
    coll = wire([d], {"OK": _m(rev=rev, eps=eps, ni=[5.0, 1, 1, 1, 4.0, 1])})
    out = qoq.backfill(["OK"], only_missing=False, now=0.0)
    assert out["filled"] == 1 and out["skipped"] == {}
    (flt, upd), = coll.updates
    keys = set(upd["$set"])
    # 2026-10-07 c: the period end dates ride WITH the keys (predicted pin)
    assert keys <= ({f"fundamentals.{k}" for k in qoq.SERIES_KEYS}
                    | {f"fundamentals.{qoq.END_SERIES_KEY}"})
    assert not any("cached_at" in k or "pct" in k or k.endswith(".sales") for k in keys)


# --------------------------------------------------------------------------
# 4 — yfinance docs and a new latest quarter are never spliced
# --------------------------------------------------------------------------
def test_NEG_yfinance_doc_and_new_latest_quarter_are_skipped(wire):
    rev, eps = [1.1e9, 1, 1, 1, 1.0e9, 1], [1.1, 1, 1, 1, 1.0, 1]
    yf = _doc("YF", rev=rev, eps=eps, rev_pct=10.0, eps_pct=10.0, src="yfinance")
    newq = _doc("NEWQ", rev=None, eps=None)                       # both % None
    coll = wire([yf, newq], {
        "YF": _m(rev=rev, eps=eps),
        "NEWQ": _m(periods=(8106, 8105, 8104, 8103, 8102, 8101), rev=None, eps=None,
                   ni=[1.0, 1, 1, 1, 1, 1])})
    out = qoq.backfill(["YF", "NEWQ"], only_missing=False, now=0.0)
    assert coll.updates == []
    assert out["skipped"] == {"yfinance_doc": 1, "new_latest_quarter": 1}
    assert qoq.backfill_skip_reason({"_source": "yfinance"}, {}) == "yfinance_doc"


def test_skip_reason_order_and_eps_disagreement():
    f = {"_source": "hybrid", "q_period_series": [8105], "rev_growth_q_pct": 10.0,
         "q_eps_growth_pct": 50.0}
    m = {"q_period_series": [8105], "rev_q_series": [1.1e9, 1, 1, 1, 1.0e9],
         "eps_q_series": [1.1, 1, 1, 1, 1.0]}
    assert qoq.backfill_skip_reason(f, m) == "eps_pct_would_disagree"
    assert qoq.backfill_skip_reason({**f, "q_eps_growth_pct": 10.0}, m) is None
    # within the 2-dp representation tolerance agrees; past it does not
    assert qoq.pct_agrees(10.0, 10.01) is True and qoq.pct_agrees(10.0, 10.02) is False
    assert qoq.pct_agrees(None, 10.0) is None and qoq.pct_agrees(10.0, float("nan")) is None


# --------------------------------------------------------------------------
# 5 — all-None lists are never written; all keys None -> failed
# --------------------------------------------------------------------------
def test_NEG_all_none_series_key_is_not_written(wire):
    rev = [1.1e9, 1, 1, 1, 1.0e9, 1]
    d = _doc("PART", rev=rev, rev_pct=10.0)
    coll = wire([d], {"PART": _m(rev=rev, eps=[None] * 6, ni=[None] * 6)})
    out = qoq.backfill(["PART"], only_missing=False, now=0.0)
    assert out["filled"] == 1
    keys = set(coll.updates[0][1]["$set"])
    assert "fundamentals.eps_q_series" not in keys and "fundamentals.ni_q_series" not in keys
    assert "fundamentals.rev_q_series" in keys
    assert qoq._has_values([None, None]) is False and qoq._has_values([]) is False
    assert qoq._has_values([None, 1.0]) is True and qoq._has_values(None) is False


def test_NEG_every_key_all_none_is_failed_no_write(wire):
    d = _doc("NIL")
    coll = wire([d], {"NIL": {"q_period_series": [None] * 6, "rev_q_series": [None] * 6,
                              "eps_q_series": [None] * 6, "ni_q_series": [None] * 6}})
    out = qoq.backfill(["NIL"], only_missing=False, now=0.0)
    assert coll.updates == [] and out["failed"] == 1 and out["filled"] == 0


# --------------------------------------------------------------------------
# 6 — the rotation
# --------------------------------------------------------------------------
def test_rotate_covers_everything_in_ceil_n_over_limit_periods():
    todo = ["E", "C", "A", "D", "B"]
    P = qoq.ROTATE_DAY_SEC
    wins = [qoq._rotate(todo, 2, period_sec=P, now=k * P + 5.0) for k in range(3)]
    assert wins[0] == ["A", "B"] and wins[1] == ["C", "D"] and wins[2] == ["E", "A"]
    assert len({tuple(w) for w in wins}) == 3
    assert set().union(*map(set, wins)) == set(todo)
    assert len(wins) == math.ceil(len(todo) / 2)
    assert qoq._rotate(todo, 0, period_sec=P, now=123.0) == sorted(todo)
    assert qoq._rotate(todo, 9, period_sec=P, now=123.0) == sorted(todo)


def test_NEG_the_same_now_is_the_same_window_and_the_walk_moves():
    todo = [f"S{i:02d}" for i in range(10)]
    W = qoq.ROTATE_WEEK_SEC
    a = qoq._rotate(todo, 3, period_sec=W, now=W * 7 + 1.0)
    assert a == qoq._rotate(list(reversed(todo)), 3, period_sec=W, now=W * 7 + 99.0)
    assert a != qoq._rotate(todo, 3, period_sec=W, now=W * 8 + 1.0)


def test_backfill_rotates_with_the_cadence_of_its_cron_line(wire, monkeypatch):
    docs = [_doc(s, periods=None) for s in ("D", "B", "A", "C")]
    seen = []
    coll = wire(docs, {})
    monkeypatch.setattr(canslim, "_fetch_massive_financials",
                        lambda sym: seen.append(sym) or None)
    qoq.backfill(limit=2, only_missing=True, now=qoq.ROTATE_DAY_SEC * 1 + 1.0)
    assert sorted(seen) == ["C", "D"]
    assert coll.updates == []


# --------------------------------------------------------------------------
# 7 — source guards
# --------------------------------------------------------------------------
def test_NEG_backfill_source_never_writes_cached_at_or_a_pct():
    src = inspect.getsource(qoq.backfill)
    assert 'sets = {f"fundamentals.{k}": m[k] for k in SERIES_KEYS if _has_values(m.get(k))}' in src
    assert "backfill_skip_reason(" in src and "BACKFILL_PROJ" in src and "_rotate(" in src
    assert '"cached_at"' not in src and "_pct" not in src.split("sets = ")[1].split("\n")[0]
