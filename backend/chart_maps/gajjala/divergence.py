"""🧨 divergence — THE engine of the Divergence record on 🚩 Gajjala's 5-min tab (2026-11-18). Pure over a plain closed
5-minute series; three callers: the cron pass (run.py, a Deps-gated hook → `run_step`), the 20:15 ET nightly
(nightly.main → `grade_divergence` → `grade_step`) and the served sub (divergence_tab.py, Mongo reads only).

Ajay, verbatim (2026-11-18): "Do we still capture divergence alerts? Can you add a tab for in in Gajjals 5 min please"
· "yes should do a track recird fir the divergence aftger EMA 9 Cross over bullish Cuz I am missing A+ i can chase the
divergency atleast like in these cases I would caught a good chunk of returns"

A DISPLAY + RECORD of the 11-16 study's REGISTERED pick (eod-audits/research/2026-11-16_explosive_divergence, OOS_SPEC.md
sha GC.DIVERGENCE_OOS_SPEC_SHA256): R1 = (9 EMA − 21 EMA) ÷ ATR(14) on a closed 5-min bar, level q60 =
GC.DIVERGENCE_R1_LEVEL, filter G+V2, exit X3, costs tx.net_pct. Nothing here sends, gates, claims or trades: no alert
kind, no keep-set kind, no rule of the 🚩 detectors reads it. UNMEASURED live; in-sample the rule did not make money.

THE RULE (the study's functions ported verbatim — tests/test_gajjala_divergence_2026_11_18.py holds the study's own
code as the oracle and pins equality):
  eligible(i)   bar i on session S, its close stamp inside the window (RTH 09:35–15:55 / AH 16:05–19:55 — pre-market
                NEVER), closed after the unit's ring clock, 9 EMA and 21 EMA finite with 9 > 21, i + 1 ≥ MIN_BARS (30),
                ATR known.
  crossing      over the eligible bars in order, the FIRST i with R1[i] ≥ level whose predecessor R1[i − 1] is None or
                below it — the study's `crossing` RETURNS there. An opening run already ≥ level never lists by itself.
  V2            read AT THAT BAR ONLY: the last 3 bars' volumes non-decreasing AND their mean ≥ the mean of the up to 12
                bars before them that are ON session S (≥ 6 such bars, else None = fails).
  ONE candidate per (session, window): V2 not True at the first crossing → NO listing for that window, whatever later
                crossings do (never iterate crossings, never the next bar). RTH first; AH only when RTH listed nothing.
  entry         the next 5-min bar's open (== OOS_SPEC "open of the next 1-min bar at/after the alert bar's close" in a
                drop-empty resampler), when that bar closes at or before the horizon (regular close / extended close,
                alerts._closes — half days included); else no_print.
  X3 exit       RTH: the close of the first 5-min bar after the alert whose 9 EMA crosses under the 21 (ema_cross's
                rule), else the regular-close mark (the close of the last bar at or before it). AH (hx.walk_h): the open
                of the next print after that down-cross bar, else the 20:00 mark.
  net %         tx.net_pct: (x(1 − c_x) − e(1 + c_e)) / e × 100, c_p = COST_BPS + SLIP_USD / p, per side.

The record (store.DIVERGENCE, one doc per (session, SYM), GG5 only): the pass writes the alert it saw ($setOnInsert —
a second qualifying bar never moves it) and refreshes `live`; the nightly GRADES FIRST, then re-detects every unit of
each session not yet marked in the ONE gajjala_state doc GC.DIVERGENCE_STATE_ID (newest session first, the loader-call
cap GC.DIVERGENCE_GRADE_MAX_LOADS): the full-day read is AUTHORITATIVE — a different bar MOVES the record (the pass's
block kept as `live_alert`, `redetect_moved`), a bar it cannot find flags `redetect_missing` (the doc and its grade
kept), a unit the pass never saw is inserted (source "nightly"); moved / inserted docs are graded from the frames already
in hand (no new loader call). A session is marked only when every unit of it loaded.
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from . import constants as GC
from . import ema_cross as X

log = logging.getLogger("chart_maps.gajjala.divergence")

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
SETTLE = timedelta(seconds=GC.BAR_SETTLE_SEC)
_RECHECK_TOL = 1e-6                       # spec §3.3 — float hygiene for the nightly's r1 re-read (information only)
OUTCOMES = ("win", "loss", "flat", "no_print")
STATES = ("open", "exited", "no_print")
REASONS = ("downcross", "close")
SOURCES = ("pass", "nightly", "backfill")
STEP_KEYS = ("rows", "graded", "not_due", "redetected", "redetect_moved", "redetect_missing", "skipped_marked",
             "deferred_cap", "deferred_grade", "load_failed", "bar_missing", "faulted", "written", "loads")


# ── the series ────────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass
class Bars5:
    """A closed 5-minute series, oldest first, prior session + today. `t` = the bar's CLOSE stamp "YYYY-MM-DD HH:MM" ET
    (bars.py); `session` = today's ISO date (a bar is ON the session when its stamp's date is it)."""
    t: list
    o: list
    h: list
    l: list                                                     # noqa: E741 — the house name
    c: list
    v: list
    ema9: list                                                  # float | None (warm-up)
    ema21: list
    session: str

    def __len__(self) -> int:
        return len(self.t)


def _iso(session) -> str:
    return session.isoformat()[:10] if isinstance(session, (date, datetime)) else str(session or "")[:10]


def _as_date(session) -> date:
    if isinstance(session, datetime):
        return session.date()
    return session if isinstance(session, date) else date.fromisoformat(str(session)[:10])


def _f(x) -> Optional[float]:
    return X.finite(x)


def from_frame(F, session_iso) -> Bars5:
    """A bars.Frame (the pass's / nightly's 5m frame) → Bars5 — the same bars, the frame's own masked 9 / 21 EMAs."""
    return Bars5(t=list(F.t), o=[float(x) for x in F.o], h=[float(x) for x in F.h], l=[float(x) for x in F.l],
                 c=[float(x) for x in F.c], v=[float(x or 0.0) for x in F.v], ema9=list(F.ema9),
                 ema21=list(F.ema21), session=_iso(session_iso))


