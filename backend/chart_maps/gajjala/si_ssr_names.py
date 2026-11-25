"""⛔🔒🩳 SI / SSR / Reg SHO names on 🚩 Gajjala's pass (2026-11-24, SPEC sissr rev 2 §3.3, WP be-pass).

THE ASK (Ajay 2026-11-24, verbatim, in order): ~23:20 ET "Make this new routine 1. Scan Short interest tabs sotkcs that
become potentials also and also look for new SSR stocks 2. Then potentials to be alerts sooner - add them to watch list
and give them a time stamp of the day" · ~23:35 ET "Days past little bit like AKAN is what I am mainly looking for many
were so confident on SSR..".

A THIRD add source on the 5-minute pass, the 🎪 pattern (promo_names.py): FOUR tagged sources, read from STORED Mongo
reads only (never an outside call from the pass):
  🩳 hsi        the High SI list (high_si.classify on this pass's floats — every 🩳 name is already a pass name)
  ⛔ ssr_today  the Rule 201 restriction triggered today (the ⛔ engine's recent_triggers)
  ⛔ ssr_recent triggered on a recent session and still in force (AKAN: trigger 11/23, "day 2" on 11/24)
  🔒 sho_past   still on a Reg SHO threshold list past its day-13 close-out date (reg_sho.payload(kick=False) — a display
                read: this module never kicks the worker and never reads the run engine directly)
Every READ name is TAGGED (`ctx["si_ssr"]`, tag_block). An off-list ⛔ / 🔒 name that passes GG's add check
(trader_names.candidate_row — the ONE add check) AND ADD_MIN_VOLUME is ADDED (a row `source: "si_ssr"`), at most
ADD_MAX_NEW_PER_PASS NEW adds a cron pass, none on the open (the open's short budget stays GG's). The rest are counted
"queued" and land on a later pass. An ADDED name failed GG's own ≥25% scanner rule, so it is HELD from every push
(run.py hands the push engines the reads WITHOUT it; 🧠 tracks it and holds it `si_ssr_add`) — ringing an added name is
HIS CALL #6. A name GG already lists is only tagged: its 🧠 push rides the UNCHANGED gate with the source leading the
title.

UNMEASURED. SI, SSR and Reg SHO are not GG's playbook; nothing has measured any of them as an entry (⛔ "UNMEASURED",
🔒 "A data label, not a signal"). GG's own detectors and the existing 🧠 gate decide every potential. Nothing here
sizes, ranks for a trade or claims an edge. Every number below is a constant read by name — no number is typed here.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable, Optional

from . import constants as GC
from . import trader_names as TN                                 # the ONE add check (candidate_row)
from . import promo_names as PN                                  # the newest-scan-doc read (added_symbols' twin)

log = logging.getLogger("chart_maps.gajjala.si_ssr_names")

SOURCE = "si_ssr"
SOURCE_KEYS = ("ssr_recent", "sho_past", "ssr_today", "hsi")      # lead precedence (HIS CALL #9)
SOURCES_ON = SOURCE_KEYS                                          # HIS CALL #3 — all four on
ADD_SOURCES = ("ssr_recent", "sho_past", "ssr_today")             # 🩳 is listed by definition (it is read from the pass)
SSR_KEYS = ("ssr_recent", "ssr_today")                            # the two ⛔ keys (one trigger each — the newest wins)
ADD_MIN_VOLUME = GC.SCAN_MIN_VOLUME                               # HIS CALL #4 — GG's floor on the snapshot at the add
ADD_MAX_NEW_PER_PASS = GC.FLOAT_MAX_NEW_PER_PASS                  # HIS CALL #10 — NEW adds per cron pass (C6)
ADD_ON_OPEN = False                                               # HIS CALL #10 — the open's budget stays GG's (C6)
ADD_ON = False                                                    # 2026-11-25 main session: off-list ADDS paused at ship — no TOTAL cap on live
                                                                  # adds exists (review #2) and that number is HIS CALL; GG's own listed names keep
                                                                  # every tag, the 🩳 title and the Watch stamp. True + his cap = adds back on.
ADD_FLAG = "add"                                                  # ctx["si_ssr"]["add"] — the read-doc marker
TRACKER_ADD_FIELD = "si_ssr_add"                                  # insert-only tracker marker (🎪 `promo` precedent)
LEAD_JOIN = " · "
GLYPHS = {"ssr_recent": "⛔", "ssr_today": "⛔", "sho_past": "🔒", "hsi": "🩳"}   # the chip's source glyphs (C11)
COUNT_KEYS = ("si_ssr_added", "si_ssr_tagged", "si_ssr_queued", "si_ssr_skipped", "si_ssr_under_floor",
              "si_ssr_failed", "si_ssr_push_held")
UNDER_FLOOR = "under_floor"
SKIP_REASONS = TN.SKIP_REASONS[:TN.SKIP_REASONS.index("over_cap")] + (UNDER_FLOOR,)   # no cap skip: over the bound = queued
TAGS_KEY = "_tags"                                                # the block's in-memory tag map — never stored (run._finish)
TAG_FIELDS = ("keys", "lead", "text", "glyphs", "ssr_day", "triggered_on", "sho_text", "hsi_text", ADD_FLAG)


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _s(x) -> Optional[str]:
    return x.strip() if isinstance(x, str) and x.strip() else None


def _num(x) -> Optional[float]:
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _int(x) -> Optional[int]:
    v = _num(x)
    return int(v) if v is not None and v == int(v) else None


def _key(sym) -> Optional[str]:
    """The pass's spelling of a list symbol (sepa.symbols.for_yahoo — the snapshot key, as 📌 / 🎪 use)."""
    from sepa import symbols
    s = str(sym or "").strip().upper().lstrip("$")
    return symbols.for_yahoo(s) if s else None


