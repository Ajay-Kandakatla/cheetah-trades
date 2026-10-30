"""🎪 Promo-circuit names on 🚩 Gajjala's list (2026-10-29, BUILD_SPEC32 D1–D4).

THE ASK (Ajay 2026-10-29 ~20:05 ET, verbatim, spelling kept): "Also I see a some of stocks we see are also in Gajjalas
page. Don't see some should we pull stocks from PROMO circuit by default every day they are having some good catched but
I do wanna run them against Gajjalas strategies". The 📌 trader-add pattern (trader_names.py), its own source: the names
the 🎪 Promo circuit TAGGED on the session's ET date (a first tag or a later one — the page's "today" rule,
PromoCircuit.tsx: the ET date of the doc's last tag) join this pass's candidate list AFTER his scanner and the 📌 step
and BEFORE the split hold-out + `gajjala_scan` write, so the hold-out, listing, STAY_LISTED_SESSIONS, the detectors,
K1–K11, the no-risk guard, both push gates and the 🏁 ledger run on them unchanged.

WHAT JOINS: the stored `promo_circuit_tags` docs ONLY (never a sweep or a StockTwits fetch from the pass), roster
accounts only, shotgun one-off mentions dropped by promo_circuit.prune_shotgun_tags over the page's own
TAG_WINDOW_DAYS window; each name then passes the SAME add check as a 📌 name (trader_names.candidate_row: snapshot,
dated session, prior close, his instrument rule, GG's price band — NO change floor, NO volume floor for the ADD);
ordered by today's % change, highest first, cut at GC.PROMO_NAMES_MAX (HIS CALL #1) A SESSION — the cap bounds the
names LISTED as 🎪 adds today (a name an earlier pass added keeps its slot and is re-read first; a new name only fills the
room left; critic F3 2026-10-29), never a per-pass count — every name past the cap is COUNTED (`promo_over_cap`), never
silently dropped. A name already on the list (GG's qualifier or a 📌 add) is TAGGED
(`promo` True + `promo_text` on THAT row; a 📌 add keeps `trader` too — two chips), never a second row.
GG's 1M floor stays on EVERY push: a 🎪 add's 🧠 push is HELD while the session volume the pass read is under
GC.SCAN_MIN_VOLUME (potential.py, PROMO_HOLD_TEXT — the 📌 hold's one mechanism, its own reason and words); the A+ is K11.

INVERTED / UNMEASURED: the Promo circuit's first tags read INVERTED in this app's study (docs/catalysts/
promo_tag_study_2026_09_21.md); nothing has measured GG's setups on these names. The add is a WATCHLIST feed for GG's
rules, not an edge — every served sentence below says so. Nothing here sizes, ranks for a trade or claims an edge.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from . import constants as GC
from . import trader_names as TN                                 # the ONE add check, the floor clause, under_floor

log = logging.getLogger("chart_maps.gajjala.promo_names")

ET = ZoneInfo("America/New_York")
SOURCE = "promo"
TAG = GC.PROMO_TAG
SKIP_REASONS = TN.SKIP_REASONS                                   # the same reasons, in the same order
SKIP_WORDS = {
    "not_in_snapshot": "not in today's market snapshot",
    "not_dated_session": "no print dated today yet",
    "no_prev_close": "no prior regular close on file",
    "type_out": "not common stock or an ADR",
    "out_of_band": f"outside GG's ${GC.SCAN_MIN_PRICE:.2f}–${GC.SCAN_MAX_PRICE:g} band",
    "over_cap": f"past the {GC.PROMO_NAMES_MAX}-name cap (a lower % change today)",
}
CAVEAT = ("the Promo circuit's first tags read INVERTED in this app's study — a watchlist for GG's rules, not an edge; "
          "UNMEASURED on his setups")
STRIP_TEXT = ("{tag} {n} of today's {total} Promo-circuit names on this pass's list ({added} added, {tagged} already "
              "listed) — your call 2026-10-29; " + CAVEAT + "; GG's rules decide every read and every A+, and "
              + TN.FLOOR_CLAUSE)
SKIP_HEAD = "{tag} not on the list: "
HOLD_WORDS = f"{TAG} under GG's {GC.SCAN_MIN_VOLUME // 1_000_000}M volume floor — listed and read, not rung"
PROMO_HOLD_TEXT = f"held: {HOLD_WORDS}"                          # the 📈 track row and /alerts serve it verbatim
HOLD_REASON = "promo_under_floor"                                # the `held` reason potential.PROMO_HELD records
COUNT_KEYS = ("promo_added", "promo_tagged", "promo_skipped", "promo_over_cap", "promo_failed")


# ── the roster (catalysts.promo_circuit — the page's own) ─────────────────────────────────────────────────────────
def _pc():
    from catalysts import promo_circuit as PC
    return PC


def _tier(doc: dict, roster: dict) -> str:
    """The LIVE roster's tier (the page's rule: a stored tier is a snapshot), else the doc's, else "B"."""
    return (roster.get(doc.get("account")) or {}).get("tier") or doc.get("tier") or "B"


