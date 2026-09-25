"""⚡ Momentum burst — relative volume surging AND the print a little above
today's low (Chart Maps, 2026-09-24).

THE ASK (Ajay 2026-09-24, verbatim): "volume and ? <1% reversal if its already
greator >1.5% is not enough runway for me to catch the upside potential.. is of
no use to me". Direction: "Up moves only". Checkbox: "Pin + badge, hide
nothing". Numbers: "Use the app's numbers". Asked whether 1.0-1.5% counts:
"yes" -> ONE threshold, 1.5% inclusive.

THE RULE (the only one this module knows):
  (a) relative volume >= BURST_RVOL_MIN, time-of-day fair: today's actual
      shares against the full 50-session average, or — in RTH, once the
      projection start has passed — today's volume projected to a full session
      on `sepa.intraday_volume`'s curve. Never a partial day against a full one.
  (b) the print MORE than 0% and AT MOST BURST_MAX_OFF_LOW_PCT above today's
      session low, judged at PCT_DP decimals (1.5% passes, 1.51% fails).
  (c) up moves only = the print above that low, which (b) already enforces.
      The day's change is echoed for the hover and is NOT a leg.

PURE: no I/O, no Mongo, no network, no clock except `_session_fraction` when
the caller passes no time. DISPLAY ONLY: it pins and badges on Chart Maps; it
gates nothing, pushes nothing, sizes nothing and enters no lane. UNMEASURED —
no study stands behind it, and every string it builds says so.

Every number in every string comes from a constant below or from the read's
own inputs; the tests monkeypatch the two thresholds and watch the words move.
"""
from __future__ import annotations

import math
from datetime import date, datetime, time
from typing import Any, Iterable, Optional

from sepa.breakout_audit import VOL_AVG_BARS                     # 50
from sepa.intraday_volume import projected_relvol
from supply_demand.demand_reentry import (RVOL_MIN_FRACTION, SESSION_MINUTES,
                                          _session_fraction)
from supply_demand.timeframes import HALF_DAYS
from supply_demand.zone_store import drop_today

CITED = False
MEASURED = False
STATUS = "unmeasured"

# The app's 1.5x volume bar. Mirrors trading.auto_entry.AUTO_RELVOL_MIN and the
# frontend's cheetahVerdict.BONDE_BREAKOUT_RVOL; text-locked by test, NOT
# imported (auto_entry builds the broker at import).
BURST_RVOL_MIN = 1.5
# Ajay 2026-09-24: "if its already greator >1.5% is not enough runway";
# 1.0-1.5 counts ("yes"). Inclusive.
BURST_MAX_OFF_LOW_PCT = 1.5
# The % he reads is the % that decides.
PCT_DP = 2
LOW_KIND = "session_low"

# The Back in Demand display floor (~31 min): the one-line flip is his call.
BURST_PROJECTION_MIN_FRAC = RVOL_MIN_FRACTION
# Mirrors trading.auto_entry.VOL_CONFIRM_MIN_FRAC; text-locked by test, never
# imported. WORDING ONLY — the "early projection" warning in the hover.
LANE_VOL_CONFIRM_MIN_FRAC = round(120.0 / 390.0, 4)
# NYSE half-day close, supply_demand/timeframes.py HALF_DAYS ("13:00 ET close").
HALF_DAY_CLOSE_ET = time(13, 0)

STATE_BURST, STATE_NO, STATE_UNKNOWN = "burst", "no", "unknown"
UNKNOWN_CODES = ("premarket", "no_print", "no_low", "no_volume", "no_avg",
                 "rvol_early", "rvol_half_day")
FAIL_CODES = ("rvol_low", "at_low", "runway_used")
READ_KEYS = ("state", "on", "reasons", "reason_text", "rvol", "rvol_basis",
             "rvol_actual", "rvol_projected", "session_pct", "projection_early",
             "today_vol", "avg_vol_50", "session_day", "off_low_pct", "low",
             "low_kind", "print", "print_session", "print_source", "as_of",
             "ext_print", "ext_as_of", "prev_close", "day_chg_pct", "session",
             "half_day", "badge", "title", "measured")

_SESSIONS_READ = ("rth", "afterhours", "closed")


