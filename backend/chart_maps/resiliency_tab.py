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

📅 EVERY SESSION / 🚀 GROWTH (2026-10-07). Ajay: "Can you do a scan for me on
the reseliency tab.. Is it working? [...] I wanna see which stocks were
reselient cuz Vista was very reselient", then "I want the highest
growth stocks on top like Vistra for example". The 📅 read now runs on EVERY
session through ONE function (`today_read`) on the 🔻 tab's clock
(`drop10_tab.mode_for`): live in market hours (the unchanged `KL.anchor_read`
path), the snapshot day bar's regular-session close after it
(`drop10_tab.day_from_snapshot`, never the after-hours print), and before the
open, overnight and on weekends the LAST closed session's close against the one
before it off the closed bars, checked against the snapshot (`KL.verify_last`)
and dated — never "today", never a tier. A T1/T2 day's pre-market keeps its
live pre-market read. The default order resolves per request: today's move
(biggest gain first) once the session has a print, else the T1 hold rate.
Each card also carries the latest quarter's sales and EPS growth against the
same quarter a year earlier (`research.decision_snapshot`, read in the warm
thread only); the 🚀 order blends both legs with `qoq.score_board`, ranking a
leg only off a material year-ago base (`qoq.MIN_EPS_BASE` through
`qoq._seq_pct`; `bonde._rev_base`). Both are ORDERS, UNMEASURED — the MEASURED
lines on this tab are about data days only.

🚀 TWO LEGS FIRST + EVERY GAP SAYS WHY (2026-10-07 b). Ajay, on "say if you
want DBRG-style one-leg names out of the top block": "yes please also no #s
for SNDK can you do a deep analysis of data and make sure you do a sanity
chcek fo missing data pieces over all." The 🚀 order is now BOTH ranked legs,
then one (an EPS leg before a sales leg), then none. Every leg that does not
rank carries a reason code and the chip says it in words (yr-ago loss, ETF/fund,
new listing, a filing a year past due...) — never a bare dash; a figure shown
but not ranked carries `NOT_RANKED_MARK`. His rule #7 (a stored figure must
agree with its own quarterly series) now covers the sales leg too
(`SALES_AGREE_REQUIRED`), an ETF never ranks, and a latest filing
`STALE_FILING_QUARTERS` or more behind the quarter now due never ranks — HIS
CALL defaults, one constant each. On the 🚀 order a served coverage line and a
fold count every gap class over the memo's cards (`growth_coverage`).

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
from observability import period_freshness as PF
from rotation import tracker as RT
from sepa import bonde as SB
from sepa import breakout_audit, qoq, universe
from sepa import massive_fundamentals as MF
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
EW_BENCH = RT.BENCHMARK                    # "RSP" — rotation.tracker (import, never the literal)
GROWTH_MARK = "\U0001F680"                # 🚀 (sort LABEL only — never a badge prefix; cardLadder routes '🚀 ' to PRICE)
MODE_LIVE, MODE_AFTER, MODE_CLOSED = "live", "after_close", "closed"   # == drop10_tab.MODE_* (test-pinned)
LAST_BASIS = "last_session"
SORT_T1, SORT_T2, SORT_DOWN, SORT_TODAY, SORT_GROWTH = (
    "res_t1", "res_t2", "res_down", "res_today", "res_growth")
TAB_SORTS = (SORT_T1, SORT_T2, SORT_DOWN, SORT_TODAY, SORT_GROWTH)
DEFAULT_SORT_KEY = "default"              # == board.DEFAULT_SORT (test-pinned; no board import here)
DEFAULT_SORT_LABEL = MARK + " T1 hold rate"   # unchanged text; now also the res_t1 label
T1_SORT_LABEL = DEFAULT_SORT_LABEL
T2_SORT_LABEL = MARK + " T2 hold rate"
DOWN_SORT_LABEL = MARK + " T1 on SPY-down days"
TODAY_SORT_LABEL = TODAY_MARK + " Today's move"
LAST_SORT_LABEL = TODAY_MARK + " Last session's move"
GROWTH_SORT_LABEL = GROWTH_MARK + " Sales + EPS growth"
DEFAULT_LABEL_SUFFIX = " (default)"
T1_BADGE_FMT = MARK + " T1 held {held}/{n} ({rate:.0f}%)"          # IDENT rung (FE prefix "🛡️ T1 held")
TODAY_HOLD_FMT = TODAY_MARK + " T{tier} today · holding {move:+.2f}%"   # PRICE rung
TODAY_DOWN_FMT = TODAY_MARK + " T{tier} today · down {move:+.2f}%"
TODAY_PLAIN_FMT = TODAY_MARK + " today · {move:+.2f}%"                # "📅 today · +4.53%"
TODAY_LAST_FMT = TODAY_MARK + " last session {day} · {move:+.2f}%"    # "📅 last session Wed 10-07 · +4.53%"
TODAY_SORT_NO_READ = "No name has a print to order by yet — the board is in T1 hold-rate order."
GROWTH_SORT_UNAVAILABLE = ("No sales or EPS figures are on file for these names right now — "
                           "the board is in its default order.")
GROWTH_CHIP_PREFIX = "Sales "             # == cardLadder IDENT_PREFIX entry (contract)
GROWTH_CHIP_FMT = "Sales {sales} · EPS {eps} YoY ({period})"
GROWTH_NO_FIGURES = "no quarterly figures on file"
GROWTH_MASSIVE_UNUSED = "Massive not used at research time, pending refresh"   # 2026-10-07 c
GROWTH_MISMATCH = "quarters not a year apart on file"
GROWTH_PERIOD_UNKNOWN = "quarter not on file"
GROWTH_STAT_KEY = "Growth"
EPS_MIN_BASE = qoq.MIN_EPS_BASE           # $0.10 (import) — HIS CALL: applied to the YEAR-AGO quarter
REV_MIN_BASE = SB.MIN_MATERIAL_BASE_REV   # $1,000,000 (import)
PCT_AGREE_TOL = qoq.PCT_AGREE_TOL                 # import — one home (2-dp representation, NOT a rule)
# 2026-10-07 b — 🚀 two legs first + every gap says why (SPEC 2026-10-07)
PCT_AGREE_TOL_1DP = 0.05 + PCT_AGREE_TOL          # a 1-dp stored figure (sales.growth_yoy_pct) — representation, NOT a rule
SALES_AGREE_REQUIRED = True                       # HIS CALL 1 (2026-10-07 b): his rule #7 applied to the sales leg
STALE_FILING_QUARTERS = qoq.YOY_GAP               # HIS CALL 2: a latest quarter this many behind the expected one never ranks
NOT_RANKED_MARK = "*"
SALES_NO_REV_TOKEN = "yr-ago rev ≤$0"            # the sales leg on a non-positive base (never "loss")
GROWTH_CHIP_NONE_FMT = GROWTH_CHIP_PREFIX + "· EPS: {reason}"   # "Sales · EPS: ETF/fund, no filings"
GROWTH_GAP_TOP = 5                                # names printed per gap line — display, NOT a rule
PENDING_REASONS = ("stored_missing", "stored_disagrees", "no_series")
RULE_REASONS = ("year_ago_loss", "year_ago_too_small")
GAP_ORDER = ("etf", "new_listing", "not_researched", "massive_unused", "no_filings",
             "stale_filings", "period_gap", "year_ago_missing")
GAP_LABEL = {"etf": "ETF/fund", "new_listing": "new listing", "not_researched": "not researched",
             "massive_unused": "Massive not used at research time",
             "no_filings": "no quarterly figures", "stale_filings": "a year past due",
             "period_gap": "quarters not a year apart", "year_ago_missing": "year-ago quarter missing"}
# 2026-10-08 — the revenue line (SPEC §3.3): a held / undetermined line is shown with *, never ranked
LINE_REASONS = ("line_unverified", "line_mixed")
REVENUE_LINE_CLASS = "revenue_line"
REVENUE_LINE_LABEL = "revenue line not the 10-Q's"
REVENUE_LINE_WHY = ("the provider's revenue line is not the one the 10-Q headlines, or which line "
                    f"ranks is pending a decision — shown with {NOT_RANKED_MARK}, never ranked; a "
                    "research refresh does not change it")
SALES_LINE_MIXED_TEXT = ("sales: the year-ago quarter sits on a different revenue line on file "
                         "— not compared")
