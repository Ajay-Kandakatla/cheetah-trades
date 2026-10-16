"""🕯️ Doji Sweep tab on Chart Maps (Ajay 2026-10-16).

The ask, verbatim: "create me a new tab for Doji candle after a sweep. For any
stocks after a down trend. May be from all chart maps especially on the 60% 70%
down stocks"

His knob answers (DECISIONS6, 2026-10-16), one line each:
  K1 "I heard but do some research and back test please on accuracy" — no named
     source; the definitions are researched and the read is backtested by us.
  K2 daily candles — one closed daily candle.
  K3 "All of them" + "Yes, any read; chips narrow" — any of three downtrend
     reads; the chips narrow; every row names the reads it meets.
  K4 "Within 5% either side counts as a test" — the low within ±5% of the
     reference low; undercut-and-reclaimed is a chip, never a gate.
  K5 "Research" — the doji body from the research; default the house 5%.

THE ONE ENGINE. `frame_features()` (every per-bar column, each reading bars
<= t only) + `row_statuses()` (the one classifier). `read()` takes the LAST
closed row for the tab; `scripts/doji_sweep_study.py` takes every row — the
same detector, sliceable point-in-time (a test proves an event at t never
changes when bars after t change). A candle FIRES when:
  * it is a doji — the body under `DOJI_BODY_PCT` of the range, the house
    STRICT `<` of `scalping/candles.anatomy` (the memo keeps the
    `DOJI_BODY_WIDE_PCT` switch);
  * its low sits within `SWEEP_TEST_PCT` either side of the lowest low of the
    `SWEEP_REF_SESSIONS` sessions before it (Connors & Raschke's Turtle Soup
    reference), that low at least `SWEEP_REF_MIN_AGE` sessions old;
  * ANY downtrend read is met: `DOWN_PCT`%+ under the 52-week high (the 📉
    tab's `fallen_tab.closed_read`), `DOWN_PCT`%+ under the all-time high (the
    🏔️ tab's `ath_tab.closed_read`), or the close below both the `SMA_FAST`- and
    `SMA_SLOW`-day simple averages.

CLOSED BARS ONLY. `KL.closed_frame` drops every bar dated the session (the
cache patches today's in-progress bar hourly); the session rolls at
`KL.ROLL_AT`, so a session's candle joins the tab after 20:00 ET.

READS MONGO ONLY (bulk_cached_frames, ath_history, ipo_dates) — never a
provider call; the whole read is built in a background memo thread (the 📉
tab's shape) and a request only filters and orders the held rows.

WRITES NOTHING. `ledger_fires()` hands the fired candles to the 17:20
`patterns.history` run, which records them in its own bucket.

UNMEASURED until doji_sweep_measured.MEASURED carries the study. Display only —
nothing here gates a scan, pushes a phone, sizes a position or enters a lane.

HIS CALL (2026-10-16; the other open calls are tagged on their constants —
Q1 / Q2 / Q5 / Q7 / Q9 / Q12 / Q18):
  Q23 `bad_bars` reads wider than AMENDMENTS6 B13's words. B13 says "a flat
      candle today" — only the day's own candle. The code ALSO counts a name
      as `bad_bars` when any low among the `SWEEP_REF_SESSIONS` bars before the
      candle is missing (the reference low cannot be read without all of them;
      tests/test_doji_sweep_tab.py::test_29). The count line says so ("a flat
      candle today (or an unreadable bar in the N sessions before it)").
      DEFAULT (MINE): keep the wider read; vs only the day's candle, with a hole
      in the reference window counted in a class of its own.
"""
from __future__ import annotations

import inspect
import logging
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd

from chart_maps import ath_history as AH
from chart_maps import ath_tab as ATH
from chart_maps import dual_momentum_tab as DMT
from chart_maps import fallen_tab as FAL
from patterns import candles_daily as CD
from scalping import candles as CANDLES
from sepa import prices
from supply_demand import key_levels as KL
from supply_demand import patterns as SDP

log = logging.getLogger("chart_maps.doji_sweep_tab")

# ---------------------------------------------------------------------------
# constants (BUILD_SPEC6 §3.1 — every number tagged with its source)
# ---------------------------------------------------------------------------
MARK = "\U0001F56F️"                      # 🕯️ (VS16 — the FE literal must match byte for byte)
TAB_KEY = "doji_sweep"
TAB_LABEL = f"{MARK} Doji Sweep"             # HIS CALL Q1 — == TAB_META.doji_sweep.label (contract)
BOARD_KEY = "doji_sweep_board"               # the served block == membership.MEMO_BLOCK_KEY[TAB_KEY]
W52_MARK = FAL.MARK                          # imported — 📉
ATH_MARK = ATH.MARK                          # imported — 🏔️ (VS16)
DOJI_BODY_PCT = CANDLES.DOJI_BODY_PCT        # imported (0.05) — Cheetah default (scalping/candles.py:27, TradeStation's 5% of the range; HIS CALL Q2)
DOJI_BODY_WIDE_PCT = 0.10                    # Cheetah default (PivotBoss Doji Reversal / Liberated Stock Trader: body within 10% of the range) — the ≤10% switch and the study's second read
BODY_STEPS = (int(round(DOJI_BODY_PCT * 100)), int(round(DOJI_BODY_WIDE_PCT * 100)))   # derived (5, 10) — the served switch; [0] = default
SMALL_WICK_PCT = CD.SMALL_WICK_PCT           # imported (0.15) — the house "little or no shadow" (dragonfly / gravestone)
LONG_LEG_BARS = 10                           # Cheetah default (TA-Lib's 10-bar candle-average period) — long-legged = a range at least the prior 10 sessions' mean range (Bulkowski: "shadows longer than those of recent candles")
SWEEP_REF_SESSIONS = 20                      # Cheetah default (Connors & Raschke, Street Smarts 1995 — Turtle Soup: the prior 20-day low)
SWEEP_REF_MIN_AGE = 4                        # Cheetah default (Connors & Raschke 1995 — that 20-day low made at least four sessions earlier)
SWEEP_TEST_PCT = 5.0                         # Ajay 2026-10-16: "Within 5% either side counts as a test"
TEST_ROUND_DP = 2                            # MINE (AMENDMENTS6 B9) — the test and both depth reads compare the % rounded to 2 dp, the served number (7.3 x 1.05 reads 5.000000000000003)
DOWN_PCT = 60.0                              # Ajay 2026-10-16 ("especially on the 60% 70% down stocks"; K3 / Q5) — reads (a) and (b) qualify at >=
DEPTH_CHIPS = (FAL.DEPTH_STEPS[0], FAL.DEPTH_STEPS[2], FAL.DEPTH_STEPS[3])   # Ajay 2026-10-16 K3 — the 40 / 60 / 70 chips, picked from the 📉 tab's own steps
SMA_FAST = 50                                # Ajay 2026-10-16 K3 (c) — "below BOTH the 50- and 200-day SMAs"
SMA_SLOW = 200                               # Ajay 2026-10-16 K3 (c)
YEAR_BARS = KL.YEAR_BARS                     # imported (252) — the 52-week read and the minimum history
VOL_AVG_BARS = CD.VOL_AVG_BARS               # imported (50) — the house last-bar volume average
VOL_HEAVY_X = CANDLES.VOL_RATIO_MIN          # imported (1.5) — borrowed from the 5-minute candle module (scalping/candles.py:30), not a daily house line (Cheetah default, his call Q9); Fraser's #2 spring "expanded volume"
VOL_QUIET_X = 1.0                            # MINE (HIS CALL Q9) — at or under the average = "quiet" (Fraser's #3 spring "modest volume")
ATR_BARS = int(inspect.signature(SDP.atr).parameters["period"].default)   # derived (14) — the house ATR period, off supply_demand/patterns.atr's signature
SESSIONS_ON_TAB = 1                          # MINE (HIS CALL Q7) — the latest closed candle only (DECISIONS6 default)
LEDGER_BACKFILL_SESSIONS = 3                 # TRANSPORT — MINE: the 17:20 ledger run records the last 3 closed candles (idempotent) so a late or missed run loses no session
INCLUDE_ETFS = FAL.INCLUDE_ETFS              # imported (False) — "stocks"
GLITCH_RATIO = FAL.GLITCH_RATIO              # imported (5.0)
MEMO_TTL_SEC = FAL.MEMO_TTL_SEC              # imported — cache freshness, NOT a rule
FAIL_RETRY_SEC = FAL.FAIL_RETRY_SEC          # imported — retry cadence, NOT a rule
FILTER_PARAM = "dj"
BODY_PARAM = "dj_body"
FILTER_KEYS = ("w52_40", "w52_60", "w52_70", "ath_60", "mas", "reclaimed")   # canonical order; FE DJ_FILTER_KEYS pinned equal
DEFAULT_SORT = "default"                     # == board.DEFAULT_SORT (test-pinned; no board import here)
SORT_TEST = "doji_test"
SORT_ATH = "doji_ath"
TAB_SORTS = (SORT_TEST, SORT_ATH)
READS = ("w52", "ath", "mas")
VARIANTS = ("dragonfly", "gravestone", "long_legged", "plain")
ROW_STATUSES = ("bad_bars", "not_doji", "ref_too_fresh", "no_test", "no_downtrend", "fired")
STATUSES = ("no_bars", "stale", "short_history") + ROW_STATUSES[:-1] + ("delisted", "etf", "data_suspect", "fired")   # derived
COUNT_KEYS = STATUSES + ("scanned", "fired_earlier", "at_body", "wider_body", "hidden_by_chips", "undercut",
                         "dropped_thin", "no_turnover", "shown")
