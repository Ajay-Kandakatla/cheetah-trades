"""The 🚩 lane-run mutex + the in-mutex cap re-read (GG LIVE spec §3.3 [C2 C3 C15], 2026-11-09).

ONE mutex (gajjala_lane_state `_id "run_mutex"`, the house lease primitive: find_one_and_update upsert, a held mutex
collides on `_id` → DuplicateKeyError) around the whole run() and run_stream() for every caller — the cron minute tick,
the api hub's bar-close run, the api hub's stream attempts.

Locks: the transport numbers (MINE); claim / release by token (NEG: a stale holder's release never frees a new
holder); a holder past `until` is taken over (NEG deadlock); two interleaved run()s → the second is "lane busy" with no
`_manage` and no broker write (NEG double write); the tick waits at most LANE_MUTEX_WAIT_SEC (NEG: never past it);
run_stream tries ONCE; the mutex is released after a run (and after a raise); a handle without the primitive runs
unlocked (the house no_store rule) while a failing primitive refuses; the C2 cap race (an order placed between the
pre-loop read and this doc's turn → `cap_open`, NEG a 4th position); byte identity of run() on the lane fixtures
except the declared additive keys (`run_ms`, `mutex_wait_ms`, `enter_ms`).
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from pymongo.errors import DuplicateKeyError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import trading.exit_engine as EE
import trading.gajjala_entry as GL
from tests.test_gajjala_lane import DAY, NOW, LaneColl, _brackets, alert, lane, seed  # noqa: F401 — `lane` is a fixture

UTC = timezone.utc
T0 = datetime(2026, 10, 20, 14, 55, tzinfo=UTC)
LEGACY_OUT_KEYS = {"ok", "ran", "manage_only", "day", "gate", "claimed", "waiting", "ordered", "skipped", "cancelled",
                   "filled", "closed", "closing", "dry_run", "breakeven", "added", "trailed", "partials", "half_off",
                   "protected", "restopped", "halt_waiting", "drawdown", "errors"}


class MutexColl(LaneColl):
    """gajjala_lane_state with Mongo's find_one_and_update(filter, $set, upsert): the `$or` free-filter on `until`;
    a held doc + upsert = DuplicateKeyError on `_id` (Mongo's behaviour)."""

    def __init__(self, docs=(), fail=False):
        super().__init__(docs)
        self.claims = 0
        self.fail = fail

    def find_one_and_update(self, q, update, upsert=False, **k):
        self.claims += 1
        if self.fail:
            raise RuntimeError("mongo down")
        now = q["$or"][0]["until"]["$lte"]
        doc = self.get(q["_id"])
        if doc is not None:
            if "until" not in doc or doc["until"] <= now:
                pre = dict(doc)
                doc.update(update["$set"])
                return pre
            if upsert:
                raise DuplicateKeyError("E11000 duplicate key run_mutex")
            return None
        if upsert:
            self.rows.append(dict({"_id": q["_id"]}, **update["$set"]))
        return None


@pytest.fixture
def clock(monkeypatch):
    c = {"t": 0.0, "slept": []}

    def sleep(sec):
        c["slept"].append(sec)
        c["t"] += sec

    monkeypatch.setattr(GL, "_mono", lambda: c["t"])
    monkeypatch.setattr(GL, "_sleep", sleep)
    monkeypatch.setattr(GL, "_mutex_now", lambda: T0 + timedelta(seconds=c["t"]))
    return c


def _mutexed(s, docs=()):
    s.db.gajjala_lane_state = MutexColl(docs)
    return s.db.gajjala_lane_state


def _mutex_doc(m):
    return m.get(GL.MUTEX_ID)


# ── numbers ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_transport_numbers():
    assert (GL.LANE_RUN_MUTEX_SEC, GL.LANE_MUTEX_WAIT_SEC, GL.LANE_MUTEX_POLL_SEC) == (55, 20, 0.5)
    assert GL.LANE_RUN_MUTEX_SEC < 60                   # under the minute tick: a dead holder never blocks two ticks
    assert GL.LANE_MUTEX_WAIT_SEC < GL.LANE_RUN_MUTEX_SEC
    assert GL.MUTEX_ID == "run_mutex" and GL.STATE_COLL == "gajjala_lane_state" and GL.LANE_BUSY_TEXT == "lane busy"
    assert GL.ORDER_SOURCES == ("tick", "stream", "bar_close", "hub_claim")
    # the lane's rules and numbers are untouched by P1 (spec §3.9)
    assert (GL.GAJJALA_RISK_PCT, GL.GG_BE_AFTER_BARS, GL.GAJJALA_MAX_OPEN, GL.GAJJALA_FILL_WAIT_SEC,
            GL.GAJJALA_MISSED_R, GL.GAJJALA_FLATTEN_BEFORE_CLOSE_MIN, GL.GAJJALA_ENTRY_CUTOFF_BEFORE_CLOSE_MIN) \
        == (0.25, 3, 3, 180, 1.0, 5, 30)


# ── the primitive ────────────────────────────────────────────────────────────────────────────────────────────────
def test_claim_collides_and_release_is_by_token(clock):
    m = MutexColl()
    a = GL._mutex_claim(m, T0, "tick:1")
    assert a and _mutex_doc(m)["until"] == T0 + timedelta(seconds=GL.LANE_RUN_MUTEX_SEC)
    assert GL._mutex_claim(m, T0 + timedelta(seconds=1), "stream:2") is None          # NEG: held → refused
    assert GL._mutex_release(m, "not-mine") is False                                  # NEG: wrong token
    assert GL._mutex_claim(m, T0 + timedelta(seconds=2), "stream:2") is None
    assert GL._mutex_release(m, a) is True
    assert GL._mutex_claim(m, T0 + timedelta(seconds=55), "stream:2")


def test_stale_holder_release_never_frees_the_new_holder(clock):
    m = MutexColl()
    a = GL._mutex_claim(m, T0, "tick:1")
    later = T0 + timedelta(seconds=GL.LANE_RUN_MUTEX_SEC + 1)
    b = GL._mutex_claim(m, later, "bar_close:1")                                      # past `until`: taken over
    assert b and b != a and _mutex_doc(m)["holder"] == "bar_close:1"
    clock["t"] = GL.LANE_RUN_MUTEX_SEC + 2
    assert GL._mutex_release(m, a) is False                                           # NEG: the stale holder
    assert GL._mutex_claim(m, later + timedelta(seconds=2), "tick:2") is None         # B still holds it
    assert GL._mutex_release(m, b) is True


def test_no_store_runs_unlocked_but_a_failing_primitive_refuses():
    assert GL._mutex_claim(None, T0, "tick") == GL.MUTEX_NO_STORE
    assert GL._mutex_claim(LaneColl(), T0, "tick") == GL.MUTEX_NO_STORE               # no atomic primitive
    assert GL._mutex_release(LaneColl(), GL.MUTEX_NO_STORE) is False
    assert GL._mutex_claim(MutexColl(fail=True), T0, "tick") is None                  # NEG: an error never runs


# ── run() / run_stream() ─────────────────────────────────────────────────────────────────────────────────────────
def test_run_takes_and_releases_the_mutex(lane, clock):
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48})
    m = _mutexed(s)
    out = s.run()
    assert out["ran"] and out["ordered"] == 1 and out["mutex_wait_ms"] == 0 and isinstance(out["run_ms"], int)
    assert m.claims == 1 and _mutex_doc(m)["until"] <= T0 + timedelta(seconds=clock["t"])     # released
    assert s.run()["ran"] and m.claims == 2                                                 # NEG: no leftover lock


