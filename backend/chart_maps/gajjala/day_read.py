"""🌫️ Day read — today's market-condition reads from the pre-registered shadow day tags. INFORMATION ONLY.

Ajay 2026-11-14: "Also lately I am seeing very choppy market but Gajjals examples are very bullish"; 2026-11-15 "yes"
to "do you want a 'choppy day' label on the Gajjala tab now, just as information? Making it a gate would wait for that
recorder's result." ONE engine: scripts.shadow_day_tags_lib.compute over scripts.shadow_day_tags_probe.build_inputs —
the recorder's own code. The CODE is byte-identical with the nightly record; the INPUTS are not: this read runs during
the session on the grades on file, the record runs after the close, so GD3w / GD4 can read differently there once the
day's grades land (served `note`). Never a gate, a push, a sort, a filter or a lane input; never reads the recorder's
store; every cutoff is the prereg's (THEIRS / MINE as the lib's SOURCE_TAGS label them). Computed ONCE per 🚩 GG5 pass
(run.py, own try, A8 token check first) into gajjala_state "day_read"; served by gajjala.tab.build (GG5, GG1) and
the 🥇 tab's build (see the doc) to the primary owner only.

Docs: docs/chart_maps/gajjala_day_read_2026_11_15.md.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from scripts import shadow_day_tags_lib as LIB          # the lib is stdlib-only: safe at import time

from . import audited_rules as AR
from . import variant as V

# the probe (pandas, pymongo, chart_maps.gajjala.*) and portfolio.store are imported LAZILY inside inputs_for()

log = logging.getLogger(__name__)

STATE_ID = "day_read"                                    # the ONE gajjala_state doc (GG5's)
# 2026-11-15 — Ajay "yes" to warming QQQ / IWM for GD7: one minute-bar fetch per symbol per session, after 10:30 ET,
# kept in this gajjala_state doc (never intraday_cache — load_intraday never caches the live day). The nightly recorder
# does NOT read it (its inputs are the frozen prereg's).
WARM_ID = "day_read_index"
FORMS = LIB.TAG_FORMS                                    # the chip order = the lib's order
# [C3] "reads" = the lib's own noun (LIB.READS); each form IS one read, so the count never double-counts.
# His word for the day lives in the ✨ label and the doc only — the prereg defines no such measure.
HEAD_TEXT = "🌫️ Day read: {on} of {read} pre-registered reads on · information only"
HEAD_NONE_READ_TEXT = "🌫️ Day read: nothing read yet · information only"
HEAD_MISSING_TAIL = " · {n} not read"
HEAD_PENDING_TAIL = " · {n} read later today"
HEAD_SESSION_TAIL = " · last session {session}"          # [C9] the board's own words (tab.SESSION_BADGE "last session")
HEAD_ABSENT_TEXT = "🌫️ Day read: no read on file for this session yet — it is read on every {cad}-minute 🚩 pass"
STATE_TEXT = {"on": "on", "off": "off", "missing": "not read", "pending": "reads at {hhmm} ET"}
FOLD_TEXT = "the {n} reads"                              # [C-R5] the <details> summary — served, never typed in the FE
# [C10] the in-sample read stated as the doc states it (docs/gajjala/shadow_day_tags_2026_11_11.md "In-sample prior");
# no claim that a forward record exists on disk.
CAPTION = ("Information only — not a gate, not measured. In the {n} sessions studied no read flagged the worse days; "
           "GD6b read the opposite way (not significant after correction); LD3i and LD9 had too few days.")
# [C1] the honesty line for the numbers he reads intraday
NOTE_TEXT = ("Read during the session from the grades on file (through {grades_through}). The nightly record is taken "
             "after the close, so GD3w and GD4 can read differently there once the day's grades land.")
NOTE_NO_GRADES_TEXT = ("Read during the session; no 🏁 grade on file yet. The nightly record is taken after the close, "
                       "so GD3w and GD4 can read differently there once the day's grades land.")
# [C2] the RULE, by name — never a date
READ_DATE_TEXT = ("Read once, when every page holds {weeks} recorded entry weeks forward from {from_} (the prereg's "
                  "MEASURE_FLOOR_WEEKS rule); nothing is read before then.")
IN_SAMPLE_SESSIONS = 22                                  # pinned == the recorder fixture's session count
_BY_T2 = ("GD4_by1030", "GD6b_by1030", "GD7_by1030")


def _t2() -> str:
    return AR.T2_FIRST_HOUR_END_ET.strftime("%H:%M")


def words() -> dict:
    """form -> the read's plain words (what ON means), the form in brackets. Cut times come from the constants."""
    t2, pre, rth = _t2(), LIB.hm_text(LIB.PRE_CUT), LIB.hm_text(LIB.GD4_PRE_CUT)
    return {"GD3w_pre": "most setups failed this week (GD3w)",
            "GD4_pre": f"risk halved after losses (GD4, before the {rth} open)",
            "GD4_by1030": f"risk halved after losses (GD4, by {t2})",
            "GD6b_pre": f"fewer runners than usual (GD6b, the {pre} pass)",
            "GD6b_by1030": f"fewer runners than usual (GD6b, the {t2} pass)",
            "GD7_by1030": f"QQQ and IWM both red into {t2} (GD7)",
            "LD3i_pre": "IWM 9 EMA under 21 (LD3i)",
            "LD9_pre": "big techs under 9 & 21 (LD9)"}


