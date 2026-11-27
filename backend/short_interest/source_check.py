"""🩳 FLOAT SOURCES — the float we divide by beside a second DATED float (2026-11-26). PURE: no I/O, no clock.

THE ASK (Ajay 2026-11-26 ~21:20 ET, verbatim)
  "Also the Float share count issue and SI discrepancy happened too many times need to do something about it"

What this module is (spec floatguard rev 2 §3.4): `compare(block, basis_doc)` puts the float the served block divides
by (Yahoo's, read date) beside the second float the share-basis doc holds (`mfloat` — Massive's free float, effective
date; written by short_interest.share_basis), rebased across the splits ON FILE, same-unit listing types only, and
ONLY when the splits on file reach back to both dates. `apply(block, cmp)` folds the answer into the block's `basis`
under three keys (SOURCE_KEYS). Every compared name gets ONE neutral sentence — both counts, both dates, both %, the
spread; never "agree". When the second float puts an EXTREME name under the EXTREME cut ("contested" — the tier ladder
is the test, as in the 🩳 list's floats_disagree) the chip gains SHORT_SOURCES. The word EXTREME is NOT changed under
the built default (`flag`); `hold` / `supported` are built and are HIS CALL #1.

No ground truth: none of the contested names was checked against a filing. A count of two providers differing — not a
signal, not a forecast. UNMEASURED. `read` is imported lazily inside functions (read imports this module).
Doc: docs/short_interest/float_accuracy_guard_2026_11_26.md.
"""
from __future__ import annotations

import math
from typing import Optional

from short_interest import basis_math as BM

FLAG_SOURCES = "sources_disagree"
SHORT_SOURCES = BM.EMOJI_WARN + " sources disagree"
ROW_FLOAT_SOURCES = "Float sources"
SRC_YAHOO, SRC_MASSIVE = "yahoo", "massive"
SOURCE_WORDS = {SRC_YAHOO: "Yahoo", SRC_MASSIVE: "Massive"}
SAME_VALUE_REL = BM.CARRY_REL_TOL            # by name: two counts this close are one number
CONTEST_MIN_REL = None                       # HIS CALL #4 — None = any difference above SAME_VALUE_REL can contest
EXTREME_CONTEST = "flag"                     # HIS CALL #1 — unknown value behaves as "off"
EXTREME_CONTEST_MODES = ("off", "flag", "hold", "supported")
EXTREME_CONTEST_BY = "any_dated"             # HIS CALL #3 — unknown value behaves as "any_dated"
EXTREME_CONTEST_BY_MODES = ("any_dated", "not_older")
COMPARE_TYPES = BM.SEC_COVER_SAME_UNIT_TYPES # by name: any other listing type is not compared
STATES = ("no_float", "unread", "none", "units", "no_splits", "window", "split_day", "compared", "contested")
SOURCE_KEYS = ("float_sources", "sources_compared", "extreme_contest")
EXAMPLE_CUTS = (0.10, 0.25, 0.50)            # the doc / CLI table only — no behaviour reads it
STATE_NO_SI = "no_si"                        # audit rows only: a name with no chip
# Wording only (spread_words): a ratio under SPREAD_PCT_UNDER prints "N% apart", under SPREAD_ONE_DP_UNDER "N.N×".
SPREAD_PCT_UNDER = 2
SPREAD_ONE_DP_UNDER = 10

