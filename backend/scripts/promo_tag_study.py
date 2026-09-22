"""🎪 Promo-circuit first-tag forward study — "can we use them?" (2026-09-21).

THE ASK (Ajay 2026-09-21, verbatim): "We have this page that pull data from
social media and chatter the keeps pulling new stocks... Can you please check if
we can use them and make sure to do some research and add them to our list as
they come through please?"

This file answers the FIRST half — *can we use them* — as a measurement. It
wires nothing, pushes nothing, gates nothing and writes nothing to Mongo.

WHAT IT MEASURES. Every first-ever promo tag (`promo_circuit_tags`), a
follower-realistic entry at the first session OPEN strictly after the tag, and
the forward return at 1 / 5 / 21 sessions against a MATCHED placebo: never-tagged
names in the same cap-at-tag decile x pre-tag liquidity tercile, entered and
exited on the SAME dates. The number that counts is the Δ of the medians with a
cluster bootstrap CI - date-clustered AND symbol-clustered - and the cluster
count printed on every line.

HOUSE RULES this file is written under:
  * every threshold is an EXISTING constant, imported by name, never retyped:
    `promo_circuit.RAN_MIN_GAIN_PCT` / `.DUMPED_DROP_PCT`, `promo_live.PROMO_MOVE_PCT`,
    `traders.curate.MAX_STALE_DAYS`, `trading.safety_floor.MIN_SHARE_PRICE`,
    `supply_demand.hot_pullback.MIN_DOLLAR_VOL_USD`, `supply_demand.zone_store.MIN_CAP_USD`,
    `sepa.adr.liquidity_check`'s own `min_dollar_vol` default (read off the signature);
  * the backtest ships with the claim - this script IS the claim's provenance;
  * NEVER `sepa.prices.load_prices` (it WRITES `price_cache` on a miss,
    prices.py:502-504). The only reads are `price_cache.find_one` and the only
    fetch is `promo_circuit._bars_since` (HTTP GET, no Mongo write);
  * importable with NO database: every Mongo read sits behind a function.

THE PRIMARY VERDICT IS THE POOLED SAMPLE (IS + OOS), 5 sessions, open entry,
shotgun-pruned cohort, all tiers. The out-of-sample cohort alone has EIGHT entry
dates today (one carrying 40% of the events) - a percentile bootstrap on eight
clusters is not a confidence interval, so OOS-5 is used as a SIGN CHECK only and
prints `ci=n/a`. In-sample is the window the promo roster was itself selected in
and is biased positive by construction; that is why the positive branch of the
verdict needs the OOS sign to agree AND a tier to carry it. A date-clean OOS
verdict needs ~3 more weeks of tags: `RERUN_AFTER`.

ONE BAR SERIES PER NAME, NEVER MERGED. `price_cache` bars and
`promo_circuit._bars_since` bars are both `adjusted=true` but adjusted as of
THEIR OWN fetch date. A reverse split after the cache date - endemic in this
cohort - makes an in-memory concat print a +-10x bar at the seam, straight into
`ret_k` / `dd_k` / `dumped_21`. A name is therefore served ENTIRELY from the
cache row or ENTIRELY from a fresh fetch; when the fresh series is used the
cache row is discarded. `tests/test_promo_tag_study.py` pins the seam.

RUN (read-only; the script is piped to /tmp, never written into /app):
  docker exec -i cheetah-market-app-api-1 sh -c 'cat > /tmp/promo_tag_study.py' \
      < backend/scripts/promo_tag_study.py
  # smoke - cache only, no HTTP, NOT QUOTABLE
  docker exec -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u \
      /tmp/promo_tag_study.py --stage both --no-refresh --draws 200 \
      --out /tmp/promo_smoke.csv --json /tmp/promo_smoke.json'
  # full - detached, outside RTH (per-ticker HTTP for every stale/missing name)
  docker exec -d -w /app cheetah-market-app-api-1 sh -c 'PYTHONPATH=/app python -u \
      /tmp/promo_tag_study.py --stage both --out /tmp/promo_tag_events.csv \
      --json /tmp/promo_tag_report.json --emit-measured /tmp/promo_measured.json \
      > /tmp/promo_tag_study.log 2>&1'
"""
from __future__ import annotations

import argparse
import inspect
import json
import math
import os
import pprint
import time
from datetime import date as _date
from datetime import datetime, time as _time, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from catalysts import promo_circuit as pc
from catalysts import promo_live
from sepa import adr as adr_mod
from sepa import cap_warm
from sepa import symbols as symbols_mod
from supply_demand import hot_pullback
from supply_demand import zone_store
from traders import curate
from trading import safety_floor

SCRIPT = "backend/scripts/promo_tag_study.py"
ET = ZoneInfo("America/New_York")

# ── study conventions (NOT trading thresholds) ───────────────────────────────
# The house convention is already "fewer than 100 usable bootstrap draws -> NaN"
# (scripts/explosive_study.boot_delta_col). MIN_CLUSTERS is the second half of
# the same idea and is the critic's addition: a percentile CI over fewer than
# this many independent clusters is not a CI, it is the clusters. It is a STUDY
# convention and it is his to move (spec §7-10); move it and every line
# re-prints with the new floor.
MIN_CLUSTERS = 20
# The first date the OOS cohort has >= MIN_CLUSTERS distinct entry dates at the
# 5-session clock. Until then `oos_clean` is false everywhere it is served.
RERUN_AFTER = "2026-10-12"
# The 50-day window every liquidity floor in the app uses (sepa.adr.liquidity_check
# period=50, hot_pullback median-50d, demand_reentry's 50-day mean).
PRE_LIQ_BARS = 50
# An account cut is only printed when it carries at least this many events.
MIN_ACCOUNT_N = 20
# Forward clocks, in sessions.
CLOCKS = (1, 5, 21)
# The line the verdict is read off.
PRIMARY = ("pooled", 5, "open", "shotgun_kept", "all")

# ── imported thresholds (identity-pinned by the tests; never retyped) ────────
RAN_MIN_GAIN_PCT = pc.RAN_MIN_GAIN_PCT                      # 30.0
DUMPED_DROP_PCT = pc.DUMPED_DROP_PCT                        # -40.0
PROMO_MOVE_PCT = promo_live.PROMO_MOVE_PCT                  # 8.0
MAX_STALE_DAYS = curate.MAX_STALE_DAYS                      # 10
MIN_SHARE_PRICE = safety_floor.MIN_SHARE_PRICE              # 2.00
MIN_DOLLAR_VOL_5M = hot_pullback.MIN_DOLLAR_VOL_USD         # 5e6
MIN_CAP_USD = zone_store.MIN_CAP_USD                        # 700_000_000
# sepa.adr's own hard floor, read off the signature so it cannot drift from it.
MIN_DOLLAR_VOL_20M = float(
    inspect.signature(adr_mod.liquidity_check).parameters["min_dollar_vol"].default)

_P_BUF: list = []


def P(*a) -> None:
    line = " ".join(str(x) for x in a)
    _P_BUF.append(line)
    print(line, flush=True)


