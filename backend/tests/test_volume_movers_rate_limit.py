"""sepa/volume_movers.py — one Yahoo 429 must not blank a float for a week (Ajay round C "fix all four", R1-11;
2026-10-13, Gajjala's tab WP2, trap T4).

`_fetch_shares_yf` swallowed every exception, so `shares_for` wrote its 7-day null TOMBSTONE on a 429 exactly as on a
real "no data" — the moat bug of 2026-10-11 in another module. Now a 429 writes only `rl_until` (now +
moat_backfill.BACKOFF_START_SEC): the float fields and `as_of` are never touched, the expired values are served while
the marker stands, and no second fetch happens inside it (the tombstone's stampede guard, kept). "no data" / "error"
keep the old 7-day tombstone. `_fetch_shares_yf` keeps its signature and its None (sepa/cap_warm.py:258 imports it).
"""
from __future__ import annotations

import pytest

from sepa import moat_backfill
from sepa import volume_movers as vm
from tests.test_gajjala_store import FakeColl

NOW = 1_800_000_000
WEEK = vm._SHARES_TTL_SEC


class YFRateLimitError(Exception):
    """Same class NAME yfinance raises on a 429 — `sepa.moat._is_rate_limit` matches by name."""


class _Ticker:
    def __init__(self, info=None, exc=None, calls=None):
        self._info, self._exc, self._calls = info, exc, calls

    @property
    def info(self):
        self._calls.append(1)
        if self._exc is not None:
            raise self._exc
        return self._info


@pytest.fixture
def env(monkeypatch):
    coll = FakeColl()
    calls: list = []
    box = {"info": {"floatShares": 3_100_000, "sharesOutstanding": 8_100_000, "marketCap": 50_000_000}, "exc": None}
    monkeypatch.setattr(vm, "_shares_coll", lambda: coll)
    monkeypatch.setattr(vm.time, "time", lambda: NOW)
    monkeypatch.setattr(vm.symbols, "yf_ticker", lambda s: _Ticker(box["info"], box["exc"], calls))
    return coll, calls, box


def _rate_limit(box):
    box["exc"] = YFRateLimitError("Too Many Requests. Rate limited. Try after a while.")


def test_fetch_status_classifies_429_no_data_error_ok(env):
    _coll, _calls, box = env
    assert vm._fetch_shares_status("AAA")[1] == "ok"
    _rate_limit(box)
    assert vm._fetch_shares_status("AAA") == (None, "rate_limited")
    box["exc"] = RuntimeError("connection reset")
    assert vm._fetch_shares_status("AAA") == (None, "error")
    box["exc"], box["info"] = None, {"marketCap": None}
    assert vm._fetch_shares_status("AAA") == (None, "no_data")


def test_429_writes_only_the_marker_never_a_tombstone(env):
    coll, _calls, box = env
    _rate_limit(box)
    vals, st = vm.shares_status("AAA")
    assert (vals, st) == (None, "rate_limited")
    doc = coll.docs["AAA"]
    assert doc["rl_until"] == NOW + moat_backfill.BACKOFF_START_SEC
    assert "as_of" not in doc
    assert not {"float_shares", "shares_outstanding", "market_cap"} & set(doc)


def test_429_leaves_an_existing_rows_float_fields_untouched(env):
    coll, _calls, box = env
    coll.docs["AAA"] = {"_id": "AAA", "float_shares": 2_000_000, "shares_outstanding": 5_000_000,
                        "market_cap": None, "as_of": NOW - WEEK - 10}
    _rate_limit(box)
    vals, st = vm.shares_status("AAA")
    assert st == "rate_limited" and vals["float_shares"] == 2_000_000       # the expired values, not None
    doc = coll.docs["AAA"]
    assert doc["float_shares"] == 2_000_000 and doc["as_of"] == NOW - WEEK - 10


def test_NEGATIVE_second_call_inside_the_marker_does_not_fetch(env):
    coll, calls, box = env
    _rate_limit(box)
    vm.shares_status("AAA")
    n = len(calls)
    assert vm.shares_status("AAA") == (None, "rl_marker")
    assert vm.shares_for("AAA") is None
    assert len(calls) == n, "the marker is the stampede guard — no Yahoo call while it stands"


def test_NEGATIVE_after_the_marker_a_fetch_happens(env, monkeypatch):
    coll, calls, box = env
    _rate_limit(box)
    vm.shares_status("AAA")
    box["exc"] = None
    monkeypatch.setattr(vm.time, "time", lambda: NOW + moat_backfill.BACKOFF_START_SEC + 1)
    n = len(calls)
    vals, st = vm.shares_status("AAA")
    assert st == "fetched" and vals["float_shares"] == 3_100_000 and len(calls) == n + 1
    assert coll.docs["AAA"]["as_of"] == NOW + moat_backfill.BACKOFF_START_SEC + 1


