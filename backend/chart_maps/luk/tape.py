"""📈 The tape per 🥇 Luk A+ row of the 🏁 Track record (BUILD_SPEC §3.9, WP-B, 2026-11-01).

Ajay 2026-11-01: "look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement
their strategy please if they have online resources."

ONE luk_ledger row id ("{date}|{SYM}|{setup}|aplus") -> the SAME payload shape as 🚩's entry tape
(`gajjala.tape.PAYLOAD_KEYS`; lite = `gajjala.tape.LITE_KEYS` via `gajjala.tape.lite_of`), so the frontend's
GgEntryTape draws it unchanged: bars at `variant.tape_tf_min(LUK)` (gajjala.tape.tape_bars), the trigger / stop / fill /
exit lines, the alert and fill rules, the fill / exit / +3R / +5R dots. The grade and every cell text are the Luk
ledger's own (ledger.cells); every tape word is typed HERE (TAPE_WORDS). A fault -> `gajjala.tape.fault_payload`'s
shape (never raises); an unknown id -> None (the route 404s).

NEVER WRITES. Cost rules (gajjala.tape's): completed days through `gajjala.tape._completed_day` (the house loader, no
force — a cached day never fetches) on the full tape, `_cached_day` (intraday_cache only) on the mini; today through
`gajjala.ledger._today_load` on the full tape only (the mini never fetches). Each payload memoised per (id, full | lite)
for GC.LEDGER_TAPE_MEMO_SEC. The alert rule and the legend's record word follow the row's OWN line
(`gajjala.ledger.LINES`, as `ledger.rang_text` does): "live" = it rang his phone, anything else = the shadow words
(2026-11-01 go-live). UNMEASURED.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta
from typing import Callable, Optional

import pandas as pd

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import tape as GT
from chart_maps.gajjala import variant as V
from chart_maps.gajjala.ledger import ET, LINES, SETTLE, UTC, _aware, _iso_t, _num, _px, _today_load
from daytrading import data as dt_data

from . import constants as LC
from . import ledger as LL
from .variant import LUK

log = logging.getLogger("chart_maps.luk.tape")

PAYLOAD_KEYS = GT.PAYLOAD_KEYS
LITE_KEYS = GT.LITE_KEYS
ONE_MIN = timedelta(minutes=1)

# ── served words — the ONLY place a Luk tape word is typed ───────────────────────────────────────────────────────
TAPE_WORDS = {
    "trigger": "trigger {px}",
    "stop": "stop {px}",
    "fill_line": "fill {px}",
    "exit_line": "closed below the {ema} EMA {px}",
    "alert": "recorded {hhmm} ET — shadow, never sent",
    "alert_live": "rang {hhmm} ET — sent to your phone",
    "fill": "fill {hhmm}",
    "fill_dot": "fill {px} at {hhmm}",
    "exit_stop": "stopped {hhmm}",
    "exit_ema9": "closed below the {ema} EMA {md} · {px}",
    "reached": "+{m}R {px} at {hhmm}",
    "axis_hi": "hi {px}",
    "axis_lo": "lo {px}",
    "axis_end": "{stamp} · {px}",
    "tf": "{n}min · pre/post market",
    "legend": ("{n}-minute closes · shaded = pre / post market · solid line = {record} · dashed = the fill · "
               "levels = trigger / stop / fill · dots = the fill, the exit and his {partials} flags"),
    "record": "the shadow record",
    "record_live": "the alert that rang your phone",
    "aria": "{sym} {n}-minute tape around the 🥇 A+ entry",
    "read": "{rang}; {plan}; {fill}{exit}{flags}",
    "open_hint": "📈 click for the full tape",
    "no_bars": "No {n}-minute bars on file for {sym} on {date} yet.",
    "today_failed": "Today's tape could not be read on this open — the next re-read tries again.",
    "lite_today": "Today's bars are not in the mini yet — 📈 loads the full tape.",
}
ALERT_WORD = {LINES[0]: "alert_live", LINES[1]: "alert"}      # by the row's own line (ledger.RANG_TEXT's rule)
RECORD_WORD = {LINES[0]: "record_live", LINES[1]: "record"}
_NO_MEMO = ("fault", "today_failed", "lite_today")

_MEMO: dict = {}                  # {(LUK.key, id, "full" | "lite"): (clock(), payload)}
_LOCK = threading.Lock()


def _w(key: str, **kw) -> str:
    return TAPE_WORDS[key].format(**kw)


def _line(row: dict) -> str:
    """The row's own line; anything not a known line word -> the shadow line (ledger.rang_text's fallback)."""
    return row.get("line") if row.get("line") in ALERT_WORD else LINES[1]


def parse_id(_id) -> Optional[tuple]:
    """"{YYYY-MM-DD}|{SYM}|{setup}|aplus" with setup one of LC.SETUPS -> (date, SYM, setup); anything else -> None."""
    if not isinstance(_id, str):
        return None
    parts = _id.split("|")
    if len(parts) != 4:
        return None
    d_s, sym, setup, kind = parts
    if kind != LL.KIND or setup not in LC.SETUPS or len(d_s) != 10 or not sym or sym != sym.strip().upper():
        return None
    try:
        d = date.fromisoformat(d_s)
    except ValueError:
        return None
    return (d, sym, setup) if LL.row_id(d.isoformat(), sym, setup) == _id else None


def _when(iso_t, d: date) -> str:
    """"HH:MM" on the alert's day, "MM-DD HH:MM" on a later one (ET)."""
    t = LL._parse_at(iso_t)
    if t is None:
        return "—"
    et = t.astimezone(ET)
    return et.strftime("%H:%M") if et.date() == d else et.strftime("%m-%d %H:%M")


