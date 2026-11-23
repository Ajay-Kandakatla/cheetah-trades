"""📈 Gajjala's Watch — VWAP on the 1 / 5 / 15-minute charts (2026-11-23, spec vwapzones rev 2 §3.2, be-watch).

Ajay, verbatim (2026-11-23): "can you add vwap and supply demand zone in the daily time frame on the watch list please" ·
"Add vwap and supply demand too". He was told GG does not use VWAP (S9 24:47) and asked for it anyway.

THE engine only: `daytrading.indicators.vwap_session` (cumulative Σ(typical × volume) / Σ volume, reset per ET date,
NaN while Σ volume = 0). This wrapper holds NO formula — it only CHOOSES THE ROWS the engine sees:
  * today's raw 1-minute rows only (the `bars.session_volume` ET-date expression — yesterday never reaches the engine);
  * the sessions named by ONE constant, `C.VWAP_SESSIONS`, which must be one of `SESSION_SETS` (HIS CALL #1, BLOCKING):
    ("rth",) = the engine's own default argument; anything else → VWAP off + ONE warning, never a raise;
  * [C2] a row tagged "rth" whose bar START is at or after the session's REGULAR close (13:00 on a half day —
    `alerts._closes`) counts as after-hours: the house session tag has no half-day clock, the cut lives here, on the
    MINUTE series, so the 1m / 5m / 15m values and the card view inherit it.
A frame's value at a bar = the VWAP after the last 1-minute bar inside its bucket (`frame_values`). The line ends at the
last closed bar — no live-tick VWAP. Display only: nothing gates, sorts or rings on it. UNMEASURED.
"""
from __future__ import annotations

import logging
import math
from typing import Optional

import pandas as pd

from daytrading.data import ET_PREMARKET_OPEN, ET_RTH_OPEN

from . import constants as C

log = logging.getLogger("chart_maps.gajjala_watch.vwap")

SESSION_SETS = (("rth",), ("premarket", "rth"), ("premarket", "rth", "afterhours"))   # the ONLY values C.VWAP_SESSIONS may take
_TAG = "vwap"                                            # the one tag every chosen row carries into the engine
_AH = "afterhours"                                       # = daytrading.data's after-hours session word
_RTH = "rth"

# ── words (every number a {} field, filled from a constant BY NAME at call time) ─────────────────────────────────────
OPEN_OF = {"premarket": ET_PREMARKET_OPEN, "rth": ET_RTH_OPEN}        # daytrading.data — the first counted session's open
SPAN_WORDS = {SESSION_SETS[0]: "the regular session (premarket not counted)",
              SESSION_SETS[1]: "premarket and the regular session",
              SESSION_SETS[2]: "the whole extended session, premarket and after-hours included"}
STOP_WORDS = {False: "stops at the regular close", True: "runs through after-hours"}     # key = "afterhours" counted
LEGEND_TEXT = "VWAP (from {open} ET)"
RULES_TEXT = ("📈 VWAP on {label}: the volume-weighted average price of {span} from {open} ET, built from closed {frame} "
              "bars (typical price × volume, the house VWAP engine). It restarts every session, {stop}, and its last "
              "point is the last closed bar — the live candle does not move it. Display only: nothing gates, sorts or "
              "rings on it. UNMEASURED.")

_WARNED: set = set()                                     # repr of each junk C.VWAP_SESSIONS already warned about


def sessions() -> Optional[tuple]:
    """tuple(C.VWAP_SESSIONS) when it is one of SESSION_SETS; anything else (a str, an empty tuple, an unknown session,
    a non-sequence) → None + ONE warning per junk value (VWAP off — never a raise). Read at CALL time."""
    v = getattr(C, "VWAP_SESSIONS", None)
    t = tuple(v) if isinstance(v, (tuple, list)) else None
    if t is not None and t in SESSION_SETS:
        return t
    key = repr(v)
    if key not in _WARNED:
        _WARNED.add(key)
        log.warning("gajjala watch VWAP: C.VWAP_SESSIONS=%s is not one of %s — VWAP off", key, SESSION_SETS)
    return None


def _utc_naive(ts) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    return t.tz_convert("UTC").tz_localize(None) if t.tzinfo is not None else t


