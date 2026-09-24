"""FRED shadow releases + the cold-fetch lock — macro_calendar (2026-09-24).

"Jobless claims" printed twice a week (Thursday = release 180, the print;
Friday = release 469, the STATE detail) and a phantom "Retail sales" shipped
on 2026-10-08 (release 494, the Chicago Fed summary). Root cause: substring
needles in _RELEASE_TIERS also match FRED "shadow" releases, and the
(kind, date) dedupe only hides a shadow that lands on the print's own date.
Fix: _RELEASE_EXCLUDE, checked before the needle table.

Also pins the module-level lock in get_macro_calendar (one cold FRED fetch at a
time) and, as a strict xfail, the OPEN padding defect at days >= 21.

Fixture: tests/fixtures/fred_release_dates_2026_09_24.json — FRED
/releases/dates response rows (realtime 2026-09-24 → 2026-10-24), trimmed to
every row the PRE-fix matcher tiered + the 31 FOMC padding rows + 3 unmatched
negatives. No API key in it.

Run:
  cd backend && .venv/bin/python -m pytest tests/test_macro_calendar_claims_2026_09_24.py -q -p no:cacheprovider
"""
import datetime
import json
import os
import sys
import threading
import time
from collections import defaultdict

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import macro_calendar as mc  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                       "fred_release_dates_2026_09_24.json")
TODAY = datetime.date(2026, 9, 24)

# The 8 measured shadow names (FRED release_id in the comment).
SHADOWS = [
    "State Unemployment Insurance Weekly Claims Report",   # 469
    "Research Consumer Price Index",                       # 345
    "Gross Domestic Product by State",                     # 140
    "Gross Domestic Product by Industry",                  # 331
    "Debt to Gross Domestic Product Ratios",               # 263
    "Personal Consumption Expenditures by State",          # 391
    "Monthly Retail Trade and Food Services",              # 436
    "Chicago Fed Advance Retail Trade Summary",            # 494
]

# The 8 real prints (FRED release_id in the comment) → (kind, tier, label).
PRINTS = {
    "Unemployment Insurance Weekly Claims Report": ("claims", 2, "Jobless claims"),         # 180
    "Consumer Price Index": ("cpi", 1, "CPI"),                                              # 10
    "Gross Domestic Product": ("gdp", 2, "GDP"),                                            # 53
    "Personal Income and Outlays": ("pce", 1, "Core PCE"),                                  # 54
    "Advance Monthly Sales for Retail and Food Services": ("retail", 2, "Retail sales"),    # 9
    "Employment Situation": ("jobs", 1, "Jobs report (NFP)"),                               # 50
    "Job Openings and Labor Turnover Survey": ("jolts", 2, "JOLTS"),                        # 192
    "ADP National Employment Report": ("adp", 2, "ADP payrolls"),                           # 194
}

PRE_FIX_KINDS = {"claims", "cpi", "gdp", "pce", "retail", "adp", "jobs", "jolts",
                 "ppi", "housing", "confidence", "regional_fed", "trade", "fomc"}


def _rows():
    with open(FIXTURE) as fh:
        return json.load(fh)["release_dates"]


class _Frozen(mc.datetime):
    @classmethod
    def now(cls, tz=None):
        return mc.datetime(2026, 9, 24, 12, 0, tzinfo=tz or mc.timezone.utc)


@pytest.fixture
def frozen_fred(monkeypatch):
    """Clock frozen at 2026-09-24 (UTC :_fred_releases and ET _today_et), FRED
    served from the fixture. Returns the list of params each GET carried."""
    import sepa.fred
    payload = {"release_dates": _rows()}
    calls = []

    class _Resp:
        status_code = 200

        def json(self):
            return payload

    def _get(*a, **k):
        calls.append(k.get("params") or {})
        return _Resp()

    monkeypatch.setattr(mc, "datetime", _Frozen)
    monkeypatch.setattr(mc, "_today_et", lambda: TODAY)
    monkeypatch.setattr(sepa.fred, "api_key", lambda: "testkey")
    monkeypatch.setattr("requests.get", _get)
    return calls


# ── fixture hygiene ───────────────────────────────────────────────────────────

def test_fixture_is_response_data_without_key_or_last_updated():
    raw = open(FIXTURE).read()
    assert "api_key" not in raw and "testkey" not in raw
    rows = _rows()
    assert rows and all(set(r) == {"release_id", "release_name", "date"} for r in rows)
    fomc = [r for r in rows if r["release_name"] == "FOMC Press Release"]
    assert len(fomc) == 31 and len({r["date"] for r in fomc}) == 31


