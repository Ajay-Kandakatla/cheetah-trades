"""📅 Runners — the nightly record (2026-11-26, spec watchrun rev 2 §3.4, WP-2 `be-track`).

Ajay 2026-11-26 ~21:40 ET, verbatim: "Ok then add them to our watch list and track them please.. I know he tracks them for
two weeks sometimes.. before he discards them.. Can you do that please".

ONE doc per run in `C.COLL_RUNTRACK` (`_id` = "<run_day>|<SYM>", handle `colls.runtrack_coll`), kept, no TTL. The runs
come from the 📅 runners doc that `runseat.py` keeps: every entry's runs AND every `removed[].entry` whose reason is
"dismissed", "aged" or "blocked" [C5] — a run his × kept off the list (`listed` False) is recorded like any other.

Every night (the 20:15 nightly, one fence after the 🩳 block) each OPEN doc's symbol costs ONE closed-daily-bar read
(`sepa.prices.closed_daily_frame(sym, now=<midnight after the recorded session>, use_cache=False)` — regular hours,
provider-adjusted, nothing cached). The rows run from the run day (day 1) through tonight's session, day `KEEP` last.

The base [C6] is decided by WHERE the seat's peak printed:
  * regular hours → "run_close": the frame's run-day close (and the frame's run-day high) — every bar on one scale;
  * at / after `daytrading.data.ET_RTH_CLOSE` → "run_high": the seat's own high, and ONLY when the frame's run-day close
    equals the seat's stored regular close at 4 decimals (`adjusted` False — equality only, no threshold). That day's
    regular close came BEFORE the run, so `close_vs_run_close_pct` is None on every row of such a doc;
  * anything else → "none": both ratios None, the base note says why.
A 🚩 A+ ring counts as "rang A+ later" only when dated AFTER the run day [C6].

Closing [C7] is on the calendar: a doc is due when its window's last session is recorded; a frame that cannot be read
on a later night closes it anyway ("calendar"), every missing session a `no_bar` row. A closed doc is never fetched
again. `summary` counts only — "x of n", split by rule, late peaks apart, no rate, no rank. UNMEASURED.

Reads come from STORED docs only: the 🧠 tracker (`auto._tracker_docs` per read source, armed turns by
`allrules.first_armed_at`) and the Track record's A+ rows (`runseat.aplus_rings`). No served word says calm, pullback or
bounce (a test reads the constants).
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC

from . import colls as CO
from . import constants as C

log = logging.getLogger("chart_maps.gajjala_watch.runtrack")

ET = ZoneInfo("America/New_York")
UTC = timezone.utc

VERSION = 1                                          # TRANSPORT
STATES = ("open", "closed")
ROW_STATES = ("ok", "no_bar")
READ_KINDS = ("potential", "armed", "aplus")
BASE_KINDS = ("run_close", "run_high", "none")
CLOSED_BY = ("window", "calendar")
SEAT_REASONS = tuple(r for r in C.RUNNERS_SEAT_REASONS if r in ("dismissed", "aged", "blocked"))   # every removal is recorded
BLOCKED = C.RUNNERS_SEAT_REASONS[2]                  # "blocked" — qualified, his × kept it off the list → listed False
KEEP = C.RUNNERS_KEEP_SESSIONS                       # his 10 — the run day is day 1
ROWS_MAX = GC.LEDGER_ROWS_MAX                        # TRANSPORT — the Track record's row cap; every run is still counted
PX_PLACES = 4                                        # the `adjusted` test: equal at 4 decimals (spec §3.4 — equality only)
OUT_KEYS = ("session", "opened", "updated", "closed", "closed_calendar", "reads", "failed", "faults")

# ── served words (all MINE — HIS CALL #15) ───────────────────────────────────────────────────────────────────────
NOTE = "UNMEASURED — every runner that qualified counts, winners and losers, listed or not; it is a record, not a test"
NO_READ = "no read"
READS_FAULT = "reads not on file"
DASH = "—"
TITLE = "📅 Runners — the record"
SYMBOL_TITLE = "📅 {sym} — every run, session by session"
RULE_WORD = {"day": "ran with no A+", "aplus": "ran after an A+"}
SUMMARY_HEAD = "{open} being watched · {closed} finished"
SUMMARY_RULE = " · {rule_word} ({n}): {again} of {n} ran again · {aplus_later} of {n} rang A+ on a later session"
SUMMARY_REG = " · {reg_up} of {reg_n} closed day {keep} above the run-day close"
SUMMARY_LATE = " · ran after the {close} close: {late_up} of {late_n} closed day {keep} above the run's high"
SUMMARY_NO_PRICE = " · {no_price} finished with no price"
EMPTY_TEXT = "Nothing recorded yet — the {at} ET nightly opens a record for every 📅 runner"
ERROR_TEXT = "📅 the runners record could not be read"
OFF_TEXT = "📅 Runners is off"
ASOF_TEXT = "recorded nightly at {at} ET · through {date}"
ASOF_NONE = "recorded nightly at {at} ET"
SHOWN_TEXT = "Showing the newest {lim} of {n} finished runs — every run is counted above."
STATE_OPEN = "being watched · day {n} of {keep}"
STATE_CLOSED = {"window": "finished · day {keep} recorded", "calendar": "finished on the calendar · {k} of {keep} sessions with no daily bar"}
LISTED_WORD = {True: "listed", False: "kept off by your ×"}
YES, NO = "yes", "no"
BASE_NOTE = {
    "run_close": "Base: the {date} regular close {px} and that day's regular high {hi} (the run peaked {at} ET, in regular "
                 "hours). Daily bars, regular hours, provider-adjusted — every number on one scale.",
    "run_high": "Base: the run's own high {px} at {at} ET. It peaked at or after the {close} ET close, so that day's regular "
                "close came before the run and is never a base — the close-vs-run-close column is empty. The next "
                "session's day change still holds the after-hours run.",
    "no_bar": "No base: the daily bars hold no bar of the run day {date}.",
    "no_peak": "No base: the run's peak time is not on file.",
    "no_high": "No base: the run's high is not on file.",
    "rebased": "No base: the run peaked at or after the {close} ET close and the daily bars are on another scale (their {date} "
               "close {fc} is not the stored {rc}) — the run's high and the bars cannot be compared.",
    "no_reg": "No base: the run peaked at or after the {close} ET close and no regular close of {date} is on file to check "
              "the scale of the daily bars.",
    "no_frame": "No base yet: the daily bars have not been read."}
CLOSED_HEADS = [["symbol", "Ticker"], ["run_day", "Ran"], ["rule", "Seat"], ["run_pct", "Run"], ["base", "Base"],
                ["best", "Best high after"], ["last_close", "Day {keep} close vs run-day close"],
                ["last_high", "Day {keep} close vs run high"], ["worst", "Worst low vs run-day close"],
                ["again", "Ran again"], ["aplus_later", "A+ on a later session"], ["listed", "Listed"],
                ["closed_by", "Finished"]]
SESSION_HEADS = [["day_n", "Day"], ["date", "Session"], ["close", "Close"], ["change", "Day change"],
                 ["high", "High"], ["low", "Low"], ["vs_close", "Close vs run-day close"],
                 ["vs_high", "Close vs run high"], ["vol_x", "Volume vs 50-day"], ["reads", "Stored reads"]]
BASE_WORD = {"run_close": "run-day close", "run_high": "run's high (after the close)", "none": "none"}
CLOSED_BY_WORD = {"window": "day {keep}", "calendar": "on the calendar"}


# ── small helpers ────────────────────────────────────────────────────────────────────────────────────────────────
def _fin(x) -> Optional[float]:
    try:
        if isinstance(x, bool) or x is None:
            return None
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _pos(x) -> Optional[float]:
    v = _fin(x)
    return v if v is not None and v > 0 else None


def _ratio(x, base) -> Optional[float]:
    """(x / base − 1) × 100 rounded to 2 decimals; None unless both are finite and base > 0."""
    v, b = _fin(x), _pos(base)
    if v is None or b is None:
        return None
    r = (v / b - 1.0) * 100.0
    return round(r, 2) if math.isfinite(r) else None


def _iso(d) -> Optional[str]:
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    if isinstance(d, str):
        try:
            return date.fromisoformat(d[:10]).isoformat()
        except ValueError:
            return None
    return None


def _as_date(d) -> Optional[date]:
    s = _iso(d)
    return date.fromisoformat(s) if s else None


def _hhmm(t: dtime) -> str:
    return t.strftime("%H:%M")


def _rth_close() -> str:
    from daytrading.data import ET_RTH_CLOSE
    return _hhmm(ET_RTH_CLOSE)


def _utc(x) -> Optional[datetime]:
    if isinstance(x, str) and x:
        try:
            x = datetime.fromisoformat(x)
        except ValueError:
            return None
    return CO.stamp_utc(x)


def _et_hhmm(x) -> Optional[str]:
    t = _utc(x)
    return t.astimezone(ET).strftime("%H:%M") if t is not None else None


def _pct_text(x) -> str:
    from . import runners as RN
    s = RN.pct_show(x)
    return s if s is not None else DASH


def _px_text(x) -> str:
    if _fin(x) is None:
        return DASH
    from chart_maps.gajjala import ledger as L
    return L._px(x)


def _key(run_day, sym) -> str:
    return f"{_iso(run_day)}|{CO.house(sym)}"


# ── the window ───────────────────────────────────────────────────────────────────────────────────────────────────
def window_of(run_day) -> list:
    """The run day + the next KEEP − 1 market days (house calendar), as ISO dates, oldest first. [] when unreadable."""
    d = _as_date(run_day)
    if d is None:
        return []
    from catalysts.medical.reaction import next_market_day
    out = [d]
    while len(out) < KEEP:
        out.append(next_market_day(out[-1]))
    return [x.isoformat() for x in out]


def recorded_session(now: datetime) -> date:
    """The session tonight's record runs through: `nightly.default_session` (today when it trades, else the last market
    day) — and the market day before it when `now` is a trading day still before the regular close (its daily bar is
    not closed; a `--once` run in the day never records a half bar)."""
    from catalysts.medical.reaction import prev_market_day
    from chart_maps.gajjala.nightly import default_session
    from daytrading.data import ET_RTH_CLOSE
    s = default_session(now)
    et = now.astimezone(ET)
    if s == et.date() and et.time() < ET_RTH_CLOSE:
        s = prev_market_day(s)
    return s


# ── the base [C6] ────────────────────────────────────────────────────────────────────────────────────────────────
def _bars(daily_df) -> dict:
    """{ISO date: {open, high, low, close, volume}} of a daily frame; {} for None / empty / unreadable."""
    out: dict = {}
    if daily_df is None or getattr(daily_df, "empty", True):
        return out
    try:
        import pandas as pd
        idx = pd.DatetimeIndex(daily_df.index)
        if idx.tz is not None:
            idx = idx.tz_convert("America/New_York").tz_localize(None)
        cols = {str(c).lower(): c for c in daily_df.columns}
        for i, ts in enumerate(idx):
            row = daily_df.iloc[i]
            out[ts.date().isoformat()] = {k: _fin(row[cols[k]]) if k in cols else None
                                          for k in ("open", "high", "low", "close", "volume")}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("runtrack: daily frame unreadable: %s", type(exc).__name__)
        return {}
    return out


def _seat_high(seat) -> Optional[float]:
    s = seat if isinstance(seat, dict) else {}
    return _pos(s.get("high_px")) if s.get("rule") == C.RUNNERS_SEAT_RULES[1] else _pos(s.get("high"))


def _seat_peak(seat) -> Optional[str]:
    s = seat if isinstance(seat, dict) else {}
    v = s.get("high_et") if s.get("rule") == C.RUNNERS_SEAT_RULES[1] else s.get("peak_et")
    if isinstance(v, str) and len(v) == 5 and v[2] == ":" and v.replace(":", "").isdigit():
        return v
    return None


def base_of(seat, daily_df, run_day) -> dict:
    """The base block — PURE. Keys: kind, price, run_close, run_high, seat_high, peak_et, peak_late, adjusted, note."""
    iso = _iso(run_day)
    bar = _bars(daily_df).get(iso) if iso else None
    seat_high = _seat_high(seat)
    peak_et = _seat_peak(seat)
    close = _rth_close()
    peak_late = (peak_et >= close) if peak_et is not None else None
    reg = _pos((seat or {}).get("reg_close")) if isinstance(seat, dict) else None
    fc = _pos(bar.get("close")) if bar else None
    fh = _pos(bar.get("high")) if bar else None
    adjusted = None if (reg is None or fc is None) else round(fc, PX_PLACES) != round(reg, PX_PLACES)
    out = {"kind": BASE_KINDS[2], "price": None, "run_close": fc, "run_high": fh, "seat_high": seat_high,
           "peak_et": peak_et, "peak_late": peak_late, "adjusted": adjusted, "note": None}
    if peak_et is None:
        out["note"] = BASE_NOTE["no_peak"]
    elif peak_late is False:
        if fc is None:
            out["note"] = BASE_NOTE["no_bar"].format(date=iso)
        else:
            out.update(kind=BASE_KINDS[0], price=fc,
                       note=BASE_NOTE["run_close"].format(date=iso, px=_px_text(fc), hi=_px_text(fh), at=peak_et))
    elif seat_high is None:
        out["note"] = BASE_NOTE["no_high"]
    elif adjusted is False:
        out.update(kind=BASE_KINDS[1], price=seat_high,
                   note=BASE_NOTE["run_high"].format(px=_px_text(seat_high), at=peak_et, close=close))
    elif fc is None:
        out["note"] = BASE_NOTE["no_bar"].format(date=iso)
    elif adjusted is True:
        out["note"] = BASE_NOTE["rebased"].format(close=close, date=iso, fc=_px_text(fc), rc=_px_text(reg))
    else:
        out["note"] = BASE_NOTE["no_reg"].format(close=close, date=iso)
    return out


def _ratio_bases(base) -> tuple:
    """(close base, high base): "run_close" → (frame run-day close, frame run-day high); "run_high" → (None, seat high);
    "none" → (None, None)."""
    b = base if isinstance(base, dict) else {}
    if b.get("kind") == BASE_KINDS[0]:
        return b.get("run_close"), b.get("run_high")
    if b.get("kind") == BASE_KINDS[1]:
        return None, b.get("seat_high")
    return None, None


# ── the rows ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _no_bar_row(iso: str, n: int) -> dict:
    return {"date": iso, "day_n": n, "state": ROW_STATES[1], "close": None, "high": None, "low": None, "volume": None,
            "change_pct": None, "high_pct": None, "low_pct": None, "close_vs_run_close_pct": None,
            "close_vs_run_high_pct": None, "avg_vol_50": None, "vol_x": None, "reads": [], "first_read_et": None}


def session_rows(daily_df, run_day, window, through, base) -> list:
    """One row per window session ≤ `through` (the run day is day 1). A session with no bar → `no_bar` (every number
    None, never a zero). change / high / low % are vs the frame's previous bar's close; the run ratios by `_ratio_bases`;
    `avg_vol_50` = the house `momentum_burst.avg_volume_before`, `vol_x` None when it is None. Reads are filled later."""
    from supply_demand import momentum_burst as MB
    bars = _bars(daily_df)
    days = sorted(bars)
    t = _iso(through)
    cb, hb = _ratio_bases(base)
    out = []
    for n, iso in enumerate(window or [], start=1):
        if t is None or iso > t:
            break
        bar = bars.get(iso)
        if not bar or _pos(bar.get("close")) is None:
            out.append(_no_bar_row(iso, n))
            continue
        prev = [d for d in days if d < iso]
        pc = _pos(bars[prev[-1]].get("close")) if prev else None
        avg = MB.avg_volume_before(daily_df, iso)
        avg = _pos(avg)
        vol = _fin(bar.get("volume"))
        vx = round(vol / avg, 2) if (vol is not None and avg is not None) else None
        out.append({"date": iso, "day_n": n, "state": ROW_STATES[0], "close": bar.get("close"), "high": bar.get("high"),
                    "low": bar.get("low"), "volume": vol, "change_pct": _ratio(bar.get("close"), pc),
                    "high_pct": _ratio(bar.get("high"), pc), "low_pct": _ratio(bar.get("low"), pc),
                    "close_vs_run_close_pct": _ratio(bar.get("close"), cb),
                    "close_vs_run_high_pct": _ratio(bar.get("close"), hb),
                    "avg_vol_50": round(avg, 2) if avg is not None else None, "vol_x": vx, "reads": [],
                    "first_read_et": None})
    return out


def reads_of(sym, iso, tracker_docs, aplus_rows) -> list:
    """The STORED reads of `sym` on session `iso`, earliest first: each 🧠 tracker doc → "potential" at its `first_seen`
    and "armed" at `allrules.first_armed_at`; each Track record A+ row of that date → "aplus" at its `at_et`. Every time
    is the stored one (ET "HH:MM"), never now; a read with no stored time is listed with at_et None (last). [] when none."""
    from . import allrules as RULES
    from . import sections as SEC
    k = CO.fold(sym)
    out = []
    for d in tracker_docs or []:
        if not isinstance(d, dict) or CO.fold(d.get("symbol") or "") != k or not k:
            continue
        if d.get("date") not in (None, iso):
            continue
        setup = d.get("setup") if isinstance(d.get("setup"), str) else None
        rs = setup == SEC.RS_SETUP
        out.append({"kind": READ_KINDS[0], "setup": setup, "rs": rs, "at_et": _et_hhmm(d.get("first_seen"))})
        armed = RULES.first_armed_at(d)
        if armed is not None:
            out.append({"kind": READ_KINDS[1], "setup": setup, "rs": rs, "at_et": _et_hhmm(armed)})
    for r in aplus_rows or []:
        if not isinstance(r, dict) or CO.fold(r.get("symbol") or "") != k or not k or r.get("date") != iso:
            continue
        setup = r.get("setup") if isinstance(r.get("setup"), str) else None
        at = r.get("at_et") if isinstance(r.get("at_et"), str) else None
        out.append({"kind": READ_KINDS[2], "setup": setup, "rs": setup == SEC.RS_SETUP, "at_et": at})
    uniq, seen = [], set()
    for e in sorted(out, key=lambda e: (e["at_et"] is None, e["at_et"] or "", READ_KINDS.index(e["kind"]),
                                        e["setup"] or "")):
        sig = (e["kind"], e["setup"], e["at_et"])
        if sig not in seen:
            seen.add(sig)
            uniq.append(e)
    return uniq


def _first_read(reads) -> Optional[str]:
    ts = [e.get("at_et") for e in reads or [] if isinstance(e, dict) and e.get("at_et")]
    return min(ts) if ts else None


# ── closing [C7] ─────────────────────────────────────────────────────────────────────────────────────────────────
def _after(doc) -> list:
    rd = doc.get("run_day")
    return [r for r in doc.get("sessions") or [] if isinstance(r, dict) and r.get("date", "") > (rd or "")]


def close_of(doc, *, by, at=None) -> dict:
    """The closed row of a doc — counts only. A ratio is None when its base is not this doc's kind."""
    kind = (doc.get("base") or {}).get("kind")
    cb, hb = _ratio_bases(doc.get("base"))
    after = _after(doc)
    with_bar = [r for r in after if r.get("state") == ROW_STATES[0]]
    best = max(with_bar, key=lambda r: (_fin(r.get("high")) or float("-inf"), r["date"]), default=None)
    if best is not None and _fin(best.get("high")) is None:
        best = None
    lows = [_ratio(r.get("low"), cb) for r in with_bar]
    lows = [x for x in lows if x is not None]
    win = doc.get("window") or []
    last = next((r for r in doc.get("sessions") or [] if win and r.get("date") == win[-1]), None)
    last_ok = last is not None and last.get("state") == ROW_STATES[0]
    seat = doc.get("seat") if isinstance(doc.get("seat"), dict) else {}
    return {"run_day": doc.get("run_day"), "rule": doc.get("rule"), "run_pct": _fin(seat.get("run_pct")),
            "base_kind": kind, "sessions_watched": len(after), "sessions_with_bar": len(with_bar),
            "best_high_after": ({"date": best["date"], "vs_run_close_pct": _ratio(best.get("high"), cb),
                                 "vs_run_high_pct": _ratio(best.get("high"), hb)} if best is not None else None),
            "close_last_vs_run_close_pct": _ratio(last.get("close"), cb) if last_ok else None,
            "close_last_vs_run_high_pct": _ratio(last.get("close"), hb) if last_ok else None,
            "worst_low_vs_run_close_pct": min(lows) if lows else None,
            "another_run": doc.get("another_run"),
            "aplus_later": any(isinstance(a, dict) and a.get("after_run") for a in doc.get("aplus") or []),
            "no_price": not with_bar, "listed": bool(doc.get("listed")), "closed_by": by,
            "closed_at": at}


