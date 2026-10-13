"""🚩 Gajjala's five setups — the forward study the push mode waits on (WP6, 2026-10-13).

WHY IT EXISTS. DECISIONS round A ships the `gajjala_setup` push in SHADOW (`GAJJALA_PUSH_MODE = "shadow"`): every A+
is recorded, nothing reaches a phone "until the 250-session study (WP6) reads and Ajay flips the constant". Round C
fixed the study: "all three [exits] reported side by side: stop-or-16:00 · stop-or-60-min · breakeven after +1R then
the first 5-min close under the 9 EMA; window = last 250 sessions; placebo = same-session scanner names with no
setup." This file IS that study. It wires nothing, pushes nothing, writes nothing to Mongo.

COHORT (STRATEGY_SPEC §3.3 + WP6).
  * Per session one grouped-daily call → a SUPERSET of his scanner (volume ≥ SCAN_MIN_VOLUME, the day's range reaches
    a price that is in the band AND ≥ SCAN_MIN_CHANGE_PCT over the prior close, CS + ADR via the scanner's own type
    rule). The superset only saves calls — the real gate is the next line.
  * 1-minute bars (pre + RTH + after-hours) → the qualification minute q = the first minute whose close is in the band
    and ≥ +25% on the prior close while the shares traded since 04:00 are ≥ 1,000,000 (his three numbers, imported).
    A name that never reaches q is not in the study.

NO LOOK-AHEAD. The detectors are the tab's own (`detectors.read_all`), fed the frames `bars.build_frames` builds — the
same closed 5/15-minute frames, the same EMAs. The study replays the 5-minute pass grid: at pass label L the frames are
CUT to the bars whose right label is ≤ L (`prefix_frame`), so a detector at L sees nothing that printed after L. The
EMAs and K1's range average are causal, so the cut frame equals the frame a live pass would have built at L (the
test pins it: truncating the 1-minute input after any minute m leaves every event found before m unchanged).
`--q-scope live` (default since the 2026-10-13 critic round): the detectors see all of today's bars, as the live pass
does once the name is listed — DECISIONS H1 reads the 🎾 reference high as "today's high so far incl. premarket", and
bars before q are already in the past at every pass, so this is no look-ahead. `--q-scope warm` (STRATEGY_SPEC §3.3's
reading): bars before q only warm the EMAs and K1's average — legs, bases and the 🎾 high start at the bar holding q.
Whichever scope runs, a name enters the PLACEBO only when no setup broke under the LIVE scope either (a real A+ that the
warm cut hides is never a placebo name).

EVENTS. Per (symbol, setup, session) the FIRST pass whose read broke with every rule met ON ITS ENTRY BAR (the bar is
the latest closed bar of its frame) inside BUILD's push windows (09:45–16:00, 16:00–20:00 ET; `alerts.window_reason`
when WP4 has shipped it, else the §3.8 rule written out below). Three entry classes, all counted:
  aplus          — broke and held the stop through the entry bar (what the push records);
  stopped_in_bar — broke, then traded under the stop inside the same bar (the detector calls it "stopped", never A+;
                   a trader filled at the break owns that loss, so leaving it out would bias the study up);
  ambiguous      — the break and the stop in the SAME minute: counted as a stop, −1R (the order cannot be told).
Fill = the trigger, at the break minute, gross. Real nano-cap fills are worse; nothing here models slippage.

EXITS (Ajay round C, `GC.STUDY_EXIT_RULES`), walked on 1-minute bars AFTER the fill minute:
  session — the stop, else the close of the tape session the entry is in (RTH → the last minute before 16:00, or 13:00
            on a half day; after-hours → the last minute before 20:00 / 17:00);
  time60  — the stop, else the close of the minute STUDY_TIME_EXIT_MIN after the fill (capped at the session end);
  trail9  — the stop until the price reaches +STUDY_BE_AFTER_R R, then breakeven, then the first 5-minute bar that
            CLOSES under the 9 EMA (capped at the session end).
A minute that trades under the live stop exits at min(its open, the stop) — a gap through the stop fills at the open.
A minute touching both the stop and an exit level counts the STOP. R = (exit − trigger) / (trigger − stop).

PLACEBO (Ajay round C). Same-session scanner names (they reached q) on which NO setup broke with every rule met at any
pass, under the run's scope AND the live scope. For each event PLACEBO_PER_EVENT closed 5-minute bars are drawn (fixed seed) from those names after their own q,
inside the same push window (RTH vs after-hours), whose NEXT bar breaks the drawn bar's high: trigger = that high,
stop = that low, the same entry classes and the same exits. Δ = event mean R − placebo mean R.

CI + VERDICT. 95% percentile bootstrap, BOOT_DRAWS resamples, fixed seed, clustered by DATE and separately by SYMBOL;
fewer than MIN_CLUSTERS clusters → "no interval". "measured_edge" only when Δ's interval clears 0 on BOTH clusterings;
"inverted" when it sits under 0 on both; else "no_signal". Win rate is never the headline: expectancy (mean R), median
R, the stop-out rate and median MFE ride beside it.

AS PRINTED, NOT SPLIT-ADJUSTED. Every fetch here (grouped daily, 1-minute, daily) passes `adjusted=false`: prices and
shares as they printed that day, which is what his scanner saw. Adjusted bars carry a LATER split back in time — a 1:20
reverse split turns 5M shares at $0.30 into 250k at $6, the name fails the 1M gate and drops out; the names that later
reverse-split are mostly the failed, diluting ones, so adjusted bars bias the study UP. The cache directory carries a
layout marker (`CACHE_LAYOUT`); a directory built with adjusted bars (no marker) is refused, never mixed.

INSTRUMENT TYPES, POINT IN TIME. The scanner's map (`scanner.fetch_type_map`) lists ACTIVE tickers only, so a warrant /
right / unit that has since expired would read "type unknown" and be kept. For a superset name the active map does not
know, the study asks `/v3/reference/tickers/{T}?date={session}` (cached per session); only a name that dated lookup
cannot type either stays "type unknown" (kept, round A — the new-listing case). Those are counted in meta, and the
report is printed a second time with them dropped (`report_known_types`).

WHAT IT DOES NOT KNOW (said in the doc and in the report):
  * float — no point-in-time float exists here; 🎾 is measured on its STRUCTURE with the ≤ 10M float gate NOT applied;
  * a ticker the ACTIVE map knows is typed by today's entity (a reused ticker reads its current type);
  * half days `timeframes.HALF_DAYS` does not list (`HALF_DAYS_UNLISTED`) are SKIPPED and named in meta — on them
    `rth_close_time` says 16:00 and entries after 13:00 would be graded as RTH; the calendar list is checked only from
    `HALF_DAYS_CHECKED_FROM`, an earlier `--start` is flagged in meta;
  * the 16:00 minute carries the closing cross and is tagged after-hours (trap T7) — the "16:00 close" here is the
    15:59 minute's close.

HOUSE RULES. Every rule number is imported from `chart_maps.gajjala.constants` (or the scanner / detectors / bars
engines); the four numbers below are the study's METHOD (STRATEGY_SPEC WP6), not his rules. Never
`daytrading.data.load_intraday` (it writes `intraday_cache`): the only reads are this script's own HTTP GETs (1-minute
bars on `_fetch_massive_minute`'s URL and paging, but `adjusted=false`), the dated type lookup and
the grouped-daily GET, both into this script's own file cache. Refuses to start 09:30–16:00 ET unless `--force`.
A walk that gets fewer sessions than asked (a failed grouped call stops it) still writes its outputs, says so in meta
and on the report, and exits 3 unless `--allow-short`.

RUN (host or a THROWAWAY container — never `docker exec` into api/cron; outside RTH):
  cd backend && .venv/bin/python -m scripts.gajjala_study --exit all \\
      --cache /tmp/gajjala_study_cache --out /tmp/gajjala_study_out
  smoke (cache only, no HTTP, NOT QUOTABLE): add --offline --symbols AAA,BBB --draws 200
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import platform
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from catalysts.medical.reaction import is_market_day, prev_market_day, rth_close_time
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import scanner as SC
from chart_maps.gajjala.bars import RULES, Frame, build_frames
from daytrading.data import ET_AFTERHOURS_CLOSE, ET_PREMARKET_OPEN, ET_RTH_CLOSE, ET_RTH_OPEN
from sepa import symbols

log = logging.getLogger("scripts.gajjala_study")

ET = ZoneInfo("America/New_York")
ONE_MIN = pd.Timedelta(minutes=1)
LIVE_SESSIONS = ("premarket", "rth", "afterhours")             # daytrading.data._classify_session tags

# ── the study's METHOD (STRATEGY_SPEC WP6) — how it measures, not a rule of his ───────────────────────────────────
BOOT_DRAWS = 2000                       # STRATEGY_SPEC WP6 "2,000 resamples, fixed seed"
BOOT_SEED = 20261013                    # any fixed value — the day the study was written
MIN_CLUSTERS = 20                       # STRATEGY_SPEC WP6 "< 20 clusters → no interval"
PLACEBO_PER_EVENT = 50                  # STRATEGY_SPEC WP6 "per event 50 random closed 5-min bars"
CI_PCT = (2.5, 97.5)                    # the 95% two-sided percentile interval

BREAK_CLASSES = ("aplus", "stopped_in_bar", "ambiguous")
Q_SCOPES = ("warm", "live")
DEFAULT_Q_SCOPE = "live"                # what the live pass (and so the shadow ledger) reads — DECISIONS H1
VERDICTS = ("measured_edge", "inverted", "no_signal", "no_interval")
# 🎾 has no point-in-time float: its structure is measured with the float gate NOT applied (said on every report)
STUDY_FLOAT = {"shares": 0, "text": "float gate not applied (no point-in-time float)", "suspect": False}
GROUPED_URL = "https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/{d}"
# AS PRINTED: never adjusted=true here — a later reverse split would rewrite the volume his scanner saw (see the header)
GROUPED_PARAMS = {"adjusted": "false", "include_otc": "false"}
DAILY_PARAMS = {"adjusted": "false", "sort": "asc"}
MINUTE_PARAMS = {"adjusted": "false", "sort": "asc", "limit": 50000}   # daytrading.data._fetch_massive_minute's page size
MINUTE_PAGE_CAP = 20                    # daytrading.data._fetch_massive_minute's own paging cutoff
RETRY_429_SEC = 2                       # daytrading.data._fetch_massive_minute's own 429 pause
CACHE_LAYOUT = {"layout": 2, "adjusted": False}    # written into <cache>/cache_layout.json; layout 1 = adjusted=true
CACHE_MARKER = "cache_layout.json"
# NYSE early closes (13:00 ET) inside the study's reach that `supply_demand.timeframes.HALF_DAYS` does not list yet —
# calendar facts, not rules. A session here whose `rth_close_time` still says 16:00 is SKIPPED (named in meta); once
# the calendar lists it, it is studied normally. Dates before HALF_DAYS_CHECKED_FROM were never checked.
HALF_DAYS_UNLISTED = ("2025-07-03", "2025-11-28", "2025-12-24")
HALF_DAYS_CHECKED_FROM = "2025-01-01"


# ── clocks ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _as_date(d) -> date:
    if isinstance(d, datetime):
        return d.date()
    return d if isinstance(d, date) else date.fromisoformat(str(d))


def at_et(session, t) -> datetime:
    return datetime.combine(_as_date(session), t, tzinfo=ET)


def utc_naive(dt) -> pd.Timestamp:
    """An aware clock → the naive-UTC Timestamp the 1-minute loader indexes by."""
    ts = pd.Timestamp(dt)
    if ts.tzinfo is None:
        return ts
    return ts.tz_convert("UTC").tz_localize(None)


def et_of(ts) -> datetime:
    return pd.Timestamp(ts).tz_localize("UTC").tz_convert(ET).to_pydatetime()


def parse_bar_t(stamp: str) -> datetime:
    """A frame stamp ("%Y-%m-%d %H:%M" ET, the bar's CLOSE) → an aware ET datetime."""
    return datetime.strptime(stamp, "%Y-%m-%d %H:%M").replace(tzinfo=ET)


def frame_len(frame: str) -> timedelta:
    return pd.Timedelta(RULES[frame]).to_pytimedelta()


def session_bounds(session) -> dict:
    """{rth_open, push_open, rth_close, ah_close} on the ET clock. The after-hours close is the RTH close plus the
    regular after-hours span (20:00 − 16:00), so a half day ends at 17:00 without a new number."""
    d = _as_date(session)
    rth_open = at_et(d, ET_RTH_OPEN)
    rth_close = at_et(d, rth_close_time(d))
    return {"rth_open": rth_open,
            "push_open": rth_open + timedelta(minutes=GC.NO_TRADE_AFTER_OPEN_MIN),
            "rth_close": rth_close,
            "ah_close": rth_close + (at_et(d, ET_AFTERHOURS_CLOSE) - at_et(d, ET_RTH_CLOSE))}


def spec_window_reason(bar_t_et: datetime, session, frame: str) -> Optional[str]:
    """BUILD_SPEC §3.8 `window_reason`, written out — used only until WP4's `alerts.window_reason` exists (a test pins
    the two equal once it does)."""
    b = session_bounds(session)
    start = bar_t_et - frame_len(frame)
    if start < b["rth_open"]:
        return "suppressed_premarket"
    if start < b["push_open"]:
        return "suppressed_first15"
    if bar_t_et > b["ah_close"]:
        return "suppressed_window"
    return None


@lru_cache(maxsize=1)
def _alerts_window() -> Optional[Callable]:
    try:
        from chart_maps.gajjala.alerts import window_reason as wr     # WP4 — the push's own gate
    except Exception:                                               # noqa: BLE001 — not shipped yet
        return None
    return wr


def window_reason(bar_t_et: datetime, session, frame: str) -> Optional[str]:
    fn = _alerts_window() or spec_window_reason
    return fn(bar_t_et, _as_date(session), frame)


def window_class(bar_t_et: datetime, session, frame: str) -> str:
    """"rth" when the entry bar STARTS before the regular close, else "ah" (the after-hours push window)."""
    return "rth" if bar_t_et - frame_len(frame) < session_bounds(session)["rth_close"] else "ah"


def refused_window(now_et: datetime) -> bool:
    """True 09:30–16:00 ET on any weekday (the conservative reading: a holiday check is not worth an RTH replay)."""
    if now_et.weekday() >= 5:
        return False
    t = now_et.timetz().replace(tzinfo=None)
    return ET_RTH_OPEN <= t < ET_RTH_CLOSE


# ── his scanner, per minute ───────────────────────────────────────────────────────────────────────────────────────
def day_minutes(raw, session) -> Optional[pd.DataFrame]:
    """The 1-minute bars of ONE ET session, 04:00–20:00 only (pre / RTH / after-hours), time order."""
    if raw is None or len(raw) == 0:
        return raw
    d = _as_date(session)
    lo, hi = utc_naive(at_et(d, ET_PREMARKET_OPEN)), utc_naive(at_et(d, ET_AFTERHOURS_CLOSE))
    out = raw[(raw.index >= lo) & (raw.index < hi)].sort_index()
    if "session" in out.columns:
        out = out[out["session"].isin(LIVE_SESSIONS)]
    return out


def qualification_minute(today: Optional[pd.DataFrame], prev_close) -> Optional[pd.Timestamp]:
    """The START (naive UTC) of the first 1-minute bar at which his scanner lists the name: that minute's close in
    [SCAN_MIN_PRICE, SCAN_MAX_PRICE], ≥ SCAN_MIN_CHANGE_PCT over the prior regular close (`scanner._at_least`, the
    scanner's own edge-exact comparison) and the shares traded since 04:00 ≥ SCAN_MIN_VOLUME. None = never listed."""
    if today is None or len(today) == 0 or not prev_close or prev_close <= 0:
        return None
    cum = 0.0
    for ts, c, v in zip(today.index, today["close"].astype(float), today["volume"].astype(float).fillna(0.0)):
        cum += v
        if (GC.SCAN_MIN_PRICE <= c <= GC.SCAN_MAX_PRICE and cum >= GC.SCAN_MIN_VOLUME
                and SC._at_least(c, prev_close, GC.SCAN_MIN_CHANGE_PCT)):
            return ts
    return None


def type_of(sym: str, types: Optional[dict], resolve: Optional[Callable] = None) -> str:
    """The instrument type: the scanner's map first (`scanner.row_type`); a name it does not know is asked of
    `resolve(sym)` (the dated reference lookup — the map lists ACTIVE tickers only, so an expired warrant / right /
    unit would otherwise read unknown). SCAN_UNKNOWN_TYPE when neither knows it."""
    typ = SC.row_type(symbols.for_yahoo(sym), types or {})
    if typ == GC.SCAN_UNKNOWN_TYPE and resolve is not None:
        got = resolve(sym)
        if got:
            return str(got)
    return typ


def type_ok(sym: str, types: Optional[dict], resolve: Optional[Callable] = None) -> bool:
    """The scanner's instrument rule (round A): CS + ADRC, an unmapped symbol per SCAN_UNKNOWN_TYPE_POLICY."""
    if GC.SCAN_INSTRUMENT_TYPES is None:
        return True
    typ = type_of(sym, types, resolve)
    if typ == GC.SCAN_UNKNOWN_TYPE:
        return GC.SCAN_UNKNOWN_TYPE_POLICY != "drop"
    return typ in GC.SCAN_INSTRUMENT_TYPES


def superset(today_rows: dict, prev_rows: dict, types: Optional[dict] = None, *,
             resolve: Optional[Callable] = None, unknown: Optional[set] = None) -> list:
    """[(SYM, prev_close)] from two grouped-daily calls: shares ≥ SCAN_MIN_VOLUME and the day's range holds a price
    that is both inside the band and ≥ SCAN_MIN_CHANGE_PCT over the prior close. Sorted by symbol. The type is checked
    LAST (a dated lookup costs a call); a name kept as "type unknown" is added to `unknown`."""
    out = []
    for sym, r in (today_rows or {}).items():
        prev = (prev_rows or {}).get(sym, {}).get("c")
        try:
            prev, h, l, v = float(prev), float(r["h"]), float(r["l"]), float(r["v"])
        except (TypeError, ValueError, KeyError):
            continue
        if not prev > 0 or v < GC.SCAN_MIN_VOLUME:
            continue
        lo = max(l, prev * (1 + GC.SCAN_MIN_CHANGE_PCT / 100), GC.SCAN_MIN_PRICE)
        if lo > min(h, GC.SCAN_MAX_PRICE) or not type_ok(sym, types, resolve):
            continue
        if unknown is not None and GC.SCAN_INSTRUMENT_TYPES is not None and \
                type_of(sym, types, resolve) == GC.SCAN_UNKNOWN_TYPE:
            unknown.add(sym)
        out.append((sym, prev))
    return sorted(out)


# ── frames at a pass ──────────────────────────────────────────────────────────────────────────────────────────────
def prefix_frame(F: Frame, n: int, today_from: Optional[int] = None) -> Frame:
    """`F` as it stood when its n-th bar was the latest closed one. `today_from` narrows TODAY to start at that frame
    index (the q scope); the bars before it stay in the frame and only warm the EMAs / K1's average."""
    lo = F.today.start if today_from is None else max(F.today.start, today_from)
    G = Frame(o=F.o[:n], h=F.h[:n], l=F.l[:n], c=F.c[:n], v=F.v[:n], t=F.t[:n], session=F.session[:n],
              ema9=F.ema9[:n], ema21=F.ema21[:n], today=range(min(lo, n), n), df=F.df.iloc[:n], frame=F.frame)
    keep = set(G.t[G.today.start:])
    G.minutes = {s: m for s, m in F.minutes.items() if s in keep}
    return G


def first_after(F: Frame, q: pd.Timestamp) -> int:
    """Frame index of the first bar whose right label is after q's START — the bar holding q, or the first after it."""
    idx = F.df.index
    return int(idx.searchsorted(q, side="right")) if len(idx) else 0


def pass_grid(session, q: pd.Timestamp) -> list:
    """The 5-minute pass labels (naive UTC) from the first one that can see q's minute closed through the
    after-hours close. A pass at label L sees exactly the bars whose right label is ≤ L (`bars.closed_only`)."""
    end = utc_naive(session_bounds(session)["ah_close"])
    step = pd.Timedelta(seconds=GC.PASS_CADENCE_SEC)
    start = (q + ONE_MIN).ceil(step)
    if start > end:
        return []
    return list(pd.date_range(start, end, freq=step))


def break_class(read: Optional[dict]) -> Optional[str]:
    """Which entry class a read is, or None. Only a break ON the frame's latest closed bar with every rule met counts:
    aplus (held the stop through the bar), stopped_in_bar (traded under it after the break), ambiguous (the break and
    the stop in one minute — the detector's only missed key is then "entry")."""
    if not read or not read.get("broke") or not read.get("entry_bar_t"):
        return None
    if read["entry_bar_t"] != read.get("as_of_bar_t"):
        return None
    st = read.get("state")
    if st == "aplus":
        return "aplus"
    if st == "stopped":
        return "stopped_in_bar"
    if st == "partial" and read.get("missed") == ["entry"] and not read.get("unjudged"):
        return "ambiguous"
    return None


# ── entry fill + exits ────────────────────────────────────────────────────────────────────────────────────────────
def bucket_minutes(raw: pd.DataFrame, label: pd.Timestamp, frame: str) -> pd.DataFrame:
    """The 1-minute bars inside the bucket that closes at `label` — the same grouping `bars._minutes_by_bucket` uses
    (LEFT-closed: [label − rule, label))."""
    rule = pd.Timedelta(RULES[frame])
    return raw[(raw.index >= label - rule) & (raw.index < label)]


def fill_of(F: Frame, j: int, trigger: float, stop: float, raw: pd.DataFrame) -> tuple:
    """(event, fill minute START | None) for entry bar j via the detectors' own `entry_event`: "break" fills at the
    first minute above the trigger; "ambiguous" is that same minute when it also traded under the stop."""
    mins = bucket_minutes(raw, F.df.index[j], F.frame)
    rows = list(zip(mins["open"].astype(float), mins["high"].astype(float), mins["low"].astype(float),
                    mins["close"].astype(float), mins["volume"].astype(float)))
    ev, m = D.entry_event(F, j, trigger, stop, rows)
    if ev == "break" and m is not None:
        return ev, mins.index[m]
    if ev == "ambiguous":
        hit = next((i for i, r in enumerate(rows) if r[1] > trigger), None)
        return ev, (mins.index[hit] if hit is not None else None)
    return ev, None


def walk_exit(after: pd.DataFrame, trigger: float, stop: float, rule: str, *, session_end: pd.Timestamp,
              time_exit: Optional[pd.Timestamp] = None, ema_exit: Optional[dict] = None) -> dict:
    """One exit rule over the 1-minute bars AFTER the fill minute (naive-UTC minute STARTS). -> {r, exit_px, reason,
    exit_t, mfe_r}. reason ∈ stop | breakeven | time | ema9 | session_end."""
    risk = trigger - stop
    live_stop, be = stop, False
    mfe = 0.0
    last_c, last_t = trigger, None
    rows = list(after.itertuples()) if after is not None and len(after) else []
    step = pd.Timedelta(RULES["5m"])

    def out(px, reason, ts):
        return {"r": (px - trigger) / risk, "exit_px": px, "reason": reason,
                "exit_t": et_of(ts).strftime("%Y-%m-%d %H:%M") if ts is not None else None, "mfe_r": mfe / risk}

    for k, row in enumerate(rows):
        ts = row.Index
        if ts >= session_end:
            break
        o, h, l, c = float(row.open), float(row.high), float(row.low), float(row.close)
        if l < live_stop:                                           # a touch of the stop wins every tie
            return out(min(o, live_stop), "breakeven" if be else "stop", ts)
        mfe = max(mfe, h - trigger)
        if rule == "time60" and time_exit is not None and ts + ONE_MIN >= time_exit:
            return out(c, "time", ts)
        if rule == "trail9":
            if be:
                lab = ts.floor(step) + step
                nxt = rows[k + 1].Index if k + 1 < len(rows) else None
                if (nxt is None or nxt >= lab) and (ema_exit or {}).get(lab):
                    return out(c, "ema9", ts)
            elif h >= trigger + GC.STUDY_BE_AFTER_R * risk:
                be, live_stop = True, trigger                       # breakeven from the NEXT minute on
        last_c, last_t = c, ts
    return out(last_c, "session_end", last_t)


def ema_exit_map(f5: Frame) -> dict:
    """{5-minute right label (naive UTC): closed under its 9 EMA} — causal (the 9 EMA of a bar uses bars ≤ it)."""
    return {f5.df.index[i]: (f5.ema9[i] is not None and f5.c[i] < f5.ema9[i]) for i in f5.today}


def trade_outcomes(today: pd.DataFrame, fill_ts: pd.Timestamp, trigger: float, stop: float, session, wclass: str,
                   ema_exit: dict, entry_class: str, rules=GC.STUDY_EXIT_RULES) -> dict:
    """{rule: walk_exit result}. An ambiguous entry is a stop on every rule (−1R)."""
    b = session_bounds(session)
    end = utc_naive(b["rth_close"] if wclass == "rth" else b["ah_close"])
    if entry_class == "ambiguous":
        return {r: {"r": -1.0, "exit_px": stop, "reason": "stop", "exit_t": et_of(fill_ts).strftime("%Y-%m-%d %H:%M"),
                    "mfe_r": 0.0} for r in rules}
    after = today[today.index > fill_ts]
    t_exit = fill_ts + ONE_MIN + pd.Timedelta(minutes=GC.STUDY_TIME_EXIT_MIN)
    return {r: walk_exit(after, trigger, stop, r, session_end=end, time_exit=t_exit, ema_exit=ema_exit)
            for r in rules}


def _flat(rec: dict, outcomes: dict) -> dict:
    for rule, o in outcomes.items():
        rec[f"r_{rule}"] = o["r"]
        rec[f"exit_{rule}"] = o["reason"]
        rec[f"exit_t_{rule}"] = o["exit_t"]
        rec[f"mfe_{rule}"] = o["mfe_r"]
    return rec


# ── one symbol-session ────────────────────────────────────────────────────────────────────────────────────────────
def study_symbol_day(symbol: str, session, raw_prev, raw_today, prev_close, *, scope: str = DEFAULT_Q_SCOPE,
                     float_read=None, rules=GC.STUDY_EXIT_RULES, with_pool: bool = True) -> dict:
    """Replay one name's session through the tab's detectors on the 5-minute pass grid from q on.
    -> {symbol, session, q_t, events, suppressed, setup_free, live_break, pool}. `events` = the first in-window break
    per setup under `scope`; `setup_free` = no setup broke under `scope` NOR under the live scope; `pool` = placebo
    candidates (only when setup_free)."""
    if scope not in Q_SCOPES:
        raise ValueError(f"scope must be one of {Q_SCOPES}")
    d = _as_date(session)
    out = {"symbol": symbol, "session": d.isoformat(), "q_t": None, "events": [], "suppressed": Counter(),
           "setup_free": None, "live_break": None, "pool": []}
    today = day_minutes(raw_today, d)
    q = qualification_minute(today, prev_close)
    if q is None:
        return out
    out["q_t"] = et_of(q).strftime("%Y-%m-%d %H:%M")
    prev = raw_prev
    if prev is not None and len(prev) and "session" in prev.columns:
        prev = prev[prev["session"].isin(LIVE_SESSIONS)]
    everything = utc_naive(session_bounds(d)["ah_close"]) + pd.Timedelta(days=1)
    fr = build_frames(symbol, d, everything, prev, today)
    if fr is None:
        return out
    f5 = fr.f5
    ema_exit = ema_exit_map(f5)
    ctx = {"symbol": symbol, "float_read": float_read if float_read is not None else STUDY_FLOAT}
    seen, out["suppressed"], any_break = replay_passes(fr, d, q, today, scope, ctx, ema_exit, rules,
                                                       q_t=out["q_t"])
    live_break = any_break if scope == "live" else \
        replay_passes(fr, d, q, today, "live", ctx, ema_exit, rules, record=False)[2]
    out["events"] = [seen[s] for s in GC.SETUPS if s in seen]
    out["live_break"] = live_break
    out["setup_free"] = not (any_break or live_break)
    if with_pool and out["setup_free"]:
        out["pool"] = placebo_pool(symbol, d, f5, today, q, ema_exit, rules)
    return out


def replay_passes(fr, d: date, q: pd.Timestamp, today: pd.DataFrame, scope: str, ctx: dict, ema_exit: dict, rules, *,
                  record: bool = True, q_t: Optional[str] = None) -> tuple:
    """The pass loop. -> (seen {setup: event row}, suppressed Counter, any_break). `record=False` only answers
    "did any setup break with every rule met on its entry bar" and stops at the first such read."""
    f5, f15 = fr.f5, fr.f15
    symbol = ctx["symbol"]
    from5 = first_after(f5, q) if scope == "warm" else None
    from15 = first_after(f15, q) if scope == "warm" else None
    lab5, lab15 = f5.df.index, f15.df.index
    seen: dict = {}
    noted: set = set()
    suppressed: Counter = Counter()
    any_break = False
    last_n = None
    for L in pass_grid(d, q):
        n5, n15 = int(lab5.searchsorted(L, side="right")), int(lab15.searchsorted(L, side="right"))
        if n5 == 0 or (n5, n15) == last_n:
            continue                                                # no new closed bar → the same reads
        last_n = (n5, n15)
        frames = {"5m": prefix_frame(f5, n5, from5), "15m": prefix_frame(f15, n15, from15) if n15 else None}
        for setup, r in D.read_all(frames, ctx).items():
            cls = break_class(r)
            if cls is None:
                continue
            any_break = True
            if not record:
                return seen, suppressed, True
            if setup in seen or (setup, r["entry_bar_t"]) in noted:
                continue
            noted.add((setup, r["entry_bar_t"]))
            bt = parse_bar_t(r["entry_bar_t"])
            why = window_reason(bt, d, r["frame"])
            if why:
                suppressed[why] += 1
                continue
            F = f15 if r["frame"] == "15m" else f5
            j = F.t.index(r["entry_bar_t"])
            trigger, stop = float(r["trigger"]), float(r["stop"])
            if not trigger > stop:
                suppressed["no_risk"] += 1
                continue
            _ev, fill_ts = fill_of(F, j, trigger, stop, today)
            if fill_ts is None:
                suppressed["no_minutes"] += 1
                continue
            wclass = window_class(bt, d, r["frame"])
            rec = {"symbol": symbol, "session": d.isoformat(), "setup": setup, "frame": r["frame"],
                   "entry_bar_t": r["entry_bar_t"], "entry_class": cls, "trigger": trigger, "stop": stop,
                   "risk_pct": r.get("risk_pct"), "fill_t": et_of(fill_ts).strftime("%Y-%m-%d %H:%M"),
                   "window": wclass, "q_t": q_t, "pass_t": et_of(L).strftime("%Y-%m-%d %H:%M"),
                   "variant": r.get("variant"), "grade": r.get("grade"), "q_scope": scope}
            seen[setup] = _flat(rec, trade_outcomes(today, fill_ts, trigger, stop, d, wclass, ema_exit, cls, rules))
    return seen, suppressed, any_break


def placebo_pool(symbol: str, session, f5: Frame, today: pd.DataFrame, q: pd.Timestamp, ema_exit: dict,
                 rules=GC.STUDY_EXIT_RULES) -> list:
    """Every closed 5-minute bar b of a no-setup name AFTER q whose next bar j = b+1 breaks h[b] inside a push window:
    trigger h[b], stop l[b], filled by the detectors' `entry_event`, the same exits. Never a bar before q."""
    d = _as_date(session)
    lo = max(first_after(f5, q), f5.today.start)
    pool = []
    for b in range(lo, len(f5) - 1):
        j = b + 1
        trigger, stop = f5.h[b], f5.l[b]
        if not trigger > stop or not f5.h[j] > trigger:
            continue
        bt = parse_bar_t(f5.t[j])
        if window_reason(bt, d, "5m"):
            continue
        ev, fill_ts = fill_of(f5, j, trigger, stop, today)
        if ev == "stop" or fill_ts is None:
            continue
        cls = "ambiguous" if ev == "ambiguous" else "break"
        wclass = window_class(bt, d, "5m")
        rec = {"symbol": symbol, "session": d.isoformat(), "bar_t": f5.t[b], "entry_bar_t": f5.t[j],
               "entry_class": cls, "trigger": trigger, "stop": stop, "window": wclass,
               "fill_t": et_of(fill_ts).strftime("%Y-%m-%d %H:%M")}
        pool.append(_flat(rec, trade_outcomes(today, fill_ts, trigger, stop, d, wclass, ema_exit, cls, rules)))
    return pool


def sample_placebo(events: list, pools: dict, *, per_event: int = PLACEBO_PER_EVENT, seed: int = BOOT_SEED) -> tuple:
    """-> (rows, missing). For each event (deterministic order) up to `per_event` draws WITHOUT replacement from the
    same session's no-setup pool in the same push window; an event with an empty pool is counted `missing`."""
    rng = np.random.default_rng(seed)
    rows, missing = [], 0
    for ev in sorted(events, key=lambda e: (e["session"], e["setup"], e["symbol"], e["entry_bar_t"])):
        cand = pools.get((ev["session"], ev["window"])) or []
        if not cand:
            missing += 1
            continue
        k = min(per_event, len(cand))
        for i in sorted(rng.choice(len(cand), size=k, replace=False).tolist()):
            rows.append(dict(cand[i], setup=ev["setup"], event_symbol=ev["symbol"],
                             event_entry_bar_t=ev["entry_bar_t"]))
    return rows, missing


# ── statistics ────────────────────────────────────────────────────────────────────────────────────────────────────
def _cluster_sums(vals, keys) -> tuple:
    keys = list(keys)
    uniq = sorted(set(keys))
    pos = {k: i for i, k in enumerate(uniq)}
    s, n = np.zeros(len(uniq)), np.zeros(len(uniq))
    for v, k in zip(vals, keys):
        s[pos[k]] += float(v)
        n[pos[k]] += 1
    return uniq, s, n


def cluster_ci(vals, keys, *, draws: int = BOOT_DRAWS, seed: int = BOOT_SEED) -> Optional[list]:
    """95% percentile CI of the MEAN, resampling whole clusters with replacement. < MIN_CLUSTERS → None."""
    uniq, s, n = _cluster_sums(vals, keys)
    if len(uniq) < MIN_CLUSTERS:
        return None
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(uniq), size=(draws, len(uniq)))
    means = s[pick].sum(axis=1) / n[pick].sum(axis=1)
    lo, hi = np.percentile(means, CI_PCT)
    return [float(lo), float(hi)]