TEXT_SPLITS_START = " — not compared: the splits on file start %s, after %s."
TEXT_SPLITS_UNDATED = " — not compared: the splits on file carry no start date."
TEXT_UNITS = " — not compared: listing type %s."
TEXT_NO_SPLITS = " — not compared: the splits read is not on file."
TEXT_SPLIT_DAY = " — not compared: a split executed the day one of them was dated."
TEXT_NONE = " · %s: none on file — one source only."
TEXT_UNREAD = " · %s: not read%s."
TEXT_NO_FLOAT = "No %% of float is shown, so nothing is compared · %s."
TEXT_USES = " The %% shown uses %s's."
TEXT_LARGER = " — larger than the %s shares outstanding on file"
TEXT_FILING = " %s dated before the %s %s %s on file."
TEXT_UNDER = " %s's float puts it under %g%%, where %s starts"
TAIL_FLAG = " — the word is not changed."
TAIL_HOLD = " %s is held at %s: %s's float puts it under %g%%."
TAIL_SUPPORTED = " The word shown is the one %s's float gives."
HOVER_HEAD = ROW_FLOAT_SOURCES + " — "


# ───────────────────────────────────────────── the modes, read at CALL time
def contest_mode() -> str:
    return EXTREME_CONTEST if EXTREME_CONTEST in EXTREME_CONTEST_MODES else "off"


def contest_by() -> str:
    return EXTREME_CONTEST_BY if EXTREME_CONTEST_BY in EXTREME_CONTEST_BY_MODES else "any_dated"


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def min_rel() -> float:
    """The spread a contest must exceed: CONTEST_MIN_REL when it is a number, else SAME_VALUE_REL."""
    return float(CONTEST_MIN_REL) if _is_number(CONTEST_MIN_REL) else SAME_VALUE_REL


def rank(t) -> int:
    """The ladder rank; a None / unknown tier ranks BELOW Low (-1) [C7]."""
    from short_interest import read as SR
    return SR.TIER_ORDER.index(t) if t in SR.TIER_ORDER else -1


def rel_of(a, b) -> Optional[float]:
    """max / min - 1 on two positive counts, else None. The ONLY division in this file."""
    a, b = BM._pos(a), BM._pos(b)
    if a is None or b is None:
        return None
    return max(a, b) / min(a, b) - 1


def spread_words(rel) -> str:
    """Wording only: `3% apart` · `under 1% apart` · `4.2× apart` · `2,317× apart`."""
    if not _is_number(rel) or rel < 0:
        return ""
    ratio = rel + 1
    if ratio < SPREAD_PCT_UNDER:
        pct = rel * 100
        return "under 1% apart" if pct < 0.5 else "%d%% apart" % int(round(pct))
    if ratio < SPREAD_ONE_DP_UNDER:
        return "%.1f× apart" % ratio
    return "%s× apart" % format(int(round(ratio)), ",")


# ───────────────────────────────────────────── leaves
def _count(v) -> Optional[int]:
    """A share count: a real int / float (never a bool or a string), finite and > 0."""
    if not _is_number(v) or v <= 0:
        return None
    n = int(round(v))
    return n if n > 0 else None


def _mfloat(basis_doc) -> Optional[dict]:
    mf = basis_doc.get("mfloat") if isinstance(basis_doc, dict) else None
    return mf if isinstance(mf, dict) else None


def _basis(block) -> dict:
    x = block.get("basis") if isinstance(block, dict) else None
    return x if isinstance(x, dict) else {}


def _pct(p) -> str:
    from short_interest import read as SR
    return SR._pct_tier(p)


def _used_words(fl, fa, pf) -> str:
    s = "%s %s (read %s)" % (SOURCE_WORDS[SRC_YAHOO], format(fl, ","), BM._md(fa))
    return s + (" = " + _pct(pf) if _is_number(pf) else "")


def _other_plain(m_sh, m_as) -> str:
    return "%s %s (as of %s)" % (SOURCE_WORDS[SRC_MASSIVE], format(m_sh, ","), BM._md(m_as))


def _other_words(m_sh, m_as, rebased, pct_m, so) -> str:
    s = "%s %s (as of %s" % (SOURCE_WORDS[SRC_MASSIVE], format(rebased, ","), BM._md(m_as))
    if rebased != m_sh:
        s += "; %s as published, split-adjusted" % format(m_sh, ",")
    s += ")"
    if _is_number(pct_m):
        s += " = " + _pct(pct_m)
    if so and rebased > so:
        s += TEXT_LARGER % format(so, ",")
    return s


