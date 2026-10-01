"""🛡️ Resiliency tab on Chart Maps (Ajay 2026-09-30).

The ask, verbatim: "Can you build me a new tab- Resileincy. This is to help me
with #1 - Stocks that are not going to by more than 0.5% during a T1 event like
FOMC or any others like todays Inflation and GDP track T2s as well. #3 - Tape
is positive and bullish EOD or Pre market. but volume has to be accounted for.
We have all of this data already."

WHAT IT READS
  * 🛡️ Held on T1 / T2 — the closed-bar event-day return (prior session close
    -> event session close) against `HOLD_MAX_DROP_PCT`, over the last
    `HOLD_WINDOW_DAYS` of T1 (T2-only) sessions. The data days are
    `macro_calendar.past_events` (FRED's own release dates, classified by the
    ONE classifier `_match_tier`, + the Fed's FOMC calendar). The box = a close
    on every window session AND held on at least `HOLD_RATE_MIN_PCT` of them.
    The name's σ and β ride on every card — a quiet name holds by construction.
  * 📅 Today — on a T1/T2 session, the one live print (`KL.anchor_read`)
    against the VERIFIED prior close (`KL.verify_last`). A name with no print
    today is `no_print`, never "holding +0.00%".
  * 📈 Bullish tape EOD — the app's accumulation day (`sepa.volume.
    accumulation_day`, the one engine) on the last closed session, the average
    = `momentum_burst.avg_volume_before`; after the close-confirm minute,
    today's snapshot day bar.
  * 🌅 Bullish tape pre-market — a fresh pre-market print above the verified
    prior close on at least `PM_RVOL_MIN` (the app's 1.5x bar) x the name's own
    mean cumulative pre-market volume by the same ET minute, over its cached
    `intraday_cache` sessions (at least `PM_BASELINE_MIN_SESSIONS`). Live
    04:00–09:30 ET only. The volume leg is OFF while `PM_VOLUME_VERIFIED` is
    False (his call, fix round 2026-09-30: `min.av` and the 1-minute bars
    disagree) — the read is `volume_unverified` and the box passes none.

THE MEMO is the 🏔️ ATH tab's: the closed-bar half is built once per
`levels_session` in a background thread (the macro calendar is read THERE,
never on a request); every request ranks it against ONE universe snapshot.
The boxes are the 🏎️ Dual Momentum filter machinery (`DMT.passes` /
`DMT.parse_mode`, ANY by default, "must match all").

DISPLAY ONLY and UNMEASURED: nothing here gates a scan, pushes a phone, sizes
a position or enters a lane. The persistence study is
`backend/scripts/resiliency_study.py`; its verdict literal lives in
`chart_maps.resiliency_measured` (read lazily). Writes nothing.
"""
from __future__ import annotations

import copy
import logging
import math
import statistics
import threading
import time
from bisect import bisect_left
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import macro_calendar
from chart_maps import dual_momentum_tab as DMT
from sepa import breakout_audit, universe
from sepa import volume as V
from supply_demand import key_levels as KL
from supply_demand import momentum_burst as MB

log = logging.getLogger("chart_maps.resiliency_tab")

MARK = "\U0001F6E1️"                 # 🛡️ (VS16 — FE literals must match byte for byte)
TODAY_MARK = "\U0001F4C5"                 # 📅
EOD_MARK = "\U0001F4C8"                   # 📈
PRE_MARK = "\U0001F305"                   # 🌅
MEASURED_DEFAULT = {"status": "pending"}  # fallback when chart_maps.resiliency_measured is absent
MEASURED = False
HOLD_MAX_DROP_PCT = 0.5        # HIS NUMBER (ask: "more than 0.5%"); down-only reading = HIS CALL #1
HOLD_WINDOW_DAYS = 365         # HIS CALL #4 — "the last 12 months" of event sessions
HOLD_RATE_MIN_PCT = 75.0       # HIS CALL #5 — the 🛡️ box cut (display cut-off, not a rule)
T2_EXCLUDES_T1_DAYS = True     # HIS CALL #7 — a session with any T1 print is T1 only
PM_BASELINE_MIN_SESSIONS = 5   # HIS CALL #12 — data sufficiency for the pre-market baseline
# HIS CALL (fix round 2026-09-30): the snapshot's pre-market shares (`min.av`) and
# the cached 1-minute bars the usual volume is built from are different sources,
# and `min.av` read +11% to +13% above the summed 1-minute pre-market bars for
# NVDA / AAPL / MU (read-only probe 2026-09-30 09:19 ET, table in
# docs/chart_maps/resiliency_tab_2026_09_30.md) — the spec's 2% STOP check failed.
# Until Ajay decides (a like-for-like source, or accept and say so), the volume
# leg is NOT compared: the 🌅 read serves `volume_unverified`, `bullish` None, the
# box passes none, and the baseline aggregation is not run.
PM_VOLUME_VERIFIED = False
PM_SLOT_MIN = 10               # aggregation granularity (UTC "HH:M" bucket) — representation, not a rule
PM_OPEN_MIN = KL.SESSION_START.hour * 60 + KL.SESSION_START.minute      # 04:00 ET, derived, never typed
PM_CLOSE_MIN = KL.PRE_FROZEN_AT.hour * 60 + KL.PRE_FROZEN_AT.minute      # 09:30 ET
PM_SLOTS = (PM_CLOSE_MIN - PM_OPEN_MIN) // PM_SLOT_MIN                   # 33
INTRADAY_COLL = "intraday_cache"  # daytrading/data.py's collection name (test-pinned against that file)
MEMO_TTL_SEC = 60 * 60         # cache freshness, NOT a rule
FAIL_RETRY_SEC = 5 * 60        # retry cadence, NOT a rule
BENCH = universe.BENCHMARK     # "SPY" (import, never the literal)
PM_RVOL_MIN = MB.BURST_RVOL_MIN          # the app's 1.5x bar (import)
PCT_DP = MB.PCT_DP                        # 2
VOL_AVG_BARS = breakout_audit.VOL_AVG_BARS  # 50 (σ window and the volume average)
BETA_BARS = KL.YEAR_BARS                  # 252
FILTER_PARAM, FILTER_MODE_PARAM = "res", "res_mode"
FILTER_KEYS = ("t1", "t2", "eod", "pre")  # canonical order; FE RES_FILTER_KEYS pinned equal by contract
FILTER_LABELS = {"t1": MARK + " Held on T1", "t2": MARK + " Held on T2",
                 "eod": EOD_MARK + " Bullish tape EOD", "pre": PRE_MARK + " Bullish tape pre-market"}
SORT_T2, SORT_DOWN, SORT_TODAY = "res_t2", "res_down", "res_today"
TAB_SORTS = (SORT_T2, SORT_DOWN, SORT_TODAY)
DEFAULT_SORT_KEY = "default"              # == board.DEFAULT_SORT (test-pinned; no board import here)
DEFAULT_SORT_LABEL = MARK + " T1 hold rate"
T2_SORT_LABEL = MARK + " T2 hold rate"
DOWN_SORT_LABEL = MARK + " T1 on SPY-down days"
TODAY_SORT_LABEL = TODAY_MARK + " Today's move"
T1_BADGE_FMT = MARK + " T1 held {held}/{n} ({rate:.0f}%)"          # IDENT rung (FE prefix "🛡️ T1 held")
TODAY_HOLD_FMT = TODAY_MARK + " T{tier} today · holding {move:+.2f}%"   # PRICE rung
TODAY_DOWN_FMT = TODAY_MARK + " T{tier} today · down {move:+.2f}%"
TODAY_SORT_UNAVAILABLE = ("Today is not a T1 or T2 data day — the board is in T1 "
                          "hold-rate order.")
EVENT_SOURCES = ("FRED release dates", "Federal Reserve FOMC calendar")
MODE_ANY, MODE_ALL = DMT.MODE_ANY, DMT.MODE_ALL
MODE_ALL_LABEL = DMT.MODE_ALL_LABEL
FILTER_MODE_DEFAULT = DMT.FILTER_MODE_DEFAULT

_TAPE_WORD = {"premarket": "pre-market", "rth": "live", "afterhours": "after-hours"}
# A read with no fresh print is priced off the snapshot's day bar: during RTH that
# bar is still forming, so it is labelled intraday; "day close" only once the
# session has closed (KL.phase "close"). Follow-up 2026-09-30.
DAY_BAR_BASIS = "day_bar"
DAY_BAR_WORD = "day bar (intraday)"
DAY_CLOSE_WORD = "day close"
_KIND_LABEL = {}
for _needle, (_k, _t, _lab) in macro_calendar._RELEASE_TIERS:
    _KIND_LABEL.setdefault(_k, _lab)


# ---------------------------------------------------------------------------
# served words (built from the constants)
# ---------------------------------------------------------------------------
NOTE_UNMEASURED = (MARK + " UNMEASURED — no study in this app yet says a name that held on "
                   "past T1 days holds on the next one, and a quiet, low-volatility name holds "
                   "most days by construction — its typical daily move and beta are on every "
                   "card.")
PRE_UNVERIFIED_TEXT = ("pre-market volume not compared — the snapshot's pre-market shares "
                       "read higher than the 1-minute bars the usual volume is built from; "
                       "your call")
# Follow-up 2026-09-30: while PM_VOLUME_VERIFIED is False no served sentence may
# promise the pre-market volume bar — the 🌅 box says it is off, in one line.
PRE_OFF_REASON = "volume check off until the two volume sources are reconciled"
PRE_OFF_LINE = (f"{PRE_MARK} Bullish tape pre-market: {PRE_OFF_REASON} — the box passes "
                "none; each card still shows its pre-market move.")


def _note_tail() -> str:
    """The note's tail, built from PM_VOLUME_VERIFIED at call time: the
    pre-market volume bar is named only while that leg is compared."""
    tape = (f" The tape reads are the app's own definitions (the accumulation day; the "
            f"{PM_RVOL_MIN:g}× volume bar)." if PM_VOLUME_VERIFIED else
            " The EOD tape read is the app's own accumulation day; the pre-market "
            + PRE_OFF_REASON + ".")
    return tape + " Nothing here gates a scan, pushes a phone, sizes a position or enters a lane. Not advice."


NOTE_TAIL = _note_tail()
NOTE = NOTE_UNMEASURED + NOTE_TAIL
WARMING_NOTE = (MARK + " Reading every name's closes on the last year's T1 and T2 days from the "
                "cached daily bars — the charts appear here as soon as it lands; you don't "
                "need to refresh.")
ERROR_NOTE_FMT = (MARK + " The Resiliency board could not be built ({reason}). It is retried "
                  "every {mins} minutes — this is not a warming state.")
