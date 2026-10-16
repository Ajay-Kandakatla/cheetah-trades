"""🕯️ Doji Sweep study — scripts/doji_sweep_study.py (BUILD_SPEC6 §3.11, WP-S;
AMENDMENTS6 B1 / B2 / B4 / B5 / B6 / B11 / B12 / B18), 2026-10-16.

Ajay 2026-10-16: "create me a new tab for Doji candle after a sweep. For any
stocks after a down trend. May be from all chart maps especially on the 60% 70%
down stocks" — and K1: "I heard but do some research and back test please on
accuracy".

Hermetic: synthetic frames, an in-memory price map, every reader injected, the
conftest refuses Mongo, no network. NEGATIVE cases throughout: the leak rule,
the masks, the placebo exclusions, the verdict rules, the read-only and
no-provider guards, the CLI refusals, no peeking in a count-only artifact.
"""
from __future__ import annotations

import ast
import io
import json
import re
import tokenize
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from chart_maps import board as BOARD
from chart_maps import doji_sweep_measured as DSM
from chart_maps import doji_sweep_tab as DJ
from chart_maps.high_beta_tab import FORBIDDEN_WORDS
from scripts import doji_sweep_study as S
from scripts.explosive_study import MIN_BUCKET_N
from sepa import prices
from supply_demand import key_levels as KL
from supply_demand import smc as SMC

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BACKEND / "scripts" / "doji_sweep_study.py"
PREREG_DOC = BACKEND.parent / DJ.PREREG_PATH
LAST = "2026-10-14"                                    # a Wednesday market day
NOW = datetime(2026, 10, 14, 22, 0, tzinfo=ET)         # after the 20:00 roll, outside the refuse window
GOOD_GIT = {"head": "a" * 40, "porcelain_empty": True}
_BWORD = re.compile("".join(map(chr, (98, 111, 117, 110, 99))), re.I)   # the b-word, never spelled in this file


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------
def _market_days(end: str, n: int) -> list:
    from market_hours.reminder import ALL_HOLIDAYS
    out, d = [], pd.Timestamp(end)
    while len(out) < n:
        if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in ALL_HOLIDAYS:
            out.append(d)
        d -= pd.Timedelta(days=1)
    return sorted(out)


PLANTS = (300, 330, 360, 390, 420, 450, 480, 505)


def _frame(seed=0, n=520, drift=-0.004, plants=PLANTS, vol=5e6, end=LAST, glitch_at=None):
    """A falling random walk with dojis planted on a test of the prior
    20-session low (set 8 sessions before): every even plant 1% above it,
    every odd plant 2% under it with the close back above."""
    rng = np.random.default_rng(seed)
    c = 100.0 * np.exp(np.cumsum(rng.normal(drift, 0.02, n)))
    prev = np.r_[c[0], c[:-1]]
    o = prev * (1 + rng.normal(0, 0.004, n))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.01, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.01, n)))
    for k, t in enumerate(plants):
        if t >= n:
            continue
        ref = lo[t - 20:t].min() * 0.97
        lo[t - 8] = ref
        low = ref * (1 + (1.0 if k % 2 == 0 else -2.0) / 100.0)
        width = low * 0.06
        mid = low + width * 0.6
        o[t], c[t], h[t], lo[t] = mid - 0.01 * width, mid + 0.01 * width, low + width, low
    if glitch_at is not None:
        c[glitch_at] = c[glitch_at] * 7.0
        h[glitch_at] = max(h[glitch_at], c[glitch_at])
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": np.full(n, float(vol))},
                        index=pd.DatetimeIndex(_market_days(end, n)))


def _spy(n=520, end=LAST, seed=99):
    rng = np.random.default_rng(seed)
    c = 400.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, n)))
    o = np.r_[c[0], c[:-1]] * (1 + rng.normal(0, 0.002, n))
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.004, "low": np.minimum(o, c) * 0.996,
                         "close": c, "volume": 5e7}, index=pd.DatetimeIndex(_market_days(end, n)))


def _universe(end=LAST):
    fr = {"ZQA": _frame(0), "ZQB": _frame(1, drift=-0.006), "ZQC": _frame(2, drift=-0.005),
          "ZQD": _frame(3, drift=-0.003), "ZQE": _frame(4, drift=-0.006, vol=4e5),
          "ZQF": _frame(5, n=200)}
    if end != LAST:
        fr = {k: _frame(i, end=end) for i, k in enumerate(fr)}
    fr["SPY"] = _spy(end=end)
    return fr


def _arrays(df, sym="ZQA", as_of=LAST, doc=None):
    spy = S.spy_maps(_spy(n=len(df), end=str(df.index[-1].date())), as_of)
    return S.symbol_arrays(sym, df, doc, None, as_of=date.fromisoformat(as_of), spy=spy)


def _main(argv, fr, *, now=NOW, git=GOOD_GIT, block=False, history_fn=None, pin=False):
    return S.main(argv, now=now, universe_fn=lambda: [s for s in fr if s != "SPY"],
                  frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr},
                  history_fn=history_fn or (lambda syms: {}), listing_fn=lambda syms: {}, block=block,
                  git_fn=lambda: dict(git), pin_prereg=pin)


def _blob():
    return S.git_blob_sha(PREREG_DOC) if PREREG_DOC.exists() else "f" * 40


def _oc(v, *, confirm="neither"):
    return {"ret": {h: v for h in S.HORIZONS}, "adj": {h: v for h in S.HORIZONS},
            "stop": {h: 0.0 for h in S.HORIZONS}, "mfe": {h: abs(v) for h in S.HORIZONS},
            "mae": {h: -abs(v) for h in S.HORIZONS}, "confirm": confirm}


def _events(n_events=300, n_dates=100, n_syms=80, effect=0.0, seed=3, k=5):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n_events):
        d = i % n_dates
        out.append({"sym": f"S{i % n_syms}", "date": f"D{d:04d}", "pos": d,
                    "ev": _oc(float(rng.normal(0, 2)) + effect),
                    "pls": [_oc(float(rng.normal(0, 2))) for _ in range(k)], "short": False})
    return out


@pytest.fixture(autouse=True)
def _reset_lists():
    S.ATTEMPTED.clear()
    S.FETCH_CALLS.clear()
    yield
    S.ATTEMPTED.clear()
    S.FETCH_CALLS.clear()


def _guard_patches(monkeypatch):
    """Let monkeypatch restore every attribute block_writes / block_fetches replace."""
    from pymongo.collection import Collection
    for m in S.RS.WRITE_METHODS:
        if hasattr(Collection, m):
            monkeypatch.setattr(Collection, m, getattr(Collection, m))
    for name in S.NO_FETCH_FUNCS:
        if hasattr(prices, name):
            monkeypatch.setattr(prices, name, getattr(prices, name))
    from sepa import universe as UNIV
    for name in S.UNIVERSE_NO_FETCH_FUNCS:
        if hasattr(UNIV, name):
            monkeypatch.setattr(UNIV, name, getattr(UNIV, name))
    monkeypatch.setattr(UNIV, "UNIV_CACHE_TTL_SEC", UNIV.UNIV_CACHE_TTL_SEC)
    monkeypatch.setattr(UNIV, "_LAST_SOURCE", dict(UNIV._LAST_SOURCE))
    monkeypatch.setattr(UNIV, "LAST_COUNTS", dict(UNIV.LAST_COUNTS))


# --------------------------------------------------------------------------
# the leak rule (NEGATIVE)
# --------------------------------------------------------------------------
def test_check_no_leak_raises_on_a_late_feature_and_an_early_outcome():
    S.check_no_leak(300, S.feature_window(300), S.outcome_window(300, 10))
    with pytest.raises(S.LeakError):
        S.check_no_leak(300, [299, 301], ())
    with pytest.raises(S.LeakError):
        S.check_no_leak(300, (), [300, 301])
    assert list(S.feature_window(300)) == list(range(300 - DJ.YEAR_BARS + 1, 301))
    assert list(S.outcome_window(300, 5)) == [301, 302, 303, 304, 305]


