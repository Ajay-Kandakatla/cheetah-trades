"""supply_demand/alert_status — what each Supply & Demand push pass did last,
so the /alerts page can say WHY the phone was quiet.

Ajay 2026-09-05 (verbatim): "Do we have the same logic in back end demand for
the ones that I get alerts. Would it be the same list of stocks.. Also can I go
to a dedicated page to see the list of alerts? May be add it to recent alerts
or something?"

The honest answer to the first question is NO: the Demand board is a
closed-bar scan over the full universe with an R:R floor; the phone gets a live,
cap-floored (demand_alerts.MIN_CAP_USD, $700M since 2026-09-10), gated subset (alert_gates: >= 5% room to the first band overhead, print
<= 1% above the demand band). A quiet phone is therefore normal, and a page
that only lists what pushed cannot tell "nothing qualified" from "the pass
never ran". This module keeps the last pass's counters per kind:

  zone_edge          read from the existing ``zone_edge_latest`` doc (_id
                     'latest'), whose counts now carry skipped_room /
                     skipped_cap / unknown_cap / pushed (zone_edge.check_once).
  zone_bounce_alert  written here by zone_bounce_alerts.check_once
  demand_alert       written here by demand_alerts.check_once
  key_level_alert    written here by key_level_alerts.run_pass (2026-09-25),
                     the 🔑 hook on the zone_edge minute
  med_catalyst       written here by catalysts.medical.routine (2026-09-29),
                     the 🧬 hook on the promo_live 5-minute line
  gajjala_setup      written here by chart_maps.gajjala.run (2026-10-13), the
                     🚩 5-minute pass on its own crontab line (SHADOW first);
                     its served pass also carries `shadow_items`, today's
                     shadow A+ rows read from `gajjala_alerts` (2026-10-13 E3)
  gajjala_potential  written here by chart_maps.gajjala.run (2026-10-15), the
                     🧠 LIVE kind riding the same 5-minute pass (no crontab line
                     of its own); its served pass also carries
                     `potential_items`, today's tracker docs read from
                     `gajjala_potentials` (read_gajjala_potentials)
  tape_burst_highbeta / tape_burst_chartmaps
                     written here by orderflow.tape_burst_kinds.run_all
                     (2026-10-14), the 🎢 / 🗺️ kinds riding the
                     `sepa.cli trade-flash-watch` line; each served pass also
                     carries `window` {open, close} (HH:MM ET, built from
                     trade_flash.WATCH_OPEN_ET / WATCH_CLOSE_ET)
  tape_control       written here by orderflow.tape_control.run_pass
                     (2026-10-16), the 🎚️ LIVE kind riding the same
                     `sepa.cli trade-flash-watch` line; its served pass also
                     carries `window`, `pins` and `note` (read_tape_control →
                     tape_control.status_block — the words are the module's)

``alert_pass_latest`` collection: {_id: kind, as_of: ET iso, date: YYYY-MM-DD,
counts: {...ints}, reason?: str}. One doc per kind, replaced every pass.
``record_pass`` is best-effort and never raises — it sits after the sends in a
cron pass, and delivery is what matters. A missing doc reads as as_of null and
counts {} (the page shows "no pass recorded", never zeros it did not measure).

GET /alerts/status (supply_demand/api.py) -> ``status_payload``:
  {in_session, now_et, gate: {min_room_pct, max_above_demand_pct, min_cap_usd,
   min_cap_txt}, passes: {zone_edge, zone_bounce_alert, demand_alert,
   earnings_reaction, board_arrival:bonde, board_arrival:growth,
   capital_quality_upgrade}, disclaimer}
  each RTH pass: {as_of, date, counts, cadence_sec[, reason]}
  each DAILY pass (the three added 2026-09-20): {as_of, date, counts,
  cadence_sec: None, schedule[, reason]} — `schedule` is the slot string built
  from the owning module's SLOTS_ET, so the page types no minute of its own.
Times are ET ISO strings; ``in_session`` is zone_edge's clock (04:00-20:00 ET pass window since 2026-09-08, pushes RTH 9:31-16:00
on NYSE trading days), evaluated at request time. ``in_session`` is the CLOCK,
not proof the crons are alive — the page compares each ``as_of`` with
``now_et`` against ``cadence_sec`` and says "stale" when a pass is overdue.

S/D scope: configured house heuristic, not a book method, no cites. Decision
support, not a buy signal, not advice.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from . import alert_gates as AG

log = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
PASS_COLL = "alert_pass_latest"
ZONE_EDGE_KIND = "zone_edge"
# The passes that run ONCE (or twice) a trading day rather than on an RTH
# cadence: 📣 earnings_reaction and the two ✨ board_arrival boards, all
# registered 2026-09-20. They carry `cadence_sec: None` — a daily pass is not
# stale five minutes after its slot — and a `schedule` string instead, so the
# page can print WHEN it runs without typing a minute of its own.
# 💎 capital_quality_upgrade (growth/quality_alerts.py, 2026-09-22) joined
# them: it runs once, after the evening metrics warm. It is the one daily pass
# whose kind ships OFF — the page must still carry it, because "why was my phone
# quiet" is exactly the question a pass he has just switched on will raise.
# 🌙 overnight_movers (overnight/push.py, 2026-10-19) joined them: one pass at
# overnight.push.SLOT_ET on the trade date. Its kind ships OFF (HIS CALL #1) —
# carried anyway, for the capital_quality reason. Typed, not imported: this file
# stays a module-level leaf (test_overnight_movers_kind pins it equal to
# overnight.push.KIND).
OVERNIGHT_KIND = "overnight_movers"
DAILY_PASS_KINDS = ("earnings_reaction", "board_arrival:bonde", "board_arrival:growth",
                    "capital_quality_upgrade", OVERNIGHT_KIND)
# 🔑 key_level_alert (supply_demand/key_level_alerts.py, 2026-09-25) rides the
# zone_edge minute — no crontab line of its own — and records its own pass doc.
# Its kind ships OFF; the page still carries it for the capital_quality reason.
KEY_LEVEL_KIND = "key_level_alert"
# 🧬 med_catalyst (catalysts/medical/routine.py, 2026-09-29) rides promo_live's
# `*/5 4-19 * * 1-5` crontab line — no line of its own — and records its own
# pass doc. Its kind ships ON for the owner only (OWNER_KEEP_SET). The module
# is NOT imported here: this file stays a module-level leaf.
MED_KIND = "med_catalyst"
# 🚩 gajjala_setup (chart_maps/gajjala/run.py, 2026-10-13) has its OWN crontab
# line (`1-56/5 4-20 * * 1-5 … chart_maps.gajjala.run`) and records its own
# pass doc. It ships in SHADOW: the counts carry `shadow_mode` / `shadow` /
# `shadow_session` (the medical keys) so the page says "shadow — not sent".
GAJJALA_KIND = "gajjala_setup"
# 🎢 / 🗺️ the two tape-burst kinds (orderflow/tape_burst_kinds.py, 2026-10-14)
# ride `sepa.cli trade-flash-watch` (`2-57/5 9-15 * * 1-5`) — no line of their
# own — and record their own pass docs. Typed, not imported: this file stays a
# module-level leaf (test_tape_burst_kinds pins them equal to
# tape_burst_kinds.KINDS).
TAPE_KINDS = ("tape_burst_highbeta", "tape_burst_chartmaps")
# 🧠 gajjala_potential (chart_maps/gajjala/potential.py, 2026-10-15). Ajay: "Give
# me an alert all continous tracker on these specifically when I get alert I
# will jump on to ride the wave" — a NEW kind, LIVE, owner-only (DECISIONS4). It
# rides the 🚩 pass (`chart_maps.gajjala.run`, no crontab line of its own — the
# key_level precedent) and records its own pass doc. Typed, not imported: this
# file stays a module-level leaf (test_gajjala_potential_kind pins it equal to
# constants.POTENTIAL_PUSH_KIND).
GAJJALA_POTENTIAL_KIND = "gajjala_potential"
# 🎚️ tape_control (orderflow/tape_control.py, 2026-10-16). Ajay: "I wwant you to
# alert me when the Buyers are winning in tape for IREN today." It rides
# `sepa.cli trade-flash-watch` (no crontab line of its own) and records its own
# pass doc. Typed, not imported: this file stays a module-level leaf
# (test_tape_control_registry pins it equal to tape_control.KIND).
TAPE_CONTROL_KIND = "tape_control"
PASS_KINDS = (ZONE_EDGE_KIND, "zone_bounce_alert", "demand_alert", KEY_LEVEL_KIND, MED_KIND,
              GAJJALA_KIND, GAJJALA_POTENTIAL_KIND) + TAPE_KINDS + (TAPE_CONTROL_KIND,) + DAILY_PASS_KINDS

# How often each cron is scheduled to run in RTH (backend/crontab: zone_edge
# `* 9-16 * * 1-5`, demand_alerts `3-58/5`, zone_bounce_alerts `4-59/5`).
# Reported per pass as `cadence_sec` so the page can call a same-day stamp
# STALE against the real schedule instead of a hard-coded "every minute"
# (review 2026-09-05: a cron dead since 10:02 read as "passes running" at
# 14:30 because the header was inferred from the clock alone). Change the
# crontab -> change this; the source guard in test_alert_status pins both.
CADENCE_SEC = {ZONE_EDGE_KIND: 60, "zone_bounce_alert": 300, "demand_alert": 300}
# DERIVED, never typed: the key-level pass is called by zone_edge's own cron
# line (zone_edge.check_once → key_level_alerts.run_pass), so its cadence IS
# zone_edge's.
CADENCE_SEC[KEY_LEVEL_KIND] = CADENCE_SEC[ZONE_EDGE_KIND]
# The 🧬 hook runs inside `python -m catalysts.promo_live` (backend/crontab:459,
# `*/5 4-19 * * 1-5`), so its cadence IS that line's: 300 s. The source guard in
# test_alert_status derives it from the crontab's minute field.
CADENCE_SEC[MED_KIND] = 300
# 🚩 its own line, minute field `1-56/5` → 300 s (pinned to the crontab by
# test_alert_status, like the zone passes).
CADENCE_SEC[GAJJALA_KIND] = 300
# 🧠 rides that same `1-56/5` line (run.run_pass calls potential.run_pass) →
# 300 s (the crontab source guard derives it from that line's minute field).
CADENCE_SEC[GAJJALA_POTENTIAL_KIND] = 300
# 🎢 / 🗺️ ride the trade-flash-watch line `2-57/5` → 300 s (the crontab source
# guard derives it from that line's minute field).
CADENCE_SEC.update({k: 300 for k in TAPE_KINDS})
# 🎚️ rides that same `2-57/5` line → 300 s (the crontab source guard derives it
# from that line's minute field).
CADENCE_SEC[TAPE_CONTROL_KIND] = 300

# The cap floor is READ from demand_alerts.MIN_CAP_USD at request time, never
# retyped (review 2026-09-14, finding 6: this said "$1B+" for four days after
# Ajay moved the floor to $700M on 2026-09-10). demand_alerts imports this
# module at module level, so the import is lazy — see `disclaimer()`.
DISCLAIMER_TEMPLATE = ("Phone pushes are a gated, live, {cap}+ subset of the boards (alert_gates: >= 5% "
                       "room to the first band overhead, print <= 1% above the demand band); the "
                       "Demand board is a closed-bar scan with an R:R floor. Counts are the last pass "
                       "of each cron, not a full-universe truth. Configured heuristic, not a book "
                       "method. Decision support, not a buy signal, not advice.")


def _coll():
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[PASS_COLL] if db is not None else None
    except Exception as exc:
        log.warning("alert_status: no mongo for %s: %s", PASS_COLL, exc)
        return None


def _int(x) -> Optional[int]:
    """Counts are ints; numpy / floats / bools coerce, garbage drops (None)."""
    if isinstance(x, bool):
        return int(x)
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or math.isinf(v):
        return None
    return int(v)


def clean_counts(counts) -> dict:
    """{str: int} only — a dict / list value (e.g. a stray `hits` list) becomes
    its length, anything non-numeric is dropped."""
    out: dict = {}
    for k, v in (counts or {}).items():
        if isinstance(v, (list, tuple, set, dict)):
            out[str(k)] = len(v)
            continue
        n = _int(v)
        if n is not None:
            out[str(k)] = n
    return out


_NOT_COUNTS = ("ran", "date", "as_of", "reason", "payload", "seconds", "latest_written",
               "breaking", "near_demand",
               # the 🔑 hook's own result rides zone_edge's (2026-09-25); it
               # records its own pass doc, never zone_edge's counts
               "key_levels")


def counts_from_result(result: dict) -> dict:
    """A check_once result -> its counters: numeric keys kept, list-valued keys
    (`hits`) become their length, bookkeeping keys dropped."""
    return clean_counts({k: v for k, v in (result or {}).items() if k not in _NOT_COUNTS})


def record_result(kind: str, result: dict, now: Optional[datetime] = None, coll=None) -> bool:
    """record_pass for a whole check_once result — the one line each pass adds
    before returning. Skips a pass that never ran the read (outside RTH)."""
    result = result or {}
    if not result.get("ran") and not result.get("reason"):
        return False
    return record_pass(kind, counts_from_result(result), now, coll=coll,
                       reason=result.get("reason"))


def record_pass(kind: str, counts: dict, now: Optional[datetime] = None, coll=None,
                reason: Optional[str] = None) -> bool:
    """Replace the `kind` doc with this pass's counters. Best-effort: returns
    True on a write, False on no coll / any error; never raises."""
    try:
        if coll is None:
            coll = _coll()
        if coll is None:
            return False
        now = now or datetime.now(ET)
        et = now.astimezone(ET) if now.tzinfo is not None else now.replace(tzinfo=ET)
        doc = {"_id": str(kind), "as_of": et.isoformat(), "date": et.date().isoformat(),
               "counts": clean_counts(counts)}
        if reason:
            doc["reason"] = str(reason)
        coll.replace_one({"_id": str(kind)}, doc, upsert=True)
        return True
    except Exception as exc:
        log.warning("alert_status: record_pass(%s) failed: %s", kind, exc)
        return False


def cap_floor_txt(usd) -> str:
    """A cap floor in words: 700_000_000 -> '$700M', 1e9 -> '$1B', 1.5e9 -> '$1.5B'."""
    v = float(usd)
    if v >= 1e9:
        b = v / 1e9
        return "$%dB" % int(b) if abs(b - round(b)) < 1e-9 else "$%.1fB" % b
    m = v / 1e6
    return "$%dM" % int(m) if abs(m - round(m)) < 1e-9 else "$%.1fM" % m


def disclaimer() -> str:
    """DISCLAIMER_TEMPLATE with the live cap floor (demand_alerts.MIN_CAP_USD,
    pinned equal to every other S/D floor by test_cap_floor_agrees)."""
    from . import demand_alerts as DA        # lazy: demand_alerts imports alert_status
    return DISCLAIMER_TEMPLATE.format(cap=cap_floor_txt(DA.MIN_CAP_USD))


def gate_payload() -> dict:
    """The phone gate's numbers for the page, every one read from its
    constant: the room / proximity floors (alert_gates) and the cap floor
    (demand_alerts.MIN_CAP_USD) both as a number and as the words
    `cap_floor_txt` makes of it (finding F5, 2026-09-14: Alerts.tsx had the
    OLD floor typed next to the corrected disclaimer — the page renders
    `min_cap_txt` now and types no figure; one formatter, here)."""
    from . import demand_alerts as DA        # lazy: demand_alerts imports alert_status
    from . import enterable as EN
    return {"min_room_pct": float(AG.ALERT_MIN_ROOM_PCT),
            "max_above_demand_pct": float(AG.ALERT_MAX_ABOVE_DEMAND_PCT),
            "min_cap_usd": float(DA.MIN_CAP_USD),
            "min_cap_txt": cap_floor_txt(DA.MIN_CAP_USD),
            # Whether the entry-timing study behind the 🎯 read has reported
            # (2026-09-15). The page says so instead of implying a measurement
            # that has not landed. `skipped_not_enterable` rides in the per-kind
            # counters automatically — `counts_from_result` keeps numeric keys.
            "enterable_status": EN.status()}


def _empty_pass() -> dict:
    return {"as_of": None, "date": None, "counts": {}}


def read_pass(kind: str, coll=None) -> dict:
    """{as_of, date, counts[, reason]} for one recorded kind; a missing or
    unreadable doc is the empty shape (as_of None, counts {})."""
    try:
        if coll is None:
            coll = _coll()
        if coll is None:
            return _empty_pass()
        doc = coll.find_one({"_id": str(kind)})
    except Exception as exc:
        log.warning("alert_status: read_pass(%s) failed: %s", kind, exc)
        return _empty_pass()
    if not doc:
        return _empty_pass()
    out = {"as_of": doc.get("as_of") or None, "date": doc.get("date") or None,
           "counts": clean_counts(doc.get("counts") or {})}
    if doc.get("reason"):
        out["reason"] = str(doc["reason"])
    return out


def read_zone_edge(latest_coll=None) -> dict:
    """The zone_edge pass from its own `zone_edge_latest` 'latest' doc — the
    same counts the board payload carries (a pre-2026-09-05 doc lacks the
    skip buckets; they are passed through as absent, never invented)."""
    try:
        if latest_coll is None:
            from . import zone_edge as ZE
            latest_coll = ZE._coll(ZE.LATEST_COLL)
        if latest_coll is None:
            return _empty_pass()
        doc = latest_coll.find_one({"_id": "latest"})
    except Exception as exc:
        log.warning("alert_status: zone_edge latest read failed: %s", exc)
        return _empty_pass()
    if not doc:
        return _empty_pass()
    # The empty-store self-heal write leaves `as_of` None on purpose (that key
    # means "a real pass with rows" to the board and the paper engine) and
    # stamps `ran_at` instead (zone_edge.check_once, 2026-09-05). For THIS
    # payload `as_of` means "when the cron last ran", the same as the two
    # recorded passes, so the stamp falls through; `reason` says what it found.
    out = {"as_of": doc.get("as_of") or doc.get("ran_at") or None, "date": doc.get("date") or None,
           "counts": clean_counts(doc.get("counts") or {})}
    if doc.get("reason"):
        out["reason"] = str(doc["reason"])
    return out


def _with_cadence(kind: str, pass_doc: dict) -> dict:
    """The pass shape plus its scheduled cadence (contract B allows extra keys)."""
    return dict(pass_doc, cadence_sec=int(CADENCE_SEC[kind]))


def schedule_map() -> dict:
    """{daily kind: 'HH:MM ET, trading days'} — every minute READ from the
    module that owns the pass (`SLOTS_ET` in each), never retyped here, so a
    slot change moves the page with it. Both imports are LAZY: this module
    must stay a module-level leaf (test_alert_status pins that), and
    `chart_maps.earnings_alerts` imports THIS module at its top.

    A module that is not on the path yet answers None rather than a guessed
    string — the page then prints the pass with no schedule, which is honest.
    """
    out: dict = {k: None for k in DAILY_PASS_KINDS}
    try:
        from chart_maps import earnings_alerts as EA
        slots = tuple(EA.SLOTS_ET)
        out["earnings_reaction"] = "%s ET, trading days" % " + ".join(slots)
    except Exception as exc:                      # pragma: no cover - import shim
        log.warning("alert_status: earnings_alerts slots unavailable: %s", exc)
    try:
        from sepa import board_arrival as BA
        for board in ("bonde", "growth"):
            out["board_arrival:%s" % board] = "%s ET, trading days" % BA.SLOTS_ET[board]
    except Exception as exc:                      # pragma: no cover - import shim
        log.warning("alert_status: board_arrival slots unavailable: %s", exc)
    try:
        from growth import quality_alerts as QA   # lazy: it pulls the growth stack
        out["capital_quality_upgrade"] = "%s ET, trading days" % QA.SLOT_ET
    except Exception as exc:                      # pragma: no cover - import shim
        log.warning("alert_status: quality_alerts slot unavailable: %s", exc)
    try:
        from overnight import push as OP         # lazy: this module stays a leaf
        out[OVERNIGHT_KIND] = "%s ET, trading days" % OP.SLOT_ET
    except Exception as exc:                      # pragma: no cover - import shim
        log.warning("alert_status: overnight push slot unavailable: %s", exc)
    return out


def tape_window() -> Optional[dict]:
    """{open, close} 'HH:MM' ET of the tape-burst passes, READ from
    orderflow.trade_flash.WATCH_OPEN_ET / WATCH_CLOSE_ET (never typed). LAZY:
    this module stays a module-level leaf. None when the module cannot be
    read — the page then judges no window rather than a guessed one."""
    try:
        from orderflow import trade_flash as TF
        return {"open": TF.WATCH_OPEN_ET.strftime("%H:%M"),
                "close": TF.WATCH_CLOSE_ET.strftime("%H:%M")}
    except Exception as exc:                      # pragma: no cover - import shim
        log.warning("alert_status: trade_flash window unavailable: %s", exc)
        return None


def _tape_control_coll():
    """The 🎚️ `tape_control_state` collection (tape_control.STATE_COLL, never
    retyped). LAZY: this module stays a module-level leaf. None when Mongo or
    the module cannot be reached — the pins then read `waiting`."""
    try:
        from orderflow import tape_control as TC
        from portfolio.store import _get_db
        db = _get_db()
        return db[TC.STATE_COLL] if db is not None else None
    except Exception as exc:
        log.warning("alert_status: no tape_control state handle: %s", exc)
        return None


def read_tape_control(coll=None, now: Optional[datetime] = None) -> dict:
    """{"pins": [...], "note": str|None} for the 🎚️ pass — tape_control.status_block's
    served words, never recomposed here. Never raises: any failure is no pins."""
    try:
        from orderflow import tape_control as TC
        now = now or datetime.now(ET)
        et = now.astimezone(ET) if now.tzinfo is not None else now.replace(tzinfo=ET)
        return TC.status_block(et, coll=coll if coll is not None else _tape_control_coll())
    except Exception as exc:
        log.warning("alert_status: tape_control status unavailable: %s", exc)
        return {"pins": [], "note": None}


def _daily(kind: str, pass_doc: dict, schedule: dict) -> dict:
    """A once-a-day pass: no cadence to be stale against, a schedule instead."""
    return dict(pass_doc, cadence_sec=None, schedule=schedule.get(kind))


def _finite(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and not math.isinf(v) else None


def _gajjala_alerts_coll():
    """The `gajjala_alerts` ledger through the gajjala store (its collection
    name, never retyped). A fresh store, not the module default: a test run
    without Mongo must not cache a None handle into the shared default.
    LAZY: `chart_maps.gajjala.alerts` imports the medical package, so only the
    store is touched here (test_alert_status pins the leaf)."""
    try:
        from chart_maps.gajjala import store as GS
        return GS.GajjalaStore().alerts_coll()
    except Exception as exc:
        log.warning("alert_status: no gajjala_alerts handle: %s", exc)
        return None


def read_gajjala_shadow(coll=None, now: Optional[datetime] = None) -> list:
    """🚩 Today's shadow A+ records, newest first (2026-10-13, E3).

    Ajay round A (DECISIONS): "every A+ is RECORDED to the alerts ledger and
    shown on /alerts as shadow — not sent". The pass doc only carries COUNTS
    (the medical precedent), so this lists the items behind them: the
    `gajjala_alerts` docs chart_maps.gajjala.alerts.run_pass claimed under the
    SHADOW: key — `state == "shadow"`, the same query its shadow_session count
    runs, so the list and the "N A+ recorded today" chip agree. Only rows of
    the ET day of `now` (the session `date` the pass stamped): yesterday's
    shadow rows never read as today's. A live claim (`claimed` / `pushed` /
    `no_target` / `failed`) is never listed here — what rang is in
    push_history and the list below. A refused A+ (`{key}#{state}`) is never
    a shadow row either.

    Each item: {date, symbol, setup, at (claimed_at, ET iso), entry_bar_t,
    frame, trigger, stop, risk_pct, text, url, note}. `text` is the push's own
    item line (`would_push.items[0].text`, composed by alerts.compose — the one
    wording engine; the page never recomposes it); `url` is the deep link the
    push would have opened (`/chart-maps?tab=gajjala&sub=<setup>&focus=<SYM>`),
    an internal path or None. A Mongo read, nothing parsed or scanned; never
    raises — a dead ledger is [] ."""
    now = now or datetime.now(ET)
    et = now.astimezone(ET) if now.tzinfo is not None else now.replace(tzinfo=ET)
    day = et.date().isoformat()
    try:
        if coll is None:
            coll = _gajjala_alerts_coll()
        if coll is None:
            return []
        docs = list(coll.find({"date": day, "state": "shadow"}))
    except Exception as exc:
        log.warning("alert_status: gajjala shadow read failed: %s", exc)
        return []
    out = []
    for d in docs:
        if not isinstance(d, dict) or d.get("state") != "shadow" or str(d.get("date") or "") != day:
            continue
        wp = d.get("would_push") if isinstance(d.get("would_push"), dict) else {}
        items = wp.get("items") if isinstance(wp.get("items"), list) else []
        first = items[0] if items and isinstance(items[0], dict) else {}
        text = first.get("text") if isinstance(first.get("text"), str) else wp.get("title")
        url = wp.get("url")
        if not (isinstance(url, str) and url.startswith("/") and not url.startswith("//")):
            url = None
        at = d.get("at") or d.get("claimed_at")                 # the pass clock first; the claim's wall clock as fallback
        at = at.isoformat() if hasattr(at, "isoformat") else (str(at) if at else None)
        out.append({"date": day, "symbol": str(d.get("symbol") or "").upper() or None,
                    "setup": d.get("setup") or None, "at": at,
                    "entry_bar_t": d.get("entry_bar_t") or None, "frame": d.get("frame") or None,
                    "trigger": _finite(d.get("trigger")), "stop": _finite(d.get("stop")),
                    "risk_pct": _finite(d.get("risk_pct")),
                    "text": text if isinstance(text, str) and text else None, "url": url,
                    "note": d.get("note") if isinstance(d.get("note"), str) else None})
    out.sort(key=lambda r: (r["at"] or "", r["symbol"] or "", r["setup"] or ""), reverse=True)
    return out


def _gajjala_potentials_coll():
    """The `gajjala_potentials` tracker through the gajjala store (its collection
    name `store.POTENTIALS`, never retyped). A fresh store, the
    `_gajjala_alerts_coll` pattern: a test run without Mongo must not cache a
    None handle into the shared default. LAZY — only the store is touched
    (test_alert_status pins the leaf)."""
    try:
        from chart_maps.gajjala import store as GS
        return GS.GajjalaStore().coll(GS.POTENTIALS)
    except Exception as exc:
        log.warning("alert_status: no gajjala_potentials handle: %s", exc)
        return None


def _et_iso(x) -> Optional[str]:
    """A datetime (UTC or ET) or an ISO string -> an ET ISO string; anything
    unreadable -> None (never a guessed stamp)."""
    if x is None or x == "":
        return None
    try:
        if isinstance(x, str):
            x = datetime.fromisoformat(x)
        if not isinstance(x, datetime):
            return None
        if x.tzinfo is None:
            x = x.replace(tzinfo=timezone.utc)  # the tracker stamps the pass clock in UTC
        return x.astimezone(ET).isoformat()
    except (TypeError, ValueError):
        return None


_POT_PUSH_STATES = ("pushed", "no_target", "failed", "claimed")


def _gajjala_held_text(reason) -> Optional[str]:
    """📌 2026-10-27 (BUILD_SPEC26 A2, critic F2): the FROZEN words of the 🧠 hold chart_maps.gajjala.trader_names owns
    (trader_names.held_text — TRADER_HOLD_TEXT, never retyped here); None for every other reason. LAZY (this module
    stays a leaf); a failed import is None — the page then words the reason as before."""
    if not isinstance(reason, str) or not reason:
        return None
    try:
        from chart_maps.gajjala import trader_names as TN
        return TN.held_text(reason)
    except Exception as exc:
        log.warning("alert_status: trader hold words unavailable: %s", exc)
        return None


def _gajjala_trader_held_text(counts) -> Optional[str]:
    """📌 2026-10-27 (critic F2): the 🧠 pass's `trader_held` counter chip words — TRADER_HOLD_TEXT, served only when
    the latest pass counted one (a pass without it keeps its shape)."""
    try:
        n = int((counts or {}).get("trader_held") or 0)
    except (TypeError, ValueError, AttributeError):
        return None
    if n <= 0:
        return None
    try:
        from chart_maps.gajjala import trader_names as TN
        return TN.TRADER_HOLD_TEXT
    except Exception as exc:
        log.warning("alert_status: trader hold words unavailable: %s", exc)
        return None


def read_gajjala_potentials(coll=None, now: Optional[datetime] = None) -> list:
    """🧠 Today's potentials, newest first sighting first (2026-10-15).

    Ajay 2026-10-15: "In all the sub tab and add a track and alert to show me
    new potential is added everyday." and "Give me an alert all continous
    tracker on these specifically when I get alert I will jump on to ride the
    wave". The pass doc carries COUNTS only (the 🚩 precedent), so this lists
    the tracker docs behind them — `gajjala_potentials`, written ONLY by
    chart_maps.gajjala.potential.track() inside the 5-minute pass. Only docs of
    the ET day of `now` (the session `date` the pass stamped): yesterday's
    potentials never read as today's.

    Each item: {date, symbol, setup, at (first_seen as ET iso), kind
    (first_kind), text (doc.line — composed by potential.line, never
    recomposed here), url (doc.url when an internal path, else None),
    push_state ("pushed" | "no_target" | "failed" | "claimed" | None),
    push_at (ET iso | None), held (the LAST `held` reason | None)[, held_text — 📌 2026-10-27: the served words of a
    📌 trader hold (trader_names.TRADER_HOLD_TEXT), present ONLY on such a row]}. A Mongo
    read, nothing scanned; never raises — a dead tracker is []."""
    now = now or datetime.now(ET)
    et = now.astimezone(ET) if now.tzinfo is not None else now.replace(tzinfo=ET)
    day = et.date().isoformat()
    try:
        if coll is None:
            coll = _gajjala_potentials_coll()
        if coll is None:
            return []
        docs = list(coll.find({"date": day}))
    except Exception as exc:
        log.warning("alert_status: gajjala potentials read failed: %s", exc)
        return []
    out = []
    for d in docs:
        if not isinstance(d, dict) or str(d.get("date") or "") != day:
            continue
        url = d.get("url")
        if not (isinstance(url, str) and url.startswith("/") and not url.startswith("//")):
            url = None
        push = d.get("push") if isinstance(d.get("push"), dict) else {}
        state = push.get("state") if push.get("state") in _POT_PUSH_STATES else None
        held = d.get("held") if isinstance(d.get("held"), list) else []
        last_held = held[-1] if held and isinstance(held[-1], dict) else {}
        reason = last_held.get("reason")
        text = d.get("line")
        first_kind = d.get("first_kind")
        item = {"date": day, "symbol": str(d.get("symbol") or "").upper() or None,
                "setup": d.get("setup") or None, "at": _et_iso(d.get("first_seen")),
                "kind": first_kind if isinstance(first_kind, str) and first_kind else None,
                "text": text if isinstance(text, str) and text else None, "url": url,
                "push_state": state, "push_at": _et_iso(push.get("at")) if push else None,
                "held": reason if isinstance(reason, str) and reason else None}
        words = _gajjala_held_text(item["held"])
        if words:                                   # 📌 2026-10-27 critic F2: only a 📌 hold carries its served words
            item["held_text"] = words
        out.append(item)
    out.sort(key=lambda r: (r["at"] or "", r["symbol"] or "", r["setup"] or ""), reverse=True)
    return out


def status_payload(*, pass_coll=None, latest_coll=None, now: Optional[datetime] = None,
                   gajjala_coll=None, potential_coll=None, tape_control_coll=None) -> dict:
    """GET /alerts/status. Every input is injectable for tests; the route passes
    none. Never raises — a dead Mongo is three empty passes, not a 500.
    The 🚩 pass also carries `shadow_items` (read_gajjala_shadow) — today's
    shadow A+ records, listed under its strip on the page. The 🧠 pass
    (2026-10-15) carries `potential_items` (read_gajjala_potentials) — today's
    tracker docs, listed under its strip. The 🎚️ tape_control pass (2026-10-16)
    carries `window`, `pins` and `note` (read_tape_control)."""
    from . import zone_edge as ZE                 # lazy: zone_edge's siblings import this module
    now = now or datetime.now(ET)
    et = now.astimezone(ET) if now.tzinfo is not None else now.replace(tzinfo=ET)
    try:
        live = bool(ZE.in_session(et))
    except Exception:
        live = False
    if pass_coll is None:
        pass_coll = _coll()
    sched = schedule_map()
    passes = {
        ZONE_EDGE_KIND:      _with_cadence(ZONE_EDGE_KIND, read_zone_edge(latest_coll)),
        "zone_bounce_alert": _with_cadence("zone_bounce_alert", read_pass("zone_bounce_alert", pass_coll)),
        "demand_alert":      _with_cadence("demand_alert", read_pass("demand_alert", pass_coll)),
        KEY_LEVEL_KIND:      _with_cadence(KEY_LEVEL_KIND, read_pass(KEY_LEVEL_KIND, pass_coll)),
        MED_KIND:            _with_cadence(MED_KIND, read_pass(MED_KIND, pass_coll)),
        GAJJALA_KIND:        dict(_with_cadence(GAJJALA_KIND, read_pass(GAJJALA_KIND, pass_coll)),
                                  shadow_items=read_gajjala_shadow(gajjala_coll, et)),
        GAJJALA_POTENTIAL_KIND: dict(_with_cadence(GAJJALA_POTENTIAL_KIND,
                                                   read_pass(GAJJALA_POTENTIAL_KIND, pass_coll)),
                                     potential_items=read_gajjala_potentials(potential_coll, et)),
    }
    tw = _gajjala_trader_held_text(passes[GAJJALA_POTENTIAL_KIND].get("counts"))
    if tw:                                          # 📌 2026-10-27 critic F2: the chip's served words, only when counted
        passes[GAJJALA_POTENTIAL_KIND]["trader_held_text"] = tw
    window = tape_window()
    for kind in TAPE_KINDS:
        passes[kind] = dict(_with_cadence(kind, read_pass(kind, pass_coll)), window=window)
    passes[TAPE_CONTROL_KIND] = dict(_with_cadence(TAPE_CONTROL_KIND, read_pass(TAPE_CONTROL_KIND, pass_coll)),
                                     window=window, **read_tape_control(tape_control_coll, et))
    for kind in DAILY_PASS_KINDS:
        passes[kind] = _daily(kind, read_pass(kind, pass_coll), sched)
    return {
        "in_session": live,
        "now_et": et.isoformat(),
        "gate": gate_payload(),
        "passes": passes,
        "disclaimer": disclaimer(),
    }


__all__ = ["PASS_COLL", "PASS_KINDS", "KEY_LEVEL_KIND", "MED_KIND", "GAJJALA_KIND", "GAJJALA_POTENTIAL_KIND", "TAPE_KINDS", "TAPE_CONTROL_KIND", "OVERNIGHT_KIND", "tape_window", "read_tape_control", "DAILY_PASS_KINDS", "CADENCE_SEC", "schedule_map",
           "record_pass", "record_result", "counts_from_result",
           "read_pass", "read_zone_edge", "gate_payload", "read_gajjala_shadow",
           "read_gajjala_potentials",
           "status_payload", "clean_counts", "DISCLAIMER_TEMPLATE", "disclaimer", "cap_floor_txt"]