# ═════════════════════════════════════════════════════════════════════════════
# BARS — one series per name, never merged
# ═════════════════════════════════════════════════════════════════════════════
def _as_date(v) -> Optional[_date]:
    """Whatever a bar carries as its date -> datetime.date. PURE."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, _date):
        return v
    if isinstance(v, str):
        try:
            return datetime.strptime(v[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def open_ts(d: _date) -> datetime:
    """The 09:30 America/New_York open of a session, UTC-aware. PURE."""
    return datetime.combine(d, _time(9, 30), tzinfo=ET)


def _f(v) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def norm_cache_bars(row: Optional[dict]) -> list:
    """A `price_cache` doc -> the study's bar shape, ascending, PURE."""
    out = []
    for b in (row or {}).get("bars") or []:
        d = _as_date(b.get("date"))
        c = _f(b.get("close"))
        if d is None or c is None:
            continue
        out.append({"date": d, "open": _f(b.get("open")) or c, "high": _f(b.get("high")) or c,
                    "low": _f(b.get("low")) or c, "close": c, "volume": _f(b.get("volume")) or 0.0})
    out.sort(key=lambda b: b["date"])
    return out


def norm_agg_bars(results: Optional[list]) -> list:
    """`promo_circuit._bars_since` raw aggs -> the study's bar shape. PURE."""
    out = []
    for b in results or []:
        d = pc._bar_date(b)
        c = _f(b.get("c"))
        if d is None or c is None:
            continue
        out.append({"date": d, "open": _f(b.get("o")) or c, "high": _f(b.get("h")) or c,
                    "low": _f(b.get("l")) or c, "close": c, "volume": _f(b.get("v")) or 0.0})
    out.sort(key=lambda b: b["date"])
    return out


def cache_covers(bars: list, event_ts: datetime, exit_needed: _date) -> bool:
    """True when a cache series may be used WHOLE for this event. PURE.

    Two halves: it must reach the exit (last bar at/after `exit_needed`) and it
    must carry the pre-tag liquidity window (at least `PRE_LIQ_BARS` bars
    strictly before the tag's session). The second is the spec's "first bar
    <= event - 50 sessions" counted in the data we actually hold, which is
    exact rather than a calendar approximation of 50 trading days.
    """
    if not bars:
        return False
    tag_d = event_ts.astimezone(ET).date()
    if bars[-1]["date"] < exit_needed:
        return False
    return sum(1 for b in bars if b["date"] < tag_d) >= PRE_LIQ_BARS


def bars_for(sym: str, event_ts: datetime, exit_needed: _date,
             cache_reader: Callable, refresh: Optional[Callable] = None) -> tuple:
    """(bars, source) for one name. source in {"cache", "refresh", "none"}.

    NEVER a merge of the two. `price_cache` and `_bars_since` are each adjusted
    as of their own fetch date; a reverse split between them puts a +-10x bar at
    the seam. A refreshed name uses the fresh series for the WHOLE window and
    the cache row is discarded.
    """
    try:
        row = cache_reader(sym)
    except Exception:                                          # noqa: BLE001
        row = None
    bars = norm_cache_bars(row)
    if cache_covers(bars, event_ts, exit_needed):
        return bars, "cache"
    if refresh is None:
        return (bars, "cache") if bars else ([], "none")
    try:
        fresh = norm_agg_bars(refresh(sym, event_ts - timedelta(days=90)))
    except Exception:                                          # noqa: BLE001
        fresh = []
    if fresh:
        return fresh, "refresh"
    return (bars, "cache") if bars else ([], "none")


# ═════════════════════════════════════════════════════════════════════════════
# EVENTS
# ═════════════════════════════════════════════════════════════════════════════
def event_time(doc: dict) -> Optional[datetime]:
    """The campaign's earliest tag: min(first_tagged_at, min(posts[].at)). PURE.

    The sweep RESETS `first_tagged_at` after `RETAG_RESET_DAYS` of dormancy
    (promo_circuit.py:397-405), and 127 docs carry a post older than it. The
    event is the earliest thing the account actually posted.
    """
    cands = []
    ts = pc._as_utc(doc.get("first_tagged_at"))
    if ts:
        cands.append(ts)
    for p in doc.get("posts") or []:
        at = pc._as_utc(p.get("at"))
        if at:
            cands.append(at)
    return min(cands) if cands else None


def events(docs: list, roster: Optional[dict] = None) -> pd.DataFrame:
    """One row per (account, ticker). PURE.

    Symbols go through `symbols.resolve` (DOOO -> DOO) BEFORE grouping, so the
    renamed series and the live one are one ticker. `is_delisted` is checked on
    the symbol AS GIVEN, which is what `symbols.is_delisted` documents.
    """
    roster = pc.PROMO_ACCOUNTS if roster is None else roster
    kept = {(t.get("account"), t.get("ticker")) for t in pc.prune_shotgun_tags(list(docs))}
    rows = []
    for d in docs:
        ts = event_time(d)
        raw = (d.get("ticker") or "").strip().upper()
        if not ts or not raw:
            continue
        sym = symbols_mod.resolve(raw)
        acct = d.get("account")
        tier = (roster.get(acct) or {}).get("tier") or d.get("tier") or "B"
        rows.append({"account": acct, "ticker": sym, "raw_ticker": raw, "tier": tier,
                     "event_ts": ts, "n_messages": int(d.get("n_messages") or 0),
                     "shotgun_kept": (acct, raw) in kept,
                     "delisted": symbols_mod.is_delisted(raw)})
    E = pd.DataFrame(rows)
    if E.empty:
        return E
    E["first_ever_ts"] = E.groupby("ticker")["event_ts"].transform("min")
    return E.sort_values(["ticker", "event_ts"]).reset_index(drop=True)


def entry_index(bars: list, event_ts: datetime) -> Optional[int]:
    """Index of the first bar whose session OPEN is STRICTLY AFTER the tag. PURE.

    A follower cannot fill at a price that already printed. Monday 10:00 RTH ->
    Tuesday's open; Monday 08:00 pre-open -> Monday's open; Friday 17:00 or a
    weekend tag -> Monday's open. None when no bar qualifies (unclosable) or
    when the series itself begins after the tag (no_history).
    """
    if not bars:
        return None
    if bars[0]["date"] > event_ts.astimezone(ET).date():
        return None                          # the series itself begins after the tag
    for i, b in enumerate(bars):
        if open_ts(b["date"]) > event_ts:
            return i
    return None


def tagday_index(bars: list, event_ts: datetime) -> Optional[int]:
    """First bar on/after the tag's ET session date. PURE."""
    d = event_ts.astimezone(ET).date()
    for i, b in enumerate(bars):
        if b["date"] >= d:
            return i
    return None


def base_close(bars: list, i_tag: Optional[int]) -> Optional[float]:
    """Close of the last bar STRICTLY BEFORE the tag's session - the board's own
    `price_action_since` base (promo_circuit.py:480). PURE."""
    if i_tag is None or i_tag <= 0:
        return None
    return bars[i_tag - 1]["close"]


def tagday_move(bars: list, i_tag: Optional[int], base: Optional[float]) -> Optional[float]:
    """close[i_tag]/base - 1: how far the name moved on the tag's own session.

    NOT "late tag". Daily bars cannot separate "was already up when the account
    posted" from "moved after the post, intraday" - the flag reads exactly what
    it is, a tag-day move. PURE."""
    if i_tag is None or base is None or i_tag >= len(bars) or not base:
        return None
    return bars[i_tag]["close"] / base - 1.0


