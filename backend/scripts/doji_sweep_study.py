"""🕯️ DOJI SWEEP — the pre-registered study behind the Chart Maps Doji Sweep tab (2026-10-16).

THE ASK (Ajay 2026-10-16, verbatim)
  "create me a new tab for Doji candle after a sweep. For any stocks after a
   down trend. May be from all chart maps especially on the 60% 70% down stocks"
  K1: "I heard but do some research and back test please on accuracy"
  K4: "Within 5% either side counts as a test"

"Accuracy" here = how often a doji on a test of the prior low, in a downtrend,
was followed by a reversal up — against the SAME names' other days in the SAME
downtrend: (a) the confirmation rate (a close above the doji's HIGH within
`CONFIRM_SESSIONS` sessions before any close under its LOW) and (b) the return
from the next open over `PRIMARY_H` sessions (median = the verdict; the mean
before and after costs beside it), the stop-out rate (a close under the doji's
low) always beside both. Never a hit rate alone.

THE PRIOR IS NULL (their claims): Bulkowski — the southern doji reverses 52% of
the time (rank 78/103), the dragonfly 50% (rank 98/103); Marshall, Young & Rose
(DJIA 1992-2002) — nothing significant after the bootstrap; George & Hwang
(2004) — names far from their 52-week high do worse. In this app: the candle
ledger never grades "indecision"; every S&D reversal gate measured flat.

PRE-REGISTERED in `docs/research/doji_sweep_study_2026_10_16.md`, committed
BEFORE any outcome run. An outcome run carries `--prereg-commit <hash>` AND
`--prereg-blob <git hash-object of the prereg>` (the blob survives a rebase).
Nothing below may change after that commit without a new prereg.

THE SAME DETECTOR. Every rule is `chart_maps.doji_sweep_tab`'s: the per-bar
features (`DJ.frame_features`), the one classifier (`DJ.row_statuses`), the
three downtrend reads (`DJ.reads_vector`), the point-in-time all-time high
(`DJ.ath_series`) and the three pre-registered verdict cells
(`DJ.study_cells`, AMENDMENTS6 B4 / B5). This file assigns no threshold of the
tab's; it adds only study numbers (`# MINE (BUILD_SPEC6 …)`).

THE THREE VERDICT CELLS (AMENDMENTS6 B4 / B5 / B6, Holm-corrected across them):
  primary       his "60% 70%": 60%+ under the 52-week high, the house 5% body,
                his 5% test, 10 sessions from the next open, net of SPY;
  any_read      the tab's default view (any downtrend read);
  test_no_doji  the same test and read with NO doji (a body of 10%+ of the
                range) — the doji's control, against its OWN matched days.
Every other cell is "exploratory — no verdict" (numbers only).

THE CI (AMENDMENTS6 B2). Binding: a bootstrap over `DSM.BLOCK_SESSIONS`-session
blocks of the SPY calendar (an event and its placebos resampled together);
the second axis resamples names. A verdict cell reads "separates" / "inverted"
only when BOTH axes agree, else "axes_disagree". The naive per-date CI is
reported beside them. The verdict reads the market-adjusted median (every
outcome minus SPY over the identical window); the raw read sits beside it.

THE LEAK RULE. Features read bars <= t only (the engine); outcomes read
t + `OUTCOME_START` .. t + h only — `check_no_leak` raises otherwise (a test sets
OUTCOME_START to 0 and watches it fail). The as-of day follows the tab
(AMENDMENTS6 B11): a session counts only after the `KL.ROLL_AT` 20:00 ET roll.
The smc swing-low read is called on a slice ending at t, never the full frame.

READ-ONLY (AMENDMENTS6 B18). Every pymongo data write raises (recorded) and an
index create is a recorded no-op before anything connects; a run that recorded
a data write exits 3 and writes no artifact. Every `sepa.prices` fetcher named
in `NO_FETCH_FUNCS` raises in-process; the price read is ONE
`bulk_cached_frames` find. `--no-fetch` is the only mode (there is no --fetch).

RUN (OUTSIDE 09:00–16:30 ET, a THROWAWAY container, the main session's
launcher scratchpad doji/doji_study_run.sh — never inside the live api):
  counts first (no outcome key exists in this artifact — no peeking):
    doji_study_run.sh --count-only --out /out/doji_sweep_counts.json
  then ONE outcome run per prereg (the container holds no .git, so the
  launcher passes the host's HEAD and attests a clean tree, AMENDMENTS6 B12;
  the launcher MUST mount <worktree>/docs/research read-only at /docs/research
  (-v <worktree>/docs/research:/docs/research:ro) — without it the run refuses,
  exit 2, because the prereg is not on disk):
    doji_study_run.sh --prereg-commit <hash> --prereg-blob <blob> \\
        --git-head <host HEAD> --git-clean
  cp <out>/doji_sweep_study.json backend/scripts/doji_sweep_measured.json
Then paste the printed `measured_literal` into chart_maps/doji_sweep_measured.py.

FIX ROUND 1 (2026-10-16, the WP-S critic):
  * The counts a verdict stands on are the CONTRAST set's (`contrast_counts`):
    events with a finite market-adjusted R_PRIMARY_H AND at least one finite
    placebo. A cell of 100 detections with 60 measurable reads too_small. The
    raw detection count is served as `n_detected` (the count-only artifact
    serves it as `n_events`).
  * B1 for the cells whose events are NOT 10%-body fires (`OWN_POOL_CELLS`:
    the control and the untested / swing cells): the pool also drops the cell's
    own event sessions and the PLACEBO_GAP sessions after each, and those draws
    are keyed by the cell (`placebo_rng(..., cell=)`), never shared.
  * The name axis reads its own cluster count (n_symbols); the block axis
    reads the cell's sessions (n_dates) — `n_blocks` is served beside it.
  * An outcome run REFUSES when the prereg file is not on disk; `git.source` =
    "measured" (git read in-process) or "attested" (--git-head / --git-clean).

FIX ROUND 2 (2026-10-16, the WP-S critic):
  * The control's own-pool rule (B1) empties or shortens the pool of names
    that keep testing (the critic's count-only probe, prereg §17), so the
    control and the primary read different populations. The prereg compares them as NUMBERS
    only (never "the test alone carries it"), and the exploratory sensitivity
    cell `test_no_doji_fire_pool` (FIRE_POOL_SENSITIVITY) reads the control's
    events against the primary's fire-only pool. Every cell serves
    `n_detected`, `n_unmatched` and `placebo_short_pool` (the unmatched share).
  * No block-count floor (written into the prereg); `n_blocks` and
    `n_detected` are served in every cell and in the literal's primary.
  * `git.source` is served (DSM.GIT_KEYS).
  * The universe step never reaches the network nor writes the shared
    universe cache: `block_fetches` also reads every cached list WHATEVER ITS
    AGE (sepa.universe's TTL is lifted in this process only) and refuses and
    counts every sepa.universe network / cache-write entry point named in
    UNIVERSE_NO_FETCH_FUNCS — a list with no cache file at all is then a
    counted provider call, and the run exits 3 with no artifact.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import ath_history as AH  # noqa: E402
from chart_maps import ath_tab as ATH  # noqa: E402
from chart_maps import board as BOARD  # noqa: E402
from chart_maps import doji_sweep_measured as DSM  # noqa: E402
from chart_maps import doji_sweep_tab as DJ  # noqa: E402
from chart_maps import fallen_tab as FAL  # noqa: E402
from scripts import resiliency_study as RS  # noqa: E402
from scripts.explosive_study import MIN_BUCKET_N  # noqa: E402
from sepa import prices  # noqa: E402
from supply_demand import demand_reentry as DR, key_levels as KL, smc as SMC  # noqa: E402

ET = KL.ET
STUDY = "doji_sweep_2026_10_16"
SCRIPT, PREREG = DJ.SCRIPT_PATH, DJ.PREREG_PATH
ARTIFACT = "backend/scripts/doji_sweep_measured.json"
DEFAULT_OUT = Path(__file__).resolve().parent / "doji_sweep_measured.json"
UNIVERSE_KEY = "full"
BENCH = "SPY"                       # the calendar and the market adjustment (a symbol, not a threshold)
HORIZONS = (5, 10, 20)              # MINE (BUILD_SPEC6 §3.11; DECISIONS6 scope "outcomes at 5 / 10 / 20 sessions")
PRIMARY_H = 10                      # MINE (BUILD_SPEC6 §3.11, HIS CALL Q17) — Bulkowski's 10-day moves; MYR's 10-day hold
CONFIRM_SESSIONS = 5                # MINE (BUILD_SPEC6 §3.11; DECISIONS6 "close above the doji HIGH within 5 sessions")
PLACEBO_K = 5                       # MINE (BUILD_SPEC6 §3.11) — k = 5 matched days per event
DRAWS_DEFAULT = 2000                # MINE (BUILD_SPEC6 §3.11) — the high_beta_study draw count
SEED_DEFAULT = 20261016             # MINE (BUILD_SPEC6 §3.11)
COOLDOWN = PRIMARY_H                # MINE (BUILD_SPEC6 §3.11) — the "independent" cell: one event per name per 10 sessions
COST_ROUND_TRIP_PCT = 0.5           # MINE (BUILD_SPEC6 §3.11; Lu, Chen & Hsu 2015 used 0.5%) — a sensitivity, never the verdict
OUTCOME_START = 1                   # MINE (BUILD_SPEC6 §3.11.2) — the leak rule: outcomes read t+1.. only (a test sets it to 0 and watches LeakError)
PLACEBO_GAP = max(HORIZONS)         # derived (AMENDMENTS6 B1) — no placebo within 20 sessions of its event or after a 10%-body fire
CI_PCT = RS.CI_PCT                  # imported (95)
ALPHA = (100.0 - CI_PCT) / 100.0    # derived (0.05) — the Holm family level
MIN_CELL_EVENTS, MIN_CELL_DATES = DSM.MIN_CELL_EVENTS, MIN_BUCKET_N   # imported (100, 30)
BLOCK_SESSIONS = DSM.BLOCK_SESSIONS                                     # imported (10) — AMENDMENTS6 B2
LIQ_FLOOR_USD = BOARD.LIQ_TIERS[BOARD.default_min_tier(DJ.TAB_KEY)]     # derived — the tab's default floor (Q6)
BOOT_CELLS_MAX = 10_000_000         # TRANSPORT — weight-matrix elements per bootstrap chunk (memory only, never a result)
UNIVERSE_NO_FETCH_FUNCS = ("_fetch_text", "_write_cached", "_write_cached_as_of")   # TRANSPORT — sepa.universe's one HTTP entry point (Wikipedia / iShares) and its two cache writers
UNIVERSE_TTL_SEC = float("inf")     # TRANSPORT — the study reads a cached universe list whatever its age (never refetched; the age is the cache's)
NO_FETCH_FUNCS = ("_fetch_massive", "_fetch_yfinance", "_fetch_one", "_fetch", "load_prices", "bulk_snapshot",
                  "market_snapshot_with_meta", "market_snapshot", "closed_daily_frame", "last_trade_price",
                  "patch_latest_closes", "bulk_live_prices", "with_today_bar")
INDEX_METHODS = ("create_index", "create_indexes")   # a reader's lazy index create: a recorded no-op
PHASES = ("read", "features", "events", "placebo", "outcomes", "bootstrap")
AXES = ("block", "date", "symbol")
STATS = ("median", "adj_median", "mean", "confirm")
ENTRIES = ("next_open", "close", "confirm")
READ_SET_BITS = {"w52": 1, "ath": 2, "mas": 4}   # TRANSPORT — a bit code for the exact read set, not a threshold
ATTEMPTED: list = []
FETCH_CALLS: list = []
LIMITS = [
    "survivors-only: the universe is today's list — deep-drawdown names that delisted are absent; absolute "
    "returns are biased up, and the same-name matched days only partly cancel it",
    "the two-year price cache gives about one year of evaluable sessions (a 252-session window first) — one "
    "market regime",
    "adjacent events' outcome windows overlap; the session-block and the by-name resampling keep them "
    "together, they do not remove the overlap",
    "the all-time high before the stored high's month is the frame's running max — a lower bound, so a name "
    "may be missed, never falsely included; the misses are not random — a name that later set a new all-time "
    "high (the later big runners) gets only the frame read, so it is under-included in the ath and any_read cells",
    "next-open entries assume the open print; close-to-close daily bars, no intraday fill is modelled",
    "the sizing probe says about 90% of his tests never undercut the prior low — the undercut cells are thin",
]


class LeakError(AssertionError):
    """A feature index after t, or an outcome index at or before t."""


class NoFetchError(RuntimeError):
    """A provider fetcher was called inside the study (it reads the cache only)."""


class WriteBlockedError(RuntimeError):
    """A pymongo data write was attempted (the study is read-only)."""


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _r(v, dp: int = 2) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return round(x, dp) if np.isfinite(x) else None


def _clean(obj):
    """Every non-finite float -> None, numpy scalars -> python (allow_nan=False safe)."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return float(obj) if np.isfinite(obj) else None
    return obj