def cluster_delta_ci(ev_vals, ev_keys, pl_vals, pl_keys, *, draws: int = BOOT_DRAWS,
                     seed: int = BOOT_SEED) -> Optional[list]:
    """95% CI of mean(event) − mean(placebo), resampling clusters from the UNION of both sides' keys (a date carries
    its events and its placebo draws together). Either side under MIN_CLUSTERS clusters → None."""
    if len(set(ev_keys)) < MIN_CLUSTERS or len(set(pl_keys)) < MIN_CLUSTERS:
        return None
    uniq = sorted(set(ev_keys) | set(pl_keys))
    pos = {k: i for i, k in enumerate(uniq)}
    es, en, ps, pn = (np.zeros(len(uniq)) for _ in range(4))
    for v, k in zip(ev_vals, ev_keys):
        es[pos[k]] += float(v)
        en[pos[k]] += 1
    for v, k in zip(pl_vals, pl_keys):
        ps[pos[k]] += float(v)
        pn[pos[k]] += 1
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(uniq), size=(draws, len(uniq)))
    e_n, p_n = en[pick].sum(axis=1), pn[pick].sum(axis=1)
    ok = (e_n > 0) & (p_n > 0)
    if not ok.any():
        return None
    delta = es[pick].sum(axis=1)[ok] / e_n[ok] - ps[pick].sum(axis=1)[ok] / p_n[ok]
    lo, hi = np.percentile(delta, CI_PCT)
    return [float(lo), float(hi)]


