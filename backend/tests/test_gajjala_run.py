"""chart_maps/gajjala/run.py — the 5-minute pass end to end (BUILD_SPEC §3.10 / WP4, 2026-10-13).

The REAL scanner, bars resampler and detectors run on fixture data: one snapshot row that passes his scanner, two
sessions of 1-minute bars expanded from the Bull Flag A+ fixture (tests/fixtures/gajjala/detector_frames.py), so the
pass goes qualifier → listed → closed 5-minute frames → A+ → the push gate. Every provider and writer is injected; the
store is the in-memory FakeColl set (tests/conftest.py refuses a real MongoClient). Negatives: a second concurrent
run, a dry run that writes, an out-of-window tick that calls the snapshot, a shadow pass that rings.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run as RUN
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_store import fake_store

ET = ZoneInfo("America/New_York")
S = date(2026, 10, 13)
PREV = date(2026, 10, 12)
ROOT = Path(__file__).resolve().parents[1]


def at(hh, mm, d=S, ss=0):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


def _ms(dt):
    return int(dt.timestamp() * 1000)


def minutes_from_5m(bars5, day: date, start: str, session: str = "rth") -> pd.DataFrame:
    """Each 5-minute (o, h, l, c, v) as five 1-minute bars that aggregate back to it exactly — open, the low, the
    high (the break minute), the close — naive-UTC index = the minute START (daytrading.data)."""
    t0 = datetime.combine(day, datetime.strptime(start, "%H:%M").time(), tzinfo=ET)
    idx, rows = [], []
    for k, (o, h, l, c, v) in enumerate(bars5):
        path = [(o, o, o, o), (o, o, l, l), (l, h, l, h), (h, h, c, c), (c, c, c, c)]
        for m, (mo, mh, ml, mc) in enumerate(path):
            ts = (t0 + timedelta(minutes=5 * k + m)).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
            idx.append(pd.Timestamp(ts))
            rows.append({"open": mo, "high": mh, "low": ml, "close": mc, "volume": v / 5, "session": session})
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


PRIOR_1M = minutes_from_5m(FX.warm(), PREV, "14:00")
TODAY_1M = minutes_from_5m(FX.bf_bars(), S, "10:00")               # 8 bars: buckets 10:00 … 10:35, labels … 10:40
NOW = at(10, 41)                                                   # the 10:40 bar has settled (BAR_SETTLE_SEC)


def snap_row(price, prev, *, vol=3_000_000, when=None, close=None):
    when = when or at(10, 40)
    return {"last_trade_price": price, "last_trade_ts_ms": _ms(when) * 1_000_000, "prev_day_close": prev,
            "min_av": vol, "min_t_ms": _ms(when), "volume": vol, "open": prev, "high": price, "low": prev,
            "close": close if close is not None else price}


class Rec:
    def __init__(self, ret=None):
        self.calls = []
        self.ret = ret

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self.ret(*a, **k) if callable(self.ret) else self.ret


def make_deps(*, rows=None, http=200, load=None, raise_for=(), clock=None):
    rows = rows if rows is not None else {"GGA": snap_row(11.2, 8.0), "NOPE": snap_row(1.0, 0.95)}
    snapshot = Rec(lambda: (rows, {"http": http, "wall_s": 0.5, "bytes": 1, "n": len(rows)}))

    def load_day(sym, day, force=False, include_premarket=True, include_afterhours=False):
        if sym in raise_for:
            raise RuntimeError("provider down")
        if load is not None:
            return load(sym, day)
        return PRIOR_1M.copy() if day == PREV else TODAY_1M.copy()

    send = Rec({"sent": 1, "failed": 0, "total_targets": 1})
    status = Rec(True)
    d = RUN.Deps(snapshot=snapshot, load_day=load_day, halts=lambda: {"session_date": S.isoformat(), "by_ticker": {}},
                 status_lookup=lambda sym, fetch=True: (None, "missing"), massive_lookup=lambda sym: 5_000_000,
                 fetch_splits=lambda sym, since: [], fetch_types=lambda: ({s: "CS" for s in rows}, True, 1),
                 daily_loader=lambda sym, now=None: None, send=send, owner="owner@example.com", record_status=status, sleep=lambda s: None,
                 clock=clock or (lambda: 0.0))
    return d, snapshot, send, status


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")


# ── end to end ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_end_to_end_qualifier_to_aplus_to_one_push(live):
    st = fake_store()
    deps, snapshot, send, status = make_deps()
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["ran"] and out["status"] == "ok" and out["errors"] == []
    assert len(snapshot.calls) == 1
    assert out["qualifiers"] == ["GGA"] and out["n_listed"] == 1 and out["n_read"] == 1
    assert "GGA:bull_flag" in out["aplus"]
    pushed = [a[1] for a, _k in send.calls]
    assert any(p["url"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=GGA" for p in pushed)
    assert len(send.calls) == out["alerts"]["pushed"] == len(out["aplus"])
    doc = st.get_read(S, "GGA")
    assert doc["setups"]["bull_flag"]["state"] == "aplus"
    assert doc["setups"]["bull_flag"]["entry_bar_t"] == doc["as_of_bar_t5"] == "2026-10-13 10:40"
    assert doc["tile"]["bars5"] and doc["tile"]["curves5"] and doc["ctx"]["float"]["src"] == "shares_out_massive"
    assert doc["listed"]["day_n"] == 1
    latest = st.latest_pass()
    assert latest["status"] == "ok" and latest["alerts"]["pushed"] == len(send.calls)
    (counts, _now, reason), _ = status.calls[0]
    assert counts["candidates"] == 1 and counts["pushed"] == len(send.calls) and reason is None
    assert st.get_state("lease")["status"] == "done"


def test_NEGATIVE_the_shipped_shadow_pass_never_rings():
    st = fake_store()
    deps, _snap, send, status = make_deps()
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert "GGA:bull_flag" in out["aplus"]
    assert send.calls == []
    assert out["alerts"]["shadow"] == len(out["aplus"]) and out["alerts"]["shadow_mode"] == 1
    assert "SHADOW:GG:2026-10-13|GGA|bull_flag" in st.alerts_coll().docs
    (counts, _n, _r), _ = status.calls[0]
    assert counts["shadow_mode"] == 1 and counts["shadow_session"] == len(out["aplus"])


def test_NEGATIVE_a_non_qualifier_is_never_read():
    st = fake_store()
    deps, *_ = make_deps()
    RUN.run_pass(NOW, store=st, deps=deps)
    assert st.get_read(S, "NOPE") is None


def test_stopped_today_is_kept_across_passes():
    st = fake_store()
    st.upsert_read(S, "GGA", {"stopped_today": {"kiss_fly": "2026-10-13 10:20"}})
    deps, *_ = make_deps()
    RUN.run_pass(NOW, store=st, deps=deps)
    assert st.get_read(S, "GGA")["stopped_today"]["kiss_fly"] == "2026-10-13 10:20"


# ── lease ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_second_concurrent_run_skips_on_the_lease():
    st = fake_store()
    assert st.claim_lease(RUN._utc(NOW))                           # another pass holds it
    deps, snapshot, *_ = make_deps()
    out = RUN.run_pass(NOW + timedelta(seconds=20), store=st, deps=deps)
    assert out["ran"] is False and "lease" in out["reason"] and snapshot.calls == []


def test_NEGATIVE_a_released_lease_still_blocks_inside_the_min_gap():
    st = fake_store()
    deps, snapshot, *_ = make_deps()
    RUN.run_pass(NOW, store=st, deps=deps)
    out = RUN.run_pass(NOW + timedelta(seconds=GC.LEASE_MIN_GAP_SEC - 10), store=st, deps=deps)
    assert out["ran"] is False and len(snapshot.calls) == 1
    out = RUN.run_pass(NOW + timedelta(seconds=GC.PASS_CADENCE_SEC), store=st, deps=deps)
    assert out["ran"] is True and len(snapshot.calls) == 2


# ── window ────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("now", [at(3, 59), at(20, 6), at(20, 56), at(10, 41, date(2026, 10, 17)),   # Saturday
                                 at(10, 41, date(2026, 9, 7))])                                    # Labor Day
def test_NEGATIVE_outside_the_window_exits_without_a_snapshot_call(now):
    deps, snapshot, send, status = make_deps()
    out = RUN.run_pass(now, store=fake_store(), deps=deps)
    assert out["ran"] is False and snapshot.calls == [] and status.calls == [] and send.calls == []


@pytest.mark.parametrize("now", [at(4, 1), at(20, 1), at(20, 5)])
def test_the_window_edges_run(now):
    assert RUN.in_window(now)


def test_main_outside_the_window_returns_0_and_never_builds_a_pass(monkeypatch):
    monkeypatch.setattr(RUN, "run_pass", lambda *a, **k: pytest.fail("no pass outside the window"))
    assert RUN.main(["--now", at(20, 10).isoformat()]) == 0


def test_main_reads_a_naive_now_as_et(monkeypatch):
    seen = []
    monkeypatch.setattr(RUN, "run_pass", lambda now, **k: (seen.append(now), {"status": "ok"})[1])
    monkeypatch.setattr(RUN, "dry_store", lambda *a, **k: None)
    assert RUN.main(["--dry-run", "--now", "2026-10-13T10:16"]) == 0
    assert seen == [datetime(2026, 10, 13, 10, 16, tzinfo=ET)]
    assert seen[0].astimezone(ET).strftime("%H:%M") == "10:16"     # NEGATIVE: never 06:16 ET (naive-as-UTC)


def test_NEGATIVE_a_naive_21_00_is_outside_the_window_not_17_00_et(monkeypatch):
    monkeypatch.setattr(RUN, "run_pass", lambda *a, **k: pytest.fail("21:00 ET is outside the window"))
    assert RUN.main(["--dry-run", "--now", "2026-10-13T21:00"]) == 0


# ── dry run ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_dry_run_calls_no_writer_and_no_sender(live):
    real = fake_store()
    st = RUN.dry_store(real)
    deps = RUN.dry_deps()
    base, _snap, send, _status = make_deps()
    for k in ("snapshot", "load_day", "halts", "status_lookup", "massive_lookup", "fetch_splits", "fetch_types",
              "daily_loader"):
        setattr(deps, k, getattr(base, k))
    out = RUN.run_pass(NOW, store=st, deps=deps, dry=True)
    assert out["ran"] and "GGA:bull_flag" in out["aplus"]
    assert out["alerts"]["dry"] == len(out["aplus"]) and out["alerts"]["pushed"] == 0
    assert deps.sent == [] and send.calls == []
    assert all(c.writes == 0 for c in real._injected.values()), {n: c.writes for n, c in real._injected.items()}
    assert st.writes                                                 # the writes it WOULD have made, recorded
    assert deps.status and deps.status[0]["candidates"] == 1        # the /alerts row went to the recorder


def test_dry_deps_never_refine_floats_and_never_cache_minutes():
    d = RUN.dry_deps()
    assert d.refine_floats is False and d.load_day is RUN._dry_load_day and d.status_lookup is RUN._dry_status_lookup
    import inspect
    src = inspect.getsource(RUN._dry_load_day)
    assert "_fetch_massive_minute" in src and "_mongo_put_day(" not in src


def test_dry_symbols_are_read_even_when_not_listed(live):
    real = fake_store()
    st = RUN.dry_store(real)
    deps = RUN.dry_deps()
    base, *_ = make_deps(rows={"NOPE": snap_row(1.0, 0.95)})
    for k in ("snapshot", "load_day", "halts", "status_lookup", "massive_lookup", "fetch_splits", "fetch_types",
              "daily_loader"):
        setattr(deps, k, getattr(base, k))
    out = RUN.run_pass(NOW, store=st, deps=deps, dry=True, symbols=["gga"])
    assert out["n_listed"] == 1 and out["n_read"] == 1


# ── budget / failures ─────────────────────────────────────────────────────────────────────────────────────────────
def test_budget_spent_skips_names_counts_them_and_still_records():
    st = fake_store()
    ticks = iter([0.0] + [GC.PASS_BUDGET_SEC + 1.0] * 50)
    deps, _snap, _send, status = make_deps(clock=lambda: next(ticks))
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["bars"]["over_budget"] == 1 and out["n_read"] == 0
    assert st.latest_pass() is not None and status.calls


def test_a_name_whose_bars_raise_is_skipped_and_counted():
    st = fake_store()
    rows = {"GGA": snap_row(11.2, 8.0), "BAD": snap_row(11.2, 8.0)}
    deps, *_ = make_deps(rows=rows, raise_for=("BAD",))
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["bars"]["failed"] == 1 and out["bars"]["loaded"] == 1 and out["n_read"] == 1


def test_NEGATIVE_a_failed_snapshot_still_reads_the_listed_names_and_says_so():
    st = fake_store()
    deps, *_ = make_deps()
    RUN.run_pass(NOW, store=st, deps=deps)                         # GGA qualifies once
    deps2, _s, _send, status = make_deps(rows={}, http=500)
    out = RUN.run_pass(NOW + timedelta(seconds=GC.PASS_CADENCE_SEC), store=st, deps=deps2)
    assert out["status"] == "failed" and out["n_listed"] == 1
    (_c, _n, reason), _ = status.calls[0]
    assert reason and "snapshot failed" in reason


def test_after_hours_pass_replaces_the_carry_and_confirms_post_market():
    st = fake_store()
    ah = at(17, 1)
    rows = {"GGA": snap_row(13.0, 8.0, when=at(17, 0), close=11.2)}
    deps, *_ = make_deps(rows=rows)
    out = RUN.run_pass(ah, store=st, deps=deps)
    assert out["tape_session"] == "afterhours" and out["status"] == "ok"
    assert st.ah_carry(S)["names"]["GGA"]["ah_move_pct"] > GC.K9_AH_CARRY_PCT
    assert isinstance(st.latest_pass()["postmarket"], dict)


def test_NEGATIVE_the_k10_confirm_load_asks_massive_for_the_dot_spelling(monkeypatch):
    """Integration 2026-10-13 (WP1 cross-WP): a class-share K10 candidate not in
    this pass's frames is loaded as MOG.A — Massive returns nothing for MOG-A."""
    st = fake_store()
    rows = {"GGA": snap_row(13.0, 8.0, when=at(17, 0), close=11.2)}
    deps, *_ = make_deps(rows=rows)
    asked = []
    real = deps.load_day

    def load_day(sym, day, **k):
        asked.append(sym)
        return real(sym, day, **k)
    deps.load_day = load_day

    def fake_confirm(cands, checked, minutes, **k):
        minutes("MOG-A")
        return [], 0
    from chart_maps.gajjala import context as CX
    monkeypatch.setattr(CX, "postmarket_confirm", fake_confirm)
    out = RUN.run_pass(at(17, 1), store=st, deps=deps)
    assert out["tape_session"] == "afterhours"
    assert "MOG.A" in asked and "MOG-A" not in asked


