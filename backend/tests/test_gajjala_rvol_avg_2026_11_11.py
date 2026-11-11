"""💋 2026-11-11 — the 50-session average volume and the pass's rel volume (spec rvolsort §3.1, WP-CTX).

Ajay 2026-11-11: "Sort by relative volume, and closer to the EMA." Display only — no gate, push, count or 🏁 change.

`context.warm_squeeze_history` stores `avg_vol_50` (the house average `momentum_burst.avg_volume_before`) beside the
🎾 chip ONLY when known, and serves it in `avg_vol`; `run.run_pass` puts `ctx["rvol"]` = the house sort engine
`drop10_tab.rvol_read` over the volume THIS pass read (`sv`, the K11 number — never the stored scan row) on the read
doc. Every expected number is built with the engines' own functions, never retyped.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from chart_maps import drop10_tab as DTAB
from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import context as CX
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import store as ST
from supply_demand import momentum_burst as MB
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_run import (ET, NOW, PREV, S, at, make_deps, minutes_from_5m, snap_row)
from tests.test_gajjala_store import fake_store

N = MB.VOL_AVG_BARS                                           # 50


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture(autouse=True)
def _no_1m_spawn(monkeypatch):
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: True)


def _frame(n: int, *, end: date = PREV, vols=None, today: date = None, today_vol: float = 1e12) -> pd.DataFrame:
    """`n` closed business days ending `end` (volume i × 100k, i = 1…n unless `vols`), plus an optional `today` row."""
    idx = list(pd.bdate_range(end=end, periods=n))
    v = list(vols) if vols is not None else [i * 1e5 for i in range(1, n + 1)]
    if today is not None:
        idx.append(pd.Timestamp(today))
        v.append(today_vol)
    return pd.DataFrame({"open": 1.0, "high": 1.2, "low": 1.0, "close": 1.1, "volume": v},
                        index=pd.DatetimeIndex(idx))


def _mean_last(n: int, k: int = N) -> float:
    return sum(i * 1e5 for i in range(n - k + 1, n + 1)) / k


def _spy_upserts(st):
    calls = []
    real = st.upsert_daily

    def spy(session, sym, fields, **kw):
        calls.append((sym, dict(fields)))
        return real(session, sym, fields, **kw)
    st.upsert_daily = spy
    return calls


# ── context.warm_squeeze_history ──────────────────────────────────────────────────────────────────────────────────
def test_sixty_sessions_store_and_serve_the_mean_of_the_last_fifty_then_the_cache_serves_it_unread():
    st = fake_store()
    calls: list = []

    def loader(sym, *, now=None):
        calls.append(sym)
        return _frame(60)
    res = CX.warm_squeeze_history(["AAA"], S, st, loader=loader)
    assert res["computed"] == 1
    assert res["avg_vol"]["AAA"] == pytest.approx(_mean_last(60))
    assert res["avg_vol"]["AAA"] == MB.avg_volume_before(_frame(60), S), "the house average, not a second engine"
    assert st.get_daily(S, "AAA")["avg_vol_50"] == pytest.approx(_mean_last(60))
    again = CX.warm_squeeze_history(["AAA"], S, st, loader=loader)
    assert again["cached"] == 1 and again["computed"] == 0 and calls == ["AAA"], "the cache is never re-read"
    assert again["avg_vol"] == res["avg_vol"]


def test_NEGATIVE_thirty_sessions_store_no_key_and_serve_no_average():
    st = fake_store()
    ups = _spy_upserts(st)
    res = CX.warm_squeeze_history(["AAA"], S, st, loader=lambda sym, now=None: _frame(30))
    assert res["avg_vol"] == {}
    assert "avg_vol_50" not in st.get_daily(S, "AAA")
    assert ups == [("AAA", {"squeeze_history": res["chips"]["AAA"]})]


def test_NEGATIVE_forty_nine_sessions_are_one_short():
    res = CX.warm_squeeze_history(["AAA"], S, fake_store(), loader=lambda sym, now=None: _frame(N - 1))
    assert res["avg_vol"] == {}


def test_NEGATIVE_a_none_frame_writes_the_daily_body_byte_identical_to_before():
    st = fake_store()
    ups = _spy_upserts(st)
    res = CX.warm_squeeze_history(["AAA"], S, st, loader=lambda sym, now=None: None)
    assert res["avg_vol"] == {}
    assert ups == [("AAA", {"squeeze_history": res["chips"]["AAA"]})], "exactly today's body — no new key"


def test_NEGATIVE_a_loader_that_raises_serves_no_average():
    def boom(sym, now=None):
        raise RuntimeError("provider down")
    res = CX.warm_squeeze_history(["AAA"], S, fake_store(), loader=boom)
    assert res["avg_vol"] == {} and res["computed"] == 1


def test_NEGATIVE_a_today_dated_row_never_enters_the_average():
    st = fake_store()
    res = CX.warm_squeeze_history(["AAA"], S, st, loader=lambda sym, now=None: _frame(N, today=S))
    assert res["avg_vol"]["AAA"] == pytest.approx(_mean_last(N)), "the 1e12 today row is dropped"
    short = CX.warm_squeeze_history(["BBB"], S, st, loader=lambda sym, now=None: _frame(N - 1, today=S))
    assert short["avg_vol"] == {}, "today's row never counts as the fiftieth session"


def test_NEGATIVE_a_nan_volume_in_the_window_gives_no_average():
    vols = [1e6] * 60
    vols[-3] = float("nan")
    st = fake_store()
    res = CX.warm_squeeze_history(["AAA"], S, st, loader=lambda sym, now=None: _frame(60, vols=vols))
    assert res["avg_vol"] == {} and "avg_vol_50" not in st.get_daily(S, "AAA")


def test_NEGATIVE_a_cached_doc_without_the_average_is_never_re_read_for_it():
    st = fake_store()
    CX.warm_squeeze_history(["AAA"], S, st, loader=lambda sym, now=None: None)   # deploy day: a doc with no average
    calls: list = []

    def loader(sym, *, now=None):
        calls.append(sym)
        return _frame(60)
    res = CX.warm_squeeze_history(["AAA"], S, st, loader=loader)
    assert res["cached"] == 1 and res["avg_vol"] == {} and calls == []


def test_NEGATIVE_a_cached_non_finite_average_is_not_served():
    st = fake_store()
    CX.warm_squeeze_history(["AAA"], S, st, loader=lambda sym, now=None: None)
    st.upsert_daily(S, "AAA", {"avg_vol_50": float("nan")})
    assert CX.warm_squeeze_history(["AAA"], S, st, loader=lambda sym, now=None: _frame(60))["avg_vol"] == {}


def test_avg_vol_is_always_a_dict():
    assert CX.warm_squeeze_history([], S, fake_store(), loader=lambda sym, now=None: None)["avg_vol"] == {}


# ── run.run_pass → ctx["rvol"] ────────────────────────────────────────────────────────────────────────────────────
def _loader60(sym, now=None):
    return _frame(60, end=(now.date() if now is not None else S) - timedelta(days=1))


def _expected(vol, avg, tape, now_et):
    t, half = MB.burst_session(tape, now_et)
    return DTAB.rvol_read({"volume": vol}, {"avg_vol50": avg}, tape=t,
                          frac=MB.session_frac(t, now_et, half_day=half), half_day=half)


def _run(now, *, rows=None, load=None, loader=_loader60, store=None):
    st = store or fake_store()
    deps, _snap, send, status = make_deps(rows=rows, load=load)
    deps.daily_loader = loader
    out = RUN.run_pass(now, store=st, deps=deps)
    return st, out, deps, send


def test_run_pass_stores_the_house_rvol_read_over_this_passes_volume_projected_in_rth():
    st, out, _deps, _send = _run(NOW)
    assert out["ran"] and out["errors"] == [] and out["tape_session"] == "rth"
    avg = st.get_daily(S, "GGA")["avg_vol_50"]
    rv = st.get_read(S, "GGA")["ctx"]["rvol"]
    assert rv == _expected(3_000_000, avg, out["tape_session"], NOW.astimezone(ET))
    assert set(rv) == {"rvol", "basis", "actual", "projected", "session_pct", "code"}
    assert MB.session_frac("rth", NOW.astimezone(ET)) >= MB.BURST_PROJECTION_MIN_FRAC
    assert rv["basis"] == "projected" and rv["rvol"] == rv["projected"] is not None


def test_NEGATIVE_C1_the_stored_scan_row_volume_never_drives_rvol():
    """Pass 1 qualifies at 3M (the stored scan `last`); pass 2 does not qualify (+12.5%) and reads 5M off the snapshot
    — the rel volume is built on 5M, never on the frozen 3M row."""
    st, _o1, _d, _s = _run(NOW)
    later = NOW + timedelta(seconds=GC.PASS_CADENCE_SEC)
    rows2 = {"GGA": snap_row(9.0, 8.0, vol=5_000_000, when=at(10, 45)), "NOPE": snap_row(1.0, 0.95)}
    _st, out2, _d2, _s2 = _run(later, rows=rows2, store=st)
    stored = {d["symbol"]: d.get("last") or {} for d in st.scan_docs([S])}
    assert stored["GGA"]["volume"] == 3_000_000, "precondition: the stored row is frozen at the qualifying pass"
    assert "GGA" not in out2["qualifiers"]
    avg = st.get_daily(S, "GGA")["avg_vol_50"]
    rv = st.get_read(S, "GGA")["ctx"]["rvol"]
    assert rv == _expected(5_000_000, avg, out2["tape_session"], later.astimezone(ET))
    assert rv != _expected(3_000_000, avg, out2["tape_session"], later.astimezone(ET))


def test_NEGATIVE_a_premarket_pass_has_no_rvol_number_code_premarket():
    today = minutes_from_5m(FX.bf_bars(), S, "07:00", session="premarket")
    prior = minutes_from_5m(FX.warm(), PREV, "14:00")
    now = at(7, 45)
    st, out, _d, _s = _run(now, rows={"GGA": snap_row(11.2, 8.0, when=at(7, 44))},
                           load=lambda s, d: prior.copy() if d == PREV else today.copy())
    assert out["tape_session"] == "premarket"
    rv = st.get_read(S, "GGA")["ctx"]["rvol"]
    assert rv["rvol"] is None and rv["code"] == "premarket" and rv["basis"] is None
    assert rv == _expected(3_000_000, st.get_daily(S, "GGA")["avg_vol_50"], "premarket", now.astimezone(ET))


def test_an_after_hours_pass_reads_the_whole_session():
    now = at(16, 30)
    st, out, _d, _s = _run(now, rows={"GGA": snap_row(11.2, 8.0, when=at(16, 29)), "NOPE": snap_row(1.0, 0.95)})
    assert out["tape_session"] == "afterhours"
    rv = st.get_read(S, "GGA")["ctx"]["rvol"]
    assert rv["basis"] == "session" and rv["projected"] is None and rv["session_pct"] == 100
    assert rv == _expected(3_000_000, st.get_daily(S, "GGA")["avg_vol_50"], "afterhours", now.astimezone(ET))


HALF = date(2026, 11, 27)                                     # the house HALF_DAYS table (13:00 close)
HALF_PREV = date(2026, 11, 25)                                # 11-26 = Thanksgiving


def _half_run(hh, mm):
    from supply_demand.timeframes import HALF_DAYS
    assert HALF.isoformat() in HALF_DAYS
    today = minutes_from_5m(FX.bf_bars(), HALF, "10:00")
    prior = minutes_from_5m(FX.warm(), HALF_PREV, "14:00")
    now = at(hh, mm, d=HALF)
    st, out, _d, _s = _run(now, rows={"GGA": snap_row(11.2, 8.0, when=now - timedelta(minutes=1))},
                           load=lambda s, d: prior.copy() if d == HALF_PREV else today.copy())
    return st, out, now


def test_NEGATIVE_a_half_day_after_13_00_is_read_as_after_hours_never_projected():
    st, out, now = _half_run(13, 30)
    rv = st.get_read(HALF, "GGA")["ctx"]["rvol"]
    assert rv["basis"] == "session" and rv["projected"] is None
    assert rv == _expected(3_000_000, st.get_daily(HALF, "GGA")["avg_vol_50"], out["tape_session"],
                           now.astimezone(ET))
    assert MB.burst_session("rth", now.astimezone(ET)) == ("afterhours", True), "an rth tape after 13:00 maps too"


def test_NEGATIVE_a_half_day_before_13_00_is_never_projected():
    st, out, now = _half_run(11, 0)
    assert out["tape_session"] == "rth"
    rv = st.get_read(HALF, "GGA")["ctx"]["rvol"]
    assert rv["projected"] is None and rv["basis"] == "actual"
    assert rv == _expected(3_000_000, st.get_daily(HALF, "GGA")["avg_vol_50"], "rth", now.astimezone(ET))


def test_NEGATIVE_no_average_no_rvol_key():
    for loader in (lambda sym, now=None: None, lambda sym, now=None: _frame(30)):
        st, out, _d, _s = _run(NOW, loader=loader)
        assert out["n_read"] == 1
        assert "rvol" not in st.get_read(S, "GGA")["ctx"]


_WALL = ("claimed_at",)                                       # the real wall clock at the claim, not the pass's `now`


def _no_wall(docs: dict) -> dict:
    return {k: {f: v for f, v in d.items() if f not in _WALL} for k, d in docs.items()}


def test_NEGATIVE_pushes_alerts_rows_alert_ctx_and_potentials_are_byte_identical_with_the_average(monkeypatch):
    """The baseline frame is the last 45 sessions of the SAME frame: the 🎾 chip is identical, the average is not
    (45 < 50) — so the ONLY difference between the two runs is the average."""
    seen: list = []
    real = AL.run_pass

    def spy(*a, **k):
        seen.append(dict(k.get("ctx") or {}))
        return real(*a, **k)
    monkeypatch.setattr(AL, "run_pass", spy)

    def short(sym, now=None):
        return _loader60(sym, now).iloc[-45:]
    runs = {}
    for name, loader in (("base", short), ("avg", _loader60)):
        st, out, deps, send = _run(NOW, loader=loader)
        runs[name] = (st, out, deps, send)
    (st0, out0, deps0, send0), (st1, out1, deps1, send1) = runs["base"], runs["avg"]
    r0, r1 = st0.get_read(S, "GGA"), st1.get_read(S, "GGA")
    assert "rvol" not in r0["ctx"] and "rvol" in r1["ctx"], "precondition: only the average differs"
    assert r0["ctx"]["squeeze_history"] == r1["ctx"]["squeeze_history"]
    assert {k: v for k, v in r1["ctx"].items() if k != "rvol"} == r0["ctx"]
    assert send0.calls and send1.calls == send0.calls, "push payloads"
    assert deps1.send_potential.calls == deps0.send_potential.calls
    assert deps1.record_status.calls == deps0.record_status.calls, "/alerts rows"
    assert deps1.record_potential_status.calls == deps0.record_potential_status.calls
    assert _no_wall(st1.alerts_coll().docs) == _no_wall(st0.alerts_coll().docs) and st0.alerts_coll().docs
    assert _no_wall(st1.coll(ST.POTENTIALS).docs) == _no_wall(st0.coll(ST.POTENTIALS).docs), "🧠 potential docs"
    assert len(seen) == 2 and seen[0] == seen[1], "alert_ctx carries no new key"
    assert not any("rvol" in c for c in seen[1].values())
    assert out1["alerts"] == out0["alerts"] and out1.get("potential") == out0.get("potential")
    assert r1["setups"] == r0["setups"]
    assert math.isfinite(r1["ctx"]["rvol"]["rvol"])