def read_at(form: str) -> Optional[tuple]:
    """The formula's own read cut (display + the pending rule only): None for the prior-session forms."""
    if form == "GD4_pre":
        return LIB.GD4_PRE_CUT
    if form == "GD6b_pre":
        return LIB.PRE_CUT
    if form in _BY_T2:
        return LIB.hm_of(_t2())
    return None


def value_text(form: str, tag) -> Optional[str]:
    """The tag's value in words; None for a missing / pending / unreadable tag."""
    if not isinstance(tag, dict) or tag.get("status") != "ok":
        return None
    v, d = tag.get("value"), tag.get("detail") or {}
    try:
        if form == "GD3w_pre":
            return f"{d['failed']} failed · {d['held']} held ({v:.0%} failed)"
        if form in ("GD4_pre", "GD4_by1030"):
            return f"risk ×{v:g}"
        if form in ("GD6b_pre", "GD6b_by1030"):
            return f"{v} names at the pass · median {d['median']}"
        if form == "GD7_by1030":
            return str(v)
        if form == "LD3i_pre":
            return f"9 − 21 EMA {v:+.2f}"
        if form == "LD9_pre":
            return f"{v} big techs weak"
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _asof_str(v) -> str:
    """[C4] an ISO datetime string → ET "%Y-%m-%d %H:%M ET"; a date-only or non-ISO string stays as is; a dict →
    "key:value" pairs joined by ", " (None entries skipped); anything else → str()."""
    if isinstance(v, str):
        if "T" in v:
            t = LIB.et_of(v)
            if t is not None:
                return t.strftime("%Y-%m-%d %H:%M") + " ET"
        return v
    if isinstance(v, dict):
        return ", ".join(f"{k}:{_asof_str(x)}" for k, x in v.items() if x is not None)
    return str(v)


def grades_through_et(doc) -> Optional[str]:
    """[C1] asof.gg5_last_graded_at rendered ET, or None."""
    g = ((doc or {}).get("asof") or {}).get("gg5_last_graded_at") if isinstance(doc, dict) else None
    return _asof_str(g) if isinstance(g, str) else None


def read_date_text() -> str:
    """[C2] the prereg's read-date RULE by name — never a date."""
    return READ_DATE_TEXT.format(weeks=AR.MEASURE_FLOOR_WEEKS, from_=LIB.FORWARD_FROM)


def _iso(session) -> str:
    return session.isoformat() if isinstance(session, date) else str(session)


# ── compute (the pass) ──────────────────────────────────────────────────────────────────────────────────────────────
def inputs_for(now: datetime, *, session: date, db=None) -> dict:
    """The recorder's inputs blob for `session`, built by the probe's own build_inputs. [C5] `db` is never
    truth-tested (a pymongo Database raises on bool): `None` → portfolio.store._get_db(); `None` back → RuntimeError."""
    from scripts import shadow_day_tags_probe as PR     # noqa: PLC0415 — pandas / pymongo / chart_maps: lazy
    if db is None:
        from portfolio import store as PS               # noqa: PLC0415 — lazy (the house Mongo handle)
        db = PS._get_db()
    if db is None:
        raise RuntimeError("day read: no db")
    return PR.build_inputs(db, now, only={_iso(session)})


