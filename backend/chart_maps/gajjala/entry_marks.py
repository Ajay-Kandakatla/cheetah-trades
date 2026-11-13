"""🟢 Gajjala sub-tab entry marks + ✨ the 30-minute blinker (SPEC dots rev 2, 2026-11-12). DISPLAY ONLY.

Ajay 2026-11-12 ~15:22 ET, verbatim: "Can you show me green on these tabs some indicators to show be which ones have best
potential entries right now I am clicking through each one and figuring out... an Indicator or new tickers with in last
30 mins like blinkers or something would be nice".

WHAT. Two served marks, computed here and nowhere else, called ONCE from `tab.build` through `_soft` (tab._entry_marks),
so 🚩 GG5, the 1-minute page and 🧪 Audited inherit them from the ONE builder:
  🟢 GREEN on a setup sub chip = its carded names whose read is an ENTRY PLAN right now (tab.is_entry_plan: A+ on the
     latest closed bar, or forming-ready, AND the trigger above the stop); on 🧠 = names with a trigger armed on a real
     plan. `triggered` is NOT green by default (GREEN_STATES — HIS CALL #1).
  ✨ NEW = something entered an entry state within GC.ENTRY_MARK_NEW_MIN minutes, by a STORED time only:
     an all-rules-met break (A+ now, or the same break read `triggered` later) from its entry bar's close;
     turned ready / 🧠 armed from the tracker's state_path stamp; new on his list today (card only);
     first seen as a 🧠 potential (card only, and only when GC.POTENTIAL_PUSH_ARMED_ONLY is off). No stored time →
     no blinker.

READ-ONLY. No store, no I/O, no wall clock (`now` comes from build). Both marks follow the 🎯 banner's own "right now"
clock (tab.banner_clock) and leave his 🚫 names out for every viewer (the 🔝 Focus rule). Never reorders, drops, gates,
pushes or counts anything; `subs`, `counts` and tile order are untouched. UNMEASURED — nothing here claims an edge.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT

# ── module words / switches (the ONLY place they are typed) ────────────────────────────────────────────────────
GREEN_STATES = ("aplus", "ready")       # MINE — tab.is_entry_plan's two states; adding "triggered" = HIS CALL #1
BREAK_STATES = ("aplus", "triggered")   # detectors._resolve_break — ONE all-rules-met break, latest bar or earlier (not a switch)
CHIP_NEW_KINDS = ("aplus", "ready", "armed")   # MINE (critic C5) — the chip pulses for entry kinds only; "listed" = HIS CALL #4
SKIP_BROKER = True                      # MINE — his 🚫 names out of the marks, every viewer (the 🔝 Focus rule) = HIS CALL #2
NEW_ON_LIST = True                      # MINE — the card's "new on his list" blinker (scanner first_qualified_at) = HIS CALL #4
GREEN_ORDER = ("aplus", "triggered", "ready", "armed")
MARK_ORDER = ("aplus", "ready", "armed", "potential", "listed")
GREEN_HEAD = "🟢 {n} close to an entry"
GREEN_WORDS = {"aplus": "A+ on the latest closed bar",
               "triggered": "triggered — broke earlier, still above its stop",
               "ready": "ready — the next bar over the trigger is the entry",
               "armed": "🧠 {armed} — the next bar over the trigger is the entry"}   # {armed} = PT.KIND_LABEL["armed"]
RANG_WORD = "alert rang {at} ET"        # rang True; rang False → tab.NO_RING_TEXT; None → no clause
GREEN_TAIL = "display only — no order, count or alert changes · {unmeasured}"
PAST_WORD = "{n} not among the {lim} cards shown: {names}"     # [C6] the SHOWN sub only
NEW_HEAD = "✨ new in the last {m} minutes"
NEW_TEXT = "new {at} ET"                # the card's visible words beside the dot
NEW_WORDS = {"aplus": "A+ on the {at} ET bar",
             "ready": "ready since the {at} ET pass",
             "armed": "🧠 {armed} since the {at} ET pass",
             "potential": "first seen as a 🧠 potential at the {at} ET pass",
             "listed": "new on his list at {at} ET — first qualified his scanner today"}
NEW_TAIL = "marked new for {m} minutes · display only"


def _GT():
    from chart_maps.gajjala import tab as GT                         # lazy: tab imports this module through _soft
    return GT


def _armed_label() -> str:
    return PT.KIND_LABEL[GC.POTENTIAL_KINDS[0]]


def _minutes() -> int:
    return GC.ENTRY_MARK_NEW_MIN                                     # read at call time, never typed


def kind_of(read) -> Optional[str]:
    """"aplus" (A+ on a real plan) · "ready" (forming-ready on a real plan) · "triggered" · None. GREEN iff the kind
    is in GREEN_STATES. A 🧪 held A+ (its own state word) → None."""
    if not isinstance(read, dict):
        return None
    GT = _GT()
    st = read.get("state")
    if st == "aplus" and GT.is_entry_plan(read):
        return "aplus"
    if st == "forming" and GT.is_entry_plan(read):
        return "ready"
    if st == "triggered":
        return "triggered"
    return None


def _utc(x) -> Optional[datetime]:
    """A stored stamp as aware UTC: a datetime (Mongo hands back NAIVE UTC — never read as ET) or an ISO string."""
    GT = _GT()
    if isinstance(x, datetime):
        return GT._stamp_utc(x)
    if isinstance(x, str) and x:
        try:
            return GT._stamp_utc(datetime.fromisoformat(x))
        except ValueError:
            return None
    return None


def _now_utc(now) -> Optional[datetime]:
    return _utc(now)


def ready_since(tracker) -> Optional[datetime]:
    """The tracker's stamp of the latest turn into (forming, armed) — state_path[-1] when it is that entry; None when
    no doc, an empty / malformed path, the last entry not (forming, armed), or a joined doc whose last entry is the
    path's FIRST (the join pass saw it first — not when it turned)."""
    if not isinstance(tracker, dict):
        return None
    path = tracker.get("state_path")
    if not isinstance(path, list) or not path or not isinstance(path[-1], dict):
        return None
    last = path[-1]
    if (last.get("state"), last.get("kind")) != (GC.POTENTIAL_STATE, GC.POTENTIAL_KINDS[0]):
        return None
    if tracker.get("first_seen_mode") == PT.FIRST_SEEN_MODES[1] and len(path) == 1:
        return None
    return _utc(last.get("at"))


