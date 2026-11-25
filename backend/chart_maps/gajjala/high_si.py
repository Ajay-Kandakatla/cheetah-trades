"""🩳 High SI sub on 🚩 Gajjala's 5-minute tab — his scanner's names with short interest High or EXTREME and a low float
(2026-11-23, SPEC highsi §3.2, WP be-sub).

Ajay 2026-11-23 (voice-typed), verbatim: "Can you create a tab similarly like Divergent with high charging tested, SHO
tag, and low floats similar to what we've done in Divergent tab under Gazilla? And also add alerts for these talks when
they are crossing EMA, 9 EMA over 21 EMA. I would like to see this. So this should be dedicated to all the high charging
tests, but also when you add something to watch list, it's easily available to you. But maintain same Gajjala rules
under 100 stock and all the other filters that you have. Look at Divergent, most of it should be available for you." ·
"New tab like divergence*" [voice typing: "high charging tested" = high short interest, "Gazilla" = Gajjala, "talks" =
stocks].

Membership (his answer #1) = a name on this tab's stored reads whose short interest is High or EXTREME by the HOUSE tier
(short_interest.read.si_tier — the 🩳 chip's own word) AND whose float is at or under GC.HIGH_SI_MAX_FLOAT (=
K8_MAX_FLOAT). TWO float reads exist — the float stored WITH the short-interest record (the tier's denominator) and the
pass's float read (the card's Float chip, the K8 gate's read). A name lists only when BOTH agree: High / EXTREME on the
record's float, at or over the High cut on the card's float (SR.tier_of — the ONE ladder, no number typed), and both
floats at or under the cap. Unknown is never listed; every not-listed name is counted by reason.

ONE membership function (`classify`) serves the board and the push step (high_si_cross.py). Computed ON THE GET from the
stored `gajjala_reads` docs tab.build already holds + ONE house short-interest read (si_map, chunked). Never fetches,
never writes. The cross marks come from tab.ema_cross_block (the ONE engine over the stored 9 / 21 EMA curves). The
push was built OFF, LIVE since 2026-11-23 (GC.HIGH_SI_CROSS_PUSH_MODE); `push_mode()` is THE mode read. UNMEASURED. Not advice.

Imports of tab / alerts / potential / divergence_tab / reg_sho are LAZY (tab imports this module).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Callable, Optional

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as DT          # the K11 parser + the ONE criteria row shape
from chart_maps.gajjala import variant as V
from chart_maps.gajjala_watch import constants as WC    # FRAME_WORDS (WC imports only sys + GC)
from short_interest import read as SR

log = logging.getLogger("chart_maps.gajjala.high_si")

TIERS = (SR.TIER_HIGH, SR.TIER_EXTREME)
STATE = "high_si"
REASONS = ("float_over", "si_float_over", "floats_disagree", "float_unknown", "not_high", "stale", "no_tier", "no_si")
NOT_ADVICE = "Not advice."
DASH = "—"

ASK_TEXT = ("Ajay 2026-11-23: “Can you create a tab similarly like Divergent with high charging tested, SHO tag, and low "
            "floats similar to what we've done in Divergent tab under Gazilla? And also add alerts for these talks when "
            "they are crossing EMA, 9 EMA over 21 EMA. I would like to see this. So this should be dedicated to all the "
            "high charging tests, but also when you add something to watch list, it's easily available to you. But "
            "maintain same Gajjala rules under 100 stock and all the other filters that you have. Look at Divergent, "
            "most of it should be available for you.” · “New tab like divergence*” [voice typing: “high charging "
            "tested” = high short interest, “Gazilla” = Gajjala, “talks” = stocks]")
RULE_LABEL = "ⓘ what gets listed"
PUSH_OFF_TEXT = ("🔕 No phone alert rings from this list — the {fast} / {slow} EMA cross push is switched off. "
                 "Off since your call of {call} (“{short}”).")   # Ajay 2026-11-24 — GC.CLEAN_ALERTS_CALL / _SHORT
ORDER_NOTE = ("🩳 a name whose 🔒 Reg SHO close-out date is still counting or was reached on the latest list first, the "
              "nearest date first (his word 2026-11-24) · "
              "then today's volume, then the lowest float (his word for every Gajjala card) · a name with no stored "
              "volume today goes last")
ORDER_SHO_UNREAD = " · the Reg SHO lists could not be read this time, so no close-out date moved a name"
ORDER_SHO_PARTIAL = " · not every Reg SHO list was read this time, so a name on an unread list was not moved"
# Ajay 2026-11-24: "Please sort the short interest tab based on that if this date is available put that ticker higher
# up" — "that date" = the 🔒 tag's day-13 close-out date (the Reg SHO run block, item["run"]["day13"]). Only a date still AHEAD (run
# state counting) or today's (reached) lifts a name; a passed date, a stale list, an unknown day count or no tag → the
# house order. 🚫 his names still go last (tab.broker_bottom runs after). Display order only — no gate, push or listing.
CLOSEOUT_UPCOMING_STATES = ("counting", "reached")
SHOWN_TEXT = "Showing the first {lim} of {n} listed names — every name is counted above."
EMPTY_SESSION = ("No name on his list had short interest {high} or {extreme} with a float at or under {cap} at the last "
                 "read of the {label} session.")
FAULT_TEXT = ("🩳 The short-interest read could not be made this time — the next re-read tries again. A missing list "
              "does not mean no name qualifies.")
FAULTS_TEXT = "{n} name(s) could not be read this time — the rest of the board stands"
CHARTLESS_TEXT = "🩳 {sym} listed · chart not stored"
NO_CROSS_TEXT = "no cross on today's stored bars"
# 2026-11-24 (SPEC sidilute §3.6, WP be-highsi) — Ajay: "Make sure we are looking for Dilution.." · "Also split related
# events and filing so we flag them in the right way". The house read (short_interest.read.si_block) refuses a float that
# is stale (more shares since it was read) or sits across a split from the short-interest count: that block carries
# basis.float_refused and no tier, so classify gives it `no_tier` (REASONS and the push's COUNT_KEYS unchanged). Here the
# words split it out of "no usable float", and a name that WAS High / EXTREME on the float on file is named.
BASIS_TEXT = ("⚠️ %s or %s on the float on file, but that float is stale or across a split — not tiered, so not "
              "listed: %s")
NO_TIER_REFUSED_HEAD = "{k} with no tier word ({m} with a float that is stale or across a split"
# printed only when at least one no-tier name is NOT refused — "the rest" never stands for zero names
NO_TIER_REFUSED_REST = "; the rest with no usable float on the short-interest record"
NO_TIER_REFUSED_WORDS = NO_TIER_REFUSED_HEAD + NO_TIER_REFUSED_REST


# ── small helpers ───────────────────────────────────────────────────────────────────────────────────────────────
def _f(x) -> Optional[float]:
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _pos(x) -> Optional[float]:
    v = _f(x)
    return v if v is not None and v > 0 else None


def _cap() -> int:
    return int(GC.HIGH_SI_MAX_FLOAT)


def _cap_text() -> str:
    return f"{_cap():,}"


def _floor_text() -> str:
    return f"{int(GC.K11_MIN_SESSION_VOLUME):,}"


def _w(tier: str) -> str:
    return SR.TIER_WORDS[tier]


def _compact(x) -> str:
    from chart_maps.gajjala import tab as GT             # lazy — tab imports this module inside build
    return GT._compact(x) or DASH


def _pct(x) -> str:
    v = _f(x)
    return DASH if v is None else SR._pct_tier(v)


# 🎾 2026-11-24 — Ajay: "If the SI tab stocks have reversal squeeze action add the tag on the ticker to for the tennis
# ball actions Run them against Gajjals other rules to show A+.. I wonder if we do this the other way around to move them
# to Reversal squeeze by default but lets not do that". The tag READS the name's own stored 🎾 read (the same read the
# 🎾 card shows, graded by every GG rule in the pass) — no new grading, no move between subs, no order change.
SQUEEZE_SETUP = "reversal_squeeze"
SQUEEZE_TAG = "🎾 Reversal Squeeze"
SQUEEZE_WORDS = {"aplus": "A+", "triggered": "triggered", "forming": "forming", "partial": "partial",
                 "stopped": "stopped"}
SQUEEZE_NEED = "GG's 🎾 Reversal Squeeze rules — the same read as the 🎾 card (display only)"


def squeeze_read(read_doc) -> Optional[dict]:
    """The name's stored 🎾 read when it would carry a 🎾 card (state in tab.TILE_STATES), else None. Never raises."""
    from chart_maps.gajjala import tab as GT
    try:
        r = ((read_doc or {}).get("setups") or {}).get(SQUEEZE_SETUP)
        if isinstance(r, dict) and r.get("state") in GT.TILE_STATES and r.get("state") in SQUEEZE_WORDS:
            return r
    except AttributeError:
        return None
    return None