def _days(d: date, last: date) -> list:
    """The alert's session and the following market days through `last`, at most GC.LEDGER_TAPE_SESSIONS."""
    from catalysts.medical.reaction import next_market_day
    out = [d]
    while out[-1] < last and len(out) < int(GC.LEDGER_TAPE_SESSIONS):
        out.append(next_market_day(out[-1]))
    return out


def fault(_id, *, lite: bool = False, now: Optional[datetime] = None, ticker: Optional[str] = None) -> dict:
    """gajjala.tape.fault_payload's shape (every PAYLOAD_KEY, no bars, the fault note); lite -> LITE_KEYS."""
    p = GT.fault_payload(_id, lite=lite, now=now, ticker=ticker, variant=LUK)
    return GT.lite_of(p) if lite else p


def _build(_id: str, *, lite: bool, now: datetime, store, load_day: Optional[Callable],
           today_load: Optional[Callable], notes: set) -> Optional[dict]:
    d, sym, _setup = parse_id(_id)
    n = V.tape_tf_min(LUK)
    # 1. the row (the ledger's own reader) + its stored grade
    try:
        rows = LL.rows_for([d], store)
    except LL.LedgerReadError:
        return fault(_id, lite=False, now=now, ticker=sym)
    row = next((r for r in rows if r["id"] == _id), None)
    if row is None:
        return None
    stored = store.ledger_docs([d])
    if stored is None:
        return fault(_id, lite=False, now=now, ticker=sym)
    doc = next((x for x in stored if isinstance(x, dict) and x.get("_id") == _id), None)
    cell = LL.cells(row, doc)
    ok_doc = doc if isinstance(doc, dict) and doc.get("version") == LL.GRADE_VERSION else {}
    f = ok_doc.get("fill") if isinstance(ok_doc.get("fill"), dict) else {}
    w = ok_doc.get("walk") if isinstance(ok_doc.get("walk"), dict) else {}
    filled = f.get("entry") == LL.FILLED and _num(f.get("fill_px")) is not None
    # 2. the window: the alert day's 04:00 ET through the exit day (or today), ≤ LEDGER_TAPE_SESSIONS sessions
    today = now.astimezone(ET).date()
    last = LL._as_date(w.get("exit_date")) or today
    days = _days(d, max(d, min(last, today)))
    start = datetime.combine(d, dt_data.ET_PREMARKET_OPEN, tzinfo=ET).astimezone(UTC)
    cut = (now - SETTLE).replace(second=0, microsecond=0)
    parts = []
    for day in days:
        if day > today:
            continue
        if day == today:
            if lite:
                notes.add("lite_today")
                continue
            try:
                res = (today_load or _today_load)(sym, day)
                frame = GT._as_frame(res)
                failed = isinstance(res, tuple) and len(res) > 1 and bool(res[1])
            except Exception as exc:                            # noqa: BLE001
                log.warning("luk tape: today read failed for %s: %s", sym, type(exc).__name__)
                frame, failed = None, True
            if frame is None or failed:
                notes.add("today_failed")
                continue
            parts.append(frame)
            continue
        loader = load_day or (GT._cached_day if lite else GT._completed_day)
        try:
            frame = GT._as_frame(loader(sym, day))
        except Exception as exc:                                # noqa: BLE001
            log.warning("luk tape: day load failed for %s %s: %s", sym, day, type(exc).__name__)
            notes.add("fault")
            continue
        if frame is not None:
            parts.append(frame)
    frame = None
    if parts:
        frame = pd.concat(parts).sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        lo_t, hi_t = start.replace(tzinfo=None), cut.astimezone(UTC).replace(tzinfo=None)
        frame = frame[(frame.index >= lo_t) & (frame.index + ONE_MIN <= hi_t)]
    bars = GT.tape_bars(frame, n)[:V.tape_bars_max(LUK)]
    shown = {x.isoformat() for x in days}
    # 3. the read — the ledger's own cell texts
    exit_bit = f"; {cell['exit_text']}" if cell.get("exit_text") else ""
    flags_bit = f"; {cell['flags_text']}" if cell.get("flags_text") else ""
    read = _w("read", rang=cell["rang_text"], plan=cell["plan_text"] or "", fill=cell["fill_text"], exit=exit_bit,
              flags=flags_bit)
    # 4. lines, rules, dots
    hlines, rules, dots = [], [], []
    if row.get("plan") == LL.PLAN_OK:
        hlines.append({"key": "trigger", "px": row["trigger"], "tone": "buy",
                       "label": _w("trigger", px=_px(row["trigger"]))})
        hlines.append({"key": "stop", "px": row["stop"], "tone": "stop", "label": _w("stop", px=_px(row["stop"]))})
    at_iso = _iso_t(row.get("at_utc"))
    if at_iso is not None:
        rules.append({"key": "alert", "at": at_iso, "style": "solid", "tone": "alert",
                      "label": _w(ALERT_WORD[_line(row)], hhmm=_when(at_iso, d))})
    ema = int(LC.LUK_PULLBACK_DAILY_EMA)
    if filled:
        fpx = float(f["fill_px"])
        hlines.append({"key": "fill", "px": fpx, "tone": "fill", "label": _w("fill_line", px=_px(fpx))})
        rules.append({"key": "fill", "at": f["fill_t"], "style": "dashed", "tone": "fill",
                      "label": _w("fill", hhmm=_when(f["fill_t"], d))})
        dots.append({"key": "fill", "at": f["fill_t"], "px": fpx, "tone": "fill",
                     "label": _w("fill_dot", px=_px(fpx), hhmm=_when(f["fill_t"], d))})
        r = _num(row.get("r_usd"))
        for m in LC.LUK_PARTIAL_R:
            t_m = w.get(LL._flag_key(m) + "_t")
            t_at = LL._parse_at(t_m)
            if w.get(LL._flag_key(m)) and t_at is not None and r is not None \
                    and t_at.astimezone(ET).date().isoformat() in shown:
                px = round(fpx + float(m) * r, 4)
                dots.append({"key": f"r{int(m)}", "at": t_m, "px": px, "tone": "target",
                             "label": _w("reached", m=int(m), px=_px(px), hhmm=_when(t_m, d))})
        if w.get("exit") == LL.EXITS[0] and w.get("exit_t") and (w.get("exit_date") or "") in shown:
            dots.append({"key": "exit", "at": w["exit_t"], "px": row["stop"], "tone": "stop",
                         "label": _w("exit_stop", hhmm=_when(w["exit_t"], d))})
        elif w.get("exit") == LL.EXITS[1] and _num(w.get("exit_px")) is not None:
            xd = LL._as_date(w.get("exit_date"))
            hlines.append({"key": "exit", "px": float(w["exit_px"]), "tone": "target",
                           "label": _w("exit_line", ema=ema, px=_px(w["exit_px"]))})
            if xd is not None and xd.isoformat() in shown:
                at_x = _iso_t(LL.close_utc(xd) - ONE_MIN)
                dots.append({"key": "exit", "at": at_x, "px": float(w["exit_px"]), "tone": "target",
                             "label": _w("exit_ema9", ema=ema, md=LL._md(xd), px=_px(w["exit_px"]))})
    # 5. axis, tone, note
    axis, tone = None, None
    if bars:
        lo = min(x["l"] if x.get("l") is not None else x["c"] for x in bars)
        hi = max(x["h"] if x.get("h") is not None else x["c"] for x in bars)
        axis = {"bl": GT._stamp(bars[0]["t"]),
                "br": _w("axis_end", stamp=GT._stamp(bars[-1]["t"]), px=_px(bars[-1]["c"])),
                "tl": _w("axis_lo", px=_px(lo)), "tr": _w("axis_hi", px=_px(hi))}
        ref = float(f["fill_px"]) if filled else _num(row.get("trigger"))
        if ref is not None:
            tone = "up" if bars[-1]["c"] >= ref else "dn"
    if "fault" in notes:
        note = GT.ENTRY_TAPE_WORDS["fault"]
    elif "today_failed" in notes:
        note = TAPE_WORDS["today_failed"]
    elif "lite_today" in notes:
        note = TAPE_WORDS["lite_today"]
    elif not bars:
        note = _w("no_bars", n=n, sym=sym, date=d.isoformat())
    else:
        note = None
    return {"id": _id, "ticker": sym, "tf": _w("tf", n=n), "lite": bool(lite), "bars": bars, "n_bars": len(bars),
            "hlines": hlines, "rules": rules, "dots": dots, "axis": axis,
            "legend": _w("legend", n=n, partials=LL.partials_text(),
                         record=TAPE_WORDS[RECORD_WORD[_line(row)]]), "read": read,
            "title": read + "\n" + TAPE_WORDS["open_hint"], "tone": tone, "note": note,
            "aria": _w("aria", sym=sym, n=n), "as_of": now.isoformat()}


