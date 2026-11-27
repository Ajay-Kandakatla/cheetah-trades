"""🩳 % of float — dilution, splits, filings (2026-11-24). PURE: the split math, the float track, the verdict, the flag words.

THE ASK (Ajay 2026-11-24, verbatim, in order — after the offer "add a check so that when Yahoo's float is far below
the SEC-filed share count, or older than a split, the 🩳 % stops using it, falls back to % of shares outstanding with
that figure's date, and says why."):
  "Yeah please"
  "Make sure we are looking for Dilution.."
  "Also split related events and filing so we flag them in the right way"

What this module is: given ONE short-interest record (client.SI_COLL) and ONE share-basis doc (share_basis.SB_COLL,
the FROZEN shape of spec §3.1), `verdict` says whether the float on file can head the 🩳 chip, which dated count the
% of shares outstanding uses instead, how the change vs the prior settlement reads across a split, and the plain flags
(⚠️ ✂️ 📄 ❔) the served chip / title / rows / EXTREME note carry. `short_interest.read.si_block(.., basis=)` is the
only caller on the read path. No I/O, no clock: `today` is passed in. `read` helpers are imported lazily inside
functions (read imports this module at load).

Rules that bind (spec sidilute REV 2):
  * Nothing is refused, rebased or replaced unless the splits read is held (`splits.status == "ok"`; held rows count
    even when the last try failed — a failed re-check never un-refuses a float) [C1].
  * The float's side of a split comes from the TRACK (`basis_asof`), never from the Yahoo read date; the track is
    re-run here at read time [C3]. A float split-carried within CARRY_REL_TOL keeps its first-seen date and drops its
    paired Yahoo count — the baseline becomes the SEC cover in force when it was first seen [C4].
  * A share count that fell to SR.SUSPECT_MAX_SHARES_OUT_FRACTION (by name, read at call time) or less with no split
    on file is a ❔ flag and never a denominator [C8].
  * An ADR's SEC cover counts ordinary shares: covers are compared only for SEC_COVER_SAME_UNIT_TYPES [P1].
  * Every rebase is tested for None before it is compared and rounded to whole shares first [C11].
  * [2026-11-24 later, "Is GMEX float accurate?"] A Yahoo float dated LATER than the record's float_asof that differs
    from it is the float the % divides by (`newer_float`), once the splits read is held [C1]; the older read never
    wins; the ⚠️ float updated flag names both counts and dates. It is used ONLY for that division and for the
    split-side check: the dilution-filing window, the share-growth check and the float track keep the REPLACED
    float's own date and count (fix after the verifier's SRTM / AAOI / 8-K 3.02 finding).
Display only; UNMEASURED. Nothing here gates, sorts, sizes or enters a lane.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

# HIS CALL #1 — one of FLOAT_STALE_MODES; an unknown value → nothing is refused for dilution.
FLOAT_STALE_WHEN = "added_exceeds_float"
FLOAT_STALE_MODES = ("any_increase", "added_exceeds_float", "tier_moves")
# 🩳 2026-11-26 (spec sishares §3.2) HIS CALL #1 — one of FLOAT_FRESH_MODES; an unknown value behaves as "off" (today's
# refusal). When a newer Yahoo float read WITH or AFTER the larger share count would be refused as stale:
#   "off"                   always refused (the 11-24 rule).
#   "issuance_before_float" not refused ONLY when an SEC filing dated strictly BEFORE the older float's date prints the
#                           exact number of shares added — the count read with the older float was already out of date.
#   "co_dated_no_filing"    not refused when no 📄 dilution event is on file since the older float and every filing
#                           read answered (`filings_known`) — rests on an absence.
FLOAT_FRESH_WHEN = "issuance_before_float"
FLOAT_FRESH_MODES = ("off", "issuance_before_float", "co_dated_no_filing")
FLOAT_FRESH_MODE_WORDS = {
    "off": "never — it is refused as stale",
    "issuance_before_float": ("only when an SEC filing dated before the older float was read states the exact number "
                              "of shares added"),
    "co_dated_no_filing": ("when no dilution filing is on file since the older float was read and every filing read "
                           "answered"),
}
# HIS CALL #17 [C4] — measured: split-scaled float matches sit at <= 1.8e-5 relative error, the next nearest 3.0e-3.
CARRY_REL_TOL = 1e-4
# HIS CALL #19 [P1] — any other Massive reference type: the SEC cover is not compared.
SEC_COVER_SAME_UNIT_TYPES = ("CS", "OS")
# The count-fell cut is SR.SUSPECT_MAX_SHARES_OUT_FRACTION, read by name at CALL time (HIS CALL #18) [C8].

# [C13] EXACT form families — no bare prefix (S-1 must not catch S-11).
# 📄 2026-11-26 (spec sitrack §3.1, A2): S-11 / S-11MEF (real-estate registrations — WHLR's 11/10 S-11) appended. The
# EDGAR form-type list has S-11, S-11/A and S-11MEF; there is no F-11 form, so nothing is added for it.
FILING_REGISTRATION_FORMS = ("S-1", "S-1MEF", "S-3", "S-3ASR", "S-3MEF", "S-4",
                             "F-1", "F-1MEF", "F-3", "F-3ASR", "F-3MEF", "F-4",
                             "S-11", "S-11MEF")
FILING_PROSPECTUS_PREFIX = "424B"
FILING_8K_FORM = "8-K"
FILING_8K_DILUTION_ITEMS = ("3.02",)
FILING_8K_CHARTER_ITEMS = ("5.03", "3.03")
KIND_REGISTRATION, KIND_PROSPECTUS, KIND_UNREGISTERED, KIND_CHARTER = (
    "registration", "prospectus", "unregistered_sale", "charter")
# 📄 2026-11-26 (spec sishares §3.2) — a 6-K the SEC full-text search matched for issuance words (`sec.fts`, written by
# share_basis / sec_fts) is a dilution filing of its own kind. `filing_kind` is NOT changed: a bare 6-K names no kind.
FILING_6K_FORM = "6-K"
FTS_ISSUANCE = "issuance"
FTS_KNOWN_STATUSES = ("ok", "none_6k")
KIND_FOREIGN_ISSUANCE = "foreign_issuance"
DILUTION_KINDS = (KIND_REGISTRATION, KIND_PROSPECTUS, KIND_UNREGISTERED, KIND_FOREIGN_ISSUANCE)

REFUSE_SPLIT_SAME_DAY, REFUSE_SPLIT, REFUSE_DILUTED = "split_same_day", "split", "diluted"
REFUSAL_ORDER = (REFUSE_SPLIT_SAME_DAY, REFUSE_SPLIT, REFUSE_DILUTED)

ORIGIN_SI_DOC, ORIGIN_SEED, ORIGIN_CARRIED = "si_doc", "seed", "carried"

# Flag keys, emoji and words. The chip shows each flag's `short`; the title / rows carry its `text`.
FLAG_FLOAT_STALE, FLAG_COUNT_STALE, FLAG_SPLIT, FLAG_FILING, FLAG_COUNT_FELL, FLAG_UNCHECKED = (
    "float_stale", "count_stale", "split", "filing", "count_fell", "unchecked")
EMOJI_WARN, EMOJI_SPLIT, EMOJI_FILING, EMOJI_CHECK = "⚠️", "✂️", "📄", "❔"
SHORT_FLOAT_STALE = EMOJI_WARN + " float stale"
SHORT_COUNT_STALE = EMOJI_WARN + " shares up %s×"
SHORT_SPLIT = EMOJI_SPLIT + " split %s"
SHORT_SPLIT_DUE = EMOJI_SPLIT + " split due %s"
SHORT_FILING = EMOJI_FILING + " %s %s"
# 📄 2026-11-26 (spec sitrack §3.1, A1 + A3) — the chip counts filing EVENTS, never copies, and says what it left out.
SHORT_FILING_SAME_DAY = EMOJI_FILING + " %s %s · same day"
TEXT_FILING_COPIES = (" — %d prospectus %s of same-day reports not counted (one document filed under several "
                      "registrations)")
TEXT_FILING_SAME_DAY = " — %s filed the same day %s was read; which came first is not known"
ANCHOR_WORDS_FLOAT, ANCHOR_WORDS_COUNT = "the float", "the share count"
TEXT_FILING_UNCHECKED = " — %d prospectus %s not yet checked for copies"
TEXT_FILING_CAPPED = " — only the newest %d filings are read"
# ⚠️ 2026-11-26 (spec sitrack §3.3, A6) — the no-usable-float baseline raised to an SEC cover count dated on or before
# the record's own count.
TEXT_COUNT_STALE_SEC = ("%s %s× more shares than the %s count dated on or before the record: %s (%s, %s) vs "
                        "%s (%s) — the %% uses the newer count; the record itself carried %s (%s)")
TITLE_SHARE_COUNTS_HEAD = "Share counts: the record carried %s (%s), under the %s count %s (%s) already dated"
TITLE_SHARE_COUNTS_GROWTH = " — growth is read from the SEC count: %s (%s, %s) = %s×"
SHORT_COUNT_FELL = EMOJI_CHECK + " shares fell %s×"
SHORT_UNCHECKED = EMOJI_CHECK + " share count unchecked"
SHORT_LAST_FAILED = EMOJI_CHECK + " last check failed"
SHORT_DILUTION_UNCHECKED = EMOJI_CHECK + " dilution unchecked"
TEXT_CHECK_FAILED = (EMOJI_CHECK + " share count check failed — the % shown uses the counts on the short-interest "
                     "record")
# 🩳 2026-11-24 later — Ajay: "Is GMEX float accurate?" A NEWER dated Yahoo float (the basis doc's `yahoo` read of
# shares_cache, dated later than the record's float_asof) that differs from the record's float is the one the % divides
# by — no size cut (any difference, any later date). The older read never wins. Dilution keeps the replaced float's
# date and count. See `newer_float` and `verdict`.
FLAG_FLOAT_UPDATED = "float_updated"
SOURCE_YAHOO = "yahoo"
SHORT_FLOAT_UPDATED = EMOJI_WARN + " float updated"
TEXT_FLOAT_UPDATED = SHORT_FLOAT_UPDATED + " — %s (Yahoo %s) replaced %s (%s)"   # new, its M/D, old, its M/D
# 🩳 2026-11-26 (spec sishares §3.2) — a newer float judged fresh (FLOAT_FRESH_WHEN), the 6-K words, the archive LINK.
SEC_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/%d/%s/%s"     # a LINK for his browser; never fetched
TEXT_COUNT_BEFORE_FLOAT = ("%s %s× more shares than the count read with the older float: %s (%s, %s) vs %s (%s) — "
                           "%s filed %s, before that float was read, states %s shares (%s + %s = %s), so the older "
                           "count was already out of date; the %% of float uses the newer float %s (Yahoo %s)")
TEXT_COUNT_WITH_FLOAT = ("%s %s× more shares than when the older float was read: %s (%s, %s) vs %s (%s) — the newer "
                         "float %s (Yahoo %s) was read with that count and no dilution filing is on file since, so "
                         "the %% of float uses it")
TEXT_FILING_SAME_DAY_6K = " — %d same-day 6-K not counted (the report of an offering already counted that day)"
TEXT_CHECK_FTS = " · 6-K issuance search (SEC full-text): %s"            # the 4th clause of the check sentence
ROW_SHARE_COUNTS, ROW_SHARE_ISSUANCE = "Share counts", "Share issuance"
SHARE_COUNT_LABELS = {"record": "Short-interest record", "yahoo": "Yahoo, current row", "sec_cover": "SEC %s cover",
                      "massive_class": "Massive ticker details, this share class",
                      "massive_weighted": "Massive ticker details, all classes converted", "filing": "%s %s states"}
SHARE_COUNT_WORDS = {"record": "short-interest record", "yahoo": "Yahoo", "massive_class": "Massive, this class",
                     "massive_weighted": "Massive, all classes"}
TEXT_NO_AS_OF = " — the provider gives no as-of"
TEXT_NO_COVER = "SEC cover: none on file"
FLAG_ROW_LABEL = {FLAG_FLOAT_STALE: "Float stale", FLAG_COUNT_STALE: "Shares up", FLAG_SPLIT: "Split",
                  FLAG_FILING: "Dilution filing", FLAG_COUNT_FELL: "Shares fell", FLAG_UNCHECKED: "Check",
                  FLAG_FLOAT_UPDATED: "Float updated"}
FLOAT_STALE_MODE_WORDS = {
    "any_increase": "any newer, larger share count than the one read with the float",
    "added_exceeds_float": "more shares added since the float was read than the float itself held",
    "tier_moves": "a newer share count that would move the tier word",
}
SOURCE_NAME = {"ref": "the Massive ticker read", "sec": "the SEC", "splits": "the splits read"}
ET_ZONE = "America/New_York"


# ───────────────────────────────────────────── input guards (a bad leaf is missing, never a NaN)
def _num(v) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _pos(v) -> Optional[float]:
    f = _num(v)
    return f if (f is not None and f > 0) else None


def _pos_int(v) -> Optional[int]:
    f = _pos(v)
    return int(round(f)) if f is not None else None


def _nonneg_int(v) -> Optional[int]:
    f = _num(v)
    return int(round(f)) if (f is not None and f >= 0) else None


def _iso(v) -> Optional[str]:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date().isoformat()
    except (TypeError, ValueError):
        return None


def _md(iso) -> str:
    d = _iso(iso)
    return "%d/%d" % (int(d[5:7]), int(d[8:10])) if d else "n/a"


def _ts(v) -> Optional[datetime]:
    """A stored UTC timestamp (ISO string or datetime) → aware datetime, else None."""
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if not isinstance(v, str) or not v:
        return None
    s = v.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _ts_iso(v) -> Optional[str]:
    d = _ts(v)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


def _et(v) -> Optional[str]:
    """`M/D HH:MM` in US Eastern for a stored UTC timestamp, else None."""
    d = _ts(v)
    if d is None:
        return None
    try:
        from zoneinfo import ZoneInfo
        d = d.astimezone(ZoneInfo(ET_ZONE))
    except Exception:                                          # noqa: BLE001 — no tz database: print UTC, say so
        d = d.astimezone(timezone.utc)
        return "%d/%d %02d:%02d UTC" % (d.month, d.day, d.hour, d.minute)
    return "%d/%d %02d:%02d ET" % (d.month, d.day, d.hour, d.minute)


def _sub(doc, key) -> dict:
    v = doc.get(key) if isinstance(doc, dict) else None
    return v if isinstance(v, dict) else {}


def _rows(raw) -> list:
    """Split rows: execution_date ISO, from > 0, to > 0, from != to; ascending. Bad rows dropped."""
    out = []
    for r in raw if isinstance(raw, list) else []:
        if not isinstance(r, dict):
            continue
        e, f, t = _iso(r.get("execution_date")), _pos(r.get("split_from")), _pos(r.get("split_to"))
        if e is None or f is None or t is None or f == t:
            continue
        out.append({"execution_date": e, "split_from": _int_if_whole(f), "split_to": _int_if_whole(t)})
    out.sort(key=lambda r: r["execution_date"])
    return out


def _int_if_whole(f: float):
    return int(f) if float(f).is_integer() else f


def _covers(raw) -> list:
    """SEC cover rows {as_of, shares, form, filed}: positive finite shares + a date; ascending, one per as_of."""
    by = {}
    for c in raw if isinstance(raw, list) else []:
        if not isinstance(c, dict):
            continue
        a, s = _iso(c.get("as_of")), _pos_int(c.get("shares"))
        if a is None or s is None:
            continue
        row = {"as_of": a, "shares": s, "form": str(c.get("form") or "") or None, "filed": _iso(c.get("filed"))}
        held = by.get(a)
        if held is None or (row["filed"] or "") >= (held["filed"] or ""):
            by[a] = row
    return [by[k] for k in sorted(by)]


def _filings(raw) -> list:
    out = []
    for f in raw if isinstance(raw, list) else []:
        if not isinstance(f, dict):
            continue
        form, filed = f.get("form"), _iso(f.get("filed"))
        if not isinstance(form, str) or not form.strip() or filed is None:
            continue
        items = f.get("items")
        if isinstance(items, (list, tuple)):
            items = ",".join(str(x) for x in items if isinstance(x, (str, int, float)) and not isinstance(x, bool))
        elif not isinstance(items, str):
            items = ""
        # 📄 2026-11-26 (spec sishares §3.2, C14) — the full-text marker is RE-EMITTED, so `_filings(_filings(raw))`
        # equals `_filings(raw)`: kept only on a 6-K / 6-K/A, dropped on any other form.
        fts = FTS_ISSUANCE if (f.get("fts") == FTS_ISSUANCE and _form_base(form) == FILING_6K_FORM) else None
        out.append({"form": form.strip(), "filed": filed, "items": items,
                    "kind": KIND_FOREIGN_ISSUANCE if fts else filing_kind(form, items),
                    "doc": _opt_str(f.get("doc")), "file": _opt_str(f.get("file")), "accn": _opt_str(f.get("accn")),
                    "with": _opt_str(f.get("with")), "fts": fts})
    out.sort(key=lambda f: f["filed"], reverse=True)          # stable: the stored order stands inside one day
    return out


def _form_base(form) -> Optional[str]:
    """An SEC form name upper-cased with one trailing '/A' dropped (6-K/A → 6-K), else None."""
    if not isinstance(form, str):
        return None
    base = form.strip().upper()
    if base.endswith("/A"):
        base = base[:-2].strip()
    return base or None


def _opt_str(v) -> Optional[str]:
    return v.strip() if isinstance(v, str) and v.strip() else None


def filing_label(f) -> str:
    """The chip's name for one filing row: an 8-K Item 3.02 reads '8-K 3.02', every other form its own name."""
    if filing_kind(f["form"], f["items"]) == KIND_UNREGISTERED and f["form"].upper().startswith(FILING_8K_FORM):
        return "%s %s" % (FILING_8K_FORM, FILING_8K_DILUTION_ITEMS[0])
    return f["form"]