def squeeze_word(r: dict) -> str:
    w = SQUEEZE_WORDS[r["state"]]
    return w + (" · ready" if r["state"] == "forming" and r.get("ready") is True else "")


def squeeze_row(r: dict) -> dict:
    """The ✓/✗ row: the 🎾 card's own pill words. A `triggered` read never claims A+ here (formulas audit D10: whether
    an alert rang is the 🎾 card's to say)."""
    from chart_maps.gajjala import tab as GT
    st = r["state"]
    if st == "triggered":
        value = "triggered — broke on the %s bar · whether an alert rang: see the 🎾 card · %s" % (
            GT._hhmm(r.get("entry_bar_t")) or DASH, GT.UNMEASURED)
    else:
        value = GT.state_label(r)
    ok = True if st in ("aplus", "triggered") else (None if st == "forming" else False)
    return {"key": "squeeze", "label": SQUEEZE_TAG, "value": value, "need": SQUEEZE_NEED, "ok": ok}


def _s(x) -> Optional[str]:
    return x if isinstance(x, str) and x.strip() else None


def basis_of(si_block) -> Optional[dict]:
    """The block's served share-basis check (`basis`, read.py §3.4) when it is a dict, else None. Never raises."""
    b = si_block.get("basis") if isinstance(si_block, dict) else None
    return b if isinstance(b, dict) else None


def float_refused(si_block) -> Optional[str]:
    """basis.float_refused when it is a non-empty string (the house read refused the float on file), else None."""
    return _s((basis_of(si_block) or {}).get("float_refused"))


def si_flags(si_block) -> list:
    """The flag `short` words the house read served on this block (basis.flags[].short) — well-formed strings only, in
    the served order. Junk (not a list, a flag that is not a dict, no / empty / non-string short) adds nothing."""
    flags = (basis_of(si_block) or {}).get("flags")
    if not isinstance(flags, list):
        return []
    return [f["short"] for f in flags if isinstance(f, dict) and _s(f.get("short"))]


def tier_chip(read: dict) -> str:
    """The card's 🩳 chip words WITH the % in them (Ajay 2026-11-23: "Why is high more than extreme? can you actually put
    a percentage directly here?"). The % is the short-interest record's own % of float (the one the house tier is read
    on), else this card's float %; no number → no %, never "None" / "nan". A name the house holds at High because its
    float is unconfirmed says so in the chip (SR.FLOAT_UNCONFIRMED_WORD) — that is why a High can carry a bigger % than
    an EXTREME. Then ` · ` + each served share-basis flag short (`si_flags`, 2026-11-24 [C6]); none → the old words
    exactly. Words only: no tier, gate or listing changes here."""
    read = read if isinstance(read, dict) else {}
    p = _f(read.get("pct_record"))
    if p is None:
        p = _f(read.get("pct_card"))
    pct = "" if p is None else _pct(p) + " "
    unc = " (%s)" % SR.FLOAT_UNCONFIRMED_WORD if read.get("float_check") == SR.FLOAT_UNCONFIRMED else ""
    fl = read.get("si_flags")
    tail = "".join(" · " + f for f in fl if _s(f)) if isinstance(fl, list) else ""
    return "🩳 %sshort interest · %s%s%s" % (pct, read.get("tier_word") or DASH, unc, tail)


def _hhmm(t) -> Optional[str]:
    from chart_maps.gajjala import tab as GT
    return GT._hhmm(t)


def _emoji() -> str:
    from chart_maps.gajjala import tab as GT
    return GT.SUB_META[GC.HIGH_SI_SUB][0]


# ── the mode (THE one read — the push step calls it) ────────────────────────────────────────────────────────────
def push_mode() -> str:
    """GC.HIGH_SI_CROSS_PUSH_MODE when it is one of GC.HIGH_SI_CROSS_PUSH_MODES, else the first ("off") — fail closed."""
    m = GC.HIGH_SI_CROSS_PUSH_MODE
    modes = tuple(GC.HIGH_SI_CROSS_PUSH_MODES)
    return m if isinstance(m, str) and m in modes else modes[0]


def _live() -> bool:
    modes = tuple(GC.HIGH_SI_CROSS_PUSH_MODES)
    return push_mode() != modes[0]


# ── the reads ───────────────────────────────────────────────────────────────────────────────────────────────────
def si_blocks(symbols, *, today) -> Optional[dict]:
    """{SYM: block} — the ONE house short-interest read (SR.si_map) over chunks of SR.MAP_MAX_SYMBOLS, merged, never
    truncated. None when Mongo has no handle (the fault — unknown is never listed)."""
    syms: list = []
    for s in symbols or []:
        s = str(s or "").strip().upper()
        if s and s not in syms:
            syms.append(s)
    db = SR.SIC._get_db()
    if db is None:
        return None
    out: dict = {}
    step = int(SR.MAP_MAX_SYMBOLS)
    for i in range(0, len(syms), step):
        out.update(SR.si_map(syms[i:i + step], db=db, today=today) or {})
    return out


def float_shares(float_read) -> Optional[int]:
    """The card's float: tab._float_shares_of — the K8 policy (positive shares; a suspect float under
    FLOAT_SUSPECT_POLICY "ineligible" is unknown), never a second float rule."""
    from chart_maps.gajjala import tab as GT
    return GT._float_shares_of(float_read)


def card_pct(si_block, float_read) -> Optional[float]:
    """The SAME short interest on the CARD's float, with the house 2-dp rounding (read.py si_block). None when either
    side is missing or not positive. Compared on the house ladder; never printed with a tier word of its own."""
    if not isinstance(si_block, dict):
        return None
    si = _pos(si_block.get("si_shares"))
    fl = float_shares(float_read)
    if si is None or not fl or fl <= 0:
        return None
    return round(si / fl * 100.0, 2)


def classify(si_block, float_read) -> dict:
    """ONE name → {"listed", "reason" (None | one of REASONS), "tier", "float_check", "float_shares" (card),
    "si_float_shares" (record), "pct_card", "hi_card"}. PURE; every leaf read with .get(); never raises on junk.
    First match: no_si · stale · no_tier · not High/EXTREME (floats_disagree when the card's float would list it, else
    not_high) · float_unknown (card) · float_over (card) · float_unknown / si_float_over (record) · floats_disagree (High
    on the record's float, under the High cut on the card's) · listed."""
    b = si_block if isinstance(si_block, dict) else None
    try:
        fl = float_shares(float_read)
    except Exception:                                    # noqa: BLE001 — a junk float read is unknown
        fl = None
    try:
        pc = card_pct(b, float_read)
    except Exception:                                    # noqa: BLE001
        pc = None
    hi_card = SR.tier_of(pc) in TIERS if pc is not None else False
    rec_fl = _pos(b.get("float_shares")) if b else None
    out = {"listed": False, "reason": None, "tier": None, "float_check": None, "float_shares": fl,
           "si_float_shares": int(rec_fl) if rec_fl is not None else None, "pct_card": pc, "hi_card": hi_card}
    if b is None or b.get("status") == "no_record" or b.get("si_shares") is None:
        out["reason"] = "no_si"
        return out
    out["tier"], out["float_check"] = b.get("tier"), b.get("float_check")
    if b.get("status") == "stale":
        out["reason"] = "stale"
        return out
    tier = b.get("tier")
    if tier is None:
        out["reason"] = "no_tier"
        return out
    cap = _cap()
    if tier not in TIERS:
        out["reason"] = "floats_disagree" if (hi_card is True and fl is not None and fl <= cap) else "not_high"
        return out
    if fl is None:
        out["reason"] = "float_unknown"
        return out
    if fl > cap:
        out["reason"] = "float_over"
        return out
    if rec_fl is None:
        out["reason"] = "float_unknown"
        return out
    if rec_fl > cap:
        out["reason"] = "si_float_over"
        return out
    if hi_card is not True:
        out["reason"] = "floats_disagree"
        return out
    out["listed"] = True
    return out