def _label(f) -> str:
    try:
        return BM.filing_label(f)
    except Exception:                                          # noqa: BLE001 — a junk row prints its form
        return str(f.get("form"))


def _filing_clause(block, d_used, d_other) -> str:
    """[C11] A 📄 filing on file dated AFTER a count's date (the newest such row; a same-day filing never counts)."""
    rows = []
    for f in _basis(block).get("filings") or []:
        if isinstance(f, dict) and isinstance(f.get("form"), str) and f["form"] and BM._iso(f.get("filed")):
            rows.append(f)
    older, newer = min(d_used, d_other), max(d_used, d_other)
    after = [f for f in rows if BM._iso(f["filed"]) > older]
    if not after:
        return ""
    f = max(after, key=lambda r: BM._iso(r["filed"]))
    filed = BM._iso(f["filed"])
    if filed > newer:
        who = "Both counts are"
    else:
        who = "%s's count is" % SOURCE_WORDS[SRC_MASSIVE if d_other < d_used else SRC_YAHOO]
    return TEXT_FILING % (who, BM.EMOJI_FILING, _label(f), BM._md(filed))


def _row(key, shares, published, as_of, date_kind, pct, tier, used) -> dict:
    return {"key": key, "label": SOURCE_WORDS[key], "shares": shares, "published": published, "as_of": as_of,
            "date_kind": date_kind, "pct": pct, "tier": tier, "used": bool(used)}


def _float_used(block) -> Optional[tuple]:
    """(float_shares, float_asof, pct_of_float) when the block shows a % of float, else None — compare's step 1 test
    and audit_row's fallback read ONE definition (2026-11-27)."""
    if not isinstance(block, dict):
        return None
    fl, fa = _count(block.get("float_shares")), BM._iso(block.get("float_asof"))
    pf = block.get("pct_of_float") if _is_number(block.get("pct_of_float")) else None
    if block.get("headline_basis") != "float" or fl is None or fa is None or pf is None:
        return None
    return fl, fa, pf


def _used_row(block, fu) -> dict:
    return _row(SRC_YAHOO, fu[0], fu[0], fu[1], "read", fu[2], block.get("tier"), True)


