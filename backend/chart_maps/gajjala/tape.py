"""🕰️ The Promo Circuit tape per Gajjala A+ entry (2026-10-16 night, DECISIONS11 D1–D3 + BUILD_SPEC11 §3.3 / §3.4 +
AMENDMENTS11 F8 / F9 / F19).

THE ASK (Ajay 2026-10-16 ~22:00 ET, verbatim):
  "We have a Promo Circuit tab in Catalyst tab. Can you use the graph component from  that to show what happened to
  Entries alert of Gajjala with all the 100% criteria satisfier. One you alert it from the alert system you built please"

UNMEASURED — a picture of what the alert did, graded by the ledger's own math; never a study. The 2026-10-14 study of
the five setups read NULL (docs/gajjala/study_2026_10_13.md) and nothing here changes that.

ONE A+ row of the 🏁 Track record -> its 5-minute tape (the Promo Circuit look: closes, pre / post market shading) plus
the lines that tape lacked: the trigger / stop / +1R levels, the alert and fill rules, the fill and exit dots. EVERY
word the owner reads on the tape is typed HERE (ENTRY_TAPE_WORDS and the view words); every grade and cell text is the
ledger's own (ledger.grade / ledger._cell / ledger.filled_grade) — the frontend composes none.

NEVER WRITES a gajjala collection. Cost rules:
- the FULL tape (the 📈 click): completed days through the house 1-minute loader (daytrading.data.load_intraday, NO
  force — a cached day reads intraday_cache, a miss fetches once and the loader caches it; BUILD_SPEC11 C1, HIS CALL
  Q10), one load at a time per (symbol, day) under a lock; today through ledger.today_bars with the ledger's own today
  loader — the ONE memo the 🏁 GET's today_read fills, never a second fetch for a name that read already loaded.
- the row's MINI tape (lite) NEVER fetches (AMENDMENTS11 F8): completed days from intraday_cache only, today from the
  ledger memo only.
- each payload is memoised per (id, full | lite) for LEDGER_TAPE_MEMO_SEC; a full build refreshes the lite entry too.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from daytrading import data as dt_data
from sepa.symbols import for_massive
from supply_demand.timeframes import resample_ohlcv

from . import constants as GC
from . import ledger as LG

log = logging.getLogger("chart_maps.gajjala.tape")

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
ONE_MIN = timedelta(minutes=1)

# ── served words — the ONLY place any tape word is typed (BUILD_SPEC11 §3.3, AMENDMENTS11 F9) ─────────────────────
ENTRY_TAPE_WORDS = {
    "trigger": "trigger {px}",
    "stop": "stop {px}",
    "target": "+{m}R {px}",
    "alert": "alert {hhmm} ET",
    "fill": "fill {hhmm}",
    "fill_dot": "fill {px} at {hhmm}",
    "exit_target": "+{m}R {hhmm}",
    "exit_stop": "stop {hhmm}",
    "axis_hi": "hi {px}",
    "axis_lo": "lo {px}",
    "axis_end": "{stamp} · {px}",
    "tf": "{n}min · pre/post market",
    "legend": "{n}-minute closes · shaded = pre / post market · solid line = the alert · dashed = the fill · levels = trigger / stop / +{m}R",
    "aria": "{sym} {n}-minute tape around the A+ entry",
    "read": "{same_head}: {same}; {next_head}: {next}",
    "open_hint": "📈 click for the full tape",
    "no_bars": "No {n}-minute bars on file for {sym} on {date} yet.",
    "today_failed": "Today's tape could not be read on this open — the next re-read tries again.",
    "lite_today": "Today's bars are not in the mini yet — 📈 loads the full tape.",   # AMENDMENTS11 A6: the mini never loads (F8)
    "fault": "The tape could not be built this time — the next re-read tries again.",
    "not_found": "No A+ entry with that id on the 🏁 Track record.",
    "split": "A split is on file after this alert — the bars are adjusted, the alert's levels are as printed; the levels are not drawn.",
}
VIEW_PARAM = "view"
VIEWS = (("all", "📋 all alerts"), ("timeline", "🕰️ entries timeline"))      # DECISIONS11 D3 (served labels)
VIEW_DEFAULT = VIEWS[0][0]
TIMELINE_EMPTY_TEXT = "No A+ entry in this span — the 🧠 alerts are under 📋 all alerts."
TAPE_HEAD = "Tape"
TAPE_TOGGLE = "📈"
PAYLOAD_KEYS = ("id", "ticker", "tf", "lite", "bars", "n_bars", "hlines", "rules", "dots", "axis", "legend", "read",
                "title", "tone", "note", "aria", "as_of")
LITE_KEYS = ("id", "ticker", "tf", "lite", "bars", "n_bars", "rules", "title", "tone", "note", "aria", "as_of")
_NO_MEMO_NOTES = ("fault", "today_failed", "lite_today")   # a failed / memo-less read is never memoised: the next re-read tries again

_MEMO: dict = {}                  # {(id, "full" | "lite"): (clock(), payload)}
_LOCK = threading.Lock()
_DAY_LOCKS: dict = {}             # {(SYM, day_iso): threading.Lock} — one completed-day load at a time (F8)


# ── the view block the 🏁 GET serves (ledger.served_block reads it) ────────────────────────────────────────────────
def views_block() -> dict:
    """DECISIONS11 D3 — the served view toggle: the param, the default, the labels, the kinds the timeline lists and
    its words. The frontend picks nothing itself."""
    return {"param": VIEW_PARAM, "default": VIEW_DEFAULT,
            "items": [{"key": k, "label": lab} for k, lab in VIEWS], "kinds": [LG.KINDS[1]],
            "empty_text": TIMELINE_EMPTY_TEXT, "tape_head": TAPE_HEAD, "tape_toggle": TAPE_TOGGLE,
            "tape_toggle_title": f"the full tape — the alert, the fill, the trigger / stop / +{LG._m()}R"}


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _w(key: str, **kw) -> str:
    return ENTRY_TAPE_WORDS[key].format(**kw)


def _stamp(ms: int) -> str:
    """PromoTagTape.etStamp's output in Python, ET — "Sep 2 · 9:00a ET"."""
    et = datetime.fromtimestamp(int(ms) / 1000, tz=UTC).astimezone(ET)
    return f"{et:%b} {et.day} · {et.hour % 12 or 12}:{et:%M}{'a' if et.hour < 12 else 'p'} ET"