LEDGER_KEYS = ("symbol", "date", "close", "doji5", "body_pct", "variant", "test_pct", "undercut", "reclaimed", "ref_low",
               "ref_date", "reads", "pct_below_52w", "pct_below_ath", "below_mas", "vol_ratio", "adv50", "bucket")
# AMENDMENTS6 B7 — the ledger's headline is the tab's default view (the house
# 5% body, at or above the tab's default liquidity floor); the 10%-body fires
# and the below-floor fires are their own sub-blocks, never pooled into it.
LEDGER_BUCKETS = (TAB_KEY, f"{TAB_KEY}_{BODY_STEPS[1]}pct", f"{TAB_KEY}_thin")   # derived
# AMENDMENTS6 B4 / B5 — the study's three pre-registered verdict cells
# (doji_sweep_measured.VERDICT_CELLS) as the engine defines them.
PRIMARY_READ = READS[0]                      # derived (AMENDMENTS6 B4) — the headline is his "60% 70%": the 52-week read
MEASURED_DEFAULT = {"state": "unmeasured"}
PREREG_PATH = "docs/research/doji_sweep_study_2026_10_16.md"
SCRIPT_PATH = "backend/scripts/doji_sweep_study.py"
DRAGONFLY_CLAIM = "reverses 50% of the time, overall rank 98 of 103 (thepatternsite.com/Dragonfly.html)"   # Cheetah default (source: Bulkowski, their claim — RESEARCH §2.2)

FEATURE_COLUMNS = ("open", "high", "low", "close", "volume", "rng", "valid", "body_pct", "upper_wick_pct",
                   "lower_wick_pct", "doji5", "doji10", "variant", "range_mean_prior", "ref_low", "ref_idx", "ref_age",
                   "ref_ok", "test_pct", "tested", "undercut", "reclaimed", "sma50", "sma200", "below_mas", "w52_high",
                   "pct_below_52w", "vol_ratio", "vol_word", "atr_prior", "range_atr", "adv50", "glitch", "suspect")

_MINUS = "−"

_memo: dict = {}                # (session_iso, ukey) -> entry
_warming: set = set()
_failures: dict = {}            # key -> (ts, reason)
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# served words — constants (BUILD_SPEC6 §3.5)
# ---------------------------------------------------------------------------
DEFAULT_SORT_LABEL = f"{MARK} Newest candle, deepest first"                          # W2
TEST_SORT_LABEL = "\U0001F4CF Closest to the prior low first"                        # W3 📏
ATH_SORT_LABEL = f"{ATH_MARK} Deepest under the all-time high first"                 # W4
WARMING_NOTE = (f"{MARK} Reading every name's last closed daily candle from the cached bars — the "
                "charts appear here as soon as it lands; you don't need to refresh.")            # W9
ERROR_NOTE_FMT = (f"{MARK} The Doji Sweep list could not be built ({{reason}}). It is retried every "
                  "{mins} minutes — this is not a warming state.")                               # W10
EMPTY_NOTE = (f"{MARK} No name's last closed candle is a doji testing its prior {SWEEP_REF_SESSIONS}-session "
              "low in a downtrend — the line above says what was not listed.")                   # W11
NOTE = (f"{MARK} Display only — the list describes the last closed candle, not what comes next. Nothing "
        "here gates a scan, pushes a phone, sizes a position or enters a lane. Not advice.")     # W12
FILTER_LABELS = {                                                                    # derived — W14
    "w52_40": f"{W52_MARK} ≥{DEPTH_CHIPS[0]}% off the 52-week high",
    "w52_60": f"{W52_MARK} ≥{DEPTH_CHIPS[1]}% off the 52-week high",
    "w52_70": f"{W52_MARK} ≥{DEPTH_CHIPS[2]}% off the 52-week high",
    "ath_60": f"{ATH_MARK} ≥{DOWN_PCT:g}% off the all-time high",
    "mas": f"Below the {SMA_FAST}- and {SMA_SLOW}-day",
    "reclaimed": "Undercut and reclaimed",
}


def _w52_note(d) -> str:
    return (f"Closed {d}% or more under the 52-week high — the highest intraday high of the last "
            f"{YEAR_BARS} closed sessions, the {FAL.TAB_LABEL} tab's own read. UNMEASURED.")


FILTER_NOTES = {                                                                     # derived — W15
    "w52_40": _w52_note(DEPTH_CHIPS[0]),
    "w52_60": _w52_note(DEPTH_CHIPS[1]),
    "w52_70": _w52_note(DEPTH_CHIPS[2]),
    "ath_60": (f"Closed {DOWN_PCT:g}% or more under the all-time high — the {ATH_MARK} ATH tab's own read "
               "(monthly history to the listing plus the cached daily bars); a name whose history does "
               "not reach its listing is read against its high since its first bar, so the true distance "
               "is at least this. UNMEASURED."),
    "mas": f"Closed below both its {SMA_FAST}-day and {SMA_SLOW}-day simple averages. UNMEASURED.",
    "reclaimed": (f"The low went under the prior {SWEEP_REF_SESSIONS}-session low and the close came back "
                  "above it. UNMEASURED."),
}
FILTERS_NOTE = ("Ticked chips narrow the list — every ticked chip must pass. They gate nothing, push "
                "nothing and enter no lane.")                                        # W16
BODY_LABELS = {BODY_STEPS[0]: f"{MARK} Body under {BODY_STEPS[0]}%",                 # derived — W18
               BODY_STEPS[1]: f"{MARK} Body under {BODY_STEPS[1]}%"}
BODY_TITLES = {BODY_STEPS[0]: (f"The app's own doji (scalping/candles.py) — the body under "        # derived — W19
                               f"{BODY_STEPS[0]}% of the day's range"),
               BODY_STEPS[1]: (f"A looser doji — the body under {BODY_STEPS[1]}% of the range "
                               "(PivotBoss, Liberated Stock Trader); the study reads both")}
READS_LEGEND = (                                                                     # W20
    f"{W52_MARK} 52-week: {DOWN_PCT:g}% or more under the highest intraday high of the last {YEAR_BARS} "
    "closed sessions.",
    f"{ATH_MARK} All-time: {DOWN_PCT:g}% or more under the all-time high (monthly history to the listing "
    "plus the cached daily bars; “high since” when the history is short — the distance is then at least "
    "this).",
    f"Averages: the close under both the {SMA_FAST}- and {SMA_SLOW}-day simple averages.",
)
VARIANT_WORDS = {"dragonfly": "Dragonfly doji", "gravestone": "Gravestone doji",     # W22
                 "long_legged": "Long-legged doji", "plain": "Doji"}
REF_LINE_LABEL = f"prior {SWEEP_REF_SESSIONS}-session low"                           # W28
READS_HEAD = "Reads met: "                                                           # AMENDMENTS6 B16 — never "Downtrend" alone
NOTE_PENDING = (f"{MARK} UNMEASURED — no study in this app has measured what a doji testing its prior "  # W29
                f"{SWEEP_REF_SESSIONS}-session low in a downtrend does next; the pre-registered backtest "
                f"({PREREG_PATH}, {SCRIPT_PATH}) is the one that may. Their claims: "
                f"{CD.BULKOWSKI_CANDLE['doji']}. {CD.CAVEAT}")
# AMENDMENTS6 B5 — the control cell's own words, beside the primary. The cell
# (doji_sweep_measured "test_no_doji") is tests WITHOUT a doji against their OWN
# matched days, so its words say only that; they never claim the doji adds or
# does not add — the reader compares this line with the primary's (fix round 1).
CONTRAST_WORDS = {"separates": "on this record the tests without a doji returned more than their matched days",
                  "inverted": "on this record the tests without a doji returned less than their matched days",
                  "no_signal": ("the tests without a doji show no difference from their matched days that this "
                                "study can separate from zero"),
                  "too_small": "too few tests without a doji to read",
                  "axes_disagree": ("no verdict for the tests without a doji — the session-block CI and the "
                                    "by-name CI disagree")}
# The 70% cell's words (B4; fix round 1, 2026-10-16): "too few to read" only while
# THIS run's counts are under the house minimums (DSM.MIN_CELL_EVENTS /
# DSM.MIN_CELL_DATES); a run that clears them still serves no verdict — the cell
# was pre-declared too small before the run.
DEEP_TOO_FEW_WORDS = "too few to read (pre-declared)"
# The words once the counts clear them; _deep_words appends DSM.EXPLORATORY_LABEL
# at serve time (DSM is imported lazily in this module, never at module level).
DEEP_PREDECLARED_PREFIX = "pre-declared too small before the run"
NOT_READ = "—"                               # a number the literal carries as None (a too-small cell) is served as a dash, never "None"
HOLM_LINE = "Verdicts are Holm-corrected across these three pre-registered reads (Holm p {p1} / {p2} / {p3})"
NO_HOLM_LINE = "No correction across these three pre-registered reads is recorded in this run"


def _verdict_words() -> dict:
    """W31 — lazy: the counts come from doji_sweep_measured."""
    from chart_maps import doji_sweep_measured as DSM
    return {"separates": "on this record they returned more than the matched days",
            "no_signal": "no difference this study can separate from zero",
            "inverted": "on this record they returned less than the matched days",
            "too_small": (f"too few to read — under {DSM.MIN_CELL_EVENTS} events or "
                          f"{DSM.MIN_CELL_DATES} sessions"),
            "axes_disagree": ("no verdict — the session-block CI and the by-name CI disagree "
                              "(AMENDMENTS6: a verdict needs both)")}


