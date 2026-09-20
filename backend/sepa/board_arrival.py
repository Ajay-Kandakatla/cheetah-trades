"""✨ Board arrivals — one push the first time a name is PLACED on a board.

Ajay 2026-09-20: *"Default on for any change of todays features Bondes or
Potus or explosive growth or Earnings I wanna see all of them."*

TWO BOARDS, ONE KIND
────────────────────
📈 Bonde (`sepa/bonde.py`) and 🚀 Explosive Growth (`growth/tracker.py`) each
already keep an arrivals ledger — the ✨ NEW badge on the tab. This module
turns an arrival on either ledger into a phone push, and NOTHING else: it
never screens, never scores, never re-ranks. Whatever the board placed, this
rings once.

WHAT FIRES
  * Bonde: a row with `is_new is True` and a `first_seen` stamp, in the
    sections `pivot → explosive → strong → steady`. The 🔎 `rejected`
    section NEVER fires — those names are not on his screen, they are the
    cohort his character clause threw away, and a push would read as a pick.
  * Growth: a row whose symbol is in `tracker.newly_found()`, with its
    `first_seen` read from the `growth_seen` ledger through
    `sepa.first_seen.first_seen_map` (identical schema, pinned identical in
    `tests/test_first_seen.py`).

WHAT NEVER FIRES
  * The FIRST cohort. This pass keeps its own `__meta__.tracking_since` in
    `board_arrival_state`, stamped on the first run with that run's clock IN
    UTC — the clock both ledgers stamp, because `select()` compares the two
    as STRINGS and an ET stamp ("…T17:42:00-04:00") sorts BELOW the UTC
    ledger stamp of the same moment ("…T21:40:00+00:00"), which would make
    the first pass push the whole board. Selection is a STRICT
    `first_seen > tracking_since`. The first pass
    therefore records the baseline and sends nothing — the same rule the two
    ledgers themselves use (`sepa/first_seen.py`), and for the same reason:
    "we have only just started watching" must never render as "these are
    fresh finds".
  * A name already rung. One claim per `(board, symbol)`, no day in the key,
    and `board_arrival_state` has NO TTL — so a name that leaves a board and
    comes back MONTHS later is not rung again. That is deliberate, not an
    oversight: the ledger's `first_seen` is `$setOnInsert` forever, so a
    returning name carries its ORIGINAL arrival date and a second push would
    claim an arrival that did not happen. Whether a genuine return should
    re-arm after N days is his call (spec §7.11).
  * A closed day. `board_arrival` is a MARKET kind: the crontab wrapper
    `python -m market_hours.gate sepa.board_arrival <board>` exits before
    this module is imported, and `push.sender` drops the kind again on the
    device path. The 🚀 board rebuilds SUNDAY 09:00, a closed day, so its
    arrivals ring the next TRADING morning at 08:08 ET. Making the kind
    PERSONAL so Sunday rings is the alternative — his call (spec §7.1).

WHAT THE PUSH SAYS ABOUT ITSELF
  Bonde's own thesis is MEASURED INVERTED (−3.11pp vs a date-matched
  placebo, 2026-09-13) and the Growth board's 100/100 screen has never been
  measured forward. Both facts ride on every body, read from the serving
  module (`bonde.measured_verdict()["headline"]`) rather than retyped. An
  arrival is a LIST EVENT, not an entry — the body says so in words.

SLOTS: Bonde 17:42 ET (right after the 17:40 `sepa.bonde show` that stamps
`first_seen`), growth 08:08 ET, weekdays. `SLOTS_ET` is what `alert_status`
and `rules_info` quote — never a second copy of the crontab minutes.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

# The owner, the spill threshold and the Mongo handle come from the kind this
# one mirrors — imported, never retyped, so a change there moves both.
from growth.alerts import OWNER, MAX_INDIVIDUAL, _db as _growth_db
from supply_demand import demand_alerts as DA
from sepa import first_seen as FS

# `sepa.bonde` and `growth.tracker` are imported LAZILY inside bonde_rows() /
# growth_rows() / message() ON PURPOSE: `alert_status` and `rules_info` import
# THIS module for its SLOTS_ET, and the S/D rules page must never drag in the
# SEPA board stack (memory: feedback_sepa_book_scope). A subprocess test pins
# both out of `sys.modules` after importing this module.

log = logging.getLogger("sepa.board_arrival")

ET = ZoneInfo("America/New_York")

KIND = "board_arrival"
STATE_COLL = "board_arrival_state"
SOURCE = "board_arrival"          # stamped on every dedupe claim this pass makes
META_ID = "__meta__"

BOARDS = ("bonde", "growth")
LABEL = {"bonde": "📈 Bonde", "growth": "🚀 Explosive Growth"}
TAB_URL = {"bonde": "/chart-maps?tab=bonde", "growth": "/chart-maps?tab=growth"}
SLOTS_ET = {"bonde": "17:42", "growth": "08:08"}   # the crontab minutes, in one place

NOT_BACKTESTED = ("NOTHING HERE IS BACKTESTED: the 100/100 screen has never "
                  "been measured forward.")
NOT_A_RECOMMENDATION = {
    "bonde": "An arrival on his screen, not an entry — not a recommendation.",
    "growth": "An arrival on a list, not an entry — not a recommendation.",
}
PAIR_WITHHELD = ("growth claim withheld — its year-over-year pair is not four "
                 "fiscal quarters apart")
PAIR_UNVERIFIED = "pair unverified — no period keys on file"


def _now() -> datetime:
    return datetime.now(ET)


def _utc_iso(dt: datetime) -> str:
    """The baseline stamp, in the SAME clock the two ledgers write.

    Both ledger writers (`sepa.first_seen` and the 🚀 tracker) stamp
    `datetime.now(timezone.utc).isoformat()` — "2026-09-21T21:40:00+00:00".
    `select()` compares those strings against `tracking_since` lexically, so a
    baseline stamped in ET ("2026-09-21T17:42:00-04:00") reads as EARLIER than
    the very ledger stamp it was written after: "17:42" sorts below "21:40",
    and the first pass would push the whole board. Everything this module
    COMPARES is therefore UTC. The human-facing `at` on a claim doc stays ET —
    nothing compares it."""
    return dt.astimezone(timezone.utc).isoformat()


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _state_coll():
    db = _growth_db()
    return db[STATE_COLL] if db is not None else None


def _state_key(board: str, symbol: str) -> str:
    """One key per (board, symbol) — no day, no TTL. See the module docstring:
    a returning name is silent by design."""
    return "%s|%s" % (board, str(symbol).upper())


def _seen(coll, keys: list) -> set:
    """The subset of `keys` already claimed — one `$in` read, never a find_one
    per name. A read failure is the empty set (push again rather than never).
    Copied from growth.alerts._seen, same failure side."""
    if coll is None or not keys:
        return set()
    try:
        return {str(d["_id"]) for d in coll.find({"_id": {"$in": sorted(set(keys))}}, {"_id": 1})}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("board_arrival: dedupe read failed: %s", exc)
        return set()


def tracking_since(coll, now: datetime) -> str:
    """When THIS pass started watching, as a UTC ISO string.

    Written once with `$setOnInsert`, then read back — so two passes racing on
    the first run agree on one baseline. With no collection the answer is
    `now`, and a strict `>` against it selects nothing: no state, no push.

    UTC, always: the ledgers stamp UTC and `select()` compares the strings
    (see `_utc_iso`). A stamp read back with any other offset is normalised
    before it is returned, so a doc written by an older build can never
    compare as earlier-than-it-was."""
    stamp = _utc_iso(now)
    if coll is None:
        return stamp
    try:
        coll.update_one({"_id": META_ID},
                        {"$setOnInsert": {"tracking_since": stamp}}, upsert=True)
        doc = coll.find_one({"_id": META_ID}) or {}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("board_arrival: tracking_since read failed: %s", exc)
        return stamp
    return _as_utc_str(doc.get("tracking_since") or stamp)


def _as_utc_str(v) -> str:
    """An ISO stamp re-expressed in UTC. Unparseable / naive → returned as-is
    (never guessed into a zone: a wrong guess would move the baseline)."""
    s = str(v)
    try:
        dt = datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return s
    if dt.tzinfo is None:
        return s
    return _utc_iso(dt)


def bonde_rows(payload: Optional[dict] = None) -> list:
    """Every ✨ NEW row the Bonde board PLACED, best section first.

    Section order is the board's own reading order — ⚡ Pivots, then the sales
    tiers — and a name placed twice (a pivot that is also `explosive`) is
    pushed once, under its first placement. `rejected` is never walked."""
    if payload is None:
        from sepa import bonde                                 # lazy — see the docstring
        payload = bonde.board() or {}
    sections = (payload or {}).get("sections") or {}
    out, seen = [], set()
    for k in ("pivot", "explosive", "strong", "steady"):
        for r in (sections.get(k) or []):
            sym = str(r.get("symbol") or "").upper()
            if not sym or sym in seen:
                continue
            seen.add(sym)
            if r.get("is_new") is not True or not r.get("first_seen"):
                continue
            out.append({"board": "bonde", "symbol": sym,
                        "first_seen": r.get("first_seen"), "row": r})
    return out


def growth_rows(board_doc: Optional[dict] = None, new=None, seen=None) -> list:
    """Every 🚀 board row the tracker calls newly found, in served order."""
    from growth import tracker as T                            # lazy — see the docstring
    rows = ((board_doc if board_doc is not None else T.board()) or {}).get("rows") or []
    if new is None:
        new = T.newly_found()
    new = {str(s).upper() for s in (new or [])}
    syms = [str(r.get("symbol") or "").upper() for r in rows]
    syms = [s for s in syms if s and s in new]
    if seen is None:
        seen = FS.first_seen_map(T.SEEN_COLL, syms, db=_growth_db())
    seen = {str(k).upper(): v for k, v in (seen or {}).items()}
    out = []
    for r in rows:
        sym = str(r.get("symbol") or "").upper()
        if not sym or sym not in new:
            continue
        out.append({"board": "growth", "symbol": sym,
                    "first_seen": seen.get(sym), "row": r})
    return out


def select(items: list, since) -> list:
    """The arrivals STRICTLY after `since` — the same ISO string comparison
    `first_seen.newly_found` uses, so the two can never disagree about which
    cohort is the first one. Both sides are UTC stamps: the ledgers write
    `datetime.now(timezone.utc).isoformat()` and `tracking_since` matches
    them (`_utc_iso`). Comparing an ET stamp here silently inverts the rule."""
    out = []
    for it in (items or []):
        fs = it.get("first_seen")
        if fs is None:
            continue
        if str(fs) > str(since):
            out.append(it)
    return out


def _pct(v) -> str:
    return "%+.0f%%" % v


def _tier_txt(row: dict) -> str:
    return row.get("tier") or "tier withheld"


def message(item: dict) -> dict:
    """The push body. Every claim on it is read from the serving module."""
    board = item["board"]
    sym = item["symbol"]
    row = item.get("row") or {}
    first = str(item.get("first_seen") or "")
    parts = ["arrived %s" % first[:10]]

    if board == "bonde":
        from sepa import bonde                                 # lazy — see the docstring
        g = _f(row.get("growth_yoy_pct"))
        title = "✨ New on 📈 Bonde — %s (%s%s)" % (
            sym, _tier_txt(row),
            (" · sales %s YoY" % _pct(g)) if g is not None else "")
        prior = _f(row.get("prior_yoy_pct"))
        if prior is not None:
            parts.append("prior quarter %s" % _pct(prior))
        if row.get("accelerating") is True:
            parts.append("accelerating")
        if row.get("pivot"):
            parts.append("⚡ Episodic Pivot on the tape")
        ok = row.get("period_ok")
        if ok is False:
            parts.append(PAIR_WITHHELD)
        elif ok is None:
            parts.append(PAIR_UNVERIFIED)
        parts.append(bonde.measured_verdict()["headline"])
    else:
        sales = _f(row.get("sales_growth_pct")) or 0.0
        eps = _f(row.get("q_eps_growth_pct")) or 0.0
        title = "✨ New on 🚀 Explosive Growth — %s (sales %s, qEPS %s)" % (
            sym, _pct(sales), _pct(eps))
        prior = _f(row.get("sales_prior_pct"))
        if prior is not None:
            parts.append("prior quarter sales %s" % _pct(prior))
        for w in (row.get("warnings") or []):
            parts.append(str(w))
        parts.append(NOT_BACKTESTED)

    parts.append(NOT_A_RECOMMENDATION[board])
    url = "%s&symbol=%s" % (TAB_URL[board], sym)
    return {"title": title, "body": " · ".join(parts), "ticker": sym,
            "tickers": [sym], "url": url, "kind": KIND,
            "data": {"url": url, "board": board, "source": SOURCE}}


def _digest_tag(item: dict) -> str:
    row = item.get("row") or {}
    if item["board"] == "bonde":
        return _tier_txt(row)
    return "sales %s" % _pct(_f(row.get("sales_growth_pct")) or 0.0)


def digest_message(board: str, items: list) -> dict:
    """The spill, past MAX_INDIVIDUAL — one row per name, body order pinned so
    the ⌘-clickable chips and the text can never disagree."""
    syms = [it["symbol"] for it in items]
    body = ", ".join("%s (%s)" % (it["symbol"], _digest_tag(it)) for it in items)
    if board == "bonde":
        from sepa import bonde                                 # lazy — see the docstring
        tail = bonde.measured_verdict()["headline"]
    else:
        tail = NOT_BACKTESTED
    return {"title": "✨ %d new on %s" % (len(items), LABEL[board]),
            "body": body + " · " + tail, "ticker": None, "tickers": syms,
            "url": TAB_URL[board], "kind": KIND,
            "data": {"url": TAB_URL[board], "board": board, "source": SOURCE}}


def _terminal(res: Optional[dict]) -> bool:
    """Delivered, or nobody targeted. A transport failure releases the claim
    (demand_alerts._terminal, the same rule every other kind reads).

    ONE ADDITION this kind needs and the day-keyed kinds do not: a CLOSED-DAY
    drop (`push.sender` returning `skipped`) is NOT terminal here. Every other
    kind's claim carries the day and expires with it, so keeping a dropped
    claim costs one silent day; this kind's claim is permanent, so keeping it
    would mute the name FOREVER on the strength of a push that never left the
    building. The crontab wrapper already exits before the pass runs on a
    closed day — this is the second line of defence."""
    if isinstance(res, dict) and res.get("skipped"):
        return False
    return DA._terminal(res)


def run(board: str, dry_run: bool = False, *, now: Optional[datetime] = None,
        coll=None, items: Optional[list] = None) -> dict:
    """One pass over one board. At most MAX_INDIVIDUAL individual pushes plus
    one digest, once per (board, symbol) EVER.

    `dry_run` skips only the WRITES (claim / send / release / record): the
    state READ is unconditional, so a dry run reports a name already rung as
    seen, never as fresh. The `__meta__` baseline IS stamped on a dry run —
    it is the honest first cohort either way, and a dry run that left the
    baseline unwritten would let the next wet pass push the whole board."""
    board = str(board or "").lower()
    if board not in BOARDS:
        raise ValueError("unknown board %r (expected one of %s)" % (board, ", ".join(BOARDS)))
    now = now or _now()
    if coll is None:
        coll = _state_coll()                                   # dry runs READ the state too
    since = tracking_since(coll, now)
    first_pass = (since == _utc_iso(now))
    if items is None:
        items = bonde_rows() if board == "bonde" else growth_rows()
    cand = select(items, since)
    for it in cand:
        it["key"] = _state_key(board, it["symbol"])
    seen = _seen(coll, [it["key"] for it in cand])
    fresh = [it for it in cand if it["key"] not in seen]

    sent, digest_sent, claimed_elsewhere = 0, 0, 0
    singles, spill = fresh[:MAX_INDIVIDUAL], fresh[MAX_INDIVIDUAL:]
    if not dry_run:
        from push import sender
        for it in singles:
            doc = {"board": board, "symbol": it["symbol"],
                   "first_seen": it.get("first_seen"), "at": now.isoformat(),
                   "source": SOURCE}
            if not DA.claim_key(coll, it["key"], doc):
                claimed_elsewhere += 1
                continue
            try:
                res = sender.send_to_user(OWNER, message(it), kind=KIND)
            except Exception as exc:                           # noqa: BLE001
                log.warning("board_arrival: push failed for %s: %s", it["symbol"], exc)
                DA.release_key(coll, it["key"])
                continue
            if _terminal(res):
                sent += 1
            else:
                DA.release_key(coll, it["key"])
        digest = []
        for it in spill:
            doc = {"board": board, "symbol": it["symbol"],
                   "first_seen": it.get("first_seen"), "at": now.isoformat(),
                   "source": SOURCE, "digest": True}
            if DA.claim_key(coll, it["key"], doc):
                digest.append(it)
            else:
                claimed_elsewhere += 1
        if digest:
            try:
                res = sender.send_to_user(OWNER, digest_message(board, digest), kind=KIND)
            except Exception as exc:                           # noqa: BLE001
                log.warning("board_arrival: digest push failed: %s", exc)
                res = DA.transport_failed(exc)                 # a raise is NOT "nobody targeted"
            if _terminal(res):
                digest_sent = len(digest)
            else:
                for it in digest:
                    DA.release_key(coll, it["key"])
    else:
        sent, digest_sent = len(singles), len(spill)           # what a wet pass WOULD send

    # NO `skipped_room / skipped_proximity / skipped_direction / skipped_knife /
    # skipped_mood / skipped_floor` here, ever: Alerts.tsx sums those six names
    # over EVERY recorded pass, so a counter borrowing one would silently
    # pollute the S/D gate aggregate on his /alerts page. This kind has no
    # gates to skip — it rings what a board placed.
    summary = {"kind": KIND, "board": board, "ran": True,
               "date": now.astimezone(ET).date().isoformat(),
               "first_pass": first_pass, "tracking_since": since,
               "rows": len(items), "since_tracking": len(cand), "fresh": len(fresh),
               "individual": sent, "digest": digest_sent,
               "claimed_elsewhere": claimed_elsewhere, "dry_run": dry_run}
    if not dry_run:
        try:
            from supply_demand import alert_status as AS
            AS.record_result("%s:%s" % (KIND, board), summary, now=now)
        except Exception as exc:                               # noqa: BLE001
            log.warning("board_arrival: status record failed: %s", exc)
    return summary


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in BOARDS:
        print("usage: python -m sepa.board_arrival <%s> [--dry-run]"
              % "|".join(BOARDS), file=sys.stderr)
        return 2
    print(json.dumps(run(argv[0], dry_run="--dry-run" in argv[1:]), default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
