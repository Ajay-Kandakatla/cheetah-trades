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

🏁 ROWS (2026-11-05, SPEC gg-track-parity §3.1 / WP-A). Ajay, verbatim: "Can you make both Gajjala's track record and
Gajjalas 1 min and Gajjalas AUDIT HAVE similar track record. It looks like our Gajjals 5 min had better win yesterday
and today... I would like you to audit but its hard to tell which ones won in Gajjlas Audit page" (trigger: "Why are the
other winners not having charts?" — the 🧪 🏁 listed only an A+ that passed every ON rule, 0 since 11-01, so its A+
block drew no chart; the winners were text lines of the compare's held list, never rows). `track_block` serves 🚩's
OWN served 🏁 block (`ledger.served_block(st.shared, …, variant=GGA)` — 🚩's rows, 🚩's grades from the ONE ledger,
🚩's dedupe, GGA's clip / words / links) plus ONE served column `audit` right after the Ticker: the audit's call on the
row's own bar (`row_audits` — the SAME record `_attribute` scores per rule, via `_record_of`): passed every rule (the
stored `aplus` is the verdict; zero rules on reads "no rule was on"), held by the rule ids (the why sentences stay in the
compare's held list — HIS CALL #31), or not judged; a passed row with an exits doc carries the T3 / T5 exit-grade words
(`EXIT_STATE_TEXT`, a word for every ledger.CELL_STATES member). The audit is read ONCE per build (`read_span` — the
SHARED store's sessions ∪ the GGA store's own, so an overlay-silent 🚩 session counts `original_only`) and HANDED to
both 🏁 blocks; `track_block` never reads it — a failed read lists 🚩's rows with NOT_READ_CELL, never an empty 🏁.
No today read on this tab (HIS CALL #28): today's rows carry the ledger's own "not read yet — graded tonight" words.

🧪 K3S ADMIT (2026-11-09, SPEC gg-k3s §3.4 / WP-C). Ajay, verbatim: "yes change the audit as per you like that is
yours I need you to make it successful and earn money that is the goal". The registry's admit rule K3S makes a 🎾
break 🚩 reads "broke — not A+" on K3 alone a 🧪 A+ (audited_pass writes the overlay entry with `admit`). Served here:
`overlay_reads` paints that 🚩 partial ONLY on its break pass (audited_rules.k3s_candidate ⇒ bars_since_entry == 0) and
only when the entry carries `admit` — afterwards the card is 🚩's partial, unchanged [C3]; the held block / held docs /
verdicts carry `admit`; the compare moves admitted records OUT of the held side and out of the per-rule attribution
(`_attribute` / `row_audits` never score them [C7]) into ONE `admitted` block ("🧪 only": W / L / filled / mean R by
GG's math, the held-by counts [C8], the same-day-original count [C7]) and `recon.admitted` (admitted rang ids with no
🚩 row [C6]); the per-rule table gains the ADMIT row (with = the admitted rings, other = 🚩's own 🎾 A+ on the same
sessions). UNMEASURED.

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
from . import detectors as D
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
ADMIT_KINDS = ("rang", "held")                                                  # 🧪 2026-11-09 K3S — an admitted row's kind
K11_RULE = D.K11_KEY.partition("_")[0].upper()     # 🧪 2026-11-09 K3S — "K11", the rule's name off its ONE key (spec §3.4)
ADMIT_HELD_STATE = "held"                                                       # a held admit never rang → no grade
ADMIT_HELD_TEXT = "held here — never rang, never graded"                        # 🧪 2026-11-09 K3S — MINE (HIS CALL #43)
SIDE_LABELS = {"original": "🚩 original", "audited": "🧪 audited"}              # §3.6 — served verbatim
# 🧪 2026-11-05 (SPEC gg-track-parity §3.1) — the 🏁 row's audit column
AUDIT_HEAD_KEY = "audit"                                                        # the served head key and row cell key
AUDIT_STATES = ("passed", "held", "not_judged", "not_read")                     # the cell's `state` (a CSS hook)
NOT_READ_CELL = {"state": AUDIT_STATES[3], "text": V.word("row_audit_not_read", V.GGA), "sub_text": None,
                 "provisional": False}                                          # the audit read failed this time
# [C4] a word for EVERY ledger.CELL_STATES member — the ledger owns the words (BUCKET_TEXT / APLUS_ITEM_LABELS /
# NO_TIME_TEXT; no_plan / no_risk / split pinned equal to the `text` ledger._cell serves for that state)
EXIT_STATE_TEXT = {**{k: LG.BUCKET_TEXT[k] for k in ("win", "loss", "open", "flat")},
                   "no_entry": LG.APLUS_ITEM_LABELS["no_entry"], "no_time": LG.NO_TIME_TEXT,
                   "no_plan": V.word("row_exit_no_plan", V.GGA), "no_risk": V.word("row_exit_no_risk", V.GGA),
                   "split": V.word("row_exit_split", V.GGA), "pending": V.word("row_exit_pending", V.GGA)}


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
    n_orig = n_aud = n_held = n_un = n_adm = 0
    for sym, doc in (reads_by or {}).items():
        setups = _setups(doc)
        ov = overlays.get(str(sym).upper())
        entries = ov.get("setups") if isinstance(ov, dict) and isinstance(ov.get("setups"), dict) else {}
        ov_at = GT._stamp_utc(ov.get("pass_at")) if isinstance(ov, dict) else None
        upd = GT._stamp_utc(doc.get("updated_at")) if isinstance(doc, dict) else None
        touched: dict = {}
        for setup, r in setups.items():
            if not isinstance(r, dict):
                continue
            e = entries.get(setup)
            if r.get("state") != "aplus":
                # (1) an audit never paints a non-A+ read — save 🧪 K3S [C3]: the 🚩 partial on its BREAK pass
                # (k3s_candidate ⇒ bars_since_entry == 0) whose entry carries the admit, under the same (2) + (3)
                if not (_entry_admit(e) and AUD.k3s_candidate(dict(r, setup=setup))
                        and e.get("entry_bar_t") == r.get("entry_bar_t")
                        and ov_at is not None and upd is not None and ov_at >= upd):
                    continue
                audit = {k: e[k] for k in AUD.AUDIT_SERVED_KEYS if k in e}
                touched[setup] = dict(r, audit=audit,
                                      state="aplus" if audit.get("aplus") is True else AUD.HELD_STATE)
                n_adm += 1                                  # never in n_aplus_original (that counts 🚩 A+)
                continue
            n_orig += 1
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
             "n_admitted": n_adm, "overlay_at": max(ats) if ats else None}
    return out, stats


def _entry_admit(e) -> Optional[str]:
    """🧪 2026-11-09 K3S — the admit rule id an overlay entry / audit block carries (a non-empty str), else None."""
    a = e.get("admit") if isinstance(e, dict) else None
    return a if isinstance(a, str) and a else None


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
                         audit_text=audit.get("text"), frame=audit.get("frame") or row.get("frame"),
                         admit=_entry_admit(audit)))                 # 🧪 2026-11-09 K3S
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
            "unaudited": {"n": n_un, "text": V.word("unaudited_line", vv, n=n_un) if n_un else None},
            "admitted": _admitted_strip(state.get("k3s_session"))}


