"""Last-lid break → prior high: does breaking the LAST supply band carry price to the old high?

Ajay 2026-09-07: "I would like to understand when the last resistance break will
the price go to ATH."

The question, made measurable
-----------------------------
At every anchor (every ANCHOR_STEP_BARS bars, bands recomputed on the bars BEFORE
the anchor only — the quick-bounce study's no-lookahead scheme) take the supply
bands of the demand-board geometry (`demand_reentry.zone_geom`). The **last lid**
is the highest supply band whose top still sits above the anchor close — the last
resistance in the lookback. An **event** is the first close through that lid's
top inside the next window (previous close at or under it). From the break close,
the study asks:

* did the HIGH reach the **prior 52-week high** (max high of the 252 bars before
  the break) within 5 / 10 / 21 / 63 sessions?  `hit_52w_N`
* did it reach the **frame high** (max high of every bar the frame holds before
  the break — the 2-year frame's stand-in for the all-time high; the study says
  "frame high", never "ATH", because the frame is 2 years)?  `hit_frame_N`
* how far did it run: `max_runup_21_pct`, `max_runup_63_pct` (best high vs the
  break close);
* did it **fail**: a close back under the lid top within FAIL_LOOKAHEAD_BARS
  (`failed_21`, `days_to_fail`).

A lid whose top already sits at the 52-week high (within AT_HIGH_TOL) is the
`at_52w` bucket: breaking it IS the new 52-week high, so the 52w question is
moot and only the frame-high / run-up / fail reads apply.

Splits: proven lid (alert_gates.is_proven_band — LID_MIN_TOUCHES / LID_MIN_STRENGTH,
the board's own bar) vs single-touch; volume-confirmed break (volume ≥
VOL_CONFIRM_RATIO × 50-day average, the bar sepa.breakout uses) vs not; distance
from the lid top to the 52-week high at the event (`≤5%`, `5–15%`, `>15%`).

Placebo: for EVERY day (and for every up-day, since a break day is an up-day by
construction) the same "high reaches the prior 52-week high within N sessions"
question, so a break-day rate is always read next to the base rate it must beat.
Persistence: rank names on the first half of their events, judge on the second
(quick_bounce.persistence reused).

Persisted weekly (Sundays 07:30 ET, backend/crontab) to Mongo `lid_break_stats`
— one row per name + `_meta`; the 🚀 Breaking tab prints the pooled read under
its pass line and each card its own count. A STUDY BOARD: nothing here changes
a rule, a gate or a lane. Medians and event-weighted rates only; n is printed
with every rate.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Callable, Iterable, Optional

from supply_demand import alert_gates as AG
from supply_demand import demand_reentry as DR
from supply_demand import price_zones
from supply_demand import quick_bounce as QB

log = logging.getLogger(__name__)

COLL = "lid_break_stats"
META_ID = "_meta"
STUDY_CRON = "30 7 * * 0"          # Sundays 07:30 ET, after quick_bounce (07:00)

ANCHOR_STEP_BARS = QB.ANCHOR_STEP_BARS      # 21 — bands recomputed ~monthly
MIN_HISTORY_BARS = 252                      # a 52-week high needs a year of bars
HORIZONS = (5, 10, 21, 63)
FAIL_LOOKAHEAD_BARS = 21
VOL_CONFIRM_RATIO = 1.5                     # sepa.breakout's volume-confirmed bar
VOL_AVG_BARS = 50
AT_HIGH_TOL = 0.995                         # lid top ≥ 99.5% of the 52w high = "at the high"
DIST_BUCKETS = ((5.0, "≤5%"), (15.0, "5–15%"), (float("inf"), ">15%"))
MIN_EVENTS = 3
DISCLAIMER = ("Breaks of the last supply band, per name, over ~2 years of daily bars with "
              "bands recomputed on prior bars only. Prior high = the 52-week high before the "
              "break; frame high = the highest bar the 2-year frame holds before it (NOT the "
              "all-time high). Read every rate next to its placebo and n. A study board, not a "
              "rule.")


def _f(x) -> Optional[float]:
    return QB._f(x)


# ── pure helpers ─────────────────────────────────────────────────────────────
def last_lid(bands: list, close: float) -> Optional[dict]:
    """The highest VALID supply band whose top sits at or above `close` — the
    last resistance overhead. None when nothing is overhead."""
    over = [b for b in (bands or [])
            if AG._valid_band(b) and str(b.get("kind") or "supply") == "supply"
            and float(b["hi"]) >= close]
    return max(over, key=lambda b: float(b["hi"])) if over else None


def prior_high(highs: list, i: int, bars: int) -> Optional[float]:
    """max high over the `bars` bars BEFORE index i (i itself excluded)."""
    lo = max(0, i - bars)
    xs = [h for h in highs[lo:i] if h is not None]
    return max(xs) if xs else None


def dist_bucket(pct: Optional[float]) -> Optional[str]:
    if pct is None:
        return None
    for lim, label in DIST_BUCKETS:
        if pct <= lim:
            return label
    return None


def reach_within(highs: list, i: int, target: float, n: int) -> Optional[int]:
    """Sessions (1-based) until a high ≥ target inside (i, i+n]; None if not
    reached; -1 when the frame ends before n sessions AND it was not reached."""
    end = min(len(highs), i + n + 1)
    for j in range(i + 1, end):
        h = highs[j]
        if h is not None and h >= target:
            return j - i
    return None if end == i + n + 1 else -1


def outcome(bars: dict, i: int, lid_hi: float, h252: Optional[float],
            hframe: Optional[float]) -> dict:
    highs, closes = bars["high"], bars["close"]
    c0 = closes[i]
    at_52w = h252 is not None and lid_hi >= AT_HIGH_TOL * h252
    out = {"at_52w": bool(at_52w),
           "dist_to_52w_pct": (round((h252 - c0) / c0 * 100.0, 2)
                               if h252 is not None and not at_52w else None)}
    for n in HORIZONS:
        r52 = None if (h252 is None or at_52w) else reach_within(highs, i, h252, n)
        rfr = None if hframe is None else reach_within(highs, i, hframe, n)
        out[f"hit_52w_{n}"] = (None if r52 in (None, -1) and (h252 is None or at_52w or r52 == -1)
                               else bool(r52 is not None and r52 > 0))
        out[f"days_to_52w_{n}"] = r52 if (r52 is not None and r52 > 0) else None
        out[f"hit_frame_{n}"] = (None if rfr == -1 or hframe is None
                                 else bool(rfr is not None and rfr > 0))
        win = [h for h in highs[i + 1:i + n + 1] if h is not None]
        out[f"resolved_{n}"] = bool(len(highs) > i + n)
        out[f"max_runup_{n}_pct"] = (round((max(win) - c0) / c0 * 100.0, 2)
                                     if win and c0 else None)
    fail_day = None
    for j in range(i + 1, min(len(closes), i + FAIL_LOOKAHEAD_BARS + 1)):
        c = closes[j]
        if c is not None and c < lid_hi:
            fail_day = j - i
            break
    out["failed_21"] = (None if len(closes) <= i + 1 else bool(fail_day is not None))
    out["days_to_fail"] = fail_day
    return out


def placebo(bars: dict, start: int, end: int, n: int, up_only: bool = False) -> tuple:
    """(hits, days) over [start, end): from ANY day (or any up-day), does the high
    reach that day's own prior 52-week high within n sessions?"""
    highs, closes = bars["high"], bars["close"]
    hits = days = 0
    for d in range(start, end):
        c, p = closes[d], closes[d - 1] if d > 0 else None
        if c is None or (up_only and (p is None or c <= p)):
            continue
        h252 = prior_high(highs, d, 252)
        if h252 is None or c >= h252:
            continue
        r = reach_within(highs, d, h252, n)
        if r == -1:
            continue                                   # unresolved: neither
        days += 1
        if r is not None:
            hits += 1
    return hits, days


