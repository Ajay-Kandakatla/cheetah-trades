"""🧘 GG-like — the tracking half (2026-11-27, spec gg-like rev 2 §3.7, WP `be-track`).

Ajay 2026-11-27 ~00:15 ET, verbatim: "Yes please, I think we are in bear market and looking at bad setups and make them
work, forcing them to work honestly... Can you update them please.. find calmer and better setups.. Continue to track
the runners we might evolve and find patterns in the current runners too but I want to make sure we are finding similar
setups to Gajjala".

WHAT. The 🧘 block (gg_like.py) is frozen on every A+ claim and every 🧠 push WHEN IT RANG (the 📶 precedent); the
🏁 row prints it (`ledger.alert_of` → `ledger._gg_like_stamp`). This module:
  * `stamp_of` — the row's ring stamp first ("ring"); else a block the nightly wrote on the row's ledger doc
    ("computed_later" — older A+ rings whose stored end-of-day read still describes the claim);
  * `ring_facts` / `split` / `split_block` — the 🏁 fold: counts and R sums of the RING-STAMPED rings only, per kind ×
    setup × group — never a mean, a rate, a rank, a pooled line or a cell that mixes two setups or two sources [C2, C6];
    "computed later" is ONE counts-only line that says why it is not a fair sample (a name that kept moving had its read
    overwritten — the rings left are the ones that did NOT move on);
  * `record_night` — the 20:15 nightly (one fence between 🩳 and 📅): ONLY on a ring-stamped A+ row, his +30% from the
    trigger (`runseat.from_trigger`, the ONE engine) — written through
    `store.annotate_ledger` (no upsert: a row with no graded ledger doc is skipped, never created [C8]); a stored `win30`
    dict is FINAL, a split verdict included. The "computed later" block on an older A+ row is written ONLY with
    `later=True` — the one-time `--once --later` run on his go (HIS CALL #11); the nightly never passes it, so with no go
    the record starts clean with the ring stamps.
UNMEASURED accounting — not a test. Observed on GG's example charts, not his rule. Nothing here gates, rings or orders.
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from datetime import datetime, timezone
from typing import Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as L

log = logging.getLogger("chart_maps.gajjala.gg_like_track")

UTC = timezone.utc
SOURCES = ("read", "ring", "computed_later")           # == gg_like.SOURCES (a test pins it)
GROUPS = ("gg_like", "not", "unknown", "none")          # the three verdicts + "no block at all"
OUTCOMES = ("win", "loss", "open")                      # the same-session column's outcomes
COUNT_KEYS = ("rows", "no_ledger_doc", "later", "later_no_match", "win30", "win30_split", "split_unchecked", "not_due",
              "load_failed", "deferred_cap", "written", "write_failed")

# ── served words (all MINE; the pass word itself is gg_like.CHIP_OK — HIS CALL #6) ───────────────────────────────────
KIND_WORD = {"aplus": "🎯 A+", "potential": "🧠 armed"}
UNKNOWN_WORD = "can't tell"
RING_LINE = "{kind} · {emoji} {label} · {group}: {rings}"
WIN30_CLAUSE = "{w} of {m} ran +{pct}% from the trigger"
FILLED_CLAUSE = "{filled} filled — {won} +{M}R, {stopped} stopped, {open} open"
R_CLAUSE = "{gross:+.2f}R before costs, {net:+.2f}R after"
STOP_CLAUSE = "stop {med:.1f}% wide (median)"
NONE_LINE = "No check on file: {a} A+ · {b} 🧠"
LATER_LINE = ("Older A+ rings checked later from the stored read ({k} of {t} still matched): {like} {a} · not {like} {b} "
              "· {unk} {c} — counts only. A name that kept moving had its read overwritten, so the rings left here are "
              "the ones that did NOT move on: not a fair sample, and no result is printed for them.")
NO_RING_LINE = "No ring carries a frozen check yet — it is stamped on every ring from the day this shipped."
TITLE_TAIL = " vs not — UNMEASURED: counts of the rings as they rang, setup by setup; not a test, no rate, no rank"
NOTE = ("Winner = your 11-26 rule: +{pct}% above the A+ trigger, same session to {end} ET. R = GG's trade math on the same "
        "session (+{M}R, the stop, or the close); after costs = less {bps} + ${slip} a share per side. Thin-R rows and "
        "duplicates are out of the R sums. Setups are never added together: the stop width differs by setup, and costs "
        "in R grow as the stop tightens. No average is printed — too few rings for one.")


def _GL():
    from chart_maps.gajjala import gg_like as GL               # lazy: the engine imports tab lazily too
    return GL


def _num(x) -> Optional[float]:
    return L._num(x)


def _like_word() -> str:
    """The pass word without its glyph — built from gg_like.CHIP_OK (the ONE place it is typed)."""
    return str(_GL().CHIP_OK).replace("🧘", "").strip()


def _group_word(g: str) -> str:
    like = _like_word()
    return {"gg_like": like, "not": f"not {like}", "unknown": UNKNOWN_WORD}.get(g, g)


def _pct_cut():
    from chart_maps.gajjala_watch import constants as WC
    return WC.RUNNERS_SEAT_APLUS_PCT


# ── the stamp ────────────────────────────────────────────────────────────────────────────────────────────────────
def _valid(raw) -> Optional[dict]:
    if raw is None:
        return None
    try:
        blk = _GL().from_stamp(raw)
    except Exception:                                           # noqa: BLE001
        return None
    return blk if isinstance(blk, dict) else None


def stamp_of(row: dict, ledger_doc: Optional[dict]) -> tuple:
    """(block | None, source | None): the row's ring stamp first (`row["gg_like"]`, frozen when it rang → "ring"); else
    the ledger doc's block, ONLY when the nightly wrote it (`source` "computed_later" on the stored dict). A ring stamp is
    never shadowed by a later block."""
    ring = _valid((row or {}).get("gg_like") if isinstance(row, dict) else None)
    if ring is not None:
        return ring, SOURCES[1]
    raw = (ledger_doc or {}).get("gg_like") if isinstance(ledger_doc, dict) else None
    if isinstance(raw, dict) and raw.get("source") == SOURCES[2]:
        later = _valid(raw)
        if later is not None:
            return later, SOURCES[2]
    return None, None


def later_block(row: dict, read_doc: Optional[dict]) -> Optional[dict]:
    """A+ rows only. `row` = the ledger row WITH the claim's `entry_bar_t` and `frame` (record_night adds them from the
    claim doc). The stored read of (date, SYM, setup) must have broke True AND entry_bar_t, frame, trigger, stop equal
    to the claim's; then gg_like.doc_blocks(read_doc)[setup] (whose entry_bar_t must be the claim's too); else None."""
    if not isinstance(row, dict) or row.get("kind") != L.KINDS[1] or not isinstance(read_doc, dict):
        return None
    setup = row.get("setup")
    r = (read_doc.get("setups") or {}).get(setup) if isinstance(read_doc.get("setups"), dict) else None
    if not isinstance(r, dict) or r.get("broke") is not True:
        return None
    ebt = row.get("entry_bar_t")
    if not isinstance(ebt, str) or not ebt or r.get("entry_bar_t") != ebt:
        return None
    if not isinstance(row.get("frame"), str) or r.get("frame") != row.get("frame"):
        return None
    for k in ("trigger", "stop"):
        a, b = _num(row.get(k)), _num(r.get(k))
        if a is None or b is None or L._D(a) != L._D(b):
            return None
    try:
        blk = (_GL().doc_blocks(read_doc) or {}).get(setup)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gg_like_track: doc_blocks failed for %s: %s", row.get("id"), type(exc).__name__)
        return None
    if not isinstance(blk, dict) or blk.get("entry_bar_t") != ebt:
        return None
    return blk


def win30_of(ledger_doc: Optional[dict]) -> Optional[bool]:
    """The stored +30% verdict: True / False when the day was measured, else None (a split, no bars, nothing stored)."""
    w = (ledger_doc or {}).get("win30") if isinstance(ledger_doc, dict) else None
    if not isinstance(w, dict) or w.get("measured") is not True or not isinstance(w.get("passed"), bool):
        return None
    return w["passed"]


# ── R (GG's trade math, the same-session column) [C6] ─────────────────────────────────────────────────────────────
def _exit_of(row: dict, same: Optional[dict]) -> Optional[tuple]:
    """(e, x, r) or None — None unless the same column FILLED (not a split, not provisional), the plan is ok, not thin."""
    if not isinstance(row, dict) or not isinstance(same, dict):
        return None
    if row.get("plan") != L.PLANS[0] or row.get("thin") is True:
        return None
    if same.get("entry") != L.ENTRIES[0] or same.get("reason") == "split" or same.get("provisional") is True:
        return None
    e, r = _num(same.get("fill_px")), _num(row.get("r"))
    if e is None or e <= 0 or r is None or r <= 0:
        return None
    out = same.get("outcome")
    if out == OUTCOMES[0]:
        x = _num(same.get("target_px"))
    elif out == OUTCOMES[1]:
        x = _num(row.get("stop"))
    elif out == OUTCOMES[2]:
        cp = _num(same.get("close_pct"))
        x = e * (1 + cp / 100) if cp is not None else None
    else:
        x = None
    if x is None or x <= 0:
        return None
    return e, x, r


def r_gross(row: dict, same: Optional[dict]) -> Optional[float]:
    """(x − e) / R, rounded 2 — x = the target on a win, the stop on a loss, the close on an open trade."""
    got = _exit_of(row, same)
    if got is None:
        return None
    e, x, r = got
    return round((x - e) / r, 2)


def r_after_costs(row: dict, same: Optional[dict]) -> Optional[float]:
    """The same trade less costs: (divergence.net_pct(x, e) / 100 × e) / R, rounded 2 — the ONE in-app cost function."""
    got = _exit_of(row, same)
    if got is None:
        return None
    from chart_maps.gajjala import divergence as DV
    e, x, r = got
    return round((DV.net_pct(x, e) / 100 * e) / r, 2)


# ── the facts and the split ──────────────────────────────────────────────────────────────────────────────────────
def ring_facts(row: dict, same: Optional[dict], ledger_doc: Optional[dict], *, provisional: bool = False,
               dup: bool = False) -> dict:
    """One ring's neutral facts. A provisional same column (today's not-final read) counts the ring but no fill, no
    outcome and no R. `win30` is read ONLY for an A+ ring whose source is "ring" [C2]."""
    blk, src = stamp_of(row, ledger_doc)
    kind = (row or {}).get("kind")
    final = isinstance(same, dict) and not provisional and same.get("provisional") is not True
    filled = bool(final and same.get("entry") == L.ENTRIES[0] and same.get("reason") != "split")
    outcome = same.get("outcome") if filled and same.get("outcome") in OUTCOMES else None
    return {"kind": kind, "setup": (row or {}).get("setup"),
            "group": blk.get("verdict") if blk is not None and blk.get("verdict") in GROUPS[:3] else GROUPS[3],
            "source": src, "counted": not dup, "filled": filled, "outcome": outcome,
            "thin": bool((row or {}).get("thin")), "r_pct": _num((row or {}).get("r_pct")),
            "r_gross": None if provisional else r_gross(row, same),
            "r_net": None if provisional else r_after_costs(row, same),
            "win30": win30_of(ledger_doc) if kind == L.KINDS[1] and src == SOURCES[1] else None}


def _cell() -> dict:
    return {"n": 0, "win30_yes": 0, "win30_n": 0, "filled": 0, "won": 0, "stopped": 0, "open": 0, "r_gross_sum": 0.0,
            "r_net_sum": 0.0, "r_n": 0, "r_pct_median": None, "_pcts": []}


def split(facts: list) -> dict:
    """Three DISJOINT parts, nothing pooled across setups [C2, C6]:
    cells[(kind, setup, group)] — ring-stamped AND counted facts only; later[(setup, group)] — "computed later" counts;
    none[kind] — rings with no block at all. `later_total` = A+ rings with no ring stamp. No mean, no rate, no rank."""
    cells: dict = {}
    later: dict = {}
    none: dict = {}
    later_total = 0
    for f in facts or []:
        if not isinstance(f, dict):
            continue
        kind, src = f.get("kind"), f.get("source")
        if kind == L.KINDS[1] and src != SOURCES[1]:
            later_total += 1
        if src == SOURCES[1]:
            if not f.get("counted"):
                continue
            c = cells.setdefault((kind, f.get("setup"), f.get("group")), _cell())
            c["n"] += 1
            if f.get("win30") is not None:
                c["win30_n"] += 1
                c["win30_yes"] += 1 if f["win30"] is True else 0
            if f.get("filled"):
                c["filled"] += 1
                o = f.get("outcome")
                if o in OUTCOMES:
                    c[{"win": "won", "loss": "stopped", "open": "open"}[o]] += 1
            if f.get("r_gross") is not None and f.get("r_net") is not None:
                c["r_gross_sum"] += f["r_gross"]
                c["r_net_sum"] += f["r_net"]
                c["r_n"] += 1
            if f.get("r_pct") is not None:
                c["_pcts"].append(f["r_pct"])
        elif src == SOURCES[2]:
            k = (f.get("setup"), f.get("group"))
            later.setdefault(k, {"n": 0})["n"] += 1
        else:
            none.setdefault(kind, {"n": 0})["n"] += 1
    for c in cells.values():
        pcts = c.pop("_pcts")
        c["r_pct_median"] = statistics.median(pcts) if pcts else None
        c["r_gross_sum"] = round(c["r_gross_sum"], 2)
        c["r_net_sum"] = round(c["r_net_sum"], 2)
    return {"cells": cells, "later": later, "none": none, "later_total": later_total}


def _setup_order(keys) -> list:
    known = [s for s in GC.SETUPS if s in keys]
    return known + sorted(str(s) for s in keys if s not in GC.SETUPS)


def split_block(facts: list) -> dict:
    """The served 🏁 fold {label, title, lines, note}. A cell with n = 0 prints nothing; a clause whose base is 0 is
    dropped. 🎯 A+ first, then 🧠 armed; setups in GC.SETUPS order; groups GG-like, not, can't tell."""
    from chart_maps.gajjala import alerts as AL
    GL = _GL()
    s = split(facts)
    pct = _pct_cut()
    lines = []
    for kind in (L.KINDS[1], L.KINDS[0]):
        setups = _setup_order({k[1] for k in s["cells"] if k[0] == kind})
        for setup in setups:
            for group in GROUPS[:3]:
                c = s["cells"].get((kind, setup, group))
                if not c or c["n"] <= 0:
                    continue
                emoji, label = AL.SETUP_META.get(setup, ("", str(setup)))
                parts = [RING_LINE.format(kind=KIND_WORD.get(kind, kind), emoji=emoji, label=label,
                                          group=_group_word(group), rings=L._plural(c["n"], "ring", "rings"))]
                if kind == L.KINDS[1] and c["win30_n"] > 0:
                    parts.append(WIN30_CLAUSE.format(w=c["win30_yes"], m=c["win30_n"], pct=pct))
                if c["filled"] > 0:
                    parts.append(FILLED_CLAUSE.format(filled=c["filled"], won=c["won"], M=L._m(), stopped=c["stopped"],
                                                      open=c["open"]))
                if c["r_n"] > 0:
                    parts.append(R_CLAUSE.format(gross=c["r_gross_sum"], net=c["r_net_sum"]))
                if c["r_pct_median"] is not None:
                    parts.append(STOP_CLAUSE.format(med=c["r_pct_median"]))
                lines.append(" · ".join(parts))
    if not s["cells"]:
        lines.append(NO_RING_LINE)
    a = (s["none"].get(L.KINDS[1]) or {}).get("n", 0)
    b = (s["none"].get(L.KINDS[0]) or {}).get("n", 0)
    if a or b:
        lines.append(NONE_LINE.format(a=a, b=b))
    if s["later"]:
        by = {g: sum(v["n"] for (st_, gg), v in s["later"].items() if gg == g) for g in GROUPS[:3]}
        lines.append(LATER_LINE.format(k=sum(v["n"] for v in s["later"].values()), t=s["later_total"],
                                       like=_like_word(), unk=UNKNOWN_WORD, a=by["gg_like"], b=by["not"],
                                       c=by["unknown"]))
    from daytrading.data import ET_AFTERHOURS_CLOSE
    note = NOTE.format(pct=pct, end=ET_AFTERHOURS_CLOSE.strftime("%H:%M"), M=L._m(),
                       bps=f"{GC.DIVERGENCE_COST_BPS * 100:.2f}%", slip=f"{GC.DIVERGENCE_SLIP_USD:.2f}")
    return {"label": f"{GL.CHIP_OK} vs not", "title": f"{GL.CHIP_OK}{TITLE_TAIL}", "lines": lines, "note": note}


