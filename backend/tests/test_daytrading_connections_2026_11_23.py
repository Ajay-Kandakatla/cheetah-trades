"""🔌 daytrading/data.py connections (spec ggconn 2026-11-23 §3.3 / WP-4).

Ajay 2026-11-23: "Can you clean up some connection I am seeing delays price update for AKAN on the watch chart..".

  * the minute fetch reads through ONE seam, `D._http_get` = `sepa.prices._http().get` (the recycled keep-alive
    session, http_hygiene tool 3) — no bare `requests.get` any more;
  * tests/conftest.py assigns a `MinuteFetchRefused` (a BaseException) refuser to that seam for the whole session;
  * the non-200 log line scrubs the key like the exception line;
  * `new_breaker()` + an optional `cb` on the breaker / fetch / `load_intraday` — a caller's OWN breaker, the module
    `_CB` untouched (the 👀 Watch loader consumes it, WP-3);
  * ONE Mongo client per process for the prior-day cache.

No network, no Mongo: every outside call is a fake.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from daytrading import data as D
from observability import logsetup as L
from sepa import prices
from tests.test_daytrading_data_et_today import _R, _bars_payload

DAY = date(2026, 11, 20)
KEY = "SUPERSECRETKEYVALUE123"
BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    D._CB["fails"] = 0
    D._CB["open_until"] = 0.0
    D.clear_fetch_failed()
    D._reset_mongo()
    monkeypatch.setattr(D, "stocks_key", lambda: "k")
    yield
    D._CB["fails"] = 0
    D._CB["open_until"] = 0.0
    D.clear_fetch_failed()
    D._reset_mongo()


def _url(sym="AAA", day=DAY):
    return f"{D.BASE_URL}/v2/aggs/ticker/{sym}/range/1/minute/{day}/{day}"


def _recorder(seq=None):
    calls = []

    def get(url, **kw):
        calls.append((url, kw))
        if seq is not None:
            return seq.pop(0)
        return _R(200, _bars_payload())
    return get, calls


# ── the seam ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_fetch_reads_through_the_seam_with_the_same_url_params_timeout_page_2_too(monkeypatch):
    page1 = dict(_bars_payload(), next_url="https://api.massive.com/next")
    get, calls = _recorder([_R(200, page1), _R(200, _bars_payload())])
    monkeypatch.setattr(D, "_http_get", get)
    out = D._fetch_massive_minute("aaa", DAY, DAY)
    assert out is not None and len(out) == 2
    assert calls == [
        (_url(), {"params": {"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": "k"},
                  "timeout": D._FETCH_TIMEOUT_SEC}),
        ("https://api.massive.com/next", {"params": {"apiKey": "k"}, "timeout": D._FETCH_TIMEOUT_SEC}),
    ]


def test_NEGATIVE_the_module_source_has_no_bare_requests_get():
    src = inspect.getsource(D)
    assert "requests.get(" not in src
    assert "import requests" not in src
    assert "_http_get(next_url, params=next_params, timeout=_FETCH_TIMEOUT_SEC)" in inspect.getsource(
        D._fetch_massive_minute)


def test_the_real_seam_hands_to_prices_http_get(monkeypatch):
    real = D._http_get.__wrapped__
    seen = []
    monkeypatch.setattr(prices, "_http", lambda: SimpleNamespace(get=lambda url, **kw: seen.append((url, kw)) or "R"))
    assert real("https://x.test/a", params={"p": 1}, timeout=6) == "R"
    assert seen == [("https://x.test/a", {"params": {"p": 1}, "timeout": 6})]


def test_the_real_seam_builds_one_session_per_thread(monkeypatch):
    made = []

    class Sess:
        def get(self, url, **kw):
            return _R(200, _bars_payload())

        def close(self):
            pass

    def factory():
        made.append(threading.current_thread().name)
        return Sess()
    monkeypatch.setattr(prices, "_POOLS", [])
    monkeypatch.setattr(prices, "_HTTP", threading.local())
    monkeypatch.setattr(prices, "_ensure_reaper", lambda: None)
    monkeypatch.setattr(prices, "_new_session", factory)
    monkeypatch.setattr(D, "_http_get", D._http_get.__wrapped__)          # the REAL seam, for this test only
    assert D._fetch_massive_minute("AAA", DAY, DAY) is not None
    assert D._fetch_massive_minute("BBB", DAY, DAY) is not None
    assert len(made) == 1                                                  # two fetches, one thread → ONE session
    res = []
    ts = [threading.Thread(target=lambda: res.append(D._fetch_massive_minute("CCC", DAY, DAY) is not None))
          for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert res == [True, True] and len(made) == 3                          # two more threads → two more sessions


# ── the test-session guard (tests/conftest.py, critique C4) ──────────────────────────────────────────────────────────
def test_NEGATIVE_a_key_and_no_stub_raises_MinuteFetchRefused_and_never_touches_the_breaker(monkeypatch, caplog):
    monkeypatch.setattr(D, "stocks_key", lambda: KEY)
    assert D._http_get.__name__ == "_refuse_minute"
    with caplog.at_level(logging.DEBUG, logger="daytrading.data"):
        with pytest.raises(BaseException) as ei:
            D._fetch_massive_minute("AAA", DAY, DAY)
    assert type(ei.value).__name__ == "MinuteFetchRefused"
    assert not isinstance(ei.value, Exception)                             # the fetch's `except Exception` misses it
    assert D._CB == {"fails": 0, "open_until": 0.0}
    assert KEY not in caplog.text and KEY not in str(ei.value)
    assert not [r for r in caplog.records if "intraday fetch failed" in r.getMessage()]


def test_NEGATIVE_the_refusal_reaches_the_caller_through_a_worker_future(monkeypatch):
    monkeypatch.setattr(D, "stocks_key", lambda: KEY)
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut = ex.submit(D._fetch_massive_minute, "AAA", DAY, DAY)
        with pytest.raises(BaseException) as ei:
            fut.result()
    assert type(ei.value).__name__ == "MinuteFetchRefused" and D._CB["fails"] == 0


def test_a_function_scope_stub_wins_and_the_refuser_is_back_after_undo():
    refuser = D._http_get
    mp = pytest.MonkeyPatch()
    get, calls = _recorder()
    mp.setattr(D, "_http_get", get)
    try:
        assert D._fetch_massive_minute("AAA", DAY, DAY) is not None and len(calls) == 1
    finally:
        mp.undo()
    assert D._http_get is refuser and D._http_get.__name__ == "_refuse_minute"


def test_the_wrapped_real_seam_is_callable_and_is_not_the_refuser():
    real = D._http_get.__wrapped__
    assert callable(real) and real is not D._http_get
    assert real.__name__ == "_http_get" and real.__module__ == "daytrading.data"


# ── failures: None, flagged, counted, the key never logged ───────────────────────────────────────────────────────────
class _Cap(logging.Handler):
    def __init__(self, redact: bool):
        super().__init__()
        self.lines = []
        if redact:
            self.addFilter(L.RedactFilter())

    def emit(self, record):
        self.lines.append(self.format(record))


@pytest.mark.parametrize("redact", [False, True], ids=["no_filter", "redact_filter"])
def test_NEGATIVE_a_raising_get_returns_none_flags_one_failure_and_logs_no_key(monkeypatch, redact):
    monkeypatch.setattr(D, "stocks_key", lambda: KEY)

    def boom(url, **kw):
        raise RuntimeError(f"HTTPSConnectionPool(host='api.massive.com'): Max retries exceeded with url: "
                           f"/v2/aggs/ticker/AAA?adjusted=true&apiKey={KEY} (Caused by ReadTimeoutError)")
    monkeypatch.setattr(D, "_http_get", boom)
    cap = _Cap(redact)
    lg = logging.getLogger("daytrading.data")
    lg.addHandler(cap)
    try:
        assert D._fetch_massive_minute("AAA", DAY, DAY) is None
    finally:
        lg.removeHandler(cap)
    assert D.last_fetch_failed() is True and D._CB["fails"] == 1
    assert cap.lines and all(KEY not in x for x in cap.lines)
    assert any("apiKey=<redacted>" in x for x in cap.lines)


def test_NEGATIVE_a_non_200_body_echoing_the_key_is_scrubbed(monkeypatch):
    monkeypatch.setattr(D, "stocks_key", lambda: KEY)
    bad = _R(403)
    bad.text = f'{{"error": "bad request", "request_url": "/v2/aggs?apiKey={KEY}"}}'
    monkeypatch.setattr(D, "_http_get", lambda url, **kw: bad)
    cap = _Cap(False)
    lg = logging.getLogger("daytrading.data")
    lg.addHandler(cap)
    try:
        assert D._fetch_massive_minute("AAA", DAY, DAY) is None
    finally:
        lg.removeHandler(cap)
    assert D.last_fetch_failed() is True and D._CB["fails"] == 1
    assert [x for x in cap.lines if "HTTP 403" in x]
    assert all(KEY not in x for x in cap.lines) and any("apiKey=<redacted>" in x for x in cap.lines)


def test_NEGATIVE_an_empty_200_is_not_a_provider_failure(monkeypatch):
    monkeypatch.setattr(D, "_http_get", lambda url, **kw: _R(200, {"results": []}))
    D._CB["fails"] = 2
    assert D._fetch_massive_minute("AAA", DAY, DAY) is None
    assert D.last_fetch_failed() is False and D._CB["fails"] == 0


# ── a caller's own breaker ───────────────────────────────────────────────────────────────────────────────────────────
def test_new_breaker_is_a_new_closed_dict_each_call_and_never_the_module_one():
    a, b = D.new_breaker(), D.new_breaker()
    assert a == {"fails": 0, "open_until": 0.0} == b
    assert a is not b and a is not D._CB and b is not D._CB
    a["fails"] = 5
    assert D.new_breaker()["fails"] == 0 and D._CB["fails"] == 0


def test_three_failures_on_cb_open_it_for_the_cooldown_and_leave_the_module_breaker_closed():
    cb, now = D.new_breaker(), 1000.0
    for _ in range(D._CB_TRIP_AFTER - 1):
        D._cb_record(False, now, cb)
    assert not D._cb_is_open(now, cb)
    D._cb_record(False, now, cb)
    assert D._cb_is_open(now, cb) and D._cb_is_open(now + D._CB_COOLDOWN_SEC - 1, cb)
    assert not D._cb_is_open(now + D._CB_COOLDOWN_SEC + 1, cb)
    assert D._CB == {"fails": 0, "open_until": 0.0} and not D._cb_is_open(now)


def test_NEGATIVE_three_failures_on_the_default_open_the_module_breaker_and_leave_cb_closed():
    cb, now = D.new_breaker(), 2000.0
    for _ in range(D._CB_TRIP_AFTER):
        D._cb_record(False, now)
    assert D._cb_is_open(now) and D._CB["open_until"] == now + D._CB_COOLDOWN_SEC
    assert cb == {"fails": 0, "open_until": 0.0} and not D._cb_is_open(now, cb)


def test_NEGATIVE_a_success_resets_only_its_own_breaker():
    cb, now = D.new_breaker(), 3000.0
    for _ in range(D._CB_TRIP_AFTER):
        D._cb_record(False, now)
        D._cb_record(False, now, cb)
    D._cb_record(True, now, cb)
    assert not D._cb_is_open(now, cb) and cb["fails"] == 0
    assert D._cb_is_open(now) and D._CB["fails"] == D._CB_TRIP_AFTER
    D._cb_record(False, now, cb)
    D._cb_record(True, now)
    assert not D._cb_is_open(now) and cb["fails"] == 1


def test_module_breaker_open_and_own_breaker_closed_the_fetch_does_call_the_provider(monkeypatch):
    D._CB["open_until"] = D.time.time() + 60
    get, calls = _recorder()
    monkeypatch.setattr(D, "_http_get", get)
    cb = D.new_breaker()
    assert D._fetch_massive_minute("AAA", DAY, DAY, cb=cb) is not None and len(calls) == 1
    assert D.last_fetch_failed() is False
    assert D._CB["open_until"] > D.time.time()                             # the module breaker is not reset by it


def test_NEGATIVE_own_breaker_open_and_module_closed_no_provider_call(monkeypatch):
    cb = D.new_breaker()
    cb["open_until"] = D.time.time() + 60
    monkeypatch.setattr(D, "_http_get", lambda *a, **k: pytest.fail("own breaker open: no call"))
    assert D._fetch_massive_minute("AAA", DAY, DAY, cb=cb) is None and D.last_fetch_failed() is True
    assert D._CB == {"fails": 0, "open_until": 0.0}


def test_NEGATIVE_a_failure_with_cb_counts_on_cb_only_and_without_on_the_module_only(monkeypatch):
    def boom(url, **kw):
        raise ConnectionError("down")
    monkeypatch.setattr(D, "_http_get", boom)
    cb = D.new_breaker()
    for _ in range(D._CB_TRIP_AFTER):
        assert D._fetch_massive_minute("AAA", DAY, DAY, cb=cb) is None
    assert cb["fails"] == D._CB_TRIP_AFTER and D._cb_is_open(D.time.time(), cb)
    assert D._CB == {"fails": 0, "open_until": 0.0}
    assert D._fetch_massive_minute("AAA", DAY, DAY) is None
    assert D._CB["fails"] == 1 and cb["fails"] == D._CB_TRIP_AFTER


# ── load_intraday(cb=) ───────────────────────────────────────────────────────────────────────────────────────────────
def _frame():
    return D.pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1.0],
                           "session": ["rth"]}, index=D.pd.DatetimeIndex(["2026-11-20 15:00"], name="ts_utc"))


def _no_cache(monkeypatch):
    monkeypatch.setattr(D, "_mongo_get_day", lambda sym, day: None)
    monkeypatch.setattr(D, "_mongo_put_day", lambda sym, day, df: None)


def test_load_intraday_without_cb_calls_the_fetch_with_exactly_three_positional_args(monkeypatch):
    _no_cache(monkeypatch)
    seen = []
    monkeypatch.setattr(D, "_fetch_massive_minute", lambda *a, **k: seen.append((a, k)) or _frame())
    assert D.load_intraday("AAA", DAY, force=True) is not None
    assert seen == [(("AAA", DAY, DAY), {})]
    monkeypatch.setattr(D, "_fetch_massive_minute", lambda s, a, b: _frame())      # every existing stub shape
    assert D.load_intraday("AAA", DAY, force=True) is not None


def test_load_intraday_with_cb_hands_it_to_the_fetch(monkeypatch):
    _no_cache(monkeypatch)
    seen = []
    monkeypatch.setattr(D, "_fetch_massive_minute", lambda *a, **k: seen.append((a, k)) or _frame())
    cb = D.new_breaker()
    assert D.load_intraday("AAA", DAY, force=True, cb=cb) is not None
    assert seen == [(("AAA", DAY, DAY), {"cb": cb})] and seen[0][1]["cb"] is cb


def test_NEGATIVE_load_intraday_range_takes_no_cb():
    assert "cb" not in inspect.signature(D.load_intraday_range).parameters
    assert "cb" in inspect.signature(D.load_intraday).parameters


# ── ONE Mongo client per process ─────────────────────────────────────────────────────────────────────────────────────
class _FakeMongo:
    def __init__(self, fail_index=False, gate=None):
        self.built = []
        self.indexes = 0
        self.closed = 0
        self.fail_index = fail_index
        self.gate = gate
        self.docs = {}
        fm = self

        class Coll:
            def create_index(self, keys, unique=False):
                fm.indexes += 1
                if fm.fail_index:
                    raise RuntimeError("index boom")

            def find_one(self, q):
                return fm.docs.get((q["symbol"], q["date"]))

            def update_one(self, q, u, upsert=False):
                fm.docs[(q["symbol"], q["date"])] = u["$set"]

        class Client:
            def __init__(self, url, serverSelectionTimeoutMS=None):
                if fm.gate is not None:
                    fm.gate.wait(0.2)                          # widen the race window
                fm.built.append(url)
                self._coll = Coll()

            def __getitem__(self, db):
                return {"intraday_cache": self._coll}

            def close(self):
                fm.closed += 1
        self.Client = Client


@pytest.fixture
def fake_mongo(monkeypatch):
    import pymongo

    def install(**kw):
        fm = _FakeMongo(**kw)
        monkeypatch.setattr(pymongo, "MongoClient", fm.Client)
        return fm
    return install


def test_n_calls_build_one_client_and_one_index(fake_mongo):
    fm = fake_mongo()
    colls = [D._get_mongo_coll() for _ in range(5)]
    assert len(fm.built) == 1 and fm.indexes == 1 and fm.closed == 0
    assert all(c is colls[0] for c in colls)


def test_get_day_and_put_day_share_the_one_client(fake_mongo):
    fm = fake_mongo()
    D._mongo_put_day("AAA", DAY, _frame())
    got = D._mongo_get_day("AAA", DAY)
    assert got is not None and len(got) == 1
    assert len(fm.built) == 1 and fm.indexes == 1


def test_a_pid_change_rebuilds(fake_mongo):
    fm = fake_mongo()
    first = D._get_mongo_coll()
    D._MONGO["pid"] = -1                                           # the cache came from another process (a fork)
    second = D._get_mongo_coll()
    assert len(fm.built) == 2 and second is not first and D._MONGO["pid"] == D.os.getpid()


def test_NEGATIVE_a_failing_create_index_closes_the_client_caches_nothing_and_retries(fake_mongo):
    fm = fake_mongo(fail_index=True)
    assert D._get_mongo_coll() is None
    assert fm.closed == 1 and D._MONGO == {"pid": None, "coll": None}
    assert D._get_mongo_coll() is None
    assert len(fm.built) == 2 and fm.closed == 2                   # the next call tried again
    fm.fail_index = False
    assert D._get_mongo_coll() is not None and len(fm.built) == 3 and fm.closed == 2


def test_NEGATIVE_two_threads_racing_build_one_client(fake_mongo):
    gate = threading.Event()
    fm = fake_mongo(gate=gate)
    bar = threading.Barrier(2)
    got = []

    def go():
        bar.wait()
        got.append(D._get_mongo_coll())
    ts = [threading.Thread(target=go) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(fm.built) == 1 and len(got) == 2 and got[0] is got[1] is not None


def test_NEGATIVE_under_the_conftest_refuser_the_cache_is_none_as_before():
    assert D._get_mongo_coll() is None
    assert D._MONGO == {"pid": None, "coll": None}
    assert D._mongo_get_day("AAA", DAY) is None
    D._mongo_put_day("AAA", DAY, _frame())                          # no raise


def test_NEGATIVE_reset_mongo_forgets_the_cache(fake_mongo):
    fm = fake_mongo()
    D._get_mongo_coll()
    D._reset_mongo()
    D._get_mongo_coll()
    assert len(fm.built) == 2


# ── the read-only probe script ───────────────────────────────────────────────────────────────────────────────────────
def _probe():
    spec = importlib.util.spec_from_file_location("minute_fetch_cost_probe_t",
                                                  BACKEND / "scripts" / "minute_fetch_cost_probe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_probe_prints_one_dict_with_the_idle_gap_block(monkeypatch):
    M = _probe()
    monkeypatch.setattr(D, "stocks_key", lambda: KEY)
    get, calls = _recorder()
    monkeypatch.setattr(D, "_http_get", get)
    monkeypatch.setattr(M, "_bare_get", lambda url, **kw: _R(200, _bars_payload()))
    slept = []
    out = M.run(["AAA", "BBB", "CCC"], DAY, key=KEY, sleep=slept.append, n_conn=lambda: 3)
    assert set(out["sequential"]) == {"bare", "pooled", "real_fetch"} == set(out["threads8"])
    assert out["sequential"]["real_fetch"]["fail"] == 0 and out["threads8"]["pooled"]["fail"] == 0
    assert list(out["idle_gap"]) == ["5", "10", "15", f"{prices.IDLE_RECYCLE_SEC - 1:g}"]
    for g in out["idle_gap"].values():
        assert g["n"] == M.ROUNDS and g["fail"] == 0 and g["errs"] == [] and g["new_conn"] == [0] * M.ROUNDS
        assert isinstance(g["median_ms"], int)
    assert slept == [g for g in M.gaps() for _ in range(M.ROUNDS)]
    assert M.gaps()[-1] == prices.IDLE_RECYCLE_SEC - 1
    assert calls                                                     # the pooled + real paths went through the seam
    text = json.dumps(out, default=str)
    assert KEY not in text and "apiKey" not in text and "http" not in text.lower()


def test_NEGATIVE_the_probe_output_never_holds_the_key_when_every_get_raises_with_it(monkeypatch, capsys):
    M = _probe()
    monkeypatch.setattr(D, "stocks_key", lambda: KEY)
    import massive_keys
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: KEY)

    def boom(url, **kw):
        raise RuntimeError(f"Max retries exceeded with url: {url}?apiKey={kw['params']['apiKey']}")
    monkeypatch.setattr(D, "_http_get", boom)
    monkeypatch.setattr(M, "_bare_get", boom)
    monkeypatch.setattr(M.logging, "basicConfig", lambda **k: None)
    lg = logging.getLogger("daytrading.data")
    prior = lg.level
    try:
        assert M.main(["--symbols", "AAA,BBB", "--skip-idle"]) == 0
    finally:
        lg.setLevel(prior)
    cap = capsys.readouterr()
    lines = [x for x in cap.out.splitlines() if x.strip()]
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert out["sequential"]["bare"]["errs"] == ["RuntimeError"] and out["sequential"]["bare"]["fail"] == 4
    assert out["sequential"]["real_fetch"]["errs"] == ["provider_failed"]
    for blob in (cap.out, cap.err):
        assert KEY not in blob and "apiKey" not in blob


def test_NEGATIVE_the_probe_with_no_key_fetches_nothing(monkeypatch):
    M = _probe()
    monkeypatch.setattr(D, "_http_get", lambda *a, **k: pytest.fail("no key: no call"))
    monkeypatch.setattr(M, "_bare_get", lambda *a, **k: pytest.fail("no key: no call"))
    out = M.run(["AAA"], DAY, key="", sleep=lambda s: pytest.fail("no sleep"))
    assert out["key"] is False and out["skipped"] == "no key" and "idle_gap" not in out


def test_NEGATIVE_the_probe_source_writes_nothing():
    src = (BACKEND / "scripts" / "minute_fetch_cost_probe.py").read_text()
    for w in ("update_one", "update_many", "insert_one", "insert_many", "delete_one", "delete_many", "replace_one",
              "create_index", "live_feed", "import websocket"):
        assert w not in src, w
