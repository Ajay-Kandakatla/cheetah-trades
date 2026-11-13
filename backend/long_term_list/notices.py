"""📅 Long Term — per-name state, weekly events and the digest (spec §3.6, critique C4 + C5).

Pure. Only three causes can ever ring (constants.RING_KINDS): a Stage 2 name
now in Stage 3 or 4 (stage_drop), a sales tier below its tier at save
(sales_drop), a 🌱 name moving Stage 1 → Stage 2 (started_moving). A
fundamental leg that fails is ⚠️ on the tab and a digest line, never a ring by
itself. A market leg that flips is a neutral `moved` line on its category —
never ⚠️, never `changed`. Missing data is `absent`: "not read, not dropped".

Per-name flags carried run to run (week 1 = `initial_flags(at_save(...))`):
  last_stage          last non-None stage read
  last_stage2_on      date of the last read at Stage 2 (= SAVED_ON when saved at Stage 2)
  stage_drop_on       date of the last stage_drop event
  stage_drop_active   True from a stage_drop until the next Stage 2 read
  sales_drop_active   True while the tier sits below its tier at save
  fundamental_failing [category…] with a fundamental leg that flipped pass → fail
  leg_last_known      {category: {leg: "pass"|"fail"}} last pass/fail read of each fundamental
                      leg, so pass → unknown → fail still raises ⚠️ (written by detect only;
                      absent from initial_flags so the baseline flags stay unchanged)
  started_moving_on   date of the last started_moving event
  zone_in             [zone…] the 🧭 zones the last read sat in
  absent              [source…] missing this week
"""
from __future__ import annotations

import copy
from typing import Optional

from . import constants as C
from . import criteria as CR
from . import words as W

KIND_ORDER = ("stage_drop", "sales_drop", "started_moving", "fundamental", "zone", "moved", "absent")
_EVENT_PRECEDENCE = ("stage_drop", "sales_drop", "started_moving", "fundamental", "moved", "zone", "absent")
STAGE_MOVED_CATS = ("quiet_strong", "accel_after_fall")


def _leg_dicts(legs) -> list:
    """list[Leg] | list[dict] | {key: verdict} -> [{"key","kind","verdict","text"}]."""
    out = []
    if isinstance(legs, dict):
        for k, v in legs.items():
            out.append({"key": k, "kind": None, "verdict": v, "text": W.DASH})
        return out
    for lg in legs or []:
        if isinstance(lg, CR.Leg):
            out.append({"key": lg.key, "kind": lg.kind, "verdict": lg.verdict, "text": lg.text})
        elif isinstance(lg, dict):
            out.append({"key": lg.get("key"), "kind": lg.get("kind"), "verdict": lg.get("verdict"),
                        "text": lg.get("text") or W.DASH})
    return out


def verdicts(legs) -> dict:
    """{leg key: verdict} from any of the leg shapes."""
    return {d["key"]: d["verdict"] for d in _leg_dicts(legs)}


def at_save(symbol, baseline) -> dict:
    """{"stage","sales_tier","legs": {cat: {leg: verdict}}, "zone_in": [...]} from the at-save baseline."""
    b = baseline or {}
    sym = str(symbol).upper()
    name = (b.get("names") or {}).get(sym) or {}
    legs: dict = {}
    for cat, rows in (b.get("categories") or {}).items():
        row = (rows or {}).get(sym)
        if not row:
            continue
        if row.get("legs") is not None:
            legs[cat] = verdicts(row["legs"])
        elif row.get("values") is not None and cat in CR.LEG_KINDS:
            legs[cat] = {lg.key: lg.verdict for lg in CR.legs(cat, row["values"])}
    zr = ((b.get("pankaj") or {}).get(sym) or {}).get("zone_read") or {}
    return {"stage": name.get("stage"), "sales_tier": name.get("sales_tier"), "legs": legs,
            "zone_in": list(zr.get("in") or [])}


def initial_flags(save: dict, saved_on: str = C.SAVED_ON) -> dict:
    stage = (save or {}).get("stage")
    return {
        "last_stage": stage,
        "last_stage2_on": saved_on if stage == C.S2_STAGE else None,
        "stage_drop_on": None,
        "stage_drop_active": False,
        "sales_drop_active": False,
        "fundamental_failing": [],
        "started_moving_on": None,
        "zone_in": list((save or {}).get("zone_in") or []),
        "absent": [],
    }


def _ladder_index(tier) -> Optional[int]:
    if isinstance(tier, str) and tier in C.SALES_TIER_LADDER:
        return C.SALES_TIER_LADDER.index(tier)
    return None


def _event(symbol, kind, session, categories, text, detail=None) -> dict:
    return {"symbol": symbol, "kind": kind, "date": session, "categories": list(categories),
            "text": text, "detail": detail or {}, "rings": kind in C.RING_KINDS}