def test_NEG_outcome_start_zero_makes_outcomes_at_raise(monkeypatch):
    a = _arrays(_frame(0))
    S.outcomes_at(a, 300, entry="next_open")
    monkeypatch.setattr(S, "OUTCOME_START", 0)
    for entry in S.ENTRIES:
        with pytest.raises(S.LeakError):
            S.outcomes_at(a, 300, entry=entry)


def test_NEG_a_frame_mutated_after_t_leaves_every_mask_at_or_before_t_unchanged():
    df = _frame(1, drift=-0.006)
    t = 420
    mut = df.copy()
    mut.iloc[t + 1:, :4] = mut.iloc[t + 1:, :4].to_numpy() * 3.0
    mut.iloc[t + 1:, 4] = 1.0
    a, b = _arrays(df), _arrays(mut)
    ma, mb = S.cell_masks(a), S.cell_masks(b)
    assert any(ma[k][:t + 1].any() for k in S.CELLS)
    for k in S.CELLS:
        assert np.array_equal(ma[k][:t + 1], mb[k][:t + 1]), k
    for col in ("st5", "st10", "readset", "eligible", "floor"):
        assert np.array_equal(a[col][:t + 1], b[col][:t + 1]), col
    assert np.allclose(a["pct_ath"][:t + 1], b["pct_ath"][:t + 1], equal_nan=True)


# --------------------------------------------------------------------------
# the same detector as the tab
# --------------------------------------------------------------------------
def test_the_study_masks_are_the_tabs_read_on_every_one_of_the_last_60_bars():
    df = _frame(1, drift=-0.006)
    a = _arrays(df)
    m = S.cell_masks(a)
    n = len(df)
    assert a["floor"][DJ.YEAR_BARS:].all()
    hits = 0
    for t in range(n - 60, n):
        day = df.index[t].date()
        sess = S.session_after(day)
        r = DJ.read("ZQB", df.iloc[:t + 1], session=sess)
        fired = r["status"] == "fired" and bool(r.get("doji5"))
        assert bool(m["any_read"][t]) is fired, (t, r["status"])
        assert bool(m["primary"][t]) is (fired and "w52" in r["reads"]), t
        hits += int(fired)
    assert hits >= 1


def test_the_verdict_cells_are_the_engines_study_cells():
    a = _arrays(_frame(2, drift=-0.005))
    vc = DJ.study_cells(DJ.frame_features(a["closed"]), pct_below_ath=a["pct_ath"], floor=a["floor"])
    m = S.cell_masks(a)
    for k in DSM.VERDICT_CELLS:
        assert np.array_equal(m[k], vc[k]), k
    assert S.CELLS[:3] == DSM.VERDICT_CELLS and set(DSM.SERVED_CELLS) <= set(S.CELLS)
    assert "w52_60" not in S.CELLS                     # == the primary (B4)


def test_the_floor_is_the_boards_own_liquidity_rule():
    a = _arrays(_frame(4, drift=-0.006, vol=4e5))
    adv = DJ.frame_features(a["closed"])["adv50"].to_numpy()
    want = np.asarray([BOARD.passes_liquidity(None if not np.isfinite(x) else x,
                                              BOARD.default_min_tier(DJ.TAB_KEY)) for x in adv])
    assert np.array_equal(a["floor"], want)
    assert (~a["floor"]).any() and a["floor"].any()


# --------------------------------------------------------------------------
# NEGATIVES on the masks
# --------------------------------------------------------------------------
DOJI5_CELLS = tuple(k for k in S.CELLS if k not in ("doji10", "test_no_doji", *S.FIRE_POOL_SENSITIVITY))
TESTED_CELLS = tuple(k for k in S.CELLS if k not in ("undercut_deep", "doji_no_test", "swing_sweep"))
REF_OK_CELLS = tuple(k for k in S.CELLS if k != "swing_sweep")


def _merged():
    a = _arrays(_frame(2, drift=-0.005))
    return a, S.cell_masks(a), DJ.frame_features(a["closed"])


def test_NEG_a_non_doji_never_enters_a_doji_cell():
    a, m, f = _merged()
    body = f["body_pct"].to_numpy()
    not5 = ~(np.nan_to_num(body, nan=np.inf) < DJ.DOJI_BODY_PCT)
    not10 = ~(np.nan_to_num(body, nan=np.inf) < DJ.DOJI_BODY_WIDE_PCT)
    assert not5.any()
    for k in DOJI5_CELLS:
        assert not (m[k] & not5).any(), k
    assert not (m["doji10"] & not10).any()
    assert not (m["test_no_doji"] & ~not10).any()         # the control never holds a doji at either body
    assert not (m["test_no_doji_fire_pool"] & ~not10).any()   # nor its sensitivity (fix round 2)


def test_NEG_a_low_outside_the_5pct_test_never_enters_a_tested_cell():
    df = _frame(2, drift=-0.005)
    df = _deep_plant(df, 470, -8.0)
    a = _arrays(df)
    m, f = S.cell_masks(a), DJ.frame_features(a["closed"])
    untested = ~f["tested"].to_numpy()
    for k in TESTED_CELLS:
        assert not (m[k] & untested).any(), k
    assert m["undercut_deep"][470]                       # it lands only in the cell outside his test


def _deep_plant(df, t, test_pct):
    df = df.copy()
    lo = df["low"].to_numpy().copy()
    ref = lo[t - 20:t].min() * 0.97
    df.iloc[t - 8, df.columns.get_loc("low")] = ref
    low = ref * (1 + test_pct / 100.0)
    width = low * 0.06
    mid = low + width * 0.6
    df.iloc[t, :4] = [mid - 0.01 * width, low + width, low, mid + 0.01 * width]
    return df


def test_NEG_a_reference_low_under_4_sessions_old_never_fires():
    a, m, f = _merged()
    young = f["ref_age"].to_numpy() < DJ.SWEEP_REF_MIN_AGE
    assert young.any()
    for k in REF_OK_CELLS:
        assert not (m[k] & young).any(), k


def test_NEG_a_suspect_bar_is_never_an_event_or_a_placebo():
    df = _frame(1, drift=-0.006, glitch_at=280)
    a = _arrays(df)
    m = S.cell_masks(a)
    sus = DJ.frame_features(a["closed"])["suspect"].to_numpy()
    assert sus[280:280 + DJ.YEAR_BARS - 1].all()
    for k in S.CELLS:
        assert not (m[k] & sus).any(), k
    for t in np.flatnonzero(m["any_read"] | m["test_no_doji"]):
        for ff in (True, False):
            assert not sus[S.placebo_pool(a, int(t), floor=ff)].any()


def test_as_of_follows_the_tabs_20h_roll_never_16_30():
    days = ["2026-10-12", "2026-10-13", "2026-10-14"]
    assert S.default_as_of(days, datetime(2026, 10, 14, 15, 0, tzinfo=ET)) == "2026-10-13"
    assert S.default_as_of(days, datetime(2026, 10, 14, 17, 0, tzinfo=ET)) == "2026-10-13"   # NEG: not RS's 16:30
    assert S.RS.default_as_of(days, datetime(2026, 10, 14, 17, 0, tzinfo=ET)) == "2026-10-14"
    assert S.default_as_of(days, datetime(2026, 10, 14, 21, 0, tzinfo=ET)) == "2026-10-14"
    assert S.default_as_of([], NOW) is None
    assert S.session_after(date(2026, 10, 14)) == date(2026, 10, 15)


def test_NEG_main_at_15h_with_force_window_cuts_the_today_bar(tmp_path):
    fr = _universe()
    out = tmp_path / "c.json"
    rc = _main(["--count-only", "--force-window", "--out", str(out)], fr,
               now=datetime(2026, 10, 14, 15, 0, tzinfo=ET))
    assert rc == 0
    art = json.loads(out.read_text())
    assert art["as_of"] == "2026-10-13" and art["last_session"] <= "2026-10-13"


