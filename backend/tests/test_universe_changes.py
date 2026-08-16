"""Index membership change tracking + the 13F bulk warm.

Ajay 2026-08-16: "we have too keep updating. Latest tickers as they change like
getting added to SP 500 or Russel 3000 and Nasdaq."

The negatives are the point. A change log that invents adds and drops is worse
than none: it would report a Wikipedia parse failure as "480 companies left the
S&P 500". So the tests lean on the guards — insane churn, a curated/stale
fallback, a first-ever snapshot, and a missing database.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sepa import universe_changes as uc  # noqa: E402


# ---------------------------------------------------------------------------
# pure diff
# ---------------------------------------------------------------------------
def test_diff_reports_adds_and_drops():
    d = uc.diff_lists(["A", "B", "C"], ["B", "C", "D"])
    assert d == {"added": ["D"], "removed": ["A"], "n_before": 3, "n_after": 3}


def test_diff_is_order_insensitive_and_sorted():
    d = uc.diff_lists(["C", "A", "B"], ["B", "A", "C"])
    assert d["added"] == [] and d["removed"] == []
    d2 = uc.diff_lists(["A"], ["Z", "B"])
    assert d2["added"] == ["B", "Z"]           # sorted, not insertion order


def test_diff_handles_empty_and_none():
    assert uc.diff_lists([], ["A"]) == {"added": ["A"], "removed": [],
                                        "n_before": 0, "n_after": 1}
    assert uc.diff_lists(None, None) == {"added": [], "removed": [],
                                         "n_before": 0, "n_after": 0}


def test_diff_dedupes_a_repeated_symbol():
    d = uc.diff_lists(["A", "A", "B"], ["A", "B", "B"])
    assert d["n_before"] == 2 and d["n_after"] == 2
    assert d["added"] == [] and d["removed"] == []


# ---------------------------------------------------------------------------
# the churn gate — the guard against a broken parse
# ---------------------------------------------------------------------------
def test_normal_index_turnover_is_sane():
    """A handful of names in and out of a 500-name index is routine."""
    d = {"added": ["N1", "N2"], "removed": ["O1", "O2"], "n_before": 500, "n_after": 500}
    assert uc.is_sane_churn(d) is True


def test_a_collapsed_parse_is_NOT_sane():
    """Wikipedia reshapes its table, the parse returns 12 names, and a naive
    differ reports 488 removals. That must never reach the change log."""
    d = {"added": [], "removed": [f"S{i}" for i in range(488)],
         "n_before": 500, "n_after": 12}
    assert uc.is_sane_churn(d) is False


def test_russell_annual_reconstitution_stays_under_the_gate():
    """Russell rebuilds every June — the one legitimately large event. ~8% of a
    3,000-name index must still count as sane."""
    d = {"added": [f"N{i}" for i in range(120)],
         "removed": [f"O{i}" for i in range(130)],
         "n_before": 3000, "n_after": 2990}
    assert uc.is_sane_churn(d) is True


def test_first_snapshot_is_always_sane():
    """Nothing to compare against — every name looks 'added'."""
    d = {"added": [f"S{i}" for i in range(500)], "removed": [],
         "n_before": 0, "n_after": 500}
    assert uc.is_sane_churn(d) is True


# ---------------------------------------------------------------------------
# refresh_one — fetch, guard, diff, persist
# ---------------------------------------------------------------------------
class _DB:
    """Records inserts so the test can assert on what was persisted."""

    def __init__(self, latest=None):
        self._latest = latest
        self.universe_snapshots = _Coll(latest)
        self.universe_changes = _Coll(None)


class _Coll:
    def __init__(self, latest):
        self._latest = latest
        self.inserted = []

    def find_one(self, *a, **kw):
        return self._latest

    def insert_one(self, doc):
        self.inserted.append(doc)

    def delete_many(self, *a, **kw):
        pass


@pytest.fixture
def stub(monkeypatch):
    """Patch the fetchers, provenance and cache-expiry so nothing hits network."""
    state = {"symbols": ["A", "B", "C"], "source": "wikipedia"}

    monkeypatch.setattr(uc, "_fetchers", lambda: {"sp500": lambda: state["symbols"]})
    monkeypatch.setattr(uc, "_expire_cache", lambda name: None)

    from sepa import universe as U
    monkeypatch.setattr(U, "last_source",
                        lambda name: ({"source": state["source"], "n": 0,
                                       "age_days": 0.0}
                                      if state["source"] else None))
    return state


def test_refresh_records_the_first_snapshot_without_claiming_changes(stub):
    db = _DB(latest=None)
    r = uc.refresh_one("sp500", db=db)
    assert r["ok"] is True and r["first_snapshot"] is True
    assert r["added"] == ["A", "B", "C"]
    assert db.universe_snapshots.inserted[0]["n"] == 3
    # a first snapshot is NOT a change event
    assert db.universe_changes.inserted == []


def test_refresh_detects_a_real_add_and_drop(stub):
    db = _DB(latest={"symbols": ["A", "B", "X"], "taken_at": "t0"})
    stub["symbols"] = ["A", "B", "C"]
    r = uc.refresh_one("sp500", db=db)
    assert r["added"] == ["C"] and r["removed"] == ["X"]
    chg = db.universe_changes.inserted[0]
    assert chg["index"] == "sp500" and chg["added"] == ["C"] and chg["removed"] == ["X"]


def test_no_change_writes_no_change_event(stub):
    db = _DB(latest={"symbols": ["A", "B", "C"], "taken_at": "t0"})
    r = uc.refresh_one("sp500", db=db)
    assert r["added"] == [] and r["removed"] == []
    assert db.universe_changes.inserted == []
    # but the snapshot IS refreshed, so the next diff has a current baseline
    assert len(db.universe_snapshots.inserted) == 1


def test_an_insane_diff_is_neither_snapshotted_nor_logged(stub):
    """REGRESSION GUARD: storing a collapsed parse as the baseline would turn
    one bad fetch into two bogus diffs — the drop, then the re-add."""
    db = _DB(latest={"symbols": [f"S{i}" for i in range(500)], "taken_at": "t0"})
    stub["symbols"] = ["S1", "S2"]
    r = uc.refresh_one("sp500", db=db)
    assert r["sane"] is False
    assert db.universe_snapshots.inserted == []
    assert db.universe_changes.inserted == []


def test_a_curated_fallback_is_refused(stub):
    """sp500 falls back to the curated ~158 names when both sources fail.
    Diffing that against the real index would report ~400 fake removals."""
    stub["source"] = "curated"
    r = uc.refresh_one("sp500", db=_DB())
    assert r["ok"] is False and "curated" in r["reason"]


def test_a_stale_cache_resolve_is_refused(stub):
    stub["source"] = "stale-cache"
    r = uc.refresh_one("sp500", db=_DB())
    assert r["ok"] is False


def test_missing_provenance_is_flagged_not_assumed(stub):
    """The Russell lists read local iShares files and record no provenance, so
    we cannot verify freshness. Report that rather than implying we checked."""
    stub["source"] = None
    r = uc.refresh_one("sp500", db=_DB())
    assert r["ok"] is True
    assert r["provenance_known"] is False


def test_a_failing_fetch_does_not_raise(monkeypatch):
    monkeypatch.setattr(uc, "_expire_cache", lambda name: None)
    monkeypatch.setattr(uc, "_fetchers", lambda: {
        "sp500": lambda: (_ for _ in ()).throw(RuntimeError("wikipedia down"))})
    r = uc.refresh_one("sp500", db=_DB())
    assert r["ok"] is False and "fetch failed" in r["reason"]


def test_unknown_index_is_rejected():
    assert uc.refresh_one("ftse100")["ok"] is False


def test_refresh_works_without_a_database(stub):
    """Mongo offline must degrade to a read-only diff, not a crash."""
    r = uc.refresh_one("sp500", db=None)
    assert r["ok"] is True and "added" in r


def test_nasdaq_is_tracked():
    """Ajay named Nasdaq explicitly and it was in no fetcher before 2026-08-16."""
    assert "nasdaq100" in uc.TRACKED
    assert {"sp500", "russell1000", "russell3000"} <= set(uc.TRACKED)


def test_every_tracked_index_has_a_fetcher():
    fetchers = uc._fetchers()
    for name in uc.TRACKED:
        assert name in fetchers, f"{name} is tracked but has no fetcher"


# ---------------------------------------------------------------------------
# the nasdaq-100 fetcher + its count gate
# ---------------------------------------------------------------------------
def test_nasdaq100_count_gate_allows_dual_class_shares():
    """The index holds 100 COMPANIES but slightly more SYMBOLS — GOOG/GOOGL
    and FOX/FOXA both sit in it. Verified live 2026-08-16: 102 tickers."""
    from sepa import universe as U
    lo, hi = U._EXPECTED_COUNTS["nasdaq100"]
    assert lo <= 102 <= hi
    assert lo < 100 and hi > 100


def test_nasdaq100_never_falls_back_to_curated():
    """A curated large-cap growth list masquerading as the Nasdaq-100 would
    corrupt every membership diff built on it."""
    import inspect
    from sepa import universe as U
    src = inspect.getsource(U.fetch_nasdaq100)
    assert 'on_exhausted="empty"' in src
    assert "curated" not in src.split('"""')[2]


