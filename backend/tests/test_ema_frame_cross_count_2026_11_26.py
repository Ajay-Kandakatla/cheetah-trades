"""ema-verify (2026-11-26, spec runcharts rev 2 §3.10 / §4.4) — the read-only 1 / 5 / 15-minute down-cross count.

Hermetic: every reader is injected (`get_day` / `runners_of` / `universe_of`); the minute loader, the provider and the
cache are made to raise so a test that reached any of them fails loudly.
"""
from __future__ import annotations

import json
import math
import random
import re
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import daytrading.data as DD
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ema_cross as EC
from chart_maps.gajjala_watch import constants as WC
from orderflow.signals import ema
from scripts import ema_frame_cross_count_2026_11_26 as M

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "ema_frame_cross_count_2026_11_26.py"
SHIPPED = BACKEND / "scripts" / "ema_frame_cross_count_2026_11_26.json"
DOC = BACKEND.parent / "docs" / "gajjala" / "ema_follow_check_2026_11_26.md"
D25, D24, D23, D20 = date(2026, 11, 25), date(2026, 11, 24), date(2026, 11, 23), date(2026, 11, 20)


# ── fixtures ──────────────────────────────────────────────────────────────────────────────────────────────────────
def minutes(day_iso: str, closes, start_et: str = "09:30") -> pd.DataFrame:
    """1-minute bars as the cache returns them: naive-UTC index `ts_utc`, OHLCV + the loader's session tag."""
    start = pd.Timestamp(f"{day_iso} {start_et}", tz=ET).tz_convert("UTC").tz_localize(None)
    idx = pd.date_range(start, periods=len(closes), freq="1min", name="ts_utc")
    c = pd.Series([float(x) for x in closes], index=idx)
    df = pd.DataFrame({"open": c, "high": c + 0.01, "low": c - 0.01, "close": c, "volume": 100.0}, index=idx)
    df["session"] = [DD._classify_session(t) for t in idx]
    return df


def zigzag(n: int, period: int = 40, base: float = 10.0, amp: float = 1.0) -> list:
    return [base + amp * math.sin(2 * math.pi * i / period) for i in range(n)]


def sawtooth(n_buckets: int, period: int = 40) -> list:
    """Four minutes of each 5-minute bucket swing on a sine; the fifth (the bucket's close) sits on a rising line —
    the 1-minute closes swing, the 5-minute closes only rise (the mechanism, built on purpose)."""
    return [10.0 + 0.02 * i + (0.0 if i % 5 == 4 else math.sin(2 * math.pi * i / period)) for i in range(5 * n_buckets)]