# ── the evaluation (ONE per build: chip + block) ────────────────────────────────────────────────────────────────
def _add_text(doc: dict) -> Optional[str]:
    ctx = doc.get("ctx") if isinstance(doc, dict) and isinstance(doc.get("ctx"), dict) else {}
    parts = [t for t in (ctx.get("trader_text"), ctx.get("promo_text")) if isinstance(t, str) and t.strip()]
    return " · ".join(parts) if parts else None


def _empty_ev() -> dict:
    return {"rows": [], "counts": {r: 0 for r in REASONS}, "over": [], "disagree": [], "no_tier_low": [], "n_read": 0,
            "faults": [], "unconfirmed": 0, "carried": 0, "adds": [], "settlement": None, "refused": 0, "basis": []}


def evaluate(reads_by: dict, *, scan_row: Callable, session: date, now: datetime, v=None,
             si_read: Optional[Callable] = None, listed: Optional[dict] = None) -> dict:
    """ONE evaluation per build, shared by the strip chip and the 🩳 block. Raises TypeError when reads_by is not a dict
    and RuntimeError when the short-interest read could not be made (tab._soft serves FAULT_TEXT). Every name in its
    OWN try (a raising name → faults, the rest stand). GG5 only (any other variant → the empty result)."""
    from chart_maps.gajjala import tab as GT
    if not isinstance(reads_by, dict):
        raise TypeError("reads_by is not a dict")
    if not V.is_gg5(V.of(v)):
        return _empty_ev()
    if si_read is None:
        def si_read(syms):
            return si_blocks(syms, today=GT._et(now).date())
    syms = [str(s or "").upper() for s in reads_by]
    blocks = si_read(syms)
    if blocks is None:
        raise RuntimeError("short interest unread")
    ev = _empty_ev()
    ev["n_read"] = len(reads_by)
    s_iso = session.isoformat() if isinstance(session, (date, datetime)) else str(session)
    rows, newest = [], None
    for sym, doc in reads_by.items():
        s = str(sym or "").upper()
        try:
            b = blocks.get(s) if isinstance(blocks, dict) else None
            fr = GT._float_read(doc, None)
            c = classify(b, fr)
            if isinstance(b, dict) and isinstance(b.get("settlement_date"), str):
                if newest is None or b["settlement_date"] > newest["settlement_date"]:
                    newest = b
            if not c["listed"]:
                reason = c["reason"]
                ev["counts"][reason] += 1
                if reason == "float_over":
                    ev["over"].append({"symbol": s, "which": "card",
                                       "float_text": (GT._float_chip(fr) or {}).get("text") or DASH})
                elif reason == "si_float_over":
                    ev["over"].append({"symbol": s, "which": "record", "float_text": _compact(c["si_float_shares"])})
                elif reason == "floats_disagree":
                    ev["disagree"].append({"symbol": s, "tier_word": SR.TIER_WORDS.get(b.get("tier")),
                                           "pct_record": _f(b.get("pct_of_float")),
                                           "si_float_shares": c["si_float_shares"], "pct_card": c["pct_card"],
                                           "float_shares": c["float_shares"]})
                elif reason == "no_tier" and float_refused(b) is not None:
                    ev["refused"] += 1                              # [C7] never "no usable float"
                    on_file = SR.tier_of(_f(basis_of(b).get("float_pct_on_file")))
                    if on_file in TIERS:                            # it WAS High / EXTREME on the float on file
                        ev["basis"].append({"symbol": s, "chip": _s(b.get("chip")),
                                            "tier_word": SR.TIER_WORDS.get(on_file)})
                elif reason == "no_tier" and c["float_shares"] is not None and c["float_shares"] <= _cap():
                    ev["no_tier_low"].append(s)
                continue
            row_ = scan_row(s) or {}
            lrow = (listed or {}).get(s) if isinstance(listed, dict) else None
            read = {"tier": c["tier"], "tier_word": SR.TIER_WORDS.get(c["tier"]), "float_check": c["float_check"],
                    "tier_sentence": SR._tier_sentence(b), "si_chip": b.get("chip"),
                    "settlement_date": b.get("settlement_date"), "float_shares": c["float_shares"],
                    "si_float_shares": c["si_float_shares"], "pct_card": c["pct_card"],
                    "pct_record": _f(b.get("pct_of_float")),
                    "float_text": (GT._float_chip(fr) or {}).get("text"), "floats_text": floats_text(fr, b),
                    "session_volume": row_.get("volume"),
                    "carried": (lrow.get("last_qualified") != s_iso) if isinstance(lrow, dict) else None,
                    "add_text": _add_text(doc), "si_flags": si_flags(b)}
            rows.append({"symbol": s, "read": read, "read_doc": doc})
        except Exception as exc:                                    # noqa: BLE001 — one name never takes the sub down
            log.warning("gajjala high si: read %s failed: %s", s, type(exc).__name__)
            ev["faults"].append(s)
    rows.sort(key=lambda r: GT.vol_float_slot(r["read"]["session_volume"], r["read"]["float_shares"]) + (r["symbol"],))
    for k in ("over", "disagree"):
        ev[k].sort(key=lambda d: d["symbol"])
    ev["no_tier_low"].sort()
    ev["basis"].sort(key=lambda d: d["symbol"])
    ev["rows"] = rows
    ev["unconfirmed"] = sum(1 for r in rows if r["read"]["float_check"] == SR.FLOAT_UNCONFIRMED)
    ev["carried"] = sum(1 for r in rows if r["read"]["carried"] is True)
    ev["adds"] = [{"symbol": r["symbol"], "add_text": r["read"]["add_text"]} for r in rows if r["read"]["add_text"]]
    if newest is not None:
        ev["settlement"] = {k: newest.get(k) for k in ("settlement_date", "published_on", "next_due_on")}
    return ev


# ── the panel words (every number a constant read at CALL time) ─────────────────────────────────────────────────
def title() -> str:
    ring = (" · %d / %d EMA crosses ring your phone" % (GC.EMA_FAST, GC.EMA_SLOW)) if _live() else ""
    return ("%s High SI — his scanner's names with short interest %s or %s and a float at or under %s%s · UNMEASURED"
            % (_emoji(), _w(SR.TIER_HIGH), _w(SR.TIER_EXTREME), _cap_text(), ring))


def rule_text() -> str:
    hi, ex = _w(SR.TIER_HIGH), _w(SR.TIER_EXTREME)
    return ("Listed when a name on this tab's list has short interest %s or %s on the house ladder — %s — AND a float at "
            "or under %s shares (the 🎾 float cap). Two float reads exist: the float stored with the short-interest "
            "record (the 🩳 chip's %%) and this card's Float chip. A name is listed only when BOTH agree — %s or %s on "
            "the record's float, at or over the %s cut on the card's float, and both floats at or under the cap; a name "
            "the two reads disagree on is counted and named below, never listed. The tier word is the 🩳 chip's own: a "
            "stale read, a read with no usable float and a name with no FINRA record carry no word, so that name is "
            "not listed and is counted. A float on the short-interest record that is stale (more shares since it was "
            "read) or sits across a split from the short-interest count carries no tier word either, so that name is "
            "not listed; it is counted apart from the names with no usable float, and named above when it was %s or "
            "%s on that float. The 🔒 Reg SHO threshold tag is a tag when the name is on an exchange list, "
            "never a condition. Read off the stored short-interest record and this tab's stored bars; nothing is "
            "fetched." % (hi, ex, SR._ladder(), _cap_text(), hi, ex, hi, hi, ex))


