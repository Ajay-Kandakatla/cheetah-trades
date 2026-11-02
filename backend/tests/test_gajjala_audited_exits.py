"""🧪 Gajjala · Audited — the exit grades (T3 fixed 2R / 3R on the Intraday VCP, T5 the 21 EMA trail), the exits
collection and the nightly (BUILD SPEC 2026-11-01 §3.3, WP-C).

Ajay 2026-11-01: "Yes make the changes in audited please" and "But keep a track record too to see the winners and
loster".

Pins: T3 through `ledger.grade(..., r_mult=k)` (the ONE trade-math engine; the default byte-identical); T5's walk (a
close EXACTLY at the EMA is not under, warm-up None = no exit, the stop first inside a bucket, the fill bucket counts
only when it closes after the fill); the cost rule [C5] THROUGH THE REAL `daytrading.data.load_intraday` — a warm
cache → 0 provider fetches and 0 cache writes, a cold symbol-day → `deferred_cold` with 0 loads and 0 fetches, a row of
today → `deferred_today`; `upsert_exits` refusals; GG5 / GG1 never index EXITS; `ALL[-1] == REPLAY`; the nightly's
inner try keeps copy / grade when the exits step raises.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import audited_exits as AX
from chart_maps.gajjala import audited_rules as AUD
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import nightly as NG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from daytrading import data as DD
from tests.test_gajjala_store import FakeColl, fake_store

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
D = date(2026, 11, 4)                                            # a Wednesday inside the GGA record (from 11-01)
PREV = date(2026, 11, 3)                                         # its prior market day (the EMA warm-up)
NIGHT = datetime(2026, 11, 5, 21, 0, tzinfo=ET)                  # the NEXT night — D is no longer today
SAME_NIGHT = datetime(2026, 11, 4, 21, 0, tzinfo=ET)             # D's own night — D is today
GGA_OWN = tuple(n for n in ST.OWN if n not in V.GGA.borrows)
TRIG, STOP = 10.0, 9.5                                           # R = 0.5


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def et(h, m, day=D) -> datetime:
    return datetime(day.year, day.month, day.day, h, m, tzinfo=ET).astimezone(UTC)


def _row(at=None, setup="intraday_vcp", trigger=TRIG, stop=STOP, sym="AAA"):
    at = at or et(10, 41)
    plan = LG.plan_of(trigger, stop)[0]
    return {"id": LG.ledger_id(D.isoformat(), sym, setup, "aplus"), "date": D.isoformat(), "symbol": sym,
            "setup": setup, "kind": "aplus", "line": "shadow", "at_utc": at, "trigger": trigger, "stop": stop,
            "plan": plan}


def _bars(start: datetime, ohlc: list) -> list:
    """[(t_utc START, o, h, l, c)] one per minute from `start`."""
    return [(start + timedelta(minutes=i), *map(float, b)) for i, b in enumerate(ohlc)]


def _bounds(row):
    return LG.session_bounds(row["date"], row["at_utc"])


# ── T3: the ledger's engine at r_mult ───────────────────────────────────────────────────────────────────────────
def test_t3_2r_before_the_stop_is_a_win_at_plus_2r():
    row = _row()
    bars = _bars(et(10, 42), [(9.98, 10.05, 9.9, 10.0), (10.0, 10.4, 9.8, 10.3), (10.3, 11.0, 10.2, 10.9)])
    g = AX.t3_grade(row, bars, _bounds(row), 2.0)
    assert (g["outcome"], g["r"], g["r_mult"], g["reason"]) == ("win", 2.0, 2.0, "target")
    assert g["fill_px"] == 10.0 and g["target_px"] == 11.0 and g["version"] == AX.EXITS_VERSION
    g3 = AX.t3_grade(row, bars, _bounds(row), 3.0)
    assert (g3["outcome"], g3["r"], g3["target_px"]) == ("open", None, 11.5)   # NEGATIVE: 3R never printed


def test_t3_3r_column_wins_only_when_3r_prints():
    row = _row()
    bars = _bars(et(10, 42), [(9.98, 10.05, 9.9, 10.0), (10.0, 11.1, 9.8, 11.0), (11.0, 11.5, 10.9, 11.4)])
    g3 = AX.t3_grade(row, bars, _bounds(row), 3.0)
    assert (g3["outcome"], g3["r"]) == ("win", 3.0)


def test_NEGATIVE_t3_stop_touched_before_2r_is_a_loss():
    row = _row()
    bars = _bars(et(10, 42), [(9.98, 10.05, 9.9, 10.0), (10.0, 10.6, 9.5, 10.1), (10.1, 11.2, 10.0, 11.1)])
    g = AX.t3_grade(row, bars, _bounds(row), 2.0)
    assert (g["outcome"], g["r"], g["reason"]) == ("loss", -1.0, "stop")


def test_NEGATIVE_t3_2r_printed_on_the_fill_minute_is_not_a_win():
    row = _row()
    bars = _bars(et(10, 42), [(9.98, 11.3, 9.9, 10.5), (10.5, 10.9, 9.8, 10.6)])
    g = AX.t3_grade(row, bars, _bounds(row), 2.0)
    assert (g["outcome"], g["r"]) == ("open", None)


def test_grade_r_mult_none_is_byte_identical_and_r_mult_moves_only_the_target_fields():
    row = _row()
    bars = _bars(et(10, 42), [(9.98, 10.05, 9.9, 10.0), (10.0, 10.6, 9.8, 10.5), (10.5, 11.1, 10.4, 11.0)])
    b = _bounds(row)
    base = LG.grade(row, bars, b, "same")
    assert json.dumps(LG.grade(row, bars, b, "same", r_mult=None), sort_keys=True) == json.dumps(base, sort_keys=True)
    assert LG.grade(row, bars, b, "same", r_mult=GC.LEDGER_R_MULT) == base
    two = LG.grade(row, bars, b, "same", r_mult=2.0)
    diff = {k for k in base if base[k] != two[k]}
    assert "target_px" in diff and diff <= {"target_px", "outcome", "exit_t", "reason", "best_to_exit_pct"}
    assert set(two) == set(base)                                  # NEGATIVE: no new key in the 🏁's grade dict


# ── T5: the 21 EMA trail ────────────────────────────────────────────────────────────────────────────────────────
def frame(closes: list) -> SimpleNamespace:
    """A 5-minute frame stand-in: [(close ET "HH:MM", close, ema21)] — today's bars only."""
    return SimpleNamespace(t=[f"{D.isoformat()} {hm}" for hm, _c, _e in closes], c=[c for _h, c, _e in closes],
                           ema21=[e for _h, _c, e in closes], today=range(len(closes)))


