"""🌀 AMD — the manipulation-cycle column on the 🔥 Hottest board.

Ajay, 2026-09-22, with a screenshot of the 🔥 Hottest tab showing the Defense
roster expanded (KRMN, RCAT, LASR, KTOS, ONDS, BBAI):

    "Add an AMD tag for these. like a column for me to see which one are getting
     manipulated. Also give me toggle option to open them app on one click in
     stead of clicking on the carets"

WHAT THIS MODULE IS
───────────────────
A CACHED READ of the document the nightly sweep already wrote. `supply_demand.
turning_bullish.warm` walks the universe at 17:20 ET on weekdays and stores one
Mongo document (`turning_bullish`, `_id: latest`); the 🌀 AMD tab in Chart Maps
draws that same document. This module indexes it by symbol and hangs one cell
on every NAME row of the 🔥 board. It does not compute a verdict, and it must
never learn how to: `turning_bullish` says so in its own words — the verdict
needs a 500-bar frame per name and "loading 2,800 of those while he waits is
how a tab times out at the open". ONE engine, one wording table
(`TB.verdict_text`), so the column and the 🌀 tab can never disagree.

IT IS MEASURED INVERTED ON ITS OWN CLAIM
────────────────────────────────────────
Re-measured 2026-09-14 on 3,712 names / 1,592,057 bars: it fires on 15.1% of
bars, forward returns are negative at every horizon, and like-for-like against a
bar inside its OWN live base at the same distance below the top it reaches the
base top LESS often — 51.9% vs 56.1%, −4.2pp [−6.92, −1.89], negative in all
seven distance buckets. The board's own freshest cut is worse: −5.6pp
[−8.97, −2.69]. Script `backend/scripts/turning_bullish_amd_study.py`, written
up in `docs/supply_demand/turning_bullish.md`.

THEREFORE (Rule #10 — an executor changes no rule, no gate, no threshold):
this column **sorts nothing, filters nothing, orders nothing, colours nothing
and gates nothing**. `"amd"` is never added to `rotation.hottest.SORT_KEYS`. No
count is placed on a sector / industry / roster row, because those rows' other
cells are medians over the FULL membership while this payload carries 25 names
per group — two populations. The board-level counts ride in ONE served sentence
under the table, built from the counts THIS request actually made.

FAILURE IS QUIET AND TOTAL
──────────────────────────
`TB.stored()` returns `{}` on any failure and never raises, so "no document"
and "Mongo down" arrive identically; both serve `store_unavailable`. `attach`
never raises. `unavailable()` exists so `rotation/api.py`'s except branch has
something that cannot itself fail — and the alias is bound at MODULE scope
there, so a broken import of this file drops the column instead of 500-ing the
whole 🔥 board.
"""
from __future__ import annotations

import logging
import time as _time
from datetime import datetime, time, timedelta
from typing import Optional

from sepa import symbols as SY                       # the shipped symbol-fate layer
from supply_demand import turning_bullish as TB      # the ONE AMD engine + wording

log = logging.getLogger("rotation.hottest_amd")

ROW_KEY = "amd"                 # the per-NAME-row key
SUMMARY_KEY = "amd_summary"     # the board-level block (sibling of d1 / pre)

# The stored document is 2.54 MB / 2,682 rows. RE-MEASURED in the api
# container 2026-09-22 00:58 ET, one fresh python process per read (import +
# connect + `find_one`): cold 0.14 s, first warm 0.01 s, steady 0.007-0.012 s.
# The 5.73 s cold figure quoted when this was specced did NOT reproduce, so
# the cache is a cheap guard against re-indexing 2,682 rows on every request,
# not a rescue from a slow read — and it is sized by the endpoint's OWN
# existing window (`rotation.api._MEMBERS_TTL_SEC`), pinned equal by test, so
# no number is invented here either way.
_AMD_TTL_SEC = 5 * 60
# {"ts": float, "built_at": str|None, "ix": {SYM: verdict}, "meta": {...}}
_index_cache: dict = {}

# Transcribed from `backend/crontab`:
#   20     17    *    *    1-5  … -m market_hours.gate supply_demand.turning_bullish warm
# i.e. 17:20 ET, weekdays only. Pinned against that line by test (read-only —
# the crontab is host-mounted and is never edited from here), never retyped as
# a judgement.
SWEEP_ET_HOUR, SWEEP_ET_MINUTE = 17, 20

