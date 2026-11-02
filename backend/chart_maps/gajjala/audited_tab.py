"""🧪 Gajjala · Audited — the served blocks of the audited tab (2026-11-01, BUILD_SPEC gg-audited §3.6 / WP-C).

THE ASK (Ajay 2026-11-01, verbatim): "I would like you to create a new tab for Gajjals when you modifiy with audit of
End of day.. Gajjals-Audited. So we can keep track of improvements on this tab".

WHAT. `tab.build(…, variant=V.GGA)` serves 🚩 Gajjala's board off the SAME pass and the SAME reads (the GGA store
borrows GG5's reads / potentials / passes); this module only lays the audit overlay the pass wrote
(`gajjala_audited_overlay`, audited_pass.py) over those reads at serve time and serves four blocks:

- `overlay_reads` — attaches an overlay entry to an A+ read ONLY when all three hold: the read is `aplus`, the entry's
  `entry_bar_t` is the read's (the bar judged is the bar served), and the overlay's `pass_at` is at least the read's
  `updated_at` (both are the pass clock — equal when the step ran on that pass). A failed audit turns the read into
  the served-only state `aplus_held` (never stored on a GG5 doc). SHALLOW: a touched doc is a new dict with a new
  `setups` dict; `tile` / `bars5` / `bars15` / curves stay the stored objects (nothing is copied, nothing mutated).
  `n_unaudited` counts the A+ reads served without an audit (no fresh matching entry) — they show as the original.
- `held_block` — the 🚩 A+ reads the audit held: the SAME gates as tab.aplus_block (rows come FROM aplus_block over
  the held reads — freshness of the latest pass, the cron pass current, inside the window), each row + `held_by`,
  `audit_text`, `frame`. A held A+ is listed, never hidden.
- `audited_block` — the 🧪 strip: the registry rows (audited_rules.registry_rows — words only), the lane-only line,
  the UNMEASURED line, the process line, the pass line (the GGA state doc audited_pass writes every pass), `stale`
  when that doc is older than 🚩's latest pass (or missing, or not ok), and the unaudited count.
- `compare_block` (🏁 only) — 🚩 original vs 🧪 audited over the GGA 🏁's own sessions, graded by the ONE ledger
  (ledger._cell over the stored `same` column), gross ±1R by the 🏁 outcome; the held rows' counterfactual = the
  original row's same-session grade (`no_original` when 🚩 has no row); `recon` (original_only / audited_only / both),
  `per_rule` (+ `per_rule_title` and `by_rule_note`), `by_day`, `entry_weeks` over the WHOLE record and
  `floor_reached` (a COUNT — `unmeasured_text` is ALWAYS served; no word flips by count).

PER RULE (2026-11-01 modifications, SPEC gg-audited-mods §3.4 / WP-D; Ajay 2026-11-01 "But keep a track record too to
see the winners and loster"). ONE row per ON rule, registry order (G3 is lane-only, never a row; T3 one row per
AUD.T3_R_MULTS). Universe of a FILTER row (T1 included) = the 🚩 originals of the span; each original is scored by the
🧪 record on ITS OWN bar [C1] — the held marker whose `entry_bar_t` is the original's, else the audited claim on that
bar, else (an original with no `entry_bar_t`, an older row) the marker, then the claim; no record → `not_judged`.
A 🧪 record no original takes is ONE `no_original` count on the side its verdict on that rule names. The outcome is
the ORIGINAL's same-session state; `with` = the rule passed it, `other` = the rule held it. T4 serves `fired` (=
other.n) and `fired_alone` (only T4 failed) [C2]; T1 serves `tie_held` (held on a bar tied by 🚩's ring order) [C3].
An EXIT row (T3 per R multiple, T5) scores the audited rows by the nightly exit grade (`gajjala_audited_exits`,
`with`) beside GG's math on the SAME rows (`other`); a missing grade is `pending` ("not graded yet"). Counts only —
every sentence from variant.WORDS_GGA, never a verdict.

READS MONGO ONLY, never a provider. Every rule, number and sentence comes from audited_rules.py / variant.WORDS_GGA /
the ledger — nothing here types a threshold. UNMEASURED — nothing here trades or enters a lane. Not advice.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from . import alerts as AL
from . import audited_rules as AUD
from . import constants as GC
from . import ledger as LG
from . import store as ST
from . import tab as GT
from . import variant as V

log = logging.getLogger("chart_maps.gajjala.audited_tab")

NO_ORIGINAL = "no_original"                                                     # §3.6 — the held row's outcome key
NO_ORIGINAL_TEXT = "no original row — the original's send failed"              # §3.6 — served verbatim
FILLED_STATES = ("win", "loss", "open", "flat")                                 # a fill printed (ledger.CELL_STATES)
OPEN_FLAT_STATES = ("open", "flat")
UNFILLED_STATES = ("no_entry",)
SIDE_LABELS = {"original": "🚩 original", "audited": "🧪 audited"}              # §3.6 — served verbatim


# ── overlay at serve time ─────────────────────────────────────────────────────────────────────────────────────────
def _setups(doc) -> dict:
    s = doc.get("setups") if isinstance(doc, dict) else None
    return s if isinstance(s, dict) else {}


def overlay_reads(reads_by: dict, st, session) -> tuple:
    """(reads_by2, stats) — §3.6 [C2, C8]. A name with no overlay doc passes through as the SAME doc object; a touched
    doc is `dict(doc)` with `setups = {**doc["setups"], **touched}` (shallow — the tile is shared by reference)."""
    overlays: dict = {}
    for o in st.overlays(session) or []:
        if isinstance(o, dict) and o.get("symbol"):
            overlays[str(o["symbol"]).upper()] = o
    out: dict = {}
    n_orig = n_aud = n_held = n_un = 0
    for sym, doc in (reads_by or {}).items():
        setups = _setups(doc)
        ov = overlays.get(str(sym).upper())
        entries = ov.get("setups") if isinstance(ov, dict) and isinstance(ov.get("setups"), dict) else {}
        ov_at = GT._stamp_utc(ov.get("pass_at")) if isinstance(ov, dict) else None
        upd = GT._stamp_utc(doc.get("updated_at")) if isinstance(doc, dict) else None
        touched: dict = {}
        for setup, r in setups.items():
            if not isinstance(r, dict) or r.get("state") != "aplus":
                continue                                            # (1) an audit never paints a non-A+ read
            n_orig += 1
            e = entries.get(setup)
            if (not isinstance(e, dict) or e.get("entry_bar_t") != r.get("entry_bar_t")      # (2) the bar served
                    or ov_at is None or upd is None or ov_at < upd):                       # (3) as fresh as the read
                n_un += 1
                continue
            audit = {k: e[k] for k in AUD.AUDIT_SERVED_KEYS if k in e}
            if audit.get("aplus") is True:
                touched[setup] = dict(r, audit=audit)
                n_aud += 1
            else:                                                   # fail closed: anything but a pass is held
                touched[setup] = dict(r, audit=audit, state=AUD.HELD_STATE)
                n_held += 1
        if touched:
            doc2 = dict(doc)
            doc2["setups"] = {**setups, **touched}
            out[sym] = doc2
        else:
            out[sym] = doc
    ats = [a for a in (GT._stamp_utc(o.get("pass_at")) for o in overlays.values()) if a is not None]
    stats = {"n_aplus_original": n_orig, "n_aplus_audited": n_aud, "n_held": n_held, "n_unaudited": n_un,
             "overlay_at": max(ats) if ats else None}
    return out, stats


# ── 🚩 A+ held by the audit ───────────────────────────────────────────────────────────────────────────────────────
def _gate_open(latest: Optional[dict], now, *, in_window: bool, cron: Optional[dict], session: date, v) -> bool:
    """tab.aplus_block's own gate (this session's pass, the cron pass within the variant's stale seconds, inside the
    window) — read with the tab's own clocks; decides only WHICH empty sentence the held block serves."""
    latest = latest if isinstance(latest, dict) else None
    at = GT._at_utc(latest)
    if cron is None and latest is not None and not latest.get("on_demand"):
        cron = latest
    c_at = GT._at_utc(cron)
    c_age = (GT._et(now) - GT._et(c_at)).total_seconds() if c_at is not None else None
    cron_ok = c_age is not None and c_age <= V.stale_after_sec(v)
    this_session = latest is not None and at is not None and latest.get("date") == session.isoformat()
    return bool(in_window and this_session and cron_ok)


