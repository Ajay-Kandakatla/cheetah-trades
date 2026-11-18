"""🧨 Divergence sub on 🚩 Gajjala's 5-minute tab — the served words, cards and 🏁 fold (2026-11-18, SPEC §3.7, WP-B).

Ajay 2026-11-18, verbatim: "Do we still capture divergence alerts? Can you add a tab for in in Gajjals 5 min please" ·
"yes should do a track recird fir the divergence aftger EMA 9 Cross over bullish / Cuz I am missing A+ i can chase the
divergency atleast like in these cases / I would caught a good chunk of returns".

A DISPLAY + RECORD of the 11-16 study's REGISTERED pick (eod-audits/research/2026-11-16_explosive_divergence/OOS_SPEC.md,
sha GC.DIVERGENCE_OOS_SPEC_SHA256). No push, no gate, no rule, no trade. The record itself is written by
chart_maps.gajjala.divergence (the pass hook + the 20:15 nightly); this module only READS `gajjala_divergence` (store
divergence_docs / divergence_dates) and the pass's stored reads, and serves words. Every number in a served sentence is
a GC.DIVERGENCE_* value (or the EMA / session constants), formatted here — never retyped.

`block` = three independently fenced parts (SPEC [C7]): (a) the panel words — pure over GC + the doc list; (b) the cards —
EACH record in its own try (a missing reads doc / an empty tile → `chartless`; a malformed tile or a raising build →
`chartless` + `faults`, never a tile); (c) the 🏁 fold in its own try (→ `track_record` None +
`track_record_fault_text`). Only the board session's doc read failing blanks the block (None → tab serves FAULT_TEXT).
Totals over rows dated on an OOS session stay SEALED until GC.DIVERGENCE_OOS_SEAL_ET (SPEC [C2]); every row always
carries its own grade cells. UNMEASURED live; in-sample the rule did not make money.
"""
from __future__ import annotations

import logging
import statistics
from datetime import date, datetime, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ema_cross as EX
from chart_maps.gajjala import variant as V

log = logging.getLogger("chart_maps.gajjala.divergence_tab")

ET = ZoneInfo("America/New_York")

FAULT_TEXT = "🧨 The divergence record could not be read this time — the next re-read tries again."
TITLE = ("🧨 Divergence — the 9 EMA far over the 21 EMA on a closed 5-min bar, volume rising · a RECORD, not a signal · "
         "UNMEASURED")
ASK_TEXT = ("Ajay 2026-11-18: “yes should do a track recird fir the divergence aftger EMA 9 Cross over bullish” · "
            "“Cuz I am missing A+ i can chase the divergency atleast like in these cases” · "
            "“I would caught a good chunk of returns”")
RULE_LABEL = "ⓘ what gets listed and how it is graded"
COHORT_TEXT = "Names read: today's 🚩 A+ and 🧠 pushes on this tab (the study's cohort), from their ring onward."
WINDOW_TEXT = {"rth": "reading closed bars", "afterhours": "reading closed bars",
               "premarket": "pre-market — nothing lists before {rth_lo} ET",
               "closed": "closed — the listings of the last session"}
ORDER_NOTE = "🧨 open first (no 9/21 down-cross yet), newest listing on top · then exited"
EMPTY_TODAY = "No name met the rule on its closed bars yet today."
EMPTY_SESSION = "No name met the rule on the {label} session."
CHARTLESS_TEXT = "🧨 {sym} listed {hhmm} ET · chart not stored"
FAULTS_TEXT = "{n} listing(s) could not draw a card — the record still holds them"
TRACK_RECORD_FAULT_TEXT = "🏁 The record fold could not be built this time — the cards above stand."
TR_TITLE = "🏁 Divergence record — every 🧨 listing, graded by the study's exit · net of costs · UNMEASURED"
TR_RULE_LABEL = "ⓘ how each listing is graded"
TR_HEADS = (("symbol", "Ticker"), ("window", "Window"), ("at", "Listed"), ("ring", "Rang"), ("entry", "Entry"),
            ("exit", "Exit"), ("gross", "Gross %"), ("net", "Net %"))
TR_TODAY_TEXT = "Today · listings grade tonight {at} ET; the card shows the live read until then"
TR_EMPTY = {"today": "No 🧨 listing yet this session.", "yesterday": "No 🧨 listing on {day}."}
TR_EMPTY_SPAN = "No 🧨 listing on this span."
WINDOW_WORDS = {"rth": "RTH", "ah": "after hours"}
RING_TEXT = {"aplus": "🎯 A+ {at} ET", "potential": "🧠 potential {at} ET"}
REASON_TEXT = {"downcross": "9/21 down-cross", "close": "the {close} mark"}
OOS_TEXT_ROW = "OOS session"
HALF_DAY_TEXT = "half day · outside the registered read"
DUP_SETUP = "🧨"
DASH = "—"
STATE_OPEN, STATE_EXITED, STATE_NO_PRINT = "open", "exited", "no_print"
GRADED_OUTCOMES = ("win", "loss", "flat")               # a graded trade with a fill (divergence.trade outcome words)
COUNT_WINDOWS = ("rth", "ah")
MINUS = "−"                                        # the served minus sign of the in-sample lines (SPEC §3.7)