# --------------------------------------------------------------------------
# placebos (+ B1)
# --------------------------------------------------------------------------
def _synthetic_a(n=200):
    return {"n": n, "eligible": np.ones(n, dtype=bool), "readset": np.full(n, 4),
            "fired10": np.zeros(n, dtype=bool), "after_fire": np.zeros(n, dtype=bool),
            "floor": np.ones(n, dtype=bool)}


def test_placebo_pool_rules_and_b1_window_exclusions():
    a = _synthetic_a()
    a["readset"][150:] = 5
    a["fired10"][40] = True
    a["after_fire"] = S.after_fire_mask(a["fired10"])
    a["floor"][60:65] = False
    t = 100
    pool = S.placebo_pool(a, t, floor=True)
    assert t not in pool
    assert not ((pool >= t - S.PLACEBO_GAP) & (pool <= t + S.PLACEBO_GAP)).any()   # B1: never its own window
    assert 40 not in pool                                                           # never a 10%-body fire
    assert not ((pool > 40) & (pool <= 40 + S.PLACEBO_GAP)).any()                  # B1: never after a fire
    assert not (pool >= 150).any()                                                  # the same read set only
    assert not np.isin(np.arange(60, 65), pool).any()                               # the floor
    assert (pool + S.PRIMARY_H <= a["n"] - 1).all()
    nofl = S.placebo_pool(a, t, floor=False)
    assert np.isin(np.arange(61, 65), nofl).all()                                   # all_liquidity: no floor
    assert S.NO_FLOOR_CELLS == ("all_liquidity",)


def test_after_fire_mask_is_the_20_sessions_after_a_fire():
    f = np.zeros(80, dtype=bool)
    f[10] = True
    m = S.after_fire_mask(f)
    assert not m[:11].any() and m[11:11 + S.PLACEBO_GAP].all() and not m[11 + S.PLACEBO_GAP:].any()


def test_draws_k5_without_replacement_deterministic_short_pool_with_replacement_empty_none():
    pool = np.arange(50, 90)
    d1 = S.draw_placebos(pool, rng=S.placebo_rng(S.SEED_DEFAULT, 3, 300, True))
    d2 = S.draw_placebos(pool, rng=S.placebo_rng(S.SEED_DEFAULT, 3, 300, True))
    d3 = S.draw_placebos(pool, rng=S.placebo_rng(S.SEED_DEFAULT, 3, 301, True))
    assert len(d1) == S.PLACEBO_K == 5 and len(set(d1)) == 5 and np.array_equal(d1, d2)
    assert not np.array_equal(d1, d3)
    short = S.draw_placebos(np.array([7, 9, 11]), rng=S.placebo_rng(1, 0, 0, True))
    assert len(short) == 5 and set(short) <= {7, 9, 11}
    assert S.draw_placebos(np.array([], dtype=int), rng=S.placebo_rng(1, 0, 0, True)).size == 0


def test_NEG_an_unmatched_event_is_counted_and_out_of_the_contrast():
    ev = _events(n_events=120, n_dates=40, n_syms=30)
    ev[0]["pls"] = []
    ev[0]["ev"] = _oc(1000.0)
    ev[1]["short"] = True
    blk = S.cell_block("w52_40", ev, draws=50, seed=1, count_only=False)
    assert blk["n_unmatched"] == 1 and blk["placebo_short_pool"] == 1
    assert blk["n_events"] == 119 and blk["n_placebo"] == 119 * 5   # the contrast set (fix round 1)
    assert S.contrast_counts(ev)["n_detected"] == 120
    assert blk["event_mean_pct"] < 100                 # the unmatched 1000% never reaches the contrast


def test_run_placebos_are_same_name_same_read_set_and_never_a_fired_session():
    fr = _universe()
    store = {}
    for s in ("ZQB", "ZQC"):
        store[s] = _arrays(fr[s], sym=s)
    for s, a in store.items():
        m = S.cell_masks(a)
        for t in np.flatnonzero(m["any_read"]):
            pool = S.placebo_pool(a, int(t), floor=True)
            assert (a["readset"][pool] == a["readset"][t]).all()
            assert not a["fired10"][pool].any() and int(t) not in pool


# --------------------------------------------------------------------------
# outcomes
# --------------------------------------------------------------------------
def _hand_a():
    n = 40
    o = np.full(n, 10.0)
    h = np.full(n, 10.5)
    lo = np.full(n, 9.5)
    c = np.full(n, 10.0)
    h[5], lo[5] = 11.0, 9.0                         # the candle at t = 5
    o[6], c[7], h[7] = 10.2, 11.5, 11.6              # next open 10.2; closes above the high on j = 2
    so = np.full(n, 100.0)
    sc = np.full(n, 100.0)
    sc[15] = 102.0
    return {"n": n, "o": o, "h": h, "l": lo, "c": c, "spy_o": so, "spy_c": sc}


def test_outcomes_by_hand():
    a = _hand_a()
    out = S.outcomes_at(a, 5, entry="next_open")
    assert out["confirm"] == "up"
    assert out["ret"][10] == pytest.approx((10.0 / 10.2 - 1) * 100)
    assert out["adj"][10] == pytest.approx((10.0 / 10.2 - 1) * 100 - 2.0)
    assert out["stop"][5] == 0.0 and out["mfe"][5] == pytest.approx((11.6 / 10.2 - 1) * 100)
    a2 = _hand_a()
    a2["c"][8] = 8.5                                 # a close under the candle's low
    a2["c"][7] = 10.0
    o2 = S.outcomes_at(a2, 5, entry="next_open")
    assert o2["confirm"] == "down" and o2["stop"][5] == 100.0
    assert np.isnan(S.outcomes_at(a2, 5, entry="confirm")["ret"][5])          # no confirmation -> no entry
    cl = S.outcomes_at(a, 5, entry="close")
    assert cl["ret"][5] == pytest.approx(0.0)
    cf = S.outcomes_at(a, 5, entry="confirm")
    assert cf["ret"][5] == pytest.approx((10.0 / 11.5 - 1) * 100)
    late = S.outcomes_at(a, 35, entry="next_open")
    assert late["confirm"] is None and np.isnan(late["ret"][10])            # incomplete window


def test_the_vectorised_baseline_return_equals_outcomes_at():
    a = _arrays(_frame(0))
    r = S._r_primary(a)
    for t in list(range(250, 260)) + [a["n"] - 11, a["n"] - 10, a["n"] - 1]:
        want = S.outcomes_at(a, t, entry="next_open")["ret"][S.PRIMARY_H]
        assert (np.isnan(r[t]) and np.isnan(want)) or r[t] == pytest.approx(want), t


# --------------------------------------------------------------------------
# the bootstrap, the verdict, Holm (B2 / B6)
# --------------------------------------------------------------------------
def test_weighted_median_equals_numpy_on_repeated_values():
    rng = np.random.default_rng(0)
    v = np.sort(rng.normal(0, 1, 37))
    w = rng.integers(0, 4, size=(25, 37)).astype(np.int32)
    w[:, 0] += 1
    got = S._wmedian(v, w)
    for i in range(25):
        assert got[i] == pytest.approx(np.median(np.repeat(v, w[i])))


def test_bootstrap_null_separates_inverted_at_the_default_seed():
    def verdict(effect):
        b = S.cell_block("primary", _events(effect=effect), draws=S.DRAWS_DEFAULT, seed=S.SEED_DEFAULT,
                         count_only=False)
        return b["verdict"]
    assert verdict(0.0) == "no_signal"
    assert verdict(3.0) == "separates"
    assert verdict(-3.0) == "inverted"


def test_NEG_too_few_dates_or_events_is_too_small():
    b = S.cell_block("primary", _events(n_events=300, n_dates=29, effect=3.0), draws=200, seed=1,
                     count_only=False)
    assert b["verdict"] == "too_small"
    b = S.cell_block("primary", _events(n_events=99, n_dates=60, effect=3.0), draws=200, seed=1,
                     count_only=False)
    assert b["verdict"] == "too_small" and S.MIN_CELL_EVENTS == 100
    assert S.cell_verdict(100, 30, [0.1, 1.0]) == "separates"
    assert S.cell_verdict(100, 30, [0.0, 1.0]) == "no_signal"                 # a bound exactly 0
    assert S.cell_verdict(100, 30, None) == "too_small"


