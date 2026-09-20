"""GET /notifications/recent — the unified recent-notifications feed
(push_history + sepa_breakouts), lifted out of main.py on 2026-09-05.

Why a module of its own: the /alerts page (Ajay 2026-09-05: "can I go to a
dedicated page to see the list of alerts? May be add it to recent alerts or
something?") needs this feed filtered to the three Supply & Demand kinds, to a
day, to one ticker — and main.py cannot be imported by the py3.9 test venv,
so the route had no test. Same path, same row shape, same default behaviour
byte-for-byte when the new query params are absent; now behind TestClient.

Query params (all optional; absent = the old feed):
  limit    1..500 (was 100) — merged rows returned
  kinds    comma list, e.g. ``demand_alert,zone_bounce_alert,supply_break_alert``
           → push rows filtered to those kinds; breakout rows ride along
           ONLY when the list names ``volume_breakout`` / ``rising_momentum`` /
           ``stage_breakdown_*`` (otherwise the breakout source is excluded)
  since    unix seconds → rows with ts >= since
  ticker   upper-cased symbol → rows whose ticker equals it

Row shape (normalized across both sources, unchanged apart from `tickers`):
    {_id, ts, ts_iso, title, body, kind, ticker, tickers, url,
     source: 'push' | 'breakout', sent, failed, total, dismissed?}

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


def gather(email: Optional[str], limit: int, *, kinds: Optional[str] = None,
           since: Optional[int] = None, ticker: Optional[str] = None,
           list_recent=None, get_db=None) -> list:
    """Merge push_history + sepa_breakouts, ts desc, capped at `limit`.
    `list_recent` / `get_db` are injectable for tests (default: the real
    push.history.list_recent and sepa.breakouts._get_db)."""
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
    pushes = list_recent(email, limit, **extra)
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
    merged.sort(key=lambda r: r.get("ts") or 0, reverse=True)
    return merged[:limit]


@router.get("/notifications/recent")
async def notifications_recent(
    limit: int = Query(25, ge=1, le=MAX_LIMIT,
                       description="Max merged rows to return"),
    kinds: Optional[str] = Query(None, description="Comma-separated push kinds; breakout rows "
                                                   "only when a breakout kind is named"),
    since: Optional[int] = Query(None, ge=0, description="Unix seconds; rows with ts >= since"),
    ticker: Optional[str] = Query(None, max_length=16, description="One symbol (upper-cased)"),
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
    """
    rows = await asyncio.to_thread(gather, email, limit, kinds=kinds, since=since, ticker=ticker)
    return JSONResponse({"rows": rows, "count": len(rows)})


__all__ = ["router", "gather", "parse_kinds", "breakout_kinds", "breakout_query",
           "normalize_breakout", "derive_tickers", "known_symbols",
           "DIGEST_KINDS", "MAX_LIMIT", "KNOWN_TTL_SEC"]