def text_for(handle, tier, first_et) -> Optional[str]:
    """"🎪 promo · first tag HH:MM ET · @handle · tier S" — None without a handle."""
    if not isinstance(handle, str) or not handle.strip():
        return None
    bits = [f"{TAG} promo"]
    if isinstance(first_et, str) and first_et:
        bits.append(f"first tag {first_et} ET")
    bits.append(f"@{handle.strip()}")
    if isinstance(tier, str) and tier:
        bits.append(f"tier {tier}")
    return " · ".join(bits)


# ── the session's names (PURE) ────────────────────────────────────────────────────────────────────────────────────
def _utc(x) -> Optional[datetime]:
    return TN._at(x)


def _as_date(session) -> date:
    return TN._as_date(session)


def _tag_times(doc: dict) -> list:
    """Every stamp a doc carries for a tag: first_tagged_at, last_tagged_at and each kept post's `at` (aware UTC)."""
    out = [_utc(doc.get("first_tagged_at")), _utc(doc.get("last_tagged_at"))]
    for p in doc.get("posts") or []:
        if isinstance(p, dict):
            out.append(_utc(p.get("at")))
    return [t for t in out if t is not None]


def names_for(now, session, tags: list, *, roster: Optional[dict] = None) -> list:
    """PURE. -> [{symbol, account, tier, first_at (ISO UTC), first_et "HH:MM", accounts: [handle]}], symbol order.

    `tags` = stored `promo_circuit_tags` docs. The page's own read first: roster accounts only, last tag inside
    promo_circuit.TAG_WINDOW_DAYS of `now`, then promo_circuit.prune_shotgun_tags over THAT window (a shotgun account's
    one-off mention is dropped — the window decides, never today's slice). A doc then counts iff one of its tag stamps
    (first_tagged_at, last_tagged_at, a kept post) falls on the session's ET date and is ≤ now. One name per ticker:
    `first_et` = its earliest such stamp; the named account = the best tier (S, A, B), then the earliest tag that day."""
    PC = _pc()
    roster = PC.PROMO_ACCOUNTS if roster is None else roster
    now_u = TN._utc(now)
    day = _as_date(session)
    lo = now_u - timedelta(days=PC.TAG_WINDOW_DAYS)
    fresh = []
    for d in tags or []:
        if not isinstance(d, dict) or d.get("account") not in roster or not d.get("ticker"):
            continue
        last = _utc(d.get("last_tagged_at"))
        if last is None or last < lo:
            continue
        fresh.append(d)
    kept = PC.prune_shotgun_tags(fresh)
    best: dict = {}
    for d in kept:
        times = [t for t in _tag_times(d) if t <= now_u and t.astimezone(ET).date() == day]
        sym = str(d["ticker"]).strip().upper().lstrip("$")
        if not times or not sym:
            continue
        first, tier = min(times), _tier(d, roster)
        rank = (PC.TIER_ORDER.get(tier, 9), first)
        cur = best.setdefault(sym, {"rank": None, "first": first, "accounts": set()})
        cur["accounts"].add(str(d["account"]))
        cur["first"] = min(cur["first"], first)                 # the earliest tag that day, whoever made it
        if cur["rank"] is None or rank < cur["rank"]:
            cur.update(rank=rank, account=str(d["account"]), tier=tier)
    out = []
    for sym in sorted(best):
        b = best[sym]
        out.append({"symbol": sym, "account": b["account"], "tier": b["tier"], "first_at": b["first"].isoformat(),
                    "first_et": b["first"].astimezone(ET).strftime("%H:%M"), "accounts": sorted(b["accounts"])})
    return out


