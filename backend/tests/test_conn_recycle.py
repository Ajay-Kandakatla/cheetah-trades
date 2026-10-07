"""Connection hygiene (2026-10-06): we close idle provider connections first.

Docker Desktop's gvisor forwarder never retires a flow the REMOTE side closes
first; the api's idle keep-alive sockets were exactly that (~14,750 stale
entries after 10.5 days, 2026-10-05). These tests pin the three tools in
``backend/http_hygiene.py``'s docstring:

  * ``sepa.prices._http()`` recycles its per-thread Session (idle 20 s, age
    600 s, reaper every 5 s) — A1..A13;
  * the finnhub per-loop httpx client keeps no idle connection and short-lived
    loops close it (chart_maps/ipo) — A14..A19;
  * main.py's AsyncClients carry ``limits=`` and yfinance forbids reuse —
    A20..A26.

No network: the loopback server below binds 127.0.0.1:0 (works under
``docker run --network none``).
"""
from __future__ import annotations

import asyncio
import http.server
import re
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import http_hygiene                                       # noqa: E402
from sepa import prices                                   # noqa: E402
from finnhub_client import client as FH                   # noqa: E402
from chart_maps import ipo as IPO                         # noqa: E402

_REAL_ENSURE_REAPER = prices._ensure_reaper
_REAL_NEW_SESSION = prices._new_session


# ── fixtures / helpers ───────────────────────────────────────────────────────

class Clock:
    def __init__(self, t: float = 0.0):
        self.t = t

    def __call__(self) -> float:
        return self.t


class StubSess:
    def __init__(self, clock: Clock):
        self.clock = clock
        self.gets = 0
        self.closes = 0
        self.closed_at: list = []
        self.raise_on_get = None

    def get(self, url, **kw):
        self.gets += 1
        if self.raise_on_get is not None:
            raise self.raise_on_get
        return SimpleNamespace(status_code=200, url=url)

    def close(self):
        self.closes += 1
        self.closed_at.append(self.clock.t)


def _isolate(monkeypatch) -> Clock:
    clock = Clock(0.0)
    monkeypatch.setattr(prices, "_POOLS", [])
    monkeypatch.setattr(prices, "_HTTP", threading.local())
    monkeypatch.setattr(prices, "_ensure_reaper", lambda: None)
    monkeypatch.setattr(prices, "_now", clock)
    return clock


@pytest.fixture
def pooled_env(monkeypatch):
    clock = _isolate(monkeypatch)
    made: list = []
    state = {"raise": None}

    def factory():
        s = StubSess(clock)
        s.raise_on_get = state["raise"]
        made.append(s)
        return s

    monkeypatch.setattr(prices, "_new_session", factory)
    return SimpleNamespace(clock=clock, made=made, state=state)


@pytest.fixture
def real_session_env(monkeypatch):
    """Same isolation, but prices._new_session is the REAL requests.Session."""
    return SimpleNamespace(clock=_isolate(monkeypatch))


def _server():
    """ThreadingHTTPServer on 127.0.0.1:0 with HTTP/1.1 keep-alive. Records each
    connection open (setup) and close (finish) — see scratchpad probe.py."""
    opened: list = []
    closed: list = []

    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            opened.append(time.monotonic())
            super().setup()

        def do_GET(self):
            b = b"ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def finish(self):
            closed.append(time.monotonic())
            super().finish()

        def log_message(self, *a):
            pass

    class S(http.server.ThreadingHTTPServer):
        daemon_threads = True

    srv = S(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/x"
    return SimpleNamespace(srv=srv, url=url, opened=opened, closed=closed)


@pytest.fixture
def server():
    s = _server()
    yield s
    s.srv.shutdown()
    s.srv.server_close()


def _saw(pred, within: float = 2.0) -> bool:
    end = time.monotonic() + within
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.02)
    return pred()