# --------------------------------------------------------------------------
# number hygiene
# --------------------------------------------------------------------------
def _f(x: Any) -> Optional[float]:
    """A finite float, else None. bool / NaN / inf / junk / None -> None."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError, OverflowError):
        return None
    return v if math.isfinite(v) else None


def _pos(x: Any) -> Optional[float]:
    v = _f(x)
    return v if v is not None and v > 0 else None


def _g(x: float) -> str:
    """A constant as he reads it: 1.5 -> '1.5', 2.0 -> '2'."""
    return f"{float(x):g}"


def _usd(x: float) -> str:
    return f"${x:,.2f}"


def _minutes(frac: float) -> int:
    return int(round(float(frac) * SESSION_MINUTES))


def _day_iso(day: Any) -> Optional[str]:
    if day is None:
        return None
    if isinstance(day, datetime):
        return day.date().isoformat()
    if isinstance(day, date):
        return day.isoformat()
    try:
        return date.fromisoformat(str(day)[:10]).isoformat()
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# frames
# --------------------------------------------------------------------------
def frame_last_day(frame) -> Optional[str]:
    """ISO date of the frame's last bar; None on None / empty / error."""
    try:
        if frame is None or len(frame) == 0:
            return None
        return frame.index[-1].date().isoformat()
    except Exception:                                           # noqa: BLE001
        return None


def avg_volume_before(frame, day) -> Optional[float]:
    """Mean volume of the last VOL_AVG_BARS closed sessions BEFORE `day`.

    `drop_today(frame, day)` first — the price cache holds today's in-progress
    bar hourly, and a day inside its own average flatters nothing honestly.
    None unless exactly VOL_AVG_BARS rows, every one finite, mean > 0."""
    try:
        iso = _day_iso(day)
        if frame is None or iso is None:
            return None
        past = drop_today(frame, date.fromisoformat(iso))
        if past is None or len(past) < VOL_AVG_BARS:
            return None
        vals = [_f(v) for v in list(past["volume"].iloc[-VOL_AVG_BARS:])]
        if len(vals) != VOL_AVG_BARS or any(v is None for v in vals):
            return None
        mean = sum(vals) / VOL_AVG_BARS
        return mean if math.isfinite(mean) and mean > 0 else None
    except Exception:                                           # noqa: BLE001
        return None


# --------------------------------------------------------------------------
# session
# --------------------------------------------------------------------------
def burst_session(tape_session: Optional[str], now_et: Optional[datetime]) -> tuple:
    """(session, half_day). The tape clock treats a half day as running to
    16:00; after the 13:00 close that day is read as after hours."""
    try:
        half = now_et is not None and now_et.date().isoformat() in HALF_DAYS
    except Exception:                                           # noqa: BLE001
        half = False
    if half and tape_session == "rth" and now_et.time() >= HALF_DAY_CLOSE_ET:
        return ("afterhours", True)
    return (tape_session, bool(half))


def session_frac(session: Optional[str], now_et: Optional[datetime] = None, *,
                 half_day: bool = False) -> Optional[float]:
    """How much of the session is done. RTH on a full day: the clock fraction.
    RTH on a half day: None (the curve is a SESSION_MINUTES-minute curve).
    After hours / closed: 1.0. Anything else: None."""
    if session == "rth":
        if half_day:
            return None
        try:
            return _f(_session_fraction(now_et))
        except Exception:                                       # noqa: BLE001
            return None
    if session in ("afterhours", "closed"):
        return 1.0
    return None


# --------------------------------------------------------------------------
# legs
# --------------------------------------------------------------------------
def rvol_leg(today_vol, avg_vol, session: Optional[str], frac: Optional[float], *,
             half_day: bool = False) -> dict:
    """The volume leg. {verdict, code, rvol, basis, actual, projected,
    session_pct, projection_early}."""
    frac = _f(frac)
    out = {"verdict": "unknown", "code": None, "rvol": None, "basis": None,
           "actual": None, "projected": None,
           "session_pct": int(round(frac * 100)) if frac is not None else None,
           "projection_early": False}
    tv, av = _pos(today_vol), _pos(avg_vol)
    if tv is None:
        out["code"] = "no_volume"
        return out
    if av is None:
        out["code"] = "no_avg"
        return out
    actual = _f(round(tv / av, 2))
    out["actual"] = actual
    if actual is None:
        out["code"] = "no_volume"
        return out
    if session == "rth":
        projected = None
        if frac is not None and frac >= BURST_PROJECTION_MIN_FRAC:
            try:
                projected = _f(projected_relvol(tv, av, frac))
            except Exception:                                   # noqa: BLE001
                projected = None
        out["projected"] = projected
        if actual >= BURST_RVOL_MIN:
            out.update(verdict="pass", code=None, rvol=actual, basis="actual")
        elif projected is not None and projected >= BURST_RVOL_MIN:
            out.update(verdict="pass", code=None, rvol=projected, basis="projected",
                       projection_early=bool(frac < LANE_VOL_CONFIRM_MIN_FRAC))
        elif projected is not None:
            out.update(verdict="fail", code="rvol_low", rvol=projected, basis="projected")
        elif half_day:
            out.update(verdict="unknown", code="rvol_half_day", rvol=actual, basis="actual")
        else:
            out.update(verdict="unknown", code="rvol_early", rvol=actual, basis="actual")
        return out
    if session in ("afterhours", "closed"):
        out.update(rvol=actual, basis="session")
        if actual >= BURST_RVOL_MIN:
            out.update(verdict="pass", code=None)
        else:
            out.update(verdict="fail", code="rvol_low")
        return out
    out["code"] = "premarket"
    return out