# ---------------------------------------------------------------------------
# the leak rule
# ---------------------------------------------------------------------------
def feature_window(t: int) -> range:
    """The widest feature read at t (the 52-week high): bars t-251 .. t."""
    return range(t - DJ.YEAR_BARS + 1, t + 1)


def outcome_window(t: int, h: int) -> range:
    """The bars an outcome at horizon h reads: t + OUTCOME_START .. t + h."""
    return range(t + OUTCOME_START, t + h + 1)


def check_no_leak(t: int, features, outcomes) -> None:
    """Any feature index > t, or any outcome index <= t -> LeakError."""
    f = list(features)
    if f and max(f) > t:
        raise LeakError(f"feature index {max(f)} reads past the candle at {t}")
    o = list(outcomes)
    if o and min(o) <= t:
        raise LeakError(f"outcome index {min(o)} reads the candle at {t} or earlier")


# ---------------------------------------------------------------------------
# the as-of rule (AMENDMENTS6 B11: the tab's 20:00 ET roll)
# ---------------------------------------------------------------------------
def session_after(as_of: date) -> date:
    """KL.levels_session(21:00 ET on as_of) — the next market day."""
    return KL.levels_session(datetime(as_of.year, as_of.month, as_of.day, 21, 0, tzinfo=ET))


def as_of_cut(now_et: datetime) -> str:
    """The tab's last closed session at `now_et` (the cut default_as_of reads up to)."""
    return KL.prev_market_day(KL.levels_session(now_et)).isoformat()


def default_as_of(bench_days: list, now_et: datetime) -> Optional[str]:
    """The last benchmark session the TAB treats as closed at `now_et`: a
    session counts only after the `KL.ROLL_AT` roll (B11), so the cut is
    KL.prev_market_day(KL.levels_session(now)) — never RS.default_as_of's
    16:30."""
    cut = as_of_cut(now_et)
    ok = [d for d in bench_days if d <= cut]
    return ok[-1] if ok else None


def _days(frame) -> list:
    return [d.date().isoformat() for d in KL._norm_index(frame)]


def spy_maps(frame, as_of: str) -> dict:
    """{"o": {iso: open}, "c": {iso: close}, "cal": sorted isos} of the benchmark through as_of."""
    if frame is None or len(frame) == 0:
        return {"o": {}, "c": {}, "cal": []}
    days = _days(frame)
    o = frame["open"].to_numpy(dtype=float)
    c = frame["close"].to_numpy(dtype=float)
    keep = [i for i, d in enumerate(days) if d <= as_of]
    return {"o": {days[i]: float(o[i]) for i in keep}, "c": {days[i]: float(c[i]) for i in keep},
            "cal": sorted(days[i] for i in keep)}


# ---------------------------------------------------------------------------
# per-symbol arrays (the engine, point-in-time over every bar)
# ---------------------------------------------------------------------------
def symbol_arrays(sym: str, df, doc, listed, *, as_of: date, spy: Optional[dict] = None) -> Optional[dict]:
    """Every per-bar array the cells, placebos and outcomes read, from the tab's
    own engine on the frame cut to bars <= as_of. None when fewer than
    YEAR_BARS + 1 closed bars exist (counted `short`)."""
    if df is None or len(df) == 0:
        return None
    as_of = as_of if isinstance(as_of, date) else date.fromisoformat(str(as_of)[:10])
    closed = df[np.asarray(KL._norm_index(df).normalize() <= pd.Timestamp(as_of))]
    if len(closed) < DJ.YEAR_BARS + 1:
        return None
    feat = DJ.frame_features(closed)
    n = len(feat)
    a = ATH.closed_read(sym, closed, doc, listed, session_after(as_of))
    usable = bool(a) and a.get("doc_state") == "ok" and not (doc or {}).get("cut_from")
    hi_t, basis = DJ.ath_series(closed, doc if usable else None)
    c = feat["close"].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        pct_ath = np.where(np.asarray(hi_t, dtype=float) > 0, (1.0 - c / hi_t) * 100.0, np.nan)
    st5 = DJ.row_statuses(feat, body_max=DJ.DOJI_BODY_PCT, pct_below_ath=pct_ath)
    st10 = DJ.row_statuses(feat, body_max=DJ.DOJI_BODY_WIDE_PCT, pct_below_ath=pct_ath)
    rd = DJ.reads_vector(feat["pct_below_52w"].to_numpy(dtype=float), pct_ath,
                         feat["below_mas"].to_numpy(dtype=bool))
    readset = sum(rd[k].astype(int) * b for k, b in READ_SET_BITS.items())
    valid = feat["valid"].to_numpy(dtype=bool)
    suspect = feat["suspect"].to_numpy(dtype=bool)
    eligible = (np.arange(n) >= DJ.YEAR_BARS - 1) & ~suspect & valid
    adv50 = feat["adv50"].to_numpy(dtype=float)
    floor = np.nan_to_num(adv50, nan=-np.inf) >= LIQ_FLOOR_USD
    fired10 = st10 == DJ.ROW_STATUSES[-1]
    after_fire = after_fire_mask(fired10)
    dates = np.asarray(_days(closed), dtype=object)
    spy = spy or {"o": {}, "c": {}}
    spy_o = np.asarray([spy["o"].get(d, np.nan) for d in dates], dtype=float)
    spy_c = np.asarray([spy["c"].get(d, np.nan) for d in dates], dtype=float)
    return {"sym": str(sym).upper(), "n": n, "dates": dates, "closed": closed, "feat": feat,
            "o": feat["open"].to_numpy(dtype=float), "h": feat["high"].to_numpy(dtype=float),
            "l": feat["low"].to_numpy(dtype=float), "c": c, "spy_o": spy_o, "spy_c": spy_c,
            "pct_ath": pct_ath, "basis": basis, "usable": usable,
            "cut": bool((doc or {}).get("cut_from")), "st5": st5, "st10": st10, "rd": rd,
            "any_rd": rd["w52"] | rd["ath"] | rd["mas"], "readset": readset, "eligible": eligible,
            "floor": floor, "fired10": fired10, "after_fire": after_fire}


def after_fire_mask(fired10) -> np.ndarray:
    """B1: True at s when any 10%-body fire of the name sits in s − PLACEBO_GAP .. s − 1."""
    f = np.asarray(fired10, dtype=bool)
    n = f.size
    cs = np.concatenate([[0], np.cumsum(f.astype(int))])
    lo_i = np.maximum(np.arange(n) - PLACEBO_GAP, 0)
    return (cs[np.arange(n)] - cs[lo_i]) > 0


def swing_sweep_at(closed, t: int) -> bool:
    """The smc sell-side sweep AT t, read on a slice ending at t (never the full
    frame: there `bars_ago == 0` is the frame's last bar, not t, and a sweep
    older than the lookback is never scanned). == the bars_ago-0 read of
    SMC.liquidity_sweeps(closed.iloc[:t + 1])."""
    start = max(0, t - (SMC.SWEEP_LOOKBACK + 2 * SMC.SWING_WINDOW))
    return any(s["bars_ago"] == 0 and s["side"] == "sell_side"
               for s in SMC.liquidity_sweeps(closed.iloc[start:t + 1]))