def _latch_words() -> str:
    if GC.HIGH_SI_CROSS_LATCH == GC.HIGH_SI_CROSS_LATCHES[1]:
        return "once per name, chart and cross"
    return "once per name, chart and session"


def push_text() -> str:
    """The panel's push line: the 🔕 sentence while push_mode() is off, else the 🔔 sentence (candle-START mute)."""
    if not _live():
        return PUSH_OFF_TEXT.format(fast=GC.EMA_FAST, slow=GC.EMA_SLOW, call=GC.CLEAN_ALERTS_CALL,
                                    short=GC.CLEAN_ALERTS_SHORT)
    from chart_maps.gajjala import alerts as AL
    from chart_maps.gajjala import potential as PT
    cw = PT._clock_words()
    f5, f15 = (WC.FRAME_WORDS[t] for t in GC.HIGH_SI_CROSS_FRAMES)
    return ("🔔 Rings your phone when the %d EMA crosses ABOVE the %d EMA on a listed name's latest closed %s or %s "
            "candle — each chart on its own cross, %s; never the candle still printing; a cross under never rings. "
            "Held on a closed day, outside %s–%s ET (%s on a half day), on a candle that STARTED in GG's first %d "
            "minutes after the open, and under GG's %s-share session floor. A cross missed by a skipped pass is never "
            "sent late. %s. %s"
            % (GC.EMA_FAST, GC.EMA_SLOW, f5, f15, _latch_words(), cw["open"], cw["close"],
               AL.HALF_DAY_AH_CLOSE.strftime("%H:%M"), cw["n"], _floor_text(), AL.FADE_CROSS_TAIL, NOT_ADVICE))


def honesty() -> str:
    from chart_maps.gajjala import divergence_tab as DVT
    is_from, is_to, n_sessions = GC.DIVERGENCE_IS_WINDOW
    ah, rth = GC.DIVERGENCE_IS["ah"], GC.DIVERGENCE_IS["rth"]
    sg = DVT._sgn
    return ("UNMEASURED — nothing has measured this list or a cross on it. The one house study of an entry after this "
            "cross is the 🧨 Divergence rule (the cross plus that rule's own conditions, on its own names — not this "
            "list; %d sessions, %s → %s): after hours %s (%d trades, %s%% net per trade [%s, %s]) · regular hours %s "
            "(%d trades, %s%% [%s, %s]); its out-of-sample read is sealed until %s ET. Short interest is a count of "
            "open short positions at the last FINRA settlement (two a month, published about %d business days later) "
            "— not a forecast. A cross is information, never an entry: no gate, no record, no trade, and the 🚩 lane "
            "never trades these alerts. A name here can reverse as easily as run. %s"
            % (n_sessions, is_from, is_to, ah["word"], ah["trades"], sg(ah["mean_net"]), sg(ah["lo"]), sg(ah["hi"]),
               rth["word"], rth["trades"], sg(rth["mean_net"]), sg(rth["lo"]), sg(rth["hi"]),
               GC.DIVERGENCE_OOS_SEAL_ET, SR.FINRA_PUBLICATION_BDAYS, NOT_ADVICE))


def cohort_text() -> str:
    return ("Names read: every name on this tab's stored 5-minute reads this session — his scanner's qualifiers (price "
            "$%g–$%g, at least %s shares and %g%% on the day), each kept %d more sessions after the day it last "
            "qualified, plus the names a tracked trader (📌) or the Promo circuit (🎪) put on his list — those skip his "
            "change and volume floors. Short interest and float are read as of now. Nothing new fetched."
            % (GC.SCAN_MIN_PRICE, GC.SCAN_MAX_PRICE, f"{int(GC.SCAN_MIN_VOLUME):,}", GC.SCAN_MIN_CHANGE_PCT,
               GC.STAY_LISTED_SESSIONS))


def counts_text(ev: dict) -> str:
    """"{n_read} listed names read · {n} listed here[ (…unconfirmed)] · not listed: " + the NON-ZERO segments (REASONS
    order, then faults). The printed numbers always sum to n_read − n."""
    ev = ev or {}
    c = ev.get("counts") or {}
    n = len(ev.get("rows") or [])
    u = int(ev.get("unconfirmed") or 0)
    hi, ex = _w(SR.TIER_HIGH), _w(SR.TIER_EXTREME)
    lo, mo = _w(SR.TIER_LOW), _w(SR.TIER_MODERATE)
    cap = _cap_text()
    j = len(ev.get("no_tier_low") or [])
    try:
        m = int(ev.get("refused") or 0)
    except (TypeError, ValueError):
        m = 0
    k_nt = int(c.get("no_tier") or 0)
    if m > 0:
        no_tier_head = (NO_TIER_REFUSED_HEAD + (NO_TIER_REFUSED_REST if k_nt > m else "")).replace("{m}", str(m))
    else:
        no_tier_head = "{k} with no tier word (no usable float on the short-interest record"
    words = {
        "float_over": "{k} %s / %s with a card float over %s" % (hi, ex, cap),
        "si_float_over": "{k} %s / %s with a short-interest-record float over %s" % (hi, ex, cap),
        "floats_disagree": "{k} where the two float reads disagree on %s" % hi,
        "float_unknown": "{k} %s / %s with an unknown float" % (hi, ex),
        "not_high": "{k} %s or %s" % (lo, mo),
        "stale": "{k} on a stale read",
        "no_tier": (no_tier_head
                    + ("; %d of them with a card float at or under the cap" % j if j else "") + ")"),
        "no_si": "{k} with no short-interest record",
    }
    segs = [words[r].format(k=int(c.get(r) or 0)) for r in REASONS if int(c.get(r) or 0) > 0]
    nf = len(ev.get("faults") or [])
    if nf:
        segs.append("%d unreadable this time" % nf)
    head = "%d listed names read · %d listed here" % (int(ev.get("n_read") or 0), n)
    if u:
        head += " (%d of them %s · %s)" % (u, hi, SR.FLOAT_UNCONFIRMED_WORD)
    return head + " · not listed: " + (" · ".join(segs) if segs else "none")


def adds_text(ev: dict) -> Optional[str]:
    rows = (ev or {}).get("rows") or []
    n = len(rows)
    if n <= 0:
        return None
    c = int((ev or {}).get("carried") or 0)
    out = ("Of the %d listed here: %d qualified on his scanner today · %d carried from an earlier session (did not "
           "qualify today)" % (n, n - c, c))
    adds = [a for a in ((ev or {}).get("adds") or []) if isinstance(a, dict) and a.get("add_text")]
    if adds:
        out += (" · %d named by a tracked trader or the Promo circuit, without his change and volume floors: %s"
                % (len(adds), " · ".join("%s (%s)" % (a["symbol"], a["add_text"]) for a in adds)))
    return out


def asof_text(ev: dict) -> Optional[str]:
    s = (ev or {}).get("settlement")
    if not isinstance(s, dict) or not s.get("settlement_date"):
        return None
    out = "Short interest as of the FINRA settlement %s" % SR._md(s["settlement_date"])
    if s.get("published_on"):
        out += " (published ~%s)" % SR._md(s["published_on"])
    if s.get("next_due_on"):
        out += "; the next one is due ~%s" % SR._md(s["next_due_on"])
    return out + "."


