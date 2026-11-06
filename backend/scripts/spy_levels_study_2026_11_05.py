"""SPY levels study 2026-11-05 — one pre-registered family of 24 intraday level rules on SPY.

THE ASK (Ajay 2026-11-05, verbatim)
  "can you also setup SPY calls and shorts please based on Supply demand and previous day high and
   lows and improved strategy with some resarch and bake that in to Auto pilot I wanna check it out"

NOTHING HERE IS A VERDICT until the outcome run reads the sealed OOS half ONCE, after the prereg
`docs/research/spy_levels_2026_11_05_prereg.md` is committed (its sha256 lives in
`backend/scripts/spy_levels_prereg.sha256`). No lane, flag, order or broker is touched; the script
never imports `trading.*` (the 0DTE lane's window constants are re-typed below and pinned by a test).

FAMILY (24 = source x mode x target x vwap; spec design.md section 3.4)
  source  pdhl  the previous RTH session's high / low from its 1-minute bars
                (`indicators.session_high_low(prev_doc, "rth")`), as LINES (lo == hi)
          fine  the strip's FINE bands (`zone_store.build_doc(..., compute=index_zones._fine_compute)`),
                rows dated before the session only; OVERLAPPING bands union-merged for the trigger
                (the strip's own list is unchanged)
  mode    cross          LONG c_prev <= hi < c ; SHORT c_prev >= lo > c
          touch_reverse  LONG c_prev > hi, L <= hi, c > hi ; SHORT mirrored
  target  next_or_flatten (the next same-source level beyond the entry, none -> flatten, trade kept)
          2R (`daytrading.signal_lab.TARGET_R`) ; flatten_only
  vwap    off | on (LONG needs c > session VWAP read at the signal bar's last minute)
  stop    the 5-minute SIGNAL BAR's extreme (the signal-lab wick stop); entry at the next 1-minute
          open; one trade per session (the first eligible signal); flat at FLATTEN_ET.

GATES: the strategy lab's A + B + C (`scripts.strategy_lab_2026_10_29`), with the deviations the
prereg states: bootstrap clusters = whole DATES, TOO SMALL on entry-WEEKS, two size-matched placebos
(B1 whole window, B2 holding-time matched; B = both), DSR over the effective (de-duplicated) trial
list. Long and short are judged on their own lines; pooled is the candidate. A null is a result.

MODES (each in its own throwaway --rm container on the compose network, outside 09:00-16:30 ET)
  fetch     minute docs through `daytrading.data.load_intraday_range` (cache hit = no call), daily
            bars once (`prices.closed_daily_frame(..., use_cache=False)`) -> <data>/spy_daily_5y.csv
  fetch --cache-only   the same accounting with NO Massive call and NO write: minute docs from the
            cache, daily bars from the price cache (`prices.bulk_cached_frames`, a read)
  smoke     network + writes blocked; SMOKE_SESSIONS IS sessions taken at a STRIDE across the IS half
  is        the whole IS half; prints the pre-registered pick
  outcome   IS pick, then the OOS half read ONCE; 24 ledger rows T02..T25
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import inspect
import json
import math
import sys
import time
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from statistics import NormalDist
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from daytrading import data as DATA  # noqa: E402
from daytrading import indicators  # noqa: E402
from daytrading.signal_lab import TARGET_R  # noqa: E402
from options.opex import CONTRACT_MULTIPLIER  # noqa: E402
from options.zero_dte import MAX_SPREAD_PCT, TARGET_DELTA  # noqa: E402
from scripts import resiliency_study as RS  # noqa: E402
from scripts import strategy_lab_2026_10_29 as LAB  # noqa: E402
from sepa import prices  # noqa: E402
from supply_demand import index_zones, price_zones, timeframes, zone_store  # noqa: E402

ET = ZoneInfo("America/New_York")
STUDY = "spy_levels_study_2026_11_05"
SCRIPT = "backend/scripts/spy_levels_study_2026_11_05.py"
PREREG_DOC = "docs/research/spy_levels_2026_11_05_prereg.md"
SHA_FILE = Path(__file__).resolve().with_name("spy_levels_prereg.sha256")
SYMBOL = "SPY"
DAILY_PERIOD = "5y"
COHORT_PERIOD = "2y"
DAILY_CSV = "spy_daily_5y.csv"
DAILY_CSV_CACHE_ONLY = "spy_daily_price_cache.csv"
MODES = ("fetch", "smoke", "is", "outcome")

# ── MINE (design.md section 1.8; every value pinned by test 10) ─────────────────────────────
FETCH_PAUSE_SEC = 1.0          # <= 60 Massive calls a minute
COST_BPS = 1.0                 # per side, of the fill price (task-given)
SLIP_USD = 0.01                # per share per side (task-given; HIS CALL #9)
PLACEBO_WINDOW_MIN = 30        # B2: +-30 minutes around the entry, inside the window
DUP_RHO = 0.95                 # duplicate-trial threshold for the effective DSR list
SUSPECT_DAILY_PCT = 1.0        # a daily H/L this far beyond the RTH print is a bad bar
MINE = {"FETCH_PAUSE_SEC": FETCH_PAUSE_SEC, "COST_BPS": COST_BPS, "SLIP_USD": SLIP_USD,
        "PLACEBO_WINDOW_MIN": PLACEBO_WINDOW_MIN, "DUP_RHO": DUP_RHO,
        "SUSPECT_DAILY_PCT": SUSPECT_DAILY_PCT}

# ── typed in the design itself (section cited), never chosen here ───────────────────────────
BAR_MINUTES = 5                # section 2 "SPY 5-minute closed bars"
PREV_SESSION_MAX_GAP_DAYS = 4  # section 3.1 "> 4 calendar days back -> excluded"
B2_THIN_N = 5                  # section 3.6 "a trade with < 5 candidates is reported b2_thin"
TOP_N_DIFFS = 10               # section 3.7 daily_vs_rth.top10
SMOKE_SESSIONS = 10            # section 5 stage 1 "10 IS sessions" (taken at a stride)
PRIOR_NARRATIVE_N = 15         # section 3.6 C / LEDGER.md narrative count before this study
FIDELITY_TOL = 1e-6            # section 3.1 "Fidelity vs price_cache SPY to 1e-6"
REPORT_PCTLS = (10, 50, 90)    # section 3.7 risk_pct_p10, daily_vs_rth p50 / p90
OVERLAY_DELTA_ATM = 0.50       # section 3.6 overlay "0.50 (task)"
RC_REFUSED = 3                 # section 3.8 "rc 3 = refused, nothing read"
DESIGN = {"BAR_MINUTES": BAR_MINUTES, "PREV_SESSION_MAX_GAP_DAYS": PREV_SESSION_MAX_GAP_DAYS,
          "B2_THIN_N": B2_THIN_N, "TOP_N_DIFFS": TOP_N_DIFFS, "SMOKE_SESSIONS": SMOKE_SESSIONS,
          "PRIOR_NARRATIVE_N": PRIOR_NARRATIVE_N, "FIDELITY_TOL": FIDELITY_TOL,
          "REPORT_PCTLS": REPORT_PCTLS, "OVERLAY_DELTA_ATM": OVERLAY_DELTA_ATM,
          "RC_REFUSED": RC_REFUSED}

# ── re-typed from trading.zero_dte_lane:54-57 (the script never imports trading.*) ──────────
ENTRY_OPEN_ET = dtime(9, 45)
LAST_ENTRY_ET = dtime(14, 30)
FLATTEN_ET = dtime(15, 45)
SIGNAL_MAX_AGE_SEC = 180
PLACEBO_EXCL_MIN = timedelta(seconds=SIGNAL_MAX_AGE_SEC) // timedelta(minutes=1)

# ── imported ────────────────────────────────────────────────────────────────────────────────
ATR_PERIOD = inspect.signature(indicators.atr).parameters["period"].default
BOOT_DRAWS = LAB.BOOT_DRAWS
PLACEBO_SETS = LAB.PLACEBO_SETS
PLACEBO_BEAT_SHARE = LAB.PLACEBO_BEAT_SHARE
DSR_PASS = LAB.DSR_PASS
SEED = LAB.SEED
MIN_CLUSTERS = LAB.MIN_CLUSTERS
SHOW_DP = LAB.SHOW_DP
FORBIDDEN_WORDS = LAB.FORBIDDEN_WORDS
LEDGER_PATH = LAB.LEDGER_PATH
GATES_RESULTS_REL = "gajjala_gates_2026_10_30/results.json"
OVERLAY_DELTAS = (TARGET_DELTA, OVERLAY_DELTA_ATM)
BAR_RULE = f"{BAR_MINUTES}min"
SATURDAY = calendar.SATURDAY

SOURCES = ("pdhl", "fine")
MODES_SIG = ("cross", "touch_reverse")
TARGETS = ("next_or_flatten", "2R", "flatten_only")
VWAPS = ("off", "on")
FAMILY = [f"{s}|{m}|{t}|vwap_{v}" for s in SOURCES for m in MODES_SIG for t in TARGETS
          for v in VWAPS]
SIDES = ("pooled", "long", "short")
COUNTERS = ("signals_skipped_same_day", "no_next_level", "entry_beyond_stop",
            "both_sides_same_bar", "multi_band_same_bar", "no_entry_bar", "outside_window")
EXIT_STOP, EXIT_TARGET, EXIT_FLAT, EXIT_DATA_END = "stop", "target", "flatten", "data_end"
UNION_SENTENCE = ("The bounds of overlapping FINE bands are merged for the trigger only; the "
                  "strip's own band list is unchanged.")
OVERLAY_NOTE = ("approximation: delta-scaled share moves; premium, theta, gamma and the "
                f"MAX_SPREAD_PCT = {MAX_SPREAD_PCT:g} % cap are not modelled; share-level costs only")
ATTEMPTED_FETCHES: list = []
RECORDED_PUTS: list = []
_Z_CI = NormalDist().inv_cdf(1 - (100 - LAB.CI_PCT) / (2 * 100))


FetchRefused = LAB.FetchRefused   # ONE refusal class with the lab's own network guard


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------
def _refuse_fetch(name):
    def _raise(*a, **k):
        ATTEMPTED_FETCHES.append(name)
        raise FetchRefused(f"{name} refused: the SPY levels study is read-only in this mode")
    return _raise


def _record_put(symbol, day, df):
    RECORDED_PUTS.append(f"{symbol}:{day}")
    return None


def block_network_and_writes() -> None:
    """Every Massive / HTTP path -> FetchRefused; every pymongo write -> a recorded no-op;
    `data._mongo_put_day` -> a recorded no-op (the cache is read via `_mongo_get_day` only)."""
    LAB.block_network()
    RS.block_writes()
    DATA._fetch_massive_minute = _refuse_fetch("data._fetch_massive_minute")
    DATA._mongo_put_day = _record_put


def _rc3(msg) -> int:
    print(f"REFUSED: {msg}", file=sys.stderr)
    return RC_REFUSED


# ---------------------------------------------------------------------------
# calendar + cohort
# ---------------------------------------------------------------------------
def weekdays(a: date, b: date) -> list:
    out, cur = [], a
    while cur <= b:
        if cur.weekday() < SATURDAY:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def default_as_of(now_et: datetime) -> date:
    """The last weekday strictly before the run's ET date (`data.load_intraday` re-fetches today)."""
    d = now_et.astimezone(ET).date() - timedelta(days=1)
    while d.weekday() >= SATURDAY:
        d -= timedelta(days=1)
    return d