def _event(f, anchor: str, copies: int) -> dict:
    return {"kind": f["kind"], "form": f["form"], "filed": f["filed"], "items": f["items"], "label": filing_label(f),
            "same_day": f["filed"] == anchor, "copies": int(copies)}


def filing_events(filings, anchor, cap=None) -> dict:
    """📄 2026-11-26 (spec sitrack §3.1, A1 + A3) — the dilution and charter EVENTS filed ON or after `anchor`. PURE,
    never raises on junk (rows go through `_filings`, so raw stored rows and `_filings` rows both work).

    E1 the 424B rows of ONE day that carry the same `doc` are one document (its registration files = the distinct
    `file`s). E2 a document under two or more files on a day the issuer also filed a report (`with`) is that report
    re-filed: no event, every row a copy (the report itself is judged by `filing_kind` as before). Any other document
    = one event, its other rows copies. A 424B row with no `doc` (a row stored before 2026-11-26) = one event, counted
    in `unchecked`. Every other row = one event. Order: filed DESC, then the stored order.
    📄 2026-11-26 (spec sishares §3.2, C13) — a 6-K the full-text search marked (kind KIND_FOREIGN_ISSUANCE) filed on a
    day that yields a COUNTED event of another dilution kind is the report of that offering: not an event, counted in
    `n_filings` and `n_reports`. On an E2 day (the 424B rows are the report re-filed, no 424B event) the 6-K IS the
    event. Otherwise it is one event.
    → {"events", "charter" (each [{kind, form, filed, items, label, same_day, copies}]), "n_filings" (dilution-kind
    rows — what the chip used to count), "n_copies", "unchecked", "n_reports", "cap" (the kept-row cap, else None)}."""
    a = _iso(anchor)
    out = {"events": [], "charter": [], "n_filings": 0, "n_copies": 0, "unchecked": 0, "n_reports": 0,
           "cap": _pos_int(cap)}
    if a is None:
        return out
    order, docs = [], {}
    for f in _filings(filings):
        if f["filed"] < a or f["kind"] not in DILUTION_KINDS + (KIND_CHARTER,):
            continue
        if f["kind"] == KIND_PROSPECTUS and f["doc"]:
            k = (f["filed"], f["doc"])
            g = docs.get(k)
            if g is None:
                g = docs[k] = {"rows": [], "files": set()}
                order.append(("doc", g))
            g["rows"].append(f)
            if f["file"]:
                g["files"].add(f["file"])
        else:
            order.append(("row", f))
    counted_days = set()                       # C13: days with a counted event of another dilution kind
    for what, x in order:
        if what == "doc":
            g = x["rows"]
            if not (len(x["files"]) >= 2 and any(r["with"] for r in g)):
                counted_days.add(g[0]["filed"])
        elif x["kind"] in DILUTION_KINDS and x["kind"] != KIND_FOREIGN_ISSUANCE:
            counted_days.add(x["filed"])
    for what, x in order:
        if what == "doc":
            rs = x["rows"]
            out["n_filings"] += len(rs)
            if len(x["files"]) >= 2 and any(r["with"] for r in rs):          # E2 — a report re-filed
                out["n_copies"] += len(rs)
                continue
            out["n_copies"] += len(rs) - 1
            out["events"].append(_event(rs[0], a, len(rs) - 1))
            continue
        if x["kind"] == KIND_CHARTER:
            out["charter"].append(_event(x, a, 0))
            continue
        out["n_filings"] += 1
        if x["kind"] == KIND_FOREIGN_ISSUANCE and x["filed"] in counted_days:     # C13 — the offering's report
            out["n_reports"] += 1
            continue
        if x["kind"] == KIND_PROSPECTUS:                                     # a 424B with no `doc`
            out["unchecked"] += 1
        out["events"].append(_event(x, a, 0))
    return out