def verdict(ci_date: Optional[list], ci_symbol: Optional[list]) -> str:
    """measured_edge only when Δ clears 0 on BOTH clusterings; inverted when under 0 on both."""
    if ci_date is None or ci_symbol is None:
        return "no_interval"
    if ci_date[0] > 0 and ci_symbol[0] > 0:
        return "measured_edge"
    if ci_date[1] < 0 and ci_symbol[1] < 0:
        return "inverted"
    return "no_signal"


def _r(x, nd=3):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def summarize(rows: list, rule: str, *, sym_key: str = "symbol", draws: int = BOOT_DRAWS,
              seed: int = BOOT_SEED) -> dict:
    """n / dates / symbols, expectancy (mean R), median R, win rate, stop-out rate (the ORIGINAL stop), breakeven
    rate, median MFE (R) and the date- and symbol-clustered CIs of the mean."""
    rs = [x[f"r_{rule}"] for x in rows if x.get(f"r_{rule}") is not None]
    keep = [x for x in rows if x.get(f"r_{rule}") is not None]
    if not keep:
        return {"n": 0, "dates": 0, "symbols": 0, "mean_r": None, "median_r": None, "win_rate": None,
                "stop_rate": None, "breakeven_rate": None, "median_mfe_r": None, "ci_date": None, "ci_symbol": None}
    reasons = Counter(x[f"exit_{rule}"] for x in keep)
    return {"n": len(keep), "dates": len({x["session"] for x in keep}), "symbols": len({x[sym_key] for x in keep}),
            "mean_r": _r(np.mean(rs)), "median_r": _r(np.median(rs)),
            "win_rate": _r(sum(1 for r in rs if r > 0) / len(rs)),
            "stop_rate": _r(reasons.get("stop", 0) / len(keep)),
            "breakeven_rate": _r(reasons.get("breakeven", 0) / len(keep)),
            "median_mfe_r": _r(np.median([x[f"mfe_{rule}"] for x in keep])),
            "ci_date": _ci(cluster_ci(rs, [x["session"] for x in keep], draws=draws, seed=seed)),
            "ci_symbol": _ci(cluster_ci(rs, [x[sym_key] for x in keep], draws=draws, seed=seed))}


