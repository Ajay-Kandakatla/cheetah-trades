"""🕯️ Doji Sweep tab — the engine, the board read, the words, the measured stub
(BUILD_SPEC6 §3.1-§3.6, WP-A; AMENDMENTS6 B4 / B5 / B7 / B9 / B13 / B15 / B16).

Ajay 2026-10-16: "create me a new tab for Doji candle after a sweep. For any
stocks after a down trend. May be from all chart maps especially on the 60% 70%
down stocks" — and "Within 5% either side counts as a test".

Pins `chart_maps/doji_sweep_tab.py` (THE ONE ENGINE `frame_features` +
`row_statuses`, the per-name `read`, the memo, the chips / body switch / orders,
`ledger_fires`, every served word) and `chart_maps/doji_sweep_measured.py` (the
UNMEASURED placeholder and the schema). Positive AND negative cases. Hermetic:
the conftest refuses Mongo, every reader is injected, `_spawn` is patched (no
thread), no network.
"""
from __future__ import annotations

import ast
import inspect
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

from chart_maps import ath_history as AH
from chart_maps import doji_sweep_measured as DSM
from chart_maps import doji_sweep_tab as DJ
from chart_maps import fallen_tab as FAL
from chart_maps.high_beta_tab import FORBIDDEN_WORDS
from patterns import candles_daily as CD
from scalping import candles as CANDLES
from sepa import entry_exit, prices, symbols
from supply_demand import key_levels as KL
from supply_demand import patterns as SDP
from supply_demand import quick_bounce as QB

ET = ZoneInfo("America/New_York")
BACKEND = Path(__file__).resolve().parents[1]
DJ_PATH = BACKEND / "chart_maps" / "doji_sweep_tab.py"
DSM_PATH = BACKEND / "chart_maps" / "doji_sweep_measured.py"

NOW = datetime(2026, 10, 16, 21, 0, tzinfo=ET)        # Friday, after the 20:00 roll
SESSION = date(2026, 10, 19)                           # -> the next market day
LAST = "2026-10-16"
NOW_RTH = datetime(2026, 10, 16, 11, 0, tzinfo=ET)     # same Friday, mid-session
SESSION_RTH = date(2026, 10, 16)


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


def _trend(n=300, *, start=200.0, end_px=100.0, end=LAST, vol=1_000_000.0, tail=30, k=1.0):
    """A falling (start > end_px) or rising series of plain bars (body 37.5% of a
    1.6 range), the last `tail` bars flat at close 101 / low 100.5."""
    idx = pd.DatetimeIndex(_market_days(end, n))
    c = np.linspace(start, end_px, n)
    o = c + 0.6
    df = pd.DataFrame({"open": o, "high": o + 0.5, "low": c - 0.5, "close": c,
                       "volume": float(vol)}, index=idx)
    df.iloc[n - tail:, :4] = [101.6, 102.1, 100.5, 101.0]
    if k != 1.0:
        df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]] * k
    return df


def _set(df, pos: int, **kw):
    for col, v in kw.items():
        df.iloc[pos, df.columns.get_loc(col)] = v
    return df


def _doji(df, *, ref=98.0, age=8, test=1.0, body=0.02, rng=2.0, pos=0.5, at=-1, low=None):
    """The candle at `at` becomes a doji (body `body` x range) whose low sits
    `test`% from the reference low `ref`, printed `age` sessions before it."""
    _set(df, at - age, low=ref)
    lo = ref * (1 + test / 100.0) if low is None else low
    hi = lo + rng
    mid = lo + rng * pos
    o = mid - body * rng / 2.0
    _set(df, at, open=o, high=hi, low=lo, close=o + body * rng)
    return df


def _fire(**kw):
    return _doji(_trend(), **kw)


def _steep(**kw):
    """>= 65% under the 252-bar high (the w52 read)."""
    return _doji(_trend(start=400.0), **kw)


def _up(**kw):
    """Close above the 200-day, < 60% off every high (no read on its own)."""
    return _doji(_trend(start=80.0, end_px=100.0), **kw)


def _st(df, body=DJ.DOJI_BODY_PCT, ath=None):
    return DJ.row_statuses(DJ.frame_features(df), body_max=body, pct_below_ath=ath)[-1]


def _read(df, sym="AAA", *, session=SESSION, **kw):
    return DJ.read(sym, df, session=session, **kw)


def _walk(n=420, seed=7, glitch_at=None):
    rng = np.random.default_rng(seed)
    c = 50.0 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    prev = np.concatenate([[c[0]], c[:-1]])
    o = prev * (1 + rng.normal(0, 0.004, n))
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.01, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.01, n)))
    v = rng.integers(200_000, 2_000_000, n).astype(float)
    df = pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": v},
                      index=pd.DatetimeIndex(_market_days(LAST, n)))
    if glitch_at is not None:
        df.iloc[glitch_at, df.columns.get_loc("close")] = c[glitch_at] * 7.0
    return df


def _next_session(day) -> date:
    d = pd.Timestamp(day).date()
    return KL.levels_session(datetime(d.year, d.month, d.day, 21, 0, tzinfo=ET))


def _ath_doc(sym, df, *, mult=3.0, hi_month="2015-06", first_bar="2015-03-01"):
    last_month = pd.Timestamp(df.index[-1]).strftime("%Y-%m")
    mask = np.asarray([d.strftime("%Y-%m") == last_month for d in df.index])
    return {"_id": sym, "status": "ok", "curation": AH.curation_key(sym),
            "check_month": last_month, "check_high": float(df["high"][mask].max()),
            "hi": float(df["high"].max()) * mult, "hi_month": hi_month, "first_bar": first_bar,
            "fetched_at": NOW.timestamp()}


def _build(frames, *, session=SESSION, docs=None, listing=None, etfs=()):
    return DJ.build("full", session, universe_fn=lambda u: list(frames),
                    frames_fn=lambda syms: {s: frames[s] for s in syms if s in frames},
                    history_fn=lambda syms: dict(docs or {}), listing_fn=lambda syms: dict(listing or {}),
                    etf_fn=lambda: set(etfs))


@pytest.fixture(autouse=True)
def _clean_memo(monkeypatch):
    with DJ._lock:
        DJ._memo.clear()
        DJ._warming.clear()
        DJ._failures.clear()
    yield
    with DJ._lock:
        DJ._memo.clear()
        DJ._warming.clear()
        DJ._failures.clear()


# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------
def _assign_lines(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    comments: dict = {}
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            comments.setdefault(tok.start[0], []).append(tok.string.lstrip("#").strip())
    return {"src": src, "tree": ast.parse(src), "comments": comments}


def test_01_constants_imported_and_his_numbers():
    assert DJ.DOJI_BODY_PCT is CANDLES.DOJI_BODY_PCT
    assert DJ.BODY_STEPS == (5, 10)
    assert DJ.DEPTH_CHIPS == (40, 60, 70)
    assert DJ.DOWN_PCT == float(DJ.DEPTH_CHIPS[1])
    assert DJ.SWEEP_TEST_PCT == 5.0
    assert DJ.SWEEP_REF_SESSIONS == 20 and DJ.SWEEP_REF_MIN_AGE == 4
    assert DJ.VOL_HEAVY_X is CANDLES.VOL_RATIO_MIN
    assert DJ.VOL_AVG_BARS == CD.VOL_AVG_BARS
    assert DJ.ATR_BARS == 14 == inspect.signature(SDP.atr).parameters["period"].default
    assert DJ.YEAR_BARS == KL.YEAR_BARS
    assert DJ.SMALL_WICK_PCT == CD.SMALL_WICK_PCT
    assert DJ.MEMO_TTL_SEC == FAL.MEMO_TTL_SEC and DJ.FAIL_RETRY_SEC == FAL.FAIL_RETRY_SEC
    assert DJ.TAB_LABEL == "\U0001F56F️ Doji Sweep"
    from chart_maps import board as B
    assert DJ.DEFAULT_SORT == B.DEFAULT_SORT
    assert DJ.PRIMARY_READ == "w52" and DJ.READS[0] == DJ.PRIMARY_READ


def test_02_tag_comments_on_the_named_constants():
    a = _assign_lines(DJ_PATH)
    lines = a["src"].splitlines()

    def comment_of(name):
        for i, ln in enumerate(lines, 1):
            if re.match(rf"^{name}\s*=", ln):
                return " ".join(a["comments"].get(i, []))
        raise AssertionError(name)
    assert comment_of("SWEEP_TEST_PCT").startswith("Ajay 2026-10-16")
    assert comment_of("SWEEP_REF_SESSIONS").startswith("Cheetah default (")
    assert comment_of("SWEEP_REF_MIN_AGE").startswith("Cheetah default (")
    vh = comment_of("VOL_HEAVY_X")                       # AMENDMENTS6 B15
    assert vh.startswith("imported") and "borrowed from the 5-minute candle module" in vh
    assert "not a daily house line (Cheetah default, his call Q9)" in vh


_TAGS = ("Ajay 2026-10-16", "Cheetah default (", "MINE", "TRANSPORT", "derived", "imported")
_MOD_ALIASES = {"FAL", "ATH", "AH", "CANDLES", "CD", "KL", "SDP", "DMT", "prices"}


def _numeric(node) -> bool:
    return any(isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
               and not isinstance(n.value, bool) for n in ast.walk(node))


def test_03_provenance_walk_every_module_number_is_tagged():
    """§3.1 rule: every module-level assignment holding a numeric literal carries
    a tag comment; every one assigned straight from another module's attribute
    says imported / derived. NEGATIVE: a synthetic untagged line fails the walk."""
    def offenders(path_src: str) -> list:
        tree = ast.parse(path_src)
        comments: dict = {}
        for tok in tokenize.generate_tokens(io.StringIO(path_src).readline):
            if tok.type == tokenize.COMMENT:
                comments.setdefault(tok.start[0], []).append(tok.string.lstrip("#").strip())
        bad = []
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            val = node.value
            if val is None:
                continue
            cs = [c for ln in range(node.lineno, node.end_lineno + 1) for c in comments.get(ln, [])]
            if _numeric(val) and not any(c.startswith(_TAGS[:5]) for c in cs):
                bad.append(node.lineno)
            if (isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name)
                    and val.value.id in _MOD_ALIASES
                    and not any(c.startswith(("imported", "derived")) for c in cs)):
                bad.append(node.lineno)
        return bad
    src = DJ_PATH.read_text(encoding="utf-8")
    assert offenders(src) == []
    assert offenders("X = 3\n") == [1]                                   # NEGATIVE
    assert offenders("Y = FAL.MARK  # mine\n") == [1]                    # NEGATIVE