PENDING_LABEL = "pending refresh"
BY_RULE_LABEL = "blank by rule"
GROWTH_GAPS_SUMMARY = "Why a card has no ranked growth — most-traded names first"
MARKET_LIVE_WHEN = "Today, live"
MARKET_PRE_WHEN = "Pre-market today, live"
MARKET_AFTER_WHEN_FMT = "Today's close ({close} ET)"
MARKET_LAST_WHEN_FMT = "Last session ({day} close)"
MARKET_LINE_FMT = (TODAY_MARK + " {when}: {bench} {spy} · {ew} {rsp} · median name {med} ({word}) · "
                   "{up} of {n} names read are up.")
MARKET_EMPTY_FMT = TODAY_MARK + " {when}: no name has a print to read yet."
MARKET_STALE_FMT = TODAY_MARK + " {when}: {stale_text} ({n} names)."   # every unread name stale
NO_PRINT_WORD = "no print"
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
    tape += (f" {TODAY_MARK} Today's move and {GROWTH_MARK} sales + EPS growth are orders, "
             "UNMEASURED — the MEASURED lines here are about data days only.")
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


def today_mode(now: datetime) -> dict:
    """{"mode", "day", "half_day"} — `drop10_tab.mode_for`, the ONE clock. `day`
    = the session the 📅 read is about (today in live / after_close, the last
    closed session in closed)."""
    from chart_maps import drop10_tab as D10
    mode, day, _tape, half = D10.mode_for(KL._et(now))
    return {"mode": mode, "day": day.isoformat(), "half_day": bool(half)}


def today_sort_label(mode: Optional[str], data_pre: bool = False) -> str:
    return TODAY_SORT_LABEL if (mode in (MODE_LIVE, MODE_AFTER) or data_pre) else LAST_SORT_LABEL


def last_session_read(closes: dict, trading_days: list, day) -> dict:
    """The last closed session's close against the BENCH-calendar day before it
    (PURE). No gap bridging — the `event_returns` rule."""
    iso = _iso(day)
    days = sorted(str(d)[:10] for d in (trading_days or []))
    closes = closes if isinstance(closes, dict) else {}
    i = bisect_left(days, iso)
    prev = days[i - 1] if 0 < i <= len(days) else None
    return {"date": iso, "prev_date": prev,
            "close": _r(closes.get(iso), 4), "prev_close": _r(closes.get(prev), 4) if prev else None,
            "move_pct": event_returns(closes, days, {iso: None})[iso]}


def _today_blank(event: Optional[dict], state: str, *, mode: Optional[str] = None,
                 day: Optional[str] = None, for_today: bool = False) -> dict:
    ev = event if isinstance(event, dict) else None
    return {"event_day": ev is not None, "tier": (ev or {}).get("tier"),
            "labels": list((ev or {}).get("labels") or []), "state": state,
            "move_pct": None, "holding": None, "print": None, "prev_close": None,
            "basis": None, "tape": None, "as_of_et": None,
            "mode": mode, "day": day, "for_today": bool(for_today)}


def _last_session_read(raw: Optional[dict], *, ref_close, ref_date,
                       last: Optional[dict]) -> dict:
    """The closed-mode read: the last session's close vs the one before it, off
    the closed bars, only when the cached last bar IS that session and the
    snapshot agrees it is final (`KL.verify_last`). Never a tier, never today."""
    lst = last if isinstance(last, dict) else {}
    d = lst.get("date")

    def _blank(state):
        return _today_blank(None, state, mode=MODE_CLOSED, day=d, for_today=False)
    if d is None or str(ref_date or "")[:10] != d:
        return _blank("stale")
    stale, ok = KL.verify_last(ref_close, ref_date, KL.row_or_none(raw))
    if stale:
        return _blank("stale")
    if not ok:
        return _blank("no_print")
    mv = _f(lst.get("move_pct"))
    if mv is None:
        return _blank("no_print")
    out = _blank("read")
    out.update(move_pct=mv, holding=held(mv), print=_r(lst.get("close"), 4),
               prev_close=_r(lst.get("prev_close"), 4), basis=LAST_BASIS)
    return out


def official_prev_close(raw: Optional[dict], ref_close, session) -> Optional[float]:
    """The prior close a live / after-close session move is measured against
    (2026-10-07 critic: NNBR cached 10-06 close 4.025 vs the snapshot's
    official 4.04 -> the card said -0.12%, the real move was -0.50%). The
    snapshot's `prev_day_close` when its day bar is dated the session
    (`drop10_tab.day_from_snapshot` — never an un-rolled overnight snapshot)
    and it agrees with the cached close within `drop10_tab.PREV_CLOSE_TOL_PCT`;
    else the cached close (a split or a bad print is never the base)."""
    from chart_maps import drop10_tab as D10
    ref = _pos(ref_close)
    pdc = _pos((D10.day_from_snapshot(raw, session) or {}).get("prev_close"))
    if ref is None or pdc is None:
        return ref
    if abs(pdc / ref - 1.0) * 100.0 > D10.PREV_CLOSE_TOL_PCT:
        return ref
    return pdc


def today_read(raw: Optional[dict], *, ref_close, ref_date, now, session, phase,
               event: Optional[dict], mode: Optional[str] = None,
               last: Optional[dict] = None) -> dict:
    """TodayRead, on EVERY session (2026-10-07). `basis == "last_close"` is
    NEVER a read — a name with no print is `no_print`, never "+0.00%".
    live = today's print (`KL.anchor_read`); after_close = the snapshot day
    bar's regular-session close (never the after-hours print); closed = the
    last closed session (dated, `for_today` False) — except a T1/T2 day's
    pre-market, which keeps its live pre-market read."""
    m = mode or today_mode(now)["mode"]
    ev = event if isinstance(event, dict) else None
    if m == MODE_CLOSED and not (phase == "pre" and ev is not None):
        return _last_session_read(raw, ref_close=ref_close, ref_date=ref_date, last=last)
    day = _iso(session)

    def _blank(state):
        return _today_blank(ev, state, mode=m, day=day, for_today=True)
    if phase is None:
        return _blank("not_open")
    row = KL.row_or_none(raw)
    if row is None:
        return _blank("no_print")
    stale, ok = KL.verify_last(ref_close, ref_date, row)
    if stale:
        return _blank("stale")
    if not ok:
        return _blank("no_print")
    if m == MODE_AFTER:
        from chart_maps import drop10_tab as D10
        dbar = D10.day_from_snapshot(raw, session)
        px, basis, tape = _pos((dbar or {}).get("last")), "day_close", None
        if px is None:
            return _blank("no_print")
    else:
        px, basis, tape = KL.anchor_read(row, now, session, ref_close)
        if px is None or basis not in ("live", "day_close"):
            return _blank("no_print")
        if basis == "day_close" and phase == "rth":
            basis = DAY_BAR_BASIS      # the day bar is still forming — not a close
    # live / after_close: the official prior close; a data day's pre-market keeps ref_close
    prev = official_prev_close(raw, ref_close, session) if m in (MODE_LIVE, MODE_AFTER) \
        else ref_close
    mv = pct_ret(px, prev)
    if mv is None:
        return _blank("no_print")
    out = _blank("read")
    out.update(move_pct=mv, holding=held(mv), print=_r(px, 4), prev_close=_r(prev, 4),
               basis=basis, tape=tape if basis == "live" else None,
               as_of_et=_print_as_of(row) if basis == "live" else None)
    return out


# ---------------------------------------------------------------------------
# 🚀 sales + EPS growth (PURE) — the latest quarter vs the same quarter a year earlier
# ---------------------------------------------------------------------------
def _yoy_base(series, min_base) -> tuple:
    """(pct, base_state, base) — `qoq._seq_pct` is the engine, slot 0 vs
    slot `qoq.YOY_GAP` of the newest-first series."""
    s = list(series) if isinstance(series, (list, tuple)) else []
    cur = qoq._f(s[0]) if s else None
    base = qoq._f(s[qoq.YOY_GAP]) if len(s) > qoq.YOY_GAP else None
    pct, state = qoq._seq_pct(cur, base, min_base)
    return pct, state, base


_BASE_WORD = {qoq.BASE_OK: "ok", qoq.BASE_NON_POSITIVE: "non_positive",
              qoq.BASE_TOO_SMALL: "too_small", qoq.BASE_UNKNOWN: "unknown"}