def test_mutex_released_after_a_raise(lane, clock, monkeypatch):
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48})
    m = _mutexed(s)
    monkeypatch.setattr(GL, "_manage", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = s.run()
    assert out["ok"] is False and _mutex_doc(m)["until"] <= T0 + timedelta(seconds=clock["t"])


def test_holder_past_until_is_taken_over(lane, clock):
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48})
    m = _mutexed(s, [{"_id": GL.MUTEX_ID, "token": "dead", "holder": "tick:99", "until": T0 - timedelta(seconds=1)}])
    out = s.run()
    assert out["ran"] and out["ordered"] == 1 and clock["slept"] == []                # NEG: no deadlock, no wait


def test_interleaved_runs_second_is_lane_busy_without_manage(lane, clock, monkeypatch):
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48})
    _mutexed(s)
    real_manage = GL._manage
    seen = {"manage": 0, "second": None}

    def manage(*a, **k):
        seen["manage"] += 1
        if seen["second"] is None:
            before = list(s.brk.calls)
            seen["second"] = GL.run(broker=s.brk, cfg=EE.get_config(), now=NOW, source="bar_close")
            seen["second_calls"] = s.brk.calls[len(before):]
        return real_manage(*a, **k)

    monkeypatch.setattr(GL, "_manage", manage)
    first = s.run()
    second = seen["second"]
    assert first["ran"] and first["ordered"] == 1
    assert second["reason"] == "lane busy" and second["ran"] is False and second["ordered"] == 0
    assert seen["manage"] == 1 and seen["second_calls"] == []                         # NEG: no double _manage write
    assert sum(clock["slept"]) <= GL.LANE_MUTEX_WAIT_SEC
    assert len(_brackets(s.brk)) == 1


