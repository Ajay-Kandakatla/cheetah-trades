"""🗂 Watch sections — group, order and the served per-tile words (2026-11-22, spec watch_org rev 4 §3.3, WP-BE).

Ajay 2026-11-22, verbatim: "I need gajjalas watch tab little more organized. With less info, I want to know previous day
winner auto additions vs intraday may be a time stamp. or something figure out a better way to organize that info for
me.." — then: "Manual ones I add them need to be on top then auto intraday..".

Sections, his order: 👤 Your names → 🎯 A+ (🤖) → 🤖 Added today (premarket, intraday and after-hours adds in ONE
section, newest first). A row's group comes from SESSION-STABLE facts only — his name or a 🤖 entry, and the entry's
`why` [C2]; never the live card state, the A+ items, the entry's setup or the 📅 read. 📅 is a tile CHIP only [D3] (the
📅 Ran section arrives with the 04:00 auto-add — a separate spec; `group_of` never returns it here).

Every row gets `org = {group, when, setup, ran, past_winner}`:
  * `when`  — "added 10:42" / "added premarket 07:12" / "added after hours 17:48" / "re-added 10:21" on a 🤖 tile; "👤 added
    08:15" / "👤 added 11-19" / "👤 yours" on his;
  * `setup` — the tile's setup chip, 🎾 Reversal Squeeze picked first (his 11-22 "I will most focus on reversal squeezes
    going forward..") — the 🚩 card's own label words (tab._setup_label), display only;
  * `ran`   — runners.ran_of on the session before the board's session (ONE read for every name);
  * `past_winner` — 🎬's own 🏆 tag (replays.store.past_wins_before), wins that ended strictly before the session.
Reads: ONE `runners.ran_for` (1 scan find + 1 reads find) and ONE cached 🏆 index; a fault in either → that field None
on every row, the groups untouched. Display only — UNMEASURED.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from . import colls as CO
from . import constants as C

log = logging.getLogger("chart_maps.gajjala_watch.sections")
ET = ZoneInfo("America/New_York")
RS_SETUP = "reversal_squeeze"                     # == GC.SETUPS member (a test pins it) — 🎾 picked first
SETUP_SOURCES = ("board", "entry")                # the chip's source: today's 🚩 card, else the 🤖 entry's setup


def _runners():
    from . import runners as RN
    return RN


def _et(t: datetime) -> datetime:
    return t.astimezone(ET)


def _entry_time(entry: dict, session: date) -> Optional[datetime]:
    """The 🤖 entry's add time in ET: `added_at` (stored UTC), else `added_et` "HH:MM" on `session`; else None."""
    t = CO.stamp_utc(entry.get("added_at"))
    if t is not None:
        return _et(t)
    hhmm = entry.get("added_et")
    if isinstance(hhmm, str):
        try:
            hm = datetime.strptime(hhmm.strip(), "%H:%M").time()
        except ValueError:
            return None
        return datetime.combine(session, hm, tzinfo=ET)
    return None


def _bucket(t: datetime) -> str:
    from catalysts.medical.reaction import rth_close_time
    from daytrading.data import ET_RTH_OPEN
    if t.time() < ET_RTH_OPEN:
        return "premarket"
    if t.time() < rth_close_time(t.date()):
        return "intraday"
    return "after_hours"


def _removed_at(removed: Optional[list], sym: str, before: Optional[datetime]) -> Optional[str]:
    """The latest removal of `sym` (fold-matched) this session as ET "HH:MM" — at or before `before` when that is known."""
    k = CO.fold(sym)
    best = None
    for r in removed or []:
        if not isinstance(r, dict) or CO.fold(r.get("symbol")) != k:
            continue
        at = CO.stamp_utc(r.get("at"))
        if before is not None and at is not None and at > before.astimezone(timezone.utc):
            continue
        key = at or datetime.min.replace(tzinfo=timezone.utc)
        if best is None or key >= best[0]:
            word = r.get("at_et") if isinstance(r.get("at_et"), str) and r.get("at_et") else (
                _et(at).strftime("%H:%M") if at is not None else None)
            best = (key, word)
    if best is None:
        return None
    return best[1] or "—"