def _admitted_strip(ks) -> dict:
    """🧪 2026-11-09 K3S — the strip's admit line off the GGA state doc's DURABLE per-session counts (audited_pass
    k3s_session). None-safe: no `k3s_session` → every number None and no text; no candidate → the counts, no text."""
    ks = ks if isinstance(ks, dict) else {}
    rang, held = _int(ks.get("rang")), _int(ks.get("held"))
    cand, k11, pa = _int(ks.get("candidates")), _int(ks.get("k11_refused")), _int(ks.get("placebo_a"))
    n = rang + held if rang is not None and held is not None else None
    text = None
    if cand and n is not None:
        text = V.word("k3s_pass_line", V.GGA, n=n, rule=AUD.K3S.id, reason=D.NOT_APLUS_REASON, rang=rang, held=held,
                      vol=k11 or 0, gate=K11_RULE, cand=cand, pa=pa or 0)
    return {"n": n, "rang": rang, "held": held, "candidates": cand, "k11_refused": k11, "placebo_a": pa, "text": text}


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
        v = _verdicts(audit) or {"passed": [], "failed": [], "rules": [], "tie": False, "ok": False}
        out.append({"id": rid, "date": day.isoformat(), "symbol": sym, "setup": setup, "held_by": v["failed"],
                    "entry_bar_t": d.get("entry_bar_t"), "passed_by": v["passed"], "rules": v["rules"],
                    "t1_tie": v["tie"], "admit": _entry_admit(audit)})          # 🧪 2026-11-09 K3S
    return out