# ── formatting (every float through ema_cross.finite; None → "—") ─────────────────────────────────────────────────
def _f(x) -> Optional[float]:
    try:
        return EX.finite(x)
    except Exception:                                   # noqa: BLE001 — a junk value is "unknown", never a raise
        return None


def _sgn(x, nd: int = 2) -> str:
    """Signed with the typographic minus (the IS lines): +1.06 / −6.73; unknown → "—"."""
    v = _f(x)
    if v is None:
        return DASH
    return (MINUS if v < 0 else "+") + f"{abs(v):.{nd}f}"


def _pct_signed(x) -> str:
    """The fold / card percent: "+x.xx%" (ASCII sign — the counts_text regex reads it); unknown → "—"."""
    v = _f(x)
    return DASH if v is None else f"{v:+.2f}%"


def _num(x, fmt: str) -> str:
    v = _f(x)
    return DASH if v is None else format(v, fmt)


def _px(x) -> str:
    from chart_maps.gajjala import tab as GT            # lazy — tab imports this module inside its branch
    return GT._px(x) if _f(x) is not None else DASH


def _hhmm(t) -> Optional[str]:
    return t[11:16] if isinstance(t, str) and len(t) >= 16 else None


def _vol(x) -> str:
    from chart_maps.gajjala import tab as GT
    v = _f(x)
    return (GT._compact(v) or DASH) if v is not None else DASH


def _hm(t) -> str:
    return t.strftime("%H:%M")


def _windows() -> dict:
    return {k: (lo, hi) for k, lo, hi in GC.DIVERGENCE_WINDOWS}


def _closes(session_iso: str) -> tuple:
    from chart_maps.gajjala import alerts as AL         # the ONE session-close table (half days)
    return AL._closes(session_iso)


def _seal_utc() -> datetime:
    return datetime.strptime(GC.DIVERGENCE_OOS_SEAL_ET, "%Y-%m-%d %H:%M").replace(tzinfo=ET).astimezone(timezone.utc)


def _aware(now: datetime) -> datetime:
    return now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)


def oos_sealed(now: datetime) -> bool:
    """True while `now` is before GC.DIVERGENCE_OOS_SEAL_ET (ET) — totals over OOS-session rows are withheld."""
    return _aware(now) < _seal_utc()


def oos_done_n(now: datetime) -> int:
    """OOS sessions whose extended close has passed — a COUNT, never a read."""
    n = 0
    for s in GC.DIVERGENCE_OOS_SESSIONS:
        _rth, ext = _closes(s)
        if datetime.combine(date.fromisoformat(s), ext, tzinfo=ET) <= _aware(now):
            n += 1
    return n


# ── the panel words (pure over GC — part (a), cannot raise on the records) ───────────────────────────────────────
def rule_text() -> str:
    w = _windows()
    (rth_lo, rth_hi), (ah_lo, ah_hi) = w["rth"], w["ah"]
    return ("Listed when a closed 5-minute bar between %s and %s ET (or %s–%s after hours; never pre-market) is the "
            "first of the session with the %d EMA at least %.3f ATRs (%d-bar ATR) over the %d EMA, after the name rang a "
            "🚩 A+ or 🧠 push on this tab, and its last %d bars' volume is rising with their mean at or above the %d bars "
            "before. Entry = the next 5-minute bar's open. Exit = the close of the first 5-minute bar whose %d EMA "
            "crosses back under the %d, else the regular-close mark (the %s mark for an after-hours listing). Net %% = "
            "gross minus %s and $%.2f a share, each side — the study's costs. One listing per stock per session."
            % (rth_lo, rth_hi, ah_lo, ah_hi, GC.EMA_FAST, GC.DIVERGENCE_R1_LEVEL, GC.DIVERGENCE_ATR_PERIOD,
               GC.EMA_SLOW, GC.DIVERGENCE_V2_RUN, GC.DIVERGENCE_V2_HOUR_BARS, GC.EMA_FAST, GC.EMA_SLOW,
               _ah_mark(), format(GC.DIVERGENCE_COST_BPS, ".2%"), GC.DIVERGENCE_SLIP_USD))


def _ah_mark() -> str:
    from daytrading.data import ET_AFTERHOURS_CLOSE
    return _hm(ET_AFTERHOURS_CLOSE)


def honesty() -> str:
    is_from, is_to, n_sessions = GC.DIVERGENCE_IS_WINDOW
    return ("The 11-16 study measured this exact rule on %d sessions (%s → %s): it did not make money and was not shown "
            "better than listed names we never rang. This sub records what the rule would have done — no alert, no "
            "gate, no trade. Small numbers mean nothing; read the net %% beside the win rate, never the win rate alone."
            % (n_sessions, is_from, is_to))


def is_lines() -> dict:
    r, a = dict(GC.DIVERGENCE_IS["rth"]), dict(GC.DIVERGENCE_IS["ah"])
    rth = ("In-sample RTH, %d trades: %s%% net per trade [%s, %s] · won %s%% · median %s%% · exits %d down-cross / %d "
           "at the mark · %d fills under $1 · %s (vs listed names %s [%s, %s], %s)"
           % (r["trades"], _sgn(r["mean_net"]), _sgn(r["lo"]), _sgn(r["hi"]), _num(r["win_pct"], ".1f"),
              _sgn(r["median_net"]), r["exit_downcross"], r["exit_close"], r["lt1_trades"], r["word"],
              _sgn(r["vs_listed_mean"]), _sgn(r["vs_listed_lo"]), _sgn(r["vs_listed_hi"]), r["vs_listed_word"]))
    ah = ("In-sample after hours, %d trades: %s%% [%s, %s] · won %s%% · %s — description only, not the registered line"
          % (a["trades"], _sgn(a["mean_net"]), _sgn(a["lo"]), _sgn(a["hi"]), _num(a["win_pct"], ".1f"), a["word"]))
    return {"rth": dict(r, text=rth), "ah": dict(a, text=ah)}