# ── one name ─────────────────────────────────────────────────────────────────
def study_symbol(df, symbol: str = "", min_history: int = MIN_HISTORY_BARS,
                 compute: Optional[Callable] = None):
    """(stats, events) for one name, or None. `compute(frame) -> price_zones payload`
    is injectable for tests."""
    if df is None or len(df) < min_history + 2:
        return None
    df = df.rename(columns={c: str(c).lower() for c in df.columns})
    cols = ("open", "high", "low", "close")
    if any(c not in df.columns for c in cols):
        return None
    bars = {k: [_f(v) for v in df[k].tolist()] for k in cols}
    vols = [_f(v) for v in df["volume"].tolist()] if "volume" in df.columns else [None] * len(df)
    dates = [str(d)[:10] for d in df.index]
    n = len(dates)
    compute = compute or (lambda hist: price_zones.compute(hist, **DR.zone_geom()))
    events, seen = [], set()
    pb = {f"{tag}_{h}": [0, 0] for tag in ("any", "up") for h in (21, 63)}
    anchor = min_history
    while anchor < n - 1:
        hist = df.iloc[:anchor + 1]
        try:
            z = compute(hist)
        except Exception:                       # noqa: BLE001
            z = None
        end = min(n, anchor + ANCHOR_STEP_BARS)
        for h in (21, 63):
            a, d = placebo(bars, anchor + 1, end, h)
            pb[f"any_{h}"][0] += a; pb[f"any_{h}"][1] += d
            u, du = placebo(bars, anchor + 1, end, h, up_only=True)
            pb[f"up_{h}"][0] += u; pb[f"up_{h}"][1] += du
        c_a = bars["close"][anchor]
        lid = last_lid((z or {}).get("supply_zones") or [], c_a) if z and c_a is not None else None
        if lid is not None:
            hi = float(lid["hi"])
            for i in range(anchor + 1, end):
                c, p = bars["close"][i], bars["close"][i - 1]
                if c is None or p is None or not (c > hi and p <= hi):
                    continue
                key = (dates[i], round(hi, 2))
                if key in seen:
                    break
                seen.add(key)
                h252 = prior_high(bars["high"], i, 252)
                hframe = prior_high(bars["high"], i, i)
                avg_v = [v for v in vols[max(0, i - VOL_AVG_BARS):i] if v]
                vr = (vols[i] / (sum(avg_v) / len(avg_v))) if vols[i] and avg_v else None
                ev = {"i": i, "date": dates[i], "lid_lo": float(lid["lo"]), "lid_hi": hi,
                      "touches": int(_f(lid.get("touches")) or 0),
                      "strength": _f(lid.get("strength")),
                      "proven": bool(AG.is_proven_band(lid)),
                      "break_close": c, "break_pct": round((c - hi) / hi * 100.0, 2),
                      "gap_pct": (round((bars["open"][i] - p) / p * 100.0, 2)
                                  if bars["open"][i] is not None else None),
                      "vol_ratio": round(vr, 2) if vr is not None else None,
                      "vol_confirmed": bool(vr is not None and vr >= VOL_CONFIRM_RATIO),
                      "high_252": h252, "high_frame": hframe,
                      **outcome(bars, i, hi, h252, hframe)}
                ev["dist_bucket"] = dist_bucket(ev["dist_to_52w_pct"])
                events.append(ev)
                break                                   # one break per lid per window
        anchor += ANCHOR_STEP_BARS
    events.sort(key=lambda e: e["i"])
    stats = summarize(symbol, events, pb, last_close=bars["close"][-1] if n else None)
    return stats, events