def _verdicts(audit) -> Optional[dict]:
    """{passed: [ids], failed: [ids], rules: [ids], tie: bool, ok: bool} of one stored audit block; None when there is
    none (a record written before the claim carried its audit — `not_judged` on every rule). `ok` (2026-11-05 [C6]) =
    the ONE stored verdict audited_rules._finish wrote (`aplus is True`) — never re-derived from the lists."""
    if not isinstance(audit, dict):
        return None
    vals = audit.get("values") if isinstance(audit.get("values"), dict) else {}
    t1 = vals.get("T1") if isinstance(vals.get("T1"), dict) else {}
    return {"passed": [p for p in audit.get("passed") or [] if isinstance(p, str) and p],
            "failed": [f.get("id") for f in audit.get("failed") or [] if isinstance(f, dict) and f.get("id")],
            "rules": [r for r in audit.get("rules") or [] if isinstance(r, str) and r],
            "tie": t1.get("tie") is True, "ok": audit.get("aplus") is True,
            "admit": _entry_admit(audit)}                               # 🧪 2026-11-09 K3S


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
    """{original, audited, held, admitted} rows of these sessions, each with its same-session `state`. 🔁 2026-11-02:
    every row carries `dup_of` — each side dedupes over its OWN rows; a held row over its ORIGINAL's facts (a held doc
    carries no ring time or plan), the partition being the held rows themselves (never inherited from the original side).
    🧪 2026-11-09 K3S: an audited row carries `admit` (its claim's audit); a held marker WITH an admit leaves `held` —
    `admitted` lists the admitted rings (they STAY in `audited`: a 🧪 A+) and the admitted holds (_admitted_rows)."""
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
        r["admit"] = _entry_admit(c.get("audit"))                  # 🧪 2026-11-09 K3S
    _dedupe_side(orig, odocs)
    _dedupe_side(aud, adocs)
    by_orig = {r["id"]: r for r in orig}
    held_all = _held_docs(st, sessions)
    held = [h for h in held_all if not h.get("admit")]
    admitted_held = [h for h in held_all if h.get("admit")]
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
    return {"original": orig, "audited": aud, "held": held,
            "admitted": _admitted_rows(aud, admitted_held, by_orig, adocs, now, session, is_today)}