def from_day_of(as_of: date) -> date:
    return as_of - timedelta(days=prices.PERIOD_DAYS[COHORT_PERIOD])


def split_weekdays(cohort_first: date, as_of: date) -> tuple:
    """Calendar weekdays of [cohort_first, as_of] in halves (no doc knowledge needed)."""
    W = weekdays(cohort_first, as_of)
    k = len(W) // 2
    return W[:k], W[k:]


def is_half_day(d: date) -> bool:
    return d.isoformat() in timeframes.HALF_DAYS


def is_holiday(d: date) -> bool:
    return timeframes._is_holiday(datetime.combine(d, dtime(0, 0)))


def prev_session(day: date, has_doc: Callable) -> Optional[date]:
    """The nearest earlier weekday whose cached doc has RTH rows, at most
    PREV_SESSION_MAX_GAP_DAYS calendar days back (a half-day may serve)."""
    cur = day - timedelta(days=1)
    while (day - cur).days <= PREV_SESSION_MAX_GAP_DAYS:
        if cur.weekday() < SATURDAY and has_doc(cur):
            return cur
        cur -= timedelta(days=1)
    return None


# ---------------------------------------------------------------------------
# loaders
# ---------------------------------------------------------------------------
def cache_loader(get: Optional[Callable] = None) -> Callable:
    """day -> the cached 1-minute doc (premarket + RTH, afterhours dropped) or None.
    `_mongo_get_day` only (or the injected raw getter); memoised for the run."""
    memo: dict = {}
    get = get or (lambda d: DATA._mongo_get_day(SYMBOL, d))

    def load(day: date):
        if day not in memo:
            df = get(day)
            memo[day] = (None if df is None or df.empty
                         else DATA._filter_sessions(df, True, False))
        return memo[day]
    return load


def rth_of(doc) -> Optional[pd.DataFrame]:
    if doc is None or len(doc) == 0 or "session" not in doc.columns:
        return None
    r = doc[doc["session"] == "rth"]
    return r if len(r) else None


def has_doc_fn(load_day: Callable) -> Callable:
    return lambda d: rth_of(load_day(d)) is not None


def fetch_history(from_day: date, as_of: date, *, pause_sec: float, loader: Callable,
                  cached: Callable, sleep: Callable = time.sleep, cache_only: bool = False,
                  failed: Callable = DATA.last_fetch_failed) -> dict:
    """Per weekday in [from_day, as_of]: a cache hit costs nothing; a miss is ONE
    `data.load_intraday_range(SPY, d, d)` call then `pause_sec`; a provider failure waits
    `data._CB_COOLDOWN_SEC` and retries that day ONCE (listed in `fetch_retried`); a day that
    fails again is listed in `fetch_failed`. `cache_only` never calls the loader."""
    days = weekdays(from_day, as_of)
    n_cached, fetched, empty, fails, retried, present = 0, [], [], [], [], []
    for d in days:
        if cached(d) is not None:
            n_cached += 1
            present.append(d)
            continue
        if cache_only:
            empty.append(d.isoformat())
            continue
        df = loader(d)
        if (df is None or not len(df)) and failed():
            sleep(DATA._CB_COOLDOWN_SEC)
            retried.append(d.isoformat())
            df = loader(d)
            if (df is None or not len(df)) and failed():
                fails.append(d.isoformat())
                sleep(pause_sec)
                continue
        if df is not None and len(df):
            fetched.append(d.isoformat())
            present.append(d)
        else:
            empty.append(d.isoformat())
        sleep(pause_sec)
    return {"sessions_requested": len(days), "sessions_cached_before": n_cached,
            "sessions_fetched": len(fetched), "fetched": fetched, "empty": empty,
            "fetch_failed": fails, "fetch_retried": retried,
            "cohort_first": present[0].isoformat() if present else None,
            "cache_only": bool(cache_only)}


def normalise_daily(df) -> Optional[pd.DataFrame]:
    if df is None or len(df) == 0:
        return None
    out = df[["open", "high", "low", "close", "volume"]].astype(float).copy()
    idx = pd.DatetimeIndex(out.index)
    if idx.tz is not None:
        idx = idx.tz_convert(ET).tz_localize(None)
    out.index = idx.normalize()
    out.index.name = "date"
    return out.sort_index()


def save_daily(df, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index_label="date", float_format="%.17g")


def load_daily(csv_path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=["date"]).set_index("date")
    return normalise_daily(df)


def price_cache_frame() -> Optional[pd.DataFrame]:
    """The price cache's SPY frame, ONE read (`bulk_cached_frames` never fetches)."""
    return normalise_daily(prices.bulk_cached_frames([SYMBOL]).get(SYMBOL))


def daily_fidelity(daily, ref) -> dict:
    if daily is None or ref is None:
        return {"price_cache_rows_compared": 0, "price_cache_mismatch_n": None}
    common = daily.index.intersection(ref.index)
    cols = ["open", "high", "low", "close"]
    diff = (daily.loc[common, cols] - ref.loc[common, cols]).abs().max(axis=1)
    return {"price_cache_rows_compared": int(len(common)),
            "price_cache_mismatch_n": int((diff > FIDELITY_TOL).sum())}


# ---------------------------------------------------------------------------
# levels (point-in-time)
# ---------------------------------------------------------------------------
def fine_raw_for(daily, day: date) -> Optional[list]:
    """The strip's FINE bands for session `day`: `zone_store.build_doc` drops rows dated `day`
    and later itself; None when it returns no doc (< zone_store.MIN_BARS prior rows)."""
    doc = zone_store.build_doc(SYMBOL, daily, day, compute=index_zones._fine_compute)
    if not doc or not doc.get("bands"):
        return None
    return [{"lo": float(b["lo"]), "hi": float(b["hi"]), "kind": b["kind"]} for b in doc["bands"]]


def pdhl_raw_for(prev_doc) -> Optional[list]:
    rth = indicators.session_high_low(prev_doc, "rth") if prev_doc is not None else None
    if not rth:
        return None
    return [{"lo": rth["high"], "hi": rth["high"], "kind": "pdh"},
            {"lo": rth["low"], "hi": rth["low"], "kind": "pdl"}]


def union_overlaps(bands) -> list:
    """Bands sorted by lo; two bands OVERLAP when b.lo <= cur.hi (touching counts) and become
    ONE band {lo: min, hi: max, kind: "merged", members}. No distance parameter."""
    out: list = []
    for b in sorted((dict(x) for x in bands or []), key=lambda z: (z["lo"], z["hi"])):
        if out and b["lo"] <= out[-1]["hi"]:
            cur = out[-1]
            members = cur.get("members") or [{"lo": cur["lo"], "hi": cur["hi"],
                                               "kind": cur["kind"]}]
            members = members + [{"lo": b["lo"], "hi": b["hi"], "kind": b["kind"]}]
            out[-1] = {"lo": min(cur["lo"], b["lo"]), "hi": max(cur["hi"], b["hi"]),
                       "kind": "merged", "members": members}
        else:
            out.append(b)
    return out


def levels_for(daily, day: date, source: str, load_day: Callable,
               has_doc: Optional[Callable] = None) -> Optional[list]:
    """The merged edge set one variant trades on `day` (None = unavailable)."""
    if source == "fine":
        raw = fine_raw_for(daily, day)
    else:
        p = prev_session(day, has_doc or has_doc_fn(load_day))
        raw = pdhl_raw_for(load_day(p)) if p is not None else None
    return union_overlaps(raw) if raw else None


# ---------------------------------------------------------------------------
# bars
# ---------------------------------------------------------------------------
def to_et(idx) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(idx)
    return (idx.tz_localize("UTC") if idx.tz is None else idx).tz_convert(ET)


def five_min(rth1m) -> Optional[pd.DataFrame]:
    return timeframes.resample_ohlcv(rth1m, BAR_RULE)


def expected_labels(day: date) -> list:
    """ET labels of a complete RTH 5-minute frame: 09:35 ... 16:00."""
    start = datetime.combine(day, DATA.ET_RTH_OPEN, tzinfo=ET)
    end = datetime.combine(day, DATA.ET_RTH_CLOSE, tzinfo=ET)
    out, t = [], start + timedelta(minutes=BAR_MINUTES)
    while t <= end:
        out.append(t)
        t += timedelta(minutes=BAR_MINUTES)
    return out


