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
     source: 'push' | 'breakout', sent, failed, total, dismissed?, repeat?}
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
})

# Upper-case only, 1-5 letters, with an optional single-letter class suffix —
# load_universe("full") spells class shares with a HYPHEN (BRK-B, HEI-A, MOG-A,
# UHAL-B, BF-B, LEN-B, GEF-B); the dot form is kept for a Massive-spelled body.
# Lower case never matches, so "nvda" in prose is not a ticker.
_TOKEN = re.compile(r"^[A-Z]{1,5}(?:[.-][A-Z])?$")

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
            tok = item.strip().split(" ")[0].split("(")[0].rstrip(",:;")
            if _TOKEN.match(tok) and tok in known and tok not in seen:
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
    for p in pushes:
        p["source"] = "push"
        # Present on every row, null on the ones stored before 2026-09-15 and
        # on the kinds that carry no read.
        p.setdefault("enterable", None)
        # Always a list (2026-09-20): the stored one, the single's ticker, or
        # what an old digest body names. Never None — the chips render nothing
        # on [].
        p["tickers"] = derive_tickers(p, known)

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
           "DIGEST_KINDS", "MAX_LIMIT", "KNOWN_TTL_SEC", "COLLAPSE_OVERFETCH"]