def _rate(evs: list, key: str) -> tuple:
    """(pct, n) over events where the outcome is known (True/False)."""
    known = [e[key] for e in evs if e.get(key) is not None]
    return (round(100.0 * sum(1 for k in known if k) / len(known), 1) if known else None,
            len(known))


def _median(xs: list) -> Optional[float]:
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def summarize(symbol: str, events: list, pb: dict, last_close: Optional[float] = None) -> dict:
    n = len(events)
    out = {"symbol": symbol, "events": n,
           "proven": sum(1 for e in events if e["proven"]),
           "at_52w": sum(1 for e in events if e["at_52w"]),
           "vol_confirmed": sum(1 for e in events if e["vol_confirmed"]),
           "last_close": last_close,
           "last_event_date": max((e["date"] for e in events), default=None)}
    for h in HORIZONS:
        out[f"hit_52w_{h}_pct"], out[f"hit_52w_{h}_n"] = _rate(events, f"hit_52w_{h}")
        out[f"hit_frame_{h}_pct"], out[f"hit_frame_{h}_n"] = _rate(events, f"hit_frame_{h}")
    out["failed_21_pct"], out["failed_21_n"] = _rate(events, "failed_21")
    out["median_days_to_52w_63"] = _median([e.get("days_to_52w_63") for e in events])
    out["median_runup_21_pct"] = _median([e.get("max_runup_21_pct") for e in events])
    out["median_runup_63_pct"] = _median([e.get("max_runup_63_pct") for e in events])
    for k, (hits, days) in pb.items():
        out[f"placebo_{k}_pct"] = round(100.0 * hits / days, 1) if days else None
        out[f"placebo_{k}_n"] = days
    out["events_detail"] = [{k: e.get(k) for k in (
        "date", "lid_lo", "lid_hi", "touches", "proven", "break_pct", "vol_ratio", "vol_confirmed",
        "at_52w", "dist_to_52w_pct", "dist_bucket", "hit_52w_21", "hit_52w_63", "days_to_52w_63",
        "hit_frame_21", "hit_frame_63", "max_runup_21_pct", "max_runup_63_pct", "failed_21",
        "days_to_fail")} for e in events[-12:]]
    return out