def _curve(curves, tone: str, n: int) -> Optional[list]:
    for cv in curves or []:
        if isinstance(cv, dict) and cv.get("tone") == tone and isinstance(cv.get("values"), list):
            vals = list(cv["values"])
            return vals if len(vals) == n else None
    return [None] * n                                            # an all-None curve is omitted by the tile writer


def from_tile(doc: dict, session_iso) -> Optional[Bars5]:
    """A stored gajjala_reads doc → Bars5 (the backfill's input): tile.bars5_prior + tile.bars5 and curves5_prior +
    curves5 (the pass's OWN 9 / 21 EMA values, index-aligned per list). None when the tile is missing / malformed (a bar
    without a stamp or a finite o/h/l/c, a curve whose length differs from its bars)."""
    try:
        tile = (doc or {}).get("tile")
        if not isinstance(tile, dict):
            return None
        parts = []
        for bk, ck in (("bars5_prior", "curves5_prior"), ("bars5", "curves5")):
            bars = tile.get(bk) if tile.get(bk) is not None else []
            if not isinstance(bars, list):
                return None
            curves = tile.get(ck) if isinstance(tile.get(ck), list) else []
            e9, e21 = _curve(curves, "ema9", len(bars)), _curve(curves, "ema21", len(bars))
            if e9 is None or e21 is None:
                return None
            parts.append((bars, e9, e21))
        out = Bars5([], [], [], [], [], [], [], [], _iso(session_iso))
        for bars, e9, e21 in parts:
            for b, a, s in zip(bars, e9, e21):
                if not isinstance(b, dict) or not isinstance(b.get("t"), str):
                    return None
                ohlc = [_f(b.get(k)) for k in ("o", "h", "l", "c")]
                if any(x is None for x in ohlc):
                    return None
                out.t.append(b["t"][:16])
                out.o.append(ohlc[0]), out.h.append(ohlc[1]), out.l.append(ohlc[2]), out.c.append(ohlc[3])
                out.v.append(_f(b.get("v")) or 0.0)
                out.ema9.append(_f(a)), out.ema21.append(_f(s))
        if not out.t or out.t != sorted(out.t) or len(set(out.t)) != len(out.t):
            return None
        return out
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala divergence: tile unreadable: %s", type(exc).__name__)
        return None


# ── the reads (the study's functions, verbatim on Bars5) ──────────────────────────────────────────────────────────
def atr_series(b: Bars5) -> list:
    """daytrading.indicators.atr over (high, low, close), GC.DIVERGENCE_ATR_PERIOD; NaN / ≤ 0 → None (study atr_series)."""
    import pandas as pd
    from daytrading import indicators as DI
    n = len(b.t)
    if not n:
        return []
    df = pd.DataFrame({"high": [float(x) for x in b.h], "low": [float(x) for x in b.l],
                       "close": [float(x) for x in b.c]})
    vals = DI.atr(df, GC.DIVERGENCE_ATR_PERIOD).tolist()
    vals = vals + [None] * (n - len(vals))
    return [None if (x is None or x != x or x <= 0) else float(x) for x in vals]


def r1_series(b: Bars5, A: list) -> list:
    """R1[i] = (ema9 − ema21) / A[i] when both EMAs are finite, ema9 > ema21 and A[i] is known; else None (study _r1)."""
    out = []
    for i in range(len(b.t)):
        f, s = _f(b.ema9[i]), _f(b.ema21[i])
        a = A[i] if i < len(A) else None
        sp = None if f is None or s is None else f - s
        out.append(None if sp is None or sp <= 0 or a is None else sp / a)
    return out


def bar_close_utc(t: str) -> datetime:
    """"YYYY-MM-DD HH:MM" ET (a bar's close stamp) → an aware UTC datetime — THE helper the ring clock compares to."""
    return datetime.strptime(str(t)[:16], "%Y-%m-%d %H:%M").replace(tzinfo=ET).astimezone(UTC)