EMPTY_NOTE = (MARK + " No name clears the liquidity floor with a read right now — the line "
              "above says where they went.")
FILTER_EMPTY_ANY_FMT = (MARK + " No name passes any ticked box ({labels}) — tick another box "
                        "to see more; the line above says how many each box passed.")
FILTER_EMPTY_FMT = (MARK + " No name passes every ticked box ({labels}) — untick one to see "
                    "more; the line above says how many each box hid.")
FILTERS_NOTE_ANY = ("Ticked boxes narrow the board — a name passing ANY ticked box shows, "
                    "with a badge for each ticked box it passes; tick “must match all” "
                    "to need every one. They sort nothing, push nothing, gate nothing and enter "
                    "no lane.")
FILTERS_NOTE_ALL = ("Ticked boxes narrow the board — every ticked box must pass. They sort "
                    "nothing, push nothing, gate nothing and enter no lane.")
EVENTS_LINE = ("Data days: FRED's own release dates (jobs report, CPI, Core PCE, GDP, retail "
               "sales, JOLTS, ADP, jobless claims, PPI) and the Fed's FOMC calendar. ISM and "
               "Fed-speaker remarks have no dated history here and are not counted.")
PRE_NOT_OPEN_TEXT = "Read 04:00–09:30 ET only — not a pre-market session now."


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _f(v) -> Optional[float]:
    """A finite plain float, else None (numpy scalars and NaN/inf never leak)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _pos(v) -> Optional[float]:
    x = _f(v)
    return x if x is not None and x > 0 else None


def _r(v, dp: int = PCT_DP) -> Optional[float]:
    x = _f(v)
    return None if x is None else float(round(x, dp))


def _n(x) -> str:
    return f"{int(x or 0):,}"


def _safe_reason(exc: BaseException) -> str:
    s = str(exc)
    if not s or "api_key" in s or "apikey" in s.lower():
        return type(exc).__name__
    return s[:200]


def _iso(d) -> str:
    return (d.isoformat() if hasattr(d, "isoformat") else str(d))[:10]


def session_for(now: datetime) -> date:
    return KL.levels_session(now)


def _ukey(universe_name) -> str:
    from chart_maps import key_levels_tab as KLT
    return KLT._ukey(universe_name)


# ---------------------------------------------------------------------------
# PURE functions (the study imports these)
# ---------------------------------------------------------------------------
def pct_ret(close, prev_close) -> Optional[float]:
    """round((c/p - 1) * 100, PCT_DP); None unless both finite > 0."""
    c, p = _pos(close), _pos(prev_close)
    if c is None or p is None:
        return None
    v = (c / p - 1.0) * 100.0
    return float(round(v, PCT_DP)) if math.isfinite(v) else None


def held(ret_pct, max_drop_pct: float = HOLD_MAX_DROP_PCT) -> Optional[bool]:
    """ret >= -max_drop (inclusive); None -> None."""
    r = _f(ret_pct)
    if r is None:
        return None
    return bool(r >= -float(max_drop_pct))


def day_iso(ts) -> str:
    """The normalized ET date of an index stamp (00:00 / 04:00 stamps safe;
    a tz-aware stamp is converted to ET first)."""
    import pandas as pd
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("America/New_York").tz_localize(None)
    return t.date().isoformat()


def closes_by_day(frame) -> dict:
    """{iso: close} — finite > 0 closes only (a later duplicate day wins)."""
    if frame is None or len(frame) == 0:
        return {}
    idx = KL._norm_index(frame)
    out: dict = {}
    for d, c in zip(idx, frame["close"].tolist()):
        v = _pos(c)
        if v is not None:
            out[d.date().isoformat()] = v
    return out


def _first_day_on_or_after(trading_days: list, iso: str) -> Optional[str]:
    i = bisect_left(trading_days, iso)
    return trading_days[i] if i < len(trading_days) else None


def event_sessions(events: list, trading_days: list, *, start: date, end: date,
                   t2_excludes_t1: bool = T2_EXCLUDES_T1_DAYS) -> dict:
    """{"t1": {iso: {"labels", "kinds", "release_dates"}}, "t2": {...}}, each
    ordered by iso. Each event maps to the FIRST trading day on or after its
    date (a Good-Friday jobs report reacts on Monday); a session is kept when
    start <= session < end (end = today's session, exclusive). With
    `t2_excludes_t1`, a session that carries any T1 print is T1 only."""
    days = sorted(str(d)[:10] for d in (trading_days or []))
    s_iso, e_iso = _iso(start), _iso(end)
    out = {"t1": {}, "t2": {}}
    for ev in events or []:
        if not isinstance(ev, dict):
            continue
        tier = ev.get("tier")
        if tier not in (1, 2):
            continue
        d = str(ev.get("date") or "")[:10]
        if len(d) != 10:
            continue
        sess = _first_day_on_or_after(days, d)
        if sess is None or not (s_iso <= sess < e_iso):
            continue
        slot = out["t1" if tier == 1 else "t2"].setdefault(
            sess, {"labels": [], "kinds": [], "release_dates": []})
        lab, kind = str(ev.get("label") or ev.get("kind") or ""), str(ev.get("kind") or "")
        if lab and lab not in slot["labels"]:
            slot["labels"].append(lab)
        if kind and kind not in slot["kinds"]:
            slot["kinds"].append(kind)
        if d not in slot["release_dates"]:
            slot["release_dates"].append(d)
    if t2_excludes_t1:
        for iso in list(out["t2"]):
            if iso in out["t1"]:
                out["t2"].pop(iso)
    return {k: {iso: v[iso] for iso in sorted(v)} for k, v in out.items()}


def t2_on_t1(events: list, trading_days: list, *, start: date, end: date) -> dict:
    """{t2 kind: {"n": sessions, "t1_labels": [...]}} — the T2 prints that fell
    on a session carrying a T1 print and are therefore counted as T1 only
    (T2_EXCLUDES_T1_DAYS). Empty when T2 keeps those days. Follow-up
    2026-09-30: a T2 kind whose every print landed on a T1 day otherwise reads
    as absent from the header."""
    if not T2_EXCLUDES_T1_DAYS:
        return {}
    both = event_sessions(events, trading_days, start=start, end=end, t2_excludes_t1=False)
    out: dict = {}
    for iso, meta in both["t2"].items():
        t1 = both["t1"].get(iso)
        if t1 is None:
            continue
        for k in meta.get("kinds") or []:
            slot = out.setdefault(k, {"n": 0, "t1_labels": []})
            slot["n"] += 1
            for lab in t1.get("labels") or []:
                if lab not in slot["t1_labels"]:
                    slot["t1_labels"].append(lab)
    return out


def event_returns(closes: dict, trading_days: list, sessions) -> dict:
    """{iso: ret | None}. prev = the trading day before in the BENCH calendar;
    None if either close is missing (no gap-bridging)."""
    days = sorted(str(d)[:10] for d in (trading_days or []))
    pos = {d: i for i, d in enumerate(days)}
    closes = closes if isinstance(closes, dict) else {}
    out: dict = {}
    for iso in (sessions or {}):
        i = pos.get(iso)
        if i is None or i == 0:
            out[iso] = None
            continue
        out[iso] = pct_ret(closes.get(iso), closes.get(days[i - 1]))
    return out


def tier_stats(rets: dict, sessions: dict, bench_rets: dict, *, tier: int) -> Optional[dict]:
    """TierStats, or None when there are no sessions. `rated` = a close on
    every session; rates are None when n == 0; the down_* subset = sessions
    where the benchmark's own event-day return is below zero."""
    sessions = sessions or {}
    if not sessions:
        return None
    rets = rets if isinstance(rets, dict) else {}
    bench_rets = bench_rets if isinstance(bench_rets, dict) else {}
    isos = list(sessions)
    read = [(iso, rets.get(iso)) for iso in isos if _f(rets.get(iso)) is not None]
    n = len(read)
    n_held = sum(1 for _i, r in read if held(r))
    down = [iso for iso in isos if (_f(bench_rets.get(iso)) is not None
                                    and float(bench_rets[iso]) < 0)]
    down_read = [(iso, rets.get(iso)) for iso in down if _f(rets.get(iso)) is not None]
    down_n = len(down_read)
    down_held = sum(1 for _i, r in down_read if held(r))

    def _labels(iso):
        return list((sessions.get(iso) or {}).get("labels") or [])

    worst = None
    if read:
        wi, wr = min(read, key=lambda x: (float(x[1]), x[0]))
        worst = {"date": wi, "labels": _labels(wi), "ret_pct": _r(wr),
                 "spy_ret_pct": _r(bench_rets.get(wi))}
    li = isos[-1]
    lr = _f(rets.get(li))
    last = {"date": li, "labels": _labels(li), "ret_pct": _r(lr), "held": held(lr),
            "spy_ret_pct": _r(bench_rets.get(li))}
    return {"tier": int(tier), "events": len(isos), "n": n, "held": n_held,
            "rate_pct": _r(n_held / n * 100.0) if n else None,
            "rated": bool(n == len(isos)),
            "down_events": len(down), "down_n": down_n, "down_held": down_held,
            "down_rate_pct": _r(down_held / down_n * 100.0) if down_n else None,
            "median_ret_pct": _r(statistics.median([float(r) for _i, r in read])) if read else None,
            "worst": worst, "last": last}


def box_pass(stats, min_rate_pct: float = HOLD_RATE_MIN_PCT) -> Optional[bool]:
    """None when stats is None or not rated; else held / n >= the cut (exact,
    not the rounded rate)."""
    if not isinstance(stats, dict) or not stats.get("rated"):
        return None
    n = int(stats.get("n") or 0)
    if n <= 0:
        return None
    return bool(int(stats.get("held") or 0) * 100.0 >= float(min_rate_pct) * n - 1e-9)


def _daily_rets(closes: dict, days: list) -> list:
    out = []
    for a, b in zip(days[:-1], days[1:]):
        out.append(pct_ret(closes.get(b), closes.get(a)))
    return out


def sigma_pct(closes: dict, trading_days: list, *, bars: int = VOL_AVG_BARS) -> Optional[float]:
    """Sample stdev of the last `bars` daily % returns on the BENCH calendar;
    None unless every one of them is read (no gap-bridging)."""
    days = sorted(str(d)[:10] for d in (trading_days or []))
    if len(days) < bars + 1:
        return None
    rets = _daily_rets(closes or {}, days[-(bars + 1):])
    if len(rets) != bars or any(r is None for r in rets) or bars < 2:
        return None
    v = statistics.stdev(rets)
    return _r(v)


def beta(closes: dict, bench_closes: dict, trading_days: list, *,
         bars: int = BETA_BARS) -> Optional[float]:
    """cov / var of the last `bars` daily returns against the benchmark's;
    None unless every pair is read or the benchmark never moved."""
    days = sorted(str(d)[:10] for d in (trading_days or []))
    if len(days) < bars + 1 or bars < 2:
        return None
    win = days[-(bars + 1):]
    x = _daily_rets(closes or {}, win)
    y = _daily_rets(bench_closes or {}, win)
    if any(v is None for v in x) or any(v is None for v in y):
        return None
    mx, my = sum(x) / len(x), sum(y) / len(y)
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    var = sum((b - my) ** 2 for b in y)
    if var <= 0:
        return None
    return _r(cov / var)


def eod_read(bar: Optional[dict], prev_close, avg_vol, *, date_iso, source) -> dict:
    """EodRead. bullish = `V.accumulation_day` (the one engine); a flat bar is
    a read that is not one (False); an unread leg -> bullish None."""
    out = {"state": "no_bars", "date": date_iso, "source": source, "chg_pct": None,
           "close_loc_pct": None, "volume": None, "avg_vol_50": None, "rvol": None,
           "up": None, "upper_half": None, "vol_ok": None, "bullish": None}
    b = bar if isinstance(bar, dict) else {}
    c, h, lo, p = _pos(b.get("close")), _pos(b.get("high")), _pos(b.get("low")), _pos(prev_close)
    if c is None or h is None or lo is None or p is None or h < lo:
        return out
    out["chg_pct"] = pct_ret(c, p)
    out["up"] = bool(c > p)
    if h == lo:
        out.update(state="flat_bar", bullish=False)
        return out
    loc = (c - lo) / (h - lo)
    out["close_loc_pct"] = _r(loc * 100.0)
    out["upper_half"] = bool(loc >= 0.5)
    v = _pos(b.get("volume"))
    if v is None:
        out["state"] = "no_volume"
        return out
    out["volume"] = int(round(v))
    a = _pos(avg_vol)
    if a is None:
        out["state"] = "no_avg"
        return out
    out.update(state="read", avg_vol_50=_r(a, 0), rvol=_r(v / a),
               vol_ok=bool(v > a),
               bullish=bool(V.accumulation_day(c, p, h, lo, v, a)))
    return out


def _utc_bucket_to_slot(d_iso: str, h: str) -> Optional[int]:
    """UTC "HH:M" (10-minute) bucket on day d -> the ET pre-market slot index,
    with THAT date's offset (DST safe). None outside 04:00–09:30 ET."""
    try:
        hh, m = str(h).split(":")
        dt = datetime(*[int(x) for x in d_iso.split("-")], int(hh), int(m) * 10,
                      tzinfo=timezone.utc).astimezone(KL.ET)
    except (TypeError, ValueError):
        return None
    if dt.date().isoformat() != d_iso:
        return None
    mins = dt.hour * 60 + dt.minute
    if mins < PM_OPEN_MIN or mins >= PM_CLOSE_MIN:
        return None
    return int((mins - PM_OPEN_MIN) // PM_SLOT_MIN)


def _starts_before_open(d_iso: str, first_ts) -> bool:
    """True when a cached day's FIRST bar (`ts_utc`, a naive UTC ISO string)
    is before that day's 09:30 ET open — the day was cached from the
    pre-market on, so a pre-market with no volume is a real zero. False on a
    missing / unparseable stamp (unknown is never counted as a zero)."""
    if not first_ts:
        return False
    try:
        dt = datetime.fromisoformat(str(first_ts).replace("Z", "+00:00"))
        y, m, dd = (int(x) for x in d_iso.split("-"))
    except (TypeError, ValueError):
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    open_et = datetime(y, m, dd, PM_CLOSE_MIN // 60, PM_CLOSE_MIN % 60, tzinfo=KL.ET)
    return dt < open_et


def pm_slots(agg_rows: list, docs: list, *, session: date, dates: list) -> dict:
    """agg_rows = [{"_id": {"s","d","h"}, "v"}], docs = [(sym, date[, first_ts_utc])]
    that exist -> {SYM: {"sessions": n, "slot_mean": [PM_SLOTS floats]}}.

    A cached day counts as a baseline session ONLY when it holds pre-market
    rows, or its first bar is before the 09:30 ET open (a real zero-volume
    pre-market). A regular-session-only day (first bar at/after 09:30 ET, or
    no first stamp) is SKIPPED, never a zero: 10,893 of 55,334 cached docs in
    the 50-session window had no pre-market bars (probe 2026-09-30, e.g. BNY
    2026-07-28 = 390 bars from 09:30 ET), and counting them as zeros shrank
    the usual volume and inflated the pre-market ratio (~1.2x at the median
    affected name, ~2.1x at p90). Dates on or after `session` never count."""
    s_iso = session.isoformat()
    want = {str(d)[:10] for d in (dates or []) if str(d)[:10] < s_iso}
    listed: set = set()
    sess: dict = {}
    for sd in docs or []:
        try:
            sym, d = str(sd[0]).upper(), str(sd[1])[:10]
        except (TypeError, IndexError):
            continue
        if d not in want:
            continue
        listed.add((sym, d))
        first = sd[2] if len(sd) > 2 else None
        if _starts_before_open(d, first):
            sess.setdefault(sym, {}).setdefault(d, [0.0] * PM_SLOTS)
    for row in agg_rows or []:
        _id = (row or {}).get("_id") or {}
        sym, d = str(_id.get("s") or "").upper(), str(_id.get("d") or "")[:10]
        if (sym, d) not in listed:
            continue
        sess.setdefault(sym, {}).setdefault(d, [0.0] * PM_SLOTS)
        k = _utc_bucket_to_slot(d, _id.get("h"))
        v = _f((row or {}).get("v"))
        if k is None or v is None or v < 0:
            continue
        sess[sym][d][k] += v
    out = {}
    for sym, by_d in sess.items():
        n = len(by_d)
        mean = [float(sum(s[k] for s in by_d.values()) / n) for k in range(PM_SLOTS)]
        out[sym] = {"sessions": n, "slot_mean": mean}
    return out


def pm_baseline_at(slot_mean: list, minute_et: int) -> Optional[float]:
    """Cumulative mean pre-market volume from 04:00 ET to `minute_et` (linear
    inside a slot). None when nothing accumulated."""
    if not isinstance(slot_mean, (list, tuple)) or len(slot_mean) != PM_SLOTS:
        return None
    m = max(PM_OPEN_MIN, min(int(minute_et), PM_CLOSE_MIN))
    total = 0.0
    for k in range(PM_SLOTS):
        a = PM_OPEN_MIN + k * PM_SLOT_MIN
        if m >= a + PM_SLOT_MIN:
            total += float(slot_mean[k] or 0.0)
        elif m > a:
            total += float(slot_mean[k] or 0.0) * (m - a) / PM_SLOT_MIN
    return total if total > 0 and math.isfinite(total) else None


def _et_of_ms(ms) -> Optional[datetime]:
    x = _pos(ms)
    if x is None:
        return None
    sec = x / 1e9 if x > 1e15 else x / 1e3
    try:
        return datetime.fromtimestamp(sec, tz=KL.ET)
    except (OverflowError, OSError, ValueError):
        return None


def _print_as_of(row: Optional[dict]) -> Optional[str]:
    from sepa import prices
    ep = prices.extended_print(row) if isinstance(row, dict) else None
    if not ep:
        return None
    try:
        return datetime.fromtimestamp(float(ep["epoch"]), tz=KL.ET).strftime("%H:%M")
    except (KeyError, TypeError, ValueError, OverflowError, OSError):
        return None


def _pre_blank(state: str, text: str) -> dict:
    return {"state": state, "text": text, "move_pct": None, "print": None,
            "prev_close": None, "as_of_et": None, "pm_volume": None, "pm_dollar_vol": None,
            "baseline_vol": None, "baseline_sessions": None, "pm_rvol": None,
            "up": None, "vol_ok": None, "bullish": None}


def pre_read(raw: Optional[dict], *, ref_close, ref_date, now, session, phase,
             baseline: Optional[dict], baseline_state: str,
             volume_verified: Optional[bool] = None) -> dict:
    """PreRead. bullish = up AND pm_rvol >= PM_RVOL_MIN; any unread leg ->
    bullish None. `volume_verified` None -> `PM_VOLUME_VERIFIED`; False ->
    state `volume_unverified` (the volume leg is not compared, bullish None)."""
    verified = PM_VOLUME_VERIFIED if volume_verified is None else bool(volume_verified)
    if phase != "pre":
        return _pre_blank("not_open", PRE_NOT_OPEN_TEXT)
    row = KL.row_or_none(raw)
    if row is None:
        return _pre_blank("no_print", "No pre-market print yet.")
    stale, ok = KL.verify_last(ref_close, ref_date, row)
    if stale:
        return _pre_blank("stale", f"Not read — {stale}.")
    if not ok:
        return _pre_blank("no_print", "No pre-market print yet.")
    px = KL.fresh_print(row, now, session)
    if px is None:
        return _pre_blank("no_print", "No pre-market print yet.")
    prev = _pos(ref_close)
    out = _pre_blank("read", "")
    out.update(move_pct=pct_ret(px, prev), print=_r(px, 4), prev_close=_r(prev, 4),
               up=bool(px > prev))
    raw = raw if isinstance(raw, dict) else {}
    av = _pos(raw.get("min_av"))
    t_et = _et_of_ms(raw.get("min_t_ms"))
    if av is None or t_et is None or t_et.date() != session:
        out.update(state="no_volume", text=f"{out['move_pct']:+.2f}% · no pre-market "
                                            "volume in the snapshot yet")
        return out
    as_of = t_et + timedelta(minutes=1)
    out.update(pm_volume=int(round(av)), pm_dollar_vol=_r(av * px, 0),
               as_of_et=as_of.strftime("%H:%M"))
    if not verified:
        out.update(state="volume_unverified",
                   text=f"{out['move_pct']:+.2f}% · {PRE_UNVERIFIED_TEXT}")
        return out
    if baseline_state == "warming":
        out.update(state="baseline_warming",
                   text=f"{out['move_pct']:+.2f}% · the usual pre-market volume is loading")
        return out
    b = baseline if isinstance(baseline, dict) else {}
    n_s = int(b.get("sessions") or 0)
    out["baseline_sessions"] = n_s
    base = (pm_baseline_at(b.get("slot_mean"), as_of.hour * 60 + as_of.minute)
            if n_s >= PM_BASELINE_MIN_SESSIONS else None)
    if base is None:
        out.update(state="no_baseline",
                   text=(f"{out['move_pct']:+.2f}% · {n_s} cached pre-market "
                         f"session{'s' if n_s != 1 else ''} (needs "
                         f"{PM_BASELINE_MIN_SESSIONS}) — volume not compared"))
        return out
    rv = _r(av / base)
    out.update(baseline_vol=_r(base, 0), pm_rvol=rv, vol_ok=bool(rv >= PM_RVOL_MIN),
               bullish=bool(out["up"] and rv >= PM_RVOL_MIN))
    out["text"] = (f"{out['move_pct']:+.2f}% · vol {rv:.2f}× usual by "
                   f"{out['as_of_et']} ({n_s} sessions)")
    return out


def _today_blank(event: Optional[dict], state: str) -> dict:
    ev = event if isinstance(event, dict) else None
    return {"event_day": ev is not None, "tier": (ev or {}).get("tier"),
            "labels": list((ev or {}).get("labels") or []), "state": state,
            "move_pct": None, "holding": None, "print": None, "prev_close": None,
            "basis": None, "tape": None, "as_of_et": None}


def today_read(raw: Optional[dict], *, ref_close, ref_date, now, session, phase,
               event: Optional[dict]) -> dict:
    """TodayRead. `basis == "last_close"` is NEVER a read — a name with no
    print today is `no_print`, never "holding +0.00%"."""
    if not isinstance(event, dict):
        return _today_blank(None, "no_event")
    if phase is None:
        return _today_blank(event, "not_open")
    row = KL.row_or_none(raw)
    if row is None:
        return _today_blank(event, "no_print")
    stale, ok = KL.verify_last(ref_close, ref_date, row)
    if stale:
        return _today_blank(event, "stale")
    if not ok:
        return _today_blank(event, "no_print")
    px, basis, tape = KL.anchor_read(row, now, session, ref_close)
    if px is None or basis not in ("live", "day_close"):
        return _today_blank(event, "no_print")
    mv = pct_ret(px, ref_close)
    if mv is None:
        return _today_blank(event, "no_print")
    if basis == "day_close" and phase == "rth":
        basis = DAY_BAR_BASIS          # the day bar is still forming — not a close
    out = _today_blank(event, "read")
    out.update(move_pct=mv, holding=held(mv), print=_r(px, 4), prev_close=_r(ref_close, 4),
               basis=basis, tape=tape if basis == "live" else None,
               as_of_et=_print_as_of(row) if basis == "live" else None)
    return out


def tile_filter(res: dict) -> dict:
    """{"t1": box, "t2": box, "eod": eod.bullish, "pre": pre.bullish} — True
    passes, False fails, None = not read (a ticked box hides a None)."""
    res = res if isinstance(res, dict) else {}

    def _b(v):
        return v if isinstance(v, bool) else None
    return {"t1": box_pass(res.get("t1")), "t2": box_pass(res.get("t2")),
            "eod": _b((res.get("eod") or {}).get("bullish")),
            "pre": _b((res.get("pre") or {}).get("bullish"))}


def parse_filters(spec) -> tuple:
    """"EOD, t1,foo" -> ("t1", "eod"). Unknown tokens dropped; None / non-str /
    blank -> (). Canonical FILTER_KEYS order."""
    if not isinstance(spec, str) or not spec.strip():
        return ()
    toks = {t.strip().lower() for t in spec.replace("+", ",").split(",")}
    return tuple(k for k in FILTER_KEYS if k in toks)


def _tier_key(st, *, down_first: bool = False) -> tuple:
    st = st if isinstance(st, dict) else {}
    rated = bool(st.get("rated"))
    rate = _f(st.get("rate_pct")) or 0.0
    dr = _f(st.get("down_rate_pct"))
    w = st.get("worst") if isinstance(st.get("worst"), dict) else None
    wr = _f((w or {}).get("ret_pct"))
    worst = (0 if w is not None and wr is not None else 1, -(wr or 0.0))
    if down_first:
        return ((0 if rated and int(st.get("down_n") or 0) else 1, -(dr or 0.0), -rate) + worst)
    return ((0 if rated else 1, -rate, 0 if dr is not None else 1, -(dr or 0.0)) + worst)


def order_key(row: dict, sort: str) -> tuple:
    res = (row or {}).get("resiliency") or {}
    sym = str((row or {}).get("symbol") or "")
    if sort == SORT_T2:
        return _tier_key(res.get("t2")) + (sym,)
    if sort == SORT_DOWN:
        return _tier_key(res.get("t1"), down_first=True) + (sym,)
    if sort == SORT_TODAY:
        td = res.get("today") or {}
        mv = _f(td.get("move_pct"))
        return (0 if td.get("state") == "read" and mv is not None else 1, -(mv or 0.0), sym)
    return _tier_key(res.get("t1")) + (sym,)


# ---------------------------------------------------------------------------
# the study verdict (lazy; WP-STUDY owns the literal)
# ---------------------------------------------------------------------------
def _measured() -> dict:
    try:
        from chart_maps import resiliency_measured as RM
        m = getattr(RM, "MEASURED", None)
        return m if isinstance(m, dict) else dict(MEASURED_DEFAULT)
    except ImportError:
        return dict(MEASURED_DEFAULT)


_STUDY_PENDING_TEXT = {
    "t1": "UNMEASURED — the persistence study has not run yet.",
    "t2": "UNMEASURED — the persistence study has not run yet.",
    "eod": "UNMEASURED — the next-session study has not run yet.",
    "pre": "UNMEASURED — pre-market volume history is too short to measure.",
}
_VERDICTS = ("separates", "no_signal", "inverted", "too_small", "unmeasured")
# The verdict word in plain words (critic 2026-10-01): a T2 INVERTED read means the
# box names held LESS above their peers on data days than on ordinary days — a
# weaker hold, never a sell read. He acts on sell signals, so the page says so.
_TIER_GLOSS = {
    "separates": "the box holds better on data days than on ordinary days",
    "no_signal": "the box can't be told apart from an ordinary day",
    "inverted": "the box holds worse on data days than on ordinary days — a weaker hold, not a sell read",
    "too_small": "too few data days to read",
}


def _study_sentence(key: str, blk: dict, run_date) -> str:
    v = str(blk.get("verdict") or "unmeasured")
    if v == "unmeasured":
        why = blk.get("reason") or blk.get("text")
        return f"UNMEASURED — {why}" if why else _STUDY_PENDING_TEXT.get(key, "UNMEASURED.")
    head = f"MEASURED {run_date or ''}".strip()
    word = v.upper()
    lift, ci = _f(blk.get("lift_pp")), blk.get("ci")
    try:
        lo, hi = _f(ci[0]), _f(ci[1])
    except (TypeError, IndexError, KeyError):
        lo = hi = None
    if key in ("t1", "t2"):
        # The verdict reads the EVENT-SPECIFIC contrast (lift on the data day minus
        # lift on the next ordinary day, same resampled dates) — σ quintile x β
        # tercile alone does not remove the quiet-name confound (fix round
        # 2026-09-30), so the served words never claim "same-volatility" names.
        sp, sci = _f(blk.get("specific_pp")), blk.get("specific_ci")
        try:
            slo, shi = _f(sci[0]), _f(sci[1])
        except (TypeError, IndexError, KeyError):
            slo = shi = None
        pl = _f(blk.get("placebo_lift_pp"))
        if None not in (lift, pl, sp, slo, shi):
            n = blk.get("n_events")
            return (f"{head}: names that held on at least {HOLD_RATE_MIN_PCT:g}% of the last "
                    f"year's T{key[1]} days held on the next one {lift:+.1f}pp more often than "
                    f"other rated names grouped only by volatility quintile and beta tercile, "
                    f"and {pl:+.1f}pp more often on the next ordinary day; the data-day edge "
                    f"beyond ordinary days is {sp:+.1f}pp [{slo:+.1f}, {shi:+.1f}]"
                    + (f", {int(n)} data days" if _f(n) is not None else "")
                    + f" — {word}"
                    + (f": {_TIER_GLOSS[v]}." if v in _TIER_GLOSS else "."))
        return f"{head}: {word}."
    if key == "eod" and lift is not None and lo is not None and hi is not None:
        return (f"{head}: a volume-confirmed up close led the next session by {lift:+.2f}pp "
                f"against the same up close on lighter volume [{lo:+.2f}, {hi:+.2f}] — "
                f"{word}.")
    return f"{head}: {word}."


def study_block(measured: Optional[dict] = None) -> dict:
    m = measured if isinstance(measured, dict) else _measured()
    status = "measured" if m.get("status") == "measured" else "pending"
    out = {"status": status, "run_date": m.get("run_date") if status == "measured" else None}
    for k in FILTER_KEYS:
        blk = m.get(k) if (status == "measured" and isinstance(m.get(k), dict)) else {}
        v = str(blk.get("verdict") or "unmeasured")
        out[k] = {"verdict": v if v in _VERDICTS else "unmeasured",
                  "text": (_study_sentence(k, blk, out["run_date"]) if status == "measured"
                           else _STUDY_PENDING_TEXT[k])}
    return out


def note_text(study: Optional[dict] = None) -> str:
    s = study if isinstance(study, dict) else study_block()
    if s.get("status") == "measured" and isinstance(s.get("t1"), dict):
        return MARK + " " + str(s["t1"].get("text") or "") + _note_tail()
    return NOTE_UNMEASURED + _note_tail()


# ---------------------------------------------------------------------------
# rules + box notes (served; the FE prints them verbatim)
# ---------------------------------------------------------------------------
def rules_block() -> dict:
    lines = [
        (f"Held = the close on a data day no more than {HOLD_MAX_DROP_PCT:g}% under the prior "
         "session's close (prior close to that day's close — an intraday dip that "
         "recovers counts as held). Down-only, absolute, not against SPY: your call."),
        (f"{MARK} box = a close on every T1 (or T2) day of the last {HOLD_WINDOW_DAYS} days "
         f"and held on at least {HOLD_RATE_MIN_PCT:g}% of them. A name missing a close is "
         "not rated and a ticked box hides it."),
        ("T1 = the jobs report, CPI, Core PCE and the FOMC decision; T2 = retail sales, JOLTS, "
         "ADP, jobless claims, GDP and PPI"
         + (" — a day with any T1 print counts as T1 only." if T2_EXCLUDES_T1_DAYS
            else ".")),
        f"'SPY fell' = {BENCH}'s own close-to-close on that day below zero.",
        (f"{EOD_MARK} = the app's accumulation day on the last session: up close, close in the "
         f"upper half of the range, volume above its {VOL_AVG_BARS}-session average."),
        ((f"{PRE_MARK} = a fresh pre-market print above the prior close on at least "
          f"{PM_RVOL_MIN:g}× the name's own pre-market volume by the same minute, over at "
          f"least {PM_BASELINE_MIN_SESSIONS} cached sessions. 04:00–09:30 ET only.")
         if PM_VOLUME_VERIFIED else
         (f"{PRE_MARK} box is OFF: {PRE_OFF_REASON} ({PRE_UNVERIFIED_TEXT}) — it passes "
          "none; the pre-market move still shows 04:00–09:30 ET.")),
    ]
    return {"hold_max_drop_pct": float(HOLD_MAX_DROP_PCT),
            "hold_rate_min_pct": float(HOLD_RATE_MIN_PCT),
            "window_days": int(HOLD_WINDOW_DAYS), "t2_excludes_t1": bool(T2_EXCLUDES_T1_DAYS),
            "pre_rvol_min": float(PM_RVOL_MIN), "pre_min_sessions": int(PM_BASELINE_MIN_SESSIONS),
            "vol_avg_bars": int(VOL_AVG_BARS), "benchmark": BENCH, "lines": lines}


def box_notes(study: Optional[dict] = None) -> dict:
    s = study if isinstance(study, dict) else study_block()

    def _st(k):
        return str((s.get(k) or {}).get("text") or "")
    tier_note = (MARK + " A close on every T{n} day of the last " + str(HOLD_WINDOW_DAYS)
                 + f" days and down no more than {HOLD_MAX_DROP_PCT:g}% on at least "
                 + f"{HOLD_RATE_MIN_PCT:g}% of them. ")
    return {"t1": tier_note.format(n=1) + _st("t1"),
            "t2": tier_note.format(n=2) + _st("t2"),
            "eod": (EOD_MARK + " The last session closed up, in the upper half of its range, on "
                    f"more volume than its {VOL_AVG_BARS}-session average — the app's "
                    "accumulation day. " + _st("eod")),
            "pre": ((PRE_MARK + " A pre-market print above yesterday's close on at least "
                     f"{PM_RVOL_MIN:g}× the name's own pre-market volume by the same minute "
                     f"(its cached sessions, at least {PM_BASELINE_MIN_SESSIONS}). Read "
                     "04:00–09:30 ET only. UNMEASURED.")
                    if PM_VOLUME_VERIFIED else
                    (PRE_OFF_LINE + " Why: " + PRE_UNVERIFIED_TEXT + ". UNMEASURED."))}


def filter_line(items, passed_all, pool, *, mode, shown) -> Optional[str]:
    on = [i for i in (items or []) if isinstance(i, dict) and i.get("on")]
    if not on:
        return None
    if DMT.parse_mode(mode) == MODE_ANY:
        bits = []
        for i in on:
            b = f"{i['label']}: {_n(i.get('pass'))} pass"
            if int(i.get("no_read") or 0) > 0:
                b += f" ({_n(i.get('no_read'))} not read)"
            bits.append(b)
        n_shown, n_pool = int(shown or 0), int(pool or 0)
        return (f"Filters on (any ticked box) — {'; '.join(bits)}. {_n(n_shown)} of "
                f"{_n(n_pool)} pass at least one ticked box, {_n(max(n_pool - n_shown, 0))} "
                "hidden (they pass none of them; a name passing several shows once, with a "
                "badge for each).")
    bits = []
    for i in on:
        b = f"{i['label']}: {_n(i.get('pass'))} pass, {_n(i.get('hidden'))} hidden"
        if int(i.get("no_read") or 0) > 0:
            b += f" ({_n(i.get('no_read'))} not read)"
        bits.append(b)
    return (f"Filters on ({MODE_ALL_LABEL}) — {'; '.join(bits)}. {_n(passed_all)} of "
            f"{_n(pool)} pass every ticked box (each count is over all {_n(pool)} names read; "
            "a name can fail more than one).")


def filter_empty_note(active, mode=FILTER_MODE_DEFAULT) -> str:
    labs = [FILTER_LABELS[k] for k in active if k in FILTER_LABELS]
    if DMT.parse_mode(mode) == MODE_ALL:
        return FILTER_EMPTY_FMT.format(labels=" + ".join(labs))
    return FILTER_EMPTY_ANY_FMT.format(labels=" or ".join(labs))


def filters_block(tfs, active, *, pool, mode=FILTER_MODE_DEFAULT,
                  study: Optional[dict] = None) -> dict:
    """The DM shape (`dual_momentum_tab.filters_block`), keys = FILTER_KEYS.
    Per-box counts over EVERY pool row, each box independently."""
    tfs = [t if isinstance(t, dict) else {} for t in (tfs or [])]
    act = tuple(k for k in FILTER_KEYS if k in (active or ()))
    md = DMT.parse_mode(mode)
    notes = box_notes(study)
    items = []
    for k in FILTER_KEYS:
        vals = [t.get(k) for t in tfs]
        n_pass = sum(1 for v in vals if v is True)
        n_fail = sum(1 for v in vals if v is False)
        n_none = len(vals) - n_pass - n_fail
        on = k in act
        it = {"key": k, "label": FILTER_LABELS[k], "on": on, "pass": n_pass,
              "fail": n_fail, "no_read": n_none,
              "hidden": (n_fail + n_none) if on else 0, "note": notes[k]}
        if k == "pre" and not PM_VOLUME_VERIFIED:
            # the 🌅 box is greyed with its one-line reason (follow-up 2026-09-30)
            it.update(off=True, off_reason=PRE_OFF_REASON)
        items.append(it)
    passed_all = sum(1 for t in tfs if DMT.passes(t, act, MODE_ALL)) if act else None
    passed_any = sum(1 for t in tfs if DMT.passes(t, act, MODE_ANY)) if act else None
    shown = (passed_all if md == MODE_ALL else passed_any) if act else None
    return {"keys": list(FILTER_KEYS), "active": list(act), "pool": int(pool or 0),
            "mode": md, "mode_param": FILTER_MODE_PARAM, "mode_all_label": MODE_ALL_LABEL,
            "passed_all": passed_all, "passed_any": passed_any, "shown": shown,
            "hidden": (len(tfs) - shown) if act else 0, "items": items,
            "line": filter_line(items, passed_all, pool, mode=md, shown=shown) if act else None,
            "note": FILTERS_NOTE_ALL if md == MODE_ALL else FILTERS_NOTE_ANY,
            "measured": False}


def filter_badges(tf, active) -> list:
    tf = tf if isinstance(tf, dict) else {}
    act = set(active or ())
    return [{"text": FILTER_LABELS[k], "tone": "good", "res_filter": k}
            for k in FILTER_KEYS if k in act and tf.get(k) is True]


# ---------------------------------------------------------------------------
# the closed-bar half (memoised) — build
# ---------------------------------------------------------------------------
def _kinds_block(sessions: dict, tier: int) -> dict:
    kinds = []
    for _needle, (k, t, _lab) in macro_calendar._RELEASE_TIERS:
        if t == tier and k not in kinds:
            kinds.append(k)
    out = {k: 0 for k in kinds}
    for meta in (sessions or {}).values():
        for k in meta.get("kinds") or []:
            out[k] = out.get(k, 0) + 1
    return out


def _session_events(calendar: Optional[dict], past: list, session: date) -> dict:
    s_iso = session.isoformat()
    rows = []
    for e in ((calendar or {}).get("macro") or []) + list(past or []):
        if isinstance(e, dict) and str(e.get("date") or "")[:10] == s_iso \
                and e.get("tier") in (1, 2):
            rows.append(e)
    t1, t2, seen = [], [], set()
    for e in rows:
        key = (e.get("kind"), s_iso)
        if key in seen:
            continue
        seen.add(key)
        lab = str(e.get("label") or e.get("kind") or "")
        (t1 if e.get("tier") == 1 else t2).append(lab)
    tier = 1 if t1 else (2 if t2 else None)
    return {"t1": t1, "t2": t2, "tier": tier}


def _next_t1(calendar: Optional[dict], session: date) -> Optional[dict]:
    s_iso = session.isoformat()
    best = None
    for e in (calendar or {}).get("macro") or []:
        if not isinstance(e, dict) or e.get("tier") != 1:
            continue
        d = str(e.get("date") or "")[:10]
        if d > s_iso and (best is None or d < best["date"]):
            best = {"date": d, "label": str(e.get("label") or e.get("kind") or "")}
    return best


def _events_error(past) -> Optional[str]:
    if not isinstance(past, dict):
        return "no answer"
    if past.get("available"):
        return None
    errs = past.get("errors") or []
    reasons = sorted({str(e.get("reason")) for e in errs if isinstance(e, dict)})
    return ", ".join(reasons) if reasons else "no FRED release answered"


def build(universe_name: str, session: date, *, universe_fn=None, frames_fn=None,
          events_fn=None, calendar_fn=None) -> dict:
    """The closed-bar half. ONE `bulk_cached_frames(syms + [BENCH])`, ONE
    `past_events`, ONE `get_macro_calendar()` (warm thread only). Raises only
    when frames come back empty for a non-empty universe."""
    from supply_demand import quick_bounce as QB
    ukey = _ukey(universe_name)
    if universe_fn is None:
        from supply_demand import demand_reentry as D
        syms_raw = D._resolve_universe(ukey)[0]
    else:
        syms_raw = universe_fn(ukey)
    syms, seen = [], set()
    for s in syms_raw or []:
        s = str(s or "").strip().upper()
        if s and s not in seen:
            seen.add(s)
            syms.append(s)
    if frames_fn is None:
        from sepa import prices
        frames_fn = prices.bulk_cached_frames
    frames = frames_fn(syms + ([BENCH] if BENCH not in seen else [])) or {}
    if syms and not frames:
        raise RuntimeError(f"resiliency tab: the price-cache read returned no frames for "
                           f"{len(syms):,} names — not memoising an empty read")

    # the benchmark calendar
    bdf = frames.get(BENCH)
    closed_b = KL.closed_frame(bdf, session) if bdf is not None else None
    bench_closes = closes_by_day(closed_b) if closed_b is not None else {}
    trading_days = sorted(bench_closes)

    # the data days
    events_error = None
    past = None
    try:
        past = (events_fn or macro_calendar.past_events)(
            session - timedelta(days=HOLD_WINDOW_DAYS + 7), session - timedelta(days=1))
        events_error = _events_error(past)
    except Exception as exc:                                    # noqa: BLE001
        events_error = type(exc).__name__
    if not trading_days and events_error is None:
        events_error = f"no {BENCH} daily bars to date the sessions"
    try:
        calendar = (calendar_fn or macro_calendar.get_macro_calendar)()
    except Exception as exc:                                    # noqa: BLE001
        log.warning("resiliency tab: macro calendar unavailable: %s", type(exc).__name__)
        calendar = None
    past_rows = list((past or {}).get("events") or []) if isinstance(past, dict) else []
    session_events = _session_events(calendar, past_rows, session)
    next_t1 = _next_t1(calendar, session)

    if events_error is None:
        sessions = event_sessions(past_rows, trading_days,
                                  start=session - timedelta(days=HOLD_WINDOW_DAYS), end=session)
        on_t1 = t2_on_t1(past_rows, trading_days,
                         start=session - timedelta(days=HOLD_WINDOW_DAYS), end=session)
    else:
        sessions = {"t1": {}, "t2": {}}
        on_t1 = {}
    bench_rets = {k: event_returns(bench_closes, trading_days, sessions[k]) for k in ("t1", "t2")}
    all_isos = sorted(set(sessions["t1"]) | set(sessions["t2"]))
    events_summary = {
        "available": events_error is None, "window_days": int(HOLD_WINDOW_DAYS),
        "first": all_isos[0] if all_isos else None, "last": all_isos[-1] if all_isos else None,
        "t1_sessions": len(sessions["t1"]),
        "t1_spy_down": sum(1 for v in bench_rets["t1"].values() if v is not None and v < 0),
        "t2_sessions": len(sessions["t2"]),
        "t2_spy_down": sum(1 for v in bench_rets["t2"].values() if v is not None and v < 0),
        "t1_by_kind": _kinds_block(sessions["t1"], 1),
        "t2_by_kind": _kinds_block(sessions["t2"], 2),
        "t2_on_t1_by_kind": on_t1,
        "sources": list(EVENT_SOURCES),
        "unsourced": list(macro_calendar.HISTORY_UNSOURCED),
        "errors": [{"release_id": e.get("release_id"), "reason": str(e.get("reason"))}
                   for e in ((past or {}).get("errors") or []) if isinstance(e, dict)]
        if isinstance(past, dict) else [],
    }

    need = KL.prev_market_day(session)
    reads: dict = {}
    for sym in syms:
        df = frames.get(sym)
        if df is None:
            continue
        try:
            closed = KL.closed_frame(df, session)
            if closed is None or len(closed) == 0:
                continue
            reads[sym] = _closed_read(closed, sessions, bench_rets, bench_closes, trading_days,
                                      need=need, session=session, events_ok=events_error is None,
                                      qb=QB)
        except Exception as exc:                                # noqa: BLE001
            log.debug("resiliency tab: %s build failed: %s", sym, type(exc).__name__)
            continue
    now_ts = time.time()
    return {"syms": syms, "reads": reads, "events_summary": events_summary,
            "session_events": session_events, "next_t1": next_t1,
            "sessions": sessions,
            "bench": {"rets": bench_rets,
                      "ref_close": bench_closes[trading_days[-1]] if trading_days else None,
                      "ref_date": trading_days[-1] if trading_days else None},
            "last_closed": trading_days[-1] if trading_days else None,
            "built_ts": now_ts,
            "built_at": datetime.fromtimestamp(now_ts, tz=KL.ET).isoformat(timespec="seconds"),
            "session": session.isoformat(), "ukey": ukey, "events_error": events_error}


def _closed_read(closed, sessions, bench_rets, bench_closes, trading_days, *, need, session,
                 events_ok, qb) -> dict:
    closes = closes_by_day(closed)
    t1 = t2 = None
    if events_ok:
        t1 = tier_stats(event_returns(closes, trading_days, sessions["t1"]), sessions["t1"],
                        bench_rets["t1"], tier=1)
        t2 = tier_stats(event_returns(closes, trading_days, sessions["t2"]), sessions["t2"],
                        bench_rets["t2"], tier=2)
    idx = KL._norm_index(closed)
    last_day = idx[-1].date()
    bar = closed.iloc[-1]
    bar_d = {k: _f(bar.get(k)) for k in ("open", "high", "low", "close", "volume")}
    prev = _f(closed["close"].iloc[-2]) if len(closed) >= 2 else None
    avg = MB.avg_volume_before(closed, last_day)
    eod = eod_read(bar_d, prev, avg, date_iso=last_day.isoformat(), source="closed")
    stale_note = None
    if last_day < need:
        stale_note = (f"cached bars end {last_day.isoformat()}; the last session is "
                      f"{need.isoformat()}")
        eod = {**eod, "state": "stale", "bullish": None}
    return {"t1": t1, "t2": t2, "sigma_pct": sigma_pct(closes, trading_days),
            "beta": beta(closes, bench_closes, trading_days), "eod": eod,
            "ref_close": _f(closed["close"].iloc[-1]), "ref_date": last_day.isoformat(),
            "adv50": _f(qb.avg_dollar_vol(closed)),
            "avg_vol_session": MB.avg_volume_before(closed, session),
            "stale_note": stale_note}


# ---------------------------------------------------------------------------
# memo (the ATH memo + DM's failure back-off)
# ---------------------------------------------------------------------------
_memo: dict = {}                # (session_iso, ukey) -> entry
_warming: set = set()
_failed: dict = {}              # key -> {"ts", "reason"}
_lock = threading.Lock()
_pm_memo: dict = {}             # key -> {"built_ts", "by_sym"}
_pm_warming: set = set()
_pm_failed: dict = {}


def _spawn(target, name: str) -> None:
    threading.Thread(target=target, name=name, daemon=True).start()


def _store(key: tuple, entry: dict) -> None:
    newest = max((k[0] for k in _memo), default=key[0])
    if key[0] < newest:
        log.info("resiliency tab: dropped a late %s build (memo holds %s)", key[0], newest)
        return
    for k in [k for k in _memo if k[0] < key[0]]:
        _memo.pop(k, None)
    _memo[key] = entry
    _failed.pop(key, None)


def _warm(key: tuple, universe_name: str, session: date) -> None:
    def _work():
        try:
            entry = build(universe_name, session)
            with _lock:
                _store(key, entry)
        except Exception as exc:                                # noqa: BLE001
            log.warning("resiliency tab: build failed for %s: %s", key, type(exc).__name__)
            with _lock:
                _failed[key] = {"ts": time.time(), "reason": _safe_reason(exc)}
        finally:
            with _lock:
                _warming.discard(key)

    with _lock:
        if key in _warming:
            return
        _warming.add(key)
    _spawn(_work, f"resiliency-tab-{key[0]}-{key[1]}")


def cached_or_warm(universe_name, *, now: datetime, sync: bool = False) -> dict:
    """{"state": "ready"|"warming"|"error", "entry"[, "reason"]}. Key =
    (session ISO, universe key). Held + fresh -> ready. Held but stale -> the
    held entry + ONE background rebuild. Nothing held -> ONE background build
    (warming). A failed build is served as "error" and retried at most once per
    FAIL_RETRY_SEC. `sync=True` builds inline (tests / the probe)."""
    session = KL.levels_session(now)
    ukey = _ukey(universe_name)
    key = (session.isoformat(), ukey)
    with _lock:
        entry = _memo.get(key)
    fresh = entry is not None and (time.time() - float(entry.get("built_ts") or 0)) < MEMO_TTL_SEC
    if fresh:
        return {"state": "ready", "entry": entry}
    if sync:
        try:
            built = build(ukey, session)
        except Exception as exc:
            with _lock:
                _failed[key] = {"ts": time.time(), "reason": _safe_reason(exc)}
            raise
        with _lock:
            _store(key, built)
        return {"state": "ready", "entry": built}
    with _lock:
        failed = dict(_failed.get(key) or {})
    backing_off = bool(failed) and (time.time() - float(failed.get("ts") or 0)) < FAIL_RETRY_SEC
    if not backing_off:
        _warm(key, ukey, session)
    if entry is not None:
        return {"state": "ready", "entry": entry}
    if failed:
        return {"state": "error", "entry": None, "reason": failed.get("reason") or "unknown"}
    return {"state": "warming", "entry": None}


# ---------------------------------------------------------------------------
# the pre-market baseline (read-only aggregation on intraday_cache)
# ---------------------------------------------------------------------------
def pm_dates(session: date) -> list:
    """The last VOL_AVG_BARS market sessions before `session`, oldest first."""
    out, d = [], session
    for _ in range(VOL_AVG_BARS):
        d = KL.prev_market_day(d)
        out.append(d.isoformat())
    return sorted(out)


def _pm_coll():
    from sepa import prices
    pc = prices._get_mongo()
    return None if pc is None else pc.database[INTRADAY_COLL]


def pm_pipeline(syms: list, dates: list) -> list:
    return [{"$match": {"symbol": {"$in": list(syms)}, "date": {"$in": list(dates)}}},
            {"$project": {"symbol": 1, "date": 1,
                          "pm": {"$filter": {"input": "$bars", "as": "b",
                                             "cond": {"$eq": ["$$b.session", "premarket"]}}}}},
            {"$unwind": "$pm"},
            {"$group": {"_id": {"s": "$symbol", "d": "$date",
                                "h": {"$substrBytes": ["$pm.ts_utc", 11, 4]}},
                        "v": {"$sum": "$pm.volume"}}}]


def pm_build(syms: list, session: date, *, coll=None) -> dict:
    c = coll if coll is not None else _pm_coll()
    if c is None:
        raise RuntimeError("the intraday cache is unavailable")
    dates = pm_dates(session)
    syms = [str(s).upper() for s in syms or []]
    agg = list(c.aggregate(pm_pipeline(syms, dates), allowDiskUse=True))
    docs = [(d.get("symbol"), d.get("date"), d.get("first")) for d in
            c.find({"symbol": {"$in": syms}, "date": {"$in": dates}},
                   {"symbol": 1, "date": 1, "_id": 0, "first": {"$min": "$bars.ts_utc"}})]
    return pm_slots(agg, docs, session=session, dates=dates)


def pm_cached_or_warm(syms, session: date, *, sync: bool = False, coll=None) -> dict:
    """{"state": "ready"|"warming"|"error", "by_sym"}. The caller warms it ONLY
    in the 'pre' phase. Key = (session ISO, the symbol set)."""
    key = (session.isoformat(), hash(tuple(sorted(str(s) for s in syms or []))))
    with _lock:
        held_e = _pm_memo.get(key)
    if held_e is not None and (time.time() - float(held_e["built_ts"])) < MEMO_TTL_SEC:
        return {"state": "ready", "by_sym": held_e["by_sym"]}
    if sync:
        try:
            by = pm_build(list(syms or []), session, coll=coll)
        except Exception as exc:                                # noqa: BLE001
            with _lock:
                _pm_failed[key] = time.time()
            log.warning("resiliency tab: pre-market baseline failed: %s", type(exc).__name__)
            return {"state": "error", "by_sym": {}}
        with _lock:
            _pm_memo.clear()
            _pm_memo[key] = {"built_ts": time.time(), "by_sym": by}
        return {"state": "ready", "by_sym": by}
    with _lock:
        failed_ts = _pm_failed.get(key)
        backing_off = failed_ts is not None and (time.time() - failed_ts) < FAIL_RETRY_SEC
        start = not backing_off and key not in _pm_warming
        if start:
            _pm_warming.add(key)
    if start:
        sy = list(syms or [])

        def _work():
            try:
                by = pm_build(sy, session, coll=coll)
                with _lock:
                    _pm_memo.clear()
                    _pm_memo[key] = {"built_ts": time.time(), "by_sym": by}
                    _pm_failed.pop(key, None)
            except Exception as exc:                            # noqa: BLE001
                log.warning("resiliency tab: pre-market baseline failed: %s",
                            type(exc).__name__)
                with _lock:
                    _pm_failed[key] = time.time()
            finally:
                with _lock:
                    _pm_warming.discard(key)
        _spawn(_work, f"resiliency-pm-{key[0]}")
    if held_e is not None:
        return {"state": "ready", "by_sym": held_e["by_sym"]}
    if failed_ts is not None:
        return {"state": "error", "by_sym": {}}
    return {"state": "warming", "by_sym": {}}


# ---------------------------------------------------------------------------
# per request — rank (PURE over the memo + one snapshot)
# ---------------------------------------------------------------------------
COUNT_KEYS = ("scanned", "no_bars", "stale", "rated_t1", "partial_t1", "t1_pass",
              "rated_t2", "partial_t2", "t2_pass", "eod_read", "eod_pass",
              "pre_read", "pre_pass", "pre_no_baseline", "eod_session")


def _session_bar(raw: Optional[dict], session: date) -> Optional[dict]:
    """Today's snapshot day bar when it is dated the session and o,h,l,c,v > 0."""
    if not isinstance(raw, dict):
        return None
    try:
        if raw.get("date") is None or day_iso(raw.get("date")) != session.isoformat():
            return None
    except (TypeError, ValueError):
        return None
    bar = {k: _pos(raw.get(k)) for k in ("open", "high", "low", "close", "volume")}
    return bar if all(v is not None for v in bar.values()) else None


def rank(entry: dict, raw: dict, pm: Optional[dict], *, now: datetime, sort: str,
         active=(), mode=FILTER_MODE_DEFAULT) -> tuple:
    """(rows, counts, filters, today_summary, sort_unavailable). Counts cover
    the WHOLE pool before the boxes; the boxes filter with `DMT.passes`; the
    order is `order_key`. Never mutates the memo; never reads the calendar."""
    now_et = KL._et(now)
    session = date.fromisoformat(str(entry["session"]))
    ph = KL.phase(now_et, session)
    raw = raw if isinstance(raw, dict) else {}
    pm = pm if isinstance(pm, dict) else {}
    pm_state = pm.get("state") or ("ready" if pm.get("by_sym") else "warming")
    pm_by = pm.get("by_sym") or {}
    act = tuple(k for k in FILTER_KEYS if k in (active or ()))
    md = DMT.parse_mode(mode)
    sev = entry.get("session_events") or {}
    event = ({"tier": sev.get("tier"), "labels": list(sev.get("t1") or []) + list(sev.get("t2") or [])}
             if sev.get("tier") in (1, 2) else None)
    counts = {k: 0 for k in COUNT_KEYS}
    today_c = {"read": 0, "holding": 0, "down": 0, "no_print": 0}
    reads = entry.get("reads") or {}
    pool: list = []
    for sym in entry.get("syms") or []:
        counts["scanned"] += 1
        rd = reads.get(sym)
        if not rd:
            counts["no_bars"] += 1
            continue
        rd = copy.deepcopy(rd)
        r_raw = raw.get(sym)
        row = KL.row_or_none(r_raw)
        stale_s, _ok = KL.verify_last(rd.get("ref_close"), rd.get("ref_date"), row)
        if stale_s or rd.get("stale_note"):
            counts["stale"] += 1
        tr = today_read(r_raw, ref_close=rd.get("ref_close"), ref_date=rd.get("ref_date"),
                        now=now_et, session=session, phase=ph, event=event)
        if rd.get("stale_note") and tr["state"] == "read":
            tr = _today_blank(event, "stale")
        pr = pre_read(r_raw, ref_close=rd.get("ref_close"), ref_date=rd.get("ref_date"),
                      now=now_et, session=session, phase=ph, baseline=pm_by.get(sym),
                      baseline_state="warming" if pm_state == "warming" else pm_state)
        if rd.get("stale_note") and pr["state"] not in ("not_open",):
            pr = _pre_blank("stale", f"Not read — {rd['stale_note']}.")
        eod = rd.get("eod") or {}
        if ph == "close" and not stale_s and _ok and not rd.get("stale_note"):
            bar = _session_bar(r_raw, session)
            if bar is not None:
                eod = eod_read(bar, rd.get("ref_close"), rd.get("avg_vol_session"),
                               date_iso=session.isoformat(), source="session")
                counts["eod_session"] += 1
        res = {"t1": rd.get("t1"), "t2": rd.get("t2"), "today": tr, "eod": eod, "pre": pr,
               "sigma_pct": rd.get("sigma_pct"), "beta": rd.get("beta"), "adv50": rd.get("adv50")}
        tf = tile_filter(res)
        for k in ("t1", "t2"):
            st = res[k]
            if isinstance(st, dict):
                counts["rated_" + k if st.get("rated") else "partial_" + k] += 1
            counts[k + "_pass"] += int(tf[k] is True)
        counts["eod_read"] += int(eod.get("state") in ("read", "flat_bar"))
        counts["eod_pass"] += int(tf["eod"] is True)
        counts["pre_read"] += int(pr.get("state") == "read")
        counts["pre_pass"] += int(tf["pre"] is True)
        counts["pre_no_baseline"] += int(pr.get("state") == "no_baseline")
        if event is not None:
            if tr["state"] == "read":
                today_c["read"] += 1
                today_c["holding" if tr["holding"] else "down"] += 1
            elif tr["state"] == "no_print":
                today_c["no_print"] += 1
        pool.append({"symbol": sym, "ref_close": rd.get("ref_close"), "adv50": rd.get("adv50"),
                     "resiliency": res, "res_filter": tf})
    filters = filters_block([r["res_filter"] for r in pool], act, pool=len(pool), mode=md,
                            study=study_block())
    rows = [r for r in pool if DMT.passes(r["res_filter"], act, md)]
    sort_unavailable = None
    eff = sort if sort in TAB_SORTS else DEFAULT_SORT_KEY
    if eff == SORT_TODAY and event is None:
        sort_unavailable = TODAY_SORT_UNAVAILABLE
        eff = DEFAULT_SORT_KEY
    rows.sort(key=lambda r: order_key(r, eff))
    # today summary (the benchmark's own read)
    if event is not None:
        b = entry.get("bench") or {}
        spy = today_read(raw.get(BENCH), ref_close=b.get("ref_close"), ref_date=b.get("ref_date"),
                         now=now_et, session=session, phase=ph, event=event)
        today = {"event_day": True, "session": session.isoformat(),
                 "t1": list(sev.get("t1") or []), "t2": list(sev.get("t2") or []),
                 "tier": int(sev["tier"]),
                 "spy_move_pct": spy.get("move_pct") if spy["state"] == "read" else None,
                 "spy_tape": spy.get("tape"), "spy_as_of_et": spy.get("as_of_et"),
                 "spy_basis": spy.get("basis") if spy["state"] == "read" else None,
                 **today_c}
    else:
        today = {"event_day": False, "session": session.isoformat(),
                 "next_t1": copy.deepcopy(entry.get("next_t1"))}
    return rows, counts, filters, today, sort_unavailable


# ---------------------------------------------------------------------------
# tile words (served; the FE prints them verbatim)
# ---------------------------------------------------------------------------
def _pct_txt(v) -> str:
    x = _f(v)
    return "—" if x is None else f"{x:+.2f}%"


def _labels_txt(labels) -> str:
    return " + ".join(str(x) for x in (labels or [])) or "data day"


def tile_badges(r: dict, active=(), *, event_day: bool = False) -> list:
    res = r.get("resiliency") or {}
    tf = r.get("res_filter") or {}
    out = []
    t1 = res.get("t1")
    if isinstance(t1, dict) and int(t1.get("n") or 0) > 0:
        out.append({"text": T1_BADGE_FMT.format(held=int(t1["held"]), n=int(t1["n"]),
                                                rate=float(t1.get("rate_pct") or 0.0)),
                    "tone": "good" if tf.get("t1") is True else "muted"})
    td = res.get("today") or {}
    if event_day and td.get("state") == "read" and td.get("tier") in (1, 2):
        fmt = TODAY_HOLD_FMT if td.get("holding") else TODAY_DOWN_FMT
        out.append({"text": fmt.format(tier=int(td["tier"]), move=float(td["move_pct"])),
                    "tone": "good" if td.get("holding") else "warn"})
    out.extend(filter_badges(tf, active))
    return out


def _tier_stat(st, tier: int) -> str:
    if not isinstance(st, dict):
        return "— (the data-day history could not be read)"
    n, ev = int(st.get("n") or 0), int(st.get("events") or 0)
    if n == 0:
        return f"no close on any of the {ev} T{tier} days"
    txt = f"{int(st['held'])}/{n} · {float(st.get('rate_pct') or 0):.0f}%"
    if int(st.get("down_n") or 0) > 0:
        txt += f" · SPY down: {int(st['down_held'])}/{int(st['down_n'])}"
    if not st.get("rated"):
        txt += f" · {ev - n} of {ev} T{tier} days without a close — not rated"
    return txt


def _eod_stat(e: dict) -> str:
    st = (e or {}).get("state")
    if st == "read":
        return (f"{str(e.get('date') or '')[5:]} · {_pct_txt(e.get('chg_pct'))} · "
                f"closed at {float(e.get('close_loc_pct') or 0):.0f}% of range · vol "
                f"{float(e.get('rvol') or 0):.2f}× {VOL_AVG_BARS}d")
    if st == "flat_bar":
        return f"{str(e.get('date') or '')[5:]} · no range (high = low) — not an accumulation day"
    if st == "no_avg":
        return f"{str(e.get('date') or '')[5:]} · {_pct_txt(e.get('chg_pct'))} · fewer than {VOL_AVG_BARS} sessions for the volume average"
    if st == "no_volume":
        return f"{str(e.get('date') or '')[5:]} · {_pct_txt(e.get('chg_pct'))} · no volume on the bar"
    if st == "stale":
        return "daily bars behind — not read"
    return "no closed bar to read"


_TODAY_TEXT = {"no_print": "no print today yet — not read",
               "stale": "daily bars behind — not read",
               "not_open": "the session has not opened"}


def _today_stat(td: dict) -> str:
    if td.get("state") == "read":
        if td.get("basis") == "live":
            when = f"{_TAPE_WORD.get(td.get('tape'), 'live')} {td.get('as_of_et') or ''} ET".replace("  ", " ")
        elif td.get("basis") == DAY_BAR_BASIS:
            when = DAY_BAR_WORD
        else:
            when = DAY_CLOSE_WORD
        return f"{_pct_txt(td.get('move_pct'))} vs {float(td.get('prev_close') or 0):.2f} · {when}"
    return _TODAY_TEXT.get(td.get("state"), "not read")


def tile_stats(r: dict, *, event_day: bool = False) -> list:
    res = r.get("resiliency") or {}
    out = [{"k": "T1 held", "v": _tier_stat(res.get("t1"), 1)},
           {"k": "T2 held", "v": _tier_stat(res.get("t2"), 2)},
           {"k": "EOD tape", "v": _eod_stat(res.get("eod") or {})},
           {"k": "Pre-market", "v": str((res.get("pre") or {}).get("text") or "not read")}]
    if event_day:
        out.append({"k": "Today", "v": _today_stat(res.get("today") or {})})
    t1 = res.get("t1") if isinstance(res.get("t1"), dict) else {}
    w = t1.get("worst")
    if isinstance(w, dict):
        out.append({"k": "T1 worst", "v": f"{_pct_txt(w.get('ret_pct'))} · {w.get('date')} "
                                          f"{_labels_txt(w.get('labels'))}"})
    la = t1.get("last")
    if isinstance(la, dict):
        out.append({"k": "Last T1", "v": f"{_pct_txt(la.get('ret_pct'))} · {la.get('date')} "
                                         f"{_labels_txt(la.get('labels'))} (SPY "
                                         f"{_pct_txt(la.get('spy_ret_pct'))})"})
    sg, bt = _f(res.get("sigma_pct")), _f(res.get("beta"))
    out.append({"k": "σ · β",
                "v": f"{'—' if sg is None else f'{sg:.1f}%/day'} · "
                     f"β {'—' if bt is None else f'{bt:.2f}'}"})
    return out


def why_text(r: dict) -> str:
    res = r.get("resiliency") or {}
    t1 = res.get("t1")
    sg = _f(res.get("sigma_pct"))
    tail = f"typical day {sg:.1f}%" if sg is not None else "typical day —"
    if not isinstance(t1, dict) or int(t1.get("n") or 0) == 0:
        return f"No T1-day read · {tail}"
    txt = (f"Held {int(t1['held'])} of {int(t1['n'])} T1 days "
           f"({float(t1.get('rate_pct') or 0):.0f}%)")
    if int(t1.get("down_n") or 0) > 0:
        txt += f", {int(t1['down_held'])} of {int(t1['down_n'])} when SPY fell"
    w = t1.get("worst")
    if isinstance(w, dict):
        txt += f" · worst {_pct_txt(w.get('ret_pct'))} ({w.get('date')} {_labels_txt(w.get('labels'))})"
    return txt + " · " + tail


# ---------------------------------------------------------------------------
# the served board block
# ---------------------------------------------------------------------------
def _kinds_txt(by_kind: dict, on_t1: Optional[dict] = None) -> str:
    bits = [f"{_KIND_LABEL.get(k, k)} {int(v)}" for k, v in (by_kind or {}).items() if int(v or 0)]
    # a T2 kind at 0 whose every print sat on a T1 day is named, not dropped
    gone = []
    for k, meta in (on_t1 or {}).items():
        if int((by_kind or {}).get(k) or 0) or not isinstance(meta, dict) or not int(meta.get("n") or 0):
            continue
        lab = _KIND_LABEL.get(k, k)
        t1 = "/".join(str(x) for x in (meta.get("t1_labels") or [])) or "T1"
        gone.append(f"{lab} 0 — every {lab} print in the window landed on a T1 {t1} day "
                    "and is counted there")
    txt = ", ".join(bits) or "none"
    return txt + "".join(f"; {g}" for g in gone)


def header_text(counts: dict, *, entry: dict, ph, pm_state: Optional[str]) -> str:
    c = counts or {}
    ev = entry.get("events_summary") or {}
    err = entry.get("events_error")
    head = f"{MARK} {_n(c.get('scanned'))} names read on the cached daily bars. "
    if err:
        head += (f"The T1/T2 day history could not be read ({err}) — no name is rated and "
                 f"the {MARK} boxes pass none; the tape reads still show. ")
    else:
        head += (f"T1 days in the last {HOLD_WINDOW_DAYS} days: {_n(ev.get('t1_sessions'))} "
                 f"({_kinds_txt(ev.get('t1_by_kind'))}), SPY fell on {_n(ev.get('t1_spy_down'))}; "
                 f"T2-only days: {_n(ev.get('t2_sessions'))} "
                 f"({_kinds_txt(ev.get('t2_by_kind'), ev.get('t2_on_t1_by_kind'))}), "
                 f"SPY fell on {_n(ev.get('t2_spy_down'))}. Rated (a close on every T1 day): "
                 f"{_n(c.get('rated_t1'))}; held on at least {HOLD_RATE_MIN_PCT:g}% of them: "
                 f"{_n(c.get('t1_pass'))}. ")
    eod_date = (entry.get("session") if int(c.get("eod_session") or 0) > 0
                else entry.get("last_closed")) or "the last session"
    head += f"{EOD_MARK} bullish EOD tape on {eod_date}: {_n(c.get('eod_pass'))}. "
    if ph == "pre":
        if not PM_VOLUME_VERIFIED:
            head += (f"{PRE_MARK} pre-market volume is not compared yet — the snapshot's "
                     "pre-market shares read higher than the cached 1-minute bars the usual "
                     f"volume comes from, so the {PRE_MARK} box passes none until you decide. ")
        elif pm_state == "warming":
            head += f"{PRE_MARK} the usual pre-market volume is loading. "
        elif pm_state == "error":
            head += f"{PRE_MARK} the cached pre-market volume could not be read. "
        else:
            head += (f"{PRE_MARK} bullish pre-market tape: {_n(c.get('pre_pass'))} of "
                     f"{_n(c.get('pre_read'))} read ({_n(c.get('pre_no_baseline'))} with fewer "
                     f"than {PM_BASELINE_MIN_SESSIONS} cached pre-market sessions). ")
    elif not PM_VOLUME_VERIFIED:
        head += f"{PRE_MARK} pre-market box: {PRE_OFF_REASON} — it passes none. "
    else:
        head += f"{PRE_MARK} the pre-market read runs 04:00–09:30 ET only. "
    head += (f"{_n(c.get('dropped_thin'))} under the liquidity floor, "
             f"{_n(c.get('no_turnover'))} with no turnover to check; showing {_n(c.get('shown'))}.")
    return head


def today_line(today: dict) -> Optional[str]:
    t = today if isinstance(today, dict) else {}
    if t.get("event_day"):
        parts = []
        if t.get("t1"):
            parts.append(f"{_labels_txt(t['t1'])} (T1)")
        if t.get("t2"):
            parts.append(f"{_labels_txt(t['t2'])} (T2)")
        txt = f"{TODAY_MARK} {t.get('session')} is a T{t.get('tier')} data day — {'; '.join(parts)}."
        spy = _f(t.get("spy_move_pct"))
        if spy is not None:
            when = _TAPE_WORD.get(t.get("spy_tape"), DAY_BAR_WORD if t.get("spy_basis") ==
                                  DAY_BAR_BASIS else DAY_CLOSE_WORD)
            if t.get("spy_as_of_et"):
                when += f" {t['spy_as_of_et']} ET"
            txt += f" SPY {spy:+.2f}% vs its prior close ({when})."
        else:
            txt += " SPY has no print today yet."
        txt += (f" {_n(t.get('holding'))} of {_n(t.get('read'))} names with a print are holding "
                f"(down no more than {HOLD_MAX_DROP_PCT:g}%).")
        return txt
    nx = t.get("next_t1")
    txt = f"{TODAY_MARK} {t.get('session')} has no T1 or T2 print."
    if isinstance(nx, dict) and nx.get("date"):
        txt += f" Next T1: {nx.get('label')} {nx.get('date')}."
    return txt


def events_line(entry: Optional[dict]) -> str:
    ev = (entry or {}).get("events_summary") or {}
    txt = EVENTS_LINE
    errs = ev.get("errors") or []
    if errs:
        bits = [f"release {e.get('release_id')}: {e.get('reason')}" for e in errs]
        txt += " Not read this time: " + "; ".join(bits) + "."
    return txt


def _market_closed(now_et: datetime) -> Optional[str]:
    try:
        from market_hours import gate
        return gate.closed_reason(now_et)
    except Exception:                                           # noqa: BLE001
        return None


def _block(state: str, *, now: datetime, sort: str, header: str, entry: Optional[dict] = None,
           counts=None, filters=None, today=None) -> dict:
    now_et = KL._et(now)
    session = session_for(now_et)
    study = study_block()
    return {"state": state, "session": session.isoformat(), "phase": KL.phase(now_et, session),
            "market_closed": _market_closed(now_et), "sort": sort, "header": header,
            "today_line": today_line(today) if today else None,
            "events_line": events_line(entry) if entry else None,
            "rules": rules_block(),
            "events": copy.deepcopy((entry or {}).get("events_summary")) if entry else None,
            "today": today, "counts": dict(counts) if counts is not None else None,
            "filters": filters, "study": study, "note": note_text(study),
            "measured": MEASURED,
            "built_at": None if not entry else str(entry.get("built_at"))}


def warming_block(*, now: datetime, sort: str = DEFAULT_SORT_KEY) -> dict:
    return _block("warming", now=now, sort=sort, header=WARMING_NOTE)


def error_note(reason) -> str:
    return ERROR_NOTE_FMT.format(reason=str(reason or "unknown"), mins=int(FAIL_RETRY_SEC // 60))


def error_block(reason, *, now: datetime, sort: str = DEFAULT_SORT_KEY) -> dict:
    return _block("error", now=now, sort=sort, header=error_note(reason))


def ready_block(counts: dict, *, entry: dict, now: datetime, sort: str, filters: dict,
                today: dict, pm_state: Optional[str] = None) -> dict:
    ph = KL.phase(KL._et(now), date.fromisoformat(str(entry["session"])))
    return _block("ready", now=now, sort=sort, entry=entry, counts=counts, filters=filters,
                  today=today, header=header_text(counts, entry=entry, ph=ph, pm_state=pm_state))


def served_sorts() -> list:
    return [{"key": DEFAULT_SORT_KEY, "label": DEFAULT_SORT_LABEL},
            {"key": SORT_T2, "label": T2_SORT_LABEL},
            {"key": SORT_DOWN, "label": DOWN_SORT_LABEL},
            {"key": SORT_TODAY, "label": TODAY_SORT_LABEL}]