def session_frame(day: date, doc) -> tuple:
    """(session dict, None) or (None, reason): the 1-minute RTH arrays, the 5-minute frame with
    ET labels, the session VWAP and the 5-minute ATR (diagnostic)."""
    rth = rth_of(doc)
    if rth is None:
        return None, "no_doc"
    rth = rth.sort_index()
    bars5 = five_min(rth)
    if bars5 is None or len(bars5) == 0:
        return None, "hole_5m"
    lab_et = to_et(bars5.index)
    want = expected_labels(day)
    have = set(lab_et.to_pydatetime())
    if any(w not in have for w in want) or len(bars5) != len(want):
        return None, "hole_5m"
    vw = indicators.vwap_session(doc.sort_index(), session="rth")
    et1 = to_et(rth.index)
    tmin = np.array([t.time() for t in et1])
    in_win = np.array([ENTRY_OPEN_ET <= t < LAST_ENTRY_ET for t in tmin])
    flat = np.flatnonzero(np.array([t >= FLATTEN_ET for t in tmin]))
    atr5 = indicators.atr(bars5, period=ATR_PERIOD)
    return {"date": day, "rth": rth, "idx_utc": pd.DatetimeIndex(rth.index), "et1": et1,
            "open": rth["open"].to_numpy(float), "high": rth["high"].to_numpy(float),
            "low": rth["low"].to_numpy(float), "close": rth["close"].to_numpy(float),
            "in_win": in_win, "flat_idx": int(flat[0]) if len(flat) else None,
            "bars5": bars5, "lab_et": lab_et, "vwap": vw.dropna(),
            "atr5": atr5.to_numpy(float) if len(atr5) else np.full(len(bars5), np.nan),
            "day_range_pct": float((rth["high"].max() - rth["low"].min()) / rth["low"].min()
                                   * 100)}, None


def usable_sessions(days, load_day: Callable, daily, has_doc: Optional[Callable] = None,
                    flagged_days: Optional[set] = None) -> tuple:
    """(sessions, excluded[{date, reason}]) — every exclusion listed with its reason."""
    has_doc = has_doc or has_doc_fn(load_day)
    flagged_days = flagged_days or set()
    keep, excl = [], []
    for d in days:
        reason = None
        if d.weekday() >= SATURDAY:
            reason = "weekend"
        elif is_half_day(d):
            reason = "half_day"
        elif is_holiday(d):
            reason = "holiday"
        if reason:
            excl.append({"date": d.isoformat(), "reason": reason})
            continue
        sess, reason = session_frame(d, load_day(d))
        if sess is None:
            excl.append({"date": d.isoformat(), "reason": reason})
            continue
        p = prev_session(d, has_doc)
        if p is None:
            excl.append({"date": d.isoformat(), "reason": "prev_session_gap"})
            continue
        fine_raw = fine_raw_for(daily, d)
        if not fine_raw:
            excl.append({"date": d.isoformat(), "reason": "no_bands"})
            continue
        pdhl_raw = pdhl_raw_for(load_day(p))
        if not pdhl_raw:
            excl.append({"date": d.isoformat(), "reason": "prev_session_gap"})
            continue
        sess.update(prev=p, prev_half=is_half_day(p), fine_raw=fine_raw, pdhl_raw=pdhl_raw,
                    levels={"fine": union_overlaps(fine_raw), "pdhl": union_overlaps(pdhl_raw)},
                    flagged=d.isoformat() in flagged_days)
        keep.append(sess)
    return keep, excl


# ---------------------------------------------------------------------------
# signals
# ---------------------------------------------------------------------------
def _fires(mode, side, b, c_prev, H, L, c) -> bool:
    if mode == "cross":
        return (c_prev <= b["hi"] < c) if side > 0 else (c < b["lo"] <= c_prev)
    if side > 0:
        return c_prev > b["hi"] and L <= b["hi"] and c > b["hi"]
    return c_prev < b["lo"] and H >= b["lo"] and c < b["lo"]


