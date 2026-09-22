"""Board-growth AS-OF REPLAY (Study C) — 🚀 100/100 screen and 📈 Bonde tiers,
measured forward on the audit panel. Plus the thin live-forward description.

NOT A SIGNAL, NOT A GATE — research only (Rule #10). Nothing here changes a
board, a rule or a threshold, and no number printed here is tradable on its own.

WHAT THIS ANSWERS. Ajay, 2026-09-21: "I felt like all the explosive growth
stocks and Bondes stocks have grown a great extent I exited the CRDO today".
The 100/100 screen (`growth/tracker.py`) has NEVER been measured forward. The
Bonde sales tiers HAVE been (`sepa/bonde.py:MEASURED`, from
`scripts/bonde_audit/attack.py`) — so this script first REPRODUCES that
measurement bar-for-bar, and only then quotes the new cells: the 100/100 screen,
ARRIVAL vs INCUMBENT, and both split by 6-month momentum quintile (the "do the
members that already ran revert" read).

ENGINE REUSE. The point-in-time state and the clustered bootstrap are
`scripts/bonde_audit/core.py`, PATH-LOADED, never copied and never edited —
`core.state_asof`, `core.Cell/build_index/boot/boot_dates/ci/med/mean/win`.
`attack.py` and `lane2.py` are the pinned authority behind `bonde.MEASURED`;
they are read, reproduced, and left alone.

LOOK-AHEAD. Every quoted cell runs `strict=True`: a filing whose availability
date EQUALS the cross-section is excluded, because `filed` is the 10-Q/10-K
filing date and an after-close filing is not tradable that day. `strict=False`
(core's own default, and attack.py's convention) exists ONLY inside
`--stage repro`, under its own header, and is never a quoted cell.
`refuse_lookahead` guards `>` only; equality is `strict`'s job.

RUN (container; the caches and the Massive key live only there, and the three
board_growth_* scripts do not exist on `main` inside /app):

    docker exec -i cheetah-market-app-api-1 sh -c \\
        'mkdir -p /tmp/scripts && cat > /tmp/scripts/board_growth_replay.py' \\
        < backend/scripts/board_growth_replay.py
    docker exec -w /app cheetah-market-app-api-1 sh -c \\
        'PYTHONPATH=/tmp:/app python -u -m scripts.board_growth_replay --stage repro'
    docker exec -d -w /app cheetah-market-app-api-1 sh -c \\
        'PYTHONPATH=/tmp:/app python -u -m scripts.board_growth_replay --stage replay \\
         --json /tmp/board_growth_replay.json --panel /tmp/board_growth_panel.csv \\
         > /tmp/board_growth_replay.log 2>&1'
    docker cp cheetah-market-app-api-1:/tmp/board_growth_replay.json <scratch>/

`-m scripts.<module>` from `-w /app` with `PYTHONPATH=/tmp:/app` is the only run
form that works: `scripts` is a PEP 420 namespace package, so `/tmp/scripts` and
`/app/scripts` merge and both `scripts.board_growth_study` and
`scripts.bonde_audit` resolve. A bare `python /tmp/scripts/x.py` puts
`/tmp/scripts` on `sys.path[0]` instead and the cross-imports fail.

Heavy stages run OUTSIDE RTH (09:30-16:00 ET).
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import logging
import math
import os
import pathlib
import sys
from typing import Optional

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from growth.tracker import (MIN_EPS_GROWTH_PCT, MIN_PRIOR_SALES_PCT,        # noqa: E402
                            MIN_SALES_GROWTH_PCT)
from rotation.backtest import BENCHMARK, LOOKBACK, REBALANCE                # noqa: E402
from sepa import qoq as qoq_mod                                            # noqa: E402
from sepa import sales as sales_mod                                        # noqa: E402
from sepa.bonde import MEASURED as BONDE_MEASURED                          # noqa: E402
from sepa.qoq import HEADLINE_PAIR, PRIOR_PAIR                             # noqa: E402

log = logging.getLogger("board_growth_replay")

HEADER = "NOT A SIGNAL, NOT A GATE — research only (Rule #10)"

# ── cross-script import (PERMANENT fallback; see the run block above) ────────
# `scripts.board_growth_study` is a sibling file that only exists under
# /tmp/scripts in the container. When the run form is wrong (or a test imports
# this module standalone) the two names are defined locally with the SAME
# bodies. This fallback is permanent by design — there is no TODO to remove it.
try:                                                        # pragma: no cover
    from scripts.board_growth_study import (LookaheadError,                # noqa: E402
                                            refuse_lookahead)
except ImportError:                                         # pragma: no cover
    class LookaheadError(RuntimeError):
        """A window that would have been measured before its own data existed."""

    def refuse_lookahead(asof_iso: str, window_start_iso: str) -> None:
        """Raise `LookaheadError` when data dated `asof_iso` would be used to
        measure a window that started on `window_start_iso`. PURE.

        It guards `>` ONLY. Same-day availability (a 10-Q filed after the close
        of the very day being measured) is NOT caught here and cannot be: the
        guard that excludes it is `strict=True` in the replay's `screen_asof`,
        which keeps rows with `avail < asof`. Every quoted cell runs strict.
        """
        a = str(asof_iso or "")[:10]
        w = str(window_start_iso or "")[:10]
        if a and w and a > w:
            raise LookaheadError(
                f"look-ahead: data as of {a} cannot measure a window starting {w}")

# ── panel conventions, every one cited ──────────────────────────────────────
ANCH = {"SPY", "QQQ", "IWM"}          # attack.py:38 / lane2.py:41 — benchmarks, not members
PANEL_STEP = REBALANCE                # attack.py:42 `cal[::21]` == rotation REBALANCE
MOM_BARS = 126                        # lane2.py:65 — the 6-month momentum window
DV_BARS = 50                          # lane2.py:64 — trailing dollar-volume median
MIN_BAR_INDEX = 60                    # attack.py:51 / lane2.py:57 `if i is None or i < 60`
H_WINDOWS = (REBALANCE, LOOKBACK, MOM_BARS)      # 21 / 63 / 126 sessions
QUINTILE_EDGES = (20, 40, 60, 80)     # lane2.py:154,175 `np.percentile(x,[20,40,60,80])`
TRIM_TOP_PCT = 5.0                    # attack.py's tail trim, reported beside the mean

# The study's own resolution floor for a placebo stratum — how many comparable
# names a cell needs before its median means anything. Not a tradable gate and
# not a threshold anyone owns; it only decides which fallback level is used,
# and the level is recorded on every event.
MIN_STRATUM = 5

# The live-forward leg (§1.2 ledger facts). 09-14 is both the audit-fin fetch
# date (filings through 09-13 only) and the first close after the growth_seen
# stamp (Saturday 2026-09-12 15:51 ET) and the bonde_seen stamp (09-14 03:46Z).
LIVE_ASOF = "2026-09-14"
LIVE_ENTRY_DATE = "2026-09-14"
LIVE_EXIT_DATE = "2026-09-21"

CORE_CANDIDATES = (
    pathlib.Path(__file__).resolve().parent / "bonde_audit" / "core.py",
    pathlib.Path("/app/scripts/bonde_audit/core.py"),
    pathlib.Path("/root/.cheetah/aud/core.py"),
)

_CORE = None


def load_core():
    """Path-load `bonde_audit/core.py` (the audit's own engine), never a copy.

    The three candidates are byte-identical today; the first that exists wins.
    `core.load()` is NOT called here — importing the file touches no cache.
    """
    global _CORE
    if _CORE is not None:
        return _CORE
    for path in CORE_CANDIDATES:
        if path.exists():
            spec = importlib.util.spec_from_file_location("bonde_audit_core", str(path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.__core_path__ = str(path)
            _CORE = mod
            return _CORE
    raise RuntimeError("bonde_audit/core.py not found in %s"
                       % ", ".join(str(p) for p in CORE_CANDIDATES))


# ── pure helpers ─────────────────────────────────────────────────────────────
def _pos(x) -> bool:
    """True only when the value is present and strictly positive."""
    try:
        return x is not None and float(x) > 0
    except (TypeError, ValueError):
        return False


def asof_rows(rec, asof_iso: str, strict: bool = True, n: int = 8):
    """(revs, epss, newest_avail) as of `asof_iso`, densified by fiscal period.

    The SAME arithmetic as `core.state_asof`'s `align="period"` branch
    (core.py:84-97): availability filter `< asof` when strict, `<= asof`
    otherwise; newest row per period index wins; slots walk backwards by period
    so a missing quarter is a `None` HOLE, never a shifted neighbour.

    None exactly when `core.state_asof` is None — fewer than 5 available rows,
    or a series `sales.compute` cannot score.
    """
    rows = list(rec or [])
    if strict:
        av = [r for r in rows if r[0] < asof_iso]
    else:
        av = [r for r in rows if r[0] <= asof_iso]
    if len(av) < 5:
        return None
    best = {}
    for a, p, rev, eps, _filed in av:
        if p not in best or a > best[p][0]:
            best[p] = (a, rev, eps)
    p0 = max(best)
    revs = [(best[p0 - j][1] if (p0 - j) in best else None) for j in range(n)]
    epss = [(best[p0 - j][2] if (p0 - j) in best else None) for j in range(n)]
    newest_avail = best[p0][0]
    # `core.state_asof` refuses an unscorable series; mirror that exactly so the
    # None-ness of the two functions is identical (pinned by test).
    if sales_mod.compute(revs, qoq_mod.yoy_pct(epss)).get("score") is None:
        return None
    return revs, epss, newest_avail


def screen_asof(rec, asof_iso: str, strict: bool = True) -> Optional[dict]:
    """Point-in-time 🚀 screen legs + 📈 Bonde state for one symbol.

    The 100/100 legs are the SHIPPED arithmetic: `sales.compute` for the top
    line, `qoq.yoy_pct` (which divides by |b|) for EPS, the tracker's own
    constants for the cuts. The Bonde five come straight from
    `core.state_asof` — one engine, not a re-implementation.

    `passes_100_100` reproduces the shipped rule INCLUDING its known hole: an
    EPS leg computed off a NEGATIVE year-ago base passes (the tracker checks
    the revenue base at :220-228 and never the EPS base). `passes_100_100_epsbase`
    is the sensitivity that refuses it. The shipped one is the quoted cell.

    `strict=True` on every quoted cell: a filing available ON `asof_iso` is a
    pre-print entry for an after-close filing, and only `strict` excludes it.
    """
    core = load_core()
    got = asof_rows(rec, asof_iso, strict=strict)
    if got is None:
        return None
    revs, epss, newest_avail = got
    st = core.state_asof(rec, asof_iso, align="period", strict=strict)
    if st is None:
        return None
    refuse_lookahead(newest_avail, asof_iso)
    eps_yoy = qoq_mod.yoy_pct(epss)
    sales = sales_mod.compute(revs, eps_yoy)
    sales_yoy = sales.get("growth_yoy_pct")
    prior_yoy = sales.get("prior_yoy_pct")
    base_ok = _pos(revs[HEADLINE_PAIR[1]]) and _pos(revs[PRIOR_PAIR[1]])
    eps_base = epss[HEADLINE_PAIR[1]]
    eps_base_negative = eps_base is not None and float(eps_base) < 0
    passes = bool(sales_yoy is not None and sales_yoy >= MIN_SALES_GROWTH_PCT
                  and eps_yoy is not None and eps_yoy >= MIN_EPS_GROWTH_PCT
                  and prior_yoy is not None and prior_yoy > MIN_PRIOR_SALES_PCT
                  and base_ok)
    return {
        "sales_yoy": sales_yoy,
        "prior_yoy": prior_yoy,
        "eps_yoy": eps_yoy,
        "base_ok": bool(base_ok),
        "eps_base_negative": bool(eps_base_negative),
        "passes_100_100": passes,
        "passes_100_100_epsbase": bool(passes and not eps_base_negative),
        "tier": st.get("tier"),
        "bonde_pass": bool(st.get("bonde_pass")),
        "cleared_floor": bool(st.get("cleared_floor")),
        "character": bool(st.get("character")),
        "stale_days": st.get("stale_days"),
        "newest_avail": newest_avail,
    }


def forward_pct(close, i: int, k: int) -> Optional[float]:
    """attack.py:53 forward return in percent: `(c[i+k]-c[i])/c[i]*100`.

    None past the end of the frame — never wraps, never borrows a bar.
    """
    c = close
    if i is None or i < 0 or i + k >= len(c):
        return None
    base = float(c[i])
    if base <= 0:
        return None
    return (float(c[i + k]) - base) / base * 100.0


def quintile_edges(values) -> Optional[np.ndarray]:
    """lane2.py:154/175 quintile edges — `np.percentile(x, [20,40,60,80])`."""
    vals = [float(v) for v in values if v is not None and not _isnan(v)]
    if not vals:
        return None
    return np.percentile(vals, list(QUINTILE_EDGES))


def _isnan(v) -> bool:
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return True


def mom_quintile(mom, edges) -> Optional[int]:
    """6-month momentum quintile 1..5 against lane2's edges.

    lane2's convention is `np.searchsorted(edges, x)` with the default
    side="left", so a value sitting EXACTLY on an edge falls into the LOWER
    bin (edges [10,20,30,40], x=20 -> index 1 -> quintile 2, the [10,20] bin).
    Stated rather than changed: the control must match lane2 bar-for-bar.
    """
    if mom is None or edges is None or _isnan(mom):
        return None
    return int(np.searchsorted(np.asarray(edges, dtype=float), float(mom))) + 1


def stratum_key(sector, dv, dv_edges) -> tuple:
    """(sector, dollar-volume quintile) — the placebo stratum's symbol axis."""
    if dv is None or dv_edges is None or _isnan(dv):
        return (sector, None)
    return (sector, int(np.searchsorted(np.asarray(dv_edges, dtype=float), float(dv))) + 1)


def excess_vs_stratum(rows, k: int, min_stratum: int = MIN_STRATUM) -> list:
    """Event excess vs the SAME date's scored non-cell names.

    Stratum order: (date, sector, dv-quintile) -> (date, dv-quintile) -> date.
    A level with fewer than `min_stratum` comparables falls through, and the
    level actually used is recorded on the event. `rows` carry `cell` (bool),
    `date`, `sector`, `dvq`, and `r[k]`.
    """
    by_sd: dict = {}
    by_dv: dict = {}
    by_date: dict = {}
    for r in rows:
        v = (r.get("r") or {}).get(k)
        if v is None or r.get("cell"):
            continue
        by_sd.setdefault((r.get("date"), r.get("sector"), r.get("dvq")), []).append(v)
        by_dv.setdefault((r.get("date"), r.get("dvq")), []).append(v)
        by_date.setdefault(r.get("date"), []).append(v)
    out = []
    for idx, r in enumerate(rows):
        if not r.get("cell"):
            continue
        v = (r.get("r") or {}).get(k)
        if v is None:
            continue
        chosen = None
        for level, pool in (("sector_dv", by_sd.get((r.get("date"), r.get("sector"), r.get("dvq")))),
                            ("dv", by_dv.get((r.get("date"), r.get("dvq")))),
                            ("date", by_date.get(r.get("date")))):
            if pool and len(pool) >= min_stratum:
                chosen = {"i": idx, "excess": float(v) - float(np.median(pool)), "level": level}
                break
        out.append(chosen or {"i": idx, "excess": None, "level": "none"})
    return out


def momentum_bucket_means(scored, k: int) -> dict:
    """lane2.py:157-160 — the ALL_SCORED MEAN forward return per 6m-momentum
    quintile, keyed 1..5.

    `bmu[b] = np.mean([r["r"][k] for r in sm if bucket(r) == b])` in lane2, with
    `sm` = the scored bars that have BOTH a momentum and a forward return. A bar
    with no `momq` (fewer than `MOM_BARS` of history) or no `r[k]` belongs to no
    bucket; an empty bucket is simply absent from the mapping.
    """
    pools: dict = {}
    for r in scored:
        q = r.get("momq")
        v = (r.get("r") or {}).get(k)
        if q is None or v is None:
            continue
        pools.setdefault(int(q), []).append(float(v))
    return {q: float(np.mean(v)) for q, v in sorted(pools.items()) if v}


def momentum_residuals(cell_rows, k: int, bucket_means: dict) -> list:
    """lane2.py:161-165 — `r["r"][k] - bmu[bucket(r)]` for the cell's bars.

    The WITHIN-QUINTILE residual: what the cell did against the rest of the
    SAME 6-month-momentum bucket of the scored universe, which is the control
    for "these names had already run". A bar with no quintile, no forward
    return, or an empty bucket is dropped (the caller counts the drops) rather
    than residualised against nothing.
    """
    out = []
    for r in cell_rows:
        q = r.get("momq")
        v = (r.get("r") or {}).get(k)
        mu = bucket_means.get(int(q)) if q is not None else None
        if q is None or v is None or mu is None:
            continue
        out.append({"sym": r.get("sym"), "date": r.get("date"),
                    "momq": int(q), "resid": float(v) - float(mu)})
    return out


def arrival_flag(prev_state, cur_state, key: str = "passes_100_100") -> Optional[str]:
    """"arrive" | "incumbent" | None for one symbol between two cross-sections.

    A previous cross-section that could not be SCORED is not a transition — a
    data hole is not an arrival — so `prev_state is None` gives None, never
    "arrive".
    """
    if not cur_state or not cur_state.get(key):
        return None
    if prev_state is None:
        return None
    return "incumbent" if prev_state.get(key) else "arrive"


def bench_by_date(bench_dates, bench_close, d0: str, dk: str) -> Optional[float]:
    """Benchmark (RSP) return over the member's own CALENDAR dates.

    The audit price pickle has no RSP, so the benchmark is aligned by DATE, not
    by bar count. None when either date has no benchmark bar (the first
    sessions of the panel window).
    """
    if not bench_dates or bench_close is None:
        return None
    key = (len(bench_dates), bench_dates[0], bench_dates[-1])
    cache = getattr(bench_by_date, "_cache", None)
    if cache is None:
        cache = bench_by_date._cache = {}
    pos = cache.get(key)
    if pos is None:
        pos = cache[key] = {d: i for i, d in enumerate(bench_dates)}
    i0, ik = pos.get(d0), pos.get(dk)
    if i0 is None or ik is None:
        return None
    b0 = float(bench_close[i0])
    if b0 <= 0:
        return None
    return (float(bench_close[ik]) - b0) / b0 * 100.0


def boot_blocks(cells, stats, ndate: int, block: int, B: int = 1000, seed: int = 11):
    """Moving-BLOCK bootstrap over date clusters — the honest CI at h > 21.

    Cross-sections are 21 sessions apart, so a 63-day forward overlaps 3 of
    them and a 126-day forward 6. `core.boot_dates` resamples single dates and
    is optimistic there; this draws contiguous blocks of `block = h // 21`
    cross-sections instead.

    At `block == 1` the draw collapses to `rng.integers(0, ndate, ndate)` and
    the output is ELEMENT-WISE EQUAL to `core.boot_dates` under the same seed
    (pinned by test). Raises when `block` is outside 1..ndate.
    """
    core = load_core()
    block = int(block)
    ndate = int(ndate)
    if block < 1:
        raise ValueError("block must be >= 1, got %r" % block)
    if block > ndate:
        raise ValueError("block %d exceeds the %d cross-sections" % (block, ndate))
    rng = np.random.default_rng(seed)
    prep = core.build_index(cells, ndate)
    nblocks = int(math.ceil(ndate / block))
    out = np.full((B, len(cells), len(stats)), np.nan)
    for b in range(B):
        starts = rng.integers(0, ndate - block + 1, nblocks)
        if block == 1:
            draw = starts
        else:
            draw = (starts[:, None] + np.arange(block)[None, :]).reshape(-1)[:ndate]
        for ci, (vv, bounds) in enumerate(prep):
            lens = bounds[draw + 1] - bounds[draw]
            tot = int(lens.sum())
            if tot == 0:
                continue
            starts_i = bounds[draw]
            ii = (np.repeat(starts_i, lens)
                  + (np.arange(tot) - np.repeat(np.cumsum(lens) - lens, lens)))
            x = vv[ii]
            for si, f in enumerate(stats):
                out[b, ci, si] = f(x)
    return out


def subpanel_offsets(dates_idx, block: int) -> list:
    """The `block` NON-OVERLAPPING sub-panels of a cross-section list.

    Printed beside the block-bootstrap CI as a cross-check (each sub-panel has
    no overlapping forward windows at all), never quoted on its own — it throws
    away (block-1)/block of the panel.
    """
    block = int(block)
    if block < 1:
        raise ValueError("block must be >= 1, got %r" % block)
    idx = list(dates_idx)
    return [idx[off::block] for off in range(block)]


def repro_ok(scored_bars, med_expl, med_scored) -> bool:
    """The reproduction gate: does this panel still BE attack.py's panel?

    Both targets are imported from `sepa.bonde.MEASURED` — the shipped numbers,
    never retyped. Exact: the scored-bar count and the 2-dp median lift.
    """
    try:
        bars_ok = int(scored_bars) == int(BONDE_MEASURED["panel_bars"])
        med_ok = round(float(med_expl) - float(med_scored), 2) == BONDE_MEASURED["tier_explosive_med"]
    except (TypeError, ValueError):
        return False
    return bool(bars_ok and med_ok)


def sanitize(obj):
    """NaN/Inf -> None, numpy scalars -> python. A bootstrap CI on an empty
    resample is `nan`, and `json.dumps` writes a bare `NaN`, which is not JSON.
    Every stage result goes through this before it is written or compared."""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def trimmed_mean(vals, top_pct: float = TRIM_TOP_PCT) -> Optional[float]:
    """attack.py's tail trim — the mean after dropping the top `top_pct`%."""
    a = np.asarray([v for v in vals if v is not None], dtype=float)
    a = a[~np.isnan(a)]
    if len(a) == 0:
        return None
    cut = np.percentile(a, 100.0 - top_pct)
    kept = a[a <= cut]
    return float(np.mean(kept)) if len(kept) else None


# ── panel ────────────────────────────────────────────────────────────────────
def build_panel(px, recs, dates, windows=H_WINDOWS, state_fn=None,
                sectors=None, anchors=ANCH, min_bar_index=MIN_BAR_INDEX):
    """attack.py:36-51 / lane2.py:39-66, reproduced: the cross-section panel.

    One row per (symbol, cross-section) with the entry bar, the forward returns,
    the trailing dollar-volume median, the 6-month momentum, and the point-in-
    time state. Bars with `i < min_bar_index` are SKIPPED — attack.py's own
    convention, and the reason the effective panel is 21 cross-sections, not 24.
    """
    if state_fn is None:
        def state_fn(rec, dt):
            return screen_asof(rec, dt, strict=True)
    sectors = sectors or {}
    rows = []
    for sym, P in px.items():
        if sym in anchors:
            continue
        d = list(P["d"])
        c = np.asarray(P["c"], dtype=float)
        v = np.asarray(P["v"], dtype=float)
        pos = {dd: i for i, dd in enumerate(d)}
        rec = recs.get(sym)
        for dt in dates:
            i = pos.get(dt)
            if i is None or i < min_bar_index:
                continue
            st = state_fn(rec, dt) if rec else None
            lo = max(0, i - DV_BARS)
            dv = float(np.median(c[lo:i] * v[lo:i])) if i > lo else None
            mom = (float((c[i] - c[i - MOM_BARS]) / c[i - MOM_BARS] * 100.0)
                   if i >= MOM_BARS and c[i - MOM_BARS] > 0 else None)
            rows.append({
                "sym": sym, "date": dt, "i": i, "price": float(c[i]),
                "sector": sectors.get(sym), "dv": dv, "mom": mom, "st": st,
                "r": {k: forward_pct(c, i, k) for k in windows},
                "exit_date": {k: (d[i + k] if i + k < len(d) else None) for k in windows},
            })
    return rows


def _ids(rows, field: str) -> tuple:
    ids: dict = {}
    for r in rows:
        key = r[field]
        if key not in ids:
            ids[key] = len(ids)
    return ids, len(ids)


def _cell_stats(core, vals) -> dict:
    a = np.asarray([v for v in vals if v is not None], dtype=float)
    a = a[~np.isnan(a)]
    return {
        "n": int(len(a)),
        "median": core.med(a) if len(a) else None,
        "mean": core.mean(a) if len(a) else None,
        "win_pct": core.win(a) if len(a) else None,
        "mean_trimmed": trimmed_mean(a),
    }


# ── stages ───────────────────────────────────────────────────────────────────
def run_repro(px, recs, dates, B: int = 500, seed: int = 7) -> dict:
    """attack.py convention — same-day filings INCLUDED (strict=False).

    REPRODUCTION ONLY, never quoted as a cell. `core.state_asof` is called with
    its DEFAULTS (strict=False, align="period") and `derived="plus90"`, exactly
    as attack.py:51 does, so the gate compares like with like.

    GATE: the scored-bar count must equal `bonde.MEASURED["panel_bars"]` and the
    explosive-tier median lift vs ALL SCORED at h=21 must equal
    `bonde.MEASURED["tier_explosive_med"]` to 2 dp. Fail = STOP; nothing new is
    quoted, and the finding is about the container caches, not about attack.py.
    """
    core = load_core()
    rows = build_panel(px, recs, dates,
                       windows=(REBALANCE,),
                       state_fn=lambda rec, dt: core.state_asof(rec, dt))
    scored = [r for r in rows if r["st"]]
    sym_ids, nsym = _ids(rows, "sym")
    k = REBALANCE
    expl = [r for r in scored if (r["st"] or {}).get("tier") == "explosive" and r["r"][k] is not None]
    base = [r for r in scored if r["r"][k] is not None]
    cell = core.Cell([sym_ids[r["sym"]] for r in expl], [r["r"][k] for r in expl])
    bcell = core.Cell([sym_ids[r["sym"]] for r in base], [r["r"][k] for r in base])
    med_expl, med_base = core.med(cell.v), core.med(bcell.v)
    bs = core.boot([cell, bcell], [core.med], nsym, B=B, seed=seed)
    lo, hi = core.ci(bs[:, 0, 0] - bs[:, 1, 0])
    gate = repro_ok(len(scored), med_expl, med_base)
    return sanitize({
        "header": HEADER,
        "convention": ("attack.py convention — same-day filings INCLUDED "
                       "(strict=False); reproduction only, never quoted as a cell"),
        "panel_rows": len(rows),
        "scored_bars": len(scored),
        "n_symbols": nsym,
        "n_dates": len(dates),
        "h": k,
        "explosive_n": len(cell.v),
        "explosive_median": med_expl,
        "all_scored_median": med_base,
        "median_lift_pp": round(med_expl - med_base, 2),
        "median_lift_ci_symbol": [lo, hi],
        "target_panel_bars": BONDE_MEASURED["panel_bars"],
        "target_tier_explosive_med": BONDE_MEASURED["tier_explosive_med"],
        "target_ci": list(BONDE_MEASURED["tier_explosive_ci"]),
        "gate_passed": bool(gate),
    })


CELL_DEFS = (
    ("G100", "passes_100_100", None),
    ("G100_epsbase", "passes_100_100_epsbase", None),
    ("B_EXPL", "bonde_tier", "explosive"),
    ("B_STRONG", "bonde_tier", "strong"),
    ("B_STEADY", "bonde_tier", "steady"),
    ("ALL_SCORED", "scored", None),
)


def _in_cell(row, kind: str, arg) -> bool:
    st = row.get("st")
    if not st:
        return False
    if kind == "scored":
        return True
    if kind == "bonde_tier":
        return bool(st.get("bonde_pass")) and st.get("tier") == arg
    return bool(st.get(kind))


def run_replay(px, recs, dates, bench=None, sectors=None, windows=H_WINDOWS,
               derived: str = "plus90", B_sym: int = 1000, B_date: int = 1000,
               seed_sym: int = 7, seed_date: int = 11) -> dict:
    """The quoted measurement: `strict=True` everywhere.

    Cells: the 100/100 screen (shipped rule and the EPS-base sensitivity), the
    three Bonde tiers, ARRIVE vs INCUMBENT for both boards, ALL_SCORED, and the
    6-month momentum-quintile splits of G100 / B_EXPL / ALL_SCORED — the split
    is what answers "do the members that already ran revert": Q5 of the screen
    against Q5 of the universe, not against the universe's average member.

    Every cell reports raw, stratum-excess and RSP-relative medians with the
    symbol-clustered CI and the DATE-clustered CI (`core.boot_dates` at h=21,
    `boot_blocks(block=h//21)` beyond it), plus the non-overlapping sub-panel
    medians as the cross-check.

    Every cell also carries `momentum_control` — lane2's WITHIN-quintile
    residual (`lane2.py:157-165`): the bar's forward return minus the MEAN
    forward return of ALL_SCORED bars in the SAME 6-month-momentum quintile,
    with a symbol-clustered CI. It is a SECOND VIEW beside the Q1..Q5 splits,
    not a replacement: the splits show where the cell sits, the residual prices
    the cell against its own momentum bucket.
    """
    core = load_core()
    rows = build_panel(px, recs, dates, windows=windows,
                       state_fn=lambda rec, dt: screen_asof(rec, dt, strict=True),
                       sectors=sectors)
    date_idx = {d: i for i, d in enumerate(dates)}
    rows.sort(key=lambda r: (r["sym"], date_idx.get(r["date"], -1)))

    # ARRIVE / INCUMBENT against the PREVIOUS cross-section of the same symbol.
    prev_by_sym: dict = {}
    for r in rows:
        prev = prev_by_sym.get(r["sym"])
        r["g100_flag"] = arrival_flag(prev, r["st"], "passes_100_100")
        r["bexpl_flag"] = arrival_flag(
            {"pass": bool(prev and prev.get("bonde_pass") and prev.get("tier") == "explosive")} if prev else None,
            {"pass": _in_cell(r, "bonde_tier", "explosive")} if r["st"] else None,
            "pass")
        prev_by_sym[r["sym"]] = r["st"]

    # dollar-volume and momentum quintiles are taken PER DATE (lane2.py:154,175)
    for d in dates:
        same = [r for r in rows if r["date"] == d]
        dv_edges = quintile_edges([r["dv"] for r in same])
        for r in same:
            r["dvq"] = stratum_key(r["sector"], r["dv"], dv_edges)[1]
    scored = [r for r in rows if r["st"]]
    mom_edges = quintile_edges([r["mom"] for r in scored])
    for r in rows:
        r["momq"] = mom_quintile(r["mom"], mom_edges)

    sym_ids, nsym = _ids(rows, "sym")
    ndate = len(dates)

    def selector(name):
        if name.endswith("_ARRIVE") or name.endswith("_INCUMBENT"):
            want = "arrive" if name.endswith("_ARRIVE") else "incumbent"
            field = "g100_flag" if name.startswith("G100") else "bexpl_flag"
            return lambda r: r.get(field) == want
        if "_Q" in name:
            base, q = name.rsplit("_Q", 1)
            sel = selector(base)
            return lambda r, sel=sel, q=int(q): sel(r) and r.get("momq") == q
        for nm, kind, arg in CELL_DEFS:
            if nm == name:
                return lambda r, kind=kind, arg=arg: _in_cell(r, kind, arg)
        raise KeyError(name)

    names = [nm for nm, _k, _a in CELL_DEFS]
    names += ["G100_ARRIVE", "G100_INCUMBENT", "B_EXPL_ARRIVE", "B_EXPL_INCUMBENT"]
    names += ["%s_Q%d" % (base, q) for base in ("G100", "B_EXPL", "ALL_SCORED")
              for q in (1, 2, 3, 4, 5)]

    out_cells: dict = {}
    mom_mu_by_window: dict = {}
    base_sel = selector("ALL_SCORED")
    for k in windows:
        block = max(1, k // REBALANCE)
        mom_mu = momentum_bucket_means(scored, k)
        mom_mu_by_window["h%d" % k] = {"Q%d" % q: mu for q, mu in sorted(mom_mu.items())}
        base_rows = [r for r in scored if base_sel(r) and r["r"][k] is not None]
        base_cell = core.Cell([sym_ids[r["sym"]] for r in base_rows], [r["r"][k] for r in base_rows])
        base_dcell = core.Cell([date_idx[r["date"]] for r in base_rows], [r["r"][k] for r in base_rows])
        for name in names:
            sel = selector(name)
            for r in scored:
                r["cell"] = bool(sel(r))
            cell_rows = [r for r in scored if r["cell"] and r["r"][k] is not None]
            if not cell_rows:
                out_cells.setdefault(name, {})["h%d" % k] = {"n": 0, "note": "empty cell"}
                continue
            raw = [r["r"][k] for r in cell_rows]
            ex = excess_vs_stratum(scored, k)
            ex_vals = [e["excess"] for e in ex if e["excess"] is not None]
            ex_levels: dict = {}
            for e in ex:
                ex_levels[e["level"]] = ex_levels.get(e["level"], 0) + 1
            rel = []
            for r in cell_rows:
                b = bench_by_date(bench[0], bench[1], r["date"], r["exit_date"][k]) if bench else None
                rel.append(r["r"][k] - b if b is not None else None)
            cell = core.Cell([sym_ids[r["sym"]] for r in cell_rows], raw)
            dcell = core.Cell([date_idx[r["date"]] for r in cell_rows], raw)
            bs = core.boot([cell, base_cell], [core.med, core.mean, core.win], nsym,
                           B=B_sym, seed=seed_sym)
            slo, shi = core.ci(bs[:, 0, 0] - bs[:, 1, 0])
            if block == 1:
                bd = core.boot_dates([dcell, base_dcell], [core.med], ndate,
                                     B=B_date, seed=seed_date)
            else:
                bd = boot_blocks([dcell, base_dcell], [core.med], ndate, block,
                                 B=B_date, seed=seed_date)
            dlo, dhi = core.ci(bd[:, 0, 0] - bd[:, 1, 0])
            # lane2's within-quintile momentum CONTROL, as a SECOND view: the
            # cell against the same 6m-momentum bucket of ALL_SCORED, with the
            # symbol-clustered CI (lane2.py:161-165 `boot([c],[mean],NS,...)`).
            res_rows = momentum_residuals(cell_rows, k, mom_mu)
            if res_rows:
                rcell = core.Cell([sym_ids[e["sym"]] for e in res_rows],
                                  [e["resid"] for e in res_rows])
                rb = core.boot([rcell], [core.mean], nsym, B=B_sym, seed=seed_sym)
                rlo, rhi = core.ci(rb[:, 0, 0])
                mom_ctrl = {
                    "n": len(res_rows),
                    "n_symbols": len({e["sym"] for e in res_rows}),
                    "n_dropped_no_quintile": len(cell_rows) - len(res_rows),
                    "mean_excess_pp": core.mean(np.asarray(
                        [e["resid"] for e in res_rows], dtype=float)),
                    "median_excess_pp": core.med(np.asarray(
                        [e["resid"] for e in res_rows], dtype=float)),
                    "ci_symbol": [rlo, rhi],
                    "by_quintile_n": {"Q%d" % q: sum(1 for e in res_rows if e["momq"] == q)
                                      for q in sorted({e["momq"] for e in res_rows})},
                }
            else:
                mom_ctrl = {"n": 0, "n_dropped_no_quintile": len(cell_rows),
                            "note": "no cell bar carries a 6m-momentum quintile"}
            sub = []
            for panel in subpanel_offsets(sorted({date_idx[r["date"]] for r in cell_rows}), block):
                vals = [r["r"][k] for r in cell_rows if date_idx[r["date"]] in set(panel)]
                sub.append(core.med(np.asarray(vals, dtype=float)) if vals else None)
            out_cells.setdefault(name, {})["h%d" % k] = {
                "n": len(cell_rows),
                "n_symbols": len({r["sym"] for r in cell_rows}),
                "n_dates": len({r["date"] for r in cell_rows}),
                "block": block,
                "n_blocks": int(math.ceil(ndate / block)),
                "raw": _cell_stats(core, raw),
                "excess_vs_stratum": _cell_stats(core, ex_vals),
                "stratum_levels": ex_levels,
                "rel_%s" % BENCHMARK.lower(): _cell_stats(core, rel),
                "median_lift_vs_all_scored_pp": round(core.med(cell.v) - core.med(base_cell.v), 2),
                "lift_ci_symbol": [slo, shi],
                "lift_ci_date": [dlo, dhi],
                "momentum_control": mom_ctrl,
                "subpanel_medians": sub,
            }
    for r in scored:
        r.pop("cell", None)
    return dict(sanitize({
        "header": HEADER,
        "strict": True,
        "derived": derived,
        "windows": list(windows),
        "panel_rows": len(rows),
        "scored_bars": len(scored),
        "n_symbols": nsym,
        "n_dates_panel": ndate,
        "n_dates_effective": len({r["date"] for r in rows}),
        "momentum_edges": (list(map(float, mom_edges)) if mom_edges is not None else None),
        "momentum_bucket_means_all_scored": mom_mu_by_window,
        "benchmark": BENCHMARK,
        "cells": out_cells,
        "biases": BIASES,
    }), panel_rows_detail=rows)


BIASES = {
    "look_ahead": ("strict=True on every quoted cell: a filing available ON the "
                   "cross-section is excluded; refuse_lookahead asserts the '>' case"),
    "survivorship": ("the universe is the audit price pickle's membership = today's; "
                     "DELISTED names are absent by construction"),
    "print_anchoring": ("an ARRIVE event is measured from the first cross-section AFTER "
                        "the filing became available, never on it"),
    "derived_q4": ("unfiled quarters are assumed available at end+90d (core.prep_fin "
                   "'plus90'); derived='drop' is the sensitivity"),
    "overlapping_windows": ("cross-sections are 21 sessions apart, so h=63/126 forwards "
                            "overlap 3x/6x — date CIs use boot_blocks(block=h//21) and "
                            "n_dates is printed per cell"),
    "static_sectors": "the sector axis is today's GICS from `companies`, applied to past bars",
}


def run_live_forward(recs, cohorts, closes, bench=None, asof: str = LIVE_ASOF,
                     entry_date: str = LIVE_ENTRY_DATE, exit_date: str = LIVE_EXIT_DATE,
                     arrivals=None) -> dict:
    """The live ledgers, 5 sessions — a DESCRIPTION, not a measurement.

    Entry = the 09-14 close: the first close after the `growth_seen` stamp
    (Saturday 2026-09-12 15:51 ET) and after the `bonde_seen` stamp
    (2026-09-14 03:46Z). The audit financials were fetched 09-14 04:02Z and
    carry filings through 09-13 only, so the as-of state is look-ahead free by
    construction — `refuse_lookahead` asserts it anyway.

    n is tiny (29 growth names, 27 genuine Bonde arrivals with 0-1 sessions of
    life). No significance is claimed and the arrivals carry no return column.
    """
    out = {
        "header": HEADER,
        "block_header": ("5 sessions, n as stated — a description, not a measurement. "
                         "Entry = the %s close: the first close after the growth_seen "
                         "stamp (Saturday 2026-09-12 15:51 ET) and after the bonde_seen "
                         "stamp (2026-09-14 03:46Z)." % entry_date),
        "asof": asof, "entry_date": entry_date, "exit_date": exit_date,
        "cohorts": {},
    }
    bench_pct = bench_by_date(bench[0], bench[1], entry_date, exit_date) if bench else None
    out["benchmark"] = {"symbol": BENCHMARK, "pct": bench_pct}
    for name, syms in (cohorts or {}).items():
        members = []
        for sym in syms:
            frame = (closes or {}).get(sym)
            st = screen_asof(recs.get(sym), asof, strict=True) if recs.get(sym) else None
            fwd = bench_by_date(frame[0], frame[1], entry_date, exit_date) if frame else None
            members.append({
                "symbol": sym,
                "sales_yoy": (st or {}).get("sales_yoy"),
                "eps_yoy": (st or {}).get("eps_yoy"),
                "tier": (st or {}).get("tier"),
                "passes_100_100": (st or {}).get("passes_100_100"),
                "fwd_5d_pct": fwd,
                "rel_%s_pp" % BENCHMARK.lower(): (round(fwd - bench_pct, 2)
                                                  if fwd is not None and bench_pct is not None
                                                  else None),
            })
        xs = [m["sales_yoy"] for m in members if m["sales_yoy"] is not None and m["fwd_5d_pct"] is not None]
        ys = [m["fwd_5d_pct"] for m in members if m["sales_yoy"] is not None and m["fwd_5d_pct"] is not None]
        rho = ci_rho = p_rho = None
        if len(xs) >= 3:
            spearman_rho, spearman_ci, perm_p = _study_stats()
            rho = spearman_rho(xs, ys)
            if rho is not None:
                ci_rho = list(spearman_ci(xs, ys))
                p_rho = perm_p(xs, ys)
        out["cohorts"][name] = {
            "n": len(members),
            "n_with_return": sum(1 for m in members if m["fwd_5d_pct"] is not None),
            "median_fwd_5d_pct": (float(np.median([m["fwd_5d_pct"] for m in members
                                                   if m["fwd_5d_pct"] is not None]))
                                  if any(m["fwd_5d_pct"] is not None for m in members) else None),
            "spearman_growth_vs_fwd": rho,
            "spearman_ci": ci_rho,
            "perm_p": p_rho,
            "members": members,
        }
    out["bonde_arrivals"] = [
        {"symbol": a.get("symbol"), "first_seen": a.get("first_seen"),
         "sessions_available": a.get("sessions_available")}
        for a in (arrivals or [])
    ]
    out["arrivals_note"] = ("genuine arrivals only (first_seen after the day-one backfill); "
                            "no return column — 0-1 sessions of life is not a return")
    return sanitize(out)


def _study_stats():
    """Lazy import of the trailing study's rank statistics.

    Fails LOUD rather than silently computing something different: the
    live-forward block quotes a Spearman with a CI and a permutation p, and
    there is exactly one implementation of those in this task.
    """
    try:
        from scripts.board_growth_study import perm_p, spearman_ci, spearman_rho
    except ImportError as exc:                                  # pragma: no cover
        raise RuntimeError(
            "board_growth_study not importable — run from /tmp/scripts with "
            "PYTHONPATH=/tmp:/app (see this module's docstring)") from exc
    return spearman_rho, spearman_ci, perm_p


# ── container I/O (never touched by the unit tests) ──────────────────────────
def load_inputs(derived: str = "plus90"):            # pragma: no cover - container
    core = load_core()
    px, fin = core.load()
    recs = core.prep_fin(fin, derived)
    cal = list(px["SPY"]["d"])
    dates = cal[::PANEL_STEP]
    return px, recs, dates


def load_bench():                                    # pragma: no cover - container
    from sepa import prices
    df = prices.load_prices(BENCHMARK)
    if df is None or getattr(df, "empty", True):
        return None
    dates = [str(d)[:10] for d in df.index]
    return dates, np.asarray(df["close"], dtype=float)


def load_sectors(symbols):                           # pragma: no cover - container
    try:
        from growth.tracker import _sectors
        return {s: (v[0] if isinstance(v, (list, tuple)) else v)
                for s, v in (_sectors(list(symbols)) or {}).items()}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("sectors unavailable (%s) — the stratum falls back to dv-quintile", exc)
        return {}


def load_cohorts():                                  # pragma: no cover - container
    """The two arrival ledgers, READ-ONLY (projected finds, never a write).

    `growth_seen` is 29 symbols all stamped at one backfill instant with zero
    arrivals since; `bonde_seen` is a 1,054-name day-one backfill plus the
    genuine arrivals after its `__meta__.tracking_since`. Both are ISO STRINGS.
    """
    from sepa import first_seen
    db = first_seen._db()
    if db is None:
        raise RuntimeError("mongo unavailable — the ledgers cannot be read")
    growth = sorted(str(d["_id"]) for d
                    in db["growth_seen"].find({"_id": {"$ne": first_seen.META_ID}}, {"_id": 1}))
    docs = list(db["bonde_seen"].find({"_id": {"$ne": first_seen.META_ID}},
                                      {"_id": 1, "first_seen": 1}))
    meta = db["bonde_seen"].find_one({"_id": first_seen.META_ID}, {"tracking_since": 1}) or {}
    since = str(meta.get("tracking_since") or "")
    day_one, arrivals = [], []
    for d in docs:
        fs = str(d.get("first_seen") or "")
        if since and fs > since:
            arrivals.append({"symbol": str(d["_id"]), "first_seen": fs})
        else:
            day_one.append(str(d["_id"]))
    return ({"growth_seen_29": growth, "bonde_seen_day_one": sorted(day_one)},
            sorted(arrivals, key=lambda a: a["symbol"]), since)


def load_closes(symbols):                            # pragma: no cover - container
    """`prices.load_prices` per symbol, healed through `symbols.resolve`.

    NOTE: on a cold symbol this FETCHES and writes the parquet price cache —
    that is the one write this study makes, and it is the price cache, never a
    ledger.
    """
    from sepa import prices, symbols as sym_mod
    out = {}
    for sym in symbols:
        try:
            if sym_mod.is_delisted(sym):
                continue
            df = prices.load_prices(sym_mod.resolve(sym))
            if df is None or getattr(df, "empty", True):
                continue
            out[sym] = ([str(d)[:10] for d in df.index], np.asarray(df["close"], dtype=float))
        except Exception as exc:                                # noqa: BLE001
            log.warning("prices unavailable for %s: %s", sym, exc)
    return out


def write_panel_csv(path, rows):                     # pragma: no cover - container
    cols = ["sym", "date", "i", "price", "sector", "dv", "mom", "momq", "dvq"]
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols + ["passes_100_100", "tier", "bonde_pass", "stale_days",
                           "g100_flag", "bexpl_flag", "r21", "r63", "r126"])
        for r in rows:
            st = r.get("st") or {}
            w.writerow([r.get(c) for c in cols]
                       + [st.get("passes_100_100"), st.get("tier"), st.get("bonde_pass"),
                          st.get("stale_days"), r.get("g100_flag"), r.get("bexpl_flag")]
                       + [(r.get("r") or {}).get(k) for k in H_WINDOWS])


def main(argv=None):                                 # pragma: no cover - container
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--stage", choices=("repro", "replay", "live-forward"), required=True)
    p.add_argument("--derived", default="plus90", choices=("plus90", "drop"))
    p.add_argument("--json", default="")
    p.add_argument("--panel", default="")
    p.add_argument("--B", type=int, default=1000)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(HEADER, flush=True)

    if a.stage == "repro":
        px, recs, dates = load_inputs("plus90")
        res = run_repro(px, recs, dates)
        print(json.dumps({k: v for k, v in res.items()}, indent=2, default=str))
        if not res["gate_passed"]:
            print("GATE FAILED — the panel no longer reproduces bonde.MEASURED. "
                  "STOP: quote nothing new; this is a finding about the caches.",
                  flush=True)
            return 2
        return 0

    if a.stage == "replay":
        px, recs, dates = load_inputs(a.derived)
        bench = load_bench()
        sectors = load_sectors([s for s in px if s not in ANCH])
        res = run_replay(px, recs, dates, bench=bench, sectors=sectors,
                         derived=a.derived, B_sym=a.B, B_date=a.B)
        rows = res.pop("panel_rows_detail")
        if a.panel:
            write_panel_csv(a.panel, rows)
            print("wrote %s (%d rows)" % (a.panel, len(rows)), flush=True)
        blob = json.dumps(res, indent=2, default=str)
        if a.json:
            with open(a.json, "w") as fh:
                fh.write(blob + "\n")
            print("wrote %s" % a.json, flush=True)
        else:
            print(blob)
        return 0

    px, recs, _dates = load_inputs(a.derived)
    del px
    bench = load_bench()
    cohorts, arrivals, since = load_cohorts()
    closes = load_closes(sorted({s for syms in cohorts.values() for s in syms}))
    cal = bench[0] if bench else []
    for arr in arrivals:
        day = str(arr.get("first_seen") or "")[:10]
        arr["sessions_available"] = (sum(1 for d in cal if day < d <= LIVE_EXIT_DATE)
                                     if day and cal else None)
    res = run_live_forward(recs, cohorts, closes, bench=bench, arrivals=arrivals)
    res["bonde_tracking_since"] = since
    blob = json.dumps(res, indent=2, default=str)
    if a.json:
        with open(a.json, "w") as fh:
            fh.write(blob + "\n")
        print("wrote %s" % a.json, flush=True)
    else:
        print(blob)
    return 0


if __name__ == "__main__":                           # pragma: no cover
    raise SystemExit(main())
