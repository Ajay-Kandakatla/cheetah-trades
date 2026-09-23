"""💎 Capital-quality upgrade — one push when a BALANCE SHEET actually improves.

Ajay, 2026-09-22: *"Filter and have alerts and new look out for such companies
where whcih have very high quality."*

WHAT THIS IS, AND WHY IT IS THE ONLY TRIGGER THAT SURVIVED
──────────────────────────────────────────────────────────
"This name is high quality" is a STATE, not an event. A state pushed on a timer
either repeats until it is muted or says nothing for a quarter. Four candidate
triggers were enumerated against how often they would ACTUALLY fire, measured on
his live data 2026-09-22; three were rejected and are written down here so the
rejection is not re-litigated from memory:

  (a) A name ARRIVING on the 🚀 board that already grades high — REJECTED,
      twice over. It is already a shipped kind: `sepa/board_arrival.py`
      (`board_arrival`, in `push.subs.OWNER_KEEP_SET` since 2026-09-20) rings on
      exactly this event, so a second kind would buzz his phone twice for one
      arrival. And the event barely happens: MEASURED 2026-09-22, the
      `growth_seen` ledger holds 30 documents, 29 of them stamped 2026-09-12 —
      the ledger's own first cohort — and **ZERO names have arrived in the ten
      days since**. `board_arrival_state` holds one document, the `__meta__`
      baseline: `board_arrival` has claimed no name and pushed nothing in the
      two days it has been live. The board rebuilds SUNDAYS. Filtering a
      ~0-per-week event by quality yields an alert that never fires.

  (b) A COMPONENT FLIPPING on a fresh filing — ACCEPTED. This is the one real
      event in the set, and it is what this module does. See below.

  (c) A high-grade name arriving at a demand band — REJECTED. `growth/alerts.py`
      (`growth_demand_alert`, also in the keep-set, 9 pushes in the last 30 days)
      already fires on precisely that touch, already carries the room /
      proximity / floor-held gates, and already prints the growth figures. A
      quality-filtered copy is a second buzz for one touch. If he wants the
      grade ON that push, it belongs in THAT body — a his-call item, not a kind.

  (d) A weekly digest of the current list — REJECTED, and this is the "cries
      wolf" case the package was warned about. With zero turnover in ten days
      the digest would restate the same ~21 names every week forever. A list
      that never changes is a page, not an alert; the 🚀 tab already is one.

(b) IN ONE SENTENCE
───────────────────
A named DEFINITIONAL component of `growth/capital_quality.py` crosses
**FAIL → PASS** on a **NEW FISCAL QUARTER**: the company went net cash, turned
free-cash-flow positive, stopped raising share count, or turned its return on
capital positive. That is an accounting fact about the business, not a mood.

FOUR THINGS THAT DELIBERATELY NEVER FIRE
────────────────────────────────────────
  * **UNKNOWN → PASS.** That is the APP learning, not the company improving. The
    single loudest instance is already scheduled: WP-2 measured that 0 of the
    485 `board_metrics` documents carry `capital_returns` today, so the two
    RELATIVE components answer `insufficient_peers` for every name. The first
    warm cron that runs with that code flips them for ~15 of 21 names AT ONCE,
    on a day when no business changed anywhere. A grade-word trigger would send
    fifteen pushes for it. This one sends none.
  * **The RELATIVE components, at all.** `roce_above_sector` and
    `capex_below_sector` can move because a PEER filed. "Your company improved"
    must never be said because somebody else got worse. Only the four
    definitional legs are watched, and `test_only_definitional_components_fire`
    pins that to `capital_quality.COMPONENTS` so a new relative leg cannot
    quietly join.
  * **PASS → FAIL.** He asked for a "look out for such companies", not a sell
    signal. The deterioration side is a real and arguably more valuable alert,
    and it is a HIS-CALL item in the doc — not something this package decided
    for him.
  * **The same quarter, twice.** The claim is per `(symbol, fiscal period)`, so
    a provider wobble that re-prints a figure inside one quarter cannot ring.
    This is the 🔔 price-alert lesson paid in advance: that kind re-fired 2,022
    times, every one of them `sent=0`, because a state with no latch re-asserts
    itself every pass.

THE PERIOD GUARD FAILS CLOSED, AND THAT MEANS IT IS SILENT ON DAY ONE
─────────────────────────────────────────────────────────────────────
The quarter is read from `capital_period` — the fiscal quarter the BALANCE SHEET
figures came from, stamped by `sepa/board_metrics._attach_capital_returns`
(Rule #7: the as-of PERIOD, never the cache age). There is no fallback. The
board row also carries a `period`, but that one is the INCOME-STATEMENT quarter
the 100/100 screen ran on; using it as the as-of of a balance-sheet fact would
be reporting a date that is not the date the figure came from.

A row with no `capital_period` is therefore recorded and never pushed
(`no_capital_period`). Measured 2026-09-22: that is every row, because no
`board_metrics` document carries `capital_returns` yet. **This kind is silent
until the `board_metrics` warm cron next runs with WP-1's code** — one cron
away, self-healing, and counted by name on the /alerts page rather than looking
like a dead job. Silent-and-correct beats firing on a proxy date.

WHAT GATES IT: NOTHING — AND THAT IS HIS CALL, NOT AN INVENTED ONE
──────────────────────────────────────────────────────────────────
His standing rule (`alert_gates.room_gate` / `demand_proximity_gate`, 2026-09-05:
*"Need only alerts on stocks that have atleast 5% to Supply and also <1% bounce
from demand zone"*) is scoped to pushes that name a PRICE at a ZONE. This push
names neither: it reports a filing. Applying a room gate would silently convert
a fundamentals notice into an entry signal — "the balance sheet improved, but
only tell me if the chart also has 5% of room" is a different claim than the one
being made. `sepa/board_arrival.py`, the closest precedent and also a board-level
event, applies no gate for the same reason and says so in its own comments.

So **no gate covers this kind**. That is stated rather than patched: adding one
is a decision for him (doc, his-call #1), and this package refused to invent it.

IT SHIPS OFF
────────────
Checked, not assumed. `push.subs.OWNER_KEEP_SET` is an explicit nine-kind
frozenset and this kind is not in it, so `owner_prefs()` hands it back False for
his devices. `default_prefs()` carries it as **False** — registered (a kind
missing from `default_prefs` silently targets zero devices, the 2026-06-24
chokepoint) but muted. No notification pref is flipped by this package. He turns
it on at /notifications, where the toggle explains what it does.

NOT MEASURED
────────────
`capital_quality.MEASURED` is False and `MEASURED_NOTE` rides on every body,
read from the serving module rather than retyped. Nobody has measured whether a
balance sheet improving predicts anything on his universe. Worse: nobody CAN,
yet — there is no historical series of these figures anywhere in the app
(`board_metrics` keeps one document per symbol and overwrites it). The state
collection this module writes is the first such history; a study becomes
possible once it has quarters in it.

SLOT: 17:52 ET, weekdays — after the 17:45 `sepa.board_metrics warm` that writes
the balance sheet this reads. `SLOT_ET` is what `alert_status` and `rules_info`
quote; never a second copy of the crontab minute.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

# The owner, the spill threshold and the Mongo handle come from the sibling
# kind on this same board — imported, never retyped, so a change there moves
# both. Same import `sepa/board_arrival.py` makes, for the same reason.
from growth.alerts import OWNER, MAX_INDIVIDUAL, _db
from growth import capital_quality as CQ
from supply_demand import demand_alerts as DA

log = logging.getLogger("growth.quality_alerts")

ET = ZoneInfo("America/New_York")

KIND = "capital_quality_upgrade"
STATE_COLL = "capital_quality_state"
SOURCE = "quality_alerts"          # stamped on every dedupe claim this pass makes
SLOT_ET = "17:52"                  # the crontab minute, in ONE place
TAB_URL = "/chart-maps?tab=growth"

# `_id` namespaces inside the ONE collection. The state doc is what the pass
# compares against; the claim doc is what stops a second push for the same
# quarter even if a state write is lost.
STATE_PREFIX = "state"
CLAIM_PREFIX = "claim"

# The four DEFINITIONAL legs, in his words, phrased as the EVENT rather than
# the state — "now holds more cash than debt", not "holds more cash than debt".
# Keys are pinned equal to capital_quality's definitional component keys by
# `test_every_definitional_component_has_a_phrase`, so a new leg over there
# fails this module's tests until it is given words here rather than pushing a
# raw key at his phone.
UPGRADE_PHRASE = {
    "net_cash":      "now holds more cash than debt",
    "positive_fcf":  "now throws off cash instead of burning it",
    "no_dilution":   "share count stopped rising",
    "positive_roce": "return on capital turned positive",
}

NOT_A_RECOMMENDATION = ("A filing changed, not a setup — not an entry and not a "
                        "recommendation.")


def _now() -> datetime:
    return datetime.now(ET)


def _definitional_keys() -> tuple:
    """The component keys this kind is allowed to fire on, read from the module
    that defines them. NEVER a second hand-typed list: a relative leg added
    there must not silently become a trigger here."""
    return tuple(k for k, kind, _label in CQ.COMPONENTS if kind == CQ.DEFINITIONAL)


def _state_coll():
    db = _db()
    return db[STATE_COLL] if db is not None else None


def _state_id(symbol: str) -> str:
    return "%s|%s" % (STATE_PREFIX, str(symbol).upper())


def _claim_id(symbol: str, period: str) -> str:
    """One claim per (symbol, fiscal quarter) — no day in the key, no TTL.
    A quarter is rung once, ever."""
    return "%s|%s|%s" % (CLAIM_PREFIX, str(symbol).upper(), str(period))


def read_state(coll, symbols: list) -> dict:
    """{SYMBOL: {"components": {...}, "period": str}} for the names in hand.

    ONE `$in` read, never a find_one per name. A read failure is the EMPTY map
    — which makes every name look like a first observation, and a first
    observation NEVER pushes. That is the safe side for this kind and the
    opposite of `growth.alerts._seen`, whose empty-on-failure means "push
    again rather than never": there, a lost read costs a duplicate; here it
    would cost a FALSE upgrade claim, so it must cost silence instead.
    """
    if coll is None or not symbols:
        return {}
    ids = sorted({_state_id(s) for s in symbols if s})
    try:
        docs = list(coll.find({"_id": {"$in": ids}}))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("quality_alerts: state read failed: %s", exc)
        return {}
    out = {}
    for d in docs:
        sym = str(d.get("symbol") or "").upper()
        if sym:
            out[sym] = {"components": dict(d.get("components") or {}),
                        "period": d.get("period")}
    return out


def observed(read: dict) -> dict:
    """The verdicts worth remembering: {component_key: verdict}, definitional
    only. UNKNOWN is stored as UNKNOWN — it must stay distinguishable from FAIL
    forever, because the whole rule turns on `unknown -> pass` being silent."""
    comps = (read or {}).get("components") or {}
    out = {}
    for k in _definitional_keys():
        v = (comps.get(k) or {}).get("verdict")
        if v in (CQ.PASS, CQ.FAIL, CQ.UNKNOWN):
            out[k] = v
    return out


def upgrades(prev: Optional[dict], now_verdicts: dict) -> list:
    """The component keys that crossed FAIL -> PASS, in `COMPONENTS` order.

    `prev` None, or a key absent from it, is a FIRST OBSERVATION: recorded,
    never rung. Same rule `sepa/board_arrival.tracking_since` applies to a
    board's first cohort, and for the same reason — "we have only just started
    watching" must never render as "something just improved".

    UNKNOWN on either side yields nothing: `unknown -> pass` is the app
    learning and `pass -> unknown` is the app forgetting. Neither is news about
    a company.
    """
    if not prev:
        return []
    out = []
    for k in _definitional_keys():
        if prev.get(k) == CQ.FAIL and now_verdicts.get(k) == CQ.PASS:
            out.append(k)
    return out


def rows(board_doc: Optional[dict] = None) -> list:
    """The 🚀 board rows with the balance sheet and the quality read attached.

    THE ORDER IS LOAD-BEARING and is the same one `growth/api.py:_payload`
    uses: `board_metrics.attach` flattens the fields, THEN
    `capital_quality.attach` reads them. Reversed, every component answers
    UNKNOWN and this pass would go permanently silent while looking healthy.
    Pinned by `test_capital_quality_is_attached_after_board_metrics`.

    Each attach carries its own try/except for the same reason the payload
    does: a cold cache or a provider shape change must leave the read off the
    rows, never take the pass down.
    """
    if board_doc is None:
        from growth import tracker as T
        board_doc = T.board() or {}
    out = (board_doc or {}).get("rows") or []
    try:
        from sepa import board_metrics as BM
        BM.attach(out)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("quality_alerts: board_metrics attach failed: %s", exc)
    try:
        CQ.attach(out)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("quality_alerts: capital_quality attach failed: %s", exc)
    return out


def scan(board_rows: list, state: dict) -> tuple:
    """(items, counts). Pure: no I/O, no push, no state write.

    An item is one SYMBOL with at least one FAIL -> PASS crossing on a NEW
    fiscal quarter. `counts` explains every row that produced none, by name, so
    the /alerts page can say why the phone was quiet instead of showing a zero
    it did not measure.
    """
    counts = {"rows": len(board_rows or []), "graded": 0, "ungraded": 0,
              "no_capital_period": 0, "baseline": 0, "same_period": 0,
              "no_upgrade": 0, "upgraded": 0}
    items, to_record = [], []
    for row in (board_rows or []):
        if not isinstance(row, dict):
            # Counted, never skipped in silence: a row shape this pass cannot
            # read is a fact the /alerts page should be able to show.
            counts["ungraded"] += 1
            continue
        sym = str(row.get("symbol") or "").upper()
        read = row.get("capital_quality")
        if not sym or not isinstance(read, dict):
            counts["ungraded"] += 1
            continue
        counts["graded"] += 1
        verdicts = observed(read)
        # Rule #7: the quarter the BALANCE SHEET figures came from. No fallback
        # to the row's income-statement `period` — see the module docstring.
        period = read.get("period")
        prev = state.get(sym)
        if not period:
            # Recorded with period None so the verdicts are not lost. The
            # record is NOT comparable and the branch below says so: a stored
            # observation with no as-of quarter may belong to the SAME quarter
            # that later becomes readable, so it is a baseline, never a prior.
            counts["no_capital_period"] += 1
            to_record.append({"symbol": sym, "components": verdicts, "period": None})
            continue
        if not prev or not prev.get("components") or not prev.get("period"):
            # A record with no as-of quarter is a BASELINE, not a comparison.
            # This is the day-one state for every row — measured 2026-09-22,
            # 21 of 21 board rows answered `no_capital_period` and 0 of 485
            # `board_metrics` documents carried `capital_returns` — so the
            # first pass after the warm lands would otherwise read a FAIL from
            # a period-less record against a real period and ring an "upgrade"
            # that happened WITHIN one fiscal quarter, with no filing behind
            # it. `same_period` below cannot catch it: "" never equals
            # "FY2026 Q2".
            counts["baseline"] += 1
            to_record.append({"symbol": sym, "components": verdicts, "period": period})
            continue
        if str(prev.get("period") or "") == str(period):
            # Same quarter: a figure that moved did so without a filing behind
            # it. Refresh the stored verdicts, ring nothing.
            counts["same_period"] += 1
            to_record.append({"symbol": sym, "components": verdicts, "period": period})
            continue
        flips = upgrades(prev.get("components"), verdicts)
        if not flips:
            counts["no_upgrade"] += 1
            to_record.append({"symbol": sym, "components": verdicts, "period": period})
            continue
        counts["upgraded"] += 1
        items.append({"symbol": sym, "row": row, "read": read, "flips": flips,
                      "period": period, "prev_period": prev.get("period"),
                      "components": verdicts,
                      "record": {"symbol": sym, "components": verdicts, "period": period}})
    # Most crossings first, then alphabetical — a stable order, and NOT a rank:
    # nothing here is measured, so the order must not imply one name is better.
    items.sort(key=lambda i: (-len(i["flips"]), i["symbol"]))
    return items, (counts, to_record)


def _grade_txt(read: dict) -> str:
    """"3 of 4 quality checks" — `answered` beside the count, always. "all" over
    three questions and "all" over six are the same word and different facts
    (`capital_quality.grade_for`)."""
    answered = int((read or {}).get("answered") or 0)
    passed = int((read or {}).get("passed") or 0)
    return "%d of %d quality checks" % (passed, answered)


def message(item: dict) -> dict:
    """The push body. Every claim on it is read from the serving module."""
    sym = item["symbol"]
    read = item.get("read") or {}
    comps = (read.get("components") or {})
    flips = item.get("flips") or []

    parts = []
    for k in flips:
        detail = (comps.get(k) or {}).get("detail")
        parts.append("%s (%s)" % (UPGRADE_PHRASE[k], detail) if detail
                     else UPGRADE_PHRASE[k])
    # Rule #7 — the fiscal quarter, and the one it is being compared against.
    parts.append("on %s (was %s)" % (item.get("period"),
                                     item.get("prev_period") or "an earlier quarter"))
    parts.append(_grade_txt(read))
    # A name the trading engine will refuse to buy says so here rather than
    # silently — the same courtesy growth.alerts.message pays.
    for w in ((item.get("row") or {}).get("warnings") or []):
        parts.append(str(w))
    # Read from capital_quality, never retyped: if that sentence changes, this
    # changes with it.
    parts.append(CQ.MEASURED_NOTE)
    parts.append(NOT_A_RECOMMENDATION)

    head = UPGRADE_PHRASE[flips[0]] if flips else "capital quality improved"
    title = "💎 %s — %s%s" % (
        sym, head, ("" if len(flips) < 2 else " (+%d more)" % (len(flips) - 1)))
    url = "%s&symbol=%s" % (TAB_URL, sym)
    return {"title": title, "body": " · ".join(parts), "ticker": sym,
            "tickers": [sym], "url": url, "kind": KIND,
            "data": {"url": url, "board": "growth", "source": SOURCE,
                     "flips": list(flips), "period": item.get("period"),
                     "measured": CQ.MEASURED}}


def digest_message(items: list) -> dict:
    """The spill, past MAX_INDIVIDUAL — one entry per name, body order pinned so
    the ⌘-clickable chips and the text can never disagree."""
    syms = [it["symbol"] for it in items]
    body = ", ".join("%s (%s)" % (it["symbol"], UPGRADE_PHRASE[it["flips"][0]])
                     for it in items if it.get("flips"))
    return {"title": "💎 %d names improved on capital quality" % len(items),
            "body": body + " · " + CQ.MEASURED_NOTE + " · " + NOT_A_RECOMMENDATION,
            "ticker": None, "tickers": syms, "url": TAB_URL, "kind": KIND,
            "data": {"url": TAB_URL, "board": "growth", "source": SOURCE,
                     "measured": CQ.MEASURED}}


def _record(coll, doc: dict, now: datetime) -> None:
    """Remember what this pass OBSERVED for one symbol. Best-effort.

    This collection is also the only per-quarter history of these figures the
    app has — `board_metrics` keeps one document per symbol and overwrites it —
    so a future study of whether a balance-sheet upgrade predicts anything has
    to start here.
    """
    if coll is None:
        return
    try:
        coll.replace_one(
            {"_id": _state_id(doc["symbol"])},
            {"_id": _state_id(doc["symbol"]), "symbol": doc["symbol"],
             "components": dict(doc.get("components") or {}),
             "period": doc.get("period"), "at": now.isoformat(), "source": SOURCE},
            upsert=True)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("quality_alerts: state write for %s failed: %s", doc["symbol"], exc)


def _terminal(res: Optional[dict]) -> bool:
    """Delivered, or nobody targeted. A transport failure releases the claim
    (`demand_alerts._terminal`, the rule every other kind reads).

    The ONE addition, identical to `board_arrival._terminal` and for the same
    reason: a CLOSED-DAY drop (`push.sender` returning `skipped`) is NOT
    terminal. Every day-keyed kind's claim expires with its day, so keeping a
    dropped claim costs one silent day; this kind's claim is per QUARTER, so
    keeping it would mute the name for three months over a push that never left
    the building."""
    if isinstance(res, dict) and res.get("skipped"):
        return False
    return DA._terminal(res)


def run(dry_run: bool = False, *, now: Optional[datetime] = None,
        board_rows: Optional[list] = None, coll=None) -> dict:
    """One pass. At most MAX_INDIVIDUAL individual pushes plus one digest, once
    per (symbol, fiscal quarter) EVER.

    `dry_run` skips only the WRITES (claim / send / release / record): the state
    READ is unconditional, so a dry run reports a quarter already rung as seen,
    never as fresh — the house rule (`growth.alerts.run` F2b, 2026-09-14).

    A send that does not TERMINATE releases its claim AND leaves the symbol's
    stored state untouched, so the next pass re-detects the identical crossing
    and retries. Recording the new verdicts before a confirmed delivery is how a
    real upgrade gets swallowed forever.
    """
    now = now or _now()
    if board_rows is None:
        board_rows = rows()
    if coll is None:
        coll = _state_coll()                                   # dry runs READ the state too
    state = read_state(coll, [r.get("symbol") for r in board_rows
                              if isinstance(r, dict) and r.get("symbol")])
    items, (counts, to_record) = scan(board_rows, state)

    for it in items:
        it["key"] = _claim_id(it["symbol"], it["period"])

    sent, digest_sent, claimed_elsewhere, retry_pending = 0, 0, 0, 0
    singles, spill = items[:MAX_INDIVIDUAL], items[MAX_INDIVIDUAL:]
    if not dry_run:
        from push import sender
        for it in singles:
            doc = {"symbol": it["symbol"], "period": it["period"],
                   "prev_period": it.get("prev_period"), "flips": list(it["flips"]),
                   "at": now.isoformat(), "source": SOURCE}
            if not DA.claim_key(coll, it["key"], doc):
                claimed_elsewhere += 1
                _record(coll, it["record"], now)               # already rung: remember it
                continue
            try:
                res = sender.send_to_user(OWNER, message(it), kind=KIND)
            except Exception as exc:                           # noqa: BLE001
                log.warning("quality_alerts: push failed for %s: %s", it["symbol"], exc)
                DA.release_key(coll, it["key"])
                retry_pending += 1                             # state NOT recorded: retry
                continue
            if _terminal(res):
                sent += 1
                _record(coll, it["record"], now)
            else:
                DA.release_key(coll, it["key"])
                retry_pending += 1
        digest = []
        for it in spill:
            doc = {"symbol": it["symbol"], "period": it["period"],
                   "prev_period": it.get("prev_period"), "flips": list(it["flips"]),
                   "at": now.isoformat(), "source": SOURCE, "digest": True}
            if DA.claim_key(coll, it["key"], doc):
                digest.append(it)
            else:
                claimed_elsewhere += 1
                _record(coll, it["record"], now)
        if digest:
            try:
                res = sender.send_to_user(OWNER, digest_message(digest), kind=KIND)
            except Exception as exc:                           # noqa: BLE001
                log.warning("quality_alerts: digest push failed: %s", exc)
                res = DA.transport_failed(exc)                 # a raise is NOT "nobody targeted"
            if _terminal(res):
                digest_sent = len(digest)
                for it in digest:
                    _record(coll, it["record"], now)
            else:
                for it in digest:
                    DA.release_key(coll, it["key"])
                retry_pending += len(digest)
        # Every row that produced no crossing still updates its baseline.
        for doc in to_record:
            _record(coll, doc, now)
    else:
        sent, digest_sent = len(singles), len(spill)           # what a wet pass WOULD send

    # NO `skipped_room / skipped_proximity / skipped_direction / skipped_knife /
    # skipped_mood / skipped_floor` here, ever: Alerts.tsx sums those six names
    # over EVERY recorded pass, so a counter borrowing one would silently
    # pollute the S/D gate aggregate on his /alerts page. This kind has no
    # gates to skip — see the module docstring: nothing gates it, by his call.
    summary = {"kind": KIND, "ran": True,
               "date": now.astimezone(ET).date().isoformat(),
               "individual": sent, "digest": digest_sent,
               "claimed_elsewhere": claimed_elsewhere,
               "retry_pending": retry_pending,
               "measured": CQ.MEASURED, "dry_run": dry_run, **counts}
    if not dry_run:
        try:
            from supply_demand import alert_status as AS
            AS.record_result(KIND, summary, now=now)
        except Exception as exc:                               # noqa: BLE001
            log.warning("quality_alerts: status record failed: %s", exc)
    return summary


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    print(json.dumps(run(dry_run="--dry-run" in argv), default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
