"""👀 Gajjala's Watch — the owner's GET payload and every served word (spec §3.7, WP-A, 2026-11-15).

Ajay 2026-11-15, verbatim: "When I add a ticker I need 1 min 3 min and 5 min charts... Not the SEPA and I need clear
distinction or may be a brighter and thicker 21 EMA and 9 EMA" · "I have a 27 inch monitor I wanna fit 3x3 tikers on
watch at any given time on this tashboard" · "Any chart I view make sure you are showing me from 4 AM for historical
behaviour and also the right side with gaps to see where it might go".

READS STORED DOCS ONLY — never a bar fetch, never a snapshot (the minute loop / the build child write the tile docs):
  * the list (`colls.owner_symbols`, one find_one);
  * the tile docs of the listed names (ONE `find({_id: {$in: names}})`; an unlisted `only` name is never read);
  * the loop state doc (ONE find_one `_id = C.STATE_LATEST_ID`);
  * today's pushed claims (ONE `find({date: session, state: "cross_pushed"})`).

Rows follow HIS list order — the server never reorders. A doc with `frames` is `ok` (stale + the status sentence when
its last read was not `loaded`: the last good charts stay, C1.2); a doc without frames serves its status; no doc =
`pending`. The `held` chip of a frame is served only when it names that frame's latest drawn UP cross (C4.4). The rule
sentences (`info`) are served ONCE, never per chart (C4.6). Every word below is a constant; every number in a word is a
`{}` field filled from its constant at CALL time. UNMEASURED — a cross is information, not an entry.
"""
from __future__ import annotations

import importlib
import logging
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC

from . import colls as CO
from . import constants as C

log = logging.getLogger("chart_maps.gajjala_watch.payload")
ET = ZoneInfo("America/New_York")

# ── words (every number a {} field) ──────────────────────────────────────────────────────────────────────────────
TITLE_TEXT = "{label} — your tickers on {minutes}-minute bars from {open} ET"
OWNER_ONLY_TEXT = "{label} is private — shown to the account owner only."
ERROR_TEXT = "The watch could not be built: {why}"
HONESTY_TEXT = ("A {fast}-over-{slow} cross is information, not an entry. UNMEASURED: nothing has measured what follows a "
                "cross on these frames.")
LEGEND_TEXT = "{period} EMA"
ADD_LABEL = "Add"
ADD_PLACEHOLDER = "Ticker, e.g. OMH"
REMOVE_LABEL = "Remove"
EMPTY_TEXT = "Your watch is empty — add a ticker to see its {minutes}-minute charts"
FULL_TEXT = "Your watch holds {max} tickers — remove one to add another"
PENDING_TEXT = {True: "⏳ first read at the next minute", False: "⏳ reading {sym}'s last session"}
NO_PRINTS_TEXT = {True: "No prints yet today for {sym} — the chart starts at its first print",
                  False: "No prints for {sym} on {session}"}
NO_BARS_TEXT = "No minute bars for {sym} on {session} or the session before — check the ticker"
FAILED_TEXT = "The minute bars could not be read — the next minute tries again"
FAILED_STALE_TEXT = "⚠️ the {hhmm} read failed — showing the {as_of} bars"
OVER_BUDGET_TEXT = "Not read this minute (time budget) — the next minute tries again"
OVER_BUDGET_STALE_TEXT = "⚠️ not read this minute (time budget) — showing the {as_of} bars"
PASS_TEXT = "🕐 minute read {at_et} ET · {n_read} of {n_names} tickers read"
PASS_BARE_TEXT = "🕐 minute read {at_et} ET"
PASS_REASON_TEXT = "{text} · {reason}"
RANG_TEXT = "🔔 {frame} {fast}/{slow} cross rang {at_et} ET"
HELD_TEXT = {
    "off": "🔕 not sent — the watch push is off",
    "missed_fetch": "🔕 not sent — the minute read failed at the cross (never sent late)",
    "suppressed_closed": "🔕 held — market closed",
    "suppressed_premarket": "🔕 held — pre-market",
    "suppressed_first15": "🔕 held — first {first} minutes",
    "suppressed_window": "🔕 held — after the extended close",
    "under_floor": "🔕 held — under GG's {floor:,} session-volume floor",
    "not_uptrend": "🔕 held — not a K5 uptrend",
    "no_store": "🔕 not sent — the alert store was down",
    "no_target": "🔕 no device to ring",
    "failed": "🔕 the send failed",
}
STORE_TEXT = {
    "added": "👀 {sym} added to your watch",
    "already": "{sym} is already on your watch",
    "full": FULL_TEXT,
    "bad_symbol": "Not a ticker — letters only, like OMH or BRK.B",
    "error": "The watch list could not be saved — try again",
    "removed": "{sym} removed from your watch",
    "absent": "{sym} is not on your watch",
}
STORE_NO_SYMBOL = "That ticker"