def held_block(reads_by: dict, latest: Optional[dict], now, *, in_window: bool, scan: dict, cron: Optional[dict],
               session: date, v) -> dict:
    """§3.6 — the held A+ section: rows FROM tab.aplus_block over the held reads (read as the A+ they were on 🚩), so
    the freshness / cron / window gates are the banner's own; each row + `held_by` [{id, why}], `audit_text`."""
    vv = V.of(v)
    view: dict = {}
    for sym, doc in (reads_by or {}).items():
        held = {s: dict(r, state="aplus") for s, r in _setups(doc).items()
                if isinstance(r, dict) and r.get("state") == AUD.HELD_STATE}
        if held:
            view[sym] = dict(doc, setups=held)
    ab = GT.aplus_block(view, latest, now, in_window=in_window, scan=scan, cron=cron, session=session, v=vv)
    rows = []
    for row in ab.get("rows") or []:
        r = _setups((reads_by or {}).get(row.get("symbol"))).get(row.get("setup")) or {}
        audit = r.get("audit") if isinstance(r.get("audit"), dict) else {}
        failed = [f for f in audit.get("failed") or [] if isinstance(f, dict)]
        rows.append(dict(row, held_by=[{"id": f.get("id"), "why": f.get("why")} for f in failed],
                         audit_text=audit.get("text"), frame=audit.get("frame") or row.get("frame")))
    empty = None
    if not rows:
        empty = (V.word("held_empty", vv) if _gate_open(latest, now, in_window=in_window, cron=cron,
                                                         session=session, v=vv)
                 else ab.get("empty_text"))                         # the banner's served gate reason
    return {"title": V.word("held_title", vv, n=len(rows)), "rows": rows, "empty_text": empty,
            "note": V.word("process", vv)}


