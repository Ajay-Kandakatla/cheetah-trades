"""Quick Bounce — which names turn at a demand band THE SAME DAY (or gap up
the next morning), measured across the universe, and the live list of those
names sitting at / just above a demand band with room overhead.

Ajay 2026-09-06: "Can you create a 'quick bounce potential' list? With the
data we have.. Look at the ones historically across our universe and create
a list that satisfy this criteria.. These stocks the expectation is they
touched the demand zone and bounced in the same day. Like NTAP, KLAC ... I
want this list in one place under chartmaps.. Sort them by nearest of the
Demand zones again with 5% supply zone. First you do the data analysis and
get all the stocks that had same day bounce or sometimes overnight down and
gapped up on the morning."

House Supply & Demand study, NO book, no Minervini cites
(feedback_sepa_book_scope). Decision support, not advice.

THE EVENT (daily closed bars, zones recomputed at anchors every
ANCHOR_STEP_BARS using only bars up to the anchor — the sd_bounce.py
discipline, so a band never sees the bars it is judged on):

  touch day   the day's low reaches a PROVEN demand band (touches >=
              alert_gates.LID_MIN_TOUCHES, strength >= LID_MIN_STRENGTH):
              low <= hi x (1 + TOUCH_TOL_PCT) and low >= lo x (1 - WICK_PCT)
              — zone_bounce_alerts' own touch geometry.
  episode     consecutive touch days of the same band (a gap of one non-touch
              day still joins) — ONE event per visit, so a name that sits in
              a band for a week is counted once, not five times.
  same_day    on a touch day the close lifts >= max(BOUNCE_MIN_PCT, ATR14)
              off the day's low — zone_bounce_alerts' floor (NTAP 09-03).
  gap_up      the next session OPENS >= GAP_MIN_PCT above the touch day's
              close (KLAC 09-04: closed inside the band, opened +2.9%).
  quick       same_day or gap_up on one of the first QUICK_MAX_TOUCH_DAYS
              touch days of the episode. `first_day_quick` = on day one.
  slow        no quick turn, but a close >= SLOW_BOUNCE_PCT above the last
              touch day's close inside SLOW_LOOKAHEAD_BARS without first
              closing BREAK_BUFFER_PCT under the floor (sd_bounce's rule).
  failed      closed under the floor first / nothing inside the window.

PLACEBO — the same "quick day" test on EVERY day of the same windows
(close lifts >= the floor off the low, or the next open gaps >= GAP_MIN_PCT):
a name's quick rate at demand only means something against how often it
does that anyway.

PERSISTENCE — rank names by first-half quick rate, measure the second half
(sd_bounce.persistence's question). The 2026-08-14 study found NO per-name
persistence for 5-bar bounces; this module re-asks it for same-day turns
and reports the answer next to the list rather than hiding it.

THE LIST (`live_rows`) — names whose stats qualify (MIN_EVENTS, MIN_QUICK_RATE)
that are INSIDE a proven demand band or at most NEAR_MAX_PCT above its top
on the live print (a name UNDER every band fell through — not a bounce
candidate), with >= the room floor to the first proven lid overhead
(alert_gates.room_gate, the phone's rule). Sorted nearest-first, room as
the tie-break. Stats live in Mongo `quick_bounce_stats` (one doc per symbol
+ `_meta`), rebuilt by the weekly cron (`python -m supply_demand.quick_bounce`).

Owner settings below are BUILDER DEFAULTS flagged for Ajay unless his words
set them (the touch geometry and bounce floor are his 🪃 rule's; 5% room
and 1%/proximity are his alert rule's).
"""
from __future__ import annotations

import logging
import math
import time
from datetime import date, datetime
from typing import Callable, Iterable, Optional

from . import alert_gates as AG
from . import price_zones
from . import demand_reentry as DR
from .zone_bounce_alerts import BOUNCE_MIN_PCT, TOUCH_TOL_PCT, WICK_PCT

log = logging.getLogger("supply_demand.quick_bounce")

COLL = "quick_bounce_stats"
META_ID = "_meta"
STUDY_CRON = "0 7 * * 0"          # Sundays 07:00 ET (backend/crontab, pinned by a test)

