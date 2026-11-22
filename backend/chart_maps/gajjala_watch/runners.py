"""📅 ran last session + 📅 runs today — the ONE engine (2026-11-22, spec watch_org rev 4 §3.2, WP-BE).

Ajay 2026-11-22, verbatim: "Manual ones I add them need to be on top then auto intraday.. every month I want previous say
winners sorted and  remove hot sectors mess from Gajjalas top view I need a new thing there.. use that space between the
parent tab of Gajjala and watch tab to be for previous day runners but remove them if they don’t run the current day".
His answer the same day to "what counts as ran yesterday": "+40% vs prior close (Recommended)" — the 09:30–20:00 high is
at least +40% over the prior close and the day's peak was not premarket (his 11-21 winner rule). "every month" is read as
"every morning": the strip is rebuilt every session; nothing monthly exists here.

Reads STORED docs only (never a bar fetch, never a snapshot, nothing written):
  * the scan docs of a day (`gajjala_scan`, non-held — Gajjala's scanner universe) — ONE projected find
    (`tags._find_scan`, `C.RUNNERS_SCAN_FIELDS`);
  * the read docs of those names that day (`gajjala_reads`, `tile.bars5` + `ctx.float` + the pass stamp `at`) — ONE
    projected `_id $in` find (`tags._find_reads`, `C.RUNNERS_READ_FIELDS`);
  * from the cut (09:45 ET, built from `ET_RTH_OPEN` + GG's 15-minute rule) only: today's read docs of the same names —
    ONE more find; the broker list (ONE read) and the cached 🏆 index for the strip.

The 📅 rule (`ran_of`): the 5-minute bars are RIGHT-labelled (gajjala/bars.py: the bar stamped 10:05 holds 10:00–10:04),
so the peak minute is the bar's START. Every compare runs at `C.RAN_PCT_ROUND` places (the scanner's own rounding); a
number printed beside its bar is FLOORED (`pct_show`) — 24.96 never prints "+25.0%" beside "under +25%" [D5].

"Runs today" (`today_of`) is judged only on a FRESH read (the doc's pass stamp `at` within `C.RUNNERS_STALE_SEC`) that
already holds the 09:45 bar; anything else is `not_read` and KEPT [D6]. The count counts only names read as running [D4].
Stateless: a removed name comes back on the next GET once it prints +25%.

Display only: no gate, push, cap, eviction or add rule reads any of this. Descriptive — UNMEASURED.
`chart_maps.replays` is imported LAZILY (its constants import this package's constants — the cycle trap); a replays fault
serves no 🏆 and no peak bucket, never an empty strip.
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC

from . import constants as C

log = logging.getLogger("chart_maps.gajjala_watch.runners")
ET = ZoneInfo("America/New_York")


# ── handles (tests replace these) ────────────────────────────────────────────────────────────────────────────────
def _store():
    """The 🚩 five-minute tab's store — the same handle `tags._store` opens (tests replace this function)."""
    from chart_maps.gajjala import store as ST
    return ST.default()


def _replays():
    """(RS, RC) — `chart_maps.replays.store` / `.constants`, imported LAZILY; any fault → None + ONE log line."""
    try:
        from chart_maps.replays import constants as RC
        from chart_maps.replays import store as RS
        return RS, RC
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: replays unavailable: %s", type(exc).__name__)
        return None


def _tags():
    from . import tags as TG
    return TG


# ── numbers ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _fin(x) -> Optional[float]:
    """A finite float, else None (bool is not a number)."""
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _pos(x) -> Optional[float]:
    v = _fin(x)
    return v if v is not None and v > 0 else None


def _pct(hi: float, base: float) -> Optional[float]:
    v = _fin((hi / base - 1.0) * 100.0) if base else None
    return round(v, C.RAN_PCT_ROUND) if v is not None else None


def pct_show(x, places: int = C.PCT_SHOW_PLACES) -> Optional[str]:
    """f"{floor(x·10^p)/10^p:+.{p}f}%" on the RAN_PCT_ROUND-rounded value; non-finite → None. FLOOR, so a printed number
    never crosses its bar: 24.96 → "+24.9%", 25.0 → "+25.0%", 39.96 → "+39.9%", -3.45 → "-3.5%" [D5]. The scaled value is
    re-rounded to the places the RAN_PCT_ROUND rounding left before the floor, so float noise never drops a digit."""
    v = _fin(x)
    if v is None:
        return None
    p = max(0, int(places))
    v = round(v, C.RAN_PCT_ROUND)
    scale = 10 ** p
    f = math.floor(round(v * scale, max(0, C.RAN_PCT_ROUND - p))) / scale
    if f == 0:
        f = 0.0                                                 # never "-0.0%"
    return f"{f:+.{p}f}%"


