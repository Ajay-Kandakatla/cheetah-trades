"""Strategy lab 2026-10-29 — one read-only script, a candidate registry, one runnable trial (T01).

THE ASKS (Ajay 2026-10-29, verbatim)
  "Also please a trading skil in to the mix I heard Claude now has a trading skill"
  "Look in to strategies yourself like ema based and Quant based reliable ones and also research
   baked in to this task but try and improve the strategy until you are postive in results"

NOTHING HERE IS A VERDICT. Every candidate is UNMEASURED until the outcome run (spec section 5)
runs after the prereg doc `docs/research/strategy_lab_2026_10_29_prereg.md` is committed. The
"trading skill" is the attached third-party quant connector; it is an INDEPENDENT cross-check of
the in-script PSR / DSR (the formula here is the gate of record). This script only writes the
unlabeled payloads for it (`connector_payloads.json`, no symbols).

CANDIDATES (every one behind `--candidate`)
  c5_reversal    RUN (trial T01). Short-term reversal, long only:
                 universe = top 500 by the median close*volume over each name's own last 50 bars
                 (liquid by `adr.liquidity_check` defaults, funds / crypto pairs / index docs out);
                 signal = the lowest tenth by 5-session return at the close of t; in at the open of
                 t+1; out at the open of t+6 (5 sessions); no stop; 10 bps + 5 bps slippage per side
                 for the top 1,000 (25 + 5 otherwise; unreachable for a top-500 rule).
  c1_ath_atr10, c2_xsmom_12_1, c3_ear_drift, c4_spy_sma10m
                 UNMEASURABLE on this cache (rolling 2-year price cache; no stamped earnings dates)
                 -> exit 3 before any read, no ledger entry. They stay UNMEASURED.

GATES (shortlist.md:23-27, pasted verbatim in `POSITIVE_TEXT`; v2 computation):
  A  OOS mean net per trade, 95% bootstrap CI over whole entry weeks (10,000 draws), in PERCENT,
     the word read on the unrounded CI (`RS.ci_of(..., dp=VERDICT_DP)`).
  B  strategy minus the same-name, same-month, same-split placebo with the overlap window
     [t-10, t-1] removed from the pool (`PLACEBO_EXCLUDE_BACK`); CI separates AND beats >= 95% of
     1,000 placebo sets.
  C  Deflated Sharpe >= 0.95 on the per-entry-day series (`GATE_C_SERIES`), N = every trial in the
     ledger (never resets).

READ-ONLY. Every pymongo write method -> a recorded no-op (`RS.block_writes`); every network
path -> `FetchRefused` (`block_network`). Never `prices.load_prices`, never a Massive fetch,
`levered_etf.load(ensure=False)` only, the type map by ONE `find_one`. No broker, order, lane
switch or constant is touched. No signal after the last signal session (no current-day list).
Smoke and calibration read the IS slice only (`seal_panel`).

LIMITS: see `LIMITS` (survivor-biased in the rule's favour; the type map is today's; a < 5x
unadjusted split is not caught; tier 2 unreachable for C5).

REPAIR 2026-10-29 (audit defects 1-4; no frozen parameter changed):
  1. An outcome run reads the ledger BEFORE any OOS read and refuses (rc 2) when T01 is already
     recorded under a different prereg sha256 (`ledger_conflict`, the one check `ledger_append`
     also uses) — a changed prereg can no longer write a verdict and then fail to log.
  2. `--ledger` must equal `LEDGER_PATH` (/research/strategy_lab_ledger.json) and its directory
     must already exist (the mount); `ledger_append` never creates a directory.
  3. A row with a >= 5x jump inside its hold (`prices._is_scale_glitch`) is KEPT and flagged
     (`glitch_hold`; counts under `flags` / `cohort_flags`); A prints with and without them.
  4. Each unmeasurable candidate carries its own `fact` in `status.json`.

GLITCH FIX 2026-10-29 (audit defect: 4 planted 10x reverse splits inside holds turned an iid null
POSITIVE): gates A and B must pass BOTH on all rows AND with the flagged (`glitch_hold`) rows
removed from trades and cohort (`verdict_of`); the report prints n_flagged and both lines; when
n_flagged > `GLITCH_VERDICT_MAX_SHARE` (5%) of the trade rows no verdict word is printed
(`UNMEASURED_GLITCH`). A harness rule, not a methodology number; no frozen parameter changed.

RUN (outside 09:00-16:30 ET; each in its own --rm container; no --env-file):
  Smoke:
    docker run --rm --cpus 4 --memory 3g --network cheetah-market-app_default \\
      -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York \\
      -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 \\
      -v /Users/ajay/clinet-test/wt-stratlab/backend:/app:ro \\
      -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro -v <S>:/strat -w /strat \\
      cheetah-api:latest python -u /app/scripts/strategy_lab_2026_10_29.py \\
      --candidate c5_reversal --smoke --out /strat/out/c5_reversal/smoke
  Calibration (IS only): the same with
      --candidate c5_reversal --calibrate --as-of 2026-10-29 --oos-from 2026-03-20 \\
      --out /strat/out/c5_reversal/calibration
  Outcome (BLOCKED until the prereg is committed; HASH = that commit): the same plus
      -v /Users/ajay/clinet-test/wt-stratlab/docs:/docs:ro \\
      -v /Users/ajay/clinet-test/eod-audits/research:/research and
      --candidate c5_reversal --as-of 2026-10-29 --oos-from 2026-03-20 \\
      --prereg /docs/research/strategy_lab_2026_10_29_prereg.md --prereg-commit HASH \\
      --ledger /research/strategy_lab_ledger.json --out /strat/out/c5_reversal
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import NormalDist
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import massive_keys  # noqa: E402
from chart_maps import fallen_tab  # noqa: E402
from chart_maps import high_beta_tab as HB  # noqa: E402
from chart_maps.gajjala import constants as GC  # noqa: E402
from chart_maps.gajjala import scanner  # noqa: E402
from chart_maps.gajjala import store as GSTORE  # noqa: E402
from scripts import high_beta_study as HBS  # noqa: E402
from scripts import resiliency_study as RS  # noqa: E402
from scripts.explosive_study import MIN_BUCKET_N  # noqa: E402
from sepa import adr  # noqa: E402
from sepa import etf_info  # noqa: E402
from sepa import levered_etf  # noqa: E402
from sepa import prices  # noqa: E402
from sepa import symbols  # noqa: E402

ET = ZoneInfo("America/New_York")
STUDY = "strategy_lab_2026_10_29"
SCRIPT = "backend/scripts/strategy_lab_2026_10_29.py"
PREREG = "docs/research/strategy_lab_2026_10_29_prereg.md"
BENCH = RS.BENCH
CI_PCT = RS.CI_PCT
MIN_CLUSTERS = MIN_BUCKET_N
_LIQ_SIG = inspect.signature(adr.liquidity_check).parameters
LIQ_MIN_DV = _LIQ_SIG["min_dollar_vol"].default
LIQ_PERIOD = _LIQ_SIG["period"].default
C5_UNIVERSE_TOP_N = 500          # shortlist.md:58
C5_RANK_BARS = 50                # shortlist.md:58
C5_R_LOOKBACK = 5                # shortlist.md:58
C5_BINS = 10                     # shortlist.md:58 (bottom decile)
C5_HOLD = 5                      # shortlist.md:58
COST_TIER1_TOP_N = 1000          # shortlist.md:18
COST_TIER1_BPS = 10.0            # shortlist.md:18
COST_TIER2_BPS = 25.0            # shortlist.md:18
SLIPPAGE_BPS = 5.0               # shortlist.md:18
CAP_PCT_OF_MDV = 1.0             # shortlist.md:18
CAP_MDV_BARS = 20                # shortlist.md:18
SETTLE_SESSIONS = 1              # T+1; shortlist.md:19 "usable from the next session"
BOOK_SLEEVES = C5_HOLD + SETTLE_SESSIONS     # v2 [C11] = 6
SIGNAL_OFFSET = 0                # the signal reads close t; the lookahead test mutates it to 1
OOS_NUM, OOS_DEN = 1, 3          # shortlist.md:24 last third by time
BOOT_DRAWS = 10_000              # shortlist.md:24
PLACEBO_SETS = 1_000             # shortlist.md:25
PLACEBO_BEAT_SHARE = 0.95        # shortlist.md:25
DSR_PASS = 0.95                  # shortlist.md:26
PLACEBO_EXCLUDE_BACK = C5_R_LOOKBACK + C5_HOLD   # v2 [C1] = 10, derived
GATE_C_SERIES = "per_entry_day"  # v2 [C3] shortlist.md:26 "(or per-rebalance)"; HIS CALL #3
GATE_C_KINDS = ("per_entry_day", "per_trade")
VERDICT_DP = 12                  # v2 [C2] precision only, percent units
SHOW_DP = 3
FUND_TYPES_SRC = "chart_maps.gajjala.constants.SCAN_INSTRUMENT_TYPES"
TYPES_STATE_ID = "types"         # gajjala store.py types_map()
CRYPTO_SUFFIX = "-USD"           # Yahoo crypto-pair spelling (a format fact)
STOPPED_SESSIONS = prices.STALE_MAX_TRADING_DAYS
DOCS_END_LABEL_DATE = "2026-05-01"   # design 3.4 IS label (C5): "docs end before 2026-05"
CALIB_REPS = 200                 # v2 [C4] measurement precision, never a gate
GLITCH_VERDICT_MAX_SHARE = 0.05  # glitch fix 2026-10-29: > 5% flagged rows -> no verdict word
UNMEASURED_GLITCH = "UNMEASURED-glitch"
CALIB_BUDGET_SEC = 600           # design 3.6 "Runtime budget 10 min"
PREREG_COMMIT_RE = r"^[0-9a-f]{12,40}$"
BOOT_CHUNK = 500                 # memory only (draws x clusters index matrix)
SEED = 20261029
EULER_GAMMA = 0.5772156649015329
FIRST_SIGNAL_IDX = max(LIQ_PERIOD, C5_R_LOOKBACK)
FORBIDDEN_WORDS = HB.FORBIDDEN_WORDS + ("edge", "recommend", "you should", "guarantee")
STRIDE_DEFAULT = 10
REFUSED_LEDGER_ROOTS = ("/tmp", "/private/tmp")
LEDGER_PATH = "/research/strategy_lab_ledger.json"   # RUN_OUTCOME --ledger; the mounted dir
EXCLUSION_REASONS = ("index_caret", "static_etf", "cached_etf", "levered_fund", "crypto_pair",
                     "type_not_equity")
SKIP_REASONS = ("no_entry_bar", "scale_glitch_signal")
FLAG_REASONS = ("scale_glitch_hold",)   # kept in trades AND cohort, flagged (repair 3)
EXIT_REASONS = ("time", "late_exit", "data_end")
MODES = ("smoke", "calibrate", "outcome")
ATTEMPTED_FETCHES: list = []

ROLLING_CACHE_FACT = "price_cache is a rolling 2-year window (prices.py:635)"
EARNINGS_DATES_FACT = ("sepa/earnings_watch.py keeps only each name's latest Yahoo last_report "
                       "(earnings_watch.py:99-107 and :240-250); no historical BMO/AMC-stamped "
                       "announcement-date series is stored")
CANDIDATES = {
    "c5_reversal": {"status": "runnable", "trial_id": "T01"},
    "c1_ath_atr10": {"status": "unmeasurable",
                     "needs": ">= 10 years of daily bars back to each listing (point-in-time ATH)",
                     "fact": ROLLING_CACHE_FACT},
    "c2_xsmom_12_1": {"status": "unmeasurable",
                      "needs": ">= 10 years of daily bars (>= 30 OOS rebalances)",
                      "fact": ROLLING_CACHE_FACT},
    "c3_ear_drift": {"status": "unmeasurable",
                     "needs": "a historical BMO/AMC-stamped announcement-date series",
                     "fact": EARNINGS_DATES_FACT},
    "c4_spy_sma10m": {"status": "unmeasurable", "needs": ">= 25 years of SPY daily bars",
                      "fact": ROLLING_CACHE_FACT},
}
UNMEASURED_NAMES = {"c1_ath_atr10": "C1 ATH breakout", "c2_xsmom_12_1": "C2 12-1 momentum",
                    "c3_ear_drift": "C3 earnings drift", "c4_spy_sma10m": "C4 SPY 10-month SMA"}
TRIALS = [{"trial_id": "T01", "candidate": "c5_reversal",
           "params": {"universe_top_n": C5_UNIVERSE_TOP_N,
                      "rank": f"median close*volume, {C5_RANK_BARS} own bars",
                      "r_lookback": C5_R_LOOKBACK, "bin": f"0 of {C5_BINS} (lowest r5)",
                      "entry": "open t+1", "exit": f"open t+1+{C5_HOLD}", "stop": None,
                      "cost_per_side_bps": {"tier1": COST_TIER1_BPS + SLIPPAGE_BPS,
                                            "tier2": COST_TIER2_BPS + SLIPPAGE_BPS}}}]
SURVIVOR_LABEL = ("provisional — survivor-biased in the rule's favour (dead names before the "
                  "cache absent; delisting returns not modelled)")
RULE_TEXT = ("top 500 names by 50-day median dollar volume; the lowest tenth by 5-session return "
             "at the close; in at the next open; out at the open 5 sessions later; no stop; "
             "long only.")
LIMITS = [
    "survivor-biased in the rule's favour: names that died before the app cached them are absent "
    "(the IS slice is close to survivors only); a stopped name exits at its last cached close "
    "(delisting returns not modelled)",
    "the instrument-type map is TODAY's active list: a fund that died before today reads unknown "
    "and is kept unless a fund list names it; some live stocks read unknown too",
    "a split appended below 5x (2:1, 3:2) between full refetches is NOT caught by the 5x glitch "
    "engine; the 20 largest single-session moves inside hold windows are listed for the audit",
    "a >= 5x jump inside a hold (the `prices._is_scale_glitch` engine) is KEPT and flagged: a "
    "real crash and an unadjusted split look alike; A and B must pass both with and without the "
    "flagged rows, and above 5% flagged rows no verdict word is printed",
    "C5 cost tier 2 is unreachable (rank <= 500 < 1,000): every trade pays 15 bps per side",
    "dividends are not in the bars (adjusted=true covers splits only)",
    "the week-cluster CI can run below its nominal level on this design (adjacent cohorts share "
    "4 of 5 hold days); the IS calibration rate prints beside the word",
    "per-entry-day Sharpe overstates PSR when cohorts overlap; the lag-1 autocorrelation and the "
    "sleeve range print beside it",
]
POSITIVE_TEXT = (  # shortlist.md:23-27, pasted unchanged
    "## POSITIVE (exact definition, all three required)\nA. **OOS expectancy.** Split by calendar time: the last third of the available sessions is the test set, sealed until design is frozen and the prereg doc is committed. On test-set trades only: mean net return per trade (after the cost model) > 0, and the 95% bootstrap CI excludes 0. The bootstrap resamples **whole entry weeks** (clustered; trades opened the same week are not independent), 10,000 draws, percentile CI. Report beside it: win rate, stop-out rate, median trade, top-1% share of total return (tail check).\nB. **Placebo fails to reproduce.** For each test-set trade, draw a random entry date for the SAME name within the same calendar month that the strategy was eligible to trade (passes the same liquidity floor), apply the SAME holding/exit rule and costs; 1,000 placebo sets. The strategy passes only if (strategy minus placebo-mean) per-trade expectancy has a clustered 95% CI excluding 0 AND the strategy beats >= 95% of the placebo sets. A placebo that is also positive means the return is market/name beta, not the rule.\nC. **Deflated Sharpe Ratio >= 0.95**, with N = every variant tried in this lab across ALL candidates (not per candidate), using the per-trade (or per-rebalance) return series' skew and kurtosis; PSR (benchmark SR 0) reported beside it. The trial count is written in the prereg log before each run; it never resets.\nAnything short of A+B+C = not positive. A pass on survivor-biased data is labelled provisional.")
RUN_SMOKE = ("docker run --rm --cpus 4 --memory 3g --network cheetah-market-app_default "
             "-e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York "
             "-e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 "
             "-v /Users/ajay/clinet-test/wt-stratlab/backend:/app:ro "
             "-v cheetah-market-app_cheetah-scans:/root/.cheetah:ro -v <S>:/strat -w /strat "
             "cheetah-api:latest python -u /app/scripts/strategy_lab_2026_10_29.py "
             "--candidate c5_reversal --smoke --out /strat/out/c5_reversal/smoke")
RUN_CALIBRATE = RUN_SMOKE.replace(
    "--smoke --out /strat/out/c5_reversal/smoke",
    "--calibrate --as-of 2026-10-29 --oos-from 2026-03-20 --out /strat/out/c5_reversal/calibration")
RUN_OUTCOME = RUN_SMOKE.replace(
    "-v <S>:/strat",
    "-v /Users/ajay/clinet-test/wt-stratlab/docs:/docs:ro "
    "-v /Users/ajay/clinet-test/eod-audits/research:/research -v <S>:/strat").replace(
    "--smoke --out /strat/out/c5_reversal/smoke",
    "--as-of 2026-10-29 --oos-from 2026-03-20 "
    "--prereg /docs/research/strategy_lab_2026_10_29_prereg.md --prereg-commit HASH "
    "--ledger /research/strategy_lab_ledger.json --out /strat/out/c5_reversal")
RUN_BY_MODE = {"smoke": RUN_SMOKE, "calibrate": RUN_CALIBRATE, "outcome": RUN_OUTCOME}

_Z975 = NormalDist().inv_cdf(1 - (100 - CI_PCT) / 200)
_Z80 = NormalDist().inv_cdf(0.80)
_TIME, _LATE, _DATA_END = 0, 1, 2


class LeakError(AssertionError):
    """A signal window that reads a bar at or after its own entry."""


class FetchRefused(RuntimeError):
    """A network path reached while the lab is read-only."""


class NaNGateError(ValueError):
    """A NaN reached a statistic or an artefact."""


class SettlementError(AssertionError):
    """Cash reused before it settled (T+1)."""


assert BOOK_SLEEVES == C5_HOLD + SETTLE_SESSIONS


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------
def _refuse_fetch(name):
    def _raise(*a, **k):
        ATTEMPTED_FETCHES.append(name)
        raise FetchRefused(f"{name} refused: the strategy lab is read-only")
    return _raise


_NET_TARGETS = (
    (prices, "_fetch_massive", "prices._fetch_massive"),
    (prices, "load_prices", "prices.load_prices"),
    (scanner, "fetch_type_map", "scanner.fetch_type_map"),
    (scanner, "ensure_type_map", "scanner.ensure_type_map"),
    (levered_etf, "ensure_async", "levered_etf.ensure_async"),
)


def block_network() -> None:
    """Every fetch path this process could reach -> FetchRefused, recorded."""
    import requests
    for mod, attr, name in _NET_TARGETS:
        if hasattr(mod, attr):
            setattr(mod, attr, _refuse_fetch(name))
    requests.Session.request = _refuse_fetch("requests.Session.request")
    requests.request = _refuse_fetch("requests.request")
    for verb in ("get", "post", "put", "delete", "head", "patch"):
        setattr(requests, verb, _refuse_fetch(f"requests.{verb}"))


def key_present() -> bool:
    return bool(massive_keys.stocks_key())


def _repo_roots() -> list:
    here = Path(__file__).resolve()
    roots = [here.parents[1]]
    top = here.parents[2]
    if top != Path(top.anchor) and (top / "backend").is_dir():
        roots.append(top)
    return roots


def out_inside_repo(out: Path) -> bool:
    o = Path(out).resolve()
    for r in _repo_roots():
        try:
            o.relative_to(r)
            return True
        except ValueError:
            continue
    return False


def ledger_refusal(path) -> Optional[str]:
    """None when `path` is the durable research ledger, else the refusal sentence: the path must
    equal `LEDGER_PATH`, sit outside `REFUSED_LEDGER_ROOTS`, and its directory must already
    exist (the mount) — the lab never creates it."""
    s = str(path)
    if s != LEDGER_PATH:
        return f"--ledger must be {LEDGER_PATH} (the mounted research ledger), not {s}."
    p = str(Path(path).resolve())
    if any(p == r or p.startswith(r + "/") or s.startswith(r + "/") for r in REFUSED_LEDGER_ROOTS):
        return "--ledger under /tmp is not durable; use the research ledger path."
    if not Path(path).parent.is_dir():
        return (f"{Path(path).parent} does not exist (the research dir is not mounted); the "
                "ledger is never created here.")
    return None


def _ledger_refused(path) -> bool:
    return ledger_refusal(path) is not None


# ---------------------------------------------------------------------------
# reads (Mongo, never a fetch)
# ---------------------------------------------------------------------------
def all_cached_symbols(coll=None) -> list:
    coll = coll if coll is not None else prices._get_mongo()
    if coll is None:
        return []
    return sorted({str(s).upper() for s in coll.distinct("symbol") if s})


def type_map(db=None) -> dict:
    """ONE find_one on the gajjala state doc `types` -> {as_of, complete, types{SYM: type}}."""
    empty = {"as_of": None, "complete": False, "types": {}}
    try:
        if db is None:
            coll = prices._get_mongo()
            db = coll.database if coll is not None else None
        if db is None:
            return empty
        doc = db[GSTORE.STATE].find_one({"_id": TYPES_STATE_ID}) or {}
        pairs = doc.get("pairs") or []
        types = {str(p[0]).upper(): str(p[1]) for p in pairs
                 if isinstance(p, (list, tuple)) and len(p) == 2 and p[0] and p[1]}
        if not types and isinstance(doc.get("types"), dict):
            types = {str(k).upper(): str(v) for k, v in doc["types"].items() if k and v}
        return {"as_of": doc.get("as_of"), "complete": bool(doc.get("complete")), "types": types}
    except Exception:                                           # noqa: BLE001
        return empty


def fund_symbols(syms, *, static_fn=None, cached_fn=None, levered_fn=None, types=None,
                 resolve_fn=None, db=None) -> dict:
    """{reason: set(symbols)} for the six exclusion reasons (first matching reason wins) plus
    `kept_unknown_type`. Unknown-type names are KEPT (dead names); share classes are KEPT;
    `symbols.DELISTED` is NOT applied."""
    syms = [str(s).upper() for s in syms]
    static = {str(s).upper() for s in ((static_fn or fallen_tab._static_etfs)() or ())}
    cached = {str(s).upper() for s in ((cached_fn or etf_info.cached_etf_set)(syms) or ())}
    lev_state = (levered_fn or levered_etf.load)(ensure=False, db=db) or {}
    levered = set()
    for items in ((lev_state.get("by_underlying") or {}) if isinstance(lev_state, dict)
                  else {}).values():
        for it in items or []:
            if isinstance(it, dict) and it.get("etf"):
                levered.add(str(it["etf"]).upper())
    types = types or {}
    resolve = resolve_fn or symbols.resolve
    out = {r: set() for r in EXCLUSION_REASONS}
    out["kept_unknown_type"] = set()
    for s in syms:
        ty = scanner.row_type(resolve(s), types)
        if ty == GC.SCAN_UNKNOWN_TYPE:
            ty = scanner.row_type(s, types)
        if s.startswith("^"):
            out["index_caret"].add(s)
        elif s in static:
            out["static_etf"].add(s)
        elif s in cached:
            out["cached_etf"].add(s)
        elif s in levered:
            out["levered_fund"].add(s)
        elif s.endswith(CRYPTO_SUFFIX):
            out["crypto_pair"].add(s)
        elif ty not in GC.SCAN_INSTRUMENT_TYPES and ty != GC.SCAN_UNKNOWN_TYPE:
            out["type_not_equity"].add(s)
        elif ty == GC.SCAN_UNKNOWN_TYPE:
            out["kept_unknown_type"].add(s)
    return out


def canonical_dedupe(frames: dict, resolve_fn=None) -> tuple:
    """Two docs that resolve to one canonical name -> keep the doc with the later last bar."""
    resolve = resolve_fn or symbols.resolve
    best: dict = {}
    for sym, fr in frames.items():
        if fr is None or len(fr) == 0:
            continue
        can = resolve(sym)
        last = pd.Timestamp(fr.index[-1])
        cur = best.get(can)
        if cur is None or last > cur[1] or (last == cur[1] and sym == can):
            best[can] = (sym, last)
    kept = {v[0] for v in best.values()}
    merged = sum(1 for s, fr in frames.items() if fr is not None and len(fr) and s not in kept)
    return {s: frames[s] for s in frames if s in kept}, merged


def _last_iso(fr) -> str:
    return RS.frame_days(fr.iloc[-1:])[0]


def docs_stopped_split(frames: dict, *, as_of: str, oos_from: str, types: dict) -> dict:
    """Disjoint buckets by the doc's last bar: ended_before_oos (< oos_from),
    ended_before_2026_05 (oos_from .. 2026-04-30), and among later docs stale at as_of
    (`prices.is_stale`, STOPPED_SESSIONS) split by presence in today's active type map."""
    out = {"ended_before_2026_05": 0, "ended_before_oos": 0, "stopped_in_oos_active": 0,
           "stopped_in_oos_not_active": 0}
    asof = pd.Timestamp(as_of)
    types = types or {}
    for sym, fr in frames.items():
        if fr is None or len(fr) == 0:
            continue
        last = _last_iso(fr)
        if last < oos_from:
            out["ended_before_oos"] += 1
        elif last < DOCS_END_LABEL_DATE:
            out["ended_before_2026_05"] += 1
        elif prices.is_stale(fr, asof, max_trading_days=STOPPED_SESSIONS):
            active = (sym in types) or (symbols.resolve(sym) in types)
            out["stopped_in_oos_active" if active else "stopped_in_oos_not_active"] += 1
    return out