def _win(window) -> tuple:
    """A window key ("rth" / "ah") or a GC.DIVERGENCE_WINDOWS triple → (key, lo, hi)."""
    if isinstance(window, (tuple, list)) and len(window) == 3:
        return tuple(window)
    for w in GC.DIVERGENCE_WINDOWS:
        if w[0] == window:
            return w
    raise ValueError(f"unknown divergence window {window!r}")


def _on(b: Bars5, i: int) -> bool:
    return str(b.t[i])[:10] == b.session


def eligible(b: Bars5, A: list, i: int, clock_utc: datetime, window) -> bool:
    """The study's eligible(): on session S, lo ≤ close HH:MM ≤ hi, closed after the clock, 9 > 21 (both finite),
    i + 1 ≥ GC.DIVERGENCE_MIN_BARS, A[i] known."""
    _k, lo, hi = _win(window)
    hm = str(b.t[i])[11:16]
    f, s = _f(b.ema9[i]), _f(b.ema21[i])
    return (_on(b, i) and lo <= hm <= hi and bar_close_utc(b.t[i]) > clock_utc and f is not None and s is not None
            and f > s and i + 1 >= GC.DIVERGENCE_MIN_BARS and i < len(A) and A[i] is not None)


def first_crossing(R1: list, el: list, level: float) -> Optional[dict]:
    """The study's crossing(): over the eligible indices in order, the FIRST i with R1[i] ≥ level whose predecessor
    R1[i − 1] is None or < level — it RETURNS there. An opening run already ≥ level never alerts by itself; an alert after
    such a run carries `after_over`. -> {"i", "after_over"} | None."""
    already = False
    for n, i in enumerate(el):
        m = R1[i]
        if m is None or m < level:
            continue
        pm = R1[i - 1] if i > 0 else None
        if pm is None or pm < level:
            return {"i": i, "after_over": already}
        if n == 0:
            already = True
    return None


def _v2_parts(b: Bars5, i: int) -> tuple:
    """(V2, run, hour) — the study's volume_reads V2 verbatim: r0 = i − V2_RUN + 1; hour = the bars in
    [r0 − V2_HOUR_BARS, r0) ON session S (≥ V2_MIN_HOUR_BARS, else V2 None); run = bars r0..i (any session)."""
    r0 = i - GC.DIVERGENCE_V2_RUN + 1
    hour = [float(b.v[m]) for m in range(max(0, r0 - GC.DIVERGENCE_V2_HOUR_BARS), max(0, r0)) if _on(b, m)]
    if r0 >= 0 and len(hour) >= GC.DIVERGENCE_V2_MIN_HOUR_BARS:
        run = [float(b.v[m]) for m in range(r0, i + 1)]
        rising = all(run[k] >= run[k - 1] for k in range(1, len(run)))
        return bool(rising and statistics.mean(run) >= statistics.mean(hour)), run, hour
    return None, None, hour


def v2_read(b: Bars5, i: int) -> Optional[bool]:
    """V2 at bar i: True / False, or None (fewer than V2_MIN_HOUR_BARS session bars before the run — fails the filter)."""
    return _v2_parts(b, i)[0]


def alert_read(b: Bars5, A: list, R1: list, clock_utc: datetime, window,
               level: float = GC.DIVERGENCE_R1_LEVEL) -> Optional[dict]:
    """ONE candidate per (session, window) = first_crossing(...) — called ONCE, never a loop over crossings. V2 at that
    bar not True → None (the window has no listing). True → {"i", "bar_t", "r1", "ema9", "ema21", "atr", "close",
    "after_over", "v2": {"run", "run_mean", "hour_mean", "hour_n"}}."""
    el = [i for i in range(len(b.t)) if eligible(b, A, i, clock_utc, window)]
    cand = first_crossing(R1, el, level)
    if cand is None:
        return None
    i = cand["i"]
    v2, run, hour = _v2_parts(b, i)
    if v2 is not True:
        return None
    return {"i": i, "bar_t": b.t[i], "r1": R1[i], "ema9": _f(b.ema9[i]), "ema21": _f(b.ema21[i]), "atr": A[i],
            "close": _f(b.c[i]), "after_over": bool(cand["after_over"]),
            "v2": {"run": run, "run_mean": statistics.mean(run), "hour_mean": statistics.mean(hour),
                   "hour_n": len(hour)}}


def up_cross_before(b: Bars5, i: int) -> Optional[str]:
    """The stamp of the last 9-over-21 UP cross ON the session at or before bar i (ema_cross's rule), else None —
    information only (the card's cross row), never a listing condition."""
    idx = [k for k in range(min(i + 1, len(b.t))) if _on(b, k)]
    ups = [x for x in X.crosses_from_emas(b.ema9, b.ema21, b.t, b.c, idx) if x["dir"] == X.UP]
    return ups[-1]["ts"] if ups else None


