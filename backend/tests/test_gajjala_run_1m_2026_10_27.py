"""chart_maps/gajjala/run_1m.py — the 🚩 1-minute page's pass (BUILD_SPEC27 §3.6 / WP-B, 2026-10-27).

Ajay 2026-10-27: "Can you create a new page, I would like you to do the same logic of Gajjalas but on 1 min candles
please." / "do everything and also add the track record for it from today.."

The REAL bars resampler, detectors, A+ gate and 🧠 gate run on fixture 1-minute bars (the Bull Flag A+ fixture read as
1-minute candles). Every store is an in-memory FakeColl set — resolved by PHYSICAL collection name through a patched
`store._coll`, so a write's landing place is what the test sees (tests/conftest.py refuses a real MongoClient). Every
spawn is a recorder: no test reaches `spawn_loop`'s real Popen (one test inspects its arguments with Popen patched).
NEGATIVES (mandatory, marked): no snapshot / type map / record_scan / ah-carry / halts / floats_for / squeeze history
call, zero writes on any GG5 collection, a held GG5 lease never blocks GG1, a second cron loop is refused, an on-open
iteration writes no /alerts row, the non-cron run.main paths never spawn, a raising spawn keeps the exit code, a live
GG5 child never makes GG1 "waiting", a raising GG1 grade keeps the nightly's exit 0. UNMEASURED: nothing here trades.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import nightly as NG
from chart_maps.gajjala import on_demand as OD
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_store import FakeColl, fake_store

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
S = date(2026, 10, 13)                                   # a Tuesday — a market day
PREV = date(2026, 10, 12)
REAL_POPEN = R1._popen
WRITE_OPS = ("update_one", "update_many", "replace_one", "insert_one", "insert_many", "delete_one", "delete_many",
             "find_one_and_update", "create_index", "bulk_write")


def at(hh, mm, ss=0, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


def m1(bars, day, start, *, volume=True):
    """Each (o, h, l, c, v) as ONE 1-minute bar — naive-UTC index = the minute START (daytrading.data)."""
    t0 = datetime.combine(day, datetime.strptime(start, "%H:%M").time(), tzinfo=ET)
    idx, rows = [], []
    for k, (o, h, l, c, v) in enumerate(bars):
        idx.append(pd.Timestamp((t0 + timedelta(minutes=k)).astimezone(UTC).replace(tzinfo=None)))
        row = {"open": o, "high": h, "low": l, "close": c, "session": "rth"}
        if volume:
            row["volume"] = v
        rows.append(row)
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


PRIOR_1M = m1(FX.warm(n=60), PREV, "14:00")
TODAY_1M = m1(FX.bf_bars(), S, "10:00")                  # 8 one-minute bars: labels 10:01 … 10:08
NOW = at(10, 8, 31)                                      # the 10:08 bar has settled (BAR_SETTLE_SEC)
CTX = {"float": {"shares": 5_000_000, "src": "shares_out_massive", "text": "5.0M float"}, "float_suspect": None,
       "rotation": None, "halts": None, "psych": [], "squeeze_history": None, "last_halt_resume_et": None,
       "reg_gain_pct": 40.0}
G5_PASS = {"strip": {"qualifiers": 1, "tape": "rth"}, "counts": {"qualifiers": 1, "rows": 9},
           "tape_session": "rth", "premarket": {"pm_levels": {"GGA": {"high": 11.0}}}, "postmarket": None,
           "ah_carry": "skipped", "status": "ok"}


class Rec:
    def __init__(self, ret=None):
        self.calls = []
        self.ret = ret

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self.ret(*a, **k) if callable(self.ret) else self.ret


class CountColl(FakeColl):
    """FakeColl that counts EVERY write method (FakeColl.writes skips find_one_and_update / create_index)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.w = 0

    def update_one(self, *a, **k):
        self.w += 1
        return super().update_one(*a, **k)

    def replace_one(self, *a, **k):
        self.w += 1
        return super().replace_one(*a, **k)

    def find_one_and_update(self, *a, **k):
        self.w += 1
        return super().find_one_and_update(*a, **k)

    def create_index(self, *a, **k):
        self.w += 1
        return super().create_index(*a, **k)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.delenv("GAJJALA_1M_ENABLED", raising=False)
    monkeypatch.setattr(R1, "_PREV_MEMO", {})
    monkeypatch.setattr(ST, "_VARIANT_STORES", {})
    monkeypatch.setattr(OD, "_STATE", {"proc": None, "started_at": None})
    monkeypatch.setattr(OD, "_STATES", {})
    # NEGATIVE guard for the whole file: no test reaches a real spawn
    monkeypatch.setattr(R1, "_popen", lambda *a, **k: pytest.fail("a test reached the real spawn"))
    monkeypatch.setattr(OD, "_spawn", lambda *a, **k: pytest.fail("a test reached the real on-open spawn"))


