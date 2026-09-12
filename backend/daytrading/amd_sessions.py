"""Session AMD — the intraday half of Ajay's 2026-09-12 request.

He asked for AMD and, shown the incompatible conventions, chose **both**: the
daily swing read (`supply_demand/amd.py`) and this, the ICT session read.

SOURCE STATUS
─────────────
ICT session theory is community-taught. **No cited source, never measured
forward, and it gates nothing** — no scan reads this, no alert fires from it,
no lane trades on it. `CITED = False`. The app has already measured this
family's nearest relative: the ICT tab came back at **+0.03R over 6,004
signals versus placebo** on 2026-09-04. Drawn because he asked to see it.

A HONEST DEVIATION FROM CANONICAL ICT — READ THIS BEFORE TRUSTING THE BAND
─────────────────────────────────────────────────────────────────────────
Canonical session AMD uses the **Asian range, 19:00–00:00 ET**, as the
accumulation. **This app cannot see it.** `daytrading/data.py` caches
`ET_PREMARKET_OPEN = 04:00` through `ET_AFTERHOURS_CLOSE = 20:00` ET and tags
everything else `closed`; the overnight hours are simply not stored. Drawing a
"3am Asian range" from bars that do not exist would be an invention.

So the windows below are what the cached tape actually supports, and they are
named for what they are rather than borrowing ICT's labels wholesale:

  ACCUMULATION  04:00–08:00 ET  the early/pre-London consolidation
  MANIPULATION  08:00–09:45 ET  the judas window, spanning the 09:30 open
  DISTRIBUTION  09:45–16:00 ET  the New York move

Every boundary is a module constant so it can be re-cut without touching logic,
and `WINDOW_NOTE` is shipped in the payload so the deviation reaches the screen
instead of living only in this docstring.
"""
from __future__ import annotations

import logging
from datetime import time as dtime
from typing import Optional

log = logging.getLogger("daytrading.amd_sessions")

ACCUMULATION_WINDOW = (dtime(4, 0), dtime(8, 0))
MANIPULATION_WINDOW = (dtime(8, 0), dtime(9, 45))
DISTRIBUTION_WINDOW = (dtime(9, 45), dtime(16, 0))

# The raid must actually pierce the accumulation range; a poke smaller than
# this is the range breathing, not a stop run. CONVENTION, in percent.
MIN_PIERCE_PCT = 0.05

CITED = False
WINDOW_NOTE = ("Accumulation is the 04:00-08:00 ET consolidation, NOT the "
               "canonical 19:00-00:00 ET Asian range — the app caches only "
               "04:00-20:00 ET, so the overnight bars do not exist.")
SOURCE_NOTE = ("Session AMD — ICT-lineage convention, no cited source, never "
               "measured forward. Display only: nothing gates on it.")


def _f(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def _et(df):
    """The frame's index as ET-local timestamps, or None."""
    try:
        import pandas as pd
        idx = pd.DatetimeIndex(df.index)
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
        return idx.tz_convert("America/New_York")
    except Exception as exc:                                   # noqa: BLE001
        log.debug("amd_sessions: index not datetime-like: %s", exc)
        return None


def _slice(df, et, window):
    lo, hi = window
    mask = [(t.time() >= lo) and (t.time() < hi) for t in et]
    if not any(mask):
        return None
    return df[mask]


def session_cycle(df, *, day=None) -> Optional[dict]:
    """The AMD read for ONE session, or None when the windows are not covered.

    `day` picks a date (default: the last one in the frame). Returns
    {"date","accumulation","manipulation","distribution","phase","note"}.
    A window with no bars yields None for that phase — never a zero, and never
    a range invented from the neighbouring window.
    """
    if df is None or len(df) == 0:
        return None
    et = _et(df)
    if et is None:
        return None
    days = sorted({t.date() for t in et})
    if not days:
        return None
    target = day or days[-1]
    dmask = [t.date() == target for t in et]
    if not any(dmask):
        return None
    dd, det = df[dmask], et[dmask]

    acc_df = _slice(dd, det, ACCUMULATION_WINDOW)
    if acc_df is None or len(acc_df) == 0:
        return None
    a_hi, a_lo = _f(acc_df["high"].max()), _f(acc_df["low"].min())
    if a_hi is None or a_lo is None or a_hi <= a_lo:
        return None
    acc = {"lo": a_lo, "hi": a_hi, "bars": int(len(acc_df))}

    man = None
    man_df = _slice(dd, det, MANIPULATION_WINDOW)
    if man_df is not None and len(man_df):
        m_hi, m_lo = _f(man_df["high"].max()), _f(man_df["low"].min())
        rng = a_hi - a_lo
        floor = max(rng * (MIN_PIERCE_PCT / 100.0 * 100.0), a_hi * MIN_PIERCE_PCT / 100.0)
        below = m_lo is not None and m_lo < a_lo - floor
        above = m_hi is not None and m_hi > a_hi + floor
        # A raid needs the CLOSE back inside the range — same test as the daily
        # module and as smc.liquidity_sweeps. Closing outside is a breakout.
        last = _f(man_df["close"].iloc[-1])
        if below and not above and last is not None and last >= a_lo:
            man = {"side": "low", "price": m_lo, "close": last}
        elif above and not below and last is not None and last <= a_hi:
            man = {"side": "high", "price": m_hi, "close": last}
        elif below and above:
            man = {"side": "both", "price": m_lo if last is None or last >= a_lo else m_hi,
                   "close": last}

    dist = None
    dist_df = _slice(dd, det, DISTRIBUTION_WINDOW)
    if dist_df is not None and len(dist_df):
        d_hi, d_lo = _f(dist_df["high"].max()), _f(dist_df["low"].min())
        close = _f(dist_df["close"].iloc[-1])
        dist = {"hi": d_hi, "lo": d_lo, "close": close,
                # direction is only claimed when the raid was one-sided; a
                # two-sided window has no thesis and must not pretend to one
                "direction": ("up" if man and man["side"] == "low" else
                              "down" if man and man["side"] == "high" else None)}

    phase = "distribution" if dist else ("manipulation" if man else "accumulation")
    return {"date": str(target), "accumulation": acc, "manipulation": man,
            "distribution": dist, "phase": phase, "note": WINDOW_NOTE}


def chart_overlay(df, *, day=None) -> dict:
    """{"bands","lines","phase","note"} for the intraday chart. Same `amd`
    kind/tone prefix as the daily module so ONE checkbox governs both."""
    c = session_cycle(df, day=day)
    if not c:
        return {"bands": [], "lines": [], "phase": None, "note": WINDOW_NOTE}
    acc = c["accumulation"]
    bands = [{"kind": "amd_accumulation", "lo": acc["lo"], "hi": acc["hi"],
              "label": "A — 04:00-08:00 ET range"}]
    lines = []
    if c["manipulation"]:
        m = c["manipulation"]
        lines.append({"price": m["price"], "tone": "amd",
                      "label": "AMD M — judas %.2f" % m["price"]})
    if c["distribution"] and c["distribution"].get("direction"):
        d = c["distribution"]
        lvl = d["hi"] if d["direction"] == "up" else d["lo"]
        if lvl is not None:
            lines.append({"price": lvl, "tone": "amd",
                          "label": "AMD D — NY %.2f" % lvl})
    return {"bands": bands, "lines": lines, "phase": c["phase"],
            "note": c["note"], "direction": (c["distribution"] or {}).get("direction")}
