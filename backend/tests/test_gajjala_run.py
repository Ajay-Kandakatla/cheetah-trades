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
                 clock=clock or (lambda: 0.0),
                 # 🧠 2026-10-15 — the potential gate's sender and /alerts row, recorders (fields on `d`)
                 send_potential=Rec({"sent": 1, "failed": 0, "total_targets": 1}),
                 record_potential_status=Rec(True))
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
    assert deps.send_potential.calls == [] and deps.record_potential_status.calls == []


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
    assert deps.send_potential.calls == [] and deps.record_potential_status.calls == []


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
    assert deps.sent_potential == [] and len(deps.status_potential) == 1   # 🧠 recorders only


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



# ── 🧠 potentials (BUILD_SPEC4 §3.8 + AMENDMENTS4 D1 / D2 / D9, 2026-10-15) ──────────────────────────────────────────
# Ajay 2026-10-15: "Give me an alert all continous tracker on these specifically when I get alert I will jump on to ride
# the wave". The fixture day truncated BEFORE the break bar: at 10:31 the 10:30 bar (P1) has closed — the bull flag is
# forming with a one-bar pullback (trigger armed); at 10:36 P2 has closed (still forming); at 10:41 it broke (A+).
T1, T2 = at(10, 31), at(10, 36)


def _seeded():
    """A store that already tracked one potential this session (a pass ran earlier) — the D9 join rule stays out."""
    from chart_maps.gajjala import store as ST
    st = fake_store()
    assert st.upsert_potential(ST.potential_key(S, "SEED", "kiss_fly"),
                               {"date": S.isoformat(), "symbol": "SEED", "setup": "kiss_fly"}, {"at": at(4, 6)})
    return st


