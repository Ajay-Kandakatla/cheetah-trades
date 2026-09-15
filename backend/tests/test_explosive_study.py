"""Study-side tests for scripts/explosive_study.py (design §6.7 item 19 + the
two container-replica pins). Everything runs WITHOUT Mongo on synthetic frames:
the script must be importable with no database, and every pure helper it
relies on is pinned here against the worktree function it replicates.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import pytest

from scripts import explosive_study as ES
from supply_demand import alert_gates as AG
from supply_demand import bounce_room as BR
from supply_demand import mood as MD
from supply_demand import patterns as PT
from supply_demand import sd_liquidity as SL
from supply_demand import turning_bullish as TB
from sepa import volume as V


# ── fixtures ──────────────────────────────────────────────────────────────────
def _frame(n: int = 400, seed: int = 5, base: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    step = rng.normal(0, 1.0, n)
    close = base + np.cumsum(step)
    close = np.maximum(close, 5.0)
    wick = np.abs(rng.normal(0, 0.8, n)) + 0.05
    high = close + wick
    low = close - wick
    low[7] = high[7] = close[7]                       # a zero-range bar for the CMF pin
    op = close - step * 0.5
    vol = rng.integers(100_000, 1_000_000, n).astype(float)
    dates = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({"date": dates, "open": op, "high": high, "low": low, "close": close,
                         "volume": vol, "d": dates.strftime("%Y-%m-%d")})


# ── the pre-registered sets are frozen and every threshold is imported ────────
def test_prereg_sets_are_frozen_and_the_five_pct_is_imported():
    assert len(ES.PREREG_P) == 14 and len(ES.PREREG_N) == 17
    assert len(set(ES.PREREG_P)) == 14 and len(set(ES.PREREG_N)) == 17
    assert ES.FIVE_PCT is AG.ALERT_MIN_ROOM_PCT
    assert ES.STOP_BUFFER_PCT is AG.STOP_BUFFER_PCT
    assert ES.SWEEP_WINDOW == AG.SWEEP_WINDOW_BARS
    assert ES.FLOOR_DEFAULT == 120 and ES.HOLD_DEFAULT == 20 and ES.CLOCKS_DEFAULT == (5, 10, 20)
    src = open(ES.__file__).read()
    # the KC study runs main() at import: it must never be imported, only transcribed
    assert "from scripts.turning_bullish_keltner_study" not in src
    assert "import scripts.turning_bullish_keltner_study" not in src
    assert "import turning_bullish_keltner_study" not in src
    assert "def kc_series" in src


# ── §6.7-19: episodes never overlap within a symbol ──────────────────────────
def test_episodes_never_overlap_within_a_symbol():
    rows = []
    for sym, idxs in (("AAA", [130, 131, 132, 150, 151, 170, 200]),
                      ("BBB", [125, 145, 146, 165, 300]),
                      ("CCC", [140])):
        for j in idxs:
            rows.append({"symbol": sym, "bar_idx": j, "dir": "bouncing" if j % 2 == 0 else "falling"})
    X = pd.DataFrame(rows).sample(frac=1.0, random_state=1).reset_index(drop=True)
    ep = ES.flag_episodes(X, 20)
    X["episode"] = ep
    for sym, g in X[X.episode].groupby("symbol"):
        j = np.sort(g["bar_idx"].to_numpy())
        assert (np.diff(j) >= 20).all(), sym
    # every non-episode has an episode of its symbol within the cooldown before it
    for _, r in X[~X.episode].iterrows():
        eps = X[(X.symbol == r.symbol) & X.episode & (X.bar_idx <= r.bar_idx)]["bar_idx"]
        assert len(eps) and r.bar_idx - eps.max() < 20
    assert X[X.symbol == "AAA"].sort_values("bar_idx")["episode"].tolist() == [True, False, False, True, False, True, True]
    assert X[X.symbol == "CCC"]["episode"].all()
    # the within-direction flag
    epd = ES.flag_episodes(X, 20, within="dir")
    X["epd"] = epd
    for (sym, d), g in X[X.epd].groupby(["symbol", "dir"]):
        j = np.sort(g["bar_idx"].to_numpy())
        assert (np.diff(j) >= 20).all()
    # AAA bouncing rows are 130,132,150,170,200 -> episodes 130,150,170,200
    aaa_b = X[(X.symbol == "AAA") & (X.dir == "bouncing")].sort_values("bar_idx")
    assert aaa_b["epd"].tolist() == [True, False, True, True, True]


# ── §6.7-19: the left join asserts on cohort shrink/growth, never silently ───
def test_left_join_asserts_on_cohort_shrink():
    E = pd.DataFrame({"symbol": ["A", "A", "B"], "date": ["d1", "d2", "d1"], "entry": [1.0, 2.0, 3.0]})
    F_missing = pd.DataFrame({"symbol": ["A"], "date": ["d1"], "rsi14_pre": [55.0]})
    X = ES.join_features(E, F_missing)
    assert len(X) == len(E)                                    # LEFT join: nothing dropped
    assert X["rsi14_pre"].isna().sum() == 2                    # the missing rows are NaN, counted
    F_dup = pd.DataFrame({"symbol": ["A", "A"], "date": ["d1", "d1"], "rsi14_pre": [55.0, 56.0]})
    with pytest.raises(AssertionError):
        ES.join_features(E, F_dup)                             # duplicate keys would GROW the cohort
    X0 = ES.join_features(E, pd.DataFrame())
    assert len(X0) == len(E)


# ── §6.7-19: the date-block placebo keeps whole dates ────────────────────────
def test_placebo_dates_keeps_whole_dates():
    rng = np.random.default_rng(0)
    counts = np.array([5, 3, 8, 2, 6, 4])
    for n_keep in (1, 4, 7, 10, 13, 27, 28):
        full, part, need = ES._date_block_keep(counts, n_keep, rng)
        taken = int(counts[full].sum())
        if part is None:
            assert taken == n_keep and need == 0
        else:
            assert part not in set(full.tolist())
            assert taken < n_keep <= taken + counts[part]
            assert need == n_keep - taken and 0 < need < counts[part]
    # the band itself: a cohort where every date is all-1 or all-0 -> whole-date keeps of
    # size 10 land on {0, 1, or a mix} but never on a mean impossible for whole dates
    D = pd.DataFrame({"date": np.repeat(["d%d" % i for i in range(10)], 10),
                      "symbol": ["s%d" % i for i in range(100)],
                      "hit5_20": np.repeat([1.0, 0.0] * 5, 10), "R20": 0.0})
    band = ES.placebo_dates(D, 10, ["hit5_20", "R20"], draws=200, seed=1)
    lo, hi = band["hit5_20"]
    assert lo in (0.0, 1.0) and hi in (0.0, 1.0)


# ── §6.7-19: the next-open convention skips a gap through the stop ───────────
def test_next_open_convention_skips_gap_through_stop():
    clocks, hold = (5, 10, 20), 20
    fh = np.full(20, 104.0)
    fl = np.full(20, 101.0)
    fc = np.full(20, 103.0)
    stop = 99.0
    gap = ES.next_open_block(98.5, fh, fl, fc, stop, None, 102.0, clocks, hold)
    assert gap["gap_N"] is True and np.isnan(gap["hit5_20_N"]) and np.isnan(gap["R20_N"])
    assert gap["why20_N"] is None
    at_stop = ES.next_open_block(99.0, fh, fl, fc, stop, None, 102.0, clocks, hold)
    assert at_stop["gap_N"] is True
    ok = ES.next_open_block(100.0, fh, fl, fc, stop, None, 102.0, clocks, hold)
    assert ok["gap_N"] is False and ok["entry_N"] == 100.0
    assert ok["risk_pct_N"] == pytest.approx((100.0 - 99.0) / 100.0 * 100.0)
    assert ok["hit5_20_N"] == 0.0 and ok["why20_N"] == "clock"
    # the stop is checked on bar j+1 itself under N
    fl2 = fl.copy()
    fl2[0] = 98.0
    stopped = ES.next_open_block(100.0, fh, fl2, fc, stop, None, 102.0, clocks, hold)
    assert stopped["stop_5_N"] == 1.0 and stopped["why5_N"] == "stop" and stopped["R5_N"] == pytest.approx(-1.0)


# ── §6.7-19: HIT5 / HIT5B / HIT_LID share the HIGH bar-part; HIT5C is the close twin ──
def test_hit5_hit5b_hit_lid_share_the_high_bar_part():
    clocks, hold = (5, 10, 20), 20
    entry, stop, band_hi, target = 100.0, 97.0, 99.0, 106.0
    fh = np.full(20, 101.0)
    fl = np.full(20, 99.5)
    fc = np.full(20, 100.5)
    fh[2] = 105.5                       # +5.5% on the HIGH of bar 3; the close stays 100.5
    b = ES.outcome_block(fh, fl, fc, entry, stop, target, band_hi, clocks, hold)
    assert b["hit5_5"] == 1.0 and b["hit5_10"] == 1.0 and b["hit5_20"] == 1.0
    assert b["k_5pct"] == 3
    assert b["hit5c_20"] == 0.0                                 # the close never got there
    assert b["hit5b_5"] == 1.0                                  # 99 * 1.05 = 103.95 <= 105.5
    assert b["hit_lid_20"] == 0.0 and b["why20"] == "clock"     # 105.5 < 106 target
    fh[4] = 106.0                                               # lid touched on bar 5's high
    b = ES.outcome_block(fh, fl, fc, entry, stop, target, band_hi, clocks, hold)
    assert b["hit_lid_5"] == 1.0 and b["why5"] == "target" and b["k_target"] == 5
    assert b["R5"] == pytest.approx((106.0 - 100.0) / 3.0)
    # the STOP is checked first inside a bar: same-bar stop + target -> stop
    fl3 = fl.copy()
    fl3[4] = 96.0
    b = ES.outcome_block(fh, fl3, fc, entry, stop, target, band_hi, clocks, hold)
    assert b["why5"] == "stop" and b["hit_lid_5"] == 0.0 and b["stop_5"] == 1.0
    assert b["hit5_5"] == 1.0                                   # bar 3 came before the bar-5 stop
    # a stop on the same bar as the +5% high -> not a hit (stop first)
    fl4 = fl.copy()
    fl4[2] = 96.0
    b = ES.outcome_block(fh, fl4, fc, entry, stop, target, band_hi, clocks, hold)
    assert b["hit5_20"] == 0.0 and b["stop_5"] == 1.0
    # CLEAR: no target -> hit_lid NaN, the trade can only stop or time out
    b = ES.outcome_block(fh, fl, fc, entry, stop, None, band_hi, clocks, hold)
    assert np.isnan(b["hit_lid_20"]) and b["why20"] == "clock" and b["hit5_20"] == 1.0
    assert b["max_gain_pct_20"] == pytest.approx(6.0)


# ── §6.7-19: the tail rule drops today's partial bar and the phantom echo only ──
def test_tail_rule_drops_today_and_phantom_only():
    f = _frame(30)
    today = f["d"].iloc[-1]
    log = {"today": 0, "phantom": 0}
    g = ES.apply_tail_rule(f, today, log)
    assert len(g) == 29 and log == {"today": 1, "phantom": 0}
    # not today, no echo -> untouched
    log = {"today": 0, "phantom": 0}
    g = ES.apply_tail_rule(f, "2030-01-01", log)
    assert len(g) == 30 and log == {"today": 0, "phantom": 0}
    # a phantom echo: same close, volume within 0.5% -> dropped
    p = f.copy()
    p.loc[p.index[-1], "close"] = p["close"].iloc[-2]
    p.loc[p.index[-1], "volume"] = p["volume"].iloc[-2] * 1.001
    log = {"today": 0, "phantom": 0}
    g = ES.apply_tail_rule(p, "2030-01-01", log)
    assert len(g) == 29 and log == {"today": 0, "phantom": 1}
    # same close but a genuinely different volume -> a real session, kept
    q = f.copy()
    q.loc[q.index[-1], "close"] = q["close"].iloc[-2]
    q.loc[q.index[-1], "volume"] = q["volume"].iloc[-2] * 1.5
    assert len(ES.apply_tail_rule(q, "2030-01-01", {"today": 0, "phantom": 0})) == 30
    # both: today's bar dropped, then the echo under it dropped
    b = p.copy()
    b.loc[b.index[-2], "close"] = b["close"].iloc[-3]
    b.loc[b.index[-2], "volume"] = b["volume"].iloc[-3]
    log = {"today": 0, "phantom": 0}
    g = ES.apply_tail_rule(b, today, log)
    assert len(g) == 28 and log == {"today": 1, "phantom": 1}
    assert list(g.index) == list(range(28))                     # integer index restored


# ── container replica 1: the served band == bounce_room.demand_read's pick ───
def test_served_band_pick_equals_bounce_room_demand_read():
    zones = [{"kind": "demand", "lo": 90.0, "hi": 92.0, "touches": 3},
             {"kind": "demand", "lo": 95.0, "hi": 99.5, "touches": 2},      # widest, top 99.5
             {"kind": "demand", "lo": 96.0, "hi": 98.0, "touches": 5},      # nested: higher lo, lower hi
             {"kind": "demand", "lo": 101.0, "hi": 103.0, "touches": 2},    # above the print: excluded
             {"kind": "supply", "lo": 97.0, "hi": 99.9, "touches": 4}]      # supply: ignored
    for px in (100.0, 99.0, 97.5, 96.5, 95.5, 93.0, 90.5):
        got = ES.served_band(px, zones)
        want = BR.demand_read(px, {"bands": zones})
        assert got is not None and want is not None, px
        assert (got["lo"], got["hi"], got["touches"]) == (want["lo"], want["hi"], want["touches"]), px
    assert ES.served_band(89.0, zones) is None and BR.demand_read(89.0, {"bands": zones}) is None
    assert ES.served_band(None, zones) is None and ES.served_band(100.0, []) is None
    # the EVENT band (highest lo under the print) is a different pick when bands nest
    px = 98.5                                          # inside {96,98}+1% AND inside {95,99.5}
    ev = max([b for b in zones if b["kind"] == "demand" and AG.demand_proximity_gate(px, b)],
             key=lambda b: b["lo"])
    assert ev["lo"] == 96.0 and ES.served_band(px, zones)["lo"] == 95.0


# ── container replica 2: intact == AG.sweep_read(frame=closed, day_low, last, day) ──
def _sweep_frame() -> pd.DataFrame:
    """Floor 100 / top 102. Bars sit at 103-105. Pierces, each the ONLY cause of
    the state asserted at its j:
      30  a real sweep (0.5% pierce, closed back above, 3x volume)
      55  a QUIET sweep (1.0x volume) — no absorption, never `found`
      60  a break-then-reclaim bar (low 99.0, close 99.6, next close 104, 3x vol)
      79  the last bar: pierce + reclaim ON THE EVENT BAR (tested as the day low)"""
    n = 80
    close = np.full(n, 104.0)
    low = np.full(n, 103.0)
    vol = np.full(n, 100_000.0)
    low[30], close[30], vol[30] = 99.5, 101.0, 300_000.0
    low[55], close[55], vol[55] = 99.4, 101.5, 100_000.0
    low[60], close[60], vol[60] = 99.0, 99.6, 300_000.0
    low[79], close[79], vol[79] = 99.3, 101.0, 300_000.0
    high = np.maximum(close + 1.0, 105.0)
    dates = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({"date": dates, "open": close, "high": high, "low": low, "close": close,
                         "volume": vol, "d": dates.strftime("%Y-%m-%d")})


def test_intact_replica_equals_sweep_read_with_sweeps_3_14_15_16_bars_back():
    f = _sweep_frame()
    band = {"kind": "demand", "lo": 100.0, "hi": 102.0, "touches": 2}
    states = {}
    for j in range(AG.SWEEP_WINDOW_BARS + 2, len(f)):
        closed = f.iloc[:j]
        closed_dt = closed.set_index(pd.to_datetime(closed["d"]))[["open", "high", "low", "close", "volume"]]
        day = pd.Timestamp(f["d"].iloc[j]).date()
        want = AG.sweep_read(band, frame=closed_dt, day_low=float(f["low"].iloc[j]),
                             last=float(f["close"].iloc[j]), day=day)
        got = ES.intact_replica(closed, band["lo"], band["hi"], float(f["low"].iloc[j]),
                                float(f["close"].iloc[j]))
        assert want is not None and got == want["state"], (j, got, want)
        states[j] = got
    # the sweep at bar 30 sits 3 / 14 / 15 bars back at j = 33 / 44 / 45 -> in the window: swept
    assert states[33] == "swept" and states[44] == "swept" and states[45] == "swept"
    assert states[46] == "intact"                              # 16 back: out of the window
    assert states[58] == "broken"                              # the quiet pierce: not found & min(low) < lo
    assert states[60] == "broken"                              # today pierced and the print is under the floor
    assert states[79] == "swept"                               # today pierced and reclaimed (event bar, vol NaN)
    assert ES.intact_replica(f.iloc[:79], 100.0, 102.0, None, 101.0) == "intact"   # no day low = the old read
    # the stop_hunt window (14 closed + the FULL event bar) agrees everywhere except when a pierce
    # sits exactly SWEEP_WINDOW_BARS bars back — asserted to be the ONLY disagreement on bars whose
    # own event bar does not pierce
    dis = []
    for j in range(AG.SWEEP_WINDOW_BARS + 2, len(f)):
        sh = ES.intact_stop_hunt(f, j, band["lo"], float(f["close"].iloc[j]))
        ev_pierce = float(f["low"].iloc[j]) < band["lo"]
        if sh != states[j] and not ev_pierce:
            dis.append(j)
    # 45: the bar-30 sweep is 15 back; 75: the bar-60 sweep is 15 back. (At j=70 the quiet bar-55
    # pierce is 15 back too, but bar 60 sits inside BOTH windows and decides both reads.)
    assert dis == [45, 75]
    for j in dis:
        assert float(f["low"].iloc[j - AG.SWEEP_WINDOW_BARS]) < band["lo"]
        assert (f["low"].iloc[j - AG.SWEEP_WINDOW_BARS + 1:j] >= band["lo"]).all()
    # documented difference on an event-bar pierce: the stop_hunt window carries the event bar's
    # REAL volume, the AG read appends it with volume NaN (no absorption test on a forming bar)
    quiet_ev = f.copy()
    quiet_ev.loc[79, "volume"] = 100_000.0
    assert ES.intact_stop_hunt(quiet_ev, 79, band["lo"], 101.0) == "broken"
    assert ES.intact_replica(quiet_ev.iloc[:79], 100.0, 102.0, 99.3, 101.0) == "swept"
    # fails closed
    assert ES.intact_replica(f.iloc[:10], 100.0, 102.0, 103.0, 104.0) is None
    assert ES.intact_replica(f.iloc[:40], 0.0, 102.0, 103.0, 104.0) is None


# ── the vectorised feature series equal the module functions at every j ──────
def test_rsi_cmf_atr_series_match_the_module_functions():
    f = _frame(300)
    c = f["close"].to_numpy(dtype=float)
    rsi = ES.rsi_series(c)
    cmf = ES.cmf_series(f["high"], f["low"], f["close"], f["volume"])
    atr = ES.atr14_series(f["high"], f["low"], f["close"])
    rng = np.random.default_rng(2)
    for j in list(rng.integers(21, 300, 60)) + [8, 9, 10, 20, 21, 27, 28]:
        want = MD._rsi(c[:j].tolist())
        if want is None:
            assert np.isnan(rsi[j - 1])
        else:
            assert rsi[j - 1] == pytest.approx(want, abs=1e-9), j
        want_c = V._chaikin_money_flow(f.iloc[:j], 20)["cmf"]
        if want_c is None:
            assert np.isnan(cmf[j - 1]), j
        else:
            assert cmf[j - 1] == pytest.approx(want_c, abs=1e-9), j
        want_a = PT.atr(f.iloc[:j], 14)
        if want_a is None:
            assert np.isnan(atr[j - 1]), j
        else:
            assert atr[j - 1] == pytest.approx(want_a, abs=1e-9), j
    assert np.isnan(rsi[13]) and not np.isnan(rsi[14])
    # a flat stretch: no losses -> 100 (gain > 0) as mood._rsi does
    flat = np.concatenate([np.linspace(10, 20, 30), np.full(20, 20.0)])
    assert ES.rsi_series(flat)[29] == 100.0 and MD._rsi(flat[:30].tolist()) == 100.0


def _kc_frame() -> pd.DataFrame:
    """A smooth drift with wide wicks (Bollinger inside Keltner -> squeeze, close above the
    midline, midline rising -> coiled_up), then a jump above the upper band (breaking_up)."""
    n = 220
    close = 100.0 + np.linspace(0, 6, n) + 0.02 * np.sin(np.arange(n))
    close[170:] += 25.0
    high = close + 2.0
    low = close - 2.0
    dates = pd.bdate_range("2025-01-02", periods=n)
    return pd.DataFrame({"date": dates, "open": close, "high": high, "low": low, "close": close,
                         "volume": 1e5, "d": dates.strftime("%Y-%m-%d")})


def test_kc_series_matches_keltner_verdict_grades():
    f = _kc_frame()
    kc = ES.kc_series(f)
    seen = {"coiled_up": 0, "breaking_up": 0}
    for j in range(45, len(f) + 1):
        v = TB.keltner_verdict(f.iloc[:j])
        grade = (v or {}).get("grade")
        assert bool(kc["coiled"][j - 1]) == (grade == "coiled_up"), (j, grade, kc["pos"][j - 1])
        assert bool(kc["breaking"][j - 1]) == (grade == "breaking_up"), (j, grade)
        if v and v.get("position") is not None:
            assert kc["pos"][j - 1] == pytest.approx(v["position"], abs=1e-9)
        if grade in seen:
            seen[grade] += 1
    assert seen["coiled_up"] > 0 and seen["breaking_up"] > 0     # the fixture exercises both
    assert (kc["fired"] & ~kc["coiled"]).sum() >= 0              # fired includes breaking bars
    assert kc["coiled"].sum() <= kc["fired"].sum()


# ── the forward pass equals the engine's loop (events() lines 495-513) ───────
def _engine_forward(hi, lo, c, j, px, stop, target, clocks, hold):
    max_clock = max(max(clocks), hold)
    hit_k = hit_px = hit_why = None
    for k in range(1, max_clock + 1):
        t = j + k
        if lo[t] <= stop:
            hit_k, hit_px, hit_why = k, stop, "stop"
            break
        if target is not None and hi[t] >= target:
            hit_k, hit_px, hit_why = k, target, "target"
            break
    out = {}
    for cl in sorted(set(clocks) | {hold}):
        if hit_k is not None and hit_k <= cl:
            ex, wy = hit_px, hit_why
        else:
            ex, wy = float(c[j + cl]), "clock"
        out["R%d" % cl] = (ex - px) / (px - stop)
        out["why%d" % cl] = wy
    return out


def test_outcome_block_matches_the_engine_forward_pass():
    f = _frame(400, seed=9)
    hi, lo, c = (f[k].to_numpy(dtype=float) for k in ("high", "low", "close"))
    clocks, hold = (5, 10, 20), 20
    rng = np.random.default_rng(4)
    checked = 0
    for j in rng.integers(50, 370, 200):
        px = float(c[j])
        stop = px * (1.0 - rng.uniform(0.005, 0.05))
        target = px * (1.0 + rng.uniform(0.02, 0.10)) if rng.uniform() < 0.8 else None
        want = _engine_forward(hi, lo, c, j, px, stop, target, clocks, hold)
        got = ES.outcome_block(hi[j + 1:j + 21], lo[j + 1:j + 21], c[j + 1:j + 21], px, stop, target,
                               px * 0.99, clocks, hold)
        for cl in (5, 10, 20):
            assert got["why%d" % cl] == want["why%d" % cl], (j, cl)
            assert got["R%d" % cl] == pytest.approx(want["R%d" % cl], abs=1e-9), (j, cl)
            assert got["stop_%d" % cl] == float(want["why%d" % cl] == "stop")
            if target is None:
                assert np.isnan(got["hit_lid_%d" % cl])
            else:
                assert got["hit_lid_%d" % cl] == float(want["why%d" % cl] == "target")
        checked += 1
    assert checked == 200


# ── an end-to-end run of the stats stage on a synthetic event table ──────────
def _synthetic_events(n_sym: int = 40, n_dates: int = 120, seed: int = 3,
                      planted: bool = False) -> pd.DataFrame:
    """`planted=True` makes HIT5 depend strongly on rsi14 (and intact) so the
    fit half SELECTS something and the scored-half branch runs."""
    rng = np.random.default_rng(seed)
    dates = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-03-03", periods=n_dates)]
    rows = []
    for s in range(n_sym):
        sym = "S%03d" % s
        js = np.sort(rng.choice(np.arange(130, 130 + n_dates), size=rng.integers(8, 25), replace=False))
        for j in js:
            entry = 50.0 + rng.uniform(0, 50)
            stop = entry * (1 - rng.uniform(0.01, 0.05))
            clear = rng.uniform() < 0.2
            target = None if clear else entry * (1 + rng.uniform(0.05, 0.2))
            rsi = rng.uniform(20, 80)
            intact = rng.uniform() < 0.4
            p_hit = (0.75 if (rsi > 60 and intact) else 0.55 if rsi > 60 else 0.08) if planted else 0.25
            hit = float(rng.uniform() < p_hit)
            stp = float(rng.uniform() < (0.3 if (planted and rsi > 60) else 0.6)) if hit == 0 else 0.0
            why = "stop" if stp else ("target" if (hit and not clear and rng.uniform() < 0.5) else "clock")
            R = -1.0 if why == "stop" else rng.uniform(-0.5, 3.0)
            row = {"symbol": sym, "date": dates[j - 130], "dir": rng.choice(["bouncing", "falling", "settling"], p=[0.6, 0.25, 0.15]),
                   "n_bands": 1, "entry": entry, "stop": stop, "target": target,
                   "room_pct": None if clear else (target / entry - 1) * 100, "clear": clear,
                   "risk_pct": (entry - stop) / entry * 100, "trade_pct": R * (entry - stop) / entry * 100,
                   "R": R, "why": why, "knife": rng.uniform() < 0.3, "mood": rng.uniform(-50, 50),
                   "bar_idx": int(j), "band_lo": stop / 0.995, "band_hi": stop / 0.995 * 1.02,
                   "band_touches": 2, "served_lo": stop / 0.995, "served_hi": stop / 0.995 * 1.02,
                   "served_touches": 2, "served_is_event": True, "open_next": entry * (1 + rng.normal(0, 0.01)),
                   "rsi14_pre": rsi, "rsi14_at": rsi + rng.normal(0, 3),
                   "rvol20_pre": rng.lognormal(0, 0.5), "rvol20_at": rng.lognormal(0, 0.5),
                   "rvol50_pre": rng.lognormal(0, 0.5), "rvol50_at": rng.lognormal(0, 0.5),
                   "dvol50_pre": rng.lognormal(16, 1.5), "cmf20_pre": rng.uniform(-0.3, 0.3),
                   "cmf20_at": rng.uniform(-0.3, 0.3), "pocket_pivot_at": rng.uniform() < 0.1,
                   "day_ret_at": rng.normal(0, 2), "close_pos_at": rng.uniform(),
                   "atr14_pct_pre": rng.uniform(1, 6), "kc_pos_pre": rng.uniform(-0.2, 1.2),
                   "kc_pos_at": rng.uniform(-0.2, 1.2), "kc_on_pre": rng.uniform() < 0.2, "kc_on_at": False,
                   "kc_coil_pre": int(rng.integers(0, 10)), "kc_coil_at": 0, "kc_rise_pre": True, "kc_rise_at": True,
                   "kc_fired_pre": rng.uniform() < 0.1, "kc_fired_at": rng.uniform() < 0.1,
                   "kc_coiled_pre": rng.uniform() < 0.08, "kc_coiled_at": rng.uniform() < 0.08,
                   "kc_breaking_pre": rng.uniform() < 0.05, "kc_breaking_at": rng.uniform() < 0.05,
                   "kc_width_ratio_pre": rng.uniform(0.5, 2), "kc_width_ratio_at": rng.uniform(0.5, 2),
                   "atr_pct_pre": rng.uniform(1, 6), "atr_pct_at": rng.uniform(1, 6),
                   "amd_grade_pre": rng.choice(["none", "basing", "raided", "stale", "failed", "marked_up"]),
                   "amd_grade_at": rng.choice(["none", "basing", "raided"]),
                   "amd_raided_pre": rng.uniform() < 0.1, "amd_raided_at": rng.uniform() < 0.1,
                   "amd_raid_ago_pre": np.nan, "amd_raid_vol_pre": np.nan, "amd_raid_depth_pre": np.nan,
                   "amd_raid_ago_at": np.nan, "amd_raid_vol_at": np.nan, "amd_raid_depth_at": np.nan,
                   "dist_52wh_pct_pre": rng.uniform(-40, 0) if j >= 252 else np.nan,
                   "above_52wl_pct_pre": rng.uniform(0, 80) if j >= 252 else np.nan,
                   "rsi_slope5_pre": rng.normal(0, 5), "vol_burst3_pre": rng.lognormal(0, 0.5),
                   "intact_state_at": "intact" if intact else rng.choice(["swept", "broken"]),
                   "intact_ev_state_at": rng.choice(["intact", "swept", "broken"]),
                   "stophunt_state": rng.choice(["intact", "swept", "broken"]),
                   "k_5pct": np.nan, "k_stop": np.nan, "k_target": np.nan,
                   "max_gain_pct_20": rng.uniform(0, 12), "hit5c_20": hit * float(rng.uniform() < 0.7),
                   "entry_N": entry, "gap_N": rng.uniform() < 0.05, "risk_pct_N": (entry - stop) / entry * 100,
                   "k_5pct_N": np.nan, "k_stop_N": np.nan, "k_target_N": np.nan,
                   "max_gain_pct_20_N": rng.uniform(0, 12), "hit5c_20_N": hit}
            row["intact_at"] = row["intact_state_at"] == "intact"
            row["intact_ev_at"] = row["intact_ev_state_at"] == "intact"
            row["intact_sh"] = row["stophunt_state"] == "intact"
            for cl in (5, 10, 20):
                for sfx in ("", "_N"):
                    row["hit5_%d%s" % (cl, sfx)] = hit
                    row["hit5b_%d" % cl] = hit
                    row["hit_lid_%d%s" % (cl, sfx)] = np.nan if clear else float(why == "target")
                    row["stop_%d%s" % (cl, sfx)] = stp
                    row["R%d%s" % (cl, sfx)] = R
                    row["why%d%s" % (cl, sfx)] = why
                    row["pct%d" % cl] = R
            rows.append(row)
    X = pd.DataFrame(rows).drop_duplicates(["symbol", "date"]).reset_index(drop=True)
    X["episode"] = ES.flag_episodes(X, 20)
    X["episode_dir"] = ES.flag_episodes(X, 20, within="dir")
    return X


def test_stats_stage_runs_end_to_end_without_mongo_and_writes_every_measured_key(tmp_path, capsys):
    X = _synthetic_events(n_sym=90, n_dates=200)                # enough bouncing episodes for the splits
    csv = tmp_path / "ev.csv"
    X.to_csv(csv, index=False)
    with open(str(csv) + ".meta.json", "w") as fh:
        json.dump({"universe_mode": "broad", "n_universe": 40, "symbols": sorted(X.symbol.unique().tolist()),
                   "n_frames": 40, "tail": {"today": 0, "phantom": 0}, "counters": {}, "floor": 120}, fh)
    cache = tmp_path / "cache.csv"
    X2 = X.copy()
    X2["symbol"] = X2["symbol"].str.replace("S", "C")
    pd.concat([X, X2]).to_csv(cache, index=False)
    out = tmp_path / "m.json"
    ES.main(["--stage", "stats", "--from-csv", str(csv), "--cache-csv", str(cache), "--json", str(out),
             "--boot-draws", "150", "--perm-draws", "100", "--placebo-draws", "100", "--emit-measured"])
    m = json.load(open(out))
    for k in ("run_date", "universe_mode", "n_names", "n_events_all", "n_events_bouncing", "n_episodes",
              "n_dates", "window", "floor", "clocks", "convention", "primary_outcome", "base",
              "survivorship", "liquidity_control", "per_feature", "selected", "edges", "splits",
              "status", "fallback", "script", "cohort_note", "intact_reconcile"):
        assert k in m, k
    assert m["status"] in ("separates", "no_signal")
    assert m["fallback"] == "intact,room_rank" and m["script"] == "backend/scripts/explosive_study.py"
    assert m["n_episodes"] <= m["n_events_bouncing"] <= m["n_events_all"]
    for k in ("hit5_5", "hit5_10", "hit5_20", "hit5b_20", "hit_lid_20", "n_lid", "stop_20", "R20",
              "R20_median", "R20_trim", "win20", "tgt_stop_clk", "room_pct", "risk_pct", "clear_pct"):
        assert k in m["base"], k
    for k in ("cache_n_names", "cache_hit5_20", "cache_stop_20", "d_hit5_vs_broad", "renames_n", "delisted_n"):
        assert k in m["survivorship"], k
    assert m["survivorship"]["cache_n_names"] == 2 * m["n_names"]
    assert {"min_dvol", "n", "hit5_20", "stop_20"} <= set(m["liquidity_control"])
    names = {(p["name"], p["convention"]) for p in m["per_feature"]}
    assert {(f, "P") for f in ES.PREREG_P} <= names and {(f, "N") for f in ES.PREREG_N} <= names
    top = m["per_feature"][0]["top"]
    for k in ("label", "d_hit5", "ci", "p_le0", "d_stop", "ci_stop", "d_hit5_reweighted", "ci_rw", "perm_p",
              "placebo_dates", "placebo_iid", "one_per_date", "one_per_symbol", "verdict"):
        assert k in top, k
    for s in ("s1", "s2", "s3"):
        assert s in m["splits"] and "verdict" in m["splits"][s]
    if m["status"] == "no_signal":
        assert m["selected"] == [] and m["edges"] == {}
    text = capsys.readouterr().out
    assert "RULE OF READING" in text and "MEASURED = {" in text and "SURVIVORSHIP" in text
    assert "NOT QUOTABLE" not in text
    # the same dict is a valid Python literal
    lit = text.split("MEASURED = ", 1)[1].split("\nstats done", 1)[0]
    import ast
    assert ast.literal_eval(lit)["status"] == m["status"]


def test_stats_stage_scores_the_oos_halves_when_the_fit_half_selects(tmp_path, capsys):
    X = _synthetic_events(n_sym=120, n_dates=220, seed=11, planted=True)
    csv = tmp_path / "ev.csv"
    X.to_csv(csv, index=False)
    out = tmp_path / "m.json"
    ES.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out),
             "--boot-draws", "200", "--perm-draws", "100", "--placebo-draws", "100"])
    m = json.load(open(out))
    text = capsys.readouterr().out
    assert "selected on the fit half: ['" in text                  # the planted feature was selected
    s1 = m["splits"]["s1"]
    assert s1["top_decile_n"] > 0 and s1["d_hit5"] is not None and s1["ci"] is not None
    assert s1["ci_2way"] is not None and s1["mdl"] is not None and s1["mdl"] > 0
    assert s1["d_hit5_top5"] is not None and s1["d_hit5_top20"] is not None
    assert "width sweep:" in text and "two-way (date x symbol) CI" in text
    for s in ("s1", "s2", "s3"):
        assert m["splits"][s]["verdict"] in ("separates", "no_signal")
    if m["status"] == "separates":
        assert m["convention"] in ("P", "N") and m["selected"] and m["edges"]
        for f in m["selected"]:
            assert f in m["edges"] and (m["edges"][f] is None or len(m["edges"][f]) == 101)
    # a planted lift of ~+40pp on a ~25% base must read as positive on the scored half
    assert s1["d_hit5"] > 0 and s1["quartile_gap"] > 0


def test_stats_stage_min_dvol_control_and_smoke_banner(tmp_path, capsys):
    X = _synthetic_events(n_sym=30, n_dates=90, seed=8)
    csv = tmp_path / "ev.csv"
    X.to_csv(csv, index=False)
    with open(str(csv) + ".meta.json", "w") as fh:
        json.dump({"universe_mode": "broad", "n_universe": 30, "stride": 18, "floor": 120}, fh)
    out = tmp_path / "m.json"
    ES.main(["--stage", "stats", "--from-csv", str(csv), "--json", str(out), "--min-dvol", "10000000",
             "--boot-draws", "120", "--perm-draws", "60", "--placebo-draws", "60"])
    m = json.load(open(out))
    assert m["quotable"] is False and m["min_dvol_filter"] == 10000000.0
    text = capsys.readouterr().out
    assert "NOT QUOTABLE" in text and "LIQUIDITY CONTROL RUN" in text
    assert "no --cache-csv given" in text


def test_symbols_for_rejects_unknown_mode_and_strides_the_sorted_list(monkeypatch):
    monkeypatch.setattr("sepa.universe.load_universe", lambda mode=None: ["ZZ", "AA", "MM", "AA", "BB"])
    assert ES.symbols_for("broad", 142) == ["AA", "BB", "MM", "ZZ"]
    assert ES.symbols_for("broad", 142, stride=2) == ["AA", "MM"]
    assert ES.symbols_for("broad", 142, names=1) == ["AA"]
    with pytest.raises(ValueError):
        ES.symbols_for("nope", 142)


# ── the non-positive-price guard: the AMMJ class that killed the cache replay ─
def _zero_low_frame() -> pd.DataFrame:
    """A frame carrying exactly one bar with low == 0.0, the AMMJ shape: the
    zero sorts first in _cluster's `pts` and becomes its own divisor."""
    f = _frame(n=300, seed=11).copy()
    f.loc[120, "low"] = 0.0
    return f