# ── the run ──────────────────────────────────────────────────────────────────
def _pooled(evs: list) -> dict:
    d = {"events": len(evs)}
    for h in HORIZONS:
        d[f"hit_52w_{h}_pct"], d[f"hit_52w_{h}_n"] = _rate(evs, f"hit_52w_{h}")
        d[f"hit_frame_{h}_pct"], d[f"hit_frame_{h}_n"] = _rate(evs, f"hit_frame_{h}")
    d["failed_21_pct"], d["failed_21_n"] = _rate(evs, "failed_21")
    d["median_days_to_52w_63"] = _median([e.get("days_to_52w_63") for e in evs])
    d["median_runup_21_pct"] = _median([e.get("max_runup_21_pct") for e in evs])
    d["median_runup_63_pct"] = _median([e.get("max_runup_63_pct") for e in evs])
    return d


def run(symbols: Iterable[str], load=None, compute: Optional[Callable] = None,
        progress: Optional[Callable] = None) -> dict:
    """Study every name; {rows, meta}. `load(symbol) -> frame` injectable."""
    if load is None:
        from sepa import prices

        def load(sym):
            return prices.load_prices(sym, period="2y")
    t0 = time.time()
    rows, per_events, all_events, skipped, failed = [], {}, [], 0, 0
    pb = {f"{tag}_{h}": [0, 0] for tag in ("any", "up") for h in (21, 63)}
    syms = [str(s).upper() for s in symbols]
    for k, sym in enumerate(syms, start=1):
        try:
            df = load(sym)
        except Exception:                       # noqa: BLE001
            df = None
        if df is None or len(df) < MIN_HISTORY_BARS + 2:
            skipped += 1
            continue
        try:
            rec = study_symbol(df, sym, compute=compute)
        except Exception as exc:                # noqa: BLE001
            log.debug("lid_break: %s failed: %s", sym, exc)
            failed += 1
            continue
        if rec is None:
            skipped += 1
            continue
        stats, events = rec
        for key in pb:
            pb[key][0] += (stats.get(f"placebo_{key}_pct") or 0) / 100.0 * (stats.get(f"placebo_{key}_n") or 0)
            pb[key][1] += stats.get(f"placebo_{key}_n") or 0
        rows.append(stats)
        if events:
            per_events[sym] = events
            all_events.extend(events)
        if progress and k % 100 == 0:
            progress(k, len(syms))
    splits = {
        "proven": _pooled([e for e in all_events if e["proven"]]),
        "single_touch": _pooled([e for e in all_events if not e["proven"]]),
        "vol_confirmed": _pooled([e for e in all_events if e["vol_confirmed"]]),
        "vol_light": _pooled([e for e in all_events if not e["vol_confirmed"]]),
        "at_52w": _pooled([e for e in all_events if e["at_52w"]]),
        "below_52w": _pooled([e for e in all_events if not e["at_52w"]]),
    }
    for _, label in DIST_BUCKETS:
        splits[f"dist_{label}"] = _pooled([e for e in all_events if e.get("dist_bucket") == label])
    # persistence: quick_bounce's ranker judges "quick" — map hit_52w_21 onto it
    mapped = {s: [dict(e, outcome="quick" if e.get("hit_52w_21") else "miss")
                  for e in evs if e.get("hit_52w_21") is not None]
              for s, evs in per_events.items()}
    meta = {"_id": META_ID, "generated_at": time.time(),
            "as_of": datetime.now().date().isoformat(),
            "universe": len(syms), "studied": len(rows), "skipped": skipped, "failed": failed,
            "names_with_events": len(per_events),
            "pooled": _pooled(all_events),
            "splits": splits,
            "placebo": {k: {"pct": round(100.0 * v[0] / v[1], 1) if v[1] else None, "n": int(v[1])}
                        for k, v in pb.items()},
            "persistence": QB.persistence({s: v for s, v in mapped.items() if v}),
            "params": {"anchor_step_bars": ANCHOR_STEP_BARS, "min_history_bars": MIN_HISTORY_BARS,
                       "horizons": list(HORIZONS), "fail_lookahead_bars": FAIL_LOOKAHEAD_BARS,
                       "vol_confirm_ratio": VOL_CONFIRM_RATIO, "at_high_tol": AT_HIGH_TOL,
                       "lid_min_touches": AG.LID_MIN_TOUCHES, "lid_min_strength": AG.LID_MIN_STRENGTH,
                       "geometry": DR.zone_geom()},
            "seconds": round(time.time() - t0, 1), "disclaimer": DISCLAIMER}
    return {"rows": rows, "meta": meta}