def world(monkeypatch, *, names=("GGA",), seed_read=True, seed_pass=True):
    """(db, shared, st): every collection by PHYSICAL name in `db`; GG5's store seeded with today's scan doc, its read
    doc (ctx) and its latest pass; the GG1 store reads the shared ones through `shared`. Write counters reset."""
    db: dict = {}
    monkeypatch.setattr(ST, "_coll", lambda name: db.setdefault(name, CountColl()))
    shared = ST.GajjalaStore()
    st = ST.GajjalaStore(variant=V.GG1, shared=shared)
    rows = [{"symbol": s, "price": 11.2, "prev_close": 8.0, "change_pct": 40.0 - i, "volume": 3_000_000}
            for i, s in enumerate(names)]
    shared.record_qualifiers(S, at(10, 6), rows, "rth")
    if seed_read:
        for s in names:
            shared.upsert_read(S, s, {"ctx": dict(CTX), "setups": {}}, now=at(10, 6, 5))
    if seed_pass:
        shared.record_pass(S, at(10, 6, 5), dict(G5_PASS))
    for c in db.values():
        c.w = 0
    return db, shared, st


def loader(*, today=None, prior=None, calls=None):
    def load_day(sym, day, force=False, include_premarket=True, include_afterhours=False):
        if calls is not None:
            calls.append((sym, day, bool(force)))
        if day == PREV:
            return (prior if prior is not None else PRIOR_1M).copy()
        return (today if today is not None else TODAY_1M).copy()
    return load_day


def deps(**over):
    d = R1.Deps1m(load_day=over.pop("load_day", loader()), send=Rec({"sent": 1}), send_potential=Rec({"sent": 1}),
                  owner="owner@example.com", record_status=Rec(True), record_potential_status=Rec(True),
                  clock=lambda: 0.0, wall=lambda: RUN._utc(NOW), sleep=lambda s: None)
    for k, v in over.items():
        setattr(d, k, v)
    return d


# ── the slot clock ────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("now,tick", [(at(10, 31, 0), at(10, 31)), (at(10, 31, 58), at(10, 31)),
                                      (at(10, 35, 59), at(10, 31)), (at(10, 36, 0), at(10, 36)),
                                      (at(4, 1, 5), at(4, 1)), (at(20, 1, 10), at(20, 1))])