def load_frames(*, frames_fn=None, symbols_fn=None, types_fn=None, stride=None) -> tuple:
    """(frames {SYM: frame}, meta {types, symbols_n, stride}) — ONE bulk read of the cache."""
    syms = list((symbols_fn or all_cached_symbols)())
    syms = sorted({str(s).upper() for s in syms if s})
    if stride and stride > 1:
        syms = sorted(set(syms[::int(stride)]) | {BENCH})
    elif BENCH not in syms:
        syms.append(BENCH)
    frames = (frames_fn or prices.bulk_cached_frames)(syms) or {}
    tm = (types_fn or type_map)() or {}
    return frames, {"types": tm, "symbols_n": len(syms), "stride": stride}


# ---------------------------------------------------------------------------
# panel
# ---------------------------------------------------------------------------
def build_panel(frames: dict, days: list) -> dict:
    syms = sorted(frames)
    n, m = len(syms), len(days)
    cols = ("open", "high", "low", "close", "volume")
    out = {c: np.full((n, m), np.nan) for c in cols}
    for i, s in enumerate(syms):
        a = RS.aligned(frames[s], days)
        for c in cols:
            out[c][i] = a[c]
    out["syms"] = syms
    out["sym_arr"] = np.array(syms, dtype=str) if syms else np.array([], dtype=str)
    out["days"] = list(days)
    return out


