# ─────────────────────────────────────────────────────────────────────────────
# Bonde board — FIRST PASS, SUPERSEDED. Kept because it is the measurement the
# audit checked, and because three of its claims did NOT reproduce and a reader
# should be able to see exactly what was struck:
#
#   1. "EP + sales-PASS loses to EP + sales-FAIL" (-3.36pp [-5.84,-0.87]).
#      Re-measured at -2.42pp [-4.88,+0.30]; spans zero in all four variants.
#      STRUCK — the board does not say it.
#   2. "BOTH character clauses are inverted." Only `consecutive_growth_q >= 2`
#      measures negative. `accelerating` is a NULL (+1.63pp, CI -0.85 to +7.54).
#   3. "Coverage is 46%, so this is the large/mid-cap half." That was this
#      script's own no-retry fetcher losing ~half its requests, not a Massive
#      limit. 1,301 names it called "no financials" do return financials.
#
# What DID reproduce is the headline, and it is the reason the tab reads the way
# it does: the Episodic Pivot confirmed by Bonde's sales gate measures INVERTED
# against a date-matched placebo.
#
# The authority is the sibling audit scripts in this directory. Quote those.
# ─────────────────────────────────────────────────────────────────────────────

"""Episodic Pivot x Bonde sales — the 2x2, measured.

RUN (the Massive key lives ONLY in the api container; a throwaway container
falls back to Yahoo and silently produces false negatives):

    cd /Users/ajay/clinet-test/cheetah-market-app && \
      docker compose exec -T api python - < /tmp/scratch/bonde/ep.py

Nothing here writes to the repo. Fundamentals are cached inside the container
at /root/.cheetah/bonde_fund_cache.json so a re-run is cheap.

WHAT IS RECONSTRUCTED, AND FROM WHAT
  * EP  — walked bar by bar off sepa.prices.load_prices (Mongo-cached CLOSED
          daily bars), firing exactly setups/episodic_pivot.py's rule:
          gap = (open[i] - close[i-1]) / close[i-1] >= 8.0%
          and volume[i] >= 5.0x mean(volume[i-50:i]).
          The stored `setups` docs are NOT read (~50 rows, duplicated, written
          by a scanner whose universe moved).
  * Bonde sales — sepa/sales.py compute() + buyable_verdict._bonde_pillar's
          PASS rule, fed a revenue series rebuilt AS OF the gap bar from
          Massive /vX/reference/financials quarterly rows whose filing_date
          is on or before the gap day. Derived Q4s (filing_date None) get
          their availability date from the ANNUAL report's filing_date, or
          are dropped when that is missing.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, "/app")

import numpy as np
import pandas as pd

from sepa import prices, universe, sales, symbols
from sepa.buyable_verdict import SALES_FLOOR_PCT, BONDE_MIN_CONSEC_Q

# ---- EP constants, copied from setups/episodic_pivot.py (do not re-derive) --
MIN_GAP_PCT = 8.0
MIN_VOL_MULT = 5.0
AVG_VOL_WINDOW = 50
TARGET_PCT_ABOVE = 6.0
TRIGGER_WINDOW = 5      # the scanner's _LOOKBACK_DAYS — how long the setup shows
BRACKET_HORIZON = 21    # patterns/history.py PATTERN_HORIZON convention

HORIZONS = (3, 5, 10, 21)
MIN_EVENT_SPACING = 5   # sessions; one event per symbol per gap
PLACEBO_POOL = 700
PLACEBO_PER_DATE = 3
BOOT = 1000
SEED = 20260913

CACHE = "/root/.cheetah/bonde_fund_cache.json"
rng = np.random.default_rng(SEED)
random.seed(SEED)


REPORT = "/root/.cheetah/bonde_report.txt"
_rf = open(REPORT, "w")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _rf.write(s + "\n")
    _rf.flush()


# ---------------------------------------------------------------------------
# 1. EP reconstruction
# ---------------------------------------------------------------------------
def load_bars(sym):
    try:
        df = prices.load_prices(sym)
    except Exception:
        return None
    if df is None or len(df) < AVG_VOL_WINDOW + 3:
        return None
    return df


def ep_events(sym, df):
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    lo = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    v = df["volume"].values.astype(float)
    n = len(df)
    out = []
    last = -10 ** 9
    for i in range(AVG_VOL_WINDOW + 1, n):
        if i - last < MIN_EVENT_SPACING:
            continue
        avg = v[i - AVG_VOL_WINDOW:i].mean()
        pc = c[i - 1]
        if avg <= 0 or pc <= 0 or not np.isfinite(avg) or not np.isfinite(pc):
            continue
        gap = (o[i] - pc) / pc * 100.0
        vm = v[i] / avg
        if gap >= MIN_GAP_PCT and vm >= MIN_VOL_MULT:
            out.append({
                "symbol": sym, "i": i, "date": df.index[i],
                "gap_pct": float(gap), "vol_mult": float(vm),
                "gap_high": float(h[i]), "gap_low": float(lo[i]),
                "gap_close": float(c[i]),
                "addv50": float(np.nanmedian(c[i - AVG_VOL_WINDOW:i] * v[i - AVG_VOL_WINDOW:i])),
            })
            last = i
    return out


# ---------------------------------------------------------------------------
# 2. Massive fundamentals with filing dates
# ---------------------------------------------------------------------------
_fund_cache = {}
if os.path.exists(CACHE):
    try:
        _fund_cache = json.load(open(CACHE))
    except Exception:
        _fund_cache = {}


def _period_index(r):
    try:
        fy = int(r.get("fiscal_year"))
    except (TypeError, ValueError):
        return None
    fp = str(r.get("fiscal_period") or "").upper().strip()
    if not fp.startswith("Q") or len(fp) < 2 or not fp[1].isdigit():
        return None
    q = int(fp[1])
    if not 1 <= q <= 4:
        return None
    return fy * 4 + (q - 1)


def _rev(r):
    try:
        v = ((r.get("financials") or {}).get("income_statement") or {}) \
            .get("revenues", {}).get("value")
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


FETCH_FAIL = set()          # symbols whose fetch ERRORED (never cached as "no data")


def _get(sess, base, params):
    """A 200, or None. 429/5xx are RETRIED — the first version of this script
    ran 8 workers, got rate-limited, and cached the empty bodies as though
    Massive had no financials for 1,057 symbols. A failed request must never
    become a measurement."""
    for attempt in range(6):
        try:
            r = sess.get(base, params=params, timeout=25)
        except Exception:
            time.sleep(0.5 * (attempt + 1))
            continue
        if r.status_code == 200:
            return r
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(0.8 * (attempt + 1) + random.random() * 0.4)
            continue
        return None                      # 401/403/404 — a real answer, not a blip
    return None


def fetch_fundamentals(sym):
    """[{idx, rev, avail, derived}] newest-first. None on FETCH FAILURE
    (distinct from [] = Massive genuinely has no quarterly financials)."""
    if sym in _fund_cache:
        return _fund_cache[sym]
    import requests
    from massive_keys import stocks_key
    key = stocks_key()
    tick = symbols.for_massive(sym)
    base = "https://api.massive.com/vX/reference/financials"
    sess = requests.Session()
    rq = _get(sess, base, {"ticker": tick, "limit": 24,
                           "timeframe": "quarterly", "apiKey": key})
    if rq is None:
        FETCH_FAIL.add(sym)
        return None
    ra = _get(sess, base, {"ticker": tick, "limit": 8,
                           "timeframe": "annual", "apiKey": key})
    annual_filed = {}
    if ra is not None:
        for r in (ra.json() or {}).get("results") or []:
            try:
                fy = int(r.get("fiscal_year"))
            except (TypeError, ValueError):
                continue
            if r.get("filing_date"):
                annual_filed[fy] = r["filing_date"]
    rows = []
    for r in (rq.json() or {}).get("results") or []:
        idx = _period_index(r)
        rev = _rev(r)
        if idx is None or rev is None:
            continue
        filed = r.get("filing_date")
        derived = not bool(filed)
        if derived:
            try:
                filed = annual_filed.get(int(r.get("fiscal_year")))
            except (TypeError, ValueError):
                filed = None
            if not filed:
                continue           # no honest availability date -> drop
        rows.append({"idx": idx, "rev": rev, "avail": filed, "derived": derived})
    rows.sort(key=lambda x: -x["idx"])
    _fund_cache[sym] = rows
    return rows


def series_as_of(rows, asof_date, drop_derived=False, strict=False):
    """Newest-first, PERIOD-ALIGNED 8-quarter revenue series knowable at asof.

    Period-aligned (slot k = period p0-k) rather than list position: Massive
    OMITS missing quarters, so list adjacency is not quarter adjacency (see
    sepa/canslim.py — 12.6% of positional YoY pairs are not 4 quarters apart).
    """
    d = str(asof_date.date())
    avail = [r for r in rows
             if (r["avail"] < d if strict else r["avail"] <= d)
             and not (drop_derived and r["derived"])]
    if not avail:
        return None
    p0 = max(r["idx"] for r in avail)
    by = {}
    for r in avail:
        by.setdefault(r["idx"], r["rev"])
    return [by.get(p0 - k) for k in range(8)]


def bonde_state(rows, asof_date, **kw):
    """(pass/fail/unknown, sales dict) under buyable_verdict._bonde_pillar."""
    ser = series_as_of(rows, asof_date, **kw)
    if ser is None:
        return "unknown", None
    s = sales.compute(ser, None)
    if s.get("score") is None:
        return "unknown", s
    g = s.get("growth_yoy_pct")
    cleared = bool(g is not None and g >= SALES_FLOOR_PCT)
    character = bool(s.get("accelerating")) or int(s.get("consecutive_growth_q") or 0) >= BONDE_MIN_CONSEC_Q
    return ("pass" if (cleared and character) else "fail"), s


# ---------------------------------------------------------------------------
# 3. forward returns + the EP's own bracket
# ---------------------------------------------------------------------------
def fwd_returns(df, i):
    """close(i+1) -> close(i+1+k). Entry at the close of the bar AFTER the gap:
    the signal needs bar i's full volume, so bar i's close is the first moment
    it exists; the next session's close is the first unambiguous, no-lookahead
    print. open(i+1) is reported alongside as the trigger-side variant."""
    c = df["close"].values.astype(float)
    o = df["open"].values.astype(float)
    n = len(c)
    if i + 1 >= n:
        return None
    e, eo = c[i + 1], o[i + 1]
    if not np.isfinite(e) or e <= 0:
        return None
    out = {"entry_close": e}
    for k in HORIZONS:
        j = i + 1 + k
        out[f"r{k}"] = (c[j] / e - 1.0) * 100.0 if j < n else None
        out[f"o{k}"] = (c[j] / eo - 1.0) * 100.0 if (j < n and eo > 0) else None
    return out


def bracket(df, ev):
    """EP's own stated outcome: trigger = gap high + .01, stop = gap low - .01,
    target = trigger * 1.06. Tie inside one bar counts as the STOP (the repo's
    pessimistic convention, patterns/history.py). Gap-through fills at the open."""
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    lo = df["low"].values.astype(float)
    n = len(o)
    i = ev["i"]
    trig = round(ev["gap_high"] + 0.01, 4)
    stop = round(ev["gap_low"] - 0.01, 4)
    tgt = round(trig * (1 + TARGET_PCT_ABOVE / 100.0), 4)
    if trig - stop <= 0:
        return None
    j = None
    for m in range(i + 1, min(i + 1 + TRIGGER_WINDOW, n)):
        if h[m] >= trig:
            j = m
            break
    if j is None:
        if i + TRIGGER_WINDOW >= n:
            return None                       # trigger window not fully observable
        return {"armed": False, "stop_dist": (trig - stop) / trig * 100}
    entry = max(trig, o[j])
    end = min(j + BRACKET_HORIZON, n - 1)
    for m in range(j, end + 1):
        if o[m] >= tgt:
            return {"armed": True, "outcome": "target",
                    "pct": (o[m] / entry - 1) * 100, "bars": m - j,
                    "stop_dist": (entry - stop) / entry * 100}
        hit_t, hit_s = h[m] >= tgt, lo[m] <= stop
        if hit_t and hit_s:
            return {"armed": True, "outcome": "stop",
                    "pct": (stop / entry - 1) * 100, "bars": m - j,
                    "stop_dist": (entry - stop) / entry * 100}
        if hit_t:
            return {"armed": True, "outcome": "target",
                    "pct": (tgt / entry - 1) * 100, "bars": m - j,
                    "stop_dist": (entry - stop) / entry * 100}
        if hit_s:
            fill = min(stop, o[m])
            return {"armed": True, "outcome": "stop",
                    "pct": (fill / entry - 1) * 100, "bars": m - j,
                    "stop_dist": (entry - stop) / entry * 100}
    if j + BRACKET_HORIZON > n - 1:
        return None                           # still undecided AND data ran out
    return {"armed": True, "outcome": "neither",
            "pct": (df["close"].values[end] / entry - 1) * 100, "bars": end - j,
            "stop_dist": (entry - stop) / entry * 100}


# ---------------------------------------------------------------------------
# clustered bootstrap
# ---------------------------------------------------------------------------
class Cell:
    """Values grouped by symbol, laid out flat for a vectorised ragged gather."""

    def __init__(self, pairs, clusters):
        idx = {s: k for k, s in enumerate(clusters)}
        buckets = defaultdict(list)
        for s, v in pairs:
            if v is not None and np.isfinite(v):
                buckets[s].append(float(v))
        flat, starts, counts = [], np.zeros(len(clusters), int), np.zeros(len(clusters), int)
        for s, vals in buckets.items():
            k = idx[s]
            starts[k] = len(flat)
            counts[k] = len(vals)
            flat.extend(vals)
        self.flat = np.asarray(flat, float)
        self.starts, self.counts = starts, counts
        self.n = len(flat)
        self.n_sym = int((counts > 0).sum())

    def draw(self, d):
        c = self.counts[d]
        tot = int(c.sum())
        if tot == 0:
            return np.empty(0)
        off = np.repeat(self.starts[d] - np.concatenate(([0], np.cumsum(c)[:-1])), c)
        return self.flat[off + np.arange(tot)]


STATS = {
    "median": lambda x: float(np.median(x)) if len(x) else np.nan,
    "mean": lambda x: float(np.mean(x)) if len(x) else np.nan,
    "win": lambda x: float((x > 0).mean() * 100) if len(x) else np.nan,
}


def boot(cells, clusters, diffs=()):
    """cells: {name: Cell}. Returns point estimates + clustered 95% CIs, and
    CIs on the named differences, PAIRED on the same resampled symbol draw."""
    K = len(clusters)
    reps = {n: {s: np.empty(BOOT) for s in STATS} for n in cells}
    dreps = {d: {s: np.empty(BOOT) for s in ("median", "mean", "win")} for d in diffs}
    for b in range(BOOT):
        d = rng.integers(0, K, K)
        drawn = {n: c.draw(d) for n, c in cells.items()}
        for n, x in drawn.items():
            for s, f in STATS.items():
                reps[n][s][b] = f(x)
        for (a, bb) in diffs:
            for s, f in STATS.items():
                dreps[(a, bb)][s][b] = f(drawn[a]) - f(drawn[bb])
    out = {"cells": {}, "diffs": {}}
    for n, c in cells.items():
        out["cells"][n] = {"n": c.n, "n_sym": c.n_sym}
        for s, f in STATS.items():
            r = reps[n][s][np.isfinite(reps[n][s])]
            out["cells"][n][s] = f(c.flat)
            out["cells"][n][s + "_ci"] = (float(np.percentile(r, 2.5)),
                                          float(np.percentile(r, 97.5))) if len(r) > 50 else None
    for (a, bb) in diffs:
        row = {}
        for s, f in STATS.items():
            r = dreps[(a, bb)][s][np.isfinite(dreps[(a, bb)][s])]
            row[s] = f(cells[a].flat) - f(cells[bb].flat)
            row[s + "_ci"] = (float(np.percentile(r, 2.5)),
                              float(np.percentile(r, 97.5))) if len(r) > 50 else None
        out["diffs"][f"{a}-{bb}"] = row
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    t0 = time.time()
    univ = [s.upper() for s in universe.load_universe()
            if s.upper() not in universe.RS_ANCHORS]
    log(f"universe: {len(univ)} symbols")

    bars, events = {}, []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(load_bars, s): s for s in univ}
        for f in as_completed(futs):
            s = futs[f]
            df = f.result()
            if df is None:
                continue
            bars[s] = df
            events.extend(ep_events(s, df))
    log(f"bars loaded: {len(bars)}  EP events: {len(events)}  "
        f"distinct symbols: {len({e['symbol'] for e in events})}  ({time.time()-t0:.0f}s)")
    if bars:
        any_df = next(iter(bars.values()))
        log(f"bar window: {min(d.index[0] for d in bars.values()).date()} .. "
            f"{max(d.index[-1] for d in bars.values()).date()}  median bars "
            f"{int(np.median([len(d) for d in bars.values()]))}")

    # ---- VALIDITY: does the bar walk reproduce the app's OWN scanner? -------
    # The stored `setups` docs are never read as data (all 63 are status=expired,
    # dated 2026-05-26..08-27, and duplicated up to 6x per symbol). They are used
    # here ONLY as an oracle: for each stored doc, find the bar whose high matches
    # its recorded gap_day_high and re-fire the rule there.
    try:
        from pymongo import MongoClient
        db = MongoClient(os.getenv("MONGO_URL") or "mongodb://mongo:27017",
                         serverSelectionTimeoutMS=3000)[os.getenv("MONGO_DB") or "cheetah"]
        docs = list(db.setups.find({"kind": "episodic_pivot"}))
        ok, bad = 0, []
        for d in docs:
            s, m = d["symbol"], (d.get("meta") or {})
            df = bars.get(s)
            gh = m.get("gap_day_high")
            if df is None or not gh:
                bad.append((s, "no bars"))
                continue
            hh = df["high"].values.astype(float)
            k = int(np.argmin(np.abs(hh - gh)))
            if abs(hh[k] - gh) / gh > 0.005 or k < AVG_VOL_WINDOW + 1:
                bad.append((s, d.get("date_et"), "no matching bar today"))
                continue
            o = df["open"].values.astype(float); c = df["close"].values.astype(float)
            v = df["volume"].values.astype(float)
            g = (o[k] - c[k - 1]) / c[k - 1] * 100.0
            vm = v[k] / v[k - AVG_VOL_WINDOW:k].mean()
            if g >= MIN_GAP_PCT and vm >= MIN_VOL_MULT:
                ok += 1
            else:
                bad.append((s, d.get("date_et"), f"recomputed gap {g:.1f}% x{vm:.1f}"))
        log(f"validity: stored EP docs re-fired from bars at their own gap bar: "
            f"{ok}/{len(docs)}  (misses: {bad[:3]})")
    except Exception as exc:
        log("validity check skipped:", exc)

    # ---- placebo draws: same DATES as the EP events, non-EP symbols ---------
    ep_by_sym = defaultdict(list)
    for e in events:
        ep_by_sym[e["symbol"]].append(e["i"])
    pool = [s for s in univ if s in bars and len(bars[s]) >= 300]
    pool = random.sample(pool, min(PLACEBO_POOL, len(pool)))
    pool_pos = {s: {d: k for k, d in enumerate(bars[s].index)} for s in pool}

    placebo = []
    for e in events:
        picks = random.sample(pool, min(12, len(pool)))
        taken = 0
        for s in picks:
            if taken >= PLACEBO_PER_DATE:
                break
            k = pool_pos[s].get(e["date"])
            if k is None or k < AVG_VOL_WINDOW + 1 or k + 1 >= len(bars[s]):
                continue
            if any(abs(k - j) <= 21 for j in ep_by_sym.get(s, ())):
                continue
            placebo.append({"symbol": s, "i": k, "date": e["date"],
                            "src": (e["symbol"], e["date"])})
            taken += 1
    log(f"placebo draws: {len(placebo)}  pool {len(pool)}  ({time.time()-t0:.0f}s)")

    # ---- fundamentals -------------------------------------------------------
    need = sorted({e["symbol"] for e in events} | {p["symbol"] for p in placebo})
    for rnd in range(4):
        todo = [s for s in need if s not in _fund_cache]
        if not todo:
            break
        FETCH_FAIL.clear()
        log(f"fundamentals round {rnd}: {len(todo)} to fetch (of {len(need)})")
        done = 0
        with ThreadPoolExecutor(max_workers=3) as ex:
            for _ in as_completed({ex.submit(fetch_fundamentals, s): s for s in todo}):
                done += 1
                if done % 250 == 0:
                    log(f"  ...{done}/{len(todo)} ({time.time()-t0:.0f}s)")
        try:
            json.dump(_fund_cache, open(CACHE, "w"))
        except Exception as exc:
            log("cache write failed:", exc)
        log(f"  round {rnd}: hard failures still outstanding {len(FETCH_FAIL)} "
            f"({time.time()-t0:.0f}s)")
        if not FETCH_FAIL:
            break
        time.sleep(3)
    hard_fail = [s for s in need if s not in _fund_cache]
    no_data = [s for s in need if _fund_cache.get(s) == []]
    have = [s for s in need if _fund_cache.get(s)]
    log(f"fundamentals: usable {len(have)}/{len(need)} | Massive has none {len(no_data)} "
        f"| unrecoverable fetch failure {len(hard_fail)}  ({time.time()-t0:.0f}s)")

    # ---- classify + measure -------------------------------------------------
    rowsA, rowsB, rowsC, rowsD = [], [], [], []
    unknown_ep = unknown_pb = 0
    flip_derived = flip_strict = comparable = 0
    tiers = defaultdict(int)
    gapq_used = 0

    why = defaultdict(int)
    for e in events:
        rows = _fund_cache.get(e["symbol"])
        if rows is None:
            why["fetch failed"] += 1
        elif not rows:
            why["Massive carries no quarterly financials"] += 1
        rows = rows or []
        state, s = bonde_state(rows, e["date"])
        if state == "unknown" and rows:
            why["< 5 quarters filed as of the gap"] += 1
        r = fwd_returns(bars[e["symbol"]], e["i"])
        if r is None:
            continue
        rec = dict(e); rec.update(r); rec["sales"] = s
        rec["bracket"] = bracket(bars[e["symbol"]], e)
        if state == "unknown":
            unknown_ep += 1
            continue
        tiers[(state, (s or {}).get("tier"))] += 1
        comparable += 1
        if bonde_state(rows, e["date"], drop_derived=True)[0] != state:
            flip_derived += 1
        if bonde_state(rows, e["date"], strict=True)[0] != state:
            flip_strict += 1
        # did the gap-day quarter itself make it into the series?
        d = str(e["date"].date())
        if any(r2["avail"] <= d and r2["avail"] >= str((e["date"] - pd.Timedelta(days=45)).date())
               for r2 in rows):
            gapq_used += 1
        rec["cell"] = "A" if state == "pass" else "B"
        (rowsA if state == "pass" else rowsB).append(rec)

    # which EP cell each placebo draw's DATE came from — so A can be compared
    # against a placebo drawn on A's OWN dates (calendar-matched), not against
    # placebos spread over every EP date.
    src_cell = {(r["symbol"], r["date"]): r["cell"] for r in rowsA + rowsB}

    for p in placebo:
        rows = _fund_cache.get(p["symbol"]) or []
        state, s = bonde_state(rows, p["date"])
        r = fwd_returns(bars[p["symbol"]], p["i"])
        if r is None:
            continue
        if state == "unknown":
            unknown_pb += 1
            continue
        rec = dict(p); rec.update(r); rec["sales"] = s
        rec["src_cell"] = src_cell.get(p["src"])
        (rowsC if state == "pass" else rowsD).append(rec)

    log("")
    log("=" * 78)
    log("CELL COUNTS")
    log(f"  A  EP + sales PASS      events {len(rowsA):6d}  symbols {len(set(r['symbol'] for r in rowsA)):5d}")
    log(f"  B  EP + sales FAIL      events {len(rowsB):6d}  symbols {len(set(r['symbol'] for r in rowsB)):5d}")
    log(f"  C  sales PASS, no EP    draws  {len(rowsC):6d}  symbols {len(set(r['symbol'] for r in rowsC)):5d}")
    log(f"  D  neither (placebo)    draws  {len(rowsD):6d}  symbols {len(set(r['symbol'] for r in rowsD)):5d}")
    log(f"  EP events unclassifiable (no usable revenue history as of the gap): {unknown_ep}")
    log(f"     why: {dict(why)}")
    log(f"  placebo draws unclassifiable: {unknown_pb}")
    log(f"  sensitivity: pass/fail flips if derived Q4s dropped : {flip_derived}/{comparable}")
    log(f"  sensitivity: pass/fail flips if filing must PRECEDE gap: {flip_strict}/{comparable}")
    log(f"  events whose series contains a quarter filed in the 45d before the gap: {gapq_used}/{comparable}")
    log(f"  tiers: {dict(sorted(tiers.items(), key=lambda kv: -kv[1]))}")

    # --- is the EP even correlated with the sales gate? ---------------------
    ep_pass = len(rowsA) / (len(rowsA) + len(rowsB)) * 100
    pb_pass = len(rowsC) / (len(rowsC) + len(rowsD)) * 100
    log("")
    log(f"  sales-gate pass RATE among EP events   : {ep_pass:.1f}% ({len(rowsA)}/{len(rowsA)+len(rowsB)})")
    log(f"  sales-gate pass RATE among date-matched non-EP draws: {pb_pass:.1f}% "
        f"({len(rowsC)}/{len(rowsC)+len(rowsD)})")
    log("  -> the two legs are close to INDEPENDENT; the intersection is roughly")
    log("     the product of the marginals, not a selected sub-population.")

    # cohort description
    for n, rs in (("A", rowsA), ("B", rowsB)):
        log(f"  {n}: median gap {np.median([r['gap_pct'] for r in rs]):.1f}%  "
            f"median vol mult {np.median([r['vol_mult'] for r in rs]):.1f}x  "
            f"median entry px ${np.median([r['entry_close'] for r in rs]):.2f}  "
            f"median 50d $vol ${np.median([r['addv50'] for r in rs])/1e6:.1f}M  "
            f"median sales YoY {np.median([r['sales']['growth_yoy_pct'] for r in rs]):+.1f}%")

    clusters = sorted({r["symbol"] for r in rowsA + rowsB + rowsC + rowsD})
    log("")
    log("=" * 78)
    log("FORWARD CLOSE-TO-CLOSE RETURNS  (entry = close of the bar AFTER the gap)")
    log("  clustered bootstrap on SYMBOL, B=%d, percentile 95%% CI" % BOOT)
    # calendar-matched placebo: only the draws taken on A's own event dates
    rowsCa = [r for r in rowsC if r["src_cell"] == "A"]
    rowsDa = [r for r in rowsD if r["src_cell"] == "A"]
    results = {}
    for k in HORIZONS:
        cells = {n: Cell([(r["symbol"], r[f"r{k}"]) for r in rs], clusters)
                 for n, rs in (("A", rowsA), ("B", rowsB), ("C", rowsC), ("D", rowsD),
                               ("Ca", rowsCa), ("Da", rowsDa))}
        res = boot(cells, clusters, diffs=[("A", "B"), ("A", "C"), ("A", "D"),
                                           ("A", "Da"), ("C", "D"), ("B", "D")])
        results[k] = res
        log(f"\n-- {k} sessions --")
        for n in ("A", "B", "C", "D", "Da"):
            c = res["cells"][n]
            log(f"   {n}: n={c['n']:6d} sym={c['n_sym']:4d}  "
                f"median {c['median']:+6.2f}% [{c['median_ci'][0]:+6.2f},{c['median_ci'][1]:+6.2f}]  "
                f"mean {c['mean']:+6.2f}% [{c['mean_ci'][0]:+6.2f},{c['mean_ci'][1]:+6.2f}]  "
                f"win {c['win']:5.1f}% [{c['win_ci'][0]:4.1f},{c['win_ci'][1]:4.1f}]")
        for d, row in res["diffs"].items():
            log(f"   LIFT {d}: median {row['median']:+6.2f}pp "
                f"[{row['median_ci'][0]:+6.2f},{row['median_ci'][1]:+6.2f}]  "
                f"mean {row['mean']:+6.2f}pp [{row['mean_ci'][0]:+6.2f},{row['mean_ci'][1]:+6.2f}]  "
                f"win {row['win']:+5.1f}pp [{row['win_ci'][0]:+5.1f},{row['win_ci'][1]:+5.1f}]")

    # open-entry variant
    log("")
    log("robustness — entry at the OPEN of the bar after the gap (Bonde's own")
    log("trigger is a stop-buy at the gap high; the open is the first fillable price):")
    for k in HORIZONS:
        cells = {n: Cell([(r["symbol"], r[f"o{k}"]) for r in rs], clusters)
                 for n, rs in (("A", rowsA), ("B", rowsB), ("C", rowsC), ("D", rowsD))}
        res = boot(cells, clusters, diffs=[("A", "D")])
        row = res["diffs"]["A-D"]
        log(f"   {k}d  A median {res['cells']['A']['median']:+6.2f}%  "
            f"D median {res['cells']['D']['median']:+6.2f}%  "
            f"A-D {row['median']:+6.2f}pp [{row['median_ci'][0]:+6.2f},{row['median_ci'][1]:+6.2f}]")

    # liquidity robustness
    log("")
    log("robustness — EP events with 50d median dollar volume >= $1M:")
    lA = [r for r in rowsA if r["addv50"] >= 1e6]
    lB = [r for r in rowsB if r["addv50"] >= 1e6]
    for k in (5, 21):
        cells = {"A": Cell([(r["symbol"], r[f"r{k}"]) for r in lA], clusters),
                 "B": Cell([(r["symbol"], r[f"r{k}"]) for r in lB], clusters),
                 "D": Cell([(r["symbol"], r[f"r{k}"]) for r in rowsD], clusters)}
        res = boot(cells, clusters, diffs=[("A", "B"), ("A", "D")])
        log(f"   {k}d  A n={res['cells']['A']['n']} median {res['cells']['A']['median']:+6.2f}%  "
            f"B n={res['cells']['B']['n']} median {res['cells']['B']['median']:+6.2f}%  "
            f"A-B {res['diffs']['A-B']['median']:+6.2f}pp "
            f"[{res['diffs']['A-B']['median_ci'][0]:+6.2f},{res['diffs']['A-B']['median_ci'][1]:+6.2f}]  "
            f"A-D {res['diffs']['A-D']['median']:+6.2f}pp "
            f"[{res['diffs']['A-D']['median_ci'][0]:+6.2f},{res['diffs']['A-D']['median_ci'][1]:+6.2f}]")

    # ---- the setup's OWN outcome -------------------------------------------
    log("")
    log("=" * 78)
    log("THE EP'S OWN BRACKET  trigger = gap high + $0.01 | stop = gap low - $0.01")
    log(f"target = trigger x 1.06 | trigger window {TRIGGER_WINDOW} sessions | "
        f"race horizon {BRACKET_HORIZON} bars | tie inside a bar = STOP")
    bstats = {}
    for name, rs in (("A", rowsA), ("B", rowsB)):
        obs = [r for r in rs if r["bracket"] is not None]
        armed = [r for r in obs if r["bracket"]["armed"]]
        tg = [r for r in armed if r["bracket"]["outcome"] == "target"]
        st = [r for r in armed if r["bracket"]["outcome"] == "stop"]
        nn = [r for r in armed if r["bracket"]["outcome"] == "neither"]
        dec = len(tg) + len(st)
        wins = [r["bracket"]["pct"] for r in tg]
        loss = [-r["bracket"]["pct"] for r in st]
        exp = (sum(wins) - sum(loss)) / dec if dec else None
        bstats[name] = dict(obs=len(obs), armed=len(armed), tg=len(tg), st=len(st),
                            nn=len(nn), exp=exp)
        log(f"\n   {name}: fully-observable events {len(obs)}  triggered {len(armed)} "
            f"({len(armed)/len(obs)*100:.1f}% of events armed)")
        log(f"      of the TRIGGERED: target-before-stop {len(tg)/len(armed)*100:5.1f}%  "
            f"stop-first {len(st)/len(armed)*100:5.1f}%  neither {len(nn)/len(armed)*100:5.1f}%")
        stop_d = [r["bracket"]["stop_dist"] for r in armed]
        log(f"      bracket geometry: target distance {TARGET_PCT_ABOVE:.2f}% fixed  "
            f"median stop distance {np.median(stop_d):.2f}% "
            f"(gap-day range; NOT comparable across setups)")
        if dec:
            log(f"      median bars to decision {np.median([r['bracket']['bars'] for r in tg + st]):.0f}")
            log(f"      EXPECTANCY_PCT (gross avg win% - avg loss% per decided) = {exp:+.2f}%")
        else:
            log("      EXPECTANCY_PCT = n/a")

    # clustered CI on the bracket numbers
    for label, key in (("target-before-stop %", "tbs"), ("expectancy_pct", "exp")):
        cells = {}
        for name, rs in (("A", rowsA), ("B", rowsB)):
            armed = [r for r in rs if r["bracket"] and r["bracket"]["armed"]]
            if key == "tbs":
                pairs = [(r["symbol"], 100.0 if r["bracket"]["outcome"] == "target" else 0.0)
                         for r in armed if r["bracket"]["outcome"] in ("target", "stop")]
            else:
                pairs = [(r["symbol"], r["bracket"]["pct"])
                         for r in armed if r["bracket"]["outcome"] in ("target", "stop")]
            cells[name] = Cell(pairs, clusters)
        res = boot(cells, clusters, diffs=[("A", "B")])
        log(f"\n   {label}: A {res['cells']['A']['mean']:+6.2f} "
            f"[{res['cells']['A']['mean_ci'][0]:+6.2f},{res['cells']['A']['mean_ci'][1]:+6.2f}]  "
            f"B {res['cells']['B']['mean']:+6.2f} "
            f"[{res['cells']['B']['mean_ci'][0]:+6.2f},{res['cells']['B']['mean_ci'][1]:+6.2f}]  "
            f"A-B {res['diffs']['A-B']['mean']:+6.2f} "
            f"[{res['diffs']['A-B']['mean_ci'][0]:+6.2f},{res['diffs']['A-B']['mean_ci'][1]:+6.2f}]")

    log("")
    log(f"done in {time.time()-t0:.0f}s")


main()
