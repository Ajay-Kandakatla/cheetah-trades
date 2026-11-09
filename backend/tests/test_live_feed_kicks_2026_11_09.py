"""GG LIVE WP-A (spec §3.1, 2026-11-09) — feed honesty on THE Massive socket: kicks, the yield guard, blind seconds,
lag, the dev guard, the served words and `/live/feed-status` (admin-only extras, the key never served).

Fake sockets only — no network. The consumer's reconnect wait goes through `live_feed._sleep`, which these tests
replace with a recorder that stops the loop.
"""
from __future__ import annotations

import ast
import asyncio
import json
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import live_feed

ET = ZoneInfo("America/New_York")
KEY = "SECRETKEY-test-123456"
MAIN_SRC = (Path(__file__).resolve().parents[1] / "main.py").read_text()


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    """Every run-time structure fresh (monkeypatch restores the module's own objects afterwards)."""
    monkeypatch.setattr(live_feed, "_events", deque(maxlen=live_feed.EVENTS_MAX))
    monkeypatch.setattr(live_feed, "_lag", deque(maxlen=live_feed.LAG_SAMPLES))
    monkeypatch.setattr(live_feed, "_msg_buckets", deque(maxlen=live_feed.MSG_RATE_WINDOW_SEC + 1))
    monkeypatch.setattr(live_feed, "_kick_times", deque(maxlen=live_feed.EVENTS_MAX))
    monkeypatch.setattr(live_feed, "_today", {"day": None, "kicks": 0, "blind_s": 0.0})
    monkeypatch.setattr(live_feed, "_link", {"conn_ts": None, "trades": 0, "kicked": False, "auth_ts": None,
                                             "drop_ts": None, "kick_pending": False, "yielding_wait": None,
                                             "last_kick_ts": None, "resume_s_last": None})
    monkeypatch.setattr(live_feed, "_listeners", [])
    monkeypatch.setattr(live_feed, "_views", {"tracked": None, "hub": None})
    monkeypatch.setattr(live_feed, "_queue", None)
    monkeypatch.setattr(live_feed, "_subscribed_t", set())
    monkeypatch.setattr(live_feed, "feed_state", dict(live_feed.feed_state, connected=False, authed=False,
                                                       trades=0, last_msg_ts=0.0, last_trade_ts=0.0,
                                                       reconnects=0, error=None))
    monkeypatch.setattr(live_feed, "_events_coll", lambda: None)
    monkeypatch.setenv("MASSIVE_API_KEY_STOCKS", KEY)
    monkeypatch.delenv("CHEETAH_ENV", raising=False)
    monkeypatch.setenv("MASSIVE_WS_ENABLED", "auto")
    yield


class _Stop(BaseException):
    pass


class _Closed(Exception):
    """websockets.ConnectionClosed shape: `rcvd.code`."""

    def __init__(self, code, reason=""):
        super().__init__(f"received {code} ({reason})")
        self.rcvd = type("Close", (), {"code": code, "reason": reason})()


class _FakeConn:
    def __init__(self, auth_frames, stream_frames, end_exc=None):
        self.auth_frames = list(auth_frames)
        self.stream_frames = list(stream_frames)
        self.end_exc = end_exc
        self.sent = []
        self.close_code = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def send(self, msg):
        self.sent.append(json.loads(msg))

    async def recv(self):
        if self.auth_frames:
            f = self.auth_frames.pop(0)
            if isinstance(f, BaseException):
                raise f
            return f
        await asyncio.sleep(10)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.stream_frames:
            return self.stream_frames.pop(0)
        if self.end_exc is not None:
            raise self.end_exc
        raise StopAsyncIteration


class _Cache:
    def __init__(self):
        self.calls = []

    async def update(self, sym, payload):
        self.calls.append((sym, dict(payload)))
        return payload


AUTH_OK = [json.dumps([{"ev": "status", "status": "connected", "message": "Connected Successfully"}]),
           json.dumps([{"ev": "status", "status": "auth_success", "message": "authenticated"}])]


