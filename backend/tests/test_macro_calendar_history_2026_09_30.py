"""macro_calendar.past_events — the dated T1/T2 history (2026-09-30).

Feeds the 🛡️ Resiliency tab. The fixture is FRED's real per-release history
captured in the api container on 2026-09-30 (names + dates, no key). Hermetic:
every FRED call goes through an injected `fetch` (or a patched `_fred_get`).
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

import macro_calendar as mc

FIX = Path(__file__).resolve().parent / "fixtures" / "fred_release_history_2026_09_30.json"
DATA = json.loads(FIX.read_text(encoding="utf-8"))
KEY = "k3y0123456789abcdef0123456789abcd"          # a fake key — must never surface

START, END = date(2024, 9, 1), date(2026, 9, 30)


def _fetch_from(data, *, fail=None, calls=None, names=None):
    fail = fail or {}

    def fetch(path, params):
        rid = int(params["release_id"])
        if calls is not None:
            calls.append((path, rid))
        if str(rid) in fail:
            raise mc.FredHTTPError(fail[str(rid)])
        rel = data["releases"].get(str(rid))
        if rel is None:
            return {}
        if path == "release":
            return {"releases": [{"id": rid, "name": (names or {}).get(rid, rel["name"])}]}
        assert path == "release/dates"
        return {"release_dates": [{"release_id": rid, "date": d} for d in rel["dates"]]}
    return fetch


@pytest.fixture(autouse=True)
def _clear_cache():
    mc._HISTORY_CACHE.clear()
    yield
    mc._HISTORY_CACHE.clear()


# ---------------------------------------------------------------- positive
def test_fixture_is_the_real_capture_and_holds_no_key():
    raw = FIX.read_text(encoding="utf-8")
    assert "api_key" not in raw and "apiKey" not in raw
    assert set(DATA["releases"]) == {str(i) for i in mc.HISTORY_RELEASE_IDS}
    assert DATA["releases"]["54"]["dates"][-1] == "2026-09-30"            # Core PCE today
    assert "2026-09-30" in DATA["releases"]["53"]["dates"]                 # GDP today


def test_exact_events_from_the_fixture():
    out = mc.past_events(START, END, fetch=_fetch_from(DATA))
    assert out["available"] is True and out["errors"] == []
    assert out["start"] == "2024-09-01" and out["end"] == "2026-09-30"
    assert out["unsourced"] == list(mc.HISTORY_UNSOURCED)
    ev = out["events"]
    by = Counter(e["kind"] for e in ev)
    assert by == {"jobs": 24, "cpi": 24, "pce": 25, "gdp": 25, "retail": 27, "jolts": 25,
                  "adp": 26, "claims": 101, "ppi": 24,
                  "fomc": sum(1 for d in mc.FOMC_DECISION_DATES if "2024-09-01" <= d <= "2026-09-30")}
    tiers = {e["kind"]: e["tier"] for e in ev}
    assert {k for k, t in tiers.items() if t == 1} == {"jobs", "cpi", "pce", "fomc"}
    assert {k for k, t in tiers.items() if t == 2} == {"gdp", "retail", "jolts", "adp",
                                                       "claims", "ppi"}
    assert tiers["ppi"] == 2                                   # the module's own tiering
    # sorted (date, tier), deduped on (kind, date)
    assert ev == sorted(ev, key=lambda e: (e["date"], e["tier"], e["kind"]))
    assert len({(e["kind"], e["date"]) for e in ev}) == len(ev)
    today = [e for e in ev if e["date"] == "2026-09-30"]
    assert {(e["kind"], e["tier"]) for e in today} == {("pce", 1), ("gdp", 2), ("adp", 2)}
    assert all(set(e) == {"date", "kind", "tier", "label", "source", "release_id"} for e in ev)


def test_fomc_rows_come_from_the_constant_incl_2024():
    out = mc.past_events(START, END, fetch=_fetch_from(DATA))
    fomc = [e for e in out["events"] if e["kind"] == "fomc"]
    assert [e["date"] for e in fomc][:3] == ["2024-09-18", "2024-11-07", "2024-12-18"]
    assert all(e["source"] == "Federal Reserve FOMC calendar" and e["release_id"] is None
               and e["tier"] == 1 and e["label"] == "FOMC decision" for e in fomc)
    assert "2026-09-16" in [e["date"] for e in fomc]


def test_2024_fomc_dates_extend_the_constant_in_order():
    d = mc.FOMC_DECISION_DATES
    assert d[:3] == ("2024-09-18", "2024-11-07", "2024-12-18")
    assert list(d) == sorted(d)


def test_claims_every_thursday():
    out = mc.past_events(date(2026, 1, 1), date(2026, 9, 29), fetch=_fetch_from(DATA))
    claims = [date.fromisoformat(e["date"]) for e in out["events"] if e["kind"] == "claims"]
    assert len(claims) >= 38
    assert Counter(d.weekday() for d in claims).most_common(1)[0][0] == 3   # Thursday


def test_window_is_inclusive_and_max_tier_filters():
    out = mc.past_events(date(2026, 9, 30), date(2026, 9, 30), fetch=_fetch_from(DATA))
    assert {e["kind"] for e in out["events"]} == {"pce", "gdp", "adp"}
    t1 = mc.past_events(date(2026, 9, 30), date(2026, 9, 30), max_tier=1,
                        fetch=_fetch_from(DATA))
    assert [e["kind"] for e in t1["events"]] == ["pce"]


def test_dedupe_kind_and_date():
    dup = json.loads(json.dumps(DATA))
    dup["releases"]["10"]["dates"] = dup["releases"]["10"]["dates"] + ["2026-09-11"]
    out = mc.past_events(START, END, fetch=_fetch_from(dup))
    assert sum(1 for e in out["events"] if e["kind"] == "cpi" and e["date"] == "2026-09-11") == 1


def test_cache_one_fetch_per_ttl_and_force(monkeypatch):
    calls = []
    fetch = _fetch_from(DATA, calls=calls)
    monkeypatch.setattr(mc, "_fred_get", fetch)
    a = mc.past_events(START, END)
    n = len(calls)
    b = mc.past_events(START, END)
    assert a is b and len(calls) == n                          # served from the cache
    mc.past_events(START, END, force=True)
    assert len(calls) == 2 * n


# ---------------------------------------------------------------- negative
def test_NEG_fomc_release_101_is_never_fetched():
    calls = []
    mc.past_events(START, END, fetch=_fetch_from(DATA, calls=calls))
    assert 101 not in {rid for _p, rid in calls}
    assert 101 not in mc.HISTORY_RELEASE_IDS


def test_NEG_one_release_5xx_is_an_error_row_and_no_key_leaks(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    fetch = _fetch_from(DATA, fail=DATA["http_status_variant"])
    out = mc.past_events(START, END, fetch=fetch)
    assert out["available"] is True
    assert out["errors"] == [{"release_id": 9, "reason": "HTTP 500"}]
    assert not any(e["kind"] == "retail" for e in out["events"])
    assert KEY not in json.dumps(out) and KEY not in caplog.text


def test_NEG_requests_error_string_with_the_key_never_surfaces(monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)

    class ConnErr(Exception):
        pass

    def fetch(path, params):
        raise ConnErr(f"HTTPSConnectionPool: /fred/release?api_key={KEY}&release_id=50")
    out = mc.past_events(START, END, fetch=fetch)
    assert out["available"] is False and out["events"][0]["kind"] == "fomc"
    assert {e["reason"] for e in out["errors"]} == {"ConnErr"}
    assert KEY not in json.dumps(out) and KEY not in caplog.text
    assert "api_key" not in caplog.text


def test_NEG_all_fail_is_unavailable_and_never_raises():
    out = mc.past_events(START, END, fetch=_fetch_from(DATA, fail={str(i): 503 for i in
                                                                    mc.HISTORY_RELEASE_IDS}))
    assert out["available"] is False
    assert len(out["errors"]) == len(mc.HISTORY_RELEASE_IDS)
    assert {e["kind"] for e in out["events"]} == {"fomc"}       # the constant still stands


def test_NEG_a_failed_read_is_not_cached(monkeypatch):
    calls = []
    fetch = _fetch_from(DATA, calls=calls, fail={"9": 500})
    monkeypatch.setattr(mc, "_fred_get", fetch)
    mc.past_events(START, END)
    n = len(calls)
    mc.past_events(START, END)
    assert len(calls) == 2 * n


def test_NEG_no_key_is_a_named_reason(monkeypatch):
    monkeypatch.setattr(mc, "_fred_key", lambda: "")
    out = mc.past_events(START, END, force=True)
    assert out["available"] is False
    assert {e["reason"] for e in out["errors"]} == {"no FRED key"}


def test_NEG_a_name_matching_no_tier_is_ignored():
    out = mc.past_events(START, END, fetch=_fetch_from(
        DATA, names={50: "Some Unrelated Survey", 180: "State Unemployment Insurance "
                                                      "Weekly Claims Report"}))
    kinds = {e["kind"] for e in out["events"]}
    assert "jobs" not in kinds and "claims" not in kinds
    assert out["errors"] == [] and out["available"] is True


def test_NEG_a_release_named_fomc_contributes_nothing():
    out = mc.past_events(START, END, fetch=_fetch_from(DATA, names={46: "FOMC Press Release"}))
    fomc = [e for e in out["events"] if e["kind"] == "fomc"]
    assert all(e["release_id"] is None for e in fomc)
    assert not any(e["kind"] == "ppi" for e in out["events"])


def test_NEG_upcoming_calendar_untouched():
    import inspect
    src = inspect.getsource(mc._fred_releases)
    assert "releases/dates" in src and "date_count[e[\"source\"]] <= 3" in src