def seal_panel(panel: dict, idx_oos: int) -> dict:
    """Columns [0, idx_oos]; close/high/low/volume at idx_oos -> NaN (only that open survives)."""
    k = int(idx_oos) + 1
    out = {kk: v for kk, v in panel.items() if not kk.startswith("_")}
    for c in ("open", "high", "low", "close", "volume"):
        a = np.array(panel[c][:, :k], dtype=float, copy=True)
        if c != "open" and a.shape[1]:
            a[:, -1] = np.nan
        out[c] = a
    for c in ("bench_open", "bench_close"):
        if c in panel:
            b = np.array(panel[c][:k], dtype=float, copy=True)
            if c == "bench_close" and b.size:
                b[-1] = np.nan
            out[c] = b
    out["days"] = list(panel["days"][:k])
    return out


_GLITCH = np.frompyfunc(prices._is_scale_glitch, 2, 1)


def _prev_own_close(close: np.ndarray) -> np.ndarray:
    ff = pd.DataFrame(close).ffill(axis=1).to_numpy()
    prev = np.full_like(ff, np.nan)
    if ff.shape[1] > 1:
        prev[:, 1:] = ff[:, :-1]
    return prev


def glitch_pairs(panel: dict) -> np.ndarray:
    """bool (n_sym, n_days): True at k when (close[k], prev own close) or (open[k], prev own
    close) is a `prices._is_scale_glitch` pair."""
    close, opn = panel["close"], panel["open"]
    prev = _prev_own_close(close)
    out = np.zeros(close.shape, dtype=bool)
    for cur in (close, opn):
        ok = np.isfinite(cur) & np.isfinite(prev)
        if ok.any():
            out[ok] |= _GLITCH(cur[ok], prev[ok]).astype(bool)
    return out


def _aux(panel: dict) -> dict:
    a = panel.get("_aux")
    if a is not None:
        return a
    opn, close = panel["open"], panel["close"]
    n = close.shape[1]
    idx = np.arange(n)
    with np.errstate(invalid="ignore"):
        vo = np.isfinite(opn) & (opn > 0)
    nxt = np.where(vo, idx[None, :], n)
    nxt = np.minimum.accumulate(nxt[:, ::-1], axis=1)[:, ::-1] if n else nxt
    prv = np.where(np.isfinite(close), idx[None, :], -1)
    prv = np.maximum.accumulate(prv, axis=1) if n else prv
    g = glitch_pairs(panel)
    a = {"nxt_open": nxt, "prv_close": prv, "glitch": g, "gcs": _cumcount(g)}
    panel["_aux"] = a
    return a


def _cumcount(g: np.ndarray) -> np.ndarray:
    return np.concatenate([np.zeros((g.shape[0], 1), dtype=np.int64),
                           np.cumsum(g, axis=1, dtype=np.int64)], axis=1)


def own_bar_rolling(x, valid, n, how) -> np.ndarray:
    """Per (s, t): `how` (mean | median) of x over the last n own bars at or before t; NaN with
    fewer than n own bars."""
    x = np.asarray(x, dtype=float)
    valid = np.asarray(valid, dtype=bool)
    out = np.full(x.shape, np.nan)
    for i in range(x.shape[0]):
        pos = np.flatnonzero(valid[i])
        if len(pos) < n:
            continue
        v = x[i, pos]
        if how == "mean":
            c = np.concatenate([[0.0], np.cumsum(v)])
            stat = (c[n:] - c[:-n]) / n
        elif how == "median":
            stat = np.median(np.lib.stride_tricks.sliding_window_view(v, n), axis=1)
        else:
            raise ValueError(how)
        out[i, pos[n - 1:]] = stat
        row = pd.Series(out[i]).ffill().to_numpy()
        row[:pos[n - 1]] = np.nan
        out[i] = row
    return out


def liquidity_panel(panel: dict) -> dict:
    close, vol = panel["close"], panel["volume"]
    own = np.isfinite(close) & np.isfinite(vol)
    dv = np.where(own, close * np.where(own, vol, 0.0), np.nan)
    mean_liq = own_bar_rolling(dv, own, LIQ_PERIOD, "mean")
    mdv50 = own_bar_rolling(dv, own, C5_RANK_BARS, "median")
    mdv20 = own_bar_rolling(dv, own, CAP_MDV_BARS, "median")
    with np.errstate(invalid="ignore"):
        liquid = np.isfinite(mean_liq) & (mean_liq >= LIQ_MIN_DV)
    n_sym, n_days = close.shape
    rank = np.zeros((n_sym, n_days), dtype=np.int32)
    sym_order = np.argsort(np.argsort(panel["sym_arr"], kind="stable"), kind="stable") \
        if n_sym else np.zeros(0, dtype=int)
    for t in range(n_days):
        elig = np.flatnonzero(liquid[:, t] & np.isfinite(close[:, t]) & np.isfinite(mdv50[:, t]))
        if not len(elig):
            continue
        order = elig[np.lexsort((sym_order[elig], -mdv50[elig, t]))]
        rank[order, t] = np.arange(1, len(order) + 1, dtype=np.int32)
    return {"liquid": liquid, "mean_dv": mean_liq, "mdv50": mdv50, "mdv20": mdv20, "rank": rank}


# ---------------------------------------------------------------------------
# signal
# ---------------------------------------------------------------------------
def signal_window(t, k=C5_R_LOOKBACK) -> range:
    return range(t - k + SIGNAL_OFFSET, t + 1 + SIGNAL_OFFSET)


def check_no_leak(t, window, entry_idx) -> None:
    for i in window:
        if i >= entry_idx:
            raise LeakError(f"signal window for t={t} reads index {i} >= entry {entry_idx}")


def r_lookback(close, t, k=C5_R_LOOKBACK, glitch=None) -> np.ndarray:
    """close[w_end]/close[w_start] - 1 over `signal_window(t, k)`; NaN unless all k+1 closes are
    finite and no adjacent pair inside the window is a scale glitch."""
    w = list(signal_window(t, k))
    c = close[:, w]
    with np.errstate(invalid="ignore", divide="ignore"):
        r = c[:, -1] / c[:, 0] - 1.0
    ok = np.isfinite(c).all(axis=1)
    if glitch is not None and len(w) > 1:
        ok &= ~glitch[:, w[1:]].any(axis=1)
    return np.where(ok, r, np.nan)


def signal_sessions(n_days) -> list:
    return list(range(FIRST_SIGNAL_IDX, int(n_days) - 1 - C5_HOLD))


def _week_monday(iso: str) -> str:
    d = date.fromisoformat(iso)
    return (d - timedelta(days=d.weekday())).isoformat()


def split_sessions(S, days, oos_from) -> dict:
    S = list(S)
    rule_k = (len(S) * (OOS_DEN - OOS_NUM)) // OOS_DEN
    rule = days[S[rule_k]] if S else None
    oos_from = oos_from or rule
    if oos_from not in days or days.index(oos_from) not in set(S):
        raise ValueError(f"--oos-from {oos_from} is not a signal date on this calendar")
    idx = days.index(oos_from)
    oos = [t for t in S if t >= idx]
    is_ = [t for t in S if t + 1 + C5_HOLD <= idx]
    emb = [t for t in S if t < idx and t + 1 + C5_HOLD > idx]
    weeks = sorted({_week_monday(days[t + 1]) for t in oos})
    return {"oos_from": oos_from, "oos_from_rule": rule, "idx_oos": idx, "oos": oos, "is": is_,
            "embargo": emb, "is_n": len(is_), "embargo_n": len(emb), "oos_n": len(oos),
            "oos_last": days[oos[-1]] if oos else None, "oos_weeks": len(weeks)}


def c5_universe(liq, t) -> np.ndarray:
    r = liq["rank"][:, t]
    u = np.flatnonzero((r >= 1) & (r <= C5_UNIVERSE_TOP_N))
    return u[np.argsort(r[u], kind="stable")]


def _select_detail(panel, liq, t):
    a = _aux(panel)
    u = c5_universe(liq, t)
    check_no_leak(t, signal_window(t), t + 1)
    r5 = r_lookback(panel["close"], t, glitch=a["glitch"])
    raw = r_lookback(panel["close"], t, glitch=None)
    n_glitch = int(np.sum(np.isfinite(raw[u]) & ~np.isfinite(r5[u]))) if len(u) else 0
    if not len(u):
        return np.zeros(0, dtype=int), u, r5, n_glitch
    ok = np.isfinite(r5[u])
    cand = u[ok]
    if not len(cand):
        return np.zeros(0, dtype=int), u, r5, n_glitch
    bins = RS.quantile_bins(r5[cand], C5_BINS, tiebreak=panel["sym_arr"][cand])
    return cand[bins == 0], u, r5, n_glitch


def c5_select(panel, liq, t) -> list:
    return [int(s) for s in _select_detail(panel, liq, t)[0]]


def cost_side(rank) -> float:
    bps = COST_TIER1_BPS if int(rank) <= COST_TIER1_TOP_N else COST_TIER2_BPS
    return (bps + SLIPPAGE_BPS) / 1e4


def _cost_tier(rank) -> int:
    return 1 if int(rank) <= COST_TIER1_TOP_N else 2


def _outcomes(panel, sidx, t, hold, glitch=None) -> Optional[dict]:
    """Vectorized outcome for symbol indices `sidx` signalled at t (the ONE engine)."""
    a = _aux(panel)
    n = panel["close"].shape[1]
    e = t + 1
    sidx = np.asarray(sidx, dtype=int)
    if e >= n or not len(sidx):
        return None
    opn, close = panel["open"], panel["close"]
    oe, ce = opn[sidx, e], close[sidx, e]
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(oe) & (oe > 0) & np.isfinite(ce)
    x_nom = t + 1 + hold
    x = a["nxt_open"][sidx, x_nom] if x_nom < n else np.full(len(sidx), n)
    reason = np.where(x == x_nom, _TIME, np.where(x < n, _LATE, _DATA_END))
    x_de = a["prv_close"][sidx, min(x_nom - 1, n - 1)]
    x = np.where(reason == _DATA_END, x_de, x)
    x = np.clip(x, e, n - 1)
    exit_px = np.where(reason == _DATA_END, close[sidx, x], opn[sidx, x])
    gcs = a["gcs"] if glitch is None else _cumcount(np.asarray(glitch, dtype=bool))
    g_hold = (gcs[sidx, x + 1] - gcs[sidx, e]) > 0
    return {"ok": ok, "e": e, "x": x, "reason": reason, "entry_px": oe, "exit_px": exit_px,
            "glitch_hold": g_hold}


def _net(entry_px, exit_px, c):
    return exit_px * (1 - c) / (entry_px * (1 + c)) - 1


def trade_outcome(panel, s, t, rank, hold=C5_HOLD, glitch=None) -> Optional[dict]:
    """One (s, t) through the vectorized engine -> outcome dict (a >= 5x jump inside the hold
    is KEPT, `glitch_hold` True), or {"skip_reason": "no_entry_bar"}; None when t has no entry
    session."""
    o = _outcomes(panel, [s], t, hold, glitch=glitch)
    if o is None:
        return None
    if not o["ok"][0]:
        return {"skip_reason": "no_entry_bar"}
    days = panel["days"]
    x = int(o["x"][0])
    ep, xp = float(o["entry_px"][0]), float(o["exit_px"][0])
    c = cost_side(rank)
    reason = EXIT_REASONS[int(o["reason"][0])]
    mae, mfe = _mae_mfe(panel, s, o["e"], x, reason, ep, xp)
    return {"sym": panel["syms"][s], "s": int(s), "t": int(t), "signal_date": days[t],
            "entry_date": days[o["e"]], "exit_date": days[x], "e": int(o["e"]), "x": x,
            "entry_px": ep, "exit_px": xp, "gross_ret": xp / ep - 1, "net_ret": _net(ep, xp, c),
            "cost_side": c, "cost_tier": _cost_tier(rank), "exit_reason": reason,
            "mae_pct": mae, "mfe_pct": mfe, "glitch_hold": bool(o["glitch_hold"][0]),
            "entry_week": _week_monday(days[o["e"]])}


def _mae_mfe(panel, s, e, x, reason, ep, xp):
    hi = x + 1 if reason == "data_end" else x
    lows = panel["low"][s, e:hi]
    highs = panel["high"][s, e:hi]
    lo = np.nanmin(np.append(lows[np.isfinite(lows)], xp))
    hh = np.nanmax(np.append(highs[np.isfinite(highs)], xp))
    return float((lo / ep - 1) * 100), float((hh / ep - 1) * 100)


