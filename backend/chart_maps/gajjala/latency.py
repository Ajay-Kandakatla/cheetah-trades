"""⏱ Speed — the latency ledger of the 🚩 A+ path (GG LIVE P4, BUILD SPEC rev 2 §3.6, 2026-11-09). READ SIDE ONLY.

THE ASK (Ajay 2026-11-09 ~01:00 ET, verbatim): "I would like the autopilot to be continously monitored or live tracked
and changed as if Gallalas makes the trades can you modify and make it more live with websockets or something else where
there is a low latency monitoring on the prices action changes please?" — this module measures every step from the
5-minute entry bar's CLOSE to the phone ring and the lane's order / fill, from records that already exist
(`gajjala_alerts`, `gajjala_lane`) plus the stream's shadow rows (`gajjala_lane_stream`, written by
trading/gajjala_stream.py) and the bar-finality probe (`gajjala_bar_final`, written by chart_maps/gajjala/bar_close.py).

CLOCKS (critique C4 — the trap this file exists to avoid): `entry_bar_t` is a NAIVE ET "YYYY-MM-DD HH:MM" (the bar's
RIGHT label = its close) and is parsed with `gajjala_entry._parse_et`; never shifted by the frame's minutes (a 15m row
is not moved). Every other stamp (`at`, `claimed_at`, `first_seen`, `ordered_at`, `fill_t`, `recv_t`, `print_t`) is a
UTC ISO stamp parsed with `gajjala_entry._parse`. A naive-as-UTC read of `entry_bar_t` adds 14,400 s+ (ring p50
14,472.7 s instead of 70.6 s on the 2026-11-09 probe) — tests/test_gajjala_latency_2026_11_09.py pins it.

ROWS: every LIVE `GG:` claim in state "pushed" (no `SHADOW:GG:`, no `GG1:` / `GGA:`, no `#state` refusal row). Lane
fields come from the lane doc of the same `_id`; an unfilled / skipped doc serves "—" for Ordered / Filled but still
counts in Read / Rang; no `order_source` on an ordered doc = "tick".

NUMBERS: percentiles = numpy linear interpolation (the numpy default — pinned on a 5-value fixture). The before / since
split at GG_LIVE_FROM carries a seeded bootstrap 95% interval of the p50 difference; under LATENCY_CI_MIN_N on a side, no
interval (the words say so). No placebo: a timing, not an outcome. Every served number carries its n. Every served
string is composed here; the frontend prints them verbatim. The script scripts/gajjala_latency_report.py prints the SAME
`payload()` (a test pins equality).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import numpy as np

from trading import gajjala_stream as _GS

from . import bar_close as _BC
from . import constants as GC

log = logging.getLogger(__name__)

# ── OWNER NUMBERS (MINE — transport / statistics, never a rule) ─────────────────────────────────────────────────────
GG_LIVE_FROM: Optional[str] = "2026-11-10"   # MINE — the ISO date of the first P1/P2 behavior switch; the main session sets it
#                                          at that deploy. None = no split (one row for the whole span). Set 2026-11-09 by the
#                                          main session: 2026-11-10 = the first full session after the GG LIVE deploy (MINE).
LATENCY_BOOT_N = 2000                    # MINE — bootstrap resamples of the p50 difference (spec §3.6)
LATENCY_BOOT_SEED = 7                    # MINE — the seed (deterministic interval; spec §3.6)
LATENCY_CI_MIN_N = 5                     # MINE — fewer than this on a side → no interval (spec §3.6 "n < 5 → no CI")
LATENCY_CI_LEVEL = 95.0                  # MINE — the interval's coverage (spec §3.6 "95% CI")

# ── collections (read only) ─────────────────────────────────────────────────────────────────────────────────────
ALERTS_COLL = "gajjala_alerts"           # = chart_maps.gajjala.store.ALERTS (test pins equality)
STREAM_COLL = _GS.STREAM_COLL            # spec §3.3 — trading/gajjala_stream.py writes it (imported, never retyped)
BAR_FINAL_COLL = _BC.COLL                # spec §3.4 — chart_maps/gajjala/bar_close.py writes it (imported, never retyped)
LIVE_PREFIX = "GG:"                      # = variant GG5.claim_prefix + ":" (test pins equality)
PUSHED = "pushed"

# ── served words (spec §3.6, fixed) ─────────────────────────────────────────────────────────────────────────────
TITLE = "⏱ Speed — seconds after the 5-minute bar closed"
COLUMNS = (("read", "Read"), ("ring", "Rang"), ("seen", "Lane saw"), ("order", "Ordered"), ("fill", "Filled"))
STEPS = ("read", "ring", "seen", "order", "fill", "broker", "would_seen", "would_order")
FOOTNOTE = "From the alert and lane records: p50 · p90 (n). A timing, not a result."
PLACEBO_TEXT = "No placebo — a timing, not an outcome."
EMPTY_TEXT = "No 🚩 A+ rang in this span."
BEFORE_LABEL = "before {date}"
SINCE_LABEL = "since {date}"
CHECK_TITLE = "Stream vs 1-minute check — same outcome {a} · different {d}"
FINALITY_TEXT = ("Bar finality: {c} of {n} closed 5-minute bars changed between 30 s and 60 s after close "
                 "(volume on {v}).")
DASH = "—"
CI_TEXT = "{label}: p50 {diff} s since {date} (95% interval {lo} to {hi}; n {nb} before · {ns} since)"
NO_CI_TEXT = "{label}: fewer than {k} on a side — no interval (n {nb} before · {ns} since)"
ENTRY_DELTA_TEXT = "1-minute fill vs the stream's trigger print: p50 {p50} R · p90 {p90} R ({n})"
ODD_LOT_TEXT = "Trigger seen only on an odd-lot print: {k} of {n}"

# stream-vs-minute (spec §3.6 / §3.7): stream side, tick side, the agreeing pairs, then the disagreements in list order
STREAM_SIDES = ("trigger", "stop", "none")
TICK_SIDES = ("ordered", "never_triggered", "missed", "other_skip", "expired")
AGREE = (("trigger", "ordered"), ("stop", "never_triggered"), ("none", "expired"))
STREAM_WORDS = {"trigger": "stream: trigger print first", "stop": "stream: stop print first",
                "none": "stream: no trigger or stop print"}
TICK_WORDS = {"ordered": "1-minute: ordered", "never_triggered": "1-minute: the stop printed first",
              "missed": "1-minute: missed", "other_skip": "1-minute: skipped",
              "expired": "1-minute: never traded the trigger by the cut-off"}
FINALITY_PARTS = (("regular", "Regular hours"), ("extended", "Extended hours"))


# ── IO seam (the lane's own; tests patch exit_engine._db) ───────────────────────────────────────────────────────
def _coll(name: str):
    from trading import gajjala_entry as GE
    return GE._coll(name)


def _find(coll, q: dict) -> list:
    if coll is None:
        return []
    try:
        return [dict(d) for d in coll.find(q)]
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala latency: read failed: %s", type(exc).__name__)
        return []


# ── clocks (ONE parser each — gajjala_entry's) ──────────────────────────────────────────────────────────────────
def close_of(entry_bar_t) -> Optional[datetime]:
    """The entry bar's close: `entry_bar_t` is naive ET, its RIGHT label — never + the frame's minutes (C4)."""
    from trading import gajjala_entry as GE
    return GE._parse_et(entry_bar_t)


def _utc(v) -> Optional[datetime]:
    from trading import gajjala_entry as GE
    return GE._parse(v)


def _secs(t, close: Optional[datetime]) -> Optional[float]:
    d = _utc(t)
    if d is None or close is None:
        return None
    return (d - close).total_seconds()


# ── statistics ──────────────────────────────────────────────────────────────────────────────────────────────────
def pct(xs, q: float) -> Optional[float]:
    """numpy linear-interpolation percentile (q in 0..100); None on no data."""
    vals = [float(x) for x in xs if x is not None]
    if not vals:
        return None
    return float(np.percentile(np.asarray(vals, dtype=float), q))


def _r1(x) -> Optional[float]:
    return None if x is None else round(float(x), 1)


def _num(x, nd: int = 1) -> str:
    return DASH if x is None else f"{float(x):,.{nd}f}"


def _signed(x, nd: int = 1) -> str:
    return DASH if x is None else f"{float(x):+,.{nd}f}"


def step_stats(xs) -> dict:
    vals = [float(x) for x in xs if x is not None]
    return {"n": len(vals), "p50": _r1(pct(vals, 50)), "p90": _r1(pct(vals, 90)),
            "min": _r1(min(vals)) if vals else None, "max": _r1(max(vals)) if vals else None}


def cell_text(st: dict) -> str:
    if not st.get("n"):
        return DASH
    return f"{_num(st['p50'])} · {_num(st['p90'])} ({st['n']})"


def boot_ci(before, since) -> Optional[dict]:
    """Seeded bootstrap of p50(since) − p50(before); None when a side has fewer than LATENCY_CI_MIN_N values."""
    a = np.asarray([float(x) for x in before if x is not None], dtype=float)
    b = np.asarray([float(x) for x in since if x is not None], dtype=float)
    if len(a) < LATENCY_CI_MIN_N or len(b) < LATENCY_CI_MIN_N:
        return None
    rng = np.random.default_rng(LATENCY_BOOT_SEED)
    ia = rng.integers(0, len(a), size=(LATENCY_BOOT_N, len(a)))
    ib = rng.integers(0, len(b), size=(LATENCY_BOOT_N, len(b)))
    d = np.percentile(b[ib], 50, axis=1) - np.percentile(a[ia], 50, axis=1)
    tail = (100.0 - LATENCY_CI_LEVEL) / 2.0
    return {"diff": _r1(np.percentile(b, 50) - np.percentile(a, 50)), "lo": _r1(np.percentile(d, tail)),
            "hi": _r1(np.percentile(d, 100.0 - tail))}


# ── span ────────────────────────────────────────────────────────────────────────────────────────────────────────
def span_key(span) -> str:
    return span if span in GC.LEDGER_SPANS else GC.LEDGER_SPAN_DEFAULT


def span_days(span_k: str, session: date) -> Optional[list]:
    """ISO dates of the span (the 🏁's own calendar, ledger._sessions_for); None = "all" (no date bound)."""
    if span_k == "all":
        return None
    from . import ledger as LG
    return [d.isoformat() for d in LG._sessions_for(span_k, session, None)]


def _today_et(now: Optional[datetime]) -> date:
    from trading import gajjala_entry as GE
    return GE._as_et(now).date()


# ── reads ───────────────────────────────────────────────────────────────────────────────────────────────────────
def is_live_row(a: dict) -> bool:
    """A LIVE `GG:` claim that reached the phone: `GG:` prefix (never SHADOW:GG: / GG1: / GGA:), no `#state` refusal
    suffix, state "pushed"."""
    _id = str(a.get("_id") or "")
    return _id.startswith(LIVE_PREFIX) and "#" not in _id and a.get("state") == PUSHED


def read_alerts(days: Optional[list]) -> list:
    q: dict = {"_id": {"$gte": LIVE_PREFIX, "$lt": LIVE_PREFIX[:-1] + chr(ord(LIVE_PREFIX[-1]) + 1)}, "state": PUSHED}
    if days is not None:
        q["date"] = {"$in": list(days)}
    return [a for a in _find(_coll(ALERTS_COLL), q) if is_live_row(a)]


def read_lane(ids: list) -> dict:
    from trading import gajjala_entry as GE
    if not ids:
        return {}
    return {d["_id"]: d for d in _find(_coll(GE.LANE_COLL), {"_id": {"$in": list(ids)}}) if "_id" in d}


def read_stream(ids: list) -> dict:
    """{doc_id: {event: row}} from the stream's insert-once rows (`_id` = "{doc_id}|{event}")."""
    out: dict = {}
    if not ids:
        return out
    for r in _find(_coll(STREAM_COLL), {"doc_id": {"$in": list(ids)}}):
        did, ev = r.get("doc_id"), r.get("event")
        if did and ev:
            out.setdefault(did, {})[ev] = r
    return out


def read_bar_final(days: Optional[list]) -> list:
    q: dict = {} if days is None else {"date": {"$in": list(days)}}
    return _find(_coll(BAR_FINAL_COLL), q)


# ── rows ────────────────────────────────────────────────────────────────────────────────────────────────────────
_NO_ORDER_STATES = ("unfilled", "skipped")


def build_row(a: dict, lane: Optional[dict], stream: Optional[dict]) -> Optional[dict]:
    close = close_of(a.get("entry_bar_t"))
    if close is None:
        return None
    d = lane or {}
    s = stream or {}
    no_order = d.get("state") in _NO_ORDER_STATES
    order = None if no_order else _secs(d.get("ordered_at"), close)
    fill = None if no_order else _secs(d.get("fill_t"), close)
    o, f = _utc(d.get("ordered_at")), _utc(d.get("fill_t"))
    broker = (f - o).total_seconds() if (not no_order and o is not None and f is not None) else None
    ordered = order is not None
    trig, seen_row = s.get("trigger") or {}, s.get("seen") or {}
    row = {"id": a.get("_id"), "symbol": a.get("symbol"), "setup": a.get("setup"), "date": a.get("date"),
           "frame": a.get("frame"), "entry_bar_t": a.get("entry_bar_t"), "close_et": close.strftime("%H:%M:%S"),
           "_close": close,
           "read": _secs(a.get("at"), close), "ring": _secs(a.get("claimed_at"), close),
           "seen": _secs(d.get("first_seen"), close), "order": order, "fill": fill, "broker": broker,
           "lane_state": d.get("state"), "source": (d.get("order_source") or "tick") if ordered else None,
           "enter_ms": d.get("enter_ms") if ordered else None,
           "would_seen": _secs(seen_row.get("recv_t"), close), "would_order": _secs(trig.get("recv_t"), close),
           "print_lag_ms": trig.get("lag_ms")}
    row["cells"] = [{"key": k, "text": _num(row[k])} for k, _l in COLUMNS]
    return row


def _served_row(r: dict) -> dict:
    out = {k: v for k, v in r.items() if k != "_close"}
    for k in STEPS:
        out[k] = _r1(out.get(k))
    return out


def _summary(rows: list, label: str, side: str) -> dict:
    steps = {k: step_stats([r[k] for r in rows]) for k in STEPS}
    return {"label": label, "side": side, "n": len(rows), "steps": steps,
            "cells": [{"key": k, "text": cell_text(steps[k]), "line": f"{lbl}: {cell_text(steps[k])}"}
                      for k, lbl in COLUMNS]}


# ── stream vs 1-minute check ────────────────────────────────────────────────────────────────────────────────────
def tick_terminal(d: dict) -> Optional[str]:
    """The 1-minute tick's terminal state of a lane doc; None while it is still open (waiting / no doc).
    `unfilled`+`never_triggered` WITH a `last` = the tick saw the stop print (`_try_waiting` writes `last`); WITHOUT
    one = the cut-off expired it (`_expire_waiting` writes no `last`)."""
    from trading import gajjala_entry as GE
    st, kind = d.get("state"), d.get("skip_kind")
    if st in GE._DAY_STATES:
        return "ordered"
    if st == "unfilled" and kind == "never_triggered":
        return "never_triggered" if d.get("last") is not None else "expired"
    if st == "skipped" and kind == "missed":
        return "missed"
    if st in ("skipped", "unfilled", "dry_run"):
        return "other_skip"
    return None


def stream_first(events: dict) -> str:
    best, best_t = "none", None
    for ev in ("trigger", "stop"):
        r = events.get(ev)
        if not r:
            continue
        t = _utc(r.get("print_t"))
        if t is None:
            continue
        if best_t is None or t < best_t:
            best, best_t = ev, t
    return best


def check_block(rows: list, lane: dict, stream: dict) -> Optional[dict]:
    ids = [r["id"] for r in rows if r["id"] in stream]
    if not ids:
        return None
    counts: dict = {}
    deltas, trig_docs, odd_only = [], 0, 0
    for did in ids:
        ev = stream[did]
        if "trigger" in ev:
            trig_docs += 1
            if ev["trigger"].get("odd_lot") is True and "trigger_lot" not in ev:
                odd_only += 1
        d = lane.get(did) or {}
        tt = tick_terminal(d)
        if tt is None:
            continue
        sf = stream_first(ev)
        counts[(sf, tt)] = counts.get((sf, tt), 0) + 1
        if tt == "ordered" and (d.get("order_source") or "tick") == "tick" and "trigger" in ev:
            fp, pp = d.get("fill_px"), ev["trigger"].get("print_px")
            tg, sp = d.get("trigger"), d.get("stop")
            try:
                risk = float(tg) - float(sp)
                if fp is not None and pp is not None and risk > 0:
                    deltas.append((float(fp) - float(pp)) / risk)
            except (TypeError, ValueError):
                pass
    order = list(AGREE) + [(s, t) for t in TICK_SIDES for s in STREAM_SIDES if (s, t) not in AGREE]
    pairs = [{"stream": s, "tick": t, "agree": (s, t) in AGREE, "n": counts[(s, t)],
              "text": f"{STREAM_WORDS[s]} · {TICK_WORDS[t]} ({counts[(s, t)]})"}
             for s, t in order if counts.get((s, t))]
    a = sum(p["n"] for p in pairs if p["agree"])
    dd = sum(p["n"] for p in pairs if not p["agree"])
    p50, p90 = pct(deltas, 50), pct(deltas, 90)
    ed = {"n": len(deltas), "p50": None if p50 is None else round(p50, 2), "p90": None if p90 is None else round(p90, 2)}
    ed["text"] = ENTRY_DELTA_TEXT.format(p50=_signed(ed["p50"], 2), p90=_signed(ed["p90"], 2), n=ed["n"])
    return {"title": CHECK_TITLE.format(a=a, d=dd), "same": a, "different": dd, "n": a + dd, "pairs": pairs,
            "entry_delta_r": ed,
            "odd_lot_only": {"n": trig_docs, "k": odd_only, "text": ODD_LOT_TEXT.format(k=odd_only, n=trig_docs)}}


# ── bar finality (P2 probe rows) ────────────────────────────────────────────────────────────────────────────────
def _v_changed(r: dict) -> bool:
    fc = r.get("fields_changed") or []
    if "v" in fc or "volume" in fc:
        return True
    try:
        return float(r.get("v_delta") or 0) != 0
    except (TypeError, ValueError):
        return False


def _v_ratio(r: dict) -> Optional[float]:
    v = (r.get("at60") or {}).get("v")
    try:
        v, dv = float(v), float(r.get("v_delta"))
    except (TypeError, ValueError):
        return None
    return abs(dv) / v * 100.0 if v > 0 else None


def _finality_counts(rows: list) -> dict:
    n = len(rows)
    c = sum(1 for r in rows if r.get("changed") is True)
    v = sum(1 for r in rows if _v_changed(r))
    p90 = pct([_v_ratio(r) for r in rows], 90)
    return {"n": n, "changed": c, "v_changed": v, "v_delta_p90_pct": _r1(p90),
            "text": FINALITY_TEXT.format(c=c, n=n, v=v)}


def finality_block(rows: list) -> Optional[dict]:
    if not rows:
        return None
    out = _finality_counts(rows)
    parts = []
    for key, label in FINALITY_PARTS:
        sub = [r for r in rows if (r.get("session_part") or "regular") == key]
        if sub:
            p = _finality_counts(sub)
            p.update(part=key, label=label, text=f"{label} — {p['text']}")
            parts.append(p)
    out["parts"] = parts
    return out


# ── the served block ────────────────────────────────────────────────────────────────────────────────────────────
def _span_label(k: str) -> str:
    from . import ledger as LG
    return LG._span_label(k)


_FROM_CONST = object()


def live_from_of(v) -> Optional[str]:
    """The split date as an ISO "YYYY-MM-DD", or None (no split). An unusable value (not an ISO date string) is no split
    — logged, never a raise."""
    if v is None:
        return None
    try:
        if not isinstance(v, str):
            raise ValueError(type(v).__name__)
        return date.fromisoformat(v.strip()).isoformat()
    except ValueError as exc:
        log.warning("gajjala latency: GG_LIVE_FROM %r is not an ISO date (%s) — no split", v, exc)
        return None


def payload(span: Optional[str] = None, now: Optional[datetime] = None, live_from=_FROM_CONST) -> dict:
    """The ⏱ block (GET /trading/gajjala/latency and scripts/gajjala_latency_report.py — ONE function). Never raises on a
    read fault (a failed read = no rows). `live_from` defaults to GG_LIVE_FROM (tests pass a date or None)."""
    lf = live_from_of(GG_LIVE_FROM if live_from is _FROM_CONST else live_from)
    span_k = span_key(span)
    days = span_days(span_k, _today_et(now))
    alerts = read_alerts(days)
    ids = [a["_id"] for a in alerts]
    lane, stream = read_lane(ids), read_stream(ids)
    rows = [r for r in (build_row(a, lane.get(a["_id"]), stream.get(a["_id"])) for a in alerts) if r is not None]
    rows.sort(key=lambda r: str(r["symbol"] or ""))
    rows.sort(key=lambda r: r["_close"], reverse=True)          # close descending, then symbol (§3.7)
    summary, ci = [], []
    if rows:
        if lf:
            before = [r for r in rows if str(r["date"] or "") < lf]
            since = [r for r in rows if str(r["date"] or "") >= lf]
            summary = [_summary(before, BEFORE_LABEL.format(date=lf), "before"),
                       _summary(since, SINCE_LABEL.format(date=lf), "since")]
            for k, lbl in COLUMNS:
                xb = [r[k] for r in before if r[k] is not None]
                xs = [r[k] for r in since if r[k] is not None]
                c = boot_ci(xb, xs)
                if c is None:
                    text = NO_CI_TEXT.format(label=lbl, k=LATENCY_CI_MIN_N, nb=len(xb), ns=len(xs))
                    ci.append({"key": k, "label": lbl, "n_before": len(xb), "n_since": len(xs), "diff": None,
                               "lo": None, "hi": None, "text": text})
                else:
                    text = CI_TEXT.format(label=lbl, diff=_signed(c["diff"]), date=lf, lo=_signed(c["lo"]),
                                          hi=_signed(c["hi"]), nb=len(xb), ns=len(xs))
                    ci.append(dict(c, key=k, label=lbl, n_before=len(xb), n_since=len(xs), text=text))
        else:
            summary = [_summary(rows, _span_label(span_k), "all")]
    from . import ledger as LG
    return {"title": TITLE, "span": span_k, "spans": [{"key": k, "label": LG._span_label(k)} for k in GC.LEDGER_SPANS],
            "days": days, "live_from": lf, "columns": [{"key": k, "label": lbl} for k, lbl in COLUMNS],
            "n_alerts": len(rows), "summary": summary, "ci": ci, "footnote": FOOTNOTE, "placebo_text": PLACEBO_TEXT,
            "empty_text": None if rows else EMPTY_TEXT,
            "rows": [_served_row(r) for r in rows],
            "check": check_block(rows, lane, stream),
            "finality": finality_block(read_bar_final(days))}


__all__ = ["payload", "close_of", "pct", "step_stats", "boot_ci", "tick_terminal", "stream_first", "check_block",
           "finality_block", "build_row", "is_live_row", "live_from_of", "GG_LIVE_FROM", "LATENCY_BOOT_N", "LATENCY_BOOT_SEED",
           "LATENCY_CI_MIN_N", "TITLE", "COLUMNS", "FOOTNOTE", "EMPTY_TEXT", "CHECK_TITLE", "FINALITY_TEXT"]