def _ci(ci):
    return None if ci is None else [_r(ci[0]), _r(ci[1])]


def compare(events: list, placebo: list, rule: str, *, draws: int = BOOT_DRAWS, seed: int = BOOT_SEED) -> dict:
    """Event vs placebo on one exit rule: both summaries + Δ mean R with both clustered CIs + the verdict."""
    ev = [x for x in events if x.get(f"r_{rule}") is not None]
    pl = [x for x in placebo if x.get(f"r_{rule}") is not None]
    se, sp = summarize(ev, rule, draws=draws, seed=seed), summarize(pl, rule, draws=draws, seed=seed)
    ev_r, pl_r = [x[f"r_{rule}"] for x in ev], [x[f"r_{rule}"] for x in pl]
    d_date = cluster_delta_ci(ev_r, [x["session"] for x in ev], pl_r, [x["session"] for x in pl],
                              draws=draws, seed=seed) if ev and pl else None
    d_sym = cluster_delta_ci(ev_r, [x["symbol"] for x in ev], pl_r, [x["symbol"] for x in pl],
                             draws=draws, seed=seed) if ev and pl else None
    delta = (se["mean_r"] - sp["mean_r"]) if se["mean_r"] is not None and sp["mean_r"] is not None else None
    return {"events": se, "placebo": sp, "delta_mean_r": _r(delta), "delta_ci_date": _ci(d_date),
            "delta_ci_symbol": _ci(d_sym), "verdict": verdict(d_date, d_sym)}


