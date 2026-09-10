"""📐 Chart-pattern alerts — Ajay 2026-09-09:

    "Can you give me hot pull back alerts and chart pattern Alerts and also
     Sameday deman alerts please... Kill all other.. I just wanna these alerts."

WHAT FIRES. One push per (symbol, pattern, confirmation day) on a pattern that
CONFIRMED on the daily frame — the scan's own `status == "confirmed"` with
`bars_since_confirm` inside FRESH_BARS. `patterns_scan` is written by the
existing scan; this module never rescans, it only reads and pushes.

WHAT THE PUSH SAYS, AND WHY. His own ledger, 669 resolved observations graded 21
sessions forward:

    cup_with_handle          n=434   45% up
    double_bottom            n=248   43% up
    triple_bottom            n= 68   37% up
    inverse_head_shoulders   n= 10   10% up
    PLACEBO (all resolved)   n=659   50% up

NOT ONE BEATS CHANCE. He was shown that and asked for the alerts anyway. So the
pattern's own record and the placebo ride in the body of every single push. This
is a watchlist ping and the phone says so; it is not a signal this app can stand
behind, and nothing in here is allowed to imply otherwise.

flat_top is excluded outright — it fired on 120 of 120 random names.

THE DEMAND GATE. Ajay 2026-09-09: "Also on the Patterns you know the deal, we
need make sure they need to be in demand zone or bouncing off demand zone."
A confirmation only reaches the phone when the name is standing at a level:

  IN THE ZONE   the print sits inside an eligible demand band
                (supply_demand.bounce_room.in_demand_read)
  REVERSING     a session low in the last 5 touched such a band and the print
                is now >= max(3%, 1 ATR) above it (bounce_room.bounce_read)

Neither read is new and neither invents a threshold: they are the SAME two
reads the 🪃 push, the Back-in-Demand sort and the SEPA 🪃 chip already use, so
"at demand" cannot come to mean two things. This is a TIGHTENING on top of the
existing freshness rule, never a loosening — and it FAILS CLOSED: a name with
no zone coverage and no buildable one sends nothing, counted separately
(``skipped_no_zone``) from a name that has coverage and simply is not at a
level (``skipped_no_demand``), so a quiet morning can always be told apart
from a blind one.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger("patterns.pattern_alerts")

KIND = "pattern_alert"
STATE_COLL = "pattern_alerts"
SCAN_DOC_ID = "latest"     # patterns.scan writes this id; NOT the newest by generated_at
FRESH_BARS = 2           # confirmed within this many sessions
MAX_SINGLES = 4
# Where a tap lands. The board moved into Chart Maps on 2026-09-09; /patterns
# still redirects here, but the push should not spend a hop.
PUSH_URL = "/chart-maps?tab=patterns"
# Zone docs the pass may build on demand when the store has no coverage for a
# fresh name. The fresh list is a handful a day; this only bounds a bad day.
MAX_ZONE_BUILDS = 40
# How far above a demand band's TOP the print may still sit and count as
# standing AT the level. bounce_room.bounce_read has no ceiling by design — it
# powers FILTERS, where a name that touched a band and ran is still a true
# answer. A PUSH is not a filter: the first dry run passed SIG at 28% above the
# band it last touched, which is the exact "late by the time it reaches me"
# complaint the demand kinds already guard. Same value as the Quick Reversal
# board's live rule ("inside a proven demand band or <= 5% above its top") —
# supply_demand.quick_bounce.NEAR_MAX_PCT, pinned equal in
# tests/test_supply_demand_contracts.py. Not a new number, an existing one.
NEAR_MAX_PCT = 5.0
ET = ZoneInfo("America/New_York")


def _db():
    try:
        from pymongo import MongoClient
        cli = MongoClient(os.getenv("MONGO_URL", "mongodb://mongo:27017"),
                          serverSelectionTimeoutMS=2500)
        return cli[os.getenv("MONGO_DB", "cheetah")]
    except Exception as exc:                                   # noqa: BLE001
        log.warning("pattern_alerts: no db: %s", exc)
        return None


def _day_et(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(tz=ET)).astimezone(ET).date().isoformat()


def record_line(pattern: str) -> str:
    """The pattern's measured record beside the placebo. Standing rule: never a
    per-name rate without its placebo. Read from the one table."""
    from supply_demand import bullish_context as BC
    rec = BC.PATTERN_RECORD.get(pattern)
    n_p, up_p, _ = BC.PATTERN_PLACEBO
    if not rec:
        return "no measured record · placebo %d%% up (n=%d)" % (up_p, n_p)
    n, up, mean = rec
    return ("your ledger: %d%% up over %d · placebo %d%% — it does NOT beat chance"
            % (up, n, up_p))


def is_fresh(row: dict, fresh_bars: int = FRESH_BARS) -> bool:
    """Confirmed, named, and recent. Anything unreadable is NOT fresh."""
    from supply_demand import bullish_context as BC
    if not isinstance(row, dict):
        return False
    name = row.get("pattern")
    if not name or name in BC.NOISE_PATTERNS:
        return False
    if str(row.get("status") or "").lower() != "confirmed":
        return False
    b = row.get("bars_since_confirm")
    try:
        b = int(b)
    except (TypeError, ValueError):
        return False
    return 0 <= b <= fresh_bars


def demand_anchor(sym: str, doc: Optional[dict], snap: Optional[dict],
                  fallback_px=None, now: Optional[datetime] = None,
                  near_max_pct: float = NEAR_MAX_PCT) -> Optional[dict]:
    """"At demand" for one name, or None. {"state", "price", "band", "role", ...}
    with state "in_zone" (inside an eligible demand band) or "reversal" (touched
    one in the last 5 sessions and lifted off it).

    Both reads come from supply_demand.bounce_room — the module that owns this
    question for every other surface. FAILS CLOSED: no doc, a tombstone doc, or
    no usable price -> None, and the caller must not push.
    """
    from supply_demand import bounce_room as BR
    if not isinstance(doc, dict) or not doc or doc.get("error"):
        return None
    px = None
    if snap:
        px, _fresh = BR.print_of(snap, (now or datetime.now(tz=ET)).timestamp())
    if px is None:
        px = _num(fallback_px)          # the scan's own last close, pre-market
    if px is None or px <= 0:
        return None
    inz = BR.in_demand_read(px, doc)
    if inz:
        return {"state": "in_zone", "price": round(px, 4), "band": inz["band"],
                "role": inz["role"], "off_floor_pct": inz["off_floor_pct"]}
    touches = BR.touch_hits(doc, (snap or {}).get("low"), (snap or {}).get("date"),
                            doc.get("date"), snapshot=snap)
    rev = BR.bounce_read(px, doc, touches)
    if not rev:
        return None
    hi = _num((rev.get("band") or {}).get("hi"))
    if hi is None or hi <= 0:
        return None                                   # unreadable band: fail closed
    above_pct = (px / hi - 1.0) * 100.0
    if above_pct > near_max_pct:
        return None                                   # it already ran: too late
    return {"state": "reversal", "price": round(px, 4), "band": rev["band"],
            "role": rev["role"], "off_low_pct": rev["bounce_pct"],
            "above_top_pct": round(above_pct, 2),
            "sessions_ago": rev["sessions_ago"]}


def anchor_txt(anchor: Optional[dict]) -> str:
    """The words for the gate in the push body, so the phone says WHY it rang."""
    if not isinstance(anchor, dict):
        return ""
    band = anchor.get("band") or {}
    lo, hi = _num(band.get("lo")), _num(band.get("hi"))
    where = ("$%g-%g" % (lo, hi)) if lo is not None and hi is not None else "the band"
    level = "broken-supply shelf" if anchor.get("role") == "broken_supply" else "demand"
    if anchor.get("state") == "in_zone":
        return "\U0001F9F2 in %s %s" % (level, where)
    off = _num(anchor.get("off_low_pct"))
    ago = anchor.get("sessions_ago")
    when = "today" if ago in (0, None) else ("%dd ago" % int(ago))
    return "\U0001FA83 reversal off %s %s (+%.1f%%, low %s)" % (
        level, where, off or 0.0, when)


def _num(x):
    """Float or None. Scan rows carry dicts, strings and NaN where a number is
    expected — never let one raise inside a push builder."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