def forward(bars: list, i: Optional[int], k: int, event_ts: Optional[datetime] = None,
            entry_px: Optional[float] = None) -> Optional[dict]:
    """The k-session forward window opened at bar `i`. None when it does not
    close - NEVER 0.0, which would read as a flat trade the follower never had.

    `assert` is the look-ahead guard: the entry bar must open strictly after the
    tag. PURE.
    """
    if i is None or not bars or i < 0 or i + k - 1 > len(bars) - 1:
        return None
    if event_ts is not None:
        assert open_ts(bars[i]["date"]) > event_ts, (
            "look-ahead: entry bar %s opens at or before the tag %s"
            % (bars[i]["date"], event_ts))
    px = bars[i]["open"] if entry_px is None else entry_px
    if not px:
        return None
    win = bars[i:i + k]
    return {"ret": win[-1]["close"] / px - 1.0,
            "peak": max(b["high"] for b in win) / px - 1.0,
            "dd": min(b["low"] for b in win) / px - 1.0}


def close_forward(bars: list, i_tag: Optional[int], k: int) -> Optional[dict]:
    """Sensitivity: entry at the TAG-DAY CLOSE, held k sessions. A follower
    cannot fill at a close that already printed, so this is never the primary.
    PURE."""
    if i_tag is None or not bars or i_tag + k > len(bars) - 1:
        return None
    px = bars[i_tag]["close"]
    if not px:
        return None
    win = bars[i_tag + 1:i_tag + 1 + k]
    if len(win) < k:
        return None
    return {"ret": win[-1]["close"] / px - 1.0,
            "dd": min(b["low"] for b in win) / px - 1.0}


def halted(bars: list, sym: str, today: _date) -> bool:
    """A name that stopped printing. `MAX_STALE_DAYS` is the trader lane's own
    liveness rule (the SDIG lesson), imported. PURE."""
    if symbols_mod.is_delisted(sym):
        return True
    if not bars:
        return False
    return (today - bars[-1]["date"]).days > MAX_STALE_DAYS


def ran_first(bars: list, i_tag: Optional[int], base: Optional[float], k: int = 5) -> Optional[bool]:
    """Did it print `RAN_MIN_GAIN_PCT` over the base inside k sessions of the tag?
    The board's own RAN rule, imported. PURE."""
    if i_tag is None or base is None or not base or i_tag >= len(bars):
        return None
    win = bars[i_tag:i_tag + k]
    if not win:
        return None
    return max(b["high"] for b in win) >= base * (1.0 + RAN_MIN_GAIN_PCT / 100.0)


def dumped(bars: list, i_tag: Optional[int], k: int = 21) -> Optional[bool]:
    """After the post-tag PEAK, did a low give back `DUMPED_DROP_PCT`? The
    board's own DUMPED rule, imported. PURE."""
    if i_tag is None or i_tag >= len(bars):
        return None
    win = bars[i_tag:i_tag + k]
    if len(win) < 2:
        return None
    highs = [b["high"] for b in win]
    j = int(np.argmax(highs))
    after = win[j:]
    if len(after) < 2:
        return False
    peak = highs[j]
    return min(b["low"] for b in after) <= peak * (1.0 + DUMPED_DROP_PCT / 100.0)


def pre_liquidity(bars: list, i_tag: Optional[int]) -> dict:
    """Mean and median close x volume over the `PRE_LIQ_BARS` bars STRICTLY
    before the tag's session, and the three floor flags. PURE."""
    out = {"liq50_mean": None, "liq50_median": None, "n_pre": 0}
    if i_tag is None or i_tag <= 0:
        return out
    win = bars[max(0, i_tag - PRE_LIQ_BARS):i_tag]
    if not win:
        return out
    dv = np.array([b["close"] * b["volume"] for b in win], dtype=float)
    out["liq50_mean"] = float(np.nanmean(dv))
    out["liq50_median"] = float(np.nanmedian(dv))
    out["n_pre"] = len(win)
    return out


def cap_at_tag(row: Optional[dict], base: Optional[float]) -> tuple:
    """(cap, cap_source, cap_posthoc) through `sepa.cap_warm.derive_cap`.

    The shares row is passed WITHOUT `market_cap` so the engine takes the shares
    path: shares x the PRE-TAG close is the cap the name carried WHEN it was
    tagged. Today's cap is post-hoc - a name that dumped 60% is smaller now than
    it was, and matching a placebo on it draws from a lower decile than the
    event actually sat in. Only when neither share count exists does today's cap
    stand in, flagged `cap_posthoc=True`. PURE.
    """
    row = row or {}
    cap, src = cap_warm.derive_cap(
        {k: row.get(k) for k in ("shares_outstanding", "float_shares")}, base)
    if cap is not None:
        return cap, src, False
    cap, src = cap_warm.derive_cap({"market_cap": row.get("market_cap")}, base)
    return cap, src, cap is not None


# ═════════════════════════════════════════════════════════════════════════════
# STATISTICS — the study's own constructions
# ═════════════════════════════════════════════════════════════════════════════
def wilson(k: int, n: int, z: float = 1.96) -> tuple:
    """Wilson score interval for a proportion. PURE."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def trimmed_mean(v: np.ndarray, frac: float = 0.05) -> float:
    """Symmetric `frac`-trimmed mean. PURE."""
    v = np.asarray([x for x in v if np.isfinite(x)], dtype=float)
    if v.size == 0:
        return float("nan")
    v = np.sort(v)
    cut = int(math.floor(v.size * frac))
    if cut > 0 and v.size - 2 * cut >= 1:
        v = v[cut:v.size - cut]
    return float(v.mean())


def _usable(D: pd.DataFrame, col: str, key: str) -> pd.DataFrame:
    """Rows with a finite `col` and a present cluster key. PURE."""
    if D is None or len(D) == 0 or col not in D.columns or key not in D.columns:
        return pd.DataFrame(columns=[col, key])
    v = pd.to_numeric(D[col], errors="coerce")
    return D[v.notna() & D[key].notna()]


def cluster_median_delta(kept: pd.DataFrame, base: pd.DataFrame, col: str, key: str,
                         draws: int = 2000, seed: int = 7) -> dict:
    """median(kept[col]) - median(base[col]) with a CLUSTER bootstrap CI.

    Its OWN construction, not a transcription of `explosive_study.cluster_boot`:
    that one is a ratio-of-sums MEAN over pre-aggregated per-cluster sums and
    cannot host a median. Here each draw resamples the CLUSTERS with replacement
    (`key` = "date" or "symbol"), MATERIALISES the resampled rows of both cohorts
    under the SAME cluster draw, and takes the difference of the two medians.
    The placebo rows carry the EVENT's symbol in `symbol`, so a symbol cluster
    holds an event and its own matched placebos.

    NaN for lo/hi/p_le0 when the cluster count is under `MIN_CLUSTERS` or fewer
    than 100 draws were usable (the house convention,
    explosive_study.boot_delta_col). `n_clusters` is always reported, NaN or not
    - it is the number the reader needs to judge the line. PURE.
    """
    nan = float("nan")
    # Only rows that actually carry a value for this column, and a cluster key,
    # take part: a NaN forward return is an unclosable window, not a cluster.
    kept = _usable(kept, col, key)
    base = _usable(base, col, key)
    kv_all = pd.to_numeric(kept[col], errors="coerce").to_numpy(dtype=float) if len(kept) else np.array([])
    bv_all = pd.to_numeric(base[col], errors="coerce").to_numpy(dtype=float) if len(base) else np.array([])
    kv_all = kv_all[np.isfinite(kv_all)]
    bv_all = bv_all[np.isfinite(bv_all)]
    # The clusters are the EVENT cohort's own: a placebo row exists only because
    # an event does, and a cluster with no closable event contributes nothing
    # that the reader would call an independent observation.
    keys = sorted(set(kept[key].tolist() if len(kept) else []))
    out = {"delta": nan, "lo": nan, "hi": nan, "p_le0": nan,
           "n_clusters": len(keys), "draws_used": 0,
           "n_kept": int(kv_all.size), "n_base": int(bv_all.size)}
    if kv_all.size == 0 or bv_all.size == 0:
        return out
    out["delta"] = float(np.median(kv_all) - np.median(bv_all))
    if len(keys) < 2:
        return out
    kg, bg = {}, {}
    for k, g in kept.groupby(key):
        v = pd.to_numeric(g[col], errors="coerce").to_numpy(dtype=float)
        kg[k] = v[np.isfinite(v)]
    for k, g in base.groupby(key):
        v = pd.to_numeric(g[col], errors="coerce").to_numpy(dtype=float)
        bg[k] = v[np.isfinite(v)]
    empty = np.array([], dtype=float)
    kl = [kg.get(k, empty) for k in keys]
    bl = [bg.get(k, empty) for k in keys]
    rng = np.random.default_rng(seed)
    n = len(keys)
    acc = []
    for _ in range(int(draws)):
        idx = rng.integers(0, n, size=n)
        kk = np.concatenate([kl[i] for i in idx])
        bb = np.concatenate([bl[i] for i in idx])
        if kk.size == 0 or bb.size == 0:
            continue
        acc.append(np.median(kk) - np.median(bb))
    out["draws_used"] = len(acc)
    if n < MIN_CLUSTERS or len(acc) < 100:
        return out
    d = np.asarray(acc, dtype=float)
    out["lo"] = float(np.percentile(d, 2.5))
    out["hi"] = float(np.percentile(d, 97.5))
    out["p_le0"] = float((d <= 0).mean())
    return out


def excludes_zero(ci: dict) -> bool:
    """True only when the interval exists AND sits wholly on one side of 0."""
    lo, hi = ci.get("lo"), ci.get("hi")
    if lo is None or hi is None or not np.isfinite(lo) or not np.isfinite(hi):
        return False
    return (lo > 0) or (hi < 0)


# ═════════════════════════════════════════════════════════════════════════════
# MATCHING — cap-at-tag decile x pre-tag liquidity tercile, same dates
# ═════════════════════════════════════════════════════════════════════════════
def _edges(v, q) -> np.ndarray:
    v = np.asarray([x for x in v if x is not None and np.isfinite(x)], dtype=float)
    if v.size == 0:
        return np.array([])
    return np.unique(np.nanpercentile(v, q))


def strata(events_df: pd.DataFrame) -> dict:
    """Cap-decile and liquidity-tercile edges, taken from the TAGGED
    distribution so the placebo is matched onto the cohort's own scale. PURE."""
    return {"cap": _edges(events_df.get("cap_at_tag", pd.Series(dtype=float)),
                          [10, 20, 30, 40, 50, 60, 70, 80, 90]),
            "liq": _edges(events_df.get("liq50_median", pd.Series(dtype=float)),
                          [100 / 3.0, 200 / 3.0])}