FLAT = (10.0, 10.2, 9.9, 10.1)                                   # a quiet minute above the stop


def test_t5_a_close_under_the_ema_exits_at_that_close():
    row = _row()
    bars = _bars(et(10, 42), [(9.98, 10.05, 9.9, 10.0)] + [FLAT] * 15)
    f = frame([("10:45", 10.2, 10.0), ("10:50", 10.3, 10.1), ("10:55", 10.15, 10.2)])
    g = AX.t5_grade(row, bars, _bounds(row), f)
    assert (g["outcome"], g["reason"], g["exit_px"], g["ema_at_exit"]) == ("win", "ema21_close", 10.15, 10.2)
    assert g["r"] == pytest.approx(0.3) and g["exit_t"] == et(10, 55).isoformat() and g["bars5_n"] == 3
    assert set(AX.T5_KEYS) <= set(g) and g["version"] == AX.EXITS_VERSION


def test_t5_an_exit_under_the_fill_is_a_loss_with_its_r():
    row = _row()
    bars = _bars(et(10, 42), [(9.98, 10.05, 9.9, 10.0)] + [FLAT] * 5)
    g = AX.t5_grade(row, bars, _bounds(row), frame([("10:45", 9.8, 10.0)]))
    assert (g["outcome"], g["reason"]) == ("loss", "ema21_close") and g["r"] == pytest.approx(-0.4)