def build_report(events: list, placebo: list, rules=GC.STUDY_EXIT_RULES, *, draws: int = BOOT_DRAWS,
                 seed: int = BOOT_SEED) -> dict:
    """{setup | "all": {rule: compare(...)}} plus the entry-class counts per setup."""
    out: dict = {"by_setup": {}, "entry_classes": {}}
    for setup in list(GC.SETUPS) + ["all"]:
        ev = events if setup == "all" else [e for e in events if e["setup"] == setup]
        pl = placebo if setup == "all" else [p for p in placebo if p["setup"] == setup]
        out["by_setup"][setup] = {rule: compare(ev, pl, rule, draws=draws, seed=seed) for rule in rules}
        out["entry_classes"][setup] = dict(Counter(e.get("entry_class") for e in ev))
    return out


# ── data: grouped daily + 1-minute bars, this script's own file cache (never Mongo) ───────────────────────────────
def _fetch_grouped_http(d: date) -> Optional[dict]:
    """{SYM: {o, h, l, c, v}} for one session; {} = no session that day (holiday); None = the call failed."""
    from massive_keys import stocks_key
    from sepa import prices
    key = stocks_key()
    if not key:
        return None
    try:
        r = prices._http().get(GROUPED_URL.format(d=d.isoformat()),
                               params=dict(GROUPED_PARAMS, apiKey=key), timeout=60)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("grouped %s: %s", d, prices._scrub_key(exc))
        return None
    if r.status_code != 200:
        log.warning("grouped %s: HTTP %s", d, r.status_code)
        return None
    out = {}
    for it in (r.json() or {}).get("results") or []:
        sym = str(it.get("T") or "").strip().upper()
        if sym:
            out[sym] = {k: it.get(k) for k in ("o", "h", "l", "c", "v")}
    return out


