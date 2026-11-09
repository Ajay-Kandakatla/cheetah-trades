"""⏱ chart_maps/gajjala/bar_close.py + the run.py hook — the bar-finality PROBE (GG LIVE spec §3.4, WP-C, 2026-11-09).

Ajay 2026-11-09: "can you modify and make it more live with websockets or something else where there is a low latency
monitoring on the prices action changes please?" / "same for reuglar Gajjlas tab as well need it to be more live"

Pinned: the target clock (boundaries), the mode switch (an env value only LOWERS it), every refusal (off, closed day,
outside the window, woke late) with NO fetch / lease / pass, the probe rows (at30 / at60, changed + its field list,
v_delta, regular / extended), the closed-bar rule (the forming bar is never read), a failed fetch = no row and no retry,
"probe complete" after GAJJALA_BAR_FINAL_PROBE_SESSIONS dates (no fetch), the GG1M_MAX_NAMES cap, probe = NO
claim_lease / run_pass / push; the `on` branch with the constant PATCHED (run_pass(None) on the wall clock and the cron
lease, the next `:x1` tick gap-refused with no snapshot, the fallback tick when the child is absent); the cron-path spawn
(one per invocation, also when gap-refused; never on the other paths; never in mode off; the child never spawns).
No test reaches a real spawn, a real clock sleep or Massive.
"""
from __future__ import annotations

import ast
import logging
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import bar_close as BC
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala import store as ST
from tests.test_gajjala_run import make_deps
from tests.test_gajjala_store import FakeColl, fake_store

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
S = date(2026, 10, 13)                                   # a Tuesday (market day)
REAL_POPEN = R1._popen
REAL_RUN_PASS = RUN.run_pass
REAL_UTC = RUN._utc
RUN_SRC = (Path(RUN.__file__).resolve().parent / "run.py").read_text(encoding="utf-8")


def at(hh, mm, ss=0.0, d=S):
    whole = int(ss)
    return datetime(d.year, d.month, d.day, hh, mm, whole, int(round((ss - whole) * 1e6)), tzinfo=ET)


class Rec:
    def __init__(self, ret=None):
        self.calls = []
        self.ret = ret

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self.ret(*a, **k) if callable(self.ret) else self.ret


class Clock:
    """wall() / sleep(s): a sleep advances the clock by s + `oversleep` (a host that woke late); a list = per sleep."""

    def __init__(self, t, oversleep=0.0):
        self.t = t.astimezone(UTC)
        self.oversleep = oversleep
        self.slept: list = []

    def wall(self):
        return self.t

    def sleep(self, s):
        over = self.oversleep
        if isinstance(over, (list, tuple)):
            over = over[len(self.slept)] if len(self.slept) < len(over) else 0.0
        self.slept.append(s)
        self.t = self.t + timedelta(seconds=s + over)


def rows(coll) -> dict:
    """The probe's ROWS only (the claim docs and the completion marker carry no `date`)."""
    return {k: d for k, d in coll.docs.items() if d.get("date")}


def _fail(what):
    def f(*a, **k):
        pytest.fail(what)
    return f


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    monkeypatch.delenv(BC.MODE_ENV, raising=False)
    # NEGATIVE guard for the whole file: no test reaches a real spawn (every clock here is a Clock — no real sleep)
    monkeypatch.setattr(R1, "_popen", _fail("a test reached the real spawn"))


# ── minute bars (naive-UTC index = the minute START, the minute loader's shape) ──────────────────────────────────────
def minutes(day, start: str, rows: list, session="rth", tagged=True) -> pd.DataFrame:
    t0 = datetime.combine(day, datetime.strptime(start, "%H:%M").time(), tzinfo=ET)
    idx = [pd.Timestamp((t0 + timedelta(minutes=k)).astimezone(UTC).replace(tzinfo=None)) for k in range(len(rows))]
    data = [{"open": o, "high": h, "low": lo, "close": c, "volume": v} for o, h, lo, c, v in rows]
    df = pd.DataFrame(data, index=pd.DatetimeIndex(idx))
    if tagged:
        df["session"] = session
    return df


# 09:55 … 10:04 (the 10:00 and 10:05 bars) + the FORMING 10:05 minute (bucket 10:05–10:10) with a wild high
BASE = [(10.0, 10.1, 9.9, 10.0, 100)] * 5 + [(10.0, 10.2, 9.95, 10.1, 200), (10.1, 10.3, 10.0, 10.2, 300),
                                             (10.2, 10.25, 10.1, 10.2, 400), (10.2, 10.4, 10.15, 10.35, 500),
                                             (10.35, 10.5, 10.3, 10.45, 1000)]
FORMING = [(10.45, 99.0, 10.4, 10.5, 9_999)]
LATE = BASE[:-1] + [(10.35, 10.6, 10.3, 10.45, 1500)]     # a late print on the 10:04 minute: new high + volume
TARGET = at(10, 5, 30)
WANT30 = {"o": 10.0, "h": 10.5, "l": 9.95, "c": 10.45, "v": 2400.0}