# ── the summary [C6, C7] ─────────────────────────────────────────────────────────────────────────────────────────
def summary(docs) -> dict:
    """Counts only, by rule: {open, closed, rules: {rule: {n, again, aplus_later, reg_n, reg_up, late_n, late_up,
    no_price, not_listed}}}. reg_* = finished docs of base "run_close" with a day-KEEP bar; late_* = base "run_high"
    with a day-KEEP bar; "up" = the ratio > 0. Nothing ranked, no rate."""
    out = {"open": 0, "closed": 0, "rules": {}}
    for d in docs or []:
        if not isinstance(d, dict):
            continue
        if d.get("state") != STATES[1] or not isinstance(d.get("closed"), dict):
            out["open"] += d.get("state") == STATES[0]
            continue
        out["closed"] += 1
        c = d["closed"]
        rule = c.get("rule") if c.get("rule") in C.RUNNERS_SEAT_RULES else d.get("rule")
        b = out["rules"].setdefault(rule, {"n": 0, "again": 0, "aplus_later": 0, "reg_n": 0, "reg_up": 0,
                                           "late_n": 0, "late_up": 0, "no_price": 0, "not_listed": 0})
        b["n"] += 1
        b["again"] += c.get("another_run") is not None
        b["aplus_later"] += bool(c.get("aplus_later"))
        b["no_price"] += bool(c.get("no_price"))
        b["not_listed"] += not c.get("listed")
        if c.get("base_kind") == BASE_KINDS[0] and _fin(c.get("close_last_vs_run_close_pct")) is not None:
            b["reg_n"] += 1
            b["reg_up"] += c["close_last_vs_run_close_pct"] > 0
        if c.get("base_kind") == BASE_KINDS[1] and _fin(c.get("close_last_vs_run_high_pct")) is not None:
            b["late_n"] += 1
            b["late_up"] += c["close_last_vs_run_high_pct"] > 0
    return out