def test_NEGATIVE_t5_a_close_exactly_at_the_ema_is_not_under():
    row = _row()
    bars = _bars(et(10, 42), [(9.98, 10.05, 9.9, 10.0)] + [FLAT] * 10)
    g = AX.t5_grade(row, bars, _bounds(row), frame([("10:45", 10.2, 10.2), ("10:50", 10.3, 10.3)]))
    assert (g["outcome"], g["r"], g["reason"], g["exit_t"]) == ("open", None, "horizon_end", None)
    assert g["close_r"] == pytest.approx(0.6)                     # the last close so far, never a grade


def test_NEGATIVE_t5_warm_up_none_never_exits():
    row = _row()
    bars = _bars(et(10, 42), [(9.98, 10.05, 9.9, 10.0)] + [FLAT] * 10)
    g = AX.t5_grade(row, bars, _bounds(row), frame([("10:45", 9.6, None), ("10:50", 9.6, None)]))
    assert (g["outcome"], g["r"]) == ("open", None)


def test_t5_a_stop_touch_inside_the_bucket_wins_over_its_close_under_the_ema():
    row = _row()
    bucket = [FLAT, FLAT, (10.0, 10.1, 9.5, 9.6), FLAT, FLAT]     # 10:50–10:54: the 10:52 minute touches the stop
    bars = _bars(et(10, 42), [(9.98, 10.05, 9.9, 10.0)] + [FLAT] * 7 + bucket)
    g = AX.t5_grade(row, bars, _bounds(row), frame([("10:45", 10.2, 10.0), ("10:50", 10.2, 10.1),
                                                    ("10:55", 9.6, 10.1)]))
    assert (g["outcome"], g["r"], g["reason"], g["exit_px"]) == ("loss", -1.0, "stop", STOP)
    assert g["exit_t"] == et(10, 52).isoformat()


def test_t5_a_stop_on_the_fill_minute_is_stop_fill_minute():
    row = _row()
    bars = _bars(et(10, 42), [(9.98, 10.05, 9.4, 9.6), FLAT])
    g = AX.t5_grade(row, bars, _bounds(row), frame([("10:45", 10.2, 10.0)]))
    assert (g["outcome"], g["r"], g["reason"]) == ("loss", -1.0, "stop_fill_minute")


def test_t5_a_fill_at_10_32_exits_on_the_10_35_close():
    row = _row(at=et(10, 31))
    bars = _bars(et(10, 32), [(9.98, 10.05, 9.9, 10.0), FLAT, FLAT, FLAT])
    g = AX.t5_grade(row, bars, _bounds(row), frame([("10:30", 9.0, 10.0), ("10:35", 9.9, 10.0)]))
    assert g["fill_t"] == et(10, 32).isoformat()
    assert (g["reason"], g["exit_t"], g["bars5_n"]) == ("ema21_close", et(10, 35).isoformat(), 1)


def test_NEGATIVE_t5_the_bucket_closing_at_the_fill_minute_is_before_the_fill():
    row = _row(at=et(10, 34))
    bars = _bars(et(10, 35), [(9.98, 10.05, 9.9, 10.0), FLAT, FLAT])
    g = AX.t5_grade(row, bars, _bounds(row), frame([("10:35", 9.0, 10.0)]))   # closed AT 10:35 — the fill's start
    assert (g["outcome"], g["bars5_n"]) == ("open", 0)


def test_t5_not_filled_serves_the_entry_word_and_no_frame_its_reason():
    row = _row()
    g = AX.t5_grade(row, _bars(et(10, 42), [(9.8, 9.9, 9.7, 9.8)]), _bounds(row), frame([("10:45", 9.0, 10.0)]))
    assert (g["entry"], g["outcome"], g["r"]) == ("no_entry", None, None)
    filled = _bars(et(10, 42), [(9.98, 10.05, 9.9, 10.0)])
    g = AX.t5_grade(row, filled, _bounds(row), None)
    assert (g["entry"], g["reason"], g["r"]) == (None, AX.NO_FRAME, None)
    g = AX.t5_grade(_row(stop=TRIG), filled, _bounds(row), None)
    assert g["entry"] == "no_risk"                                # NEGATIVE: no plan → never a walk