def _run_consumer(monkeypatch, conns, tracked=None):
    waits = []
    it = iter(conns)

    def fake_connect(url, **kw):
        return next(it)

    async def fake_sleep(s):
        waits.append(s)
        raise _Stop()

    monkeypatch.setattr(live_feed.websockets, "connect", fake_connect)
    monkeypatch.setattr(live_feed, "_sleep", fake_sleep)

    async def go():
        q = asyncio.Queue()
        try:
            await live_feed.massive_ws_consumer(_Cache(), set(tracked or {"AAPL"}), q)
        except _Stop:
            pass

    asyncio.run(go())
    return waits


# ── defaults = today ────────────────────────────────────────────────────────────────────────────────────────────
def test_knob_defaults_are_todays_behaviour():
    assert live_feed._RECONNECT_COOLDOWN == 30.0
    assert live_feed.KICK_COOLDOWN_SEC == live_feed._RECONNECT_COOLDOWN
    assert live_feed.KICK_YIELD_AFTER_N is None
    assert live_feed.KICK_YIELD_WINDOW_SEC is None
    assert live_feed.KICK_YIELD_SEC is None
    assert live_feed.LIVE_FEED_EVENTS_TTL_DAYS == 14


# ── kicks ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_kick_status_then_1008_counts_one_kick_and_waits_the_kick_cooldown(monkeypatch):
    monkeypatch.setattr(live_feed, "KICK_COOLDOWN_SEC", 7.0)
    conn = _FakeConn(AUTH_OK, [
        json.dumps([{"ev": "T", "sym": "AAPL", "p": 1.0, "s": 100, "t": int(time.time() * 1000)}]),
        json.dumps([{"ev": "status", "status": "max_connections", "message": "Maximum number of websocket connections exceeded."}]),
    ], end_exc=_Closed(1008, "policy violation"))
    waits = _run_consumer(monkeypatch, [conn])
    assert waits == [7.0]
    st = live_feed.status_payload(tracked_n=1, admin=False, is_enabled=True)
    assert st["kicks_today"] == 1 and st["kicks_1h"] == 1
    assert st["state"] == "kicked"
    assert st["word"] == ("📡 Reconnecting — another connection on this Massive key took the stream (1 times today). "
                          "The 1-minute check keeps running.")
    assert st["last_kick_et"] and st["last_kick_age_s"] is not None
    kinds = [e["kind"] for e in live_feed._events]
    assert kinds == ["connect", "auth", "status", "close", "reconnect_wait"]      # "connected" is not a timeline row
    assert [e["status"] for e in live_feed._events if e["kind"] == "status"] == ["max_connections"]
    close = [e for e in live_feed._events if e["kind"] == "close"][0]
    assert close["close_code"] == 1008 and close["trades_in_conn"] == 1


def test_a_1008_close_alone_is_a_kick(monkeypatch):
    monkeypatch.setattr(live_feed, "KICK_COOLDOWN_SEC", 7.0)
    waits = _run_consumer(monkeypatch, [_FakeConn(AUTH_OK, [], end_exc=_Closed(1008))])
    assert waits == [7.0] and live_feed._today["kicks"] == 1


def test_NEG_a_1006_close_without_status_is_not_a_kick(monkeypatch):
    monkeypatch.setattr(live_feed, "KICK_COOLDOWN_SEC", 7.0)
    waits = _run_consumer(monkeypatch, [_FakeConn(AUTH_OK, [], end_exc=_Closed(1006, "abnormal"))])
    assert waits == [live_feed._RECONNECT_COOLDOWN]
    st = live_feed.status_payload(tracked_n=1, admin=False, is_enabled=True)
    assert st["kicks_today"] == 0 and st["state"] == "down"
    assert st["word"].startswith("📡 Live stream down (") and KEY not in st["word"]


def test_NEG_failed_connect_before_auth_keeps_the_exponential_backoff(monkeypatch):
    conn = _FakeConn([json.dumps([{"ev": "status", "status": "auth_failed", "message": "bad key"}])], [])
    waits = _run_consumer(monkeypatch, [conn])
    assert waits == [2] and live_feed._today["kicks"] == 0


