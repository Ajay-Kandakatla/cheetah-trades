"""Moat carry-forward + moat-only backfill (2026-10-11).

The weekly research refresh hit Yahoo 429s on ~1,300 names; `compute_moat`
returned None for each (the same value as "no fundamentals") and the refresh
wrote `moat: null` over last week's good moat — 87.7% of served blobs blank.

Locks: a failed READ raises MoatFetchError (never None), the 429 breaker, the
research carry-forward (+ moat_as_of / moat_status stamps), the 0-of-6 read
guard, the scanner / peers fallback, the sequential backfill (pacing, backoff,
resumable pass, moat-only writes), the CLI wiring, and the coverage census.
Hermetic: every Yahoo / Mongo touch is an in-memory stand-in.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sepa import moat as moat_mod  # noqa: E402
from sepa import moat_backfill as mb  # noqa: E402
from sepa import research  # noqa: E402

try:                                   # the REAL class yfinance raises on 429
    from yfinance.exceptions import YFRateLimitError
except Exception:                      # pragma: no cover
    class YFRateLimitError(Exception):
        def __init__(self):
            super().__init__("Too Many Requests. Rate limited. Try after a while.")


# ── stand-ins ───────────────────────────────────────────────────────────────
class FakeColl:
    """The slice of a pymongo collection these modules use, keyed by
    `symbol` (research cache) or `_id` (backfill state)."""

    def __init__(self, docs=(), key="symbol"):
        self.key = key
        self.docs = {d[key]: copy.deepcopy(d) for d in docs}
        self.sets: list[tuple[str, dict]] = []

    def find_one(self, flt, projection=None, **_):
        d = self.docs.get(flt.get(self.key))
        return copy.deepcopy(d) if d else None

    def find(self, flt=None, projection=None, **_):
        return [copy.deepcopy(d) for d in self.docs.values()]

    def update_one(self, flt, update, upsert=False):
        k = flt[self.key]
        fields = update.get("$set", {})
        self.sets.append((k, dict(fields)))
        if k not in self.docs:
            if not upsert:
                return
            self.docs[k] = {self.key: k}
        for f, v in fields.items():
            assert "." not in f, f"dotted $set {f!r} fails on a null parent"
            self.docs[k][f] = copy.deepcopy(v)


GOOD = {"score": 72.0, "label": "NARROW", "tier": 3, "components": {},
        "narrative": "x", "data_source": "yfinance",
        "data_completeness": 6, "is_partial": False}
T_OLD = 1_790_000_000

GOOD_INFO = {"returnOnEquity": 0.30, "grossMargins": 0.60,
             "operatingMargins": 0.30, "freeCashflow": 30, "totalRevenue": 100,
             "totalDebt": 10, "totalCash": 50, "ebitda": 40,
             "revenueGrowth": 0.20}


class _Ticker:
    def __init__(self, info=None, exc=None):
        self._info, self._exc = info, exc

    @property
    def info(self):
        if self._exc is not None:
            raise self._exc
        return self._info


@pytest.fixture(autouse=True)
def _closed_breaker():
    moat_mod.reset_breaker()
    yield
    moat_mod.reset_breaker()


def _yf(info=None, exc=None, calls=None):
    def factory(sym):
        if calls is not None:
            calls.append(sym)
        return _Ticker(info, exc)
    return mock.patch.object(moat_mod.symbols, "yf_ticker", side_effect=factory)


# ── compute_moat: could-not-read vs no-data ─────────────────────────────────
def test_429_raises_rate_limited_and_opens_the_breaker():
    calls: list = []
    with _yf(exc=YFRateLimitError(), calls=calls):
        with pytest.raises(moat_mod.MoatFetchError) as ei:
            moat_mod.compute_moat("AAA")
        assert ei.value.rate_limited is True
        assert moat_mod.rate_limit_cooling()
        # inside the cooldown: no Yahoo call at all
        with pytest.raises(moat_mod.MoatFetchError) as ei2:
            moat_mod.compute_moat("BBB")
        assert ei2.value.rate_limited is True
        assert calls == ["AAA"]
        # the backfill path ignores the breaker and reads
        with pytest.raises(moat_mod.MoatFetchError):
            moat_mod.compute_moat("CCC", breaker=False)
        assert calls == ["AAA", "CCC"]


def test_transport_error_is_a_fetch_error_but_not_a_rate_limit():
    with _yf(exc=ConnectionError("reset by peer")):
        with pytest.raises(moat_mod.MoatFetchError) as ei:
            moat_mod.compute_moat("AAA")
    assert ei.value.rate_limited is False
    assert not moat_mod.rate_limit_cooling()      # breaker stays closed


def test_too_many_requests_message_counts_as_rate_limit():
    with _yf(exc=RuntimeError("Too Many Requests. Rate limited.")):
        with pytest.raises(moat_mod.MoatFetchError) as ei:
            moat_mod.compute_moat("AAA")
    assert ei.value.rate_limited is True


def test_empty_info_is_a_genuine_none_not_an_error():
    with _yf(info={}):
        assert moat_mod.compute_moat("AAA") is None
    with _yf(info=None):
        assert moat_mod.compute_moat("AAA") is None


def test_good_read_scores_and_stamps_as_of():
    with _yf(info=GOOD_INFO), mock.patch.object(moat_mod.time, "time", return_value=1_791_000_000.4):
        m = moat_mod.compute_moat("AAA")
    assert m["label"] == "WIDE" and m["data_completeness"] == 6
    assert m["as_of"] == 1_791_000_000


def test_lost_inputs_only_fires_on_zero_inputs_over_a_moat_with_inputs():
    zero = {"tier": 0, "data_completeness": 0}
    assert moat_mod.lost_inputs(zero, GOOD) is True
    assert moat_mod.lost_inputs(zero, {"tier": 2}) is True          # legacy dict, no completeness
    assert moat_mod.lost_inputs(zero, None) is False
    assert moat_mod.lost_inputs(zero, {"tier": 0, "data_completeness": 0}) is False
    assert moat_mod.lost_inputs(GOOD, GOOD) is False                 # new has inputs
    assert moat_mod.lost_inputs(None, GOOD) is False                 # genuine None is not this


# ── compute_research carry-forward ──────────────────────────────────────────
@pytest.fixture
def heavy_stubs():
    df = pd.DataFrame({"close": range(1, 261)},
                      index=pd.date_range("2025-01-01", periods=260))
    with mock.patch.object(research.prices, "load_prices", return_value=df), \
         mock.patch.object(research.adr, "liquidity_check", return_value={"liquid": True}), \
         mock.patch.object(research.adr, "adr_pct", return_value=3.0), \
         mock.patch.object(research.vcp, "detect", return_value=None), \
         mock.patch.object(research.power_play, "detect", return_value=None), \
         mock.patch.object(research.base_count, "count_bases", return_value=None), \
         mock.patch.object(research.stage_mod, "classify", return_value=None), \
         mock.patch.object(research.canslim, "fundamentals_for", return_value={"passed": 2}), \
         mock.patch.object(research.company_names, "name_for", return_value="Co"), \
         mock.patch.object(research, "ipo_age_for", return_value=None):
        yield


def _cache(docs=()):
    coll = FakeColl(docs)
    return coll, mock.patch.object(research, "_get_cache", return_value=coll)


def _moat_raises(exc):
    return mock.patch.object(research.moat_mod, "compute_moat", side_effect=exc)


def _moat_returns(val):
    return mock.patch.object(research.moat_mod, "compute_moat", return_value=val)


def test_429_keeps_the_old_moat_and_its_age(heavy_stubs):
    coll, p = _cache([{"symbol": "AAA", "moat": GOOD, "moat_as_of": T_OLD,
                       "moat_status": "ok", "cached_at": T_OLD}])
    with p, _moat_raises(moat_mod.MoatFetchError("AAA", "429", rate_limited=True)):
        out = research.compute_research("AAA")
    doc = coll.docs["AAA"]
    assert doc["moat"] == GOOD                      # NOT blanked
    assert doc["moat_as_of"] == T_OLD               # age not reset
    assert doc["moat_status"] == "fetch_failed"
    assert doc["moat_failed_at"] > T_OLD
    assert doc["cached_at"] > T_OLD                 # the rest of the blob refreshed
    assert doc["fundamentals"] == {"passed": 2}
    assert out["moat"] == GOOD and out["moat_status"] == "fetch_failed"
    _, written = coll.sets[-1]
    assert "moat" not in written and "moat_as_of" not in written


def test_429_on_a_legacy_moat_stamps_its_age_from_cached_at(heavy_stubs):
    # written before 2026-10-11: no moat_as_of — the moat was read with cached_at
    coll, p = _cache([{"symbol": "AAA", "moat": GOOD, "cached_at": T_OLD}])
    with p, _moat_raises(moat_mod.MoatFetchError("AAA", "429", rate_limited=True)):
        out = research.compute_research("AAA")
    doc = coll.docs["AAA"]
    assert doc["moat"] == GOOD
    assert doc["moat_as_of"] == T_OLD
    assert out["moat"]["as_of"] == T_OLD            # the returned copy shows the age


def test_genuine_no_data_writes_none(heavy_stubs):
    coll, p = _cache([{"symbol": "AAA", "moat": GOOD, "moat_as_of": T_OLD,
                       "cached_at": T_OLD}])
    with p, _moat_returns(None):
        out = research.compute_research("AAA")
    doc = coll.docs["AAA"]
    assert doc["moat"] is None
    assert doc["moat_status"] == "no_data"
    assert doc["moat_as_of"] > T_OLD
    assert out["moat"] is None


def test_no_previous_blob_and_a_429_writes_no_moat_and_does_not_crash(heavy_stubs):
    coll, p = _cache()
    with p, _moat_raises(moat_mod.MoatFetchError("NEW", "429", rate_limited=True)):
        out = research.compute_research("NEW")
    doc = coll.docs["NEW"]
    assert doc.get("moat") is None
    assert doc["moat_status"] == "fetch_failed"
    assert out["moat"] is None and out["moat_as_of"] is None


def test_a_fresh_read_replaces_the_old_moat(heavy_stubs):
    coll, p = _cache([{"symbol": "AAA", "moat": GOOD, "moat_as_of": T_OLD}])
    new = {**GOOD, "score": 85.0, "label": "WIDE", "tier": 4, "as_of": T_OLD + 999}
    with p, _moat_returns(new):
        research.compute_research("AAA")
    doc = coll.docs["AAA"]
    assert doc["moat"]["label"] == "WIDE"
    assert doc["moat_as_of"] == T_OLD + 999 and doc["moat_status"] == "ok"


def test_zero_input_read_never_replaces_a_moat_that_had_inputs(heavy_stubs):
    coll, p = _cache([{"symbol": "AAA", "moat": GOOD, "moat_as_of": T_OLD}])
    zero = {"score": 0.0, "label": "UNKNOWN", "tier": 0, "data_completeness": 0}
    with p, _moat_returns(zero):
        out = research.compute_research("AAA")
    assert coll.docs["AAA"]["moat"] == GOOD
    assert out["moat_status"] == "fetch_failed"


def test_zero_input_read_IS_written_when_nothing_better_is_stored(heavy_stubs):
    coll, p = _cache([{"symbol": "ETF", "moat": None}])
    zero = {"score": 0.0, "label": "UNKNOWN", "tier": 0, "data_completeness": 0}
    with p, _moat_returns(zero):
        research.compute_research("ETF")
    assert coll.docs["ETF"]["moat"]["label"] == "UNKNOWN"
    assert coll.docs["ETF"]["moat_status"] == "ok"


def test_a_scoring_bug_also_keeps_the_cached_moat(heavy_stubs):
    coll, p = _cache([{"symbol": "AAA", "moat": GOOD, "moat_as_of": T_OLD}])
    with p, _moat_raises(ZeroDivisionError("bug")):
        research.compute_research("AAA")
    assert coll.docs["AAA"]["moat"] == GOOD
    assert coll.docs["AAA"]["moat_status"] == "fetch_failed"


def test_with_moat_false_carries_without_reading_or_restamping(heavy_stubs):
    coll, p = _cache([{"symbol": "AAA", "moat": GOOD, "moat_as_of": T_OLD,
                       "moat_status": "ok"}])
    with p, _moat_raises(AssertionError("must not be called")) as cm:
        out = research.compute_research("AAA", with_moat=False)
    assert cm.call_count == 0
    doc = coll.docs["AAA"]
    assert doc["moat"] == GOOD and doc["moat_status"] == "ok"
    assert out["moat"] == GOOD


def test_refresh_universe_tallies_moat_outcomes(heavy_stubs):
    coll, p = _cache([{"symbol": s, "moat": GOOD, "moat_as_of": T_OLD} for s in ("A", "B")])
    with p, mock.patch.object(research.company_names, "bulk_warm"), \
            _moat_raises(moat_mod.MoatFetchError("x", "429", rate_limited=True)):
        res = research.refresh_universe(["A", "B"], max_workers=2)
    assert res["moat"] == {"fetch_failed": 2}
    with p, mock.patch.object(research.company_names, "bulk_warm"):
        res = research.refresh_universe(["A", "B"], max_workers=2, with_moat=False)
    assert res["moat"] == {"carried": 2}
    assert all(coll.docs[s]["moat"] == GOOD for s in ("A", "B"))


# ── THE regression, pinned end to end through the REAL compute_moat ────────
def test_REGRESSION_2026_10_11_a_429_never_blanks_a_cached_moat(heavy_stubs):
    """Real yfinance YFRateLimitError, real compute_moat, real
    compute_research + refresh_universe: every stored moat survives."""
    syms = ["NVDA", "MSFT", "KO"]
    coll, p = _cache([{"symbol": s, "moat": GOOD, "moat_as_of": T_OLD,
                       "cached_at": T_OLD} for s in syms])
    with p, _yf(exc=YFRateLimitError()), \
            mock.patch.object(research.company_names, "bulk_warm"):
        research.refresh_universe(syms, max_workers=3)
        research.compute_research("NVDA")
    for s in syms:
        assert coll.docs[s]["moat"] == GOOD, f"{s} moat was blanked by a 429"
        assert coll.docs[s]["moat_as_of"] == T_OLD
    assert all(f.get("moat", "absent") == "absent" for _, f in coll.sets)


# ── read paths: as_of attach + live-or-cached fallback ──────────────────────
def test_with_moat_as_of_sources_and_negatives():
    assert research.with_moat_as_of({"moat": GOOD, "moat_as_of": 5})["as_of"] == 5
    assert research.with_moat_as_of({"moat": GOOD, "cached_at": 7})["as_of"] == 7
    assert research.with_moat_as_of({"moat": {**GOOD, "as_of": 9}, "moat_as_of": 5})["as_of"] == 9
    assert "as_of" not in research.with_moat_as_of({"moat": GOOD})
    assert research.with_moat_as_of({"moat": None, "moat_as_of": 5}) is None
    assert research.with_moat_as_of({"moat": "WIDE"}) is None
    assert research.with_moat_as_of(None) is None


def test_moat_live_or_cached():
    coll, p = _cache([{"symbol": "AAA", "moat": GOOD, "moat_as_of": T_OLD}])
    live = {**GOOD, "as_of": T_OLD + 5}
    with p, _moat_returns(live):
        assert research.moat_live_or_cached("AAA") == live
    with p, _moat_raises(moat_mod.MoatFetchError("AAA", "429", rate_limited=True)):
        got = research.moat_live_or_cached("AAA")
        assert got["label"] == "NARROW" and got["as_of"] == T_OLD
        assert research.moat_live_or_cached("ZZZ") is None       # nothing cached
    with p, _moat_returns(None):                                  # Yahoo: no data
        assert research.moat_live_or_cached("AAA") is None


def test_scanner_and_peers_use_the_fallback_not_raw_compute_moat():
    root = Path(__file__).resolve().parents[1] / "sepa"
    scanner_src = (root / "scanner.py").read_text()
    peers_src = (root / "moat_peers.py").read_text()
    assert "research_mod.moat_live_or_cached" in scanner_src
    assert "_moat.compute_moat" not in scanner_src
    assert "research_mod.with_moat_as_of(blob)" in scanner_src
    assert "moat_live_or_cached" in peers_src
    assert "moat_mod.compute_moat" not in peers_src


# ── backfill: pick ──────────────────────────────────────────────────────────
T0 = 1_791_000_000


def test_pick_orders_no_moat_first_then_oldest_and_skips_this_pass():
    docs = [
        {"symbol": "OLD", "moat": GOOD, "moat_as_of": T0 - 900},
        {"symbol": "OLDER", "moat": GOOD, "moat_as_of": T0 - 9000},
        {"symbol": "LEGACY", "moat": GOOD},
        {"symbol": "ZNULL", "moat": None},
        {"symbol": "ANULL"},
        {"symbol": "NODATA", "moat": None, "moat_as_of": T0 - 50},
        {"symbol": "DONE", "moat": GOOD, "moat_as_of": T0 + 1},
        {"symbol": "TRIED", "moat": None, "moat_failed_at": T0 + 1},
        {"moat": None},                                   # no symbol: ignored
    ]
    assert mb.pick(docs, mode="null", pass_started_at=T0) == ["ANULL", "ZNULL", "NODATA"]
    assert mb.pick(docs, mode="refresh", pass_started_at=T0) == [
        "ANULL", "ZNULL", "NODATA", "LEGACY", "OLDER", "OLD"]
    assert mb.pick(docs, mode="refresh", pass_started_at=T0,
                   symbols=["old", "znull", "DONE"]) == ["ZNULL", "OLD"]
    assert mb.pick(docs, mode="null", pass_started_at=T0, symbols=[]) == []
    with pytest.raises(ValueError):
        mb.pick(docs, mode="everything", pass_started_at=T0)


# ── backfill: run ───────────────────────────────────────────────────────────
class Clock:
    def __init__(self, t=T0):
        self.t = float(t)
        self.sleeps: list[float] = []

    def __call__(self):
        return self.t

    def sleep(self, d):
        self.sleeps.append(d)
        self.t += d


def _fetcher(script, calls):
    """script: sym -> list of outcomes consumed in order (dict/None/exception);
    the last outcome repeats."""
    def fetch(sym):
        calls.append(sym)
        seq = script.get(sym, [dict(GOOD)])
        out = seq.pop(0) if len(seq) > 1 else seq[0]
        if isinstance(out, BaseException):
            raise out
        return copy.deepcopy(out)
    return fetch


def _rl():
    return moat_mod.MoatFetchError("x", "429", rate_limited=True)


def _run(coll, state, clock, script=None, calls=None, **kw):
    calls = calls if calls is not None else []
    return mb.run(coll, state, fetch=_fetcher(script or {}, calls),
                  sleep=clock.sleep, clock=clock, **kw)


def test_backfill_fills_nulls_and_writes_only_the_moat_fields():
    coll = FakeColl([
        {"symbol": "A", "moat": None, "cached_at": 111, "fundamentals": {"x": 1}},
        {"symbol": "B", "cached_at": 222},
        {"symbol": "C", "moat": GOOD, "moat_as_of": T0 - 10, "cached_at": 333},
    ])
    state, clock, calls = FakeColl(key="_id"), Clock(), []
    res = _run(coll, state, clock, {"B": [None]}, calls)
    assert calls == ["A", "B"]                      # C has a moat: untouched in null mode
    assert res["status"] == "done" and res["done"] is True
    assert res["counts"]["ok"] == 1 and res["counts"]["no_data"] == 1
    a = coll.docs["A"]
    assert a["moat"]["label"] == "NARROW" and a["moat_status"] == "ok"
    assert a["moat_as_of"] == a["moat"]["as_of"]
    assert a["cached_at"] == 111 and a["fundamentals"] == {"x": 1}
    assert coll.docs["B"]["moat"] is None and coll.docs["B"]["moat_status"] == "no_data"
    assert coll.docs["C"]["moat_as_of"] == T0 - 10
    for _, fields in coll.sets:
        assert set(fields) <= {"moat", "moat_as_of", "moat_status", "moat_failed_at"}
    assert clock.sleeps == [mb.DEFAULT_INTERVAL_SEC]  # paced between the 2 reads


def test_backfill_write_never_creates_a_blob():
    coll = FakeColl()
    assert mb._write(coll, "GHOST", dict(GOOD), T0) == "ok"
    assert coll.docs == {}


def test_backfill_backs_off_on_429_then_succeeds():
    coll = FakeColl([{"symbol": "A"}])
    state, clock = FakeColl(key="_id"), Clock()
    res = _run(coll, state, clock, {"A": [_rl(), _rl(), dict(GOOD)]})
    assert res["status"] == "done" and res["counts"]["rate_limit_waits"] == 2
    backoffs = [s for s in clock.sleeps if s >= mb.BACKOFF_START_SEC]
    assert backoffs == [mb.BACKOFF_START_SEC, mb.BACKOFF_START_SEC * 2]
    assert coll.docs["A"]["moat_status"] == "ok"


def test_backfill_stops_after_max_429_retries_and_RESUMES_where_it_stopped():
    coll = FakeColl([{"symbol": s} for s in ("A", "B", "C")])
    state, clock, calls = FakeColl(key="_id"), Clock(), []
    script = {"B": [_rl()] * (mb.MAX_RATE_LIMIT_RETRIES + 1) + [dict(GOOD)]}
    res = _run(coll, state, clock, script, calls)
    assert res["status"] == "rate_limited" and res["done"] is False
    assert res["processed"] == 1 and coll.docs["A"]["moat_status"] == "ok"
    assert "moat_status" not in coll.docs["B"]           # B stays owed, unmarked
    assert max(clock.sleeps) == mb.BACKOFF_MAX_SEC        # backoff capped
    first_pass = state.docs["moat_backfill:null"]["pass_started_at"]

    calls.clear()
    clock.t += 3600
    res2 = _run(coll, state, clock, script, calls)
    assert res2["resumed"] is True and res2["pass_started_at"] == first_pass
    assert calls == ["B", "C"]                            # A is NOT re-read
    assert res2["status"] == "done" and res2["done"] is True
    assert state.docs["moat_backfill:null"]["done"] is True


def test_backfill_time_budget_stops_and_resumes():
    coll = FakeColl([{"symbol": s} for s in "ABCDE"])
    state, clock, calls = FakeColl(key="_id"), Clock(), []
    res = _run(coll, state, clock, calls=calls, interval_sec=30.0, max_minutes=1.0)
    assert res["status"] == "budget" and res["done"] is False
    assert calls == ["A", "B", "C"]        # reads at t0, t0+30, t0+60 → budget hit at 4th
    calls.clear()
    res2 = _run(coll, state, clock, calls=calls)
    assert calls == ["D", "E"] and res2["done"] is True


def test_backfill_non_429_failure_is_marked_and_skipped_this_pass_only():
    coll = FakeColl([{"symbol": "A"}, {"symbol": "B"}])
    state, clock, calls = FakeColl(key="_id"), Clock(), []
    bad = moat_mod.MoatFetchError("A", "HTTP 500", rate_limited=False)
    res = _run(coll, state, clock, {"A": [bad]}, calls, limit=1)
    assert res["counts"]["failed"] == 1 and res["done"] is False   # limit left B owed
    assert coll.docs["A"]["moat_status"] == "fetch_failed"
    calls.clear()
    _run(coll, state, clock, {"A": [bad]}, calls)
    assert calls == ["B"]                                  # A not retried this pass
    calls.clear()
    clock.t += 10
    _run(coll, state, clock, {"A": [dict(GOOD)]}, calls, restart=True)
    assert calls == ["A"]                                  # a new pass retries it


def test_backfill_stops_when_yahoo_is_unreachable():
    n = mb.MAX_CONSECUTIVE_FAILURES + 5
    coll = FakeColl([{"symbol": f"S{i:03d}"} for i in range(n)])
    state, clock, calls = FakeColl(key="_id"), Clock(), []
    down = moat_mod.MoatFetchError("x", "connection refused", rate_limited=False)
    script = {f"S{i:03d}": [down] for i in range(n)}
    res = _run(coll, state, clock, script, calls)
    assert res["status"] == "unreachable"
    assert len(calls) == mb.MAX_CONSECUTIVE_FAILURES


def test_backfill_keeps_a_moat_on_a_zero_input_read():
    coll = FakeColl([{"symbol": "A", "moat": GOOD, "moat_as_of": T0 - 99}])
    state, clock = FakeColl(key="_id"), Clock()
    zero = {"score": 0.0, "label": "UNKNOWN", "tier": 0, "data_completeness": 0}
    res = _run(coll, state, clock, {"A": [zero]}, mode="refresh")
    assert res["counts"]["kept"] == 1
    assert coll.docs["A"]["moat"] == GOOD
    assert coll.docs["A"]["moat_status"] == "fetch_failed"


def test_resume_only_does_nothing_without_an_unfinished_pass():
    coll = FakeColl([{"symbol": "A"}])
    state, clock, calls = FakeColl(key="_id"), Clock(), []
    res = _run(coll, state, clock, calls=calls, mode="refresh", resume_only=True)
    assert res["status"] == "nothing_to_resume" and calls == []
    assert state.docs == {}


def test_refresh_mode_rereads_every_moat_oldest_first_and_keeps_its_symbol_filter():
    coll = FakeColl([
        {"symbol": "NEW", "moat": GOOD, "moat_as_of": T0 - 10},
        {"symbol": "OLD", "moat": GOOD, "moat_as_of": T0 - 10_000},
        {"symbol": "GONE", "moat": GOOD, "moat_as_of": T0 - 99_999},   # left the universe
    ])
    state, clock, calls = FakeColl(key="_id"), Clock(), []
    res = _run(coll, state, clock, calls=calls, mode="refresh",
               symbols=["NEW", "OLD"], limit=1, restart=True)
    assert calls == ["OLD"] and res["done"] is False
    calls.clear()
    _run(coll, state, clock, calls=calls, mode="refresh", resume_only=True)
    assert calls == ["NEW"]                                # GONE stays out on resume


def test_backfill_rejects_an_unknown_mode():
    with pytest.raises(ValueError):
        mb.run(FakeColl(), FakeColl(key="_id"), mode="all")


# ── CLI wiring ──────────────────────────────────────────────────────────────
def _cli(argv):
    from sepa import cli
    with mock.patch.object(sys, "argv", ["sepa.cli", *argv]):
        return cli.main()


def test_cli_research_refresh_runs_moat_sequentially_after_the_threads():
    with mock.patch.object(research, "refresh_universe",
                           return_value={"refreshed": ["A", "B"], "failed": [],
                                         "duration_sec": 1.0}) as ru, \
         mock.patch("sepa.universe.load_universe", return_value=["A", "B", "Z"]), \
         mock.patch.object(mb, "run_default", return_value={}) as rd:
        assert _cli(["research-refresh", "--mode", "broad"]) == 0
    assert ru.call_args.kwargs["with_moat"] is False
    rd.assert_called_once()
    kw = rd.call_args.kwargs
    assert kw["mode"] == "refresh" and kw["restart"] is True and kw["symbols"] == ["A", "B"]


def test_cli_adhoc_symbols_and_no_canslim_skip_the_moat_pass():
    for argv, with_moat in ((["--symbols", "A"], True), (["--no-canslim"], True),
                            (["--skip-moat-pass"], True)):
        with mock.patch.object(research, "refresh_universe",
                               return_value={"refreshed": ["A"], "failed": [],
                                             "duration_sec": 1.0}) as ru, \
             mock.patch("sepa.universe.load_universe", return_value=["A"]), \
             mock.patch.object(mb, "run_default") as rd:
            assert _cli(["research-refresh", *argv]) == 0
        assert ru.call_args.kwargs["with_moat"] is with_moat, argv
        rd.assert_not_called()


def test_cli_catchup_skip_still_resumes_an_unfinished_moat_pass():
    with mock.patch.object(research, "needs_refresh", return_value=(False, "healthy")), \
         mock.patch.object(research, "refresh_universe") as ru, \
         mock.patch.object(mb, "run_default", return_value={}) as rd:
        assert _cli(["research-refresh", "--only-if-stale"]) == 0
    ru.assert_not_called()
    assert rd.call_args.kwargs["resume_only"] is True


def test_cli_moat_backfill_exit_codes():
    for status, code in (("done", 0), ("budget", 0), ("nothing_to_resume", 0),
                         ("rate_limited", 2), ("unreachable", 2), ("no_mongo", 2)):
        with mock.patch.object(mb, "run_default", return_value={"status": status}) as rd:
            assert _cli(["moat-backfill", "--symbols", "a, b", "--interval", "2"]) == code
        kw = rd.call_args.kwargs
        assert kw["symbols"] == ["A", "B"] and kw["interval_sec"] == 2.0
        assert kw["mode"] == "null"


# ── coverage census script ──────────────────────────────────────────────────
def _census_mod():
    path = Path(__file__).resolve().parents[1] / "scripts" / "moat_coverage.py"
    spec = importlib.util.spec_from_file_location("moat_coverage", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_coverage_census_counts():
    cov = _census_mod()
    now, day = T0, 86400
    docs = [
        {"cached_at": now - 1 * day, "moat": {"tier": 3, "data_completeness": 6},
         "moat_status": "ok", "moat_as_of": now - 2 * day},
        {"cached_at": now - 1 * day, "moat": None, "moat_status": "no_data"},
        {"cached_at": now - 1 * day},                                  # missing moat
        {"cached_at": now - 30 * day, "moat": {"tier": 0, "data_completeness": 0}},
        {"moat": "WIDE"},                       # not a dict, no cached_at → null, stale
        {"cached_at": now - 1 * day, "moat": {"tier": 2}, "moat_as_of": now - 10 * day,
         "moat_status": "weird"},
    ]
    r = cov.census(docs, now=now, since=now - 2 * day, ttl_sec=16 * day)
    assert r["all"] == {"docs": 6, "moat_present": 3, "moat_scored": 2, "moat_null": 3,
                        "moat_null_pct": 50.0, "moat_scored_pct": 33.3}
    assert r["fresh"]["docs"] == 4 and r["fresh"]["moat_present"] == 2
    assert r["fresh"]["moat_scored"] == 2
    assert r["stale"]["moat_scored"] == 0          # the tier-0 dict is present, NOT scored
    assert r["stale"]["docs"] == 2 and r["stale"]["moat_present"] == 1
    assert r["refreshed_since"]["docs"] == 4
    assert r["present_unknown_tier0"] == 1 and r["present_zero_inputs"] == 1
    assert r["moat_status"] == {"ok": 1, "no_data": 1, "fetch_failed": 0, "legacy_unset": 4}
    assert r["moat_value_age"] == {"le_7d": 1, "le_16d": 1, "gt_16d": 0, "unstamped": 1}


def test_coverage_census_empty():
    r = _census_mod().census([], now=T0, since=T0, ttl_sec=1)
    assert r["all"] == {"docs": 0, "moat_present": 0, "moat_scored": 0, "moat_null": 0,
                        "moat_null_pct": None, "moat_scored_pct": None}


def test_coverage_census_tier_shapes_that_must_not_count_as_scored():
    r = _census_mod().census([
        {"cached_at": T0, "moat": {"tier": "3"}},          # string tier
        {"cached_at": T0, "moat": {"tier": None}},
        {"cached_at": T0, "moat": {}},
        {"cached_at": T0, "moat": {"tier": 1}},
    ], now=T0, since=T0, ttl_sec=10)
    assert r["all"]["moat_present"] == 4 and r["all"]["moat_scored"] == 1