# ── resolve against the pass's snapshot (PURE but for the tag set on a listed row) ────────────────────────────────
def _text(n: dict) -> Optional[str]:
    return text_for(n.get("account"), n.get("tier"), n.get("first_et"))


def listed_today(scan_docs) -> set:
    """PURE. The 🎪 adds already LISTED today: the session's `gajjala_scan` docs whose `last.source` is "promo" (an
    earlier pass wrote them; scanner.listed_symbols keeps them listed whatever this pass reads). Each holds a cap slot."""
    out = set()
    for d in scan_docs or []:
        last = d.get("last") if isinstance(d, dict) else None
        if isinstance(last, dict) and last.get("source") == SOURCE and d.get("symbol"):
            out.add(str(d["symbol"]).upper())
    return out


def resolve(names: list, rows: dict, session, types: Optional[dict], qualifiers: list, kept=(), listed=()) -> dict:
    """-> {"added": [Row], "tagged": [SYM], "kept": [SYM], "skips": {reason: [SYM]}}. The snapshot key is
    sepa.symbols.for_yahoo. A name already listed (GG's qualifier OR a 📌 add): THAT row gains `promo` True +
    `promo_text` in place (a 📌 row keeps `trader`) → tagged, never a second row, never counted against the cap.
    `kept` = listed_today (the 🎪 adds an earlier pass of THIS session wrote): they hold their cap slots — a kept name
    that passes trader_names.candidate_row is re-added (its row re-read this pass), one that fails it stays listed off
    its stored doc ("kept"), and NEITHER is ever "over_cap" or a skip. Every other name runs candidate_row (the ONE add
    check); the rows that pass are ordered by today's change_pct, highest first (then symbol), and only the room the
    kept slots leave (GC.PROMO_NAMES_MAX − kept not tagged) is added with {source, promo, promo_text}; the rest are
    skipped "over_cap". So the session lists at most GC.PROMO_NAMES_MAX 🎪 adds, whatever the passes rank. `listed` =
    scanner.listed_symbols for the session window (verifier L1 2026-10-29): a name this pass does not list as a row but
    the list already carries (e.g. a 🎪 add that GG's own scanner listed on a later pass, then dropped) stays listed
    off its stored doc ("kept") — never a candidate, never "over_cap", never a cap slot (it is not one of today's 🎪
    adds). The tags land only once the walk has finished cleanly (the 📌 F6 rule)."""
    from sepa import symbols
    session_iso = session.isoformat() if isinstance(session, (date, datetime)) else str(session)
    by_sym = {str(q.get("symbol")): q for q in qualifiers or [] if isinstance(q, dict)}
    kept = {str(s).upper() for s in kept or ()}
    listed = {str(s).upper() for s in listed or ()}
    tagged: list = []
    skips: dict = {}
    pending: dict = {}
    cands: list = []
    held: list = []                                              # kept names re-added this pass (hold their slot)
    stay: list = []                                              # kept names listed off their stored doc
    seen: set = set()
    for n in names or []:
        key = symbols.for_yahoo(n["symbol"])
        if key in seen:
            continue
        seen.add(key)
        pt = _text(n)
        q = by_sym.get(key)
        if q is not None:
            if q.get("source") != SOURCE and key not in pending:
                pending[key] = (q, pt)
                tagged.append(key)
            continue
        if key in listed and key not in kept:                    # already on the list off a stored doc (L1)
            stay.append(key)
            continue
        r, why = TN.candidate_row(key, rows, session_iso, types)
        if why is not None:
            if key in kept:
                stay.append(key)
            else:
                skips.setdefault(why, []).append(key)
            continue
        r.update({"source": SOURCE, "promo": True, "promo_text": pt})
        if key in kept:
            held.append(r)
        else:
            cands.append(r)

    def order(r):
        return (-float(r.get("change_pct") or 0.0), r["symbol"])

    cands.sort(key=order)
    room = max(0, GC.PROMO_NAMES_MAX - len(kept - set(tagged)))
    added = sorted(held + cands[:room], key=order)
    over = [r["symbol"] for r in cands[room:]]
    if over:
        skips["over_cap"] = over
    for q, pt in pending.values():
        q["promo"], q["promo_text"] = True, pt
    return {"added": added, "tagged": tagged, "kept": sorted(stay),
            "skips": {k: sorted(skips[k]) if k != "over_cap" else skips[k] for k in SKIP_REASONS if k in skips}}