# ── 🧪 the strip ──────────────────────────────────────────────────────────────────────────────────────────────────
def _int(x) -> Optional[int]:
    return x if isinstance(x, int) and not isinstance(x, bool) else None


def audited_block(st, session: date, now, latest: Optional[dict], stats: Optional[dict]) -> dict:
    """§3.6 — the registry, the lane-only / UNMEASURED / process lines, the pass line off the GGA state doc
    (audited_pass.LATEST_ID), `stale` (the doc older than 🚩's latest pass, missing, or not ok) and the unaudited count."""
    from . import audited_pass as AP
    vv = V.GGA
    g3 = AUD.by_id("G3")
    params = dict(getattr(g3, "params", None) or {})
    state = st.get_state(AP.LATEST_ID) or {}
    s_at = GT._stamp_utc(state.get("at"))
    l_at = GT._at_utc(latest)
    ok = state.get("ok") is True
    stale = bool(l_at is not None and (s_at is None or s_at < l_at or not ok))
    pass_text = None
    if s_at is not None and ok:
        pass_text = V.word("pass_line", vv, hhmm=GT._et(s_at).strftime("%H:%M"),
                           n_read=_int(state.get("n_read")) or 0,
                           n_orig=_int(state.get("n_aplus_original")) or 0,
                           n_aud=_int(state.get("n_aplus_audited")) or 0,
                           n_held=_int(state.get("n_held")) or 0)
    n_un = _int((stats or {}).get("n_unaudited")) if isinstance(stats, dict) else None
    return {"title": V.word("strip_title", vv),
            "registry": AUD.registry_rows(),
            "on_ids": [r.id for r in AUD.on_rules()],
            "lane_only_text": V.word("lane_only", vv, m=params.get("m", AUD.G3_MAX_AGE_MIN),
                                     mr=params.get("missed_r", AUD.G3_MISSED_R)),
            "unmeasured_text": V.word("unmeasured", vv, floor=AUD.MEASURE_FLOOR_WEEKS),
            "process_text": V.word("process", vv),
            "pass": {"at_et": GT._et(s_at).strftime("%H:%M") if s_at is not None else None,
                     "ok": ok if state else None,
                     "n_read": _int(state.get("n_read")),
                     "n_aplus_original": _int(state.get("n_aplus_original")),
                     "n_aplus_audited": _int(state.get("n_aplus_audited")),
                     "n_held": _int(state.get("n_held")),
                     "text": pass_text},
            "stale": stale,
            "stale_text": (V.word("pass_stale", vv, hhmm=GT._et(l_at).strftime("%H:%M")) if stale else None),
            "unaudited": {"n": n_un, "text": V.word("unaudited_line", vv, n=n_un) if n_un else None}}


# ── 🏁 audited vs original ────────────────────────────────────────────────────────────────────────────────────────
def _docs_by_id(docs) -> dict:
    if docs is None:
        raise LG.LedgerReadError("the ledger could not be read")
    return {d.get("_id"): d for d in docs if isinstance(d, dict)}


def _state(row: dict, docs: dict, now, session: date, is_today: bool) -> str:
    """The row's same-session state — ledger._cell over the stored `same` column (the 🏁's own word)."""
    doc = docs.get(row["id"]) or {}
    g = doc.get("same") if isinstance(doc.get("same"), dict) else None
    return LG._cell(row, "same", g, False, now, session, is_today)["state"]


def _held_docs(st, sessions) -> list:
    got = st.held_rows(sessions)
    if got is None:
        raise LG.LedgerReadError("the held A+ rows could not be read")
    out, seen = [], set()
    for d in got:
        if not isinstance(d, dict) or d.get("state") != AUD.HELD_ROW_STATE:
            continue
        sym, setup, day = str(d.get("symbol") or "").upper(), d.get("setup"), LG._as_date(d.get("date"))
        if not sym or not isinstance(setup, str) or not setup or day is None:
            continue
        rid = LG.ledger_id(day.isoformat(), sym, setup, LG.KINDS[1])
        if rid in seen:
            continue
        seen.add(rid)
        audit = d.get("audit") if isinstance(d.get("audit"), dict) else {}
        v = _verdicts(audit) or {"passed": [], "failed": [], "rules": [], "tie": False}
        out.append({"id": rid, "date": day.isoformat(), "symbol": sym, "setup": setup, "held_by": v["failed"],
                    "entry_bar_t": d.get("entry_bar_t"), "passed_by": v["passed"], "rules": v["rules"],
                    "t1_tie": v["tie"]})
    return out