def _as_of_day(v) -> Optional[str]:
    if isinstance(v, datetime):
        return KL._et(v if v.tzinfo else v.replace(tzinfo=timezone.utc)).date().isoformat()
    x = _pos(v)
    if x is None:
        return None
    try:
        return datetime.fromtimestamp(x, tz=KL.ET).date().isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _growth_blank() -> dict:
    return {"state": "no_doc", "period": None, "year_ago_period": None, "source": None,
            "sales_yoy_pct": None, "sales_stored_pct": None, "sales_base": "unknown",
            "sales_year_ago": None, "sales_ranked": False,
            "eps_yoy_pct": None, "eps_stored_pct": None, "eps_base": "unknown",
            "eps_year_ago": None, "eps_agrees": None, "eps_ranked": False,
            "score": None, "legs": 0, "as_of": None,
            # 2026-10-07 b
            "sales_series_pct": None, "eps_series_pct": None, "sales_agrees": None,
            "sales_reason": "no_doc", "eps_reason": "no_doc", "eps_year_ago_ni": None,
            "sales_latest": None,
            "latest_idx": None, "expected_idx": None, "etf": False,
            "gap": None, "bars": None, "massive_unused": False,
            # 2026-10-08 — which revenue line the sales leg is on
            "sales_line": None, "sales_line_words": None, "sales_line_note": None}


def _card_state(out: dict, state: str) -> dict:
    """A card-level state copies into both legs (neither ranks)."""
    out.update(state=state, sales_reason=state, eps_reason=state,
               sales_ranked=False, eps_ranked=False, sales_yoy_pct=None, eps_yoy_pct=None)
    return out


def expected_quarter_idx(today: date) -> int:
    """`y*4 + (q-1)` of the quarter whose filings are due by `today`
    (`period_freshness.expected_13f_quarter` — the 13F cadence, one home)."""
    y, q = PF.quarter_of(PF.expected_13f_quarter(today))
    return int(y) * 4 + (int(q) - 1)


def growth_read(f: Optional[dict], *, today: Optional[date] = None,
                is_etf: bool = False) -> dict:
    """GrowthRead off one `research.decision_snapshot` row. A leg is RANKED
    only off a material year-ago base — EPS `EPS_MIN_BASE` (via `qoq._seq_pct`),
    sales `bonde._rev_base` ("ok" = at or over `REV_MIN_BASE`) — AND a stored
    figure that agrees with the company's own quarterly series (his rule #7;
    the sales leg obeys it while `SALES_AGREE_REQUIRED`). Every leg that does
    not rank carries a reason code (2026-10-07 b), so no surface prints a bare
    dash. Card-level states: etf / no_doc / period_mismatch / stale_filings /
    no_figures. PURE."""
    out = _growth_blank()
    out["etf"] = bool(is_etf)
    has_doc = isinstance(f, dict)
    if has_doc:
        src = f.get("_source")
        periods = f.get("q_period_series") if isinstance(f.get("q_period_series"), list) else None
        ya = qoq.HEADLINE_PAIR[1]
        out.update(source=src if isinstance(src, str) else None,
                   period=qoq.period_label(periods[0], src) if periods else None,
                   year_ago_period=(qoq.period_label(periods[ya], src)
                                    if periods and len(periods) > ya else None),
                   as_of=_as_of_day(f.get("cached_at")))
    # 1. an ETF / fund files no company financials — never ranked, even with figures
    if is_etf:
        return _card_state(out, "etf")
    # 2. no research document
    if not has_doc:
        return _card_state(out, "no_doc")
    # 3. quarters not four apart on file — the labels, AND (2026-10-07 c) the
    #    stored period end dates when the doc carries them (`qoq.ends_year_apart`:
    #    CRDO's labels are four apart, its quarters 455 days)
    ends = f.get(qoq.END_SERIES_KEY) if isinstance(f.get(qoq.END_SERIES_KEY), list) else None
    if qoq.period_ok(periods, ends=ends) is False:
        return _card_state(out, "period_mismatch")
    # 4. a latest filing a year or more behind the quarter now due (recycled ticker / provider gap)
    li = qoq._int_or_none(periods[0]) if periods else None
    out["latest_idx"] = li
    if today is not None:
        ei = expected_quarter_idx(today)
        out["expected_idx"] = ei
        if li is not None and ei - li >= STALE_FILING_QUARTERS:
            return _card_state(out, "stale_filings")
    # 5. sales — the 2-dp spine figure first, canslim's 1-dp one as the fallback
    sales = f.get("sales") if isinstance(f.get("sales"), dict) else {}
    s_st, tol = _r(f.get("rev_growth_q_pct")), PCT_AGREE_TOL
    if s_st is None:
        s_st, tol = _r(sales.get("growth_yoy_pct")), PCT_AGREE_TOL_1DP
    rev = f.get("rev_q_series") if isinstance(f.get("rev_q_series"), list) else []
    s_ser = qoq.yoy_pct(rev)
    rb = SB._rev_base({"fundamentals": f})
    s_base = rb.get("base_state") if rb.get("base_state") in (
        "ok", "non_positive", "too_small", "unknown") else "unknown"
    s_v, s_rk, s_why, s_ag = None, False, "not_filed", None
    if s_base == "non_positive":
        s_why = "year_ago_loss"
    elif s_base == "too_small":
        s_why = "year_ago_too_small"
    elif s_base == "unknown":
        slot0 = _f(rev[0]) if rev else None
        slot4 = _f(rev[qoq.YOY_GAP]) if len(rev) > qoq.YOY_GAP else None
        if s_st is not None:
            s_v, s_why = s_st, "no_series"
        elif slot0 is not None and slot4 is None:
            s_why = "year_ago_missing"
    else:                                                   # base ok
        if s_st is None and s_ser is not None:
            s_v, s_why = s_ser, "stored_missing"
        elif s_st is not None and s_ser is not None:
            s_ag = qoq.pct_agrees(s_st, s_ser, tol)
            s_v = s_st
            if s_ag is True:
                s_why, s_rk = None, True
            else:
                s_why, s_rk = "stored_disagrees", not SALES_AGREE_REQUIRED
        elif s_st is not None:
            s_v, s_why = s_st, "no_series"
    # 5b. the revenue line (2026-10-08) — after the rule reasons, which keep priority.
    #     A held line (a ledger note) or an undetermined one NEVER ranks, even when
    #     the stored figure agrees with its series; a legacy doc (no rev_line*) is untouched.
    #     `rev_line` is the newest FILED slot's line, so it is never "undetermined" on a
    #     written doc — the hole lives in `rev_line_series` (2026-10-08 critic): the latest
    #     or the year-ago slot on LINE_UNDETERMINED is read here, per slot.
    line, note, mixed = f.get("rev_line"), f.get("rev_line_note"), f.get("rev_line_mixed")
    line = line if isinstance(line, str) and line else None
    note = note if isinstance(note, str) and note else None
    l_ser = f.get("rev_line_series") if isinstance(f.get("rev_line_series"), list) else []
    undet = line == MF.LINE_UNDETERMINED or any(
        len(l_ser) > i and l_ser[i] == MF.LINE_UNDETERMINED for i in (0, qoq.YOY_GAP))
    if s_why not in RULE_REASONS:
        if note or undet:
            s_why, s_rk = "line_unverified", False
            s_v = s_st if s_st is not None else s_ser
        elif mixed and not (len(rev) > qoq.YOY_GAP and _f(rev[qoq.YOY_GAP]) is not None):
            s_why, s_rk, s_v = "line_mixed", False, None
    out.update(sales_line=line, sales_line_words=MF.LINE_WORDS.get(line) if line else None,
               sales_line_note=note or (MF.LINE_WORDS[MF.LINE_UNDETERMINED] if undet else None))
    out.update(sales_stored_pct=s_st, sales_base=s_base, sales_year_ago=_f(rb.get("base_rev")),
               sales_latest=_f(rb.get("latest_rev")),
               sales_yoy_pct=s_v, sales_ranked=bool(s_rk), sales_series_pct=s_ser,
               sales_agrees=s_ag, sales_reason=s_why)
    # 6. EPS — ranked only when its year-ago base is material AND its own series agrees
    e_st = _r(f.get("q_eps_growth_pct"))
    eps = f.get("eps_q_series") if isinstance(f.get("eps_q_series"), list) else []
    pct, st, b = _yoy_base(eps, EPS_MIN_BASE)
    e_base = _BASE_WORD.get(st, "unknown")
    e_v, e_rk, e_why, agrees, ni_ya = None, False, "not_filed", None, None
    if e_base == "non_positive":
        e_why = "year_ago_loss"
    elif e_base == "too_small":
        e_why = "year_ago_too_small"
    elif e_base == "unknown":
        ni = f.get("ni_q_series") if isinstance(f.get("ni_q_series"), list) else []
        ni_b = _f(ni[qoq.YOY_GAP]) if len(ni) > qoq.YOY_GAP else None
        e0 = _f(eps[0]) if eps else None
        if ni_b is not None and ni_b <= 0:
            e_why, ni_ya = "year_ago_loss", ni_b            # DISPLAY ONLY — never a %, never ranked
        elif e_st is not None:
            e_v, e_why = e_st, "no_series"
        elif e0 is not None:
            e_why = "year_ago_missing"
    else:                                                   # base ok
        if e_st is None and pct is not None:
            e_v, e_why = pct, "stored_missing"
        elif e_st is not None and pct is not None:
            agrees = qoq.pct_agrees(e_st, pct, PCT_AGREE_TOL)
            e_v = e_st
            if agrees is True:
                e_why, e_rk = None, True
            else:
                e_why = "stored_disagrees"
        elif e_st is not None:
            e_v, e_why = e_st, "no_series"
    out.update(eps_stored_pct=e_st, eps_base=e_base, eps_year_ago=_f(b), eps_yoy_pct=e_v,
               eps_agrees=agrees, eps_ranked=bool(e_rk), eps_series_pct=pct,
               eps_reason=e_why, eps_year_ago_ni=ni_ya)
    # 7. card state
    figure = s_v is not None or e_v is not None
    out["state"] = ("read" if figure or s_why != "not_filed" or e_why != "not_filed"
                    else "no_figures")
    # 2026-10-07 c — WHICH "no figures" (critic, MEASURED: 89 of 144 such cards
    # have Massive quarterly filings since 2025-06). A doc whose research run
    # fell back to yfinance (`canslim._from_hybrid`: Massive answered no EPS
    # figure, or failed) never stored Massive's quarters — a refresh can fill
    # it. Only a doc where Massive's own answer was stored and empty is
    # "neither provider".
    out["massive_unused"] = bool(out["state"] == "no_figures" and src == "yfinance")
    return out


