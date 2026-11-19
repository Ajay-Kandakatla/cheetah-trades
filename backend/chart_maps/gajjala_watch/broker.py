"""🚫 his broker list on 👀 Gajjala's Watch — the served words (2026-11-19, spec watchfid §3.2, WP-B).

Ajay 2026-11-19, verbatim: "Add a button to say not in fidelity, AZI and CHSN are not in fidelity don't add them to watch
list".

ONE list, ONE engine: `chart_maps.gajjala.store.broker_flags` (the gajjala_state doc "broker_flags", "." == "-"). This
module only SERVES what the owner's Watch GET needs, read ONCE per GET:
  * every row's `broker_text` (tab.broker_text_for — the 🚩 card's own word; None when the name is not on the list or
    the list could not be read — never the seed guess);
  * the board's `broker` block (BROKER_KEYS): the one-way 🚫 button's icon / title, `editable` (False on a read fault),
    the fault line, and the 🤖 auto engine's last-step words (`not_eligible` names it kept off, `broker_fault`) read from
    the loop state doc of THIS session only;
  * the 🤖 hover hint gains the auto engine's ONE phrase (`auto.broker_words()`) before its final "UNMEASURED." — a
    VALUE change only, the auto block's key set is untouched;
  * `add_note`: his own typed add of a listed name still lands (HIS CALL #1) and its answer carries the word.

Every word is composed from tab.BROKER_FLAG_TEXT / BROKER_FLAG_ICON / BROKER_FAULT_TEXT and auto.broker_words(); the
broker's name is never typed here. Display only — nothing is written, nothing rings. UNMEASURED.
"""
from __future__ import annotations

import importlib
import logging
from typing import Optional

from chart_maps.gajjala import store as GS
from chart_maps.gajjala import tab as GT

log = logging.getLogger("chart_maps.gajjala_watch.broker")

BROKER_KEYS = ("toggle", "text", "title", "editable", "fault_text", "auto_text", "auto_fault_text")
MARK_TITLE_TEXT = "{text} — mark it and take it off your 👀 watch"
FAULT_LINE_TEXT = "{icon} {fault}"                                   # tab.BROKER_FAULT_TEXT behind the icon
AUTO_KEPT_OFF_TEXT = "{icon} not seated by 🤖 auto — on your list: {names}"
AUTO_FAULT_TEXT = "{icon} your list could not be read at the last minute — 🤖 auto did not check it"
ADD_NOTE_TEXT = "{text} · {word}"
NOTE_STATES = ("added", "replaced", "already")
HINT_TAIL = "UNMEASURED."
AUTO_STATE_KEYS = ("not_eligible", "broker_fault")                   # the loop state doc's auto keys (WP-A seam)


def _store():
    """The 🚩 five-minute tab's store — the ONE broker list lives there (tests replace this function, the tags._store
    pattern)."""
    return GS.default()


def read() -> tuple:
    """(flags tuple | None, fault) — ONE `store.broker_flags` read. A fault or a raise → (None, True): the tags are off,
    never the seed guess."""
    try:
        syms, fault = GS.broker_flags(_store())
    except Exception as exc:                                            # noqa: BLE001
        log.warning("gajjala_watch: broker list unavailable: %s", type(exc).__name__)
        return None, True
    if fault:
        return None, True
    return tuple(s for s in (syms or ()) if isinstance(s, str)), False


def text_for(sym, flags) -> Optional[str]:
    """The row word — tab's own rule ("." == "-"); None for an unlisted name or unknown flags."""
    return GT.broker_text_for(sym, flags)


def auto_lines(state_doc, siso) -> tuple:
    """(auto_text, auto_fault_text) from the loop state doc's `auto` block — ONLY when that doc is of THIS session.
    Old docs (keys absent) / another session / no names → (None, None)."""
    if not isinstance(state_doc, dict) or not isinstance(siso, str) or not siso or state_doc.get("session") != siso:
        return None, None
    blk = state_doc.get("auto")
    if not isinstance(blk, dict):
        return None, None
    raw = blk.get(AUTO_STATE_KEYS[0])
    names = [n.strip() for n in raw if isinstance(n, str) and n.strip()] if isinstance(raw, list) else []
    text = AUTO_KEPT_OFF_TEXT.format(icon=GT.BROKER_FLAG_ICON, names=", ".join(names)) if names else None
    fault = AUTO_FAULT_TEXT.format(icon=GT.BROKER_FLAG_ICON) if blk.get(AUTO_STATE_KEYS[1]) is True else None
    return text, fault


