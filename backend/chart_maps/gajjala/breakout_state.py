"""⏸ The "no breakout" line on Gajjala's cards, 🧠 potentials and today's 📈 Track rows (2026-11-12).

Ajay 2026-11-12 ~14:45 ET, verbatim: "Most of our potentials are not having breakout, please write that on them that..
I need for an additonal break out from the triggers Usually after that run up to tirgger point they are mostly just
sitting there"

GG's own words behind the line: C3 "The volume will dry up during the entries of all my setups and it picks up if the
setup works."; X5 CGC "breakout on good volume"; E3 "a breakout back into its range = out" (that last one is an EXIT
word — never printed here, his 2026-11-06 call "keep it"). GG gives NO number for "good volume" on the break.

Display only — no alert, A+, rule, order or grade reads it. UNMEASURED. Computed at SERVE time from the read on the
card and the stored tile bars of the READ's own frame (never the drawn frame, never the 🎾 wide frame); attached by ONE
post-walk call in tab.build (the 🧭 _stage_tag pattern). Nothing in the pass reads this module.

Definitions (structural; no threshold; MINE — (Cheetah default, not his), potential.CHEETAH_TAG):
- trigger bar = the read's own break bar (`entry_bar_t`, only when `broke is True`) — the detector's strict `>`.
- breakout = a later CLOSED bar closing above the highest high from the trigger bar through the bar before it.
- volume louder = that bar's volume, rounded as the K3 row prints it, above the busiest base bar parsed off the card's
  own K3 row (detectors.K3_VOL_KEY) — no ratio.
- traded under the stop = the first bar from the trigger bar on whose low is under the read's stop (the engine's strict
  `<`, detectors.stopped_after); nothing at or after it is read as a breakout.
- back under = the latest closed bar closed under the trigger.
- the latest closed bar decides: 🔊/🔇/⤴️ only when it is itself a breakout; otherwise ⏸ (an earlier breakout is named).
- no breakout yet (🧠) = a potential read (forming with a base): by construction no bar traded over its trigger.

Precedence (broke reads): trigger bar = latest bar → no line · stop traded → ✖️ · last close < trigger → ↩️ · latest
bar is a breakout → 🔊/🔇/⤴️ · else ⏸.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import variant as V

# ── words (MINE; the ONLY place they are typed — the FE types none) ───────────────────────────────────────────────
STATES = ("waiting", "broke_vol", "broke_quiet", "broke_unjudged", "back_under", "stop_printed", "off_chart",
          "no_break_yet", "no_break")
CARD_STATES = STATES[:-1]                      # "no_break" is a 📈 Track row word only
SKIP_STATES = ("stopped", "invalid", "none")   # a broke read in these never gets a line
SEP = " · "
HEAD = {
    "waiting": "⏸ no breakout since the trigger",
    "waiting_after": "⏸ no new breakout since the {at} bar",
    "broke_vol": "🔊 broke out on the {at} bar — volume louder than the base's busiest bar",
    "broke_quiet": "🔇 broke out on the {at} bar — volume not louder than the base's busiest bar",
    "broke_unjudged": "⤴️ broke out on the {at} bar — volume not judged",
    "back_under": "↩️ back under the trigger {trigger} since the {at} bar",
    "stop_printed": "✖️ traded under the stop {stop} on the {at} bar",
    "off_chart": "⏸ trigger bar {reach} is off the chart — breakout not read",
    "no_break_yet": "⏸ no breakout yet",
    "no_break": "⏸ no breakout over {trigger}",
    "no_break_bare": "⏸ no breakout",
}
PART = {
    "last": "last close {close} ({pct} vs the trigger {trigger})",
    "last_nopct": "last close {close}, trigger {trigger}",
    "need": "needs a close above {level} (the high since the trigger) on volume louder than {peak} (the base's busiest bar)",
    "need_nopeak": "needs a close above {level} (the high since the trigger); base volume not on file",
    "closed_over": "closed above {level}, the high since the trigger",
    "vol": "volume {vol} vs {peak} (the base's busiest bar)",
    "vol_unjudged": "base volume not on file",
    "prior": "that breakout: {word}",
    "prior_stop": "broke out on the {at} bar before that",
    "since": "{mins} min since the trigger bar ({reach})",
    "since_seen": "{mins} min since first seen ({first} bar)",
}
VOL_WORD = {"broke_vol": "volume louder than the base's busiest bar",
            "broke_quiet": "volume not louder than the base's busiest bar",
            "broke_unjudged": "volume not judged"}
_BUSIEST_RE = re.compile(r"^busiest bar ([\d,]+)$")   # mirrors detectors._busiest + _vol — pinned by a round-trip test
_STAMP = "%Y-%m-%d %H:%M"


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _tab():
    from chart_maps.gajjala import tab as T          # lazy: tab imports this module inside build
    return T


def base_peak_volume(read: dict) -> Optional[float]:
    """The busiest base bar off the card's own K3 row (key detectors.K3_VOL_KEY): "busiest bar 1,234,567" → 1234567.0;
    "no bar yet" / no row / anything garbled → None."""
    from chart_maps.gajjala import detectors as D
    if not isinstance(read, dict):
        return None
    for c in read.get("criteria") or []:
        if isinstance(c, dict) and c.get("key") == D.K3_VOL_KEY:
            m = _BUSIEST_RE.match(c.get("value") or "") if isinstance(c.get("value"), str) else None
            return float(m.group(1).replace(",", "")) if m else None
    return None


def _upto(bars, as_of_t) -> list:
    """Dict bars only, cut to the bar whose `t` == as_of_t when it is served (inclusive)."""
    out = [b for b in bars or [] if isinstance(b, dict)]
    ts = [b.get("t") for b in out]
    if isinstance(as_of_t, str) and as_of_t in ts:
        out = out[:ts.index(as_of_t) + 1]
    return out


def _loud(v, peak) -> Optional[bool]:
    """Volume louder than the base's busiest bar, compared as printed (round(v)); None = not judged."""
    x = _tab()._f(v)
    if peak is None or x is None or x <= 0:
        return None
    return round(x) > peak