def detect(symbol, chips, flags, prev_legs, now, save, session) -> tuple:
    """(events, new flags) for one saved name this week.

    chips      [category key…] the name carries
    flags      last week's flags (None -> initial_flags(save))
    prev_legs  {cat: legs} of the last run (None -> the at-save legs)
    now        {"stage","stage_label","sales_tier","sales_yoy_pct","sales_q_end",
                "legs": {cat: [Leg|dict]}, "zone_read": dict|None, "absent": [source…]}
    save       at_save(...) output
    session    "YYYY-MM-DD" of this read
    """
    sym = str(symbol).upper()
    chips = list(chips or [])
    save = save or {}
    now = now or {}
    f = copy.deepcopy(flags) if flags else initial_flags(save)
    for k, v in initial_flags(save).items():
        f.setdefault(k, v)
    events: list = []
    now_stage = now.get("stage")
    prior_last = f.get("last_stage")

    # ── stage_drop: Stage 2 at save or at any run since the last drop, now 3 / 4 [C5] ──
    fired_drop = False
    last2, drop_on = f.get("last_stage2_on"), f.get("stage_drop_on")
    if now_stage in C.STAGE_DROP_TO and last2 and (drop_on is None or last2 > drop_on):
        events.append(_event(sym, "stage_drop", session, chips,
                             W.stage_drop_text(sym, now_stage, now.get("stage_label"), last2),
                             {"to": now_stage, "last_stage2_on": last2}))
        f["stage_drop_on"] = session
        f["stage_drop_active"] = True
        fired_drop = True
    if now_stage == C.S2_STAGE:
        f["last_stage2_on"] = session
        f["stage_drop_active"] = False

    # ── started_moving: a 🌱 name, last non-None read Stage 1, now Stage 2 ──
    fired_start = False
    if ("quiet_strong" in chips and now_stage == C.STARTED_MOVING_PAIR[1]
            and prior_last == C.STARTED_MOVING_PAIR[0]):
        events.append(_event(sym, "started_moving", session, ["quiet_strong"],
                             W.started_moving_text(sym, now.get("stage_label")),
                             {"from": prior_last, "to": now_stage}))
        f["started_moving_on"] = session
        fired_start = True
    if now_stage is not None:
        f["last_stage"] = now_stage

    # ── sales_drop: tier below its tier at save; unknown either side -> nothing ──
    fired_sales = False
    si, ni = _ladder_index(save.get("sales_tier")), _ladder_index(now.get("sales_tier"))
    if si is not None and ni is not None:
        if ni < si:
            if not f.get("sales_drop_active"):
                events.append(_event(sym, "sales_drop", session, chips,
                                     W.sales_drop_text(sym, save.get("sales_tier"), now.get("sales_tier"),
                                                       now.get("sales_yoy_pct"), now.get("sales_q_end")),
                                     {"from": save.get("sales_tier"), "to": now.get("sales_tier")}))
                fired_sales = True
            f["sales_drop_active"] = True
        else:
            f["sales_drop_active"] = False

    # ── per category: fundamental ⚠️ and neutral moved lines ──
    prev_all = prev_legs if prev_legs is not None else (save.get("legs") or {})
    save_legs = save.get("legs") or {}
    failing = list(f.get("fundamental_failing") or [])
    last_known = copy.deepcopy(f.get("leg_last_known") or {})
    now_legs = now.get("legs") or {}
    for cat in chips:
        if cat == C.PANKAJ_KEY or cat not in CR.LEG_KINDS:
            continue
        cur = _leg_dicts(now_legs.get(cat))
        if not cur:
            continue
        pv = verdicts(prev_all.get(cat)) if prev_all.get(cat) is not None else verdicts(save_legs.get(cat))
        sv = verdicts(save_legs.get(cat)) if save_legs.get(cat) is not None else {}
        lk = last_known.setdefault(cat, {})
        kinds = CR.LEG_KINDS[cat]
        newly, newly_any, moved = [], False, []
        all_f_pass = True
        for lg in cur:
            key, v = lg["key"], lg["verdict"]
            kind = lg.get("kind") or kinds.get(key)
            old = pv.get(key)
            flipped = old in (CR.PASS, CR.FAIL) and v in (CR.PASS, CR.FAIL) and old != v
            if kind == CR.FUNDAMENTAL:
                if v != CR.PASS:
                    all_f_pass = False
                f_old = old
                if f_old not in (CR.PASS, CR.FAIL):      # last week unread -> the last known verdict
                    f_old = lk.get(key) if lk.get(key) in (CR.PASS, CR.FAIL) else sv.get(key)
                if v in (CR.PASS, CR.FAIL):
                    lk[key] = v
                if f_old == CR.PASS and v == CR.FAIL:
                    newly_any = True
                    if fired_sales and key == "sales_tier":
                        continue                         # folded into the sales_drop event
                    newly.append(lg["text"])
            elif kind == CR.MARKET:
                if flipped:
                    moved.append(lg["text"])
            elif kind == CR.STAGE:
                if cat not in STAGE_MOVED_CATS or not flipped or fired_drop:
                    continue
                if cat == "quiet_strong" and fired_start:
                    continue                             # the 🌱 → 🚀 event already says it
                if cat == "quiet_strong" and old == CR.PASS and now_stage is not None:
                    moved.append(W.left_stage1_text(now_stage, now.get("stage_label")))
                else:
                    moved.append(lg["text"])
        if newly:
            events.append(_event(sym, "fundamental", session, [cat], W.fundamental_text(sym, cat, newly),
                                 {"legs": newly}))
        if newly_any and cat not in failing:
            failing.append(cat)
        if all_f_pass and cat in failing:
            failing.remove(cat)
        if moved:
            events.append(_event(sym, "moved", session, [cat], W.moved_text(sym, moved), {"legs": moved}))
    f["fundamental_failing"] = [c for c in chips if c in failing]
    f["leg_last_known"] = {c: v for c, v in last_known.items() if v}

    # ── 🧭 zone: newly inside one of Pankaj's zones (neutral) ──
    zr = now.get("zone_read")
    if C.PANKAJ_KEY in chips and isinstance(zr, dict) and not zr.get("unknown"):
        prev_in = set(f.get("zone_in") or [])
        for zk in zr.get("in") or []:
            if zk in prev_in:
                continue
            lo, hi = (zr.get("zones") or {}).get(zk) or (None, None)
            events.append(_event(sym, "zone", session, [C.PANKAJ_KEY],
                                 W.zone_event_text(sym, zk, lo, hi, zr.get("close_date")), {"zone": zk}))
        f["zone_in"] = list(zr.get("in") or [])

    # ── absent: not read, not dropped ──
    ab = [s for s in (now.get("absent") or []) if s]
    if ab:
        events.append(_event(sym, "absent", session, chips, W.absent_text(sym, ab), {"sources": ab}))
    f["absent"] = ab

    events.sort(key=lambda e: _EVENT_PRECEDENCE.index(e["kind"]))
    return events, f