def signals_for(bars5, bands, mode: str, vwap, vwap_align: bool, lab_et=None) -> tuple:
    """([signal], counters) over closed 5-minute bars. A bar that fires BOTH sides is skipped
    (counted); several same-side bands -> the one whose fired edge is nearest the close."""
    cnt = {"both_sides_same_bar": 0, "multi_band_same_bar": 0}
    out = []
    if bars5 is None or len(bars5) < 2 or not bands:
        return out, cnt
    lab_et = lab_et if lab_et is not None else to_et(bars5.index)
    O, H, L, C = (bars5[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    for k in range(1, len(bars5)):
        c_prev, c = C[k - 1], C[k]
        fired = {s: [b for b in bands if _fires(mode, s, b, c_prev, H[k], L[k], c)]
                 for s in (1, -1)}
        if fired[1] and fired[-1]:
            cnt["both_sides_same_bar"] += 1
            continue
        side = 1 if fired[1] else (-1 if fired[-1] else 0)
        if not side:
            continue
        cands = fired[side]
        if len(cands) > 1:
            cnt["multi_band_same_bar"] += 1
        band = min(cands, key=lambda b: abs((b["hi"] if side > 0 else b["lo"]) - c))
        t_close_utc = pd.Timestamp(bars5.index[k])
        if vwap_align:
            v = vwap.asof(t_close_utc - pd.Timedelta(minutes=1)) if len(vwap) else float("nan")
            if not (v == v) or not ((c > v) if side > 0 else (c < v)):
                continue
        out.append({"k": k, "side": side, "band": band, "c": float(c),
                    "stop": float(L[k] if side > 0 else H[k]), "t_close_utc": t_close_utc,
                    "t_close_et": lab_et[k]})
    return out, cnt


def next_level(bands, entry: float, side: int) -> Optional[float]:
    if side > 0:
        lv = [b["lo"] for b in bands if b["lo"] > entry]
        return min(lv) if lv else None
    lv = [b["hi"] for b in bands if b["hi"] < entry]
    return max(lv) if lv else None


def first_trade(signals, sess) -> tuple:
    """(trade or None, counters): the FIRST eligible signal of the session; later eligible
    signals are counted, never scored."""
    cnt = {k: 0 for k in ("signals_skipped_same_day", "entry_beyond_stop", "no_entry_bar",
                          "outside_window")}
    trade = None
    idx = sess["idx_utc"]
    flat = sess["flat_idx"]
    for s in signals:
        i = int(idx.searchsorted(s["t_close_utc"], side="left"))
        if i >= len(idx) or (flat is not None and i >= flat):
            cnt["no_entry_bar"] += 1
            continue
        if not sess["in_win"][i]:
            cnt["outside_window"] += 1
            continue
        if trade is not None:
            cnt["signals_skipped_same_day"] += 1
            continue
        entry = float(sess["open"][i])
        if (entry <= s["stop"]) if s["side"] > 0 else (entry >= s["stop"]):
            cnt["entry_beyond_stop"] += 1
            continue
        trade = dict(s, entry_idx=i, entry=entry)
    return trade, cnt


# ---------------------------------------------------------------------------
# exits — ONE engine for the strategy and both placebos
# ---------------------------------------------------------------------------
def net_of(gross_pct, entry, *, cost_bps=COST_BPS, slip_usd=SLIP_USD):
    return gross_pct - 2 * (cost_bps / 100 + slip_usd / np.asarray(entry, float) * 100)


def candidate_outcomes(sess, side: int, stop_dist: float, target_dist: Optional[float], *,
                       idxs=None, cost_bps=COST_BPS, slip_usd=SLIP_USD) -> dict:
    """For every candidate entry minute i (default: every minute in the entry window): enter at
    open[i], stop open[i] - side*stop_dist, target open[i] + side*target_dist (None = flatten),
    walk bars j >= i: stop first (exit min(open[j], stop) for a long), then target (max(open[j],
    target)), same minute both -> STOP (ict/backtest.py:35); at the first bar >= FLATTEN_ET exit
    at its open; no such bar -> the last close (data_end)."""
    O, Hh, Ll, Cc = sess["open"], sess["high"], sess["low"], sess["close"]
    n = len(O)
    flat = sess["flat_idx"]
    end = flat if flat is not None else n
    I = np.flatnonzero(sess["in_win"]) if idxs is None else np.asarray(idxs, dtype=int)
    exit_px = np.empty(len(I))
    reason = np.empty(len(I), dtype=object)
    exit_i = np.empty(len(I), dtype=int)
    for q, i in enumerate(I):
        e = O[i]
        st = e - side * stop_dist
        tg = None if target_dist is None else e + side * target_dist
        lo, hi = Ll[i:end], Hh[i:end]
        hit_s = (lo <= st) if side > 0 else (hi >= st)
        js = int(np.argmax(hit_s)) if hit_s.any() else None
        jt = None
        if tg is not None:
            hit_t = (hi >= tg) if side > 0 else (lo <= tg)
            jt = int(np.argmax(hit_t)) if hit_t.any() else None
        if js is not None and (jt is None or js <= jt):
            j = i + js
            o = O[j] if j > i else e
            exit_px[q] = min(o, st) if side > 0 else max(o, st)
            reason[q], exit_i[q] = EXIT_STOP, j
        elif jt is not None:
            j = i + jt
            o = O[j] if j > i else e
            exit_px[q] = max(o, tg) if side > 0 else min(o, tg)
            reason[q], exit_i[q] = EXIT_TARGET, j
        elif flat is not None:
            exit_px[q], reason[q], exit_i[q] = O[flat], EXIT_FLAT, flat
        else:
            exit_px[q], reason[q], exit_i[q] = Cc[n - 1], EXIT_DATA_END, n - 1
    entry = O[I]
    gross = side * (exit_px - entry) / entry * 100
    return {"idx": I, "entry": entry, "exit": exit_px, "reason": reason, "exit_idx": exit_i,
            "gross_pct": gross, "net_pct": net_of(gross, entry, cost_bps=cost_bps,
                                                  slip_usd=slip_usd)}


def parse_key(key: str) -> dict:
    s, m, t, v = key.split("|")
    return {"source": s, "mode": m, "target": t, "vwap_align": v == "vwap_on"}


def target_dist_of(target: str, entry: float, stop: float, nxt: Optional[float]):
    risk = abs(entry - stop)
    if target == "2R":
        return TARGET_R * risk
    if target == "next_or_flatten":
        return None if nxt is None else abs(nxt - entry)
    return None


def trade_row(sess, key, sig, split: str) -> dict:
    p = parse_key(key)
    side, entry, stop = sig["side"], sig["entry"], sig["stop"]
    bands = sess["levels"][p["source"]]
    nxt = next_level(bands, entry, side)
    td = target_dist_of(p["target"], entry, stop, nxt)
    sd = abs(entry - stop)
    o = candidate_outcomes(sess, side, sd, td, idxs=[sig["entry_idx"]])
    k = sig["k"]
    atr = sess["atr5"][k] if k < len(sess["atr5"]) else float("nan")
    risk_pct = sd / entry * 100
    room_pct = abs(nxt - entry) / entry * 100 if nxt is not None else None
    net = float(o["net_pct"][0])
    return {"date": sess["date"].isoformat(), "week": LAB._week_monday(sess["date"].isoformat()),
            "variant": key, "split": split, "side": "long" if side > 0 else "short",
            "sign": side, "source_band_lo": sig["band"]["lo"], "source_band_hi": sig["band"]["hi"],
            "signal_bar_t_close": sig["t_close_et"].isoformat(),
            "t_entry": sess["et1"][sig["entry_idx"]].isoformat(), "entry_idx": sig["entry_idx"],
            "entry": entry, "stop": stop, "stop_dist": sd,
            "target": None if td is None else entry + side * td, "target_dist": td,
            "exit": float(o["exit"][0]), "exit_reason": o["reason"][0],
            "gross_pct": float(o["gross_pct"][0]), "net_pct": net,
            "net_r": net / 100 * entry / sd, "risk_pct": risk_pct, "room_pct": room_pct,
            "room_over_risk": room_pct / risk_pct if room_pct is not None else None,
            "stop_over_atr": sd / atr if atr == atr and atr > 0 else None,
            "atr5_pct": atr / sig["c"] * 100 if atr == atr else None,
            "no_next_level": p["target"] == "next_or_flatten" and nxt is None,
            "flagged": bool(sess.get("flagged")) and p["source"] == "fine"}


def run_variant(sessions, key: str, split: str) -> tuple:
    """(trades DataFrame, summed counters) for one variant over `sessions`."""
    p = parse_key(key)
    cnt = {k: 0 for k in COUNTERS}
    rows = []
    for sess in sessions:
        sigs, c1 = signals_for(sess["bars5"], sess["levels"][p["source"]], p["mode"],
                               sess["vwap"], p["vwap_align"], lab_et=sess["lab_et"])
        tr, c2 = first_trade(sigs, sess)
        for d in (c1, c2):
            for k, v in d.items():
                cnt[k] += v
        if tr is not None:
            row = trade_row(sess, key, tr, split)
            cnt["no_next_level"] += int(row["no_next_level"])
            rows.append(row)
    return pd.DataFrame(rows), cnt


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def _r(x, dp=SHOW_DP):
    return RS._r(x, dp)


def wilson(k: int, n: int) -> Optional[list]:
    if n <= 0:
        return None
    z = _Z_CI
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [_r(c - h), _r(c + h)]


def n_weeks(trades) -> int:
    if trades is None or len(trades) == 0:
        return 0
    return int(pd.Series([LAB._week_monday(d) for d in trades["date"]]).nunique())


def _lab_frame(trades) -> pd.DataFrame:
    """The lab's column names: `t` (entry day), `net_ret` / `gross_ret` (fractions)."""
    return pd.DataFrame({"t": trades["date"].to_numpy(),
                         "net_ret": trades["net_pct"].to_numpy(float) / 100,
                         "gross_ret": trades["gross_pct"].to_numpy(float) / 100})


def _nanmed(v) -> Optional[float]:
    a = np.array([x for x in v if x is not None and x == x], dtype=float)
    return _r(float(np.median(a))) if a.size else None


def max_drawdown_pct(net_pct) -> Optional[float]:
    a = np.asarray(net_pct, dtype=float)
    if a.size == 0:
        return None
    cum = np.concatenate([[0.0], np.cumsum(a)])
    return _r(float(np.max(np.maximum.accumulate(cum) - cum)))


def block(trades, counters=None, n_sessions=None, *, draws=BOOT_DRAWS, seed=SEED) -> dict:
    """The BLOCK of design section 3.7 for one trade set."""
    cnt = {k: int((counters or {}).get(k, 0)) for k in COUNTERS}
    if trades is None or len(trades) == 0:
        A = LAB.cluster_mean_ci([], [])
        return dict({"n_trades": 0, "n_dates": 0, "n_weeks": 0, "trades_per_day": 0.0,
                     "mean_net_pct": None, "ci95_pct": None, "ci_raw_pct": None,
                     "word": A["word"], "pass": False}, **cnt)
    t = trades.sort_values(["date", "t_entry"])
    net = t["net_pct"].to_numpy(float)
    A = LAB.cluster_mean_ci(net / 100, t["date"].astype(str), draws=draws, seed=seed)
    srt = np.sort(net)[::-1]
    top = srt[:max(1, int(math.ceil(len(srt) / 100)))]
    tot = float(np.sum(net))
    nw = n_weeks(t)
    wk = t.groupby("week")["net_pct"].mean()
    sd_w = float(np.std(wk.to_numpy(float), ddof=1)) if len(wk) > 1 else None
    reasons = t["exit_reason"].astype(str)
    wins = int(np.sum(net > 0))
    nr = t["net_r"].to_numpy(float)
    return dict({
        "n_trades": int(len(t)), "n_dates": int(t["date"].nunique()), "n_weeks": nw,
        "trades_per_day": _r(len(t) / n_sessions) if n_sessions else None,
        "mean_net_pct": A["mean_pct"], "ci95_pct": A["ci_pct"], "ci_raw_pct": A["ci_raw_pct"],
        "word": A["word"], "pass": A["word"] == "separates",
        "mean_net_r": _r(float(np.mean(nr))), "median_net_pct": _r(float(np.median(net))),
        "gross_mean_pct": _r(float(t["gross_pct"].mean())),
        "win_rate": _r(wins / len(t)), "win_rate_ci": wilson(wins, len(t)),
        "stop_out_rate": _r(float(np.mean(reasons == EXIT_STOP))),
        "target_rate": _r(float(np.mean(reasons == EXIT_TARGET))),
        "flatten_rate": _r(float(np.mean(reasons.isin([EXIT_FLAT, EXIT_DATA_END])))),
        "risk_pct_median": _nanmed(t["risk_pct"]),
        "risk_pct_p10": _r(float(np.percentile(t["risk_pct"].to_numpy(float), REPORT_PCTLS[0]))),
        "stop_over_atr_median": _nanmed(t["stop_over_atr"]),
        "room_over_risk_median": _nanmed(t["room_over_risk"]),
        "max_drawdown_pct": max_drawdown_pct(net),
        "top1_share": _r(float(np.sum(top)) / tot) if tot > 0 else None,
        "breakeven_cost_bps": _r(LAB.breakeven_cost_bps(_lab_frame(t))),
        "mde_pct": _r(LAB.mde_pct(sd_w, nw)) if sd_w is not None else None}, **cnt)


def placebo_pool(sess, trade, *, window_min: Optional[int], excl_min: int = PLACEBO_EXCL_MIN):
    """Candidate net_pct over the trade's own day, side, stop / target distances: every
    entry-window minute with |m - t_entry| >= excl_min, and within +-window_min when given."""
    td = trade["target_dist"]
    o = candidate_outcomes(sess, int(trade["sign"]), float(trade["stop_dist"]),
                           None if td is None or pd.isna(td) else float(td))
    et = sess["et1"]
    t0 = et[int(trade["entry_idx"])]
    dm = np.abs(np.asarray((et[o["idx"]] - t0) / pd.Timedelta(minutes=1), dtype=float))
    keep = dm >= excl_min
    if window_min is not None:
        keep &= dm <= window_min
    return o["net_pct"][keep], o["idx"][keep]


def placebo_minutes(trades, sessions_by_date: dict, *, window_min: Optional[int],
                    excl_min: int = PLACEBO_EXCL_MIN, sets: int = PLACEBO_SETS,
                    seed: int = SEED + 1, draws: int = BOOT_DRAWS) -> dict:
    """One placebo: per trade one random candidate minute per set; beat share over `sets`;
    the per-trade diff (net - pool mean) through the date-cluster CI. Pass = separates AND
    beat share >= PLACEBO_BEAT_SHARE."""
    if trades is None or len(trades) == 0:
        return {"beat_share": None, "diff_mean_pct": None, "diff_ci_pct": None,
                "word": "too_small", "pass": False, "n": 0, "thin_n": 0}
    pools = []
    for _, tr in trades.iterrows():
        pools.append(placebo_pool(sessions_by_date[tr["date"]], tr, window_min=window_min,
                                  excl_min=excl_min)[0])
    net = trades["net_pct"].to_numpy(float)
    L = np.array([len(p) for p in pools], dtype=int)
    ok = L > 0
    rng = np.random.default_rng(seed)
    flat = np.concatenate(pools) if int(L.sum()) else np.zeros(0)
    off = np.concatenate([[0], np.cumsum(L)[:-1]]).astype(int)
    u = np.floor(rng.random((int(sets), len(L))) * np.maximum(L, 1)).astype(int)
    vals = np.broadcast_to(net, u.shape).copy()
    if ok.any():
        vals[:, ok] = flat[off[ok] + u[:, ok]]
    pj = vals.mean(axis=1)
    beat = float(np.mean(float(np.mean(net)) > pj))
    pool_mean = np.array([float(np.mean(p)) if len(p) else v for p, v in zip(pools, net)])
    d = net - pool_mean
    ci = LAB.cluster_mean_ci(d / 100, trades["date"].astype(str), draws=draws, seed=seed)
    ok_pass = ci["word"] == "separates" and beat >= PLACEBO_BEAT_SHARE
    return {"beat_share": _r(beat), "diff_mean_pct": ci["mean_pct"], "diff_ci_pct": ci["ci_pct"],
            "word": ci["word"], "pass": bool(ok_pass), "n": int(len(trades)),
            "thin_n": int(np.sum(L < B2_THIN_N)), "empty_pool_n": int(np.sum(~ok))}


def sr_of(trades) -> Optional[float]:
    if trades is None or len(trades) == 0:
        return None
    return LAB.moments(LAB.gate_c_series(_lab_frame(trades), "per_entry_day"))["sr"]


def date_series(trades, dates) -> np.ndarray:
    m = {} if trades is None or len(trades) == 0 else dict(zip(trades["date"], trades["net_pct"]))
    return np.array([float(m.get(d, 0.0)) for d in dates])


def duplicate_clusters(variant_series: dict, *, rho: float = DUP_RHO) -> list:
    """Greedy in the dict's (family) order: a variant joins the first representative with
    |Pearson rho| > `rho`, else it opens a cluster. A constant series never joins."""
    reps: list = []
    for k, s in variant_series.items():
        s = np.asarray(s, dtype=float)
        joined = False
        for cl in reps:
            r = np.asarray(variant_series[cl[0]], dtype=float)
            if s.std() > 0 and r.std() > 0 and abs(float(np.corrcoef(s, r)[0, 1])) > rho:
                cl.append(k)
                joined = True
                break
        if not joined:
            reps.append([k])
    return reps


def corr_matrix(variant_series: dict) -> pd.DataFrame:
    keys = list(variant_series)
    M = np.full((len(keys), len(keys)), np.nan)
    for a, ka in enumerate(keys):
        for b, kb in enumerate(keys):
            x, y = np.asarray(variant_series[ka], float), np.asarray(variant_series[kb], float)
            if x.std() > 0 and y.std() > 0:
                M[a, b] = float(np.corrcoef(x, y)[0, 1])
    return pd.DataFrame(M, index=keys, columns=keys)


def gates(trades, sessions_by_date, trial_srs, trial_srs_naive, *, n_sessions,
          counters=None, draws=BOOT_DRAWS, sets=PLACEBO_SETS, seed=SEED) -> dict:
    """A (block), B1 + B2 placebos, C (effective + naive DSR), the verdict, and the clean
    re-computation without flagged trades."""
    blk = block(trades, counters, n_sessions, draws=draws, seed=seed)
    b1 = placebo_minutes(trades, sessions_by_date, window_min=None, sets=sets, seed=seed + 1,
                         draws=draws)
    b2 = placebo_minutes(trades, sessions_by_date, window_min=PLACEBO_WINDOW_MIN, sets=sets,
                         seed=seed + 2, draws=draws)
    B = bool(b1["pass"] and b2["pass"])
    x = LAB.gate_c_series(_lab_frame(trades), "per_entry_day") if len(trades) else np.zeros(0)
    c = LAB.deflated(x, list(trial_srs))
    cn = LAB.deflated(x, list(trial_srs_naive))
    C = c.get("dsr") is not None and c["dsr"] >= DSR_PASS
    gate_c = {"n": c["n"], "sr": c["sr"], "skew": c["skew"], "kurt": c["kurt"], "sr0": c["sr0"],
              "psr0": c["psr0"], "dsr": c["dsr"], "N": c["N"], "sr0_naive": cn["sr0"],
              "dsr_naive": cn["dsr"], "N_naive": cn["N"], "pass": bool(C)}
    n_flag = int(trades["flagged"].sum()) if len(trades) else 0
    a_clean = b_clean = None
    if n_flag:
        clean = trades[~trades["flagged"].astype(bool)]
        a_clean = block(clean, None, n_sessions, draws=draws, seed=seed)["pass"]
        c1 = placebo_minutes(clean, sessions_by_date, window_min=None, sets=sets, seed=seed + 1,
                             draws=draws)
        c2 = placebo_minutes(clean, sessions_by_date, window_min=PLACEBO_WINDOW_MIN, sets=sets,
                             seed=seed + 2, draws=draws)
        b_clean = bool(c1["pass"] and c2["pass"])
    v = LAB.positive_verdict(blk["pass"], B, C, blk["n_weeks"], a_clean=a_clean,
                             b_clean=b_clean, n_flagged=n_flag, n_rows=len(trades))
    v.pop("label", None)
    return {"block": blk, "placebo": {"b1": b1, "b2": b2, "pass": B}, "gate_c": gate_c,
            "verdict": v}


def side_slices(trades) -> dict:
    if trades is None or len(trades) == 0:
        e = pd.DataFrame(columns=["date", "side"])
        return {"pooled": e, "long": e, "short": e}
    return {"pooled": trades, "long": trades[trades["side"] == "long"],
            "short": trades[trades["side"] == "short"]}


def is_pick(is_blocks: dict) -> Optional[dict]:
    """Among variants whose pooled IS block has >= MIN_CLUSTERS entry-weeks: the highest lower
    bound of the IS 95 % CI of net_pct; ties -> family order. None = nothing qualifies."""
    best = None
    for key in FAMILY:
        b = (is_blocks.get(key) or {}).get("pooled") or {}
        ci = b.get("ci_raw_pct")
        if int(b.get("n_weeks") or 0) < MIN_CLUSTERS or not ci or ci[0] is None:
            continue
        if best is None or ci[0] > best["is_lower_ci_pct"]:
            best = {"variant": key, "criterion": "highest IS lower 95% CI of net_pct, pooled, "
                    f">= {MIN_CLUSTERS} IS entry-weeks", "is_lower_ci_pct": ci[0],
                    "n_weeks": int(b["n_weeks"])}
    return best


def overlay(trades, *, draws=BOOT_DRAWS, seed=SEED) -> dict:
    """Options approximation per trade: delta x side x (exit - entry) x CONTRACT_MULTIPLIER."""
    out = {"note": OVERLAY_NOTE}
    if trades is None or len(trades) == 0:
        return out
    mv = trades["sign"].to_numpy(float) * (trades["exit"].to_numpy(float)
                                           - trades["entry"].to_numpy(float))
    for dl in OVERLAY_DELTAS:
        usd = dl * mv * CONTRACT_MULTIPLIER
        ci = LAB.cluster_mean_ci(usd / 100, trades["date"].astype(str), draws=draws, seed=seed)
        out[f"delta_{dl:.2f}"] = {"mean_usd_per_contract": _r(float(np.mean(usd))),
                                  "ci": ci["ci_pct"], "word": ci["word"],
                                  "breakeven_spread_usd_per_share": _r(float(np.mean(dl * mv)))}
    return out


# ---------------------------------------------------------------------------
# data diagnostics
# ---------------------------------------------------------------------------
def suspect_rows(daily, load_day: Callable, days) -> tuple:
    """(suspect rows, daily_vs_rth distribution) over the daily rows dated in `days` that have
    a cached minute doc: SUSPECT when the daily high / low is more than SUSPECT_DAILY_PCT beyond
    the RTH print, or `prices._is_scale_glitch(close, prev_close)`."""
    allowed = {d.isoformat() for d in days}
    rows, diffs = [], []
    prev_close = None
    for ts, r in daily.iterrows():
        iso = ts.date().isoformat()
        pc, prev_close = prev_close, float(r["close"])
        if iso not in allowed:
            continue
        rth = indicators.session_high_low(load_day(ts.date()), "rth") \
            if rth_of(load_day(ts.date())) is not None else None
        if not rth:
            continue
        dh = abs(r["high"] - rth["high"]) / rth["high"] * 100
        dlo = abs(r["low"] - rth["low"]) / rth["low"] * 100
        dmax = float(max(dh, dlo))
        diffs.append((dmax, iso))
        reason = []
        if dh > SUSPECT_DAILY_PCT:
            reason.append("high")
        if dlo > SUSPECT_DAILY_PCT:
            reason.append("low")
        if pc is not None and prices._is_scale_glitch(float(r["close"]), pc):
            reason.append("scale_glitch")
        if reason:
            rows.append({"date": iso, "high": float(r["high"]), "rth_high": rth["high"],
                         "low": float(r["low"]), "rth_low": rth["low"], "diff_pct": _r(dmax),
                         "reason": "+".join(reason)})
    a = np.array([d for d, _ in diffs], dtype=float)
    dist = {"n": int(a.size),
            "p50_pct": _r(float(np.percentile(a, REPORT_PCTLS[1]))) if a.size else None,
            "p90_pct": _r(float(np.percentile(a, REPORT_PCTLS[2]))) if a.size else None,
            "max_pct": _r(float(a.max())) if a.size else None,
            "top10": [{"date": i, "diff_pct": _r(d)} for d, i in sorted(diffs, reverse=True)
                      [:TOP_N_DIFFS]]}
    return rows, dist


def flagged_days(daily, suspects, days) -> set:
    """Sessions whose 252-row FINE window (rows dated before the session) holds a suspect row."""
    if not suspects:
        return set()
    sus = {pd.Timestamp(s["date"]) for s in suspects}
    out = set()
    for d in days:
        win = daily.index[daily.index < pd.Timestamp(d)][-price_zones.LOOKBACK_BARS:]
        if any(t in sus for t in win):
            out.add(d.isoformat())
    return out


def fidelity(daily, coll_index_zones=None, coll_zone_store=None) -> dict:
    """The study's bands vs what the strip / the zone store SERVED on each stored day (a doc
    dated d was drawn from rows dated before d; the daily frame holds every row before the run
    date, so every stored doc is checkable)."""
    out = {"index_zones_days_checked": 0, "index_zones_days_equal": 0,
           "zone_store_days_checked": 0, "zone_store_days_equal": 0, "mismatches": []}
    if daily is None or not len(daily):
        return out
    for doc in (coll_index_zones.find({}, {"date": 1, "indexes.SPY.resolutions.fine.bands": 1})
                if coll_index_zones is not None else []):
        d = date.fromisoformat(doc["date"])
        served = (((doc.get("indexes") or {}).get(SYMBOL) or {}).get("resolutions") or {}
                  ).get("fine", {}).get("bands") or []
        mine = fine_raw_for(daily, d) or []
        a = sorted((b["kind"], round(b["lo"], 2), round(b["hi"], 2)) for b in served)
        b = sorted((x["kind"], round(x["lo"], 2), round(x["hi"], 2)) for x in mine)
        out["index_zones_days_checked"] += 1
        if a == b:
            out["index_zones_days_equal"] += 1
        else:
            out["mismatches"].append({"store": "index_zones", "date": doc["date"],
                                      "served_n": len(a), "study_n": len(b)})
    for doc in (coll_zone_store.find({"symbol": SYMBOL}, {"date": 1, "bands": 1})
                if coll_zone_store is not None else []):
        d = date.fromisoformat(doc["date"])
        mdoc = zone_store.build_doc(SYMBOL, daily, d) or {}
        a = sorted((b["kind"], b["lo"], b["hi"]) for b in doc.get("bands") or [])
        b = sorted((x["kind"], x["lo"], x["hi"]) for x in mdoc.get("bands") or [])
        out["zone_store_days_checked"] += 1
        eq = len(a) == len(b) and all(x[0] == y[0] and abs(x[1] - y[1]) <= FIDELITY_TOL
                                      and abs(x[2] - y[2]) <= FIDELITY_TOL for x, y in zip(a, b))
        if eq:
            out["zone_store_days_equal"] += 1
        else:
            out["mismatches"].append({"store": "zone_store", "date": doc["date"],
                                      "served_n": len(a), "study_n": len(b)})
    return out


def _mongo_colls():
    try:
        from portfolio.store import _get_db
        db = _get_db()
        if db is None:
            return None, None
        return db[index_zones.COLLECTION], db[zone_store.COLL]
    except Exception:                                           # noqa: BLE001
        return None, None


def data_block(sessions, excluded_is, excluded_oos, is_days, oos_days) -> dict:
    fine_raw_n = [len(s["fine_raw"]) for s in sessions]
    fine_m_n = [len(s["levels"]["fine"]) for s in sessions]
    w_raw = [(b["hi"] - b["lo"]) / b["lo"] * 100 for s in sessions for b in s["fine_raw"]]
    w_m = [(b["hi"] - b["lo"]) / b["lo"] * 100 for s in sessions for b in s["levels"]["fine"]]
    merges = [len(s["fine_raw"]) - len(s["levels"]["fine"]) for s in sessions]
    pr = [(s["pdhl_raw"][0]["hi"] - s["pdhl_raw"][1]["lo"]) / s["pdhl_raw"][1]["lo"] * 100
          for s in sessions]
    gaps = [(s["date"] - s["prev"]).days for s in sessions]
    return {"fine": {"bands_per_day_median_raw": _nanmed(fine_raw_n),
                     "bands_per_day_median_merged": _nanmed(fine_m_n),
                     "width_pct_median_raw": _nanmed(w_raw),
                     "width_pct_median_merged": _nanmed(w_m),
                     "overlap_merges_per_day_mean": _r(float(np.mean(merges))) if merges else None,
                     "sessions_with_overlap": int(sum(m > 0 for m in merges))},
            "pdhl": {"source": "rth_minute", "range_pct_median": _nanmed(pr),
                     "prev_session_gap_max_days": int(max(gaps)) if gaps else None,
                     "prev_session_half_day_n": int(sum(bool(s["prev_half"]) for s in sessions))},
            "split_counts": {"is": {"first": is_days[0].isoformat() if is_days else None,
                                    "last": is_days[-1].isoformat() if is_days else None,
                                    "n_weekdays": len(is_days),
                                    "n_usable": int(sum(s["split"] == "is" for s in sessions)),
                                    "excluded": excluded_is},
                             "oos": {"first": oos_days[0].isoformat() if oos_days else None,
                                     "last": oos_days[-1].isoformat() if oos_days else None,
                                     "n_weekdays": len(oos_days),
                                     "n_usable": int(sum(s["split"] == "oos" for s in sessions)),
                                     "excluded": excluded_oos}}}


def scale_block(sessions, all_trades) -> dict:
    t = all_trades if all_trades is not None and len(all_trades) else None
    return {"atr14_5m_pct_median": _nanmed(t["atr5_pct"]) if t is not None else None,
            "stop_dist_pct_median": _nanmed(t["risk_pct"]) if t is not None else None,
            "stop_over_atr_median": _nanmed(t["stop_over_atr"]) if t is not None else None,
            "day_range_pct_median": _nanmed([s["day_range_pct"] for s in sessions])}


# ---------------------------------------------------------------------------
# prior trial SRs (ledger T01 + the gates study's four)
# ---------------------------------------------------------------------------
def prior_srs(ledger_path) -> list:
    rows = LAB._read_ledger(ledger_path)
    t01 = [r.get("sr_per_entry_day") for r in rows if r.get("trial_id") == "T01"]
    res = Path(ledger_path).parent / GATES_RESULTS_REL
    reads = (json.loads(res.read_text(encoding="utf-8")).get("result") or {}).get("reads") or {}
    g = [v.get("sr") for k, v in sorted(reads.items()) if isinstance(v, dict)
         and v.get("sr") is not None]
    return [float(s) for s in t01 + g if s is not None]


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def forbidden_hits(text) -> list:
    return LAB.forbidden_hits(text)


def _f(v, dp=SHOW_DP):
    return "n/a" if v is None else f"{v:.{dp}f}"


def _ci(ci):
    return "n/a" if not ci else f"[{_f(ci[0])}, {_f(ci[1])}]"


def _side_line(key, side, blk, verdict=None) -> str:
    w = (verdict or {}).get("word") or blk.get("word")
    return (f"- `{key}` · **{side}** · {w} · trades {blk.get('n_trades')} · weeks "
            f"{blk.get('n_weeks')} · mean {_f(blk.get('mean_net_pct'))} % CI "
            f"{_ci(blk.get('ci95_pct'))} · win {_f(blk.get('win_rate'))} · stop-out "
            f"{_f(blk.get('stop_out_rate'))} · target {_f(blk.get('target_rate'))} · room/risk "
            f"{_f(blk.get('room_over_risk_median'))} · risk {_f(blk.get('risk_pct_median'))} %")


def render_report(stats) -> str:
    sc = (stats.get("data") or {}).get("scale") or {}
    L = [f"# SPY levels study — {stats['mode']} ({stats.get('as_of')})", "",
         "Every number below is a measurement on closed bars; nothing here orders, gates or "
         "alerts anything.", "", UNION_SENTENCE, "",
         f"Scale (at signal bars, per variant-row): stop median "
         f"{_f(sc.get('stop_dist_pct_median'))} % vs 5-min ATR "
         f"{_f(sc.get('atr14_5m_pct_median'))} %; day range median (per session) "
         f"{_f(sc.get('day_range_pct_median'))} %.", ""]
    if stats.get("pick") is not None or stats["mode"] in ("is", "outcome"):
        p = stats.get("pick")
        L += [f"IS pick: {p['variant'] if p else 'none (TOO SMALL)'}", ""]
    for split in ("is", "oos"):
        blocks = stats.get(split) or {}
        if not blocks:
            continue
        L += [f"## {split.upper()}", ""]
        for key in FAMILY:
            vb = blocks.get(key) or {}
            for side in SIDES:
                sb = vb.get(side) or {}
                blk = sb.get("block", sb)
                L.append(_side_line(key, side, blk, sb.get("verdict")))
            fb = vb.get("fallback")
            if fb is not None:
                L.append(f"  - fallback (no next level, flattened): trades {fb.get('n_trades')} · "
                         f"mean {_f(fb.get('mean_net_pct'))} %")
        L.append("")
    cand = stats.get("candidate")
    if cand:
        L += ["## Candidate", "", f"- variant `{cand['variant']}`",
              f"- pooled: {cand['verdict_pooled']}", f"- long: {cand['verdict_long']}",
              f"- short: {cand['verdict_short']}", f"- ship word: {cand['ship_word']}", ""]
    ov = stats.get("overlay_options") or {}
    if ov:
        L += ["## Options overlay (approximation)", ""]
        for key, o in ov.items():
            L.append(f"- `{key}`: {o.get('note')}")
            for dk in [k for k in o if k.startswith("delta_")]:
                L.append(f"  - {dk}: mean {_f(o[dk]['mean_usd_per_contract'])} USD/contract, "
                         f"CI {_ci(o[dk]['ci'])}")
        L.append("")
    if stats.get("smoke_gates"):
        L += ["## Smoke gates (IS sample, code path only, not a verdict)", ""]
        for key, g in stats["smoke_gates"].items():
            L.append(f"- `{key}`: B1 beat {g['placebo']['b1']['beat_share']} · B2 beat "
                     f"{g['placebo']['b2']['beat_share']} · C sr {_f(g['gate_c']['sr'])} · word "
                     f"{g['verdict']['word']}")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# artefacts
# ---------------------------------------------------------------------------
def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        f = float(o)
        return f if math.isfinite(f) else None
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (date, datetime, pd.Timestamp)):
        return o.isoformat()
    raise TypeError(type(o))


def _scrub(o):
    if isinstance(o, dict):
        return {k: _scrub(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_scrub(v) for v in o]
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def write_artefacts(out: Path, stats, trades=None, trials=None, corr=None, log_lines=()):
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.json").write_text(json.dumps(_scrub(json.loads(json.dumps(
        stats, default=_json_default))), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    if trades is not None:
        trades.to_csv(out / "trades.csv", index=False)
    if trials is not None:
        trials.to_csv(out / "trials.csv", index=False)
    if corr is not None:
        corr.to_csv(out / "variant_corr.csv")
    rep = render_report(stats)
    hits = forbidden_hits(rep)
    if hits:
        raise ValueError(f"report word guard: {hits}")
    (out / "report.md").write_text(rep, encoding="utf-8")
    (out / "run.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------
def build_sessions(days, split, load_day, daily, flagged=None) -> tuple:
    sess, excl = usable_sessions(days, load_day, daily, flagged_days=flagged)
    for s in sess:
        s["split"] = split
    return sess, excl


def run_family(sessions, split) -> tuple:
    """{key: (trades, counters)} for all 24 variants."""
    return {k: run_variant(sessions, k, split) for k in FAMILY}


def split_blocks(fam, n_sessions, *, draws, seed) -> dict:
    out = {}
    for key, (tr, cnt) in fam.items():
        sl = side_slices(tr)
        out[key] = {s: block(sl[s], cnt if s == "pooled" else None, n_sessions, draws=draws,
                             seed=seed) for s in SIDES}
        if parse_key(key)["target"] == "next_or_flatten" and len(tr):
            out[key]["fallback"] = block(tr[tr["no_next_level"].astype(bool)], None, n_sessions,
                                         draws=draws, seed=seed)
    return out


def trials_frame(stats) -> pd.DataFrame:
    rows = []
    for key in FAMILY:
        for side in SIDES:
            r = {"variant": key, "side": side}
            for split in ("is", "oos"):
                sb = ((stats.get(split) or {}).get(key) or {}).get(side) or {}
                blk = sb.get("block", sb)
                for f in ("n_trades", "n_weeks", "mean_net_pct", "word", "win_rate",
                          "stop_out_rate", "room_over_risk_median"):
                    r[f"{split}_{f}"] = blk.get(f)
                r[f"{split}_verdict"] = (sb.get("verdict") or {}).get("word")
            rows.append(r)
    return pd.DataFrame(rows)


def concat(fam) -> pd.DataFrame:
    parts = [tr for tr, _ in fam.values() if len(tr)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def stride_pick(days, n: int) -> list:
    """`n` days spread across `days` at a fixed stride (never the first n)."""
    if len(days) <= n:
        return list(days)
    step = len(days) // n
    return list(days[step // 2::step])[:n]


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="SPY levels study (2026-11-05).")
    ap.add_argument("--mode", choices=MODES, required=True)
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cohort-stats", default=None)
    ap.add_argument("--prereg", default=None)
    ap.add_argument("--prereg-commit", default=None)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--pause-sec", type=float, default=FETCH_PAUSE_SEC)
    ap.add_argument("--cache-only", action="store_true")
    ap.add_argument("--draws", type=int, default=BOOT_DRAWS)
    ap.add_argument("--placebo-sets", type=int, default=PLACEBO_SETS)
    return ap.parse_args(argv)


def read_sha_file(path: Path = SHA_FILE) -> Optional[str]:
    try:
        s = path.read_text(encoding="utf-8").strip()
        return s or None
    except OSError:
        return None


def main(argv=None, *, now=None, load_day=None, daily=None, fetch_loader=None, cached=None,
         block=True, colls=None, sleep=time.sleep) -> int:
    a = parse_args(argv)
    now_et = (now or datetime.now(tz=ET)).astimezone(ET)
    out = Path(a.out)
    if LAB.out_inside_repo(out):
        return _rc3("--out is inside the repo; artefacts never land in the repo.")
    if RS.refused_window(now_et):
        return _rc3(f"{now_et:%H:%M} ET is inside {RS.REFUSE_FROM[0]:02d}:{RS.REFUSE_FROM[1]:02d}"
                    f"-{RS.REFUSE_TO[0]:02d}:{RS.REFUSE_TO[1]:02d} ET.")
    as_of = date.fromisoformat(a.as_of) if a.as_of else default_as_of(now_et)
    if as_of >= now_et.date():
        return _rc3("--as-of must be a session before the run's ET date (today re-fetches).")
    if a.mode != "fetch" and not a.cohort_stats:
        return _rc3("a non-fetch mode needs --cohort-stats (the fetch stage's stats.json).")
    sha = None
    if a.mode == "outcome":
        miss = [n for n, v in (("--prereg", a.prereg), ("--prereg-commit", a.prereg_commit),
                               ("--ledger", a.ledger)) if not v]
        if miss:
            return _rc3(f"an outcome run needs {', '.join(miss)}.")
        if not LAB.valid_commit(a.prereg_commit):
            return _rc3("--prereg-commit must be 12-40 lowercase hex (a real commit).")
        if LAB.ledger_refusal(a.ledger):
            return _rc3(LAB.ledger_refusal(a.ledger))
        if not Path(a.prereg).is_file():
            return _rc3(f"the prereg file {a.prereg} does not exist.")
        sha = hashlib.sha256(Path(a.prereg).read_bytes()).hexdigest()
        want = read_sha_file()
        if want is None or sha != want:
            return _rc3("the prereg sha256 differs from backend/scripts/spy_levels_prereg.sha256.")
        if (out / "stats.json").exists():
            return _rc3(f"{out}/stats.json exists: the OOS half is read ONCE.")
        rows = LAB._read_ledger(a.ledger)
        for k in range(len(FAMILY)):
            clash = LAB.ledger_conflict(rows, f"T{k + 2:02d}", sha)
            if clash:
                return _rc3(clash)
    if a.mode == "fetch":
        return run_fetch(a, now_et, as_of, out, fetch_loader=fetch_loader, cached=cached,
                         daily=daily, block=block, colls=colls, sleep=sleep)
    cs = json.loads(Path(a.cohort_stats).read_text(encoding="utf-8"))
    cdata = cs.get("data") or {}
    if not cdata.get("cohort_first") or not cdata.get("daily_csv"):
        return _rc3("--cohort-stats carries no cohort_first / daily_csv.")
    if not a.as_of and cs.get("as_of"):
        as_of = date.fromisoformat(cs["as_of"])
    if cs.get("as_of") and cs["as_of"] != as_of.isoformat():
        return _rc3(f"--as-of {as_of} differs from the cohort's as_of {cs['as_of']}.")
    prior = None
    if a.mode == "outcome":
        try:
            prior = prior_srs(a.ledger)
        except (OSError, ValueError) as exc:
            return _rc3(f"the prior trial SRs are unreadable ({exc}); nothing read.")
    if block:
        block_network_and_writes()
    load_day = load_day or cache_loader()
    daily = daily if daily is not None else load_daily(cdata["daily_csv"])
    cohort_first = date.fromisoformat(cdata["cohort_first"])
    is_days, oos_days = split_weekdays(cohort_first, as_of)
    t0 = time.time()
    stats = {"study": STUDY, "script": SCRIPT, "mode": a.mode,
             "run_at_et": now_et.isoformat(), "as_of": as_of.isoformat(),
             "from_day": from_day_of(as_of).isoformat(), "prereg_sha256": sha,
             "prereg_commit": a.prereg_commit, "seed": SEED,
             "costs": {"cost_bps_side": COST_BPS, "slip_usd_side": SLIP_USD},
             "mine": dict(MINE, PLACEBO_EXCL_MIN=PLACEBO_EXCL_MIN), "design_typed": DESIGN,
             "family": {"n_variants": len(FAMILY), "keys": FAMILY},
             "cohort_stats": {"path": a.cohort_stats, "cache_only": cdata.get("cache_only")}}
    run_is = stride_pick(is_days, SMOKE_SESSIONS) if a.mode == "smoke" else is_days
    allowed_days = list(run_is) + (list(oos_days) if a.mode == "outcome" else [])
    seal_end = as_of if (a.mode == "outcome" or not oos_days) else oos_days[0] - timedelta(days=1)
    sus, dist = suspect_rows(daily, load_day, weekdays(daily.index.min().date(), seal_end))
    flagged = flagged_days(daily, sus, allowed_days)
    is_sess, is_excl = build_sessions(run_is, "is", load_day, daily, flagged)
    fam_is = run_family(is_sess, "is")
    stats["is"] = split_blocks(fam_is, len(is_sess), draws=a.draws, seed=SEED)
    oos_sess, oos_excl, fam_oos = [], [], {}
    pick = is_pick(stats["is"])
    stats["pick"] = pick
    if a.mode == "outcome":
        if pick is None:
            return _rc3("pick == null: no variant has >= MIN_CLUSTERS IS entry-weeks; the OOS "
                        "half stays sealed (TOO SMALL).")
        oos_sess, oos_excl = build_sessions(oos_days, "oos", load_day, daily, flagged)
        fam_oos = run_family(oos_sess, "oos")
    sessions = is_sess + oos_sess
    db = data_block(sessions, is_excl, oos_excl, run_is, oos_days if a.mode == "outcome" else [])
    colls = colls if colls is not None else _mongo_colls()
    all_tr = concat(fam_oos) if fam_oos else concat(fam_is)
    stats["data"] = {"cohort_first": cohort_first.isoformat(),
                     "split": dict(boundary=oos_days[0].isoformat() if oos_days else None,
                                   **db["split_counts"]),
                     "daily_frame": {"rows": int(len(daily)),
                                     "first": daily.index.min().date().isoformat(),
                                     "last": daily.index.max().date().isoformat(),
                                     "suspect_rows": sus,
                                     **{k: cdata.get("daily_frame", {}).get(k) for k in
                                        ("price_cache_rows_compared", "price_cache_mismatch_n")}},
                     "daily_vs_rth": dist, "fidelity": fidelity(daily, *colls),
                     "pdhl": db["pdhl"], "fine": db["fine"],
                     "scale": scale_block(sessions, all_tr)}
    stats["N"] = {"prior_narrative": PRIOR_NARRATIVE_N, "this_study": len(FAMILY),
                  "narrative_total": PRIOR_NARRATIVE_N + len(FAMILY), "dup_rho": DUP_RHO}
    corr = None
    trades_out = concat(fam_is)
    if a.mode == "smoke":
        by_date = {s["date"].isoformat(): s for s in is_sess}
        stats["smoke_gates"] = {}
        for key in FAMILY:
            tr, cnt = fam_is[key]
            stats["smoke_gates"][key] = gates(tr, by_date, [], [], n_sessions=len(is_sess),
                                              counters=cnt, draws=a.draws, sets=a.placebo_sets)
    if a.mode == "outcome":
        oos_dates = [s["date"].isoformat() for s in oos_sess]
        series = {k: date_series(fam_oos[k][0], oos_dates) for k in FAMILY}
        clusters = duplicate_clusters(series, rho=DUP_RHO)
        corr = corr_matrix(series)
        srs = {k: sr_of(fam_oos[k][0]) for k in FAMILY}
        eff = [srs[c[0]] for c in clusters if srs[c[0]] is not None]
        naive = [srs[k] for k in FAMILY if srs[k] is not None]
        stats["N"].update(prior_sr_available=len(prior), effective_variants=len(clusters),
                          dsr_sr_list_n=len(prior) + len(eff), clusters=clusters)
        by_date = {s["date"].isoformat(): s for s in oos_sess}
        stats["oos"] = {}
        for key in FAMILY:
            tr, cnt = fam_oos[key]
            sl = side_slices(tr)
            vb = {}
            for side in SIDES:
                vb[side] = gates(sl[side], by_date, prior + eff, prior + naive,
                                 n_sessions=len(oos_sess), counters=cnt if side == "pooled"
                                 else None, draws=a.draws, sets=a.placebo_sets)
            if parse_key(key)["target"] == "next_or_flatten" and len(tr):
                vb["fallback"] = block(tr[tr["no_next_level"].astype(bool)], None,
                                       len(oos_sess), draws=a.draws, seed=SEED)
            vb["selectable"] = key == pick["variant"]
            stats["oos"][key] = vb
        c = stats["oos"][pick["variant"]]
        words = {s: c[s]["verdict"]["word"] for s in SIDES}
        stats["candidate"] = {"variant": pick["variant"], "verdict_pooled": words["pooled"],
                              "verdict_long": words["long"], "verdict_short": words["short"],
                              "ship_word": "HIS CALL" if words["pooled"] == "POSITIVE" else "OFF"}
        stats["overlay_options"] = {k: overlay(fam_oos[k][0], draws=a.draws) for k in FAMILY}
        trades_out = pd.concat([concat(fam_is), concat(fam_oos)], ignore_index=True)
    stats["attempted_fetches"] = list(ATTEMPTED_FETCHES)
    stats["recorded_puts"] = list(RECORDED_PUTS)
    stats["runtime_sec"] = _r(time.time() - t0, 1)
    stats["words_guard"] = "clean"
    log = summary_lines(stats)
    write_artefacts(out, stats, trades_out, trials_frame(stats), corr, log)
    if a.mode == "outcome":
        for k, key in enumerate(FAMILY):
            v = stats["oos"][key]
            cl = next(i for i, c in enumerate(stats["N"]["clusters"]) if key in c)
            LAB.ledger_append(a.ledger, {
                "trial_id": f"T{k + 2:02d}", "candidate": f"spy_levels:{key}",
                "params": dict(parse_key(key), stop="signal_bar_extreme",
                               cost_bps_side=COST_BPS, slip_usd_side=SLIP_USD),
                "prereg_sha256": sha, "prereg_commit": a.prereg_commit,
                "as_of": as_of.isoformat(), "oos_from": stats["data"]["split"]["boundary"],
                "run_date": now_et.date().isoformat(),
                "sr_per_entry_day": v["pooled"]["gate_c"]["sr"],
                "n_per_entry_day": v["pooled"]["gate_c"]["n"],
                "verdict": v["pooled"]["verdict"]["word"],
                "verdict_long": v["long"]["verdict"]["word"],
                "verdict_short": v["short"]["verdict"]["word"], "dup_cluster": cl,
                "selected": key == pick["variant"]})
    for line in log:
        print(line)
    return 0


def run_fetch(a, now_et, as_of, out, *, fetch_loader=None, cached=None, daily=None, block=True,
              colls=None, sleep=time.sleep) -> int:
    from_day = from_day_of(as_of)
    if a.cache_only and block:
        block_network_and_writes()
    cached = cached or (lambda d: DATA._mongo_get_day(SYMBOL, d))
    loader = fetch_loader or (lambda d: DATA.load_intraday_range(SYMBOL, d, d))
    t0 = time.time()
    fh = fetch_history(from_day, as_of, pause_sec=a.pause_sec, loader=loader, cached=cached,
                       sleep=sleep, cache_only=a.cache_only)
    if daily is None:
        raw = (prices.bulk_cached_frames([SYMBOL]).get(SYMBOL) if a.cache_only else
               prices.closed_daily_frame(SYMBOL, now=now_et, period=DAILY_PERIOD,
                                         use_cache=False))
        daily = normalise_daily(raw)
    if daily is None:
        return _rc3("no SPY daily frame came back.")
    daily = daily[daily.index < pd.Timestamp(now_et.date())]
    csv = out.parent.parent / "data" / (DAILY_CSV_CACHE_ONLY if a.cache_only else DAILY_CSV)
    save_daily(daily, csv)
    ref = daily if a.cache_only else (price_cache_frame() if block else None)
    fid_daily = daily_fidelity(daily, ref)
    load_day = cache_loader(cached)
    all_days = weekdays(daily.index.min().date(), as_of)
    sus, dist = suspect_rows(daily, load_day, all_days)
    colls = colls if colls is not None else _mongo_colls()
    stats = {"study": STUDY, "script": SCRIPT, "mode": "fetch", "run_at_et": now_et.isoformat(),
             "as_of": as_of.isoformat(), "from_day": from_day.isoformat(),
             "data": dict(fh, daily_csv=str(csv),
                          daily_frame={"rows": int(len(daily)),
                                       "first": daily.index.min().date().isoformat(),
                                       "last": daily.index.max().date().isoformat(),
                                       "source": ("price_cache (read)" if a.cache_only else
                                                  f"closed_daily_frame {DAILY_PERIOD} fresh"),
                                       "suspect_rows": sus, **fid_daily},
                          daily_vs_rth=dist, fidelity=fidelity(daily, *colls)),
             "attempted_fetches": list(ATTEMPTED_FETCHES), "recorded_puts": list(RECORDED_PUTS),
             "runtime_sec": _r(time.time() - t0, 1)}
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.json").write_text(json.dumps(_scrub(json.loads(json.dumps(
        stats, default=_json_default))), indent=1, allow_nan=False) + "\n", encoding="utf-8")
    d = stats["data"]
    lines = [f"{STUDY} fetch{' (cache-only)' if a.cache_only else ''}: requested "
             f"{d['sessions_requested']} · cached before {d['sessions_cached_before']} · fetched "
             f"{d['sessions_fetched']} · retried {len(d['fetch_retried'])} · failed "
             f"{len(d['fetch_failed'])} · cohort_first "
             f"{d['cohort_first']}",
             f"daily {d['daily_frame']['rows']} rows {d['daily_frame']['first']} -> "
             f"{d['daily_frame']['last']} · suspect {len(sus)} · price_cache mismatches "
             f"{fid_daily['price_cache_mismatch_n']} of {fid_daily['price_cache_rows_compared']}",
             f"fidelity {stats['data']['fidelity']['index_zones_days_equal']}/"
             f"{stats['data']['fidelity']['index_zones_days_checked']} index_zones · "
             f"{stats['data']['fidelity']['zone_store_days_equal']}/"
             f"{stats['data']['fidelity']['zone_store_days_checked']} zone_store · attempted "
             f"fetches {ATTEMPTED_FETCHES} · recorded puts {len(RECORDED_PUTS)}"]
    (out / "run.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:
        print(line)
    return 0


def summary_lines(stats) -> list:
    d = stats["data"]
    sp = d["split"]
    sc = d["scale"]
    lines = [f"{STUDY} {stats['mode']}: as_of {stats['as_of']} · cohort_first {d['cohort_first']}"
             f" · boundary {sp['boundary']} · IS usable {sp['is']['n_usable']}/"
             f"{sp['is']['n_weekdays']} · OOS usable {sp['oos']['n_usable']}/"
             f"{sp['oos']['n_weekdays']}",
             f"scale (at signal bars, per variant-row): stop median "
             f"{sc['stop_dist_pct_median']} % · 5-min ATR "
             f"{sc['atr14_5m_pct_median']} % · stop/ATR {sc['stop_over_atr_median']} · day range "
             f"{sc['day_range_pct_median']} %",
             f"fine bands/day raw {d['fine']['bands_per_day_median_raw']} merged "
             f"{d['fine']['bands_per_day_median_merged']} · overlap sessions "
             f"{d['fine']['sessions_with_overlap']} · pdhl range {d['pdhl']['range_pct_median']} %"
             f" · suspect rows {len(d['daily_frame']['suspect_rows'])} · fidelity "
             f"{d['fidelity']['index_zones_days_equal']}/{d['fidelity']['index_zones_days_checked']}",
             f"attempted fetches {stats['attempted_fetches']} · recorded puts "
             f"{len(stats['recorded_puts'])}"]
    for key in FAMILY:
        b = (stats.get("is") or {}).get(key, {}).get("pooled", {})
        lines.append(f"IS {key}: n {b.get('n_trades')} wk {b.get('n_weeks')} mean "
                     f"{b.get('mean_net_pct')} stop-out {b.get('stop_out_rate')} target "
                     f"{b.get('target_rate')} room/risk {b.get('room_over_risk_median')}")
    lines.append(f"pick {stats.get('pick')}")
    if stats.get("candidate"):
        c = stats["candidate"]
        lines.append(f"candidate {c['variant']}: pooled {c['verdict_pooled']} · long "
                     f"{c['verdict_long']} · short {c['verdict_short']} · {c['ship_word']}")
    lines.append(f"runtime {stats.get('runtime_sec')}s")
    return lines


def imported_modules(path=None) -> set:
    return LAB.imported_modules(path or __file__)


if __name__ == "__main__":
    raise SystemExit(main())
