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

🚩 THE 1-MINUTE PAGE (2026-10-27, BUILD_SPEC27 §3.7 / WP-C): the same tape for the 1-minute page's store (`V.of(store)`
= GG1): bars at variant.tape_tf_min (GG1M_TAPE_TF_MIN — 1-minute bars, HIS CALL #8), capped at variant.tape_bars_max
(GG1M_TAPE_BARS_MAX), its minute words from that number, and its memo keyed (variant key, id, full | lite) — a GG1 id
has the SAME shape as a GG5 id, so a GG5 memo entry never answers it. GG5 keeps every byte and the (id, …) key.

📈 THE 🧠 POTENTIAL TAPE (2026-10-29, BUILD_SPEC31 D1). Ajay, verbatim: "I wanna see this kind of graph in our Track
record page this screenshot is from Promo circuit page." The 🏁 list's 🧠 rows ("{date}|{SYM}|{setup}|potential",
LG.KINDS[0]) get the SAME build as an A+ row: the ledger's own 🧠 row (alert_of over store.potential_pushes, the
variant's push states), its stored grades (GG's trade math as if entered at the trigger), the same window, bars, lines,
rules and dots — only the words are the potential's own (POTENTIAL_TAPE_KEYS below: the ring, the plan, entered / never
printed, the no-risk / no-plan sentence, the legend, the aria). A no_risk / no_plan 🧠 row draws the bars and the ring
only (the composer's own rule: no levels without an ok plan). The cost rules are unchanged (the mini never fetches),
the memo key carries the id (the kind is in it). Every A+ payload keeps every byte (the sha256 pin in
tests/test_gajjala_tape_potential_2026_10_29.py).
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
from . import variant as V

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
    "split_replayed": "A split is on file after this alert — the replayed bars print as traded before and after it, so the levels are not drawn.",   # AMENDMENTS11 A7
    # 📈 2026-10-29 (BUILD_SPEC31 D1) — the 🧠 potential tape's own words (the A+ words above never move)
    "pot_rang": "🧠 potential rang {hhmm} ET",
    "pot_shadow": "🧠 potential recorded {hhmm} ET — shadow, never sent",
    "pot_no_time": "🧠 potential · {why}",
    "pot_plan": "{head} · trigger {trigger} · stop {stop}",
    "pot_entered": "entered at the trigger {hhmm} ET · fill {px}",
    "pot_never": "the trigger never printed",
    "pot_no_levels": "{why} — the bars and the ring only, no levels drawn",
    "pot_alert": "🧠 rang {hhmm} ET",
    "pot_alert_shadow": "🧠 recorded {hhmm} ET",
    "pot_legend": "{n}-minute closes · shaded = pre / post market · solid line = the 🧠 ring · dashed = the fill at the trigger · levels = trigger / stop / +{m}R",
    "pot_legend_no_levels": "{n}-minute closes · shaded = pre / post market · solid line = the 🧠 ring",
    "pot_aria": "{sym} {n}-minute tape around the 🧠 potential",
}
POTENTIAL_TAPE_KEYS = tuple(k for k in ENTRY_TAPE_WORDS if k.startswith("pot_"))   # the 🧠 tape's words (D1)
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
    """A ledger id "{YYYY-MM-DD}|{SYM}|{setup}|{kind}" with kind an A+ (LG.KINDS[1]) or — 2026-10-29, BUILD_SPEC31 D1 —
    a 🧠 potential (LG.KINDS[0]) -> (date, SYM, setup); junk, another kind or a non-str -> None (kind_of names the
    kind). (Phase 2: a "REPLAY:" id is dispatched before this — replay_ref.)"""
    if not isinstance(_id, str):
        return None
    parts = _id.split("|")
    if len(parts) != 4:
        return None
    d_s, sym, setup, kind = parts
    if kind not in (LG.KINDS[1], LG.KINDS[0]) or len(d_s) != 10 or not sym or sym != sym.strip().upper() or not setup.strip():
        return None
    try:
        d = date.fromisoformat(d_s)
    except ValueError:
        return None
    return d, sym, setup