def _fetch_daily_http(sym: str, start: date, end: date) -> Optional[list]:
    """[{t (ms), o, h, l, c, v}] daily bars for one ticker, oldest first; [] = none on file; None = the call failed."""
    from massive_keys import stocks_key
    from sepa import prices
    key = stocks_key()
    if not key:
        return None
    url = (f"https://api.massive.com/v2/aggs/ticker/{symbols.for_massive(sym)}/range/1/day/"
           f"{start.isoformat()}/{end.isoformat()}")
    try:
        r = prices._http().get(url, params=dict(DAILY_PARAMS, apiKey=key), timeout=30)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("daily %s: %s", sym, prices._scrub_key(exc))
        return None
    if r.status_code != 200:
        log.warning("daily %s: HTTP %s", sym, r.status_code)
        return None
    return [{k: it.get(k) for k in ("t", "o", "h", "l", "c", "v")} for it in (r.json() or {}).get("results") or []]


def _fetch_minutes_http(sym: str, d: date) -> Optional[pd.DataFrame]:
    """1-minute bars of one session AS PRINTED (`adjusted=false`) — `daytrading.data._fetch_massive_minute`'s URL,
    paging and 429 handling, but this script's own GET (that loader hard-codes adjusted=true). NO Mongo write.
    -> the loader's frame shape; an empty frame = no prints that day (an answer); None = the call failed or was cut."""
    from daytrading.data import _CB_TRIP_AFTER, _FETCH_TIMEOUT_SEC, BASE_URL
    from massive_keys import stocks_key
    from sepa import prices
    key = stocks_key()
    if not key:
        return None
    http = prices._http()
    url: Optional[str] = f"{BASE_URL}/v2/aggs/ticker/{symbols.for_massive(sym).upper()}/range/1/minute/{d}/{d}"
    params = dict(MINUTE_PARAMS, apiKey=key)
    rows, pages, n_429 = [], 0, 0
    while url:
        try:
            r = http.get(url, params=params, timeout=_FETCH_TIMEOUT_SEC)
        except Exception as exc:                                    # noqa: BLE001
            log.warning("minutes %s %s: %s", sym, d, prices._scrub_key(exc))
            return None
        if r.status_code == 429:
            n_429 += 1
            if n_429 >= _CB_TRIP_AFTER:
                log.warning("minutes %s %s: HTTP 429 x%d, giving up", sym, d, n_429)
                return None
            time.sleep(RETRY_429_SEC)
            continue
        n_429 = 0
        if r.status_code != 200:
            log.warning("minutes %s %s: HTTP %s", sym, d, r.status_code)
            return None
        body = r.json() or {}
        rows.extend(body.get("results") or [])
        url = body.get("next_url")
        params = {"apiKey": key}                                    # next_url carries its own cursor
        pages += 1
        if url and pages >= MINUTE_PAGE_CAP:
            log.warning("minutes %s %s: paging cut at %d pages — not cached", sym, d, pages)
            return None
    return json_to_frame({"t": [it.get("t") for it in rows], "o": [it.get("o") for it in rows],
                          "h": [it.get("h") for it in rows], "l": [it.get("l") for it in rows],
                          "c": [it.get("c") for it in rows], "v": [it.get("v") or 0.0 for it in rows]})


def _fetch_type_dated_http(sym: str, d: date) -> Optional[dict]:
    """{"type": T | None} for one ticker AS OF the session (`/v3/reference/tickers/{T}?date=`) — the active-only map
    cannot type a warrant / right / unit that has since expired. 404 = no reference entry that day ({"type": None},
    an answer); None = the call failed."""
    from massive_keys import stocks_key
    from sepa import prices
    key = stocks_key()
    if not key:
        return None
    url = f"{SC._REF_TICKERS_URL}/{symbols.for_massive(sym).upper()}"
    try:
        r = prices._http().get(url, params={"date": d.isoformat(), "apiKey": key}, timeout=30)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("type %s %s: %s", sym, d, prices._scrub_key(exc))
        return None
    if r.status_code == 404:
        return {"type": None}
    if r.status_code != 200:
        log.warning("type %s %s: HTTP %s", sym, d, r.status_code)
        return None
    res = (r.json() or {}).get("results") or {}
    return {"type": (str(res["type"]) if res.get("type") else None)}


class StaleCache(RuntimeError):
    """The cache directory was built under another layout (layout 1 = split-adjusted bars)."""