# ── study geometry ───────────────────────────────────────────────────────────
ANCHOR_STEP_BARS = 21          # zones recomputed ~monthly (sd_bounce)
MIN_HISTORY_BARS = 150         # warm-up before the first anchor (sd_bounce used 300; 150 keeps ~17 months of events on a 2-year frame — builder default)
GAP_MIN_PCT = 2.0              # "gapped up in the morning": next open >= +2% (builder default)
QUICK_MAX_TOUCH_DAYS = 3       # quick = on one of the first 3 touch days (KLAC: day 3) (builder default)
EPISODE_JOIN_GAP = 1           # one non-touch day inside an episode still joins it
SLOW_LOOKAHEAD_BARS = 5        # sd_bounce's "within a week"
SLOW_BOUNCE_PCT = 2.0          # sd_bounce's real turn
BREAK_BUFFER_PCT = 1.0         # sd_bounce's failed-zone line
# ── list membership (builder defaults, flagged) ─────────────────────────────
MIN_EVENTS = 3                 # below this a rate is noise
MIN_QUICK_RATE_PCT = 50.0      # at least half of its visits turned quickly
NEAR_MAX_PCT = 5.0             # list names inside a band or <= 5% above its top
ROOM_MIN_PCT = AG.ALERT_MIN_ROOM_PCT      # his "5% to supply"
STOP_BUFFER_PCT = AG.STOP_BUFFER_PCT      # the paper lane's stop under the floor
DISCLAIMER = ("Same-day turns at demand bands, per name, over ~2 years of daily bars. "
              "A fast turn is consistent with resting bids but does not prove them; the "
              "per-name ranking is checked for persistence and the answer is shown. Past "
              "behaviour of a level is not a forecast. Not advice.")


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ── pure: bars → events ──────────────────────────────────────────────────────

def atr_series(highs: list, lows: list, closes: list, period: int = 14) -> list:
    """Simple 14-bar mean of true range, per bar, using ONLY bars up to and
    including that bar (None until `period` bars exist). Same math as
    supply_demand.patterns.atr, made a series so an event never reads a
    volatility computed from its own future."""
    n = len(closes)
    tr = []
    for i in range(n):
        h, l, c = highs[i], lows[i], closes[i]
        if i == 0:
            tr.append(h - l)
        else:
            p = closes[i - 1]
            tr.append(max(h - l, abs(h - p), abs(l - p)))
    out = [None] * n
    run = 0.0
    for i in range(n):
        run += tr[i]
        if i >= period:
            run -= tr[i - period]
        if i >= period - 1:
            out[i] = run / period
    return out


def lift_floor_pct(low: float, atr: Optional[float]) -> float:
    """max(BOUNCE_MIN_PCT, ATR as % of the low) — zone_bounce_alerts' floor."""
    if low is None or low <= 0:
        return BOUNCE_MIN_PCT
    a = (atr / low * 100.0) if atr else 0.0
    return max(BOUNCE_MIN_PCT, a)


def is_touch(low: float, band: dict) -> bool:
    lo, hi = float(band["lo"]), float(band["hi"])
    return low <= hi * (1.0 + TOUCH_TOL_PCT / 100.0) and low >= lo * (1.0 - WICK_PCT / 100.0)


def quick_day(bars: dict, i: int, atr: Optional[float]) -> Optional[str]:
    """'same_day' when bar i's close lifts >= the floor off its low; 'gap_up'
    when bar i+1 opens >= GAP_MIN_PCT above bar i's close; else None."""
    low, close = bars["low"][i], bars["close"][i]
    if low is None or low <= 0 or close is None:
        return None
    lift = (close / low - 1.0) * 100.0
    if lift >= lift_floor_pct(low, atr):
        return "same_day"
    if i + 1 < len(bars["open"]):
        nxt = bars["open"][i + 1]
        if nxt is not None and nxt >= close * (1.0 + GAP_MIN_PCT / 100.0):
            return "gap_up"
    return None