# ───────────────────────────────────────────── the split math
def side(d_iso, e_iso) -> str:
    """Which side of a split executing on `e_iso` the date `d_iso` is on."""
    d, e = _iso(d_iso), _iso(e_iso)
    return "pre" if d < e else ("post" if d > e else "same")


def _factor(r) -> float:
    return float(r["split_to"]) / float(r["split_from"])


def rebase(value, d_from, d_to, splits) -> Optional[float]:
    """`value` counted on `d_from`, in the share units of `d_to`: the product of to/from (pre→post) or from/to
    (post→pre). None when a split executes ON either date, or on a missing value / date."""
    v = _num(value)
    a0, b0 = _iso(d_from), _iso(d_to)
    if v is None or a0 is None or b0 is None:
        return None
    for r in splits or []:
        a, b = side(a0, r["execution_date"]), side(b0, r["execution_date"])
        if "same" in (a, b):
            return None
        if a == "pre" and b == "post":
            v = v * _factor(r)
        elif a == "post" and b == "pre":
            v = v / _factor(r)
    return v


def _rb(value, d_from, d_to, splits) -> Optional[int]:
    """`rebase` rounded to whole shares (or None) — every rebased count is compared only in this form [C11]."""
    v = rebase(value, d_from, d_to, splits)
    return int(round(v)) if v is not None else None


def same_side(d1, d2, splits) -> bool:
    """No split between the two dates and none ON either date."""
    a0, b0 = _iso(d1), _iso(d2)
    if a0 is None or b0 is None:
        return False
    for r in splits or []:
        a, b = side(a0, r["execution_date"]), side(b0, r["execution_date"])
        if a == "same" or b == "same" or a != b:
            return False
    return True


def day_after(d_iso) -> str:
    return (date.fromisoformat(_iso(d_iso)) + timedelta(days=1)).isoformat()


def split_words(split_from, split_to) -> str:
    """(5,1) "1-for-5 reverse split" · (1,2) "2-for-1 split" · (2.8,1) "1-for-2.8 reverse split" (to-for-from)."""
    f, t = float(split_from), float(split_to)
    return "%g-for-%g %ssplit" % (t, f, "reverse " if t < f else "")


def ratio_words(r) -> str:
    r = float(r)
    if r >= 10:
        return "%.0f" % r
    if r >= 1.1:
        return "%.1f" % r
    return "%.3f" % r


def filing_kind(form, items) -> Optional[str]:
    """[C13] The dilution / charter kind of one SEC filing, on EXACT form families, else None."""
    if not isinstance(form, str):
        return None
    base = form.strip().upper()
    if base.endswith("/A"):
        base = base[:-2].strip()
    if base in FILING_REGISTRATION_FORMS:
        return KIND_REGISTRATION
    if base.startswith(FILING_PROSPECTUS_PREFIX):
        return KIND_PROSPECTUS
    if base == FILING_8K_FORM:
        its = _items(items)
        if any(i in its for i in FILING_8K_DILUTION_ITEMS):
            return KIND_UNREGISTERED
        if any(i in its for i in FILING_8K_CHARTER_ITEMS):
            return KIND_CHARTER
    return None


def _items(items) -> list:
    if isinstance(items, (list, tuple)):
        items = ",".join(str(x) for x in items)
    if not isinstance(items, str):
        return []
    return [x.strip() for x in items.split(",") if x.strip()]


# ───────────────────────────────────────────── the float track [C3][C4]
def _record_fields(rec: dict) -> tuple:
    legacy = rec.get("v") != 2
    F = None if legacy else _pos_int(rec.get("float_shares"))
    Fa = None if legacy else _iso(rec.get("float_asof"))
    P = _pos_int(rec.get("shares_outstanding"))
    if legacy:
        Pa = None
        f = _num(rec.get("fetched_at"))
        if f is not None and f > 0:
            try:
                Pa = datetime.fromtimestamp(f, tz=timezone.utc).date().isoformat()
            except (OverflowError, OSError, ValueError):
                Pa = None
    else:
        Pa = _iso(rec.get("shares_asof"))
    return F, Fa, P, (Pa if P else None)


def _norm_track(prev) -> Optional[dict]:
    if not isinstance(prev, dict):
        return None
    value, since = _pos_int(prev.get("value")), _iso(prev.get("since"))
    if value is None or since is None:
        return None
    shares = _pos_int(prev.get("shares"))
    return {"value": value, "since": since, "shares": shares,
            "shares_asof": _iso(prev.get("shares_asof")) if shares else None,
            "basis_asof": _iso(prev.get("basis_asof")) or since,
            "origin": prev.get("origin") if isinstance(prev.get("origin"), str) else ORIGIN_SI_DOC,
            "carried": _rows(prev.get("carried"))}


def newer_float(si_record, basis_doc) -> Optional[dict]:
    """[2026-11-24 later] The basis doc's Yahoo float when it is DATED LATER than the record's float and DIFFERS from it,
    else None: {shares, as_of, source "yahoo", paired_shares (Yahoo's shares outstanding from the same row, or None),
    replaced_shares, replaced_asof}. None (the record's float stands) on: no record float or no record float date (a
    legacy record), no Yahoo float, a Yahoo float that is missing / NaN / zero / negative / bool, an undated Yahoo
    read, a Yahoo read dated ON or BEFORE the record's float date, an equal count — or no held splits read [C1]:
    nothing is replaced unless the splits are on file, since a split between the two reads is what the split rules
    must judge (held rows count even after a failed try). PURE."""
    if not isinstance(si_record, dict) or not isinstance(basis_doc, dict):
        return None
    F, Fa, _P, _Pa = _record_fields(si_record)
    yh = basis_doc.get("yahoo")
    if F is None or Fa is None or not isinstance(yh, dict) or _status(_sub(basis_doc, "splits")) != "ok":
        return None
    yf, ya = _pos_int(yh.get("float_shares")), _iso(yh.get("as_of"))
    if yf is None or ya is None or ya <= Fa or yf == F:
        return None
    return {"shares": yf, "as_of": ya, "source": SOURCE_YAHOO, "paired_shares": _pos_int(yh.get("shares_outstanding")),
            "replaced_shares": F, "replaced_asof": Fa}