def off_low_pct(px, low) -> Optional[float]:
    """% the print sits above the low, at PCT_DP decimals. None if unusable."""
    p, lo = _pos(px), _pos(low)
    if p is None or lo is None:
        return None
    return _f(round((p / lo - 1.0) * 100.0, PCT_DP))


def day_change_pct(px, prev) -> Optional[float]:
    """% change of the print vs yesterday's close, at PCT_DP decimals."""
    p, pv = _pos(px), _pos(prev)
    if p is None or pv is None:
        return None
    return _f(round((p / pv - 1.0) * 100.0, PCT_DP))


# --------------------------------------------------------------------------
# wording
# --------------------------------------------------------------------------
def rule_text() -> str:
    mn, mx = _g(BURST_RVOL_MIN), _g(BURST_MAX_OFF_LOW_PCT)
    return (f"Rule: relative volume at least {mn}× AND the print more than 0% and "
            f"at most {mx}% above today's low. Past {mx}% above the low there is "
            f"not enough runway. Up moves only = the print above the low; the "
            f"day's change is shown, not required. UNMEASURED — no study behind "
            f"it. It pins and badges; it gates nothing, pushes nothing, sizes "
            f"nothing and enters no lane.")


def _reason_text(code: str, *, actual=None, rvol=None, off=None) -> str:
    mn, mx = _g(BURST_RVOL_MIN), _g(BURST_MAX_OFF_LOW_PCT)
    a = f"{actual:.2f}" if actual is not None else "?"
    r = f"{rvol:.2f}" if rvol is not None else "?"
    o = f"{off:+.2f}" if off is not None else "?"
    if code == "premarket":
        return ("pre-market — the day's low does not exist until the 09:30 ET "
                "open, so this cannot pass yet")
    if code == "no_print":
        return ("no print dated today in the snapshot (halted, not traded this "
                "session, or a stale snapshot)")
    if code == "no_low":
        return "no session low in the snapshot yet"
    if code == "no_volume":
        return "no session volume in the snapshot"
    if code == "no_avg":
        return f"fewer than {VOL_AVG_BARS} closed sessions of volume to average"
    if code == "rvol_early":
        return (f"RVOL {a}× so far — under {mn}×, and the full-session projection "
                f"starts {_minutes(BURST_PROJECTION_MIN_FRAC)} min after the open")
    if code == "rvol_half_day":
        return (f"RVOL {a}× so far — under {mn}×, and on a half-day session the "
                f"full-session projection is off")
    if code == "rvol_low":
        return f"RVOL {r}× — under {mn}×"
    if code == "at_low":
        return f"{o}% above today's low — at the low, no reversal yet"
    if code == "runway_used":
        return f"{o}% above today's low — past {mx}%, not enough runway"
    return str(code)