# ── persistence ──────────────────────────────────────────────────────────────
def _coll(coll=None):
    if coll is not None:
        return coll
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[COLL] if db is not None else None
    except Exception as exc:                    # noqa: BLE001
        log.warning("lid_break: no mongo: %s", exc)
        return None


def save(result: dict, coll=None) -> int:
    coll = _coll(coll)
    if coll is None:
        return 0
    n = 0
    for r in result.get("rows") or []:
        coll.replace_one({"_id": r["symbol"]},
                         dict(r, _id=r["symbol"], generated_at=result["meta"]["generated_at"]),
                         upsert=True)
        n += 1
    coll.replace_one({"_id": META_ID}, dict(result["meta"]), upsert=True)
    return n


def load_stats(symbols: Optional[Iterable[str]] = None, coll=None) -> dict:
    coll = _coll(coll)
    if coll is None:
        return {}
    q: dict = {"_id": {"$ne": META_ID}}
    if symbols is not None:
        q["_id"] = {"$in": [str(s).upper() for s in symbols]}
    try:
        return {d["_id"]: d for d in coll.find(q)}
    except Exception as exc:                    # noqa: BLE001
        log.warning("lid_break: load failed: %s", exc)
        return {}


def load_meta(coll=None) -> Optional[dict]:
    coll = _coll(coll)
    if coll is None:
        return None
    try:
        return coll.find_one({"_id": META_ID})
    except Exception:                           # noqa: BLE001
        return None