def parse_id(_id) -> Optional[tuple]:
    """A ledger A+ id "{YYYY-MM-DD}|{SYM}|{setup}|aplus" -> (date, SYM, setup); a 🧠 id, junk or a non-str -> None."""
    if not isinstance(_id, str):
        return None
    parts = _id.split("|")
    if len(parts) != 4:
        return None
    d_s, sym, setup, kind = parts
    if kind != LG.KINDS[1] or len(d_s) != 10 or not sym or sym != sym.strip().upper() or not setup.strip():
        return None
    try:
        d = date.fromisoformat(d_s)
    except ValueError:
        return None
    return d, sym, setup


def _naive_utc_index(df):
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    out = df.copy()
    out.index = idx
    return out


def _frame_of(bars) -> Optional[pd.DataFrame]:
    """[(t_utc aware, o, h, l, c)] (the ledger's tuples) -> the loader's frame shape (naive-UTC minute starts)."""
    if not bars:
        return None
    idx = pd.DatetimeIndex([LG._aware(b[0]).replace(tzinfo=None) for b in bars])
    return pd.DataFrame({"open": [float(b[1]) for b in bars], "high": [float(b[2]) for b in bars],
                         "low": [float(b[3]) for b in bars], "close": [float(b[4]) for b in bars]}, index=idx)


def _as_frame(res) -> Optional[pd.DataFrame]:
    """A loader answer (DataFrame | [(t, o, h, l, c)] | (either, provider_failed) | None) -> a frame or None."""
    if isinstance(res, tuple):
        res = res[0]
    if res is None:
        return None
    if isinstance(res, list):
        return _frame_of(res)
    if getattr(res, "empty", True):
        return None
    return _naive_utc_index(res)


