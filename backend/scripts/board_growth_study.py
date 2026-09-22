"""Study A + B-trailing — what the 🚀 Explosive Growth and 📈 Bonde boards have
ALREADY done, measured against RSP and against the scan universe's median member.

NOT A SIGNAL, NOT A GATE — research only (Rule #10).

His sentence (2026-09-21): *"I felt like all the explosive growth stocks and
Bondes stocks have grown a great extent I exited the CRDO today"*. This script
answers the measurable half: the trailing distribution of every current board
member over 1w / 1m / 3m / 6m / 1y, raw, relative to RSP (by CALENDAR DATE, not
bar count) and as a percentile of the scan universe (his standing rule: the
MEDIAN MEMBER, not the ETF). Study B-trailing then asks whether the screen
number itself tracks the trailing run — a look-back mirror or not.

WHAT THIS SCRIPT NEVER DOES
───────────────────────────
* `growth.tracker.screen()` / `build()` WRITE (`_record_seen` stamps
  `growth_seen`). Only the stored doc is read, through `tracker.board()`.
* `sepa.bonde.board(db=None)` WRITES `bonde_seen` via `first_seen.record`.
  Every call here passes `NoWriteDB()`, whose every collection method raises —
  `first_seen.record` catches and returns 0, which is a clean read.
* No threshold, gate, stop or level is invented. `NEAR_HIGH_PCT` is the trend
  template's own literal, pinned by a test. There is deliberately NO
  "beaten down" constant: distance from the 52-week high is reported as
  DECILES, because the ask contains no such percentage (Rule #1).

THE ONE WRITE THAT CAN HAPPEN
─────────────────────────────
`sepa.prices.load_prices` fetches AND writes the parquet + Mongo price cache
for a cold symbol (`prices.py:503-508`). "Read-only" in this study means the
LEDGERS (`growth_seen`, `bonde_seen`, `growth_board`), which are never written.
The run log says so out loud.

RUN (in the api container — the three research scripts live in /tmp/scripts,
never in /app; `scripts` is a PEP 420 namespace package, so PYTHONPATH=/tmp:/app
merges /tmp/scripts with /app/scripts and both `scripts.board_growth_study` and
`scripts.bonde_audit` resolve):

    docker exec -i cheetah-market-app-api-1 sh -c 'mkdir -p /tmp/scripts && cat > /tmp/scripts/board_growth_study.py' < backend/scripts/board_growth_study.py
    docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/tmp:/app python -u -m scripts.board_growth_study --stage members --out /tmp/board_growth_members.csv --json /tmp/board_growth_study.json'

Windows, and whose number each one is (§1.4 of the spec):
  5   one trading week
  21  `rotation.backtest.REBALANCE`
  63  `rotation.backtest.LOOKBACK`
  126 the momentum window `bonde_audit/lane2.py:65` measures over
  252 the trend template's 52-week window (`sepa/trend_template.py:52`)
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import logging
import math
import os
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

import numpy as np

# Constants are IMPORTED, never retyped.
from rotation.backtest import BENCHMARK, LOOKBACK, REBALANCE          # "RSP", 63, 21
from sepa.sales import (SALES_EXPLOSIVE_PCT, SALES_FLOOR_PCT,         # noqa: F401
                        SALES_PREFERRED_PCT)
from growth.tracker import (MIN_EPS_GROWTH_PCT, MIN_PRIOR_SALES_PCT,  # noqa: F401
                            MIN_SALES_GROWTH_PCT)

log = logging.getLogger("scripts.board_growth_study")

HEADER = "NOT A SIGNAL, NOT A GATE — research only (Rule #10)"

WINDOWS = (("1w", 5), ("1m", REBALANCE), ("3m", LOOKBACK), ("6m", 126), ("1y", 252))

# `sepa/trend_template.py:65` — the literal inside `within_25pct_of_52w_high`.
# PINNED by a test against the template itself. It is NOT a new number, and
# there is NO companion "beaten down" percentage anywhere in this module.
NEAR_HIGH_PCT = 25.0

# The 52-week window the trend template measures the high over.
HIGH_WINDOW_BARS = 252
# lane2.py:65's momentum window — the pre-filing look-back leg uses the same one.
MOM_WINDOW_BARS = 126

DEFAULT_FIN_PATH = "/root/.cheetah/audit_fin_v1.json.gz"

# The rule of reading printed above every Study-B table. Two branches, no verdict.
B_RULE_OF_READING = (
    "rho > 0 with a CI above 0 = the board lists names whose growth the market "
    "has already paid for (a look-back mirror); a CI spanning 0 = the screen "
    "number does not track the trailing run."
)

PRICE_CACHE_NOTE = (
    "prices.load_prices may fetch+write the parquet cache for a cold symbol; "
    "the ledgers (growth_seen, bonde_seen, growth_board) are never written."
)


class LookaheadError(RuntimeError):
    """A window that would have been measured before its own data existed."""


# ═════════════════════════════════════════════════════════════════════════════
# Pure helpers — every one of these is unit-tested, none of them touch I/O
# ═════════════════════════════════════════════════════════════════════════════
def _f(v) -> Optional[float]:
    """A finite float, or None. PURE."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def trailing_return_pct(close, k: int) -> Optional[float]:
    """`(close[-1]/close[-1-k] - 1) * 100`. PURE.

    None when the frame is too short (`len(close) <= k`) or the base bar is
    non-positive — a return off a zero or negative base is not a number.
    """
    c = np.asarray(close, dtype=float)
    if k is None or int(k) <= 0 or c.size <= int(k):
        return None
    base = c[-1 - int(k)]
    last = c[-1]
    if not (math.isfinite(base) and math.isfinite(last)) or base <= 0:
        return None
    return (last / base - 1.0) * 100.0