SOURCE = ("supply_demand.turning_bullish — the nightly sweep's stored document "
          "(Mongo `turning_bullish`, _id `latest`), the SAME document the 🌀 AMD tab "
          "in Chart Maps draws. Never recomputed on this request.")
CRON_NOTE = ("Written by the weekday sweep (17:20 ET, Mon-Fri) — so before 17:20 on a "
             "trading day, and all weekend, this read is the previous sweep's and says so.")

REASONS = ("not_in_store", "store_unavailable", "no_verdict")
REASON_TEXT = {
    # The words "no cycle" / "clean" are deliberately NOT in this sentence:
    # they are the words of a REAL read (`TB.AMD_TEXT["none"]` is "AMD no
    # cycle"), and a blank must never wear them. It says the same thing in
    # words the column cannot be misread as having measured.
    "not_in_store": (
        "Not read: this name is not in the nightly AMD sweep, so this app has no AMD "
        "cycle for it. A blank here means UNKNOWN — it is not a verdict, and it does "
        "not say the name is un-manipulated."),
    "store_unavailable": (
        "Not read: the nightly AMD sweep document could not be read, so no name on this "
        "board has an AMD state right now."),
    "no_verdict": (
        "Not read: the sweep has this name but produced no gradeable AMD cycle for it."),
}

# Every figure below appears VERBATIM in supply_demand/turning_bullish.py's own
# docstring; tests/test_hottest_amd.py pins each string against it (whitespace-
# normalised). Never retyped onto a surface, never rounded here.
AMD_MEASURED = {
    "date": "2026-09-14",
    "population": "3,712 names / 1,592,057 bars",
    "fire_rate": "Fires on 15.1% of bars.",
    "forward": "5d −0.36% [−0.77, −0.06], 10d −0.48% [−1.07, −0.02], "
               "21d −0.41% [−1.11, +0.15]",
    "claim": "51.9% vs 56.1%, −4.2pp [−6.92, −1.89]",
    "buckets": "negative in all seven distance buckets",
    "fresh_cut": "The board's own 0-3 cut is worse: −5.6pp [−8.97, −2.69]",
    "script": "backend/scripts/turning_bullish_amd_study.py",
    "doc": "docs/supply_demand/turning_bullish.md",
}

HONESTY = (
    "🌀 AMD is the app's manipulation read: the module's own cycle phase — a base was "
    "built, its low was swept and price CLOSED back inside (raided), or the markup "
    "happened (marked up), or the base gave way (base failed). IT IS MEASURED INVERTED "
    "ON ITS OWN CLAIM. Re-measured {date} on {population}: {fire_rate} Forward returns "
    "are negative at every horizon ({forward}). Like-for-like against a bar inside its "
    "OWN live base at the same distance below the top it reaches the base top LESS "
    "often — {claim}, {buckets}. The board's own freshest cut is worse still: "
    "{fresh_cut}. So this is a STATE, not a ranking and not a quality score: a fresh "
    "raid is not a reason to buy, and this app measured it going the other way. It "
    "sorts nothing, filters nothing, orders nothing, colours nothing and gates nothing. "
    "Re-runnable: {script}; written up in {doc}."
).format(**AMD_MEASURED)

HEAD_TITLE = ("Which AMD cycle phase this name is in, from the nightly sweep. "
              + HONESTY + " — = not read; hover the cell for why.")

GROUP_NOTE = (
    "No AMD state on a sector, industry or roster row. A cycle phase has no median, and "
    "a count over the names printed here would describe a different population from the "
    "medians beside it (those are the full membership). The board-level line under the "
    "table carries the counts.")

NO_SORT_REASON = (
    "This column does not sort. Ranking the board on a read measured inverted against "
    "its own placebo ({claim}) would order names by something measured to go the wrong "
    "way.").format(**AMD_MEASURED)

NO_COLOUR_REASON = (
    "This column is deliberately colourless. The 🌀 AMD tab paints “raided” green, but "
    "that is the exact state measured {claim} against its own placebo — a green cell "
    "read at a glance down 600 rows is a ranking, and this read is not one. The words "
    "are the read; the hover carries the measurement.").format(**AMD_MEASURED)

UNAVAILABLE_NOTE = (
    "🌀 AMD: the nightly sweep document could not be read, so the AMD column is not "
    "shown. Nothing on this board changed — it is the read that is missing, not the "
    "names.")