def test_end_to_end_a_forming_flag_rings_one_potential_push():
    from chart_maps.gajjala import store as ST
    st = _seeded()
    deps, _snap, send, _status = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    out = RUN.run_pass(T1, store=st, deps=deps)
    assert out["ran"] and out["status"] == "ok" and out["errors"] == []
    pot = out["potential"]
    sent = [p for (_o, p), _k in deps.send_potential.calls]
    # one push per (symbol, setup) forming with its sideways part begun — the flag, plus any other setup the same
    # bars read as a potential (K3 / HIS CALL P6); each its own push, never twice
    assert pot["new"] == pot["potential"] == pot["pushed"] == len(sent) >= 1
    assert len({p["tag"] for p in sent}) == len(sent)
    flag = [p for p in sent if p["url"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=GGA"]
    assert len(flag) == 1 and flag[0]["kind"] == "gajjala_potential"
    assert flag[0]["title"] == "🧠 GGA · 🚩 Bull Flag — trigger armed · UNMEASURED"
    assert {o for (o, _p), _k in deps.send_potential.calls} == {"owner@example.com"}
    docs = [d for d in st.coll(ST.POTENTIALS).docs.values() if d.get("symbol") == "GGA"]
    assert len(docs) == len(sent) and all(d["push"]["state"] == "pushed" for d in docs)
    bf = st.get_potential(S, "GGA", "bull_flag")
    assert bf["first_seen_et"] == "10:31" and bf["first_kind"] == "armed" and bf["first_px"] == FX.P1[3]
    assert bf["first_tells"]["float_text"] and bf["first_tells"]["float_shares"] == 5_000_000
    assert send.calls == []                                          # the A+ sender: nothing (no A+, and shadow)
    assert len(deps.record_potential_status.calls) == 1
    (counts, _now, reason), _ = deps.record_potential_status.calls[0]
    assert counts["pushed"] == len(sent) and reason is None
    assert st.latest_pass()["potential"]["pushed"] == len(sent)


def test_NEGATIVE_D9_a_mid_session_first_pass_joins_and_never_rings():
    st = fake_store()
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    out = RUN.run_pass(T1, store=st, deps=deps)
    assert deps.send_potential.calls == [] and out["potential"]["joined"] >= 1 and out["potential"]["pushed"] == 0
    doc = st.get_potential(S, "GGA", "bull_flag")
    assert doc["first_seen_mode"] == "joined" and [h["reason"] for h in doc["held"]] == ["joined_midsession"]


def test_D9_an_unbroken_pass_chain_with_nothing_forming_lets_the_first_sighting_ring():
    """Fix round 1 (2026-10-15): the 10:26 pass ran the 🧠 gate (nothing listed, nothing forming) and _finish wrote its
    pass doc with a `potential` block; the 10:31 pass is the next link of the chain — a normal first sighting (K3)."""
    st = fake_store()
    quiet, *_ = make_deps(rows={"NOPE": snap_row(1.0, 0.95, when=at(10, 25))})
    first = RUN.run_pass(at(10, 26), store=st, deps=quiet)
    assert first["ran"] and first["potential"]["potential"] == 0 and isinstance(st.latest_pass()["potential"], dict)
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    out = RUN.run_pass(T1, store=st, deps=deps)
    assert out["potential"]["joined"] == 0 and out["potential"]["pushed"] == len(deps.send_potential.calls) >= 1
    assert st.get_potential(S, "GGA", "bull_flag")["first_seen_mode"] == "normal"


def test_NEGATIVE_D9_a_gap_in_the_pass_chain_joins_and_never_rings():
    """The gate ran at 07:56 (nothing forming), then no pass until 10:31 (a host sleep): the 10:31 pass joins."""
    st = fake_store()
    quiet, *_ = make_deps(rows={"NOPE": snap_row(1.0, 0.95, when=at(7, 55))})
    assert RUN.run_pass(at(7, 56), store=st, deps=quiet)["ran"]
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    out = RUN.run_pass(T1, store=st, deps=deps)
    assert deps.send_potential.calls == [] and out["potential"]["joined"] >= 1 and out["potential"]["pushed"] == 0
    assert st.get_potential(S, "GGA", "bull_flag")["first_seen_mode"] == "joined"


def test_D2_a_name_that_stops_qualifying_follows_the_bars_not_the_stored_row():
    st = _seeded()
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    RUN.run_pass(T1, store=st, deps=deps)
    deps2, *_ = make_deps(rows={"NOPE": snap_row(1.0, 0.95, when=at(10, 35))})    # GGA did not qualify at T2
    out = RUN.run_pass(T2, store=st, deps=deps2)
    assert "GGA" not in out["qualifiers"] and out["n_read"] == 1
    doc = st.get_potential(S, "GGA", "bull_flag")
    assert doc["first_px"] == FX.P1[3] and doc["last"]["px"] == FX.P2[3] != 11.2
    assert doc["move_pct"] == round((FX.P2[3] / FX.P1[3] - 1) * 100, 2) != 0
    assert len(deps2.send_potential.calls) == 0                     # rang once at T1, never twice (K3)


def test_NEGATIVE_D1_a_raising_potential_gate_never_silences_the_pass(monkeypatch):
    from chart_maps.gajjala import potential as PT
    monkeypatch.setattr(PT, "run_pass", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("pot down")))
    st = _seeded()
    deps, _snap, _send, status = make_deps()
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert "potential" in out["errors"] and out["potential"] == {} and out["status"] == "ok"
    latest = st.latest_pass()
    assert latest["strip"] and latest["counts"] and latest["alerts"]["aplus"] >= 1
    (_c, _n, reason), _ = status.calls[0]
    assert reason is None                                            # the 🚩 row is not marked by the 🧠 failure
    (pc, _n2, preason), _ = deps.record_potential_status.calls[0]
    assert pc == {} and preason == "pass error: potential"


def test_NEGATIVE_D1_a_raising_a_plus_gate_still_runs_the_potential_gate(monkeypatch):
    from chart_maps.gajjala import alerts as AL
    monkeypatch.setattr(AL, "run_pass", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("A+ down")))
    st = _seeded()
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    out = RUN.run_pass(T1, store=st, deps=deps)
    assert "alerts" in out["errors"] and out["status"] == "error"
    assert out["potential"]["pushed"] == len(deps.send_potential.calls) >= 1
    assert st.latest_pass()["strip"] is not None
    (_pc, _n, preason), _ = deps.record_potential_status.calls[0]
    assert preason is None


def test_NEGATIVE_the_dry_run_records_no_potential_write_and_sends_nothing(live):
    real = fake_store()
    st = RUN.dry_store(real)
    deps = RUN.dry_deps()
    base, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    for k in ("snapshot", "load_day", "halts", "status_lookup", "massive_lookup", "fetch_splits", "fetch_types",
              "daily_loader"):
        setattr(deps, k, getattr(base, k))
    out = RUN.run_pass(T1, store=st, deps=deps, dry=True)
    assert out["potential"]["potential"] >= 1
    assert [w for w in st.writes if w[0] == "gajjala_potentials"] == []
    assert deps.sent_potential == [] and real.coll("gajjala_potentials").writes == 0


def test_the_pass_reads_the_same_ctx_the_read_doc_stores(monkeypatch):
    from chart_maps.gajjala import potential as PT
    seen = {}
    real = PT.run_pass

    def spy(*a, **k):
        seen.update(k)
        return real(*a, **k)
    monkeypatch.setattr(PT, "run_pass", spy)
    st = _seeded()
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    RUN.run_pass(T1, store=st, deps=deps)
    assert seen["ctx"]["GGA"] == st.get_read(S, "GGA")["ctx"]
    assert seen["send"] is deps.send_potential and seen["tape"] == "rth" and seen["live_rows"]["GGA"]["price"] == 11.2


