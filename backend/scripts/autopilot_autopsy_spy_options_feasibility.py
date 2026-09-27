"""Auto-Pilot autopsy: SPY 0DTE options feasibility numbers (2026-09-27).

THE ASK (Ajay 2026-09-27, verbatim): "We are losing a lot of money in autopilot
reasearch and make to understand the where we are losing money and why and
create a better plan to make money and use our data logic in autopilot please..
not sure whats missing but find ways to make it better. Also try and do SPY
options buying please? in the auto pilot daily, high frequency trades with
monitoring min to min to make sure it sell on time? I would like to execute
atleasst 5 trades if possible on SPY. based on the demand entries with a minimum
of at least one trade based on volatility of the market."

This file backs every number in the SPY-options feasibility memo
(docs/trading/autopilot_spy_options_feasibility_2026_09_27.md). It is READ-ONLY:
it places, cancels and modifies nothing, calls no broker endpoint, and writes
nothing to Mongo (its own pymongo client, `find` only, so no helper's
create_index runs). Part C reads Massive with the options key and prints status
codes and counts only; the key is never printed.

  Part A  the 0DTE paper lane's own journal (Mongo `zero_dte_positions`): fills,
          wins, $ P&L and premium-% expectancy with CIs, split by the dealer
          regime stamped at entry, exits by kind, latency.
  Part B  SPY census on the cached 1-minute tape (`intraday_cache`, RTH only):
          how many Signal Lab composite BUY/SELL tags (the lane's trigger) and
          ORB signals (daytrading.signals.orb, Crabel/Raschke) land inside the
          lane's entry window per session; the UNDERLYING R of each under the
          lane's stock exits (signal stop, signal target, FLATTEN_ET flat) vs a
          same-session random-time placebo with the same side and stop distance;
          session-clustered bootstrap CIs; split by the prior close's VIX regime
          (sepa.iv_read.classify).
  Part C  data availability: Massive options minute aggregates, NBBO quote
          history and expired-contract reference for past SPY 0DTE contracts.
  Part D  how often SPY passes the S/D buy condition (demand_proximity_gate +
          room_gate, the standing alert gate) on daily closes, and on the day's
          low as an upper bound, with the demand engine's geometry.

Underlying R is NOT option P&L: theta, the spread, the premium exits and fills
are not modelled here (Part C says the data to model them now exists).

Every threshold is imported from the module that enforces it; nothing is typed.

Run (read-only, inside the api container, which has the Mongo env and the
options key):
  docker exec -i -w /app cheetah-market-app-api-1 python - < \
      backend/scripts/autopilot_autopsy_spy_options_feasibility.py
  add `--part A,B` etc. after `python -` to run a subset.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
SEED = 20260927
BOOT = 4000
PLACEBO_K = 40
TIME_MATCH_BARS = 15      # study design choice (placebo window), not a trading rule
SYMBOL = "SPY"


# ── read-only Mongo ──────────────────────────────────────────────────────────
def _db():
    from pymongo import MongoClient
    c = MongoClient(os.getenv("MONGO_URL", "mongodb://mongo:27017"), serverSelectionTimeoutMS=3000)
    return c[os.getenv("MONGO_DB", "cheetah")]


# ── statistics ───────────────────────────────────────────────────────────────
def wilson(k: int, n: int, z: float = 1.96) -> tuple:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h), 1), round(100 * (c + h), 1))


def boot_mean(xs, draws: int = BOOT, seed: int = SEED) -> tuple:
    xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    if len(xs) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    a = np.asarray(xs)
    m = rng.choice(a, size=(draws, a.size), replace=True).mean(axis=1)
    return (round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3))


def boot_cluster(groups: dict, draws: int = BOOT, seed: int = SEED) -> tuple:
    """Mean over pooled values, resampling SESSIONS (clusters) with replacement."""
    keys = [k for k, v in groups.items() if v]
    if len(keys) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    sums = np.array([sum(groups[k]) for k in keys], dtype=float)
    cnts = np.array([len(groups[k]) for k in keys], dtype=float)
    idx = rng.integers(0, len(keys), size=(draws, len(keys)))
    m = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return (round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3))


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _iso(v):
    """Broker / lane timestamps (Alpaca stamps carry nanoseconds) -> aware UTC."""
    if not v:
        return None
    s = str(v).replace("Z", "+00:00")
    m = re.match(r"^(.*?\.\d{6})\d*(.*)$", s)
    if m:
        s = m.group(1) + m.group(2)
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


# ── Part A: the 0DTE lane's own journal ──────────────────────────────────────
def part_a() -> dict:
    from trading import zero_dte_lane as ZL
    db = _db()
    docs = list(db[ZL.POSITIONS_COLL].find({}, {"_id": 0}))
    out = {"n_orders": len(docs), "status": dict(Counter(d.get("status") for d in docs))}

    def regime_of(d):
        r = d.get("regime")
        return (r.get("regime") if isinstance(r, dict) else r) or "UNKNOWN"

    out["regime_field_types"] = dict(Counter(type(d.get("regime")).__name__ for d in docs))
    # What contract_for() actually compares against SKIP_REGIMES in production:
    out["skip_check_would_fire"] = sum(
        1 for d in docs if str(d.get("regime") or "").upper() in ZL.SKIP_REGIMES)
    out["entered_while_regime_in_skip_list"] = sum(
        1 for d in docs if str(regime_of(d)).upper() in ZL.SKIP_REGIMES)

    missed = [d for d in docs if d.get("status") == "missed"]
    k_fill = len(docs) - len(missed)
    out["fill_rate_pct"] = round(100 * k_fill / len(docs), 1) if docs else None
    out["fill_rate_ci"] = wilson(k_fill, len(docs))
    by_sym = defaultdict(lambda: [0, 0])
    for d in docs:
        by_sym[d["symbol"]][0] += 1
        by_sym[d["symbol"]][1] += d.get("status") != "missed"
    out["fills_by_symbol"] = {s: {"orders": v[0], "filled": v[1], "ci": wilson(v[1], v[0])}
                              for s, v in sorted(by_sym.items())}

    closed = [d for d in docs if d.get("status") == "closed"]

    def block(rows):
        pnl = [_f(d.get("realized_pnl")) or 0.0 for d in rows]
        ret = [_f(d.get("premium_return_pct")) for d in rows if _f(d.get("premium_return_pct")) is not None]
        wins = sum(p > 0 for p in pnl)
        win_p = [p for p in pnl if p > 0]
        loss_p = [p for p in pnl if p < 0]
        return {"n": len(rows), "wins": wins, "win_rate_pct": round(100 * wins / len(rows), 1) if rows else None,
                "win_rate_ci": wilson(wins, len(rows)),
                "sum_pnl": round(sum(pnl), 2),
                "mean_pnl": round(st.mean(pnl), 2) if pnl else None, "mean_pnl_ci": boot_mean(pnl),
                "avg_win": round(st.mean(win_p), 2) if win_p else None,
                "avg_loss": round(st.mean(loss_p), 2) if loss_p else None,
                "mean_premium_ret_pct": round(st.mean(ret), 1) if ret else None,
                "mean_premium_ret_ci": boot_mean(ret)}

    out["closed_all"] = block(closed)
    out["closed_by_regime"] = {rg: block([d for d in closed if regime_of(d) == rg])
                               for rg in sorted({regime_of(d) for d in closed})}
    out["closed_spy"] = block([d for d in closed if d.get("symbol") == SYMBOL])

    def exit_kind(d):
        r = (d.get("close_reason") or "").lower()
        if r.startswith("flatten"):
            return "clock_flatten"
        if "signal stop" in r:
            return "stock_stop"
        if "target" in r:
            return "stock_target"
        if r.startswith("premium"):
            return "premium_take" if "+" in r.split("(")[0] else "premium_stop"
        return "other"

    out["exits"] = dict(Counter(exit_kind(d) for d in closed))
    out["exits_pnl"] = {k: round(sum(_f(d.get("realized_pnl")) or 0 for d in closed if exit_kind(d) == k), 2)
                        for k in out["exits"]}

    lat = defaultdict(list)
    hold_min = []
    for d in docs:
        for k, v in ZL.latency(d).items():
            if v is not None:
                lat[k].append(v)
    for d in closed:
        a, b = _iso(d.get("fill_ts")), _iso(d.get("closed_ts"))
        if a and b:
            hold_min.append((b - a).total_seconds() / 60.0)
    out["latency_median_sec"] = {k: round(st.median(v), 1) for k, v in lat.items()}
    out["latency_max_sec"] = {k: round(max(v), 1) for k, v in lat.items()}
    out["hold_minutes_median"] = round(st.median(hold_min), 1) if hold_min else None
    # "sell on time": close limit sent -> broker fill. The close is a day LIMIT
    # at the bid that is re-sent only when the broker cancels it, never re-priced.
    close_lat = []
    for d in closed:
        a, b = _iso(d.get("close_sent_ts")), _iso(d.get("closed_ts"))
        if a and b:
            close_lat.append(((b - a).total_seconds(), d.get("symbol"), d.get("day")))
    close_lat.sort()
    out["close_send_to_fill_sec"] = {
        "n": len(close_lat),
        "median": round(st.median([c[0] for c in close_lat]), 1) if close_lat else None,
        "over_60s": [(round(c[0], 1), c[1], c[2]) for c in close_lat if c[0] > 60]}
    ent_et = [t.astimezone(ET).strftime("%H:%M") for t in (_iso(d.get("order_ts")) for d in docs) if t]
    out["entry_time_et_range"] = (min(ent_et), max(ent_et)) if ent_et else None
    out["entry_before_1100_et"] = sum(1 for t in ent_et if t < "11:00")
    out["days"] = len({d.get("day") for d in docs})
    out["entries_per_day_max"] = max(Counter(d.get("day") for d in docs).values()) if docs else 0
    out["lane_caps"] = {"MAX_ENTRIES_PER_DAY": ZL.MAX_ENTRIES_PER_DAY, "MAX_OPEN": ZL.MAX_OPEN,
                        "one_entry_per_name_per_day": True,
                        "ENTRY_OPEN_ET": str(ZL.ENTRY_OPEN_ET), "LAST_ENTRY_ET": str(ZL.LAST_ENTRY_ET),
                        "FLATTEN_ET": str(ZL.FLATTEN_ET), "ENTRY_FILL_WAIT_SEC": ZL.ENTRY_FILL_WAIT_SEC,
                        "PREMIUM_STOP_PCT": ZL.PREMIUM_STOP_PCT, "PREMIUM_TAKE_PCT": ZL.PREMIUM_TAKE_PCT}
    return out


# ── Part B: SPY census on the cached 1-minute tape ───────────────────────────
def _sessions(db, symbol: str) -> list:
    """[(date, rth frame indexed ET tz-aware, raw frame naive-UTC with session)]."""
    out = []
    for doc in db.intraday_cache.find({"symbol": symbol}, {"_id": 0}).sort("date", 1):
        bars = doc.get("bars") or []
        if not bars:
            continue
        df = pd.DataFrame(bars)
        if "ts_utc" not in df.columns:
            continue
        df["ts_utc"] = pd.to_datetime(df["ts_utc"])
        df = df.set_index("ts_utc").sort_index()
        rth = df[df["session"] == "rth"].copy()
        if len(rth) < 300:            # half-days / holes: not a full session
            continue
        et = rth.copy()
        et.index = rth.index.tz_localize("UTC").tz_convert(ET)
        out.append((doc["date"], et, df))
    return out


def _walk(hi, lo, cl, close_t, i0, side, entry, stop, target, flat_t):
    """R of one underlying trade from the close of bar i0. Stop is checked
    before target inside a bar; flat at the close of the last bar that closes
    at or before `flat_t`."""
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    last = None
    for k in range(i0 + 1, len(cl)):
        if close_t[k] > flat_t:
            break
        last = k
        if side == "long":
            if lo[k] <= stop:
                return -1.0, "stop"
            if hi[k] >= target:
                return (target - entry) / risk, "target"
        else:
            if hi[k] >= stop:
                return -1.0, "stop"
            if lo[k] <= target:
                return (entry - target) / risk, "target"
    if last is None:
        return None
    px = cl[last]
    return ((px - entry) if side == "long" else (entry - px)) / risk, "flat"


def _placebo(rng, hi, lo, cl, close_t, win_idx, side, risk_pct, target_r, flat_t):
    vals = []
    for _ in range(PLACEBO_K):
        j = rng.choice(win_idx)
        e = cl[j]
        risk = e * risk_pct
        if side == "long":
            s, t = e - risk, e + target_r * risk
        else:
            s, t = e + risk, e - target_r * risk
        r = _walk(hi, lo, cl, close_t, j, side, e, s, t, flat_t)
        if r is not None:
            vals.append(r[0])
    return st.mean(vals) if vals else None


def _vix_by_session(db) -> dict:
    from sepa import iv_read
    d = db.price_cache.find_one({"symbol": "^VIX"}, {"_id": 0, "bars": 1}) or {}
    rows = sorted(((str(b["date"])[:10], _f(b.get("close"))) for b in d.get("bars") or []), key=lambda r: r[0])
    out, prev = {}, None
    for day, c in rows:
        out[day] = iv_read.classify(prev) if prev is not None else None
        if c is not None:
            prev = c
    return out, rows


def part_b() -> dict:
    from daytrading import signal_lab as SL
    from daytrading.signals import orb as ORB
    from trading import zero_dte_lane as ZL
    db = _db()
    sess = _sessions(db, SYMBOL)
    vix_reg, vix_rows = _vix_by_session(db)
    rng = random.Random(SEED)
    one = timedelta(minutes=1)

    tags_per_session, orb_per_session = [], []
    comp = defaultdict(list)          # session -> [R]
    comp_first = defaultdict(list)    # session -> [R] first tag only (lane: one per name per day)
    comp_diff = defaultdict(list)
    comp_first_diff = defaultdict(list)
    comp_first_tdiff = defaultdict(list)
    comp_first_why = Counter()
    comp_pl = defaultdict(list)
    comp_by_vix = defaultdict(lambda: defaultdict(list))
    comp_why = Counter()
    risk_pcts = []
    orb_r = defaultdict(list)
    orb_diff = defaultdict(list)
    orb_why = Counter()
    orb_risk = []
    orb_by_vix = defaultdict(lambda: defaultdict(list))
    ranges = []

    for day, et, raw in sess:
        hi = et["high"].to_numpy(dtype=float)
        lo = et["low"].to_numpy(dtype=float)
        cl = et["close"].to_numpy(dtype=float)
        stamps = list(et.index)
        close_t = [(s + one).timetz().replace(tzinfo=None) for s in stamps]
        win_idx = [k for k, t in enumerate(close_t) if ZL.ENTRY_OPEN_ET <= t < ZL.LAST_ENTRY_ET]
        if not win_idx:
            continue
        flat_t = ZL.FLATTEN_ET
        ranges.append((hi.max() - lo.min()) / cl[0] * 100.0)
        vreg = vix_reg.get(day) or "unknown"

        evs = SL.events_from_frame(et)
        tags = [e for e in evs if e.get("kind") in ("buy", "sell")
                and ZL.ENTRY_OPEN_ET <= close_t[int(e["i"])] < ZL.LAST_ENTRY_ET]
        tags_per_session.append(len(tags))
        for n, e in enumerate(tags):
            i0 = int(e["i"])
            side = "long" if e["kind"] == "buy" else "short"
            entry, stop, target = float(e["price"]), _f(e.get("stop")), _f(e.get("target"))
            if stop is None or target is None:
                continue
            r = _walk(hi, lo, cl, close_t, i0, side, entry, stop, target, flat_t)
            if r is None:
                continue
            rp = abs(entry - stop) / entry
            risk_pcts.append(rp * 100.0)
            pl = _placebo(rng, hi, lo, cl, close_t, win_idx, side, rp, SL.TARGET_R, flat_t)
            comp[day].append(r[0])
            comp_why[r[1]] += 1
            comp_by_vix[vreg][day].append(r[0])
            if n == 0:
                comp_first[day].append(r[0])
                comp_first_why[r[1]] += 1
                if pl is not None:
                    comp_first_diff[day].append(r[0] - pl)
                # time-matched placebo: a random bar within +-TIME_MATCH_BARS of
                # the tag (the open is more volatile than midday, so a
                # whole-window placebo flatters an early tag)
                near = [k for k in win_idx if k != i0 and abs(k - i0) <= TIME_MATCH_BARS]
                if near:
                    plt = _placebo(rng, hi, lo, cl, close_t, near, side, rp, SL.TARGET_R, flat_t)
                    if plt is not None:
                        comp_first_tdiff[day].append(r[0] - plt)
            if pl is not None:
                comp_pl[day].append(pl)
                comp_diff[day].append(r[0] - pl)

        sigs = ORB.detect(raw[raw["session"].isin(["rth", "premarket"])])
        sigs_in = []
        for s in sigs:
            ts = pd.Timestamp(s["entry_ts"])
            ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
            ts = ts.tz_convert(ET)
            if ts not in et.index:
                continue
            i0 = et.index.get_loc(ts)
            if not (ZL.ENTRY_OPEN_ET <= close_t[i0] < ZL.LAST_ENTRY_ET):
                continue
            sigs_in.append((i0, s))
        orb_per_session.append(len(sigs_in))
        for i0, s in sigs_in:
            side = s["side"]
            entry, stop, target = float(s["entry_price"]), float(s["stop"]), float(s["target"])
            r = _walk(hi, lo, cl, close_t, i0, side, entry, stop, target, flat_t)
            if r is None:
                continue
            rp = abs(entry - stop) / entry
            orb_risk.append(rp * 100.0)
            pl = _placebo(rng, hi, lo, cl, close_t, win_idx, side, rp, float(s["r_multiple_potential"]), flat_t)
            orb_r[day].append(r[0])
            orb_why[r[1]] += 1
            orb_by_vix[vreg][day].append(r[0])
            if pl is not None:
                orb_diff[day].append(r[0] - pl)

    def pooled(g):
        v = [x for xs in g.values() for x in xs]
        return v

    def summ(g, why=None):
        v = pooled(g)
        if not v:
            return {"n": 0}
        return {"n": len(v), "sessions": sum(1 for x in g.values() if x),
                "mean_R": round(st.mean(v), 3), "mean_R_ci_sessions": boot_cluster(g),
                "target_hit_pct": round(100 * (why or {}).get("target", 0) / len(v), 1) if why else None,
                "stop_out_pct": round(100 * (why or {}).get("stop", 0) / len(v), 1) if why else None,
                "stop_out_ci": wilson((why or {}).get("stop", 0), len(v)) if why else None}

    tps = tags_per_session
    out = {
        "sessions": len(tps), "first": sess[0][0] if sess else None, "last": sess[-1][0] if sess else None,
        "composite_tags_per_session": {
            "mean": round(st.mean(tps), 2) if tps else None, "median": st.median(tps) if tps else None,
            "max": max(tps) if tps else None,
            "pct_sessions_ge1": round(100 * sum(t >= 1 for t in tps) / len(tps), 1) if tps else None,
            "pct_sessions_ge5": round(100 * sum(t >= 5 for t in tps) / len(tps), 1) if tps else None,
            "hist": dict(sorted(Counter(tps).items()))},
        "composite_underlying": summ(comp, comp_why),
        "composite_first_tag_only": summ(comp_first, comp_first_why),
        "composite_first_tag_minus_placebo": {
            "mean": round(st.mean(pooled(comp_first_diff)), 3) if pooled(comp_first_diff) else None,
            "ci_sessions": boot_cluster(comp_first_diff)},
        "composite_first_tag_minus_time_matched_placebo": {
            "bars": TIME_MATCH_BARS,
            "mean": round(st.mean(pooled(comp_first_tdiff)), 3) if pooled(comp_first_tdiff) else None,
            "ci_sessions": boot_cluster(comp_first_tdiff)},
        "composite_placebo_mean_R": round(st.mean(pooled(comp_pl)), 3) if pooled(comp_pl) else None,
        "composite_minus_placebo": {"mean": round(st.mean(pooled(comp_diff)), 3) if pooled(comp_diff) else None,
                                    "ci_sessions": boot_cluster(comp_diff)},
        "composite_risk_pct_median": round(st.median(risk_pcts), 3) if risk_pcts else None,
        "composite_by_vix_regime": {k: summ(v) for k, v in sorted(comp_by_vix.items())},
        "orb_signals_per_session": {"mean": round(st.mean(orb_per_session), 2) if orb_per_session else None,
                                    "hist": dict(sorted(Counter(orb_per_session).items()))},
        "orb_underlying": summ(orb_r, orb_why),
        "orb_minus_placebo": {"mean": round(st.mean(pooled(orb_diff)), 3) if pooled(orb_diff) else None,
                              "ci_sessions": boot_cluster(orb_diff)},
        "orb_risk_pct_median": round(st.median(orb_risk), 3) if orb_risk else None,
        "orb_by_vix_regime": {k: summ(v) for k, v in sorted(orb_by_vix.items())},
        "session_range_pct_median": round(st.median(ranges), 3) if ranges else None,
        "vix_regime_days": dict(Counter(vix_reg.get(d) or "unknown" for d, _, _ in sess)),
        "vix_last": vix_rows[-1] if vix_rows else None,
        "lane_window": [str(ZL.ENTRY_OPEN_ET), str(ZL.LAST_ENTRY_ET)], "flatten": str(ZL.FLATTEN_ET),
        "placebo_k": PLACEBO_K, "seed": SEED,
    }
    return out


# ── Part C: is there option price history? ──────────────────────────────────
def part_c() -> dict:
    import requests
    from massive_keys import options_key
    key = options_key()
    if not key:
        return {"error": "no options key in this environment"}

    def hit(path, params):
        p = dict(params)
        p["apiKey"] = key
        try:
            r = requests.get("https://api.massive.com" + path, params=p, timeout=15)
            body = r.json() if r.content else {}
        except Exception as exc:                   # noqa: BLE001 — never echo the URL
            return {"http": None, "error": type(exc).__name__}
        res = body.get("results") or []
        return {"http": r.status_code, "status": body.get("status"), "n": len(res)}

    out = {}
    probes = {
        "minute_bars_0dte_2026_09_25_770C": "/v2/aggs/ticker/O:SPY260925C00770000/range/1/minute/2026-09-25/2026-09-25",
        "minute_bars_0dte_2025_09_10_650C": "/v2/aggs/ticker/O:SPY250910C00650000/range/1/minute/2025-09-10/2025-09-10",
        "minute_bars_0dte_2023_09_11_448C": "/v2/aggs/ticker/O:SPY230911C00448000/range/1/minute/2023-09-11/2023-09-11",
    }
    for k, path in probes.items():
        out[k] = hit(path, {"adjusted": "true", "sort": "asc", "limit": 50000})
    out["nbbo_quote_history_2026_09_25_770C"] = hit(
        "/v3/quotes/O:SPY260925C00770000", {"timestamp.gte": "2026-09-25T14:00:00Z", "limit": 50})
    out["trade_history_2026_09_25_770C"] = hit(
        "/v3/trades/O:SPY260925C00770000", {"timestamp.gte": "2026-09-25T14:00:00Z", "limit": 50})
    out["expired_contract_reference_2026_09_10"] = hit(
        "/v3/reference/options/contracts",
        {"underlying_ticker": SYMBOL, "expiration_date": "2026-09-10", "expired": "true", "limit": 1000})
    # live snapshot freshness labels (what the 0DTE lane's chain row is built from)
    try:
        from options import opex
        contracts, _spot = opex._fetch_contracts(SYMBOL)
        out["snapshot_timeframes"] = {
            "n": len(contracts),
            "last_quote": dict(Counter((c.get("last_quote") or {}).get("timeframe") for c in contracts)),
            "underlying_asset": dict(Counter((c.get("underlying_asset") or {}).get("timeframe") for c in contracts)),
            "expiries": dict(sorted(Counter((c.get("details") or {}).get("expiration_date") for c in contracts).items())),
        }
    except Exception as exc:                       # noqa: BLE001
        out["snapshot_timeframes"] = {"error": type(exc).__name__}
    return out


# ── Part D: SPY vs the standing S/D buy condition ───────────────────────────
def part_d() -> dict:
    from supply_demand import alert_gates as AG
    from supply_demand import demand_reentry, price_zones
    db = _db()
    doc = db.price_cache.find_one({"symbol": SYMBOL}, {"_id": 0, "bars": 1}) or {}
    f = pd.DataFrame(doc.get("bars") or [])
    for c in ("open", "high", "low", "close", "volume"):
        f[c] = pd.to_numeric(f[c], errors="coerce")
    f["d"] = f["date"].astype(str).str[:10]
    f = f.dropna(subset=["open", "high", "low", "close"]).sort_values("d").drop_duplicates("d", keep="last")
    f = f.reset_index(drop=True)
    geom = demand_reentry.zone_geom()
    c = f["close"].to_numpy(dtype=float)
    lo = f["low"].to_numpy(dtype=float)
    n = 0
    res = {"close": Counter(), "low": Counter()}
    rooms = []
    for j in range(253, len(f)):
        n += 1
        prev = float(c[j - 1])
        for basis, px in (("close", float(c[j])), ("low", float(lo[j]))):
            z = price_zones.compute(f.iloc[max(0, j - 252):j], last_price=px, max_zones=None, **geom)
            if not z:
                res[basis]["no_zones"] += 1
                continue
            bands = (z.get("supply_zones") or []) + (z.get("demand_zones") or [])
            near = [b for b in (z.get("demand_zones") or []) if AG.demand_proximity_gate(px, b)]
            ok_room, room = AG.room_gate(px, bands, prev)
            if near:
                res[basis]["near_demand"] += 1
            if ok_room:
                res[basis]["room_ok"] += 1
            if near and ok_room:
                res[basis]["both"] += 1
            if basis == "close" and room and room.get("room_pct_raw") is not None:
                rooms.append(float(room["room_pct_raw"]))
    out = {"sessions": n, "first": f["d"].iloc[253] if len(f) > 253 else None, "last": f["d"].iloc[-1],
           "ALERT_MIN_ROOM_PCT": AG.ALERT_MIN_ROOM_PCT,
           "ALERT_MAX_ABOVE_DEMAND_PCT": AG.ALERT_MAX_ABOVE_DEMAND_PCT, "geometry": geom}
    for basis in ("close", "low"):
        r = res[basis]
        out[basis] = {k: r.get(k, 0) for k in ("near_demand", "room_ok", "both", "no_zones")}
        out[basis]["both_pct"] = round(100 * r.get("both", 0) / n, 1) if n else None
        out[basis]["both_ci"] = wilson(r.get("both", 0), n)
    out["room_pct_raw_median_at_close"] = round(st.median(rooms), 2) if rooms else None
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", default="A,B,C,D")
    ap.add_argument("--json", default=None, help="also write the result JSON here")
    a = ap.parse_args(argv)
    parts = {p.strip().upper() for p in a.part.split(",")}
    out = {"run_at": datetime.now(timezone.utc).isoformat(), "symbol": SYMBOL}
    for p, fn in (("A", part_a), ("B", part_b), ("C", part_c), ("D", part_d)):
        if p in parts:
            print("running part %s ..." % p, file=sys.stderr, flush=True)
            out["part_" + p] = fn()
    txt = json.dumps(out, indent=1, default=str)
    print(txt)
    if a.json:
        with open(a.json, "w") as fh:
            fh.write(txt)


if __name__ == "__main__":
    main()