def coverage_class(g: Optional[dict], *, bars, min_bars) -> str:
    """The ONE gap class of a card's GrowthRead (first match wins). PURE."""
    g = g if isinstance(g, dict) else {}
    legs = int(g.get("legs") or 0) if _f(g.get("score")) is not None else 0
    st = g.get("state")
    if legs >= 2:
        return "two_legs"
    if legs == 1:
        return "one_leg"
    if st == "etf":
        return "etf"
    if st == "no_doc":
        return "new_listing" if (bars is not None and int(bars) < int(min_bars)) else "not_researched"
    if st == "period_mismatch":
        return "period_gap"
    if st == "stale_filings":
        return "stale_filings"
    why = (g.get("sales_reason"), g.get("eps_reason"))
    if any(w in PENDING_REASONS for w in why):
        return "pending"
    if any(w in RULE_REASONS for w in why):
        return "by_rule"
    if any(w in LINE_REASONS for w in why):
        return REVENUE_LINE_CLASS
    if "year_ago_missing" in why:
        return "year_ago_missing"
    if g.get("massive_unused"):
        return "massive_unused"
    return "no_filings"


COVERAGE_CLASSES = ("two_legs", "one_leg", "pending", "by_rule", REVENUE_LINE_CLASS) + GAP_ORDER


def _pending_legs(g: dict) -> int:
    n = 0
    for leg in ("sales", "eps"):
        if g.get(leg + "_reason") in PENDING_REASONS and not g.get(leg + "_ranked"):
            n += 1
    return n


def _by_adv(items: list) -> list:
    """[(sym, adv50)] -> symbols, adv50 desc (None last), then symbol."""
    return [s for s, _a in sorted(items, key=lambda t: (_f(t[1]) is None, -(_f(t[1]) or 0.0), t[0]))]


def growth_coverage(reads, *, min_bars, ttl_days) -> dict:
    """What growth is on file across the memo's cards, by gap class. `reads` =
    {sym: closed read with "growth" + "adv50"}. Identity: sum(classes) == n ==
    len(reads). PURE."""
    items = list(reads.items()) if isinstance(reads, dict) else []
    classes = {k: 0 for k in COVERAGE_CLASSES}
    members: dict = {k: [] for k in COVERAGE_CLASSES}
    pend: list = []
    plegs = n_doc = 0
    asofs: dict = {}
    for sym, rd in items:
        rd = rd if isinstance(rd, dict) else {}
        g = rd.get("growth") if isinstance(rd.get("growth"), dict) else {}
        cls = g.get("gap") or coverage_class(g, bars=rd.get("bars"), min_bars=min_bars)
        if cls not in classes:
            cls = "no_filings"
        classes[cls] += 1
        members[cls].append((sym, rd.get("adv50")))
        pl = _pending_legs(g)
        plegs += pl
        if pl:
            pend.append((sym, rd.get("adv50")))
        if g.get("state") != "no_doc" and not (g.get("state") == "etf" and not g.get("as_of")):
            n_doc += 1
        a = g.get("as_of")
        if a:
            asofs[a] = asofs.get(a, 0) + 1
    asof = max(sorted(asofs), key=lambda k: asofs[k]) if asofs else None
    return {"n": len(items), "classes": classes,
            "top": {k: _by_adv(v)[:GROWTH_GAP_TOP] for k, v in members.items() if v},
            "pending_legs": plegs, "pending_top": _by_adv(pend)[:GROWTH_GAP_TOP],
            "asof": asof, "asof_n": int(asofs.get(asof, 0)) if asof else 0,
            "n_doc": n_doc, "min_bars": int(min_bars), "ttl_days": int(ttl_days)}


def score_growth(growths: list) -> None:
    """IN PLACE: `score` / `legs` off `qoq.score_board` (the breakouts board's
    equal-weight percentile blend) over the RANKED legs only."""
    growths = [g for g in (growths or []) if isinstance(g, dict)]
    tmp = [{"i": g.get("eps_yoy_pct") if g.get("eps_ranked") else None,
            "g": g.get("sales_yoy_pct") if g.get("sales_ranked") else None} for g in growths]
    qoq.score_board(tmp, income_key="i", growth_key="g", out_key="s")
    for g, t in zip(growths, tmp):
        g["score"], g["legs"] = _f(t["s"]), int(t["qoq_legs"])


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
        return ((0 if td.get("state") == "read" and mv is not None else 1, -(mv or 0.0))
                + _tier_key(res.get("t1")) + (sym,))          # ties: the T1 hold rate
    if sort == SORT_GROWTH:
        # his YES (2026-10-07 b): BOTH ranked legs first, then one ranked leg (an
        # EPS leg before a sales leg — shipped #8 kept), then none
        g = res.get("growth") or {}
        sc = _f(g.get("score"))
        legs = int(g.get("legs") or 0) if sc is not None else 0
        block = 0 if legs >= 2 else (1 if legs == 1 else 2)
        return ((block, not bool(g.get("eps_ranked")), -(sc or 0.0))
                + _tier_key(res.get("t1")) + (sym,))
    return _tier_key(res.get("t1")) + (sym,)          # SORT_T1, "default" and unknown keys