def bars5(df) -> list:
    """THE 5-minute tape bars — one engine for the live tape and the replay's stored bars5: a 1-minute frame in the
    loader's shape (naive-UTC minute STARTS; open/high/low/close[, volume][, session]) -> resample_ohlcv (left-closed,
    right-labelled) at LEDGER_TAPE_TF_MIN -> [{"t": epoch ms of the right label, "o", "h", "l", "c" (round 4), "v":
    float | None, "s": session}] ascending; `session` from daytrading.data._classify_session when absent; NaN volume ->
    None; [] for None / empty."""
    if df is None or getattr(df, "empty", True):
        return []
    try:
        f = _naive_utc_index(df).sort_index()
    except Exception:                                           # noqa: BLE001
        return []
    f = f[~f.index.duplicated(keep="last")]
    cols = [c for c in ("open", "high", "low", "close", "volume", "session") if c in f.columns]
    f = f[cols].copy()
    if "session" not in f.columns or f["session"].isna().any():
        tags = [dt_data._classify_session(ts) for ts in f.index]
        f["session"] = tags if "session" not in f.columns else f["session"].where(f["session"].notna(), tags)
    rule = f"{GC.LEDGER_TAPE_TF_MIN}min"
    out5 = resample_ohlcv(f, rule)
    if out5 is None or out5.empty:
        return []
    n_vol = None                                                # the printed-volume minutes per bucket, same engine
    if "volume" in f.columns:
        n_vol = resample_ohlcv(f[["open", "high", "low", "close"]].assign(volume=f["volume"].notna().astype(float)),
                               rule)["volume"]
    out = []
    for ts, r in zip(out5.index, out5.itertuples(index=False)):
        v = getattr(r, "volume", None)
        v = None if v is None or v != v else float(v)
        if v is not None and n_vol is not None and not float(n_vol.get(ts, 0.0) or 0.0) > 0:
            v = None                                            # a bucket with no printed volume is None, never 0.0
        t = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        out.append({"t": int(t.timestamp() * 1000), "o": round(float(r.open), 4), "h": round(float(r.high), 4),
                    "l": round(float(r.low), 4), "c": round(float(r.close), 4), "v": v,
                    "s": getattr(r, "session", None) or dt_data._classify_session(ts)})
    return out


# ── the loaders (C1 / F8) ──────────────────────────────────────────────────────────────────────────────────────────
def _completed_day(sym: str, day: date):
    """The FULL tape's completed day: the house loader, NO force (a cached day never fetches; a miss fetches once and
    the loader caches it — BUILD_SPEC11 C1). A provider failure (None with the loader's failed flag, as
    ledger._default_load_day reads it) RAISES, so the tape serves the fault note instead of a silently missing day."""
    dt_data.clear_fetch_failed()
    df = dt_data.load_intraday(for_massive(sym), day, include_premarket=True, include_afterhours=True)
    if df is None and dt_data.last_fetch_failed():
        raise RuntimeError("the minute provider failed")
    return df


def _cached_day(sym: str, day: date):
    """The MINI tape's completed day: intraday_cache ONLY — a miss is that day absent, never a fetch (F8)."""
    df = dt_data._mongo_get_day(for_massive(sym), day)
    if df is None or getattr(df, "empty", True):
        return None
    return dt_data._filter_sessions(df, True, True)


def _day_lock(sym: str, day: date) -> threading.Lock:
    with _LOCK:
        return _DAY_LOCKS.setdefault((sym, day.isoformat()), threading.Lock())


def _market_days(d: date, last: date) -> list:
    out = [d]
    while out[-1] < last and len(out) < int(GC.LEDGER_TAPE_SESSIONS):
        out.append(LG._next_market_day(out[-1]))
    return out


# ── the payload ───────────────────────────────────────────────────────────────────────────────────────────────────
def fault_payload(_id, *, lite: bool = False, now: Optional[datetime] = None, ticker: Optional[str] = None) -> dict:
    """AMENDMENTS11 F19 — the tape that could not be built: every PAYLOAD_KEY present, no bars, the fault note."""
    n = GC.LEDGER_TAPE_TF_MIN
    return {"id": _id if isinstance(_id, str) else "", "ticker": ticker, "tf": _w("tf", n=n), "lite": bool(lite),
            "bars": [], "n_bars": 0, "hlines": [], "rules": [], "dots": [], "axis": None, "legend": None,
            "read": None, "title": None, "tone": None, "note": ENTRY_TAPE_WORDS["fault"],
            "aria": _w("aria", sym=ticker, n=n) if ticker else None, "as_of": LG._aware(now).isoformat()}