def _last_index_on_or_before(dates: list, d: str) -> Optional[int]:
    """Position of the last bar whose date is <= `d`. PURE. None when none is."""
    if not dates or not d:
        return None
    target = str(d)[:10]
    idx = None
    for i, x in enumerate(dates):
        if str(x)[:10] <= target:
            idx = i
        else:
            break
    return idx


def calendar_window_return_pct(dates: list, close, start_date: str,
                               end_date: str) -> Optional[float]:
    """Return between the last bar <= `start_date` and the last bar <= `end_date`.

    PURE. This is how the benchmark is ALWAYS measured: by calendar date, never
    by bar count. A member frame with a hole in it would otherwise be compared
    against an RSP window of a different length, which is a different question.
    None when either side has no bar, or the start close is non-positive.
    """
    c = np.asarray(close, dtype=float)
    i0 = _last_index_on_or_before(dates, start_date)
    i1 = _last_index_on_or_before(dates, end_date)
    if i0 is None or i1 is None or i0 >= c.size or i1 >= c.size:
        return None
    a, b = c[i0], c[i1]
    if not (math.isfinite(a) and math.isfinite(b)) or a <= 0:
        return None
    return (b / a - 1.0) * 100.0


def first_close_after(dates: list, close, d: str) -> Optional[tuple]:
    """The FIRST bar strictly after `d`, as `(date, close)`. PURE.

    Never the bar ON `d`: a 10-Q filed after that day's close is not tradable
    on it, so any "since qualification" return anchors on the next session.
    None when `d` is past the end of the frame.
    """
    if not dates or not d:
        return None
    c = np.asarray(close, dtype=float)
    target = str(d)[:10]
    for i, x in enumerate(dates):
        if str(x)[:10] > target:
            if i >= c.size:
                return None
            return (str(x)[:10], float(c[i]))
    return None


def relative_pp(member_pct: Optional[float],
                bench_pct: Optional[float]) -> Optional[float]:
    """Member minus benchmark, in percentage points, rounded to 2. PURE.

    The exact form `rotation/tracker.py:444-458 _relativize` prints for
    `rel_5d`/`rel_21d`/`rel_63d`, including rotation's own rule: when either
    side is missing the answer is None, NEVER the raw number.
    """
    m, b = _f(member_pct), _f(bench_pct)
    if m is None or b is None:
        return None
    return round(m - b, 2)


def pct_below_high(close) -> Optional[float]:
    """The trend template's arithmetic (`sepa/trend_template.py:52-56`). PURE.

    `window = close[-252:]`, `hi52 = window.max()`, `(1 - price/hi52) * 100`.
    CLOSE-based, like the template. 0.0 when the last close IS the high.
    """
    c = np.asarray(close, dtype=float)
    c = c[np.isfinite(c)]
    if c.size == 0:
        return None
    window = c[-HIGH_WINDOW_BARS:] if c.size >= HIGH_WINDOW_BARS else c
    hi = float(window.max())
    if not hi:
        return None
    return (1.0 - float(c[-1]) / hi) * 100.0


def pct_below_intraday_high(high, close) -> Optional[float]:
    """The intraday-high variant. PURE. A SECONDARY column, always labelled —
    the template's own number is the close-based one above."""
    h = np.asarray(high, dtype=float)
    c = np.asarray(close, dtype=float)
    if h.size == 0 or c.size == 0:
        return None
    window = h[-HIGH_WINDOW_BARS:] if h.size >= HIGH_WINDOW_BARS else h
    window = window[np.isfinite(window)]
    if window.size == 0:
        return None
    hi = float(window.max())
    last = _f(c[-1])
    if not hi or last is None:
        return None
    return (1.0 - last / hi) * 100.0


def distribution(vals: Iterable[Optional[float]]) -> dict:
    """n / median / mean / deciles p10..p90 / n_pos / n_neg / share_pos. PURE."""
    a = np.asarray([v for v in (_f(x) for x in (vals if vals is not None else [])) if v is not None],
                   dtype=float)
    if a.size == 0:
        out = {"n": 0, "median": None, "mean": None,
               "n_pos": 0, "n_neg": 0, "share_pos": None}
        out.update({f"p{q}": None for q in range(10, 100, 10)})
        return out
    out = {
        "n": int(a.size),
        "median": round(float(np.median(a)), 2),
        "mean": round(float(a.mean()), 2),
        "n_pos": int((a > 0).sum()),
        "n_neg": int((a < 0).sum()),
        "share_pos": round(float((a > 0).mean()) * 100.0, 1),
    }
    for q in range(10, 100, 10):
        out[f"p{q}"] = round(float(np.percentile(a, q)), 2)
    return out


def median_ci(vals: Iterable[Optional[float]], B: int = 2000,
              seed: int = 7) -> tuple:
    """Percentile bootstrap CI for the median, resampling MEMBERS. PURE.

    One date, so members are the right (and only) cluster: the cross-section is
    iid over names in a way a time series never is. `(None, None)` under n=3.
    """
    a = np.asarray([v for v in (_f(x) for x in (vals if vals is not None else [])) if v is not None],
                   dtype=float)
    if a.size < 3:
        return (None, None)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, a.size, (int(B), a.size))
    meds = np.median(a[idx], axis=1)
    return (round(float(np.percentile(meds, 2.5)), 2),
            round(float(np.percentile(meds, 97.5)), 2))