def horizon_of(session, window) -> tuple:
    """(HH:MM, aware UTC) of the window's horizon: "rth" → the regular close, "ah" → the extended close
    (alerts._closes — 16:00 / 20:00, half days 13:00 / 17:00)."""
    from . import alerts as AL
    k = _win(window)[0]
    d = _as_date(session)
    reg, ext = AL._closes(d)
    t = reg if k == GC.DIVERGENCE_WINDOWS[0][0] else ext
    return t.strftime("%H:%M"), datetime.combine(d, t, tzinfo=ET).astimezone(UTC)


def _hstamp(b: Bars5, horizon_hm: str) -> str:
    return f"{b.session} {horizon_hm}"


def entry_of(b: Bars5, i: int, horizon_hm: str) -> Optional[dict]:
    """{"px": the next bar's open, "t": its close stamp} when bar i + 1 exists and closes at or before the horizon
    (its bucket starts before it — tx.entry_k); else None (no print)."""
    if i + 1 < len(b.t) and str(b.t[i + 1])[:16] <= _hstamp(b, horizon_hm):
        px = _f(b.o[i + 1])
        return {"px": px, "t": b.t[i + 1]} if px is not None else None
    return None


def _x3(b: Bars5, i: int, window, horizon_hm: str, final: bool) -> Optional[dict]:
    """X3 over the bars in hand. `final` False (a live read) → None while undecided (no down-cross yet / an AH signal
    whose next print has not come) and the horizon bar has not closed."""
    H = _hstamp(b, horizon_hm)
    n = len(b.t)
    k = _win(window)[0]
    downs = [x for x in X.crosses_from_emas(b.ema9, b.ema21, b.t, b.c, range(i + 1, n))
             if x["dir"] == X.DOWN and str(x["ts"])[:16] <= H]
    if downs:
        j = downs[0]["i"]
        if k == GC.DIVERGENCE_WINDOWS[0][0]:
            return {"px": _f(b.c[j]), "t": b.t[j], "reason": REASONS[0], "cross_t": b.t[j], "px_at": "close"}
        if j + 1 < n and str(b.t[j + 1])[:16] <= H:              # hx.walk_h: the next print's open after the signal
            return {"px": _f(b.o[j + 1]), "t": b.t[j + 1], "reason": REASONS[0], "cross_t": b.t[j], "px_at": "open"}
        if not final:
            return None
    elif not final:
        return None
    last = [m for m in range(i + 1, n) if str(b.t[m])[:16] <= H]
    ent = entry_of(b, i, horizon_hm)
    px = _f(b.c[last[-1]]) if last else (ent or {}).get("px")
    return {"px": px, "t": H, "reason": REASONS[1], "cross_t": downs[0]["ts"] if downs else None, "px_at": "close"}


def x3_exit(b: Bars5, i: int, window, horizon_hm: str) -> dict:
    """The study's X3 (tx.walk / hx.walk_h) over a COMPLETE session: {"px", "t", "reason" downcross | close,
    "cross_t", "px_at" close | open}. `t` = the exit bar's close stamp (the horizon for the mark); px_at "open" = an
    after-hours fill at the next print's open (that bar's bucket START is the fill moment)."""
    return _x3(b, i, window, horizon_hm, True)


def net_pct(x: float, e: float) -> float:
    """tx.net_pct verbatim: (x(1 − c_x) − e(1 + c_e)) / e × 100, c_p = DIVERGENCE_COST_BPS + DIVERGENCE_SLIP_USD / p."""
    def cside(p):
        return GC.DIVERGENCE_COST_BPS + GC.DIVERGENCE_SLIP_USD / p
    return (x * (1 - cside(x)) - e * (1 + cside(e))) / e * 100


def _bucket() -> timedelta:
    import pandas as pd
    from .bars import RULE_OF
    return pd.Timedelta(RULE_OF["5m"]).to_pytimedelta()


def _hold_min(entry_t: str, ex: dict) -> Optional[float]:
    """≈ tx's hold: minutes from the entry bucket's START (the next bar opens there) to the exit moment — the exit bar's
    close stamp, or its bucket START for an open fill (px_at "open"). Exact when every minute printed."""
    try:
        x = bar_close_utc(ex["t"]) - (_bucket() if ex.get("px_at") == "open" else timedelta(0))
        return round((x - (bar_close_utc(entry_t) - _bucket())).total_seconds() / 60.0, 1)
    except (TypeError, ValueError, KeyError):
        return None


def _outcome(net: Optional[float]) -> str:
    if net is None:
        return OUTCOMES[3]
    return OUTCOMES[0] if net > 0 else (OUTCOMES[1] if net < 0 else OUTCOMES[2])


def trade(b: Bars5, i: int, window, horizon_hm: str) -> dict:
    """{"entry", "exit", "gross_pct", "net_pct", "hold_min", "outcome"} — outcome win (net > 0) | loss (< 0) | flat
    (== 0) | no_print (no entry before the horizon: entry / exit / % None)."""
    ent = entry_of(b, i, horizon_hm)
    if ent is None:
        return {"entry": None, "exit": None, "gross_pct": None, "net_pct": None, "hold_min": None,
                "outcome": OUTCOMES[3]}
    ex = x3_exit(b, i, window, horizon_hm)
    e, x = ent["px"], ex["px"]
    gross = (x / e - 1) * 100 if (x is not None and e) else None
    net = net_pct(x, e) if (x is not None and e) else None
    return {"entry": ent, "exit": ex, "gross_pct": gross, "net_pct": net, "hold_min": _hold_min(ent["t"], ex),
            "outcome": _outcome(net)}