def _run_text(run_pct: float) -> str:
    """The chip's whole-percent word — used ONLY where the number is ≥ RAN_MIN_PCT (a counted run), see RAN_TEXT."""
    return f"{run_pct:+.0f}%"


# ── clocks ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _hhmm(t) -> str:
    return t.strftime("%H:%M")


def clock_words() -> dict:
    """{open, end, cut, stale_min} — every time the copy prints, BUILT (never typed): daytrading.data ET_RTH_OPEN /
    ET_AFTERHOURS_CLOSE, potential._mute_end_hhmm (09:30 + GG's 15-minute rule), C.RUNNERS_STALE_SEC in minutes."""
    from chart_maps.gajjala import potential as PT
    from daytrading.data import ET_AFTERHOURS_CLOSE, ET_RTH_OPEN
    return {"open": _hhmm(ET_RTH_OPEN), "end": _hhmm(ET_AFTERHOURS_CLOSE), "cut": PT._mute_end_hhmm(),
            "stale_min": C.RUNNERS_STALE_SEC // 60}


def _prev_market_day(d: date) -> date:
    from chart_maps.gajjala import tab
    return tab._prev_market_day(d)


def runner_day(now: datetime) -> tuple:
    """(day, today, live) for the STRIP. In the pass window of a market day: (the market day before today, today, True);
    otherwise (after the pass close, before the first pass, a closed day): (the last completed session, None, False) —
    that session's runners, nothing cut."""
    from chart_maps.gajjala import tab
    session, is_today, in_window = tab.session_for(now)
    if is_today and in_window:
        return _prev_market_day(session), session, True
    return session, None, False


def cut_at(today: date) -> datetime:
    """ET_RTH_OPEN + GC.NO_TRADE_AFTER_OPEN_MIN on `today`, tz ET — THE potential._mute_end (reused, never retyped)."""
    from chart_maps.gajjala import potential as PT
    return PT._mute_end(today)


def _utc(v) -> Optional[datetime]:
    """A stored pass stamp as aware UTC: a datetime (Mongo hands back naive UTC) or an ISO string; else None."""
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v.strip())
        except ValueError:
            return None
    if not isinstance(v, datetime):
        return None
    return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)


def _now_utc(now: datetime) -> datetime:
    return now.replace(tzinfo=ET).astimezone(timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)


def _md(d: date) -> str:
    return d.strftime("%m-%d")


def _dayword(d: date) -> str:
    return d.strftime("%a")


# ── bars ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _tod(b: dict) -> str:
    return b["t"][11:16]


def bars_of(read_doc, day_iso: str) -> list:
    """`tile.bars5` of `day_iso` — dict bars whose `t` is "YYYY-MM-DD HH:MM" on that date with finite o/h/l/c > 0, in
    time order; anything else (no doc, junk, another date) → dropped / []."""
    tile = read_doc.get("tile") if isinstance(read_doc, dict) else None
    raw = tile.get("bars5") if isinstance(tile, dict) else None
    if not isinstance(raw, list):
        return []
    out = []
    for b in raw:
        if not isinstance(b, dict):
            continue
        t = b.get("t")
        if not isinstance(t, str) or len(t) < 16 or not t.startswith(day_iso + " "):
            continue
        if any(_pos(b.get(k)) is None for k in ("o", "h", "l", "c")):
            continue
        out.append(b)
    out.sort(key=lambda b: b["t"])
    return out


def _ext(bars: list) -> list:
    """The 09:30–20:00 bars: `s` absent (regular) or after hours."""
    return [b for b in bars if b.get("s") is None or b.get("s") == C.BAR_AH]


def _bar_start(b: dict) -> str:
    t = datetime.strptime(b["t"][:16], "%Y-%m-%d %H:%M") - timedelta(minutes=C.BAR_MIN)
    return t.strftime("%H:%M")


def _last(scan_doc) -> dict:
    last = scan_doc.get("last") if isinstance(scan_doc, dict) else None
    return last if isinstance(last, dict) else {}