def floats_text(float_read, si_block) -> Optional[str]:
    """Both floats, each labelled — ONE function (the card's float row and the push body). None when either read has
    no positive share count."""
    from chart_maps.gajjala import tab as GT
    if float_shares(float_read) is None or not isinstance(si_block, dict) or _pos(si_block.get("float_shares")) is None:
        return None
    ft = (GT._float_chip(float_read) or {}).get("text") or DASH
    fu = (basis_of(si_block) or {}).get("float_update")
    if isinstance(fu, dict) and _pos(fu.get("replaced_shares")) is not None:
        # 2026-11-24 later — the block divides by Yahoo's newer float, not the short-interest record's
        asof = si_block.get("float_asof") or fu.get("as_of")
        return ("%s on this card · %s from Yahoo's newer read%s, replacing %s on the short-interest record"
                % (ft, _compact(si_block.get("float_shares")), (" (%s)" % SR._md(asof)) if asof else "",
                   _compact(fu.get("replaced_shares"))))
    return "%s on this card · %s on the short-interest record" % (ft, _compact(si_block.get("float_shares")))


def _sho_payload(now):
    from short_interest import reg_sho as RS
    return RS.payload(kick=False, now=now)


def closeout_date(item) -> Optional[str]:
    """The 🔒 tag's day-13 date (ISO) when it is upcoming or today — else None. Never raises."""
    try:
        if not isinstance(item, dict) or item.get("state") != "on" or item.get("stale") is True:
            return None
        run = item.get("run")
        if not isinstance(run, dict) or run.get("state") not in CLOSEOUT_UPCOMING_STATES:
            return None
        d = run.get("day13")
        if not isinstance(d, str):
            return None
        date.fromisoformat(d)
        return d
    except (TypeError, ValueError):
        return None


def closeout_order(rows: list, items) -> list:
    """Rows with an upcoming close-out date first (nearest first), the rest after — a STABLE sort, so the house order
    (volume → float) holds inside each date and among the undated. `items` = the Reg SHO payload's items (may be {})."""
    items = items if isinstance(items, dict) else {}

    def key(r):
        d = closeout_date(items.get(str((r or {}).get("symbol") or "").upper()))
        return (0, d) if d else (1, "")
    return sorted(list(rows), key=key)


def sho_text(rows: list, *, now, sho_read: Optional[Callable] = None) -> Optional[str]:
    """🔒 how many listed names sit on a Reg SHO threshold list — a TAG. Reads payload["complete"]: an unread exchange
    list is named and "None …" prints only when every list was read. None when no row or the read raises."""
    if not rows:
        return None
    try:
        from short_interest import reg_sho as RS
        p = (sho_read or _sho_payload)(now)
        items = (p or {}).get("items") or {}
        syms = [str(r.get("symbol") or "").upper() for r in rows if isinstance(r, dict)]
        n, k = len(syms), sum(1 for s in syms if s in items)
        g = RS.GLYPH
        if (p or {}).get("complete") is True:
            if k == 0:
                return "%s None of the %d listed is on a Reg SHO threshold list — a tag, not a condition." % (g, n)
            return "%s %d of the %d listed are on a Reg SHO threshold list — a tag, not a condition." % (g, k, n)
        unread = "; ".join(str(s.get("text")) for s in ((p or {}).get("sources") or [])
                           if isinstance(s, dict) and s.get("ok") is not True and s.get("text"))
        if k > 0:
            return ("%s %d of the %d listed are on a Reg SHO threshold list — at least: %s. A tag, not a condition."
                    % (g, k, n, unread or DASH))
        return ("%s Not every Reg SHO threshold list could be read: %s. A missing tag does not mean a name is on no "
                "list." % (g, unread or DASH))
    except Exception as exc:                                        # noqa: BLE001 — the panel still serves
        log.warning("gajjala high si: reg sho read failed: %s", type(exc).__name__)
        return None


def excluded_text(ev: dict) -> Optional[str]:
    over = (ev or {}).get("over") or []
    if not over:
        return None
    parts = [("%s (card %s)" % (o["symbol"], o.get("float_text") or DASH)) if o.get("which") == "card"
             else ("%s (record float %s)" % (o["symbol"], o.get("float_text") or DASH)) for o in over]
    return "%s / %s but over the float cap: %s" % (_w(SR.TIER_HIGH), _w(SR.TIER_EXTREME), " · ".join(parts))


def disagree_text(ev: dict) -> Optional[str]:
    dis = (ev or {}).get("disagree") or []
    if not dis:
        return None
    parts = ["%s — %s on the short-interest record's float (%s of %s), %s of this card's float (%s)"
             % (d["symbol"], d.get("tier_word") or DASH, _pct(d.get("pct_record")), _compact(d.get("si_float_shares")),
                _pct(d.get("pct_card")), _compact(d.get("float_shares"))) for d in dis]
    return "The two float reads disagree — not listed: " + " · ".join(parts)


def no_tier_text(ev: dict) -> Optional[str]:
    names = (ev or {}).get("no_tier_low") or []
    if not names:
        return None
    return ("Short interest on file but no tier word (no usable float on the short-interest record), card float at or "
            "under %s: %s — the tier is never worked out on the card's float here." % (_cap_text(), " · ".join(names)))


def basis_text(ev: dict) -> Optional[str]:
    """[C7] The names the house read refused a float for that were High / EXTREME on that float on file — `SYM — <the
    block's served 🩳 chip>`. None when there is none."""
    names = [d for d in ((ev or {}).get("basis") or []) if isinstance(d, dict) and _s(d.get("symbol"))]
    if not names:
        return None
    return BASIS_TEXT % (_w(SR.TIER_HIGH), _w(SR.TIER_EXTREME),
                         " · ".join("%s — %s" % (d["symbol"], _s(d.get("chip")) or DASH) for d in names))


def empty_today() -> str:
    return ("No name on his list has short interest %s or %s with a float at or under %s right now."
            % (_w(SR.TIER_HIGH), _w(SR.TIER_EXTREME), _cap_text()))


def empty_session(label: str) -> str:
    return EMPTY_SESSION.format(high=_w(SR.TIER_HIGH), extreme=_w(SR.TIER_EXTREME), cap=_cap_text(), label=label)


# ── the card rows ───────────────────────────────────────────────────────────────────────────────────────────────
def volume_row(volume) -> dict:
    """The K11 row: a known volume → DT.k11_criterion unchanged (✓ / ✗). An unknown one (a carried name has no scan row
    today) → ok None and "judged at the ring" — never ✗ (the pass reads the live snapshot)."""
    floor = int(GC.K11_MIN_SESSION_VOLUME)
    if DT._k11_volume(volume) is None:
        return DT.criterion(DT.K11_KEY, "K11 no volume stored for this name today — the push floor (≥ %s) is judged "
                            "at the ring on the pass's own volume read" % f"{floor:,}", None, "", "≥ %s" % f"{floor:,}")
    return DT.k11_criterion(volume)


def cross_row(fr: dict, tf: str) -> dict:
    """A criteria row from tab.ema_cross_block over the stored curves (the ONE engine; no EMA comparison here)."""
    from chart_maps.gajjala import tab as GT
    blk = GT.ema_cross_block(fr) if isinstance(fr, dict) else None
    ok = None if not blk else (blk.get("dir") == "up")
    return {"key": "cross_" + tf, "label": "%d / %d EMA · %s" % (GC.EMA_FAST, GC.EMA_SLOW, WC.FRAME_WORDS.get(tf, tf)),
            "value": (blk.get("text") if blk else None) or NO_CROSS_TEXT,
            "need": "a cross above on the latest closed candle rings your phone" if _live() else "", "ok": ok}