def test_the_pass_doc_says_whether_the_type_map_was_complete():
    """Integration 2026-10-13 (WP1 cross-WP): `complete` + the scanner's AH tripwire counts reach the pass doc."""
    st = fake_store()
    deps, *_ = make_deps()
    RUN.run_pass(NOW, store=st, deps=deps)
    doc = st.latest_pass()
    assert doc["types_meta"]["complete"] is True and doc["types_meta"]["as_of"] == S.isoformat()
    assert "ah_rows" in doc["counts"] and "ah_close_eq_last" in doc["counts"]


def test_NEGATIVE_a_partial_type_fetch_reads_incomplete_in_the_pass_doc():
    st = fake_store()
    deps, *_ = make_deps()
    deps.fetch_types = lambda: ({"GGA": "CS"}, False, 15)
    RUN.run_pass(NOW, store=st, deps=deps)
    assert st.latest_pass()["types_meta"]["complete"] is False


# ── crontab ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_exactly_one_crontab_line_each_through_the_gate():
    lines = [ln for ln in (ROOT / "crontab").read_text().splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    run = [ln for ln in lines if re.search(r"-m market_hours\.gate chart_maps\.gajjala\.run(\s|$)", ln)]
    nightly = [ln for ln in lines if re.search(r"-m market_hours\.gate chart_maps\.gajjala\.nightly(\s|$)", ln)]
    assert len(run) == 1 and len(nightly) == 1
    f = run[0].split()
    assert f[0] == "1-56/5" and f[1] == "4-20" and f[4] == "1-5"
    assert int(f[0].split("/")[1]) * 60 == GC.PASS_CADENCE_SEC
    n = nightly[0].split()
    assert (n[0], n[1], n[4]) == ("15", "20", "1-5")
    assert not [ln for ln in lines if "chart_maps.gajjala" in ln and "market_hours.gate" not in ln]