def oos_text() -> str:
    ss = GC.DIVERGENCE_OOS_SESSIONS
    return ("Out of sample, registered before any read: %s → %s (%d sessions; OOS_SPEC sha %s…) — this record's first "
            "two weeks. Each listing's grade shows as it lands; totals over these sessions stay sealed on this tab until "
            "%s ET, when the registered read is taken ONCE. This tab is NOT that read. Eight sessions cannot ship "
            "anything." % (ss[0], ss[-1], len(ss), GC.DIVERGENCE_OOS_SPEC_SHA256[:8], GC.DIVERGENCE_OOS_SEAL_ET))


def window_text(sess: dict) -> str:
    tape = (sess or {}).get("tape")
    t = WINDOW_TEXT.get(tape, WINDOW_TEXT["closed"])
    return t.format(rth_lo=_windows()["rth"][0])


# ── one record's facts ──────────────────────────────────────────────────────────────────────────────────────────
def _grade(doc: dict) -> Optional[dict]:
    """The stored grade when it is of the current GC.DIVERGENCE_GRADE_VERSION (an older one waits for its re-grade)."""
    g = doc.get("grade")
    if isinstance(g, dict) and g.get("version") == GC.DIVERGENCE_GRADE_VERSION and g.get("outcome"):
        return g
    return None


def _alert(doc: dict) -> dict:
    a = doc.get("alert")
    return a if isinstance(a, dict) else {}


def _bar_t(doc: dict) -> str:
    t = _alert(doc).get("bar_t")
    return t if isinstance(t, str) else ""


def _sym(doc: dict) -> str:
    return str(doc.get("symbol") or "").upper()


def _state(doc: dict) -> str:
    """open | exited | no_print — a graded record's words win over the live block."""
    g = _grade(doc)
    if g is not None:
        return STATE_NO_PRINT if g.get("outcome") == STATE_NO_PRINT else STATE_EXITED
    live = doc.get("live") if isinstance(doc.get("live"), dict) else {}
    s = live.get("state")
    return s if s in (STATE_OPEN, STATE_EXITED, STATE_NO_PRINT) else STATE_OPEN


def _entry(doc: dict) -> Optional[dict]:
    g = _grade(doc)
    src = g if g is not None else (doc.get("live") if isinstance(doc.get("live"), dict) else {})
    e = src.get("entry")
    return e if isinstance(e, dict) and _f(e.get("px")) is not None else None


def _exit(doc: dict) -> Optional[dict]:
    g = _grade(doc)
    src = g if g is not None else (doc.get("live") if isinstance(doc.get("live"), dict) else {})
    x = src.get("exit")
    return x if isinstance(x, dict) and _f(x.get("px")) is not None else None


def _net(doc: dict) -> Optional[float]:
    g = _grade(doc)
    if g is not None:
        return _f(g.get("net_pct"))
    live = doc.get("live") if isinstance(doc.get("live"), dict) else {}
    return _f(live.get("net_pct_now"))


def _reason_word(x: Optional[dict], doc: dict) -> str:
    reason = (x or {}).get("reason")
    if reason == "downcross":
        return REASON_TEXT["downcross"]
    return REASON_TEXT["close"].format(close=_close_mark(doc))


def _close_mark(doc: dict) -> str:
    """The horizon stamp of the record's window: the regular close (half days per alerts._closes), the extended
    close for an after-hours listing."""
    try:
        rth, ext = _closes(str(doc.get("date")))
    except Exception:                                   # noqa: BLE001
        return DASH
    return _hm(ext if doc.get("window") == "ah" else rth)


def state_label(doc: dict) -> str:
    at = _hhmm(_bar_t(doc)) or DASH
    s = _state(doc)
    if s == STATE_NO_PRINT:
        return "🧨 listed %s ET · no print after the listing" % at
    if s == STATE_EXITED:
        x = _exit(doc)
        return "🧨 listed %s ET · exited %s ET (%s) · %s net" % (at, _hhmm((x or {}).get("t")) or DASH,
                                                              _reason_word(x, doc), _pct_signed(_net(doc)))
    return "🧨 listed %s ET · open — no 9/21 down-cross yet" % at


def plan_text(doc: dict) -> str:
    e = _entry(doc)
    if e is None:
        return "entry = the next 5-minute bar's open (not printed yet)"
    live = doc.get("live") if isinstance(doc.get("live"), dict) else {}
    return ("entry %s (next bar's open, %s ET) · exit = first 5-min %d/%d down-cross close, else the %s mark · gap now "
            "%s ATRs" % (_px(e.get("px")), _hhmm(e.get("t")) or DASH, GC.EMA_FAST, GC.EMA_SLOW, _close_mark(doc),
                         _num(live.get("gap_now_atr"), ".2f")))