def _stamp(s) -> Optional[datetime]:
    if not isinstance(s, str):
        return None
    try:
        return datetime.strptime(s, _STAMP)
    except ValueError:
        return None


def _mins(a: str, b: str) -> Optional[int]:
    """Whole minutes from bar stamp a to bar stamp b; None on a parse error or a negative answer."""
    x, y = _stamp(a), _stamp(b)
    if x is None or y is None:
        return None
    n = (y - x) // timedelta(minutes=1)
    return n if n >= 0 else None


def _vol_state(v, peak) -> str:
    loud = _loud(v, peak)
    return "broke_unjudged" if loud is None else ("broke_vol" if loud else "broke_quiet")


# ── the reads (pure) ──────────────────────────────────────────────────────────────────────────────────────────────
def read_breakout(bars: list, *, trigger, stop=None, entry_t: str, as_of_t: Optional[str] = None,
                  base_peak: Optional[float] = None) -> Optional[dict]:
    """What the bars did since the trigger bar (module docstring). PURE. None = no line."""
    T = _tab()
    trig = T._f(trigger)
    if trig is None:
        return None
    bs = _upto(bars, as_of_t)
    ts = [b.get("t") for b in bs]
    if entry_t not in ts:
        first = ts[0] if ts else None
        if isinstance(entry_t, str) and isinstance(first, str) and entry_t < first:
            return {"state": "off_chart", "reach_t": entry_t}
        return None
    j, last = ts.index(entry_t), len(bs) - 1
    if j == last:
        return None                                   # a fresh break: the pill already says it
    h = [T._f(b.get("h")) for b in bs]
    c = [T._f(b.get("c")) for b in bs]
    lo = [T._f(b.get("l")) for b in bs]
    v = [b.get("v") for b in bs]
    if any(h[k] is None or c[k] is None for k in range(j, last + 1)):
        return None
    s = T._f(stop)
    ks = next((k for k in range(j, last + 1) if s is not None and lo[k] is not None and lo[k] < s), None)
    end = last if ks is None else ks - 1
    kb = kb_lvl = None
    for k in range(j + 1, end + 1):
        lvl = max(h[j:k])
        if c[k] > lvl:
            kb, kb_lvl = k, lvl
    out = {"state": None, "reach_t": ts[j], "last_t": ts[last], "minutes": _mins(ts[j], ts[last]), "at_t": None,
           "level": None, "close": c[last], "vol": None, "base_peak": base_peak, "prior_t": None, "prior_state": None}
    if kb is not None:
        out["prior_t"], out["prior_state"] = ts[kb], _vol_state(v[kb], base_peak)
    if ks is not None:
        out.update(state="stop_printed", at_t=ts[ks])
    elif c[last] < trig:
        k = last
        while k - 1 >= j and c[k - 1] < trig:
            k -= 1
        out.update(state="back_under", at_t=ts[k], prior_t=None, prior_state=None)
    elif kb == last:
        out.update(state=_vol_state(v[last], base_peak), at_t=ts[last], level=kb_lvl, vol=T._f(v[last]),
                   prior_t=None, prior_state=None)
    else:
        out.update(state="waiting", at_t=out["prior_t"], level=max(h[j:last + 1]))
    return out


