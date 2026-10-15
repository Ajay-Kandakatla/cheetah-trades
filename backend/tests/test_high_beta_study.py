"""🎢 High Beta down-day study (scripts/high_beta_study.py) — the engines it
reuses, the two-way bootstrap, the leak rule, the clock, the read-only guard,
a synthetic null (never separates) and a planted reversal (separates), and the
served literal pinned field-for-field to the artifact.

Pre-registration: docs/research/high_beta_2026_10_14_prereg.md. NOT RUN here —
every frame below is synthetic.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from chart_maps import high_beta_measured as HBM
from chart_maps import high_beta_tab as HB
from chart_maps import resiliency_tab as RES
from scripts import high_beta_study as S
from sepa import beta as BETA

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
DRAWS = 200


def _days(end: str, n: int) -> pd.DatetimeIndex:
    from market_hours.reminder import ALL_HOLIDAYS
    out, d = [], pd.Timestamp(end)
    while len(out) < n:
        if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in ALL_HOLIDAYS:
            out.append(d)
        d -= pd.Timedelta(days=1)
    return pd.DatetimeIndex(sorted(out))


def _fr(close, idx):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99,
                         "close": close, "volume": 1e6}, index=idx)


def _universe(*, n_names=120, n_bars=340, seed=1, planted=0.0):
    """iid returns: r = β × SPY + noise, β loadings 1.8..3.0. `planted` adds
    planted/3 to each of the 3 sessions after a close of −cut% or worse."""
    rng = np.random.default_rng(seed)
    idx = _days("2026-09-30", n_bars)
    spy = rng.normal(0.0003, 0.01, n_bars)
    frames = {"SPY": _fr(100 * np.exp(np.cumsum(np.log1p(spy))), idx)}
    for i in range(n_names):
        b = 1.8 + 1.2 * i / max(n_names - 1, 1)
        r = b * spy + rng.normal(0, 0.03, n_bars)
        if planted:
            for t in range(n_bars - 3):
                if r[t] <= -S.CUT / 100.0:
                    r[t + 1:t + 4] += planted / 3.0
        frames[f"N{i:03d}"] = _fr(100 * np.exp(np.cumsum(np.log1p(r))), idx)
    return frames


AS_OF = "2026-09-30"


# ---------------------------------------------------------------------------
# the engines it reuses
# ---------------------------------------------------------------------------
def test_rolling_beta_is_the_house_beta_on_a_gap_free_name():
    fr = _universe(n_names=3, seed=4)
    days = sorted(RES.closes_by_day(fr["SPY"]))
    spy_c = S.RS.aligned(fr["SPY"], days)["close"]
    spy_lr = np.log(spy_c / np.concatenate([[np.nan], spy_c[:-1]]))
    s = S.series_for(S.RS.aligned(fr["N001"], days), spy_lr)
    fe = len(days) - 1
    want = BETA._beta(BETA._log_returns(fr["N001"]), BETA._log_returns(fr["SPY"]))
    assert abs(s["beta"][fe] - want) < 1e-9
    assert round(float(s["beta"][fe]), 2) == BETA.beta_from_frame(fr["N001"], BETA.log_returns(fr["SPY"]))
    sg = RES.sigma_pct(RES.closes_by_day(fr["N001"]), days)
    assert round(float(s["sigma"][fe]), 2) == sg


def test_NEG_a_hole_inside_the_window_is_no_beta_and_no_sigma():
    fr = _universe(n_names=1, seed=5)
    days = sorted(RES.closes_by_day(fr["SPY"]))
    holed = fr["N000"].drop(fr["N000"].index[-10])
    spy_c = S.RS.aligned(fr["SPY"], days)["close"]
    spy_lr = np.log(spy_c / np.concatenate([[np.nan], spy_c[:-1]]))
    s = S.series_for(S.RS.aligned(holed, days), spy_lr)
    assert np.isnan(s["beta"][len(days) - 1]) and np.isnan(s["sigma"][len(days) - 1])
    assert np.isfinite(s["beta"][len(days) - 12])                 # a window ending before the hole


def test_NEG_an_outcome_with_a_missing_bar_is_dropped():
    s = {"close": np.array([10.0, 11.0, np.nan, 12.0]), "high": np.ones(4) * 13,
         "low": np.ones(4) * 9}
    assert S.outcome(s, 0, 1)[0] == pytest.approx(10.0)
    assert S.outcome(s, 0, 3) == (None, None, None)


# ---------------------------------------------------------------------------
# the leak rule
# ---------------------------------------------------------------------------
def test_windows_never_reach_the_cohort_day():
    for d in (253, 300):
        assert max(S.feature_window(d, S.BETA_LOOKBACK)) == d - 1
        assert min(S.outcome_window(d, 3)) == d + 1
        S.check_no_leak(d, S.feature_window(d, S.BETA_LOOKBACK), S.outcome_window(d, 5))


def test_NEG_a_mutated_feature_window_is_caught(monkeypatch):
    monkeypatch.setattr(S, "FEATURE_END_OFFSET", 0)
    with pytest.raises(S.LeakError):
        S.build_rows(_universe(n_names=3), as_of=AS_OF)
    with pytest.raises(S.LeakError):
        S.check_no_leak(10, [9], [10])


# ---------------------------------------------------------------------------
# the two-way bootstrap
# ---------------------------------------------------------------------------
def test_weights_are_blocks_times_symbols_and_reproducible():
    ws, wy = S.weights(23, 7, 50, 3)
    assert ws.shape == (50, 23) and wy.shape == (50, 7)
    assert (ws.sum(axis=1) == 23).all() and (wy.sum(axis=1) == 7).all()
    ws2, wy2 = S.weights(23, 7, 50, 3)
    assert (ws == ws2).all() and (wy == wy2).all()
    # moving blocks: every drawn session sits in a run of BLOCK_LEN consecutive ones
    starts = np.flatnonzero(np.diff(np.concatenate([[0], (ws[0] > 0).astype(int), [0]])) == 1)
    ends = np.flatnonzero(np.diff(np.concatenate([[0], (ws[0] > 0).astype(int), [0]])) == -1)
    assert all(e - s >= S.BLOCK_LEN for s, e in zip(starts, ends[:len(starts)])
               if e < 23 and s > 0)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_NEG_synthetic_null_is_no_signal(seed):
    art = S.run_study(_universe(seed=seed), as_of=AS_OF, draws=DRAWS, shuffle_draws=20)
    p = art["primary"]
    assert p["verdict"] == "no_signal", p
    assert p["n_sessions"] >= S.MIN_BUCKET_N and p["ci"][0] <= 0 <= p["ci"][1]


def test_planted_three_session_reversal_separates():
    art = S.run_study(_universe(seed=1, planted=0.02), as_of=AS_OF, draws=DRAWS, shuffle_draws=20)
    p = art["primary"]
    assert p["verdict"] == "separates" and p["contrast_pp"] > 1.0, p
    assert p["ci"][0] > 0 and p["ci_session_only"][0] > 0
    assert p["cohort_mean_pct"] > p["placebo_mean_pct"]
    assert art["leave_top5"]["n_sessions"] == p["n_sessions"] - S.LEAVE_OUT_TOP
    assert len(art["leave_top5"]["dropped"]) == S.LEAVE_OUT_TOP
    for k in ("h1", "h5", "mfe3", "mae3", "spy_red", "spy_green", "b20", "top20",
              "sigma_matched", "first_half", "second_half"):
        assert k in art, k


def test_NEG_29_sessions_is_too_small():
    art = S.run_study(_universe(seed=1, planted=0.02), as_of=AS_OF, draws=50,
                      sessions_max=S.MIN_BUCKET_N - 1, shuffle_draws=0)
    assert art["primary"]["verdict"] == "too_small"
    assert art["primary"]["n_sessions"] <= S.MIN_BUCKET_N - 1


def test_NEG_no_rows_is_too_small_and_json_safe():
    fr = _universe(n_names=2, n_bars=200)                    # no full β window
    art = S.run_study(fr, as_of=AS_OF, draws=20, shuffle_draws=0)
    assert art["primary"]["verdict"] == "too_small" and art["n_rows"] == 0
    json.dumps(art, allow_nan=False, default=str)


# ---------------------------------------------------------------------------
# the clock, the gates, the read-only guard, main + the literal
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("hh,mm", [(9, 0), (12, 0), (16, 29)])
def test_NEG_refuses_the_session_window(hh, mm, tmp_path):
    now = datetime(2026, 10, 15, hh, mm, tzinfo=ET)
    assert S.main(["--prereg-commit", "x", "--out", str(tmp_path / "a.json")], now=now,
                  universe_fn=lambda: [], frames_fn=lambda s: {}, block=False) == 2


def test_NEG_an_outcome_run_needs_a_prereg_commit_and_a_smoke_never_writes_the_real_path(tmp_path):
    now = datetime(2026, 10, 14, 22, 0, tzinfo=ET)
    assert S.main(["--out", str(tmp_path / "a.json")], now=now, universe_fn=lambda: [],
                  frames_fn=lambda s: {}, block=False) == 2
    real = str(BACKEND / "scripts" / "high_beta_measured.json")
    assert S.main(["--limit", "3", "--out", real], now=now, universe_fn=lambda: [],
                  frames_fn=lambda s: {}, block=False) == 2


def test_writes_are_recorded_no_ops(monkeypatch):
    from pymongo.collection import Collection
    for m in S.RS.WRITE_METHODS:
        if hasattr(Collection, m):
            monkeypatch.setattr(Collection, m, getattr(Collection, m))
    S.ATTEMPTED.clear()
    S.block_writes()

    class _Fake:
        name = "price_cache"
    assert Collection.insert_one(_Fake(), {"x": 1}) is None
    assert Collection.update_many(_Fake(), {}, {}) is None
    assert S.ATTEMPTED == ["price_cache.insert_one", "price_cache.update_many"]


def test_main_writes_the_artifact_and_the_literal_round_trips(tmp_path, monkeypatch, capsys):
    fr = _universe(n_names=40, seed=2)
    out = tmp_path / "high_beta_measured.json"
    now = datetime(2026, 10, 14, 22, 0, tzinfo=ET)
    rc = S.main(["--prereg-commit", "abc1234", "--out", str(out), "--draws", "40"], now=now,
                universe_fn=lambda: [s for s in fr if s != "SPY"],
                frames_fn=lambda syms: {s: fr[s] for s in syms if s in fr}, block=False)
    assert rc == 0
    art = json.loads(out.read_text())
    for k in ("study", "script", "prereg", "prereg_commit", "run_date", "as_of", "definitions",
              "primary", "spy_red", "leave_top5", "limits", "attempted_writes"):
        assert k in art, k
    assert art["as_of"] == AS_OF and art["smoke"] is False
    assert art["definitions"]["DOWN_CHIP_PCT"] == HB.DOWN_CHIP_PCT
    assert art["definitions"]["B15_MIN"] == HB.B15_MIN and art["definitions"]["BLOCK_LEN"] == 5
    assert any("survivors-only" in s for s in art["limits"])
    printed = capsys.readouterr().out
    assert "measured_literal" in printed
    lit = S.measured_literal(art)
    assert lit["status"] == "measured" and lit["cohort"] == "survivors-only"
    assert set(lit["primary"]) == set(S.PRIMARY_KEYS)
    for k in S.SECONDARY_BLOCKS:
        assert set(lit[k]) == set(S.SECONDARY_KEYS), k
    # the served line built from it: MEASURED, survivors-only, no forbidden word
    monkeypatch.setattr(HBM, "MEASURED", lit)
    blk = HB.study_block()
    assert blk["status"] == "measured" and "survivors-only cohort" in blk["text"]
    assert "MEASURED" in blk["text"] and "SPY-red days only" in blk["text"]
    for w in HB.FORBIDDEN_WORDS:
        assert w not in blk["text"].lower(), w


def test_measured_literal_pins_the_artifact_field_for_field():
    art_path = BACKEND / "scripts" / "high_beta_measured.json"
    m = HBM.MEASURED
    if m.get("status") != "measured":
        assert m == {"state": "unmeasured"}
        if art_path.exists():
            art = json.loads(art_path.read_text())
            assert art.get("smoke") is True or art.get("prereg_commit") is None, (
                "a real artifact exists but MEASURED is still the placeholder — paste the literal")
        assert HB.study_block()["status"] == "unmeasured"
        return
    art = json.loads(art_path.read_text())
    assert m == S.measured_literal(art)
    assert art["smoke"] is False and art["prereg_commit"]


def test_NEG_a_malformed_literal_never_breaks_the_served_line(monkeypatch):
    monkeypatch.setattr(HBM, "MEASURED", {"status": "measured", "primary": {"ci": None}})
    assert HB.study_block()["status"] == "unmeasured"
    monkeypatch.setattr(HBM, "MEASURED", "junk")
    assert HB.study_block()["text"] == HB.NOTE_PENDING


# ---------------------------------------------------------------------------
# import scope + words
# ---------------------------------------------------------------------------
_KL_RE = re.compile(r"^\s*(from\s+supply_demand\s+import\s+[^\n]*\bkey_levels\b"
                    r"|from\s+supply_demand\.key_levels\s+import"
                    r"|import\s+supply_demand\.key_levels)", re.M)


def test_the_script_never_imports_key_levels_and_reuses_the_named_engines():
    src = (BACKEND / "scripts" / "high_beta_study.py").read_text(encoding="utf-8")
    assert not _KL_RE.search(src)
    got = S.imported_modules()
    assert {"chart_maps.high_beta_tab", "scripts.resiliency_study",
            "scripts.explosive_study.MIN_BUCKET_N", "sepa.prices",
            "supply_demand.demand_reentry"} <= got
    for need in ("RS.verdict", "RS.ci_of", "RS.assign_cells", "RS.cell_contrast",
                 "RS.shuffle_lifts", "RS.refused_window", "RS.default_as_of", "RS.aligned",
                 "HB.categories", "HB.qqq_members", "HB.resolve_symbols"):
        assert need in src, need


def test_the_script_never_says_a_forbidden_word():
    import ast
    tree = ast.parse((BACKEND / "scripts" / "high_beta_study.py").read_text(encoding="utf-8"))
    words = " ".join(n.value for n in ast.walk(tree)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)).lower()
    for w in HB.FORBIDDEN_WORDS:
        assert w not in words, w


def test_his_numbers_are_imported_never_retyped():
    assert (S.B15, S.B20, S.TOP_PCT, S.CUT) == (HB.B15_MIN, HB.B20_MIN, HB.TOP_PCT,
                                                HB.DOWN_CHIP_PCT)
    assert S.SIGMA_BARS == HB.SIGMA_BARS and S.BETA_LOOKBACK == BETA.BETA_LOOKBACK
    src = (BACKEND / "scripts" / "high_beta_study.py").read_text(encoding="utf-8")
    for name in ("SESSIONS_MAX", "DRAWS_DEFAULT", "SEED_DEFAULT", "HORIZONS", "BLOCK_LEN",
                 "LEAVE_OUT_TOP"):
        line = next(l for l in src.splitlines() if l.startswith(name + " ="))
        assert "# MINE (AMENDMENTS §8" in line, line