def summary_text(s) -> str:
    """The served line: one clause per rule with a finished run, every count "x of n", late peaks apart, then NOTE."""
    t = SUMMARY_HEAD.format(open=s["open"], closed=s["closed"])
    for rule in C.RUNNERS_SEAT_RULES + tuple(r for r in s["rules"] if r not in C.RUNNERS_SEAT_RULES):
        b = s["rules"].get(rule)
        if not b or b["n"] <= 0:
            continue
        t += SUMMARY_RULE.format(rule_word=RULE_WORD.get(rule, str(rule)), n=b["n"], again=b["again"],
                                 aplus_later=b["aplus_later"])
        if b["reg_n"] > 0:
            t += SUMMARY_REG.format(reg_up=b["reg_up"], reg_n=b["reg_n"], keep=KEEP)
        if b["late_n"] > 0:
            t += SUMMARY_LATE.format(close=_rth_close(), late_up=b["late_up"], late_n=b["late_n"], keep=KEEP)
        if b["no_price"] > 0:
            t += SUMMARY_NO_PRICE.format(no_price=b["no_price"])
    return t + " · " + NOTE


# ── the seats ────────────────────────────────────────────────────────────────────────────────────────────────────
def _rs():
    from . import runseat as RS                                 # lazy: WP-1's engine
    return RS


