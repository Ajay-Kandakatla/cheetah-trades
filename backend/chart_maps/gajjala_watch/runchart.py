"""📅 Runners on one continuous multi-session chart (2026-11-26, spec runcharts rev 2 §3.2).

Ajay 2026-11-26, verbatim: "I want you to have continous charts for previous day runners we have some examples with
traderview charts with couple of indicators can you set that up? I wanna able to horizontal scroll tp check continuity
like he does".

This module only CHOOSES DAYS and calls the house engines — it holds no second engine of anything:
  * the 1-minute bars of a day: `daytrading.data.load_intraday` (completed days from the Mongo day cache, the live day
    re-fetched) with the chart's OWN breaker from `daytrading.data.new_breaker`; provider failure vs "no bars" through
    `clear_fetch_failed` / `last_fetch_failed`; Massive's spelling through `sepa.symbols.for_massive`;
  * WHEN a cached day was fetched: `intraday_cache.cached_at`, read through the loader's own handle
    `daytrading.data._get_mongo_coll` (one projected find, never a write);
  * market days: `catalysts.medical.reaction.prev_market_day`; the current session: `chart_maps.gajjala.tab.session_for`;
  * 1m → N: `supply_demand.timeframes.resample_ohlcv`; closed bars only: `bars.closed_only`; the EMA frame:
    `bars.build_frame`; bars + curves + the 50-bar volume average: `bars.tile_payload`; half days: `alerts._closes`;
  * splits: `chart_maps.drop10_tab.fetch_splits_strict`; "did it run": `runners.ran_for`; VWAP (off by default):
    `gajjala_watch.build.name_vwap` → `vwap.frame_values`.

The EMA seeding (the same sentences are in docs/gajjala/runners_continuous_chart_2026_11_26.md):
  * 9 / 21 EMA = `orderflow.signals.ema` through `bars.build_frame` — EMA_t = α·close_t + (1 − α)·EMA_{t−1},
    α = 2/(n + 1), the first value = the first close (the thinkorswim `MovAvgExponential` formula).
  * It runs over EVERY closed bar of the frame handed in — the seed session(s) + the drawn sessions, pre-market, regular
    and after-hours — in time order. It is NOT restarted at a session, at 09:30, or at the overnight gap.
  * `RUNCHART_SEED_SESSIONS` (1) session before the first drawn one is loaded only to warm it: at 5-minute bars a full
    session is 192 bars, so the first drawn bar's 21 EMA carries (1 − 2/22)^192 ≈ 1e-8 of the seed — nil.
  * The first `period − 1` bars of the LOADED frame are a gap, never a guess (bars._masked_ema); a thin name with fewer
    bars than that before the first drawn bar starts its line late.
  * After a split cut the frame starts at the cut: the seed session may be gone and the line then starts late. When
    every earlier day was read after the split nothing is cut and the line is continuous across it.
  * The values at a bar can differ in the last decimals from the 🚩 card's (which runs over two sessions): more history.
  * A bar is drawn at its START (`chart_x`); the cards and the 👀 Watch stamp the same bar at its CLOSE. The 5-minute bar
    this chart puts at 10:00 is the card's "10:05". Same bar, same EMA value.

Locks: `_LOCK` guards the module dicts and NOTHING else — never held across a provider call, a Mongo read, a wait, a
split check or a payload build. A name's gate (`_GATES`) holds ONE read per NAME; only a second ask for the same name
waits on it (`RUNCHART_WAIT_SEC`), then answers `busy`.

The ONLY write is the minute loader's own day cache (completed days, the loader's rule). Display only — nothing here
rings, gates, sorts, adds a name or stores anything else. UNMEASURED.
"""
from __future__ import annotations

import calendar
import logging
import math
import threading
import time
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd

from chart_maps import board
from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from daytrading.data import ET_AFTERHOURS_CLOSE, ET_PREMARKET_OPEN, ET_RTH_OPEN

from . import constants as C

log = logging.getLogger("chart_maps.gajjala_watch.runchart")
ET = ZoneInfo("America/New_York")

STATUSES = ("loaded", "no_bars", "failed", "over_budget")
_NO_CUT = {"split": None, "cut_iso": None, "not_drawn": [], "adjusted": False}

