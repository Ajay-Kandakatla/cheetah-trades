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

Row shape (normalized across both sources, unchanged):
    {_id, ts, ts_iso, title, body, kind, ticker, url,
     source: 'push' | 'breakout', sent, failed, total, dismissed?}
``ts`` is a UTC epoch and ``ts_iso`` UTC — the page formats in
America/New_York and says ET.
"""
from __future__ import annotations

import asyncio
import logging
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
        "url":          f"/sepa/{ticker}?from=alert" if ticker else None,
        "user_email":   None,
        "sent":         0,
        "failed":       0,
        "total":        0,
        "source":       "breakout",
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
    for p in pushes:
        p["source"] = "push"

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
           "normalize_breakout", "MAX_LIMIT"]
