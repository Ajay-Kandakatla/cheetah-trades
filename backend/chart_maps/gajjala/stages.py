"""🧭 Setup stages — the setups a stock passed through on his list, as tags on every Gajjala card (2026-11-11).

Ajay 2026-11-11 ~08:39 ET, verbatim:
  "Another big thing I need is what stages a stock has crossed in the past like

   Bullflag -> EMA Kiss and Fly -> and Horizontal -Fade so I know their stages may be add them like tags or some UI to
   show me stages with time stamps if its same day"

DISPLAY ONLY. No gate, no rule, no threshold, no number, no push, no order change, no write, no fetch. HISTORY, not a
signal: nothing here claims an edge.

A "stage" = one of GG's five setups the stock was in, in time order; each tag says how far that setup got
(🧠 potential · 🎯 A+ · triggered · stopped). Two sources, both read by tab._stage_tag ONCE per board, never per card:
  1. the 🧠 tracker's own `state_path` (potential.track — the ONE engine that records a setup's states through a
     session; every stamp = the PASS clock that first saw the state);
  2. the live A+ alerts that RANG, through tab._entry_times (store.alert_rows + ledger.alert_of, line "live") — merged
     ONLY where the tracker path has no A+ step (an A+ can ring before the setup ever read as a potential).
A clock only for today's session ("time stamps if its same day"); every other session shows its date only.

This module is a pure view over that one engine: no store, no clock, no I/O, no datetime parsing. It imports only
`constants` (plus the standard library); tab.py imports it, never the other way round.
"""
from __future__ import annotations

import copy
import re
from datetime import date
from typing import Optional

from . import constants as GC

# ── the served words: the ONLY place they are typed (the frontend types none) ────────────────────────────────────
TITLE = "🧭 Setup stages"
MILESTONE_STATES = ("aplus", "triggered", "stopped")          # == tab.MARKED_STATES (a test pins equality)
STAGES = ("potential",) + MILESTONE_STATES                    # the ladder, in GG's order
STAGE_WORDS = {"potential": "🧠 potential", "aplus": "🎯 A+", "triggered": "triggered", "stopped": "stopped"}
#   each milestone word's LAST token == the FIRST word of tab.state_label for that state ("A+", "triggered",
#   "stopped" — the pill on the same card); a test pins it
STEP_SEP = " · "                                             # between the steps inside one tag
TAG_SEP = " → "                                              # between tags: his own arrow ("Bullflag -> EMA Kiss and Fly -> …")
TODAY_LABEL = "today"
HINT = ("The setups this stock passed through on his list, oldest first. Today's steps show the {n}-minute pass time "
        "(ET) that first saw them; earlier sessions show the date only. A setup shows here once it was a 🧠 potential "
        "or its 🎯 A+ alert rang — today's and the last session's full path are on the 🧠 Potential sub's 📈 Track.")
BORROWED_TEXT = " On this tab the steps are 🚩 Gajjala's own reads and alerts (shared), before the audit."
_HHMM = re.compile(r"^\d\d:\d\d$")
_LAST = "~"                                                  # sorts after every "HH:MM" (a tag with no clock goes last)


def stage_of(entry) -> Optional[str]:
    """One `state_path` entry → its stage, or None (partial / invalid / none / graveyard / a forming read with no base
    / malformed / not a dict). Building and trigger armed both count as "potential"."""
    if not isinstance(entry, dict):
        return None
    st = entry.get("state")
    if st == GC.POTENTIAL_STATE and entry.get("kind") in GC.POTENTIAL_KINDS:
        return "potential"
    if isinstance(st, str) and st in MILESTONE_STATES:
        return st
    return None


def clock_of(x) -> Optional[str]:
    """`x` when it is an ET "HH:MM" string, else None ("9:5", None, 930, "", "09:52:00" → None)."""
    return x if isinstance(x, str) and _HHMM.match(x) else None


def _fold(raw: list) -> list:
    out = []
    for s in raw:
        if out and out[-1]["stage"] == s["stage"]:
            continue                                          # consecutive equal stages fold — the FIRST one stays
        out.append(s)
    return out


def steps(doc: Optional[dict], *, entry_at: Optional[str] = None) -> list:
    """RAW steps (clocks kept; tag() blanks them): the tracker path in stored order, never-steps dropped, consecutive
    equal stages folded (the first entry kept). `entry_at` = the clock of a live A+ that RANG for this (session,
    symbol, setup): merged ONLY when the path has no A+ step, at the first step whose clock is later (one ET day, so
    the "HH:MM" strings order), else appended. A path that already has its A+ is never changed by it. Nothing else is
    ever added — a triggered / stopped with no A+ and no rang alert stays as seen."""
    path = doc.get("state_path") if isinstance(doc, dict) else None
    raw = []
    for e in path if isinstance(path, list) else ():
        s = stage_of(e)
        if s is None:
            continue
        raw.append({"stage": s, "word": STAGE_WORDS[s], "at_et": clock_of(e.get("at_et"))})
    raw = _fold(raw)
    at = clock_of(entry_at)
    if at is not None and not any(s["stage"] == "aplus" for s in raw):
        step = {"stage": "aplus", "word": STAGE_WORDS["aplus"], "at_et": at}
        i = next((k for k, s in enumerate(raw) if s["at_et"] is not None and s["at_et"] > at), len(raw))
        raw.insert(i, step)
        raw = _fold(raw)
    return raw