def test_slot_of_is_the_1_56_5_grid_and_robust_to_a_late_start(now, tick):
    t, nxt = R1.slot_of(now)
    assert t == tick and nxt == tick + timedelta(seconds=GC.PASS_CADENCE_SEC)
    assert (t.minute - GC.PASS_MINUTE_OFFSET) % (GC.PASS_CADENCE_SEC // 60) == 0 and t.second == 0


def test_NEGATIVE_slot_of_never_rounds_up_to_the_next_tick():
    assert R1.slot_of(at(10, 30, 59))[0] == at(10, 26)                 # 58 s before 10:31 is still the 10:26 slot
    assert R1.slot_of(at(10, 31, 58))[0] != at(10, 36)


def test_next_start_is_the_next_closed_minute_plus_the_settle():
    assert R1.next_start(at(10, 31, 10)) == at(10, 31, 30)
    assert R1.next_start(at(10, 31, 30)) == at(10, 32, 30)
    assert R1.next_start(at(10, 32, 5)) == at(10, 32, 30)


def test_fits_uses_the_budget_and_the_margin_from_the_start():
    nxt = at(10, 36)
    edge = nxt - timedelta(seconds=GC.GG1M_MINUTE_BUDGET_SEC + GC.GG1M_SLOT_MARGIN_SEC)
    assert edge == at(10, 35, 5)
    assert R1.fits(edge, nxt) is True
    assert R1.fits(edge + timedelta(seconds=1), nxt) is False          # NEGATIVE: one second past → refused


# ── the loop (fake wall clock + fake sleep) ───────────────────────────────────────────────────────────────────────
class Clock:
    def __init__(self, t):
        self.t = RUN._utc(t)

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t = self.t + timedelta(seconds=s)


def _loop(monkeypatch, start, *, iteration=None):
    clock = Clock(start)
    seen = []

    def fake_iteration(now, **k):
        seen.append((now.astimezone(ET), k.get("slot")))
        clock.t = clock.t + timedelta(seconds=5)                        # each iteration takes 5 s of wall
        return iteration(now) if iteration else {"ran": True, "status": "ok"}
    monkeypatch.setattr(R1, "run_iteration", fake_iteration)
    st = fake_store()
    st.variant = V.GG1
    d = deps(wall=clock, sleep=clock.sleep)
    out = R1.loop(store=st, deps=d)
    return out, seen, st


def test_loop_runs_five_iterations_per_slot_and_refuses_tick_plus_4_30(monkeypatch):
    out, seen, st = _loop(monkeypatch, at(10, 31, 10))
    assert [t.strftime("%H:%M:%S") for t, _s in seen] == ["10:31:10", "10:31:30", "10:32:30", "10:33:30",
                                                          "10:34:30"]
    assert [s["i"] for _t, s in seen] == [0, 1, 2, 3, 4] and all(s["tick"] == at(10, 31) for _t, s in seen)
    assert out["n"] == 5 and out["reason"] == "no time left in the slot"
    doc = st.get_state(R1.LOOP_STATE_ID)
    assert doc["n"] == 5 and doc["reason"] == "no time left in the slot" and doc["tick"] == RUN._utc(at(10, 31))
    assert doc["ended_at"] is not None


def test_NEGATIVE_zero_iterations_when_the_start_is_past_tick_plus_4_05(monkeypatch):
    """The "GG5 ran long" case: the spawn lands after the last start that fits — nothing runs, the reason is kept."""
    out, seen, st = _loop(monkeypatch, at(10, 35, 6))
    assert seen == [] and out["n"] == 0 and out["reason"] == "no time left in the slot"
    assert st.get_state(R1.LOOP_STATE_ID)["reason"] == "no time left in the slot"


def test_loop_stops_after_the_extended_close(monkeypatch):
    out, seen, _st = _loop(monkeypatch, at(20, 1, 10))                  # reads the 20:00 bar, then stops
    assert [t.strftime("%H:%M:%S") for t, _s in seen] == ["20:01:10"]
    assert out["reason"] == "after the extended close"


def test_NEGATIVE_no_iteration_past_the_extended_close(monkeypatch):
    out, seen, st = _loop(monkeypatch, at(20, 2, 10))
    assert seen == [] and out["n"] == 0 and out["reason"] == "after the extended close"
    assert st.get_state(R1.LOOP_STATE_ID)["reason"] == "after the extended close"


def test_loop_ends_on_a_held_lease(monkeypatch):
    out, seen, _st = _loop(monkeypatch, at(10, 31, 10),
                           iteration=lambda now: {"ran": False, "reason": R1.LEASE_HELD})
    assert len(seen) == 1 and out["reason"] == "lease held" and out["n"] == 0


def test_the_loop_reasons_are_the_four_the_spec_names():
    assert R1.LOOP_REASONS == ("no time left in the slot", "after the extended close", "off", "lease held")


# ── the switch ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_enabled_reads_the_constant_and_the_env_at_call_time(monkeypatch):
    assert R1.enabled() is True
    monkeypatch.setenv("GAJJALA_1M_ENABLED", "1")
    assert R1.enabled() is True
    monkeypatch.setenv("GAJJALA_1M_ENABLED", "0")
    assert R1.enabled() is False                                         # NEGATIVE: env "0"
    monkeypatch.delenv("GAJJALA_1M_ENABLED")
    monkeypatch.setattr(GC, "GAJJALA_1M_ENABLED", False)
    assert R1.enabled() is False                                         # NEGATIVE: the constant


@pytest.mark.parametrize("how", ["constant", "env"])
def test_NEGATIVE_switched_off_no_spawn_and_no_iteration(monkeypatch, how):
    if how == "constant":
        monkeypatch.setattr(GC, "GAJJALA_1M_ENABLED", False)
    else:
        monkeypatch.setenv("GAJJALA_1M_ENABLED", "0")
    out, seen, st = _loop(monkeypatch, at(10, 31, 10))
    assert seen == [] and out["reason"] == "off" and st.get_state(R1.LOOP_STATE_ID)["reason"] == "off"
    spawn = Rec(True)
    monkeypatch.setattr(R1, "spawn_loop", spawn)
    monkeypatch.setattr(RUN, "in_window", lambda *_a, **_k: True)
    monkeypatch.setattr(RUN, "run_pass", lambda now, **k: {"status": "ok"})
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    assert RUN.main([]) == 0 and spawn.calls == []
    monkeypatch.setattr(R1, "run_iteration", lambda *a, **k: pytest.fail("off: no iteration"))
    assert R1.main(["--loop"]) == 0 and R1.main(["--on-demand"]) == 0


# ── the names: GG5's listed names only ────────────────────────────────────────────────────────────────────────────
def _names_store():
    st = fake_store()
    st.record_qualifiers(S, at(10, 0), [{"symbol": "AAA", "change_pct": 10.0}, {"symbol": "BBB", "change_pct": 50.0},
                                        {"symbol": "CCC", "change_pct": 30.0}, {"symbol": "DDD", "change_pct": 30.0}],
                         "rth")
    st.record_qualifiers(PREV, at(10, 0, d=PREV), [{"symbol": "ZZZ", "change_pct": 99.0},
                                                   {"symbol": "MMM", "change_pct": 80.0},
                                                   {"symbol": "AAA", "change_pct": 90.0}], "rth")
    return st


def test_names_order_by_todays_change_then_carried_by_symbol():
    names, n_capped = R1.names_for(_names_store(), S)
    assert names == ["BBB", "CCC", "DDD", "AAA", "MMM", "ZZZ"] and n_capped == 0


def test_names_cap_counts_what_it_cut(monkeypatch):
    monkeypatch.setattr(GC, "GG1M_MAX_NAMES", 2)
    assert R1.names_for(_names_store(), S) == (["BBB", "CCC"], 4)
    monkeypatch.setattr(GC, "GG1M_MAX_NAMES", 60)
    st = fake_store()
    st.record_qualifiers(S, at(10, 0), [{"symbol": f"S{i:02d}", "change_pct": float(i)} for i in range(61)], "rth")
    names, n_capped = R1.names_for(st, S)
    assert len(names) == 60 and n_capped == 1 and names[0] == "S60" and "S00" not in names


def test_NEGATIVE_a_held_or_unlisted_name_is_never_read():
    st = _names_store()
    st.set_split_check(S, "BBB", "held", held=True)
    names, _n = R1.names_for(st, S)
    assert "BBB" not in names and "QQQ" not in names


# ── one iteration end to end (shadow) ─────────────────────────────────────────────────────────────────────────────
def test_iteration_records_the_1m_aplus_in_shadow_and_never_sends(monkeypatch):
    db, shared, st = world(monkeypatch)
    d = deps()
    out = R1.run_iteration(NOW, store=st, deps=d)
    assert out["ran"] and out["status"] == "ok" and out["errors"] == []
    assert out["n_listed"] == 1 and out["n_read"] == 1 and out["n_capped"] == 0 and "GGA:bull_flag" in out["aplus"]
    assert out["bars_through_et"] == "10:08" and out["bars"]["loaded"] == 1
    assert out["alerts"]["shadow"] >= 1 and out["alerts"]["shadow_mode"] == 1 and out["alerts"]["pushed"] == 0
    assert d.send.calls == [] and d.send_potential.calls == []           # NEGATIVE: shadow never sends
    ids = set(db["gajjala_1m_alerts"].docs)
    assert "SHADOW:GG1:2026-10-13|GGA|bull_flag" in ids and all(i.startswith("SHADOW:GG1:") for i in ids)
    assert "gajjala_alerts" not in db or db["gajjala_alerts"].docs == {}  # NEGATIVE: never GG5's ledger
    assert "shadow" in out["potential"]                                  # a shadow variant's own key
    assert st.get_state("lease")["status"] == "done"


def test_the_read_doc_keys_are_exactly_the_specs(monkeypatch):
    db, shared, st = world(monkeypatch)
    R1.run_iteration(NOW, store=st, deps=deps())
    doc = db["gajjala_1m_reads"].docs["2026-10-13|GGA"]
    assert set(doc) - {"_id"} == {"as_of_bar_t1", "as_of_bar_t5", "setups", "ctx", "tile", "listed", "stopped_today",
                                  "date", "symbol", "updated_at", "at"}
    assert set(doc["tile"]) == {"bars1", "curves1", "vol_avg1", "bars5", "curves5", "vol_avg5"}
    assert doc["as_of_bar_t1"] == "2026-10-13 10:08" and doc["as_of_bar_t5"] == "2026-10-13 10:05"
    assert 0 < len(doc["tile"]["bars1"]) <= GC.GG1M_TILE_BARS_MAX
    assert doc["setups"]["bull_flag"]["state"] == "aplus" and doc["setups"]["bull_flag"]["frame"] == "1m"
    assert doc["listed"]["day_n"] == 1
    assert "as_of_bar_t15" not in doc and "bars15" not in doc["tile"]    # NEGATIVE: no GG5 frame keys


def test_the_tile_keeps_only_the_last_tile_bars_max_one_minute_bars(monkeypatch):
    monkeypatch.setattr(GC, "GG1M_TILE_BARS_MAX", 3)
    db, shared, st = world(monkeypatch)
    R1.run_iteration(NOW, store=st, deps=deps())
    tile = db["gajjala_1m_reads"].docs["2026-10-13|GGA"]["tile"]
    assert [b["t"] for b in tile["bars1"]] == ["2026-10-13 10:06", "2026-10-13 10:07", "2026-10-13 10:08"]


def test_ctx_is_gg5s_stored_ctx_and_nothing_is_recomputed(monkeypatch):
    from chart_maps.gajjala import context as CX
    from chart_maps.gajjala import scanner as SC
    from sepa import prices
    boom = lambda *a, **k: pytest.fail("GG1 never calls this")             # noqa: E731
    for mod, name in ((RUN, "_snapshot"), (RUN, "_halts"), (prices, "market_snapshot_with_meta"),
                      (SC, "ensure_type_map"), (SC, "fetch_type_map"), (SC, "record_scan"), (SC, "commit_ah_carry"),
                      (SC, "scan_rows"), (CX, "floats_for"), (CX, "warm_squeeze_history"),
                      (CX, "record_live_halts"), (CX, "postmarket_confirm")):
        monkeypatch.setattr(mod, name, boom)
    db, shared, st = world(monkeypatch)
    out = R1.run_iteration(NOW, store=st, deps=deps())
    assert out["status"] == "ok" and out["errors"] == []
    assert db["gajjala_1m_reads"].docs["2026-10-13|GGA"]["ctx"] == CTX


def test_NEGATIVE_a_name_without_a_gg5_read_still_reads_with_an_empty_ctx(monkeypatch):
    db, shared, st = world(monkeypatch, seed_read=False)
    out = R1.run_iteration(NOW, store=st, deps=deps())
    assert out["n_read"] == 1 and db["gajjala_1m_reads"].docs["2026-10-13|GGA"]["ctx"] == {}


def test_k11_reads_the_1_minute_session_volume(monkeypatch):
    db, shared, st = world(monkeypatch)
    R1.run_iteration(NOW, store=st, deps=deps())
    bf = db["gajjala_1m_reads"].docs["2026-10-13|GGA"]["setups"]["bull_flag"]
    from chart_maps.gajjala import detectors as D
    k11 = [c for c in bf["criteria"] if c.get("key") == D.K11_KEY]
    assert bf["state"] == "aplus" and k11 and k11[0]["ok"] is True


def test_NEGATIVE_no_volume_means_k11_unknown_and_the_read_is_partial(monkeypatch):
    db, shared, st = world(monkeypatch)
    no_vol = loader(today=m1(FX.bf_bars(), S, "10:00", volume=False), prior=m1(FX.warm(n=60), PREV, "14:00",
                                                                             volume=False))
    out = R1.run_iteration(NOW, store=st, deps=deps(load_day=no_vol))
    bf = db["gajjala_1m_reads"].docs["2026-10-13|GGA"]["setups"]["bull_flag"]
    assert bf["state"] == "partial" and out["aplus"] == []
    assert db.get("gajjala_1m_alerts") is None or not [i for i in db["gajjala_1m_alerts"].docs if "|bull_flag" in i
                                                        and "#" not in i]


def test_NEGATIVE_a_spent_budget_counts_over_budget_and_is_never_a_failure(monkeypatch):
    from chart_maps.gajjala import bars as B
    import itertools
    ticks = itertools.count()
    monkeypatch.setattr(B.time, "monotonic", lambda: float(next(ticks)))
    monkeypatch.setattr(GC, "GG1M_MINUTE_BUDGET_SEC", 0)
    db, shared, st = world(monkeypatch, names=("GGA", "GGB"))
    calls = []
    out = R1.run_iteration(NOW, store=st, deps=deps(load_day=loader(calls=calls)))
    assert out["bars"]["over_budget"] == 2 and out["n_read"] == 0 and calls == []
    assert out["status"] == "ok" and out["errors"] == []


def test_the_prior_day_is_loaded_once_per_process(monkeypatch):
    db, shared, st = world(monkeypatch)
    calls = []
    d = deps(load_day=loader(calls=calls))
    R1.run_iteration(NOW, store=st, deps=d)
    R1.run_iteration(NOW + timedelta(seconds=60), store=st, deps=d)
    prev = [c for c in calls if c[1] == PREV]
    today = [c for c in calls if c[1] == S]
    assert len(prev) == 1 and prev[0][2] is False                       # the second iteration loads today only
    assert len(today) == 2 and all(c[2] is True for c in today)         # NEGATIVE: today is never memoised


def test_NEGATIVE_a_failed_prior_day_is_not_memoised():
    calls = []

    def load(sym, day, force=False, include_premarket=True, include_afterhours=False):
        calls.append(day)
        return None
    fn = R1._memo_prev(load)
    assert fn("GGA", PREV) is None and fn("GGA", PREV) is None and calls == [PREV, PREV]


# ── per-prefix writes ─────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_gg1_iteration_writes_only_gajjala_1m_collections(monkeypatch):
    db, shared, st = world(monkeypatch)
    R1.run_iteration(NOW, store=st, deps=deps())
    written = {n for n, c in db.items() if c.w}
    assert written and all(n.startswith("gajjala_1m_") for n in written), written
    for name in ST.ALL:                                                  # every GG5 collection, gajjala_state too
        assert name not in db or db[name].w == 0, name
    assert {"gajjala_1m_reads", "gajjala_1m_passes", "gajjala_1m_alerts", "gajjala_1m_state"} <= written


# ── the GG1 lease ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_held_gg5_lease_never_blocks_gg1(monkeypatch):
    db, shared, st = world(monkeypatch)
    assert shared.claim_lease(RUN._utc(NOW))                              # the 🚩 pass is running
    out = R1.run_iteration(NOW, store=st, deps=deps())
    assert out["ran"] and out["lease"]["why"] == "claimed"
    assert db["gajjala_state"].docs["lease"]["status"] == "running"     # GG5's lease untouched


def test_a_gg1_cron_claim_takes_over_an_on_open_holder(monkeypatch):
    db, shared, st = world(monkeypatch)
    assert st.claim_lease(RUN._utc(NOW), source=ST.LEASE_ON_DEMAND)
    out = R1.run_iteration(NOW + timedelta(seconds=5), store=st, deps=deps())
    assert out["ran"] and out["lease"]["why"] == "taken_over"


def test_NEGATIVE_a_second_cron_loop_is_refused(monkeypatch):
    db, shared, st = world(monkeypatch)
    assert st.claim_lease(RUN._utc(NOW), source=ST.LEASE_CRON)
    calls = []
    d = deps(load_day=loader(calls=calls))
    out = R1.run_iteration(NOW + timedelta(seconds=5), store=st, deps=d)
    assert out["ran"] is False and out["reason"] == "lease held — another 1-minute iteration is running"
    assert calls == [] and d.record_status.calls == [] and d.record_potential_status.calls == []
    assert "gajjala_1m_passes" not in db or db["gajjala_1m_passes"].docs == {}


def test_a_crashed_gg1_holder_frees_itself_after_its_own_lease_sec(monkeypatch):
    db, shared, st = world(monkeypatch)
    assert st.claim_lease(RUN._utc(NOW), source=ST.LEASE_CRON)
    out = R1.run_iteration(NOW + timedelta(seconds=GC.GG1M_LEASE_SEC), store=st, deps=deps())
    assert out["ran"] is True


# ── the pass doc + the /alerts rows ───────────────────────────────────────────────────────────────────────────────
def test_the_pass_doc_carries_gg5s_strip_and_subs_with_from_pass(monkeypatch):
    db, shared, st = world(monkeypatch)
    R1.run_iteration(NOW, store=st, deps=deps(), slot={"tick": at(10, 6), "i": 2})
    doc = db["gajjala_1m_passes"].docs["2026-10-13|10:08:31"]
    for k in R1.G5_COPY_KEYS:
        assert doc[k] == G5_PASS[k], k
    assert doc["from_pass"] == "2026-10-13|10:06"
    assert set(R1.PASS_KEYS) <= set(doc) and doc["finished_at"] is not None
    assert doc["slot"] == {"tick": RUN._utc(at(10, 6)), "i": 2} and doc["on_demand"] is False
    assert doc["bars_through_et"] == "10:08" and doc["status"] == "ok"
    latest = st.latest_cron_pass()
    assert latest and latest["pass_id"] == "2026-10-13|10:08:31"
    assert shared.latest_pass()["pass_id"] == "2026-10-13|10:06"         # NEGATIVE: GG5's pointer never moves


def test_NEGATIVE_no_gg5_pass_on_file_copies_nones(monkeypatch):
    db, shared, st = world(monkeypatch, seed_pass=False)
    R1.run_iteration(NOW, store=st, deps=deps())
    doc = db["gajjala_1m_passes"].docs["2026-10-13|10:08:31"]
    assert doc["from_pass"] is None and doc["strip"] is None and doc["status"] == "ok"


def test_the_alerts_rows_are_the_two_gg1_kinds(monkeypatch):
    from supply_demand import alert_status as AS
    kinds = []
    monkeypatch.setattr(AS, "record_pass", lambda kind, counts, now, coll=None, reason=None: (kinds.append(kind),
                                                                                                True)[1])
    db, shared, st = world(monkeypatch)
    d = deps()
    d.record_status, d.record_potential_status = R1._record_status, R1._record_potential_status
    R1.run_iteration(NOW, store=st, deps=d)
    assert kinds == [V.GG1.push_kind_setup, V.GG1.push_kind_potential] == ["gajjala_1m_setup", "gajjala_1m_potential"]
    assert "gajjala_setup" not in kinds and "gajjala_potential" not in kinds     # NEGATIVE: never GG5's rows


def test_NEGATIVE_an_on_open_iteration_writes_no_alerts_row_and_rings_nothing(monkeypatch):
    db, shared, st = world(monkeypatch)
    d = deps()
    out = R1.run_on_demand(NOW, store=st, deps=d)
    assert out["ran"] and out["on_demand"] is True and out["status"] == "ok"
    assert d.record_status.calls == [] and d.record_potential_status.calls == []
    assert d.send.calls == [] and d.send_potential.calls == []
    assert out["alerts"].get("dry", 0) >= 1
    assert "gajjala_1m_alerts" not in db or db["gajjala_1m_alerts"].docs == {}
    assert "2026-10-13|10:08:31|open" in db["gajjala_1m_passes"].docs
    assert st.latest_cron_pass() is None                                 # an open never moves latest_cron


def test_shadow_potentials_are_claimed_settled_and_never_sent(monkeypatch):
    db, shared, st = world(monkeypatch)
    st.record_pass(S, NOW - timedelta(seconds=60), {"potential": {"tracked_today": 0}}, hhmm="10:07:31")
    d = deps()
    out = R1.run_iteration(NOW, store=st, deps=d)
    pot = out["potential"]
    assert pot["shadow"] >= 1 and d.send_potential.calls == []
    docs = list(db["gajjala_1m_potentials"].docs.values())
    assert any((x.get("push") or {}).get("state") == "shadow" for x in docs)
    assert "gajjala_potentials" not in db or db["gajjala_potentials"].docs == {}   # NEGATIVE: never GG5's tracker


# ── run.main: the cron path spawns, nothing else does ─────────────────────────────────────────────────────────────
def _main_env(monkeypatch, *, status="ok"):
    spawn = Rec(True)
    monkeypatch.setattr(R1, "spawn_loop", spawn)
    monkeypatch.setattr(RUN, "in_window", lambda *_a, **_k: True)
    monkeypatch.setattr(RUN, "run_pass", lambda now, **k: {"status": status})
    monkeypatch.setattr(RUN, "run_on_demand", lambda now, **k: {"status": status})
    monkeypatch.setattr(RUN, "dry_store", lambda *a, **k: None)
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    return spawn


def test_run_main_cron_path_spawns_the_loop_once(monkeypatch, caplog):
    spawn = _main_env(monkeypatch)
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")
    assert RUN.main([]) == 0 and len(spawn.calls) == 1
    assert [r for r in caplog.records if r.getMessage().startswith("gajjala 1m loop:")]


@pytest.mark.parametrize("argv", [["--dry-run"], ["--dry-run", "--now", "2026-10-13T10:41"], ["--on-demand"],
                                  ["--symbols", "GGA"], ["--now", "2026-10-13T10:41"]])
def test_NEGATIVE_the_non_cron_paths_never_spawn(monkeypatch, argv):
    spawn = _main_env(monkeypatch)
    RUN.main(argv)
    assert spawn.calls == []


def test_NEGATIVE_a_raising_spawn_keeps_the_exit_code(monkeypatch):
    _main_env(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError("fork")
    monkeypatch.setattr(R1, "spawn_loop", boom)
    assert RUN.main([]) == 0
    _main_env(monkeypatch, status="error")
    monkeypatch.setattr(R1, "spawn_loop", boom)
    assert RUN.main([]) == 1
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: False)
    assert RUN.main([]) == 1


def test_spawn_loop_starts_the_detached_loop_and_never_raises():
    spawn = Rec(type("P", (), {"pid": 7})())
    assert R1.spawn_loop(spawn) is True
    assert spawn.calls == [((list(R1.ARGV_LOOP), R1.PROC_NAME_LOOP), {})]
    assert R1.ARGV_LOOP[1:] == ("-m", "chart_maps.gajjala.run_1m", "--loop")

    def boom(*a, **k):
        raise OSError("fork failed")
    assert R1.spawn_loop(boom) is False                                  # NEGATIVE: never raises


def test_the_real_popen_is_a_new_session_holding_none_of_the_cron_jobs_pipes(monkeypatch):
    import subprocess
    seen = {}

    class P:
        pid = 9

    def fake_popen(argv, **kw):
        seen.update(kw, argv=argv)
        return P()
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(R1, "_popen", REAL_POPEN)                        # the real _popen, Popen itself patched
    assert R1.spawn_loop() is True
    assert seen["start_new_session"] is True and seen["close_fds"] is True
    assert seen["argv"] == list(R1.ARGV_LOOP) and seen["cwd"] == OD._BACKEND_DIR
    assert seen["stdin"] is subprocess.DEVNULL
    assert seen["stdout"] is not None and seen["stderr"] is not None      # NEGATIVE: never the inherited pipes


# ── run.dry_store keeps the variant ───────────────────────────────────────────────────────────────────────────────
def test_dry_store_of_a_gg1_store_records_physical_gajjala_1m_names(monkeypatch):
    db, shared, st = world(monkeypatch)
    dry = RUN.dry_store(st)
    assert dry.variant is V.GG1 and dry.shared is shared and dry.dry is True
    out = R1.run_iteration(NOW, store=dry, deps=deps(), dry=True)
    assert out["writes"] and all(n.startswith("gajjala_1m_") for n, _op in out["writes"]), out["writes"]
    assert all(c.w == 0 for c in db.values())                            # NEGATIVE: nothing landed
    assert out["sent"] == []


def test_NEGATIVE_a_gg5_dry_store_still_records_gg5_names(monkeypatch):
    real = fake_store()
    dry = RUN.dry_store(real)
    assert dry.variant is V.GG5 and dry.shared is None
    dry.set_state("x", {"a": 1})
    assert dry.writes == [("gajjala_state", "update_one")]


def test_run_1m_main_dry_run_json_writes_only_gajjala_1m_and_sends_nothing(monkeypatch, capsys):
    db, shared, st = world(monkeypatch)
    monkeypatch.setattr(ST, "for_variant", lambda v=None: st)
    monkeypatch.setattr(RUN, "_dry_load_day", loader())
    assert R1.main(["--dry-run", "--json", "--now", "2026-10-13T10:08:31"]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["writes"] and all(w[0].startswith("gajjala_1m_") for w in out["writes"])
    assert out["sent"] == [] and all(c.w == 0 for c in db.values())


def test_NEGATIVE_run_1m_main_refuses_a_non_dry_now_replay(monkeypatch):
    monkeypatch.setattr(R1, "run_iteration", lambda *a, **k: pytest.fail("never"))
    monkeypatch.setattr(R1, "loop", lambda *a, **k: pytest.fail("never"))
    assert R1.main(["--now", "2026-10-13T10:41"]) == 2
    assert R1.main(["--loop", "--now", "2026-10-13T10:41"]) == 2
    assert R1.main(["--now", "2026-10-13T21:00"]) == 0                  # outside the window: nothing, exit 0


# ── on_demand.request(variant=GG1) ────────────────────────────────────────────────────────────────────────────────
class FakeProc:
    def __init__(self):
        self.alive, self.pid = True, 4242

    def poll(self):
        return None if self.alive else 0


class Spawn:
    def __init__(self):
        self.calls, self.procs = [], []

    def __call__(self, argv, name):
        self.calls.append((list(argv), name))
        p = FakeProc()
        self.procs.append(p)
        return p


def _with_cron(st, t):
    st.record_pass(t.astimezone(ET).date(), t, {"status": "ok", "wall_s": 5.0, "n_listed": 1, "n_read": 1,
                                                "on_demand": False, "finished_at": t + timedelta(seconds=5)},
                   hhmm=t.astimezone(ET).strftime("%H:%M:%S"))
    return st


def test_on_demand_gg1_spawns_run_1m_on_demand_in_its_own_slot():
    st = _with_cron(ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL}, variant=V.GG1, shared=fake_store()),
                    at(10, 31, 10))
    spawn = Spawn()
    r = OD.request(at(10, 34, 10), store=st, spawn=spawn, variant=V.GG1)
    assert r["state"] == "started" and tuple(r) == OD.RESPONSE_KEYS
    assert spawn.calls == [(list(R1.ARGV_ON_DEMAND), OD.PROC_NAME_1M)] and OD.PROC_NAME_1M == "gajjala-1m-on-open"
    assert R1.ARGV_ON_DEMAND[1:] == ("-m", "chart_maps.gajjala.run_1m", "--on-demand")
    assert OD._STATES["gajjala_1m"]["proc"] is spawn.procs[0] and OD._STATE["proc"] is None
    r2 = OD.request(at(10, 34, 11), store=st, spawn=spawn, variant=V.GG1)
    assert r2["state"] == "waiting" and "on open" in r2["text"]
    assert len(spawn.calls) == 1