def _iso(session) -> str:
    if isinstance(session, datetime):
        return session.date().isoformat()
    return session.isoformat() if isinstance(session, date) else str(session)


# ── the stored reads (the cron path of run.main; tests inject their own) ──────────────────────────────────────────
def default_reader(now, session) -> dict:
    """{"ssr": the ⛔ engine's recent_triggers(now), "sho": the 🔒 display read payload(kick=False), "faults": [..]} —
    Mongo reads only, never an outside call, never a worker kick. Each source in its OWN try: one that raises is left
    out and named in `faults`; the other stands."""
    out: dict = {"ssr": None, "sho": None, "faults": []}
    try:
        from short_interest import ssr as SSR
        out["ssr"] = SSR.recent_triggers(now)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala si/ssr names: the SSR read failed: %s", type(exc).__name__)
        out["faults"].append("ssr")
    try:
        from short_interest import reg_sho as RSH
        out["sho"] = RSH.payload(kick=False, now=now)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala si/ssr names: the Reg SHO read failed: %s", type(exc).__name__)
        out["faults"].append("sho")
    return out


# ── the tags (PURE) ───────────────────────────────────────────────────────────────────────────────────────────────
def source_tags(read) -> dict:
    """PURE but for the 🔒 words (reg_sho.past_closeout_text). -> {SYM: {key: {"text", ...}}} for the ⛔ / 🔒 keys of
    SOURCES_ON. ⛔: every recent_triggers row with a tag_text — `ssr_today` when its trigger day is the read's `today`,
    else `ssr_recent` (the newest trigger already won in the engine). 🔒: an item still ON a list (`state == "on"`, the
    engine's own word — a stale list's "on" item counts, as the engine's chip shows it) whose run is past its close-out
    date (the engine's words decide: past_closeout_text None → not past). Junk reads add nothing."""
    out: dict = {}
    read = read if isinstance(read, dict) else {}
    ssr = read.get("ssr") if isinstance(read.get("ssr"), dict) else {}
    today = _s(ssr.get("today"))
    by = ssr.get("by_symbol") if isinstance(ssr.get("by_symbol"), dict) else {}
    for sym, r in by.items():
        if not isinstance(r, dict):
            continue
        key, text = _key(sym), _s(r.get("tag_text"))
        if not key or not text:
            continue
        on = _s(r.get("triggered_on"))
        recent, on_today = SSR_KEYS
        k = on_today if (today and on == today) else recent
        if k not in SOURCES_ON:
            continue
        out.setdefault(key, {})[k] = {"text": text, "title": _s(r.get("title")), "triggered_on": on,
                                      "day_n": _int(r.get("day_n"))}
    sho = read.get("sho") if isinstance(read.get("sho"), dict) else {}
    items = sho.get("items") if isinstance(sho.get("items"), dict) else {}
    if "sho_past" in SOURCES_ON and items:
        from short_interest import reg_sho as RSH
        for sym, it in items.items():
            if not isinstance(it, dict) or it.get("state") != "on":
                continue
            try:
                text = _s(RSH.past_closeout_text(it.get("run")))
            except Exception:                                   # noqa: BLE001 — junk run → not past
                text = None
            key = _key(sym)
            if key and text:
                out.setdefault(key, {})["sho_past"] = {"text": text}
    return out