def track_update(prev, si_record, splits) -> Optional[dict]:
    """The float's track: when this value was first seen and which splits it was carried across. `splits` = the held
    split rows (future-dated included) or None when the splits were never read."""
    if not isinstance(si_record, dict):
        return None
    F, Fa, P, Pa = _record_fields(si_record)
    if F is None or Fa is None:
        return None
    fresh = {"value": F, "since": Fa, "shares": P, "shares_asof": Pa if P else None, "basis_asof": Fa,
             "origin": ORIGIN_SI_DOC, "carried": []}
    p = _norm_track(prev)
    if p is None:
        return fresh
    if p["value"] == F:
        return p                                   # the first-seen date stands across re-warms
    if splits is None:
        return fresh
    cands = [r for r in _rows(splits) if r["execution_date"] >= p["basis_asof"]]
    f = 1.0
    for k, r in enumerate(cands, start=1):
        f *= _factor(r)
        target = p["value"] * f
        if abs(F - target) <= CARRY_REL_TOL * target:
            return {"value": F, "since": p["since"], "shares": None, "shares_asof": None,
                    "basis_asof": day_after(r["execution_date"]), "origin": ORIGIN_CARRIED,
                    "carried": p["carried"] + cands[:k]}
    return fresh


# ───────────────────────────────────────────── triggers
def stale_trigger(si, base, paired, newer) -> bool:
    """The refusal cut of FLOAT_STALE_WHEN (read at call time), all four on ONE split basis. Unknown mode → False."""
    from short_interest import read as SR
    base, paired, newer = _pos(base), _pos(paired), _pos(newer)
    if base is None or paired is None or newer is None:
        return False
    mode = FLOAT_STALE_WHEN
    if mode == "any_increase":
        return newer > paired
    if mode == "added_exceeds_float":
        return (newer - paired) > base
    if mode == "tier_moves":
        s = _num(si)
        den = base + newer - paired
        if s is None or s < 0 or den <= 0:
            return False
        return SR.tier_of(round(s / base * 100, 2)) != SR.tier_of(round(s / den * 100, 2))
    return False


def change_across_split(si, s_iso, prev_si, prev_iso, executed) -> Optional[dict]:
    """[C2] The change vs the prior settlement when a split executed between (or on) the two settlements."""
    si, prev_si = _num(si), _num(prev_si)
    S, prevS = _iso(s_iso), _iso(prev_iso)
    if si is None or prev_si is None or S is None or prevS is None or prev_si <= 0:
        return None
    rows = [r for r in _rows(executed) if prevS <= r["execution_date"] <= S]
    if not rows:
        return None
    splits = [{"execution_date": r["execution_date"], "split_from": r["split_from"], "split_to": r["split_to"],
               "words": split_words(r["split_from"], r["split_to"])} for r in rows]
    adj = rebase(prev_si, prevS, S, _rows(executed))
    if adj is None or adj <= 0:
        on = next((r for r in splits if r["execution_date"] in (S, prevS)), splits[0])
        return {"pct": None, "prev_adj": None, "same_day": True, "splits": splits,
                "words": "the %s executed %s, a settlement day, and which side of it that count is on is not known"
                         % (on["words"], _md(on["execution_date"]))}
    named = " and ".join("the %s %s" % (r["words"], _md(r["execution_date"])) for r in splits)
    return {"pct": round((si - adj) / adj * 100, 1), "prev_adj": int(round(adj)), "same_day": False,
            "splits": splits,
            "words": "%s %s the %s counted then into %s of today's shares"
                     % (named, "turns" if len(splits) == 1 else "turn", format(int(round(prev_si)), ","),
                        format(int(round(adj)), ","))}


# ───────────────────────────────────────────── 🩳 2026-11-26 (spec sishares §3.2 / §3.4) — fresh floats, 6-Ks, counts
_ACCN_RE = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
_DOC_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_CIK_RE = re.compile(r"[0-9]{1,10}")


def _exact_int(v) -> Optional[int]:
    """A positive whole count as stored (an int, never a bool / float / string) — compared to the share, never
    rounded."""
    return v if (isinstance(v, int) and not isinstance(v, bool) and v > 0) else None


def fts_of(sec) -> dict:
    """The SEC full-text search sub-doc `sec.fts` (spec §3.1) when it is a dict, else {}."""
    v = sec.get("fts") if isinstance(sec, dict) else None
    return v if isinstance(v, dict) else {}


def filings_known(sec) -> bool:
    """[C1] True ONLY when every filing read answered: the SEC read is ok / none with no error and no kept-row cap, and
    the 6-K full-text search is in FTS_KNOWN_STATUSES with no error and no cap. A missing, failed, blocked or switched
    off read is never "no filing"."""
    if not isinstance(sec, dict) or _status(sec) not in ("ok", "none") or sec.get("error") or sec.get("filings_cap"):
        return False
    fts = fts_of(sec)
    return _status(fts) in FTS_KNOWN_STATUSES and not fts.get("error") and not fts.get("cap")


def _number_of(fts, growth) -> tuple:
    """(n, 6-K hits) of the exact-number answer when it was asked for THIS growth (n = to − from, to the share), else
    (None, [])."""
    num = fts.get("number") if isinstance(fts, dict) else None
    if not isinstance(num, dict) or not isinstance(growth, dict):
        return None, []
    fs, ts = _exact_int(growth.get("from_shares")), _exact_int(growth.get("to_shares"))
    n, nf, nt = _exact_int(num.get("n")), _exact_int(num.get("from")), _exact_int(num.get("to"))
    if fs is None or ts is None or n is None or nf is None or nt is None:
        return None, []
    if n != ts - fs or nf != fs or nt != ts:
        return None, []
    hits = []
    for h in num.get("hits") if isinstance(num.get("hits"), list) else []:
        if not isinstance(h, dict) or _form_base(h.get("form")) != FILING_6K_FORM:
            continue
        filed = _iso(h.get("filed"))
        if filed is None:
            continue
        hits.append({"accn": _opt_str(h.get("accn")), "filed": filed, "doc": _opt_str(h.get("doc")),
                     "form": h["form"].strip()})
    hits.sort(key=lambda h: h["filed"])
    return n, hits


def issuance_proof(sec, growth, anchor, basis_date, executed) -> Optional[dict]:
    """[C6] {"n", "accn", "filed", "doc", "form"} — the OLDEST 6-K the SEC full-text search found printing the exact
    number of shares this growth added, filed STRICTLY before `anchor` (the older float's date) on the same split side
    as `basis_date`; else None. Needs the SEC read ok / none and the full-text read ok (a held answer with `error` set
    still counts — a filed document does not change). PURE."""
    if not isinstance(sec, dict) or _status(sec) not in ("ok", "none"):
        return None
    fts = fts_of(sec)
    if _status(fts) != "ok":
        return None
    a = _iso(anchor)
    n, hits = _number_of(fts, growth)
    if a is None or n is None:
        return None
    for h in hits:                                             # oldest first
        if h["filed"] < a and same_side(h["filed"], basis_date, executed):
            return dict(h, n=n)
    return None


def float_fresh(upd, growth, sec, events, *, anchor, basis_date, executed) -> Optional[dict]:
    """[C1][C6] Whether a newer Yahoo float the stale cut would refuse is used instead, under FLOAT_FRESH_WHEN (read at
    call time). None = refused as today. Else {"mode", "proof" (issuance_proof's dict, or None in the second mode)}.
    Every mode needs: the growth's count dated ON or BEFORE the newer float, on its split side, and the newer float's
    own Yahoo row carrying at least that count (rebased to `basis_date`)."""
    mode = FLOAT_FRESH_WHEN
    if mode == "off" or mode not in FLOAT_FRESH_MODES:
        return None
    if not isinstance(upd, dict) or not isinstance(growth, dict):
        return None
    ta, ua, ts = _iso(growth.get("to_asof")), _iso(upd.get("as_of")), _pos_int(growth.get("to_shares"))
    if ta is None or ua is None or ts is None or ta > ua or not same_side(ta, ua, executed):
        return None
    pr = _rb(upd.get("paired_shares"), ua, basis_date, executed)
    if pr is None or pr < ts:
        return None
    if mode == "issuance_before_float":
        proof = issuance_proof(sec, growth, anchor, basis_date, executed)
        return {"mode": mode, "proof": proof} if proof else None
    if events or not filings_known(sec):
        return None
    return {"mode": mode, "proof": None}


def filing_url(cik, accn, doc) -> Optional[str]:
    """The SEC archive LINK of one filed document (opened in his browser, never fetched), or None unless the CIK is
    digits, the accession is NNNNNNNNNN-NN-NNNNNN and the document a plain file name."""
    if isinstance(cik, bool):
        return None
    if isinstance(cik, int):
        c = cik
    elif isinstance(cik, str) and _CIK_RE.fullmatch(cik.strip()):
        c = int(cik.strip())
    else:
        return None
    if c <= 0 or not isinstance(accn, str) or not _ACCN_RE.fullmatch(accn) or not isinstance(doc, str) \
            or not _DOC_RE.fullmatch(doc):
        return None
    return SEC_ARCHIVE_URL % (c, accn.replace("-", ""), doc)