def test_NEG_clean_close_that_is_not_a_kick_reconnects_at_once_like_today(monkeypatch):
    conn1 = _FakeConn(AUTH_OK, [])                                   # iterator ends cleanly
    conn2 = _FakeConn(AUTH_OK, [], end_exc=_Closed(1006))
    waits = _run_consumer(monkeypatch, [conn1, conn2])
    assert waits == [live_feed._RECONNECT_COOLDOWN]                   # no sleep after the clean close


def test_NEG_yield_guard_off_never_yields():
    for i in range(6):
        w = live_feed._on_drop(was_authed=True, exc_text="received 1008", close_code=1008, backoff=2, clean=False,
                               now=1000.0 + i)
        assert w == live_feed.KICK_COOLDOWN_SEC
    state, word = live_feed.state_word(1010.0, is_enabled=True)
    assert state == "kicked" and "not reclaiming" not in word and "(6 times today)" in word


def test_yield_guard_on_after_n_kicks_waits_the_yield_and_says_so(monkeypatch):
    monkeypatch.setattr(live_feed, "KICK_YIELD_AFTER_N", 3)
    monkeypatch.setattr(live_feed, "KICK_YIELD_WINDOW_SEC", 600.0)
    monkeypatch.setattr(live_feed, "KICK_YIELD_SEC", 900.0)
    waits = [live_feed._on_drop(was_authed=True, exc_text="", close_code=1008, backoff=2, clean=False,
                                now=5000.0 + 60 * i) for i in range(3)]
    assert waits == [live_feed.KICK_COOLDOWN_SEC, live_feed.KICK_COOLDOWN_SEC, 900.0]
    state, word = live_feed.state_word(5130.0, is_enabled=True)
    assert state == "kicked"
    assert word == ("📡 Paused — another connection on this Massive key keeps taking the stream (3 times today); "
                    "not reclaiming it for 900 s. The 1-minute check keeps running.")


def test_NEG_yield_window_expired_kicks_do_not_count(monkeypatch):
    monkeypatch.setattr(live_feed, "KICK_YIELD_AFTER_N", 2)
    monkeypatch.setattr(live_feed, "KICK_YIELD_WINDOW_SEC", 100.0)
    monkeypatch.setattr(live_feed, "KICK_YIELD_SEC", 900.0)
    a = live_feed._on_drop(was_authed=True, exc_text="", close_code=1008, backoff=2, clean=False, now=1000.0)
    b = live_feed._on_drop(was_authed=True, exc_text="", close_code=1008, backoff=2, clean=False, now=1500.0)
    assert a == b == live_feed.KICK_COOLDOWN_SEC


def test_blind_seconds_and_resume_from_drop_to_auth_success():
    live_feed._on_drop(was_authed=True, exc_text="", close_code=1008, backoff=2, clean=False, now=1_000_000.0)
    live_feed._on_auth(1_000_035.0)
    assert live_feed._link["resume_s_last"] == 35.0
    assert live_feed._today["blind_s"] == 35.0
    assert live_feed._link["kick_pending"] is False
    live_feed._on_drop(was_authed=True, exc_text="", close_code=1006, backoff=2, clean=False, now=1_000_100.0)
    live_feed._on_auth(1_000_140.0)
    assert live_feed._today["blind_s"] == 75.0 and live_feed._link["resume_s_last"] == 40.0


def test_NEG_startup_auth_is_not_blind_time():
    live_feed._on_auth(2_000_000.0)
    assert live_feed._today["blind_s"] == 0.0 and live_feed._link["resume_s_last"] is None


# ── lag ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_lag_is_recv_minus_sip_t():
    t = int(time.time() * 1000) - 200
    asyncio.run(live_feed._handle(json.dumps([{"ev": "T", "sym": "AAPL", "p": 1.0, "s": 1, "t": t}]), _Cache()))
    st = live_feed.status_payload(tracked_n=0, admin=False, is_enabled=True)
    assert 190 <= st["lag_ms_p50"] <= 400