def hsi_tags(names, floats, *, si_read: Optional[Callable] = None, today) -> dict:
    """{SYM: {"text"}} for the names the 🩳 rule LISTS on this pass's floats (high_si.classify — the ONE rule; the chip
    words are high_si.tier_chip's). `si_read(syms) -> {SYM: block} | None` (None = high_si.si_blocks). None from the
    read → RuntimeError (unknown is never tagged)."""
    from . import high_si as HS
    syms = [str(s).upper() for s in names or []]
    if not syms or "hsi" not in SOURCES_ON:
        return {}
    blocks = (si_read or (lambda ss: HS.si_blocks(ss, today=today)))(syms)
    if blocks is None:
        raise RuntimeError("short interest unread")
    out: dict = {}
    for s in syms:
        b = blocks.get(s) if isinstance(blocks, dict) else None
        c = HS.classify(b, (floats or {}).get(s))
        if not c.get("listed"):
            continue
        out[s] = {"text": HS.tier_chip({"tier_word": HS.SR.TIER_WORDS.get(c.get("tier")),
                                        "pct_record": HS._f((b or {}).get("pct_of_float")),
                                        "pct_card": c.get("pct_card"), "float_check": c.get("float_check"),
                                        "si_flags": HS.si_flags(b)})}
    return out


def tag_block(sym, src, hsi, *, add: bool) -> Optional[dict]:
    """ONE name's `ctx["si_ssr"]`: {"keys" (SOURCE_KEYS order), "lead" (the first key's words), "text" (every key's
    words, LEAD_JOIN), "glyphs", "ssr_day", "triggered_on", "sho_text", "hsi_text", "add"}. None when the name has no
    key AND is not an add; an add whose tag lapsed (the 3-session carry) → keys [] and lead None, add True."""
    src = src if isinstance(src, dict) else {}
    hsi = hsi if isinstance(hsi, dict) else {}
    texts: dict = {}
    for k in SOURCE_KEYS:
        if k not in SOURCES_ON:
            continue
        t = _s(hsi.get("text")) if k == "hsi" else _s((src.get(k) or {}).get("text"))
        if t:
            texts[k] = t
    keys = list(texts)
    if not keys and not add:
        return None
    ssr_k = next((k for k in keys if k in SSR_KEYS), None)
    ssr = (src.get(ssr_k) or {}) if ssr_k else {}
    return {"keys": keys, "lead": texts[keys[0]] if keys else None,
            "text": LEAD_JOIN.join(texts[k] for k in keys) or None,
            "glyphs": "".join(dict.fromkeys(GLYPHS[k] for k in keys)) or None,
            "ssr_day": _int(ssr.get("day_n")), "triggered_on": _s(ssr.get("triggered_on")),
            "sho_text": texts.get("sho_past"), "hsi_text": texts.get("hsi"), ADD_FLAG: bool(add)}


def _rank(keys) -> int:
    return min((SOURCE_KEYS.index(k) for k in keys if k in SOURCE_KEYS), default=len(SOURCE_KEYS))