def bucket(v: Optional[float], edges: np.ndarray) -> int:
    """Stratum index for one value; -1 when unknown. PURE."""
    if v is None or not np.isfinite(v) or edges.size == 0:
        return -1
    return int(np.searchsorted(edges, v, side="right"))


def matched_placebo(ev: dict, panel: pd.DataFrame, k: int, rng,
                    refill: Optional[Callable] = None) -> list:
    """`k` never-tagged names in the SAME (cap decile, liquidity tercile) with a
    closable window on the SAME entry date. `match_fallback=True` when the
    stratum is thinner than k and the nearest cap decile is borrowed from.

    Never draws a tagged name - the panel is built from never-tagged symbols
    only. Each returned row carries the EVENT's symbol and date so the cluster
    bootstrap can hold an event and its placebos in one cluster.
    """
    if panel.empty or ev.get("cap_bucket", -1) < 0 or ev.get("liq_bucket", -1) < 0:
        return []
    d, cb, lb = ev["entry_date"], ev["cap_bucket"], ev["liq_bucket"]
    same_day = panel[panel["date"] == d]
    pick = same_day[(same_day["cap_bucket"] == cb) & (same_day["liq_bucket"] == lb)]
    if len(pick) < k and refill is not None:
        extra = refill(d)
        if extra is not None and not extra.empty:
            same_day = pd.concat([same_day, extra[extra["date"] == d]], ignore_index=True)
            pick = same_day[(same_day["cap_bucket"] == cb) & (same_day["liq_bucket"] == lb)]
    fallback = False
    if len(pick) < k:
        fallback = True
        near = same_day[same_day["liq_bucket"] == lb].copy()
        if near.empty:
            near = same_day.copy()
        if near.empty:
            return []
        near["_d"] = (near["cap_bucket"] - cb).abs()
        pick = near.sort_values("_d").head(max(k, 1) * 4)
    if pick.empty:
        return []
    take = pick.sample(n=min(k, len(pick)), random_state=int(rng.integers(0, 2 ** 31 - 1)))
    out = []
    for _, r in take.iterrows():
        out.append({"event_id": ev["event_id"], "symbol": ev["ticker"], "date": d,
                    "placebo_symbol": r["symbol"], "cap_bucket": int(r["cap_bucket"]),
                    "liq_bucket": int(r["liq_bucket"]), "match_fallback": fallback,
                    "cap_posthoc": bool(r.get("cap_posthoc", False)),
                    **{c: r[c] for c in r.index if c.startswith(("ret_", "dd_", "peak_", "close_ret_"))}})
    return out


# ═════════════════════════════════════════════════════════════════════════════
# PANELS — vectorised per-symbol forward windows
# ═════════════════════════════════════════════════════════════════════════════
def symbol_panel(sym: str, bars: list, dates: list, shares_row: Optional[dict]) -> list:
    """One row per requested entry date for a never-tagged pool name: the same
    forward windows, the same cap derivation and the same pre-entry liquidity
    the tagged cohort gets. PURE."""
    if not bars:
        return []
    idx = {b["date"]: i for i, b in enumerate(bars)}
    n = len(bars)
    op = np.array([b["open"] for b in bars], dtype=float)
    hi = np.array([b["high"] for b in bars], dtype=float)
    lo = np.array([b["low"] for b in bars], dtype=float)
    cl = np.array([b["close"] for b in bars], dtype=float)
    vo = np.array([b["volume"] for b in bars], dtype=float)
    dv = pd.Series(cl * vo).rolling(PRE_LIQ_BARS, min_periods=PRE_LIQ_BARS).median().shift(1).to_numpy()
    out = []
    for d in dates:
        i = idx.get(d)
        if i is None or i == 0 or not np.isfinite(op[i]) or op[i] <= 0:
            continue
        liq = dv[i]
        if not np.isfinite(liq):
            continue
        cap, cap_src, posthoc = cap_at_tag(shares_row, float(cl[i - 1]))
        row = {"symbol": sym, "date": d, "liq50_median": float(liq),
               "cap": cap, "cap_source": cap_src, "cap_posthoc": posthoc}
        for k in CLOCKS:
            if i + k - 1 <= n - 1:
                row["ret_%d" % k] = float(cl[i + k - 1] / op[i] - 1.0)
                row["dd_%d" % k] = float(lo[i:i + k].min() / op[i] - 1.0)
                row["peak_%d" % k] = float(hi[i:i + k].max() / op[i] - 1.0)
            else:
                row["ret_%d" % k] = np.nan
                row["dd_%d" % k] = np.nan
                row["peak_%d" % k] = np.nan
            if i - 1 + k <= n - 1 and cl[i - 1] > 0:
                row["close_ret_%d" % k] = float(cl[i - 1 + k] / cl[i - 1] - 1.0)
            else:
                row["close_ret_%d" % k] = np.nan
        if not np.isfinite(row["ret_%d" % CLOCKS[0]]):
            continue
        out.append(row)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# MONGO (every read behind a function; nothing is ever written)