def resolve_sort(sort, *, mode, n_read, n_growth) -> tuple:
    """(effective key, sort_unavailable | None). `default` RESOLVES per request:
    today's move once the session (live / after the close) has a print, else
    the T1 hold rate. The served key is always an explicit one."""
    req = sort if sort in TAB_SORTS else DEFAULT_SORT_KEY
    dflt = SORT_TODAY if (mode in (MODE_LIVE, MODE_AFTER) and int(n_read or 0) > 0) else SORT_T1
    if req == DEFAULT_SORT_KEY:
        return dflt, None
    if req == SORT_TODAY and not int(n_read or 0):
        return SORT_T1, TODAY_SORT_NO_READ
    if req == SORT_GROWTH and not int(n_growth or 0):
        return dflt, GROWTH_SORT_UNAVAILABLE
    return req, None


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
def growth_rule_line() -> str:
    """The 🚀 rule, built from the constants at call time (2026-10-07 b)."""
    return (f"{GROWTH_MARK} Sales + EPS growth = the latest reported quarter against the same "
            "quarter a year earlier. Order: names ranked on BOTH legs first, then one leg (an "
            "EPS leg before a sales leg), then none; within a block each leg's percentile is "
            "averaged — the breakouts board's blend. Never ranked: a year-ago EPS under "
            f"${EPS_MIN_BASE:.2f} or a year-ago loss, a year-ago revenue under "
            f"${REV_MIN_BASE / 1e6:g}M or at or under zero, quarters not a year apart on file, "
            f"a latest filing {STALE_FILING_QUARTERS} or more quarters past due, an ETF/fund, "
            "and a stored figure that is missing or disagrees with its own quarterly series "
            f"(shown with {NOT_RANKED_MARK}). UNMEASURED — an order, not a forecast.")


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
        (f"{TODAY_MARK} Today's move = the price against the prior session's close: live in "
         "market hours, the regular-session close after it, and before the open, overnight "
         "and on weekends the last session's close against the one before it, labelled with "
         "its date (closed bars, checked against the snapshot). On a T1/T2 day the card also "
         "says T1/T2, and its pre-market print is read live. The same "
         f"{HOLD_MAX_DROP_PCT:g}% line colours it."),
        ("Default order: today's move, biggest gain first, once the session has a print "
         f"(market hours and after the close); before that, {MARK} T1 hold rate. A name with "
         "no print sorts last; ties go to the T1 hold rate. The "
         f"{TODAY_MARK} line counts every name read, before the boxes and the liquidity "
         "floor."),
        growth_rule_line(),
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
            "vol_avg_bars": int(VOL_AVG_BARS), "benchmark": BENCH,
            "eps_min_base": float(EPS_MIN_BASE), "rev_min_base": float(REV_MIN_BASE),
            "stale_filing_quarters": int(STALE_FILING_QUARTERS),
            "sales_agree_required": bool(SALES_AGREE_REQUIRED),
            "lines": lines}


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
        # Only the kinds the measured history uses (FRED kinds + FOMC decisions):
        # Fed-calendar rows (minutes, Beige, Chair) never make a T1/T2 day here.
        if isinstance(e, dict) and str(e.get("date") or "")[:10] == s_iso \
                and e.get("tier") in (1, 2) and e.get("kind") in macro_calendar.HISTORY_KINDS:
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
        if not isinstance(e, dict) or e.get("tier") != 1 \
                or e.get("kind") not in macro_calendar.HISTORY_KINDS:
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


def _etf_set(syms) -> set:
    """Every ETF / fund the app already knows — the static ETF universe, the RS
    anchors, the pinned demand ETFs and the etf_info cache (ONE projected read,
    never a fetch). Each source fails to set() on its own."""
    out: set = set()
    try:
        out |= {str(s).upper() for s in (universe.fetch_etf_universe() or [])}
    except Exception:                                           # noqa: BLE001
        pass
    try:
        out |= {str(s).upper() for s in universe.RS_ANCHORS}
    except Exception:                                           # noqa: BLE001
        pass
    try:
        from supply_demand import demand_reentry as D
        out |= {str(s).upper() for s in D.PINNED_ETFS}
    except Exception:                                           # noqa: BLE001
        pass
    try:
        from sepa import etf_info
        out |= set(etf_info.cached_etf_set(syms) or ())
    except Exception:                                           # noqa: BLE001
        pass
    return out