def universe_cohort(panel, liq, sessions, split) -> pd.DataFrame:
    """Every (s, t) with s in U_t that has an outcome, flag `selected` (bottom decile).
    `split` = a label or {t: label}. Skips land in `.attrs["skips"]` / `.attrs["cohort_skips"]`."""
    days = panel["days"]
    cols = {k: [] for k in ("s", "t", "e", "x", "reason", "entry_px", "exit_px", "rank", "r5",
                            "selected", "mdv20", "glitch_hold")}
    skips: dict = {}
    cskips: dict = {}
    flags: dict = {}
    cflags: dict = {}

    def _bump(d, lab, key, n, keys=SKIP_REASONS):
        if n:
            d.setdefault(lab, {r: 0 for r in keys})[key] += int(n)
    for t in sessions:
        lab = split.get(t) if isinstance(split, dict) else split
        sel, u, r5, n_gl = _select_detail(panel, liq, t)
        if not len(u):
            continue
        _bump(cskips, lab, "scale_glitch_signal", n_gl)
        o = _outcomes(panel, u, t, C5_HOLD)
        if o is None:
            continue
        is_sel = np.isin(u, sel)
        no_entry = ~o["ok"]
        g_hold = o["ok"] & o["glitch_hold"]
        _bump(cskips, lab, "no_entry_bar", no_entry.sum())
        _bump(cflags, lab, "scale_glitch_hold", g_hold.sum(), FLAG_REASONS)
        _bump(skips, lab, "no_entry_bar", (no_entry & is_sel).sum())
        _bump(flags, lab, "scale_glitch_hold", (g_hold & is_sel).sum(), FLAG_REASONS)
        keep = o["ok"]
        if not keep.any():
            continue
        uk = u[keep]
        cols["s"].append(uk)
        cols["t"].append(np.full(len(uk), t))
        cols["e"].append(np.full(len(uk), o["e"]))
        cols["x"].append(o["x"][keep])
        cols["reason"].append(o["reason"][keep])
        cols["entry_px"].append(o["entry_px"][keep])
        cols["exit_px"].append(o["exit_px"][keep])
        cols["rank"].append(liq["rank"][uk, t])
        cols["r5"].append(r5[uk])
        cols["selected"].append(is_sel[keep])
        cols["mdv20"].append(liq["mdv20"][uk, t])
        cols["glitch_hold"].append(o["glitch_hold"][keep])
    if not cols["s"]:
        df = pd.DataFrame(columns=_COHORT_COLS)
    else:
        arr = {k: np.concatenate(v) for k, v in cols.items()}
        ranks = arr["rank"].astype(int)
        c = np.array([cost_side(r) for r in ranks]) if len(ranks) else np.zeros(0)
        tier = np.array([_cost_tier(r) for r in ranks]) if len(ranks) else np.zeros(0, int)
        t_arr = arr["t"].astype(int)
        e_arr = arr["e"].astype(int)
        x_arr = arr["x"].astype(int)
        df = pd.DataFrame({
            "sym": panel["sym_arr"][arr["s"].astype(int)], "s": arr["s"].astype(int),
            "t": t_arr, "e": e_arr, "x": x_arr,
            "signal_date": [days[i] for i in t_arr], "entry_date": [days[i] for i in e_arr],
            "exit_date": [days[i] for i in x_arr],
            "entry_px": arr["entry_px"], "exit_px": arr["exit_px"],
            "gross_ret": arr["exit_px"] / arr["entry_px"] - 1,
            "net_ret": _net(arr["entry_px"], arr["exit_px"], c),
            "cost_side": c, "cost_tier": tier, "r5": arr["r5"],
            "r5_ok": np.isfinite(arr["r5"]), "mdv50_rank": ranks, "mdv20": arr["mdv20"],
            "exit_reason": [EXIT_REASONS[int(r)] for r in arr["reason"]],
            "selected": arr["selected"].astype(bool),
            "glitch_hold": arr["glitch_hold"].astype(bool)})
        df["split"] = [(split.get(int(t)) if isinstance(split, dict) else split) for t in t_arr]
        wk = {d: _week_monday(d) for d in set(df["entry_date"])}
        df["entry_week"] = df["entry_date"].map(wk)
        df["month"] = df["signal_date"].str[:7]
        df["cohort_n"] = df.groupby("t")["selected"].transform("sum").astype(int)
    for lab in set(skips) | set(cskips) | set(flags) | set(cflags):
        skips.setdefault(lab, {r: 0 for r in SKIP_REASONS})
        cskips.setdefault(lab, {r: 0 for r in SKIP_REASONS})
        flags.setdefault(lab, {r: 0 for r in FLAG_REASONS})
        cflags.setdefault(lab, {r: 0 for r in FLAG_REASONS})
        skips[lab]["scale_glitch_signal"] = cskips[lab]["scale_glitch_signal"]
    df = df.reset_index(drop=True)
    df.attrs["skips"] = skips
    df.attrs["cohort_skips"] = cskips
    df.attrs["flags"] = flags
    df.attrs["cohort_flags"] = cflags
    return df


_COHORT_COLS = ["sym", "s", "t", "e", "x", "signal_date", "entry_date", "exit_date", "entry_px",
                "exit_px", "gross_ret", "net_ret", "cost_side", "cost_tier", "r5", "r5_ok",
                "mdv50_rank", "mdv20", "exit_reason", "selected", "glitch_hold", "split",
                "entry_week", "month", "cohort_n"]
TRADE_KEYS = ("trial_id", "sym", "signal_date", "entry_date", "exit_date", "entry_px", "exit_px",
              "gross_ret", "net_ret", "cost_side", "cost_tier", "r5", "mdv50_rank", "mdv20",
              "cohort_n", "r_multiple", "mae_pct", "mfe_pct", "exit_reason", "glitch_hold", "split",
              "entry_week")


def trades_from_cohort(panel, cohort: pd.DataFrame, trial_id="T01") -> pd.DataFrame:
    tr = cohort[cohort["selected"].astype(bool)].copy() if len(cohort) else cohort.copy()
    tr["row"] = tr.index.to_numpy()
    tr = tr.reset_index(drop=True)
    tr["trial_id"] = trial_id
    tr["r_multiple"] = None
    mae, mfe = [], []
    for s, e, x, rsn, ep, xp in zip(tr["s"], tr["e"], tr["x"], tr["exit_reason"],
                                    tr["entry_px"], tr["exit_px"]):
        a, b = _mae_mfe(panel, int(s), int(e), int(x), rsn, float(ep), float(xp))
        mae.append(a)
        mfe.append(b)
    tr["mae_pct"] = mae
    tr["mfe_pct"] = mfe
    return tr


def c5_rows(panel, liq, sessions_by_split: dict, trial_id="T01") -> tuple:
    """(cohort, trades) over {label: [t, ...]}."""
    split = {}
    sessions = []
    for lab, ts in sessions_by_split.items():
        for t in ts:
            split[int(t)] = lab
            sessions.append(int(t))
    cohort = universe_cohort(panel, liq, sorted(sessions), split)
    return cohort, trades_from_cohort(panel, cohort, trial_id)


# ---------------------------------------------------------------------------
# book, settlement, capacity
# ---------------------------------------------------------------------------
def check_settlement(schedule: pd.DataFrame, sleeves: int = BOOK_SLEEVES) -> None:
    """Every cash transfer (sale -> buy) must have sale_idx + SETTLE_SESSIONS <= buy_idx."""
    if schedule is None or len(schedule) == 0:
        return
    bad = schedule[schedule["sale_idx"].astype(int) + SETTLE_SESSIONS
                   > schedule["buy_idx"].astype(int)]
    if len(bad):
        r = bad.iloc[0]
        raise SettlementError(f"sleeve {int(r['sleeve'])} of {sleeves}: a sale at index "
                              f"{int(r['sale_idx'])} ({r.get('reason')}) funds a buy at "
                              f"{int(r['buy_idx'])} before it settles")


def _simulate_book(trades, panel, n_days, sleeves, net: bool):
    close = panel["close"]
    a = _aux(panel)
    rows = trades.reset_index(drop=True)
    by_entry: dict = {}
    for i, e in enumerate(rows["e"].astype(int)):
        by_entry.setdefault(e, []).append(i)
    exits_open: dict = {}
    exits_close: dict = {}
    for i, (x, rsn) in enumerate(zip(rows["x"].astype(int), rows["exit_reason"])):
        (exits_close if rsn == "data_end" else exits_open).setdefault(x, []).append(i)
    cash = {k: [{"amount": 1.0 / sleeves, "sale_idx": -10 ** 9, "reason": "initial"}]
            for k in range(sleeves)}
    shares = np.zeros(len(rows))
    sleeve_of = np.zeros(len(rows), dtype=int)
    open_pos: set = set()
    transfers = []
    d0 = int(rows["e"].min())
    d1 = int(rows["x"].max())
    out = []
    v_prev = 1.0
    for d in range(d0, d1 + 1):
        for i in exits_open.get(d, []):
            if i in open_pos:
                c = rows.at[i, "cost_side"] if net else 0.0
                cash[sleeve_of[i]].append({"amount": shares[i] * rows.at[i, "exit_px"] * (1 - c),
                                           "sale_idx": d, "reason": rows.at[i, "exit_reason"]})
                open_pos.discard(i)
        if d in by_entry:
            k = d % sleeves
            fund, keep = 0.0, []
            for it in cash[k]:
                if it["reason"] in ("time", "initial") or it["sale_idx"] + SETTLE_SESSIONS <= d:
                    fund += it["amount"]
                    transfers.append({"sleeve": k, "sale_idx": it["sale_idx"], "buy_idx": d,
                                      "reason": it["reason"]})
                else:
                    keep.append(it)
            cash[k] = keep
            ids = by_entry[d]
            alloc = fund / len(ids)
            for i in ids:
                c = rows.at[i, "cost_side"] if net else 0.0
                shares[i] = alloc / (rows.at[i, "entry_px"] * (1 + c))
                sleeve_of[i] = k
                open_pos.add(i)
        for i in exits_close.get(d, []):
            if i in open_pos:
                c = rows.at[i, "cost_side"] if net else 0.0
                cash[sleeve_of[i]].append({"amount": shares[i] * rows.at[i, "exit_px"] * (1 - c),
                                           "sale_idx": d, "reason": "data_end"})
                open_pos.discard(i)
        v = sum(it["amount"] for k in cash for it in cash[k])
        for i in open_pos:
            s = int(rows.at[i, "s"])
            j = a["prv_close"][s, d]
            v += shares[i] * (close[s, j] if j >= 0 else rows.at[i, "entry_px"])
        busy = {int(sleeve_of[i]) for i in open_pos}
        out.append((d, v / v_prev - 1, len(open_pos), len({int(rows.at[i, "e"]) for i in open_pos}),
                    sleeves - len(busy)))
        v_prev = v
    return out, pd.DataFrame(transfers, columns=["sleeve", "sale_idx", "buy_idx", "reason"])


def daily_book(trades, panel, days, hold=C5_HOLD, sleeves=BOOK_SLEEVES) -> pd.DataFrame:
    """BOOK_SLEEVES sleeves of 1/sleeves capital; the cohort entering at open e uses sleeve
    e mod sleeves, equal weight; T+1 settlement checked. Descriptive only."""
    cols = ["date", "split", "book_gross", "book_net", "n_positions", "n_cohorts",
            "n_sleeves_idle", "spy_ret"]
    if trades is None or len(trades) == 0:
        return pd.DataFrame(columns=cols)
    n_days = len(days)
    g, sched_g = _simulate_book(trades, panel, n_days, sleeves, net=False)
    nt, sched_n = _simulate_book(trades, panel, n_days, sleeves, net=True)
    check_settlement(sched_n, sleeves)
    check_settlement(sched_g, sleeves)
    bc = panel.get("bench_close")
    lab = trades["split"].iloc[0] if "split" in trades.columns else None
    rows = []
    for (d, rg, npos, ncoh, idle), (_d, rn, *_rest) in zip(g, nt):
        spy = None
        if bc is not None and d >= 1 and np.isfinite(bc[d]) and np.isfinite(bc[d - 1]):
            spy = float(bc[d] / bc[d - 1] - 1)
        rows.append({"date": days[d], "split": lab, "book_gross": float(rg), "book_net": float(rn),
                     "n_positions": npos, "n_cohorts": ncoh, "n_sleeves_idle": idle,
                     "spy_ret": spy})
    _ = hold
    return pd.DataFrame(rows, columns=cols)


def capacity_usd(trades, sleeves=BOOK_SLEEVES) -> Optional[float]:
    if trades is None or len(trades) == 0:
        return None
    cap = sleeves * trades["cohort_n"].astype(float) * CAP_PCT_OF_MDV / 100.0 \
        * trades["mdv20"].astype(float)
    cap = cap[np.isfinite(cap)]
    return float(cap.min()) if len(cap) else None


# ---------------------------------------------------------------------------
# statistics (PURE; percent units)
# ---------------------------------------------------------------------------
def assert_finite(x, what) -> np.ndarray:
    a = np.asarray(x, dtype=float)
    if not np.isfinite(a).all():
        raise NaNGateError(f"non-finite value reached {what}")
    return a


def _codes(clusters):
    _u, inv = np.unique(np.asarray(clusters).astype(str), return_inverse=True)
    return inv, len(_u)


def cluster_draws(x_pct, clusters, *, draws=BOOT_DRAWS, seed=SEED):
    inv, nc = _codes(clusters)
    num = np.bincount(inv, weights=x_pct, minlength=nc)
    w = np.bincount(inv, minlength=nc).astype(float)
    parts = []
    left, i = int(draws), 0
    while left > 0:
        k = min(BOOT_CHUNK, left)
        parts.append(RS.boot_draws([(num, w)], k, seed + i)[0])
        left -= k
        i += 1
    return (np.concatenate(parts) if parts else np.zeros(0)), nc