# ── state (module level) — `_LOCK` guards these dicts and nothing else ──────────────────────────────────────────────
_LOCK = threading.Lock()
_GATES: dict = {}           # {SYM: threading.Lock()} — one read per NAME at a time
_DAYS: dict = {}            # {(SYM, day_iso): (session_iso, DataFrame | None, cached_at | None)} — completed days only
_TODAY: dict = {}           # {SYM: (clock(), read_at, DataFrame | None, status)} — the live day's last ANSWERED read
_SPLITS: dict = {}          # {(SYM, oldest_iso, newest_iso): list} — answered split checks only
_SPLIT_DOWN: dict = {"until": 0.0}
_BUILT: dict = {}           # {(SYM, tf): (days_key, today_clock | None, payload)}
_SEEN: dict = {}            # {SYM: clock()}
_BREAKER: Optional[dict] = None


def reset() -> None:
    """Clear every module dict and the chart's breaker (tests)."""
    global _BREAKER
    with _LOCK:
        _GATES.clear()
        _DAYS.clear()
        _TODAY.clear()
        _SPLITS.clear()
        _SPLIT_DOWN["until"] = 0.0
        _BUILT.clear()
        _SEEN.clear()
        _BREAKER = None


def _dt():
    from daytrading import data as dt_data
    return dt_data


def _label(d) -> str:
    """"Wed 11-25" — the strip's own date words (runners._dayword + runners._md)."""
    from . import runners as RN
    dd = d if isinstance(d, date) else date.fromisoformat(str(d)[:10])
    return f"{RN._dayword(dd)} {RN._md(dd)}"


def _hhmm(t) -> str:
    from . import runners as RN
    return RN._hhmm(t)


# ── 1. frame key ─────────────────────────────────────────────────────────────────────────────────────────────────
def tf_of(raw) -> str:
    """`raw` when it is a key of RUNCHART_FRAMES, else RUNCHART_DEFAULT_TF (a non-str, a Query object, "3m", "")."""
    keys = dict(C.RUNCHART_FRAMES)
    return raw if isinstance(raw, str) and raw in keys else C.RUNCHART_DEFAULT_TF


# ── 2. days ──────────────────────────────────────────────────────────────────────────────────────────────────────
def days_for(now, n_load) -> tuple:
    """(days oldest→newest, session, is_today, in_window) — the session clock, then `n_load − 1` steps back through the
    house calendar (prev_market_day): never a weekend or a holiday."""
    from catalysts.medical.reaction import prev_market_day
    from chart_maps.gajjala import tab
    session, is_today, in_window = tab.session_for(now)
    days = [session]
    for _ in range(max(0, int(n_load) - 1)):
        days.insert(0, prev_market_day(days[0]))
    return days, session, bool(is_today), bool(in_window)


# ── 3. the chart's own breaker ───────────────────────────────────────────────────────────────────────────────────
def breaker() -> dict:
    """The chart's OWN breaker (the rest.breaker() shape): built once under _LOCK with dt_data.new_breaker(). Never the
    module breaker, never the Watch's."""
    global _BREAKER
    b = _BREAKER
    if b is not None:
        return b
    with _LOCK:
        if _BREAKER is None:
            _BREAKER = _dt().new_breaker()
        return _BREAKER


# ── 4. day loads ─────────────────────────────────────────────────────────────────────────────────────────────────
def load_days(sym, days, *, force_day=None, load_day=None, budget_sec=C.RUNCHART_BUDGET_SEC,
              clock=time.monotonic) -> tuple:
    """(parts {iso: DataFrame}, status {iso: loaded | no_bars | failed | over_budget}) — NEWEST day first, so the budget
    cuts the oldest. Sequential in the calling thread. Holds no lock."""
    from sepa.symbols import for_massive
    dt_data = _dt()
    msym = for_massive(sym)
    if load_day is None:
        cb = breaker()

        def load(s, d, force=False, include_premarket=True, include_afterhours=True):
            return dt_data.load_intraday(s, d, force=force, include_premarket=include_premarket,
                                         include_afterhours=include_afterhours, cb=cb)
    else:
        load = load_day
    deadline = clock() + float(budget_sec)
    parts: dict = {}
    status: dict = {}
    for d in sorted(days, reverse=True):
        iso = d.isoformat()
        if clock() > deadline:
            status[iso] = "over_budget"
            continue
        try:
            dt_data.clear_fetch_failed()
            df = load(msym, d, force=(force_day is not None and d == force_day), include_premarket=True,
                      include_afterhours=True)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala watch runchart: day load failed: %s", type(exc).__name__)
            status[iso] = "failed"
            continue
        if df is None or len(df) == 0:
            status[iso] = "failed" if dt_data.last_fetch_failed() else "no_bars"
        else:
            parts[iso] = df
            status[iso] = "loaded"
    return parts, status