# ───────────────────────────────────────────── the comparison
def compare(block, basis_doc) -> Optional[dict]:
    """None when `basis_doc` is not a dict or holds no dict `mfloat`. Else {state, sources, rel, contest, text, row}:
    `row` = the panel sentence (the hover prints HOVER_HEAD + it); `text` = the flag text, set only when a flag is to be
    appended (contested under flag / hold / supported). First match of §3.4 steps 1-10. PURE, never raises on junk."""
    mf = _mfloat(basis_doc)
    if mf is None or not isinstance(block, dict):
        return None
    from short_interest import read as SR
    mode, by = contest_mode(), contest_by()
    st = BM._status(mf)
    m_sh, m_as = _count(mf.get("shares")), BM._iso(mf.get("as_of"))
    usable = st == "ok" and m_sh is not None and m_as is not None
    other = _row(SRC_MASSIVE, None, m_sh if usable else None, m_as if usable else None, "as_of", None, None, False)
    out = {"state": None, "sources": [other], "rel": None, "contest": None, "text": None, "row": None}

    fu = _float_used(block)
    # 1. no % of float shown: the second float is listed, nothing is compared
    if fu is None:
        if usable:
            m = _other_plain(m_sh, m_as)
        elif st == "none":
            m = "%s: none on file" % SOURCE_WORDS[SRC_MASSIVE]
        else:
            m = "%s: not read" % SOURCE_WORDS[SRC_MASSIVE]
        out.update(state="no_float", row=TEXT_NO_FLOAT % m)
        return out
    fl, fa, pf = fu
    used = _used_row(block, fu)
    out["sources"] = [used, other]
    head = "float: " + _used_words(fl, fa, pf)
    # 2 / 3. the second float is not usable
    if st == "none":
        out.update(state="none", row=head + TEXT_NONE % SOURCE_WORDS[SRC_MASSIVE])
        return out
    if not usable:
        last = BM._et(mf.get("error_at"))
        out.update(state="unread", row=head + TEXT_UNREAD % (SOURCE_WORDS[SRC_MASSIVE],
                                                             " (last try failed %s)" % last if last else ""))
        return out
    head += " · " + _other_plain(m_sh, m_as)
    ref, sp = BM._sub(basis_doc, "ref"), BM._sub(basis_doc, "splits")
    rtype = ref.get("type") if isinstance(ref.get("type"), str) and ref.get("type") else None
    # 4. same-unit listing types only
    if rtype not in COMPARE_TYPES:
        out.update(state="units", row=head + TEXT_UNITS % (rtype or "n/a"))
        return out
    # 5. the splits read must be held
    if BM._status(sp) != "ok":
        out.update(state="no_splits", row=head + TEXT_NO_SPLITS)
        return out
    # 6. the splits on file must reach back to BOTH dates [C1] — never contested
    since = BM._iso(sp.get("since"))
    if since is None:
        out.update(state="window", row=head + TEXT_SPLITS_UNDATED)
        return out
    if m_as < since or fa < since:
        whose = "the second float's date" if m_as < since else "the date of the float divided by"
        out.update(state="window", row=head + TEXT_SPLITS_START % (BM._md(since), whose))
        return out
    # 7. a split ON either date: which side a count is on is not known
    rebased = BM._rb(m_sh, m_as, fa, BM._rows(sp.get("rows")))
    if rebased is None:
        out.update(state="split_day", row=head + TEXT_SPLIT_DAY)
        return out
    # 8. the second % on THE tier engine (same ladder, same shares-outstanding confirmation, same stale rule)
    pct_m = SR.pct_of(block.get("si_shares"), rebased) if rebased > 0 else None
    tier_m = SR.si_tier(dict(block, pct_of_float=pct_m))[0]
    # 9. the spread
    rel = rel_of(fl, rebased)
    differs = rel is not None and rel > min_rel()
    other.update(shares=rebased, pct=pct_m, tier=tier_m)
    out["rel"] = rel
    so = _count(block.get("shares_outstanding"))
    spread = spread_words(rel)
    base = ("float: %s · %s%s.%s" % (_used_words(fl, fa, pf), _other_words(m_sh, m_as, rebased, pct_m, so),
                                     (" · " + spread) if spread else "", TEXT_USES % SOURCE_WORDS[SRC_YAHOO])
            + _filing_clause(block, fa, m_as))
    # 10. contested: an EXTREME name the second float puts under the EXTREME cut
    contested = (block.get("tier") == SR.TIER_EXTREME and differs and rank(tier_m) < rank(SR.TIER_EXTREME)
                 and (by != "not_older" or m_as >= fa))
    if not contested:
        out.update(state="compared", row=base)
        return out
    if mode == "hold":
        to = SR.TIER_HIGH
    elif mode == "supported":
        to = tier_m if rank(tier_m) >= 0 and rank(tier_m) < rank(SR.TIER_HIGH) else SR.TIER_HIGH
    else:
        to = SR.TIER_EXTREME
    out["contest"] = {"mode": mode, "from": SR.TIER_EXTREME, "to": to, "by": by, "pct": pct_m, "shares": rebased,
                      "as_of": m_as}
    words, cut = SR.TIER_WORDS, SR.SIC.SI_HIGH_PCT
    under = TEXT_UNDER % (SOURCE_WORDS[SRC_MASSIVE], cut, words[SR.TIER_EXTREME])
    if mode == "off":
        out.update(state="contested", row=base + under + ".")
        return out
    if mode == "hold":
        tail = TAIL_HOLD % (words[SR.TIER_EXTREME], words[SR.TIER_HIGH], SOURCE_WORDS[SRC_MASSIVE], cut)
    elif mode == "supported":
        tail = TAIL_SUPPORTED % SOURCE_WORDS[SRC_MASSIVE]
    else:
        tail = under + TAIL_FLAG
    text = SHORT_SOURCES + " — " + base + tail
    out.update(state="contested", text=text, row=text)
    return out