ROW_STATES = ("ok", "pending", "no_prints", "no_bars", "failed", "over_budget")
DOC_STATUSES = ("loaded", "no_prints", "no_bars", "failed", "over_budget")      # build.status_of (WP-B)
PUSHED_STATE = "cross_pushed"                                                    # = alerts.FADE_CROSS_STATES[1] (test pins)
HELD_PUSHED = "pushed"


# ── words filled at call time ────────────────────────────────────────────────────────────────────────────────────
def _frame_minutes() -> list:
    import pandas as pd
    return [int(pd.Timedelta(rule).total_seconds() // 60) for _tf, rule in C.FRAMES]


def _minutes_words() -> str:
    """"1-, 3- and 5" from C.FRAMES (the rules' minutes), never typed."""
    mins = [str(m) for m in _frame_minutes()]
    return (", ".join(m + "-" for m in mins[:-1]) + " and " + mins[-1]) if len(mins) > 1 else "".join(mins)


def title() -> str:
    return TITLE_TEXT.format(label=C.TAB_LABEL, minutes=_minutes_words(), open=GC.PASS_OPEN_ET)


def empty_text() -> str:
    return EMPTY_TEXT.format(minutes=_minutes_words())


def owner_only_payload() -> dict:
    return {"state": "owner_only", "reason": OWNER_ONLY_TEXT.format(label=C.TAB_LABEL), "title": title()}


def error_payload(why: str) -> dict:
    return {"state": "error", "reason": ERROR_TEXT.format(why=why), "title": title()}


def full_text() -> str:
    return FULL_TEXT.format(max=C.MAX_SYMBOLS)


def honesty() -> str:
    return HONESTY_TEXT.format(fast=GC.EMA_FAST, slow=GC.EMA_SLOW)


def held_text(reason) -> Optional[str]:
    t = HELD_TEXT.get(reason) if isinstance(reason, str) else None
    return t.format(first=GC.NO_TRADE_AFTER_OPEN_MIN, floor=int(GC.K11_MIN_SESSION_VOLUME)) if t else None


def store_text(state: str, symbol: Optional[str]) -> str:
    t = STORE_TEXT.get(state, STORE_TEXT["error"])
    return t.format(sym=symbol or STORE_NO_SYMBOL, max=C.MAX_SYMBOLS)


def push_mode() -> str:
    m = C.PUSH_MODE
    return m if isinstance(m, str) and m in C.PUSH_MODES else C.PUSH_MODES[0]


def legend() -> list:
    from chart_maps.gajjala import bars as B
    return [{"tone": tone, "label": LEGEND_TEXT.format(period=period)} for tone, _l, period in B.EMA_TONES]


def _lazy_call(module: str, fn: str) -> Optional[str]:
    """WP-B's sentence (`build.uptrend_rule` / `cross_alerts.rules_line`), imported lazily through sys.modules; any
    failure → None (the board still answers)."""
    try:
        out = getattr(importlib.import_module(module), fn)()
        return out if isinstance(out, str) else None
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala_watch: %s.%s unavailable: %s", module, fn, exc)
        return None


def info() -> dict:
    return {"honesty": honesty(),
            "push_text": _lazy_call("chart_maps.gajjala_watch.cross_alerts", "rules_line"),
            "uptrend_rule": _lazy_call("chart_maps.gajjala_watch.build", "uptrend_rule"),
            "push_mode": push_mode(), "push_frames": list(C.PUSH_FRAMES)}


# ── clocks ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _now(now: Optional[datetime]) -> datetime:
    if now is None:
        return datetime.now(ET)
    return now.replace(tzinfo=ET) if now.tzinfo is None else now.astimezone(ET)


def _to_et(v) -> Optional[datetime]:
    """A stored stamp (datetime — naive = UTC, the Mongo read-back — or an ISO string) in ET; else None."""
    try:
        if isinstance(v, str) and v:
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            return (v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v).astimezone(ET)
    except Exception:                                          # noqa: BLE001
        return None
    return None


def _clock(v, now: datetime) -> Optional[str]:
    """"HH:MM" for a stamp of today (ET), "YYYY-MM-DD HH:MM" for an older one, None when unreadable."""
    et = _to_et(v)
    if et is None:
        return None
    return et.strftime("%H:%M") if et.date() == now.date() else et.strftime("%Y-%m-%d %H:%M")


def next_window_sec(now: datetime, in_window: bool) -> Optional[int]:
    """[C2.7] Out of window: seconds to the next pass open (GC.PASS_OPEN_ET) on a market day — today's when it is a
    market day still before the open, else `reaction.next_market_day`'s. In window: None."""
    if in_window:
        return None
    from catalysts.medical import reaction as RX
    open_t = dtime.fromisoformat(GC.PASS_OPEN_ET)
    today = now.date()
    day = today if (RX.is_market_day(today) and now.time() < open_t) else RX.next_market_day(today)
    return max(0, int((datetime.combine(day, open_t, tzinfo=ET) - now).total_seconds()))


def pass_block(doc, now: datetime, in_window: bool) -> Optional[dict]:
    if not isinstance(doc, dict):
        return None
    at = _to_et(doc.get("at"))
    at_et = _clock(doc.get("at"), now)
    if at is None or at_et is None:
        return None
    n_read, n_names = doc.get("n_read"), doc.get("n_names")
    if isinstance(n_read, int) and isinstance(n_names, int) and not isinstance(n_read, bool):
        text = PASS_TEXT.format(at_et=at_et, n_read=n_read, n_names=n_names)
    else:
        text = PASS_BARE_TEXT.format(at_et=at_et)
    reason = doc.get("reason")
    if isinstance(reason, str) and reason.strip() and reason.strip() != "ok":
        text = PASS_REASON_TEXT.format(text=text, reason=reason.strip())
    stale = bool(in_window and (now - at) > timedelta(seconds=GC.GG1M_STALE_AFTER_SEC))
    return {"at_et": at_et, "text": text, "stale": stale}


# ── rows ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _latest_up_t(blk) -> Optional[str]:
    """The stamp of the frame's latest drawn UP cross (the stored `ema_cross.crosses` — the diamonds on the chart)."""
    from chart_maps.gajjala import ema_cross as EX
    xs = blk.get("crosses") if isinstance(blk, dict) else None
    ups = [x for x in (xs if isinstance(xs, list) else []) if isinstance(x, dict) and x.get("dir") == EX.UP]
    t = ups[-1].get("t") if ups else None
    return t if isinstance(t, str) and t else None


def _held(blk, h) -> Optional[dict]:
    if not isinstance(h, dict):
        return None
    reason, bar_t = h.get("reason"), h.get("bar_t")
    if reason == HELD_PUSHED or not isinstance(bar_t, str) or bar_t != _latest_up_t(blk):
        return None
    text = held_text(reason)
    return {"text": text} if text else None


def _list(v) -> list:
    return list(v) if isinstance(v, (list, tuple)) else []


def frame_block(sym: str, tf: str, t: dict, held_doc) -> dict:
    blk = t.get("ema_cross") if isinstance(t.get("ema_cross"), dict) else None
    if blk is not None:
        blk = {k: v for k, v in blk.items() if not str(k).startswith("_")}       # `_marks` never served
    up = t.get("uptrend") if isinstance(t.get("uptrend"), dict) else {}
    return {"tf": tf, "label": t.get("label") or C.FRAME_WORDS.get(tf, tf),
            "tile": {"symbol": sym, "href": "", "bars": _list(t.get("bars")), "curves": _list(t.get("curves")),
                     "markers": _list(t.get("markers")), "lines": [], "bands": [], "stats": [], "why": "",
                     "vol_avg": t.get("vol_avg") if isinstance(t.get("vol_avg"), dict) else None},
            "axis": t.get("axis") if isinstance(t.get("axis"), dict) else None,
            "ema_cross": blk,
            "uptrend": {"ok": up.get("ok"), "short": up.get("short")},
            "held": _held(blk, (held_doc or {}).get(tf) if isinstance(held_doc, dict) else None)}


def status_text(status, sym: str, *, has_frames: bool, doc: dict, session: str, is_today: bool,
                now: datetime) -> Optional[str]:
    as_of = _clock(doc.get("loaded_at"), now) or "last"
    if status == "no_prints":
        return NO_PRINTS_TEXT[bool(is_today)].format(sym=sym, session=session)
    if status == "no_bars":
        return NO_BARS_TEXT.format(sym=sym, session=session)
    if status == "over_budget":
        return OVER_BUDGET_STALE_TEXT.format(as_of=as_of) if has_frames else OVER_BUDGET_TEXT
    if has_frames:
        return FAILED_STALE_TEXT.format(hhmm=_clock(doc.get("at"), now) or "last", as_of=as_of)
    return FAILED_TEXT


def _rang(claims: list, now: datetime) -> list:
    out = []
    for c in sorted(claims, key=lambda c: str(c.get("at") or "")):
        tf = c.get("frame")
        at_et = _clock(c.get("at"), now)
        words = C.FRAME_WORDS.get(tf, tf if isinstance(tf, str) else "")
        out.append({"frame": tf, "at_et": at_et,
                    "text": RANG_TEXT.format(frame=words, fast=GC.EMA_FAST, slow=GC.EMA_SLOW, at_et=at_et or "—")})
    return out


def row(sym: str, doc, *, session: str, is_today: bool, in_window: bool, now: datetime, claims: list) -> dict:
    out = {"symbol": sym, "state": "pending", "text": None, "from_session": None, "as_of_et": None, "stale": False,
           "frames": [], "rang": _rang(claims, now)}
    if not isinstance(doc, dict):
        out["text"] = PENDING_TEXT[bool(in_window)].format(sym=sym)
        return out
    status = doc.get("status")
    fr = doc.get("frames") if isinstance(doc.get("frames"), dict) else {}
    frames = [frame_block(sym, tf, fr[tf], doc.get("held")) for tf, _r in C.FRAMES if isinstance(fr.get(tf), dict)]
    kw = dict(doc=doc, session=session, is_today=is_today, now=now)
    if frames:
        dsess = doc.get("session")
        out.update(state="ok", frames=frames, as_of_et=_clock(doc.get("loaded_at"), now),
                   from_session=(dsess if isinstance(dsess, str) and dsess and dsess != session else None))
        if status != "loaded":
            out.update(stale=True, text=status_text(status, sym, has_frames=True, **kw))
        return out
    if status in (None, "loaded"):
        out["text"] = PENDING_TEXT[bool(in_window)].format(sym=sym)
        return out
    state = status if status in ROW_STATES else "failed"
    out.update(state=state, text=status_text(state, sym, has_frames=False, **kw))
    return out


# ── the payload ──────────────────────────────────────────────────────────────────────────────────────────────────
def _session_of(now: datetime) -> tuple:
    from chart_maps.gajjala import tab
    return tab.session_for(now)


def build(now: Optional[datetime] = None, db=None, only=None) -> dict:
    """The owner's board. `only` = the names to serve rows for (the pending poll); an unlisted name is dropped and
    never read. Never raises (state "error" + reason)."""
    now = _now(now)
    try:
        return _build(now, db, only)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("gajjala_watch: payload failed: %s", exc)
        return error_payload(type(exc).__name__)


def _build(now: datetime, db, only) -> dict:
    session, is_today, in_window = _session_of(now)
    siso = session.isoformat()[:10] if isinstance(session, (date, datetime)) else str(session)[:10]
    cs = CO.colls(db)
    symbols = CO.owner_symbols(db) if cs is not None else []
    if only is None:
        names = list(symbols)
    else:
        wanted = {s for s in only if isinstance(s, str)}
        names = [s for s in symbols if s in wanted]
    tiles, state_doc, claims = {}, None, []
    if cs is not None:
        if names:
            try:
                tiles = {d.get("_id"): d for d in cs["tiles"].find({"_id": {"$in": names}}) if isinstance(d, dict)}
            except Exception as exc:                           # noqa: BLE001
                log.warning("gajjala_watch: tile docs unreadable: %s", exc)
            try:
                claims = [d for d in cs["alerts"].find({"date": siso, "state": PUSHED_STATE}) if isinstance(d, dict)]
            except Exception as exc:                           # noqa: BLE001
                log.warning("gajjala_watch: claims unreadable: %s", exc)
        try:
            state_doc = cs["state"].find_one({"_id": C.STATE_LATEST_ID})
        except Exception as exc:                               # noqa: BLE001
            log.warning("gajjala_watch: state doc unreadable: %s", exc)
    rows = [row(s, tiles.get(s), session=siso, is_today=is_today, in_window=in_window, now=now,
                claims=[c for c in claims if c.get("symbol") == s and c.get("state") == PUSHED_STATE])
            for s in names]
    full = len(symbols) >= C.MAX_SYMBOLS
    out = {"state": "ok", "title": title(), "session": siso, "is_today": bool(is_today), "in_window": bool(in_window),
           "refresh_sec": GC.GG1M_CADENCE_SEC if in_window else 0,
           "next_window_sec": next_window_sec(now, bool(in_window)),
           "max_symbols": C.MAX_SYMBOLS, "symbols": list(symbols), "full": full,
           "full_text": full_text(), "add_label": ADD_LABEL, "add_placeholder": ADD_PLACEHOLDER,
           "remove_label": REMOVE_LABEL, "empty_text": empty_text(),
           "pass": pass_block(state_doc, now, bool(in_window)),
           "info": info(), "legend": legend(), "rows": rows}
    if any(r["state"] == "pending" for r in rows):
        out["pending_poll_sec"] = GC.ON_DEMAND_POLL_SEC
        out["pending_wait_max_sec"] = GC.ON_DEMAND_WAIT_MAX_SEC
    return out