def issuances(doc, growth, anchor) -> list:
    """The 6-Ks the SEC full-text search matched for issuance words (`sec.fts.issuance`, a read with status ok), filed
    DESC: [{form, filed, accn, shares (the exact growth number the filing prints, else None), ex, url, label, text,
    before_float (filed before `anchor`, or None with no anchor)}]. PURE, never raises on junk."""
    sec = _sub(doc, "sec")
    fts = fts_of(sec)
    raw = fts.get("issuance")
    if _status(fts) != "ok" or not isinstance(raw, list):
        return []
    n, hits = _number_of(fts, growth)
    hit_accns = {h["accn"] for h in hits if h["accn"]}
    cik = _sub(doc, "ref").get("cik")
    a = _iso(anchor)
    out = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        form, filed, accn = _opt_str(r.get("form")), _iso(r.get("filed")), _opt_str(r.get("accn"))
        if filed is None or _form_base(form) != FILING_6K_FORM:
            continue
        d = _opt_str(r.get("doc"))
        ex = [{"type": e["type"].strip(), "desc": _opt_str(e.get("desc"))}
              for e in (r.get("ex") if isinstance(r.get("ex"), list) else [])
              if isinstance(e, dict) and _opt_str(e.get("type"))]
        shares = n if (n and accn and accn in hit_accns) else None
        before = (filed < a) if a else None
        label = "%s %s" % (form, _md(filed))
        text = "%s — the SEC full-text search matched issuance words" % label
        if shares:
            text += "; it states %s shares" % format(shares, ",")
        if before is not None:
            text += "; dated %s %s (the check's start date)" % ("before" if before else "on or after", _md(a))
        if ex:
            text += " · " + " · ".join(("%s: %s" % (e["type"], e["desc"])) if e["desc"] else e["type"] for e in ex)
        out.append({"form": form, "filed": filed, "accn": accn, "shares": shares, "ex": ex,
                    "url": filing_url(cik, accn, d), "label": label, "text": text, "before_float": before})
    out.sort(key=lambda r: r["filed"], reverse=True)
    return out


def _et_date(v) -> Optional[str]:
    """The US-Eastern calendar date of a stored UTC timestamp (ISO), else None."""
    d = _ts(v)
    if d is None:
        return None
    try:
        from zoneinfo import ZoneInfo
        return d.astimezone(ZoneInfo(ET_ZONE)).date().isoformat()
    except Exception:                                          # noqa: BLE001 — no tz database: the UTC date
        return d.astimezone(timezone.utc).date().isoformat()


def _sc_row(key, label, shares, flt, as_of, date_kind) -> dict:
    return {"key": key, "label": label, "shares": shares, "float": flt, "as_of": as_of, "date_kind": date_kind}


def share_counts(si_record, basis_doc, growth) -> list:
    """§3.4 — every share count on file for the name, in this order, only those with a value: the short-interest
    record, Yahoo's current row, the newest same-unit SEC cover, Massive's two ticker-detail counts (dated by the read
    — the provider gives no as-of), the number a 6-K states for THIS growth. [{key, label, shares, float, as_of,
    date_kind ("read" | "as_of" | "filed")}]. No comparison, no cut, no flag. PURE, never raises on junk."""
    rec = si_record if isinstance(si_record, dict) else {}
    doc = basis_doc if isinstance(basis_doc, dict) else {}
    out = []
    F, Fa, P, Pa = _record_fields(rec)
    if P or F:
        out.append(_sc_row("record", SHARE_COUNT_LABELS["record"], P, F, Pa if P else Fa, "read"))
    yh = doc.get("yahoo") if isinstance(doc.get("yahoo"), dict) else {}
    Y, yf = _pos_int(yh.get("shares_outstanding")), _pos_int(yh.get("float_shares"))
    if Y or yf:
        out.append(_sc_row("yahoo", SHARE_COUNT_LABELS["yahoo"], Y, yf, _iso(yh.get("as_of")), "read"))
    ref, sec = _sub(doc, "ref"), _sub(doc, "sec")
    rtype = ref.get("type") if isinstance(ref.get("type"), str) else None
    covers = _covers(sec.get("covers")) if _status(sec) == "ok" else []
    if covers and rtype in SEC_COVER_SAME_UNIT_TYPES:
        c = covers[-1]
        out.append(_sc_row("sec_cover", SHARE_COUNT_LABELS["sec_cover"] % (c["form"] or "filing"), c["shares"], None,
                           c["as_of"], "as_of"))
    if _status(ref) == "ok":
        ra = _et_date(ref.get("read_at"))
        for key, field in (("massive_class", "share_class_shares"), ("massive_weighted", "weighted_shares")):
            v = _pos_int(ref.get(field))
            if v:
                out.append(_sc_row(key, SHARE_COUNT_LABELS[key], v, None, ra, "read"))
    if _status(fts_of(sec)) == "ok":
        n, hits = _number_of(fts_of(sec), growth)
        if n and hits:
            h = hits[0]
            out.append(_sc_row("filing", SHARE_COUNT_LABELS["filing"] % (h["form"], _md(h["filed"])), n, None,
                               h["filed"], "filed"))
    return out