def read_forming(bars: list, *, trigger, as_of_t: Optional[str] = None,
                 first_bar_t: Optional[str] = None) -> Optional[dict]:
    """A 🧠 potential: no breakout yet — the last close and the minutes since the tracker first saw it (same date)."""
    T = _tab()
    if T._f(trigger) is None:
        return None
    bs = _upto(bars, as_of_t)
    close = next((x for x in (T._f(b.get("c")) for b in reversed(bs)) if x is not None), None)
    last_t = bs[-1].get("t") if bs else None
    a, b = _stamp(first_bar_t), _stamp(last_t)
    mins = _mins(first_bar_t, last_t) if a is not None and b is not None and a.date() == b.date() else None
    return {"state": "no_break_yet", "close": close, "first_t": first_bar_t if mins is not None else None,
            "minutes": mins}


# ── words ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _last_part(r: dict, trigger) -> Optional[str]:
    T = _tab()
    close = r.get("close")
    if T._f(close) is None:
        return None
    pct = PT._pct_move(close, trigger)
    if pct is None:
        return PART["last_nopct"].format(close=T._px(close), trigger=T._px(trigger))
    return PART["last"].format(close=T._px(close), pct=f"{pct:+.1f}%", trigger=T._px(trigger))


def words(r: dict, *, trigger, stop=None) -> dict:
    """{head, detail, text} of one read (STATES); detail = SEP-joined parts, text = head + detail."""
    T = _tab()
    st = r.get("state")
    hh = T._hhmm
    since = (PART["since"].format(mins=r["minutes"], reach=hh(r.get("reach_t")))
             if isinstance(r.get("minutes"), int) else None)
    parts: list = []
    if st == "off_chart":
        head = HEAD["off_chart"].format(reach=hh(r.get("reach_t")))
    elif st == "waiting":
        at = r.get("at_t")
        head = HEAD["waiting_after"].format(at=hh(at)) if at else HEAD["waiting"]
        peak = r.get("base_peak")
        need = (PART["need"].format(level=T._px(r.get("level")), peak=T._compact(peak)) if T._compact(peak)
                else PART["need_nopeak"].format(level=T._px(r.get("level"))))
        prior = PART["prior"].format(word=VOL_WORD[r["prior_state"]]) if at and r.get("prior_state") in VOL_WORD else None
        parts = [_last_part(r, trigger), need, prior, since]
    elif st in VOL_WORD:
        head = HEAD[st].format(at=hh(r.get("at_t")))
        vol = (PART["vol"].format(vol=T._compact(r.get("vol")), peak=T._compact(r.get("base_peak")))
               if st != "broke_unjudged" else PART["vol_unjudged"])
        parts = [PART["closed_over"].format(level=T._px(r.get("level"))), vol, _last_part(r, trigger), since]
    elif st == "back_under":
        head = HEAD["back_under"].format(trigger=T._px(trigger), at=hh(r.get("at_t")))
        parts = [_last_part(r, trigger), since]
    elif st == "stop_printed":
        head = HEAD["stop_printed"].format(stop=T._px(stop), at=hh(r.get("at_t")))
        prior = PART["prior_stop"].format(at=hh(r["prior_t"])) if r.get("prior_t") else None
        parts = [prior, _last_part(r, trigger), since]
    elif st == "no_break_yet":
        head = HEAD["no_break_yet"]
        seen = (PART["since_seen"].format(mins=r["minutes"], first=hh(r.get("first_t")))
                if isinstance(r.get("minutes"), int) else None)
        parts = [_last_part(r, trigger), seen]
    else:                                             # "no_break" — a 📈 Track row word only
        head = HEAD["no_break"].format(trigger=T._px(trigger)) if T._f(trigger) is not None else HEAD["no_break_bare"]
    detail = "".join(SEP + p for p in parts if p)
    return {"head": head, "detail": detail, "text": head + detail}


def hint() -> str:
    """The ℹ️ hover: the definitions, the Cheetah tag, GG's C3 quote (read off verified_rules.json, never typed) and
    UNMEASURED."""
    quote = None
    try:
        from chart_maps.gajjala import playbook as PB
        doc = PB._rules_doc() or {}
        for t in doc.get("topics") or []:
            for r in (t.get("verified") or []) if isinstance(t, dict) else []:
                if isinstance(r, dict) and r.get("id") == "C3" and r.get("quotes"):
                    quote = r["quotes"][0] if isinstance(r["quotes"][0], str) else None
                    break
            if quote:
                break
    except Exception:                                                # noqa: BLE001 — the hint is never load-bearing
        quote = None
    tag = PT.CHEETAH_TAG.rstrip(")") + ".)"
    gg = f" GG: “{quote}”" if quote else ""
    return ("Display only — no alert, A+, rule, order or grade reads it. Trigger bar = the bar that broke the trigger "
            "(the card's own A+ / triggered / broke bar). Breakout = a later closed bar closing above the highest high "
            "since the trigger bar; the latest closed bar decides the line, an earlier breakout is named in the detail. "
            "Volume louder = that bar's volume above the busiest bar of the base (the card's K3 row). Traded under the "
            "stop = a bar from the trigger bar on traded under the card's stop; nothing after it counts as a breakout. "
            "Back under = the latest closed bar closed under the trigger. No breakout yet = a 🧠 potential: no bar has "
            f"traded over its trigger. {tag}{gg} UNMEASURED.")


