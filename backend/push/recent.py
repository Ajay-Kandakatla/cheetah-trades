"""GET /notifications/recent — the unified recent-notifications feed
(push_history + sepa_breakouts), lifted out of main.py on 2026-09-05.

Why a module of its own: the /alerts page (Ajay 2026-09-05: "can I go to a
dedicated page to see the list of alerts? May be add it to recent alerts or
something?") needs this feed filtered to the three Supply & Demand kinds, to a
day, to one ticker — and main.py cannot be imported by the py3.9 test venv,
so the route had no test. Same path, same row shape, same default behaviour
byte-for-byte when the new query params are absent; now behind TestClient.

Query params (all optional; absent = the old feed):
  limit    1..500 (was 100) — merged rows returned (COLLAPSED rows, see below)
  kinds    comma list, e.g. ``demand_alert,zone_bounce_alert,supply_break_alert``
           → push rows filtered to those kinds; breakout rows ride along
           ONLY when the list names ``volume_breakout`` / ``rising_momentum`` /
           ``stage_breakdown_*`` (otherwise the breakout source is excluded)
  since    unix seconds → rows with ts >= since
  ticker   upper-cased symbol → rows whose ticker equals it
  collapse 2026-09-21, default TRUE — fold ADJACENT rows of the merged ts-desc
           list that share ``(source, kind, ticker, title, tuple(tickers))``
           into the newest one, which then carries a ``repeat`` block. The
           BODY is deliberately NOT part of that identity (two of his presets
           firing on one print differ only in their Note and must read as one
           line); ``tickers`` IS, so two count-only digests naming different
           names never merge. ``collapse=false`` returns the flat
           pre-2026-09-21 list. See docs/notifications/alerts_feed_collapse.md.

Row shape (normalized across both sources, unchanged apart from `tickers`):
    {_id, ts, ts_iso, title, body, kind, ticker, tickers, url,
     source: 'push' | 'breakout', sent, failed, total, dismissed?, repeat?,
     items?, items_not_stored?}
`items` / `items_not_stored` (2026-09-29) are present ONLY on a push row that
lists linkable lines — see ``served_items``.
`repeat` is present ONLY on a survivor of a fold:
    {count, first_ts, first_ts_iso, last_ts, truncated, line}
`line` is the whole sentence — every reader prints it verbatim and none of
them recomposes it, reads a clock or formats a date for this row.

Payload: {"rows", "count", "collapse", "raw_truncated"} — ``raw_truncated`` is
measured on the RAW push fetch (it hit its cap), never on the served length,
so the page's "newest 500 only" warning survives the collapse.

`tickers` (2026-09-20, Ajay: "I need the stock tickers to be clickables in
alerts individually if there are multiple in one alert by command click") is
ALWAYS a list on every row — see ``derive_tickers``.
``ts`` is a UTC epoch and ``ts_iso`` UTC — the page formats in
America/New_York and says ET.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from auth import current_user_email

log = logging.getLogger("push.recent")

router = APIRouter(tags=["notifications"])

MAX_LIMIT = 500
BREAKOUT_SOURCE_CAP = 200          # source-side cap on sepa_breakouts, as before
# 2026-09-21. `limit` counts COLLAPSED rows, so the raw push fetch over-reads
# by this factor (bounded by MAX_LIMIT) to still fill a page after folding.
# An engineering bound, not a trading number: the worst measured fold on his
# own feed was -12% (bell, raw 50). A bigger factor only costs bell traffic.
COLLAPSE_OVERFETCH = 2

# The kinds that live in sepa_breakouts rather than push_history. A `kinds`
# list that names none of these excludes the breakout source entirely.
BREAKOUT_KINDS = ("volume_breakout", "rising_momentum")
BREAKOUT_KIND_PREFIX = "stage_breakdown_"

# --------------------------------------------------------------------------
# Per-ticker links (2026-09-20)
# --------------------------------------------------------------------------
# The kinds whose body is a LIST of names. A row stored before this date
# carries no `tickers`, so the feed derives them from the body — but ONLY for
# these kinds. A morning brief or a lesson body is prose and the regex never
# runs over it ("NEW, AT, ET" would all read as tickers).
DIGEST_KINDS = frozenset({
    "growth_demand_alert", "demand_alert", "zone_bounce_alert",
    "hot_pullback_alert", "pattern_alert", "board_arrival", "earnings_reaction",
    # 💎 growth/quality_alerts.py (2026-09-22) — its digest body is
    # "SYM (now holds more cash than debt), SYM (…)", a LIST of names, so the
    # feed may derive per-ticker chips from it.
    "capital_quality_upgrade",
    # 🧬 catalysts/medical/alerts.py (2026-09-29) — its digest body is
    # "SYM · label · +N%" lines, a LIST of names.
    "med_catalyst",
})

# Upper-case only, 1-5 letters, with an optional single-letter class suffix —
# load_universe("full") spells class shares with a HYPHEN (BRK-B, HEI-A, MOG-A,
# UHAL-B, BF-B, LEN-B, GEF-B); the dot form is kept for a Massive-spelled body.
# Lower case never matches, so "nvda" in prose is not a ticker.
_TOKEN = re.compile(r"^[A-Z]{1,5}(?:[.-][A-Z])?$")

# --------------------------------------------------------------------------
# Every item of a consolidated push (2026-09-29)
# --------------------------------------------------------------------------
# Ajay, on the "⚡ Tape burst at a zone — CRWV +7 more" card: "I am unable to
# see the other that are hiddedn her … Can you show them all and make all the
# tickers clicable individually?". The composers now LOG every entry as
# `items` (push.sender strips it from the device payload); this module serves
# them, each line's leading ticker linked. docs/alerts/every_item_2026_09_29.md
DEFAULT_ITEM_URL = "/sepa/{sym}?tab=supply"       # the page's own chip destination
# kind -> per-ticker page for one ITEM line. Mirrors each kind's single-push url
# (pinned by tests against zone_edge._url, key_level_alerts.url_for, the
# trade_flash / med_catalyst builders). A kind here ALSO opts its OLD rows
# (no stored items) into the body-line parse.
ITEM_URL_BY_KIND = {
    "trade_flash":          "/sepa/{sym}?tab=tape&from=supply-demand",
    "demand_alert":         DEFAULT_ITEM_URL,
    "zone_bounce_alert":    DEFAULT_ITEM_URL,
    "supply_break_alert":   DEFAULT_ITEM_URL,
    "key_level_alert":      "/chart-maps?tab=support&symbol={sym}",
    "med_catalyst":         "/sepa/{sym}?tab=catalyst",
    "juggernaut_watchlist": DEFAULT_ITEM_URL,
    "leaderboard_breakout": DEFAULT_ITEM_URL,
    "accumulation_change":  DEFAULT_ITEM_URL,
}
ITEM_KINDS = frozenset(ITEM_URL_BY_KIND)
_LEAD_MARK = re.compile(r"^[^A-Za-z0-9+$]+")   # emoji / spaces / bullets before a line's first token
_MORE_TAIL = re.compile(r"^\+(\d+) more\b")    # "+3 more on the board"
_TITLE_MORE = re.compile(r"\+(\d+) more\b")    # "… CRWV +7 more"


def lead_token(text: str) -> str:
    """First token after stripping a leading marker (_LEAD_MARK), cut at '(' and
    rstripped of ',:;' (and a closing ')', so "(NVDA) x" reads NVDA). '' when
    nothing is left. '🆕 NVDA · $1' -> 'NVDA'; '+3 more' -> '+3';
    '$68.39 · …' -> '$68.39'."""
    if not isinstance(text, str):
        return ""
    t = _LEAD_MARK.sub("", text.strip())
    if not t:
        return ""
    return t.split(" ")[0].split("(")[0].rstrip(",:;)")


def lead_symbol(text: str, known: frozenset) -> Optional[str]:
    """lead_token when it matches _TOKEN AND is in `known`, else None. Lower case
    never matches."""
    tok = lead_token(text)
    if tok and _TOKEN.match(tok) and tok in known:
        return tok
    return None


def item_url(kind: Optional[str], sym: str) -> str:
    return ITEM_URL_BY_KIND.get(kind or "", DEFAULT_ITEM_URL).format(sym=sym)


def _stored_items(raw) -> list:
    """The row's stored `items`: dict entries with a non-blank str `text`,
    `symbol` upper-cased when a non-blank str else None. [] otherwise."""
    if not isinstance(raw, list):
        return []
    out = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        text = it.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        sym = it.get("symbol")
        sym = sym.strip().upper() if isinstance(sym, str) and sym.strip() else None
        out.append({"symbol": sym, "text": text.strip()})
    return out


def _tail_rest(line: str) -> Optional[str]:
    """For a body's own "+N more…" tail line: '' when it is a PURE tail marker
    ("+3 more", "+3 more on the board", "+3 more on /watchlist"), else what
    rides after it — zone_edge._tag_msg appends " · pre-mkt" to the body END,
    so "+3 more · pre-mkt" keeps "pre-mkt" (a session tag is never dropped).
    None when the line is not a tail at all."""
    m = _MORE_TAIL.match(line)
    if not m:
        return None
    rest = line[m.end():]
    if rest.startswith(" on "):
        cut = rest.find(" · ")
        rest = "" if cut < 0 else rest[cut:]
    rest = rest.strip()
    if rest.startswith("·"):
        rest = rest[1:].strip()
    return rest


def _body_lines(row: dict) -> list:
    body = row.get("body")
    return ([ln.strip() for ln in body.split("\n") if ln.strip()]
            if isinstance(body, str) and body else [])


def served_items(row: dict, known: frozenset) -> Optional[tuple]:
    """(items, not_stored) for one push row, or None (= the row renders its body as today).
    items: [{"symbol": str|None, "text": str, "url": str|None, "pushed": bool}]

    1. stored = the row's valid `items` ([] when absent / not a list).
    2. no stored items = a LEGACY row: only a kind in ITEM_KINDS, and never a
       single (a non-blank `ticker`).
    3. the body's lines come first, verbatim (`pushed: True`); a line is
       matched POSITIONALLY to the next stored entry when it IS that entry's
       text, or its leading token equals the entry's symbol case-insensitively
       (the builder's own symbol is trusted even outside _TOKEN); a None
       symbol or a lower-case body therefore never stalls the walk into
       repeating lines. Any other line links its leading token only when it
       is known. With stored items, the body's own "+N more…" tail is dropped
       (the unpushed entries below ARE those names — "more" is never said
       twice); a session tag riding on it survives (``_tail_rest``).
    4. the stored items the body never printed follow (`pushed: False`).
    5. not_stored: stored -> items_total - len(stored); legacy -> the body's
       "+N more" tail, else the title's "+N more" minus the lines printed.
    """
    kind = row.get("kind")
    stored = _stored_items(row.get("items"))
    if not stored:
        if kind not in ITEM_KINDS:
            return None
        tick = row.get("ticker")
        if isinstance(tick, str) and tick.strip():
            return None
    lines = _body_lines(row)
    if stored:
        kept = []
        for ln in lines:
            rest = _tail_rest(ln)
            if rest is None:
                kept.append(ln)
            elif rest:
                kept.append(rest)
        lines = kept
    trusted = frozenset(known) | {it["symbol"] for it in stored if it["symbol"]}
    out: list = []
    j = 0
    for line in lines:
        tok = lead_token(line)
        nxt = stored[j] if j < len(stored) else None
        if nxt is not None and (line == nxt["text"]
                                or (nxt["symbol"] and tok.upper() == nxt["symbol"])):
            sym = nxt["symbol"] or lead_symbol(line, trusted)
            j += 1
        else:
            sym = lead_symbol(line, trusted)
        out.append({"symbol": sym, "text": line,
                    "url": item_url(kind, sym) if sym else None, "pushed": True})
    for it in stored[j:]:
        sym = it["symbol"]
        out.append({"symbol": sym, "text": it["text"],
                    "url": item_url(kind, sym) if sym else None, "pushed": False})
    if not any(e["symbol"] for e in out):
        return None
    not_stored = 0
    if stored:
        total = row.get("items_total")
        if isinstance(total, int) and not isinstance(total, bool):
            not_stored = max(0, total - len(stored))
    else:
        tail = next((m for m in (_MORE_TAIL.match(ln) for ln in lines) if m), None)
        if tail:
            not_stored = int(tail.group(1))
        else:
            tm = _TITLE_MORE.search(row.get("title") or "") \
                if isinstance(row.get("title"), str) else None
            if tm:
                printed = sum(1 for ln in lines if not _MORE_TAIL.match(ln))
                not_stored = max(0, int(tm.group(1)) + 1 - printed)
    return out, not_stored


# --------------------------------------------------------------------------
# OLD ⚡ tape-burst rows: every burst, re-read from trade_flash_events
# --------------------------------------------------------------------------
# A trade_flash row stored before 2026-09-29 printed 4 bursts and dropped the
# rest — but every burst it was about is still a document in
# trade_flash_events (the dedupe store the push was built from), stamped
# `recorded_at` by build_events a moment BEFORE the push's own `ts`. So HIS
# "CRWV +7 more" card can list all 8. The read is trusted ONLY when the window
# holds exactly the title's N+1 events (1,672 of 1,677 old rows on prod,
# 2026-09-29); anything else keeps the honest "+N more not stored" line.
# The window is shorter than the 5-minute poll cadence, so two pushes never
# share one. docs/alerts/every_item_2026_09_29.md
TAPE_WINDOW_BEFORE_SEC = 240
TAPE_WINDOW_AFTER_SEC = 5
# Engineering bounds on the ONE ranged read per request (not trading numbers):
# a full page (MAX_LIMIT rows) at the measured p99 of 24 events per push, and a
# server-side time cap so a slow Mongo can never stall /alerts.
TAPE_RECON_MAX_DOCS = MAX_LIMIT * 24
TAPE_RECON_MAX_MS = 2000
_TAPE_FIELDS = {"_id": 0, "symbol": 1, "time_et": 1, "dollars": 1, "side": 1,
                "board": 1, "recorded_at": 1}


def _num_stamp(v) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v) if v == v else None


def tape_recon_want(row: dict) -> Optional[int]:
    """N+1 (the title's count) when an OLD trade_flash row hid bursts and is
    worth a re-read, else None. Stored items, a single, no "+N more" title, a
    body that already printed them all or no usable ts -> None."""
    if row.get("kind") != "trade_flash" or _stored_items(row.get("items")):
        return None
    tick = row.get("ticker")
    if isinstance(tick, str) and tick.strip():
        return None
    title = row.get("title")
    m = _TITLE_MORE.search(title) if isinstance(title, str) else None
    if not m:
        return None
    want = int(m.group(1)) + 1
    printed = sum(1 for ln in _body_lines(row) if not _MORE_TAIL.match(ln))
    if want <= printed:
        return None
    ts = _num_stamp(row.get("ts"))
    if ts is None or ts <= 0:
        return None
    return want


def tape_items_for_legacy(rows: list, get_db) -> dict:
    """{row index: items} for the OLD trade_flash rows whose bursts can be
    re-read from trade_flash_events. ONE ranged find for the whole page
    (bounded by TAPE_RECON_MAX_DOCS and TAPE_RECON_MAX_MS), bucketed in memory.

    A row is filled only when its window [ts-240s, ts+5s] holds EXACTLY the
    title's N+1 events; they are sorted dollars-desc (the builder's order) and
    each line is trade_flash.headline(e) — the builder's own function, so a
    rebuilt line is byte-identical to the one the phone showed. Mongo down, a
    failed read, a count mismatch or a window cut by the doc cap -> the row is
    left out (the honest "+N more not stored" path). Never raises."""
    wants = {}
    for i, r in enumerate(rows):
        w = tape_recon_want(r)
        if w is not None:
            wants[i] = w
    if not wants:
        return {}
    try:
        db = get_db()
    except Exception:                                        # noqa: BLE001
        db = None
    if db is None:
        return {}
    stamps = [_num_stamp(rows[i].get("ts")) for i in wants]
    lo = min(stamps) - TAPE_WINDOW_BEFORE_SEC
    hi = max(stamps) + TAPE_WINDOW_AFTER_SEC
    try:
        from orderflow.trade_flash import EVENTS_COLL, headline
        cur = (db[EVENTS_COLL].find({"recorded_at": {"$gte": lo, "$lte": hi}}, _TAPE_FIELDS)
               .sort("recorded_at", -1).limit(TAPE_RECON_MAX_DOCS)
               .max_time_ms(TAPE_RECON_MAX_MS))
        docs = list(cur)
    except Exception as exc:                                 # noqa: BLE001
        log.warning("push.recent: trade_flash_events read failed: %s", exc)
        return {}
    evs = []
    for d in docs:
        at = _num_stamp(d.get("recorded_at")) if isinstance(d, dict) else None
        if at is not None:
            evs.append((at, d))
    # The cap cut the OLDEST end of a desc read: a window reaching at or below
    # the last stamp returned may be missing documents, so it is not trusted.
    complete_above = evs[-1][0] if len(docs) >= TAPE_RECON_MAX_DOCS and evs else None
    out = {}
    for i, want in wants.items():
        ts = _num_stamp(rows[i].get("ts"))
        a, b = ts - TAPE_WINDOW_BEFORE_SEC, ts + TAPE_WINDOW_AFTER_SEC
        if complete_above is not None and a <= complete_above:
            continue
        hit = [d for at, d in evs if a <= at <= b]
        if len(hit) != want:
            continue
        hit.sort(key=lambda e: -(_num_stamp(e.get("dollars")) or 0))
        try:
            items = [{"symbol": str(e["symbol"]).strip().upper(), "text": headline(e)}
                     for e in hit]
        except Exception:                                    # noqa: BLE001
            continue
        if all(it["symbol"] for it in items):
            out[i] = items
    return out


KNOWN_TTL_SEC = 3600
_known_cache: dict = {"at": 0.0, "set": None}


def known_symbols(loader=None, renames=None, delisted=None) -> frozenset:
    """Every symbol a derived token is allowed to be.

    ``load_universe("full")`` ∪ the RENAMES keys (the OLD symbol, still spelled
    in an old push body) ∪ each rename's NEW symbol (``value[0]`` — RENAMES is
    {OLD: (NEW, effective, evidence)}) ∪ the DELISTED keys (a 90-day-old push
    can name a symbol that died since). Cached for ``KNOWN_TTL_SEC``; the
    loaders are injectable for tests.
    """
    now = time.time()
    if (loader is None and renames is None and delisted is None
            and _known_cache["set"] is not None
            and now - _known_cache["at"] < KNOWN_TTL_SEC):
        return _known_cache["set"]
    if loader is None or renames is None or delisted is None:
        from sepa import symbols as SY
        from sepa import universe as UN
        loader = loader or (lambda: UN.load_universe("full"))
        renames = SY.RENAMES if renames is None else renames
        delisted = SY.DELISTED if delisted is None else delisted
    try:
        base = {str(t).upper() for t in (loader() or [])}
    except Exception as exc:                                  # pragma: no cover
        log.warning("push.recent: universe load failed: %s", exc)
        base = set()
    base |= {str(k).upper() for k in (renames or {})}
    base |= {str(v[0]).upper() for v in (renames or {}).values() if v}
    base |= {str(k).upper() for k in (delisted or {})}
    out = frozenset(base)
    _known_cache["at"], _known_cache["set"] = now, out
    return out


def derive_tickers(row: dict, known: frozenset) -> list:
    """The names one feed row links to, in body order.

    1. a stored ``tickers`` list wins (the builder knew them at push time);
    2. else a single push's ``ticker``;
    3. else, and ONLY for a DIGEST kind, the LEADING token of each
       comma/newline-separated item of the body, kept when it looks like a
       ticker AND is in ``known``. "NVDA, AVGO · pushed 08:15 ET · NEW AT"
       yields ["NVDA", "AVGO"] even when ET and AT are real symbols — they are
       not in leading position. "+3 more on the board" yields nothing.
    4. else [].

    The derivation is a best-effort read of OLD rows only; every row stored
    from 2026-09-20 carries the list.
    """
    stored = row.get("tickers")
    if isinstance(stored, list) and stored:
        out, seen = [], set()
        for t in stored:
            if not isinstance(t, str):
                continue
            u = t.upper()
            if u and u not in seen:
                seen.add(u)
                out.append(u)
        if out:
            return out
    tick = row.get("ticker")
    if isinstance(tick, str) and tick.strip():
        return [tick.strip().upper()]
    if row.get("kind") not in DIGEST_KINDS:
        return []
    body = row.get("body")
    if not isinstance(body, str) or not body:
        return []
    out, seen = [], set()
    for line in body.split("\n"):
        for item in line.split(", "):
            tok = lead_symbol(item, known)
            if tok and tok not in seen:
                seen.add(tok)
                out.append(tok)
    return out


_EMOJI = {
    "volume_breakout":          "🚀",
    "rising_momentum":          "📈",
    "stage_breakdown_2_3":      "⚠️",
    "stage_breakdown_2_4":      "🔻",
    "stage_breakdown_3_4":      "🔻",
}
_LABEL = {
    "volume_breakout":          "Volume breakout",
    "rising_momentum":          "Rising momentum",
    "stage_breakdown_2_3":      "Stage 2→3 topping",
    "stage_breakdown_2_4":      "Stage 2→4 cliff",
    "stage_breakdown_3_4":      "Stage 3→4 decline",
}


def parse_kinds(raw: Optional[str]) -> Optional[list]:
    """'a, b,,c' -> ['a', 'b', 'c']; None / blank / only commas -> None (no filter)."""
    if raw is None:
        return None
    out = []
    for part in str(raw).split(","):
        k = part.strip()
        if k and k not in out:
            out.append(k)
    return out or None


def is_breakout_kind(kind: str) -> bool:
    return kind in BREAKOUT_KINDS or kind.startswith(BREAKOUT_KIND_PREFIX)


def breakout_kinds(kind_list: Optional[list]) -> Optional[list]:
    """None = no kinds filter, include every breakout row (the old feed);
    [] = the list named no breakout kind, exclude the source; else the subset
    of the list that lives in sepa_breakouts."""
    if kind_list is None:
        return None
    return [k for k in kind_list if is_breakout_kind(k)]


def normalize_breakout(b: dict) -> dict:
    """One sepa_breakouts doc -> the feed row shape. Title = emoji + kind label
    + ticker (the BreakoutAlertBanner vocabulary); the body carries price + day
    change so the history view still reads after the banner is dismissed."""
    ticker = b.get("ticker") or ""
    kind = b.get("kind") or "volume_breakout"
    emoji = _EMOJI.get(kind, "📣")
    label = _LABEL.get(kind, kind)
    ts = int(b.get("ts") or 0)
    ctx = b.get("context") or {}
    extras: list = []
    if ctx.get("last_close") is not None:
        extras.append(f"${float(ctx['last_close']):.2f}")
    if ctx.get("day_change_pct") is not None:
        d = float(ctx["day_change_pct"])
        extras.append(f"{'+' if d >= 0 else ''}{d:.1f}%")
    extras_str = "  ·  ".join(extras)
    reason = (b.get("reason") or "").strip()
    body = f"{extras_str}\n{reason}" if extras_str else reason
    return {
        "_id":          str(b.get("_id")),
        "ts":           ts,
        "ts_iso":       datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None,
        "title":        f"{emoji} {label} · {ticker}",
        "body":         body,
        "kind":         kind,
        "ticker":       ticker,
        # One shape for the feed: a breakout row names exactly its own symbol.
        "tickers":      [ticker] if ticker else [],
        "url":          f"/sepa/{ticker}?from=alert" if ticker else None,
        "user_email":   None,
        "sent":         0,
        "failed":       0,
        "total":        0,
        "source":       "breakout",
        # A breakout row is not a demand-zone push and carries no 🎯 verdict —
        # the key is present and null so the feed row shape is one shape
        # (2026-09-15).
        "enterable":    None,
        "dismissed":    bool(b.get("dismissed_at")),
    }


def breakout_query(kind_list: Optional[list], since: Optional[int],
                   ticker: Optional[str]) -> Optional[dict]:
    """The sepa_breakouts filter, or None when the source is excluded. `{}`
    with no params = the old unfiltered read."""
    bk_kinds = breakout_kinds(kind_list)
    if bk_kinds is not None and not bk_kinds:
        return None
    q: dict = {}
    if bk_kinds:
        q["kind"] = {"$in": bk_kinds}
    if since is not None:
        q["ts"] = {"$gte": int(since)}
    if ticker:
        q["ticker"] = ticker
    return q


def _retired_kinds() -> frozenset:
    """push.subs.RETIRED_2026_09_20, imported lazily (the registry owns the
    list; this module never retypes a kind). Empty if the registry is
    unavailable so a read never fails on the filter."""
    try:
        from push import subs
        return frozenset(subs.RETIRED_2026_09_20)
    except Exception:                                    # noqa: BLE001
        return frozenset()


# --------------------------------------------------------------------------
# Repeat collapse (2026-09-21)
# --------------------------------------------------------------------------
# Ajay, asked "Collapse the 2,022 old rows on the Alerts page?": "Yes to all..".
# He is NOT asking to delete or hide history — the rows stay readable, they
# stop filling the page one identical line at a time. His screenshot showed the
# same ARM line twice and the same ON line twice inside one 15:00 ET block.
# Presentation only: nothing here gates, ranks or hides a KIND.


def _et_dt(ts) -> datetime:
    """The market-time datetime for a unix stamp. Raises on garbage — every
    caller wraps it, because a clock must never blank the feed."""
    from zoneinfo import ZoneInfo
    return datetime.fromtimestamp(int(ts), ZoneInfo("America/New_York"))


def _et_clock(ts) -> Optional[str]:
    """"15:00" in market time — the page's own ``etFromTs`` style (24h,
    zero-padded), so the served sentence reads as one voice with the row."""
    try:
        return _et_dt(ts).strftime("%H:%M")
    except Exception:                                        # noqa: BLE001
        return None


def _et_day(ts) -> Optional[str]:
    """"Jun 5" in market time, from the ONE engine that already writes those
    words in his price-alert messages (``sepa.price_alerts._et_day_label``).
    That import pulls notify/prices/massive_keys, so it is lazy AND wrapped:
    if it fails we fall back to YYYY-MM-DD off the same zoneinfo datetime
    rather than growing a second "Mon D" formatter."""
    try:
        from sepa.price_alerts import _et_day_label
        label = _et_day_label(ts)
        if label:
            return label
    except Exception:                                        # noqa: BLE001
        pass
    try:
        return _et_dt(ts).strftime("%Y-%m-%d")
    except Exception:                                        # noqa: BLE001
        return None


def repeat_key(row: dict) -> tuple:
    """(source, kind, ticker, title, tickers). Exact strings — no normalisation
    beyond ticker upper/None; the BODY is NOT part of the identity (see the
    doc: two presets on one print differ only by their Note and must fold).
    ``tickers`` (the served list, always present after gather's tagging) keeps
    two count-only digests with different names apart — "🚀 3 growth names at
    demand" carries a count and no name, so without it two such rows with the
    same count would swallow each other."""
    t = row.get("ticker")
    t = t.strip().upper() if isinstance(t, str) and t.strip() else None
    tk = row.get("tickers")
    tk = tuple(x for x in tk if isinstance(x, str)) if isinstance(tk, list) else ()
    return (row.get("source") or "push", row.get("kind"), t, row.get("title"), tk)


def repeat_line(count: int, first_ts, last_ts, *, truncated: bool = False) -> str:
    """The whole sentence the surfaces print verbatim.

    "1 more like this · first 15:00 ET, last 15:00 ET"   (same ET day)
    "12 more like this · first Jun 5 ET, last Sep 21 ET" (across days)
    "40+ more like this · first Aug 31 ET, last Sep 21 ET" (the raw fetch cut it)

    ``count`` is the GROUP size, so the number shown is count - 1 — the
    survivor is already on screen. "first" means the oldest row IN THIS READ
    (the ``since`` window and the raw fetch cap), never "first ever".
    """
    try:
        n = int(count) - 1
    except Exception:                                        # noqa: BLE001
        n = 0
    head = f"{n}{'+' if truncated else ''} more like this"
    try:
        first = int(first_ts or 0)
        last = int(last_ts or 0)
    except Exception:                                        # noqa: BLE001
        return head
    if first <= 0 or last <= 0:
        return head
    try:
        same_day = _et_dt(first).date() == _et_dt(last).date()
    except Exception:                                        # noqa: BLE001
        return head
    fmt = _et_clock if same_day else _et_day
    a, b = fmt(first), fmt(last)
    if not a or not b:
        return head
    return f"{head} · first {a} ET, last {b} ET"


def repeat_block(group: list, *, truncated: bool = False) -> dict:
    """The served block for a folded group (always >= 2 members). ``count``
    includes the survivor; ``last_ts`` is the survivor's own stamp."""
    stamps = []
    for r in group:
        try:
            stamps.append(int(r.get("ts") or 0))
        except Exception:                                    # noqa: BLE001
            stamps.append(0)
    first_ts = min(stamps) if stamps else 0
    last_ts = stamps[0] if stamps else 0
    return {
        "count":        len(group),
        "first_ts":     first_ts,
        "first_ts_iso": (datetime.fromtimestamp(first_ts, tz=timezone.utc).isoformat()
                         if first_ts > 0 else None),
        "last_ts":      last_ts,
        "truncated":    bool(truncated),
        "line":         repeat_line(len(group), first_ts, last_ts, truncated=truncated),
    }


def collapse_repeats(rows: list, *, tail_truncated: bool = False) -> list:
    """Fold maximal runs of ADJACENT rows sharing ``repeat_key`` into the
    newest member of each run.

    "Adjacent" is literal: adjacent in the served ts-desc list AFTER the
    retired filter and the merge. An interleaved different alert splits a run
    on purpose — [ARM, ON, ARM] is three events, not two.

    A run of 1 is passed through as the SAME dict object, untouched and with
    no ``repeat`` key (the pre-2026-09-21 row, byte-identical). A run of >= 2
    yields a shallow COPY of the newest row plus ``repeat``; the input list and
    its dicts are never mutated.

    ``tail_truncated`` (the raw push fetch hit its cap) stamps ``truncated`` on
    the LAST PUSH run — whatever its size — and only when that run has >= 2
    members. The cut is on the push fetch, and a breakout run can sit older
    than every push in the merged list, so the marker never lands there. A
    singleton push tail closes every run above it (no row of those runs can
    exist past the cut), so it carries nothing and nothing else is marked
    either; the payload's top-level ``raw_truncated`` is what covers that case.
    """
    groups: list = []
    i, n = 0, len(rows)
    while i < n:
        key = repeat_key(rows[i])
        j = i
        while j + 1 < n and repeat_key(rows[j + 1]) == key:
            j += 1
        groups.append(rows[i:j + 1])
        i = j + 1
    mark = -1
    if tail_truncated:
        for idx, g in enumerate(groups):
            if (g[0].get("source") or "push") == "push":
                mark = idx
        # the LAST push run owns the cut; a singleton one closes every run
        # above it, so nothing at all is marked in that case.
        if mark >= 0 and len(groups[mark]) < 2:
            mark = -1
    out: list = []
    for idx, g in enumerate(groups):
        if len(g) < 2:
            out.append(g[0])
            continue
        row = dict(g[0])
        row["repeat"] = repeat_block(g, truncated=(idx == mark))
        out.append(row)
    return out


def gather(email: Optional[str], limit: int, *, kinds: Optional[str] = None,
           since: Optional[int] = None, ticker: Optional[str] = None,
           list_recent=None, get_db=None, collapse: bool = True) -> list:
    """Merge push_history + sepa_breakouts, ts desc, capped at `limit`.

    Still returns a LIST — every existing caller reads a list. The payload
    flags ride on ``gather_payload`` instead.
    """
    rows, _ = _gather(email, limit, kinds=kinds, since=since, ticker=ticker,
                      list_recent=list_recent, get_db=get_db, collapse=collapse)
    return rows


def gather_payload(email: Optional[str], limit: int, *, kinds: Optional[str] = None,
                   since: Optional[int] = None, ticker: Optional[str] = None,
                   list_recent=None, get_db=None, collapse: bool = True) -> dict:
    """What the route serves: ``{rows, count, collapse, raw_truncated}``."""
    rows, raw_truncated = _gather(email, limit, kinds=kinds, since=since, ticker=ticker,
                                  list_recent=list_recent, get_db=get_db, collapse=collapse)
    return {"rows": rows, "count": len(rows), "collapse": bool(collapse),
            "raw_truncated": bool(raw_truncated)}


def _gather(email: Optional[str], limit: int, *, kinds: Optional[str] = None,
            since: Optional[int] = None, ticker: Optional[str] = None,
            list_recent=None, get_db=None, collapse: bool = True) -> tuple:
    """(rows, raw_truncated). `list_recent` / `get_db` are injectable for tests
    (default: the real push.history.list_recent and sepa.breakouts._get_db)."""
    if list_recent is None:
        from push import history
        list_recent = history.list_recent
    if get_db is None:
        from sepa import breakouts as bk
        get_db = bk._get_db
    kind_list = parse_kinds(kinds)
    tick = (ticker or "").strip().upper() or None
    limit = max(1, min(int(limit or 1), MAX_LIMIT))

    # Push-history rows are already in the right shape; just tag them. The
    # positional (email, limit) call is the pre-2026-09-05 one; the filters
    # ride as kwargs only when asked for, so the default read is unchanged.
    extra = {}
    if kind_list is not None:
        extra["kinds"] = kind_list
    if since is not None:
        extra["since_ts"] = int(since)
    if tick:
        extra["ticker"] = tick
    # `limit` counts COLLAPSED rows, so the raw push fetch over-reads (bounded
    # by MAX_LIMIT) — the default read is 50 raw, not 25. `raw_truncated` is
    # measured HERE, on the raw fetch, never on the served length: after a fold
    # the served list is shorter than the cap and the page's "newest 500 only"
    # warning would otherwise vanish exactly when it matters.
    raw_limit = min(limit * COLLAPSE_OVERFETCH, MAX_LIMIT) if collapse else limit
    pushes = list_recent(email, raw_limit, **extra)
    raw_truncated = bool(collapse) and len(pushes) >= raw_limit
    # RETIRED kinds never reach a surface he reads (Ajay 2026-09-20: "Remove
    # volleyball and learning of stocks I do dont wanna see them they are
    # spamming too much"). The spam was HERE, not on his phone: push_history
    # held 1,710 hourly minervini_flashcards rows (the module behind that kind
    # was deleted 2026-09-20 — "Delete Flashcards please") + ~215 vb_* rows, every one
    # `sent=0` since the 2026-09-08 keep-set, and the bell / Alerts page drew
    # all of them. The rows stay in Mongo until the 90-day TTL (evidence,
    # reversible); this filter is what hides them. A serve-time filter, not a
    # purge — flipping it back is one line.
    pushes = [p for p in pushes if p.get("kind") not in _retired_kinds()]
    known = known_symbols() if pushes else frozenset()
    # OLD ⚡ tape-burst rows get every burst back from trade_flash_events —
    # one bounded read for the whole page, only when such a row is on it.
    tape = tape_items_for_legacy(pushes, get_db) if pushes else {}
    for idx, p in enumerate(pushes):
        if idx in tape:
            p["items"], p["items_total"] = tape[idx], len(tape[idx])
        p["source"] = "push"
        # Present on every row, null on the ones stored before 2026-09-15 and
        # on the kinds that carry no read.
        p.setdefault("enterable", None)
        # Always a list (2026-09-20): the stored one, the single's ticker, or
        # what an old digest body names. Never None — the chips render nothing
        # on [].
        p["tickers"] = derive_tickers(p, known)
        # EVERY item of a consolidated push (2026-09-29): served only when the
        # row lists linkable lines; `items_total` is storage-only, never served.
        served = served_items(p, known)
        p.pop("items_total", None)
        if served:
            p["items"], p["items_not_stored"] = served
        else:
            p.pop("items", None)

    breakout_rows: list = []
    bq = breakout_query(kind_list, since, tick)
    if bq is not None:
        try:
            db = get_db()
        except Exception:
            db = None
        if db is not None:
            try:
                cur = db.sepa_breakouts.find(bq).sort("ts", -1).limit(BREAKOUT_SOURCE_CAP)
                for b in cur:
                    breakout_rows.append(normalize_breakout(b))
            except Exception:
                pass

    merged = pushes + breakout_rows
    # Stable sort, no tie-break key: within equal ts the push rows keep their
    # Mongo index order and stay ahead of the breakouts. Adding a tie-break
    # here would reorder the default read AND reshuffle which rows are
    # adjacent, which is what the collapse groups on.
    merged.sort(key=lambda r: r.get("ts") or 0, reverse=True)
    if collapse:
        merged = collapse_repeats(merged, tail_truncated=raw_truncated)
    return merged[:limit], raw_truncated


@router.get("/notifications/recent")
async def notifications_recent(
    limit: int = Query(25, ge=1, le=MAX_LIMIT,
                       description="Max merged rows to return"),
    kinds: Optional[str] = Query(None, description="Comma-separated push kinds; breakout rows "
                                                   "only when a breakout kind is named"),
    since: Optional[int] = Query(None, ge=0, description="Unix seconds; rows with ts >= since"),
    ticker: Optional[str] = Query(None, max_length=16, description="One symbol (upper-cased)"),
    collapse: bool = Query(True, description="Fold adjacent rows with the same "
                                             "source+kind+ticker+title(+tickers) into the newest "
                                             "one, with a served `repeat` block; false = the flat list"),
    email: str = Depends(current_user_email),
):
    """Unified recent-notifications feed: push_history + sepa_breakouts.

    The NotificationBell dropdown, the /notifications history panel and the
    /alerts page (2026-09-05) all consume this endpoint so volume breakouts /
    stage breakdowns from the sepa_breakouts collection show up alongside the
    pushes captured via push_history (flashcards, morning brief, S/D alerts).

    Sorted by ts desc, capped at ``limit``. Breakouts are pulled with a
    200-row hard cap on the source side so a wildly long banner stack doesn't
    bloat the merge. See the module docstring for the filter params.

    2026-09-21: adjacent identical rows arrive folded into one survivor
    carrying ``repeat`` (``collapse=false`` = the old flat list), and the
    payload carries ``collapse`` + ``raw_truncated``.
    """
    payload = await asyncio.to_thread(gather_payload, email, limit, kinds=kinds,
                                      since=since, ticker=ticker, collapse=collapse)
    return JSONResponse(payload)


__all__ = ["router", "gather", "gather_payload", "parse_kinds", "breakout_kinds",
           "breakout_query", "normalize_breakout", "derive_tickers", "known_symbols",
           "collapse_repeats", "repeat_key", "repeat_block", "repeat_line",
           "DIGEST_KINDS", "MAX_LIMIT", "KNOWN_TTL_SEC", "COLLAPSE_OVERFETCH",
           "served_items", "lead_symbol", "lead_token", "item_url", "ITEM_KINDS",
           "ITEM_URL_BY_KIND", "DEFAULT_ITEM_URL", "tape_items_for_legacy",
           "tape_recon_want", "TAPE_WINDOW_BEFORE_SEC", "TAPE_WINDOW_AFTER_SEC"]