def _deep_words(deep: dict) -> str:
    """The 70% cell's clause words: DEEP_TOO_FEW_WORDS while its counts are under
    DSM.MIN_CELL_EVENTS or DSM.MIN_CELL_DATES, else DEEP_PREDECLARED_PREFIX +
    DSM.EXPLORATORY_LABEL. Never a verdict word. Counts read as _n reads them
    (None → 0)."""
    from chart_maps import doji_sweep_measured as DSM
    if (int(deep["n_events"] or 0) < DSM.MIN_CELL_EVENTS
            or int(deep["n_dates"] or 0) < DSM.MIN_CELL_DATES):
        return DEEP_TOO_FEW_WORDS
    return f"{DEEP_PREDECLARED_PREFIX} — {DSM.EXPLORATORY_LABEL}"


def _measured_fmt() -> str:
    """W30 (AMENDMENTS6 B2 / B4 / B5 / B6). The primary is his "60% 70%":
    `DOWN_PCT`%+ under the 52-week high; every primary median is net of SPY over
    the same sessions (the raw read beside it); the any-read line and the
    no-doji control sit beside it; verdicts need BOTH CIs to agree. The
    `DEPTH_CHIPS[2]`%+ cell (doji_sweep_measured.PREDECLARED_TOO_SMALL) is served
    with its counts and _deep_words (too few / pre-declared) — never a verdict
    word (B4; the WP-A critic, 2026-10-16). The CI level
    is the one the verdict used (`ci_pct`); the Holm words only when the literal
    records a Holm p for all three verdict cells (fix round 1)."""
    return (f"{MARK} MEASURED {{run_date}} (prereg {{prereg}}, survivors-only, candles {{first}} to "
            f"{{last}}): {{n_events}} dojis testing the prior low {DOWN_PCT:g}%+ under the 52-week high, "
            "on {n_dates} sessions across {n_symbols} names. Bought at the next open and held {h} "
            "sessions, net of SPY over the same sessions: median {em}% against {pm}% on {n_placebo} "
            "matched days of the same names in the same downtrend ({n_short} with a short placebo pool, "
            "{n_unmatched} with none) — {pp} pp (before SPY {raw_pp} pp), {ci_lvl} CI by {block}-session "
            "block [{lo}, {hi}], by name [{slo}, {shi}]: {words}. Any downtrend read: {any_n} dojis, "
            "{any_pp} pp, {any_ci_lvl} CI [{any_lo}, {any_hi}] / [{any_slo}, {any_shi}]: {any_words}. The "
            "control — a test of the low without a doji, against its own matched days: {nd_n} tests, "
            "{nd_pp} pp, {nd_ci_lvl} CI [{nd_lo}, {nd_hi}] / [{nd_slo}, {nd_shi}]: {nd_words}. "
            f"Under the 52-week high by {DEPTH_CHIPS[2]}%+: "
            "{deep_n} dojis on {deep_d} sessions — {deep_words}. {holm}; "
            "every other cell is exploratory — no verdict. Closed above the doji's high within {c} "
            "sessions before closing under its low {cp}% vs {pcp}% (difference CI by block [{clo}, "
            "{chi}] pp); closed under its low within {h} sessions {sp}% vs {psp}%. Mean {mean}% (before "
            "SPY) against {pmean}% on the matched days (difference CI by block [{mlo}, {mhi}] pp), "
            "before costs; {net}% after a {cost}% round trip. Not advice.")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _f(v) -> Optional[float]:
    return KL._f(v)


def _m(s: str) -> str:
    return s.replace("-", _MINUS)


def _n(x) -> str:
    return f"{int(x or 0):,}"


def _r(v, dp: int) -> Optional[float]:
    x = _f(v)
    return None if x is None else round(x, dp)


def _ge(v, x) -> Optional[bool]:
    v = _f(v)
    return None if v is None else bool(v >= x)


def _signed(x) -> str:
    return _m(f"{float(x):+.2f}")


def _sn(x) -> str:
    """_signed, or NOT_READ for a None / NaN the literal carries."""
    return NOT_READ if _f(x) is None else _signed(x)


def _rate(x) -> str:
    return NOT_READ if _f(x) is None else f"{float(x):.0f}"


def _lvl(x) -> str:
    return f"{float(x):g}%" if _f(x) is not None else NOT_READ


# ---------------------------------------------------------------------------
# THE ONE ENGINE (PURE)
# ---------------------------------------------------------------------------
def frame_features(closed: pd.DataFrame) -> pd.DataFrame:
    """One row per CLOSED bar t of `closed` (same index); every column reads bars
    <= t only. PURE, no I/O. read() takes its LAST row;
    scripts/doji_sweep_study.py takes every row — the one engine (DECISIONS6:
    "the SAME detector"). Columns = FEATURE_COLUMNS, formulas = BUILD_SPEC6 §3.2.

    Ajay 2026-10-16: "create me a new tab for Doji candle after a sweep. For any
    stocks after a down trend. May be from all chart maps especially on the 60%
    70% down stocks"."""
    o = closed["open"].to_numpy(dtype=float)
    h = closed["high"].to_numpy(dtype=float)
    lo = closed["low"].to_numpy(dtype=float)
    c = closed["close"].to_numpy(dtype=float)
    v = closed["volume"].to_numpy(dtype=float)
    n = len(c)
    with np.errstate(divide="ignore", invalid="ignore"):
        rng = h - lo
        valid = np.isfinite(o) & np.isfinite(h) & np.isfinite(lo) & np.isfinite(c) & (rng > 0)
        safe = np.where(valid, rng, np.nan)
        body_pct = np.where(valid, np.abs(c - o) / safe, np.nan)
        upper = np.where(valid, (h - np.maximum(o, c)) / safe, np.nan)
        lower = np.where(valid, (np.minimum(o, c) - lo) / safe, np.nan)
        doji5 = valid & (np.nan_to_num(body_pct, nan=np.inf) < DOJI_BODY_PCT)
        doji10 = valid & (np.nan_to_num(body_pct, nan=np.inf) < DOJI_BODY_WIDE_PCT)
        range_mean_prior = pd.Series(rng).shift(1).rolling(LONG_LEG_BARS).mean().to_numpy()

        variant = np.full(n, None, dtype=object)
        for i in np.flatnonzero(valid):
            if upper[i] <= SMALL_WICK_PCT:
                variant[i] = "dragonfly"
            elif lower[i] <= SMALL_WICK_PCT:
                variant[i] = "gravestone"
            elif np.isfinite(range_mean_prior[i]) and rng[i] >= range_mean_prior[i]:
                variant[i] = "long_legged"
            else:
                variant[i] = "plain"

        N = SWEEP_REF_SESSIONS
        ref_low = np.full(n, np.nan)
        ref_idx = np.full(n, -1, dtype=int)
        if n > N:
            win = np.lib.stride_tricks.sliding_window_view(lo, N)[: n - N]   # row j = bars j..j+N-1 = the window of t = j+N
            ts = np.arange(N, n)
            ok = np.isfinite(win).all(axis=1)
            mins = np.where(ok, win.min(axis=1), np.nan)
            last = ts - 1 - np.argmin(win[:, ::-1], axis=1)                    # the MOST RECENT bar printing the minimum (Q18)
            ok = ok & (mins > 0)
            ref_low[ts] = np.where(ok, mins, np.nan)
            ref_idx[ts] = np.where(ok, last, -1)
        ref_age = np.where(ref_idx >= 0, np.arange(n) - ref_idx, 0)
        ref_ok = ref_age >= SWEEP_REF_MIN_AGE
        test_pct = (lo - ref_low) / ref_low * 100.0
        tp = np.nan_to_num(np.round(np.abs(test_pct), TEST_ROUND_DP), nan=np.inf)
        tested = tp <= SWEEP_TEST_PCT
        undercut = np.nan_to_num(lo < ref_low, nan=False) & np.isfinite(ref_low) & np.isfinite(lo)
        reclaimed = undercut & np.isfinite(c) & (c > np.nan_to_num(ref_low, nan=np.inf))

        cs = pd.Series(c)
        sma50 = cs.rolling(SMA_FAST).mean().to_numpy()
        sma200 = cs.rolling(SMA_SLOW).mean().to_numpy()
        below_mas = (np.nan_to_num(c < sma50, nan=False) & np.nan_to_num(c < sma200, nan=False)
                     & np.isfinite(sma50) & np.isfinite(sma200) & np.isfinite(c))
        # one missing high inside the window never drops the 52-week read: the max over
        # the finite highs of the window (nanmax), served only once a full window of
        # bars exists (fix round 1)
        w52_high = pd.Series(h).rolling(YEAR_BARS, min_periods=1).max().to_numpy()
        w52_high[np.arange(n) < YEAR_BARS - 1] = np.nan
        pct_below_52w = np.where(w52_high > 0, (1.0 - c / w52_high) * 100.0, np.nan)

        avg_v = pd.Series(v).shift(1).rolling(VOL_AVG_BARS).mean().to_numpy()
        vol_ratio = np.where(avg_v > 0, v / np.where(avg_v > 0, avg_v, np.nan), np.nan)
        vol_ratio = np.where(np.isfinite(vol_ratio), vol_ratio, np.nan)
        vol_word = np.full(n, None, dtype=object)
        vol_word[np.nan_to_num(vol_ratio, nan=np.inf) <= VOL_QUIET_X] = "quiet"
        vol_word[np.nan_to_num(vol_ratio, nan=-np.inf) >= VOL_HEAVY_X] = "heavy"

        hs, ls = pd.Series(h), pd.Series(lo)
        prev = cs.shift(1)
        tr = pd.concat([hs - ls, (hs - prev).abs(), (ls - prev).abs()], axis=1).max(axis=1)
        atr_prior = tr.rolling(ATR_BARS).mean().shift(1).to_numpy()
        range_atr = np.where(atr_prior > 0, rng / np.where(atr_prior > 0, atr_prior, np.nan), np.nan)
        adv50 = pd.Series(c * v).rolling(VOL_AVG_BARS).mean().to_numpy()

        c_prev = prev.to_numpy()
        ratio = c / c_prev
        glitch = ((np.nan_to_num(c, nan=0.0) > 0) & (np.nan_to_num(c_prev, nan=0.0) > 0)
                  & ((np.nan_to_num(ratio, nan=1.0) >= GLITCH_RATIO)
                     | (np.nan_to_num(ratio, nan=1.0) <= 1.0 / GLITCH_RATIO)))
        suspect = (pd.Series(glitch.astype(float)).rolling(YEAR_BARS - 1, min_periods=1).max()
                   .to_numpy() > 0)

    cols = {"open": o, "high": h, "low": lo, "close": c, "volume": v, "rng": rng, "valid": valid,
            "body_pct": body_pct, "upper_wick_pct": upper, "lower_wick_pct": lower, "doji5": doji5,
            "doji10": doji10, "variant": variant, "range_mean_prior": range_mean_prior,
            "ref_low": ref_low, "ref_idx": ref_idx, "ref_age": ref_age, "ref_ok": ref_ok,
            "test_pct": test_pct, "tested": tested, "undercut": undercut, "reclaimed": reclaimed,
            "sma50": sma50, "sma200": sma200, "below_mas": below_mas, "w52_high": w52_high,
            "pct_below_52w": pct_below_52w, "vol_ratio": vol_ratio, "vol_word": vol_word,
            "atr_prior": atr_prior, "range_atr": range_atr, "adv50": adv50, "glitch": glitch,
            "suspect": suspect}
    return pd.DataFrame({k: cols[k] for k in FEATURE_COLUMNS}, index=closed.index)