def build(universe_name: str, session: date, *, universe_fn=None, frames_fn=None,
          events_fn=None, calendar_fn=None, fund_fn=None, etf_fn=None) -> dict:
    """The closed-bar half. ONE `bulk_cached_frames(syms + [BENCH, EW_BENCH])`,
    ONE `past_events`, ONE `get_macro_calendar()`, ONE
    `research.decision_snapshot(syms)` (warm thread only). Raises only when
    frames come back empty for a non-empty universe."""
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
    frames = frames_fn(syms + [b for b in (BENCH, EW_BENCH) if b not in seen]) or {}
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

    # the equal-weight benchmark (the market line's second number)
    ew = {"symbol": EW_BENCH, "ref_close": None, "ref_date": None, "last_session": None}
    try:
        edf = frames.get(EW_BENCH)
        closed_e = KL.closed_frame(edf, session) if edf is not None else None
        if closed_e is not None and len(closed_e):
            e_closes = closes_by_day(closed_e)
            e_last = KL._norm_index(closed_e)[-1].date().isoformat()
            ew.update(ref_close=_f(closed_e["close"].iloc[-1]), ref_date=e_last,
                      last_session=last_session_read(e_closes, trading_days, need))
    except Exception as exc:                                    # noqa: BLE001
        log.debug("resiliency tab: %s read failed: %s", EW_BENCH, type(exc).__name__)

    # 🚀 the latest quarter's sales + EPS growth — ONE projected Mongo read, here
    # in the warm thread only (never on a request)
    fund_error = None
    try:
        if fund_fn is None:
            from sepa import research
            fund_fn = research.decision_snapshot
        fund = fund_fn(syms) or {}
        if not isinstance(fund, dict):
            fund = {}
    except Exception as exc:                                    # noqa: BLE001
        fund, fund_error = {}, type(exc).__name__               # never the text (keys)
    from sepa import research as _research               # lazy (hermetic suite)
    try:
        etfs = set((etf_fn or _etf_set)(list(reads)) or ())
    except Exception as exc:                                    # noqa: BLE001
        log.debug("resiliency tab: ETF set unavailable: %s", type(exc).__name__)
        etfs = set()
    for sym, rd in reads.items():
        rd["growth"] = growth_read(fund.get(sym), today=session, is_etf=sym in etfs)
    score_growth([rd["growth"] for rd in reads.values()])
    min_bars = int(_research.MIN_RESEARCH_BARS)
    ttl_days = int(_research.CACHE_TTL_SEC // 86400)
    for rd in reads.values():
        g = rd["growth"]
        g["gap"] = coverage_class(g, bars=rd.get("bars"), min_bars=min_bars)
        g["bars"] = rd.get("bars")
    growth_cov = growth_coverage(reads, min_bars=min_bars, ttl_days=ttl_days)

    now_ts = time.time()
    return {"syms": syms, "reads": reads, "events_summary": events_summary,
            "session_events": session_events, "next_t1": next_t1,
            "sessions": sessions,
            "bench": {"rets": bench_rets,
                      "ref_close": bench_closes[trading_days[-1]] if trading_days else None,
                      "ref_date": trading_days[-1] if trading_days else None,
                      "last_session": last_session_read(bench_closes, trading_days, need)},
            "ew": ew,
            "fund_summary": {"available": bool(fund) and fund_error is None, "n": len(fund),
                             "error": fund_error},
            "growth_coverage": growth_cov,
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
    return {"t1": t1, "t2": t2, "bars": int(len(closed)),
            "sigma_pct": sigma_pct(closes, trading_days),
            "beta": beta(closes, bench_closes, trading_days), "eod": eod,
            "ref_close": _f(closed["close"].iloc[-1]), "ref_date": last_day.isoformat(),
            "adv50": _f(qb.avg_dollar_vol(closed)),
            "avg_vol_session": MB.avg_volume_before(closed, session),
            "stale_note": stale_note,
            "last_session": last_session_read(closes, trading_days, need)}


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
              "pre_read", "pre_pass", "pre_no_baseline", "eod_session",
              "today_read", "today_up", "today_stale", "growth_ranked", "growth_eps_ranked")


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
    tm = today_mode(now_et)
    t_mode = tm["mode"]
    data_pre = ph == "pre" and event is not None
    counts = {k: 0 for k in COUNT_KEYS}
    today_c = {"read": 0, "holding": 0, "down": 0, "no_print": 0, "stale": 0, "up": 0}
    moves: list = []
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
                        now=now_et, session=session, phase=ph, event=event, mode=t_mode,
                        last=rd.get("last_session"))
        if rd.get("stale_note") and tr["state"] == "read":
            tr = _today_blank(event if tr.get("for_today") else None, "stale",
                              mode=tr.get("mode"), day=tr.get("day"),
                              for_today=bool(tr.get("for_today")))
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
        gr = rd.get("growth") if isinstance(rd.get("growth"), dict) else growth_read(None)
        res = {"t1": rd.get("t1"), "t2": rd.get("t2"), "today": tr, "eod": eod, "pre": pr,
               "growth": gr,
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
        # 📅 counts on EVERY session (2026-10-07), the whole pool before the boxes
        if tr["state"] == "read":
            today_c["read"] += 1
            today_c["holding" if tr["holding"] else "down"] += 1
            mv = _f(tr.get("move_pct"))
            if mv is not None:
                moves.append(mv)
                today_c["up"] += int(mv > 0)
        elif tr["state"] == "no_print":
            today_c["no_print"] += 1
        elif tr["state"] == "stale":
            today_c["stale"] += 1
        counts["growth_ranked"] += int(_f(gr.get("score")) is not None)
        counts["growth_eps_ranked"] += int(bool(gr.get("eps_ranked")))
        pool.append({"symbol": sym, "ref_close": rd.get("ref_close"), "adv50": rd.get("adv50"),
                     "resiliency": res, "res_filter": tf})
    counts["today_read"] = today_c["read"]
    counts["today_up"] = today_c["up"]
    counts["today_stale"] = today_c["stale"]
    filters = filters_block([r["res_filter"] for r in pool], act, pool=len(pool), mode=md,
                            study=study_block())
    rows = [r for r in pool if DMT.passes(r["res_filter"], act, md)]
    eff, sort_unavailable = resolve_sort(sort, mode=t_mode, n_read=today_c["read"],
                                         n_growth=counts["growth_ranked"])
    rows.sort(key=lambda r: order_key(r, eff))
    # today summary (the benchmarks' own reads) — ALWAYS the same keys
    b = entry.get("bench") or {}
    spy = today_read(raw.get(BENCH), ref_close=b.get("ref_close"), ref_date=b.get("ref_date"),
                     now=now_et, session=session, phase=ph, event=event, mode=t_mode,
                     last=b.get("last_session"))
    ew = entry.get("ew") or {}
    rsp = today_read(raw.get(EW_BENCH), ref_close=ew.get("ref_close"),
                     ref_date=ew.get("ref_date"), now=now_et, session=session, phase=ph,
                     event=event, mode=t_mode, last=ew.get("last_session"))
    spy_ok = spy["state"] == "read"
    today = {"event_day": event is not None, "session": session.isoformat(),
             "t1": list(sev.get("t1") or []) if event is not None else [],
             "t2": list(sev.get("t2") or []) if event is not None else [],
             "tier": int(sev["tier"]) if event is not None else None,
             "next_t1": copy.deepcopy(entry.get("next_t1")),
             "mode": t_mode,
             "day": session.isoformat() if (t_mode != MODE_CLOSED or data_pre) else tm["day"],
             "data_pre": bool(data_pre), "half_day": bool(tm["half_day"]),
             "spy_move_pct": spy.get("move_pct") if spy_ok else None,
             "spy_tape": spy.get("tape") if spy_ok else None,
             "spy_as_of_et": spy.get("as_of_et") if spy_ok else None,
             "spy_basis": spy.get("basis") if spy_ok else None,
             "rsp_move_pct": rsp.get("move_pct") if rsp["state"] == "read" else None,
             "spy_state": spy["state"], "rsp_state": rsp["state"],
             "median_move_pct": _r(statistics.median(moves)) if moves else None,
             **today_c}
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
    mv = _f(td.get("move_pct"))
    # `event_day` is kept for the call sites; the 📅 pill reads on EVERY session (2026-10-07)
    if td.get("state") == "read" and mv is not None:
        if td.get("tier") in (1, 2) and td.get("for_today"):
            fmt = TODAY_HOLD_FMT if td.get("holding") else TODAY_DOWN_FMT
            text = fmt.format(tier=int(td["tier"]), move=mv)
        elif td.get("basis") == LAST_BASIS:
            text = TODAY_LAST_FMT.format(day=KL._day_mmdd(td.get("day"), weekday=True), move=mv)
        else:
            text = TODAY_PLAIN_FMT.format(move=mv)
        out.append({"text": text, "tone": "good" if td.get("holding") else "warn"})
    out.extend(filter_badges(tf, active))
    out.append({"text": growth_chip(res.get("growth")), "tone": "muted"})
    return out


def _gp(v) -> str:
    x = _f(v)
    return "—" if x is None else f"{x:+,.1f}%"


def _usd(x) -> str:
    v = _f(x)
    if v is None:
        return "—"
    return f"{'-' if v < 0 else ''}${abs(v):,.2f}"


def _research_limits() -> tuple:
    """(MIN_RESEARCH_BARS, TTL days) from `sepa.research` — one home, lazy."""
    from sepa import research as _research
    return int(_research.MIN_RESEARCH_BARS), int(_research.CACHE_TTL_SEC // 86400)


def _usd_short(x) -> str:
    """$8.97B / $1.90B / $23.0M / $512.0K / $900 — sign first ("-$23.0M")."""
    v = _f(x)
    if v is None:
        return "n/a"
    from decimal import ROUND_HALF_UP, Decimal
    a, sg = Decimal(repr(abs(v))), ("-" if v < 0 else "")

    def _q(x: Decimal, dp: str) -> str:                     # half-up: $8.965B -> $8.97B
        return f"{x.quantize(Decimal(dp), rounding=ROUND_HALF_UP):,}"
    if a >= Decimal("1e9"):
        return f"{sg}${_q(a / Decimal('1e9'), '0.01')}B"
    if a >= Decimal("1e6"):
        return f"{sg}${_q(a / Decimal('1e6'), '0.1')}M"
    if a >= Decimal("1e3"):
        return f"{sg}${_q(a / Decimal('1e3'), '0.1')}K"
    return f"{sg}${_q(a, '1')}"


def _cal_label(idx) -> Optional[str]:
    """'Q2 2026' for a calendar quarter index (y*4 + q-1)."""
    return qoq.period_label(idx, "yfinance")


def _pct1(v: float) -> str:
    """'+19.3%' from 19.25 — 1 dp, half away from zero (a 2-dp stored figure
    never prints its banker's-rounded neighbour)."""
    from decimal import ROUND_HALF_UP, Decimal
    d = Decimal(repr(float(v))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{d:+,}%"


def _leg_token(g: dict, leg: str) -> str:
    """One leg of the chip — a figure (`*` when shown, not ranked) or a reason
    in at most three words. NEVER a bare dash."""
    v = _f(g.get(leg + "_yoy_pct"))
    why = g.get(leg + "_reason")
    if v is not None:
        return _pct1(v) + ("" if g.get(leg + "_ranked") else NOT_RANKED_MARK)
    if why == "year_ago_loss":
        # revenue at or under $0 is not a loss (57 of 59 such sales legs read
        # exactly $0 — pre-revenue names; 2026-10-07 c)
        return "yr-ago loss" if leg == "eps" else SALES_NO_REV_TOKEN
    if why == "year_ago_too_small":
        return (f"yr-ago <${EPS_MIN_BASE:.2f}" if leg == "eps"
                else f"yr-ago <${REV_MIN_BASE / 1e6:g}M")
    if why == "year_ago_missing":
        return "yr-ago n/a"
    if why in LINE_REASONS:
        return "line n/a"
    return "not filed"


def _card_reason(g: dict) -> Optional[str]:
    """The chip reason for a card-level state, or None for a read."""
    st = g.get("state")
    if st == "etf":
        return "ETF/fund, no filings"
    if st == "no_doc":
        min_bars, ttl = _research_limits()
        gap = g.get("gap")
        if gap == "new_listing" and g.get("bars") is not None:
            return f"new listing, {int(g['bars']):,} bars, not researched"
        if gap == "not_researched":
            return f"not researched in {ttl} days"
        return "no research on file"
    if st == "no_figures":
        return GROWTH_MASSIVE_UNUSED if g.get("massive_unused") else GROWTH_NO_FIGURES
    if st == "stale_filings":
        return f"latest filing {g.get('period') or GROWTH_PERIOD_UNKNOWN}, a year or more past due"
    if st == "period_mismatch":
        return GROWTH_MISMATCH
    return None


def growth_chip(g: Optional[dict]) -> str:
    """The IDENT chip. Starts with GROWTH_CHIP_PREFIX; never contains a dash
    placeholder (2026-10-07 b)."""
    g = g if isinstance(g, dict) else growth_read(None)
    why = _card_reason(g)
    if why is not None:
        return GROWTH_CHIP_NONE_FMT.format(reason=why)
    return GROWTH_CHIP_FMT.format(sales=_leg_token(g, "sales"), eps=_leg_token(g, "eps"),
                                  period=g.get("period") or GROWTH_PERIOD_UNKNOWN)


MASSIVE_UNUSED_TEXT = ("the research run fell back to yfinance, which had none; Massive's quarterly "
                       "figures were not used on that run — pending a research refresh (a domestic "
                       "filer usually fills; a foreign filer may stay empty)")
SERIES_WORDS = "the quarterly series on file"        # never "the filings" (2026-10-07 c)
YEAR_AGO_MISSING_TEXT = "the year-ago quarter is not on file (a spin-off, an IPO's first year, or a filing hole)"
REFRESH_TEXT = "it ranks once a research refresh stores it"


def _sales_clause(g: dict) -> str:
    why = g.get("sales_reason")
    ss, sv, ser = _f(g.get("sales_stored_pct")), _f(g.get("sales_yoy_pct")), _f(g.get("sales_series_pct"))
    words, note = g.get("sales_line_words"), g.get("sales_line_note")
    if why == "line_unverified":
        if sv is not None:
            return f"sales {sv:+.2f}% on the provider's {words or 'revenue'} — not ranked: {note}"
        return f"sales: not ranked — {note}"
    if why == "line_mixed":
        return SALES_LINE_MIXED_TEXT
    if why == "year_ago_loss":
        return ("sales: year-ago revenue at or under $0"
                + (f" — the stored {ss:+.2f}% is a sign flip, not growth" if ss is not None else ""))
    if why == "year_ago_too_small":
        return (f"sales: year-ago revenue under ${REV_MIN_BASE / 1e6:g}M"
                + (f" — the stored {ss:+.2f}% is arithmetic, not ranked" if ss is not None else ""))
    if why == "stored_missing" and ser is not None:
        base = _usd_short(g.get("sales_year_ago"))
        latest = _f(g.get("sales_latest"))
        amt = (f" ({_usd_short(latest)} vs {base} a year earlier)" if latest is not None
               else f" (year-ago {base})")
        return (f"sales {ser:+.2f}% from {SERIES_WORDS}{amt} — not ranked: the "
                f"stored figure is missing; {REFRESH_TEXT}")
    if why == "stored_disagrees" and ss is not None and ser is not None:
        tail = ("ranked on the stored figure (the agreement check is off)" if g.get("sales_ranked")
                else "not ranked until they agree")
        return (f"sales {ss:+.2f}% stored vs {ser:+.2f}% from {SERIES_WORDS} — the stored "
                f"figure and the quarterly series disagree; {tail}")
    if why == "no_series" and sv is not None:
        return f"sales {sv:+.2f}% (not ranked — no quarterly series on file to check its base)"
    if why == "year_ago_missing":
        return "sales: " + YEAR_AGO_MISSING_TEXT
    if sv is not None and g.get("sales_ranked"):
        line = g.get("sales_line")
        if line not in (None, MF.LINE_REVENUE) and words:
            return f"sales {sv:+.2f}% ({words})"
        return f"sales {sv:+.2f}%"
    return "sales: no figure on file"


def _eps_clause(g: dict) -> str:
    why = g.get("eps_reason")
    es, ev, ser = _f(g.get("eps_stored_pct")), _f(g.get("eps_yoy_pct")), _f(g.get("eps_series_pct"))
    b = g.get("eps_year_ago")
    if why == "year_ago_loss" and g.get("eps_year_ago_ni") is not None and g.get("eps_base") == "unknown":
        return (f"EPS: the year-ago quarter lost money (net income "
                f"{_usd_short(g.get('eps_year_ago_ni'))}; its EPS is not on file) — never ranked")
    if why == "year_ago_loss":
        return (f"EPS: the year-ago quarter lost money or broke even ({_usd(b)})"
                + (f" — the stored {es:+.2f}% is a sign flip, not growth" if es is not None else ""))
    if why == "year_ago_too_small":
        return (f"EPS: year-ago EPS {_usd(b)} is under the {_usd(EPS_MIN_BASE)} floor"
                + (f" — the stored {es:+.2f}% is arithmetic, not ranked" if es is not None else ""))
    if why == "stored_missing" and ser is not None:
        return (f"EPS {ser:+.2f}% from {SERIES_WORDS} (year-ago {_usd(b)}) — not "
                f"ranked: the stored figure is missing; {REFRESH_TEXT}")
    if why == "stored_disagrees" and ev is not None:
        return (f"EPS {ev:+.2f}% (not ranked — the stored figure and its own quarterly series "
                "disagree" + (f": series {ser:+.2f}%" if ser is not None else "") + ")")
    if why == "no_series" and ev is not None:
        return f"EPS {ev:+.2f}% (not ranked — no quarterly series on file to check its base)"
    if why == "year_ago_missing":
        return "EPS: " + YEAR_AGO_MISSING_TEXT
    if ev is not None and g.get("eps_ranked"):
        return f"EPS {ev:+.2f}% (year-ago {_usd(b)})"
    return "EPS: no figure on file"


def _growth_stat(g: Optional[dict]) -> str:
    g = g if isinstance(g, dict) else growth_read(None)
    st = g.get("state")
    tail = [f"figures cached {g['as_of']}"] if g.get("as_of") else []
    if st == "etf":
        return " · ".join(["ETF/fund — no company filings; never ranked"] + tail)
    if st == "no_doc":
        min_bars, ttl = _research_limits()
        if g.get("gap") == "new_listing" and g.get("bars") is not None:
            return (f"new listing — {int(g['bars']):,} daily bars, fewer than the {min_bars} "
                    "research needs (a new listing, a spin-off or a rename not yet spliced); "
                    "not researched")
        if g.get("gap") == "not_researched":
            return f"not researched — no research stored in the last {ttl} days"
        return "no research on file"
    if st == "no_figures":
        if g.get("massive_unused"):
            return " · ".join([GROWTH_NO_FIGURES + " — " + MASSIVE_UNUSED_TEXT] + tail)
        return " · ".join([GROWTH_NO_FIGURES] + tail)
    if st == "period_mismatch":
        return " · ".join(["the latest quarter and the year-ago quarter on file are not four "
                           "quarters apart — not read"] + tail)
    if st == "stale_filings":
        li, ei = g.get("latest_idx"), g.get("expected_idx")
        n = (int(ei) - int(li)) if (li is not None and ei is not None) else None
        return " · ".join([f"latest filing {g.get('period') or GROWTH_PERIOD_UNKNOWN} is "
                           f"{n if n is not None else 'many'} quarters behind the quarter now "
                           f"due ({_cal_label(ei) or GROWTH_PERIOD_UNKNOWN}) — a recycled "
                           "ticker or a provider gap; never ranked"] + tail)
    p, ya = g.get("period"), g.get("year_ago_period")
    head = f"{p} vs {ya}" if (p and ya) else (p or ya or GROWTH_PERIOD_UNKNOWN)
    return " · ".join([head, _sales_clause(g), _eps_clause(g)] + tail)


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
_TODAY_TEXT_BY_MODE = {(MODE_AFTER, "no_print"): "no trade in today's session — not read"}


def _today_stat(td: dict) -> str:
    by_mode = _TODAY_TEXT_BY_MODE.get((td.get("mode"), td.get("state")))
    if by_mode:
        return by_mode
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
    td = res.get("today") or {}
    if td.get("for_today"):          # was `event_day`: the session's own read, every session
        out.append({"k": "Today", "v": _today_stat(td)})
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
    out.append({"k": GROWTH_STAT_KEY, "v": _growth_stat(res.get("growth"))})
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
        if t.get("mode") == MODE_CLOSED and not t.get("data_pre"):
            # 00:00–04:00 ET on a data day: the 📅 reads are the LAST session's —
            # never printed as this data day's (2026-10-07)
            return txt + f" {_TODAY_TEXT['not_open'][0].upper()}{_TODAY_TEXT['not_open'][1:]}."
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


def market_line(today: Optional[dict]) -> Optional[str]:
    """The served market-context line: SPY, RSP, the median name and n up of n
    read — every universe name read, before the boxes and the floor. The word
    down / up / flat comes ONLY from the median's sign."""
    t = today if isinstance(today, dict) else {}
    m = t.get("mode")
    if not m:
        return None
    if m == MODE_LIVE:
        when = MARKET_LIVE_WHEN + (f" {t['spy_as_of_et']} ET" if t.get("spy_as_of_et") else "")
    elif m == MODE_AFTER:
        from chart_maps import drop10_tab as D10
        close = MB.HALF_DAY_CLOSE_ET if t.get("half_day") else D10.ZE_CLOSE
        when = MARKET_AFTER_WHEN_FMT.format(close=f"{close:%H:%M}")
    elif t.get("data_pre"):
        when = MARKET_PRE_WHEN
    else:
        when = MARKET_LAST_WHEN_FMT.format(day=KL._day_mmdd(t.get("day"), weekday=True))
    stale_text = _TODAY_TEXT["stale"]
    if not int(t.get("read") or 0):
        if int(t.get("stale") or 0):        # host sleep: the cached bars are behind, not "no print"
            return MARKET_STALE_FMT.format(when=when, stale_text=stale_text, n=_n(t.get("stale")))
        return MARKET_EMPTY_FMT.format(when=when)
    med = _f(t.get("median_move_pct"))
    if med is None:
        return MARKET_EMPTY_FMT.format(when=when)

    def _px(v, state):
        if _f(v) is not None:
            return _pct_txt(v)
        return stale_text if state == "stale" else NO_PRINT_WORD
    word = "down" if med < 0 else ("up" if med > 0 else "flat")
    return MARKET_LINE_FMT.format(when=when, bench=BENCH,
                                  spy=_px(t.get("spy_move_pct"), t.get("spy_state")),
                                  ew=EW_BENCH, rsp=_px(t.get("rsp_move_pct"), t.get("rsp_state")),
                                  med=f"{med:+.2f}%", word=word, up=_n(t.get("up")),
                                  n=_n(t.get("read")))


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


def _gap_why(cls: str, cov: dict) -> str:
    """Why a gap class has no ranked growth — built from the constants."""
    return {
        "pending": ("the stored figure is missing, or it and the quarterly series on file "
                    f"disagree — shown with {NOT_RANKED_MARK}, not ranked until a research "
                    "refresh stores a figure that agrees"),
        "by_rule": ("the year-ago quarter lost money or had no revenue, or its EPS is under "
                    f"${EPS_MIN_BASE:.2f} / its revenue under ${REV_MIN_BASE / 1e6:g}M — "
                    "never ranked"),
        "etf": "an ETF or fund files no company financials",
        "new_listing": (f"fewer than {int(cov.get('min_bars') or 0):,} daily bars (a new listing, "
                        "a spin-off or a rename not yet spliced) — research has not run"),
        "not_researched": f"no research stored in the last {int(cov.get('ttl_days') or 0)} days",
        "massive_unused": MASSIVE_UNUSED_TEXT,
        "no_filings": ("the stored research has no quarterly figures from Massive or yfinance "
                       "(often a foreign filer)"),
        "stale_filings": ("the latest quarter on file is a year or more past due — a recycled "
                          "ticker or a provider gap; never ranked"),
        "period_gap": ("the latest quarter and the year-ago quarter on file are not four "
                       "quarters apart"),
        "year_ago_missing": YEAR_AGO_MISSING_TEXT,
        REVENUE_LINE_CLASS: REVENUE_LINE_WHY,
    }[cls]


def growth_line(cov: Optional[dict]) -> Optional[str]:
    """The served 🚀 coverage line (every number served; the FE composes none)."""
    if not isinstance(cov, dict) or not isinstance(cov.get("classes"), dict):
        return None
    c = cov["classes"]
    none = sum(int(c.get(k) or 0) for k in GAP_ORDER)
    bits = [f"{_n(c.get(k))} {GAP_LABEL[k]}" for k in GAP_ORDER if int(c.get(k) or 0)]
    gaps = f" ({', '.join(bits)})" if bits else ""
    asof = (f"most figures cached {cov['asof']}" if cov.get("asof")
            else "no figures cached")
    n_line = int(c.get(REVENUE_LINE_CLASS) or 0)
    line_seg = f" · {_n(n_line)} {REVENUE_LINE_LABEL}" if n_line > 0 else ""
    return (f"{GROWTH_MARK} Growth on file: {_n(c.get('two_legs'))} both legs · "
            f"{_n(c.get('one_leg'))} one leg · {_n(c.get('pending'))} {PENDING_LABEL} · "
            f"{_n(c.get('by_rule'))} {BY_RULE_LABEL}{line_seg} · no figure {_n(none)}{gaps} · of "
            f"{_n(cov.get('n'))} · {_n(cov.get('pending_legs'))} figures marked "
            f"{NOT_RANKED_MARK} wait on a research refresh · {asof}.")


def growth_gaps_block(cov: Optional[dict]) -> Optional[dict]:
    """The fold under the line: one line per gap class with any name, the
    most-traded names first (adv50 desc, at most GROWTH_GAP_TOP)."""
    if not isinstance(cov, dict) or not isinstance(cov.get("classes"), dict):
        return None
    c, top = cov["classes"], cov.get("top") or {}
    labels = {"pending": PENDING_LABEL, "by_rule": BY_RULE_LABEL,
              REVENUE_LINE_CLASS: REVENUE_LINE_LABEL, **GAP_LABEL}
    lines = []
    for k in ("pending", "by_rule", REVENUE_LINE_CLASS) + GAP_ORDER:
        n = int(c.get(k) or 0)
        if not n:
            continue
        names = [str(x) for x in (top.get(k) or [])][:GROWTH_GAP_TOP]
        more = f" +{n - len(names):,} more" if n > len(names) else ""
        lines.append(f"{labels[k]} ({n:,}): {_gap_why(k, cov)} — {', '.join(names)}{more}")
    return {"summary": GROWTH_GAPS_SUMMARY, "lines": lines}


def _block(state: str, *, now: datetime, sort: str, header: str, entry: Optional[dict] = None,
           counts=None, filters=None, today=None) -> dict:
    now_et = KL._et(now)
    session = session_for(now_et)
    study = study_block()
    cov = (entry or {}).get("growth_coverage") if (entry and state == "ready") else None
    cov = cov if isinstance(cov, dict) else None
    return {"state": state, "session": session.isoformat(), "phase": KL.phase(now_et, session),
            "market_closed": _market_closed(now_et), "sort": sort, "header": header,
            "today_line": today_line(today) if today else None,
            "market_line": market_line(today) if today else None,
            "events_line": events_line(entry) if entry else None,
            "rules": rules_block(),
            "events": copy.deepcopy((entry or {}).get("events_summary")) if entry else None,
            "today": today, "counts": dict(counts) if counts is not None else None,
            "filters": filters, "study": study, "note": note_text(study),
            "measured": MEASURED,
            # 🚀 coverage (2026-10-07 b) — the line + fold only on the 🚀 order (Rule #5)
            "growth_coverage": copy.deepcopy(cov) if cov is not None else None,
            "growth_line": growth_line(cov) if (cov is not None and sort == SORT_GROWTH) else None,
            "growth_gaps": (growth_gaps_block(cov) if (cov is not None and sort == SORT_GROWTH)
                            else None),
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


def served_sorts(resolved: str = SORT_T1, *, today_label: str = TODAY_SORT_LABEL) -> list:
    """`default` FIRST, labelled with what it resolved to (the generic Sort
    select shows the URL's `default`), then the five explicit keys."""
    labels = {SORT_TODAY: today_label, SORT_T1: T1_SORT_LABEL, SORT_T2: T2_SORT_LABEL,
              SORT_DOWN: DOWN_SORT_LABEL, SORT_GROWTH: GROWTH_SORT_LABEL}
    head = labels.get(resolved, T1_SORT_LABEL) + DEFAULT_LABEL_SUFFIX
    return ([{"key": DEFAULT_SORT_KEY, "label": head}]
            + [{"key": k, "label": labels[k]}
               for k in (SORT_TODAY, SORT_T1, SORT_T2, SORT_DOWN, SORT_GROWTH)])