# ── the store ───────────────────────────────────────────────────────────────────────────────────────────────────
def gga_store(alerts=(), exits=(), ledger=()):
    shared = fake_store()
    colls = {n: FakeColl() for n in GGA_OWN}
    colls[ST.ALERTS] = FakeColl(list(alerts))
    colls[ST.EXITS] = FakeColl(list(exits))
    colls[ST.LEDGER] = FakeColl(list(ledger))
    return ST.GajjalaStore(colls=colls, variant=V.GGA, shared=shared), shared


def test_exits_collection_names_and_order():
    assert ST.EXITS == "gajjala_exits" and ST.EXITS in ST.ALL and ST.EXITS in ST.OWN
    assert ST.ALL[-1] == ST.REPLAY and ST.EXITS not in ST.TTL_DAYS
    assert ST.EXITS_KEYS == frozenset({"date", "symbol", "setup", "kind", "alert", "graded_at", "version"})
    assert ST.GajjalaStore(variant=V.GGA, shared=fake_store()).physical(ST.EXITS) == "gajjala_audited_exits"
    assert ST.GajjalaStore().physical(ST.EXITS) == "gajjala_exits"
    assert not {"same", "next", "line"} & ST.EXITS_KEYS               # NEGATIVE: never the 🏁 ledger schema


class Counting(FakeColl):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def create_index(self, spec, **kw):
        self.calls += 1
        super().create_index(spec, **kw)


def test_NEGATIVE_gg5_and_gg1_ensure_indexes_never_touch_exits_and_gga_indexes_it_without_ttl():
    c5 = Counting()
    fake_store(**{ST.EXITS: c5}).ensure_indexes()
    assert c5.calls == 0                                          # GG5's bare run walks ALL
    c1 = Counting()
    g1_colls = {n: FakeColl() for n in ST.OWN}
    g1_colls[ST.EXITS] = c1
    ST.GajjalaStore(colls=g1_colls, variant=V.GG1, shared=fake_store()).ensure_indexes()
    assert c1.calls == 0                                          # GG1's run walks OWN
    gga, shared = gga_store()
    gga.ensure_indexes()
    specs = gga.coll(ST.EXITS).indexes
    assert [sp for sp, _ in specs] == [(("date", 1), ("symbol", 1)), (("symbol", 1), ("date", -1))]
    assert all("expireAfterSeconds" not in kw for _sp, kw in specs)   # kept, no TTL
    assert all(shared.coll(n).indexes == [] for n in ST.ALL)