def message(row: dict, anchor: Optional[dict] = None) -> dict:
    sym, pat = row.get("symbol"), row.get("pattern")
    parts = []
    for key, fmt in (("last_close", "$%g"), ("neckline", "neckline $%g"),
                     ("stop", "stop $%g"), ("target", "target $%g")):
        v = _num(row.get(key))
        if v is not None:
            parts.append(fmt % v)
    # WHY it rang at all (Ajay 2026-09-09): the demand read comes before the
    # pattern's record, because the level is the reason and the pattern is not.
    at = anchor_txt(anchor if anchor is not None else row.get("demand_anchor"))
    if at:
        parts.insert(1, at)
    parts.append(record_line(pat))
    return {"title": "\U0001F4D0 %s %s confirmed" % (sym, str(pat).replace("_", " ")),
            "body": " · ".join(parts), "icon": "/icon.svg",
            "tag": "pat-%s" % str(sym).lower(),
            "url": PUSH_URL, "kind": KIND, "ticker": sym,
            "data": {"url": PUSH_URL, "symbol": sym, "source": "patterns"}}


def digest_message(rows: list, day: str) -> Optional[dict]:
    if not rows:
        return None
    from supply_demand import bullish_context as BC
    names = ", ".join(
        "%s (%s%s)" % (r.get("symbol"), str(r.get("pattern")).replace("_", " "),
                       " · in demand" if (r.get("demand_anchor") or {}).get("state") == "in_zone"
                       else " · reversal" if r.get("demand_anchor") else "")
        for r in rows[:10])
    return {"title": "\U0001F4D0 %d more patterns confirmed" % len(rows),
            "body": names + " · placebo %d%% up — none of these beats chance"
                    % BC.PATTERN_PLACEBO[1],
            "icon": "/icon.svg", "tag": "pat-digest-%s" % day,
            "url": PUSH_URL, "kind": KIND, "ticker": None,
            "data": {"url": PUSH_URL, "source": "patterns"}}