def entry_tape(_id, *, lite: bool = False, now: Optional[datetime] = None, store=None,
               clock: Optional[Callable] = None, load_day: Optional[Callable] = None,
               today_load: Optional[Callable] = None) -> Optional[dict]:
    """None = unknown id (the route 404s). Else the payload (PAYLOAD_KEYS; lite = LITE_KEYS); any fault -> the
    fault payload (never raises). Memoised per (id, full | lite) for GC.LEDGER_TAPE_MEMO_SEC; a failed read is never
    memoised. The lite build never fetches."""
    ref = parse_id(_id)
    if ref is None:
        return None
    clock = clock or time.monotonic
    now = _aware(now)
    lite = bool(lite)
    key = (LUK.key, _id, "lite" if lite else "full")
    with _LOCK:
        hit = _MEMO.get(key)
    if hit is not None and clock() - hit[0] < GC.LEDGER_TAPE_MEMO_SEC:
        return hit[1]
    notes: set = set()
    try:
        if store is None:
            from . import store as LS
            store = LS.default()
        p = _build(_id, lite=lite, now=now, store=store, load_day=load_day, today_load=today_load, notes=notes)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("luk tape: build failed for %s: %s", _id, type(exc).__name__)
        notes.add("fault")
        p = GT.fault_payload(_id, lite=lite, now=now, ticker=ref[1], variant=LUK)
    if p is None:
        return None
    out = GT.lite_of(p) if lite else p
    if not any(k in notes for k in _NO_MEMO) and p.get("note") != GT.ENTRY_TAPE_WORDS["fault"]:
        t = clock()
        with _LOCK:
            for k in [k for k, v in _MEMO.items() if t - v[0] >= GC.LEDGER_TAPE_MEMO_SEC]:
                _MEMO.pop(k, None)
            _MEMO[key] = (t, out)
    return out


__all__ = ["PAYLOAD_KEYS", "LITE_KEYS", "TAPE_WORDS", "parse_id", "entry_tape", "fault"]