def test_upsert_exits_writes_on_gga_and_refuses_everything_else():
    gga, shared = gga_store()
    cols = AUD.EXIT_COLS
    body = {"date": D.isoformat(), "symbol": "AAA", "setup": "intraday_vcp", "kind": "aplus", "alert": {},
            "graded_at": "x", "version": AX.EXITS_VERSION, cols[-1]: {"outcome": "open"}}
    assert gga.upsert_exits("id1", body, cols=cols) is True
    assert gga.coll(ST.EXITS).docs["id1"][cols[-1]] == {"outcome": "open"}
    assert gga.exits_docs([D])[0]["_id"] == "id1" and gga.exits_docs([PREV]) == []
    assert gga.upsert_exits("id2", dict(body, same={}), cols=cols) is False            # NEGATIVE: a 🏁 key
    assert gga.upsert_exits("id2", dict(body, junk=1), cols=cols) is False             # NEGATIVE: outside the keys
    assert gga.upsert_exits("id2", {cols[0]: {}}, cols=()) is False                    # NEGATIVE: col not named
    assert gga.upsert_exits("", body, cols=cols) is False                              # NEGATIVE: empty id
    assert gga.upsert_exits(None, body, cols=cols) is False
    assert gga.upsert_exits("id2", {}, cols=cols) is False
    assert set(gga.coll(ST.EXITS).docs) == {"id1"}
    gg5 = fake_store()
    assert gg5.upsert_exits("id1", body, cols=cols) is False                           # NEGATIVE: the 🚩 store
    g1 = ST.GajjalaStore(colls={n: FakeColl() for n in ST.OWN}, variant=V.GG1, shared=fake_store())
    assert g1.upsert_exits("id1", body, cols=cols) is False                            # NEGATIVE: the 1-minute store
    assert gg5.coll(ST.EXITS).writes == 0 and g1.coll(ST.EXITS).writes == 0
    assert all(shared.coll(n).writes == 0 for n in ST.ALL)
    assert ST.GajjalaStore(colls={n: None for n in GGA_OWN}, variant=V.GGA,
                           shared=fake_store()).exits_docs([D]) is None                  # a read fault, never []


# ── grade_exits ─────────────────────────────────────────────────────────────────────────────────────────────────
AT = et(10, 41).isoformat()


def _claim(sym="AAA", setup="intraday_vcp", day=D, trigger=TRIG, stop=STOP, at=None):
    return {"_id": f"SHADOW:GGA:{day.isoformat()}|{sym}|{setup}", "date": day.isoformat(), "symbol": sym,
            "setup": setup, "state": "shadow", "at": at or AT, "trigger": trigger, "stop": stop, "price": trigger}


def _lid(sym="AAA", setup="intraday_vcp", day=D):
    return LG.ledger_id(day.isoformat(), sym, setup, "aplus")


def day_df(day: date, path) -> pd.DataFrame:
    """A load_intraday-shaped frame (naive-UTC minute STARTS) 09:30–15:59 ET; `path(i)` = (o, h, l, c)."""
    start = datetime(day.year, day.month, day.day, 9, 30, tzinfo=ET).astimezone(UTC).replace(tzinfo=None)
    idx = pd.DatetimeIndex([start + timedelta(minutes=i) for i in range(390)], name="ts_utc")
    rows = [path(i) for i in range(390)]
    return pd.DataFrame({"open": [r[0] for r in rows], "high": [r[1] for r in rows], "low": [r[2] for r in rows],
                         "close": [r[3] for r in rows], "volume": [1000.0] * 390, "session": ["rth"] * 390},
                        index=idx)


def prev_path(i):
    p = 8.0 + i * 0.004                                           # a slow climb: the EMA is warm by today's open
    return p, p + 0.02, p - 0.02, p + 0.01


def same_path(i):
    if i < 72:                                                    # 09:30–10:41 under the trigger
        return 9.9, 9.95, 9.85, 9.9
    if i == 72:                                                   # 10:42 the fill minute
        return 9.98, 10.05, 9.9, 10.0
    p = 10.0 + (i - 72) * 0.02                                    # then up and away: 2R by 11:32
    return p, p + 0.02, p - 0.01, p + 0.01


WARM = {(s, d): f(d, p) for s in ("AAA", "BBB") for d, p, f in ((PREV, prev_path, day_df), (D, same_path, day_df))}


class Loads:
    def __init__(self, table=None, fail=False):
        self.table = WARM if table is None else table
        self.calls = []
        self.fail = fail

    def __call__(self, sym, day):
        self.calls.append((sym, day))
        if self.fail:
            return None, True
        return self.table.get((sym, day)), False


def warm_all(sym, day):
    return True


def test_a_row_of_today_is_deferred_today_and_loads_nothing():
    gga, _ = gga_store(alerts=[_claim()])
    loads, probes = Loads(), []
    out = AX.grade_exits(gga, SAME_NIGHT, load_df=loads, warm=lambda s, d: probes.append((s, d)) or True)
    assert (out["rows"], out["deferred_today"], out["loads"], out["written"]) == (1, 1, 0, 0)
    assert loads.calls == [] and probes == [] and gga.coll(ST.EXITS).docs == {}