def cluster_mean_ci(x, clusters, *, draws=BOOT_DRAWS, seed=SEED) -> dict:
    """x in FRACTIONS -> percent; whole-cluster bootstrap via RS.boot_draws; word on the
    unrounded CI."""
    xp = assert_finite(x, "cluster_mean_ci") * 100.0
    n = len(xp)
    if n == 0:
        return {"mean_pct": None, "ci_pct": None, "ci_raw_pct": None, "word": "too_small",
                "n": 0, "n_clusters": 0}
    d, nc = cluster_draws(xp, clusters, draws=draws, seed=seed)
    ci_raw = RS.ci_of(d, dp=VERDICT_DP)
    return {"mean_pct": RS._r(float(xp.mean()), SHOW_DP), "ci_pct": RS.ci_of(d, dp=SHOW_DP),
            "ci_raw_pct": ci_raw, "word": RS.verdict(nc, ci_raw), "n": int(n),
            "n_clusters": int(nc)}


def _pool_index(cohort: pd.DataFrame, exclude_back: int) -> dict:
    """Per cohort row: its same-sym / same-month / same-split pool without signal index in
    [t - exclude_back, t - 1], as two contiguous segments of a sorted array."""
    n = len(cohort)
    key_df = pd.DataFrame({"a": cohort["sym"].astype(str), "b": cohort["month"].astype(str),
                           "c": cohort["split"].astype(str)})
    gid = key_df.groupby(["a", "b", "c"], sort=True).ngroup().to_numpy().astype(np.int64)
    t = cohort["t"].to_numpy().astype(np.int64)
    net = cohort["net_ret"].to_numpy().astype(float)
    big = int(t.max() if n else 0) + exclude_back + 10
    keys = gid * big + t
    order = np.argsort(keys, kind="stable")
    ks = keys[order]
    net_s = net[order]
    g0 = np.searchsorted(ks, gid * big, "left")
    g1 = np.searchsorted(ks, (gid + 1) * big, "left")
    lo = np.maximum(gid * big + t - exclude_back, gid * big)
    a = np.maximum(np.searchsorted(ks, lo, "left"), g0)
    b = np.searchsorted(ks, gid * big + t, "left")
    a = np.minimum(a, b)
    len1 = a - g0
    L = len1 + (g1 - b)
    cs = np.concatenate([[0.0], np.cumsum(net_s)])
    pool_mean = (cs[a] - cs[g0] + cs[g1] - cs[b]) / np.maximum(L, 1)
    return {"g0": g0, "a": a, "b": b, "len1": len1, "L": L, "net_s": net_s,
            "pool_mean": pool_mean}


def _placebo_core(rows, pidx, net_rows, sets, seed, chunk=100):
    rows = np.asarray(rows, dtype=int)
    n = len(rows)
    L = pidx["L"][rows]
    g0, b, len1 = pidx["g0"][rows], pidx["b"][rows], pidx["len1"][rows]
    rng = np.random.default_rng(seed)
    pj = []
    left = int(sets)
    while left > 0:
        k = min(chunk, left)
        u = rng.integers(0, L, size=(k, n))
        pos = np.where(u < len1, g0 + u, b + (u - len1))
        pj.append(pidx["net_s"][pos].mean(axis=1))
        left -= k
    pj = np.concatenate(pj) if pj else np.zeros(0)
    s_mean = float(np.mean(net_rows)) if n else float("nan")
    beat = float(np.mean(s_mean > pj)) if len(pj) else None
    d = np.asarray(net_rows, dtype=float) - pidx["pool_mean"][rows]
    return beat, d, L


def placebo(trades, cohort, *, sets=PLACEBO_SETS, seed=SEED + 1,
            exclude_back=PLACEBO_EXCLUDE_BACK, draws=BOOT_DRAWS, pidx=None) -> dict:
    """Gate B: per trade, the pool = cohort rows of the same symbol, calendar month and split,
    without signal index in [t - exclude_back, t - 1] (the trade's own row always stays)."""
    if trades is None or len(trades) == 0:
        return {"diff": cluster_mean_ci([], []), "beat_share": None, "pass": False, "n": 0,
                "pool_self_only_n": 0, "pool_p10": None, "pool_median": None}
    pidx = pidx if pidx is not None else _pool_index(cohort, exclude_back)
    rows = _trade_rows(trades, cohort)
    net = assert_finite(trades["net_ret"], "placebo")
    beat, d, L = _placebo_core(rows, pidx, net, sets, seed)
    diff = cluster_mean_ci(d, trades["entry_week"], draws=draws, seed=seed)
    ok = diff["word"] == "separates" and beat is not None and beat >= PLACEBO_BEAT_SHARE
    return {"diff": diff, "beat_share": RS._r(beat, 4), "pass": bool(ok), "n": int(len(rows)),
            "pool_self_only_n": int(np.sum(L == 1)), "pool_p10": float(np.percentile(L, 10)),
            "pool_median": float(np.median(L)), "exclude_back": int(exclude_back)}


def _trade_rows(trades, cohort) -> np.ndarray:
    if "row" in trades.columns:
        return trades["row"].to_numpy().astype(int)
    pos = {(s, int(t)): i for i, (s, t) in enumerate(zip(cohort["sym"], cohort["t"]))}
    return np.array([pos[(s, int(t))] for s, t in zip(trades["sym"], trades["t"])], dtype=int)


def gate_c_series(trades, kind=GATE_C_SERIES) -> np.ndarray:
    if trades is None or len(trades) == 0:
        return np.zeros(0)
    if kind == "per_trade":
        return assert_finite(trades["net_ret"], "gate_c_series") * 100.0
    if kind == "per_entry_day":
        g = trades.groupby("t", sort=True)["net_ret"].mean()
        return assert_finite(g.to_numpy(), "gate_c_series") * 100.0
    raise ValueError(f"unknown gate C series {kind}")


def moments(x) -> dict:
    a = assert_finite(x, "moments")
    n = len(a)
    if n < 3:
        return {"n": n, "sr": None, "skew": None, "kurt": None}
    sd = float(np.std(a, ddof=1))
    if not sd > 0:
        return {"n": n, "sr": None, "skew": None, "kurt": None}
    z = (a - a.mean()) / np.std(a)
    return {"n": n, "sr": float(a.mean() / sd), "skew": float(np.mean(z ** 3)),
            "kurt": float(np.mean(z ** 4))}


def psr(sr, sr0, n, skew, kurt) -> Optional[float]:
    if sr is None or n is None or n < 2:
        return None
    den = 1 - skew * sr + (kurt - 1) / 4.0 * sr * sr
    if not den > 0:
        return None
    return float(NormalDist().cdf((sr - sr0) * math.sqrt(n - 1) / math.sqrt(den)))


def dsr_sr0(trial_srs) -> float:
    srs = [float(s) for s in trial_srs if s is not None]
    N = len(srs)
    if N < 2:
        return 0.0
    sd = float(np.std(srs, ddof=1))
    nd = NormalDist()
    g = EULER_GAMMA
    return float(sd * ((1 - g) * nd.inv_cdf(1 - 1.0 / N) + g * nd.inv_cdf(1 - 1.0 / (N * math.e))))


def deflated(x, trial_srs) -> dict:
    m = moments(x)
    srs = list(trial_srs or [])
    if m["sr"] is not None and not srs:
        srs = [m["sr"]]
    sr0 = dsr_sr0(srs)
    if m["sr"] is None:
        return dict(m, sr0=sr0, psr0=None, dsr=None, N=len(srs))
    return dict(m, sr0=sr0, psr0=psr(m["sr"], 0.0, m["n"], m["skew"], m["kurt"]),
                dsr=psr(m["sr"], sr0, m["n"], m["skew"], m["kurt"]), N=len(srs))


def breakeven_cost_bps(trades) -> Optional[float]:
    """The per-side cost c solving mean net = 0 (exact for one cost tier): 1e4 * g / (2 + g)."""
    if trades is None or len(trades) == 0:
        return None
    g = float(np.mean(assert_finite(trades["gross_ret"], "breakeven")))
    if not g > 0:
        return None
    return float(1e4 * g / (2 + g))


def mde_pct(sd_week_pct, n_weeks) -> Optional[float]:
    if sd_week_pct is None or not n_weeks or n_weeks <= 0 or not math.isfinite(sd_week_pct):
        return None
    return float((_Z975 + _Z80) * sd_week_pct / math.sqrt(n_weeks))


def glitch_share_exceeded(n_flagged, n_rows) -> bool:
    """True when the flagged rows are more than `GLITCH_VERDICT_MAX_SHARE` of the trade rows."""
    n_rows = int(n_rows or 0)
    return n_rows > 0 and int(n_flagged or 0) > GLITCH_VERDICT_MAX_SHARE * n_rows


def positive_verdict(a, b, c, n_weeks, *, a_clean=None, b_clean=None, n_flagged=0,
                     n_rows=None) -> dict:
    """A and B must pass on all rows AND with the flagged rows removed (`a_clean`, `b_clean`;
    None = no flagged rows, the all-rows result stands); > 5% flagged -> `UNMEASURED_GLITCH`."""
    a_c = bool(a) if a_clean is None else bool(a_clean)
    b_c = bool(b) if b_clean is None else bool(b_clean)
    if glitch_share_exceeded(n_flagged, n_rows):
        word = UNMEASURED_GLITCH
    elif int(n_weeks or 0) < MIN_CLUSTERS:
        word = "TOO SMALL"
    elif a and b and c and a_c and b_c:
        word = "POSITIVE"
    else:
        word = "NOT POSITIVE"
    nr = int(n_rows or 0)
    return {"word": word, "A": bool(a), "B": bool(b), "C": bool(c), "A_clean": a_c,
            "B_clean": b_c, "n_flagged": int(n_flagged or 0), "n_rows": nr,
            "flagged_share": round(int(n_flagged or 0) / nr, 6) if nr else None,
            "n_weeks": int(n_weeks or 0),
            "label": SURVIVOR_LABEL if word == "POSITIVE" else None}


def verdict_of(g) -> dict:
    """The verdict for one `gate_block` result (the one wiring the outcome run uses)."""
    cl = g.get("clean") or {}
    return positive_verdict(g["A"].get("pass"), g["B"].get("pass"), g["C"].get("pass"),
                            g["A"].get("n_clusters"),
                            a_clean=(cl.get("A") or {}).get("pass"),
                            b_clean=(cl.get("B") or {}).get("pass"),
                            n_flagged=cl.get("n_flagged", 0), n_rows=cl.get("n_rows"))


def _wilson(k, n):
    if not n:
        return None, None
    p = k / n
    z = _Z975
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return round(max(0.0, mid - half), 4), round(min(1.0, mid + half), 4)


def _day_excess(trades, cohort) -> np.ndarray:
    mean_t = cohort.groupby("t")["net_ret"].mean()
    return trades["net_ret"].to_numpy() - trades["t"].map(mean_t).to_numpy()


def _week_sd_pct(trades) -> Optional[float]:
    if trades is None or len(trades) == 0:
        return None
    wk = (trades["net_ret"] * 100.0).groupby(trades["entry_week"]).mean()
    return float(wk.std(ddof=1)) if len(wk) > 1 else None


def calibrate_null(panel_is, liq, split, *, reps=CALIB_REPS, draws=BOOT_DRAWS,
                   placebo_sets=PLACEBO_SETS, seed=SEED + 2, rows=None,
                   budget_sec=CALIB_BUDGET_SEC) -> dict:
    """IS-only nulls: per IS signal session, the same COUNT as that day's trades drawn at random
    from the eligible cohort rows (U_t with finite r5); two windows of n_oos_weeks consecutive IS
    entry weeks (first, last). Measures the false rate of the B CI, the full B pass and the
    same-day excess CI."""
    idx_oos = int(split["idx_oos"])
    close = panel_is["close"]
    if close.shape[1] > idx_oos and np.isfinite(close[:, idx_oos:]).any():
        raise LeakError("calibrate_null was handed a panel with a finite close at/after oos_from")
    if rows is None:
        rows = c5_rows(panel_is, liq, {"is": [t for t in split["is"]
                                              if t < close.shape[1] - 1 - C5_HOLD]})
    cohort, trades = rows
    n_w = int(split.get("oos_weeks") or 0)
    nominal = (100 - CI_PCT) / 100
    base = {"reps": int(reps), "reps_done": 0, "n_oos_weeks": n_w, "nominal": nominal,
            "windows": [], "method": "random same-count selection from the eligible IS cohort"}
    if not len(trades) or not n_w:
        return base
    weeks = sorted(set(trades["entry_week"]))
    wins = [weeks[:n_w], weeks[-n_w:]]
    pidx = _pool_index(cohort, PLACEBO_EXCLUDE_BACK)
    day_mean = cohort.groupby("t")["net_ret"].mean()
    elig = cohort.index[cohort["r5_ok"].astype(bool)].to_numpy()
    elig_t = cohort["t"].to_numpy()[elig]
    by_t = {int(t): elig[elig_t == t] for t in np.unique(elig_t)}
    k_t = trades.groupby("t").size().to_dict()
    net_all = cohort["net_ret"].to_numpy()
    wk_all = cohort["entry_week"].to_numpy()
    t_all = cohort["t"].to_numpy()
    win_sessions = []
    for w in wins:
        ws = set(w)
        win_sessions.append(sorted({int(t) for t, wk in zip(trades["t"], trades["entry_week"])
                                    if wk in ws}))
    counts = [{"b_ci_false": 0, "b_full_false": 0, "excess_ci_false": 0} for _ in wins]
    t0 = time.time()
    done = 0
    for rep in range(int(reps)):
        if time.time() - t0 > budget_sec:
            break
        rng = np.random.default_rng(seed + rep)
        for wi, sess in enumerate(win_sessions):
            pick = []
            for t in sess:
                pool = by_t.get(t)
                k = int(k_t.get(t, 0))
                if pool is None or not len(pool) or not k:
                    continue
                pick.append(rng.choice(pool, size=min(k, len(pool)), replace=False))
            if not pick:
                continue
            r = np.concatenate(pick)
            beat, d, _L = _placebo_core(r, pidx, net_all[r], placebo_sets, seed + 100_000 + rep)
            dci = cluster_mean_ci(d, wk_all[r], draws=draws, seed=seed + rep)
            ex = net_all[r] - pd.Series(t_all[r]).map(day_mean).to_numpy()
            eci = cluster_mean_ci(ex, wk_all[r], draws=draws, seed=seed + 7 + rep)
            c = counts[wi]
            c["b_ci_false"] += dci["word"] in ("separates", "inverted")
            c["b_full_false"] += (dci["word"] == "separates" and beat is not None
                                  and beat >= PLACEBO_BEAT_SHARE)
            c["excess_ci_false"] += eci["word"] in ("separates", "inverted")
        done += 1
    base["reps_done"] = done
    for wi, w in enumerate(wins):
        blk = {"first_week": w[0], "last_week": w[-1], "n_weeks": len(w),
               "n_sessions": len(win_sessions[wi])}
        for k, v in counts[wi].items():
            blk[k] = {"k": int(v), "rate": round(v / done, 4) if done else None,
                      "ci95": list(_wilson(v, done))}
        base["windows"].append(blk)
    tot = {k: sum(c[k] for c in counts) for k in counts[0]}
    n_tot = done * len(wins)
    base["pooled"] = {k: {"k": int(v), "n": n_tot, "rate": round(v / n_tot, 4) if n_tot else None,
                          "ci95": list(_wilson(v, n_tot))} for k, v in tot.items()}
    base["runtime_sec"] = round(time.time() - t0, 1)
    return base