def rang_today(st, session) -> dict:
    """{SYM: [(frame, bar_t), …]} of today's PUSHED 🩳 cross claims, sorted by bar_t; {} on any fault / no collection."""
    try:
        from chart_maps.gajjala import alerts as AL
        coll = st.alerts_coll() if st is not None else None
        if coll is None:
            return {}
        iso = session.isoformat() if isinstance(session, (date, datetime)) else str(session)
        prefix = GC.HIGH_SI_CROSS_CLAIM_PREFIX + ":"
        out: dict = {}
        for d in coll.find({"date": iso, "kind": GC.HIGH_SI_CROSS_PUSH_KIND, "state": AL.FADE_CROSS_STATES[1]}):
            if not isinstance(d, dict) or d.get("kind") != GC.HIGH_SI_CROSS_PUSH_KIND:
                continue
            if d.get("state") != AL.FADE_CROSS_STATES[1] or not str(d.get("_id") or "").startswith(prefix):
                continue
            sym, fr, bt = str(d.get("symbol") or "").upper(), d.get("frame"), d.get("bar_t")
            if sym and fr in GC.HIGH_SI_CROSS_FRAMES and isinstance(bt, str):
                out.setdefault(sym, []).append((fr, bt))
        return {s: sorted(v, key=lambda x: x[1]) for s, v in out.items()}
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala high si: rang read failed: %s", type(exc).__name__)
        return {}


def card(read_doc: dict, row: dict, *, tf: str, scan_row: dict, sess: dict, halt_doc, listed_info, pass_at, v,
         rang: Optional[list] = None) -> dict:
    """One house card for one listed name, on the frame `tf`. No buy marker, no ENTRY line, no plan. Raises on a
    malformed stored tile (the caller's per-name fence)."""
    from chart_maps.gajjala import tab as GT
    vv = V.of(v)
    tile = read_doc.get("tile")
    t = tf if tf in vv.tfs else vv.primary
    suf = str(V.frame_minutes(t, vv))
    if not isinstance(tile, dict) or not isinstance(tile.get(f"bars{suf}"), list):
        raise ValueError("malformed stored tile")
    fr = GT._tile_frame(read_doc, tf, vv)
    sym = str(row.get("symbol") or "").upper()
    r = row["read"]
    hi, ex = _w(SR.TIER_HIGH), _w(SR.TIER_EXTREME)
    frames = {f: (fr if f == fr["tf"] else GT._tile_frame(read_doc, f, vv)) for f in GC.HIGH_SI_CROSS_FRAMES}
    markers = []
    cross = GT.ema_cross_block(fr)
    if cross:
        markers += [{"date": m["t"], "kind": GT.EMA_CROSS_MARK[m["dir"]], "label": m["text"], "price": _f(m["ema"])}
                    for m in cross.get("_marks") or []]
    markers = GT._on_bars(markers, fr["bars"])
    stats = [s for s in ({"k": "Change", "v": GT._pct(scan_row.get("change_pct"))},
                         {"k": "Volume", "v": GT._compact(scan_row.get("volume"))}) if s["v"]]
    chips = GT._chips(read_doc, GC.HIGH_SI_SUB, {}, scan_row, sess, halt_doc, None, pass_at=pass_at)
    criteria = [
        {"key": "si_tier", "label": "short interest",
         "value": ((r.get("tier_sentence") or "") + " On this card's float the same short interest is %s — also at or "
                   "over the %s cut." % (_pct(r.get("pct_card")), hi)).strip(),
         "need": "%s or %s on the house ladder, on both float reads" % (hi, ex), "ok": True},
        {"key": "float", "label": "float", "value": r.get("floats_text") or DASH,
         "need": "both at or under %s" % _cap_text(), "ok": True},
        *[cross_row(frames[f], f) for f in GC.HIGH_SI_CROSS_FRAMES],
        volume_row(r.get("session_volume")),
    ]
    sq = squeeze_read(read_doc)
    if sq is not None:
        criteria.append(squeeze_row(sq))
    if rang:
        criteria.append({"key": "rang", "label": "🔔 rang today",
                         "value": " · ".join("%s %s ET" % (WC.FRAME_WORDS.get(f, f), _hhmm(bt) or DASH)
                                             for f, bt in rang),
                         "need": "", "ok": True})
    g = {"setup": GC.HIGH_SI_SUB, "state": STATE,
         "state_label": "%s · float at or under %s%s" % (tier_chip(r), _cap_text(),
                                                         " · %s %s" % (SQUEEZE_TAG, squeeze_word(sq)) if sq else ""),
         "criteria": criteria, "missed": [], "unjudged": [], "plan_text": None, "chips": chips,
         "listed": GT._listed_block(listed_info),
         "high_si": {"tier": r.get("tier"), "float_check": r.get("float_check"), "si_chip": r.get("si_chip"),
                     "carried": r.get("carried"), "add_text": r.get("add_text"),
                     "squeeze": ({"state": sq["state"], "word": squeeze_word(sq)} if sq else None)}}
    vol_avg = fr.get("vol_avg") if isinstance(fr.get("vol_avg"), dict) else None
    out = {"symbol": sym, "name": read_doc.get("name"), "href": GT.chart_href(sym, fr["tf"], vv), "tf": fr["tf"],
           "bars": fr["bars"], "vol_avg": vol_avg, "bands": [], "lines": [], "markers": markers, "stats": stats,
           "why": "", "badges": [], "curves": fr["curves"], "ema_blink": GT.ema_blink_of(fr), "gajjala": g}
    ax = GT.card_axis(fr, vv, sym=sym)
    if ax is not None:
        out["axis"] = ax
    return out


def _cards(rows: list, *, tf: str, scan_row: Callable, sess: dict, halts_by: dict, listed: dict, pass_at, v,
           rang: dict) -> tuple:
    """(tiles, chartless, faults) — EACH listed name in its own try; a name is never dropped from the words."""
    from chart_maps.gajjala import tab as GT
    tiles, chartless, faults = [], [], []
    for row in rows:
        sym = row["symbol"]
        line = {"symbol": sym, "at_text": None, "state_label": None, "href": None,
                "text": CHARTLESS_TEXT.format(sym=sym or DASH)}
        try:
            line["state_label"] = tier_chip(row["read"])
            line["href"] = GT.chart_href(sym, tf, v) if sym else None
            t = card(row["read_doc"], row, tf=tf, scan_row=scan_row(sym), sess=sess,
                     halt_doc=(halts_by or {}).get(sym), listed_info=(listed or {}).get(sym), pass_at=pass_at, v=v,
                     rang=(rang or {}).get(sym))
            if not t["bars"]:
                chartless.append(line)
                continue
            tiles.append(t)
        except Exception as exc:                                    # noqa: BLE001 — one name never takes the sub down
            log.warning("gajjala high si tab: card %s failed: %s", sym, type(exc).__name__)
            chartless.append(line)
            faults.append(sym)
    return tiles, chartless, faults


# ── ⛔ SSR "new today" list (2026-11-24, SPEC ssrlist §3.3, WP be-block) ──────────────────────────────────────────
# Ajay 2026-11-24: "What are the SSR stocks today" · "Can you add it to short interest tab" · "The new ones". The names
# whose short-sale restriction STARTED in the session shown, resolved by the ⛔ SSR tag's ONE engine
# (short_interest.ssr.new_triggers, lazy import in _ssr_read only), split into four folds by the tab's own two facts —
# on GG's 🚩 list (`listed`), High / EXTREME house tier (SR.si_tier via si_blocks). Display only: no push, no gate, no
# order change of the 🩳 cards, no lane. A display reader: this section never asks the lists to refresh. UNMEASURED.
SSR_NEW_KEY = "ssr_new"
SSR_NEW_KIND = "ssr_new_triggers"                 # == ssr.NEW_KIND (pinned by the integration test)
SSR_NEW_GROUPS = ("list_high", "list_other", "high", "rest")
SSR_NEW_MIXED = ("list_other", "rest")            # the folds that can hold a name with no tier [C2]
SSR_NEW_OPEN = ()                                 # HIS CALL 2 — the folds printed open
SSR_NEW_NAMED = ("list_high",)                    # the folds whose line names their tickers
SSR_NEW_BLOCK_KEYS = ("title", "counts_text", "tier_note", "window_text", "asof_text", "status_text", "partial_text",
                      "si_note", "list_note", "faults_text", "fault_text", "empty_text", "order_note", "rule_label",
                      "rule_text", "note_text", "withheld_text", "n", "n_untiered", "groups")