def _demand_pass(fresh: list, now: Optional[datetime] = None,
                 anchors: Optional[dict] = None, build: bool = True) -> tuple:
    """Keep only the (key, row) pairs standing at a demand level; stamp the
    survivor's row with ``demand_anchor``. Returns (kept, no_demand, no_zone).

    ``anchors`` short-circuits the whole I/O layer for tests: {SYMBOL: anchor
    or None}, where None means "has coverage, is not at a level".
    """
    if not fresh:
        return [], 0, 0
    syms = sorted({str(r.get("symbol") or "").upper() for _k, r in fresh} - {""})
    # The scan's own confirmation close is the reference price, and pre-market
    # (the 08:15 cron) it is the ONLY one: bulk_snapshot is empty before the
    # open, and a None print silently failed every name closed in the first dry
    # run. A live print, when there is one, still wins.
    fallbacks = {}
    for _k, r in fresh:
        sym = str(r.get("symbol") or "").upper()
        px = _num(r.get("last_close"))
        if sym and px is not None and sym not in fallbacks:
            fallbacks[sym] = px
    if anchors is None:
        anchors = _load_anchors(syms, fallbacks, now=now, build=build)
    kept, no_demand, no_zone = [], 0, 0
    for key, row in fresh:
        sym = str(row.get("symbol") or "").upper()
        if sym not in anchors:               # no coverage at all -> fail closed
            no_zone += 1
            continue
        anchor = anchors.get(sym)
        if not anchor:
            no_demand += 1
            continue
        row = dict(row)
        row["demand_anchor"] = anchor
        kept.append((key, row))
    return kept, no_demand, no_zone


def _load_anchors(syms: list, fallbacks: Optional[dict] = None,
                  now: Optional[datetime] = None, build: bool = True) -> dict:
    """{SYMBOL: anchor or None} for every symbol that HAS zone coverage.
    Symbols absent from the result have none and must not push. Any failure
    here leaves symbols out — silence, never a free pass."""
    from supply_demand import bounce_room as BR
    out: dict = {}
    if not syms:
        return out
    now = now or datetime.now(tz=ET)
    try:
        day = BR.last_weekday(now.astimezone(ET).date())
        docs, missing = BR.load_docs(syms, day)
    except Exception as exc:                                    # pragma: no cover
        log.warning("pattern_alerts: zone load failed: %s", exc)
        return out
    if missing and build:
        for sym in missing[:MAX_ZONE_BUILDS]:
            try:
                doc = BR.default_builder(sym, day)
            except Exception as exc:                            # pragma: no cover
                log.debug("pattern_alerts: zone build failed for %s: %s", sym, exc)
                continue
            if doc and not doc.get("error"):
                docs[sym] = doc
        if len(missing) > MAX_ZONE_BUILDS:
            log.info("pattern_alerts: %d names past the zone-build cap stay quiet",
                     len(missing) - MAX_ZONE_BUILDS)
    try:
        from sepa import prices
        snapshot = prices.bulk_snapshot(list(docs.keys())) or {}
    except Exception as exc:                                    # pragma: no cover
        log.warning("pattern_alerts: snapshot failed: %s", exc)
        snapshot = {}
    for sym, doc in docs.items():
        if not doc or doc.get("error"):
            continue                        # a tombstone is NOT coverage
        out[sym] = demand_anchor(sym, doc, snapshot.get(sym),
                                 fallback_px=(fallbacks or {}).get(sym), now=now)
    return out