def test_NEG_trade_without_t_adds_no_lag_sample():
    asyncio.run(live_feed._handle(json.dumps([{"ev": "T", "sym": "AAPL", "p": 1.0, "s": 1}]), _Cache()))
    assert len(live_feed._lag) == 0
    st = live_feed.status_payload(tracked_n=0, admin=True, is_enabled=True)
    assert st["lag_ms_p50"] is None and st["lag_ms_p99"] is None
    assert st["admin_word"].startswith("lag — ms · 0 kicks today · 0 s blind")


def test_lag_percentile_is_linear_interpolation():
    assert live_feed._pctl([1.0, 2.0, 3.0, 4.0, 10.0], 50) == 3.0
    assert live_feed._pctl([1.0, 2.0, 3.0, 4.0, 10.0], 90) == pytest.approx(7.6)
    assert live_feed._pctl([], 50) is None


def test_msgs_per_second_over_the_last_minute():
    now = time.time()
    frame = json.dumps([{"ev": "T", "sym": "AAPL", "p": 1.0, "s": 1}] * 120)
    asyncio.run(live_feed._handle(frame, _Cache()))
    assert live_feed._msgs_per_s(now + 0.5) == 2.0
    assert live_feed._msgs_per_s(now + live_feed.MSG_RATE_WINDOW_SEC + 2) == 0.0      # NEG: old seconds drop out


# ── the dev guard ───────────────────────────────────────────────────────────────────────────────────────────────
def test_dev_env_with_a_key_is_off_in_auto(monkeypatch):
    monkeypatch.setenv("CHEETAH_ENV", "dev")
    assert live_feed.enabled() is False


def test_explicit_true_wins_over_dev(monkeypatch):
    monkeypatch.setenv("CHEETAH_ENV", "dev")
    monkeypatch.setenv("MASSIVE_WS_ENABLED", "true")
    assert live_feed.enabled() is True


def test_NEG_prod_env_with_a_key_stays_on(monkeypatch):
    monkeypatch.setenv("CHEETAH_ENV", "prod")
    assert live_feed.enabled() is True
    monkeypatch.delenv("CHEETAH_ENV")
    assert live_feed.enabled() is True


def test_dev_compose_pins_the_feed_off():
    src = (Path(__file__).resolve().parents[2] / "docker-compose.dev.yml").read_text()
    assert 'MASSIVE_WS_ENABLED: "false"' in src and "CHEETAH_ENV: dev" in src


# ── the served words ────────────────────────────────────────────────────────────────────────────────────────────
def _ts(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=ET).timestamp()


def test_live_word_names_the_last_print_age():
    now = _ts(2026, 11, 10, 10, 0)
    live_feed.feed_state.update(authed=True, last_trade_ts=now - 3)
    assert live_feed.state_word(now, is_enabled=True) == ("live", "📡 Live prices — last print 3 s ago")


def test_quiet_when_authed_on_a_closed_day_or_outside_04_20():
    live_feed.feed_state.update(authed=True)
    assert live_feed.state_word(_ts(2026, 11, 14, 10, 0), is_enabled=True) == (
        "quiet", "📡 Connected — no prints (market closed).")                 # Saturday
    assert live_feed.state_word(_ts(2026, 11, 10, 21, 0), is_enabled=True)[0] == "quiet"
    assert live_feed.state_word(_ts(2026, 11, 10, 3, 59), is_enabled=True)[0] == "quiet"
    assert live_feed.state_word(_ts(2026, 11, 10, 4, 0), is_enabled=True)[0] == "live"   # NEG: 04:00 is in session


def test_off_word_when_the_feed_is_disabled():
    assert live_feed.state_word(is_enabled=False) == ("off", "📡 Live stream off on this server.")


def test_every_state_has_a_word_and_none_says_bounce_or_edge():
    for k in live_feed.FEED_STATES:
        assert k in live_feed.FEED_WORDS
    for w in list(live_feed.FEED_WORDS.values()) + [live_feed.ADMIN_WORD]:
        assert "bounce" not in w.lower() and "edge" not in w.lower()


# ── /live/feed-status ───────────────────────────────────────────────────────────────────────────────────────────
NEW_KEYS = ("kicks_1h", "kicks_today", "last_kick_et", "last_kick_age_s", "blind_s_today", "resume_s_last",
            "connected_since_et", "lag_ms_p50", "lag_ms_p99", "msgs_per_s_1m", "hub_symbols", "subscribed_t",
            "state", "word")