# ---------------------------------------------------------------------------
# the 13F bulk warm
# ---------------------------------------------------------------------------
def test_warm_universe_excludes_etfs(monkeypatch):
    """A fund files no 13F about itself: the provider 404s and the empty result
    is cached under a 1-hour TTL, so every sweep would re-ask for nothing."""
    from sepa import warm_whales as ww
    from sepa import universe as U
    monkeypatch.setattr(U, "fetch_broad", lambda: ["NVDA", "SPY", "AAPL", "QQQ"])
    monkeypatch.setattr(U, "fetch_etf_universe", lambda: ["SPY", "QQQ", "IWM"])
    assert ww.universe() == ["NVDA", "AAPL"]


def test_warm_universe_survives_a_failing_etf_list(monkeypatch):
    from sepa import warm_whales as ww
    from sepa import universe as U
    monkeypatch.setattr(U, "fetch_broad", lambda: ["NVDA", "AAPL"])
    monkeypatch.setattr(U, "fetch_etf_universe",
                        lambda: (_ for _ in ()).throw(RuntimeError("down")))
    assert ww.universe() == ["NVDA", "AAPL"]


def test_warm_concurrency_stays_polite():
    """The constraint is the provider's tolerance, not our CPU. A wide pool
    risks a block that takes the whole panel down."""
    from sepa import warm_whales as ww
    assert 1 <= ww.WORKERS <= 6


def test_weekly_warm_and_change_crons_are_scheduled():
    """The rule is only real if it is scheduled."""
    crontab = (Path(__file__).resolve().parents[1] / "crontab").read_text()
    live = [ln for ln in crontab.splitlines() if ln and not ln.startswith("#")]

    warm = [ln for ln in live if "sepa.warm_whales " in ln or ln.endswith("sepa.warm_whales")]
    assert len(warm) == 1, "expected exactly one scheduled 13F warm"
    assert warm[0].split()[4] == "0", "13F warm should run on Sunday"

    chg = [ln for ln in live if "sepa.universe_changes" in ln]
    assert len(chg) == 1, "expected exactly one scheduled membership refresh"
    assert chg[0].split()[4] == "0", "membership refresh should run on Sunday"
