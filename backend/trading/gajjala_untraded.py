"""🏁 Not traded on the 🚩 lane (2026-11-11) — the 🏁 Track record's own grade on every lane row without a fill.

Ajay 2026-11-11 ~12:00 ET, verbatim: "Maintain a track record when Alpaca is blocked please, Like we do in Gajjals so I
know how our strategies are working"

PURE READS. This module never writes a collection and never touches an order. It joins each stored lane row with no fill
(skipped / unfilled / dry_run) to the SAME alert's 🏁 row (lane `_id` = the raw `GG:` alert → `ledger.alert_of` → the
ledger id) and prints the 🏁's own same-session cell words. The block tallies those cells with the 🏁's own thin rule
(`ledger._tally_into`) and its 🔁 one count per stock per day (`ledger.dedupe_trades`). No R, no $, no new grading math:
every grade is the stored nightly `same` column, or today a memo-only provisional through `ledger.grade` on the 🏁's
own memo (`ledger.today_bars(load=None)` never fetches). Nothing here is ever summed into the lane's P&L, the journal or
the P&L by lane. Rows the lane's own rule called out (never_triggered, v1 dead) and 🏁 fills outside the lane's own clock
are listed apart from the total. A tally of the alerts as sent, small n — UNMEASURED, not advice.
Spec: scratchpad four/laneskip/spec.md §3.1 · docs/trading_gajjala_lane.md "🏁 Not traded".
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable, Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as GLG
from trading import gajjala_entry as GL

log = logging.getLogger("trading.gajjala_untraded")

UNTRADED_STATES = ("skipped", "unfilled", "dry_run")          # ⊂ GL.STATES (test pins)
TRADED_STATES = ("open", "closing", "closed")                  # ⊂ GL._DAY_STATES (test pins) — the comparison line
NOT_SEEN_FINAL = ("off", "after_cutoff")                       # tab_payload's synthetic reasons: ROW CELL ONLY, never counted
REASON_ORDER = ("broker_gap", "blocked", "rounding", "unfilled", "floor", "earnings", "missed", "size", "cap_open",
                "held", "cooldown", "halt", "no_plan", "no_risk", "disarmed", "thin_r", "stale", "cap_day",
                "never_triggered", "dead", "other")
OUT_OF_TOTAL = ("never_triggered", "dead")                     # MINE — HIS CALL UT-7: the lane's own rule said out
ROW_TRACK_KEYS = ("track_state", "track_text")
BLOCK_KEYS = ("title", "span_text", "total", "lines", "traded", "honesty", "fault_text")
LINE_KEYS = ("key", "label", "n", "counts", "dup", "no_row", "late", "in_total", "provisional", "text")
LATE_KINDS = ("other_session", "after_cutoff", "past_flatten")
TRACK_LEAD = "not traded · 🏁"
TITLE = "🏁 Not traded — the same alerts graded by GG's trade math"
TOTAL_LABEL = "All not traded (the lane's 'out' rows apart)"
TRADED_LABEL = "Lane fills, the same 🏁 grade"
OUT_TAIL = "not in the total — the lane's own rule said out"
LATE_TAIL = "after the lane's cut-off or flatten (not counted)"
FAULT_TEXT = "🏁 grades not read on this open — the lane rows are unchanged"
EMPTY_TEXT = "No lane row without a fill yet."
NO_ROW_TEXT = "has no 🏁 row for this alert"
STOP_TAIL = {"broker_gap": "at the alert's stop, which Alpaca refuses",
             "rounding": "at the alert's stop, before the broker's price grid"}      # HIS CALL UT-7b
# MINE (HIS CALL UT-10) — every number is a constant by name, never retyped
REASON_TEXT = {
    "broker_gap": f"Alpaca refused — stop under ${GL.MIN_STOP_GAP_USD:.2f} below the last",
    "blocked": "the order never reached the broker",
    "rounding": f"the broker's price grid moved the stop over {GL.GAJJALA_MAX_ROUND_R_PCT:g}% of R",
    "unfilled": "order sent, never filled",
    "floor": "house safety floors (your switch)",
    "earnings": "refused on earnings",
    "missed": f"already past +{GL.GAJJALA_MISSED_R:g}R when the lane looked",
    "size": "0 shares fit the size",
    "cap_open": f"{GL.GAJJALA_MAX_OPEN} positions already open",
    "held": "already holding the name",
    "cooldown": "cooldown after a stop-out",
    "halt": "halt wait ran into the cut-off",
    "no_plan": "no usable trigger and stop",
    "no_risk": "trigger = stop",
    "disarmed": "engine disarmed — nothing sent",
    "thin_r": "v1 thin-R refusal (retired)",
    "stale": "v1 stale line (retired)",
    "cap_day": "v1 day cap (retired)",
    "never_triggered": ("never triggered for the lane — the stop printed first, or no trade at the trigger by the "
                        "cut-off"),
    "dead": "v1 dead setup (retired) — the stop printed first",
    "other": "other",
}


# ── seams + small pure pieces ────────────────────────────────────────────────────────────────────────────────────
def _store():
    """The 🏁 store (GG5), as GL._alert_docs builds it — the tests inject a GajjalaStore(colls=…)."""
    from chart_maps.gajjala import store as ST
    return ST.GajjalaStore()


def is_untraded(doc: dict) -> bool:
    return (doc or {}).get("state") in UNTRADED_STATES


def is_traded(doc: dict) -> bool:
    return (doc or {}).get("state") in TRADED_STATES


def cell_only(doc: dict) -> bool:
    """Today's synthetic not-seen row the lane will never trade (lane off / after the cut-off): the row cell only."""
    return (doc or {}).get("state") == "not_seen" and (doc or {}).get("not_seen") in NOT_SEEN_FINAL