def seat_runs(runners_doc, through) -> list:
    """Every run of the runners doc dated ≤ `through`: each entry's `runs` (listed) ∪ each `removed[].entry`'s runs whose
    reason is "dismissed", "aged" or "blocked" (listed False only for "blocked"). One per (run day, fold); a run listed
    anywhere is listed. -> [{key, symbol, run_day, rule, reading, seat, listed, seat_end}]."""
    t = _iso(through)
    by: dict = {}
    doc = runners_doc if isinstance(runners_doc, dict) else {}

    def take(entry, listed, end):
        if not isinstance(entry, dict):
            return
        sym = CO.house(entry.get("symbol") or "")
        if not sym:
            return
        for run in entry.get("runs") or []:
            if not isinstance(run, dict):
                continue
            rd = _iso(run.get("date"))
            if rd is None or t is None or rd > t:
                continue
            k = _key(rd, sym)
            cur = by.get(k)
            if cur is None:
                by[k] = {"key": k, "symbol": sym, "run_day": rd, "rule": run.get("rule"),
                         "reading": entry.get("reading"), "seat": dict(run), "listed": listed, "seat_end": end}
                continue
            cur["listed"] = cur["listed"] or listed
            if end is not None and cur["seat_end"] is None:
                cur["seat_end"] = end
            if run.get("rule") == C.RUNNERS_SEAT_RULES[1] and cur["rule"] != C.RUNNERS_SEAT_RULES[1]:
                cur.update(rule=run.get("rule"), seat=dict(run))

    for e in doc.get("entries") or []:
        take(e, True, None)
    for r in doc.get("removed") or []:
        if not isinstance(r, dict) or r.get("reason") not in SEAT_REASONS:
            continue
        end = {"reason": r.get("reason"), "session": _iso(r.get("session"))}
        take(r.get("entry"), r.get("reason") != BLOCKED, end)
    return sorted(by.values(), key=lambda s: (s["run_day"], s["symbol"]))