def minute_vwap(raw, session_iso: str, *, sessions=SESSION_SETS[0], rth_close=None) -> Optional[pd.Series]:
    """THE engine over today's chosen 1-minute rows, reindexed to today's rows (NaN elsewhere). `raw` = the minute
    loader's frame (bar START, naive UTC, a `session` column). `rth_close` = the session's regular close as a naive-UTC
    Timestamp (an aware one is converted); None = no cut. None when raw is None / empty, lacks `session` or `volume`,
    has no row of `session_iso`, or no value is finite."""
    if raw is None or len(raw) == 0 or "session" not in raw.columns or "volume" not in raw.columns:
        return None
    want = tuple(sessions) if isinstance(sessions, (tuple, list)) else ()
    idx = raw.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
        raw = raw.set_axis(idx)
    days = idx.tz_localize("UTC").tz_convert("America/New_York").strftime("%Y-%m-%d")
    today = raw[days == str(session_iso)[:10]]
    if today.empty:
        return None
    tag = today["session"].astype(str).to_numpy(copy=True)
    if rth_close is not None:
        cut = _utc_naive(rth_close)
        tag[(tag == _RTH) & (today.index >= cut)] = _AH
    keep = pd.Series(tag, index=today.index).isin(want).to_numpy()
    rows = today[keep]
    if rows.empty:
        return None
    from daytrading.indicators import vwap_session
    vw = vwap_session(rows.assign(session=_TAG), session=_TAG)
    out = pd.to_numeric(vw, errors="coerce").reindex(today.index)
    if not any(math.isfinite(float(x)) for x in out.to_numpy() if x == x):
        return None
    return out


def frame_values(vw, labels, rule: str, *, dp: int = C.VWAP_DP) -> list:
    """For each frame label L (a bar's CLOSE stamp, naive UTC): the minute VWAP after the last finite 1-minute row of
    the bucket [L − rule, L) — the `bars._minutes_by_bucket` bucket label — rounded to `dp`; None where there is none.
    Never NaN."""
    labels = list(labels)
    if vw is None or not len(labels):
        return [None] * len(labels)
    s = pd.to_numeric(vw, errors="coerce").dropna()
    s = s[[math.isfinite(float(x)) for x in s.to_numpy()]] if len(s) else s
    if s.empty:
        return [None] * len(labels)
    key = s.index.floor(rule) + pd.Timedelta(rule)
    last = s.groupby(key).last()
    by = dict(zip(last.index, last.to_numpy()))
    out = []
    for lab in labels:
        v = by.get(pd.Timestamp(lab))
        out.append(round(float(v), dp) if v is not None and math.isfinite(float(v)) else None)
    return out


def _num(v) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _stored(stored_frame) -> Optional[list]:
    if not isinstance(stored_frame, dict):
        return None
    vw = stored_frame.get("vwap")
    vals = vw.get("values") if isinstance(vw, dict) else None
    return vals if isinstance(vals, list) else None


def curve_values(stored_frame: dict, n_bars: int) -> Optional[list]:
    """The stored `vwap.values` cleaned (anything not a finite number → None); None unless a list of exactly `n_bars`
    with at least one finite value (an old doc without the key, a ragged list, all None)."""
    vals = _stored(stored_frame)
    if vals is None or len(vals) != n_bars:
        return None
    clean = [_num(v) for v in vals]
    return clean if any(v is not None for v in clean) else None


def by_stamp(stored_frame: dict) -> dict:
    """{bar["t"]: value} of a stored frame — finite values only; {} when the values do not line up with the bars."""
    vals = _stored(stored_frame)
    bars = stored_frame.get("bars") if isinstance(stored_frame, dict) else None
    if vals is None or not isinstance(bars, list) or len(vals) != len(bars):
        return {}
    out = {}
    for b, v in zip(bars, vals):
        f = _num(v)
        if f is not None and isinstance(b, dict) and isinstance(b.get("t"), str):
            out[b["t"]] = f
    return out


def align(by: dict, bars: list) -> Optional[list]:
    """The values of `by` for `bars` (by `t`); None when no bar matches a finite value."""
    if not isinstance(by, dict) or not by or not isinstance(bars, list):
        return None
    vals = [_num(by.get(b.get("t"))) if isinstance(b, dict) else None for b in bars]
    return vals if any(v is not None for v in vals) else None


def _open_words(sets: tuple) -> str:
    """The FIRST counted session's open (daytrading.data, by name) as HH:MM — no digit typed."""
    return OPEN_OF[next(iter(sets))].strftime("%H:%M")


def legend_label() -> str:
    """The legend's VWAP label — the first counted session's open (daytrading.data, by name); "" when VWAP is off."""
    s = sessions()
    return LEGEND_TEXT.format(open=_open_words(s)) if s else ""


def rules_line() -> str:
    """ONE sentence for the legend hover, ℹ️ and the rules panel; "" when VWAP is off or C.VWAP_SESSIONS is junk."""
    if not C.VWAP_ON:
        return ""
    s = sessions()
    if s is None:
        return ""
    return RULES_TEXT.format(label=C.TAB_LABEL, span=SPAN_WORDS[s], open=_open_words(s),
                             frame=C.FRAME_WORDS[C.AXIS_FRAME], stop=STOP_WORDS[_AH in s])


__all__ = ["SESSION_SETS", "sessions", "minute_vwap", "frame_values", "curve_values", "by_stamp", "align",
           "legend_label", "rules_line"]
