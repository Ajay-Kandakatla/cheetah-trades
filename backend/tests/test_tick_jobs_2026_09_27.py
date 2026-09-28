"""Chart Maps lanes — the snapshot trigger and the daily review ride the
existing per-minute exit_engine tick (trading/tick_jobs.py, 2026-09-27).

The crontab is host-mounted and a deploy never ships a new line, so the three
designed crontab lines would never have run. These pin the tick-driven design:

  * snapshot: only while the program is ON (paper / sim), only on an open
    market day inside [09:30, LAST_ENTRY_ET), at most once per 5-min bucket
    even with overlapping ticks, fire-and-forget (an HTTP failure never
    raises and is ledgered once per ET day; a read timeout is "sent");
  * review: first tick at/after 16:50 ET, exactly once a day, never before,
    never on a closed day; a raising or slow review never raises into the
    tick; a failed or done day never re-runs; an overrun (daemon thread,
    the process never lingers) or a dead owner's claim is re-claimed by a
    later tick past REVIEW_BUDGET_SEC;
  * exit_engine._main runs the jobs AFTER tick() (exits first), and a crash
    in the jobs never changes the tick's exit code.

Hermetic: MiniDB stand-in, a fake http_get, no network, no broker, no orders.
"""
import os
import sys
import time
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.exit_engine as EE  # noqa: E402
import trading.program_caps as PC  # noqa: E402
import trading.tick_jobs as TJ  # noqa: E402
from tests.test_program_caps import ET, MiniDB  # noqa: E402

MON = (2026, 9, 28)          # an open Monday
SUN = (2026, 9, 27)          # weekend
HOLIDAY = (2026, 11, 26)     # Thanksgiving (market_hours ALL_HOLIDAYS)
ON = {"cm_program": True}
OFF = {"cm_program": False}


def at(day, h, m, s=0):
    return datetime(*day, h, m, s, tzinfo=ET)


class Resp:
    def __init__(self, code):
        self.status_code = code


class ReadTimeout(Exception):
    """Same class name as requests.exceptions.ReadTimeout (name-matched)."""


class Http:
    def __init__(self, code=200, exc=None):
        self.calls = []
        self.code = code
        self.exc = exc

    def __call__(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers,
                           "timeout": timeout})
        if self.exc is not None:
            raise self.exc
        return Resp(self.code)


@pytest.fixture
def db(monkeypatch):
    d = MiniDB()
    monkeypatch.setattr(EE, "_DB", d)
    monkeypatch.setattr(EE, "_db", lambda: d)
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.delenv("INTERNAL_API_BASE", raising=False)
    return d


def ledger_rows(d, kind):
    return [r for r in d.trade_ledger.rows if r.get("kind") == kind]


def snap(http, now, cfg=ON, mode="paper", market_open=True):
    return TJ.maybe_trigger_snapshot(market_open=market_open, now=now, cfg=cfg,
                                     mode=mode, http_get=http)


# ═════════════════════════════════════════════════════════════════════════════
# SNAPSHOT
# ═════════════════════════════════════════════════════════════════════════════
def test_snapshot_fires_once_with_the_cron_header_and_record_true(db):
    http = Http()
    out = snap(http, at(MON, 10, 2))
    assert out["fired"] is True and out["bucket"] == "2026-09-28T10:00"
    assert len(http.calls) == 1
    c = http.calls[0]
    assert c["url"] == "http://api:8000/chart-maps/lane-snapshot"
    assert c["params"] == {"record": "true"}
    assert c["headers"] == {"X-User-Email": "cron@internal"}
    assert c["timeout"] == TJ.SNAPSHOT_TIMEOUT_SEC


def test_snapshot_uses_internal_api_base(db, monkeypatch):
    monkeypatch.setenv("INTERNAL_API_BASE", "http://api-x:9000/")
    http = Http()
    snap(http, at(MON, 11, 0))
    assert http.calls[0]["url"] == "http://api-x:9000/chart-maps/lane-snapshot"


def test_NEG_program_off_makes_no_call(db):
    http = Http()
    for cfg in (OFF, {}, {"cm_program": "true"}):
        out = snap(http, at(MON, 10, 0), cfg=cfg)
        assert out["fired"] is False and out["skipped"] == "program OFF"
    assert http.calls == []
    assert db.program_state.rows == []                 # not even a claim


