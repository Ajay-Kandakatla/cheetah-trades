"""⏰ Time-window glow (2026-11-24) — two descriptive clock windows for the 🚩 Gajjala page, served for a reminder line.

Ajay 2026-11-24, verbatim: "We did some research yesterday about highest price action time 33% was after hours can you
add a reminder of that somwhere for me like radiating when we enter those timings".

The study (eod-audits/research/2026-11-22_winner_time_of_day/: report.md, prereg.md, tod.py) found the 33% is the FIRST
HOUR's share of winners' biggest burst; after hours holds about its fair share of the day's highs. Its results ship in
data/winner_time_of_day_2026_11_22.json (the study's results.json + additive per-sample keys, re-run by
backend/scripts/winner_time_of_day_2026_11_22.py — every original key byte-equal to the study's). This module reads that
file ONCE and builds every number in its sentences from it (or from a house constant by name) — none is typed here.

  W1 "⏰ Burst window" = the study's first-hour bucket (its label carries the clock: 09:30–10:30 ET).
  W2 "⏰ Second wave"  = the hours W2_HOURS of the file's hourly tables (15:00 + 16:00 → 15:00–17:00 ET).

Closed day (market_hours.gate.closed_reason) → `closed: true` (windows still listed; the FE never glows). Half day
(supply_demand.timeframes.HALF_DAYS): a window ending after that day's regular close is DROPPED, never shortened — the
study measured full sessions, and on a 13:00 close 15:00–17:00 is no longer "the close into after hours"; the served
`note` says so. A missing / corrupt file → `state: "fault"`, no windows, never a raise.

Display only: no gate, no push, no record, no trade. Descriptive timing, not an entry rule. UNMEASURED as a trade signal.
"""
from __future__ import annotations

import functools
import json
import logging
import re
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC

log = logging.getLogger("chart_maps.gajjala.time_windows")

ET = ZoneInfo("America/New_York")
KIND = "gajjala_time_windows"
API_PATH = "/chart-maps/gajjala/time-windows"
DATA_PATH = Path(__file__).resolve().parent / "data" / "winner_time_of_day_2026_11_22.json"
SAMPLE = "B_w40_universe"                 # the study's main sample (report.md "Main sample = B") — a key into the file
W1_BUCKET = "first hour 09:30-10:30"      # a key into the file's burst / peak tables; its label carries the clock
AH_BUCKET = "after hours 16:00-20:00"     # a key into the file's peak table (the after-hours fair-share line)
W2_HOURS = ("15:00", "16:00")             # keys into the file's hourly tables — W2 = these whole hours
SLOT_MIN = 15                             # the width of the file's *_quarter_k slots (the script's quarter_k)
W1_KEY, W2_KEY = "burst_window", "second_wave"
W1_LABEL, W2_LABEL = "⏰ Burst window", "⏰ Second wave"
TAIL = "Descriptive timing, not an entry rule. UNMEASURED as a trade signal. Not advice."
FAULT_TEXT = "⏰ time windows unavailable — the study file could not be read."
_CLOCK_RE = re.compile(r"(\d{2}:\d{2})-(\d{2}:\d{2})")
_STUDY_DATE_RE = re.compile(r"(\d{4})_(\d{2})_(\d{2})$")