def check_once(owner: Optional[str] = None, now: Optional[datetime] = None,
               rows: Optional[list] = None, coll=None, force: bool = False,
               anchors: Optional[dict] = None, build_zones: bool = True) -> dict:
    from push import sender
    from portfolio.alerts import _resolve_owner

    owner = (owner or _resolve_owner()).lower()
    day = _day_et(now)
    if rows is None:
        db = _db()
        doc = None
        if db is not None:
            try:
                # The scan writes _id "latest". Sorting by generated_at instead
                # picks up "qualifier_verdicts" — a different doc in the same
                # collection whose `results` is always empty, so the pass would
                # have found nothing forever and looked like a quiet market.
                # Caught by a dry run before the cron shipped.
                doc = db.patterns_scan.find_one({"_id": SCAN_DOC_ID})
            except Exception as exc:                            # pragma: no cover
                log.warning("pattern_alerts: scan read failed: %s", exc)
        rows = list((doc or {}).get("results") or [])
    rows = list(rows or [])
    if coll is None:
        db = _db()
        coll = getattr(db, STATE_COLL) if db is not None else None

    # The scan can hold the SAME row twice (HGBL double_bottom, 2026-09-09) —
    # the Mongo dedupe only spans passes, so without this it is two identical
    # pushes in one pass.
    fresh, seen, stale, dup, in_pass = [], 0, 0, 0, set()
    for r in rows:
        if not is_fresh(r):
            stale += 1
            continue
        key = "%s:%s:%s" % (r.get("symbol"), r.get("pattern"),
                            str(r.get("confirmed_date") or day)[:10])
        if coll is not None and not force:
            try:
                if coll.find_one({"_id": key}):
                    seen += 1
                    continue
            except Exception as exc:                            # pragma: no cover
                log.warning("pattern_alerts dedupe read failed: %s", exc)
        if key in in_pass:
            dup += 1
            continue
        in_pass.add(key)
        fresh.append((key, r))

    # The demand gate (Ajay 2026-09-09). Runs AFTER dedupe so a name already
    # pushed never pays for a zone build, and BEFORE the singles/digest split so
    # the split only ever sees names that passed.
    fresh, no_demand, no_zone = _demand_pass(fresh, now=now, anchors=anchors,
                                             build=build_zones)

    pushed = 0
    singles, rest = fresh[:MAX_SINGLES], fresh[MAX_SINGLES:]
    to_send = [(k, message(r)) for k, r in singles]
    dig = digest_message([r for _k, r in rest], day)
    if dig is not None:
        to_send.append(("digest:%s" % day, dig))
    for key, msg in to_send:
        res = sender.send_to_user(owner, msg, kind=KIND) or {}
        sent, targets = res.get("sent", 0), res.get("total_targets", 0)
        if sent > 0:
            pushed += 1
        if (sent > 0 or targets == 0) and coll is not None:
            try:
                coll.update_one({"_id": key}, {"$set": {
                    "at": datetime.now(timezone.utc), "day": day,
                    "sent": sent, "targets": targets}}, upsert=True)
            except Exception as exc:                            # pragma: no cover
                log.warning("pattern_alerts dedupe write failed: %s", exc)
    out = {"ran": True, "day": day, "candidates": len(rows), "fresh": len(fresh),
           "skipped_stale": stale, "skipped_seen": seen, "skipped_dup": dup,
           "skipped_no_demand": no_demand, "skipped_no_zone": no_zone,
           "pushed": pushed, "singles": len(singles), "digest": bool(dig)}
    log.info("PATTERN-ALERTS: %s", out)
    return out


if __name__ == "__main__":                                     # pragma: no cover
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    check_once()