def _verdicts(audit) -> Optional[dict]:
    """{passed: [ids], failed: [ids], rules: [ids], tie: bool} of one stored audit block; None when there is none
    (a record written before the claim carried its audit — `not_judged` on every rule)."""
    if not isinstance(audit, dict):
        return None
    vals = audit.get("values") if isinstance(audit.get("values"), dict) else {}
    t1 = vals.get("T1") if isinstance(vals.get("T1"), dict) else {}
    return {"passed": [p for p in audit.get("passed") or [] if isinstance(p, str) and p],
            "failed": [f.get("id") for f in audit.get("failed") or [] if isinstance(f, dict) and f.get("id")],
            "rules": [r for r in audit.get("rules") or [] if isinstance(r, str) and r],
            "tie": t1.get("tie") is True}


def _claim_audits(st, sessions) -> dict:
    """{ledger id: {audit, entry_bar_t}} of the 🧪 shadow claims of these sessions — read off the GGA alerts docs
    directly (ledger.alert_of drops both keys) [C1]. None from the store → LedgerReadError."""
    got = st.alert_rows(sessions)
    if got is None:
        raise LG.LedgerReadError("the audited claims could not be read")
    prefix = AL.SHADOW_CLAIM_PREFIX + V.GGA.claim_prefix + ":"
    out: dict = {}
    for d in got:
        rid = _claim_id(d, (prefix,))
        if rid is not None and rid not in out:
            out[rid] = {"audit": d.get("audit") if isinstance(d.get("audit"), dict) else None,
                        "entry_bar_t": d.get("entry_bar_t")}
    return out


def _original_bars(shared, sessions) -> dict:
    """{ledger id: entry_bar_t} of the 🚩 claims of these sessions (`GG:` live or `SHADOW:GG:` shadow) — a READ of the
    GG5 alerts collection, the one rows_for(sessions, shared) already reads [C1]. None → LedgerReadError."""
    got = shared.alert_rows(sessions)
    if got is None:
        raise LG.LedgerReadError("the original claims could not be read")
    p = V.GG5.claim_prefix + ":"
    out: dict = {}
    for d in got:
        rid = _claim_id(d, (p, AL.SHADOW_CLAIM_PREFIX + p))
        if rid is not None and rid not in out:
            out[rid] = d.get("entry_bar_t")
    return out


def _claim_id(d, prefixes: tuple) -> Optional[str]:
    """The 🏁 ledger id of one claim doc — None unless its `_id` starts with one of `prefixes`, carries no `#`, its
    state is one the ledger reads, and it has a symbol / setup / date."""
    if not isinstance(d, dict):
        return None
    _id = str(d.get("_id") or "")
    if "#" in _id or not _id.startswith(prefixes) or d.get("state") not in ST.LEDGER_ALERT_STATES:
        return None
    sym, setup, day = str(d.get("symbol") or "").upper(), d.get("setup"), LG._as_date(d.get("date"))
    if not sym or not isinstance(setup, str) or not setup or day is None:
        return None
    return LG.ledger_id(day.isoformat(), sym, setup, LG.KINDS[1])


def _rank(setup) -> int:
    return GC.SETUPS.index(setup) if setup in GC.SETUPS else len(GC.SETUPS)


def _cols(docs: dict, rid) -> tuple:
    """(same, next) stored grade columns of one ledger id (None where absent)."""
    doc = docs.get(rid) or {}
    return tuple(doc.get(h) if isinstance(doc.get(h), dict) else None for h in GC.LEDGER_HORIZONS)


def _dedupe_side(rows: list, docs: dict) -> None:
    """🔁 2026-11-02 (Ajay: one count per stock per day) — THE ledger engine over one side's rows, in place: `dup_of` =
    the counted row's id, else None. Partition (date, symbol, count line), as on the 🏁."""
    facts = [LG.trade_facts(r, *_cols(docs, r["id"]), group=(r["date"], r["symbol"], LG._count_line(r)),
                            rank=_rank(r.get("setup"))) for r in rows]
    dups = LG.dedupe_trades([f for f in facts if f])
    for r in rows:
        r["dup_of"] = dups.get(r["id"])