def _sleeve_psr_range(trades):
    if trades is None or len(trades) == 0:
        return None
    g = trades.groupby("t", sort=True)["net_ret"].mean() * 100.0
    ts = g.index.to_numpy()
    vals = []
    for k in range(C5_HOLD):
        sub = g.to_numpy()[(ts - ts.min()) % C5_HOLD == k]
        m = moments(sub)
        p = psr(m["sr"], 0.0, m["n"], m["skew"], m["kurt"]) if m["sr"] is not None else None
        if p is not None:
            vals.append(p)
    return [round(min(vals), 4), round(max(vals), 4)] if vals else None


def _lag1(x) -> Optional[float]:
    x = np.asarray(x, dtype=float)
    if len(x) < 3 or np.std(x[:-1]) == 0 or np.std(x[1:]) == 0:
        return None
    return float(np.corrcoef(x[:-1], x[1:])[0, 1])


def gate_block(trades, cohort, *, draws, placebo_sets, seed, trial_srs_others) -> dict:
    """A, B, C and the reported lines for one split's trades."""
    if trades is None or len(trades) == 0:
        A = cluster_mean_ci([], [])
        return {"A": dict(A, **{"pass": False}), "B": placebo(None, None),
                "C": {"pass": False, "dsr": None}, "reported": {},
                "clean": {"A": dict(A, **{"pass": False}), "B": placebo(None, None),
                          "n_flagged": 0, "n_rows": 0}}
    net = trades["net_ret"].to_numpy()
    A = cluster_mean_ci(net, trades["entry_week"], draws=draws, seed=seed)
    A["pass"] = A["word"] == "separates"
    srt = np.sort(net)[::-1]
    top = srt[:max(1, int(math.ceil(0.01 * len(srt))))]
    tot = float(np.sum(net))
    A["beside"] = {"win_rate": round(float(np.mean(net > 0)), 4), "stop_out_rate": None,
                   "median_pct": RS._r(float(np.median(net)) * 100, SHOW_DP),
                   "top1pct_share": RS._r(float(np.sum(top)) / tot, 4) if tot > 0 else None,
                   "mae_p10_pct": RS._r(float(np.percentile(trades["mae_pct"], 10)), SHOW_DP),
                   "gross_mean_pct": RS._r(float(trades["gross_ret"].mean()) * 100, SHOW_DP),
                   "breakeven_bps_side": RS._r(breakeven_cost_bps(trades), 3)}
    B = placebo(trades, cohort, sets=placebo_sets, seed=seed + 1, draws=draws)
    x = gate_c_series(trades)
    own = moments(x)
    srs = list(trial_srs_others or []) + ([own["sr"]] if own["sr"] is not None else [])
    C = deflated(x, srs)
    C["series"] = GATE_C_SERIES
    C["pass"] = C["dsr"] is not None and C["dsr"] >= DSR_PASS
    C["lag1_autocorr"] = RS._r(_lag1(x), 4)
    C["sleeve_psr_range"] = _sleeve_psr_range(trades)
    xt = gate_c_series(trades, "per_trade")
    ot = moments(xt)
    C["per_trade"] = deflated(xt, list(trial_srs_others or []) + (
        [ot["sr"]] if ot["sr"] is not None else []))
    nde = trades[trades["exit_reason"] != "data_end"]
    gh = (trades["glitch_hold"].astype(bool) if "glitch_hold" in trades.columns
          else pd.Series(False, index=trades.index))
    clean = _clean_gates(trades, cohort, gh.to_numpy(), A, B, draws=draws,
                         placebo_sets=placebo_sets, seed=seed)
    rep = {"same_day_excess": cluster_mean_ci(_day_excess(trades, cohort), trades["entry_week"],
                                              draws=draws, seed=seed + 3),
           "A_without_data_end": cluster_mean_ci(nde["net_ret"], nde["entry_week"], draws=draws,
                                                 seed=seed + 4),
           "A_without_scale_glitch_hold": clean["A"],
           "n_scale_glitch_hold": int(gh.sum()),
           "A_by_entry_day": cluster_mean_ci(net, trades["entry_date"], draws=draws,
                                             seed=seed + 5),
           "A_by_trade": cluster_mean_ci(net, np.arange(len(net)), draws=min(draws, 2000),
                                         seed=seed + 6),
           "exit_reasons": {r: int((trades["exit_reason"] == r).sum()) for r in EXIT_REASONS},
           "largest_net_trades": _largest_trades(trades)}
    return {"A": A, "B": B, "C": C, "reported": rep, "own_sr": own["sr"], "clean": clean}


def _clean_gates(trades, cohort, gh, A, B, *, draws, placebo_sets, seed) -> dict:
    """Gates A and B with the flagged rows removed from trades AND cohort (same seeds as the
    all-rows gates, so no flagged row anywhere -> identical to them)."""
    cg = (cohort["glitch_hold"].astype(bool).to_numpy() if "glitch_hold" in cohort.columns
          else np.zeros(len(cohort), dtype=bool))
    n_flagged = int(np.sum(gh))
    out = {"n_flagged": n_flagged, "n_rows": int(len(trades)),
           "n_cohort_flagged": int(cg.sum())}
    if n_flagged == 0 and not cg.any():
        return dict(out, A=A, B=B)
    tr = trades[~gh].copy()
    co = cohort[~cg].reset_index(drop=True)
    if "row" in tr.columns:
        newpos = np.cumsum(~cg) - 1
        tr["row"] = newpos[tr["row"].to_numpy().astype(int)]
    tr = tr.reset_index(drop=True)
    Ac = cluster_mean_ci(tr["net_ret"], tr["entry_week"], draws=draws, seed=seed)
    Ac["pass"] = Ac["word"] == "separates"
    Bc = placebo(tr, co, sets=placebo_sets, seed=seed + 1, draws=draws)
    return dict(out, A=Ac, B=Bc)


def _largest_trades(trades, k=20) -> list:
    idx = np.argsort(-np.abs(trades["net_ret"].to_numpy()), kind="stable")[:k]
    out = []
    for i in idx:
        r = trades.iloc[int(i)]
        out.append({"sym": r["sym"], "signal_date": r["signal_date"], "entry_date": r["entry_date"],
                    "exit_date": r["exit_date"], "entry_px": float(r["entry_px"]),
                    "exit_px": float(r["exit_px"]), "net_pct": round(float(r["net_ret"]) * 100, 3),
                    "exit_reason": r["exit_reason"]})
    return out


def largest_moves(panel, cohort, k=20) -> list:
    """The k largest single-session |open/prev close - 1| inside any cohort hold window [e, x]
    (the C9 audit list; no threshold)."""
    if cohort is None or len(cohort) == 0:
        return []
    opn = panel["open"]
    prev = _prev_own_close(panel["close"])
    with np.errstate(invalid="ignore", divide="ignore"):
        gap = np.abs(opn / prev - 1.0)
    n_sym, n_days = opn.shape
    cover = np.zeros((n_sym, n_days + 1), dtype=np.int64)
    s = cohort["s"].to_numpy().astype(int)
    np.add.at(cover, (s, cohort["e"].to_numpy().astype(int)), 1)
    np.add.at(cover, (s, cohort["x"].to_numpy().astype(int) + 1), -1)
    mask = np.cumsum(cover, axis=1)[:, :n_days] > 0
    g = np.where(mask & np.isfinite(gap), gap, -1.0)
    flat = np.argsort(-g, axis=None, kind="stable")[:k]
    out = []
    for f in flat:
        i, j = divmod(int(f), n_days)
        if g[i, j] < 0:
            break
        out.append({"sym": panel["syms"][i], "date": panel["days"][j],
                    "open_vs_prev_close_pct": round(float(gap[i, j]) * 100, 3)})
    return out


# ---------------------------------------------------------------------------
# prereg, ledger
# ---------------------------------------------------------------------------
def prereg_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def valid_commit(h) -> bool:
    return bool(re.fullmatch(PREREG_COMMIT_RE, str(h or "")))


def _read_ledger(path) -> list:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8") or "[]")
    return data if isinstance(data, list) else []


def ledger_conflict(rows, trial_id, sha) -> Optional[str]:
    """The refusal sentence when `trial_id` is already in the ledger under a different prereg
    sha256 (a changed prereg is a new trial), else None. Read BEFORE any OOS read."""
    for r in rows or []:
        if r.get("trial_id") == trial_id and r.get("prereg_sha256") != sha:
            return (f"ledger: trial {trial_id} already recorded under a different prereg sha256 "
                    "— a changed prereg is a new trial")
    return None


