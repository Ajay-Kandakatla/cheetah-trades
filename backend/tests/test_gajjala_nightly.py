"""chart_maps/gajjala/nightly.py — the 20:15 ET job (spec §3.10; WP2, 2026-10-13): float warm, the 30-session halt
backfill from Nasdaq Trader's dated list, and the 🎾 squeeze-history warm for TOMORROW. Every provider is injected.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import context as CX
from chart_maps.gajjala import nightly as NG
from tests.test_gajjala_context import Massive, Yahoo
from tests.test_gajjala_store import fake_store

S = date(2026, 10, 13)                     # Tuesday
T = date(2026, 10, 14)                     # the next market day — the chips are for it
NOW = datetime(2026, 10, 14, 0, 15, tzinfo=timezone.utc)   # 20:15 EDT


# WIDENED 2026-10-27 (BUILD_SPEC27 §3.6, the 🚩 1-minute page): main() now grades the GG1 record after GG5's run — the
# main() tests here inject GG5's store only, so the GG1 grade is a recorder (tests/test_gajjala_run_1m_2026_10_27.py
# pins the hook itself)
@pytest.fixture(autouse=True)
def _no_1m_grade(monkeypatch):
    monkeypatch.setattr(NG, "grade_1m", lambda now, **k: {"grade": {}})


class Halts:
    def __init__(self, fail=()):
        self.fail = set(fail)
        self.calls: list = []

    def __call__(self, d):
        self.calls.append(d)
        if d in self.fail:
            return {}
        # every session has halts (a zero-halt answer is a failed read since 2026-10-13); AAA's fall on day % 7 == 0
        t = "AAA" if d.day % 7 == 0 else "ZZZ"
        return {"session_date": d.isoformat(),
                "by_ticker": {t: {"ticker": t, "n_halts": 1, "reasons": ["LUDP"],
                                  "halts": [{"halt_time": "10:00:00", "resume_date": d.strftime("%m/%d/%Y"),
                                             "resume_time": "10:05:00"}]}}}


def _daily(sym, *, now=None):
    days = CX.history_window(T)
    return pd.DataFrame([{"open": 1, "high": 1.1, "low": 1.0, "close": 1, "volume": 1} for _ in days],
                        index=pd.DatetimeIndex([pd.Timestamp(d) for d in days]))


def _store_with_names():
    st = fake_store()
    st.record_qualifiers(S, NOW, [{"symbol": "AAA", "change_pct": 80.0}, {"symbol": "BBB", "change_pct": 30.0}],
                         "rth")
    st.record_qualifiers(date(2026, 10, 12), NOW, [{"symbol": "OLD", "change_pct": 40.0}], "rth")
    st.record_qualifiers(date(2026, 10, 9), NOW, [{"symbol": "GONE", "change_pct": 99.0}], "rth")
    st.replace_ah_carry(S, NOW, [{"symbol": "CAR", "ah_move_pct": 14.0, "price": 1.14, "day_c": 1.0}])
    return st


def _run(st, **kw):
    kw.setdefault("now", NOW)
    kw.setdefault("fetch_halts", Halts())
    kw.setdefault("daily_loader", _daily)
    kw.setdefault("status_lookup", Yahoo())
    kw.setdefault("massive_lookup", Massive())
    kw.setdefault("sleep", lambda s: None)
    return NG.run(S, store=st, **kw)


def test_halt_window_is_the_30_sessions_ending_today():
    w = NG.halt_window(S)
    assert len(w) == GC.K8_HISTORY_SESSIONS and w[-1] == S


def test_names_for_tomorrow_are_the_listed_set_plus_tonights_carry():
    syms, prio = NG.names_for_tomorrow(_store_with_names(), S)
    assert syms == ["AAA", "BBB", "CAR", "OLD"], "GONE qualified 3 sessions before tomorrow — graveyard, not warmed"
    assert prio["AAA"]["change_pct"] == 80.0 and prio["CAR"]["change_pct"] == 14.0


def test_first_night_backfills_all_30_then_is_idempotent():
    st, h = _store_with_names(), Halts()
    out = _run(st, fetch_halts=h)
    assert out["errors"] == [] and out["halts"]["read"] == 30 and len(h.calls) == 30
    assert sorted(h.calls) == NG.halt_window(S)
    again = Halts()
    out2 = _run(st, fetch_halts=again)
    assert again.calls == [] and out2["halts"]["already"] == 30


def test_backfills_exactly_the_missing_sessions():
    st = _store_with_names()
    w = NG.halt_window(S)
    st.set_state(CX.HALT_BACKFILL_STATE_ID, {"done": [d.isoformat() for d in w[:25]]})
    h = Halts()
    _run(st, fetch_halts=h)
    assert h.calls == w[25:]


def test_NEGATIVE_a_failed_read_is_not_marked_and_is_retried_next_night():
    st = _store_with_names()
    w = NG.halt_window(S)
    out = _run(st, fetch_halts=Halts(fail={w[3]}))
    assert out["halts"]["failed"] == 1 and out["halts"]["read"] == 29
    retry = Halts()
    _run(st, fetch_halts=retry)
    assert retry.calls == [w[3]]


def test_NEGATIVE_done_marks_older_than_the_window_are_dropped():
    st = _store_with_names()
    st.set_state(CX.HALT_BACKFILL_STATE_ID, {"done": ["2020-01-02"]})
    _run(st)
    assert "2020-01-02" not in st.get_state(CX.HALT_BACKFILL_STATE_ID)["done"]


def test_backfilled_halts_reach_tomorrows_squeeze_chip():
    st = _store_with_names()
    out = _run(st)
    halt_days = [d.isoformat() for d in NG.halt_window(S) if d.day % 7 == 0]
    chip = st.get_daily(T, "AAA")["squeeze_history"]
    assert chip["halt_days"] == halt_days and chip["n"] == len(halt_days)
    assert chip["ledger_complete"] is True and "halt list from" not in chip["text"]
    assert st.get_daily(T, "BBB")["squeeze_history"]["n"] == 0
    assert st.get_daily(S, "AAA") is None, "the chip is for tomorrow, never stored under tonight"
    assert out["history"]["computed"] == 4
    assert _run(st)["history"] == {"computed": 0, "cached": 4, "deferred": 0}


def test_float_warm_fetches_every_name_paced_and_stops_at_the_first_429():
    st, sleeps = _store_with_names(), []
    y = Yahoo()
    out = _run(st, status_lookup=y, sleep=sleeps.append)
    assert sorted(y.fetched) == ["AAA", "BBB", "CAR", "OLD"] and len(sleeps) == 3
    assert out["floats"]["fetched"] == 4
    st2 = _store_with_names()
    limited = Yahoo(answers={"AAA": (None, "rate_limited")})
    _run(st2, status_lookup=limited)
    assert limited.fetched == ["AAA"]
    assert st2.get_state(CX.FLOAT_STATE_ID)["n"] == 1


def test_NEGATIVE_one_step_raising_does_not_stop_the_others(monkeypatch):
    st = _store_with_names()

    def boom(*a, **k):
        raise RuntimeError("float chain exploded")
    monkeypatch.setattr(CX, "floats_for", boom)
    out = _run(st)
    assert out["errors"] == ["floats: RuntimeError"]
    assert out["halts"]["read"] == 30 and out["history"]["computed"] == 4


def test_NEGATIVE_steps_flag_runs_only_the_named_step():
    st, h = _store_with_names(), Halts()
    y = Yahoo()
    out = _run(st, fetch_halts=h, status_lookup=y, steps=("history",))
    assert h.calls == [] and y.fetched == [] and "halts" not in out and out["history"]["computed"] == 4


def test_default_session_on_a_weekend_is_the_last_market_day():
    sat = datetime(2026, 10, 17, 16, 0, tzinfo=timezone.utc)
    assert NG.default_session(sat) == date(2026, 10, 16)
    assert NG.default_session(NOW) == S


def test_main_parses_args_and_returns_nonzero_on_a_step_error(monkeypatch):
    seen = {}
    st = fake_store()
    monkeypatch.setattr("chart_maps.gajjala.store.default", lambda: st)

    def fake_run(session, *, store=None, steps=NG.STEPS):
        seen.update(session=session, store=store, steps=steps)
        return {"errors": ["halts: X"]}
    monkeypatch.setattr(NG, "run", fake_run)
    assert NG.main(["--session", "2026-10-13", "--steps", "halts,bogus"]) == 1
    assert seen == {"session": S, "store": st, "steps": ("halts",)}
    monkeypatch.setattr(NG, "run", lambda session, *, store=None, steps=NG.STEPS: {"errors": []})
    assert NG.main([]) == 0


# ── 2026-10-13 review: a 200 that carries no halt of that session is NOT a read ───────────────────────────────────
def test_NEGATIVE_zero_halt_answer_is_failed_and_retried():
    st = _store_with_names()
    w = NG.halt_window(S)
    calm = w[5]

    def fetch(d):
        if d == calm:
            return {"session_date": d.isoformat(), "by_ticker": {}, "n_halts": 0}
        return Halts()(d)
    out = NG.backfill_halts(st, S, fetch=fetch)
    assert out["failed"] == 1 and out["read"] == 29
    assert calm.isoformat() not in st.get_state(CX.HALT_BACKFILL_STATE_ID)["done"]
    retry = Halts()
    NG.backfill_halts(st, S, fetch=retry)
    assert retry.calls == [calm]


def test_NEGATIVE_feed_ignoring_haltdate_marks_only_the_real_day(monkeypatch):
    """Every GET answers with the 10/09 body (as if Nasdaq ignored `&haltdate`): only 10/09 is read; the other 29
    sessions stay out of `done` and the chip keeps its "halt list from …" caveat. Before the fix: read 30, failed 0."""
    from catalysts import halts as H
    from tests.test_halts_for_date import _R, _body
    monkeypatch.setattr(H.requests, "get", lambda url, **k: _R(_body()))
    st = _store_with_names()
    out = _run(st, fetch_halts=H.get_halts_for_date, steps=("halts", "history"))
    assert (out["halts"]["read"], out["halts"]["failed"]) == (1, 29)
    assert st.get_state(CX.HALT_BACKFILL_STATE_ID)["done"] == ["2026-10-09"]
    assert st.get_daily(T, "AAA")["squeeze_history"]["ledger_complete"] is False


# ── 🏁 the grade step (2026-10-16, BUILD_SPEC9 §3.5) — LAST, its own try, picked up by the existing crontab line ────
def test_the_grade_step_is_last_and_runs_by_default():
    assert NG.STEPS == ("floats", "halts", "history", "grade")


def test_main_with_no_args_runs_grade_because_the_crontab_line_passes_no_steps(monkeypatch):
    seen = {}
    st = fake_store()
    monkeypatch.setattr("chart_maps.gajjala.store.default", lambda: st)

    def fake_run(session, *, store=None, steps=NG.STEPS):
        seen["steps"] = steps
        return {"errors": []}
    monkeypatch.setattr(NG, "run", fake_run)
    assert NG.main([]) == 0 and "grade" in seen["steps"] and seen["steps"][-1] == "grade"


def test_the_grade_step_reports_its_summary_and_reads_through_injected_loaders():
    from chart_maps.gajjala import ledger as LG
    st = _store_with_names()
    calls = []
    out = _run(st, ledger_load_day=lambda s, d: calls.append((s, d)) or ([], False),
               ledger_split_lookup=lambda s, a, n: False)
    assert out["errors"] == [] and out["grade"]["read_fault"] is False and calls == []   # no alert rang: no load
    assert set(LG.STEP_KEYS) <= set(out["grade"])


def test_NEGATIVE_a_raising_grade_step_never_stops_the_other_steps(monkeypatch):
    from chart_maps.gajjala import ledger as LG

    def boom(*a, **k):
        raise RuntimeError("ledger exploded")
    monkeypatch.setattr(LG, "grade_step", boom)
    out = _run(_store_with_names())
    assert out["errors"] == ["grade: RuntimeError"]
    assert out["floats"]["fetched"] == 4 and out["halts"]["read"] == 30 and out["history"]["computed"] == 4
    assert "grade" not in out


def test_NEGATIVE_steps_history_runs_no_grade(monkeypatch):
    from chart_maps.gajjala import ledger as LG
    called = []
    monkeypatch.setattr(LG, "grade_step", lambda *a, **k: called.append(1) or {})
    out = _run(_store_with_names(), steps=("history",))
    assert called == [] and "grade" not in out