def _read_sides(st, sessions, now, session: date, is_today: bool) -> dict:
    """{original, audited, held} rows of these sessions, each with its same-session `state`. 🔁 2026-11-02: every row
    carries `dup_of` — each side dedupes over its OWN rows; a held row over its ORIGINAL's facts (a held doc carries no
    ring time or plan), the partition being the held rows themselves (never inherited from the original side)."""
    shared = st.shared
    orig = [r for r in LG.rows_for(sessions, shared) if r.get("kind") == LG.KINDS[1]]
    aud = [r for r in LG.rows_for(sessions, st, variant=V.GGA) if r.get("kind") == LG.KINDS[1]]
    odocs = _docs_by_id(shared.ledger_docs(sessions))
    adocs = _docs_by_id(st.ledger_docs(sessions))
    for r in orig:
        r["state"] = _state(r, odocs, now, session, is_today)
    for r in aud:
        r["state"] = _state(r, adocs, now, session, is_today)
    obars = _original_bars(shared, sessions)
    claims = _claim_audits(st, sessions)
    for r in orig:
        r["entry_bar_t"] = obars.get(r["id"])
    for r in aud:
        c = claims.get(r["id"]) or {}
        r["audit"] = c.get("audit")
        r["entry_bar_t"] = c.get("entry_bar_t")
    _dedupe_side(orig, odocs)
    _dedupe_side(aud, adocs)
    by_orig = {r["id"]: r for r in orig}
    held = _held_docs(st, sessions)
    for h in held:
        o = by_orig.get(h["id"])
        h["state"] = o["state"] if o is not None else NO_ORIGINAL
        if o is None:
            h["state_text"] = NO_ORIGINAL_TEXT
        else:
            doc = odocs.get(o["id"]) or {}
            g = doc.get("same") if isinstance(doc.get("same"), dict) else None
            h["state_text"] = LG._cell(o, "same", g, False, now, session, is_today)["text"]
    facts_held = [LG.trade_facts(o, *_cols(odocs, o["id"]), group=(h["date"], h["symbol"], LG._count_line(o)),
                                 rank=_rank(h.get("setup")))
                  for h in held for o in [by_orig.get(h["id"])] if o is not None]
    dups_held = LG.dedupe_trades([f for f in facts_held if f])
    for h in held:
        h["dup_of"] = dups_held.get(h["id"])                  # None on a NO_ORIGINAL held row
    return {"original": orig, "audited": aud, "held": held}


def _tally(rows: list, r_of=None) -> dict:
    """Counts of `rows` by their `state`; `mean_r` over decided rows = ±LEDGER_R_MULT (GG's math) — or, with `r_of`
    (an exit grade's own R per row), the mean of `r_of(row)` over the decided rows that carry a number. 🔁 2026-11-02:
    THE one filter point — a duplicate row (`dup_of` set) is dropped first and counted in `n_dup`; `n` = counted rows."""
    kept = [r for r in rows if not r.get("dup_of")]
    n_dup = len(rows) - len(kept)
    rows = kept
    c = {"n": len(rows), "n_dup": n_dup, "filled": 0, "win": 0, "loss": 0, "open_flat": 0, "unfilled": 0, "pending": 0,
         NO_ORIGINAL: 0}
    for r in rows:
        s = r.get("state")
        if s in FILLED_STATES:
            c["filled"] += 1
        if s == "win":
            c["win"] += 1
        elif s == "loss":
            c["loss"] += 1
        elif s in OPEN_FLAT_STATES:
            c["open_flat"] += 1
        elif s in UNFILLED_STATES:
            c["unfilled"] += 1
        elif s == NO_ORIGINAL:
            c[NO_ORIGINAL] += 1
        else:
            c["pending"] += 1                                       # pending / no plan / no risk / no time / split
    decided = c["win"] + c["loss"]
    if r_of is None:
        r_mult = float(GC.LEDGER_R_MULT)
        c["mean_r"] = round((c["win"] * r_mult - c["loss"] * 1.0) / decided, 4) if decided else None
    else:
        rs = [LG._num(r_of(r)) for r in rows if r.get("state") in ("win", "loss")]
        rs = [float(x) for x in rs if x is not None]
        c["mean_r"] = round(sum(rs) / len(rs), 4) if rs else None
    c["win_pct"] = LG._win_pct(c)
    return c


def _wl_text(c: dict) -> str:
    pct = f" ({c['win_pct']}%)" if c.get("win_pct") is not None else ""
    return f"{c['win']} W / {c['loss']} L{pct}"


def _mean_text(c: dict) -> str:
    if c.get("mean_r") is None:
        return "no decided trade yet"
    return f"mean {c['mean_r']:+.2f}R over {c['win'] + c['loss']} decided"


def _side(key: str, rows: list) -> dict:
    c = _tally(rows)
    label = SIDE_LABELS[key]
    bits = [f"{label}: {c['n']} A+", _wl_text(c), f"{c['open_flat']} open or flat", f"{c['unfilled']} no entry"]
    if c["pending"]:
        bits.append(f"{c['pending']} not graded yet")
    bits += [_mean_text(c), GT.UNMEASURED]
    return {"key": key, "label": label, "n": c["n"], "n_dup": c["n_dup"], "filled": c["filled"], "win": c["win"],
            "loss": c["loss"],
            "open_flat": c["open_flat"], "unfilled": c["unfilled"], "mean_r": c["mean_r"], "win_pct": c["win_pct"],
            "text": " · ".join(bits)}