# ── the file, read once ──────────────────────────────────────────────────────────────────────────────────────────────
@functools.lru_cache(maxsize=4)
def _load(path: str) -> Optional[dict]:
    """The study file (one read per path per process); None when it is missing or not a JSON object."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:                                  # missing / unreadable / corrupt
        log.warning("time_windows: %s unreadable: %s", path, type(exc).__name__)
        return None
    return data if isinstance(data, dict) else None


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _clock(label: str) -> tuple:
    """(start, end) minutes-of-day from a study bucket label ('… 09:30-10:30')."""
    m = _CLOCK_RE.search(label)
    if not m:
        raise ValueError(f"no clock in bucket label {label!r}")
    return _hm(m.group(1)), _hm(m.group(2))


def _row(table: list, bucket: str) -> dict:
    for r in table:
        if r.get("bucket") == bucket:
            return r
    raise KeyError(bucket)


def _pct(k: int, n: int) -> float:
    if not isinstance(n, int) or n <= 0:
        raise ValueError("empty sample")
    return round(100.0 * k / n, 1)


def _slot_sum(quarter_k: dict, start: int, end: int) -> int:
    return sum(int(v) for k, v in quarter_k.items() if start <= _hm(k) < end)


def _study_date() -> str:
    m = _STUDY_DATE_RE.search(DATA_PATH.stem)
    return "-".join(m.groups()) if m else DATA_PATH.stem


def numbers(data: dict) -> dict:
    """Every number the sentences print, read from the study file (raises on a malformed file)."""
    s = data[SAMPLE]
    burst, peak = s["burst"], s["peak"]
    clocks = [_clock(r["bucket"]) for r in burst]
    clock_start, clock_end = min(a for a, _ in clocks), max(b for _, b in clocks)
    clock_min = sum(b - a for a, b in clocks)
    w1s, w1e = _clock(W1_BUCKET)
    b1 = _row(burst, W1_BUCKET)
    n_burst = int(b1["n"])
    open_min = _hm(_open_hhmm())
    first_n = int(GC.NO_TRADE_AFTER_OPEN_MIN)
    bq = s["burst_quarter_k"]
    first_pct = _pct(_slot_sum(bq, open_min, open_min + first_n), n_burst) if first_n % SLOT_MIN == 0 else None
    w2s, w2e = _hm(W2_HOURS[0]), _hm(W2_HOURS[-1]) + 60
    hourly = s["peak_hourly"]
    busiest = max(hourly, key=lambda h: hourly[h])
    ah = _row(peak, AH_BUCKET)
    ahs, ahe = _clock(AH_BUCKET)
    lo, hi = ah["ci"]
    return {
        "clock_start": _fmt(clock_start), "clock_end": _fmt(clock_end),
        "w1_start": _fmt(w1s), "w1_end": _fmt(w1e),
        "w1_burst_pct": b1["pct"],
        "w1_clock_pct": b1["null_pct"],
        "w1_multiple": round((b1["k"] / n_burst) / ((w1e - w1s) / clock_min), 1),
        "open": _fmt(open_min), "first_n": first_n,
        "first_end": _fmt(open_min + first_n), "first_pct": first_pct,
        "w2_start": _fmt(w2s), "w2_end": _fmt(w2e),
        "w2_burst_pct": _pct(_slot_sum(bq, w2s, w2e), n_burst),
        "busiest_hour": busiest, "busiest_end": _fmt(_hm(busiest) + 60), "busiest_pct": hourly[busiest],
        "busiest_in_w2": w2s <= _hm(busiest) < w2e,
        "ah_start": _fmt(ahs), "ah_end": _fmt(ahe), "ah_pct": ah["pct"], "ah_clock_pct": ah["null_pct"],
        "ah_lo": lo, "ah_hi": hi,
        "ah_share": "fair" if lo <= ah["null_pct"] <= hi else ("more" if lo > ah["null_pct"] else "less"),
        "burst_window_min": s["burst_window_min"],
        "n_days": s["n_days"], "symbols": s["symbols"], "first_day": s["first_day"], "last_day": s["last_day"],
        "float_max_shares": s["float_max_shares"], "min_high_gain_pct": s["min_high_gain_pct"],
    }


def _open_hhmm() -> str:
    """The regular open, from the house clock (daytrading.data.ET_RTH_OPEN) — never typed."""
    from daytrading.data import ET_RTH_OPEN
    return ET_RTH_OPEN.strftime("%H:%M")


# ── the served sentences ─────────────────────────────────────────────────────────────────────────────────────────────
def _w1_text(x: dict) -> str:
    t = ("%s %s–%s ET: %s%% of the winners' biggest %d-minute burst started in this hour — %s× its %s%% share of the "
         "%s–%s clock."
         % (W1_LABEL, x["w1_start"], x["w1_end"], x["w1_burst_pct"], x["burst_window_min"], x["w1_multiple"],
            x["w1_clock_pct"], x["clock_start"], x["clock_end"]))
    if x["first_pct"] is not None:
        t += (" %s%% started %s–%s, inside GG's first %d minutes — he takes no trades then."
              % (x["first_pct"], x["open"], x["first_end"], x["first_n"]))
    return t


def _ah_words(x: dict) -> str:
    share = {"fair": "about its fair share", "more": "more than its share", "less": "less than its share"}[x["ah_share"]]
    return ("After hours as a whole (%s–%s) holds %s%% of the day's highs on %s%% of the clock — %s."
            % (x["ah_start"], x["ah_end"], x["ah_pct"], x["ah_clock_pct"], share))


def _divergence_words() -> str:
    """The 🧨 Divergence study's after-hours read, from GC.DIVERGENCE_IS / _WINDOW (the high_si.honesty() source)."""
    from chart_maps.gajjala import divergence_tab as DVT
    is_from, is_to, n_sessions = GC.DIVERGENCE_IS_WINDOW
    ah = GC.DIVERGENCE_IS["ah"]
    return ("The 🧨 Divergence rule's after-hours entries %s in its study (%d trades, %s%% net per trade [%s, %s], "
            "%d sessions %s → %s)."
            % (ah["word"], ah["trades"], DVT._sgn(ah["mean_net"]), DVT._sgn(ah["lo"]), DVT._sgn(ah["hi"]),
               n_sessions, is_from, is_to))