def _as_float(x, n: int) -> np.ndarray:
    if x is None:
        return np.full(n, np.nan)
    a = np.asarray(x, dtype=float)
    return a if a.shape == (n,) else np.full(n, np.nan)


def reads_vector(pct_below_52w, pct_below_ath, below_mas) -> dict:
    """{"w52": round(pct52, TEST_ROUND_DP) >= DOWN_PCT, "ath":
    round(pctath, TEST_ROUND_DP) >= DOWN_PCT, "mas": below_mas.astype(bool)} as
    bool arrays; NaN / None never meets a read; pct_below_ath None = all-NaN.
    PURE."""
    p52 = np.asarray(pct_below_52w, dtype=float)
    n = len(p52)
    pa = _as_float(pct_below_ath, n)
    mas = np.asarray(below_mas, dtype=bool) if below_mas is not None else np.zeros(n, dtype=bool)
    # AMENDMENTS6 B9 extended to the depth reads (2026-10-16, the WP-A critic):
    # each depth compares the % rounded to TEST_ROUND_DP — the number the card,
    # the chip (the 📉 tab's 2-dp pct_below) and the study cells show — so a
    # raw 59.996 (served 60.00) meets the 60% read and 59.994 (served 59.99)
    # does not; the read, the chip and the primary cell agree at the line.
    # Fix round 1 (2026-10-16): Python's round() element by element — the SAME
    # rule as _r, the ATH pct_below and the 📉 tab's served pct. np.round scales
    # by 10**dp first, so an exact-half 59.995 read 60.00 there while the card
    # and the chip showed 59.99.
    return {"w52": _round_vec(p52, TEST_ROUND_DP) >= DOWN_PCT,
            "ath": _round_vec(pa, TEST_ROUND_DP) >= DOWN_PCT,
            "mas": mas.astype(bool)}


def _round_vec(arr, dp: int) -> np.ndarray:
    """Python round(x, dp) per element (the served numbers' rule); NaN → -inf so
    it never meets a read. PURE."""
    a = np.asarray(arr, dtype=float)
    return np.array([round(float(x), dp) if np.isfinite(x) else -np.inf for x in a.ravel()],
                    dtype=float).reshape(a.shape)


def row_statuses(feat: pd.DataFrame, *, body_max: float, pct_below_ath=None) -> np.ndarray:
    """Per bar, the FIRST match of ROW_STATUSES: bad_bars (the bar itself not
    valid, or its reference low unreadable) → not_doji (body_pct >= body_max, the
    house STRICT `<` for a doji) → ref_too_fresh (not ref_ok) → no_test (not
    tested) → no_downtrend (no read of reads_vector met) → fired. dtype object.
    THE ONE CLASSIFIER: read() takes [-1]; the study takes every element. PURE."""
    valid = feat["valid"].to_numpy(dtype=bool)
    ref_low = feat["ref_low"].to_numpy(dtype=float)
    body = feat["body_pct"].to_numpy(dtype=float)
    rd = reads_vector(feat["pct_below_52w"].to_numpy(dtype=float), pct_below_ath,
                      feat["below_mas"].to_numpy(dtype=bool))
    any_read = rd["w52"] | rd["ath"] | rd["mas"]
    conds = [~valid | ~np.isfinite(ref_low),
             ~(np.nan_to_num(body, nan=np.inf) < body_max),
             ~feat["ref_ok"].to_numpy(dtype=bool),
             ~feat["tested"].to_numpy(dtype=bool),
             ~any_read]
    return np.select(conds, list(ROW_STATUSES[:-1]), default=ROW_STATUSES[-1]).astype(object)


def ath_series(closed: pd.DataFrame, doc: Optional[dict]) -> tuple:
    """(hi_t, basis_t) point-in-time — PURE. run_t = the running max of the
    frame's highs (NaN-safe). With a USABLE doc (the caller passes one only when
    ath_tab.closed_read reports doc_state "ok" and the doc has no cut_from)
    holding a finite hi and an hi_month "YYYY-MM": a bar whose month is AFTER
    hi_month gets hi_t = max(run_t, hi) and basis "history" (exact: hi is the
    all-time max and it was set before t); every other bar gets hi_t = run_t and
    basis "frame" (exact when the pre-t high sits inside the 2-year frame, a
    LOWER bound otherwise — so a 60%+ read off it is at least 60% off the true
    high). MINE (HIS CALL Q12)."""
    highs = closed["high"].to_numpy(dtype=float)
    n = len(highs)
    run = np.fmax.accumulate(highs) if n else highs
    hi_t = run.astype(float).copy()
    basis = np.full(n, "frame", dtype=object)
    d = doc if isinstance(doc, dict) else {}
    hi = _f(d.get("hi"))
    hm = str(d.get("hi_month") or "")
    if hi is not None and len(hm) == 7 and hm[4] == "-":
        months = np.asarray([x.strftime("%Y-%m") for x in KL._norm_index(closed)], dtype=object)
        after = months > hm
        hi_t = np.where(after, np.fmax(run, hi), run)
        basis[after] = "history"
    return hi_t, basis


def study_cells(feat: pd.DataFrame, *, pct_below_ath, floor) -> dict:
    """The three pre-registered verdict cells (doji_sweep_measured.VERDICT_CELLS,
    AMENDMENTS6 B4 / B5 / B6) as bool arrays over `feat`'s bars — the engine's
    own definitions, so the study never restates a rule. PURE.
      eligible     = bar index >= YEAR_BARS - 1, a valid bar, no scale glitch in
                     its YEAR_BARS-session window (the 📉 held-out rule);
      primary      = eligible & floor & fired at DOJI_BODY_PCT & the 52-week read
                     (his "60% 70%");
      any_read     = eligible & floor & fired at DOJI_BODY_PCT (the tab's view);
      test_no_doji = eligible & floor & body >= DOJI_BODY_WIDE_PCT (no doji at
                     either body) & the same test (ref_ok & tested) & the same
                     52-week read as the primary — the doji's control (B5)."""
    n = len(feat)
    fl = np.asarray(floor, dtype=bool) if floor is not None else np.zeros(n, dtype=bool)
    valid = feat["valid"].to_numpy(dtype=bool)
    eligible = (np.arange(n) >= YEAR_BARS - 1) & valid & ~feat["suspect"].to_numpy(dtype=bool)
    st5 = row_statuses(feat, body_max=DOJI_BODY_PCT, pct_below_ath=pct_below_ath)
    rd = reads_vector(feat["pct_below_52w"].to_numpy(dtype=float), pct_below_ath,
                      feat["below_mas"].to_numpy(dtype=bool))
    body = np.nan_to_num(feat["body_pct"].to_numpy(dtype=float), nan=-np.inf)
    base = eligible & fl
    fired = st5 == ROW_STATUSES[-1]
    return {"primary": base & fired & rd[PRIMARY_READ],
            "any_read": base & fired,
            "test_no_doji": (base & np.isfinite(feat["ref_low"].to_numpy(dtype=float))
                             & (body >= DOJI_BODY_WIDE_PCT) & feat["ref_ok"].to_numpy(dtype=bool)
                             & feat["tested"].to_numpy(dtype=bool) & rd[PRIMARY_READ])}


@dataclass(frozen=True)
class Cfg:
    body_pct: float = DOJI_BODY_PCT


def _iso(idx, i) -> Optional[str]:
    try:
        return idx[int(i)].date().isoformat() if int(i) >= 0 else None
    except (IndexError, TypeError, ValueError):
        return None