# ── board surface ────────────────────────────────────────────────────────────
def board_meta(meta: Optional[dict] = None) -> Optional[dict]:
    """The slim block the 🚀 Breaking tab prints under its pass line."""
    m = meta if meta is not None else load_meta()
    if not isinstance(m, dict):
        return None
    pooled, pb, sp = m.get("pooled") or {}, m.get("placebo") or {}, m.get("splits") or {}
    return {"as_of": m.get("as_of"), "events": pooled.get("events"),
            "names": m.get("names_with_events"), "universe": m.get("universe"),
            "hit_52w_21_pct": pooled.get("hit_52w_21_pct"), "hit_52w_21_n": pooled.get("hit_52w_21_n"),
            "hit_52w_63_pct": pooled.get("hit_52w_63_pct"), "hit_52w_63_n": pooled.get("hit_52w_63_n"),
            "placebo_any_21_pct": (pb.get("any_21") or {}).get("pct"),
            "placebo_up_21_pct": (pb.get("up_21") or {}).get("pct"),
            "placebo_any_63_pct": (pb.get("any_63") or {}).get("pct"),
            "placebo_up_63_pct": (pb.get("up_63") or {}).get("pct"),
            "failed_21_pct": pooled.get("failed_21_pct"),
            "median_days_to_52w_63": pooled.get("median_days_to_52w_63"),
            "median_runup_21_pct": pooled.get("median_runup_21_pct"),
            "median_runup_63_pct": pooled.get("median_runup_63_pct"),
            "proven_hit_52w_21_pct": (sp.get("proven") or {}).get("hit_52w_21_pct"),
            "proven_n": (sp.get("proven") or {}).get("hit_52w_21_n"),
            "single_hit_52w_21_pct": (sp.get("single_touch") or {}).get("hit_52w_21_pct"),
            "single_n": (sp.get("single_touch") or {}).get("hit_52w_21_n"),
            "volc_hit_52w_21_pct": (sp.get("vol_confirmed") or {}).get("hit_52w_21_pct"),
            "volc_n": (sp.get("vol_confirmed") or {}).get("hit_52w_21_n"),
            "dist": {label: {"pct": (sp.get(f"dist_{label}") or {}).get("hit_52w_21_pct"),
                             "n": (sp.get(f"dist_{label}") or {}).get("hit_52w_21_n")}
                     for _, label in DIST_BUCKETS},
            "persistence": m.get("persistence"), "disclaimer": DISCLAIMER}


def card_stat(stats: Optional[dict]) -> Optional[str]:
    """One stats-row value for a Breaking card: 'n breaks · x% → 52w in 21d · y% failed'."""
    if not isinstance(stats, dict) or not stats.get("events"):
        return None
    n = int(stats["events"])
    parts = [f"{n} break{'s' if n != 1 else ''}"]
    if stats.get("hit_52w_21_pct") is not None and (stats.get("hit_52w_21_n") or 0) >= 1:
        parts.append(f"{stats['hit_52w_21_pct']:.0f}% → 52w in 21d (n={stats['hit_52w_21_n']})")
    if stats.get("failed_21_pct") is not None:
        parts.append(f"{stats['failed_21_pct']:.0f}% back under in 21d")
    return " · ".join(parts)


if __name__ == "__main__":
    import json
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from sepa.universe import load_universe
    syms = sys.argv[1].split(",") if len(sys.argv) > 1 else load_universe("full")
    res = run(syms, progress=lambda k, n: log.info("lid_break: %d/%d", k, n))
    saved = save(res)
    m = res["meta"]
    log.info("LID-BREAK STUDY — %d studied · %d events in %d names · 52w hit 21d %s%% (placebo any %s%% / up %s%%) "
             "· failed 21d %s%% · saved=%d · %.1fs",
             m["studied"], m["pooled"]["events"], m["names_with_events"],
             m["pooled"].get("hit_52w_21_pct"), (m["placebo"].get("any_21") or {}).get("pct"),
             (m["placebo"].get("up_21") or {}).get("pct"), m["pooled"].get("failed_21_pct"),
             saved, m["seconds"])
    print(json.dumps(board_meta(m), default=str)[:1500])