def _admitted_rows(aud: list, admitted_held: list, by_orig: dict, adocs: dict, now, session: date,
                   is_today: bool) -> list:
    """🧪 2026-11-09 K3S — the admitted rows: kind "rang" (an audited row with `admit`; its state = the GGA ledger's
    same-session grade, `dup_of` its own side's) and kind "held" (a `#held` marker with `admit`; it never rang → no
    grade, state ADMIT_HELD_STATE). `original_same_day` = the id is also a 🚩 row (a later same-day 🚩 🎾 A+ under the
    one claim per name per day [C7])."""
    out = []
    for r in aud:
        if not r.get("admit"):
            continue
        doc = adocs.get(r["id"]) or {}
        g = doc.get("same") if isinstance(doc.get("same"), dict) else None
        v = _verdicts(r.get("audit")) or {"failed": []}
        out.append({"id": r["id"], "date": r["date"], "symbol": r["symbol"], "setup": r["setup"],
                    "kind": ADMIT_KINDS[0], "rule": r["admit"], "held_by": list(v["failed"]), "state": r["state"],
                    "state_text": LG._cell(r, "same", g, False, now, session, is_today)["text"],
                    "dup_of": r.get("dup_of"), "entry_bar_t": r.get("entry_bar_t"),
                    "original_same_day": r["id"] in by_orig})
    for h in admitted_held:
        out.append({"id": h["id"], "date": h["date"], "symbol": h["symbol"], "setup": h["setup"],
                    "kind": ADMIT_KINDS[1], "rule": h["admit"], "held_by": list(h.get("held_by") or []),
                    "state": ADMIT_HELD_STATE, "state_text": ADMIT_HELD_TEXT, "dup_of": None,
                    "entry_bar_t": h.get("entry_bar_t"), "original_same_day": h["id"] in by_orig})
    return out


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
    marker, then the claim. A record no original takes is returned once in the second list (None verdicts dropped).
    🧪 2026-11-09 K3S: an admitted record (`admit`) is never scored on a filter row — _unadmitted [C7]."""
    markers, claims = _unadmitted(sides)
    taken: set = set()
    pairs = []
    for o in sides["original"]:
        rec = _record_of(o, markers, claims)
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


def _unadmitted(sides: dict) -> tuple:
    """({id: held marker}, {id: audited claim}) with every admitted record (`admit` set) left out — 🧪 2026-11-09 K3S:
    an admit is not a verdict on 🚩's A+, so neither the per-rule filter rows nor the 🏁 audit column ever read it."""
    return ({h["id"]: h for h in sides["held"] if not h.get("admit")},
            {a["id"]: a for a in sides["audited"] if not a.get("admit")})


def _record_of(o: dict, markers: dict, claims: dict) -> Optional[tuple]:
    """("m", marker) | ("c", claim) | None — the 🧪 record on the original's OWN bar [C1]: the held marker on that bar,
    else the audited claim on that bar, else (an original with no bar) the marker, then the claim. Extracted from
    _attribute 2026-11-05 (byte-identical semantics) — row_audits reads the SAME record the per-rule table scores."""
    m, c = markers.get(o["id"]), claims.get(o["id"])
    ob = _bar(o.get("entry_bar_t"))
    if ob is not None:
        if m is not None and _bar(m.get("entry_bar_t")) == ob:
            return ("m", m)
        if c is not None and _bar(c.get("entry_bar_t")) == ob:
            return ("c", c)
        return None
    return ("m", m) if m is not None else (("c", c) if c is not None else None)


def _rec_verdicts(kind: str, rec: dict) -> Optional[dict]:
    if kind == "m":
        return {"passed": list(rec.get("passed_by") or []), "failed": list(rec.get("held_by") or []),
                "rules": list(rec.get("rules") or []), "tie": rec.get("t1_tie") is True,
                "ok": False}                                    # 2026-11-05 [C6]: a held marker never passed
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
        kind = getattr(rule, "kind", AUD.KIND_FILTER)
        if kind == AUD.KIND_EXIT:
            out += _exit_rows(rule, sides["audited"], exits_by_id or {})
        elif kind == AUD.KIND_ADMIT:                                 # 🧪 2026-11-09 K3S
            out.append(_admit_row(rule, sides))
        else:
            out.append(_filter_row(rule, pairs, loose))
    return out


def _admit_row(rule, sides: dict) -> dict:
    """🧪 2026-11-09 K3S [C4] — the ADMIT row: `with` = the 🧪-only rings this rule admitted (graded by GG's math off
    the GGA ledger, mean R printed), `other` = 🚩's own A+ on the rule's setups (AUD.K3S_SETUPS) over the same sessions.
    The delta prints W / L, filled, never-filled and mean R beside 🚩's 🎾 W / L — never W / L alone."""
    vv = V.GGA
    rid = rule.id
    rows = [r for r in sides["audited"] if r.get("admit") == rid]
    orig = [o for o in sides["original"] if o.get("setup") in AUD.K3S_SETUPS]
    w = _pr_side(V.word("per_rule_admit_with", vv), rows)
    other = _pr_side(V.word("per_rule_admit_other", vv), orig)
    if w["n"] == 0:
        delta = V.word("per_rule_no_rows", vv)
    else:
        wt = _tally(rows)
        delta = V.word("per_rule_delta_admit", vv, n=w["n"], w=w["win"], l=w["loss"], filled=wt["filled"],
                       u=w["unfilled"], mr=_mean_text(wt), gw=other["win"], gl=other["loss"], gn=other["n"])
    return _pr_row(rid, rid, AUD.KIND_ADMIT, f"{rid} {getattr(rule, 'name', None) or rid}", w, other, delta,
                   not_judged=0)