# --------------------------------------------------------------------------
# the read
# --------------------------------------------------------------------------
def read(*, px, low, prev_close, today_vol, avg_vol, session, frac=None,
         half_day=False, session_day=None, print_session=None, print_source=None,
         as_of=None, ext_print=None, ext_as_of=None) -> dict:
    """One tile's ⚡ read, keys exactly READ_KEYS. Never raises on junk input."""
    p, lo, prev = _f(px), _f(low), _f(prev_close)
    tv, av = _f(today_vol), _f(avg_vol)
    fr = _f(frac)
    half = half_day is True
    ext = _f(ext_print)
    day_chg = day_change_pct(p, prev)

    fails: list = []
    unknowns: list = []
    leg = {"verdict": "unknown", "code": None, "rvol": None, "basis": None,
           "actual": None, "projected": None,
           "session_pct": int(round(fr * 100)) if fr is not None else None,
           "projection_early": False}
    off = None

    if session not in _SESSIONS_READ:
        unknowns.append("premarket")
    else:
        if p is None or p <= 0:
            unknowns.append("no_print")
        if lo is None or lo <= 0:
            unknowns.append("no_low")
        leg = rvol_leg(tv, av, session, fr, half_day=half)
        if leg["verdict"] == "fail":
            fails.append(leg["code"])
        elif leg["verdict"] == "unknown" and leg["code"]:
            unknowns.append(leg["code"])
        if "no_print" not in unknowns and "no_low" not in unknowns:
            off = off_low_pct(p, lo)
            if off is None:
                unknowns.append("no_print")
            elif off <= 0:
                fails.append("at_low")
            elif off > BURST_MAX_OFF_LOW_PCT:
                fails.append("runway_used")

    fails = [c for c in FAIL_CODES if c in fails]
    unknowns = [c for c in UNKNOWN_CODES if c in unknowns]
    if fails:
        state, reasons = STATE_NO, fails + unknowns
    elif unknowns:
        state, reasons = STATE_UNKNOWN, unknowns
    else:
        state, reasons = STATE_BURST, []
    on = state == STATE_BURST
    rvol = _f(leg.get("rvol"))
    actual = _f(leg.get("actual"))
    reason_text = [_reason_text(c, actual=actual, rvol=rvol, off=off) for c in reasons]

    badge = None
    if on and rvol is not None and off is not None:
        badge = f"⚡ Momentum burst · {rvol:.2f}× vol · +{off:.2f}% off low"

    lines: list = []
    mn, mx = _g(BURST_RVOL_MIN), _g(BURST_MAX_OFF_LOW_PCT)
    if on:
        lines.append(f"⚡ Momentum burst — RVOL {rvol:.2f}× (at least {mn}×) and "
                     f"the print {off:+.2f}% above today's low (limit {mx}%). "
                     f"UNMEASURED.")
    elif state == STATE_NO:
        lines.append(f"⚡ Not a momentum burst: {'; '.join(reason_text)}.")
    else:
        lines.append(f"⚡ Unknown: {'; '.join(reason_text)}.")

    basis = leg.get("basis")
    if rvol is not None:
        if basis == "projected":
            pct = leg.get("session_pct")
            ln = (f"RVOL {rvol:.2f}× — today's volume projected to a full session "
                  f"on the app's intraday volume curve ({pct}% of the session "
                  f"done); {actual:.2f}× the {VOL_AVG_BARS}-session average so "
                  f"far. Day volume includes pre-market prints.")
            if leg.get("projection_early"):
                ln += (f" Early projection: it runs high this soon after the open "
                       f"— the Auto-Pilot does not trust it before "
                       f"{_minutes(LANE_VOL_CONFIRM_MIN_FRAC)} min.")
            lines.append(ln)
        elif basis == "actual" and rvol >= BURST_RVOL_MIN:
            lines.append(f"RVOL {rvol:.2f}× — today's volume already beats {mn}× "
                         f"the full {VOL_AVG_BARS}-session average; no projection "
                         f"needed. Day volume includes pre-market prints.")
        elif basis == "actual":
            lines.append(f"RVOL {rvol:.2f}× so far against the full "
                         f"{VOL_AVG_BARS}-session average. Day volume includes "
                         f"pre-market prints.")
        elif basis == "session":
            lines.append(f"RVOL {rvol:.2f}× — the session's volume (the snapshot "
                         f"also counts pre- and after-hours prints) against the "
                         f"{VOL_AVG_BARS}-session average.")

    day_iso = _day_iso(session_day)
    if off is not None:
        if session == "rth":
            src = f"live RTH · {as_of}" if as_of else "live RTH"
        else:
            where = "cached daily bar" if print_source == "daily_bar" else "live snapshot"
            src = f"the {day_iso} close from the {where}"
        lines.append(f"{off:+.2f}% above today's low {_usd(lo)} — print {_usd(p)} ({src}).")
        lines.append("A snapshot has no timing: it cannot tell a fresh reversal off "
                     "the low from a slide back toward it.")
    if ext is not None:
        lines.append(f"After-hours last trade {_usd(ext)} at {ext_as_of} — shown, not read.")
    if day_chg is not None:
        lines.append(f"{day_chg:+.2f}% on the day vs yesterday's close {_usd(prev)} "
                     f"— shown, not required.")
    lines.append(rule_text())

    avg_out = _f(round(av, 2)) if av is not None else None
    return {
        "state": state,
        "on": on,
        "reasons": list(reasons),
        "reason_text": reason_text,
        "rvol": rvol,
        "rvol_basis": basis,
        "rvol_actual": actual,
        "rvol_projected": _f(leg.get("projected")),
        "session_pct": leg.get("session_pct"),
        "projection_early": bool(leg.get("projection_early")),
        "today_vol": tv,
        "avg_vol_50": avg_out,
        "session_day": day_iso,
        "off_low_pct": off,
        "low": lo,
        "low_kind": LOW_KIND,
        "print": p,
        "print_session": print_session if isinstance(print_session, str) else None,
        "print_source": print_source if isinstance(print_source, str) else None,
        "as_of": as_of if isinstance(as_of, str) else None,
        "ext_print": ext,
        "ext_as_of": ext_as_of if (ext is not None and isinstance(ext_as_of, str)) else None,
        "prev_close": prev,
        "day_chg_pct": day_chg,
        "session": session if isinstance(session, str) else None,
        "half_day": half,
        "badge": badge,
        "title": "\n".join(lines),
        "measured": False,
    }