def test_04_statuses_and_counts_shape():
    assert len(set(DJ.STATUSES)) == len(DJ.STATUSES)
    assert set(DJ.ROW_STATUSES) <= set(DJ.STATUSES)
    assert set(DJ.STATUSES) <= set(DJ.COUNT_KEYS)
    assert DJ.STATUSES[-1] == "fired" and DJ.ROW_STATUSES[-1] == "fired"
    assert DJ.LEDGER_KEYS[-1] == "bucket" and len(set(DJ.LEDGER_KEYS)) == len(DJ.LEDGER_KEYS)
    assert DJ.LEDGER_BUCKETS == ("doji_sweep", "doji_sweep_10pct", "doji_sweep_thin")


# --------------------------------------------------------------------------
# source guards (NEGATIVE)
# --------------------------------------------------------------------------
_OWNED = ("SWEEP_TEST_PCT", "SWEEP_REF_SESSIONS", "SWEEP_REF_MIN_AGE", "DOJI_BODY_WIDE_PCT",
          "VOL_QUIET_X", "LONG_LEG_BARS")


def test_05_no_other_module_assigns_the_doji_thresholds():
    allowed = {DJ_PATH, DSM_PATH, BACKEND / "scripts" / "doji_sweep_study.py"}
    pat = re.compile(r"^\s*(" + "|".join(_OWNED) + r")\s*=", re.M)
    hits = []
    for p in BACKEND.rglob("*.py"):
        if p in allowed or "tests" in p.parts or ".venv" in p.parts or "node_modules" in p.parts:
            continue
        try:
            txt = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if pat.search(txt):
            hits.append(str(p))
    assert hits == []


def test_06_dj_never_names_a_fetcher_or_imports_board_at_module_level():
    src = DJ_PATH.read_text(encoding="utf-8")
    assert not re.search(r"load_prices|_fetch|bulk_snapshot|closed_daily_frame|with_today_bar|"
                         r"market_snapshot|bulk_live_prices|patch_latest_closes", src)
    tree = ast.parse(src)
    top = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            top |= {f"{node.module}.{a.name}" for a in node.names}
        elif isinstance(node, ast.Import):
            top |= {a.name for a in node.names}
    assert "chart_maps.board" not in top
    assert not any(t.startswith("scripts") for t in top)
    assert "chart_maps.doji_sweep_measured" not in top


def _strings(path: Path) -> list:
    out = []
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.append(n.value)
    return out


def test_07_no_b_word_and_no_forecast_word():
    for p in (DJ_PATH, DSM_PATH):
        raw = p.read_text(encoding="utf-8").replace("quick_bounce", "")
        assert not re.search(r"bounc", raw, re.I), p
        for s in _strings(p):
            low = s.lower()
            for w in FORBIDDEN_WORDS:
                assert w not in low, (p.name, w, s[:80])


# --------------------------------------------------------------------------
# the engine — positives
# --------------------------------------------------------------------------
def test_10_fires_on_a_doji_testing_a_20_session_low_in_a_downtrend():
    df = _fire()
    feat = DJ.frame_features(df)
    assert tuple(feat.columns) == DJ.FEATURE_COLUMNS
    last = feat.iloc[-1]
    assert _st(df) == "fired"
    assert bool(last["tested"]) and not bool(last["undercut"]) and bool(last["below_mas"])
    assert int(last["ref_age"]) == 8 and float(last["ref_low"]) == 98.0
    r = _read(df)
    assert r["status"] == "fired" and r["reads"] == ["mas"]
    assert r["test_pct"] == 1.0 and r["tested"] and not r["undercut"] and not r["reclaimed"]


def test_11_undercut_and_reclaimed():
    df = _fire(test=-2.0, rng=4.0, pos=0.75)
    r = _read(df)
    assert r["status"] == "fired"
    assert r["undercut"] and r["reclaimed"] and r["test_pct"] == -2.0
    assert r["close"] > r["ref_low"]


def test_12_undercut_closed_under_is_not_reclaimed():
    df = _fire(test=-2.0, rng=1.0, pos=0.3)
    r = _read(df)
    assert r["status"] == "fired" and r["undercut"] and not r["reclaimed"]


def test_13_deep_under_the_52_week_high_reads_w52():
    r = _read(_steep())
    assert r["status"] == "fired"
    assert "w52" in r["reads"] and r["pct_below_52w"] >= 65
    assert r["w52"]["pct_below"] == pytest.approx(r["pct_below_52w"], abs=0.006)


# --------------------------------------------------------------------------
# the engine — negatives (each its own test)
# --------------------------------------------------------------------------
def test_20_NEG_body_6pct_is_not_a_doji_at_5_but_fires_at_10():
    df = _fire(body=0.06)
    assert _st(df) == "not_doji"
    assert _st(df, body=DJ.DOJI_BODY_WIDE_PCT) == "fired"
    assert not bool(DJ.frame_features(df)["doji5"].iloc[-1])
    r = _read(df, cfg=DJ.Cfg(body_pct=DJ.DOJI_BODY_WIDE_PCT))
    assert r["status"] == "fired" and r["doji5"] is False


def test_21_NEG_body_exactly_5pct_is_not_a_doji_house_strict():
    df = _trend()
    _set(df, -9, low=95.0)
    _set(df, -1, open=98.0, close=98.25, high=100.5, low=95.5)       # 0.25 / 5.0 == 0.05 exactly
    feat = DJ.frame_features(df)
    assert feat["body_pct"].iloc[-1] == 0.05
    assert not bool(feat["doji5"].iloc[-1])
    assert CANDLES.anatomy(98.0, 100.5, 95.5, 98.25)["is_doji"] is False
    assert _st(df) == "not_doji"


def test_22_doji5_equals_anatomy_over_a_random_grid():
    rng = np.random.default_rng(11)
    n = 200
    o = rng.uniform(10, 11, n)
    body = rng.choice([0.0, 0.01, 0.03, 0.049, 0.05, 0.051, 0.08, 0.2], n)
    r = rng.uniform(0.5, 2.0, n)
    lo = o - rng.uniform(0, 1, n) * r
    h = lo + r
    c = o + body * r * rng.choice([-1, 1], n)
    c = np.clip(c, lo, h)
    h[::17] = lo[::17]                                                  # flat bars
    df = pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": 1.0},
                      index=pd.DatetimeIndex(_market_days(LAST, n)))
    feat = DJ.frame_features(df)
    for i in range(n):
        a = CANDLES.anatomy(o[i], h[i], lo[i], c[i])
        assert bool(feat["doji5"].iloc[i]) == bool(a and a["is_doji"]), i


@pytest.mark.parametrize("low,want", [(84.0, "fired"), (84.008, "no_test"),
                                      (76.0, "fired"), (75.992, "no_test")])
def test_23_NEG_the_5pct_test_boundary_both_sides(low, want):
    df = _doji(_trend(), ref=80.0, low=low)
    feat = DJ.frame_features(df)
    assert _st(df) == want
    assert bool(feat["tested"].iloc[-1]) is (want == "fired")
    if low < 80.0 and want == "fired":
        assert bool(feat["undercut"].iloc[-1])


def test_24_NEG_float_boundary_rounds_to_2dp_B9():
    """AMENDMENTS6 B9: 7.3 x 1.05 -> 5.000000000000003 % reads a test; 5.01 % does not."""
    df = _trend(k=0.073)
    _set(df, -9, low=7.3)
    lo = 7.3 * 1.05
    _set(df, -1, open=lo + 0.05, close=lo + 0.052, high=lo + 0.1, low=lo)
    feat = DJ.frame_features(df)
    assert feat["test_pct"].iloc[-1] > 5.0                              # the raw float is over
    assert bool(feat["tested"].iloc[-1])
    _set(df, -1, low=7.3 * 1.0501, open=7.3 * 1.0501 + 0.05, close=7.3 * 1.0501 + 0.052,
         high=7.3 * 1.0501 + 0.1)
    assert not bool(DJ.frame_features(df)["tested"].iloc[-1])


