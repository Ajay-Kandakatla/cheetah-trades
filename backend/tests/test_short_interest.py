"""Contracts for short-interest squeeze gauges (short_interest/client.py).

Pure logic — fetchers are monkeypatched, no network. Locks the pct-primary
squeeze label and the percent-of-shares / days-to-cover / trend computation.
"""
from __future__ import annotations

from short_interest import client


def test_squeeze_signal_is_pct_primary():
    # Mega-cap: <1% short, moderate days-to-cover → must NOT flag (can't squeeze)
    assert client._squeeze_signal(0.94, 2.74) == "low"
    # Genuinely elevated short interest
    assert client._squeeze_signal(12.91, 4.16) == "elevated"
    # Very high short %
    assert client._squeeze_signal(25.0, 1.0) == "high"
    # Elevated short % that's also hard to cover → high
    assert client._squeeze_signal(12.0, 6.0) == "high"
    # Mid short % + hard to cover → elevated
    assert client._squeeze_signal(6.0, 6.0) == "elevated"
    # Mid short % + easy to cover → low
    assert client._squeeze_signal(6.0, 2.0) == "low"


def test_squeeze_signal_dtc_only_fallback():
    assert client._squeeze_signal(None, 6.0) == "elevated"
    assert client._squeeze_signal(None, 1.0) == "low"


def test_short_interest_for_computes(monkeypatch):
    monkeypatch.setattr(client, "_fetch_short_interest_rows", lambda s, limit=4: [
        {"settlement_date": "2026-05-15", "short_interest": 1000, "avg_daily_volume": 500, "days_to_cover": 2.0},
        {"settlement_date": "2026-04-30", "short_interest": 800, "avg_daily_volume": 400, "days_to_cover": 2.0},
    ])
    monkeypatch.setattr(client, "_shares_outstanding", lambda s: 10000)
    d = client.short_interest_for("FOO")
    assert d["short_interest"] == 1000
    assert d["pct_of_shares"] == 10.0          # 1000 / 10000 * 100
    assert d["days_to_cover"] == 2.0
    assert d["si_change_pct"] == 25.0          # (1000 - 800) / 800 * 100
    assert d["prev_settlement_date"] == "2026-04-30"
    assert d["squeeze"] == "elevated"          # pct == 10 → elevated


def test_short_interest_for_none_when_no_record(monkeypatch):
    monkeypatch.setattr(client, "_fetch_short_interest_rows", lambda s, limit=4: [])
    assert client.short_interest_for("FOO") is None


def test_short_interest_for_handles_missing_shares(monkeypatch):
    monkeypatch.setattr(client, "_fetch_short_interest_rows", lambda s, limit=4: [
        {"settlement_date": "2026-05-15", "short_interest": 1000, "avg_daily_volume": 500, "days_to_cover": 6.0},
    ])
    monkeypatch.setattr(client, "_shares_outstanding", lambda s: None)
    d = client.short_interest_for("FOO")
    assert d["pct_of_shares"] is None
    assert d["si_change_pct"] is None          # no prior settlement
    assert d["squeeze"] == "elevated"          # no pct, dtc 6 ≥ HIGH_DTC


# ─────────────────────────────────────────────────────────────────────────────
# The short-INTEREST bulk cache (2026-09-20, for the Bonde pick line).
#
# THE DEFECT THESE NEGATIVES EXIST FOR: this module owns two different short
# measurements. Short VOLUME is a daily tape ratio (`short_volume_latest`);
# short INTEREST is a bi-monthly FINRA settlement (`short_interest_latest`).
# A days-to-cover chip fed from the volume cache would render a confident
# number of the wrong series, so the read path is pinned to SI_COLL alone.
# ─────────────────────────────────────────────────────────────────────────────
import time as _time
from datetime import date, timedelta

import pytest


class FakeColl:
    """Minimal Mongo double — `_id: {$in: [...]}` + `fetched_at: {$gte: n}`."""

    def __init__(self, docs=None):
        self.docs = {d["_id"]: dict(d) for d in (docs or [])}

    def find(self, q=None, proj=None):
        q = q or {}
        for d in self.docs.values():
            idq = q.get("_id")
            if isinstance(idq, dict) and d["_id"] not in idq.get("$in", []):
                continue
            fq = q.get("fetched_at")
            if isinstance(fq, dict) and (d.get("fetched_at") or 0) < fq.get("$gte", 0):
                continue
            yield dict(d)

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)

    def estimated_document_count(self):
        return len(self.docs)