def test_NEG_live_is_never_a_program(db):
    http = Http()
    assert snap(http, at(MON, 10, 0), mode="live")["fired"] is False
    assert http.calls == []


@pytest.mark.parametrize("hm", [(9, 29), (9, 0), (15, 45), (15, 50), (16, 0), (16, 55)])
def test_NEG_no_call_outside_0930_to_last_entry(db, hm):
    http = Http()
    out = snap(http, at(MON, *hm))
    assert out["fired"] is False and out["skipped"]
    assert http.calls == []


@pytest.mark.parametrize("hm", [(9, 30), (15, 44)])
def test_window_edges_inside(db, hm):
    http = Http()
    assert snap(http, at(MON, *hm))["fired"] is True
    assert len(http.calls) == 1


def test_window_end_is_the_lane_last_entry_constant():
    from trading.zone_edge_entry import LAST_ENTRY_ET
    from supply_demand.bounce_room import SESSION_OPEN
    assert TJ._last_entry() is LAST_ENTRY_ET
    assert TJ._session_open() is SESSION_OPEN


@pytest.mark.parametrize("day", [SUN, HOLIDAY])
def test_NEG_no_call_on_a_closed_day_even_if_the_clock_says_open(db, day):
    http = Http()
    out = snap(http, at(day, 10, 0), market_open=True)
    assert out["fired"] is False and out["skipped"] in ("weekend", "holiday 2026-11-26")
    assert http.calls == []


@pytest.mark.parametrize("mo", [False, None])
def test_NEG_no_call_when_the_broker_clock_is_not_open(db, mo):
    http = Http()
    assert snap(http, at(MON, 13, 30), market_open=mo)["fired"] is False
    assert http.calls == []


def test_NEG_two_ticks_one_bucket_one_call(db):
    http = Http()
    assert snap(http, at(MON, 10, 5, 1))["fired"] is True
    second = snap(http, at(MON, 10, 9, 59))
    assert second["fired"] is False and "already fired" in second["skipped"]
    assert len(http.calls) == 1
    assert snap(http, at(MON, 10, 10, 0))["fired"] is True
    assert len(http.calls) == 2


def test_NEG_a_slow_tick_never_claims_an_older_bucket(db):
    http = Http()
    snap(http, at(MON, 10, 10))
    late = snap(http, at(MON, 10, 9))                  # an overrunning earlier tick
    assert late["fired"] is False
    assert len(http.calls) == 1


def test_NEG_http_failure_never_raises_and_is_ledgered_once_per_day(db):
    import requests
    http = Http(exc=requests.exceptions.ConnectionError("refused"))
    a = snap(http, at(MON, 10, 0))
    b = snap(http, at(MON, 10, 5))
    assert a["fired"] is True and "ConnectionError" in a["error"] and a["ledgered"] is True
    assert b["fired"] is True and b["ledgered"] is False
    assert len(ledger_rows(db, TJ.SNAPSHOT_FAIL_KIND)) == 1
    nxt = at((2026, 9, 29), 10, 0)                     # next ET day: ledgered again
    assert snap(http, nxt)["ledgered"] is True
    assert len(ledger_rows(db, TJ.SNAPSHOT_FAIL_KIND)) == 2


def test_NEG_http_500_is_a_failure(db):
    out = snap(Http(code=500), at(MON, 10, 0))
    assert out["error"] == "HTTP 500"
    assert len(ledger_rows(db, TJ.SNAPSHOT_FAIL_KIND)) == 1


def test_read_timeout_is_sent_not_a_failure(db, monkeypatch):
    import requests
    for exc in (requests.exceptions.ReadTimeout("slow"), ReadTimeout("slow")):
        d = MiniDB()
        monkeypatch.setattr(EE, "_db", lambda d=d: d)
        out = snap(Http(exc=exc), at(MON, 10, 0))
        assert out["fired"] is True and "error" not in out
        assert ledger_rows(d, TJ.SNAPSHOT_FAIL_KIND) == []


def test_NEG_connect_timeout_is_a_failure(db):
    import requests
    out = snap(Http(exc=requests.exceptions.ConnectTimeout("no route")), at(MON, 10, 0))
    assert "ConnectTimeout" in out["error"]


def test_NEG_no_mongo_means_no_call(db, monkeypatch):
    monkeypatch.setattr(EE, "_db", lambda: None)
    http = Http()
    out = snap(http, at(MON, 10, 0))
    assert out["fired"] is False and "no mongo" in out["skipped"]
    assert http.calls == []