def _cross_text(doc: dict, cross: Optional[dict]) -> str:
    """The last bullish 9/21 cross of the session at or before the listing bar: the record's own `up_cross_t`
    (divergence.up_cross_before over the whole session from 04:00 — None = no cross today) when the engine stored the
    key, else (an older record) the card frame's crosses (ema_cross — the ONE engine) on the session date."""
    a = _alert(doc)
    bar_t, day = _bar_t(doc), str(doc.get("date") or "")
    stamp = a.get("up_cross_t") if isinstance(a.get("up_cross_t"), str) else None
    if "up_cross_t" not in a and isinstance(cross, dict):
        ups = [c.get("t") for c in cross.get("crosses") or []
               if c.get("dir") == "up" and isinstance(c.get("t"), str) and c["t"][:10] == day and c["t"] <= bar_t]
        stamp = ups[-1] if ups else None
    if stamp:
        return "%d EMA crossed above the %d at %s ET" % (GC.EMA_FAST, GC.EMA_SLOW, _hhmm(stamp) or DASH)
    from daytrading.data import ET_PREMARKET_OPEN
    return "%d EMA already over the %d EMA at %s — no cross today" % (GC.EMA_FAST, GC.EMA_SLOW, _hm(ET_PREMARKET_OPEN))


def criteria(doc: dict, cross: Optional[dict] = None) -> list:
    a = _alert(doc)
    v2 = a.get("v2") if isinstance(a.get("v2"), dict) else {}
    run = v2.get("run") if isinstance(v2.get("run"), list) else []
    at = _hhmm(_bar_t(doc)) or DASH
    return [
        {"key": "gap", "label": "%d EMA over %d EMA, in ATRs" % (GC.EMA_FAST, GC.EMA_SLOW),
         "value": "%s ATRs on the %s ET bar" % (_num(a.get("r1"), ".2f"), at),
         "need": "≥ %.3f ATRs — the first bar over it today" % GC.DIVERGENCE_R1_LEVEL, "ok": True},
        {"key": "cross", "label": "bullish %d/%d cross" % (GC.EMA_FAST, GC.EMA_SLOW), "value": _cross_text(doc, cross),
         "need": "%d EMA above the %d EMA (long only)" % (GC.EMA_FAST, GC.EMA_SLOW), "ok": True},
        {"key": "volume", "label": "volume rising",
         "value": "%s · %d-bar mean %s ≥ prior hour %s" % (" → ".join(_vol(x) for x in run) or DASH,
                                                         GC.DIVERGENCE_V2_RUN, _vol(v2.get("run_mean")),
                                                         _vol(v2.get("hour_mean"))),
         "need": "%d bars non-decreasing, mean ≥ the %d bars before" % (GC.DIVERGENCE_V2_RUN,
                                                                       GC.DIVERGENCE_V2_HOUR_BARS),
         "ok": True},
    ]


def _ring_text(doc: dict) -> Optional[str]:
    ring = doc.get("ring") if isinstance(doc.get("ring"), dict) else {}
    kind, at = ring.get("kind"), ring.get("at_et")
    if kind in RING_TEXT and isinstance(at, str) and at:
        rd = ring.get("date")
        prior = isinstance(rd, str) and rd and rd != doc.get("date")    # an after-close ring of the prior session
        return RING_TEXT[kind].format(at=at) + (" (%s)" % rd if prior else "")
    return None


def record_words(doc: dict) -> dict:
    """The record in words for the card (every value a string or None — no raw float served)."""
    e, x = _entry(doc), _exit(doc)
    w = doc.get("window")
    return {"window": w if w in WINDOW_WORDS else None, "window_text": WINDOW_WORDS.get(w),
            "at_text": "%s ET" % (_hhmm(_bar_t(doc)) or DASH), "ring_text": _ring_text(doc), "state": _state(doc),
            "entry_text": ("%s · %s ET" % (_px(e.get("px")), _hhmm(e.get("t")) or DASH)) if e else None,
            "exit_text": ("%s · %s ET · %s" % (_px(x.get("px")), _hhmm(x.get("t")) or DASH, _reason_word(x, doc))
                          if x else None),
            "net_text": _pct_signed(_net(doc)) if _net(doc) is not None else None,
            "graded": _grade(doc) is not None,
            "oos_text": OOS_TEXT_ROW if doc.get("date") in GC.DIVERGENCE_OOS_SESSIONS else None,
            "half_day_text": HALF_DAY_TEXT if doc.get("half_day") is True else None}