def read(sym: str, df, *, session: date, ath_doc: Optional[dict] = None, listed: Optional[str] = None,
         cfg: Cfg = Cfg(), etf_set=(), now_ts: Optional[float] = None) -> dict:
    """The tab's per-name read of the last CLOSED daily candle before `session`
    (BUILD_SPEC6 §3.2 steps 1-8). PURE except the two reads it delegates to the
    📉 / 🏔️ engines, both pure on their inputs. Every NaN is served None.

    Ajay 2026-10-16: "Within 5% either side counts as a test"."""
    from sepa import symbols
    sym = str(sym or "").upper()
    closed = KL.closed_frame(df, session) if df is not None else None
    if closed is None or len(closed) == 0:
        return {"symbol": sym, "status": "no_bars"}
    idx = KL._norm_index(closed)
    last_d = idx[-1].date()
    if last_d < KL.prev_market_day(session):
        return {"symbol": sym, "status": "stale", "date": last_d.isoformat()}
    if len(closed) < YEAR_BARS:
        return {"symbol": sym, "status": "short_history", "date": last_d.isoformat(),
                "n_bars": int(len(closed))}
    feat = frame_features(closed)
    st = row_statuses(feat, body_max=cfg.body_pct)[-1]
    last = feat.iloc[-1]
    close = float(last["close"])
    ath = None
    pct_ath_vec = None
    if st in ("no_downtrend", "fired"):
        a = ATH.closed_read(sym, df, ath_doc, listed, session, now_ts=now_ts)
        if a and (_f(a.get("hi_closed")) or 0) > 0:
            pct_ath_raw = (1.0 - close / float(a["hi_closed"])) * 100.0
            pct_ath_vec = np.full(len(feat), np.nan)
            pct_ath_vec[-1] = pct_ath_raw
            st = row_statuses(feat, body_max=cfg.body_pct, pct_below_ath=pct_ath_vec)[-1]
            ath = {"hi": float(a["hi_closed"]), "hi_date": a.get("hi_date"),
                   "proven": bool(a.get("proven")), "label": a.get("label"),
                   "since": a.get("since"), "pct_below": round(pct_ath_raw, 2)}
    if st == "fired":
        if symbols.is_delisted(sym):
            st = "delisted"
        elif not INCLUDE_ETFS and sym in (etf_set or ()):
            st = "etf"
        elif bool(last["suspect"]):
            st = "data_suspect"
    w52 = suspect = None
    adv50 = _r(last["adv50"], 0)
    if st in ("fired", "delisted", "etf", "data_suspect"):
        w = FAL.closed_read(sym, df, session) or {}
        if w.get("high") is not None:
            w52 = {"high": w["high"], "high_date": w.get("high_date"), "pct_below": w.get("pct_below")}
        adv50 = w.get("adv50", adv50)
        if st == "data_suspect":
            suspect = w.get("suspect") or FAL._suspect(closed)
    rd = reads_vector(feat["pct_below_52w"].to_numpy(dtype=float)[-1:],
                      None if pct_ath_vec is None else pct_ath_vec[-1:],
                      feat["below_mas"].to_numpy(dtype=bool)[-1:])
    reads = [k for k in READS if bool(rd[k][0])]
    ref_idx = int(last["ref_idx"])
    return {"symbol": sym, "status": str(st), "date": last_d.isoformat(),
            "open": _r(last["open"], 4), "high": _r(last["high"], 4), "low": _r(last["low"], 4),
            "close": _r(close, 4), "volume": _r(last["volume"], 0),
            "body_pct": _r(last["body_pct"], 4), "upper_wick_pct": _r(last["upper_wick_pct"], 4),
            "lower_wick_pct": _r(last["lower_wick_pct"], 4), "variant": last["variant"],
            "doji5": bool(last["doji5"]), "ref_low": _r(last["ref_low"], 4),
            "ref_date": _iso(idx, ref_idx), "ref_age": int(last["ref_age"]),
            "test_pct": _r(last["test_pct"], 2), "tested": bool(last["tested"]),
            "undercut": bool(last["undercut"]), "reclaimed": bool(last["reclaimed"]),
            "w52": w52, "pct_below_52w": _r(last["pct_below_52w"], 2), "ath": ath,
            "pct_below_ath": None if ath is None else ath["pct_below"],
            "sma50": _r(last["sma50"], 4), "sma200": _r(last["sma200"], 4),
            "below_mas": bool(last["below_mas"]), "reads": reads,
            "vol_ratio": _r(last["vol_ratio"], 2), "vol_word": last["vol_word"],
            "range_atr": _r(last["range_atr"], 2), "adv50": _r(adv50, 0),
            "n_bars": int(len(closed)), "suspect": suspect}


# ---------------------------------------------------------------------------
# the board read (I/O in the background thread only) — the 📉 memo shape
# ---------------------------------------------------------------------------
def session_for(now: datetime) -> date:
    """== FAL.session_for (KL.levels_session): the session rolls at KL.ROLL_AT."""
    return FAL.session_for(now)


def _syms(raw) -> list:
    out: list = []
    seen: set = set()
    for s in raw or []:
        s = str(s or "").strip().upper()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _resolve(ukey: str, universe_fn=None) -> list:
    if universe_fn is None:
        from supply_demand import demand_reentry as D
        return _syms(D._resolve_universe(ukey)[0])
    return _syms(universe_fn(ukey))


def _sessions(session: date, k: int) -> list:
    out = [session]
    while len(out) < max(1, int(k)):
        out.append(KL.prev_market_day(out[-1]))
    return out


def build(universe, session: date, *, universe_fn=None, frames_fn=None, history_fn=None, listing_fn=None,
          etf_fn=None, sessions_on_tab: int = SESSIONS_ON_TAB) -> dict:
    """ONE cached-frames read (bulk_cached_frames — Mongo, never a fetch), ONE
    ath_history read, ONE listing read, the static ETF lists; every name read at
    the 10%-body switch (the 5% view is a request-time filter on `doji5`).
    Raises on an empty frames read (never memoised). WRITES NOTHING.
    `sum(counts[s] for s in STATUSES) == counts["scanned"]`."""
    ukey = FAL._ukey(universe)
    syms = _resolve(ukey, universe_fn)
    frames = (frames_fn or prices.bulk_cached_frames)(syms) or {}
    if syms and not frames:
        raise RuntimeError(f"doji sweep tab: the price-cache read returned no frames for "
                           f"{len(syms):,} names — not memoising an empty read")
    if history_fn is None:
        history_fn = AH.read_many
    if listing_fn is None:
        from sepa import ipo_age
        listing_fn = ipo_age.listing_dates_map
    docs = history_fn(syms) or {}
    listing = listing_fn(syms) or {}
    etf_set = (etf_fn or FAL._static_etfs)() or set()
    now_ts = time.time()
    cfg = Cfg(body_pct=DOJI_BODY_WIDE_PCT)
    sess = _sessions(session, sessions_on_tab)
    counts = {k: 0 for k in COUNT_KEYS}
    rows: dict = {}
    suspects: list = []
    for sym in syms:
        counts["scanned"] += 1
        for k, s in enumerate(sess):
            try:
                r = read(sym, frames.get(sym), session=s, ath_doc=docs.get(sym),
                         listed=ATH.listed_for(sym, listing), cfg=cfg, etf_set=etf_set, now_ts=now_ts)
            except Exception as exc:                                # noqa: BLE001
                log.debug("doji sweep tab: %s read failed: %s", sym, exc)
                r = {"symbol": sym, "status": "no_bars"}
            if k == 0:
                counts[r["status"]] += 1
                if r["status"] == "data_suspect" and isinstance(r.get("suspect"), dict):
                    suspects.append({"symbol": sym, **r["suspect"], "pct_below": r.get("pct_below_52w")})
            if r["status"] == "fired":
                if k >= 1:
                    counts["fired_earlier"] += 1
                rows[sym] = r
                break
    del frames
    suspects.sort(key=lambda d: d["symbol"])
    built = time.time()
    return {"syms": syms, "rows": rows, "counts": counts, "suspects": suspects,
            "session": session.isoformat(), "as_of": KL.prev_market_day(session).isoformat(),
            "built_ts": built,
            "built_at": datetime.fromtimestamp(built, tz=KL.ET).isoformat(timespec="seconds"),
            "ukey": ukey}


def _safe_reason(exc: BaseException) -> str:
    return FAL._safe_reason(exc)


def _spawn(target, name: str) -> None:
    threading.Thread(target=target, name=name, daemon=True).start()


def _store(key: tuple, entry: dict) -> bool:
    """Under `_lock`. A late older-session build is dropped; storing evicts
    older sessions."""
    newest = max((k[0] for k in _memo), default=key[0])
    if key[0] < newest:
        log.info("doji sweep tab: dropped a late %s build (memo holds %s)", key[0], newest)
        return False
    for k in [k for k in _memo if k[0] < key[0]]:
        _memo.pop(k, None)
    _memo[key] = entry
    _failures.pop(key, None)
    return True


def _warm(key: tuple, universe: str, session: date) -> None:
    def _work():
        try:
            entry = build(universe, session)
            with _lock:
                _store(key, entry)
        except Exception as exc:                                    # noqa: BLE001
            log.warning("doji sweep tab: build failed for %s: %s", key, type(exc).__name__)
            with _lock:
                _failures[key] = (time.time(), _safe_reason(exc))
        finally:
            with _lock:
                _warming.discard(key)

    with _lock:
        if key in _warming:
            return
        _warming.add(key)
    _spawn(_work, f"doji-sweep-tab-{key[0]}-{key[1]}")