def _read_seats(db):
    """The runners doc through runseat (lazy); None on any fault."""
    try:
        return _rs().read_doc(CO.colls(db))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("runtrack: the runners doc unreadable: %s", type(exc).__name__)
        return None


# ── the store seams (stored reads only) ──────────────────────────────────────────────────────────────────────────
def _default_stores() -> dict:
    """{page key: its store} — the Track record pages (C.RUNNERS_SEAT_PAGES) and the 🧠 tracker read sources."""
    from chart_maps.gajjala import store as ST
    from chart_maps.gajjala import variant as V
    vs = {v.key: v for v in V.VARIANTS}
    out = {}
    for k in dict.fromkeys(tuple(C.RUNNERS_SEAT_PAGES) + tuple(C.AUTO_READ_SOURCES)):
        if k in vs:
            out[k] = ST.default() if V.is_gg5(vs[k]) else ST.for_variant(vs[k])
    return out


def _rings(dates, stores) -> list:
    """The Track record's A+ rows of these dates — `runseat.aplus_rings` (the ONE ring reader). Raises on a fault."""
    return _rs().aplus_rings(sorted(dates), stores=stores)


def _trackers(iso: str, stores) -> Optional[list]:
    """Every 🧠 tracker doc of the session across the read sources (`auto._tracker_docs`, the ✅ projection); None when any
    read faulted."""
    from . import auto as AUTO
    out = []
    for k in AUTO.read_sources():
        got = AUTO._tracker_docs((stores or {}).get(k), iso, fields=C.RULES_TRACKER_FIELDS)
        if got is None:
            return None
        out.extend(got)
    return out


def _grades(dates, stores) -> Optional[dict]:
    """{ledger id: the Track record's same-session state (`ledger._state_of`)} of these dates across the pages; None on a
    fault."""
    from chart_maps.gajjala import ledger as L
    out = {}
    for k in C.RUNNERS_SEAT_PAGES:
        st = (stores or {}).get(k)
        if st is None:
            continue
        docs = st.ledger_docs(sorted(dates))
        if docs is None:
            return None
        for d in docs:
            if isinstance(d, dict) and isinstance(d.get("same"), dict) and d.get("_id"):
                out[d["_id"]] = L._state_of(d["same"])
    return out


def _default_daily(sym, *, now=None):
    from sepa.prices import closed_daily_frame
    return closed_daily_frame(sym, now=now, use_cache=False)