def when_block(entry: Optional[dict], his_at: Optional[datetime], session: date,
               removed_at: Optional[str] = None) -> Optional[dict]:
    """{bucket, verb, at_et, date, text, title} — a 🤖 entry's add time (verb "re-added" when `removed_at`, the ET
    clock of its earlier removal this session, is given) or his own name's (`his_at`, aware UTC or None)."""
    if entry is not None:
        t = _entry_time(entry, session)
        if t is None:
            return None
        bucket = _bucket(t)
        verb = C.WHEN_VERBS[1] if removed_at else C.WHEN_VERBS[0]
        at = t.strftime("%H:%M")
        title = C.WHEN_TITLE.format(verb=verb, date=t.strftime("%m-%d"), at=at, where=C.WHEN_WHERE[bucket])
        if removed_at:
            title += C.WHEN_READD_TITLE.format(rm_at=removed_at)
        return {"bucket": bucket, "verb": verb, "at_et": at, "date": t.date().isoformat(),
                "text": C.WHEN_TEXT[bucket].format(verb=verb, at=at), "title": title}
    t = CO.stamp_utc(his_at)
    if t is None:
        return {"bucket": None, "verb": None, "at_et": None, "date": None, "text": C.WHEN_HIS_UNDATED, "title": None}
    t = _et(t)
    at = t.strftime("%H:%M")
    text = (C.WHEN_HIS_TEXT.format(at=at) if t.date() == session
            else C.WHEN_HIS_DAY_TEXT.format(md=t.strftime("%m-%d")))
    return {"bucket": None, "verb": C.WHEN_VERBS[0], "at_et": at, "date": t.date().isoformat(), "text": text,
            "title": None}


def setup_block(row: dict, entry: Optional[dict]) -> Optional[dict]:
    """{setup, label, state_label, source, text, title} — the tile's ONE setup chip (`text` = the label the FE prints,
    `title` = the state words on hover): today's 🚩 card setups (row.tags.setups), else the
    🤖 entry's setup; 🎾 Reversal Squeeze first, else the first one. Display only (live words, never a group input)."""
    from chart_maps.gajjala import constants as GC
    from chart_maps.gajjala import tab
    tags = row.get("tags") if isinstance(row, dict) else None
    cands = []
    for s in (tags.get("setups") if isinstance(tags, dict) and isinstance(tags.get("setups"), list) else []):
        if isinstance(s, dict) and s.get("setup") in GC.SETUPS:
            cands.append((s["setup"], s.get("state_label") if isinstance(s.get("state_label"), str) else None,
                          SETUP_SOURCES[0]))
    es = entry.get("setup") if isinstance(entry, dict) else None
    if isinstance(es, str) and es in GC.SETUPS and all(c[0] != es for c in cands):
        cands.append((es, None, SETUP_SOURCES[1]))
    if not cands:
        return None
    pick = next((c for c in cands if c[0] == RS_SETUP), cands[0])
    label = tab._setup_label(pick[0])
    return {"setup": pick[0], "label": label, "state_label": pick[1], "source": pick[2],
            "text": label, "title": pick[1]}


def past_block(idx, sym: str, session_iso: str) -> Optional[dict]:
    """🎬's own 🏆 tag fields (`past_winner`, `past_winner_count`, `past_winner_more_text`) for wins that ENDED strictly
    before `session_iso`, plus `text` (the newest) and `title` (every served item) — None when none / no index."""
    if not idx:
        return None
    from chart_maps.replays import constants as RC
    from chart_maps.replays import store as RS
    out = RS.past_wins_before(idx, CO.house(sym), session_iso, RC.PAST_WIN_DAY_WORDS)
    if not out or not out.get("past_winner"):
        return None
    items = [w["text"] for w in out["past_winner"] if isinstance(w, dict) and isinstance(w.get("text"), str)]
    more = out.get("past_winner_more_text")
    return dict(out, text=items[0] if items else None, title=" · ".join(items + ([more] if more else [])) or None)


def group_of(entry: Optional[dict]) -> str:
    """[D3] session-stable only: his name → "yours"; a 🎯 A+ seat → "aplus"; any other 🤖 entry → "auto"."""
    if entry is None:
        return C.SECTION_KEYS[0]
    if isinstance(entry, dict) and entry.get("why") == C.AUTO_APLUS_WHY:
        return C.SECTION_KEYS[1]
    return C.SECTION_KEYS[2]