SSR_NEW_GROUP_KEYS = ("key", "summary", "count", "open", "rows")
SSR_NEW_ROW_KEYS = ("symbol", "href", "at_text", "drop_text", "source_text", "mark_text", "si_text")
SSR_NEW_COPIED = ("title", "window_text", "asof_text", "status_text", "partial_text", "faults_text", "fault_text",
                  "rule_text", "note_text", "withheld_text")          # the engine's own served texts, copied as is

SSR_NEW_FAULT = ("⛔ The list of names newly under SSR could not be built this time — the next re-read tries again. A "
                 "missing list does not mean no name triggered.")
SSR_NEW_SI_UNREAD = ("Short interest could not be read this time — the names are not split or ordered by it, and a "
                     "missing 🩳 does not mean a name has none.")
SSR_NEW_LIST_UNREAD = "His list is empty or could not be read this time — the names are not split by it."
SSR_NEW_RULE_LABEL = "ⓘ how this list is read"
SSR_NEW_TIER_NOTE = ("{U} of the {n} names are not tiered — no current short interest % of float on file — so the {hi} "
                     "/ {ex} counts are a floor, and a name under “not tiered” may still be heavily shorted.")
SSR_NEW_UNTIERED_TAIL = " ({u} not tiered)"
SSR_NEW_ORDER_NOTE = ("Inside each fold: {ex} first, then {hi}, then the lower tiers, then the names not tiered; inside "
                      "each, the highest short interest % of float first; a name with no % of float goes last, A to Z.")
SSR_NEW_SUMMARY = {
    "list_high": "🚩 on his list · {hi} or {ex} short interest — {k}: {tickers}",
    "list_other": "🚩 on his list · short interest under {hi} or not tiered — {k}",
    "high": "🩳 {hi} or {ex} short interest · not on his list — {k}",
    "rest": "every other name — {k}",
}
SSR_NEW_SUMMARY_LIST_SI_UNREAD = "🚩 on his list — {k}"
SSR_NEW_SUMMARY_HIGH_LIST_UNREAD = "🩳 {hi} or {ex} short interest — {k}"
SSR_NEW_COUNTS = ("{n} names · {on_list} on his 🚩 list ({list_high} with {hi} or {ex} short interest) · {high} more "
                  "with {hi} or {ex} short interest · {rest} others")
SSR_NEW_COUNTS_SI_UNREAD = "{n} names · {on_list} on his 🚩 list · {rest} others"
SSR_NEW_COUNTS_LIST_UNREAD = "{n} names · {high} with {hi} or {ex} short interest · {rest} others"
SSR_NEW_COUNTS_BARE = "{n} names"
SSR_NEW_RULES_LINE = ("⛔ New SSR names on the 🩳 High SI sub: every name whose short-sale restriction started in the "
                      "session shown, read by the ⛔ SSR tag's own rules, in four folds — on his 🚩 list with {hi} or "
                      "{ex} short interest, on his list otherwise, {hi} or {ex} off his list, every other name. A name "
                      "with no current short interest % of float on file is counted as not tiered. A list only: it "
                      "pushes nothing, gates nothing, sorts no 🩳 card and enters no lane. UNMEASURED.")


def _ssr_read(session, now):
    """The engine's answer for the session shown — the ONE import of the ⛔ SSR engine in this module."""
    from short_interest import ssr as SSR
    return SSR.new_triggers(session, now=now)


def _ssr_s(x) -> Optional[str]:
    return x if isinstance(x, str) and x.strip() else None


def ssr_si_text(b) -> Optional[str]:
    """The house 🩳 chip AS IS whenever the block carries one — any basis (float, shares out, a share count) [C2]."""
    return _ssr_s(b.get("chip")) if isinstance(b, dict) else None


def ssr_tiered(b) -> bool:
    """True when the house read gave the name a tier word (SR.si_tier: float basis AND an ok read)."""
    return isinstance(b, dict) and b.get("tier") in SR.TIER_ORDER


def ssr_new_rank(b) -> tuple:
    """Inside a fold: EXTREME, High, Moderate, Low, then no tier; inside each the highest % of float; no % last."""
    t = -SR.TIER_ORDER.index(b.get("tier")) if ssr_tiered(b) else 1
    p = _f(b.get("pct_of_float")) if isinstance(b, dict) else None
    return (t, 0, -p) if p is not None else (t, 1, 0)


def ssr_new_fault() -> dict:
    out = {k: None for k in SSR_NEW_BLOCK_KEYS}
    out["fault_text"] = SSR_NEW_FAULT
    out["groups"] = []
    return out


def ssr_new_rules_line() -> str:
    """The ℹ️ sentence for the new list — the tier words read at call time [C7a]."""
    return SSR_NEW_RULES_LINE.format(hi=_w(SR.TIER_HIGH), ex=_w(SR.TIER_EXTREME))


def ssr_new_block(listed, *, session, now, tf, v=None, ssr_read: Optional[Callable] = None,
                  si_read: Optional[Callable] = None) -> dict:
    """The ⛔ new-today section (served as high_si.ssr_new). Copies the engine's texts, splits its rows into the four
    SSR_NEW_GROUPS folds and orders each by ssr_new_rank. Unknown is never a yes. Never raises (→ ssr_new_fault())."""
    try:
        ans = (ssr_read or _ssr_read)(session, now)
        if not isinstance(ans, dict) or ans.get("kind") != SSR_NEW_KIND:
            return ssr_new_fault()
        hi, ex = _w(SR.TIER_HIGH), _w(SR.TIER_EXTREME)
        out = {k: None for k in SSR_NEW_BLOCK_KEYS}
        for k in SSR_NEW_COPIED:
            out[k] = _ssr_s(ans.get(k))
        out["rule_label"] = SSR_NEW_RULE_LABEL
        out["groups"] = []
        if ans.get("status") != "ok" or out["fault_text"] is not None:
            return out
        raw = ans.get("rows")
        rows = [(r["symbol"].strip(), r) for r in (raw if isinstance(raw, list) else [])
                if isinstance(r, dict) and _ssr_s(r.get("symbol"))]
        n = len(rows)
        out["n"] = n
        if not rows:
            out["empty_text"] = _ssr_s(ans.get("empty_text"))
            out["n_untiered"] = 0
            return out
        from chart_maps.gajjala import store as ST
        from chart_maps.gajjala import tab as GT
        syms = [s for s, _r in rows]
        try:
            blocks = si_read(syms) if si_read is not None else si_blocks(syms, today=GT._et(now).date())
        except Exception as exc:                                    # noqa: BLE001 — the list stands, said so
            log.warning("gajjala high si: ssr new si read failed: %s", type(exc).__name__)
            blocks = None
        si_ok = isinstance(blocks, dict)
        list_ok = isinstance(listed, dict) and bool(listed)
        on_keys = {ST.broker_fold(k) for k in listed} - {""} if list_ok else set()
        by: dict = {g: [] for g in SSR_NEW_GROUPS}
        untiered = {g: 0 for g in SSR_NEW_GROUPS}
        for sym, r in rows:
            b = blocks.get(sym.upper()) if si_ok else None
            b = b if isinstance(b, dict) else None
            high = si_ok and ssr_tiered(b) and b.get("tier") in TIERS
            if list_ok and ST.broker_fold(sym) in on_keys:
                g = "list_high" if high else "list_other"
            else:
                g = "high" if high else "rest"
            if si_ok and not ssr_tiered(b):
                untiered[g] += 1
            try:
                href = GT.chart_href(sym, tf, v)
            except Exception:                                       # noqa: BLE001 — a row never needs its link
                href = None
            row = {"symbol": sym, "href": href, "at_text": _ssr_s(r.get("at_text")),
                   "drop_text": _ssr_s(r.get("drop_text")), "source_text": _ssr_s(r.get("source_text")),
                   "mark_text": _ssr_s(r.get("mark_text")), "si_text": ssr_si_text(b) if si_ok else None}
            by[g].append((ssr_new_rank(b) + (sym,), row))
        for g in SSR_NEW_GROUPS:
            items = [row for _k, row in sorted(by[g], key=lambda x: x[0])]
            if not items:
                continue
            k = len(items)
            if g == "list_other" and not si_ok:
                summary = SSR_NEW_SUMMARY_LIST_SI_UNREAD.format(k=k)
            elif g == "high" and not list_ok:
                summary = SSR_NEW_SUMMARY_HIGH_LIST_UNREAD.format(hi=hi, ex=ex, k=k)
            else:
                summary = SSR_NEW_SUMMARY[g].format(hi=hi, ex=ex, k=k, tickers=" ".join(r["symbol"] for r in items))
            if g in SSR_NEW_MIXED and si_ok and untiered[g] > 0:
                summary += SSR_NEW_UNTIERED_TAIL.format(u=untiered[g])
            out["groups"].append({"key": g, "summary": summary, "count": k, "open": g in SSR_NEW_OPEN,
                                  "rows": items})
        c = {g: len(by[g]) for g in SSR_NEW_GROUPS}
        fmt = dict(n=n, hi=hi, ex=ex, on_list=c["list_high"] + c["list_other"], list_high=c["list_high"],
                   high=c["high"], rest=c["rest"])
        tmpl = (SSR_NEW_COUNTS if si_ok and list_ok else SSR_NEW_COUNTS_SI_UNREAD if list_ok
                else SSR_NEW_COUNTS_LIST_UNREAD if si_ok else SSR_NEW_COUNTS_BARE)
        parts = [tmpl.format(**fmt)] + [t for t in (_ssr_s(ans.get("sources_text")),
                                                     _ssr_s(ans.get("retriggered_text"))) if t]
        out["counts_text"] = " · ".join(parts)
        total = sum(untiered.values())
        out["n_untiered"] = total if si_ok else None
        out["tier_note"] = SSR_NEW_TIER_NOTE.format(U=total, n=n, hi=hi, ex=ex) if si_ok and total > 0 else None
        out["si_note"] = None if si_ok else SSR_NEW_SI_UNREAD
        out["list_note"] = None if list_ok else SSR_NEW_LIST_UNREAD
        out["order_note"] = SSR_NEW_ORDER_NOTE.format(hi=hi, ex=ex) if si_ok else None
        return out
    except Exception as exc:                                        # noqa: BLE001 — the 🩳 sub never goes down for it
        log.warning("gajjala high si: ssr new list failed: %s", type(exc).__name__)
        return ssr_new_fault()