def live_state(b: Bars5, alert_i: int, window, horizon_hm: str) -> dict:
    """The pass's live read of a listing: {"as_of_bar_t", "entry", "exit" | None, "state" open | exited | no_print,
    "gap_now_atr", "net_pct_now" | None}. Exited = X3 decided on the bars in hand (or the horizon bar closed → the
    mark); open = entry printed (or not yet) and no exit; no_print = no bar before the horizon after the listing while a
    later bar exists. net_pct_now = the exit's net when exited, else the latest close vs the entry."""
    n = len(b.t)
    H = _hstamp(b, horizon_hm)
    last_t = str(b.t[-1])[:16] if n else None
    A = atr_series(b)
    f, s = (_f(b.ema9[-1]), _f(b.ema21[-1])) if n else (None, None)
    a = A[-1] if A else None
    gap = (f - s) / a if (f is not None and s is not None and a) else None
    ent = entry_of(b, alert_i, horizon_hm)
    out = {"as_of_bar_t": b.t[-1] if n else None, "entry": ent, "exit": None, "state": STATES[0],
           "gap_now_atr": gap, "net_pct_now": None}
    if ent is None:
        if alert_i + 1 < n:                                     # a later bar exists, but none before the horizon
            out["state"] = STATES[2]
        return out
    ex = _x3(b, alert_i, window, horizon_hm, last_t is not None and last_t >= H)
    if ex is not None and ex.get("px") is not None:
        out.update(exit=ex, state=STATES[1], net_pct_now=net_pct(ex["px"], ent["px"]))
    else:
        c = _f(b.c[-1])
        out["net_pct_now"] = net_pct(c, ent["px"]) if c is not None else None
    return out


def record_id(session_iso, sym: str) -> str:
    """`"{date}|{SYM}"` — one record per (session, symbol)."""
    return f"{_iso(session_iso)}|{(sym or '').upper()}"


# ── the cohort (the study's units: today's 🚩 A+ shadow / live + 🧠 pushed rows with a plan) ──────────────────────────
def units_today(store, session) -> dict:
    """{SYM: {"clock": aware UTC, "kind", "setup", "at_et", "line", "date"}} from ledger.rows_for([prev market day,
    session], store): plan == PLANS[0] and (kind 🧠 potential, or kind A+ on APLUS_LINES); only rows whose
    session_bounds same_date == session (an after-close ring of TODAY belongs to tomorrow; YESTERDAY's after-close ring
    counts from 04:00 ET); clock = at_utc on the session's own rows, 04:00 ET (ET_PREMARKET_OPEN) for a prior-date
    ring; the earliest clock per symbol. A row without an alert time is never a unit. Raises ledger.LedgerReadError."""
    from daytrading.data import ET_PREMARKET_OPEN
    from . import ledger as LG
    d = _as_date(session)
    rows = LG.rows_for([LG._prev_market_day(d), d], store)
    four = datetime.combine(d, ET_PREMARKET_OPEN, tzinfo=ET).astimezone(UTC)
    out: dict = {}
    for r in rows:
        if r.get("plan") != LG.PLANS[0]:
            continue
        kind = r.get("kind")
        if not (kind == LG.KINDS[0] or (kind == LG.KINDS[1] and r.get("line") in LG.APLUS_LINES)):
            continue
        at = r.get("at_utc")
        if not isinstance(at, datetime):
            continue
        try:
            if LG.session_bounds(r["date"], at)["same_date"] != d:
                continue
        except Exception:                                       # noqa: BLE001
            continue
        clock = at.astimezone(UTC) if r["date"] == d.isoformat() else four
        sym = str(r.get("symbol") or "").upper()
        cur = out.get(sym)
        if cur is None or clock < cur["clock"]:
            out[sym] = {"clock": clock, "kind": kind, "setup": r.get("setup"), "at_et": r.get("at_et"),
                        "line": r.get("line"), "date": r["date"]}
    return out


def detect(b: Bars5, unit_clock: datetime, session, level: float = GC.DIVERGENCE_R1_LEVEL) -> Optional[dict]:
    """RTH window first, then AH (only when RTH listed nothing) → {"window", **alert_read, "up_cross_t"} | None."""
    if b is None or not len(b.t):
        return None
    A = atr_series(b)
    R1 = r1_series(b, A)
    for w in GC.DIVERGENCE_WINDOWS:
        a = alert_read(b, A, R1, unit_clock, w, level)
        if a is not None:
            return dict(a, window=w[0], up_cross_t=up_cross_before(b, a["i"]))
    return None


def _half_day(session) -> bool:
    from daytrading.data import ET_RTH_CLOSE
    from . import alerts as AL
    return AL._closes(_as_date(session))[0] != ET_RTH_CLOSE


def _alert_block(a: dict) -> dict:
    return {k: v for k, v in a.items() if k != "window"}