def apply(block, cmp) -> None:
    """Fold one `compare` answer into the block — everything built first, then assigned (atomic). The three
    SOURCE_KEYS on `block["basis"]`; on a flagged contest ONE flag appended LAST; under hold / supported the tier."""
    if not isinstance(block, dict) or not isinstance(cmp, dict):
        return
    bb = block.get("basis")
    if not isinstance(bb, dict) or cmp.get("state") not in STATES:
        return
    rows = [dict(r) for r in (cmp.get("sources") or []) if isinstance(r, dict)]
    sc = {"state": cmp["state"], "rel": cmp.get("rel"), "text": cmp.get("row")}
    ec = dict(cmp["contest"]) if isinstance(cmp.get("contest"), dict) else None
    flags = tier = None
    if ec is not None and ec.get("mode") in ("flag", "hold", "supported") and isinstance(cmp.get("text"), str):
        held = bb.get("flags") if isinstance(bb.get("flags"), list) else []
        flags = list(held) + [BM._flag(FLAG_SOURCES, BM.EMOJI_WARN, SHORT_SOURCES, cmp["text"])]
        if ec["mode"] in ("hold", "supported"):
            tier = ec.get("to")
    bb["float_sources"] = rows
    bb["sources_compared"] = sc
    bb["extreme_contest"] = ec
    if flags is not None:
        bb["flags"] = flags
    if tier is not None:
        block["tier"] = tier


# ───────────────────────────────────────────── the served sentences
def _flagged(block) -> bool:
    return any(isinstance(f, dict) and f.get("key") == FLAG_SOURCES for f in (_basis(block).get("flags") or []))


def _text(block) -> Optional[str]:
    sc = _basis(block).get("sources_compared")
    t = sc.get("text") if isinstance(sc, dict) else None
    return t if isinstance(t, str) and t else None


def title_sentences(block) -> list:
    """The neutral hover sentence; empty when the flag was appended (its text already rides the title)."""
    try:
        t = _text(block)
        if t is None or _flagged(block):
            return []
        return [HOVER_HEAD + (t if t.endswith(".") else t + ".")]
    except Exception:                                          # noqa: BLE001 — the hover never costs the block
        return []


def rows(block) -> list:
    """ONE panel row {"k": ROW_FLOAT_SOURCES, "v": the sentence}, or none."""
    try:
        t = _text(block)
        return [{"k": ROW_FLOAT_SOURCES, "v": t}] if t is not None else []
    except Exception:                                          # noqa: BLE001
        return []


def rules_sentence() -> str:
    """The last sentence of basis_math.rules_sentence(), built from the constants and the mode at call time."""
    from short_interest import read as SR
    s = ("A second dated float (%s's free float) is read beside %s's and both are in the hover with their dates"
         % (SOURCE_WORDS[SRC_MASSIVE], SOURCE_WORDS[SRC_YAHOO]))
    mode = contest_mode()
    if mode == "off":
        return s + "."
    s += "; when it puts an %s name under the cut the chip adds '%s'" % (SR.TIER_WORDS[SR.TIER_EXTREME], SHORT_SOURCES)
    if mode == "hold":
        return s + " and the word stops at %s." % SR.TIER_WORDS[SR.TIER_HIGH]
    if mode == "supported":
        return s + " and the word is the second float's."
    return s + " and the word stays."