def test_NEGATIVE_a_live_gg5_child_never_makes_gg1_waiting_and_back():
    g5 = _with_cron(fake_store(), at(10, 31, 10))
    g1 = _with_cron(ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL}, variant=V.GG1, shared=g5),
                    at(10, 31, 10))
    spawn = Spawn()
    assert OD.request(at(10, 34, 10), store=g5, spawn=spawn)["state"] == "started"
    assert OD.request(at(10, 34, 11), store=g1, spawn=spawn, variant=V.GG1)["state"] == "started"
    assert [n for _a, n in spawn.calls] == [OD.PROC_NAME, OD.PROC_NAME_1M]
    OD._STATE["proc"].alive = False
    assert OD.request(at(10, 34, 12), store=g5, spawn=spawn)["state"] == "started"   # GG1's live child is not GG5's


def test_on_demand_gg1_texts_use_the_1_minute_cadence():
    g1 = ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL}, variant=V.GG1, shared=fake_store())
    r = OD.request(at(10, 34, 10), store=g1, spawn=Spawn(), variant=V.GG1)        # no GG1 cron iteration yet (A12)
    assert r["state"] == "waiting" and "no 1-minute pass has landed" in r["text"]
    g1.claim_lease(RUN._utc(at(10, 34, 20)), source=ST.LEASE_CRON)
    r = OD.request(at(10, 34, 30), store=_with_cron(g1, at(10, 33, 30)), spawn=Spawn(), variant=V.GG1)
    assert r["state"] == "waiting" and r["text"].startswith("🔄 the 1-minute pass started")
    assert "5-minute" not in r["text"]                                    # NEGATIVE: never GG5's word on GG1