LABEL = "🌀 AMD"

_ROW_KEYS = ("known", "grade", "phase", "text", "tone", "title",
             "bars_ago", "base_bars", "reason", "reason_text")

_MISS = object()          # "this symbol is not in the sweep at all"


# ---------------------------------------------------------------------------
# Scrubbing
# ---------------------------------------------------------------------------
def _num(v) -> Optional[float]:
    """NaN / ±inf -> None. A NaN survives every arithmetic step and then passes
    EVERY `<=` comparison, so one bad bar silently reorders a board; the
    endpoint's JSON scrub runs far too late to protect anything that sorts."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


# ---------------------------------------------------------------------------
# The index over the sweep's rows
# ---------------------------------------------------------------------------
def _index(doc: Optional[dict]) -> dict:
    """{SYMBOL: verdict-or-None} for every row in the sweep, plus one alias per
    renamed ticker.

    A renamed ticker looks EXACTLY like a legitimate miss — the cell goes blank
    and nothing says why — so both sides resolve through `sepa.symbols.resolve`,
    the shipped symbol-fate layer. The alias never overwrites a direct hit.
    """
    ix: dict = {}
    for r in (doc or {}).get("rows") or []:
        if not isinstance(r, dict):
            continue
        sym = str(r.get("symbol") or "").strip().upper()
        if sym:
            ix[sym] = r.get("amd")
    for sym in list(ix):
        try:
            alias = SY.resolve(sym)
        except Exception:                                      # noqa: BLE001
            continue
        if alias and alias != sym and alias not in ix:
            ix[alias] = ix[sym]
    return ix


def _lookup(ix: dict, symbol) -> object:
    s = str(symbol or "").strip().upper()
    if not s:
        return _MISS
    if s in ix:
        return ix[s]
    try:
        a = SY.resolve(s)
    except Exception:                                          # noqa: BLE001
        a = s
    return ix[a] if a in ix else _MISS


# ---------------------------------------------------------------------------
# The ET clock and the DUE sweep
# ---------------------------------------------------------------------------
def _board():
    """`chart_maps.board`, lazily. It owns the ONE session-date rule and the
    shipped ET tz object; it is 4k lines, so it is not imported at module
    load."""
    from chart_maps import board as B
    return B


def _et_tz():
    try:
        return _board().ET
    except Exception:                                          # noqa: BLE001
        # Only reached when the board module cannot be imported at all. Same
        # zone, stdlib, used to print the stamp — the SESSION rule is never
        # guessed at (see `_sessions`: it returns None for all of it).
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/New_York")


def _due_session(now_et):
    """The last sweep that was DUE.

    `board._session_day` has NO time-of-day test — it returns TODAY from
    midnight — while the sweep writes at 17:20 ET. So a naive
    `built_at_date < last_session` is True every weekday morning, which is
    exactly when he reads this board. Before 17:20 on a session day, the
    newest sweep that was due is the PREVIOUS session's.
    """
    B = _board()
    last = B._session_day(now_et)
    if now_et.date() == last and now_et.time() < time(SWEEP_ET_HOUR, SWEEP_ET_MINUTE):
        last = B._session_day(now_et - timedelta(days=1))
    return last


def _built_at_et(built_at_iso: Optional[str]):
    """The stored UTC stamp as an aware ET datetime, or None.

    `warm()` stamps `datetime.now(timezone.utc)` — UTC, not ET. A manual
    re-warm after 20:00 ET carries the NEXT UTC date, and a UTC-vs-ET date
    comparison would print a date that has not happened in his timezone and
    pin `stale` False forever.
    """
    if not built_at_iso:
        return None
    try:
        dt = datetime.fromisoformat(str(built_at_iso).replace("Z", "+00:00"))
    except Exception:                                          # noqa: BLE001
        return None
    tz = _et_tz()
    if dt.tzinfo is None:
        from datetime import timezone as _tzmod
        dt = dt.replace(tzinfo=_tzmod.utc)
    try:
        return dt.astimezone(tz)
    except Exception:                                          # noqa: BLE001
        return None


def _sessions(built_at_iso: Optional[str], now=None) -> dict:
    """The built_at / session / staleness block. Never raises, never guesses."""
    et = _built_at_et(built_at_iso)
    out = {"built_at": built_at_iso,
           "built_at_et": et.isoformat() if et is not None else None,
           "built_at_date": et.date().isoformat() if et is not None else None,
           "last_session": None, "due_session": None,
           "stale": None, "stale_note": None}
    try:
        tz = _board().ET
        now_et = (now or datetime.now(tz)).astimezone(tz)
        last = _board()._session_day(now_et)
        due = _due_session(now_et)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("rotation/amd: session calendar unavailable: %s", exc)
        return out
    out["last_session"] = last.isoformat()
    out["due_session"] = due.isoformat()
    if out["built_at_date"] is None:
        return out
    out["stale"] = out["built_at_date"] < out["due_session"]
    out["stale_note"] = (
        "The AMD sweep runs weekdays at %02d:%02d ET. This read is from %s; the newest "
        "sweep that was due is %s." % (SWEEP_ET_HOUR, SWEEP_ET_MINUTE,
                                       out["built_at_date"], out["due_session"]))
    return out


# ---------------------------------------------------------------------------
# One cell
# ---------------------------------------------------------------------------
def blank(reason: str = "not_in_store") -> dict:
    """The fully-shaped unknown cell. Every key, always — the frontend reads
    ONE shape everywhere instead of testing for presence."""
    r = reason if reason in REASONS else "not_in_store"
    return {"known": False, "grade": None, "phase": None, "text": None,
            "tone": None, "title": REASON_TEXT[r], "bars_ago": None,
            "base_bars": None, "reason": r, "reason_text": REASON_TEXT[r]}


def read_one(sym: str, verdict: Optional[dict]) -> dict:
    """One name's cell. PURE, never raises.

    `known` is gated on membership in `TB.AMD_GRADES` on purpose:
    `verdict_text` does `table.get(grade) or table["none"]`, so an ungradeable
    row would be handed the words of a real read ("AMD no cycle") — and the
    live sweep shows that grade never legitimately occurs, so any such cell
    would be a fallback wearing a verdict's clothes.
    """
    try:
        if not isinstance(verdict, dict):
            return blank("no_verdict")
        grade = verdict.get("grade")
        text, tone = TB.verdict_text("amd", verdict)
        if not text or grade not in TB.AMD_GRADES:
            return blank("no_verdict")
        age = (verdict.get("raid_bars_ago") if grade in ("raided", "stale")
               else verdict.get("failed_bars_ago") if grade == "failed"
               else verdict.get("bars_ago") if grade == "marked_up" else None)
        return {"known": True, "grade": grade,
                "phase": verdict.get("phase"),
                "text": text, "tone": tone,
                "title": "%s: %s. %s" % (str(sym or "").upper(), text, HONESTY),
                "bars_ago": _num(age), "base_bars": _num(verdict.get("base_bars")),
                "reason": None, "reason_text": None}
    except Exception as exc:                                   # noqa: BLE001
        log.debug("rotation/amd(%s): unreadable verdict: %s", sym, exc)
        return blank("no_verdict")


# ---------------------------------------------------------------------------
# The store read, behind the endpoint's own TTL
# ---------------------------------------------------------------------------
def cache_clear() -> None:
    """Tests only."""
    _index_cache.clear()


def _doc_meta(doc: Optional[dict]) -> dict:
    d = doc or {}
    # `built_at` is what `turning_bullish.warm` stamped, which is UTC. It is
    # served as the raw stamp for provenance, and `built_at_utc` marks the zone
    # so a future consumer cannot read the naive string as local time; the
    # SURFACE reads `built_at_et`, which carries its own offset.
    return {"available": bool(d),
            "built_at": TB._iso(d.get("built_at")),
            "built_at_utc": True,
            "n_scanned": _num(d.get("n_scanned")),
            "n_rows": _num(d.get("n_rows"))}


def by_symbol(doc: Optional[dict] = None, *, now=None) -> tuple:
    """`(index, doc_meta)`. ONE `TB.stored()` per cache miss.

    `doc=` bypasses the cache entirely — that is the injectable path the tests
    and any caller with a document in hand use.
    """
    if doc is not None:
        meta = _doc_meta(doc)
        meta.update(_sessions(meta["built_at"], now=now))
        return _index(doc), meta

    # Read the entry ONCE. `_index_cache` holds a single "entry" key that is
    # rebound whole, so a reader either sees the old entry or the new one and
    # never a half-written dict.
    ent = _index_cache.get("entry")
    if not ent or (_time.time() - float(ent.get("ts") or 0)) >= _AMD_TTL_SEC:
        try:
            d = TB.stored()
        except Exception as exc:                               # noqa: BLE001
            log.warning("rotation/amd: store read failed: %s", exc)
            d = {}
        meta = _doc_meta(d)
        ix = _index(d)
        # A MISS is never cached — the same rule `rotation.api._members_table`
        # follows: a Mongo blip must not blank the column for five minutes when
        # the document is sitting right there.
        if meta["available"]:
            # ONE rebinding, not clear()-then-update(): a concurrent request
            # landing between the two saw an empty dict and paid for a second
            # `TB.stored()` find_one. Cost only, never a wrong payload, but the
            # whole point of this cache is to not do that.
            _index_cache["entry"] = {"ts": _time.time(),
                                     "built_at": meta["built_at"],
                                     "ix": ix, "meta": meta}
    else:
        ix, meta = ent["ix"], dict(ent["meta"])

    meta = dict(meta)
    meta.update(_sessions(meta["built_at"], now=now))
    return ix, meta


# ---------------------------------------------------------------------------
# The board block
# ---------------------------------------------------------------------------
def _grade_label(grade: str) -> str:
    """"raided" -> "raided", "marked_up" -> "marked up" — from `TB.AMD_TEXT`,
    never a second wording table here."""
    base = (TB.AMD_TEXT.get(grade) or ("",))[0]
    return base[4:] if base.startswith("AMD ") else (base or grade)


# Why a name is blank, in the words the sentence uses. Keyed by `REASONS` so a
# new refusal cannot be added without deciding how it reads here.
_BLANK_PHRASE = {
    "not_in_store": "not in the nightly sweep",
    "no_verdict": "swept but the cycle could not be read",
    "store_unavailable": "the sweep was unreadable",
}


def _blank_clause(n_blank: int, blank_reasons: Optional[dict]) -> str:
    """"(7 not in the nightly sweep)" — built from the COUNTS, never assumed.

    The first version of this sentence hardcoded "not in the nightly sweep"
    for every blank. That happens to read true while `no_verdict` is 0, and
    becomes a lie the first morning a swept name fails to produce a cycle: the
    board would say a name was never looked at when it was looked at and came
    back unreadable. Every clause now comes from `blank_reasons`.
    """
    if not n_blank:
        return ""
    counts = {k: int(v or 0) for k, v in (blank_reasons or {}).items()
              if k in _BLANK_PHRASE and (v or 0) > 0}
    if not counts:
        # n_blank without a reason breakdown: say the count and nothing else
        # rather than inventing which refusal it was.
        return " (%d blank)" % n_blank
    if len(counts) == 1:
        (reason, _), = counts.items()
        return " (%d %s)" % (n_blank, _BLANK_PHRASE[reason])
    bits = ["%d %s" % (counts[r], _BLANK_PHRASE[r]) for r in REASONS if counts.get(r)]
    return " (" + ", ".join(bits) + ")"


def _coverage_note(n: int, n_known: int, n_blank: int, grades: dict,
                   built_at_et: Optional[str],
                   blank_reasons: Optional[dict] = None) -> str:
    bits = ["%s %d" % (_grade_label(g), grades.get(g, 0))
            for g in TB.AMD_GRADES if grades.get(g)]
    swept = "sweep date unknown"
    if built_at_et:
        swept = "swept %s ET" % str(built_at_et)[:16].replace("T", " ")
    parts = ["%s read for %d of %d names on this board%s"
             % (LABEL, n_known, n, _blank_clause(n_blank, blank_reasons))]
    if bits:
        parts.append(", ".join(bits))
    parts.append(swept)
    return (" · ".join(parts)
            + ". Measured INVERTED against its own placebo (%s) — a state, not a "
              "ranking." % AMD_MEASURED["claim"])


def _summary(*, available: bool, n: int, n_known: int, n_blank: int,
             grades: dict, blank_reasons: dict, meta: dict,
             unavailable_note: Optional[str]) -> dict:
    return {
        "available": bool(available),
        "n": n, "n_known": n_known, "n_blank": n_blank,
        "blank_reasons": blank_reasons, "grades": grades,
        "grade_order": list(TB.AMD_GRADES),
        "built_at": meta.get("built_at"),
        "built_at_et": meta.get("built_at_et"),
        "built_at_date": meta.get("built_at_date"),
        "last_session": meta.get("last_session"),
        "due_session": meta.get("due_session"),
        "stale": meta.get("stale"), "stale_note": meta.get("stale_note"),
        "n_scanned": meta.get("n_scanned"), "n_rows": meta.get("n_rows"),
        "source": SOURCE, "cron": CRON_NOTE, "measured": dict(AMD_MEASURED),
        "honesty": HONESTY, "head_title": HEAD_TITLE, "group_note": GROUP_NOTE,
        "no_sort_reason": NO_SORT_REASON, "sortable": False,
        "no_colour_reason": NO_COLOUR_REASON, "coloured": False,
        "coverage_note": _coverage_note(n, n_known, n_blank, grades,
                                        meta.get("built_at_et"), blank_reasons),
        "unavailable_note": unavailable_note,
        "label": LABEL,
    }


def unavailable(reason: str = "store_unavailable") -> dict:
    """The full `amd_summary` shape with `available False`.

    `rotation/api.py`'s except branch references this, so it must exist and
    must never raise: it is the thing that runs when everything else already
    failed.
    """
    try:
        r = reason if reason in REASONS else "store_unavailable"
        return _summary(available=False, n=0, n_known=0, n_blank=0,
                        grades={g: 0 for g in TB.AMD_GRADES},
                        blank_reasons={k: 0 for k in REASONS},
                        meta={}, unavailable_note=UNAVAILABLE_NOTE
                        if r == "store_unavailable" else REASON_TEXT[r])
    except Exception:                                          # noqa: BLE001
        return {"available": False, "n": 0, "n_known": 0, "n_blank": 0,
                "label": LABEL, "unavailable_note": UNAVAILABLE_NOTE,
                "sortable": False, "coloured": False}


# ---------------------------------------------------------------------------
# attach
# ---------------------------------------------------------------------------
def _name_rows(body: dict):
    """Every NAME row on the board, once per row object.

    Themes are flat rosters; a sector carries both its own `names` and its
    industries' `names`, and the same symbol legitimately appears in both — the
    ROW gets a cell each time, the COUNT sees the symbol once.
    """
    for t in (body or {}).get("themes") or []:
        if isinstance(t, dict):
            for r in t.get("names") or []:
                if isinstance(r, dict):
                    yield r
    for s in (body or {}).get("sectors") or []:
        if not isinstance(s, dict):
            continue
        for r in s.get("names") or []:
            if isinstance(r, dict):
                yield r
        for i in s.get("industries") or []:
            if not isinstance(i, dict):
                continue
            for r in i.get("names") or []:
                if isinstance(r, dict):
                    yield r


def attach(body: dict, *, doc: Optional[dict] = None, now=None) -> dict:
    """Hang one AMD cell on every NAME row, in place, and return the summary.

    ORDER IS NEVER TOUCHED. This takes the ALREADY-BUILT board body, so
    ranking, truncation and every existing key are untouched by construction —
    it adds one key per name row and nothing else. Group rows get nothing at
    all (see `GROUP_NOTE`). Never raises.
    """
    try:
        ix, meta = by_symbol(doc, now=now)
        available = bool(meta.get("available"))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("rotation/amd: read failed: %s", exc)
        ix, meta, available = {}, {}, False

    seen: dict = {}
    for r in _name_rows(body):
        sym = str(r.get("symbol") or "").strip().upper()
        if not available:
            cell = blank("store_unavailable")
        else:
            v = _lookup(ix, sym)
            cell = blank("not_in_store") if v is _MISS else read_one(sym, v)
        r[ROW_KEY] = cell
        if sym and sym not in seen:
            seen[sym] = cell

    grades = {g: 0 for g in TB.AMD_GRADES}
    blank_reasons = {k: 0 for k in REASONS}
    n_known = 0
    for cell in seen.values():
        if cell.get("known"):
            n_known += 1
            g = cell.get("grade")
            if g in grades:
                grades[g] += 1
        else:
            rsn = cell.get("reason")
            if rsn in blank_reasons:
                blank_reasons[rsn] += 1
    n = len(seen)
    return _summary(available=available, n=n, n_known=n_known,
                    n_blank=n - n_known, grades=grades,
                    blank_reasons=blank_reasons, meta=meta,
                    unavailable_note=None if available else UNAVAILABLE_NOTE)