def basis_of(scan_doc, bars: list) -> Optional[float]:
    """Last session's REGULAR close: the scan doc's frozen `last.day_c` once its tape says after hours (Massive freezes the
    day bar at the close), else the close of the LAST regular bar (`s` absent) of `bars`, else None."""
    last = _last(scan_doc)
    dc = _pos(last.get("day_c"))
    if dc is not None and last.get("tape_session") == C.SCAN_SESSION_AFTER:
        return dc
    reg = [b for b in bars if isinstance(b, dict) and b.get("s") is None and _pos(b.get("c")) is not None]
    return _pos(reg[-1]["c"]) if reg else None


# ── the 📅 rule ─────────────────────────────────────────────────────────────────────────────────────────────────
def _timing(peak_et: str) -> tuple:
    rr = _replays()
    if rr is None:
        return None, None
    RS, RC = rr
    try:
        b = RS.bucket_of(peak_et)
        return b, (RC.WIN_TIMING_WORDS.get(b) if b else None)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: peak bucket unavailable: %s", type(exc).__name__)
        return None, None


def ran_of(scan_doc, read_doc, day: date) -> Optional[dict]:
    """Did the name RUN on `day` (his 11-22 answer)? None when the prior close or the 09:30–20:00 bars are missing.
    Keys: {date, day, prev_close, high, run_pct, peak_et, timing, timing_text, pm_high_pct, premarket_peak, counts,
    reg_close, text, title}."""
    pc = _pos(_last(scan_doc).get("prev_close"))
    if pc is None:
        return None
    day_iso = day.isoformat()
    bars = bars_of(read_doc, day_iso)
    ext = _ext(bars)
    if not ext:
        return None
    pre = [b for b in bars if b.get("s") == C.BAR_PRE]
    hi = max(float(b["h"]) for b in ext)
    pk = next(b for b in ext if float(b["h"]) == hi)              # the FIRST bar printing the high
    peak_et = _bar_start(pk)
    pm_hi = max((float(b["h"]) for b in pre), default=None)
    run_pct = _pct(hi, pc)
    pm_pct = _pct(pm_hi, pc) if pm_hi is not None else None
    if run_pct is None:
        return None
    premarket_peak = pm_hi is not None and pm_hi > hi             # STRICT: a tie is not a premarket peak (AKAN 11-20)
    counts = run_pct >= C.RAN_MIN_PCT and not premarket_peak
    timing, timing_text = _timing(peak_et)
    w = clock_words()
    dword = _dayword(day)
    date_word = f"{dword} {_md(day)}"
    pct_s = pct_show(run_pct)
    pm_s = pct_show(pm_pct) if pm_pct is not None else C.RAN_NONE
    text = None
    if counts:
        text = (C.RAN_TEXT.format(day=dword, pct=_run_text(run_pct), timing=timing_text) if timing_text
                else C.RAN_TEXT_NO_TIMING.format(day=dword, pct=_run_text(run_pct)))
    if counts:
        title = C.RAN_TITLE.format(date=date_word, open=w["open"], end=w["end"], high=f"{hi:g}", pct=pct_s,
                                   pc=f"{pc:g}", at=peak_et, pm=pm_s, bar=C.RAN_MIN_PCT)
    elif premarket_peak:
        title = C.RAN_PM_PEAK_TITLE.format(date=date_word, pm=pm_s, open=w["open"], end=w["end"], pct=pct_s)
    else:
        title = C.RAN_UNDER_TITLE.format(date=date_word, open=w["open"], end=w["end"], pct=pct_s, bar=C.RAN_MIN_PCT)
    return {"date": day_iso, "day": dword, "prev_close": pc, "high": _fin(hi), "run_pct": run_pct, "peak_et": peak_et,
            "timing": timing, "timing_text": timing_text, "pm_high_pct": pm_pct, "premarket_peak": premarket_peak,
            "counts": counts, "reg_close": basis_of(scan_doc, bars), "text": text,
            "title": title + " — " + C.ORG_NOTE}