# ── resolve against the pass's snapshot (PURE) ────────────────────────────────────────────────────────────────────
def resolve(tags, rows, session, types, qualifiers, listed, *, on_open: bool) -> dict:
    """-> {"added": [Row], "tagged": [SYM], "kept": [SYM], "queued": [SYM], "skips": {reason: [SYM]}}.
    A name on this pass's rows (GG's qualifier, a 📌 or a 🎪 add) → tagged, never a second row. A name the list already
    carries off a stored doc (`listed`) → kept. Every other ⛔ / 🔒 name runs trader_names.candidate_row (the ONE add
    check), then ADD_MIN_VOLUME on the snapshot volume (under_floor). The rows that pass are ordered (SOURCE_KEYS rank,
    volume desc, symbol); the first ADD_MAX_NEW_PER_PASS are added with {source, si_ssr_keys}, the rest "queued" (a
    later pass adds them). on_open and not ADD_ON_OPEN → nothing added (all queued; the tags still serve)."""
    session_iso = _iso(session)
    by_sym = {str(q.get("symbol")).upper(): q for q in qualifiers or [] if isinstance(q, dict) and q.get("symbol")}
    listed = {str(s).upper() for s in listed or ()}
    tagged, kept, cands = [], [], []
    skips: dict = {}
    for key in sorted(tags or {}):
        t = tags[key] if isinstance(tags[key], dict) else {}
        keys = [k for k in SOURCE_KEYS if k in t and k in ADD_SOURCES]
        if not keys:
            continue
        if key in by_sym:
            tagged.append(key)
            continue
        if key in listed:
            kept.append(key)
            continue
        r, why = TN.candidate_row(key, rows, session_iso, types)
        if why is not None:
            skips.setdefault(why, []).append(key)
            continue
        vol = _num(r.get("volume"))
        if vol is None or vol < ADD_MIN_VOLUME:
            skips.setdefault(UNDER_FLOOR, []).append(key)
            continue
        r.update({"source": SOURCE, "si_ssr_keys": keys})
        cands.append(((_rank(keys), -vol, key), r))
    cands.sort(key=lambda c: c[0])
    room = 0 if (not ADD_ON or (on_open and not ADD_ON_OPEN)) else ADD_MAX_NEW_PER_PASS
    added = [r for _k, r in cands[:room]]
    queued = [r["symbol"] for _k, r in cands[room:]]
    return {"added": added, "tagged": tagged, "kept": kept, "queued": queued,
            "skips": {k: skips[k] for k in SKIP_REASONS if k in skips}}


# ── the pass step (FENCED) ────────────────────────────────────────────────────────────────────────────────────────
def _zero_counts(result: dict, **over) -> None:
    c = dict(result.get("counts") or {})
    c.update(dict.fromkeys(COUNT_KEYS, 0))
    c.update(over)
    result["counts"] = c


def run_step(st, now, session, rows, result: dict, *, types, reader: Callable, good: bool,
             on_open: bool) -> Optional[dict]:
    """After the 🎪 step, before scanner.record_scan — run.py calls it ONLY when Deps.si_ssr_names is wired.
    good False (a failed snapshot) → None, `result` untouched. FENCED: any raise (the reader included) → logged,
    {"error": type name}, nothing added, counts si_ssr_* = 0 and si_ssr_failed = 1. Otherwise appends the added Rows to
    result["qualifiers"]; result["counts"] gains COUNT_KEYS. -> {added, tagged, kept, queued, skips, names, on_open,
    faults, TAGS_KEY: {SYM: source tags}} — TAGS_KEY is in-memory only (ctx_tags reads it; run._finish never stores it).
    (2026-11-25: the land-order interlock that held every add until the Watch's C2 filter landed is DROPPED — be-pass
    and be-watch ship in ONE commit, so the Watch's C2 filter `_si_ssr_adds` is always in the same tree; the Watch's own
    si_ssr tests pin it.)"""
    try:
        if not good:
            return None
        read = reader(now, session) or {}
        tags = source_tags(read)
        quals = list(result.get("qualifiers") or [])
        from . import scanner as SC
        listed = set(SC.listed_symbols(st, session))
        res = resolve(tags, rows, session, types, quals, listed, on_open=on_open)
        result["qualifiers"] = quals + res["added"]
        _zero_counts(result, si_ssr_added=len(res["added"]), si_ssr_tagged=len(res["tagged"]) + len(res["kept"]),
                     si_ssr_queued=len(res["queued"]),
                     si_ssr_skipped=sum(len(v) for k, v in res["skips"].items() if k != UNDER_FLOOR),
                     si_ssr_under_floor=len(res["skips"].get(UNDER_FLOOR) or []))
        faults = read.get("faults") if isinstance(read, dict) and isinstance(read.get("faults"), list) else []
        blk = {"added": [r["symbol"] for r in res["added"]], "tagged": res["tagged"], "kept": res["kept"],
               "queued": res["queued"], "skips": res["skips"], "names": len(tags), "on_open": bool(on_open),
               "faults": list(faults), TAGS_KEY: tags}
        return blk
    except Exception as exc:                                    # noqa: BLE001
        log.exception("gajjala si/ssr names: the step failed — the pass goes on without it")
        try:
            _zero_counts(result, si_ssr_failed=1)
        except Exception:                                       # noqa: BLE001
            pass
        return {"error": type(exc).__name__}