# ── _match_tier per name [C2] ─────────────────────────────────────────────────

@pytest.mark.parametrize("name", SHADOWS)
def test_shadow_release_matches_no_tier(name):
    assert mc._match_tier(name) is None
    assert mc._match_tier(name.upper()) is None       # case-insensitive


@pytest.mark.parametrize("name,expected", sorted(PRINTS.items()))
def test_real_print_still_matches_its_tier(name, expected):
    assert mc._match_tier(name) == expected
    assert mc._match_tier(name.upper()) == expected


def test_unrelated_unemployment_release_never_matched():
    # NEGATIVE: it never matched before the fix and must not start matching.
    assert mc._match_tier("Unemployment in States and Local Areas") is None


def test_fomc_press_release_still_matches_here_skipped_downstream():
    # NEGATIVE for the exclusion: FOMC is dropped in _fred_releases, not here.
    assert mc._match_tier("FOMC Press Release") == ("fomc", 1, "FOMC decision")


def test_exclusion_needles_are_lower_case():
    # _match_tier lower-cases the name; an upper-case needle could never fire.
    assert all(x == x.lower() and x for x in mc._RELEASE_EXCLUDE)


def test_empty_and_none_names_match_nothing():
    assert mc._match_tier("") is None
    assert mc._match_tier(None) is None


# ── fixture-wide: one source per (kind, date) [C2] ───────────────────────────

def test_fixture_one_source_per_kind_and_date():
    groups = defaultdict(set)
    for r in _rows():
        meta = mc._match_tier(r["release_name"])
        if meta:
            groups[(meta[0], r["date"])].add(r["release_name"])
    multi = {k: v for k, v in groups.items() if len(v) != 1}
    assert multi == {}


def test_fixture_exclusion_eats_no_kind():
    kinds = {m[0] for m in (mc._match_tier(r["release_name"]) for r in _rows()) if m}
    assert kinds == PRE_FIX_KINDS


def test_fixture_unmatched_negatives_stay_unmatched():
    for nm in ("Bankrate Monitor (BRM) National Index",
               "Housing Units Authorized By Building Permits",
               "Key ECB Interest Rates"):
        assert any(r["release_name"] == nm for r in _rows())
        assert mc._match_tier(nm) is None


# ── _fred_releases(14), frozen at 2026-09-24 ─────────────────────────────────

def test_fred_releases_14_frozen_rows(frozen_fred):
    out = mc._fred_releases(14)
    assert frozen_fred and frozen_fred[0]["realtime_start"] == "2026-09-24"
    assert frozen_fred[0]["realtime_end"] == "2026-10-08"

    by_kind = defaultdict(list)
    for e in out:
        by_kind[e["kind"]].append((e["date"], e["source"]))

    claims = [d for d, _ in by_kind["claims"]]
    assert claims == ["2026-09-24", "2026-10-01", "2026-10-08"]
    assert all(datetime.date.fromisoformat(d).weekday() == 3 for d in claims)   # Thursday
    assert {s for _, s in by_kind["claims"]} == {"Unemployment Insurance Weekly Claims Report"}

    assert by_kind["retail"] == []          # 494's 10-08 phantom gone; 9 prints 10-15
    assert by_kind["gdp"] == [("2026-09-30", "Gross Domestic Product")]
    assert by_kind["pce"] == [("2026-09-30", "Personal Income and Outlays")]
    assert "cpi" not in by_kind             # 10-14 is outside the window
    assert [d for d, _ in by_kind["jobs"]] == ["2026-10-02"]
    assert [d for d, _ in by_kind["jolts"]] == ["2026-09-29"]
    assert [d for d, _ in by_kind["adp"]] == ["2026-09-30"]
    assert "fomc" not in by_kind            # padding rows skipped (frozen-date path)

    assert {(e["date"], e["kind"]) for e in out} == {
        ("2026-09-24", "claims"), ("2026-09-24", "housing"), ("2026-09-25", "confidence"),
        ("2026-09-29", "jolts"), ("2026-09-30", "adp"), ("2026-09-30", "gdp"),
        ("2026-09-30", "pce"), ("2026-10-01", "claims"), ("2026-10-02", "jobs"),
        ("2026-10-06", "trade"), ("2026-10-08", "claims"),
    }
    assert len(out) == 11
    assert [(e["date"], e["tier"]) for e in out] == sorted((e["date"], e["tier"]) for e in out)