# ── the served blocks ─────────────────────────────────────────────────────────────────────────────────────────────
def _served(r: dict, read: dict) -> dict:
    w = words(r, trigger=read.get("trigger"), stop=read.get("stop"))
    return {"state": r["state"], "head": w["head"], "detail": w["detail"], "text": w["text"], "hint": hint()}


def block(read: dict, doc: dict, v=None, *, pot: Optional[dict] = None) -> Optional[dict]:
    """The card line of one read (None = no line): a broke read (aplus / triggered / partial / 🧪 aplus_held) → what the
    bars did since its trigger bar; a 🧠 potential → no breakout yet; anything else → None."""
    if not isinstance(read, dict) or read.get("setup") not in GC.SETUPS or not isinstance(doc, dict):
        return None
    T, vv = _tab(), V.of(v)
    bars = T._tile_frame(doc, read.get("frame") or vv.primary, vv)["bars"]
    if read.get("broke") is True and read.get("state") not in SKIP_STATES and isinstance(read.get("entry_bar_t"), str):
        r = read_breakout(bars, trigger=read.get("trigger"), stop=read.get("stop"), entry_t=read["entry_bar_t"],
                          as_of_t=read.get("as_of_bar_t"), base_peak=base_peak_volume(read))
    elif PT.potential_kind(read) is not None:
        r = read_forming(bars, trigger=read.get("trigger"), as_of_t=read.get("as_of_bar_t"),
                         first_bar_t=(pot or {}).get("first_bar_t") if isinstance(pot, dict) else None)
    else:
        r = None
    return _served(r, read) if r else None


def row_block(read: Optional[dict], doc: Optional[dict], v=None, *, pot: Optional[dict] = None) -> Optional[dict]:
    """A 📈 Track row of today: the card's block; else a read that never broke (and is not `stopped`) → no_break."""
    b = block(read, doc, v, pot=pot)
    if b is not None:
        return b
    if (isinstance(read, dict) and read.get("setup") in GC.SETUPS and read.get("broke") is not True
            and read.get("state") != "stopped"):
        return _served({"state": "no_break"}, read)
    return None


def tag(out: dict, reads_by: dict, v=None, *, pots: Optional[list] = None) -> None:
    """In place: every card in out["tiles"] gains gajjala["breakout"], every row of TODAY's 📈 Track gains "breakout"
    (never "yesterday": reads_by is the board session's). `pots` = build's tracker docs of the board session. Every
    block is computed FIRST, then all are assigned (a raise → no card and no row has the key). Never reorders, drops
    or gates; a card or row with no line keeps every byte."""
    pots_by = {(str(d.get("symbol") or "").upper(), d.get("setup")): d for d in pots or [] if isinstance(d, dict)}
    reads_by = reads_by if isinstance(reads_by, dict) else {}

    def read_of(sym, setup):
        doc = reads_by.get(sym)
        doc = doc if isinstance(doc, dict) else None
        setups = (doc or {}).get("setups")
        read = setups.get(setup) if isinstance(setups, dict) else None
        return read if isinstance(read, dict) else None, doc

    adds = []
    for t in out.get("tiles") or []:
        if isinstance(t, dict) and isinstance(t.get("gajjala"), dict):
            sym, setup = str(t.get("symbol") or "").upper(), t["gajjala"].get("setup")
            read, doc = read_of(sym, setup)
            b = block(read, doc, v, pot=pots_by.get((sym, setup)))
            if b is not None:
                adds.append((t["gajjala"], b))
    tr = out.get("track")
    today = tr.get("today") if isinstance(tr, dict) else None
    for row in (today.get("rows") or []) if isinstance(today, dict) else []:
        if isinstance(row, dict):
            sym, setup = str(row.get("symbol") or "").upper(), row.get("setup")
            read, doc = read_of(sym, setup)
            b = row_block(read, doc, v, pot=pots_by.get((sym, setup)))
            if b is not None:
                adds.append((row, b))
    for target, b in adds:
        target["breakout"] = b


__all__ = ["STATES", "CARD_STATES", "SKIP_STATES", "HEAD", "PART", "VOL_WORD", "SEP", "base_peak_volume",
           "read_breakout", "read_forming", "words", "hint", "block", "row_block", "tag"]