# ── (b) the cards ───────────────────────────────────────────────────────────────────────────────────────────────
def card(read_doc: dict, doc: dict, *, scan_row: dict, sess: dict, halt_doc, listed_info, pass_at, v) -> dict:
    """One house card for one record. Raises on a malformed stored tile (the caller's per-record fence)."""
    from chart_maps.gajjala import tab as GT
    vv = V.of(v)
    tile = read_doc.get("tile")
    suf = str(V.frame_minutes(vv.primary, vv))
    if not isinstance(tile, dict) or not isinstance(tile.get(f"bars{suf}"), list):
        raise ValueError("malformed stored tile")
    fr = GT._tile_frame(read_doc, vv.primary, vv)
    sym = _sym(doc)
    bar_t = _bar_t(doc)
    markers = [{"date": bar_t, "kind": "buy", "label": "🧨"}]
    x = _exit(doc)
    if x is not None and isinstance(x.get("t"), str):
        markers.append({"date": x["t"], "kind": GT.EMA_CROSS_MARK["down"],
                        "label": "exit %s ET (%s)" % (_hhmm(x["t"]) or DASH, _reason_word(x, doc)),
                        "price": _f(x.get("px"))})
    cross = GT.ema_cross_block(fr)
    if cross:
        markers += [{"date": m["t"], "kind": GT.EMA_CROSS_MARK[m["dir"]], "label": m["text"], "price": _f(m["ema"])}
                    for m in cross.pop("_marks")]
    markers = GT._on_bars(markers, fr["bars"])
    e = _entry(doc)
    lines = ([{"price": _f(e["px"]), "label": "ENTRY %s" % _px(e["px"]), "tone": "buy", "text": _px(e["px"])}]
             if e is not None else [])
    a = _alert(doc)
    stats = [s for s in ({"k": "Change", "v": GT._pct(scan_row.get("change_pct"))},
                         {"k": "Volume", "v": GT._compact(scan_row.get("volume"))}) if s["v"]]
    stats.append({"k": "Gap", "v": "%s ATRs" % _num(a.get("r1"), ".2f")})
    chips = GT._chips(read_doc, GC.DIVERGENCE_SUB, {}, scan_row, sess, halt_doc, None, pass_at=pass_at)
    g = {"setup": GC.DIVERGENCE_SUB, "state": "divergence", "state_label": state_label(doc),
         "criteria": criteria(doc, cross), "missed": [], "unjudged": [], "plan_text": plan_text(doc), "chips": chips,
         "listed": GT._listed_block(listed_info), "divergence": record_words(doc)}
    vol_avg = fr.get("vol_avg") if isinstance(fr.get("vol_avg"), dict) else None
    out = {"symbol": sym, "name": read_doc.get("name"), "href": GT.chart_href(sym, fr["tf"], vv), "tf": fr["tf"],
           "bars": fr["bars"], "vol_avg": vol_avg, "bands": [], "lines": lines, "markers": markers, "stats": stats,
           "why": "", "badges": [], "curves": fr["curves"], "ema_blink": GT.ema_blink_of(fr), "gajjala": g}
    ax = GT.card_axis(fr, vv, sym=sym)
    if ax is not None:
        out["axis"] = ax
    return out


def _order(docs: list) -> list:
    """Open first (newest listing on top), then exited / no print (newest first)."""
    opened = sorted([d for d in docs if _state(d) == STATE_OPEN], key=_bar_t, reverse=True)
    rest = sorted([d for d in docs if _state(d) != STATE_OPEN], key=_bar_t, reverse=True)
    return opened + rest


def _cards(docs: list, *, reads_by: dict, scan_row: Callable, sess: dict, halts_by: dict, listed: dict, pass_at,
           v) -> tuple:
    """(tiles, chartless, faults) — EACH record in its own try; a record is never dropped from the words."""
    from chart_maps.gajjala import tab as GT
    tiles, chartless, faults = [], [], []
    for doc in _order(docs):
        sym = _sym(doc)
        line = {"symbol": sym, "at_text": "%s ET" % (_hhmm(_bar_t(doc)) or DASH), "state_label": None, "href": None,
                "text": CHARTLESS_TEXT.format(sym=sym or DASH, hhmm=_hhmm(_bar_t(doc)) or DASH)}
        try:
            line["state_label"] = state_label(doc)
            line["href"] = GT.chart_href(sym, V.of(v).primary, v) if sym else None
            rd = (reads_by or {}).get(sym)
            if not isinstance(rd, dict):
                chartless.append(line)
                continue
            t = card(rd, doc, scan_row=scan_row(sym), sess=sess, halt_doc=(halts_by or {}).get(sym),
                     listed_info=(listed or {}).get(sym), pass_at=pass_at, v=v)
            if not t["bars"]:
                chartless.append(line)
                continue
            tiles.append(t)
        except Exception as exc:                                    # noqa: BLE001 — one record never takes the sub down
            log.warning("gajjala divergence tab: card %s failed: %s", sym, type(exc).__name__)
            chartless.append(line)
            faults.append(sym)
    return tiles, chartless, faults


# ── (c) the 🏁 fold ─────────────────────────────────────────────────────────────────────────────────────────────
def _sessions(store, span_k: str, session: date) -> list:
    from chart_maps.gajjala import ledger as LG
    if span_k == GC.LEDGER_SPANS[-1]:                               # "all" — the record's own dates
        dates = store.divergence_dates()
        if dates is None:
            raise LG.LedgerReadError("the divergence dates could not be read")
        days = {d for d in (LG._as_date(x) for x in list(dates) + [session.isoformat()]) if d is not None}
        return sorted(days)
    return LG._sessions_for(span_k, session, store)


def _utc(t) -> Optional[datetime]:
    if not isinstance(t, str) or len(t) < 16:
        return None
    try:
        from chart_maps.gajjala import divergence as DV             # the ONE bar-stamp helper (the engine module)
        return DV.bar_close_utc(t)
    except Exception:                                               # noqa: BLE001
        return None


def _cell(state: str, text: str, provisional: bool = False) -> dict:
    c = {"state": state, "text": text}
    if provisional:
        c["provisional"] = True
    return c