class FakeDB:
    def __init__(self, colls=None):
        self.colls = dict(colls or {})
        self.touched = []

    def __getitem__(self, name):
        self.touched.append(name)
        return self.colls.setdefault(name, FakeColl())

    def __getattr__(self, name):
        return self[name]


def _iso(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


@pytest.fixture
def no_network(monkeypatch):
    """Any HTTP call from a read path is a bug, so make one an exception."""
    import requests

    def boom(*a, **k):
        raise AssertionError("a read path made a network call")

    monkeypatch.setattr(requests, "get", boom)
    return boom


# ───────────────────────────────────────────── short_interest_map
def test_short_interest_map_on_an_empty_collection_is_empty_and_never_fetches(no_network):
    db = FakeDB()
    assert client.short_interest_map(["FOO", "BAR"], db=db) == {}


def test_NEGATIVE_the_map_never_reads_the_short_VOLUME_cache(no_network):
    """THE WRONG-SERIES TRAP. `short_volume_latest` holds a DAILY tape ratio.
    Seed it for the symbol and the short-INTEREST map must still be empty —
    a days-to-cover chip fed from that collection would be a confident
    number of an entirely different measurement."""
    db = FakeDB({
        "short_volume_latest": FakeColl([
            {"_id": "FOO", "symbol": "FOO", "short_volume_pct": 61.2,
             "date": _iso(1)}]),
        "short_volume_cache": FakeColl([
            {"_id": "FOO-1", "symbol": "FOO", "short_volume_pct": 58.0}]),
    })
    assert client.short_interest_map(["FOO"], db=db) == {}
    assert "short_volume_latest" not in db.touched
    assert client.SI_COLL in db.touched
    # ...and the reader must not have grown a fallback behind our backs.
    src = open(client.__file__).read()
    body = src[src.index("def short_interest_map"):src.index("def warm_short_interest")]
    assert "short_volume" not in body


def test_the_stale_label_bites_past_SI_STALE_DAYS_and_not_before():
    db = FakeDB({client.SI_COLL: FakeColl([
        {"_id": "OLD", "symbol": "OLD", "settlement_date": _iso(46),
         "days_to_cover": 6.1},
        {"_id": "NEW", "symbol": "NEW", "settlement_date": _iso(44),
         "days_to_cover": 2.0},
    ])})
    m = client.short_interest_map(["OLD", "NEW"], db=db)
    assert client.SI_STALE_DAYS == 45
    assert m["OLD"]["stale"] is True and m["OLD"]["age_days"] == 46
    assert m["NEW"]["stale"] is False and m["NEW"]["age_days"] == 44
    # The label never touches the value it labels.
    assert m["OLD"]["days_to_cover"] == 6.1


def test_the_stale_label_reads_the_same_clock_as_the_rest_of_the_pick_line():
    """ONE CLOCK. The surprise and IPO legs age against the LOCAL date
    (`sepa.bonde_picks._today()`); a UTC `today` here runs a calendar day
    ahead every evening after 19:00 CT, so the two stale labels on one row
    would disagree by a day for five hours a night."""
    from sepa import bonde_picks as BP

    today = BP._today()
    assert client._age_days(today.isoformat()) == 0
    assert client._age_days((today - timedelta(days=46)).isoformat()) == 46


def test_NEGATIVE_age_days_never_reaches_for_the_UTC_clock():
    """The failure this pins is invisible for 19 hours a day, so pin the
    source: `_age_days` must not call `_now_utc()`."""
    src = open(client.__file__).read()
    body = src[src.index("def _age_days"):src.index("def short_interest_map")]
    assert "_now_utc" not in body
    assert "date.today()" in body


def test_a_remembered_MISS_reads_as_unknown_freshness_not_as_fresh():
    """A `settlement_date` of None is the warm saying "asked, no record" —
    it must not read as a zero-day-old settlement."""
    db = FakeDB({client.SI_COLL: FakeColl([
        {"_id": "ADR", "symbol": "ADR", "settlement_date": None,
         "fetched_at": _time.time()}])})
    m = client.short_interest_map(["ADR"], db=db)
    assert m["ADR"]["stale"] is None and m["ADR"]["age_days"] is None


def test_NEGATIVE_an_unparseable_settlement_date_is_unknown_not_a_crash():
    db = FakeDB({client.SI_COLL: FakeColl([
        {"_id": "JUNK", "symbol": "JUNK", "settlement_date": "not-a-date"}])})
    m = client.short_interest_map(["JUNK"], db=db)
    assert m["JUNK"]["stale"] is None and m["JUNK"]["age_days"] is None


# ───────────────────────────────────────────── warm_short_interest
def test_warm_writes_the_settlement_fields_and_a_fetched_at(monkeypatch):
    monkeypatch.setattr(client, "short_interest_for", lambda s: {
        "symbol": s, "settlement_date": "2026-08-31", "short_interest": 1000,
        "avg_daily_volume": 190, "days_to_cover": 5.28, "shares_outstanding": 5138,
        "pct_of_shares": 19.46, "prev_settlement_date": "2026-08-15",
        "si_change_pct": 3.1, "squeeze": "high"})
    db = FakeDB()
    res = client.warm_short_interest(["iova"], db=db, sleep_sec=0)
    assert res == {"n": 1, "fetched": 1, "written": 1, "skipped": 0, "failed": 0}
    doc = db[client.SI_COLL].docs["IOVA"]
    assert doc["days_to_cover"] == 5.28 and doc["pct_of_shares"] == 19.46
    assert doc["settlement_date"] == "2026-08-31"
    assert doc["fetched_at"] > 0


def test_warm_SKIPS_a_doc_fresher_than_the_TTL_unless_forced(monkeypatch):
    """TWO Massive calls per name — re-paying for a series that moves twice a
    month is the whole reason the TTL exists."""
    calls = []
    monkeypatch.setattr(client, "short_interest_for",
                        lambda s: calls.append(s) or {"settlement_date": "2026-08-31"})
    db = FakeDB({client.SI_COLL: FakeColl([
        {"_id": "FOO", "symbol": "FOO", "settlement_date": "2026-08-31",
         "fetched_at": _time.time()}])})
    res = client.warm_short_interest(["FOO"], db=db, sleep_sec=0)
    assert res["skipped"] == 1 and res["fetched"] == 0 and calls == []

    res = client.warm_short_interest(["FOO"], db=db, sleep_sec=0, force=True)
    assert res["skipped"] == 0 and res["fetched"] == 1 and calls == ["FOO"]


def test_a_None_answer_is_WRITTEN_so_the_miss_is_REMEMBERED(monkeypatch):
    """Without this the next warm re-pays two Massive calls for every ADR and
    thin name the provider has no record for, forever, and the board cannot
    tell "never warmed" from "warmed, no record"."""
    monkeypatch.setattr(client, "short_interest_for", lambda s: None)
    db = FakeDB()
    res = client.warm_short_interest(["ADR"], db=db, sleep_sec=0)
    assert res["written"] == 1 and res["failed"] == 0
    doc = db[client.SI_COLL].docs["ADR"]
    assert doc["settlement_date"] is None and doc["symbol"] == "ADR"
    # ...and the very next warm skips it on the TTL.
    assert client.warm_short_interest(["ADR"], db=db, sleep_sec=0)["skipped"] == 1


def test_NEGATIVE_warm_never_raises_when_the_fetcher_does(monkeypatch):
    """It runs inside a cron behind `market_hours.gate`; one thin name must
    not take down the other 198."""
    def boom(sym):
        if sym == "BAD":
            raise RuntimeError("provider 500")
        return {"settlement_date": "2026-08-31"}

    monkeypatch.setattr(client, "short_interest_for", boom)
    db = FakeDB()
    res = client.warm_short_interest(["BAD", "GOOD"], db=db, sleep_sec=0)
    assert res["failed"] == 1 and res["written"] == 1
    assert "GOOD" in db[client.SI_COLL].docs and "BAD" not in db[client.SI_COLL].docs


def test_warm_with_no_db_returns_counts_instead_of_raising(monkeypatch):
    monkeypatch.setattr(client, "_get_db", lambda: None)
    assert client.warm_short_interest(["FOO"])["n"] == 1
    assert client.short_interest_map(["FOO"]) == {}


# ───────────────────────────────────────────── the import cycle
def test_client_has_no_top_level_sepa_import():
    """sepa.bonde → sepa.bonde_picks → (inside attach) short_interest.client,
    and client._main → (inside the function) sepa.bonde. A module-level
    `import sepa` here closes the cycle."""
    import re
    for line in open(client.__file__).read().splitlines():
        assert not re.match(r"^(from|import) sepa", line), line


def test_import_order_bonde_then_client_and_back():
    import importlib
    import sys

    mods = ("sepa.bonde", "sepa.bonde_picks", "short_interest.client")
    for order in (mods[:1] + mods[2:], mods[2:] + mods[:1]):
        for m in mods:
            sys.modules.pop(m, None)
        for m in order:
            try:
                importlib.import_module(m)
            except ModuleNotFoundError as exc:      # bonde_picks lands in P2b
                if "bonde_picks" not in str(exc):
                    raise