def break_at(read) -> Optional[datetime]:
    """The break's entry bar CLOSE (the bar stamp is its close label — never add the frame), aware ET; None when absent."""
    if not isinstance(read, dict):
        return None
    from chart_maps.gajjala import alerts as AL
    return AL.bar_close_et(read.get("entry_bar_t"))


def first_on_potential(trackers: dict, sym: str) -> Optional[datetime]:
    """The earliest first_seen over the symbol's tracker docs; None when none, any first_seen missing, or ANY doc of
    the symbol is joined (its first sighting is the join pass)."""
    docs = [d for (s, _setup), d in (trackers or {}).items() if s == sym and isinstance(d, dict)]
    if not docs:
        return None
    if any(d.get("first_seen_mode") == PT.FIRST_SEEN_MODES[1] for d in docs):
        return None
    stamps = [_utc(d.get("first_seen")) for d in docs]
    if any(t is None for t in stamps):
        return None
    return min(stamps)


def listed_at(sym, scan_doc, listed_info, session) -> Optional[datetime]:
    """New on his list today: the scanner's first_qualified_at, only when the name is listed SINCE today (not carried)."""
    if not NEW_ON_LIST or not isinstance(listed_info, dict) or not isinstance(scan_doc, dict):
        return None
    if session is None or listed_info.get("since") != session.isoformat():
        return None
    return _utc(scan_doc.get("first_qualified_at"))


def is_new(at, now) -> bool:
    """0 ≤ now − at < ENTRY_MARK_NEW_MIN minutes (30:00 exactly → False; a future stamp → False)."""
    if at is None or now is None:
        return False
    age = (now - at).total_seconds()
    return 0 <= age < _minutes() * 60


def _words(kind: str, at, rang_clause=None) -> str:
    GT = _GT()
    w = NEW_WORDS[kind].format(at=GT._hhmm(at), armed=_armed_label())
    if kind == "aplus" and rang_clause:
        w += " — " + rang_clause
    return w


def _tail() -> str:
    return " · " + NEW_TAIL.format(m=_minutes())


def mark(kind, at, *, rang_clause=None) -> dict:
    """One served blinker: {kind, at_et, until (aware-UTC ISO), text, title}."""
    GT = _GT()
    hhmm = GT._hhmm(at)
    until = _utc(at) + timedelta(minutes=_minutes())
    return {"kind": kind, "at_et": hhmm, "until": until.isoformat(), "text": NEW_TEXT.format(at=hhmm),
            "title": _words(kind, at, rang_clause) + _tail()}