def test_B2_one_block_carrying_the_effect_the_block_ci_spans_zero_the_date_ci_does_not():
    ev, pl, owner, blocks, dates = [], [], [], [], []
    for b in range(30):
        base = 0.2 if b % 2 else -0.2
        for d in range(10):
            for _k in range(2):
                ev.append(base + (5.0 if b == 0 else 0.0))
                pl.append(0.0)
                owner.append(len(ev) - 1)
                blocks.append(b)
                dates.append(b * 10 + d)
    blk = S.cluster_ci(ev, pl, owner, blocks, stat="mean", draws=2000, seed=7)
    naive = S.cluster_ci(ev, pl, owner, dates, stat="mean", draws=2000, seed=7)
    assert naive[0] > 0                               # the naive per-date CI clears zero
    assert blk[0] <= 0 <= blk[1]                      # the binding block CI spans it
    assert S.cluster_ci([1.0], [0.0], [0], ["x"], stat="mean", draws=10, seed=1) is None   # < 2 clusters


def test_axes_must_agree_and_holm_stops_the_step_down():
    assert S.axes_verdict(200, 60, 50, [0.5, 1.0], [0.2, 0.9]) == "separates"
    assert S.axes_verdict(200, 60, 50, [0.5, 1.0], [-0.2, 0.9]) == "axes_disagree"     # NEG
    assert S.axes_verdict(200, 60, 50, [-1.0, -0.5], [-0.9, -0.1]) == "inverted"
    assert S.axes_verdict(200, 60, 50, [-1.0, 0.5], [-0.9, 0.1]) == "no_signal"
    assert S.axes_verdict(200, 60, 50, [0.5, 1.0], [0.2, 0.9], p_holm=0.06) == "no_signal"   # NEG: Holm
    assert S.axes_verdict(200, 60, 50, [0.5, 1.0], [0.2, 0.9], p_holm=0.01) == "separates"
    assert S.axes_verdict(99, 60, 50, [0.5, 1.0], [0.2, 0.9]) == "too_small"


def test_holm_and_its_levels():
    assert S.holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert S.holm([None, 0.02, 0.5]) == [None, pytest.approx(0.04), pytest.approx(0.5)]
    lv = S.holm_levels([0.01, 0.04, 0.03])
    assert lv == pytest.approx([100 - 5 / 3, 95.0, 97.5])
    assert S.p_from_boot(np.array([1.0, 2.0, 3.0, -1.0])) == pytest.approx(0.5)
    assert S.p_from_boot(None) is None


def test_the_symbol_axis_and_the_block_axis_differ_on_a_clustered_name():
    ev = _events(n_events=300, n_dates=100, n_syms=80, effect=0.0)
    for e in ev:
        if e["sym"] == "S0":
            e["ev"] = _oc(40.0)
    b = S.cell_block("any_read", ev, draws=500, seed=2, count_only=False)
    assert b["ci_symbol"] != b["ci_block"] and b["ci_date"] != b["ci_block"]


# --------------------------------------------------------------------------
# the smc slice (the full-frame trap — NEGATIVE)
# --------------------------------------------------------------------------
def _smc_frame(n=400, seed=11):
    rng = np.random.default_rng(seed)
    c = 50 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.01, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.015, n)))
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": 1e6},
                        index=pd.DatetimeIndex(_market_days(LAST, n)))


def _truncated(df, t):
    return any(s["bars_ago"] == 0 and s["side"] == "sell_side" for s in SMC.liquidity_sweeps(df.iloc[:t + 1]))


def test_swing_sweep_at_equals_the_truncated_read_on_20_random_t():
    df = _smc_frame()
    rng = np.random.default_rng(5)
    ts = rng.choice(np.arange(70, len(df)), 20, replace=False)
    for t in ts:
        assert S.swing_sweep_at(df, int(t)) is _truncated(df, int(t)), t
    assert any(S.swing_sweep_at(df, t) for t in range(70, len(df)))


def test_NEG_the_full_frame_call_reads_the_wrong_bar_and_misses_old_sweeps():
    df = _smc_frame()
    hits = [t for t in range(70, len(df) - 120) if S.swing_sweep_at(df, t)]
    assert hits
    t = hits[0]
    full = SMC.liquidity_sweeps(df)
    assert not any(s["idx"] == t for s in full)        # older than the lookback: the full frame never scans it
    # a frame whose LAST bar is a sell-side sweep: read whole, bars_ago == 0 is
    # that last bar for EVERY t — a quiet earlier candle would read as a sweep
    end = hits[-1]
    df2 = df.iloc[:end + 1]
    assert any(s["bars_ago"] == 0 and s["side"] == "sell_side" for s in SMC.liquidity_sweeps(df2))
    quiet = [u for u in range(70, end) if not S.swing_sweep_at(df2, u)]
    assert quiet and not S.swing_sweep_at(df2, quiet[-1])
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    fn = src[src.index("def swing_sweep_at"):src.index("# the cells (BUILD_SPEC6")]
    assert "closed.iloc[start:t + 1]" in fn and "liquidity_sweeps(closed)" not in fn


# --------------------------------------------------------------------------
# no provider, no write (B18)
# --------------------------------------------------------------------------
def test_block_fetches_makes_every_fetcher_raise_and_records_it(monkeypatch):
    _guard_patches(monkeypatch)
    S.block_fetches()
    present = [n for n in S.NO_FETCH_FUNCS if hasattr(prices, n)]
    assert {"load_prices", "_fetch_massive", "bulk_snapshot"} <= set(present)
    for name in present:
        with pytest.raises(S.NoFetchError):
            getattr(prices, name)("SPY")
    assert S.FETCH_CALLS == present


def test_writes_raise_and_are_recorded_an_index_create_is_a_no_op(monkeypatch):
    from pymongo.collection import Collection
    _guard_patches(monkeypatch)
    S.block_writes()

    class _Fake:
        name = "price_cache"
    with pytest.raises(S.WriteBlockedError):
        Collection.insert_one(_Fake(), {"x": 1})
    with pytest.raises(S.WriteBlockedError):
        Collection.update_one(_Fake(), {}, {"$set": {"a": 1}})
    assert Collection.create_index(_Fake(), "k") == "blocked_index"
    assert S.ATTEMPTED == ["price_cache.insert_one", "price_cache.update_one", "price_cache.create_index"]
    assert S.data_writes(S.ATTEMPTED) == ["price_cache.insert_one", "price_cache.update_one"]


def test_NEG_a_run_that_attempts_a_data_write_exits_3_and_writes_nothing(monkeypatch, tmp_path):
    from pymongo.collection import Collection
    _guard_patches(monkeypatch)

    class _Fake:
        name = "ath_history"

    def sneaky(syms):
        try:
            Collection.update_one(_Fake(), {}, {"$set": {"a": 1}})
        except S.WriteBlockedError:
            pass
        return {}
    out = tmp_path / "c.json"
    rc = _main(["--count-only", "--out", str(out)], _universe(), block=True, history_fn=sneaky)
    assert rc == 3 and not out.exists()


def test_main_with_the_guards_on_makes_no_provider_call(monkeypatch, tmp_path):
    _guard_patches(monkeypatch)
    out = tmp_path / "c.json"
    assert _main(["--count-only", "--out", str(out)], _universe(), block=True) == 0
    art = json.loads(out.read_text())
    assert art["provider_calls"] == 0 and art["attempted_writes"] == []