def _ring_block(u: dict) -> dict:
    return {"kind": u.get("kind"), "setup": u.get("setup"), "line": u.get("line"), "at_et": u.get("at_et"),
            "date": u.get("date"), "clock": u["clock"].isoformat()}


def _locate(b: Bars5, bar_t) -> Optional[int]:
    if not isinstance(bar_t, str):
        return None
    try:
        return b.t.index(bar_t)
    except ValueError:
        return None


def run_step(store, frames: dict, now: datetime, session) -> dict:
    """THE PASS HOOK (run.Deps.divergence): units_today ∩ frames → from_frame(f5) → the stored alert's live read, or
    detect → upsert_divergence($setOnInsert date / symbol / window / alert / ring / recorded_at / source "pass" /
    half_day; $set live / at). -> {"units", "read", "alerted", "new", "updated", "read_fault"}. NEVER raises (each name
    its own try); a ledger read fault → read_fault True, nothing written. Never sends anything."""
    out = {"units": 0, "read": 0, "alerted": 0, "new": 0, "updated": 0, "read_fault": False}
    try:
        d = _as_date(session)
        iso = d.isoformat()
        try:
            units = units_today(store, d)
        except Exception as exc:                                # noqa: BLE001 — LedgerReadError or a store fault
            log.warning("gajjala divergence: the cohort could not be read: %s", type(exc).__name__)
            out["read_fault"] = True
            return out
        out["units"] = len(units)
        try:
            have = {doc.get("_id"): doc for doc in (store.divergence_docs([d]) or []) if isinstance(doc, dict)}
        except Exception:                                       # noqa: BLE001
            have = {}
        stamp = _utc(now)
        for sym in sorted(units):
            fr = (frames or {}).get(sym)
            if fr is None:
                continue
            try:
                f5 = getattr(fr, "f5", fr)
                if f5 is None or not len(f5.t):
                    continue
                b = from_frame(f5, iso)
                out["read"] += 1
                rid = record_id(iso, sym)
                doc = have.get(rid)
                if doc is not None and isinstance(doc.get("alert"), dict):
                    i = _locate(b, doc["alert"].get("bar_t"))
                    if i is None:
                        continue
                    hm, _hu = horizon_of(d, doc.get("window"))
                    if store.upsert_divergence(rid, {}, {"live": live_state(b, i, doc.get("window"), hm), "at": stamp}):
                        out["updated"] += 1
                    continue
                a = detect(b, units[sym]["clock"], d)
                if a is None:
                    continue
                out["alerted"] += 1
                hm, _hu = horizon_of(d, a["window"])
                ins = {"date": iso, "symbol": sym, "window": a["window"], "alert": _alert_block(a),
                       "ring": _ring_block(units[sym]), "recorded_at": stamp.isoformat(), "source": SOURCES[0],
                       "half_day": _half_day(d)}
                if store.upsert_divergence(rid, ins, {"live": live_state(b, a["i"], a["window"], hm), "at": stamp}):
                    out["new"] += 1
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala divergence: %s failed: %s", sym, type(exc).__name__)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala divergence: the step failed: %s", type(exc).__name__)
    return out


def _utc(now: Optional[datetime]) -> datetime:
    if now is None:
        return datetime.now(UTC)
    return now.astimezone(UTC) if now.tzinfo is not None else now.replace(tzinfo=UTC)


# ── the nightly ───────────────────────────────────────────────────────────────────────────────────────────────────
def _default_load_day(sym: str, day: date) -> tuple:
    """(1-minute DataFrame | None, provider_failed) — the ledger's `_default_load_day` shape, the raw frame kept
    (bars.build_frames reads it): daytrading.data.load_intraday(for_massive(sym), day, pre + after hours)."""
    from daytrading import data as dt_data
    from sepa.symbols import for_massive
    try:
        dt_data.clear_fetch_failed()
        df = dt_data.load_intraday(for_massive(sym), day, include_premarket=True, include_afterhours=True)
        return df, bool(df is None and dt_data.last_fetch_failed())
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala divergence: 1-minute load failed for %s %s: %s", sym, day, type(exc).__name__)
        return None, True


def _graded(doc: dict) -> bool:
    g = (doc or {}).get("grade")
    return isinstance(g, dict) and g.get("version") == GC.DIVERGENCE_GRADE_VERSION