def _row(doc: dict, *, v, broker_text_of) -> dict:
    from chart_maps.gajjala import ledger as LG
    from chart_maps.gajjala import tab as GT
    sym, d_iso = _sym(doc), str(doc.get("date") or "")
    rid = str(doc.get("_id") or "%s|%s" % (d_iso, sym))
    g = _grade(doc)
    e, x = _entry(doc), _exit(doc)
    at = _hhmm(_bar_t(doc))
    outcome = g.get("outcome") if g is not None else None
    if g is not None and outcome in GRADED_OUTCOMES:
        bucket = outcome
    elif g is not None:
        bucket = LG.BUCKETS[4]                                      # no print → "— no fill / not graded"
    else:
        bucket = LG.BUCKETS[2]                                      # not graded yet → open
    if e is not None:
        entry = _cell("filled", "%s · %s ET" % (_px(e.get("px")), _hhmm(e.get("t")) or DASH), provisional=g is None)
    elif g is not None:
        entry = _cell("no_entry", "no print after the listing")
    else:
        entry = _cell("pending", "next bar's open — not printed yet")
    if g is not None and x is not None:
        exit_c = _cell(outcome, "%s · %s ET · %s" % (_px(x.get("px")), _hhmm(x.get("t")) or DASH, _reason_word(x, doc)))
    elif g is not None:
        exit_c = _cell("no_entry", DASH)
    elif x is not None:
        exit_c = _cell("pending", "%s · %s ET · %s · not final" % (_px(x.get("px")), _hhmm(x.get("t")) or DASH,
                                                                   _reason_word(x, doc)), provisional=True)
    else:
        exit_c = _cell(LG.BUCKETS[2], "open — graded tonight %s ET" % GC.LEDGER_GRADE_AT_ET)
    if g is not None and outcome in GRADED_OUTCOMES:
        gross = _cell(outcome, _pct_signed(g.get("gross_pct")))
        net = _cell(outcome, _pct_signed(g.get("net_pct")))
    else:
        gross, net = _cell("pending", DASH), _cell("pending", DASH)
    w = doc.get("window") if doc.get("window") in WINDOW_WORDS else None
    try:
        btx = broker_text_of(sym) if broker_text_of is not None else None
    except Exception:                                               # noqa: BLE001 — a tag never takes the fold down
        btx = None
    return {"key": rid.replace("|", "-"), "id": rid, "date": d_iso, "symbol": sym, "window": w,
            "window_text": WINDOW_WORDS.get(w), "at_et": at, "at_text": "%s ET" % (at or DASH),
            "ring_text": _ring_text(doc), "entry": entry, "exit": exit_c, "gross": gross, "net": net,
            "outcome": outcome, "bucket": bucket, "bucket_text": LG.BUCKET_TEXT[bucket],
            "flag_text": LG.BUCKET_TEXT[bucket] if bucket in LG.FLAG_BUCKETS else None,
            "reason_text": _reason_word(x, doc) if x is not None else None,
            "oos_text": OOS_TEXT_ROW if d_iso in GC.DIVERGENCE_OOS_SESSIONS else None,
            "half_day_text": HALF_DAY_TEXT if doc.get("half_day") is True else None,
            "href": GT.chart_href(sym, V.of(v).primary, v) if sym else None, "broker_text": btx,
            "dup_of": None, "dup_text": None,
            "_net": _f(g.get("net_pct")) if g is not None and outcome in GRADED_OUTCOMES else None,
            "_gross": _f(g.get("gross_pct")) if g is not None and outcome in GRADED_OUTCOMES else None,
            "_reason": (x or {}).get("reason") if g is not None else None, "_half": doc.get("half_day") is True,
            "_facts": {"id": rid, "group": (d_iso, sym, GC.DIVERGENCE_SUB), "at": _utc(_bar_t(doc)),
                       "filled": True if e is not None else (False if g is not None else None),
                       "fill_t": _utc((e or {}).get("t")),
                       "decided_t": _utc((x or {}).get("t")) if g is not None else None,
                       "trigger": None, "stop": None, "rank": 0}}


def _blank() -> dict:
    return {"n": 0, "win": 0, "loss": 0, "flat": 0, "open": 0, "no_print": 0, "pct": None, "net_mean": None,
            "net_median": None, "gross_mean": None, "exit_downcross": 0, "exit_close": 0, "dup": 0, "sealed_rows": 0,
            "half_day": 0}


def _mean(xs: list) -> Optional[float]:
    return round(statistics.fmean(xs), 4) if xs else None


def _median(xs: list) -> Optional[float]:
    return round(statistics.median(xs), 4) if xs else None


def _counts(rows: list, sealed: bool) -> dict:
    """Per window over the rows: dups out; rows dated on an OOS session out while sealed (`sealed_rows`); half-day rows
    out of the registered-line totals (`half_day`, HIS CALL #7)."""
    out = {}
    for w in COUNT_WINDOWS:
        c, nets, grosses = _blank(), [], []
        for r in rows:
            if r.get("window") != w:
                continue
            if r.get("dup_of"):
                c["dup"] += 1
                continue
            if sealed and r["date"] in GC.DIVERGENCE_OOS_SESSIONS:
                c["sealed_rows"] += 1
                continue
            if r.get("_half"):
                c["half_day"] += 1
                continue
            b = r["bucket"]
            if b in GRADED_OUTCOMES:
                c[b] += 1
                c["n"] += 1
                if r.get("_net") is not None:
                    nets.append(r["_net"])
                if r.get("_gross") is not None:
                    grosses.append(r["_gross"])
                if r.get("_reason") == "downcross":
                    c["exit_downcross"] += 1
                elif r.get("_reason") == "close":
                    c["exit_close"] += 1
            elif b == "open":
                c["open"] += 1
            else:
                c["no_print"] += 1
        c["pct"] = int(round(100.0 * c["win"] / c["n"])) if c["n"] else None
        c["net_mean"], c["net_median"], c["gross_mean"] = _mean(nets), _median(nets), _mean(grosses)
        out[w] = c
    return out