def _aplus_of(doc, rings, grades) -> list:
    """The doc's A+ rings: every ring of the symbol dated in its window, or measured on a window session (`play_day`).
    `after_run` = the ring's date > the run day (a ring ON the run day is listed, never "rang A+ later"). The seat's own
    ring carries the seat's from-trigger %; every other ring None (nothing is measured here)."""
    k = CO.fold(doc.get("symbol") or "")
    win = set(doc.get("window") or [])
    rd = doc.get("run_day") or ""
    seat = doc.get("seat") if isinstance(doc.get("seat"), dict) else {}
    out = []
    for r in rings or []:
        if not isinstance(r, dict) or CO.fold(r.get("symbol") or "") != k:
            continue
        d, pd_ = _iso(r.get("date")), _iso(r.get("play_day"))
        if d not in win and pd_ not in win:
            continue
        own = seat.get("rule") == C.RUNNERS_SEAT_RULES[1] and r.get("id") is not None and seat.get("ring_id") == r.get("id")
        out.append({"id": r.get("id"), "page": r.get("page"), "date": d, "setup": r.get("setup"),
                    "at_et": r.get("at_et") if isinstance(r.get("at_et"), str) else None, "play_day": pd_,
                    "outcome": (grades or {}).get(r.get("id")),
                    "from_trigger_pct": _fin(seat.get("run_pct")) if own else None, "passed": True if own else None,
                    "after_run": bool(d and d > rd)})
    out.sort(key=lambda a: (a["date"] or "", a["at_et"] or "", a["id"] or ""))
    return out


# ── the night ────────────────────────────────────────────────────────────────────────────────────────────────────
def _new_doc(seat, now) -> dict:
    return {"_id": seat["key"], "symbol": seat["symbol"], "run_day": seat["run_day"], "rule": seat["rule"],
            "reading": seat["reading"], "seat": seat["seat"], "listed": bool(seat["listed"]), "state": STATES[0],
            "window": window_of(seat["run_day"]), "base": None, "sessions": [], "another_run": None, "aplus": [],
            "seat_end": seat["seat_end"], "closed": None, "tracked_through": None, "opened_at": now,
            "updated_at": now, "version": VERSION}


def _same(a: dict, b: dict) -> bool:
    drop = ("updated_at",)
    return {k: v for k, v in a.items() if k not in drop} == {k: v for k, v in b.items() if k not in drop}


def nightly(now: datetime, *, db=None, stores=None, daily: Optional[Callable] = None, coll=None, seats=None,
            dry: bool = False) -> dict:
    """Open a doc for every run not on file, mark `another_run` on an older open doc of the same symbol, ONE daily frame
    per OPEN symbol (its own try; None → `failed`), rows through tonight's session, close what is due. A read fault of
    the seats, or of the record itself, writes nothing. `seats` = the runners doc (None → read through runseat)."""
    through = recorded_session(now)
    t = through.isoformat()
    out = {"session": t, "opened": 0, "updated": 0, "closed": 0, "closed_calendar": 0, "reads": 0, "failed": 0,
           "faults": []}
    c = coll if coll is not None else CO.runtrack_coll(db)
    if c is None:
        out["faults"].append("record")
        return out
    rdoc = seats if seats is not None else _read_seats(db)
    if not isinstance(rdoc, dict):
        out["faults"].append("seats")
        return out
    try:
        stored = {d["_id"]: d for d in c.find({}) if isinstance(d, dict) and isinstance(d.get("_id"), str)}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("runtrack: the record unreadable: %s", type(exc).__name__)
        out["faults"].append("record")
        return out
    runs = seat_runs(rdoc, through)
    work = {k: dict(v) for k, v in stored.items()}
    for s in runs:                                              # open what is not on file; refresh an open seat
        cur = work.get(s["key"])
        if cur is None:
            work[s["key"]] = _new_doc(s, now)
            out["opened"] += 1
            continue
        if cur.get("state") == STATES[0]:
            if s["rule"] != cur.get("rule") or s["seat"] != cur.get("seat"):
                cur.update(rule=s["rule"], seat=s["seat"])
            if s["seat_end"] is not None and cur.get("seat_end") is None:
                cur["seat_end"] = s["seat_end"]
    for d in work.values():                                     # another run inside an older open doc's window
        if d.get("state") != STATES[0]:
            continue
        later = sorted((o for o in work.values() if o is not d and CO.fold(o.get("symbol") or "") ==
                        CO.fold(d.get("symbol") or "") and (o.get("run_day") or "") > (d.get("run_day") or "")
                        and o.get("run_day") in (d.get("window") or [])), key=lambda o: o["run_day"])
        if later and d.get("another_run") is None:
            d["another_run"] = {"date": later[0]["run_day"], "rule": later[0].get("rule")}
    open_docs = [d for d in work.values() if d.get("state") == STATES[0]]
    if open_docs:
        stores = stores if stores is not None else _default_stores()
        loader = daily or _default_daily
        isos = sorted({w for d in open_docs for w in d.get("window") or [] if w <= t})
        dates = set(isos)
        from catalysts.medical.reaction import prev_market_day
        for d in open_docs:
            rd = _as_date(d.get("run_day"))
            if rd is not None:
                dates.add(prev_market_day(rd).isoformat())       # an after-close ring the day before plays on the run day
        try:
            rings = _rings(dates, stores)
        except Exception as exc:                                # noqa: BLE001
            log.warning("runtrack: the A+ rings unreadable: %s", type(exc).__name__)
            rings = None
            out["faults"].append("aplus")
        try:
            grades = _grades(dates, stores)
        except Exception as exc:                                # noqa: BLE001
            log.warning("runtrack: the Track record grades unreadable: %s", type(exc).__name__)
            grades = None
        if grades is None and "grades" not in out["faults"]:
            out["faults"].append("grades")
        trackers: dict = {}
        for iso in isos:
            try:
                trackers[iso] = _trackers(iso, stores)
            except Exception as exc:                            # noqa: BLE001
                log.warning("runtrack: the 🧠 trackers unreadable: %s", type(exc).__name__)
                trackers[iso] = None
            if trackers[iso] is None and "trackers" not in out["faults"]:
                out["faults"].append("trackers")
        frames: dict = {}
        as_of = datetime.combine(through + timedelta(days=1), dtime(0, 0))   # naive = ET midnight: tonight's bar in
        for sym in dict.fromkeys(CO.house(d.get("symbol") or "") for d in open_docs):
            out["reads"] += 1
            try:
                frames[sym] = loader(sym, now=as_of)
            except Exception as exc:                            # noqa: BLE001
                log.warning("runtrack: daily bars of %s failed: %s", sym, type(exc).__name__)
                frames[sym] = None
            if frames[sym] is None or getattr(frames[sym], "empty", True):
                frames[sym] = None
                out["failed"] += 1
        for d in open_docs:
            _night_doc(d, frames.get(CO.house(d.get("symbol") or "")), t, now, rings, grades, trackers, out)
    writes = []
    for k, d in work.items():
        old = stored.get(k)
        if old is not None and _same(old, d):
            continue
        d["updated_at"] = now
        writes.append(d)
        if old is not None:
            out["updated"] += 1
    if dry:
        out["writes"] = [w["_id"] for w in writes]
        return out
    for w in writes:
        try:
            c.replace_one({"_id": w["_id"]}, w, upsert=True)
        except Exception as exc:                                # noqa: BLE001
            log.warning("runtrack: write of %s failed: %s", w["_id"], type(exc).__name__)
            if "write" not in out["faults"]:
                out["faults"].append("write")
    return out


