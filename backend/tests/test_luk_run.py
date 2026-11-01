"""🥇 Luk's pass (chart_maps/luk/run.py — BUILD_SPEC §3.8, WP-A4, 2026-11-01).

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources."

The pass's ORCHESTRATION is pinned here over in-memory stores and faked steps (the steps' own engines are pinned in
their own files): the 16-step order, every provider dependency counted in `calls`, the [fixed: C1] bars-through clock
(written to luk_state, read by the next pass's detectors), a dry pass that lands nothing, the lease, the switch, the
window, the slot arithmetic, the detached child and the CLI refusals. NEGATIVES throughout.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import run as GR
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala import store as GS
from chart_maps.luk import alerts as AL
from chart_maps.luk import bars as BA
from chart_maps.luk import constants as LC
from chart_maps.luk import daily as DA
from chart_maps.luk import detectors as DT
from chart_maps.luk import ledger as LG
from chart_maps.luk import market_state as MS
from chart_maps.luk import run as LR
from chart_maps.luk import screens as SC
from chart_maps.luk import store as ST
from tests.test_gajjala_store import FakeColl

ET = ZoneInfo("America/New_York")
DAY = "2026-11-03"                                   # a Tuesday, a market day
PRIOR = "2026-11-02"


def at(hhmm: str, sec: int = 0, day: str = DAY) -> datetime:
    return datetime.fromisoformat(f"{day}T{hhmm}:00").replace(tzinfo=ET) + timedelta(seconds=sec)


class Rec:
    def __init__(self, ret=None):
        self.calls = []
        self.ret = ret

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self.ret(*a, **k) if callable(self.ret) else self.ret


def mk_colls() -> dict:
    colls = {n: FakeColl() for n in ST.LOGICAL}
    colls[ST.SCREENS_KEY] = FakeColl()
    return colls


def mk_store(colls=None):
    colls = colls if colls is not None else mk_colls()
    return ST.LukStore(colls=colls), colls


ROWS = {"AAA": {"close": 10.0, "change_pct": 4.0}, "BBB": {"close": 20.0, "change_pct": -9.0},
        "ETF1": {"close": 30.0, "change_pct": 20.0}, "NOPX": {"close": None, "change_pct": 50.0}}
TYPES = {"AAA": "CS", "BBB": "ADRC", "ETF1": "ETF", "NOPX": "CS"}


class FakeF:
    def __init__(self, t1, t5):
        self.t1, self.t5 = t1, t5
        self.as_of_bar_t = {"1m": t1 and t1.strftime("%Y-%m-%d %H:%M"), "5m": t5 and t5.strftime("%Y-%m-%d %H:%M"),
                            "60m": None}


def fake_steps(monkeypatch, *, t1=None, t5=None, read=None):
    """Every step module faked at its boundary; the fakes CALL the injected provider deps the way the real ones do,
    so the `calls` block is exercised. -> the spies."""
    spies = {"warm": [], "read_all": [], "shortlist": [], "frames_for": [], "grade": [], "screens": []}

    def warm(store, session, priority, *, now, cap_new, budget_sec, clock, cached, fetch):
        spies["warm"].append({"priority": list(priority), "cap_new": cap_new, "budget_sec": budget_sec,
                              "fetch": fetch})
        facts, fetched = {}, 0                    # daily.warm's REAL counters (REFIX 2026-11-01): no own doc here, so
        for s in priority:                        # every name is untrusted; `cached` is never called
            if fetch is not None and fetched < cap_new:
                fetched += 1
                fetch(s, session)
                facts[s] = {"tier": "lead"}
            else:
                facts[s] = DA.pending()
        return {"facts": facts, "doc_hits": 0, "computed": fetched, "fetched": fetched,
                "deferred": len(priority) - fetched, "untrusted": len(priority), "no_frame": 0}

    def index_state(session, *, loader=None, store=None, now=None):
        spies.setdefault("index_store", []).append(store)
        return {s: loader(s) for s in LC.LUK_INDEX_SYMBOLS}

    def shortlist(lists, carried):
        spies["shortlist"].append(set(carried))
        return sorted({r["symbol"] for lst in lists.values() for r in lst}), 0

    def frames_for(names, session, now, *, load_day, budget_sec, stats):
        spies["frames_for"].append({"names": list(names), "budget_sec": budget_sec})
        d = datetime.fromisoformat(DAY).date()
        for s in names:
            load_day(s, datetime.fromisoformat(PRIOR).date(), include_premarket=True, include_afterhours=True)
            load_day(s, d, force=True, include_premarket=True, include_afterhours=True)
        stats.update(loaded=len(names), no_bars=0, failed=0, over_budget=0)
        return {s: FakeF(t1, t5) for s in names}

    def read_all(F, facts, iso, *, prev_through_1m=None):
        spies["read_all"].append(prev_through_1m)
        return dict(read or {})

    monkeypatch.setattr(DA, "warm", warm)
    monkeypatch.setattr(DA, "index_state", index_state)
    monkeypatch.setattr(SC, "row_of", lambda sym, row, facts, cap, iso: {"symbol": sym, "cap_text": "cap"})
    monkeypatch.setattr(SC, "premarket", lambda rows: [dict(r, rank=i + 1) for i, r in enumerate(rows)])
    monkeypatch.setattr(SC, "leader", lambda rows: [])
    monkeypatch.setattr(SC, "potent", lambda rows: [])
    monkeypatch.setattr(SC, "shortlist", shortlist)
    monkeypatch.setattr(MS, "block", lambda states: {"title": "🧭 Indices", "rows": [], "note": ""})
    monkeypatch.setattr(BA, "frames_for", frames_for)
    monkeypatch.setattr(BA, "latest_closed_t", lambda F, tf: F.t1 if tf == "1m" else F.t5)
    monkeypatch.setattr(DT, "read_all", read_all)
    monkeypatch.setattr(LG, "grade_step", lambda *a, **k: spies["grade"].append((a, k)) or {"rows": 0})
    return spies


def fake_deps(**over) -> LR.Deps:
    status = Rec(True)
    d = LR.Deps(snapshot=lambda: (dict(ROWS), {"http": 200, "wall_s": 0.4}), types=lambda: dict(TYPES),
                caps=lambda tickers, px: {t: None for t in tickers}, cached=lambda s, d, now=None: None,
                fetch=lambda s, d: None, load_day=lambda *a, **k: None, index_loader=lambda s: None,
                record_status=status, grade_load_day=lambda s, d: ([], False))
    for k, v in over.items():
        setattr(d, k, v)
    return d


SUMMARY_KEYS = {"ran", "session", "at_et", "dry", "errors", "lease", "snapshot", "screens", "shortlist", "bars",
                "n_read", "states", "aplus", "alerts", "market_state", "ledger", "calls", "bars_through", "wall_s",
                "status"}


# ── the switch, the window, the slot ──────────────────────────────────────────────────────────────────────────────
def test_enabled_reads_the_constant_and_the_env(monkeypatch):
    monkeypatch.delenv("LUK_ENABLED", raising=False)
    assert LR.enabled() is True
    monkeypatch.setenv("LUK_ENABLED", "0")
    assert LR.enabled() is False                                         # NEGATIVE: env off
    monkeypatch.setenv("LUK_ENABLED", "1")
    monkeypatch.setattr(LC, "LUK_ENABLED", False)
    assert LR.enabled() is False                                         # NEGATIVE: constant off


@pytest.mark.parametrize("hhmm,day,ok", [("04:00", DAY, True), ("03:59", DAY, False), ("16:05", DAY, True),
                                         ("16:06", DAY, False), ("17:06", DAY, False), ("10:00", "2026-11-07", False),
                                         ("10:00", "2026-11-26", False)])
def test_in_window_is_04_00_to_16_05_et_on_a_market_day(hhmm, day, ok):
    assert LR.in_window(at(hhmm, day=day)) is ok


def test_in_window_bare_reads_the_wall_clock(monkeypatch):
    monkeypatch.setattr(GR, "_utc", lambda now=None: at("10:00") if now is None else now)
    assert LR.in_window() is True
    monkeypatch.setattr(GR, "_utc", lambda now=None: at("17:06") if now is None else now)
    assert LR.in_window() is False


def test_fits_is_budget_plus_margin_before_the_next_tick():
    nxt = at("10:06")
    room = LC.LUK_PASS_BUDGET_SEC + LC.LUK_SLOT_MARGIN_SEC
    assert LR.fits(nxt - timedelta(seconds=room), nxt) is True                    # exactly fits
    assert LR.fits(nxt - timedelta(seconds=room - 1), nxt) is False               # NEGATIVE: one second short
    assert LR.slot_of(at("10:01", 7)) == R1.slot_of(at("10:01", 7))                # the house grid, imported
    assert LR.slot_of(at("10:01", 7))[1] == at("10:06")


def test_child_refusal_order(monkeypatch):
    monkeypatch.setenv("LUK_ENABLED", "1")
    assert LR.child_refusal(at("10:01", 7)) is None
    assert LR.child_refusal(at("10:04")) == LR.SKIP_SLOT                 # 10:04 + 140 s > the 10:06 tick
    assert LR.child_refusal(at("17:06")) == LR.SKIP_WINDOW
    monkeypatch.setenv("LUK_ENABLED", "0")
    assert LR.child_refusal(at("10:01", 7)) == LR.SKIP_OFF


# ── the child ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_spawn_child_starts_the_detached_child_and_never_raises(monkeypatch):
    spawn = Rec(type("P", (), {"pid": 7})())
    assert LR.spawn_child(spawn) is True
    assert spawn.calls == [((list(LR.ARGV_CHILD), LR.PROC_NAME), {})]
    assert LR.ARGV_CHILD[1:] == ("-m", "chart_maps.luk.run", "--child")

    def boom(*a, **k):
        raise OSError("fork failed")
    assert LR.spawn_child(boom) is False                                 # NEGATIVE: never raises
    popen = Rec(None)
    monkeypatch.setattr(R1, "_popen", popen)                             # the default = run_1m's detached Popen
    assert LR.spawn_child() is True and popen.calls[0][0] == (list(LR.ARGV_CHILD), LR.PROC_NAME)


@pytest.mark.parametrize("why", [LR.SKIP_OFF, LR.SKIP_WINDOW, LR.SKIP_SLOT])
def test_NEGATIVE_a_refused_child_writes_skipped_and_exits_0(monkeypatch, why):
    st, colls = mk_store()
    rp = Rec({"status": "ok"})
    monkeypatch.setattr(LR, "run_pass", rp)
    monkeypatch.setattr(LR, "child_refusal", lambda now=None: why)
    assert LR.main(["--child"], store=st) == 0
    assert rp.calls == []
    doc = colls[GS.STATE].docs[LR.CHILD_STATE_ID]
    assert doc["state"] == "skipped" and doc["reason"] == why


def test_a_child_inside_its_slot_runs_one_pass(monkeypatch):
    st, _colls = mk_store()
    rp = Rec({"status": "ok"})
    monkeypatch.setattr(LR, "run_pass", rp)
    monkeypatch.setattr(LR, "child_refusal", lambda now=None: None)
    assert LR.main(["--child"], store=st) == 0 and len(rp.calls) == 1
    assert rp.calls[0][1]["store"] is st
    rp.ret = {"status": "error"}
    assert LR.main(["--child"], store=st) == 1


def test_NEGATIVE_a_now_replay_without_dry_run_refuses(monkeypatch):
    rp = Rec({"status": "ok"})
    monkeypatch.setattr(LR, "run_pass", rp)
    assert LR.main(["--now", f"{DAY}T09:52"]) == 2
    assert LR.main(["--child", "--now", f"{DAY}T09:52"]) == 2
    assert rp.calls == []


# ── the pass ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _aplus(bar="09:35"):
    return {"opening_range_high": {"setup": "opening_range_high", "state": "aplus", "frame": "1m",
                                   "entry_bar_t": f"{DAY} {bar}", "trigger": 10.0, "stop": 9.7, "risk_pct": 3.0,
                                   "r_usd": 0.3}}


def test_the_pass_counts_every_provider_call_and_serves_the_summary(monkeypatch):
    spies = fake_steps(monkeypatch, t1=at("09:35"), t5=at("09:35"), read=_aplus())
    st, colls = mk_store()
    deps = fake_deps()
    out = LR.run_pass(at("09:36", 7), store=st, deps=deps)
    assert out["ran"] and out["status"] == "ok" and out["errors"] == []
    assert SUMMARY_KEYS <= set(out)
    assert out["calls"] == {"snapshot": 1, "daily_fetch": 2, "minute_today": 2, "minute_prior": 2,
                            "index": len(LC.LUK_INDEX_SYMBOLS), "caps": 1}
    assert out["screens"]["daily"] == {"doc_hits": 0, "computed": 2, "fetched": 2, "deferred": 0, "untrusted": 2,
                                       "no_frame": 0}
    assert spies["index_store"] == [st], "9 the index words are kept in this pass's store (once per session)"
    assert spies["warm"][0]["priority"] == ["BBB", "AAA"]               # |change| desc; ETF and no-price out
    assert spies["warm"][0]["cap_new"] == LC.LUK_DAILY_MAX_NEW_PER_PASS
    assert spies["warm"][0]["budget_sec"] == LC.LUK_DAILY_WARM_BUDGET_SEC
    assert 0 < spies["frames_for"][0]["budget_sec"] <= LC.LUK_PASS_BUDGET_SEC
    assert out["shortlist"] == {"n": 2, "capped_n": 0, "symbols": ["AAA", "BBB"]}
    assert out["n_read"] == 2 and out["states"]["aplus"] == 2 and out["alerts"]["shadow"] == 2
    assert set(colls[GS.READS].docs) == {f"{DAY}|AAA", f"{DAY}|BBB"}
    assert set(colls[ST.SCREENS_KEY].docs) == {DAY}
    assert {d["state"] for d in colls[GS.ALERTS].docs.values()} == {"shadow"}
    assert len(spies["grade"]) == 1                                      # 14 the 🏁 step ran once (not dry)
    gk = spies["grade"][0][1]
    assert gk["max_loads"] == LC.LUK_GRADE_MAX_LOADS and gk["budget_sec"] == LC.LUK_GRADE_BUDGET_SEC
    assert deps.record_status.calls and deps.record_status.calls[0][0][2] is None   # 16 the /alerts row, no reason
    assert colls[GS.STATE].docs["lease"]["status"] == "done"            # released
    assert colls[GS.PASSES].docs["latest"]["calls"] == out["calls"]     # the pass doc carries the cost block


def test_C1_the_pass_writes_bars_through_and_the_next_pass_reads_it(monkeypatch):
    st, colls = mk_store()
    spies = fake_steps(monkeypatch, t1=at("09:35"), t5=at("09:35"))
    first = LR.run_pass(at("09:36", 7), store=st, deps=fake_deps())
    assert spies["read_all"] == [None, None]                             # the session's first pass: no clock yet
    doc = colls[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH]
    assert doc["session"] == DAY and doc["t1"] == at("09:35") and doc["t5"] == at("09:35")
    assert first["bars_through"] == {"t1_et": "09:35", "t5_et": "09:35"}
    spies = fake_steps(monkeypatch, t1=at("09:40"), t5=at("09:40"))
    LR.run_pass(at("09:41", 7), store=st, deps=fake_deps())
    assert spies["read_all"] == [at("09:35"), at("09:35")]               # the previous pass's 1-minute bars-through
    assert colls[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH]["t1"] == at("09:40")


def test_NEGATIVE_bars_through_never_moves_backwards_and_never_crosses_a_session(monkeypatch):
    st, colls = mk_store()
    colls[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH] = {"_id": LC.LUK_STATE_BARS_THROUGH, "session": DAY,
                                                        "t1": at("09:35"), "t5": at("09:35")}
    fake_steps(monkeypatch, t1=None, t5=None)                            # nothing read this pass
    out = LR.run_pass(at("09:41", 7), store=st, deps=fake_deps())
    assert colls[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH]["t1"] == at("09:35")
    assert out["bars_through"]["t1_et"] == "09:35"
    assert LR.prev_bars_through({"session": PRIOR, "t1": at("15:59", day=PRIOR)}, DAY) == (None, None)
    assert LR.prev_bars_through(None, DAY) == (None, None)


def test_prev_bars_through_normalises_a_mongo_naive_utc_stamp():
    naive_utc = datetime(2026, 11, 3, 14, 35)                            # 09:35 ET as Mongo hands it back
    t1, t5 = LR.prev_bars_through({"session": DAY, "t1": naive_utc, "t5": f"{DAY} 09:35"}, DAY)
    assert t1 == at("09:35") and t1.tzinfo is not None and t5 == at("09:35")


def test_the_carried_names_are_forming_or_triggered_reads_today_and_the_prior_session(monkeypatch):
    st, colls = mk_store()
    for day, sym, state in ((DAY, "KEEP1", "forming"), (PRIOR, "KEEP2", "triggered"), (DAY, "DROP1", "none"),
                            (PRIOR, "DROP2", "stopped"), ("2026-10-30", "DROP3", "forming")):
        colls[GS.READS].docs[f"{day}|{sym}"] = {"_id": f"{day}|{sym}", "date": day, "symbol": sym,
                                                "setups": {"pullback_reversal": {"state": state}}}
    spies = fake_steps(monkeypatch)
    LR.run_pass(at("09:36", 7), store=st, deps=fake_deps())
    assert spies["shortlist"] == [{"KEEP1", "KEEP2"}]


def test_symbols_narrow_the_names_read(monkeypatch):
    spies = fake_steps(monkeypatch)
    st, _colls = mk_store()
    out = LR.run_pass(at("09:36", 7), store=st, deps=fake_deps(), symbols=["zzz"])
    assert spies["frames_for"][0]["names"] == ["ZZZ"] and out["shortlist"]["symbols"] == ["ZZZ"]


def test_the_dry_pass_lands_nothing_and_records_only_luk_writes(monkeypatch):
    spies = fake_steps(monkeypatch, t1=at("09:35"), t5=at("09:35"), read=_aplus())
    real, colls = mk_store()
    st = ST.dry_store(real)
    deps = LR.dry_deps()
    assert deps.fetch is None                                            # a dry pass never force-fetches a daily bar
    assert deps.index_loader is LR._dry_index_loader                     # nor writes the house cache for QQQ / IWM
    base = fake_deps()
    for k in ("snapshot", "types", "caps", "cached", "load_day", "index_loader", "grade_load_day"):
        setattr(deps, k, getattr(base, k))
    out = LR.run_pass(at("09:36", 7), store=st, deps=deps, dry=True)
    assert out["dry"] is True and out["status"] == "ok" and out["errors"] == []
    assert all(c.writes == 0 and c.docs == {} for c in colls.values())  # NEGATIVE: zero writes land
    names = {w[0] for w in st.writes}
    assert {"luk_screens", "luk_reads", "luk_passes", "luk_state"} <= names
    assert all(n.startswith("luk_") for n in names)
    assert spies["warm"][0]["fetch"] is None and out["calls"]["daily_fetch"] == 0
    assert out["screens"]["daily"]["deferred"] == 2 and out["screens"]["daily"]["untrusted"] == 2
    assert out["alerts"]["dry"] == 2 and out["alerts"]["shadow"] == 0
    assert spies["grade"] == [] and out["ledger"] is None                # NEGATIVE: no grade step on a dry pass
    assert deps.status and deps.status[0]["candidates"] == 2              # the /alerts row went to the recorder


def test_NEGATIVE_a_held_lease_refuses_before_the_snapshot(monkeypatch):
    fake_steps(monkeypatch)
    st, colls = mk_store()
    colls[GS.STATE].docs["lease"] = {"_id": "lease", "status": "running", "held_by": "cron", "token": "x",
                                     "claimed_at": at("09:36"), "started_at": at("09:36"),
                                     "last_cron_started_at": at("09:36")}
    snap = Rec(({}, {"http": 200}))
    out = LR.run_pass(at("09:36", 30), store=st, deps=fake_deps(snapshot=snap))
    assert out["ran"] is False and out["reason"].startswith("lease held") and snap.calls == []
    assert out["calls"]["snapshot"] == 0


def test_the_lease_runs_on_luks_own_numbers():
    st, _colls = mk_store()
    assert st._lease_nums() == (LC.LUK_LEASE_SEC, LC.LUK_LEASE_MIN_GAP_SEC)


def test_NEGATIVE_outside_the_window_nothing_is_claimed(monkeypatch):
    fake_steps(monkeypatch)
    st, colls = mk_store()
    out = LR.run_pass(at("17:06"), store=st, deps=fake_deps())
    assert out["ran"] is False and out["reason"] == "outside the pass window"
    assert colls[GS.STATE].docs == {} and colls[GS.PASSES].docs == {}


def test_NEGATIVE_a_raising_snapshot_still_records_the_pass_and_releases(monkeypatch):
    fake_steps(monkeypatch)
    st, colls = mk_store()

    def boom():
        raise RuntimeError("massive down")
    deps = fake_deps(snapshot=boom)
    out = LR.run_pass(at("09:36", 7), store=st, deps=deps)
    assert out["status"] == "error" and "RuntimeError" in out["errors"]
    assert colls[GS.PASSES].docs["latest"]["status"] == "error"
    assert colls[GS.STATE].docs["lease"]["status"] == "done"
    assert deps.record_status.calls[0][0][2].startswith("pass error")


def test_NEGATIVE_a_raising_gate_or_grade_step_is_named_and_the_pass_ends(monkeypatch):
    fake_steps(monkeypatch, t1=at("09:35"), t5=at("09:35"), read=_aplus())

    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(AL, "run_pass", boom)
    monkeypatch.setattr(LG, "grade_step", boom)
    st, colls = mk_store()
    out = LR.run_pass(at("09:36", 7), store=st, deps=fake_deps())
    assert out["errors"] == ["alerts", "ledger"] and out["status"] == "ok"
    assert colls[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH]["t1"] == at("09:35")   # 15 still written


def test_the_dry_cli_prints_json_and_lands_nothing(monkeypatch, capsys):
    fake_steps(monkeypatch, t1=at("09:50"), t5=at("09:50"))
    real, colls = mk_store()
    deps = fake_deps()
    deps.fetch = None
    rc = LR.main(["--dry-run", "--json", "--now", f"{DAY}T09:52"], store=ST.dry_store(real), deps=deps)
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry"] is True and set(out["calls"]) == set(LR.CALL_KEYS)
    assert out["writes"] and all(n.startswith("luk_") for n in out["writes"])
    assert all(c.writes == 0 for c in colls.values())


# ── the real steps end to end (no step faked: the orchestration meets every sibling's real signature) ───────────────
def _minutes(day: str, upto: str = "15:59", base: float = 100.0):
    import pandas as pd
    idx = pd.date_range(f"{day} 09:30", f"{day} {upto}", freq="1min", tz=ET)
    n = len(idx)
    close = [base + 0.01 * i for i in range(n)]
    df = pd.DataFrame({"open": close, "high": [c + 0.05 for c in close], "low": [c - 0.05 for c in close],
                       "close": close, "volume": [10_000] * n, "session": ["rth"] * n},
                      index=idx.tz_convert("UTC").tz_localize(None))
    return df


def _daily(end: str, n: int = 220):
    import pandas as pd
    from datetime import timezone as _tz
    idx = pd.bdate_range(end=end, periods=n)
    close = [50.0 + 0.25 * i for i in range(n)]
    df = pd.DataFrame({"open": close, "high": [c * 1.03 for c in close], "low": [c * 0.99 for c in close],
                       "close": close, "volume": [2_000_000] * n}, index=idx)
    df.attrs["cached_at"] = datetime.fromisoformat(f"{end}T17:00").replace(tzinfo=ET).astimezone(_tz.utc).timestamp()
    return df


def _snap_row(px: float, now: datetime) -> dict:
    return {"open": px * 0.98, "high": px * 1.01, "low": px * 0.97, "close": px, "volume": 3_000_000, "vwap": px,
            "change_pct": 3.0, "last_trade_price": px, "last_trade_ts_ms": int(now.timestamp() * 1000),
            "prev_day_close": px / 1.03, "todays_change": px - px / 1.03}


def _never(*a, **k):
    raise AssertionError("daily.warm never calls deps.cached (REFIX 2026-11-01: the house cache is never trusted)")


def _e2e(now, loads: list) -> LR.Deps:
    rows = {"AAA": _snap_row(104.0, now), "BBB": _snap_row(104.0, now), "ETF1": _snap_row(50.0, now)}

    def load_day(sym, day, force=False, include_premarket=True, include_afterhours=False):
        loads.append((sym, str(day)))
        return _minutes(str(day), "10:40" if str(day) == DAY else "15:59")
    deps = LR.dry_deps()
    deps.snapshot = lambda: (dict(rows), {"http": 200, "wall_s": 0.5})
    deps.types = lambda: dict(TYPES)
    deps.caps = lambda tickers, px: {t: 2_000_000_000 for t in tickers}
    deps.cached = _never
    deps.fetch = lambda sym, session: _daily(PRIOR)                      # Luk's own post-close fetch (PRIOR = the
    deps.load_day = load_day                                             # previous market day of DAY)
    deps.index_loader = lambda sym: _daily(PRIOR)
    return deps


def test_the_dry_pass_runs_the_real_steps_end_to_end(monkeypatch):
    from catalysts.medical.reaction import prev_market_day
    assert prev_market_day(datetime.fromisoformat(DAY).date()).isoformat() == PRIOR
    now = at("10:41", 7)
    loads: list = []
    deps = _e2e(now, loads)
    real, colls = mk_store()
    st = ST.dry_store(real)
    out = LR.run_pass(now, store=st, deps=deps, dry=True)
    json.dumps(out, default=str)                                         # the --json print never raises
    assert out["status"] == "ok" and out["errors"] == [], out["errors"]
    assert out["screens"]["daily"]["computed"] == 2 and out["screens"]["screened_n"] == 2
    assert out["screens"]["daily"]["untrusted"] == 2 and out["screens"]["daily"]["doc_hits"] == 0
    assert out["shortlist"]["symbols"] == ["AAA", "BBB"]
    assert out["bars"]["loaded"] == 2 and out["n_read"] == 2
    assert out["calls"]["snapshot"] == 1 and out["calls"]["caps"] == 1 and out["calls"]["daily_fetch"] == 2
    assert out["calls"]["minute_today"] == 2
    assert out["calls"]["minute_prior"] == 2 * LC.LUK_HOURLY_SESSIONS
    assert out["calls"]["minute_today"] + out["calls"]["minute_prior"] == len(loads)
    assert out["calls"]["index"] == len(LC.LUK_INDEX_SYMBOLS)
    assert out["bars_through"]["t1_et"] == "10:40" and out["bars_through"]["t5_et"] == "10:40"
    assert set(out["states"]) == set(LR.STATE_KEYS) and sum(out["states"].values()) == 2 * len(LC.SETUPS)
    assert all(c.writes == 0 and c.docs == {} for c in colls.values())  # NEGATIVE: nothing lands
    assert {w[0] for w in st.writes} <= set(ST.PHYSICAL)


def test_NEGATIVE_the_dry_pass_without_the_own_fetch_screens_nothing():
    now = at("10:41", 7)
    deps = _e2e(now, [])
    deps.fetch = None                                                    # the real dry_deps: no daily fetch
    real, _colls = mk_store()
    out = LR.run_pass(now, store=ST.dry_store(real), deps=deps, dry=True)
    assert out["status"] == "ok" and out["calls"]["daily_fetch"] == 0
    assert out["screens"]["screened_n"] == 0 and out["screens"]["daily"]["deferred"] == 2
    assert out["screens"]["daily"]["computed"] == 0


# ── the type map: the stored 🚩 doc's REAL shape (REFIX 2026-11-01) ─────────────────────────────────────────────────
class _TypesStore:
    def __init__(self, doc=None, exc=None):
        self.doc, self.exc = doc, exc

    def types_map(self):
        if self.exc:
            raise self.exc
        return self.doc


SCANNER_DOC = {"as_of": DAY, "attempted_on": DAY, "complete": True, "calls": 3, "n": 4,
               "fetched_at": at("04:01"),
               "pairs": [["AAA", "CS"], ("BBB", "ADRC"), ["ETF1", "ETF", "junk"], "NOPX", ["ETF1", "ETF"]]}


def test_types_reads_the_scanner_doc_pairs(monkeypatch):
    monkeypatch.setattr(GS, "default", lambda: _TypesStore(dict(SCANNER_DOC)))
    assert LR._types() == {"AAA": "CS", "BBB": "ADRC", "ETF1": "ETF"}   # a 2-list, a 2-tuple; junk dropped


def test_NEGATIVE_types_ignores_the_old_wrong_types_key(monkeypatch):
    monkeypatch.setattr(GS, "default", lambda: _TypesStore({"types": {"AAA": "CS"}, "as_of": DAY}))
    assert LR._types() == {}


@pytest.mark.parametrize("store", [_TypesStore(None), _TypesStore(exc=RuntimeError("mongo down")),
                                   _TypesStore("junk"), _TypesStore({"pairs": "junk"})])
def test_NEGATIVE_types_none_or_raising_is_empty_never_raises(monkeypatch, store):
    monkeypatch.setattr(GS, "default", lambda: store)
    assert LR._types() == {}


def test_the_dry_pass_through_the_real_type_map_read(monkeypatch):
    monkeypatch.setattr(GS, "default", lambda: _TypesStore(dict(SCANNER_DOC)))
    now = at("10:41", 7)
    deps = _e2e(now, [])
    deps.types = LR._types                                               # the REAL read, the patched 🚩 store
    real, _colls = mk_store()
    out = LR.run_pass(now, store=ST.dry_store(real), deps=deps, dry=True)
    assert out["status"] == "ok" and out["errors"] == [], out["errors"]
    assert out["screens"]["screened_n"] == 2 and out["shortlist"]["symbols"] == ["AAA", "BBB"]   # ETF1 is no CS


def test_NEGATIVE_an_absent_type_map_is_an_empty_universe_not_a_raise(monkeypatch):
    monkeypatch.setattr(GS, "default", lambda: _TypesStore(None))
    now = at("10:41", 7)
    deps = _e2e(now, [])
    deps.types = LR._types
    real, _colls = mk_store()
    out = LR.run_pass(now, store=ST.dry_store(real), deps=deps, dry=True)
    assert out["errors"] == [] and out["screens"]["screened_n"] == 0
    assert out["screens"]["not_screened_n"] == 0 and out["n_read"] == 0 and out["calls"]["daily_fetch"] == 0


# ── the index words: once per session (REFIX 2026-11-01) ───────────────────────────────────────────────────────────
def test_the_index_words_are_loaded_once_per_session(monkeypatch):
    st, colls = mk_store()
    now = at("10:41", 7)
    deps = _e2e(now, [])
    deps.fetch = None
    first = LR.run_pass(now, store=st, deps=deps, dry=True)
    assert first["calls"]["index"] == len(LC.LUK_INDEX_SYMBOLS)
    assert colls[GS.STATE].docs[LC.LUK_STATE_INDEX]["session"] == DAY

    def boom(sym):
        raise AssertionError("never reached on the second pass of a session")
    deps.index_loader = boom
    second = LR.run_pass(at("10:46", 7), store=st, deps=deps, dry=True)
    assert second["calls"]["index"] == 0 and second["errors"] == []
    assert second["market_state"] == first["market_state"]


def test_NEGATIVE_the_default_index_loader_never_reads_the_house_cache(monkeypatch):
    import threading
    from sepa import prices as P
    seen = []
    me = threading.get_ident()      # Luk's index fetch runs INLINE on this thread (daily.py has no pool); a stray
                                    # Russell-wide load_prices pool leaked by an earlier test also loads QQQ/IWM, so
                                    # the discriminator is the THREAD, never the symbol

    def load_prices(sym, period="2y", force=False):
        seen.append((sym, period, force, threading.get_ident()))
        return _daily(PRIOR)

    def refuse(*a, **k):
        raise AssertionError("the index words never read the house cache")
    monkeypatch.setattr(P, "load_prices", load_prices)
    monkeypatch.setattr(P, "closed_daily_frame", refuse)
    monkeypatch.setattr(P, "cached_frame_meta", refuse)
    now = at("10:41", 7)
    deps = _e2e(now, [])
    deps.index_loader = None                                             # Deps' default → daily.default_index_loader
    real, _colls = mk_store()
    out = LR.run_pass(now, store=ST.dry_store(real), deps=deps, dry=True)
    assert out["errors"] == [] and out["calls"]["index"] == len(LC.LUK_INDEX_SYMBOLS)
    luk_calls = [c[:3] for c in seen if c[3] == me]
    assert luk_calls == [(s, "1y", True) for s in LC.LUK_INDEX_SYMBOLS]
    assert not [c for c in luk_calls if not c[2]]                        # NEGATIVE: never a cache-trusting load


def test_NEGATIVE_the_dry_index_loader_never_writes_the_house_cache(monkeypatch):
    from sepa import prices as P
    df = _daily(PRIOR)

    def refuse(*a, **k):
        raise AssertionError("a dry run writes no house cache")
    monkeypatch.setattr(P, "_fetch", lambda sym, period: df)
    for name in ("_mongo_put", "_parquet_put", "load_prices", "closed_daily_frame", "cached_frame_meta"):
        monkeypatch.setattr(P, name, refuse)
    got = LR._dry_index_loader("QQQ")
    assert got is not None and len(got) == len(df)
    monkeypatch.setattr(P, "_fetch", lambda sym, period: None)
    assert LR._dry_index_loader("QQQ") is None