def _held_side(rows: list) -> dict:
    c = _tally(rows)
    bits = [f"🚩 A+ held by the audit: {c['n']}", "what the original did: " + _wl_text(c),
            f"{c['open_flat']} open or flat", f"{c['unfilled']} no entry"]
    if c[NO_ORIGINAL]:
        bits.append(f"{c[NO_ORIGINAL]} with no original row")
    if c["pending"]:
        bits.append(f"{c['pending']} not graded yet")
    bits += [_mean_text(c), GT.UNMEASURED]
    out_rows = []
    for h in sorted(rows, key=lambda x: (x["date"], x["symbol"], GC.SETUPS.index(x["setup"])
                                         if x["setup"] in GC.SETUPS else len(GC.SETUPS)), reverse=True):
        label = GT._setup_label(h["setup"])
        ids = list(h.get("held_by") or [])
        out_rows.append({"date": h["date"], "symbol": h["symbol"], "setup": h["setup"], "setup_label": label,
                         "held_by": ids, "outcome": h["state"], "outcome_text": h.get("state_text"),
                         "dup_of": h.get("dup_of"),                                    # 🔁 listed, never hidden
                         "text": (f"{h['date']} · {h['symbol']} · {label} · held by "
                                  f"{', '.join(ids) if ids else '—'} · the original: {h.get('state_text') or '—'}")})
    return {"n": c["n"], "n_dup": c["n_dup"], "win": c["win"], "loss": c["loss"], "open_flat": c["open_flat"],
            "unfilled": c["unfilled"], NO_ORIGINAL: c[NO_ORIGINAL], "mean_r": c["mean_r"], "text": " · ".join(bits), "rows": out_rows}


# ── 🧪 per rule (SPEC gg-audited-mods §3.4) ──────────────────────────────────────────────────────────────────────
KIND_CAP = "cap"                                                                # the T1 row's served kind (a filter)


def _bar(x) -> Optional[str]:
    return str(x) if x is not None and str(x) else None


def _attribute(sides: dict) -> tuple:
    """([(original row, verdicts | None)], [unmatched record verdicts]) — [C1] each 🚩 original scored by the 🧪 record
    on ITS bar: the held marker on that bar, else the audited claim on that bar, else (an original with no bar) the
    marker, then the claim. A record no original takes is returned once in the second list (None verdicts dropped)."""
    markers = {h["id"]: h for h in sides["held"]}
    claims = {a["id"]: a for a in sides["audited"]}
    taken: set = set()
    pairs = []
    for o in sides["original"]:
        m, c = markers.get(o["id"]), claims.get(o["id"])
        ob = _bar(o.get("entry_bar_t"))
        rec = None
        if ob is not None:
            if m is not None and _bar(m.get("entry_bar_t")) == ob:
                rec = ("m", m)
            elif c is not None and _bar(c.get("entry_bar_t")) == ob:
                rec = ("c", c)
        else:
            rec = ("m", m) if m is not None else (("c", c) if c is not None else None)
        if rec is not None:
            taken.add((rec[0], o["id"]))      # 🔁 a duplicate original still takes its record (never a false no_original)
        if o.get("dup_of"):
            continue                          # 🔁 2026-11-02: a duplicate original is neither with- nor held- scored
        if rec is None:
            pairs.append((o, None))
            continue
        pairs.append((o, _rec_verdicts(*rec)))
    loose = [_rec_verdicts("m", m) for i, m in markers.items() if ("m", i) not in taken]
    loose += [_rec_verdicts("c", c) for i, c in claims.items() if ("c", i) not in taken]
    return pairs, [v for v in loose if v is not None]


def _rec_verdicts(kind: str, rec: dict) -> Optional[dict]:
    if kind == "m":
        return {"passed": list(rec.get("passed_by") or []), "failed": list(rec.get("held_by") or []),
                "rules": list(rec.get("rules") or []), "tie": rec.get("t1_tie") is True}
    return _verdicts(rec.get("audit"))


def _side_text(label: str, c: dict) -> str:
    bits = [f"{label}: {c['n']} A+", f"{c['win']} W / {c['loss']} L", f"{c['unfilled']} no entry"]
    if c["open_flat"]:
        bits.append(f"{c['open_flat']} open or flat")
    if c["pending"]:
        bits.append(f"{c['pending']} not graded yet")
    if c[NO_ORIGINAL]:
        bits.append(f"{c[NO_ORIGINAL]} no original row")
    bits.append(_mean_text(c))
    return " · ".join(bits)


def _pr_side(label: str, rows: list, *, no_original: int = 0, r_of=None, extra: Optional[str] = None) -> dict:
    c = _tally(rows, r_of=r_of)
    c[NO_ORIGINAL] = no_original
    text = _side_text(label, c)
    if extra:
        text += " · " + extra
    return {"label": label, "n": c["n"], "n_dup": c["n_dup"], "win": c["win"], "loss": c["loss"],
            "unfilled": c["unfilled"],
            "open_flat": c["open_flat"], "pending": c["pending"], NO_ORIGINAL: c[NO_ORIGINAL], "mean_r": c["mean_r"],
            "text": text}