def lite_of(full: dict) -> dict:
    """LITE_KEYS; bars = the Promo engine's lite stride (t/c/s, every LITE_STRIDE-th + the last — the constant read at
    CALL time); rules = the alert rule only."""
    from catalysts import promo_tape as PROMO
    out = {k: full.get(k) for k in LITE_KEYS}
    out["bars"] = PROMO.lite_payload({"bars": full.get("bars") or []}, stride=PROMO.LITE_STRIDE)["bars"]
    out["rules"] = [r for r in full.get("rules") or [] if r.get("key") == "alert"]
    out["lite"] = True
    return out


def _cell_text(c: dict) -> str:
    return c["text"] + (" · " + c["sub_text"] if c.get("sub_text") else "")


def _build(_id: str, *, lite: bool, now: datetime, store, clock: Callable, load_day: Optional[Callable],
           today_bars: Optional[Callable], notes_out: Optional[set] = None) -> Optional[dict]:
    from . import tab as GT
    parsed = parse_id(_id)
    if parsed is None:
        return None
    d, sym, _setup = parsed
    n, m = GC.LEDGER_TAPE_TF_MIN, LG._m()
    # 1. the row — the ledger's own reader (alert_of), each doc in its own try
    docs = store.alert_rows([d])
    if docs is None:
        return fault_payload(_id, lite=lite, now=now, ticker=sym)
    row = None
    for doc in docs:
        try:
            r = LG.alert_of(doc, LG.KINDS[1])
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala tape: unreadable alert doc %s: %s", (doc or {}).get("_id"), type(exc).__name__)
            continue
        if r is not None and r["id"] == _id:
            row = r
            break
    if row is None:
        return None
    # 2. the stored grades (the nightly's)
    stored = {x.get("_id"): x for x in store.ledger_docs([d]) or [] if isinstance(x, dict)}
    doc_l = stored.get(_id) or {}
    same = doc_l.get("same") if isinstance(doc_l.get("same"), dict) else None
    nxt = doc_l.get("next") if isinstance(doc_l.get("next"), dict) else None
    # 3. the window: the alert day's 04:00 ET through the next column's end (or now)
    b_real = LG._bounds_of(row)
    b = b_real or LG._nominal_bounds(row)
    start = datetime.combine(d, dt_data.ET_PREMARKET_OPEN, tzinfo=ET).astimezone(UTC)
    end = min(now, b["next_end"])
    days = _market_days(d, b["next_date"])
    today = now.astimezone(ET).date()
    # 4. the bars per day
    notes = notes_out if notes_out is not None else set()
    parts = []
    today_part, cut = None, None
    for day in days:
        if day > today:
            continue
        if day == today:
            try:                                                # F8: the mini reads the memo only (load None)
                tbars, fetched = (today_bars or LG.today_bars)(sym, day, now=now, clock=clock,
                                                               load=None if lite else LG._today_load)
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala tape: today read failed for %s: %s", sym, type(exc).__name__)
                tbars, fetched = None, None
            if not tbars:
                notes.add("lite_today" if lite else "today_failed")   # A6: a mini's memo miss is not a failed read
                continue
            cut = LG._floor_minute(min(now, LG._aware(fetched) if isinstance(fetched, datetime) else now) - LG.SETTLE)
            today_part = [x for x in tbars if x[0] + ONE_MIN <= cut]
            f = _frame_of(today_part)
            if f is not None:
                parts.append(f)
            continue
        loader = load_day or (_cached_day if lite else _completed_day)
        try:
            if lite:
                res = loader(sym, day)
            else:
                with _day_lock(sym, day):
                    res = loader(sym, day)
            f = _as_frame(res)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala tape: day load failed for %s %s: %s", sym, day, type(exc).__name__)
            notes.add("fault")
            continue
        if f is not None:
            parts.append(f)
    # 5. the frame cut to the window -> the 5-minute bars
    frame = None
    if parts:
        frame = pd.concat(parts).sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        lo_t, hi_t = start.replace(tzinfo=None), end.replace(tzinfo=None)
        frame = frame[(frame.index >= lo_t) & (frame.index + ONE_MIN <= hi_t)]
    bars = bars5(frame)[:int(GC.LEDGER_TAPE_BARS_MAX)]
    # 6. today's provisional same column (the ledger's own grade on the closed minutes, as today_read grades it)
    session, is_today, _in = GT.session_for(now)
    same_p, prov = None, False
    # E1 (as today_read): yesterday's after-close row is graded on today's bars only when today_read's split check
    # answered "no split" (_TODAY_SPLIT memo — read only, never a fetch, F8); a held or unread check -> no grade
    sp_today = None
    if b["same_date"] == today and d != today:
        with LG._TODAY_LOCK:
            sp_today = LG._TODAY_SPLIT.get((today.isoformat(), sym, d.isoformat()))
    if (same is None and b_real is not None and b["same_date"] == today and row.get("plan") == LG.PLANS[0]
            and today_part is not None and cut is not None and (d == today or sp_today is False)):
        same_p = LG.grade(row, today_part, dict(b, same_end=min(b["same_end"], cut)), "same")
        prov = True
    # 7. the cells — the 🏁 Track record's own texts
    cs = LG._cell(row, "same", same or same_p, prov, now, session, is_today)
    cn = LG._cell(row, "next", nxt, False, now, session, is_today)
    heads = dict(LG.HEADS)
    read = _w("read", same_head=heads["same"], same=_cell_text(cs), next_head=heads["next"], next=_cell_text(cn))
    # 8. the lines, rules and dots
    f = LG.filled_grade(same or same_p, nxt)
    # the exit follows the column that DECIDED the trade: a same-session "open" decided next session -> next's exit
    ex = nxt if isinstance(nxt, dict) and nxt.get("outcome") in LG.DECIDED else f
    # F9: a split the ledger has on file — a split cell, or a decided column copied across a split (split_on)
    split = any(isinstance(g, dict) and (g.get("reason") == "split" or g.get("split_on")) for g in (same, nxt))
    split = split or (sp_today is not None and sp_today is not False)     # today_read's check answered a split
    hlines, rules, dots = [], [], []
    if row.get("plan") == LG.PLANS[0]:
        hlines.append({"key": "trigger", "px": row["trigger"], "tone": "buy",
                       "label": _w("trigger", px=LG._px(row["trigger"]))})
        hlines.append({"key": "stop", "px": row["stop"], "tone": "stop", "label": _w("stop", px=LG._px(row["stop"]))})
        if f is not None and LG._num(f.get("target_px")) is not None:
            hlines.append({"key": "target", "px": f["target_px"], "tone": "target",
                           "label": _w("target", m=m, px=LG._px(f["target_px"]))})
    at_iso = LG._iso_t(row.get("at_utc"))
    if at_iso is not None:
        rules.append({"key": "alert", "at": at_iso, "style": "solid", "tone": "alert",
                      "label": _w("alert", hhmm=LG._when(at_iso, d))})
    if f is not None and f.get("fill_t"):
        rules.append({"key": "fill", "at": f["fill_t"], "style": "dashed", "tone": "fill",
                      "label": _w("fill", hhmm=LG._when(f["fill_t"], d))})
        dots.append({"key": "fill", "at": f["fill_t"], "px": f["fill_px"], "tone": "fill",
                     "label": _w("fill_dot", px=LG._px(f["fill_px"]), hhmm=LG._when(f["fill_t"], d))})
        if ex.get("exit_t") and ex.get("outcome") == "win" and LG._num(ex.get("target_px")) is not None:
            dots.append({"key": "exit", "at": ex["exit_t"], "px": ex["target_px"], "tone": "target",
                         "label": _w("exit_target", m=m, hhmm=LG._when(ex["exit_t"], d))})
        elif (ex.get("exit_t") and ex.get("outcome") == "loss" and ex.get("reason") in ("stop", "stop_fill_minute")
              and LG._num(row.get("stop")) is not None):
            dots.append({"key": "exit", "at": ex["exit_t"], "px": row["stop"], "tone": "stop",
                         "label": _w("exit_stop", hhmm=LG._when(ex["exit_t"], d))})
    if split:                                               # F9: the bars are adjusted, the levels as printed
        hlines, dots = [], []
    axis, tone = None, None
    if bars:
        lo = min(x["l"] if x.get("l") is not None else x["c"] for x in bars)
        hi = max(x["h"] if x.get("h") is not None else x["c"] for x in bars)
        axis = {"bl": _stamp(bars[0]["t"]),
                "br": _w("axis_end", stamp=_stamp(bars[-1]["t"]), px=LG._px(bars[-1]["c"])),
                "tl": _w("axis_lo", px=LG._px(lo)), "tr": _w("axis_hi", px=LG._px(hi))}
        ref = LG._num((f or {}).get("fill_px"))
        ref = ref if ref is not None else LG._num(row.get("trigger"))
        if ref is not None and not split:                   # F9: an adjusted close vs an as-printed level: no tone
            tone = "up" if bars[-1]["c"] >= ref else "dn"
    if split:
        note = ENTRY_TAPE_WORDS["split"]
    elif "fault" in notes:
        note = ENTRY_TAPE_WORDS["fault"]
    elif "today_failed" in notes:
        note = ENTRY_TAPE_WORDS["today_failed"]
    elif "lite_today" in notes:
        note = ENTRY_TAPE_WORDS["lite_today"]
    elif not bars:
        note = _w("no_bars", n=n, sym=sym, date=d.isoformat())
    else:
        note = None
    return {"id": _id, "ticker": sym, "tf": _w("tf", n=n), "lite": bool(lite), "bars": bars, "n_bars": len(bars),
            "hlines": hlines, "rules": rules, "dots": dots, "axis": axis, "legend": _w("legend", n=n, m=m),
            "read": read, "title": read + "\n" + ENTRY_TAPE_WORDS["open_hint"], "tone": tone, "note": note,
            "aria": _w("aria", sym=sym, n=n), "as_of": now.isoformat()}