def reason_of(doc: dict) -> str:
    d = doc or {}
    k = d.get("skip_kind")
    if k in REASON_ORDER:
        return k
    if not k and d.get("state") == "unfilled":
        return "unfilled"
    if d.get("state") == "dry_run":
        return "disarmed"
    return "other"


def lane_window_miss(day: str, g: Optional[dict]) -> Optional[str]:
    """The lane's own clock against the 🏁's STORED fill_t / exit_t (no new math): a fill on another session, a fill at
    or after the lane's cut-off, or a decided exit at or after the lane's flatten. None = inside the lane's window."""
    if not isinstance(g, dict) or g.get("entry") != "filled":
        return None
    ft = GLG._parse_at(g.get("fill_t"))
    if ft is None:
        return None
    f = ft.astimezone(GL.ET)
    if f.date().isoformat() != day:
        return LATE_KINDS[0]
    if f.time() >= GL.cutoff_et(day):
        return LATE_KINDS[1]
    if g.get("outcome") in GLG.DECIDED:
        xt = GLG._parse_at(g.get("exit_t"))
        if xt is not None:
            x = xt.astimezone(GL.ET)
            if x.date().isoformat() != day or x.time() >= GL.flatten_et(day):
                return LATE_KINDS[2]
    return None


def provisional_same(row: dict, session: date, now: datetime, *,
                     today_bars: Optional[Callable] = None) -> Optional[dict]:
    """Today's provisional same-session grade from the 🏁's OWN memo (MEMO-ONLY: `load=None` never fetches), cut
    exactly as ledger.today_read cuts it. None on a memo miss or when the row's same session is not `session`."""
    if row.get("date") != session.isoformat() or row.get("plan") != GLG.PLANS[0]:
        return None
    bars, fetched = (today_bars or GLG.today_bars)(row["symbol"], session, now=now, load=None)
    if not bars or fetched is None:
        return None
    now = GLG._aware(now)
    cut = GLG._floor_minute(min(now, GLG._aware(fetched)) - GLG.SETTLE)
    closed = [b for b in bars if b[0] + GLG.ONE_MIN <= cut]
    b = GLG._bounds_of(row)
    if not b or b["same_date"] != session:
        return None
    return GLG.grade(row, closed, dict(b, same_end=min(b["same_end"], cut)), "same")


def _thin_out(state: Optional[str]) -> bool:
    """Does THE thin rule (ledger._tally_into) keep this cell state out of the counts? — asked of the 🏁 itself."""
    c = GLG._counts_blank("same")
    GLG._tally_into(c, state, True)
    return c["thin"] > 0


def track_of(row: Optional[dict], cell: Optional[dict], *, reason: str, late: Optional[str], day: str,
             dup_text: Optional[str], fill_t: Optional[str] = None) -> dict:
    """-> {track_state, track_text}: TRACK_LEAD + the 🏁's own cell words, then the tails (late · out · stop · thin ·
    🔁). `fill_t` = the 🏁 fill stamp, read only for the after-cut-off tail."""
    tails = []
    if row is None or cell is None:
        state, text = "no_row", f"{TRACK_LEAD} {NO_ROW_TEXT}"
    else:
        state = cell["state"]
        text = f"{TRACK_LEAD} {cell['text']}" + (f" — {cell['sub_text']}" if cell.get("sub_text") else "")
    if late == LATE_KINDS[1]:
        tails.append(f"the 🏁 filled at {GL._et_hhmm(fill_t) or '—'} ET, after the lane's "
                     f"{GL._hhmm(GL.cutoff_et(day))} ET cut-off — not counted")
    elif late == LATE_KINDS[2]:
        tails.append(f"the 🏁 exit came after the lane's {GL._hhmm(GL.flatten_et(day))} ET flatten — not counted")
    elif late == LATE_KINDS[0]:
        tails.append("the 🏁 filled on a session the lane never trades — not counted")
    if reason in OUT_OF_TOTAL:
        tails.append(OUT_TAIL)
    if cell is not None and reason in STOP_TAIL and cell.get("state") in GLG.DECIDED:
        tails.append(STOP_TAIL[reason])
    if row is not None and cell is not None and row.get("thin") and _thin_out(cell.get("state")):
        tails.append(f"{GLG.THIN_TEXT} (not in the counts)")
    if dup_text:
        tails.append(dup_text)
    return {"track_state": state, "track_text": text + "".join(f" · {t}" for t in tails)}