# ═════════════════════════════════════════════════════════════════════════════
def _price_reader():
    coll = pc._coll("price_cache")
    if coll is None:
        return lambda s: None
    return lambda s: coll.find_one({"symbol": s.upper()})


def _shares_map(symbols: list) -> dict:
    try:
        from sepa import volume_movers as vm
        coll = vm._shares_coll()
    except Exception:                                          # noqa: BLE001
        coll = None
    if coll is None:
        return {}
    out = {}
    try:
        # `shares_cache` is keyed by `_id` = the symbol (volume_movers.shares_for
        # :79, :104) — there is no `symbol` field on the row.
        for d in coll.find({"_id": {"$in": [s.upper() for s in symbols]}}):
            out[str(d.get("_id") or "").upper()] = d
    except Exception as exc:                                   # noqa: BLE001
        P("  shares cache unreadable: %s" % exc)
    return out


def _tag_docs() -> list:
    coll = pc._tags_coll()
    if coll is None:
        raise SystemExit("promo_circuit_tags unreadable — nothing to measure")
    return list(coll.find({}))


def _pool_symbols(tagged: set) -> list:
    coll = pc._coll("price_cache")
    if coll is None:
        return []
    out = []
    try:
        for d in coll.find({}, {"symbol": 1}):
            s = (d.get("symbol") or "").upper()
            if s and s not in tagged:
                out.append(s)
    except Exception as exc:                                   # noqa: BLE001
        P("  price_cache listing failed: %s" % exc)
    return sorted(set(out))


# ═════════════════════════════════════════════════════════════════════════════
# REPLAY
# ═════════════════════════════════════════════════════════════════════════════
def context_line(sym: str, dates: list, reader: Callable) -> dict:
    """The benchmark's own median forward return over the SAME entry dates.
    CONTEXT ONLY — never the base of the Δ. The Δ is against the matched
    placebo; a broad-market line is here so a reader can see what the tape was
    doing, not so a promo name can be scored against it."""
    if not sym or not dates:
        return {}
    try:
        bars = norm_cache_bars(reader(sym))
    except Exception:                                          # noqa: BLE001
        return {}
    rows = symbol_panel(sym, bars, dates, None)
    if not rows:
        return {}
    D = pd.DataFrame(rows)
    return {"symbol": sym, "n_dates": int(len(D)),
            **{"median_ret_%d" % k: _nz(D["ret_%d" % k].median()) for k in CLOCKS}}


def replay(a) -> tuple:
    t0 = time.time()
    today = datetime.now(timezone.utc).astimezone(ET).date()
    refresh = None if a.no_refresh else (lambda s, since: pc._bars_since(s, since))
    reader = _price_reader()

    docs = _tag_docs()
    E = events(docs)
    if E.empty:
        raise SystemExit("no events")
    P("events: %d rows  %d tickers  %d accounts  first_ever %s..%s"
      % (len(E), E["ticker"].nunique(), E["account"].nunique(),
         E["first_ever_ts"].min().date(), E["first_ever_ts"].max().date()))

    shares = _shares_map(sorted(E["ticker"].unique()))
    P("shares rows for tagged names: %d of %d" % (len(shares), E["ticker"].nunique()))

    bar_cache: dict = {}
    src_counts = {"cache": 0, "refresh": 0, "none": 0}
    rows = []
    for _, e in E.iterrows():
        sym, ts = e["ticker"], e["event_ts"]
        need = (ts + timedelta(days=int(max(CLOCKS) * 1.6) + 10)).astimezone(ET).date()
        need = min(need, today)
        if sym not in bar_cache:
            bar_cache[sym] = bars_for(sym, ts, need, reader, refresh)
            src_counts[bar_cache[sym][1]] += 1
            if len(bar_cache) % 200 == 0:
                P("  bars %d names  %.0fs  %s" % (len(bar_cache), time.time() - t0, src_counts))
        bars, source = bar_cache[sym]
        i_tag = tagday_index(bars, ts)
        i_ent = entry_index(bars, ts)
        base = base_close(bars, i_tag)
        if not bars or bars[0]["date"] > ts.astimezone(ET).date() or i_tag in (None, 0) and base is None:
            status = "no_history"
        elif halted(bars, sym, today):
            status = "halted"
        elif i_ent is None:
            status = "unclosable"
        else:
            status = "ok"
        liq = pre_liquidity(bars, i_tag)
        cap, cap_src, posthoc = cap_at_tag(shares.get(sym), base)
        cap_today, _ = cap_warm.derive_cap({"market_cap": (shares.get(sym) or {}).get("market_cap")}, base)
        tm = tagday_move(bars, i_tag, base)
        r = {"account": e["account"], "ticker": sym, "raw_ticker": e["raw_ticker"],
             "tier": e["tier"], "event_ts": ts.isoformat(),
             "first_ever_ts": e["first_ever_ts"].isoformat(),
             "shotgun_kept": bool(e["shotgun_kept"]), "delisted": bool(e["delisted"]),
             "n_messages": int(e["n_messages"]),
             "entry_date": bars[i_ent]["date"].isoformat() if i_ent is not None else None,
             "base": base, "tagday_move": tm,
             "tagday_move_ge_8": (None if tm is None else bool(tm * 100.0 >= PROMO_MOVE_PCT)),
             "ran_first": ran_first(bars, i_tag, base), "dumped_21": dumped(bars, i_tag, 21),
             "liq50_mean": liq["liq50_mean"], "liq50_median": liq["liq50_median"],
             "under_20m": (None if liq["liq50_mean"] is None else bool(liq["liq50_mean"] < MIN_DOLLAR_VOL_20M)),
             "under_5m": (None if liq["liq50_median"] is None else bool(liq["liq50_median"] < MIN_DOLLAR_VOL_5M)),
             "under_2": (None if base is None else bool(base < MIN_SHARE_PRICE)),
             "cap_at_tag": cap, "cap_source": cap_src, "cap_posthoc": posthoc,
             "cap_today": cap_today,
             "cap_known": cap is not None,
             "cap_under_700m": (None if cap is None else bool(cap < MIN_CAP_USD)),
             "bar_source": source, "status": status, "match_fallback": False}
        for k in CLOCKS:
            f = forward(bars, i_ent, k, ts) if status in ("ok", "halted") else None
            r["ret_%d" % k] = None if f is None else f["ret"]
            r["dd_%d" % k] = None if f is None else f["dd"]
            r["peak_%d" % k] = None if f is None else f["peak"]
            cf = close_forward(bars, i_tag, k) if status in ("ok", "halted") else None
            r["close_ret_%d" % k] = None if cf is None else cf["ret"]
        # halted sensitivities: the last available close, and a total loss.
        if status == "halted" and i_ent is not None and bars and bars[i_ent]["open"]:
            r["halt_last_close_ret"] = bars[-1]["close"] / bars[i_ent]["open"] - 1.0
            r["halt_zero_ret"] = -1.0
        else:
            r["halt_last_close_ret"] = None
            r["halt_zero_ret"] = None
        rows.append(r)
    EV = pd.DataFrame(rows)
    st = EV["status"].value_counts().to_dict()
    P("replay: %d event rows  bar_source=%s  status=%s  %.0fs"
      % (len(EV), src_counts, st, time.time() - t0))

    # ── placebo panel ────────────────────────────────────────────────────────
    ok = EV[EV["entry_date"].notna()].copy()
    dates = sorted({_as_date(d) for d in ok["entry_date"].dropna().unique()})
    tagged = set(EV["ticker"].unique()) | set(EV["raw_ticker"].unique())
    pool = _pool_symbols(tagged)
    P("placebo pool: %d never-tagged price_cache symbols over %d entry dates"
      % (len(pool), len(dates)))
    pool_shares = _shares_map(pool) if pool else {}
    panel_rows, pending, n_pool_used = [], [], 0
    exit_need = max(dates) if dates else today
    for s in pool:
        row = None
        try:
            row = reader(s)
        except Exception:                                      # noqa: BLE001
            row = None
        bars = norm_cache_bars(row)
        if not bars or bars[-1]["date"] < exit_need:
            pending.append(s)
            continue
        pr = symbol_panel(s, bars, dates, pool_shares.get(s))
        if pr:
            n_pool_used += 1
            panel_rows.extend(pr)
    P("placebo panel: %d rows from %d cache-fresh names; %d stale/short held back "
      "for lazy refresh (budget %d)" % (len(panel_rows), n_pool_used, len(pending), a.pool_refresh_max))
    ctx = context_line(a.context, dates, reader)
    if ctx:
        P("context %s over the same entry dates: %s" % (a.context, ctx))
    PANEL = pd.DataFrame(panel_rows)
    return EV, PANEL, pending, pool_shares, refresh, reader, dates, src_counts, ctx