def test_NEGATIVE_stale_values_are_served_during_the_marker(env):
    coll, calls, box = env
    coll.docs["AAA"] = {"_id": "AAA", "float_shares": 2_000_000, "shares_outstanding": 5_000_000,
                        "market_cap": None, "as_of": NOW - WEEK - 10, "rl_until": NOW + 30}
    vals, st = vm.shares_status("AAA")
    assert st == "stale_served" and vals["float_shares"] == 2_000_000
    assert vm.shares_for("AAA")["float_shares"] == 2_000_000
    assert calls == []


def test_NEGATIVE_plain_no_data_still_tombstones_seven_days(env):
    coll, calls, box = env
    box["info"] = {}
    assert vm.shares_status("ETFX") == (None, "no_data")
    doc = coll.docs["ETFX"]
    assert doc["as_of"] == NOW and doc["float_shares"] is None and doc["shares_outstanding"] is None
    n = len(calls)
    assert vm.shares_status("ETFX") == (None, "tombstone")
    assert len(calls) == n


def test_NEGATIVE_cached_fresh_row_served_without_a_fetch(env):
    coll, calls, _box = env
    coll.docs["AAA"] = {"_id": "AAA", "float_shares": 1_000_000, "shares_outstanding": 2_000_000,
                        "market_cap": 9, "as_of": NOW - 60}
    assert vm.shares_status("AAA")[1] == "cached"
    assert vm.shares_for("AAA")["float_shares"] == 1_000_000
    assert calls == []


def test_NEGATIVE_fetch_false_never_calls_yahoo(env):
    coll, calls, _box = env
    assert vm.shares_status("NEW", fetch=False) == (None, "missing")
    coll.docs["OLD"] = {"_id": "OLD", "float_shares": 1, "as_of": NOW - WEEK - 1}
    assert vm.shares_status("OLD", fetch=False) == (None, "stale")
    assert calls == [] and "NEW" not in coll.docs


def test_NEGATIVE_fetch_shares_yf_still_returns_none_on_a_429(env):
    """cap_warm.py imports `_fetch_shares_yf` and catches per symbol — its contract is unchanged."""
    _coll, _calls, box = env
    _rate_limit(box)
    assert vm._fetch_shares_yf("AAA") is None
    box["exc"] = None
    assert vm._fetch_shares_yf("AAA") == {"shares_outstanding": 8_100_000, "float_shares": 3_100_000,
                                          "market_cap": 50_000_000}


def test_NEGATIVE_a_swapped_fetch_hook_is_still_honoured(env, monkeypatch):
    """A caller that replaces `_fetch_shares_yf` (tests, an injected warm) keeps working: its None = "no_data"."""
    coll, calls, _box = env
    monkeypatch.setattr(vm, "_fetch_shares_yf", lambda s: None)
    assert vm.shares_status("ZZZ") == (None, "no_data")
    assert calls == [] and coll.docs["ZZZ"]["as_of"] == NOW


# ── 2026-10-13 review: the served values carry the ROW's age ─────────────────────────────────────────────────────
def test_served_values_carry_the_rows_as_of(env):
    coll, _calls, _box = env
    coll.docs["AAA"] = {"_id": "AAA", "float_shares": 1_000_000, "shares_outstanding": 2_000_000,
                        "market_cap": 9, "as_of": NOW - 60}
    assert vm.shares_status("AAA")[0]["as_of"] == NOW - 60
    coll.docs["OLD"] = {"_id": "OLD", "float_shares": 2_000_000, "shares_outstanding": 5_000_000,
                        "market_cap": None, "as_of": NOW - WEEK - 10, "rl_until": NOW + 30}
    vals, st = vm.shares_status("OLD")
    assert st == "stale_served" and vals["as_of"] == NOW - WEEK - 10, "the week-old stamp, not now"


def test_fetched_values_carry_the_fetch_time(env):
    _coll, _calls, _box = env
    vals, st = vm.shares_status("AAA")
    assert st == "fetched" and vals["as_of"] == NOW


def test_NEGATIVE_shares_for_never_returns_the_as_of_key(env):
    """/sepa/shares, russell_watch and promo_circuit read `shares_for` — their payload is unchanged."""
    coll, _calls, _box = env
    coll.docs["AAA"] = {"_id": "AAA", "float_shares": 1_000_000, "shares_outstanding": 2_000_000,
                        "market_cap": 9, "as_of": NOW - 60}
    assert vm.shares_for("AAA") == {"shares_outstanding": 2_000_000, "float_shares": 1_000_000, "market_cap": 9}
    assert "as_of" not in vm.shares_for("NEW")