def _by_day(sides: dict) -> list:
    days = sorted({r["date"] for k in ("original", "audited", "held") for r in sides[k]}, reverse=True)
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


def read_span(st, session: date, now, *, span: str = "", is_today: bool = False) -> dict:
    """🧪 2026-11-05 [C1, C5] — the ONE audit read of a 🏁 build, handed to both 🏁 blocks: {"span", "sessions",
    "sides" (_read_sides), "exits_by_id"}. `sessions` = the list served_block reads over the SHARED store (every 🚩 A+
    session ≥ the record start) ∪ the GGA store's own claim / marker dates (no audited-only claim lost); on today /
    yesterday / 5d / 10d both are the same calendar window — only "all" differs. Raises (LedgerReadError, or anything a
    stored doc throws) — the TAB softens it."""
    now = LG._aware(now)
    session = LG._as_date(session)
    span_k = span if span in GC.LEDGER_SPANS else GC.LEDGER_SPAN_DEFAULT
    shared = LG._clip(LG._sessions_for(span_k, session, st.shared, [], V.GGA), V.GGA)
    own = LG._clip(LG._sessions_for(span_k, session, st, [], V.GGA), V.GGA)
    sessions = sorted(set(shared) | set(own))
    sides = _read_sides(st, sessions, now, session, is_today)
    exits = st.exits_docs(sessions)
    if exits is None:
        raise LG.LedgerReadError("the audited exit grades could not be read")
    return {"span": span_k, "sessions": sessions, "sides": sides,
            "exits_by_id": {d.get("_id"): d for d in exits if isinstance(d, dict)}}


def compare_block(st, session: date, now, *, span: str = "", is_today: bool = False,
                  read: Optional[dict] = None) -> dict:
    """§3.6 [C5] — 🚩 original vs 🧪 audited on the 🏁's sessions (read_span's: the record start clips them). `read` =
    the tab's ONE read_span dict (2026-11-05); None → this block reads it itself (direct callers). Raises
    ledger.LedgerReadError on a read fault (the tab softens it to None)."""
    now = LG._aware(now)
    session = LG._as_date(session)
    if read is None:
        read = read_span(st, session, now, span=span, is_today=is_today)
    span_k = read["span"]
    sides = read["sides"]
    exits_by_id = read["exits_by_id"]
    oid = {r["id"] for r in sides["original"]}
    aid = {r["id"] for r in sides["audited"]}
    hid = {h["id"] for h in sides["held"]}
    adm = {r["id"] for r in sides.get("admitted") or [] if r["kind"] == ADMIT_KINDS[0]}   # ⊆ aid — 🧪 K3S rings
    original_only = len(oid - aid - hid)
    audited_only = len((aid | hid) - oid - adm)    # on this tab (audited or held) with no 🚩 row: the send failed
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
                      "admitted": len(adm - oid),          # 🧪 2026-11-09 K3S [C6]: 🧪-only rings with no 🚩 row
                      "text": V.word("compare_recon", vv, original_only=original_only, audited_only=audited_only)},
            "admitted": _admitted_block(sides.get("admitted") or [], oid),
            "per_rule_title": V.word("per_rule_title", vv),
            "per_rule": _per_rule(sides, exits_by_id, now, session, is_today),
            "by_rule_note": V.word("by_rule_note", vv),
            "by_day": _by_day(sides),
            "entry_weeks": weeks, "floor_weeks": floor, "floor_reached": reached,
            "unmeasured_text": (V.word("floor_reached", vv, n=weeks, floor=floor) if reached
                                else V.word("unmeasured", vv, floor=floor))}