def kind_of(_id) -> Optional[str]:
    """The kind of a ledger id parse_id reads (LG.KINDS[1] A+ | LG.KINDS[0] 🧠); anything else -> None."""
    return _id.rsplit("|", 1)[-1] if parse_id(_id) is not None else None


def replay_ref(_id) -> Optional[tuple]:
    """⏪ A replay id "REPLAY:{YYYY-MM-DD}|{SYM}|{setup}" (exactly ledger.replay_id's shape, no "#") -> (date, SYM,
    setup); anything else -> None (DECISIONS11 D5, BUILD_SPEC11 §3.11)."""
    if not isinstance(_id, str) or not _id.startswith(LG.REPLAY_ID_PREFIX) or "#" in _id:
        return None
    parts = _id[len(LG.REPLAY_ID_PREFIX):].split("|")
    if len(parts) != 3:
        return None
    d_s, sym, setup = parts
    if len(d_s) != 10 or not sym or sym != sym.strip().upper() or not setup.strip():
        return None
    try:
        d = date.fromisoformat(d_s)
    except ValueError:
        return None
    return (d, sym, setup) if LG.replay_id(d.isoformat(), sym, setup) == _id else None


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
    None; [] for None / empty. 2026-10-27: = tape_bars(df, LEDGER_TAPE_TF_MIN) (read at call time)."""
    return tape_bars(df, GC.LEDGER_TAPE_TF_MIN)


def tape_bars(df, tf_min) -> list:
    """bars5's engine at any bar size `tf_min` (minutes) — GG5 LEDGER_TAPE_TF_MIN, the 1-minute page GG1M_TAPE_TF_MIN
    (2026-10-27): the same resampler, the same shape."""
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
    rule = f"{int(tf_min)}min"
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
def fault_payload(_id, *, lite: bool = False, now: Optional[datetime] = None, ticker: Optional[str] = None,
                  variant=None) -> dict:
    """AMENDMENTS11 F19 — the tape that could not be built: every PAYLOAD_KEY present, no bars, the fault note.
    `variant` (2026-10-27): its bar size in the words (GG5 LEDGER_TAPE_TF_MIN)."""
    n = V.tape_tf_min(variant)
    aria_key = "pot_aria" if kind_of(_id) == LG.KINDS[0] else "aria"          # 2026-10-29: a 🧠 id's own aria
    return {"id": _id if isinstance(_id, str) else "", "ticker": ticker, "tf": _w("tf", n=n), "lite": bool(lite),
            "bars": [], "n_bars": 0, "hlines": [], "rules": [], "dots": [], "axis": None, "legend": None,
            "read": None, "title": None, "tone": None, "note": ENTRY_TAPE_WORDS["fault"],
            "aria": _w(aria_key, sym=ticker, n=n) if ticker else None, "as_of": LG._aware(now).isoformat()}


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


def _stored_bars5(raw) -> list:
    """⏪ A replay doc's stored `bars5` -> the tape bars: each {t, o, h, l, c, v, s} validated (t an int epoch ms, c a
    finite number; o / h / l / v a number or None; s a string or None), ascending by t, one bar per t, capped at
    LEDGER_TAPE_BARS_MAX. Junk is dropped, never drawn."""
    out = {}
    for x in raw if isinstance(raw, list) else []:
        if not isinstance(x, dict):
            continue
        t, c = x.get("t"), LG._num(x.get("c"))
        if isinstance(t, bool) or not isinstance(t, int) or c is None:
            continue
        s = x.get("s")
        out[t] = {"t": t, "o": LG._num(x.get("o")), "h": LG._num(x.get("h")), "l": LG._num(x.get("l")), "c": c,
                  "v": LG._num(x.get("v")), "s": s if isinstance(s, str) else None}
    return [out[k] for k in sorted(out)][:int(GC.LEDGER_TAPE_BARS_MAX)]


def _build_replay(_id: str, *, lite: bool, now: datetime, store) -> Optional[dict]:
    """⏪ (DECISIONS11 D2 / D5, BUILD_SPEC11 §3.11) a REPLAYED row's tape: the replay doc's stored `bars5` (as printed,
    built by bars5() in scripts/gajjala_replay.py), its own pre-graded columns, note = ledger.REPLAY_NOTE. NEVER calls
    a loader (no cache read, no fetch, no today memo). None = no such replay doc (the route 404s)."""
    from . import tab as GT
    ref = replay_ref(_id)
    if ref is None:
        return None
    d, sym, _setup = ref
    rd = getattr(store, "replay_rows", None)
    docs = rd([d]) if callable(rd) else None
    if docs is None:
        return fault_payload(_id, lite=lite, now=now, ticker=sym)
    doc, row = None, None
    for x in docs:
        if not isinstance(x, dict) or x.get("_id") != _id:
            continue
        try:
            r = LG.alert_of(x, LG.KINDS[1])
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala tape: unreadable replay doc %s: %s", _id, type(exc).__name__)
            continue
        if r is not None and r["line"] == LG.LINES[2] and r["id"] == _id:
            doc, row = x, r
            break
    if row is None:
        return None
    same = doc.get("same") if isinstance(doc.get("same"), dict) else None
    nxt = doc.get("next") if isinstance(doc.get("next"), dict) else None
    bars = _stored_bars5(doc.get("bars5"))
    session, is_today, _in = GT.session_for(now)
    cs = LG.replay_cell(row, "same", same, now, session, is_today)
    cn = LG.replay_cell(row, "next", nxt, now, session, is_today)
    # F9 (as _build): a split cell on file -> the stored bars5 spans the split (the next session's minutes print
    # post-split), so the as-printed levels are not drawn — no hlines, no dots, no tone. The note says why in the
    # replay's own words (AMENDMENTS11 A7: ENTRY_TAPE_WORDS["split"] says "the bars are adjusted", which a replay's
    # bars are not) and keeps REPLAY_NOTE after it.
    split = any(isinstance(g, dict) and (g.get("reason") == "split" or g.get("split_on")) for g in (same, nxt))
    note = (ENTRY_TAPE_WORDS["split_replayed"] + " " + LG.REPLAY_NOTE) if split else LG.REPLAY_NOTE
    return _compose(_id, row, d, sym, bars, cs, cn, same, nxt, split=split, note=note, lite=lite, now=now)


def _build(_id: str, *, lite: bool, now: datetime, store, clock: Callable, load_day: Optional[Callable],
           today_bars: Optional[Callable], notes_out: Optional[set] = None) -> Optional[dict]:
    from . import tab as GT
    if isinstance(_id, str) and _id.startswith(LG.REPLAY_ID_PREFIX):       # ⏪ the replayed line: never a loader
        return _build_replay(_id, lite=lite, now=now, store=store)
    parsed = parse_id(_id)
    if parsed is None:
        return None
    d, sym, _setup = parsed
    kind = kind_of(_id)                                         # 2026-10-29: A+ (as always) or a 🧠 potential (D1)
    pot = kind == LG.KINDS[0]
    v = V.of(store)                                             # 2026-10-27: GG5 for today's store
    n, m = V.tape_tf_min(v), LG._m()
    # 1. the row — the ledger's own reader (alert_of), each doc in its own try; a 🧠 row from the 🧠 pushes the
    #    ledger reads (the variant's push states), with the variant (the 1-minute page's shadow 🧠 rows are rows)
    docs = store.potential_pushes([d]) if pot else store.alert_rows([d])
    if docs is None:
        return fault_payload(_id, lite=lite, now=now, ticker=sym, variant=v)
    row = None
    for doc in docs:
        try:
            r = (LG.alert_of(doc, kind, variant=v) if pot and not V.is_gg5(v) else LG.alert_of(doc, kind) if pot
                 else LG.alert_of(doc, LG.KINDS[1]))
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
    # 5. the frame cut to the window -> the tape bars (GG5: 5-minute; the 1-minute page: its own size and cap)
    frame = None
    if parts:
        frame = pd.concat(parts).sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]
        lo_t, hi_t = start.replace(tzinfo=None), end.replace(tzinfo=None)
        frame = frame[(frame.index >= lo_t) & (frame.index + ONE_MIN <= hi_t)]
    bars = (bars5(frame)[:int(GC.LEDGER_TAPE_BARS_MAX)] if V.is_gg5(v)
            else tape_bars(frame, n)[:V.tape_bars_max(v)])
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
    # F9: a split the ledger has on file — a split cell, or a decided column copied across a split (split_on)
    split = any(isinstance(g, dict) and (g.get("reason") == "split" or g.get("split_on")) for g in (same, nxt))
    split = split or (sp_today is not None and sp_today is not False)     # today_read's check answered a split
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
    return _compose(_id, row, d, sym, bars, cs, cn, same or same_p, nxt, split=split, note=note, lite=lite, now=now,
                    n=n, kind=kind)


def _pot_words(row: dict, d: date, same: Optional[dict], nxt: Optional[dict], f: Optional[dict], read: str, n: int,
               m: str) -> dict:
    """📈 2026-10-29 (BUILD_SPEC31 D1) — a 🧠 row's own words over the SAME lines / rules / dots: the read leads with
    the ring and the plan, then entered at the trigger / the trigger never printed (only once the next-session
    column holds a stored no_entry grade — a provisional or same-only grade is still live and claims neither) / the
    no-risk or no-plan sentence (LG.NO_RISK_TEXT / NO_PLAN_TEXT), then the 🏁 cells."""
    at_iso = LG._iso_t(row.get("at_utc"))
    shadow = row.get("push_state") == GC.PUSH_MODES[0]       # the 1-minute page's 🧠 recorded in shadow, never sent
    if at_iso is None:
        head = _w("pot_no_time", why=LG.NO_TIME_TEXT)
    else:
        head = _w("pot_shadow" if shadow else "pot_rang", hhmm=LG._when(at_iso, d))
    ok = row.get("plan") == LG.PLANS[0]
    if ok:
        head = _w("pot_plan", head=head, trigger=LG._px(row["trigger"]), stop=LG._px(row["stop"]))
        if f is not None and f.get("fill_t"):
            entry = _w("pot_entered", hhmm=LG._when(f["fill_t"], d), px=LG._px(f["fill_px"]))
        elif isinstance(nxt, dict) and nxt.get("entry") == "no_entry":
            entry = ENTRY_TAPE_WORDS["pot_never"]
        else:
            entry = None
    else:
        entry = _w("pot_no_levels", why=LG.NO_RISK_TEXT if row.get("plan") == LG.PLANS[2] else LG.NO_PLAN_TEXT)
    pread = "; ".join(x for x in (head, entry, read) if x)
    return {"read": pread, "legend": _w("pot_legend" if ok else "pot_legend_no_levels", n=n, m=m),
            "aria": _w("pot_aria", sym=row["symbol"], n=n),
            "alert": "pot_alert_shadow" if shadow else "pot_alert"}


def _compose(_id: str, row: dict, d: date, sym: str, bars: list, cs: dict, cn: dict, same: Optional[dict],
             nxt: Optional[dict], *, split: bool, note: Optional[str], lite: bool, now: datetime,
             n: Optional[int] = None, kind: Optional[str] = None) -> dict:
    """Steps 7–8 — ONE composer for the live / shadow tape and the ⏪ replayed tape: the read (the 🏁 cells), the
    trigger / stop / +1R lines, the alert / fill rules, the fill / exit dots, the axis and the tone. `n` (2026-10-27)
    = the bar size in minutes of the words; None = LEDGER_TAPE_TF_MIN (GG5, as always). `kind` (2026-10-29) =
    LG.KINDS[0] for a 🧠 row: the same marks, the potential's own words (_pot_words); anything else = A+, every byte
    as before."""
    n, m = (GC.LEDGER_TAPE_TF_MIN if n is None else n), LG._m()
    heads = dict(LG.HEADS)
    read = _w("read", same_head=heads["same"], same=_cell_text(cs), next_head=heads["next"], next=_cell_text(cn))
    # 8. the lines, rules and dots
    f = LG.filled_grade(same, nxt)
    # the exit follows the column that DECIDED the trade: a same-session "open" decided next session -> next's exit
    ex = nxt if isinstance(nxt, dict) and nxt.get("outcome") in LG.DECIDED else f
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
    pw = _pot_words(row, d, same, nxt, f, read, n, m) if kind == LG.KINDS[0] else None
    if pw is not None:                                      # 📈 D1: the 🧠 ring's own label, same rule
        for r in rules:
            if r["key"] == "alert":
                r["label"] = _w(pw["alert"], hhmm=LG._when(r["at"], d))
        read = pw["read"]
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
    return {"id": _id, "ticker": sym, "tf": _w("tf", n=n), "lite": bool(lite), "bars": bars, "n_bars": len(bars),
            "hlines": hlines, "rules": rules, "dots": dots, "axis": axis,
            "legend": pw["legend"] if pw is not None else _w("legend", n=n, m=m),
            "read": read, "title": read + "\n" + ENTRY_TAPE_WORDS["open_hint"], "tone": tone, "note": note,
            "aria": pw["aria"] if pw is not None else _w("aria", sym=sym, n=n), "as_of": now.isoformat()}


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
    ref = parse_id(_id) or replay_ref(_id)                       # ⏪ a "REPLAY:" id is dispatched in _build
    if ref is None:
        return None
    clock = clock or time.monotonic
    now = LG._aware(now)
    lite = bool(lite)
    from . import store as ST
    try:
        st = store or ST.default()
    except Exception as exc:                                    # noqa: BLE001 — _build below serves the fault
        log.warning("gajjala tape: no store: %s", type(exc).__name__)
        st = None
    v = V.of(st)
    gg5 = V.is_gg5(v)

    def mkey(mode: str) -> tuple:
        """GG5: (id, mode), as always; another variant: (variant key, id, mode) — a GG1 id has a GG5 id's shape."""
        return (_id, mode) if gg5 else (v.key, _id, mode)
    key = mkey("lite" if lite else "full")
    with _LOCK:
        hit = _MEMO.get(key)
    if hit is not None and clock() - hit[0] < GC.LEDGER_TAPE_MEMO_SEC:
        return hit[1]
    notes: set = set()
    try:
        p = _build(_id, lite=lite, now=now, store=st, clock=clock, load_day=load_day,
                   today_bars=today_bars, notes_out=notes)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala tape: build failed for %s: %s", _id, type(exc).__name__)
        p = fault_payload(_id, lite=lite, now=now, ticker=ref[1]) if gg5 else fault_payload(
            _id, lite=lite, now=now, ticker=ref[1], variant=v)
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
                _MEMO[mkey("lite")] = (t, lite_of(p))
    return out


__all__ = ["ENTRY_TAPE_WORDS", "POTENTIAL_TAPE_KEYS", "kind_of", "VIEW_PARAM", "VIEWS", "VIEW_DEFAULT", "TIMELINE_EMPTY_TEXT", "TAPE_HEAD", "TAPE_TOGGLE",
           "PAYLOAD_KEYS", "LITE_KEYS", "views_block", "parse_id", "replay_ref", "bars5", "tape_bars", "entry_tape",
           "lite_of",
           "fault_payload"]