# ── the night ────────────────────────────────────────────────────────────────────────────────────────────────────
def _window(now: datetime, sessions: Optional[int]) -> list:
    from chart_maps.gajjala import context as CX
    from chart_maps.gajjala import nightly as NG
    n = int(sessions) if sessions is not None else int(GC.LEDGER_GRADE_LOOKBACK_SESSIONS)
    return CX.history_window(L._next_market_day(NG.default_session(now)), n)


def _claims_by_id(claims: list) -> dict:
    """{ledger id: the claim doc} — the FIRST A+ claim doc that reads as a row (rows_for's own first-wins dedupe)."""
    out: dict = {}
    for d in claims or []:
        try:
            row = L.alert_of(d, L.KINDS[1])
        except Exception:                                       # noqa: BLE001
            row = None
        if row is None or row.get("line") not in L.LINES[:2] or row["id"] in out:
            continue
        out[row["id"]] = d
    return out


def record_night(now, *, store=None, sessions=None, dry=False, load_day=None, split_look=None, cached_at=None,
                 max_loads=None, later=False) -> dict:
    """The nightly 🧘 record over the ledger's own window (GG5). Per A+ row (lines live / shadow):
      0. no graded ledger doc → `no_ledger_doc`, nothing read, nothing written (the grade files it; next night) [C8];
      1. ONLY with `later=True` (the one-time run, his go — HIS CALL #11; the nightly never passes it): no ring stamp and
         no block on its ledger doc → the stored read; a match → `gg_like` (source computed_later). Off → nothing read;
      2. a RING-STAMPED row whose ledger doc holds no `win30` dict (a stored one is FINAL), once its play day ended: the
         split guard as runseat._judge runs it, then the ledger's loader and runseat.from_trigger → `win30` [C2];
      3. one store.annotate_ledger per row with something to write (never an upsert).
    🧠 rows: nothing is written. -> counts (COUNT_KEYS + sessions, read_fault, dry, later_on, loads)."""
    from chart_maps.gajjala_watch import runseat as RS
    from chart_maps.gajjala import store as ST
    now = L._aware(now)
    now_iso = now.isoformat()
    out: dict = {k: 0 for k in COUNT_KEYS}
    out.update(sessions=[], read_fault=False, dry=bool(dry), later_on=bool(later), loads=0)
    st = store if store is not None else ST.default()
    days = _window(now, sessions)
    out["sessions"] = [d.isoformat() for d in days]
    try:
        rows = L.rows_for(days, st)
    except L.LedgerReadError:
        out["read_fault"] = True
        return out
    stored = st.ledger_docs(days)
    claims = st.alert_rows(days)
    if stored is None or claims is None:
        out["read_fault"] = True
        return out
    docs = {d.get("_id"): d for d in stored if isinstance(d, dict) and d.get("_id")}
    by_claim = _claims_by_id(claims)
    cap = int(max_loads) if max_loads is not None else int(GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS)
    load = load_day or L._default_load_day
    look = split_look or RS.split_look(st)
    cached = cached_at or RS._default_cached_at
    memo: dict = {}
    for row in rows:
        if row.get("kind") != L.KINDS[1] or row.get("line") not in L.LINES[:2]:
            continue                                            # 🧠 rows: forward stamps only (HIS CALL #9)
        out["rows"] += 1
        try:
            doc = docs.get(row["id"])
            if not isinstance(doc, dict):
                out["no_ledger_doc"] += 1
                continue
            sets: dict = {}
            ring = _valid(row.get("gg_like"))
            if later is True and ring is None and _valid(doc.get("gg_like")) is None:
                claim = by_claim.get(row["id"]) or {}
                try:
                    rd = st.get_read(row["date"], row["symbol"])
                except Exception:                               # noqa: BLE001
                    rd = None
                blk = later_block(dict(row, entry_bar_t=claim.get("entry_bar_t"), frame=claim.get("frame")), rd)
                if blk is not None:
                    sets["gg_like"] = dict(blk, source=SOURCES[2], computed_at=now_iso)
                    out["later"] += 1
                else:
                    out["later_no_match"] += 1
            if ring is not None and not isinstance(doc.get("win30"), dict):
                w = _win30(row, now, now_iso, st, look, cached, load, memo, cap, out, RS)
                if w is not None:
                    sets["win30"] = w
            if not sets or dry:
                continue
            res = st.annotate_ledger(row["id"], sets)
            if res == "matched":
                out["written"] += 1
            elif res == "unmatched":
                out["no_ledger_doc"] += 1
            else:
                out["write_failed"] += 1
        except Exception as exc:                                # noqa: BLE001
            log.warning("gg_like_track: row %s failed: %s", row.get("id"), type(exc).__name__)
            out["write_failed"] += 1
    return out