def grade_step(store, now: datetime, *, load_day: Optional[Callable] = None, max_loads: Optional[int] = None) -> dict:
    """🧨 THE NIGHTLY (nightly.main → grade_divergence). sessions = the last GC.LEDGER_GRADE_LOOKBACK_SESSIONS market
    days up to today (the 🏁's window). ONE per-run loader memo keyed (sym, day); the cap (max_loads, else
    GC.DIVERGENCE_GRADE_MAX_LOADS) counts LOADER CALLS exactly as ledger.grade_step does (ok | deferred_cap |
    load_failed).
      (1) GRADE FIRST: every doc lacking grade.version == DIVERGENCE_GRADE_VERSION whose horizon + BAR_SETTLE_SEC has
          passed — load prev + session → bars.build_frames(...).f5 → locate alert.bar_t (missing → bar_missing,
          faulted) → re-read r1 (|Δ| ≤ 1e-6 → recheck_ok) → trade() → $set grade + graded_at. Horizon not ended →
          not_due (no grade key).
      (2) RE-DETECT the sessions whose extended close + settle has passed and that the GC.DIVERGENCE_STATE_ID marker
          does not hold, NEWEST FIRST: units_today → load (memo, cap) → detect → no doc: insert (source "nightly");
          same bar: nothing; a different bar: MOVE (alert / window replaced, live_alert = the pass's block unless
          set, redetect_moved, grade cleared); no listing: redetect_missing (doc + grade kept). A session is marked
          only when every unit of it loaded; marker entries outside `sessions` are pruned on the write. A marker read
          that raises → every session unmarked (the cap still bounds the loads).
      (3) GRADE the docs (2) inserted or moved from the frames (2) built — no new loader call.
    -> {"sessions", "read_fault", "marked", STEP_KEYS…}. Idempotent: a second run the same night writes 0."""
    from . import bars as B
    from . import context as CX
    from . import ledger as LG
    from . import nightly as NG
    now = _utc(now)
    end_session = NG.default_session(now)
    sessions = CX.history_window(LG._next_market_day(end_session), GC.LEDGER_GRADE_LOOKBACK_SESSIONS)
    keep = {d.isoformat() for d in sessions}
    out: dict = {"sessions": [d.isoformat() for d in sessions], "read_fault": False, "marked": []}
    out.update({k: 0 for k in STEP_KEYS})
    docs = store.divergence_docs(sessions)
    if docs is None:
        out["read_fault"] = True
        return out
    by_id = {doc.get("_id"): doc for doc in docs if isinstance(doc, dict) and doc.get("_id")}
    out["rows"] = len(by_id)
    cap = int(max_loads) if max_loads is not None else int(GC.DIVERGENCE_GRADE_MAX_LOADS)
    load = load_day or _default_load_day
    memo: dict = {}
    built: dict = {}
    stamp = now.isoformat()

    def days_for(sym: str, days: list) -> str:
        """ok | deferred_cap | load_failed — ledger.grade_step's days_for, loader calls counted."""
        miss = [x for x in days if (sym, x) not in memo]
        if out["loads"] + len(miss) > cap:
            return "deferred_cap"
        for x in miss:
            out["loads"] += 1
            try:
                res = load(sym, x)
                raw, failed = (res if isinstance(res, tuple) else (res, False))
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala divergence: load raised for %s %s: %s", sym, x, type(exc).__name__)
                raw, failed = None, True
            memo[(sym, x)] = (raw, bool(failed))
        if any(memo[(sym, x)][1] for x in days):
            return "load_failed"
        return "ok"

    def series(sym: str, d: date) -> Optional[Bars5]:
        k = (sym, d.isoformat())
        if k not in built:
            raw_prev, raw_today = memo[(sym, LG._prev_market_day(d))][0], memo[(sym, d)][0]
            fr = B.build_frames(sym, d, now, raw_prev, raw_today)
            built[k] = from_frame(fr.f5, d) if fr is not None and fr.f5 is not None else None
        return built[k]

    def grade_doc(doc: dict, b: Optional[Bars5], recheck: bool = True) -> None:
        d = _as_date(doc["date"])
        window = doc.get("window")
        a = doc.get("alert") if isinstance(doc.get("alert"), dict) else {}
        i = _locate(b, a.get("bar_t")) if b is not None else None
        if i is None:
            out["bar_missing"] += 1
            out["faulted"] += 1
            return
        hm, _hu = horizon_of(d, window)
        ok = True
        if recheck:
            R1 = r1_series(b, atr_series(b))
            r_now, r_was = R1[i], _f(a.get("r1"))
            ok = r_now is not None and r_was is not None and abs(r_now - r_was) <= _RECHECK_TOL
        g = dict(trade(b, i, window, hm), horizon_t=_hstamp(b, hm), recheck_ok=bool(ok),
                 version=GC.DIVERGENCE_GRADE_VERSION)
        if store.upsert_divergence(doc["_id"], {}, {"grade": g, "graded_at": stamp, "at": now}):
            out["written"] += 1
            out["graded"] += 1
            doc["grade"] = g

    # (1) GRADE FIRST
    for doc in sorted(by_id.values(), key=lambda x: (str(x.get("date") or ""), str(x.get("symbol") or "")),
                      reverse=True):
        try:
            if _graded(doc):
                continue
            d = _as_date(doc["date"])
            _hm, hu = horizon_of(d, doc.get("window"))
            if now < hu + SETTLE:
                out["not_due"] += 1
                continue
            sym = str(doc.get("symbol") or "").upper()
            st = days_for(sym, [LG._prev_market_day(d), d])
            if st != "ok":
                out[st] += 1
                continue
            grade_doc(doc, series(sym, d))
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala divergence: grading %s failed: %s", doc.get("_id"), type(exc).__name__)
            out["faulted"] += 1

    # (2) RE-DETECT
    try:
        marker = store.get_state(GC.DIVERGENCE_STATE_ID) or {}
    except Exception as exc:                                    # noqa: BLE001 — fail OPEN on the marker
        log.warning("gajjala divergence: the re-detect marker could not be read: %s", type(exc).__name__)
        marker = {}
    checked = marker.get("checked") if isinstance(marker.get("checked"), dict) else {}
    checked = dict(checked)
    from . import alerts as AL
    due = []
    for d in sorted(sessions, reverse=True):
        if now < datetime.combine(d, AL._closes(d)[1], tzinfo=ET).astimezone(UTC) + SETTLE:
            continue
        if d.isoformat() in checked:
            out["skipped_marked"] += 1
            continue
        due.append(d)
    to_grade: list = []
    for d in due:
        iso = d.isoformat()
        try:
            units = units_today(store, d)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala divergence: the cohort of %s could not be read: %s", iso, type(exc).__name__)
            out["read_fault"] = True
            break
        complete, alerted, loads0 = True, 0, out["loads"]
        for sym in sorted(units):
            try:
                st = days_for(sym, [LG._prev_market_day(d), d])
                if st != "ok":
                    out[st] += 1
                    complete = False
                    continue
                b = series(sym, d)
                a = detect(b, units[sym]["clock"], d) if b is not None else None
                rid = record_id(iso, sym)
                doc = by_id.get(rid)
                if a is not None:
                    alerted += 1
                if a is not None and doc is None:
                    ins = {"date": iso, "symbol": sym, "window": a["window"], "alert": _alert_block(a),
                           "ring": _ring_block(units[sym]), "recorded_at": stamp, "source": SOURCES[1],
                           "half_day": _half_day(d)}
                    if store.upsert_divergence(rid, ins, {"at": now, "redetected_at": stamp}):
                        out["written"] += 1
                        out["redetected"] += 1
                        new = dict(ins, _id=rid)
                        by_id[rid] = new
                        to_grade.append((new, b))
                elif a is not None:
                    old = doc.get("alert") if isinstance(doc.get("alert"), dict) else {}
                    if old.get("bar_t") == a["bar_t"]:
                        continue
                    sets = {"alert": _alert_block(a), "window": a["window"], "redetect_moved": True,
                            "redetected_at": stamp, "grade": None, "graded_at": None, "at": now}
                    if not isinstance(doc.get("live_alert"), dict):
                        sets["live_alert"] = dict(old)   # the pass's block, kept once (its bar_t carries its window)
                    if store.upsert_divergence(rid, {}, sets):
                        out["written"] += 1
                        out["redetect_moved"] += 1
                        doc.update(sets)
                        to_grade.append((doc, b))
                elif doc is not None:
                    if store.upsert_divergence(rid, {}, {"redetect_missing": True, "redetected_at": stamp,
                                                         "at": now}):
                        out["written"] += 1
                        out["redetect_missing"] += 1
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala divergence: re-detecting %s %s failed: %s", iso, sym, type(exc).__name__)
                out["faulted"] += 1
                complete = False
        if complete:
            checked[iso] = {"at": stamp, "units": len(units), "alerted": alerted, "loads": out["loads"] - loads0}
            out["marked"].append(iso)
    pruned = {k: v for k, v in checked.items() if k in keep}
    if out["marked"] or len(pruned) != len(checked):
        try:
            store.set_state(GC.DIVERGENCE_STATE_ID, {"checked": pruned, "at": stamp})
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala divergence: the re-detect marker could not be written: %s", type(exc).__name__)

    # (3) GRADE what (2) inserted or moved — from the frames in hand, never a new loader call
    for doc, b in to_grade:
        try:
            if b is None:
                out["deferred_grade"] += 1
                continue
            d = _as_date(doc["date"])
            _hm, hu = horizon_of(d, doc.get("window"))
            if now < hu + SETTLE:
                out["not_due"] += 1
                continue
            grade_doc(doc, b, recheck=True)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala divergence: grading %s failed: %s", doc.get("_id"), type(exc).__name__)
            out["faulted"] += 1
    return out


def grade_divergence(now: datetime, *, store=None) -> dict:
    """The fence nightly.main calls: {"grade": grade_step(store or the GG5 store, now)}; a raise → {"error": "grade:
    <Type>"} (logged). Never raises; never in the nightly's `errors` or exit code."""
    try:
        if store is None:
            from . import store as ST
            store = ST.default()
        return {"grade": grade_step(store, now)}
    except Exception as exc:                                    # noqa: BLE001
        log.exception("gajjala nightly: the 🧨 divergence record's grade failed")
        return {"error": f"grade: {type(exc).__name__}"}


__all__ = ["Bars5", "from_frame", "from_tile", "atr_series", "r1_series", "bar_close_utc", "eligible", "first_crossing",
           "v2_read", "alert_read", "up_cross_before", "horizon_of", "entry_of", "x3_exit", "net_pct", "trade",
           "units_today", "detect", "live_state", "record_id", "run_step", "grade_step", "grade_divergence"]