def test_NEG_the_script_never_calls_or_names_a_fetcher_in_code():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    bad = set(S.NO_FETCH_FUNCS)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in bad and not node.attr.startswith(("_fetch", "fetch_")), node.attr
        if isinstance(node, ast.Name):
            assert node.id not in bad and not node.id.startswith(("_fetch", "fetch_")), node.id
    mods = S.imported_modules()
    assert not any(m.split(".")[-1] in bad for m in mods)
    assert {"chart_maps.doji_sweep_tab", "chart_maps.doji_sweep_measured", "scripts.resiliency_study",
            "scripts.explosive_study.MIN_BUCKET_N", "sepa.prices"} <= mods


def test_NEG_there_is_no_fetch_mode():
    with pytest.raises(SystemExit):
        S.parse_args(["--fetch"])
    assert S.parse_args([]).no_fetch is True and S.parse_args(["--no-fetch"]).no_fetch is True


# --------------------------------------------------------------------------
# CLI refusals + no peeking
# --------------------------------------------------------------------------
@pytest.mark.parametrize("hm", [(9, 0), (12, 30), (16, 29)])
def test_NEG_refuses_inside_the_session_window(hm, tmp_path):
    now = datetime(2026, 10, 14, hm[0], hm[1], tzinfo=ET)
    assert _main(["--count-only", "--out", str(tmp_path / "c.json")], _universe(), now=now) == 2


def test_NEG_an_outcome_run_needs_both_prereg_ids_a_clean_tree_and_the_real_blob(tmp_path):
    fr = _universe()
    out = str(tmp_path / "a.json")
    assert _main(["--out", out, "--prereg-blob", _blob()], fr) == 2
    assert _main(["--out", out, "--prereg-commit", "abc1234"], fr) == 2
    both = ["--out", out, "--prereg-commit", "abc1234", "--prereg-blob", _blob(), "--draws", "20"]
    assert _main(both, fr, git={"head": "a" * 40, "porcelain_empty": False}) == 2       # B12: a dirty tree
    assert _main(both, fr, git={"head": None, "porcelain_empty": None}) == 2            # no git, no attestation
    if PREREG_DOC.exists():
        wrong = ["--out", out, "--prereg-commit", "abc1234", "--prereg-blob", "0" * 40]
        assert _main(wrong, fr) == 2                                                   # a changed prereg
    attested = both + ["--git-head", "b" * 40, "--git-clean"]
    assert _main(attested, fr, git={"head": None, "porcelain_empty": None}) == 0
    art = json.loads(Path(out).read_text())
    assert art["git"]["head"] == "b" * 40 and art["git"]["porcelain_empty"] is True


def test_NEG_a_smoke_or_count_only_run_never_writes_the_real_artifact_path():
    real = str(S.DEFAULT_OUT)
    assert _main(["--limit", "5", "--out", real], _universe()) == 2
    assert _main(["--count-only", "--out", real], _universe()) == 2
    assert S.DEFAULT_OUT.name == "doji_sweep_measured.json"


def test_NEG_a_count_only_artifact_holds_no_outcome_key(tmp_path):
    out = tmp_path / "c.json"
    assert _main(["--count-only", "--out", str(out)], _universe()) == 0
    txt = out.read_text()
    art = json.loads(txt)
    assert art["count_only"] is True and art["smoke"] is False and art["baselines"] is None
    assert set(art) == set(DSM.ARTIFACT_KEYS)
    assert set(art["cells"]) == set(S.CELLS)
    for k, c in art["cells"].items():
        assert set(c) == set(DSM.COUNT_CELL_KEYS), k
    for word in ("median_diff_pp", "event_median_pct", "ci_block", "confirm_pct", "stop_pct", "p_holm"):
        assert word not in txt, word
    assert art["cells"]["primary"]["n_events"] >= 1
    smoke = tmp_path / "s.json"
    assert _main(["--limit", "3", "--out", str(smoke)], _universe()) == 0
    s = json.loads(smoke.read_text())
    assert s["smoke"] is True and s["count_only"] is True and s["universe_n"] == 3


# --------------------------------------------------------------------------
# the full artifact's schema (+ B4 / B6 / B12)
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def full_art(tmp_path_factory):
    out = tmp_path_factory.mktemp("dj") / "a.json"
    fr = _universe()
    rc = S.main(["--prereg-commit", "abc1234", "--prereg-blob", _blob(), "--out", str(out), "--draws", "40"],
                now=NOW, universe_fn=lambda: [s for s in fr if s != "SPY"],
                frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr},
                history_fn=lambda syms: {}, listing_fn=lambda syms: {}, block=False,
                git_fn=lambda: dict(GOOD_GIT), pin_prereg=False)
    assert rc == 0
    txt = out.read_text()
    return json.loads(txt), txt


def test_the_full_artifact_schema(full_art):
    art, txt = full_art
    assert set(art) == set(DSM.ARTIFACT_KEYS) and art["schema"] == DSM.SCHEMA_VERSION
    assert set(art["cells"]) == set(S.CELLS) and art["primary"] == art["cells"]["primary"]
    for k, c in art["cells"].items():
        assert set(c) == set(DSM.CELL_KEYS), k
        assert set(c["by_horizon"]) == {"5", "10", "20"}, k
        for hb in c["by_horizon"].values():
            assert set(hb) == set(DSM.HORIZON_KEYS)
        if c["event_mean_pct"] is not None:
            assert c["net_mean_pct"] == pytest.approx(round(c["event_mean_pct"] - S.COST_ROUND_TRIP_PCT, 2),
                                                      abs=0.011)
    assert set(art["baselines"]["all_days"]) == {"w52", "ath", "mas", "any"}
    for b in art["baselines"]["all_days"].values():
        assert set(b) == set(DSM.BASELINE_KEYS)
    assert set(art["git"]) == set(DSM.GIT_KEYS) and art["git"]["source"] == "measured"   # fix round 2
    for k, c in art["cells"].items():                                                   # fix round 2: served counts
        assert c["n_detected"] >= c["n_events"] and c["n_unmatched"] <= c["n_detected"], k
        assert c["n_blocks"] <= c["n_dates"], k
    assert art["git"]["script_blob"] == S.git_blob_sha(SCRIPT_PATH)
    assert art["git"]["detector_blob"] == S.git_blob_sha(BACKEND / "chart_maps" / "doji_sweep_tab.py")
    assert art["git"]["measured_blob"] == S.git_blob_sha(BACKEND / "chart_maps" / "doji_sweep_measured.py")
    assert art["git"]["prereg_blob"] == art["prereg_blob"] == _blob()
    assert set(art["phase_sec"]) == set(S.PHASES)
    assert art["provider_calls"] == 0 and art["smoke"] is False and art["count_only"] is False
    json.dumps(art, allow_nan=False)
    assert "NaN" not in txt and "Infinity" not in txt
    assert any("survivors-only" in s for s in art["limits"])
    assert art["n_names_with_bars"] == 6 and art["n_names_eligible"] == 5     # ZQF holds 200 bars


def test_B6_exactly_three_verdict_cells_and_w52_70_never_a_verdict_word(full_art):
    art, _ = full_art
    with_v = {k for k, c in art["cells"].items() if c["verdict"] is not None}
    assert with_v == set(DSM.VERDICT_CELLS)
    for k, c in art["cells"].items():
        assert c["role"] == (DSM.ROLE_VERDICT if k in DSM.VERDICT_CELLS else DSM.EXPLORATORY_LABEL), k
        if k not in DSM.VERDICT_CELLS:
            assert c["p_holm"] is None and c["ci_pct"] == S.CI_PCT
        else:
            assert c["verdict"] in DSM.VERDICTS
    assert art["cells"]["w52_70"]["verdict"] is None                                    # B4