# ── the stored reader (the cron and on-open paths of run.main; tests inject their own) ────────────────────────────
def default_tags(now=None) -> list:
    """The stored `promo_circuit_tags` docs whose last tag is inside the page's TAG_WINDOW_DAYS — ONE Mongo read, no
    fetch. A dead store raises (the step's fence counts it promo_failed)."""
    PC = _pc()
    coll = PC._tags_coll()
    if coll is None:
        raise RuntimeError("promo tags store unavailable")
    now_u = TN._utc(now or datetime.now(timezone.utc))
    return list(coll.find({"last_tagged_at": {"$gte": now_u - timedelta(days=PC.TAG_WINDOW_DAYS)}}))


# ── the pass step (FENCED) ────────────────────────────────────────────────────────────────────────────────────────
def _zero_counts(result: dict, **over) -> None:
    c = dict(result.get("counts") or {})
    c.update({k: 0 for k in COUNT_KEYS})
    c.update(over)
    result["counts"] = c


def run_step(st, now, session, rows, result: dict, *, types, reader: Callable, good: bool) -> Optional[dict]:
    """After the 📌 step, before scanner.record_scan — run.py calls it ONLY when its Deps.promo_tags reader is wired.
    The source is EMPTY → None and `result` untouched (BUILD_SPEC32 D2: an empty source adds NO key — the pass doc,
    its counts and every served byte stay as before): a failed snapshot (good False; nothing to resolve against), or
    no Promo name tagged on the session's date. FENCED: any raise (the reader included) → logged, {"error": type
    name}, nothing added, counts promo_* = 0 and promo_failed = 1. Otherwise appends the added Rows to
    result["qualifiers"]; result["counts"] gains COUNT_KEYS (promo_failed 0).
    -> {added: [SYM], tagged: [SYM], skips: {reason: [SYM]}, names: n} | {"error": name} | None."""
    try:
        if not good:
            return None
        tags = list(reader(now) or [])
        names = names_for(now, session, tags)
        if not names:
            return None
        quals = list(result.get("qualifiers") or [])
        kept = listed_today(st.scan_docs([session]))            # critic F3: the cap bounds TODAY's listed 🎪 adds
        from . import scanner as SC
        listed = set(SC.listed_symbols(st, session))            # verifier L1: a listed name is never a candidate
        res = resolve(names, rows, session, types, quals, kept, listed)
        skipped = sum(len(v) for k, v in res["skips"].items() if k != "over_cap")
        over = len(res["skips"].get("over_cap") or [])
        result["qualifiers"] = quals + res["added"]
        _zero_counts(result, promo_added=len(res["added"]), promo_tagged=len(res["tagged"]), promo_skipped=skipped,
                     promo_over_cap=over)
        return {"added": [r["symbol"] for r in res["added"]], "tagged": res["tagged"], "kept": res["kept"],
                "skips": res["skips"], "names": len(names)}
    except Exception as exc:                                    # noqa: BLE001
        log.exception("gajjala promo names: the step failed — the pass goes on without it")
        try:
            _zero_counts(result, promo_failed=1)
        except Exception:                                       # noqa: BLE001
            pass
        return {"error": type(exc).__name__}