def ledger_append(path, entry) -> list:
    """Atomic tmp+rename. Same trial_id + prereg_sha256 + as_of replaces; same trial_id with a
    different sha raises; anything else appends. The directory must already exist (never
    created: an unmounted /research would put the ledger inside the --rm container)."""
    p = Path(path)
    if not p.parent.is_dir():
        raise FileNotFoundError(f"ledger directory {p.parent} does not exist; never created here")
    rows = _read_ledger(p)
    clash = ledger_conflict(rows, entry.get("trial_id"), entry.get("prereg_sha256"))
    if clash:
        raise ValueError(clash)
    out, replaced = [], False
    for r in rows:
        if r.get("trial_id") == entry.get("trial_id"):
            if r.get("as_of") == entry.get("as_of"):
                out.append(entry)
                replaced = True
                continue
        out.append(r)
    if not replaced:
        out.append(entry)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(out, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    return out


def ledger_trial_srs(rows, exclude_trial=None) -> list:
    """Per-entry-day SR of every distinct trial (latest row per trial_id)."""
    last: dict = {}
    for r in rows or []:
        if r.get("trial_id") and r.get("sr_per_entry_day") is not None:
            last[r["trial_id"]] = float(r["sr_per_entry_day"])
    return [v for k, v in last.items() if k != exclude_trial]


# ---------------------------------------------------------------------------
# report + artefacts
# ---------------------------------------------------------------------------
def forbidden_hits(text) -> list:
    """FORBIDDEN_WORDS found in `text`, each matched from a word start (so "ledger" is not
    "edge", while "edges" and "prediction" are hits)."""
    low = str(text or "").lower()
    return [w for w in FORBIDDEN_WORDS if re.search(r"(?<![a-z0-9])" + re.escape(w), low)]


def _fmt(v, dp=3):
    return "n/a" if v is None else f"{v:.{dp}f}"


def _ci(ci, dp=3):
    return "n/a" if not ci else f"[{ci[0]:.{dp}f}, {ci[1]:.{dp}f}]"


def _calib_line(cal) -> str:
    if not cal or not cal.get("pooled"):
        return "CI calibration (IS nulls, nominal 5%): not measured yet"
    p = cal["pooled"]

    def one(k):
        r = p[k]
        lo, hi = r["ci95"]
        return (f"{100 * r['rate']:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"
                if r["rate"] is not None else "n/a")
    return (f"CI calibration (IS nulls, nominal {100 * cal['nominal']:.0f}%): B CI "
            f"{one('b_ci_false')} · B full {one('b_full_false')} · same-day excess "
            f"{one('excess_ci_false')} ({cal['reps_done']} of {cal['reps']} reps)")


def render_report(stats) -> str:
    mode = stats.get("mode")
    v = stats.get("verdict") or {}
    pf = (lambda k: "pass" if v.get(k) else "fail")
    glitch = (f"n_flagged {v.get('n_flagged', 0)} of {v.get('n_rows', 0)} trade rows "
              f"({_fmt(100 * v['flagged_share'] if v.get('flagged_share') is not None else None, 2)}"
              f"%; limit {_fmt(100 * GLITCH_VERDICT_MAX_SHARE, 0)}%)")
    if mode == "outcome" and v.get("word") == UNMEASURED_GLITCH:
        head = (f"**{UNMEASURED_GLITCH}: no verdict word** — {glitch}; flagged split-glitch rows "
                f"above the limit (A {pf('A')} / without flagged {pf('A_clean')} · B {pf('B')} / "
                f"without flagged {pf('B_clean')} · C {pf('C')})")
    elif mode == "outcome":
        head = (f"**Verdict: {v.get('word')}** (A {pf('A')} / without flagged {pf('A_clean')} · "
                f"B {pf('B')} / without flagged {pf('B_clean')} · C {pf('C')} · {glitch})"
                f"{' — ' + v['label'] if v.get('label') else ''}")
    else:
        head = (f"**Verdict: not computed — {mode} run, OOS sealed** (A/B/C read only in the "
                "outcome run after the prereg commit)")
    un = ", ".join(UNMEASURED_NAMES.values())
    needs = "; ".join(f"{UNMEASURED_NAMES[k]}: {CANDIDATES[k]['needs']}" for k in UNMEASURED_NAMES)
    cal = stats.get("calendar") or {}
    sp = stats.get("split") or {}
    uni = stats.get("universe") or {}
    costs = stats.get("costs") or {}
    excl_n = sum((uni.get("excluded_by_reason") or {}).values())
    lines = [f"# Strategy lab 2026-10-29 — T01 C5 short-term reversal", "", head, "",
             _calib_line(stats.get("calibration")), "",
             f"UNMEASURED (not run on this cache): {un} — {needs}", "",
             f"Rule: {RULE_TEXT}", "",
             f"Data: calendar {cal.get('first_day')}..{stats.get('as_of')}; OOS signals "
             f"{sp.get('oos_from')}..{sp.get('oos_last')}; "
             f"{(stats.get('oos') or {}).get('n_trades', 'sealed')} trades in "
             f"{sp.get('oos_weeks')} entry weeks; costs {costs.get('tier1_bps_side')} bps per "
             f"side; universe excludes funds, crypto pairs and index docs ({excl_n} symbols, "
             "list in stats.json).", ""]
    if mode == "outcome":
        o = stats["oos"]
        A, B, C = o["A"], o["B"], o["C"]
        cl = o.get("clean") or {}
        Ac, Bc = cl.get("A") or {}, cl.get("B") or {}
        Bcd = Bc.get("diff") or {}
        bs = A.get("beside") or {}
        lines += ["| line | value | 95% CI (entry weeks) | word |", "|---|---|---|---|",
                  f"| A OOS mean net per trade | {_fmt(A.get('mean_pct'))}% | "
                  f"{_ci(A.get('ci_pct'))} | {A.get('word')} |",
                  f"| B minus same-name same-month placebo (overlap removed) | "
                  f"{_fmt(B['diff'].get('mean_pct'))} pp | {_ci(B['diff'].get('ci_pct'))} | "
                  f"beat share {_fmt(100 * B['beat_share'] if B.get('beat_share') is not None else None, 1)}% |",
                  f"| A without the {cl.get('n_flagged', 0)} flagged rows | "
                  f"{_fmt(Ac.get('mean_pct'))}% | {_ci(Ac.get('ci_pct'))} | {Ac.get('word')} |",
                  f"| B without the flagged rows (trades and pool) | {_fmt(Bcd.get('mean_pct'))} pp | "
                  f"{_ci(Bcd.get('ci_pct'))} | beat share "
                  f"{_fmt(100 * Bc['beat_share'] if Bc.get('beat_share') is not None else None, 1)}% |",
                  f"| C Deflated Sharpe, per entry day (N={C.get('N')}) | {_fmt(C.get('dsr'), 2)} | "
                  f"PSR(0) {_fmt(C.get('psr0'), 2)} · lag-1 autocorr "
                  f"{_fmt(C.get('lag1_autocorr'), 2)} | |", "",
                  f"Beside A: win rate {_fmt(bs.get('win_rate'), 3)} · median "
                  f"{_fmt(bs.get('median_pct'))}% · stop-out rate n/a (no stop) · top-1% share "
                  f"{_fmt(bs.get('top1pct_share'), 3)} · MAE p10 {_fmt(bs.get('mae_p10_pct'))}% · "
                  f"gross mean {_fmt(bs.get('gross_mean_pct'))}% · break-even cost "
                  f"{_fmt(bs.get('breakeven_bps_side'), 1)} bps per side.", ""]
        rep = o.get("reported") or {}
        sde = rep.get("same_day_excess") or {}
        lines += [f"Reported, never the verdict: same-day universe excess "
                  f"{_fmt(sde.get('mean_pct'))} pp {_ci(sde.get('ci_pct'))} · A without data_end "
                  f"{_fmt((rep.get('A_without_data_end') or {}).get('mean_pct'))}% · A without "
                  f"the {rep.get('n_scale_glitch_hold', 0)} scale-glitch-hold rows "
                  f"{_fmt((rep.get('A_without_scale_glitch_hold') or {}).get('mean_pct'))}% "
                  f"{_ci((rep.get('A_without_scale_glitch_hold') or {}).get('ci_pct'))} · per-trade "
                  f"PSR {_fmt((C.get('per_trade') or {}).get('psr0'), 2)} / DSR "
                  f"{_fmt((C.get('per_trade') or {}).get('dsr'), 2)} · sleeve PSR range "
                  f"{C.get('sleeve_psr_range')} · daily book {o.get('book')} · capacity $"
                  f"{_fmt(o.get('capacity_usd'), 0)} · skips {stats.get('skips')} · flags "
                  f"{stats.get('flags')} · IS block in "
                  f"stats.json ({(stats.get('is') or {}).get('label')}) · MDE "
                  f"{_fmt(stats.get('mde'))}%.", "",
                  "Trading-skill cross-check: PSR / DSR formula vs connector (both printed in "
                  "connector_results.json; the formula is the gate).", ""]
    else:
        isb = stats.get("is") or {}
        lines += [f"IS (sealed slice; counts and dispersion only): {isb.get('n_trades')} trades, "
                  f"{isb.get('n_weeks')} entry weeks, {isb.get('n_sessions')} sessions; "
                  f"dispersion {isb.get('dispersion')}; MDE {_fmt(stats.get('mde'))}% per trade "
                  f"over {sp.get('oos_weeks')} OOS weeks. {isb.get('label')}.", ""]
    lines += ["POSITIVE definition (verbatim, shortlist.md:23-27):", "", POSITIVE_TEXT, "",
              "Limits:"] + [f"- {x}" for x in LIMITS] + ["", "Re-run:", "",
                                                        f"    {RUN_BY_MODE.get(mode, RUN_SMOKE)}",
                                                        ""]
    return "\n".join(lines)


def connector_payloads(stats, daily, trades) -> dict:
    """Unlabeled OOS arrays for the trading-skill connector (no symbols)."""
    d = daily[daily["split"] == "oos"] if daily is not None and len(daily) else daily
    tr = trades[trades["split"] == "oos"] if trades is not None and len(trades) else trades
    rets = [float(v) for v in (d["book_net"] if d is not None and len(d) else [])]
    bench = [None if v is None or (isinstance(v, float) and not math.isfinite(v)) else float(v)
             for v in (d["spy_ret"] if d is not None and len(d) else [])]
    return {"sharpe_stats": {"returns": rets, "periods_per_year": 252},
            "dsr": {"returns": [float(v) for v in gate_c_series(tr)] if tr is not None else [],
                    "trial_sharpes": list(stats.get("trial_srs") or [])},
            "tearsheet": {"dates": list(d["date"]) if d is not None and len(d) else [],
                          "returns": rets, "benchmark_returns": bench}}


def _json(obj) -> str:
    return json.dumps(obj, indent=1, allow_nan=False, default=_jdefault) + "\n"


def _jdefault(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o).__name__)


def write_artefacts(out_dir, *, stats, trades=None, daily=None, payloads=None, report=None,
                    calibration=None, log_lines=None) -> None:
    """Every artefact through allow_nan=False — a NaN raises ValueError, never lands silently."""
    out = Path(out_dir)
    blobs = {"stats.json": _json(stats)}
    if trades is not None:
        recs = [{k: r.get(k) for k in TRADE_KEYS} for r in trades.to_dict("records")]
        blobs["trades.json"] = _json(recs)
    if payloads is not None:
        blobs["connector_payloads.json"] = _json(payloads)
    if calibration is not None:
        blobs["calibration.json"] = _json(calibration)
    if daily is not None:
        num = daily[["book_gross", "book_net"]].to_numpy(dtype=float) if len(daily) else []
        assert_finite(num, "daily.csv")
        blobs["daily.csv"] = daily.to_csv(index=False)
    if report is not None:
        blobs["report.md"] = report
    if log_lines is not None:
        blobs["run.log"] = "\n".join(log_lines) + "\n"
    out.mkdir(parents=True, exist_ok=True)
    for name, text in blobs.items():
        (out / name).write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------
def _universe(frames, *, types, as_of, oos_from, fund_kw=None) -> tuple:
    tmap = (types or {}).get("types") or {}
    docs_total = len(frames)
    stopped = docs_stopped_split(frames, as_of=as_of, oos_from=oos_from, types=tmap)
    dd, merged = canonical_dedupe({s: f for s, f in frames.items() if s != BENCH})
    kw = dict(fund_kw or {})
    if "db" not in kw:
        coll = prices._get_mongo()
        kw["db"] = coll.database if coll is not None else None
    ex = fund_symbols(sorted(dd), types=tmap, **kw)
    excluded = set().union(*(ex[r] for r in EXCLUSION_REASONS))
    kept = {s: f for s, f in dd.items() if s not in excluded}
    meta = {"docs_total": docs_total,
            "excluded_by_reason": {r: len(ex[r]) for r in EXCLUSION_REASONS},
            "excluded_symbols_by_reason": {r: sorted(ex[r]) for r in EXCLUSION_REASONS},
            "kept_unknown_type": sorted(ex["kept_unknown_type"]),
            "type_map_as_of": (types or {}).get("as_of"),
            "type_map_complete": (types or {}).get("complete"),
            "dupes_merged": merged, "docs_stopped": stopped,
            "universe_symbols": len(kept)}
    return kept, meta


def _is_label(meta) -> str:
    st = meta.get("docs_stopped") or {}
    n = int(st.get("ended_before_oos", 0)) + int(st.get("ended_before_2026_05", 0))
    return f"IS: survivors only ({n:,} of {meta.get('docs_total', 0):,} docs end before 2026-05)"