def _arun(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


# ── prices._Pooled ───────────────────────────────────────────────────────────

def test_NEGATIVE_two_gets_19_9s_apart_reuse_one_session(pooled_env):
    p = prices._http()
    p.get("https://a")
    pooled_env.clock.t = 19.9
    p.get("https://a")
    assert len(pooled_env.made) == 1
    assert pooled_env.made[0].gets == 2
    assert pooled_env.made[0].closes == 0


def test_gets_20_1s_apart_recycle_exactly_once(pooled_env):
    p = prices._http()
    p.get("https://a")
    pooled_env.clock.t = 20.1
    p.get("https://a")
    old, new = pooled_env.made
    assert old.closes == 1 and old.gets == 1
    assert new.gets == 1 and new.closes == 0


def test_max_age_recycles_a_busy_session_once_at_600s(pooled_env):
    p = prices._http()
    for t in range(0, 611, 10):
        pooled_env.clock.t = float(t)
        p.get("https://a")
    closes = sum(s.closes for s in pooled_env.made)
    assert closes == 1
    assert pooled_env.made[0].closed_at == [600.0]
    assert len(pooled_env.made) == 2


def test_reap_once_closes_an_idle_session_once(pooled_env):
    p = prices._http()
    p.get("https://a")
    assert prices._reap_once(p.last + 21) == 1
    assert prices._reap_once(p.last + 21) == 0, "a closed pool is not closed again"
    assert pooled_env.made[0].closes == 1


def test_NEGATIVE_reaper_leaves_a_warm_session(pooled_env):
    p = prices._http()
    p.get("https://a")
    assert prices._reap_once(p.last + 19) == 0
    assert pooled_env.made[0].closes == 0
    assert p.sess is pooled_env.made[0]


def test_NEGATIVE_reaper_skips_a_busy_pool(pooled_env):
    p = prices._http()
    p.get("https://a")
    with p.lock:
        assert prices._reap_once(p.last + 999) == 0
    assert pooled_env.made[0].closes == 0
    assert p in prices._POOLS


def test_dead_thread_pool_is_closed_and_dropped(pooled_env):
    box: list = []

    def work():
        q = prices._http()
        q.get("https://a")
        box.append(q)

    t = threading.Thread(target=work)
    t.start()
    t.join()
    mine = prices._http()
    mine.get("https://a")
    dead = box[0]
    assert dead in prices._POOLS and mine in prices._POOLS

    assert prices._reap_once(21.0) == 2
    assert dead not in prices._POOLS, "a dead thread's closed pool is dropped"
    assert mine in prices._POOLS, "a live thread's pool stays registered"
    assert all(s.closes == 1 for s in pooled_env.made)


def test_one_pool_per_thread(pooled_env):
    a, b = prices._http(), prices._http()
    assert a is b
    other: list = []
    t = threading.Thread(target=lambda: other.append(prices._http()))
    t.start()
    t.join()
    assert other[0] is not a
    assert len(prices._POOLS) == 2


def test_failed_get_closes_and_reraises(pooled_env):
    pooled_env.state["raise"] = ConnectionError("reset")
    p = prices._http()
    with pytest.raises(ConnectionError):
        p.get("https://a")
    assert pooled_env.made[0].closes == 1
    assert p.sess is None
    pooled_env.state["raise"] = None
    p.get("https://a")
    assert len(pooled_env.made) == 2
    assert pooled_env.made[1].gets == 1


def test_NEGATIVE_stream_true_is_refused(pooled_env):
    p = prices._http()
    with pytest.raises(ValueError):
        p.get("https://a", stream=True)
    assert pooled_env.made == [], "_new_session is never called for a refused stream"


def test_loopback_real_session_reuses_then_reaper_sends_our_FIN(real_session_env, server):
    p = prices._http()
    r1 = p.get(server.url, timeout=5)
    r2 = p.get(server.url, timeout=5)
    assert r1.status_code == 200 and r2.status_code == 200
    time.sleep(0.3)
    assert len(server.opened) == 1, "two gets ride ONE kept-alive connection"
    assert server.closed == [], "the warm session holds its socket open"

    # A live Response keeps a makefile() reference to the socket, so the fd
    # only really closes once callers drop it (they do: every caller reads
    # .json() and returns). Drop ours as a caller would.
    del r1, r2
    assert prices._reap_once(prices._now() + 21) == 1
    assert _saw(lambda: len(server.closed) == 1), "the reaper closed it: OUR FIN"


def test_ensure_reaper_starts_exactly_one_daemon_thread(monkeypatch):
    started: list = []

    class StubThread:
        def __init__(self, target=None, name=None, daemon=None, **kw):
            self.target, self.name, self.daemon = target, name, daemon

        def start(self):
            started.append(self)

    monkeypatch.setattr(prices, "_REAPER_STARTED", False)
    monkeypatch.setattr(prices.threading, "Thread", StubThread)
    for _ in range(3):
        _REAL_ENSURE_REAPER()
    assert len(started) == 1
    assert started[0].daemon is True
    assert started[0].name == "prices-http-reaper"


def test_constants_are_the_reviewed_values():
    assert prices.IDLE_RECYCLE_SEC == 20.0
    assert prices.MAX_AGE_SEC == 600.0
    assert prices.REAP_EVERY_SEC == 5.0
    assert prices.IDLE_RECYCLE_SEC > 15, "the live_feed poller (15 s) stays warm"
    assert prices.IDLE_RECYCLE_SEC + prices.REAP_EVERY_SEC < 60, \
        "we close before a 60 s provider idle timeout"


# ── finnhub and IPO ──────────────────────────────────────────────────────────

def test_finnhub_client_keeps_no_idle_connection():
    async def go():
        c = await FH._get_http()
        try:
            return c._transport._pool._max_keepalive_connections
        finally:
            await FH.aclose_loop_client()

    assert _arun(go()) == 0


def test_finnhub_client_loopback_closes_after_response(server):
    async def go():
        c = await FH._get_http()
        try:
            r = await c.get(server.url)
            return r.status_code, len(c._transport._pool.connections)
        finally:
            await FH.aclose_loop_client()

    n0 = len(server.closed)
    status, pooled = _arun(go())
    assert status == 200
    assert pooled == 0, "no connection is kept after the response"
    assert _saw(lambda: len(server.closed) > n0), "server saw OUR close"


def test_aclose_loop_client_closes_and_forgets():
    async def go():
        c = await FH._get_http()
        loop = asyncio.get_event_loop()
        assert loop in FH._http_by_loop
        await FH.aclose_loop_client()
        out = (c.is_closed, loop in FH._http_by_loop)
        await FH.aclose_loop_client()          # NEG: second call is a no-op
        return out + (loop in FH._http_by_loop,)

    closed, still_mapped, mapped_after_second = _arun(go())
    assert closed is True
    assert still_mapped is False
    assert mapped_after_second is False


def test_ipo_calendar_closes_its_loop_client(monkeypatch):
    seen: dict = {}

    async def stub(frm, to):
        seen["client"] = await FH._get_http()
        seen["loop"] = asyncio.get_event_loop()
        return []

    monkeypatch.setattr(FH, "ipo_calendar", stub)
    try:
        out = IPO.calendar("2026-01-01", "2026-01-05")
    finally:
        asyncio.set_event_loop(asyncio.new_event_loop())
    assert out["ok"] is True
    assert seen["client"].is_closed is True
    assert seen["loop"] not in FH._http_by_loop


def test_NEGATIVE_fetch_windows_without_aclose_still_returns():
    async def stub(frm, to):
        return [{"symbol": "X", "date": frm}]

    fh = SimpleNamespace(ipo_calendar=stub)
    out = _arun(IPO._fetch_windows(fh, [("2026-01-01", "2026-01-05")]))
    assert out == [("2026-01-01", "2026-01-05", [{"symbol": "X", "date": "2026-01-01"}], None)]


def test_NEGATIVE_aclose_failure_does_not_lose_results():
    async def stub(frm, to):
        return [{"symbol": "Y"}]

    async def boom():
        raise RuntimeError("close failed")

    fh = SimpleNamespace(ipo_calendar=stub, aclose_loop_client=boom)
    out = _arun(IPO._fetch_windows(fh, [("a", "b"), ("c", "d")]))
    assert [o[2] for o in out] == [[{"symbol": "Y"}], [{"symbol": "Y"}]]


# ── main.py guards and http_hygiene ──────────────────────────────────────────

def _asyncclients_without_limits(src: str) -> list:
    """Every `httpx.AsyncClient(` call not opened by `with ` on its line whose
    argument list (balanced parens) has no `limits=`."""
    bad = []
    for m in re.finditer(r"httpx\.AsyncClient\(", src):
        line_start = src.rfind("\n", 0, m.start()) + 1
        if "with " in src[line_start:m.start()]:
            continue
        depth, i = 1, m.end()
        while i < len(src) and depth:
            depth += {"(": 1, ")": -1}.get(src[i], 0)
            i += 1
        if "limits=" not in src[m.end():i]:
            bad.append(src[line_start:src.find("\n", m.start())].strip())
    return bad


def test_every_long_lived_asyncclient_has_limits():
    for rel in ("main.py", "finnhub_client/client.py"):
        src = (BACKEND / rel).read_text()
        assert _asyncclients_without_limits(src) == [], rel
    assert (BACKEND / "main.py").read_text().count("limits=http_hygiene.NO_KEEPALIVE") >= 4

    sample = "x = httpx.AsyncClient(timeout=10)\n"
    assert _asyncclients_without_limits(sample) == ["x = httpx.AsyncClient(timeout=10)"]
    assert _asyncclients_without_limits("y = httpx.AsyncClient(timeout=f(1), limits=L)\n") == []
    assert _asyncclients_without_limits("    async with httpx.AsyncClient(timeout=5) as c:\n") == []


def test_no_keepalive_limits_values():
    assert http_hygiene.NO_KEEPALIVE.max_keepalive_connections == 0
    assert http_hygiene.NO_KEEPALIVE.max_connections == 100


def test_yfinance_session_forbids_reuse(monkeypatch):
    from curl_cffi import CurlOpt
    import yfinance.data as yfd

    monkeypatch.setattr(http_hygiene, "_YF_INSTALLED", False)
    assert http_hygiene.install_yfinance_no_reuse() is True
    first = yfd.YfData()._session
    assert http_hygiene.install_yfinance_no_reuse() is True
    assert yfd.YfData()._session is first, "idempotent: no second swap"
    assert yfd.YfData()._session.curl_options[CurlOpt.FORBID_REUSE] == 1


def test_yfinance_loopback_closes_after_transfer(monkeypatch, server):
    import yfinance.data as yfd

    monkeypatch.setattr(http_hygiene, "_YF_INSTALLED", False)
    assert http_hygiene.install_yfinance_no_reuse() is True
    n0 = len(server.closed)
    r = yfd.YfData()._session.get(server.url, timeout=5)
    assert r.status_code == 200
    assert _saw(lambda: len(server.closed) > n0), "libcurl closed after the transfer"


def test_NEGATIVE_install_without_yfinance_returns_false(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance.data", None)
    monkeypatch.setitem(sys.modules, "yfinance", None)
    monkeypatch.setattr(http_hygiene, "_YF_INSTALLED", False)
    assert http_hygiene.install_yfinance_no_reuse() is False
    assert http_hygiene._YF_INSTALLED is False


def test_main_installs_before_the_first_sepa_import():
    lines = (BACKEND / "main.py").read_text().splitlines()
    install = next(i for i, l in enumerate(lines)
                   if l.strip() == "http_hygiene.install_yfinance_no_reuse()")
    first_sepa = next(i for i, l in enumerate(lines)
                      if re.match(r"\s*(from sepa\b|import sepa\b)", l))
    assert install < first_sepa


def test_NEGATIVE_prices_has_no_bare_thread_session_left():
    src = (BACKEND / "sepa" / "prices.py").read_text()
    assert "_HTTP.session =" not in src
    assert "_HTTP.pooled = _Pooled()" in src