def cached_or_warm(universe, *, now: datetime, sync: bool = False) -> dict:
    """{"state": "ready"|"warming"|"error", "entry", "reason"}. Fresh exact entry
    -> ready. `sync=True` builds inline (never spawns). Otherwise ONE background
    build (unless one failed under FAIL_RETRY_SEC ago) and the newest held entry
    of the same universe is served (the 📉 memo, keyed (session, universe))."""
    session = session_for(now)
    ukey = FAL._ukey(universe)
    key = (session.isoformat(), ukey)
    with _lock:
        entry = _memo.get(key)
    fresh = entry is not None and (time.time() - float(entry.get("built_ts") or 0)) < MEMO_TTL_SEC
    if fresh:
        return {"state": "ready", "entry": entry, "reason": None}
    if sync:
        try:
            built = build(ukey, session)
        except Exception as exc:
            with _lock:
                _failures[key] = (time.time(), _safe_reason(exc))
            raise
        with _lock:
            _store(key, built)
        return {"state": "ready", "entry": built, "reason": None}
    with _lock:
        failed = _failures.get(key)
    backing_off = failed is not None and (time.time() - float(failed[0])) < FAIL_RETRY_SEC
    if not backing_off:
        _warm(key, ukey, session)
    with _lock:
        held_key = key if key in _memo else max(
            (k for k in _memo if k[1] == key[1]),
            key=lambda k: float(_memo[k].get("built_ts") or 0), default=None)
        held = _memo.get(held_key) if held_key is not None else None
    if held is not None:
        return {"state": "ready", "entry": held, "reason": None}
    if failed is not None:
        return {"state": "error", "entry": None, "reason": failed[1] or "unknown"}
    return {"state": "warming", "entry": None, "reason": None}


# ---------------------------------------------------------------------------
# per request: body switch, chips, order (PURE)
# ---------------------------------------------------------------------------
def parse_filters(spec) -> tuple:
    """"w52_60, reclaimed,junk" -> ("w52_60", "reclaimed"). Split on "," and "+",
    trimmed, lowercased, unknown tokens dropped, canonical FILTER_KEYS order;
    non-str / blank -> ()."""
    if not isinstance(spec, str) or not spec.strip():
        return ()
    toks = {t.strip().lower() for t in spec.replace("+", ",").split(",")}
    return tuple(k for k in FILTER_KEYS if k in toks)


def parse_body(raw) -> int:
    """A served BODY_STEPS value given as an exact digit string (or int), else
    BODY_STEPS[0]. " 10 " and "7" -> the default."""
    if isinstance(raw, bool) or not isinstance(raw, (str, int)):
        return BODY_STEPS[0]
    s = str(raw)
    if not s.isdigit():
        return BODY_STEPS[0]
    v = int(s)
    return v if (v in BODY_STEPS and s == str(v)) else BODY_STEPS[0]


def tile_filter(r: dict) -> dict:
    """The chips' True / False / None (not read) for one row. The 52-week chips
    read the 📉 tab's served pct (its depth views' number)."""
    pct = (r.get("w52") or {}).get("pct_below")
    return {"w52_40": _ge(pct, DEPTH_CHIPS[0]), "w52_60": _ge(pct, DEPTH_CHIPS[1]),
            "w52_70": _ge(pct, DEPTH_CHIPS[2]),
            "ath_60": None if r.get("pct_below_ath") is None else ("ath" in (r.get("reads") or [])),
            "mas": bool(r.get("below_mas")), "reclaimed": bool(r.get("reclaimed"))}


def filter_line(items, passed_all, pool) -> str:
    """W17 — the served line while a chip is ticked."""
    bits = []
    for it in items:
        if not it["on"]:
            continue
        b = f"{it['label']}: {_n(it['pass'])} pass, {_n(it['hidden'])} hidden"
        if it["no_read"]:
            b += f" ({_n(it['no_read'])} not read)"
        bits.append(b)
    return (f"Chips on (every ticked chip must pass) — {'; '.join(bits)}. {_n(passed_all)} of "
            f"{_n(pool)} pass every ticked chip (each count is over all {_n(pool)} names at this body).")


def filters_block(tfs, active, *, pool: int) -> dict:
    """Per-chip counts over every name at the picked body (each chip on its own),
    the served line when any is ticked. No mode switch: every ticked chip must
    pass (K3 "chips narrow")."""
    tfs = [t if isinstance(t, dict) else {} for t in (tfs or [])]
    act = tuple(k for k in FILTER_KEYS if k in (active or ()))
    items = []
    for k in FILTER_KEYS:
        vals = [t.get(k) for t in tfs]
        n_pass = sum(1 for v in vals if v is True)
        n_fail = sum(1 for v in vals if v is False)
        n_none = len(vals) - n_pass - n_fail
        on = k in act
        items.append({"key": k, "label": FILTER_LABELS[k], "on": on, "pass": n_pass, "fail": n_fail,
                      "no_read": n_none, "hidden": (n_fail + n_none) if on else 0,
                      "note": FILTER_NOTES[k]})
    passed_all = sum(1 for t in tfs if DMT.passes(t, act, DMT.MODE_ALL)) if act else None
    return {"keys": list(FILTER_KEYS), "active": list(act), "pool": int(pool or 0),
            "mode": DMT.MODE_ALL, "passed_all": passed_all, "shown": passed_all,
            "hidden": (len(tfs) - passed_all) if act else 0, "items": items,
            "line": filter_line(items, passed_all, pool) if act else None,
            "note": FILTERS_NOTE, "measured": False}


def body_block(body: int) -> dict:
    return {"param": BODY_PARAM, "pct": body,
            "steps": [{"key": str(b), "label": BODY_LABELS[b], "title": BODY_TITLES[b], "on": b == body,
                       "default": b == BODY_STEPS[0]} for b in BODY_STEPS]}


def _ord(iso) -> int:
    try:
        return date.fromisoformat(str(iso)[:10]).toordinal()
    except (TypeError, ValueError):
        return 0


def rank(entry: dict, *, sort: str, active=(), body: int = BODY_STEPS[0]) -> tuple:
    """(rows at the picked body after the ticked chips, in the asked order,
    counts, filters block). Rows are the memo's own dicts — READ-ONLY; the board
    copies what it uses. Orders (stable, ties by symbol): default = the newest
    candle, then the deepest under the 52-week high; SORT_TEST = the low closest
    to the prior low (either side); SORT_ATH = the deepest under the all-time
    high, a name with no ATH read last; any other sort = default."""
    every = list((entry.get("rows") or {}).values())
    at_body = every if body == BODY_STEPS[1] else [r for r in every if r.get("doji5")]
    if sort == SORT_TEST:
        key = lambda r: (abs(float(r.get("test_pct") or 0.0)), -(r.get("pct_below_52w") or 0.0),  # noqa: E731
                         r["symbol"])
    elif sort == SORT_ATH:
        key = lambda r: (r.get("pct_below_ath") is None, -(r.get("pct_below_ath") or 0.0),  # noqa: E731
                         -(r.get("pct_below_52w") or 0.0), r["symbol"])
    else:
        key = lambda r: (-_ord(r.get("date")), -(r.get("pct_below_52w") or 0.0), r["symbol"])  # noqa: E731
    at_body = sorted(at_body, key=key)
    act = tuple(k for k in FILTER_KEYS if k in (active or ()))
    tfs = [tile_filter(r) for r in at_body]
    filters = filters_block(tfs, act, pool=len(at_body))
    kept = [r for r, tf in zip(at_body, tfs) if DMT.passes(tf, act, DMT.MODE_ALL)]
    counts = {k: 0 for k in COUNT_KEYS}
    counts.update({k: v for k, v in (entry.get("counts") or {}).items() if k in counts})
    counts.update(at_body=len(at_body), wider_body=len(every) - len(at_body),
                  hidden_by_chips=len(at_body) - len(kept),
                  undercut=sum(1 for r in at_body if r.get("undercut")))
    return kept, counts, filters


def served_sorts() -> list:
    return [{"key": DEFAULT_SORT, "label": DEFAULT_SORT_LABEL},
            {"key": SORT_TEST, "label": TEST_SORT_LABEL},
            {"key": SORT_ATH, "label": ATH_SORT_LABEL}]


# ---------------------------------------------------------------------------
# the ledger hand-off (AMENDMENTS6 B7) — WRITES NOTHING
# ---------------------------------------------------------------------------
def ledger_bucket(fire: dict) -> str:
    """Which ledger block a fire belongs to (AMENDMENTS6 B7): LEDGER_BUCKETS[0]
    = the tab's default view (the house 5% body AND the tab's default liquidity
    floor — `board.passes_liquidity` at `board.default_min_tier(TAB_KEY)`, the
    house engine, never a typed number); a fire under the floor (or with no
    turnover) = LEDGER_BUCKETS[2] whatever its body; any other fire (a body from
    5% to under 10%) = LEDGER_BUCKETS[1]. Lazy board import (no module cycle)."""
    from chart_maps import board as B
    if not B.passes_liquidity((fire or {}).get("adv50"), B.default_min_tier(TAB_KEY)):
        return LEDGER_BUCKETS[2]
    return LEDGER_BUCKETS[0] if (fire or {}).get("doji5") else LEDGER_BUCKETS[1]