def _w2_text(x: dict) -> str:
    t = "%s %s–%s ET: %s%% of the bursts started here (the close into after hours)" % (
        W2_LABEL, x["w2_start"], x["w2_end"], x["w2_burst_pct"])
    if x["busiest_in_w2"]:
        t += "; %s–%s is the busiest hour for the day's high (%s%%)" % (
            x["busiest_hour"], x["busiest_end"], x["busiest_pct"])
    return t + ". " + _ah_words(x) + " " + _divergence_words()


def _float_words(shares) -> str:
    if not isinstance(shares, (int, float)) or shares <= 0:
        return ""
    return ", float ≤ %gM shares" % (shares / 1e6)


def source_text(x: dict) -> str:
    gain = (" (%s–%s high ≥ +%d%% over the prior close)" % (x["clock_start"], x["clock_end"], x["min_high_gain_pct"])
            if isinstance(x.get("min_high_gain_pct"), int) else "")
    return ("Study %s, winner days%s: %s days / %s names%s, %s → %s. %s"
            % (_study_date(), gain, f"{x['n_days']:,}", f"{x['symbols']:,}", _float_words(x["float_max_shares"]),
               x["first_day"], x["last_day"], TAIL))


# ── the payload ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _closed_reason(now_et: datetime) -> Optional[str]:
    from market_hours import gate as MG
    return MG.closed_reason(now_et)


def _half_day_close(day: date) -> Optional[dtime]:
    """The regular close of a house-calendar half day; None on a full session."""
    from supply_demand.timeframes import HALF_DAYS
    if day.isoformat() not in HALF_DAYS:
        return None
    from catalysts.medical.reaction import rth_close_time
    return rth_close_time(day)


def fault_payload(day: str, closed: bool, reason: Optional[str]) -> dict:
    return {"kind": KIND, "date": day, "closed": closed, "closed_reason": reason, "half_day": False,
            "state": "fault", "windows": [], "note": None, "source_text": None, "fault_text": FAULT_TEXT}


def build(now: Optional[datetime] = None, path: Optional[Path] = None) -> dict:
    """The served block for `now` (default: the wall clock) — never raises."""
    n = (now or datetime.now(ET))
    n = n.astimezone(ET) if n.tzinfo else n.replace(tzinfo=ET)
    day = n.date()
    try:
        reason = _closed_reason(n)
    except Exception as exc:                                  # the gate's holiday table unreadable → not closed
        log.warning("time_windows: closed_reason failed: %s", type(exc).__name__)
        reason = None
    closed = reason is not None
    data = _load(str(path or DATA_PATH))
    if data is None:
        return fault_payload(day.isoformat(), closed, reason)
    try:
        x = numbers(data)
        windows = [
            {"key": W1_KEY, "start": x["w1_start"], "end": x["w1_end"], "label": W1_LABEL, "text": _w1_text(x)},
            {"key": W2_KEY, "start": x["w2_start"], "end": x["w2_end"], "label": W2_LABEL, "text": _w2_text(x)},
        ]
        src = source_text(x)
    except Exception as exc:                                  # malformed file → the fault shape
        log.warning("time_windows: study file malformed: %s", type(exc).__name__)
        return fault_payload(day.isoformat(), closed, reason)
    note = None
    half = _half_day_close(day)
    if half is not None:
        dropped = [w for w in windows if _hm(w["end"]) > half.hour * 60 + half.minute]
        windows = [w for w in windows if w not in dropped]
        if dropped:
            note = ("Half day — the regular session closes %s ET, so %s (measured on full sessions) %s not shown today."
                    % (half.strftime("%H:%M"), " and ".join("%s %s–%s" % (w["label"], w["start"], w["end"])
                                                            for w in dropped), "is" if len(dropped) == 1 else "are"))
            src = src + " " + note
    return {"kind": KIND, "date": day.isoformat(), "closed": closed, "closed_reason": reason,
            "half_day": half is not None, "state": "ok", "windows": windows, "note": note, "source_text": src,
            "fault_text": None}