def no_real_readers(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("ema-verify reached a real reader")
    for name in ("load_intraday", "load_intraday_range", "_fetch_massive_minute", "_mongo_get_day", "_mongo_put_day"):
        monkeypatch.setattr(DD, name, refuse)


def store_reader(cache: dict, calls: list):
    def get_day(sym, d):
        calls.append((sym, d.isoformat()))
        return cache.get((sym, d.isoformat()))
    return get_day


# ── 1. the formula pin ────────────────────────────────────────────────────────────────────────────────────────────
def tos_recursion(prices, n):
    """thinkorswim MovAvgExponential: EMA1 = price1; EMAn = α·pricen + (1 − α)·EMAn−1, α = 2 / (n + 1)."""
    a = 2.0 / (n + 1)
    out = [float(prices[0])]
    for p in prices[1:]:
        out.append(a * float(p) + (1 - a) * out[-1])
    return out


def sma_seeded(prices, n):
    """The FE lib/ema.ts seed: None until bar n − 1, which holds the SMA of the first n, then the same recursion."""
    a = 2.0 / (n + 1)
    out = [None] * (n - 1) + [sum(prices[:n]) / n]
    for p in prices[n:]:
        out.append(a * p + (1 - a) * out[-1])
    return out


def test_house_ema_is_the_thinkorswim_recursion():
    rng = random.Random(7)
    prices = [10 + rng.uniform(-1, 1) for _ in range(300)]
    for n in (GC.EMA_FAST, GC.EMA_SLOW):
        assert (GC.EMA_FAST, GC.EMA_SLOW) == (9, 21)
        house = ema(pd.Series(prices), n).tolist()
        tos = tos_recursion(prices, n)
        assert max(abs(x - y) for x, y in zip(house, tos)) < 1e-12


def test_negative_sma_seed_differs_in_its_first_bars():
    rng = random.Random(8)
    prices = [10 + rng.uniform(-1, 1) for _ in range(120)]
    for n in (GC.EMA_FAST, GC.EMA_SLOW):
        house = ema(pd.Series(prices), n).tolist()
        sma = sma_seeded(prices, n)
        assert all(v is None for v in sma[: n - 1])
        assert abs(house[n - 1] - sma[n - 1]) > 1e-6


# ── 2. counts = THE cross engine, today's bars only ─────────────────────────────────────────────────────────────
def test_counts_equal_the_cross_engine_on_a_zigzag():
    F = M.frame_for(None, minutes("2026-11-24", zigzag(300)), "2026-11-24", "1m")
    xs = EC.crosses_from_emas(F.ema9, F.ema21, F.t, F.c, F.today)
    c = M.counts(F)
    assert c["down"] == sum(1 for x in xs if x["dir"] == EC.DOWN) > 0
    assert c["up"] == sum(1 for x in xs if x["dir"] == EC.UP) > 0
    assert c["bars"] == len(F.today) == 300


def test_negative_flat_series_has_no_cross():
    F = M.frame_for(None, minutes("2026-11-24", [10.0] * 200), "2026-11-24", "1m")
    assert M.counts(F) == {"bars": 200, "down": 0, "up": 0}


def test_negative_warm_up_bars_are_never_a_cross():
    F = M.frame_for(None, minutes("2026-11-24", zigzag(200, period=6)), "2026-11-24", "1m")
    xs = EC.frame_crosses(F)
    assert xs and min(x["i"] for x in xs) >= GC.EMA_SLOW
    assert all(F.ema21[i] is None for i in range(GC.EMA_SLOW - 1))


def test_negative_a_cross_on_the_prior_day_is_not_counted():
    prev = minutes("2026-11-23", zigzag(300))
    day = minutes("2026-11-24", [20.0 + 0.01 * i for i in range(120)])
    F = M.frame_for(prev, day, "2026-11-24", "1m")
    every = EC.crosses_from_emas(F.ema9, F.ema21, F.t, F.c, None)
    assert any(x["dir"] == EC.DOWN for x in every)
    assert M.counts(F)["down"] == 0
    assert M.counts(F)["bars"] == 120


def test_counts_of_none_is_zero():
    assert M.counts(None) == {"bars": 0, "down": 0, "up": 0}


# ── 3. frame_for: the prior day only warms ──────────────────────────────────────────────────────────────────────
def test_prior_day_warms_the_first_bar():
    prev = minutes("2026-11-23", zigzag(960, base=10), start_et="04:00")
    day = minutes("2026-11-24", zigzag(120))
    F = M.frame_for(prev, day, "2026-11-24", "5m")
    assert F.today.start > 0
    assert F.ema21[F.today.start] is not None
    assert len(F.today) == 24


def test_negative_without_the_prior_day_the_first_bars_are_warm_up():
    F = M.frame_for(None, minutes("2026-11-24", zigzag(300)), "2026-11-24", "5m")
    assert F.today.start == 0
    assert all(v is None for v in F.ema21[: GC.EMA_SLOW - 1])
    assert F.ema21[GC.EMA_SLOW - 1] is not None


def test_negative_a_day_with_no_bar_gives_none():
    assert M.frame_for(None, None, "2026-11-24", "5m") is None
    assert M.frame_for(None, minutes("2026-11-24", [])[:0], "2026-11-24", "5m") is None
    closed_only_bars = minutes("2026-11-24", [10.0] * 30, start_et="02:00")
    assert set(closed_only_bars["session"]) == {"closed"}
    assert M.frame_for(None, closed_only_bars, "2026-11-24", "5m") is None
    prev = minutes("2026-11-23", zigzag(300))
    assert M.frame_for(prev, None, "2026-11-24", "5m") is None


def test_name_day_warm_flag_and_not_cached():
    cache = {("AAA", "2026-11-24"): minutes("2026-11-24", zigzag(300)),
             ("AAA", "2026-11-23"): minutes("2026-11-23", zigzag(300)),
             ("BBB", "2026-11-24"): minutes("2026-11-24", zigzag(300))}
    calls = []
    g = store_reader(cache, calls)
    a = M.name_day("AAA", D24, get_day=g)
    b = M.name_day("BBB", D24, get_day=g)
    assert a["warm"] is True and b["warm"] is False
    assert a["day"] == "2026-11-24" and a["symbol"] == "AAA"
    assert M.name_day("CCC", D24, get_day=g) is None
    assert ("AAA", "2026-11-23") in calls


# ── 4. frames by name; the mechanism on a saw-tooth ─────────────────────────────────────────────────────────────
def test_frames_come_from_the_watch_constant(monkeypatch):
    cache = {("AAA", "2026-11-24"): minutes("2026-11-24", zigzag(300))}
    g = store_reader(cache, [])
    assert list(M.name_day("AAA", D24, get_day=g)["frames"]) == [tf for tf, _ in WC.FRAMES]
    monkeypatch.setattr(WC, "FRAMES", (("5m", "5min"), ("15m", "15min")))
    assert list(M.name_day("AAA", D24, get_day=g)["frames"]) == ["5m", "15m"]


def test_tf_names_are_read_by_name(monkeypatch):
    assert M._tf_names() == (WC.FRAMES[0][0], GC.RUN_BASE_FRAME, WC.FRAMES[-1][0])
    monkeypatch.setattr(GC, "RUN_BASE_FRAME", "15m")
    assert M._tf_names()[1] == "15m"


def test_sawtooth_crosses_on_1m_not_on_5m():
    cache = {("AAA", "2026-11-24"): minutes("2026-11-24", sawtooth(60))}
    r = M.name_day("AAA", D24, get_day=store_reader(cache, []))
    assert r["frames"]["1m"]["down"] > 0
    assert r["frames"]["5m"]["down"] == 0
    assert r["frames"]["5m"]["bars"] == 60


# ── 5. population ───────────────────────────────────────────────────────────────────────────────────────────────
def _world():
    runners = {D25: ["RUN1", "RUN2", "NOPE"], D24: ["RUN1"], D23: []}
    others = [f"O{i:02d}" for i in range(30)]
    universe = {D25: runners[D25] + others, D24: runners[D24] + others, D23: others}
    cache = {}
    for d in (D25, D24, D23, D20):
        for s in ["RUN1", "RUN2"] + others:
            cache[(s, d.isoformat())] = minutes(d.isoformat(), zigzag(120))
    return runners, universe, cache


def test_population_placebo_never_holds_a_runner(monkeypatch):
    no_real_readers(monkeypatch)
    runners, universe, cache = _world()
    calls = []
    pop = M.population(D25, 3, runners_of=lambda d: runners[d], universe_of=lambda d: universe[d],
                       get_day=store_reader(cache, calls))
    for r in pop["rows"]:
        if r["group"] == "other":
            assert r["symbol"] not in runners[date.fromisoformat(r["day"])]
    by_day = {x["day"]: x for x in pop["days"]}
    assert by_day["2026-11-25"]["runners_cached"] == 2 and by_day["2026-11-25"]["others_sampled"] == 2
    assert by_day["2026-11-24"]["runners_cached"] == 1 and by_day["2026-11-24"]["others_sampled"] == 1
    assert [x["day"] for x in pop["days"]] == ["2026-11-25", "2026-11-24", "2026-11-23"]


def test_population_sample_is_seeded():
    runners, universe, cache = _world()
    kw = dict(runners_of=lambda d: runners[d], universe_of=lambda d: universe[d], get_day=store_reader(cache, []))

    def others(seed):
        return sorted((r["day"], r["symbol"]) for r in M.population(D25, 3, seed=seed, **kw)["rows"]
                      if r["group"] == "other")
    assert others(M.SEED) == others(M.SEED)
    assert others(M.SEED) != others(M.SEED + 1)


def test_negative_uncached_days_are_skipped_and_counted(monkeypatch):
    no_real_readers(monkeypatch)
    runners, universe, cache = _world()
    cache.pop(("O00", "2026-11-25"), None)
    pop = M.population(D25, 3, runners_of=lambda d: runners[d], universe_of=lambda d: universe[d],
                       get_day=store_reader(cache, []))
    assert pop["skipped"]["runner_not_cached"] == 1
    assert not any(r["symbol"] == "NOPE" for r in pop["rows"])
    assert pop["skipped"]["days_no_runner"] == 1
    assert not any(r["day"] == "2026-11-23" for r in pop["rows"])


def test_negative_day_with_no_runner_reads_nothing():
    calls, uni = [], []
    pop = M.population(D25, 2, runners_of=lambda d: [], universe_of=lambda d: uni.append(d) or ["X"],
                       get_day=store_reader({}, calls))
    assert pop["rows"] == [] and calls == [] and uni == []
    assert pop["skipped"]["days_no_runner"] == 2


def test_population_reads_minutes_only_through_get_day(monkeypatch):
    no_real_readers(monkeypatch)
    runners, universe, cache = _world()
    calls = []
    pop = M.population(D25, 3, runners_of=lambda d: runners[d], universe_of=lambda d: universe[d],
                       get_day=store_reader(cache, calls))
    assert pop["rows"]
    assert calls and all(isinstance(s, str) for s, _d in calls)


def test_population_steps_off_a_closed_end_day():
    runners, universe, cache = _world()
    pop = M.population(date(2026, 11, 26), 1, runners_of=lambda d: runners.get(d, []),
                       universe_of=lambda d: universe.get(d, []), get_day=store_reader(cache, []))
    assert [x["day"] for x in pop["days"]] == ["2026-11-25"]


# ── 6. the cluster bootstrap ────────────────────────────────────────────────────────────────────────────────────
def _mean_x(rows):
    return sum(r["x"] for r in rows) / len(rows) if rows else None


def _clusters(k=12):
    rng = random.Random(3)
    return {f"S{i}": [{"x": rng.uniform(0, 10)} for _ in range(1 + i % 3)] for i in range(k)}


def test_boot_ci_is_deterministic_and_covers_the_point():
    by = _clusters()
    a = M.boot_ci(by, _mean_x, n=400, seed=1)
    assert a == M.boot_ci(by, _mean_x, n=400, seed=1)
    assert a != M.boot_ci(by, _mean_x, n=400, seed=2)
    pt = _mean_x([r for v in by.values() for r in v])
    assert a[0] <= pt <= a[1]


def test_boot_ci_resamples_symbols_not_days():
    by = {"BIG": [{"x": 10.0} for _ in range(10)]}
    by.update({f"S{i}": [{"x": 0.0}] for i in range(10)})
    cluster = M.boot_ci(by, _mean_x, n=2000, seed=5)
    day_level = M.boot_ci({f"{s}|{j}": [r] for s, rs in by.items() for j, r in enumerate(rs)}, _mean_x,
                          n=2000, seed=5)
    assert cluster != day_level
    assert (cluster[1] - cluster[0]) > (day_level[1] - day_level[0])


def _independent_diff(a_by, b_by, stat, *, n, seed):
    """The OLD rule (two independent resamples), kept here only to show the union rule differs from it."""
    ka, kb = sorted(a_by), sorted(b_by)
    rng = random.Random(seed)
    draws = []
    for _ in range(n):
        ra = [r for k in rng.choices(ka, k=len(ka)) for r in a_by[k]]
        rb = [r for k in rng.choices(kb, k=len(kb)) for r in b_by[k]]
        draws.append(stat(ra) - stat(rb))
    return M._interval(draws)


def test_boot_diff_resamples_a_shared_symbol_once_for_both_groups():
    k = M.MIN_CLUSTERS + 2
    a_by = {f"S{i}": [{"x": float(i)}] for i in range(k)}
    b_by = {f"S{i}": [{"x": float(i)}] for i in range(k)}
    lo, hi = M._boot_diff(a_by, b_by, _mean_x, n=500, seed=7)
    assert lo == 0.0 and hi == 0.0
    ilo, ihi = _independent_diff(a_by, b_by, _mean_x, n=500, seed=7)
    assert ihi - ilo > 1.0


def test_boot_diff_is_deterministic_and_covers_the_point_with_partial_overlap():
    rng = random.Random(11)
    a_by = {f"S{i}": [{"x": rng.uniform(0, 10)} for _ in range(1 + i % 2)] for i in range(14)}
    b_by = {f"S{i}": [{"x": rng.uniform(2, 12)}] for i in range(8, 24)}
    a = M._boot_diff(a_by, b_by, _mean_x, n=800, seed=3)
    assert a == M._boot_diff(a_by, b_by, _mean_x, n=800, seed=3)
    assert a != M._boot_diff(a_by, b_by, _mean_x, n=800, seed=4)
    pt = _mean_x([r for v in a_by.values() for r in v]) - _mean_x([r for v in b_by.values() for r in v])
    assert a[0] <= pt <= a[1]


def test_negative_boot_diff_drops_a_draw_whose_stat_is_none():
    def stat(rows):
        return None if not rows or any(r.get("poison") for r in rows) else _mean_x(rows)

    a_by = {f"A{i}": [{"x": 1.0}] for i in range(M.MIN_CLUSTERS)}
    a_by["Z"] = [{"x": 100.0, "poison": True}]
    b_by = {f"B{i}": [{"x": 0.0}] for i in range(M.MIN_CLUSTERS)}
    assert M._boot_diff(a_by, b_by, stat, n=2000, seed=2) == (1.0, 1.0)
    a_by["Z"] = [{"x": 100.0}]
    lo, hi = M._boot_diff(a_by, b_by, stat, n=2000, seed=2)
    assert hi > 1.0


def test_negative_boot_diff_needs_min_clusters_in_each_group_not_in_the_union():
    a_by = {f"S{i}": [{"x": 1.0}] for i in range(M.MIN_CLUSTERS - 1)}
    b_by = {f"T{i}": [{"x": 0.0}] for i in range(M.MIN_CLUSTERS + 5)}
    assert len(set(a_by) | set(b_by)) >= M.MIN_CLUSTERS
    assert M._boot_diff(a_by, b_by, _mean_x, n=50) is None
    assert M._boot_diff(b_by, a_by, _mean_x, n=50) is None


def test_shipped_runner_minus_placebo_ci_is_the_union_bootstrap_of_the_saved_rows():
    out = json.loads(SHIPPED.read_text(encoding="utf-8"))
    if out.get("not_run"):
        pytest.skip("the shipped JSON says not_run: true")
    rows, p = out["rows"], out["params"]
    by_g = {g: M._by_symbol([r for r in rows if r.get("group") == g]) for g in M.GROUPS}
    ci = M._boot_diff(by_g[M.GROUPS[0]], by_g[M.GROUPS[1]], M._ratio(out["summary"]["first"], out["summary"]["gg"],
                                                                       "down"), n=p["boot_n"], seed=p["seed"])
    assert out["summary"]["runner_minus_other_ratio_down"]["ci"] == [M._rnd(ci[0]), M._rnd(ci[1])]


def test_negative_too_few_symbols_gives_no_interval():
    by = _clusters(M.MIN_CLUSTERS - 1)
    assert M.boot_ci(by, _mean_x, n=100) is None
    rows = [{"symbol": f"S{i}", "day": "2026-11-24", "warm": True, "group": "runner",
             "frames": {"1m": {"bars": 100, "down": 5, "up": 5}, "5m": {"bars": 20, "down": 1, "up": 1},
                        "15m": {"bars": 7, "down": 0, "up": 0}}} for i in range(M.MIN_CLUSTERS - 1)]
    s = M.summary(rows, n=50)
    p = s["groups"]["runner"]["primary"]
    assert p["ci"] is None and "too few names" in p["ci_text"] and p["point"] == 4.0
    assert s["groups"]["other"]["primary"]["ci"] is None
    assert s["runner_minus_other_ratio_down"]["ci"] is None
    assert json.loads(json.dumps(s, allow_nan=False))["groups"]["runner"]["primary"]["ci"] is None


# ── 7. summary ──────────────────────────────────────────────────────────────────────────────────────────────────
def _row(sym, day, group, warm, d1, d5, d15, bars=(100, 20, 7), up=(0, 0, 0)):
    return {"symbol": sym, "day": day, "group": group, "warm": warm,
            "frames": {"1m": {"bars": bars[0], "down": d1, "up": up[0]},
                       "5m": {"bars": bars[1], "down": d5, "up": up[1]},
                       "15m": {"bars": bars[2], "down": d15, "up": up[2]}}}


def test_summary_primary_by_hand():
    rows = [_row("A", "2026-11-24", "runner", True, 10, 2, 1), _row("A", "2026-11-25", "runner", False, 6, 3, 0),
            _row("B", "2026-11-24", "runner", True, 4, 4, 1), _row("C", "2026-11-24", "other", True, 8, 1, 1)]
    s = M.summary(rows, n=50)
    r = s["groups"]["runner"]
    assert r["primary"]["point"] == round(((10 - 2) + (6 - 3) + (4 - 4)) / 3, 4)
    assert r["ratio_down"]["point"] == round(20 / 9, 4)
    assert r["diff_down_gg_slow"]["point"] == round((1 + 3 + 3) / 3, 4)
    assert r["down_per_100_bars_1m"]["point"] == round(100 * 20 / 300, 4)
    assert r["n_name_days"] == 3 and r["n_symbols"] == 2
    assert set(s["groups"]["other"]) == set(r)
    assert s["groups"]["other"]["primary"]["point"] == 7.0
    assert s["runner_minus_other_ratio_down"]["point"] == round(20 / 9 - 8.0, 4)


def test_summary_warm_only_drops_exactly_the_cold_rows():
    rows = [_row("A", "2026-11-24", "runner", True, 10, 2, 1), _row("A", "2026-11-25", "runner", False, 6, 3, 0),
            _row("B", "2026-11-24", "runner", True, 4, 4, 1)]
    w = M.summary(rows, n=50)["groups"]["runner"]["warm_only"]["primary"]
    assert w["n_name_days"] == 2 and w["point"] == round((8 + 0) / 2, 4)
    assert M.summary(rows, n=50)["groups"]["runner"]["n_warm"] == 2


def test_summary_carries_a_ci_with_enough_symbols():
    rows = [_row(f"S{i}", "2026-11-24", "runner", True, 5 + i % 4, 1 + i % 2, 0) for i in range(12)]
    rows += [_row(f"P{i}", "2026-11-24", "other", True, 3 + i % 3, 1, 0) for i in range(12)]
    s = M.summary(rows, n=300)
    p = s["groups"]["runner"]["primary"]
    assert p["ci"] is not None and p["ci_text"] is None and p["ci"][0] <= p["point"] <= p["ci"][1]
    assert s["runner_minus_other_ratio_down"]["ci"] is not None


def test_negative_rows_missing_a_frame_are_left_out_of_that_number():
    rows = [_row("A", "2026-11-24", "runner", True, 10, 2, 1)]
    rows.append({**_row("B", "2026-11-24", "runner", True, 0, 0, 0), "frames": {"1m": None, "5m": None, "15m": None}})
    r = M.summary(rows, n=20)["groups"]["runner"]
    assert r["primary"]["point"] == 8.0


# ── 8. the doc's table is generated ─────────────────────────────────────────────────────────────────────────────
def test_doc_table_is_render_markdown_of_the_shipped_json():
    out = json.loads(SHIPPED.read_text(encoding="utf-8"))
    if out.get("not_run"):
        pytest.skip("the shipped JSON says not_run: true — no run to pin")
    doc = DOC.read_text(encoding="utf-8")
    assert M.MARK_BEGIN in doc and M.MARK_END in doc
    body = doc.split(M.MARK_BEGIN, 1)[1].split(M.MARK_END, 1)[0].strip("\n")
    assert body == M.render_markdown(out)


def test_shipped_json_is_strict_and_carries_ci_and_placebo():
    out = json.loads(SHIPPED.read_text(encoding="utf-8"), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    if out.get("not_run"):
        pytest.skip("the shipped JSON says not_run: true")
    g = out["summary"]["groups"]
    assert set(g) == set(M.GROUPS)
    assert out["params"]["seed"] == M.SEED and out["params"]["boot_n"] == M.BOOT_N
    assert out["params"]["min_clusters"] == M.MIN_CLUSTERS
    p = g["runner"]["primary"]
    assert (p["ci"] is None) == (p["ci_text"] is not None)


def test_render_not_run_never_prints_a_number():
    txt = M.render_markdown({"not_run": True, "reason": "container down"})
    assert txt.startswith("**NOT RUN**") and not re.search(r"\d", txt)


def test_render_prints_too_few_names_not_an_interval():
    rows = [_row(f"S{i}", "2026-11-24", "runner", True, 5, 1, 0) for i in range(3)]
    out = M.run(D25, 1, get_day=lambda s, d: None, runners_of=lambda d: [], universe_of=lambda d: [], n=10)
    out["summary"] = M.summary(rows, n=10)
    md = M.render_markdown(out)
    line = next(x for x in md.splitlines() if "PRIMARY" in x)
    assert "too few names" in line and "[" not in line


def test_main_markdown_reads_no_cache(monkeypatch, tmp_path, capsys):
    no_real_readers(monkeypatch)
    rows = [_row(f"S{i}", "2026-11-24", "runner", True, 5, 1, 0) for i in range(3)]
    out = M.run(D25, 1, get_day=lambda s, d: None, runners_of=lambda d: [], universe_of=lambda d: [], n=10)
    out["summary"] = M.summary(rows, n=10)
    f = tmp_path / "x.json"
    f.write_text(json.dumps(out, allow_nan=False), encoding="utf-8")
    assert M.main(["--markdown", str(f)]) == 0
    assert capsys.readouterr().out.strip() == M.render_markdown(out)


def test_run_output_is_strict_json(monkeypatch):
    no_real_readers(monkeypatch)
    runners, universe, cache = _world()
    out = M.run(D25, 3, get_day=store_reader(cache, []), runners_of=lambda d: runners[d],
                universe_of=lambda d: universe[d], n=20)
    back = json.loads(json.dumps(out, allow_nan=False))
    assert back["not_run"] is False and back["params"]["frames"] == [list(x) for x in WC.FRAMES]
    assert back["summary"]["first"] == "1m" and back["summary"]["gg"] == GC.RUN_BASE_FRAME


# ── 9. source guards ────────────────────────────────────────────────────────────────────────────────────────────
def test_source_guards():
    src = SCRIPT.read_text(encoding="utf-8")
    for bad in ("load_intraday(", "load_intraday_range", "_fetch_massive_minute", "update_one", "insert_", "requests.",
                ".ewm(", "signals.ema(", "_masked_ema(", "crosses_from_emas(", "boun" + "ce", chr(64),
                "win rate", "win_rate", "winrate", "hit rate"):
        assert bad not in src.lower(), bad
    assert "frame_crosses" in src and "_mongo_get_day" in src and "build_frame" in src and "resample_ohlcv" in src
    assert not re.search(r"ema9|ema21", src)


def test_new_files_hold_no_at_sign_nor_the_forbidden_word():
    for p in (SCRIPT, Path(__file__), DOC, SHIPPED):
        if p.exists():
            t = p.read_text(encoding="utf-8")
            assert chr(64) not in t, p
            assert ("boun" + "ce") not in t.lower(), p