class Cache:
    """JSON file cache: grouped/<D>.json, minutes/<D>/<SYM>.json. `offline` = never fetch. A failed fetch (None) is
    never written, so a re-run retries it; an empty answer is written (it is an answer)."""

    def __init__(self, root, *, offline: bool = False, fetch_grouped: Optional[Callable] = None,
                 fetch_minutes: Optional[Callable] = None, fetch_daily: Optional[Callable] = None,
                 fetch_type: Optional[Callable] = None):
        self.root = Path(root)
        self.offline = offline
        self._fg = fetch_grouped or _fetch_grouped_http
        self._fm = fetch_minutes or _fetch_minutes_http
        self._fd = fetch_daily or _fetch_daily_http
        self._ft = fetch_type or _fetch_type_dated_http
        self.stats = Counter()
        self._check_layout()

    def _check_layout(self) -> None:
        """A cache built with adjusted bars (no marker, layout 1) is REFUSED — mixing the two would put split-
        adjusted volume back into the cohort. An empty / new directory gets the marker."""
        marker = self._read(self.root / CACHE_MARKER)
        if marker is None:
            if any((self.root / sub).exists() for sub in ("grouped", "minutes", "daily", "types")):
                raise StaleCache(f"{self.root} holds bars without a layout marker (split-adjusted, layout 1) — "
                                 f"use a fresh --cache directory")
            self._write(self.root / CACHE_MARKER, CACHE_LAYOUT)
        elif marker != CACHE_LAYOUT:
            raise StaleCache(f"{self.root} layout {marker} != {CACHE_LAYOUT} — use a fresh --cache directory")

    def ticker_type(self, sym: str, d: date) -> Optional[str]:
        """The dated reference type of `sym` on session `d` (cached per session); None = unknown or not fetched."""
        p = self.root / "types" / d.isoformat() / f"{sym.replace('/', '_')}.json"
        got = self._read(p)
        if got is None:
            if self.offline:
                self.stats["type_offline_miss"] += 1
                return None
            got = self._ft(sym, d)
            self.stats["type_fetch"] += 1
            if got is None:
                self.stats["type_failed"] += 1
                return None
            self._write(p, got)
        else:
            self.stats["type_hit"] += 1
        return got.get("type") if isinstance(got, dict) else None

    def daily_bars(self, sym: str, d: date, *, lookback_days: int = 14) -> Optional[list]:
        """Daily bars from `d − lookback_days` through `d` (the replay's prior close + prior session); cached."""
        p = self.root / "daily" / f"{sym.replace('/', '_')}_{d.isoformat()}.json"
        got = self._read(p)
        if got is not None:
            return got
        if self.offline:
            return None
        got = self._fd(sym, d - timedelta(days=lookback_days), d)
        if got is not None:
            self._write(p, got)
        return got

    def _read(self, p: Path):
        try:
            return json.loads(p.read_text())
        except (OSError, ValueError):
            return None

    def _write(self, p: Path, obj) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(obj))
        tmp.replace(p)

    def grouped(self, d: date) -> Optional[dict]:
        p = self.root / "grouped" / f"{d.isoformat()}.json"
        got = self._read(p)
        if got is not None:
            self.stats["grouped_hit"] += 1
            return got
        if self.offline:
            self.stats["grouped_offline_miss"] += 1
            return None
        got = self._fg(d)
        self.stats["grouped_fetch"] += 1
        if got is not None:
            self._write(p, got)
        return got

    def minutes(self, sym: str, d: date) -> Optional[pd.DataFrame]:
        p = self.root / "minutes" / d.isoformat() / f"{sym.replace('/', '_')}.json"
        got = self._read(p)
        if got is None:
            if self.offline:
                self.stats["minutes_offline_miss"] += 1
                return None
            df = self._fm(sym, d)
            self.stats["minutes_fetch"] += 1
            if df is None:
                self.stats["minutes_failed"] += 1
                return None
            got = frame_to_json(df)
            self._write(p, got)
        else:
            self.stats["minutes_hit"] += 1
        return json_to_frame(got)


