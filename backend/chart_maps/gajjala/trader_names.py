"""📌 Trader names on 🚩 Gajjala's list (2026-10-27, BUILD_SPEC26 §3.3 + AMENDMENTS A2).

THE ASK (Ajay 2026-10-27, two messages, verbatim): "Can you track this guy please? and his tickers" (stocktwits.com/
algo888), then "Add them to Gajjals, they are pretty good". HIS call, a gate change he made himself: the names an account
FLAGGED in traders/registry.py (`"gajjala": True`) posted in the last TRADER_NAMES_FRESH_SESSIONS market sessions (today
included) join this pass's candidate list AFTER his scanner (scanner.scan_rows — untouched, byte-identical) and BEFORE
the split hold-out + `gajjala_scan` write (scanner.record_scan), so the hold-out, listing, STAY_LISTED_SESSIONS, the
detectors, K1–K11, the no-risk guard, both push gates and the 🏁 ledger run on them unchanged.

WHAT JOINS: a fresh, snapshot-resolvable name dated the session, with a prior regular close, inside GG's price band and
Ajay's round-A instrument rule (scanner.type_verdict — the SAME rule); OTC never appears (the snapshot excludes it).
WITHOUT GG's change and volume floors (HIS CALL #1) — that IS the add. A name his scanner already lists is TAGGED (one
row, `trader` set, no `source`), never a second row. Every add carries `source: "trader"` and the 📌 tag.
A2 (orchestrator, binding): GG's 1M floor stays on EVERY push — a 📌 add's 🧠 potential push is HELD while the session
volume the pass read is under GC.SCAN_MIN_VOLUME (potential.py, TRADER_HOLD_TEXT); the A+ path is already K11.

The pass re-reads a flagged StockTwits account at most every TRADER_REFRESH_SEC (state doc "trader_refresh"); an
x-sourced account is NEVER fetched by the pass (its twice-a-day cron read is the traders package's own). The refresh is
None in tests, replays, dry runs and the on-open pass (run.Deps.trader_fetch).

UNMEASURED: no study in this app has read these names (the closest class measured — promo-account first tags — read
INVERTED). Nothing here sizes, ranks or claims an edge; GG's rules decide every read and every A+.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from . import constants as GC

log = logging.getLogger("chart_maps.gajjala.trader_names")

ET = ZoneInfo("America/New_York")
SOURCE = "trader"
STATE_ID = "trader_refresh"
SKIP_REASONS = ("not_in_snapshot", "not_dated_session", "no_prev_close", "type_out", "out_of_band", "over_cap")
SKIP_TEXT = {
    "not_in_snapshot": "not in today's market snapshot (OTC, or no trade yet)",
    "not_dated_session": "no print dated today yet",
    "no_prev_close": "no prior regular close on file",
    "type_out": "not common stock or an ADR (your instrument rule)",
    "out_of_band": f"outside GG's ${GC.SCAN_MIN_PRICE:.2f}–${GC.SCAN_MAX_PRICE:g} band",
    "over_cap": f"past the {GC.TRADER_NAMES_MAX}-name cap a pass",
}
_FLOOR_M = GC.SCAN_MIN_VOLUME // 1_000_000                       # GG's floor in millions — the constant, never retyped
FLOOR_CLAUSE = f"no push rings on one until today's volume clears GG's {_FLOOR_M}M floor"   # A2
STRIP_TEXT = ("{tag} {n} of {who}'s posted names on this pass's list — your call 2026-10-27; GG's rules decide every "
              "read and every A+, and " + FLOOR_CLAUSE)
SKIP_HEAD = "{tag} not on the list: "
HOLD_WORDS = f"{GC.TRADER_TAG} under GG's {_FLOOR_M}M volume floor — listed and read, not rung"
TRADER_HOLD_TEXT = f"held: {HOLD_WORDS}"                         # A2 — FROZEN (the 📈 track row serves it verbatim)
HOLD_REASON = "trader_under_floor"                                # A2 — the `held` reason potential.TRADER_HELD records


# ── who ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _traders() -> list:
    from traders import registry as R
    return list(R.TRADERS)


def flagged() -> list:
    """Every registry row flagged for this scan (`"gajjala": True`, the bool — never truthy)."""
    return [t for t in _traders() if isinstance(t, dict) and t.get("gajjala") is True]


def text_for(key) -> Optional[str]:
    """"📌 {handle}" for a trader key (the registry's handle; an unknown key prints the key itself); None for no key."""
    if not isinstance(key, str) or not key.strip():
        return None
    who = next((t for t in _traders() if isinstance(t, dict) and t.get("key") == key), None)
    handle = (who or {}).get("handle") or key
    return f"{GC.TRADER_TAG} {handle}"


def _handles(who: Optional[list] = None) -> list:
    return [str(t.get("handle") or t.get("key")) for t in (flagged() if who is None else who)]


# ── the window (PURE) ─────────────────────────────────────────────────────────────────────────────────────────────
def _as_date(session) -> date:
    if isinstance(session, datetime):
        return session.date()
    return session if isinstance(session, date) else date.fromisoformat(str(session))


def window_start(session) -> datetime:
    """Aware UTC: 00:00 ET of the (TRADER_NAMES_FRESH_SESSIONS − 1)-th previous market day (the house calendar)."""
    from catalysts.medical.reaction import prev_market_day
    d = _as_date(session)
    for _ in range(GC.TRADER_NAMES_FRESH_SESSIONS - 1):
        d = prev_market_day(d)
    return datetime.combine(d, time.min, tzinfo=ET).astimezone(timezone.utc)


def _at(x) -> Optional[datetime]:
    """A post's created_at as aware UTC (a naive stamp is UTC — the store's rule); None when it does not parse."""
    if isinstance(x, datetime):
        dt = x
    elif isinstance(x, str) and x.strip():
        try:
            dt = datetime.fromisoformat(x.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _utc(now: datetime) -> datetime:
    return now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)


def names_for(now, session, posts_by: dict) -> tuple:
    """PURE. -> (names, over_cap_skips). `posts_by` = {trader key: [post]}; only FLAGGED keys are read. A post counts
    iff its created_at parses and window_start(session) ≤ at ≤ now; its symbols = post.cashtags minus
    traders.feed.MARKET_TICKERS. One name per symbol (the newest mention wins); order (at desc, symbol asc); the first
    TRADER_NAMES_MAX are kept, the rest are skipped "over_cap". name = {symbol, trader, at (ISO), post_id, text}."""
    from traders.feed import MARKET_TICKERS
    keys = {t.get("key") for t in flagged()}
    lo, hi = window_start(session), _utc(now)
    best: dict = {}
    for key, posts in (posts_by or {}).items():
        if key not in keys:
            continue
        for p in posts or []:
            if not isinstance(p, dict):
                continue
            at = _at(p.get("created_at"))
            if at is None or not (lo <= at <= hi):
                continue
            for tag in p.get("cashtags") or []:
                sym = str(tag or "").strip().upper().lstrip("$")
                if not sym or sym in MARKET_TICKERS:
                    continue
                cur = best.get(sym)
                if cur is None or at > cur[0]:
                    best[sym] = (at, {"symbol": sym, "trader": key, "at": at.isoformat(),
                                      "post_id": str(p.get("id") or p.get("_id") or ""),
                                      "text": p.get("text") if isinstance(p.get("text"), str) else ""})
    order = sorted(best.values(), key=lambda x: (-x[0].timestamp(), x[1]["symbol"]))
    names = [n for _at_, n in order[:GC.TRADER_NAMES_MAX]]
    over = [{"symbol": n["symbol"], "trader": n["trader"], "reason": "over_cap"}
            for _at_, n in order[GC.TRADER_NAMES_MAX:]]
    return names, over


# ── resolve against the pass's snapshot (PURE but for the tag set on a qualifier row) ─────────────────────────────
def candidate_row(key: str, rows: dict, session_iso: str, types: Optional[dict]) -> tuple:
    """PURE. The ONE add check (📌 trader names; 🎪 promo_names reuses it, 2026-10-29) -> (Row, None) or (None, reason):
    not_in_snapshot, not_dated_session (no print dated the session), no_prev_close, type_out (scanner.type_verdict),
    out_of_band (GG's price band), in that order; else scanner.build_row's Row. GG's change and volume floors are NOT
    applied (HIS CALL #1)."""
    from sepa import prices
    from . import scanner as SC
    row = (rows or {}).get(key)
    if not isinstance(row, dict):
        return None, "not_in_snapshot"
    ep = prices.extended_print(row)
    if not ep or ep["date"] != session_iso:
        return None, "not_dated_session"
    prev = SC._f(row.get("prev_day_close"))
    if not prev or prev <= 0:
        return None, "no_prev_close"
    typ, verdict = SC.type_verdict(key, types)
    if verdict == "out":
        return None, "type_out"
    r = SC.build_row(key, row, ep, prev, typ, session_iso)
    if not (GC.SCAN_MIN_PRICE <= r["price"] <= GC.SCAN_MAX_PRICE):
        return None, "out_of_band"
    return r, None


def resolve(names: list, rows: dict, session, types: Optional[dict], qualifiers: list) -> dict:
    """-> {"added": [Row], "tagged": [SYM], "skips": [{symbol, trader, reason}]}. The snapshot key is
    sepa.symbols.for_yahoo(symbol) (BRK.B post ↔ BRK-B row). A name his scanner already lists: THAT row gets
    `trader` / `trader_text` in place (no `source`, no second row) → tagged. Otherwise, in order: not_in_snapshot,
    not_dated_session (no print dated the session), no_prev_close, type_out (scanner.type_verdict), out_of_band (GG's
    price band) — else scanner.build_row's Row + {source, trader, trader_text} → added. GG's change and volume floors
    are NOT applied (HIS CALL #1)."""
    from sepa import symbols
    session_iso = session.isoformat() if isinstance(session, (date, datetime)) else str(session)
    by_sym = {str(q.get("symbol")): q for q in qualifiers or [] if isinstance(q, dict)}
    added, tagged, skips = [], [], []
    pending: dict = {}          # 2026-10-27 critic F6: GG's rows are tagged only once this walk has finished cleanly
    for n in names or []:
        sym, key = n["symbol"], symbols.for_yahoo(n["symbol"])
        tt = text_for(n["trader"])

        def skip(reason):
            skips.append({"symbol": key, "trader": n["trader"], "reason": reason})

        q = by_sym.get(key)
        if q is not None:
            if q.get("source") != SOURCE and key not in pending:
                pending[key] = (q, n["trader"], tt)
                tagged.append(key)
            continue
        r, why = candidate_row(key, rows, session_iso, types)
        if why is not None:
            skip(why)
            continue
        r.update({"source": SOURCE, "trader": n["trader"], "trader_text": tt})
        added.append(r)
        by_sym[key] = r                                         # a second spelling of the same name never adds twice
    for q, trader, tt in pending.values():                      # F6 — nothing above raised: now the tags land
        q["trader"], q["trader_text"] = trader, tt
    return {"added": added, "tagged": tagged, "skips": skips}


# ── the in-pass refresh (a flagged StockTwits account, at most every TRADER_REFRESH_SEC) ──────────────────────────
def default_fetch(key: str) -> dict:
    from traders import feed
    return feed.refresh(trader=key, pages=GC.TRADER_FETCH_PAGES, timeout=GC.TRADER_FETCH_TIMEOUT_SEC)


def default_posts(key: str) -> list:
    from traders import feed
    return feed.stored(trader=key)


def maybe_refresh(st, now, fetch: Callable) -> Optional[dict]:
    """The state doc STATE_ID {at, ok, stored}: due when there is none or now − at ≥ TRADER_REFRESH_SEC. Each flagged
    trader whose source is "stocktwits" is fetched in its own try; the memo is written (at = now) whatever happened.
    -> the memo written, or None when not due. An x-sourced account is NEVER fetched here."""
    now_u = _utc(now)
    doc = st.get_state(STATE_ID) or {}
    last = _at(doc.get("at"))
    if last is not None and (now_u - last).total_seconds() < GC.TRADER_REFRESH_SEC:
        return None
    ok, stored = True, 0
    for t in flagged():
        if t.get("source") != "stocktwits":
            continue
        try:
            r = fetch(t["key"]) or {}
            ok = ok and bool(r.get("ok"))
            stored += int(r.get("stored") or 0)
        except Exception as exc:                                # noqa: BLE001 — a dark fetch never fails the pass
            log.warning("gajjala trader names: refresh of %s failed: %s", t.get("key"), type(exc).__name__)
            ok = False
    memo = {"at": now_u, "ok": ok, "stored": stored}
    try:
        st.set_state(STATE_ID, memo)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala trader names: refresh memo write failed: %s", type(exc).__name__)
    return memo


# ── the pass step (FENCED) ────────────────────────────────────────────────────────────────────────────────────────
def run_step(st, now, session, rows, result: dict, *, types, deps, good: bool, refresh: bool) -> dict:
    """After scanner.scan_rows, before scanner.record_scan. FENCED: any raise → logged, {"error": type name}, `result`
    untouched. good False (a failed snapshot) → {"skipped": "snapshot"}, nothing added. refresh → maybe_refresh with
    deps.trader_fetch. Appends the added Rows to result["qualifiers"]; result["counts"] gains trader_added /
    trader_tagged / trader_skipped. -> {added: [SYM], tagged: [SYM], skips, who: [handles], refresh: memo | None}."""
    try:
        if not good:
            return {"skipped": "snapshot"}
        who = flagged()
        fetch = getattr(deps, "trader_fetch", None)
        memo = maybe_refresh(st, now, fetch) if (refresh and fetch is not None) else None
        posts_fn = getattr(deps, "trader_posts", None) or default_posts
        posts_by: dict = {}
        for t in who:
            try:
                posts_by[t["key"]] = list(posts_fn(t["key"]) or [])
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala trader names: posts of %s unreadable: %s", t.get("key"), type(exc).__name__)
                posts_by[t["key"]] = []
        names, over = names_for(now, session, posts_by)
        quals = list(result.get("qualifiers") or [])
        res = resolve(names, rows, session, types, quals)
        skips = res["skips"] + over
        counts = dict(result.get("counts") or {}, trader_added=len(res["added"]), trader_tagged=len(res["tagged"]),
                      trader_skipped=len(skips))
        result["qualifiers"] = quals + res["added"]
        result["counts"] = counts
        return {"added": [r["symbol"] for r in res["added"]], "tagged": res["tagged"], "skips": skips,
                "who": _handles(who), "refresh": memo}
    except Exception as exc:                                    # noqa: BLE001
        log.exception("gajjala trader names: the step failed — the pass goes on without it")
        return {"error": type(exc).__name__}


def recount(result: dict) -> None:
    """After scanner.record_scan (its split hold-out rewrites counts["qualifiers"]): qualifiers = GG's rows only,
    trader_added = the 📌 adds."""
    q = [r for r in result.get("qualifiers") or [] if isinstance(r, dict)]
    c = result.setdefault("counts", {})
    c["qualifiers"] = sum(1 for r in q if r.get("source") != SOURCE)
    c["trader_added"] = sum(1 for r in q if r.get("source") == SOURCE)


def trim_block(block, result: dict) -> None:
    """After scanner.record_scan (2026-10-27 critic F1): its split hold-out may drop a name the step added or tagged.
    The block keeps only the symbols still on result["qualifiers"], and counts["trader_tagged"] follows (recount owns
    trader_added), so the strip line never counts a name that is not listed. A skipped / failed block is left as is."""
    if not _block_ok(block):
        return
    listed = {str(q.get("symbol")) for q in result.get("qualifiers") or [] if isinstance(q, dict)}
    block["added"] = [s for s in block.get("added") or [] if s in listed]
    block["tagged"] = [s for s in block.get("tagged") or [] if s in listed]
    c = result.get("counts")
    if isinstance(c, dict) and "trader_tagged" in c:
        c["trader_tagged"] = len(block["tagged"])


def held_text(reason) -> Optional[str]:
    """The served words of a 🧠 hold this module owns (A2): TRADER_HOLD_TEXT for HOLD_REASON, else None."""
    return TRADER_HOLD_TEXT if reason == HOLD_REASON else None


def tag_map(scan_docs, rows=()) -> dict:
    """PURE. {SYM: {"trader", "trader_text"}} — each symbol's NEWEST `gajjala_scan` doc decides (`last.trader`); this
    pass's rows override (a row with no trader untags its symbol)."""
    newest: dict = {}
    for d in scan_docs or []:
        if not isinstance(d, dict) or not d.get("symbol"):
            continue
        sym, day = str(d["symbol"]).upper(), str(d.get("date") or "")
        if sym not in newest or day > newest[sym][0]:
            newest[sym] = (day, (d.get("last") or {}).get("trader") if isinstance(d.get("last"), dict) else None)
    by = {s: t for s, (_d, t) in newest.items()}
    for r in rows or ():
        if isinstance(r, dict) and r.get("symbol"):
            by[str(r["symbol"]).upper()] = r.get("trader")
    return {s: {"trader": t, "trader_text": text_for(t)} for s, t in by.items() if isinstance(t, str) and t}


def added_symbols(scan_docs, rows=()) -> set:
    """PURE. The 📌 ADDS (rows `source == "trader"`) the potential hold (A2) binds: a row of this pass decides; a name
    with no row this pass reads its newest `gajjala_scan` doc's `last.source` (a 📌 add kept listed by
    STAY_LISTED_SESSIONS is still a 📌 add)."""
    newest: dict = {}
    for d in scan_docs or []:
        if not isinstance(d, dict) or not d.get("symbol"):
            continue
        sym, day = str(d["symbol"]).upper(), str(d.get("date") or "")
        if sym not in newest or day > newest[sym][0]:
            last = d.get("last") if isinstance(d.get("last"), dict) else {}
            newest[sym] = (day, last.get("source") == SOURCE)
    by = {s: a for s, (_d, a) in newest.items()}
    for r in rows or ():
        if isinstance(r, dict) and r.get("symbol"):
            by[str(r["symbol"]).upper()] = r.get("source") == SOURCE
    return {s for s, a in by.items() if a}


def under_floor(volume) -> bool:
    """A2 — the session volume the pass read is under GG's floor (unknown reads under: fail closed, never rings)."""
    try:
        v = float(volume)
    except (TypeError, ValueError):
        return True
    return not (v == v and v >= GC.SCAN_MIN_VOLUME)


# ── served words ──────────────────────────────────────────────────────────────────────────────────────────────────
def _block_ok(block) -> bool:
    return isinstance(block, dict) and "skipped" not in block and "error" not in block


def strip_text(block) -> Optional[str]:
    """The strip line — None when nothing of his is on the list, or the step was skipped / failed."""
    if not _block_ok(block):
        return None
    n = len(block.get("added") or []) + len(block.get("tagged") or [])
    if n == 0:
        return None
    return STRIP_TEXT.format(tag=GC.TRADER_TAG, n=n, who=", ".join(block.get("who") or []))


def skip_text(block) -> Optional[str]:
    """The names he posted that did not join, each with its reason — None when there is none."""
    if not _block_ok(block):
        return None
    skips = [s for s in block.get("skips") or [] if isinstance(s, dict) and s.get("reason") in SKIP_TEXT]
    if not skips:
        return None
    return SKIP_HEAD.format(tag=GC.TRADER_TAG) + "; ".join(f"{s['symbol']} — {SKIP_TEXT[s['reason']]}"
                                                           for s in skips)


def legend_row() -> dict:
    """The counts legend's LAST row (tab.LEGEND_KEYS)."""
    return {"key": "trader", "word": f"{GC.TRADER_TAG} trader",
            "text": (f"a name a trader you flagged posted in the last {GC.TRADER_NAMES_FRESH_SESSIONS} market sessions "
                     "(today included) — on the list by your call without GG's change and volume floors, inside GG's "
                     "price band and your instrument rule; GG's rules read it like any other name, and "
                     + FLOOR_CLAUSE)}


def rules_clause() -> str:
    """The ℹ️ scanner pick's 📌 clause — "" when no trader is flagged."""
    who = flagged()
    if not who:
        return ""
    return (f"{GC.TRADER_TAG} Trader names (your call — “Add them to Gajjals, they are pretty good”): the names "
            f"{', '.join(_handles(who))} posted in the last {GC.TRADER_NAMES_FRESH_SESSIONS} market sessions (today "
            f"included), newest first, at most {GC.TRADER_NAMES_MAX} a pass, join this list without GG's change and "
            f"volume floors — inside GG's ${GC.SCAN_MIN_PRICE:.2f}–${GC.SCAN_MAX_PRICE:g} band and your instrument "
            f"rule, never OTC; the pass re-reads his posts every {GC.TRADER_REFRESH_SEC // 60} minutes. A {GC.TRADER_TAG} tag on "
            f"every card, row and push; GG's rules decide every read, and {FLOOR_CLAUSE}. The window, the cap and the "
            "re-read are Cheetah defaults (yours, not GG's).")


__all__ = ["SOURCE", "STATE_ID", "SKIP_REASONS", "SKIP_TEXT", "STRIP_TEXT", "SKIP_HEAD", "TRADER_HOLD_TEXT",
           "HOLD_REASON", "FLOOR_CLAUSE", "flagged", "text_for", "window_start", "names_for", "candidate_row", "resolve", "default_fetch",
           "default_posts", "maybe_refresh", "run_step", "recount", "trim_block", "held_text", "tag_map", "added_symbols", "under_floor",
           "strip_text", "skip_text", "legend_row", "rules_clause"]