def slow_outcome(closes: list, entry_i: int, band_lo: float) -> dict:
    """sd_bounce.bounce_outcome's rule from the LAST touch day: a close >=
    SLOW_BOUNCE_PCT above it inside SLOW_LOOKAHEAD_BARS before a close
    BREAK_BUFFER_PCT under the floor."""
    out = {"bounced": False, "bars_to_bounce": None, "broke": False}
    n = len(closes)
    if entry_i < 0 or entry_i >= n - 1 or not band_lo:
        return out
    entry = closes[entry_i]
    floor_ = band_lo * (1.0 - BREAK_BUFFER_PCT / 100.0)
    for k in range(1, SLOW_LOOKAHEAD_BARS + 1):
        j = entry_i + k
        if j >= n:
            break
        c = closes[j]
        if c < floor_:
            out["broke"] = True
            return out
        if (c / entry - 1.0) * 100.0 >= SLOW_BOUNCE_PCT:
            out.update({"bounced": True, "bars_to_bounce": k})
            return out
    return out


def episodes_for_band(bars: dict, atrs: list, band: dict, start: int, end: int,
                      dates: list) -> list:
    """Touch episodes of ONE band inside bars [start, end). An episode is the
    run of touch days (gaps <= EPISODE_JOIN_GAP join). Returns one event dict
    per episode with the outcome class."""
    lows, closes = bars["low"], bars["close"]
    events, i = [], start
    while i < end:
        if lows[i] is None or not is_touch(lows[i], band):
            i += 1
            continue
        touch_days = [i]
        j = i + 1
        gap = 0
        while j < end:
            if lows[j] is not None and is_touch(lows[j], band):
                touch_days.append(j)
                gap = 0
            else:
                gap += 1
                if gap > EPISODE_JOIN_GAP:
                    break
            j += 1
        outcome, day_k, kind = None, None, None
        for k, d in enumerate(touch_days[:QUICK_MAX_TOUCH_DAYS], start=1):
            kind = quick_day(bars, d, atrs[d])
            if kind:
                outcome, day_k = "quick", k
                break
        ev = {"i": touch_days[0], "date": dates[touch_days[0]],
              "band_lo": float(band["lo"]), "band_hi": float(band["hi"]),
              "touches": int(band.get("touches") or 0),
              "touch_days": len(touch_days), "outcome": outcome, "kind": kind,
              "quick_day": day_k, "first_day_quick": bool(outcome == "quick" and day_k == 1),
              "lift_pct": None, "bars_to_bounce": None}
        if outcome == "quick":
            d = touch_days[day_k - 1]
            ev["lift_pct"] = round((closes[d] / lows[d] - 1.0) * 100.0, 2)
            if kind == "gap_up" and d + 1 < len(bars["open"]):
                ev["gap_pct"] = round((bars["open"][d + 1] / closes[d] - 1.0) * 100.0, 2)
        else:
            so = slow_outcome(closes, touch_days[-1], float(band["lo"]))
            ev["outcome"] = "slow" if so["bounced"] else "failed"
            ev["bars_to_bounce"] = so["bars_to_bounce"]
            ev["broke"] = so["broke"]
        events.append(ev)
        i = touch_days[-1] + 1
    return events


def placebo_days(bars: dict, atrs: list, start: int, end: int) -> tuple:
    """(quick_days, days) over [start, end): how often ANY day passes the
    quick-day test — the base rate a touch-day rate is judged against."""
    q = n = 0
    for i in range(start, end):
        if bars["low"][i] is None:
            continue
        n += 1
        if quick_day(bars, i, atrs[i]):
            q += 1
    return q, n


def study_symbol(df, symbol: str = "", min_history: int = MIN_HISTORY_BARS,
                 compute: Optional[Callable] = None) -> Optional[dict]:
    """Quick-bounce statistics for one name over its history. `compute`
    (frame -> price_zones payload) is injectable for tests."""
    if df is None or len(df) < min_history + 2:
        return None
    df = df.rename(columns={c: str(c).lower() for c in df.columns})
    bars = {k: [_f(v) for v in df[k].tolist()] for k in ("open", "high", "low", "close")}
    dates = [str(d)[:10] for d in df.index]
    n = len(dates)
    atrs = atr_series([h or 0.0 for h in bars["high"]], [l or 0.0 for l in bars["low"]],
                      [c or 0.0 for c in bars["close"]])
    compute = compute or (lambda hist: price_zones.compute(hist, **DR.zone_geom()))
    events, pq, pn = [], 0, 0
    anchor = min_history
    seen = set()
    while anchor < n - 1:
        hist = df.iloc[:anchor + 1]
        try:
            z = compute(hist)
        except Exception:                       # noqa: BLE001
            z = None
        end = min(n, anchor + ANCHOR_STEP_BARS)
        q, m = placebo_days(bars, atrs, anchor + 1, end)
        pq, pn = pq + q, pn + m
        if z:
            bands = [b for b in (z.get("demand_zones") or [])
                     if AG._valid_band(b) and AG.is_proven_band(b)]
            for b in bands:
                for ev in episodes_for_band(bars, atrs, b, anchor + 1, end, dates):
                    key = (ev["date"], round(ev["band_lo"], 2))
                    if key in seen:
                        continue
                    seen.add(key)
                    events.append(ev)
        anchor += ANCHOR_STEP_BARS
    events.sort(key=lambda e: e["i"])
    return summarize(symbol, events, pq, pn, last_close=bars["close"][-1] if n else None)