def _add_sources() -> tuple:
    return (TN.SOURCE, PN.SOURCE, SOURCE)


def recount(result: dict) -> None:
    """After scanner.record_scan, trader_names.recount and promo_names.recount: qualifiers = GG's rows only (no 📌, 🎪
    or ⛔🔒 add); si_ssr_added = the ⛔🔒 adds — ONLY when the step counted (a pass without it keeps its counts' shape)."""
    q = [r for r in result.get("qualifiers") or [] if isinstance(r, dict)]
    c = result.setdefault("counts", {})
    if any(r.get("source") == SOURCE for r in q):
        c["qualifiers"] = sum(1 for r in q if r.get("source") not in _add_sources())
    if "si_ssr_added" in c:
        c["si_ssr_added"] = sum(1 for r in q if r.get("source") == SOURCE)


def _block_ok(block) -> bool:
    return isinstance(block, dict) and "error" not in block


def trim_block(block, result: dict) -> None:
    """After scanner.record_scan (the 📌 F1 rule, promo_names.trim_block's twin): a name the split hold-out dropped
    leaves `added` / `tagged`, and counts["si_ssr_tagged"] follows. A failed block is left as is."""
    if not _block_ok(block):
        return
    rows = {str(q.get("symbol")) for q in result.get("qualifiers") or [] if isinstance(q, dict)}
    block["added"] = [s for s in block.get("added") or [] if s in rows]
    block["tagged"] = [s for s in block.get("tagged") or [] if s in rows]
    c = result.get("counts")
    if isinstance(c, dict) and "si_ssr_tagged" in c:
        c["si_ssr_tagged"] = len(block["tagged"]) + len(block.get("kept") or [])


def note_push_held(block, result: dict, n: int) -> None:
    """run.py, once the reads exist: the number of ADDED names read this pass that the push engines never see (C1)."""
    if not _block_ok(block):
        return
    block["push_held"] = int(n)
    c = result.get("counts")
    if isinstance(c, dict) and "si_ssr_push_held" in c:
        c["si_ssr_push_held"] = int(n)


def stored_block(block) -> Optional[dict]:
    """The pass doc's copy: the block without its in-memory keys (TAGS_KEY)."""
    if not isinstance(block, dict):
        return None
    return {k: v for k, v in block.items() if k != TAGS_KEY}


def added_symbols(scan_docs, rows=()) -> set:
    """PURE. The ⛔🔒 ADDS (rows `source == "si_ssr"`) the push hold binds — promo_names.added_symbols' twin: a row of
    this pass decides; a name with no row this pass reads its newest `gajjala_scan` doc (an add kept listed by
    STAY_LISTED_SESSIONS stays an add, held, for the whole carry)."""
    by = {s: last.get("source") == SOURCE for s, last in PN._newest(scan_docs).items()}
    for r in rows or ():
        if isinstance(r, dict) and r.get("symbol"):
            by[str(r["symbol"]).upper()] = r.get("source") == SOURCE
    return {s for s, a in by.items() if a}