def run_c5(frames, *, as_of, oos_from, draws=BOOT_DRAWS, placebo_sets=PLACEBO_SETS, seed=SEED,
           mode="smoke", trial_srs=None, types=None, fund_kw=None, calib_reps=CALIB_REPS) -> dict:
    """mode smoke | calibrate | outcome -> {"stats", "trades", "daily", "payloads",
    "calibration", "cohort"}. Raises ValueError for an `oos_from` that is not a signal date."""
    if mode not in MODES:
        raise ValueError(mode)
    t0 = time.time()
    bench = frames[BENCH]
    days = [d for d in sorted(set(RS.frame_days(bench))) if d <= as_of]
    S_full = signal_sessions(len(days))
    split = split_sessions(S_full, days, oos_from)
    kept, meta = _universe(frames, types=types, as_of=as_of, oos_from=split["oos_from"],
                           fund_kw=fund_kw)
    panel = build_panel(kept, days)
    ba = RS.aligned(bench, days)
    panel["bench_open"], panel["bench_close"] = ba["open"], ba["close"]
    sealed = mode in ("smoke", "calibrate")
    work = seal_panel(panel, split["idx_oos"]) if sealed else panel
    liq = liquidity_panel(work)
    S_work = set(signal_sessions(len(work["days"])))
    by_split = {"is": [t for t in split["is"] if t in S_work]}
    if not sealed:
        by_split["oos"] = split["oos"]
    cohort, trades = c5_rows(work, liq, by_split)
    tier2 = int((trades["cost_tier"] == 2).sum()) if len(trades) else 0
    assert tier2 == 0, "C5 rank <= 500 < 1,000: tier 2 is unreachable"
    elig_syms = sorted(set(cohort["sym"])) if len(cohort) else []
    asof_ts = pd.Timestamp(as_of)
    stopped_elig = [s for s in elig_syms
                    if prices.is_stale(kept[s], asof_ts, max_trading_days=STOPPED_SESSIONS)]
    meta["names_ever_eligible"] = len(elig_syms)
    meta["stopped_names_ever_eligible"] = len(stopped_elig)
    tr_is = trades[trades["split"] == "is"] if len(trades) else trades
    sd_w = _week_sd_pct(tr_is)
    stats = {"study": STUDY, "script": SCRIPT, "candidate": "c5_reversal", "trial_id": "T01",
             "params": TRIALS[0]["params"], "prereg": PREREG, "prereg_sha256": None,
             "prereg_commit": None, "mode": mode, "run_date": None, "as_of": as_of,
             "calendar": {"first_day": days[0], "last_day": days[-1], "n_days": len(days)},
             "signal_sessions": {"n": len(S_full), "first": days[S_full[0]] if S_full else None,
                                 "last": days[S_full[-1]] if S_full else None},
             "split": {k: split[k] for k in ("oos_from", "oos_from_rule", "is_n", "embargo_n",
                                             "oos_n", "oos_last", "oos_weeks")},
             "universe": meta, "skips": cohort.attrs.get("skips", {}),
             "cohort_skips": cohort.attrs.get("cohort_skips", {}),
             "flags": cohort.attrs.get("flags", {}),
             "cohort_flags": cohort.attrs.get("cohort_flags", {}),
             "costs": {"tier1_bps_side": COST_TIER1_BPS + SLIPPAGE_BPS,
                       "tier2_bps_side": COST_TIER2_BPS + SLIPPAGE_BPS,
                       "tier1_top_n": COST_TIER1_TOP_N, "tier2_trades": tier2,
                       "breakeven_bps_side": None},
             "mde": RS._r(mde_pct(sd_w, split["oos_weeks"]), SHOW_DP),
             "limits": list(LIMITS), "calibration": None}
    is_counts = {"n_trades": int(len(tr_is)),
                 "n_weeks": int(tr_is["entry_week"].nunique()) if len(tr_is) else 0,
                 "n_sessions": int(tr_is["t"].nunique()) if len(tr_is) else 0,
                 "n_cohort_rows": int((cohort["split"] == "is").sum()) if len(cohort) else 0,
                 "n_scale_glitch_hold": int(tr_is["glitch_hold"].sum()) if len(tr_is) else 0,
                 "label": _is_label(meta)}
    out = {"stats": stats, "trades": None, "daily": None, "payloads": None, "calibration": None,
           "cohort": cohort}
    if sealed:
        x = (tr_is["net_ret"].to_numpy() * 100) if len(tr_is) else np.zeros(0)
        is_counts["dispersion"] = {
            "sd_trade_pct": RS._r(float(np.std(x, ddof=1)), SHOW_DP) if len(x) > 1 else None,
            "sd_week_pct": RS._r(sd_w, SHOW_DP),
            "p90_minus_p10_pct": RS._r(float(np.percentile(x, 90) - np.percentile(x, 10)),
                                       SHOW_DP) if len(x) else None}
        is_counts["exit_reasons"] = {r: int((tr_is["exit_reason"] == r).sum()) if len(tr_is)
                                     else 0 for r in EXIT_REASONS}
        stats["is"] = is_counts
        stats["oos"] = {"sealed": True}
        stats["verdict"] = {"word": None, "sealed": True}
        if mode == "calibrate":
            cal = calibrate_null(work, liq, split, reps=calib_reps, draws=draws,
                                 placebo_sets=placebo_sets, seed=seed + 2,
                                 rows=(cohort, trades))
            stats["calibration"] = cal
            out["calibration"] = cal
        stats["runtime_sec"] = round(time.time() - t0, 1)
        return out
    others = list(trial_srs or [])
    tr_oos = trades[trades["split"] == "oos"]
    co_oos = cohort[cohort["split"] == "oos"]
    g_oos = gate_block(tr_oos, cohort, draws=draws, placebo_sets=placebo_sets, seed=seed,
                       trial_srs_others=others)
    g_is = gate_block(tr_is, cohort, draws=draws, placebo_sets=placebo_sets, seed=seed + 50,
                      trial_srs_others=others)
    d_is = daily_book(tr_is, panel, days)
    d_oos = daily_book(tr_oos, panel, days)
    daily = pd.concat([d_is, d_oos], ignore_index=True) if len(d_is) or len(d_oos) else d_oos
    g_oos["n_trades"] = int(len(tr_oos))
    g_oos["capacity_usd"] = capacity_usd(tr_oos)
    g_oos["book"] = _book_stats(d_oos)
    g_oos["reported"]["largest_moves_in_holds"] = largest_moves(panel, co_oos)
    g_is["book"] = _book_stats(d_is)
    g_is["label"] = _is_label(meta)
    g_is.update({k: v for k, v in is_counts.items() if k != "label"})
    stats["oos"] = g_oos
    stats["is"] = g_is
    stats["costs"]["breakeven_bps_side"] = g_oos["A"].get("beside", {}).get("breakeven_bps_side")
    stats["trial_srs"] = others + ([g_oos["own_sr"]] if g_oos.get("own_sr") is not None else [])
    stats["verdict"] = verdict_of(g_oos)
    out.update(trades=trades, daily=daily)
    out["payloads"] = connector_payloads(stats, daily, trades)
    stats["runtime_sec"] = round(time.time() - t0, 1)
    return out


def _book_stats(d) -> dict:
    if d is None or len(d) < 2:
        return {}
    r = d["book_net"].to_numpy(dtype=float)
    eq = np.cumprod(1 + r)
    dd = float(np.min(eq / np.maximum.accumulate(eq) - 1))
    yrs = len(r) / 252.0
    cagr = float(eq[-1] ** (1 / yrs) - 1) if yrs > 0 and eq[-1] > 0 else None
    m = moments(r)
    return {"n_days": int(len(r)), "cagr_pct": RS._r(cagr * 100 if cagr is not None else None, 3),
            "vol_pct_ann": RS._r(float(np.std(r, ddof=1) * math.sqrt(252) * 100), 3),
            "max_drawdown_pct": RS._r(dd * 100, 3), "sr_daily": RS._r(m["sr"], 4),
            "psr0": RS._r(psr(m["sr"], 0.0, m["n"], m["skew"], m["kurt"]) if m["sr"] else None, 4)}


def refuse_unmeasurable(candidate, out_dir) -> int:
    c = CANDIDATES[candidate]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "status.json").write_text(_json({"candidate": candidate, "status": "unmeasurable",
                                            "needs": c["needs"], "fact": c["fact"]}),
                                     encoding="utf-8")
    print(f"UNMEASURABLE: {candidate} needs {c['needs']} — stays UNMEASURED (no read, no ledger "
          "entry).")
    return 3


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Strategy lab 2026-10-29 (read-only).")
    ap.add_argument("--candidate", required=True, choices=sorted(CANDIDATES))
    ap.add_argument("--out", required=True)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--stride", type=int, default=None)
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--oos-from", default=None)
    ap.add_argument("--prereg", default=None)
    ap.add_argument("--prereg-commit", default=None)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--draws", type=int, default=BOOT_DRAWS)
    ap.add_argument("--placebo-sets", type=int, default=PLACEBO_SETS)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--force-window", action="store_true")
    return ap.parse_args(argv)


def _refuse(msg) -> int:
    print(f"REFUSED: {msg}", file=sys.stderr)
    return 2


def main(argv=None, *, now=None, frames_fn=None, symbols_fn=None, types_fn=None,
         block=True, fund_kw=None, calib_reps=CALIB_REPS) -> int:
    a = parse_args(argv)
    now_et = (now or datetime.now(tz=ET)).astimezone(ET)
    if out_inside_repo(Path(a.out)):
        return _refuse("--out is inside the repo; artefacts never land in the repo.")
    if CANDIDATES[a.candidate]["status"] != "runnable":
        return refuse_unmeasurable(a.candidate, a.out)
    if RS.refused_window(now_et) and not a.force_window:
        return _refuse(f"{now_et:%H:%M} ET is inside {RS.REFUSE_FROM[0]:02d}:"
                       f"{RS.REFUSE_FROM[1]:02d}-{RS.REFUSE_TO[0]:02d}:{RS.REFUSE_TO[1]:02d} ET; "
                       "pass --force-window to override.")
    if key_present():
        return _refuse("a Massive key is in the environment; the lab runs with no key.")
    if a.smoke and a.calibrate:
        return _refuse("--smoke and --calibrate are separate runs.")
    if a.stride is not None and not a.smoke:
        return _refuse("--stride is a smoke-only option.")
    if a.calibrate and not a.oos_from:
        return _refuse("--calibrate needs --oos-from (the frozen date).")
    if a.prereg_commit is not None and not valid_commit(a.prereg_commit):
        return _refuse("--prereg-commit must be 12-40 lowercase hex (a real commit).")
    if a.ledger and ledger_refusal(a.ledger):
        return _refuse(ledger_refusal(a.ledger))
    mode = "smoke" if a.smoke else ("calibrate" if a.calibrate else "outcome")
    if mode == "outcome":
        miss = [n for n, v in (("--prereg", a.prereg), ("--prereg-commit", a.prereg_commit),
                               ("--oos-from", a.oos_from), ("--ledger", a.ledger)) if not v]
        if miss:
            return _refuse(f"an outcome run needs {', '.join(miss)} (commit the prereg first).")
        if not Path(a.prereg).is_file():
            return _refuse(f"the prereg file {a.prereg} does not exist.")
    sha = prereg_sha256(a.prereg) if a.prereg and Path(a.prereg).is_file() else None
    ledger_rows = _read_ledger(a.ledger) if (mode == "outcome" and a.ledger) else []
    if mode == "outcome":
        clash = ledger_conflict(ledger_rows, "T01", sha)
        if clash:
            return _refuse(clash + "; nothing read (no bar, no OOS, no artefact).")
    if block:
        RS.block_writes()
        block_network()
    t0 = time.time()
    stride = (a.stride if a.stride is not None else STRIDE_DEFAULT) if mode == "smoke" else None
    frames, lmeta = load_frames(frames_fn=frames_fn, symbols_fn=symbols_fn, types_fn=types_fn,
                                stride=stride)
    if not frames or frames.get(BENCH) is None:
        return _refuse(f"the price cache returned no {BENCH} frame.")
    bench_days = sorted(set(RS.frame_days(frames[BENCH])))
    as_of = a.as_of or RS.default_as_of(bench_days, now_et)
    if not as_of:
        return _refuse("no closed session to measure up to.")
    others = ledger_trial_srs(ledger_rows, exclude_trial="T01")
    try:
        res = run_c5(frames, as_of=as_of, oos_from=a.oos_from, draws=a.draws,
                     placebo_sets=a.placebo_sets, seed=a.seed, mode=mode, trial_srs=others,
                     types=lmeta.get("types"), fund_kw=fund_kw, calib_reps=calib_reps)
    except ValueError as exc:
        return _refuse(str(exc))
    stats = res["stats"]
    stats.update(prereg_sha256=sha, prereg_commit=a.prereg_commit,
                 run_date=now_et.date().isoformat(), stride=stride,
                 attempted_writes=sorted(set(RS.ATTEMPTED)),
                 attempted_fetches=list(ATTEMPTED_FETCHES),
                 runtime_sec=round(time.time() - t0, 1))
    if mode == "outcome" and stats.get("calibration") is None:
        cal_path = Path(a.out) / "calibration" / "calibration.json"
        if cal_path.is_file():
            stats["calibration"] = json.loads(cal_path.read_text(encoding="utf-8"))
    report = render_report(stats)
    log = _summary_lines(stats, mode, a.out)
    write_artefacts(a.out, stats=stats, trades=res["trades"], daily=res["daily"],
                    payloads=res["payloads"], report=report, calibration=res["calibration"],
                    log_lines=log)
    if mode == "outcome":
        ledger_append(a.ledger, {"trial_id": "T01", "candidate": "c5_reversal",
                                 "params": TRIALS[0]["params"], "prereg_sha256": sha,
                                 "prereg_commit": a.prereg_commit, "as_of": as_of,
                                 "oos_from": stats["split"]["oos_from"],
                                 "run_date": stats["run_date"],
                                 "sr_per_entry_day": stats["oos"].get("own_sr"),
                                 "n_per_entry_day": (stats["oos"]["C"] or {}).get("n"),
                                 "verdict": stats["verdict"]["word"]})
    for line in log:
        print(line)
    return 0


def _summary_lines(stats, mode, out) -> list:
    u = stats["universe"]
    sp = stats["split"]
    lines = [f"{STUDY} {mode}: as_of {stats['as_of']} · calendar {stats['calendar']['n_days']} "
             f"sessions · signal sessions {stats['signal_sessions']['n']} · oos_from "
             f"{sp['oos_from']} (rule {sp['oos_from_rule']}) · OOS weeks {sp['oos_weeks']}",
             f"universe: docs {u['docs_total']} · excluded {u['excluded_by_reason']} · kept unknown "
             f"type {len(u['kept_unknown_type'])} · dupes merged {u['dupes_merged']} · ever "
             f"eligible {u.get('names_ever_eligible')}",
             f"attempted writes {stats.get('attempted_writes')} · attempted fetches "
             f"{stats.get('attempted_fetches')} · tier2 trades {stats['costs']['tier2_trades']}"]
    if mode == "outcome":
        v = stats["verdict"]
        lines.append(f"verdict {v['word']} (A {v['A']} / clean {v.get('A_clean')} · B {v['B']} / "
                     f"clean {v.get('B_clean')} · C {v['C']} · n_flagged {v.get('n_flagged', 0)} "
                     f"of {v.get('n_rows', 0)}) -> {out}")
    else:
        isb = stats["is"]
        lines.append(f"IS sealed slice: trades {isb['n_trades']} · entry weeks {isb['n_weeks']} · "
                     f"sessions {isb['n_sessions']} · MDE {stats.get('mde')} pct · OOS sealed")
        if stats.get("calibration"):
            lines.append(_calib_line(stats["calibration"]))
    lines.append(f"runtime {stats.get('runtime_sec')}s -> {out}")
    return lines


def imported_modules(path=None) -> set:
    """Top-level module names this file imports (the house AST reader)."""
    return HBS.imported_modules(path or __file__)


if __name__ == "__main__":
    raise SystemExit(main())