def section_for(flags, now, session) -> str:
    """"changed" | "started_moving" | "not_read" | "holding"."""
    f = flags or {}
    if f.get("stage_drop_active") or f.get("sales_drop_active") or f.get("fundamental_failing"):
        return "changed"
    if session and f.get("started_moving_on") == session:
        return "started_moving"
    n = now or {}
    readable = []
    for legs in (n.get("legs") or {}).values():
        for d in _leg_dicts(legs):
            if d.get("kind") != CR.INFO and d.get("verdict") != CR.INFO_V:
                readable.append(d.get("verdict"))
    if readable:
        if all(v == CR.UNKNOWN for v in readable):
            return "not_read"
    else:
        zr = n.get("zone_read")
        if n.get("stage") is None and (not isinstance(zr, dict) or zr.get("unknown")):
            return "not_read"
    return "holding"


def digest(events, top_new, session) -> dict:
    """The weekly digest: title, body lines (capped), items and counts."""
    evs = sorted(events or [], key=lambda e: (KIND_ORDER.index(e["kind"]), e["symbol"]))
    counts = {k: sum(1 for e in evs if e["kind"] == k) for k in KIND_ORDER}
    n_dropped = counts["stage_drop"] + counts["sales_drop"]
    top_lines = [W.top_new_text(cat, syms) for cat, syms in (top_new or {}).items() if syms]
    n_new = sum(len(s) for s in (top_new or {}).values() if s)
    all_lines = [e["text"] for e in evs] + top_lines
    lines = all_lines[:C.DIGEST_BODY_LINES]
    if len(all_lines) > C.DIGEST_BODY_LINES:
        lines.append(W.more_text(len(all_lines) - C.DIGEST_BODY_LINES))
    n_ring = sum(1 for e in evs if e["kind"] in C.RING_KINDS)
    return {
        "title": W.digest_title(session, n_dropped, counts["started_moving"], counts["zone"]),
        "lines": lines,
        "items": [{"symbol": e["symbol"], "kind": e["kind"], "text": e["text"]} for e in evs],
        "n_ring": n_ring,
        "n_dropped": n_dropped,
        "n_started": counts["started_moving"],
        "n_fundamental": counts["fundamental"],
        "n_zone": counts["zone"],
        "n_moved": counts["moved"],
        "n_new_in_top": n_new,
        "n_absent": counts["absent"],
        "rings": n_ring > 0,
    }