def tag(setup: str, raw: list, *, clock: bool) -> Optional[dict]:
    """One served tag of (setup, its raw steps). None for a setup outside GC.SETUPS or no step. `clock` False → every
    served `at_et` is None and the text carries no time."""
    if setup not in GC.SETUPS or not raw:
        return None
    meta = {k: (e, label) for k, e, label in GC.SUBS}
    emoji, label = meta[setup]
    served = [{"stage": s["stage"], "word": s["word"], "at_et": s["at_et"] if clock else None} for s in raw]
    text = f"{emoji} {label}" + STEP_SEP + STEP_SEP.join(f"{s['word']} {s['at_et']}" if s["at_et"] else s["word"]
                                                         for s in served)
    return {"setup": setup, "emoji": emoji, "label": label, "steps": served, "text": text}


def sort_key(raw: list, setup: str) -> tuple:
    """Tags in one session order by their first step's ET clock, then GG's SETUPS order — strings and ints only, never a
    datetime; a tag with no clock sorts last."""
    first = clock_of(raw[0].get("at_et")) if raw and isinstance(raw[0], dict) else None
    order = GC.SETUPS.index(setup) if setup in GC.SETUPS else len(GC.SETUPS)
    return (first or _LAST, order, str(setup))


def day_label(d: date) -> str:
    """"Mon 11-10" — the house day label (== ledger._dow_md, a test pins it)."""
    return f"{d:%a} {d:%m-%d}"


def hint(cadence_min: int, *, borrowed: bool = False) -> str:
    return HINT.format(n=cadence_min) + (BORROWED_TEXT if borrowed else "")


def by_symbol(sessions: dict, *, board_session: date, is_today: bool, symbols, cadence_min: int,
              borrowed: bool = False, entries: Optional[dict] = None) -> dict:
    """{SYM: block} for the card symbols. `sessions` = {date: [tracker docs]}; `entries` = tab._entry_times' answer
    {(date_iso, SYM, setup): "HH:MM"} (None → {}). Only symbols in `symbols` are read; a symbol with no tag has no
    entry. Per session: one tag per (SYM, setup) from its doc (first doc wins) with that key's rang A+ merged, plus a
    claim-only tag for a rang A+ whose (SYM, setup) has no doc. Groups oldest session first; a clock only on the board
    session when it is today."""
    entries = entries if isinstance(entries, dict) else {}
    syms = {str(s).upper() for s in symbols or () if s}
    groups_by: dict = {}
    for d in sorted(d for d in (sessions or {}) if isinstance(d, date)):
        iso = d.isoformat()
        docs: dict = {}
        for doc in sessions.get(d) or []:
            if not isinstance(doc, dict):
                continue
            sym, setup = str(doc.get("symbol") or "").upper(), doc.get("setup")
            if sym not in syms or not isinstance(setup, str) or setup not in GC.SETUPS:
                continue
            if isinstance(doc.get("date"), str) and doc["date"] != iso:
                continue                                      # a doc of another session never lands in this one
            docs.setdefault((sym, setup), doc)                # the first doc wins on a dup id
        raws = {k: steps(doc, entry_at=entries.get((iso, k[0], k[1]))) for k, doc in docs.items()}
        for key, at in entries.items():
            if not (isinstance(key, tuple) and len(key) == 3 and key[0] == iso):
                continue
            sym, setup = str(key[1] or "").upper(), key[2]
            if sym in syms and setup in GC.SETUPS and (sym, setup) not in raws:
                raws[(sym, setup)] = steps(None, entry_at=at)   # an A+ that rang with no tracker doc
        clock = bool(d == board_session and is_today)
        label = TODAY_LABEL if clock else day_label(d)
        per: dict = {}
        for (sym, setup), raw in raws.items():
            t = tag(setup, raw, clock=clock)
            if t is not None:
                per.setdefault(sym, []).append((sort_key(raw, setup), t))
        for sym, pairs in per.items():
            pairs.sort(key=lambda p: p[0])
            groups_by.setdefault(sym, []).append({"date": iso, "label": label, "clock": clock,
                                                  "tags": [t for _k, t in pairs]})
    out = {}
    for sym, groups in groups_by.items():
        out[sym] = {"title": TITLE, "hint": hint(cadence_min, borrowed=borrowed), "sep": TAG_SEP, "groups": groups,
                    "text": TAG_SEP.join(f"{g['label']}: " + TAG_SEP.join(t["text"] for t in g["tags"])
                                         for g in groups)}
    return out


def for_tile(block: dict, setup: Optional[str], board_session: date) -> dict:
    """A deep copy of the symbol's block for ONE card: a tag is `here` only when it is the card's own setup in the board
    session (☀️ / 🌙 cards: none)."""
    out = copy.deepcopy(block)
    iso = board_session.isoformat()
    for g in out.get("groups") or []:
        for t in g.get("tags") or []:
            t["here"] = bool(g.get("date") == iso and setup is not None and t.get("setup") == setup)
    return out


__all__ = ["TITLE", "MILESTONE_STATES", "STAGES", "STAGE_WORDS", "STEP_SEP", "TAG_SEP", "TODAY_LABEL", "HINT",
           "BORROWED_TEXT", "stage_of", "clock_of", "steps", "tag", "sort_key", "day_label", "hint", "by_symbol",
           "for_tile"]