def _counts_text(w: str, c: dict) -> str:
    head = WINDOW_WORDS[w] if w == "rth" else "AH"
    if c["n"]:
        s = ("%s · %d graded: %d wins · %d losses · %d%% won · net %s per trade (median %s) · %d down-cross exits / %d at "
             "the mark · %d open · %d no print" % (head, c["n"], c["win"], c["loss"], c["pct"],
                                                  _pct_signed(c["net_mean"]), _pct_signed(c["net_median"]),
                                                  c["exit_downcross"], c["exit_close"], c["open"], c["no_print"]))
    else:
        s = "%s · nothing to total yet" % head
    if c["sealed_rows"] > 0:
        s += " · %d OOS listing(s) not totalled until %s ET" % (c["sealed_rows"], GC.DIVERGENCE_OOS_SEAL_ET)
    if c["half_day"] > 0:
        s += " · %d half-day listing(s) outside the registered read" % c["half_day"]
    return s


def _oos_counts_text(store, v, broker_text_of) -> str:
    """After the seal: ONE read over every OOS session (not the span) — the registered window, RTH graded rows."""
    from chart_maps.gajjala import ledger as LG
    docs = store.divergence_docs([date.fromisoformat(s) for s in GC.DIVERGENCE_OOS_SESSIONS])
    if docs is None:
        raise LG.LedgerReadError("the OOS rows could not be read")
    rows = _dedupe([_row(d, v=v, broker_text_of=None) for d in docs if isinstance(d, dict)])
    c = _counts(rows, sealed=False)["rth"]
    return ("OOS %d sessions · RTH %d graded · net %s (median %s) · no CI under the lab's 30-week rule"
            % (len(GC.DIVERGENCE_OOS_SESSIONS), c["n"], _pct_signed(c["net_mean"]), _pct_signed(c["net_median"])))


def _dedupe(rows: list) -> list:
    """One count per stock per day — ledger.dedupe_trades (THE engine); a duplicate is chipped, never counted."""
    from chart_maps.gajjala import ledger as LG
    dups = LG.dedupe_trades([r["_facts"] for r in rows])
    by_id = {r["id"]: r for r in rows}
    for r in rows:
        first = dups.get(r["id"])
        if first is not None:
            r["dup_of"] = first
            r["dup_text"] = LG.DUP_TEXT.format(at=(by_id.get(first) or {}).get("at_et") or DASH, setup=DUP_SETUP)
            r["flag_text"] = None
    return rows


def _fold_rule_text() -> str:
    return ("Graded by the study's exit: entry = the next 5-minute bar's open; exit = the close of the first 5-minute "
            "bar whose %d EMA crosses back under the %d (after hours: the next print's open after that bar), else the "
            "regular-close mark (the %s mark after hours). Net %% = gross minus %s and $%.2f a share, each side. One "
            "count per stock per day." % (GC.EMA_FAST, GC.EMA_SLOW, _ah_mark(), format(GC.DIVERGENCE_COST_BPS, ".2%"),
                                          GC.DIVERGENCE_SLIP_USD))


def _strip(rows: list) -> None:
    for r in rows:
        for k in [k for k in r if k.startswith("_")]:
            r.pop(k, None)