def test_the_literal_round_trips_through_the_tabs_served_line(full_art, monkeypatch):
    art, _ = full_art
    lit = S.measured_literal(art)
    assert tuple(lit) == DSM.LITERAL_TOP_KEYS and lit["status"] == "measured"
    assert set(lit["primary"]) == set(DSM.LITERAL_PRIMARY_KEYS)
    for k in DSM.SERVED_CELLS:
        assert set(lit["cells"][k]) == set(DSM.literal_cell_keys(k)), k
    assert lit["cost_round_trip_pct"] == S.COST_ROUND_TRIP_PCT and lit["block_sessions"] == DSM.BLOCK_SESSIONS
    monkeypatch.setattr(DSM, "MEASURED", lit)
    blk = DJ.study_block()
    assert blk["status"] == "measured" and "MEASURED" in blk["text"] and "survivors-only" in blk["text"]
    for w in FORBIDDEN_WORDS:
        assert w not in blk["text"].lower(), w


def test_measured_literal_pins_the_artifact_field_for_field():
    art_path = BACKEND / "scripts" / "doji_sweep_measured.json"
    m = DSM.MEASURED
    if m.get("status") != "measured":
        assert m == {"state": "unmeasured"}
        if art_path.exists():
            art = json.loads(art_path.read_text())
            assert art.get("smoke") is True or art.get("count_only") is True or not art.get("prereg_commit"), (
                "a real artifact exists but MEASURED is still the placeholder — paste the literal")
        assert DJ.study_block()["status"] == "unmeasured"
        return
    art = json.loads(art_path.read_text())
    assert m == S.measured_literal(art)
    assert art["smoke"] is False and art["count_only"] is False and art["prereg_commit"]
    assert S.pin_violations(art) == []                                   # final-critic fix 2026-10-16
    assert art["definitions"]["seed"] == S.SEED_DEFAULT and art["definitions"]["draws"] == S.DRAWS_DEFAULT
    assert art["as_of"] in S.as_of_cuts(art["run_date"])
    assert art["git"]["porcelain_empty"] is True and art["provider_calls"] == 0
    if not PREREG_DOC.exists():
        pytest.skip("docs/ not mounted — run the D12 recipe")
    assert S.git_blob_sha(PREREG_DOC) == art["prereg_blob"]


def test_git_blob_sha_equals_git_hash_object(tmp_path):
    p = tmp_path / "h.txt"
    p.write_bytes(b"hello\n")
    assert S.git_blob_sha(p) == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_the_prereg_is_on_disk_and_says_it_was_not_run():
    if not PREREG_DOC.exists():
        pytest.skip("docs/ not mounted — run the D12 recipe")
    txt = PREREG_DOC.read_text(encoding="utf-8")
    assert "**Status: PRE-REGISTERED, NOT RUN.**" in txt
    assert "I heard but do some research and back test please on accuracy" in txt
    for name in ("PRIMARY_H", "CONFIRM_SESSIONS", "PLACEBO_K", "DRAWS_DEFAULT", "SEED_DEFAULT",
                 "MIN_CELL_EVENTS", "BLOCK_SESSIONS", "COST_ROUND_TRIP_PCT"):
        assert name in txt, name
    for k in DSM.VERDICT_CELLS:
        assert f"`{k}`" in txt, k
    assert not _BWORD.search(txt)


# --------------------------------------------------------------------------
# constants + words
# --------------------------------------------------------------------------
def test_constants_are_imported_never_retyped():
    assert S.MIN_CELL_DATES == MIN_BUCKET_N and S.MIN_CELL_EVENTS == DSM.MIN_CELL_EVENTS
    assert S.LIQ_FLOOR_USD == BOARD.LIQ_TIERS["ok"] and S.CI_PCT == S.RS.CI_PCT
    assert S.BLOCK_SESSIONS == DSM.BLOCK_SESSIONS and S.PLACEBO_GAP == max(S.HORIZONS)
    assert (S.SCRIPT, S.PREREG) == (DJ.SCRIPT_PATH, DJ.PREREG_PATH)
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    for name in ("HORIZONS", "PRIMARY_H", "CONFIRM_SESSIONS", "PLACEBO_K", "DRAWS_DEFAULT", "SEED_DEFAULT",
                 "COOLDOWN", "COST_ROUND_TRIP_PCT", "OUTCOME_START"):
        line = next(l for l in src.splitlines() if l.startswith(name + " ="))
        assert "# MINE (BUILD_SPEC6" in line, line


def test_NEG_the_script_never_assigns_a_tab_constant():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    mine = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        mine.add(n.id)
    tab = {k for k in vars(DJ) if k.isupper()}
    assert not (mine & tab), sorted(mine & tab)


_TAGS = re.compile(r"MINE|TRANSPORT|derived|imported|Cheetah default|Ajay 2026-10-16")


def test_every_module_number_carries_a_provenance_tag():
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    comments: dict = {}
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            comments[tok.start[0]] = tok.string
    for node in ast.parse(src).body:
        if not isinstance(node, ast.Assign):
            continue
        nums = [n for n in ast.walk(node.value) if isinstance(n, ast.Constant)
                and isinstance(n.value, (int, float)) and not isinstance(n.value, bool)]
        if not nums:
            continue
        txt = " ".join(comments.get(i, "") for i in range(node.lineno, node.end_lineno + 1))
        assert _TAGS.search(txt), (node.lineno, ast.get_source_segment(src, node)[:80])