def build_placebo(EV: pd.DataFrame, PANEL: pd.DataFrame, pending: list, pool_shares: dict,
                  refresh, reader, dates: list, a) -> tuple:
    """Draw `--k` matched placebos per closable event. Thin strata pull the
    lazy pool refresh, bounded by `--pool-refresh-max`."""
    if PANEL.empty:
        return pd.DataFrame(), {"refreshed": 0, "fallback": 0}
    ok = EV[EV["ret_%d" % CLOCKS[0]].notna()].copy()
    if ok.empty:
        return pd.DataFrame(), {"refreshed": 0, "fallback": 0}
    S = strata(ok)
    PANEL = PANEL.copy()
    PANEL["cap_bucket"] = [bucket(v, S["cap"]) for v in PANEL["cap"]]
    PANEL["liq_bucket"] = [bucket(v, S["liq"]) for v in PANEL["liq50_median"]]
    PANEL = PANEL[(PANEL["cap_bucket"] >= 0) & (PANEL["liq_bucket"] >= 0)]
    state = {"refreshed": 0, "pending": list(pending)}

    def refill(_d):
        """Lazy pool refresh: pull the next names off the stale list, fetch each
        as a WHOLE fresh series, and extend the panel. Bounded and counted."""
        if refresh is None or state["refreshed"] >= a.pool_refresh_max or not state["pending"]:
            return None
        batch, got = [], []
        while state["pending"] and len(batch) < 40 and state["refreshed"] < a.pool_refresh_max:
            batch.append(state["pending"].pop(0))
            state["refreshed"] += 1
        for s in batch:
            try:
                bars = norm_agg_bars(refresh(s, min(dates) - timedelta(days=120)))
            except Exception:                                  # noqa: BLE001
                bars = []
            got.extend(symbol_panel(s, bars, dates, pool_shares.get(s)))
        if not got:
            return None
        G = pd.DataFrame(got)
        G["cap_bucket"] = [bucket(v, S["cap"]) for v in G["cap"]]
        G["liq_bucket"] = [bucket(v, S["liq"]) for v in G["liq50_median"]]
        G = G[(G["cap_bucket"] >= 0) & (G["liq_bucket"] >= 0)]
        nonlocal PANEL
        PANEL = pd.concat([PANEL, G], ignore_index=True)
        return G

    rng = np.random.default_rng(a.seed)
    rows, fb = [], 0
    for eid, e in ok.iterrows():
        ev = {"event_id": int(eid), "ticker": e["ticker"],
              "entry_date": _as_date(e["entry_date"]),
              "cap_bucket": bucket(e["cap_at_tag"], S["cap"]),
              "liq_bucket": bucket(e["liq50_median"], S["liq"])}
        got = matched_placebo(ev, PANEL, a.k, rng, refill)
        if got and got[0]["match_fallback"]:
            fb += 1
        rows.extend(got)
    Pf = pd.DataFrame(rows)
    P("placebo draws: %d rows for %d events (k=%d); fallback strata %d; pool refreshes %d"
      % (len(Pf), len(ok), a.k, fb, state["refreshed"]))
    return Pf, {"refreshed": state["refreshed"], "fallback": fb,
                "cap_edges": [float(x) for x in S["cap"]],
                "liq_edges": [float(x) for x in S["liq"]]}


# ═════════════════════════════════════════════════════════════════════════════
# STATS
# ═════════════════════════════════════════════════════════════════════════════
def line_key(split: str, clock: int, entry: str, cohort: str, cut: str) -> str:
    return "%s|%d|%s|%s|%s" % (split, clock, entry, cohort, cut)