def track_record(store, session: date, now: datetime, *, span: str, is_today: bool, v, broker_text_of,
                 board_docs: Optional[list] = None) -> dict:
    """The 🏁 fold (the 🏁 shape, GgTr* renderable). Raises on a read fault (the caller's fence)."""
    from chart_maps.gajjala import ledger as LG
    span_k = span if span in GC.LEDGER_SPANS else GC.LEDGER_SPAN_DEFAULT
    sessions = _sessions(store, span_k, session)
    if board_docs is not None and sessions == [session]:
        docs = board_docs
    else:
        docs = store.divergence_docs(sessions)
        if docs is None:
            raise LG.LedgerReadError("the divergence record could not be read")
    docs = sorted([d for d in docs if isinstance(d, dict) and d.get("symbol")],
                  key=lambda d: (str(d.get("date") or ""), _bar_t(d), _sym(d)))
    rows = _dedupe([_row(d, v=v, broker_text_of=broker_text_of) for d in docs])
    sealed = oos_sealed(now)
    counts = _counts(rows, sealed)
    s_iso = session.isoformat()
    days, served_n = LG._group_days(rows, s_iso, is_today)
    extra = len(rows) - served_n
    shown = [r for d in days for r in d["rows"]]
    out = {"title": TR_TITLE, "rule_label": TR_RULE_LABEL, "rule_text": _fold_rule_text(), "honesty": honesty(),
           "span": span_k, "spans": [{"key": k, "label": LG._span_label(k)} for k in GC.LEDGER_SPANS],
           "heads": [{"key": k, "label": lab} for k, lab in TR_HEADS],
           "counts": counts, "counts_text": {w: _counts_text(w, counts[w]) for w in COUNT_WINDOWS},
           "is_text": is_lines()["rth"]["text"],
           "oos_sealed": sealed, "oos_seal_et": GC.DIVERGENCE_OOS_SEAL_ET,
           "today_text": (TR_TODAY_TEXT.format(at=GC.LEDGER_GRADE_AT_ET)
                          if is_today and session in sessions else None),
           "days": days,
           "more_text": f"+{extra} more rows — the counts above cover all {len(rows)}" if extra > 0 else None,
           "empty_text": None if rows else _empty_text(span_k, sessions),
           "grade_at_et": GC.LEDGER_GRADE_AT_ET,
           "categories": LG._categories(shown), "category_param": LG.CATEGORY_PARAM,
           "category_empty_text": LG.CATEGORY_EMPTY_TEXT,
           "sorts": LG._sorts(), "sort_param": LG.SORT_PARAM, "sort_default": LG.SORT_KEYS[0],
           "bucket_order": list(LG.BUCKETS)}
    if sealed:
        out["oos_progress_text"] = ("OOS session %d of %d · sealed read after %s ET — not this tab"
                                    % (oos_done_n(now), len(GC.DIVERGENCE_OOS_SESSIONS), GC.DIVERGENCE_OOS_SEAL_ET))
    else:
        out["oos_counts_text"] = _oos_counts_text(store, v, broker_text_of)
    _strip(rows)
    return out


def _empty_text(span_k: str, sessions: list) -> str:
    if span_k == "today":
        return TR_EMPTY["today"]
    if span_k == "yesterday":
        return TR_EMPTY["yesterday"].format(day=sessions[0].isoformat() if sessions else DASH)
    return TR_EMPTY_SPAN


# ── the served block ────────────────────────────────────────────────────────────────────────────────────────────
def count_today(store, session: date) -> Optional[int]:
    """The 🧨 chip count: today's records; None on a read fault (the strip prints no number)."""
    try:
        docs = store.divergence_docs([session])
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala divergence tab: count read failed: %s", type(exc).__name__)
        return None
    return None if docs is None else len([d for d in docs if isinstance(d, dict)])


def block(store, session: date, now: datetime, *, span: str, is_today: bool, in_window: bool, reads_by: dict,
          scan_row: Callable, sess: dict, halts_by: dict, listed: dict, pass_at, flags,
          broker_text_of: Optional[Callable], v) -> Optional[dict]:
    """The 🧨 sub's served block (+ `_tiles`, popped by tab.build). None ONLY when the board session's record cannot be
    read (tab then serves FAULT_TEXT). `flags` is the order list tab.build applies with broker_bottom after the cut."""
    try:
        docs = store.divergence_docs([session])
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala divergence tab: read failed: %s", type(exc).__name__)
        docs = None
    if docs is None:
        return None
    docs = [d for d in docs if isinstance(d, dict) and d.get("symbol")]
    # (a) the panel words — pure
    states = [_state(d) for d in docs]
    out = {"title": TITLE, "ask_text": ASK_TEXT, "rule_label": RULE_LABEL, "rule_text": rule_text(),
           "honesty": honesty(), "is_line": is_lines(), "oos_text": oos_text(),
           "oos_sessions": list(GC.DIVERGENCE_OOS_SESSIONS), "oos_spec_sha256": GC.DIVERGENCE_OOS_SPEC_SHA256,
           "oos_done_n": oos_done_n(now), "oos_sealed": oos_sealed(now), "oos_seal_et": GC.DIVERGENCE_OOS_SEAL_ET,
           "cohort_text": COHORT_TEXT, "window_text": window_text(sess), "n_today": len(docs),
           "n_open": states.count(STATE_OPEN), "n_exited": states.count(STATE_EXITED),
           "empty_text": (None if docs else EMPTY_TODAY if is_today else
                          EMPTY_SESSION.format(label=(sess or {}).get("label") or session.isoformat())),
           "order_note": ORDER_NOTE}
    # (b) the cards — each record fenced
    tiles, chartless, faults = _cards(docs, reads_by=reads_by, scan_row=scan_row, sess=sess, halts_by=halts_by,
                                      listed=listed, pass_at=pass_at, v=v)
    out["chartless"] = chartless
    out["faults"] = faults
    out["faults_text"] = FAULTS_TEXT.format(n=len(faults)) if faults else None
    # (c) the 🏁 fold — its own fence
    try:
        out["track_record"] = track_record(store, session, now, span=span, is_today=is_today, v=v,
                                           broker_text_of=broker_text_of, board_docs=docs)
        out["track_record_fault_text"] = None
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala divergence tab: track record failed: %s", type(exc).__name__)
        out["track_record"] = None
        out["track_record_fault_text"] = TRACK_RECORD_FAULT_TEXT
    out["_tiles"] = tiles
    return out


__all__ = ["FAULT_TEXT", "TITLE", "ASK_TEXT", "TRACK_RECORD_FAULT_TEXT", "block", "count_today", "track_record", "card",
           "rule_text", "honesty", "is_lines", "oos_text", "oos_sealed", "oos_done_n", "state_label", "plan_text",
           "criteria", "record_words"]