def honesty_text(day: str) -> str:
    return (f"A 🏁 grade is not a fill: it enters at the trigger from {GLG._t(GC.LEDGER_FILL_FROM_ET)} ET and wins at "
            f"+{GLG._m()}R before the stop; a gap through the stop is not priced. The lane's own trade exits on "
            f"breakeven, the add, the partial and the {GL.GG_TRAIL_EMA} EMA trail, flat by "
            f"{GL._hhmm(GL.flatten_et(day))} ET. Rows the lane's own rule called out, and 🏁 fills after the lane's "
            f"{GL._hhmm(GL.cutoff_et(day))} ET cut-off, stay out of the total. Never added to the lane's P&L above. A "
            f"tally of the alerts as sent, small n — UNMEASURED, not advice.")


# ── the block ────────────────────────────────────────────────────────────────────────────────────────────────────
def _blank_line(key: str, label: str, in_total: bool) -> dict:
    return {"key": key, "label": label, "n": 0, "counts": GLG._counts_blank("same"), "dup": 0, "no_row": 0,
            "late": 0, "in_total": in_total, "provisional": False, "text": None}


def _line_text(ln: dict, out_tail: bool) -> str:
    c = ln["counts"]
    return (f"{ln['label']}: {ln['n']} · {GLG._wl(c)}"
            + (f" · {c['open']} open" if c["open"] else "")            # the 🏁's own word (_counts_text), true intraday too
            + (f" · {c['no_entry']} no entry" if c["no_entry"] else "")
            + GLG._extras(c, "same") + GLG._dup_tail(ln["dup"])
            + (f" · {ln['no_row']} without a 🏁 row" if ln["no_row"] else "")
            + (f" · {ln['late']} {LATE_TAIL}" if ln["late"] else "")
            + (f" · {OUT_TAIL}" if out_tail else "")
            + (" · today not final" if ln["provisional"] else ""))


def _fault_block() -> dict:
    return {"title": TITLE, "span_text": None, "total": None, "lines": [], "traded": None, "honesty": None,
            "fault_text": FAULT_TEXT}


def read(lane_docs: list, *, day: str, now: datetime, shown_ids: Optional[set] = None, store=None,
         today_bars: Optional[Callable] = None) -> dict:
    """-> {"rows": {lane_id: {track_state, track_text}}, "block": {BLOCK_KEYS}}. ONE alert_rows call and AT MOST ONE
    ledger find by ids; NEVER WRITES. A read fault (either read None, or anything raising) -> rows {} + the fault block."""
    try:
        return _read(lane_docs, day=day, now=now, shown_ids=shown_ids, store=store, today_bars=today_bars)
    except Exception as exc:                                    # noqa: BLE001 — the lane panel never goes down on this
        log.warning("gajjala untraded: read failed: %s", type(exc).__name__)
        return {"rows": {}, "block": _fault_block()}