def test_NEG_claim_error_other_than_dup_makes_no_call(db):
    db.program_state.raise_on["find_one_and_update"] = RuntimeError("mongo down")
    http = Http()
    out = snap(http, at(MON, 10, 0))
    assert out["fired"] is False and "claim failed" in out["skipped"]
    assert http.calls == []


def test_NEG_ledger_crash_never_raises(db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("ledger down")
    monkeypatch.setattr(EE, "ledger", boom)
    out = snap(Http(code=503), at(MON, 10, 0))
    assert out["error"] == "HTTP 503" and out["ledgered"] is False


def test_NEG_config_read_crash_never_raises(db, monkeypatch):
    def boom():
        raise RuntimeError("config down")
    monkeypatch.setattr(EE, "get_config", boom)
    http = Http()
    out = TJ.maybe_trigger_snapshot(market_open=True, now=at(MON, 10, 0), http_get=http)
    assert out["fired"] is False and "RuntimeError" in out["error"]
    assert http.calls == []


# ═════════════════════════════════════════════════════════════════════════════
# REVIEW
# ═════════════════════════════════════════════════════════════════════════════
class Build:
    def __init__(self, exc=None, sleep=0.0):
        self.calls = []
        self.exc = exc
        self.sleep = sleep

    def __call__(self, day, now):
        self.calls.append((day, now))
        if self.sleep:
            time.sleep(self.sleep)
        if self.exc is not None:
            raise self.exc
        return {"day": day, "headline": "%s: 0 entries" % day}


def test_review_runs_once_on_the_first_tick_at_or_after_1650(db):
    b = Build()
    first = TJ.maybe_run_review(now=at(MON, 16, 50, 3), build=b)
    assert first["ran"] is True and first["status"] == "done"
    assert b.calls == [("2026-09-28", at(MON, 16, 50, 3))]
    second = TJ.maybe_run_review(now=at(MON, 16, 51), build=b)
    assert second == {"ran": False, "skipped": "already ran today"}
    assert len(b.calls) == 1
    claim = db.program_state.find_one({"_id": "lane_review:2026-09-28"})
    assert claim["status"] == "done" and claim["headline"] == "2026-09-28: 0 entries"


@pytest.mark.parametrize("hm", [(16, 49), (9, 30), (16, 0), (15, 45)])
def test_NEG_review_never_before_1650(db, hm):
    b = Build()
    out = TJ.maybe_run_review(now=at(MON, *hm), build=b)
    assert out["ran"] is False and "before 16:50" in out["skipped"]
    assert b.calls == [] and db.program_state.rows == []


@pytest.mark.parametrize("day", [SUN, HOLIDAY])
def test_NEG_review_never_on_a_closed_day(db, day):
    b = Build()
    out = TJ.maybe_run_review(now=at(day, 16, 55), build=b)
    assert out["ran"] is False and b.calls == []
    assert db.program_state.rows == []


def test_review_runs_again_on_the_next_trading_day(db):
    b = Build()
    TJ.maybe_run_review(now=at(MON, 16, 50), build=b)
    TJ.maybe_run_review(now=at((2026, 9, 29), 16, 52), build=b)
    assert [c[0] for c in b.calls] == ["2026-09-28", "2026-09-29"]


def test_NEG_review_raising_never_raises_and_never_reruns(db):
    b = Build(exc=RuntimeError("broker down"))
    out = TJ.maybe_run_review(now=at(MON, 16, 50), build=b)
    assert out["ran"] is True and out["status"] == "failed" and "broker down" in out["error"]
    assert len(ledger_rows(db, TJ.REVIEW_FAIL_KIND)) == 1
    again = TJ.maybe_run_review(now=at(MON, 16, 51), build=b)
    assert again["ran"] is False and len(b.calls) == 1


def test_NEG_review_over_budget_returns_and_is_ledgered(db):
    """Fix round 2026-09-27: an overrun is abandoned with its process and a
    LATER tick (claimed_at older than the budget) re-claims the day; a tick
    inside the budget window never does."""
    b = Build(sleep=0.4)
    t0 = time.monotonic()
    out = TJ.maybe_run_review(now=at(MON, 16, 50), build=b, budget_sec=0.05)
    assert time.monotonic() - t0 < 0.35
    assert out["status"] == "over_budget"
    assert len(ledger_rows(db, TJ.REVIEW_OVER_BUDGET_KIND)) == 1
    time.sleep(0.5)                                     # let the worker finish
    assert len(b.calls) == 1
    inside = TJ.maybe_run_review(now=at(MON, 16, 50, 30), build=b)   # < 45 s later
    assert inside["ran"] is False and "another tick owns it" in inside["skipped"]
    assert len(b.calls) == 1
    fast = Build()
    later = TJ.maybe_run_review(now=at(MON, 16, 51, 7), build=fast)
    assert later["ran"] is True and later["status"] == "done"
    assert len(fast.calls) == 1
    claim = db.program_state.find_one({"_id": "lane_review:2026-09-28"})
    assert claim["status"] == "done" and claim["attempts"] == 2
    assert TJ.maybe_run_review(now=at(MON, 16, 52), build=fast)["ran"] is False


def test_a_dead_owners_running_claim_is_taken_over_after_the_budget(db):
    """A `cron` redeploy / OOM between the claim and the mark leaves the day
    `running` with no live owner. No live owner can hold it past
    REVIEW_BUDGET_SEC, so the next tick past that re-claims it."""
    db.program_state.rows.append({"_id": "lane_review:2026-09-28", "day": "2026-09-28",
                                  "claimed_at": at(MON, 16, 50, 9).isoformat(timespec="seconds"),
                                  "status": "running"})
    b = Build()
    early = TJ.maybe_run_review(now=at(MON, 16, 50, 40), build=b)
    assert early["ran"] is False and "16:50:09" in early["skipped"]
    assert b.calls == []
    edge = at(MON, 16, 50, 9 + int(TJ.REVIEW_BUDGET_SEC))
    out = TJ.maybe_run_review(now=edge, build=b)
    assert out["ran"] is True and out["status"] == "done"
    assert len(b.calls) == 1


@pytest.mark.parametrize("status", ["done", "failed"])
def test_NEG_a_final_day_is_never_taken_over_however_old(db, status):
    db.program_state.rows.append({"_id": "lane_review:2026-09-28", "day": "2026-09-28",
                                  "claimed_at": at(MON, 16, 50).isoformat(timespec="seconds"),
                                  "status": status})
    b = Build()
    out = TJ.maybe_run_review(now=at(MON, 16, 59, 59), build=b)
    assert out == {"ran": False, "skipped": "already ran today"}
    assert b.calls == []


def test_NEG_review_claim_error_other_than_dup_does_not_run(db):
    db.program_state.raise_on["find_one_and_update"] = RuntimeError("mongo down")
    b = Build()
    out = TJ.maybe_run_review(now=at(MON, 16, 50), build=b)
    assert out["ran"] is False and "claim failed" in out["skipped"]
    assert b.calls == []


def test_NEG_an_overrunning_review_does_not_keep_the_cron_process_alive(tmp_path):
    """Supercronic never starts a tick while the previous one is running, so a
    lingering worker would skip every tick until the review ended. The
    process must exit at the budget, not when the build finishes."""
    import subprocess
    script = tmp_path / "linger.py"
    script.write_text(
        "import sys, time\n"
        "sys.path.insert(0, %r)\n"
        "from datetime import datetime\n"
        "from trading import tick_jobs as TJ\n"
        "class C:\n"
        "    def find_one_and_update(self, *a, **k): return None\n"
        "    def find_one(self, *a, **k): return None\n"
        "    def update_one(self, *a, **k): pass\n"
        "TJ._state_coll = lambda: C()\n"
        "TJ._closed_reason = lambda n: None\n"
        "TJ._ledger = lambda k, d: None\n"
        "r = TJ.maybe_run_review(now=datetime(2026, 9, 28, 16, 50),\n"
        "                        build=lambda d, n: time.sleep(20) or {}, budget_sec=0.3)\n"
        "print(r['status'], flush=True)\n"
        "raise SystemExit(0)\n" % os.path.join(os.path.dirname(__file__), ".."))
    t0 = time.monotonic()
    p = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                       timeout=60)
    wall = time.monotonic() - t0
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "over_budget"
    assert wall < 10, "the cron process lingered %.1fs for the review thread" % wall