def test_25_NEG_reference_age_3_is_too_fresh_4_fires():
    assert _st(_fire(age=3)) == "ref_too_fresh"
    assert _st(_fire(age=4)) == "fired"


def test_26_NEG_equal_minima_the_most_recent_sets_the_age():
    df = _fire(age=10)
    _set(df, -3, low=98.0)                                             # same low, 2 sessions before
    feat = DJ.frame_features(df)
    assert int(feat["ref_age"].iloc[-1]) == 2
    assert _st(df) == "ref_too_fresh"


def test_27_NEG_no_downtrend_read():
    df = _up()
    assert _st(df) == "no_downtrend"
    r = _read(df)
    assert r["status"] == "no_downtrend" and r["reads"] == []


def test_28_NEG_59_99_under_the_52_week_high_alone_is_no_downtrend():
    df = _up()
    c = float(df["close"].iloc[-1])
    _set(df, -100, high=c / (1 - 0.5999))
    feat = DJ.frame_features(df)
    assert feat["pct_below_52w"].iloc[-1] == pytest.approx(59.99, abs=1e-6)
    assert feat["pct_below_52w"].iloc[-1] < DJ.DOWN_PCT
    assert not bool(feat["below_mas"].iloc[-1])
    assert _read(df)["status"] == "no_downtrend"


def test_29_NEG_nan_low_in_the_window_and_a_flat_bar_are_bad_bars():
    df = _fire()
    _set(df, -5, low=np.nan)
    assert _st(df) == "bad_bars"
    df2 = _fire()
    _set(df2, -1, high=99.0, low=99.0, open=99.0, close=99.0)
    assert _st(df2) == "bad_bars"


# --------------------------------------------------------------------------
# variants and volume
# --------------------------------------------------------------------------
def test_30_variants():
    v = lambda df: DJ.frame_features(df)["variant"].iloc[-1]         # noqa: E731
    assert v(_fire(pos=0.95, body=0.02)) == "dragonfly"               # upper wick ~4%
    assert v(_fire(pos=0.05, body=0.02)) == "gravestone"              # lower wick ~4%
    assert v(_fire(rng=2.0, pos=0.5)) == "long_legged"                # 2.0 >= the prior-10 mean 1.6
    assert v(_fire(rng=1.0, pos=0.5)) == "plain"                      # NEG under the mean, both wicks > 15%


@pytest.mark.parametrize("ratio,word", [(0.9, "quiet"), (1.6, "heavy"), (1.2, None)])
def test_31_volume_words(ratio, word):
    df = _fire()
    _set(df, -1, volume=1_000_000.0 * ratio)
    feat = DJ.frame_features(df)
    assert feat["vol_ratio"].iloc[-1] == pytest.approx(ratio)
    assert feat["vol_word"].iloc[-1] == word


def test_32_NEG_zero_average_volume_is_none_never_inf():
    df = _fire()
    df["volume"] = 0.0
    _set(df, -1, volume=500.0)
    feat = DJ.frame_features(df)
    assert np.isnan(feat["vol_ratio"].iloc[-1])
    r = _read(df)
    assert r["vol_ratio"] is None and r["vol_word"] is None
    json.dumps(r, allow_nan=False)