def _with_not_judged(delta: str, n: int) -> str:
    return delta + " · " + V.word("per_rule_not_judged", V.GGA, n=n) if n else delta


def _pr_row(key: str, rid: str, kind: str, label: str, w: dict, o: dict, delta: str, *, not_judged: int,
            fired_alone=None, tie_held=None) -> dict:
    return {"key": key, "id": rid, "name": getattr(AUD.by_id(rid), "name", None) or rid, "kind": kind,
            "label": label, "with": w, "other": o, "not_judged": not_judged, "fired_alone": fired_alone,
            "tie_held": tie_held, "delta_text": delta,
            "text": f"{label} · {w['text']} · {o['text']} · {delta} · {GT.UNMEASURED}"}


def _filter_row(rule, pairs: list, loose: list) -> dict:
    rid = rule.id
    vv = V.GGA
    with_rows, other_rows, recs_held = [], [], []
    not_judged = 0
    for o, v in pairs:
        if v is not None and rid in v["passed"]:
            with_rows.append(o)
        elif v is not None and rid in v["failed"]:
            other_rows.append(o)
            recs_held.append(v)
        else:
            not_judged += 1                         # no record on the bar / recorded before the rule joined
    no_w = sum(1 for v in loose if rid in v["passed"])
    no_o = sum(1 for v in loose if rid in v["failed"])
    is_t1, is_t4 = rid == "T1", rid == "T4"
    fired_alone = sum(1 for v in recs_held if v["failed"] == [rid]) if is_t4 else None
    tie_held = sum(1 for v in recs_held if v["tie"]) if is_t1 else None
    extra = None
    if is_t4:
        extra = V.word("per_rule_t4_fired", vv, fired=len(other_rows), alone=fired_alone)
    elif is_t1 and tie_held:
        extra = V.word("per_rule_t1_tie", vv, n=tie_held)
    w = _pr_side(V.word("per_rule_with", vv), with_rows, no_original=no_w)
    other = _pr_side(V.word("per_rule_cap_held" if is_t1 else "per_rule_held", vv), other_rows, no_original=no_o,
                     extra=extra)
    if w["n"] + other["n"] == 0:
        delta = V.word("per_rule_no_rows", vv)
    else:
        delta = V.word("per_rule_delta_filter", vv, w=LG._plural(other["win"], "winner", "winners"),
                       l=LG._plural(other["loss"], "loser", "losers"), u=other["unfilled"])
    label = f"{rid} {getattr(rule, 'name', None) or rid}"
    return _pr_row(rid, rid, KIND_CAP if is_t1 else AUD.KIND_FILTER, label, w, other,
                   _with_not_judged(delta, not_judged), not_judged=not_judged, fired_alone=fired_alone,
                   tie_held=tie_held)


def _exit_rows(rule, audited: list, exits_by_id: dict) -> list:
    vv = V.GGA
    rid = rule.id
    is_t3 = rid == "T3"
    rows = [r for r in audited if r.get("setup") in AUD.T3_SETUPS] if is_t3 else list(audited)
    out = []
    for k in (AUD.T3_R_MULTS if is_t3 else (None,)):
        col = AUD.exit_col_key(rid, k)
        graded = []
        for r in rows:
            doc = exits_by_id.get(r["id"]) or {}
            g = doc.get(col) if isinstance(doc.get(col), dict) else None
            graded.append({"state": LG._state_of(g) if g is not None else "pending",
                           "r": g.get("r") if g is not None else None,
                           "dup_of": r.get("dup_of")})          # 🔁 2026-11-02: _tally drops a duplicate
        name = getattr(rule, "name", None) or rid
        label = (f"{rid} {name} +{k:g}R · {' · '.join(GT._setup_label(s) for s in AUD.T3_SETUPS)}" if is_t3
                 else f"{rid} {name}")
        w = _pr_side(V.word("per_rule_with", vv), graded, r_of=lambda x: x.get("r"))
        other = _pr_side(V.word("per_rule_gg_math", vv), rows)
        if not rows:
            delta = V.word("per_rule_no_rows", vv)
        elif w["pending"] == w["n"]:
            delta = V.word("per_rule_not_graded", vv)
        else:
            delta = V.word("per_rule_delta_exit", vv, rule=label, ww=w["win"], wl=w["loss"], gw=other["win"],
                           gl=other["loss"], n=w["n"])
        out.append(_pr_row(col, rid, AUD.KIND_EXIT, label, w, other, delta, not_judged=0))
    return out


