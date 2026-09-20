"""📣 earnings_reaction — the push the Earnings Flow tab never sent.

Ajay 2026-09-20: *"Also don't forget to alert me on earnings surprises I think
stock witz also has it. I wanna make sure we are catching those in alerts as
well."* One message earlier: *"We already have an earning calendar tracker"*.

And, the same day, about this kind and the three others shipped beside it:
*"Default on for any change of todays features Bondes or Potus or explosive
growth or Earnings I wanna see all of them."* So this kind ships **ON**: it is
registered in `push/subs.OWNER_KEEP_SET` and `default_prefs()` carries True.

NO NEW TRACKER. This module is a pure consumer of `chart_maps.earnings.scan()`
— the tab he already has — plus one read-only surprise read per reacted name.
The gate is the tab's own REACTED half (institutional buying on the reaction
bar: >= MIN_VOL_RATIO x the 60-day MEDIAN volume, close in the top
(1 - MIN_CLOSE_LOC) of the bar's range, >= MIN_DOLLAR_VOL traded, up on the
day) AND this quarter's EPS surprise above zero. Every number in the body is
read from the constant that enforces it; nothing here is retyped.

THE TWO CALENDAR TRAPS THAT SET THE CRON SLOTS
----------------------------------------------
WRONG QUARTER. On the reaction day, before the 17:45 `sepa.earnings_watch`
refresh, the reporter's calendar doc still has `next_date = report_date` and
`last_report` = the PRIOR quarter. The tab shows that stale figure; this pass
must not. Hence the date/reaction match below, and a read-only fresh fetch.

THE ROLL. At 17:45 the doc rolls (`next_date` -> next quarter, `last_report` ->
this report) and `chart_maps.earnings.phase_for` then reads an AMC reporter as
UPCOMING, so `scan()` drops it. The evening pass therefore runs BEFORE 17:45.

SLOTS_ET = ("08:25", "17:35"), both outside RTH and both before the roll:
  17:35  after the 16:30 broad fast-scan patched today's CLOSED bar — catches
         names that reported AFTER yesterday's close (reaction bar = today).
  08:25  before any bar for today exists — catches names that reported BEFORE
         yesterday's open, whose surprise yfinance publishes only once the
         report date is in the past (earnings_watch.py: `past` needs
         `ts.date() < today`), so the evening pass cannot see it.

WHAT THE 2026-09-20 CRITIQUE CHANGED (each finding, and the answer)
-------------------------------------------------------------------
F1/F7  The doc's `when` is None for most near reporters (1,646 of 2,071 docs
       after Friday's refresh), so anchoring on it would score an AMC
       reporter's PRE-report bar and then burn the dedupe key the real
       reaction needed. And an estimated report date drifts by a day, which
       would make a plain `last_report.date == report_date` match never come
       true. So the match is on the REACTION DATE: the fresh fetch's own
       `date`/`when` are re-anchored through `earnings_picks.reaction_read`
       and the resulting bar must be the bar `scan()` scored. `when` None on
       the fresh fetch is `timing_unknown` — no claim, no push.
F2     `chart_maps.earnings.LOOKBACK_DAYS` counts SESSIONS now, so Friday
       reporters reach `scan()` on Monday at all.
F3     A failed fetch is not "pending": `this_quarter_report` returns a status
       and `fetch_failed` is counted separately, with one retry; when half the
       reacted names fail, the pass says so on /alerts instead of reading as a
       quiet tape.
F5     `run()` refuses when the price cache's last bar is not the session this
       slot expects — a pre-market Scan click patches today's date into the
       cache and would otherwise drop every BMO reporter with no counter.
F9     The title carries the reaction date in BOTH slots, so the 08:25 push
       can never read as today's move.

NOT MEASURED. The institutional read is an owner setting calibrated on two
names on the 2026-08-19 tape (TGT, BULL) — there is no forward measurement and
no CI, and the body says so. Related nulls: the entry-trigger study
(2026-09-15, confirmation entries are cushion, not edge) and the 8-K event
study (2026-09-01, no chase edge after a day-0 pop). The replay that ships
beside this module is a phone-load COUNT, not an edge claim.

SOURCES: yfinance (calendar + surprise) and Massive (bars). StockTwits has no
earnings or surprise feed — checked 2026-09-20, the connector exposes
sentiment, message volume and trending only.

Event notice, decision support. Not a buy signal, not advice.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from chart_maps import earnings as E
from growth.alerts import OWNER, MAX_INDIVIDUAL, _bands_for
from sepa import earnings_watch as EW
from supply_demand import alert_gates as AG
from supply_demand import alert_status as AS
from supply_demand import demand_alerts as DA
from supply_demand import enterable as EN

log = logging.getLogger("chart_maps.earnings_alerts")

ET = ZoneInfo("America/New_York")
KIND = "earnings_reaction"
STATE_COLL = "earnings_reaction_state"
SOURCE = "earnings_alerts"

# The two crontab minutes. `alert_status` and the /alerts page quote these;
# the crontab is the enforcing copy and MAIN writes it.
SLOTS_ET = ("08:25", "17:35")

# How far a CONFIRMED report date may sit from the calendar's estimate before
# the two are not the same event. yfinance moves a confirmed date by a day
# often enough that an exact match never comes true (critique F7); three days
# is wide enough for that drift and far narrower than a quarter.
REPORT_DATE_TOL_DAYS = 3

# One retry on a failed yfinance read, and the pause before it. The Friday
# 17:45 pool run came back with the `Ticker.calendar` fallback for 1,636 of
# 2,071 names while single calls succeeded in 2.5s.
FETCH_RETRIES = 1
FETCH_RETRY_SLEEP_SEC = 1.0


def _now() -> datetime:
    return datetime.now(ET)


def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _db():
    try:
        from portfolio.store import _get_db
        return _get_db()
    except Exception as exc:                                   # noqa: BLE001
        log.warning("earnings_alerts: no mongo: %s", exc)
        return None


def _state_coll():
    db = _db()
    return db[STATE_COLL] if db is not None else None


def _state_key(symbol: str, report_date: str) -> str:
    """One claim per (name, report). A new quarter is a new key; a second pass
    the same evening finds the key and sends nothing."""
    return "%s|%s" % (str(symbol or "").upper(), str(report_date or "")[:10])


def _seen(coll, keys: list) -> set:
    """The subset of `keys` already claimed — one `$in` read. A read failure is
    the empty set (push again rather than never)."""
    if coll is None or not keys:
        return set()
    try:
        return {str(d["_id"]) for d in coll.find({"_id": {"$in": sorted(set(keys))}}, {"_id": 1})}
    except Exception as exc:                                   # noqa: BLE001
        log.warning("earnings_alerts: dedupe read failed: %s", exc)
        return set()


def _days_apart(a: str, b: str) -> Optional[int]:
    from datetime import date
    try:
        ya, ma, da = (int(x) for x in str(a)[:10].split("-"))
        yb, mb, db = (int(x) for x in str(b)[:10].split("-"))
        return abs((date(ya, ma, da) - date(yb, mb, db)).days)
    except Exception:
        return None


def this_quarter_report(row: dict, doc_last_report: Optional[dict],
                        fetch=None) -> tuple:
    """(last_report, status) for THIS report. IMPURE by default (one yfinance
    read), and READ-ONLY: nothing here writes the calendar, because a write
    would roll `next_date` and delete the name from the tab's REACTED half the
    same hour.

    status is "doc" when the stored doc already describes this report,
    "fetched" when a fresh read answered, and "fetch_failed" when the read
    returned nothing or the `Ticker.calendar` fallback shape (no last_report
    AND no when) after the retry. "fetch_failed" is NOT "pending": the first
    is a provider outage the page must name, the second is a number the
    provider has not published yet (critique F3).
    """
    rpt = str((row or {}).get("report_date") or "")[:10]
    lr = doc_last_report if isinstance(doc_last_report, dict) else None
    if lr and str(lr.get("date") or "")[:10] == rpt and rpt:
        return lr, "doc"
    fn = fetch or EW._fetch_next
    sym = str((row or {}).get("symbol") or "").upper()
    res = None
    for attempt in range(FETCH_RETRIES + 1):
        try:
            res = fn(sym)
        except Exception as exc:                               # noqa: BLE001
            log.debug("earnings_alerts: fetch failed %s: %s", sym, exc)
            res = None
        if isinstance(res, dict) and not (res.get("last_report") is None
                                          and res.get("when") is None):
            return res.get("last_report"), "fetched"
        if attempt < FETCH_RETRIES:
            time.sleep(FETCH_RETRY_SLEEP_SEC)
    return None, "fetch_failed"


def surprise_for(row: dict, last_report: Optional[dict], m: Optional[dict],
                 frame=None) -> tuple:
    """(surprise_pct, status) for one REACTED row. PURE given `frame`.

    status:
      "ok"              a this-report beat, scored on the right bar
      "pending"         no this-report figure yet, or the bar `scan()` scored
                        is not the bar this report reacted on
      "timing_unknown"  the fresh read has no BMO/AMC stamp, so the reaction
                        bar cannot be anchored — never guessed (critique F1)
      "no_surprise"     a this-report row with a null / NaN surprise
      "not_a_beat"      a miss or an in-line print (<= 0)

    The unit is PERCENT exactly as `earnings_watch` stores it: 6.16 means
    +6.16%. Nothing here rescales: the only other surprise reader in the tree
    served a FRACTION until 2026-09-20, and this module never reads it.

    THE REACTION-DATE MATCH. A confirmed date may sit up to
    REPORT_DATE_TOL_DAYS from the calendar's estimate, so the dates are not
    compared for equality; instead the fresh report's own date and timing are
    re-anchored through the shared `earnings_picks.reaction_read` and the bar
    that comes back must be the bar `scan()` scored. That one rule refuses an
    AMC reporter's pre-report bar, a BMO reporter's next-day bar, and a prior
    quarter's row, without inventing a rule for each.
    """
    rpt = str((row or {}).get("report_date") or "")[:10]
    lr = last_report if isinstance(last_report, dict) else None
    if not lr:
        return None, "pending"
    ldate = str(lr.get("date") or "")[:10]
    if not ldate or not rpt:
        return None, "pending"
    apart = _days_apart(ldate, rpt)
    if apart is None or apart > REPORT_DATE_TOL_DAYS:
        return None, "pending"                    # a different quarter
    when = lr.get("when")
    if not when:
        return None, "timing_unknown"
    bar_date = str((m or {}).get("date") or "")[:10]
    if not bar_date:
        return None, "pending"
    from sepa import earnings_picks as EP
    rr = EP.reaction_read(frame, ldate, when) if frame is not None else None
    if not rr or str(rr.get("reaction_date") or "")[:10] != bar_date:
        return None, "pending"
    s = _f(lr.get("surprise_pct"))
    if s is None:
        return None, "no_surprise"
    if s <= 0:
        return s, "not_a_beat"
    return s, "ok"


def context_for(symbol: str, m: dict, *, bands=None, day=None) -> dict:
    """Room / demand band / 🎯 on the REACTION bar — recorded, NEVER binding.

    This is an event notice, not a demand entry: `feedback_alert_gate_room_
    proximity` binds the S/D zone pushes, and widening it to this kind would
    be a gate change nobody asked for. The read rides the body so he can see
    where the print sits, and `would_skip_room` counts how often the standing
    5% room gate WOULD have refused it (§7.4b — his call, not this module's).
    """
    out = {"room": None, "room_ok": None, "hit": None, "band": None, "enterable": None}
    px = _f((m or {}).get("close"))
    if px is None or px <= 0:
        return out
    bands = _bands_for(symbol) if bands is None else bands
    bands = bands or []
    ok_room, room = AG.room_gate(px, bands)
    out["room"], out["room_ok"] = room, bool(ok_room)
    demand = [b for b in bands
              if str(b.get("kind") or "demand").lower() == "demand"
              and _f(b.get("lo")) and _f(b.get("hi"))]
    hits = []
    for b in demand:
        h = DA.read(px, b, (m or {}).get("change_pct"), prev_close=None)
        if h:
            hits.append((0 if h.get("state") == "in" else 1,
                         float(h.get("dist_pct") or 0.0), b, h))
    if not hits:
        return out
    hits.sort(key=lambda t: (t[0], t[1]))
    _, _, band, hit = hits[0]
    out["band"], out["hit"] = band, hit
    day_low = _f((m or {}).get("low"))
    prev_close = _f((m or {}).get("prev_close"))
    sw = AG.sweep_read(band, symbol, frame=AG.daily_frame(symbol), day_low=day_low,
                       last=px, day=day or (m or {}).get("date"))
    out["enterable"] = EN.assess(kind=EN.KIND_DEMAND, px=px, band=band, bands=bands,
                                 prev_close=prev_close, day_low=day_low,
                                 change_pct=(m or {}).get("change_pct"),
                                 floor_state=(sw or {}).get("state"),
                                 room_ok=bool(ok_room),
                                 prox_ok=AG.demand_proximity_gate(px, band),
                                 room=room)
    return out


def _band_txt(ctx: dict) -> str:
    band, hit = (ctx or {}).get("band"), (ctx or {}).get("hit")
    if not band:
        if (ctx or {}).get("room") is None and (ctx or {}).get("room_ok") is None:
            return "zone read unavailable"
        return "no demand band under the print"
    lo, hi = float(band.get("lo") or 0), float(band.get("hi") or 0)
    if isinstance(hit, dict) and hit.get("state") == "above":
        return "%g%% above demand $%g–%g" % (float(hit.get("dist_pct") or 0.0), lo, hi)
    return "in demand $%g–%g" % (lo, hi)


def message(row: dict, last_report: dict, ctx: dict, surprise_pct: float) -> dict:
    """The push body. Every threshold is printed from the constant that
    enforces it, so a change to `chart_maps.earnings` moves the words too."""
    sym = str(row["symbol"]).upper()
    m = row
    chg = _f(m.get("change_pct")) or 0.0
    vr = _f(m.get("vol_ratio")) or 0.0
    loc = _f(m.get("close_loc"))
    dv = _f(m.get("dollar_vol")) or 0.0
    top_pct = round((1 - E.MIN_CLOSE_LOC) * 100)

    ea = _f((last_report or {}).get("eps_actual"))
    ee = _f((last_report or {}).get("eps_estimate"))
    parts = []
    if ea is not None and ee is not None:
        parts.append("EPS %g vs %g est" % (ea, ee))
    else:
        parts.append("EPS beat %+.1f%%" % surprise_pct)
    parts.append("reported %s %s" % (str((last_report or {}).get("date") or "")[:10],
                                     (last_report or {}).get("when") or "timing unconfirmed"))
    parts.append("reaction %+.1f%% on %.1f× median volume, $%dM traded, closed in the "
                 "top %d%% of the range (loc %.2f)"
                 % (chg, vr, round(dv / 1e6), top_pct, loc if loc is not None else 0.0))
    gap = _f(m.get("gap_pct"))
    if gap is not None:
        parts.append("gap %+.1f%%" % gap)
    room_s = AG.room_txt((ctx or {}).get("room"))
    if room_s:
        parts.append(room_s)
    parts.append(_band_txt(ctx))
    en = (ctx or {}).get("enterable")
    if isinstance(en, dict) and en.get("verdict"):
        parts.append("🎯 %s" % en["verdict"])
    parts.append("institutional-buy read = owner setting (%.1f× median vol · close in top "
                 "%d%% · ≥ $%dM), NOT measured · event notice, not a recommendation"
                 % (E.MIN_VOL_RATIO, top_pct, round(E.MIN_DOLLAR_VOL / 1e6)))

    title = ("📣 %s beat by %+.1f%% — reacted UP %+.1f%% on %.1f× volume (%s)"
             % (sym, surprise_pct, chg, vr, str(m.get("date") or "")[:10]))
    return {"title": title, "body": " · ".join(parts), "ticker": sym,
            "url": "/chart-maps?tab=earnings&symbol=%s" % sym, "kind": KIND,
            "enterable": EN.slim((ctx or {}).get("enterable"))}


def digest_message(items: list) -> dict:
    """The spill. `tickers` rides the payload in the order the body lists them
    (Ajay 2026-09-20: "I need the stock tickers to be clickables in alerts
    individually if there are multiple in one alert by command click")."""
    syms = [str(i["row"]["symbol"]).upper() for i in items]
    body = " · ".join("%s %+.1f%% beat / %+.1f%%"
                      % (str(i["row"]["symbol"]).upper(), float(i["surprise_pct"]),
                         _f(i["row"].get("change_pct")) or 0.0)
                      for i in items)
    return {"title": "📣 %d earnings beats with institutional buying" % len(items),
            "body": body, "url": "/chart-maps?tab=earnings", "kind": KIND,
            "ticker": None, "tickers": syms}


def _frame_for(symbol: str):
    try:
        from sepa import prices
        return prices.load_prices(symbol)
    except Exception as exc:                                   # noqa: BLE001
        log.debug("earnings_alerts: frame load failed %s: %s", symbol, exc)
        return None


def _doc_reports(day: str) -> dict:
    """{SYMBOL: last_report} from the SAME calendar collection `E.scan` read.

    COST, not correctness. `this_quarter_report` takes the stored doc first
    and only falls through to a fresh yfinance read when the doc does not
    already describe THIS report — but `run()` had no way to hand it those
    docs, so the "doc" branch was dead in cron and every REACTED name paid a
    network read, plus `FETCH_RETRY_SLEEP_SEC` again whenever the provider was
    down. One Mongo read per pass replaces N network reads.

    Read-only and failure-tolerant on purpose: any error returns {} and the
    pass behaves exactly as it did before this function existed. It must never
    become the only source of a last_report — a doc whose `last_report.date`
    does not match the report being scored is ignored downstream, which is
    what keeps a stale calendar row from being scored as this quarter.
    """
    try:
        cal = E._calendar_rows(str(day)[:10])
    except Exception as exc:                                   # noqa: BLE001
        log.warning("earnings_alerts: calendar read failed: %s", exc)
        return {}
    out = {}
    for sym, doc in (cal or {}).items():
        lr = (doc or {}).get("last_report")
        if isinstance(lr, dict):
            out[str(sym).upper()] = lr
    return out


def _scan(now: datetime, *, scan_result: Optional[dict] = None,
          doc_reports: Optional[dict] = None, fetch=None, frames: Optional[dict] = None,
          bands: Optional[dict] = None) -> tuple:
    """(items, counts). No push, no state write. UPCOMING rows are never
    iterated — `upcoming_ignored` is the proof."""
    d = now.astimezone(ET).date().isoformat()
    res = scan_result if scan_result is not None else E.scan(today=d)
    rows = list(res.get("reacted") or [])
    counts = {
        "calendar_names": int(res.get("calendar_names") or 0),
        "reacted": len(rows),
        "reacted_seen": int(res.get("reacted_seen") or 0),
        "reacted_not_institutional": int(res.get("reacted_not_institutional") or 0),
        "dropped_not_last_bar": int(res.get("dropped_not_last_bar") or 0),
        "upcoming_ignored": len(res.get("upcoming") or []),
        "calendar_when_none": 0,
        "fetch_failed": 0,
        "skipped_timing_unknown": 0,
        "skipped_surprise_pending": 0,
        "skipped_no_surprise": 0,
        "skipped_not_a_beat": 0,
        "context_unavailable": 0,
        "would_skip_room": 0,
        "doc_hits": 0,
        "candidates": 0,
    }
    # Un-injected (this is the cron path): read the calendar docs ONCE so the
    # "doc" branch of `this_quarter_report` is live. An injected {} keeps the
    # old fetch-everything behaviour, which is what the fetch tests pin.
    if doc_reports is None and rows:
        doc_reports = _doc_reports(d)
    out = []
    for row in rows:
        sym = str(row.get("symbol") or "").upper()
        if not sym:
            continue
        if not row.get("when"):
            counts["calendar_when_none"] += 1          # doc side, diagnostic only
        doc_lr = (doc_reports or {}).get(sym)
        lr, fstat = this_quarter_report(row, doc_lr, fetch)
        if fstat == "doc":
            counts["doc_hits"] += 1        # a name that cost no network read
        if fstat == "fetch_failed":
            counts["fetch_failed"] += 1
            continue
        frame = frames.get(sym) if frames is not None else _frame_for(sym)
        s, status = surprise_for(row, lr, row, frame=frame)
        if status == "timing_unknown":
            counts["skipped_timing_unknown"] += 1
            continue
        if status == "pending":
            counts["skipped_surprise_pending"] += 1
            continue
        if status == "no_surprise":
            counts["skipped_no_surprise"] += 1
            continue
        if status == "not_a_beat":
            counts["skipped_not_a_beat"] += 1
            continue
        try:
            ctx = context_for(sym, row,
                              bands=(bands.get(sym, []) if bands is not None else None),
                              day=row.get("date"))
        except Exception as exc:                               # noqa: BLE001
            log.warning("earnings_alerts: context failed for %s: %s", sym, exc)
            counts["context_unavailable"] += 1
            ctx = {"room": None, "room_ok": None, "hit": None, "band": None, "enterable": None}
        if ctx.get("room_ok") is False:
            counts["would_skip_room"] += 1             # counted, never enforced
        out.append({"row": row, "last_report": lr, "surprise_pct": s, "ctx": ctx,
                    "key": _state_key(sym, row.get("report_date"))})
    counts["candidates"] = len(out)
    return out, counts


def candidates(now: Optional[datetime] = None, **inj) -> list:
    """What a wet pass would push, in `scan()`'s dollar-volume order. No push,
    no state write. This is what the tests call."""
    return _scan(now or _now(), **inj)[0]


def _slot(now: datetime) -> str:
    return "morning" if now.astimezone(ET).time().hour < 12 else "evening"


def expected_last_bar(now: datetime) -> str:
    """The session the price cache's last bar must be for this slot.

    Evening (17:35): today — the 16:30 broad fast-scan patched today's CLOSED
    bar. Morning (08:25): the previous trading day — no bar for today exists
    yet. A mismatch means the cache is stale, or a pre-market Scan click
    patched today's date in (prices.py documents pre-market snapshots dated
    today), and either way every reaction bar would silently look like an old
    bar (critique F5).
    """
    d = now.astimezone(ET).date().isoformat()
    return d if _slot(now) == "evening" else E._trading_days_back(d, 1)


def _last_cached_bar() -> Optional[str]:
    df = _frame_for("SPY")
    try:
        return str(df.index[-1])[:10] if df is not None and len(df) else None
    except Exception:                                          # pragma: no cover
        return None


def _terminal(res: Optional[dict]) -> bool:
    return DA._terminal(res)


def run(dry_run: bool = False, *, force: bool = False, now: Optional[datetime] = None,
        coll=None, last_bar: Optional[str] = None, **inj) -> dict:
    """One pass. Claim-then-send, once per (symbol, report_date), at most
    MAX_INDIVIDUAL individual pushes plus one digest.

    `dry_run` skips only the WRITES (claim / send / release / record): the
    dedupe READ is unconditional, so a key already rung tonight reports as
    seen, never as fresh. `force` skips the session and freshness guards — for
    in-container smoke runs only; it is the flag the Monday dry run uses.
    """
    now = now or _now()
    if not force and DA.in_session(now):
        return {"kind": KIND, "ran": False, "dry_run": dry_run,
                "reason": "in session — the price cache's last bar is a partial bar "
                          "(vcp-watch patches it hourly); run before 09:30 or after 16:35 ET"}
    expected = expected_last_bar(now)
    if not force:
        seen_bar = last_bar if last_bar is not None else _last_cached_bar()
        if seen_bar != expected:
            out = {"kind": KIND, "ran": False, "dry_run": dry_run,
                   "reason": "price cache last bar %s, expected %s — pass skipped"
                             % (seen_bar, expected)}
            if not dry_run:
                AS.record_result(KIND, out, now=now)
            return out

    day = now.astimezone(ET).date().isoformat()
    items, counts = _scan(now, **inj)
    if coll is None:
        coll = _state_coll()                                   # dry runs READ the state too
    seen = _seen(coll, [it["key"] for it in items])
    fresh = [it for it in items if it["key"] not in seen]

    sent, digest_sent, claimed_elsewhere = 0, 0, 0
    singles, spill = fresh[:MAX_INDIVIDUAL], fresh[MAX_INDIVIDUAL:]
    if not dry_run:
        from push import sender
        for it in singles:
            doc = {"symbol": it["row"]["symbol"], "report_date": it["row"].get("report_date"),
                   "reaction_date": it["row"].get("date"), "surprise_pct": it["surprise_pct"],
                   "at": now.isoformat(), "source": SOURCE}
            if not DA.claim_key(coll, it["key"], doc):
                claimed_elsewhere += 1
                continue
            try:
                res = sender.send_to_user(
                    OWNER, message(it["row"], it["last_report"], it["ctx"], it["surprise_pct"]),
                    kind=KIND)
            except Exception as exc:                           # noqa: BLE001
                log.warning("earnings_alerts: push failed for %s: %s", it["row"]["symbol"], exc)
                DA.release_key(coll, it["key"])
                continue
            if _terminal(res):
                sent += 1
            else:
                DA.release_key(coll, it["key"])
        digest = []
        for it in spill:
            doc = {"symbol": it["row"]["symbol"], "report_date": it["row"].get("report_date"),
                   "reaction_date": it["row"].get("date"), "surprise_pct": it["surprise_pct"],
                   "at": now.isoformat(), "source": SOURCE, "digest": True}
            if DA.claim_key(coll, it["key"], doc):
                digest.append(it)
            else:
                claimed_elsewhere += 1
        if digest:
            try:
                res = sender.send_to_user(OWNER, digest_message(digest), kind=KIND)
            except Exception as exc:                           # noqa: BLE001
                log.warning("earnings_alerts: digest push failed: %s", exc)
                res = DA.transport_failed(exc)
            if _terminal(res):
                digest_sent = len(digest)
            else:
                for it in digest:
                    DA.release_key(coll, it["key"])
    else:
        sent, digest_sent = len(singles), len(spill)           # what a wet pass WOULD send

    summary = {"kind": KIND, "ran": True, "date": day, "slot": _slot(now),
               "candidates": len(items), "fresh": len(fresh), "individual": sent,
               "digest": digest_sent, "claimed_elsewhere": claimed_elsewhere,
               "dry_run": dry_run, **counts}
    # The provider went dark on half the reacted names: say so on /alerts
    # rather than let the page read this pass as a quiet tape (critique F3).
    reacted = int(counts.get("reacted") or 0)
    failed = int(counts.get("fetch_failed") or 0)
    if reacted and failed >= max(1, reacted // 2):
        summary["reason"] = ("yfinance fallback on %d of %d REACTED names — surprises unread"
                             % (failed, reacted))
    if not dry_run:
        AS.record_result(KIND, summary, now=now)
    return summary


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description="📣 earnings reaction push (one pass)")
    p.add_argument("--dry-run", action="store_true", help="read state, send nothing")
    p.add_argument("--force", action="store_true",
                   help="skip the session and price-cache guards (smoke runs only)")
    a = p.parse_args(argv)
    print(json.dumps(run(dry_run=a.dry_run, force=a.force), default=str))
    return 0


if __name__ == "__main__":                                     # pragma: no cover
    raise SystemExit(main())