def summarize(symbol: str, events: list, placebo_quick: int, placebo_days_n: int,
              last_close: Optional[float] = None) -> dict:
    quick = [e for e in events if e["outcome"] == "quick"]
    same = [e for e in quick if e["kind"] == "same_day"]
    gaps = [e for e in quick if e["kind"] == "gap_up"]
    first = [e for e in quick if e.get("first_day_quick")]
    slow = [e for e in events if e["outcome"] == "slow"]
    failed = [e for e in events if e["outcome"] == "failed"]
    lifts = sorted(e["lift_pct"] for e in quick if e.get("lift_pct") is not None)
    n = len(events)
    rate = round(100.0 * len(quick) / n, 1) if n else None
    base = round(100.0 * placebo_quick / placebo_days_n, 1) if placebo_days_n else None
    return {"symbol": symbol, "events": n, "quick": len(quick), "same_day": len(same),
            "gap_up": len(gaps), "first_day_quick": len(first), "slow": len(slow),
            "failed": len(failed),
            "quick_rate_pct": rate,
            "first_day_rate_pct": round(100.0 * len(first) / n, 1) if n else None,
            "placebo_rate_pct": base,
            "edge_pts": round(rate - base, 1) if rate is not None and base is not None else None,
            "median_lift_pct": lifts[len(lifts) // 2] if lifts else None,
            "last_quick_date": max((e["date"] for e in quick), default=None),
            "last_event_date": max((e["date"] for e in events), default=None),
            "last_close": last_close,
            "events_detail": [{k: e.get(k) for k in ("date", "band_lo", "band_hi", "touches",
                                                     "touch_days", "outcome", "kind", "quick_day",
                                                     "lift_pct", "gap_pct", "bars_to_bounce")}
                              for e in events[-12:]]}


def qualifies(stats: Optional[dict], min_events: int = MIN_EVENTS,
              min_rate: float = MIN_QUICK_RATE_PCT) -> bool:
    if not isinstance(stats, dict):
        return False
    n, rate = stats.get("events") or 0, stats.get("quick_rate_pct")
    return bool(n >= min_events and rate is not None and rate >= min_rate)


# ── persistence (first half ranks, second half judges) ──────────────────────

def _rank_corr(xs: list, ys: list) -> Optional[float]:
    n = len(xs)
    if n < 5:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return round(num / den, 3) if den else None


def persistence(per_symbol_events: dict, min_each_half: int = 2) -> dict:
    """{split_date, names, top_q_second_half_pct, bottom_q_second_half_pct,
    gap_pts, rank_corr}. Rank on first-half quick rate, judge on the second."""
    all_dates = sorted(e["date"] for evs in per_symbol_events.values() for e in evs)
    if len(all_dates) < 20:
        return {"names": 0, "note": "too few events"}
    split = all_dates[len(all_dates) // 2]
    rows = []
    for sym, evs in per_symbol_events.items():
        a = [e for e in evs if e["date"] < split]
        b = [e for e in evs if e["date"] >= split]
        if len(a) < min_each_half or len(b) < min_each_half:
            continue
        ra = 100.0 * sum(1 for e in a if e["outcome"] == "quick") / len(a)
        rb = 100.0 * sum(1 for e in b if e["outcome"] == "quick") / len(b)
        rows.append((sym, ra, rb))
    if len(rows) < 8:
        return {"split_date": split, "names": len(rows), "note": "too few names with events in both halves"}
    rows.sort(key=lambda r: -r[1])
    q = max(1, len(rows) // 4)
    top = rows[:q]
    bot = rows[-q:]
    top_b = sum(r[2] for r in top) / len(top)
    bot_b = sum(r[2] for r in bot) / len(bot)
    return {"split_date": split, "names": len(rows), "quartile": q,
            "top_q_first_half_pct": round(sum(r[1] for r in top) / len(top), 1),
            "top_q_second_half_pct": round(top_b, 1),
            "bottom_q_second_half_pct": round(bot_b, 1),
            "gap_pts": round(top_b - bot_b, 1),
            "rank_corr": _rank_corr([r[1] for r in rows], [r[2] for r in rows])}


# ── the run ──────────────────────────────────────────────────────────────────

def run(symbols: Iterable[str], load=None, compute: Optional[Callable] = None,
        progress: Optional[Callable] = None) -> dict:
    """Study every name; {rows, meta}. `load(symbol) -> frame` injectable."""
    if load is None:
        from sepa import prices

        def load(sym):
            return prices.load_prices(sym, period="2y")
    t0 = time.time()
    rows, per_events, skipped, failed = [], {}, 0, 0
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
            rec = _study_with_events(df, sym, compute)
        except Exception as exc:                # noqa: BLE001
            log.debug("quick_bounce: %s failed: %s", sym, exc)
            failed += 1
            continue
        if rec is None:
            skipped += 1
            continue
        stats, events = rec
        rows.append(stats)
        if events:
            per_events[sym] = events
        if progress and k % 100 == 0:
            progress(k, len(syms))
    ev_total = sum(r["events"] for r in rows)
    quick_total = sum(r["quick"] for r in rows)
    same_total = sum(r["same_day"] for r in rows)
    gap_total = sum(r["gap_up"] for r in rows)
    first_total = sum(r["first_day_quick"] for r in rows)
    pb_q = sum(r.get("_pq") or 0 for r in rows)
    pb_n = sum(r.get("_pn") or 0 for r in rows)
    for r in rows:
        r.pop("_pq", None)
        r.pop("_pn", None)
    qual = [r for r in rows if qualifies(r)]
    meta = {"_id": META_ID, "generated_at": time.time(),
            "as_of": datetime.now().date().isoformat(),
            "universe": len(syms), "studied": len(rows), "skipped": skipped, "failed": failed,
            "events": ev_total, "quick": quick_total, "same_day": same_total, "gap_up": gap_total,
            "first_day_quick": first_total,
            "quick_rate_pct": round(100.0 * quick_total / ev_total, 1) if ev_total else None,
            "first_day_rate_pct": round(100.0 * first_total / ev_total, 1) if ev_total else None,
            "placebo_rate_pct": round(100.0 * pb_q / pb_n, 1) if pb_n else None,
            "qualifying": len(qual),
            "persistence": persistence(per_events),
            "params": {"anchor_step_bars": ANCHOR_STEP_BARS, "min_history_bars": MIN_HISTORY_BARS,
                       "touch_tol_pct": TOUCH_TOL_PCT, "wick_pct": WICK_PCT,
                       "bounce_min_pct": BOUNCE_MIN_PCT, "gap_min_pct": GAP_MIN_PCT,
                       "quick_max_touch_days": QUICK_MAX_TOUCH_DAYS,
                       "slow_lookahead_bars": SLOW_LOOKAHEAD_BARS, "slow_bounce_pct": SLOW_BOUNCE_PCT,
                       "min_events": MIN_EVENTS, "min_quick_rate_pct": MIN_QUICK_RATE_PCT,
                       "near_max_pct": NEAR_MAX_PCT, "room_min_pct": ROOM_MIN_PCT,
                       "lid_min_touches": AG.LID_MIN_TOUCHES, "lid_min_strength": AG.LID_MIN_STRENGTH},
            "seconds": round(time.time() - t0, 1), "disclaimer": DISCLAIMER}
    meta["edge_pts"] = (round(meta["quick_rate_pct"] - meta["placebo_rate_pct"], 1)
                        if meta["quick_rate_pct"] is not None and meta["placebo_rate_pct"] is not None
                        else None)
    return {"rows": rows, "meta": meta}


def _study_with_events(df, symbol: str, compute: Optional[Callable]):
    """study_symbol plus the raw events (for persistence) and the placebo counts."""
    df = df.rename(columns={c: str(c).lower() for c in df.columns})
    if len(df) < MIN_HISTORY_BARS + 2:
        return None
    bars = {k: [_f(v) for v in df[k].tolist()] for k in ("open", "high", "low", "close")}
    dates = [str(d)[:10] for d in df.index]
    n = len(dates)
    atrs = atr_series([h or 0.0 for h in bars["high"]], [l or 0.0 for l in bars["low"]],
                      [c or 0.0 for c in bars["close"]])
    compute = compute or (lambda hist: price_zones.compute(hist, **DR.zone_geom()))
    events, pq, pn = [], 0, 0
    anchor = MIN_HISTORY_BARS
    seen = set()
    while anchor < n - 1:
        hist = df.iloc[:anchor + 1]
        try:
            z = compute(hist)
        except Exception:                       # noqa: BLE001
            z = None
        end = min(n, anchor + ANCHOR_STEP_BARS)
        q, m = placebo_days(bars, atrs, anchor + 1, end)
        pq, pn = pq + q, pn + m
        if z:
            for b in (z.get("demand_zones") or []):
                if not (AG._valid_band(b) and AG.is_proven_band(b)):
                    continue
                for ev in episodes_for_band(bars, atrs, b, anchor + 1, end, dates):
                    key = (ev["date"], round(ev["band_lo"], 2))
                    if key in seen:
                        continue
                    seen.add(key)
                    events.append(ev)
        anchor += ANCHOR_STEP_BARS
    events.sort(key=lambda e: e["i"])
    stats = summarize(symbol, events, pq, pn, last_close=bars["close"][-1] if n else None)
    stats["_pq"], stats["_pn"] = pq, pn
    stats["avg_dollar_vol_50"] = avg_dollar_vol(df)
    return stats, events


def avg_dollar_vol(df, bars: int = 50) -> Optional[float]:
    """50-bar mean of close x volume — the boards' liquidity floor input."""
    try:
        tail = df.tail(bars)
        v = (tail["close"].astype(float) * tail["volume"].astype(float)).mean()
        return round(float(v), 0) if v == v else None
    except Exception:                           # noqa: BLE001
        return None


# ── Mongo ────────────────────────────────────────────────────────────────────

def _coll(coll=None):
    if coll is not None:
        return coll
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[COLL] if db is not None else None
    except Exception as exc:                    # noqa: BLE001
        log.warning("quick_bounce: no mongo: %s", exc)
        return None


def save(result: dict, coll=None) -> int:
    coll = _coll(coll)
    if coll is None:
        return 0
    n = 0
    for r in result.get("rows") or []:
        doc = dict(r, _id=r["symbol"], generated_at=result["meta"]["generated_at"])
        coll.replace_one({"_id": r["symbol"]}, doc, upsert=True)
        n += 1
    coll.replace_one({"_id": META_ID}, dict(result["meta"]), upsert=True)
    return n


def load_stats(symbols: Optional[Iterable[str]] = None, coll=None) -> dict:
    """{SYMBOL: stats} (every stored name when `symbols` is None)."""
    coll = _coll(coll)
    if coll is None:
        return {}
    q: dict = {"_id": {"$ne": META_ID}}
    if symbols is not None:
        q["_id"] = {"$in": [str(s).upper() for s in symbols]}
    try:
        return {d["_id"]: d for d in coll.find(q)}
    except Exception as exc:                    # noqa: BLE001
        log.warning("quick_bounce: load failed: %s", exc)
        return {}


def load_meta(coll=None) -> Optional[dict]:
    coll = _coll(coll)
    if coll is None:
        return None
    try:
        return coll.find_one({"_id": META_ID})
    except Exception:                           # noqa: BLE001
        return None


def qualifying_symbols(coll=None) -> set:
    return {s for s, st in load_stats(coll=coll).items() if qualifies(st)}


# ── the live list ────────────────────────────────────────────────────────────

def nearest_demand(px: float, bands: list) -> Optional[dict]:
    """The proven demand band price is INSIDE (dist 0) or the closest one
    UNDER the print within NEAR_MAX_PCT of its top; None = no band to bounce
    off (the name fell through every band, or sits far above them)."""
    best = None
    for b in bands or []:
        if not (AG._valid_band(b) and AG.is_proven_band(b)) or AG._kind(b) != "demand":
            continue
        lo, hi = float(b["lo"]), float(b["hi"])
        if lo <= px <= hi:
            d = 0.0
        elif px > hi:
            d = (px - hi) / hi * 100.0
            if d > NEAR_MAX_PCT:
                continue
        else:
            continue                             # under the band: fell through
        if best is None or d < best["dist_pct"]:
            best = {"band": AG._slim(b), "dist_pct": round(d, 2), "state": "inside" if d == 0.0 else "above"}
    return best


def live_row(symbol: str, stats: dict, doc: dict, px: Optional[float],
             min_room: Optional[float] = ROOM_MIN_PCT) -> Optional[dict]:
    """One board row or None (no print / no band nearby / not enough room)."""
    px = _f(px)
    if px is None or px <= 0 or not isinstance(doc, dict):
        return None
    near = nearest_demand(px, doc.get("bands") or [])
    if near is None:
        return None
    band = near["band"]
    bands, pc = doc.get("bands") or [], doc.get("prev_close")
    ok, room = AG.room_gate(px, bands, pc, min_room_pct=ROOM_MIN_PCT)   # the house floor: flagged always
    if min_room:
        ok_min = ok if float(min_room) == ROOM_MIN_PCT else AG.room_gate(px, bands, pc, min_room_pct=float(min_room))[0]
        if not ok_min:
            return {"symbol": symbol, "hidden": "room", "room": room, "dist_pct": near["dist_pct"]}
    stop = round(float(band["lo"]) * (1.0 - STOP_BUFFER_PCT / 100.0), 2)
    return {"symbol": symbol, "print": px, "band": band, "dist_pct": near["dist_pct"],
            "state": near["state"], "room": room, "room_ok": ok,
            "stop": stop, "risk_pct": round((px - stop) / px * 100.0, 2),
            "target": (room or {}).get("target"),
            "rr": (round((room["target"] - px) / (px - stop), 1)
                   if room and room.get("target") and px > stop and room["target"] > px else None),
            "plan": AG.plan_txt(px, band, room),
            "stats": {k: stats.get(k) for k in ("events", "quick", "same_day", "gap_up",
                                                "first_day_quick", "quick_rate_pct",
                                                "first_day_rate_pct", "placebo_rate_pct",
                                                "edge_pts", "median_lift_pct", "last_quick_date")},
            "prev_close": _f(doc.get("prev_close")), "atr14": _f(doc.get("atr14"))}


def order_key(row: dict) -> tuple:
    """Nearest the band first (inside = 0), then the most room."""
    room = row.get("room") or {}
    rp = room.get("room_pct_raw")
    return (row.get("dist_pct") if row.get("dist_pct") is not None else 99.0,
            -(rp if rp is not None else 999.0))


def live_rows(stats: dict, docs: dict, prints: dict,
              min_room: Optional[float] = ROOM_MIN_PCT) -> dict:
    """{rows, hidden_room, no_band, no_print} over the qualifying names."""
    rows, hidden_room, no_band, no_print = [], 0, 0, 0
    for sym, st in stats.items():
        if not qualifies(st):
            continue
        doc = docs.get(sym)
        px = prints.get(sym)
        if px is None:
            no_print += 1
            continue
        r = live_row(sym, st, doc, px, min_room) if doc else None
        if r is None:
            no_band += 1
            continue
        if r.get("hidden"):
            hidden_room += 1
            continue
        rows.append(r)
    rows.sort(key=order_key)
    return {"rows": rows, "hidden_room": hidden_room, "no_band": no_band, "no_print": no_print}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from sepa.universe import load_universe
    syms = load_universe() if len(sys.argv) < 2 else sys.argv[1].split(",")
    res = run(syms, progress=lambda k, n: log.info("quick_bounce: %d/%d", k, n))
    saved = save(res)
    m = res["meta"]
    log.info("QUICK-BOUNCE: studied=%s events=%s quick_rate=%s placebo=%s edge=%s first_day=%s "
             "qualifying=%s persistence=%s seconds=%s saved=%s",
             m["studied"], m["events"], m["quick_rate_pct"], m["placebo_rate_pct"], m["edge_pts"],
             m["first_day_rate_pct"], m["qualifying"], m["persistence"], m["seconds"], saved)