# ───────────────────────────────────────────── the audit row + the cut table (short_interest.source_audit)
def audit_row(block, basis_doc, groups=None) -> dict:
    """FROZEN (§3.6). One row per name; a name with no chip is state `no_si` with no numbers (never 0)."""
    b = block if isinstance(block, dict) else None
    doc = basis_doc if isinstance(basis_doc, dict) else None
    row = {"symbol": (b or {}).get("symbol") or (doc or {}).get("_id"), "groups": list(groups or []),
           "state": STATE_NO_SI, "chip": None, "tier": None, "contested": False, "held": False, "differ": False,
           "settlement_date": None, "si_shares": None, "used": None, "other": None, "float_rel": None,
           "count_used": None, "counts": [], "count_rel": None, "checked_at": None}
    if b is None or b.get("status") == "no_record" or b.get("si_shares") is None or not b.get("chip"):
        return row
    bb = _basis(b)
    sc = bb.get("sources_compared") if isinstance(bb.get("sources_compared"), dict) else None
    srcs = [r for r in (bb.get("float_sources") or []) if isinstance(r, dict)]
    ec = bb.get("extreme_contest") if isinstance(bb.get("extreme_contest"), dict) else None
    state = sc.get("state") if sc and sc.get("state") in STATES else "unread"
    rel = sc.get("rel") if sc and _is_number(sc.get("rel")) else None
    counts = [dict(r) for r in (bb.get("share_counts") or []) if isinstance(r, dict)]
    dated = [r["shares"] for r in counts
             if r.get("key") in ("record", "yahoo", "sec_cover") and _count(r.get("shares")) and BM._iso(r.get("as_of"))]
    so = _count(b.get("shares_outstanding"))
    fu = _float_used(b)
    row.update({
        "state": state, "chip": b.get("chip"), "tier": b.get("tier"),
        "contested": ec is not None, "held": bool(ec and ec.get("to") != ec.get("from")),
        "differ": bool(state in ("compared", "contested") and rel is not None and rel > SAME_VALUE_REL),
        "settlement_date": b.get("settlement_date"), "si_shares": b.get("si_shares"),
        # no float_sources (no second-float sub on file): the float the chip divides by, from the block itself
        "used": next((dict(r) for r in srcs if r.get("used")), None) or (_used_row(b, fu) if fu else None),
        "other": next((dict(r) for r in srcs if not r.get("used")), None),
        "float_rel": rel,
        "count_used": ({"shares": so, "as_of": b.get("shares_asof"), "source": b.get("shares_source")} if so else None),
        "counts": counts,
        "count_rel": rel_of(max(dated), min(dated)) if len(dated) >= 2 else None,
        "checked_at": bb.get("checked_at") or (doc or {}).get("checked_at"),
    })
    return row


def cut_table(rows, cuts=EXAMPLE_CUTS) -> dict:
    """Over audit-shaped rows ({state, tier, other: {tier}, float_rel, held?}): how many compared floats differ by more
    than each cut, and how many EXTREME names the second float puts under the EXTREME cut. `cut None` = SAME_VALUE_REL.
    Counts are over rows whose state is compared / contested. Display / CLI only."""
    from short_interest import read as SR
    rs = [r for r in (rows or []) if isinstance(r, dict)]
    comp = [r for r in rs if r.get("state") in ("compared", "contested")]
    win = [r for r in rs if r.get("state") == "window"]
    out = {"n": len(rs), "compared": len(comp), "window": len(win), "not_compared": len(rs) - len(comp) - len(win),
           "cuts": []}
    for c in (None,) + tuple(cuts or ()):
        thr = SAME_VALUE_REL if c is None else float(c)
        d = [r for r in comp if _is_number(r.get("float_rel")) and r["float_rel"] > thr]
        names = sorted(str(r.get("symbol") or r.get("s") or "") for r in d
                       if (r.get("held") or r.get("tier") == SR.TIER_EXTREME)
                       and rank((r.get("other") or {}).get("tier")) < rank(SR.TIER_EXTREME))
        out["cuts"].append({"cut": c, "differ": len(d), "contested": len(names), "names": names})
    return out