def _broker_words() -> Optional[str]:
    """The auto engine's ONE phrase, imported lazily through sys.modules (the payload's AUTO_MODULE). Any failure → None."""
    from . import payload as PL
    try:
        w = importlib.import_module(PL.AUTO_MODULE).broker_words()
    except Exception as exc:                                            # noqa: BLE001
        log.debug("gajjala_watch: auto broker words unavailable: %s", type(exc).__name__)
        return None
    return w if isinstance(w, str) and w.strip() else None


def hint_with_rule(hint):
    """The 🤖 hover hint with the auto engine's phrase as a sentence right before its final HINT_TAIL. No phrase, a hint
    not ending HINT_TAIL, or the phrase already in it → the hint unchanged."""
    if not isinstance(hint, str) or not hint.endswith(HINT_TAIL):
        return hint
    w = _broker_words()
    if not w:
        return hint
    sentence = w[0].upper() + w[1:]
    if w in hint or sentence in hint:
        return hint
    return hint[:-len(HINT_TAIL)] + sentence + ". " + HINT_TAIL


def board_block(fault, state_doc, siso) -> dict:
    """The board's `broker` block — keys == BROKER_KEYS. `editable` False on a read fault (the button is not offered)."""
    auto_text, auto_fault_text = auto_lines(state_doc, siso)
    return {"toggle": GT.BROKER_FLAG_ICON, "text": GT.BROKER_FLAG_TEXT,
            "title": MARK_TITLE_TEXT.format(text=GT.BROKER_FLAG_TEXT), "editable": not fault,
            "fault_text": FAULT_LINE_TEXT.format(icon=GT.BROKER_FLAG_ICON, fault=GT.BROKER_FAULT_TEXT) if fault else None,
            "auto_text": auto_text, "auto_fault_text": auto_fault_text}


def _rows(out) -> list:
    rows = out.get("rows") if isinstance(out, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def apply(out, *, state_doc=None, siso=None) -> None:
    """ONE list read → every dict row's `broker_text`, the board's `broker` block, and the 🤖 hint's sentence. Never
    raises: any fault → every row None + a fault block (None when even that cannot be composed)."""
    if not isinstance(out, dict):
        return
    try:
        flags, fault = read()
        for r in _rows(out):
            r["broker_text"] = text_for(r.get("symbol"), flags)
        out["broker"] = board_block(fault, state_doc, siso)
    except Exception as exc:                                            # noqa: BLE001
        log.warning("gajjala_watch: broker words failed: %s", type(exc).__name__)
        for r in _rows(out):
            r["broker_text"] = None
        try:
            out["broker"] = board_block(True, None, None)
        except Exception:                                               # noqa: BLE001
            out["broker"] = None
    try:
        a = out.get("auto")
        if isinstance(a, dict):
            a["hint"] = hint_with_rule(a.get("hint"))
    except Exception as exc:                                            # noqa: BLE001 — the hint stays as it was
        log.warning("gajjala_watch: broker hint failed: %s", type(exc).__name__)


def add_note(out) -> dict:
    """His add answer + " · " + the word when the name is on the list (read OK). Never blocks, never adds a key; a fault,
    an unlisted name, another state or any raise → `out` unchanged."""
    try:
        if not isinstance(out, dict) or out.get("state") not in NOTE_STATES:
            return out
        sym, text = out.get("symbol"), out.get("text")
        if not isinstance(sym, str) or not isinstance(text, str):
            return out
        flags, fault = read()
        if fault or not text_for(sym, flags):
            return out
        return dict(out, text=ADD_NOTE_TEXT.format(text=text, word=GT.BROKER_FLAG_TEXT))
    except Exception as exc:                                            # noqa: BLE001
        log.warning("gajjala_watch: broker add note failed: %s", type(exc).__name__)
        return out


__all__ = ["BROKER_KEYS", "MARK_TITLE_TEXT", "FAULT_LINE_TEXT", "AUTO_KEPT_OFF_TEXT", "AUTO_FAULT_TEXT", "ADD_NOTE_TEXT",
           "NOTE_STATES", "HINT_TAIL", "read", "text_for", "auto_lines", "hint_with_rule", "board_block", "apply",
           "add_note"]