def df_base():
    return minutes(S, "09:55", BASE + FORMING)


def df_late():
    return minutes(S, "09:55", LATE + FORMING)


def world(monkeypatch, names=("GGA",)):
    """(db, shared): every collection by name in `db` (FakeColl); GG5's store seeded with today's qualifiers."""
    db: dict = {}
    monkeypatch.setattr(ST, "_coll", lambda name: db.setdefault(name, FakeColl()))
    shared = ST.GajjalaStore()
    rows = [{"symbol": s, "price": 11.2, "prev_close": 8.0, "change_pct": 90.0 - i, "volume": 3_000_000}
            for i, s in enumerate(names)]
    shared.record_qualifiers(S, at(10, 1), rows, "rth")
    for c in db.values():
        c.writes = 0
    return db, shared


def loader(clock, *, first=df_base, second=df_base, fail30=(), fail60=(), calls=None):
    """today's minutes: `first()` before the at60 moment, `second()` from it; a name in fail30 / fail60 → None / raise."""
    cut = BC.at60_moment(TARGET).astimezone(UTC)

    def load_day(sym, day, force=False, include_premarket=True, include_afterhours=False):
        late = clock.wall() >= cut
        if calls is not None:
            calls.append((sym, day, bool(force), "at60" if late else "at30"))
        if not late and sym in fail30:
            return None
        if late and sym in fail60:
            raise RuntimeError("429")
        return (second if late else first)()
    return load_day


# ── the clock ─────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("now,want", [(at(10, 3, 12), at(10, 5, 30)), (at(10, 5, 29.9), at(10, 5, 30)),
                                      (at(10, 5, 30.1), at(10, 10, 30)), (at(19, 58), at(20, 0, 30)),
                                      (at(10, 1, 4), at(10, 5, 30)), (at(4, 1), at(4, 5, 30))])
def test_next_target(now, want):
    got = BC.next_target(now)
    assert got == want and got.tzinfo is not None


def test_NEGATIVE_the_target_itself_is_not_strictly_after_it():
    assert BC.next_target(at(10, 5, 30)) == at(10, 10, 30)             # strictly after: never the same instant
    assert BC.next_target(at(10, 5, 30).astimezone(UTC)) == at(10, 10, 30)   # any tz in, the ET grid out


def test_the_bar_and_the_second_read_are_derived():
    assert BC.bar_label(TARGET) == at(10, 5)
    assert BC.at60_moment(TARGET) == at(10, 6)                          # = close + PASS_MINUTE_OFFSET min (the :x1 read)
    assert (BC.at60_moment(TARGET) - TARGET).total_seconds() == GC.BAR_CLOSE_LATE_MAX_SEC


# ── the switch ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_mode_ships_probe():
    assert GC.GAJJALA_BAR_CLOSE_MODE == "probe" and BC.mode() == "probe"


@pytest.mark.parametrize("const,env,want", [("probe", "off", "off"), ("probe", "OFF", "off"), ("on", "probe", "probe"),
                                            ("on", "off", "off"), ("on", "", "on"), ("probe", "garbage", "probe")])
def test_env_only_lowers(monkeypatch, const, env, want):
    monkeypatch.setattr(GC, "GAJJALA_BAR_CLOSE_MODE", const)
    monkeypatch.setenv(BC.MODE_ENV, env)
    assert BC.mode() == want


@pytest.mark.parametrize("const,env", [("probe", "on"), ("off", "on"), ("off", "probe")])
def test_NEGATIVE_env_never_raises_the_mode(monkeypatch, const, env):
    monkeypatch.setattr(GC, "GAJJALA_BAR_CLOSE_MODE", const)
    monkeypatch.setenv(BC.MODE_ENV, env)
    assert BC.mode() == const