def test_a_row_before_its_close_is_not_due():
    gga, _ = gga_store(alerts=[_claim()])
    out = AX.grade_exits(gga, datetime(2026, 11, 4, 15, 0, tzinfo=ET), load_df=Loads(), warm=warm_all)
    assert (out["not_due"], out["loads"], out["written"]) == (1, 0, 0)


@pytest.fixture
def real_loader(monkeypatch):
    """The REAL load_intraday: the cache (`_mongo_get_day`) answers from `cache`, `_fetch_massive_minute` and
    `_mongo_put_day` are counted, `_today_et` pinned (the loader's own "today")."""
    st = SimpleNamespace(cache=dict(WARM), fetch=[], put=[], today=NIGHT.astimezone(ET).date())

    def get_day(symbol, day):
        df = st.cache.get((symbol.upper(), day))
        return None if df is None else df.copy()
    monkeypatch.setattr(DD, "_mongo_get_day", get_day)
    monkeypatch.setattr(DD, "_fetch_massive_minute", lambda s, a, b: st.fetch.append((s, a)) or WARM.get((s, a)))
    monkeypatch.setattr(DD, "_mongo_put_day", lambda s, d, df: st.put.append((s, d)))
    monkeypatch.setattr(DD, "_today_et", lambda: st.today)
    return st


def test_C5_warm_cache_through_the_real_load_intraday_costs_zero_fetches(real_loader):
    gga, shared = gga_store(alerts=[_claim()])
    out = AX.grade_exits(gga, NIGHT)                              # NO load_df / warm injection
    assert (out["rows"], out["graded"], out["written"], out["loads"]) == (1, 1, 1, 2)
    assert real_loader.fetch == [] and real_loader.put == []      # cache hits only — never a provider call
    doc = gga.coll(ST.EXITS).docs[_lid()]
    assert set(doc) - {"_id"} <= ST.EXITS_KEYS | set(AUD.EXIT_COLS)
    assert set(AUD.EXIT_COLS) <= set(doc) and doc["version"] == AX.EXITS_VERSION
    t3a, t3b, t5 = (doc[c] for c in AUD.EXIT_COLS)
    assert (t3a["outcome"], t3a["r"]) == ("win", AUD.T3_R_MULTS[0])
    assert t5["entry"] == "filled" and t5["fill_px"] == TRIG
    assert gga.coll(ST.LEDGER).writes == 0 and all(shared.coll(n).writes == 0 for n in ST.ALL)


def test_C5_NEGATIVE_a_cold_prior_day_is_deferred_cold_never_fetched_and_still_due(real_loader):
    del real_loader.cache[("AAA", PREV)]
    gga, _ = gga_store(alerts=[_claim()])
    out = AX.grade_exits(gga, NIGHT)
    assert (out["deferred_cold"], out["loads"], out["written"], out["graded"]) == (1, 0, 0, 0)
    assert real_loader.fetch == [] and real_loader.put == [] and gga.coll(ST.EXITS).docs == {}
    real_loader.cache[("AAA", PREV)] = WARM[("AAA", PREV)]        # the next night the day is warm → graded
    out = AX.grade_exits(gga, NIGHT)
    assert (out["deferred_cold"], out["written"]) == (0, 1) and real_loader.fetch == []


def test_C5_NEGATIVE_a_cold_session_day_is_deferred_cold(real_loader):
    del real_loader.cache[("AAA", D)]
    gga, _ = gga_store(alerts=[_claim()])
    out = AX.grade_exits(gga, NIGHT)
    assert (out["deferred_cold"], out["loads"]) == (1, 0) and real_loader.fetch == []