def test_tick_waits_at_most_the_bound_then_lane_busy(lane, clock, monkeypatch):
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48})
    m = _mutexed(s, [{"_id": GL.MUTEX_ID, "token": "hub", "holder": "stream:1",
                      "until": T0 + timedelta(seconds=GL.LANE_RUN_MUTEX_SEC)}])
    monkeypatch.setattr(GL, "_manage", lambda *a, **k: pytest.fail("ran _manage without the mutex"))
    out = s.run()
    assert out["reason"] == "lane busy" and out["ran"] is False
    assert GL.LANE_MUTEX_WAIT_SEC - GL.LANE_MUTEX_POLL_SEC <= sum(clock["slept"]) <= GL.LANE_MUTEX_WAIT_SEC
    assert out["mutex_wait_ms"] <= GL.LANE_MUTEX_WAIT_SEC * 1000                      # NEG: never past the bound
    assert m.claims == len(clock["slept"]) + 1 and s.brk.calls == []
    assert _mutex_doc(m)["token"] == "hub"                                            # NEG: the holder untouched


def test_tick_gets_the_mutex_once_the_holder_releases(lane, clock):
    s = lane(alerts=[alert()], lasts={"SAIQ": 4.48})
    _mutexed(s, [{"_id": GL.MUTEX_ID, "token": "hub", "holder": "stream:1", "until": T0 + timedelta(seconds=3)}])
    out = s.run()
    assert out["ran"] and out["ordered"] == 1 and 3000 <= out["mutex_wait_ms"] <= 3500


def test_run_stream_tries_once(lane, clock):
    s = lane(docs=[seed()], lasts={})
    m = _mutexed(s, [{"_id": GL.MUTEX_ID, "token": "tick", "until": T0 + timedelta(seconds=30)}])
    out = GL.run_stream(seed()["_id"], last=4.47, source="stream:T", broker=s.brk, cfg=EE.get_config(), now=NOW)
    assert out["reason"] == "lane busy" and m.claims == 1 and clock["slept"] == []    # NEG: never waits
    assert s.db.gajjala_lane.get(seed()["_id"])["state"] == "waiting" and _brackets(s.brk) == []


def test_run_stream_no_manage_no_account_tick(lane, clock, monkeypatch):
    s = lane(docs=[seed()], lasts={})
    _mutexed(s)
    monkeypatch.setattr(GL, "_manage", lambda *a, **k: pytest.fail("run_stream ran _manage"))
    monkeypatch.setattr(GL, "_account_tick", lambda *a, **k: pytest.fail("run_stream ran _account_tick"))
    out = GL.run_stream(seed()["_id"], last=4.47, source="stream:T", print_t="2026-10-20T14:55:00.000+00:00",
                        broker=s.brk, cfg=EE.get_config(), now=NOW)
    assert out["ordered"] == 1 and len(_brackets(s.brk)) == 1


def test_run_stream_gates_like_run(lane, clock):
    s = lane(docs=[seed()], lasts={}, market_open=False)
    _mutexed(s)
    out = GL.run_stream(seed()["_id"], last=4.47, broker=s.brk, cfg=EE.get_config(), now=NOW)
    assert out["ran"] is False and _brackets(s.brk) == []                            # NEG: market closed
    s = lane(docs=[seed()], lasts={}, mode="live")
    out = GL.run_stream(seed()["_id"], last=4.47, broker=s.brk, cfg=EE.get_config(), now=NOW)
    assert out["ran"] is False and _brackets(s.brk) == []                            # NEG: a live broker
    s = lane(docs=[seed()], lasts={}, now=datetime(2026, 10, 20, 9, 40, tzinfo=NOW.tzinfo))
    out = GL.run_stream(seed()["_id"], last=4.47, broker=s.brk, cfg=EE.get_config(), now=s.now)
    assert out["ran"] is False and _brackets(s.brk) == []                            # NEG: before 09:45 window


# ── C2: the in-mutex cap re-read ─────────────────────────────────────────────────────────────────────────────────
class RaceColl(LaneColl):
    """After the FIRST read of the live states, another caller's order lands (a doc in `ordered`)."""

    def __init__(self, docs=(), race=True):
        super().__init__(docs)
        self.race = race
        self.live_reads = 0

    def find(self, q=None, *a, **k):
        res = super().find(q, *a, **k)
        if isinstance((q or {}).get("state"), dict) and "$in" in q["state"]:
            self.live_reads += 1
            if self.race and self.live_reads == 1:
                self.rows.append({"_id": f"GG:{DAY}|CCC|bull_flag", "date": DAY, "symbol": "CCC", "state": "ordered"})
        return res


def _live(sym):
    return {"_id": f"GG:{DAY}|{sym}|bull_flag", "date": DAY, "symbol": sym, "state": "open"}