def percentile_of(vals: Iterable[Optional[float]], x: Optional[float]) -> Optional[float]:
    """Where `x` sits inside `vals`, 0-100, by AVERAGE RANK (mid-rank). PURE.

    `100 * (count(v < x) + 0.5*count(v == x)) / n`. Ties get the average rank
    rather than the optimistic or the pessimistic end. None on an empty cohort
    or a missing `x`.
    """
    a = np.asarray([v for v in (_f(v) for v in (vals if vals is not None else [])) if v is not None],
                   dtype=float)
    xv = _f(x)
    if a.size == 0 or xv is None:
        return None
    below = float((a < xv).sum())
    equal = float((a == xv).sum())
    return round(100.0 * (below + 0.5 * equal) / a.size, 1)


def _avg_ranks(a: np.ndarray) -> np.ndarray:
    """1-based average (mid) ranks. PURE — no scipy in the container."""
    n = a.size
    order = np.argsort(a, kind="mergesort")
    srt = a[order]
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and srt[j + 1] == srt[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def _paired(x, y) -> tuple:
    """The finite pairs of two sequences, as float arrays. PURE."""
    xs = [_f(v) for v in (x if x is not None else [])]
    ys = [_f(v) for v in (y if y is not None else [])]
    n = min(len(xs), len(ys))
    ok = [(xs[i], ys[i]) for i in range(n)
          if xs[i] is not None and ys[i] is not None]
    if not ok:
        return (np.empty(0), np.empty(0))
    return (np.asarray([p[0] for p in ok], dtype=float),
            np.asarray([p[1] for p in ok], dtype=float))


def spearman_rho(x, y) -> Optional[float]:
    """Spearman rho from AVERAGE RANKS (no scipy in the container). PURE.

    None when fewer than 3 usable pairs, or when either side is constant —
    a constant side has no rank order, so a correlation would be a division
    by zero dressed up as a number.
    """
    xa, ya = _paired(x, y)
    if xa.size < 3:
        return None
    rx, ry = _avg_ranks(xa), _avg_ranks(ya)
    if rx.std() == 0 or ry.std() == 0:
        return None
    rho = float(np.corrcoef(rx, ry)[0, 1])
    return None if not math.isfinite(rho) else round(rho, 4)


def spearman_ci(x, y, B: int = 2000, seed: int = 11) -> tuple:
    """Percentile bootstrap CI for `spearman_rho`, resampling PAIRS. PURE."""
    xa, ya = _paired(x, y)
    if xa.size < 3 or spearman_rho(xa, ya) is None:
        return (None, None)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(int(B)):
        idx = rng.integers(0, xa.size, xa.size)
        r = spearman_rho(xa[idx], ya[idx])
        if r is not None:
            out.append(r)
    if len(out) < 3:
        return (None, None)
    arr = np.asarray(out, dtype=float)
    return (round(float(np.percentile(arr, 2.5)), 4),
            round(float(np.percentile(arr, 97.5)), 4))


def perm_p(x, y, draws: int = 5000, seed: int = 13) -> Optional[float]:
    """Two-sided permutation p for `spearman_rho`. PURE.

    `(1 + #{|rho_perm| >= |rho_obs|}) / (draws + 1)` — the +1 form, so a p of
    exactly zero can never be printed.
    """
    xa, ya = _paired(x, y)
    obs = spearman_rho(xa, ya)
    if obs is None:
        return None
    rng = np.random.default_rng(seed)
    hits = 0
    n = 0
    for _ in range(int(draws)):
        r = spearman_rho(xa, rng.permutation(ya))
        if r is None:
            continue
        n += 1
        if abs(r) >= abs(obs) - 1e-12:
            hits += 1
    if n == 0:
        return None
    return round((1.0 + hits) / (n + 1.0), 4)


def refuse_lookahead(asof_iso: str, window_start_iso: str) -> None:
    """Raise `LookaheadError` when data dated `asof_iso` would be used to
    measure a window that started on `window_start_iso`. PURE.

    It guards `>` ONLY. Same-day availability (a 10-Q filed after the close of
    the very day being measured) is NOT caught here and cannot be: the guard
    that excludes it is `strict=True` in the replay's `screen_asof`, which keeps
    rows with `avail < asof`. Every quoted cell runs strict.
    """
    a = str(asof_iso or "")[:10]
    w = str(window_start_iso or "")[:10]
    if a and w and a > w:
        raise LookaheadError(
            f"look-ahead: data as of {a} cannot measure a window starting {w}")


def period_age_days(period_end_iso: Optional[str],
                    asof_iso: Optional[str]) -> Optional[int]:
    """Calendar days from a fiscal quarter END to `asof`. PURE.

    None when either side is missing. There is deliberately NO `period_stale`
    flag here — a staleness cut would be a day threshold nobody owns; the days
    are printed and the reader sorts by them.
    """
    try:
        e = date.fromisoformat(str(period_end_iso)[:10])
        a = date.fromisoformat(str(asof_iso)[:10])
    except (TypeError, ValueError):
        return None
    return (a - e).days


# ═════════════════════════════════════════════════════════════════════════════
# The read-only database stand-in
# ═════════════════════════════════════════════════════════════════════════════
class _Refuse:
    """Every attribute raises. `first_seen.record` catches and returns 0."""

    def __init__(self, name: str):
        object.__setattr__(self, "_name", name)

    def __getattr__(self, item):
        raise RuntimeError(
            f"read-only: {object.__getattribute__(self, '_name')}.{item} "
            f"refused by NoWriteDB")

    def __setattr__(self, item, value):
        raise RuntimeError("read-only: NoWriteDB")


class NoWriteDB:
    """A db handle whose every collection refuses every method.

    `sepa.bonde.board(db=None)` WRITES `bonde_seen` through
    `first_seen.record` (`sepa/first_seen.py:56-80`), which swallows any
    exception and returns 0. Handing it this object is therefore a clean read
    of the board with no arrival stamp — verified before/after by reading
    `bonde_seen.PTGX.last_seen` in the run log.
    """

    def __getitem__(self, name):
        return _Refuse(str(name))

    def __getattr__(self, name):
        return _Refuse(str(name))


# ═════════════════════════════════════════════════════════════════════════════
# Data functions — container only, all I/O behind here
# ═════════════════════════════════════════════════════════════════════════════
def _db():
    """The app's own accessor, so this script cannot drift from it."""
    from growth.tracker import _db as tracker_db
    return tracker_db()


def growth_board_doc() -> dict:
    """The STORED 🚀 doc. `tracker.board()` is a pure read; `screen()`/`build()`
    write `growth_board` AND `growth_seen` and are never called here."""
    from growth import tracker
    return tracker.board() or {}


GROWTH_ROW_KEYS = ("symbol", "sales_growth_pct", "q_eps_growth_pct",
                   "sales_prior_pct", "price", "market_cap", "liquid",
                   "promo_tagged", "period_mismatch", "prior_hole",
                   "base_negative", "period", "period_end", "period_age_days",
                   "as_of", "sector", "industry")


def growth_members() -> list:
    """The served 🚀 rows, projected. `as_of` is the CACHE bar date and
    `period` is FISCAL — neither is the screen date."""
    doc = growth_board_doc()
    out = []
    for r in (doc.get("rows") or []):
        out.append({k: r.get(k) for k in GROWTH_ROW_KEYS})
    return out


def flag_dropped(rows: list) -> list:
    """Flag every row whose `last_seen` is not the cohort's LATEST stamp. PURE.

    The dropped test is against the cohort itself, NEVER against
    `growth_board.built_at`. `_record_seen` (`growth/tracker.py:504-535`) takes
    ONE clock read and writes that same string to every symbol in the build;
    `build()` then takes a SECOND clock read for `built_at` microseconds later.
    So every CURRENT member's `last_seen` sorts strictly below `built_at`
    (`...03:38:08.081177+00:00` < `...03:38:08.083000`) and a
    `last_seen < built_at` test flags the whole board as dropped — 29 of 29 on
    the live ledger, where the true answer is 8.

    Because one build writes one shared stamp, the cohort's own maximum IS that
    build's stamp, and a name re-stamped by it can never fall below it.

    `first_seen`/`last_seen` are ISO STRINGS (`sepa/first_seen.py:56-80`), so
    they compare lexically. A row with no `last_seen` at all was not stamped by
    the latest build and is dropped; if NO row carries a stamp there is no
    build to compare against and nothing is flagged.
    """
    out = [dict(r) for r in rows]
    stamps = [str(r.get("last_seen")) for r in out if r.get("last_seen")]
    latest = max(stamps) if stamps else None
    for r in out:
        r["dropped"] = bool(latest) and str(r.get("last_seen") or "") != latest
    return out


def growth_first_cohort() -> list:
    """The `growth_seen` cohort with its ISO stamps, flagged `dropped` when the
    name stopped being re-stamped by the board's latest build (`flag_dropped`).
    """
    db = _db()
    if db is None:
        return []
    rows = []
    for d in db["growth_seen"].find({"_id": {"$ne": "__meta__"}},
                                    {"_id": 1, "first_seen": 1, "last_seen": 1}):
        rows.append({
            "symbol": str(d["_id"]).upper(),
            "first_seen": d.get("first_seen"),
            "last_seen": d.get("last_seen"),
        })
    rows = flag_dropped(rows)
    rows.sort(key=lambda r: r["symbol"])
    return rows


def _iso(v) -> Optional[str]:
    """A datetime or an ISO string, as a comparable ISO string. PURE.

    A NAIVE datetime is read as UTC, never as local time: pymongo hands back
    naive UTC datetimes (`growth_board.built_at`) and the api container runs
    `TZ=America/New_York`, so `astimezone` on a naive value would shift the
    stamp by the local offset (03:38:08Z printing as 07:38:08Z).
    """
    if v is None:
        return None
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(v)


BONDE_ROW_KEYS = ("symbol", "tier", "growth_yoy_pct", "prior_yoy_pct",
                  "last_close", "base_state", "period", "period_ok")


def bonde_members(uncapped: bool = True) -> dict:
    """The 📈 board as served, plus the scan universe behind it.

    `uncapped=True` lifts `SECTION_CAP` IN PROCESS (restored in `finally`) so
    the full screen is visible: the served sections are capped 60/60/60/40/40
    AFTER the counts are taken (`sepa/bonde.py:626-628`), and the steady slice
    he sees is the top-40 of 666 by growth. Visible and uncapped are reported
    apart and the doc says which is which.

    ONE `scanner.load_latest()` call is made here, for the universe. `bonde.board`
    does its own read internally — that is bonde's code and it is untouched;
    both stamps are logged so a scan landing mid-run is visible rather than
    reconciled by hand.
    """
    from sepa import bonde, scanner

    scan = scanner.load_latest() or {}
    all_results = scan.get("all_results") or []
    universe = {
        "symbols": [str(r.get("symbol") or "").upper()
                    for r in all_results if r.get("symbol")],
        "generated_at": (scan.get("generated_at") or scan.get("finished_at")
                         or scan.get("started_at")),
        "n": len(all_results),
    }

    prior_caps = dict(bonde.SECTION_CAP)
    try:
        if uncapped:
            bonde.SECTION_CAP = {k: 10 ** 9 for k in bonde.SECTIONS}
        board = bonde.board(db=NoWriteDB())
    finally:
        bonde.SECTION_CAP = prior_caps

    sections = {}
    for name, rows in (board.get("sections") or {}).items():
        out = []
        for r in rows:
            row = {k: r.get(k) for k in BONDE_ROW_KEYS}
            row["section"] = name
            out.append(row)
        sections[name] = out
    return {
        "sections": sections,
        "counts": board.get("counts") or {},
        "caps": prior_caps,
        "uncapped": bool(uncapped),
        "n_pass": board.get("n_pass"),
        "n_period_mismatch": board.get("n_period_mismatch"),
        "scan_ts": board.get("scan_ts"),
        "universe": universe,
    }


def bonde_first_seen(symbols: Iterable[str]) -> dict:
    """`bonde_seen` first/last stamps for the given names. READ-ONLY find."""
    db = _db()
    syms = sorted({str(s).upper() for s in (symbols or []) if s})
    if db is None or not syms:
        return {}
    out = {}
    for d in db["bonde_seen"].find({"_id": {"$in": syms}},
                                   {"_id": 1, "first_seen": 1, "last_seen": 1}):
        out[str(d["_id"]).upper()] = {"first_seen": d.get("first_seen"),
                                      "last_seen": d.get("last_seen")}
    return out


def seen_probe(collection: str, symbol: str = "PTGX") -> Optional[str]:
    """`last_seen` of one name — the no-write proof, read before AND after."""
    db = _db()
    if db is None:
        return None
    try:
        d = db[collection].find_one({"_id": str(symbol).upper()},
                                    {"_id": 1, "last_seen": 1}) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("seen_probe %s failed: %s", collection, exc)
        return None
    return d.get("last_seen")


_PRICE_CACHE: dict = {}


def load_close(sym: str):
    """`(dates_iso, close, high)` for a symbol, memoised. None when unusable.

    Delisted names are refused by `symbols.is_delisted` (checked AS GIVEN) and
    renames are healed by `symbols.resolve` before the price read.
    """
    s = str(sym or "").upper()
    if not s:
        return None
    if s in _PRICE_CACHE:
        return _PRICE_CACHE[s]
    from sepa import prices, symbols as SYM
    out = None
    if not SYM.is_delisted(s):
        try:
            df = prices.load_prices(SYM.resolve(s))
        except Exception as exc:                                # noqa: BLE001
            log.warning("load_prices(%s) failed: %s", s, exc)
            df = None
        if df is not None and len(df) > 0:
            dates = [str(x)[:10] for x in df.index]
            out = (dates,
                   df["close"].to_numpy(dtype=float),
                   df["high"].to_numpy(dtype=float))
    _PRICE_CACHE[s] = out
    return out


def _period_index(fy, fp) -> Optional[int]:
    """`fy*4 + (q-1)`, exactly `bonde_audit/core.py:prep_fin`'s index. PURE."""
    f = str(fp or "").upper().strip()
    if not f.startswith("Q"):
        return None
    try:
        q = int(f[1:])
        if not 1 <= q <= 4:
            return None
        return int(fy) * 4 + (q - 1)
    except (TypeError, ValueError):
        return None


def filed_dates(fin_path: str = DEFAULT_FIN_PATH) -> dict:
    """Per symbol, the NEWEST quarter's `{filed, end, derived, fy, fp}`. PURE-ish
    (one file read, no network, no Mongo).

    `filed` is the SEC filing date of the 10-Q/10-K — NOT the press-release
    date. Press releases are not in this panel at all, which is why the column
    is `since_10q_filed_pct` and why "since the print" goes to NOT MEASURED.
    An unfiled quarter gets `end + 90d` with `derived=True`, the same
    assumption `core.prep_fin(derived="plus90")` makes.
    """
    try:
        with gzip.open(fin_path, "rt") as fh:
            fin = json.load(fh)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("filed_dates: %s unreadable: %s", fin_path, exc)
        return {}
    return filed_dates_from(fin)


def filed_dates_from(fin: dict) -> dict:
    """The pure half of `filed_dates`, over an already-loaded panel. PURE."""
    out = {}
    for sym, v in (fin or {}).items():
        best = None
        for q in ((v or {}).get("q") or []):
            p = _period_index(q.get("fy"), q.get("fp"))
            if p is None:
                continue
            filed = q.get("filed")
            end = q.get("end")
            derived = False
            if not filed:
                if not end:
                    continue
                try:
                    filed = (date.fromisoformat(str(end)[:10])
                             + timedelta(days=90)).isoformat()
                except ValueError:
                    continue
                derived = True
            if best is None or p > best[0]:
                best = (p, {"filed": str(filed)[:10], "end": str(end)[:10] if end else None,
                            "derived": derived, "fy": q.get("fy"), "fp": q.get("fp")})
        if best is not None:
            out[str(sym).upper()] = best[1]
    return out


# ═════════════════════════════════════════════════════════════════════════════
# Per-member metrics
# ═════════════════════════════════════════════════════════════════════════════
def member_metrics(dates: list, close, high, bench_dates: Optional[list],
                   bench_close) -> dict:
    """Every trailing column for one member, benchmarked BY CALENDAR DATE."""
    c = np.asarray(close, dtype=float)
    out: dict = {"last_date": dates[-1] if dates else None,
                 "last_close": _f(c[-1]) if c.size else None,
                 "n_bars": int(c.size)}
    for name, k in WINDOWS:
        r = trailing_return_pct(c, k)
        r = None if r is None else round(r, 2)
        out[f"ret_{name}_pct"] = r
        b = None
        if r is not None and bench_dates is not None and dates:
            start = dates[len(dates) - 1 - k]
            b = calendar_window_return_pct(bench_dates, bench_close,
                                           start, dates[-1])
            b = None if b is None else round(b, 2)
            out[f"win_{name}_start"] = start
        out[f"bench_{name}_pct"] = b
        # Relativised from the PRINTED numbers, so the CSV's three columns add
        # up: a `rel` computed off unrounded inputs disagrees with `ret - bench`
        # as the reader sees them by up to a basis point.
        out[f"rel_{name}_pp"] = relative_pp(r, b)
    pbh = pct_below_high(c)
    out["pct_below_high"] = None if pbh is None else round(pbh, 2)
    out["at_52w_high"] = (pbh is not None and pbh <= 0.0)
    out["within_near_high"] = (pbh is not None and pbh <= NEAR_HIGH_PCT)
    pbi = pct_below_intraday_high(high, c)
    out["pct_below_intraday_high"] = None if pbi is None else round(pbi, 2)
    return out


def filed_metrics(dates: list, close, info: Optional[dict],
                  asof_date: Optional[str] = None) -> dict:
    """`since_10q_filed_pct` (anchored at the first close STRICTLY AFTER the
    10-Q filing date) and `pre_filed_126_pct`.

    `pre_filed_126_pct` is the 126 bars BEFORE that anchor — it CONTAINS the
    earnings reaction and any pre-release run, and the doc's column note says
    so. It is not a clean "before the news" leg and must never be read as one.
    """
    out = {"filed": None, "filed_derived": None, "anchor_date": None,
           "anchor_close": None, "since_10q_filed_pct": None,
           "pre_filed_126_pct": None, "period_end": None,
           "period_age_days": None}
    if not info:
        return out
    out["filed"] = info.get("filed")
    out["filed_derived"] = bool(info.get("derived"))
    out["period_end"] = info.get("end")
    out["period_age_days"] = period_age_days(
        info.get("end"), asof_date or (dates[-1] if dates else None))
    anchor = first_close_after(dates, close, info.get("filed"))
    if anchor is None:
        return out
    a_date, a_close = anchor
    out["anchor_date"] = a_date
    out["anchor_close"] = round(a_close, 4)
    c = np.asarray(close, dtype=float)
    if a_close > 0 and c.size:
        out["since_10q_filed_pct"] = round((float(c[-1]) / a_close - 1) * 100.0, 2)
    i = dates.index(a_date)
    if i >= MOM_WINDOW_BARS:
        base = float(c[i - MOM_WINDOW_BARS])
        if base > 0:
            out["pre_filed_126_pct"] = round((a_close / base - 1) * 100.0, 2)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# Cohort summaries + Study B
# ═════════════════════════════════════════════════════════════════════════════
def universe_percentiles(rows: list, universe_rows: list) -> None:
    """Stamp `universe_pctile_<window>` on every row, in place.

    His standing rule: the benchmark that matters is the MEDIAN MEMBER, not the
    ETF (memory `feedback_track_sector_rotation`). The scan's `all_results` IS
    the universe, so a board member's percentile inside it is the direct read
    of "have these grown a great extent" — compared with what.
    """
    for name, _k in WINDOWS:
        key = f"ret_{name}_pct"
        pool = [r.get(key) for r in universe_rows]
        for r in rows:
            r[f"universe_pctile_{name}"] = percentile_of(pool, r.get(key))


def cohort_summary(name: str, rows: list, crdo_symbol: str = "CRDO") -> dict:
    """Every printed cohort line, with n and a CI on every median."""
    out: dict = {"cohort": name, "n": len(rows), "windows": {}}
    for wname, _k in WINDOWS:
        raw = [r.get(f"ret_{wname}_pct") for r in rows]
        rel = [r.get(f"rel_{wname}_pp") for r in rows]
        pct = [r.get(f"universe_pctile_{wname}") for r in rows]
        block = {
            "raw": distribution(raw),
            "raw_median_ci": median_ci(raw),
            "vs_rsp": distribution(rel),
            "vs_rsp_median_ci": median_ci(rel),
            "universe_pctile": distribution(pct),
            "universe_pctile_median_ci": median_ci(pct),
            "crdo_pctile_in_cohort": None,
        }
        crdo = next((r for r in rows if r.get("symbol") == crdo_symbol), None)
        if crdo is not None:
            block["crdo_pctile_in_cohort"] = percentile_of(raw, crdo.get(f"ret_{wname}_pct"))
            block["crdo_ret_pct"] = crdo.get(f"ret_{wname}_pct")
            block["crdo_universe_pctile"] = crdo.get(f"universe_pctile_{wname}")
        out["windows"][wname] = block

    pbh = [r.get("pct_below_high") for r in rows]
    out["pct_below_high"] = distribution(pbh)
    out["n_at_52w_high"] = sum(1 for r in rows if r.get("at_52w_high"))
    out["near_high_pct"] = NEAR_HIGH_PCT
    out["n_within_near_high"] = sum(1 for r in rows if r.get("within_near_high"))
    out["n_since_10q_filed_positive"] = sum(
        1 for r in rows if (_f(r.get("since_10q_filed_pct")) or 0) > 0)
    out["n_since_10q_filed_known"] = sum(
        1 for r in rows if r.get("since_10q_filed_pct") is not None)
    out["since_10q_filed_pct"] = distribution(
        [r.get("since_10q_filed_pct") for r in rows])
    out["pre_filed_126_pct"] = distribution(
        [r.get("pre_filed_126_pct") for r in rows])
    ages = [r.get("period_age_days") for r in rows]
    out["period_age_days"] = distribution(ages)
    out["n_no_prices"] = sum(1 for r in rows if not r.get("n_bars"))
    return out


B_SCREEN_KEYS = {
    "sales": ("sales_growth_pct", "growth_yoy_pct"),
    "eps": ("q_eps_growth_pct",),
}


def _screen_value(row: dict, keys: tuple) -> Optional[float]:
    for k in keys:
        if row.get(k) is not None:
            return _f(row.get(k))
    return None


def study_b_table(name: str, rows: list) -> dict:
    """Study B-trailing: does the SCREEN NUMBER track the trailing run?"""
    out = {"cohort": name, "rule_of_reading": B_RULE_OF_READING, "legs": {}}
    for leg, keys in B_SCREEN_KEYS.items():
        xs = [_screen_value(r, keys) for r in rows]
        if all(v is None for v in xs):
            continue
        leg_out = {}
        targets = [(f"ret_{w}_pct", w) for w, _k in WINDOWS]
        targets.append(("since_10q_filed_pct", "since_10q_filed"))
        for key, label in targets:
            ys = [r.get(key) for r in rows]
            rho = spearman_rho(xs, ys)
            lo, hi = spearman_ci(xs, ys)
            leg_out[label] = {
                "n": int(_paired(xs, ys)[0].size),
                "rho": rho, "ci": [lo, hi],
                "perm_p": perm_p(xs, ys) if rho is not None else None,
            }
        out["legs"][leg] = leg_out
    return out


def reading_sentence(summary: dict, b_table: dict) -> str:
    """The doc's fill-in sentence, either branch, no verdict word."""
    w = (summary.get("windows") or {}).get("3m") or {}
    b = (((b_table.get("legs") or {}).get("sales") or {}).get("3m")) or {}
    rho, ci, n = b.get("rho"), b.get("ci") or [None, None], b.get("n")
    tracks = (rho is not None and ci[0] is not None
              and ((ci[0] > 0 and ci[1] > 0) or (ci[0] < 0 and ci[1] < 0)))
    pct = (w.get("universe_pctile") or {}).get("median")
    pci = w.get("universe_pctile_median_ci") or [None, None]
    return (
        f"The {summary.get('cohort')} screen number "
        f"{'does' if tracks else 'does not'} track the trailing 3m return "
        f"(rho {rho} [{ci[0]},{ci[1]}], n {n}); the board's median member sits "
        f"at the {pct}th percentile of the scan universe over 3m "
        f"[{pci[0]},{pci[1]}]; "
        f"{'the board is a look-back mirror' if tracks else 'his impression comes from the right tail'}."
    )


# ═════════════════════════════════════════════════════════════════════════════
# Stage: members
# ═════════════════════════════════════════════════════════════════════════════
def _cohorts(growth_rows: list, growth_cohort: list, bonde: dict,
             arrivals: set) -> dict:
    """The cohorts of §3.1, each a list of `{symbol, **screen columns}`."""
    sections = bonde.get("sections") or {}
    caps = bonde.get("caps") or {}

    def visible(section):
        cap = caps.get(section)
        rows = sections.get(section) or []
        return rows[:cap] if cap else rows

    cohorts = {
        "universe_all": [{"symbol": s} for s in (bonde.get("universe") or {}).get("symbols", [])],
        "growth_21": [dict(r) for r in growth_rows],
        "growth_first_29": [dict(r) for r in growth_cohort],
        "bonde_visible_explosive": [dict(r) for r in visible("explosive")],
        "bonde_visible_strong": [dict(r) for r in visible("strong")],
        "bonde_visible_steady": [dict(r) for r in visible("steady")],
        "bonde_uncapped_explosive": [dict(r) for r in (sections.get("explosive") or [])],
        "bonde_uncapped_strong": [dict(r) for r in (sections.get("strong") or [])],
        "bonde_uncapped_steady": [dict(r) for r in (sections.get("steady") or [])],
        "bonde_rejected": [dict(r) for r in (sections.get("rejected") or [])],
    }
    seen = set()
    vis_all = []
    for k in ("bonde_visible_explosive", "bonde_visible_strong",
              "bonde_visible_steady"):
        for r in cohorts[k]:
            if r["symbol"] not in seen:
                seen.add(r["symbol"])
                vis_all.append(dict(r))
    cohorts["bonde_visible_all"] = vis_all
    by_sym = {r["symbol"]: r for r in (sections.get("explosive") or [])
              + (sections.get("strong") or []) + (sections.get("steady") or [])}
    cohorts["bonde_arrivals_27"] = [dict(by_sym.get(s, {"symbol": s}))
                                    for s in sorted(arrivals)]
    return cohorts


def run_members(out_csv: Optional[str], out_json: Optional[str],
                fin_path: str = DEFAULT_FIN_PATH,
                bench: str = BENCHMARK, uncapped: bool = True) -> dict:
    """Study A + B-trailing over the served boards. All I/O lives here."""
    run_started = datetime.now(timezone.utc).isoformat()
    print(HEADER, flush=True)
    print(PRICE_CACHE_NOTE, flush=True)

    probe_before = {c: seen_probe(c) for c in ("bonde_seen", "growth_seen")}
    print(f"no-write probe BEFORE: {probe_before}", flush=True)

    growth_doc = growth_board_doc()
    growth_built_at = _iso(growth_doc.get("built_at"))
    growth_rows = growth_members()
    growth_cohort = growth_first_cohort()
    bonde = bonde_members(uncapped=uncapped)
    scan_generated_at = _iso((bonde.get("universe") or {}).get("generated_at"))
    print(f"growth_board.built_at = {growth_built_at} (stamp verbatim; "
          f"the writer is not identified by this script)", flush=True)
    print(f"scan generated_at = {scan_generated_at}; universe n = "
          f"{(bonde.get('universe') or {}).get('n')}", flush=True)

    seen_map = bonde_first_seen([r["symbol"] for v in (bonde.get("sections") or {}).values()
                                 for r in v])
    tracking = sorted({v.get("first_seen") for v in seen_map.values() if v.get("first_seen")})
    day_one = tracking[0] if tracking else None
    arrivals = {s for s, v in seen_map.items()
                if day_one and str(v.get("first_seen") or "") > day_one}

    cohorts = _cohorts(growth_rows, growth_cohort, bonde, arrivals)

    b = load_close(bench)
    if b is None:
        raise RuntimeError(f"benchmark {bench} has no price frame")
    bench_dates, bench_close, _bh = b
    fin = filed_dates(fin_path)

    n_delisted = 0
    n_no_fin = 0
    for name, rows in cohorts.items():
        for r in rows:
            frame = load_close(r["symbol"])
            if frame is None:
                r["n_bars"] = 0
                n_delisted += 1
                continue
            dates, close, high = frame
            r.update(member_metrics(dates, close, high, bench_dates, bench_close))
            info = fin.get(str(r["symbol"]).upper())
            if info is None:
                n_no_fin += 1
            r.update(filed_metrics(dates, close, info))

    universe_rows = cohorts["universe_all"]
    for name, rows in cohorts.items():
        universe_percentiles(rows, universe_rows)

    summaries = {name: cohort_summary(name, rows) for name, rows in cohorts.items()}
    b_tables = {name: study_b_table(name, rows) for name, rows in cohorts.items()
                if name != "universe_all"}

    probe_after = {c: seen_probe(c) for c in ("bonde_seen", "growth_seen")}
    print(f"no-write probe AFTER : {probe_after}", flush=True)
    if probe_before != probe_after:
        print("!! LEDGER CHANGED DURING THE RUN — the no-write proof FAILED",
              flush=True)

    payload = {
        "header": HEADER,
        "stage": "members",
        "benchmark": bench,
        "windows": [{"name": n, "bars": k} for n, k in WINDOWS],
        "near_high_pct": NEAR_HIGH_PCT,
        "screen": {"min_sales_growth_pct": MIN_SALES_GROWTH_PCT,
                   "min_eps_growth_pct": MIN_EPS_GROWTH_PCT,
                   "min_prior_sales_pct": MIN_PRIOR_SALES_PCT,
                   "sales_floor_pct": SALES_FLOOR_PCT,
                   "sales_preferred_pct": SALES_PREFERRED_PCT,
                   "sales_explosive_pct": SALES_EXPLOSIVE_PCT},
        "cohorts": summaries,
        "study_b": b_tables,
        "sentences": {name: reading_sentence(summaries[name], b_tables[name])
                      for name in b_tables},
        "counts": {"bonde": bonde.get("counts"), "n_pass": bonde.get("n_pass"),
                   "n_period_mismatch": bonde.get("n_period_mismatch"),
                   "bonde_arrivals": sorted(arrivals),
                   "bonde_day_one_stamp": day_one,
                   "n_symbols_without_prices": n_delisted,
                   "n_symbols_without_fin": n_no_fin},
        "notes": {"price_cache": PRICE_CACHE_NOTE,
                  "pre_filed_126": ("contains the earnings reaction and any "
                                    "pre-release run"),
                  "filed": ("SEC 10-Q/10-K filing date; press-release / 8-K "
                            "dates are not in this panel")},
        "inputs": {
            "growth_built_at": growth_built_at,
            "scan_generated_at": scan_generated_at,
            "bonde_seen_probe_before": probe_before.get("bonde_seen"),
            "bonde_seen_probe_after": probe_after.get("bonde_seen"),
            "growth_seen_probe_before": probe_before.get("growth_seen"),
            "growth_seen_probe_after": probe_after.get("growth_seen"),
            "fin_path": fin_path,
            "run_started": run_started,
            "run_finished": datetime.now(timezone.utc).isoformat(),
        },
    }

    if out_json:
        with open(out_json, "w") as fh:
            json.dump(payload, fh, indent=1, default=str)
        print(f"wrote {out_json}", flush=True)
    if out_csv:
        write_members_csv(out_csv, cohorts)
        print(f"wrote {out_csv}", flush=True)
    for name in sorted(b_tables):
        print(f"  {payload['sentences'][name]}", flush=True)
    return payload


def write_members_csv(path: str, cohorts: dict) -> int:
    """One row per (cohort, symbol) with every column. Returns rows written."""
    rows = []
    for name, members in cohorts.items():
        for r in members:
            row = dict(r)
            row["cohort"] = name
            rows.append(row)
    keys = ["cohort", "symbol"]
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", default="members", choices=("members",))
    ap.add_argument("--out", default=None, help="members CSV")
    ap.add_argument("--json", dest="json_path", default=None)
    ap.add_argument("--fin", default=DEFAULT_FIN_PATH)
    ap.add_argument("--bench", default=BENCHMARK)
    ap.add_argument("--uncapped", dest="uncapped", action="store_true", default=True)
    ap.add_argument("--capped-only", dest="uncapped", action="store_false")
    args = ap.parse_args(argv)
    run_members(args.out, args.json_path, fin_path=args.fin,
                bench=args.bench, uncapped=args.uncapped)
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    logging.basicConfig(level=os.getenv("LOGLEVEL", "INFO"))
    raise SystemExit(main())