def _memo_ok(p: dict, notes: Optional[set] = None) -> bool:
    """A failed read (fault / today_failed) is never memoised, whatever note the payload shows (a split note wins)."""
    if notes and any(k in notes for k in _NO_MEMO_NOTES):
        return False
    return p.get("note") not in tuple(ENTRY_TAPE_WORDS[k] for k in _NO_MEMO_NOTES)


def entry_tape(_id: str, *, lite: bool = False, now: Optional[datetime] = None, store=None,
               clock: Optional[Callable] = None, load_day: Optional[Callable] = None,
               today_bars: Optional[Callable] = None) -> Optional[dict]:
    """None = unknown id (the route 404s). Else the FROZEN payload (BUILD_SPEC11 §3.4; lite = LITE_KEYS); a per-row
    fault -> the payload with bars [] and note ENTRY_TAPE_WORDS["fault"] (never raises). Memoised per (id, full | lite)
    LEDGER_TAPE_MEMO_SEC (_MEMO under _LOCK; older entries pruned on write); a full build refreshes the lite entry; a
    failed read (fault / today_failed) is never memoised. The lite build never fetches (F8)."""
    if parse_id(_id) is None:
        return None
    clock = clock or time.monotonic
    now = LG._aware(now)
    lite = bool(lite)
    key = (_id, "lite" if lite else "full")
    with _LOCK:
        hit = _MEMO.get(key)
    if hit is not None and clock() - hit[0] < GC.LEDGER_TAPE_MEMO_SEC:
        return hit[1]
    notes: set = set()
    try:
        from . import store as ST
        p = _build(_id, lite=lite, now=now, store=store or ST.default(), clock=clock, load_day=load_day,
                   today_bars=today_bars, notes_out=notes)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala tape: build failed for %s: %s", _id, type(exc).__name__)
        p = fault_payload(_id, lite=lite, now=now, ticker=parse_id(_id)[1])
    if p is None:
        return None
    out = lite_of(p) if lite else p
    if _memo_ok(p, notes):
        t = clock()
        with _LOCK:
            for k in [k for k, v in _MEMO.items() if t - v[0] >= GC.LEDGER_TAPE_MEMO_SEC]:
                _MEMO.pop(k, None)
            _MEMO[key] = (t, out)
            if not lite:
                _MEMO[(_id, "lite")] = (t, lite_of(p))
    return out


__all__ = ["ENTRY_TAPE_WORDS", "VIEW_PARAM", "VIEWS", "VIEW_DEFAULT", "TIMELINE_EMPTY_TEXT", "TAPE_HEAD", "TAPE_TOGGLE",
           "PAYLOAD_KEYS", "LITE_KEYS", "views_block", "parse_id", "bars5", "entry_tape", "lite_of", "fault_payload"]