def _try(s, race):
    s.db.gajjala_lane = RaceColl([seed(), _live("AAA"), _live("BBB")], race=race)
    out = {"waiting": 0, "skipped": 0, "ordered": 0, "dry_run": 0, "halt_waiting": 0, "errors": []}
    reads = GL._Reads(s.brk, "2026-10-16T00:00:00+00:00")
    GL._try_waiting(s.db.gajjala_lane, EE.get_config(), s.brk, NOW, DAY, reads, out, scoll=s.db.gajjala_lane_state)
    return out, s.db.gajjala_lane.get(seed()["_id"])


def test_cap_race_in_mutex_reread_skips_cap_open(lane):
    s = lane(lasts={"SAIQ": 4.48})
    out, d = _try(s, race=True)
    assert (d["state"], d["skip_kind"]) == ("skipped", "cap_open") and out["ordered"] == 0
    assert _brackets(s.brk) == []                                                     # NEG: never a 4th position


def test_cap_race_control_orders_with_two_open(lane):
    s = lane(lasts={"SAIQ": 4.48})
    out, d = _try(s, race=False)
    assert d["state"] == "ordered" and out["ordered"] == 1 and len(_brackets(s.brk)) == 1


def test_reread_holds_a_name_ordered_meanwhile(lane):
    s = lane(lasts={"SAIQ": 4.48})

    class Held(LaneColl):
        n = 0

        def find(self, q=None, *a, **k):
            res = super().find(q, *a, **k)
            if isinstance((q or {}).get("state"), dict) and "$in" in q["state"]:
                Held.n += 1
                if Held.n == 1:
                    self.rows.append({"_id": f"GG:{DAY}|SAIQ|kiss_fly", "date": DAY, "symbol": "SAIQ",
                                      "state": "ordering"})
            return res

    s.db.gajjala_lane = Held([seed()])
    out = {"waiting": 0, "skipped": 0, "ordered": 0, "dry_run": 0, "halt_waiting": 0, "errors": []}
    GL._try_waiting(s.db.gajjala_lane, EE.get_config(), s.brk, NOW, DAY, GL._Reads(s.brk, "x"), out,
                    scoll=s.db.gajjala_lane_state)
    d = s.db.gajjala_lane.get(seed()["_id"])
    assert (d["state"], d["skip_kind"]) == ("skipped", "held") and _brackets(s.brk) == []


# ── byte identity of the default run() ──────────────────────────────────────────────────────────────────────────
def _strip(doc):
    return {k: v for k, v in doc.items() if k not in ("updated_at", "enter_ms")}


def test_default_run_identical_with_and_without_the_mutex_except_declared_keys(lane, clock):
    a = lane(alerts=[alert(), alert("JBDI", "kiss_fly", 2.48, 2.40)], lasts={"SAIQ": 4.48, "JBDI": 2.40})
    out_a = a.run()
    docs_a = sorted((_strip(d) for d in a.db.gajjala_lane.rows), key=lambda d: d["_id"])
    led_a = [(r["kind"], r["symbol"], r["detail"], r["dry_run"]) for r in a.db.trade_ledger.rows]
    b = lane(alerts=[alert(), alert("JBDI", "kiss_fly", 2.48, 2.40)], lasts={"SAIQ": 4.48, "JBDI": 2.40})
    _mutexed(b)
    out_b = b.run()
    docs_b = sorted((_strip(d) for d in b.db.gajjala_lane.rows), key=lambda d: d["_id"])
    led_b = [(r["kind"], r["symbol"], r["detail"], r["dry_run"]) for r in b.db.trade_ledger.rows]
    assert docs_a == docs_b and led_a == led_b and a.brk.calls == b.brk.calls
    assert set(out_a) == set(out_b) == LEGACY_OUT_KEYS | {"run_ms", "mutex_wait_ms"}
    assert {k: v for k, v in out_a.items() if k not in ("run_ms", "mutex_wait_ms")} == \
        {k: v for k, v in out_b.items() if k not in ("run_ms", "mutex_wait_ms")}
    ordered = a.db.gajjala_lane.get(f"GG:{DAY}|SAIQ|bull_flag")
    assert ordered["state"] == "ordered" and isinstance(ordered["enter_ms"], int)
    for k in ("order_source", "stream_print_px", "stream_print_t"):                  # NEG: the tick writes none
        assert k not in ordered
    assert a.db.gajjala_lane.get(f"GG:{DAY}|JBDI|kiss_fly")["state"] == "unfilled"
    row_keys = set(GL.ROW_KEYS)
    assert not row_keys & {"order_source", "stream_print_px", "stream_print_t", "enter_ms"}   # tab payload unchanged