def test_NEG_review_no_mongo_does_not_run(db, monkeypatch):
    monkeypatch.setattr(EE, "_db", lambda: None)
    b = Build()
    out = TJ.maybe_run_review(now=at(MON, 16, 55), build=b)
    assert out["ran"] is False and b.calls == []


def test_default_build_is_lane_review_for_today_recorded(db, monkeypatch):
    from trading import lane_review
    seen = []
    monkeypatch.setattr(lane_review, "build",
                        lambda **k: seen.append(k) or {"headline": "h"})
    out = TJ.maybe_run_review(now=at(MON, 16, 50))
    assert out["status"] == "done"
    assert seen == [{"day": "2026-09-28", "now": at(MON, 16, 50), "record": True}]


def test_lane_review_module_places_no_orders():
    """Broker-light by design: the review only READS closed orders."""
    import inspect
    from trading import lane_review
    src = inspect.getsource(lane_review)
    for verb in ("submit_order", "place_order", "cancel_order", "close_position",
                 "entries.enter", "flatten("):
        assert verb not in src, verb


# ═════════════════════════════════════════════════════════════════════════════
# THE TICK
# ═════════════════════════════════════════════════════════════════════════════
def test_run_after_tick_reads_the_tick_market_open_and_program(db, monkeypatch):
    monkeypatch.setattr(EE, "get_config", lambda: dict(ON))
    monkeypatch.setattr(EE, "_broker_mode", lambda: "paper")
    calls = []
    monkeypatch.setattr(TJ, "_default_get", lambda *a, **k: calls.append((a, k)) or Resp(200))
    out = TJ.run_after_tick({"market_open": True}, now=at(MON, 11, 0))
    assert out["lane_snapshot"]["fired"] is True and len(calls) == 1
    assert out["lane_review"]["ran"] is False
    out2 = TJ.run_after_tick({"market_open": False, "reason": "market_closed"},
                             now=at(MON, 11, 7))
    assert out2["lane_snapshot"]["fired"] is False and len(calls) == 1