def _mark_words(m: dict) -> str:
    t, sfx = m.get("title") or "", _tail()
    return t[:-len(sfx)] if t.endswith(sfx) else t


def mark_of(read, *, tracker, scan_doc, listed_info, session, now, rang) -> Optional[dict]:
    """[C1] The FIRST candidate that is new: a break (A+ now or the same break read triggered) from its entry bar's
    close; a ready read from the tracker's armed stamp; new on his list today. Independent of GREEN_STATES. `rang` = a
    zero-arg callable → the alert clause or None, called only for a new break."""
    if not isinstance(read, dict):
        return None
    if read.get("state") in BREAK_STATES:
        at = break_at(read)
        if is_new(at, now):
            return mark("aplus", at, rang_clause=rang() if callable(rang) else None)
    if kind_of(read) == "ready":
        at = ready_since(tracker)
        if is_new(at, now):
            return mark("ready", at)
    at = listed_at(None, scan_doc, listed_info, session)
    if is_new(at, now):
        return mark("listed", at)
    return None


def _past(names, lim) -> str:
    return PAST_WORD.format(n=len(names), lim=lim, names=", ".join(names))


def green_block(rows, *, past=None, lim=None) -> Optional[dict]:
    """rows = [(kind, SYM, rang_clause | None)] → {n, label, title}; None when empty (never n 0)."""
    rows = [r for r in rows or [] if r and r[0] in GREEN_WORDS]
    if not rows:
        return None
    GT = _GT()
    groups = []
    for k in GREEN_ORDER:
        names = sorted((r for r in rows if r[0] == k), key=lambda r: r[1])
        if not names:
            continue
        txt = ", ".join(f"{sym} ({c})" if c else sym for _k, sym, c in names)
        groups.append(GREEN_WORDS[k].format(armed=_armed_label()) + ": " + txt)
    n = len(rows)
    title = GREEN_HEAD.format(n=n) + " — " + " · ".join(groups)
    if past:
        title += " · " + _past(past, lim)
    title += " · " + GREEN_TAIL.format(unmeasured=GT.UNMEASURED)
    return {"n": n, "label": str(n), "title": title}


def new_block(rows, *, past=None, lim=None) -> Optional[dict]:
    """rows = [(SYM, mark)], mark kind in CHIP_NEW_KINDS → {n, until, title}; None when empty."""
    rows = [(s, m) for s, m in rows or [] if isinstance(m, dict) and m.get("kind") in CHIP_NEW_KINDS]
    if not rows:
        return None
    rows.sort(key=lambda r: (-_utc(r[1]["until"]).timestamp(), r[0]))      # newest first, then the symbol
    until = max((r[1]["until"] for r in rows), key=lambda u: _utc(u))
    title = NEW_HEAD.format(m=_minutes()) + " — " + " · ".join(f"{s} {_mark_words(m)}" for s, m in rows)
    if past:
        title += " · " + _past(past, lim)
    return {"n": len(rows), "until": until, "title": title}