# ── "runs today" ────────────────────────────────────────────────────────────────────────────────────────────────
def today_of(read_doc, today: date, basis: Optional[float], cut: datetime, now: datetime) -> dict:
    """{state, today_pct, at_et, text} — `running` / `not_running` only on a FRESH read (pass stamp `at` within
    C.RUNNERS_STALE_SEC of `now`) that holds a bar ending at/after `cut`; otherwise `not_read` (kept) [D4, D5, D6]."""
    at = _utc(read_doc.get("at")) if isinstance(read_doc, dict) else None
    at_et = _hhmm(at.astimezone(ET)) if at is not None else None
    w = clock_words()
    not_read = {"state": C.TODAY_STATES[2], "today_pct": None, "at_et": at_et, "text": C.RUNNERS_NOT_READ_TEXT}
    if basis is None or not isinstance(read_doc, dict) or at is None:
        return not_read
    if at < _now_utc(now) - timedelta(seconds=C.RUNNERS_STALE_SEC):
        return not_read
    tb = _ext(bars_of(read_doc, today.isoformat()))
    cut_hhmm = _hhmm(cut.astimezone(ET)) if cut.tzinfo is not None else _hhmm(cut)
    if not any(_tod(b) >= cut_hhmm for b in tb):
        return not_read                                          # the 09:45 bar is not on file yet (a late pass)
    pct = _pct(max(float(b["h"]) for b in tb), basis)
    if pct is None:
        return not_read
    state = C.TODAY_STATES[0] if pct >= C.RUNNERS_LEAVE_PCT else C.TODAY_STATES[1]
    return {"state": state, "today_pct": pct, "at_et": at_et,
            "text": C.RUNNERS_TODAY_TEXT.format(pct=pct_show(pct), open=w["open"])}


# ── reads ───────────────────────────────────────────────────────────────────────────────────────────────────────
def read_day(st, day_iso: str, names: Optional[list] = None) -> tuple:
    """(scan_by {SYM: doc}, reads_by {SYM: doc}) — ONE scan find of `day_iso` (names None = every non-held doc of the
    day) + ONE reads find over the scan names only (none → no reads find). RAISES on a fault."""
    from chart_maps.gajjala import store as ST
    TG = _tags()
    scan = TG._find_scan(st, [day_iso], None if names is None else list(names), fields=C.RUNNERS_SCAN_FIELDS)
    scan_by: dict = {}
    for d in scan:
        s = d.get("symbol")
        if isinstance(s, str) and s.strip() and d.get("date") in (None, day_iso):
            scan_by.setdefault(s.upper(), d)
    if not scan_by:
        return {}, {}
    reads = TG._find_reads(st, [ST.key(day_iso, s) for s in scan_by], fields=C.RUNNERS_READ_FIELDS)
    return scan_by, reads


def read_today(st, today_iso: str, names: list) -> dict:
    """{SYM: today's read doc} — ONE projected find; no names → {} (no find). RAISES on a fault."""
    if not names:
        return {}
    from chart_maps.gajjala import store as ST
    return _tags()._find_reads(st, [ST.key(today_iso, s) for s in names], fields=C.RUNNERS_READ_FIELDS)


def ran_for(names: list, day: date, *, st=None) -> dict:
    """The Watch's 📅 read: {FOLDED SYM: ran dict} for `names` on `day` — 1 scan find + 1 reads find (0 with no names).
    Both class spellings are asked for (BRK.B and BRK-B) and the result is keyed by `CO.fold`, so a row spelled either
    way finds a scan doc stored either way. RAISES on a fault (the caller serves no chip)."""
    from . import colls as CO
    want: list = []
    for n in names:
        if isinstance(n, str) and n.strip():
            h = CO.house(n)
            for v in (h, h.replace(".", "-")):
                if v not in want:
                    want.append(v)
    if not want:
        return {}
    st = st if st is not None else _store()
    scan_by, reads_by = read_day(st, day.isoformat(), want)
    out: dict = {}
    for sym, doc in scan_by.items():
        r = ran_of(doc, reads_by.get(sym), day)
        if r is not None:
            out[CO.fold(sym)] = r
    return out