def test_NEG_no_b_word_and_no_forecast_word_in_the_script():
    raw = SCRIPT_PATH.read_text(encoding="utf-8")
    assert not _BWORD.search(raw)
    words = " ".join(n.value for n in ast.walk(ast.parse(raw))
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)).lower()
    for w in FORBIDDEN_WORDS:
        assert w not in words, w
    assert not _BWORD.search(Path(__file__).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# fix round 1 (2026-10-16, the WP-S critic)
# --------------------------------------------------------------------------
_NAN = float("nan")


def _probe_events():
    """The critic's probe: 100 detected events, 40 with no R_10 (the last
    sessions before as-of), 20 of those also unmatched; a strong effect on the
    60 measurable ones, on 40 dates over 35 names."""
    rng = np.random.default_rng(3)
    out = []
    for i in range(100):
        d = i % 40
        ev = _oc(float(rng.normal(0, 2)) + 3.0) if i < 60 else _oc(_NAN, confirm=None)
        pls = [_oc(float(rng.normal(0, 2))) for _ in range(5)] if i < 80 else []
        out.append({"sym": f"S{i % 35}", "date": f"D{d:04d}", "pos": d, "ev": ev, "pls": pls, "short": False})
    return out


def test_NEG_100_detected_with_60_measurable_reads_too_small(monkeypatch):
    ev = _probe_events()
    b = S.cell_block("primary", ev, draws=500, seed=S.SEED_DEFAULT, count_only=False)
    assert b["verdict"] == "too_small"
    assert b["n_events"] == 60 and b["n_detected"] == 100
    assert b["n_dates"] == len({e["date"] for e in ev[:60]}) and b["n_symbols"] == len({e["sym"] for e in ev[:60]})
    assert b["n_blocks"] == len({e["pos"] // S.BLOCK_SESSIONS for e in ev[:60]})
    cc = S.contrast_counts(ev)
    assert cc["n_events"] == 60 and S.cell_too_small(cc)
    # POSITIVE: the same 60 measurable events copied up to 120 clear the gate
    big = [dict(e, date=f"E{i:04d}", pos=40 + i, sym=f"T{i % 40}") for i, e in enumerate(ev[:60] * 2)]
    assert not S.cell_too_small(S.contrast_counts(big))


def test_NEG_an_event_whose_placebos_are_all_nan_is_out_of_the_contrast():
    ev = _events(n_events=101, n_dates=40, n_syms=40)
    ev[0]["pls"] = [_oc(_NAN) for _ in range(5)]
    ev[1]["ev"] = _oc(_NAN)
    cc = S.contrast_counts(ev)
    assert cc["n_events"] == 99 and cc["n_detected"] == 101
    assert {id(e) for e in S.contrast_events(ev)} == {id(e) for e in ev[2:]}
    assert S.cell_block("any_read", ev, draws=50, seed=1, count_only=False)["verdict"] == "too_small"


def test_NEG_the_name_axis_reads_its_own_cluster_count():
    assert S.axes_verdict(200, 60, MIN_BUCKET_N - 1, [0.5, 1.0], [0.2, 0.9]) == "too_small"
    assert S.axes_verdict(200, 60, MIN_BUCKET_N, [0.5, 1.0], [0.2, 0.9]) == "separates"
    assert S.axes_verdict(200, MIN_BUCKET_N - 1, 50, [0.5, 1.0], [0.2, 0.9]) == "too_small"
    b = S.cell_block("primary", _events(n_events=300, n_dates=100, n_syms=25, effect=3.0), draws=200, seed=1,
                     count_only=False)
    assert b["verdict"] == "too_small" and b["n_symbols"] == 25 and b["n_dates"] == 100


def _falling(seed):
    return _arrays(_frame(seed, drift=-0.005, plants=()))


@pytest.mark.parametrize("key", S.OWN_POOL_CELLS)
def test_NEG_B1_an_own_pool_cells_pool_never_holds_its_own_events_or_the_20_after(key):
    held_without = 0
    checked = 0
    for seed in range(6):
        a = _falling(seed)
        m = S.cell_masks(a)
        a["own"] = S.own_masks(m)
        own = m[key]
        after = S.after_fire_mask(own)
        for t in np.flatnonzero(own):
            for ff in (True, False):
                pool = S.cell_pool(a, key, int(t), floor=ff)
                assert not own[pool].any(), (seed, t)
                assert not after[pool].any(), (seed, t)
                checked += 1
                bare = S.placebo_pool(a, int(t), floor=ff)
                held_without += int((own[bare] | after[bare]).any())
    if key == "test_no_doji":
        assert checked and held_without        # the fire-based pool alone DID hold them (the defect)


def test_every_other_cell_is_a_subset_of_the_10pct_fires():
    for seed in range(6):
        for a in (_falling(seed), _arrays(_frame(seed))):
            m = S.cell_masks(a)
            for k in S.CELLS:
                if k not in S.OWN_POOL_CELLS and k not in S.FIRE_POOL_SENSITIVITY:
                    assert not (m[k] & ~a["fired10"]).any(), (seed, k)


def test_own_pool_draws_are_keyed_by_the_cell():
    assert S.pool_key("primary", 2, 300, True) == S.pool_key("any_read", 2, 300, True) == (2, 300, True, None)
    assert S.pool_key("test_no_doji", 2, 300, True) == (2, 300, True, "test_no_doji")
    assert S.pool_key("test_no_doji", 2, 300, True) != S.pool_key("doji_no_test", 2, 300, True)
    pool = np.arange(50, 120)
    base = S.draw_placebos(pool, rng=S.placebo_rng(S.SEED_DEFAULT, 2, 300, True))
    same = S.draw_placebos(pool, rng=S.placebo_rng(S.SEED_DEFAULT, 2, 300, True, cell="primary"))
    own = S.draw_placebos(pool, rng=S.placebo_rng(S.SEED_DEFAULT, 2, 300, True, cell="test_no_doji"))
    assert np.array_equal(base, same) and not np.array_equal(base, own)


def test_the_run_draws_own_pools_and_gates_p_on_the_contrast_counts(monkeypatch, tmp_path):
    real_pool, real_counts = S.cell_pool, S.contrast_counts
    seen, p_calls = [], []

    def spy_pool(a, key, t, *, floor):
        pool = real_pool(a, key, t, floor=floor)
        if key in S.OWN_POOL_CELLS:
            own = a["own"][key]
            seen.append(bool((own[pool] | S.after_fire_mask(own)[pool]).any()))
        return pool

    def zero_counts(events):
        return {**real_counts(events), "n_events": 0}

    monkeypatch.setattr(S, "cell_pool", spy_pool)
    monkeypatch.setattr(S, "contrast_counts", zero_counts)
    monkeypatch.setattr(S, "cell_pvalue", lambda *a, **k: p_calls.append(1) or 0.01)
    fr = {"ZQA": _frame(0), "ZQB": _frame(1, drift=-0.006), "SPY": _spy()}
    out = tmp_path / "a.json"
    assert _main(["--prereg-commit", "abc1234", "--prereg-blob", _blob(), "--out", str(out), "--draws", "20"],
                 fr) == 0
    assert seen and not any(seen)              # every own-cell pool the run drew from excluded its own events
    assert p_calls == []                       # NEG: a cell under the gate on its contrast counts gets no p
    art = json.loads(out.read_text())
    for k in DSM.VERDICT_CELLS:
        assert art["cells"][k]["verdict"] == "too_small" and art["cells"][k]["p_holm"] is None, k


def test_NEG_an_outcome_run_refuses_without_the_prereg_on_disk(monkeypatch, tmp_path):
    fr = _universe()
    monkeypatch.setattr(S, "prereg_file", lambda: tmp_path / "missing.md")
    argv = ["--out", str(tmp_path / "a.json"), "--prereg-commit", "abc1234", "--prereg-blob", "f" * 40,
            "--draws", "20"]
    assert _main(argv, fr) == 2 and not (tmp_path / "a.json").exists()
    assert _main(["--count-only", "--out", str(tmp_path / "c.json")], fr) == 0     # counts need no prereg


def test_git_source_is_measured_or_attested(monkeypatch, tmp_path):
    if not PREREG_DOC.exists():
        pytest.skip("docs/ not mounted — run the D12 recipe")
    fr = {"ZQA": _frame(0), "SPY": _spy()}
    base = ["--prereg-commit", "abc1234", "--prereg-blob", _blob(), "--draws", "20"]
    out1, out2 = tmp_path / "m.json", tmp_path / "t.json"
    assert _main(base + ["--out", str(out1)], fr) == 0
    assert json.loads(out1.read_text())["git"]["source"] == "measured"
    assert _main(base + ["--out", str(out2), "--git-head", "b" * 40, "--git-clean"], fr,
                 git={"head": None, "porcelain_empty": None}) == 0
    assert json.loads(out2.read_text())["git"]["source"] == "attested"


# --------------------------------------------------------------------------
# fix round 2 (2026-10-16, the WP-S critic)
# --------------------------------------------------------------------------
def test_n_detected_and_n_blocks_and_git_source_are_in_the_schema():
    assert {"n_detected", "n_blocks"} <= set(DSM.CELL_KEYS) & set(DSM.LITERAL_PRIMARY_KEYS)
    assert "source" in DSM.GIT_KEYS
    assert not ({"n_detected", "n_blocks"} & set(DSM.COUNT_CELL_KEYS))    # NEG: a count-only cell stays bare


def test_the_literal_carries_the_counts_behind_the_verdict(full_art):
    art, _ = full_art
    lit = S.measured_literal(art)
    for k in ("n_detected", "n_blocks", "n_unmatched", "placebo_short_pool"):
        assert lit["primary"][k] == art["primary"][k], k


def test_the_fire_pool_sensitivity_reads_the_controls_events_against_the_primarys_pool():
    assert S.FIRE_POOL_SENSITIVITY == {"test_no_doji_fire_pool": "test_no_doji"}
    assert S.CELLS[-1] == "test_no_doji_fire_pool"                       # appended: no earlier seed moved
    assert "test_no_doji_fire_pool" not in S.OWN_POOL_CELLS
    assert "test_no_doji_fire_pool" not in DSM.VERDICT_CELLS + DSM.SERVED_CELLS
    assert S.pool_key("test_no_doji_fire_pool", 2, 300, True) == (2, 300, True, None)
    held = 0
    for seed in range(6):
        a = _falling(seed)
        m = S.cell_masks(a)
        a["own"] = S.own_masks(m)
        assert np.array_equal(m["test_no_doji_fire_pool"], m["test_no_doji"]), seed
        own = m["test_no_doji"]
        for t in np.flatnonzero(own):
            sens = S.cell_pool(a, "test_no_doji_fire_pool", int(t), floor=True)
            assert np.array_equal(sens, S.placebo_pool(a, int(t), floor=True))          # the primary's rule
            ctrl = S.cell_pool(a, "test_no_doji", int(t), floor=True)
            assert set(ctrl.tolist()) <= set(sens.tolist())                           # the control's is a subset
            held += int((own[sens] | S.after_fire_mask(own)[sens]).any())
    assert held        # NEG: the sensitivity pool DOES hold control days (it is not the control's own-pool rule)


def test_NEG_the_sensitivity_cell_is_exploratory_never_a_verdict(full_art):
    art, _ = full_art
    c, ctrl = art["cells"]["test_no_doji_fire_pool"], art["cells"]["test_no_doji"]
    assert c["verdict"] is None and c["role"] == DSM.EXPLORATORY_LABEL and c["p_holm"] is None
    assert c["n_detected"] == ctrl["n_detected"]
    assert c["n_unmatched"] <= ctrl["n_unmatched"]        # the wider pool never leaves more events unmatched


def _old_cache(tmp_path, name, syms, days=400):
    import os
    f = tmp_path / f"{name}.txt"
    f.write_text("\n".join(syms))
    old = f.stat().st_mtime - days * 86400
    os.utime(f, (old, old))
    return f


def test_the_universe_guard_reads_a_stale_cache_and_never_fetches(monkeypatch, tmp_path):
    from sepa import universe as UNIV
    _guard_patches(monkeypatch)
    monkeypatch.setattr(UNIV, "UNIV_CACHE_DIR", tmp_path)
    _old_cache(tmp_path, "sp500", ["ZQA", "ZQB", "ZQC"])
    assert UNIV._read_cached("sp500") is None              # NEG: past the 30-day TTL the app would refetch
    S.block_fetches()
    assert UNIV._read_cached("sp500") == ["ZQA", "ZQB", "ZQC"]
    assert UNIV.fetch_sp500() == ["ZQA", "ZQB", "ZQC"]
    assert S.FETCH_CALLS == [] and (tmp_path / "sp500.txt").read_text() == "ZQA\nZQB\nZQC"


def test_NEG_a_missing_universe_list_is_a_counted_provider_call_and_writes_no_cache(monkeypatch, tmp_path):
    from sepa import universe as UNIV
    _guard_patches(monkeypatch)
    monkeypatch.setattr(UNIV, "UNIV_CACHE_DIR", tmp_path)
    S.block_fetches()
    for name in S.UNIVERSE_NO_FETCH_FUNCS:
        assert hasattr(UNIV, name), name
    with pytest.raises(S.NoFetchError):
        UNIV._fetch_text("https://example.invalid/")
    with pytest.raises(S.NoFetchError):
        UNIV._write_cached("sp400", ["ZQA"])
    S.FETCH_CALLS.clear()
    UNIV.fetch_sp400()                                     # no cache file: the ladder tries the network
    assert "universe._fetch_text" in S.FETCH_CALLS
    assert list(tmp_path.iterdir()) == []                  # nothing written to the shared cache dir


def test_NEG_a_run_whose_universe_step_tries_the_network_exits_3(monkeypatch, tmp_path):
    from sepa import universe as UNIV
    _guard_patches(monkeypatch)
    monkeypatch.setattr(UNIV, "UNIV_CACHE_DIR", tmp_path)
    fr = _universe()

    def universe_via_sepa():
        UNIV.fetch_sp400()
        return [s for s in fr if s != "SPY"]
    out = tmp_path / "c.json"
    rc = S.main(["--count-only", "--out", str(out)], now=NOW, universe_fn=universe_via_sepa,
                frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr}, history_fn=lambda syms: {},
                listing_fn=lambda syms: {}, block=True, git_fn=lambda: dict(GOOD_GIT))
    assert rc == 3 and not out.exists()


def test_the_prereg_settles_the_block_floor_and_words_the_control_as_numbers_only():
    if not PREREG_DOC.exists():
        pytest.skip("docs/ not mounted — run the D12 recipe")
    txt = PREREG_DOC.read_text(encoding="utf-8")
    assert "No block-count floor" in txt and "`n_blocks`" in txt and "`n_detected`" in txt
    assert "HIS CALL**, settled before" not in txt                    # NEG: no rule left open
    assert "the test of the low alone carries it, not the doji" not in txt   # NEG: the invalid inference
    assert "`test_no_doji_fire_pool`" in txt and "unmatched share" in txt
    assert "/docs/research:ro" in txt and "`source`" in txt


# --------------------------------------------------------------------------
# final-critic fix (2026-10-16): the pre-registration is pinned
# --------------------------------------------------------------------------
@pytest.mark.parametrize("extra,word", [(["--seed", "1"], "--seed"), (["--draws", "20"], "--draws"),
                                        (["--as-of", LAST], "--as-of")])
def test_NEG_an_outcome_run_refuses_a_free_seed_draws_or_as_of(extra, word, tmp_path, capsys):
    out = tmp_path / "a.json"
    argv = ["--out", str(out), "--prereg-commit", "abc1234", "--prereg-blob", _blob()] + extra
    assert _main(argv, _universe(), pin=True) == 2 and not out.exists()
    err = capsys.readouterr().err
    assert "pre-registration pin" in err and word in err


def test_the_pin_leaves_counts_free_and_defaults_pass_it(monkeypatch, tmp_path, capsys):
    fr = _universe()
    c = tmp_path / "c.json"
    assert _main(["--count-only", "--draws", "20", "--seed", "1", "--as-of", LAST, "--out", str(c)], fr,
                 pin=True) == 0                                   # counts read no outcome — nothing to steer
    capsys.readouterr()
    monkeypatch.setattr(S, "prereg_file", lambda: tmp_path / "missing.md")
    argv = ["--out", str(tmp_path / "a.json"), "--prereg-commit", "abc1234", "--prereg-blob", "f" * 40]
    assert _main(argv, fr, pin=True) == 2                         # the defaults pass the pin, stop at the prereg
    err = capsys.readouterr().err
    assert "pre-registration pin" not in err and "not on disk" in err
    assert S.outcome_pin_refusal(S.parse_args([])) is None


def test_NEG_an_outcome_run_refuses_a_cache_behind_the_tabs_last_closed_session(tmp_path, capsys):
    if not PREREG_DOC.exists():
        pytest.skip("docs/ not mounted — run the D12 recipe")
    out = tmp_path / "a.json"
    later = datetime(2026, 10, 15, 22, 0, tzinfo=ET)              # cut 10-15; the fixture cache ends 10-14
    argv = ["--out", str(out), "--prereg-commit", "abc1234", "--prereg-blob", _blob()]
    assert _main(argv, _universe(), now=later, pin=True) == 2 and not out.exists()
    assert "cache ends 2026-10-14" in capsys.readouterr().err


def test_as_of_cuts_bracket_the_roll():
    assert S.as_of_cuts("2026-10-14") == {"2026-10-13", "2026-10-14"}     # before / after the 20:00 roll
    assert S.as_of_cuts("2026-10-17") == {"2026-10-16"}                   # a Saturday: Friday either way
    assert S.as_of_cut(NOW) == LAST


def test_NEG_pin_violations_flag_every_steerable_knob(full_art):
    art, _ = full_art
    assert any("draws" in v for v in S.pin_violations(art))       # the fixture ran 40 draws — never pasteable
    ok = json.loads(json.dumps(art))
    ok["definitions"]["draws"] = S.DRAWS_DEFAULT
    assert S.pin_violations(ok) == []
    for path, val, word in ((("definitions", "seed"), 1, "seed"), (("as_of",), "2026-10-09", "as_of"),
                            (("git", "porcelain_empty"), None, "clean"), (("provider_calls",), 1, "provider"),
                            (("smoke",), True, "smoke"), (("prereg_blob",), None, "prereg"),
                            (("git", "head"), None, "clean")):
        bad = json.loads(json.dumps(ok))
        tgt = bad
        for k in path[:-1]:
            tgt = tgt[k]
        tgt[path[-1]] = val
        v = S.pin_violations(bad)
        assert v and any(word in x for x in v), (path, v)
    assert S.pin_violations({})                                    # NEG: an empty artifact is never pasteable