def test_NEG_run_after_tick_with_program_off_calls_nothing(db, monkeypatch):
    monkeypatch.setattr(EE, "get_config", lambda: dict(OFF))
    monkeypatch.setattr(EE, "_broker_mode", lambda: "paper")
    calls = []
    monkeypatch.setattr(TJ, "_default_get", lambda *a, **k: calls.append(a) or Resp(200))
    for m in range(30, 60, 5):
        TJ.run_after_tick({"market_open": True}, now=at(MON, 9, m))
    assert calls == []


def test_main_runs_the_jobs_after_tick_exits(monkeypatch):
    order = []

    def fake_tick(force=False):
        order.append("tick")                            # exits are managed in here
        return {"ok": True, "market_open": False}

    def fake_after(summary):
        order.append(("after", summary.get("market_open")))
        return {"lane_review": {"ran": True}}

    monkeypatch.setattr(EE, "tick", fake_tick)
    monkeypatch.setattr(TJ, "run_after_tick", fake_after)
    assert EE._main(["tick"]) == 0
    assert order == ["tick", ("after", False)]


def test_NEG_main_exit_code_survives_a_crashing_review(db, monkeypatch):
    """The review raises inside the real hook: tick() (exit management) already
    ran, nothing raises, and the tick's own exit code stands."""
    order = []
    monkeypatch.setattr(EE, "tick", lambda force=False: order.append("tick") or
                        {"ok": True, "market_open": False})
    from trading import lane_review

    def boom(**k):
        order.append("review")
        raise RuntimeError("review exploded")
    monkeypatch.setattr(lane_review, "build", boom)
    real = TJ.run_after_tick
    monkeypatch.setattr(TJ, "run_after_tick",
                        lambda s: real(s, now=at(MON, 16, 50)))
    assert EE._main(["tick"]) == 0
    assert order == ["tick", "review"]
    assert len(ledger_rows(db, TJ.REVIEW_FAIL_KIND)) == 1


def test_NEG_main_exit_code_survives_a_hook_that_raises(monkeypatch):
    monkeypatch.setattr(EE, "tick", lambda force=False: {"ok": False, "reason": "x"})

    def boom(summary):
        raise RuntimeError("hook exploded")
    monkeypatch.setattr(TJ, "run_after_tick", boom)
    assert EE._main(["tick"]) == 1                      # the tick's own code, unchanged
    monkeypatch.setattr(EE, "tick", lambda force=False: {"ok": True})
    assert EE._main(["tick"]) == 0


def test_NEG_usage_path_runs_no_jobs(monkeypatch):
    called = []
    monkeypatch.setattr(TJ, "run_after_tick", lambda s: called.append(s))
    assert EE._main([]) == 2 and called == []