def _night_doc(d, frame, t, now, rings, grades, trackers, out) -> None:
    """One OPEN doc, in place: base + rows from tonight's frame (kept as stored when the frame failed), reads, rings,
    then the closing rule."""
    win = d.get("window") or window_of(d.get("run_day"))
    d["window"] = win
    if rings is not None:
        d["aplus"] = _aplus_of(d, rings, grades)
    by_ring_date: dict = {}
    for a in d.get("aplus") or []:
        by_ring_date.setdefault(a.get("date"), []).append({"symbol": d.get("symbol"), "date": a.get("date"),
                                                            "setup": a.get("setup"), "at_et": a.get("at_et")})
    due = bool(win) and win[-1] <= t
    if frame is not None:
        d["base"] = base_of(d.get("seat"), frame, d.get("run_day"))
        old = {r.get("date"): r for r in d.get("sessions") or [] if isinstance(r, dict)}
        rows = session_rows(frame, d.get("run_day"), win, t, d["base"])
        for r in rows:
            tk = trackers.get(r["date"])
            if tk is None:
                prev = old.get(r["date"]) or {}
                r["reads"] = prev.get("reads") if isinstance(prev.get("reads"), list) else None
            else:
                r["reads"] = reads_of(d.get("symbol"), r["date"], tk, by_ring_date.get(r["date"]))
            r["first_read_et"] = _first_read(r["reads"])
        d["sessions"] = rows
        d["tracked_through"] = rows[-1]["date"] if rows else d.get("tracked_through")
        if due:
            d["state"], d["closed"] = STATES[1], close_of(d, by=CLOSED_BY[0], at=now)
            out["closed"] += 1
        return
    if bool(win) and win[-1] < t:                               # failed again after the closing night → the calendar
        have = {r.get("date") for r in d.get("sessions") or [] if isinstance(r, dict)}
        rows = [r for r in d.get("sessions") or [] if isinstance(r, dict)]
        rows += [_no_bar_row(iso, n) for n, iso in enumerate(win, start=1) if iso not in have]
        d["sessions"] = sorted(rows, key=lambda r: r["date"])
        if d.get("base") is None:
            d["base"] = dict(base_of(d.get("seat"), None, d.get("run_day")), note=BASE_NOTE["no_frame"])
        d["state"], d["closed"] = STATES[1], close_of(d, by=CLOSED_BY[1], at=now)
        out["closed"] += 1
        out["closed_calendar"] += 1


# ── served ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _seat_text(doc) -> str:
    from . import runners as RN
    seat = doc.get("seat") if isinstance(doc.get("seat"), dict) else {}
    pct = _fin(seat.get("run_pct"))
    if pct is None:
        return DASH
    if doc.get("rule") == C.RUNNERS_SEAT_RULES[1]:
        return C.RUNNERS_SEAT_CHIP_APLUS.format(pct=f"{math.floor(pct):+d}%")
    return C.RUNNERS_SEAT_CHIP_DAY.format(pct=RN._run_text(pct))


def _state_text(doc) -> str:
    if doc.get("state") == STATES[1] and isinstance(doc.get("closed"), dict):
        by = doc["closed"].get("closed_by")
        k = sum(1 for r in doc.get("sessions") or [] if isinstance(r, dict) and r.get("state") == ROW_STATES[1])
        return STATE_CLOSED.get(by, STATE_CLOSED["window"]).format(keep=KEEP, k=k)
    n = len([r for r in doc.get("sessions") or [] if isinstance(r, dict)])
    return STATE_OPEN.format(n=max(n, 1), keep=KEEP)


def _heads(heads) -> list:
    return [[k, label.format(keep=KEEP)] for k, label in heads]


def _reads_text(reads) -> str:
    if reads is None:
        return READS_FAULT
    if not reads:
        return NO_READ
    parts = []
    for e in reads:
        word = {"potential": "🧠", "armed": "🧠 armed", "aplus": "🎯 A+"}.get(e.get("kind"), str(e.get("kind")))
        rs = " 🎾" if e.get("rs") else ""
        parts.append(f"{word}{rs} {e.get('at_et') or DASH}")
    return " · ".join(parts)