def is_add(doc) -> bool:
    """A read doc whose ctx["si_ssr"][ADD_FLAG] is True, or a 🧠 tracker doc whose TRACKER_ADD_FIELD is True."""
    if not isinstance(doc, dict):
        return False
    if doc.get(TRACKER_ADD_FIELD) is True:
        return True
    ctx = doc.get("ctx") if isinstance(doc.get("ctx"), dict) else {}
    tag = ctx.get(SOURCE) if isinstance(ctx.get(SOURCE), dict) else {}
    return tag.get(ADD_FLAG) is True


def ctx_tags(block, names, floats, adds, *, today, si_read: Optional[Callable] = None) -> dict:
    """{SYM: tag_block} for the names READ this pass — FENCED → {} on a raise. ⛔ / 🔒 from the step's block (a failed
    or absent block → none), 🩳 from hsi_tags in its OWN fence (a failed short-interest read drops only the 🩳 keys),
    `add` = the name is one of this pass's ⛔🔒 adds (`adds`, added_symbols)."""
    try:
        src = block.get(TAGS_KEY) if isinstance(block, dict) else None
        src = src if isinstance(src, dict) else {}
        try:
            hsi = hsi_tags(names, floats, si_read=si_read, today=today)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala si/ssr names: the 🩳 tag read failed: %s", type(exc).__name__)
            hsi = {}
        adds = {str(s).upper() for s in adds or ()}
        out: dict = {}
        for s in names or []:
            u = str(s).upper()
            tb = tag_block(u, src.get(u), hsi.get(u), add=u in adds)
            if tb is not None:
                out[u] = tb
        return out
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala si/ssr names: the tags failed: %s", type(exc).__name__)
        return {}


# ── served words ──────────────────────────────────────────────────────────────────────────────────────────────────
def rules_clause() -> str:
    """The ℹ️ sentence — every number a constant read at call time."""
    from short_interest import ssr as SSR
    days = SSR.SSR_RECENT_TRIGGER_DAYS
    glyphs = "".join(dict.fromkeys(GLYPHS[k] for k in SOURCE_KEYS))
    return (f"{glyphs} SI / SSR / Reg SHO names (your call 2026-11-24 — “Days past little bit like AKAN is what I am "
            f"mainly looking for”): every name GG's pass reads is tagged 🩳 High SI, ⛔ SSR today, ⛔ SSR started up to "
            f"{days} market day(s) before today, or 🔒 past its Reg SHO close-out date. An off-list ⛔ / 🔒 name inside "
            f"GG's ${GC.SCAN_MIN_PRICE:.2f}–${GC.SCAN_MAX_PRICE:g} band, your instrument rule and "
            f"{ADD_MIN_VOLUME:,} shares today joins the pass — at most {ADD_MAX_NEW_PER_PASS} new a pass, none on the "
            "open — and is read by GG's rules but never rings: it failed GG's own scanner change rule. A name GG "
            "already lists rings through the unchanged 🧠 rules with every source in the title — a 🩳 name's tier and "
            "short-interest % are in every 🧠 alert title, also beside ⛔ / 🔒. SI, SSR and Reg "
            "SHO are not GG's playbook — UNMEASURED.")


__all__ = ["SOURCE", "SOURCE_KEYS", "SOURCES_ON", "ADD_SOURCES", "SSR_KEYS", "ADD_MIN_VOLUME", "ADD_MAX_NEW_PER_PASS",
           "ADD_ON_OPEN", "ADD_ON", "ADD_FLAG", "TRACKER_ADD_FIELD", "LEAD_JOIN", "GLYPHS", "COUNT_KEYS", "SKIP_REASONS",
           "TAGS_KEY", "TAG_FIELDS",
           "default_reader", "source_tags", "hsi_tags", "tag_block", "resolve", "run_step",
           "recount", "trim_block", "note_push_held", "stored_block", "added_symbols", "is_add", "ctx_tags",
           "rules_clause"]