def test_drop_nonpositive_removes_only_the_bad_rows_and_counts_them():
    f = _zero_low_frame()
    log = {"nonpos_names": 0, "nonpos_rows": 0}
    g = ES.drop_nonpositive(f, log)
    assert len(g) == len(f) - 1
    assert log == {"nonpos_names": 1, "nonpos_rows": 1}
    assert (g[["open", "high", "low", "close"]].to_numpy(dtype=float) > 0.0).all()
    assert list(g.index) == list(range(len(g)))                 # index reset, positional j stays valid
    kept = f.drop(index=120).reset_index(drop=True)
    pd.testing.assert_frame_equal(g, kept)
    # a clean frame is returned untouched and nothing is counted
    clean = _frame(n=50, seed=3)
    log2 = {"nonpos_names": 0, "nonpos_rows": 0}
    assert ES.drop_nonpositive(clean, log2) is clean
    assert log2 == {"nonpos_names": 0, "nonpos_rows": 0}


def test_zero_low_breaks_price_zones_and_the_guard_fixes_it():
    """Pins the root cause: price_zones._cluster divides by its cluster seed
    (`(price - cur[0][0]) / cur[0][0]`), so a 0.0 low either raises
    ZeroDivisionError or seeds a band at 0.0 — both of which are the defect that
    killed chunk 0 of the cache replay. After the guard, neither happens."""
    from supply_demand import demand_reentry as DR
    from supply_demand import price_zones as PZ
    f = _zero_low_frame()
    sub = f.iloc[:252]
    px = float(f["close"].iloc[252])
    broke = False
    try:
        z = PZ.compute(sub, last_price=px, max_zones=None, **DR.zone_geom())
        broke = any(float(b["lo"]) <= 0.0 for b in z.get("demand") or [])
    except ZeroDivisionError:
        broke = True
    assert broke, "the synthetic frame no longer reproduces the zero-price defect"
    g = ES.drop_nonpositive(f, None)
    z2 = PZ.compute(g.iloc[:252], last_price=float(g["close"].iloc[252]), max_zones=None,
                    **DR.zone_geom())
    assert all(float(b["lo"]) > 0.0 for b in z2.get("demand") or [])
    assert all(float(b["lo"]) > 0.0 for b in z2.get("supply") or [])


def test_frame_wrapper_applies_the_guard_and_counts_each_name_once(monkeypatch):
    f = _zero_low_frame()
    monkeypatch.setattr(ES, "_ORIG_FRAME", lambda coll, sym: f.copy())
    monkeypatch.setattr(ES, "_SEEN", set())
    monkeypatch.setattr(ES, "TAIL", {"names": 0, "today": 0, "phantom": 0,
                                     "nonpos_names": 0, "nonpos_rows": 0})
    a = ES.frame_with_tail_rule(None, "AMMJ")
    b = ES.frame_with_tail_rule(None, "AMMJ")                    # second pass: same frame, no re-count
    assert len(a) == len(b) == len(f) - 1
    assert (a[["open", "high", "low", "close"]].to_numpy(dtype=float) > 0.0).all()
    assert ES.TAIL["names"] == 1
    assert ES.TAIL["nonpos_names"] == 1 and ES.TAIL["nonpos_rows"] == 1