def ledger_fires(*, now: Optional[datetime] = None, sessions: int = LEDGER_BACKFILL_SESSIONS, universe: str = "full",
                 universe_fn=None, frames_fn=None, history_fn=None, listing_fn=None, etf_fn=None) -> list:
    """Every candle the tab's detector FIRED on (at the 10%-body switch) over the
    last `sessions` closed sessions, one dict of exactly LEDGER_KEYS per (symbol,
    candle date), for `patterns.history.record_doji_sweeps` (the 17:20 cron).
    ONE frames / history / listing / ETF read for the universe, then one build
    per session on those held reads. `bucket` = ledger_bucket (B7: the 5%-body
    at-floor headline vs the 10%-body and below-floor sub-blocks). WRITES
    NOTHING; raises like build() on an empty frames read (the caller logs it)."""
    now = now or datetime.now(KL.ET)
    ukey = FAL._ukey(universe)
    syms = _resolve(ukey, universe_fn)
    frames = (frames_fn or prices.bulk_cached_frames)(syms) or {}
    if history_fn is None:
        history_fn = AH.read_many
    if listing_fn is None:
        from sepa import ipo_age
        listing_fn = ipo_age.listing_dates_map
    docs = history_fn(syms) or {}
    listing = listing_fn(syms) or {}
    etf_set = (etf_fn or FAL._static_etfs)() or set()
    out: list = []
    seen: set = set()
    for s in _sessions(session_for(now), sessions):
        entry = build(universe, s, frames_fn=lambda _: frames, history_fn=lambda _: docs,
                      listing_fn=lambda _: listing, etf_fn=lambda: etf_set,
                      universe_fn=lambda _: syms, sessions_on_tab=1)
        for sym in sorted(entry["rows"]):
            r = entry["rows"][sym]
            if r.get("status") != "fired" or (sym, r.get("date")) in seen:
                continue
            seen.add((sym, r.get("date")))
            fire = {k: r.get(k) for k in LEDGER_KEYS if k != "bucket"}
            fire["reads"] = list(r.get("reads") or [])
            fire["bucket"] = ledger_bucket(fire)
            out.append({k: fire.get(k) for k in LEDGER_KEYS})
    del frames
    return out


# ---------------------------------------------------------------------------
# the study line (lazy DSM read)
# ---------------------------------------------------------------------------
def _measured() -> dict:
    try:
        from chart_maps import doji_sweep_measured as DSM
        m = DSM.load()
        return m if isinstance(m, dict) else dict(MEASURED_DEFAULT)
    except (ImportError, AttributeError):
        return dict(MEASURED_DEFAULT)


def is_measured() -> bool:
    """True only when study_block() serves the measured line — the flag and the
    text never disagree (fix round 1)."""
    return study_block()["status"] == "measured"


def _ci(c) -> tuple:
    """(lo, hi) signed; a None CI (cluster_ci with fewer than 2 clusters) is
    served NOT_READ, never a reason to hide a completed study."""
    if c is None:
        return NOT_READ, NOT_READ
    return _sn(c[0]), _sn(c[1])


def study_block() -> dict:
    """{"status", "text", "verdict", "prereg", "script"} — NOTE_PENDING until
    doji_sweep_measured.MEASURED is a measured literal; any malformed literal
    (a missing key, an unknown verdict) serves the unmeasured block (a bad paste
    never breaks the served line). A None NUMBER is served NOT_READ."""
    pending = {"status": "unmeasured", "text": NOTE_PENDING, "verdict": None, "prereg": PREREG_PATH,
               "script": SCRIPT_PATH}
    m = _measured()
    if m.get("status") != "measured":
        return pending
    try:
        from chart_maps import doji_sweep_measured as DSM
        vw = _verdict_words()
        p = m["primary"]
        cells = m["cells"]
        a, nd = cells["any_read"], cells["test_no_doji"]
        deep = cells[DSM.PREDECLARED_TOO_SMALL[0]]
        lo, hi = _ci(p["adj_ci_block"])
        slo, shi = _ci(p["adj_ci_symbol"])
        any_lo, any_hi = _ci(a["adj_ci_block"])
        any_slo, any_shi = _ci(a["adj_ci_symbol"])
        nd_lo, nd_hi = _ci(nd["adj_ci_block"])
        nd_slo, nd_shi = _ci(nd["adj_ci_symbol"])
        clo, chi = _ci(p["ci_confirm_block"])
        mlo, mhi = _ci(p["ci_mean_block"])
        holm_p = [_f(x["p_holm"]) for x in (p, a, nd)]
        holm = (HOLM_LINE.format(**{f"p{i + 1}": f"{v:.3f}" for i, v in enumerate(holm_p)})
                if all(v is not None for v in holm_p) else NO_HOLM_LINE)
        text = _measured_fmt().format(
            run_date=m["run_date"], prereg=m["prereg_commit"], first=m["first_session"],
            last=m["last_session"], n_events=_n(p["n_events"]), n_dates=_n(p["n_dates"]),
            n_symbols=_n(p["n_symbols"]), h=int(p["horizon"]),
            em=_sn(p["adj_event_median_pct"]), pm=_sn(p["adj_placebo_median_pct"]),
            n_placebo=_n(p["n_placebo"]), n_short=_n(p["placebo_short_pool"]),
            n_unmatched=_n(p["n_unmatched"]), pp=_sn(p["adj_median_diff_pp"]),
            raw_pp=_sn(p["median_diff_pp"]), ci_lvl=_lvl(p["ci_pct"]),
            block=int(m["block_sessions"]), lo=lo, hi=hi, slo=slo, shi=shi, words=vw[p["verdict"]],
            any_n=_n(a["n_events"]), any_pp=_sn(a["adj_median_diff_pp"]), any_ci_lvl=_lvl(a["ci_pct"]),
            any_lo=any_lo, any_hi=any_hi, any_slo=any_slo, any_shi=any_shi, any_words=vw[a["verdict"]],
            nd_n=_n(nd["n_events"]), nd_pp=_sn(nd["adj_median_diff_pp"]), nd_ci_lvl=_lvl(nd["ci_pct"]),
            nd_lo=nd_lo, nd_hi=nd_hi, nd_slo=nd_slo, nd_shi=nd_shi,
            nd_words=CONTRAST_WORDS[nd["verdict"]],
            deep_n=_n(deep["n_events"]), deep_d=_n(deep["n_dates"]), deep_words=_deep_words(deep),
            holm=holm,
            c=int(m["confirm_sessions"]), cp=_rate(p["confirm_pct"]),
            pcp=_rate(p["placebo_confirm_pct"]), clo=clo, chi=chi, sp=_rate(p["stop_pct"]),
            psp=_rate(p["placebo_stop_pct"]), mean=_sn(p["event_mean_pct"]),
            pmean=_sn(p["placebo_mean_pct"]), mlo=mlo, mhi=mhi,
            net=_sn(p["net_mean_pct"]), cost=f"{float(m['cost_round_trip_pct']):g}")
    except (KeyError, TypeError, ValueError, IndexError):
        return pending
    return {"status": "measured", "text": text, "verdict": p.get("verdict"), "prereg": PREREG_PATH,
            "script": SCRIPT_PATH}


# ---------------------------------------------------------------------------
# envelope words (every number from a constant or a count)
# ---------------------------------------------------------------------------
def header_text(counts, *, body: int, as_of) -> str:
    """W8 + AMENDMENTS6 B16 (the undercut count under the "Sweep" word)."""
    c = counts or {}
    when = (f"on {as_of or '—'}" if SESSIONS_ON_TAB <= 1
            else f"on the last {SESSIONS_ON_TAB} closed candles (newest {as_of or '—'})")
    return (f"{MARK} {_n(c.get('at_body'))} of {_n(c.get('scanned'))} names printed a doji {when} — a body "
            f"under {body}% of the day's range — with the low within {SWEEP_TEST_PCT:g}% either side of the "
            f"lowest low of the {SWEEP_REF_SESSIONS} sessions before it, in a downtrend: {DOWN_PCT:g}%+ under "
            f"the 52-week high, {DOWN_PCT:g}%+ under the all-time high, or below the {SMA_FAST}- and "
            f"{SMA_SLOW}-day. Sweep: {_n(c.get('at_body'))} tests · {_n(c.get('undercut'))} undercut the low.")


def order_line(sort) -> str:
    """W5 / W6 / W7."""
    if sort == SORT_TEST:
        return (f"Order: the low closest to the prior {SWEEP_REF_SESSIONS}-session low first (either side), "
                "then the deepest under the 52-week high.")
    if sort == SORT_ATH:
        return ("Order: the deepest under the all-time high first; a name with no all-time-high read "
                "sits last.")
    return ("Order: the newest candle first, then the deepest under the 52-week high — an order, not a "
            "ranking of setups.")


def count_line(counts, *, body: int, min_tier_label: str, need_date) -> str:
    """W13 (AMENDMENTS6 B13: a bad bar is a flat candle on the day itself; an
    unreadable bar in the reference window lands in the same class)."""
    c = counts or {}
    b5, b10 = BODY_STEPS
    N = SWEEP_REF_SESSIONS
    text = (f"Showing {_n(c.get('shown'))} — {_n(c.get('dropped_thin'))} under the liquidity floor "
            f"({min_tier_label})")
    if int(c.get("no_turnover") or 0):
        text += f", {_n(c.get('no_turnover'))} with no turnover to check"
    text += "."
    if int(c.get("hidden_by_chips") or 0):
        text += f" {_n(c.get('hidden_by_chips'))} hidden by the chips you ticked."
    if body == b5 and int(c.get("wider_body") or 0):
        text += (f" {_n(c.get('wider_body'))} more have a body from {b5}% to under {b10}% (the "
                 f"“{BODY_LABELS[b10]}” switch shows them).")
    if int(c.get("fired_earlier") or 0):
        text += f" {_n(c.get('fired_earlier'))} fired on one of the {SESSIONS_ON_TAB - 1} candles before."
    text += (f" Not listed: {_n(c.get('not_doji'))} whose candle was not a doji (a body of {b10}% of the "
             f"range or more), {_n(c.get('no_test'))} whose low sat more than {SWEEP_TEST_PCT:g}% from the "
             f"prior {N}-session low, {_n(c.get('ref_too_fresh'))} whose prior {N}-session low was set "
             f"under {SWEEP_REF_MIN_AGE} sessions before the candle, {_n(c.get('no_downtrend'))} meeting "
             f"none of the three downtrend reads, {_n(c.get('data_suspect'))} with a one-session close move "
             f"of {GLITCH_RATIO:g}× or more in the last {YEAR_BARS} sessions (named below — check before "
             f"trusting), {_n(c.get('etf'))} ETFs, {_n(c.get('delisted'))} delisted, "
             f"{_n(c.get('short_history'))} with fewer than {YEAR_BARS} sessions of history, "
             f"{_n(c.get('stale'))} whose cached bars end before {need_date}, {_n(c.get('bad_bars'))} with a "
             f"flat candle today (or an unreadable bar in the {N} sessions before it), "
             f"{_n(c.get('no_bars'))} with no cached bars.")
    return text