# ---------------------------------------------------------------------------
# the cells (BUILD_SPEC6 §3.11.4 + AMENDMENTS6 B4 / B5 / B6)
# ---------------------------------------------------------------------------
_T, _N, _A = f"{DJ.SWEEP_TEST_PCT:g}", DJ.SWEEP_REF_SESSIONS, DJ.SWEEP_REF_MIN_AGE
_B5, _B10 = DJ.BODY_STEPS
_D = f"{DJ.DOWN_PCT:g}"
_BASE = (f"a body under {_B5}% of the range, the low within {_T}% either side of the prior {_N}-session low "
         f"(set {_A}+ sessions before), the ${LIQ_FLOOR_USD / 1e6:g}M/day floor")   # derived — the base rule's words
CELL_DEFS = {                       # derived — the words of each cell, built from the tab's constants
    "primary": ("Primary — 60%+ under the 52-week high",
                f"{_BASE}, {_D}%+ under the 52-week high (his \"60% 70%\"); next open, {PRIMARY_H} sessions, "
                "net of SPY"),
    "any_read": ("Any downtrend read (the tab's default view)",
                 f"{_BASE}, any of {_D}%+ under the 52-week high, {_D}%+ under the all-time high, or below the "
                 f"{DJ.SMA_FAST}- and {DJ.SMA_SLOW}-day"),
    "test_no_doji": ("The control — a test of the low without a doji",
                     f"a body of {_B10}% of the range or more, the same test, floor and 52-week read as the "
                     "primary, against its own matched days"),
    "w52_40": (f"{DJ.DEPTH_CHIPS[0]}%+ under the 52-week high", f"any_read and {DJ.DEPTH_CHIPS[0]}%+ under the 52-week high"),
    "w52_70": (f"{DJ.DEPTH_CHIPS[2]}%+ under the 52-week high (pre-declared too small)",
               f"any_read and {DJ.DEPTH_CHIPS[2]}%+ under the 52-week high"),
    "ath_60": (f"{_D}%+ under the all-time high", "any_read and the all-time-high read"),
    "mas": (f"Below the {DJ.SMA_FAST}- and {DJ.SMA_SLOW}-day", "any_read and the averages read"),
    "mas_only": ("Below the averages only", "any_read whose ONLY read is the averages"),
    "doji10": (f"Body under {_B10}%", f"the any_read rule at a body under {_B10}% of the range"),
    "above": ("Low at or above the prior low", f"any_read and the low at or above the prior low (0 … +{_T}%)"),
    "undercut": ("Undercut the prior low", f"any_read and the low under the prior low (−{_T}% … 0)"),
    "undercut_reclaimed": ("Undercut and reclaimed", "any_read, the low under the prior low and the close back above it"),
    "undercut_closed_under": ("Undercut, closed under", "any_read, the low under the prior low and the close not above it"),
    "undercut_deep": (f"Undercut by more than {_T}% (outside his test)",
                      f"a doji ({_B5}%), the prior low {_A}+ sessions old, the low more than {_T}% under it, "
                      "any read, the floor"),
    "swing_sweep": ("The smc swing-low sweep (Q4)",
                    f"a doji ({_B5}%), any read, the floor, and a sell-side sweep of a swing low "
                    f"(window {SMC.SWING_WINDOW}, lookback {SMC.SWEEP_LOOKBACK}) on the candle"),
    "dragonfly": ("Dragonfly doji", "any_read and the dragonfly shape"),
    "gravestone": ("Gravestone doji", "any_read and the gravestone shape"),
    "long_legged": ("Long-legged doji", "any_read and the long-legged shape"),
    "plain": ("Plain doji", "any_read and no named shape"),
    "vol_quiet": ("Quiet volume", f"any_read and volume at or under {DJ.VOL_QUIET_X:g}× the {DJ.VOL_AVG_BARS}-day average"),
    "vol_heavy": ("Heavy volume", f"any_read and volume at {DJ.VOL_HEAVY_X:g}× the {DJ.VOL_AVG_BARS}-day average or more"),
    "doji_no_test": ("A doji, no test", f"a doji ({_B5}%), the prior low {_A}+ sessions old, the low more than "
                                       f"{_T}% above it, any read, the floor"),
    "independent": ("One per name per 10 sessions",
                    f"any_read, greedy in date order: an event within {COOLDOWN} sessions after a kept one of the "
                    "same name is dropped"),
    "all_liquidity": ("No liquidity floor", "the any_read rule without the floor (placebos without it too)"),
    "from_close": ("Entry at the doji close", "any_read; the return from the doji's own close"),
    "confirm_entry": ("Entry at the confirming close",
                      f"any_read events that closed above the doji's high within {CONFIRM_SESSIONS} sessions; "
                      "the return from that close (placebos conditioned the same way)"),
    "test_no_doji_fire_pool": ("The control against the primary's pool (a sensitivity)",
                               "the test_no_doji events, their matched days drawn from the primary's pool rule "
                               "(the fire-based exclusions only, without the control's own-event exclusion) — "
                               "numbers only, never compared with the primary as a verdict"),
}
CELLS = tuple(CELL_DEFS)
CELL_ENTRY = {"from_close": "close", "confirm_entry": "confirm"}
NO_FLOOR_CELLS = ("all_liquidity",)
# B1 (fix round 1): the cells whose events need not be 10%-body fires — the
# fire-based exclusions never remove their OWN events, so their pools drop them
# (and the PLACEBO_GAP sessions after each) explicitly. Every other cell's mask
# is a subset of the 10%-body fires (test-pinned).
OWN_POOL_CELLS = ("test_no_doji", "undercut_deep", "swing_sweep", "doji_no_test")
# Fix round 2: {sensitivity cell: the cell whose events it re-reads} — the same
# events against the fire-only pool (placebo_pool without `own`), exploratory.
FIRE_POOL_SENSITIVITY = {"test_no_doji_fire_pool": "test_no_doji"}
assert CELLS[:3] == DSM.VERDICT_CELLS
assert not set(FIRE_POOL_SENSITIVITY) & (set(OWN_POOL_CELLS) | set(DSM.VERDICT_CELLS))
assert set(FIRE_POOL_SENSITIVITY.values()) <= set(OWN_POOL_CELLS)
assert set(OWN_POOL_CELLS) <= set(CELLS)
assert set(DSM.SERVED_CELLS) <= set(CELLS)


def _variant_mask(feat, name: str) -> np.ndarray:
    return np.asarray([v == name for v in feat["variant"].to_numpy(dtype=object)], dtype=bool)


def _vol_mask(feat, word: str) -> np.ndarray:
    return np.asarray([v == word for v in feat["vol_word"].to_numpy(dtype=object)], dtype=bool)


def cell_masks(a: dict) -> dict:
    """{cell_key: bool ndarray over a's bars}, keys == CELLS order. The three
    verdict cells are DJ.study_cells' own; the rest follow BUILD_SPEC6
    §3.11.4 with the spec's "primary" (the tab's default view) = `any_read`."""
    feat, n = a["feat"], a["n"]
    vc = DJ.study_cells(feat, pct_below_ath=a["pct_ath"], floor=a["floor"])
    anyr = vc["any_read"]
    elig, floor, any_rd = a["eligible"], a["floor"], a["any_rd"]
    doji5 = feat["doji5"].to_numpy(dtype=bool)
    ref_ok = feat["ref_ok"].to_numpy(dtype=bool) & np.isfinite(feat["ref_low"].to_numpy(dtype=float))
    tested = feat["tested"].to_numpy(dtype=bool)
    test_pct = np.nan_to_num(feat["test_pct"].to_numpy(dtype=float), nan=0.0)
    undercut = feat["undercut"].to_numpy(dtype=bool)
    reclaimed = feat["reclaimed"].to_numpy(dtype=bool)
    p52 = DJ._round_vec(feat["pct_below_52w"].to_numpy(dtype=float), DJ.TEST_ROUND_DP)
    st5_fired = a["st5"] == DJ.ROW_STATUSES[-1]
    st10_fired = a["st10"] == DJ.ROW_STATUSES[-1]
    base_doji = elig & floor & doji5 & any_rd
    swing = np.zeros(n, dtype=bool)
    for t in np.flatnonzero(base_doji):
        swing[t] = swing_sweep_at(a["closed"], int(t))
    indep = np.zeros(n, dtype=bool)
    last = None
    for t in np.flatnonzero(anyr):
        if last is None or t - last > COOLDOWN:
            indep[t] = True
            last = t
    m = {"primary": vc["primary"], "any_read": anyr, "test_no_doji": vc["test_no_doji"],
         "w52_40": anyr & (p52 >= DJ.DEPTH_CHIPS[0]), "w52_70": anyr & (p52 >= DJ.DEPTH_CHIPS[2]),
         "ath_60": anyr & a["rd"]["ath"], "mas": anyr & a["rd"]["mas"],
         "mas_only": anyr & (a["readset"] == READ_SET_BITS["mas"]),
         "doji10": elig & floor & st10_fired,
         "above": anyr & ~undercut, "undercut": anyr & undercut,
         "undercut_reclaimed": anyr & reclaimed, "undercut_closed_under": anyr & undercut & ~reclaimed,
         "undercut_deep": base_doji & ref_ok & ~tested & (test_pct < 0),
         "swing_sweep": swing,
         "dragonfly": anyr & _variant_mask(feat, "dragonfly"),
         "gravestone": anyr & _variant_mask(feat, "gravestone"),
         "long_legged": anyr & _variant_mask(feat, "long_legged"),
         "plain": anyr & _variant_mask(feat, "plain"),
         "vol_quiet": anyr & _vol_mask(feat, "quiet"), "vol_heavy": anyr & _vol_mask(feat, "heavy"),
         "doji_no_test": base_doji & ref_ok & ~tested & (test_pct > 0),
         "independent": indep, "all_liquidity": elig & st5_fired,
         "from_close": anyr.copy(), "confirm_entry": anyr.copy()}
    for k, src in FIRE_POOL_SENSITIVITY.items():
        m[k] = np.asarray(m[src], dtype=bool).copy()
    return {k: np.asarray(m[k], dtype=bool) for k in CELLS}