def test_fred_releases_no_shadow_source_ever_served(frozen_fred):
    # NEGATIVE across the whole 30-day fixture window: no shadow name is a source.
    out = mc._fred_releases(30)
    assert not {e["source"] for e in out} & set(SHADOWS)
    assert "fomc" not in {e["kind"] for e in out}


def test_fred_releases_no_key_returns_empty(monkeypatch):
    # NEGATIVE: no key → [] without touching the network.
    import sepa.fred
    monkeypatch.setattr(sepa.fred, "api_key", lambda: "")
    monkeypatch.delenv("FRED_API_KEY", raising=False)

    def _boom(*a, **k):
        raise AssertionError("network touched without a key")

    monkeypatch.setattr("requests.get", _boom)
    assert mc._fred_releases(14) == []


# ── compute(14): one claims row per ISO week ─────────────────────────────────

def test_compute_14_one_claims_per_iso_week(frozen_fred, monkeypatch):
    monkeypatch.setattr(mc, "_earnings_ahead", lambda days: [])
    d = mc.compute(14)
    t2_claims = [e for e in d["macro_by_tier"]["2"] if e["kind"] == "claims"]
    weeks = [datetime.date.fromisoformat(e["date"]).isocalendar()[1] for e in t2_claims]
    assert len(t2_claims) == 3 and len(weeks) == len(set(weeks))
    assert not any(e["kind"] == "retail" for e in d["macro"])
    t1 = d["next_tier1"]
    assert isinstance(t1, dict) and t1["tier"] == 1
    assert (t1["date"], t1["kind"]) == ("2026-09-30", "pce")   # first tier-1 by date
    assert d["days"] == 14


# ── lock + double-checked cache [C7] ─────────────────────────────────────────

def test_concurrent_cold_callers_share_one_compute(monkeypatch):
    monkeypatch.setattr(mc, "_CACHE", {"at": 0.0, "data": None})
    calls = []

    def _slow(days=mc.DEFAULT_DAYS):
        calls.append(days)
        time.sleep(0.2)
        return {"days": days, "n": len(calls)}

    monkeypatch.setattr(mc, "compute", _slow)
    barrier = threading.Barrier(2)
    results = [None, None]

    def _run(i):
        barrier.wait()
        results[i] = mc.get_macro_calendar()

    ts = [threading.Thread(target=_run, args=(i,)) for i in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(5)
    assert len(calls) == 1
    assert results[0] is results[1] and results[0] is not None

    # a warm hit does not recompute
    assert mc.get_macro_calendar() is results[0]
    assert len(calls) == 1

    # NEGATIVE: force=True always recomputes (under the lock)
    forced = mc.get_macro_calendar(force=True)
    assert len(calls) == 2 and forced is not results[0]

    # NEGATIVE: the cache key is still `days` — a 7-day call after a 14-day fill recomputes
    seven = mc.get_macro_calendar(days=7)
    assert len(calls) == 3 and seven["days"] == 7


def test_lock_is_released_when_compute_raises(monkeypatch):
    # NEGATIVE: a failing cold fetch must not wedge the lock for the next caller.
    monkeypatch.setattr(mc, "_CACHE", {"at": 0.0, "data": None})

    def _boom(days=mc.DEFAULT_DAYS):
        raise RuntimeError("FRED down")

    monkeypatch.setattr(mc, "compute", _boom)
    with pytest.raises(RuntimeError):
        mc.get_macro_calendar()
    assert mc._CACHE_LOCK.acquire(timeout=1)
    mc._CACHE_LOCK.release()
    assert mc._CACHE["data"] is None


# ── OPEN defect: the padding filter at days >= 21 [C3] ───────────────────────

@pytest.mark.xfail(strict=True, reason=(
    "padding filter drops a weekly print at days >= 21 — HIS CALL §7.5; "
    "XPASS means someone fixed it, remove this marker deliberately"))
def test_fred_releases_21_keeps_the_weekly_claims_print(frozen_fred):
    out = mc._fred_releases(21)
    claims = [e["date"] for e in out if e["kind"] == "claims"]
    assert claims == ["2026-09-24", "2026-10-01", "2026-10-08", "2026-10-15"]