def apply(out, *, reads_by, carded, pots, trackers, scan_by, listed, session, now, pass_doc, cron, in_window, v, lim,
          flags, entries=None) -> None:
    """Serve `out["entry_marks"]` and the shown tiles' `new_mark`. Everything is computed first, then assigned — a
    raise assigns nothing (tab._soft logs it)."""
    GT = _GT()
    g = GT.banner_clock(pass_doc, now, in_window=in_window, cron=cron, session=session, v=v)
    live_at = g["at"] if g["live"] else None
    if live_at is None:
        out["entry_marks"] = {"subs": {}}
        return
    now_u = _now_utc(now)
    reads_by = reads_by or {}
    trackers = trackers or {}
    scan_by = scan_by or {}
    listed = listed or {}

    def skip(sym) -> bool:
        return SKIP_BROKER and GT.broker_text_for(sym, flags or None) is not None

    def fresh(doc) -> bool:
        return GT.read_of_pass(doc, live_at)

    memo: dict = {}

    def ent():
        if "v" not in memo:
            memo["v"] = entries() if callable(entries) else entries
        return memo["v"]

    def clause(sym, setup) -> Optional[str]:
        if entries is None:
            return None
        e = ent()
        r = GT._rang(e, session, sym, setup)
        if r is True:
            return RANG_WORD.format(at=e[(session.isoformat(), sym, setup)])
        if r is False:
            return GT.NO_RING_TEXT
        return None

    sub_k = out.get("sub")
    shown = {t.get("symbol") for t in (out.get("tiles") or []) if isinstance(t, dict)}
    subs: dict = {}
    marks: dict = {}

    def blocks(key, green_rows, new_rows):
        gp = np = None
        if key == sub_k:                                            # [C6] the SHOWN sub only
            gp = sorted({r[1] for r in green_rows} - shown) or None
            np = sorted({r[0] for r in new_rows} - shown) or None
        gb = green_block(green_rows, past=gp, lim=lim)
        nb = new_block(new_rows, past=np, lim=lim)
        b = {k: x for k, x in (("green", gb), ("new", nb)) if x}
        if b:
            subs[key] = b

    for setup in GC.SETUPS:
        green_rows, new_rows = [], []
        for sym in carded.get(setup, []) if isinstance(carded, dict) else []:
            if skip(sym):
                continue
            doc = reads_by.get(sym)
            if not fresh(doc):
                continue
            read = (doc.get("setups") or {}).get(setup) if isinstance(doc.get("setups"), dict) else None
            if not isinstance(read, dict):
                continue
            k = kind_of(read)
            if k in GREEN_STATES:
                green_rows.append((k, sym, clause(sym, setup) if k == "aplus" else None))
            m = mark_of(read, tracker=trackers.get((sym, setup)), scan_doc=scan_by.get(sym),
                        listed_info=listed.get(sym), session=session, now=now_u,
                        rang=lambda s=sym, su=setup: clause(s, su))
            if m:
                marks[(setup, sym)] = m
                if m["kind"] in CHIP_NEW_KINDS:
                    new_rows.append((sym, m))
        blocks(setup, green_rows, new_rows)

    # 🧠 — one name per symbol
    pot_green: set = set()
    armed_at: dict = {}
    pot_seen: list = []
    for p in pots or []:
        _okey, row, doc, read = p
        sym = row.get("symbol")
        if not sym or skip(sym) or not fresh(doc):
            continue
        if sym not in pot_seen:
            pot_seen.append(sym)
        if row.get("kind") != GC.POTENTIAL_KINDS[0]:
            continue
        if not GT.is_entry_plan(read):                              # [C2] no plan → no green, no armed blink
            continue
        pot_green.add(sym)
        t = ready_since(trackers.get((sym, row.get("setup"))))
        if t is not None and (sym not in armed_at or t > armed_at[sym]):
            armed_at[sym] = t
    pot_new = []
    for sym in pot_seen:
        m = None
        if is_new(armed_at.get(sym), now_u):
            m = mark("armed", armed_at[sym])
        elif not GC.POTENTIAL_PUSH_ARMED_ONLY:                      # [C7] read at call time
            t = first_on_potential(trackers, sym)
            if is_new(t, now_u):
                m = mark("potential", t)
        if m:
            marks[(GC.POTENTIAL_SUB, sym)] = m
            if m["kind"] in CHIP_NEW_KINDS:
                pot_new.append((sym, m))
    blocks(GC.POTENTIAL_SUB, [(GC.POTENTIAL_KINDS[0], s, None) for s in sorted(pot_green)], pot_new)

    tile_key = sub_k if sub_k in GC.SETUPS or sub_k == GC.POTENTIAL_SUB else None
    assigns = [(t, marks[(tile_key, t.get("symbol"))]) for t in (out.get("tiles") or [])
               if tile_key is not None and isinstance(t, dict) and (tile_key, t.get("symbol")) in marks]
    tbl = out.get("table")                                          # 📋 2026-11-13 — the table rows: the setup mark, else the 🧠 one
    rows = tbl.get("rows") if isinstance(tbl, dict) and isinstance(tbl.get("rows"), list) else []
    assigns += [(r, m) for r in rows if isinstance(r, dict)
                for m in [marks.get((r.get("setup"), r.get("symbol"))) or marks.get((GC.POTENTIAL_SUB, r.get("symbol")))]
                if m]
    out["entry_marks"] = {"subs": subs}
    for t, m in assigns:
        t["new_mark"] = dict(m)


__all__ = ["apply", "kind_of", "ready_since", "break_at", "first_on_potential", "listed_at", "is_new", "mark",
           "mark_of", "green_block", "new_block", "GREEN_STATES", "BREAK_STATES", "CHIP_NEW_KINDS", "SKIP_BROKER",
           "NEW_ON_LIST", "PAST_WORD", "NEW_TEXT", "NEW_WORDS", "GREEN_WORDS", "RANG_WORD"]
