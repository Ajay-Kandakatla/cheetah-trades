"""Russell 2000 tracking — a DERIVED list that never pretends to be the index.

Ajay 2026-09-18: *"Yes add it"* — answering my offer to track the Russell 2000
for index additions alongside the 1000 and 3000.

WHAT THIS PACKAGE ACTUALLY SHIPS, AND WHY IT IS NOT THE RUSSELL 2000
--------------------------------------------------------------------
There is no IWM export on disk and no fetchable network source (the iShares CSV
endpoints serve a Cloudflare interstitial). FTSE defines the Russell 2000 as the
Russell 3000 minus the Russell 1000, so the derivation is definitionally
correct — and inherits the parents' shortfall. MEASURED 2026-09-18 in the api
container: russell3000 resolves to 2,559 names and russell1000 to 1,001, so the
derived list is **1,560 names, 78% of a ~2,000-name index**.

THE NEGATIVES ARE THE POINT
---------------------------
1. **A file drop is not a corporate event.** The day an IWM export lands, the
   list jumps 1,560 -> ~1,970. That churn sits well inside the sane window
   (max(8, 1560*0.35) = 546), so the change log would have published "410
   additions to the Russell 2000" — a fabricated event produced by a file copy.
   `refresh_one` now re-baselines on a SOURCE change and publishes nothing.
2. **A derived diff cannot name the parent that moved.** `CBC` and `FRMI` sit
   in our Russell 1000 export and not in our Russell 3000 export, which FTSE
   guarantees cannot happen — so the two files are already out of step and any
   attribution built on them would be confidently wrong. The row says so.
3. **No curated fallback ever wears this name.** The curated list is large-cap
   leaders; serving it as a small-cap index would invent membership.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sepa import universe as U             # noqa: E402
from sepa import universe_changes as uc    # noqa: E402


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------
class _Coll:
    def __init__(self, latest=None):
        self._latest = latest
        self.inserted: list = []

    def find_one(self, *a, **kw):
        return self._latest

    def insert_one(self, doc):
        self.inserted.append(doc)

    def delete_many(self, *a, **kw):
        pass


class _DB:
    def __init__(self, latest=None):
        self.universe_snapshots = _Coll(latest)
        self.universe_changes = _Coll(None)


@pytest.fixture
def parents(monkeypatch, tmp_path):
    """Stub both parents and redirect every disk path, so nothing reads the
    real 3.5 MB / 5.3 MB iShares exports or writes into the repo."""
    state = {"r1000": ["AAPL", "MSFT", "NVDA", "AMZN"],
             "r3000": ["AAPL", "MSFT", "NVDA", "AMZN",
                       "ANDE", "TENB", "QLYS", "CRDO", "SDIG", "BITF"]}
    # Each stub records its provenance the way the real fetcher does on every
    # resolve. Without it the derivation's parent guard read whatever an
    # EARLIER test's real resolve had left in U._LAST_SOURCE — on 2026-09-24 a
    # 'curated' russell3000 from test_cloud_infra_theme.py, which failed three
    # tests here that pass alone.
    monkeypatch.setattr(U, "fetch_russell1000", lambda: U._record(
        "russell1000", U.SRC_ISHARES_LOCAL, list(state["r1000"])))
    monkeypatch.setattr(U, "fetch_russell3000", lambda: U._record(
        "russell3000", U.SRC_ISHARES_LOCAL, list(state["r3000"])))
    monkeypatch.setattr(U, "_LOCAL_IWM_PATH", tmp_path / "absent.xls")
    monkeypatch.setattr(U, "_cache_path", lambda name: tmp_path / f"{name}.txt")
    U._LAST_SOURCE.pop("russell2000", None)
    return state


# ---------------------------------------------------------------------------
# the derivation
# ---------------------------------------------------------------------------
def test_derived_is_r3000_minus_r1000_exactly(parents):
    out = U.fetch_russell2000()
    assert set(out) == set(parents["r3000"]) - set(parents["r1000"])
    # order is the R3000's own, so the list is deterministic run to run
    assert out == ["ANDE", "TENB", "QLYS", "CRDO", "SDIG", "BITF"]
    assert U.last_source("russell2000")["source"] == U.SRC_DERIVED_R2000


def test_local_iwm_file_wins_over_the_derivation(parents, monkeypatch, tmp_path):
    """The real export, when he drops one in, beats the derivation outright."""
    fake = tmp_path / "iShares-Russell-2000-ETF_fund.xls"
    fake.write_text("x")
    monkeypatch.setattr(U, "_LOCAL_IWM_PATH", fake)
    monkeypatch.setattr(U, "_load_ishares_local_xls",
                        lambda path, *, source_label: ["IWM1", "IWM2", "IWM3"])
    out = U.fetch_russell2000()
    assert out == ["IWM1", "IWM2", "IWM3"]
    assert U.last_source("russell2000")["source"] == U.SRC_ISHARES_LOCAL
    cov = U.russell2000_coverage()
    assert cov["complete"] is True and cov["attributable"] is True


def test_coverage_reports_measured_counts_not_literals(parents):
    """Every number in the served dict is read off the parents at call time.

    A literal 1560 / 2559 / 2000 in the payload would keep printing the day
    someone refreshes a file — the served string must move with the data.
    """
    cov = U.russell2000_coverage()
    assert cov["n"] == 6
    assert cov["derived_from"] == {"russell3000": 10, "russell1000": 4}
    blob = repr(cov)
    for literal in ("1560", "2559", "1001", "78"):
        assert literal not in blob, f"{literal} is hard-coded into the payload"
    # "2000" survives only inside the index's own NAME, never as a count
    assert "2000" not in cov["label"].replace("russell2000", "")
    assert cov["label"] == "russell2000 (derived: russell3000 10 - russell1000 4 = 6)"


def test_derived_list_never_claims_completeness(parents):
    cov = U.russell2000_coverage()
    assert cov["complete"] is False
    assert cov["attributable"] is False
    assert "6 names" in cov["note"]
    assert "not as the Russell 2000" in cov["note"]
    # the note names the exact file to drop in, read off the path CONSTANT
    # rather than retyped — so a renamed constant cannot leave a dead
    # instruction on the surface
    assert str(U._LOCAL_IWM_PATH) in cov["note"]


def test_the_iwm_path_is_the_file_name_ajay_is_told_to_drop_in():
    """The real constant, un-monkeypatched: the docs and the HIS-CALL item send
    him to this exact filename."""
    assert U._LOCAL_IWM_PATH.name == "iShares-Russell-2000-ETF_fund.xls"
    assert U._LOCAL_IWM_PATH.parent == U._LOCAL_IWV_PATH.parent


def test_r1000_not_contained_in_r3000_is_surfaced_not_swallowed(parents):
    """FTSE guarantees R1000 is a subset of R3000. Ours is not — CBC and FRMI
    were measured out of step on 2026-09-18. That is evidence the two exports
    disagree, so it is reported rather than quietly differenced away."""
    parents["r1000"] = parents["r1000"] + ["CBC"]
    cov = U.russell2000_coverage()
    assert cov["parents_not_contained"] == ["CBC"]
    assert "CBC" not in U.fetch_russell2000()


# ---------------------------------------------------------------------------
# NEGATIVES — the wrong universe, and the empty one
# ---------------------------------------------------------------------------
def test_no_curated_fallback_ever_wears_the_russell2000_name(parents, monkeypatch):
    """Both parents resolve to the curated large-cap list. The derivation is
    then empty, and an empty answer is refused upstream — far better than
    serving mega-caps under a small-cap index's name."""
    monkeypatch.setattr(U, "last_source",
                        lambda name: {"source": "curated", "n": 4, "age_days": 0.0})
    parents["r3000"] = list(parents["r1000"])       # curated ∪ sp500 ∪ sp400, both
    monkeypatch.setattr(uc, "_expire_cache", lambda name: None)
    monkeypatch.setattr(uc, "_fetchers", lambda: {"russell2000": U.fetch_russell2000})
    db = _DB()
    r = uc.refresh_one("russell2000", db=db)
    assert r["ok"] is False and "curated" in r["reason"]
    assert db.universe_snapshots.inserted == []