# ---------------------------------------------------------------------------
# placebos (BUILD_SPEC6 §3.11.1 item 8 + AMENDMENTS6 B1)
# ---------------------------------------------------------------------------
def placebo_pool(a: dict, t: int, *, floor: bool, own=None) -> np.ndarray:
    """Sessions s of the SAME name: eligible, the floor passed (when `floor`),
    the SAME read set as t, never a fired candle at the 10% body, PRIMARY_H
    sessions after them, more than PLACEBO_GAP sessions from t, and not inside
    the PLACEBO_GAP sessions after any 10%-body fire of the name (B1). With
    `own` (the cell's event mask over the name's bars), never one of the cell's
    own event sessions nor the PLACEBO_GAP sessions after one (B1, fix round 1)."""
    n = a["n"]
    idx = np.arange(n)
    ok = (a["eligible"] & (a["readset"] == a["readset"][t]) & ~a["fired10"] & ~a["after_fire"]
          & (idx + PRIMARY_H <= n - 1) & (np.abs(idx - t) > PLACEBO_GAP) & (a["readset"] > 0))
    if floor:
        ok &= a["floor"]
    if own is not None:
        own = np.asarray(own, dtype=bool)
        ok &= ~own & ~after_fire_mask(own)
    return np.flatnonzero(ok)


def own_masks(masks: dict) -> dict:
    """{cell: mask} for the OWN_POOL_CELLS (what `cell_pool` reads as a["own"])."""
    return {k: np.asarray(masks[k], dtype=bool) for k in OWN_POOL_CELLS}


def cell_pool(a: dict, key: str, t: int, *, floor: bool) -> np.ndarray:
    """The pool the run draws from for cell `key`: placebo_pool, plus the
    cell's own-event exclusion for an OWN_POOL_CELLS cell (a["own"][key])."""
    own = a["own"][key] if key in OWN_POOL_CELLS else None
    return placebo_pool(a, t, floor=floor, own=own)


def pool_key(key: str, si: int, t: int, floor: bool) -> tuple:
    """Draws are shared across every fire-based cell holding (si, t, floor);
    an OWN_POOL_CELLS cell's draws are its own."""
    return (si, t, floor, key if key in OWN_POOL_CELLS else None)


def draw_placebos(pool: np.ndarray, *, rng) -> np.ndarray:
    """PLACEBO_K draws: without replacement from a pool of k+, with
    replacement from a pool of 1..k-1 (a short pool, counted), none from 0."""
    pool = np.asarray(pool, dtype=int)
    if pool.size == 0:
        return pool
    return np.sort(rng.choice(pool, PLACEBO_K, replace=pool.size < PLACEBO_K))


def placebo_rng(seed: int, sym_index: int, t: int, floor: bool, *, cell: Optional[str] = None):
    """default_rng([SEED, symbol_index, t, floor_flag]) — and, for an
    OWN_POOL_CELLS cell, + [1 + its CELLS index] (its own stream)."""
    key = [int(seed), int(sym_index), int(t), int(bool(floor))]
    if cell is not None and cell in OWN_POOL_CELLS:
        key.append(1 + CELLS.index(cell))
    return np.random.default_rng(key)


# ---------------------------------------------------------------------------
# outcomes (identical rules on every day's own bar)
# ---------------------------------------------------------------------------
def _empty_outcome(confirm=None) -> dict:
    nan = float("nan")
    return {"ret": {h: nan for h in HORIZONS}, "adj": {h: nan for h in HORIZONS},
            "stop": {h: nan for h in HORIZONS}, "mfe": {h: nan for h in HORIZONS},
            "mae": {h: nan for h in HORIZONS}, "confirm": confirm}


def outcomes_at(a: dict, t: int, *, entry: str) -> dict:
    """R_h (%), the market-adjusted R_h (minus SPY over the identical window),
    stop-out_h (a close under the candle's low), MFE_h / MAE_h, and the
    confirmation ("up" = a close above the candle's high first, "down" = a
    close under its low first, "neither", None = the window is incomplete).
    entry "next_open": from open_{t+1}; "close": from close_t; "confirm": from
    the confirming close j* (NaN unless the candle confirmed "up")."""
    if entry not in ENTRIES:
        raise ValueError(f"entry {entry!r}")
    n, o, h, lo, c = a["n"], a["o"], a["h"], a["l"], a["c"]
    so, sc = a["spy_o"], a["spy_c"]
    cw = outcome_window(t, CONFIRM_SESSIONS)
    check_no_leak(t, (), cw)
    conf, jstar = None, None
    if cw.stop - 1 <= n - 1:
        conf = "neither"
        for j in cw:
            if c[j] > h[t]:
                conf, jstar = "up", j
                break
            if c[j] < lo[t]:
                conf = "down"
                break
    out = _empty_outcome(conf)
    if entry == "next_open":
        base, px_i = t, t + OUTCOME_START
        if px_i > n - 1:
            return out
        px, spx = o[px_i], so[px_i]
    elif entry == "close":
        base, px, spx = t, c[t], sc[t]
    else:
        if conf != "up":
            return out
        base, px, spx = jstar, c[jstar], sc[jstar]
    if not (np.isfinite(px) and px > 0):
        return out
    for hz in HORIZONS:
        win = outcome_window(base, hz)
        check_no_leak(t, (), win)
        if win.stop - 1 > n - 1:
            continue
        sl = slice(win.start, win.stop)
        cc, hh, ll = c[sl], h[sl], lo[sl]
        if not (np.isfinite(cc).all() and np.isfinite(hh).all() and np.isfinite(ll).all()):
            continue
        ret = (cc[-1] / px - 1.0) * 100.0
        out["ret"][hz] = ret
        sx = sc[win.stop - 1]
        if np.isfinite(spx) and spx > 0 and np.isfinite(sx):
            out["adj"][hz] = ret - (sx / spx - 1.0) * 100.0
        out["stop"][hz] = 100.0 if bool((cc < lo[t]).any()) else 0.0
        out["mfe"][hz] = (hh.max() / px - 1.0) * 100.0
        out["mae"][hz] = (ll.min() / px - 1.0) * 100.0
    return out


def _confirm_value(conf) -> float:
    if conf == "up":
        return 100.0
    if conf in ("down", "neither"):
        return 0.0
    return float("nan")


# ---------------------------------------------------------------------------
# the bootstrap (event + its placebos resampled together)
# ---------------------------------------------------------------------------
def _prep(ev, pl, pl_owner, clusters):
    """The contrast set: events with a finite value AND at least one finite
    placebo; placebos finite with a kept owner. Returns (ev, pl, owner, codes,
    n_clusters) with owners re-indexed onto the kept events."""
    ev = np.asarray(ev, dtype=float)
    pl = np.asarray(pl, dtype=float)
    owner = np.asarray(pl_owner, dtype=int)
    cl = np.asarray(clusters, dtype=object)
    if ev.size == 0:
        return ev, pl[:0], owner[:0], np.zeros(0, dtype=int), 0
    pl_ok = np.isfinite(pl) & (owner >= 0) & (owner < ev.size)
    pl_ok[pl_ok] &= np.isfinite(ev[owner[pl_ok]])
    has_pl = np.zeros(ev.size, dtype=bool)
    has_pl[owner[pl_ok]] = True
    keep = np.isfinite(ev) & has_pl
    remap = np.full(ev.size, -1, dtype=int)
    remap[keep] = np.arange(int(keep.sum()))
    pl_ok &= keep[np.clip(owner, 0, ev.size - 1)]
    ev2, pl2, own2 = ev[keep], pl[pl_ok], remap[owner[pl_ok]]
    labels = [str(x) for x in cl[keep]]
    uniq = {lab: i for i, lab in enumerate(sorted(set(labels)))}
    codes = np.asarray([uniq[lab] for lab in labels], dtype=int)
    return ev2, pl2, own2, codes, len(uniq)