def is_burst(rd) -> bool:
    return isinstance(rd, dict) and rd.get("on") is True and rd.get("state") == STATE_BURST


def counts(reads: Iterable) -> dict:
    """{"burst", "no", "unknown"} — a None / malformed read counts as unknown."""
    out = {STATE_BURST: 0, STATE_NO: 0, STATE_UNKNOWN: 0}
    for rd in reads or []:
        st = rd.get("state") if isinstance(rd, dict) else None
        if st == STATE_BURST and is_burst(rd):
            out[STATE_BURST] += 1
        elif st == STATE_NO:
            out[STATE_NO] += 1
        else:
            out[STATE_UNKNOWN] += 1
    return out


_count_reads = counts


def board_note(session: Optional[str], frac: Optional[float] = None, *,
               half_day: bool = False, counts: Optional[dict] = None,
               reads: Optional[list] = None) -> str:
    """The one line the page prints under the board while ⚡ is on."""
    mn = _g(BURST_RVOL_MIN)
    n = VOL_AVG_BARS
    fr = _f(frac)
    if session == "rth":
        if half_day:
            note = (f"Half-day session — the full-session projection assumes a "
                    f"{SESSION_MINUTES}-minute day, so only today's actual volume "
                    f"already at {mn}× the full {n}-session average counts.")
        elif fr is None or fr < BURST_PROJECTION_MIN_FRAC:
            note = (f"Live, {_minutes(fr or 0.0)} min into the session — volume "
                    f"counts only if today's shares already beat {mn}× the full "
                    f"{n}-session average; the full-session projection starts "
                    f"{_minutes(BURST_PROJECTION_MIN_FRAC)} min after the open.")
        elif fr < LANE_VOL_CONFIRM_MIN_FRAC:
            note = (f"Live, {int(round(fr * 100))}% of the session done — today's "
                    f"volume (pre-market included) is projected to a full session "
                    f"on the app's intraday volume curve; this early it runs high "
                    f"— the Auto-Pilot does not trust it before "
                    f"{_minutes(LANE_VOL_CONFIRM_MIN_FRAC)} min.")
        else:
            note = (f"Live, {int(round(fr * 100))}% of the session done — today's "
                    f"volume (pre-market included) is projected to a full session "
                    f"on the app's intraday volume curve before it is compared "
                    f"with the {n}-session average; never a partial day against "
                    f"a full one.")
    elif session == "afterhours":
        note = (f"After the close — the session's closing print and its volume "
                f"against the {n}-session average. After-hours trades are shown "
                f"in the hover, not read.")
    elif session == "closed":
        note = (f"Market closed — the last session's close and its volume against "
                f"the {n}-session average.")
    else:
        # Pre-market (and a session the clock could not name — `read`
        # short-circuits it the same way). The line already says every read is
        # unknown, so the suffix below is not repeated.
        return ("Pre-market — the day's low does not exist until the 09:30 ET "
                "open, so every ⚡ read is unknown and none can pass.")

    rl = list(reads or [])
    c = counts if isinstance(counts, dict) else _count_reads(rl)
    total = sum(int(c.get(k) or 0) for k in (STATE_BURST, STATE_NO, STATE_UNKNOWN))
    if total > 0 and int(c.get(STATE_UNKNOWN) or 0) == total:
        tally: dict = {}
        order: list = []
        for rd in rl:
            for txt in (rd.get("reason_text") or []) if isinstance(rd, dict) else []:
                if txt not in tally:
                    order.append(txt)
                tally[txt] = tally.get(txt, 0) + 1
        if order:
            top = max(order, key=lambda k: (tally[k], -order.index(k)))
            note += f" Every read here is unknown: {top}."
    return note