def _ts(v) -> Optional[float]:
    t = CO.stamp_utc(v)
    return t.timestamp() if t is not None else None


def order(rows: list, groups: dict, entries: dict) -> list:
    """Rows in SECTION_ORDER; inside: 👤 his order as served (newest added first); 🎯 newest A+ first (`aplus_at`, else
    `added_at`); 🤖 newest added first; an undated 🤖 last; a tie keeps the served order."""
    def key(ix):
        i, r = ix
        sym = r["symbol"]
        g = groups[sym]
        e = entries.get(sym) or {}
        if g == C.SECTION_KEYS[0]:
            inner = (0, 0.0)
        elif g == C.SECTION_KEYS[1]:
            t = _ts(e.get("aplus_at"))
            t = t if t is not None else _ts(e.get("added_at"))
            inner = (0, -t) if t is not None else (1, 0.0)
        else:
            t = _ts(e.get("added_at"))
            inner = (0, -t) if t is not None else (1, 0.0)
        return (C.SECTION_ORDER.index(g), inner, i)
    return [r for _i, r in sorted(enumerate(rows), key=key)]


def sections_block(rows: list, *, session: date) -> list:
    """[{key, title, text, hint, n, symbols}] — the non-empty groups in SECTION_ORDER (rows already ordered)."""
    from chart_maps.gajjala import tab
    prev = tab._prev_market_day(session)
    out = []
    for k in C.SECTION_ORDER:
        syms = [r["symbol"] for r in rows if (r.get("org") or {}).get("group") == k]
        if not syms:
            continue
        title = C.SECTION_WORDS[k]
        out.append({"key": k, "title": title, "text": C.SECTION_TEXT.format(title=title, n=len(syms)),
                    "hint": C.SECTION_HINTS[k].format(date=prev.strftime("%m-%d")), "n": len(syms),
                    "symbols": syms})
    return out


def _ran_by(names: list, session: date) -> dict:
    from chart_maps.gajjala import tab
    try:
        return _runners().ran_for(names, tab._prev_market_day(session))
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: 📅 ran read unavailable: %s", type(exc).__name__)
        return {}


def _past_idx():
    rr = _runners()._replays()
    if rr is None:
        return None
    RS = rr[0]
    try:
        return RS._past_index(RS.root_dir())
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: past-winner index unavailable: %s", type(exc).__name__)
        return None


def apply(rows: list, *, entries: dict, removed: list, his_added: dict, session: date) -> tuple:
    """(rows in section order, each with `org`; sections). A fault grouping / ordering → (rows unchanged, every `org`
    None; None). The 📅 / 🏆 reads fail soft per field."""
    try:
        entries = entries if isinstance(entries, dict) else {}
        groups = {r["symbol"]: group_of(entries.get(r["symbol"])) for r in rows}
        ordered = order(rows, groups, entries)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: sections unavailable: %s", type(exc).__name__)
        for r in rows:
            r["org"] = None
        return rows, None
    ran_by = _ran_by([r["symbol"] for r in rows], session)
    idx = _past_idx()
    siso = session.isoformat()[:10]
    for r in ordered:
        sym = r["symbol"]
        e = entries.get(sym)
        org = {"group": groups[sym], "when": None, "setup": None, "ran": None, "past_winner": None}
        try:
            if e is not None:
                org["when"] = when_block(e, None, session, _removed_at(removed, sym, _entry_time(e, session)))
            else:
                org["when"] = when_block(None, (his_added or {}).get(CO.fold(sym)), session)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala_watch: when word unavailable: %s", type(exc).__name__)
        try:
            org["setup"] = setup_block(r, e)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala_watch: setup chip unavailable: %s", type(exc).__name__)
        org["ran"] = ran_by.get(CO.fold(sym))
        try:
            org["past_winner"] = past_block(idx, sym, siso)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala_watch: past winner unavailable: %s", type(exc).__name__)
        r["org"] = org
    try:
        sections = sections_block(ordered, session=session)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala_watch: section heads unavailable: %s", type(exc).__name__)
        sections = None
    return ordered, sections