def share_counts_text(rows, basis_doc) -> str:
    """The one "Share counts" row: every count with its date words, then the SEC cover state when no cover row."""
    parts = []
    rows = [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    for r in rows:
        k = r.get("key")
        if k is None:
            continue
        val = (format(r["shares"], ",") if r.get("shares") else
               ("float %s" % format(r["float"], ",") if r.get("float") else None))
        if val is None:
            continue
        if k == "filing":
            parts.append("%s +%s" % (r["label"], val))
            continue
        name = r.get("label") if k == "sec_cover" else SHARE_COUNT_WORDS.get(k, r.get("label") or k)
        when = ("as of %s" if r.get("date_kind") == "as_of" else "read %s") % _md(r.get("as_of"))
        if k in ("massive_class", "massive_weighted"):
            when += TEXT_NO_AS_OF
        parts.append("%s %s (%s)" % (name, val, when))
    if not any(r.get("key") == "sec_cover" for r in rows):
        doc = basis_doc if isinstance(basis_doc, dict) else {}
        ref, sec = _sub(doc, "ref"), _sub(doc, "sec")
        rtype = ref.get("type") if isinstance(ref.get("type"), str) else None
        if _status(sec) == "ok" and _covers(sec.get("covers")) and rtype not in SEC_COVER_SAME_UNIT_TYPES:
            parts.append("SEC cover: " + _units_words(rtype))
        else:
            parts.append(TEXT_NO_COVER)
    return " · ".join(parts) + "."


# ───────────────────────────────────────────── the verdict
def _flag(key, emoji, short, text) -> dict:
    return {"key": key, "emoji": emoji, "short": short, "text": text}


def failed_flag() -> dict:
    """The (i)-shaped flag a raising verdict serves [C11]."""
    return _flag(FLAG_UNCHECKED, EMOJI_CHECK, SHORT_UNCHECKED, TEXT_CHECK_FAILED)


def _src_words(src, form) -> str:
    if src == "sec":
        return "SEC %s cover" % form if form else "SEC cover"
    if src == "yahoo":
        return "Yahoo"
    return "the short-interest record"


def _status(sub: dict) -> Optional[str]:
    s = sub.get("status")
    return s if isinstance(s, str) and s else None


def verdict(si_record, basis_doc, today) -> Optional[dict]:
    """The read-time judgement for one record + its share-basis doc (spec §3.3). None when the record has no
    settlement / count. Every number in the answer is finite or None."""
    from short_interest import read as SR
    if not isinstance(si_record, dict):
        return None
    rec = si_record
    doc = basis_doc if isinstance(basis_doc, dict) else {}
    S = _iso(rec.get("settlement_date"))
    si = _nonneg_int(rec.get("short_interest"))
    if S is None or si is None:
        return None
    T = _iso(today) or SR._today(today).isoformat()
    F, Fa, P, Pa = _record_fields(rec)
    # [2026-11-24 later, fix] a newer dated Yahoo float is used ONLY to divide by (`Fd`, suspect-checked against the
    # count on its own Yahoo row) and for the split-side check (`split_basis`). The dilution-filing window, the
    # share-growth check and the float track keep the REPLACED float's own date and count (F / Fa / P / Pa, the track).
    upd = newer_float(rec, basis_doc)
    Fd, Pf = (upd["shares"], upd["paired_shares"] or P) if upd else (F, P)
    prevS = _iso(rec.get("prev_settlement_date"))
    prev_si = _nonneg_int(rec.get("prev_short_interest")) if prevS else None
    frac = SR.SUSPECT_MAX_SHARES_OUT_FRACTION

    ref, sec, sp = _sub(doc, "ref"), _sub(doc, "sec"), _sub(doc, "splits")
    rows = _rows(sp.get("rows")) if _status(sp) == "ok" else None      # held rows count after a failed try [C1]
    splits_ok = rows is not None
    executed = [r for r in rows if r["execution_date"] <= T] if splits_ok else []
    upcoming = [r for r in rows if r["execution_date"] > T] if splits_ok else []

    is_float = F is not None and SR._float_suspect(si, F, P) is None
    track = track_update(doc.get("float_track"), rec, rows) if F is not None else None
    if is_float:
        basis_date = track["basis_asof"] if track else None
        anchor = track["since"] if track else None
    else:
        basis_date = anchor = Pa
    upd_suspect = SR._float_suspect(si, Fd, Pf) if upd else None
    if upd and upd_suspect and is_float:            # a newer float that fails its own check never replaces a good one
        upd, upd_suspect, Fd, Pf = None, None, F, P
    div_float = (upd_suspect is None) if upd else is_float          # a float is divided by (split-side check runs)
    split_basis = upd["as_of"] if upd else basis_date

    sec_ok = _status(sec) == "ok"
    all_covers = _covers(sec.get("covers")) if sec_ok else []
    rtype = ref.get("type") if isinstance(ref.get("type"), str) else None
    same_unit = rtype in SEC_COVER_SAME_UNIT_TYPES
    covers = all_covers if same_unit else []
    sec_units = bool(all_covers) and not same_unit                     # [P1]
    filings = _filings(sec.get("filings")) if _status(sec) in ("ok", "none") else []   # no cover fact ≠ no filings
    yh = doc.get("yahoo") if isinstance(doc.get("yahoo"), dict) else {}
    Y, Ya = _pos_int(yh.get("shares_outstanding")), _iso(yh.get("as_of"))
    if Y is None or Ya is None:
        Y = Ya = None

    # ── baseline: the count in force when the float was first seen
    base = None                                     # (shares, as_of, source, form)
    record_under = None                             # A6: the record's own count when an SEC cover raised the baseline
    carried_future = dilution_unchecked = False
    if splits_ok and is_float and track:
        if track.get("shares") and track.get("shares_asof"):
            base = (track["shares"], track["shares_asof"], "yahoo", None)
        elif track.get("origin") == ORIGIN_CARRIED:
            if any(r["execution_date"] > T for r in track.get("carried") or []):
                carried_future = True
            else:
                for c in reversed(covers):
                    if c["as_of"] <= track["since"] and _rb(c["shares"], c["as_of"], basis_date, executed):
                        base = (c["shares"], c["as_of"], "sec", c["form"])
                        break
                if base is None:
                    dilution_unchecked = True
    elif splits_ok and not is_float and P and Pa:
        base = (P, Pa, "record", None)
        # ⚠️ 2026-11-26 (spec sitrack §3.3, A6) — no usable float: the baseline is the LARGER of the record's count and
        # the newest same-unit SEC cover dated on or before it (rebased to its split side; a split ON either date
        # leaves the record's count). The float branch above is NOT changed (HIS CALL, §7 #4).
        cov = next((c for c in reversed(covers) if c["as_of"] <= anchor), None)
        adj_cov = _rb(cov["shares"], cov["as_of"], basis_date, executed) if cov else None
        if adj_cov and adj_cov > P:
            base = (cov["shares"], cov["as_of"], "sec", cov["form"])
            record_under = {"shares": P, "as_of": Pa}
    paired = _rb(base[0], base[1], basis_date, executed) if base else None
    if not paired:
        paired = None

    # ── step 1: float vs count across a split
    reasons, split_side = [], {}
    if splits_ok and div_float and split_basis:
        for r in rows:
            a, b = side(split_basis, r["execution_date"]), side(S, r["execution_date"])
            split_side[r["execution_date"]] = (a, b)
            if "same" in (a, b):
                reasons.append(REFUSE_SPLIT_SAME_DAY)
            elif a != b:
                reasons.append(REFUSE_SPLIT)

    # 📄 2026-11-26 (spec sitrack §3.1, A1 + A3) — EVENTS on or after the anchor, never copies; a same-day filing is
    # counted and labelled (which came first is not known). Read here (spec sishares §3.2): the fresh-float check of
    # step 2 needs them.
    ev = filing_events(filings, anchor, cap=sec.get("filings_cap"))
    dil, charter = ev["events"], ev["charter"]

    # ── step 2: share-count evidence
    growth = fell = fresh = None
    count_flag = False
    sec_ev = y_ev = None
    newest_after = next((c for c in reversed(covers) if anchor and c["as_of"] > anchor), None)
    if splits_ok and paired:
        if newest_after:
            adj = _rb(newest_after["shares"], newest_after["as_of"], basis_date, executed)
            if adj:
                sec_ev = (adj, newest_after["as_of"], "sec", newest_after["form"])
        ycands = [(P, Pa), (Y, Ya)]
        ycands = [(n, d) for n, d in ycands if n and d and d > anchor and same_side(d, basis_date, executed)]
        if ycands:
            n, d = max(ycands, key=lambda x: x[1])
            y_ev = (n, d, "yahoo", None)
        newer = sec_ev if (sec_ev and (y_ev is None or y_ev[0] <= sec_ev[0])) else y_ev
        if newer and newer[0] > paired:
            growth = {"ratio": round(newer[0] / paired, 3), "from_shares": paired, "from_asof": base[1],
                      "from_source": base[2], "to_shares": newer[0], "to_asof": newer[1], "to_source": newer[2],
                      "to_form": newer[3]}
            if record_under:
                growth["record_under"] = dict(record_under)
            if is_float:
                si_b = rebase(si, S, basis_date, executed)
                if stale_trigger(si_b, F, paired, newer[0]):
                    # 🩳 2026-11-26 (spec sishares §3.2) — a newer float read with the grown count, under
                    # FLOAT_FRESH_WHEN, is used instead of refused
                    fresh = float_fresh(upd, growth, sec, dil, anchor=anchor, basis_date=basis_date,
                                        executed=executed) if upd else None
                    if not fresh:
                        reasons.append(REFUSE_DILUTED)
            else:
                count_flag = stale_trigger(si, paired, paired, newer[0])
        falls = [c for c in (sec_ev, y_ev) if c and c[0] <= paired * frac]
        if falls:
            c = min(falls, key=lambda x: x[0])
            fell = {"ratio": round(paired / c[0], 3), "from_shares": paired, "from_asof": base[1],
                    "from_source": base[2], "to_shares": c[0], "to_asof": c[1], "to_source": c[2], "to_form": c[3]}
    refused_reasons = [k for k in REFUSAL_ORDER if k in reasons]
    float_refused = refused_reasons[0] if refused_reasons else None
    if float_refused:                                  # a float refused for a split is never "fresh"
        fresh = None

    # ── step 3: the count for % of shares outstanding
    count, count_changed, no_pct, pct_so = None, False, False, None
    # a newer float divided by while the record's count sits across a split from S: the count is chosen as below
    p_cross = bool(upd and not float_refused and P and Pa and splits_ok and not same_side(Pa, S, executed))
    if splits_ok and (float_refused or not is_float or p_cross or fresh):
        P_on_S = P if (P and Pa and same_side(Pa, S, executed)) else None
        cut = P_on_S * frac if P_on_S else None
        c_sec = c_y = None
        if newest_after:
            v = _rb(newest_after["shares"], newest_after["as_of"], S, executed)
            if v and not (cut is not None and v <= cut):
                c_sec = {"shares": v, "as_of": newest_after["as_of"], "source": "sec", "form": newest_after["form"]}
        if Y and Pa and Ya > Pa and same_side(Ya, S, executed) and not (cut is not None and Y <= cut):
            c_y = {"shares": Y, "as_of": Ya, "source": "yahoo", "form": None}
        if c_sec and (c_y is None or c_y["shares"] <= c_sec["shares"]):
            count = c_sec
        elif c_y:
            count = c_y
        elif P_on_S:
            count = {"shares": P_on_S, "as_of": Pa, "source": "record", "form": None}
        if (count is None and p_cross and upd["paired_shares"]
                and same_side(upd["as_of"], S, executed)):               # the newer float's own Yahoo row
            count = {"shares": upd["paired_shares"], "as_of": upd["as_of"], "source": "yahoo", "form": None}
        if count:
            pct_so = round(si / count["shares"] * 100.0, 2)
            count_changed = (count["shares"] != P or count["as_of"] != Pa)
        else:
            no_pct = True

    # ── step 4: the change across a split [C2]
    change = change_across_split(si, S, prev_si, prevS, executed) if splits_ok else None

    # ── step 5: flags
    flags, title_lines = [], []
    float_line = None
    if REFUSE_DILUTED in refused_reasons and growth:
        frm = ("Yahoo, with the float" if growth["from_source"] == "yahoo"
               else "SEC cover, the count on file before the float was read")
        text = ("%s — %s× more shares than when the float was read: %s (%s, %s) vs %s (%s, %s)"
                % (SHORT_FLOAT_STALE, ratio_words(growth["ratio"]), format(growth["to_shares"], ","),
                   _src_words(growth["to_source"], growth["to_form"]), _md(growth["to_asof"]),
                   format(growth["from_shares"], ","), frm, _md(growth["from_asof"])))
        flags.append(_flag(FLAG_FLOAT_STALE, EMOJI_WARN, SHORT_FLOAT_STALE, text))
    if count_flag and growth:
        r = ratio_words(growth["ratio"])
        if growth["from_source"] == "sec" and record_under:
            text = (TEXT_COUNT_STALE_SEC
                    % (EMOJI_WARN, r, _src_words("sec", base[3]), format(growth["to_shares"], ","),
                       _src_words(growth["to_source"], growth["to_form"]), _md(growth["to_asof"]),
                       format(growth["from_shares"], ","), _md(growth["from_asof"]),
                       format(record_under["shares"], ","), _md(record_under["as_of"])))
        else:
            text = ("%s %s× more shares than on the short-interest record: %s (%s, %s) vs %s (%s) — the %% uses the "
                    "newer count" % (EMOJI_WARN, r, format(growth["to_shares"], ","),
                                     _src_words(growth["to_source"], growth["to_form"]), _md(growth["to_asof"]),
                                     format(growth["from_shares"], ","), _md(growth["from_asof"])))
        flags.append(_flag(FLAG_COUNT_STALE, EMOJI_WARN, SHORT_COUNT_STALE % r, text))
    if fresh and growth:                               # 🩳 2026-11-26 (spec sishares §3.2) — the count was out of date
        r, pr = ratio_words(growth["ratio"]), fresh["proof"]
        head = (EMOJI_WARN, r, format(growth["to_shares"], ","), _src_words(growth["to_source"], growth["to_form"]),
                _md(growth["to_asof"]), format(growth["from_shares"], ","), _md(growth["from_asof"]))
        if pr:
            text = TEXT_COUNT_BEFORE_FLOAT % (head + (
                pr["form"], _md(pr["filed"]), format(pr["n"], ","), format(growth["from_shares"], ","),
                format(pr["n"], ","), format(growth["to_shares"], ","), format(upd["shares"], ","),
                _md(upd["as_of"])))
        else:
            text = TEXT_COUNT_WITH_FLOAT % (head + (format(upd["shares"], ","), _md(upd["as_of"])))
        flags.append(_flag(FLAG_COUNT_STALE, EMOJI_WARN, SHORT_COUNT_STALE % r, text))
    if record_under:                                   # A6 — the three counts, always, in the hover
        head = (TITLE_SHARE_COUNTS_HEAD % (format(record_under["shares"], ","), _md(record_under["as_of"]),
                                           _src_words("sec", base[3]), format(base[0], ","), _md(base[1])))
        if growth:
            head += TITLE_SHARE_COUNTS_GROWTH % (format(growth["to_shares"], ","),
                                                 _src_words(growth["to_source"], growth["to_form"]),
                                                 _md(growth["to_asof"]), ratio_words(growth["ratio"]))
        title_lines.append(head + ".")
    if growth and (flags and flags[-1]["key"] in (FLAG_FLOAT_STALE, FLAG_COUNT_STALE)) and newest_after:
        prev_c = next((c for c in reversed(covers) if c["as_of"] <= anchor), None)
        if prev_c:
            pa = _rb(prev_c["shares"], prev_c["as_of"], newest_after["as_of"], executed)
            if pa:
                title_lines.append("SEC cover counts: %s on %s → %s on %s — %s×."
                                   % (format(pa, ","), _md(prev_c["as_of"]), format(newest_after["shares"], ","),
                                      _md(newest_after["as_of"]), ratio_words(newest_after["shares"] / pa)))

    split_list = []
    floor = min(S, anchor) if anchor else S
    ex_flag = [r for r in reversed(executed) if r["execution_date"] > floor]
    carried_dates = set() if upd else {r["execution_date"] for r in ((track or {}).get("carried") or [])}
    split_since = upd["as_of"] if upd else (track or {}).get("since")      # the date of the float divided by

    def _split_text(r, due: bool) -> str:
        E, w = r["execution_date"], split_words(r["split_from"], r["split_to"])
        ab = split_side.get(E)
        if ab and ("same" in ab or ab[0] != ab[1]):
            a, b = ab
            if "same" in ab:
                who = ("the float was first seen" if a == "same" else "short interest was counted")
                return ("%s %s %s — %s that same day; which side of the split it is on is not known, so no %% of "
                        "float is shown" % (EMOJI_SPLIT, w, _md(E), who))
            how = "carried across it" if E in carried_dates else "first seen"
            return ("%s %s %s — the float on file dates from %s it (%s, %s) and short interest was counted %s it "
                    "(%s), so no %% of float is shown"
                    % (EMOJI_SPLIT, w, _md(E), "before" if a == "pre" else "after", how,
                       _md(split_since), "before" if b == "pre" else "after", _md(S)))
        if due:
            return "%s %s due %s" % (EMOJI_SPLIT, w, _md(E))
        if side(S, E) == "same":
            return ("%s %s %s — short interest was counted that same day; which side of the split it is on is not "
                    "known" % (EMOJI_SPLIT, w, _md(E)))
        return ("%s %s %s — short interest counted %s it (%s)"
                % (EMOJI_SPLIT, w, _md(E), "before" if side(S, E) == "pre" else "after", _md(S)))

    if ex_flag:
        texts = [_split_text(r, False) for r in ex_flag]
        short = SHORT_SPLIT % _md(ex_flag[0]["execution_date"])
        if len(ex_flag) > 1:
            short += " +%d" % (len(ex_flag) - 1)
        flags.append(_flag(FLAG_SPLIT, EMOJI_SPLIT, short, " · ".join(texts)))
        for r in ex_flag:
            split_list.append(dict(r, words=split_words(r["split_from"], r["split_to"]), when="executed"))
    for r in upcoming:
        flags.append(_flag(FLAG_SPLIT, EMOJI_SPLIT, SHORT_SPLIT_DUE % _md(r["execution_date"]), _split_text(r, True)))
        split_list.append(dict(r, words=split_words(r["split_from"], r["split_to"]), when="upcoming"))
    after_s = [r for r in executed if S < r["execution_date"] <= T]
    if after_s:
        f = 1.0
        for r in after_s:
            f *= _factor(r)
        title_lines.append("FINRA counted %s shares short before the split%s — %s of today's shares."
                           % (format(si, ","), "" if len(after_s) == 1 else "s", format(int(round(si * f)), ",")))
    if float_refused in (REFUSE_SPLIT, REFUSE_SPLIT_SAME_DAY):
        want = (lambda ab: "same" in ab) if float_refused == REFUSE_SPLIT_SAME_DAY else (
            lambda ab: "same" not in ab and ab[0] != ab[1])
        r = next((r for r in rows if want(split_side.get(r["execution_date"], ("x", "x")))), None)
        if r is not None:
            float_line = _split_text(r, r["execution_date"] > T)
    elif float_refused == REFUSE_DILUTED and flags and flags[0]["key"] == FLAG_FLOAT_STALE:
        float_line = flags[0]["text"]

    anchor_words = ANCHOR_WORDS_FLOAT if is_float else ANCHOR_WORDS_COUNT

    def _same_day_tail(evs, words) -> str:
        same = [words(e) for e in evs if e["same_day"]]
        return TEXT_FILING_SAME_DAY % (" · ".join(same), anchor_words) if same else ""

    def _named(e) -> str:
        return "%s %s" % (e["label"], _md(e["filed"]))

    if dil:
        more = (" +%d" % (len(dil) - 1)) if len(dil) > 1 else ""
        if all(e["same_day"] for e in dil):
            short = SHORT_FILING_SAME_DAY % (dil[0]["label"], _md(dil[0]["filed"]) + more)
        else:
            short = SHORT_FILING % (dil[0]["label"], _md(dil[0]["filed"])) + more
        if len(dil) == 1:
            text = "%s dilution filing: %s" % (EMOJI_FILING, _named(dil[0]))
        else:
            text = "%s %d dilution filings since %s: %s" % (EMOJI_FILING, len(dil), _md(anchor),
                                                           " · ".join(_named(e) for e in dil[:3]))
            if len(dil) > 3:
                text += " (+%d more)" % (len(dil) - 3)
        if ev["n_copies"]:
            text += TEXT_FILING_COPIES % (ev["n_copies"], "copy" if ev["n_copies"] == 1 else "copies")
        text += _same_day_tail(dil, _named)
        if ev["n_reports"]:                            # C13 — a 6-K that reports an offering already counted
            text += TEXT_FILING_SAME_DAY_6K % ev["n_reports"]
        if ev["unchecked"]:
            text += TEXT_FILING_UNCHECKED % (ev["unchecked"], "filing" if ev["unchecked"] == 1 else "filings")
        if ev["cap"]:
            text += TEXT_FILING_CAPPED % ev["cap"]
        flags.append(_flag(FLAG_FILING, EMOJI_FILING, short, text))

    def _charter_words(f) -> str:
        its = [i for i in _items(f["items"]) if i in FILING_8K_CHARTER_ITEMS]
        return "%s Item %s %s" % (FILING_8K_FORM, "/".join(its), _md(f["filed"]))

    if charter:
        title_lines.append("Charter filing (a reverse split is filed under this item; so are other charter "
                           "changes): %s%s." % ("; ".join(_charter_words(f) for f in charter),
                                               _same_day_tail(charter, _charter_words)))
    if fell:
        r = ratio_words(fell["ratio"])
        text = ("%s share count fell %s× with no split on file: %s (%s, %s) vs %s (%s) — a split the splits read "
                "does not list is possible, and the %% shown is not adjusted for one"
                % (EMOJI_CHECK, r, format(fell["to_shares"], ","), _src_words(fell["to_source"], fell["to_form"]),
                   _md(fell["to_asof"]), format(fell["from_shares"], ","), _md(fell["from_asof"])))
        if charter:
            text += " · charter filing " + _charter_words(charter[0])
        flags.append(_flag(FLAG_COUNT_FELL, EMOJI_CHECK, SHORT_COUNT_FELL % r, text))

    # unchecked: at most ONE on the chip (the first that holds), every text in the title
    unchecked = []                                     # (short, text)
    named = (("ref", ref), ("sec", sec), ("splits", sp))
    never = [(k, s) for k, s in named if _status(s) == "failed" or (k == "sec" and _status(s) == "blocked")]
    for k, s in never:
        last = _et(s.get("error_at"))
        unchecked.append((SHORT_UNCHECKED, "%s share count not checked — %s did not answer%s; the %% shown uses the "
                          "counts on the short-interest record"
                          % (EMOJI_CHECK, SOURCE_NAME[k], " (last try %s)" % last if last else "")))
    for k, s in named:
        if _status(s) not in (None, "failed", "blocked") and s.get("error"):
            unchecked.append((SHORT_LAST_FAILED, "%s %s last answered %s and failed at %s — the flags and the %% "
                              "shown use the earlier answer"
                              % (EMOJI_CHECK, SOURCE_NAME[k], _et(s.get("read_at")) or "n/a",
                                 _et(s.get("error_at")) or "n/a")))
    if dilution_unchecked and not carried_future:
        cw = " and the ".join("%s %s" % (split_words(r["split_from"], r["split_to"]), _md(r["execution_date"]))
                              for r in (track or {}).get("carried") or [])
        unchecked.append((SHORT_DILUTION_UNCHECKED, "%s dilution not checked — the float was carried across the %s "
                          "and no SEC share count from before %s is on file"
                          % (EMOJI_CHECK, cw or "split", _md((track or {}).get("since")))))
    if unchecked:
        flags.append(_flag(FLAG_UNCHECKED, EMOJI_CHECK, unchecked[0][0], " ".join(t for _s, t in unchecked)))
    float_update = None
    if upd:                                            # FIRST on the chip: the float the % is read against changed
        flags.insert(0, _flag(FLAG_FLOAT_UPDATED, EMOJI_WARN, SHORT_FLOAT_UPDATED,
                              TEXT_FLOAT_UPDATED % (format(upd["shares"], ","), _md(upd["as_of"]),
                                                    format(upd["replaced_shares"], ","), _md(upd["replaced_asof"]))))
        float_update = dict(upd, suspect=upd_suspect,
                            pct=(round(si / Fd * 100.0, 2) if (upd_suspect is None and not float_refused) else None))

    # ── status + sources + the check sentence
    missing = any(_status(s) is None for _k, s in named)
    partial = bool(never or missing or fell or any(s.get("error") for _k, s in named if _status(s)))
    sources = {"sec": "units" if sec_units else (_status(sec) or "not_read"),
               "splits": _status(sp) or "not_read",
               "yahoo": "ok" if Y else "not_read"}
    check = _check_text(ref, sec, sp, sec_units, rtype, Y, Ya)
    iss = issuances(doc, growth, anchor)
    counts = share_counts(rec, doc, growth)
    rows_out = ([{"k": "Note", "v": l} for l in title_lines]
                + [{"k": FLAG_ROW_LABEL.get(f["key"], "Flag"), "v": f["text"]} for f in flags]
                + ([{"k": ROW_SHARE_COUNTS, "v": share_counts_text(counts, doc)}] if counts else [])
                + [{"k": ROW_SHARE_ISSUANCE, "v": i["text"]} for i in iss]
                + [{"k": "Share-count check", "v": check}])
    tier_text = None
    if float_refused == REFUSE_DILUTED:
        tier_text = getattr(SR, "TIER_FLOAT_STALE_TEXT", None)
    elif float_refused:
        tier_text = getattr(SR, "TIER_SPLIT_TEXT", None)
    # [2026-11-24 later, refix 3] a dilution refusal judges the REPLACED float (its date and count ran the check), so
    # the "would read" % is on it — exactly as before the newer-float rule (LABT 18.04%, the line and the panel agree)
    fpd = F if (float_refused == REFUSE_DILUTED and upd) else Fd
    fpof = round(si / fpd * 100.0, 2) if (float_refused and fpd) else None
    return {"float_refused": float_refused, "refused_reasons": refused_reasons, "float_pct_on_file": fpof,
            "count": count, "count_changed": bool(count_changed), "pct_of_shares_out": pct_so, "no_pct": bool(no_pct),
            "growth": growth, "fell": fell, "change": change, "splits": split_list,
            "filings": [{"form": f["form"], "filed": f["filed"], "items": f["items"], "kind": f["kind"],
                         "copies": f["copies"], "same_day": f["same_day"]} for f in dil],
            "charter": [{"form": f["form"], "filed": f["filed"], "items": f["items"]} for f in charter],
            "flags": flags, "status": "partial" if partial else "ok", "sources": sources,
            "checked_at": _ts_iso(doc.get("checked_at")), "tier_text": tier_text,
            "title_lines": title_lines, "rows": rows_out, "check_text": check, "float_line": float_line,
            "track": track, "float_update": float_update, "issuances": iss, "share_counts": counts,
            "float_fresh": ({"mode": fresh["mode"], "accn": (fresh["proof"] or {}).get("accn"),
                             "filed": (fresh["proof"] or {}).get("filed")} if fresh else None)}


def _when(sub) -> str:
    return _et(sub.get("read_at")) or "n/a"


def _units_words(rtype) -> str:
    return ("not compared — an ADR's SEC cover counts ordinary shares" if (rtype or "").upper().startswith("ADR")
            else "not compared — the SEC cover counts a different share unit (listing type %s)" % (rtype or "n/a"))


def _fts_words(fts: dict) -> str:
    """[C1, C9] The 6-K full-text search read state, in words — never silent."""
    st = _status(fts)
    if st == "ok":
        s = (("last try failed %s; the answer read %s is used" % (_et(fts.get("error_at")) or "n/a", _when(fts)))
             if fts.get("error") else "read %s" % _when(fts))
        cap = _pos_int(fts.get("cap"))
        return s + (" — only the first %d answers are read" % cap if cap else "")
    if st == "none_6k":
        if fts.get("error"):                       # a held "none" a later pass could not re-ask: 6-Ks may exist now
            return ("not read — paused" if fts.get("error") == "blocked"
                    else "not read — last try failed %s" % (_et(fts.get("error_at")) or "n/a"))
        return "no 6-K filed in the window"
    if st == "failed":
        return "not read — last try failed %s" % (_et(fts.get("error_at")) or "n/a")
    if st == "blocked":
        return "not read — paused"
    if st == "off":
        return "switched off"
    return "not read"


def _check_text(ref, sec, sp, sec_units, rtype, Y, Ya) -> str:
    st = _status(sec)
    if sec_units:
        s = _units_words(rtype)
    elif st == "ok":
        s = (("last try failed %s; the answer read %s is used" % (_et(sec.get("error_at")) or "n/a", _when(sec)))
             if sec.get("error") else "read %s" % _when(sec))
    elif st == "none":
        s = "read %s — no cover count on file" % _when(sec)
    elif st == "no_cik":
        s = "not read — no SEC filer number on file for this listing"
    elif st == "blocked":
        s = "not read — SEC calls were paused"
    elif st == "failed":
        s = "not read — last try failed %s" % (_et(sec.get("error_at")) or "n/a")
    else:
        s = "not read"
    if _status(ref) == "failed":
        s += " (the Massive ticker read failed)"
    stp = _status(sp)
    if stp == "ok":
        p = (("last try failed %s; the rows read %s are used" % (_et(sp.get("error_at")) or "n/a", _when(sp)))
             if sp.get("error") else "read %s" % _when(sp))
    elif stp == "failed":
        p = "not read — last try failed %s" % (_et(sp.get("error_at")) or "n/a")
    else:
        p = "not read"
    y = ("%s as of %s" % (format(Y, ","), Ya)) if Y else "not read"
    # 🩳 2026-11-26 (spec sishares §3.2) — the 4th clause ONLY when the doc holds a full-text read (else byte-identical)
    f = (TEXT_CHECK_FTS % _fts_words(sec["fts"])) if isinstance(sec.get("fts"), dict) else ""
    return "SEC cover count: %s · splits (Massive): %s · Yahoo shares outstanding: %s%s." % (s, p, y, f)


def rules_sentence() -> str:
    """The one sentence folded onto the END of the 🩳 rules pick that starts '% of float = ' (the section is at its
    8-pick cap). Built from FLOAT_STALE_WHEN and the flag words by name."""
    mode = FLOAT_STALE_MODE_WORDS.get(FLOAT_STALE_WHEN)
    stale = ("stale (%s)" % mode) if mode else "stale"
    return ("The %% of float is not shown when the float on file is %s or sits on the other side of a split from "
            "the short-interest count: the chip falls back to %% of shares outstanding on the newest dated count (an "
            "SEC cover page or Yahoo's later count, with its date), carries no tier word, and says why — '%s', "
            "'%s', '%s' for a registration, prospectus or 8-K Item %s filing since the float was read, '%s' when a "
            "count fell with no split on file, '%s' when a check could not run. A change vs the prior settlement "
            "across a split is split-adjusted. A Yahoo float dated later than the one on the short-interest record "
            "and different from it is the one divided by once the splits are on file, with '%s' naming both and their "
            "dates; filings and share growth are still looked for from the older float's date. A newer float read "
            "with or after the larger share count is used, not called stale, %s, with '%s'. A %s the SEC full-text "
            "search matches for issuance words is a '%s' filing too, never a second one on a day an offering is "
            "already counted."
            % (stale, SHORT_FLOAT_STALE, SHORT_SPLIT % "M/D", EMOJI_FILING, FILING_8K_DILUTION_ITEMS[0],
               SHORT_COUNT_FELL % "N", SHORT_UNCHECKED, SHORT_FLOAT_UPDATED,
               FLOAT_FRESH_MODE_WORDS.get(FLOAT_FRESH_WHEN, FLOAT_FRESH_MODE_WORDS["off"]), SHORT_COUNT_STALE % "N",
               FILING_6K_FORM, EMOJI_FILING))