def _admitted_block(rows: list, oid: set) -> dict:
    """🧪 2026-11-09 K3S [C4, C7, C8] — "🧪 only": the admitted rings (W / L / filled / no entry / not graded / mean R
    by GG's math — `_tally`, the 🔁 dedupe included) and the admitted holds (`held_by_counts` — the per-rule hold share,
    by count then id), `same_day_original` (an admitted ring whose id is also a 🚩 row), one row per record."""
    vv = V.GGA
    rule = AUD.K3S.id
    rang = [r for r in rows if r["kind"] == ADMIT_KINDS[0]]
    held = [r for r in rows if r["kind"] == ADMIT_KINDS[1]]
    c = _tally(rang)
    n = c["n"] + len(held)
    counts: dict = {}
    for h in held:
        for i in h.get("held_by") or []:
            counts[i] = counts.get(i, 0) + 1
    held_by_counts = dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    held_by_text = (V.word("admitted_held_by", vv, parts=" · ".join(f"{k} ×{v}" for k, v in held_by_counts.items()))
                    if held_by_counts else None)
    text = (V.word("admitted_line", vv, n=n, rule=rule, rang=c["n"], held=len(held), w=c["win"], l=c["loss"],
                   filled=c["filled"], u=c["unfilled"], pending=c["pending"], mr=_mean_text(c)) if n
            else V.word("admitted_empty", vv, rule=rule))
    out_rows = []
    for r in sorted(rows, key=lambda x: (x["date"], x["symbol"], _rank(x["setup"])), reverse=True):
        label = GT._setup_label(r["setup"])
        ids = list(r.get("held_by") or [])
        same = r.get("original_same_day") is True
        text_r = (f"{r['date']} · {r['symbol']} · {label} · 🧪 only by {r['rule']}"
                  + (f" · held by {', '.join(ids)}" if ids else " · rang in shadow")
                  + f" · {r.get('state_text') or '—'}"
                  + (f" · {V.word('admitted_same_day', vv)}" if same else ""))
        out_rows.append({"date": r["date"], "symbol": r["symbol"], "setup": r["setup"], "setup_label": label,
                         "rule": r["rule"], "kind": r["kind"], "held_by": ids, "outcome": r["state"],
                         "outcome_text": r.get("state_text"), "dup_of": r.get("dup_of"), "original_same_day": same,
                         "text": text_r})
    adm = {r["id"] for r in rang}
    return {"title": V.word("admitted_title", vv, reason=D.NOT_APLUS_REASON), "n": n, "rang": c["n"],
            "held": len(held), "filled": c["filled"], "win": c["win"], "loss": c["loss"], "unfilled": c["unfilled"],
            "pending": c["pending"], "mean_r": c["mean_r"], "same_day_original": len(adm & oid),
            "held_by_counts": held_by_counts, "held_by_text": held_by_text, "text": text, "rows": out_rows}


# ── 🏁 rows: 🚩's own A+ with the audit's call (2026-11-05, SPEC gg-track-parity §3.1) ────────────────────────────────
def row_audits(sides: dict, exits_by_id: dict) -> dict:
    """{original id: audit cell} for EVERY original row (a duplicate too — listed, never counted): the record on the
    row's own bar (_record_of — the one the per-rule table scores), its verdicts, its cell. An admitted record never
    lands on a 🚩 row (_unadmitted): a same-id 🚩 row reads "not judged" — the truth under one claim per name per day."""
    markers, claims = _unadmitted(sides)
    out: dict = {}
    for o in sides["original"]:
        rec = _record_of(o, markers, claims)
        v = _rec_verdicts(*rec) if rec is not None else None
        out[o["id"]] = _audit_cell(v, o.get("setup"), o["id"], exits_by_id or {})
    return out


def _audit_cell(v: Optional[dict], setup, rid: str, exits_by_id: dict) -> dict:
    """{state, text, sub_text, provisional} — held (ids only [C7]) / passed (the stored `aplus` [C6]; the exit-grade
    sub-line, or "no rule was on" when the claim was judged with every rule OFF) / not_judged (no record on the bar, or
    a record with no verdict)."""
    vv = V.GGA
    if v is not None and v.get("failed"):
        return {"state": AUDIT_STATES[1], "text": V.word("row_audit_held", vv, ids=", ".join(v["failed"])),
                "sub_text": None, "provisional": False}
    if v is not None and v.get("ok"):
        sub = _exit_line(rid, setup, exits_by_id) if v.get("rules") else V.word("row_audit_passed_none_on", vv)
        return {"state": AUDIT_STATES[0], "text": V.word("row_audit_passed", vv), "sub_text": sub,
                "provisional": False}
    return {"state": AUDIT_STATES[2], "text": V.word("row_audit_not_judged", vv),
            "sub_text": V.word("row_audit_not_judged_sub", vv), "provisional": False}