def test_NEGATIVE_no_crontab_line_names_potential():
    lines = [ln for ln in (ROOT / "crontab").read_text().splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    assert not [ln for ln in lines if "potential" in ln]


# ── 🔄 scan on open (2026-10-15 — DECISIONS5 K2/K4, C1–C7, AMENDMENTS5 A1, A5–A10, A13) ─────────────────────────────
# Ajay 2026-10-15: "When ever I open Gajjala's intiate a new scan of stocks.  In that moment and if there are any
# enterable stocks on the top which I see in potential i guess". An open never rings a device and never makes a cron
# tick skip, refuse or delay its gates beyond the bounded wait.
import copy                                                            # noqa: E402
import logging                                                         # noqa: E402
from datetime import timezone                                          # noqa: E402

from chart_maps.gajjala import store as ST                             # noqa: E402
from tests.test_gajjala_store import FakeColl                          # noqa: E402

POLLS = int(GC.CRON_WAIT_ON_DEMAND_SEC // GC.ON_DEMAND_POLL_SEC)


def _u(dt):
    return RUN._utc(dt)


def _lease(st):
    return st.coll(ST.STATE).docs.get(ST.LEASE_ID)


class Sleeps:
    def __init__(self, on=None):
        self.calls, self.on = [], on

    def __call__(self, s):
        self.calls.append(s)
        if self.on:
            self.on(len(self.calls))


def test_C1_a_cron_tick_waits_for_an_on_open_pass_then_runs():
    st = fake_store()
    o = st.claim_lease(_u(NOW - timedelta(seconds=5)), source=ST.LEASE_ON_DEMAND)
    sleeps = Sleeps(on=lambda n: n == 3 and st.release_lease(_u(NOW), o.token))
    deps, snapshot, _send, status = make_deps()
    deps.sleep = sleeps
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["ran"] and out["lease"]["why"] == "claimed" and out.get("reason") is None
    assert out["lease"]["waited_s"] == 3 * GC.ON_DEMAND_POLL_SEC and sleeps.calls == [GC.ON_DEMAND_POLL_SEC] * 3
    assert len(snapshot.calls) == 1 and len(status.calls) == 1
    assert _lease(st)["status"] == "done" and _lease(st)["last_cron_started_at"] == _u(NOW)   # A6: the tick clock
    assert out["on_demand"] is False and st.latest_cron_pass()["_id"] == "latest_cron"


def test_C1_NEGATIVE_a_stuck_on_open_lease_never_refuses_the_cron():
    st = fake_store()
    o = st.claim_lease(_u(NOW - timedelta(seconds=5)), source=ST.LEASE_ON_DEMAND)
    sleeps = Sleeps()
    deps, snapshot, _send, status = make_deps()
    deps.sleep = sleeps
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["ran"] and out["lease"]["why"] == "taken_over" and len(sleeps.calls) == POLLS
    assert out["lease"]["waited_s"] == GC.CRON_WAIT_ON_DEMAND_SEC and len(snapshot.calls) == 1
    lease = copy.deepcopy(_lease(st))
    assert lease["status"] == "done" and lease["held_by"] == ST.LEASE_CRON and lease["token"] != o.token
    assert st.release_lease(_u(NOW + timedelta(minutes=1)), o.token) is False      # the stuck holder frees nothing
    assert _lease(st) == lease


def test_C1_NEGATIVE_a_cron_held_lease_never_makes_a_cron_wait():
    st = fake_store()
    assert st.claim_lease(_u(NOW - timedelta(seconds=20)))
    sleeps = Sleeps()
    deps, snapshot, *_ = make_deps()
    deps.sleep = sleeps
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["ran"] is False and out["lease"]["why"] == "held" and out["reason"] == RUN._LEASE_REASON["held"]
    assert sleeps.calls == [] and snapshot.calls == []


def test_C1_NEGATIVE_an_open_never_moves_the_cron_min_gap():
    st = fake_store()
    assert RUN.run_pass(at(10, 26), store=st, deps=make_deps()[0])["ran"]
    dup = RUN.run_pass(at(10, 28), store=st, deps=make_deps()[0])
    assert dup["ran"] is False and dup["lease"]["why"] == "gap" and "lease" in dup["reason"]   # unchanged guard
    assert RUN.run_on_demand(at(10, 28), store=st, deps=make_deps()[0])["ran"]
    assert RUN.run_on_demand(at(10, 30, ss=59), store=st, deps=make_deps()[0])["ran"]
    assert _lease(st)["last_cron_started_at"] == _u(at(10, 26))
    out = RUN.run_pass(at(10, 31), store=st, deps=make_deps()[0])
    assert out["ran"] and out["lease"]["why"] == "claimed"


def test_C1_an_on_open_pass_skips_the_gap_but_never_a_held_lease():
    st = fake_store()
    assert RUN.run_pass(NOW, store=st, deps=make_deps()[0])["ran"]
    od = RUN.run_on_demand(NOW + timedelta(seconds=30), store=st, deps=make_deps()[0])
    assert od["ran"] and od["lease"]["why"] == "claimed" and od["on_demand"] is True
    for holder in (ST.LEASE_CRON, ST.LEASE_ON_DEMAND):
        st2 = fake_store()
        assert st2.claim_lease(_u(NOW), source=holder)
        sleeps = Sleeps()
        deps, snapshot, *_ = make_deps()
        deps.sleep = sleeps
        out = RUN.run_on_demand(NOW + timedelta(seconds=10), store=st2, deps=deps)
        assert out["ran"] is False and out["reason"] == RUN._ON_DEMAND_REFUSED and out["lease"]["why"] == "held"
        assert snapshot.calls == [] and sleeps.calls == []


def test_A6_a_late_tick_that_waits_the_full_bound_never_gaps_the_next_on_time_tick():
    """Measured: cron start offsets max 58.5 s. A tick 58 s late meets a stuck open, waits CRON_WAIT_ON_DEMAND_SEC, takes
    over — its gap clock is the TICK, so the on-time next tick still claims."""
    st = fake_store()
    assert RUN.run_pass(at(10, 26), store=st, deps=make_deps()[0])["ran"]
    assert st.claim_lease(_u(at(10, 31, ss=50)), source=ST.LEASE_ON_DEMAND)
    late = RUN.run_pass(at(10, 31, ss=58), store=st, deps=make_deps()[0])
    assert late["ran"] and late["lease"]["why"] == "taken_over"
    assert late["lease"]["waited_s"] == GC.CRON_WAIT_ON_DEMAND_SEC
    assert _lease(st)["last_cron_started_at"] == _u(at(10, 31, ss=58))
    nxt = RUN.run_pass(at(10, 36), store=st, deps=make_deps()[0])
    assert nxt["ran"] and nxt["lease"]["why"] == "claimed"               # never "gap"


class _ReleaseOnSecondLeaseRead(FakeColl):
    """The on-open holder releases between the cron's 2nd attempt and its classify read (AMENDMENTS5 A7)."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.lease_reads = 0

    def find_one(self, q=None, projection=None):
        if q == {"_id": ST.LEASE_ID}:
            self.lease_reads += 1
            if self.lease_reads == 2:
                self.docs[ST.LEASE_ID]["status"] = "done"
        return super().find_one(q, projection)


def test_A7_a_release_race_inside_the_wait_retries_and_never_takes_over():
    coll = _ReleaseOnSecondLeaseRead()
    st = fake_store(**{ST.STATE: coll})
    st.claim_lease(_u(NOW - timedelta(seconds=5)), source=ST.LEASE_ON_DEMAND)
    sleeps = Sleeps()
    deps, snapshot, *_ = make_deps()
    deps.sleep = sleeps
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["ran"] and out["lease"]["why"] == "claimed" and len(sleeps.calls) == 2
    assert len(snapshot.calls) == 1


class _ReleaseOnFirstLeaseRead(_ReleaseOnSecondLeaseRead):
    """The on-open holder releases between the cron's FIRST attempt and its classify read (round-1 finding)."""
    def find_one(self, q=None, projection=None):
        if q == {"_id": ST.LEASE_ID}:
            self.lease_reads += 1
            if self.lease_reads == 1:
                self.docs[ST.LEASE_ID]["status"] = "done"
        return FakeColl.find_one(self, q, projection)


def test_C1_NEGATIVE_a_release_race_on_the_first_claim_never_costs_the_tick():
    coll = _ReleaseOnFirstLeaseRead()
    st = fake_store(**{ST.STATE: coll})
    st.claim_lease(_u(NOW - timedelta(seconds=30)), source=ST.LEASE_ON_DEMAND)
    sleeps = Sleeps()
    deps, snapshot, *_ = make_deps()
    deps.sleep = sleeps
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["ran"] and out["lease"]["why"] == "claimed" and out["lease"]["waited_s"] == 0.0
    assert out.get("reason") is None and sleeps.calls == [] and len(snapshot.calls) == 1
    assert _lease(st)["held_by"] == ST.LEASE_CRON and _lease(st)["last_cron_started_at"] == _u(NOW)


def test_C1_NEGATIVE_a_real_store_fault_is_retried_once_then_refused_without_waiting():
    st = fake_store(**{ST.STATE: FakeColl(fail=True)})
    calls = []
    real = st.claim_lease

    def spy(*a, **k):
        calls.append(k.get("take_over", False))
        return real(*a, **k)
    st.claim_lease = spy
    sleeps = Sleeps()
    deps, snapshot, *_ = make_deps()
    deps.sleep = sleeps
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["ran"] is False and out["lease"]["why"] == "error" and out["reason"] == RUN._LEASE_REASON["error"]
    assert calls == [False, False] and sleeps.calls == [] and snapshot.calls == []      # one immediate retry, no wait


def test_C1_NEGATIVE_a_cron_that_waited_spends_the_wait_out_of_its_own_bar_budget(monkeypatch):
    from chart_maps.gajjala import bars as B
    budgets = []
    real = B.frames_for

    def spy(*a, **k):
        budgets.append(k["budget_sec"])
        return real(*a, **k)
    monkeypatch.setattr(B, "frames_for", spy)
    clock = {"t": 0.0}

    def tick_sleep(s):
        clock["t"] += s
    for release_at in (None, 3):                                          # stuck → take-over; released at the 3rd poll
        st = fake_store()
        o = st.claim_lease(_u(NOW - timedelta(seconds=5)), source=ST.LEASE_ON_DEMAND)
        deps, *_ = make_deps(clock=lambda: clock["t"])
        deps.sleep = Sleeps(on=lambda n, st=st, o=o, r=release_at: (tick_sleep(GC.ON_DEMAND_POLL_SEC),
                                                                    r and n == r and st.release_lease(_u(NOW), o.token)))
        out = RUN.run_pass(NOW, store=st, deps=deps)
        waited = out["lease"]["waited_s"]
        assert out["ran"] and waited > 0
        assert budgets[-1] <= GC.PASS_BUDGET_SEC - waited                # never the full budget after a wait
        assert waited + budgets[-1] <= GC.PASS_BUDGET_SEC                 # ends inside the tick's original window
    st = fake_store()
    assert RUN.run_pass(NOW, store=st, deps=make_deps()[0])["ran"]
    assert GC.PASS_BUDGET_SEC - 1.0 < budgets[-1] <= GC.PASS_BUDGET_SEC  # positive control: no wait → full budget


def test_A5_NEGATIVE_naive_lease_stamps_make_the_cron_wait_and_take_over_never_error():
    st = fake_store()
    naive = lambda dt: _u(dt).astimezone(timezone.utc).replace(tzinfo=None)   # noqa: E731
    st.coll(ST.STATE).docs[ST.LEASE_ID] = {"_id": ST.LEASE_ID, "status": "running", "held_by": ST.LEASE_ON_DEMAND,
                                           "token": "od", "claimed_at": naive(NOW - timedelta(seconds=5)),
                                           "od_started_at": naive(NOW - timedelta(seconds=5)),
                                           "last_cron_started_at": naive(NOW - timedelta(minutes=5))}
    sleeps = Sleeps()
    deps, *_ = make_deps()
    deps.sleep = sleeps
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["ran"] and out["lease"]["why"] == "taken_over" and len(sleeps.calls) == POLLS


def test_K2_an_on_open_pass_never_sends_never_claims_never_writes_the_tracker_never_records_an_alerts_row(live):
    st = fake_store()
    deps, _snap, send, status = make_deps()
    out = RUN.run_on_demand(NOW, store=st, deps=deps)
    assert out["ran"] and out["status"] == "ok" and "GGA:bull_flag" in out["aplus"]
    assert send.calls == [] and deps.send_potential.calls == []
    assert st.alerts_coll().docs == {}                                    # no claim, no SHADOW: row, no #state row
    assert status.calls == [] and deps.record_potential_status.calls == []
    assert out["alerts"]["dry"] >= 1 and out["alerts"]["pushed"] == 0
    assert st.get_read(S, "GGA")["updated_at"] == _u(NOW)                 # the read IS refreshed
    assert "2026-10-13|GGA" in st.coll(ST.SCAN).docs
    ids = [k for k in st.coll(ST.PASSES).docs if k.endswith("|open")]
    assert ids == ["2026-10-13|10:41:00|open"]
    doc = st.coll(ST.PASSES).docs[ids[0]]
    assert doc["on_demand"] is True and doc["bars_through_et"] == "10:40" and doc["lease"]["why"] == "claimed"
    assert doc["finished_at"] >= doc["at"]
    assert st.latest_pass()["pass_id"] == ids[0] and st.latest_cron_pass() is None     # A10: the cron pointer untouched
    assert _lease(st)["status"] == "done" and "started_at" not in _lease(st)             # A9


def test_K2_NEGATIVE_an_on_open_forming_flag_never_rings_and_never_tracks(live):
    st = _seeded()
    seed = copy.deepcopy(st.coll(ST.POTENTIALS).docs)
    deps, _snap, send, status = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    out = RUN.run_on_demand(T1, store=st, deps=deps)
    assert out["ran"] and out["potential"]["potential"] >= 1 and out["potential"]["dry"] >= 1
    assert deps.send_potential.calls == [] and send.calls == []
    assert st.coll(ST.POTENTIALS).docs == seed                            # only SEED: no tracker write
    assert status.calls == [] and deps.record_potential_status.calls == []
    assert out["potential"]["tracked_today"] == 1                         # the real (cron-written) count, dry or not


def test_C7_an_on_open_pass_never_refines_floats(monkeypatch):
    from chart_maps.gajjala import context as CX
    seen = []
    real = CX.floats_for

    def spy(*a, **k):
        seen.append(bool(k.get("refine")))
        return real(*a, **k)
    monkeypatch.setattr(CX, "floats_for", spy)
    st = fake_store()
    deps, *_ = make_deps()
    deps.refine_floats = True
    assert RUN.run_on_demand(NOW, store=st, deps=deps)["ran"]
    assert seen and True not in seen
    seen.clear()
    assert RUN.run_pass(NOW + timedelta(seconds=GC.PASS_CADENCE_SEC), store=st, deps=deps)["ran"]
    assert True in seen                                                   # positive control: the cron refines


def test_C2_the_on_open_budget_is_the_short_one_and_an_overrun_keeps_the_last_read(monkeypatch):
    from chart_maps.gajjala import bars as B
    budgets = []
    real = B.frames_for

    def spy(*a, **k):
        budgets.append(k["budget_sec"])
        return real(*a, **k)
    monkeypatch.setattr(B, "frames_for", spy)
    st = fake_store()
    assert RUN.run_pass(NOW, store=st, deps=make_deps()[0])["ran"]
    assert GC.ON_DEMAND_BUDGET_SEC < budgets[-1] <= GC.PASS_BUDGET_SEC
    cron_id = st.latest_pass()["pass_id"]
    read = copy.deepcopy(st.get_read(S, "GGA"))
    assert read["updated_at"] == _u(NOW)
    ticks = iter([0.0] + [GC.ON_DEMAND_BUDGET_SEC + 1.0] * 50)
    deps, *_ = make_deps(clock=lambda: next(ticks))
    out = RUN.run_on_demand(NOW + timedelta(seconds=60), store=st, deps=deps)
    assert budgets[-1] <= GC.ON_DEMAND_BUDGET_SEC
    assert out["ran"] and out["bars"]["over_budget"] == 1 and out["n_read"] == 0
    assert st.get_read(S, "GGA") == read                                  # the name keeps its last cron read
    assert st.latest_pass()["pass_id"] == cron_id                         # A13: nothing re-read → "latest" stays
    assert "2026-10-13|10:42:00|open" in st.coll(ST.PASSES).docs          # the open's own doc is still on file


def test_C5_a_quiet_mornings_first_sighting_still_rings_on_the_next_cron_after_an_on_open_pass():
    st = fake_store()
    quiet, *_ = make_deps(rows={"NOPE": snap_row(1.0, 0.95, when=at(10, 25))})
    assert RUN.run_pass(at(10, 26), store=st, deps=quiet)["ran"]
    od, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    o = RUN.run_on_demand(at(10, 30, ss=40), store=st, deps=od)
    assert o["ran"] and o["potential"]["potential"] >= 1 and o["potential"]["dry"] >= 1
    assert o["potential"]["joined"] == 0 and od.send_potential.calls == []
    assert st.coll(ST.POTENTIALS).docs == {}
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    out = RUN.run_pass(T1, store=st, deps=deps)
    assert out["ran"] and out["potential"]["joined"] == 0
    assert out["potential"]["pushed"] == len(deps.send_potential.calls) >= 1
    bf = st.get_potential(S, "GGA", "bull_flag")
    assert bf["first_seen_mode"] == "normal" and bf["first_seen_et"] == "10:31"


def test_C5_NEGATIVE_an_on_open_join_never_unlocks_the_next_cron():
    st = fake_store()
    od, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    o = RUN.run_on_demand(at(10, 30, ss=40), store=st, deps=od)
    assert o["potential"]["joined"] >= 1 and o["potential"]["tracked_today"] == 0
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    out = RUN.run_pass(T1, store=st, deps=deps)
    assert out["potential"]["joined"] >= 1 and deps.send_potential.calls == []


def test_C5_an_on_open_pass_doc_never_overwrites_the_cron_minute_doc():
    st = fake_store()
    assert RUN.run_pass(at(10, 31), store=st, deps=make_deps()[0])["ran"]
    cron = copy.deepcopy(st.coll(ST.PASSES).docs["2026-10-13|10:31"])
    assert RUN.run_on_demand(at(10, 31, ss=40), store=st, deps=make_deps()[0])["ran"]
    docs = st.coll(ST.PASSES).docs
    assert "2026-10-13|10:31:40|open" in docs and docs["2026-10-13|10:31"] == cron
    assert docs["latest_cron"]["pass_id"] == "2026-10-13|10:31" and docs["latest"]["pass_id"].endswith("|open")


@pytest.mark.parametrize("now", [at(3, 59), at(20, 6), at(10, 41, date(2026, 10, 17)), at(10, 41, date(2026, 9, 7))])
def test_C6_an_on_open_pass_outside_the_window_never_claims(now):
    st = fake_store()
    deps, snapshot, *_ = make_deps()
    out = RUN.run_on_demand(now, store=st, deps=deps)
    assert out["ran"] is False and snapshot.calls == [] and st.coll(ST.STATE).docs == {}


def test_latest_never_moves_back():
    st = fake_store()
    assert RUN.run_pass(at(10, 41, ss=30), store=st, deps=make_deps()[0])["ran"]       # started later, recorded first
    assert RUN.run_on_demand(at(10, 41), store=st, deps=make_deps()[0])["ran"]
    assert st.latest_pass()["pass_id"] == "2026-10-13|10:41"
    assert "2026-10-13|10:41:00|open" in st.coll(ST.PASSES).docs


def test_A8_a_superseded_on_open_pass_stops_writing_and_the_cron_reads_survive(monkeypatch):
    st = fake_store()
    rows = {"GGA": snap_row(11.2, 8.0), "GGB": snap_row(11.2, 8.0)}
    for s in ("GGA", "GGB"):
        st.upsert_read(S, s, {"setups": {}, "by": "cron"}, now=_u(NOW + timedelta(minutes=1)))
    cron_reads = copy.deepcopy(st.coll(ST.READS).docs)
    written, frozen = [], {}
    real = st.upsert_read

    def upsert_then_flip(session, sym, doc, *, now=None):
        written.append(sym)
        real(session, sym, doc, now=now)
        _lease(st)["token"] = "the-cron-took-it-over"
        frozen.update({n: c.writes for n, c in st._injected.items()})
    monkeypatch.setattr(st, "upsert_read", upsert_then_flip)
    lease_at_flip = {}
    real_release = st.release_lease

    def release_spy(now, token=None):
        lease_at_flip.update(copy.deepcopy(_lease(st)))
        return real_release(now, token)
    monkeypatch.setattr(st, "release_lease", release_spy)
    deps, *_ = make_deps(rows=rows)
    out = RUN.run_on_demand(NOW, store=st, deps=deps)
    assert out["superseded"] == 1 and out["status"] == "superseded" and len(written) == 1
    after = {n: c.writes for n, c in st._injected.items()}
    # zero writes after the flip — but the token-guarded release attempt (an update_one that matches nothing)
    assert {n: w for n, w in after.items() if n != ST.STATE} == {n: w for n, w in frozen.items() if n != ST.STATE}
    assert after[ST.STATE] - frozen[ST.STATE] <= 1
    other = ({"GGA", "GGB"} - set(written)).pop()
    assert st.coll(ST.READS).docs[f"2026-10-13|{other}"] == cron_reads[f"2026-10-13|{other}"]
    assert not [k for k in st.coll(ST.PASSES).docs if k.endswith("|open")] and st.latest_pass() is None
    assert _lease(st) == lease_at_flip and _lease(st)["status"] == "running"   # the cron's lease is untouched


def test_A8_a_failed_owner_read_stops_the_open_and_frees_its_own_lease(monkeypatch):
    """lease_owner_is fails closed on a read fault: the open stops writing, and its token-guarded release frees its
    OWN lease — so the next cron claims at once instead of waiting CRON_WAIT_ON_DEMAND_SEC."""
    st = fake_store()
    monkeypatch.setattr(st, "lease_owner_is", lambda token: False)       # = the find_one raised
    deps, *_ = make_deps()
    out = RUN.run_on_demand(NOW, store=st, deps=deps)
    assert out["superseded"] == 1 and out["status"] == "superseded"
    assert _lease(st)["status"] == "done" and _lease(st)["held_by"] == ST.LEASE_ON_DEMAND
    sleeps = Sleeps()
    deps, snapshot, *_ = make_deps()
    deps.sleep = sleeps
    nxt = RUN.run_pass(NOW + timedelta(seconds=GC.PASS_CADENCE_SEC), store=st, deps=deps)
    assert nxt["ran"] and nxt["lease"]["why"] == "claimed" and sleeps.calls == []


def test_A8_a_superseded_open_that_then_raises_writes_no_error_doc():
    """Final critic 2026-10-16: the lease flips, then the body raises an ORDINARY exception (not _Superseded) before
    its last owner check — _finish checks the owner before the pass doc, so no "|open" doc lands."""
    st = fake_store()
    deps, *_ = make_deps()

    def flip_then_raise(frames, ctx):
        _lease(st)["token"] = "the-cron-took-it-over"
        raise RuntimeError("detector broke")
    deps.read_all = flip_then_raise
    out = RUN.run_on_demand(NOW, store=st, deps=deps)
    assert out["superseded"] == 1 and out["status"] == "superseded" and out["reason"].startswith("superseded")
    assert not [k for k in st.coll(ST.PASSES).docs if k.endswith("|open")] and st.latest_pass() is None
    assert _lease(st)["token"] == "the-cron-took-it-over" and _lease(st)["status"] == "running"


def test_NEGATIVE_A8_an_open_that_raises_while_it_still_owns_the_lease_writes_its_error_doc():
    st = fake_store()
    deps, *_ = make_deps()

    def boom(frames, ctx):
        raise RuntimeError("detector broke")
    deps.read_all = boom
    out = RUN.run_on_demand(NOW, store=st, deps=deps)
    assert out["status"] == "error" and "superseded" not in out
    opens = [d for k, d in st.coll(ST.PASSES).docs.items() if k.endswith("|open")]
    assert len(opens) == 1 and opens[0]["status"] == "error" and _lease(st)["status"] == "done"


def test_NEGATIVE_A8_a_cron_pass_never_reads_the_owner_check(monkeypatch):
    st = fake_store()
    monkeypatch.setattr(st, "lease_owner_is", lambda *a, **k: pytest.fail("the cron never checks"))
    assert RUN.run_pass(NOW, store=st, deps=make_deps()[0])["ran"]


# ── main --on-demand (AMENDMENTS5 A1: the api spawns `python -m chart_maps.gajjala.run --on-demand`) ─────────────────
def test_A1_main_on_demand_dry_run_uses_a_dry_store_and_both_gates_dry(monkeypatch, live, caplog):
    base, snapshot, send, status = make_deps()
    real = fake_store()
    seen = {}
    real_dry_store, real_run = RUN.dry_store, RUN.run_on_demand
    monkeypatch.setattr(RUN, "dry_deps", lambda: base)
    monkeypatch.setattr(RUN, "dry_store", lambda *a, **k: real_dry_store(real))

    def spy(now, **k):
        seen.update(k)
        return real_run(now, **k)
    monkeypatch.setattr(RUN, "run_on_demand", spy)
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")
    assert RUN.main(["--on-demand", "--dry-run", "--now", "2026-10-13T10:41"]) == 0
    assert getattr(seen["store"], "dry", False) is True and seen["deps"] is base
    assert send.calls == [] and base.send_potential.calls == [] and status.calls == []
    assert base.record_potential_status.calls == [] and len(snapshot.calls) == 1
    assert all(c.writes == 0 for c in real._injected.values())          # a dry store lands nothing
    assert seen["store"].writes                                           # … and recorded what it would have written
    assert any("gajjala on-open pass:" in r.getMessage() and "'lease'" in r.getMessage() for r in caplog.records)


def test_A1_NEGATIVE_main_on_demand_outside_the_window_never_runs(monkeypatch):
    monkeypatch.setattr(RUN, "run_on_demand", lambda *a, **k: pytest.fail("no on-open pass outside the window"))
    monkeypatch.setattr(RUN, "run_pass", lambda *a, **k: pytest.fail("no pass outside the window"))
    assert RUN.main(["--on-demand", "--now", "2026-10-13T20:10"]) == 0
    assert RUN.main(["--on-demand", "--now", "2026-10-17T10:41"]) == 0   # Saturday


def test_A1_main_on_demand_uses_the_real_store_and_exits_1_on_an_error(monkeypatch):
    st = fake_store()
    monkeypatch.setattr(ST, "default", lambda: st)
    calls = []
    monkeypatch.setattr(RUN, "run_pass", lambda *a, **k: pytest.fail("the cron path never runs"))
    monkeypatch.setattr(RUN, "run_on_demand", lambda now, **k: (calls.append(k), {"status": "ok"})[1])
    assert RUN.main(["--on-demand", "--now", "2026-10-13T10:41"]) == 0
    assert calls[0]["store"] is st and isinstance(calls[0]["deps"], RUN.Deps)
    monkeypatch.setattr(RUN, "run_on_demand", lambda now, **k: {"status": "error"})
    assert RUN.main(["--on-demand", "--now", "2026-10-13T10:41"]) == 1
    monkeypatch.setattr(RUN, "run_on_demand", lambda now, **k: {"status": "superseded"})
    assert RUN.main(["--on-demand", "--now", "2026-10-13T10:41"]) == 0


def test_the_cron_log_line_carries_the_lease(monkeypatch, caplog):
    monkeypatch.setattr(RUN, "run_pass", lambda now, **k: {"status": "ok", "lease": {"why": "taken_over"}})
    monkeypatch.setattr(ST, "default", lambda: fake_store())
    caplog.set_level(logging.INFO, logger="chart_maps.gajjala.run")
    assert RUN.main(["--now", "2026-10-13T10:41"]) == 0
    msg = [r.getMessage() for r in caplog.records if r.getMessage().startswith("gajjala pass:")]
    assert msg and "taken_over" in msg[0] and "on-open" not in msg[0]


def test_run_on_demand_is_run_pass_with_on_demand_and_no_yahoo(monkeypatch):
    seen = {}
    monkeypatch.setattr(RUN, "run_pass", lambda now, **k: (seen.update(k), {"ran": False})[1])
    RUN.run_on_demand(NOW, store="S")
    assert seen["on_demand"] is True and seen["store"] == "S" and seen["deps"].refine_floats is False


def test_NEGATIVE_no_crontab_line_names_the_on_open_pass():
    lines = [ln for ln in (ROOT / "crontab").read_text().splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    assert not [ln for ln in lines if re.search(r"on_demand|on.demand|on.open|gajjala\.scan", ln)]