def error_note(reason) -> str:
    """W10."""
    return ERROR_NOTE_FMT.format(reason=str(reason or "unknown"), mins=int(FAIL_RETRY_SEC // 60))


def _block(state: str, *, session_iso: str, sort: str, body: int, header: str, filters: dict,
           entry: Optional[dict] = None, counts: Optional[dict] = None,
           min_tier_label: Optional[str] = None) -> dict:
    ready = state == "ready" and entry is not None
    need = KL.prev_market_day(date.fromisoformat(session_iso)).isoformat()
    return {"state": state, "session": session_iso,
            "as_of": (entry or {}).get("as_of") if ready else None,
            "built_at": (entry or {}).get("built_at") if ready else None,
            "measured": is_measured(), "study": study_block(), "sort": sort, "header": header,
            "order_line": order_line(sort),
            "count_line": (count_line(counts, body=body, min_tier_label=min_tier_label or "—", need_date=need)
                           if ready else None),
            "note": NOTE, "body": body_block(body), "filters": filters,
            "counts": dict(counts) if ready else None,
            "suspects": FAL.suspects_block((entry or {}).get("suspects")) if ready else None,
            "reads_legend": list(READS_LEGEND), "test_pct": SWEEP_TEST_PCT,
            "ref_sessions": SWEEP_REF_SESSIONS, "ref_min_age": SWEEP_REF_MIN_AGE, "down_pct": DOWN_PCT,
            "sma_fast": SMA_FAST, "sma_slow": SMA_SLOW, "year_bars": YEAR_BARS, "filter_param": FILTER_PARAM}


def ready_block(counts, *, entry, sort, body, filters, min_tier_label) -> dict:
    """The served `doji_sweep_board` once the memo is ready (§3.4)."""
    return _block("ready", session_iso=str(entry["session"]), sort=sort, body=body,
                  header=header_text(counts, body=body, as_of=entry.get("as_of")), filters=filters,
                  entry=entry, counts=counts, min_tier_label=min_tier_label)


def warming_block(*, now, sort, body, active) -> dict:
    """While the first build runs: the warming header + the study line."""
    return _block("warming", session_iso=session_for(now).isoformat(), sort=sort, body=body,
                  header=WARMING_NOTE, filters=filters_block([], active, pool=0))


def error_block(reason, *, now, sort, body, active) -> dict:
    return _block("error", session_iso=session_for(now).isoformat(), sort=sort, body=body,
                  header=error_note(reason), filters=filters_block([], active, pool=0))


# ---------------------------------------------------------------------------
# tile words (served; the FE prints them verbatim)
# ---------------------------------------------------------------------------
def _variant(r) -> str:
    return VARIANT_WORDS.get(r.get("variant") or "plain", VARIANT_WORDS["plain"])


def test_text(r) -> str:
    """W24 — badge 2."""
    t = float(r.get("test_pct") or 0.0)
    N = SWEEP_REF_SESSIONS
    if r.get("reclaimed"):
        return f"Undercut the prior {N}-session low by {abs(t):.2f}% · closed back above it"
    if r.get("undercut"):
        return f"Undercut the prior {N}-session low by {abs(t):.2f}% · closed under it"
    if round(t, 2) == 0:
        return f"Low at the prior {N}-session low"
    return f"Low {t:.2f}% above the prior {N}-session low"


def reads_text(r) -> str:
    """W26 with AMENDMENTS6 B16: "Reads met: …" (never "Downtrend" alone)."""
    reads = r.get("reads") or []
    parts = []
    if "w52" in reads and r.get("pct_below_52w") is not None:
        parts.append(f"{W52_MARK} {float(r['pct_below_52w']):.2f}% under the 52-week high")
    a = r.get("ath")
    if "ath" in reads and a:
        if a.get("proven"):
            parts.append(f"{ATH_MARK} {float(a['pct_below']):.2f}% under the all-time high")
        else:
            parts.append(f"{ATH_MARK} {float(a['pct_below']):.2f}% under the high since {a.get('since')}")
    if "mas" in reads:
        parts.append(f"below the {SMA_FAST}- and {SMA_SLOW}-day")
    return READS_HEAD + " · ".join(parts)


def tile_badges(r) -> list:
    """W23 (warn) + W24 (muted)."""
    return [{"text": f"{MARK} {_variant(r)} · body {float(r.get('body_pct') or 0.0) * 100:.1f}% of the range",
             "tone": "warn"},
            {"text": test_text(r), "tone": "muted"}]


def _ma_state(r) -> str:
    c, s50, s200 = _f(r.get("close")), _f(r.get("sma50")), _f(r.get("sma200"))
    if c is None or s50 is None or s200 is None:
        return "not read"
    if c < s50 and c < s200:
        return "close below both"
    if c >= s50 and c >= s200:
        return "close above both"
    return f"close above the {SMA_FAST}-day" if c >= s50 else f"close above the {SMA_SLOW}-day"


def tile_stats(r) -> list:
    """W25, in order."""
    doji = (f"{_variant(r)} · upper wick {float(r.get('upper_wick_pct') or 0.0) * 100:.0f}% · lower wick "
            f"{float(r.get('lower_wick_pct') or 0.0) * 100:.0f}%")
    if r.get("range_atr") is not None:
        doji += f" · range {float(r['range_atr']):.1f}× the {ATR_BARS}-day ATR"
    out = [{"k": "Doji", "v": doji},
           {"k": "Prior low", "v": (f"{float(r.get('ref_low') or 0.0):.2f} · {r.get('ref_date') or '—'} · "
                                    f"{int(r.get('ref_age') or 0)} sessions before")}]
    w = r.get("w52")
    if w and w.get("high") is not None and w.get("pct_below") is not None:
        out.append({"k": "52w high", "v": (f"{float(w['high']):.2f} · {w.get('high_date') or '—'} · "
                                           f"{float(w['pct_below']):.2f}% under")})
    else:
        out.append({"k": "52w high", "v": "not read"})
    a = r.get("ath")
    if a:
        out.append({"k": "All-time high" if a.get("proven") else f"High since {a.get('since')}",
                    "v": f"{float(a['hi']):.2f} · {a.get('hi_date') or '—'} · {float(a['pct_below']):.2f}% under"})
    else:
        out.append({"k": "All-time high", "v": "not read"})
    if r.get("sma50") is not None and r.get("sma200") is not None:
        out.append({"k": f"{SMA_FAST} / {SMA_SLOW}-day",
                    "v": f"{float(r['sma50']):.2f} / {float(r['sma200']):.2f} · {_ma_state(r)}"})
    else:
        out.append({"k": f"{SMA_FAST} / {SMA_SLOW}-day", "v": "not read"})
    if r.get("vol_ratio") is not None:
        v = f"{float(r['vol_ratio']):.1f}× the {VOL_AVG_BARS}-day average"
        if r.get("vol_word"):
            v += f" · {r['vol_word']}"
        out.append({"k": "Volume", "v": v})
    else:
        out.append({"k": "Volume", "v": "not read"})
    return out


def tile_lines(r) -> list:
    return [{"price": r.get("ref_low"), "label": REF_LINE_LABEL, "tone": "neutral"}]


def tile_markers(r) -> list:
    return [{"date": r.get("date"), "label": MARK}]


def why_text(r, zone_text: str) -> str:
    """W27."""
    return f"{MARK} {_variant(r)} on {r.get('date')} · {test_text(r)} · {reads_text(r)} · {zone_text}"


def tile_block(r) -> dict:
    """The served `tile.doji_sweep` (the board adds `zone`)."""
    return {"date": r.get("date"), "variant": r.get("variant"), "variant_text": _variant(r),
            "body_pct": r.get("body_pct"), "upper_wick_pct": r.get("upper_wick_pct"),
            "lower_wick_pct": r.get("lower_wick_pct"), "doji5": bool(r.get("doji5")),
            "ref_low": r.get("ref_low"), "ref_date": r.get("ref_date"), "ref_age": r.get("ref_age"),
            "test_pct": r.get("test_pct"), "tested": bool(r.get("tested")), "undercut": bool(r.get("undercut")),
            "reclaimed": bool(r.get("reclaimed")), "test_text": test_text(r),
            "reads": list(r.get("reads") or []), "reads_text": reads_text(r),
            "w52": dict(r["w52"]) if r.get("w52") else None, "pct_below_52w": r.get("pct_below_52w"),
            "ath": dict(r["ath"]) if r.get("ath") else None, "pct_below_ath": r.get("pct_below_ath"),
            "sma50": r.get("sma50"), "sma200": r.get("sma200"), "below_mas": bool(r.get("below_mas")),
            "vol_ratio": r.get("vol_ratio"), "vol_word": r.get("vol_word"), "range_atr": r.get("range_atr"),
            "close": r.get("close"), "adv50": r.get("adv50")}