# --------------------------------------------------------------------------
# parity — the one engine against the house engines
# --------------------------------------------------------------------------
def _eq(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and np.isnan(a) and np.isnan(b):
        return True
    if a is None and b is None:
        return True
    try:
        return bool(a == b) or (np.isfinite(a) and np.isfinite(b) and abs(float(a) - float(b)) < 1e-9)
    except TypeError:
        return False


def test_40_parity_with_the_house_engines():
    df = _walk(glitch_at=300)
    full = DJ.frame_features(df)
    rng = np.random.default_rng(3)
    ts = sorted(set(rng.integers(260, len(df) - 1, 5).tolist()) | {299, 300, 301})
    for t in ts:
        sl = df.iloc[:t + 1]
        last = DJ.frame_features(sl).iloc[-1]
        for col in DJ.FEATURE_COLUMNS:
            assert _eq(full[col].iloc[t], last[col]), (t, col)
        assert full["sma50"].iloc[t] == pytest.approx(entry_exit._sma(sl, 50))
        assert full["sma200"].iloc[t] == pytest.approx(entry_exit._sma(sl, 200))
        assert full["atr_prior"].iloc[t] == pytest.approx(SDP.atr(df.iloc[:t], DJ.ATR_BARS))
        assert abs(full["adv50"].iloc[t] - QB.avg_dollar_vol(sl)) <= 0.5
        w = FAL.closed_read("WALK", sl, _next_session(sl.index[-1]))
        assert full["w52_high"].iloc[t] == pytest.approx(w["high"], abs=5e-5)
        assert full["pct_below_52w"].iloc[t] == pytest.approx(w["pct_below"], abs=0.006)
        assert bool(full["suspect"].iloc[t]) == (FAL._suspect(sl) is not None)
        lb = CD.read_daily(sl)["last_bar"]
        assert round(float(full["vol_ratio"].iloc[t]), 2) == lb["vol_ratio"]
    assert bool(full["suspect"].iloc[300]) and not bool(full["suspect"].iloc[299])


def test_41_NEG_look_ahead_guard_bars_after_t_never_change_t():
    df = _fire(at=-40)                                                   # an event mid-frame
    t = len(df) - 40
    base = DJ.frame_features(df)
    st = DJ.row_statuses(base, body_max=DJ.DOJI_BODY_PCT)
    assert st[t] == "fired"
    mutated = df.copy()
    mutated.iloc[t + 1:, :] = mutated.iloc[t + 1:, :] * 10.0
    after = DJ.frame_features(mutated)
    pd.testing.assert_frame_equal(base.iloc[:t + 1], after.iloc[:t + 1])
    st2 = DJ.row_statuses(after, body_max=DJ.DOJI_BODY_PCT)
    assert list(st[:t + 1]) == list(st2[:t + 1])


# --------------------------------------------------------------------------
# read()
# --------------------------------------------------------------------------
def test_50_NEG_today_dated_bar_is_dropped_then_read_after_the_roll():
    df = _fire()                                                         # the 10-16 bar IS the doji
    mid = _read(df, session=SESSION_RTH)
    assert mid["status"] != "fired" and mid["date"] == "2026-10-15"
    after = _read(df, session=DJ.session_for(NOW))
    assert DJ.session_for(NOW) == SESSION
    assert after["status"] == "fired" and after["date"] == LAST


def test_51_NEG_stale_and_history_minimum():
    old = _doji(_trend(end="2026-10-14"))
    assert _read(old)["status"] == "stale"
    short = _doji(_trend(n=251))
    r = _read(short)
    assert r["status"] == "short_history" and r["n_bars"] == 251
    ok = _doji(_trend(n=252))
    assert _read(ok)["status"] not in ("short_history", "stale", "no_bars")
    assert _read(None)["status"] == "no_bars"


def test_52_NEG_delisted_etf_and_scale_glitch_are_held_out(monkeypatch):
    monkeypatch.setattr(symbols, "is_delisted", lambda s: str(s).upper() == "DEAD")
    assert _read(_fire(), "DEAD")["status"] == "delisted"
    assert _read(_fire(), "SPYX", etf_set={"SPYX"})["status"] == "etf"
    g = _fire()
    _set(g, -100, close=1000.0)
    r = _read(g, "GLCH")
    assert r["status"] == "data_suspect"
    sr = r["suspect"]["ratio"]
    assert isinstance(r["suspect"], dict) and max(sr, 1 / sr) >= DJ.GLITCH_RATIO * 0.99
    assert _read(_fire(), "GOOD")["status"] == "fired"


def test_53_ath_doc_proven_reads_ath_alone():
    sym = "ATHX"
    df = _up()
    doc = _ath_doc(sym, df)
    r = _read(df, sym, ath_doc=doc, listed="2015-03-10", now_ts=NOW.timestamp())
    assert r["status"] == "fired" and r["reads"] == ["ath"]
    assert r["ath"]["proven"] is True and r["ath"]["label"] == "ATH"
    assert r["pct_below_ath"] >= DJ.DOWN_PCT
    json.dumps(r, allow_nan=False)


def test_54_NEG_no_doc_reads_the_frame_only_high_since():
    df = _steep()
    r = _read(df, "FRM", ath_doc=None, listed=None)
    assert r["ath"] is not None and r["ath"]["proven"] is False
    assert r["ath"]["label"].startswith("High since ")
    assert "ath" in r["reads"]                                          # 400 -> 100: the frame alone reads it
    up = _read(_up(), "FRM2", ath_doc=None)
    assert up["status"] == "no_downtrend" and "ath" not in up["reads"]


def test_55_read_keys_and_json_safe():
    r = _read(_steep())
    assert tuple(r) == ("symbol", "status", "date", "open", "high", "low", "close", "volume", "body_pct",
                        "upper_wick_pct", "lower_wick_pct", "variant", "doji5", "ref_low", "ref_date",
                        "ref_age", "test_pct", "tested", "undercut", "reclaimed", "w52", "pct_below_52w",
                        "ath", "pct_below_ath", "sma50", "sma200", "below_mas", "reads", "vol_ratio",
                        "vol_word", "range_atr", "adv50", "n_bars", "suspect")
    txt = json.dumps(r, allow_nan=False)
    assert "NaN" not in txt and "nan" not in txt
    assert r["ref_date"] == pd.Timestamp(_steep().index[-9]).date().isoformat()


# --------------------------------------------------------------------------
# ath_series (the study's point-in-time ATH)
# --------------------------------------------------------------------------
def test_60_ath_series_history_only_after_the_stored_month():
    df = _steep()
    month = df.index[100].strftime("%Y-%m")
    doc = {"hi": 5000.0, "hi_month": month}
    hi, basis = DJ.ath_series(df, doc)
    months = np.asarray([d.strftime("%Y-%m") for d in df.index])
    after = months > month
    assert set(basis[after]) == {"history"} and (hi[after] == 5000.0).all()
    run = np.fmax.accumulate(df["high"].to_numpy(dtype=float))
    assert set(basis[~after]) == {"frame"}
    assert np.allclose(hi[~after], run[~after])                         # NEG: never the doc's hi there
    assert (hi[~after] < 5000.0).all()
    hi0, b0 = DJ.ath_series(df, None)
    assert set(b0) == {"frame"} and np.allclose(hi0, run)


# --------------------------------------------------------------------------
# study cells (AMENDMENTS6 B4 / B5)
# --------------------------------------------------------------------------
def test_61_study_cells_primary_any_read_and_the_doji_contrast():
    steep = DJ.frame_features(_steep())
    floor = np.ones(len(steep), dtype=bool)
    c = DJ.study_cells(steep, pct_below_ath=None, floor=floor)
    assert set(c) == set(DSM.VERDICT_CELLS)
    assert c["primary"][-1] and c["any_read"][-1] and not c["test_no_doji"][-1]
    assert not (c["primary"] & ~c["any_read"]).any()                    # primary within any_read
    mas_only = DJ.frame_features(_fire())
    c2 = DJ.study_cells(mas_only, pct_below_ath=None, floor=floor)
    assert c2["any_read"][-1] and not c2["primary"][-1]                 # NEG: no 52-week read
    nod = DJ.frame_features(_steep(body=0.3))
    c3 = DJ.study_cells(nod, pct_below_ath=None, floor=floor)
    assert c3["test_no_doji"][-1] and not c3["any_read"][-1]
    c4 = DJ.study_cells(steep, pct_below_ath=None, floor=~floor)
    assert not any(v.any() for v in c4.values())                        # NEG: under the floor


# --------------------------------------------------------------------------
# the board read
# --------------------------------------------------------------------------
def _universe():
    g = _fire()
    _set(g, -100, close=1000.0)
    return {"MAS": _fire(), "DEEP": _steep(test=-2.0, rng=4.0, pos=0.75), "WIDE": _fire(body=0.07),
            "NOTD": _fire(body=0.3), "UP": _up(), "STALE": _doji(_trend(end="2026-10-14")),
            "SHORT": _doji(_trend(n=200)), "GLCH": g, "ETFX": _fire(), "FLAT": _fire(age=2)}


def test_70_build_counts_sum_rows_fired_only():
    e = _build(_universe(), etfs={"ETFX"})
    c = e["counts"]
    assert sum(c[s] for s in DJ.STATUSES) == c["scanned"] == 10
    assert set(e["rows"]) == {"MAS", "DEEP", "WIDE"}
    assert all(r["status"] == "fired" for r in e["rows"].values())
    assert c["etf"] == 1 and c["data_suspect"] == 1 and c["stale"] == 1 and c["short_history"] == 1
    assert c["not_doji"] == 1 and c["no_downtrend"] == 1 and c["ref_too_fresh"] == 1
    assert e["as_of"] == KL.prev_market_day(SESSION).isoformat() == LAST
    assert [s["symbol"] for s in e["suspects"]] == ["GLCH"]
    assert e["rows"]["WIDE"]["doji5"] is False and e["rows"]["MAS"]["doji5"] is True


def test_71_NEG_an_empty_frames_read_raises_and_is_never_memoised():
    with pytest.raises(RuntimeError):
        DJ.build("full", SESSION, universe_fn=lambda u: ["AAA"], frames_fn=lambda s: {},
                 history_fn=lambda s: {}, listing_fn=lambda s: {}, etf_fn=lambda: set())
    assert DJ._memo == {}


def test_72_memo_warming_then_ready(monkeypatch):
    spawned = []
    monkeypatch.setattr(DJ, "_spawn", lambda target, name: spawned.append((target, name)))
    frames = _universe()
    real = DJ.build
    monkeypatch.setattr(DJ, "build", lambda u, s, **kw: real(
        "full", s, universe_fn=lambda _u: list(frames), frames_fn=lambda syms: dict(frames),
        history_fn=lambda _s: {}, listing_fn=lambda _s: {}, etf_fn=lambda: set()))
    first = DJ.cached_or_warm("full", now=NOW)
    assert first["state"] == "warming" and len(spawned) == 1
    assert spawned[0][1] == f"doji-sweep-tab-{SESSION.isoformat()}-full"
    again = DJ.cached_or_warm("full", now=NOW)
    assert again["state"] == "warming" and len(spawned) == 1            # one build in flight
    spawned[0][0]()
    ready = DJ.cached_or_warm("full", now=NOW)
    assert ready["state"] == "ready" and set(ready["entry"]["rows"]) == {"MAS", "DEEP", "WIDE", "ETFX"}


def test_73_NEG_a_failing_build_is_an_error_retried_only_after_the_backoff(monkeypatch):
    spawned = []
    monkeypatch.setattr(DJ, "_spawn", lambda target, name: spawned.append(target))

    def boom(u, s, **kw):
        raise RuntimeError("cache down")
    monkeypatch.setattr(DJ, "build", boom)
    assert DJ.cached_or_warm("full", now=NOW)["state"] == "warming"
    spawned[0]()
    err = DJ.cached_or_warm("full", now=NOW)
    assert err["state"] == "error" and err["reason"] == "cache down"
    assert len(spawned) == 1                                            # backing off
    key = (SESSION.isoformat(), "full")
    DJ._failures[key] = (DJ.time.time() - DJ.FAIL_RETRY_SEC - 1, "cache down")
    DJ.cached_or_warm("full", now=NOW)
    assert len(spawned) == 2                                            # retried after the backoff


def test_74_NEG_a_late_older_session_build_is_dropped():
    with DJ._lock:
        assert DJ._store(("2026-10-19", "full"), {"built_ts": 1.0})
        assert not DJ._store(("2026-10-16", "full"), {"built_ts": 2.0})
        assert set(DJ._memo) == {("2026-10-19", "full")}


# --------------------------------------------------------------------------
# rank / chips / body switch / orders
# --------------------------------------------------------------------------
def _row(sym, *, d=LAST, doji5=True, test=1.0, p52=50.0, pa=None, reads=("mas",), mas=True,
         reclaimed=False, undercut=False):
    return {"symbol": sym, "date": d, "doji5": doji5, "test_pct": test, "pct_below_52w": p52,
            "w52": {"high": 200.0, "high_date": "2026-01-02", "pct_below": p52},
            "pct_below_ath": pa, "reads": list(reads), "below_mas": mas, "reclaimed": reclaimed,
            "undercut": undercut}


def _entry(rows):
    return {"rows": {r["symbol"]: r for r in rows}, "counts": {"scanned": 9, "fired": len(rows)}}


ROWS = [_row("AAA", p52=72.0, reads=("w52", "mas"), reclaimed=True, undercut=True, test=-1.5),
        _row("BBB", p52=65.0, reads=("w52", "mas"), test=0.5),
        _row("CCC", doji5=False, p52=80.0, reads=("w52",), mas=False, test=3.0),
        _row("DDD", d="2026-10-15", p52=90.0, reads=("w52", "ath", "mas"), pa=91.0, test=-0.2),
        _row("EEE", p52=30.0, test=0.5)]


def test_80_body_switch_keeps_doji5_at_5_and_all_at_10():
    rows, counts, _f = DJ.rank(_entry(ROWS), sort=DJ.DEFAULT_SORT, body=5)
    assert "CCC" not in {r["symbol"] for r in rows} and counts["at_body"] == 4
    assert counts["wider_body"] == 1
    rows10, c10, _f = DJ.rank(_entry(ROWS), sort=DJ.DEFAULT_SORT, body=10)
    assert {r["symbol"] for r in rows10} == {r["symbol"] for r in ROWS} and c10["wider_body"] == 0


def test_81_chips_and_every_ticked_chip_must_pass():
    rows, counts, f = DJ.rank(_entry(ROWS), sort=DJ.DEFAULT_SORT, active=("w52_60", "reclaimed"))
    assert [r["symbol"] for r in rows] == ["AAA"]
    assert counts["hidden_by_chips"] == 3
    assert f["active"] == ["w52_60", "reclaimed"] and f["passed_all"] == 1 and f["mode"] == "all"
    assert "mode_param" not in f and "mode_all_label" not in f          # no mode switch
    assert f["line"].startswith("Chips on (every ticked chip must pass)")


def test_82_NEG_unknown_chip_ignored_and_ath_chip_needs_an_ath_read():
    assert DJ.parse_filters("w52_60, reclaimed,junk") == ("w52_60", "reclaimed")
    assert DJ.parse_filters("MAS+w52_40") == ("w52_40", "mas")
    assert DJ.parse_filters(None) == () and DJ.parse_filters(7) == () and DJ.parse_filters("  ") == ()
    rows, _c, f = DJ.rank(_entry(ROWS), sort=DJ.DEFAULT_SORT, active=DJ.parse_filters("junk"))
    assert len(rows) == 4 and f["line"] is None
    assert DJ.tile_filter(ROWS[0])["ath_60"] is None
    rows, _c, f = DJ.rank(_entry(ROWS), sort=DJ.DEFAULT_SORT, active=("ath_60",))
    assert [r["symbol"] for r in rows] == ["DDD"]
    item = next(i for i in f["items"] if i["key"] == "ath_60")
    assert item["no_read"] == 3 and item["pass"] == 1


def test_83_the_three_orders_ties_by_symbol_and_NEG_unknown_sort():
    by = lambda srt: [r["symbol"] for r in DJ.rank(_entry(ROWS), sort=srt, body=10)[0]]   # noqa: E731
    assert by(DJ.DEFAULT_SORT) == ["CCC", "AAA", "BBB", "EEE", "DDD"]
    assert by(DJ.SORT_TEST) == ["DDD", "BBB", "EEE", "AAA", "CCC"]
    assert by(DJ.SORT_ATH) == ["DDD", "CCC", "AAA", "BBB", "EEE"]
    assert by("hb_drop") == by(DJ.DEFAULT_SORT)
    tie = [_row("ZZZ", p52=50.0, test=0.5), _row("AAB", p52=50.0, test=-0.5)]
    assert [r["symbol"] for r in DJ.rank(_entry(tie), sort=DJ.SORT_TEST)[0]] == ["AAB", "ZZZ"]
    assert [r["symbol"] for r in DJ.rank(_entry(tie), sort=DJ.DEFAULT_SORT)[0]] == ["AAB", "ZZZ"]
    assert [s["key"] for s in DJ.served_sorts()] == [DJ.DEFAULT_SORT, DJ.SORT_TEST, DJ.SORT_ATH]


@pytest.mark.parametrize("raw,want", [("7", 5), (" 10 ", 5), (None, 5), ("10", 10), ("5", 5),
                                      (10, 10), (True, 5), ("010", 5), ("abc", 5)])
def test_84_parse_body(raw, want):
    assert DJ.parse_body(raw) == want


def test_85_body_block_and_undercut_count():
    b = DJ.body_block(10)
    assert b["param"] == "dj_body" and [s["key"] for s in b["steps"]] == ["5", "10"]
    assert [s["on"] for s in b["steps"]] == [False, True] and b["steps"][0]["default"]
    _r, counts, _f = DJ.rank(_entry(ROWS), sort=DJ.DEFAULT_SORT, body=5)
    assert counts["undercut"] == 1
    h = DJ.header_text(counts, body=5, as_of=LAST)
    assert "Sweep: 4 tests · 1 undercut the low." in h               # AMENDMENTS6 B16


# --------------------------------------------------------------------------
# ledger hand-off (AMENDMENTS6 B7)
# --------------------------------------------------------------------------
def test_90_ledger_fires_one_dict_per_candle_one_frames_read(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a default Mongo reader was reached")
    monkeypatch.setattr(prices, "bulk_cached_frames", refuse)
    monkeypatch.setattr(AH, "read_many", refuse)
    monkeypatch.setattr(DJ, "_spawn", refuse)
    late = _fire(at=-2)                                                  # fires on the 10-15 candle only
    frames = {"NOW1": _fire(), "LATE": late, "NONE": _fire(body=0.3)}
    calls = []

    def frames_fn(syms):
        calls.append(list(syms))
        return {s: frames[s] for s in syms}
    out = DJ.ledger_fires(now=NOW, universe_fn=lambda u: list(frames), frames_fn=frames_fn,
                          history_fn=lambda s: {}, listing_fn=lambda s: {}, etf_fn=lambda: set())
    assert len(calls) == 1
    got = {(f["symbol"], f["date"]) for f in out}
    assert got == {("NOW1", "2026-10-16"), ("LATE", "2026-10-15")}
    for f in out:
        assert tuple(f) == DJ.LEDGER_KEYS
        assert isinstance(f["reads"], list) and f["bucket"] == "doji_sweep"
    assert not any(f["symbol"] == "NONE" for f in out)                  # NEG: never a non-fired candle
    assert DJ._memo == {}                                               # writes nothing, memoises nothing


def test_91_ledger_bucket_split():
    assert DJ.ledger_bucket({"doji5": True, "adv50": 20e6}) == "doji_sweep"
    assert DJ.ledger_bucket({"doji5": False, "adv50": 20e6}) == "doji_sweep_10pct"
    assert DJ.ledger_bucket({"doji5": True, "adv50": 5e6}) == "doji_sweep_thin"
    assert DJ.ledger_bucket({"doji5": False, "adv50": 5e6}) == "doji_sweep_thin"
    assert DJ.ledger_bucket({"doji5": True, "adv50": None}) == "doji_sweep_thin"   # NEG: unknown fails the floor


# --------------------------------------------------------------------------
# words
# --------------------------------------------------------------------------
def _clean(s: str):
    low = s.lower()
    assert "bounc" not in low, s
    for w in FORBIDDEN_WORDS:
        assert w not in low, (w, s)
    assert "None" not in s and "nan" not in low.replace("nance", ""), s


def _words_from(r) -> list:
    out = [DJ.why_text(r, "zone text"), DJ.test_text(r), DJ.reads_text(r)]
    out += [b["text"] for b in DJ.tile_badges(r)]
    out += [f"{s['k']} {s['v']}" for s in DJ.tile_stats(r)]
    out += [x["label"] for x in DJ.tile_lines(r)] + [x["label"] for x in DJ.tile_markers(r)]
    return out


def test_100_every_word_family_is_clean():
    e = _build(_universe(), etfs={"ETFX"})
    rows, counts, f = DJ.rank(e, sort=DJ.DEFAULT_SORT, active=("w52_40",), body=5)
    counts.update(shown=2, dropped_thin=1, no_turnover=1)
    texts = [DJ.TAB_LABEL, DJ.DEFAULT_SORT_LABEL, DJ.TEST_SORT_LABEL, DJ.ATH_SORT_LABEL, DJ.WARMING_NOTE,
             DJ.EMPTY_NOTE, DJ.NOTE, DJ.FILTERS_NOTE, DJ.REF_LINE_LABEL, DJ.NOTE_PENDING,
             DJ.error_note("boom"), DJ.header_text(counts, body=5, as_of=e["as_of"]),
             DJ.count_line(counts, body=5, min_tier_label="Ok · ≥$10M/day", need_date=LAST), f["line"]]
    texts += [DJ.order_line(s) for s in (DJ.DEFAULT_SORT, DJ.SORT_TEST, DJ.SORT_ATH)]
    texts += list(DJ.FILTER_LABELS.values()) + list(DJ.FILTER_NOTES.values()) + list(DJ.READS_LEGEND)
    texts += list(DJ.BODY_LABELS.values()) + list(DJ.BODY_TITLES.values()) + list(DJ.VARIANT_WORDS.values())
    texts += list(DJ._verdict_words().values()) + list(DJ.CONTRAST_WORDS.values())
    for r in e["rows"].values():
        texts += _words_from(r)
        json.dumps(DJ.tile_block(r), allow_nan=False)
    for t in texts:
        _clean(t)
    assert DJ.reads_text(e["rows"]["DEEP"]).startswith("Reads met: ")   # B16
    assert "Downtrend" not in DJ.reads_text(e["rows"]["DEEP"])


def test_101_the_numbers_in_the_words_are_the_constants():
    c = {k: 0 for k in DJ.COUNT_KEYS}
    h = DJ.header_text(c, body=DJ.BODY_STEPS[0], as_of=LAST)
    assert f"within {DJ.SWEEP_TEST_PCT:g}% either side" in h
    assert f"the {DJ.SWEEP_REF_SESSIONS} sessions before it" in h
    assert f"{DJ.DOWN_PCT:g}%+ under the 52-week high" in h and f"{DJ.DOWN_PCT:g}%+ under the all-time" in h
    assert f"below the {DJ.SMA_FAST}- and {DJ.SMA_SLOW}-day" in h and f"under {DJ.BODY_STEPS[0]}% of" in h
    assert set(re.findall(r"(\d+)%", h)) == {str(DJ.BODY_STEPS[0]), f"{DJ.SWEEP_TEST_PCT:g}", f"{DJ.DOWN_PCT:g}"}
    cl = DJ.count_line(c, body=5, min_tier_label="x", need_date=LAST)
    assert f"{DJ.BODY_STEPS[1]}% of the range" in cl and f"more than {DJ.SWEEP_TEST_PCT:g}% from" in cl
    assert f"under {DJ.SWEEP_REF_MIN_AGE} sessions before" in cl and f"{DJ.GLITCH_RATIO:g}×" in cl
    assert f"fewer than {DJ.YEAR_BARS} sessions" in cl and f"before {LAST}" in cl
    assert "a flat candle today" in cl                                   # AMENDMENTS6 B13
    for i, k in enumerate(("w52_40", "w52_60", "w52_70")):
        assert re.search(r"≥(\d+)%", DJ.FILTER_LABELS[k]).group(1) == str(DJ.DEPTH_CHIPS[i])
        assert DJ.FILTER_NOTES[k].startswith(f"Closed {DJ.DEPTH_CHIPS[i]}% or more")
        assert f"last {DJ.YEAR_BARS} closed" in DJ.FILTER_NOTES[k]
    assert f"≥{DJ.DOWN_PCT:g}%" in DJ.FILTER_LABELS["ath_60"]
    assert DJ.FILTER_LABELS["mas"] == f"Below the {DJ.SMA_FAST}- and {DJ.SMA_SLOW}-day"
    assert all(f"{DJ.DOWN_PCT:g}%" in x for x in DJ.READS_LEGEND[:2])
    assert f"{DJ.YEAR_BARS} closed" in DJ.READS_LEGEND[0]
    f = DJ.filters_block([DJ.tile_filter(r) for r in ROWS], ("w52_70",), pool=len(ROWS))
    assert re.search(r"(\d+) of (\d+) pass every ticked chip", f["line"]).groups() == ("3", "5")
    assert str(int(DJ.FAIL_RETRY_SEC // 60)) in DJ.error_note("x")


def test_102_NEG_count_line_with_zero_counts_still_names_every_class():
    cl = DJ.count_line({}, body=5, min_tier_label="no floor", need_date=LAST)
    for frag in ("was not a doji", "whose low sat more than", "was set under", "none of the three downtrend",
                 "one-session close move", "ETFs", "delisted", "sessions of history", "cached bars end",
                 "a flat candle today", "no cached bars"):
        assert frag in cl, frag
    assert "hidden by the chips" not in cl and "fired on one of" not in cl
    _clean(cl)


def test_103_board_envelopes():
    e = _build(_universe(), etfs={"ETFX"})
    rows, counts, f = DJ.rank(e, sort=DJ.SORT_TEST, active=(), body=5)
    b = DJ.ready_block(counts, entry=e, sort=DJ.SORT_TEST, body=5, filters=f, min_tier_label="Ok")
    assert b["state"] == "ready" and b["as_of"] == LAST and b["count_line"] and b["counts"]
    assert b["study"]["status"] == "unmeasured" and b["measured"] is False
    assert b["suspects"]["n"] == 1 and b["filter_param"] == "dj" and b["test_pct"] == 5.0
    assert b["reads_legend"] == list(DJ.READS_LEGEND) and b["order_line"] == DJ.order_line(DJ.SORT_TEST)
    w = DJ.warming_block(now=NOW, sort=DJ.DEFAULT_SORT, body=5, active=("mas",))
    assert w["state"] == "warming" and w["header"] == DJ.WARMING_NOTE
    assert w["counts"] is None and w["count_line"] is None and w["suspects"] is None and w["as_of"] is None
    assert w["session"] == SESSION.isoformat() and w["study"]["text"] == DJ.NOTE_PENDING
    er = DJ.error_block("boom", now=NOW, sort=DJ.DEFAULT_SORT, body=5, active=())
    assert er["state"] == "error" and "boom" in er["header"]
    for blk in (b, w, er):
        json.dumps(blk, allow_nan=False)
    t = DJ.tile_block(e["rows"]["DEEP"])
    assert t["reclaimed"] and t["test_text"].endswith("closed back above it")
    assert DJ.tile_lines(e["rows"]["DEEP"])[0]["label"] == DJ.REF_LINE_LABEL
    assert DJ.tile_markers(e["rows"]["DEEP"]) == [{"date": LAST, "label": DJ.MARK}]
    assert DJ.why_text(e["rows"]["DEEP"], "z").startswith(DJ.MARK)


# --------------------------------------------------------------------------
# the study line + DSM
# --------------------------------------------------------------------------
def _cell(key="any_read", verdict="no_signal", n=420):
    c = {"role": "verdict", "verdict": verdict, "ci_pct": 95.0, "p_holm": 0.62, "n_events": n, "n_dates": 80,
         "median_diff_pp": 0.4, "ci_block": [-0.8, 1.1], "ci_symbol": [-0.6, 1.0], "adj_median_diff_pp": 0.3,
         "adj_ci_block": [-0.9, 1.2], "adj_ci_symbol": [-0.7, 1.05]}
    if key not in DSM.VERDICT_CELLS:
        c["role"] = DSM.EXPLORATORY_LABEL
    return {k: c[k] for k in DSM.literal_cell_keys(key)}


def _literal():
    p = {"role": "verdict", "verdict": "no_signal", "ci_pct": 95.0, "p_holm": 0.88, "horizon": 10,
         "entry": "next_open", "n_events": 412, "n_dates": 77, "n_symbols": 301,
         "n_detected": 430, "n_blocks": 24, "n_placebo": 2050,   # fix round 2 (WP-S): the counts behind the verdict
         "n_unmatched": 6, "placebo_short_pool": 23, "event_median_pct": -1.25,
         "placebo_median_pct": -1.75, "median_diff_pp": 0.5, "ci_block": [-0.9, 1.4],
         "ci_symbol": [-0.5, 1.2], "robust": True, "adj_event_median_pct": -0.4,
         "adj_placebo_median_pct": -0.65, "adj_median_diff_pp": 0.25, "adj_ci_block": [-1.1, 1.3],
         "adj_ci_symbol": [-0.8, 1.15], "event_mean_pct": 0.9, "placebo_mean_pct": 0.7,
         "ci_mean_block": [-0.6, 1.0], "net_mean_pct": 0.4, "confirm_pct": 41.0,
         "placebo_confirm_pct": 38.0, "ci_confirm_block": [-3.0, 9.0], "stop_pct": 33.0,
         "placebo_stop_pct": 30.0}
    return {"status": "measured", "schema": 1, "script": DJ.SCRIPT_PATH,
            "artifact": "backend/scripts/doji_sweep_measured.json", "prereg": DJ.PREREG_PATH,
            "prereg_commit": "abc1234", "prereg_blob": "f" * 40, "run_date": "2026-10-17",
            "as_of": "2026-10-16", "first_session": "2025-10-14", "last_session": "2026-10-02",
            "cohort": "survivors-only", "cost_round_trip_pct": 0.5, "confirm_sessions": 5,
            "block_sessions": DSM.BLOCK_SESSIONS, "primary": p,
            "cells": {k: _cell(k) for k in DSM.SERVED_CELLS}}


def test_110_study_block_placeholder_is_unmeasured():
    s = DJ.study_block()
    assert s["status"] == "unmeasured" and s["text"] == DJ.NOTE_PENDING and s["verdict"] is None
    assert "UNMEASURED" in s["text"] and CD.BULKOWSKI_CANDLE["doji"] in s["text"] and CD.CAVEAT in s["text"]
    assert s["prereg"] == DJ.PREREG_PATH and s["script"] == DJ.SCRIPT_PATH
    assert DJ.is_measured() is False


def test_111_study_block_measured_literal(monkeypatch):
    lit = _literal()
    assert set(lit) == set(DSM.LITERAL_TOP_KEYS)
    assert set(lit["primary"]) == set(DSM.LITERAL_PRIMARY_KEYS)
    monkeypatch.setattr(DSM, "MEASURED", lit)
    s = DJ.study_block()
    assert s["status"] == "measured" and s["verdict"] == "no_signal" and DJ.is_measured()
    t = s["text"]
    for frag in ("412 dojis", "held 10 sessions", "net of SPY", f"{DJ.DOWN_PCT:g}%+ under the 52-week high",
                 "median −0.40% against −0.65%", "+0.25 pp", "before SPY +0.50 pp",
                 f"CI by {DSM.BLOCK_SESSIONS}-session block [−1.10, +1.30]", "by name [−0.80, +1.15]",
                 "Any downtrend read: 420 dojis", "a test of the low without a doji, against its own matched",
                 "41% vs 38%", "33% vs 30%", "0.5% round trip", "Holm-corrected", "exploratory — no verdict",
                 "95% CI by", "Holm p 0.880 / 0.620 / 0.620", "23 with a short placebo pool", "6 with none",
                 "Mean +0.90% (before SPY) against +0.70% on the matched days",
                 "difference CI by block [−0.60, +1.00] pp", "(difference CI by block [−3.00, +9.00] pp)"):
        assert frag in t, frag
    assert "Mean +0.90% before costs" not in t                     # the raw mean is labelled, never bare
    _clean(t)


def test_112_NEG_a_malformed_literal_serves_the_unmeasured_block(monkeypatch):
    lit = _literal()
    del lit["primary"]["adj_ci_block"]
    monkeypatch.setattr(DSM, "MEASURED", lit)
    assert DJ.study_block()["text"] == DJ.NOTE_PENDING
    lit2 = _literal()
    del lit2["cells"]["test_no_doji"]
    monkeypatch.setattr(DSM, "MEASURED", lit2)
    assert DJ.study_block()["status"] == "unmeasured"
    monkeypatch.setattr(DSM, "MEASURED", "junk")
    assert DJ.study_block()["text"] == DJ.NOTE_PENDING
    lit3 = _literal()
    lit3["primary"]["verdict"] = "maybe"
    monkeypatch.setattr(DSM, "MEASURED", lit3)
    assert DJ.study_block()["status"] == "unmeasured"


def test_113_dsm_placeholder_and_schema():
    assert DSM.MEASURED == {"state": "unmeasured"}
    got = DSM.load()
    assert got == DSM.MEASURED and got is not DSM.MEASURED
    from scripts.explosive_study import MIN_BUCKET_N
    assert DSM.MIN_CELL_DATES == MIN_BUCKET_N
    assert set(DSM.LITERAL_PRIMARY_KEYS) <= set(DSM.CELL_KEYS)
    assert set(DSM.LITERAL_CELL_KEYS) <= set(DSM.CELL_KEYS)
    assert set(DSM.HORIZON_KEYS) <= set(DSM.CELL_KEYS)
    assert not (set(DSM.COUNT_CELL_KEYS) & {"median_diff_pp", "ci_block", "verdict", "confirm_pct"})
    assert len(DSM.VERDICT_CELLS) == 3 and DSM.VERDICT_CELLS[0] == "primary"           # B6
    assert set(DSM.VERDICT_CELLS[1:]) <= set(DSM.SERVED_CELLS)
    assert "w52_60" not in DSM.SERVED_CELLS                              # the primary IS the 60% read (B4)
    assert set(DJ._verdict_words()) == set(DSM.VERDICTS) == set(DJ.CONTRAST_WORDS)
    assert "git" in DSM.ARTIFACT_KEYS and "placebo_short_pool" in DSM.CELL_KEYS     # B12 / B1
    assert "ci_block" in DSM.CELL_KEYS and "adj_median_diff_pp" in DSM.CELL_KEYS    # B2


# --------------------------------------------------------------------------
# fix round 1 (2026-10-16, the WP-A critic)
# --------------------------------------------------------------------------
def test_114_NEG_the_control_words_never_claim_the_doji_adds(monkeypatch):
    """The HIGH: test_no_doji is the no-doji tests against THEIR matched days. A null
    primary beside a separating control must never read 'the doji adds'."""
    lit = _literal()
    lit["primary"].update(verdict="no_signal", adj_median_diff_pp=0.05, adj_ci_block=[-0.9, 1.0])
    lit["cells"]["test_no_doji"].update(verdict="separates", adj_median_diff_pp=1.9,
                                        adj_ci_block=[0.6, 3.1], adj_ci_symbol=[0.5, 3.0])
    monkeypatch.setattr(DSM, "MEASURED", lit)
    t = DJ.study_block()["text"]
    assert "+1.90 pp, 95% CI [+0.60, +3.10] / [+0.50, +3.00]: on this record the tests without a doji " \
           "returned more than their matched days" in t
    assert "+0.05 pp" in t and DJ._verdict_words()["no_signal"] in t
    low = t.lower()
    assert "doji adds" not in low and "add to the test" not in low and "adds to" not in low
    for w in DJ.CONTRAST_WORDS.values():
        lw = w.lower()
        assert "without a doji" in lw, w
        assert "adds" not in lw and "add to" not in lw and "does not add" not in lw, w
        _clean(w)


def test_115_holm_words_only_when_the_literal_carries_them(monkeypatch):
    lit = _literal()
    lit["cells"]["any_read"]["p_holm"] = None
    monkeypatch.setattr(DSM, "MEASURED", lit)
    t = DJ.study_block()["text"]
    assert "Holm" not in t and DJ.NO_HOLM_LINE in t                   # NEGATIVE: no record, no claim
    lit2 = _literal()
    for c in (lit2["primary"], lit2["cells"]["any_read"], lit2["cells"]["test_no_doji"]):
        c["ci_pct"] = 98.33
    lit2["primary"]["p_holm"] = 0.012
    monkeypatch.setattr(DSM, "MEASURED", lit2)
    t2 = DJ.study_block()["text"]
    assert "Holm-corrected" in t2 and "Holm p 0.012 / 0.620 / 0.620" in t2
    assert "98.33% CI by 10-session block" in t2 and "95% CI" not in t2   # the CI at the verdict's level
    lit3 = _literal()
    del lit3["cells"]["test_no_doji"]["p_holm"]                       # NEGATIVE: a schema key missing = malformed
    monkeypatch.setattr(DSM, "MEASURED", lit3)
    assert DJ.study_block()["status"] == "unmeasured"


def test_116_NEG_measured_flag_matches_the_text_and_a_none_ci_is_a_dash(monkeypatch):
    lit = _literal()
    lit["primary"]["verdict"] = "maybe"
    monkeypatch.setattr(DSM, "MEASURED", lit)
    assert DJ.study_block()["status"] == "unmeasured" and DJ.is_measured() is False
    lit2 = _literal()
    lit2["cells"]["test_no_doji"].update(verdict="too_small", adj_ci_symbol=None, adj_median_diff_pp=None)
    monkeypatch.setattr(DSM, "MEASURED", lit2)
    s = DJ.study_block()
    assert s["status"] == "measured" and DJ.is_measured() is True
    assert "[—, —]: too few tests without a doji to read" in s["text"] and "— pp" in s["text"]
    assert "UNMEASURED" not in s["text"]
    _clean(s["text"])
    lit3 = _literal()
    lit3["primary"]["ci_confirm_block"] = None
    lit3["primary"]["placebo_mean_pct"] = None
    monkeypatch.setattr(DSM, "MEASURED", lit3)
    t3 = DJ.study_block()["text"]
    assert "(difference CI by block [—, —] pp)" in t3 and "against —% on the matched days" in t3
    b = DJ.warming_block(now=NOW, sort=DJ.DEFAULT_SORT, body=5, active=())
    assert b["measured"] is True and b["study"]["status"] == "measured"


def test_117_literal_schema_carries_b1_b4_b6():
    assert {"placebo_short_pool", "n_unmatched"} <= set(DSM.LITERAL_PRIMARY_KEYS)      # B1 served
    assert {"placebo_mean_pct", "ci_mean_block", "ci_confirm_block"} <= set(DSM.LITERAL_PRIMARY_KEYS)
    assert {"ci_pct", "p_holm"} <= set(DSM.LITERAL_PRIMARY_KEYS) & set(DSM.CELL_KEYS)
    assert "verdict" not in DSM.LITERAL_CELL_KEYS                                      # B6: no verdict word
    assert {"verdict", "ci_pct", "p_holm"} <= set(DSM.LITERAL_VERDICT_CELL_KEYS)
    assert set(DSM.LITERAL_VERDICT_CELL_KEYS) <= set(DSM.CELL_KEYS)
    for k in DSM.SERVED_CELLS:
        has_v = "verdict" in DSM.literal_cell_keys(k)
        assert has_v is (k in DSM.VERDICT_CELLS), k
    assert DSM.PREDECLARED_TOO_SMALL == ("w52_70",)                                    # B4
    assert set(DSM.PREDECLARED_TOO_SMALL) <= set(DSM.SERVED_CELLS)
    assert not set(DSM.PREDECLARED_TOO_SMALL) & set(DSM.VERDICT_CELLS)
    lit = _literal()
    assert set(lit["primary"]) == set(DSM.LITERAL_PRIMARY_KEYS)
    for k, c in lit["cells"].items():
        assert set(c) == set(DSM.literal_cell_keys(k)), k


def test_118_NEG_one_missing_high_keeps_the_52_week_read():
    df = _steep()
    i = len(df) - 150
    df.iloc[i, df.columns.get_loc("high")] = np.nan
    r = _read(df)
    assert r["pct_below_52w"] is not None and "w52" in r["reads"]
    assert r["pct_below_52w"] == pytest.approx(r["w52"]["pct_below"], abs=0.006)
    clean = _read(_steep())
    assert r["pct_below_52w"] == pytest.approx(clean["pct_below_52w"], abs=0.006)
    feat = DJ.frame_features(df)
    hi = df["high"].to_numpy(dtype=float)
    assert feat["w52_high"].iloc[-1] == pytest.approx(np.nanmax(hi[-DJ.YEAR_BARS:]))
    # NEGATIVE: never a 52-week high before a full window of bars exists
    assert feat["w52_high"].iloc[: DJ.YEAR_BARS - 1].isna().all()
    assert np.isfinite(feat["w52_high"].iloc[DJ.YEAR_BARS - 1])


# --------------------------------------------------------------------------
# fix round 2 (2026-10-16, the WP-A critic) — Ajay 2026-10-16: "especially on
# the 60% 70% down stocks"
# --------------------------------------------------------------------------
def _depth_frame(frac):
    """_up() (no read on its own) with one high 100 sessions back putting the
    close `frac` under the 52-week high (and under the frame-only ATH)."""
    df = _up()
    c = float(df["close"].iloc[-1])
    return _set(df, -100, high=c / (1 - frac))


def test_119_NEG_depth_reads_compare_the_served_2dp_number_B9():
    """B9 extended to the depth reads: the read, the chip and the primary cell
    agree at the line — a raw 59.996 (served 60.00) meets the 60% read, a raw
    59.994 (served 59.99) does not."""
    rv = DJ.reads_vector(np.array([59.996, 59.994, 60.0, np.nan]),
                         np.array([59.996, 59.994, 60.0, np.nan]), np.zeros(4, dtype=bool))
    assert rv["w52"].tolist() == [True, False, True, False]
    assert rv["ath"].tolist() == [True, False, True, False]
    df = _depth_frame(0.59996)
    feat = DJ.frame_features(df)
    raw = float(feat["pct_below_52w"].iloc[-1])
    assert raw == pytest.approx(59.996, abs=1e-6) and raw < DJ.DOWN_PCT     # the RAW % is under the line
    r = _read(df)
    assert r["status"] == "fired"
    assert r["pct_below_52w"] == 60.0 and "w52" in r["reads"]               # the card
    assert r["w52"]["pct_below"] == 60.0 and DJ.tile_filter(r)["w52_60"] is True   # the chip
    assert r["pct_below_ath"] == 60.0 and "ath" in r["reads"]               # the ATH read, same rule
    n = len(feat)
    cells = DJ.study_cells(feat, pct_below_ath=None, floor=np.ones(n, dtype=bool))
    assert bool(cells["primary"][-1]) is True                               # the primary cell
    # NEGATIVE: served 59.99 never meets the 60% read anywhere
    df2 = _depth_frame(0.59994)
    feat2 = DJ.frame_features(df2)
    assert round(float(feat2["pct_below_52w"].iloc[-1]), 2) == 59.99
    r2 = _read(df2)
    assert r2["status"] == "no_downtrend" and r2["reads"] == []
    cells2 = DJ.study_cells(feat2, pct_below_ath=None, floor=np.ones(len(feat2), dtype=bool))
    assert bool(cells2["primary"][-1]) is False and bool(cells2["any_read"][-1]) is False


def _half_frame():
    """A 300-bar downtrend whose 52-week (and frame-only all-time) high is 200.00
    and whose doji closes at 80.01 — raw depth 59.995, an exact half at 2 dp
    (the WP-A critic's probe, fix round 1)."""
    idx = pd.bdate_range(end=pd.Timestamp(KL.prev_market_day(SESSION)), periods=300)
    n = 300
    o = np.full(n, 79.8); c = np.full(n, 79.8); h = np.full(n, 80.4); lo = np.full(n, 79.0)
    o[:100] = 198.0; c[:100] = 198.0; h[:100] = 199.0; lo[:100] = 197.0
    h[60] = 200.0
    lo[291] = 78.0
    o[-1], c[-1], h[-1], lo[-1] = 80.008, 80.01, 81.2, 78.6
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c,
                         "volume": np.full(n, 1e6)}, index=idx)


def test_119b_NEG_an_exact_half_depth_rounds_like_the_served_number_B9():
    """Fix round 1: np.round read 59.995 as 60.00 while the card / chip served
    59.99. The read now uses the served rule: read, chip and primary agree."""
    raw = (1.0 - 80.01 / 200.0) * 100.0
    assert float(np.round(raw, 2)) == 60.0 and round(raw, 2) == 59.99      # the trap exists
    rv = DJ.reads_vector(np.array([raw]), np.array([raw]), np.zeros(1, dtype=bool))
    assert rv["w52"].tolist() == [False] and rv["ath"].tolist() == [False]
    df = _half_frame()
    feat = DJ.frame_features(df)
    assert round(float(feat["pct_below_52w"].iloc[-1]), 2) == 59.99
    r = _read(df)
    assert r["pct_below_52w"] == 59.99 and "w52" not in r["reads"]          # the card
    assert r["pct_below_ath"] == 59.99 and "ath" not in r["reads"]          # the ATH read
    tf = DJ.tile_filter(r)
    assert tf["w52_60"] is not True and tf["ath_60"] is not True            # the chips
    if r["w52"] is not None:
        assert r["w52"]["pct_below"] == 59.99 and tf["w52_60"] is False
    cells = DJ.study_cells(feat, pct_below_ath=None, floor=np.ones(len(feat), dtype=bool))
    assert bool(cells["primary"][-1]) is False                              # the primary cell
    # positive twin: one cent lower on the close (raw 60.0) meets every read
    df2 = _half_frame()
    _set(df2, -1, close=80.0, open=79.998)
    r2 = _read(df2)
    assert r2["status"] == "fired" and "w52" in r2["reads"] and r2["pct_below_52w"] == 60.0
    assert DJ.tile_filter(r2)["w52_60"] is True
    feat2 = DJ.frame_features(df2)
    cells2 = DJ.study_cells(feat2, pct_below_ath=None, floor=np.ones(len(feat2), dtype=bool))
    assert bool(cells2["primary"][-1]) is True


def _deep_clause(t: str) -> str:
    i = t.index("Under the 52-week high by")
    return t[i: t.index(".", i) + 1]


def test_120_the_70pct_cell_is_served_with_its_counts_and_no_verdict_word(monkeypatch):
    lit = _literal()
    lit["cells"]["w52_70"].update(n_events=69, n_dates=59)
    monkeypatch.setattr(DSM, "MEASURED", lit)
    s = DJ.study_block()
    assert s["status"] == "measured"
    want = (f"Under the 52-week high by {DJ.DEPTH_CHIPS[2]}%+: 69 dojis on 59 sessions — too few to "
            "read (pre-declared).")
    assert want in s["text"] and DJ.DEPTH_CHIPS[2] == 70
    clause = _deep_clause(s["text"])
    assert clause == want
    for w in DJ._verdict_words().values():                                  # NEGATIVE: no verdict word
        assert w not in clause, w
    for w in ("separates", "inverted", "no difference", "returned more", "returned less"):
        assert w not in clause.lower(), w
    _clean(s["text"])
    lit2 = _literal()
    lit2["cells"]["w52_70"].update(n_events=1234, n_dates=59)
    monkeypatch.setattr(DSM, "MEASURED", lit2)
    t2 = DJ.study_block()["text"]
    assert "1,234 dojis on 59 sessions" in t2
    # fix round 1: counts that clear the minimums never say "too few to read"
    c2 = _deep_clause(t2)
    assert c2 == (f"Under the 52-week high by {DJ.DEPTH_CHIPS[2]}%+: 1,234 dojis on 59 sessions — "
                  f"{DJ.DEEP_PREDECLARED_PREFIX} — {DSM.EXPLORATORY_LABEL}.")
    assert "too few" not in c2 and DSM.EXPLORATORY_LABEL in c2
    for w in DJ._verdict_words().values():
        assert w not in c2, w
    _clean(t2)
    # NEGATIVE: either count under its minimum keeps "too few to read"
    for ev, d in ((DSM.MIN_CELL_EVENTS - 1, 59), (1234, DSM.MIN_CELL_DATES - 1)):
        lit3 = _literal()
        lit3["cells"]["w52_70"].update(n_events=ev, n_dates=d)
        monkeypatch.setattr(DSM, "MEASURED", lit3)
        assert DJ.DEEP_TOO_FEW_WORDS in _deep_clause(DJ.study_block()["text"]), (ev, d)
    for ev, d in ((DSM.MIN_CELL_EVENTS, DSM.MIN_CELL_DATES),):
        lit4 = _literal()
        lit4["cells"]["w52_70"].update(n_events=ev, n_dates=d)
        monkeypatch.setattr(DSM, "MEASURED", lit4)
        assert DJ.DEEP_PREDECLARED_PREFIX in _deep_clause(DJ.study_block()["text"])


def test_121_NEG_a_verdict_on_the_70pct_cell_is_never_served_and_a_missing_cell_is_malformed(monkeypatch):
    lit = _literal()
    monkeypatch.setattr(DSM, "MEASURED", lit)
    base = DJ.study_block()["text"]
    lit2 = _literal()
    lit2["cells"]["w52_70"]["verdict"] = "separates"                        # a stray verdict key
    monkeypatch.setattr(DSM, "MEASURED", lit2)
    t2 = DJ.study_block()["text"]
    assert t2 == base and DJ._verdict_words()["separates"] not in _deep_clause(t2)
    lit3 = _literal()
    del lit3["cells"]["w52_70"]
    monkeypatch.setattr(DSM, "MEASURED", lit3)
    assert DJ.study_block()["status"] == "unmeasured"
    lit4 = _literal()
    del lit4["cells"]["w52_70"]["n_dates"]
    monkeypatch.setattr(DSM, "MEASURED", lit4)
    assert DJ.study_block()["text"] == DJ.NOTE_PENDING


def test_122_his_call_q23_bad_bars_reading_is_recorded():
    """Q23: a hole in the reference window counts as bad_bars (test_29) — the
    reading is recorded in the module docstring's HIS CALL list."""
    doc = DJ.__doc__ or ""
    assert "HIS CALL" in doc and "Q23" in doc and "B13" in doc and "test_29" in doc
    df = _fire()
    _set(df, -5, low=np.nan)
    assert _st(df) == "bad_bars"                                            # the code is kept
    assert "or an unreadable bar in the" in DJ.count_line({}, body=5, min_tier_label="Ok",
                                                          need_date=LAST)