# ── the strip ───────────────────────────────────────────────────────────────────────────────────────────────────
def _past(idx, RS, sym: str, day_iso: str) -> tuple:
    """(text, title) of the 🏆 wins that ENDED strictly before the run day — the chip prints the newest with the
    strip's short prefix, the title every served item with 🎬's own words; none / a fault → (None, None)."""
    if idx is None or RS is None:
        return None, None
    try:
        short = RS.past_wins_before(idx, sym, day_iso, C.RUNNERS_PAST_WORDS)
        if not short or not short.get("past_winner"):
            return None, None
        from chart_maps.replays import constants as RC
        full = RS.past_wins_before(idx, sym, day_iso, RC.PAST_WIN_DAY_WORDS) or {}
        items = [w.get("text") for w in full.get("past_winner") or [] if isinstance(w, dict) and w.get("text")]
        more = full.get("past_winner_more_text")
        title = " · ".join(items + ([more] if more else [])) or None
        return short["past_winner"][0].get("text"), title
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: past winners unavailable: %s", type(exc).__name__)
        return None, None


def _float_of(today_doc, last_doc, now) -> tuple:
    from chart_maps.gajjala import tab
    chip = None
    for d in (today_doc, last_doc):
        if isinstance(d, dict):
            chip = tab._float_chip(tab._float_read(d, None))
            if chip is not None:
                break
    if chip is None:
        return None, None
    try:
        from . import float_read as FR
        title = FR.title(chip, now)
    except Exception:                                           # noqa: BLE001 — the chip stands without its title
        title = None
    return chip.get("text"), title


def _broker_flags(st):
    """The 🚫 list — ONE read; a fault (or the seed fallback) → None: no name is tagged, nobody is hidden."""
    try:
        from chart_maps.gajjala import store as ST
        flags, fault = ST.broker_flags(st)
        return None if fault else flags
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: broker list unavailable: %s", type(exc).__name__)
        return None


def _head(day: date, w: dict) -> dict:
    return {"title": C.RUNNERS_TITLE.format(day=_dayword(day), md=_md(day)),
            "hint": C.RUNNERS_HINT.format(day=_dayword(day), open=w["open"], end=w["end"], bar=C.RAN_MIN_PCT,
                                          cut=w["cut"], leave=C.RUNNERS_LEAVE_PCT, stale_min=w["stale_min"])}