# ── 5. when a cached day was fetched ─────────────────────────────────────────────────────────────────────────────
def cached_at(sym, isos, *, coll=None) -> dict:
    """{iso: aware-UTC datetime} of WHEN each cached day was fetched — ONE projected find on the loader's own handle.
    No collection, a fault, a missing or non-datetime stamp → that day is absent. Never raises, never writes."""
    want = [str(i) for i in (isos or [])]
    if not want:
        return {}
    out: dict = {}
    try:
        from sepa.symbols import for_massive
        c = coll if coll is not None else _dt()._get_mongo_coll()
        if c is None:
            return {}
        q = {"symbol": for_massive(sym).upper(), "date": {"$in": want}}
        for doc in c.find(q, {"_id": 0, "date": 1, "cached_at": 1}):
            iso, at = (doc or {}).get("date"), (doc or {}).get("cached_at")
            if isinstance(iso, str) and iso in want and isinstance(at, datetime):
                out[iso] = at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at.astimezone(timezone.utc)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch runchart: cached_at read failed: %s", type(exc).__name__)
        return {}
    return out


# ── 6. clean ─────────────────────────────────────────────────────────────────────────────────────────────────────
def clean(parts) -> tuple:
    """(raw DataFrame | None, dropped) — concat, sort, a duplicate minute keeps the last; a row whose open/high/low/close
    is not finite or is ≤ 0 is dropped and counted (the runners.bars_of rule); a bad volume → 0.0."""
    frames = [p for p in (parts or {}).values() if p is not None and len(p)]
    if not frames:
        return None, 0
    raw = pd.concat(frames).sort_index(kind="mergesort")
    raw = raw[~raw.index.duplicated(keep="last")].copy()
    px = raw[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce").astype(float)
    ok = (px.gt(0) & px.lt(math.inf)).all(axis=1)
    dropped = int((~ok).sum())
    raw = raw[ok].copy()
    raw[["open", "high", "low", "close"]] = px[ok]
    if "volume" in raw.columns:
        vol = pd.to_numeric(raw["volume"], errors="coerce").astype(float)
        raw["volume"] = vol.where(vol.ge(0) & vol.lt(math.inf), 0.0)
    else:
        raw["volume"] = 0.0
    if raw.empty:
        return None, dropped
    return raw, dropped


# ── 7. splits ────────────────────────────────────────────────────────────────────────────────────────────────────
def _in_window(splits, oldest_iso: str, newest_iso: str) -> list:
    rows = []
    for s in splits or []:
        if not isinstance(s, dict):
            continue
        e = s.get("execution_date")
        if isinstance(e, str) and len(e) >= 10 and oldest_iso < e[:10] <= newest_iso:
            rows.append(dict(s, execution_date=e[:10]))
    return sorted(rows, key=lambda r: r["execution_date"])


def splits_in(sym, days, *, splits_fn=None, clock=time.monotonic, fetch=True) -> Optional[list]:
    """The splits executed inside (oldest, newest], date order; [] = the provider answered with none; None = not
    checked. ONE fetch_splits_strict per (SYM, oldest, newest) — answered checks only are held. A raise → None, and no
    name asks again for RUNCHART_SPLIT_RETRY_SEC. `fetch` False → the held answer or None, never a read. Holds no lock
    while it reads."""
    if not days:
        return None
    oldest, newest = days[0].isoformat(), days[-1].isoformat()
    key = (sym, oldest, newest)
    with _LOCK:
        if key in _SPLITS:
            return list(_SPLITS[key])
        if not fetch or clock() < _SPLIT_DOWN["until"]:
            return None
    if splits_fn is None:
        from chart_maps.drop10_tab import fetch_splits_strict as fn
    else:
        fn = splits_fn
    try:
        got = fn(sym, oldest)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch runchart: split check failed: %s", type(exc).__name__)
        with _LOCK:
            _SPLIT_DOWN["until"] = clock() + float(C.RUNCHART_SPLIT_RETRY_SEC)
        return None
    rows = _in_window(got, oldest, newest)
    with _LOCK:
        _SPLITS[key] = rows
    return list(rows)


# ── 8. the split cut (PURE) ──────────────────────────────────────────────────────────────────────────────────────
def split_cut(days, loaded, stamps, splits) -> dict:
    """{"split", "cut_iso", "not_drawn", "adjusted"} — PURE (no I/O, no timer, no module state). The LATEST in-window split decides; a
    day that holds bars before it is PROVEN on the new share count only when it was fetched (its stamp's ET date) after
    the split (on it too when RUNCHART_SPLIT_SAME_DAY_OK). All proven → nothing cut (adjusted). Else everything up to
    the latest unproven day is not drawn: one share count from the cut to the last bar, never a hole, never a rescale."""
    isos = [d.isoformat() for d in days]
    if not splits or not isos:
        return dict(_NO_CUT, not_drawn=[])
    rows = _in_window(splits, isos[0], isos[-1])
    if not rows:
        return dict(_NO_CUT, not_drawn=[])
    split = rows[-1]
    e = split["execution_date"]
    have = set(loaded or [])
    pre = [i for i in isos if i in have and i < e]
    if not pre:
        return dict(_NO_CUT, not_drawn=[])

    def proven(iso: str) -> bool:
        at = (stamps or {}).get(iso)
        if not isinstance(at, datetime):
            return False
        at = at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at
        d = at.astimezone(ET).date().isoformat()
        return d >= e if C.RUNCHART_SPLIT_SAME_DAY_OK else d > e

    unproven = [i for i in pre if not proven(i)]
    if not unproven:
        return {"split": split, "cut_iso": None, "not_drawn": [], "adjusted": True}
    u = unproven[-1]
    cut_iso = next(i for i in isos if i > u)
    return {"split": split, "cut_iso": cut_iso, "not_drawn": [i for i in isos if i in have and i <= u],
            "adjusted": False}


# ── 9-12. session tags, the frame, bar starts, chart x ───────────────────────────────────────────────────────────
def _starts(index, rule):
    return (index - pd.Timedelta(rule)).tz_localize("UTC").tz_convert("America/New_York")


def session_tags(starts_et) -> list:
    """Per bucket START (ET): before ET_RTH_OPEN → premarket; at/after the day's regular close (alerts._closes — 13:00
    on a half day) → afterhours; else rth."""
    closes: dict = {}
    out = []
    for ts in starts_et:
        d = ts.date()
        if d not in closes:
            closes[d] = AL._closes(d)[0]
        t = ts.time()
        out.append("premarket" if t < ET_RTH_OPEN else ("afterhours" if t >= closes[d] else "rth"))
    return out


def frame_of(raw, tf, read_at) -> Optional[B.Frame]:
    """resample_ohlcv → closed_only AS OF `read_at` (when the minutes were READ, never the asking clock) → the session
    column re-tagged per bucket start (half days included) → build_frame. None when no closed bar."""
    from supply_demand.timeframes import resample_ohlcv
    if raw is None or len(raw) == 0:
        return None
    rule = dict(C.RUNCHART_FRAMES)[tf_of(tf)]
    res = resample_ohlcv(raw, rule)
    if res is None or res.empty:
        return None
    closed = B.closed_only(res, read_at)
    if closed is None or closed.empty:
        return None
    closed = closed.copy()
    st = _starts(closed.index, rule)
    closed["session"] = session_tags(st)
    return B.build_frame(closed, st[-1].date().isoformat(), rule)


def starts_et(F, rule):
    """The ET START of each bar of F (a bar belongs to the session its bucket STARTS in — the bars.py expression)."""
    return _starts(F.df.index, rule)


def chart_x(starts) -> list:
    """The ET wall-clock START of each bar written AS IF UTC (seconds) — a UTC-drawing chart prints ET, no timezone code
    in the browser. Strictly ascending."""
    return [int(calendar.timegm(ts.timetuple())) for ts in starts]


# ── 13. payload ──────────────────────────────────────────────────────────────────────────────────────────────────
def _frames_list() -> list:
    return [{"key": k, "label": C.FRAME_WORDS.get(k, k)} for k, _r in C.RUNCHART_FRAMES]


def _frame_min(tf: str) -> int:
    return int(pd.Timedelta(dict(C.RUNCHART_FRAMES)[tf]).total_seconds() // 60)


def _title(sym: str, tf: str, labels: list) -> Optional[str]:
    if not labels:
        return None
    frame = C.FRAME_WORDS.get(tf, tf)
    if len(labels) == 1 or labels[0] == labels[-1]:
        return C.RUNCHART_TITLE_ONE.format(sym=sym, frame=frame, first=labels[0])
    return C.RUNCHART_TITLE.format(sym=sym, frame=frame, first=labels[0], last=labels[-1])


def _hint(tf: str) -> str:
    return C.RUNCHART_HINT.format(frame=C.FRAME_WORDS.get(tf, tf), n=C.RUNCHART_SESSIONS,
                                  open=_hhmm(ET_PREMARKET_OPEN), end=_hhmm(ET_AFTERHOURS_CLOSE),
                                  seed=C.RUNCHART_SEED_SESSIONS, slow=GC.EMA_SLOW, vol=board.VOL_AVG_PERIOD,
                                  memo=C.RUNCHART_MEMO_SEC)


def _et_of(ts) -> datetime:
    if isinstance(ts, datetime):
        return ts.replace(tzinfo=ET) if ts.tzinfo is None else ts.astimezone(ET)
    return datetime.now(ET)


def _vwap_curve(frames_obj, F, start: int, sessions: list, rule: str) -> Optional[dict]:
    from . import build as BLD
    from . import vwap as VW
    vals: list = []
    for s in sessions:
        labels = F.df.index[start + s["from"]:start + s["to"] + 1]
        vw = BLD.name_vwap(frames_obj, date.fromisoformat(s["date"]))
        vals.extend(VW.frame_values(vw, labels, rule, dp=C.VWAP_DP) if vw is not None else [None] * len(labels))
    if not any(v is not None and math.isfinite(v) for v in vals):
        return None
    return {"tone": C.VWAP_TONE, "label": C.VWAP_LABEL, "values": vals}


def payload(sym, entry, tf) -> dict:
    """The served chart (§3.4) — a pure function of the entry and the frame (no clock), so it is safe to hold."""
    tf = tf_of(tf)
    rule = dict(C.RUNCHART_FRAMES)[tf]
    days = list(entry["days"])
    isos = [d.isoformat() for d in days]
    status = dict(entry.get("status") or {})
    parts = dict(entry.get("parts") or {})
    cut = entry.get("cut") or _NO_CUT
    cut_iso = cut.get("cut_iso")
    if cut_iso:
        parts = {k: v for k, v in parts.items() if k >= cut_iso}
        status = {k: v for k, v in status.items() if k >= cut_iso}
    drawn = [i for i in isos[-int(C.RUNCHART_SESSIONS):] if not cut_iso or i >= cut_iso]
    ran = entry.get("ran") if isinstance(entry.get("ran"), dict) else None
    ran_date = ran.get("date") if ran else None
    read_at = entry.get("read_at")

    raw, dropped = clean(parts)
    F = frame_of(raw, tf, read_at) if raw is not None else None
    bars: list = []
    curves: list = []
    vol_avg = None
    sessions: list = []
    shade: list = []
    start = 0
    capped = False
    n_before_cap = 0
    if F is not None and len(F) and drawn:
        st = starts_et(F, rule)
        dates = [ts.date().isoformat() for ts in st]
        start = next((i for i, d in enumerate(dates) if d >= drawn[0]), len(F))
        n_before_cap = len(set(dates[start:]))
        while len(F) - start > int(C.RUNCHART_MAX_BARS) and len(set(dates[start:])) > 1:
            first = dates[start]
            start = next(i for i in range(start, len(F)) if dates[i] != first)
            capped = True
        if start < len(F):
            F.today = range(start, len(F))
            frames_obj = B.Frames(sym, isos[-1], {tf: F}, raw, primary=tf, slow=tf)
            tp = B.tile_payload(frames_obj, tf)
            bars = tp["bars"]
            if len(bars) != len(F) - start:
                raise ValueError("bars do not line up with the frame")
            for b, x in zip(bars, chart_x(st[start:])):
                b["x"] = x
            curves = list(tp["curves"])
            vol_avg = tp["vol_avg"]
            for i, d in enumerate(dates[start:]):
                if sessions and sessions[-1]["date"] == d:
                    sessions[-1]["to"] = i
                else:
                    sessions.append({"date": d, "label": _label(d), "from": i, "to": i,
                                     "half_day": d in AL.HALF_DAYS, "ran": ran_date == d})
            for i, b in enumerate(bars):
                s = b.get("s")
                if s is None:
                    continue
                if (shade and shade[-1]["kind"] == s and shade[-1]["to"] == i - 1
                        and dates[start + i] == dates[start + i - 1]):
                    shade[-1]["to"] = i
                else:
                    shade.append({"from": i, "to": i, "kind": s})
            if C.RUNCHART_VWAP_ON:
                vc = _vwap_curve(frames_obj, F, start, sessions, rule)
                if vc is not None:
                    curves.append(vc)

    seed_isos = [i for i in isos if drawn and i < drawn[0] and (not cut_iso or i >= cut_iso)]
    failed = [i for i in isos if status.get(i) == "failed"]
    budget = [i for i in isos if status.get(i) == "over_budget"]
    notes: list = []
    sp = cut.get("split") if isinstance(cut.get("split"), dict) else None
    if cut_iso and sp:
        notes.append({"kind": "split", "text": C.RUNCHART_SPLIT_TEXT.format(
            to=float(sp.get("split_to") or 1.0), frm=float(sp.get("split_from") or 1.0),
            day=_label(sp["execution_date"]), days=", ".join(_label(i) for i in cut.get("not_drawn") or []))})
    if cut.get("adjusted") and sp:
        notes.append({"kind": "split_adjusted", "text": C.RUNCHART_SPLIT_ADJUSTED_TEXT.format(
            to=float(sp.get("split_to") or 1.0), frm=float(sp.get("split_from") or 1.0),
            day=_label(sp["execution_date"]))})
    if not entry.get("split_checked") and bars:
        notes.append({"kind": "split_unchecked", "text": C.RUNCHART_SPLIT_UNCHECKED_TEXT})
    if failed:
        notes.append({"kind": "failed", "text": C.RUNCHART_FAILED_TEXT.format(days=", ".join(_label(i) for i in failed))})
    if budget:
        notes.append({"kind": "budget", "text": C.RUNCHART_BUDGET_TEXT.format(days=", ".join(_label(i) for i in budget))})
    if capped:
        notes.append({"kind": "bar_cap", "text": C.RUNCHART_BAR_CAP_TEXT.format(
            frame=C.FRAME_WORDS.get(tf, tf), k=len(sessions), n=n_before_cap, cap=C.RUNCHART_MAX_BARS)})

    live = bool(entry.get("is_today") and entry.get("in_window"))
    window_labels = [_label(i) for i in drawn] or [_label(i) for i in isos[-1:]]
    if bars:
        state, text = "ok", None
        last_t = bars[-1]["t"]
        as_of_bar_t = last_t
        as_of_text = C.RUNCHART_ASOF_TEXT.format(bar=f"{_label(last_t[:10])} {last_t[11:16]}",
                                                 at=_et_of(read_at).strftime("%H:%M"))
        title = _title(sym, tf, [s["label"] for s in sessions])
    else:
        state = "error" if failed else "empty"
        text = (C.RUNCHART_ERROR_TEXT.format(sym=sym) if failed else
                C.RUNCHART_EMPTY_TEXT.format(sym=sym, n=C.RUNCHART_SESSIONS, first=window_labels[0],
                                             last=window_labels[-1]))
        as_of_bar_t = as_of_text = None
        title = _title(sym, tf, window_labels)
        bars, curves, vol_avg, sessions, shade, start = [], [], None, [], [], 0
    return {
        "state": state, "symbol": sym, "tf": tf, "frame_min": _frame_min(tf), "frames": _frames_list(),
        "title": title, "text": text, "notes": notes, "as_of_text": as_of_text, "as_of_bar_t": as_of_bar_t,
        "live": live, "refresh_sec": C.RUNCHART_MEMO_SEC if live else 0, "hint": _hint(tf),
        "words": dict(C.RUNCHART_WORDS),
        "ran": ({"date": ran.get("date"), "text": ran.get("text"), "title": ran.get("title")} if ran else None),
        "sessions": sessions, "bars": bars, "curves": curves, "vol_avg": vol_avg, "shade": shade,
        "view": {"sessions": C.RUNCHART_VIEW_SESSIONS, "sessions_phone": C.RUNCHART_VIEW_SESSIONS_PHONE,
                 "right_gap_bars": C.RUNCHART_RIGHT_GAP_BARS},
        "seed": {"sessions": sum(1 for i in seed_isos if i in parts), "bars": start},
        "dropped": dropped,
    }


# ── 14. busy ─────────────────────────────────────────────────────────────────────────────────────────────────────
def busy(sym) -> dict:
    return {"state": "busy", "symbol": sym,
            "text": C.RUNCHART_BUSY_TEXT.format(sym=sym, sec=C.RUNCHART_BUSY_RETRY_SEC),
            "retry_sec": C.RUNCHART_BUSY_RETRY_SEC}


# ── 15. build ────────────────────────────────────────────────────────────────────────────────────────────────────
def _gate(sym: str) -> threading.Lock:
    with _LOCK:
        g = _GATES.get(sym)
        if g is None:
            g = _GATES[sym] = threading.Lock()
        return g


def _young(stamp, clock) -> bool:
    return stamp is not None and clock() - stamp < C.RUNCHART_MEMO_SEC - C.RUNCHART_MEMO_SLACK_SEC


def _built_hit(sym: str, tf: str, days_key: tuple, clock) -> Optional[dict]:
    with _LOCK:
        row = _BUILT.get((sym, tf))
    if row is None or row[0] != days_key:
        return None
    return row[2] if (row[1] is None or _young(row[1], clock)) else None


def _evict_locked() -> None:
    """Past RUNCHART_MEMO_MAX names the least recently opened name's rows go (and its gate when not held). Caller holds
    _LOCK."""
    while len(_SEEN) > int(C.RUNCHART_MEMO_MAX):
        old = min(_SEEN, key=_SEEN.get)
        _SEEN.pop(old, None)
        for k in [k for k in _DAYS if k[0] == old]:
            _DAYS.pop(k, None)
        _TODAY.pop(old, None)
        for k in [k for k in _BUILT if k[0] == old]:
            _BUILT.pop(k, None)
        for k in [k for k in _SPLITS if k[0] == old]:
            _SPLITS.pop(k, None)
        g = _GATES.get(old)
        if g is not None and not g.locked():
            _GATES.pop(old, None)


def _ran(sym: str, now, ran_fn) -> Optional[dict]:
    try:
        from . import colls as CO
        from . import runners as RN
        fn = ran_fn or RN.ran_for
        got = fn([sym], RN.runner_day(now)[0])
        r = got.get(CO.fold(sym)) if isinstance(got, dict) else None
        if isinstance(r, dict) and r.get("counts") is True:
            return {"date": r.get("date"), "text": r.get("text"), "title": r.get("title")}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch runchart: ran read failed: %s", type(exc).__name__)
    return None


def _fault(sym, tf, days) -> dict:
    out = {"state": "error", "symbol": sym, "text": C.RUNCHART_FAULT_TEXT.format(sym=sym)}
    if tf:
        out.update(tf=tf, frame_min=_frame_min(tf), frames=_frames_list(),
                   title=_title(sym, tf, [_label(d) for d in (days or [])[-int(C.RUNCHART_SESSIONS):]]))
    return out


def build(symbol, now=None, *, tf=None, load_day=None, splits_fn=None, cached_at_fn=None, ran_fn=None, clock=None,
          wait_sec=None) -> dict:
    """The owner's continuous chart of one name (B1-B7). Never raises: a fault → state `error` with
    RUNCHART_FAULT_TEXT; the name's gate is released in a `finally`."""
    clock = clock or time.monotonic
    if not C.RUNCHART_ON:                                                                   # B1
        return {"state": "off"}
    from . import store as ST
    sym = ST.normalize(symbol)                                                              # B2
    if sym is None:
        return {"state": "bad_symbol", "symbol": None, "text": C.RUNCHART_BAD_SYMBOL_TEXT}
    gate, held_gate, frame, days = None, False, None, None
    try:
        now = _et_of(now) if now is not None else datetime.now(ET)
        frame = tf_of(tf)                                                                   # B3
        days, session, is_today, in_window = days_for(now, int(C.RUNCHART_SESSIONS) + int(C.RUNCHART_SEED_SESSIONS))
        isos = [d.isoformat() for d in days]
        days_key = (tuple(isos), is_today, in_window)       # the clock state too: a live payload never serves a closed ask
        session_iso = session.isoformat()
        hit = _built_hit(sym, frame, days_key, clock)                                       # B4
        if hit is not None:
            return hit
        gate = _gate(sym)                                                                   # B5
        held_gate = gate.acquire(timeout=float(wait_sec or C.RUNCHART_WAIT_SEC))
        if not held_gate:
            return busy(sym)
        hit = _built_hit(sym, frame, days_key, clock)                                       # B6.a
        if hit is not None:
            return hit
        live_iso = session_iso if is_today else None
        with _LOCK:                                                                         # B6.b
            for k in [k for k, v in _DAYS.items() if v[0] != session_iso]:
                _DAYS.pop(k, None)
            held = {i: _DAYS[(sym, i)] for i in isos if (sym, i) in _DAYS and i != live_iso}
            today_row = _TODAY.get(sym) if is_today else None
        if today_row is not None and not (_young(today_row[0], clock)
                                          and _et_of(today_row[1]).date() == session):
            today_row = None
        need = [d for d in days if d.isoformat() not in held
                and not (d.isoformat() == live_iso and today_row is not None)]
        parts: dict = {}
        status: dict = {}
        stamps: dict = {}
        for i, (_s, df, at) in held.items():
            status[i] = "loaded" if df is not None else "no_bars"
            if df is not None:
                parts[i] = df
            if at is not None:
                stamps[i] = at
        if today_row is not None:
            status[live_iso] = today_row[3]
            if today_row[2] is not None:
                parts[live_iso] = today_row[2]
        got_parts, got_status, got_stamps = {}, {}, {}
        if need:                                                                            # B6.c
            got_parts, got_status = load_days(sym, need, force_day=session if is_today else None,
                                              load_day=load_day, clock=clock)
            done = [i for i, s in got_status.items() if s == "loaded" and i != live_iso]
            got_stamps = (cached_at_fn or cached_at)(sym, done) if done else {}
            got_stamps = got_stamps if isinstance(got_stamps, dict) else {}
        with _LOCK:                                                                         # B6.d
            for i, s in got_status.items():
                if s not in ("loaded", "no_bars"):
                    continue
                df = got_parts.get(i)
                if i == live_iso:
                    today_row = (clock(), now, df, s)
                    _TODAY[sym] = today_row
                else:
                    _DAYS[(sym, i)] = (session_iso, df, got_stamps.get(i))
            _SEEN[sym] = clock()
            _evict_locked()
        parts.update(got_parts)
        status.update(got_status)
        stamps.update({i: at for i, at in got_stamps.items() if isinstance(at, datetime)})
        has_bars = [i for i in isos if i in parts]
        if not has_bars:                                                                    # B6.e
            splits = None
        else:                                       # newest day failed → the held answer only, never the 15 s read
            splits = splits_in(sym, days, splits_fn=splits_fn, clock=clock,
                               fetch=status.get(isos[-1]) != "failed")
        cut = split_cut(days, has_bars, stamps, splits)                                     # B6.f
        today_clock = today_row[0] if (today_row is not None and live_iso is not None) else None
        read_at = today_row[1] if today_clock is not None else now
        entry = {"parts": parts, "status": status, "days": days, "session": session, "is_today": is_today,  # B6.h
                 "in_window": in_window, "read_at": read_at, "cut": cut, "split_checked": splits is not None,
                 "ran": _ran(sym, now, ran_fn)}                                             # B6.g
        p = payload(sym, entry, frame)                                                      # B6.i
        # B6.j — an unchecked split (`split_checked` False) is never held either: the next open past
        # RUNCHART_SPLIT_RETRY_SEC asks again and draws the cut (2026-11-26 refix).
        if splits is not None and not any(s in ("failed", "over_budget") for s in status.values()):
            with _LOCK:
                _BUILT.pop((sym, frame), None)
                _BUILT[(sym, frame)] = (days_key, today_clock, p)
                while len(_BUILT) > int(C.RUNCHART_BUILT_MAX):
                    _BUILT.pop(next(iter(_BUILT)), None)
        return p                                                                            # B7
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala watch runchart: build failed: %s", type(exc).__name__)
        return _fault(sym, frame, days)
    finally:
        if held_gate and gate is not None:
            gate.release()