def _route():
    """The route body compiled straight out of main.py (the host venv cannot import main.py whole)."""
    tree = ast.parse(MAIN_SRC)
    fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "live_feed_status")
    fn.decorator_list = []
    ns = {"live_feed": live_feed, "tracked_symbols": {"AAPL", "MSFT"}, "_finnhub_poller_enabled": lambda: False,
          "Query": lambda *a, **k: 0, "Depends": lambda *a, **k: None, "current_user_email": None}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "main.py", "exec"), ns)
    return ns["live_feed_status"]


@pytest.fixture
def owner(monkeypatch):
    import auth
    monkeypatch.setattr(auth, "HOUSE_OWNER_EMAILS", ["owner@example.test"])
    return "owner@example.test"


def _poison():
    """The key in every string the feed could serve: an error, a status message, a close reason."""
    live_feed.feed_state["error"] = f"auth_failed: bad key {KEY}"
    live_feed._timeline("status", status="auth_failed", message=f"key {KEY} rejected")
    live_feed._on_drop(was_authed=True, exc_text=f"closed with {KEY}", close_code=1008, backoff=2, clean=False)


def test_feed_status_serves_the_new_keys_and_admin_extras(owner):
    _poison()
    st = asyncio.run(_route()(events=1, email=owner))
    for k in NEW_KEYS:
        assert k in st, k
    assert st["tracked"] == 2 and st["active_source"] == "massive_ws"
    assert st["admin_word"] == "lag — ms · 1 kicks today · 0 s blind"
    assert isinstance(st["events"], list) and 0 < len(st["events"]) <= live_feed.EVENTS_SERVED


def test_NEG_feed_status_never_carries_the_key_even_with_events(owner):
    _poison()
    for email in (owner, "household@example.test"):
        st = asyncio.run(_route()(events=1, email=email))
        assert KEY not in json.dumps(st, default=str)


def test_NEG_non_admin_gets_no_events_and_no_admin_word(owner):
    st = asyncio.run(_route()(events=1, email="household@example.test"))
    assert "events" not in st and "admin_word" not in st
    assert "word" in st and "state" in st


def test_NEG_admin_without_events_flag_gets_no_timeline(owner):
    st = asyncio.run(_route()(events=0, email=owner))
    assert "events" not in st and "admin_word" in st


def test_timeline_persists_off_the_loop_without_the_key(monkeypatch):
    rows = []

    class _Coll:
        def insert_one(self, doc):
            rows.append(doc)

    monkeypatch.setattr(live_feed, "_events_coll", lambda: _Coll())

    async def go():
        live_feed._timeline("status", status="max_connections", message=f"from {KEY}")
        await asyncio.sleep(0.05)

    asyncio.run(go())
    assert len(rows) == 1
    assert rows[0]["kind"] == "status" and rows[0]["at"] is not None
    assert KEY not in json.dumps(rows[0], default=str)


def test_NEG_timeline_without_mongo_keeps_memory_only():
    async def go():
        live_feed._timeline("connect")
        await asyncio.sleep(0.01)

    asyncio.run(go())
    assert [e["kind"] for e in live_feed._events] == ["connect"]