def _add_sources() -> tuple:
    return (TN.SOURCE, SOURCE)


def recount(result: dict) -> None:
    """After scanner.record_scan and trader_names.recount: qualifiers = GG's rows only (neither a 📌 nor a 🎪 add);
    promo_added = the 🎪 adds — ONLY when the step counted (a pass without the source keeps its counts' shape)."""
    q = [r for r in result.get("qualifiers") or [] if isinstance(r, dict)]
    c = result.setdefault("counts", {})
    if any(r.get("source") == SOURCE for r in q):
        c["qualifiers"] = sum(1 for r in q if r.get("source") not in _add_sources())
    if "promo_added" in c:
        c["promo_added"] = sum(1 for r in q if r.get("source") == SOURCE)


def _block_ok(block) -> bool:
    return isinstance(block, dict) and "skipped" not in block and "error" not in block


def trim_block(block, result: dict) -> None:
    """After scanner.record_scan (the 📌 F1 rule): a name the split hold-out dropped leaves the block too, and
    counts["promo_tagged"] follows (recount owns promo_added). A skipped / failed block is left as is."""
    if not _block_ok(block):
        return
    listed = {str(q.get("symbol")) for q in result.get("qualifiers") or [] if isinstance(q, dict)}
    block["added"] = [s for s in block.get("added") or [] if s in listed]
    block["tagged"] = [s for s in block.get("tagged") or [] if s in listed]
    c = result.get("counts")
    if isinstance(c, dict) and "promo_tagged" in c:
        c["promo_tagged"] = len(block["tagged"])


def held_text(reason) -> Optional[str]:
    """The served words of a 🧠 hold this module owns: PROMO_HOLD_TEXT for HOLD_REASON, else None."""
    return PROMO_HOLD_TEXT if reason == HOLD_REASON else None


def _newest(scan_docs) -> dict:
    newest: dict = {}
    for d in scan_docs or []:
        if not isinstance(d, dict) or not d.get("symbol"):
            continue
        sym, day = str(d["symbol"]).upper(), str(d.get("date") or "")
        if sym not in newest or day > newest[sym][0]:
            newest[sym] = (day, d.get("last") if isinstance(d.get("last"), dict) else {})
    return {s: last for s, (_d, last) in newest.items()}


def tag_map(scan_docs, rows=()) -> dict:
    """PURE. {SYM: {"promo": True, "promo_text"}} — each symbol's NEWEST `gajjala_scan` doc decides (`last.promo` is
    True); this pass's rows override (a row without it untags its symbol). Only tagged symbols are keys."""
    by = {s: last for s, last in _newest(scan_docs).items()}
    for r in rows or ():
        if isinstance(r, dict) and r.get("symbol"):
            by[str(r["symbol"]).upper()] = r
    return {s: {"promo": True, "promo_text": r.get("promo_text") if isinstance(r.get("promo_text"), str) else None}
            for s, r in by.items() if isinstance(r, dict) and r.get("promo") is True}


def added_symbols(scan_docs, rows=()) -> set:
    """PURE. The 🎪 ADDS (rows `source == "promo"`) the potential hold binds: a row of this pass decides; a name with
    no row this pass reads its newest `gajjala_scan` doc (a 🎪 add kept listed by STAY_LISTED_SESSIONS is still one)."""
    by = {s: last.get("source") == SOURCE for s, last in _newest(scan_docs).items()}
    for r in rows or ():
        if isinstance(r, dict) and r.get("symbol"):
            by[str(r["symbol"]).upper()] = r.get("source") == SOURCE
    return {s for s, a in by.items() if a}