def test_NEGATIVE_gg5_request_answers_byte_identical_with_or_without_the_variant():
    for t in (at(10, 34, 10), at(3, 0), at(10, 31, 40)):
        a = OD.request(t, store=_with_cron(fake_store(), at(10, 31, 10)), spawn=Spawn())
        OD._STATE.update(proc=None)
        b = OD.request(t, store=_with_cron(fake_store(), at(10, 31, 10)), spawn=Spawn(), variant=V.GG5)
        OD._STATE.update(proc=None)
        assert json.dumps(a, default=str) == json.dumps(b, default=str)
    st = fake_store()
    r = OD.request(at(10, 34), store=st, spawn=Spawn())
    assert "no 5-minute pass has landed" in r["text"]                     # GG5's word unchanged


def test_on_demand_gg1_default_store_is_the_variant_store(monkeypatch):
    g1 = ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL}, variant=V.GG1, shared=fake_store())
    seen = []
    monkeypatch.setattr(ST, "for_variant", lambda v=None: (seen.append(v), g1)[1])
    monkeypatch.setattr(ST, "default", lambda: pytest.fail("GG1 never opens GG5's store as its own"))
    r = OD.request(at(10, 34, 10), spawn=Spawn(), variant=V.GG1)
    assert seen == [V.GG1] and r["state"] in OD.STATES