# ── the canary (written, never run here — HIS CALL #10) ─────────────────────────────────────────────────────────
def _canary():
    import importlib.util
    p = Path(__file__).resolve().parents[1] / "scripts" / "live_feed_canary.py"
    spec = importlib.util.spec_from_file_location("live_feed_canary", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_NEG_canary_refuses_on_a_market_day_inside_the_window():
    c = _canary()
    assert c.refuse_reason(datetime(2026, 11, 10, 10, 0, tzinfo=ET), False)          # Tuesday RTH
    assert c.refuse_reason(datetime(2026, 11, 10, 4, 0, tzinfo=ET), False)           # premarket
    assert c.refuse_reason(datetime(2026, 11, 10, 20, 4, tzinfo=ET), False)          # the last pass slot


def test_canary_may_run_on_a_closed_window_or_with_force():
    c = _canary()
    assert c.refuse_reason(datetime(2026, 11, 14, 10, 0, tzinfo=ET), False) is None  # Saturday
    assert c.refuse_reason(datetime(2026, 11, 10, 21, 0, tzinfo=ET), False) is None  # after 20:05
    assert c.refuse_reason(datetime(2026, 11, 10, 10, 0, tzinfo=ET), True) is None


def test_canary_every_step_fits_inside_the_api_kick_cooldown():
    c = _canary()
    assert c.step_budget() < live_feed.KICK_COOLDOWN_SEC
    assert c.CANARY_STEP_GAP_SEC >= 60



# ── critic review 2026-11-09: the timeline records kicks, not acks; today's waits exactly ────────────────────────
def test_NEG_200_subscribe_acks_write_zero_timeline_rows():
    acks = [{"ev": "status", "status": "success", "message": f"subscribed to: T.S{i:03d}"} for i in range(200)]
    acks.append({"ev": "status", "status": "connected", "message": "Connected Successfully"})
    asyncio.run(live_feed._handle(json.dumps(acks), _Cache()))
    assert list(live_feed._events) == []


def test_a_max_connections_status_writes_one_timeline_row():
    frame = [{"ev": "status", "status": "success", "message": "subscribed to: T.AAPL"},
             {"ev": "status", "status": "max_connections", "message": "Maximum number of websocket connections exceeded."}]
    asyncio.run(live_feed._handle(json.dumps(frame), _Cache()))
    rows = list(live_feed._events)
    assert len(rows) == 1 and rows[0]["kind"] == "status" and rows[0]["status"] == "max_connections"
    assert live_feed._link["kicked"] is True


def test_auth_failures_and_errors_are_timeline_rows():
    frame = [{"ev": "status", "status": s, "message": "x"} for s in ("auth_failed", "auth_timeout", "error")]
    asyncio.run(live_feed._handle(json.dumps(frame), _Cache()))
    assert [e["status"] for e in live_feed._events] == ["auth_failed", "auth_timeout", "error"]


def test_NEG_clean_close_right_after_max_connections_reconnects_at_once_like_today(monkeypatch):
    monkeypatch.setattr(live_feed, "KICK_COOLDOWN_SEC", 7.0)
    conn1 = _FakeConn(AUTH_OK, [json.dumps([{"ev": "status", "status": "max_connections", "message": "m"}])])
    conn2 = _FakeConn(AUTH_OK, [], end_exc=_Closed(1006))
    waits = _run_consumer(monkeypatch, [conn1, conn2])
    assert waits == [live_feed._RECONNECT_COOLDOWN]           # no sleep after the clean close (today), 30 s after 1006
    assert live_feed._today["kicks"] == 1                     # the kick is still COUNTED


def test_authed_drop_waits_todays_cooldown_and_not_authed_1008_keeps_the_backoff(monkeypatch):
    monkeypatch.setattr(live_feed, "KICK_COOLDOWN_SEC", 7.0)
    assert live_feed._on_drop(was_authed=True, exc_text="received 1006", close_code=1006, backoff=4,
                              clean=False) == live_feed._RECONNECT_COOLDOWN
    # a 1008 before auth with no max_connections text: today = the backoff, never a cooldown
    conn = _FakeConn([_Closed(1008, "policy")], [])
    waits = _run_consumer(monkeypatch, [conn])
    assert waits == [2] and live_feed._today["kicks"] == 1


def test_default_waits_equal_todays_code_for_every_case():
    """Today: clean → 0; (authed or 'max_connections' in text) → 30; else backoff. Defaults must match exactly."""
    cases = [(True, "", 1000, True), (False, "", 1000, True), (True, "received 1006", 1006, False),
             (True, "received 1008", 1008, False), (False, "auth failed: max_connections: m", None, False),
             (False, "received 1008", 1008, False), (False, "dns", None, False)]
    for authed, text, code, clean in cases:
        today = 0.0 if clean else (30.0 if (authed or "max_connections" in text) else 8)
        got = live_feed._on_drop(was_authed=authed, exc_text=text, close_code=code, backoff=8, clean=clean)
        assert got == today, (authed, text, code, clean)