# ── the served block ────────────────────────────────────────────────────────────────────────────────────────────
def block(ev: Optional[dict], *, session: date, now: datetime, is_today: bool, in_window: bool, tf: str, lim: int,
          scan_row: Callable, sess: dict, halts_by: dict, listed: dict, pass_at, flags, v, st=None,
          sho_read: Optional[Callable] = None, ssr_read: Optional[Callable] = None,
          ssr_si_read: Optional[Callable] = None) -> Optional[dict]:
    """The 🩳 sub's served block (+ `_tiles`, popped by tab.build). None ONLY when the evaluation faulted (`ev` None →
    tab serves FAULT_TEXT). `lim` is used for `shown_text` only (tab.build makes the cut; `flags` = its broker order).
    `ssr_new` = the ⛔ new-today section (ssr_new_block), fenced on its own — it never moves a card or a text above."""
    if ev is None:
        return None
    rows = list(ev.get("rows") or [])
    n = len(rows)
    try:                                                            # the Reg SHO payload read ONCE (tag + order)
        sho_pay, sho_err = (sho_read or _sho_payload)(now), None
    except Exception as exc:                                        # noqa: BLE001 — the house order then, said so
        sho_pay, sho_err = None, exc

    def _sho_once(_now):
        if sho_err is not None:
            raise sho_err
        return sho_pay
    sho_items = (sho_pay or {}).get("items") if isinstance(sho_pay, dict) else None
    rows = closeout_order(rows, sho_items)
    if not isinstance(sho_items, dict):
        order_note = ORDER_NOTE + ORDER_SHO_UNREAD
    elif sho_pay.get("complete") is not True:
        order_note = ORDER_NOTE + ORDER_SHO_PARTIAL
    else:
        order_note = ORDER_NOTE
    rang = rang_today(st, session)
    label = (sess or {}).get("label") or (session.isoformat() if isinstance(session, (date, datetime)) else str(session))
    out = {"title": title(), "ask_text": ASK_TEXT, "rule_label": RULE_LABEL, "rule_text": rule_text(),
           "honesty": honesty(), "cohort_text": cohort_text(), "counts_text": counts_text(ev),
           "adds_text": adds_text(ev), "asof_text": asof_text(ev),
           "sho_text": sho_text(rows, now=now, sho_read=_sho_once), "push_text": push_text(), "order_note": order_note,
           "shown_text": SHOWN_TEXT.format(lim=lim, n=n) if isinstance(lim, int) and n > lim else None,
           "excluded_text": excluded_text(ev), "disagree_text": disagree_text(ev), "no_tier_text": no_tier_text(ev),
           "basis_text": basis_text(ev), "n": n, "n_read": int(ev.get("n_read") or 0),
           "empty_text": None if rows else (empty_today() if is_today else empty_session(label))}
    tiles, chartless, card_faults = _cards(rows, tf=tf, scan_row=scan_row, sess=sess, halts_by=halts_by, listed=listed,
                                           pass_at=pass_at, v=v, rang=rang)
    faults = list(dict.fromkeys(list(ev.get("faults") or []) + card_faults))
    out["chartless"] = chartless
    out["faults"] = faults
    out["faults_text"] = FAULTS_TEXT.format(n=len(faults)) if faults else None
    try:
        out[SSR_NEW_KEY] = ssr_new_block(listed, session=session, now=now, tf=tf, v=v, ssr_read=ssr_read,
                                         si_read=ssr_si_read)
    except Exception as exc:                                        # noqa: BLE001 — the cards stand
        log.warning("gajjala high si: ssr new section failed: %s", type(exc).__name__)
        out[SSR_NEW_KEY] = ssr_new_fault()
    out["_tiles"] = tiles
    return out


__all__ = ["TIERS", "STATE", "REASONS", "NOT_ADVICE", "ASK_TEXT", "RULE_LABEL", "PUSH_OFF_TEXT", "ORDER_NOTE",
           "ORDER_SHO_UNREAD", "ORDER_SHO_PARTIAL", "CLOSEOUT_UPCOMING_STATES", "closeout_date", "closeout_order",
           "SHOWN_TEXT", "FAULT_TEXT", "FAULTS_TEXT", "CHARTLESS_TEXT", "push_mode", "si_blocks", "float_shares",
           "card_pct", "classify", "evaluate", "title", "rule_text", "push_text", "honesty", "cohort_text",
           "counts_text", "adds_text", "asof_text", "floats_text", "sho_text", "excluded_text", "disagree_text",
           "no_tier_text", "BASIS_TEXT", "NO_TIER_REFUSED_WORDS", "NO_TIER_REFUSED_HEAD",
           "NO_TIER_REFUSED_REST", "basis_of", "float_refused", "si_flags",
           "basis_text", "empty_today", "empty_session", "volume_row", "cross_row", "rang_today", "card", "block",
           "SSR_NEW_KEY", "SSR_NEW_KIND", "SSR_NEW_GROUPS", "SSR_NEW_MIXED", "SSR_NEW_OPEN", "SSR_NEW_NAMED",
           "SSR_NEW_BLOCK_KEYS", "SSR_NEW_GROUP_KEYS", "SSR_NEW_ROW_KEYS", "SSR_NEW_FAULT", "SSR_NEW_SI_UNREAD",
           "SSR_NEW_LIST_UNREAD", "SSR_NEW_RULE_LABEL", "SSR_NEW_TIER_NOTE", "SSR_NEW_UNTIERED_TAIL",
           "SSR_NEW_ORDER_NOTE", "SSR_NEW_RULES_LINE", "ssr_si_text", "ssr_tiered", "ssr_new_rank", "ssr_new_fault",
           "ssr_new_rules_line", "ssr_new_block"]