def test_C5_NEGATIVE_the_loaders_today_is_deferred_today_with_zero_fetches(real_loader):
    real_loader.today = D
    gga, _ = gga_store(alerts=[_claim()])
    out = AX.grade_exits(gga, SAME_NIGHT)
    assert (out["deferred_today"], out["loads"], out["written"]) == (1, 0, 0) and real_loader.fetch == []


def test_a_warm_but_failing_loader_is_load_failed_and_retried():
    gga, _ = gga_store(alerts=[_claim()])
    out = AX.grade_exits(gga, NIGHT, load_df=Loads(fail=True), warm=warm_all)
    assert (out["load_failed"], out["written"]) == (1, 0) and gga.coll(ST.EXITS).docs == {}
    out = AX.grade_exits(gga, NIGHT, load_df=Loads(), warm=warm_all)
    assert out["written"] == 1


def test_a_loader_that_raises_is_load_failed_never_raised():
    def boom(sym, day):
        raise RuntimeError("down")
    gga, _ = gga_store(alerts=[_claim()])
    out = AX.grade_exits(gga, NIGHT, load_df=boom, warm=warm_all)
    assert (out["load_failed"], out["faulted"], out["written"]) == (1, 0, 0)


def test_the_load_cap_defers_the_rest():
    gga, _ = gga_store(alerts=[_claim("AAA"), _claim("BBB")])
    loads = Loads()
    out = AX.grade_exits(gga, NIGHT, load_df=loads, warm=warm_all, max_loads=2)
    assert (out["loads"], out["written"], out["deferred_cap"]) == (2, 1, 1) and len(loads.calls) == 2


def test_a_session_with_no_minute_is_no_bars():
    gga, _ = gga_store(alerts=[_claim()])
    out = AX.grade_exits(gga, NIGHT, load_df=Loads(table={("AAA", PREV): WARM[("AAA", PREV)]}), warm=warm_all)
    assert (out["no_bars"], out["written"]) == (1, 0)


def test_t3_columns_only_on_the_vcp_and_t5_on_every_setup():
    gga, _ = gga_store(alerts=[_claim("AAA", "intraday_vcp"), _claim("BBB", "bull_flag")])
    out = AX.grade_exits(gga, NIGHT, load_df=Loads(), warm=warm_all)
    assert out["written"] == 2
    docs = gga.coll(ST.EXITS).docs
    t5 = AUD.EXIT_COLS[-1]
    assert set(AUD.EXIT_COLS) <= set(docs[_lid("AAA")])
    assert t5 in docs[_lid("BBB", "bull_flag")]
    assert not set(AUD.EXIT_COLS[:-1]) & set(docs[_lid("BBB", "bull_flag")])          # NEGATIVE: no T3 on a flag


def test_stored_columns_at_this_version_are_skipped_and_an_old_version_regrades():
    gga, _ = gga_store(alerts=[_claim()])
    AX.grade_exits(gga, NIGHT, load_df=Loads(), warm=warm_all)
    loads = Loads()
    out = AX.grade_exits(gga, NIGHT, load_df=loads, warm=warm_all)
    assert (out["loads"], out["written"], out["graded"]) == (0, 0, 0) and loads.calls == []
    doc = gga.coll(ST.EXITS).docs[_lid()]
    doc[AUD.EXIT_COLS[-1]]["version"] = AX.EXITS_VERSION - 1
    out = AX.grade_exits(gga, NIGHT, load_df=loads, warm=warm_all)
    assert out["written"] == 1 and loads.calls


def test_a_row_without_a_plan_gets_its_entry_word_without_a_load():
    gga, _ = gga_store(alerts=[_claim(stop=TRIG)])                # trigger == stop → no_risk
    loads = Loads()
    out = AX.grade_exits(gga, SAME_NIGHT, load_df=loads, warm=warm_all)
    assert (out["written"], out["loads"]) == (1, 0) and loads.calls == []
    doc = gga.coll(ST.EXITS).docs[_lid()]
    assert {doc[c]["entry"] for c in AUD.EXIT_COLS} == {"no_risk"}