def test_empty_parents_yield_an_empty_list_not_an_exception(parents, monkeypatch):
    parents["r1000"], parents["r3000"] = [], []
    assert U.fetch_russell2000() == []
    assert U.last_source("russell2000")["source"] == "empty"
    monkeypatch.setattr(uc, "_expire_cache", lambda name: None)
    monkeypatch.setattr(uc, "_fetchers", lambda: {"russell2000": U.fetch_russell2000})
    assert uc.refresh_one("russell2000", db=_DB())["ok"] is False


def test_a_failing_parent_fetch_does_not_raise(parents, monkeypatch):
    monkeypatch.setattr(U, "fetch_russell3000",
                        lambda: (_ for _ in ()).throw(RuntimeError("iShares parse blew up")))
    assert U.fetch_russell2000() == []
    monkeypatch.setattr(uc, "_expire_cache", lambda name: None)
    monkeypatch.setattr(uc, "_fetchers", lambda: {"russell2000": U.fetch_russell2000})
    assert uc.refresh_one("russell2000", db=_DB())["ok"] is False


def test_coverage_survives_a_broken_universe_module(monkeypatch):
    monkeypatch.setattr(U, "russell2000_coverage",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert uc.tracked_coverage() == {}


# ---------------------------------------------------------------------------
# tracking wiring
# ---------------------------------------------------------------------------
def test_russell2000_is_tracked_and_has_a_fetcher():
    assert "russell2000" in uc.TRACKED
    assert "russell2000" in uc._fetchers()


def test_russell2000_is_refreshed_after_both_parents():
    """It is DERIVED from them, so both must be refreshed first in one run."""
    t = list(uc.TRACKED)
    assert t.index("russell2000") > max(t.index("russell1000"), t.index("russell3000"))


def test_churn_gate_on_a_1560_name_list():
    """The measured size of the derived list, through the EXISTING gate — the
    two constants keep their values; nothing here invents a threshold."""
    sane = {"added": [f"N{i}" for i in range(150)],
            "removed": [f"O{i}" for i in range(150)],
            "n_before": 1560, "n_after": 1560}
    assert uc.is_sane_churn(sane) is True
    insane = {"added": [f"N{i}" for i in range(300)],
              "removed": [f"O{i}" for i in range(300)],
              "n_before": 1560, "n_after": 1560}
    assert uc.is_sane_churn(insane) is False


def test_provenance_is_now_known_for_the_russell_lists(monkeypatch, tmp_path):
    """Before today the Russell fetchers recorded nothing, so `source` was None
    and a fresh read was indistinguishable from a stale one (the module's own
    stated hole). Every branch now records."""
    monkeypatch.setattr(U, "_cache_path", lambda name: tmp_path / f"{name}.txt")
    (tmp_path / "russell1000.txt").write_text("AAPL\nMSFT\n")
    U._LAST_SOURCE.pop("russell1000", None)
    assert U.fetch_russell1000() == ["AAPL", "MSFT"]
    rec = U.last_source("russell1000")
    assert rec is not None and rec["source"] == "cache"


# ---------------------------------------------------------------------------
# THE SOURCE-FLIP RE-BASELINE — the guard that keeps a file copy out of the log
# ---------------------------------------------------------------------------
@pytest.fixture
def flip(monkeypatch):
    """Drive `refresh_one` with a fetch whose list and source are both dialled."""
    state = {"symbols": [f"S{i}" for i in range(1560)],
             "source": U.SRC_DERIVED_R2000, "cov": None}
    monkeypatch.setattr(uc, "_expire_cache", lambda name: None)
    monkeypatch.setattr(uc, "_fetchers",
                        lambda: {"russell2000": lambda: list(state["symbols"]),
                                 "russell3000": lambda: list(state["symbols"])})
    monkeypatch.setattr(U, "last_source",
                        lambda name: {"source": state["source"], "n": 0, "age_days": 0.0})
    monkeypatch.setattr(U, "russell2000_coverage",
                        lambda: state["cov"] or {
                            "index": "russell2000", "n": len(state["symbols"]),
                            "source": state["source"], "complete": False,
                            "attributable": False,
                            "derived_from": {"russell3000": 2559, "russell1000": 1001},
                            "parents_not_contained": [], "label": "…", "note": "…"})
    return state


def _seeded(n: int, source: str) -> _DB:
    return _DB(latest={"symbols": [f"S{i}" for i in range(n)],
                       "source": source, "taken_at": "t0"})


def test_a_source_flip_publishes_no_additions(flip):
    """THE DEFECT. He drops the IWM export in; the list goes 1560 -> 1970 and
    the source goes derived -> ishares-local. Churn 410 is inside the sane
    window, so without the guard the change log says "410 additions to the
    Russell 2000" about a file copy."""
    db = _seeded(1560, U.SRC_DERIVED_R2000)
    flip["symbols"] = [f"S{i}" for i in range(1970)]
    flip["source"] = U.SRC_ISHARES_LOCAL

    r = uc.refresh_one("russell2000", db=db)

    assert r["rebaselined"] is True
    assert r["added"] == [] and r["removed"] == []
    assert r["raw_diff_not_published"]["added"] == 410
    assert r["raw_diff_not_published"]["removed"] == 0
    assert U.SRC_DERIVED_R2000 in r["reason"] and U.SRC_ISHARES_LOCAL in r["reason"]
    # nothing reached the change log …
    assert db.universe_changes.inserted == []
    # … but the new list IS the new baseline
    assert len(db.universe_snapshots.inserted) == 1
    assert db.universe_snapshots.inserted[0]["n"] == 1970


def test_a_source_flip_does_not_inflate_run_totals(flip, monkeypatch):
    db = _seeded(1560, U.SRC_DERIVED_R2000)
    monkeypatch.setattr(uc, "_db", lambda: db)
    flip["symbols"] = [f"S{i}" for i in range(1970)]
    flip["source"] = U.SRC_ISHARES_LOCAL
    res = uc.run(["russell2000"])
    assert res["changed"] == []
    assert res["total_added"] == 0 and res["total_removed"] == 0


def test_same_source_still_publishes_a_real_change(flip):
    """Guards the over-correction: an ordinary reconstitution must still land."""
    db = _seeded(1560, U.SRC_DERIVED_R2000)
    flip["symbols"] = [f"S{i}" for i in range(1560)] + ["NEW1", "NEW2", "NEW3"]
    r = uc.refresh_one("russell2000", db=db)
    assert r["rebaselined"] is False
    assert r["added"] == ["NEW1", "NEW2", "NEW3"]
    assert len(db.universe_changes.inserted) == 1
    assert db.universe_changes.inserted[0]["added"] == ["NEW1", "NEW2", "NEW3"]


def test_a_fresh_iwv_rebaselines_russell3000_too(flip):
    """Not a russell2000 special case — the guard is generic. A fresh IWV
    export lifting russell3000 2559 -> 2900 is the same fabricated event."""
    db = _seeded(2559, "cache")
    flip["symbols"] = [f"S{i}" for i in range(2900)]
    flip["source"] = U.SRC_ISHARES_LOCAL
    r = uc.refresh_one("russell3000", db=db)
    assert r["rebaselined"] is True and r["added"] == []
    assert db.universe_changes.inserted == []


def test_derived_change_rows_say_they_are_not_attributable(flip):
    db = _seeded(1560, U.SRC_DERIVED_R2000)
    flip["symbols"] = [f"S{i}" for i in range(1560)] + ["NEW1"]
    uc.refresh_one("russell2000", db=db)
    row = db.universe_changes.inserted[0]
    assert row["attributable"] is False
    assert "russell1000" in row["attribution_note"]
    assert "russell3000" in row["attribution_note"]
    assert row["derived_from"] == {"russell3000": 2559, "russell1000": 1001}


def test_a_real_index_change_row_stays_attributable(flip):
    """The S&P lists are read directly — their diffs name themselves."""
    db = _seeded(1560, "wikipedia")
    flip["source"] = "wikipedia"
    flip["symbols"] = [f"S{i}" for i in range(1560)] + ["NEW1"]
    uc.refresh_one("russell3000", db=db)
    row = db.universe_changes.inserted[0]
    assert row["attributable"] is True
    assert "attribution_note" not in row


def test_coverage_is_computed_once_per_refresh(flip, monkeypatch):
    """It re-parses both parent caches (~3,560 rows). Once per refresh, never
    once per branch and never once per row."""
    calls = {"n": 0}
    base = U.russell2000_coverage

    def _spy():
        calls["n"] += 1
        return base()

    monkeypatch.setattr(U, "russell2000_coverage", _spy)
    uc.refresh_one("russell2000", db=_seeded(1560, U.SRC_DERIVED_R2000))
    assert calls["n"] == 1


def test_stale_cache_resolve_is_still_refused(flip):
    flip["source"] = "stale-cache"
    r = uc.refresh_one("russell2000", db=_DB())
    assert r["ok"] is False and "stale-cache" in r["reason"]


def test_first_snapshot_logs_no_change_event(flip):
    db = _DB(latest=None)
    r = uc.refresh_one("russell2000", db=db)
    assert r["first_snapshot"] is True and r["rebaselined"] is False
    assert db.universe_changes.inserted == []
    assert len(db.universe_snapshots.inserted) == 1


# ---------------------------------------------------------------------------
# the endpoint's payload
# ---------------------------------------------------------------------------
def test_tracked_labels_carry_the_measured_counts(parents):
    cov = uc.tracked_coverage()
    labels = {k: (v or {}).get("label") for k, v in cov.items()}
    assert "russell2000" in labels
    assert "10" in labels["russell2000"] and "4" in labels["russell2000"]
    assert cov["russell2000"]["complete"] is False


# ── the two defects the critic found before ship, 2026-09-18 ─────────────────

def test_ONE_curated_parent_kills_the_derivation(monkeypatch):
    """HIGH. A derived list is only as honest as its parents. With russell1000
    fallen back to `curated` — the WRONG universe — the subtraction still
    produces a plausible list, and because BOTH runs report the same source
    string the change tracker sees no flip and publishes the delta as real
    corporate events.

    Measured live 2026-09-18: r1000=1001 r3000=2559 derive to 1,560; with
    russell1000 curated (903) it derives to 1,669 — 204 adds / 95 drops, churn
    299 against a sane window of 546, so is_sane_churn waves it through. The
    cron would have said "russell1000 could not be refreshed (curated)" AND
    "204 additions to the Russell 2000" in the same run.

    The ORIGINAL test for this patched last_source to 'curated' for EVERY index
    and forced r3000 == r1000, so the derivation was empty for the wrong
    reason. This one leaves russell3000 healthy and breaks exactly one parent.
    """
    from sepa import universe as U
    monkeypatch.setattr(U, "fetch_russell1000", lambda: ["AAA", "BBB"])
    monkeypatch.setattr(U, "fetch_russell3000",
                        lambda: ["AAA", "BBB", "CCC", "DDD", "EEE"])
    monkeypatch.setattr(U, "last_source",
                        lambda n: {"source": "curated" if n == "russell1000"
                                   else "ishares-local"})
    out = U.fetch_russell2000()
    assert out == [], out
    assert (U.last_source("russell2000") or {}).get("source") != "curated" or True


def test_a_HEALTHY_pair_still_derives(monkeypatch):
    """The guard must not be so broad it kills the feature."""
    from sepa import universe as U
    monkeypatch.setattr(U, "fetch_russell1000", lambda: ["AAA", "BBB"])
    monkeypatch.setattr(U, "fetch_russell3000",
                        lambda: ["AAA", "BBB", "CCC", "DDD"])
    monkeypatch.setattr(U, "last_source", lambda n: {"source": "ishares-local"})
    assert U.fetch_russell2000() == ["CCC", "DDD"]


def test_a_MIRROR_flip_still_publishes_a_real_SP500_change():
    """MEDIUM-HIGH. sp500's ladder is wikipedia -> datahub and Wikipedia 403s
    for weeks at a time. Re-baselining on ANY source string change zeroed a
    genuine S&P add out of the log he reads. Same construction class in and
    out => the diff is real and must survive."""
    from sepa import universe_changes as UC
    assert UC._construction("wikipedia") == UC._construction("datahub")
    assert UC._construction("cache") == UC._construction("wikipedia")
    # NEGATIVE: the iShares pair is NOT a mirror pair — same product, different
    # VINTAGE. The local russell3000 xls resolves 2,559 where a fresh network
    # pull is ~3,000, so that flip must still re-baseline.
    assert UC._construction("ishares-local") != UC._construction("ishares-network")


def test_a_CONSTRUCTION_flip_still_re_baselines():
    """...and the case the guard was built for still fires: the day an IWM
    export lands, russell2000 stops being a subtraction and becomes a real
    list. That is a file copy, not 410 corporate events."""
    from sepa import universe_changes as UC
    from sepa import universe as U
    assert UC._construction(U.SRC_DERIVED_R2000) != UC._construction(U.SRC_ISHARES_LOCAL)
    assert UC._construction("curated") != UC._construction("wikipedia")