def tags_of(inputs: dict, session) -> dict:
    """== LIB.compute(inputs, session) — nothing added."""
    return LIB.compute(inputs, _iso(session))


def _fetch_bars(sym: str, session: date) -> list:
    """Today's rth minute bars for `sym` through daytrading.data.load_intraday (it never caches the live day), shaped
    like an intraday_cache doc's bars. Empty on any failure."""
    from daytrading import data as DD                   # noqa: PLC0415 — pandas: lazy
    df = DD.load_intraday(sym, session, include_premarket=False)
    if df is None or df.empty:
        return []
    out = []
    for ts, r in df.iterrows():
        out.append({"ts_utc": ts.isoformat(), "open": float(r["open"]), "high": float(r["high"]),
                    "low": float(r["low"]), "close": float(r["close"]), "volume": float(r["volume"]),
                    "session": r.get("session")})
    return out


def _complete(kept: list, sess: str) -> bool:
    """The cut holds the last minute before 10:30 (its bar starts at 10:29 ET) — a fetch the provider has not caught up
    on is never stored, so the session's read is never frozen on a short tape."""
    t = LIB.et_of(kept[-1][0])
    last = (datetime.combine(date.fromisoformat(sess), AR.T2_FIRST_HOUR_END_ET) - timedelta(minutes=1)).time()
    return t is not None and t.date().isoformat() == sess and t.time() >= last


def warm_index(st, inputs: dict, now: datetime, session: date, *, fetch=None) -> dict:
    """GD7's QQQ / IWM bars for TODAY when intraday_cache has none: after the 10:30 ET cut only, read from the WARM_ID
    doc, else fetched ONCE per symbol (a cut that reaches 10:29 is stored; a failed, empty or short fetch is retried next
    pass). Fills
    inputs["index_intraday"] and sets asof qqq_last_date / iwm_last_date to the session for a warmed symbol. Any other
    session, a pre-cut clock or a cache hit → inputs untouched."""
    from scripts import shadow_day_tags_probe as PR     # noqa: PLC0415 — lazy
    sess = _iso(session)
    at = now if now.tzinfo is not None else now.replace(tzinfo=LIB.UTC)
    et = at.astimezone(LIB.ET)
    if st is None or sess != et.date().isoformat() or et.time() < AR.T2_FIRST_HOUR_END_ET:
        return inputs
    intra = inputs.setdefault("index_intraday", {})
    need = [s for s in LIB.INDEX_SYMS if not intra.get(f"{s}|{sess}")]
    if not need:
        return inputs
    doc = st.get_state(WARM_ID)
    doc = doc if isinstance(doc, dict) and doc.get("session") == sess else {"session": sess, "bars": {}}
    bars = dict(doc.get("bars") or {})
    fetched = False
    for s in need:
        if not bars.get(s):
            try:
                kept = PR.cut_bars((fetch or _fetch_bars)(s, session), sess)
            except Exception:                           # noqa: BLE001 — a raising fetch never costs the other 7 reads
                log.warning("day read: %s 10:30 warm fetch failed", s, exc_info=True)
                kept = []
            if kept and _complete(kept, sess):
                bars[s], fetched = kept, True
        if bars.get(s):
            intra[f"{s}|{sess}"] = bars[s]
            inputs.setdefault("asof", {})[f"{s.lower()}_last_date"] = sess
    if fetched:
        st.set_state(WARM_ID, {"session": sess, "bars": bars, "fetched_at": at.astimezone(LIB.UTC)})
    return inputs


def compute(now: datetime, session: date, *, db=None, st=None, fetch=None) -> dict:
    inputs = warm_index(st, inputs_for(now, session=session, db=db), now, session, fetch=fetch)
    at = now if now.tzinfo is not None else now.replace(tzinfo=LIB.UTC)
    return {"session": _iso(session), "computed_at": at.astimezone(LIB.UTC), "tags": tags_of(inputs, session),
            "asof": inputs.get("asof"), "constants": inputs.get("constants"),
            "inputs_sha256": LIB.sha256_hex(LIB.inputs_blob(inputs)), "forms": list(FORMS)}


def run_step(st, now: datetime, session: date) -> Optional[dict]:
    """The pass hook: ONE compute, ONE gajjala_state write. Never swallows — run.py's own try does."""
    doc = compute(now, session, st=st)
    st.set_state(STATE_ID, doc)
    return doc