def frame_to_json(df: pd.DataFrame) -> dict:
    if df is None or len(df) == 0:
        return {"t": [], "o": [], "h": [], "l": [], "c": [], "v": []}
    return {"t": [int(pd.Timestamp(t).value // 1_000_000) for t in df.index],
            "o": df["open"].astype(float).tolist(), "h": df["high"].astype(float).tolist(),
            "l": df["low"].astype(float).tolist(), "c": df["close"].astype(float).tolist(),
            "v": (df["volume"].astype(float).fillna(0.0).tolist() if "volume" in df.columns else [0.0] * len(df))}


def json_to_frame(obj: dict) -> pd.DataFrame:
    """The cache's JSON → the loader's shape: naive-UTC index (minute START), OHLCV + the session tag."""
    from daytrading.data import _classify_session
    idx = pd.to_datetime(obj.get("t") or [], unit="ms")
    df = pd.DataFrame({"open": obj.get("o") or [], "high": obj.get("h") or [], "low": obj.get("l") or [],
                       "close": obj.get("c") or [], "volume": obj.get("v") or []}, index=idx, dtype=float)
    df.index.name = "ts_utc"
    df["session"] = [_classify_session(ts) for ts in df.index]
    return df.sort_index()


def sessions_back(end: date, n: int, cache: Cache, *, start: Optional[date] = None) -> list:
    """[(session, grouped rows)] oldest first: market days back from `end` whose grouped call returned rows (an empty
    answer = a holiday the calendar does not list — skipped), `n` of them (or back to `start`), plus ONE extra session
    in front for the first day's prior close. A failed call stops the walk (re-run fills the cache)."""
    out, d, guard = [], end, 0
    need = None if start else n + 1
    while guard < 4000:
        guard += 1
        if is_market_day(d):
            rows = cache.grouped(d)
            if rows is None:
                log.warning("grouped %s missing — stopping the walk there", d)
                break
            if rows:
                out.append((d, rows))
                if need is not None and len(out) >= need:
                    break
                if start is not None and d < start:
                    break
        d = d - timedelta(days=1)
    return list(reversed(out))


def default_end(now_et: datetime) -> date:
    """The last COMPLETED session: today once its after-hours have closed, else the market day before."""
    today = now_et.date()
    if is_market_day(today) and now_et >= session_bounds(today)["ah_close"]:
        return today
    return prev_market_day(today)


def knobs_snapshot() -> dict:
    """Every constant the run used (re-runs compare against it)."""
    out = {}
    for name in dir(GC):
        if name.isupper():
            v = getattr(GC, name)
            if isinstance(v, (int, float, str, bool, type(None))):
                out[name] = v
            elif isinstance(v, (tuple, list, frozenset, set)):
                out[name] = sorted(v) if isinstance(v, (frozenset, set)) else list(v)
    return out


def half_day_unlisted(d: date) -> bool:
    """An NYSE early close the calendar does not know yet: `rth_close_time` would grade it as a 16:00 day."""
    return d.isoformat() in HALF_DAYS_UNLISTED and rth_close_time(d) == ET_RTH_CLOSE


def run(*, end: date, sessions: int, start: Optional[date], cache: Cache, rules, scope: str = DEFAULT_Q_SCOPE,
        only: Optional[set] = None, draws: int = BOOT_DRAWS, types: Optional[dict] = None,
        dated_types: bool = True, progress: Optional[Callable] = None) -> dict:
    """The whole study. -> {events, placebo, report, report_known_types, counts, window, sessions, skipped_half_days,
    half_days_unchecked}. `dated_types` = ask the dated reference lookup for a name the map does not type."""
    days = sessions_back(end, sessions, cache, start=start)
    events, pools, counts = [], defaultdict(list), Counter()
    skipped_half: list = []
    for (pd_day, prev_rows), (d, rows) in zip(days, days[1:]):
        if start is not None and d < start:
            continue
        if half_day_unlisted(d):
            skipped_half.append(d.isoformat())
            continue
        memo: dict = {}

        def resolve(sym, _d=d, _memo=memo):
            if sym not in _memo:
                counts["type_dated_lookups"] += 1
                _memo[sym] = cache.ticker_type(sym, _d)
                counts["type_dated_found"] += bool(_memo[sym])
            return _memo[sym]

        unknown: set = set()
        names = superset(rows, prev_rows, types, resolve=resolve if dated_types else None, unknown=unknown)
        counts["sessions"] += 1
        counts["superset"] += len(names)
        counts["type_unknown_kept"] += len(unknown)
        for sym, prev_close in names:
            if only and sym not in only:
                continue
            raw_today = cache.minutes(sym, d)
            if raw_today is None or len(raw_today) == 0:
                counts["no_bars"] += 1
                continue
            raw_prev = cache.minutes(sym, pd_day)
            try:
                res = study_symbol_day(sym, d, raw_prev, raw_today, prev_close, scope=scope, rules=rules)
            except Exception as exc:                                # noqa: BLE001 — one name never sinks the run
                log.warning("study %s %s failed: %s", sym, d, exc)
                counts["failed"] += 1
                continue
            if res["q_t"] is None:
                counts["never_listed"] += 1
                continue
            counts["listed"] += 1
            known = sym not in unknown
            counts["listed_type_unknown"] += not known
            for k, v in res["suppressed"].items():
                counts[k] += v
            events.extend(dict(e, type_known=known) for e in res["events"])
            for row in res["pool"]:
                pools[(row["session"], row["window"])].append(dict(row, type_known=known))
            counts["setup_free_names"] += bool(res["setup_free"])
            counts["live_only_break_names"] += bool(res["live_break"] and not res["events"] and scope != "live")
            counts["events_so_far"] = len(events)
        if progress:
            progress(d, counts)
    placebo, missing = sample_placebo(events, pools)
    counts["placebo_missing"] = missing
    counts["events"] = len(events)
    counts["placebo_rows"] = len(placebo)
    ev_k = [e for e in events if e["type_known"]]
    pools_k = {k: [r for r in v if r["type_known"]] for k, v in pools.items()}
    placebo_k, missing_k = sample_placebo(ev_k, pools_k)
    counts["events_type_known"], counts["placebo_rows_type_known"] = len(ev_k), len(placebo_k)
    counts["placebo_missing_type_known"] = missing_k
    got = max(len(days) - 1, 0)
    window = [days[1][0].isoformat() if len(days) > 1 else None, days[-1][0].isoformat() if days else None]
    return {"events": events, "placebo": placebo, "counts": dict(counts), "window": window,
            "sessions": {"requested": None if start else sessions, "got": got, "studied": counts["sessions"],
                         "short": (start is None and got < sessions)},
            "skipped_half_days": skipped_half,
            "half_days_unchecked": bool(window[0] and window[0] < HALF_DAYS_CHECKED_FROM),
            "report": build_report(events, placebo, rules, draws=draws),
            "report_known_types": build_report(ev_k, placebo_k, rules, draws=draws)}


def _md_table(report: dict, rules) -> list:
    lines = ["| setup | exit | n | dates | syms | mean R [date CI] [sym CI] | median R | win | stop-out | "
             "median MFE | placebo mean R | Δ mean R [date CI] [sym CI] | verdict |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for setup, by in report["by_setup"].items():
        for rule in rules:
            c = by[rule]
            e, p = c["events"], c["placebo"]
            lines.append(f"| {setup} | {rule} | {e['n']} | {e['dates']} | {e['symbols']} | {e['mean_r']} "
                         f"{e['ci_date']} {e['ci_symbol']} | {e['median_r']} | {e['win_rate']} | {e['stop_rate']} | "
                         f"{e['median_mfe_r']} | {p['mean_r']} | {c['delta_mean_r']} {c['delta_ci_date']} "
                         f"{c['delta_ci_symbol']} | {c['verdict']} |")
    return lines


def render_md(result: dict, rules) -> str:
    ss = result.get("sessions") or {}
    c = result.get("counts") or {}
    head = [f"sessions requested {ss.get('requested')} · got {ss.get('got')} · studied {ss.get('studied')}"
            + (" · **SHORT WALK — a grouped call failed; re-run to fill the cache**" if ss.get("short") else ""),
            f"half days skipped (not in timeframes.HALF_DAYS): {result.get('skipped_half_days') or 'none'}"
            + (f" · **window starts before {HALF_DAYS_CHECKED_FROM}: earlier half days unchecked**"
               if result.get("half_days_unchecked") else ""),
            f"listed names typed 'unknown' (kept, round A): {c.get('listed_type_unknown', 0)} · dated type lookups "
            f"{c.get('type_dated_lookups', 0)}, typed {c.get('type_dated_found', 0)}", ""]
    lines = head + _md_table(result["report"], rules)
    if "report_known_types" in result:
        lines += ["", "With 'type unknown' names dropped (events and placebo):", ""] + \
            _md_table(result["report_known_types"], rules)
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gajjala setups forward study (WP6) — read-only, own file cache.")
    ap.add_argument("--start", type=date.fromisoformat, default=None)
    ap.add_argument("--end", type=date.fromisoformat, default=None)
    ap.add_argument("--sessions", type=int, default=GC.STUDY_SESSIONS)
    ap.add_argument("--exit", choices=list(GC.STUDY_EXIT_RULES) + ["all"], default="all")
    ap.add_argument("--q-scope", choices=Q_SCOPES, default=DEFAULT_Q_SCOPE)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--symbols", default="", help="comma list — a smoke run only")
    ap.add_argument("--draws", type=int, default=BOOT_DRAWS)
    ap.add_argument("--offline", action="store_true", help="cache only, no HTTP")
    ap.add_argument("--no-types", action="store_true", help="skip the reference type map (every name 'type unknown')")
    ap.add_argument("--force", action="store_true", help="run inside 09:30–16:00 ET anyway")
    ap.add_argument("--allow-short", action="store_true", help="exit 0 even when fewer sessions came back than asked")
    a = ap.parse_args(argv)
    now_et = datetime.now(ET)
    if refused_window(now_et) and not a.force:
        print(f"refused: {now_et:%H:%M} ET is inside the regular session — run after 16:00 ET or pass --force",
              file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    rules = tuple(GC.STUDY_EXIT_RULES) if a.exit == "all" else (a.exit,)
    try:
        cache = Cache(a.cache, offline=a.offline)
    except StaleCache as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    types = None
    if not a.no_types and not a.offline:
        types, complete, calls = SC.fetch_type_map()
        log.info("type map: %d symbols, complete=%s, %d calls", len(types), complete, calls)
    only = {s.strip().upper() for s in a.symbols.split(",") if s.strip()} or None
    t0 = time.time()
    res = run(end=a.end or default_end(now_et), sessions=a.sessions, start=a.start, cache=cache, rules=rules,
              scope=a.q_scope, only=only, draws=a.draws, types=types, dated_types=not a.no_types,
              progress=lambda d, c: log.info("%s listed=%d events=%d", d, c.get("listed", 0), c.get("events_so_far", 0)))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(res["events"]).to_csv(out / "events.csv", index=False)
    pd.DataFrame(res["placebo"]).to_csv(out / "placebo.csv", index=False)
    meta = {"argv": sys.argv, "run_at": now_et.isoformat(), "wall_s": round(time.time() - t0, 1),
            "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
            "q_scope": a.q_scope, "rules": rules, "draws": a.draws, "seed": BOOT_SEED, "min_clusters": MIN_CLUSTERS,
            "placebo_per_event": PLACEBO_PER_EVENT, "float_gate": STUDY_FLOAT["text"],
            "types": ("skipped" if types is None else len(types)), "cache": dict(cache.stats),
            "window": res["window"], "sessions": res["sessions"], "skipped_half_days": res["skipped_half_days"],
            "half_days_unchecked": res["half_days_unchecked"], "cache_layout": CACHE_LAYOUT,
            "counts": res["counts"], "knobs": knobs_snapshot()}
    (out / "report.json").write_text(json.dumps({"meta": meta, "report": res["report"],
                                                 "report_known_types": res["report_known_types"]},
                                                indent=1, default=str))
    md = render_md(res, rules)
    (out / "report.md").write_text(md + "\n")
    print(json.dumps({"window": res["window"], "sessions": res["sessions"], "counts": res["counts"]}, default=str))
    print(md)
    if res["sessions"]["short"] and not a.allow_short:
        print(f"short walk: {res['sessions']['got']} of {res['sessions']['requested']} sessions — re-run to fill the "
              f"cache, or pass --allow-short", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