def _exit_line(rid: str, setup, exits_by_id: dict) -> Optional[str]:
    """The passed row's T3 / T5 exit grades in words ("T3 +2R: ✅ winner +2.0R · … · T5 21 EMA trail: …") — the SAME
    state engine _exit_rows reads (ledger._state_of; a missing column is "pending"); None when no exits doc exists."""
    doc = (exits_by_id or {}).get(rid)
    if not isinstance(doc, dict):
        return None
    vv = V.GGA
    cols = [("T3", k) for k in AUD.T3_R_MULTS] if setup in AUD.T3_SETUPS else []
    cols.append(("T5", None))
    bits = []
    for col_id, k in cols:
        g = doc.get(AUD.exit_col_key(col_id, k))
        g = g if isinstance(g, dict) else None
        state = LG._state_of(g) if g else "pending"
        word = EXIT_STATE_TEXT.get(state) or EXIT_STATE_TEXT["pending"]
        r = LG._num(g.get("r")) if g and state in LG.DECIDED else None
        tail = f" {r:+.1f}R" if r is not None else ""
        label = (V.word("row_exit_t3", vv, k=k) if col_id == "T3" else V.word("row_exit_t5", vv, ema=AUD.T5_EMA))
        bits.append(f"{label}: {word}{tail}")
    return " · ".join(bits)


def track_block(st, session: date, now, *, span: str = "", is_today: bool = False, today: Optional[dict] = None,
                broker_text_of=None, read: Optional[dict] = None) -> dict:
    """The 🧪 🏁: 🚩's served block over the SHARED store with GGA's clip / words / links, + the audit column (head
    "🧪 Audit" right after the Ticker). NEVER reads the audit itself [C1]: `read` is the tab's read_span dict, or None
    = the audit was not read this time → every row's cell is NOT_READ_CELL (the rows stay). Raises only what
    served_block raises (LedgerReadError on the SHARED ledger → the tab serves TRACK_RECORD_FAULT)."""
    block = LG.served_block(st.shared, session, now, span=span, is_today=is_today, today=today,
                            broker_text_of=broker_text_of, variant=V.GGA)
    heads = list(block["heads"])
    i = next(j for j, h in enumerate(heads) if h["key"] == LG.HEADS[0][0]) + 1
    heads.insert(i, {"key": AUDIT_HEAD_KEY, "label": V.word("ledger_audit_head", V.GGA)})
    block["heads"] = heads
    audits = None
    if isinstance(read, dict):
        try:
            audits = row_audits(read["sides"], read["exits_by_id"])
        except Exception as exc:                                    # noqa: BLE001 — [C1] fail VISIBLE, never empty
            log.warning("gajjala audited: row audits failed: %s", type(exc).__name__)
            audits = None
    for day in (block.get("days") or []) + ((block.get("aplus") or {}).get("days") or []):
        for r in day.get("rows") or []:                             # the same dicts in both lists — set in place
            r[AUDIT_HEAD_KEY] = (dict(NOT_READ_CELL) if audits is None
                                 else audits.get(r["id"]) or _audit_cell(None, r.get("setup"), r["id"], {}))
    block["counts_text"] = None                 # HIS CALL #29 default: no 🧠 row on this tab → no zero 🧠 lines
    block["kinds"] = None                       # HIS CALL #29: the 🎯 chip is a no-op on an A+-only list
    block["kind_empty_text"] = None
    return block


__all__ = ["overlay_reads", "held_block", "audited_block", "compare_block", "read_span", "track_block", "row_audits",
           "EXIT_STATE_TEXT", "NOT_READ_CELL", "AUDIT_HEAD_KEY", "AUDIT_STATES", "NO_ORIGINAL", "NO_ORIGINAL_TEXT"]