# ── nightly: GG1 graded after GG5 ─────────────────────────────────────────────────────────────────────────────────
def test_nightly_grades_gg1_after_gg5(monkeypatch, capsys):
    from chart_maps.gajjala import ledger as LG
    order = []
    g5 = fake_store()
    g1 = ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL}, variant=V.GG1, shared=g5)
    monkeypatch.setattr(ST, "default", lambda: g5)
    monkeypatch.setattr(ST, "for_variant", lambda v=None: g1 if v is V.GG1 else g5)
    monkeypatch.setattr(NG, "run", lambda session, *, store=None, steps=NG.STEPS: (order.append(("gg5", store)),
                                                                                 {"errors": [], "grade": {"n": 1}})[1])
    monkeypatch.setattr(LG, "grade_step", lambda store, now, **k: (order.append(("gg1", store)), {"n": 2})[1])
    assert NG.main([]) == 0
    assert order == [("gg5", g5), ("gg1", g1)]
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["gajjala_1m"] == {"grade": {"n": 2}} and out["grade"] == {"n": 1}


def test_NEGATIVE_a_raising_gg1_grade_keeps_exit_0_and_gg5s_summary(monkeypatch, capsys):
    from chart_maps.gajjala import ledger as LG
    g5 = fake_store()
    monkeypatch.setattr(ST, "default", lambda: g5)
    monkeypatch.setattr(ST, "for_variant", lambda v=None: ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL},
                                                                         variant=V.GG1, shared=g5))
    monkeypatch.setattr(NG, "run", lambda session, *, store=None, steps=NG.STEPS: {"errors": [], "grade": {"n": 1},
                                                                                  "names": 3})

    def boom(*a, **k):
        raise RuntimeError("ledger exploded")
    monkeypatch.setattr(LG, "grade_step", boom)
    assert NG.main([]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["errors"] == [] and out["grade"] == {"n": 1} and out["names"] == 3
    assert out["gajjala_1m"] == {"error": "grade: RuntimeError"}


def test_NEGATIVE_steps_without_grade_never_grade_gg1(monkeypatch):
    from chart_maps.gajjala import ledger as LG
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    monkeypatch.setattr(NG, "run", lambda session, *, store=None, steps=NG.STEPS: {"errors": []})
    monkeypatch.setattr(LG, "grade_step", lambda *a, **k: pytest.fail("no grade step asked"))
    assert NG.main(["--steps", "history"]) == 0