def test_NEGATIVE_an_unknown_constant_reads_off(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_BAR_CLOSE_MODE", "fast")
    assert BC.mode() == "off"


# ── refusals: no sleep, no fetch, no lease, no pass ─────────────────────────────────────────────────────────────
def _no_side_effects(monkeypatch):
    monkeypatch.setattr(RUN, "run_pass", _fail("a refused child never runs a pass"))
    monkeypatch.setattr(ST.GajjalaStore, "claim_lease", _fail("a refused child never claims the lease"))
    monkeypatch.setattr(R1, "names_for", _fail("a refused child never reads the names"))


def _refused(monkeypatch, now, *, clock=None, **kw):
    _no_side_effects(monkeypatch)
    calls: list = []
    clock = clock or Clock(now)
    out = BC.wait_and_run(now, sleep=clock.sleep, wall=clock.wall, coll=FakeColl(), shared=object(),
                          load_day=loader(clock, calls=calls), **kw)
    assert out["ran"] is False and calls == []
    return out, clock


def test_NEGATIVE_mode_off_refuses_before_sleeping(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.bar_close")
    monkeypatch.setattr(GC, "GAJJALA_BAR_CLOSE_MODE", "off")
    out, clock = _refused(monkeypatch, at(10, 3, 12))
    assert out["reason"] == BC.R_OFF and clock.slept == []
    assert [r.getMessage() for r in caplog.records] == [f"gajjala bar-close: {BC.R_OFF}"]   # one log line


def test_NEGATIVE_env_lowering_probe_to_off_refuses(monkeypatch):
    monkeypatch.setenv(BC.MODE_ENV, "off")
    out, clock = _refused(monkeypatch, at(10, 3, 12))
    assert out["reason"] == BC.R_OFF and clock.slept == []


@pytest.mark.parametrize("day,word", [(date(2026, 11, 26), "holiday 2026-11-26"), (date(2026, 10, 17), "weekend")])
def test_NEGATIVE_a_closed_day_refuses(monkeypatch, day, word):
    out, clock = _refused(monkeypatch, at(10, 3, 12, d=day))
    assert out["reason"] == word and clock.slept == []


def test_NEGATIVE_20_05_30_is_outside_the_window(monkeypatch):
    out, clock = _refused(monkeypatch, at(20, 1, 10))
    assert out["target"] == at(20, 5, 30) and out["reason"] == BC.R_WINDOW and clock.slept == []


def test_the_20_00_30_target_is_inside_the_window():
    assert BC.refusal(at(20, 0, 30)) is None and BC.refusal(at(4, 5, 30)) is None


def test_NEGATIVE_woke_31_s_late_refuses_with_the_late_words(monkeypatch):
    clock = Clock(at(10, 3, 12), oversleep=31)
    out, _ = _refused(monkeypatch, at(10, 3, 12), clock=clock)
    assert out["reason"].startswith(BC.R_LATE) and "31 s after 10:05:30 ET" in out["reason"]
    assert clock.slept == [pytest.approx(138.0)]


def test_NEGATIVE_woke_late_in_mode_on_runs_no_pass(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_BAR_CLOSE_MODE", "on")
    clock = Clock(at(10, 3, 12), oversleep=31)
    out, _ = _refused(monkeypatch, at(10, 3, 12), clock=clock, run_pass=_fail("late → no pass"))
    assert out["reason"].startswith(BC.R_LATE)


# ── the probe ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _probe(monkeypatch, *, names=("GGA",), oversleep=0.0, coll=None, **ld):
    db, shared = world(monkeypatch, names)
    clock = Clock(at(10, 3, 12), oversleep=oversleep)
    calls: list = []
    coll = coll if coll is not None else db.setdefault(BC.COLL, FakeColl())
    out = BC.wait_and_run(at(10, 3, 12), sleep=clock.sleep, wall=clock.wall, coll=coll, shared=shared,
                          load_day=loader(clock, calls=calls, **ld))
    return out, coll, calls, clock, db


def test_probe_writes_at30_and_at60_unchanged(monkeypatch):
    out, coll, calls, clock, _db = _probe(monkeypatch)
    assert out["ran"] is True and out["probe"]["rows"] == 1 and out["probe"]["changed"] == 0
    row = coll.docs["2026-10-13|10:05|GGA"]
    assert {k: row["at30"][k] for k in "ohlcv"} == WANT30 == {k: row["at60"][k] for k in "ohlcv"}
    assert row["changed"] is False and row["fields_changed"] == [] and row["v_delta"] == 0.0 and row["late"] is False
    assert BC.COMPLETE_ID not in coll.docs                               # NEGATIVE: one date → no marker
    assert (row["date"], row["symbol"], row["bar_t"], row["session_part"]) == ("2026-10-13", "GGA", "2026-10-13 10:05",
                                                                             "regular")
    assert row["at30"]["read_at"] == TARGET.astimezone(UTC)
    assert row["at60"]["read_at"] == BC.at60_moment(TARGET).astimezone(UTC)
    assert [c[3] for c in calls] == ["at30", "at60"] and all(c[2] is True for c in calls)   # force=True both times
    assert clock.slept == [pytest.approx(138.0), pytest.approx(30.0)]                    # to the target, then +30 s
    assert isinstance(row["at"], datetime)
    assert coll.indexes == [((("at", 1),), {"expireAfterSeconds": GC.LEDGER_TTL_DAYS * 86400})]


def test_probe_a_bar_that_changed_names_its_fields(monkeypatch):
    out, coll, _calls, _clock, _db = _probe(monkeypatch, second=df_late)
    row = coll.docs["2026-10-13|10:05|GGA"]
    assert row["changed"] is True and row["fields_changed"] == ["h", "v"] and row["v_delta"] == 500.0
    assert row["at60"]["h"] == 10.6 and row["at30"]["h"] == 10.5
    assert out["probe"]["changed"] == 1


def test_NEGATIVE_the_forming_bar_is_never_read():
    raw = df_base()
    bar = BC.read_bar(raw, at(10, 5), TARGET)
    assert bar["h"] == 10.5 and bar["v"] == 2400.0                      # the 10:05 minute (h 99) sits in the 10:10 bar
    assert BC.read_bar(raw, at(10, 10), TARGET) is None                 # the forming bucket: not closed at 10:05:30
    assert BC.read_bar(raw, at(10, 5), at(10, 5, 29.9)) is None         # BAR_SETTLE_SEC not yet passed → not read
    assert BC.read_bar(raw, at(10, 10), at(10, 10, 30))["h"] == 99.0   # (the same bucket once IT has settled)


def test_NEGATIVE_a_minute_stamped_after_the_settle_cut_is_excluded():
    """A print on the forming minute changes nothing in the bar read at close + BAR_SETTLE_SEC."""
    with_forming = BC.read_bar(df_base(), at(10, 5), TARGET)
    without = BC.read_bar(minutes(S, "09:55", BASE), at(10, 5), TARGET)
    assert {k: with_forming[k] for k in "ohlcv"} == {k: without[k] for k in "ohlcv"}


def test_extended_and_untagged_session_parts(monkeypatch):
    pm = minutes(S, "08:00", BASE[5:], session="premarket")
    assert BC._session_part(BC.read_bar(pm, at(8, 5), at(8, 5, 30)), at(8, 5)) == "extended"
    plain = minutes(S, "10:00", BASE[5:], tagged=False)
    assert BC._session_part(BC.read_bar(plain, at(10, 5), TARGET), at(10, 5)) == "regular"
    plain_pm = minutes(S, "08:00", BASE[5:], tagged=False)
    assert BC._session_part(BC.read_bar(plain_pm, at(8, 5), at(8, 5, 30)), at(8, 5)) == "extended"


def test_NEGATIVE_a_failed_fetch_writes_no_row_and_is_never_retried(monkeypatch):
    out, coll, calls, _clock, _db = _probe(monkeypatch, names=("GGA", "BAD", "BAD60"), fail30=("BAD",),
                                           fail60=("BAD60",))
    assert sorted(rows(coll)) == ["2026-10-13|10:05|GGA"]
    assert [c for c in calls if c[0] == "BAD"] == [("BAD", S, True, "at30")]          # once; no at60, no retry
    assert [c[3] for c in calls if c[0] == "BAD60"] == ["at30", "at60"]                # one each, no retry
    assert (out["probe"]["failed_at30"], out["probe"]["failed_at60"], out["probe"]["rows"]) == (1, 1, 1)


def test_NEGATIVE_a_name_with_no_closed_bar_writes_no_row(monkeypatch):
    out, coll, _calls, _clock, _db = _probe(monkeypatch, first=lambda: minutes(S, "09:55", BASE[:5]))
    assert rows(coll) == {} and out["probe"]["rows"] == 0


def test_NEGATIVE_probe_complete_after_the_sessions_fetches_nothing(monkeypatch):
    n = GC.GAJJALA_BAR_FINAL_PROBE_SESSIONS
    full = FakeColl([{"_id": f"d{i}", "date": f"2026-10-0{i + 1}"} for i in range(n)])
    out, coll, calls, clock, _db = _probe(monkeypatch, coll=full)
    _ = coll
    assert out["ran"] is False and out["reason"] == BC.R_COMPLETE == "probe complete — HIS CALL #5"
    assert calls == [] and clock.slept == []


def test_one_session_short_of_complete_still_probes(monkeypatch):
    n = GC.GAJJALA_BAR_FINAL_PROBE_SESSIONS
    short = FakeColl([{"_id": f"d{i}", "date": f"2026-10-0{i + 1}"} for i in range(n - 1)])
    db: dict = {}
    monkeypatch.setattr(ST, "_coll", lambda name: short if name == BC.COLL else db.setdefault(name, FakeColl()))
    shared = ST.GajjalaStore()
    shared.record_qualifiers(S, at(10, 1), [{"symbol": "GGA", "price": 1, "prev_close": 1, "change_pct": 50,
                                             "volume": 1}], "rth")
    clock = Clock(at(10, 3, 12))
    out = BC.wait_and_run(at(10, 3, 12), sleep=clock.sleep, wall=clock.wall, shared=shared, load_day=loader(clock))
    assert out["ran"] is True and "2026-10-13|10:05|GGA" in short.docs
    marker = short.docs[BC.COMPLETE_ID]                                  # the 5th date landed → the marker, once
    assert "at" not in marker and "date" not in marker and len(marker["dates"]) == n
    assert out["probe"]["complete"] is True and BC.probe_complete(short) is True


def test_NEGATIVE_names_capped_at_gg1m_max_names(monkeypatch):
    names = tuple(f"N{i:03d}" for i in range(GC.GG1M_MAX_NAMES + 1))
    out, coll, calls, _clock, _db = _probe(monkeypatch, names=names)
    fetched = {c[0] for c in calls}
    assert len(fetched) == GC.GG1M_MAX_NAMES and names[-1] not in fetched   # the 61st (lowest change) never fetched
    assert out["probe"]["names"] == GC.GG1M_MAX_NAMES and len(rows(coll)) == GC.GG1M_MAX_NAMES


def test_NEGATIVE_the_cap_holds_even_if_the_names_source_widened(monkeypatch):
    names = [f"N{i:03d}" for i in range(GC.GG1M_MAX_NAMES + 1)]
    monkeypatch.setattr(R1, "names_for", lambda shared, session: (names, 0))
    clock = Clock(TARGET)
    calls: list = []
    res = BC.probe(TARGET, coll=FakeColl(), shared=object(), load_day=loader(clock, calls=calls), sleep=clock.sleep,
                   wall=clock.wall)
    assert res["names"] == GC.GG1M_MAX_NAMES and names[-1] not in {c[0] for c in calls}


def test_NEGATIVE_probe_mode_claims_no_lease_runs_no_pass_and_pushes_nothing(monkeypatch):
    from push import hooks
    from chart_maps.gajjala import alerts as AL
    from chart_maps.gajjala import potential as PT
    monkeypatch.setattr(RUN, "run_pass", _fail("probe → no pass"))
    monkeypatch.setattr(ST.GajjalaStore, "claim_lease", _fail("probe → no lease"))
    monkeypatch.setattr(AL, "run_pass", _fail("probe → no A+ gate"))
    monkeypatch.setattr(PT, "run_pass", _fail("probe → no 🧠 gate"))
    for name in ("notify_gajjala_setup", "notify_gajjala_potential", "notify_gajjala_1m_setup"):
        monkeypatch.setattr(hooks, name, _fail("probe → no push"))
    out, coll, _calls, _clock, db = _probe(monkeypatch, names=("GGA", "GGB"))
    assert out["probe"]["rows"] == 2
    assert {n: c.writes for n, c in db.items() if c.writes} == {BC.COLL: 3}    # the ONLY writes: the claim + 2 rows
    assert len(rows(coll)) == 2


# ── `on` (HIS CALL #5) — the constant PATCHED here only ─────────────────────────────────────────────────────────────
def _on_world(monkeypatch, start, *, oversleep=0.0):
    monkeypatch.setattr(GC, "GAJJALA_BAR_CLOSE_MODE", "on")
    st = fake_store()
    deps, snapshot, _send, _status = make_deps()
    deps.audited_store = lambda _st: None
    clock = Clock(start, oversleep=oversleep)
    monkeypatch.setattr(RUN, "_utc", lambda now=None: REAL_UTC(clock.wall() if now is None else now))
    monkeypatch.setattr(ST, "default", lambda: st)
    monkeypatch.setattr(RUN, "_cron_deps", lambda: deps)
    rp = Rec(lambda *a, **k: REAL_RUN_PASS(*a, **k))
    monkeypatch.setattr(RUN, "run_pass", rp)
    for name in ("_spawn_1m", "_spawn_luk", "_spawn_bar_close"):
        monkeypatch.setattr(RUN, name, _fail(f"the child never calls {name}"))
    monkeypatch.setattr(BC, "spawn_child", _fail("the child never spawns a child"))
    monkeypatch.setattr(R1, "spawn_loop", _fail("the child never spawns the 1-minute loop"))
    monkeypatch.setattr(BC, "probe", _fail("mode on never probes"))
    return st, deps, snapshot, clock, rp


def _lease_start(st):
    return REAL_UTC(st.coll(ST.STATE).docs[ST.LEASE_ID]["last_cron_started_at"])


def test_on_the_child_runs_the_cron_pass_on_the_wall_clock(monkeypatch):
    st, deps, snapshot, clock, rp = _on_world(monkeypatch, at(10, 3, 12), oversleep=7)
    out = BC.wait_and_run(sleep=clock.sleep, wall=clock.wall)
    assert out["ran"] is True and len(rp.calls) == 1
    (args, kw) = rp.calls[0]
    assert args == (None,)                                              # NEGATIVE: never now=target (replay semantics)
    assert kw["store"] is st and kw["deps"] is deps
    target = TARGET.astimezone(UTC)
    assert target <= _lease_start(st) <= target + timedelta(seconds=GC.BAR_CLOSE_LATE_MAX_SEC)
    assert _lease_start(st) == target + timedelta(seconds=7)
    assert len(snapshot.calls) == 1 and out["pass"]["ran"] is True


def test_NEGATIVE_on_the_x1_tick_30_s_later_is_gap_refused_with_no_snapshot(monkeypatch):
    st, deps, snapshot, clock, _rp = _on_world(monkeypatch, at(10, 3, 12))
    BC.wait_and_run(sleep=clock.sleep, wall=clock.wall)
    assert len(snapshot.calls) == 1
    clock.t = at(10, 6).astimezone(UTC)                                  # the crontab's 10:06 tick
    deps2, snap2, _s, _st = make_deps()
    tick = REAL_RUN_PASS(None, store=st, deps=deps2)
    assert tick["ran"] is False and tick["lease"]["why"] == "gap" and tick["reason"] == RUN._LEASE_REASON["gap"]
    assert snap2.calls == []                                            # no double pass


def test_on_fallback_a_dead_child_leaves_the_tick_its_pass(monkeypatch):
    st, deps, snapshot, clock, _rp = _on_world(monkeypatch, at(9, 58))
    BC.wait_and_run(sleep=clock.sleep, wall=clock.wall)                   # the 10:00:30 pass
    assert _lease_start(st) == at(10, 0, 30).astimezone(UTC)
    clock.t = at(10, 6).astimezone(UTC)                                  # no 10:05:30 child; the tick 330 s later
    deps2, snap2, _s, _st = make_deps()
    deps2.audited_store = lambda _st: None
    tick = REAL_RUN_PASS(None, store=st, deps=deps2)
    assert tick["lease"]["why"] == "claimed" and len(snap2.calls) == 1   # today's timing


# ── the spawn (run.main's cron path) ─────────────────────────────────────────────────────────────────────────────
def _main_env(monkeypatch, *, status="ok", ret=None):
    child = Rec(True)
    monkeypatch.setattr(BC, "spawn_child", child)
    monkeypatch.setattr(R1, "spawn_loop", Rec(True))
    monkeypatch.setattr(RUN, "in_window", lambda *_a, **_k: True)
    rp = Rec(ret if ret is not None else {"status": status})
    monkeypatch.setattr(RUN, "run_pass", rp)
    monkeypatch.setattr(RUN, "run_on_demand", Rec({"status": status}))
    monkeypatch.setattr(RUN, "dry_store", lambda *a, **k: None)
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    return child, rp


def test_the_cron_path_spawns_one_child(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")
    child, _rp = _main_env(monkeypatch)
    assert RUN.main([]) == 0 and len(child.calls) == 1
    assert [r.getMessage() for r in caplog.records if r.getMessage().startswith("gajjala bar-close:")] == [
        "gajjala bar-close: spawned"]


def test_the_cron_path_spawns_one_child_also_when_gap_refused(monkeypatch):
    child, _rp = _main_env(monkeypatch, ret={"ran": False, "reason": RUN._LEASE_REASON["gap"],
                                            "lease": {"why": "gap"}})
    assert RUN.main([]) == 0 and len(child.calls) == 1


def test_the_cron_path_keeps_its_deps(monkeypatch):
    from chart_maps.gajjala import promo_names as PN
    from chart_maps.gajjala import trader_names as TN
    _child, rp = _main_env(monkeypatch)
    RUN.main([])
    assert rp.calls[0][1]["deps"] == RUN.Deps(trader_fetch=TN.default_fetch, promo_tags=PN.default_tags)
    assert RUN._cron_deps() == rp.calls[0][1]["deps"]                    # ONE definition for both paths


@pytest.mark.parametrize("argv", [["--dry-run"], ["--dry-run", "--now", "2026-10-13T10:41"], ["--on-demand"],
                                  ["--symbols", "GGA"], ["--now", "2026-10-13T10:41"], ["--at-bar-close"]])
def test_NEGATIVE_the_other_paths_never_spawn(monkeypatch, argv):
    child, _rp = _main_env(monkeypatch)
    monkeypatch.setattr(BC, "wait_and_run", Rec({"ran": False, "reason": "x"}))
    RUN.main(argv)
    assert child.calls == []


@pytest.mark.parametrize("how", ["const", "env"])
def test_NEGATIVE_mode_off_never_spawns(monkeypatch, caplog, how):
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")
    child, _rp = _main_env(monkeypatch)
    if how == "const":
        monkeypatch.setattr(GC, "GAJJALA_BAR_CLOSE_MODE", "off")
    else:
        monkeypatch.setenv(BC.MODE_ENV, "off")
    assert RUN.main([]) == 0 and child.calls == []
    assert any(r.getMessage() == "gajjala bar-close: off (GAJJALA_BAR_CLOSE_MODE) — not spawned"
               for r in caplog.records)


def test_NEGATIVE_a_raising_spawn_keeps_the_exit_code(monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")
    def _boom(*a, **k):
        raise RuntimeError("fork")
    _main_env(monkeypatch)
    monkeypatch.setattr(BC, "spawn_child", _boom)
    assert RUN.main([]) == 0
    assert any(r.getMessage() == "gajjala bar-close: spawn step failed: RuntimeError" for r in caplog.records)
    _main_env(monkeypatch, status="error")
    monkeypatch.setattr(BC, "spawn_child", _boom)
    assert RUN.main([]) == 1
    _main_env(monkeypatch)
    monkeypatch.setattr(BC, "spawn_child", lambda *a, **k: False)
    assert RUN.main([]) == 0


def test_the_child_path_never_spawns_and_exits_on_its_own_words(monkeypatch):
    for name in ("_spawn_1m", "_spawn_luk", "_spawn_bar_close"):
        monkeypatch.setattr(RUN, name, _fail(f"--at-bar-close never calls {name}"))
    monkeypatch.setattr(RUN, "run_pass", _fail("--at-bar-close in probe never runs the pass"))
    monkeypatch.setattr(RUN, "in_window", _fail("the child's window check is bar_close's (on the target)"))
    wr = Rec({"ran": False, "reason": BC.R_OFF})
    monkeypatch.setattr(BC, "wait_and_run", wr)
    assert RUN.main(["--at-bar-close"]) == 0 and wr.calls == [((), {})]       # wall clock, no args
    monkeypatch.setattr(BC, "wait_and_run", Rec({"ran": True, "status": "error"}))
    assert RUN.main(["--at-bar-close"]) == 1


def test_spawn_child_argv_and_never_raises():
    spawn = Rec(type("P", (), {"pid": 7})())
    assert BC.spawn_child(spawn) is True
    assert spawn.calls == [((list(BC.ARGV_CHILD), BC.PROC_NAME), {})]
    assert BC.ARGV_CHILD[1:] == ("-m", "chart_maps.gajjala.run", "--at-bar-close")

    def boom(*a, **k):
        raise OSError("fork failed")
    assert BC.spawn_child(boom) is False                                 # NEGATIVE: never raises


def test_NEGATIVE_no_real_process_under_pytest():
    assert BC.spawn_child() is False                                      # the autouse guard would fail on _popen


def test_the_real_popen_is_a_detached_session(monkeypatch):
    seen = {}

    class P:
        pid = 9

    def fake_popen(argv, **kw):
        seen.update(kw, argv=argv)
        return P()
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    assert BC.spawn_child(REAL_POPEN) is True                             # run_1m's real _popen, Popen patched
    assert seen["start_new_session"] is True and seen["close_fds"] is True
    assert seen["argv"] == list(BC.ARGV_CHILD) and seen["stdin"] is subprocess.DEVNULL


def test_the_hook_is_called_once_after_the_1m_and_the_other_hook():
    tree = ast.parse(RUN_SRC)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    found = []
    for n in ast.walk(main):
        body = getattr(n, "body", None)
        if isinstance(body, list):
            for i, stmt in enumerate(body):
                if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
                        and isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "_spawn_bar_close"):
                    found.append([s.value.func.id for s in body[:i] if isinstance(s, ast.Expr)
                                  and isinstance(s.value, ast.Call) and isinstance(s.value.func, ast.Name)])
    assert len(found) == 1 and found[0][-2:] == ["_spawn_1m", "_spawn_luk"]


# ── the 1-minute loop vs a `:x5:30` read (doc arithmetic) ─────────────────────────────────────────────────────────
def test_the_1m_loop_grid_ends_before_the_next_target():
    """On the :30 grid the last 1-minute start that fits the slot is :x4:30; its bar budget ends 25 s before :x5:30."""
    tick, next_tick = R1.slot_of(at(10, 1, 8))
    start, last = at(10, 1, 8), None
    while R1.fits(start, next_tick):
        last = start
        start = R1.next_start(start)
    assert last == at(10, 4, 30)
    end = last + timedelta(seconds=GC.GG1M_MINUTE_BUDGET_SEC)
    assert end == at(10, 5, 5) and end < BC.next_target(tick)
    latest_fit = next_tick - timedelta(seconds=GC.GG1M_MINUTE_BUDGET_SEC + GC.GG1M_SLOT_MARGIN_SEC)
    assert latest_fit == at(10, 5, 5)                                     # an OVERRUN start ≤ :x5:05 can budget to :x5:40


# ── what does NOT change ──────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_pass_timing_constants_are_untouched():
    assert (GC.PASS_MINUTE_OFFSET, GC.PASS_CADENCE_SEC, GC.BAR_SETTLE_SEC, GC.PASS_BUDGET_SEC, GC.LEASE_SEC,
            GC.LEASE_MIN_GAP_SEC) == (1, 300, 30, 240, 280, 240)
    lines = [ln for ln in (Path(RUN.__file__).resolve().parents[2] / "crontab").read_text().splitlines()
             if "chart_maps.gajjala.run" in ln and not ln.lstrip().startswith("#")]
    assert any(ln.split()[:5] == ["1-56/5", "4-20", "*", "*", "1-5"] for ln in lines)   # the `:x1` minute, unchanged
    assert not [ln for ln in lines if "--at-bar-close" in ln]              # the child is spawned, never a crontab line


# ── critic review 2026-11-09: the marker, the worker cap, the late second read, one child per target ──────────────
def test_NEGATIVE_expired_rows_with_the_marker_never_probe_again(monkeypatch):
    marker_only = FakeColl([{"_id": BC.COMPLETE_ID, "kind": "marker", "dates": ["d"] * 5}])   # every row TTL'd away
    out, _coll, calls, clock, _db = _probe(monkeypatch, coll=marker_only)
    assert out["reason"] == BC.R_COMPLETE and calls == [] and clock.slept == []
    assert list(marker_only.docs) == [BC.COMPLETE_ID]                    # no claim, no row


def test_no_marker_and_four_dates_still_fetches(monkeypatch):
    four = FakeColl([{"_id": f"d{i}", "date": f"2026-10-0{i + 1}"} for i in range(GC.GAJJALA_BAR_FINAL_PROBE_SESSIONS - 1)])
    assert BC.probe_complete(four) is False and BC.COMPLETE_ID not in four.docs      # NEGATIVE: never early
    out, _coll, calls, _clock, _db = _probe(monkeypatch, coll=four)
    assert out["ran"] is True and calls


def test_a_due_count_without_a_marker_writes_it_and_refuses(monkeypatch):
    n = GC.GAJJALA_BAR_FINAL_PROBE_SESSIONS
    full = FakeColl([{"_id": f"d{i}", "date": f"2026-10-0{i + 1}"} for i in range(n)])
    out, _coll, calls, _clock, _db = _probe(monkeypatch, coll=full)
    assert out["reason"] == BC.R_COMPLETE and calls == []
    assert "at" not in full.docs[BC.COMPLETE_ID]


class _RecPool(BC.ThreadPoolExecutor):
    seen: list = []

    def __init__(self, max_workers=None, **kw):
        _RecPool.seen.append(max_workers)
        super().__init__(max_workers=max_workers, **kw)


def test_the_probe_fetches_at_most_the_worker_cap_at_once(monkeypatch):
    import threading
    import time as _time
    assert GC.GAJJALA_BAR_FINAL_PROBE_WORKERS == 2
    _RecPool.seen = []
    monkeypatch.setattr(BC, "ThreadPoolExecutor", _RecPool)
    lock, live, peak = threading.Lock(), [0], [0]
    base = loader(Clock(TARGET))

    def load_day(*a, **k):
        with lock:
            live[0] += 1
            peak[0] = max(peak[0], live[0])
        _time.sleep(0.005)
        try:
            return base(*a, **k)
        finally:
            with lock:
                live[0] -= 1
    names = [f"N{i}" for i in range(12)]
    monkeypatch.setattr(R1, "names_for", lambda shared, session: (names, 0))
    clock = Clock(TARGET)
    BC.probe(TARGET, coll=FakeColl(), shared=object(), load_day=load_day, sleep=clock.sleep, wall=clock.wall)
    assert _RecPool.seen == [GC.GAJJALA_BAR_FINAL_PROBE_WORKERS] * 2       # at30 + at60, never board.BAR_WORKERS
    assert 1 <= peak[0] <= GC.GAJJALA_BAR_FINAL_PROBE_WORKERS


def test_NEGATIVE_a_late_second_read_marks_rows_late_never_changed(monkeypatch):
    out, coll, calls, _clock, _db = _probe(monkeypatch, oversleep=[0.0, 31.0], second=df_late)
    row = rows(coll)["2026-10-13|10:05|GGA"]
    assert row["late"] is True and row["changed"] is None and row["at60"] is None and row["fields_changed"] == []
    assert row["at30"]["h"] == 10.5 and [c[3] for c in calls] == ["at30"]   # no second fetch
    assert out["probe"]["late"] is True and out["probe"]["changed"] == 0


def test_a_second_read_exactly_at_the_cap_is_not_late(monkeypatch):
    out, coll, calls, _clock, _db = _probe(monkeypatch, oversleep=[0.0, float(GC.BAR_CLOSE_LATE_MAX_SEC)],
                                           second=df_late)
    row = rows(coll)["2026-10-13|10:05|GGA"]
    assert row["late"] is False and row["changed"] is True and [c[3] for c in calls] == ["at30", "at60"]


def test_NEGATIVE_two_children_one_target_one_set_of_rows(monkeypatch):
    db, shared = world(monkeypatch, ("GGA", "GGB"))
    coll = db.setdefault(BC.COLL, FakeColl())
    c1, calls1 = Clock(at(10, 3, 12)), []
    out1 = BC.wait_and_run(at(10, 3, 12), sleep=c1.sleep, wall=c1.wall, coll=coll, shared=shared,
                           load_day=loader(c1, calls=calls1))
    c2, calls2 = Clock(at(10, 5, 20)), []                                # a pass that ended after :x5:20 → 2nd child
    out2 = BC.wait_and_run(at(10, 5, 20), sleep=c2.sleep, wall=c2.wall, coll=coll, shared=shared,
                           load_day=loader(c2, calls=calls2))
    assert out1["target"] == out2["target"] and out1["ran"] is True
    assert out2["ran"] is False and out2["reason"] == BC.R_OWNED and calls2 == [] and c2.slept == []
    assert sorted(rows(coll)) == ["2026-10-13|10:05|GGA", "2026-10-13|10:05|GGB"]
    claims = [d for k, d in coll.docs.items() if k.startswith(BC.CLAIM_PREFIX)]
    assert len(claims) == 1 and "at" in claims[0] and "date" not in claims[0]   # TTL'd; never counted as a session


def test_NEGATIVE_a_failed_claim_refuses_without_fetching(monkeypatch):
    out, _coll, calls, clock, _db = _probe(monkeypatch, coll=FakeColl(fail=True))
    assert out["reason"] == BC.R_CLAIM_FAILED and calls == [] and clock.slept == []