def test_a_dry_run_writes_nothing():
    gga, _ = gga_store(alerts=[_claim()])
    out = AX.grade_exits(gga, NIGHT, load_df=Loads(), warm=warm_all, dry=True)
    assert out["dry"] is True and out["graded"] == 1 and out["written"] == 0
    assert gga.coll(ST.EXITS).writes == 0


def test_a_read_fault_on_the_exits_or_the_alerts_grades_nothing():
    gga, _ = gga_store(alerts=[_claim()])
    gga._injected[ST.EXITS] = FakeColl(fail=True)
    out = AX.grade_exits(gga, NIGHT, load_df=Loads(), warm=warm_all)
    assert out["read_fault"] is True and out["loads"] == 0
    gga2, _ = gga_store()
    gga2._injected[ST.ALERTS] = FakeColl(fail=True)
    assert AX.grade_exits(gga2, NIGHT, load_df=Loads(), warm=warm_all)["read_fault"] is True


def test_the_exits_step_never_writes_the_ledger():
    gga, shared = gga_store(alerts=[_claim()])
    spy = []
    gga.upsert_ledger = lambda *a, **k: spy.append(a) or True
    AX.grade_exits(gga, NIGHT, load_df=Loads(), warm=warm_all)
    assert spy == [] and gga.coll(ST.LEDGER).writes == 0 and shared.coll(ST.LEDGER).writes == 0


def test_t5_reads_the_gg5_frame_with_the_prior_day_warm_up(monkeypatch):
    seen = []
    real = AX.t5_grade
    monkeypatch.setattr(AX, "t5_grade", lambda row, bars, b, f5: seen.append(f5) or real(row, bars, b, f5))
    gga, _ = gga_store(alerts=[_claim()])
    AX.grade_exits(gga, NIGHT, load_df=Loads(), warm=warm_all)
    assert len(seen) == 1
    b = LG.session_bounds(D, et(10, 41))
    want = B.build_frames("AAA", D, b["same_end"] + LG.SETTLE, WARM[("AAA", PREV)], WARM[("AAA", D)],
                          variant=V.GG5).frame("5m")
    assert seen[0].ema21 == want.ema21 and seen[0].t == want.t and seen[0].frame == "5m"
    today_only = B.build_frames("AAA", D, b["same_end"] + LG.SETTLE, None, WARM[("AAA", D)],
                                variant=V.GG5).frame("5m")
    assert today_only.ema21 != seen[0].ema21                      # NEGATIVE: an EMA over today only differs


def test_cols_are_built_from_the_registry():
    t3, t5 = AX._cols()
    assert tuple(t3) + (t5,) == tuple(AUD.EXIT_COLS)
    assert tuple(t3.values()) == tuple(AUD.T3_R_MULTS)


# ── the nightly ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_grade_audited_serves_copy_grade_and_exits():
    gga, _ = gga_store(alerts=[_claim()])
    seen = []
    res = NG.grade_audited(NIGHT, store=gga, load_day=lambda s, d: ([], False), split_lookup=lambda *a: False,
                           exits_load=Loads(), exits_warm=lambda s, d: seen.append((s, d)) or True)
    assert set(res) == {"copy", "grade", "exits"}
    assert res["exits"]["written"] == 1 and seen                  # the injected loader and probe were used


def test_an_exits_raise_never_hides_copy_or_grade(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("exits down")
    monkeypatch.setattr(AX, "grade_exits", boom)
    gga, _ = gga_store(alerts=[_claim()])
    res = NG.grade_audited(NIGHT, store=gga, load_day=lambda s, d: ([], False), split_lookup=lambda *a: False)
    assert res["exits"] == {"error": "exits: RuntimeError"}
    assert "rows" in res["copy"] and "rows" in res["grade"] and "error" not in res


def test_NEGATIVE_a_copy_raise_keeps_the_outer_shape(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(NG, "copy_original_grades", boom)
    gga, _ = gga_store()
    assert NG.grade_audited(NIGHT, store=gga) == {"error": "grade: RuntimeError"}