def ran(block) -> bool:
    """The step ran on this pass doc (a dict block under "promo" — skipped, failed or counted)."""
    return isinstance(block, dict)


# ── served words ──────────────────────────────────────────────────────────────────────────────────────────────────
def strip_text(block) -> Optional[str]:
    """The strip line — None when no 🎪 name is on the list, or the step was skipped / failed / absent. "added" counts
    every 🎪 add listed today that is one of today's names: re-read this pass (`added`) or listed off its stored doc
    (`kept`, an earlier pass's add that this pass's check could not re-read)."""
    if not _block_ok(block):
        return None
    a = len(block.get("added") or []) + len(block.get("kept") or [])
    t = len(block.get("tagged") or [])
    if a + t == 0:
        return None
    total = block.get("names") if isinstance(block.get("names"), int) else a + t
    return STRIP_TEXT.format(tag=TAG, n=a + t, total=max(total, a + t), added=a, tagged=t)


def skip_text(block) -> Optional[str]:
    """The names tagged today that did not join, COUNTED by reason (the page lists them; ~150 a day) — None when none."""
    if not _block_ok(block):
        return None
    sk = block.get("skips") if isinstance(block.get("skips"), dict) else {}
    bits = [f"{len(sk[k])} {SKIP_WORDS[k]}" for k in SKIP_REASONS if isinstance(sk.get(k), list) and sk[k]]
    if not bits:
        return None
    return SKIP_HEAD.format(tag=TAG) + "; ".join(bits)


def legend_row() -> dict:
    """The counts legend's 🎪 row — appended after the 📌 row ONLY when the latest pass ran the source (tab.py)."""
    return {"key": "promo", "word": f"{TAG} promo",
            "text": ("a name the Promo circuit tagged today (its page's rule), on the list by your call without GG's "
                     f"change and volume floors, inside GG's price band and your instrument rule, at most "
                     f"{GC.PROMO_NAMES_MAX} a session by today's % change; " + CAVEAT + "; GG's rules read it like any "
                     "other name, and " + TN.FLOOR_CLAUSE)}


def rules_clause() -> str:
    """The ℹ️ section's 🎪 clause."""
    PC = _pc()
    return (f"{TAG} Promo names (your call — “should we pull stocks from PROMO circuit by default every day”): the "
            f"names the Promo circuit tagged on the session's date (its page's rule; shotgun one-off mentions dropped "
            f"over its {PC.TAG_WINDOW_DAYS}-day window), read from its stored tags — never fetched by the pass — join "
            f"this list without GG's change and volume floors, inside GG's ${GC.SCAN_MIN_PRICE:.2f}–"
            f"${GC.SCAN_MAX_PRICE:g} band and your instrument rule, at most {GC.PROMO_NAMES_MAX} a session by today's "
            f"% change (a name added earlier today keeps its place; the rest counted, never hidden); a name already listed is tagged {TAG}, never added twice. "
            f"{CAVEAT[0].upper() + CAVEAT[1:]}. GG's rules decide every read, and {TN.FLOOR_CLAUSE}. The cap and the "
            "order are Cheetah defaults (yours, not GG's).")


__all__ = ["SOURCE", "TAG", "SKIP_REASONS", "SKIP_WORDS", "CAVEAT", "STRIP_TEXT", "SKIP_HEAD", "HOLD_WORDS",
           "PROMO_HOLD_TEXT", "HOLD_REASON", "COUNT_KEYS", "text_for", "names_for", "listed_today", "resolve", "default_tags",
           "run_step", "recount", "trim_block", "held_text", "tag_map", "added_symbols", "ran", "strip_text",
           "skip_text", "legend_row", "rules_clause"]