def strip(now: datetime, *, st=None, past=None, broker=None) -> dict:
    """The 📅 strip payload (spec §3.4). `past` = a ready 🏆 index (tests), `broker` = a ready flag list (tests); else
    each is read once. Never raises on a store fault (state "error" + the served sentence)."""
    if not C.RUNNERS_STRIP_ON:
        return {"state": C.RUNNERS_STATES[3]}
    from chart_maps.gajjala import tab
    w = clock_words()
    day, today, live = runner_day(now)
    day_iso = day.isoformat()
    head = _head(day, w)
    st = st if st is not None else _store()
    try:
        scan_by, reads_by = read_day(st, day_iso)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: runners unreadable: %s", type(exc).__name__)
        return {"state": C.RUNNERS_STATES[2], "text": C.RUNNERS_ERROR_TEXT, "day": day_iso, **head}
    ran: dict = {}
    no_bars = 0
    for sym, doc in scan_by.items():
        rd = reads_by.get(sym)
        if not _ext(bars_of(rd, day_iso)):
            no_bars += 1
            continue
        r = ran_of(doc, rd, day)
        if r is not None and r["counts"]:
            ran[sym] = r
    cut_dt = cut_at(today) if today is not None else None
    now_et = now.astimezone(ET) if now.tzinfo is not None else now.replace(tzinfo=ET)
    cut_active = bool(live and cut_dt is not None and now_et >= cut_dt)
    today_by: dict = {}
    today_ok = True
    if cut_active and ran:
        try:
            today_by = read_today(st, today.isoformat(), list(ran))
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala_watch: today's runner reads unavailable: %s", type(exc).__name__)
            today_by, today_ok = {}, False
    flags = broker if broker is not None else (_broker_flags(st) if ran else None)
    idx, RS = None, None
    if ran:
        rr = _replays()
        if rr is not None:
            RS = rr[0]
            try:
                idx = past if past is not None else RS._past_index(RS.root_dir())
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala_watch: past-winner index unavailable: %s", type(exc).__name__)
                idx = None
    rows, removed = [], []
    n_running = n_not_read = 0
    newest_at = None
    for sym, r in ran.items():
        tdoc = today_by.get(sym) if today_ok else None
        td = None
        if cut_active:
            td = today_of(tdoc, today, r["reg_close"], cut_dt, now)
            at = _utc(tdoc.get("at")) if isinstance(tdoc, dict) else None
            if at is not None and (newest_at is None or at > newest_at):
                newest_at = at
        ftext, ftitle = _float_of(tdoc if cut_active else None, reads_by.get(sym), now)
        ptext, ptitle = _past(idx, RS, sym, day_iso)
        btext = tab.broker_text_for(sym, flags)
        run_text = _run_text(r["run_pct"])
        if td is not None and td["state"] == C.TODAY_STATES[1]:
            removed.append({"symbol": sym, "run_text": run_text, "today_pct": td["today_pct"], "text": td["text"],
                            "_k": (btext is not None, -r["run_pct"], sym)})
            continue
        if td is not None:
            if td["state"] == C.TODAY_STATES[0]:
                n_running += 1
            else:
                n_not_read += 1
        rows.append({"symbol": sym, "run_pct": r["run_pct"], "run_text": run_text, "timing": r["timing"],
                     "timing_text": r["timing_text"], "peak_et": r["peak_et"], "float_text": ftext,
                     "float_title": ftitle, "past_winner_text": ptext, "past_winner_title": ptitle,
                     "broker_text": btext, "today_state": td["state"] if td else None,
                     "today_pct": td["today_pct"] if td else None, "today_text": td["text"] if td else None,
                     "title": r["title"] + (" · " + td["text"] if td else ""),
                     "_k": (btext is not None, -r["run_pct"], sym)})
    rows.sort(key=lambda x: x["_k"])
    removed.sort(key=lambda x: x["_k"])
    for x in rows + removed:
        x.pop("_k", None)
    n = len(rows) + len(removed)
    as_of_et = _hhmm(newest_at.astimezone(ET)) if newest_at is not None else None
    stale = bool(cut_active and (newest_at is None
                                 or newest_at < _now_utc(now) - timedelta(seconds=C.RUNNERS_STALE_SEC)))
    if n == 0:
        text = C.RUNNERS_EMPTY_TEXT.format(day=_dayword(day), bar=C.RAN_MIN_PCT, open=w["open"], end=w["end"])
    elif cut_active:
        text = C.RUNNERS_COUNT_CUT.format(k=n_running, n=n)
        if n_not_read > 0:
            text += C.RUNNERS_COUNT_NOT_READ.format(u=n_not_read)
        if stale:
            text += C.RUNNERS_STALE_TEXT.format(at=as_of_et or "—")
    else:
        text = C.RUNNERS_COUNT_ALL.format(n=n)
    return {"state": C.RUNNERS_STATES[0] if n else C.RUNNERS_STATES[1], **head, "text": text,
            "day": day_iso, "day_word": _dayword(day), "today": today.isoformat() if today else None, "live": live,
            "cut_active": cut_active, "cut_at": w["cut"], "refresh_sec": GC.PASS_CADENCE_SEC if live else 0,
            "fold_at": C.RUNNERS_FOLD_AT, "fold_at_phone": C.RUNNERS_FOLD_AT_PHONE, "more_text": C.RUNNERS_MORE_TEXT,
            "less_text": C.RUNNERS_LESS_TEXT, "n": n, "n_running": n_running, "n_not_read": n_not_read,
            "no_bars": no_bars, "as_of_et": as_of_et if cut_active else None, "stale": stale, "rows": rows,
            "removed": removed,
            "removed_text": (C.RUNNERS_REMOVED_TEXT.format(n=len(removed), leave=C.RUNNERS_LEAVE_PCT, open=w["open"])
                             if removed else None)}


def rules_line() -> str:
    """The ℹ️ clause — every number and time from the constants / the house clock at CALL time (never typed here)."""
    w = clock_words()
    return (f"📅 Previous day runners (owner only, display only): a name on Gajjala's scanner last session whose "
            f"{w['open']}–{w['end']} ET high reached +{C.RAN_MIN_PCT:g}% or more over the prior close with the day's "
            f"peak not premarket, biggest gain first, 🚫 names last (never dropped); from {w['cut']} ET a name leaves "
            f"while today's high since {w['open']} ET is under +{C.RUNNERS_LEAVE_PCT:g}% vs its last-session close and "
            f"comes back when it gets there — never on a read older than {w['stale_min']} minutes; 👀 Watch tiles carry "
            f"the same 📅 label, and the Watch is grouped "
            + ", then ".join(C.SECTION_WORDS[k] for k in C.SECTION_ORDER)
            + ". Descriptive — UNMEASURED; no gate, push or add rule reads it.")