def load_doc(gg5_store) -> Optional[dict]:
    d = gg5_store.get_state(STATE_ID)
    return d if isinstance(d, dict) and d else None


# ── serve ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _aware_et(x) -> Optional[datetime]:
    """A stored instant → aware ET. pymongo hands back naive UTC; a string goes through the lib's et_of."""
    if isinstance(x, datetime):
        return (x if x.tzinfo is not None else x.replace(tzinfo=LIB.UTC)).astimezone(LIB.ET)
    if isinstance(x, str):
        return LIB.et_of(x)
    return None


def _counts0() -> dict:
    return {"on": 0, "off": 0, "read": 0, "missing": 0, "pending": 0}


def served_block(doc: Optional[dict], session: date, now: datetime) -> dict:
    """The `day_read` payload block (pure). `absent` when no doc, the doc's session is not the board's, or its compute
    clock is unreadable. `pending` iff the session is today ET AND the doc was computed before the form's read cut —
    keyed on the doc's own computed_at, never the GET clock. The tab decides owner → None."""
    sess = _iso(session)
    n_now = now if now.tzinfo is not None else now.replace(tzinfo=LIB.UTC)
    is_today = sess == n_now.astimezone(LIB.ET).date().isoformat()
    tail = "" if is_today else HEAD_SESSION_TAIL.format(session=sess)
    caption = CAPTION.format(n=IN_SAMPLE_SESSIONS)
    computed = _aware_et(doc.get("computed_at")) if isinstance(doc, dict) else None
    tags = doc.get("tags") if isinstance(doc, dict) else None
    if not isinstance(doc, dict) or doc.get("session") != sess or computed is None or not isinstance(tags, dict):
        return {"state": "absent", "session": sess, "is_today": is_today, "computed_at_et": None,
                "grades_through_et": None,
                "head": HEAD_ABSENT_TEXT.format(cad=V.cadence_sec(V.GG5) // 60) + tail,
                "counts": _counts0(), "fold_text": None, "chips": [], "note": None, "caption": caption,
                "read_date_text": read_date_text(), "tags": {}}
    w = words()
    counts = _counts0()
    chips, served_tags = [], {}
    stamp = "read %s ET" % computed.strftime("%Y-%m-%d %H:%M")
    for form in FORMS:
        tag = tags.get(form) if isinstance(tags.get(form), dict) else None
        ra = read_at(form)
        if is_today and ra is not None and computed < LIB.at_cut(sess, ra):
            state = "pending"
        elif tag is not None and tag.get("status") == "ok":
            state = "on" if tag.get("on") is True else "off"
        else:
            state = "missing"
        counts[state] += 1
        served_tags[form] = None if state == "pending" else tag
        asof = ""
        if state != "pending" and tag is not None:
            for k, v in (tag.get("asof") or {}).items():
                s = _asof_str(v) if v is not None else ""
                if s:
                    asof += " · %s %s" % (k, s)
        chips.append({
            "form": form, "state": state, "text": w[form],
            "state_text": (STATE_TEXT[state].format(hhmm=LIB.hm_text(ra)) if state == "pending"
                           else STATE_TEXT[state]),
            "value_text": value_text(form, tag) if state in ("on", "off") else None,
            "why": (tag or {}).get("why") if state == "missing" else None,
            "asof_text": stamp + asof,
            "source": LIB.SOURCE_TAGS[form],
            "reads_at": LIB.hm_text(ra) if ra is not None else None,
        })
    counts["read"] = counts["on"] + counts["off"]
    head = (HEAD_TEXT.format(on=counts["on"], read=counts["read"]) if counts["read"] > 0 else HEAD_NONE_READ_TEXT)
    if counts["missing"]:
        head += HEAD_MISSING_TAIL.format(n=counts["missing"])
    if counts["pending"]:
        head += HEAD_PENDING_TAIL.format(n=counts["pending"])
    head += tail
    gt = grades_through_et(doc)
    return {"state": "read", "session": sess, "is_today": is_today,
            "computed_at_et": computed.strftime("%H:%M") + " ET", "grades_through_et": gt,
            "head": head, "counts": counts, "fold_text": FOLD_TEXT.format(n=len(chips)), "chips": chips,
            "note": NOTE_TEXT.format(grades_through=gt) if gt else NOTE_NO_GRADES_TEXT,
            "caption": caption, "read_date_text": read_date_text(), "tags": served_tags}