def _per_rule(sides: dict, exits_by_id: dict, now, session: date, is_today: bool) -> list:
    """§3.4 — ONE row per ON rule in registry order (lane-only G3 never a row; T3 one row per AUD.T3_R_MULTS). Every
    number a COUNT, every sentence served. `now` / `session` / `is_today` are the 🏁's own clocks — the states on the
    sides were read with them (ledger._cell)."""
    pairs, loose = _attribute(sides)
    out = []
    for rule in AUD.on_rules():
        if getattr(rule, "kind", AUD.KIND_FILTER) == AUD.KIND_EXIT:
            out += _exit_rows(rule, sides["audited"], exits_by_id or {})
        else:
            out.append(_filter_row(rule, pairs, loose))
    return out


def _by_day(sides: dict) -> list:
    days = sorted({r["date"] for rows in sides.values() for r in rows}, reverse=True)
    out = []
    for d in days:
        cell = {}
        for k in ("original", "audited", "held"):
            c = _tally([r for r in sides[k] if r["date"] == d])
            cell[k] = {"n": c["n"], "win": c["win"], "loss": c["loss"]}
        dd = LG._as_date(d)
        label = LG._dow_md(dd) if dd is not None else d
        o, a, h = cell["original"], cell["audited"], cell["held"]
        out.append({"date": d, "label": label, **cell,
                    "text": (f"{label}: 🚩 {o['n']} ({o['win']} W / {o['loss']} L) · 🧪 {a['n']} ({a['win']} W / "
                             f"{a['loss']} L) · held {h['n']} ({h['win']} W / {h['loss']} L)")})
    return out


def _entry_weeks(audited: list) -> int:
    weeks = set()
    for r in audited:
        if r.get("state") in FILLED_STATES:
            d = LG._as_date(r.get("date"))
            if d is not None:
                weeks.add(tuple(d.isocalendar()[:2]))
    return len(weeks)


def compare_block(st, session: date, now, *, span: str = "", is_today: bool = False) -> dict:
    """§3.6 [C5] — 🚩 original vs 🧪 audited on the GGA 🏁's own sessions (its record start clips them). Raises
    ledger.LedgerReadError on a read fault (the tab softens it to None)."""
    now = LG._aware(now)
    session = LG._as_date(session)
    span_k = span if span in GC.LEDGER_SPANS else GC.LEDGER_SPAN_DEFAULT
    sessions = LG._clip(LG._sessions_for(span_k, session, st, [], V.GGA), V.GGA)
    sides = _read_sides(st, sessions, now, session, is_today)
    exits = st.exits_docs(sessions)
    if exits is None:
        raise LG.LedgerReadError("the audited exit grades could not be read")
    exits_by_id = {d.get("_id"): d for d in exits if isinstance(d, dict)}
    oid = {r["id"] for r in sides["original"]}
    aid = {r["id"] for r in sides["audited"]}
    hid = {h["id"] for h in sides["held"]}
    original_only = len(oid - aid - hid)
    audited_only = len((aid | hid) - oid)          # on this tab (audited or held) with no 🚩 row: the send failed
    both = len(aid & hid)                          # held on one pass, audited A+ on a later one the same day
    all_k = "all"
    if span_k == all_k:
        weeks = _entry_weeks(sides["audited"])
    else:                                          # the floor counts the WHOLE record, never the span shown
        rec = LG._clip(LG._sessions_for(all_k, session, st, [], V.GGA), V.GGA)
        aud_all = [r for r in LG.rows_for(rec, st, variant=V.GGA) if r.get("kind") == LG.KINDS[1]]
        adocs = _docs_by_id(st.ledger_docs(rec))
        for r in aud_all:
            r["state"] = _state(r, adocs, now, session, is_today)
        weeks = _entry_weeks(aud_all)
    floor = AUD.MEASURE_FLOOR_WEEKS
    reached = weeks >= floor
    vv = V.GGA
    return {"title": V.word("compare_title", vv),
            "honesty": V.word("compare_honesty", vv, r=float(GC.LEDGER_R_MULT), floor=floor, n=weeks),
            "span": span_k,
            "sides": [_side("original", sides["original"]), _side("audited", sides["audited"])],
            "held": _held_side(sides["held"]),
            "recon": {"original_only": original_only, "audited_only": audited_only, "both": both,
                      "text": V.word("compare_recon", vv, original_only=original_only, audited_only=audited_only)},
            "per_rule_title": V.word("per_rule_title", vv),
            "per_rule": _per_rule(sides, exits_by_id, now, session, is_today),
            "by_rule_note": V.word("by_rule_note", vv),
            "by_day": _by_day(sides),
            "entry_weeks": weeks, "floor_weeks": floor, "floor_reached": reached,
            "unmeasured_text": (V.word("floor_reached", vv, n=weeks, floor=floor) if reached
                                else V.word("unmeasured", vv, floor=floor))}


__all__ = ["overlay_reads", "held_block", "audited_block", "compare_block", "NO_ORIGINAL", "NO_ORIGINAL_TEXT"]