def _wmedian(vals_sorted: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Row-wise median of `vals_sorted` repeated by the integer weights `w`
    (draws x n) — == np.median(np.repeat(vals, w_row)) for every row."""
    cw = np.cumsum(w, axis=1, dtype=np.int64)
    tot = cw[:, -1]
    k1, k2 = (tot - 1) // 2, tot // 2
    n = vals_sorted.size
    i1 = np.minimum((cw <= k1[:, None]).sum(axis=1), n - 1)
    i2 = np.minimum((cw <= k2[:, None]).sum(axis=1), n - 1)
    out = (vals_sorted[i1] + vals_sorted[i2]) / 2.0
    return np.where(tot > 0, out, np.nan)


def _stat(vals: np.ndarray, w: np.ndarray, stat: str) -> np.ndarray:
    if stat == "median":
        order = np.argsort(vals, kind="mergesort")
        return _wmedian(vals[order], w[:, order])
    tot = w.sum(axis=1)
    return np.where(tot > 0, (w @ vals) / np.maximum(tot, 1), np.nan)


def point_diff(ev, pl, pl_owner, *, stat: str) -> Optional[float]:
    """stat(events) − stat(placebos) over the contrast set (unweighted)."""
    ev2, pl2, _o, _c, _n = _prep(ev, pl, pl_owner, np.zeros(len(np.asarray(ev))))
    if ev2.size == 0 or pl2.size == 0:
        return None
    f = np.median if stat == "median" else np.mean
    return float(f(ev2) - f(pl2))


def cluster_boot(ev, pl, pl_owner, clusters, *, stat: str, draws: int, seed) -> Optional[np.ndarray]:
    """`draws` bootstrap values of stat(events) − stat(placebos): per draw the
    clusters are resampled with replacement (rng.integers(0, C, C)) and every
    event carries its own placebos. None under 2 clusters. stat "median" |
    "mean"."""
    ev2, pl2, own2, codes, nc = _prep(ev, pl, pl_owner, clusters)
    if nc < 2 or pl2.size == 0:
        return None
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, nc, size=(int(draws), nc))
    pl_codes = codes[own2]
    width = max(ev2.size + pl2.size, 1)
    step = max(1, min(int(draws), BOOT_CELLS_MAX // width))
    out = np.empty(int(draws), dtype=float)
    for s in range(0, int(draws), step):
        p = pick[s:s + step]
        rows = p.shape[0]
        flat = (np.arange(rows)[:, None] * nc + p).ravel()
        cnt = np.bincount(flat, minlength=rows * nc).reshape(rows, nc).astype(np.int32)
        out[s:s + step] = _stat(ev2, cnt[:, codes], stat) - _stat(pl2, cnt[:, pl_codes], stat)
    return out


def ci_from_boot(boot, *, ci_pct: float = CI_PCT) -> Optional[list]:
    if boot is None:
        return None
    b = np.asarray(boot, dtype=float)
    b = b[np.isfinite(b)]
    if b.size == 0:
        return None
    lo, hi = np.percentile(b, [(100.0 - ci_pct) / 2.0, 100.0 - (100.0 - ci_pct) / 2.0])
    return [_r(lo), _r(hi)]


def p_from_boot(boot) -> Optional[float]:
    """Two-sided bootstrap p: 2 × the smaller tail share at zero, capped at 1."""
    if boot is None:
        return None
    b = np.asarray(boot, dtype=float)
    b = b[np.isfinite(b)]
    if b.size == 0:
        return None
    return float(min(1.0, 2.0 * min(np.mean(b <= 0), np.mean(b >= 0))))


def cluster_ci(ev, pl, pl_owner, clusters, *, stat: str, draws: int, seed,
               ci_pct: float = CI_PCT) -> Optional[list]:
    """The percentile CI of cluster_boot, 2 dp; None under 2 clusters."""
    return ci_from_boot(cluster_boot(ev, pl, pl_owner, clusters, stat=stat, draws=draws, seed=seed),
                        ci_pct=ci_pct)


def holm(pvals: list) -> list:
    """Holm step-down adjusted p-values (same order as given; None stays None)."""
    idx = [i for i, p in enumerate(pvals) if p is not None]
    out: list = [None] * len(pvals)
    m = len(idx)
    run = 0.0
    for r, i in enumerate(sorted(idx, key=lambda i: (pvals[i], i))):
        run = max(run, min(1.0, (m - r) * float(pvals[i])))
        out[i] = run
    return out


def holm_levels(pvals: list) -> list:
    """The CI level each p's Holm rank tests at: rank r (0 = smallest p) of m ->
    100 − (100 − CI_PCT) / (m − r). None stays None (CI_PCT is served)."""
    idx = [i for i, p in enumerate(pvals) if p is not None]
    out: list = [None] * len(pvals)
    m = len(idx)
    for r, i in enumerate(sorted(idx, key=lambda i: (pvals[i], i))):
        out[i] = 100.0 - (100.0 - CI_PCT) / (m - r)
    return out


def cell_verdict(n_events: int, n_dates: int, ci) -> str:
    """too_small under MIN_CELL_EVENTS events; else RS.verdict(n_dates, ci)
    (too_small under MIN_BUCKET_N dates or no CI; a bound exactly 0 is
    no_signal)."""
    if int(n_events or 0) < MIN_CELL_EVENTS:
        return "too_small"
    return RS.verdict(n_dates, ci)


def axes_verdict(n_events: int, n_dates: int, n_symbols: int, ci_block, ci_symbol, *, p_holm=None) -> str:
    """AMENDMENTS6 B2 + B6: the block axis and the name axis must AGREE, else
    "axes_disagree"; a separating / inverted read whose Holm-adjusted p is above
    ALPHA (the step-down stopped earlier) reads no_signal. Every count is the
    CONTRAST set's (`contrast_counts`). The block axis is gated on the cell's
    sessions (n_dates); the name axis on its own clusters (n_symbols — fix
    round 1). Either axis too_small -> too_small."""
    vb = cell_verdict(n_events, n_dates, ci_block)
    if vb == "too_small":
        return vb
    vs = cell_verdict(n_events, n_symbols, ci_symbol)
    if vs == "too_small":
        return vs
    if vb != vs:
        return "axes_disagree"
    if vb in ("separates", "inverted") and p_holm is not None and p_holm > ALPHA:
        return "no_signal"
    return vb


# ---------------------------------------------------------------------------
# one cell
# ---------------------------------------------------------------------------
def _arrays(events: list, field: str, h):
    """(ev, pl, owner) for one outcome field at horizon h ("confirm" ignores h)."""
    def val(o):
        if field == "confirm":
            return _confirm_value(o.get("confirm"))
        return o[field][h]
    ev = np.asarray([val(e["ev"]) for e in events], dtype=float)
    pl, owner = [], []
    for i, e in enumerate(events):
        for p in e["pls"]:
            pl.append(val(p))
            owner.append(i)
    return ev, np.asarray(pl, dtype=float), np.asarray(owner, dtype=int)


def _clusters(events: list, axis: str) -> list:
    if axis == "block":
        return [int(e["pos"]) // BLOCK_SESSIONS for e in events]
    if axis == "date":
        return [e["date"] for e in events]
    return [e["sym"] for e in events]


def _seed(seed: int, key: str, axis: str, stat: str, h: int) -> list:
    return [int(seed), CELLS.index(key), AXES.index(axis), STATS.index(stat), int(h)]


def _median_of(x) -> Optional[float]:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(np.median(x)) if x.size else None


def _mean_of(x) -> Optional[float]:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(np.mean(x)) if x.size else None


def _contrast_sides(ev, pl, owner):
    ev2, pl2, _o, _c, _n = _prep(ev, pl, owner, np.zeros(ev.size))
    return ev2, pl2


def cell_pvalue(key: str, events: list, *, draws: int, seed: int) -> Optional[float]:
    """The verdict p of a verdict cell: the larger of the block-axis and the
    name-axis bootstrap p of the market-adjusted Δmedian at PRIMARY_H (both
    axes must clear — B2)."""
    ev, pl, ow = _arrays(events, "adj", PRIMARY_H)
    ps = [p_from_boot(cluster_boot(ev, pl, ow, _clusters(events, ax), stat="median", draws=draws,
                                   seed=_seed(seed, key, ax, "adj_median", PRIMARY_H)))
          for ax in ("block", "symbol")]
    return None if any(p is None for p in ps) else max(ps)


def count_block(key: str, events: list) -> dict:
    """The DETECTION counts (a count-only artifact's cell; never a verdict's)."""
    label, definition = CELL_DEFS[key]
    role = DSM.ROLE_VERDICT if key in DSM.VERDICT_CELLS else DSM.EXPLORATORY_LABEL
    vals = {"label": label, "definition": definition, "role": role, "n_events": len(events),
            "n_dates": len({e["date"] for e in events}), "n_symbols": len({e["sym"] for e in events})}
    return {k: vals[k] for k in DSM.COUNT_CELL_KEYS}


def contrast_events(events: list) -> list:
    """The events the verdict contrast reads: a finite market-adjusted
    R_PRIMARY_H AND at least one finite placebo of it (== `_prep`'s keep set
    on the "adj" field at PRIMARY_H)."""
    def fin(o):
        return np.isfinite(float(o["adj"][PRIMARY_H]))
    return [e for e in events if fin(e["ev"]) and any(fin(p) for p in e["pls"])]


def contrast_counts(events: list) -> dict:
    """{"n_events", "n_dates", "n_symbols", "n_blocks"} over `contrast_events`
    — what every gate reads — and "n_detected" = every detected event."""
    ce = contrast_events(events)
    return {"n_events": len(ce), "n_dates": len({e["date"] for e in ce}),
            "n_symbols": len({e["sym"] for e in ce}), "n_blocks": len(set(_clusters(ce, "block"))),
            "n_detected": len(events)}


def cell_too_small(counts: dict) -> bool:
    """The gate before any p-value: either axis too_small on the contrast counts."""
    return axes_verdict(counts["n_events"], counts["n_dates"], counts["n_symbols"], [1.0, 1.0],
                        [1.0, 1.0]) == "too_small"


def cell_block(key: str, events: list, *, draws: int, seed: int, count_only: bool,
               ci_pct: float = CI_PCT, p_holm: Optional[float] = None) -> dict:
    """One cell: exactly DSM.CELL_KEYS (DSM.COUNT_CELL_KEYS when count_only —
    no outcome key exists there). `events` = [{"sym", "date", "pos", "ev":
    outcome, "pls": [outcome …], "short": bool}]. A verdict cell's CIs are at
    `ci_pct` (its Holm level) and its verdict needs both axes (B2); an
    exploratory cell carries verdict None (B6)."""
    if count_only:
        return count_block(key, events)
    cb = {**count_block(key, events), **contrast_counts(events)}   # the served n_* = the contrast set's
    verdict_cell = key in DSM.VERDICT_CELLS
    level = float(ci_pct) if verdict_cell else CI_PCT
    matched = [e for e in events if e["pls"]]
    H = PRIMARY_H

    def boot(field, h, axis, stat):
        ev, pl, ow = _arrays(matched, field, h)
        label = {"adj": "adj_median", "confirm": "confirm"}.get(field, stat)
        return cluster_boot(ev, pl, ow, _clusters(matched, axis), stat=stat, draws=draws,
                            seed=_seed(seed, key, axis, label, h))

    def ci(field, h, axis, stat):
        return ci_from_boot(boot(field, h, axis, stat), ci_pct=level)

    def sides(field, h):
        ev, pl, ow = _arrays(matched, field, h)
        return _contrast_sides(ev, pl, ow)

    ev_r, pl_r = sides("ret", H)
    ev_a, pl_a = sides("adj", H)
    ev_c, pl_c = sides("confirm", H)
    ev_s, pl_s = sides("stop", H)
    em, pm = _median_of(ev_r), _median_of(pl_r)
    aem, apm = _median_of(ev_a), _median_of(pl_a)
    emean, pmean = _mean_of(ev_r), _mean_of(pl_r)
    cp, pcp = _mean_of(ev_c), _mean_of(pl_c)
    ci_block, ci_date, ci_symbol = (ci("ret", H, ax, "median") for ax in AXES)
    adj_ci_block, adj_ci_symbol = ci("adj", H, "block", "median"), ci("adj", H, "symbol", "median")
    n_m = len(matched)
    if verdict_cell:
        verdict = axes_verdict(cb["n_events"], cb["n_dates"], cb["n_symbols"], adj_ci_block, adj_ci_symbol,
                               p_holm=p_holm)
    else:
        verdict = None
    by_h = {}
    for h in HORIZONS:
        e_h, p_h = sides("ret", h)
        ea_h, pa_h = sides("adj", h)
        by_h[str(h)] = {"n_events": int(e_h.size), "event_median_pct": _r(_median_of(e_h)),
                        "placebo_median_pct": _r(_median_of(p_h)),
                        "median_diff_pp": _r(None if e_h.size == 0 or p_h.size == 0
                                             else _median_of(e_h) - _median_of(p_h)),
                        "ci_block": ci_block if h == H else ci("ret", h, "block", "median"),
                        "adj_median_diff_pp": _r(None if ea_h.size == 0 or pa_h.size == 0
                                                 else _median_of(ea_h) - _median_of(pa_h)),
                        "adj_ci_block": adj_ci_block if h == H else ci("adj", h, "block", "median")}
    mfe_e, _ = sides("mfe", H)
    mae_e, _ = sides("mae", H)

    def diff(x, y):
        return None if x is None or y is None else x - y

    vals = {**cb, "verdict": verdict, "ci_pct": _r(level), "p_holm": _r(p_holm, 4) if verdict_cell else None,
            "horizon": H, "entry": CELL_ENTRY.get(key, "next_open"),
            "n_placebo": int(sum(len(e["pls"]) for e in matched)),
            "n_unmatched": int(len(events) - n_m),
            "placebo_short_pool": int(sum(1 for e in events if e.get("short"))),
            "event_median_pct": _r(em), "placebo_median_pct": _r(pm), "median_diff_pp": _r(diff(em, pm)),
            "ci_block": ci_block, "ci_date": ci_date, "ci_symbol": ci_symbol,
            "robust": (RS.verdict(cb["n_dates"], adj_ci_block) == RS.verdict(cb["n_symbols"], adj_ci_symbol)),
            "adj_event_median_pct": _r(aem), "adj_placebo_median_pct": _r(apm),
            "adj_median_diff_pp": _r(diff(aem, apm)), "adj_ci_block": adj_ci_block,
            "adj_ci_symbol": adj_ci_symbol,
            "event_mean_pct": _r(emean), "placebo_mean_pct": _r(pmean), "mean_diff_pp": _r(diff(emean, pmean)),
            "ci_mean_block": ci("ret", H, "block", "mean"),
            "net_mean_pct": _r(None if emean is None else emean - COST_ROUND_TRIP_PCT),
            "confirm_pct": _r(cp), "placebo_confirm_pct": _r(pcp), "confirm_diff_pp": _r(diff(cp, pcp)),
            "ci_confirm_block": ci("confirm", H, "block", "mean"),
            "stop_pct": _r(_mean_of(ev_s)), "placebo_stop_pct": _r(_mean_of(pl_s)),
            "mfe_median_pct": _r(_median_of(mfe_e)), "mae_median_pct": _r(_median_of(mae_e)),
            "by_horizon": by_h}
    return {k: _clean(vals[k]) for k in DSM.CELL_KEYS}


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------
def _baselines(acc: dict) -> dict:
    out = {}
    for k in ("w52", "ath", "mas", "any"):
        v = np.asarray(acc[k]["v"], dtype=float)
        d = acc[k]["d"]
        out[k] = {"n_days": int(v.size), "n_dates": len(set(d)), "median_pct": _r(_median_of(v)),
                  "mean_pct": _r(_mean_of(v))}
    return {"all_days": out}


def _r_primary(a: dict) -> np.ndarray:
    """R_PRIMARY_H from the next open for every bar (vectorised; == outcomes_at)."""
    n, o, h, lo, c = a["n"], a["o"], a["h"], a["l"], a["c"]
    out = np.full(n, np.nan)
    if n > PRIMARY_H:
        t = np.arange(n - PRIMARY_H)
        px = o[t + OUTCOME_START]
        win_ok = np.ones(t.size, dtype=bool)
        for j in range(OUTCOME_START, PRIMARY_H + 1):
            win_ok &= np.isfinite(c[t + j]) & np.isfinite(h[t + j]) & np.isfinite(lo[t + j])
        with np.errstate(divide="ignore", invalid="ignore"):
            r = (c[t + PRIMARY_H] / px - 1.0) * 100.0
        out[t] = np.where(win_ok & np.isfinite(px) & (px > 0), r, np.nan)
    return out


def run_study(frames: dict, docs: dict, listing: dict, *, syms: list, as_of, draws: int, seed: int,
              count_only: bool, read_sec: float = 0.0) -> dict:
    """The point-in-time replay of the tab's detector over every cached bar.
    Placebos drawn ONCE per (symbol, t, floor flag) and shared by every cell
    holding that event; outcomes cached per (symbol, t, entry)."""
    ph = {k: 0.0 for k in PHASES}
    ph["read"] = round(float(read_sec), 1)
    as_of_iso = str(as_of)[:10]
    spy = spy_maps(frames.get(BENCH), as_of_iso)
    cal = np.asarray(spy["cal"], dtype=object)
    store: dict = {}
    events = {k: [] for k in CELLS}
    basis = {"history": 0, "frame": 0, "cut_frame_only": 0}
    n_bars = n_elig = 0
    elig_dates: set = set()
    acc = {k: {"v": [], "d": []} for k in ("w52", "ath", "mas", "any")}
    for si, sym in enumerate(sorted({str(s).upper() for s in syms})):
        df = frames.get(sym)
        if df is None or len(df) == 0:
            continue
        n_bars += 1
        t0 = time.time()
        a = symbol_arrays(sym, df, (docs or {}).get(sym), ATH.listed_for(sym, listing or {}),
                          as_of=date.fromisoformat(as_of_iso), spy=spy)
        ph["features"] += time.time() - t0
        if a is None:
            continue
        basis["cut_frame_only" if a["cut"] else ("history" if a["usable"] else "frame")] += 1
        t0 = time.time()
        if a["eligible"].any():
            n_elig += 1
            elig_dates.update(a["dates"][a["eligible"]].tolist())
        masks = cell_masks(a)
        a["own"] = own_masks(masks)
        for k in CELLS:
            for t in np.flatnonzero(masks[k]):
                check_no_leak(int(t), feature_window(int(t)), ())
                events[k].append((si, int(t)))
        if not count_only:
            r10 = _r_primary(a)
            base = a["eligible"] & a["floor"]
            for k, m in (("w52", a["rd"]["w52"]), ("ath", a["rd"]["ath"]), ("mas", a["rd"]["mas"]),
                         ("any", a["any_rd"])):
                sel = base & m & np.isfinite(r10)
                acc[k]["v"].extend(r10[sel].tolist())
                acc[k]["d"].extend(a["dates"][sel].tolist())
        for drop in ("feat", "closed"):
            a.pop(drop, None)
        store[si] = a
        ph["events"] += time.time() - t0
    out = {"universe_n": len(syms), "n_names_with_bars": n_bars, "n_names_eligible": n_elig,
           "first_session": min(elig_dates) if elig_dates else None,
           "last_session": max(elig_dates) if elig_dates else None, "n_sessions": len(elig_dates),
           "ath_basis": basis}
    if count_only:
        cells = {k: count_block(k, [{"sym": store[si]["sym"], "date": store[si]["dates"][t]}
                                    for si, t in events[k]]) for k in CELLS}
        return {**out, "primary": cells["primary"], "cells": cells, "baselines": None,
                "phase_sec": {k: round(v, 1) for k, v in ph.items()}}
    # placebos — once per (symbol, t, floor flag) for the fire-based cells; an
    # OWN_POOL_CELLS cell's own pool and stream (B1, fix round 1)
    t0 = time.time()
    pls: dict = {}
    for k in CELLS:
        ff = k not in NO_FLOOR_CELLS
        for si, t in events[k]:
            pk = pool_key(k, si, t, ff)
            if pk not in pls:
                pool = cell_pool(store[si], k, t, floor=ff)
                pls[pk] = (draw_placebos(pool, rng=placebo_rng(seed, si, t, ff, cell=pk[3])),
                           0 < pool.size < PLACEBO_K)
    ph["placebo"] = time.time() - t0
    # outcomes — cached per (symbol, t, entry)
    t0 = time.time()
    oc: dict = {}

    def outc(si, t, entry):
        key = (si, t, entry)
        if key not in oc:
            oc[key] = outcomes_at(store[si], t, entry=entry)
        return oc[key]

    recs: dict = {}
    for k in CELLS:
        entry = CELL_ENTRY.get(k, "next_open")
        ff = k not in NO_FLOOR_CELLS
        rows = []
        for si, t in events[k]:
            a = store[si]
            ev = outc(si, t, entry)
            if entry == "confirm" and ev.get("confirm") != "up":
                continue
            draw, short = pls[pool_key(k, si, t, ff)]
            pl = [outc(si, int(s), entry) for s in draw]
            if entry == "confirm":
                pl = [p for p in pl if p.get("confirm") == "up"]
            d = a["dates"][t]
            rows.append({"sym": a["sym"], "date": d, "pos": int(np.searchsorted(cal, d)), "ev": ev,
                         "pls": pl, "short": bool(short)})
        recs[k] = rows
    ph["outcomes"] = time.time() - t0
    # the three verdict cells: p, Holm, the Holm CI level
    t0 = time.time()
    vk = DSM.VERDICT_CELLS
    pv = []
    for k in vk:
        small = cell_too_small(contrast_counts(recs[k]))          # the contrast set's counts (fix round 1)
        pv.append(None if small else cell_pvalue(k, [e for e in recs[k] if e["pls"]], draws=draws,
                                                     seed=seed))
    p_holm = holm(pv)
    levels = holm_levels(pv)
    cells = {}
    for k in CELLS:
        if k in vk:
            i = vk.index(k)
            cells[k] = cell_block(k, recs[k], draws=draws, seed=seed, count_only=False,
                                  ci_pct=levels[i] if levels[i] is not None else CI_PCT, p_holm=p_holm[i])
        else:
            cells[k] = cell_block(k, recs[k], draws=draws, seed=seed, count_only=False)
    ph["bootstrap"] = time.time() - t0
    return {**out, "primary": cells["primary"], "cells": cells, "baselines": _baselines(acc),
            "phase_sec": {k: round(v, 1) for k, v in ph.items()}}


def definitions(draws: int, seed: int) -> dict:
    """Every constant the run used (the tab's, DSM's and this file's), by name."""
    return {"DOJI_BODY_PCT": DJ.DOJI_BODY_PCT, "DOJI_BODY_WIDE_PCT": DJ.DOJI_BODY_WIDE_PCT,
            "SWEEP_TEST_PCT": DJ.SWEEP_TEST_PCT, "TEST_ROUND_DP": DJ.TEST_ROUND_DP,
            "SWEEP_REF_SESSIONS": DJ.SWEEP_REF_SESSIONS, "SWEEP_REF_MIN_AGE": DJ.SWEEP_REF_MIN_AGE,
            "DOWN_PCT": DJ.DOWN_PCT, "DEPTH_CHIPS": list(DJ.DEPTH_CHIPS), "SMA_FAST": DJ.SMA_FAST,
            "SMA_SLOW": DJ.SMA_SLOW, "YEAR_BARS": DJ.YEAR_BARS, "SMALL_WICK_PCT": DJ.SMALL_WICK_PCT,
            "LONG_LEG_BARS": DJ.LONG_LEG_BARS, "VOL_AVG_BARS": DJ.VOL_AVG_BARS, "VOL_QUIET_X": DJ.VOL_QUIET_X,
            "VOL_HEAVY_X": DJ.VOL_HEAVY_X, "GLITCH_RATIO": DJ.GLITCH_RATIO, "PRIMARY_READ": DJ.PRIMARY_READ,
            "SWING_WINDOW": SMC.SWING_WINDOW, "SWEEP_LOOKBACK": SMC.SWEEP_LOOKBACK,
            "LIQ_FLOOR_USD": LIQ_FLOOR_USD, "HORIZONS": list(HORIZONS), "PRIMARY_H": PRIMARY_H,
            "CONFIRM_SESSIONS": CONFIRM_SESSIONS, "PLACEBO_K": PLACEBO_K, "PLACEBO_GAP": PLACEBO_GAP,
            "COOLDOWN": COOLDOWN, "COST_ROUND_TRIP_PCT": COST_ROUND_TRIP_PCT, "CI_PCT": CI_PCT,
            "ALPHA": ALPHA, "BLOCK_SESSIONS": BLOCK_SESSIONS, "MIN_CELL_EVENTS": MIN_CELL_EVENTS,
            "MIN_CELL_DATES": MIN_CELL_DATES, "VERDICT_CELLS": list(DSM.VERDICT_CELLS),
            "PREDECLARED_TOO_SMALL": list(DSM.PREDECLARED_TOO_SMALL), "CELLS": list(CELLS),
            "BENCH": BENCH, "UNIVERSE": f"{UNIVERSE_KEY} − ETFs − delisted (today's list)",
            "ROLL_AT": KL.ROLL_AT.strftime("%H:%M"), "draws": int(draws), "seed": int(seed),
            "refuse_window_et": f"{RS.REFUSE_FROM[0]:02d}:{RS.REFUSE_FROM[1]:02d}–"
                                f"{RS.REFUSE_TO[0]:02d}:{RS.REFUSE_TO[1]:02d}",
            "cohort": "survivors-only (today's list)"}


def measured_literal(art: dict) -> dict:
    """The chart_maps.doji_sweep_measured.MEASURED literal for an artifact
    (exactly DSM.LITERAL_TOP_KEYS; the primary's DSM.LITERAL_PRIMARY_KEYS; each
    served cell's DSM.literal_cell_keys)."""
    def pick(blk, keys):
        blk = blk if isinstance(blk, dict) else {}
        return {k: blk.get(k) for k in keys}
    d = art.get("definitions") or {}
    cells = art.get("cells") or {}
    vals = {"status": "measured", "schema": art.get("schema"), "script": SCRIPT, "artifact": ARTIFACT,
            "prereg": PREREG, "prereg_commit": art.get("prereg_commit"),
            "prereg_blob": art.get("prereg_blob"), "run_date": art.get("run_date"), "as_of": art.get("as_of"),
            "first_session": art.get("first_session"), "last_session": art.get("last_session"),
            "cohort": "survivors-only", "cost_round_trip_pct": d.get("COST_ROUND_TRIP_PCT"),
            "confirm_sessions": d.get("CONFIRM_SESSIONS"), "block_sessions": d.get("BLOCK_SESSIONS"),
            "primary": pick(art.get("primary"), DSM.LITERAL_PRIMARY_KEYS),
            "cells": {k: pick(cells.get(k), DSM.literal_cell_keys(k)) for k in DSM.SERVED_CELLS}}
    return {k: vals[k] for k in DSM.LITERAL_TOP_KEYS}


def pin_violations(art: dict) -> list:
    """Why an artifact may NOT be pasted as MEASURED (final-critic fix
    2026-10-16) — [] when it is the one pre-registered outcome run: real
    (not smoke / count-only), named prereg, SEED_DEFAULT / DRAWS_DEFAULT, the
    tab's default as-of for its run date, a committed clean tree and no
    provider call."""
    art = art if isinstance(art, dict) else {}
    d = art.get("definitions") or {}
    g = art.get("git") or {}
    bad = []
    if art.get("smoke") is not False or art.get("count_only") is not False:
        bad.append("smoke or count-only")
    if not art.get("prereg_commit") or not art.get("prereg_blob"):
        bad.append("no prereg commit / blob")
    if d.get("seed") != SEED_DEFAULT:
        bad.append(f"seed {d.get('seed')} != SEED_DEFAULT")
    if d.get("draws") != DRAWS_DEFAULT:
        bad.append(f"draws {d.get('draws')} != DRAWS_DEFAULT")
    try:
        cuts = as_of_cuts(art.get("run_date"))
    except (TypeError, ValueError):
        cuts = set()
    if art.get("as_of") not in cuts:
        bad.append(f"as_of {art.get('as_of')} is not the default for run_date {art.get('run_date')}")
    if not g.get("head") or g.get("porcelain_empty") is not True:
        bad.append("not a committed clean tree")
    if art.get("provider_calls") != 0:
        bad.append(f"provider_calls {art.get('provider_calls')}")
    return bad


# ---------------------------------------------------------------------------
# I/O guards (AMENDMENTS6 B18)
# ---------------------------------------------------------------------------
def block_writes() -> None:
    """Every pymongo write method -> recorded; a data write RAISES
    WriteBlockedError, an index create is a no-op (this process only)."""
    from pymongo.collection import Collection

    def _make(name):
        def _blocked(self, *a, **k):
            ATTEMPTED.append(f"{getattr(self, 'name', '?')}.{name}")
            if name in INDEX_METHODS:
                return "blocked_index"
            raise WriteBlockedError(f"{name} blocked — the study is read-only")
        return _blocked
    for m in RS.WRITE_METHODS:
        if hasattr(Collection, m):
            setattr(Collection, m, _make(m))


def data_writes(attempted) -> list:
    """The attempted writes that are not an index create."""
    return sorted({w for w in attempted if w.rsplit(".", 1)[-1] not in INDEX_METHODS})


def block_fetches() -> None:
    """Every sepa.prices name in NO_FETCH_FUNCS and every sepa.universe name in
    UNIVERSE_NO_FETCH_FUNCS -> records the call in FETCH_CALLS (the universe's
    as "universe.<name>") and raises NoFetchError; sepa.universe reads every
    cached list whatever its age (UNIVERSE_TTL_SEC). This process only."""
    from sepa import universe as UNIV

    def _make(mod, label, name):
        def _refused(*a, **k):
            FETCH_CALLS.append(label)
            raise NoFetchError(f"{mod}.{name} called — the study reads the cache only")
        return _refused
    for name in NO_FETCH_FUNCS:
        if hasattr(prices, name):
            setattr(prices, name, _make("sepa.prices", name, name))
    for name in UNIVERSE_NO_FETCH_FUNCS:
        if hasattr(UNIV, name):
            setattr(UNIV, name, _make("sepa.universe", f"universe.{name}", name))
    UNIV.UNIV_CACHE_TTL_SEC = UNIVERSE_TTL_SEC


def git_blob_sha(path) -> str:
    """== `git hash-object <path>`: sha1(b"blob <len>\\0" + data)."""
    data = Path(path).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def prereg_file() -> Path:
    """The prereg on disk: <repo>/PREREG (in the throwaway container, where
    backend/ is /app, that is /docs/research/… — the launcher mounts it ro)."""
    return Path(__file__).resolve().parents[2] / PREREG


def git_state(root=None) -> dict:
    """{"head", "porcelain_empty"} from git in `root` (the repo), None each when
    git or the .git dir is unreadable (the throwaway container mounts backend/
    only — the launcher then passes --git-head / --git-clean)."""
    root = str(root or Path(__file__).resolve().parents[2])
    out = {"head": None, "porcelain_empty": None}
    try:
        h = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True,
                           timeout=20)
        if h.returncode == 0 and h.stdout.strip():
            out["head"] = h.stdout.strip()
        s = subprocess.run(["git", "-C", root, "status", "--porcelain"], capture_output=True, text=True,
                           timeout=60)
        if s.returncode == 0:
            out["porcelain_empty"] = s.stdout.strip() == ""
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def default_universe(*, universe_fn=None) -> list:
    """DR._resolve_universe("full")[0] − FAL._static_etfs() − symbols.is_delisted (today's list)."""
    from sepa import symbols
    raw = universe_fn(UNIVERSE_KEY) if universe_fn else DR._resolve_universe(UNIVERSE_KEY)[0]
    etfs = FAL._static_etfs()
    out, seen = [], set()
    for s in raw or []:
        s = str(s or "").strip().upper()
        if s and s not in seen and s not in etfs and not symbols.is_delisted(s):
            seen.add(s)
            out.append(s)
    return out


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Doji Sweep study (read-only, cache only).", allow_abbrev=False)
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (default: the tab's last closed session)")
    ap.add_argument("--draws", type=int, default=DRAWS_DEFAULT)
    ap.add_argument("--seed", type=int, default=SEED_DEFAULT)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--prereg-commit", default=None, help="the commit holding the prereg (outcome runs)")
    ap.add_argument("--prereg-blob", default=None, help="git hash-object of the prereg (outcome runs)")
    ap.add_argument("--force-window", action="store_true", help="run inside 09:00–16:30 ET anyway")
    ap.add_argument("--limit", type=int, default=None, help="SMOKE: first N names, counts only")
    ap.add_argument("--count-only", action="store_true", help="counts only — no outcome is read")
    ap.add_argument("--no-fetch", action="store_true", default=True,
                    help="the ONLY mode: the cached bars, never a provider (kept explicit)")
    ap.add_argument("--git-head", default=None, help="the host's HEAD when the container holds no .git (B12)")
    ap.add_argument("--git-clean", action="store_true",
                    help="the launcher's attestation that the host's git status --porcelain is empty (B12)")
    return ap.parse_args(argv)


def outcome_pin_refusal(a) -> Optional[str]:
    """Final-critic fix 2026-10-16: the prereg names ONE outcome run, so its
    knobs are not free on the CLI — an outcome run uses SEED_DEFAULT,
    DRAWS_DEFAULT and the tab's default as-of, or it is refused. None = pinned."""
    if a.seed != SEED_DEFAULT:
        return f"--seed {a.seed} is not the pre-registered SEED_DEFAULT {SEED_DEFAULT}"
    if a.draws != DRAWS_DEFAULT:
        return f"--draws {a.draws} is not the pre-registered DRAWS_DEFAULT {DRAWS_DEFAULT}"
    if a.as_of is not None:
        return "--as-of is not allowed: the outcome run measures up to the tab's last closed session"
    return None


def as_of_cuts(run_date: str) -> set:
    """Every cut an outcome run on `run_date` could have measured up to (its
    clock is not in the artifact — 00:00 and 23:59 ET bracket the ROLL_AT
    roll). The literal pin requires the artifact's as_of in this set."""
    d = datetime.strptime(str(run_date), "%Y-%m-%d")
    return {as_of_cut(d.replace(hour=0, minute=0, tzinfo=ET)),
            as_of_cut(d.replace(hour=23, minute=59, tzinfo=ET))}


def main(argv=None, *, now=None, universe_fn=None, frames_fn=None, history_fn=None, listing_fn=None,
         block=True, git_fn=None, pin_prereg=True) -> int:
    """`pin_prereg=False` is for the test fixtures' small-draw outcome runs
    only (keyword-only, like `block`; the CLI never reaches it)."""
    a = parse_args(argv)
    now_et = (now or datetime.now(tz=ET)).astimezone(ET)
    if RS.refused_window(now_et) and not a.force_window:
        print(f"REFUSED: {now_et:%H:%M} ET is inside {RS.REFUSE_FROM[0]:02d}:{RS.REFUSE_FROM[1]:02d}–"
              f"{RS.REFUSE_TO[0]:02d}:{RS.REFUSE_TO[1]:02d} ET; pass --force-window to override.",
              file=sys.stderr)
        return 2
    smoke = a.limit is not None
    count_only = bool(a.count_only or smoke)
    if count_only and Path(a.out).resolve() == DEFAULT_OUT.resolve():
        print("REFUSED: a count-only / --limit run never writes the real artifact path.", file=sys.stderr)
        return 2
    git = dict((git_fn or git_state)())
    git["source"] = "measured"
    if git.get("head") is None:
        git["head"] = (a.git_head or "").strip() or None
        git["source"] = "attested"
    if git.get("porcelain_empty") is None and a.git_clean:
        git["porcelain_empty"] = True
        git["source"] = "attested"
    if not count_only:
        why = outcome_pin_refusal(a) if pin_prereg else None
        if why:
            print(f"REFUSED (pre-registration pin): {why}.", file=sys.stderr)
            return 2
        if not (a.prereg_commit or "").strip() or not (a.prereg_blob or "").strip():
            print("REFUSED: an outcome run needs --prereg-commit AND --prereg-blob (commit the prereg first).",
                  file=sys.stderr)
            return 2
        doc = prereg_file()
        if not doc.is_file():
            print(f"REFUSED: the prereg {doc} is not on disk — mount docs/research read-only at "
                  f"{doc.parent} (an outcome run re-hashes it).", file=sys.stderr)
            return 2
        if git_blob_sha(doc) != a.prereg_blob.strip():
            print("REFUSED: the prereg on disk is not the blob this run names — a changed prereg needs a new one.",
                  file=sys.stderr)
            return 2
        if not git.get("head") or git.get("porcelain_empty") is not True:
            print("REFUSED: an outcome run needs a committed, clean tree (git HEAD and an empty "
                  "git status --porcelain; in the container pass --git-head and --git-clean).", file=sys.stderr)
            return 2
    if block:
        block_writes()
        block_fetches()
    t0 = time.time()
    syms = [str(s).upper() for s in universe_fn()] if universe_fn is not None else default_universe()
    if smoke:
        syms = syms[:max(0, int(a.limit))]
    frames = (frames_fn or prices.bulk_cached_frames)(syms + [BENCH]) or {}
    if frames.get(BENCH) is None or len(frames[BENCH]) == 0:
        print(f"REFUSED: the price cache returned no {BENCH} frame.", file=sys.stderr)
        return 2
    as_of = a.as_of or default_as_of(sorted(_days(frames[BENCH])), now_et)
    if not as_of:
        print("REFUSED: no closed session to measure up to.", file=sys.stderr)
        return 2
    if not count_only and pin_prereg and as_of != as_of_cut(now_et):
        print(f"REFUSED (pre-registration pin): the {BENCH} cache ends {as_of}, before the tab's last closed "
              f"session {as_of_cut(now_et)} — refresh the cache first (the one outcome run is not spent).",
              file=sys.stderr)
        return 2
    docs = (history_fn or AH.read_many)(syms) or {}
    if listing_fn is None:
        from sepa import ipo_age
        listing_fn = ipo_age.listing_dates_map
    listing = listing_fn(syms) or {}
    read_sec = time.time() - t0
    body = run_study(frames, docs, listing, syms=syms, as_of=as_of, draws=a.draws, seed=a.seed,
                     count_only=count_only, read_sec=read_sec)
    root = Path(__file__).resolve()
    git_blk = {"head": git.get("head"), "porcelain_empty": git.get("porcelain_empty"),
               "script_blob": git_blob_sha(root), "detector_blob": git_blob_sha(DJ.__file__),
               "measured_blob": git_blob_sha(DSM.__file__),
               "prereg_blob": (a.prereg_blob or "").strip() or None,
               "source": git["source"]}
    vals = {"study": STUDY, "schema": DSM.SCHEMA_VERSION, "script": SCRIPT, "prereg": PREREG,
            "prereg_commit": (a.prereg_commit or "").strip() or None,
            "prereg_blob": (a.prereg_blob or "").strip() or None, "smoke": bool(smoke),
            "count_only": count_only, "run_date": now_et.date().isoformat(), "as_of": as_of,
            **body, "definitions": definitions(a.draws, a.seed), "limits": list(LIMITS),
            "runtime_sec": round(time.time() - t0, 1), "attempted_writes": sorted(set(ATTEMPTED)),
            "provider_calls": len(FETCH_CALLS), "git": {k: git_blk[k] for k in DSM.GIT_KEYS}}
    art = _clean({k: vals[k] for k in DSM.ARTIFACT_KEYS})
    bad = data_writes(ATTEMPTED)
    if bad or FETCH_CALLS:
        print(f"FAILED: the run attempted data writes {bad} / provider calls {sorted(set(FETCH_CALLS))} — "
              "no artifact written, nothing from it is quotable.", file=sys.stderr)
        return 3
    Path(a.out).write_text(json.dumps(art, indent=1, allow_nan=False, default=str) + "\n", encoding="utf-8")
    p = art["primary"]
    if count_only:
        print(f"primary (counts only): {p['n_events']} events · {p['n_dates']} sessions · {p['n_symbols']} names")
    else:
        print(f"primary (net of SPY, {PRIMARY_H} sessions from the next open): {p['verdict']} "
              f"{p['adj_median_diff_pp']}pp CI block {p['adj_ci_block']} name {p['adj_ci_symbol']} "
              f"(level {p['ci_pct']}%, Holm p {p['p_holm']}) · events {p['n_events']} on {p['n_dates']} sessions")
    for k in CELLS:
        c = art["cells"][k]
        tail = "" if count_only else (f" · {c.get('verdict') or c['role']} {c.get('adj_median_diff_pp')}pp "
                                      f"block {c.get('adj_ci_block')} name {c.get('adj_ci_symbol')} · "
                                      f"detected {c.get('n_detected')} unmatched {c.get('n_unmatched')} "
                                      f"short pool {c.get('placebo_short_pool')} blocks {c.get('n_blocks')}")
        print(f"{k}: {c['n_events']} events / {c['n_dates']} sessions / {c['n_symbols']} names{tail}")
    print(f"provider_calls {art['provider_calls']} · attempted_writes {art['attempted_writes']} · "
          f"{art['runtime_sec']}s · phases {art['phase_sec']} -> {a.out}")
    if not count_only:
        print("measured_literal (paste into chart_maps/doji_sweep_measured.py):")
        print(json.dumps(measured_literal(art), indent=4, ensure_ascii=False))
    return 0


def imported_modules(path: Optional[str] = None) -> set:
    """Top-level module names this file imports (the import-scope test reads it)."""
    src = Path(path or __file__).read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.update(f"{node.module}.{n.name}" for n in node.names)
    return mods


if __name__ == "__main__":
    raise SystemExit(main())