def _read(lane_docs, *, day, now, shown_ids, store, today_bars) -> dict:
    from chart_maps.gajjala import alerts as AL
    from chart_maps.gajjala import store as ST
    store = store if store is not None else _store()
    now = GLG._aware(now)
    session = GLG._as_date(day)
    all_docs = [d for d in lane_docs or [] if isinstance(d, dict)]
    docs = [d for d in all_docs if is_untraded(d) or is_traded(d) or cell_only(d)]
    dates = sorted({str(d.get("date")) for d in all_docs if d.get("date")})
    al = store.alert_rows(dates)
    if al is None:
        return {"rows": {}, "block": _fault_block()}
    by_date: dict = {}                                          # ONE pass over the alerts, then each date reads its own
    for x in al:
        xd = GLG._as_date(x.get("date")) if isinstance(x, dict) and isinstance(x.get("date"), str) else None
        if xd is not None:                                      # alert_of needs a str date (else it is never a row)
            by_date.setdefault(xd.isoformat(), []).append(x)
    entry = {raw["_id"]: a for d in dates for a, raw in GL._live_alerts(d, by_date.get(d, []))}
    ids = [a["id"] for a in entry.values()]
    led = [] if not ids else store._find_or_none(ST.LEDGER, {"_id": {"$in": ids}})
    if led is None:
        return {"rows": {}, "block": _fault_block()}
    stored = {x["_id"]: x for x in led if isinstance(x, dict)}
    by_lid = {a["id"]: a for a in entry.values()}
    sames, facts = {}, []
    for row in entry.values():
        doc = stored.get(row["id"]) or {}
        same = doc.get("same") if isinstance(doc.get("same"), dict) else None
        nxt = doc.get("next") if isinstance(doc.get("next"), dict) else None
        prov = False
        if same is None:
            same = provisional_same(row, session, now, today_bars=today_bars)
            prov = same is not None
        sames[row["id"]] = (same, prov)
        facts.append(GLG.trade_facts(row, same, nxt, group=GLG.dup_group(row), rank=GLG._setup_rank(row["setup"])))
    dups = GLG.dedupe_trades([f for f in facts if f])

    def _dup_text(lid):
        first = dups.get(lid)
        if first is None:
            return None
        c_row = by_lid.get(first) or {}
        e, label = AL.SETUP_META.get(c_row.get("setup"), ("", c_row.get("setup")))
        return GLG.DUP_TEXT.format(at=c_row.get("at_et") or GLG.NO_TIME_TEXT, setup=f"{e} {label}".strip())

    rows: dict = {}
    lines = {k: _blank_line(k, REASON_TEXT[k], k not in OUT_OF_TOTAL) for k in REASON_ORDER}
    traded = _blank_line("traded", TRADED_LABEL, False)
    untraded_docs = []
    for doc in docs:
        row = entry.get(doc.get("_id"))
        same, prov = sames.get(row["id"], (None, False)) if row else (None, False)
        cell = GLG._cell(row, "same", same, prov, now, session, True) if row else None
        late = lane_window_miss(str(doc.get("date") or ""), same)
        reason = reason_of(doc)
        dup_text = _dup_text(row["id"]) if row else None
        if is_untraded(doc) or cell_only(doc):
            rows[doc["_id"]] = track_of(row, cell, reason=reason, late=late, day=str(doc.get("date") or day),
                                        dup_text=dup_text, fill_t=(same or {}).get("fill_t"))
        if cell_only(doc):
            continue                                            # today's not-seen rows are NEVER tallied
        ln = traded if is_traded(doc) else lines[reason]
        if is_untraded(doc):
            untraded_docs.append(doc)
        ln["n"] += 1
        if dup_text:
            ln["dup"] += 1
        elif row is None:
            ln["no_row"] += 1
        elif late:
            ln["late"] += 1
        else:
            GLG._tally_into(ln["counts"], cell["state"], bool(row.get("thin")))
            ln["provisional"] = ln["provisional"] or bool(cell.get("provisional"))
    out_lines = []
    for k in REASON_ORDER:
        ln = lines[k]
        if not ln["n"]:
            continue
        ln["counts"]["pct"] = GLG._win_pct(ln["counts"])
        ln["text"] = _line_text(ln, not ln["in_total"])
        out_lines.append(ln)
    traded["counts"]["pct"] = GLG._win_pct(traded["counts"])
    traded["text"] = _line_text(traded, False)
    total = None
    if untraded_docs:
        total = _blank_line("total", TOTAL_LABEL, True)
        for ln in out_lines:
            if not ln["in_total"]:
                continue
            for k in ("n", "dup", "no_row", "late"):
                total[k] += ln[k]
            for k, v in ln["counts"].items():
                if k != "pct":
                    total["counts"][k] += v
            total["provisional"] = total["provisional"] or ln["provisional"]
        total["counts"]["pct"] = GLG._win_pct(total["counts"])
        total["text"] = _line_text(total, False)
        first = min(str(d.get("date")) for d in untraded_docs)
        span = (f"Every lane row without a fill since {first} — {GLG._plural(len(untraded_docs), 'row', 'rows')} · "
                f"the 🏁 same-session column · one count per stock per day")
        if shown_ids is not None and any(d.get("_id") not in shown_ids for d in untraded_docs):
            span += f" · the table shows today and the last {GL.RECENT_MAX}"
    else:
        span = EMPTY_TEXT
    block = {"title": TITLE, "span_text": span, "total": total, "lines": out_lines, "traded": traded,
             "honesty": honesty_text(day), "fault_text": None}
    return {"rows": rows, "block": block}