def _nz(v) -> float:
    """float(v) with None / non-numeric / inf all collapsing to NaN. PURE."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return f if np.isfinite(f) else float("nan")


def _fmt_ci(ci: dict) -> str:
    lo, hi = _nz(ci.get("lo")), _nz(ci.get("hi"))
    if not np.isfinite(lo) or not np.isfinite(hi):
        return "n/a (%d clusters)" % (ci.get("n_clusters") or 0)
    return "[%+.2f%%, %+.2f%%]" % (100 * lo, 100 * hi)


def one_line(K: pd.DataFrame, B: pd.DataFrame, col: str, draws: int, seed: int) -> dict:
    kv = pd.to_numeric(K[col], errors="coerce").dropna().to_numpy() if len(K) else np.array([])
    bv = pd.to_numeric(B[col], errors="coerce").dropna().to_numpy() if len(B) else np.array([])
    nan = float("nan")
    cd = cluster_median_delta(K, B, col, "date", draws, seed)
    cs = cluster_median_delta(K, B, col, "symbol", draws, seed + 1)
    wins = int((kv > 0).sum())
    dd_col = col.replace("ret_", "dd_") if col.startswith("ret_") else None
    dd = pd.to_numeric(K[dd_col], errors="coerce").dropna().to_numpy() if (dd_col and dd_col in K) else np.array([])
    return {"n": int(kv.size), "n_placebo": int(bv.size),
            "n_date_clusters": int(cd["n_clusters"]), "n_symbol_clusters": int(cs["n_clusters"]),
            "median": float(np.median(kv)) if kv.size else nan,
            "placebo_median": float(np.median(bv)) if bv.size else nan,
            "delta": cd["delta"], "ci_date": [cd["lo"], cd["hi"]], "p_le0": cd["p_le0"],
            "ci_symbol": [cs["lo"], cs["hi"]],
            "date_excl0": excludes_zero(cd), "symbol_excl0": excludes_zero(cs),
            "win_pct": 100.0 * wins / kv.size if kv.size else nan,
            "win_ci": [100 * x for x in wilson(wins, int(kv.size))],
            "median_dd": float(np.median(dd)) if dd.size else nan,
            "trimmed_mean": trimmed_mean(kv)}


def _cuts(K: pd.DataFrame) -> list:
    out = [("all", K)]
    for t in ("S", "A", "B"):
        sub = K[K["tier"] == t]
        if len(sub):
            out.append(("tier:%s" % t, sub))
    for acct, sub in K.groupby("account"):
        if len(sub) >= MIN_ACCOUNT_N:
            out.append(("account:%s" % acct, sub))
    return out


def _med(D: pd.DataFrame, col: str) -> float:
    if col not in D.columns:
        return float("nan")
    return _nz(pd.to_numeric(D[col], errors="coerce").median())


def base_rates(K: pd.DataFrame, EV: pd.DataFrame, src_counts: dict, extra: dict) -> dict:
    def pct(mask_col, frame=None):
        f = EV if frame is None else frame
        v = f[mask_col].dropna() if mask_col in f else pd.Series(dtype=float)
        return 100.0 * float(v.astype(bool).mean()) if len(v) else float("nan")
    n = max(len(EV), 1)
    capk = EV[EV["cap_known"] == True] if "cap_known" in EV else EV.iloc[0:0]   # noqa: E712
    return {
        "n_events": int(len(EV)),
        "ran_first_pct": pct("ran_first"), "tagday_move_ge_8_pct": pct("tagday_move_ge_8"),
        "dumped_21_pct": pct("dumped_21"),
        "median_dd_5": _med(EV, "dd_5"), "median_dd_21": _med(EV, "dd_21"),
        "under_20m_pct": pct("under_20m"), "under_5m_pct": pct("under_5m"),
        "under_2_pct": pct("under_2"),
        "cap_under_700m_pct_of_known": (100.0 * float(capk["cap_under_700m"].astype(bool).mean())
                                        if len(capk) else float("nan")),
        "cap_unknown_pct": 100.0 * float((~EV["cap_known"].astype(bool)).mean()) if len(EV) else float("nan"),
        "cap_posthoc_pct": pct("cap_posthoc"),
        "unclosable_pct": 100.0 * float((EV["status"] == "unclosable").mean()) if len(EV) else float("nan"),
        "halted_pct": 100.0 * float((EV["status"] == "halted").mean()) if len(EV) else float("nan"),
        "no_history_pct": 100.0 * float((EV["status"] == "no_history").mean()) if len(EV) else float("nan"),
        "n_cache": int(src_counts.get("cache", 0)), "n_refresh": int(src_counts.get("refresh", 0)),
        "n_no_bars": int(src_counts.get("none", 0)),
        "pct_of_events": round(100.0 * len(K) / n, 1),
        **extra,
    }


def report(EV: pd.DataFrame, PL: pd.DataFrame, a, src_counts: dict, extra: dict) -> dict:
    """Every line of the cross-product, each with its cluster counts."""
    EV = EV.copy()
    EV["symbol"] = EV["ticker"]
    EV["date"] = [_as_date(d) for d in EV["entry_date"]]
    EV["split"] = np.where(pd.to_datetime(EV["first_ever_ts"], utc=True)
                           < pd.Timestamp(a.oos_from, tz="UTC"), "IS", "OOS")
    if not PL.empty:
        PL = PL.copy()
        PL["date"] = [_as_date(d) if not isinstance(d, _date) else d for d in PL["date"]]
        sp = EV.set_index(EV.index)["split"].to_dict()
        tier = EV["tier"].to_dict()
        acct = EV["account"].to_dict()
        sg = EV["shotgun_kept"].to_dict()
        PL["split"] = PL["event_id"].map(sp)
        PL["tier"] = PL["event_id"].map(tier)
        PL["account"] = PL["event_id"].map(acct)
        PL["shotgun_kept"] = PL["event_id"].map(sg)

    lines = {}
    for cohort in ("all", "shotgun_kept"):
        Kc = EV if cohort == "all" else EV[EV["shotgun_kept"].astype(bool)]
        Bc = PL if (PL.empty or cohort == "all") else PL[PL["shotgun_kept"].astype(bool)]
        for split in ("pooled", "IS", "OOS"):
            Ks = Kc if split == "pooled" else Kc[Kc["split"] == split]
            Bs = Bc if (Bc.empty or split == "pooled") else Bc[Bc["split"] == split]
            for cut, Kx in _cuts(Ks):
                if Bs.empty:
                    Bx = Bs
                else:
                    Bx = Bs[Bs["event_id"].isin(Kx.index)]
                for clock in CLOCKS:
                    for entry in ("open", "close"):
                        col = ("ret_%d" if entry == "open" else "close_ret_%d") % clock
                        if col not in Kx.columns:
                            continue
                        ln = one_line(Kx, Bx if col in Bx.columns else Bx.iloc[0:0], col, a.draws, a.seed)
                        ln.update({"split": split, "clock": clock, "entry": entry,
                                   "cohort": cohort, "cut": cut,
                                   "is_only_21": clock == 21})
                        lines[line_key(split, clock, entry, cohort, cut)] = ln
    K_primary = EV[EV["shotgun_kept"].astype(bool)]
    return {"lines": lines, "as_of": datetime.now(timezone.utc).date().isoformat(),
            "oos_from": a.oos_from, "min_clusters": MIN_CLUSTERS, "rerun_after": RERUN_AFTER,
            "draws": a.draws, "seed": a.seed, "k": a.k,
            "base_rates": base_rates(K_primary, EV, src_counts, extra),
            "script": SCRIPT}


def verdict(rep: dict) -> str:
    """Mechanical, printed above the tables. PRIMARY = POOLED, 5 sessions, open
    entry, shotgun-pruned cohort, all tiers.

    In-sample is the window the promo roster was selected in - it is biased
    POSITIVE by construction. The positive branch is therefore the hardest to
    reach: it needs both cluster CIs off zero, the OOS-5 SIGN to agree, and at
    least one tier's pooled line to carry it. A NaN symbol-CI is read as "does
    not exclude zero", never as agreement.
    """
    L = rep.get("lines", {})
    prim = L.get(line_key(*PRIMARY))
    if not prim:
        return "insufficient — no primary line; re-run after %s" % RERUN_AFTER
    lo = _nz((prim.get("ci_date") or [None, None])[0])
    if not np.isfinite(lo):
        return ("insufficient — %d date clusters; re-run after %s"
                % (prim.get("n_date_clusters", 0), RERUN_AFTER))
    d = _nz(prim.get("delta"))
    dx = bool(prim.get("date_excl0"))
    sx = bool(prim.get("symbol_excl0"))
    if dx and np.isfinite(d) and d < 0:
        if sx:
            return "inverted — do-not-chase radar; not a source of entries"
        return "inverted on dates, null on symbols — radar only"
    if not dx or not sx:
        return "null — not a source of entries; radar only"
    if not np.isfinite(d) or d <= 0:
        return "null — not a source of entries; radar only"
    oos = L.get(line_key("OOS", 5, "open", "shotgun_kept", "all")) or {}
    od = _nz(oos.get("delta"))
    if not np.isfinite(od) or od <= 0:
        return "positive pooled, OOS sign disagrees — null until re-run"
    carried = [k for k in ("tier:S", "tier:A", "tier:B")
               if (L.get(line_key("pooled", 5, "open", "shotgun_kept", k)) or {}).get("date_excl0")
               and _nz((L.get(line_key("pooled", 5, "open", "shotgun_kept", k)) or {}).get("delta")) > 0]
    if not carried:
        return "positive pooled, no tier carries it — null until re-run"
    return ("positive — pooled Δmedian %+.2f%% at 5 sessions, OOS sign agrees, carried by %s; "
            "re-run after %s" % (100 * d, ",".join(carried), RERUN_AFTER))


def print_report(rep: dict) -> None:
    L = rep["lines"]
    oos = L.get(line_key("OOS", 5, "open", "shotgun_kept", "all")) or {}
    od = _nz(oos.get("delta"))
    oos_tail = ("   oos_5: sign=%s, n=%d, clusters=%d, ci=%s"
                % (("+" if od > 0 else "−") if np.isfinite(od) else "?",
                   oos.get("n") or 0, oos.get("n_date_clusters") or 0,
                   _fmt_ci({"lo": (oos.get("ci_date") or [None, None])[0],
                            "hi": (oos.get("ci_date") or [None, None])[1],
                            "n_clusters": oos.get("n_date_clusters") or 0})))
    P("=" * 130)
    P("VERDICT (pooled · 5 sessions · open entry · shotgun_kept · all tiers): %s" % verdict(rep))
    P("  MIN_CLUSTERS=%d   RERUN_AFTER=%s   oos_clean=False" % (MIN_CLUSTERS, RERUN_AFTER))
    P("=" * 130)
    hdr = ("%-8s %-3s %-5s %-13s %-16s %6s %5s %5s %9s %9s %9s %-22s %-22s %6s %9s"
           % ("split", "k", "entry", "cohort", "cut", "n", "dC", "sC", "median",
              "placebo", "delta", "ci_date", "ci_symbol", "win%", "median_dd"))
    for cohort in ("shotgun_kept", "all"):
        for entry in ("open", "close"):
            P("")
            P("-" * 130)
            P("cohort=%s  entry=%s%s" % (cohort, entry, oos_tail))
            P("-" * 130)
            P(hdr)
            for split in ("pooled", "IS", "OOS"):
                for clock in CLOCKS:
                    sel = [ln for ln in L.values()
                           if (ln["split"], ln["clock"], ln["entry"], ln["cohort"])
                           == (split, clock, entry, cohort)]
                    order = {"all": 0, "tier:S": 1, "tier:A": 2, "tier:B": 3}
                    for ln in sorted(sel, key=lambda x: (order.get(x["cut"], 9), x["cut"])):
                        tail = "  [IS-only, not OOS-closable before ~2026-10-01]" if clock == 21 else ""
                        P("%-8s %-3d %-5s %-13s %-16s %6d %5d %5d %+8.2f%% %+8.2f%% %+8.2f%% %-22s %-22s %5.1f%% %+8.2f%%%s"
                          % (split, clock, entry, cohort, ln["cut"], ln["n"],
                             ln["n_date_clusters"], ln["n_symbol_clusters"],
                             100 * _nz(ln["median"]), 100 * _nz(ln["placebo_median"]),
                             100 * _nz(ln["delta"]),
                             _fmt_ci({"lo": ln["ci_date"][0], "hi": ln["ci_date"][1],
                                      "n_clusters": ln["n_date_clusters"]}),
                             _fmt_ci({"lo": ln["ci_symbol"][0], "hi": ln["ci_symbol"][1],
                                      "n_clusters": ln["n_symbol_clusters"]}),
                             _nz(ln["win_pct"]), 100 * _nz(ln["median_dd"]), tail))
    P("")
    P("-" * 130)
    P("BASE RATES (every tagged event, closable or not)")
    P("-" * 130)
    for k, v in rep["base_rates"].items():
        P("  %-32s %s" % (k, ("%.2f" % v) if isinstance(v, float) else v))


def emit_measured(rep: dict) -> dict:
    L = rep["lines"]
    prim = L.get(line_key(*PRIMARY)) or {}
    oos = L.get(line_key("OOS", 5, "open", "shotgun_kept", "all")) or {}
    od = _nz(oos.get("delta"))
    oci = oos.get("ci_date") or [None, None]
    return {
        "as_of": rep.get("as_of"), "primary": "pooled-5-open",
        "n_5": prim.get("n"), "n_date_clusters_5": prim.get("n_date_clusters"),
        "delta_5": prim.get("delta"), "ci_date_5": prim.get("ci_date"),
        "ci_symbol_5": prim.get("ci_symbol"), "placebo_median_5": prim.get("placebo_median"),
        "oos_5": {"n": oos.get("n"), "clusters": oos.get("n_date_clusters"),
                  "sign": (None if not np.isfinite(od) else ("+" if od > 0 else "−")),
                  "ci": (None if not np.isfinite(_nz(oci[0])) else [oci[0], oci[1]])},
        "oos_clean": False, "rerun_after": RERUN_AFTER,
        "verdict": verdict(rep), "script": SCRIPT,
    }


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return None if not np.isfinite(f) else f
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (_date, datetime)):
        return o.isoformat()
    return o


def _placebo_path(out: str) -> str:
    return out[:-4] + "_placebo.csv" if out.endswith(".csv") else out + ".placebo.csv"


# ═════════════════════════════════════════════════════════════════════════════
def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage", default="both", choices=("replay", "stats", "both"))
    ap.add_argument("--out", default="/tmp/promo_tag_events.csv")
    ap.add_argument("--from-csv", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--emit-measured", default=None)
    ap.add_argument("--no-refresh", action="store_true",
                    help="cache only; stale rows read as unclosable (smoke)")
    ap.add_argument("--pool-refresh-max", type=int, default=800)
    ap.add_argument("--k", type=int, default=5, help="matched placebo draws per event")
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--oos-from", default="2026-09-03")
    ap.add_argument("--context", default="RSP")
    a = ap.parse_args(argv)

    src_counts, extra = {}, {}
    if a.stage in ("replay", "both"):
        EV, PANEL, pending, pool_shares, refresh, reader, dates, src_counts, ctx = replay(a)
        PL, meta = build_placebo(EV, PANEL, pending, pool_shares, refresh, reader, dates, a)
        extra = {"context": ctx, "pool_refreshed": meta.get("refreshed", 0),
                 "match_fallback_events": meta.get("fallback", 0),
                 "cap_decile_edges": meta.get("cap_edges", []),
                 "liq_tercile_edges": meta.get("liq_edges", [])}
        EV.to_csv(a.out, index=True, index_label="event_id")
        PL.to_csv(_placebo_path(a.out), index=False)
        P("wrote %s (%d rows) and %s (%d rows)"
          % (a.out, len(EV), _placebo_path(a.out), len(PL)))
        json.dump(_clean({"src_counts": src_counts, **extra}),
                  open(a.out + ".meta.json", "w"), indent=1)
        a.from_csv = a.out

    if a.stage in ("stats", "both"):
        if not a.from_csv:
            ap.error("--from-csv is required for --stage stats")
        EV = pd.read_csv(a.from_csv, index_col="event_id")
        pp = _placebo_path(a.from_csv)
        PL = pd.read_csv(pp) if os.path.exists(pp) else pd.DataFrame()
        if not src_counts and os.path.exists(a.from_csv + ".meta.json"):
            m = json.load(open(a.from_csv + ".meta.json"))
            src_counts = m.pop("src_counts", {})
            extra = m
        rep = report(EV, PL, a, src_counts, extra)
        print_report(rep)
        if a.json:
            json.dump(_clean(rep), open(a.json, "w"), indent=1)
            P("wrote %s" % a.json)
        meas = _clean(emit_measured(rep))
        if a.emit_measured:
            json.dump(meas, open(a.emit_measured, "w"), indent=1)
            P("wrote %s" % a.emit_measured)
        P("")
        P("# ---- MEASURED literal (the MAIN SESSION pastes this into catalysts/promo_curate.py) ----")
        P("MEASURED = " + pprint.pformat(meas, width=100, sort_dicts=False))


if __name__ == "__main__":
    main()