def _win30(row, now, now_iso, st, look, cached, load, memo, cap, out, RS) -> Optional[dict]:
    """The +30% verdict of one ring-stamped A+ row, or None (not due / split unchecked / load failed / capped — retried
    next night). A day that was loaded answers a FINAL dict, whatever `measured` says."""
    from chart_maps.gajjala_watch import constants as WC
    d = L._as_date(row.get("date"))
    at = row.get("at_utc") if isinstance(row.get("at_utc"), datetime) else None
    t = _num(row.get("trigger"))
    if d is None or at is None or t is None or t <= 0:
        m = RS.from_trigger([], d, at, row.get("trigger"))     # aplus_no_time / aplus_no_trigger: nothing to load
        out["win30"] += 1
        return dict({k: m.get(k) for k in RS.FROM_TRIGGER_KEYS}, min_pct=WC.RUNNERS_SEAT_APLUS_PCT, at=now_iso)
    pd_ = RS.play_day(d, at)
    if now < RS.measure_end(pd_) + L.SETTLE:
        out["not_due"] += 1
        return None
    iso = pd_.isoformat()
    try:
        stamp = (cached(row["symbol"], [iso]) or {}).get(iso)
    except Exception:                                           # noqa: BLE001
        stamp = None
    fetched = RS.fetched_on(stamp, now)
    if fetched <= d:
        sp = False
    else:
        try:
            sp = look(row["symbol"], d, fetched)
        except Exception:                                       # noqa: BLE001
            sp = None
    if sp is None:
        out["split_unchecked"] += 1
        return None
    if sp is not False:
        out["win30_split"] += 1
        return {"measured": False, "why": "split", "at": now_iso}
    key = (row["symbol"], pd_)
    if key not in memo:
        if out["loads"] >= cap:
            out["deferred_cap"] += 1
            return None
        out["loads"] += 1
        try:
            res = load(row["symbol"], pd_)
            bars, failed = (res if isinstance(res, tuple) else (res, False))
            bars = bars if isinstance(bars, list) or bars is None else L.bars_from_frame(bars)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gg_like_track: load raised for %s %s: %s", row["symbol"], pd_, type(exc).__name__)
            bars, failed = None, True
        memo[key] = (bars or [], bool(failed))
    bars, failed = memo[key]
    if failed or not bars:
        out["load_failed"] += 1
        return None
    m = RS.from_trigger(bars, pd_, at, t)
    out["win30"] += 1
    return dict({k: m.get(k) for k in RS.FROM_TRIGGER_KEYS}, min_pct=WC.RUNNERS_SEAT_APLUS_PCT, at=now_iso)


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chart_maps.gajjala.gg_like_track", description=__doc__.split("\n")[0])
    ap.add_argument("--once", action="store_true", help="run the nightly 🧘 record once (the 20:15 nightly's function)")
    ap.add_argument("--sessions", type=int, default=None, help="the last N market sessions (default: the ledger's window)")
    ap.add_argument("--dry-run", action="store_true", help="compute and count, write nothing")
    ap.add_argument("--later", action="store_true",
                    help="also write the 'computed later' block on older A+ rows (the one-time run — his go, HIS CALL #11)")
    args = ap.parse_args(argv)
    if not args.once:
        ap.print_help()
        return 2
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    out = record_night(datetime.now(UTC), sessions=args.sessions, dry=args.dry_run, later=args.later)
    print(json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