def _closed_row(doc) -> dict:
    c = doc.get("closed") or {}
    best = c.get("best_high_after") if isinstance(c.get("best_high_after"), dict) else None
    kind = c.get("base_kind")
    best_v = None
    if best is not None:
        best_v = best.get("vs_run_close_pct") if kind == BASE_KINDS[0] else best.get("vs_run_high_pct")
    values = {"symbol": doc.get("symbol"), "run_day": doc.get("run_day"), "rule": doc.get("rule"),
              "run_pct": _fin(c.get("run_pct")), "base": kind, "best": _fin(best_v),
              "last_close": _fin(c.get("close_last_vs_run_close_pct")),
              "last_high": _fin(c.get("close_last_vs_run_high_pct")),
              "worst": _fin(c.get("worst_low_vs_run_close_pct")), "again": c.get("another_run") is not None,
              "aplus_later": bool(c.get("aplus_later")), "listed": bool(c.get("listed")), "closed_by": c.get("closed_by")}
    ar = c.get("another_run") if isinstance(c.get("another_run"), dict) else None
    cells = {"symbol": doc.get("symbol") or DASH, "run_day": doc.get("run_day") or DASH, "rule": _seat_text(doc),
             "run_pct": _pct_text(values["run_pct"]), "base": BASE_WORD.get(kind, BASE_WORD["none"]),
             "best": (f"{_pct_text(best_v)} {best['date']}" if best is not None and _fin(best_v) is not None else DASH),
             "last_close": _pct_text(values["last_close"]), "last_high": _pct_text(values["last_high"]),
             "worst": _pct_text(values["worst"]), "again": (f"{YES} {ar.get('date')}" if ar else NO),
             "aplus_later": YES if values["aplus_later"] else NO, "listed": LISTED_WORD[values["listed"]],
             "closed_by": CLOSED_BY_WORD.get(values["closed_by"], DASH).format(keep=KEEP)}
    if c.get("no_price"):
        cells["closed_by"] += " · no price"
    return {"id": doc.get("_id"), "symbol": doc.get("symbol"), "run_day": doc.get("run_day"), "cells": cells,
            "values": values}


def _session_row(r) -> dict:
    values = {"day_n": r.get("day_n"), "date": r.get("date"), "close": _fin(r.get("close")),
              "change": _fin(r.get("change_pct")), "high": _fin(r.get("high")), "low": _fin(r.get("low")),
              "vs_close": _fin(r.get("close_vs_run_close_pct")), "vs_high": _fin(r.get("close_vs_run_high_pct")),
              "vol_x": _fin(r.get("vol_x")), "reads": r.get("first_read_et")}
    nb = r.get("state") == ROW_STATES[1]
    cells = {"day_n": f"{r.get('day_n')} of {KEEP}", "date": r.get("date") or DASH,
             "close": "no bar" if nb else _px_text(values["close"]), "change": _pct_text(values["change"]),
             "high": _px_text(values["high"]), "low": _px_text(values["low"]), "vs_close": _pct_text(values["vs_close"]),
             "vs_high": _pct_text(values["vs_high"]),
             "vol_x": f"{values['vol_x']:g}×" if values["vol_x"] is not None else DASH,
             "reads": _reads_text(r.get("reads") if "reads" in r else [])}
    return {"date": r.get("date"), "state": r.get("state"), "cells": cells, "values": values}


def _read_all(coll, symbol=None) -> Optional[list]:
    try:
        q = {"symbol": CO.house(symbol)} if symbol else {}
        return [d for d in coll.find(q) if isinstance(d, dict)]
    except Exception as exc:                                    # noqa: BLE001
        log.warning("runtrack: the record unreadable: %s", type(exc).__name__)
        return None


def payload(now: datetime, symbol: Optional[str] = None, *, db=None, coll=None) -> dict:
    """The served record. Without `symbol`: {state, title, summary_text, note, asof_text, heads, rows (finished, newest
    run first, at most ROWS_MAX), shown_text, open_n, closed_n}. With `symbol`: {state, symbol, title, note, docs: [{run_day,
    seat_text, state_text, heads, rows, base_note}]}. Every cell a served string beside its raw number; no NaN."""
    at = GC.LEDGER_GRADE_AT_ET
    sym = CO.house(symbol) if isinstance(symbol, str) and symbol.strip() else None
    if not C.RUNNERS_SEAT_ON:
        return {"state": "off", "title": TITLE, "text": OFF_TEXT, "note": NOTE}
    c = coll if coll is not None else CO.runtrack_coll(db)
    docs = _read_all(c, sym) if c is not None else None
    if docs is None:
        return {"state": "error", "title": TITLE, "text": ERROR_TEXT, "note": NOTE}
    if sym:
        docs.sort(key=lambda d: d.get("run_day") or "", reverse=True)
        return {"state": "ok" if docs else "empty", "symbol": sym, "title": SYMBOL_TITLE.format(sym=sym), "note": NOTE,
                "docs": [{"run_day": d.get("run_day"), "seat_text": _seat_text(d), "state_text": _state_text(d),
                          "listed_text": LISTED_WORD[bool(d.get("listed"))], "heads": _heads(SESSION_HEADS),
                          "rows": [_session_row(r) for r in d.get("sessions") or [] if isinstance(r, dict)],
                          "base_note": (d.get("base") or {}).get("note") or BASE_NOTE["no_frame"]} for d in docs]}
    s = summary(docs)
    closed = sorted((d for d in docs if d.get("state") == STATES[1] and isinstance(d.get("closed"), dict)),
                    key=lambda d: (d.get("run_day") or "", d.get("symbol") or ""), reverse=True)
    thr = [d.get("tracked_through") for d in docs if isinstance(d.get("tracked_through"), str)]
    shown = closed[:ROWS_MAX]
    return {"state": "ok" if docs else "empty", "title": TITLE,
            "summary_text": summary_text(s) if docs else EMPTY_TEXT.format(at=at), "note": NOTE,
            "asof_text": ASOF_TEXT.format(at=at, date=max(thr)) if thr else ASOF_NONE.format(at=at),
            "heads": _heads(CLOSED_HEADS), "rows": [_closed_row(d) for d in shown],
            "shown_text": SHOWN_TEXT.format(lim=ROWS_MAX, n=len(closed)) if len(closed) > ROWS_MAX else None,
            "open_n": s["open"], "closed_n": s["closed"], "summary": s}


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chart_maps.gajjala_watch.runtrack", description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="run the nightly record once (the 20:15 nightly's own function)")
    ap.add_argument("--dry-run", action="store_true", help="compute, print the ids it would write, write nothing")
    args = ap.parse_args(argv)
    if not args.once:
        ap.print_help()
        return 2
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    out = nightly(datetime.now(UTC), dry=args.dry_run)
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
